"""Tests de ``quantlab.data.manifest``.

Chaque valeur attendue porte sa source, et aucune ne vient de la sortie du code.
Quatre sources sont employées :

- (a) un calcul écrit à la main dans le commentaire du test ;
- (b) une identité ou une propriété mathématique ;
- (c) une valeur publiée, ici les vecteurs de FIPS 180-4 ;
- (d) une implémentation indépendante, ici ``hashlib`` de la bibliothèque
  standard, sollicitée sur le même intrant.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from quantlab.core.errors import DataQualityError
from quantlab.core.paths import Layer
from quantlab.core.types import Frequency
from quantlab.data.manifest import (
    FRAME_DIGEST_VERSION,
    NULL_TOKEN,
    DatasetManifest,
    ProvenanceError,
    find_manifest,
    lineage,
    manifest_path_for,
    read_manifest,
    require_gold_ready,
    require_manifest,
    sha256_file,
    sha256_frame,
    write_manifest,
)

# ---------------------------------------------------------------------------
# Fabriques de test
# ---------------------------------------------------------------------------


def make_manifest(**overrides: object) -> DatasetManifest:
    """Rend un manifeste complet, que chaque test dégrade à sa guise."""
    champs: dict[str, object] = {
        "dataset_id": "demo_gold",
        "source": "Yahoo Finance, API v8",
        "provider": "quantlab.data.providers.yahoo",
        "url": "https://query1.finance.yahoo.com/v8/finance/chart/SPY",
        "download_timestamp": datetime(2026, 9, 1, 13, 45, tzinfo=UTC),
        "data_start": date(2010, 1, 4),
        "data_end": date(2026, 8, 31),
        "frequency": Frequency.DAILY,
        "timezone": "America/New_York",
        "exchange": "XNYS",
        "currency": "USD",
        "adjusted": True,
        "point_in_time": False,
        "survivorship_free": None,
        "corporate_actions": "dividendes et divisions appliqués par la source",
        "revision_policy": "les prix ajustés sont recalculés à chaque dividende",
        "license": "Yahoo, usage personnel",
        "license_url": "https://legal.yahoo.com/",
        "checksum_sha256": "0" * 64,
        "n_rows": 4_192,
        "n_columns": 2,
        "columns": ("close", "volume"),
        "processing_version": "1.0.0",
        "layer": Layer.GOLD,
        "parent_datasets": ("demo_silver",),
        "notes": "jeu de démonstration",
    }
    champs.update(overrides)
    return DatasetManifest(**champs)  # type: ignore[arg-type]


def write_chain(root: Path) -> None:
    """Écrit trois manifestes en chaîne : brut, silver, gold."""
    brut = make_manifest(
        dataset_id="demo_raw",
        layer=Layer.RAW,
        parent_datasets=(),
        checksum_sha256="1" * 64,
    )
    silver = make_manifest(
        dataset_id="demo_silver",
        layer=Layer.SILVER,
        parent_datasets=("demo_raw",),
        checksum_sha256="2" * 64,
    )
    gold = make_manifest(dataset_id="demo_gold", checksum_sha256="3" * 64)
    for m in (brut, silver, gold):
        write_manifest(m, manifest_path_for(m.dataset_id, m.layer, manifests_dir=root))


def condense_a_la_main(morceaux: list[str]) -> str:
    """Rend le condensé de la suite d'octets documentée, écrite morceau par morceau.

    La documentation de :func:`sha256_frame` impose que chaque morceau entre
    dans le condenseur précédé de sa longueur en octets, sur huit octets
    gros-boutiens. La fonction applique cette règle littéralement, sans rien
    emprunter au module contrôlé : elle n'utilise que ``hashlib``, source (d).
    """
    condenseur = hashlib.sha256()
    for morceau in morceaux:
        octets = morceau.encode("utf-8")
        condenseur.update(len(octets).to_bytes(8, "big"))
        condenseur.update(octets)
    return condenseur.hexdigest()


# ---------------------------------------------------------------------------
# sha256_file
# ---------------------------------------------------------------------------


def test_sha256_file_vecteur_publie_chaine_vide(tmp_path: Path) -> None:
    """Source (c) : vecteur de la chaîne vide, NIST FIPS 180-4, annexe des
    exemples de SHA-256, valeur publiée
    e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855."""
    fichier = tmp_path / "vide.bin"
    fichier.write_bytes(b"")
    assert sha256_file(fichier) == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_sha256_file_vecteur_publie_abc(tmp_path: Path) -> None:
    """Source (c) : vecteur « abc » de FIPS 180-2 annexe B.1, repris dans
    FIPS 180-4, valeur publiée
    ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad."""
    fichier = tmp_path / "abc.bin"
    fichier.write_bytes(b"abc")
    assert sha256_file(fichier) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_sha256_file_decoupage_sans_effet(tmp_path: Path) -> None:
    """Source (d) : ``hashlib`` sur le contenu entier, contre la lecture par
    blocs. Le fichier fait 3 MiB, donc plus de deux blocs par défaut, et deux
    tailles de bloc sont comparées."""
    contenu = np.random.default_rng(7).integers(0, 256, size=3 * 1024 * 1024, dtype=np.uint8).tobytes()
    fichier = tmp_path / "gros.bin"
    fichier.write_bytes(contenu)
    attendu = hashlib.sha256(contenu).hexdigest()
    assert sha256_file(fichier) == attendu
    assert sha256_file(fichier, chunk_size=1024) == attendu


def test_sha256_file_absent_leve(tmp_path: Path) -> None:
    with pytest.raises(ProvenanceError, match="introuvable"):
        sha256_file(tmp_path / "jamais_ecrit.bin")


# ---------------------------------------------------------------------------
# sha256_frame
# ---------------------------------------------------------------------------


def test_sha256_frame_suit_l_encodage_documente() -> None:
    """Source (a) : la suite d'octets documentée est reconstruite à la main.

    Le tableau porte deux colonnes, « b » de flottants et « a » de textes, et un
    index entier nommé « i ». Chaque morceau entre précédé de sa longueur en
    octets, sur huit octets gros-boutiens. L'ordre documenté est la version,
    « nrows=2 », « ncols=2 », « index=yes », « index-name=i », puis les deux
    valeurs d'index. Viennent enfin les colonnes triées par nom, donc « a »
    avant « b ». Les flottants s'écrivent par leur repr : 2.5 et -1.0.
    """
    df = pd.DataFrame({"b": [2.5, -1.0], "a": ["x", "y"]}, index=pd.Index([10, 11], name="i"))
    morceaux = [
        FRAME_DIGEST_VERSION,
        "nrows=2",
        "ncols=2",
        "index=yes",
        "index-name=i",
        "10",
        "11",
        "column=a",
        "x",
        "y",
        "column=b",
        "2.5",
        "-1.0",
    ]
    assert sha256_frame(df) == condense_a_la_main(morceaux)


def test_sha256_frame_deux_ecritures_donnent_la_meme_empreinte(tmp_path: Path) -> None:
    """Source (b) : identité. Le même contenu écrit deux fois en Parquet rend
    deux fichiers dont les empreintes de FICHIER peuvent différer, alors que
    l'empreinte de TABLEAU doit être la même. C'est la raison d'être de
    :func:`sha256_frame`."""
    index = pd.date_range("2020-01-01", periods=5, freq="D", name="date")
    df = pd.DataFrame({"close": [1.0, 2.0, 3.0, 4.0, 5.0], "volume": [10, 20, 30, 40, 50]}, index=index)
    premier = tmp_path / "un.parquet"
    second = tmp_path / "deux.parquet"
    df.to_parquet(premier)
    df.to_parquet(second)
    assert sha256_frame(pd.read_parquet(premier)) == sha256_frame(pd.read_parquet(second))
    assert sha256_frame(pd.read_parquet(premier)) == sha256_frame(df)


def test_sha256_frame_change_si_une_valeur_change() -> None:
    """Source (b) : une cellule modifiée change le condensé. La modification
    porte sur le dernier bit utile d'un flottant, donc le plus petit changement
    représentable."""
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0]})
    modifie = df.copy()
    modifie.loc[2, "x"] = np.nextafter(3.0, 4.0)
    assert sha256_frame(df) != sha256_frame(modifie)


def test_sha256_frame_invariant_a_l_ordre_des_colonnes() -> None:
    """Source (b) : la documentation trie les colonnes, donc l'empreinte ne
    dépend pas de leur rangement."""
    df = pd.DataFrame({"x": [1.0, 2.0], "y": [3.0, 4.0], "a": [5.0, 6.0]})
    assert sha256_frame(df) == sha256_frame(df[["y", "a", "x"]])


def test_sha256_frame_sensible_a_l_ordre_des_lignes() -> None:
    """Source (b) : une série temporelle renversée n'est pas la même donnée,
    donc son empreinte diffère."""
    index = pd.date_range("2020-01-01", periods=3, freq="D")
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0]}, index=index)
    assert sha256_frame(df) != sha256_frame(df.iloc[::-1])


def test_sha256_frame_sensible_a_l_index() -> None:
    """Source (b) : deux tableaux aux mêmes valeurs mais aux dates différentes
    sont deux jeux différents, et l'exclusion de l'index les confond."""
    valeurs = {"x": [1.0, 2.0]}
    a = pd.DataFrame(valeurs, index=pd.to_datetime(["2020-01-01", "2020-01-02"]))
    b = pd.DataFrame(valeurs, index=pd.to_datetime(["2021-01-01", "2021-01-02"]))
    assert sha256_frame(a) != sha256_frame(b)
    assert sha256_frame(a, include_index=False) == sha256_frame(b, include_index=False)


def test_sha256_frame_valeurs_manquantes_confondues() -> None:
    """Source (a) : la documentation dit que ``None``, ``NaN`` et ``pandas.NA``
    rendent le même jeton, donc les trois tableaux ci-dessous ont la même
    empreinte. Le test verrouille ce choix déclaré, il ne le découvre pas."""
    a = pd.DataFrame({"x": [1.0, np.nan]})
    b = pd.DataFrame({"x": [1.0, None]}, dtype="float64")
    c = pd.DataFrame({"x": pd.array([1.0, pd.NA], dtype="Float64")})
    assert sha256_frame(a) == sha256_frame(b) == sha256_frame(c)


def test_sha256_frame_cas_limites() -> None:
    """Source (b) : quatre cas limites rendent tous un condensé hexadécimal de
    64 caractères, et les cas distincts restent distincts. Le rendement de
    -100 % est représenté par la valeur -1.0, qui doit passer comme une autre."""
    vide = pd.DataFrame({"x": pd.Series(dtype="float64")})
    un_point = pd.DataFrame({"x": [1.0]})
    constante = pd.DataFrame({"x": [2.0, 2.0, 2.0]})
    ruine = pd.DataFrame({"x": [-1.0, 0.0, 0.0]})
    empreintes = [sha256_frame(d) for d in (vide, un_point, constante, ruine)]
    for empreinte in empreintes:
        assert len(empreinte) == 64
        assert set(empreinte) <= set("0123456789abcdef")
    assert len(set(empreintes)) == 4


def test_sha256_frame_ancre_dates_booleens_et_manquant() -> None:
    """Source (a) : second ancrage écrit à la main, sur les trois règles que le
    premier ancrage ne touchait pas.

    Un, un horodatage s'écrit en ISO 8601, donc ``« 2020-03-02T00:00:00 »`` avec
    un T et non une espace. Deux, un booléen s'écrit ``« true »`` ou
    ``« false »``, et surtout AVANT le test d'entier, sans quoi ``True``
    s'écrirait ``« 1 »`` et se confondrait avec la colonne d'entiers voisine.
    Trois, une valeur manquante s'écrit :data:`NULL_TOKEN`. Les colonnes sont
    triées par nom, donc « flag », « n », puis « px ».
    """
    index = pd.DatetimeIndex(["2020-03-02", "2020-03-03"], name="date")
    df = pd.DataFrame(
        {"flag": [True, False], "n": [1, 0], "px": [10.5, np.nan]},
        index=index,
    )
    morceaux = [
        FRAME_DIGEST_VERSION,
        "nrows=2",
        "ncols=3",
        "index=yes",
        "index-name=date",
        "2020-03-02T00:00:00",
        "2020-03-03T00:00:00",
        "column=flag",
        "true",
        "false",
        "column=n",
        "1",
        "0",
        "column=px",
        "10.5",
        NULL_TOKEN,
    ]
    assert sha256_frame(df) == condense_a_la_main(morceaux)


def test_sha256_frame_ancre_sans_index() -> None:
    """Source (a) : l'exclusion de l'index se marque dans le flux par
    ``« index=no »``, et aucune valeur d'index ne suit. Sans ce marqueur, deux
    appels de sens opposé pourraient rendre le même condensé."""
    df = pd.DataFrame({"a": [1.0]}, index=pd.Index([99], name="i"))
    morceaux = [FRAME_DIGEST_VERSION, "nrows=1", "ncols=1", "index=no", "column=a", "1.0"]
    assert sha256_frame(df, include_index=False) == condense_a_la_main(morceaux)


def test_sha256_frame_booleen_ne_se_confond_pas_avec_entier() -> None:
    """Source (a) : le module écrit ``« true »`` pour ``True`` et ``« 1 »`` pour
    l'entier ``1``, donc les deux colonnes ci-dessous diffèrent. Le test garde
    l'ordre des tests de type, ``bool`` héritant de ``int`` en Python."""
    booleens = pd.DataFrame({"x": [True, False, True]})
    entiers = pd.DataFrame({"x": [1, 0, 1]})
    assert sha256_frame(booleens) != sha256_frame(entiers)


def test_sha256_frame_point_aveugle_texte_contre_nombre_declare() -> None:
    """Source (a) : limite DÉCLARÉE dans la docstring, verrouillée par un test.

    Une colonne d'entiers et la même colonne relue en texte s'écrivent pareil,
    donc rendent la même empreinte. Un typage qui dérape ne se voit pas ici, et
    c'est au contrôle de schéma de le voir. Le jour où ce choix change, ce test
    tombe et force la mise à jour de la documentation.
    """
    entiers = pd.DataFrame({"x": [1, 2, 3]})
    textes = pd.DataFrame({"x": ["1", "2", "3"]})
    assert sha256_frame(entiers) == sha256_frame(textes)


def test_sha256_frame_colonnes_dupliquees_refusees() -> None:
    """Source (a) : deux colonnes de même nom rendent le tableau ambigu, et le
    contrat du module dit que la fonction lève plutôt que de choisir."""
    df = pd.DataFrame([[1.0, 2.0]], columns=["x", "x"])
    with pytest.raises(DataQualityError, match="même nom"):
        sha256_frame(df)


@settings(deadline=None, max_examples=60)
@given(
    lignes=st.lists(
        st.tuples(
            st.floats(allow_nan=False, allow_infinity=False, width=32),
            st.floats(allow_nan=False, allow_infinity=False, width=32),
        ),
        min_size=2,
        max_size=12,
    )
)
def test_propriete_permutation_des_colonnes_et_ordre_des_lignes(
    lignes: list[tuple[float, float]],
) -> None:
    """Source (b) : deux propriétés algébriques de l'empreinte.

    Un, la permutation des colonnes laisse l'empreinte inchangée, puisque le
    hachage trie les colonnes. Deux, renverser les lignes change l'empreinte
    dès qu'il y a au moins deux lignes, l'index entrant dans le hachage et son
    ordre étant alors différent.
    """
    df = pd.DataFrame(lignes, columns=["x", "y"])
    assert sha256_frame(df) == sha256_frame(df[["y", "x"]])
    assert sha256_frame(df) != sha256_frame(df.iloc[::-1])


# ---------------------------------------------------------------------------
# Le modèle
# ---------------------------------------------------------------------------


def test_aller_retour_json(tmp_path: Path) -> None:
    """Source (b) : identité. Relire ce qu'on vient d'écrire rend le même
    objet, champ pour champ."""
    manifest = make_manifest()
    chemin = write_manifest(manifest, tmp_path / "m.json")
    assert read_manifest(chemin) == manifest


def test_aller_retour_conserve_les_trois_valeurs(tmp_path: Path) -> None:
    """Source (b) : ``None`` doit survivre au JSON en ``null``, sans devenir
    ``False``. Un booléen à deux valeurs perdrait ici l'information « non
    vérifié »."""
    for valeur in (None, True, False):
        manifest = make_manifest(survivorship_free=valeur)
        chemin = write_manifest(manifest, tmp_path / f"m_{valeur}.json")
        brut = json.loads(chemin.read_text(encoding="utf-8"))
        assert brut["survivorship_free"] is valeur
        assert read_manifest(chemin).survivorship_free is valeur


def test_horodatage_naif_refuse() -> None:
    """Source (a) : le contrat exige un fuseau. ``datetime(2026, 9, 1, 13, 45)``
    ne désigne aucun instant, donc la construction doit échouer."""
    with pytest.raises(ValidationError, match="fuseau"):
        make_manifest(download_timestamp=datetime(2026, 9, 1, 13, 45))


def test_horodatage_normalise_en_utc() -> None:
    """Source (a) : 08 h 45 à UTC-05:00 est le même instant que 13 h 45 UTC,
    puisque 8 + 5 = 13. Le manifeste doit stocker la seconde écriture."""
    est = timezone(timedelta(hours=-5))
    manifest = make_manifest(download_timestamp=datetime(2026, 9, 1, 8, 45, tzinfo=est))
    assert manifest.download_timestamp == datetime(2026, 9, 1, 13, 45, tzinfo=UTC)
    assert manifest.download_timestamp.utcoffset() == timedelta(0)


def test_champ_obligatoire_manquant_refuse() -> None:
    """Source (a) : ``source`` est déclaré obligatoire, donc son absence lève."""
    champs = make_manifest().model_dump()
    del champs["source"]
    with pytest.raises(ValidationError, match="source"):
        DatasetManifest(**champs)


def test_cle_inconnue_refusee() -> None:
    """Source (a) : ``StrictModel`` interdit les clés inconnues, donc une faute
    de frappe lève au lieu de créer un champ fantôme."""
    with pytest.raises(ValidationError, match="providr"):
        make_manifest(providr="yahoo")


def test_incoherences_refusees() -> None:
    """Source (a) : trois règles écrites, trois refus attendus. Une période qui
    finit avant de commencer, un compte de colonnes qui ne colle pas à la liste
    (2 déclarées pour 3 noms), et un jeu déclaré son propre parent."""
    with pytest.raises(ValidationError, match="précède"):
        make_manifest(data_start=date(2020, 1, 1), data_end=date(2019, 12, 31))
    with pytest.raises(ValidationError, match="n_columns"):
        make_manifest(n_columns=2, columns=("a", "b", "c"))
    with pytest.raises(ValidationError, match="propre parent"):
        make_manifest(dataset_id="x", parent_datasets=("x", "y"))


def test_devise_et_empreinte_controlees() -> None:
    """Source (a) : « USDX » a quatre lettres, donc n'est pas un code ISO 4217 ;
    « zz…z » n'est pas hexadécimal ; 63 caractères ne font pas 64."""
    with pytest.raises(ValidationError, match="ISO 4217"):
        make_manifest(currency="USDX")
    with pytest.raises(ValidationError, match="hexadécimaux"):
        make_manifest(checksum_sha256="z" * 64)
    with pytest.raises(ValidationError, match="hexadécimaux"):
        make_manifest(checksum_sha256="a" * 63)


# ---------------------------------------------------------------------------
# La règle du gold
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("champ", "valeur", "attendu"),
    [
        ("license", "", "license"),
        ("checksum_sha256", "", "checksum_sha256"),
        ("processing_version", "  ", "processing_version"),
        ("timezone", "", "timezone"),
        ("n_rows", 0, "n_rows"),
        ("parent_datasets", (), "parent_datasets"),
    ],
)
def test_gold_incomplet_refuse(champ: str, valeur: object, attendu: str) -> None:
    """Source (a) : la liste des champs exigés en gold est écrite dans le
    module, donc vider l'un d'eux doit produire un refus qui le nomme."""
    manifest = make_manifest(**{champ: valeur})
    assert attendu in manifest.missing_for_gold()
    with pytest.raises(ProvenanceError, match=attendu):
        require_gold_ready(manifest)


def test_gold_complet_accepte() -> None:
    """Source (b) : le manifeste de référence est complet par construction,
    donc rien ne manque et le contrôle passe sans lever."""
    manifest = make_manifest()
    assert manifest.missing_for_gold() == ()
    require_gold_ready(manifest)


def test_couche_brute_tolere_l_incomplet() -> None:
    """Source (a) : la règle ne porte que sur le gold, une donnée brute étant
    parfois livrée sans licence écrite."""
    require_gold_ready(make_manifest(layer=Layer.RAW, license="", parent_datasets=()))


@pytest.mark.parametrize("couche", [Layer.RAW, Layer.BRONZE, Layer.SILVER])
def test_la_regle_ne_mord_que_sur_le_gold(couche: Layer) -> None:
    """Source (a) : la docstring borne le contrôle à la seule couche gold.

    Les trois autres couches acceptent donc un manifeste incomplet. C'est le
    passage en silver qui oblige à trancher la licence, et la promotion en gold
    qui l'exige. Sans ce test, étendre le contrôle à bronze et à silver
    passerait inaperçu.
    """
    incomplet = make_manifest(layer=couche, license="", processing_version="", parent_datasets=())
    assert incomplet.missing_for_gold() != ()
    require_gold_ready(incomplet)


def test_write_manifest_refuse_un_gold_incomplet(tmp_path: Path) -> None:
    """Source (a) : l'écriture applique la même règle, sinon le fichier
    incomplet existerait sur le disque et se relirait plus tard."""
    with pytest.raises(ProvenanceError, match="license"):
        write_manifest(make_manifest(license=""), tmp_path / "m.json")
    assert not (tmp_path / "m.json").exists()


def test_survivorship_free_non_exige_en_gold() -> None:
    """Source (a) : le champ à trois valeurs ne figure pas dans la liste des
    exigences, précisément pour que « non vérifié » reste disponible."""
    assert make_manifest(survivorship_free=None).missing_for_gold() == ()


# ---------------------------------------------------------------------------
# Chemins, recherche, lignée
# ---------------------------------------------------------------------------


def test_manifest_path_for(tmp_path: Path) -> None:
    """Source (a) : le chemin documenté est
    ``<racine>/<couche>/<dataset_id>.json``."""
    chemin = manifest_path_for("demo_gold", Layer.GOLD, manifests_dir=tmp_path)
    assert chemin == tmp_path / "gold" / "demo_gold.json"
    assert manifest_path_for("demo_gold", "gold", manifests_dir=tmp_path) == chemin


def test_manifest_path_for_refuse_un_identifiant_dangereux(tmp_path: Path) -> None:
    """Source (a) : « ../evasion » écrirait hors du répertoire des manifestes."""
    with pytest.raises(ProvenanceError, match="séparateur"):
        manifest_path_for("../evasion", Layer.GOLD, manifests_dir=tmp_path)
    with pytest.raises(ProvenanceError, match="vide"):
        manifest_path_for("   ", Layer.GOLD, manifests_dir=tmp_path)


def test_read_manifest_absent_leve(tmp_path: Path) -> None:
    with pytest.raises(ProvenanceError, match="introuvable"):
        read_manifest(tmp_path / "rien.json")


def test_read_manifest_json_casse_leve(tmp_path: Path) -> None:
    chemin = tmp_path / "casse.json"
    chemin.write_text("{ceci n'est pas du JSON", encoding="utf-8")
    with pytest.raises(ProvenanceError, match="illisible ou invalide"):
        read_manifest(chemin)


def test_require_manifest_lit_et_controle(tmp_path: Path) -> None:
    """Source (b) : la porte d'entrée rend le même objet que celui écrit."""
    write_chain(tmp_path)
    relu = require_manifest("demo_gold", Layer.GOLD, manifests_dir=tmp_path)
    assert relu.dataset_id == "demo_gold"
    assert relu.parent_datasets == ("demo_silver",)


def test_require_manifest_absent_leve(tmp_path: Path) -> None:
    """Source (a) : un jeu sans manifeste ne se charge pas en gold."""
    with pytest.raises(ProvenanceError, match="introuvable"):
        require_manifest("jamais_publie", Layer.GOLD, manifests_dir=tmp_path)


def test_lineage_trois_niveaux(tmp_path: Path) -> None:
    """Source (a) : la chaîne écrite est demo_raw -> demo_silver -> demo_gold,
    et l'ordre documenté va de l'ancêtre au jeu demandé."""
    write_chain(tmp_path)
    chaine = lineage("demo_gold", manifests_dir=tmp_path)
    assert [m.dataset_id for m in chaine] == ["demo_raw", "demo_silver", "demo_gold"]
    assert [m.layer for m in chaine] == [Layer.RAW, Layer.SILVER, Layer.GOLD]


def test_lineage_sans_parent(tmp_path: Path) -> None:
    """Source (a) : un jeu brut sans parent rend une liste d'un seul élément."""
    brut = make_manifest(dataset_id="solitaire", layer=Layer.RAW, parent_datasets=())
    write_manifest(brut, manifest_path_for(brut.dataset_id, brut.layer, manifests_dir=tmp_path))
    assert [m.dataset_id for m in lineage("solitaire", manifests_dir=tmp_path)] == ["solitaire"]


def test_lineage_parent_manquant_leve(tmp_path: Path) -> None:
    """Source (a) : demo_gold cite demo_silver, qui n'est pas écrit ici."""
    gold = make_manifest()
    write_manifest(gold, manifest_path_for(gold.dataset_id, gold.layer, manifests_dir=tmp_path))
    with pytest.raises(ProvenanceError, match="demo_silver"):
        lineage("demo_gold", manifests_dir=tmp_path)


def test_lineage_cycle_leve(tmp_path: Path) -> None:
    """Source (a) : « a » a pour parent « b » et « b » a pour parent « a ».
    La remontée ne se termine pas, donc la fonction doit lever."""
    a = make_manifest(dataset_id="a", layer=Layer.SILVER, parent_datasets=("b",))
    b = make_manifest(dataset_id="b", layer=Layer.BRONZE, parent_datasets=("a",))
    for m in (a, b):
        write_manifest(m, manifest_path_for(m.dataset_id, m.layer, manifests_dir=tmp_path))
    with pytest.raises(ProvenanceError, match="cycle"):
        lineage("a", manifests_dir=tmp_path)


def test_lineage_parent_partage_apparait_une_fois(tmp_path: Path) -> None:
    """Source (a) : deux silver issus du même brut, un gold issu des deux. Le
    brut est cité deux fois dans la lignée mais ne doit apparaître qu'une, et
    avant les deux silver qui en descendent."""
    brut = make_manifest(dataset_id="r", layer=Layer.RAW, parent_datasets=())
    s1 = make_manifest(dataset_id="s1", layer=Layer.SILVER, parent_datasets=("r",))
    s2 = make_manifest(dataset_id="s2", layer=Layer.SILVER, parent_datasets=("r",))
    gold = make_manifest(dataset_id="g", parent_datasets=("s1", "s2"))
    for m in (brut, s1, s2, gold):
        write_manifest(m, manifest_path_for(m.dataset_id, m.layer, manifests_dir=tmp_path))
    ids = [m.dataset_id for m in lineage("g", manifests_dir=tmp_path)]
    assert ids == ["r", "s1", "s2", "g"]


@pytest.mark.parametrize("motif", ["demo_ra?", "demo_*", "[d]emo_raw", "demo_raw*"])
def test_find_manifest_ne_traite_pas_l_identifiant_comme_un_motif(tmp_path: Path, motif: str) -> None:
    """Source (a) : la docstring dit que l'identifiant se compare caractère pour
    caractère, donc aucun de ces quatre motifs ne désigne un jeu écrit.

    Le contrôle compte : une recherche par motif rendrait le manifeste de
    ``« demo_raw »`` pour la demande ``« demo_ra? »``, en silence, et la lignée
    d'un jeu attribuerait alors le mauvais ancêtre.
    """
    brut = make_manifest(dataset_id="demo_raw", layer=Layer.RAW, parent_datasets=())
    write_manifest(brut, manifest_path_for(brut.dataset_id, brut.layer, manifests_dir=tmp_path))
    with pytest.raises(ProvenanceError, match="aucun manifeste"):
        find_manifest(motif, manifests_dir=tmp_path)


def test_find_manifest_trouve_l_identifiant_exact(tmp_path: Path) -> None:
    """Source (a) : le pendant positif du test précédent, sinon un refus
    systématique le ferait passer."""
    write_chain(tmp_path)
    assert find_manifest("demo_silver", manifests_dir=tmp_path).layer is Layer.SILVER


def test_find_manifest_identifiant_reutilise_leve(tmp_path: Path) -> None:
    """Source (a) : le même identifiant dans deux couches signale une
    réutilisation, que la convention interdit."""
    a = make_manifest(dataset_id="doublon", layer=Layer.RAW, parent_datasets=())
    b = make_manifest(dataset_id="doublon", layer=Layer.SILVER, parent_datasets=("r",))
    for m in (a, b):
        write_manifest(m, manifest_path_for(m.dataset_id, m.layer, manifests_dir=tmp_path))
    with pytest.raises(ProvenanceError, match="plusieurs manifestes"):
        find_manifest("doublon", manifests_dir=tmp_path)

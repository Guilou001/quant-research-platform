"""Contrôles du lac de données.

Aucune valeur attendue de ce fichier ne vient de la sortie du code. Chaque test
dit en commentaire d'où vient son attendu : une valeur écrite à la main dans le
test lui-même, une identité mathématique, ou une propriété du format Parquet.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import duckdb
import pandas as pd
import polars as pl
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from quantlab.core.errors import DataQualityError
from quantlab.core.paths import Layer
from quantlab.data.lake import (
    MANIFEST_FILENAME,
    ProvenanceError,
    _fingerprint,
    describe_table,
    duckdb_connection,
    list_tables,
    promote,
    query,
    read_table,
    table_exists,
    to_analytics,
    write_table,
)

# Cinq séances de janvier 2020, écrites à la main. Tout attendu de comptage de
# ce fichier se déduit de ces cinq lignes, jamais d'une exécution du code.
PRICES = pl.DataFrame(
    {
        "date": ["2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07", "2020-01-08"],
        "ticker": ["SPY", "SPY", "SPY", "SPY", "SPY"],
        "close": [324.87, 322.41, 323.64, 322.73, 324.45],
    }
)

SOURCE_MANIFEST = {
    "source": "test",
    "url": "https://example.invalid/prices.csv",
    "downloaded_at": "2026-09-01T00:00:00+00:00",
    "license": "usage de test",
}


@pytest.fixture
def lake_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Déplace la racine du laboratoire dans ``tmp_path``.

    Sans ce détournement, les tests écriraient dans le vrai lac du dépôt.
    """
    monkeypatch.setenv("QUANTLAB_ROOT", str(tmp_path))
    for layer in Layer:
        (tmp_path / "data" / layer.value).mkdir(parents=True, exist_ok=True)
    return tmp_path


# --------------------------------------------------------------------------- #
# Aller-retour d'écriture et de lecture
# --------------------------------------------------------------------------- #


def test_ecriture_puis_lecture_rend_les_memes_valeurs(lake_root: Path) -> None:
    """Source (a) : l'attendu est le tableau littéral écrit en tête de fichier."""
    receipt = write_table(PRICES, "prices", Layer.BRONZE)

    assert receipt.n_rows == 5  # cinq lignes écrites à la main dans PRICES
    assert receipt.n_columns == 3  # date, ticker, close
    assert receipt.fingerprint.startswith("sha256:")

    back = read_table("prices", Layer.BRONZE)
    assert isinstance(back, pl.DataFrame)
    assert back.sort("date").to_dicts() == PRICES.sort("date").to_dicts()


def test_lecture_pandas_rend_un_dataframe_pandas(lake_root: Path) -> None:
    """Source (a) : cinq lignes et trois colonnes, comptées dans PRICES."""
    write_table(PRICES, "prices", Layer.BRONZE)
    back = read_table("prices", Layer.BRONZE, engine="pandas")
    assert isinstance(back, pd.DataFrame)
    assert back.shape == (5, 3)


def test_projection_et_filtre(lake_root: Path) -> None:
    """Source (a) : trois clôtures de PRICES dépassent 323,00 (324,87 ; 323,64 ; 324,45)."""
    write_table(PRICES, "prices", Layer.BRONZE)
    back = read_table(
        "prices",
        Layer.BRONZE,
        columns=["date", "close"],
        filters=[("close", ">", 323.0)],
    )
    assert isinstance(back, pl.DataFrame)
    assert back.columns == ["date", "close"]
    assert back.height == 3
    assert sorted(back["close"].to_list()) == [323.64, 324.45, 324.87]


def test_filtre_in_et_operateur_inconnu(lake_root: Path) -> None:
    """Source (a) : deux dates demandées sur les cinq écrites."""
    write_table(PRICES, "prices", Layer.BRONZE)
    back = read_table("prices", Layer.BRONZE, filters=[("date", "in", ["2020-01-02", "2020-01-08"])])
    assert isinstance(back, pl.DataFrame)
    assert back.height == 2
    with pytest.raises(ValueError, match="opérateur inconnu"):
        read_table("prices", Layer.BRONZE, filters=[("close", "~=", 1.0)])


def test_filtre_not_in(lake_root: Path) -> None:
    """Source (a) : cinq dates écrites moins les deux exclues, donc trois lignes."""
    write_table(PRICES, "prices", Layer.BRONZE)
    back = read_table("prices", Layer.BRONZE, filters=[("date", "not in", ["2020-01-02", "2020-01-08"])])
    assert isinstance(back, pl.DataFrame)
    assert back["date"].to_list() == ["2020-01-03", "2020-01-06", "2020-01-07"]


def test_moteur_inconnu_leve(lake_root: Path) -> None:
    write_table(PRICES, "prices", Layer.BRONZE)
    with pytest.raises(ValueError, match="moteur inconnu"):
        read_table("prices", Layer.BRONZE, engine="pyspark")  # type: ignore[arg-type]


def test_lecture_dun_jeu_absent_leve(lake_root: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_table("inexistant", Layer.SILVER)


def test_identifiant_qui_sort_du_lac_est_refuse(lake_root: Path) -> None:
    """Un identifiant avec séparateur écrirait hors du lac."""
    with pytest.raises(ValueError, match="séparateur"):
        write_table(PRICES, "../evil", Layer.BRONZE)


# --------------------------------------------------------------------------- #
# Provenance
# --------------------------------------------------------------------------- #


def test_gold_refuse_sans_manifeste(lake_root: Path) -> None:
    """La règle de l'étage gold : pas de manifeste, pas d'écriture."""
    with pytest.raises(ProvenanceError, match="sans manifeste"):
        write_table(PRICES, "panel", Layer.GOLD)
    assert not table_exists("panel", Layer.GOLD)


def test_gold_accepte_avec_manifeste(lake_root: Path) -> None:
    """Source (a) : le manifeste rendu doit rendre le dictionnaire passé."""
    receipt = write_table(PRICES, "panel", Layer.GOLD, manifest=SOURCE_MANIFEST)
    payload = json.loads(receipt.manifest_path.read_text("utf-8"))
    assert payload["source"] == SOURCE_MANIFEST
    assert payload["layer"] == "gold"
    assert payload["n_rows"] == 5  # cinq lignes de PRICES
    assert receipt.manifest_path.name == MANIFEST_FILENAME


def test_manifeste_non_serialisable_est_refuse(lake_root: Path) -> None:
    with pytest.raises(ProvenanceError, match="non sérialisable"):
        write_table(PRICES, "panel", Layer.GOLD, manifest=object())


def test_raw_est_immuable(lake_root: Path) -> None:
    """La règle de l'étage raw : la preuve ne se corrige pas, même sur demande."""
    write_table(PRICES, "yahoo_spy", Layer.RAW)
    with pytest.raises(ProvenanceError, match="immuable"):
        write_table(PRICES, "yahoo_spy", Layer.RAW, overwrite=True)


def test_ecrasement_refuse_sans_drapeau(lake_root: Path) -> None:
    write_table(PRICES, "prices", Layer.BRONZE)
    with pytest.raises(DataQualityError, match="existe déjà"):
        write_table(PRICES, "prices", Layer.BRONZE)
    receipt = write_table(PRICES, "prices", Layer.BRONZE, overwrite=True)
    assert receipt.n_rows == 5  # cinq lignes de PRICES


def test_empreinte_stable_pour_le_meme_contenu(lake_root: Path) -> None:
    """Source (b) : identité. Le même contenu écrit deux fois a la même empreinte."""
    first = write_table(PRICES, "prices", Layer.BRONZE)
    second = write_table(PRICES, "prices", Layer.BRONZE, overwrite=True)
    assert first.fingerprint == second.fingerprint

    modified = PRICES.with_columns(pl.col("close") + 1.0)
    third = write_table(modified, "prices", Layer.BRONZE, overwrite=True)
    assert third.fingerprint != first.fingerprint


def test_empreinte_recalculee_a_la_main(lake_root: Path) -> None:
    """Source (d) : hashlib recalcule l'empreinte hors du module, sur les mêmes octets.

    La règle documentée est : empreinte SHA-256 de chaque fichier, puis SHA-256
    de la suite triée des couples (chemin relatif, empreinte du fichier). Le test
    la réapplique avec la bibliothèque standard, sans appeler le code du lac.
    """
    receipt = write_table(PRICES, "prices", Layer.BRONZE)
    assert len(receipt.files) == 1  # un jeu non partitionné s'écrit en un fichier

    attendu = hashlib.sha256()
    for relative in sorted(receipt.files):
        octets = (receipt.path / relative).read_bytes()
        attendu.update(relative.encode("utf-8"))
        attendu.update(hashlib.sha256(octets).hexdigest().encode("ascii"))
    assert receipt.fingerprint == "sha256:" + attendu.hexdigest()


def test_empreinte_detecte_un_octet_modifie(lake_root: Path) -> None:
    """Source (b) : l'empreinte scelle des octets, donc un octet retourné la change.

    C'est la propriété que la docstring de l'empreinte annonce. Sans ce contrôle,
    une empreinte calculée sur la seule taille des fichiers passerait les autres
    tests.
    """
    receipt = write_table(PRICES, "prices", Layer.BRONZE)
    fichier = receipt.path / receipt.files[0]
    octets = bytearray(fichier.read_bytes())
    octets[len(octets) // 2] ^= 0xFF  # un octet retourné, la taille ne bouge pas
    fichier.write_bytes(bytes(octets))

    apres, fiches = _fingerprint(receipt.path)
    assert apres != receipt.fingerprint
    assert fiches[0]["bytes"] == len(octets)  # même taille, empreinte différente


# --------------------------------------------------------------------------- #
# Catalogue
# --------------------------------------------------------------------------- #


def test_catalogue_et_fiche(lake_root: Path) -> None:
    """Source (a) : deux jeux écrits, cinq lignes chacun pour le premier."""
    write_table(PRICES, "prices", Layer.BRONZE)
    write_table(PRICES, "autre", Layer.BRONZE)
    assert list_tables(Layer.BRONZE) == ["autre", "prices"]
    assert list_tables(Layer.SILVER) == []
    assert table_exists("prices", Layer.BRONZE)
    assert not table_exists("prices", Layer.SILVER)

    fiche = describe_table("prices", Layer.BRONZE)
    assert fiche.n_rows == 5
    assert set(fiche.schema) == {"date", "ticker", "close"}
    assert fiche.schema["close"] == "Float64"
    assert fiche.partition_by == ()
    assert fiche.has_manifest
    assert fiche.total_bytes > 0
    with pytest.raises(FileNotFoundError):
        describe_table("prices", Layer.SILVER)


def test_partitionnement_hive(lake_root: Path) -> None:
    """Source (a) : cinq lignes SPY et deux lignes QQQ, comptées à la main."""
    two = pl.concat(
        [
            PRICES,
            pl.DataFrame(
                {
                    "date": ["2020-01-02", "2020-01-03"],
                    "ticker": ["QQQ", "QQQ"],
                    "close": [216.16, 214.29],
                }
            ),
        ]
    )
    receipt = write_table(two, "prices", Layer.BRONZE, partition_by=["ticker"])
    assert receipt.n_rows == 7  # 5 + 2
    assert (receipt.path / "ticker=SPY").is_dir()
    assert (receipt.path / "ticker=QQQ").is_dir()

    fiche = describe_table("prices", Layer.BRONZE)
    assert fiche.partition_by == ("ticker",)

    back = read_table("prices", Layer.BRONZE, filters=[("ticker", "==", "QQQ")])
    assert isinstance(back, pl.DataFrame)
    assert back.height == 2  # deux lignes QQQ écrites à la main


def test_partition_by_ignore_un_ancetre_qui_porte_un_egal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Source (b) : un jeu non partitionné n'a aucune colonne de partition.

    La lecture des noms de répertoires doit s'arrêter au répertoire du jeu. Le
    lac est ici posé sous « lake=v1 », un nom parfaitement légitime qui contient
    un « = » : avant correctif, ce jeu se décrivait comme partitionné par
    « lake ».
    """
    monkeypatch.setenv("QUANTLAB_ROOT", str(tmp_path / "lake=v1"))

    write_table(PRICES, "prices", Layer.BRONZE)
    assert describe_table("prices", Layer.BRONZE).partition_by == ()

    write_table(PRICES, "parts", Layer.BRONZE, partition_by=["ticker"])
    assert describe_table("parts", Layer.BRONZE).partition_by == ("ticker",)


def test_partition_numerique_garde_ses_valeurs(lake_root: Path) -> None:
    """Source (a) : trois lignes écrites à la main, 2020 deux fois et 2021 une fois.

    La colonne de partition ne vit plus dans le fichier mais dans le nom du
    répertoire, et son type est réinféré à la lecture. Mesuré avec polars 1.44 :
    une partition entière revient en ``Int64``, en dernière colonne.
    """
    frame = pl.DataFrame({"annee": [2020, 2020, 2021], "close": [1.0, 2.0, 3.0]})
    write_table(frame, "annuel", Layer.BRONZE, partition_by=["annee"])

    back = read_table("annuel", Layer.BRONZE)
    assert isinstance(back, pl.DataFrame)
    assert sorted(back["annee"].to_list()) == [2020, 2020, 2021]
    assert back["annee"].dtype == pl.Int64
    assert back.columns[-1] == "annee"
    assert sorted(back.filter(pl.col("annee") == 2020)["close"].to_list()) == [1.0, 2.0]


def test_colonne_de_partition_absente(lake_root: Path) -> None:
    with pytest.raises(ValueError, match="partition absentes"):
        write_table(PRICES, "prices", Layer.BRONZE, partition_by=["marche"])


# --------------------------------------------------------------------------- #
# SQL
# --------------------------------------------------------------------------- #


def test_requete_duckdb_retrouve_le_compte(lake_root: Path) -> None:
    """Source (a) : cinq lignes écrites, donc cinq lignes comptées par DuckDB."""
    write_table(PRICES, "prices", Layer.BRONZE)
    out = query("SELECT count(*) AS n FROM bronze_prices")
    assert out["n"].to_list() == [5]


def test_requete_duckdb_par_groupe(lake_root: Path) -> None:
    """Source (a) : cinq lignes SPY et deux lignes QQQ, comptées à la main."""
    two = pl.concat(
        [
            PRICES,
            pl.DataFrame(
                {
                    "date": ["2020-01-02", "2020-01-03"],
                    "ticker": ["QQQ", "QQQ"],
                    "close": [216.16, 214.29],
                }
            ),
        ]
    )
    write_table(two, "prices", Layer.SILVER, partition_by=["ticker"])
    out = query("SELECT ticker, count(*) AS n FROM silver_prices GROUP BY 1 ORDER BY 1")
    assert out.to_dicts() == [{"ticker": "QQQ", "n": 2}, {"ticker": "SPY", "n": 5}]


def test_les_vues_portent_le_nom_etage_puis_jeu(lake_root: Path) -> None:
    write_table(PRICES, "prices", Layer.BRONZE)
    write_table(PRICES, "prices", Layer.SILVER)
    with duckdb_connection() as con:
        noms = {row[0] for row in con.execute("SELECT view_name FROM duckdb_views()").fetchall()}
    assert {"bronze_prices", "silver_prices"} <= noms


def test_lecture_seule_ne_pose_aucun_schema_scratch(lake_root: Path) -> None:
    """Source (b) : la différence entre les deux modes est l'existence du schéma."""
    write_table(PRICES, "prices", Layer.BRONZE)
    with duckdb_connection(read_only=True) as con, pytest.raises(duckdb.Error):
        con.execute("CREATE TABLE scratch.t AS SELECT 1 AS a")
    with duckdb_connection(read_only=False) as con:
        con.execute("CREATE TABLE scratch.t AS SELECT 1 AS a")
        assert con.execute("SELECT a FROM scratch.t").fetchall() == [(1,)]


# --------------------------------------------------------------------------- #
# La conversion vers l'analytique
# --------------------------------------------------------------------------- #


def test_to_analytics_trie_et_pose_un_index_utc() -> None:
    """Source (a) : l'ordre attendu est l'ordre chronologique écrit ici à la main."""
    desordre = pl.DataFrame({"date": ["2020-01-06", "2020-01-02", "2020-01-03"], "r": [0.03, 0.01, 0.02]})
    panel = to_analytics(desordre)
    assert isinstance(panel.index, pd.DatetimeIndex)
    assert panel.index.is_monotonic_increasing
    assert str(panel.index.tz) == "UTC"
    assert [d.strftime("%Y-%m-%d") for d in panel.index] == [
        "2020-01-02",
        "2020-01-03",
        "2020-01-06",
    ]
    # Les valeurs suivent leur date : 0,01 le 2, 0,02 le 3, 0,03 le 6.
    assert panel["r"].tolist() == [0.01, 0.02, 0.03]
    assert "date" not in panel.columns


def test_to_analytics_index_naif_si_timezone_none() -> None:
    frame = pl.DataFrame({"date": ["2020-01-02", "2020-01-03"], "r": [0.01, 0.02]})
    panel = to_analytics(frame, timezone=None)
    assert panel.index.tz is None


def test_to_analytics_leve_sur_doublon() -> None:
    """Deux fois la même séance : un panneau de rendements ne peut pas l'accepter."""
    frame = pl.DataFrame({"date": ["2020-01-02", "2020-01-02"], "r": [0.01, 0.02]})
    with pytest.raises(DataQualityError, match="doublon"):
        to_analytics(frame)


def test_to_analytics_leve_sur_index_non_trie_quand_sort_est_faux() -> None:
    frame = pl.DataFrame({"date": ["2020-01-03", "2020-01-02"], "r": [0.02, 0.01]})
    with pytest.raises(DataQualityError, match="pas trié"):
        to_analytics(frame, sort=False)


def test_to_analytics_leve_sur_colonne_absente() -> None:
    frame = pl.DataFrame({"jour": ["2020-01-02"], "r": [0.01]})
    with pytest.raises(DataQualityError, match="absente"):
        to_analytics(frame)


def test_to_analytics_leve_sur_date_manquante() -> None:
    frame = pl.DataFrame({"date": ["2020-01-02", None], "r": [0.01, 0.02]})
    with pytest.raises(DataQualityError, match="manquantes"):
        to_analytics(frame)


def test_to_analytics_reprend_un_index_pandas_deja_temporel() -> None:
    frame = pd.DataFrame(
        {"r": [0.02, 0.01]},
        index=pd.DatetimeIndex(["2020-01-03", "2020-01-02"], name="date"),
    )
    panel = to_analytics(frame)
    assert [d.strftime("%Y-%m-%d") for d in panel.index] == ["2020-01-02", "2020-01-03"]
    assert panel["r"].tolist() == [0.01, 0.02]


def test_to_analytics_accepte_une_serie_vide() -> None:
    """Cas limite : zéro ligne. La fonction rend un cadre vide, elle ne lève pas."""
    frame = pl.DataFrame({"date": [], "r": []}, schema={"date": pl.Utf8, "r": pl.Float64})
    panel = to_analytics(frame)
    assert len(panel) == 0
    assert isinstance(panel.index, pd.DatetimeIndex)


def test_to_analytics_accepte_un_point_unique_et_une_serie_constante() -> None:
    """Cas limites : une observation, puis des valeurs toutes égales."""
    un = to_analytics(pl.DataFrame({"date": ["2020-01-02"], "r": [0.0]}))
    assert len(un) == 1
    constante = pl.DataFrame({"date": ["2020-01-02", "2020-01-03", "2020-01-06"], "r": [0.5, 0.5, 0.5]})
    panel = to_analytics(constante)
    assert panel["r"].tolist() == [0.5, 0.5, 0.5]


# --------------------------------------------------------------------------- #
# Cas limites d'écriture
# --------------------------------------------------------------------------- #


def test_valeurs_extremes_survivent_a_laller_retour(lake_root: Path) -> None:
    """Source (b) : Parquet stocke le double IEEE 754, donc le retour est exact.

    Le rendement de -100 %, la valeur manquante et le NaN sont trois choses
    différentes, et elles doivent le rester après un passage par le disque.
    """
    frame = pl.DataFrame(
        {
            "date": ["2020-01-02", "2020-01-03", "2020-01-06"],
            "r": [-1.0, float("nan"), None],
        }
    )
    write_table(frame, "extremes", Layer.BRONZE)
    back = read_table("extremes", Layer.BRONZE)
    assert isinstance(back, pl.DataFrame)
    valeurs = back.sort("date")["r"].to_list()
    assert valeurs[0] == -1.0
    assert valeurs[1] != valeurs[1]  # NaN ne s'égale pas lui-même
    assert valeurs[2] is None


def test_ecriture_dun_tableau_vide_puis_relecture(lake_root: Path) -> None:
    """Cas limite : zéro ligne mais des colonnes. Le schéma survit."""
    vide = pl.DataFrame({"date": [], "close": []}, schema={"date": pl.Utf8, "close": pl.Float64})
    receipt = write_table(vide, "vide", Layer.BRONZE)
    assert receipt.n_rows == 0
    fiche = describe_table("vide", Layer.BRONZE)
    assert fiche.n_rows == 0
    assert set(fiche.schema) == {"date", "close"}


def test_tableau_sans_colonne_est_refuse(lake_root: Path) -> None:
    with pytest.raises(DataQualityError, match="sans colonne"):
        write_table(pl.DataFrame(), "rien", Layer.BRONZE)


def test_index_pandas_non_nomme_est_refuse(lake_root: Path) -> None:
    """Sans nom, l'index deviendrait une colonne appelée « None »."""
    frame = pd.DataFrame({"r": [0.01]}, index=pd.DatetimeIndex(["2020-01-02"]))
    with pytest.raises(DataQualityError, match="pas de nom"):
        write_table(frame, "prices", Layer.BRONZE)


def test_index_pandas_nomme_devient_une_colonne(lake_root: Path) -> None:
    frame = pd.DataFrame(
        {"r": [0.01, 0.02]}, index=pd.DatetimeIndex(["2020-01-02", "2020-01-03"], name="date")
    )
    write_table(frame, "prices", Layer.BRONZE)
    fiche = describe_table("prices", Layer.BRONZE)
    assert set(fiche.schema) == {"date", "r"}


# --------------------------------------------------------------------------- #
# Promotion
# --------------------------------------------------------------------------- #


def drop_weekend_placeholder(frame: pl.DataFrame) -> pl.DataFrame:
    """Retire la séance du 2020-01-06, prise ici comme décision de nettoyage."""
    return frame.filter(pl.col("date") != "2020-01-06")


def test_promotion_ecrit_le_parent_dans_le_manifeste_enfant(lake_root: Path) -> None:
    """Source (a) et (b) : cinq lignes moins une, et l'empreinte du parent, connue."""
    parent = write_table(PRICES, "prices", Layer.BRONZE, manifest=SOURCE_MANIFEST)
    enfant = promote(
        "prices",
        Layer.BRONZE,
        Layer.SILVER,
        transform=drop_weekend_placeholder,
        notes="séance du 6 janvier retirée pour l'exemple",
    )
    assert enfant.n_rows == 4  # 5 lignes de PRICES moins la séance retirée

    payload = json.loads(enfant.manifest_path.read_text("utf-8"))
    bloc = payload["parent"]
    assert bloc["dataset_id"] == "prices"
    assert bloc["layer"] == "bronze"
    assert bloc["fingerprint"] == parent.fingerprint
    assert bloc["n_rows"] == 5
    assert bloc["transform"] == "drop_weekend_placeholder"
    assert payload["notes"] == "séance du 6 janvier retirée pour l'exemple"
    # La provenance de la source d'origine descend avec le jeu.
    assert payload["source"] == SOURCE_MANIFEST


def test_promotion_vers_gold_sans_manifeste_reste_possible_par_le_parent(lake_root: Path) -> None:
    """La citation du parent est une provenance : gold l'accepte."""
    write_table(PRICES, "prices", Layer.SILVER)
    enfant = promote("prices", Layer.SILVER, Layer.GOLD, notes="panneau consommable")
    payload = json.loads(enfant.manifest_path.read_text("utf-8"))
    assert payload["parent"]["layer"] == "silver"
    assert payload["source"] is None
    assert enfant.n_rows == 5  # aucune transformation, cinq lignes de PRICES


def test_promotion_a_rebours_est_refusee(lake_root: Path) -> None:
    write_table(PRICES, "prices", Layer.GOLD, manifest=SOURCE_MANIFEST)
    with pytest.raises(ProvenanceError, match="promotion refusée"):
        promote("prices", Layer.GOLD, Layer.BRONZE)
    with pytest.raises(ProvenanceError, match="promotion refusée"):
        promote("prices", Layer.GOLD, Layer.GOLD)


def test_promotion_dun_jeu_absent_leve(lake_root: Path) -> None:
    with pytest.raises(FileNotFoundError):
        promote("inconnu", Layer.BRONZE, Layer.SILVER)


def test_promotion_sous_un_autre_identifiant(lake_root: Path) -> None:
    write_table(PRICES, "prices", Layer.BRONZE)
    promote("prices", Layer.BRONZE, Layer.SILVER, to_dataset_id="prices_propres")
    assert table_exists("prices_propres", Layer.SILVER)
    assert not table_exists("prices", Layer.SILVER)


# --------------------------------------------------------------------------- #
# Propriétés
# --------------------------------------------------------------------------- #


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(valeurs=st.lists(st.floats(allow_nan=False, allow_infinity=False, width=64), min_size=0, max_size=60))
def test_propriete_aller_retour_conserve_les_valeurs(lake_root: Path, valeurs: list[float]) -> None:
    """Source (b) : identité. Lire ce qu'on vient d'écrire rend la même suite.

    Parquet stocke le double IEEE 754 sans perte, donc l'égalité est exacte et
    non approchée. La propriété tient pour toute longueur, la liste vide comprise.
    """
    frame = pl.DataFrame({"i": list(range(len(valeurs))), "x": pl.Series(valeurs, dtype=pl.Float64)})
    write_table(frame, "prop_roundtrip", Layer.BRONZE, overwrite=True)
    back = read_table("prop_roundtrip", Layer.BRONZE)
    assert isinstance(back, pl.DataFrame)
    assert back.sort("i")["x"].to_list() == valeurs


@settings(max_examples=40, deadline=None)
@given(
    permutation=st.permutations(range(6)),
    valeurs=st.lists(st.floats(allow_nan=False, allow_infinity=False, width=64), min_size=6, max_size=6),
)
def test_propriete_to_analytics_ne_depend_pas_de_lordre_des_lignes(
    permutation: list[int], valeurs: list[float]
) -> None:
    """Source (b) : invariance par permutation. Le tri rend l'ordre chronologique.

    Six dates ouvrables distinctes de janvier 2020, mélangées de toutes les
    façons possibles, doivent rendre le même panneau.
    """
    dates = [
        "2020-01-02",
        "2020-01-03",
        "2020-01-06",
        "2020-01-07",
        "2020-01-08",
        "2020-01-09",
    ]
    direct = to_analytics(pl.DataFrame({"date": dates, "r": valeurs}))
    melange = to_analytics(
        pl.DataFrame({"date": [dates[i] for i in permutation], "r": [valeurs[i] for i in permutation]})
    )
    assert list(melange.index) == list(direct.index)
    assert melange["r"].tolist() == direct["r"].tolist()

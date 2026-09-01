"""La provenance : quelle donnée exacte a produit ce résultat ?

**Le problème.** Un backtest se défend par ses données autant que par son code.
Le code vit dans git, qui répond à la question « quelle version a tourné ». Les
données, elles, ne vivent pas dans git : elles sont téléchargées, puis
retéléchargées, et la seconde réponse du serveur n'est pas la première. Sans
trace écrite, la question « quelle donnée exacte a produit ce ratio de
Sharpe ? » reste sans réponse, et le résultat n'est plus reproductible même
avec un dépôt propre.

**Le remède.** Chaque jeu de données porte un manifeste, un objet validé qui dit
d'où il vient, quand il a été pris, ce qu'il couvre, sous quelle licence, et
quelle est son empreinte cryptographique. Le manifeste se sérialise en JSON à
côté du jeu, dans ``metadata/manifests/``, et il se relit sans ouvrir la donnée.

**Pourquoi un jeu sans manifeste ne se charge pas en gold.** La couche *gold*
alimente directement les facteurs, les backtests et les rapports publiés. Un
chiffre publié doit pouvoir être rattaché à son intrant, sinon la publication
engage une réputation sur une donnée que personne ne sait retrouver. La règle
est donc binaire : pas de manifeste complet, pas de promotion en gold, et
:class:`ProvenanceError` plutôt qu'un avertissement dans un journal que
personne ne lit. Un avertissement se contourne par habitude, une exception non.

**Pourquoi l'horodatage de téléchargement compte autant que la période
couverte.** Deux requêtes identiques à Yahoo Finance, séparées de six mois,
rendent des séries différentes sur la même période. Le prix ajusté est recalculé
à chaque dividende et à chaque division. Le prix ajusté du 2 janvier 2015 lu en
janvier 2020 n'est donc pas celui lu en janvier 2026. Un titre qui verse quatre
fois par an accumule vingt-quatre versements en six ans, chiffre modélisé sur
un rythme trimestriel constant. Une série se désigne donc par un
couple, la période couverte et la date de la prise, jamais par la période seule.
Le même mécanisme joue sur les révisions macroéconomiques : le PIB d'un
trimestre est révisé pendant des années, et un backtest qui utilise la valeur
d'aujourd'hui pour une décision d'hier lit l'avenir.

**Trois valeurs plutôt que deux.** ``survivorship_free`` vaut ``True``, ``False``
ou ``None``, et ``None`` signifie « non vérifié ». Un booléen à deux valeurs
force à choisir entre deux mensonges quand la vérité est qu'on ne sait pas, et
le choix se fait toujours du côté flatteur. Le troisième état supprime la
tentation.

**Le vocabulaire du module.**

``dataset_id``
    L'identifiant unique et stable d'un jeu, par exemple
    ``« yahoo_spx_daily_2026-09-01 »``. Il ne se réutilise jamais pour un autre
    contenu : un nouveau téléchargement donne un nouvel identifiant.

``lignée``
    La chaîne des jeux dont un jeu descend, du brut au gold. Elle se reconstruit
    par :func:`lineage` à partir du champ ``parent_datasets``.

``empreinte``
    Le condensé SHA-256 du contenu. Il répond à « le fichier a-t-il bougé ? »
    sans comparer les fichiers, et il tient dans une ligne de rapport.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pydantic import Field, field_validator, model_validator

from quantlab.core.config import StrictModel
from quantlab.core.errors import DataQualityError, QuantLabError
from quantlab.core.logging import get_logger
from quantlab.core.paths import Layer, ensure, metadata_dir
from quantlab.core.types import Frequency

__all__ = [
    "DEFAULT_CHUNK_SIZE",
    "FRAME_DIGEST_VERSION",
    "GOLD_REQUIRED_TEXT_FIELDS",
    "NULL_TOKEN",
    "DatasetManifest",
    "ProvenanceError",
    "find_manifest",
    "lineage",
    "manifest_path_for",
    "manifests_root",
    "read_manifest",
    "require_gold_ready",
    "require_manifest",
    "sha256_file",
    "sha256_frame",
    "write_manifest",
]

_log = get_logger(__name__)

#: Étiquette de version du format d'empreinte de tableau. Elle entre dans le
#: hachage : changer la façon de sérialiser change l'étiquette, donc change
#: toutes les empreintes, ce qui évite de comparer deux formats sans le voir.
FRAME_DIGEST_VERSION = "quantlab/sha256_frame/v1"

#: Le jeton qui remplace toute valeur manquante dans l'empreinte d'un tableau.
#: Il commence par un octet nul, qu'aucun texte lisible ne contient.
NULL_TOKEN = "\x00null"

#: Taille des blocs lus par :func:`sha256_file`, en octets. Un mébioctet tient
#: en mémoire sur toute machine et évite un appel système par kilooctet.
DEFAULT_CHUNK_SIZE = 1 << 20

#: Les champs textuels qu'un manifeste doit renseigner avant toute promotion en
#: gold. La liste est explicite plutôt que déduite, pour qu'un ajout de champ
#: facultatif ne durcisse pas la règle par accident.
GOLD_REQUIRED_TEXT_FIELDS: tuple[str, ...] = (
    "source",
    "provider",
    "url",
    "timezone",
    "currency",
    "corporate_actions",
    "revision_policy",
    "license",
    "checksum_sha256",
    "processing_version",
)


class ProvenanceError(QuantLabError):
    """La provenance d'un jeu est absente, incomplète ou incohérente.

    Levée dans trois situations. Un manifeste attendu n'existe pas sur le
    disque. Un manifeste existe mais ne renseigne pas les champs exigés pour la
    couche gold. Une lignée ne se referme pas, soit qu'un parent déclaré soit
    introuvable, soit que la chaîne des parents forme un cycle.
    """


class DatasetManifest(StrictModel):
    """La carte d'identité d'un jeu de données, validée et sérialisable.

    Le manifeste répond à une seule question, et il y répond entièrement :
    quelle donnée exacte a produit ce résultat ? Il porte donc l'origine, la
    date de prise, la couverture, les conventions de traitement, la licence et
    l'empreinte, plus les identifiants des jeux dont il descend.

    Attributes:
        dataset_id: identifiant unique et stable, jamais réutilisé.
        source: l'origine humaine, par exemple « Yahoo Finance, API v8 ».
        provider: le module qui a fait la requête, par exemple
            ``« quantlab.data.providers.yahoo »``.
        url: l'adresse exacte interrogée, paramètres compris quand ils tiennent.
        download_timestamp: l'instant de la prise, avec fuseau, normalisé en UTC.
        data_start: premier jour couvert par la donnée.
        data_end: dernier jour couvert par la donnée.
        frequency: la fréquence d'observation, voir :class:`Frequency`.
        timezone: le fuseau IANA des horodatages, par exemple
            ``« America/New_York »``. Une série intrajournalière sans fuseau
            déclaré est inutilisable.
        exchange: le code de marché quand il existe, ``None`` pour une série
            macroéconomique qui n'en a pas.
        currency: la devise ISO 4217 des montants, trois majuscules.
        adjusted: les prix sont-ils ajustés des actions de société.
        point_in_time: le jeu sait-il ce qu'il était à une date passée.
        survivorship_free: ``True``, ``False`` ou ``None`` pour « non vérifié ».
        corporate_actions: le traitement des actions de société, en clair.
        revision_policy: ce que la source fait de ses révisions, en clair.
        license: la licence d'usage, citée telle qu'elle est publiée.
        license_url: l'adresse du texte de licence.
        checksum_sha256: l'empreinte du contenu, 64 caractères hexadécimaux.
        n_rows: le nombre de lignes.
        n_columns: le nombre de colonnes.
        columns: les noms de colonnes, dans l'ordre du fichier.
        processing_version: la version du code qui a produit le jeu.
        layer: l'étage du lac, voir :class:`Layer`.
        parent_datasets: les identifiants des jeux dont celui-ci descend.
        notes: tout ce qui ne rentre dans aucun champ, en français.
        manifest_version: la version du format de manifeste lui-même.

    Raises:
        ValueError: si un champ viole une règle de cohérence. Quatre cas : un
            horodatage sans fuseau, une devise de quatre lettres, une période
            qui se termine avant de commencer, un jeu déclaré son propre parent.
            Pydantic enveloppe ces erreurs dans une ``ValidationError``.

    Example:
        >>> m = DatasetManifest(
        ...     dataset_id="demo",
        ...     source="Test",
        ...     provider="quantlab.tests",
        ...     url="https://example.org/demo.csv",
        ...     download_timestamp=datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
        ...     data_start=date(2020, 1, 1),
        ...     data_end=date(2020, 12, 31),
        ...     frequency=Frequency.DAILY,
        ...     timezone="UTC",
        ...     currency="CAD",
        ...     adjusted=False,
        ...     point_in_time=False,
        ...     corporate_actions="aucune",
        ...     revision_policy="aucune révision",
        ...     license="CC BY 4.0",
        ...     n_rows=3,
        ...     n_columns=1,
        ...     columns=("close",),
        ...     processing_version="1.0.0",
        ...     layer=Layer.RAW,
        ... )
        >>> m.survivorship_free is None
        True

    Note:
        Le modèle hérite de :class:`quantlab.core.config.StrictModel`, donc il
        est gelé et refuse toute clé inconnue. Une faute de frappe dans un nom
        de champ lève à la construction plutôt que de créer un attribut fantôme.
    """

    dataset_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    url: str = ""
    download_timestamp: datetime
    data_start: date
    data_end: date
    frequency: Frequency
    timezone: str = ""
    exchange: str | None = None
    currency: str = ""
    adjusted: bool
    point_in_time: bool
    survivorship_free: bool | None = None
    corporate_actions: str = ""
    revision_policy: str = ""
    license: str = ""
    license_url: str | None = None
    checksum_sha256: str = ""
    n_rows: int = Field(default=0, ge=0)
    n_columns: int = Field(default=0, ge=0)
    columns: tuple[str, ...] = ()
    processing_version: str = ""
    layer: Layer
    parent_datasets: tuple[str, ...] = ()
    notes: str = ""
    manifest_version: str = "1"

    @field_validator("download_timestamp")
    @classmethod
    def _horodatage_conscient_du_fuseau(cls, value: datetime) -> datetime:
        """Refuse un horodatage naïf et normalise tout le reste en UTC."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "download_timestamp doit porter un fuseau : un horodatage naïf "
                "ne désigne aucun instant, il désigne une heure locale inconnue"
            )
        return value.astimezone(UTC)

    @field_validator("currency")
    @classmethod
    def _devise_iso_4217(cls, value: str) -> str:
        """Impose trois majuscules, ou la chaîne vide pour un jeu sans montant."""
        if value and (len(value) != 3 or not value.isalpha() or not value.isupper()):
            raise ValueError(f"currency doit être un code ISO 4217 de trois majuscules, reçu « {value} »")
        return value

    @field_validator("checksum_sha256")
    @classmethod
    def _empreinte_hexadecimale(cls, value: str) -> str:
        """Impose 64 caractères hexadécimaux minuscules, ou rien du tout."""
        if not value:
            return value
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("checksum_sha256 doit valoir 64 caractères hexadécimaux minuscules")
        return value

    @model_validator(mode="after")
    def _coherence_interne(self) -> DatasetManifest:
        """Vérifie l'ordre des dates, le compte des colonnes et la lignée."""
        if self.data_end < self.data_start:
            raise ValueError(f"data_end ({self.data_end}) précède data_start ({self.data_start})")
        if self.columns and self.n_columns != len(self.columns):
            raise ValueError(f"n_columns vaut {self.n_columns} pour {len(self.columns)} noms de colonnes")
        if self.dataset_id in self.parent_datasets:
            raise ValueError(f"« {self.dataset_id} » ne peut pas être son propre parent")
        if len(set(self.parent_datasets)) != len(self.parent_datasets):
            raise ValueError("parent_datasets contient un doublon")
        return self

    def missing_for_gold(self) -> tuple[str, ...]:
        """Rend les champs qui manquent pour une promotion en gold.

        Returns:
            Les noms de champs insuffisamment renseignés, dans l'ordre du
            contrôle. Un tuple vide signifie que le manifeste est complet.

        Note:
            ``survivorship_free`` n'est pas exigé. Le champ a trois valeurs
            justement pour que ``None`` reste disponible, et forcer une réponse
            reviendrait à fabriquer la réponse flatteuse.
        """
        manquants = [nom for nom in GOLD_REQUIRED_TEXT_FIELDS if not str(getattr(self, nom)).strip()]
        if self.n_rows <= 0:
            manquants.append("n_rows")
        if not self.columns:
            manquants.append("columns")
        if not self.parent_datasets:
            manquants.append("parent_datasets")
        return tuple(manquants)


def _feed(hasher: Any, text: str) -> None:
    """Verse un morceau de texte dans le condenseur, précédé de sa longueur.

    Le préfixe de longueur sur huit octets gros-boutiens rend l'encodage sans
    ambiguïté : deux découpages différents ne peuvent pas produire la même suite
    d'octets. Un simple séparateur ne suffirait pas, une valeur qui le contient
    l'imitant.
    """
    raw = text.encode("utf-8")
    hasher.update(len(raw).to_bytes(8, "big"))
    hasher.update(raw)


def _canonical_scalar(value: object) -> str:
    """Rend l'écriture canonique d'une valeur, pour le hachage d'un tableau.

    Les règles, dans l'ordre où elles s'appliquent :

    - toute valeur manquante, ``None``, ``NaN`` ou ``pandas.NA``, devient
      :data:`NULL_TOKEN`. Les trois se confondent donc volontairement ;
    - un booléen devient ``« true »`` ou ``« false »``, avant le test d'entier,
      parce qu'en Python ``bool`` hérite de ``int`` ;
    - un flottant devient son ``repr``, l'écriture décimale la plus courte qui
      relit exactement le même nombre ; les infinis deviennent ``« inf »`` et
      ``« -inf »`` ;
    - un entier devient son écriture décimale ;
    - un horodatage devient son ISO 8601, fuseau compris ;
    - des octets deviennent leur hexadécimal ;
    - un tuple, cas d'un index à plusieurs niveaux, devient la concaténation
      canonique de ses éléments ;
    - tout le reste devient ``str(value)``.
    """
    if value is None:
        return NULL_TOKEN
    if isinstance(value, tuple):
        return "(" + "\x1f".join(_canonical_scalar(part) for part in value) + ")"
    try:
        if bool(pd.isna(value)):
            return NULL_TOKEN
    except (TypeError, ValueError):
        pass
    if isinstance(value, (bool, np.bool_)):
        return "true" if bool(value) else "false"
    if isinstance(value, (float, np.floating)):
        f = float(value)
        if math.isinf(f):
            return "inf" if f > 0 else "-inf"
        return repr(f)
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).hex()
    return str(value)


def sha256_file(path: str | Path, *, chunk_size: int = DEFAULT_CHUNK_SIZE) -> str:
    """Rend le condensé SHA-256 d'un fichier, en hexadécimal minuscule.

    **Le problème.** Un fichier téléchargé deux fois se compare mal : il pèse
    des mégaoctets, il ne rentre pas dans un rapport, et l'ouvrir pour comparer
    coûte autant que le retélécharger.

    **L'intuition.** Une fonction de hachage réduit un contenu de taille
    quelconque à 32 octets, de telle façon qu'un octet changé change le résultat
    de fond en comble. L'égalité des condensés vaut donc preuve pratique
    d'égalité des contenus.

    .. math::

        h = \\mathrm{SHA256}(b_1 \\Vert b_2 \\Vert \\dots \\Vert b_n)

    où :math:`b_i` est le i-ème bloc d'octets du fichier et :math:`\\Vert` la
    concaténation. Le découpage en blocs ne change pas le résultat, la fonction
    de compression traitant un flux.

    Args:
        path: le chemin du fichier à condenser.
        chunk_size: la taille des blocs lus, en octets. Sans effet sur le
            résultat, seulement sur la mémoire occupée.

    Returns:
        Les 64 caractères hexadécimaux minuscules du condensé.

    Raises:
        ProvenanceError: si le chemin n'existe pas ou n'est pas un fichier.

    Example:
        >>> import tempfile, pathlib
        >>> d = pathlib.Path(tempfile.mkdtemp())
        >>> _ = (d / "a.txt").write_bytes(b"abc")
        >>> sha256_file(d / "a.txt")
        'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'

    Note:
        **Hypothèses.** Résistance aux collisions de SHA-256, aucune collision
        n'étant publiée à ce jour. **Provenance.** SHA-256 est normalisé par le
        NIST, FIPS 180-4 (2015). **Limites.** Le condensé prouve l'identité du
        contenu, jamais son exactitude : deux téléchargements erronés
        identiques ont le même condensé. **Alternatives.** MD5 et SHA-1 sont
        plus rapides et cassés ; BLAKE3 est plus rapide et sûr, mais hors de la
        bibliothèque standard. **Pourquoi celle-ci.** Elle est standard,
        disponible partout, et son coût est négligeable devant celui du
        téléchargement. **Vérification.** Les vecteurs publiés de FIPS 180-4
        sont rejoués dans les tests, dont ``SHA256("abc")`` ci-dessus.
    """
    p = Path(path)
    if not p.is_file():
        raise ProvenanceError(f"fichier introuvable pour empreinte : {p}")
    hasher = hashlib.sha256()
    with p.open("rb") as handle:
        while True:
            block = handle.read(chunk_size)
            if not block:
                break
            hasher.update(block)
    return hasher.hexdigest()


def sha256_frame(df: pd.DataFrame, *, include_index: bool = True) -> str:
    """Rend une empreinte SHA-256 reproductible d'un tableau pandas.

    **Le problème.** Le condensé d'un fichier Parquet ne dit rien du contenu.
    Deux écritures du même tableau donnent deux fichiers différents, parce que
    la compression, l'ordre des groupes de lignes et les métadonnées de version
    bougent. Comparer deux jeux exige donc une empreinte du contenu logique, pas
    de son emballage.

    **L'intuition.** On fabrique une écriture canonique du tableau, une suite
    d'octets qui ne dépend que des valeurs, et on condense cette suite. Deux
    tableaux logiquement identiques donnent la même suite, donc la même
    empreinte, quel que soit le format de stockage.

    .. math::

        H(D) = \\mathrm{SHA256}\\Big( \\mathcal{C}(v) \\Vert
        \\mathcal{C}(n) \\Vert \\mathcal{C}(I) \\Vert
        \\big\\Vert_{c \\in \\sigma(C)} \\mathcal{C}(c) \\Big)

    où :math:`v` est :data:`FRAME_DIGEST_VERSION`, :math:`n` le couple du
    nombre de lignes et de colonnes, et :math:`I` l'index. :math:`C` est
    l'ensemble des colonnes, :math:`\\sigma(C)` ces colonnes triées par leur
    nom, et :math:`\\mathcal{C}` l'encodage canonique décrit ci-dessous.

    **Ce qui entre exactement dans le hachage**, dans cet ordre, chaque morceau
    étant précédé de sa longueur en octets sur huit octets gros-boutiens :

    1. la chaîne :data:`FRAME_DIGEST_VERSION` ;
    2. ``« nrows=… »``, le nombre de lignes ;
    3. ``« ncols=… »``, le nombre de colonnes ;
    4. ``« index=yes »`` ou ``« index=no »`` selon ``include_index`` ;
    5. si l'index entre, ``« index-name=… »`` puis chaque valeur d'index
       encodée par :func:`_canonical_scalar`, dans l'ordre des lignes ;
    6. pour chaque colonne, prise dans l'ordre alphabétique de son nom,
       ``« column=… »`` puis chaque valeur encodée, dans l'ordre des lignes.

    **Ce qui n'entre pas.** L'ordre des colonnes, volontairement : deux tableaux
    aux mêmes colonnes rangées autrement ont la même empreinte. Le type de
    stockage, lui aussi : un entier en ``int32`` et le même en ``int64``
    s'écrivent tous deux ``« 7 »``, donc se confondent. C'est un choix, motivé
    par la stabilité entre versions de pandas, dont les noms de types changent.
    N'entrent pas non plus le nom de l'index, ni les noms de niveaux d'un index
    à plusieurs étages : deux tableaux qui ne diffèrent que par ces étiquettes
    ont la même empreinte.

    **Le point aveugle, mesuré et déclaré.** L'indifférence au type va plus loin
    qu'un changement de largeur d'entier. Une colonne d'entiers ``1, 2, 3`` et
    la même colonne relue en texte ``« 1 », « 2 », « 3 »`` rendent la MÊME
    empreinte, puisque les deux s'écrivent pareil. Un fichier dont la colonne
    numérique se charge silencieusement en texte passe donc le contrôle
    d'empreinte. Le condensé répond à « le contenu a-t-il bougé ? », jamais à
    « le typage est-il celui que j'attends ? », et c'est au contrôle de schéma
    de répondre à la seconde question. En revanche un booléen ne se confond
    avec rien : ``True`` s'écrit ``« true »`` et l'entier ``1`` s'écrit
    ``« 1 »``. De même ``7`` et ``7.0`` diffèrent. L'ordre des lignes entre
    pleinement : une série temporelle renversée n'est pas la même donnée.

    Args:
        df: le tableau à condenser.
        include_index: l'index entre-t-il dans l'empreinte. Le laisser à
            ``True`` pour toute série temporelle, où l'index porte les dates.

    Returns:
        Les 64 caractères hexadécimaux minuscules du condensé.

    Raises:
        DataQualityError: si deux colonnes portent le même nom. Le tableau
            serait ambigu, et l'empreinte dépendrait alors d'un ordre que la
            fonction refuse justement de regarder.

    Example:
        >>> a = pd.DataFrame({"x": [1.0, 2.0], "y": [3.0, 4.0]})
        >>> sha256_frame(a) == sha256_frame(a[["y", "x"]])
        True
        >>> sha256_frame(a) == sha256_frame(a.iloc[::-1])
        False

    Note:
        **Hypothèses.** Le tableau tient en mémoire, et ses valeurs ont une
        écriture canonique stable ; c'est le cas des nombres, des textes, des
        booléens et des horodatages. **Provenance.** Le procédé est celui du
        hachage de Merkle appliqué à plat, avec le préfixe de longueur
        recommandé pour éviter les ambiguïtés de concaténation. **Limites.**
        Le coût est linéaire en nombre de cellules et passe par Python pour
        chaque valeur, donc c'est une opération de métadonnées, pas une boucle
        de calcul. Les valeurs manquantes se confondent : ``None``, ``NaN`` et
        ``pandas.NA`` rendent le même jeton. **Alternatives.**
        ``pandas.util.hash_pandas_object`` est plus rapide, mais son résultat
        dépend des types et n'est pas garanti stable entre versions ; écrire un
        Parquet et le condenser dépend de la compression. **Pourquoi
        celle-ci.** L'empreinte doit survivre à une montée de version de pandas
        et à un changement de format de stockage, sinon elle ne prouve rien à
        six mois. **Vérification.** Deux tests reconstruisent à la main la
        suite d'octets documentée, l'un sur un index entier, l'autre sur un
        index de dates avec une colonne booléenne et une valeur manquante, puis
        comparent au condensé rendu.
    """
    noms = [str(c) for c in df.columns]
    if len(set(noms)) != len(noms):
        raise DataQualityError("le tableau porte des colonnes de même nom, empreinte impossible")

    hasher = hashlib.sha256()
    _feed(hasher, FRAME_DIGEST_VERSION)
    _feed(hasher, f"nrows={len(df)}")
    _feed(hasher, f"ncols={len(df.columns)}")
    _feed(hasher, "index=yes" if include_index else "index=no")
    if include_index:
        _feed(hasher, f"index-name={'' if df.index.name is None else df.index.name}")
        for valeur in df.index:
            _feed(hasher, _canonical_scalar(valeur))
    for colonne in sorted(df.columns, key=str):
        _feed(hasher, f"column={colonne}")
        for valeur in df[colonne]:
            _feed(hasher, _canonical_scalar(valeur))
    return hasher.hexdigest()


def manifests_root(manifests_dir: str | Path | None = None) -> Path:
    """Rend la racine des manifestes, ``metadata/manifests`` par défaut.

    Args:
        manifests_dir: une racine de remplacement, utile pour un test qui
            travaille dans un ``tmp_path``. ``None`` prend celle du dépôt.
    """
    return Path(manifests_dir) if manifests_dir is not None else metadata_dir("manifests")


def manifest_path_for(
    dataset_id: str,
    layer: Layer | str,
    *,
    manifests_dir: str | Path | None = None,
) -> Path:
    """Rend le chemin du manifeste d'un jeu, sous ``metadata/manifests/``.

    Le chemin est ``metadata/manifests/<couche>/<dataset_id>.json``. Ranger par
    couche fait apparaître d'un ``ls`` ce qui a été promu et ce qui ne l'a pas
    été.

    Args:
        dataset_id: l'identifiant du jeu.
        layer: l'étage du lac, valeur de :class:`Layer` ou son texte.
        manifests_dir: racine de remplacement, voir :func:`manifests_root`.

    Returns:
        Le chemin, que le fichier existe ou non.

    Raises:
        ProvenanceError: si l'identifiant est vide ou contient un séparateur de
            chemin, ce qui écrirait le manifeste hors de son répertoire.
    """
    if not dataset_id or not dataset_id.strip():
        raise ProvenanceError("dataset_id vide : un jeu sans nom ne se retrouve pas")
    if "/" in dataset_id or "\\" in dataset_id or dataset_id in {".", ".."}:
        raise ProvenanceError(f"dataset_id « {dataset_id} » ne peut pas contenir de séparateur de chemin")
    return manifests_root(manifests_dir) / Layer(layer).value / f"{dataset_id}.json"


def require_gold_ready(manifest: DatasetManifest) -> None:
    """Lève si le manifeste ne suffit pas à publier en gold.

    Args:
        manifest: le manifeste à contrôler.

    Raises:
        ProvenanceError: si un champ exigé manque, la liste des manquants étant
            citée dans le message.

    Note:
        Le contrôle ne s'applique qu'aux jeux dont la couche est
        :attr:`Layer.GOLD`. Un manifeste de couche brute a le droit d'être
        incomplet : la donnée brute est parfois livrée sans licence écrite, et
        c'est le passage en silver qui oblige à trancher.
    """
    if manifest.layer is not Layer.GOLD:
        return
    manquants = manifest.missing_for_gold()
    if manquants:
        raise ProvenanceError(
            f"le manifeste « {manifest.dataset_id} » ne peut pas passer en gold, "
            f"champs manquants : {', '.join(manquants)}"
        )


def write_manifest(manifest: DatasetManifest, path: str | Path) -> Path:
    """Écrit le manifeste en JSON et rend le chemin écrit.

    Args:
        manifest: le manifeste à sérialiser.
        path: le fichier de destination. Ses répertoires parents sont créés.

    Returns:
        Le chemin du fichier écrit.

    Raises:
        ProvenanceError: si la couche est gold et qu'un champ exigé manque.

    Note:
        Le JSON est indenté à deux espaces, sans échappement des accents, avec
        les clés dans l'ordre déclaré du modèle. Deux écritures du même
        manifeste donnent donc deux fichiers identiques octet pour octet, ce qui
        rend le fichier comparable par ``git diff``.
    """
    require_gold_ready(manifest)
    destination = Path(path)
    ensure(destination.parent)
    charge = json.loads(manifest.model_dump_json())
    destination.write_text(json.dumps(charge, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _log.info(
        "manifeste écrit",
        extra={"dataset_id": manifest.dataset_id, "layer": manifest.layer.value, "path": str(destination)},
    )
    return destination


def read_manifest(path: str | Path) -> DatasetManifest:
    """Relit un manifeste JSON et le valide.

    Args:
        path: le fichier à lire.

    Returns:
        Le manifeste validé.

    Raises:
        ProvenanceError: si le fichier manque, s'il n'est pas du JSON, ou si son
            contenu ne valide pas contre :class:`DatasetManifest`.
    """
    p = Path(path)
    if not p.is_file():
        raise ProvenanceError(f"manifeste introuvable : {p}")
    try:
        return DatasetManifest.model_validate_json(p.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ProvenanceError(f"manifeste illisible ou invalide dans {p} :\n{exc}") from exc


def find_manifest(dataset_id: str, *, manifests_dir: str | Path | None = None) -> DatasetManifest:
    """Retrouve un manifeste par son seul identifiant, toutes couches confondues.

    L'identifiant est comparé caractère pour caractère au nom du fichier, dans
    chacune des quatre couches. Ce n'est pas un motif : ``« demo_ra? »`` ne
    trouve pas ``« demo_raw »``, il ne trouve rien.

    Args:
        dataset_id: l'identifiant cherché.
        manifests_dir: racine de remplacement, voir :func:`manifests_root`.

    Returns:
        Le manifeste trouvé.

    Raises:
        ProvenanceError: si aucun fichier ne porte cet identifiant, ou si
            plusieurs couches en portent un. Le second cas signale un
            identifiant réutilisé, ce que la convention interdit.

    Note:
        La recherche énumère les couches plutôt que d'interroger le disque par
        motif. Une recherche par motif rendrait le manifeste d'un AUTRE jeu dès
        que l'identifiant contient une étoile ou un point d'interrogation, et
        elle le rendrait en silence.
    """
    racine = manifests_root(manifests_dir)
    trouves = [
        chemin
        for chemin in (manifest_path_for(dataset_id, couche, manifests_dir=manifests_dir) for couche in Layer)
        if chemin.is_file()
    ]
    if not trouves:
        raise ProvenanceError(f"aucun manifeste pour « {dataset_id} » sous {racine}")
    if len(trouves) > 1:
        chemins = ", ".join(str(t) for t in trouves)
        raise ProvenanceError(f"« {dataset_id} » porté par plusieurs manifestes : {chemins}")
    return read_manifest(trouves[0])


def require_manifest(
    dataset_id: str,
    layer: Layer | str,
    *,
    manifests_dir: str | Path | None = None,
) -> DatasetManifest:
    """Rend le manifeste d'un jeu, et lève s'il manque ou s'il est incomplet.

    C'est la porte d'entrée du chargement en gold. Un jeu qui n'a pas de
    manifeste complet ne se charge pas, et l'appelant n'a pas à s'en souvenir :
    c'est cette fonction qui refuse.

    Args:
        dataset_id: l'identifiant du jeu.
        layer: la couche où le manifeste est attendu.
        manifests_dir: racine de remplacement, voir :func:`manifests_root`.

    Returns:
        Le manifeste validé, complet pour sa couche.

    Raises:
        ProvenanceError: si le fichier manque, s'il est illisible, ou s'il est
            incomplet alors que la couche est gold.
    """
    manifest = read_manifest(manifest_path_for(dataset_id, layer, manifests_dir=manifests_dir))
    require_gold_ready(manifest)
    return manifest


def lineage(dataset_id: str, *, manifests_dir: str | Path | None = None) -> list[DatasetManifest]:
    """Remonte la chaîne des parents et rend la lignée ordonnée.

    L'ordre va de l'ancêtre le plus lointain au jeu demandé, qui ferme la liste.
    Lue de haut en bas, la liste raconte donc la fabrication : le téléchargement
    brut d'abord, la donnée nettoyée ensuite, le jeu publié en dernier.

    Args:
        dataset_id: l'identifiant du jeu dont on veut la lignée.
        manifests_dir: racine de remplacement, voir :func:`manifests_root`.

    Returns:
        Les manifestes, ancêtres d'abord, le jeu demandé en dernier. Un jeu sans
        parent rend une liste d'un seul élément.

    Raises:
        ProvenanceError: si un manifeste de la chaîne est introuvable, ou si les
            parents forment un cycle.

    Example:
        Pour un gold ``« g »`` dont le parent est ``« s »``, lui-même issu de
        ``« r »``, la fonction rend ``[r, s, g]``.

    Note:
        Le parcours est en profondeur, post-ordre, avec mémorisation. Un jeu
        cité par deux descendants n'apparaît donc qu'une fois, à la première
        position où il est complet. Le cycle est détecté par la pile des
        identifiants en cours de visite, et non par un compteur d'itérations.
    """
    vus: dict[str, DatasetManifest] = {}
    ordre: list[DatasetManifest] = []
    en_cours: list[str] = []

    def visiter(identifiant: str) -> None:
        """Ajoute le jeu et ses ancêtres à la lignée, les ancêtres d'abord.

        Le jeu déjà vu ne se revisite pas. Le jeu présent dans la pile des
        visites en cours ferme un cycle, et lève.
        """
        if identifiant in vus:
            return
        if identifiant in en_cours:
            chaine = " -> ".join([*en_cours, identifiant])
            raise ProvenanceError(f"cycle dans la lignée : {chaine}")
        en_cours.append(identifiant)
        manifest = find_manifest(identifiant, manifests_dir=manifests_dir)
        for parent in manifest.parent_datasets:
            visiter(parent)
        en_cours.pop()
        vus[identifiant] = manifest
        ordre.append(manifest)

    visiter(dataset_id)
    return ordre

"""Le lac de données : écrire, lire, interroger, et refuser ce qui n'a pas de provenance.

**Le problème.** Un fichier CSV posé sur un disque ne dit ni d'où il vient, ni
quand il est arrivé, ni ce qu'on lui a fait. Six mois plus tard, deux fichiers
portent le même nom, aucun ne porte la même valeur, et le résultat publié n'est
plus reproductible même si le code n'a pas bougé d'une ligne.

**Le remède.** Un lac à quatre étages, où chaque étage a une règle qui ne se
négocie pas, et où l'accès passe par des fonctions qui refusent d'écrire une
donnée sans provenance.

Les quatre étages, et ce qui a le droit d'y arriver
---------------------------------------------------

``raw`` (immuable)
    La réponse de la source, octet pour octet, avec sa date de téléchargement.
    Exemple de ce qui a le droit d'y arriver : le CSV que Yahoo a rendu le
    2026-09-01 à 14h02 pour le ticker ``SPY``, y compris ses colonnes mal
    nommées et ses lignes vides. Rien n'y est corrigé, jamais. Une correction
    dans ``raw`` détruit la seule preuve de ce que la source répondait ce
    jour-là, et le laboratoire perd la capacité de distinguer une erreur de la
    source d'une erreur de son propre code. :func:`write_table` refuse donc
    d'écraser un jeu ``raw`` existant.

``bronze`` (technique)
    Le même contenu, lisible. Parsage des dates, typage des colonnes,
    renommage. Exemple : la colonne ``Adj Close`` devient ``adj_close`` en
    ``Float64``, et la colonne ``Date`` devient une vraie date. Aucune décision
    financière n'est prise ici. Un prix aberrant reste aberrant à cet étage.

``silver`` (propre)
    La donnée sur laquelle on accepte de raisonner. Calendrier d'échange
    respecté, doublons retirés, divisions et dividendes traités, devise
    déclarée. Exemple : la séance du 2018-12-05, fermée pour les funérailles de
    George H. W. Bush, disparaît du calendrier au lieu de porter un rendement
    nul. C'est ici que vivent les décisions méthodologiques, et chacune laisse
    une trace dans le manifeste.

``gold`` (consommable)
    Les jeux qu'un facteur, un modèle, un backtest ou un optimiseur lisent
    directement. Exemple : un panneau de rendements quotidiens, dates en
    lignes, actifs en colonnes, sans trou et sans doublon. Un jeu ``gold``
    porte son manifeste : sans lui, :func:`write_table` lève
    :class:`ProvenanceError` et rien n'est écrit.

La frontière des bibliothèques
------------------------------

Le lac parle Parquet, Polars et DuckDB ; l'analytique parle pandas indexé par
le temps. La conversion se fait une seule fois, par :func:`to_analytics`, à la
sortie du ``gold``. Aucun calcul ne fait l'aller-retour, parce que chaque
conversion coûte une copie et une occasion de perdre le fuseau horaire.

Exemple d'emploi :

.. code-block:: python

    receipt = write_table(prices, "yahoo_prices", Layer.BRONZE)
    df = read_table("yahoo_prices", Layer.BRONZE, columns=["date", "adj_close"])
    panel = to_analytics(df, index_col="date")
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import shutil
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import duckdb
import pandas as pd
import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq

from quantlab.core.errors import DataQualityError, QuantLabError
from quantlab.core.logging import get_logger
from quantlab.core.paths import Layer, data_dir, ensure

__all__ = [
    "LAYER_ORDER",
    "MANIFEST_FILENAME",
    "ProvenanceError",
    "TableDescription",
    "WriteReceipt",
    "describe_table",
    "duckdb_connection",
    "list_tables",
    "promote",
    "query",
    "read_table",
    "table_exists",
    "to_analytics",
    "write_table",
]

_log = get_logger(__name__)

#: Le nom du fichier de manifeste déposé dans le répertoire de chaque jeu.
MANIFEST_FILENAME = "_manifest.json"

#: Le gabarit des fichiers Parquet écrits. Le nom est déterministe pour qu'une
#: réécriture du même contenu rende la même empreinte de répertoire.
_BASENAME_TEMPLATE = "part-{i}.parquet"

#: La compression retenue. ``zstd`` compresse mieux que ``snappy`` pour un coût
#: de décompression comparable sur des colonnes numériques (rapporté, benchmarks
#: Parquet de la fondation Apache), et DuckDB comme Polars la lisent nativement.
_COMPRESSION = "zstd"

#: L'ordre des étages. Une promotion ne va que vers la droite.
LAYER_ORDER: tuple[Layer, ...] = (Layer.RAW, Layer.BRONZE, Layer.SILVER, Layer.GOLD)

#: Un prédicat déclaratif, indépendant du moteur : colonne, opérateur, valeur.
type Predicate = tuple[str, str, Any]

_OPERATORS = frozenset({"==", "!=", "<", "<=", ">", ">=", "in", "not in"})

type _FrameLike = pl.DataFrame | pd.DataFrame


class ProvenanceError(QuantLabError):
    """Une donnée est écrite ou promue sans la provenance que son étage exige.

    Deux cas la lèvent. Un jeu ``gold`` écrit sans manifeste et sans parent : il
    serait alors consommé par un backtest sans que personne puisse dire d'où il
    vient. Une promotion qui remonte le lac, de ``gold`` vers ``bronze`` par
    exemple : le sens des étages serait perdu, et un jeu propre écraserait sa
    propre source.

    Note:
        Cette erreur n'est pas dans ``quantlab.core.errors`` parce qu'elle ne
        concerne que le lac. Elle hérite de :class:`~quantlab.core.errors.QuantLabError`,
        donc un appelant qui attrape la racine l'attrape aussi.
    """


@dataclass(frozen=True, slots=True)
class WriteReceipt:
    """Ce qui a été écrit, et où, une fois l'écriture terminée.

    Attributes:
        dataset_id: l'identifiant du jeu.
        layer: l'étage d'écriture.
        path: le répertoire du jeu.
        manifest_path: le chemin du manifeste déposé.
        n_rows: le nombre de lignes écrites, mesuré après écriture.
        n_columns: le nombre de colonnes écrites, colonnes de partition comprises.
        fingerprint: l'empreinte du contenu, préfixée ``sha256:``.
        files: les chemins relatifs des fichiers Parquet, triés.
    """

    dataset_id: str
    layer: Layer
    path: Path
    manifest_path: Path
    n_rows: int
    n_columns: int
    fingerprint: str
    files: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TableDescription:
    """La fiche d'un jeu du lac, lue sans charger les données.

    Attributes:
        dataset_id: l'identifiant du jeu.
        layer: l'étage où il vit.
        path: son répertoire.
        n_rows: le nombre de lignes, compté par Polars sans matérialiser les colonnes.
        schema: le nom de chaque colonne et son type Polars, en texte.
        files: les chemins relatifs des fichiers Parquet, triés.
        total_bytes: la taille sur disque, compression comprise.
        partition_by: les colonnes de partition, vide si le jeu n'est pas partitionné.
        has_manifest: si un manifeste accompagne le jeu.
        manifest: le contenu du manifeste, ou ``None``.
    """

    dataset_id: str
    layer: Layer
    path: Path
    n_rows: int
    schema: dict[str, str]
    files: tuple[str, ...]
    total_bytes: int
    partition_by: tuple[str, ...]
    has_manifest: bool
    manifest: dict[str, Any] | None


# --------------------------------------------------------------------------- #
# Chemins et utilitaires internes
# --------------------------------------------------------------------------- #


def _dataset_dir(dataset_id: str, layer: Layer | str) -> Path:
    """Rend le répertoire d'un jeu, sans le créer.

    Raises:
        ValueError: si l'identifiant est vide ou contient un séparateur de
            chemin. Un identifiant comme ``"../secrets"`` sortirait du lac.
    """
    if not dataset_id or dataset_id.strip() != dataset_id:
        raise ValueError(f"identifiant de jeu invalide : {dataset_id!r}")
    if "/" in dataset_id or "\\" in dataset_id or dataset_id in {".", ".."}:
        raise ValueError(f"un identifiant de jeu ne porte pas de séparateur : {dataset_id!r}")
    return data_dir(Layer(layer)) / dataset_id


def _parquet_files(directory: Path) -> list[Path]:
    """Rend les fichiers Parquet d'un jeu, triés par chemin pour le déterminisme."""
    return sorted(directory.rglob("*.parquet"))


def _is_hive(directory: Path) -> bool:
    """Dit si le jeu est partitionné, en cherchant un répertoire ``clé=valeur``."""
    return any(p.is_dir() and "=" in p.name for p in directory.rglob("*"))


def _partition_columns(directory: Path) -> tuple[str, ...]:
    """Rend les colonnes de partition lues dans les noms de répertoires.

    La lecture s'arrête au répertoire du jeu. Remonter au-delà ferait passer pour
    une partition n'importe quel répertoire ancêtre portant un « = », par exemple
    une racine de laboratoire nommée ``lake=v1``, et un jeu non partitionné se
    décrirait alors comme partitionné.
    """
    for file in _parquet_files(directory):
        relative = file.relative_to(directory)
        parts = [p.split("=", 1)[0] for p in relative.parts[:-1] if "=" in p]
        if parts:
            return tuple(parts)
    return ()


def _scan(directory: Path) -> pl.LazyFrame:
    """Rend un plan de lecture paresseux sur tous les fichiers Parquet du jeu."""
    files = _parquet_files(directory)
    if not files:
        raise DataQualityError(f"aucun fichier Parquet dans {directory}")
    return pl.scan_parquet(str(directory / "**" / "*.parquet"), hive_partitioning=_is_hive(directory))


def _sha256_file(path: Path, chunk_bytes: int = 1 << 20) -> str:
    """Rend l'empreinte SHA-256 d'un fichier, lu par blocs d'un mégaoctet."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(chunk_bytes):
            digest.update(block)
    return digest.hexdigest()


def _fingerprint(directory: Path) -> tuple[str, list[dict[str, Any]]]:
    """Rend l'empreinte du jeu entier et la fiche de chacun de ses fichiers.

    **Le problème.** Un jeu vit dans plusieurs fichiers, et un résultat publié
    doit pouvoir dire sur quels octets exactement il a été calculé. Comparer les
    dates de modification ne suffit pas : elles changent à la copie et ne
    changent pas à l'édition d'un octet en place.

    **L'intuition.** Hacher chaque fichier, puis hacher la liste triée des
    couples (chemin, haché). Le tri rend l'empreinte indépendante de l'ordre où
    le système de fichiers rend les noms, et l'inclusion du chemin fait qu'un
    fichier renommé change l'empreinte.

    .. math::

        F = H\\!\\left( \\bigl\\Vert_{i=1}^{n} \\; p_i \\,\\Vert\\, \\mathrm{hex}(H(b_i)) \\right)

    où :math:`H` est SHA-256, :math:`n` le nombre de fichiers Parquet du jeu,
    :math:`p_i` le chemin du fichier relatif au répertoire du jeu, :math:`b_i`
    son contenu en octets, :math:`\\mathrm{hex}` l'écriture hexadécimale sur
    64 caractères, et :math:`\\Vert` la concaténation d'octets. Les fichiers
    sont pris dans l'ordre croissant de :math:`p_i`.

    **Hypothèses.** Les noms de fichiers sont stables d'une écriture à l'autre,
    ce que garantit le gabarit déterministe ``part-{i}.parquet``. Aucun fichier
    n'est modifié pendant le calcul, le lac n'ayant qu'un écrivain à la fois.

    **Provenance.** SHA-256 vient de la norme NIST FIPS 180-4 (2015). La forme
    « hacher les hachés » est celle des arbres de Merkle (Merkle, 1979), réduite
    ici à un seul niveau, faute d'avoir besoin de prouver l'appartenance d'un
    fichier isolé.

    **Ce que l'empreinte prouve, et ce qu'elle ne prouve pas.** Elle prouve
    qu'aucun octet du jeu n'a bougé depuis l'écriture, ce qui suffit à détecter
    une modification manuelle ou une écriture concurrente. Elle ne prouve pas
    que deux versions de Parquet écriraient les mêmes octets pour les mêmes
    données : l'empreinte est un sceau, pas un identifiant sémantique du
    contenu. Comparer deux jeux écrits par deux versions de la bibliothèque
    passe par les données, pas par cette empreinte.

    **Alternatives.** Un CRC32 par fichier serait plus rapide mais se falsifie,
    donc il ne vaudrait que contre l'accident. Un haché des seules données
    logiques, lignes triées et colonnes normalisées, survivrait à un changement
    de version de Parquet, au prix d'une lecture complète du jeu à chaque
    contrôle. Le sceau d'octets est retenu parce qu'il coûte une lecture
    séquentielle et qu'il répond à la question posée ici : ce fichier est-il
    bien celui que le manifeste décrit.

    Args:
        directory: le répertoire du jeu.

    Returns:
        Le couple (empreinte préfixée ``sha256:``, fiches des fichiers). Chaque
        fiche porte le chemin relatif, la taille en octets et le haché du
        fichier.

    Note:
        Comment vérifier que l'implémentation est correcte : recalculer
        l'empreinte avec ``hashlib`` hors du module et retrouver la même chaîne,
        puis retourner un octet d'un fichier sans changer sa taille et vérifier
        que l'empreinte change. Les deux contrôles sont dans
        ``tests/unit/test_data_lake.py``.
    """
    rows: list[dict[str, Any]] = []
    combined = hashlib.sha256()
    for file in _parquet_files(directory):
        relative = file.relative_to(directory).as_posix()
        checksum = _sha256_file(file)
        rows.append({"path": relative, "bytes": file.stat().st_size, "sha256": checksum})
        combined.update(relative.encode("utf-8"))
        combined.update(checksum.encode("ascii"))
    return f"sha256:{combined.hexdigest()}", rows


def _serialize_manifest(manifest: Any) -> dict[str, Any] | None:
    """Met un objet de provenance sous une forme sérialisable en JSON.

    Accepte un modèle Pydantic (``model_dump``), un objet doté de ``to_dict``,
    ou n'importe quel dictionnaire. Les autres types sont refusés plutôt que
    convertis en texte : un manifeste illisible ne vaut pas mieux que pas de
    manifeste.

    Raises:
        ProvenanceError: si l'objet ne sait pas se transformer en dictionnaire.
    """
    if manifest is None:
        return None
    if isinstance(manifest, Mapping):
        return dict(manifest)
    for method in ("model_dump", "to_dict", "asdict"):
        converter = getattr(manifest, method, None)
        if callable(converter):
            payload = converter(mode="json") if method == "model_dump" else converter()
            if isinstance(payload, Mapping):
                return dict(payload)
    raise ProvenanceError(
        f"manifeste de type {type(manifest).__name__} non sérialisable : "
        "fournir un dictionnaire, un modèle Pydantic ou un objet doté de « to_dict »"
    )


def _to_polars(df: _FrameLike) -> pl.DataFrame:
    """Rend un ``polars.DataFrame`` à partir de pandas ou de Polars.

    Un index pandas qui n'est pas un ``RangeIndex`` porte de l'information, le
    plus souvent la date. Il devient donc une colonne au lieu d'être perdu en
    silence. Un tel index doit porter un nom, faute de quoi la colonne
    s'appellerait « None ».

    Raises:
        DataQualityError: si l'index pandas porte de l'information sans nom.
        TypeError: si l'objet n'est ni un DataFrame pandas ni un DataFrame Polars.
    """
    if isinstance(df, pl.DataFrame):
        return df
    if isinstance(df, pd.DataFrame):
        keep_index = not isinstance(df.index, pd.RangeIndex)
        if keep_index and df.index.name is None and df.index.nlevels == 1:
            raise DataQualityError(
                "l'index pandas porte de l'information mais n'a pas de nom : "
                "nommer l'index (par exemple « date ») avant d'écrire dans le lac"
            )
        return pl.from_pandas(df, include_index=keep_index)
    raise TypeError(f"attendu un DataFrame pandas ou Polars, reçu {type(df).__name__}")


def _predicate_expression(predicate: Predicate) -> pl.Expr:
    """Traduit un prédicat déclaratif en expression Polars.

    Args:
        predicate: un triplet ``(colonne, opérateur, valeur)``. Les opérateurs
            acceptés sont ``==``, ``!=``, ``<``, ``<=``, ``>``, ``>=``, ``in``
            et ``not in``.

    Raises:
        ValueError: si l'opérateur est inconnu.
    """
    column, operator, value = predicate
    if operator not in _OPERATORS:
        raise ValueError(f"opérateur inconnu : {operator!r}, attendu l'un de {sorted(_OPERATORS)}")
    col = pl.col(column)
    match operator:
        case "==":
            return col == value
        case "!=":
            return col != value
        case "<":
            return col < value
        case "<=":
            return col <= value
        case ">":
            return col > value
        case ">=":
            return col >= value
        case "in":
            return col.is_in(list(value))
        case _:
            return ~col.is_in(list(value))


def _view_name(dataset_id: str, layer: Layer) -> str:
    """Rend le nom de vue DuckDB d'un jeu, sous la forme ``<étage>_<jeu>``."""
    return f"{Layer(layer).value}_{dataset_id}"


# --------------------------------------------------------------------------- #
# Écriture
# --------------------------------------------------------------------------- #


def write_table(
    df: _FrameLike,
    dataset_id: str,
    layer: Layer | str,
    manifest: Any | None = None,
    partition_by: Sequence[str] | None = None,
    *,
    parent: Mapping[str, Any] | None = None,
    notes: str | None = None,
    overwrite: bool = False,
) -> WriteReceipt:
    """Écrit un jeu en Parquet dans le lac et dépose son manifeste.

    La fonction rend un accusé d'écriture qui porte l'empreinte du contenu. Le
    manifeste est écrit dans le répertoire du jeu, sous le nom
    ``_manifest.json``, pour qu'un jeu déplacé emporte sa provenance avec lui.

    Args:
        df: les données, en pandas ou en Polars. Un index pandas nommé qui
            n'est pas un ``RangeIndex`` devient une colonne.
        dataset_id: l'identifiant du jeu, sans séparateur de chemin.
        layer: l'étage d'écriture.
        manifest: la provenance de la donnée. Un dictionnaire, un modèle
            Pydantic ou un objet doté de ``to_dict``. Obligatoire en ``gold``.
        partition_by: les colonnes de partition, écrites en style Hive
            (``colonne=valeur`` dans le nom de répertoire). Partitionner par une
            colonne très cardinale, une date par exemple, crée un fichier par
            valeur et ralentit tout : partitionner par année ou par marché.
        parent: la citation du jeu d'origine, posée par :func:`promote`.
        notes: une phrase libre sur ce que cette écriture contient.
        overwrite: autorise l'écrasement d'un jeu existant. Interdit en ``raw``.

    Returns:
        Un :class:`WriteReceipt` avec le chemin, le compte de lignes mesuré
        après écriture, et l'empreinte.

    Raises:
        ProvenanceError: si l'étage est ``gold`` et qu'aucune provenance n'est
            fournie, ou si un jeu ``raw`` existant serait écrasé.
        DataQualityError: si le jeu existe déjà et que ``overwrite`` est faux,
            ou si le tableau n'a aucune colonne.
        ValueError: si une colonne de partition est absente du tableau.

    Example:
        >>> receipt = write_table(prices, "yahoo_prices", Layer.BRONZE)  # doctest: +SKIP
        >>> receipt.n_rows  # doctest: +SKIP
        12345

    Note:
        Comment vérifier que l'implémentation est correcte : réécrire le même
        contenu au même endroit doit rendre la même empreinte, et lire le jeu
        doit rendre exactement les valeurs écrites. Les deux contrôles sont
        dans ``tests/unit/test_data_lake.py``.
    """
    target_layer = Layer(layer)
    frame = _to_polars(df)
    if frame.width == 0:
        raise DataQualityError("un jeu sans colonne ne s'écrit pas")

    provenance = _serialize_manifest(manifest)
    if target_layer is Layer.GOLD and provenance is None and parent is None:
        raise ProvenanceError(
            f"le jeu « {dataset_id} » ne peut pas entrer en gold sans manifeste : "
            "un jeu consommé par un backtest doit dire d'où il vient"
        )

    columns = set(frame.columns)
    partitions = tuple(partition_by or ())
    missing = [c for c in partitions if c not in columns]
    if missing:
        raise ValueError(f"colonnes de partition absentes du tableau : {missing}")

    directory = _dataset_dir(dataset_id, target_layer)
    if directory.exists() and _parquet_files(directory):
        if target_layer is Layer.RAW:
            raise ProvenanceError(
                f"le jeu raw « {dataset_id} » existe déjà et raw est immuable : "
                "écrire sous un autre identifiant, daté, plutôt que corriger la preuve"
            )
        if not overwrite:
            raise DataQualityError(
                f"le jeu « {dataset_id} » existe déjà en {target_layer.value} : "
                "passer overwrite=True pour le remplacer"
            )
        shutil.rmtree(directory)
    ensure(directory)

    if partitions:
        pq.write_to_dataset(
            frame.to_arrow(),
            root_path=str(directory),
            partition_cols=list(partitions),
            basename_template=_BASENAME_TEMPLATE,
            existing_data_behavior="delete_matching",
            compression=_COMPRESSION,
        )
    else:
        frame.write_parquet(directory / _BASENAME_TEMPLATE.format(i=0), compression=_COMPRESSION)

    fingerprint, files = _fingerprint(directory)
    written = _scan(directory)
    schema = written.collect_schema()
    n_rows = int(written.select(pl.len()).collect().item())

    payload: dict[str, Any] = {
        "dataset_id": dataset_id,
        "layer": target_layer.value,
        "created_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "n_rows": n_rows,
        "n_columns": len(schema),
        "columns": {name: str(dtype) for name, dtype in schema.items()},
        "partition_by": list(partitions),
        "compression": _COMPRESSION,
        "fingerprint": fingerprint,
        "files": files,
        "source": provenance,
        "parent": dict(parent) if parent is not None else None,
        "notes": notes,
        "writer": {"polars": pl.__version__, "pyarrow": pa.__version__},
    }
    manifest_path = directory / MANIFEST_FILENAME
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), "utf-8")

    _log.info(
        "jeu écrit",
        extra={
            "dataset_id": dataset_id,
            "layer": target_layer.value,
            "rows": n_rows,
            "files": len(files),
            "fingerprint": fingerprint,
        },
    )
    return WriteReceipt(
        dataset_id=dataset_id,
        layer=target_layer,
        path=directory,
        manifest_path=manifest_path,
        n_rows=n_rows,
        n_columns=len(schema),
        fingerprint=fingerprint,
        files=tuple(row["path"] for row in files),
    )


# --------------------------------------------------------------------------- #
# Lecture
# --------------------------------------------------------------------------- #


def read_table(
    dataset_id: str,
    layer: Layer | str,
    columns: Sequence[str] | None = None,
    filters: Sequence[Predicate] | None = None,
    engine: Literal["polars", "pandas"] = "polars",
) -> pl.DataFrame | pd.DataFrame:
    """Lit un jeu du lac, en ne touchant que les colonnes et les lignes demandées.

    La lecture est paresseuse : Polars construit un plan, pousse la projection
    des colonnes et les prédicats jusque dans le fichier Parquet, et ne
    matérialise que ce qui reste. Demander deux colonnes sur quarante lit deux
    colonnes sur disque, pas quarante.

    Args:
        dataset_id: l'identifiant du jeu.
        layer: l'étage où le lire.
        columns: les colonnes voulues. Toutes si absent.
        filters: des prédicats ``(colonne, opérateur, valeur)`` combinés par
            « et ». Les opérateurs sont ``==``, ``!=``, ``<``, ``<=``, ``>``,
            ``>=``, ``in`` et ``not in``. Ce format est déclaratif à dessein :
            il se traduit vers Polars comme vers DuckDB sans changer le code
            appelant.
        engine: ``"polars"`` rend un ``polars.DataFrame``, ``"pandas"`` rend un
            ``pandas.DataFrame`` à index entier. Pour un index temporel, passer
            le résultat à :func:`to_analytics`.

    Returns:
        Le tableau demandé, dans le type du moteur choisi.

    Raises:
        FileNotFoundError: si le jeu n'existe pas à cet étage.
        DataQualityError: si le répertoire existe sans fichier Parquet.
        ValueError: si le moteur ou un opérateur est inconnu.

    Example:
        >>> read_table("prices", Layer.SILVER, columns=["date", "close"],
        ...            filters=[("ticker", "in", ["SPY", "QQQ"])])  # doctest: +SKIP
    """
    if engine not in {"polars", "pandas"}:
        raise ValueError(f"moteur inconnu : {engine!r}, attendu « polars » ou « pandas »")
    directory = _dataset_dir(dataset_id, layer)
    if not directory.exists():
        raise FileNotFoundError(f"jeu introuvable : {directory}")
    plan = _scan(directory)
    if filters:
        for predicate in filters:
            plan = plan.filter(_predicate_expression(predicate))
    if columns is not None:
        plan = plan.select(list(columns))
    frame = plan.collect()
    return frame.to_pandas() if engine == "pandas" else frame


def table_exists(dataset_id: str, layer: Layer | str) -> bool:
    """Dit si un jeu porte au moins un fichier Parquet à cet étage."""
    directory = _dataset_dir(dataset_id, layer)
    return directory.is_dir() and bool(_parquet_files(directory))


def list_tables(layer: Layer | str) -> list[str]:
    """Rend les identifiants des jeux d'un étage, triés par ordre alphabétique."""
    base = data_dir(Layer(layer))
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir() if p.is_dir() and _parquet_files(p))


def describe_table(dataset_id: str, layer: Layer | str) -> TableDescription:
    """Rend la fiche d'un jeu sans charger ses colonnes en mémoire.

    Le schéma vient des en-têtes Parquet et le compte de lignes des
    métadonnées de groupe de lignes. Décrire un jeu de dix gigaoctets coûte donc
    le temps de lire quelques kilooctets d'en-têtes.

    Raises:
        FileNotFoundError: si le jeu n'existe pas à cet étage.
    """
    directory = _dataset_dir(dataset_id, layer)
    if not table_exists(dataset_id, layer):
        raise FileNotFoundError(f"jeu introuvable : {directory}")
    plan = _scan(directory)
    schema = plan.collect_schema()
    files = _parquet_files(directory)
    manifest_path = directory / MANIFEST_FILENAME
    manifest = json.loads(manifest_path.read_text("utf-8")) if manifest_path.is_file() else None
    return TableDescription(
        dataset_id=dataset_id,
        layer=Layer(layer),
        path=directory,
        n_rows=int(plan.select(pl.len()).collect().item()),
        schema={name: str(dtype) for name, dtype in schema.items()},
        files=tuple(f.relative_to(directory).as_posix() for f in files),
        total_bytes=sum(f.stat().st_size for f in files),
        partition_by=_partition_columns(directory),
        has_manifest=manifest is not None,
        manifest=manifest,
    )


# --------------------------------------------------------------------------- #
# SQL
# --------------------------------------------------------------------------- #


def duckdb_connection(read_only: bool = True) -> duckdb.DuckDBPyConnection:
    """Rend une connexion DuckDB où chaque jeu du lac est déjà une vue.

    Les vues portent le nom ``<étage>_<jeu>`` : un jeu ``prices`` en ``silver``
    s'interroge par ``SELECT * FROM silver_prices``.

    **Pourquoi DuckDB lit le Parquet sans le charger en mémoire.** Une vue sur
    ``read_parquet`` ne copie rien. Trois mécanismes se combinent. D'abord le
    format est en colonnes : lire deux colonnes sur quarante lit les seuls
    octets de ces deux colonnes, alors qu'un format en lignes obligerait à
    traverser les quarante. Ensuite chaque fichier porte, pour chaque groupe de
    lignes et chaque colonne, le minimum et le maximum ; un filtre
    ``WHERE date >= '2020-01-01'`` saute les groupes dont le maximum est
    antérieur, sans les décompresser. Enfin l'exécution est vectorisée et par
    flux : DuckDB traite des lots de quelques milliers de lignes puis les
    libère. La mémoire consommée dépend donc de la requête et non de la taille
    du fichier. Une agrégation sur un jeu plus gros que la mémoire vive passe,
    et c'est la raison pour laquelle le lac reste en Parquet plutôt qu'en base.

    Args:
        read_only: à ``True``, la connexion s'ouvre avec les seules vues du lac
            et aucun espace où déposer un résultat. À ``False``, un schéma
            ``scratch`` est créé pour y matérialiser des résultats
            intermédiaires.

    Returns:
        Une connexion en mémoire, à fermer par l'appelant.

    Note:
        DuckDB refuse d'ouvrir une base en mémoire en mode lecture seule, ce qui
        est mesuré : ``duckdb.connect(":memory:", read_only=True)`` lève
        ``CatalogException: Cannot launch in-memory database in read-only mode``
        avec la version 1.5.5. Le drapeau est donc tenu par le laboratoire et
        non par le moteur, et sa portée est limitée : mesuré, un ``CREATE TABLE``
        dans le schéma principal réussit même à ``True``. Ce que le drapeau
        garantit est plus étroit. Aucun objet inscriptible n'est créé à
        l'ouverture, et les fichiers du lac ne sont jamais ouverts qu'en lecture
        par ``read_parquet``, si bien qu'une requête ne peut pas modifier le lac.
        Un appelant qui écrit dans sa propre connexion en mémoire n'atteint que
        sa mémoire.

    Example:
        >>> with duckdb_connection() as con:  # doctest: +SKIP
        ...     con.execute("SELECT count(*) FROM bronze_prices").fetchone()
    """
    con = duckdb.connect(":memory:")
    n_views = 0
    for layer in LAYER_ORDER:
        for dataset_id in list_tables(layer):
            directory = _dataset_dir(dataset_id, layer)
            pattern = (directory / "**" / "*.parquet").as_posix().replace("'", "''")
            hive = "true" if _is_hive(directory) else "false"
            con.execute(
                f'CREATE OR REPLACE VIEW "{_view_name(dataset_id, layer)}" AS '
                f"SELECT * FROM read_parquet('{pattern}', hive_partitioning={hive})"
            )
            n_views += 1
    if not read_only:
        con.execute("CREATE SCHEMA IF NOT EXISTS scratch")
    _log.debug("connexion DuckDB ouverte", extra={"views": n_views, "read_only": read_only})
    return con


def query(sql: str) -> pl.DataFrame:
    """Exécute du SQL sur le lac et rend un ``polars.DataFrame``.

    Args:
        sql: la requête, écrite contre les vues ``<étage>_<jeu>``.

    Returns:
        Le résultat, en Polars. Le passage par Arrow évite une copie : DuckDB et
        Polars partagent la même représentation en colonnes.

    Example:
        >>> query("SELECT ticker, count(*) AS n FROM silver_prices GROUP BY 1")  # doctest: +SKIP
    """
    with duckdb_connection(read_only=True) as con:
        return con.execute(sql).pl()


# --------------------------------------------------------------------------- #
# La frontière avec l'analytique
# --------------------------------------------------------------------------- #


def to_analytics(
    df: _FrameLike,
    index_col: str = "date",
    *,
    timezone: str | None = "UTC",
    sort: bool = True,
    drop_index_col: bool = True,
) -> pd.DataFrame:
    """Rend un ``pandas.DataFrame`` indexé par le temps, trié et sans doublon.

    C'est la seule conversion Polars vers pandas du laboratoire, et elle vit à
    la sortie du ``gold``. La centraliser tient trois promesses que du code
    dispersé perdrait : l'index est trié, il ne porte aucun doublon, et son
    fuseau est déclaré au lieu d'être hérité au hasard du fichier lu.

    **Pourquoi le fuseau est un paramètre et pas une devinette.** Une barre
    quotidienne n'a pas d'heure et se lit naturellement en date naïve. Une barre
    intrajournalière en a une, et la lire sans fuseau mélange l'heure de New
    York et celle de Montréal deux fois par an, aux changements d'heure. Le
    laboratoire écrit donc ``timezone="UTC"`` par défaut et exige un choix
    explicite pour le reste.

    Args:
        df: le tableau à convertir, Polars ou pandas.
        index_col: la colonne qui porte le temps. Si elle est absente et que
            l'index pandas est déjà un ``DatetimeIndex``, cet index est repris.
        timezone: le fuseau de l'index. ``"UTC"`` par défaut, ``None`` pour un
            index naïf, un nom de fuseau IANA sinon.
        sort: trie l'index croissant. À ``False``, un index non trié lève.
        drop_index_col: retire la colonne de temps des colonnes une fois posée
            en index.

    Returns:
        Un ``pandas.DataFrame`` à ``DatetimeIndex`` strictement croissant.

    Raises:
        DataQualityError: si la colonne de temps manque, si elle porte des
            valeurs manquantes, si l'index porte un doublon, ou si l'index n'est
            pas trié alors que ``sort`` est faux.

    Example:
        >>> frame = pl.DataFrame({"date": ["2020-01-03", "2020-01-02"], "r": [0.01, -0.02]})
        >>> panel = to_analytics(frame)
        >>> panel.index[0].strftime("%Y-%m-%d")
        '2020-01-02'

    Note:
        Comment vérifier que l'implémentation est correcte : donner deux lignes
        dans le désordre et retrouver l'ordre chronologique, puis donner deux
        fois la même date et vérifier que la fonction lève. Les deux cas sont
        testés.
    """
    if isinstance(df, pl.DataFrame):
        out = df.to_pandas()
    elif isinstance(df, pd.DataFrame):
        out = df.copy()
    else:
        raise TypeError(f"attendu un DataFrame pandas ou Polars, reçu {type(df).__name__}")

    if index_col in out.columns:
        stamps = pd.DatetimeIndex(pd.to_datetime(out[index_col]))
        if drop_index_col:
            out = out.drop(columns=[index_col])
    elif isinstance(out.index, pd.DatetimeIndex):
        stamps = out.index
    else:
        raise DataQualityError(
            f"colonne de temps « {index_col} » absente, et l'index n'est pas un DatetimeIndex ; "
            f"colonnes présentes : {list(out.columns)}"
        )

    if bool(stamps.isna().any()):
        raise DataQualityError(f"la colonne de temps « {index_col} » porte des dates manquantes")

    if timezone is None:
        stamps = stamps.tz_localize(None) if stamps.tz is not None else stamps
    elif stamps.tz is None:
        stamps = stamps.tz_localize(timezone)
    else:
        stamps = stamps.tz_convert(timezone)

    stamps.name = index_col
    out.index = stamps

    duplicated = stamps.duplicated()
    if bool(duplicated.any()):
        offenders = stamps[duplicated].unique()[:5]
        raise DataQualityError(
            f"l'index temporel porte {int(duplicated.sum())} doublon(s), "
            f"par exemple {[str(x) for x in offenders]}"
        )

    if not stamps.is_monotonic_increasing:
        if not sort:
            raise DataQualityError("l'index temporel n'est pas trié et sort=False")
        out = out.sort_index()
    return out


# --------------------------------------------------------------------------- #
# Promotion d'un étage au suivant
# --------------------------------------------------------------------------- #


def promote(
    dataset_id: str,
    from_layer: Layer | str,
    to_layer: Layer | str,
    transform: Callable[[pl.DataFrame], _FrameLike] | None = None,
    notes: str | None = None,
    *,
    to_dataset_id: str | None = None,
    partition_by: Sequence[str] | None = None,
    overwrite: bool = False,
) -> WriteReceipt:
    """Passe un jeu d'un étage au suivant en écrivant un manifeste qui cite son parent.

    Le manifeste enfant porte l'identifiant, l'étage et l'empreinte du parent.
    C'est ce qui rend la chaîne remontable : d'un panneau ``gold`` on retrouve
    le fichier ``raw`` exact qui l'a produit, en suivant les empreintes.

    Args:
        dataset_id: le jeu à promouvoir.
        from_layer: son étage actuel.
        to_layer: l'étage d'arrivée, strictement à droite du précédent.
        transform: la fonction appliquée au tableau lu. Sans elle, le contenu
            est recopié tel quel, ce qui n'a de sens que d'un étage technique au
            suivant.
        notes: ce que cette promotion a décidé, en une phrase. Une décision
            méthodologique non écrite est une décision perdue.
        to_dataset_id: l'identifiant d'arrivée, le même par défaut.
        partition_by: les colonnes de partition à l'arrivée.
        overwrite: autorise l'écrasement du jeu d'arrivée.

    Returns:
        L'accusé d'écriture du jeu enfant.

    Raises:
        ProvenanceError: si l'étage d'arrivée n'est pas strictement après
            l'étage de départ.
        FileNotFoundError: si le jeu de départ n'existe pas.

    Example:
        >>> promote("prices", Layer.BRONZE, Layer.SILVER,
        ...         transform=lambda d: d.unique(subset=["date", "ticker"]),
        ...         notes="doublons de séance retirés")  # doctest: +SKIP

    Note:
        Comment vérifier que l'implémentation est correcte : promouvoir un jeu,
        relire le manifeste enfant, et retrouver dans son bloc ``parent``
        l'empreinte que le manifeste du parent portait. C'est testé.
    """
    source_layer = Layer(from_layer)
    target_layer = Layer(to_layer)
    if LAYER_ORDER.index(target_layer) <= LAYER_ORDER.index(source_layer):
        raise ProvenanceError(
            f"promotion refusée de {source_layer.value} vers {target_layer.value} : "
            "le lac se remonte de raw vers gold et jamais dans l'autre sens"
        )
    if not table_exists(dataset_id, source_layer):
        raise FileNotFoundError(f"jeu introuvable : {_dataset_dir(dataset_id, source_layer)}")

    parent_description = describe_table(dataset_id, source_layer)
    parent_manifest = parent_description.manifest or {}
    parent_block: dict[str, Any] = {
        "dataset_id": dataset_id,
        "layer": source_layer.value,
        "fingerprint": parent_manifest.get("fingerprint"),
        "n_rows": parent_description.n_rows,
        "created_at": parent_manifest.get("created_at"),
        "transform": getattr(transform, "__name__", None) if transform is not None else None,
        "promoted_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
    }

    frame = read_table(dataset_id, source_layer, engine="polars")
    if not isinstance(frame, pl.DataFrame):  # pragma: no cover - le moteur Polars rend du Polars
        raise TypeError("la lecture Polars n'a pas rendu un DataFrame Polars")
    result = transform(frame) if transform is not None else frame

    receipt = write_table(
        result,
        to_dataset_id or dataset_id,
        target_layer,
        manifest=parent_manifest.get("source"),
        partition_by=partition_by,
        parent=parent_block,
        notes=notes,
        overwrite=overwrite,
    )
    _log.info(
        "jeu promu",
        extra={
            "dataset_id": dataset_id,
            "from_layer": source_layer.value,
            "to_layer": target_layer.value,
            "rows_in": parent_description.n_rows,
            "rows_out": receipt.n_rows,
        },
    )
    return receipt

"""Le fournisseur de prix de prototypage, et ses limites déclarées sans détour.

Yahoo Finance rend gratuitement des barres quotidiennes sur des dizaines de
milliers de titres. C'est sa seule qualité, et elle suffit pour maquetter une
stratégie avant de payer un fournisseur professionnel. Sa donnée porte quatre
défauts connus, énumérés dans :data:`KNOWN_LIMITATIONS`, et le premier invalide
à lui seul toute étude transversale sur un univers historique.

**Le biais de survie, chiffré.** Yahoo ne rend que les titres qui existent
encore. Une sélection d'actions bâtie sur cet univers ne voit jamais les
faillites, donc surestime le rendement. L'ordre de grandeur rapporté par la
littérature va de 1 à 4 points de pourcentage par an, selon la période et
l'univers retenus. Deux références : Brown, Goetzmann, Ibbotson et Ross (1992)
pour la mécanique du biais, Elton, Gruber et Blake (1996) pour les fonds. Statut
de ce chiffre : rapporté, non mesuré ici.

**La frontière du module.** Deux fonctions pures font le travail scientifique,
:func:`normalize` et :func:`to_wide`, et se testent sans réseau. La classe
:class:`YahooProvider` ne fait que le réseau et la provenance. Séparer les deux
est la raison pour laquelle la totalité de la logique de mise en forme est
vérifiable hors ligne.

**Ce que ce module ne fait pas.** Il ne met rien en cache, ne pose aucun fichier
sur le disque, et ne connaît pas la couche du lac où sa sortie sera rangée. Le
rangement appartient à ``quantlab.data``, pas au fournisseur.

Exemple :

.. code-block:: python

    provider = YahooProvider()
    prices = provider.fetch(["SPY", "TLT"], start="2020-01-01", end="2020-12-31")
    wide = to_wide(prices, field="adj_close")
    manifest = provider.manifest()
    assert manifest.survivorship_free is False
"""

from __future__ import annotations

import datetime as dt
import re
import time
from collections.abc import Sequence
from typing import Any, ClassVar, Final, Literal

import pandas as pd

from quantlab.core.config import get_settings
from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.logging import get_logger, stage
from quantlab.core.paths import Layer
from quantlab.core.types import Frequency
from quantlab.data.manifest import DatasetManifest, sha256_frame
from quantlab.data.providers.base import BaseProvider

log = get_logger(__name__)

#: Le nom du fournisseur, tel qu'il apparaît dans une configuration d'expérience.
PROVIDER_NAME: Final[str] = "yahoo"

#: Le schéma de sortie, fixe. Aucune fonction de ce module n'en rend un autre.
SCHEMA: Final[tuple[str, ...]] = (
    "date",
    "symbol",
    "open",
    "high",
    "low",
    "close",
    "adj_close",
    "volume",
)

#: Les champs de valeur, ceux qui portent un nombre par séance et par titre.
VALUE_FIELDS: Final[tuple[str, ...]] = ("open", "high", "low", "close", "adj_close", "volume")

#: Les champs sans lesquels une barre n'est pas une barre.
REQUIRED_FIELDS: Final[frozenset[str]] = frozenset({"open", "high", "low", "close"})

#: Le type de chaque colonne du schéma. Le volume est en flottant parce qu'il
#: manque parfois, et qu'un entier ne sait pas porter une valeur absente.
DTYPES: Final[dict[str, str]] = {
    "date": "datetime64[ns]",
    "symbol": "str",
    "open": "float64",
    "high": "float64",
    "low": "float64",
    "close": "float64",
    "adj_close": "float64",
    "volume": "float64",
}

#: Les intervalles pour lesquels une barre couvre une séance entière ou plus.
#: Leur horodatage est ramené à minuit, sans quoi deux sources de la même séance
#: ne se joignent pas.
DAILY_OR_COARSER: Final[frozenset[str]] = frozenset({"1d", "5d", "1wk", "1mo", "3mo"})

#: La licence de la source, telle qu'elle vaut pour ce laboratoire.
LICENSE: Final[str] = "Yahoo, usage personnel"

#: Ce qui arrive au chiffre déjà téléchargé quand la source le recalcule.
REVISION_POLICY: Final[str] = (
    "les prix ajustés sont recalculés à chaque dividende, donc une même requête "
    "rend des valeurs différentes dans le temps"
)

#: Le nom de la source, tel qu'il apparaît dans un manifeste.
SOURCE_NAME: Final[str] = "Yahoo Finance"

#: L'adresse publique de la source. L'adresse de l'interface interrogée par
#: yfinance n'est pas documentée par Yahoo, donc elle n'est pas écrite ici.
SOURCE_URL: Final[str] = "https://finance.yahoo.com"

#: La version de la mise en forme. Elle change dès que le schéma de sortie
#: change, pour qu'un manifeste ancien ne se confonde pas avec un neuf.
PROCESSING_VERSION: Final[str] = "quantlab.data.providers.yahoo/1"

#: Le traitement des actions de société, selon le mode demandé à Yahoo.
CORPORATE_ACTIONS_AUTO: Final[str] = (
    "auto_adjust=True : dividendes et divisions appliqués rétroactivement au close, "
    "et adj_close recopie ce close déjà corrigé"
)
CORPORATE_ACTIONS_MANUAL: Final[str] = (
    "auto_adjust=False : close brut, adj_close corrigé des dividendes et des divisions, "
    "l'écart entre les deux colonnes mesurant l'effet cumulé des détachements"
)

#: La correspondance entre l'intervalle demandé à Yahoo et la fréquence du
#: laboratoire. ``Frequency`` ne descend pas sous la séance, donc les
#: intervalles intrajournaliers n'y ont aucun équivalent et ne sont pas listés.
INTERVAL_TO_FREQUENCY: Final[dict[str, Frequency]] = {
    "1d": Frequency.DAILY,
    "1wk": Frequency.WEEKLY,
    "1mo": Frequency.MONTHLY,
    "3mo": Frequency.QUARTERLY,
}

#: Les quatre limites connues de la source. Elles se citent dans tout rapport
#: qui s'appuie sur ce fournisseur, et aucune n'est corrigeable par du code.
KNOWN_LIMITATIONS: Final[tuple[str, ...]] = (
    "Biais de survie : les titres radiés, fusionnés ou faillis ne sont pas rendus, "
    "si bien qu'un univers reconstruit aujourd'hui ne contient que des survivants.",
    "Aucun calendrier point-in-time des indices : la composition passée d'un indice "
    "n'est pas connaissable, donc une sélection « les titres du S&P 500 en 2005 » "
    "se fabrique avec la liste d'aujourd'hui, ce qui est une fuite.",
    "Ajustements rétroactifs : chaque dividende et chaque division réécrivent toute "
    "l'histoire des prix ajustés, donc un résultat n'est pas reproductible à la "
    "virgule sans conserver l'extraction datée.",
    "Aucun carnet d'ordres : ni écart acheteur-vendeur, ni profondeur, ni horodatage "
    "de transaction, donc aucun coût d'exécution ne se mesure sur cette source.",
)

#: Les valeurs acceptées par l'argument ``on_missing``.
MissingPolicy = Literal["raise", "drop"]

#: Les clés que :meth:`YahooProvider.manifest` accepte en remplacement.
_MANIFEST_KEYS: Final[frozenset[str]] = frozenset(
    {"symbols", "start", "end", "interval", "rows", "adjusted", "auto_adjust", "dataset_id", "checksum"}
)


def _dataset_id(symbols: tuple[str, ...], interval: str, start: dt.date, end: dt.date) -> str:
    """Rend l'identifiant du jeu, lisible et sûr pour un nom de fichier.

    Un identifiant nomme ce qu'il contient : la source, l'univers, le pas de
    temps et la fenêtre. Yahoo emploie dans ses tickers des caractères qu'un
    système de fichiers refuse, dont l'accent circonflexe des indices et le
    signe égal des devises. Ils sont remplacés par un tiret.
    """
    portion = symbols[0].lower() if len(symbols) == 1 else f"{len(symbols)}titres"
    portion = re.sub(r"[^a-z0-9]+", "-", portion).strip("-") or "univers"
    return f"yahoo-{portion}-{interval}-{start.isoformat()}-{end.isoformat()}"


def _canonical_field(name: object) -> str:
    """Rend le nom canonique d'un champ yfinance, « Adj Close » devenant « adj_close »."""
    return str(name).strip().lower().replace(" ", "_")


def _as_symbol_tuple(tickers: Sequence[str] | str | None) -> tuple[str, ...]:
    """Rend les identifiants demandés sous forme de tuple, doublons retirés.

    Yahoo répond en majuscules quel que soit la casse demandée, mesuré le
    2026-09-01. Les identifiants sont donc mis en majuscules ici, pour que la
    comparaison entre demandé et reçu ne dépende pas de la saisie.
    """
    if tickers is None:
        return ()
    if isinstance(tickers, str):
        tickers = [tickers]
    seen: dict[str, None] = {}
    for raw in tickers:
        symbol = str(raw).strip().upper()
        if symbol:
            seen[symbol] = None
    return tuple(seen)


def _as_date(value: dt.date | dt.datetime | str) -> dt.date:
    """Rend une date calendaire à partir d'une date, d'un instant ou d'un texte ISO."""
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return pd.Timestamp(value).date()


def _dates_from_index(index: pd.Index, *, interval: str) -> pd.DatetimeIndex:
    """Rend l'index temporel d'un tableau yfinance en horodatages sans fuseau.

    Le fuseau est retiré en gardant l'heure locale du marché, et non l'heure
    universelle. La raison se vérifie sur un exemple. Une séance de New York
    ouverte le 2 janvier à minuit local devient le 2 janvier à 5 heures en temps
    universel, donc sa date survit. Un marché à l'est de Greenwich, lui,
    changerait de jour.
    """
    try:
        idx = pd.DatetimeIndex(index)
    except (TypeError, ValueError) as exc:
        raise DataQualityError(
            f"l'index du tableau yfinance n'est pas temporel : {type(index).__name__}"
        ) from exc
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    if interval in DAILY_OR_COARSER:
        idx = idx.normalize()
    return idx


def _split_by_symbol(raw: pd.DataFrame, *, requested: tuple[str, ...]) -> dict[str, pd.DataFrame]:
    """Rend un tableau par titre, colonnes déjà renommées en noms canoniques.

    yfinance rend trois formes selon ses arguments, mesurées le 2026-09-01 avec
    la version 1.7.0 :

    1. ``group_by="column"`` et plusieurs titres, colonnes à deux niveaux
       nommés ``('Price', 'Ticker')``, le champ au premier niveau ;
    2. ``group_by="ticker"``, les mêmes deux niveaux dans l'ordre inverse ;
    3. ``multi_level_index=False`` et un seul titre, colonnes plates.

    Le niveau qui porte les champs se reconnaît à son contenu, pas à son nom :
    c'est celui qui contient « Open », « High », « Low » et « Close ».

    Raises:
        DataQualityError: si aucun niveau ne porte les champs, si les colonnes
            sont plates sans qu'un seul identifiant soit demandé, ou si les
            champs obligatoires manquent.
    """
    if isinstance(raw.columns, pd.MultiIndex):
        if raw.columns.nlevels != 2:
            raise DataQualityError(
                f"colonnes à {raw.columns.nlevels} niveaux, deux sont attendus (champ et titre)"
            )
        level_fields = [
            {_canonical_field(v) for v in raw.columns.get_level_values(level)} for level in (0, 1)
        ]
        if level_fields[0].issuperset(REQUIRED_FIELDS):
            symbol_level = 1
        elif level_fields[1].issuperset(REQUIRED_FIELDS):
            symbol_level = 0
        else:
            raise DataQualityError(
                "aucun niveau de colonnes ne porte les champs open, high, low et close ; "
                f"niveau 0 = {sorted(level_fields[0])}, niveau 1 = {sorted(level_fields[1])}"
            )
        symbols = list(dict.fromkeys(str(s).upper() for s in raw.columns.get_level_values(symbol_level)))
        out: dict[str, pd.DataFrame] = {}
        for symbol in symbols:
            sub = raw.xs(symbol, axis=1, level=symbol_level, drop_level=True)
            sub.columns = pd.Index([_canonical_field(c) for c in sub.columns])
            out[symbol] = sub
        return out

    columns = {_canonical_field(c) for c in raw.columns}
    if not columns.issuperset(REQUIRED_FIELDS):
        raise DataQualityError(f"colonnes plates incomplètes : {sorted(REQUIRED_FIELDS - columns)} manquent")
    if len(requested) != 1:
        raise DataQualityError(
            "un tableau à colonnes plates ne dit pas de quel titre il parle ; "
            f"un seul identifiant doit être passé, {len(requested)} l'ont été"
        )
    flat = raw.copy()
    flat.columns = pd.Index([_canonical_field(c) for c in flat.columns])
    return {requested[0]: flat}


def normalize(
    raw: pd.DataFrame,
    *,
    tickers: Sequence[str] | str | None = None,
    interval: str = "1d",
    on_missing: MissingPolicy = "raise",
    check_ohlc: bool = True,
) -> pd.DataFrame:
    """Rend un tableau long au schéma fixe à partir de la réponse de yfinance.

    **Le problème.** yfinance ne rend pas une table, il rend trois formes selon
    ses arguments : colonnes à deux niveaux champ puis titre, les mêmes deux
    niveaux inversés, ou colonnes plates pour un titre seul. Un code d'analyse
    qui s'adapte à ces formes les propage partout, et la première ligne d'une
    stratégie devient une gymnastique de colonnes.

    **L'intuition.** Une observation de marché est un triplet, la date, le titre
    et la barre. Le format long l'écrit tel quel, une ligne par couple, et toute
    autre forme s'en déduit. C'est le format que DuckDB, Polars et Parquet
    aiment, et c'est celui que :func:`to_wide` retourne au besoin.

    **La transformation.**

    .. math::

        \\mathrm{normalize} : (t, f, s) \\mapsto (t, s, f)

    où :math:`t` est l'horodatage de la barre, :math:`s` le titre et :math:`f`
    le champ, avec :math:`f \\in \\{open, high, low, close, adj\\_close, volume\\}`.
    Le résultat est trié par :math:`(t, s)`, et le couple :math:`(t, s)` est une
    clé, donc unique.

    **Les hypothèses.** Trois, toutes vérifiées et non supposées. Un, l'index du
    tableau reçu est temporel. Deux, le couple date et titre est unique, ce qui
    est contrôlé et lève sinon. Trois, ``high`` domine ``low``, ce qui est
    contrôlé quand ``check_ohlc`` vaut vrai.

    **La provenance.** Le format long, dit *tidy*, vient de Wickham (2014),
    « Tidy Data », Journal of Statistical Software 59(10). Sa règle est simple :
    une variable par colonne, une observation par ligne.

    **Les limites.** La fonction met en forme, elle ne corrige rien. Elle ne
    détecte pas une division non ajustée, ne comble aucun trou de séance, et ne
    sait pas si un titre a cessé d'exister ou si Yahoo a simplement omis de
    répondre. Le contrôle de qualité qui va plus loin vit dans
    ``quantlab.data.quality``.

    **Les alternatives.** Garder la forme large de yfinance évite cette étape,
    au prix d'un code d'analyse qui connaît la forme de son fournisseur. Passer
    par un index à deux niveaux date et titre est équivalent, et rend seulement
    l'écriture des jointures plus lourde.

    **Pourquoi cette forme ici.** Le laboratoire écrit son lac en Parquet et
    l'interroge en DuckDB, deux technologies orientées colonnes qui travaillent
    sur des tables longues. La conversion vers pandas large se fait une fois, à
    l'entrée d'un calcul, par :func:`to_wide`.

    Args:
        raw: la réponse de ``yfinance.download``, telle quelle.
        tickers: les identifiants demandés. Ils servent à deux choses, nommer le
            titre quand les colonnes sont plates, et détecter ceux que Yahoo n'a
            pas rendus. Sans eux, aucun titre manquant ne peut être détecté.
        interval: le pas de temps demandé. Les intervalles d'une séance ou plus
            voient leur horodatage ramené à minuit.
        on_missing: « raise » lève quand un titre demandé n'a aucune donnée,
            « drop » le retire en journalisant un avertissement. La valeur par
            défaut lève, parce qu'un univers silencieusement amputé fausse toute
            comparaison transversale.
        check_ohlc: contrôle que ``high`` reste supérieur ou égal à ``low``.

    Returns:
        Un tableau aux colonnes :data:`SCHEMA`, trié par date puis par titre,
        d'index entier remis à zéro.

    Raises:
        InsufficientDataError: si le tableau reçu est vide, ou si aucune ligne
            ne survit au retrait des barres entièrement absentes.
        DataQualityError: si la forme des colonnes est inconnue, si un couple
            date et titre apparaît deux fois, ou si ``high`` passe sous ``low``.
            Levée aussi quand un titre demandé n'a rien rendu et que
            ``on_missing`` vaut « raise ».
        ValueError: si ``on_missing`` ne vaut ni « raise » ni « drop ».

    Example:
        Trois séances de janvier 2024 pour deux titres donnent six lignes, et la
        première porte le titre dont le nom vient en premier dans l'ordre
        alphabétique.

    Note:
        Comment vérifier que l'implémentation est correcte. Le nombre de lignes
        rendues égale le nombre de dates multiplié par le nombre de titres quand
        aucune barre ne manque. La somme d'une colonne de prix est invariante à
        l'ordre des lignes reçues. Et le passage par :func:`to_wide` puis la
        relecture d'une cellule redonnent la valeur d'origine. Les trois
        propriétés sont testées.
    """
    if on_missing not in ("raise", "drop"):
        raise ValueError(f"on_missing vaut « {on_missing} », attendu « raise » ou « drop »")
    if not isinstance(raw, pd.DataFrame):
        raise TypeError(f"un DataFrame est attendu, reçu {type(raw).__name__}")
    if raw.empty or len(raw.columns) == 0:
        raise InsufficientDataError("la réponse de yfinance ne porte aucune ligne exploitable")

    requested = _as_symbol_tuple(tickers)
    dates = _dates_from_index(raw.index, interval=interval)
    by_symbol = _split_by_symbol(raw, requested=requested)

    parts: list[pd.DataFrame] = []
    empty_symbols: list[str] = []
    for symbol, sub in by_symbol.items():
        columns: dict[str, Any] = {"date": dates, "symbol": symbol}
        for column in ("open", "high", "low", "close"):
            columns[column] = sub[column].to_numpy(dtype="float64") if column in sub else float("nan")
        columns["adj_close"] = (
            sub["adj_close"].to_numpy(dtype="float64")
            if "adj_close" in sub
            else columns["close"]  # auto_adjust=True : le close rendu est déjà ajusté.
        )
        columns["volume"] = sub["volume"].to_numpy(dtype="float64") if "volume" in sub else float("nan")
        part = pd.DataFrame(columns)
        part = part[~part[list(VALUE_FIELDS)].isna().all(axis=1)]
        if part.empty:
            empty_symbols.append(symbol)
            continue
        parts.append(part)

    missing = sorted(set(requested) - set(by_symbol)) + sorted(empty_symbols)
    if missing:
        message = f"aucune donnée rendue par Yahoo pour {missing}"
        if on_missing == "raise":
            raise DataQualityError(message)
        log.warning("titres sans données, retirés", extra={"symbols": missing, "provider": PROVIDER_NAME})

    if not parts:
        raise InsufficientDataError("aucune barre exploitable après retrait des lignes vides")

    out = pd.concat(parts, ignore_index=True)

    duplicated = out.duplicated(subset=["date", "symbol"], keep=False)
    if bool(duplicated.any()):
        offenders = out.loc[duplicated, ["date", "symbol"]].drop_duplicates().head(5)
        raise DataQualityError(
            f"{int(duplicated.sum())} lignes portent un couple (date, symbole) déjà vu ; "
            f"premiers cas : {offenders.to_dict(orient='records')}"
        )

    if check_ohlc:
        broken = out["high"] < out["low"]
        if bool(broken.any()):
            offenders = out.loc[broken, ["date", "symbol", "high", "low"]].head(5)
            raise DataQualityError(
                f"{int(broken.sum())} barres ont un plus haut sous leur plus bas ; "
                f"premiers cas : {offenders.to_dict(orient='records')}"
            )

    out = out.sort_values(["date", "symbol"], kind="stable", ignore_index=True)
    return out[list(SCHEMA)].astype(DTYPES)


def to_wide(df: pd.DataFrame, field: str = "adj_close") -> pd.DataFrame:
    """Rend un tableau dates fois symboles à partir du tableau long.

    **Le problème.** Une matrice de covariance, une régression et un
    rééquilibrage lisent tous une matrice dates fois actifs. Le format long ne
    la donne pas directement, et la conversion est le seul endroit où un
    décalage d'alignement peut naître.

    **L'intuition.** Chaque titre devient une colonne, indexée par sa propre
    date. L'assemblage aligne sur l'union des dates, donc un titre qui n'a pas
    coté ce jour-là porte une valeur absente au lieu de décaler ses voisins.
    C'est ce décalage, et non la valeur absente, qui produit des rendements
    faux.

    .. math::

        W_{t,s} = x_{t,s} \\quad \\text{si } (t, s) \\text{ existe},
        \\qquad \\mathrm{NaN} \\text{ sinon}

    où :math:`W` est la matrice rendue, :math:`t` une date, :math:`s` un titre,
    et :math:`x` la colonne demandée du tableau long.

    **Les hypothèses.** Une seule, et elle est contrôlée : le couple date et
    titre est unique. Sans elle, une valeur en écraserait une autre en silence.

    **La provenance.** Aucune : c'est une transposition, pas une méthode. Le
    passage long vers large est le ``pivot`` de Wickham (2014).

    **Les limites.** La matrice rendue porte des valeurs absentes dès qu'un
    titre a un calendrier différent des autres, cas fréquent entre deux places.
    Les combler est une décision méthodologique, elle appartient à la couche
    *silver* et jamais à cette fonction.

    **Les alternatives.** ``DataFrame.pivot`` fait la même chose en une ligne.
    L'assemblage colonne par colonne est retenu ici parce qu'il rend un ordre de
    colonnes déterministe, alphabétique, quel que soit l'ordre d'arrivée des
    lignes.

    **Pourquoi ici.** Les bibliothèques d'analyse du laboratoire, ``statsmodels``,
    ``arch`` et ``skfolio``, prennent toutes une matrice dates fois actifs. La
    conversion se fait une fois, à cet endroit.

    Args:
        df: un tableau long au schéma :data:`SCHEMA`.
        field: la colonne de valeur à répandre, ``adj_close`` par défaut parce
            que c'est la seule qui porte les dividendes et les divisions.

    Returns:
        Un tableau d'index ``DatetimeIndex`` trié et nommé « date », de colonnes
        triées par ordre alphabétique et nommées « symbol », en float64.

    Raises:
        ValueError: si ``field`` n'est pas une colonne de valeur du tableau.
        DataQualityError: si un couple date et titre apparaît deux fois.
        InsufficientDataError: si le tableau est vide.

    Example:
        Deux titres sur trois séances rendent une matrice de trois lignes et
        deux colonnes.

    Note:
        Comment vérifier que l'implémentation est correcte. Pour toute ligne du
        tableau long, la cellule ``wide.at[date, symbol]`` égale la valeur de
        cette ligne, à l'identique et sans tolérance. Le test le vérifie sur des
        données engendrées au hasard.
    """
    if field not in VALUE_FIELDS:
        raise ValueError(f"« {field} » n'est pas un champ de valeur ; attendus : {list(VALUE_FIELDS)}")
    absent = [column for column in ("date", "symbol", field) if column not in df.columns]
    if absent:
        raise ValueError(f"colonnes absentes du tableau long : {absent}")
    if df.empty:
        raise InsufficientDataError("le tableau long est vide, aucune matrice à construire")

    duplicated = df.duplicated(subset=["date", "symbol"], keep=False)
    if bool(duplicated.any()):
        offenders = df.loc[duplicated, ["date", "symbol"]].drop_duplicates().head(5)
        raise DataQualityError(
            f"{int(duplicated.sum())} lignes portent un couple (date, symbole) déjà vu ; "
            f"premiers cas : {offenders.to_dict(orient='records')}"
        )

    columns = {
        str(symbol): pd.Series(
            part[field].to_numpy(dtype="float64"),
            index=pd.DatetimeIndex(part["date"]),
        )
        for symbol, part in df.groupby("symbol", sort=True)
    }
    wide = pd.DataFrame(columns).sort_index()
    wide.index = pd.DatetimeIndex(wide.index, name="date")
    wide.columns.name = "symbol"
    return wide


class YahooProvider(BaseProvider):
    """Télécharge des barres chez Yahoo Finance et déclare ce qu'elles valent.

    La classe ne fait que deux choses : appeler ``yfinance.download`` avec des
    arguments explicites, et rendre le manifeste de ce qui vient d'arriver. La
    mise en forme appartient à :func:`normalize`, qui est pure et se teste sans
    réseau.

    Le socle :class:`~quantlab.data.providers.base.BaseProvider` apporte le
    cache brut et le client HTTP. Ce fournisseur ne s'en sert pas pour
    télécharger, yfinance tenant sa propre session, mais il en hérite le contrat
    et le dossier de cache nommé par ``name``.

    Attributes:
        name: « yahoo », le nom qui apparaît dans une ``DataConfig`` et qui
            nomme le dossier de cache brut du socle.

    Example:
        .. code-block:: python

            provider = YahooProvider()
            prices = provider.fetch("SPY", start="2024-01-02", end="2024-01-31")
            provider.manifest().survivorship_free  # False, toujours
    """

    name: ClassVar[str] = PROVIDER_NAME

    def __init__(
        self,
        *,
        on_missing: MissingPolicy = "raise",
        timeout_s: float = 30.0,
        max_retries: int | None = None,
        retry_delay_s: float | None = None,
        threads: bool = False,
        **base_kwargs: Any,
    ) -> None:
        """Construit le fournisseur.

        Args:
            on_missing: politique appliquée à un titre que Yahoo ne rend pas,
                « raise » par défaut.
            timeout_s: délai maximal d'une requête, en secondes.
            max_retries: nombre de TENTATIVES de téléchargement, la première
                comprise, donc trois valent deux relances. Sans valeur, le
                réglage d'environnement ``QUANTLAB_MAX_RETRIES`` décide, qui
                vaut 3 par défaut. Une valeur sous 1 est ramenée à 1 : refuser
                d'appeler la source serait un silence, pas une prudence.
            retry_delay_s: pause entre deux relances, en secondes. Sans valeur,
                ``QUANTLAB_REQUEST_DELAY_S`` décide.
            threads: parallélisme de yfinance. Faux par défaut, parce que le
                mode parallèle rend l'ordre des messages d'erreur non
                déterministe, ce qui gêne le diagnostic pour un gain nul sur les
                univers de quelques dizaines de titres.
            **base_kwargs: les arguments du socle commun, ``client``,
                ``raw_root`` et ``now``. Les tests y passent un ``tmp_path``.
        """
        super().__init__(**base_kwargs)
        settings = get_settings()
        self.on_missing: MissingPolicy = on_missing
        self.timeout_s = float(timeout_s)
        self.max_retries = int(settings.max_retries if max_retries is None else max_retries)
        self.retry_delay_s = float(settings.request_delay_s if retry_delay_s is None else retry_delay_s)
        self.threads = bool(threads)
        self._last: dict[str, Any] | None = None

    def fetch(
        self,
        tickers: Sequence[str] | str | None = None,
        *,
        start: dt.date | str,
        end: dt.date | str,
        interval: str = "1d",
        auto_adjust: bool = True,
        end_inclusive: bool = True,
        on_missing: MissingPolicy | None = None,
    ) -> pd.DataFrame:
        """Télécharge les barres demandées et les rend au schéma :data:`SCHEMA`.

        Args:
            tickers: un identifiant ou une suite d'identifiants Yahoo. Sans
                valeur, l'appel lève : l'argument n'est facultatif que pour
                rester compatible avec la signature du socle, qui n'attend que
                ``start`` et ``end``.
            start: première date, incluse.
            end: dernière date. Incluse quand ``end_inclusive`` vaut vrai.
            interval: le pas de temps, « 1d » par défaut.
            auto_adjust: vrai, Yahoo rend des prix déjà corrigés des dividendes
                et des divisions, et ``adj_close`` recopie ``close``. Faux, les
                deux colonnes diffèrent.
            end_inclusive: mesuré le 2026-09-01 avec yfinance 1.7.0, une requête
                bornée au 2024-01-09 rend le 2024-01-08 pour dernière séance
                alors que le 9 était ouvert : Yahoo exclut sa borne haute. Vrai,
                l'argument ajoute un jour avant l'appel pour que la borne
                demandée soit réellement incluse.
            on_missing: politique de titre manquant pour cet appel seulement.

        Returns:
            Le tableau long, trié, au schéma fixe. Son empreinte SHA-256 est
            calculée au passage et entre dans le manifeste, ce qui rattache le
            manifeste à cette table précise et à aucune autre.

        Raises:
            ValueError: si ``start`` ne précède pas ``end``.
            DataQualityError: si la donnée reçue viole le schéma.
            InsufficientDataError: si Yahoo ne rend aucune ligne.

        Note:
            L'import de ``yfinance`` est local à la méthode : la dépendance est
            facultative, déclarée dans l'extra « data » du projet, et le module
            reste importable sans elle.
        """
        import yfinance as yf

        symbols = _as_symbol_tuple(tickers)
        if not symbols:
            raise ValueError("aucun identifiant demandé")
        start_date, end_date = _as_date(start), _as_date(end)
        if start_date >= end_date:
            raise ValueError(f"start ({start_date}) doit précéder end ({end_date})")
        query_end = end_date + dt.timedelta(days=1) if end_inclusive else end_date

        with stage(
            "yahoo.fetch",
            provider=self.name,
            symbols=len(symbols),
            interval=interval,
            start=start_date.isoformat(),
            end=end_date.isoformat(),
        ) as payload:
            raw = self._download(
                yf,
                symbols=symbols,
                start=start_date,
                end=query_end,
                interval=interval,
                auto_adjust=auto_adjust,
            )
            frame = normalize(
                raw,
                tickers=symbols,
                interval=interval,
                on_missing=self.on_missing if on_missing is None else on_missing,
            )
            payload["rows"] = len(frame)

        self._last = {
            "checksum": sha256_frame(frame),
            "symbols": symbols,
            "start": start_date,
            "end": end_date,
            "interval": interval,
            "rows": len(frame),
            "auto_adjust": auto_adjust,
            "retrieved_at": dt.datetime.now(dt.UTC),
        }
        return frame

    def _download(
        self,
        yf: Any,
        *,
        symbols: tuple[str, ...],
        start: dt.date,
        end: dt.date,
        interval: str,
        auto_adjust: bool,
    ) -> pd.DataFrame:
        """Appelle ``yfinance.download`` et relance sur erreur réseau transitoire.

        Les arguments passés sont ceux de la signature mesurée de yfinance 1.7.0
        le 2026-09-01. Aucun n'est deviné.

        Le nombre de tentatives est ramené à 1 au minimum. Sans ce plancher, un
        ``max_retries`` nul ferait sortir la boucle sans avoir appelé Yahoo, et
        l'erreur rendue parlerait d'une source muette là où personne ne l'avait
        interrogée.
        """
        last_error: Exception | None = None
        attempts = max(1, self.max_retries)
        for attempt in range(1, attempts + 1):
            try:
                return yf.download(
                    tickers=list(symbols),
                    start=start.isoformat(),
                    end=end.isoformat(),
                    interval=interval,
                    auto_adjust=auto_adjust,
                    group_by="column",
                    progress=False,
                    threads=self.threads,
                    actions=False,
                    multi_level_index=True,
                    timeout=self.timeout_s,
                )
            except Exception as exc:  # La relance vaut pour toute erreur réseau, quelle qu'elle soit.
                last_error = exc
                log.warning(
                    "téléchargement Yahoo échoué, relance",
                    extra={"attempt": attempt, "attempts": attempts, "error": repr(exc)},
                )
                if attempt < attempts:
                    time.sleep(self.retry_delay_s)
        raise DataQualityError(f"Yahoo n'a pas répondu après {attempts} tentatives : {last_error!r}")

    def manifest(self, **overrides: Any) -> DatasetManifest:
        """Rend le manifeste de la dernière extraction, ou celui qu'on décrit.

        Trois champs comptent plus que les autres, et ce fournisseur les remplit
        sans nuance. ``survivorship_free`` vaut faux : Yahoo ne rend que des
        titres vivants. ``point_in_time`` vaut faux : rien n'indique ce que la
        source disait à une date passée. ``adjusted`` vaut vrai : la colonne
        ``adj_close`` est toujours remplie, par la colonne « Adj Close » quand
        ``auto_adjust`` est faux, par le ``close`` déjà corrigé sinon.

        Deux champs restent vides, et c'est délibéré. ``currency`` n'est pas
        mesuré, Yahoo rendant les prix dans la devise de cotation sans la
        nommer dans la réponse de ``download``. ``license_url`` n'est pas
        rempli : l'adresse des conditions d'utilisation n'a pas été vérifiée, et
        une adresse plausible vaut moins que rien dans un manifeste.

        Args:
            **overrides: décrit une extraction sans en avoir faite une, ou
                corrige un champ de la dernière. Clés acceptées : ``symbols``,
                ``start``, ``end``, ``interval``, ``rows``, ``adjusted``,
                ``auto_adjust``, ``dataset_id`` et ``checksum``.

        Returns:
            Le manifeste commun du laboratoire, gelé, de couche
            :attr:`~quantlab.core.paths.Layer.BRONZE` : les colonnes sont
            nommées et typées, et aucune décision financière n'a été prise.

        Raises:
            ValueError: si une clé de remplacement est inconnue.
            ConfigError: si aucun téléchargement n'a eu lieu et que les clés
                ``symbols``, ``start`` et ``end`` manquent. Levée aussi quand
                l'intervalle demandé n'est pas une clé de
                :data:`INTERVAL_TO_FREQUENCY`, ce qui vise les pas
                intrajournaliers et « 5d ».
        """
        unknown = sorted(set(overrides) - _MANIFEST_KEYS)
        if unknown:
            raise ValueError(
                f"clés de manifeste inconnues : {unknown} ; acceptées : {sorted(_MANIFEST_KEYS)}"
            )

        base: dict[str, Any] = dict(self._last or {})
        base.update(overrides)
        for required in ("symbols", "start", "end"):
            if required not in base:
                raise ConfigError(
                    "le manifeste exige un téléchargement préalable, ou les clés symbols, start et end"
                )

        symbols = _as_symbol_tuple(base["symbols"])
        start_date, end_date = _as_date(base["start"]), _as_date(base["end"])
        interval = str(base.get("interval", "1d"))
        frequency = INTERVAL_TO_FREQUENCY.get(interval)
        if frequency is None:
            raise ConfigError(
                f"l'intervalle « {interval} » n'a pas d'équivalent dans Frequency ; "
                f"intervalles couverts : {sorted(INTERVAL_TO_FREQUENCY)}. Deux familles sont "
                "hors couverture, les pas intrajournaliers, que Frequency ne descend pas voir, "
                "et « 5d », dont les cinq séances ne tombent sur aucune période nommée"
            )
        auto_adjust = bool(base.get("auto_adjust", True))

        return DatasetManifest(
            dataset_id=str(base.get("dataset_id") or _dataset_id(symbols, interval, start_date, end_date)),
            source=SOURCE_NAME,
            provider=self.name,
            url=SOURCE_URL,
            download_timestamp=base.get("retrieved_at") or dt.datetime.now(dt.UTC),
            data_start=start_date,
            data_end=end_date,
            frequency=frequency,
            adjusted=bool(base.get("adjusted", True)),
            point_in_time=False,
            survivorship_free=False,
            corporate_actions=CORPORATE_ACTIONS_AUTO if auto_adjust else CORPORATE_ACTIONS_MANUAL,
            revision_policy=REVISION_POLICY,
            license=LICENSE,
            checksum_sha256=str(base.get("checksum", "")),
            n_rows=int(base.get("rows", 0)),
            n_columns=len(SCHEMA),
            columns=SCHEMA,
            processing_version=PROCESSING_VERSION,
            layer=Layer.BRONZE,
            notes=" ".join(KNOWN_LIMITATIONS),
        )

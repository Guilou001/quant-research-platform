"""La bibliothèque de Kenneth French, et l'analyse de ses fichiers plats.

**Le problème.** Les facteurs de Fama et French sont la référence de tout test
d'anomalie, et ils sont publiés dans des fichiers texte dont le format n'a pas
bougé depuis vingt ans. Un en-tête en prose, plusieurs tableaux empilés dans le
même fichier, des dates écrites sans séparateur, des valeurs exprimées en
pourcentage, des manquants codés par un nombre. Un lecteur pressé y perd le
deuxième tableau, garde le code ``-99.99`` pour un rendement de moins 99 %, et
raisonne ensuite sur des pourcentages qu'il croit décimaux. Les trois fautes se
composent, et aucune ne lève d'exception.

**Le remède.** L'analyse syntaxique vit ici, dans une fonction pure et testée
hors réseau, séparée du téléchargement. :func:`parse_french_csv` prend le texte
et rend des tableaux nommés, datés, en décimales, avec leurs manquants en
``NaN``. Le fournisseur :class:`FrenchProvider` ne fait que chercher les octets,
les mettre en cache et appeler cette fonction.

**Ce que le fichier contient réellement.** Mesuré le 2026-09-01 sur cinq
archives de la bibliothèque, millésime CRSP 202606 :

- ``F-F_Research_Data_Factors.CSV`` porte deux tableaux, les rendements
  mensuels de 192607 à 202606 puis les rendements annuels de 1927 à 2025,
  séparés par une ligne vide et le titre « Annual Factors: January-December » ;
- ``F-F_Research_Data_Factors_daily.CSV`` porte un seul tableau, du 19260701 au
  20260630, et son archive pèse 177 852 octets ;
- ``25_Portfolios_5x5.CSV`` porte dix tableaux, dont six qui ne sont PAS des
  pourcentages. Ce sont « Number of Firms in Portfolios », « Average Market
  Cap », et les quatre tableaux de ratios titrés « For portfolios formed in
  June of year t » ;
- le titre d'un tableau tient parfois sur deux lignes, ainsi « Annual Factors: »
  puis « January-December » dans le fichier de momentum mensuel ;
- les fins de ligne sont des CRLF, et le fichier se termine par la mention de
  droit d'auteur.

**Provenance et licence.** Fama, E. F. et French, K. R. (1993), « Common risk
factors in the returns on stocks and bonds », *Journal of Financial Economics*
33(1), 3-56, et Fama et French (2015), « A five-factor asset pricing model »,
*JFE* 116(1), 1-22. Les données sont diffusées par Kenneth R. French pour un
usage académique, la citation étant demandée. Elles sont construites sur CRSP,
donc exemptes de biais du survivant, et révisées rétroactivement à chaque
millésime de CRSP, donc non point-in-time.

Exemple :

.. code-block:: python

    provider = FrenchProvider()
    tables = provider.fetch_tables("F-F_Research_Data_Factors")
    mensuel = tables["monthly"]
    annuel = tables["annual_factors_january_december"]
"""

from __future__ import annotations

import datetime as dt
import io
import re
import zipfile
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, ClassVar, Final, Literal

import numpy as np
import pandas as pd

from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.logging import get_logger
from quantlab.core.paths import Layer
from quantlab.core.types import Frequency
from quantlab.data.manifest import DatasetManifest
from quantlab.data.providers.base import BaseProvider, HttpClient, RawResponse

log = get_logger(__name__)

#: Racine des archives de la bibliothèque. Mesurée le 2026-09-01 : les onze
#: fichiers de :func:`available_datasets` répondent 200 sur cette racine.
BASE_URL: Final[str] = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"

#: Suffixe des archives. La bibliothèque publie aussi des fichiers TXT, non
#: retenus ici : leur format est celui du CSV sans les virgules, donc plus
#: fragile à découper.
ARCHIVE_SUFFIX: Final[str] = "_CSV.zip"

#: Les codes de manquant, écrits noir sur blanc dans l'en-tête des fichiers de
#: portefeuilles : « Missing data are indicated by -99.99 or -999. » (rapporté,
#: lu le 2026-09-01 dans « 6_Portfolios_2x3.CSV », ligne 8).
MISSING_CODES: Final[tuple[float, ...]] = (-99.99, -999.0)

#: Diviseur qui fait passer du pourcentage à la décimale. Les fichiers publient
#: 0,97 pour un rendement mensuel de 0,97 %, soit 0,0097 en décimales.
PERCENT_DIVISOR: Final[float] = 100.0

#: Mots qui, dans le titre d'un tableau, signalent des pourcentages. Un tableau
#: sans titre est un tableau de rendements dans tous les fichiers mesurés.
PERCENT_TITLE_KEYWORDS: Final[tuple[str, ...]] = ("return", "factor")

#: Licence déclarée dans le manifeste.
LICENSE: Final[str] = (
    "usage académique, citation demandée ; données de Kenneth R. French, "
    "copyright Eugene F. Fama et Kenneth R. French"
)

#: Les colonnes rendues par :meth:`FrenchProvider.benchmark_factors`, dans cet
#: ordre.
BENCHMARK_COLUMNS: Final[tuple[str, ...]] = ("MKT-RF", "SMB", "HML", "RMW", "CMA", "MOM", "RF")

#: Jeu utilisé par défaut quand l'appelant n'en nomme aucun.
DEFAULT_DATASET: Final[str] = "F-F_Research_Data_Factors_daily"

_NON_WORD = re.compile(r"[^0-9a-z]+")
_DATE_LENGTHS: Final[tuple[int, ...]] = (4, 6, 8)


@dataclass(frozen=True, slots=True)
class FrenchDatasetSpec:
    """La fiche d'un fichier de la bibliothèque.

    Attributes:
        name: le nom du fichier sans le suffixe « _CSV.zip ».
        frequency: la fréquence du tableau principal.
        description: ce que le fichier contient, en une phrase.
        columns: les colonnes de facteurs attendues, vide pour les fichiers de
            portefeuilles dont les colonnes sont les portefeuilles eux-mêmes.
        archive_bytes: la taille de l'archive mesurée le 2026-09-01, ou ``None``
            si elle n'a pas été mesurée. Elle sert de contrôle grossier, pas de
            somme de contrôle.
    """

    name: str
    frequency: Frequency
    description: str
    columns: tuple[str, ...] = ()
    archive_bytes: int | None = None


_DATASETS: Final[Mapping[str, FrenchDatasetSpec]] = MappingProxyType(
    {
        spec.name: spec
        for spec in (
            FrenchDatasetSpec(
                name="F-F_Research_Data_Factors",
                frequency=Frequency.MONTHLY,
                description="Les trois facteurs de Fama et French (1993), mensuels puis annuels.",
                columns=("MKT-RF", "SMB", "HML", "RF"),
                archive_bytes=13052,
            ),
            FrenchDatasetSpec(
                name="F-F_Research_Data_Factors_daily",
                frequency=Frequency.DAILY,
                description="Les trois facteurs de Fama et French (1993), quotidiens.",
                columns=("MKT-RF", "SMB", "HML", "RF"),
                archive_bytes=177852,
            ),
            FrenchDatasetSpec(
                name="F-F_Research_Data_Factors_weekly",
                frequency=Frequency.WEEKLY,
                description="Les trois facteurs de Fama et French (1993), hebdomadaires.",
                columns=("MKT-RF", "SMB", "HML", "RF"),
                archive_bytes=42925,
            ),
            FrenchDatasetSpec(
                name="F-F_Research_Data_5_Factors_2x3",
                frequency=Frequency.MONTHLY,
                description="Les cinq facteurs de Fama et French (2015), mensuels puis annuels.",
                columns=("MKT-RF", "SMB", "HML", "RMW", "CMA", "RF"),
                archive_bytes=11901,
            ),
            FrenchDatasetSpec(
                name="F-F_Research_Data_5_Factors_2x3_daily",
                frequency=Frequency.DAILY,
                description="Les cinq facteurs de Fama et French (2015), quotidiens.",
                columns=("MKT-RF", "SMB", "HML", "RMW", "CMA", "RF"),
                archive_bytes=149894,
            ),
            FrenchDatasetSpec(
                name="F-F_Momentum_Factor",
                frequency=Frequency.MONTHLY,
                description="Le facteur de momentum de Carhart (1997), mensuel puis annuel.",
                columns=("MOM",),
                archive_bytes=5610,
            ),
            FrenchDatasetSpec(
                name="F-F_Momentum_Factor_daily",
                frequency=Frequency.DAILY,
                description="Le facteur de momentum de Carhart (1997), quotidien.",
                columns=("MOM",),
                archive_bytes=85139,
            ),
            FrenchDatasetSpec(
                name="25_Portfolios_5x5",
                frequency=Frequency.MONTHLY,
                description=(
                    "Les 25 portefeuilles triés par taille et par ratio comptable sur marché, "
                    "mensuels, avec le nombre de sociétés et la capitalisation moyenne."
                ),
                archive_bytes=548060,
            ),
            FrenchDatasetSpec(
                name="25_Portfolios_5x5_Daily",
                frequency=Frequency.DAILY,
                description=(
                    "Les 25 portefeuilles triés par taille et par ratio comptable sur marché, quotidiens."
                ),
                archive_bytes=4032594,
            ),
            FrenchDatasetSpec(
                name="6_Portfolios_2x3",
                frequency=Frequency.MONTHLY,
                description=(
                    "Les six portefeuilles taille sur ratio comptable qui construisent SMB et HML, mensuels."
                ),
                archive_bytes=149079,
            ),
            FrenchDatasetSpec(
                name="6_Portfolios_2x3_daily",
                frequency=Frequency.DAILY,
                description=(
                    "Les six portefeuilles taille sur ratio comptable qui construisent SMB et HML, "
                    "quotidiens."
                ),
                archive_bytes=1132480,
            ),
        )
    }
)


def available_datasets() -> Mapping[str, FrenchDatasetSpec]:
    """Rend les fichiers de la bibliothèque que ce module sait nommer.

    Returns:
        Un dictionnaire en lecture seule, du nom de fichier vers sa fiche.

    Note:
        Les onze noms répondent 200 sur la racine :data:`BASE_URL`, mesuré le
        2026-09-01. La bibliothèque en publie plusieurs centaines d'autres, tous
        lisibles par :func:`parse_french_csv` : cette table ne borne pas
        l'analyse, elle documente les jeux dont le laboratoire se sert.
    """
    return _DATASETS


@dataclass(frozen=True, eq=False)
class FrenchBlock:
    """Un tableau d'un fichier de la bibliothèque, daté et mis à l'échelle.

    Attributes:
        name: le nom court, dérivé du titre ou, à défaut, de la fréquence.
        title: le titre tel qu'il est écrit dans le fichier, lignes jointes par
            un espace. Vide pour le premier tableau des fichiers de facteurs.
        frequency: la fréquence déduite des dates du tableau.
        in_percent: vrai si les valeurs publiées étaient des pourcentages, donc
            si elles ont été divisées par 100.
        frame: les données, indexées par un ``DatetimeIndex`` nommé « date ».
        first_line: le numéro de la ligne d'en-tête dans le fichier, à partir
            de 1, pour retrouver le tableau à l'œil.
    """

    name: str
    title: str
    frequency: Frequency
    in_percent: bool
    frame: pd.DataFrame
    first_line: int


@dataclass(frozen=True, eq=False)
class ParsedFrenchFile:
    """Le contenu complet d'un fichier de la bibliothèque, une fois analysé.

    Attributes:
        preamble: le texte libre qui précède le premier tableau.
        trailer: le texte libre qui suit le dernier tableau, la mention de droit
            d'auteur en pratique.
        blocks: les tableaux, dans l'ordre du fichier.
    """

    preamble: str
    trailer: str
    blocks: tuple[FrenchBlock, ...] = ()

    @property
    def tables(self) -> dict[str, pd.DataFrame]:
        """Rend les tableaux par leur nom court."""
        return {block.name: block.frame for block in self.blocks}

    @property
    def names(self) -> tuple[str, ...]:
        """Rend les noms des tableaux, dans l'ordre du fichier."""
        return tuple(block.name for block in self.blocks)

    def block(self, name: str) -> FrenchBlock:
        """Rend un tableau avec sa fiche, ou lève une ``KeyError`` explicite.

        Args:
            name: le nom court du tableau.

        Returns:
            Le tableau, sa fréquence et son titre.

        Raises:
            KeyError: si aucun tableau ne porte ce nom.
        """
        for block in self.blocks:
            if block.name == name:
                return block
        raise KeyError(f"tableau « {name} » absent ; disponibles : {', '.join(self.names)}")

    def __getitem__(self, name: str) -> pd.DataFrame:
        """Rend les données d'un tableau par son nom."""
        return self.block(name).frame

    def __iter__(self) -> Iterator[FrenchBlock]:
        """Parcourt les tableaux dans l'ordre du fichier."""
        return iter(self.blocks)

    def __len__(self) -> int:
        """Rend le nombre de tableaux."""
        return len(self.blocks)

    @property
    def primary(self) -> pd.DataFrame:
        """Rend le premier tableau, celui que l'appelant veut neuf fois sur dix.

        Raises:
            InsufficientDataError: si le fichier ne porte aucun tableau.
        """
        if not self.blocks:
            raise InsufficientDataError("le fichier ne porte aucun tableau exploitable")
        return self.blocks[0].frame


@dataclass(slots=True)
class _RawBlock:
    """Un tableau encore en texte : son titre, ses colonnes, ses lignes."""

    title: str
    columns: tuple[str, ...]
    first_line: int
    rows: list[list[str]] = field(default_factory=list)


def _slugify(text: str, max_words: int) -> str:
    """Rend un nom court en minuscules à partir d'un titre libre.

    Args:
        text: le titre, éventuellement sur plusieurs lignes déjà jointes.
        max_words: le nombre de mots gardés, pour éviter des noms de trois
            lignes dans les fichiers de portefeuilles.

    Returns:
        Les mots retenus joints par des soulignés, ou une chaîne vide.

    Example:
        « Annual Factors: January-December » donne
        ``annual_factors_january_december``.
    """
    words = _NON_WORD.sub(" ", text.lower()).split()
    return "_".join(words[:max_words])


def _is_date_token(token: str) -> bool:
    """Dit si un jeton est une date de la bibliothèque : 4, 6 ou 8 chiffres."""
    return token.isdigit() and len(token) in _DATE_LENGTHS


def _split_blocks(lines: Sequence[str]) -> tuple[str, str, list[_RawBlock]]:
    """Découpe le fichier en préambule, tableaux bruts et texte de fin.

    La règle de découpage tient en quatre cas, et elle est mécanique. Une ligne
    dont le premier champ est vide ouvre un tableau : c'est l'en-tête de
    colonnes. Une ligne dont le premier champ est une date alimente le tableau
    courant. Une ligne vide ferme le tableau courant et solde le texte en
    attente. Toute autre ligne est du texte en attente.

    Le titre d'un tableau est le bloc de lignes de texte qui le précède
    IMMÉDIATEMENT, sans ligne vide entre les deux. Cette règle sépare deux
    choses que l'œil confond. Le préambule du fichier est détaché du premier
    tableau par une ligne vide. Le titre « Average Value Weighted Returns --
    Monthly » colle à son en-tête dans les fichiers de portefeuilles.

    Args:
        lines: les lignes du fichier, retours chariot déjà retirés.

    Returns:
        Le préambule, le texte de fin, et la liste des tableaux bruts.
    """
    preamble: list[str] = []
    trailer: list[str] = []
    pending: list[str] = []
    blocks: list[_RawBlock] = []
    current: _RawBlock | None = None

    def _solder() -> None:
        """Verse le texte en attente au préambule, ou au texte de fin."""
        if pending:
            (trailer if blocks else preamble).extend(pending)
            pending.clear()

    for lineno, line in enumerate(lines, start=1):
        if not line.strip():
            current = None
            _solder()
            continue
        fields = [item.strip() for item in line.split(",")]
        if len(fields) > 1 and fields[0] == "":
            current = _RawBlock(
                title=" ".join(pending).strip(),
                columns=tuple(fields[1:]),
                first_line=lineno,
            )
            pending.clear()
            blocks.append(current)
            continue
        if _is_date_token(fields[0]):
            if current is None:
                current = _RawBlock(
                    title=" ".join(pending).strip(),
                    columns=tuple(f"V{i}" for i in range(1, len(fields))),
                    first_line=lineno,
                )
                pending.clear()
                blocks.append(current)
                log.warning(
                    "tableau sans en-tête de colonnes, noms générés",
                    extra={"line": lineno, "columns": len(fields) - 1},
                )
            current.rows.append(fields)
            continue
        current = None
        pending.append(line.strip())

    _solder()
    return "\n".join(preamble), "\n".join(trailer), blocks


def _build_index(
    tokens: Sequence[str],
    *,
    date_position: Literal["end", "start"],
    weekly_gap_threshold_days: float,
    first_line: int,
) -> tuple[pd.DatetimeIndex, Frequency]:
    """Date un tableau et déduit sa fréquence de la forme de ses dates.

    **Le problème.** La bibliothèque écrit ``192607`` pour juillet 1926 et
    ``19260701`` pour le 1er juillet 1926. Le même fichier mêle les deux formes
    quand il empile un tableau mensuel et un tableau annuel.

    **La convention retenue.** Un rendement mensuel est daté à la FIN de la
    période qu'il décrit, ici le 31 juillet 1926, et un rendement annuel au
    31 décembre. C'est la convention du reste du laboratoire, où une série
    mensuelle s'aligne sur ``Frequency.MONTHLY.pandas_alias``, soit « ME ».
    Dater au début décalerait toute la série d'une période, et un facteur
    décalé d'un mois change le signe de la plupart des régressions.

    Args:
        tokens: les jetons de date, tous de même longueur.
        date_position: « end » pour la fin de période, « start » pour le début.
            L'argument ne change rien aux dates de huit chiffres, qui désignent
            déjà un jour et non une période.
        weekly_gap_threshold_days: au-dessus de cet écart médian entre deux
            dates de huit chiffres, le tableau est déclaré hebdomadaire. La
            bibliothèque publie du quotidien avec un écart médian de 1 jour et
            de l'hebdomadaire avec un écart de 7 jours, si bien que la frontière
            est large.
        first_line: le numéro de ligne du tableau, pour le message d'erreur.

    Returns:
        L'index daté, nommé « date », et la fréquence déduite.

    Raises:
        DataQualityError: si les jetons n'ont pas tous la même longueur, ou si
            leur longueur n'est ni 4, ni 6, ni 8.

    Note:
        Pour vérifier : ``192607`` doit rendre le 1926-07-31 en position « end »
        et le 1926-07-01 en position « start ».
    """
    lengths = {len(token) for token in tokens}
    if len(lengths) != 1:
        raise DataQualityError(f"tableau ligne {first_line} : dates de longueurs mêlées {sorted(lengths)}")
    width = lengths.pop()
    if width == 8:
        index = pd.to_datetime(list(tokens), format="%Y%m%d")
        frequency = Frequency.DAILY
        if len(index) > 1:
            gaps = np.diff(index.to_numpy()).astype("timedelta64[D]").astype(float)
            if float(np.median(gaps)) >= weekly_gap_threshold_days:
                frequency = Frequency.WEEKLY
    elif width == 6:
        starts = pd.to_datetime(list(tokens), format="%Y%m")
        index = starts + pd.offsets.MonthEnd(0) if date_position == "end" else starts
        frequency = Frequency.MONTHLY
    elif width == 4:
        starts = pd.to_datetime(list(tokens), format="%Y")
        index = starts + pd.offsets.YearEnd(0) if date_position == "end" else starts
        frequency = Frequency.ANNUAL
    else:  # pragma: no cover - _is_date_token filtre déjà les autres largeurs
        raise DataQualityError(f"tableau ligne {first_line} : largeur de date inattendue {width}")
    return pd.DatetimeIndex(index, name="date"), frequency


def _to_float(token: str, *, first_line: int, column: str) -> float:
    """Convertit un jeton en flottant, le vide devenant ``NaN``."""
    if token == "":
        return float("nan")
    try:
        return float(token)
    except ValueError as exc:
        raise DataQualityError(
            f"tableau ligne {first_line}, colonne « {column} » : « {token} » n'est pas un nombre"
        ) from exc


def _is_percent_block(title: str, keywords: Sequence[str]) -> bool:
    """Dit si les valeurs d'un tableau sont des pourcentages.

    **Pourquoi la question se pose.** Diviser tout par 100 est faux. Le fichier
    des 25 portefeuilles porte un tableau « Number of Firms in Portfolios », où
    7 est un nombre de sociétés. Il en porte un autre, « Average Market Cap », où
    2,71 est une capitalisation en millions de dollars. Les diviser rendrait 0,07
    société et 0,0271 million.

    **La règle.** Un tableau sans titre est en pourcentage, ce qui est le cas de
    tous les tableaux principaux des fichiers de facteurs. Un tableau titré est
    en pourcentage si son titre contient un des mots déclarés, « return » ou
    « factor » par défaut.

    Args:
        title: le titre du tableau, vide s'il n'en a pas.
        keywords: les mots qui signalent des pourcentages, en minuscules.

    Returns:
        Vrai si le tableau doit être divisé par 100.

    Note:
        Vérification : sur « 25_Portfolios_5x5.CSV », la règle rend vrai pour
        les quatre tableaux de rendements et faux pour les six autres, mesuré
        le 2026-09-01. Le fichier porte donc dix tableaux.
    """
    if not title:
        return True
    lowered = title.lower()
    return any(keyword in lowered for keyword in keywords)


def _apply_missing_codes(
    values: np.ndarray,
    missing_codes: Sequence[float],
    tolerance: float,
) -> np.ndarray:
    """Remplace les codes de manquant par ``NaN``, avant toute mise à l'échelle.

    L'ordre compte, et c'est l'erreur classique. Divisé d'abord, ``-99.99``
    devient ``-0.9999`` et passe pour une perte de 99,99 %, parfaitement
    plausible sur un portefeuille de petites sociétés en 1932. Remplacé
    d'abord, il devient ``NaN`` et se voit.

    Args:
        values: le tableau de valeurs, tel qu'il est écrit dans le fichier.
        missing_codes: les codes à traiter comme manquants.
        tolerance: l'écart absolu toléré pour reconnaître un code. Les fichiers
            écrivent parfois « -999 » et parfois « -999.00 », qui donnent le
            même flottant, si bien qu'une comparaison exacte suffirait ; la
            tolérance protège des millésimes qui écriraient « -99.990 ».

    Returns:
        Une copie où les codes reconnus valent ``NaN``.
    """
    cleaned = values.astype(float, copy=True)
    for code in missing_codes:
        cleaned[np.isclose(cleaned, code, rtol=0.0, atol=tolerance)] = np.nan
    return cleaned


def parse_french_csv(
    text: str,
    *,
    missing_codes: Sequence[float] = MISSING_CODES,
    missing_tolerance: float = 1e-9,
    percent_divisor: float = PERCENT_DIVISOR,
    percent_keywords: Sequence[str] = PERCENT_TITLE_KEYWORDS,
    date_position: Literal["end", "start"] = "end",
    max_name_words: int = 8,
    weekly_gap_threshold_days: float = 4.0,
    uppercase_columns: bool = True,
) -> ParsedFrenchFile:
    """Analyse un fichier de la bibliothèque et rend ses tableaux nommés.

    **Le problème.** Le fichier n'est pas un CSV : c'est de la prose, puis
    plusieurs CSV empilés, séparés par des lignes vides et annoncés par des
    titres. ``pandas.read_csv`` en tire soit une erreur, soit un seul tableau
    tronqué au premier saut de ligne.

    **L'intuition.** Chaque ligne appartient à l'une de quatre catégories, et sa
    catégorie se lit sur son premier champ. Vide, c'est un en-tête de colonnes.
    Numérique de 4, 6 ou 8 chiffres, c'est une observation. Rien du tout, la
    ligne est vide et ferme le tableau. Sinon, c'est du texte.

    **La conversion de pourcentage.**

    .. math::

        r_{d\\acute{e}cimal} = \\frac{v_{fichier}}{100}

    où :math:`v_{fichier}` est la valeur écrite dans le fichier, en points de
    pourcentage, et :math:`r_{d\\acute{e}cimal}` le rendement en décimales. La
    bibliothèque écrit ``0.97`` pour 0,97 %, qui vaut 0,0097. La division n'est
    appliquée qu'aux tableaux reconnus comme des pourcentages par
    :func:`_is_percent_block`, et toujours APRÈS le remplacement des codes de
    manquant.

    Args:
        text: le contenu du fichier, déjà décodé.
        missing_codes: les valeurs qui signifient « manquant ».
        missing_tolerance: l'écart absolu toléré pour reconnaître un code.
        percent_divisor: le diviseur de la conversion, 100 par construction.
        percent_keywords: les mots d'un titre qui signalent des pourcentages.
        date_position: « end » pour dater à la fin de la période décrite.
        max_name_words: le nombre de mots gardés dans un nom de tableau.
        weekly_gap_threshold_days: la frontière entre quotidien et
            hebdomadaire, en jours d'écart médian.
        uppercase_columns: met les noms de colonnes en majuscules, ce qui rend
            « Mkt-RF » sous la forme « MKT-RF » et « Mom » sous « MOM ». Les
            fichiers changent la casse d'un millésime à l'autre, et un code qui
            dépend de la casse casse sans prévenir.

    Returns:
        Le fichier analysé : préambule, texte de fin, tableaux.

    Raises:
        DataQualityError: si un tableau porte des lignes de longueurs
            différentes, des dates mêlées, ou une valeur non numérique.

    Hypothèses:
        Les dates d'un même tableau ont toutes la même largeur, les colonnes
        sont séparées par des virgules, et les valeurs sont écrites en notation
        décimale anglaise. Les trois hypothèses tiennent sur les cinq fichiers
        mesurés le 2026-09-01.

    Limites:
        Les fichiers de portefeuilles portent plusieurs tableaux dont le titre
        commence par les mêmes mots, ainsi « For portfolios formed in June of
        year t ». Leurs noms courts entrent alors en collision et reçoivent un
        suffixe numérique ; le titre complet reste dans
        :attr:`FrenchBlock.title`.

        Le texte doit arriver sans traduction préalable des fins de ligne. Un
        appelant qui lit le fichier en mode texte universel voit ses retours
        chariot isolés changés en sauts de ligne, ce qui insère une ligne vide
        entre un titre et son en-tête. Un titre sur dix se perd alors, mesuré le
        2026-09-01 sur « 6_Portfolios_2x3.CSV ». La méthode
        :meth:`FrenchProvider.extract_text` décode les octets sans traduction,
        et c'est le chemin normal.

    Alternatives:
        Découper le fichier avec ``pandas.read_csv(skiprows=..., nrows=...)`` en
        codant les décalages en dur marche jusqu'au millésime suivant, où le
        nombre de lignes change. Chercher les tableaux par leur forme, comme
        ici, ne dépend d'aucun décalage.

    Example:
        >>> texte = ",Mkt-RF,RF\\n193609,   0.97,   0.01\\n"
        >>> parsed = parse_french_csv(texte)
        >>> float(parsed.primary.loc["1936-09-30", "MKT-RF"])
        0.0097

    Note:
        Pour vérifier l'implémentation, reprendre trois lignes littérales d'un
        fichier réel. Trois contrôles suffisent alors. La valeur 0,97 doit
        devenir 0,0097. Le code ``-99.99`` doit devenir ``NaN``, et surtout pas
        ``-0.9999``. Le tableau annuel du fichier mensuel doit ressortir comme
        un second tableau, et non se perdre.
    """
    # Les fichiers mêlent deux conventions de fin de ligne. La plupart des lignes
    # se terminent par CRLF, mais certaines portent un retour chariot isolé. Il
    # colle tantôt deux lignes de titre, et fabrique tantôt une ligne vide entre
    # un titre et son en-tête. Mesuré le 2026-09-01 dans « 6_Portfolios_2x3.CSV » :
    # quinze retours chariot isolés, aux lignes 2527, 5037, 6241, 7445 et 8205. Le
    # saut de ligne fait donc seul autorité, et le retour chariot est retiré partout.
    preamble, trailer, raw_blocks = _split_blocks(text.replace("\r", "").split("\n"))
    blocks: list[FrenchBlock] = []
    taken: dict[str, int] = {}

    for raw in raw_blocks:
        if not raw.rows:
            log.warning("tableau vide ignoré", extra={"line": raw.first_line, "title": raw.title})
            continue
        widths = {len(row) for row in raw.rows}
        expected = len(raw.columns) + 1
        if widths != {expected}:
            raise DataQualityError(
                f"tableau ligne {raw.first_line} : {expected} champs attendus, "
                f"largeurs rencontrées {sorted(widths)}"
            )
        index, frequency = _build_index(
            [row[0] for row in raw.rows],
            date_position=date_position,
            weekly_gap_threshold_days=weekly_gap_threshold_days,
            first_line=raw.first_line,
        )
        columns = [name.upper() if uppercase_columns else name for name in raw.columns]
        values = np.array(
            [
                [
                    _to_float(token, first_line=raw.first_line, column=column)
                    for token, column in zip(row[1:], columns, strict=True)
                ]
                for row in raw.rows
            ],
            dtype=float,
        )
        values = _apply_missing_codes(values, missing_codes, missing_tolerance)
        in_percent = _is_percent_block(raw.title, percent_keywords)
        if in_percent:
            values = values / percent_divisor
        frame = pd.DataFrame(values, index=index, columns=columns)

        base = _slugify(raw.title, max_name_words) or frequency.value
        seen = taken.get(base, 0)
        taken[base] = seen + 1
        name = base if seen == 0 else f"{base}_{seen + 1}"
        blocks.append(
            FrenchBlock(
                name=name,
                title=raw.title,
                frequency=frequency,
                in_percent=in_percent,
                frame=frame,
                first_line=raw.first_line,
            )
        )

    log.info(
        "fichier de la bibliothèque analysé",
        extra={"tables": len(blocks), "names": ",".join(block.name for block in blocks)},
    )
    return ParsedFrenchFile(preamble=preamble, trailer=trailer, blocks=tuple(blocks))


def _coerce_timestamp(value: dt.date | dt.datetime | str | pd.Timestamp | None) -> pd.Timestamp | None:
    """Rend une borne de date sous forme de ``Timestamp``, ou ``None``."""
    if value is None:
        return None
    return pd.Timestamp(value)


def slice_period(
    frame: pd.DataFrame,
    start: dt.date | str | pd.Timestamp | None = None,
    end: dt.date | str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Rend les lignes comprises entre deux bornes, incluses toutes les deux.

    Args:
        frame: un tableau indexé par des dates.
        start: première date gardée, ou ``None`` pour ne pas couper à gauche.
        end: dernière date gardée, ou ``None`` pour ne pas couper à droite.

    Returns:
        Une vue copiée du tableau, bornes incluses.

    Note:
        Les dates mensuelles étant portées à la fin de la période décrite, une
        borne au 1er janvier 1927 garde le mois de janvier 1927, daté du 31.
    """
    left = _coerce_timestamp(start)
    right = _coerce_timestamp(end)
    mask = np.ones(len(frame), dtype=bool)
    if left is not None:
        mask &= frame.index >= left
    if right is not None:
        mask &= frame.index <= right
    return frame.loc[mask].copy()


def combine_benchmark_factors(
    five_factor: pd.DataFrame,
    momentum: pd.DataFrame,
    *,
    momentum_column: str = "MOM",
    columns: Sequence[str] = BENCHMARK_COLUMNS,
) -> pd.DataFrame:
    """Assemble les cinq facteurs, le momentum et le taux sans risque.

    **Le problème.** La bibliothèque publie les cinq facteurs dans un fichier et
    le momentum dans un autre, avec des dates de fin différentes. Les coller par
    une jointure interne raccourcit silencieusement l'échantillon des cinq
    facteurs quand le momentum s'arrête plus tôt.

    **La règle.** L'index des cinq facteurs gouverne. Le momentum est réaligné
    sur cet index, et les dates qu'il ne couvre pas restent ``NaN``, visibles.

    Args:
        five_factor: le tableau des cinq facteurs, portant MKT-RF, SMB, HML,
            RMW, CMA et RF.
        momentum: le tableau du momentum, portant la colonne nommée par
            ``momentum_column``.
        momentum_column: le nom de la colonne de momentum.
        columns: l'ordre des colonnes rendues.

    Returns:
        Un tableau indexé comme ``five_factor``, avec les sept colonnes
        demandées.

    Raises:
        DataQualityError: si une colonne attendue manque.
        InsufficientDataError: si les deux index ne se recoupent pas du tout.

    Note:
        SMB n'est pas le même dans le modèle à trois facteurs et dans celui à
        cinq : Fama et French (2015) le construisent sur les six tris qui
        servent aussi à RMW et CMA. Celui rendu ici est celui du fichier à cinq
        facteurs, et c'est le bon quand les cinq facteurs sont au dénominateur
        de la même régression.

        Pour vérifier : sur deux tableaux fabriqués à la main dont l'un couvre
        un mois de moins, la sortie garde toutes les lignes du premier et porte
        exactement un ``NaN`` dans la colonne de momentum.
    """
    wanted = [name for name in columns if name != momentum_column]
    missing = [name for name in wanted if name not in five_factor.columns]
    if missing:
        raise DataQualityError(f"colonnes absentes du fichier à cinq facteurs : {missing}")
    if momentum_column not in momentum.columns:
        raise DataQualityError(
            f"colonne « {momentum_column} » absente du fichier de momentum ; "
            f"colonnes présentes : {list(momentum.columns)}"
        )
    if five_factor.index.intersection(momentum.index).empty:
        raise InsufficientDataError(
            "les cinq facteurs et le momentum ne partagent aucune date ; "
            "fréquences ou conventions de date incompatibles"
        )
    combined = five_factor.loc[:, wanted].copy()
    combined[momentum_column] = momentum[momentum_column].reindex(five_factor.index)
    return combined.loc[:, list(columns)]


#: Traitement des actions de société, tel que la bibliothèque le décrit. Les
#: rendements de CRSP sont ajustés des divisions et des dividendes.
CORPORATE_ACTIONS: Final[str] = "rendements CRSP ajustés des divisions et incluant les dividendes réinvestis"

#: Politique de révision, déclarée telle qu'elle est observée. Chaque millésime
#: de CRSP republie l'histoire entière, y compris les dates anciennes.
REVISION_POLICY: Final[str] = (
    "série entièrement republiée à chaque millésime de CRSP, révisions rétroactives comprises, "
    "sans conservation des millésimes précédents par la source"
)

#: Nom lisible de la source, pour le manifeste.
SOURCE_NAME: Final[str] = "Kenneth R. French data library, Tuck School of Business, Dartmouth"

#: Adresse du texte de licence, la page de conditions de la bibliothèque.
LICENSE_URL: Final[str] = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html"

#: Version du code de lecture. Elle change dès qu'une convention change, par
#: exemple la position de date ou la règle de conversion de pourcentage.
PROCESSING_VERSION: Final[str] = "french-1.0.0"

#: Devise des montants publiés. Les facteurs sont des rendements, donc sans
#: unité, mais les tableaux de capitalisation des fichiers de portefeuilles sont
#: en dollars américains.
CURRENCY: Final[str] = "USD"

#: Fuseau des horodatages. Les dates sont des dates de séance du marché
#: américain, sans heure, si bien que le fuseau ne sert qu'à les situer.
TIMEZONE: Final[str] = "America/New_York"

#: Signature d'une archive ZIP, ses deux premiers octets.
ZIP_SIGNATURE: Final[bytes] = b"PK"


class FrenchProvider(BaseProvider):
    """Le fournisseur de la bibliothèque de Kenneth French.

    Il hérite du socle commun, donc du client HTTP poli, du cache brut horodaté
    et de l'empreinte SHA-256 vérifiée à la relecture. Il n'ajoute que ce qui
    est propre à cette source : l'adresse des archives, l'ouverture du ZIP et
    l'appel à :func:`parse_french_csv`.

    Le téléchargement et l'analyse restent séparés, si bien que toute la
    logique difficile se teste hors réseau en passant du texte à
    :func:`parse_french_csv`.

    Args:
        client: le client HTTP. Sans valeur, il est créé au premier besoin.
        raw_root: la racine du cache brut. Sans valeur,
            ``data/raw/french/``. Les tests y passent un ``tmp_path``.
        now: fournisseur de l'horodatage, injectable.
        base_url: la racine des archives.

    Example:
        >>> provider = FrenchProvider()
        >>> provider.archive_url("F-F_Research_Data_Factors_daily").endswith("_CSV.zip")
        True
    """

    #: Nom court du fournisseur, qui nomme aussi son dossier de cache brut.
    name: ClassVar[str] = "french"

    def __init__(
        self,
        *,
        client: HttpClient | None = None,
        raw_root: Any = None,
        now: Callable[[], dt.datetime] | None = None,
        base_url: str = BASE_URL,
    ) -> None:
        horloge = {"now": now} if now is not None else {}
        super().__init__(client=client, raw_root=raw_root, **horloge)
        self.base_url = base_url

    # ------------------------------------------------------------------ #
    # Localisation
    # ------------------------------------------------------------------ #
    def archive_url(self, dataset: str) -> str:
        """Rend l'adresse de l'archive d'un jeu.

        Args:
            dataset: le nom du fichier sans le suffixe « _CSV.zip ».

        Returns:
            L'adresse complète, par exemple la racine suivie de
            ``F-F_Research_Data_Factors_daily_CSV.zip``.

        Raises:
            ConfigError: si le nom est vide ou fait d'espaces.
        """
        if not dataset or not dataset.strip():
            raise ConfigError("le nom du jeu de données est vide")
        return f"{self.base_url}{dataset}{ARCHIVE_SUFFIX}"

    @staticmethod
    def available_datasets() -> Mapping[str, FrenchDatasetSpec]:
        """Rend les jeux connus du module. Voir :func:`available_datasets`."""
        return available_datasets()

    # ------------------------------------------------------------------ #
    # Téléchargement
    # ------------------------------------------------------------------ #
    def raw_archive(self, dataset: str = DEFAULT_DATASET, *, refresh: bool = False) -> RawResponse:
        """Rend la réponse brute portant l'archive, du cache ou du réseau.

        Le cache est la couche ``raw`` du lac, et il est immuable : un nouveau
        téléchargement crée un fichier horodaté de plus, sans toucher aux
        précédents. Une étude se rejoue ainsi sur le millésime exact qui l'a
        produite, alors que la bibliothèque republie ses fichiers chaque mois.

        Args:
            dataset: le nom du fichier sans le suffixe.
            refresh: force un nouveau téléchargement.

        Returns:
            La réponse brute, avec son empreinte et son horodatage.
        """
        return self.fetch_cached(self.archive_url(dataset), label=dataset, refresh=refresh)

    def download(self, dataset: str = DEFAULT_DATASET, *, refresh: bool = False) -> bytes:
        """Rend les octets de l'archive ZIP d'un jeu.

        Args:
            dataset: le nom du fichier sans le suffixe.
            refresh: force un nouveau téléchargement.

        Returns:
            Le contenu de l'archive.

        Raises:
            DataQualityError: si la réponse n'est pas une archive ZIP. Une page
                d'erreur en HTML arrive avec un code 200 et se lirait sinon
                comme un fichier vide.
        """
        payload = self.raw_archive(dataset, refresh=refresh).content
        if not payload.startswith(ZIP_SIGNATURE):
            raise DataQualityError(
                f"{self.archive_url(dataset)} n'a pas rendu une archive ZIP ; "
                f"premiers octets : {payload[:16]!r}"
            )
        return payload

    @staticmethod
    def extract_text(payload: bytes, *, encoding: str = "latin-1") -> str:
        """Rend le texte du fichier CSV que contient l'archive.

        Args:
            payload: les octets de l'archive ZIP.
            encoding: l'encodage de décodage. « latin-1 » est retenu parce qu'il
                ne lève jamais. Les fichiers mesurés sont en ASCII pur, et un
                octet inattendu dans un millésime futur ne doit pas arrêter une
                étude sur un caractère de préambule.

        Returns:
            Le contenu texte du fichier CSV, retours de ligne inchangés.

        Raises:
            DataQualityError: si l'archive ne contient aucun fichier CSV.
        """
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            members = sorted(n for n in archive.namelist() if n.lower().endswith(".csv"))
            if not members:
                raise DataQualityError(f"aucun fichier CSV dans l'archive : {archive.namelist()}")
            if len(members) > 1:
                log.warning("archive à plusieurs CSV, le premier est retenu", extra={"members": members})
            return archive.read(members[0]).decode(encoding)

    def read_text(self, dataset: str = DEFAULT_DATASET, *, refresh: bool = False) -> str:
        """Rend le texte brut du fichier CSV d'un jeu."""
        return self.extract_text(self.download(dataset, refresh=refresh))

    # ------------------------------------------------------------------ #
    # Lecture
    # ------------------------------------------------------------------ #
    def parse(
        self,
        dataset: str = DEFAULT_DATASET,
        *,
        refresh: bool = False,
        **kwargs: Any,
    ) -> ParsedFrenchFile:
        """Télécharge un jeu et rend son analyse complète.

        Args:
            dataset: le nom du fichier sans le suffixe.
            refresh: force un nouveau téléchargement.
            **kwargs: transmis à :func:`parse_french_csv`.

        Returns:
            Le fichier analysé, tableaux compris.
        """
        return parse_french_csv(self.read_text(dataset, refresh=refresh), **kwargs)

    def fetch_tables(
        self,
        dataset: str = DEFAULT_DATASET,
        start: dt.date | str | None = None,
        end: dt.date | str | None = None,
        *,
        refresh: bool = False,
        **kwargs: Any,
    ) -> dict[str, pd.DataFrame]:
        """Rend tous les tableaux d'un jeu, bornés à la période demandée.

        Args:
            dataset: le nom du fichier sans le suffixe.
            start: première date gardée.
            end: dernière date gardée.
            refresh: force un nouveau téléchargement.
            **kwargs: transmis à :func:`parse_french_csv`.

        Returns:
            Un dictionnaire du nom court de chaque tableau vers ses données.
        """
        parsed = self.parse(dataset, refresh=refresh, **kwargs)
        return {name: slice_period(frame, start, end) for name, frame in parsed.tables.items()}

    def fetch(
        self,
        dataset: str = DEFAULT_DATASET,
        start: dt.date | str | None = None,
        end: dt.date | str | None = None,
        *,
        table: str | None = None,
        refresh: bool = False,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Rend un seul tableau, le premier du fichier par défaut.

        Le protocole :class:`~quantlab.core.protocols.DataProvider` demande un
        ``DataFrame``, alors qu'un fichier de la bibliothèque en porte
        plusieurs. La règle est donc explicite : ``fetch`` rend le tableau
        principal, celui des rendements à la fréquence du fichier, et
        :meth:`fetch_tables` rend le dictionnaire entier.

        Args:
            dataset: le nom du fichier sans le suffixe.
            start: première date gardée.
            end: dernière date gardée.
            table: le nom court d'un autre tableau du même fichier, par exemple
                « annual_factors_january_december ».
            refresh: force un nouveau téléchargement.
            **kwargs: transmis à :func:`parse_french_csv`.

        Returns:
            Le tableau demandé, indexé par un ``DatetimeIndex`` nommé « date ».

        Raises:
            KeyError: si ``table`` ne nomme aucun tableau du fichier.
            InsufficientDataError: si le fichier ne porte aucun tableau.
        """
        parsed = self.parse(dataset, refresh=refresh, **kwargs)
        frame = parsed.primary if table is None else parsed[table]
        return slice_period(frame, start, end)

    def benchmark_factors(
        self,
        frequency: Frequency | str = Frequency.MONTHLY,
        start: dt.date | str | None = None,
        end: dt.date | str | None = None,
        *,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """Rend MKT-RF, SMB, HML, RMW, CMA, MOM et RF alignés sur un même index.

        C'est le jeu de référence de toute régression d'attribution. Le
        rendement d'une stratégie se régresse sur ces sept colonnes, et
        l'ordonnée à l'origine est l'alpha qui reste une fois payées les
        expositions aux facteurs connus.

        .. math::

            r_t - r_{f,t} = \\alpha
            + \\beta_{MKT}\\,MKT\\!-\\!RF_t + \\beta_{SMB}\\,SMB_t
            + \\beta_{HML}\\,HML_t + \\beta_{RMW}\\,RMW_t
            + \\beta_{CMA}\\,CMA_t + \\beta_{MOM}\\,MOM_t + \\varepsilon_t

        où :math:`r_t` est le rendement de la stratégie, :math:`r_{f,t}` le taux
        sans risque de la colonne RF, et les six bêtas les expositions.

        Args:
            frequency: ``Frequency.DAILY`` ou ``Frequency.MONTHLY``.
            start: première date gardée.
            end: dernière date gardée.
            refresh: force un nouveau téléchargement des deux fichiers.

        Returns:
            Un tableau à sept colonnes, en décimales, indexé par « date ».

        Raises:
            ConfigError: si la fréquence demandée n'est publiée ni en quotidien
                ni en mensuel.

        Note:
            Les cinq facteurs commencent en juillet 1963, alors que les trois
            facteurs remontent à juillet 1926. La contrainte vient de la
            disponibilité de la rentabilité opérationnelle chez Compustat, et
            non du code. Pour un échantillon long, prendre les trois facteurs
            par :meth:`fetch`.
        """
        freq = Frequency(frequency)
        files = {
            Frequency.DAILY: ("F-F_Research_Data_5_Factors_2x3_daily", "F-F_Momentum_Factor_daily"),
            Frequency.MONTHLY: ("F-F_Research_Data_5_Factors_2x3", "F-F_Momentum_Factor"),
        }
        if freq not in files:
            raise ConfigError(
                f"fréquence « {freq.value} » non publiée pour les facteurs de référence ; "
                f"choisir parmi {[f.value for f in files]}"
            )
        five_name, mom_name = files[freq]
        five = self.fetch(five_name, refresh=refresh)
        momentum = self.fetch(mom_name, refresh=refresh)
        combined = combine_benchmark_factors(five, momentum)
        return slice_period(combined, start, end)

    # ------------------------------------------------------------------ #
    # Provenance
    # ------------------------------------------------------------------ #
    def manifest(
        self,
        dataset: str = DEFAULT_DATASET,
        *,
        table: str | None = None,
        frame: pd.DataFrame | None = None,
        refresh: bool = False,
        **_: Any,
    ) -> DatasetManifest:
        """Décrit un jeu : origine, licence, biais du survivant, point-in-time.

        Deux déclarations décident de ce qu'on a le droit de conclure.

        ``survivorship_free=True``
            Les facteurs sont construits sur l'univers CRSP complet, sociétés
            radiées comprises, donc l'échantillon ne surestime pas les
            rendements par disparition des perdants.

        ``point_in_time=False``
            La série est révisée rétroactivement à chaque millésime de CRSP. Le
            rendement de juillet 1926 lu aujourd'hui n'est pas exactement celui
            qu'on aurait lu il y a dix ans. Un backtest qui s'appuie dessus
            utilise des chiffres qui n'existaient pas au moment de la décision.

        La fréquence déclarée est celle du tableau DÉCRIT, lue sur ses propres
        dates, et non celle du fichier. Le même fichier empile un tableau
        mensuel et un tableau annuel, et ``Frequency.MONTHLY.periods_per_year``
        vaut 12 contre 1 pour ``Frequency.ANNUAL``. Prendre la fréquence du
        fichier annualiserait la moyenne du tableau annuel douze fois trop haut
        et sa volatilité d'un facteur racine de douze, soit 3,46.

        Args:
            dataset: le nom du fichier sans le suffixe.
            table: le tableau décrit, le principal par défaut.
            frame: un tableau déjà chargé, pour éviter de le relire. Sans
                valeur, il est relu du cache. La fréquence reste celle du
                tableau nommé par ``table``, un bornage ne la changeant pas.
            refresh: force un nouveau téléchargement.

        Returns:
            Le manifeste du jeu, empreinte et couverture comprises.

        Raises:
            InsufficientDataError: si le fichier ne porte aucun tableau, ou si
                le tableau décrit est vide.
            KeyError: si ``table`` ne nomme aucun tableau du fichier.

        Note:
            L'empreinte est celle de l'ARCHIVE téléchargée, pas du tableau
            analysé. C'est elle qui identifie le millésime, et deux lectures
            différentes de la même archive doivent porter la même empreinte.
        """
        raw = self.raw_archive(dataset, refresh=refresh)
        parsed = self.parse(dataset)
        if not parsed.blocks:
            raise InsufficientDataError(f"le fichier « {dataset} » ne porte aucun tableau exploitable")
        block = parsed.blocks[0] if table is None else parsed.block(table)
        described = frame if frame is not None else block.frame
        spec = _DATASETS.get(dataset)
        if len(described) == 0:
            raise InsufficientDataError(
                f"le tableau décrit de « {dataset} » est vide, sa couverture est indéterminée"
            )
        columns = tuple(str(column) for column in described.columns)
        return DatasetManifest(
            dataset_id=f"french-{dataset}-{table or 'primary'}",
            source=SOURCE_NAME,
            provider=self.name,
            url=self.archive_url(dataset),
            download_timestamp=raw.fetched_at,
            data_start=described.index[0].date(),
            data_end=described.index[-1].date(),
            frequency=block.frequency,
            timezone=TIMEZONE,
            exchange=None,
            currency=CURRENCY,
            adjusted=True,
            point_in_time=False,
            survivorship_free=True,
            corporate_actions=CORPORATE_ACTIONS,
            revision_policy=REVISION_POLICY,
            license=LICENSE,
            license_url=LICENSE_URL,
            checksum_sha256=raw.sha256,
            n_rows=len(described),
            n_columns=len(columns),
            columns=columns,
            processing_version=PROCESSING_VERSION,
            layer=Layer.BRONZE,
            notes=(
                spec.description
                if spec is not None
                else "jeu hors de la table des jeux connus, analysé par la même syntaxe"
            ),
        )

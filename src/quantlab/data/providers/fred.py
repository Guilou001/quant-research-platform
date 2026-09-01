r"""Le PIB tel qu'on le connaissait à l'époque, et non tel qu'on le corrige aujourd'hui.

FRED rend la dernière version d'une série macroéconomique, ALFRED rend la
version qui était publiée à une date choisie. Toute la valeur de ce module tient
dans cette différence, et elle se résume en une ligne de manifeste :
``point_in_time`` vaut faux pour :class:`FredProvider` et vrai pour
:class:`AlfredProvider`.

**Le problème, en une phrase.** Une série macroéconomique est réécrite après sa
publication, si bien que le chiffre lu aujourd'hui pour un trimestre de 2008
n'est pas celui qu'un investisseur pouvait lire en 2008.

**L'exemple chiffré, mesuré le 2026-09-01.** La série ``GDPC1``, le produit
intérieur brut réel des États-Unis, est demandée à ALFRED pour quatre
millésimes. Le tableau donne le niveau du premier trimestre de 2008 et la
croissance annualisée que ce niveau implique, par la formule
:math:`g_t = (Y_t / Y_{t-1})^4 - 1`.

=================  ==================  ==================  ==================
Millésime          Niveau 2008 T1      Croissance 2008 T1  Croissance 2007 T4
=================  ==================  ==================  ==================
2008-04-30          11 693,1            +0,60 %             +0,58 %
2008-06-26          11 703,6            +0,96 %             +0,58 %
2008-07-31          11 646,0            +0,87 %             -0,17 %
2026-08-01          16 843,003          -1,70 %             +2,54 %
=================  ==================  ==================  ==================

Le détail du premier calcul, à la main. Le rapport 11 693,1 / 11 675,7 vaut
1,0014903. Porté à la puissance quatre, il donne 1,0059744, soit +0,5974 %, que
la colonne arrondit à +0,60 %.

**Ce que la fuite produit concrètement.** Prenons une règle « acheter quand la
croissance du PIB accélère ». Testée sur les données révisées d'aujourd'hui,
elle lit +2,54 % puis -1,70 %, donc une décélération brutale, et n'achète pas au
premier trimestre de 2008. La même règle, avec l'information réellement disponible le
30 avril 2008, lit +0,58 % puis +0,60 %, donc une accélération, et achète juste
avant l'effondrement des marchés. Le backtest sur données révisées gagne un
arbitrage que personne ne pouvait faire, et son rendement mesure la révision, pas
la stratégie.

**Le piège des niveaux.** Les niveaux ne se comparent pas d'un millésime à
l'autre, parce que le PIB réel change d'année de référence à chaque révision
globale. Le même trimestre de 2008 vaut ainsi 11 693,1 dans le millésime d'avril
2008 contre 16 843,003 dans celui d'août 2026. Seules les croissances se
comparent, et un panneau de millésimes se lit donc toujours en variations.

**Statut des chiffres ci-dessus** : mesurés le 2026-09-01, par téléchargement
des quatre millésimes depuis ``alfredgraph.csv``. Les extraits exacts sont
recopiés dans le fichier de tests, si bien que le calcul se refait hors
réseau.

**Ce que le module fait, et ce qu'il ne fait pas.** Il télécharge, il analyse le
CSV, il assemble un panneau de millésimes et il rend l'état connaissable à une
date. Il ne comble aucune valeur manquante, ne rééchantillonne rien et ne décale
aucun signal. Le décalage de publication appartient au module point-in-time, qui
consomme le panneau rendu ici.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from io import StringIO
from typing import Any, ClassVar, Final

import pandas as pd

from quantlab.core.errors import (
    ConfigError,
    DataQualityError,
    InsufficientDataError,
    LookAheadError,
)
from quantlab.core.logging import get_logger, stage
from quantlab.core.paths import Layer
from quantlab.core.types import Frequency
from quantlab.data.manifest import DatasetManifest
from quantlab.data.providers.base import BaseProvider

log = get_logger(__name__)

#: Le nom du fournisseur qui rend la dernière version d'une série.
FRED_PROVIDER_NAME: Final[str] = "fred"

#: Le nom du fournisseur qui rend une version datée d'une série.
ALFRED_PROVIDER_NAME: Final[str] = "alfred"

#: L'export CSV de FRED, sans clé d'interface. Répond 200 le 2026-09-01, mesuré.
FRED_CSV_URL: Final[str] = "https://fred.stlouisfed.org/graph/fredgraph.csv"

#: L'export CSV d'ALFRED, sans clé d'interface. Répond 200 le 2026-09-01, mesuré.
ALFRED_CSV_URL: Final[str] = "https://alfred.stlouisfed.org/graph/alfredgraph.csv"

#: Les noms acceptés pour la première colonne. « observation_date » est celui
#: que l'export rend le 2026-09-01, mesuré ; « date » se rencontre dans des
#: exports plus anciens, statut rapporté.
DATE_COLUMN_NAMES: Final[frozenset[str]] = frozenset({"observation_date", "date"})

#: Les écritures d'une valeur absente. Le point est la convention historique de
#: FRED, statut rapporté ; la cellule vide est ce que l'export rend, mesuré le
#: 2026-09-01. Les 16 869 observations de ``DGS10`` portent 719 cellules vides
#: et aucun point, et le millésime ALFRED du 2008-06-26 de la même série en
#: porte 523 sur 12 126, toujours sans un seul point.
MISSING_TOKENS: Final[frozenset[str]] = frozenset({".", "", "na", "n/a", "nan"})

#: Le format de date de l'export, mesuré le 2026-09-01.
DATE_FORMAT: Final[str] = "%Y-%m-%d"

#: L'unité temporelle tenue dans tout le laboratoire. pandas 3 rend des index
#: en secondes ou en microsecondes selon la fonction appelée, et deux unités
#: différentes se joignent mal. Une seule unité est donc imposée à la sortie.
DATETIME_DTYPE: Final[str] = "datetime64[ns]"

#: Le nom de l'index d'une série d'observations.
OBSERVATION_DATE: Final[str] = "observation_date"

#: Le nom de la colonne qui porte la date de publication d'un millésime.
VINTAGE_DATE: Final[str] = "vintage_date"

#: Le nom de la colonne qui porte la valeur.
VALUE: Final[str] = "value"

#: Les colonnes d'un panneau de millésimes, dans l'ordre.
PANEL_SCHEMA: Final[tuple[str, str, str]] = (OBSERVATION_DATE, VINTAGE_DATE, VALUE)

#: La licence, citée telle que la banque la publie. Chaque série porte les
#: droits de sa source d'origine, et une série tierce peut être protégée.
LICENSE: Final[str] = (
    "FRED, conditions d'utilisation de la Federal Reserve Bank of St. Louis ; "
    "les droits dépendent de la source de chaque série et se vérifient série par série"
)

#: L'adresse du texte de licence.
LICENSE_URL: Final[str] = "https://fred.stlouisfed.org/legal/"

#: Ce que FRED fait des chiffres déjà publiés.
FRED_REVISION_POLICY: Final[str] = (
    "la série est réécrite à chaque révision, donc la valeur lue hier n'est plus "
    "lisible et une extraction non datée n'est pas reproductible"
)

#: Ce qu'ALFRED fait des chiffres déjà publiés.
ALFRED_REVISION_POLICY: Final[str] = (
    "chaque millésime est figé et reste interrogeable, donc une extraction datée se refait à l'identique"
)

#: La version du code qui produit les tableaux de ce module.
PROCESSING_VERSION: Final[str] = "1.0.0"

#: Les limites connues, à citer dans tout rapport qui s'appuie sur ce module.
KNOWN_LIMITATIONS: Final[tuple[str, ...]] = (
    "FRED ne dit pas ce qu'il disait hier : une série téléchargée sans millésime "
    "porte les révisions postérieures à toute date de backtest.",
    "ALFRED ne couvre pas toutes les séries, et une série absente de ses millésimes "
    "n'est pas reconstructible point-in-time depuis cette source.",
    "Le millésime donne la date de publication, jamais l'heure : une décision prise "
    "le matin d'une publication de 8 h 30 reste indistincte d'une décision du soir.",
    "Les niveaux ne se comparent pas d'un millésime à l'autre quand la source change "
    "d'année de référence, et seules les variations restent comparables.",
    "L'export CSV ne déclare ni unité ni devise, donc l'unité se lit sur la page de la "
    "série et non dans le fichier.",
)

#: Les bornes de la déduction de fréquence, en jours, ouvertes à droite. Elles
#: sont larges à dessein : un mois vaut 28 à 31 jours, un trimestre 90 à 92.
FREQUENCY_BOUNDS_DAYS: Final[tuple[tuple[float, Frequency], ...]] = (
    (4.0, Frequency.DAILY),
    (10.0, Frequency.WEEKLY),
    (45.0, Frequency.MONTHLY),
    (135.0, Frequency.QUARTERLY),
)


# --------------------------------------------------------------------------- #
# Analyse du CSV
# --------------------------------------------------------------------------- #


def series_id_from_header(column: str) -> tuple[str, dt.date | None]:
    """Rend l'identifiant de série et le millésime portés par un nom de colonne.

    (1) Le problème : ALFRED nomme sa colonne de valeurs ``GDPC1_20080626``, où
    le suffixe est la date du millésime, alors que FRED la nomme ``GDPC1``.
    Un code qui lirait le nom tel quel changerait de colonne à chaque millésime.
    (2) L'intuition : le suffixe est un ``AAAAMMJJ``, donc il se reconnaît à sa
    longueur et à ses chiffres, sans autre convention.

    Args:
        column: le nom de la deuxième colonne du CSV.

    Returns:
        Le couple identifiant et millésime. Le millésime vaut ``None`` quand la
        colonne n'en porte pas, ce qui est le cas de tout export FRED.

    Raises:
        DataQualityError: si le nom de colonne est vide.

    Example:
        >>> series_id_from_header("GDPC1_20080626")
        ('GDPC1', datetime.date(2008, 6, 26))
        >>> series_id_from_header("DGS10")
        ('DGS10', None)

    Note:
        Vérification (10) : le format du suffixe est mesuré le 2026-09-01 sur
        quatre millésimes de ``GDPC1``, dont l'en-tête vaut exactement
        ``observation_date,GDPC1_20080430``. Un suffixe de huit chiffres qui ne
        formerait pas une date, par exemple ``99999999``, est rendu comme partie
        de l'identifiant plutôt que refusé, parce que rien n'interdit à la
        source de nommer une série ainsi.
    """
    name = column.strip()
    if not name:
        raise DataQualityError("la colonne de valeurs du CSV n'a pas de nom")
    head, separator, tail = name.rpartition("_")
    if separator and len(tail) == 8 and tail.isdigit() and head:
        try:
            return head, dt.datetime.strptime(tail, "%Y%m%d").date()
        except ValueError:
            return name, None
    return name, None


def parse_fred_csv(
    text: str,
    *,
    series_id: str | None = None,
    missing_tokens: frozenset[str] = MISSING_TOKENS,
    date_format: str = DATE_FORMAT,
) -> pd.Series:
    """Rend la série de flottants portée par un export CSV de FRED ou d'ALFRED.

    (1) Le problème : l'export écrit ses valeurs absentes en clair, par un point
    ou par une cellule vide, et un flottant lu sur ces écritures vaut zéro ou
    lève, deux réponses fausses. (2) L'intuition : une valeur absente devient un
    ``NaN`` déclaré, et tout ce qui n'est ni un nombre ni une absence connue
    fait échouer l'analyse plutôt que de passer en silence.

    (3) La transformation, pour chaque ligne :

    .. math::

        v_i =
        \\begin{cases}
        \\mathrm{NaN} & \\text{si le texte appartient aux jetons d'absence,} \\\\
        \\mathrm{float}(x_i) & \\text{sinon.}
        \\end{cases}

    (4) Les variables : :math:`x_i` est le texte de la deuxième colonne de la
    ligne :math:`i`, et :math:`v_i` la valeur rendue. (5) Les hypothèses : le
    fichier porte exactement deux colonnes, la première est une date au format
    ``date_format``, et une date n'apparaît qu'une fois.

    Args:
        text: le contenu du CSV, déjà décodé.
        series_id: le nom imposé à la série rendue. Sans valeur, il est lu dans
            l'en-tête, suffixe de millésime retiré.
        missing_tokens: les écritures d'une valeur absente, comparées en
            minuscules après retrait des espaces.
        date_format: le format de date attendu dans la première colonne.

    Returns:
        Une série de ``float64`` indexée par un ``DatetimeIndex`` nommé
        ``« observation_date »``, en unité ``datetime64[ns]``, triée par date
        croissante. Son nom est l'identifiant de série.

    Raises:
        InsufficientDataError: si le fichier ne porte aucune observation, cas
            d'un fichier vide ou réduit à son en-tête.
        DataQualityError: si l'en-tête est inattendu, si une ligne n'a pas deux
            champs, si une date est illisible, si une valeur n'est ni un nombre
            ni une absence connue, ou si une date apparaît deux fois.

    Example:
        >>> csv_text = "observation_date,DGS10\\n2020-01-02,1.88\\n2020-01-03,.\\n"
        >>> serie = parse_fred_csv(csv_text)
        >>> serie.name, float(serie.iloc[0]), bool(serie.isna().iloc[1])
        ('DGS10', 1.88, True)

    Note:
        Provenance (6) : le format est celui de l'export public de la Federal
        Reserve Bank of St. Louis, mesuré le 2026-09-01 ; il n'y a pas d'article
        derrière. Limites (7) : la fonction refuse un fichier à plusieurs séries,
        que l'export sait pourtant produire quand plusieurs identifiants sont
        demandés. Alternatives (8) : ``pandas.read_csv`` avec
        ``na_values=["."]``, plus court, mais qui accepte en silence une colonne
        entièrement textuelle et rend alors une série d'objets. Choix (9) :
        l'analyse ligne à ligne dit quelle ligne est fautive, ce qui est la
        seule information utile devant un fichier de seize mille lignes.
        Vérification (10) : le test hors réseau analyse un extrait recopié de
        l'export réel, avec un point et une cellule vide, et retrouve les deux
        valeurs présentes.
    """
    rows = [row for row in csv.reader(StringIO(text.lstrip("﻿"))) if any(f.strip() for f in row)]
    if not rows:
        raise InsufficientDataError("le CSV est vide, aucune observation à analyser")

    header = [field.strip() for field in rows[0]]
    if len(header) != 2:
        raise DataQualityError(
            f"un export d'une seule série porte deux colonnes, celui-ci en porte {len(header)} : {header}"
        )
    if header[0].lower() not in DATE_COLUMN_NAMES:
        raise DataQualityError(
            f"première colonne nommée « {header[0]} », attendue parmi {sorted(DATE_COLUMN_NAMES)}"
        )

    column_id, _ = series_id_from_header(header[1])
    name = series_id or column_id
    absent = {token.lower() for token in missing_tokens}
    dates: list[dt.date] = []
    values: list[float] = []

    for line_number, row in enumerate(rows[1:], start=2):
        if len(row) != 2:
            raise DataQualityError(f"ligne {line_number} : {len(row)} champs au lieu de deux, {row}")
        raw_date, raw_value = row[0].strip(), row[1].strip()
        try:
            dates.append(dt.datetime.strptime(raw_date, date_format).date())
        except ValueError as exc:
            raise DataQualityError(
                f"ligne {line_number} : date illisible « {raw_date} », format attendu « {date_format} »"
            ) from exc
        if raw_value.lower() in absent:
            values.append(float("nan"))
            continue
        try:
            values.append(float(raw_value))
        except ValueError as exc:
            raise DataQualityError(
                f"ligne {line_number} : valeur « {raw_value} » ni nombre ni absence connue "
                f"parmi {sorted(missing_tokens)}"
            ) from exc

    if not dates:
        raise InsufficientDataError(f"« {name} » ne porte aucune observation, seulement son en-tête")

    index = pd.DatetimeIndex(dates, name=OBSERVATION_DATE).astype(DATETIME_DTYPE)
    if index.has_duplicates:
        doublons = index[index.duplicated()].strftime("%Y-%m-%d").tolist()
        raise DataQualityError(f"« {name} » porte des dates en double : {sorted(set(doublons))[:5]}")
    serie = pd.Series(values, index=index, dtype="float64", name=name)
    if not serie.index.is_monotonic_increasing:
        log.warning("export non trié, tri appliqué", extra={"series_id": name, "rows": len(serie)})
        serie = serie.sort_index()
    return serie


def infer_frequency(
    index: pd.DatetimeIndex,
    *,
    bounds_days: tuple[tuple[float, Frequency], ...] = FREQUENCY_BOUNDS_DAYS,
) -> Frequency:
    """Rend la fréquence déduite de l'écart médian entre deux observations.

    (1) Le problème : le manifeste exige une fréquence, et l'export CSV ne la
    déclare nulle part. Elle se lit donc dans les dates elles-mêmes.
    (2) L'intuition : la médiane des écarts résiste aux trous, alors que la
    moyenne se laisse déplacer par un seul intervalle long. Une série
    quotidienne de marché a une médiane de un jour, une série mensuelle de
    trente et un, une série trimestrielle de quatre-vingt-onze ou
    quatre-vingt-douze.

    (3) La règle :

    .. math::

        m = \\mathrm{med}\\{ t_{i+1} - t_i \\}_{i=1}^{n-1}, \\qquad
        f(m) = \\min\\{ f_k : m < b_k \\}

    (4) Les variables : :math:`t_i` est la date de l'observation :math:`i`,
    exprimée en jours, :math:`m` l'écart médian, et :math:`b_k` la borne du
    couple :math:`k` de ``bounds_days``, associée à la fréquence :math:`f_k`.
    Aucune borne franchie rend :attr:`Frequency.ANNUAL`.
    (5) Les hypothèses : l'index est trié, sans doublon, et décrit une seule
    série. Un index qui répète ses dates, comme la colonne d'observation d'un
    panneau de millésimes, donne un écart médian de zéro jour et fait déclarer
    « quotidien » une série trimestrielle. C'est mesuré le 2026-09-01 sur deux
    millésimes de ``GDPC1``, dont les écarts valent 0, 92, 0, 92 puis 0.

    Args:
        index: l'index temporel de la série, deux points au moins.
        bounds_days: les seuils, ouverts à droite, du plus court au plus long.
            Le dernier cas non couvert rend :attr:`Frequency.ANNUAL`.

    Returns:
        La fréquence déduite.

    Raises:
        InsufficientDataError: si l'index porte moins de deux dates, un écart
            n'existant pas sur un point unique.

    Example:
        Trois observations trimestrielles du 1er janvier, du 1er avril et du
        1er juillet 2008 donnent des écarts de 91 et 91 jours, donc une médiane
        de 91, comprise entre 45 et 135, donc ``Frequency.QUARTERLY``.

    Note:
        Provenance (6) : aucune, la règle est un usage de la profession et non
        un résultat publié, donc son statut est celui d'un précepte. Les bornes
        par défaut sont posées ici, et elles sont un argument. Limites (7) : la
        déduction est une heuristique, pas une mesure. Une série mensuelle
        amputée d'un mois sur deux serait lue trimestrielle. Alternatives (8) :
        ``pandas.infer_freq``, qui rend un alias exact, mais qui rend ``None``
        dès qu'un seul écart s'écarte du pas, ce qui arrive à toute série de
        marché fermée les jours fériés. Choix (9) : le manifeste exige une
        fréquence, et une valeur déduite et déclarée vaut mieux qu'une valeur
        par défaut posée sans regarder la donnée. L'appelant peut toujours
        imposer la sienne. Vérification (10) : cinq tests fixent un index dont
        les écarts sont comptés à la main dans leur commentaire, un par
        fréquence rendue.
    """
    if len(index) < 2:
        raise InsufficientDataError(
            f"la fréquence se déduit d'au moins deux dates, l'index en porte {len(index)}"
        )
    gaps = pd.Series(index.to_series().diff().dropna().dt.total_seconds() / 86400.0)
    median_gap = float(gaps.median())
    for limit, frequency in bounds_days:
        if median_gap < limit:
            return frequency
    return Frequency.ANNUAL


# --------------------------------------------------------------------------- #
# Le panneau de millésimes
# --------------------------------------------------------------------------- #


def _as_date(value: dt.date | dt.datetime | str) -> dt.date:
    """Rend une date calendaire depuis une date, un instant ou un texte ISO."""
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return dt.datetime.strptime(str(value).strip()[:10], DATE_FORMAT).date()


def combine_checksums(checksums: Iterable[str]) -> str:
    """Rend l'empreinte unique d'un assemblage de fichiers, depuis leurs empreintes.

    (1) Le problème : un panneau vient de plusieurs téléchargements, et le
    manifeste ne porte qu'une empreinte. Sans elle, la question « quels octets
    exacts ont produit ce panneau » reste sans réponse, et le manifeste ment par
    omission. (2) L'intuition : hacher la liste des empreintes revient à hacher
    les fichiers eux-mêmes, à ceci près que le calcul est immédiat et ne relit
    rien.

    (3) La définition :

    .. math::

        H = \\mathrm{SHA256}\\big( h_1 \\Vert \\text{« | »} \\Vert h_2 \\Vert
        \\cdots \\Vert h_n \\big)

    (4) Les variables : :math:`h_i` est l'empreinte hexadécimale du millésime
    :math:`i`, les millésimes étant pris dans l'ordre où l'appelant les donne,
    c'est-à-dire trié par date. Le séparateur empêche deux découpages différents
    de donner la même chaîne. (5) Les hypothèses : chaque :math:`h_i` identifie
    son fichier, ce que SHA-256 assure en pratique.

    Args:
        checksums: les empreintes, dans l'ordre qui définit l'assemblage.

    Returns:
        Une empreinte de 64 caractères hexadécimaux minuscules, ou la chaîne
        vide si aucune empreinte n'est donnée.

    Example:
        >>> combine_checksums([]) == ""
        True
        >>> len(combine_checksums(["a" * 64, "b" * 64]))
        64

    Note:
        Provenance (6) : le procédé est un arbre de Merkle réduit à un seul
        niveau, d'après Merkle, CRYPTO 1987, statut rapporté. Aucune subtilité
        cryptographique n'entre ici, le but étant la traçabilité et non la
        résistance à un adversaire. Limites (7) : l'empreinte dépend de l'ordre, donc deux
        assemblages des mêmes millésimes rangés autrement diffèrent. C'est voulu,
        l'ordre faisant partie de l'assemblage. Alternatives (8) : hacher la
        concaténation des contenus, exact mais qui oblige à garder tous les
        octets en mémoire. Choix (9) : les empreintes suffisent, et elles sont
        déjà calculées par le cache brut. Vérification (10) : un test contrôle
        que l'empreinte est reproductible, qu'elle change quand un seul
        millésime change, et qu'elle vaut la valeur qu'un appel direct à
        ``hashlib`` donne sur la même chaîne.
    """
    empreintes = [str(c) for c in checksums if str(c)]
    if not empreintes:
        return ""
    return hashlib.sha256("|".join(empreintes).encode("utf-8")).hexdigest()


def empty_panel() -> pd.DataFrame:
    """Rend un panneau vide au schéma :data:`PANEL_SCHEMA`, types compris.

    Un tableau vide sans types force l'appelant à traiter le cas vide à part.
    Celui-ci porte les mêmes colonnes et les mêmes types qu'un panneau rempli,
    donc il se concatène et se filtre comme lui.
    """
    return pd.DataFrame(
        {
            OBSERVATION_DATE: pd.Series(dtype=DATETIME_DTYPE),
            VINTAGE_DATE: pd.Series(dtype=DATETIME_DTYPE),
            VALUE: pd.Series(dtype="float64"),
        }
    )


def build_vintage_panel(
    vintages: Mapping[dt.date | str, pd.Series],
    *,
    dropna: bool = False,
) -> pd.DataFrame:
    """Rend le panneau long des millésimes : date d'observation, millésime, valeur.

    (1) Le problème : chaque millésime est une série entière, et comparer deux
    millésimes revient à aligner deux index qui n'ont ni la même longueur ni les
    mêmes valeurs. (2) L'intuition : une observation macroéconomique porte deux
    dates, celle de la période décrite et celle de la publication qui l'annonce.
    Le format long les écrit toutes les deux, une ligne par couple, et c'est
    exactement ce qu'un jeu point-in-time demande.

    (5) Les hypothèses : chaque série porte un index temporel sans doublon, et
    deux millésimes différents décrivent la même série.

    Args:
        vintages: les séries, rangées par date de millésime. L'ordre du
            dictionnaire n'importe pas, le tri est refait.
        dropna: retire les lignes de valeur absente. Faux par défaut, parce
            qu'une valeur retirée par une révision est une information : elle
            dit que la source a cessé de publier ce point.

    Returns:
        Le panneau, colonnes :data:`PANEL_SCHEMA`, trié par date d'observation
        puis par millésime, index remis à zéro.

    Raises:
        DataQualityError: si un millésime porte un index non temporel, ou si le
            même couple observation et millésime apparaît deux fois.

    Example:
        Deux millésimes de ``GDPC1``, celui du 2008-04-30 et celui du
        2026-08-01, chacun réduit au premier trimestre de 2008, donnent deux
        lignes : ``(2008-01-01, 2008-04-30, 11693.1)`` et
        ``(2008-01-01, 2026-08-01, 16843.003)``. Les deux valeurs mesurées le
        2026-09-01 décrivent le même trimestre.

    Note:
        Limites (7) : la taille croît comme le produit du nombre de dates par le
        nombre de millésimes, donc une série quotidienne sur cent millésimes
        pèse des millions de lignes. Pour ce cas, ne demander que les millésimes
        des dates de rééquilibrage. Alternatives (8) : ne garder que les
        premières publications, plus compact, mais qui perd les révisions
        intermédiaires dont la mesure de la révision a besoin. Choix (9) : le
        panneau complet est la seule forme qui répond à « que savait-on le
        jour J » pour un J quelconque. Vérification (10) : le test hors réseau
        construit un panneau de deux millésimes et vérifie que la valeur du
        millésime le plus ancien ne bouge pas quand le plus récent change.
    """
    frames: list[pd.DataFrame] = []
    for raw_vintage, serie in vintages.items():
        vintage = _as_date(raw_vintage)
        if not isinstance(serie.index, pd.DatetimeIndex):
            raise DataQualityError(
                f"le millésime {vintage.isoformat()} porte un index "
                f"{type(serie.index).__name__} au lieu d'un DatetimeIndex"
            )
        block = pd.DataFrame(
            {
                OBSERVATION_DATE: serie.index.astype(DATETIME_DTYPE),
                VINTAGE_DATE: pd.Series(
                    [pd.Timestamp(vintage)] * len(serie), dtype=DATETIME_DTYPE
                ).to_numpy(),
                VALUE: serie.to_numpy(dtype="float64"),
            }
        )
        frames.append(block)

    if not frames:
        return empty_panel()

    panel = pd.concat(frames, ignore_index=True)
    if dropna:
        panel = panel.dropna(subset=[VALUE])
    duplicated = panel.duplicated(subset=[OBSERVATION_DATE, VINTAGE_DATE])
    if bool(duplicated.any()):
        first = panel.loc[duplicated].iloc[0]
        raise DataQualityError(
            "le même couple observation et millésime apparaît deux fois, "
            f"par exemple {first[OBSERVATION_DATE].date()} au millésime {first[VINTAGE_DATE].date()}"
        )
    panel = panel.sort_values([OBSERVATION_DATE, VINTAGE_DATE], kind="stable").reset_index(drop=True)
    return panel[list(PANEL_SCHEMA)]


def check_vintage_ordering(panel: pd.DataFrame, *, tolerance_days: int = 0) -> None:
    """Vérifie qu'aucune observation ne précède de plus de rien sa propre publication.

    Une ligne dont la date d'observation dépasse la date de millésime décrit une
    période que la publication ne pouvait pas connaître. Sur une série
    rétrospective, c'est le signe d'un panneau mal assemblé, et le contrôle
    lève. Une série de prévision viole cette règle légitimement, et
    ``tolerance_days`` sert alors à la desserrer en connaissance de cause.

    Args:
        panel: le panneau au schéma :data:`PANEL_SCHEMA`.
        tolerance_days: le nombre de jours dont une observation peut dépasser
            son millésime sans faire lever. Zéro par défaut.

    Raises:
        LookAheadError: si au moins une ligne dépasse la tolérance. Le message
            nomme la première ligne fautive et compte les autres.

    Note:
        Attention à la convention de datage de FRED : une observation
        trimestrielle est datée du PREMIER jour de son trimestre. Le premier
        trimestre de 2008 porte donc la date du 2008-01-01 et se publie le
        2008-04-30. Le contrôle passe, alors que la période décrite se termine
        pourtant après le début du trimestre. Ce contrôle attrape un panneau
        mal assemblé, pas un décalage de publication.
    """
    if panel.empty:
        return
    ecart = (panel[OBSERVATION_DATE] - panel[VINTAGE_DATE]).dt.days
    fautives = panel.loc[ecart > tolerance_days]
    if not fautives.empty:
        first = fautives.iloc[0]
        raise LookAheadError(
            f"{len(fautives)} ligne(s) datent d'après leur millésime, "
            f"la première décrivant le {first[OBSERVATION_DATE].date()} "
            f"pour un millésime du {first[VINTAGE_DATE].date()}"
        )


def as_of(panel: pd.DataFrame, date: dt.date | dt.datetime | str) -> pd.DataFrame:
    r"""Rend l'état du panneau tel qu'il était connaissable à la date demandée.

    (1) Le problème : un backtest daté du 15 mai 2008 doit lire la série dans sa
    version du 15 mai 2008, et aucune version postérieure, sans quoi son
    rendement mesure les révisions. (2) L'intuition : pour chaque date
    d'observation, garder le millésime le plus récent parmi ceux qui ne
    dépassent pas la date demandée.

    (3) La sélection, formellement :

    .. math::

        v^{(d)}(t) = v\big(t,\; \max\{ s \in V(t) : s \leq d \}\big)

    (4) Les variables : :math:`t` est la date d'observation et :math:`d` la date
    demandée. L'ensemble :math:`V(t)` porte les millésimes qui donnent une valeur
    pour :math:`t`, et :math:`v(t, s)` est la valeur publiée au millésime
    :math:`s`. Une observation dont aucun millésime ne précède :math:`d`
    disparaît, ce qui est le comportement voulu : à cette date, elle n'était pas
    publiée.

    (5) Les hypothèses : le panneau porte les colonnes :data:`PANEL_SCHEMA`, et
    une date de millésime est une date de publication et non de collecte.

    Args:
        panel: le panneau des millésimes.
        date: la date à laquelle on se place.

    Returns:
        Un tableau indexé par date d'observation, deux colonnes, la valeur et le
        millésime dont elle vient. Vide, au bon schéma, quand aucun millésime ne
        précède la date.

    Raises:
        DataQualityError: si le panneau ne porte pas les colonnes attendues.

    Example:
        Sur un panneau de ``GDPC1`` fait des millésimes 2008-04-30 et
        2026-08-01, ``as_of(panel, "2008-06-30")`` rend 11 693,1 pour le premier
        trimestre de 2008, valeur mesurée le 2026-09-01, et jamais 16 843,003.

    Note:
        Limites (7) : la date de millésime n'a pas d'heure, donc une publication
        du matin et une décision du soir tombent le même jour et deviennent
        indistinctes. Pour une stratégie qui traite dans la journée, décaler
        d'une séance après ce filtre. Seconde limite, lisible dans la définition
        de :math:`V(t)` : un millésime qui cesse de LISTER une observation ne la
        retire pas, et c'est la dernière valeur publiée qui reste rendue. Le
        retrait ne s'exprime que par une valeur absente, écriture qu'ALFRED
        emploie et que le panneau conserve. Alternatives (8) : une jointure
        ``merge_asof`` sur les millésimes, qui fait le même travail mais impose
        un tri préalable et se trompe en silence s'il manque. Choix (9) : le
        filtre puis la dernière ligne par groupe se lisent en deux lignes, et
        chacune est testable seule. Vérification (10) : un test de propriété
        tire des panneaux au hasard et vérifie que le millésime rendu ne dépasse
        jamais la date demandée. Un second vérifie qu'une date plus tardive ne
        rend jamais un millésime plus ancien.
    """
    manquantes = [colonne for colonne in PANEL_SCHEMA if colonne not in panel.columns]
    if manquantes:
        raise DataQualityError(f"le panneau ne porte pas les colonnes {manquantes}")
    limite = pd.Timestamp(_as_date(date))
    visible = panel.loc[panel[VINTAGE_DATE] <= limite]
    if visible.empty:
        vide = empty_panel().set_index(OBSERVATION_DATE)
        return vide[[VALUE, VINTAGE_DATE]]
    ordonne = visible.sort_values([OBSERVATION_DATE, VINTAGE_DATE], kind="stable")
    dernier = ordonne.groupby(OBSERVATION_DATE, as_index=False, sort=True).tail(1)
    return dernier.set_index(OBSERVATION_DATE)[[VALUE, VINTAGE_DATE]]


@dataclass(frozen=True, slots=True)
class VintagePanel:
    """Un panneau de millésimes qui répond à « que savait-on le jour J ».

    La classe tient le protocole
    :class:`quantlab.core.protocols.PointInTimeDataset` : elle porte une seule
    méthode qui compte, :meth:`as_of`. Elle n'ajoute aucun calcul à
    :func:`as_of`, elle lui donne un objet à qui la question se pose.

    Attributes:
        series_id: l'identifiant de la série décrite.
        frame: le panneau au schéma :data:`PANEL_SCHEMA`.

    Example:
        .. code-block:: python

            panneau = VintagePanel("GDPC1", build_vintage_panel(millesimes))
            connu = panneau.as_of("2008-06-30")
    """

    series_id: str
    frame: pd.DataFrame

    def as_of(self, date: dt.date | str) -> pd.DataFrame:
        """Rend l'état connaissable à ``date``, voir :func:`as_of`."""
        return as_of(self.frame, date)

    @property
    def vintage_dates(self) -> tuple[dt.date, ...]:
        """Rend les dates de millésime présentes, triées, sans doublon."""
        if self.frame.empty:
            return ()
        uniques = pd.DatetimeIndex(self.frame[VINTAGE_DATE].unique()).sort_values()
        return tuple(stamp.date() for stamp in uniques)

    @property
    def observation_dates(self) -> pd.DatetimeIndex:
        """Rend les dates d'observation présentes, triées, sans doublon."""
        if self.frame.empty:
            return pd.DatetimeIndex([], name=OBSERVATION_DATE, dtype=DATETIME_DTYPE)
        return pd.DatetimeIndex(self.frame[OBSERVATION_DATE].unique(), name=OBSERVATION_DATE).sort_values()

    def revisions(self, observation_date: dt.date | str) -> pd.Series:
        """Rend la suite des valeurs publiées pour une même observation.

        C'est la vue qui montre la révision elle-même : l'index porte les
        millésimes, les valeurs disent ce que la source annonçait à chacun.

        Args:
            observation_date: la période décrite.

        Returns:
            Une série indexée par millésime, triée, éventuellement vide.
        """
        cible = pd.Timestamp(_as_date(observation_date))
        lignes = self.frame.loc[self.frame[OBSERVATION_DATE] == cible]
        serie = lignes.set_index(VINTAGE_DATE)[VALUE].sort_index()
        return serie.rename(self.series_id)


# --------------------------------------------------------------------------- #
# Les fournisseurs
# --------------------------------------------------------------------------- #


def _manifest(
    *,
    dataset_id: str,
    provider_name: str,
    url: str,
    fetched_at: dt.datetime,
    index: pd.DatetimeIndex,
    frequency: Frequency | None,
    columns: tuple[str, ...],
    n_rows: int,
    point_in_time: bool,
    revision_policy: str,
    checksum: str,
    notes: str,
) -> DatasetManifest:
    """Rend le manifeste commun aux deux fournisseurs, seul ``point_in_time`` changeant."""
    if len(index) == 0:
        raise InsufficientDataError(f"« {dataset_id} » ne porte aucune observation, manifeste impossible")
    resolue = frequency if frequency is not None else infer_frequency(index)
    return DatasetManifest(
        dataset_id=dataset_id,
        source="Federal Reserve Bank of St. Louis, export CSV public sans clé",
        provider=f"quantlab.data.providers.{provider_name}",
        url=url,
        download_timestamp=fetched_at,
        data_start=index.min().date(),
        data_end=index.max().date(),
        frequency=resolue,
        timezone="",
        exchange=None,
        currency="",
        adjusted=False,
        point_in_time=point_in_time,
        survivorship_free=None,
        corporate_actions="sans objet, série macroéconomique",
        revision_policy=revision_policy,
        license=LICENSE,
        license_url=LICENSE_URL,
        checksum_sha256=checksum,
        n_rows=n_rows,
        n_columns=len(columns),
        columns=columns,
        processing_version=PROCESSING_VERSION,
        layer=Layer.RAW,
        notes=notes,
    )


class FredProvider(BaseProvider):
    """Télécharge la DERNIÈRE version d'une série, et le déclare dans son manifeste.

    Le fournisseur convient à une description du passé, par exemple un graphique
    de l'inflation depuis 1960. Il ne convient pas à un backtest : son manifeste
    porte ``point_in_time`` à faux, et un moteur de backtest doit refuser une
    entrée ainsi marquée.

    Attributes:
        name: « fred », qui nomme aussi le dossier du cache brut.

    Example:
        .. code-block:: python

            fournisseur = FredProvider()
            taux = fournisseur.fetch("DGS10", start="2020-01-01", end="2020-01-10")
            fournisseur.manifest().point_in_time  # False, toujours
    """

    name: ClassVar[str] = FRED_PROVIDER_NAME

    #: L'adresse de l'export, dérivable pour un miroir ou un test.
    csv_url: ClassVar[str] = FRED_CSV_URL

    def __init__(self, **kwargs: Any) -> None:
        """Construit le fournisseur, arguments passés à :class:`BaseProvider`.

        Args:
            **kwargs: ``client``, ``raw_root`` et ``now``, voir
                :class:`quantlab.data.providers.base.BaseProvider`. Un test hors
                réseau passe un client factice et un ``raw_root`` temporaire.
        """
        super().__init__(**kwargs)
        self._last: dict[str, Any] | None = None

    def fetch(
        self,
        series_id: str,
        *,
        start: dt.date | str | None = None,
        end: dt.date | str | None = None,
        refresh: bool = False,
        frequency: Frequency | None = None,
    ) -> pd.DataFrame:
        """Télécharge une série et la rend en tableau indexé par la date d'observation.

        Args:
            series_id: l'identifiant FRED, par exemple ``« DGS10 »``.
            start: première date rendue, incluse. Sans valeur, tout l'historique.
            end: dernière date rendue, incluse. Sans valeur, jusqu'au dernier
                point publié.
            refresh: force un nouveau téléchargement au lieu de relire le cache
                brut.
            frequency: la fréquence déclarée au manifeste. Sans valeur, elle est
                déduite de l'index par :func:`infer_frequency`.

        Returns:
            Un tableau d'une colonne, nommée par l'identifiant, indexée par un
            ``DatetimeIndex`` nommé ``« observation_date »``.

        Raises:
            ValueError: si ``series_id`` est vide, ou si ``start`` suit ``end``.
            InsufficientDataError: si la source ne rend aucune observation, ou
                si la fenêtre demandée est vide.
            DataQualityError: si le CSV reçu viole le format attendu.

        Note:
            Les bornes sont envoyées à la source par les paramètres ``cosd`` et
            ``coed``, mesurés le 2026-09-01 sur ``DGS10`` du 2020-01-01 au
            2020-01-10, qui rendent sept séances. Le découpage est refait
            localement, la borne haute de la source n'étant pas garantie
            inclusive par sa documentation.
        """
        identifiant = str(series_id).strip().upper()
        if not identifiant:
            raise ValueError("aucun identifiant de série demandé")
        debut = _as_date(start) if start is not None else None
        fin = _as_date(end) if end is not None else None
        if debut is not None and fin is not None and debut > fin:
            raise ValueError(f"start ({debut}) suit end ({fin})")

        params: dict[str, str] = {"id": identifiant}
        if debut is not None:
            params["cosd"] = debut.isoformat()
        if fin is not None:
            params["coed"] = fin.isoformat()

        with stage("fred.fetch", provider=self.name, series_id=identifiant) as payload:
            raw = self.fetch_cached(self.csv_url, params=params, label=identifiant, refresh=refresh)
            serie = parse_fred_csv(raw.text(), series_id=identifiant)
            serie = _slice(serie, debut, fin)
            payload["rows"] = len(serie)

        if serie.empty:
            raise InsufficientDataError(
                f"« {identifiant} » ne porte aucune observation entre {debut} et {fin}"
            )
        self._last = {
            "series_id": identifiant,
            "url": raw.url,
            "checksum": raw.sha256,
            "fetched_at": raw.fetched_at,
            "index": serie.index,
            "rows": len(serie),
            "frequency": frequency,
        }
        return serie.to_frame()

    def manifest(self, **overrides: Any) -> DatasetManifest:
        """Rend le manifeste de la dernière extraction, ``point_in_time`` à faux.

        Args:
            **overrides: remplace un champ du dernier téléchargement. Clés
                acceptées : ``series_id``, ``url``, ``checksum``, ``fetched_at``,
                ``index``, ``rows``, ``frequency``.

        Returns:
            Le manifeste validé.

        Raises:
            ConfigError: si aucun téléchargement n'a eu lieu et que les
                remplacements ne suffisent pas.
            ValueError: si une clé de remplacement est inconnue.
        """
        base = _manifest_base(self._last, overrides)
        return _manifest(
            dataset_id=f"fred-{str(base['series_id']).lower()}",
            provider_name=self.name,
            url=str(base["url"]),
            fetched_at=base["fetched_at"],
            index=base["index"],
            frequency=base.get("frequency"),
            columns=(str(base["series_id"]),),
            n_rows=int(base["rows"]),
            point_in_time=False,
            revision_policy=FRED_REVISION_POLICY,
            checksum=str(base.get("checksum", "")),
            notes=(
                "Série dans sa dernière version. Elle ne dit pas ce qui était publié "
                "à une date passée, donc elle ne convient pas à un backtest. " + " ".join(KNOWN_LIMITATIONS)
            ),
        )


class AlfredProvider(BaseProvider):
    """Télécharge une série TELLE QU'ELLE ÉTAIT PUBLIÉE à une date choisie.

    C'est le seul des deux fournisseurs dont le manifeste porte
    ``point_in_time`` à vrai, et cette différence d'un booléen décide de ce
    qu'un backtest a le droit de lire.

    Attributes:
        name: « alfred », qui nomme aussi le dossier du cache brut.

    Example:
        .. code-block:: python

            fournisseur = AlfredProvider()
            panneau = fournisseur.vintage_panel("GDPC1", ["2008-04-30", "2026-08-01"])
            connu_en_2008 = as_of(panneau, "2008-06-30")
    """

    name: ClassVar[str] = ALFRED_PROVIDER_NAME

    #: L'adresse de l'export, dérivable pour un miroir ou un test.
    csv_url: ClassVar[str] = ALFRED_CSV_URL

    def __init__(self, **kwargs: Any) -> None:
        """Construit le fournisseur, arguments passés à :class:`BaseProvider`.

        Args:
            **kwargs: ``client``, ``raw_root`` et ``now``, voir
                :class:`quantlab.data.providers.base.BaseProvider`.
        """
        super().__init__(**kwargs)
        self._last: dict[str, Any] | None = None

    def fetch_vintage(
        self,
        series_id: str,
        vintage_date: dt.date | str,
        *,
        start: dt.date | str | None = None,
        end: dt.date | str | None = None,
        refresh: bool = False,
    ) -> pd.Series:
        """Rend la série telle qu'elle était publiée au millésime demandé.

        Args:
            series_id: l'identifiant ALFRED, par exemple ``« GDPC1 »``.
            vintage_date: la date de publication, c'est-à-dire la date à
                laquelle on se place.
            start: première date d'observation rendue, incluse.
            end: dernière date d'observation rendue, incluse.
            refresh: force un nouveau téléchargement.

        Returns:
            Une série de ``float64`` nommée par l'identifiant, indexée par la
            date d'observation.

        Raises:
            ValueError: si l'identifiant est vide.
            InsufficientDataError: si le millésime ne porte aucune observation.
            DataQualityError: si le CSV reçu viole le format attendu.

        Note:
            La date de millésime n'a pas besoin d'être une date de publication
            réelle. ALFRED rend l'état connu ce jour-là, donc une date quelconque
            rend le dernier état antérieur, mesuré le 2026-09-01 sur ``GDPC1``
            au millésime du 2008-06-26, un jeudi sans publication de PIB.
        """
        identifiant = str(series_id).strip().upper()
        if not identifiant:
            raise ValueError("aucun identifiant de série demandé")
        millesime = _as_date(vintage_date)
        debut = _as_date(start) if start is not None else None
        fin = _as_date(end) if end is not None else None

        params: dict[str, str] = {"id": identifiant, "vintage_date": millesime.isoformat()}
        if debut is not None:
            params["cosd"] = debut.isoformat()
        if fin is not None:
            params["coed"] = fin.isoformat()

        with stage(
            "alfred.fetch_vintage",
            provider=self.name,
            series_id=identifiant,
            vintage_date=millesime.isoformat(),
        ) as payload:
            raw = self.fetch_cached(
                self.csv_url,
                params=params,
                label=f"{identifiant}-{millesime.isoformat()}",
                refresh=refresh,
            )
            serie = parse_fred_csv(raw.text(), series_id=identifiant)
            serie = _slice(serie, debut, fin)
            payload["rows"] = len(serie)

        if serie.empty:
            raise InsufficientDataError(
                f"« {identifiant} » ne porte aucune observation au millésime {millesime}"
            )
        self._last = {
            "series_id": identifiant,
            "url": raw.url,
            "checksum": raw.sha256,
            "fetched_at": raw.fetched_at,
            "index": serie.index,
            "rows": len(serie),
            "vintages": (millesime,),
            "frequency": None,
        }
        return serie

    def vintage_panel(
        self,
        series_id: str,
        vintage_dates: Iterable[dt.date | str],
        *,
        start: dt.date | str | None = None,
        end: dt.date | str | None = None,
        refresh: bool = False,
        dropna: bool = False,
    ) -> pd.DataFrame:
        """Rend le panneau des millésimes demandés, prêt pour le module point-in-time.

        Args:
            series_id: l'identifiant ALFRED.
            vintage_dates: les dates de publication demandées. Les doublons sont
                retirés, l'ordre est refait par tri.
            start: première date d'observation rendue, incluse.
            end: dernière date d'observation rendue, incluse.
            refresh: force un nouveau téléchargement de chaque millésime.
            dropna: retire les lignes de valeur absente.

        Returns:
            Le panneau au schéma :data:`PANEL_SCHEMA`.

        Raises:
            ValueError: si aucune date de millésime n'est demandée.

        Note:
            Un appel par millésime, donc autant de requêtes que de dates. Le
            cache brut de :class:`BaseProvider` évite de les refaire, un
            millésime étant figé par définition.

            Deux précautions valent d'être dites, parce qu'elles ont chacune
            produit un manifeste faux avant d'être corrigées le 2026-09-01.
            L'index déclaré au manifeste porte les dates d'observation SANS
            doublon. Le panneau répète chaque trimestre une fois par millésime,
            l'écart médian de ces répétitions vaut zéro jour, et une série
            trimestrielle se déclarerait alors quotidienne. L'empreinte
            déclarée est celle des millésimes assemblés, par
            :func:`combine_checksums`, et non la chaîne vide.
        """
        millesimes = sorted({_as_date(v) for v in vintage_dates})
        if not millesimes:
            raise ValueError("aucune date de millésime demandée")
        series: dict[dt.date | str, pd.Series] = {}
        checksums: list[str] = []
        derniere: dict[str, Any] = {}
        for millesime in millesimes:
            series[millesime] = self.fetch_vintage(
                series_id, millesime, start=start, end=end, refresh=refresh
            )
            derniere = dict(self._last or {})
            checksums.append(str(derniere.get("checksum", "")))

        panel = build_vintage_panel(series, dropna=dropna)
        self._last = {
            **derniere,
            "index": pd.DatetimeIndex(panel[OBSERVATION_DATE].unique(), name=OBSERVATION_DATE),
            "rows": len(panel),
            "vintages": tuple(millesimes),
            "checksum": combine_checksums(checksums),
            "columns": PANEL_SCHEMA,
        }
        log.info(
            "panneau de millésimes construit",
            extra={
                "series_id": str(series_id).strip().upper(),
                "vintages": len(millesimes),
                "rows": len(panel),
            },
        )
        return panel

    def fetch(
        self,
        series_id: str,
        *,
        start: dt.date | str | None = None,
        end: dt.date | str | None = None,
        vintage_dates: Iterable[dt.date | str] | None = None,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """Rend le panneau des millésimes demandés, ou le millésime du jour.

        Args:
            series_id: l'identifiant ALFRED.
            start: première date d'observation rendue, incluse.
            end: dernière date d'observation rendue, incluse.
            vintage_dates: les millésimes voulus. Sans valeur, le millésime du
                jour, c'est-à-dire l'état publié aujourd'hui.
            refresh: force un nouveau téléchargement.

        Returns:
            Le panneau au schéma :data:`PANEL_SCHEMA`.
        """
        voulus = list(vintage_dates) if vintage_dates is not None else [dt.date.today()]
        return self.vintage_panel(series_id, voulus, start=start, end=end, refresh=refresh)

    def manifest(self, **overrides: Any) -> DatasetManifest:
        """Rend le manifeste de la dernière extraction, ``point_in_time`` à vrai.

        Args:
            **overrides: remplace un champ du dernier téléchargement. Clés
                acceptées : ``series_id``, ``url``, ``checksum``, ``fetched_at``,
                ``index``, ``rows``, ``frequency``, ``vintages``, ``columns``.

        Returns:
            Le manifeste validé, dont ``point_in_time`` vaut vrai.

        Raises:
            ConfigError: si aucun téléchargement n'a eu lieu et que les
                remplacements ne suffisent pas.
            ValueError: si une clé de remplacement est inconnue.
        """
        base = _manifest_base(self._last, overrides)
        millesimes = tuple(base.get("vintages") or ())
        colonnes = tuple(base.get("columns") or (str(base["series_id"]),))
        etendue = (
            f"{millesimes[0].isoformat()} à {millesimes[-1].isoformat()}" if millesimes else "non trouvé"
        )
        return _manifest(
            dataset_id=f"alfred-{str(base['series_id']).lower()}-{len(millesimes)}v",
            provider_name=self.name,
            url=str(base["url"]),
            fetched_at=base["fetched_at"],
            index=base["index"],
            frequency=base.get("frequency"),
            columns=colonnes,
            n_rows=int(base["rows"]),
            point_in_time=True,
            revision_policy=ALFRED_REVISION_POLICY,
            checksum=str(base.get("checksum", "")),
            notes=(
                f"{len(millesimes)} millésime(s), de {etendue}. "
                "Chaque valeur porte la date à laquelle elle était publiée. " + " ".join(KNOWN_LIMITATIONS)
            ),
        )


#: Les clés qu'un manifeste accepte en remplacement.
_MANIFEST_KEYS: Final[frozenset[str]] = frozenset(
    {"series_id", "url", "checksum", "fetched_at", "index", "rows", "frequency", "vintages", "columns"}
)

#: Les clés sans lesquelles aucun manifeste ne se construit.
_MANIFEST_REQUIRED: Final[tuple[str, ...]] = ("series_id", "url", "fetched_at", "index", "rows")


def _manifest_base(last: dict[str, Any] | None, overrides: Mapping[str, Any]) -> dict[str, Any]:
    """Rend le dictionnaire de manifeste, dernier téléchargement complété des remplacements.

    Raises:
        ValueError: si une clé de remplacement est inconnue.
        ConfigError: si une clé obligatoire manque, faute de téléchargement.
    """
    inconnues = sorted(set(overrides) - _MANIFEST_KEYS)
    if inconnues:
        raise ValueError(f"clés de manifeste inconnues : {inconnues} ; acceptées : {sorted(_MANIFEST_KEYS)}")
    base: dict[str, Any] = dict(last or {})
    base.update(overrides)
    manquantes = [cle for cle in _MANIFEST_REQUIRED if base.get(cle) is None]
    if manquantes:
        raise ConfigError(
            f"le manifeste exige un téléchargement préalable, ou les clés {manquantes} en remplacement"
        )
    return base


def _slice(serie: pd.Series, start: dt.date | None, end: dt.date | None) -> pd.Series:
    """Rend la série bornée aux deux dates, chacune incluse quand elle est donnée."""
    borne = serie
    if start is not None:
        borne = borne.loc[borne.index >= pd.Timestamp(start)]
    if end is not None:
        borne = borne.loc[borne.index <= pd.Timestamp(end)]
    return borne

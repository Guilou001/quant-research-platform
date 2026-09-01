"""Le calendrier d'échange, et pourquoi 252 est une convention à vérifier.

**Le problème.** Annualiser une volatilité quotidienne en la multipliant par
racine de 252 suppose que l'année porte 252 séances. Elle n'en porte presque
jamais exactement 252, le nombre varie d'une année et d'un marché à l'autre, et
l'écart se propage tel quel dans tous les ratios de Sharpe publiés.

**Ce que ce module rend possible.** Compter les séances réellement ouvertes
plutôt que les supposer, distinguer une séance écourtée d'une séance pleine,
et refuser de traiter une date qui n'est pas une séance. Il s'appuie sur
``exchange_calendars``, qui porte les jours fériés, les fermetures
exceptionnelles et les séances écourtées de plus de cinquante places.

**Limite déclarée.** ``exchange_calendars`` est une base entretenue par la
communauté, pas un registre officiel. Les fermetures exceptionnelles anciennes,
avant 1990, y sont moins fiables que les récentes.
"""

from __future__ import annotations

import datetime as dt
import functools

import pandas as pd

from quantlab.core.errors import InsufficientDataError
from quantlab.core.types import Frequency

#: Calendrier par défaut du laboratoire : la Bourse de New York.
DEFAULT_CALENDAR = "XNYS"


@functools.lru_cache(maxsize=32)
def get_calendar(name: str = DEFAULT_CALENDAR):  # type de retour opaque, fixé par exchange_calendars
    """Rend un calendrier d'échange, mis en cache.

    Args:
        name: le code ISO 10383 du marché, par exemple ``"XNYS"`` pour New York,
            ``"XTSE"`` pour Toronto, ``"XLON"`` pour Londres.
    """
    import exchange_calendars as xcals

    return xcals.get_calendar(name)


def sessions(
    start: str | dt.date,
    end: str | dt.date,
    calendar: str = DEFAULT_CALENDAR,
) -> pd.DatetimeIndex:
    """Rend les séances ouvertes de la période, bornes incluses."""
    cal = get_calendar(calendar)
    return cal.sessions_in_range(pd.Timestamp(start), pd.Timestamp(end))


def sessions_per_year(
    start: str | dt.date,
    end: str | dt.date,
    calendar: str = DEFAULT_CALENDAR,
) -> float:
    """Compte les séances réelles par an sur la période, au lieu de supposer 252.

    Le calcul divise le nombre de séances ouvertes par la durée de la période en
    années de 365,25 jours.

    Args:
        start: première date de la période.
        end: dernière date de la période.
        calendar: le marché dont on compte les séances.

    Returns:
        Le nombre moyen de séances par an, mesuré.

    Raises:
        InsufficientDataError: si la période ne contient aucune séance.

    Example:
        Mesuré le 2026-09-01 : la Bourse de New York a ouvert 2 516 fois entre
        le 1er janvier 2010 et le 31 décembre 2019, soit 251,703 séances par an
        sur 9,996 année. L'écart avec la convention de 252 déplace une
        volatilité annualisée de 0,059 % en valeur relative, ce qui est
        négligeable ici et ne l'est plus sur un marché qui ferme souvent.
    """
    idx = sessions(start, end, calendar)
    if len(idx) == 0:
        raise InsufficientDataError(f"aucune séance de {calendar} entre {start} et {end}")
    span_years = (pd.Timestamp(end) - pd.Timestamp(start)).days / 365.25
    if span_years <= 0:
        raise InsufficientDataError("la période est de durée nulle")
    return len(idx) / span_years


def annualization_factor(
    frequency: Frequency,
    *,
    measured_over: tuple[str | dt.date, str | dt.date] | None = None,
    calendar: str = DEFAULT_CALENDAR,
) -> float:
    r"""Rend le facteur d'annualisation, conventionnel ou mesuré.

    Args:
        frequency: la fréquence d'observation de la série.
        measured_over: si donné et si la fréquence est quotidienne, compte les
            séances réelles de cette période au lieu d'appliquer 252.
        calendar: le marché servant au comptage.

    Returns:
        Le nombre de périodes par an à utiliser dans
        :math:`\sigma_{ann} = \sigma \sqrt{N}`.

    Note:
        Le comptage mesuré n'a de sens qu'en quotidien. Un mois reste un
        douzième d'année quel que soit le calendrier.
    """
    if measured_over is not None and frequency is Frequency.DAILY:
        return sessions_per_year(measured_over[0], measured_over[1], calendar)
    return frequency.periods_per_year


def is_session(date: str | dt.date, calendar: str = DEFAULT_CALENDAR) -> bool:
    """Dit si la date est une séance ouverte du marché."""
    return get_calendar(calendar).is_session(pd.Timestamp(date))


def next_session(date: str | dt.date, calendar: str = DEFAULT_CALENDAR) -> pd.Timestamp:
    """Rend la première séance strictement postérieure à la date.

    Sert à poser une décision au bon moment. Un signal calculé sur la clôture
    du jour ``t`` se négocie au plus tôt à la séance suivante, et cette fonction
    est ce qui empêche de l'oublier.
    """
    return get_calendar(calendar).next_session(pd.Timestamp(date))


def previous_session(date: str | dt.date, calendar: str = DEFAULT_CALENDAR) -> pd.Timestamp:
    """Rend la dernière séance strictement antérieure à la date."""
    return get_calendar(calendar).previous_session(pd.Timestamp(date))


def early_closes(
    start: str | dt.date,
    end: str | dt.date,
    calendar: str = DEFAULT_CALENDAR,
) -> pd.DatetimeIndex:
    """Rend les séances écourtées de la période.

    Une séance écourtée porte moins de volume et un écart acheteur-vendeur plus
    large. Une stratégie intrajournalière qui les traite comme des séances
    pleines surestime sa capacité.
    """
    cal = get_calendar(calendar)
    ec = cal.early_closes
    mask = (ec >= pd.Timestamp(start)) & (ec <= pd.Timestamp(end))
    return pd.DatetimeIndex(ec[mask])

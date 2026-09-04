r"""Le momentum de série temporelle, écrit d'après les équations de l'article.

**Le problème.** Moskowitz, Ooi et Pedersen (2012) publient quatre équations et
une phrase de dimensionnement. Entre ces quatre équations et une série de
rendements mensuels, il reste six conventions à trancher, et chacune déplace le
résultat. Ce module les tranche une fois, les documente, et les rend testables.

**L'intuition.** Chaque instrument est regardé seul. Le signe de son rendement
excédentaire des douze derniers mois décide du sens de la position. La taille de
la position est inversement proportionnelle à la volatilité estimée la veille,
de sorte que chaque instrument apporte le même risque au portefeuille. Le
portefeuille est la moyenne équipondérée des instruments disponibles.

**Les quatre équations recopiées.** La volatilité ex ante,

.. math::

    \sigma_t^2 = \kappa \sum_{i=0}^{\infty} (1-\delta)\,\delta^{\,i}\,
                 \left(r_{t-1-i} - \bar{r}_t\right)^2

où :math:`\kappa` vaut 261 dans l'article, :math:`\delta` se déduit du centre de
masse par :math:`\delta = c/(c+1)` avec :math:`c` égal à 60 jours, et
:math:`\bar{r}_t` est la moyenne pondérée des mêmes poids. Le signal,

.. math::

    S^s_t = \operatorname{sign}\left(r^s_{t-k,t}\right)

Le rendement d'un instrument, puis celui du portefeuille diversifié sur les
:math:`S_t` instruments disponibles,

.. math::

    r^{\text{TSMOM},s}_{t,t+1} = S^s_t \frac{\lambda}{\sigma^s_t}\, r^s_{t,t+1}
    \qquad
    r^{\text{TSMOM}}_{t,t+1} = \frac{1}{S_t} \sum_{s=1}^{S_t}
        S^s_t \frac{\lambda}{\sigma^s_t}\, r^s_{t,t+1}

où :math:`\lambda` est la volatilité cible, 40 % dans l'article.

**Les six conventions tranchées ici, toutes déclarées.**

Un, la somme infinie est tronquée à l'échantillon disponible et ses poids sont
renormalisés, ce que fait ``adjust=True`` de pandas.

Deux, l'indice :math:`t-1-i` de l'équation est pris au pied de la lettre : la
volatilité datée du jour :math:`t` n'utilise aucun rendement du jour
:math:`t`. Le décalage d'un jour est donc écrit dans la fonction.

Trois, la volatilité retenue à la date de décision mensuelle est celle du
dernier jour de bourse du mois, donc calculée sur les rendements jusqu'à
l'avant-dernier.

Quatre, une position dont la volatilité ou le signal manque est absente du
portefeuille, et le diviseur :math:`S_t` ne la compte pas.

Cinq, pour une détention de :math:`h` mois, la position agrégée est la moyenne
des positions des cohortes encore actives, chacune gardant le signe ET la
volatilité de sa propre date de formation. C'est la lecture littérale de
« la moyenne des rendements de tous les portefeuilles encore actifs ».

Six, la division par :math:`S_t` intervient APRÈS la moyenne des cohortes, ce
qui garde l'équipondération à chaque date plutôt qu'à chaque date de formation.

**Ce que ce module n'implémente pas.** Aucune métrique de performance. Le ratio
de Sharpe vit dans :mod:`quantlab.analytics.ratios`, le rendement du
portefeuille sort de :func:`quantlab.backtest.engine.run_backtest`, et le signe
du rendement cumulé sort de
:func:`quantlab.features.transforms.time_series_momentum_signal`.

**Pourquoi une volatilité écrite ici plutôt que celle de**
``features.transforms``. Elles ne calculent pas la même chose.
:func:`quantlab.features.transforms.ewma_volatility` prend la moyenne
exponentielle des carrés, donc sans retrancher la moyenne, annualise par 252 et
ne décale pas. L'article retranche la moyenne, annualise par 261 et décale d'un
jour. Les trois écarts sont matériels sur la taille des positions, et le second
vaut à lui seul 1,77 % de volatilité.

**Limites connues.** Le modèle de volatilité n'a pas de retour à la moyenne.
Aucune borne n'est posée sur la taille de position, si bien qu'un actif à 1,5 %
de volatilité reçoit un levier de vingt-six fois pour atteindre 40 %. Cette
absence de borne est celle de l'article, dont l'univers est fait de contrats à
terme. Sur des fonds négociés en bourse, elle n'est pas exécutable.
:func:`position_sizes` accepte donc un plafond facultatif, qui vaut l'infini
par défaut.

**Provenance.** Moskowitz, T. J., Ooi, Y. H. et Pedersen, L. H. (2012). Time
series momentum. *Journal of Financial Economics*, 104(2), 228-250.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.logging import get_logger
from quantlab.features.transforms import time_series_momentum_signal

__all__ = [
    "DEFAULT_ANNUALIZATION_DAYS",
    "DEFAULT_CENTER_OF_MASS_DAYS",
    "DEFAULT_HOLDING",
    "DEFAULT_LOOKBACK",
    "DEFAULT_TARGET_VOLATILITY",
    "PAPER_GRID",
    "cohort_positions",
    "diversified_weights",
    "ex_ante_volatility",
    "formation_signal",
    "grid_weights",
    "position_sizes",
    "smoothing_from_center_of_mass",
    "tsmom_weights",
]

_LOG = get_logger(__name__)

#: Le centre de masse des poids de la volatilité ex ante, en jours de bourse.
#: RAPPORTÉ de l'article, qui publie la condition et jamais le lissage.
DEFAULT_CENTER_OF_MASS_DAYS = 60.0

#: Le facteur d'annualisation de la variance quotidienne. RAPPORTÉ de
#: l'article, qui écrit 261 et non les 252 usuels.
DEFAULT_ANNUALIZATION_DAYS = 261.0

#: La volatilité annualisée visée par chaque position. RAPPORTÉ de l'article.
DEFAULT_TARGET_VOLATILITY = 0.40

#: La fenêtre de formation retenue par l'article pour son analyse détaillée.
DEFAULT_LOOKBACK = 12

#: La durée de détention retenue par l'article pour son analyse détaillée.
DEFAULT_HOLDING = 1

#: Les huit valeurs de formation et de détention du tableau 2 de l'article.
PAPER_GRID: tuple[int, ...] = (1, 3, 6, 9, 12, 24, 36, 48)


def smoothing_from_center_of_mass(center_of_mass: float) -> float:
    r"""Rend le lissage :math:`\delta` qui donne le centre de masse demandé.

    **Le problème.** L'article publie la condition
    :math:`\sum_i (1-\delta)\delta^i\, i = 60` et jamais la valeur de
    :math:`\delta`. Un code qui devine le lissage se trompe de taille de
    position sur chaque actif et chaque date.

    **La formule.** La somme vaut :math:`\delta/(1-\delta)`, donc

    .. math::

        \delta = \frac{c}{c+1}

    où :math:`c` est le centre de masse demandé, en jours de bourse.

    **Hypothèses.** Les poids somment à un et décroissent géométriquement, ce
    qui est la forme posée par l'article.

    **Limites.** Le centre de masse ne suffit pas à décrire la pondération quand
    l'échantillon est court : la troncature déplace le centre de masse effectif
    vers le présent.

    **Comment vérifier.** Un centre de masse de 60 rend 60/61, soit environ
    0,983607, et la demi-vie correspondante vaut environ 41,94 jours.

    Args:
        center_of_mass: le centre de masse demandé, strictement positif.

    Returns:
        Le lissage :math:`\delta`, dans l'intervalle ouvert de 0 à 1.

    Raises:
        ConfigError: si le centre de masse n'est pas strictement positif.

    Example:
        >>> round(smoothing_from_center_of_mass(60.0), 6)
        0.983607
    """
    if not math.isfinite(center_of_mass) or center_of_mass <= 0.0:
        raise ConfigError(f"le centre de masse doit être strictement positif, reçu {center_of_mass}.")
    return float(center_of_mass / (center_of_mass + 1.0))


def ex_ante_volatility(
    daily_returns: pd.DataFrame,
    *,
    center_of_mass: float = DEFAULT_CENTER_OF_MASS_DAYS,
    annualization_days: float = DEFAULT_ANNUALIZATION_DAYS,
    min_periods: int = 60,
) -> pd.DataFrame:
    r"""Rend la volatilité ex ante annualisée de l'article, jour par jour.

    **Le problème.** Dimensionner une position à l'inverse de sa volatilité
    suppose une volatilité connue AVANT le rendement qu'elle dimensionne. Une
    estimation qui inclut le jour courant produit un backtest qui sait ce qu'il
    va se passer, et le gain apparent est spectaculaire.

    **L'intuition.** Une moyenne exponentielle des écarts au carré, dont les
    poids décroissent en s'éloignant du présent, puis un décalage d'un jour pour
    fermer la porte à l'information du jour.

    **La formule, celle de l'article.**

    .. math::

        \sigma_t^2 = \kappa \sum_{i=0}^{\infty} (1-\delta)\,\delta^{\,i}\,
                     \left(r_{t-1-i} - \bar{r}_t\right)^2,
        \qquad
        \bar{r}_t = \sum_{i=0}^{\infty} (1-\delta)\,\delta^{\,i}\, r_{t-1-i}

    **Définition des variables.** :math:`r_u` est le rendement excédentaire
    quotidien de l'instrument le jour :math:`u`, :math:`\kappa` le facteur
    d'annualisation de la variance, 261 dans l'article, :math:`\delta` le
    lissage déduit du centre de masse par
    :func:`smoothing_from_center_of_mass`, et :math:`\bar{r}_t` la moyenne
    pondérée des mêmes poids.

    **Le calcul effectif.** Les poids sommant à un, la variance pondérée s'écrit
    comme la différence entre la moyenne pondérée des carrés et le carré de la
    moyenne pondérée. C'est cette forme qui est calculée, en deux moyennes
    exponentielles au lieu d'une double boucle.

    **Hypothèses.** Les rendements sont quotidiens et déjà excédentaires. La
    somme infinie est tronquée à l'échantillon et ses poids renormalisés, ce que
    fait ``adjust=True``. Aucune interpolation ne comble un jour manquant : un
    trou reste un trou, et la moyenne exponentielle l'ignore.

    **Limites.** Le modèle est intégré, donc sans retour à la moyenne : après un
    choc, l'estimation décroît vers zéro. Il suppose aussi la même dynamique de
    volatilité pour tous les actifs à toutes les dates, ce que l'article assume
    explicitement.

    **Alternatives.** Un GARCH estimé par actif capterait le retour à la
    moyenne, au prix d'une estimation par actif et d'un risque de fuite si elle
    porte sur l'échantillon entier. La volatilité réalisée sur fenêtre glissante
    est plus simple et réagit plus lentement.

    **Comment vérifier l'implémentation.** Sur une série de rendements
    constants, la variance pondérée est exactement nulle, donc la volatilité
    aussi. Sur une série qui alterne :math:`+c` et :math:`-c`, la moyenne
    pondérée tend vers zéro et la volatilité vers :math:`|c|\sqrt{\kappa}`. Et
    la valeur du jour :math:`t` ne change pas quand on modifie le rendement du
    jour :math:`t`, ce que vérifie
    :func:`quantlab.features.transforms.assert_causal`.

    Args:
        daily_returns: les rendements excédentaires quotidiens, une colonne par
            instrument.
        center_of_mass: le centre de masse des poids, en jours de bourse.
        annualization_days: le facteur qui annualise la variance quotidienne.
        min_periods: le nombre de jours valides exigé avant de rendre une
            estimation.

    Returns:
        La volatilité annualisée, de même forme et de même index que l'entrée,
        manquante tant que ``min_periods`` jours ne sont pas disponibles.

    Raises:
        ConfigError: si un réglage est hors de son domaine.
        InsufficientDataError: si le tableau est vide.
    """
    if daily_returns.empty:
        raise InsufficientDataError("aucun rendement quotidien fourni à la volatilité ex ante.")
    if not math.isfinite(annualization_days) or annualization_days <= 0.0:
        raise ConfigError(f"l'annualisation doit être positive, reçu {annualization_days}.")
    if min_periods < 2:
        raise ConfigError(f"min_periods doit valoir au moins 2, reçu {min_periods}.")

    delta = smoothing_from_center_of_mass(center_of_mass)
    alpha = 1.0 - delta
    lagged = daily_returns.shift(1)
    weighted = lagged.ewm(alpha=alpha, min_periods=min_periods, adjust=True)
    mean = weighted.mean()
    mean_of_squares = lagged.pow(2).ewm(alpha=alpha, min_periods=min_periods, adjust=True).mean()
    variance = (mean_of_squares - mean.pow(2)).clip(lower=0.0)
    return variance.mul(annualization_days).pow(0.5)


@dataclass(frozen=True)
class MonthlyInputs:
    """Les tableaux mensuels que la stratégie consomme, et les quotidiens dont ils viennent.

    Attributes:
        daily_returns: les rendements simples quotidiens, par instrument.
        daily_excess: les mêmes, moins le taux sans risque quotidien.
        daily_volatility: la volatilité ex ante annualisée, jour par jour.
        last_sessions: la dernière séance de chaque mois civil.
        monthly_sessions: le nombre de séances observées par mois et instrument.
        monthly_excess: le rendement excédentaire mensuel, absent sous le
            minimum de séances.
        monthly_volatility: la volatilité ex ante à la dernière séance du mois.
    """

    daily_returns: pd.DataFrame
    daily_excess: pd.DataFrame
    daily_volatility: pd.DataFrame
    last_sessions: pd.DatetimeIndex
    monthly_sessions: pd.DataFrame
    monthly_excess: pd.DataFrame
    monthly_volatility: pd.DataFrame


def monthly_inputs_from_prices(
    prices: pd.DataFrame,
    rf_daily: pd.Series,
    rf_monthly: pd.Series,
    *,
    center_of_mass: float = DEFAULT_CENTER_OF_MASS_DAYS,
    annualization_days: float = DEFAULT_ANNUALIZATION_DAYS,
    min_periods: int = 252,
    min_trading_days: int = 15,
) -> MonthlyInputs:
    r"""Passe des prix quotidiens aux rendements excédentaires mensuels et à la volatilité de décision.

    **Le problème.** L'article travaille en mois, les prix arrivent en jours, et
    le passage de l'un à l'autre porte trois décisions qui déplacent le
    résultat. À quelle date du mois lire la volatilité, combien de séances
    exigent un mois, et comment dater le mois pour qu'il s'apparie aux facteurs
    publiés. Ce passage n'est écrit qu'ici, et l'étude 001 comme la
    réconciliation LEAN l'appellent.

    **La formule.** Le rendement brut mensuel compose les rendements
    quotidiens du mois civil,

    .. math::

        R_m = \prod_{d \in m} (1 + r_d) - 1,
        \qquad
        r^{e}_m = R_m - r^{f}_m

    et il est absent quand le mois compte moins de ``min_trading_days``
    séances observées. La volatilité mensuelle est celle de
    :func:`ex_ante_volatility` lue à la dernière séance du mois, donc calculée
    sur les rendements jusqu'à l'avant-dernière.

    **Les hypothèses.** Le taux quotidien couvre chaque séance, sinon la
    fonction refuse plutôt que de retrancher une valeur absente. Le mois est
    daté de sa fin civile, parce qu'un mois dont la dernière séance tombe le 30
    ne s'apparierait ni à AQR ni à Kenneth French. L'étude 001 a mesuré que
    trente pour cent des mois disparaissaient sans cela.

    **Comment vérifier.** Sur deux instruments et trois mois de prix construits
    à la main, le rendement mensuel vaut le rapport des prix de fin de mois
    moins un moins le taux. Un mois à une seule séance est absent, et changer
    le rendement de la dernière séance ne change pas la volatilité lue à cette
    séance.

    Args:
        prices: les prix ajustés, une colonne par instrument, index quotidien.
        rf_daily: le taux sans risque quotidien, en décimal.
        rf_monthly: le taux sans risque mensuel, en décimal, daté en fin de
            mois ou reporté sur elle.
        center_of_mass: le centre de masse de la volatilité, en séances.
        annualization_days: le facteur d'annualisation de la variance.
        min_periods: le nombre de séances exigé avant une volatilité.
        min_trading_days: le nombre de séances exigé pour qu'un mois compte.

    Returns:
        Les tableaux de :class:`MonthlyInputs`.

    Raises:
        DataQualityError: le taux quotidien ne couvre pas toutes les séances.
        InsufficientDataError: aucun prix.
    """
    if prices.empty:
        raise InsufficientDataError("aucun prix pour construire les entrées mensuelles.")
    rendements = prices.pct_change()
    taux = rf_daily.reindex(rendements.index).ffill()
    if bool(taux.isna().any()):
        raise DataQualityError("le taux sans risque quotidien ne couvre pas toutes les séances.")
    exces = rendements.sub(taux, axis=0)
    volatilite = ex_ante_volatility(
        exces,
        center_of_mass=center_of_mass,
        annualization_days=annualization_days,
        min_periods=min_periods,
    )
    cle = [rendements.index.year, rendements.index.month]
    dernieres = pd.DatetimeIndex(sorted(rendements.index.to_series().groupby(cle).max().to_numpy()))
    fins = pd.DatetimeIndex(dernieres.to_period("M").to_timestamp("M"))
    seances = rendements.notna().groupby(cle).sum().set_axis(fins)
    brut = ((1.0 + rendements).groupby(cle).prod() - 1.0).set_axis(fins)
    brut = brut.where(seances >= int(min_trading_days))
    taux_mensuel = rf_monthly.reindex(fins, method="ffill")
    return MonthlyInputs(
        daily_returns=rendements,
        daily_excess=exces,
        daily_volatility=volatilite,
        last_sessions=dernieres,
        monthly_sessions=seances,
        monthly_excess=brut.sub(taux_mensuel, axis=0),
        monthly_volatility=volatilite.reindex(dernieres).set_axis(fins),
    )


def formation_signal(
    monthly_excess_returns: pd.DataFrame,
    lookback: int = DEFAULT_LOOKBACK,
) -> pd.DataFrame:
    r"""Rend le signe du rendement excédentaire cumulé sur la fenêtre de formation.

    **Le problème.** Décider long ou court sans comparer les instruments entre
    eux. C'est la définition même du momentum de série temporelle, et elle
    tient dans un signe.

    **L'intuition.** Un instrument qui a monté sur douze mois est acheté, un
    instrument qui a baissé est vendu. Rien d'autre n'entre dans la décision.

    **La formule.** :math:`S^s_t = \operatorname{sign}(r^s_{t-k,t})`, où
    :math:`k` est la fenêtre de formation en mois et :math:`r^s_{t-k,t}` le
    rendement excédentaire cumulé de l'instrument sur cette fenêtre, le mois
    :math:`t` compris.

    **Hypothèses.** Les rendements sont mensuels, simples, et déjà
    excédentaires. Un cumul exactement nul rend une position plate, choix hérité
    de :func:`quantlab.features.transforms.time_series_momentum_signal`.

    **Limites.** Le signe jette l'amplitude. Une hausse de 2 % et une hausse de
    60 % donnent la même position, ce qui est délibéré : c'est la volatilité,
    et non le rendement passé, qui dimensionne.

    **Comment vérifier.** Douze mois strictement positifs rendent +1, douze mois
    strictement négatifs rendent -1, et la fenêtre incomplète rend une valeur
    manquante.

    Args:
        monthly_excess_returns: les rendements excédentaires mensuels, une
            colonne par instrument.
        lookback: la fenêtre de formation, en mois.

    Returns:
        Le signal, à valeurs dans moins un, zéro et plus un.
    """
    return time_series_momentum_signal(monthly_excess_returns, lookback)


def position_sizes(
    signal: pd.DataFrame,
    volatility: pd.DataFrame,
    *,
    target_volatility: float = DEFAULT_TARGET_VOLATILITY,
    max_position: float = math.inf,
    volatility_floor: float = 1e-6,
) -> pd.DataFrame:
    r"""Rend la position brute de chaque instrument, avant équipondération.

    **Le problème.** Un contrat obligataire porte 2 % de volatilité et un
    contrat de gaz naturel 53 %. Leur donner le même poids en dollars ne
    diversifie rien, le second portant tout le risque. Une position inversement
    proportionnelle à la volatilité les remet à égalité.

    **La formule.**

    .. math::

        P^s_t = S^s_t \, \frac{\lambda}{\max(\sigma^s_t, \epsilon)}

    **Définition des variables.** :math:`S^s_t` est le signal à trois valeurs,
    :math:`\lambda` la volatilité cible, :math:`\sigma^s_t` la volatilité
    ex ante annualisée et :math:`\epsilon` un plancher qui empêche la division
    par une volatilité nulle.

    **Hypothèses.** La volatilité future égale la volatilité estimée, si bien
    que chaque position porte bien :math:`\lambda` de volatilité. C'est faux en
    pratique, et l'écart est le premier risque de la construction.

    **Limites.** Sans plafond, un actif à faible volatilité reçoit un levier
    arbitrairement grand. Le paramètre ``max_position`` borne la valeur absolue
    de la position et vaut l'infini par défaut, ce qui reproduit l'article.

    **Comment vérifier.** À volatilité cible de 40 % et volatilité estimée de
    20 %, la position vaut deux fois le signal. À volatilité estimée de 40 %,
    elle vaut exactement le signal.

    Args:
        signal: le signal à trois valeurs.
        volatility: la volatilité ex ante annualisée, même forme et même index.
        target_volatility: la volatilité annualisée visée par position.
        max_position: la valeur absolue maximale d'une position.
        volatility_floor: le plancher de volatilité, strictement positif.

    Returns:
        Les positions brutes, manquantes là où le signal ou la volatilité
        manque.

    Raises:
        ConfigError: si un réglage est hors de son domaine, ou si les deux
            tableaux n'ont pas la même forme.
    """
    if target_volatility <= 0.0 or not math.isfinite(target_volatility):
        raise ConfigError(f"la volatilité cible doit être positive, reçu {target_volatility}.")
    if volatility_floor <= 0.0:
        raise ConfigError(f"le plancher de volatilité doit être positif, reçu {volatility_floor}.")
    if max_position <= 0.0:
        raise ConfigError(f"le plafond de position doit être positif, reçu {max_position}.")
    if not signal.columns.equals(volatility.columns):
        raise ConfigError("le signal et la volatilité ne portent pas les mêmes colonnes.")
    if not signal.index.equals(volatility.index):
        raise ConfigError("le signal et la volatilité ne portent pas le même index.")

    borne = volatility.clip(lower=volatility_floor)
    brut = signal.mul(target_volatility).div(borne)
    if math.isfinite(max_position):
        brut = brut.clip(lower=-max_position, upper=max_position)
    return brut.where(signal.notna() & volatility.notna())


def cohort_positions(positions: pd.DataFrame, holding: int = DEFAULT_HOLDING) -> pd.DataFrame:
    r"""Rend la position agrégée des cohortes encore actives.

    **Le problème.** Une détention de :math:`h` mois pourrait se lire de deux
    façons, et elles ne donnent pas la même série. Soit on ne mesure qu'un mois
    sur :math:`h`, ce qui jette les données. Soit on tient :math:`h` cohortes en
    parallèle et on publie leur moyenne chaque mois, ce que font Jegadeesh et
    Titman (1993) et ce que reprend l'article.

    **L'intuition.** À chaque mois, :math:`h` portefeuilles coexistent, formés
    aux :math:`h` dernières dates. Chacun garde le signe et la volatilité de sa
    date de formation. La position tenue est leur moyenne.

    **La formule.**

    .. math::

        C^s_t = \frac{1}{h_{\text{eff}}} \sum_{j=0}^{h-1} P^s_{t-j}

    où :math:`h_{\text{eff}}` compte les seules cohortes où l'instrument
    existait, ce qui évite de diluer un instrument nouvellement entré.

    **Hypothèses.** Une cohorte ne se réévalue pas : elle garde sa volatilité de
    formation pendant toute sa vie. C'est la lecture littérale de l'article, et
    l'alternative, réactualiser la volatilité à chaque mois, changerait la
    rotation sans changer le signe des positions.

    **Limites.** La moyenne sur les cohortes disponibles fait varier le levier
    effectif à l'entrée d'un instrument dans l'univers. L'effet est borné par
    :math:`1/S_t` et disparaît après :math:`h` mois.

    **Comment vérifier.** Pour ``holding`` égal à un, la fonction rend son
    entrée inchangée. Pour ``holding`` égal à trois sur trois positions valant
    1, 2 et 4, la troisième ligne vaut la moyenne, soit 7/3.

    Args:
        positions: les positions brutes, une ligne par date de formation.
        holding: le nombre de mois de détention, au moins un.

    Returns:
        Les positions agrégées, de même forme que l'entrée.

    Raises:
        ConfigError: si la détention n'est pas un entier positif.
    """
    if not isinstance(holding, int | np.integer) or isinstance(holding, bool):
        raise ConfigError(f"holding doit être un entier, reçu {type(holding).__name__}.")
    holding = int(holding)
    if holding < 1:
        raise ConfigError(f"holding doit valoir au moins 1, reçu {holding}.")
    if holding == 1:
        return positions.copy()
    agrege = positions.rolling(window=holding, min_periods=1).mean()
    return agrege.where(positions.notna())


def diversified_weights(positions: pd.DataFrame) -> pd.DataFrame:
    r"""Divise les positions par le nombre d'instruments disponibles à chaque date.

    **Le problème.** L'univers ne naît pas d'un coup. Diviser par un nombre fixe
    d'instruments donne un portefeuille dont le levier grandit avec l'univers,
    et confond l'effet de la stratégie avec celui de son remplissage.

    **La formule.**

    .. math::

        w^s_t = \frac{P^s_t}{S_t},
        \qquad S_t = \#\{s : P^s_t \text{ existe}\}

    **Hypothèses.** Un instrument sans position n'est pas un instrument à
    position nulle : il est hors univers, et il ne compte pas au dénominateur.
    Les valeurs manquantes deviennent des zéros une fois la division faite, ce
    qu'attend le moteur de backtest.

    **Limites.** L'équipondération entre instruments n'égalise pas les
    contributions au risque du portefeuille, les instruments d'une même classe
    étant corrélés entre eux. L'article assume ce choix.

    **Comment vérifier.** Trois positions valant 3, 6 et une valeur manquante
    rendent 1,5, 3,0 et 0,0, parce que le diviseur vaut deux et non trois.

    Args:
        positions: les positions agrégées, valeurs manquantes hors univers.

    Returns:
        Les poids du portefeuille, sans valeur manquante.

    Raises:
        InsufficientDataError: si aucune date ne porte le moindre instrument.
    """
    compte = positions.notna().sum(axis=1)
    if int(compte.max() if len(compte) else 0) == 0:
        raise InsufficientDataError("aucune date ne porte d'instrument disponible.")
    diviseur = compte.astype(float).where(compte > 0)
    return positions.div(diviseur, axis=0).fillna(0.0)


def tsmom_weights(
    monthly_excess_returns: pd.DataFrame,
    volatility: pd.DataFrame,
    *,
    lookback: int = DEFAULT_LOOKBACK,
    holding: int = DEFAULT_HOLDING,
    target_volatility: float = DEFAULT_TARGET_VOLATILITY,
    max_position: float = math.inf,
) -> pd.DataFrame:
    """Enchaîne signal, dimensionnement, cohortes et équipondération.

    C'est la fonction que les études appellent. Elle ne fait qu'appeler les
    quatre précédentes dans l'ordre, et elle existe pour que cet ordre ne se
    réécrive pas dans chaque étude.

    Args:
        monthly_excess_returns: les rendements excédentaires mensuels.
        volatility: la volatilité ex ante annualisée aux mêmes dates.
        lookback: la fenêtre de formation, en mois.
        holding: la durée de détention, en mois.
        target_volatility: la volatilité annualisée visée par position.
        max_position: la valeur absolue maximale d'une position.

    Returns:
        Les poids du portefeuille, une ligne par date de décision, sans valeur
        manquante. La ligne datée :math:`t` se détient pendant le mois
        :math:`t+1`, ce que fait le décalage d'exécution du moteur de backtest.
    """
    signal = formation_signal(monthly_excess_returns, lookback)
    brut = position_sizes(
        signal,
        volatility,
        target_volatility=target_volatility,
        max_position=max_position,
    )
    agrege = cohort_positions(brut, holding)
    poids = diversified_weights(agrege)
    _LOG.info(
        "poids TSMOM construits",
        extra={"lookback": lookback, "holding": holding, "n_dates": len(poids)},
    )
    return poids


def grid_weights(
    monthly_excess_returns: pd.DataFrame,
    volatility: pd.DataFrame,
    *,
    formations: Sequence[int] = PAPER_GRID,
    holdings: Sequence[int] = PAPER_GRID,
    target_volatility: float = DEFAULT_TARGET_VOLATILITY,
    max_position: float = math.inf,
) -> dict[tuple[int, int], pd.DataFrame]:
    """Rend les poids de chaque cellule de la grille formation contre détention.

    La grille du tableau 2 de l'article compte huit formations et huit
    détentions, soit soixante-quatre cellules. Chacune est une stratégie
    distincte, et le compte entre dans le ratio de Sharpe dégonflé.

    Args:
        monthly_excess_returns: les rendements excédentaires mensuels.
        volatility: la volatilité ex ante annualisée aux mêmes dates.
        formations: les fenêtres de formation, en mois.
        holdings: les durées de détention, en mois.
        target_volatility: la volatilité annualisée visée par position.
        max_position: la valeur absolue maximale d'une position.

    Returns:
        Un dictionnaire dont la clé est le couple formation et détention, et la
        valeur le tableau de poids correspondant.
    """
    signaux = {k: formation_signal(monthly_excess_returns, k) for k in formations}
    sorties: dict[tuple[int, int], pd.DataFrame] = {}
    for k, signal in signaux.items():
        brut = position_sizes(
            signal,
            volatility,
            target_volatility=target_volatility,
            max_position=max_position,
        )
        for h in holdings:
            sorties[k, h] = diversified_weights(cohort_positions(brut, h))
    _LOG.info("grille construite", extra={"n_cells": len(sorties)})
    return sorties

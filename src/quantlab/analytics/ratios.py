"""Les ratios ajustés du risque, et ce que chacun appelle « risque ».

Tous les ratios de ce module ont la même forme : une récompense au numérateur,
une mesure de risque au dénominateur. Ce qui change d'un ratio à l'autre est la
définition du risque, et rien d'autre.

- Sharpe : l'écart type des rendements excédentaires.
- Sortino : le semi-écart type sous une cible.
- Calmar : le pire repli du patrimoine composé.
- Information : l'écart type de la différence avec un repère.
- Omega : l'espérance des pertes sous un seuil.

**Pourquoi un seul module**. La règle 12 du laboratoire interdit d'implémenter
une métrique financière deux fois. Un ratio de Sharpe qui vit à deux endroits
finit par valoir deux nombres différents, et personne ne sait lequel a produit
le chiffre publié. Toute nouvelle mesure de performance vient donc ici.

**L'avertissement qui doit accompagner chaque chiffre**. Un ratio de Sharpe de
backtest choisi parmi plusieurs essais est biaisé vers le haut, mécaniquement,
même quand aucune stratégie n'a de valeur. Le dégonflage de ce biais vit dans
``quantlab.validation.dsr`` et ne se calcule pas ici. Un Sharpe publié sans son
nombre d'essais, son échantillon et sa base de coûts ne respecte pas la règle 5.

**Deux conventions de ce module, valables partout**.

1. Un taux sans risque, une cible ou un seuil donné sous forme de nombre est
   ANNUEL par défaut, et se ramène à la période par la composition inverse,
   :math:`(1 + r_a)^{1/N} - 1`. Le paramètre ``*_kind`` accepte ``"periodic"``
   pour donner directement un taux de période.
2. Le facteur d'annualisation vient de la fréquence déclarée. Il vaut 252 en
   quotidien par convention, et ``periods_per_year`` accepte le comptage mesuré
   de :func:`quantlab.core.calendars.annualization_factor`.

Références principales : Sharpe (1966, 1994), Lo (2002), Jobson et Korkie
(1981), Memmel (2003), Pezier et White (2006), Sortino et Price (1994),
Young (1991), Grinold et Kahn (2000), Keating et Shadwick (2002).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from scipy import stats

from quantlab.analytics.drawdown import max_drawdown
from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.types import Frequency, ReturnSeries

__all__ = [
    "ConfidenceInterval",
    "SharpeStandardError",
    "adjusted_sharpe_ratio",
    "calmar_ratio",
    "information_ratio",
    "lo_autocorrelation_factor",
    "omega_ratio",
    "sharpe_confidence_interval",
    "sharpe_ratio",
    "sharpe_standard_error",
    "sharpe_tstat",
    "sortino_ratio",
]

#: Les deux façons de composer le numérateur d'un ratio de Sharpe.
SharpeMethod = Literal["arithmetic", "geometric"]
#: Un taux fourni par l'appelant est annuel par défaut, ou déjà périodique.
RateKind = Literal["annual", "periodic"]
#: Les deux erreurs types disponibles pour un ratio de Sharpe.
SharpeErrorMethod = Literal["lo", "iid"]

#: Deux observations au minimum : un écart type d'échantillon en exige deux.
MIN_OBSERVATIONS = 2
#: Quatre observations au minimum pour un moment d'ordre quatre. Précepte.
MIN_OBSERVATIONS_FOURTH_MOMENT = 4
#: Niveau de confiance par défaut des intervalles, convention déclarée.
DEFAULT_CONFIDENCE = 0.95
#: Seuil relatif sous lequel une dispersion est tenue pour nulle. Une série
#: constante rend un écart type de l'ordre de 1e-18 et non de zéro : la moyenne
#: n'est pas représentable exactement, donc les écarts non plus.
DEFAULT_VOLATILITY_FLOOR = 1e-12


# ---------------------------------------------------------------------------
# Aides internes. Aucune n'est publique : elles fixent des conventions que les
# fonctions exportées documentent chacune pour son compte.
# ---------------------------------------------------------------------------


def _as_returns(
    returns: ReturnSeries | Sequence[float],
    *,
    min_observations: int = MIN_OBSERVATIONS,
    label: str = "rendements",
) -> pd.Series:
    """Rend une série de rendements en flottants, sans valeur manquante.

    Args:
        returns: la série d'entrée, ou toute suite de nombres.
        min_observations: le nombre d'observations exigé après retrait des
            valeurs manquantes.
        label: le nom employé dans le message d'erreur.

    Returns:
        Une série de type ``float64``, indexée comme l'entrée.

    Raises:
        InsufficientDataError: si trop peu d'observations subsistent.
        DataQualityError: si une valeur n'est pas finie.

    Note:
        Les valeurs manquantes sont retirées, jamais remplacées par zéro. Un
        zéro est un rendement nul, donc une information ; un trou est une
        absence d'information, et les deux ne se confondent pas.
    """
    series = (
        returns.astype("float64")
        if isinstance(returns, pd.Series)
        else pd.Series(list(returns), dtype="float64")
    )
    series = series.dropna()
    if not bool(np.isfinite(series.to_numpy()).all()):
        raise DataQualityError(f"les {label} contiennent une valeur infinie")
    if len(series) < min_observations:
        raise InsufficientDataError(
            f"{len(series)} observation(s) de {label} après retrait des valeurs "
            f"manquantes, {min_observations} exigées"
        )
    return series


def _volatility_threshold(series: pd.Series, floor: float) -> float:
    """Rend le seuil sous lequel une dispersion est tenue pour nulle.

    Le seuil est relatif à l'échelle des données, et jamais plus petit que le
    seuil lui-même. Sans lui, une série constante passerait le contrôle : sa
    moyenne n'étant pas représentable exactement en binaire, ses écarts valent
    quelques 1e-18 au lieu de zéro, et le ratio rendu vaudrait 1e16.

    Args:
        series: la série dont on mesure l'échelle.
        floor: le seuil relatif, sans dimension.

    Raises:
        ConfigError: si le seuil est négatif.
    """
    if floor < 0.0:
        raise ConfigError(f"volatility_floor vaut {floor}, il doit être positif ou nul")
    scale = float(np.max(np.abs(series.to_numpy())))
    return floor * max(scale, 1.0)


def _check_compoundable(series: pd.Series) -> None:
    """Vérifie qu'une série de rendements simples peut se composer.

    Un rendement simple inférieur à -100 % détruit plus que le capital investi.
    Cela n'a de sens pour aucune position financée d'avance, et cela rend le
    patrimoine composé négatif, donc tout repli et toute croissance annualisée
    ininterprétables.

    Raises:
        DataQualityError: si un rendement est strictement inférieur à -1.
    """
    worst = float(series.min())
    if worst < -1.0:
        raise DataQualityError(
            f"rendement simple de {worst:.4f}, inférieur à -100 % : la composition n'est pas définie"
        )


def _resolve_periods_per_year(frequency: Frequency, periods_per_year: float | None) -> float:
    """Rend le facteur d'annualisation retenu, déclaré ou mesuré.

    Args:
        frequency: la fréquence d'observation de la série.
        periods_per_year: un comptage mesuré qui l'emporte sur la convention,
            typiquement celui de :func:`quantlab.core.calendars.annualization_factor`.

    Raises:
        ConfigError: si le comptage fourni n'est pas strictement positif.
    """
    if periods_per_year is None:
        return float(frequency.periods_per_year)
    if not math.isfinite(periods_per_year) or periods_per_year <= 0.0:
        raise ConfigError(f"periods_per_year vaut {periods_per_year}, il doit être positif")
    return float(periods_per_year)


def _to_periodic_rate(
    rate: float | pd.Series,
    *,
    periods_per_year: float,
    kind: RateKind,
    label: str,
) -> float | pd.Series:
    """Ramène un taux annuel à la période, par composition inverse.

    .. math::

        r_p = (1 + r_a)^{1/N} - 1

    Args:
        rate: le taux, annuel ou déjà périodique.
        periods_per_year: le nombre de périodes par an, :math:`N`.
        kind: ``"annual"`` ou ``"periodic"``.
        label: le nom du taux dans les messages d'erreur.

    Raises:
        ConfigError: si ``kind`` est inconnu.
        DataQualityError: si un taux annuel vaut moins de -100 %.

    Note:
        La division par :math:`N` serait fausse : un taux annuel de 12 % ne
        donne pas 1 % par mois mais 0,9489 %, parce que les mois se composent.
        L'écart est de 5,4 % en valeur relative sur le taux mensuel, mesuré.
    """
    if kind == "periodic":
        return rate
    if kind != "annual":
        raise ConfigError(f"{label}_kind vaut {kind!r}, attendu 'annual' ou 'periodic'")
    if isinstance(rate, pd.Series):
        if bool((rate <= -1.0).any()):
            raise DataQualityError(f"{label} annuel inférieur ou égal à -100 %")
        return (1.0 + rate) ** (1.0 / periods_per_year) - 1.0
    if rate <= -1.0:
        raise DataQualityError(f"{label} annuel de {rate}, inférieur ou égal à -100 %")
    return (1.0 + rate) ** (1.0 / periods_per_year) - 1.0


def _excess_returns(
    series: pd.Series,
    risk_free: float | ReturnSeries,
    *,
    periods_per_year: float,
    risk_free_kind: RateKind,
) -> pd.Series:
    """Rend les rendements excédentaires, taux sans risque déjà ramené à la période.

    Raises:
        DataQualityError: si un taux sans risque en série ne couvre pas toutes
            les dates de la série de rendements.
    """
    periodic = _to_periodic_rate(
        risk_free, periods_per_year=periods_per_year, kind=risk_free_kind, label="risk_free"
    )
    if isinstance(periodic, pd.Series):
        aligned = periodic.reindex(series.index)
        if bool(aligned.isna().any()):
            raise DataQualityError("le taux sans risque ne couvre pas toutes les dates des rendements")
        return series - aligned.astype("float64")
    return series - float(periodic)


def _compounded_return(series: pd.Series, *, horizon_periods: float) -> float:
    """Rend le rendement composé sur un horizon exprimé en périodes.

    .. math::

        R(H) = \\left[\\prod_{t=1}^{T} (1 + r_t)\\right]^{H/T} - 1

    Args:
        series: les rendements simples de la période.
        horizon_periods: :math:`H`, le nombre de périodes de l'horizon voulu.
            Vaut :math:`N` pour une croissance annualisée, 1 pour un rendement
            géométrique moyen par période.

    Note:
        Un patrimoine final nul ou négatif rend -1, soit la perte totale, plutôt
        qu'une puissance fractionnaire de zéro qui donnerait ``nan``.
    """
    _check_compoundable(series)
    wealth = float(np.prod(1.0 + series.to_numpy()))
    if wealth <= 0.0:
        return -1.0
    return wealth ** (horizon_periods / len(series)) - 1.0


def _sample_skewness(series: pd.Series) -> float:
    """Rend l'asymétrie d'échantillon, moments non corrigés.

    .. math::

        S = \\frac{\\frac{1}{T}\\sum (r_t - \\bar{r})^3}
                  {\\left[\\frac{1}{T}\\sum (r_t - \\bar{r})^2\\right]^{3/2}}
    """
    x = series.to_numpy()
    deviations = x - x.mean()
    m2 = float(np.mean(deviations**2))
    m3 = float(np.mean(deviations**3))
    return m3 / m2**1.5


def _sample_excess_kurtosis(series: pd.Series) -> float:
    """Rend l'excès d'aplatissement d'échantillon, moments non corrigés.

    .. math::

        K - 3 = \\frac{\\frac{1}{T}\\sum (r_t - \\bar{r})^4}
                      {\\left[\\frac{1}{T}\\sum (r_t - \\bar{r})^2\\right]^2} - 3
    """
    x = series.to_numpy()
    deviations = x - x.mean()
    m2 = float(np.mean(deviations**2))
    m4 = float(np.mean(deviations**4))
    return m4 / m2**2 - 3.0


def _newey_west_lags(n_observations: int) -> int:
    """Rend le nombre de retards de la règle usuelle de Newey et West.

    .. math::

        m = \\left\\lfloor 4 \\left(\\frac{T}{100}\\right)^{2/9} \\right\\rfloor

    Args:
        n_observations: :math:`T`, la taille de l'échantillon.

    Note:
        Règle de sélection automatique, précepte largement suivi et non un
        résultat d'optimalité. Elle donne 4 retards pour 100 observations, 5
        pour 500 et 6 pour 1 000, mesuré. Elle est bornée à :math:`T - 1`.
    """
    lags = math.floor(4.0 * (n_observations / 100.0) ** (2.0 / 9.0))
    return max(0, min(lags, n_observations - 1))


def _lo_standard_error(excess: pd.Series, *, lags: int) -> float:
    """Rend l'erreur type d'un ratio de Sharpe périodique par la méthode de Lo (2002).

    **Le problème**. L'erreur type i.i.d. suppose des rendements indépendants et
    de même loi. Les rendements de fonds peu liquides sont autocorrélés, et
    l'erreur type i.i.d. est alors trop petite, donc le test trop permissif.

    **La méthode**. Lo (2002) traite le ratio de Sharpe comme une fonction de
    deux moments estimés, puis applique la méthode delta à une covariance de
    type Newey et West, robuste à l'hétéroscédasticité et à l'autocorrélation.

    .. math::

        \\hat{\\theta} = (\\hat{\\mu}, \\hat{\\sigma}^2), \\qquad
        g(\\theta) = \\frac{\\mu}{\\sigma}, \\qquad
        \\nabla g = \\left(\\frac{1}{\\sigma},\\; -\\frac{\\mu}{2\\sigma^3}\\right)

    .. math::

        u_t = \\begin{pmatrix} r_t - \\mu \\\\ (r_t - \\mu)^2 - \\sigma^2 \\end{pmatrix},
        \\qquad
        \\Sigma = \\Gamma_0 + \\sum_{j=1}^{m}\\left(1 - \\frac{j}{m+1}\\right)
        (\\Gamma_j + \\Gamma_j^{\\top})

    .. math::

        \\widehat{Var}(\\widehat{SR}) = \\frac{\\nabla g^{\\top} \\Sigma \\nabla g}{T}

    Args:
        excess: les rendements excédentaires périodiques.
        lags: :math:`m`, le nombre de retards du noyau de Bartlett. Zéro donne
            la version robuste à la seule hétéroscédasticité.

    Returns:
        L'erreur type du ratio de Sharpe PÉRIODIQUE.

    Raises:
        InsufficientDataError: si la variance estimée est nulle ou négative.

    Note:
        Vérification. À ``lags=0``, l'expression se réduit à une identité de
        moments qui se contrôle à la main :
        :math:`T \\cdot Var = 1 - SR \\cdot S + \\frac{SR^2}{4}(K - 1)`,
        où :math:`S` est l'asymétrie et :math:`K` l'aplatissement non centré.
        Pour une loi normale, :math:`S = 0` et :math:`K = 3`, ce qui redonne
        :math:`(1 + SR^2/2)/T`. Le test du module vérifie cette identité.
    """
    x = excess.to_numpy(dtype="float64")
    n = x.size
    mu = float(x.mean())
    deviations = x - mu
    sigma2 = float(np.mean(deviations**2))
    if sigma2 <= 0.0:
        raise InsufficientDataError("variance nulle : l'erreur type de Lo n'est pas définie")
    sigma = math.sqrt(sigma2)
    moments = np.column_stack((deviations, deviations**2 - sigma2))
    covariance = moments.T @ moments / n
    for lag in range(1, lags + 1):
        gamma = moments[lag:].T @ moments[:-lag] / n
        weight = 1.0 - lag / (lags + 1.0)
        covariance = covariance + weight * (gamma + gamma.T)
    gradient = np.array([1.0 / sigma, -mu / (2.0 * sigma**3)])
    variance = float(gradient @ covariance @ gradient) / n
    if variance <= 0.0:
        raise InsufficientDataError("la variance estimée du ratio de Sharpe est nulle ou négative")
    return math.sqrt(variance)


# ---------------------------------------------------------------------------
# Résultats structurés
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SharpeStandardError:
    """Les deux erreurs types d'un ratio de Sharpe, et de quoi les relire.

    Attributes:
        iid: l'erreur type sous hypothèse i.i.d., :math:`\\sqrt{(1 + SR^2/2)/T}`.
        lo: l'erreur type robuste à l'autocorrélation, Lo (2002).
        sharpe: le ratio de Sharpe auquel les deux se rapportent.
        n_observations: :math:`T`, le nombre d'observations retenues.
        lags: le nombre de retards employé par la version de Lo.
        annualized: vrai si les trois premiers champs sont sur l'échelle
            annuelle, faux s'ils sont sur l'échelle de la période.

    Note:
        Le rapport ``lo / iid`` mesure ce que coûte l'hypothèse i.i.d. sur cette
        série précise. Au-dessus de 1, l'erreur type i.i.d. est trop petite et
        le test correspondant est trop permissif.
    """

    iid: float
    lo: float
    sharpe: float
    n_observations: int
    lags: int
    annualized: bool


@dataclass(frozen=True, slots=True)
class ConfidenceInterval:
    """Un intervalle de confiance de ratio de Sharpe, et sa fabrication.

    Attributes:
        low: la borne basse.
        high: la borne haute.
        confidence: le niveau de confiance, par exemple 0,95.
        sharpe: le ratio de Sharpe estimé, centre de l'intervalle.
        standard_error: l'erreur type employée.
        method: ``"lo"`` ou ``"iid"``, l'erreur type retenue.
    """

    low: float
    high: float
    confidence: float
    sharpe: float
    standard_error: float
    method: str


# ---------------------------------------------------------------------------
# Ratio de Sharpe
# ---------------------------------------------------------------------------


def sharpe_ratio(
    returns: ReturnSeries | Sequence[float],
    *,
    risk_free: float | ReturnSeries = 0.0,
    frequency: Frequency,
    annualize: bool = True,
    method: SharpeMethod = "arithmetic",
    risk_free_kind: RateKind = "annual",
    ddof: int = 1,
    periods_per_year: float | None = None,
    volatility_floor: float = DEFAULT_VOLATILITY_FLOOR,
) -> float:
    r"""Rend le ratio de Sharpe, rendement excédentaire par unité d'écart type.

    **(1) Le problème**. Deux stratégies rapportent 12 % par an. La première
    oscille de 3 % autour de sa tendance, la seconde de 30 %. Le rendement seul
    les déclare identiques, ce qu'aucun gérant ne croit. Il faut un nombre qui
    rapporte la récompense à ce qu'elle a coûté en incertitude.

    **(2) L'intuition**. Le ratio compte combien d'écarts types de rendement la
    stratégie gagne par an, au-delà du taux sans risque. Un Sharpe de 1 signifie
    que le gain annuel excédentaire vaut exactement un écart type annuel, donc
    qu'une année sur six environ finit sous le taux sans risque si les
    rendements sont normaux.

    **(3) La formule**.

    .. math::

        \widehat{SR}_{p} = \frac{\bar{r} - r_f}{\hat{\sigma}}, \qquad
        \widehat{SR}_{ann} = \frac{(\bar{r} - r_f) \, N}{\hat{\sigma} \sqrt{N}}
        = \widehat{SR}_{p} \sqrt{N}

    En version géométrique, le numérateur devient la croissance composée :

    .. math::

        \widehat{SR}_{ann}^{g\acute{e}o} =
        \frac{\left[\prod_{t=1}^{T}(1 + r_t - r_{f,t})\right]^{N/T} - 1}
             {\hat{\sigma}\sqrt{N}}

    **(4) Les variables**.

    - :math:`r_t` le rendement simple de la période :math:`t` ;
    - :math:`r_{f,t}` le taux sans risque de la même période ;
    - :math:`\bar{r} - r_f` la moyenne des rendements excédentaires ;
    - :math:`\hat{\sigma}` leur écart type d'échantillon, ``ddof`` degrés de
      liberté retirés ;
    - :math:`N` le nombre de périodes par an ;
    - :math:`T` le nombre d'observations.

    **Le numérateur : arithmétique ou géométrique**. Le numérateur arithmétique
    multiplie la moyenne par :math:`N`. Il répond à la question « combien
    rapporte une période typique, mise à l'échelle de l'année ». Le numérateur
    géométrique compose les rendements et répond à « qu'a réellement gagné un
    dollar investi ». Sur une PÉRIODE, la moyenne géométrique est toujours la
    plus petite, d'environ :math:`\sigma^2/2`. Exemple travaillé : une hausse de
    10 % suivie d'une baisse de 10 % laisse 0,99, soit -1,0 % composé, alors que
    la moyenne arithmétique vaut exactement zéro. Après annualisation, l'ordre
    peut s'inverser, la composition jouant alors dans l'autre sens. Sur les
    quatre rendements de l'exemple ci-dessous, 1,47 % par mois composé douze fois
    donne 19,19 %, contre 18,00 % pour douze fois 1,50 %, MESURÉ. Le laboratoire
    prend l'arithmétique par défaut parce que c'est la convention de la
    littérature citée, Lo (2002) compris, et que l'erreur type publiée s'y
    rapporte.

    **L'annualisation, et pourquoi elle croît en racine de N**. Le numérateur
    s'annualise en multipliant par :math:`N`, le dénominateur en multipliant par
    :math:`\sqrt{N}`, sous hypothèse de rendements indépendants. Le rapport gagne
    donc un facteur :math:`\sqrt{N}`. Concrètement, un Sharpe mensuel de 0,20
    devient 0,69 en annuel, et un Sharpe quotidien de 0,06 devient 0,95. Un
    ratio de Sharpe sans sa fréquence de calcul n'est pas interprétable, et
    c'est la raison pour laquelle ``frequency`` n'a pas de valeur par défaut.

    **Le taux sans risque se soustrait AVANT l'annualisation**. L'ordre n'est pas
    un détail de présentation. Un taux annuel de 4 % vaut 0,32737 % par mois, et
    douze fois ce nombre font 3,92849 % et non 4 %. Retrancher le taux annuel à
    un rendement déjà annualisé retire donc 7 points de base de trop, MODÉLISÉ,
    et l'écart vient de la composition du taux lui-même, pas de la volatilité.
    Ce module ramène toujours le taux à la période, puis soustrait, puis
    annualise.

    **(5) Les hypothèses**. Rendements indépendants et de même loi, écart type
    fini, et préférences qui ne regardent que les deux premiers moments.
    L'annualisation en :math:`\sqrt{N}` n'a besoin que de l'absence
    d'autocorrélation, pas de la normalité.

    **(6) La provenance**. Sharpe (1966), « Mutual Fund Performance », Journal of
    Business 39(1), sous le nom de « reward to variability ratio ». Révision par
    Sharpe (1994), « The Sharpe Ratio », Journal of Portfolio Management 21(1),
    qui impose l'usage du rendement EXCÉDENTAIRE et non du rendement brut.

    **(7) Les limites, chiffrées quand elles se chiffrent**.

    - *L'autocorrélation.* Sous autocorrélation positive, la volatilité
      annualisée en :math:`\sqrt{N}` est sous-estimée, donc le Sharpe annualisé
      surestimé. Avec un processus autorégressif d'ordre un d'autocorrélation
      mensuelle 0,3, la surestimation vaut +32,5 % ; à 0,5 elle vaut +63,3 %.
      Ces deux nombres sont MODÉLISÉS, calculés depuis la formule de Lo (2002)
      reprise dans :func:`lo_autocorrelation_factor`, et le test du module les
      recalcule à la main. Le chiffre de « 65 % » souvent attribué à Lo (2002)
      pour une autocorrélation de 0,3 ne sort PAS de cette formule. Elle donne
      32,5 % à 0,3, et 65 % sont atteints entre 0,50 et 0,51, MODÉLISÉ et
      encadré par le test du module. L'article n'a pas été consulté depuis cet
      environnement, donc l'attribution exacte de ce chiffre est NON VÉRIFIÉE,
      et c'est le calcul qui est reproduit ici, pas la citation.
    - *La non-normalité.* Le ratio ignore l'asymétrie et les queues épaisses.
      Une stratégie de vente d'options affiche un Sharpe flatteur jusqu'au jour
      où la queue se réalise. La correction de Pezier et White vit dans
      :func:`adjusted_sharpe_ratio`.
    - *La sélection.* Un Sharpe choisi comme le meilleur de :math:`n` essais est
      biaisé vers le haut même quand aucune stratégie n'a de valeur : le maximum
      de :math:`n` variables centrées croît avec :math:`n`. Le dégonflage vit
      dans ``quantlab.validation.dsr``, d'après Bailey et López de Prado (2014).
    - *L'échantillon fini.* Un Sharpe annuel de 1 mesuré sur trois ans reste
      indistinguable de zéro au seuil de 5 %. Voir :func:`sharpe_tstat`.

    **(8) Les alternatives**. Sortino, quand la baisse seule compte ; Calmar,
    quand la contrainte est le pire repli ; Omega, quand la loi entière compte ;
    ratio de l'information, quand la performance se juge contre un repère.

    **(9) Pourquoi ce ratio ici**. Il est la mesure la plus lue de la
    littérature répliquée par le laboratoire, donc la seule qui rend les
    résultats comparables aux articles d'origine sans retraitement.

    **(10) Comment vérifier l'implémentation**. Quatre contrôles vivent dans
    ``tests/unit/test_analytics_ratios.py``. Un calcul à la main sur quatre
    rendements, l'identité d'annualisation :math:`SR_{ann} = SR_p \sqrt{N}`,
    l'invariance d'échelle à taux sans risque nul, et le refus de rendre
    l'infini quand l'écart type est nul.

    Args:
        returns: les rendements simples de la stratégie, périodicité constante.
        risk_free: le taux sans risque, annuel par défaut. Un nombre s'applique
            à toutes les dates, une série s'aligne sur l'index des rendements.
        frequency: la fréquence d'observation. Sans valeur par défaut : une
            annualisation muette est la première source de Sharpe faux.
        annualize: si faux, rend le ratio sur l'échelle de la période.
        method: ``"arithmetic"`` ou ``"geometric"`` pour le numérateur.
        risk_free_kind: ``"annual"`` ou ``"periodic"``.
        ddof: degrés de liberté retirés à l'écart type, 1 par défaut, donc
            l'estimateur sans biais de la variance.
        periods_per_year: comptage mesuré du nombre de périodes par an, qui
            l'emporte sur la convention de la fréquence.
        volatility_floor: en deçà de ce seuil relatif, l'écart type est tenu
            pour nul. Une série constante ne rend pas un écart type de zéro mais
            un résidu de calcul flottant de l'ordre de 1e-18, qui donnerait un
            ratio de Sharpe de 1e16 au lieu d'une erreur.

    Returns:
        Le ratio de Sharpe, annualisé sauf indication contraire.

    Raises:
        InsufficientDataError: moins de deux observations, ou écart type nul.
        DataQualityError: valeur infinie, ou taux sans risque incomplet.
        ConfigError: ``method`` inconnu.

    Example:
        Quatre rendements mensuels de 1 %, 3 %, -2 % et 4 %. La moyenne vaut
        1,5 % et l'écart type d'échantillon 2,6458 %, donc un Sharpe mensuel de
        0,566947 et un Sharpe annualisé de 0,566947 fois la racine de 12, soit
        1,963961. Ces nombres sont calculés à la main dans le test du module.

        >>> import pandas as pd
        >>> from quantlab.core.types import Frequency
        >>> r = pd.Series([0.01, 0.03, -0.02, 0.04])
        >>> round(sharpe_ratio(r, frequency=Frequency.MONTHLY), 6)
        1.963961
    """
    periods = _resolve_periods_per_year(frequency, periods_per_year)
    excess = _excess_returns(
        _as_returns(returns),
        risk_free,
        periods_per_year=periods,
        risk_free_kind=risk_free_kind,
    )
    sigma = float(excess.std(ddof=ddof))
    if not math.isfinite(sigma) or sigma <= _volatility_threshold(excess, volatility_floor):
        raise InsufficientDataError(
            "l'écart type des rendements excédentaires est nul ou non fini : le ratio "
            "de Sharpe n'est pas défini, et rendre l'infini masquerait le problème"
        )
    horizon = periods if annualize else 1.0
    if method == "arithmetic":
        numerator = float(excess.mean()) * horizon
    elif method == "geometric":
        numerator = _compounded_return(excess, horizon_periods=horizon)
    else:
        raise ConfigError(f"method vaut {method!r}, attendu 'arithmetic' ou 'geometric'")
    denominator = sigma * math.sqrt(horizon)
    return numerator / denominator


def lo_autocorrelation_factor(
    autocorrelation: float | Sequence[float],
    *,
    periods: int,
) -> float:
    r"""Rend le facteur d'annualisation d'un Sharpe sous autocorrélation, Lo (2002).

    **(1) Le problème**. Multiplier un Sharpe mensuel par racine de 12 suppose
    des rendements indépendants. Les rendements de fonds peu liquides sont
    autocorrélés positivement, la volatilité annuelle est alors plus grande que
    :math:`\sigma\sqrt{12}`, et le Sharpe annualisé usuel est trop flatteur.

    **(2) L'intuition**. La variance d'une somme de variables corrélées n'est
    pas la somme des variances : les covariances s'ajoutent. Le facteur correct
    remplace :math:`\sqrt{q}` par une racine qui compte ces covariances.

    **(3) La formule**.

    .. math::

        \eta(q) = \frac{q}{\sqrt{q + 2\sum_{k=1}^{q-1}(q-k)\,\rho_k}}

    **(4) Les variables**. :math:`q` le nombre de périodes agrégées,
    :math:`\rho_k` l'autocorrélation d'ordre :math:`k` des rendements. Sous un
    processus autorégressif d'ordre un, :math:`\rho_k = \rho^k`.

    **(5) Les hypothèses**. Rendements de même loi, autocorrélations connues,
    taux sans risque constant sur l'horizon agrégé.

    **(6) La provenance**. Lo (2002), « The Statistics of Sharpe Ratios »,
    Financial Analysts Journal 58(4), 36 à 52.

    **(7) Les limites**. Les :math:`\rho_k` sont estimés, donc bruités, et
    l'erreur se propage au carré dans la somme. Le facteur n'est pas défini si
    la combinaison d'autocorrélations rend la variance agrégée négative.

    **(8) Les alternatives**. Estimer directement la volatilité des rendements
    agrégés sur des blocs de :math:`q` périodes, ce qui ne suppose aucune
    structure, mais divise le nombre d'observations par :math:`q`.

    **(9) Pourquoi ici**. Le module publie des Sharpe annualisés en
    :math:`\sqrt{N}` ; cette fonction chiffre l'erreur commise plutôt que de la
    supposer nulle, et n'est jamais appliquée en silence par
    :func:`sharpe_ratio`.

    **(10) Comment vérifier**. À :math:`\rho = 0`, le facteur vaut exactement
    :math:`\sqrt{q}`. Le test du module recalcule à la main le cas
    :math:`q = 12`, :math:`\rho = 0{,}3` : la somme vaut 4,53061257, donc
    :math:`\eta = 12/\sqrt{21{,}06122514} = 2{,}614806`, contre
    :math:`\sqrt{12} = 3{,}464102`. La surestimation du Sharpe annualisé usuel
    vaut donc 32,48 %, MODÉLISÉ.

    Args:
        autocorrelation: soit un nombre, interprété comme le coefficient d'un
            processus autorégressif d'ordre un, soit la suite des
            :math:`\rho_1` à :math:`\rho_{q-1}`.
        periods: :math:`q`, le nombre de périodes agrégées, par exemple 12 pour
            passer du mois à l'année.

    Returns:
        Le facteur :math:`\eta(q)` par lequel multiplier le Sharpe périodique.

    Raises:
        ConfigError: si ``periods`` est inférieur à 1, si la suite fournie est
            trop courte, ou si la variance agrégée implicite n'est pas positive.
    """
    if periods < 1:
        raise ConfigError(f"periods vaut {periods}, il doit valoir au moins 1")
    if isinstance(autocorrelation, (int, float)):
        rho = [float(autocorrelation) ** k for k in range(1, periods)]
    else:
        rho = [float(value) for value in autocorrelation]
        if len(rho) < periods - 1:
            raise ConfigError(f"{len(rho)} autocorrélations fournies, {periods - 1} exigées pour q={periods}")
        rho = rho[: periods - 1]
    aggregated_variance = periods + 2.0 * sum((periods - k) * value for k, value in enumerate(rho, start=1))
    if aggregated_variance <= 0.0:
        raise ConfigError("la combinaison d'autocorrélations donne une variance agrégée négative")
    return periods / math.sqrt(aggregated_variance)


def sharpe_standard_error(
    returns: ReturnSeries | Sequence[float],
    *,
    frequency: Frequency,
    risk_free: float | ReturnSeries = 0.0,
    annualize: bool = True,
    lags: int | None = None,
    risk_free_kind: RateKind = "annual",
    ddof: int = 1,
    periods_per_year: float | None = None,
) -> SharpeStandardError:
    r"""Rend les deux erreurs types d'un ratio de Sharpe, i.i.d. et robuste.

    **(1) Le problème**. Un ratio de Sharpe est une estimation, donc il porte une
    incertitude, et cette incertitude est grande. Publier 1,20 sans dire que
    l'intervalle va de 0,10 à 2,30 revient à publier un nombre faux.

    **(2) L'intuition**. L'incertitude vient de deux sources : la moyenne est mal
    connue, et l'écart type aussi. La seconde source ajoute le terme en
    :math:`SR^2/2`, qui grandit quand le ratio grandit.

    **(3) Les formules**. Version i.i.d. de Jobson et Korkie (1981), corrigée
    par Memmel (2003) :

    .. math::

        \widehat{SE}_{iid}(\widehat{SR}) = \sqrt{\frac{1 + \frac{1}{2}\widehat{SR}^2}{T}}

    Version robuste de Lo (2002), méthode delta sur une covariance de Newey et
    West à noyau de Bartlett :

    .. math::

        \widehat{SE}_{Lo}(\widehat{SR}) =
        \sqrt{\frac{\nabla g^{\top}\, \Sigma \, \nabla g}{T}}, \qquad
        \nabla g = \left(\frac{1}{\sigma}, -\frac{\mu}{2\sigma^3}\right)

    Le détail de :math:`\Sigma` vit dans la docstring de la fonction interne qui
    la construit.

    **(4) Les variables**. :math:`T` le nombre d'observations, :math:`SR` le
    ratio de Sharpe PÉRIODIQUE, :math:`\mu` et :math:`\sigma` les deux premiers
    moments des rendements excédentaires, :math:`m` le nombre de retards.

    **(5) Les hypothèses**. Les deux formules sont asymptotiques : elles
    décrivent la loi de l'estimateur quand :math:`T` grandit. La version i.i.d.
    suppose en plus l'indépendance et la normalité ; la version de Lo ne suppose
    ni l'une ni l'autre, mais exige assez d'observations pour estimer quatre
    moments et :math:`m` autocovariances.

    **(6) La provenance**. Jobson et Korkie (1981), Journal of Finance 36(4),
    889 à 908 ; Memmel (2003), Finance Letters 1, 21 à 23 ; Lo (2002), Financial
    Analysts Journal 58(4), 36 à 52. Noyau de Bartlett d'après Newey et West
    (1987), Econometrica 55(3), 703 à 708.

    **(7) Les limites**. En deçà d'une quarantaine d'observations,
    l'approximation asymptotique est médiocre et la loi de l'estimateur est
    asymétrique, PRÉCEPTE dont ce module n'a pas mesuré l'ampleur. Seconde
    limite,
    l'annualisation de l'erreur type par :math:`\sqrt{N}` réintroduit
    l'hypothèse d'indépendance que la version de Lo venait de retirer. Les deux
    corrections ne se remplacent donc pas : celle de Lo porte sur l'ERREUR
    D'ESTIMATION, celle de :func:`lo_autocorrelation_factor` sur le POINT
    ESTIMÉ.

    **(8) Les alternatives**. Un bootstrap par blocs stationnaires, qui ne
    suppose aucune forme de dépendance mais coûte cher, et dont l'intervalle
    n'est pas symétrique.

    **(9) Pourquoi les deux**. Rendre les deux nombres rend visible ce que coûte
    l'hypothèse i.i.d. sur la série examinée. Un rapport ``lo / iid`` supérieur
    à 1,3 signale une série dont le Sharpe ne doit pas être testé à la formule
    simple, seuil de lecture qui est un PRÉCEPTE et non un résultat.

    **Les deux erreurs types ne partagent pas le même écart type**. Le champ
    ``iid`` et le champ ``sharpe`` emploient l'écart type à ``ddof`` degrés de
    liberté retirés, un par défaut. La covariance de Lo, elle, se construit sur
    les moments centrés d'échantillon, donc à zéro degré retiré, comme dans la
    dérivation de l'article. L'écart est d'ordre :math:`1/T` et il est DÉCLARÉ
    plutôt que corrigé. Il est visible en petit échantillon : sur quatre
    observations, les deux ratios valent 0,5669 et 0,6547, MESURÉ.

    **(10) Comment vérifier**. À ``lags=0``, l'erreur de Lo satisfait
    l'identité de moments :math:`T \cdot SE^2 = 1 - SR\,S + \frac{SR^2}{4}(K-1)`,
    contrôlée dans le test du module contre les moments de ``scipy.stats``. Sur
    un échantillon normal, les deux erreurs types se rejoignent.

    Args:
        returns: les rendements simples de la stratégie.
        frequency: la fréquence d'observation.
        risk_free: le taux sans risque, annuel par défaut.
        annualize: si vrai, les trois nombres rendus sont sur l'échelle
            annuelle, obtenue en multipliant par la racine du nombre de périodes.
        lags: le nombre de retards du noyau de Bartlett. Sans valeur, la règle
            :math:`\lfloor 4 (T/100)^{2/9} \rfloor` décide.
        risk_free_kind: ``"annual"`` ou ``"periodic"``.
        ddof: degrés de liberté de l'écart type du ratio de Sharpe rendu.
        periods_per_year: comptage mesuré, qui l'emporte sur la convention.

    Returns:
        Un :class:`SharpeStandardError` portant les deux erreurs types.

    Raises:
        InsufficientDataError: moins de trois observations, ou variance nulle.
        ConfigError: si ``lags`` est négatif ou dépasse :math:`T - 1`.

    Example:
        Sur quatre rendements mensuels de 1 %, 3 %, -2 % et 4 %, le ratio de
        Sharpe mensuel vaut 0,566947 et l'erreur type i.i.d. mensuelle
        :math:`\sqrt{(1 + 0{,}566947^2/2)/4} = 0{,}538682`, calcul repris à la
        main dans le test du module.
    """
    periods = _resolve_periods_per_year(frequency, periods_per_year)
    excess = _excess_returns(
        _as_returns(returns, min_observations=3),
        risk_free,
        periods_per_year=periods,
        risk_free_kind=risk_free_kind,
    )
    n_obs = len(excess)
    if lags is None:
        lags = _newey_west_lags(n_obs)
    if lags < 0 or lags > n_obs - 1:
        raise ConfigError(f"lags vaut {lags}, attendu entre 0 et {n_obs - 1}")
    periodic_sharpe = sharpe_ratio(
        excess,
        frequency=frequency,
        annualize=False,
        ddof=ddof,
        periods_per_year=periods,
    )
    iid = math.sqrt((1.0 + 0.5 * periodic_sharpe**2) / n_obs)
    lo = _lo_standard_error(excess, lags=lags)
    scale = math.sqrt(periods) if annualize else 1.0
    return SharpeStandardError(
        iid=iid * scale,
        lo=lo * scale,
        sharpe=periodic_sharpe * scale,
        n_observations=n_obs,
        lags=lags,
        annualized=annualize,
    )


def sharpe_confidence_interval(
    returns: ReturnSeries | Sequence[float],
    *,
    frequency: Frequency,
    risk_free: float | ReturnSeries = 0.0,
    confidence: float = DEFAULT_CONFIDENCE,
    method: SharpeErrorMethod = "lo",
    annualize: bool = True,
    lags: int | None = None,
    risk_free_kind: RateKind = "annual",
    ddof: int = 1,
    periods_per_year: float | None = None,
) -> ConfidenceInterval:
    r"""Rend un intervalle de confiance normal autour du ratio de Sharpe.

    **(1) Le problème**. Un ratio de Sharpe publié seul laisse croire à une
    précision qu'il n'a pas. L'intervalle rend visible ce que l'échantillon
    permet réellement d'affirmer.

    **(2) L'intuition**. L'estimateur est asymptotiquement normal autour de la
    vraie valeur ; l'intervalle est donc le point estimé, plus ou moins un
    quantile normal fois l'erreur type.

    **(3) La formule**.

    .. math::

        \left[\widehat{SR} - z_{1-\alpha/2}\,\widehat{SE},\;
              \widehat{SR} + z_{1-\alpha/2}\,\widehat{SE}\right]

    **(4) Les variables**. :math:`z_{1-\alpha/2}` le quantile de la loi normale
    centrée réduite, 1,959964 à 95 % ; :math:`\widehat{SE}` l'erreur type de
    :func:`sharpe_standard_error`.

    **(5) Les hypothèses**. Normalité asymptotique de l'estimateur, donc
    intervalle symétrique. Elle est raisonnable au-delà de quelques centaines
    d'observations et douteuse en deçà de cinquante, PRÉCEPTE non mesuré ici.

    **(6) La provenance**. Lo (2002) pour l'erreur type et pour la construction
    de l'intervalle sous cette approximation.

    **(7) Les limites**. L'intervalle est symétrique alors que la loi exacte du
    ratio de Sharpe ne l'est pas en petit échantillon. Sur un échantillon court,
    la borne basse est trop haute et la couverture réelle inférieure au niveau
    annoncé. Ampleur NON MESURÉE ici.

    **(8) Les alternatives**. Un intervalle par bootstrap par blocs, asymétrique
    par construction, ou l'intervalle exact sous normalité fondé sur la loi t
    non centrée.

    **(9) Pourquoi celui-ci**. Il se calcule en une passe, il s'appuie sur la
    même erreur type que le test de :func:`sharpe_tstat`, et les deux disent donc
    exactement la même chose.

    **(10) Comment vérifier**. La largeur vaut exactement
    :math:`2 z_{1-\alpha/2} \widehat{SE}`, et le point estimé est le centre.
    Le test du module contrôle les deux identités contre ``scipy.stats.norm``.

    Args:
        returns: les rendements simples de la stratégie.
        frequency: la fréquence d'observation.
        risk_free: le taux sans risque, annuel par défaut.
        confidence: le niveau de confiance, strictement entre 0 et 1.
        method: ``"lo"`` pour l'erreur type robuste, ``"iid"`` pour la simple.
        annualize: échelle annuelle si vrai, échelle de la période sinon.
        lags: retards du noyau de Bartlett, règle automatique sans valeur.
        risk_free_kind: ``"annual"`` ou ``"periodic"``.
        ddof: degrés de liberté de l'écart type.
        periods_per_year: comptage mesuré du nombre de périodes par an.

    Returns:
        Un :class:`ConfidenceInterval` qui porte ses bornes et sa fabrication.

    Raises:
        ConfigError: niveau de confiance hors de ]0, 1[, ou méthode inconnue.
    """
    if not 0.0 < confidence < 1.0:
        raise ConfigError(f"confidence vaut {confidence}, attendu strictement entre 0 et 1")
    if method not in ("lo", "iid"):
        raise ConfigError(f"method vaut {method!r}, attendu 'lo' ou 'iid'")
    errors = sharpe_standard_error(
        returns,
        frequency=frequency,
        risk_free=risk_free,
        annualize=annualize,
        lags=lags,
        risk_free_kind=risk_free_kind,
        ddof=ddof,
        periods_per_year=periods_per_year,
    )
    standard_error = errors.lo if method == "lo" else errors.iid
    quantile = float(stats.norm.ppf(0.5 + confidence / 2.0))
    half_width = quantile * standard_error
    return ConfidenceInterval(
        low=errors.sharpe - half_width,
        high=errors.sharpe + half_width,
        confidence=confidence,
        sharpe=errors.sharpe,
        standard_error=standard_error,
        method=method,
    )


def sharpe_tstat(
    returns: ReturnSeries | Sequence[float],
    *,
    frequency: Frequency,
    risk_free: float | ReturnSeries = 0.0,
    method: SharpeErrorMethod = "lo",
    lags: int | None = None,
    risk_free_kind: RateKind = "annual",
    ddof: int = 1,
    periods_per_year: float | None = None,
) -> float:
    r"""Rend la statistique de test du ratio de Sharpe contre zéro.

    **(1) Le problème**. Savoir si un Sharpe positif mesuré est distinguable de
    zéro, c'est-à-dire s'il survivrait à un autre échantillon.

    **(2) L'intuition**. Le point estimé se divise par son incertitude. Deux
    écarts types de distance à zéro sont le seuil usuel de 5 %.

    **(3) La formule**.

    .. math::

        t = \frac{\widehat{SR}}{\widehat{SE}(\widehat{SR})}

    Le rapport est le même en périodique et en annualisé, les deux termes étant
    multipliés par la même racine de :math:`N`. La valeur rendue est donc sans
    échelle, ce qui est voulu.

    **(4) Les variables**. :math:`\widehat{SR}` le ratio de Sharpe périodique,
    :math:`\widehat{SE}` son erreur type, i.i.d. ou robuste selon ``method``.

    **(5) Les hypothèses**. Normalité asymptotique de l'estimateur.

    **(6) La provenance**. Lo (2002) ; Jobson et Korkie (1981) pour la version
    i.i.d.

    **(7) Les limites**. Le test porte sur UNE série choisie d'avance. Appliqué
    à la meilleure de vingt stratégies, il rejette bien trop souvent : le seuil
    de 5 % devient 64 % de fausse découverte au moins une fois sur vingt essais
    indépendants, calcul MODÉLISÉ, :math:`1 - 0{,}95^{20} = 0{,}642`. La
    correction du nombre d'essais vit dans ``quantlab.validation.dsr``.

    **(8) Les alternatives**. Le test classique de la moyenne,
    :math:`t = \widehat{SR}\sqrt{T}`, qui ignore l'incertitude sur l'écart type
    et surestime donc la significativité. Pour un Sharpe périodique de 0,5,
    l'erreur type i.i.d. vaut :math:`\sqrt{1{,}125/T}` au lieu de
    :math:`\sqrt{1/T}`, soit une statistique 6,1 % trop grande dans la version
    classique, MODÉLISÉ.

    **(9) Pourquoi celle-ci**. Elle partage son erreur type avec l'intervalle de
    confiance du module, donc les deux ne peuvent pas se contredire.

    **(10) Comment vérifier**. Le test du module contrôle
    :math:`t = SR / SE` contre les deux quantités calculées séparément, et
    l'invariance du :math:`t` à l'annualisation.

    Args:
        returns: les rendements simples de la stratégie.
        frequency: la fréquence d'observation.
        risk_free: le taux sans risque, annuel par défaut.
        method: ``"lo"`` ou ``"iid"``.
        lags: retards du noyau de Bartlett, règle automatique sans valeur.
        risk_free_kind: ``"annual"`` ou ``"periodic"``.
        ddof: degrés de liberté de l'écart type.
        periods_per_year: comptage mesuré du nombre de périodes par an.

    Returns:
        La statistique :math:`t`, sans unité. Sa valeur p bilatérale s'obtient
        par ``2 * (1 - scipy.stats.norm.cdf(abs(t)))``.

    Raises:
        ConfigError: si ``method`` est inconnu.
    """
    if method not in ("lo", "iid"):
        raise ConfigError(f"method vaut {method!r}, attendu 'lo' ou 'iid'")
    errors = sharpe_standard_error(
        returns,
        frequency=frequency,
        risk_free=risk_free,
        annualize=False,
        lags=lags,
        risk_free_kind=risk_free_kind,
        ddof=ddof,
        periods_per_year=periods_per_year,
    )
    standard_error = errors.lo if method == "lo" else errors.iid
    return errors.sharpe / standard_error


def adjusted_sharpe_ratio(
    returns: ReturnSeries | Sequence[float],
    *,
    frequency: Frequency,
    risk_free: float | ReturnSeries = 0.0,
    annualize: bool = True,
    risk_free_kind: RateKind = "annual",
    ddof: int = 1,
    periods_per_year: float | None = None,
) -> float:
    r"""Rend le ratio de Sharpe corrigé de l'asymétrie et de l'aplatissement.

    **(1) Le problème**. Le ratio de Sharpe ne regarde que deux moments. Une
    stratégie qui gagne un peu chaque mois et perd beaucoup rarement, comme la
    vente d'options hors de la monnaie, obtient un Sharpe élevé jusqu'à la perte
    qui efface plusieurs années. Deux séries de même moyenne et de même écart
    type ne valent pas la même chose pour l'investisseur.

    **(2) L'intuition**. On développe l'utilité espérée au quatrième ordre. Un
    investisseur aime l'asymétrie positive et déteste les queues épaisses, donc
    la correction ajoute un terme proportionnel à l'asymétrie et retranche un
    terme proportionnel à l'excès d'aplatissement.

    **(3) La formule**.

    .. math::

        ASR = SR \left[1 + \frac{S}{6}SR - \frac{K - 3}{24}SR^2\right]

    **(4) Les variables**. :math:`SR` le ratio de Sharpe PÉRIODIQUE, :math:`S`
    l'asymétrie d'échantillon, :math:`K` l'aplatissement non centré, donc
    :math:`K - 3` l'excès d'aplatissement, nul pour une loi normale.

    **Sur quelle échelle la correction s'applique**. Ici sur l'échelle de la
    PÉRIODE, où :math:`S` et :math:`K` sont mesurés, puis le résultat est
    annualisé en :math:`\sqrt{N}` comme le Sharpe lui-même. La convention
    concurrente applique la correction au Sharpe déjà annualisé tout en gardant
    des moments périodiques, ce qui mélange deux horizons et gonfle le terme en
    :math:`SR^2` d'un facteur :math:`N`. Ce module refuse ce mélange, et le
    déclare plutôt que de le subir.

    **(5) Les hypothèses**. Utilité à aversion absolue constante, développement
    de Taylor tronqué au quatrième ordre, moments d'ordre trois et quatre finis
    et bien estimés.

    **(6) La provenance**. Pezier et White (2006), « The Relative Merits of
    Investable Hedge Fund Indices and of Funds of Hedge Funds in Optimal
    Portfolio Construction », ICMA Centre Discussion Paper DP2006-10. Le
    développement remonte à Cornish et Fisher (1938) pour l'expansion des
    quantiles.

    **(7) Les limites**. Le développement suppose les termes d'ordre trois et
    quatre petits. Pour un Sharpe périodique élevé et un aplatissement extrême,
    le crochet peut devenir négatif et le ratio corrigé changer de signe, ce qui
    n'a plus de sens économique. Ce module NE tronque PAS le résultat : une
    valeur aberrante montre que l'approximation ne tient pas, et la masquer
    effacerait cet avertissement. Second point, l'asymétrie et l'aplatissement
    d'échantillon sont très mal estimés en petit échantillon, leur erreur type
    valant respectivement :math:`\sqrt{6/T}` et :math:`\sqrt{24/T}` sous
    normalité, soit 0,24 et 0,49 pour 100 observations, MODÉLISÉ.

    **(8) Les alternatives**. Le Sharpe probabiliste de Bailey et López de Prado
    (2012), qui rend la probabilité que le vrai Sharpe dépasse un seuil sous une
    loi non normale, plutôt qu'un point corrigé.

    **(9) Pourquoi celle-ci**. Elle garde l'unité et l'ordre de grandeur du
    Sharpe, donc elle se compare directement à lui, et l'écart entre les deux se
    lit comme le prix des moments supérieurs.

    **(10) Comment vérifier**. Sur une série symétrique, l'asymétrie est nulle et
    le premier terme de correction disparaît. Le test du module reprend une
    série de quatre rendements dont les moments se calculent à la main :
    asymétrie nulle, aplatissement 1,36, donc excès -1,64.

    Args:
        returns: les rendements simples, quatre observations au minimum.
        frequency: la fréquence d'observation.
        risk_free: le taux sans risque, annuel par défaut.
        annualize: échelle annuelle si vrai.
        risk_free_kind: ``"annual"`` ou ``"periodic"``.
        ddof: degrés de liberté de l'écart type du ratio de Sharpe. Les moments
            d'ordre trois et quatre restent des moments d'échantillon non
            corrigés, écart d'ordre :math:`1/T` DÉCLARÉ.
        periods_per_year: comptage mesuré du nombre de périodes par an.

    Returns:
        Le ratio de Sharpe ajusté, annualisé sauf indication contraire.

    Raises:
        InsufficientDataError: moins de quatre observations, ou écart type nul.
    """
    periods = _resolve_periods_per_year(frequency, periods_per_year)
    excess = _excess_returns(
        _as_returns(returns, min_observations=MIN_OBSERVATIONS_FOURTH_MOMENT),
        risk_free,
        periods_per_year=periods,
        risk_free_kind=risk_free_kind,
    )
    periodic_sharpe = sharpe_ratio(
        excess,
        frequency=frequency,
        annualize=False,
        ddof=ddof,
        periods_per_year=periods,
    )
    skewness = _sample_skewness(excess)
    excess_kurtosis = _sample_excess_kurtosis(excess)
    adjusted = periodic_sharpe * (
        1.0 + (skewness / 6.0) * periodic_sharpe - (excess_kurtosis / 24.0) * periodic_sharpe**2
    )
    return adjusted * math.sqrt(periods) if annualize else adjusted


def sortino_ratio(
    returns: ReturnSeries | Sequence[float],
    *,
    frequency: Frequency,
    risk_free: float | ReturnSeries = 0.0,
    target: float | ReturnSeries | None = None,
    annualize: bool = True,
    risk_free_kind: RateKind = "annual",
    target_kind: RateKind = "annual",
    periods_per_year: float | None = None,
) -> float:
    r"""Rend le ratio de Sortino, excédent par unité de semi-écart type de baisse.

    **(1) Le problème**. L'écart type punit la hausse autant que la baisse. Une
    stratégie qui gagne parfois beaucoup est pénalisée exactement comme une
    stratégie qui perd parfois beaucoup, alors qu'aucun investisseur ne les
    confond.

    **(2) L'intuition**. On ne compte au dénominateur que les écarts SOUS une
    cible. La volatilité de bonne nature ne coûte plus rien.

    **(3) La formule**.

    .. math::

        Sortino = \frac{\bar{r} - r_f}{DD(\tau)}, \qquad
        DD(\tau) = \sqrt{\frac{1}{T}\sum_{t=1}^{T}\left[\min(r_t - \tau,\, 0)\right]^2}

    **(4) Les variables**. :math:`\tau` la cible sous laquelle un rendement
    compte comme une perte, égale au taux sans risque par défaut ; :math:`DD` le
    semi-écart type de baisse ; les autres comme au ratio de Sharpe.

    **La convention qui change tout au dénominateur**. La somme est divisée par
    :math:`T`, le nombre TOTAL d'observations, et non par le nombre
    d'observations sous la cible. Diviser par le nombre de baisses donnerait un
    ratio qui s'améliore quand les baisses se raréfient tout en restant aussi
    profondes, ce qui est le contraire de ce qu'on veut mesurer. Cette
    convention est celle de Sortino et Price (1994) et celle du laboratoire.

    **(5) Les hypothèses**. Une cible économiquement justifiée, et assez
    d'observations sous cette cible pour que le semi-écart type soit estimable.

    **(6) La provenance**. Sortino et van der Meer (1991), « Downside Risk »,
    Journal of Portfolio Management 17(4) ; Sortino et Price (1994),
    « Performance Measurement in a Downside Risk Framework », Journal of
    Investing 3(3).

    **(7) Les limites**. Le dénominateur ne repose que sur une partie de
    l'échantillon, donc il est plus bruité que l'écart type complet. Sur une
    série sans aucune observation sous la cible, il vaut zéro et le ratio n'est
    pas défini ; ce module lève alors une erreur plutôt que de rendre l'infini.

    **(8) Les alternatives**. Le ratio d'Omega, qui utilise la loi entière sous
    et au-dessus du seuil, et le ratio de Calmar, qui remplace la dispersion par
    le pire repli.

    **(9) Pourquoi ici**. C'est la mesure attendue par la littérature des fonds
    de couverture, celle que le laboratoire réplique le plus souvent.

    **(10) Comment vérifier, et une fausse identité à ne pas répéter**. On lit
    souvent que « le Sortino égale le Sharpe quand la série est symétrique et
    que la cible vaut la moyenne ». C'est FAUX en tant qu'énoncé utile. Une
    série symétrique autour de sa moyenne, une cible égale à cette moyenne et un
    taux sans risque qui vaut lui aussi la moyenne donnent deux ratios nuls.
    L'identité est alors vraie et vide.

    L'identité non triviale est autre, et le test du module la vérifie au
    quinzième chiffre. Pour une série symétrique autour de sa moyenne, la moitié
    de la variance vient des écarts négatifs, donc
    :math:`DD(\bar{r}) = \sigma_{pop}/\sqrt{2}` et

    .. math::

        Sortino(\tau = \bar{r}) = \sqrt{2} \; \frac{\bar{r} - r_f}{\sigma_{pop}}
        = \sqrt{2} \; SR_{pop}

    Exemple travaillé, quatre rendements de 3 %, -1 %, 2 % et 0 %. La moyenne
    vaut 1 % et les écarts sont +2, -2, +1 et -1 point, donc symétriques. Le
    semi-écart type sous 1 % vaut :math:`\sqrt{(0{,}02^2 + 0{,}01^2)/4} = 1{,}118
    \%`, le Sortino vaut 0,894427, l'écart type de population vaut 1,581139 %,
    le Sharpe vaut 0,632456, et leur rapport vaut exactement :math:`\sqrt{2}`.

    Args:
        returns: les rendements simples de la stratégie.
        frequency: la fréquence d'observation.
        risk_free: le taux du numérateur, annuel par défaut.
        target: la cible du dénominateur. Sans valeur, elle vaut le taux sans
            risque, ce qui est la convention usuelle.
        annualize: numérateur multiplié par :math:`N` et dénominateur par
            :math:`\sqrt{N}` si vrai.
        risk_free_kind: ``"annual"`` ou ``"periodic"``.
        target_kind: ``"annual"`` ou ``"periodic"``.
        periods_per_year: comptage mesuré du nombre de périodes par an.

    Returns:
        Le ratio de Sortino, annualisé sauf indication contraire.

    Raises:
        InsufficientDataError: moins de deux observations, ou aucune observation
            sous la cible.
    """
    periods = _resolve_periods_per_year(frequency, periods_per_year)
    series = _as_returns(returns)
    excess = _excess_returns(series, risk_free, periods_per_year=periods, risk_free_kind=risk_free_kind)
    if target is None:
        periodic_target = _to_periodic_rate(
            risk_free, periods_per_year=periods, kind=risk_free_kind, label="risk_free"
        )
    else:
        periodic_target = _to_periodic_rate(
            target, periods_per_year=periods, kind=target_kind, label="target"
        )
    if isinstance(periodic_target, pd.Series):
        aligned = periodic_target.reindex(series.index)
        if bool(aligned.isna().any()):
            raise DataQualityError("la cible ne couvre pas toutes les dates des rendements")
        shortfall = np.minimum(series.to_numpy() - aligned.to_numpy(), 0.0)
    else:
        shortfall = np.minimum(series.to_numpy() - float(periodic_target), 0.0)
    downside = math.sqrt(float(np.mean(shortfall**2)))
    if downside <= 0.0:
        raise InsufficientDataError(
            "aucune observation sous la cible : le semi-écart type de baisse est nul "
            "et le ratio de Sortino n'est pas défini"
        )
    horizon = periods if annualize else 1.0
    return float(excess.mean()) * horizon / (downside * math.sqrt(horizon))


def calmar_ratio(
    returns: ReturnSeries | Sequence[float],
    *,
    frequency: Frequency,
    periods_per_year: float | None = None,
    drawdown_floor: float = DEFAULT_VOLATILITY_FLOOR,
) -> float:
    r"""Rend le ratio de Calmar, croissance annualisée sur pire repli.

    **(1) Le problème**. Un investisseur ne quitte pas une stratégie parce que sa
    variance a monté. Il la quitte quand son capital a fondu de 40 % et qu'il ne
    supporte plus d'attendre. La contrainte qui décide est le repli, pas l'écart
    type.

    **(2) L'intuition**. On divise ce que la stratégie a rapporté par an par la
    pire perte subie entre un sommet et le creux qui suit.

    **(3) La formule**.

    .. math::

        Calmar = \frac{CAGR}{|MDD|}, \qquad
        CAGR = \left[\prod_{t=1}^{T}(1 + r_t)\right]^{N/T} - 1

    .. math::

        MDD = \max_{t} \frac{\max_{s \le t} W_s - W_t}{\max_{s \le t} W_s},
        \qquad W_t = \prod_{u \le t}(1 + r_u), \; W_0 = 1

    **(4) Les variables**. :math:`W_t` le patrimoine composé partant de 1,
    :math:`MDD` le pire repli en fraction du sommet atteint avant lui,
    :math:`CAGR` la croissance annuelle composée.

    **(5) Les hypothèses**. Rendements simples composables, donc supérieurs ou
    égaux à -100 %, et une période assez longue pour que le pire repli observé
    soit représentatif.

    **(6) La provenance**. Young (1991), « Calmar Ratio: A Smoother Tool »,
    Futures magazine, octobre 1991. L'original se calcule sur une fenêtre
    glissante de 36 mois.

    **(7) Les limites, et la principale est sévère**. Le pire repli est un
    MAXIMUM, donc il croît mécaniquement avec la longueur de l'échantillon :
    plus on observe, plus on trouve pire, et le ratio baisse sans qu'aucune
    stratégie ait changé. Deux Calmar calculés sur des périodes de longueurs
    différentes ne se comparent pas. Ce module retient la fenêtre COMPLÈTE et
    non les 36 mois de l'original, choix DÉCLARÉ, et l'échantillon doit donc
    accompagner le chiffre.

    **(8) Les alternatives**. Le ratio de Sterling, qui moyenne les replis
    annuels au lieu de retenir le pire, et le ratio de Burke, qui prend la
    racine de la somme des carrés des replis. Les deux sont plus stables et
    moins lisibles.

    **(9) Pourquoi ici**. Il parle la langue du comité d'investissement, qui
    raisonne en perte maximale supportable, pas en écart type.

    **Le pire repli n'est pas recalculé ici**. Il vient de
    :func:`quantlab.analytics.drawdown.max_drawdown`, qui le rend NÉGATIF ; sa
    valeur absolue entre au dénominateur. La règle 12 du laboratoire interdit
    d'implémenter une métrique deux fois, et le repli en est une.

    **(10) Comment vérifier**. Le test du module recalcule séparément les deux
    termes, à la main, sur quatre rendements mensuels de +10 %, -20 %, +15 % et
    +5 %. Le patrimoine finit à 1,0626, donc une croissance annualisée de
    :math:`1{,}0626^3 - 1 = 19{,}9802\%`. Le pire repli vaut
    :math:`(1{,}1 - 0{,}88)/1{,}1 = 20\%`, donc un Calmar de 0,999008.

    Args:
        returns: les rendements simples de la stratégie.
        frequency: la fréquence d'observation, qui fixe l'annualisation.
        periods_per_year: comptage mesuré du nombre de périodes par an.
        drawdown_floor: seuil sous lequel le repli est tenu pour nul. Un repli
            de 1e-16 issu d'un arrondi rendrait un ratio de 1e15.

    Returns:
        Le ratio de Calmar. Il est toujours annualisé : la croissance composée
        n'a pas de sens sur une échelle plus courte que l'année.

    Raises:
        InsufficientDataError: moins de deux observations, ou aucun repli, le
            ratio étant alors infini.
        DataQualityError: un rendement inférieur à -100 %.
    """
    periods = _resolve_periods_per_year(frequency, periods_per_year)
    series = _as_returns(returns)
    drawdown = abs(max_drawdown(series))
    if drawdown <= drawdown_floor:
        raise InsufficientDataError(
            "aucun repli mesuré sur la période : le ratio de Calmar serait infini, "
            "ce qui signale un échantillon trop court plutôt qu'une stratégie parfaite"
        )
    return _compounded_return(series, horizon_periods=periods) / drawdown


def information_ratio(
    returns: ReturnSeries | Sequence[float],
    benchmark: ReturnSeries | Sequence[float],
    *,
    frequency: Frequency,
    annualize: bool = True,
    ddof: int = 1,
    periods_per_year: float | None = None,
    volatility_floor: float = DEFAULT_VOLATILITY_FLOOR,
) -> float:
    r"""Rend le ratio de l'information, écart au repère divisé par son écart type.

    **(1) Le problème**. Un gérant indiciel amélioré qui bat son repère de 2 %
    par an est bon si son écart au repère est régulier, et chanceux si cet écart
    saute de plus ou moins 15 %. Le rendement excédentaire seul ne dit pas
    lequel des deux on regarde.

    **(2) L'intuition**. On mesure la performance active, la différence de
    rendement avec le repère, et on la rapporte à sa propre dispersion. Le ratio
    répond à « combien d'écart de suivi le gérant consomme par point d'avance ».

    **(3) La formule**.

    .. math::

        IR = \frac{\overline{(r_t - b_t)} \, N}{TE}, \qquad
        TE = \hat{\sigma}(r_t - b_t)\sqrt{N}

    **(4) Les variables**. :math:`r_t` le rendement du portefeuille,
    :math:`b_t` celui du repère, :math:`r_t - b_t` le rendement actif,
    :math:`TE` l'écart de suivi annualisé, qui est l'écart type du rendement
    actif et rien d'autre.

    **Le taux sans risque n'apparaît pas**. Il se simplifie dans la différence,
    puisqu'il est retranché des deux côtés. Le soustraire une seconde fois est
    une erreur fréquente et elle abaisse le ratio.

    **(5) Les hypothèses**. Portefeuille et repère observés aux mêmes dates,
    même fréquence, même devise, et rendement actif non autocorrélé pour que
    l'annualisation en :math:`\sqrt{N}` tienne.

    **(6) La provenance**. Grinold et Kahn (2000), « Active Portfolio
    Management », deuxième édition, chapitres 5 et 6. La loi fondamentale de la
    gestion active y relie le ratio au pouvoir prédictif :
    :math:`IR \approx IC \sqrt{BR}`, où :math:`IC` est la corrélation entre
    prévision et réalisation et :math:`BR` le nombre de paris indépendants par
    an.

    **(7) Les limites**. Le ratio dépend entièrement du repère choisi, et
    changer de repère change le verdict sans qu'aucune décision de gestion ait
    bougé. Il ignore de plus le sens de l'écart : un écart de suivi dû à des
    surperformances est puni comme un écart dû à des retards.

    **(8) Les alternatives**. L'alpha d'une régression sur le repère, qui
    corrige du bêta au lieu de le supposer égal à 1. Ou le ratio de Sharpe de la
    série active, qui en diffère par le seul traitement du taux sans risque.

    **(9) Pourquoi ici**. Toute stratégie du laboratoire se compare à un repère
    passif, et ce ratio est la forme normalisée de cette comparaison.

    **(10) Comment vérifier**. Le test du module calcule à la main l'écart
    actif, sa moyenne, son écart type et le rapport, sur quatre observations.

    Args:
        returns: les rendements simples du portefeuille.
        benchmark: les rendements du repère. Une série s'aligne par l'index,
            une suite de nombres doit avoir la même longueur que ``returns``.
        frequency: la fréquence d'observation.
        annualize: échelle annuelle si vrai.
        ddof: degrés de liberté de l'écart type du rendement actif.
        periods_per_year: comptage mesuré du nombre de périodes par an.
        volatility_floor: seuil relatif sous lequel l'écart de suivi est tenu
            pour nul, même raison qu'au ratio de Sharpe.

    Returns:
        Le ratio de l'information, annualisé sauf indication contraire.

    Raises:
        InsufficientDataError: moins de deux dates communes, ou écart de suivi
            nul, ce qui arrive quand le portefeuille réplique exactement le
            repère.
        DataQualityError: si les deux suites n'ont pas la même longueur alors
            qu'aucune ne porte d'index de dates comparable.
    """
    periods = _resolve_periods_per_year(frequency, periods_per_year)
    portfolio = _as_returns(returns, label="rendements du portefeuille")
    if isinstance(benchmark, pd.Series):
        reference = _as_returns(benchmark, label="rendements du repère")
        common = portfolio.index.intersection(reference.index)
        active = portfolio.loc[common] - reference.loc[common]
    else:
        reference = _as_returns(benchmark, label="rendements du repère")
        if len(reference) != len(portfolio):
            raise DataQualityError(
                f"{len(portfolio)} rendements de portefeuille contre {len(reference)} du "
                "repère : sans index de dates, les longueurs doivent coïncider"
            )
        active = pd.Series(
            portfolio.to_numpy() - reference.to_numpy(), index=portfolio.index, dtype="float64"
        )
    if len(active) < MIN_OBSERVATIONS:
        raise InsufficientDataError(f"{len(active)} date(s) commune(s) entre le portefeuille et le repère")
    tracking_error = float(active.std(ddof=ddof))
    if not math.isfinite(tracking_error) or tracking_error <= _volatility_threshold(active, volatility_floor):
        raise InsufficientDataError(
            "l'écart de suivi est nul : le portefeuille reproduit le repère et le "
            "ratio de l'information n'est pas défini"
        )
    horizon = periods if annualize else 1.0
    return float(active.mean()) * horizon / (tracking_error * math.sqrt(horizon))


def omega_ratio(
    returns: ReturnSeries | Sequence[float],
    *,
    frequency: Frequency,
    threshold: float = 0.0,
    threshold_kind: RateKind = "annual",
    periods_per_year: float | None = None,
) -> float:
    r"""Rend le ratio d'Omega, gains au-dessus d'un seuil sur pertes en dessous.

    **(1) Le problème**. Le ratio de Sharpe résume une loi entière par deux
    nombres. Deux stratégies de mêmes moyenne et variance mais de formes très
    différentes reçoivent le même score.

    **(2) L'intuition**. On coupe la loi des rendements à un seuil. Au-dessus, on
    somme tout ce qui dépasse ; en dessous, tout ce qui manque. Le rapport des
    deux dit combien de gain on obtient par unité de perte, sans jeter aucune
    information de la loi.

    **(3) La formule**.

    .. math::

        \Omega(\tau) = \frac{\int_{\tau}^{b}[1 - F(x)]\,dx}{\int_{a}^{\tau}F(x)\,dx}
        = \frac{\mathbb{E}[\max(r - \tau,\, 0)]}{\mathbb{E}[\max(\tau - r,\, 0)]}

    En version d'échantillon, c'est la somme des dépassements divisée par la
    somme des manques.

    **(4) Les variables**. :math:`\tau` le seuil, :math:`F` la fonction de
    répartition des rendements, :math:`a` et :math:`b` les bornes du support.

    **(5) Les hypothèses**. Aucune sur la forme de la loi, ce qui est l'intérêt
    de la mesure. Il faut seulement des observations des deux côtés du seuil.

    **(6) La provenance**. Keating et Shadwick (2002), « A Universal Performance
    Measure », Journal of Performance Measurement 6(3).

    **(7) Les limites**. Le ratio ne s'annualise par aucune règle simple : son
    horizon est celui des rendements fournis, et un Omega quotidien ne se
    convertit pas en Omega annuel. C'est la raison pour laquelle cette fonction
    n'a pas d'argument ``annualize``, la fréquence ne servant qu'à ramener le
    seuil à la période. Deuxième limite, le ratio dépend fortement du seuil, et
    l'ordre de deux stratégies peut s'inverser d'un seuil à l'autre.

    **(8) Les alternatives**. Le ratio de gain sur perte, qui compare les
    moyennes des périodes positives et négatives sans pondérer par l'ampleur, et
    la dominance stochastique d'ordre deux, plus rigoureuse et rarement
    concluante sur des données réelles.

    **(9) Pourquoi ici**. C'est la seule mesure du module qui utilise la loi
    entière, donc le contrôle naturel des trois ratios fondés sur des moments.

    **(10) Comment vérifier**. Deux identités que le test du module contrôle.
    D'abord :math:`\Omega(\bar{r}) = 1` exactement, la somme des dépassements
    moins la somme des manques valant :math:`T(\bar{r} - \tau)`. Ensuite
    :math:`\Omega(\tau) = 1 + (\bar{r} - \tau)/\mathbb{E}[\max(\tau - r, 0)]`.
    Le ratio décroît par ailleurs quand le seuil monte, propriété vérifiée par
    un test de propriété.

    Args:
        returns: les rendements simples de la stratégie.
        frequency: la fréquence d'observation, qui sert à ramener un seuil
            annuel à la période.
        threshold: le seuil, annuel par défaut, zéro par défaut.
        threshold_kind: ``"annual"`` ou ``"periodic"``.
        periods_per_year: comptage mesuré du nombre de périodes par an.

    Returns:
        Le ratio d'Omega au seuil demandé, sans unité, sur l'horizon des
        rendements fournis.

    Raises:
        InsufficientDataError: si aucune observation ne tombe sous le seuil, le
            dénominateur étant alors nul.
    """
    periods = _resolve_periods_per_year(frequency, periods_per_year)
    series = _as_returns(returns)
    periodic_threshold = _to_periodic_rate(
        threshold, periods_per_year=periods, kind=threshold_kind, label="threshold"
    )
    if isinstance(periodic_threshold, pd.Series):
        raise ConfigError("le seuil d'Omega doit être un nombre, pas une série")
    deviations = series.to_numpy() - float(periodic_threshold)
    gains = float(np.sum(np.maximum(deviations, 0.0)))
    losses = float(np.sum(np.maximum(-deviations, 0.0)))
    if losses <= 0.0:
        raise InsufficientDataError(
            "aucune observation sous le seuil : le dénominateur d'Omega est nul et le "
            "ratio n'est pas défini sur cet échantillon"
        )
    return gains / losses

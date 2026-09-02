r"""Les portefeuilles gérés en volatilité, et la constante qui décide de tout.

**Le problème.** Moreira et Muir (2017) multiplient un facteur par l'inverse de
sa variance réalisée du mois précédent, puis remettent le résultat à l'échelle
par une constante. Cette constante est choisie pour que la série gérée ait la
même volatilité que la série d'origine SUR TOUT L'ÉCHANTILLON. Un investisseur
de 1930 ne connaît pas cette constante, et deux articles publiés en font
l'explication principale du résultat.

**Le remède.** Ce module sépare trois objets que la formule mélange. La mesure
de variance vit dans :func:`realized_variance`, :func:`ewma_variance` et
:func:`garch_variance`. La constante vit dans :func:`full_sample_constant` et
:func:`expanding_constant`. Le portefeuille lui-même vit dans
:func:`volatility_managed_returns`, qui reçoit l'une et l'autre. Changer de
constante ne demande donc pas de retoucher la stratégie.

**La règle de causalité.** Le rendement géré du mois :math:`t+1` n'emploie que
des grandeurs connues à la fin du mois :math:`t`. La variance est celle du mois
:math:`t`, décalée d'un mois par :func:`managed_weights`. La constante en
expansion est décalée d'un mois de plus, sans quoi l'écart type du mois courant
entrerait dans le poids du mois courant.

**Provenance.** Moreira, A. et Muir, T. (2017), « Volatility-Managed
Portfolios », *The Journal of Finance* 72(4), 1611-1644. La critique de la
constante vient de Liu, Tang et Zhou (2019), *Journal of Portfolio Management*
46(1), 38-51, et de Cederburg, O'Doherty, Wang et Yan (2020), *Journal of
Financial Economics* 138(1), 95-117.

**Les limites.** Rien ici ne connaît les frais, qui vivent dans
:mod:`quantlab.execution.costs`. Rien ici ne connaît le hors échantillon, qui
vit dans :mod:`quantlab.validation`. Ce module rend des séries, et le jugement
se prend ailleurs.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd

from quantlab.analytics.regression import factor_regression
from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.logging import get_logger
from quantlab.core.types import Frequency

__all__ = [
    "PAPER_RMSE_SCALE",
    "SpanningResult",
    "VarianceMethod",
    "VolatilityManagedResult",
    "appraisal_ratio",
    "combined_sharpe",
    "ewma_variance",
    "expanding_constant",
    "full_sample_constant",
    "garch_variance",
    "hedged_spread",
    "leverage_series",
    "managed_weights",
    "monthly_variance",
    "real_time_combination",
    "spanning_regression",
    "utility_gain",
    "volatility_managed_returns",
]

_LOG = get_logger(__name__)

#: Les trois mesures de variance conditionnelle reconnues par
#: :func:`monthly_variance`.
VarianceMethod = Literal["realized", "ewma", "garch"]

#: Le facteur qui convertit notre volatilité résiduelle annualisée, en
#: pourcentage, vers la colonne « RMSE » du tableau 1 de l'article. MESURÉ par
#: identification : l'article imprime 51,39 pour le marché et annonce un ratio
#: d'appréciation de 0,33, ce qui exige RMSE égale à racine de douze fois la
#: volatilité résiduelle annualisée.
PAPER_RMSE_SCALE: float = math.sqrt(12.0)

#: Le nombre minimal de jours de bourse exigé par défaut dans un mois pour que
#: sa variance réalisée soit retenue. Un seul jour suffit à définir une somme de
#: carrés, donc la valeur par défaut ne filtre rien et le filtrage se déclare.
DEFAULT_MIN_OBSERVATIONS: int = 1

#: Le plancher de variance sous lequel un mois est déclaré dégénéré. Une
#: variance nulle rendrait un poids infini, et la division ne lèverait pas.
VARIANCE_FLOOR: float = 1e-12


def _as_series(values: pd.Series, *, label: str) -> pd.Series:
    """Contrôle qu'une entrée est une série datée, triée et flottante."""
    if not isinstance(values, pd.Series):
        raise ConfigError(f"{label} doit être une pandas.Series, reçu {type(values).__name__}.")
    if not isinstance(values.index, pd.DatetimeIndex):
        raise ConfigError(f"{label} doit porter un DatetimeIndex.")
    if not values.index.is_monotonic_increasing:
        raise DataQualityError(f"{label} n'est pas trié par date croissante.")
    if values.index.has_duplicates:
        raise DataQualityError(f"{label} porte des dates en double.")
    return values.astype(float)


def _month_end_index(period_index: pd.PeriodIndex) -> pd.DatetimeIndex:
    """Rend l'index de fins de mois correspondant à un index de périodes."""
    return pd.DatetimeIndex(period_index.to_timestamp(how="end").normalize(), name="date")


def realized_variance(
    daily_returns: pd.Series,
    *,
    demean: bool = False,
    min_observations: int = DEFAULT_MIN_OBSERVATIONS,
) -> pd.DataFrame:
    r"""Rend la variance réalisée mensuelle d'un facteur, et son compte de jours.

    **Le problème.** L'équation (2) de l'article somme les carrés des écarts à
    la moyenne sur « les 22 jours du mois », avec 22 au dénominateur de cette
    moyenne. Aucun mois n'a exactement 22 jours de bourse, et le texte ne dit
    pas si le diviseur suit le compte réel. Le compte est donc rendu à côté de
    la variance, pour que l'étude puisse le publier au lieu de le supposer.

    **La formule.** Pour le mois :math:`t` comptant :math:`n_t` séances,

    .. math::

        RV_t = \sum_{d=1}^{n_t} \left( f_{t,d} - \bar{f}_t \right)^2,
        \qquad
        \bar{f}_t = \frac{1}{n_t} \sum_{d=1}^{n_t} f_{t,d}

    La moyenne :math:`\bar{f}_t` vaut zéro quand ``demean`` est faux, et la
    somme devient alors la somme des carrés bruts.

    **Les variables.** :math:`f_{t,d}` est le rendement quotidien du facteur au
    jour :math:`d` du mois :math:`t`, :math:`n_t` le nombre de séances du mois,
    :math:`RV_t` la variance réalisée du mois.

    **Les hypothèses.** Les rendements quotidiens sont indépendants entre eux à
    l'intérieur du mois. C'est faux en présence d'autocorrélation, et la somme
    des carrés sous-estime alors la variance mensuelle vraie.

    **Les limites.** Un mois amputé de séances rend une somme plus petite, sans
    que rien ne le signale. C'est la raison d'être de la colonne de comptage et
    du filtre ``min_observations``.

    **Une alternative écartée.** Diviser par :math:`n_t` rendrait une variance
    par jour au lieu d'une variance par mois. Le résultat de la stratégie n'en
    changerait pas, la constante de mise à l'échelle absorbant tout facteur
    multiplicatif constant, mais le nombre publié cesserait d'être celui de
    l'article.

    Args:
        daily_returns: les rendements quotidiens du facteur, en décimales.
        demean: retrancher la moyenne du mois avant d'élever au carré.
        min_observations: le nombre minimal de séances exigé dans le mois.

    Returns:
        Un tableau indexé par fin de mois, portant ``variance`` et
        ``n_observations``. Les mois trop courts portent une variance manquante
        et gardent leur compte réel.

    Raises:
        ConfigError: si ``min_observations`` est inférieur à un.
        InsufficientDataError: si la série quotidienne est vide.

    Example:
        Quatre séances à +1 %, -1 %, +1 % et -1 % dans le même mois. Sans
        centrage, la somme des carrés vaut quatre fois 0,0001, soit 0,0004.
    """
    if min_observations < 1:
        raise ConfigError(f"min_observations doit valoir au moins 1, reçu {min_observations}.")
    series = _as_series(daily_returns, label="daily_returns")
    if series.empty:
        raise InsufficientDataError("la série quotidienne est vide, aucune variance mensuelle possible.")

    groups = series.groupby(series.index.to_period("M"))
    if demean:
        variance = groups.apply(lambda block: float(((block - block.mean()) ** 2).sum()))
    else:
        variance = groups.apply(lambda block: float((block**2).sum()))
    counts = groups.size()

    index = _month_end_index(pd.PeriodIndex(variance.index))
    frame = pd.DataFrame(
        {"variance": variance.to_numpy(dtype=float), "n_observations": counts.to_numpy(dtype=int)},
        index=index,
    )
    frame.loc[frame["n_observations"] < min_observations, "variance"] = np.nan
    frame.loc[frame["variance"] <= VARIANCE_FLOOR, "variance"] = np.nan
    return frame


def ewma_variance(
    daily_returns: pd.Series,
    *,
    halflife_days: float,
    min_observations: int = DEFAULT_MIN_OBSERVATIONS,
) -> pd.DataFrame:
    r"""Rend une variance mensuelle lissée exponentiellement sur les jours passés.

    **Le problème.** La variance réalisée d'un mois donne le même poids à la
    première séance et à la dernière. Après un choc en fin de mois, elle réagit
    donc trop peu, et le portefeuille garde une exposition qu'il aurait dû
    réduire.

    **La formule.** La variance quotidienne lissée suit la récurrence

    .. math::

        h_d = (1 - \lambda)\, f_d^2 + \lambda\, h_{d-1},
        \qquad
        \lambda = 2^{-1 / H}

    et la variance du mois :math:`t` vaut :math:`n_t\, h_{D(t)}`, où
    :math:`D(t)` est la dernière séance du mois.

    **Les variables.** :math:`H` est la demi-vie en séances, :math:`\lambda` le
    facteur d'oubli, :math:`h_d` la variance quotidienne lissée, :math:`n_t` le
    nombre de séances du mois.

    **Les hypothèses.** La variance mensuelle vaut la variance quotidienne
    multipliée par le nombre de séances, ce qui suppose des rendements
    quotidiens non corrélés.

    **Les limites.** Le facteur d'échelle :math:`n_t` n'a aucun effet sur la
    stratégie, la constante de mise à l'échelle absorbant tout facteur commun.
    Il n'est gardé que pour que les deux mesures de variance vivent dans la
    même unité.

    Args:
        daily_returns: les rendements quotidiens du facteur, en décimales.
        halflife_days: la demi-vie du lissage, en séances.
        min_observations: le nombre minimal de séances exigé dans le mois.

    Returns:
        Un tableau de même forme que celui de :func:`realized_variance`.

    Raises:
        ConfigError: si la demi-vie n'est pas strictement positive.

    Example:
        Une demi-vie de 22 séances donne un facteur d'oubli de 0,969, donc une
        fenêtre efficace d'environ 32 séances.
    """
    if halflife_days <= 0.0:
        raise ConfigError(f"halflife_days doit être strictement positif, reçu {halflife_days}.")
    series = _as_series(daily_returns, label="daily_returns")
    smoothed = (series**2).ewm(halflife=halflife_days, adjust=False).mean()
    periods = series.index.to_period("M")
    last = smoothed.groupby(periods).last()
    counts = series.groupby(periods).size()
    index = _month_end_index(pd.PeriodIndex(last.index))
    frame = pd.DataFrame(
        {
            "variance": last.to_numpy(dtype=float) * counts.to_numpy(dtype=float),
            "n_observations": counts.to_numpy(dtype=int),
        },
        index=index,
    )
    frame.loc[frame["n_observations"] < min_observations, "variance"] = np.nan
    frame.loc[frame["variance"] <= VARIANCE_FLOOR, "variance"] = np.nan
    return frame


def garch_variance(
    daily_returns: pd.Series,
    *,
    refit_months: int = 120,
    min_train_days: int = 1260,
    p: int = 1,
    q: int = 1,
    distribution: str = "normal",
    min_observations: int = DEFAULT_MIN_OBSERVATIONS,
) -> pd.DataFrame:
    r"""Rend une variance mensuelle issue d'un GARCH réestimé en expansion.

    **Le problème.** Un GARCH ajusté une fois sur tout l'échantillon connaît la
    crise de 2008 en 1930. Ses paramètres sont alors une information future, et
    l'annexe A.1 de l'article, qui annonce que des modèles plus élaborés font
    mieux, tombe sous cette critique.

    **Le remède.** Les paramètres sont réestimés à intervalles réguliers sur les
    seules séances passées, puis la variance conditionnelle est filtrée en avant
    avec ces paramètres figés. Le filtre est causal par construction, la
    récurrence GARCH n'employant que des rendements antérieurs.

    **La formule.** Avec :math:`p = q = 1`,

    .. math::

        h_d = \omega + \alpha\, \varepsilon_{d-1}^2 + \beta\, h_{d-1}

    et la variance du mois :math:`t` vaut la somme des :math:`h_d` de ses
    séances.

    **Les variables.** :math:`\omega`, :math:`\alpha` et :math:`\beta` sont les
    paramètres estimés sur le passé, :math:`\varepsilon_d` le rendement centré
    du jour, :math:`h_d` sa variance conditionnelle.

    **Les hypothèses.** Les paramètres restent valables jusqu'à la
    réestimation suivante. Les rendements sont exprimés en pourcentage avant
    l'ajustement, condition numérique demandée par la bibliothèque ``arch``.

    **Les limites.** Le premier bloc de séances, celui qui sert au premier
    ajustement, ne reçoit aucune variance et sort du tableau. Le coût de calcul
    croît avec le nombre de réestimations.

    Args:
        daily_returns: les rendements quotidiens du facteur, en décimales.
        refit_months: le nombre de mois entre deux réestimations.
        min_train_days: le nombre de séances exigé avant le premier ajustement.
        p: l'ordre des termes d'innovation.
        q: l'ordre des termes de variance retardée.
        distribution: la loi des innovations passée à ``arch``.
        min_observations: le nombre minimal de séances exigé dans le mois.

    Returns:
        Un tableau de même forme que celui de :func:`realized_variance`, borné
        aux mois postérieurs au premier ajustement.

    Raises:
        ConfigError: si ``refit_months`` ou ``min_train_days`` est trop petit.
        InsufficientDataError: si la série ne porte pas assez de séances.

    Example:
        Une réestimation tous les 120 mois sur un siècle de séances demande
        environ dix ajustements, et le premier consomme les cinq premières
        années.
    """
    from arch.univariate import arch_model

    if refit_months < 1:
        raise ConfigError(f"refit_months doit valoir au moins 1, reçu {refit_months}.")
    if min_train_days < 100:
        raise ConfigError(f"min_train_days doit valoir au moins 100, reçu {min_train_days}.")
    series = _as_series(daily_returns, label="daily_returns")
    if len(series) <= min_train_days:
        raise InsufficientDataError(
            f"{len(series)} séances disponibles, {min_train_days} exigées avant le premier ajustement."
        )

    scaled = series * 100.0
    model = arch_model(scaled, mean="Constant", vol="GARCH", p=p, q=q, dist=distribution, rescale=False)
    months = pd.PeriodIndex(series.index.to_period("M")).unique().sort_values()
    start_positions: list[int] = []
    for position, month in enumerate(months):
        used = int((series.index.to_period("M") <= month).sum())
        if used >= min_train_days:
            start_positions.append(position)
    if not start_positions:
        raise InsufficientDataError("aucun mois ne dispose du nombre de séances exigé pour l'ajustement.")

    filtered = pd.Series(np.nan, index=series.index, dtype=float)
    first = start_positions[0]
    refit_points = list(range(first, len(months), refit_months))
    for order, point in enumerate(refit_points):
        train_end = months[point]
        train = scaled.loc[series.index.to_period("M") <= train_end]
        fitted = arch_model(
            train, mean="Constant", vol="GARCH", p=p, q=q, dist=distribution, rescale=False
        ).fit(disp="off", show_warning=False)
        fixed = model.fix(fitted.params)
        variance = pd.Series(fixed.conditional_volatility**2, index=series.index, dtype=float)
        block_end = months[refit_points[order + 1]] if order + 1 < len(refit_points) else months[-1]
        mask = (series.index.to_period("M") > train_end) & (series.index.to_period("M") <= block_end)
        filtered.loc[mask] = variance.loc[mask]
        _LOG.info(
            "GARCH réestimé",
            extra={"fin_apprentissage": str(train_end), "n_seances": len(train)},
        )

    periods = series.index.to_period("M")
    total = filtered.groupby(periods).sum(min_count=1) / (100.0**2)
    counts = series.groupby(periods).size()
    index = _month_end_index(pd.PeriodIndex(total.index))
    frame = pd.DataFrame(
        {"variance": total.to_numpy(dtype=float), "n_observations": counts.to_numpy(dtype=int)},
        index=index,
    )
    frame.loc[frame["n_observations"] < min_observations, "variance"] = np.nan
    frame.loc[frame["variance"] <= VARIANCE_FLOOR, "variance"] = np.nan
    return frame.dropna(subset=["variance"])


def monthly_variance(
    daily_returns: pd.Series,
    *,
    method: VarianceMethod = "realized",
    parameters: Mapping[str, Any] | None = None,
) -> pd.DataFrame:
    """Rend la variance mensuelle par la mesure demandée.

    Les trois mesures rendent le même tableau, ce qui permet à l'étude de les
    échanger sans changer une ligne de la stratégie.

    Args:
        daily_returns: les rendements quotidiens du facteur, en décimales.
        method: ``« realized »``, ``« ewma »`` ou ``« garch »``.
        parameters: les arguments nommés propres à la mesure choisie.

    Returns:
        Un tableau indexé par fin de mois, portant ``variance`` et
        ``n_observations``.

    Raises:
        ConfigError: si la mesure demandée n'est pas reconnue.
    """
    kwargs = dict(parameters or {})
    if method == "realized":
        return realized_variance(daily_returns, **kwargs)
    if method == "ewma":
        return ewma_variance(daily_returns, **kwargs)
    if method == "garch":
        return garch_variance(daily_returns, **kwargs)
    raise ConfigError(f"mesure de variance inconnue : {method!r}, attendu realized, ewma ou garch.")


def leverage_series(variance: pd.Series) -> pd.Series:
    r"""Rend l'inverse de la variance, indexé à la date de décision.

    Args:
        variance: la variance mensuelle, indexée par fin de mois.

    Returns:
        La série :math:`1 / \hat{\sigma}^2_t`, indexée comme l'entrée.
    """
    return 1.0 / _as_series(variance, label="variance")


def managed_weights(
    variance: pd.Series,
    *,
    constant: float | pd.Series,
    leverage_cap: float | None = None,
) -> pd.Series:
    r"""Rend le poids détenu chaque mois sur le facteur, sans information future.

    **La règle.** Le poids porté par le mois :math:`t+1` vaut
    :math:`c / \hat{\sigma}^2_t`. Il est donc indexé à la date du mois
    :math:`t+1`, alors que la variance qui le produit porte la date du mois
    :math:`t`. Le décalage se fait ici, une fois, et pas ailleurs.

    Args:
        variance: la variance mensuelle du facteur, indexée par fin de mois.
        constant: la constante de mise à l'échelle, un nombre ou une série
            déjà décalée dont l'index suit celui de la variance.
        leverage_cap: le poids maximal autorisé, appliqué APRÈS la constante,
            donc lisible directement comme un levier.

    Returns:
        La série des poids, indexée par le mois où ils sont détenus.

    Raises:
        ConfigError: si la constante est une série d'index incompatible.
    """
    if leverage_cap is not None and leverage_cap <= 0.0:
        raise ConfigError(f"leverage_cap doit être strictement positif, reçu {leverage_cap}.")
    inverse = leverage_series(variance)
    if isinstance(constant, pd.Series):
        aligned = _as_series(constant, label="constant").reindex(inverse.index)
        weights = aligned * inverse
    else:
        weights = float(constant) * inverse
    if leverage_cap is not None:
        weights = weights.clip(upper=leverage_cap)
    shifted = weights.shift(1)
    shifted.name = "weight"
    return shifted


def full_sample_constant(factor: pd.Series, unscaled: pd.Series) -> float:
    r"""Rend la constante qui égalise les deux écarts types sur tout l'échantillon.

    **Ce que la constante fait, et ce qu'elle cache.** Elle vaut

    .. math::

        c = \frac{\mathrm{sd}(f)}{\mathrm{sd}(f / \hat{\sigma}^2)}

    calculée sur l'échantillon entier. Elle rend les deux séries comparables à
    l'œil et laisse le ratio de Sharpe de la série gérée inchangé. Elle emploie
    en revanche des écarts types que personne ne connaît avant la dernière
    date, ce qui est exactement l'objection de Liu, Tang et Zhou (2019).

    Args:
        factor: le facteur d'origine, mensuel.
        unscaled: le facteur divisé par sa variance retardée, mensuel.

    Returns:
        La constante, un nombre strictement positif.

    Raises:
        InsufficientDataError: si moins de deux mois sont communs aux deux
            séries.
        DataQualityError: si l'un des deux écarts types est nul.
    """
    left, right = _as_series(factor, label="factor").align(
        _as_series(unscaled, label="unscaled"), join="inner"
    )
    frame = pd.concat({"factor": left, "unscaled": right}, axis=1).dropna()
    if len(frame) < 2:
        raise InsufficientDataError(f"{len(frame)} mois communs, deux au moins sont nécessaires.")
    denominator = float(frame["unscaled"].std(ddof=1))
    numerator = float(frame["factor"].std(ddof=1))
    if denominator <= 0.0 or numerator <= 0.0:
        raise DataQualityError("écart type nul : la constante de mise à l'échelle n'existe pas.")
    return numerator / denominator


def expanding_constant(
    factor: pd.Series,
    unscaled: pd.Series,
    *,
    min_periods: int,
) -> pd.Series:
    r"""Rend la constante estimée mois après mois sur le seul passé.

    **La différence avec :func:`full_sample_constant`.** La valeur portée par le
    mois :math:`t` est calculée sur les mois 1 à :math:`t-1`, donc connue à la
    fin du mois :math:`t-1`. Le décalage d'un mois est appliqué ici, et il est
    ce qui sépare une stratégie tenable d'une stratégie rétrospective.

    Args:
        factor: le facteur d'origine, mensuel.
        unscaled: le facteur divisé par sa variance retardée, mensuel.
        min_periods: le nombre de mois exigé avant la première constante.

    Returns:
        La série des constantes, manquante tant que le minimum n'est pas
        atteint.

    Raises:
        ConfigError: si ``min_periods`` est inférieur à deux.

    Example:
        Avec ``min_periods`` égal à 120, la première constante utilisable date
        du 121e mois et emploie les 120 premiers.
    """
    if min_periods < 2:
        raise ConfigError(f"min_periods doit valoir au moins 2, reçu {min_periods}.")
    left, right = _as_series(factor, label="factor").align(
        _as_series(unscaled, label="unscaled"), join="inner"
    )
    frame = pd.concat({"factor": left, "unscaled": right}, axis=1).dropna()
    numerator = frame["factor"].expanding(min_periods).std(ddof=1)
    denominator = frame["unscaled"].expanding(min_periods).std(ddof=1)
    constant = (numerator / denominator).shift(1)
    constant.name = "constant"
    return constant


@dataclass(frozen=True, eq=False)
class VolatilityManagedResult:
    """Le portefeuille géré, ses poids, et la constante qui l'a mis à l'échelle.

    Attributes:
        returns: le rendement mensuel du portefeuille géré.
        base: le facteur d'origine, borné au même index.
        weights: le poids détenu chaque mois sur le facteur.
        constant: la constante employée, nombre ou série.
        n_observations: le nombre de mois communs retenus.
    """

    returns: pd.Series
    base: pd.Series
    weights: pd.Series
    constant: float | pd.Series
    n_observations: int


def volatility_managed_returns(
    factor: pd.Series,
    variance: pd.Series,
    *,
    constant: Literal["full_sample", "expanding"] | float = "full_sample",
    min_periods: int = 120,
    leverage_cap: float | None = None,
) -> VolatilityManagedResult:
    r"""Rend le portefeuille géré en volatilité d'un facteur mensuel.

    **La formule, équation (1) de l'article.**

    .. math::

        f^{\sigma}_{t+1} = \frac{c}{\hat{\sigma}^2_t(f)}\, f_{t+1}

    **Les trois choix qu'elle contient.** La mesure de variance
    :math:`\hat{\sigma}^2_t`, faite ailleurs. Le décalage d'un mois, fait par
    :func:`managed_weights`. La constante :math:`c`, faite ici et choisie par
    l'appelant entre le plein échantillon et l'expansion.

    **Les hypothèses.** Le facteur est un rendement en excès, donc autofinancé,
    et un poids supérieur à un ne coûte pas de financement supplémentaire. Cette
    hypothèse est celle de l'article, et elle est fausse pour un investisseur
    réel dont le levier se finance.

    **Les limites.** Aucun frais n'est retranché ici. La constante est calibrée
    sur la série SANS plafond, comme dans l'article, si bien qu'un plafond
    abaisse la volatilité de la série gérée sous celle du facteur.

    Args:
        factor: le facteur d'origine, mensuel, en décimales.
        variance: la variance mensuelle du facteur, indexée par fin de mois.
        constant: ``« full_sample »``, ``« expanding »``, ou une valeur fixée.
        min_periods: le minimum exigé par la constante en expansion.
        leverage_cap: le plafond appliqué à l'inverse de la variance.

    Returns:
        Le résultat complet, rendements, poids et constante.

    Raises:
        InsufficientDataError: si aucun mois ne survit à l'alignement.
        ConfigError: si le mot de la constante n'est pas reconnu.

    Example:
        Avec la constante de plein échantillon, l'écart type de la série gérée
        égale celui du facteur d'origine à la précision machine, ce qui est le
        contrôle le plus simple de l'implémentation.
    """
    monthly = _as_series(factor, label="factor")
    variances = _as_series(variance, label="variance")
    inverse_lagged = managed_weights(variances, constant=1.0)
    left, right = monthly.align(inverse_lagged, join="inner")
    frame = pd.concat({"factor": left, "inverse": right}, axis=1).dropna()
    if frame.empty:
        raise InsufficientDataError("aucun mois commun entre le facteur et sa variance retardée.")
    unscaled = frame["factor"] * frame["inverse"]

    if isinstance(constant, str):
        if constant == "full_sample":
            scale: float | pd.Series = full_sample_constant(frame["factor"], unscaled)
        elif constant == "expanding":
            scale = expanding_constant(frame["factor"], unscaled, min_periods=min_periods)
        else:
            raise ConfigError(
                f"constante inconnue : {constant!r}, attendu « full_sample », « expanding » ou un nombre."
            )
    else:
        scale = float(constant)

    weights = scale * frame["inverse"]
    if leverage_cap is not None:
        if leverage_cap <= 0.0:
            raise ConfigError(f"leverage_cap doit être strictement positif, reçu {leverage_cap}.")
        weights = weights.clip(upper=leverage_cap)
    managed = (weights * frame["factor"]).dropna()
    managed.name = "managed"
    weights = weights.loc[managed.index]
    weights.name = "weight"
    return VolatilityManagedResult(
        returns=managed,
        base=frame["factor"].loc[managed.index],
        weights=weights,
        constant=scale,
        n_observations=len(managed),
    )


@dataclass(frozen=True)
class SpanningResult:
    """Le résultat de la régression d'engendrement du tableau 1 de l'article.

    Attributes:
        n_observations: le nombre de mois de la régression.
        beta: la pente sur le facteur d'origine.
        alpha_annual: l'ordonnée à l'origine annualisée, en décimales.
        alpha_stderr_annual: son erreur type annualisée.
        alpha_tstat: la statistique t de l'ordonnée à l'origine.
        r_squared: le coefficient de détermination.
        residual_vol_annual: l'écart type résiduel annualisé, en décimales.
        paper_rmse: la colonne « RMSE » de l'article, en pourcentage.
        appraisal_ratio: le rapport de l'alpha à la volatilité résiduelle.
    """

    n_observations: int
    beta: float
    alpha_annual: float
    alpha_stderr_annual: float
    alpha_tstat: float
    r_squared: float
    residual_vol_annual: float
    paper_rmse: float
    appraisal_ratio: float

    def as_row(self) -> dict[str, float]:
        """Rend le résultat sous forme de ligne de tableau."""
        return {
            "n_observations": float(self.n_observations),
            "beta": self.beta,
            "alpha_annual_pct": self.alpha_annual * 100.0,
            "alpha_stderr_pct": self.alpha_stderr_annual * 100.0,
            "alpha_tstat": self.alpha_tstat,
            "r_squared": self.r_squared,
            "residual_vol_annual_pct": self.residual_vol_annual * 100.0,
            "paper_rmse": self.paper_rmse,
            "appraisal_ratio": self.appraisal_ratio,
        }


def spanning_regression(
    managed: pd.Series,
    base: pd.Series,
    *,
    frequency: Frequency = Frequency.MONTHLY,
    cov_type: str = "nonrobust",
) -> SpanningResult:
    r"""Rend la régression du facteur géré sur le facteur d'origine.

    **La formule, équation (3) de l'article.**

    .. math::

        f^{\sigma}_{t+1} = \alpha + \beta f_{t+1} + \epsilon_{t+1}

    **Ce que l'alpha veut dire.** Il est positif si et seulement si l'ensemble
    des deux titres, géré et non géré, étend la frontière moyenne-variance. Le
    poids qui réalise ce gain se calcule sur tout l'échantillon, ce qui est le
    point que Cederburg et ses coauteurs opposent à cette lecture.

    **Le ratio d'appréciation.** Il vaut :math:`\alpha / \sigma_\epsilon`, les
    deux grandeurs étant annualisées de la même façon, et il est insensible à
    toute mise à l'échelle constante du facteur géré.

    Args:
        managed: le facteur géré, mensuel.
        base: le facteur d'origine, mensuel.
        frequency: la fréquence des deux séries.
        cov_type: ``« nonrobust »`` pour l'erreur type ordinaire de l'article,
            ``« HAC »`` pour la version robuste à l'autocorrélation.

    Returns:
        Le résultat complet de la régression.

    Raises:
        InsufficientDataError: si moins de trois mois sont communs.

    Example:
        Un facteur géré construit comme deux fois le facteur d'origine rend un
        bêta de deux, un alpha nul et un coefficient de détermination de un.
    """
    left, right = _as_series(managed, label="managed").align(_as_series(base, label="base"), join="inner")
    frame = pd.concat({"managed": left, "base": right}, axis=1).dropna()
    if len(frame) < 3:
        raise InsufficientDataError(f"{len(frame)} mois communs, trois au moins sont nécessaires.")
    result = factor_regression(
        frame["managed"],
        frame["base"],
        frequency=frequency,
        cov_type=cov_type,
        annualize_alpha=True,
    )
    periods = frequency.periods_per_year
    residual_vol = float(np.std(result.residuals, ddof=2)) * math.sqrt(periods)
    alpha = float(result.alpha)
    return SpanningResult(
        n_observations=len(frame),
        beta=float(result.betas.iloc[0]),
        alpha_annual=alpha,
        alpha_stderr_annual=float(result.alpha_stderr),
        alpha_tstat=float(result.alpha_tstat),
        r_squared=float(result.r_squared),
        residual_vol_annual=residual_vol,
        paper_rmse=residual_vol * 100.0 * PAPER_RMSE_SCALE,
        appraisal_ratio=alpha / residual_vol if residual_vol > 0.0 else float("nan"),
    )


def appraisal_ratio(alpha_annual: float, residual_vol_annual: float) -> float:
    """Rend le ratio d'appréciation, alpha divisé par volatilité résiduelle.

    Args:
        alpha_annual: l'ordonnée à l'origine annualisée.
        residual_vol_annual: l'écart type résiduel annualisé.

    Returns:
        Le rapport des deux, ou ``nan`` si le dénominateur est nul.
    """
    if residual_vol_annual <= 0.0:
        return float("nan")
    return alpha_annual / residual_vol_annual


def combined_sharpe(base_sharpe: float, appraisal: float) -> float:
    r"""Rend le ratio de Sharpe atteignable en combinant les deux titres.

    .. math::

        SR_{new} = \sqrt{SR_{old}^2 + \left( \alpha / \sigma_\epsilon \right)^2}

    Args:
        base_sharpe: le ratio de Sharpe du facteur d'origine.
        appraisal: le ratio d'appréciation du facteur géré.

    Returns:
        Le ratio de Sharpe de la combinaison à poids optimaux.
    """
    return math.sqrt(base_sharpe**2 + appraisal**2)


def utility_gain(base_sharpe: float, appraisal: float) -> float:
    r"""Rend le gain d'utilité de l'équation (4) de l'article.

    .. math::

        \Delta U_{MV} = \frac{SR_{new}^2 - SR_{old}^2}{SR_{old}^2}

    Args:
        base_sharpe: le ratio de Sharpe du facteur d'origine.
        appraisal: le ratio d'appréciation du facteur géré.

    Returns:
        Le gain en fraction de l'utilité d'origine.

    Raises:
        ConfigError: si le ratio de Sharpe d'origine est nul.

    Example:
        Un Sharpe de 0,42 et un ratio d'appréciation de 0,33 rendent 0,617,
        soit 61,7 %, calcul fait à la main dans la fiche de littérature.
    """
    if base_sharpe == 0.0:
        raise ConfigError("un ratio de Sharpe d'origine nul rend le gain d'utilité indéfini.")
    return (combined_sharpe(base_sharpe, appraisal) ** 2 - base_sharpe**2) / base_sharpe**2


def hedged_spread(
    managed: pd.Series,
    base: pd.Series,
    *,
    min_periods: int,
) -> pd.Series:
    r"""Rend l'écart géré moins bêta fois l'original, le bêta estimé sur le passé.

    **Pourquoi cette série.** L'alpha d'engendrement est le rendement d'une
    combinaison des deux titres à poids optimaux ex post. Cette série en donne
    la version tenable : le bêta employé au mois :math:`t` est estimé sur les
    mois antérieurs, et son ratio de Sharpe est le ratio d'appréciation qu'un
    investisseur aurait réellement obtenu.

    .. math::

        s_t = f^{\sigma}_t - \hat{\beta}_{t-1} f_t

    Args:
        managed: le facteur géré, mensuel.
        base: le facteur d'origine, mensuel.
        min_periods: le nombre de mois exigé avant le premier bêta.

    Returns:
        La série des écarts couverts, manquante tant que le minimum n'est pas
        atteint.

    Raises:
        ConfigError: si ``min_periods`` est inférieur à trois.
    """
    if min_periods < 3:
        raise ConfigError(f"min_periods doit valoir au moins 3, reçu {min_periods}.")
    left, right = _as_series(managed, label="managed").align(_as_series(base, label="base"), join="inner")
    frame = pd.concat({"managed": left, "base": right}, axis=1).dropna()
    covariance = frame["managed"].expanding(min_periods).cov(frame["base"])
    variance = frame["base"].expanding(min_periods).var(ddof=1)
    beta = (covariance / variance).shift(1)
    spread = (frame["managed"] - beta * frame["base"]).dropna()
    spread.name = "hedged_spread"
    return spread


def real_time_combination(
    base: pd.Series,
    managed: pd.Series,
    *,
    min_periods: int,
    risk_aversion: float,
) -> pd.DataFrame:
    r"""Rend la combinaison moyenne-variance reconstruite mois après mois.

    **Le test de Cederburg et coauteurs.** Un investisseur d'aversion
    :math:`\gamma` choisit ses poids par

    .. math::

        w_t = \frac{1}{\gamma}\, \hat{\Sigma}_{t-1}^{-1} \hat{\mu}_{t-1}

    où moyenne et covariance sont estimées sur les seuls mois antérieurs. La
    même règle est appliquée au facteur d'origine seul, et les deux rendements
    se comparent.

    **Les hypothèses.** Les deux titres sont des rendements en excès, donc le
    reste de la richesse dort au taux sans risque. Aucun plafond de levier
    n'est imposé, ce qui avantage la combinaison en cas d'estimation instable.

    **Les limites.** La matrice de covariance de deux séries très corrélées
    s'inverse mal, et les poids explosent. C'est un défaut de la règle, pas du
    code, et il fait partie de ce que le test mesure.

    Args:
        base: le facteur d'origine, mensuel.
        managed: le facteur géré, mensuel.
        min_periods: le nombre de mois exigé avant la première décision.
        risk_aversion: le coefficient d'aversion au risque.

    Returns:
        Un tableau à quatre colonnes : ``combination``, ``base_only``,
        ``weight_base`` et ``weight_managed``.

    Raises:
        ConfigError: si l'aversion n'est pas strictement positive.
        InsufficientDataError: si l'historique commun est trop court.
    """
    if risk_aversion <= 0.0:
        raise ConfigError(f"risk_aversion doit être strictement positif, reçu {risk_aversion}.")
    left, right = _as_series(base, label="base").align(_as_series(managed, label="managed"), join="inner")
    frame = pd.concat({"base": left, "managed": right}, axis=1).dropna()
    if len(frame) <= min_periods:
        raise InsufficientDataError(f"{len(frame)} mois communs, plus de {min_periods} sont nécessaires.")

    rows: list[dict[str, float]] = []
    dates: list[pd.Timestamp] = []
    values = frame.to_numpy(dtype=float)
    for position in range(min_periods, len(frame)):
        history = values[:position]
        mean = history.mean(axis=0)
        covariance = np.cov(history, rowvar=False, ddof=1)
        try:
            weights = np.linalg.solve(risk_aversion * covariance, mean)
        except np.linalg.LinAlgError:
            weights = np.array([mean[0] / (risk_aversion * covariance[0, 0]), 0.0])
        single = mean[0] / (risk_aversion * covariance[0, 0])
        realized = values[position]
        rows.append(
            {
                "combination": float(weights @ realized),
                "base_only": float(single * realized[0]),
                "weight_base": float(weights[0]),
                "weight_managed": float(weights[1]),
            }
        )
        dates.append(frame.index[position])
    return pd.DataFrame(rows, index=pd.DatetimeIndex(dates, name="date"))

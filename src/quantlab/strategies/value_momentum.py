r"""La valeur, le momentum, et le gain que leur corrélation négative rapporte.

**Le problème.** Asness, Moskowitz et Pedersen (2013) ne montrent pas que la
valeur rapporte, ni que le momentum rapporte. Ils montrent que les deux se
tiennent en sens opposés, et que le mélange bat largement chaque jambe. Le
résultat porte donc sur la DIVERSIFICATION, et il se chiffre autrement qu'un
rendement.

**Le remède.** Ce module sépare quatre objets. La construction d'une jambe à
partir de portefeuilles triés vit dans :func:`rank_weighted_factor` et
:func:`high_minus_low`. Le mélange vit dans :func:`blend_returns` et
:func:`risk_parity_weights`. Le diagnostic d'une paire vit dans
:func:`pair_diagnostics`. La théorie qui prédit le gain vit dans
:func:`two_asset_sharpe` et :func:`equal_risk_sharpe`, dont les valeurs se
confrontent aux mesures.

**La formule qui porte l'étude.** Pour deux jambes de ratios de Sharpe
:math:`S_1` et :math:`S_2`, mélangées à risque égal, le ratio de Sharpe du
mélange ne dépend que de ces deux nombres et de la corrélation :

.. math::

    S_{mix} = \frac{S_1 + S_2}{\sqrt{2 + 2\rho}}

Les volatilités disparaissent, ce qui rend le gain de diversification lisible
d'un coup d'œil. Le multiplicateur par rapport à deux jambes indépendantes vaut
:math:`1/\sqrt{1+\rho}`, et il vaut 1,54 pour une corrélation de -0,577.

**La règle de causalité.** Un mélange à parts égales n'estime rien et se tient
donc sans information future. Un mélange à risque égal estime deux écarts
types, et :func:`risk_parity_weights` les calcule sur une fenêtre en expansion
close à la fin du mois précédent. La version de plein échantillon existe aussi,
elle est nommée comme telle, et elle n'est pas tenable.

**Provenance.** Asness, C. S., Moskowitz, T. J. et Pedersen, L. H. (2013),
« Value and Momentum Everywhere », *The Journal of Finance* 68(3), 929-985.
L'équation (1) du module est celle de la page 938. La borne de la corrélation
mécanique vient du même article, page 950.

**Les limites.** Rien ici ne connaît les frais, qui vivent dans
:mod:`quantlab.execution.costs`. Rien ici ne construit un portefeuille à partir
de titres individuels : les entrées sont des portefeuilles déjà triés, ou des
facteurs déjà publiés.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from quantlab.analytics.ratios import sharpe_ratio
from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.logging import get_logger
from quantlab.core.types import Frequency

__all__ = [
    "MECHANICAL_CORRELATION_LAGGED_PRICE",
    "MECHANICAL_CORRELATION_PAPER",
    "PairDiagnostics",
    "align_pair",
    "blend_returns",
    "correlation_standard_error",
    "diversification_multiplier",
    "equal_risk_sharpe",
    "grid_average_over_size",
    "high_minus_low",
    "pair_diagnostics",
    "rank_weighted_factor",
    "rank_weights",
    "rebalanced_blend",
    "risk_parity_weights",
    "rolling_correlation",
    "sharpe_sensitivity_to_correlation",
    "stress_correlation",
    "two_asset_sharpe",
]

_LOG = get_logger(__name__)

#: La corrélation valeur contre momentum publiée pour les actions américaines,
#: écart haut moins bas, page 950 de l'article. RAPPORTÉ.
MECHANICAL_CORRELATION_PAPER: float = -0.53

#: La même corrélation une fois le prix du ratio comptable retardé d'un an, de
#: sorte que les deux signaux ne partagent plus aucune donnée de prix, page 950.
#: RAPPORTÉ. L'écart avec la valeur précédente borne la part de la corrélation
#: qui vient de la construction plutôt que d'un mécanisme économique.
MECHANICAL_CORRELATION_LAGGED_PRICE: float = -0.28

#: Le plancher d'écart type sous lequel une jambe est déclarée dégénérée. Un
#: écart type nul rendrait un poids infini, et la division ne lèverait pas.
VOLATILITY_FLOOR: float = 1e-12


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


def _as_frame(values: pd.DataFrame, *, label: str) -> pd.DataFrame:
    """Contrôle qu'une entrée est un tableau daté de portefeuilles triés."""
    if not isinstance(values, pd.DataFrame):
        raise ConfigError(f"{label} doit être un pandas.DataFrame, reçu {type(values).__name__}.")
    if not isinstance(values.index, pd.DatetimeIndex):
        raise ConfigError(f"{label} doit porter un DatetimeIndex.")
    if values.shape[1] < 2:
        raise InsufficientDataError(
            f"{label} porte {values.shape[1]} colonne, deux au moins sont nécessaires."
        )
    return values.astype(float)


def rank_weights(n_portfolios: int) -> np.ndarray:
    r"""Rend les poids de rang de l'équation (1) de l'article.

    **(1) Le problème.** Un écart haut moins bas ne retient que deux
    portefeuilles sur dix et jette l'information des huit autres. L'article
    veut un portefeuille qui emploie tout le classement.

    **(2) L'intuition.** Chaque portefeuille reçoit un poids proportionnel à
    son écart au rang moyen. Le mieux classé est le plus acheté, le moins bien
    classé le plus vendu, et celui du milieu ne pèse rien.

    **(3) La formule.**

    .. math::

        w_i = c \left( i - \frac{n+1}{2} \right), \qquad
        c = \left( \sum_{j : w_j > 0} \left( j - \frac{n+1}{2} \right) \right)^{-1}

    **(4) Les variables.** :math:`i` le rang du portefeuille, compté à partir
    de un dans l'ordre croissant du signal ; :math:`n` leur nombre ;
    :math:`c` la constante qui met le portefeuille à un dollar acheté et un
    dollar vendu.

    **(5) Les hypothèses.** Les portefeuilles sont ordonnés par le signal, du
    plus faible au plus fort, et l'ordre ne change pas dans le temps.

    **(6) La provenance.** Équation (1), page 938 de l'article.

    **(7) Les limites.** L'article classe des TITRES, ce qui donne des poids
    qui bougent chaque mois. Appliquée à des portefeuilles déjà triés, la
    formule donne des poids constants, donc un portefeuille plus grossier.

    **(8) Les solutions écartées.** L'écart haut moins bas, disponible dans
    :func:`high_minus_low`, et le tri en trois groupes égaux de l'article. Le
    premier jette de l'information, le second exige les titres individuels.

    **(9) La raison du choix.** Les deux constructions sont publiées côte à
    côte dans la table I de l'article, et ses corrélations diffèrent
    systématiquement d'environ 0,10 entre elles.

    **(10) Comment vérifier.** Pour dix portefeuilles, la somme des poids
    positifs vaut un et le poids du dixième vaut 0,36. Pour cinq, il vaut deux
    tiers. Les deux valeurs se calculent à la main.

    Args:
        n_portfolios: le nombre de portefeuilles triés, au moins deux.

    Returns:
        Les poids, de somme nulle, dont la partie positive somme à un.

    Raises:
        ConfigError: si le nombre de portefeuilles est inférieur à deux.

    Example:
        >>> float(rank_weights(5)[-1].round(6))
        0.666667
    """
    if n_portfolios < 2:
        raise ConfigError(f"n_portfolios doit valoir au moins 2, reçu {n_portfolios}.")
    ranks = np.arange(1, n_portfolios + 1, dtype=float)
    deviations = ranks - (n_portfolios + 1.0) / 2.0
    scale = float(deviations[deviations > 0.0].sum())
    return deviations / scale


def rank_weighted_factor(portfolios: pd.DataFrame) -> pd.Series:
    r"""Rend le facteur pondéré par le rang d'un jeu de portefeuilles triés.

    **Le problème.** Transformer dix déciles de momentum en une seule série de
    rendement long et court, sans jeter les huit déciles du milieu.

    **La formule.** Le rendement du mois vaut :math:`\sum_i w_i r_{i,t}`, où
    les poids sont ceux de :func:`rank_weights`. Ils sont constants, donc le
    facteur est une combinaison linéaire fixe des colonnes.

    **Comment vérifier.** Sur deux portefeuilles, les poids valent -1 et +1, et
    le facteur coïncide exactement avec :func:`high_minus_low`. Un test le
    vérifie.

    Args:
        portfolios: les rendements des portefeuilles, colonnes ordonnées du
            signal le plus faible au plus fort.

    Returns:
        La série du facteur, nommée « rank_weighted ».

    Raises:
        InsufficientDataError: si le tableau porte moins de deux colonnes.
    """
    frame = _as_frame(portfolios, label="portfolios")
    weights = rank_weights(frame.shape[1])
    factor = frame.mul(weights, axis=1).sum(axis=1, min_count=frame.shape[1])
    factor.name = "rank_weighted"
    return factor


def high_minus_low(portfolios: pd.DataFrame) -> pd.Series:
    """Rend l'écart entre le portefeuille le mieux classé et le moins bien classé.

    C'est la construction « P3-P1 » de la table I de l'article, transposée au
    nombre de groupes que porte le tableau reçu.

    Args:
        portfolios: les rendements des portefeuilles, colonnes ordonnées du
            signal le plus faible au plus fort.

    Returns:
        La série de l'écart, nommée « high_minus_low ».

    Raises:
        InsufficientDataError: si le tableau porte moins de deux colonnes.
    """
    frame = _as_frame(portfolios, label="portfolios")
    spread = frame.iloc[:, -1] - frame.iloc[:, 0]
    spread.name = "high_minus_low"
    return spread


def grid_average_over_size(grid: pd.DataFrame, *, n_size: int, n_signal: int) -> pd.DataFrame:
    """Moyenne un tableau croisé taille sur signal le long de la dimension taille.

    **Pourquoi.** Les vingt-cinq portefeuilles de Kenneth French croisent cinq
    quintiles de capitalisation et cinq quintiles du signal. Moyenner sur la
    taille rend cinq portefeuilles de signal pur. Ils sont à peu près neutres
    en taille, ce qui est la comparaison que l'étude cherche.

    **L'ordre des colonnes compte.** Les colonnes sont lues comme un tableau
    dont la taille varie le plus lentement, ce qui est l'ordre publié :
    ME1 BM1, ME1 BM2, jusqu'à ME5 BM5.

    Args:
        grid: les rendements des ``n_size * n_signal`` portefeuilles.
        n_size: le nombre de groupes de capitalisation.
        n_signal: le nombre de groupes du signal.

    Returns:
        Un tableau de ``n_signal`` colonnes, nommées « q1 » à « qN ».

    Raises:
        ConfigError: si le nombre de colonnes ne vaut pas le produit attendu.
    """
    frame = _as_frame(grid, label="grid")
    if frame.shape[1] != n_size * n_signal:
        raise ConfigError(
            f"le tableau porte {frame.shape[1]} colonnes, "
            f"{n_size} fois {n_signal} en exigent {n_size * n_signal}."
        )
    values = frame.to_numpy(dtype=float).reshape(len(frame), n_size, n_signal)
    averaged = np.nanmean(values, axis=1)
    return pd.DataFrame(
        averaged,
        index=frame.index,
        columns=[f"q{i + 1}" for i in range(n_signal)],
    )


def align_pair(value: pd.Series, momentum: pd.Series) -> pd.DataFrame:
    """Aligne deux jambes sur leurs seuls mois communs et complets.

    Args:
        value: la jambe de valeur.
        momentum: la jambe de momentum.

    Returns:
        Un tableau à deux colonnes, « value » et « momentum », sans trou.

    Raises:
        InsufficientDataError: si moins de deux mois sont communs.
    """
    left = _as_series(value, label="value")
    right = _as_series(momentum, label="momentum")
    frame = pd.concat({"value": left, "momentum": right}, axis=1, join="inner").dropna()
    if len(frame) < 2:
        raise InsufficientDataError(f"{len(frame)} mois communs, deux au moins sont nécessaires.")
    return frame


def blend_returns(
    value: pd.Series,
    momentum: pd.Series,
    *,
    value_weight: float | pd.Series = 0.5,
) -> pd.Series:
    r"""Rend le mélange de deux jambes, à poids fixe ou variable.

    **La formule.** L'équation (3) de l'article, généralisée au poids :

    .. math::

        r^{mix}_t = w_t\, r^{val}_t + (1 - w_t)\, r^{mom}_t

    **La causalité.** Un poids constant n'estime rien. Un poids en série est
    supposé DÉJÀ décalé par celui qui l'a construit, et
    :func:`risk_parity_weights` le fait.

    Args:
        value: la jambe de valeur.
        momentum: la jambe de momentum.
        value_weight: le poids de la jambe de valeur, un nombre ou une série.

    Returns:
        La série du mélange, nommée « blend ».

    Raises:
        InsufficientDataError: si moins de deux mois sont communs.
    """
    frame = align_pair(value, momentum)
    if isinstance(value_weight, pd.Series):
        weight = _as_series(value_weight, label="value_weight").reindex(frame.index)
    else:
        weight = pd.Series(float(value_weight), index=frame.index)
    blend = weight * frame["value"] + (1.0 - weight) * frame["momentum"]
    blend = blend.dropna()
    blend.name = "blend"
    return blend


def risk_parity_weights(
    value: pd.Series,
    momentum: pd.Series,
    *,
    min_periods: int | None = None,
) -> pd.Series:
    r"""Rend le poids de la jambe de valeur dans un mélange à risque égal.

    **Le problème.** Un mélange à parts égales de dollars n'égalise pas les
    risques quand une jambe est deux fois plus volatile que l'autre. Le mélange
    à risque égal corrige cela, et c'est lui dont le ratio de Sharpe suit la
    formule fermée de :func:`equal_risk_sharpe`.

    **La formule.**

    .. math::

        w_t = \frac{1 / \hat{\sigma}^{val}_{t}}
                   {1 / \hat{\sigma}^{val}_{t} + 1 / \hat{\sigma}^{mom}_{t}}
            = \frac{\hat{\sigma}^{mom}_{t}}{\hat{\sigma}^{val}_{t} + \hat{\sigma}^{mom}_{t}}

    **Les deux versions, et laquelle est tenable.** Sans ``min_periods``, les
    deux écarts types sont ceux de tout l'échantillon : le poids est un nombre
    unique, il emploie l'avenir, et il sert de repère théorique. Avec
    ``min_periods``, ils sont calculés sur les mois 1 à :math:`t-1` puis
    décalés d'un mois, donc connus à la fin du mois :math:`t-1`.

    **Comment vérifier.** Sur deux jambes d'écarts types 1 et 3, le poids de la
    première vaut 0,75. Un test le vérifie à la main.

    Args:
        value: la jambe de valeur.
        momentum: la jambe de momentum.
        min_periods: le nombre de mois exigé avant le premier poids. Sans
            valeur, le poids est celui de plein échantillon.

    Returns:
        La série du poids de la jambe de valeur, manquante tant que le minimum
        n'est pas atteint.

    Raises:
        ConfigError: si ``min_periods`` est inférieur à deux.
        DataQualityError: si un écart type de plein échantillon est nul.
    """
    frame = align_pair(value, momentum)
    if min_periods is None:
        sigma_value = float(frame["value"].std(ddof=1))
        sigma_momentum = float(frame["momentum"].std(ddof=1))
        total = sigma_value + sigma_momentum
        if sigma_value <= VOLATILITY_FLOOR or sigma_momentum <= VOLATILITY_FLOOR:
            raise DataQualityError("écart type nul : le mélange à risque égal n'existe pas.")
        weight = pd.Series(sigma_momentum / total, index=frame.index)
        weight.name = "value_weight"
        return weight
    if min_periods < 2:
        raise ConfigError(f"min_periods doit valoir au moins 2, reçu {min_periods}.")
    sigma_value = frame["value"].expanding(min_periods).std(ddof=1)
    sigma_momentum = frame["momentum"].expanding(min_periods).std(ddof=1)
    weight = (sigma_momentum / (sigma_value + sigma_momentum)).shift(1)
    weight.name = "value_weight"
    return weight


def rebalanced_blend(
    value: pd.Series,
    momentum: pd.Series,
    *,
    value_weight: float = 0.5,
    rebalance_months: int = 1,
) -> pd.DataFrame:
    r"""Rend le mélange rééquilibré tous les ``k`` mois, et ses poids détenus.

    **Le problème.** Un mélange à parts égales ne reste à parts égales que si
    on le rééquilibre. Entre deux rééquilibrages, la jambe qui monte prend du
    poids, et la rotation du mélange dépend donc de la fréquence choisie.

    **Le mécanisme.** Le poids dérive avec le rendement de chaque jambe, selon
    :math:`w_{t+1} = w_t (1 + r^{val}_t) / (1 + r^{mix}_t)`, puis il est remis
    à sa cible tous les ``k`` mois. Une jambe longue et courte peut porter un
    rendement de période inférieur à -1 dans un cas extrême, et la fonction
    lève alors plutôt que de produire un poids sans sens.

    **Comment vérifier.** À ``rebalance_months`` égal à un, le poids détenu est
    constant et le rendement coïncide avec :func:`blend_returns`. Un test le
    vérifie.

    Args:
        value: la jambe de valeur.
        momentum: la jambe de momentum.
        value_weight: la cible de poids de la jambe de valeur.
        rebalance_months: le nombre de mois entre deux rééquilibrages.

    Returns:
        Un tableau à trois colonnes : « value_weight » le poids détenu,
        « momentum_weight » son complément, et « blend » le rendement.

    Raises:
        ConfigError: si ``rebalance_months`` est inférieur à un, ou si le poids
            cible sort de l'intervalle unité.
        DataQualityError: si la valeur du mélange atteint zéro ou passe dessous.
    """
    if rebalance_months < 1:
        raise ConfigError(f"rebalance_months doit valoir au moins 1, reçu {rebalance_months}.")
    if not 0.0 <= value_weight <= 1.0:
        raise ConfigError(f"value_weight doit tenir dans [0, 1], reçu {value_weight}.")
    frame = align_pair(value, momentum)
    held_value = np.empty(len(frame), dtype=float)
    blend = np.empty(len(frame), dtype=float)
    current = value_weight
    val = frame["value"].to_numpy(dtype=float)
    mom = frame["momentum"].to_numpy(dtype=float)
    for i in range(len(frame)):
        if i % rebalance_months == 0:
            current = value_weight
        held_value[i] = current
        period = current * val[i] + (1.0 - current) * mom[i]
        blend[i] = period
        growth = 1.0 + period
        if growth <= 0.0:
            raise DataQualityError(
                f"la valeur du mélange atteint {growth} au mois {frame.index[i].date()} ; "
                "le poids dérivé n'est pas défini."
            )
        current = current * (1.0 + val[i]) / growth
    result = pd.DataFrame(
        {
            "value_weight": held_value,
            "momentum_weight": 1.0 - held_value,
            "blend": blend,
        },
        index=frame.index,
    )
    return result


def rolling_correlation(value: pd.Series, momentum: pd.Series, *, window: int) -> pd.Series:
    """Rend la corrélation des deux jambes sur une fenêtre glissante.

    Args:
        value: la jambe de valeur.
        momentum: la jambe de momentum.
        window: la longueur de la fenêtre, en mois.

    Returns:
        La série des corrélations, nommée « correlation », manquante tant que
        la fenêtre n'est pas pleine.

    Raises:
        ConfigError: si la fenêtre est inférieure à trois mois.
    """
    if window < 3:
        raise ConfigError(f"window doit valoir au moins 3, reçu {window}.")
    frame = align_pair(value, momentum)
    correlation = frame["value"].rolling(window).corr(frame["momentum"])
    correlation.name = "correlation"
    return correlation


def stress_correlation(
    value: pd.Series,
    momentum: pd.Series,
    conditioning: pd.Series,
    *,
    quantile: float,
) -> dict[str, float]:
    """Rend la corrélation des deux jambes dans les mois de tension et hors tension.

    **La définition de la tension.** Les mois dont le rendement de la série de
    conditionnement tombe sous son quantile ``quantile``. La série de
    conditionnement est habituellement le rendement du marché.

    **Le seuil est calculé sur tout l'échantillon**, donc ce diagnostic n'est
    pas une stratégie et ne se détient pas. Il répond à la question « la
    diversification tient-elle quand elle sert », et rien d'autre.

    Args:
        value: la jambe de valeur.
        momentum: la jambe de momentum.
        conditioning: la série qui définit la tension.
        quantile: le quantile de coupure, strictement entre zéro et un.

    Returns:
        Un dictionnaire portant le nombre de mois, la corrélation en tension,
        la corrélation hors tension, et le seuil retenu.

    Raises:
        ConfigError: si le quantile sort de l'intervalle ouvert unité.
        InsufficientDataError: si moins de trois mois tombent en tension.
    """
    if not 0.0 < quantile < 1.0:
        raise ConfigError(f"quantile doit tenir dans ]0, 1[, reçu {quantile}.")
    frame = align_pair(value, momentum)
    signal = _as_series(conditioning, label="conditioning").reindex(frame.index).dropna()
    frame = frame.loc[signal.index]
    threshold = float(signal.quantile(quantile))
    stressed = frame.loc[signal <= threshold]
    calm = frame.loc[signal > threshold]
    if len(stressed) < 3 or len(calm) < 3:
        raise InsufficientDataError(
            f"{len(stressed)} mois en tension et {len(calm)} hors tension, trois au moins sont nécessaires."
        )
    return {
        "threshold": threshold,
        "n_stress": float(len(stressed)),
        "n_calm": float(len(calm)),
        "correlation_stress": float(stressed["value"].corr(stressed["momentum"])),
        "correlation_calm": float(calm["value"].corr(calm["momentum"])),
    }


def correlation_standard_error(correlation: float, n_observations: int) -> float:
    r"""Rend l'erreur type asymptotique d'un coefficient de corrélation.

    **La formule.** :math:`\mathrm{SE}(\hat{\rho}) = (1 - \rho^2)/\sqrt{n}`,
    l'écart type asymptotique de l'estimateur de Pearson sous normalité.

    **À quoi elle sert ici.** Elle fixe la tolérance des contrôles de
    réplication, exprimée en écarts types plutôt qu'en points de corrélation
    choisis après coup.

    Args:
        correlation: la corrélation, dans l'intervalle fermé de -1 à 1.
        n_observations: le nombre d'observations, au moins deux.

    Returns:
        L'erreur type, un nombre positif ou nul.

    Raises:
        ConfigError: si la corrélation sort de son intervalle, ou si le nombre
            d'observations est inférieur à deux.

    Example:
        >>> round(correlation_standard_error(0.0, 100), 4)
        0.1
    """
    if not -1.0 <= correlation <= 1.0:
        raise ConfigError(f"correlation doit tenir dans [-1, 1], reçu {correlation}.")
    if n_observations < 2:
        raise ConfigError(f"n_observations doit valoir au moins 2, reçu {n_observations}.")
    return (1.0 - correlation**2) / math.sqrt(float(n_observations))


def two_asset_sharpe(
    sharpe_value: float,
    sharpe_momentum: float,
    *,
    volatility_value: float,
    volatility_momentum: float,
    correlation: float,
    value_weight: float,
) -> float:
    r"""Rend le ratio de Sharpe d'un mélange de deux jambes, en forme fermée.

    **(1) Le problème.** Mesurer le mélange puis mesurer ses jambes ne dit pas
    d'où vient le gain. Il faut la formule qui relie les deux, pour vérifier
    que les chiffres mesurés en découlent et pour lire la part que porte la
    corrélation.

    **(2) L'intuition.** Le numérateur est une moyenne pondérée des primes.
    Le dénominateur est la volatilité du mélange, et c'est le seul terme où la
    corrélation entre.

    **(3) La formule.**

    .. math::

        S_{mix} = \frac{w \sigma_1 S_1 + (1 - w) \sigma_2 S_2}
        {\sqrt{w^2 \sigma_1^2 + (1-w)^2 \sigma_2^2 + 2 w (1-w) \rho \sigma_1 \sigma_2}}

    **(4) Les variables.** :math:`S_1` et :math:`S_2` les ratios de Sharpe des
    deux jambes, :math:`\sigma_1` et :math:`\sigma_2` leurs volatilités,
    :math:`\rho` leur corrélation, :math:`w` le poids de la première.

    **(5) Les hypothèses.** Les deux jambes sont autofinancées, donc leur
    rendement est déjà excédentaire et le taux sans risque ne réapparaît pas.
    Les quatre moments sont ceux du même échantillon.

    **(6) La provenance.** L'algèbre moyenne-variance de Markowitz (1952),
    appliquée au cas à deux actifs. L'article s'en sert page 945 pour montrer
    qu'un poids positif sur un momentum non rentable améliore la frontière.

    **(7) Les limites.** La formule est exacte sur un échantillon donné, elle
    ne prédit rien. Elle suppose des moments constants, ce que la corrélation
    glissante contredit.

    **(8) Les solutions écartées.** Mesurer directement le mélange, ce que
    l'étude fait aussi. La forme fermée ajoute la décomposition, pas le
    chiffre.

    **(9) La raison du choix.** Elle permet de répondre à la question du
    laboratoire, combien de Sharpe une unité de corrélation négative rapporte,
    ce qu'aucune mesure directe ne donne.

    **(10) Comment vérifier.** Avec deux jambes de même volatilité et de même
    Sharpe, mélangées à parts égales, le résultat vaut
    :math:`S \sqrt{2/(1+\rho)}`. À :math:`\rho = 1` il vaut :math:`S`, et à
    :math:`\rho = -1` il diverge. Un test vérifie les deux bornes.

    Args:
        sharpe_value: le ratio de Sharpe de la première jambe, annualisé.
        sharpe_momentum: celui de la seconde, dans la même annualisation.
        volatility_value: la volatilité de la première jambe.
        volatility_momentum: celle de la seconde.
        correlation: la corrélation des deux jambes.
        value_weight: le poids de la première jambe.

    Returns:
        Le ratio de Sharpe du mélange, dans l'annualisation des entrées.

    Raises:
        ConfigError: si une volatilité est négative ou nulle, ou si la
            corrélation sort de son intervalle.
        DataQualityError: si la variance du mélange est nulle, ce qui arrive
            quand deux jambes parfaitement opposées se compensent exactement.
    """
    if volatility_value <= 0.0 or volatility_momentum <= 0.0:
        raise ConfigError("les deux volatilités doivent être strictement positives.")
    if not -1.0 <= correlation <= 1.0:
        raise ConfigError(f"correlation doit tenir dans [-1, 1], reçu {correlation}.")
    other = 1.0 - value_weight
    numerator = value_weight * volatility_value * sharpe_value + other * volatility_momentum * sharpe_momentum
    variance = (
        value_weight**2 * volatility_value**2
        + other**2 * volatility_momentum**2
        + 2.0 * value_weight * other * correlation * volatility_value * volatility_momentum
    )
    if variance <= VOLATILITY_FLOOR:
        raise DataQualityError("la variance du mélange est nulle : son ratio de Sharpe n'existe pas.")
    return numerator / math.sqrt(variance)


def equal_risk_sharpe(sharpe_value: float, sharpe_momentum: float, correlation: float) -> float:
    r"""Rend le ratio de Sharpe du mélange à risque égal, sans les volatilités.

    **Le résultat.** Quand les deux jambes portent le même risque, les
    volatilités se simplifient et il reste

    .. math::

        S_{mix} = \frac{S_1 + S_2}{\sqrt{2 + 2\rho}}

    **Pourquoi il compte.** Trois nombres suffisent à prédire le mélange, et
    l'écart entre cette prédiction et la mesure devient un contrôle de
    cohérence. La formule dit aussi que la corrélation agit seule sur le
    dénominateur, ce qui isole exactement le gain de diversification.

    **Comment vérifier.** À :math:`\rho = 0` le résultat vaut
    :math:`(S_1 + S_2)/\sqrt{2}`, soit la racine de la somme des carrés quand
    les deux Sharpe sont égaux. Un test le vérifie.

    Args:
        sharpe_value: le ratio de Sharpe de la première jambe.
        sharpe_momentum: celui de la seconde.
        correlation: leur corrélation, strictement supérieure à -1.

    Returns:
        Le ratio de Sharpe du mélange à risque égal.

    Raises:
        ConfigError: si la corrélation vaut -1 ou sort de son intervalle.

    Example:
        >>> round(equal_risk_sharpe(0.5, 0.5, 0.0), 6)
        0.707107
    """
    if not -1.0 < correlation <= 1.0:
        raise ConfigError(f"correlation doit tenir dans ]-1, 1], reçu {correlation}.")
    return (sharpe_value + sharpe_momentum) / math.sqrt(2.0 + 2.0 * correlation)


def diversification_multiplier(correlation: float) -> float:
    r"""Rend ce que la corrélation multiplie le ratio de Sharpe du mélange.

    **La formule.** Le rapport du mélange à risque égal à ce qu'il vaudrait si
    les deux jambes étaient indépendantes :

    .. math::

        m(\rho) = \frac{S_{mix}(\rho)}{S_{mix}(0)} = \frac{1}{\sqrt{1 + \rho}}

    **Ce qu'il dit.** Une corrélation de -0,577 multiplie le ratio de Sharpe
    par 1,54 par rapport à deux jambes indépendantes, et par 2,18 par rapport à
    deux jambes parfaitement corrélées.

    Args:
        correlation: la corrélation, strictement supérieure à -1.

    Returns:
        Le multiplicateur, supérieur à un quand la corrélation est négative.

    Raises:
        ConfigError: si la corrélation vaut -1 ou sort de son intervalle.

    Example:
        >>> round(diversification_multiplier(0.0), 6)
        1.0
    """
    if not -1.0 < correlation <= 1.0:
        raise ConfigError(f"correlation doit tenir dans ]-1, 1], reçu {correlation}.")
    return 1.0 / math.sqrt(1.0 + correlation)


def sharpe_sensitivity_to_correlation(
    sharpe_value: float, sharpe_momentum: float, correlation: float
) -> float:
    r"""Rend la dérivée du ratio de Sharpe du mélange par rapport à la corrélation.

    **La réponse à la question du laboratoire.** Combien de ratio de Sharpe une
    unité de corrélation négative rapporte-t-elle. En dérivant la formule du
    mélange à risque égal :

    .. math::

        \frac{\partial S_{mix}}{\partial \rho}
        = -\frac{S_1 + S_2}{(2 + 2\rho)^{3/2}}
        = -\frac{S_{mix}}{2(1 + \rho)}

    **Comment la lire.** La dérivée est négative, donc rendre la corrélation
    plus négative augmente le ratio de Sharpe. Sa valeur absolue croît quand la
    corrélation descend, si bien que le gain n'est pas linéaire : les derniers
    dixièmes rapportent bien plus que les premiers.

    **Comment vérifier.** La différence finie de :func:`equal_risk_sharpe`
    autour de la corrélation doit tendre vers cette dérivée. Un test le
    vérifie à 1e-6.

    Args:
        sharpe_value: le ratio de Sharpe de la première jambe.
        sharpe_momentum: celui de la seconde.
        correlation: leur corrélation, strictement supérieure à -1.

    Returns:
        La dérivée, négative quand la somme des deux Sharpe est positive.

    Raises:
        ConfigError: si la corrélation vaut -1 ou sort de son intervalle.
    """
    if not -1.0 < correlation <= 1.0:
        raise ConfigError(f"correlation doit tenir dans ]-1, 1], reçu {correlation}.")
    return -(sharpe_value + sharpe_momentum) / (2.0 + 2.0 * correlation) ** 1.5


@dataclass(frozen=True)
class PairDiagnostics:
    """Tout ce qu'une paire valeur contre momentum rend, en une ligne.

    Attributes:
        label: le nom du regroupement, par exemple « EVERYWHERE ».
        n_months: le nombre de mois communs aux deux jambes.
        start: la première date commune, au format ISO.
        end: la dernière date commune.
        correlation: la corrélation des deux jambes.
        correlation_stderr: son erreur type asymptotique.
        sharpe_value: le ratio de Sharpe annualisé de la jambe de valeur.
        sharpe_momentum: celui de la jambe de momentum.
        sharpe_equal_weight: celui du mélange à parts égales de dollars.
        sharpe_risk_parity: celui du mélange à risque égal, poids de plein
            échantillon.
        sharpe_risk_parity_formula: la prédiction de :func:`equal_risk_sharpe`.
        volatility_value: la volatilité annualisée de la jambe de valeur.
        volatility_momentum: celle de la jambe de momentum.
        gain_over_best_leg: le ratio de Sharpe du mélange à parts égales moins
            le meilleur des deux Sharpe de jambe.
        multiplier: le multiplicateur de :func:`diversification_multiplier`.
        sensitivity: la dérivée de :func:`sharpe_sensitivity_to_correlation`.
    """

    label: str
    n_months: int
    start: str
    end: str
    correlation: float
    correlation_stderr: float
    sharpe_value: float
    sharpe_momentum: float
    sharpe_equal_weight: float
    sharpe_risk_parity: float
    sharpe_risk_parity_formula: float
    volatility_value: float
    volatility_momentum: float
    gain_over_best_leg: float
    multiplier: float
    sensitivity: float


def pair_diagnostics(
    value: pd.Series,
    momentum: pd.Series,
    *,
    label: str,
    frequency: Frequency = Frequency.MONTHLY,
    value_weight: float = 0.5,
) -> PairDiagnostics:
    """Rend le diagnostic complet d'une paire valeur contre momentum.

    **Ce que la fonction ne fait pas.** Elle ne calcule aucune métrique
    elle-même : le ratio de Sharpe vient de :mod:`quantlab.analytics.ratios`,
    et la volatilité s'en déduit par la définition du ratio. La règle 12 du
    ``CLAUDE.md`` interdit la seconde implémentation.

    **La volatilité annualisée** est celle de l'écart type d'échantillon
    multiplié par la racine du nombre de mois par an, la convention du
    sous-paquet des métriques.

    Args:
        value: la jambe de valeur.
        momentum: la jambe de momentum.
        label: le nom du regroupement, recopié tel quel dans le résultat.
        frequency: la fréquence des deux séries.
        value_weight: le poids de la jambe de valeur dans le mélange à parts
            fixes.

    Returns:
        Le diagnostic, gelé.

    Raises:
        InsufficientDataError: si moins de deux mois sont communs.
    """
    frame = align_pair(value, momentum)
    periods = 12.0 if frequency is Frequency.MONTHLY else 252.0
    scale = math.sqrt(periods)
    vol_value = float(frame["value"].std(ddof=1)) * scale
    vol_momentum = float(frame["momentum"].std(ddof=1)) * scale
    correlation = float(frame["value"].corr(frame["momentum"]))
    sharpe_v = sharpe_ratio(frame["value"], frequency=frequency)
    sharpe_m = sharpe_ratio(frame["momentum"], frequency=frequency)
    equal_weight = blend_returns(frame["value"], frame["momentum"], value_weight=value_weight)
    parity_weight = risk_parity_weights(frame["value"], frame["momentum"])
    parity = blend_returns(frame["value"], frame["momentum"], value_weight=parity_weight)
    sharpe_ew = sharpe_ratio(equal_weight, frequency=frequency)
    sharpe_rp = sharpe_ratio(parity, frequency=frequency)
    return PairDiagnostics(
        label=label,
        n_months=len(frame),
        start=str(frame.index[0].date()),
        end=str(frame.index[-1].date()),
        correlation=correlation,
        correlation_stderr=correlation_standard_error(correlation, len(frame)),
        sharpe_value=sharpe_v,
        sharpe_momentum=sharpe_m,
        sharpe_equal_weight=sharpe_ew,
        sharpe_risk_parity=sharpe_rp,
        sharpe_risk_parity_formula=equal_risk_sharpe(sharpe_v, sharpe_m, correlation),
        volatility_value=vol_value,
        volatility_momentum=vol_momentum,
        gain_over_best_leg=sharpe_ew - max(sharpe_v, sharpe_m),
        multiplier=diversification_multiplier(correlation),
        sensitivity=sharpe_sensitivity_to_correlation(sharpe_v, sharpe_m, correlation),
    )

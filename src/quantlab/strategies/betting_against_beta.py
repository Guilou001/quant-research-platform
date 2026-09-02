r"""Parier contre le bêta, et le levier qui rend le pari possible.

**Le problème.** Frazzini et Pedersen (2014) achètent les titres à bêta faible,
vendent ceux à bêta élevé, et mettent chaque jambe à l'échelle par l'inverse de
son bêta ex ante. Le portefeuille vise ainsi un bêta nul. Trois décisions de
construction décident du résultat, et aucune n'est celle d'un tri ordinaire :
l'estimateur de bêta, la pondération par les rangs, et la mise à l'échelle par
l'inverse du bêta.

**Le remède.** Ce module sépare ces trois décisions. L'estimateur vit dans
:func:`frazzini_pedersen_beta`, qui compose une corrélation longue et deux
volatilités courtes, puis rétrécit vers un. La pondération vit dans
:func:`leg_weights`, qui rend les rangs de l'article, l'équipondération, ou la
capitalisation. La mise à l'échelle vit dans :func:`bab_portfolio`. Changer de
pondération ne demande donc pas de retoucher l'estimateur.

**La règle de causalité.** Le rendement du mois :math:`t+1` n'emploie que des
grandeurs connues à la fin du mois :math:`t`. Le décalage se fait en un seul
endroit, dans :func:`bab_portfolio`, par l'argument ``execution_lag``. Les
rendements recouvrants de :func:`overlapping_log_returns` regardent en arrière
au cas de référence, alors que l'article les écrit tournés vers l'avant.

**Provenance.** Frazzini, A. et Pedersen, L. H. (2014), « Betting against
beta », *Journal of Financial Economics* 111(1), 1-25. La critique de la
construction vient de Novy-Marx, R. et Velikov, M. (2022), « Betting against
betting against beta », *Journal of Financial Economics* 143(1), 80-106.

**Les limites.** Rien ici ne connaît les frais, qui vivent dans
:mod:`quantlab.execution.costs`. Rien ici ne connaît le hors échantillon, qui
vit dans :mod:`quantlab.validation`. Ce module rend des séries, et le jugement
se prend ailleurs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.logging import get_logger

__all__ = [
    "DEFAULT_SHRINKAGE_TARGET",
    "DEFAULT_SHRINKAGE_WEIGHT",
    "Alignment",
    "BabResult",
    "BetaEstimate",
    "Weighting",
    "bab_portfolio",
    "beta_identity_terms",
    "financing_cost",
    "frazzini_pedersen_beta",
    "leg_weights",
    "market_capitalization",
    "overlapping_log_returns",
    "rolling_log_volatility",
    "shrink_beta",
]

_LOG = get_logger(__name__)

#: Le poids que l'article accorde à l'estimation temporelle du bêta, page 17.
#: Le complément va sur la valeur un. La note 14 le justifie par la moyenne
#: empirique du facteur de Vasicek, 0,61 sur les actions américaines.
DEFAULT_SHRINKAGE_WEIGHT: float = 0.6

#: La cible du rétrécissement, le bêta transversal moyen, qui vaut un par
#: construction puisque le marché est la somme pondérée de ses titres.
DEFAULT_SHRINKAGE_TARGET: float = 1.0

#: Le plancher sous lequel un bêta de jambe est jugé dégénéré. Diviser par un
#: bêta proche de zéro rendrait un levier immense sans lever d'exception.
BETA_FLOOR: float = 1e-3

#: Les deux alignements possibles de la fenêtre recouvrante.
Alignment = Literal["backward", "forward"]

#: Les trois pondérations comparées, celle de l'article et ses deux témoins.
Weighting = Literal["rank", "equal", "cap"]


# --------------------------------------------------------------------------- #
# Contrôles d'entrée
# --------------------------------------------------------------------------- #
def _as_frame(values: pd.DataFrame, *, label: str) -> pd.DataFrame:
    """Contrôle qu'une entrée est un tableau daté, trié et sans date double."""
    if not isinstance(values, pd.DataFrame):
        raise ConfigError(f"{label} doit être un pandas.DataFrame, reçu {type(values).__name__}.")
    if not isinstance(values.index, pd.DatetimeIndex):
        raise ConfigError(f"{label} doit porter un DatetimeIndex.")
    if not values.index.is_monotonic_increasing:
        raise DataQualityError(f"{label} n'est pas trié par date croissante.")
    if values.index.has_duplicates:
        raise DataQualityError(f"{label} porte des dates en double.")
    if values.shape[1] == 0:
        raise InsufficientDataError(f"{label} ne porte aucune colonne.")
    return values.astype(float)


def _as_series(values: pd.Series, *, label: str) -> pd.Series:
    """Contrôle qu'une entrée est une série datée, triée et sans date double."""
    if not isinstance(values, pd.Series):
        raise ConfigError(f"{label} doit être une pandas.Series, reçu {type(values).__name__}.")
    if not isinstance(values.index, pd.DatetimeIndex):
        raise ConfigError(f"{label} doit porter un DatetimeIndex.")
    if not values.index.is_monotonic_increasing:
        raise DataQualityError(f"{label} n'est pas trié par date croissante.")
    if values.index.has_duplicates:
        raise DataQualityError(f"{label} porte des dates en double.")
    return values.astype(float)


def _check_window(window: int, min_periods: int, *, name: str) -> None:
    """Refuse une fenêtre vide ou un minimum plus grand qu'elle."""
    if window < 2:
        raise ConfigError(f"{name} doit valoir au moins 2, reçu {window}.")
    if min_periods < 2:
        raise ConfigError(f"le minimum de {name} doit valoir au moins 2, reçu {min_periods}.")
    if min_periods > window:
        raise ConfigError(f"le minimum de {name} ({min_periods}) dépasse la fenêtre ({window}).")


# --------------------------------------------------------------------------- #
# Les rendements recouvrants
# --------------------------------------------------------------------------- #
def overlapping_log_returns(
    returns: pd.DataFrame | pd.Series,
    horizon: int = 3,
    *,
    alignment: Alignment = "backward",
) -> pd.DataFrame | pd.Series:
    r"""Rend les rendements logarithmiques cumulés sur une fenêtre recouvrante.

    **(1) Le problème.** Les petites capitalisations ne se négocient pas à la
    même seconde que l'indice. Leur rendement quotidien réagit donc avec un
    jour de retard, ce qui abaisse leur corrélation mesurée avec le marché et
    fausse leur bêta vers le bas. Le défaut porte un nom, la négociation non
    synchrone.

    **(2) L'intuition.** Additionner trois jours de rendement absorbe le
    décalage : si le titre réagit le lendemain, la somme contient quand même sa
    réaction. La corrélation mesurée sur ces sommes retrouve alors le lien vrai.

    **(3) La formule.** L'article écrit, équation (15),

    .. math::

        r^{3d}_{i,t} = \sum_{k=0}^{2} \ln\left(1 + r^{i}_{t+k}\right)

    Cette écriture tourne la fenêtre vers l'AVANT. L'alignement inverse somme
    de :math:`t-2` à :math:`t`, ce qui donne les mêmes fenêtres décalées de deux
    séances.

    **(4) Les variables.** :math:`r^{i}_{t}` le rendement simple du jour,
    :math:`\ln(1 + r)` son équivalent logarithmique, additif par construction.
    L'entier ``horizon`` fixe le nombre de jours additionnés.

    **(5) Les hypothèses.** Les rendements sont simples et supérieurs à moins
    un. Un rendement manquant rend manquante toute somme qui le contient.

    **(6) La provenance.** Frazzini et Pedersen (2014), page 17, qui reprennent
    la correction de Scholes et Williams (1977) et de Dimson (1979).

    **(7) Les limites.** La somme recouvrante crée une autocorrélation d'ordre
    deux dans la série produite. Elle ne sert donc qu'à estimer une corrélation,
    jamais à mesurer une performance.

    **(8) Les alternatives.** Le bêta de Dimson additionne les coefficients
    d'une régression sur les avances et les retards du marché. Il demande une
    régression multiple par titre, plus lourde et plus bruitée.

    **(9) La raison du choix.** L'article emploie la somme recouvrante, et
    l'objet de l'étude est de le répliquer.

    **(10) Comment vérifier.** Sur une série constante de rendement nul, la
    somme vaut zéro partout. Sur trois rendements de 1 %, la somme du troisième
    jour vaut trois fois le logarithme de 1,01.

    Args:
        returns: les rendements simples, quotidiens, en tableau ou en série.
        horizon: le nombre de jours additionnés, trois dans l'article.
        alignment: ``« backward »`` somme de :math:`t-h+1` à :math:`t`,
            ``« forward »`` somme de :math:`t` à :math:`t+h-1`.

    Returns:
        Les sommes de rendements logarithmiques, de même forme que l'entrée, et
        manquantes tant que la fenêtre n'est pas pleine.

    Raises:
        ConfigError: si ``horizon`` est inférieur à un, ou si l'alignement est
            inconnu.
        DataQualityError: si un rendement vaut moins un ou moins.

    Example:
        >>> import pandas as pd
        >>> idx = pd.date_range("2020-01-01", periods=4, freq="D")
        >>> r = pd.Series([0.0, 0.0, 0.0, 0.0], index=idx)
        >>> float(overlapping_log_returns(r, 3).iloc[-1])
        0.0
    """
    if horizon < 1:
        raise ConfigError(f"horizon doit valoir au moins 1, reçu {horizon}.")
    if alignment not in ("backward", "forward"):
        raise ConfigError(f"alignement « {alignment} » inconnu, choisir backward ou forward.")
    est_serie = isinstance(returns, pd.Series)
    frame = returns.to_frame(name=returns.name or "asset") if est_serie else returns
    frame = _as_frame(frame, label="returns")
    if bool((frame <= -1.0).any().any()):
        raise DataQualityError("un rendement vaut moins un ou moins, le logarithme n'existe pas.")
    logs = np.log1p(frame)
    if alignment == "backward":
        cumule = logs.rolling(horizon, min_periods=horizon).sum()
    else:
        inverse = logs.iloc[::-1]
        cumule = inverse.rolling(horizon, min_periods=horizon).sum().iloc[::-1]
    return cumule.iloc[:, 0].rename(returns.name) if est_serie else cumule


def rolling_log_volatility(
    returns: pd.DataFrame | pd.Series,
    window: int,
    min_periods: int,
) -> pd.DataFrame | pd.Series:
    r"""Rend l'écart type glissant des rendements logarithmiques.

    **Pourquoi le logarithme.** Le bêta de l'article est un rapport de
    volatilités multiplié par une corrélation, et les deux termes se mesurent
    sur des rendements logarithmiques. Mélanger une volatilité simple et une
    corrélation logarithmique fausserait le rapport.

    .. math::

        \hat{\sigma}_{i,t} = \operatorname{std}\left(
        \ln(1 + r^{i}_{s}) \;:\; s \in [t - w + 1, t] \right)

    Args:
        returns: les rendements simples, en tableau ou en série.
        window: la longueur de la fenêtre, en observations.
        min_periods: le nombre d'observations non manquantes exigé.

    Returns:
        L'écart type glissant, de même forme que l'entrée.

    Raises:
        ConfigError: si la fenêtre ou le minimum sont mal formés.
        DataQualityError: si un rendement vaut moins un ou moins.
    """
    _check_window(window, min_periods, name="volatility_window")
    est_serie = isinstance(returns, pd.Series)
    frame = returns.to_frame(name=returns.name or "asset") if est_serie else returns
    frame = _as_frame(frame, label="returns")
    if bool((frame <= -1.0).any().any()):
        raise DataQualityError("un rendement vaut moins un ou moins, le logarithme n'existe pas.")
    ecart = np.log1p(frame).rolling(window, min_periods=min_periods).std(ddof=1)
    return ecart.iloc[:, 0].rename(returns.name) if est_serie else ecart


def shrink_beta(
    beta_timeseries: pd.DataFrame | pd.Series,
    *,
    weight: float = DEFAULT_SHRINKAGE_WEIGHT,
    target: float = DEFAULT_SHRINKAGE_TARGET,
) -> pd.DataFrame | pd.Series:
    r"""Rétrécit un bêta estimé vers une cible transversale.

    **Le problème.** Un bêta estimé est bruité, et il sert ici de DIVISEUR. Une
    valeur trop basse sur la jambe longue produit un levier excessif, et
    l'erreur ne se compense pas entre les deux jambes.

    **La formule**, page 17 de l'article :

    .. math::

        \hat{\beta}_i = w\, \hat{\beta}^{TS}_i + (1 - w)\, \beta^{XS}

    Le poids vaut 0,6 sur l'estimation temporelle et 0,4 sur la valeur un. Le
    sens compte : l'inverse rétrécirait beaucoup plus fort.

    **Ce que le rétrécissement ne change pas.** Il est affine et croissant, donc
    il laisse le CLASSEMENT des titres intact. Il ne change donc pas la
    composition des deux jambes, seulement le levier appliqué à chacune.

    Args:
        beta_timeseries: le bêta estimé, avant rétrécissement.
        weight: le poids accordé à l'estimation, entre 0 et 1.
        target: la cible du rétrécissement, un dans l'article.

    Returns:
        Le bêta rétréci, de même forme que l'entrée.

    Raises:
        ConfigError: si le poids sort de l'intervalle unité.

    Example:
        >>> import pandas as pd
        >>> b = pd.Series([2.0], index=pd.DatetimeIndex(["2020-01-31"]))
        >>> float(shrink_beta(b).iloc[0])
        1.6
    """
    if not 0.0 <= weight <= 1.0:
        raise ConfigError(f"le poids du rétrécissement doit tenir entre 0 et 1, reçu {weight}.")
    return weight * beta_timeseries + (1.0 - weight) * target


@dataclass(frozen=True)
class BetaEstimate:
    """Le bêta ex ante de l'article, et les trois morceaux qui le composent.

    Garder les morceaux permet de vérifier l'identité de Novy-Marx et Velikov,
    qui montre que ce bêta mélange un bêta de régression et un rapport de
    volatilités.

    Attributes:
        beta: le bêta rétréci, celui qui entre dans les portefeuilles.
        beta_timeseries: le bêta avant rétrécissement.
        correlation: la corrélation longue entre rendements recouvrants.
        asset_volatility: la volatilité courte de chaque actif.
        market_volatility: la volatilité courte du marché.
        shrinkage_weight: le poids employé, reproduit pour la traçabilité.
    """

    beta: pd.DataFrame
    beta_timeseries: pd.DataFrame
    correlation: pd.DataFrame
    asset_volatility: pd.DataFrame
    market_volatility: pd.Series
    shrinkage_weight: float


def frazzini_pedersen_beta(
    asset_returns: pd.DataFrame,
    market_returns: pd.Series,
    *,
    volatility_window: int,
    volatility_min_periods: int,
    correlation_window: int,
    correlation_min_periods: int,
    overlap: int = 3,
    alignment: Alignment = "backward",
    shrinkage_weight: float = DEFAULT_SHRINKAGE_WEIGHT,
    shrinkage_target: float = DEFAULT_SHRINKAGE_TARGET,
) -> BetaEstimate:
    r"""Rend le bêta ex ante de Frazzini et Pedersen, équation (16).

    **(1) Le problème.** Un bêta de régression sur cinq ans mesure une
    exposition moyenne sur cinq ans. Quand la volatilité d'un titre double en
    six mois, son bêta réel double aussi, et la régression longue ne le voit
    pas. Employer un bêta périmé pour fixer un levier produit une couverture
    fausse.

    **(2) L'intuition.** Séparer le bêta en deux morceaux qui ne bougent pas à
    la même vitesse. La corrélation est stable, donc elle se mesure sur cinq
    ans. Le rapport des volatilités bouge vite, donc il se mesure sur un an. Le
    bêta obtenu réagit vite sans hériter du bruit d'une régression courte.

    **(3) La formule.**

    .. math::

        \hat{\beta}^{TS}_{i,t} = \hat{\rho}_{i,t}\,
        \frac{\hat{\sigma}_{i,t}}{\hat{\sigma}_{m,t}},
        \qquad
        \hat{\beta}_{i,t} = w\, \hat{\beta}^{TS}_{i,t} + (1 - w)

    **(4) Les variables.** :math:`\hat{\sigma}` est un écart type glissant de
    rendements logarithmiques quotidiens sur un an, avec au moins 120 séances.
    :math:`\hat{\rho}` est une corrélation glissante sur cinq ans, mesurée sur
    des rendements recouvrants de trois jours, avec au moins 750 séances.

    **(5) Les hypothèses.** Le marché est le bon dénominateur, donc son bêta
    vaut un. La corrélation est plus stable que la volatilité, ce que l'article
    affirme sans le chiffrer.

    **(6) La provenance.** Frazzini et Pedersen (2014), page 17 et note 14.

    **(7) Les limites.** Novy-Marx et Velikov (2022) établissent l'identité

    .. math::

        \beta^{FP}_i = \frac{\sigma^{i}_{1} / \sigma^{i}_{5}}
        {\sigma^{m}_{1} / \sigma^{m}_{5}}\, \beta^{i}_{5}

    donc ce bêta mélange un bêta de régression et un rapport de volatilités.
    Une variable corrélée à la volatilité de marché le prédit mécaniquement.
    :func:`beta_identity_terms` rend les deux membres pour le vérifier.

    **(8) Les alternatives.** Le bêta de régression sur soixante mois, celui de
    Kenneth French, est plus simple et se compare directement.

    **(9) La raison du choix.** L'article emploie celui-ci, et le répliquer
    exige de le reproduire plutôt que de l'approcher.

    **(10) Comment vérifier.** Le bêta du marché contre lui-même vaut un avant
    rétrécissement, la corrélation valant un et les deux volatilités étant
    égales. Un test le vérifie à 1e-12.

    Args:
        asset_returns: les rendements simples des actifs, en colonnes.
        market_returns: les rendements simples du marché.
        volatility_window: la fenêtre des volatilités, en observations.
        volatility_min_periods: le minimum d'observations d'une volatilité.
        correlation_window: la fenêtre de la corrélation, en observations.
        correlation_min_periods: le minimum d'observations d'une corrélation.
        overlap: le nombre de périodes additionnées pour la corrélation.
        alignment: l'alignement de la fenêtre recouvrante.
        shrinkage_weight: le poids du rétrécissement.
        shrinkage_target: la cible du rétrécissement.

    Returns:
        Un :class:`BetaEstimate` dont ``beta`` porte le bêta rétréci.

    Raises:
        ConfigError: si une fenêtre est mal formée.
        InsufficientDataError: si les deux entrées ne partagent aucune date.
    """
    _check_window(volatility_window, volatility_min_periods, name="volatility_window")
    _check_window(correlation_window, correlation_min_periods, name="correlation_window")
    assets = _as_frame(asset_returns, label="asset_returns")
    market = _as_series(market_returns, label="market_returns")
    commun = assets.index.intersection(market.index)
    if commun.empty:
        raise InsufficientDataError("les actifs et le marché ne partagent aucune date.")
    assets = assets.loc[commun]
    market = market.loc[commun]

    vol_actifs = rolling_log_volatility(assets, volatility_window, volatility_min_periods)
    vol_marche = rolling_log_volatility(market, volatility_window, volatility_min_periods)

    cumul_actifs = overlapping_log_returns(assets, overlap, alignment=alignment)
    cumul_marche = overlapping_log_returns(market, overlap, alignment=alignment)
    correlation = cumul_actifs.rolling(correlation_window, min_periods=correlation_min_periods).corr(
        cumul_marche
    )

    beta_ts = correlation.mul(vol_actifs).div(vol_marche, axis=0)
    beta = shrink_beta(beta_ts, weight=shrinkage_weight, target=shrinkage_target)
    _LOG.info(
        "bêta ex ante estimé",
        extra={
            "n_assets": int(assets.shape[1]),
            "n_dates": len(commun),
            "n_finite": int(np.isfinite(beta.to_numpy()).sum()),
        },
    )
    return BetaEstimate(
        beta=beta,
        beta_timeseries=beta_ts,
        correlation=correlation,
        asset_volatility=vol_actifs,
        market_volatility=vol_marche,
        shrinkage_weight=float(shrinkage_weight),
    )


def beta_identity_terms(
    asset_returns: pd.DataFrame,
    market_returns: pd.Series,
    *,
    volatility_window: int,
    volatility_min_periods: int,
    correlation_window: int,
    correlation_min_periods: int,
    overlap: int = 3,
    alignment: Alignment = "backward",
) -> dict[str, pd.DataFrame]:
    r"""Rend les deux membres de l'identité de Novy-Marx et Velikov.

    **Ce que l'identité dit.** Le bêta de l'article se réécrit comme le bêta de
    régression à cinq ans, corrigé par un rapport de rapports de volatilités :

    .. math::

        \beta^{FP}_i = \frac{\sigma^{i}_{1} / \sigma^{i}_{5}}
        {\sigma^{m}_{1} / \sigma^{m}_{5}}\, \beta^{i}_{5}

    où :math:`\beta^{i}_{5} = \hat{\rho}\, \sigma^{i}_{5} / \sigma^{m}_{5}` est
    le bêta de régression estimé sur la même fenêtre longue et sur les mêmes
    rendements recouvrants.

    **Pourquoi la vérifier.** L'identité est une conséquence algébrique, donc
    les deux membres doivent coïncider à la précision machine. Un écart
    signalerait que notre estimateur n'est pas celui de l'article.

    Args:
        asset_returns: les rendements simples des actifs, en colonnes.
        market_returns: les rendements simples du marché.
        volatility_window: la fenêtre courte des volatilités.
        volatility_min_periods: son minimum d'observations.
        correlation_window: la fenêtre longue.
        correlation_min_periods: son minimum d'observations.
        overlap: le nombre de périodes additionnées.
        alignment: l'alignement de la fenêtre recouvrante.

    Returns:
        Un dictionnaire à quatre clés. ``beta_fp`` porte le membre de gauche,
        ``beta_identity`` le membre de droite, ``beta_regression_long`` le bêta
        de régression longue, et ``volatility_ratio`` le facteur correcteur.
    """
    estimate = frazzini_pedersen_beta(
        asset_returns,
        market_returns,
        volatility_window=volatility_window,
        volatility_min_periods=volatility_min_periods,
        correlation_window=correlation_window,
        correlation_min_periods=correlation_min_periods,
        overlap=overlap,
        alignment=alignment,
        shrinkage_weight=1.0,
    )
    assets = _as_frame(asset_returns, label="asset_returns")
    market = _as_series(market_returns, label="market_returns")
    commun = assets.index.intersection(market.index)
    cumul_actifs = overlapping_log_returns(assets.loc[commun], overlap, alignment=alignment)
    cumul_marche = overlapping_log_returns(market.loc[commun], overlap, alignment=alignment)
    long_actifs = cumul_actifs.rolling(correlation_window, min_periods=correlation_min_periods).std(ddof=1)
    long_marche = cumul_marche.rolling(correlation_window, min_periods=correlation_min_periods).std(ddof=1)
    beta_long = estimate.correlation.mul(long_actifs).div(long_marche, axis=0)
    ratio = (
        long_actifs.rdiv(long_marche, axis=0)
        .mul(estimate.asset_volatility)
        .div(estimate.market_volatility, axis=0)
    )
    return {
        "beta_fp": estimate.beta_timeseries,
        "beta_identity": beta_long * ratio,
        "beta_regression_long": beta_long,
        "volatility_ratio": ratio,
    }


# --------------------------------------------------------------------------- #
# Les poids des deux jambes
# --------------------------------------------------------------------------- #
def leg_weights(
    betas: pd.Series,
    *,
    method: Weighting = "rank",
    capitalization: pd.Series | None = None,
) -> tuple[pd.Series, pd.Series]:
    r"""Rend les poids de la jambe à bêta faible et de la jambe à bêta élevé.

    **(1) Le problème.** Un tri en deux moitiés ne dit pas comment répartir le
    poids à l'intérieur de chaque moitié. La réponse décide de tout, parce
    qu'elle décide de la part donnée aux petites capitalisations.

    **(2) L'intuition.** L'article classe les titres par bêta et donne un poids
    proportionnel à la distance au rang moyen. Le titre au bêta le plus bas
    reçoit donc le plus gros poids de la jambe longue. La capitalisation
    n'entre nulle part, ce que Novy-Marx et Velikov attaquent.

    **(3) La formule.** Soit :math:`z` le vecteur des rangs de bêta et
    :math:`\bar{z}` leur moyenne :

    .. math::

        w_H = k\,(z - \bar{z})^{+}, \qquad
        w_L = k\,(z - \bar{z})^{-}, \qquad
        k = \frac{2}{\mathbf{1}'_n \lvert z - \bar{z} \rvert}

    La constante :math:`k` donne :math:`\mathbf{1}'_n w_H = \mathbf{1}'_n w_L =
    1`, ce qui fournit un contrôle immédiat.

    **(4) Les variables.** :math:`z_i` est le rang du bêta du titre :math:`i`,
    les ex aequo recevant le rang moyen. Le signe plus garde les écarts
    positifs, le signe moins la valeur absolue des écarts négatifs.

    **(5) Les hypothèses.** Au moins deux titres portent un bêta fini, et les
    bêtas ne sont pas tous égaux. Les deux témoins coupent à la médiane, ce qui
    coïncide avec la coupure au rang moyen quand aucun bêta n'est ex aequo.

    **(6) La provenance.** Frazzini et Pedersen (2014), équation (17). Les deux
    témoins viennent de Novy-Marx et Velikov (2022), section 3.

    **(7) Les limites.** La pondération par la capitalisation exige une série de
    capitalisations, que le fournisseur ne donne pas toujours. Sans elle, la
    fonction lève plutôt que d'approcher.

    **(8) Les alternatives.** Le tri en déciles extrêmes, celui du tableau III
    de l'article, jette la moitié centrale de l'information.

    **(9) La raison du choix.** Les trois pondérations sont exposées côte à
    côte, parce que leur écart EST le résultat que la critique annonce.

    **(10) Comment vérifier.** Sur cinq bêtas distincts, les rangs valent 1 à 5,
    le rang moyen vaut 3, la somme des écarts absolus vaut 6, donc :math:`k`
    vaut un tiers. Les poids longs valent alors deux tiers et un tiers sur les
    deux plus bas, et rien sur les trois autres.

    Args:
        betas: les bêtas ex ante d'une date, indexés par titre.
        method: ``« rank »``, ``« equal »`` ou ``« cap »``.
        capitalization: les capitalisations, exigées par ``« cap »`` seulement.

    Returns:
        Le couple des poids, jambe à bêta faible d'abord. Les deux séries sont
        positives et somment à un.

    Raises:
        ConfigError: si la méthode est inconnue, ou si la capitalisation manque.
        InsufficientDataError: si moins de deux bêtas finis sont disponibles.
        DataQualityError: si tous les bêtas sont égaux, ou si une jambe reçoit
            une capitalisation totale nulle.

    Example:
        >>> import pandas as pd
        >>> b = pd.Series([0.5, 0.8, 1.0, 1.3, 1.7], index=list("abcde"))
        >>> bas, haut = leg_weights(b)
        >>> round(float(bas.iloc[0]), 3), round(float(bas.sum()), 12)
        (0.667, 1.0)
    """
    if method not in ("rank", "equal", "cap"):
        raise ConfigError(f"pondération « {method} » inconnue, choisir rank, equal ou cap.")
    propres = betas.dropna().astype(float)
    if propres.size < 2:
        raise InsufficientDataError(f"{propres.size} bêta fini, il en faut au moins 2.")
    if float(propres.max() - propres.min()) == 0.0:
        raise DataQualityError("tous les bêtas sont égaux, aucun classement n'est possible.")

    rangs = propres.rank(method="average")
    ecart = rangs - float(rangs.mean())
    if method == "rank":
        constante = 2.0 / float(ecart.abs().sum())
        haut = constante * ecart.clip(lower=0.0)
        bas = constante * (-ecart).clip(lower=0.0)
        return bas, haut

    est_bas = ecart < 0.0
    est_haut = ecart > 0.0
    if not bool(est_bas.any()) or not bool(est_haut.any()):
        raise DataQualityError("la coupure au rang moyen laisse une jambe vide.")
    if method == "equal":
        base = pd.Series(1.0, index=propres.index)
    else:
        if capitalization is None:
            raise ConfigError("la pondération « cap » exige une série de capitalisations.")
        base = capitalization.reindex(propres.index).astype(float)
        if base.isna().any():
            raise DataQualityError("une capitalisation manque sur un titre classé.")
        if bool((base < 0.0).any()):
            raise DataQualityError("une capitalisation est négative.")
    poids_bas = base.where(est_bas, 0.0)
    poids_haut = base.where(est_haut, 0.0)
    if float(poids_bas.sum()) <= 0.0 or float(poids_haut.sum()) <= 0.0:
        raise DataQualityError("une jambe reçoit un poids total nul.")
    return poids_bas / float(poids_bas.sum()), poids_haut / float(poids_haut.sum())


def market_capitalization(firm_count: pd.DataFrame, average_size: pd.DataFrame) -> pd.DataFrame:
    """Rend la capitalisation totale d'un portefeuille, produit de deux séries.

    La bibliothèque de Kenneth French publie le nombre de sociétés d'un
    portefeuille et la taille moyenne de ses membres. Leur produit est la
    capitalisation du portefeuille, la seule mesure de taille disponible pour
    des portefeuilles agrégés.

    Args:
        firm_count: le nombre de sociétés, par date et par portefeuille.
        average_size: la taille moyenne, dans la même unité et la même forme.

    Returns:
        La capitalisation totale, alignée sur les dates et colonnes communes.

    Raises:
        InsufficientDataError: si les deux tableaux ne se recoupent pas.
    """
    gauche = _as_frame(firm_count, label="firm_count")
    droite = _as_frame(average_size, label="average_size")
    colonnes = gauche.columns.intersection(droite.columns)
    dates = gauche.index.intersection(droite.index)
    if colonnes.empty or dates.empty:
        raise InsufficientDataError("le nombre de sociétés et la taille moyenne ne se recoupent pas.")
    produit = gauche.loc[dates, colonnes] * droite.loc[dates, colonnes]
    return produit.where(produit > 0.0)


# --------------------------------------------------------------------------- #
# Le portefeuille
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class BabResult:
    """Le facteur reconstruit, ses deux jambes, et ce qu'il a fallu emprunter.

    Attributes:
        returns: le rendement du facteur, indexé par le mois de DÉTENTION.
        low_leg: le rendement excédentaire de la jambe à bêta faible, non
            amplifiée, indexé de même.
        high_leg: le rendement excédentaire de la jambe à bêta élevé.
        beta_low: le bêta ex ante de la jambe longue, connu à la formation.
        beta_high: le bêta ex ante de la jambe courte.
        leverage_low: l'inverse de ``beta_low``, le montant acheté par dollar.
        leverage_high: l'inverse de ``beta_high``, le montant vendu.
        positions: les positions nettes par titre, indexées par la date de
            FORMATION, prêtes pour un calcul de rotation.
        n_names: le nombre de titres classés à chaque formation.
        n_missing_returns: le nombre de cellules de rendement manquantes
            traitées comme nulles, mesuré et publié plutôt que caché.
    """

    returns: pd.Series
    low_leg: pd.Series
    high_leg: pd.Series
    beta_low: pd.Series
    beta_high: pd.Series
    leverage_low: pd.Series
    leverage_high: pd.Series
    positions: pd.DataFrame
    n_names: pd.Series
    n_missing_returns: int


def bab_portfolio(
    betas: pd.DataFrame,
    excess_returns: pd.DataFrame,
    *,
    weighting: Weighting = "rank",
    capitalization: pd.DataFrame | None = None,
    min_names: int = 10,
    execution_lag: int = 1,
) -> BabResult:
    r"""Construit le facteur pari contre le bêta, équation (18) de l'article.

    **(1) Le problème.** Un portefeuille long sur bêta faible et court sur bêta
    élevé n'est pas neutre au marché : sa jambe longue bouge moins que sa jambe
    courte, donc l'écart garde un bêta négatif. Le tri seul mesure donc un
    mélange de la prime cherchée et d'une exposition au marché.

    **(2) L'intuition.** Amplifier la jambe longue et réduire la jambe courte
    jusqu'à ce que les deux portent un bêta de un. La différence porte alors un
    bêta de zéro par construction, et ce qui reste est la prime.

    **(3) La formule.**

    .. math::

        r^{BAB}_{t+1} = \frac{1}{\beta^{L}_{t}}\left(r^{L}_{t+1} - r^{f}\right)
        - \frac{1}{\beta^{H}_{t}}\left(r^{H}_{t+1} - r^{f}\right)

    avec :math:`r^{L} = r' w_L`, :math:`r^{H} = r' w_H`,
    :math:`\beta^{L} = \beta' w_L` et :math:`\beta^{H} = \beta' w_H`.

    **(4) Les variables.** :math:`w_L` et :math:`w_H` viennent de
    :func:`leg_weights`. Les rendements entrants sont déjà excédentaires du
    taux sans risque, ce qui évite de le soustraire deux fois.

    **(5) Les hypothèses.** Le levier s'obtient au taux sans risque, hypothèse
    de l'article qui est aussi ce que la théorie conteste. Le coût réel se
    facture séparément par :func:`financing_cost`. Un rendement manquant sur un
    titre classé vaut zéro, faute de savoir ce qu'il aurait rendu.

    **(6) La provenance.** Frazzini et Pedersen (2014), équations (17) et (18),
    pages 18 et 19.

    **(7) Les limites.** Le bêta ex ante sert de diviseur, donc son bruit se
    transforme en levier. Les auteurs le reconnaissent page 18 et s'appuient sur
    les rendements réalisés plutôt que sur le bêta ex ante.

    **(8) Les alternatives.** Couvrir l'écart par le marché lui-même, ce que
    Novy-Marx et Velikov proposent, évite la division par un bêta bruité.

    **(9) La raison du choix.** C'est la construction de l'article, et l'étude
    la compare ensuite aux deux témoins.

    **(10) Comment vérifier.** Le bêta ex ante du facteur vaut exactement zéro,
    puisque :math:`\beta^{L} / \beta^{L} - \beta^{H} / \beta^{H} = 0`. Un test
    l'exige à 1e-12, et le bêta RÉALISÉ mesuré par régression le confirme
    approximativement.

    Args:
        betas: les bêtas ex ante, une ligne par date de formation.
        excess_returns: les rendements excédentaires, mêmes colonnes.
        weighting: la pondération passée à :func:`leg_weights`.
        capitalization: les capitalisations, exigées par ``« cap »``.
        min_names: le nombre minimal de titres classés pour former une date.
        execution_lag: le nombre de périodes entre formation et détention. Un
            au cas de référence, jamais zéro.

    Returns:
        Un :class:`BabResult`.

    Raises:
        ConfigError: si ``execution_lag`` est inférieur à un, ou si
            ``min_names`` est inférieur à deux.
        InsufficientDataError: si aucune date ne réunit assez de titres.
    """
    if execution_lag < 1:
        raise ConfigError(f"execution_lag doit valoir au moins 1, reçu {execution_lag}.")
    if min_names < 2:
        raise ConfigError(f"min_names doit valoir au moins 2, reçu {min_names}.")
    betas = _as_frame(betas, label="betas")
    rendements = _as_frame(excess_returns, label="excess_returns")
    colonnes = betas.columns.intersection(rendements.columns)
    if colonnes.empty:
        raise InsufficientDataError("les bêtas et les rendements ne partagent aucune colonne.")
    dates = betas.index.intersection(rendements.index)
    if len(dates) <= execution_lag:
        raise InsufficientDataError("l'échantillon commun est plus court que le décalage demandé.")
    betas = betas.loc[dates, colonnes]
    rendements = rendements.loc[dates, colonnes]

    lignes: list[dict[str, float]] = []
    index_detention: list[pd.Timestamp] = []
    index_formation: list[pd.Timestamp] = []
    positions: list[pd.Series] = []
    manquants = 0
    for position in range(len(dates) - execution_lag):
        formation = dates[position]
        detention = dates[position + execution_lag]
        ligne = betas.iloc[position].dropna()
        if ligne.size < min_names:
            continue
        caps = None if capitalization is None else capitalization.reindex(index=[formation]).iloc[0]
        try:
            poids_bas, poids_haut = leg_weights(ligne, method=weighting, capitalization=caps)
        except (DataQualityError, InsufficientDataError):
            continue
        beta_bas = float((ligne * poids_bas).sum())
        beta_haut = float((ligne * poids_haut).sum())
        if abs(beta_bas) < BETA_FLOOR or abs(beta_haut) < BETA_FLOOR:
            continue
        futurs = rendements.loc[detention, poids_bas.index]
        manquants += int(futurs.isna().sum())
        futurs = futurs.fillna(0.0)
        rendement_bas = float((futurs * poids_bas).sum())
        rendement_haut = float((futurs * poids_haut).sum())
        lignes.append(
            {
                "returns": rendement_bas / beta_bas - rendement_haut / beta_haut,
                "low_leg": rendement_bas,
                "high_leg": rendement_haut,
                "beta_low": beta_bas,
                "beta_high": beta_haut,
                "leverage_low": 1.0 / beta_bas,
                "leverage_high": 1.0 / beta_haut,
                "n_names": float(ligne.size),
            }
        )
        index_detention.append(detention)
        index_formation.append(formation)
        positions.append(poids_bas / beta_bas - poids_haut / beta_haut)

    if not lignes:
        raise InsufficientDataError("aucune date ne réunit assez de titres classés.")
    table = pd.DataFrame(lignes, index=pd.DatetimeIndex(index_detention, name="date"))
    cadre_positions = pd.DataFrame(positions, index=pd.DatetimeIndex(index_formation, name="date"))
    cadre_positions = cadre_positions.reindex(columns=colonnes).fillna(0.0)
    _LOG.info(
        "facteur reconstruit",
        extra={
            "weighting": weighting,
            "n_months": len(table),
            "n_missing_returns": manquants,
        },
    )
    return BabResult(
        returns=table["returns"].rename("bab"),
        low_leg=table["low_leg"].rename("low_leg"),
        high_leg=table["high_leg"].rename("high_leg"),
        beta_low=table["beta_low"],
        beta_high=table["beta_high"],
        leverage_low=table["leverage_low"],
        leverage_high=table["leverage_high"],
        positions=cadre_positions,
        n_names=table["n_names"].astype(int),
        n_missing_returns=manquants,
    )


def financing_cost(
    leverage_low: pd.Series,
    leverage_high: pd.Series,
    *,
    spread_bps_annual: float,
    periods_per_year: float = 12.0,
    basis: Literal["net", "gross"] = "net",
) -> pd.Series:
    r"""Rend le coût périodique du levier, au-dessus du taux sans risque.

    **Le problème.** L'article emprunte au taux sans risque, ce qui est
    exactement l'hypothèse que sa propre théorie conteste. Un investisseur
    contraint paie un écart, et cet écart mange le rendement d'autant plus que
    la jambe longue est amplifiée.

    **La formule.**

    .. math::

        c_t = \frac{s}{N} \times
        \begin{cases}
        1/\beta^{L}_t - 1/\beta^{H}_t & \text{en base nette} \\
        1/\beta^{L}_t & \text{en base brute}
        \end{cases}

    La base nette suppose que le produit de la vente à découvert finance une
    part de l'achat. La base brute suppose qu'il ne rapporte rien, ce qui
    majore le coût.

    Args:
        leverage_low: l'inverse du bêta de la jambe longue.
        leverage_high: l'inverse du bêta de la jambe courte.
        spread_bps_annual: l'écart de financement annuel, en points de base.
        periods_per_year: le nombre de périodes par an.
        basis: ``« net »`` ou ``« gross »``.

    Returns:
        Le coût par période, positif, aligné sur les deux entrées.

    Raises:
        ConfigError: si l'écart est négatif ou si la base est inconnue.
    """
    if spread_bps_annual < 0.0:
        raise ConfigError(f"l'écart de financement doit être positif, reçu {spread_bps_annual}.")
    if basis not in ("net", "gross"):
        raise ConfigError(f"base « {basis} » inconnue, choisir net ou gross.")
    if periods_per_year <= 0.0:
        raise ConfigError(f"periods_per_year doit être positif, reçu {periods_per_year}.")
    bas, haut = leverage_low.align(leverage_high, join="inner")
    montant = bas if basis == "gross" else bas - haut
    taux = spread_bps_annual / 10_000.0 / periods_per_year
    return (taux * montant.abs()).rename("financing_cost")

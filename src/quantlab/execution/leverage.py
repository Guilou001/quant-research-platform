r"""L'empilement : une exposition variable à un portefeuille, financée au taux court plus un écart.

**Le problème.** Un fonds à parité de risque, ou un fonds « à rendements
empilés », tient plus d'un dollar d'exposition par dollar de capital et règle
cette exposition sur la volatilité passée. Le laboratoire savait facturer la
rotation et l'emprunt de titres, pas le demi-dollar emprunté ni la décision
d'exposition elle-même. Sans cette brique, aucun rendement empilé n'est net.

**L'intuition.** Le levier ne crée pas de ratio de Sharpe ; il multiplie le
rendement excédentaire et la volatilité par le même facteur, puis retire ce
que coûte l'emprunt et chaque changement d'exposition. Tout ce qui compte est
donc dans deux nombres, l'écart de financement et le coût par unité négociée.

**La formule.** Les rendements sont en excédent du taux sans risque. Avec
:math:`e_{t-1}` l'exposition décidée avec l'information de la période
précédente, :math:`s` l'écart de financement annuel au-dessus du taux sans
risque, :math:`m` le nombre de périodes par an et :math:`c` le coût par unité
d'exposition négociée :

.. math::

    r^{emp}_t = e_{t-1}\, r_t \;-\; \max(e_{t-1} - 1, 0)\, \frac{s}{m}
    \;-\; c\, |e_{t-1} - e_{t-2}|.

Le premier terme est l'exposition, le deuxième le coût du capital emprunté, le
troisième la rotation de l'exposition. Sous un dollar, le capital non investi
rapporte le taux sans risque, donc zéro en excédent.

**L'exposition à cible de volatilité.** :math:`e_t = \min(\sigma^\star /
\hat\sigma_t, e_{\max})`, où :math:`\hat\sigma_t` est la volatilité
annualisée des :math:`w` dernières périodes. C'est la règle de Moreira et
Muir (2017) et des fonds de tendance, sans estimation autre qu'un écart type.

**Hypothèses.** L'écart de financement est constant et modélisé ; un compte
sur marge de particulier paie davantage. L'exposition se décide sur la
période précédente et s'applique à la suivante, jamais la même, règle 1.

**Provenance.** Hurst, Ooi et Pedersen (2017) pour la convention des
rendements excédentaires ; Moreira et Muir (2017) pour la cible de
volatilité ; spécification 007.

**Ce qui vérifie l'implémentation.** Une exposition constante à un et sans
coût rend le rendement d'origine. L'exemple à la main de la spécification
007 : exposition 1,5, rendement -1 %, écart 0,6 % par an, rend -1,525 %.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from quantlab.core.errors import ConfigError


@dataclass(frozen=True)
class LeveredReturns:
    """Le rendement empilé et ses deux coûts, période par période.

    Attributes:
        net: le rendement excédentaire net du financement et de la rotation.
        exposure: l'exposition réellement tenue pendant chaque période.
        financing_cost: le coût du capital emprunté, en fraction du capital.
        trading_cost: le coût des changements d'exposition, en fraction du capital.
    """

    net: pd.Series
    exposure: pd.Series
    financing_cost: pd.Series
    trading_cost: pd.Series


def volatility_target_exposure(
    returns: pd.Series,
    *,
    target_vol: float,
    window: int,
    periods_per_year: float,
    max_leverage: float,
    min_periods: int | None = None,
) -> pd.Series:
    """Rend l'exposition décidée à chaque période, cible sur volatilité passée, plafonnée.

    L'exposition rendue à la date t n'emploie que les rendements jusqu'à t
    inclus ; c'est :func:`apply_leverage` qui la décale d'une période.

    Args:
        returns: les rendements excédentaires du portefeuille, une période par ligne.
        target_vol: la volatilité annualisée visée, en fraction.
        window: le nombre de périodes de la fenêtre d'écart type.
        periods_per_year: le facteur d'annualisation, douze en mensuel.
        max_leverage: le plafond de l'exposition.
        min_periods: les périodes exigées avant la première décision, la fenêtre par défaut.

    Returns:
        L'exposition, absente tant que la fenêtre n'est pas pleine.
    """
    if target_vol <= 0 or window < 2 or periods_per_year <= 0 or max_leverage <= 0:
        raise ConfigError("cible, fenêtre, périodes par an et plafond doivent être positifs.")
    vol = returns.rolling(window, min_periods=min_periods or window).std(ddof=1) * np.sqrt(periods_per_year)
    exposition = (target_vol / vol).clip(upper=max_leverage)
    return exposition.rename("exposure")


def apply_leverage(
    returns: pd.Series,
    exposure: pd.Series,
    *,
    financing_spread_annual: float,
    periods_per_year: float,
    trade_cost_per_unit: float = 0.0,
    initial_exposure: float = 1.0,
) -> LeveredReturns:
    """Applique une exposition décidée la période précédente, financée au-delà d'un dollar.

    Args:
        returns: les rendements excédentaires du portefeuille.
        exposure: l'exposition décidée à chaque date, appliquée à la suivante.
        financing_spread_annual: l'écart annuel au-dessus du taux sans risque, en fraction.
        periods_per_year: le facteur d'annualisation, douze en mensuel.
        trade_cost_per_unit: le coût par unité d'exposition négociée, en fraction.
        initial_exposure: l'exposition tenue avant la première décision.

    Returns:
        Le rendement net et ses deux coûts, sur l'index des rendements.
    """
    if financing_spread_annual < 0 or trade_cost_per_unit < 0 or periods_per_year <= 0:
        raise ConfigError("écart, coût et périodes par an doivent être positifs ou nuls.")
    tenue = exposure.reindex(returns.index).shift(1).ffill().fillna(initial_exposure)
    precedente = tenue.shift(1).fillna(initial_exposure)
    financement = np.maximum(tenue - 1.0, 0.0) * financing_spread_annual / periods_per_year
    rotation = (tenue - precedente).abs() * trade_cost_per_unit
    net = tenue * returns - financement - rotation
    return LeveredReturns(
        net=net.rename("net"),
        exposure=tenue.rename("exposure"),
        financing_cost=pd.Series(financement, index=returns.index, name="financing_cost"),
        trading_cost=rotation.rename("trading_cost"),
    )

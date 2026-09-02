"""Phase 4. Le moteur de backtest du laboratoire, et ses garde-fous de datation.

Le sous-paquet porte la brique la plus dangereuse du dépôt. Une erreur d'une
seule période dans l'exécution invente du rendement à partir de rien, et ce
rendement inventé ressemble en tous points à un résultat de recherche.

Le contrat correspondant vit dans
:class:`quantlab.core.protocols.BacktestEngine`. Les moteurs externes, VectorBT
et LEAN, servent de contrôle et n'entrent pas ici.
"""

from __future__ import annotations

from quantlab.backtest.engine import (
    DEFAULT_EXECUTION_LAG,
    BacktestResult,
    apply_execution_lag,
    equity_curve,
    rebalance_dates,
    run_backtest,
    volatility_target,
)

__all__ = [
    "DEFAULT_EXECUTION_LAG",
    "BacktestResult",
    "apply_execution_lag",
    "equity_curve",
    "rebalance_dates",
    "run_backtest",
    "volatility_target",
]

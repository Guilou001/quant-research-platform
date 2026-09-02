"""Phase 6. Coûts, impact de marché, participation au volume, capacité.

Le premier module de ce sous-paquet est :mod:`quantlab.execution.costs`, qui
porte la décomposition du coût en six termes activables séparément. Sans lui,
aucun rendement net n'existe, et une étude ne peut pas franchir son parcours de
validation.

Les autres briques annoncées, la participation au volume et la capacité, ne sont
pas encore écrites. Leurs contrats vivent dans
:mod:`quantlab.core.protocols`, et c'est là qu'il faut lire avant d'ajouter quoi
que ce soit ici.
"""

from __future__ import annotations

from quantlab.execution.costs import (
    BaseCostModel,
    BorrowCostModel,
    CompositeCostModel,
    CostBreakdown,
    FinancingCostModel,
    LinearCostModel,
    SqrtImpactModel,
    breakeven_cost_bps,
    from_config,
)

__all__ = [
    "BaseCostModel",
    "BorrowCostModel",
    "CompositeCostModel",
    "CostBreakdown",
    "FinancingCostModel",
    "LinearCostModel",
    "SqrtImpactModel",
    "breakeven_cost_bps",
    "from_config",
]

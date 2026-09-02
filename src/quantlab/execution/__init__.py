"""Phase 6. Coûts, impact de marché, participation au volume, capacité.

Deux modules. :mod:`quantlab.execution.costs` porte la décomposition du coût en
six termes activables séparément ; sans lui, aucun rendement net n'existe.
:mod:`quantlab.execution.capacity` rejoue les mêmes poids à plusieurs tailles de
capital avec un impact en racine carrée de la participation, et rend le capital
où l'alpha net s'annule. Ce second module a une forme fermée qui contrôle le
moteur, et le contrôle est publié dans l'objet rendu.

Tout chiffre de capacité porte le statut MODÉLISÉ : le coefficient d'impact
n'est calibré sur aucune exécution réelle, et la capacité lui est
proportionnelle à la puissance moins deux.
"""

from __future__ import annotations

from quantlab.execution.capacity import (
    CapacityCurve,
    ImpactAtScale,
    average_daily_dollar_volume,
    breakeven_aum,
    capacity_curve,
    interpolate_crossing,
    realized_daily_volatility,
)
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
    signed_trades,
)

__all__ = [
    "BaseCostModel",
    "BorrowCostModel",
    "CapacityCurve",
    "CompositeCostModel",
    "CostBreakdown",
    "FinancingCostModel",
    "ImpactAtScale",
    "LinearCostModel",
    "SqrtImpactModel",
    "average_daily_dollar_volume",
    "breakeven_aum",
    "breakeven_cost_bps",
    "capacity_curve",
    "from_config",
    "interpolate_crossing",
    "realized_daily_volatility",
    "signed_trades",
]

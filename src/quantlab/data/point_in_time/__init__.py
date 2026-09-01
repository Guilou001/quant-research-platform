"""Le registre point-in-time : la période décrite d'un côté, la disponibilité de l'autre.

Ce sous-paquet porte la règle la plus stricte du laboratoire. Une information
n'est lisible qu'à partir de l'instant où elle était connaissable, et le code
refuse plutôt que d'arbitrer. Le détail du raisonnement, le schéma temporel et
les sources vivent dans :mod:`quantlab.data.point_in_time.frame`.
"""

from quantlab.data.point_in_time.frame import (
    AS_OF_COLUMN,
    AVAILABLE_FROM_COLUMN,
    DEFAULT_ENTITY_COLUMN,
    PERIOD_END_COLUMN,
    LookAheadReport,
    PITFrame,
    asof_join,
    assert_no_lookahead,
    lookahead_report,
)

__all__ = [
    "AS_OF_COLUMN",
    "AVAILABLE_FROM_COLUMN",
    "DEFAULT_ENTITY_COLUMN",
    "PERIOD_END_COLUMN",
    "LookAheadReport",
    "PITFrame",
    "asof_join",
    "assert_no_lookahead",
    "lookahead_report",
]

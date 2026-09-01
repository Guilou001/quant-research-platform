"""Les contrôles de qualité du lac : échouer bruyamment plutôt que laisser passer.

Le détail vit dans :mod:`quantlab.data.quality.checks`, qui documente pour
chaque contrôle ce qu'il attrape réellement et ce qu'il laisse passer.
"""

from quantlab.data.quality.checks import (
    CheckResult,
    QualityReport,
    Severity,
    check_column_schema,
    check_extreme_returns,
    check_missing_sessions,
    check_monotonic_index,
    check_no_duplicate_timestamps,
    check_ohlc_consistency,
    check_positive_prices,
    check_split_anomaly,
    check_stale_prices,
    check_timezone,
    run_checks,
)

__all__ = [
    "CheckResult",
    "QualityReport",
    "Severity",
    "check_column_schema",
    "check_extreme_returns",
    "check_missing_sessions",
    "check_monotonic_index",
    "check_no_duplicate_timestamps",
    "check_ohlc_consistency",
    "check_positive_prices",
    "check_split_anomaly",
    "check_stale_prices",
    "check_timezone",
    "run_checks",
]

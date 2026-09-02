"""Le rapport d'étude : ses quinze sections, ses tableaux, et son verdict.

Le sous-paquet écrit ce qu'une étude a produit, et il en déduit le verdict au
lieu de le laisser choisir. Les seuils vivent dans
:class:`~quantlab.reporting.study.VerdictCriteria`, et la déduction vit dans
:func:`~quantlab.reporting.study.decide_verdict`.

Un ratio de Sharpe supérieur à 1 ne suffit à aucun niveau de l'échelle des
verdicts. Le raisonnement complet vit dans la documentation du module
:mod:`quantlab.reporting.study`.
"""

from __future__ import annotations

from quantlab.reporting.study import (
    REPORT_SECTIONS,
    VERDICT_LADDER,
    MetricLabel,
    ReplicationCheck,
    ReportFigure,
    ReportTable,
    StudyReport,
    VerdictCriteria,
    VerdictEvidence,
    decide_verdict,
    generate_report,
    metrics_table,
    replication_table,
    section_keys,
)

__all__ = [
    "REPORT_SECTIONS",
    "VERDICT_LADDER",
    "MetricLabel",
    "ReplicationCheck",
    "ReportFigure",
    "ReportTable",
    "StudyReport",
    "VerdictCriteria",
    "VerdictEvidence",
    "decide_verdict",
    "generate_report",
    "metrics_table",
    "replication_table",
    "section_keys",
]

"""Le point d'entrée de l'étude 003, valeur et momentum, partout.

Ce fichier orchestre et n'implémente rien de réutilisable. La stratégie vit dans
:mod:`quantlab.strategies.value_momentum`, les métriques dans
:mod:`quantlab.analytics`, les contrôles dans :mod:`quantlab.validation`.

Lancement :

.. code-block:: bash

    export QUANTLAB_USER_AGENT="votre nom votre courriel"
    uv run python studies/003_value_and_momentum/run.py
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from quantlab.analytics.drawdown import max_drawdown
from quantlab.analytics.ratios import sharpe_ratio, sharpe_tstat
from quantlab.analytics.risk import kurtosis, skewness, volatility
from quantlab.analytics.turnover import annualized_turnover, turnover_series
from quantlab.analytics.visualization import figures as viz
from quantlab.core.config import ExperimentConfig, load_config
from quantlab.core.determinism import child_generators
from quantlab.core.errors import ConfigError
from quantlab.core.logging import get_logger, stage
from quantlab.core.types import AssetClass, CostBasis, Frequency, SampleTag
from quantlab.data.providers.aqr import AqrProvider
from quantlab.data.providers.french import FrenchProvider
from quantlab.execution.costs import breakeven_cost_bps
from quantlab.experiments import ExperimentRegistry
from quantlab.reporting.study import (
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
)
from quantlab.strategies.base import AlphaMetadata, AlphaRegistry
from quantlab.strategies.value_momentum import (
    MECHANICAL_CORRELATION_LAGGED_PRICE,
    MECHANICAL_CORRELATION_PAPER,
    align_pair,
    blend_returns,
    correlation_standard_error,
    equal_risk_sharpe,
    grid_average_over_size,
    high_minus_low,
    pair_diagnostics,
    rank_weighted_factor,
    rebalanced_blend,
    risk_parity_weights,
    rolling_correlation,
    stress_correlation,
    two_asset_sharpe,
)
from quantlab.validation.bootstrap import bootstrap_statistic
from quantlab.validation.cpcv import CombinatorialPurgedCV, cpcv_performance_distribution
from quantlab.validation.dsr import deflated_sharpe_ratio, expected_maximum_sharpe
from quantlab.validation.multiple_testing import (
    TrialCounter,
    adjust_pvalues,
    haircut_sharpe,
    required_tstat,
)
from quantlab.validation.pbo import probability_of_backtest_overfitting
from quantlab.validation.robustness import cost_multiplier_analysis, subperiod_performance

LOG = get_logger("quantlab.studies.003")
STUDY_DIR = Path(__file__).resolve().parent
RESULTS = STUDY_DIR / "results"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"

MONTHLY = Frequency.MONTHLY

#: Les onze paires de la feuille « VME Factors » d'AQR, dans l'ordre du
#: document. La clé est celle de la configuration, les deux valeurs sont les
#: colonnes de valeur et de momentum.
AQR_PAIRS: Mapping[str, tuple[str, str]] = {
    "EVERYWHERE": ("VAL", "MOM"),
    "ALL_EQUITIES": ("VAL^SS", "MOM^SS"),
    "ALL_OTHER": ("VAL^AA", "MOM^AA"),
    "US": ("VALLS_VME_US90", "MOMLS_VME_US90"),
    "UK": ("VALLS_VME_UK90", "MOMLS_VME_UK90"),
    "EU": ("VALLS_VME_ROE90", "MOMLS_VME_ROE90"),
    "JP": ("VALLS_VME_JP90", "MOMLS_VME_JP90"),
    "EQ": ("VALLS_VME_EQ", "MOMLS_VME_EQ"),
    "FX": ("VALLS_VME_FX", "MOMLS_VME_FX"),
    "FI": ("VALLS_VME_FI", "MOMLS_VME_FI"),
    "COM": ("VALLS_VME_COM", "MOMLS_VME_COM"),
}

#: Le nom lisible de chaque regroupement, employé dans les tableaux publiés.
PAIR_LABELS: Mapping[str, str] = {
    "EVERYWHERE": "Toutes classes d'actifs",
    "ALL_EQUITIES": "Actions, agrégat",
    "ALL_OTHER": "Hors actions, agrégat",
    "US": "Actions américaines",
    "UK": "Actions britanniques",
    "EU": "Actions européennes",
    "JP": "Actions japonaises",
    "EQ": "Indices actions par pays",
    "FX": "Devises",
    "FI": "Obligations d'État",
    "COM": "Matières premières",
    "FF_HML_UMD": "HML contre momentum de Carhart",
    "FF_RANK_5X5": "Rang sur quintiles, taille neutralisée",
    "FF_SPREAD_5X5": "Haut moins bas sur quintiles",
    "FF_HML_DECILES": "HML contre déciles 12-2",
}

#: La table I de l'article, colonne « facteur », version publiée consultée le
#: 2026-09-01. RAPPORTÉ. Chaque entrée porte la corrélation, le ratio de Sharpe
#: de la valeur, celui du momentum, celui du mélange à parts égales, puis la
#: corrélation de la construction haut moins bas.
PAPER_TABLE_1: Mapping[str, dict[str, float]] = {
    "EVERYWHERE": {"rho": -0.60, "sr_val": 0.72, "sr_mom": 0.74, "sr_mix": 1.59, "rho_hml": -0.53},
    "ALL_EQUITIES": {"rho": -0.60, "sr_val": 0.51, "sr_mom": 0.59, "sr_mix": 1.28, "rho_hml": -0.52},
    "ALL_OTHER": {"rho": -0.49, "sr_val": 0.55, "sr_mom": 0.62, "sr_mix": 1.14, "rho_hml": -0.40},
    "US": {"rho": -0.65, "sr_val": 0.26, "sr_mom": 0.45, "sr_mix": 0.86, "rho_hml": -0.53},
    "UK": {"rho": -0.62, "sr_val": 0.38, "sr_mom": 0.48, "sr_mix": 1.07, "rho_hml": -0.43},
    "EU": {"rho": -0.55, "sr_val": 0.54, "sr_mom": 0.75, "sr_mix": 1.20, "rho_hml": -0.52},
    "JP": {"rho": -0.64, "sr_val": 0.77, "sr_mom": 0.13, "sr_mix": 0.88, "rho_hml": -0.60},
    "EQ": {"rho": -0.37, "sr_val": 0.60, "sr_mom": 0.63, "sr_mix": 1.00, "rho_hml": -0.34},
    "FX": {"rho": -0.43, "sr_val": 0.44, "sr_mom": 0.32, "sr_mix": 0.69, "rho_hml": -0.42},
    "FI": {"rho": -0.35, "sr_val": 0.07, "sr_mom": 0.17, "sr_mix": 0.20, "rho_hml": -0.17},
    "COM": {"rho": -0.46, "sr_val": 0.31, "sr_mom": 0.51, "sr_mix": 0.77, "rho_hml": -0.39},
}

#: Le rendement moyen annualisé, l'écart type et la statistique t du facteur
#: combiné mondial, page 945 de l'article. RAPPORTÉ.
PAPER_COMBO_MEAN_PCT: float = 6.8
PAPER_COMBO_VOL_PCT: float = 4.3
PAPER_COMBO_TSTAT: float = 9.83


def _write_table(frame: pd.DataFrame, name: str) -> Path:
    """Écrit un tableau sous ``results/tables`` et rend son chemin."""
    TABLES.mkdir(parents=True, exist_ok=True)
    path = TABLES / f"{name}.csv"
    frame.to_csv(path, index=False)
    LOG.info("tableau écrit", extra={"name": name, "n_rows": len(frame)})
    return path


def _save_figure(fig: Any, name: str) -> Path:
    """Écrit une figure en PNG et en PDF, et rend le chemin du PNG."""
    FIGURES.mkdir(parents=True, exist_ok=True)
    written = viz.save_figure(fig, FIGURES / name, vector=True)
    return next(p for p in written if p.suffix == ".png")


def _aqr_pairs(vme: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Rend les onze paires d'AQR, chacune alignée sur ses mois communs."""
    return {
        key: align_pair(vme[value].dropna(), vme[momentum].dropna())
        for key, (value, momentum) in AQR_PAIRS.items()
    }


def _french_pairs(provider: FrenchProvider, params: Mapping[str, Any]) -> dict[str, pd.DataFrame]:
    """Rend les quatre paires bâties sur la bibliothèque de Kenneth French.

    Quatre constructions, de la plus publiée à la plus fine. Les deux facteurs
    de Kenneth French d'abord. Puis le facteur pondéré par le rang sur les
    quintiles de chaque tri, la taille étant moyennée. Puis l'écart haut moins
    bas sur ces mêmes quintiles. Enfin HML contre les dix déciles de momentum.
    """
    factors = provider.fetch(str(params["french_factors_dataset"]))
    momentum_factor = provider.fetch(str(params["french_momentum_dataset"]))
    value_grid = provider.fetch(
        str(params["french_value_grid_dataset"]), table="average_value_weighted_returns_monthly"
    )
    momentum_grid = provider.fetch(
        str(params["french_momentum_grid_dataset"]), table="average_value_weighted_returns_monthly"
    )
    deciles = provider.fetch(
        str(params["french_momentum_decile_dataset"]), table="value_weight_returns_monthly"
    )
    value_quintiles = grid_average_over_size(value_grid, n_size=5, n_signal=5)
    momentum_quintiles = grid_average_over_size(momentum_grid, n_size=5, n_signal=5)
    return {
        "FF_HML_UMD": align_pair(factors["HML"].dropna(), momentum_factor["MOM"].dropna()),
        "FF_RANK_5X5": align_pair(
            rank_weighted_factor(value_quintiles).dropna(),
            rank_weighted_factor(momentum_quintiles).dropna(),
        ),
        "FF_SPREAD_5X5": align_pair(
            high_minus_low(value_quintiles).dropna(), high_minus_low(momentum_quintiles).dropna()
        ),
        "FF_HML_DECILES": align_pair(factors["HML"].dropna(), rank_weighted_factor(deciles).dropna()),
    }


def _diagnostic_row(label_key: str, frame: pd.DataFrame, value_weight: float) -> dict[str, Any]:
    """Rend une ligne de tableau depuis le diagnostic d'une paire."""
    diag = pair_diagnostics(
        frame["value"],
        frame["momentum"],
        label=label_key,
        frequency=MONTHLY,
        value_weight=value_weight,
    )
    return {
        "key": diag.label,
        "pair": PAIR_LABELS[diag.label],
        "n_months": diag.n_months,
        "start": diag.start,
        "end": diag.end,
        "correlation": diag.correlation,
        "correlation_stderr": diag.correlation_stderr,
        "sharpe_value": diag.sharpe_value,
        "sharpe_momentum": diag.sharpe_momentum,
        "sharpe_equal_weight": diag.sharpe_equal_weight,
        "sharpe_risk_parity": diag.sharpe_risk_parity,
        "sharpe_risk_parity_formula": diag.sharpe_risk_parity_formula,
        "formula_gap": abs(diag.sharpe_risk_parity - diag.sharpe_risk_parity_formula),
        "volatility_value_pct": diag.volatility_value * 100.0,
        "volatility_momentum_pct": diag.volatility_momentum * 100.0,
        "gain_over_best_leg": diag.gain_over_best_leg,
        "diversification_multiplier": diag.multiplier,
        "sharpe_per_unit_correlation": diag.sensitivity,
    }


def main() -> None:
    """Mène l'étude de bout en bout et écrit tout ce qu'elle produit."""
    config = load_config(STUDY_DIR / "config.yaml", ExperimentConfig)
    params = config.params
    RESULTS.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)

    # Trois tirages indépendants, dérivés de la graine unique par
    # SeedSequence.spawn, jamais par « graine plus un ». Règle 14.
    generator_bootstrap, generator_reserve, generator_spare = child_generators(config.seed, 3)
    del generator_reserve, generator_spare

    paper_start = pd.Timestamp(params["paper_start"])
    paper_end = pd.Timestamp(params["paper_end"])
    headline = str(params["headline_pair"])
    base_weight = float(params["blend_value_weight"])
    weight_grid = [float(w) for w in params["blend_weight_grid"]]
    spread_bps = float(config.costs.spread_bps)

    n_positive_multipliers = len([m for m in params["cost_multipliers"] if float(m) > 0.0])
    expected_trials = (
        2 * len(AQR_PAIRS)
        + len(AQR_PAIRS)
        + 2 * 4
        + len(AQR_PAIRS) * len(weight_grid)
        + len(params["risk_parity_min_periods_grid"])
        + len(params["rebalance_months_grid"])
        + len(params["execution_lags"])
        + len(params["cost_bps_grid"])
        + n_positive_multipliers
        # Quatre évaluations publiées vivent hors des grilles, et la règle 8
        # les compte comme les autres. Les quatre mélanges de la jambe B sur la
        # fenêtre de l'article, les quinze mélanges à risque égal de cette même
        # fenêtre, les trois agrégats du panneau équilibré, et les deux
        # sous-fenêtres du hors échantillon.
        + 4
        + (len(AQR_PAIRS) + 4)
        + 3
        + 2
    )

    counter = TrialCounter()
    registry = ExperimentRegistry()
    manifests: list[dict[str, Any]] = []

    with registry.run(
        name="003_value_and_momentum",
        hypothesis=config.hypothesis,
        config=config.model_dump(mode="json"),
        seed=config.seed,
        universe=list(config.data.universe),
        date_start=config.data.start,
        date_end=config.data.end,
        cost_basis=CostBasis.NET,
        cost_assumptions={"spread_bps": spread_bps},
        n_trials=expected_trials,
    ) as run:
        # ------------------------------------------------------------------ #
        # 1. Les données
        # ------------------------------------------------------------------ #
        with stage("chargement", experiment_id=run.record.experiment_id):
            aqr = AqrProvider()
            french = FrenchProvider()
            vme = aqr.vme_factors()
            manifests.append(aqr.manifest("vme").model_dump(mode="json"))
            pairs_a = _aqr_pairs(vme)
            pairs_b = _french_pairs(french, params)
            for dataset in (
                params["french_factors_dataset"],
                params["french_momentum_dataset"],
                params["french_value_grid_dataset"],
                params["french_momentum_grid_dataset"],
                params["french_momentum_decile_dataset"],
            ):
                manifests.append(french.manifest(str(dataset)).model_dump(mode="json"))
            market = french.fetch(str(params["french_factors_dataset"]))["MKT-RF"].dropna()

            sources = pd.DataFrame(
                [
                    {
                        "source": "AQR",
                        "dataset": "Value-and-Momentum-Everywhere-Factors-Monthly",
                        "sheet_or_table": "VME Factors",
                        "start": str(vme.index[0].date()),
                        "end": str(vme.index[-1].date()),
                        "n_rows": len(vme),
                        "n_columns": vme.shape[1],
                    }
                ]
                + [
                    {
                        "source": "Kenneth French",
                        "dataset": str(dataset),
                        "sheet_or_table": table,
                        "start": str(frame.index[0].date()),
                        "end": str(frame.index[-1].date()),
                        "n_rows": len(frame),
                        "n_columns": frame.shape[1],
                    }
                    for dataset, table, frame in (
                        (
                            params["french_factors_dataset"],
                            "monthly",
                            french.fetch(str(params["french_factors_dataset"])),
                        ),
                        (
                            params["french_momentum_dataset"],
                            "monthly",
                            french.fetch(str(params["french_momentum_dataset"])),
                        ),
                        (
                            params["french_value_grid_dataset"],
                            "average_value_weighted_returns_monthly",
                            french.fetch(
                                str(params["french_value_grid_dataset"]),
                                table="average_value_weighted_returns_monthly",
                            ),
                        ),
                        (
                            params["french_momentum_grid_dataset"],
                            "average_value_weighted_returns_monthly",
                            french.fetch(
                                str(params["french_momentum_grid_dataset"]),
                                table="average_value_weighted_returns_monthly",
                            ),
                        ),
                        (
                            params["french_momentum_decile_dataset"],
                            "value_weight_returns_monthly",
                            french.fetch(
                                str(params["french_momentum_decile_dataset"]),
                                table="value_weight_returns_monthly",
                            ),
                        ),
                    )
                ]
            )
            _write_table(sources, "data_sources")

            coverage = pd.DataFrame(
                [
                    {
                        "key": key,
                        "pair": PAIR_LABELS[key],
                        "n_months": len(frame),
                        "start": str(frame.index[0].date()),
                        "end": str(frame.index[-1].date()),
                        "n_months_paper_window": len(
                            frame.loc[(frame.index >= paper_start) & (frame.index <= paper_end)]
                        ),
                    }
                    for key, frame in {**pairs_a, **pairs_b}.items()
                ]
            )
            _write_table(coverage, "pair_coverage")

        # ------------------------------------------------------------------ #
        # 2. La réplication de la table I, sur la fenêtre de l'article
        # ------------------------------------------------------------------ #
        with stage("replication", experiment_id=run.record.experiment_id):
            replication_rows: list[dict[str, Any]] = []
            for key, frame in pairs_a.items():
                window = frame.loc[(frame.index >= paper_start) & (frame.index <= paper_end)]
                row = _diagnostic_row(key, window, base_weight)
                published = PAPER_TABLE_1[key]
                row["published_correlation"] = published["rho"]
                row["published_correlation_high_minus_low"] = published["rho_hml"]
                row["published_sharpe_value"] = published["sr_val"]
                row["published_sharpe_momentum"] = published["sr_mom"]
                row["published_sharpe_blend"] = published["sr_mix"]
                row["correlation_gap"] = row["correlation"] - published["rho"]
                row["correlation_gap_in_sigmas"] = row["correlation_gap"] / correlation_standard_error(
                    published["rho"], row["n_months"]
                )
                replication_rows.append(row)
                counter = counter.record("replication_A", key, row["sharpe_equal_weight"])
            replication_frame = pd.DataFrame(replication_rows)
            _write_table(replication_frame, "replication_table1")

            headline_paper = pairs_a[headline].loc[
                (pairs_a[headline].index >= paper_start) & (pairs_a[headline].index <= paper_end)
            ]
            headline_paper_blend = blend_returns(
                headline_paper["value"], headline_paper["momentum"], value_weight=base_weight
            )
            combo_frame = pd.DataFrame(
                [
                    {
                        "quantity": "rendement moyen annualisé du mélange, %",
                        "published": PAPER_COMBO_MEAN_PCT,
                        "ours": float(headline_paper_blend.mean() * 12.0 * 100.0),
                    },
                    {
                        "quantity": "écart type annualisé du mélange, %",
                        "published": PAPER_COMBO_VOL_PCT,
                        "ours": float(volatility(headline_paper_blend, frequency=MONTHLY) * 100.0),
                    },
                    {
                        "quantity": "statistique t du mélange",
                        "published": PAPER_COMBO_TSTAT,
                        "ours": float(sharpe_tstat(headline_paper_blend, frequency=MONTHLY)),
                    },
                ]
            )
            combo_frame["gap_relative"] = (
                combo_frame["ours"] - combo_frame["published"]
            ).abs() / combo_frame["published"].abs()
            _write_table(combo_frame, "paper_combination")

            # Le panneau déséquilibré : la moyenne mondiale d'avant 1983 ne
            # porte pas les huit marchés, et l'article n'en dit rien.
            balanced_index = pd.concat(
                [pairs_a[key] for key in ("US", "UK", "EU", "JP", "EQ", "FX", "FI", "COM")],
                axis=1,
                join="inner",
            ).index
            balanced_rows: list[dict[str, Any]] = []
            for key in ("EVERYWHERE", "ALL_EQUITIES", "ALL_OTHER"):
                frame = pairs_a[key]
                for label, subset in (
                    ("panneau déséquilibré", frame.loc[frame.index <= paper_end]),
                    (
                        "panneau équilibré",
                        frame.loc[frame.index.isin(balanced_index) & (frame.index <= paper_end)],
                    ),
                ):
                    diag = _diagnostic_row(key, subset, base_weight)
                    if label == "panneau équilibré":
                        counter = counter.record("balanced_panel", key, diag["sharpe_equal_weight"])
                    balanced_rows.append(
                        {
                            "key": key,
                            "pair": PAIR_LABELS[key],
                            "panel": label,
                            "n_months": diag["n_months"],
                            "start": diag["start"],
                            "correlation": diag["correlation"],
                            "sharpe_value": diag["sharpe_value"],
                            "sharpe_momentum": diag["sharpe_momentum"],
                            "sharpe_equal_weight": diag["sharpe_equal_weight"],
                            "published_sharpe_blend": PAPER_TABLE_1[key]["sr_mix"],
                        }
                    )
            balanced_frame = pd.DataFrame(balanced_rows)
            _write_table(balanced_frame, "balanced_panel")

        # ------------------------------------------------------------------ #
        # 3. Le tableau principal, échantillon complet, jambes A et B
        # ------------------------------------------------------------------ #
        with stage("paires", experiment_id=run.record.experiment_id):
            full_rows: list[dict[str, Any]] = []
            for family, pairs in (("A", pairs_a), ("B", pairs_b)):
                for key, frame in pairs.items():
                    row = _diagnostic_row(key, frame, base_weight)
                    row["leg"] = family
                    full_rows.append(row)
                    counter = counter.record(f"pairs_{family}_ew", key, row["sharpe_equal_weight"])
                    counter = counter.record(f"pairs_{family}_rp", key, row["sharpe_risk_parity"])
            full_frame = pd.DataFrame(full_rows)
            _write_table(full_frame, "pairs_full_sample")

            # Le même tableau restreint à la fenêtre de l'article, pour que la
            # jambe B se compare à la jambe A sur les mêmes dates.
            common_rows: list[dict[str, Any]] = []
            for family, pairs in (("A", pairs_a), ("B", pairs_b)):
                for key, frame in pairs.items():
                    window = frame.loc[(frame.index >= paper_start) & (frame.index <= paper_end)]
                    row = _diagnostic_row(key, window, base_weight)
                    row["leg"] = family
                    common_rows.append(row)
                    # Les onze mélanges à parts égales de la jambe A sur cette
                    # fenêtre sont déjà comptés sous « replication_A ». Les
                    # quatre de la jambe B et les quinze à risque égal ne le
                    # sont pas, et ils sont publiés.
                    if family == "B":
                        counter = counter.record("paper_window_B_ew", key, row["sharpe_equal_weight"])
                    counter = counter.record("paper_window_rp", key, row["sharpe_risk_parity"])
            common_frame = pd.DataFrame(common_rows)
            _write_table(common_frame, "pairs_paper_window")

            # La borne mécanique de l'article, page 950. Le ratio comptable de
            # Kenneth French emploie une capitalisation de décembre de l'année
            # précédente, donc un prix déjà retardé de six à dix-huit mois.
            us_window = pairs_a["US"].loc[
                (pairs_a["US"].index >= paper_start) & (pairs_a["US"].index <= paper_end)
            ]
            ff_window = pairs_b["FF_HML_UMD"].loc[
                (pairs_b["FF_HML_UMD"].index >= paper_start) & (pairs_b["FF_HML_UMD"].index <= paper_end)
            ]
            mechanical_frame = pd.DataFrame(
                [
                    {
                        "construction": "AQR, valeur au prix courant, actions américaines",
                        "price_lag": "aucun",
                        "n_months": len(us_window),
                        "correlation": float(us_window["value"].corr(us_window["momentum"])),
                        "published_reference": MECHANICAL_CORRELATION_PAPER,
                    },
                    {
                        "construction": "Kenneth French, HML contre momentum de Carhart",
                        "price_lag": "capitalisation de décembre de l'année précédente",
                        "n_months": len(ff_window),
                        "correlation": float(ff_window["value"].corr(ff_window["momentum"])),
                        "published_reference": MECHANICAL_CORRELATION_LAGGED_PRICE,
                    },
                ]
            )
            _write_table(mechanical_frame, "mechanical_correlation")

        # ------------------------------------------------------------------ #
        # 4. La formule, et ce qu'une unité de corrélation rapporte
        # ------------------------------------------------------------------ #
        with stage("formule", experiment_id=run.record.experiment_id):
            formula_rows: list[dict[str, Any]] = []
            for row in full_rows:
                key = row["key"]
                frame = (pairs_a | pairs_b)[key]
                reconstructed = two_asset_sharpe(
                    row["sharpe_value"],
                    row["sharpe_momentum"],
                    volatility_value=row["volatility_value_pct"] / 100.0,
                    volatility_momentum=row["volatility_momentum_pct"] / 100.0,
                    correlation=row["correlation"],
                    value_weight=base_weight,
                )
                independent = equal_risk_sharpe(row["sharpe_value"], row["sharpe_momentum"], 0.0)
                formula_rows.append(
                    {
                        "key": key,
                        "pair": row["pair"],
                        "leg": row["leg"],
                        "n_months": row["n_months"],
                        "correlation": row["correlation"],
                        "sharpe_equal_weight_measured": row["sharpe_equal_weight"],
                        "sharpe_equal_weight_formula": reconstructed,
                        "sharpe_risk_parity_measured": row["sharpe_risk_parity"],
                        "sharpe_risk_parity_formula": row["sharpe_risk_parity_formula"],
                        "sharpe_if_independent": independent,
                        "diversification_multiplier": row["diversification_multiplier"],
                        "sharpe_per_unit_correlation": row["sharpe_per_unit_correlation"],
                        "sharpe_from_correlation": row["sharpe_risk_parity_formula"] - independent,
                        "max_absolute_gap": max(
                            abs(reconstructed - row["sharpe_equal_weight"]), row["formula_gap"]
                        ),
                    }
                )
                del frame
            formula_frame = pd.DataFrame(formula_rows)
            _write_table(formula_frame, "formula_check")

        # ------------------------------------------------------------------ #
        # 5. Le mélange de référence, ses coûts et son hors échantillon
        # ------------------------------------------------------------------ #
        with stage("couts", experiment_id=run.record.experiment_id):
            headline_frame = pairs_a[headline]
            headline_gross = blend_returns(
                headline_frame["value"], headline_frame["momentum"], value_weight=base_weight
            )
            weights_frame = pd.DataFrame(
                {"value": base_weight, "momentum": 1.0 - base_weight}, index=headline_frame.index
            )
            rotation = turnover_series(
                weights_frame,
                headline_frame.rename(columns={"value": "value", "momentum": "momentum"}),
                drifted=True,
                convention="full_sum",
            )
            annual_rotation = annualized_turnover(rotation, frequency=MONTHLY)
            aligned_rotation = rotation.reindex(headline_gross.index).fillna(0.0)

            def net_returns(rate_bps: float) -> pd.Series:
                """Rend le mélange net d'un taux de coût, en points de base."""
                return headline_gross - aligned_rotation * rate_bps / 10_000.0

            cost_rows: list[dict[str, Any]] = []
            for rate in params["cost_bps_grid"]:
                rate = float(rate)
                net = net_returns(rate)
                sharpe_net = sharpe_ratio(net, frequency=MONTHLY)
                cost_rows.append(
                    {
                        "cost_bps": rate,
                        "n_months": len(net),
                        "gross_annual_pct": float(headline_gross.mean() * 12.0 * 100.0),
                        "net_annual_pct": float(net.mean() * 12.0 * 100.0),
                        "annual_turnover": annual_rotation,
                        "net_sharpe": sharpe_net,
                    }
                )
                counter = counter.record("costs", f"rate{rate}", sharpe_net)
            breakeven = breakeven_cost_bps(
                headline_gross, aligned_rotation, frequency=MONTHLY, min_observations=12
            )
            cost_frame = pd.DataFrame(cost_rows)
            cost_frame["breakeven_cost_bps"] = breakeven
            # La rotation annuelle qui annulerait le rendement brut au taux de
            # la ligne. Elle borne ce que la rotation INTERNE des deux jambes,
            # non publiée, aurait le droit de valoir.
            cost_frame["turnover_that_cancels_gross"] = [
                float("inf")
                if row["cost_bps"] <= 0.0
                else row["gross_annual_pct"] / 100.0 / (row["cost_bps"] / 10_000.0)
                for row in cost_rows
            ]
            _write_table(cost_frame, "costs")

            headline_net = net_returns(spread_bps)
            holdout = headline_net.loc[headline_net.index > paper_end]

            # La colonne EVERYWHERE d'AQR survit à ses composantes hors
            # actions, qui s'arrêtent plus tôt. Les derniers mois du hors
            # échantillon ne portent donc que les quatre marchés d'actions, et
            # la composition change sans que rien ne le signale dans le fichier.
            last_non_equity = min(pairs_a[key].index[-1] for key in ("EQ", "FX", "FI", "COM", "ALL_OTHER"))
            composition_rows = [
                {
                    "window": "hors échantillon complet",
                    "start": str(holdout.index[0].date()),
                    "end": str(holdout.index[-1].date()),
                    "n_months": len(holdout),
                    "asset_classes_present": "huit puis quatre",
                    "sharpe_net": sharpe_ratio(holdout, frequency=MONTHLY),
                },
                {
                    "window": "hors échantillon, huit classes présentes",
                    "start": str(holdout.index[0].date()),
                    "end": str(last_non_equity.date()),
                    "n_months": len(holdout.loc[holdout.index <= last_non_equity]),
                    "asset_classes_present": "huit",
                    "sharpe_net": sharpe_ratio(
                        holdout.loc[holdout.index <= last_non_equity], frequency=MONTHLY
                    ),
                },
                {
                    "window": "hors échantillon, actions seules",
                    "start": str(holdout.loc[holdout.index > last_non_equity].index[0].date()),
                    "end": str(holdout.index[-1].date()),
                    "n_months": len(holdout.loc[holdout.index > last_non_equity]),
                    "asset_classes_present": "quatre, actions seules",
                    "sharpe_net": sharpe_ratio(
                        holdout.loc[holdout.index > last_non_equity], frequency=MONTHLY
                    ),
                },
            ]
            # Les deux sous-fenêtres sont des lectures concurrentes du même
            # hors échantillon, donc deux essais. La fenêtre entière est celle
            # que le verdict emploie et elle est comptée ailleurs.
            for row in composition_rows[1:]:
                counter = counter.record("holdout_window", str(row["window"]), row["sharpe_net"])
            composition_frame = pd.DataFrame(composition_rows)
            _write_table(composition_frame, "holdout_composition")

            def net_sharpe_at_multiple(multiplier: float) -> float:
                """Rend le ratio de Sharpe hors échantillon à un multiple de coût."""
                series = net_returns(spread_bps * multiplier)
                return sharpe_ratio(series.loc[series.index > paper_end], frequency=MONTHLY)

            # Le multiple nul est écarté : cost_multiplier_analysis exige des
            # multiples strictement positifs, le rendement brut étant déjà
            # publié par la ligne à zéro point de base du tableau des coûts.
            positive_multipliers = tuple(float(m) for m in params["cost_multipliers"] if float(m) > 0.0)
            cost_analysis = cost_multiplier_analysis(
                net_sharpe_at_multiple,
                multipliers=positive_multipliers,
                threshold=0.0,
            )
            _write_table(cost_analysis.table, "cost_multiples")
            for multiplier in positive_multipliers:
                counter = counter.record(
                    "cost_multiple", f"x{multiplier}", net_sharpe_at_multiple(multiplier)
                )

        # ------------------------------------------------------------------ #
        # 6. La robustesse
        # ------------------------------------------------------------------ #
        with stage("robustesse", experiment_id=run.record.experiment_id):
            sweep_rows: list[dict[str, Any]] = []
            for key, frame in pairs_a.items():
                for weight in weight_grid:
                    blend = blend_returns(frame["value"], frame["momentum"], value_weight=weight)
                    sharpe = sharpe_ratio(blend, frequency=MONTHLY)
                    sweep_rows.append(
                        {
                            "key": key,
                            "pair": PAIR_LABELS[key],
                            "value_weight": weight,
                            "n_months": len(blend),
                            "sharpe": sharpe,
                        }
                    )
                    counter = counter.record("weight_grid", f"{key}_w{weight}", sharpe)
            sweep_frame = pd.DataFrame(sweep_rows)
            _write_table(sweep_frame, "weight_sweep")

            optimum_rows: list[dict[str, Any]] = []
            for key in pairs_a:
                subset = sweep_frame.loc[sweep_frame["key"] == key].sort_values("sharpe")
                at_half = float(subset.loc[subset["value_weight"] == base_weight, "sharpe"].iloc[0])
                interior = subset.loc[(subset["value_weight"] > 0.0) & (subset["value_weight"] < 1.0)]
                optimum_rows.append(
                    {
                        "key": key,
                        "pair": PAIR_LABELS[key],
                        "best_weight": float(subset["value_weight"].iloc[-1]),
                        "best_sharpe": float(subset["sharpe"].iloc[-1]),
                        "sharpe_at_half": at_half,
                        "cost_of_holding_half": float(subset["sharpe"].iloc[-1]) - at_half,
                        "worst_interior_weight": float(interior["value_weight"].iloc[0]),
                        "worst_interior_sharpe": float(interior["sharpe"].iloc[0]),
                        "sharpe_value_only": float(
                            subset.loc[subset["value_weight"] == 1.0, "sharpe"].iloc[0]
                        ),
                        "sharpe_momentum_only": float(
                            subset.loc[subset["value_weight"] == 0.0, "sharpe"].iloc[0]
                        ),
                    }
                )
            optimum_frame = pd.DataFrame(optimum_rows)
            _write_table(optimum_frame, "weight_optimum")

            best_weight = (
                sweep_frame.loc[sweep_frame["key"] == headline]
                .sort_values("sharpe", ascending=False)["value_weight"]
                .iloc[0]
            )

            parity_rows: list[dict[str, Any]] = []
            for min_periods in params["risk_parity_min_periods_grid"]:
                min_periods = int(min_periods)
                live_weight = risk_parity_weights(
                    headline_frame["value"], headline_frame["momentum"], min_periods=min_periods
                )
                live_blend = blend_returns(
                    headline_frame["value"], headline_frame["momentum"], value_weight=live_weight
                )
                sharpe = sharpe_ratio(live_blend, frequency=MONTHLY)
                parity_rows.append(
                    {
                        "min_periods": min_periods,
                        "n_months": len(live_blend),
                        "start": str(live_blend.index[0].date()),
                        "median_value_weight": float(live_weight.dropna().median()),
                        "sharpe_live": sharpe,
                        "sharpe_full_sample_weight": float(
                            full_frame.loc[full_frame["key"] == headline, "sharpe_risk_parity"].iloc[0]
                        ),
                        "sharpe_equal_weight": float(
                            sharpe_ratio(headline_gross.loc[live_blend.index], frequency=MONTHLY)
                        ),
                    }
                )
                counter = counter.record("rp_window", f"min{min_periods}", sharpe)
            parity_frame = pd.DataFrame(parity_rows)
            _write_table(parity_frame, "risk_parity_window")

            rebalance_rows: list[dict[str, Any]] = []
            for months in params["rebalance_months_grid"]:
                months = int(months)
                out = rebalanced_blend(
                    headline_frame["value"],
                    headline_frame["momentum"],
                    value_weight=base_weight,
                    rebalance_months=months,
                )
                held = out[["value_weight", "momentum_weight"]].rename(
                    columns={"value_weight": "value", "momentum_weight": "momentum"}
                )
                rotation_k = turnover_series(held, headline_frame, drifted=True, convention="full_sum")
                gross_k = out["blend"]
                net_k = gross_k - rotation_k.reindex(gross_k.index).fillna(0.0) * spread_bps / 10_000.0
                sharpe = sharpe_ratio(net_k, frequency=MONTHLY)
                rebalance_rows.append(
                    {
                        "rebalance_months": months,
                        "n_months": len(gross_k),
                        "annual_turnover": annualized_turnover(rotation_k, frequency=MONTHLY),
                        "gross_sharpe": sharpe_ratio(gross_k, frequency=MONTHLY),
                        "net_sharpe": sharpe,
                        "max_value_weight": float(out["value_weight"].max()),
                        "min_value_weight": float(out["value_weight"].min()),
                    }
                )
                counter = counter.record("rebalance", f"k{months}", sharpe)
            rebalance_frame = pd.DataFrame(rebalance_rows)
            _write_table(rebalance_frame, "rebalance")

            lag_rows: list[dict[str, Any]] = []
            for lag in params["execution_lags"]:
                lag = int(lag)
                live_weight = risk_parity_weights(
                    headline_frame["value"],
                    headline_frame["momentum"],
                    min_periods=int(params["risk_parity_min_periods"]),
                ).shift(lag - 1)
                lagged = blend_returns(
                    headline_frame["value"], headline_frame["momentum"], value_weight=live_weight
                )
                sharpe = sharpe_ratio(lagged, frequency=MONTHLY)
                lag_rows.append(
                    {
                        "execution_lag_months": lag,
                        "n_months": len(lagged),
                        "sharpe": sharpe,
                        "median_value_weight": float(live_weight.dropna().median()),
                    }
                )
                counter = counter.record("lag", f"lag{lag}", sharpe)
            lag_frame = pd.DataFrame(lag_rows)
            _write_table(lag_frame, "execution_lag")

            rolling_rows: list[dict[str, Any]] = []
            rolling_series: dict[str, pd.Series] = {}
            for window in params["rolling_correlation_window_grid"]:
                window = int(window)
                series = rolling_correlation(
                    headline_frame["value"], headline_frame["momentum"], window=window
                ).dropna()
                rolling_series[str(window)] = series
                rolling_rows.append(
                    {
                        "window_months": window,
                        "n_windows": len(series),
                        "minimum": float(series.min()),
                        "median": float(series.median()),
                        "maximum": float(series.max()),
                        "share_negative": float((series < 0.0).mean()),
                        "date_of_maximum": str(series.idxmax().date()),
                    }
                )
            rolling_frame = pd.DataFrame(rolling_rows)
            _write_table(rolling_frame, "rolling_correlation")

            stress_rows: list[dict[str, Any]] = []
            for quantile in params["stress_quantile_grid"]:
                quantile = float(quantile)
                for key in ("EVERYWHERE", "ALL_EQUITIES", "US", "FF_HML_UMD"):
                    frame = (pairs_a | pairs_b)[key]
                    out = stress_correlation(frame["value"], frame["momentum"], market, quantile=quantile)
                    stress_rows.append(
                        {
                            "key": key,
                            "pair": PAIR_LABELS[key],
                            "quantile": quantile,
                            "threshold_market_pct": out["threshold"] * 100.0,
                            "n_stress": int(out["n_stress"]),
                            "correlation_stress": out["correlation_stress"],
                            "correlation_calm": out["correlation_calm"],
                            "gap": out["correlation_stress"] - out["correlation_calm"],
                        }
                    )
            stress_frame = pd.DataFrame(stress_rows)
            _write_table(stress_frame, "stress_correlation")

            subperiods = subperiod_performance(
                headline_net,
                breakpoints=[pd.Timestamp(b) for b in params["subperiod_breakpoints"]],
                frequency=MONTHLY,
            )
            _write_table(subperiods, "subperiods")

            tail_rows: list[dict[str, Any]] = []
            for name, series in (
                ("Valeur, toutes classes d'actifs", headline_frame["value"]),
                ("Momentum, toutes classes d'actifs", headline_frame["momentum"]),
                ("Mélange à parts égales, brut", headline_gross),
                ("Mélange à parts égales, net à dix points de base", headline_net),
            ):
                tail_rows.append(
                    {
                        "series": name,
                        "n_months": len(series),
                        "annual_return_pct": float(series.mean() * 12.0 * 100.0),
                        "annual_volatility_pct": float(volatility(series, frequency=MONTHLY) * 100.0),
                        "skewness": skewness(series),
                        "excess_kurtosis": kurtosis(series, excess=True),
                        "max_drawdown_pct": max_drawdown(series) * 100.0,
                        "sharpe": sharpe_ratio(series, frequency=MONTHLY),
                    }
                )
            tail_frame = pd.DataFrame(tail_rows)
            _write_table(tail_frame, "tail_risk")

        # ------------------------------------------------------------------ #
        # 7. Les contrôles de surapprentissage
        # ------------------------------------------------------------------ #
        with stage("validation", experiment_id=run.record.experiment_id):
            performance_matrix = pd.DataFrame(
                {
                    f"w{weight:.1f}": blend_returns(
                        headline_frame["value"], headline_frame["momentum"], value_weight=weight
                    )
                    - aligned_rotation * spread_bps / 10_000.0
                    for weight in weight_grid
                }
            ).dropna()
            pbo_result = probability_of_backtest_overfitting(
                performance_matrix, n_splits=8, frequency=MONTHLY
            )

            selected_weights: list[str] = []

            def best_of_path(path: Any) -> float:
                """Choisit le meilleur poids sur chaque bloc d'apprentissage.

                La validation croisée combinatoire ne dit rien d'une série
                figée, tout chemin la reconstruisant en entier. Elle juge donc
                ici le PROCESSUS de sélection du poids : sur chaque bloc
                d'apprentissage, le poids de meilleur ratio de Sharpe est
                retenu, et son rendement du bloc de test est collecté.
                """
                pieces: list[pd.Series] = []
                for segment in path.segments:
                    train = performance_matrix.iloc[segment.train_index]
                    test = performance_matrix.iloc[segment.test_index]
                    best = max(
                        performance_matrix.columns,
                        key=lambda column: sharpe_ratio(train[column], frequency=MONTHLY),
                    )
                    selected_weights.append(best)
                    pieces.append(test[best])
                return sharpe_ratio(pd.concat(pieces).sort_index(), frequency=MONTHLY)

            cv = CombinatorialPurgedCV.from_config(config.validation)
            distribution = cpcv_performance_distribution(
                cv, performance_matrix, best_of_path, metric_name="sharpe"
            )
            cpcv_frame = distribution.summary.rename("value").reset_index()
            cpcv_frame.columns = ["statistic", "value"]
            # La validation croisée ne dit rien si la sélection ne varie jamais.
            # Le compte de poids distincts retenus le rend lisible.
            cpcv_frame = pd.concat(
                [
                    cpcv_frame,
                    pd.DataFrame(
                        [
                            {
                                "statistic": "n_selections",
                                "value": float(len(selected_weights)),
                            },
                            {
                                "statistic": "n_distinct_weights_selected",
                                "value": float(len(set(selected_weights))),
                            },
                        ]
                    ),
                ],
                ignore_index=True,
            )
            _write_table(cpcv_frame, "cpcv_distribution")
            _write_table(distribution.metrics.rename("sharpe").reset_index(), "cpcv_paths")

            n_trials = counter.n_trials()
            if n_trials != expected_trials:
                raise ConfigError(
                    f"{n_trials} essais enregistrés contre {expected_trials} déduits des grilles. "
                    "Le compte du registre et celui du ratio de Sharpe dégonflé divergeraient."
                )
            oos_sharpe = sharpe_ratio(holdout, frequency=MONTHLY)
            oos_tstat = sharpe_tstat(holdout, frequency=MONTHLY)
            trial_variance = max(counter.sharpe_variance(), 1e-6)
            deflated_value = deflated_sharpe_ratio(
                observed_sr=oos_sharpe,
                sharpe_variance_across_trials=trial_variance,
                n_trials=n_trials,
                n_obs=float(len(holdout)),
                skew=skewness(holdout),
                kurtosis=kurtosis(holdout, excess=False),
            )
            if oos_sharpe > 0.0:
                cut = haircut_sharpe(
                    observed_sr=oos_sharpe,
                    n_tests=n_trials,
                    n_obs=len(holdout),
                    frequency=MONTHLY,
                    method="holm",
                )
                adjusted_tstat = cut.adjusted_tstat
                haircut_status = "calculé"
            else:
                adjusted_tstat = oos_tstat
                haircut_status = (
                    "non défini : rabattre un ratio de Sharpe négatif n'a pas de sens, "
                    "donc la statistique t brute est reportée telle quelle"
                )
            deflation_frame = pd.DataFrame(
                [
                    {
                        "observed_sharpe_oos_net": oos_sharpe,
                        "observed_tstat": oos_tstat,
                        "n_observations": len(holdout),
                        "n_trials": n_trials,
                        "variance_of_trial_sharpes": trial_variance,
                        "mean_sharpe_across_trials": counter.mean_sharpe(),
                        "expected_maximum_sharpe_under_null": expected_maximum_sharpe(
                            n_trials, trial_variance
                        ),
                        "deflated_sharpe": deflated_value,
                        "required_tstat_bonferroni": required_tstat(n_trials, 0.05, method="bonferroni"),
                        "adjusted_tstat": adjusted_tstat,
                        "haircut_status": haircut_status,
                    }
                ]
            )
            _write_table(deflation_frame, "deflated_sharpe")

            # Le compte d'essais de référence est 183, celui du registre. Les
            # deux autres conventions bornent l'effet du compte, et aucune ne
            # remplace la référence.
            sensitivity_rows: list[dict[str, Any]] = []
            for convention, sharpes in (
                (
                    "les 15 mélanges à parts égales, un par paire",
                    [row["sharpe_equal_weight"] for row in full_rows],
                ),
                (
                    "les 121 cellules du balayage des poids",
                    [row["sharpe"] for row in sweep_rows],
                ),
                ("tous les essais comptés, référence", None),
            ):
                if sharpes is None:
                    count, variance = n_trials, trial_variance
                else:
                    count, variance = len(sharpes), float(np.var(sharpes, ddof=1))
                sensitivity_rows.append(
                    {
                        "convention": convention,
                        "n_trials": count,
                        "variance_of_trial_sharpes": variance,
                        "expected_maximum_sharpe_under_null": expected_maximum_sharpe(count, variance),
                        "deflated_sharpe": deflated_sharpe_ratio(
                            observed_sr=oos_sharpe,
                            sharpe_variance_across_trials=variance,
                            n_trials=count,
                            n_obs=float(len(holdout)),
                            skew=skewness(holdout),
                            kurtosis=kurtosis(holdout, excess=False),
                        ),
                        "required_tstat_bonferroni": required_tstat(count, 0.05, method="bonferroni"),
                    }
                )
            _write_table(pd.DataFrame(sensitivity_rows), "deflation_sensitivity")

            multiplicity_rows: list[dict[str, Any]] = []
            for row in full_rows:
                key = row["key"]
                frame = (pairs_a | pairs_b)[key]
                blend = blend_returns(frame["value"], frame["momentum"], value_weight=base_weight)
                tstat = float(sharpe_tstat(blend, frequency=MONTHLY))
                multiplicity_rows.append(
                    {
                        "key": key,
                        "pair": row["pair"],
                        "leg": row["leg"],
                        "n_months": row["n_months"],
                        "sharpe_blend": row["sharpe_equal_weight"],
                        "tstat": tstat,
                        "pvalue": 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(tstat) / math.sqrt(2.0)))),
                    }
                )
            multiplicity = adjust_pvalues(
                [row["pvalue"] for row in multiplicity_rows], method="holm", alpha=0.05
            )
            multiple_frame = pd.DataFrame(multiplicity_rows)
            multiple_frame["adjusted_pvalue"] = multiplicity.adjusted_pvalues
            multiple_frame["rejected"] = multiplicity.rejected
            _write_table(multiple_frame, "multiple_testing")

            block = float(params["bootstrap_block_months"])
            distribution_boot = bootstrap_statistic(
                holdout.to_numpy(),
                lambda sample: float(np.mean(sample) * 12.0),
                "circular_block",
                int(params["bootstrap_resamples"]),
                generator_bootstrap,
                block_size=int(block),
            )
            bootstrap_frame = pd.DataFrame(
                [
                    {
                        "statistic": "rendement annualisé du mélange net, hors échantillon",
                        "observed": distribution_boot.observed,
                        "standard_error": distribution_boot.standard_error,
                        "p05": distribution_boot.quantile(0.05),
                        "p95": distribution_boot.quantile(0.95),
                        "share_positive": float((distribution_boot.replicates > 0.0).mean()),
                        "n_resamples": distribution_boot.n_resamples,
                        "block_months": block,
                    }
                ]
            )
            _write_table(bootstrap_frame, "bootstrap")

            trials_frame = pd.DataFrame(
                [{"family": family, "n_trials": counter.n_trials(family)} for family in counter.families()]
                + [{"family": "TOTAL", "n_trials": n_trials}]
            )
            _write_table(trials_frame, "trials")

        # ------------------------------------------------------------------ #
        # 8. Les figures
        # ------------------------------------------------------------------ #
        with stage("figures", experiment_id=run.record.experiment_id):
            figure_specs: list[tuple[str, str, str]] = []

            fig, _ = viz.equity_curve(
                {
                    "Valeur": headline_frame["value"],
                    "Momentum": headline_frame["momentum"],
                    "Mélange à parts égales": headline_gross,
                },
                log_scale=True,
                currency="$ US",
                title=(
                    "Un dollar au 31 janvier 1972, toutes classes d'actifs, "
                    "brut de frais, échelle logarithmique"
                ),
            )
            _save_figure(fig, "equity_everywhere")
            figure_specs.append(
                (
                    "equity_everywhere",
                    "performance",
                    "La richesse cumulée des deux jambes et de leur mélange.",
                )
            )

            heat_index = pairs_a["ALL_EQUITIES"].index.intersection(pairs_a["ALL_OTHER"].index)
            heat_frame = pd.DataFrame(
                {
                    "Valeur, actions": pairs_a["ALL_EQUITIES"]["value"].reindex(heat_index),
                    "Momentum, actions": pairs_a["ALL_EQUITIES"]["momentum"].reindex(heat_index),
                    "Valeur, hors actions": pairs_a["ALL_OTHER"]["value"].reindex(heat_index),
                    "Momentum, hors actions": pairs_a["ALL_OTHER"]["momentum"].reindex(heat_index),
                },
                index=heat_index,
            ).dropna()
            # Le titre se déduit des données. L'agrégat hors actions s'arrête
            # plus tôt que l'agrégat d'actions, donc l'intersection ne court
            # pas jusqu'à la fin du classeur.
            fig, _ = viz.correlation_heatmap(
                heat_frame,
                title=(
                    "Corrélations des quatre agrégats, mensuelles, "
                    f"{heat_frame.index[0]:%Y-%m} à {heat_frame.index[-1]:%Y-%m}"
                ),
            )
            _save_figure(fig, "correlation_heatmap")
            figure_specs.append(("correlation_heatmap", "performance", "Les quatre agrégats de la table II."))

            with viz.portfolio_style():
                fig = viz.mpl.figure.Figure(figsize=(8.0, 4.5), layout="tight")
                axes = fig.subplots()
                for window, series in rolling_series.items():
                    axes.plot(series.index, series.to_numpy(), label=f"{window} mois", linewidth=1.2)
                axes.axhline(0.0, color="black", linewidth=0.8)
                axes.set_ylabel("Corrélation valeur contre momentum")
                axes.set_xlabel("Fin de la fenêtre")
                axes.set_title("La corrélation reste négative dans toutes les fenêtres glissantes")
                # La virgule décimale des axes est la convention du portefeuille.
                # Les fabriques de viz la posent elles-mêmes ; une figure bâtie
                # à la main doit la poser.
                axes.yaxis.set_major_formatter(viz.gvf_style.formateur(2))
                axes.legend()
            _save_figure(fig, "rolling_correlation")
            figure_specs.append(
                ("rolling_correlation", "robustness", "La corrélation sur fenêtre glissante.")
            )

            with viz.portfolio_style():
                fig = viz.mpl.figure.Figure(figsize=(8.0, 4.5), layout="tight")
                axes = fig.subplots()
                grid = np.linspace(-0.95, 0.95, 200)
                median_value = float(np.median([r["sharpe_value"] for r in full_rows]))
                median_momentum = float(np.median([r["sharpe_momentum"] for r in full_rows]))
                axes.plot(
                    grid,
                    [equal_risk_sharpe(median_value, median_momentum, float(r)) for r in grid],
                    linewidth=1.4,
                    label="Formule, aux ratios de Sharpe médians des jambes",
                )
                for family, marker in (("A", "o"), ("B", "s")):
                    subset = [r for r in formula_rows if r["leg"] == family]
                    axes.scatter(
                        [r["correlation"] for r in subset],
                        [r["sharpe_risk_parity_measured"] for r in subset],
                        marker=marker,
                        s=36,
                        label=f"Mesuré, jambe {family}",
                    )
                axes.set_xlabel("Corrélation entre la valeur et le momentum")
                axes.set_ylabel("Ratio de Sharpe du mélange à risque égal")
                axes.set_title("Le ratio de Sharpe du mélange contre la corrélation des deux jambes")
                axes.xaxis.set_major_formatter(viz.gvf_style.formateur(2))
                axes.yaxis.set_major_formatter(viz.gvf_style.formateur(2))
                axes.legend()
            _save_figure(fig, "sharpe_versus_correlation")
            figure_specs.append(
                (
                    "sharpe_versus_correlation",
                    "performance",
                    "La mesure contre la forme fermée, quinze paires.",
                )
            )

            fig, _ = viz.parameter_heatmap(
                sweep_frame,
                x="value_weight",
                y="pair",
                metric="sharpe",
                x_label="Poids de la jambe de valeur",
                y_label="Regroupement",
                metric_label="Ratio de Sharpe annualisé, brut de frais",
                title="Le mélange bat ses deux jambes dans les onze regroupements",
            )
            _save_figure(fig, "weight_heatmap")
            figure_specs.append(
                ("weight_heatmap", "robustness", "Le ratio de Sharpe par poids et par regroupement.")
            )

            fig, _ = viz.subperiod_bars(
                subperiods,
                metric_column="sharpe",
                metric_label="Ratio de Sharpe annualisé, net",
                title="Le mélange par sous-période, net de dix points de base",
            )
            _save_figure(fig, "subperiod_bars")
            figure_specs.append(("subperiod_bars", "robustness", "Les trois sous-périodes."))

            fig, _ = viz.cost_sensitivity(
                positive_multipliers,
                [net_sharpe_at_multiple(m) for m in positive_multipliers],
                title="Le mélange hors échantillon contre le multiple de coût",
            )
            _save_figure(fig, "cost_sensitivity")
            figure_specs.append(("cost_sensitivity", "costs", "La sensibilité au coût."))

            fig, _ = viz.underwater(headline_net, title="La distance au sommet du mélange net, 1972-2026")
            _save_figure(fig, "underwater_blend")
            figure_specs.append(("underwater_blend", "performance", "Le repli du mélange."))

            fig, _ = viz.return_histogram(
                headline_net, title="La distribution mensuelle du mélange net, 1972-2026"
            )
            _save_figure(fig, "return_histogram")
            figure_specs.append(("return_histogram", "performance", "La distribution du mélange."))

        # ------------------------------------------------------------------ #
        # 9. Le verdict
        # ------------------------------------------------------------------ #
        checks = tuple(
            ReplicationCheck(
                quantity=f"corrélation valeur contre momentum, {PAIR_LABELS[row['key']]}",
                published=row["published_correlation"],
                ours=row["correlation"],
                tolerance=float(params["correlation_tolerance_sigmas"])
                * correlation_standard_error(row["published_correlation"], row["n_months"]),
                tolerance_kind="absolute",
                source="Asness, Moskowitz et Pedersen (2013), table I, colonne « facteur »",
                note=(
                    "Tolérance égale à deux erreurs types d'échantillonnage, "
                    "règle écrite dans config.yaml avant la mesure."
                ),
            )
            for row in replication_rows
        )
        _write_table(replication_table(checks), "replication_checks")

        criteria = VerdictCriteria(**params["verdict"])
        positive_share = float((subperiods["sharpe"] > 0.0).mean())
        all_negative = bool(all(row["correlation"] < 0.0 for row in full_rows))
        all_beat_legs = bool(all(row["gain_over_best_leg"] > 0.0 for row in full_rows))
        market_common = market.reindex(headline_gross.index).dropna()
        portfolio_correlation = float(headline_gross.loc[market_common.index].corr(market_common))
        evidence = VerdictEvidence(
            hypothesis_supported=all_negative and all_beat_legs,
            replication_checks=checks,
            oos_sharpe=oos_sharpe,
            tstat_after_multiplicity=adjusted_tstat,
            deflated_sharpe=deflated_value,
            pbo=pbo_result.pbo,
            positive_subperiod_share=positive_share,
            surviving_cost_multiple=(
                cost_analysis.breakeven_multiplier
                if cost_analysis.breakeven_multiplier is not None
                else (
                    float(cost_analysis.table["multiplier"].max())
                    if cost_analysis.status == "survives_all"
                    else 0.0
                )
            ),
            portfolio_correlation=portfolio_correlation,
            notes=(
                "Le hors échantillon porte sur le mélange à parts égales de la paire toutes "
                "classes d'actifs, net de dix points de base, après juillet 2011."
            ),
        )
        verdict, reasons = decide_verdict(evidence, criteria)
        run.set_verdict(verdict)

        headline_row = next(row for row in full_rows if row["key"] == headline)
        metric_values = {
            "correlation_toutes_classes": headline_row["correlation"],
            "sharpe_valeur_toutes_classes": headline_row["sharpe_value"],
            "sharpe_momentum_toutes_classes": headline_row["sharpe_momentum"],
            "sharpe_melange_parts_egales": headline_row["sharpe_equal_weight"],
            "sharpe_melange_risque_egal": headline_row["sharpe_risk_parity"],
            "gain_sur_la_meilleure_jambe": headline_row["gain_over_best_leg"],
            "multiplicateur_de_diversification": headline_row["diversification_multiplier"],
            "sharpe_par_unite_de_correlation": headline_row["sharpe_per_unit_correlation"],
            "ecart_maximal_mesure_contre_formule": float(formula_frame["max_absolute_gap"].max()),
            "sharpe_melange_oos_net": oos_sharpe,
            "rotation_annualisee": annual_rotation,
            "cout_de_rentabilite_bps": breakeven,
            "probabilite_de_surapprentissage": pbo_result.pbo,
            "sharpe_degonfle": deflated_value,
            "t_apres_correction": adjusted_tstat,
            "part_de_sous_periodes_positives": positive_share,
            "correlation_avec_le_marche": portfolio_correlation,
            "cpcv_sharpe_moyen": float(distribution.summary["mean"]),
            "cpcv_part_de_chemins_negatifs": float(distribution.negative_share),
        }
        labels = {
            "correlation_toutes_classes": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "sharpe_valeur_toutes_classes": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "sharpe_momentum_toutes_classes": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "sharpe_melange_parts_egales": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "sharpe_melange_risque_egal": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "gain_sur_la_meilleure_jambe": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "multiplicateur_de_diversification": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "sharpe_par_unite_de_correlation": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "ecart_maximal_mesure_contre_formule": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "sharpe_melange_oos_net": MetricLabel(SampleTag.OUT_OF_SAMPLE, CostBasis.NET),
            "rotation_annualisee": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "cout_de_rentabilite_bps": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "probabilite_de_surapprentissage": MetricLabel(SampleTag.VALIDATION, CostBasis.NET),
            "sharpe_degonfle": MetricLabel(SampleTag.OUT_OF_SAMPLE, CostBasis.NET),
            "t_apres_correction": MetricLabel(SampleTag.OUT_OF_SAMPLE, CostBasis.NET),
            "part_de_sous_periodes_positives": MetricLabel(SampleTag.VALIDATION, CostBasis.NET),
            "correlation_avec_le_marche": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "cpcv_sharpe_moyen": MetricLabel(SampleTag.OUT_OF_SAMPLE, CostBasis.NET),
            "cpcv_part_de_chemins_negatifs": MetricLabel(SampleTag.OUT_OF_SAMPLE, CostBasis.NET),
        }
        metrics = metrics_table(metric_values, labels)
        _write_table(metrics, "metrics")
        for name, value in metric_values.items():
            run.log_metric(name, value, sample=labels[name].sample)

        payload = {
            "study": "003_value_and_momentum",
            "experiment_id": run.record.experiment_id,
            "seed": config.seed,
            "verdict": verdict.value,
            "reasons": reasons,
            "n_trials": n_trials,
            "trials_by_family": {family: counter.n_trials(family) for family in counter.families()},
            "metrics": metric_values,
            "metric_samples": {name: label.sample.value for name, label in labels.items()},
            "cost_basis": {name: label.cost_basis.value for name, label in labels.items()},
            "hypothesis_parts": {
                "toutes_les_correlations_negatives": all_negative,
                "le_melange_bat_les_deux_jambes_partout": all_beat_legs,
                "meilleur_poids_de_valeur_sur_la_paire_de_reference": float(best_weight),
            },
            "samples": {
                "paper_window": [str(paper_start.date()), str(paper_end.date())],
                "full_window": [
                    str(headline_frame.index[0].date()),
                    str(headline_frame.index[-1].date()),
                ],
                "holdout_window": [str(holdout.index[0].date()), str(holdout.index[-1].date())],
            },
            "cost_assumptions_bps": {"spread_bps": spread_bps},
        }
        (RESULTS / "metrics.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        report_tables = [
            ReportTable(
                "replication_table1", "replication", replication_frame, "La table I, colonne facteur."
            ),
            ReportTable("pairs_full_sample", "performance", full_frame, "Les quinze paires."),
            ReportTable("formula_check", "performance", formula_frame, "La mesure contre la formule."),
            ReportTable("balanced_panel", "replication", balanced_frame, "Le panneau déséquilibré."),
            ReportTable(
                "mechanical_correlation",
                "robustness",
                mechanical_frame,
                "La part mécanique de la corrélation.",
            ),
            ReportTable("weight_sweep", "robustness", sweep_frame, "Le balayage des poids."),
            ReportTable("weight_optimum", "robustness", optimum_frame, "Le poids optimal par paire."),
            ReportTable("risk_parity_window", "out_of_sample", parity_frame, "Le poids en temps réel."),
            ReportTable("rebalance", "costs", rebalance_frame, "Le rééquilibrage et sa rotation."),
            ReportTable("costs", "costs", cost_frame, "Les coûts et le rendement net."),
            ReportTable("subperiods", "robustness", subperiods, "Les sous-périodes."),
            ReportTable(
                "holdout_composition",
                "out_of_sample",
                composition_frame,
                "La composition du hors échantillon.",
            ),
            ReportTable(
                "stress_correlation", "robustness", stress_frame, "La corrélation en période de tension."
            ),
            ReportTable(
                "cpcv_distribution",
                "out_of_sample",
                cpcv_frame,
                "La validation croisée combinatoire purgée.",
            ),
            ReportTable("multiple_testing", "statistical_tests", multiple_frame, "La correction de Holm."),
            ReportTable("trials", "statistical_tests", trials_frame, "Le compte des essais."),
        ]
        report_figures = [
            ReportFigure(name, section, FIGURES / f"{name}.png", caption)
            for name, section, caption in figure_specs
        ]
        report = StudyReport(
            study_name="003_value_and_momentum",
            experiment_id=run.record.experiment_id,
            hypothesis=config.hypothesis,
            paper=config.paper or "",
            criteria=criteria,
            evidence=evidence,
            sections=_sections(metric_values, headline_row, oos_sharpe, annual_rotation),
            metrics=metrics,
            tables=report_tables,
            figures=report_figures,
            config=config.model_dump(mode="json"),
            dataset_manifests=manifests,
        )
        generate_report(STUDY_DIR, report)
        run.log_artifact(str(RESULTS))

        AlphaRegistry().register(
            AlphaMetadata(
                name="value_and_momentum_everywhere",
                family="value",
                paper=config.paper,
                asset_classes=[
                    AssetClass.EQUITY,
                    AssetClass.EQUITY_INDEX,
                    AssetClass.FX,
                    AssetClass.BOND,
                    AssetClass.COMMODITY,
                ],
                horizon="formation mensuelle, détention un mois, rééquilibrage mensuel",
                economic_rationale=["contrainte institutionnelle", "prime de risque"],
                inputs=[
                    "facteurs de valeur et de momentum d'AQR, mensuels, depuis janvier 1972",
                    "facteurs et portefeuilles triés de Kenneth French, mensuels, depuis 1926",
                ],
                known_risks=[
                    "Une part de la corrélation négative vient du prix partagé par les deux signaux.",
                    "Les facteurs d'AQR sont bruts de frais et leur rotation interne n'est pas publiée.",
                    "Le panneau est déséquilibré avant 1983, les huit classes n'existant pas toutes.",
                    "Le momentum s'effondre par crises, Daniel et Moskowitz (2016).",
                ],
                validation_status=verdict,
                verdict_experiment_id=run.record.experiment_id,
                created=pd.Timestamp.today().date(),
                last_modified=pd.Timestamp.today().date(),
                notes=(
                    "Étude 003. Le mécanisme invoqué est le risque de financement : le momentum "
                    "tient les positions encombrées et souffre des chocs de liquidité, la valeur "
                    "tient les positions contrariennes et y gagne. Le résultat de l'étude porte "
                    "sur la diversification et non sur les rendements des jambes. Le verdict est "
                    "déduit par quantlab.reporting.study.decide_verdict."
                ),
            ),
            overwrite=True,
        )
        LOG.info("étude terminée", extra={"verdict": verdict.value, "n_trials": n_trials})


def _sections(
    metric_values: Mapping[str, float],
    headline_row: Mapping[str, Any],
    oos_sharpe: float,
    annual_rotation: float,
) -> dict[str, str]:
    """Rend la prose des quinze sections du rapport HTML."""
    return {
        "hypothesis": (
            "La valeur et le momentum sont-ils deux anomalies séparées, ou deux faces d'un même "
            "phénomène dont la corrélation négative fait tout le rendement du mélange ?"
        ),
        "paper": (
            "Asness, Moskowitz et Pedersen (2013), Value and Momentum Everywhere, Journal of "
            "Finance 68(3). Les chiffres cibles viennent de sa table I, colonne facteur."
        ),
        "methodology": (
            "Chaque paire donne une corrélation, deux ratios de Sharpe de jambe, et deux "
            "mélanges. Le premier pèse les dollars à parts égales, le second égalise les "
            "risques. La forme fermée du second prédit le résultat depuis trois nombres."
        ),
        "data": (
            "Onze paires viennent des facteurs publiés par AQR, mensuels depuis janvier 1972. "
            "Quatre paires sont bâties sur les portefeuilles triés de Kenneth French, sans "
            "biais de survie, depuis 1927."
        ),
        "implementation": (
            "La logique vit dans quantlab.strategies.value_momentum. Le mélange à parts égales "
            "n'estime rien. Le mélange à risque égal estime deux écarts types, et sa version "
            "tenable les calcule sur une fenêtre en expansion décalée d'un mois."
        ),
        "assumptions": (
            "Les facteurs sont autofinancés, donc leur rendement est déjà excédentaire. Les "
            "coûts internes de chaque jambe ne sont pas publiés et ne sont pas retranchés."
        ),
        "replication": (
            f"La corrélation de la paire toutes classes d'actifs vaut "
            f"{headline_row['correlation']:.3f} contre -0,60 publié."
        ),
        "performance": (
            "Tous les chiffres portent leur échantillon et leur base de coût dans le tableau ci-dessous."
        ),
        "costs": (
            f"La rotation annualisée du seul rééquilibrage vaut {annual_rotation:.2f} et le coût "
            f"qui annule le rendement brut vaut {metric_values['cout_de_rentabilite_bps']:.0f} "
            "points de base."
        ),
        "robustness": (
            "Le poids du mélange, la fenêtre de la corrélation, la période de tension, le pas de "
            "rééquilibrage et le délai d'exécution sont balayés. Chaque cellule compte comme un "
            "essai."
        ),
        "out_of_sample": (f"Après juillet 2011, le mélange net rend un ratio de Sharpe de {oos_sharpe:.2f}."),
        "statistical_tests": (
            "Le ratio de Sharpe dégonflé, la probabilité de surapprentissage et la correction de "
            "Holm sur les quinze paires sont rapportés dans les tableaux joints."
        ),
        "factor_attribution": (
            f"La corrélation du mélange avec le marché américain vaut "
            f"{metric_values['correlation_avec_le_marche']:.3f}, et elle décide du critère "
            "d'apport au portefeuille."
        ),
        "limitations": (
            "Les facteurs d'AQR ne sont pas reconstructibles sans données commerciales. Une part "
            "de la corrélation négative vient de la construction des deux signaux. Le panneau "
            "est déséquilibré avant 1983."
        ),
        "verdict": "Le verdict est déduit des seuils écrits dans config.yaml, sans arbitrage.",
    }


if __name__ == "__main__":
    main()

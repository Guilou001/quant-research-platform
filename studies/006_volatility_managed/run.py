"""Le point d'entrée de l'étude 006, portefeuilles gérés en volatilité.

Ce fichier orchestre et n'implémente rien de réutilisable. La stratégie vit dans
:mod:`quantlab.strategies.volatility_managed`, les métriques dans
:mod:`quantlab.analytics`, les contrôles dans :mod:`quantlab.validation`.

Lancement :

.. code-block:: bash

    export QUANTLAB_USER_AGENT="votre nom votre courriel"
    uv run python studies/006_volatility_managed/run.py
"""

from __future__ import annotations

import hashlib
import io
import itertools
import json
import math
import warnings
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests

from quantlab.analytics.drawdown import max_drawdown
from quantlab.analytics.ratios import sharpe_ratio, sharpe_tstat
from quantlab.analytics.risk import expected_shortfall, kurtosis, skewness, value_at_risk
from quantlab.analytics.turnover import annualized_turnover, turnover_series
from quantlab.analytics.visualization import figures as viz
from quantlab.core.config import ExperimentConfig, get_settings, load_config
from quantlab.core.determinism import make_generator
from quantlab.core.errors import ConfigError
from quantlab.core.logging import get_logger, stage
from quantlab.core.types import AssetClass, CostBasis, Frequency, SampleTag
from quantlab.data.providers.french import FrenchProvider
from quantlab.execution.costs import LinearCostModel, breakeven_cost_bps
from quantlab.experiments import ExperimentRegistry
from quantlab.reporting.series import save_series
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
from quantlab.strategies.volatility_managed import (
    hedged_spread,
    monthly_variance,
    real_time_combination,
    spanning_regression,
    utility_gain,
    volatility_managed_returns,
)
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
from quantlab.validation.splits import WalkForward

warnings.filterwarnings("ignore", category=FutureWarning, module="pandas")

LOG = get_logger("quantlab.studies.006")
STUDY_DIR = Path(__file__).resolve().parent
RESULTS = STUDY_DIR / "results"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"

#: Le tableau 1, panneau A, du document de travail NBER 22208. RAPPORTÉ, lu dans
#: la fiche de littérature ``docs/literature/moreira_muir_2017.md``.
PAPER_TABLE_1: Mapping[str, dict[str, float]] = {
    "MKT-RF": {"beta": 0.61, "alpha": 4.86, "stderr": 1.56, "n": 1065, "r2": 0.37, "rmse": 51.39},
    "SMB": {"beta": 0.62, "alpha": -0.58, "stderr": 0.91, "n": 1065, "r2": 0.38, "rmse": 30.44},
    "HML": {"beta": 0.57, "alpha": 1.97, "stderr": 1.02, "n": 1065, "r2": 0.32, "rmse": 34.92},
    "MOM": {"beta": 0.47, "alpha": 12.51, "stderr": 1.71, "n": 1060, "r2": 0.22, "rmse": 50.37},
    "RMW": {"beta": 0.62, "alpha": 2.44, "stderr": 0.83, "n": 621, "r2": 0.38, "rmse": 20.16},
    "CMA": {"beta": 0.68, "alpha": 0.38, "stderr": 0.67, "n": 621, "r2": 0.46, "rmse": 17.55},
    "ROE": {"beta": 0.63, "alpha": 5.48, "stderr": 0.97, "n": 575, "r2": 0.40, "rmse": 23.69},
    "IA": {"beta": 0.68, "alpha": 1.55, "stderr": 0.67, "n": 575, "r2": 0.47, "rmse": 16.58},
    "CARRY": {"beta": 0.71, "alpha": 2.78, "stderr": 1.49, "n": 360, "r2": 0.33, "rmse": 25.34},
}

#: Le nom lisible de chaque facteur, employé dans les tableaux publiés.
FACTOR_LABELS: Mapping[str, str] = {
    "MKT-RF": "Marché",
    "SMB": "Taille",
    "HML": "Valeur",
    "MOM": "Momentum",
    "RMW": "Rentabilité (RMW)",
    "CMA": "Investissement (CMA)",
    "ROE": "Rentabilité sur fonds propres (ROE)",
    "IA": "Investissement (IA)",
    "CARRY": "Portage de change",
}


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


def _load_french(provider: FrenchProvider) -> dict[str, pd.DataFrame]:
    """Télécharge les six fichiers de la bibliothèque de Kenneth French."""
    names = {
        "three_daily": "F-F_Research_Data_Factors_daily",
        "three_monthly": "F-F_Research_Data_Factors",
        "five_daily": "F-F_Research_Data_5_Factors_2x3_daily",
        "five_monthly": "F-F_Research_Data_5_Factors_2x3",
        "mom_daily": "F-F_Momentum_Factor_daily",
        "mom_monthly": "F-F_Momentum_Factor",
    }
    return {key: provider.fetch(value) for key, value in names.items()}


def _load_global_q(daily_url: str, monthly_url: str, user_agent: str) -> dict[str, Any]:
    """Télécharge les facteurs q de Hou, Xue et Zhang, en libre accès."""
    out: dict[str, Any] = {}
    for key, url in (("daily", daily_url), ("monthly", monthly_url)):
        response = requests.get(url, headers={"User-Agent": user_agent}, timeout=120)
        response.raise_for_status()
        payload = response.content
        frame = pd.read_csv(io.BytesIO(payload))
        if key == "daily":
            frame.index = pd.DatetimeIndex(pd.to_datetime(frame.pop("date")), name="date")
        else:
            periods = [
                pd.Period(year=int(y), month=int(m), freq="M")
                for y, m in zip(frame["year"], frame["month"], strict=True)
            ]
            frame.index = pd.DatetimeIndex(
                pd.PeriodIndex(periods).to_timestamp(how="end").normalize(), name="date"
            )
            frame = frame.drop(columns=["year", "month"])
        out[key] = frame.astype(float) / 100.0
        out[f"{key}_sha256"] = hashlib.sha256(payload).hexdigest()
        out[f"{key}_bytes"] = len(payload)
        out[f"{key}_url"] = url
    return out


def _certainty_equivalent(returns: pd.Series, risk_aversion: float) -> float:
    """Rend l'équivalent certain annualisé d'un investisseur moyenne-variance."""
    periods = Frequency.MONTHLY.periods_per_year
    return float(returns.mean() * periods - 0.5 * risk_aversion * returns.var(ddof=1) * periods)


def _cost_series(weights: pd.DataFrame, rate_bps: float) -> pd.Series:
    """Rend le coût mensuel d'une suite de poids, au taux unitaire demandé."""
    model = LinearCostModel(spread_bps=rate_bps)
    dates = list(weights.index)
    values: list[float] = [0.0]
    for previous, current in itertools.pairwise(dates):
        cost = model.cost(previous=weights.loc[previous], target=weights.loc[current])
        values.append(float(cost))
    return pd.Series(values, index=weights.index, name="cost")


def main() -> None:
    """Mène l'étude de bout en bout et écrit tout ce qu'elle produit."""
    config = load_config(STUDY_DIR / "config.yaml", ExperimentConfig)
    params = config.params
    generator = make_generator(config.seed)
    counter = TrialCounter()
    RESULTS.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)

    paper_end = pd.Timestamp(params["paper_end"])
    naive_end = pd.Timestamp(params["naive_end"])
    full_end = pd.Timestamp(config.data.end)
    min_periods = int(params["constant_min_periods"])
    monthly = Frequency.MONTHLY

    # Le nombre d'essais est déduit des grilles AVANT l'ouverture de
    # l'expérience, parce que le registre le fige à l'ouverture. Il est ensuite
    # confronté au compte réellement enregistré, et un écart lève.
    n_estimators = 2 + len(params["ewma_halflives"]) + 1
    n_positive_multipliers = len([m for m in params["cost_multipliers"] if float(m) > 0.0])
    expected_trials = (
        2 * len(config.data.universe)
        + len(params["risk_aversion_grid"]) * len(params["constant_min_periods_grid"])
        + 2 * len(params["cost_bps_grid"])
        + n_positive_multipliers
        + len(params["execution_delays"])
        + n_estimators * len(params["leverage_caps"])
        + len(params["constant_min_periods_grid"])
        + 1
    )

    registry = ExperimentRegistry()
    manifests: list[dict[str, Any]] = []

    with registry.run(
        name="006_volatility_managed",
        hypothesis=config.hypothesis,
        config=config.model_dump(mode="json"),
        seed=config.seed,
        universe=list(config.data.universe),
        date_start=config.data.start,
        date_end=config.data.end,
        cost_basis=CostBasis.NET,
        cost_assumptions={"spread_bps": config.costs.spread_bps},
        n_trials=expected_trials,
    ) as run:
        # ------------------------------------------------------------------ #
        # 1. Les données
        # ------------------------------------------------------------------ #
        with stage("chargement", experiment_id=run.record.experiment_id):
            provider = FrenchProvider()
            french = _load_french(provider)
            user_agent = get_settings().user_agent
            global_q = _load_global_q(
                str(params["global_q_daily_url"]),
                str(params["global_q_monthly_url"]),
                user_agent,
            )
            for dataset, table in (
                ("F-F_Research_Data_Factors_daily", None),
                ("F-F_Research_Data_Factors", None),
                ("F-F_Research_Data_5_Factors_2x3_daily", None),
                ("F-F_Research_Data_5_Factors_2x3", None),
                ("F-F_Momentum_Factor_daily", None),
                ("F-F_Momentum_Factor", None),
            ):
                manifests.append(provider.manifest(dataset, table=table).model_dump(mode="json"))

        daily: dict[str, pd.Series] = {
            "MKT-RF": french["three_daily"]["MKT-RF"],
            "SMB": french["three_daily"]["SMB"],
            "HML": french["three_daily"]["HML"],
            "MOM": french["mom_daily"]["MOM"],
            "RMW": french["five_daily"]["RMW"],
            "CMA": french["five_daily"]["CMA"],
            "ROE": global_q["daily"]["R_ROE"],
            "IA": global_q["daily"]["R_IA"],
        }
        month: dict[str, pd.Series] = {
            "MKT-RF": french["three_monthly"]["MKT-RF"],
            "SMB": french["three_monthly"]["SMB"],
            "HML": french["three_monthly"]["HML"],
            "MOM": french["mom_monthly"]["MOM"],
            "RMW": french["five_monthly"]["RMW"],
            "CMA": french["five_monthly"]["CMA"],
            "ROE": global_q["monthly"]["R_ROE"],
            "IA": global_q["monthly"]["R_IA"],
        }

        sources = pd.DataFrame(
            [
                {
                    "source": "Kenneth French",
                    "dataset": name,
                    "start": str(frame.index[0].date()),
                    "end": str(frame.index[-1].date()),
                    "n_rows": len(frame),
                }
                for name, frame in (
                    ("F-F_Research_Data_Factors_daily", french["three_daily"]),
                    ("F-F_Research_Data_Factors", french["three_monthly"]),
                    ("F-F_Research_Data_5_Factors_2x3_daily", french["five_daily"]),
                    ("F-F_Research_Data_5_Factors_2x3", french["five_monthly"]),
                    ("F-F_Momentum_Factor_daily", french["mom_daily"]),
                    ("F-F_Momentum_Factor", french["mom_monthly"]),
                )
            ]
            + [
                {
                    "source": "global-q.org",
                    "dataset": f"q5_factors_{key} (sha256 {global_q[f'{key}_sha256'][:12]})",
                    "start": str(global_q[key].index[0].date()),
                    "end": str(global_q[key].index[-1].date()),
                    "n_rows": len(global_q[key]),
                }
                for key in ("daily", "monthly")
            ]
        )
        _write_table(sources, "data_sources")

        variance: dict[str, pd.DataFrame] = {
            name: monthly_variance(
                series,
                method=str(params["variance_method"]),
                parameters={
                    "demean": bool(params["demean_realized_variance"]),
                    "min_observations": int(params["min_trading_days"]),
                },
            )
            for name, series in daily.items()
        }

        # ------------------------------------------------------------------ #
        # 2. Front 1, le compte de mois
        # ------------------------------------------------------------------ #
        with stage("front1", experiment_id=run.record.experiment_id):
            rows: list[dict[str, Any]] = []
            for name in ("MKT-RF", "RMW"):
                for start in params["candidate_starts"]:
                    for min_days in params["candidate_min_days"]:
                        frame = monthly_variance(
                            daily[name],
                            method="realized",
                            parameters={"min_observations": int(min_days)},
                        )
                        managed = volatility_managed_returns(month[name], frame["variance"])
                        for end_name, end in (("naive_end", naive_end), ("paper_end", paper_end)):
                            kept = managed.returns.loc[
                                (managed.returns.index >= pd.Timestamp(start))
                                & (managed.returns.index <= end)
                            ]
                            rows.append(
                                {
                                    "factor": FACTOR_LABELS[name],
                                    "start": str(start),
                                    "min_trading_days": int(min_days),
                                    "end_label": end_name,
                                    "end": str(end.date()),
                                    "n_months": len(kept),
                                    "paper_n": PAPER_TABLE_1[name]["n"],
                                    "gap": int(len(kept) - PAPER_TABLE_1[name]["n"]),
                                }
                            )
            month_counts = pd.DataFrame(rows)
            _write_table(month_counts, "front1_month_counts")

            end_rows: list[dict[str, Any]] = []
            for name in ("MKT-RF", "SMB", "HML", "MOM", "RMW", "CMA", "ROE", "IA"):
                managed = volatility_managed_returns(month[name], variance[name]["variance"])
                start_floor = (
                    pd.Timestamp(params["global_q_start"]) if name in ("ROE", "IA") else pd.Timestamp.min
                )
                for end_name, end in (("2015-12", naive_end), ("2015-04", paper_end)):
                    kept = managed.returns.loc[managed.returns.index <= end]
                    kept_floor = kept.loc[kept.index >= start_floor]
                    end_rows.append(
                        {
                            "factor": FACTOR_LABELS[name],
                            "end": end_name,
                            "n_months": len(kept),
                            "n_months_with_q_start": len(kept_floor),
                            "paper_n": int(PAPER_TABLE_1[name]["n"]),
                            "gap": int(len(kept) - PAPER_TABLE_1[name]["n"]),
                        }
                    )
            end_date_table = pd.DataFrame(end_rows)
            _write_table(end_date_table, "front1_end_date")

        # ------------------------------------------------------------------ #
        # 3. La réplication du tableau 1, panneau A
        # ------------------------------------------------------------------ #
        with stage("replication", experiment_id=run.record.experiment_id):
            replication_rows: list[dict[str, Any]] = []
            managed_paper: dict[str, Any] = {}
            for name in ("MKT-RF", "SMB", "HML", "MOM", "RMW", "CMA", "ROE", "IA"):
                floor = pd.Timestamp(params["global_q_start"]) if name in ("ROE", "IA") else pd.Timestamp.min
                factor = month[name].loc[(month[name].index >= floor) & (month[name].index <= paper_end)]
                result = volatility_managed_returns(factor, variance[name]["variance"])
                managed_paper[name] = result
                fit = spanning_regression(result.returns, result.base)
                paper = PAPER_TABLE_1[name]
                base_sharpe = sharpe_ratio(result.base, frequency=monthly)
                replication_rows.append(
                    {
                        "factor": FACTOR_LABELS[name],
                        "n_months": fit.n_observations,
                        "paper_n": int(paper["n"]),
                        "beta": fit.beta,
                        "paper_beta": paper["beta"],
                        "alpha_annual_pct": fit.alpha_annual * 100.0,
                        "paper_alpha": paper["alpha"],
                        "alpha_stderr_pct": fit.alpha_stderr_annual * 100.0,
                        "paper_stderr": paper["stderr"],
                        "alpha_tstat": fit.alpha_tstat,
                        "r_squared": fit.r_squared,
                        "paper_r2": paper["r2"],
                        "paper_rmse_ours": fit.paper_rmse,
                        "paper_rmse": paper["rmse"],
                        "appraisal_ratio": fit.appraisal_ratio,
                        "base_sharpe": base_sharpe,
                        "utility_gain": utility_gain(base_sharpe, fit.appraisal_ratio),
                    }
                )
                counter = counter.record("in_sample", f"{name}_realized", base_sharpe)
            replication_frame = pd.DataFrame(replication_rows)
            _write_table(replication_frame, "replication_table1")

            coverage = pd.DataFrame(
                [
                    {
                        "factor": FACTOR_LABELS[name],
                        "daily_source": source,
                        "monthly_source": source,
                        "covered": covered,
                    }
                    for name, source, covered in (
                        ("MKT-RF", "Kenneth French", True),
                        ("SMB", "Kenneth French", True),
                        ("HML", "Kenneth French", True),
                        ("MOM", "Kenneth French", True),
                        ("RMW", "Kenneth French", True),
                        ("CMA", "Kenneth French", True),
                        ("ROE", "global-q.org", True),
                        ("IA", "global-q.org", True),
                        ("CARRY", "non trouvé, série quotidienne non publiée", False),
                    )
                ]
            )
            _write_table(coverage, "factor_coverage")

        market = managed_paper["MKT-RF"]
        market_fit = spanning_regression(market.returns, market.base)
        save_series(
            RESULTS,
            "managed_market_ex_post_gross",
            market.returns,
            sample=SampleTag.IN_SAMPLE,
            basis=CostBasis.GROSS,
            frequency=Frequency.MONTHLY,
            universe="facteur Mkt-RF de Ken French",
            notes="constante de calibrage choisie sur toute la fenêtre de l'article, non tenable en direct",
        )

        # ------------------------------------------------------------------ #
        # 4. L'extension à juin 2026
        # ------------------------------------------------------------------ #
        with stage("extension", experiment_id=run.record.experiment_id):
            extension_rows: list[dict[str, Any]] = []
            managed_full: dict[str, Any] = {}
            for name in ("MKT-RF", "SMB", "HML", "MOM", "RMW", "CMA", "ROE", "IA"):
                floor = pd.Timestamp(params["global_q_start"]) if name in ("ROE", "IA") else pd.Timestamp.min
                factor = month[name].loc[(month[name].index >= floor) & (month[name].index <= full_end)]
                result = volatility_managed_returns(factor, variance[name]["variance"])
                managed_full[name] = result
                fit = spanning_regression(result.returns, result.base)
                after = result.returns.loc[result.returns.index > paper_end]
                after_base = result.base.loc[after.index]
                after_fit = spanning_regression(after, after_base) if len(after) > 12 else None
                extension_rows.append(
                    {
                        "factor": FACTOR_LABELS[name],
                        "n_months": fit.n_observations,
                        "alpha_annual_pct": fit.alpha_annual * 100.0,
                        "alpha_tstat": fit.alpha_tstat,
                        "appraisal_ratio": fit.appraisal_ratio,
                        "n_months_after_paper": len(after),
                        "alpha_after_paper_pct": (
                            after_fit.alpha_annual * 100.0 if after_fit is not None else float("nan")
                        ),
                        "alpha_after_paper_tstat": (
                            after_fit.alpha_tstat if after_fit is not None else float("nan")
                        ),
                    }
                )
            extension_frame = pd.DataFrame(extension_rows)
            _write_table(extension_frame, "extension_full_sample")

        # ------------------------------------------------------------------ #
        # 5. Front 3, la constante de calibrage
        # ------------------------------------------------------------------ #
        with stage("front3", experiment_id=run.record.experiment_id):
            constant_rows: list[dict[str, Any]] = []
            real_time: dict[str, Any] = {}
            for name in ("MKT-RF", "SMB", "HML", "MOM", "RMW", "CMA", "ROE", "IA"):
                ex_post = managed_full[name]
                live = volatility_managed_returns(
                    ex_post.base,
                    variance[name]["variance"],
                    constant="expanding",
                    min_periods=min_periods,
                )
                real_time[name] = live
                common = live.returns.index
                post_common = ex_post.returns.loc[common]
                fit_post = spanning_regression(post_common, ex_post.base.loc[common])
                fit_live = spanning_regression(live.returns, live.base)
                constant_rows.append(
                    {
                        "factor": FACTOR_LABELS[name],
                        "n_months": len(common),
                        "alpha_ex_post_pct": fit_post.alpha_annual * 100.0,
                        "alpha_real_time_pct": fit_live.alpha_annual * 100.0,
                        "alpha_gap_pct": (fit_live.alpha_annual - fit_post.alpha_annual) * 100.0,
                        "tstat_ex_post": fit_post.alpha_tstat,
                        "tstat_real_time": fit_live.alpha_tstat,
                        "appraisal_ex_post": fit_post.appraisal_ratio,
                        "appraisal_real_time": fit_live.appraisal_ratio,
                        "appraisal_ratio_of_ratios": (
                            fit_live.appraisal_ratio / fit_post.appraisal_ratio
                            if fit_post.appraisal_ratio != 0.0
                            else float("nan")
                        ),
                        "vol_ratio_ex_post": float(
                            post_common.std(ddof=1) / ex_post.base.loc[common].std(ddof=1)
                        ),
                        "vol_ratio_real_time": float(live.returns.std(ddof=1) / live.base.std(ddof=1)),
                    }
                )
                counter = counter.record("real_time", f"{name}_expanding", fit_live.appraisal_ratio)
            constant_frame = pd.DataFrame(constant_rows)
            _write_table(constant_frame, "front3_constant")

            combination_rows: list[dict[str, Any]] = []
            for gamma in params["risk_aversion_grid"]:
                for window in params["constant_min_periods_grid"]:
                    live = volatility_managed_returns(
                        managed_full["MKT-RF"].base,
                        variance["MKT-RF"]["variance"],
                        constant="expanding",
                        min_periods=int(window),
                    )
                    table = real_time_combination(
                        live.base,
                        live.returns,
                        min_periods=int(params["combination_min_periods"]),
                        risk_aversion=float(gamma),
                    )
                    combination_rows.append(
                        {
                            "risk_aversion": float(gamma),
                            "constant_window_months": int(window),
                            "n_months": len(table),
                            "sharpe_combination": sharpe_ratio(table["combination"], frequency=monthly),
                            "sharpe_base_only": sharpe_ratio(table["base_only"], frequency=monthly),
                            "ce_combination": _certainty_equivalent(table["combination"], float(gamma)),
                            "ce_base_only": _certainty_equivalent(table["base_only"], float(gamma)),
                            "median_weight_base": float(table["weight_base"].median()),
                            "median_weight_managed": float(table["weight_managed"].median()),
                            "p99_weight_managed": float(table["weight_managed"].quantile(0.99)),
                        }
                    )
                    counter = counter.record(
                        "combination",
                        f"gamma{gamma}_win{window}",
                        combination_rows[-1]["sharpe_combination"],
                    )
            combination_frame = pd.DataFrame(combination_rows)
            combination_frame["combination_wins"] = (
                combination_frame["ce_combination"] > combination_frame["ce_base_only"]
            )
            _write_table(combination_frame, "front3_combination")

            leverage_rows = []
            for name in ("MKT-RF", "MOM"):
                weights = managed_full[name].weights
                leverage_rows.append(
                    {
                        "factor": FACTOR_LABELS[name],
                        "median_weight": float(weights.median()),
                        "p95_weight": float(weights.quantile(0.95)),
                        "p99_weight": float(weights.quantile(0.99)),
                        "max_weight": float(weights.max()),
                        "share_above_2": float((weights > 2.0).mean()),
                        "correlation_with_base": float(
                            managed_full[name].returns.corr(managed_full[name].base)
                        ),
                    }
                )
            _write_table(pd.DataFrame(leverage_rows), "leverage_profile")

        # ------------------------------------------------------------------ #
        # 6. Les coûts
        # ------------------------------------------------------------------ #
        with stage("couts", experiment_id=run.record.experiment_id):
            live_market = real_time["MKT-RF"]
            spread_live = hedged_spread(live_market.returns, live_market.base, min_periods=min_periods)
            save_series(
                RESULTS,
                "managed_market_real_time_gross",
                live_market.returns,
                sample=SampleTag.OUT_OF_SAMPLE,
                basis=CostBasis.GROSS,
                frequency=Frequency.MONTHLY,
                universe="facteur Mkt-RF de Ken French",
                notes="constante estimée en expansion, tenable en temps réel",
            )
            save_series(
                RESULTS,
                "hedged_spread_real_time_gross",
                spread_live,
                sample=SampleTag.OUT_OF_SAMPLE,
                basis=CostBasis.GROSS,
                frequency=Frequency.MONTHLY,
                universe="facteur Mkt-RF de Ken French",
                notes="facteur géré moins bêta estimé sur le passé, la seule version négociable",
            )

            beta_live = (
                (live_market.returns.loc[spread_live.index] - spread_live)
                / live_market.base.loc[spread_live.index]
            ).rename("hedge")
            legs = pd.DataFrame(
                {
                    "managed_leg": live_market.weights.loc[spread_live.index],
                    "hedge_leg": -beta_live,
                }
            )
            rotation = turnover_series(legs, drifted=False, convention="full_sum", include_initial=False)

            post_market = managed_full["MKT-RF"]
            post_fit = spanning_regression(post_market.returns, post_market.base)
            spread_post = (post_market.returns - post_fit.beta * post_market.base).dropna()
            spread_post = spread_post.rename("spread_ex_post")
            legs_post = pd.DataFrame(
                {
                    "managed_leg": post_market.weights.loc[spread_post.index],
                    "hedge_leg": -post_fit.beta,
                }
            )
            rotation_post = turnover_series(
                legs_post, drifted=False, convention="full_sum", include_initial=False
            )

            versions = {
                "écart couvert, constante et bêta ex post": (spread_post, legs_post, rotation_post),
                "écart couvert, constante et bêta en temps réel": (spread_live, legs, rotation),
            }

            cost_rows: list[dict[str, Any]] = []
            net_by_rate: dict[float, pd.Series] = {}
            for version, (series, weight_frame, rotations) in versions.items():
                live_version = version.endswith("temps réel")
                for rate in params["cost_bps_grid"]:
                    costs = _cost_series(weight_frame, float(rate))
                    net = (series - costs).dropna()
                    if live_version:
                        net_by_rate[float(rate)] = net
                    cost_rows.append(
                        {
                            "version": version,
                            "cost_bps": float(rate),
                            "n_months": len(net),
                            "start": str(net.index[0].date()),
                            "end": str(net.index[-1].date()),
                            "gross_mean_annual_pct": float(series.mean() * 12.0 * 100.0),
                            "net_mean_annual_pct": float(net.mean() * 12.0 * 100.0),
                            "net_sharpe": sharpe_ratio(net, frequency=monthly),
                            "net_tstat": sharpe_tstat(net, frequency=monthly),
                            "annual_turnover": annualized_turnover(rotations, frequency=monthly),
                            "breakeven_cost_bps": breakeven_cost_bps(
                                series.loc[rotations.index], rotations, frequency=monthly
                            ),
                        }
                    )
                    family = "costs" if live_version else "costs_ex_post"
                    counter = counter.record(family, f"rate{rate}", cost_rows[-1]["net_sharpe"])
            cost_frame = pd.DataFrame(cost_rows)
            _write_table(cost_frame, "costs")

            annual_rotation = annualized_turnover(rotation, frequency=monthly)
            breakeven = breakeven_cost_bps(spread_live.loc[rotation.index], rotation, frequency=monthly)

            def evaluate_cost(multiplier: float) -> float:
                """Rend le Sharpe net de l'écart couvert à ce multiple de coût."""
                costs = _cost_series(legs, config.costs.spread_bps * multiplier)
                return sharpe_ratio((spread_live - costs).dropna(), frequency=monthly)

            cost_analysis = cost_multiplier_analysis(
                evaluate_cost,
                multipliers=[m for m in params["cost_multipliers"] if m > 0.0],
                threshold=0.0,
            )
            _write_table(cost_analysis.table, "cost_multiples")
            for multiplier, value in zip(
                cost_analysis.table["multiplier"], cost_analysis.table["metric"], strict=True
            ):
                counter = counter.record("cost_multiple", f"x{multiplier}", float(value))

            # Le bêta de couverture est le second estimateur en temps réel de
            # l'étude, et rien n'obligeait à le prendre en expansion. La ligne
            # ex post ci-dessous mesure ce que ce choix coûte. Elle emploie le
            # bêta de plein échantillon, donc elle n'est pas tenable : elle sert
            # à borner la fragilité du chiffre principal, pas à le remplacer.
            fixed_beta = spanning_regression(live_market.returns, live_market.base).beta
            spread_fixed = (live_market.returns - fixed_beta * live_market.base).loc[spread_live.index]
            hedge_rows = [
                {
                    "hedge_beta": "bêta en expansion, tenable",
                    "beta_median": float(beta_live.median()),
                    "n_months": len(spread_live),
                    "gross_sharpe_full": sharpe_ratio(spread_live, frequency=monthly),
                    "gross_sharpe_oos": sharpe_ratio(
                        spread_live.loc[spread_live.index > paper_end], frequency=monthly
                    ),
                    "correlation_with_base": float(spread_live.corr(live_market.base.loc[spread_live.index])),
                },
                {
                    "hedge_beta": "bêta de plein échantillon, non tenable",
                    "beta_median": fixed_beta,
                    "n_months": len(spread_fixed),
                    "gross_sharpe_full": sharpe_ratio(spread_fixed, frequency=monthly),
                    "gross_sharpe_oos": sharpe_ratio(
                        spread_fixed.loc[spread_fixed.index > paper_end], frequency=monthly
                    ),
                    "correlation_with_base": float(
                        spread_fixed.corr(live_market.base.loc[spread_fixed.index])
                    ),
                },
            ]
            hedge_frame = pd.DataFrame(hedge_rows)
            _write_table(hedge_frame, "hedge_sensitivity")
            counter = counter.record("hedge", "beta_plein_echantillon", hedge_rows[1]["gross_sharpe_full"])

            delay_rows: list[dict[str, Any]] = []
            for delay in params["execution_delays"]:
                shifted = live_market.weights.shift(delay - 1)
                delayed = (shifted * live_market.base).dropna()
                delay_rows.append(
                    {
                        "execution_lag_months": int(delay),
                        "n_months": len(delayed),
                        "sharpe": sharpe_ratio(delayed, frequency=monthly),
                        "alpha_annual_pct": spanning_regression(
                            delayed, live_market.base.loc[delayed.index]
                        ).alpha_annual
                        * 100.0,
                    }
                )
                counter = counter.record("delay", f"lag{delay}", delay_rows[-1]["sharpe"])
            _write_table(pd.DataFrame(delay_rows), "execution_delay")

        # ------------------------------------------------------------------ #
        # 7. La robustesse
        # ------------------------------------------------------------------ #
        with stage("robustesse", experiment_id=run.record.experiment_id):
            estimator_rows: list[dict[str, Any]] = []
            configurations: dict[str, pd.Series] = {}
            base_market = managed_full["MKT-RF"].base

            estimators: list[tuple[str, str, dict[str, Any]]] = [
                ("variance réalisée", "realized", {"demean": False}),
                ("variance réalisée centrée", "realized", {"demean": True}),
            ]
            estimators += [
                (f"lissage exponentiel {h:.0f} séances", "ewma", {"halflife_days": float(h)})
                for h in params["ewma_halflives"]
            ]
            estimators.append(
                (
                    "GARCH(1,1) réestimé",
                    "garch",
                    {
                        "refit_months": int(params["garch_refit_months"]),
                        "min_train_days": int(params["garch_min_train_days"]),
                        "p": int(params["garch_p"]),
                        "q": int(params["garch_q"]),
                        "distribution": str(params["garch_distribution"]),
                    },
                )
            )

            for label, method, kwargs in estimators:
                estimate = monthly_variance(daily["MKT-RF"], method=method, parameters=kwargs)
                for cap in params["leverage_caps"]:
                    cap_value = None if float(cap) == 0.0 else float(cap)
                    live = volatility_managed_returns(
                        base_market,
                        estimate["variance"],
                        constant="expanding",
                        min_periods=min_periods,
                        leverage_cap=cap_value,
                    )
                    spread = hedged_spread(live.returns, live.base, min_periods=min_periods)
                    costs = _cost_series(
                        pd.DataFrame({"managed_leg": live.weights.loc[spread.index]}),
                        config.costs.spread_bps,
                    )
                    net = (spread - costs).dropna()
                    key = f"{label} | plafond {cap}"
                    configurations[key] = net
                    sharpe = sharpe_ratio(net, frequency=monthly)
                    estimator_rows.append(
                        {
                            "estimator": label,
                            "leverage_cap": float(cap),
                            "n_months": len(net),
                            "net_sharpe": sharpe,
                            "net_alpha_annual_pct": float(net.mean() * 12.0 * 100.0),
                            "net_tstat": sharpe_tstat(net, frequency=monthly),
                        }
                    )
                    counter = counter.record("sweep", key, sharpe)
            sweep_frame = pd.DataFrame(estimator_rows)
            _write_table(sweep_frame, "parameter_sweep")

            window_rows: list[dict[str, Any]] = []
            for window in params["constant_min_periods_grid"]:
                live = volatility_managed_returns(
                    base_market,
                    variance["MKT-RF"]["variance"],
                    constant="expanding",
                    min_periods=int(window),
                )
                fit = spanning_regression(live.returns, live.base)
                spread = hedged_spread(live.returns, live.base, min_periods=int(window))
                window_rows.append(
                    {
                        "constant_window_months": int(window),
                        "n_months": fit.n_observations,
                        "alpha_annual_pct": fit.alpha_annual * 100.0,
                        "alpha_tstat": fit.alpha_tstat,
                        "appraisal_ratio": fit.appraisal_ratio,
                        "hedged_spread_sharpe": sharpe_ratio(spread, frequency=monthly),
                    }
                )
                counter = counter.record("window", f"win{window}", window_rows[-1]["hedged_spread_sharpe"])
            _write_table(pd.DataFrame(window_rows), "constant_window")

            subperiods = subperiod_performance(
                spread_live,
                breakpoints=[*[pd.Timestamp(b) for b in params["subperiod_breakpoints"]], paper_end],
                frequency=monthly,
                min_observations=12,
            )
            subperiods["label"] = [
                f"{pd.Timestamp(a):%Y-%m} à {pd.Timestamp(b):%Y-%m}"
                for a, b in zip(subperiods["start"], subperiods["end"], strict=True)
            ]
            _write_table(subperiods, "subperiods")

            tail_rows: list[dict[str, Any]] = []
            for label, series in (
                ("Marché", base_market),
                ("Marché géré, constante ex post", managed_full["MKT-RF"].returns),
                ("Marché géré, constante en temps réel", live_market.returns),
                ("Écart couvert en temps réel, net", net_by_rate[config.costs.spread_bps]),
            ):
                tail_rows.append(
                    {
                        "series": label,
                        "n_months": len(series),
                        "annual_return_pct": float(series.mean() * 12.0 * 100.0),
                        "annual_vol_pct": float(series.std(ddof=1) * math.sqrt(12.0) * 100.0),
                        "sharpe": sharpe_ratio(series, frequency=monthly),
                        "skewness": skewness(series),
                        "excess_kurtosis": kurtosis(series),
                        "var_5_pct": value_at_risk(series, 0.05) * 100.0,
                        "expected_shortfall_5_pct": expected_shortfall(series, 0.05) * 100.0,
                        "max_drawdown_pct": max_drawdown(series) * 100.0,
                    }
                )
            _write_table(pd.DataFrame(tail_rows), "tail_risk")

        # ------------------------------------------------------------------ #
        # 8. Les contrôles statistiques
        # ------------------------------------------------------------------ #
        with stage("validation", experiment_id=run.record.experiment_id):
            performance_matrix = pd.DataFrame(configurations).dropna()
            pbo_result = probability_of_backtest_overfitting(
                performance_matrix, n_splits=8, frequency=monthly
            )

            def best_of_path(path: Any) -> float:
                """Choisit la meilleure configuration sur chaque bloc d'apprentissage.

                La validation croisée combinatoire ne dit rien d'une série figée,
                puisque tout chemin la reconstruit en entier. Elle juge donc ici
                le PROCESSUS de sélection : sur chaque bloc d'apprentissage, la
                configuration de meilleur Sharpe est retenue, et son rendement du
                bloc de test suivant est collecté.
                """
                pieces: list[pd.Series] = []
                for segment in path.segments:
                    train = performance_matrix.iloc[segment.train_index]
                    test = performance_matrix.iloc[segment.test_index]
                    best = max(
                        performance_matrix.columns,
                        key=lambda column: sharpe_ratio(train[column], frequency=monthly),
                    )
                    pieces.append(test[best])
                return sharpe_ratio(pd.concat(pieces).sort_index(), frequency=monthly)

            cv = CombinatorialPurgedCV.from_config(config.validation)
            distribution = cpcv_performance_distribution(
                cv,
                performance_matrix,
                best_of_path,
                metric_name="sharpe",
            )
            cpcv_frame = distribution.summary.rename("value").reset_index()
            cpcv_frame.columns = ["statistic", "value"]
            _write_table(cpcv_frame, "cpcv_distribution")
            _write_table(distribution.metrics.rename("sharpe").reset_index(), "cpcv_paths")

            walk = WalkForward(
                train_size=int(params["constant_min_periods"]),
                test_size=12,
                anchored=True,
                purge=int(config.validation.purge_periods),
                embargo=int(config.validation.embargo_periods),
            )
            walk_rows: list[dict[str, Any]] = []
            values = spread_live.to_numpy()
            for fold, (train_idx, test_idx) in enumerate(walk.split(spread_live)):
                block = pd.Series(values[test_idx], index=spread_live.index[test_idx])
                walk_rows.append(
                    {
                        "fold": fold,
                        "train_end": str(spread_live.index[train_idx][-1].date()),
                        "test_start": str(block.index[0].date()),
                        "test_end": str(block.index[-1].date()),
                        "n_test": len(block),
                        "mean_annual_pct": float(block.mean() * 12.0 * 100.0),
                    }
                )
            walk_frame = pd.DataFrame(walk_rows)
            _write_table(walk_frame, "walk_forward")

            oos = net_by_rate[config.costs.spread_bps]
            holdout = oos.loc[oos.index > paper_end]
            oos_sharpe = sharpe_ratio(holdout, frequency=monthly)
            n_trials = counter.n_trials()
            if n_trials != expected_trials:
                raise ConfigError(
                    f"{n_trials} essais enregistrés contre {expected_trials} déduits des grilles. "
                    "Le compte du registre et celui du ratio de Sharpe dégonflé divergeraient."
                )
            trial_variance = max(counter.sharpe_variance(), 1e-6)
            oos_tstat = sharpe_tstat(holdout, frequency=monthly)
            deflated_value = deflated_sharpe_ratio(
                observed_sr=oos_sharpe,
                sharpe_variance_across_trials=trial_variance,
                n_trials=n_trials,
                n_obs=float(len(holdout)),
                skew=skewness(holdout),
                kurtosis=kurtosis(holdout, excess=False),
            )
            expected_max = expected_maximum_sharpe(n_trials, trial_variance)
            if oos_sharpe > 0.0:
                cut = haircut_sharpe(
                    observed_sr=oos_sharpe,
                    n_tests=n_trials,
                    n_obs=len(holdout),
                    frequency=monthly,
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
                        "expected_maximum_sharpe_under_null": expected_max,
                        "deflated_sharpe": deflated_value,
                        "required_tstat_bonferroni": required_tstat(n_trials, 0.05, method="bonferroni"),
                        "adjusted_tstat": adjusted_tstat,
                        "haircut_status": haircut_status,
                    }
                ]
            )
            _write_table(deflation_frame, "deflated_sharpe")

            factor_pvalues = []
            for row in constant_rows:
                tstat = abs(row["tstat_real_time"])
                factor_pvalues.append(2.0 * (1.0 - 0.5 * (1.0 + math.erf(tstat / math.sqrt(2.0)))))
            multiplicity = adjust_pvalues(factor_pvalues, method="holm", alpha=0.05)
            multiple_frame = pd.DataFrame(
                {
                    "factor": [row["factor"] for row in constant_rows],
                    "tstat_real_time": [row["tstat_real_time"] for row in constant_rows],
                    "pvalue": factor_pvalues,
                    "adjusted_pvalue": multiplicity.adjusted_pvalues,
                    "rejected": multiplicity.rejected,
                }
            )
            _write_table(multiple_frame, "multiple_testing")

            block_size = float(params["bootstrap_block_months"])
            draws = int(params["bootstrap_resamples"])
            sample = holdout.to_numpy()
            replicates = np.empty(draws, dtype=float)
            for draw in range(draws):
                starts = generator.integers(0, len(sample), size=int(np.ceil(len(sample) / block_size)))
                pieces = [sample[s : s + int(block_size)] for s in starts]
                joined = np.concatenate(pieces)[: len(sample)]
                replicates[draw] = joined.mean() * 12.0
            bootstrap_frame = pd.DataFrame(
                {
                    "statistic": ["rendement annualisé de l'écart couvert net, hors échantillon"],
                    "observed": [float(sample.mean() * 12.0)],
                    "p05": [float(np.quantile(replicates, 0.05))],
                    "p95": [float(np.quantile(replicates, 0.95))],
                    "share_positive": [float((replicates > 0.0).mean())],
                    "n_resamples": [draws],
                }
            )
            _write_table(bootstrap_frame, "bootstrap")

            trials_frame = pd.DataFrame(
                [{"family": family, "n_trials": counter.n_trials(family)} for family in counter.families()]
                + [{"family": "TOTAL", "n_trials": n_trials}]
            )
            _write_table(trials_frame, "trials")

        # ------------------------------------------------------------------ #
        # 9. Les figures
        # ------------------------------------------------------------------ #
        with stage("figures", experiment_id=run.record.experiment_id):
            figure_specs: list[tuple[str, str, str]] = []

            equity_start = max(managed_full["MKT-RF"].returns.index[0], live_market.returns.index[0])
            fig, _ = viz.equity_curve(
                {
                    "Marché géré, constante ex post": managed_full["MKT-RF"].returns.loc[
                        managed_full["MKT-RF"].returns.index >= equity_start
                    ],
                    "Marché géré, constante en temps réel": live_market.returns,
                },
                benchmark=base_market.loc[base_market.index >= equity_start],
                benchmark_label="Marché, sans gestion",
                log_scale=True,
                title=(
                    "Richesse cumulée du marché géré en volatilité, base 1 dollar des "
                    f"États-Unis au {equity_start:%Y-%m-%d}"
                ),
            )
            figure_specs.append(
                (
                    _save_figure(fig, "equity_market").stem,
                    "performance",
                    "Richesse cumulée en échelle logarithmique, dollars des États-Unis.",
                )
            )

            fig, _ = viz.underwater(
                live_market.returns,
                title="Repli du marché géré en volatilité, constante en temps réel",
            )
            figure_specs.append(
                (
                    _save_figure(fig, "underwater_real_time").stem,
                    "robustness",
                    "Distance au sommet précédent, en points de pourcentage.",
                )
            )

            fig, _ = viz.rolling_metric(
                spread_live,
                metric="sharpe",
                window=120,
                frequency=monthly,
                title="Ratio de Sharpe glissant sur dix ans de l'écart couvert en temps réel",
            )
            figure_specs.append(
                (
                    _save_figure(fig, "rolling_sharpe_spread").stem,
                    "out_of_sample",
                    "Ratio de Sharpe annualisé sur fenêtre glissante de 120 mois.",
                )
            )

            fig, _ = viz.cost_sensitivity(
                list(cost_analysis.table["multiplier"]),
                list(cost_analysis.table["metric"]),
                threshold=0.0,
                metric_label="Ratio de Sharpe net de l'écart couvert",
                title="Sensibilité au multiple de coût, écart couvert en temps réel",
            )
            figure_specs.append(
                (
                    _save_figure(fig, "cost_sensitivity").stem,
                    "costs",
                    "Ratio de Sharpe net en fonction du multiple appliqué aux dix points de base.",
                )
            )

            fig, _ = viz.subperiod_bars(
                subperiods,
                metric_column="sharpe",
                error_column="sharpe_se_lo",
                title="Ratio de Sharpe de l'écart couvert par sous-période",
            )
            figure_specs.append(
                (
                    _save_figure(fig, "subperiod_bars").stem,
                    "robustness",
                    "Ratio de Sharpe annualisé et son intervalle à 95 pour cent, par sous-période.",
                )
            )

            heatmap_source = sweep_frame.copy()
            heatmap_source["leverage_cap_label"] = heatmap_source["leverage_cap"].map(
                lambda c: "aucun" if c == 0.0 else f"{c:g}"
            )
            fig, _ = viz.parameter_heatmap(
                heatmap_source,
                x="leverage_cap_label",
                y="estimator",
                metric="net_sharpe",
                x_label="Plafond de levier",
                y_label="Mesure de variance",
                metric_label="Ratio de Sharpe net",
                title="Ratio de Sharpe net de l'écart couvert selon la mesure de variance et le plafond",
            )
            figure_specs.append(
                (
                    _save_figure(fig, "parameter_heatmap").stem,
                    "robustness",
                    "Une case par couple de réglages, ratio de Sharpe net de dix points de base.",
                )
            )

            correlation_source = pd.DataFrame(
                {
                    "Marché": base_market,
                    "Géré ex post": managed_full["MKT-RF"].returns,
                    "Géré en temps réel": live_market.returns,
                    "Écart couvert": spread_live,
                }
            ).dropna()
            fig, _ = viz.correlation_heatmap(
                correlation_source,
                title="Corrélations mensuelles entre le marché et ses versions gérées",
            )
            figure_specs.append(
                (
                    _save_figure(fig, "correlation_heatmap").stem,
                    "factor_attribution",
                    "Corrélations de Pearson sur les mois communs aux quatre séries.",
                )
            )

            fig, _ = viz.return_histogram(
                live_market.returns,
                title="Distribution mensuelle du marché géré, constante en temps réel",
            )
            figure_specs.append(
                (
                    _save_figure(fig, "return_histogram").stem,
                    "statistical_tests",
                    "Histogramme des rendements mensuels et loi normale de même moyenne.",
                )
            )

            fig, _ = viz.qq_plot(
                spread_live,
                title="Quantiles de l'écart couvert contre quantiles normaux",
            )
            figure_specs.append(
                (
                    _save_figure(fig, "qq_plot_spread").stem,
                    "statistical_tests",
                    "Écart à la normalité des rendements mensuels de l'écart couvert.",
                )
            )

        # ------------------------------------------------------------------ #
        # 10. Le verdict
        # ------------------------------------------------------------------ #
        alpha_checks = tuple(
            ReplicationCheck(
                quantity=f"alpha annualisé, {FACTOR_LABELS[name]}",
                published=PAPER_TABLE_1[name]["alpha"],
                ours=float(
                    replication_frame.loc[
                        replication_frame["factor"] == FACTOR_LABELS[name], "alpha_annual_pct"
                    ].iloc[0]
                ),
                tolerance=float(params["verdict"]["replication_tolerance"]),
                source="Moreira et Muir (2016), NBER 22208, tableau 1, panneau A",
            )
            for name in ("MKT-RF", "MOM", "RMW", "ROE", "IA")
        )
        checks = (
            *alpha_checks,
            ReplicationCheck(
                quantity="nombre de mois du marché",
                published=float(PAPER_TABLE_1["MKT-RF"]["n"]),
                ours=float(market_fit.n_observations),
                tolerance=0.0,
                tolerance_kind="absolute",
                source="Moreira et Muir (2016), NBER 22208, tableau 1, panneau A",
                note="Retrouvé exactement en arrêtant l'échantillon en avril 2015.",
            ),
            ReplicationCheck(
                quantity="bêta du marché géré",
                published=PAPER_TABLE_1["MKT-RF"]["beta"],
                ours=market_fit.beta,
                tolerance=float(params["verdict"]["replication_tolerance"]),
                source="Moreira et Muir (2016), NBER 22208, tableau 1, panneau A",
            ),
            ReplicationCheck(
                quantity="erreur type de l'alpha du marché",
                published=PAPER_TABLE_1["MKT-RF"]["stderr"],
                ours=market_fit.alpha_stderr_annual * 100.0,
                tolerance=float(params["verdict"]["replication_tolerance"]),
                source="Moreira et Muir (2016), NBER 22208, tableau 1, panneau A",
            ),
        )
        _write_table(replication_table(checks), "replication_checks")

        criteria = VerdictCriteria(**params["verdict"])
        positive_share = float((subperiods["sharpe"] > 0.0).mean())
        evidence = VerdictEvidence(
            hypothesis_supported=bool(market_fit.alpha_annual > 0.0),
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
            portfolio_correlation=float(spread_live.corr(base_market.loc[spread_live.index])),
            notes=(
                "L'alpha en échantillon est répliqué. Le hors échantillon porte sur l'écart couvert "
                "en temps réel, net de dix points de base."
            ),
        )
        verdict, reasons = decide_verdict(evidence, criteria)
        run.set_verdict(verdict)

        metric_values = {
            "alpha_marche_in_sample_pct": market_fit.alpha_annual * 100.0,
            "tstat_alpha_marche_in_sample": market_fit.alpha_tstat,
            "appraisal_marche_in_sample": market_fit.appraisal_ratio,
            "alpha_marche_temps_reel_pct": float(
                constant_frame.loc[constant_frame["factor"] == "Marché", "alpha_real_time_pct"].iloc[0]
            ),
            "tstat_alpha_marche_temps_reel": float(
                constant_frame.loc[constant_frame["factor"] == "Marché", "tstat_real_time"].iloc[0]
            ),
            "appraisal_marche_temps_reel": float(
                constant_frame.loc[constant_frame["factor"] == "Marché", "appraisal_real_time"].iloc[0]
            ),
            "sharpe_ecart_couvert_oos_net": oos_sharpe,
            "sharpe_ecart_couvert_complet_net": sharpe_ratio(oos, frequency=monthly),
            "rotation_annualisee": annual_rotation,
            "cout_de_rentabilite_bps": breakeven,
            "probabilite_de_surapprentissage": pbo_result.pbo,
            "sharpe_degonfle": deflated_value,
            "t_apres_correction": adjusted_tstat,
            "part_de_sous_periodes_positives": positive_share,
            "correlation_avec_le_marche": evidence.portfolio_correlation or float("nan"),
            "cpcv_sharpe_moyen": float(distribution.summary["mean"]),
            "cpcv_part_de_chemins_negatifs": float(distribution.negative_share),
        }
        labels = {
            "alpha_marche_in_sample_pct": MetricLabel(SampleTag.IN_SAMPLE, CostBasis.GROSS),
            "tstat_alpha_marche_in_sample": MetricLabel(SampleTag.IN_SAMPLE, CostBasis.GROSS),
            "appraisal_marche_in_sample": MetricLabel(SampleTag.IN_SAMPLE, CostBasis.GROSS),
            "alpha_marche_temps_reel_pct": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "tstat_alpha_marche_temps_reel": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "appraisal_marche_temps_reel": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "sharpe_ecart_couvert_oos_net": MetricLabel(SampleTag.OUT_OF_SAMPLE, CostBasis.NET),
            "sharpe_ecart_couvert_complet_net": MetricLabel(SampleTag.VALIDATION, CostBasis.NET),
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
            "study": "006_volatility_managed",
            "experiment_id": run.record.experiment_id,
            "seed": config.seed,
            "verdict": verdict.value,
            "reasons": reasons,
            "n_trials": n_trials,
            "trials_by_family": {family: counter.n_trials(family) for family in counter.families()},
            "metrics": metric_values,
            "metric_samples": {name: label.sample.value for name, label in labels.items()},
            "cost_basis": {name: label.cost_basis.value for name, label in labels.items()},
            "samples": {
                "paper_window": ["1926-08-31", str(paper_end.date())],
                "full_window": ["1926-08-31", str(full_end.date())],
                "real_time_window": [
                    str(live_market.returns.index[0].date()),
                    str(live_market.returns.index[-1].date()),
                ],
                "holdout_window": [str(holdout.index[0].date()), str(holdout.index[-1].date())],
            },
            "cost_assumptions_bps": {"spread_bps": config.costs.spread_bps},
            "data_sha256": {
                "global_q_daily": global_q["daily_sha256"],
                "global_q_monthly": global_q["monthly_sha256"],
            },
        }
        (RESULTS / "metrics.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        report_tables = [
            ReportTable("replication_table1", "replication", replication_frame, "Tableau 1, panneau A."),
            ReportTable("front1_end_date", "data", end_date_table, "Le compte de mois par date de fin."),
            ReportTable("factor_coverage", "data", coverage, "Les neuf facteurs et leur source."),
            ReportTable(
                "front3_constant",
                "out_of_sample",
                constant_frame,
                "Constante ex post contre temps réel.",
            ),
            ReportTable(
                "front3_combination",
                "out_of_sample",
                combination_frame,
                "Combinaison moyenne-variance.",
            ),
            ReportTable("costs", "costs", cost_frame, "Coûts et rendement net."),
            ReportTable(
                "hedge_sensitivity",
                "costs",
                hedge_frame,
                "Ce que coûte le bêta de couverture estimé sur le passé.",
            ),
            ReportTable("parameter_sweep", "robustness", sweep_frame, "Balayage des réglages."),
            ReportTable("subperiods", "robustness", subperiods, "Sous-périodes."),
            ReportTable(
                "cpcv_distribution",
                "out_of_sample",
                cpcv_frame,
                "Validation croisée combinatoire purgée, sept chemins.",
            ),
            ReportTable("multiple_testing", "statistical_tests", multiple_frame, "Correction de Holm."),
            ReportTable("trials", "statistical_tests", trials_frame, "Le compte des essais."),
        ]
        report_figures = [
            ReportFigure(name, section, FIGURES / f"{name}.png", caption)
            for name, section, caption in figure_specs
        ]
        report = StudyReport(
            study_name="006_volatility_managed",
            experiment_id=run.record.experiment_id,
            hypothesis=config.hypothesis,
            paper=config.paper or "",
            criteria=criteria,
            evidence=evidence,
            sections=_sections(metric_values, market_fit, constant_frame, oos_sharpe),
            metrics=metrics,
            tables=report_tables,
            figures=report_figures,
            config=config.model_dump(mode="json"),
            dataset_manifests=manifests,
        )
        generate_report(STUDY_DIR, report)
        run.log_artifact(str(RESULTS))

        alpha_registry = AlphaRegistry()
        alpha_registry.register(
            AlphaMetadata(
                name="volatility_managed_market",
                family="timing",
                paper=config.paper,
                asset_classes=[AssetClass.EQUITY_INDEX],
                horizon="formation sur un mois de séances, détention un mois",
                economic_rationale=["prime de risque", "friction"],
                inputs=[
                    "rendements quotidiens du facteur, bibliothèque de Kenneth French",
                    "rendements mensuels du facteur, même bibliothèque",
                ],
                known_risks=[
                    "La constante de mise à l'échelle emploie l'écart type de plein échantillon.",
                    "Le levier exigé dépasse deux plusieurs mois sur cent.",
                    "La rotation mensuelle rend la stratégie sensible aux frais.",
                ],
                validation_status=verdict,
                verdict_experiment_id=run.record.experiment_id,
                created=pd.Timestamp.today().date(),
                last_modified=pd.Timestamp.today().date(),
                notes=(
                    "Étude 006. Le mécanisme invoqué est une prime de risque dont le prix, le "
                    "rapport du rendement attendu à la variance, baisse quand la variance monte. "
                    "La variance se prévoit bien mieux à un mois que le rendement attendu, et "
                    "c'est cet écart de prévisibilité qui produit l'alpha en échantillon. La "
                    "friction retenue est le coût de rotation d'un levier qui change tous les "
                    "mois. Le verdict est déduit par quantlab.reporting.study.decide_verdict."
                ),
            ),
            overwrite=True,
        )
        LOG.info("étude terminée", extra={"verdict": verdict.value, "n_trials": n_trials})


def _sections(
    metric_values: Mapping[str, float],
    market_fit: Any,
    constant_frame: pd.DataFrame,
    oos_sharpe: float,
) -> dict[str, str]:
    """Rend la prose des quinze sections du rapport HTML."""
    real_time_alpha = float(
        constant_frame.loc[constant_frame["factor"] == "Marché", "alpha_real_time_pct"].iloc[0]
    )
    return {
        "hypothesis": (
            "Gérer un facteur par sa volatilité passée crée-t-il de l'alpha, ou seulement "
            "l'illusion qu'en donne une constante de calibrage choisie après coup ?"
        ),
        "paper": (
            "Moreira et Muir (2017), Volatility-Managed Portfolios, Journal of Finance 72(4). "
            "Les chiffres cibles viennent du document de travail NBER 22208 d'avril 2016."
        ),
        "methodology": (
            "Le facteur est multiplié par l'inverse de sa variance réalisée du mois précédent, "
            "puis mis à l'échelle par une constante. Le test est une régression du facteur géré "
            "sur le facteur d'origine, et l'ordonnée à l'origine est lue comme un alpha."
        ),
        "data": (
            "Six facteurs viennent de la bibliothèque de Kenneth French, en quotidien et en "
            "mensuel. Deux viennent de global-q.org. Le portage de change n'est pas publié en "
            "quotidien, donc il est déclaré non trouvé."
        ),
        "implementation": (
            "La stratégie vit dans quantlab.strategies.volatility_managed. La variance porte la "
            "date du mois qui la produit, et le décalage d'un mois se fait en un seul endroit."
        ),
        "assumptions": (
            "Le facteur est autofinancé, donc le levier ne coûte rien de plus que la rotation. "
            "Les rendements quotidiens sont supposés non corrélés à l'intérieur du mois."
        ),
        "replication": (
            f"L'alpha du marché ressort à {market_fit.alpha_annual * 100.0:.2f} pour cent par an "
            f"contre 4,86 publié, sur {market_fit.n_observations} mois contre 1 065 publiés."
        ),
        "performance": (
            "Tous les chiffres portent leur échantillon et leur base de coût dans le tableau ci-dessous."
        ),
        "costs": (
            f"La rotation annualisée vaut {metric_values['rotation_annualisee']:.2f} et le coût "
            f"qui annule le rendement brut vaut {metric_values['cout_de_rentabilite_bps']:.0f} "
            "points de base."
        ),
        "robustness": (
            "La mesure de variance, le plafond de levier, la fenêtre de la constante et le délai "
            "d'exécution sont balayés, et chaque cellule compte comme un essai."
        ),
        "out_of_sample": (
            f"Avec une constante estimée sur le seul passé, l'alpha du marché passe de "
            f"{market_fit.alpha_annual * 100.0:.2f} à {real_time_alpha:.2f} pour cent par an. "
            f"Le Sharpe hors échantillon de l'écart couvert net vaut {oos_sharpe:.2f}."
        ),
        "statistical_tests": (
            "Le ratio de Sharpe dégonflé, la probabilité de surapprentissage et la correction de "
            "Holm sur les huit facteurs sont rapportés dans les tableaux joints."
        ),
        "factor_attribution": (
            "La corrélation de l'écart couvert avec le marché est celle d'une série construite "
            "pour être orthogonale au passé, et elle est publiée dans les métriques."
        ),
        "limitations": (
            "Le portage de change manque. Les facteurs q sont d'un millésime plus récent que "
            "celui de l'article. Aucun coût de financement du levier n'est retranché."
        ),
        "verdict": "Le verdict est déduit des seuils écrits dans config.yaml, sans arbitrage.",
    }


if __name__ == "__main__":
    main()

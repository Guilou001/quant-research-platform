"""Étude 011 : un ensemble d'arbres ordonne-t-il les rendements mieux qu'une régression, après coûts ?

Le point d'entrée ne porte aucune logique réutilisable : il assemble les briques
de ``quantlab.models`` sur le panneau point-in-time de l'étude 004 et écrit ses
résultats dans ``results/``. Il est déterministe et sort sur le réseau pour le
seul taux sans risque de Kenneth French.

    uv run python studies/011_cross_sectional_ml/run.py
"""

from __future__ import annotations

import json
import math
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import polars as pl
import yaml

from quantlab.analytics.drawdown import max_drawdown
from quantlab.analytics.ic import ic_series, ic_summary
from quantlab.analytics.ratios import sharpe_ratio, sharpe_standard_error
from quantlab.analytics.risk import kurtosis, skewness
from quantlab.analytics.visualization.figures import equity_curve, save_figure
from quantlab.backtest.engine import run_backtest
from quantlab.core.logging import configure_logging, get_logger, stage
from quantlab.core.types import CostBasis, Frequency, SampleTag
from quantlab.data.providers.french import FrenchProvider
from quantlab.execution.costs import LinearCostModel
from quantlab.experiments import ExperimentRegistry
from quantlab.models.cross_sectional import permutation_importance, spec_from_config, walk_forward_predict
from quantlab.models.evaluation import (
    diebold_mariano,
    oos_r2,
    predictions_to_wide,
    r2_by_date,
    squared_errors,
)
from quantlab.models.panel import DATE_LEVEL, ENTITY_LEVEL, Panel, make_panel, price_features
from quantlab.reporting.series import load_series, save_series
from quantlab.reporting.study import ReplicationCheck, VerdictCriteria, VerdictEvidence, decide_verdict
from quantlab.signals.standardize import signal_to_weights
from quantlab.validation.dsr import deflated_sharpe_ratio
from quantlab.validation.pbo import probability_of_backtest_overfitting
from quantlab.validation.robustness import subperiod_performance
from quantlab.validation.splits import ExpandingSplit

warnings.filterwarnings("ignore", category=FutureWarning, module="pandas")
STUDY_DIR = Path(__file__).resolve().parent
ROOT = STUDY_DIR.parents[1]
RESULTS = STUDY_DIR / "results"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"
MONTHLY = Frequency.MONTHLY
LOG = get_logger("study.011")


def _write_table(frame: pd.DataFrame, name: str) -> None:
    frame.to_csv(TABLES / f"{name}.csv", float_format="%.10g")


def _month_end(index: pd.Index) -> pd.DatetimeIndex:
    """Ramène des dates à la fin de mois civile, pour apparier des sources différentes."""
    return pd.DatetimeIndex(pd.to_datetime(index)).to_period("M").to_timestamp("M")


def load_panel(config: dict[str, Any]) -> tuple[Panel, pd.DataFrame, dict[str, Any]]:
    """Assemble le panneau depuis le cache de l'étude 004 et le taux sans risque de Kenneth French."""
    cache = ROOT / config["data"]["feature_cache"]
    if not (cache / "variables.parquet").exists():
        raise FileNotFoundError(f"cache de caractéristiques absent : {cache}. Lancer l'étude 004 d'abord.")
    variables = pl.read_parquet(cache / "variables.parquet").to_pandas()
    variables[ENTITY_LEVEL] = variables["entity_id"].astype(int).astype(str)
    variables[DATE_LEVEL] = _month_end(variables["as_of"])
    accounting = (
        variables.drop(columns=["entity_id", "as_of"]).set_index([DATE_LEVEL, ENTITY_LEVEL]).sort_index()
    )
    accounting = accounting[~accounting.index.duplicated(keep="last")]

    equity = pl.read_parquet(cache / "equity.parquet").to_pandas().set_index("as_of")
    equity.index = _month_end(equity.index)
    returns = pl.read_parquet(cache / "returns.parquet").to_pandas().set_index("date")
    returns.index = _month_end(returns.index)
    returns = returns.sort_index()

    french = FrenchProvider()
    factors = french.benchmark_factors(frequency=MONTHLY, start=config["data"]["risk_free_start"])
    rf = factors["RF"]
    rf.index = _month_end(rf.index)
    rf = rf.reindex(returns.index)
    if bool(rf.isna().any()):
        missing = rf.index[rf.isna()]
        raise ValueError(f"taux sans risque manquant sur {len(missing)} mois, dont {missing[0].date()}.")
    excess = returns.sub(rf, axis=0)

    prices = price_features(returns, equity)
    features = accounting.join(prices, how="left")
    counts = features.groupby(level=DATE_LEVEL).size()
    keep_dates = counts.index[counts >= int(config["data"]["min_names_per_date"])]
    features = features[features.index.get_level_values(DATE_LEVEL).isin(keep_dates)]
    panel = make_panel(features, excess)
    coverage = {
        "n_dates": len(panel.dates),
        "first_date": str(panel.dates.min().date()),
        "last_date": str(panel.dates.max().date()),
        "n_entities": int(panel.features.index.get_level_values(ENTITY_LEVEL).nunique()),
        "n_rows": len(panel.features),
        "n_labelled": int(panel.label.notna().sum()),
        "n_features": int(panel.features.shape[1]),
        "features": list(panel.feature_names),
        "mean_names_per_date": float(counts.loc[keep_dates].mean()),
        "manifest": french.manifest("F-F_Research_Data_Factors").model_dump(mode="json"),
    }
    return panel, excess, coverage


def _describe(s: pd.Series, label: str) -> dict[str, Any]:
    se = sharpe_standard_error(s, frequency=MONTHLY)
    return {
        "series": label,
        "n_months": len(s),
        "start": str(s.index.min().date()),
        "end": str(s.index.max().date()),
        "return_annual_pct": float(((1 + s).prod() ** (12 / len(s)) - 1) * 100),
        "volatility_annual_pct": float(s.std(ddof=1) * np.sqrt(12) * 100),
        "sharpe": float(sharpe_ratio(s, frequency=MONTHLY)),
        "sharpe_se_lo": float(se.lo),
        "max_drawdown_pct": float(max_drawdown(s) * 100),
    }


def _decile_backtest(
    pred_wide: pd.DataFrame, excess: pd.DataFrame, cfg: dict[str, Any], cost_bps: float
) -> Any:
    """Rejoue le portefeuille décile long moins court d'un modèle, décalé d'un mois."""
    weights = signal_to_weights(
        pred_wide,
        method="equal_long_short",
        n_quantiles=int(cfg["n_quantiles"]),
        target_gross=float(cfg["target_gross"]),
    )
    returns = excess.reindex(index=weights.index.union(excess.index), columns=weights.columns).fillna(0.0)
    returns = returns.loc[weights.index.min() :]
    model = LinearCostModel(spread_bps=cost_bps) if cost_bps > 0 else None
    return run_backtest(
        weights=weights, returns=returns, cost_model=model, execution_lag=1, frequency=MONTHLY
    )


def main() -> None:
    configure_logging("INFO")
    config = yaml.safe_load((STUDY_DIR / "config.yaml").read_text(encoding="utf-8"))
    for d in (RESULTS, TABLES, FIGURES):
        d.mkdir(parents=True, exist_ok=True)
    seed = int(config["seed"])
    wf = config["walk_forward"]
    pcfg = config["portfolio"]
    reference = str(config["models"]["reference"])
    challenger = str(config["models"]["challenger"])
    metrics: dict[str, Any] = {
        "n_trials": int(config["n_trials"]),
        "reference": reference,
        "challenger": challenger,
    }

    with stage("chargement"):
        panel, excess, coverage = load_panel(config)
        metrics["coverage"] = coverage
        LOG.info("panneau", extra={"n_rows": coverage["n_rows"], "n_dates": coverage["n_dates"]})

    split = ExpandingSplit(
        train_size=int(wf["train_months"]), test_size=int(wf["test_months"]), purge=int(wf["purge_months"])
    )
    realized = panel.label
    outputs: dict[str, Any] = {}
    fold_rows: list[pd.DataFrame] = []
    with stage("modeles"):
        for name, grid in config["models"]["grids"].items():
            spec = spec_from_config(name, grid, seed=seed)
            out = walk_forward_predict(panel, spec, split, validation_periods=int(wf["validation_months"]))
            outputs[name] = out
            report = out.report()
            report.insert(0, "model", name)
            fold_rows.append(report)
            LOG.info("modèle prévu", extra={"model": name, "n_folds": len(out.folds)})
    folds = pd.concat(fold_rows)
    _write_table(folds, "folds")
    metrics["n_folds"] = len(outputs[reference].folds)
    metrics["test_window"] = {
        "start": str(outputs[reference].folds[0].test_start.date()),
        "end": str(outputs[reference].folds[-1].test_end.date()),
    }

    with stage("evaluation"):
        rows = []
        losses: dict[str, pd.Series] = {}
        ic_tables = {}
        for name, out in outputs.items():
            y = realized.reindex(out.predictions.index)
            r2 = oos_r2(y, out.predictions)
            losses[name] = squared_errors(y, out.predictions)
            pred_wide = predictions_to_wide(out.predictions)
            real_wide = predictions_to_wide(y.rename(name))
            ic = ic_series(pred_wide, real_wide)
            summary = ic_summary(ic, frequency=MONTHLY)
            ic_tables[name] = ic
            by_date = r2_by_date(y, out.predictions)
            rows.append(
                {
                    "model": name,
                    "family": out.family,
                    "n_configs": out.n_configs,
                    "r2_oos_pct": r2 * 100.0,
                    "r2_oos_median_by_date_pct": float(by_date.median() * 100.0),
                    "share_dates_r2_positive": float((by_date > 0).mean()),
                    "ic_mean": summary.mean,
                    "ic_t_hac": summary.t_stat_hac,
                    "ic_hit_rate": summary.hit_rate,
                    "chosen_configs": "; ".join(sorted({str(f.config) for f in out.folds})),
                }
            )
        evaluation = pd.DataFrame(rows).set_index("model")
        _write_table(evaluation, "evaluation")
        _write_table(pd.DataFrame(ic_tables), "ic_by_month")
        dm_rows = []
        for name in outputs:
            if name == reference:
                continue
            dm = diebold_mariano(losses[reference], losses[name])
            dm_rows.append(
                {
                    "model": name,
                    "against": reference,
                    "dm_statistic": dm.statistic,
                    "dm_pvalue": dm.pvalue,
                    "mean_loss_difference": dm.mean_difference,
                    "n_months": dm.n_periods,
                    "lags": dm.lags,
                }
            )
        dm_table = pd.DataFrame(dm_rows).set_index("model")
        _write_table(dm_table, "diebold_mariano")
        metrics["evaluation"] = evaluation.to_dict(orient="index")
        metrics["diebold_mariano"] = dm_table.to_dict(orient="index")

    with stage("portefeuilles"):
        net: dict[str, pd.Series] = {}
        port_rows = []
        cost_bps = float(pcfg["spread_bps"])
        universe_note = (
            f"{coverage['n_entities']} grandes capitalisations américaines du panneau point-in-time de "
            "l'étude 004, biais de survie déclaré, déciles long moins court"
        )
        for name, out in outputs.items():
            result = _decile_backtest(predictions_to_wide(out.predictions), excess, pcfg, cost_bps)
            gross = result.gross_returns.iloc[1:]
            net_series = result.net_returns.iloc[1:]
            net[name] = net_series
            row = _describe(net_series, name)
            row["sharpe_gross"] = float(sharpe_ratio(gross, frequency=MONTHLY))
            row["turnover_annual"] = float(result.turnover.mean() * 12)
            port_rows.append(row)
            save_series(
                RESULTS,
                f"ml_{name}_decile_gross",
                gross,
                sample=SampleTag.OUT_OF_SAMPLE,
                basis=CostBasis.GROSS,
                frequency=MONTHLY,
                universe=universe_note,
            )
            save_series(
                RESULTS,
                f"ml_{name}_decile_net",
                net_series,
                sample=SampleTag.OUT_OF_SAMPLE,
                basis=CostBasis.NET,
                frequency=MONTHLY,
                universe=universe_note,
                cost_assumptions=f"{cost_bps} pb par unité négociée",
            )
        portfolios = pd.DataFrame(port_rows).set_index("series")
        _write_table(portfolios, "portfolios")
        metrics["portfolios"] = portfolios.to_dict(orient="index")
        fig, _ = equity_curve(
            {name: s for name, s in net.items()},
            title=(
                f"Déciles long moins court de {len(net)} modèles, nets de {cost_bps:g} pb, "
                f"{metrics['test_window']['start'][:4]}-{metrics['test_window']['end'][:4]}"
            ),
            currency="$ US",
        )
        save_figure(fig, FIGURES / "equity_decile_net.png")

    with stage("couts"):
        cost_rows = []
        surviving = 0.0
        pred_ch = predictions_to_wide(outputs[challenger].predictions)
        for multiple in pcfg["cost_multiples"]:
            res = _decile_backtest(pred_ch, excess, pcfg, cost_bps * float(multiple)).net_returns.iloc[1:]
            sr = float(sharpe_ratio(res, frequency=MONTHLY))
            cost_rows.append(
                {"multiple": float(multiple), "cost_bps": cost_bps * float(multiple), "sharpe_net": sr}
            )
            if sr > 0:
                surviving = float(multiple)
        _write_table(pd.DataFrame(cost_rows).set_index("multiple"), "cost_multiples")
        metrics["surviving_cost_multiple"] = surviving

    with stage("importance"):
        out = outputs[challenger]
        last = out.folds[-1]
        last_dates = panel.dates[(panel.dates >= last.test_start) & (panel.dates <= last.test_end)]
        rows_last = panel.rows_at(last_dates)
        importance = permutation_importance(
            out.last_model,
            panel.features.iloc[rows_last],
            panel.label.iloc[rows_last],
            seed=seed,
            n_repeats=int(config["importance"]["n_repeats"]),
        )
        _write_table(importance, "importance_challenger_last_fold")
        metrics["importance_top5"] = importance.head(5)["importance"].to_dict()

    with stage("validation"):
        s = net[challenger]
        matrix = pd.DataFrame(net).dropna()
        pbo = probability_of_backtest_overfitting(matrix, n_splits=8, frequency=MONTHLY)
        sharpes_monthly = np.array(
            [sharpe_ratio(v, frequency=MONTHLY, annualize=False) for v in net.values()]
        )
        dsr = deflated_sharpe_ratio(
            observed_sr=float(sharpe_ratio(s, frequency=MONTHLY, annualize=False)),
            sharpe_variance_across_trials=float(sharpes_monthly.var(ddof=1)),
            n_trials=int(config["n_trials"]),
            n_obs=float(len(s)),
            skew=float(skewness(s)),
            kurtosis=float(kurtosis(s, excess=False)),
        )
        sub = subperiod_performance(s, n_periods=int(pcfg["subperiods"]), frequency=MONTHLY)
        _write_table(sub, "subperiods_challenger")
        share_positive = float((sub["sharpe"] > 0).mean()) if "sharpe" in sub.columns else math.nan
        se = sharpe_standard_error(s, frequency=MONTHLY)
        try:
            rp = load_series(ROOT / "studies" / "009_multi_strategy" / "results", "portfolio_risk_parity_net")
            common = pd.concat([s.rename("ml"), rp.rename("rp")], axis=1, join="inner").dropna()
            corr_009 = float(common["ml"].corr(common["rp"])) if len(common) > 12 else math.nan
        except FileNotFoundError:
            corr_009 = math.nan
        metrics["validation"] = {
            "challenger_sharpe_net": float(sharpe_ratio(s, frequency=MONTHLY)),
            "challenger_tstat": float(sharpe_ratio(s, frequency=MONTHLY) / se.lo),
            "reference_sharpe_net": float(sharpe_ratio(net[reference], frequency=MONTHLY)),
            "pbo": float(pbo.pbo),
            "deflated_sharpe": float(dsr),
            "positive_subperiod_share": share_positive,
            "correlation_with_009_risk_parity": corr_009,
            "n_oos_months": len(s),
        }

    with stage("verdict"):
        crit = VerdictCriteria(**{k: v for k, v in config["verdict"].items() if k != "dm_pvalue_max"})
        tree_r2 = max(
            float(evaluation.loc[m, "r2_oos_pct"])
            for m in evaluation.index
            if evaluation.loc[m, "family"] == "tree"
        )
        checks = (
            ReplicationCheck(
                "r2_oos_mensuel_arbres_pct",
                published=float(config["replication"]["target_r2_pct"]),
                ours=tree_r2,
                tolerance=float(config["replication"]["tolerance_pct_points"]),
                tolerance_kind="absolute",
                source=(
                    "Gu, Kelly et Xiu (2020), table 1, forêt aléatoire, mille plus grandes capitalisations"
                ),
                note="fenêtre 2020-2026 contre 1987-2016, 27 variables contre 94",
            ),
        )
        dm_ch = metrics["diebold_mariano"][challenger]
        beats = (
            dm_ch["dm_statistic"] > 0
            and dm_ch["dm_pvalue"] <= float(config["verdict"]["dm_pvalue_max"])
            and metrics["validation"]["challenger_sharpe_net"] > metrics["validation"]["reference_sharpe_net"]
        )
        evidence = VerdictEvidence(
            hypothesis_supported=bool(beats),
            replication_checks=checks,
            oos_sharpe=metrics["validation"]["challenger_sharpe_net"],
            tstat_after_multiplicity=metrics["validation"]["challenger_tstat"],
            deflated_sharpe=metrics["validation"]["deflated_sharpe"],
            pbo=metrics["validation"]["pbo"],
            positive_subperiod_share=share_positive,
            surviving_cost_multiple=metrics["surviving_cost_multiple"],
            portfolio_correlation=corr_009 if math.isfinite(corr_009) else None,
            notes=(
                "prévisions hors échantillon en marche avant, hyperparamètres réglés sur la fin de "
                "l'entraînement"
            ),
        )
        verdict, reasons = decide_verdict(evidence, crit)
        metrics["hypothesis_supported"] = bool(beats)
        metrics["verdict"] = verdict.value
        metrics["verdict_reasons"] = reasons
        pd.DataFrame({"reason": reasons}).to_csv(TABLES / "verdict_reasons.csv", index=False)

    (RESULTS / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    with ExperimentRegistry().run(
        name="cross_sectional_ml_011",
        hypothesis=config["hypothesis"],
        config={k: v for k, v in config.items() if k != "verdict"},
        seed=seed,
        universe=[f"panneau 004, {coverage['n_entities']} sociétés"],
        date_start=metrics["test_window"]["start"],
        date_end=metrics["test_window"]["end"],
        cost_basis=CostBasis.NET,
        cost_assumptions={"spread_bps": cost_bps},
        n_trials=int(config["n_trials"]),
    ) as run:
        run.log_metric(
            "challenger_sharpe_net",
            metrics["validation"]["challenger_sharpe_net"],
            sample=SampleTag.OUT_OF_SAMPLE,
        )
        run.log_metric(
            "challenger_r2_oos_pct",
            float(evaluation.loc[challenger, "r2_oos_pct"]),
            sample=SampleTag.OUT_OF_SAMPLE,
        )
        run.set_verdict(verdict)
    LOG.info("étude terminée", extra={"verdict": verdict.value})


if __name__ == "__main__":
    main()

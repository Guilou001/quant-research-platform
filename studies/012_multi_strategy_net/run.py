"""Étude 012 : le portefeuille de l'étude 009 sur les séries NETTES de chaque stratégie.

Le point d'entrée ne porte aucune logique réutilisable : il assemble les briques
de ``quantlab`` et écrit ses résultats dans ``results/``. Il est déterministe.

    uv run python studies/012_multi_strategy_net/run.py
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from quantlab.analytics.comparison import compare_trajectories, fund_returns_from_prices
from quantlab.analytics.drawdown import max_drawdown
from quantlab.analytics.ic import effective_breadth
from quantlab.analytics.ratios import sharpe_ratio, sharpe_standard_error
from quantlab.analytics.returns import resample_returns
from quantlab.analytics.risk import kurtosis, skewness
from quantlab.analytics.visualization.figures import correlation_heatmap, equity_curve, save_figure
from quantlab.backtest.engine import run_backtest
from quantlab.core.logging import configure_logging, get_logger, stage
from quantlab.core.types import CostBasis, Frequency, ReturnKind, SampleTag
from quantlab.data.providers.yahoo import YahooProvider, to_wide
from quantlab.execution.costs import LinearCostModel
from quantlab.experiments import ExperimentRegistry
from quantlab.portfolio.covariance import LedoitWolfCovariance
from quantlab.portfolio.optimizers import (
    EqualWeight,
    HierarchicalRiskParity,
    InverseVolatility,
    MeanVarianceWithCosts,
    MinimumVariance,
    RiskParity,
)
from quantlab.reporting.series import load_series, save_series
from quantlab.reporting.study import ReplicationCheck, VerdictCriteria, VerdictEvidence, decide_verdict
from quantlab.validation.dsr import deflated_sharpe_ratio
from quantlab.validation.pbo import probability_of_backtest_overfitting
from quantlab.validation.robustness import subperiod_performance

warnings.filterwarnings("ignore", category=FutureWarning, module="pandas")
STUDY_DIR = Path(__file__).resolve().parent
ROOT = STUDY_DIR.parents[1]
RESULTS = STUDY_DIR / "results"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"
MONTHLY = Frequency.MONTHLY
LOG = get_logger("study.012")


def _write_table(frame: pd.DataFrame, name: str) -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    frame.to_csv(TABLES / f"{name}.csv")


def _load_inputs(config: dict[str, Any]) -> pd.DataFrame:
    """Charge les huit séries de tête, les passe en mensuel et les aligne sur leur fenêtre commune."""
    columns: dict[str, pd.Series] = {}
    for key, spec in config["series"].items():
        s = load_series(ROOT / "studies" / spec["study"] / "results", spec["name"])
        if s.index.to_series().diff().median() < pd.Timedelta(days=20):
            s = resample_returns(s, MONTHLY, ReturnKind.SIMPLE)
        s.index = s.index.to_period("M").to_timestamp("M")
        columns[key] = s.rename(key)
    frame = pd.DataFrame(columns).dropna(how="any")
    return frame


def _fit_weights(train: pd.DataFrame, name: str, config: dict[str, Any]) -> pd.Series:
    """Estime les poids d'un optimiseur sur la seule fenêtre passée."""
    cov = LedoitWolfCovariance().covariance(train)
    if name == "equal_weight":
        return EqualWeight().optimize(covariance=cov)
    if name == "inverse_volatility":
        return InverseVolatility().optimize(covariance=cov)
    if name == "risk_parity":
        return RiskParity().optimize(covariance=cov)
    if name == "minimum_variance":
        return MinimumVariance(max_weight=0.5).optimize(covariance=cov)
    if name == "hrp":
        return HierarchicalRiskParity().optimize(covariance=cov)
    if name == "mean_variance":
        mv = config["mean_variance"]
        # L'alpha attendu est la moyenne PASSÉE : c'est le test de DeMiguel et coauteurs.
        alpha = train.mean()
        return MeanVarianceWithCosts(
            risk_aversion=float(mv["risk_aversion"]),
            long_only=bool(mv["long_only"]),
            max_weight=float(mv["max_weight"]),
        ).optimize(alpha=alpha, covariance=cov)
    raise ValueError(f"optimiseur inconnu : {name}")


def _walk_forward(returns: pd.DataFrame, name: str, config: dict[str, Any], cost_bps: float) -> Any:
    """Poids réestimés tous les douze mois sur le passé seul, tenus entre deux estimations."""
    wf = config["walk_forward"]
    min_train, step = int(wf["min_train_months"]), int(wf["refit_every_months"])
    targets: dict[pd.Timestamp, pd.Series] = {}
    for start in range(min_train, len(returns), step):
        train = returns.iloc[:start]
        targets[returns.index[start - 1]] = _fit_weights(train, name, config)
    weights = pd.DataFrame(targets).T.reindex(returns.index)
    first = min(targets)
    return run_backtest(
        weights=weights.loc[first:],
        returns=returns.loc[first:],
        frequency=MONTHLY,
        execution_lag=1,
        cost_model=LinearCostModel(spread_bps=cost_bps),
    )


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
        "skewness": float(skewness(s)),
    }


def main() -> None:
    configure_logging("INFO")
    config = yaml.safe_load((STUDY_DIR / "config.yaml").read_text(encoding="utf-8"))
    for d in (RESULTS, TABLES, FIGURES):
        d.mkdir(parents=True, exist_ok=True)
    holdout_start = pd.Timestamp(config["final_holdout_start"])
    cost_bps = float(config["costs"]["spread_bps"])
    metrics: dict[str, Any] = {"n_trials": int(config["n_trials"])}

    with stage("chargement"):
        returns = _load_inputs(config)
        metrics["common_window"] = {
            "start": str(returns.index.min().date()),
            "end": str(returns.index.max().date()),
            "n_months": len(returns),
        }
        LOG.info("fenêtre commune", extra={"n": len(returns), "start": str(returns.index.min().date())})

    with stage("correlations"):
        corr = returns.corr()
        _write_table(corr, "correlation_matrix")
        breadth = float(effective_breadth(corr))
        upper = corr.where(np.triu(np.ones(corr.shape, dtype=bool), k=1))
        pairs = upper.stack()  # noqa: PD013 - une série indexée par paire est bien ce qu'on veut
        metrics["correlation"] = {
            "mean_pairwise": float(pairs.mean()),
            "min_pair": {"pair": " / ".join(pairs.idxmin()), "value": float(pairs.min())},
            "max_pair": {"pair": " / ".join(pairs.idxmax()), "value": float(pairs.max())},
            "effective_breadth": breadth,
            "n_strategies": int(returns.shape[1]),
        }
        fig, _ = correlation_heatmap(
            returns,
            title=(
                "Corrélations mensuelles de huit stratégies, "
                f"{returns.index.min().year}-{returns.index.max().year}"
            ),
        )
        save_figure(fig, FIGURES / "correlation_heatmap.png")

    with stage("chaque_strategie_seule"):
        alone = pd.DataFrame([_describe(returns[c], c) for c in returns.columns]).set_index("series")
        _write_table(alone, "strategies_alone")
        best_alone = alone["sharpe"].idxmax()
        metrics["best_alone"] = {"strategy": best_alone, "sharpe": float(alone.loc[best_alone, "sharpe"])}

    with stage("walk_forward"):
        oos: dict[str, pd.Series] = {}
        rows = []
        for name in config["optimizers"]:
            result = _walk_forward(returns, name, config, cost_bps)
            net = result.net_returns.dropna()
            oos[name] = net
            row = _describe(net, name)
            row["turnover_annual"] = float(result.turnover.mean() * 12)
            row["sharpe_before_holdout"] = float(
                sharpe_ratio(net.loc[net.index < holdout_start], frequency=MONTHLY)
            )
            row["sharpe_holdout"] = float(
                sharpe_ratio(net.loc[net.index >= holdout_start], frequency=MONTHLY)
            )
            rows.append(row)
            save_series(
                RESULTS,
                f"portfolio_{name}_net",
                net,
                sample=SampleTag.OUT_OF_SAMPLE,
                basis=CostBasis.NET,
                frequency=MONTHLY,
                universe="huit stratégies du laboratoire, poids réestimés chaque année sur le passé",
                cost_assumptions=f"{cost_bps} pb par unité de rotation",
            )
        portfolios = pd.DataFrame(rows).set_index("series")
        _write_table(portfolios, "portfolios_walk_forward")
        fig, _ = equity_curve(
            {k: v for k, v in oos.items()},
            currency="$ US",
            title="Richesse nette de six allocations, réestimées chaque année sur le seul passé",
        )
        save_figure(fig, FIGURES / "equity_portfolios.png")

    with stage("apport_marginal"):
        reference = "risk_parity"
        base = oos[reference]
        marginal_rows = []
        for dropped in returns.columns:
            sub = returns.drop(columns=[dropped])
            res = _walk_forward(sub, reference, config, cost_bps).net_returns.dropna()
            common = base.index.intersection(res.index)
            marginal_rows.append(
                {
                    "dropped": dropped,
                    "sharpe_with": float(sharpe_ratio(base.loc[common], frequency=MONTHLY)),
                    "sharpe_without": float(sharpe_ratio(res.loc[common], frequency=MONTHLY)),
                }
            )
        marginal = pd.DataFrame(marginal_rows).set_index("dropped")
        marginal["marginal_sharpe"] = marginal["sharpe_with"] - marginal["sharpe_without"]
        _write_table(marginal, "marginal_contribution")
        metrics["marginal"] = {k: float(v) for k, v in marginal["marginal_sharpe"].items()}

    with stage("multiple_de_couts"):
        # À quel multiple du coût supposé la référence meurt-elle ? La rotation
        # d'un portefeuille de stratégies rééquilibré chaque année est faible,
        # et le chiffre le dit plutôt que le supposer.
        cost_rows = []
        surviving = 0.0
        for multiple in (1.0, 2.0, 5.0, 10.0, 20.0):
            res = _walk_forward(returns, reference, config, cost_bps * multiple).net_returns.dropna()
            sr = float(sharpe_ratio(res, frequency=MONTHLY))
            cost_rows.append({"multiple": multiple, "cost_bps": cost_bps * multiple, "sharpe_net": sr})
            if sr > 0:
                surviving = multiple
        _write_table(pd.DataFrame(cost_rows).set_index("multiple"), "cost_multiples")
        metrics["surviving_cost_multiple"] = surviving

    with stage("repere_fonds"):
        ticker = config["benchmark_fund"]
        try:
            px = to_wide(
                YahooProvider().fetch([ticker], start="2013-01-01", end="2026-08-31"), field="adj_close"
            )
            fund = fund_returns_from_prices(px, frequency=MONTHLY)[ticker]
            fund.index = fund.index.to_period("M").to_timestamp("M")
            comp = compare_trajectories(
                oos[reference], fund, frequency=MONTHLY, strategy_name=reference, fund_name=ticker
            )
            metrics["benchmark_fund"] = comp.as_row()
            metrics["benchmark_fund"]["start"] = str(comp.start.date())
            metrics["benchmark_fund"]["end"] = str(comp.end.date())
            _write_table(pd.DataFrame([metrics["benchmark_fund"]]), "benchmark_fund")
        except Exception as exc:
            metrics["benchmark_fund"] = {"error": str(exc)}
            LOG.warning("repère de fonds indisponible", extra={"ticker": ticker, "error": str(exc)})

    with stage("validation"):
        s = oos[reference]
        before = s.loc[s.index < holdout_start]
        holdout = s.loc[s.index >= holdout_start]
        matrix = pd.DataFrame(oos).dropna()
        pbo = probability_of_backtest_overfitting(matrix, n_splits=8, frequency=MONTHLY)
        sharpes_monthly = np.array(
            [sharpe_ratio(v, frequency=MONTHLY, annualize=False) for v in oos.values()]
        )
        dsr = deflated_sharpe_ratio(
            observed_sr=float(sharpe_ratio(holdout, frequency=MONTHLY, annualize=False)),
            sharpe_variance_across_trials=float(sharpes_monthly.var(ddof=1)),
            n_trials=int(config["n_trials"]),
            n_obs=float(len(holdout)),
            skew=float(skewness(holdout)),
            kurtosis=float(kurtosis(holdout, excess=False)),
        )
        sub = subperiod_performance(s, n_periods=4, frequency=MONTHLY)
        _write_table(sub, "subperiods")
        share_positive = float((sub["sharpe"] > 0).mean()) if "sharpe" in sub.columns else float("nan")
        se_holdout = sharpe_standard_error(holdout, frequency=MONTHLY)
        metrics["validation"] = {
            "reference": reference,
            "sharpe_before_holdout": float(sharpe_ratio(before, frequency=MONTHLY)),
            "sharpe_holdout": float(sharpe_ratio(holdout, frequency=MONTHLY)),
            "sharpe_holdout_se_lo": float(se_holdout.lo),
            "tstat_holdout": float(sharpe_ratio(holdout, frequency=MONTHLY) / se_holdout.lo),
            "pbo": float(pbo.pbo),
            "deflated_sharpe": float(dsr),
            "positive_subperiod_share": share_positive,
            "n_holdout_months": len(holdout),
        }

    with stage("verdict"):
        crit = VerdictCriteria(**config["verdict"])
        best = float(alone["sharpe"].max())
        combined = float(portfolios.loc[reference, "sharpe"])
        checks = (
            ReplicationCheck(
                "sharpe_du_melange_contre_meilleure_jambe_seule",
                published=best,
                ours=combined,
                tolerance=0.0,
                tolerance_kind="absolute",
                source="hypothèse de l'étude : le mélange bat la meilleure stratégie seule",
                note="le contrôle passe si notre Sharpe est au moins celui de la meilleure jambe",
            ),
        )
        evidence = VerdictEvidence(
            hypothesis_supported=combined > best,
            replication_checks=checks,
            oos_sharpe=metrics["validation"]["sharpe_holdout"],
            tstat_after_multiplicity=metrics["validation"]["tstat_holdout"],
            deflated_sharpe=metrics["validation"]["deflated_sharpe"],
            pbo=metrics["validation"]["pbo"],
            positive_subperiod_share=share_positive,
            surviving_cost_multiple=metrics["surviving_cost_multiple"],
            portfolio_correlation=None,
            notes=(
                "portefeuille de stratégies, coûts de rééquilibrage facturés, "
                "holdout jamais consulté avant cette étape"
            ),
        )
        verdict, reasons = decide_verdict(evidence, crit)
        metrics["verdict"] = verdict.value
        metrics["verdict_reasons"] = reasons
        pd.DataFrame({"reason": reasons}).to_csv(TABLES / "verdict_reasons.csv", index=False)

    (RESULTS / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    with ExperimentRegistry().run(
        name="multi_strategy_net_012",
        hypothesis=config["hypothesis"],
        config=config,
        seed=int(config["seed"]),
        universe=list(returns.columns),
        date_start=metrics["common_window"]["start"],
        date_end=metrics["common_window"]["end"],
        cost_basis=CostBasis.NET,
        cost_assumptions={"spread_bps": cost_bps},
        n_trials=int(config["n_trials"]),
    ) as run:
        run.log_metric(
            "sharpe_holdout", metrics["validation"]["sharpe_holdout"], sample=SampleTag.FINAL_HOLDOUT
        )
        run.log_metric(
            "sharpe_before_holdout",
            metrics["validation"]["sharpe_before_holdout"],
            sample=SampleTag.OUT_OF_SAMPLE,
        )
        run.set_verdict(verdict)
    LOG.info("étude terminée", extra={"verdict": verdict.value})


if __name__ == "__main__":
    main()

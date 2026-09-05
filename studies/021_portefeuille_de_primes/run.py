"""Étude 021 : le portefeuille de primes pré-inscrit, trois jambes, une règle de poids, un empilement.

Tout paramètre vient de ``config.yaml``, écrit avant le premier chiffre. Le
verdict porte sur la seule configuration de référence déclarée là ; les
autres configurations sont de l'information et comptent comme essais.

    uv run python studies/021_portefeuille_de_primes/run.py
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
from quantlab.analytics.returns import resample_returns, to_returns
from quantlab.analytics.risk import kurtosis, skewness
from quantlab.analytics.visualization.figures import (
    correlation_heatmap,
    cumulative_return_pct,
    save_figure,
)
from quantlab.backtest.engine import run_backtest
from quantlab.core.logging import configure_logging, get_logger, stage
from quantlab.core.types import CostBasis, Frequency, ReturnKind, SampleTag
from quantlab.data.providers.cboe import CboeIndexProvider, daily_segment
from quantlab.data.providers.french import FrenchProvider
from quantlab.data.providers.yahoo import YahooProvider, to_wide
from quantlab.execution.costs import LinearCostModel
from quantlab.execution.leverage import apply_leverage, volatility_target_exposure
from quantlab.experiments import ExperimentRegistry
from quantlab.portfolio.covariance import LedoitWolfCovariance
from quantlab.portfolio.optimizers import EqualWeight, InverseVolatility
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
LOG = get_logger("study.021")


def _write_table(frame: pd.DataFrame, name: str) -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    frame.to_csv(TABLES / f"{name}.csv")


def _month_end(s: pd.Series) -> pd.Series:
    s = s.copy()
    s.index = pd.DatetimeIndex(s.index).to_period("M").to_timestamp("M")
    return s


def _load_legs(config: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Charge les trois jambes en excédent du taux sans risque, la vente de puts AVANT son coût.

    Returns:
        Le tableau mensuel aligné sur la fenêtre commune, et les mesures de chargement.
    """
    legs = config["legs"]
    colonnes: dict[str, pd.Series] = {}
    for key in ("trend", "value_mom"):
        spec = legs[key]
        s = load_series(ROOT / "studies" / spec["study"] / "results", spec["name"])
        if s.index.to_series().diff().median() < pd.Timedelta(days=20):
            s = resample_returns(s, MONTHLY, ReturnKind.SIMPLE)
        colonnes[key] = _month_end(s).rename(key)
    cboe = CboeIndexProvider()
    niveaux = daily_segment(cboe.history(legs["put_writing"]["cboe_index"]))
    quotidien = to_returns(
        pd.Series(niveaux["level"].to_numpy(), index=niveaux["date"]), kind=ReturnKind.SIMPLE
    )
    put_total = _month_end(resample_returns(quotidien, MONTHLY, ReturnKind.SIMPLE))
    rf = FrenchProvider().benchmark_factors(frequency=MONTHLY, start="1986-01-01")["RF"]
    rf = _month_end(rf)
    colonnes["put_writing"] = (put_total - rf.reindex(put_total.index)).rename("put_writing")
    frame = pd.DataFrame(colonnes).dropna(how="any")
    mesures = {
        "put_index": legs["put_writing"]["cboe_index"],
        "put_daily_start": str(niveaux["date"].min().date()),
        "put_daily_end": str(niveaux["date"].max().date()),
        "put_daily_rows": len(niveaux),
        "put_manifest_license": cboe.manifest().license,
        "common_window": {
            "start": str(frame.index.min().date()),
            "end": str(frame.index.max().date()),
            "n_months": len(frame),
        },
    }
    return frame, mesures


def _apply_put_cost(legs: pd.DataFrame, config: dict[str, Any], multiple: float) -> pd.DataFrame:
    """Retire à la vente de puts son coût mensuel déclaré, multiplié pour le test de survie."""
    net = legs.copy()
    if "put_writing" in net.columns:
        cout = float(config["legs"]["put_writing"]["cost_bps_per_month"]) / 1e4 * multiple
        net["put_writing"] = net["put_writing"] - cout
    return net


def _fit_weights(train: pd.DataFrame, name: str) -> pd.Series:
    """Les poids d'une règle sur la seule fenêtre passée ; aucune moyenne n'est estimée."""
    cov = LedoitWolfCovariance().covariance(train)
    if name == "equal_weight":
        return EqualWeight().optimize(covariance=cov)
    if name == "inverse_volatility":
        return InverseVolatility().optimize(covariance=cov)
    raise ValueError(f"règle de poids inconnue : {name}")


def _walk_forward(returns: pd.DataFrame, name: str, config: dict[str, Any], cost_bps: float) -> Any:
    """Poids réestimés tous les douze mois sur le passé seul, tenus entre deux estimations."""
    wf = config["walk_forward"]
    min_train, step = int(wf["min_train_months"]), int(wf["refit_every_months"])
    targets: dict[pd.Timestamp, pd.Series] = {}
    for start in range(min_train, len(returns), step):
        targets[returns.index[start - 1]] = _fit_weights(returns.iloc[:start], name)
    weights = pd.DataFrame(targets).T.reindex(returns.index)
    first = min(targets)
    return run_backtest(
        weights=weights.loc[first:],
        returns=returns.loc[first:],
        frequency=MONTHLY,
        execution_lag=1,
        cost_model=LinearCostModel(spread_bps=cost_bps),
    )


def _stack(mix: pd.Series, config: dict[str, Any], max_leverage: float, cost_multiple: float = 1.0) -> Any:
    """Empile le mélange net à la cible de volatilité déclarée, sous le plafond donné."""
    st = config["stacking"]
    exposition = volatility_target_exposure(
        mix,
        target_vol=float(st["target_vol"]),
        window=int(st["vol_window_months"]),
        periods_per_year=12,
        max_leverage=max_leverage,
    )
    return apply_leverage(
        mix,
        exposition,
        financing_spread_annual=float(st["financing_spread_annual"]),
        periods_per_year=12,
        trade_cost_per_unit=float(st["exposure_trade_cost_per_unit"]) * cost_multiple,
    )


def _build(
    legs_gross: pd.DataFrame,
    allocation: str,
    max_leverage: float,
    config: dict[str, Any],
    cost_multiple: float = 1.0,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Rend le mélange net, le rendement empilé net et l'exposition tenue, pour une configuration."""
    legs_net = _apply_put_cost(legs_gross, config, cost_multiple)
    spread = float(config["costs"]["spread_bps"]) * cost_multiple
    mix = _walk_forward(legs_net, allocation, config, spread).net_returns.dropna()
    empile = _stack(mix, config, max_leverage, cost_multiple)
    # La première année de l'empilement attend la fenêtre de volatilité ; elle est retirée
    # pour que toutes les configurations se comparent sur les mêmes mois.
    fenetre = int(config["stacking"]["vol_window_months"])
    net = empile.net.iloc[fenetre:]
    return mix.loc[net.index], net, empile.exposure.loc[net.index]


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
    reference_alloc = str(config["reference_allocation"])
    caps = [float(c) for c in config["stacking"]["leverage_caps_declared"]]
    reference_cap = caps[0]
    metrics: dict[str, Any] = {"n_trials": int(config["n_trials"])}

    with stage("chargement"):
        legs_gross, mesures = _load_legs(config)
        metrics["data"] = mesures
        legs_net = _apply_put_cost(legs_gross, config, 1.0)
        _write_table(legs_net, "legs_monthly_net")

    with stage("correlations"):
        corr = legs_net.corr()
        _write_table(corr, "correlation_matrix")
        upper = corr.where(np.triu(np.ones(corr.shape, dtype=bool), k=1))
        pairs = upper.stack()  # noqa: PD013
        metrics["correlation"] = {
            "mean_pairwise": float(pairs.mean()),
            "min_pair": {"pair": " / ".join(pairs.idxmin()), "value": float(pairs.min())},
            "max_pair": {"pair": " / ".join(pairs.idxmax()), "value": float(pairs.max())},
            "effective_breadth": float(effective_breadth(corr)),
        }
        fig, _ = correlation_heatmap(
            legs_net,
            title=(
                "Corrélations mensuelles des trois primes, "
                f"{legs_net.index.min().year}-{legs_net.index.max().year}"
            ),
        )
        save_figure(fig, FIGURES / "correlations")

    with stage("chaque_jambe_seule"):
        alone = pd.DataFrame([_describe(legs_net[c], c) for c in legs_net.columns]).set_index("series")
        _write_table(alone, "legs_alone")

    with stage("configurations"):
        configs: dict[str, pd.Series] = {}
        mixes: dict[str, pd.Series] = {}
        expositions: dict[str, pd.Series] = {}
        rows = []
        for allocation in config["allocations"]:
            for cap in caps:
                nom = f"{allocation}_cap{cap:.1f}"
                mix, net, expo = _build(legs_gross, allocation, cap, config)
                configs[nom], mixes[nom], expositions[nom] = net, mix, expo
                row = _describe(net, nom)
                row["allocation"] = allocation
                row["leverage_cap"] = cap
                row["mean_exposure"] = float(expo.mean())
                row["sharpe_unlevered_mix"] = float(sharpe_ratio(mix, frequency=MONTHLY))
                row["sharpe_before_holdout"] = float(
                    sharpe_ratio(net.loc[net.index < holdout_start], frequency=MONTHLY)
                )
                row["sharpe_holdout"] = float(
                    sharpe_ratio(net.loc[net.index >= holdout_start], frequency=MONTHLY)
                )
                rows.append(row)
        portfolios = pd.DataFrame(rows).set_index("series")
        _write_table(portfolios, "configurations")
        reference = f"{reference_alloc}_cap{reference_cap:.1f}"
        ref = configs[reference]
        _write_table(pd.DataFrame(expositions), "exposures")
        for nom, serie in configs.items():
            save_series(
                RESULTS,
                f"portfolio_{nom}_net",
                serie,
                sample=SampleTag.OUT_OF_SAMPLE,
                basis=CostBasis.NET,
                frequency=MONTHLY,
                universe=(
                    "trois primes, poids par règle réestimés chaque année, empilement à cible de volatilité"
                ),
                cost_assumptions=(
                    f"{config['costs']['spread_bps']} pb de rotation, "
                    f"{config['legs']['put_writing']['cost_bps_per_month']} pb par mois sur les puts, "
                    f"{config['stacking']['financing_spread_annual'] * 1e4:.0f} pb/an de financement, "
                    f"{config['stacking']['exposure_trade_cost_per_unit'] * 1e4:.0f} pb "
                    "par unité d'exposition"
                ),
            )
        # La meilleure jambe seule se compare sur les MÊMES mois que la référence.
        alone_common = pd.DataFrame(
            [_describe(legs_net.loc[ref.index, c], c) for c in legs_net.columns]
        ).set_index("series")
        _write_table(alone_common, "legs_alone_reference_window")
        best_alone = alone_common["sharpe"].idxmax()
        metrics["best_alone"] = {"leg": best_alone, "sharpe": float(alone_common.loc[best_alone, "sharpe"])}
        metrics["reference"] = {"name": reference, **portfolios.loc[reference].to_dict()}
        courbes = {
            "Portefeuille de primes, empilé à 1,5": ref,
            "Mélange sans levier": mixes[reference],
            "Tendance seule": legs_net.loc[ref.index, "trend"],
            "Valeur et momentum seuls": legs_net.loc[ref.index, "value_mom"],
            "Vente de puts seule": legs_net.loc[ref.index, "put_writing"],
        }
        fig, _ = cumulative_return_pct(
            courbes,
            title=(
                "Le portefeuille de primes et ses trois jambes, rendement excédentaire cumulé en %, "
                f"{ref.index.min().year}-{ref.index.max().year}"
            ),
        )
        save_figure(fig, FIGURES / "portefeuille_de_primes")

    with stage("apport_marginal"):
        marginal_rows = []
        for dropped in legs_gross.columns:
            sub = legs_gross.drop(columns=[dropped])
            _, sans, _ = _build(sub, reference_alloc, reference_cap, config)
            common = ref.index.intersection(sans.index)
            marginal_rows.append(
                {
                    "dropped": dropped,
                    "sharpe_with": float(sharpe_ratio(ref.loc[common], frequency=MONTHLY)),
                    "sharpe_without": float(sharpe_ratio(sans.loc[common], frequency=MONTHLY)),
                }
            )
        marginal = pd.DataFrame(marginal_rows).set_index("dropped")
        marginal["marginal_sharpe"] = marginal["sharpe_with"] - marginal["sharpe_without"]
        _write_table(marginal, "marginal_contribution")
        metrics["marginal"] = {k: float(v) for k, v in marginal["marginal_sharpe"].items()}

    with stage("multiple_de_couts"):
        cost_rows = []
        surviving = 0.0
        for multiple in [float(m) for m in config["costs"]["multiples"]]:
            _, net_m, _ = _build(legs_gross, reference_alloc, reference_cap, config, cost_multiple=multiple)
            sr = float(sharpe_ratio(net_m, frequency=MONTHLY))
            cost_rows.append({"multiple": multiple, "sharpe_net": sr})
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
            fund = _month_end(fund_returns_from_prices(px, frequency=MONTHLY)[ticker])
            comp = compare_trajectories(
                ref, fund, frequency=MONTHLY, strategy_name=reference, fund_name=ticker
            )
            metrics["benchmark_fund"] = comp.as_row()
            metrics["benchmark_fund"]["start"] = str(comp.start.date())
            metrics["benchmark_fund"]["end"] = str(comp.end.date())
            _write_table(pd.DataFrame([metrics["benchmark_fund"]]), "benchmark_fund")
        except Exception as exc:
            metrics["benchmark_fund"] = {"error": str(exc)}
            LOG.warning("repère de fonds indisponible", extra={"ticker": ticker, "error": str(exc)})

    with stage("validation"):
        before = ref.loc[ref.index < holdout_start]
        holdout = ref.loc[ref.index >= holdout_start]
        matrix = pd.DataFrame(configs).dropna()
        pbo = probability_of_backtest_overfitting(matrix, n_splits=8, frequency=MONTHLY)
        sharpes_monthly = np.array(
            [sharpe_ratio(v, frequency=MONTHLY, annualize=False) for v in configs.values()]
        )
        dsr = deflated_sharpe_ratio(
            observed_sr=float(sharpe_ratio(holdout, frequency=MONTHLY, annualize=False)),
            sharpe_variance_across_trials=float(sharpes_monthly.var(ddof=1)),
            n_trials=int(config["n_trials"]),
            n_obs=float(len(holdout)),
            skew=float(skewness(holdout)),
            kurtosis=float(kurtosis(holdout, excess=False)),
        )
        sub = subperiod_performance(ref, n_periods=4, frequency=MONTHLY)
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
            "return_holdout_annual_pct": float(((1 + holdout).prod() ** (12 / len(holdout)) - 1) * 100),
            "max_drawdown_pct": float(max_drawdown(ref) * 100),
        }

    with stage("verdict"):
        crit = VerdictCriteria(**config["verdict"])
        best = float(metrics["best_alone"]["sharpe"])
        combined = float(portfolios.loc[reference, "sharpe"])
        checks = (
            ReplicationCheck(
                "sharpe_du_portefeuille_contre_meilleure_jambe_seule",
                published=best,
                ours=combined,
                tolerance=0.0,
                tolerance_kind="absolute",
                source="hypothèse de l'étude : le portefeuille bat la meilleure jambe seule, mêmes mois",
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
                "configuration de référence déclarée avant tout calcul ; holdout jamais consulté "
                "avant cette étape ; financement modélisé"
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
        name=config["name"],
        hypothesis=config["hypothesis"],
        config=config,
        seed=int(config["seed"]),
        universe=list(legs_gross.columns),
        date_start=str(ref.index.min().date()),
        date_end=str(ref.index.max().date()),
        cost_basis=CostBasis.NET,
        cost_assumptions={
            "spread_bps": float(config["costs"]["spread_bps"]),
            "put_cost_bps_per_month": float(config["legs"]["put_writing"]["cost_bps_per_month"]),
            "financing_spread_annual": float(config["stacking"]["financing_spread_annual"]),
            "exposure_trade_cost_per_unit": float(config["stacking"]["exposure_trade_cost_per_unit"]),
        },
        n_trials=int(config["n_trials"]),
    ) as run:
        run.log_metric(
            "sharpe_holdout", metrics["validation"]["sharpe_holdout"], sample=SampleTag.OUT_OF_SAMPLE
        )
        run.set_verdict(verdict)
    LOG.info("étude terminée", extra={"verdict": verdict.value})
    print(
        json.dumps(
            {k: metrics[k] for k in ("data", "best_alone", "reference", "validation", "verdict")},
            indent=1,
            default=str,
        )
    )


if __name__ == "__main__":
    main()

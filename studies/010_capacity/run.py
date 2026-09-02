"""Étude 010 : à quelle taille les deux stratégies chiffrables cessent-elles de rapporter ?

Le point d'entrée ne porte aucune logique réutilisable : il rebâtit les poids
des études 001 et 007 avec les briques de ``quantlab`` et leurs propres
paramètres, puis appelle le module de capacité. Tout chiffre produit est
MODÉLISÉ. Il est déterministe et sort sur le réseau, Yahoo et Kenneth French.

    uv run python studies/010_capacity/run.py
"""

from __future__ import annotations

import json
import math
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from quantlab.analytics.returns import to_returns
from quantlab.analytics.visualization.figures import capacity_plot, save_figure
from quantlab.core.config import ExperimentConfig, load_config
from quantlab.core.logging import configure_logging, get_logger, stage
from quantlab.core.types import CostBasis, Frequency, SampleTag, Verdict
from quantlab.data.providers.french import FrenchProvider
from quantlab.data.providers.yahoo import YahooProvider, to_wide
from quantlab.execution.capacity import (
    CapacityCurve,
    average_daily_dollar_volume,
    capacity_curve,
    realized_daily_volatility,
)
from quantlab.experiments import ExperimentRegistry
from quantlab.strategies.statistical_arbitrage import TradingRule, statistical_arbitrage_weights
from quantlab.strategies.time_series_momentum import ex_ante_volatility, tsmom_weights

warnings.filterwarnings("ignore", category=FutureWarning, module="pandas")
STUDY_DIR = Path(__file__).resolve().parent
STUDIES = STUDY_DIR.parent
RESULTS = STUDY_DIR / "results"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"
LOG = get_logger("study.010")


@dataclass(frozen=True)
class StrategyInputs:
    """Ce que la capacité exige d'une stratégie : poids, rendements, volumes, volatilités."""

    name: str
    weights: pd.DataFrame
    returns: pd.DataFrame
    adv_dollars: pd.DataFrame
    volatility: pd.DataFrame
    frequency: Frequency
    evaluate_from: pd.Timestamp | None
    universe: str
    manifests: list[dict[str, Any]]


def _write_table(frame: pd.DataFrame, name: str) -> None:
    frame.to_csv(TABLES / f"{name}.csv", float_format="%.10g")


def load_tsmom(study_dir: Path, impact: dict[str, Any]) -> StrategyInputs:
    """Rebâtit les poids mensuels de l'étude 001 avec ses paramètres, et y joint les volumes."""
    config = load_config(study_dir / "config.yaml", ExperimentConfig)
    p = config.params
    universe = list(config.data.universe)
    yahoo = YahooProvider()
    raw = yahoo.fetch(universe, start=config.data.start, end=config.data.end, on_missing="drop")
    prices = to_wide(raw, config.data.price_field).reindex(columns=universe)
    closes = to_wide(raw, "close").reindex(columns=universe)
    volumes = to_wide(raw, "volume").reindex(columns=universe)
    returns = prices.pct_change()

    french = FrenchProvider()
    daily_factors = french.benchmark_factors(frequency=Frequency.DAILY, start=config.data.start)
    monthly_factors = french.benchmark_factors(frequency=Frequency.MONTHLY, start=p["aqr_start"])
    rf_daily = daily_factors["RF"].reindex(returns.index).ffill()
    if bool(rf_daily.isna().any()):
        raise ValueError("le taux sans risque quotidien ne couvre pas toutes les séances.")
    excess_daily = returns.sub(rf_daily, axis=0)
    volatility = ex_ante_volatility(
        excess_daily,
        center_of_mass=float(p["volatility_center_of_mass_days"]),
        annualization_days=float(p["volatility_annualization_days"]),
        min_periods=int(p["volatility_min_periods_days"]),
    )

    key = [returns.index.year, returns.index.month]
    last_sessions = pd.DatetimeIndex(sorted(returns.index.to_series().groupby(key).max().to_numpy()))
    month_ends = pd.DatetimeIndex(last_sessions.to_period("M").to_timestamp("M"))
    sessions = returns.notna().groupby(key).sum().set_axis(month_ends)
    monthly_raw = ((1.0 + returns).groupby(key).prod() - 1.0).set_axis(month_ends)
    monthly_raw = monthly_raw.where(sessions >= int(p["min_trading_days_per_month"]))
    rf_monthly = monthly_factors["RF"].reindex(month_ends, method="ffill")
    excess_monthly = monthly_raw.sub(rf_monthly, axis=0)
    volatility_monthly = volatility.reindex(last_sessions).set_axis(month_ends)

    start = p["backtest_start"]
    weights = tsmom_weights(
        excess_monthly,
        volatility_monthly,
        lookback=int(p["lookback_months"]),
        holding=int(p["holding_months"]),
        target_volatility=float(p["target_volatility"]),
    ).loc[start:]
    engine_returns = excess_monthly.loc[start:].fillna(0.0)
    adv = average_daily_dollar_volume(
        closes, volumes, window=int(impact["adv_window_days"]), min_periods=int(impact["min_periods_days"])
    )
    vol = realized_daily_volatility(
        returns, window=int(impact["volatility_window_days"]), min_periods=int(impact["min_periods_days"])
    )
    return StrategyInputs(
        name="tsmom",
        weights=weights,
        returns=engine_returns,
        adv_dollars=adv,
        volatility=vol,
        frequency=Frequency.MONTHLY,
        evaluate_from=None,
        universe="28 fonds négociés en bourse, quatre classes d'actifs, substituts aux contrats à terme",
        manifests=[
            yahoo.manifest().model_dump(mode="json"),
            french.manifest("F-F_Research_Data_Factors").model_dump(mode="json"),
        ],
    )


def load_statarb(study_dir: Path, impact: dict[str, Any]) -> StrategyInputs:
    """Rebâtit les poids quotidiens de l'étude 007, règle de l'article, et y joint les volumes."""
    config = load_config(study_dir / "config.yaml", ExperimentConfig)
    params = config.params
    benchmark = str(params["benchmark_symbol"])
    provider = YahooProvider(on_missing="drop")
    raw = provider.fetch(
        list(config.data.universe), start=config.data.start, end=config.data.end, auto_adjust=False
    )
    adjusted = to_wide(raw, "adj_close")
    closes = to_wide(raw, "close")
    volumes = to_wide(raw, "volume")
    all_returns = to_returns(adjusted)
    stock_returns = all_returns.drop(columns=[benchmark])
    dollar_volume = (closes * volumes).drop(columns=[benchmark])
    liquidity = dollar_volume.rolling(int(params["correlation_window"])).median()
    liquid = (liquidity >= float(params["min_dollar_volume"])).reindex(stock_returns.index)
    filled = stock_returns.fillna(0.0)
    rules = [TradingRule(**rule) for rule in params["rules"]]
    result = statistical_arbitrage_weights(
        stock_returns,
        rules=rules,
        tradable=liquid,
        correlation_window=int(params["correlation_window"]),
        estimation_window=int(params["estimation_window"]),
        n_components=int(params["n_components"]),
        variance_share=None,
        max_characteristic_days=float(params["max_characteristic_days"]),
        gross_leverage=float(params["gross_leverage"]),
        reestimation_days=int(params["reestimation_days"]),
        hedge_at_entry=bool(params["hedge_at_entry"]),
        min_names=int(params["min_names"]),
        centre_across_names=True,
        use_modified_s_score=False,
    )
    weights = result.weights[rules[0].name]
    first_decision = weights.dropna(how="all").index[0]
    first_trade = filled.index[filled.index.get_loc(first_decision) + 1]
    adv = average_daily_dollar_volume(
        closes.drop(columns=[benchmark]),
        volumes.drop(columns=[benchmark]),
        window=int(impact["adv_window_days"]),
        min_periods=int(impact["min_periods_days"]),
    )
    vol = realized_daily_volatility(
        stock_returns,
        window=int(impact["volatility_window_days"]),
        min_periods=int(impact["min_periods_days"]),
    )
    return StrategyInputs(
        name="statarb",
        weights=weights,
        returns=filled,
        adv_dollars=adv,
        volatility=vol,
        frequency=Frequency.DAILY,
        evaluate_from=pd.Timestamp(first_trade),
        universe="grandes capitalisations américaines via Yahoo, biais de survie déclaré, règle de l'article",
        manifests=[provider.manifest().model_dump(mode="json")],
    )


def _curve(
    inputs: StrategyInputs,
    *,
    spec: dict[str, Any],
    impact: dict[str, Any],
    aum_grid: tuple[float, ...],
    coefficient: float,
    execution_days: int,
) -> CapacityCurve:
    """Appelle le module de capacité avec les paramètres déclarés de la stratégie."""
    return capacity_curve(
        inputs.weights,
        inputs.returns,
        adv_dollars=inputs.adv_dollars,
        volatility=inputs.volatility,
        frequency=inputs.frequency,
        aum_grid=aum_grid,
        coefficient=coefficient,
        spread_bps=float(spec["spread_bps"]),
        execution_days=execution_days,
        participation_cap=float(impact["participation_cap"]),
        execution_lag=1,
        evaluate_from=inputs.evaluate_from,
        on_missing_liquidity=str(impact["on_missing_liquidity"]),  # type: ignore[arg-type]
    )


def _row(strategy: str, case: str, curve: CapacityCurve, reference_aum: float) -> dict[str, Any]:
    """Résume une courbe en une ligne, dont le ratio net au capital de référence."""
    if reference_aum in curve.table.index:
        sharpe_at_reference = float(curve.table.loc[reference_aum, "sharpe_net"])
    else:
        sharpe_at_reference = math.nan
    retention = (
        sharpe_at_reference / curve.sharpe_reference
        if curve.sharpe_reference and math.isfinite(curve.sharpe_reference)
        else math.nan
    )
    return {
        "strategy": strategy,
        "case": case,
        "coefficient": curve.coefficient,
        "execution_days": curve.execution_days,
        "n_periods": curve.n_periods,
        "sharpe_reference": curve.sharpe_reference,
        "return_reference_annual": curve.return_reference_annual,
        "sharpe_at_reference_aum": sharpe_at_reference,
        "retention_at_reference_aum": retention,
        "breakeven_aum": curve.breakeven_aum,
        "participation_cap_aum": curve.participation_cap_aum,
        "capacity_aum": curve.capacity_aum,
        "half_sharpe_aum": curve.half_sharpe_aum,
        "breakeven_check_mean_net": curve.breakeven_check,
        "breakeven_clipped": curve.breakeven_clipped,
        "binding_assets": "; ".join(f"{asset} {value:.3g}" for asset, value in curve.binding_assets),
    }


def main() -> None:
    configure_logging("INFO")
    config = yaml.safe_load((STUDY_DIR / "config.yaml").read_text(encoding="utf-8"))
    for d in (RESULTS, TABLES, FIGURES):
        d.mkdir(parents=True, exist_ok=True)
    impact = dict(config["impact"])
    grid = tuple(float(a) for a in config["aum_grid"])
    reference_aum = float(config["reference_aum"])
    crit = config["verdict"]
    loaders = {"tsmom": load_tsmom, "statarb": load_statarb}
    metrics: dict[str, Any] = {"n_trials": int(config["n_trials"]), "status": "modélisé", "strategies": {}}
    summary_rows: list[dict[str, Any]] = []
    sensitivity_rows: list[dict[str, Any]] = []
    reasons: list[str] = []
    all_hold = True
    windows: list[tuple[str, str]] = []

    for name, spec in config["strategies"].items():
        with stage(f"{name}_donnees"):
            inputs = loaders[name](STUDIES / spec["study"], impact)
            windows.append((str(inputs.returns.index.min().date()), str(inputs.returns.index.max().date())))
            LOG.info(
                "poids rebâtis",
                extra={
                    "strategy": name,
                    "n_periods": len(inputs.weights),
                    "n_assets": inputs.weights.shape[1],
                },
            )

        with stage(f"{name}_capacite"):
            base = _curve(
                inputs,
                spec=spec,
                impact=impact,
                aum_grid=grid,
                coefficient=float(impact["coefficient"]),
                execution_days=int(spec["execution_days"]),
            )
            _write_table(base.table, f"capacity_{name}")
            fig, _ = capacity_plot(
                base.table,
                breakeven_aum=base.breakeven_aum,
                half_sharpe_aum=base.half_sharpe_aum,
                capacity_aum=base.capacity_aum,
                title=None,
            )
            save_figure(fig, FIGURES / f"capacity_{name}.png")
            row = _row(name, "base", base, reference_aum)
            summary_rows.append(row)
            holds = (
                math.isfinite(row["retention_at_reference_aum"])
                and row["retention_at_reference_aum"] >= float(crit["min_sharpe_retention_at_reference"])
                and row["sharpe_at_reference_aum"] >= float(crit["min_net_sharpe_at_reference"])
            )
            all_hold = all_hold and holds
            reasons.append(
                f"{name} : ratio net {row['sharpe_at_reference_aum']:.3f} au capital de référence, "
                f"rétention {row['retention_at_reference_aum']:.3f} ; "
                f"{'tient' if holds else 'ne tient pas'}"
            )
            metrics["strategies"][name] = {
                **base.summary(),
                "hypothesis_supported": holds,
                "universe": inputs.universe,
                "window": {"start": windows[-1][0], "end": windows[-1][1]},
                "spread_bps": float(spec["spread_bps"]),
                "manifests": inputs.manifests,
            }

        with stage(f"{name}_sensibilite"):
            for coefficient in impact["coefficient_sensitivity"]:
                curve = _curve(
                    inputs,
                    spec=spec,
                    impact=impact,
                    aum_grid=(reference_aum,),
                    coefficient=float(coefficient),
                    execution_days=int(spec["execution_days"]),
                )
                sensitivity_rows.append(_row(name, f"coefficient_{coefficient}", curve, reference_aum))
            for days in spec["execution_days_sensitivity"]:
                curve = _curve(
                    inputs,
                    spec=spec,
                    impact=impact,
                    aum_grid=(reference_aum,),
                    coefficient=float(impact["coefficient"]),
                    execution_days=int(days),
                )
                sensitivity_rows.append(_row(name, f"execution_days_{days}", curve, reference_aum))

    summary = pd.DataFrame(summary_rows).set_index("strategy")
    sensitivity = pd.DataFrame(sensitivity_rows)
    _write_table(summary, "summary")
    _write_table(sensitivity.set_index(["strategy", "case"]), "sensitivity")
    verdict = Verdict.EXPERIMENTAL if all_hold else Verdict.REJECTED
    metrics["verdict"] = verdict.value
    metrics["verdict_reasons"] = reasons
    metrics["not_computable"] = (
        "xsmom, value_mom, quality, bab, vol_managed et fx_carry tournent sur des portefeuilles de "
        "facteurs publiés sans poids par titre ni volume : capacité non calculable, déclarée."
    )
    (RESULTS / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    with ExperimentRegistry().run(
        name="capacity_010",
        hypothesis=config["hypothesis"],
        config=config,
        seed=int(config["seed"]),
        universe=list(config["strategies"]),
        date_start=min(w[0] for w in windows),
        date_end=max(w[1] for w in windows),
        cost_basis=CostBasis.NET,
        cost_assumptions={
            "impact_coefficient": float(impact["coefficient"]),
            "participation_cap": float(impact["participation_cap"]),
            **{
                f"spread_bps_{name}": float(spec["spread_bps"]) for name, spec in config["strategies"].items()
            },
        },
        n_trials=int(config["n_trials"]),
    ) as run:
        for name in summary.index:
            run.log_metric(
                f"sharpe_at_reference_aum_{name}",
                float(summary.loc[name, "sharpe_at_reference_aum"]),
                sample=SampleTag.OUT_OF_SAMPLE,
            )
        run.set_verdict(verdict)
    LOG.info("étude terminée", extra={"verdict": verdict.value})


if __name__ == "__main__":
    main()

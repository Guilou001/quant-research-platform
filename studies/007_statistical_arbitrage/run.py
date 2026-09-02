"""Le point d'entrée de l'étude 007, arbitrage statistique.

Ce fichier orchestre et n'implémente rien de réutilisable. La stratégie vit
dans :mod:`quantlab.strategies.statistical_arbitrage`, les métriques dans
:mod:`quantlab.analytics`, les contrôles dans :mod:`quantlab.validation`.

Lancement :

.. code-block:: bash

    export QUANTLAB_USER_AGENT="votre nom votre courriel"
    uv run python studies/007_statistical_arbitrage/run.py
"""

from __future__ import annotations

import itertools
import json
import math
import warnings
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from quantlab.analytics.drawdown import max_drawdown
from quantlab.analytics.ratios import sharpe_ratio, sharpe_tstat
from quantlab.analytics.regression import beta as market_beta
from quantlab.analytics.returns import to_returns
from quantlab.analytics.risk import kurtosis, skewness, volatility
from quantlab.analytics.turnover import annualized_turnover, turnover_series
from quantlab.analytics.visualization import figures as viz
from quantlab.backtest.engine import BacktestResult, run_backtest
from quantlab.core.config import ExperimentConfig, load_config
from quantlab.core.determinism import child_generators
from quantlab.core.errors import ConfigError, QuantLabError
from quantlab.core.logging import get_logger, stage
from quantlab.core.types import AssetClass, CostBasis, Frequency, SampleTag
from quantlab.data.providers.yahoo import YahooProvider, to_wide
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
from quantlab.strategies.statistical_arbitrage import (
    SURVIVORSHIP_BIAS_RISK,
    StatisticalArbitrageResult,
    TradingRule,
    market_hedged_book,
    statistical_arbitrage_weights,
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

warnings.filterwarnings("ignore", category=FutureWarning, module="pandas")

LOG = get_logger("quantlab.studies.007")
STUDY_DIR = Path(__file__).resolve().parent
RESULTS = STUDY_DIR / "results"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"
DAILY = Frequency.DAILY

#: Le ratio de Sharpe annuel du portefeuille à quinze composantes principales,
#: table 6 page 774. RAPPORTÉ, lu dans le fac-similé de l'article publié.
PAPER_ANNUAL_SHARPE: Mapping[int, float] = {
    1997: 1.4,
    1998: 1.4,
    1999: 0.2,
    2000: 2.2,
    2001: 2.6,
    2002: 3.4,
    2003: 0.9,
    2004: 2.2,
    2005: 1.2,
    2006: 1.0,
    2007: -0.7,
}

#: Les cinq lignes de la table 8, page 776, sur 2002 à 2007. RAPPORTÉ.
PAPER_TABLE_8: Mapping[str, float] = {
    "1 portefeuille propre": 0.7,
    "15 portefeuilles propres": 0.9,
    "45 pour cent de variance": 0.6,
    "55 pour cent de variance": 0.7,
    "65 pour cent de variance": 0.4,
}


def _write_table(frame: pd.DataFrame, name: str) -> Path:
    """Écrit un tableau sous ``results/tables`` et rend son chemin."""
    TABLES.mkdir(parents=True, exist_ok=True)
    path = TABLES / f"{name}.csv"
    frame.to_csv(path, index=False)
    LOG.info("tableau écrit", extra={"name": name, "n_rows": len(frame)})
    return path


def _save_figure(fig: Any, name: str) -> str:
    """Écrit une figure en PNG et en PDF, et rend son nom de base."""
    FIGURES.mkdir(parents=True, exist_ok=True)
    written = viz.save_figure(fig, FIGURES / name, vector=True)
    return next(p for p in written if p.suffix == ".png").stem


def _slice(series: pd.Series, start: str | None = None, end: str | None = None) -> pd.Series:
    """Rend la tranche datée d'une série, bornes incluses."""
    out = series
    if start is not None:
        out = out.loc[out.index >= pd.Timestamp(start)]
    if end is not None:
        out = out.loc[out.index <= pd.Timestamp(end)]
    return out


def _sharpe(series: pd.Series) -> float:
    """Rend le ratio de Sharpe annualisé, ou ``nan`` sur une tranche vide."""
    if len(series) < 3:
        return float("nan")
    return sharpe_ratio(series, frequency=DAILY)


def _probe_delisted(provider: YahooProvider, symbols: Sequence[str], start: str, end: str) -> pd.DataFrame:
    """Demande un par un des titres retirés de l'indice, et note ce qui revient."""
    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        try:
            frame = provider.fetch([symbol], start=start, end=end, auto_adjust=False)
        except QuantLabError:
            rows.append(
                {
                    "symbol": symbol,
                    "returned": False,
                    "first_day": "",
                    "last_day": "",
                    "n_days": 0,
                }
            )
            continue
        wide = to_wide(frame, "adj_close")[symbol].dropna()
        rows.append(
            {
                "symbol": symbol,
                "returned": True,
                "first_day": str(wide.index[0].date()),
                "last_day": str(wide.index[-1].date()),
                "n_days": len(wide),
            }
        )
    return pd.DataFrame(rows)


def _run_pipeline(
    returns: pd.DataFrame,
    tradable: pd.DataFrame,
    params: Mapping[str, Any],
    rules: Sequence[TradingRule],
    **overrides: Any,
) -> StatisticalArbitrageResult:
    """Déroule la chaîne quotidienne avec le cas de référence et ses écarts."""
    settings: dict[str, Any] = {
        "correlation_window": int(params["correlation_window"]),
        "estimation_window": int(params["estimation_window"]),
        "n_components": int(params["n_components"]),
        "variance_share": None,
        "max_characteristic_days": float(params["max_characteristic_days"]),
        "gross_leverage": float(params["gross_leverage"]),
        "reestimation_days": int(params["reestimation_days"]),
        "hedge_at_entry": bool(params["hedge_at_entry"]),
        "min_names": int(params["min_names"]),
        "centre_across_names": True,
        "use_modified_s_score": False,
    }
    settings.update(overrides)
    return statistical_arbitrage_weights(returns, rules=rules, tradable=tradable, **settings)


def _backtest(weights: pd.DataFrame, returns: pd.DataFrame, cost_bps: float) -> BacktestResult:
    """Rejoue une suite de poids, décalée d'une séance, au taux de coût demandé."""
    model = LinearCostModel(spread_bps=cost_bps) if cost_bps > 0.0 else None
    return run_backtest(
        weights=weights,
        returns=returns,
        cost_model=model,
        execution_lag=1,
        frequency=DAILY,
    )


def _cost_profile(
    result: BacktestResult,
    gross: pd.Series,
    returns: pd.DataFrame,
    first_trade: pd.Timestamp,
) -> tuple[float, float]:
    """Rend la rotation annuelle en somme entière et le coût qui annule le brut."""
    rotations = turnover_series(
        result.executed_weights.loc[first_trade:],
        returns,
        drifted=True,
        convention="full_sum",
    )
    return annualized_turnover(rotations, DAILY), breakeven_cost_bps(gross, rotations, frequency=DAILY)


def _windows(params: Mapping[str, Any]) -> dict[str, tuple[str | None, str | None]]:
    """Rend les cinq fenêtres nommées de l'étude."""
    return {
        "paper": (params["paper_start"], params["paper_end"]),
        "paper_early": (params["paper_start"], params["paper_early_end"]),
        "paper_late": (params["paper_late_start"], params["paper_end"]),
        "table8": ("2002-01-01", params["paper_end"]),
        "crisis": ("2008-01-01", "2009-12-31"),
        "post_publication": (params["publication_date"], None),
    }


def _performance_row(
    name: str, gross: pd.Series, net: pd.Series, params: Mapping[str, Any]
) -> dict[str, Any]:
    """Rend une ligne de performance, une colonne par fenêtre nommée."""
    row: dict[str, Any] = {"configuration": name}
    row["n_days_total"] = len(net)
    row["sharpe_gross_full"] = _sharpe(gross)
    row["sharpe_net_full"] = _sharpe(net)
    row["return_gross_annual_pct"] = float(gross.mean() * 252.0 * 100.0)
    row["return_net_annual_pct"] = float(net.mean() * 252.0 * 100.0)
    for label, (start, end) in _windows(params).items():
        row[f"sharpe_net_{label}"] = _sharpe(_slice(net, start, end))
    return row


def main() -> None:
    """Mène l'étude de bout en bout et écrit tout ce qu'elle produit."""
    config = load_config(STUDY_DIR / "config.yaml", ExperimentConfig)
    params = config.params
    RESULTS.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)

    rules = [TradingRule(**rule) for rule in params["rules"]]
    reference_rule = rules[0]
    benchmark = str(params["benchmark_symbol"])
    reference_cost = float(config.costs.spread_bps)
    grid_pairs = [
        (int(nc), int(ew)) for nc in params["grid_n_components"] for ew in params["grid_estimation_windows"]
    ]
    positive_multipliers = [float(m) for m in params["cost_multipliers"] if float(m) > 0.0]
    expected_trials = (
        len(grid_pairs)
        + len(params["extra_n_components"])
        + len(params["variance_shares"])
        + len(params["extra_correlation_windows"])
        + len(params["extra_reestimation_days"])
        + len(params["extra_characteristic_days"])
        + (len(rules) - 1)
        + len(params["s_score_variants"])
        + len(params["hedge_variants"])
        + len(params["book_conventions"])
        + len(params["cost_bps_grid"])
        + len(positive_multipliers)
    )
    bootstrap_generator, _ = child_generators(config.seed, 2)
    counter = TrialCounter()
    registry = ExperimentRegistry()
    manifests: list[dict[str, Any]] = []

    with registry.run(
        name="007_statistical_arbitrage",
        hypothesis=config.hypothesis,
        config=config.model_dump(mode="json"),
        seed=config.seed,
        universe=list(config.data.universe),
        date_start=config.data.start,
        date_end=config.data.end,
        cost_basis=CostBasis.NET,
        cost_assumptions={"spread_bps": reference_cost},
        n_trials=expected_trials,
        notes=(
            "SURVIVORSHIP_BIAS_RISK = True. L'univers est choisi parmi les titres qui cotent "
            "encore, donc il exclut ceux dont l'écart ne s'est jamais refermé. L'étude ne "
            "peut pas conclure au-delà de la réplication."
        ),
    ) as run:
        # ------------------------------------------------------------------ #
        # 1. Les données
        # ------------------------------------------------------------------ #
        with stage("chargement", experiment_id=run.record.experiment_id):
            provider = YahooProvider(on_missing="drop")
            requested = list(config.data.universe)
            raw = provider.fetch(
                requested,
                start=config.data.start,
                end=config.data.end,
                auto_adjust=False,
            )
            manifests.append(provider.manifest().model_dump(mode="json"))
            adjusted = to_wide(raw, "adj_close")
            closes = to_wide(raw, "close")
            volumes = to_wide(raw, "volume")
            missing = sorted(set(requested) - set(adjusted.columns))
            if benchmark not in adjusted.columns:
                raise ConfigError(f"le repère de marché {benchmark} n'a pas été rendu par Yahoo.")

            all_returns = to_returns(adjusted)
            market_returns = all_returns[benchmark].dropna()
            stock_returns = all_returns.drop(columns=[benchmark])
            dollar_volume = (closes * volumes).drop(columns=[benchmark])
            liquidity = dollar_volume.rolling(int(params["correlation_window"])).median()
            liquid = (liquidity >= float(params["min_dollar_volume"])).reindex(stock_returns.index)
            filled_returns = stock_returns.fillna(0.0)

            first_days = adjusted.apply(lambda column: column.first_valid_index())
            coverage_rows = [
                {
                    "threshold": cut,
                    "n_available": int((first_days <= pd.Timestamp(cut)).sum()),
                }
                for cut in ("1996-01-02", "1998-01-02", "2000-01-03", "2005-01-03", "2010-01-04")
            ]
            universe_frame = pd.DataFrame(
                [
                    {
                        "symbol": symbol,
                        "first_day": str(first_days[symbol].date()),
                        "last_day": str(adjusted[symbol].last_valid_index().date()),
                        "n_days": int(adjusted[symbol].notna().sum()),
                    }
                    for symbol in sorted(adjusted.columns)
                ]
            )
            _write_table(universe_frame, "universe")
            _write_table(pd.DataFrame(coverage_rows), "universe_coverage")
            _write_table(
                pd.DataFrame([{"symbol": s, "reason": "refusé par Yahoo"} for s in missing]),
                "universe_missing",
            )
            probe = _probe_delisted(
                provider, list(params["delisted_probe"]), config.data.start, config.data.end
            )
            _write_table(probe, "delisted_probe")

        # ------------------------------------------------------------------ #
        # 2. Le cas de référence, et les quatre règles
        # ------------------------------------------------------------------ #
        with stage("reference", experiment_id=run.record.experiment_id):
            reference = _run_pipeline(stock_returns, liquid, params, rules)
            reference_weights = reference.weights[reference_rule.name]
            reference_result = _backtest(reference_weights, filled_returns, reference_cost)
            first_decision = reference_weights.dropna(how="all").index[0]
            first_trade = filled_returns.index[filled_returns.index.get_loc(first_decision) + 1]
            gross = reference_result.gross_returns.loc[first_trade:]
            net = reference_result.net_returns.loc[first_trade:]
            _univers_sa = (
                "grandes capitalisations américaines via Yahoo, biais de survie déclaré, règle de l'article"
            )
            save_series(
                RESULTS,
                "statarb_gross",
                gross,
                sample=SampleTag.IN_SAMPLE,
                basis=CostBasis.GROSS,
                frequency=Frequency.DAILY,
                universe=_univers_sa,
            )
            save_series(
                RESULTS,
                "statarb_net",
                net,
                sample=SampleTag.IN_SAMPLE,
                basis=CostBasis.NET,
                frequency=Frequency.DAILY,
                universe=_univers_sa,
                cost_assumptions="5 pb par unité négociée, l'hypothèse de l'article",
            )

            full_turnover = turnover_series(
                reference_result.executed_weights.loc[first_trade:],
                filled_returns,
                drifted=True,
                convention="full_sum",
            )
            reference_rotation = annualized_turnover(full_turnover, DAILY)

            rule_rows: list[dict[str, Any]] = []
            for rule in rules:
                result = _backtest(reference.weights[rule.name], filled_returns, reference_cost)
                rule_gross = result.gross_returns.loc[first_trade:]
                rule_net = result.net_returns.loc[first_trade:]
                row = _performance_row(rule.name, rule_gross, rule_net, params)
                rotation, rule_breakeven = _cost_profile(result, rule_gross, filled_returns, first_trade)
                row["turnover_annual_full_sum"] = rotation
                row["breakeven_cost_bps"] = rule_breakeven
                row["mean_positions"] = float(reference.n_positions[rule.name].replace(0.0, np.nan).mean())
                rule_rows.append(row)
                if rule.name != reference_rule.name:
                    counter = counter.record("rules", rule.name, row["sharpe_net_full"])
            _write_table(pd.DataFrame(rule_rows), "trading_rules")

        # ------------------------------------------------------------------ #
        # 3. La réplication, année par année
        # ------------------------------------------------------------------ #
        with stage("replication", experiment_id=run.record.experiment_id):
            annual_rows: list[dict[str, Any]] = []
            for year in sorted({d.year for d in net.index}):
                block_net = net.loc[net.index.year == year]
                block_gross = gross.loc[gross.index.year == year]
                annual_rows.append(
                    {
                        "year": year,
                        "n_days": len(block_net),
                        "sharpe_gross": _sharpe(block_gross),
                        "sharpe_net": _sharpe(block_net),
                        "paper_sharpe": PAPER_ANNUAL_SHARPE.get(year, float("nan")),
                        "return_net_annual_pct": float(block_net.mean() * 252.0 * 100.0),
                    }
                )
            annual_frame = pd.DataFrame(annual_rows)
            _write_table(annual_frame, "annual_sharpe")

            decay_rows: list[dict[str, Any]] = []
            for label, (start, end) in _windows(params).items():
                block_net = _slice(net, start, end)
                block_gross = _slice(gross, start, end)
                decay_rows.append(
                    {
                        "window": label,
                        "start": str(block_net.index[0].date()) if len(block_net) else "",
                        "end": str(block_net.index[-1].date()) if len(block_net) else "",
                        "n_days": len(block_net),
                        "sharpe_gross": _sharpe(block_gross),
                        "sharpe_net": _sharpe(block_net),
                        "tstat_net": sharpe_tstat(block_net, frequency=DAILY)
                        if len(block_net) > 3
                        else float("nan"),
                        "return_net_annual_pct": float(block_net.mean() * 252.0 * 100.0),
                        "vol_annual_pct": volatility(block_net, frequency=DAILY) * 100.0,
                        "max_drawdown_pct": max_drawdown(block_net) * 100.0,
                    }
                )
            decay_frame = pd.DataFrame(decay_rows)
            _write_table(decay_frame, "decay")

        # ------------------------------------------------------------------ #
        # 4. Les diagnostics du processus de retour à la moyenne
        # ------------------------------------------------------------------ #
        with stage("diagnostics", experiment_id=run.record.experiment_id):
            member_counts = reference.membership.sum(axis=1)
            eligible_counts = reference.eligible.sum(axis=1)
            stationary_counts = reference.s_score.notna().sum(axis=1)
            diagnostic_rows: list[dict[str, Any]] = []
            for label, (start, end) in {"full": (None, None), **_windows(params)}.items():
                mask = pd.Series(True, index=reference.s_score.index)
                if start is not None:
                    mask &= mask.index >= pd.Timestamp(start)
                if end is not None:
                    mask &= mask.index <= pd.Timestamp(end)
                mask &= member_counts > 0
                if not bool(mask.any()):
                    continue
                tau = reference.characteristic_days.loc[mask]
                diagnostic_rows.append(
                    {
                        "window": label,
                        "n_days": int(mask.sum()),
                        "median_universe_size": float(member_counts[mask].median()),
                        "median_characteristic_days": float(np.nanmedian(tau.to_numpy())),
                        "median_half_life_days": float(np.nanmedian(tau.to_numpy())) * math.log(2.0),
                        "median_equilibrium_vol_bps": float(
                            np.nanmedian(reference.equilibrium_volatility.loc[mask].to_numpy()) * 1e4
                        ),
                        "share_stationary": float((stationary_counts[mask] / member_counts[mask]).mean()),
                        "share_eligible": float((eligible_counts[mask] / member_counts[mask]).mean()),
                        "median_abs_s_score": float(
                            np.nanmedian(np.abs(reference.s_score.loc[mask].to_numpy()))
                        ),
                        "median_drift_bps": float(np.nanmedian(reference.drift.loc[mask].to_numpy()) * 1e4),
                        "median_n_factors": float(reference.n_factors[mask].median()),
                        "median_variance_share": float(reference.variance_share[mask].median()),
                    }
                )
            diagnostics_frame = pd.DataFrame(diagnostic_rows)
            _write_table(diagnostics_frame, "ou_diagnostics")

            base_member = stock_returns.notna().rolling(int(params["correlation_window"])).sum() == float(
                params["correlation_window"]
            )
            n_base = int(base_member.to_numpy().sum())
            n_kept = int((base_member & reference.membership).to_numpy().sum())
            liquidity_rows = [
                {
                    "statistic": "part de couples titre-date retirés par le seuil de liquidité",
                    "value": float(1.0 - n_kept / max(n_base, 1)),
                },
                {
                    "statistic": "seuil retenu, en dollars de volume médian quotidien",
                    "value": float(params["min_dollar_volume"]),
                },
                {
                    "statistic": "taille médiane de l'univers négociable",
                    "value": float(member_counts[member_counts > 0].median()),
                },
                {
                    "statistic": "taille minimale de l'univers négociable",
                    "value": float(member_counts[member_counts > 0].min()),
                },
                {
                    "statistic": "taille maximale de l'univers négociable",
                    "value": float(member_counts.max()),
                },
            ]
            _write_table(pd.DataFrame(liquidity_rows), "liquidity_filter")
            _write_table(
                pd.DataFrame(
                    [{"statistic": key, "value": value} for key, value in reference.diagnostics.items()]
                ),
                "pipeline_diagnostics",
            )

        # ------------------------------------------------------------------ #
        # 5. La robustesse, grille et variantes
        # ------------------------------------------------------------------ #
        with stage("robustesse", experiment_id=run.record.experiment_id):
            grid_rows: list[dict[str, Any]] = []
            grid_returns: dict[str, pd.Series] = {}
            for n_components, estimation_window in grid_pairs:
                label = f"nc{n_components}_ew{estimation_window}"
                if n_components == int(params["n_components"]) and estimation_window == int(
                    params["estimation_window"]
                ):
                    cell_gross, cell_net = gross, net
                    rotation = reference_rotation
                    cell_breakeven = breakeven_cost_bps(gross, full_turnover, frequency=DAILY)
                else:
                    outcome = _run_pipeline(
                        stock_returns,
                        liquid,
                        params,
                        [reference_rule],
                        n_components=n_components,
                        estimation_window=estimation_window,
                    )
                    result = _backtest(outcome.weights[reference_rule.name], filled_returns, reference_cost)
                    cell_gross = result.gross_returns.loc[first_trade:]
                    cell_net = result.net_returns.loc[first_trade:]
                    rotation, cell_breakeven = _cost_profile(result, cell_gross, filled_returns, first_trade)
                    del outcome, result
                row = _performance_row(label, cell_gross, cell_net, params)
                row["n_components"] = n_components
                row["estimation_window"] = estimation_window
                row["turnover_annual_full_sum"] = rotation
                row["breakeven_cost_bps"] = cell_breakeven
                grid_rows.append(row)
                grid_returns[label] = cell_net
                counter = counter.record("grid", label, row["sharpe_net_full"])
            grid_frame = pd.DataFrame(grid_rows)
            _write_table(grid_frame, "parameter_grid")

            variant_rows: list[dict[str, Any]] = []

            def _variant(family: str, label: str, **overrides: Any) -> None:
                """Déroule une variante, l'enregistre comme essai et note sa ligne."""
                nonlocal counter
                outcome = _run_pipeline(stock_returns, liquid, params, [reference_rule], **overrides)
                result = _backtest(outcome.weights[reference_rule.name], filled_returns, reference_cost)
                variant_gross = result.gross_returns.loc[first_trade:]
                variant_net = result.net_returns.loc[first_trade:]
                row = _performance_row(label, variant_gross, variant_net, params)
                row["family"] = family
                row["median_n_factors"] = float(outcome.n_factors.median())
                rotation, variant_breakeven = _cost_profile(
                    result, variant_gross, filled_returns, first_trade
                )
                row["turnover_annual_full_sum"] = rotation
                row["breakeven_cost_bps"] = variant_breakeven
                variant_rows.append(row)
                counter = counter.record(family, label, row["sharpe_net_full"])
                del outcome, result

            for n_components in params["extra_n_components"]:
                _variant("n_components", f"nc{int(n_components)}", n_components=int(n_components))
            for share in params["variance_shares"]:
                _variant(
                    "variance_share",
                    f"share{int(float(share) * 100)}",
                    n_components=None,
                    variance_share=float(share),
                )
            for window in params["extra_correlation_windows"]:
                _variant("correlation_window", f"corr{int(window)}", correlation_window=int(window))
            for days in params["extra_reestimation_days"]:
                _variant("reestimation", f"every{int(days)}", reestimation_days=int(days))
            for days in params["extra_characteristic_days"]:
                value = float(days)
                _variant(
                    "characteristic_days",
                    "tau_aucun" if value == 0.0 else f"tau{int(value)}",
                    max_characteristic_days=None if value == 0.0 else value,
                )
            for variant in params["s_score_variants"]:
                if variant == "sans_centrage":
                    _variant("s_score", variant, centre_across_names=False)
                else:
                    _variant("s_score", variant, use_modified_s_score=True)
            for variant in params["hedge_variants"]:
                _variant("hedge", variant, hedge_at_entry=False)
            variant_frame = pd.DataFrame(variant_rows)
            _write_table(variant_frame, "variants")

            # Les deux lectures du livre négocié. Le cas de référence replie les
            # portefeuilles propres sur les titres ; l'article ne le fait pas
            # pour les composantes principales, sections 5.1 et 5.3.
            reference_positions = reference.positions[reference_rule.name]
            hedged_panel = filled_returns.copy()
            hedged_panel[benchmark] = market_returns.reindex(filled_returns.index).fillna(0.0)
            convention_books: dict[str, tuple[pd.DataFrame, pd.DataFrame]] = {
                "actions_plus_repere": (
                    market_hedged_book(
                        reference_positions,
                        filled_returns,
                        market_returns,
                        window=int(params["market_beta_window"]),
                        benchmark=benchmark,
                    ),
                    hedged_panel,
                ),
                "actions_seules": (reference_positions, filled_returns),
            }
            convention_rows: list[dict[str, Any]] = []
            for label in params["book_conventions"]:
                book, panel = convention_books[str(label)]
                outcome_result = _backtest(book, panel, reference_cost)
                book_gross = outcome_result.gross_returns.loc[first_trade:]
                book_net = outcome_result.net_returns.loc[first_trade:]
                row = _performance_row(str(label), book_gross, book_net, params)
                rotation, book_breakeven = _cost_profile(outcome_result, book_gross, panel, first_trade)
                row["turnover_annual_full_sum"] = rotation
                row["breakeven_cost_bps"] = book_breakeven
                row["median_gross_exposure"] = float(
                    book.abs().sum(axis=1).loc[first_trade:].replace(0.0, np.nan).median()
                )
                row["tstat_net_post_publication"] = float(
                    sharpe_tstat(_slice(book_net, params["publication_date"], None), frequency=DAILY)
                )
                convention_rows.append(row)
                counter = counter.record("convention", str(label), row["sharpe_net_full"])
                del outcome_result
            convention_frame = pd.DataFrame(convention_rows)
            _write_table(convention_frame, "conventions")

            cuts = [pd.Timestamp(b) for b in params["subperiod_breakpoints"]]
            bounds = [net.index[0], *cuts, net.index[-1]]
            subperiods = subperiod_performance(
                net,
                breakpoints=cuts,
                frequency=DAILY,
                labels=[f"{start:%Y-%m} à {end:%Y-%m}" for start, end in itertools.pairwise(bounds)],
            )
            _write_table(subperiods, "subperiods")

        # ------------------------------------------------------------------ #
        # 6. Les coûts, et le chiffre qui décide
        # ------------------------------------------------------------------ #
        with stage("couts", experiment_id=run.record.experiment_id):
            breakeven = breakeven_cost_bps(gross, full_turnover, frequency=DAILY)
            annual_full_turnover = reference_rotation
            cost_rows: list[dict[str, Any]] = []
            net_by_rate: dict[float, pd.Series] = {}
            for rate in params["cost_bps_grid"]:
                value = float(rate)
                result = _backtest(reference_weights, filled_returns, value)
                rate_net = result.net_returns.loc[first_trade:]
                net_by_rate[value] = rate_net
                cost_rows.append(
                    {
                        "cost_bps": value,
                        "sharpe_net_full": _sharpe(rate_net),
                        "sharpe_net_paper": _sharpe(_slice(rate_net, *_windows(params)["paper"])),
                        "sharpe_net_post_publication": _sharpe(
                            _slice(rate_net, *_windows(params)["post_publication"])
                        ),
                        "return_net_annual_pct": float(rate_net.mean() * 252.0 * 100.0),
                    }
                )
                counter = counter.record("costs", f"cost{value:g}", cost_rows[-1]["sharpe_net_full"])
                del result
            cost_frame = pd.DataFrame(cost_rows)
            cost_frame.insert(0, "gross_return_annual_pct", float(gross.mean() * 252.0 * 100.0))
            cost_frame.insert(0, "turnover_annual_full_sum", annual_full_turnover)
            cost_frame.insert(0, "breakeven_cost_bps", breakeven)
            _write_table(cost_frame, "costs")

            def _evaluate_multiplier(multiplier: float) -> float:
                """Rend le ratio de Sharpe net au multiple de coût demandé."""
                nonlocal counter
                rate = reference_cost * multiplier
                result = _backtest(reference_weights, filled_returns, rate)
                value = _sharpe(result.net_returns.loc[first_trade:])
                counter = counter.record("cost_multiple", f"x{multiplier:g}", value)
                return value

            cost_analysis = cost_multiplier_analysis(_evaluate_multiplier, positive_multipliers)
            multiple_frame = cost_analysis.table.copy()
            multiple_frame["status"] = cost_analysis.status
            multiple_frame["breakeven_multiplier"] = (
                cost_analysis.breakeven_multiplier
                if cost_analysis.breakeven_multiplier is not None
                else float("nan")
            )
            _write_table(multiple_frame, "cost_multiples")

        # ------------------------------------------------------------------ #
        # 7. Les contrôles statistiques
        # ------------------------------------------------------------------ #
        with stage("validation", experiment_id=run.record.experiment_id):
            performance_matrix = pd.DataFrame(grid_returns).dropna()
            pbo_result = probability_of_backtest_overfitting(performance_matrix, n_splits=8, frequency=DAILY)

            def best_of_path(path: Any) -> float:
                """Choisit la meilleure cellule sur l'apprentissage, la juge sur le test.

                Une série figée rend des chemins identiques, ce qui ne mesure
                rien. La validation croisée juge donc le PROCESSUS de sélection.
                """
                pieces: list[pd.Series] = []
                for segment in path.segments:
                    train = performance_matrix.iloc[segment.train_index]
                    test = performance_matrix.iloc[segment.test_index]
                    best = max(performance_matrix.columns, key=lambda column: _sharpe(train[column]))
                    pieces.append(test[best])
                return _sharpe(pd.concat(pieces).sort_index())

            cv = CombinatorialPurgedCV.from_config(config.validation)
            distribution = cpcv_performance_distribution(
                cv, performance_matrix, best_of_path, metric_name="sharpe"
            )
            cpcv_frame = distribution.summary.rename("value").reset_index()
            cpcv_frame.columns = ["statistic", "value"]
            _write_table(cpcv_frame, "cpcv_distribution")

            holdout = _slice(net_by_rate[reference_cost], params["publication_date"], None)
            oos_sharpe = _sharpe(holdout)
            oos_tstat = sharpe_tstat(holdout, frequency=DAILY)
            n_trials = counter.n_trials()
            if n_trials != expected_trials:
                raise ConfigError(
                    f"{n_trials} essais enregistrés contre {expected_trials} déduits des grilles. "
                    "Le compte du registre et celui du ratio de Sharpe dégonflé divergeraient."
                )
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
                    frequency=DAILY,
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

            grid_tstats = []
            for label in grid_returns:
                block = _slice(grid_returns[label], params["publication_date"], None)
                grid_tstats.append(sharpe_tstat(block, frequency=DAILY))
            pvalues = [2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(t) / math.sqrt(2.0)))) for t in grid_tstats]
            multiplicity = adjust_pvalues(pvalues, method="holm", alpha=0.05)
            _write_table(
                pd.DataFrame(
                    {
                        "configuration": list(grid_returns),
                        "tstat_post_publication": grid_tstats,
                        "pvalue": pvalues,
                        "adjusted_pvalue": multiplicity.adjusted_pvalues,
                        "rejected": multiplicity.rejected,
                    }
                ),
                "multiple_testing",
            )

            block = int(params["bootstrap_block_days"])
            draws = int(params["bootstrap_resamples"])
            sample = holdout.to_numpy()
            replicates = np.empty(draws, dtype=float)
            for draw in range(draws):
                starts = bootstrap_generator.integers(0, len(sample), size=int(np.ceil(len(sample) / block)))
                joined = np.concatenate([sample[s : s + block] for s in starts])[: len(sample)]
                replicates[draw] = joined.mean() * 252.0
            _write_table(
                pd.DataFrame(
                    {
                        "statistic": ["rendement annualisé net, après publication"],
                        "observed": [float(sample.mean() * 252.0)],
                        "p05": [float(np.quantile(replicates, 0.05))],
                        "p95": [float(np.quantile(replicates, 0.95))],
                        "share_positive": [float((replicates > 0.0).mean())],
                        "n_resamples": [draws],
                        "block_days": [block],
                    }
                ),
                "bootstrap",
            )

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
            market_aligned = market_returns.reindex(net.index).fillna(0.0)

            fig, _ = viz.equity_curve(
                {
                    "Arbitrage statistique, brut": gross,
                    f"Arbitrage statistique, net de {reference_cost:g} points de base": net,
                },
                benchmark=market_aligned,
                benchmark_label="Fonds indiciel du S&P 500",
                log_scale=True,
                currency="$ US",
                title=(
                    "Richesse cumulée de l'arbitrage statistique, base 1 dollar des "
                    f"États-Unis au {net.index[0]:%Y-%m-%d}"
                ),
            )
            figure_specs.append(
                (
                    _save_figure(fig, "equity_curve"),
                    "performance",
                    "Richesse cumulée en échelle logarithmique, dollars des États-Unis.",
                )
            )

            fig, _ = viz.underwater(net, title="Repli de l'arbitrage statistique, net de frais")
            figure_specs.append(
                (
                    _save_figure(fig, "underwater"),
                    "robustness",
                    "Distance au sommet précédent, en points de pourcentage.",
                )
            )

            fig, _ = viz.rolling_metric(
                net,
                metric="sharpe",
                window=252,
                frequency=DAILY,
                title="Ratio de Sharpe glissant sur un an, net de frais",
            )
            figure_specs.append(
                (
                    _save_figure(fig, "rolling_sharpe"),
                    "out_of_sample",
                    "Ratio de Sharpe annualisé sur fenêtre glissante de 252 séances.",
                )
            )

            fig, _ = viz.cost_sensitivity(
                list(cost_analysis.table["multiplier"]),
                list(cost_analysis.table["metric"]),
                threshold=0.0,
                metric_label="Ratio de Sharpe net",
                title="Sensibilité au multiple de coût, cas de référence",
            )
            figure_specs.append(
                (
                    _save_figure(fig, "cost_sensitivity"),
                    "costs",
                    "Ratio de Sharpe net selon le multiple appliqué aux cinq points de base.",
                )
            )

            fig, _ = viz.parameter_heatmap(
                grid_frame,
                x="estimation_window",
                y="n_components",
                metric="sharpe_net_full",
                x_label="Fenêtre d'estimation, en séances",
                y_label="Nombre de composantes principales",
                metric_label="Ratio de Sharpe net",
                title="Ratio de Sharpe net selon le nombre de facteurs et la fenêtre d'estimation",
            )
            figure_specs.append(
                (
                    _save_figure(fig, "parameter_heatmap"),
                    "robustness",
                    "Une case par couple de réglages, ratio de Sharpe net sur tout l'échantillon.",
                )
            )

            fig, _ = viz.subperiod_bars(
                subperiods,
                metric_column="sharpe",
                error_column="sharpe_se_lo",
                title="Ratio de Sharpe net par sous-période",
            )
            figure_specs.append(
                (
                    _save_figure(fig, "subperiod_bars"),
                    "robustness",
                    "Ratio de Sharpe annualisé et son intervalle à 95 pour cent.",
                )
            )

            fig, _ = viz.return_histogram(
                net, title="Distribution quotidienne de l'arbitrage statistique, net de frais"
            )
            figure_specs.append(
                (
                    _save_figure(fig, "return_histogram"),
                    "statistical_tests",
                    "Histogramme des rendements quotidiens et loi normale de même moyenne.",
                )
            )

            fig, _ = viz.qq_plot(net, title="Quantiles du rendement net contre quantiles normaux")
            figure_specs.append(
                (
                    _save_figure(fig, "qq_plot"),
                    "statistical_tests",
                    "Écart à la normalité des rendements quotidiens nets.",
                )
            )

            fig, _ = viz.correlation_heatmap(
                pd.DataFrame({"Marché": market_aligned, "Brut": gross, "Net": net}),
                title="Corrélations quotidiennes de la stratégie et du marché",
            )
            figure_specs.append(
                (
                    _save_figure(fig, "correlation_heatmap"),
                    "factor_attribution",
                    "Corrélations de Pearson sur les séances communes.",
                )
            )

        # ------------------------------------------------------------------ #
        # 9. Le verdict
        # ------------------------------------------------------------------ #
        tolerance = float(params["verdict"]["replication_tolerance"])
        targets = params["paper_targets"]
        share_rows = variant_frame.set_index("configuration")
        median_tau = float(diagnostics_frame.set_index("window").loc["paper", "median_characteristic_days"])
        median_factors_55 = float(share_rows.loc["share55", "median_n_factors"])
        equilibrium_vol_bps = float(
            diagnostics_frame.set_index("window").loc["paper", "median_equilibrium_vol_bps"]
        )

        source = "Avellaneda et Lee (2010), Quantitative Finance 10(7)"
        checks = (
            ReplicationCheck(
                quantity="ratio de Sharpe, 15 composantes, 1997-2007",
                published=float(targets["sharpe_pca15_1997_2007"]),
                ours=float(decay_frame.set_index("window").loc["paper", "sharpe_net"]),
                tolerance=tolerance,
                source=f"{source}, table 6, page 774",
            ),
            ReplicationCheck(
                quantity="ratio de Sharpe, 15 composantes, 2003-2007",
                published=float(targets["sharpe_pca15_2003_2007"]),
                ours=float(decay_frame.set_index("window").loc["paper_late", "sharpe_net"]),
                tolerance=tolerance,
                source=f"{source}, résumé page 761 et table 6",
            ),
            ReplicationCheck(
                quantity="ratio de Sharpe, 1 portefeuille propre, 2002-2007",
                published=float(targets["sharpe_one_eigenportfolio_2002_2007"]),
                ours=float(share_rows.loc["nc1", "sharpe_net_table8"]),
                tolerance=tolerance,
                source=f"{source}, table 8, page 776",
            ),
            ReplicationCheck(
                quantity="ratio de Sharpe, 55 pour cent de variance, 2002-2007",
                published=float(targets["sharpe_share55_2002_2007"]),
                ours=float(share_rows.loc["share55", "sharpe_net_table8"]),
                tolerance=tolerance,
                source=f"{source}, table 8, page 776",
            ),
            ReplicationCheck(
                quantity="ratio de Sharpe, 65 pour cent de variance, 2002-2007",
                published=float(targets["sharpe_share65_2002_2007"]),
                ours=float(share_rows.loc["share65", "sharpe_net_table8"]),
                tolerance=tolerance,
                source=f"{source}, table 8, page 776",
            ),
            ReplicationCheck(
                quantity="temps de retour à la moyenne médian, en séances",
                published=float(targets["mean_reversion_days"]),
                ours=median_tau,
                tolerance=3.0,
                tolerance_kind="absolute",
                source=f"{source}, page 771",
            ),
            ReplicationCheck(
                quantity="volatilité d'équilibre du résidu, en points de base",
                published=float(targets["residual_equilibrium_vol_bps"]),
                ours=equilibrium_vol_bps,
                tolerance=150.0,
                tolerance_kind="absolute",
                source=f"{source}, page 771",
            ),
            ReplicationCheck(
                quantity="nombre de facteurs à 55 pour cent de variance",
                published=float(targets["n_factors_at_share55"]),
                ours=median_factors_55,
                tolerance=10.0,
                tolerance_kind="absolute",
                source=f"{source}, conclusion pages 779 et 780",
            ),
        )
        _write_table(replication_table(checks), "replication_checks")

        criteria = VerdictCriteria(**params["verdict"])
        positive_share = float((subperiods["sharpe"] > 0.0).mean())
        correlation = float(net.corr(market_aligned))
        evidence = VerdictEvidence(
            hypothesis_supported=bool(float(gross.mean()) > 0.0),
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
            portfolio_correlation=correlation,
            notes=(
                "SURVIVORSHIP_BIAS_RISK = True. L'univers ne porte que des titres qui cotent "
                "encore, ce qui retire ceux dont l'écart ne s'est jamais refermé. Le verdict "
                "ne peut pas dépasser REPLICATED, quelle que soit la valeur des critères."
            ),
        )
        verdict, reasons = decide_verdict(evidence, criteria)
        run.set_verdict(verdict)

        metric_values = {
            "cout_de_rentabilite_bps": breakeven,
            "rotation_annuelle_somme_entiere": annual_full_turnover,
            "sharpe_net_fenetre_de_larticle": float(
                decay_frame.set_index("window").loc["paper", "sharpe_net"]
            ),
            "sharpe_net_1997_2002": float(decay_frame.set_index("window").loc["paper_early", "sharpe_net"]),
            "sharpe_net_2003_2007": float(decay_frame.set_index("window").loc["paper_late", "sharpe_net"]),
            "sharpe_net_apres_publication": oos_sharpe,
            "sharpe_brut_fenetre_de_larticle": float(
                decay_frame.set_index("window").loc["paper", "sharpe_gross"]
            ),
            "rendement_brut_annuel_pct": float(gross.mean() * 252.0 * 100.0),
            "volatilite_annuelle_pct": volatility(net, frequency=DAILY) * 100.0,
            "pire_repli_pct": max_drawdown(net) * 100.0,
            "beta_au_marche": market_beta(net, market_aligned),
            "correlation_au_marche": correlation,
            "temps_de_retour_median_seances": median_tau,
            "demi_vie_mediane_seances": median_tau * math.log(2.0),
            "probabilite_de_surapprentissage": pbo_result.pbo,
            "sharpe_degonfle": deflated_value,
            "t_apres_correction": adjusted_tstat,
            "part_de_sous_periodes_positives": positive_share,
            "cpcv_sharpe_moyen": float(distribution.summary["mean"]),
            "cpcv_part_de_chemins_negatifs": float(distribution.negative_share),
        }
        labels = {
            "cout_de_rentabilite_bps": MetricLabel(SampleTag.IN_SAMPLE, CostBasis.GROSS),
            "rotation_annuelle_somme_entiere": MetricLabel(SampleTag.IN_SAMPLE, CostBasis.GROSS),
            "sharpe_net_fenetre_de_larticle": MetricLabel(SampleTag.IN_SAMPLE, CostBasis.NET),
            "sharpe_net_1997_2002": MetricLabel(SampleTag.IN_SAMPLE, CostBasis.NET),
            "sharpe_net_2003_2007": MetricLabel(SampleTag.IN_SAMPLE, CostBasis.NET),
            "sharpe_net_apres_publication": MetricLabel(SampleTag.OUT_OF_SAMPLE, CostBasis.NET),
            "sharpe_brut_fenetre_de_larticle": MetricLabel(SampleTag.IN_SAMPLE, CostBasis.GROSS),
            "rendement_brut_annuel_pct": MetricLabel(SampleTag.IN_SAMPLE, CostBasis.GROSS),
            "volatilite_annuelle_pct": MetricLabel(SampleTag.IN_SAMPLE, CostBasis.NET),
            "pire_repli_pct": MetricLabel(SampleTag.IN_SAMPLE, CostBasis.NET),
            "beta_au_marche": MetricLabel(SampleTag.IN_SAMPLE, CostBasis.NET),
            "correlation_au_marche": MetricLabel(SampleTag.IN_SAMPLE, CostBasis.NET),
            "temps_de_retour_median_seances": MetricLabel(SampleTag.IN_SAMPLE, CostBasis.GROSS),
            "demi_vie_mediane_seances": MetricLabel(SampleTag.IN_SAMPLE, CostBasis.GROSS),
            "probabilite_de_surapprentissage": MetricLabel(SampleTag.VALIDATION, CostBasis.NET),
            "sharpe_degonfle": MetricLabel(SampleTag.OUT_OF_SAMPLE, CostBasis.NET),
            "t_apres_correction": MetricLabel(SampleTag.OUT_OF_SAMPLE, CostBasis.NET),
            "part_de_sous_periodes_positives": MetricLabel(SampleTag.VALIDATION, CostBasis.NET),
            "cpcv_sharpe_moyen": MetricLabel(SampleTag.OUT_OF_SAMPLE, CostBasis.NET),
            "cpcv_part_de_chemins_negatifs": MetricLabel(SampleTag.OUT_OF_SAMPLE, CostBasis.NET),
        }
        metrics = metrics_table(metric_values, labels)
        _write_table(metrics, "metrics")
        for name, value in metric_values.items():
            run.log_metric(name, value, sample=labels[name].sample)

        payload = {
            "study": "007_statistical_arbitrage",
            "experiment_id": run.record.experiment_id,
            "seed": config.seed,
            "verdict": verdict.value,
            "reasons": reasons,
            "survivorship_bias_risk": bool(SURVIVORSHIP_BIAS_RISK),
            "n_trials": n_trials,
            "trials_by_family": {family: counter.n_trials(family) for family in counter.families()},
            "metrics": metric_values,
            "metric_samples": {name: label.sample.value for name, label in labels.items()},
            "cost_basis": {name: label.cost_basis.value for name, label in labels.items()},
            "samples": {
                "first_trade": str(first_trade.date()),
                "last_day": str(net.index[-1].date()),
                "paper_window": [params["paper_start"], params["paper_end"]],
                "post_publication_window": [params["publication_date"], str(net.index[-1].date())],
            },
            "universe": {
                "requested": len(requested),
                "returned": len(adjusted.columns),
                "missing": missing,
                "delisted_probe_returned": int(probe["returned"].sum()),
                "delisted_probe_requested": len(probe),
            },
            "cost_assumptions_bps": {"spread_bps": reference_cost},
        }
        (RESULTS / "metrics.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        report_tables = [
            ReportTable("annual_sharpe", "replication", annual_frame, "Sharpe par année contre table 6."),
            ReportTable("decay", "performance", decay_frame, "La décroissance par fenêtre."),
            ReportTable("costs", "costs", cost_frame, "Le coût de seuil de rentabilité."),
            ReportTable("parameter_grid", "robustness", grid_frame, "Seize réglages."),
            ReportTable("variants", "robustness", variant_frame, "Les variantes hors grille."),
            ReportTable(
                "conventions",
                "robustness",
                convention_frame,
                "Les deux lectures du livre négocié chez l'article.",
            ),
            ReportTable("subperiods", "robustness", subperiods, "Sous-périodes."),
            ReportTable("ou_diagnostics", "statistical_tests", diagnostics_frame, "Le processus estimé."),
            ReportTable("trials", "statistical_tests", trials_frame, "Le compte des essais."),
            ReportTable("universe_coverage", "data", pd.DataFrame(coverage_rows), "Profondeur."),
            ReportTable("delisted_probe", "data", probe, "Les titres retirés, demandés un par un."),
        ]
        report_figures = [
            ReportFigure(name, section, FIGURES / f"{name}.png", caption)
            for name, section, caption in figure_specs
        ]
        report = StudyReport(
            study_name="007_statistical_arbitrage",
            experiment_id=run.record.experiment_id,
            hypothesis=config.hypothesis,
            paper=config.paper or "",
            criteria=criteria,
            evidence=evidence,
            sections=_sections(metric_values, decay_frame, breakeven, reference_cost),
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
                name="statistical_arbitrage_pca",
                family="mean_reversion",
                paper=config.paper,
                asset_classes=[AssetClass.EQUITY],
                horizon="signal quotidien, détention jusqu'au retour du s-score",
                economic_rationale=["friction", "biais comportemental"],
                inputs=[
                    "cours de clôture quotidiens ajustés, fournisseur Yahoo",
                    "volume quotidien, pour le filtre de liquidité",
                ],
                known_risks=[
                    "L'univers est choisi parmi les titres qui cotent encore, biais du survivant.",
                    "La rotation quotidienne rend la stratégie sensible au moindre point de base.",
                    "Le débouclage forcé d'août 2007 frappe toutes les variantes en même temps.",
                    "L'estimateur de la vitesse de rappel est biaisé sur soixante points.",
                    "Notre couverture négocie la jambe de facteurs, ce que l'article ne fait "
                    "pas pour ses variantes en composantes principales, et le coût de seuil "
                    "en dépend.",
                ],
                validation_status=verdict,
                verdict_experiment_id=run.record.experiment_id,
                created=pd.Timestamp.today().date(),
                last_modified=pd.Timestamp.today().date(),
                notes=(
                    "Étude 007. Le mécanisme invoqué est la rémunération du fournisseur de "
                    "liquidité, qui achète ce que personne ne veut et vend ce que tout le monde "
                    "veut. La friction retenue est le coût de rotation d'un signal qui change de "
                    "position tous les jours. Le verdict est déduit par "
                    "quantlab.reporting.study.decide_verdict, et l'étude déclare que le biais du "
                    "survivant lui interdit de dépasser la réplication."
                ),
            ),
            overwrite=True,
        )
        LOG.info("étude terminée", extra={"verdict": verdict.value, "n_trials": n_trials})


def _sections(
    metric_values: Mapping[str, float],
    decay_frame: pd.DataFrame,
    breakeven: float,
    reference_cost: float,
) -> dict[str, str]:
    """Rend la prose des quinze sections du rapport HTML."""
    windows = decay_frame.set_index("window")
    return {
        "hypothesis": (
            "Le résidu d'une action face aux composantes principales de son univers revient-il "
            "à sa moyenne assez vite, et assez loin, pour payer la rotation qu'il exige ?"
        ),
        "paper": (
            "Avellaneda et Lee (2010), Statistical Arbitrage in the US Equities Market, "
            "Quantitative Finance 10(7), 761-782."
        ),
        "methodology": (
            "Analyse en composantes principales sur une fenêtre glissante d'un an, régression du "
            "titre sur les facteurs sur soixante séances, modèle de retour à la moyenne sur le "
            "résidu cumulé, et règle tout ou rien sur le s-score."
        ),
        "data": (
            "Cours de clôture quotidiens ajustés de grandes capitalisations américaines, "
            "fournisseur Yahoo. L'univers est choisi parmi les titres qui cotent encore, et le "
            "biais du survivant est déclaré."
        ),
        "implementation": (
            "La stratégie vit dans quantlab.strategies.statistical_arbitrage. Toute grandeur "
            "datée du jour n'emploie que les rendements de ce jour et des précédents, et la "
            "détention se décale d'une séance dans le moteur de backtest."
        ),
        "assumptions": (
            "Un titre qui cesse de coter est réputé liquidé à son dernier cours. Le levier ne "
            "coûte rien de plus que la rotation, et l'emprunt de titres est gratuit."
        ),
        "replication": (
            f"Le ratio de Sharpe net sur la fenêtre de l'article vaut "
            f"{float(windows.loc['paper', 'sharpe_net']):.2f} contre 1,44 publié."
        ),
        "performance": (
            "Tous les chiffres portent leur échantillon et leur base de coût dans le tableau des métriques."
        ),
        "costs": (
            f"Le coût qui annule le rendement brut vaut {breakeven:.2f} points de base par "
            f"unité négociée, contre les {reference_cost:g} points de base que l'article "
            "retient."
        ),
        "robustness": (
            "Le nombre de facteurs, la fenêtre d'estimation, la fenêtre de corrélation, la "
            "fréquence de réestimation, le filtre de vitesse et les seuils sont balayés."
        ),
        "out_of_sample": (
            f"Après la publication, le ratio de Sharpe net vaut "
            f"{metric_values['sharpe_net_apres_publication']:.2f}."
        ),
        "statistical_tests": (
            "Le ratio de Sharpe dégonflé, la probabilité de surapprentissage et la correction "
            "de Holm sur les seize cellules de la grille sont dans les tableaux joints."
        ),
        "factor_attribution": (
            f"La corrélation quotidienne avec le fonds indiciel vaut "
            f"{metric_values['correlation_au_marche']:.3f}, la couverture par les "
            "portefeuilles propres étant déjà faite dans les poids."
        ),
        "limitations": (
            "Le seuil de capitalisation d'un milliard de dollars à la date de négociation n'est "
            "pas reproductible sans capitalisation en temps réel. L'univers porte le biais du "
            "survivant, et l'étude ne peut pas conclure au-delà de la réplication."
        ),
        "verdict": "Le verdict est déduit des seuils écrits dans config.yaml, sans arbitrage.",
    }


if __name__ == "__main__":
    main()

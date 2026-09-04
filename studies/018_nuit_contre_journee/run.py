"""Étude 018 : la nuit contre la journée, sur le momentum de série temporelle et cinq fonds de facteurs.

uv run python studies/018_nuit_contre_journee/run.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from gvf.style import OKABE_ITO
from matplotlib.figure import Figure

from quantlab.analytics.ratios import sharpe_ratio, sharpe_tstat
from quantlab.analytics.returns import overnight_intraday_split, resample_returns
from quantlab.analytics.visualization.figures import portfolio_style, save_figure
from quantlab.backtest.engine import run_backtest
from quantlab.core.config import ExperimentConfig, load_config
from quantlab.core.logging import configure_logging, get_logger, stage
from quantlab.core.types import CostBasis, Frequency, ReturnKind, SampleTag
from quantlab.data.providers.french import FrenchProvider
from quantlab.data.providers.yahoo import YahooProvider, to_wide
from quantlab.experiments import ExperimentRegistry
from quantlab.reporting.study import VerdictCriteria, VerdictEvidence, decide_verdict
from quantlab.strategies.time_series_momentum import monthly_inputs_from_prices, tsmom_weights

STUDY_DIR = Path(__file__).resolve().parent
ROOT = STUDY_DIR.parents[1]
RESULTS = STUDY_DIR / "results"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"
MONTHLY = Frequency.MONTHLY
DAILY = Frequency.DAILY
LOG = get_logger("study.018")


def _write_table(frame: pd.DataFrame, name: str) -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    frame.to_csv(TABLES / f"{name}.csv")


def _describe(s: pd.Series, frequency: Frequency) -> dict[str, float]:
    s = s.dropna()
    par_an = 12 if frequency is MONTHLY else 252
    return {
        "n_periods": len(s),
        "mean_annual_pct": float(s.mean() * par_an * 100),
        "sharpe": float(sharpe_ratio(s, frequency=frequency)),
        "t_stat": float(sharpe_tstat(s, frequency=frequency)),
    }


def main() -> None:
    configure_logging("INFO")
    config = yaml.safe_load((STUDY_DIR / "config.yaml").read_text(encoding="utf-8"))
    for d in (RESULTS, TABLES, FIGURES):
        d.mkdir(parents=True, exist_ok=True)
    source = load_config(ROOT / "studies" / config["source_study"] / "config.yaml", ExperimentConfig)
    p = source.params
    metrics: dict[str, Any] = {"source_study": config["source_study"]}
    yahoo = YahooProvider()
    french = FrenchProvider()

    with stage("stratégie"):
        brut = yahoo.fetch(
            source.data.universe, start=source.data.start, end=source.data.end, on_missing="drop"
        )
        adj = to_wide(brut, "adj_close").reindex(columns=source.data.universe)
        ouverture = to_wide(brut, "open").reindex(columns=source.data.universe).reindex(adj.index)
        cloture = to_wide(brut, "close").reindex(columns=source.data.universe).reindex(adj.index)
        # Les trois tableaux doivent porter des prix positifs là où le titre cote ;
        # ailleurs, les parts sont absentes et le contrôle d'identité les ignore.
        masque = adj.notna() & ouverture.notna() & cloture.notna() & (ouverture > 0) & (cloture > 0)
        nuit, jour = overnight_intraday_split(
            ouverture.where(masque, 1.0), cloture.where(masque, 1.0), adj.where(masque, 1.0)
        )
        nuit, jour = nuit.where(masque & masque.shift(1)), jour.where(masque)
        total = adj.pct_change()
        identite = ((1 + nuit) * (1 + jour) - 1 - total).abs()
        metrics["identity_max_abs_gap"] = float(identite.max().max())

        quotidiens = french.benchmark_factors(frequency=DAILY, start=source.data.start)
        mensuels = french.benchmark_factors(frequency=MONTHLY, start=p["aqr_start"])
        entrees = monthly_inputs_from_prices(
            adj,
            quotidiens["RF"],
            mensuels["RF"],
            center_of_mass=float(p["volatility_center_of_mass_days"]),
            annualization_days=float(p["volatility_annualization_days"]),
            min_periods=int(p["volatility_min_periods_days"]),
            min_trading_days=int(p["min_trading_days_per_month"]),
        )
        debut = p["backtest_start"]
        poids = tsmom_weights(
            entrees.monthly_excess,
            entrees.monthly_volatility,
            lookback=int(p["lookback_months"]),
            holding=int(p["holding_months"]),
            target_volatility=float(p["target_volatility"]),
        ).loc[debut:]
        # Les parts mensuelles par instrument, composées dans le mois, datées en fin de mois.
        nuit_m = resample_returns(nuit.fillna(0.0), MONTHLY, ReturnKind.SIMPLE)
        jour_m = resample_returns(jour.fillna(0.0), MONTHLY, ReturnKind.SIMPLE)
        nuit_m.index = nuit_m.index.to_period("M").to_timestamp("M")
        jour_m.index = jour_m.index.to_period("M").to_timestamp("M")
        total_m = entrees.monthly_excess.loc[debut:].fillna(0.0)
        commun = poids.index.intersection(nuit_m.index)
        rendement_total = run_backtest(
            weights=poids.loc[commun],
            returns=total_m.loc[commun],
            cost_model=None,
            execution_lag=1,
            frequency=MONTHLY,
        ).gross_returns
        rendement_nuit = run_backtest(
            weights=poids.loc[commun],
            returns=nuit_m.loc[commun, poids.columns],
            cost_model=None,
            execution_lag=1,
            frequency=MONTHLY,
        ).gross_returns
        rendement_jour = run_backtest(
            weights=poids.loc[commun],
            returns=jour_m.loc[commun, poids.columns],
            cost_model=None,
            execution_lag=1,
            frequency=MONTHLY,
        ).gross_returns
        parts = pd.DataFrame(
            {"total_excess": rendement_total, "overnight": rendement_nuit, "intraday": rendement_jour}
        )
        parts["residual"] = parts["total_excess"] - parts["overnight"] - parts["intraday"]
        _write_table(parts, "strategy_parts_monthly")
        metrics["strategy"] = {
            "total_excess": _describe(parts["total_excess"], MONTHLY),
            "overnight": _describe(parts["overnight"], MONTHLY),
            "intraday": _describe(parts["intraday"], MONTHLY),
            "residual_mean_annual_pct": float(parts["residual"].mean() * 12 * 100),
            "overnight_share_of_total": float(parts["overnight"].mean() / parts["total_excess"].mean())
            if parts["total_excess"].mean() != 0
            else float("nan"),
            "difference_overnight_minus_intraday": _describe(parts["overnight"] - parts["intraday"], MONTHLY),
        }

    with stage("fonds de facteurs"):
        fonds = list(config["factor_funds"])
        brut_f = yahoo.fetch(
            fonds, start=config["factor_funds_start"], end=source.data.end, on_missing="drop"
        )
        adj_f = to_wide(brut_f, "adj_close").reindex(columns=fonds)
        ouv_f = to_wide(brut_f, "open").reindex(columns=fonds).reindex(adj_f.index)
        clo_f = to_wide(brut_f, "close").reindex(columns=fonds).reindex(adj_f.index)
        masque_f = adj_f.notna() & ouv_f.notna() & clo_f.notna() & (ouv_f > 0) & (clo_f > 0)
        nuit_f, jour_f = overnight_intraday_split(
            ouv_f.where(masque_f, 1.0), clo_f.where(masque_f, 1.0), adj_f.where(masque_f, 1.0)
        )
        nuit_f, jour_f = nuit_f.where(masque_f & masque_f.shift(1)), jour_f.where(masque_f)
        lignes = []
        for t in fonds:
            n, j = nuit_f[t].dropna(), jour_f[t].dropna()
            lignes.append(
                {
                    "fund": t,
                    "factor": config["factor_funds"][t],
                    "first_date": str(n.index.min().date()),
                    "n_days": len(n),
                    "overnight_mean_annual_pct": float(n.mean() * 252 * 100),
                    "intraday_mean_annual_pct": float(j.mean() * 252 * 100),
                    "overnight_sharpe": float(sharpe_ratio(n, frequency=DAILY)),
                    "intraday_sharpe": float(sharpe_ratio(j, frequency=DAILY)),
                    "overnight_t": float(sharpe_tstat(n, frequency=DAILY)),
                    "intraday_t": float(sharpe_tstat(j, frequency=DAILY)),
                    "overnight_share_of_total": float(n.mean() / (n.mean() + j.mean()))
                    if (n.mean() + j.mean()) != 0
                    else float("nan"),
                }
            )
        fonds_df = pd.DataFrame(lignes).set_index("fund")
        _write_table(fonds_df, "factor_funds_split")
        metrics["factor_funds"] = fonds_df.to_dict(orient="index")

    with stage("figure"), portfolio_style():
        fig = Figure(figsize=(10, 4.6))
        ax = fig.add_subplot(111)
        etiquettes = ["Momentum temporel, 28 fonds"] + [f"{t}, {config['factor_funds'][t]}" for t in fonds]
        nuit_v = [metrics["strategy"]["overnight"]["mean_annual_pct"]] + [
            fonds_df.loc[t, "overnight_mean_annual_pct"] for t in fonds
        ]
        jour_v = [metrics["strategy"]["intraday"]["mean_annual_pct"]] + [
            fonds_df.loc[t, "intraday_mean_annual_pct"] for t in fonds
        ]
        x = np.arange(len(etiquettes))
        ax.bar(x - 0.2, nuit_v, width=0.4, color=OKABE_ITO[0], label="la nuit, de la clôture à l'ouverture")
        ax.bar(
            x + 0.2,
            jour_v,
            width=0.4,
            color=OKABE_ITO[1],
            label="la journée, de l'ouverture à la clôture",
        )
        ax.axhline(0, color="black", linewidth=0.6)
        ax.set_xticks(x, etiquettes, rotation=20, ha="right")
        ax.set_ylabel("Rendement moyen annualisé, en %")
        ax.set_title("Où le rendement se gagne : la nuit ou la journée, moyennes annualisées en %")
        ax.legend(fontsize=9)
        fig.tight_layout()
        save_figure(fig, FIGURES / "nuit_contre_journee")

    with stage("verdict"):
        s = metrics["strategy"]
        supporte = bool(
            s["overnight"]["mean_annual_pct"] > 0
            and s["overnight"]["mean_annual_pct"] > s["intraday"]["mean_annual_pct"]
        )
        evidence = VerdictEvidence(
            hypothesis_supported=supporte,
            oos_sharpe=s["total_excess"]["sharpe"],
            notes=(
                "décomposition en parts composées, fonds cotés au lieu d'actions ; "
                "aucun chiffre publié à répliquer sur ces fonds"
            ),
        )
        verdict, reasons = decide_verdict(evidence, VerdictCriteria())
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
        universe=list(source.data.universe) + fonds,
        date_start=str(parts.index.min().date()),
        date_end=str(parts.index.max().date()),
        cost_basis=CostBasis.GROSS,
        cost_assumptions={},
        n_trials=int(config["n_trials"]),
    ) as run:
        run.log_metric("overnight_sharpe", s["overnight"]["sharpe"], sample=SampleTag.OUT_OF_SAMPLE)
        run.log_metric("intraday_sharpe", s["intraday"]["sharpe"], sample=SampleTag.OUT_OF_SAMPLE)
        run.set_verdict(verdict)
    LOG.info("étude terminée", extra={"verdict": verdict.value})
    print(json.dumps({k: metrics[k] for k in ("identity_max_abs_gap", "strategy", "verdict")}, indent=2))
    print(fonds_df.round(3).to_string())


if __name__ == "__main__":
    main()

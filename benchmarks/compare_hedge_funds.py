"""Compare le portefeuille de l'étude 009 aux grands fonds fermés, sur rendements annuels.

Les fonds du registre ``hedge_funds.yaml`` ne publient qu'un chiffre par an,
rapporté par la presse ou par un livre. La comparaison se fait donc à l'année,
sur les années communes, avec l'intervalle de confiance que dix années
imposent. Le portefeuille est la parité de risque de l'étude 009, la référence
déclarée avant tout calcul, nette de coûts de transaction et brute de frais.

    uv run python benchmarks/compare_hedge_funds.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from quantlab.analytics.comparison import (
    annual_comparison_table,
    annual_returns,
    hedge_fund_table,
    load_hedge_fund_registry,
    scale_to_volatility,
)
from quantlab.analytics.ratios import sharpe_ratio
from quantlab.analytics.visualization.figures import (
    annual_returns_heatmap,
    annual_returns_lines,
    correlation_bars,
    save_figure,
)
from quantlab.core.logging import configure_logging, get_logger
from quantlab.core.types import Frequency
from quantlab.reporting.series import load_series

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmarks"
RESULTS = BENCH / "results"
FIGURES = RESULTS / "figures"
STUDY_RESULTS = ROOT / "studies" / "009_multi_strategy" / "results"
SERIES = "portfolio_risk_parity_net"
STRATEGY_LABEL = "laboratoire 009"
SCALED_LABEL = "laboratoire 009 à 10 % de volatilité"
TARGET_VOLATILITY = 0.10
DATE = "2026-09-02"
LOG = get_logger("benchmarks.hedge_funds")


def main() -> None:
    configure_logging("INFO")
    FIGURES.mkdir(parents=True, exist_ok=True)
    monthly = load_series(STUDY_RESULTS, SERIES)
    ours = annual_returns(monthly, frequency=Frequency.MONTHLY).rename(STRATEGY_LABEL)
    scaled_monthly = scale_to_volatility(monthly, TARGET_VOLATILITY, frequency=Frequency.MONTHLY)
    scaled = annual_returns(scaled_monthly, frequency=Frequency.MONTHLY).rename(SCALED_LABEL)

    records = load_hedge_fund_registry(BENCH / "hedge_funds.yaml")
    funds = hedge_fund_table(records)
    labels = {r.key: f"{r.name} ({r.manager})" for r in records}

    table = annual_comparison_table(ours, funds, strategy_name=STRATEGY_LABEL)
    scaled_table = annual_comparison_table(scaled, funds, strategy_name=SCALED_LABEL)
    table.insert(2, "fund_label", table["fund"].map(labels))
    table["mean_strategy_at_10pct_vol"] = scaled_table["mean_strategy"].to_numpy()
    table["vol_strategy_at_10pct_vol"] = scaled_table["vol_strategy"].to_numpy()
    table["worst_strategy_at_10pct_vol"] = scaled_table["worst_strategy"].to_numpy()
    table["hit_rate_at_10pct_vol"] = scaled_table["hit_rate"].to_numpy()
    table.to_csv(
        RESULTS / f"fonds_fermes_contre_portefeuille_009_{DATE}.csv", index=False, float_format="%.6g"
    )

    reported = pd.DataFrame(
        [
            {
                "fund": r.key,
                "fund_label": labels[r.key],
                "year": year,
                "return_pct": value,
                "verification": r.verification_of(year),
            }
            for r in records
            for year, value in sorted(r.annual_returns_pct.items())
        ]
    )
    reported.to_csv(RESULTS / f"fonds_fermes_rendements_annuels_{DATE}.csv", index=False)

    window = pd.concat([ours, funds], axis=1).sort_index().loc[int(ours.index.min()) :]
    window = window.rename(columns=labels)
    fig, _ = annual_returns_lines(window, highlight=STRATEGY_LABEL)
    save_figure(fig, FIGURES / "fonds_fermes_rendements_annuels.png")
    fig, _ = annual_returns_heatmap(window, highlight=STRATEGY_LABEL)
    save_figure(fig, FIGURES / "fonds_fermes_carte_annuelle.png")
    scaled_window = (
        pd.concat([scaled, funds], axis=1).sort_index().loc[int(scaled.index.min()) :].rename(columns=labels)
    )
    fig, _ = annual_returns_lines(
        scaled_window,
        highlight=SCALED_LABEL,
        title=(
            f"Rendements annuels, {SCALED_LABEL} (modélisé) et {len(funds.columns)} fonds, "
            f"{int(scaled.index.min())}-{int(scaled.index.max())}"
        ),
    )
    save_figure(fig, FIGURES / "fonds_fermes_rendements_annuels_vol10.png")
    fig, _ = correlation_bars(table.assign(fund=table["fund_label"]))
    save_figure(fig, FIGURES / "fonds_fermes_correlations.png")

    summary = {
        "date": DATE,
        "series": SERIES,
        "years": [int(ours.index.min()), int(ours.index.max())],
        "n_years": len(ours),
        "mean_annual": float(ours.mean()),
        "vol_annual": float(ours.std(ddof=1)),
        "worst_year": float(ours.min()),
        "best_year": float(ours.max()),
        "sharpe_monthly_annualized": float(sharpe_ratio(monthly, frequency=Frequency.MONTHLY)),
        "monthly_volatility_annualized": float(monthly.std(ddof=1) * (12**0.5)),
        "scaled_target_volatility": TARGET_VOLATILITY,
        "scaled_mean_annual": float(scaled.mean()),
        "scaled_worst_year": float(scaled.min()),
        "n_funds": len(funds.columns),
        "status": {"strategy": "mesuré", "scaled": "modélisé", "funds": "rapporté"},
    }
    (RESULTS / f"fonds_fermes_resume_{DATE}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    LOG.info("comparaison écrite", extra={"n_funds": summary["n_funds"], "n_years": summary["n_years"]})


if __name__ == "__main__":
    main()

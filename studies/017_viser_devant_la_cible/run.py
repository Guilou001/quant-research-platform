"""Étude 017 : viser devant la cible, forme simple, sur le momentum de série temporelle.

uv run python studies/017_viser_devant_la_cible/run.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from gvf.style import OKABE_ITO
from matplotlib.figure import Figure

from quantlab.analytics.ratios import sharpe_ratio
from quantlab.analytics.turnover import annualized_turnover
from quantlab.analytics.visualization.figures import portfolio_style, save_figure
from quantlab.backtest.engine import run_backtest
from quantlab.core.config import ExperimentConfig, load_config
from quantlab.core.logging import configure_logging, get_logger, stage
from quantlab.core.types import CostBasis, Frequency, SampleTag
from quantlab.data.providers.french import FrenchProvider
from quantlab.data.providers.yahoo import YahooProvider, to_wide
from quantlab.execution.costs import from_config as cost_from_config
from quantlab.execution.rebalancing import partial_rebalance
from quantlab.experiments import ExperimentRegistry
from quantlab.reporting.series import save_series
from quantlab.reporting.study import VerdictCriteria, VerdictEvidence, decide_verdict
from quantlab.strategies.time_series_momentum import monthly_inputs_from_prices, tsmom_weights

STUDY_DIR = Path(__file__).resolve().parent
ROOT = STUDY_DIR.parents[1]
RESULTS = STUDY_DIR / "results"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"
MONTHLY = Frequency.MONTHLY
LOG = get_logger("study.017")


def _write_table(frame: pd.DataFrame, name: str) -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    frame.to_csv(TABLES / f"{name}.csv")


def main() -> None:
    configure_logging("INFO")
    config = yaml.safe_load((STUDY_DIR / "config.yaml").read_text(encoding="utf-8"))
    for d in (RESULTS, TABLES, FIGURES):
        d.mkdir(parents=True, exist_ok=True)
    source = load_config(ROOT / "studies" / config["source_study"] / "config.yaml", ExperimentConfig)
    p = source.params
    metrics: dict[str, Any] = {"source_study": config["source_study"]}

    with stage("données"):
        yahoo = YahooProvider()
        brut = yahoo.fetch(
            source.data.universe, start=source.data.start, end=source.data.end, on_missing="drop"
        )
        prix = to_wide(brut, source.data.price_field).reindex(columns=source.data.universe)
        french = FrenchProvider()
        quotidiens = french.benchmark_factors(frequency=Frequency.DAILY, start=source.data.start)
        mensuels = french.benchmark_factors(frequency=Frequency.MONTHLY, start=p["aqr_start"])
        entrees = monthly_inputs_from_prices(
            prix,
            quotidiens["RF"],
            mensuels["RF"],
            center_of_mass=float(p["volatility_center_of_mass_days"]),
            annualization_days=float(p["volatility_annualization_days"]),
            min_periods=int(p["volatility_min_periods_days"]),
            min_trading_days=int(p["min_trading_days_per_month"]),
        )
        debut = p["backtest_start"]
        cibles = tsmom_weights(
            entrees.monthly_excess,
            entrees.monthly_volatility,
            lookback=int(p["lookback_months"]),
            holding=int(p["holding_months"]),
            target_volatility=float(p["target_volatility"]),
        ).loc[debut:]
        rendements = entrees.monthly_excess.loc[debut:].fillna(0.0)
        modele = cost_from_config(source.costs, frequency=MONTHLY)

    with stage("grille des taux"):
        fin_selection = pd.Timestamp(config["selection_end"])
        debut_holdout = pd.Timestamp(config["holdout_start"])
        lignes = []
        series_nettes: dict[float, pd.Series] = {}
        for taux in config["rates"]:
            decides = partial_rebalance(cibles, rendements, float(taux))
            resultat = run_backtest(
                weights=decides, returns=rendements, cost_model=modele, execution_lag=1, frequency=MONTHLY
            )
            net, brut_r = resultat.net_returns, resultat.gross_returns
            series_nettes[float(taux)] = net
            sel_net, hold_net = net.loc[:fin_selection], net.loc[debut_holdout:]
            sel_brut, hold_brut = brut_r.loc[:fin_selection], brut_r.loc[debut_holdout:]
            lignes.append(
                {
                    "rate": float(taux),
                    "sharpe_net_selection": float(sharpe_ratio(sel_net, frequency=MONTHLY)),
                    "sharpe_gross_selection": float(sharpe_ratio(sel_brut, frequency=MONTHLY)),
                    "sharpe_net_holdout": float(sharpe_ratio(hold_net, frequency=MONTHLY)),
                    "sharpe_gross_holdout": float(sharpe_ratio(hold_brut, frequency=MONTHLY)),
                    "turnover_annual": float(annualized_turnover(resultat.turnover, MONTHLY)),
                    "cost_annual_pct": float(resultat.costs.mean() * 12 * 100),
                    "gross_exposure_mean": float(resultat.gross_exposure.mean()),
                    "n_months_selection": len(sel_net),
                    "n_months_holdout": len(hold_net),
                }
            )
        grille = pd.DataFrame(lignes).set_index("rate")
        _write_table(grille, "rate_grid")
        retenu = float(grille["sharpe_net_selection"].idxmax())
        complet = grille.loc[1.0]
        choisi = grille.loc[retenu]
        metrics["grid"] = grille.to_dict(orient="index")
        metrics["selected_rate"] = retenu
        metrics["holdout"] = {
            "sharpe_net_selected": float(choisi["sharpe_net_holdout"]),
            "sharpe_net_full_rebalance": float(complet["sharpe_net_holdout"]),
            "sharpe_gross_selected": float(choisi["sharpe_gross_holdout"]),
            "sharpe_gross_full_rebalance": float(complet["sharpe_gross_holdout"]),
            "turnover_selected": float(choisi["turnover_annual"]),
            "turnover_full_rebalance": float(complet["turnover_annual"]),
            "cost_annual_pct_selected": float(choisi["cost_annual_pct"]),
            "cost_annual_pct_full_rebalance": float(complet["cost_annual_pct"]),
        }
        # Le meilleur taux du holdout, lu APRÈS coup et publié comme tel, jamais retenu.
        metrics["holdout_best_rate_after_the_fact"] = float(grille["sharpe_net_holdout"].idxmax())
        save_series(
            RESULTS,
            "tsmom_partial_net",
            series_nettes[retenu],
            sample=SampleTag.OUT_OF_SAMPLE,
            basis=CostBasis.NET,
            frequency=MONTHLY,
            universe="28 fonds cotés de l'étude 001",
            cost_assumptions=f"coûts de l'étude 001, taux de rapprochement {retenu}",
        )
        save_series(
            RESULTS,
            "tsmom_full_net",
            series_nettes[1.0],
            sample=SampleTag.OUT_OF_SAMPLE,
            basis=CostBasis.NET,
            frequency=MONTHLY,
            universe="28 fonds cotés de l'étude 001",
            cost_assumptions="coûts de l'étude 001, rééquilibrage complet",
        )

    with stage("figure"), portfolio_style():
        fig = Figure(figsize=(10, 4.4))
        ax = fig.add_subplot(111)
        ax.plot(
            grille.index,
            grille["sharpe_net_selection"],
            marker="o",
            color=OKABE_ITO[0],
            label="net, avant publication (fenêtre de choix)",
        )
        ax.plot(
            grille.index,
            grille["sharpe_net_holdout"],
            marker="s",
            color=OKABE_ITO[3],
            label="net, après publication (holdout)",
        )
        ax.plot(
            grille.index,
            grille["sharpe_gross_holdout"],
            marker="^",
            color=OKABE_ITO[1],
            linestyle="--",
            label="brut, après publication",
        )
        ax.axvline(retenu, color="black", linewidth=0.8, linestyle=":", label=f"taux retenu {retenu:.1f}")
        ax.set_xlabel("Fraction du chemin parcourue vers la cible à chaque mois")
        ax.set_ylabel("Ratio de Sharpe annualisé")
        ax.set_title(
            "Momentum de série temporelle : ce que le rapprochement partiel change au ratio de Sharpe"
        )
        ax.legend(fontsize=9)
        fig.tight_layout()
        save_figure(fig, FIGURES / "sharpe_par_taux")

    with stage("verdict"):
        supporte = (
            bool(metrics["holdout"]["sharpe_net_selected"] > metrics["holdout"]["sharpe_net_full_rebalance"])
            and retenu < 1.0
        )
        evidence = VerdictEvidence(
            hypothesis_supported=supporte,
            oos_sharpe=metrics["holdout"]["sharpe_net_selected"],
            notes=(
                "forme simple de l'article, taux constant choisi avant publication ; "
                "aucun chiffre publié à répliquer"
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
        universe=list(source.data.universe),
        date_start=str(cibles.index.min().date()),
        date_end=str(cibles.index.max().date()),
        cost_basis=CostBasis.NET,
        cost_assumptions={
            k: float(v) for k, v in source.costs.model_dump(mode="json").items() if isinstance(v, int | float)
        },
        n_trials=int(config["n_trials"]),
    ) as run:
        run.log_metric(
            "sharpe_net_holdout_selected",
            metrics["holdout"]["sharpe_net_selected"],
            sample=SampleTag.FINAL_HOLDOUT,
        )
        run.log_metric(
            "sharpe_net_holdout_full",
            metrics["holdout"]["sharpe_net_full_rebalance"],
            sample=SampleTag.FINAL_HOLDOUT,
        )
        run.set_verdict(verdict)
    LOG.info("étude terminée", extra={"verdict": verdict.value})
    print(
        json.dumps(
            {
                k: metrics[k]
                for k in ("selected_rate", "holdout", "holdout_best_rate_after_the_fact", "verdict")
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

"""Étude 015 : ce que le forfait gratuit de Polygon donne pour un univers sans biais de survie.

uv run python studies/015_univers_polygon/run.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from gvf.style import OKABE_ITO
from matplotlib.figure import Figure

from quantlab.analytics.visualization.figures import portfolio_style, save_figure
from quantlab.core.logging import configure_logging, get_logger, stage
from quantlab.core.types import CostBasis, SampleTag, Verdict
from quantlab.data.providers.polygon import PolygonProvider, ProviderError
from quantlab.experiments import ExperimentRegistry

STUDY_DIR = Path(__file__).resolve().parent
RESULTS = STUDY_DIR / "results"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"
LOG = get_logger("study.015")


def _write_table(frame: pd.DataFrame, name: str) -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    frame.to_csv(TABLES / f"{name}.csv")


def _probe(fournisseur: PolygonProvider, ticker: str, start: str, end: str) -> dict[str, Any]:
    """Demande des barres et rend ce que le forfait a répondu, refus compris."""
    try:
        barres = fournisseur.daily_bars(ticker, start=start, end=end)
    except ProviderError as exc:
        return {
            "ticker": ticker,
            "status": getattr(exc, "status_code", None),
            "n_bars": 0,
            "first_date": None,
            "last_date": None,
            "message": str(exc)[:200],
        }
    return {
        "ticker": ticker,
        "status": 200,
        "n_bars": len(barres),
        "first_date": str(barres["date"].min().date()) if len(barres) else None,
        "last_date": str(barres["date"].max().date()) if len(barres) else None,
        "message": "",
    }


def main() -> None:
    configure_logging("INFO")
    config = yaml.safe_load((STUDY_DIR / "config.yaml").read_text(encoding="utf-8"))
    for d in (RESULTS, TABLES, FIGURES):
        d.mkdir(parents=True, exist_ok=True)
    metrics: dict[str, Any] = {}
    fournisseur = PolygonProvider()
    p = config["probes"]

    with stage("sondes de prix"):
        profondeur = _probe(fournisseur, p["depth_ticker"], p["depth_start"], p["depth_end"])
        radie = _probe(fournisseur, p["delisted_ticker"], p["delisted_start"], p["delisted_end"])
        sondes = pd.DataFrame([profondeur, radie]).set_index("ticker")
        _write_table(sondes, "price_probes")
        metrics["probes"] = {"depth": profondeur, "delisted": radie}

    with stage("référentiel"):
        radies = fournisseur.reference_tickers(active=False)
        actifs = fournisseur.reference_tickers(active=True)
        manifeste = fournisseur.manifest().model_dump(mode="json")
        t = config["reference"]["security_type"]
        cs_radies = radies[radies["type"] == t].copy()
        cs_actifs = actifs[actifs["type"] == t].copy()
        annees_radiation = pd.to_datetime(cs_radies["delisted_utc"], utc=True).dt.year
        par_annee = annees_radiation.value_counts().sort_index()
        par_annee = par_annee[par_annee.index >= int(config["reference"]["first_year"])]
        calendrier = pd.DataFrame({"delistings": par_annee.astype(int)})
        calendrier.index.name = "year"
        # Ce qui existait au premier janvier de chaque année : les actifs
        # d'aujourd'hui plus les radiés depuis, et la part qui survit aujourd'hui.
        lignes = []
        for annee in calendrier.index:
            existaient = len(cs_actifs) + int((annees_radiation >= annee).sum())
            lignes.append(
                {
                    "year": int(annee),
                    "existing_on_jan_1": existaient,
                    "surviving_today": len(cs_actifs),
                    "share_surviving": len(cs_actifs) / existaient,
                }
            )
        survie = pd.DataFrame(lignes).set_index("year")
        _write_table(calendrier, "delistings_by_year")
        _write_table(survie, "survivorship_by_year")
        metrics["reference"] = {
            "n_tickers_delisted_all_types": len(radies),
            "n_tickers_active_all_types": len(actifs),
            "n_common_stocks_delisted": len(cs_radies),
            "n_common_stocks_delisted_dated": int(annees_radiation.notna().sum()),
            "n_common_stocks_active": len(cs_actifs),
            "first_delisting_year": int(annees_radiation.min()) if annees_radiation.notna().any() else None,
            "share_surviving_from_first_year": float(survie["share_surviving"].iloc[0]),
            "delistings_2023": int(calendrier.loc[2023, "delistings"]) if 2023 in calendrier.index else None,
            "manifest": manifeste,
        }

    with stage("figure"), portfolio_style():
        fig = Figure(figsize=(10, 4.4))
        ax = fig.add_subplot(111)
        ax.bar(
            calendrier.index,
            calendrier["delistings"],
            color=OKABE_ITO[3],
            label="actions ordinaires radiées dans l'année",
        )
        ax.set_ylabel("Nombre de radiations")
        ax.set_xlabel("Année")
        ax2 = ax.twinx()
        ax2.plot(
            survie.index,
            survie["share_surviving"] * 100,
            color=OKABE_ITO[0],
            linewidth=1.8,
            label="part des actions du 1er janvier encore cotées en 2026, en %",
        )
        ax2.set_ylabel("Part encore cotée en 2026, en %")
        ax2.set_ylim(0, 100)
        ax.set_title(
            f"Polygon, référentiel gratuit : {int(calendrier['delistings'].sum())} radiations "
            f"depuis {int(calendrier.index.min())}, et ce qui survit"
        )
        h1, l1 = ax.get_legend_handles_labels()
        h2, l2 = ax2.get_legend_handles_labels()
        ax.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=9)
        fig.tight_layout()
        save_figure(fig, FIGURES / "radiations_et_survie")

    with stage("verdict"):
        assez_profond = (
            profondeur["first_date"] is not None and profondeur["first_date"] <= p["required_first_date"]
        )
        radie_disponible = radie["status"] == 200 and radie["n_bars"] > 0
        raisons = [
            f"{'RÉUSSI' if assez_profond else 'ÉCHOUÉ'} | profondeur d'historique : première barre "
            f"{profondeur['first_date']}, exigé au plus tard {p['required_first_date']}",
            f"{'RÉUSSI' if radie_disponible else 'ÉCHOUÉ'} | prix d'un titre radié : {p['delisted_ticker']} "
            f"en 2008 répond {radie['status']}, {radie['n_bars']} barres",
            f"RÉUSSI | référentiel : {metrics['reference']['n_common_stocks_delisted_dated']} actions "
            f"ordinaires radiées datées depuis {metrics['reference']['first_delisting_year']}",
        ]
        verdict = Verdict.EXPERIMENTAL if (assez_profond and radie_disponible) else Verdict.REJECTED
        raisons.append(f"VERDICT | {verdict.value}")
        metrics["verdict"] = verdict.value
        metrics["verdict_reasons"] = raisons
        pd.DataFrame({"reason": raisons}).to_csv(TABLES / "verdict_reasons.csv", index=False)

    (RESULTS / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    with ExperimentRegistry().run(
        name=config["name"],
        hypothesis=config["hypothesis"],
        config=config,
        seed=int(config["seed"]),
        universe=[p["depth_ticker"], p["delisted_ticker"]],
        date_start=p["depth_start"],
        date_end=p["depth_end"],
        cost_basis=CostBasis.GROSS,
        cost_assumptions={},
        n_trials=int(config["n_trials"]),
    ) as run:
        run.log_metric(
            "share_surviving_from_first_year",
            metrics["reference"]["share_surviving_from_first_year"],
            sample=SampleTag.OUT_OF_SAMPLE,
        )
        run.set_verdict(verdict)
    LOG.info("étude terminée", extra={"verdict": verdict.value})
    print(
        json.dumps(
            {k: v for k, v in metrics.items() if k != "reference"}
            | {"reference": {k: v for k, v in metrics["reference"].items() if k != "manifest"}},
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )


if __name__ == "__main__":
    main()

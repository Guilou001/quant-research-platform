"""Étude 020 : les meilleures idées des gestionnaires concentrés, d'un dépôt 13F au suivant.

uv run python studies/020_meilleures_idees_13f/run.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from quantlab.analytics.ratios import sharpe_ratio, sharpe_tstat
from quantlab.analytics.regression import factor_regression
from quantlab.analytics.visualization.figures import cumulative_return_pct, save_figure
from quantlab.core.logging import configure_logging, get_logger, stage
from quantlab.core.paths import Layer, data_dir
from quantlab.core.types import CostBasis, Frequency, SampleTag
from quantlab.data.providers.openfigi import OpenFigiMapper
from quantlab.data.providers.sec13f import SecForm13FProvider
from quantlab.data.providers.yahoo import YahooProvider, to_wide
from quantlab.experiments import ExperimentRegistry
from quantlab.reporting.series import save_series
from quantlab.reporting.study import VerdictCriteria, VerdictEvidence, decide_verdict

STUDY_DIR = Path(__file__).resolve().parent
RESULTS = STUDY_DIR / "results"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"
MONTHLY = Frequency.MONTHLY
LOG = get_logger("study.020")


def _write_table(frame: pd.DataFrame, name: str) -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    frame.to_csv(TABLES / f"{name}.csv")


def _best_ideas_of_quarter(tables: dict[str, pd.DataFrame], config: dict[str, Any]) -> pd.DataFrame:
    """Rend, par déclaration concentrée, sa plus grosse position et sa date de dépôt."""
    f = config["filings"]
    soumissions = tables["submissions"]
    soumissions = soumissions[soumissions["submission_type"] == f["submission_type"]]
    couvertures = tables["coverpages"]
    non_amendees = couvertures[
        couvertures["is_amendment"].isna() | (couvertures["is_amendment"].astype(str).str.strip() == "")
    ]
    soumissions = soumissions[soumissions["accession"].isin(non_amendees["accession"])]
    positions = tables["holdings"]
    positions = positions[positions["accession"].isin(soumissions["accession"])]
    positions = positions[positions["shares_type"].astype(str).str.strip().eq("SH")]
    sans_option = positions["put_call"].isna() | (positions["put_call"].astype(str).str.strip() == "")
    positions = positions[sans_option & positions["value_usd"].notna() & (positions["value_usd"] > 0)]
    agregat = positions.groupby("accession").agg(
        n_positions=("value_usd", "size"), total_value=("value_usd", "sum")
    )
    concentres = agregat[
        (agregat["n_positions"] >= f["min_positions"])
        & (agregat["n_positions"] <= f["max_positions"])
        & (agregat["total_value"] >= f["min_total_value_usd"])
    ]
    if concentres.empty:
        return pd.DataFrame()
    retenues = positions[positions["accession"].isin(concentres.index)]
    idx = retenues.groupby("accession")["value_usd"].idxmax()
    top = retenues.loc[idx].merge(concentres, left_on="accession", right_index=True)
    top["weight"] = top["value_usd"] / top["total_value"]
    top = top[top["weight"] >= f["min_top_weight"]]
    top = top.merge(
        soumissions[["accession", "cik", "filing_date", "period_end"]], on="accession", how="inner"
    )
    return top[
        [
            "accession",
            "cik",
            "filing_date",
            "period_end",
            "cusip",
            "figi",
            "issuer",
            "weight",
            "n_positions",
            "total_value",
            "value_unit",
        ]
    ]


def _describe(s: pd.Series) -> dict[str, float]:
    s = s.dropna()
    return {
        "n_months": len(s),
        "annual_return_pct": float(((1 + s).prod() ** (12 / len(s)) - 1) * 100) if len(s) else float("nan"),
        "sharpe": float(sharpe_ratio(s, frequency=MONTHLY)) if len(s) > 2 else float("nan"),
        "t_stat": float(sharpe_tstat(s, frequency=MONTHLY)) if len(s) > 2 else float("nan"),
    }


def main() -> None:
    configure_logging("INFO")
    config = yaml.safe_load((STUDY_DIR / "config.yaml").read_text(encoding="utf-8"))
    for d in (RESULTS, TABLES, FIGURES):
        d.mkdir(parents=True, exist_ok=True)
    metrics: dict[str, Any] = {}

    with stage("déclarations"):
        fournisseur = SecForm13FProvider()
        fichiers = fournisseur.quarter_files()
        idees = []
        for url in fichiers:
            tables = fournisseur.quarter(url)
            bloc = _best_ideas_of_quarter(tables, config)
            if not bloc.empty:
                idees.append(bloc)
            del tables
        idees_df = pd.concat(idees, ignore_index=True)
        idees_df["cusip"] = idees_df["cusip"].astype(str).str.strip().str.upper()
        idees_df = idees_df[idees_df["period_end"] >= pd.Timestamp(config["prices"]["start"])]
        idees_df = idees_df.reset_index(drop=True)
        _write_table(idees_df, "best_ideas_raw")
        suspectes = idees_df["value_unit"].eq("suspect")
        idees_df = idees_df[~suspectes].reset_index(drop=True)
        en_milliers = idees_df["value_unit"].eq("thousands")
        metrics["units"] = {
            "n_suspect_dropped": int(suspectes.sum()),
            "n_in_thousands": int(en_milliers.sum()),
            "share_in_thousands_by_year": {
                str(k): round(float(v), 4)
                for k, v in en_milliers.groupby(idees_df["period_end"].dt.year).mean().items()
            },
        }
        metrics["filings"] = {
            "n_quarter_files": len(fichiers),
            "n_best_ideas": len(idees_df),
            "n_distinct_cusips": int(idees_df["cusip"].nunique()),
            "n_managers": int(idees_df["cik"].nunique()),
            "first_period": str(idees_df["period_end"].min().date()),
            "last_period": str(idees_df["period_end"].max().date()),
        }

    with stage("correspondance"):
        mapper = OpenFigiMapper(data_dir(Layer.RAW) / "openfigi" / "cusip_map.json")
        correspondance = mapper.map(idees_df["cusip"].unique().tolist())
        _write_table(correspondance.set_index("cusip"), "cusip_mapping")
        idees_df = idees_df.merge(
            correspondance[["cusip", "ticker", "found", "security_type"]], on="cusip", how="left"
        )
        exclus = idees_df["security_type"].isin(config["filings"]["exclude_security_types"])
        metrics["mapping"] = {
            "n_cusips": len(correspondance),
            "n_found": int(correspondance["found"].sum()),
            "share_found": float(correspondance["found"].mean()),
            "security_types": correspondance["security_type"].value_counts().head(8).to_dict(),
            "n_ideas_excluded_by_type": int(exclus.sum()),
            "share_ideas_excluded_by_type": float(exclus.mean()),
        }
        idees_df = idees_df[~exclus].reset_index(drop=True)

    with stage("prix"):
        symboles = sorted(
            {
                t
                for t in idees_df["ticker"].dropna().unique()
                if isinstance(t, str) and t.replace("/", "").replace("-", "").isalnum()
            }
        )
        symboles_yahoo = [t.replace("/", "-") for t in symboles]
        yahoo = YahooProvider()
        brut = yahoo.fetch(
            [*symboles_yahoo, config["prices"]["benchmark"]],
            start=config["prices"]["start"],
            end=config["prices"]["end"],
            on_missing="drop",
        )
        prix = to_wide(brut, "adj_close")
        mensuel = prix.resample("ME").last().pct_change()
        idees_df["ticker_yahoo"] = idees_df["ticker"].astype(str).str.replace("/", "-")
        avec_prix = idees_df["ticker_yahoo"].isin(prix.columns)
        metrics["prices"] = {
            "n_tickers_requested": len(symboles_yahoo),
            "n_tickers_with_prices": int(sum(t in prix.columns for t in symboles_yahoo)),
            "share_ideas_with_prices": float(avec_prix.mean()),
        }

    with stage("portefeuille"):
        lag = pd.Timedelta(days=int(config["filings"]["formation_lag_days"]))
        periodes = sorted(idees_df["period_end"].unique())
        rendements_eq, rendements_votes, lignes = [], [], []
        precedentes: set[str] = set()
        for i, fin in enumerate(periodes):
            formation = pd.Timestamp(fin) + lag
            prochaine = (
                pd.Timestamp(periodes[i + 1]) + lag
                if i + 1 < len(periodes)
                else mensuel.index.max() + pd.Timedelta(days=1)
            )
            bloc = idees_df[(idees_df["period_end"] == fin) & (idees_df["filing_date"] <= formation)]
            n_idees = len(bloc)
            votes = (
                bloc["ticker_yahoo"].where(bloc["ticker_yahoo"].isin(prix.columns)).dropna().value_counts()
            )
            n_sans_prix = int(n_idees - bloc["ticker_yahoo"].isin(prix.columns).sum())
            noms = set(votes.index)
            renouvellement = 1.0 - len(noms & precedentes) / len(noms) if noms and precedentes else np.nan
            lignes.append(
                {
                    "period_end": pd.Timestamp(fin).date(),
                    "formation": formation.date(),
                    "n_ideas": n_idees,
                    "n_ideas_without_price": n_sans_prix,
                    "n_distinct_with_price": len(votes),
                    "share_renewed": renouvellement,
                }
            )
            if len(votes) == 0:
                continue
            precedentes = noms
            mois = mensuel.index[(mensuel.index > formation) & (mensuel.index <= prochaine)]
            if len(mois) == 0:
                continue
            r = mensuel.loc[mois, votes.index]
            rendements_eq.append(r.mean(axis=1))
            rendements_votes.append((r * (votes / votes.sum())).sum(axis=1))
        eq = pd.concat(rendements_eq).sort_index()
        eq = eq[~eq.index.duplicated()]
        vt = pd.concat(rendements_votes).sort_index()
        vt = vt[~vt.index.duplicated()]
        marche = mensuel[config["prices"]["benchmark"]].reindex(eq.index)
        couverture = pd.DataFrame(lignes).set_index("period_end")
        _write_table(couverture, "coverage_by_quarter")
        # Coûts : la part des noms remplacés d'une formation à la suivante, mesurée,
        # payée à l'achat et à la vente, étalée sur les trois mois du trimestre.
        rotation = float(couverture["share_renewed"].mean())
        cout_mensuel = float(config["costs"]["spread_bps"]) / 1e4 * 2.0 * rotation / 3
        series = pd.DataFrame(
            {
                "equal_weight": eq,
                "vote_weight": vt,
                "market": marche,
                "equal_weight_net": eq - cout_mensuel,
                "vote_weight_net": vt - cout_mensuel,
            }
        )
        _write_table(series, "monthly_returns")
        for nom in ("equal_weight", "vote_weight"):
            save_series(
                RESULTS,
                f"best_ideas_{nom}_gross",
                series[nom],
                sample=SampleTag.OUT_OF_SAMPLE,
                basis=CostBasis.GROSS,
                frequency=MONTHLY,
                universe="plus grosses positions des gestionnaires 13F concentrés, prix Yahoo des survivants",
            )
        metrics["portfolio"] = {nom: _describe(series[nom]) for nom in series.columns}
        exces = {
            nom: _describe(series[nom] - series["market"])
            for nom in ("equal_weight", "vote_weight", "equal_weight_net")
        }
        metrics["excess_over_market"] = exces
        facteur = series[["market"]].rename(columns={"market": "marche"})
        reg = factor_regression(series["equal_weight"], facteur, frequency=MONTHLY)
        metrics["capm"] = {
            "alpha_annual": float(reg.alpha),
            "alpha_t": float(reg.alpha_tstat),
            "beta": float(reg.betas["marche"]),
            "r_squared": float(reg.r_squared),
        }
        recent = series.loc["2020-01-01":]
        metrics["since_2020"] = {
            nom: _describe(recent[nom]) for nom in ("equal_weight", "vote_weight", "market")
        }
        metrics["coverage"] = {
            "ideas_total": int(couverture["n_ideas"].sum()),
            "ideas_without_price": int(couverture["n_ideas_without_price"].sum()),
            "share_without_price": float(
                couverture["n_ideas_without_price"].sum() / couverture["n_ideas"].sum()
            ),
            "mean_distinct_ideas_per_quarter": float(couverture["n_distinct_with_price"].mean()),
            "mean_share_renewed": rotation,
            "monthly_cost": cout_mensuel,
        }

    with stage("figure"):
        fig, _ = cumulative_return_pct(
            {
                "Meilleures idées, équipondérées": series["equal_weight"],
                "Meilleures idées, pondérées par les votes": series["vote_weight"],
                "Marché, SPY": series["market"],
            },
            title=(
                f"Les meilleures idées des gestionnaires concentrés contre le marché, en %, "
                f"{series.index.min().year}-{series.index.max().year}"
            ),
        )
        save_figure(fig, FIGURES / "meilleures_idees")

    with stage("verdict"):
        supporte = bool(
            metrics["excess_over_market"]["equal_weight"]["annual_return_pct"] > 0
            and metrics["capm"]["alpha_t"] > 0
        )
        evidence = VerdictEvidence(
            hypothesis_supported=supporte,
            oos_sharpe=metrics["portfolio"]["equal_weight_net"]["sharpe"],
            notes="prix des survivants seulement ; la part des idées sans prix borne le biais et est publiée",
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
        universe=["13F"],
        date_start=str(series.index.min().date()),
        date_end=str(series.index.max().date()),
        cost_basis=CostBasis.NET,
        cost_assumptions={"spread_bps": float(config["costs"]["spread_bps"])},
        n_trials=int(config["n_trials"]),
    ) as run:
        run.log_metric("alpha_annual", metrics["capm"]["alpha_annual"], sample=SampleTag.OUT_OF_SAMPLE)
        run.set_verdict(verdict)
    LOG.info("étude terminée", extra={"verdict": verdict.value})
    print(
        json.dumps(
            {
                k: metrics[k]
                for k in (
                    "filings",
                    "mapping",
                    "prices",
                    "coverage",
                    "portfolio",
                    "excess_over_market",
                    "capm",
                    "since_2020",
                    "verdict",
                )
            },
            indent=1,
            default=str,
        )
    )


if __name__ == "__main__":
    main()

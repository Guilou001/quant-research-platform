"""Étude 016 : ce qui survit à la publication, sur 212 portefeuilles sans biais de survie.

Le point d'entrée ne porte aucune logique réutilisable : il assemble les briques
de ``quantlab`` et écrit ses résultats dans ``results/``. Il est déterministe.

    uv run python studies/016_publication_decay_212/run.py
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
import yaml
from gvf.style import OKABE_ITO
from matplotlib.figure import Figure
from scipy import stats

from quantlab.analytics.ratios import sharpe_ratio, sharpe_tstat
from quantlab.analytics.visualization.figures import portfolio_style, save_figure
from quantlab.core.determinism import make_generator
from quantlab.core.logging import configure_logging, get_logger, stage
from quantlab.core.types import CostBasis, Frequency, SampleTag
from quantlab.data.providers.osap import OsapProvider
from quantlab.experiments import ExperimentRegistry
from quantlab.reporting.study import ReplicationCheck, VerdictCriteria, VerdictEvidence, decide_verdict
from quantlab.validation.bootstrap import bootstrap_confidence_interval, bootstrap_statistic

warnings.filterwarnings("ignore", category=FutureWarning, module="pandas")
STUDY_DIR = Path(__file__).resolve().parent
RESULTS = STUDY_DIR / "results"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"
MONTHLY = Frequency.MONTHLY
WINDOWS = ("in_sample", "post_sample", "post_publication")
LOG = get_logger("study.016")


def _write_table(frame: pd.DataFrame, name: str) -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    frame.to_csv(TABLES / f"{name}.csv")


def _describe_window(s: pd.Series) -> dict[str, float]:
    n = len(s)
    return {
        "n_months": n,
        "mean_monthly_pct": float(s.mean()) * 100,
        "t_stat": float(sharpe_tstat(s, frequency=MONTHLY)) if n > 1 else float("nan"),
        "sharpe": float(sharpe_ratio(s, frequency=MONTHLY)) if n > 1 else float("nan"),
    }


def _pooled_regression(stack: pd.DataFrame) -> dict[str, Any]:
    """Rendement normalisé sur deux indicatrices, effet fixe par prédicteur, erreurs groupées par mois."""
    y = stack["scaled"].to_numpy()
    X = pd.get_dummies(stack["predictor"], dtype=float)
    X["post_sample"] = (stack["window"] == "post_sample").astype(float)
    X["post_publication"] = (stack["window"] == "post_publication").astype(float)
    groupes = pd.factorize(stack.index)[0]
    modele = sm.OLS(y, X.to_numpy()).fit(cov_type="cluster", cov_kwds={"groups": groupes})
    colonnes = list(X.columns)
    i_ps, i_pp = colonnes.index("post_sample"), colonnes.index("post_publication")
    return {
        "post_sample_decline": float(-modele.params[i_ps]),
        "post_sample_se": float(modele.bse[i_ps]),
        "post_sample_t": float(modele.tvalues[i_ps]),
        "post_publication_decline": float(-modele.params[i_pp]),
        "post_publication_se": float(modele.bse[i_pp]),
        "post_publication_t": float(modele.tvalues[i_pp]),
        "n_observations": int(modele.nobs),
        "n_month_clusters": len(np.unique(groupes)),
        "n_predictors": int(stack["predictor"].nunique()),
    }


def _bootstrap_mean(values: np.ndarray, rng: np.random.Generator, n: int) -> tuple[float, float]:
    distribution = bootstrap_statistic(values, lambda x: float(np.mean(x)), "iid", n, rng)
    intervalle = bootstrap_confidence_interval(distribution, 0.95, "percentile")
    return float(intervalle.low), float(intervalle.high)


def _spearman_permutation(x: np.ndarray, y: np.ndarray, rng: np.random.Generator, n: int) -> dict[str, float]:
    rho, _ = stats.spearmanr(x, y)
    rx = stats.rankdata(x)
    rx = (rx - rx.mean()) / rx.std()
    ry = stats.rankdata(y)
    ry = (ry - ry.mean()) / ry.std()
    permutees = np.array([rng.permutation(ry) for _ in range(n)]) @ rx / len(rx)
    return {
        "spearman": float(rho),
        "permutation_p_value": float((np.abs(permutees) >= abs(rho)).mean()),
        "n": len(x),
    }


def main() -> None:
    configure_logging("INFO")
    config = yaml.safe_load((STUDY_DIR / "config.yaml").read_text(encoding="utf-8"))
    for d in (RESULTS, TABLES, FIGURES):
        d.mkdir(parents=True, exist_ok=True)
    rng = make_generator(int(config["seed"]))
    metrics: dict[str, Any] = {"published": config["published"]}
    minimum = int(config["pooling"]["min_months_per_window"])

    with stage("données"):
        fournisseur = OsapProvider()
        rendements = fournisseur.long_short_returns()
        manifeste_rendements = fournisseur.manifest().model_dump(mode="json")
        fiche = fournisseur.signal_documentation()
        metrics["data"] = {
            "n_predictors_file": int(rendements.shape[1]),
            "first_month": str(rendements.index.min().date()),
            "last_month": str(rendements.index.max().date()),
            "manifest_returns": manifeste_rendements,
        }

    with stage("fenêtres"):
        lignes: list[dict[str, Any]] = []
        piles: list[pd.DataFrame] = []
        ecartes: list[str] = []
        for acronyme in rendements.columns:
            if acronyme not in fiche.index:
                ecartes.append(acronyme)
                continue
            s = rendements[acronyme].dropna()
            fin = pd.Timestamp(
                year=int(fiche.loc[acronyme, "sample_end_year"]),
                month=int(config["dates"]["sample_end_month"]),
                day=1,
            ) + pd.offsets.MonthEnd(0)
            pub = pd.Timestamp(
                year=int(fiche.loc[acronyme, "publication_year"]),
                month=int(config["dates"]["publication_month"]),
                day=1,
            ) + pd.offsets.MonthEnd(0)
            fenetre = pd.Series(
                np.where(
                    s.index <= fin, "in_sample", np.where(s.index <= pub, "post_sample", "post_publication")
                ),
                index=s.index,
            )
            ligne: dict[str, Any] = {
                "predictor": acronyme,
                "authors": fiche.loc[acronyme, "authors"],
                "publication_year": int(fiche.loc[acronyme, "publication_year"]),
                "sample_end_year": int(fiche.loc[acronyme, "sample_end_year"]),
                "op_tstat": float(fiche.loc[acronyme, "op_tstat"])
                if pd.notna(fiche.loc[acronyme, "op_tstat"])
                else float("nan"),
                "start": str(s.index.min().date()),
                "end": str(s.index.max().date()),
            }
            mesuree = pd.Series(True, index=s.index)
            for w in WINDOWS:
                bloc = s[fenetre == w]
                assez = len(bloc) >= minimum
                mesuree[fenetre == w] = assez
                d = _describe_window(bloc) if assez else {"n_months": len(bloc)}
                ligne.update({f"{w}_{k}": v for k, v in d.items()})
            mu = ligne.get("in_sample_mean_monthly_pct", float("nan")) / 100
            if not np.isfinite(mu) or (config["pooling"]["require_positive_in_sample_mean"] and mu <= 0):
                ligne["excluded_reason"] = (
                    "fenêtre de l'article trop courte"
                    if not np.isfinite(mu)
                    else "rendement moyen non positif dans la fenêtre de l'article"
                )
                lignes.append(ligne)
                continue
            for w in WINDOWS[1:]:
                if f"{w}_mean_monthly_pct" in ligne:
                    ligne[f"{w}_return_ratio"] = (ligne[f"{w}_mean_monthly_pct"] / 100) / mu
                    ligne[f"{w}_sharpe_ratio_ratio"] = ligne[f"{w}_sharpe"] / ligne["in_sample_sharpe"]
            lignes.append(ligne)
            piles.append(
                pd.DataFrame(
                    {
                        "predictor": acronyme,
                        "window": fenetre,
                        "scaled": s / mu,
                        "raw": s,
                        "measured": mesuree,
                    }
                )
            )
        fenetres = pd.DataFrame(lignes).set_index("predictor")
        _write_table(fenetres, "windows")
        stack_total = pd.concat(piles)
        stack = stack_total[stack_total["measured"]]
        metrics["coverage"] = {
            "n_predictors_documented": len(fenetres),
            "n_predictors_without_doc": len(ecartes),
            "n_excluded": int(fenetres["excluded_reason"].notna().sum())
            if "excluded_reason" in fenetres.columns
            else 0,
            "n_in_regression": int(stack["predictor"].nunique()),
            "excluded_months_below_threshold": int((~stack_total["measured"]).sum()),
        }

    with stage("mise en commun"):
        n_boot = int(config["pooling"]["bootstrap_resamples"])
        pooled: dict[str, Any] = {}
        for w in WINDOWS[1:]:
            ratios = fenetres[f"{w}_return_ratio"].dropna()
            sharpes = fenetres[f"{w}_sharpe_ratio_ratio"].dropna()
            lo, hi = _bootstrap_mean(ratios.to_numpy(), rng, n_boot)
            lo_s, hi_s = _bootstrap_mean(sharpes.to_numpy(), rng, n_boot)
            pooled[w] = {
                "n_predictors": len(ratios),
                "mean_return_ratio": float(ratios.mean()),
                "median_return_ratio": float(ratios.median()),
                "mean_return_decline": float(1.0 - ratios.mean()),
                "median_return_decline": float(1.0 - ratios.median()),
                "decline_ci95_low": float(1.0 - hi),
                "decline_ci95_high": float(1.0 - lo),
                "share_declining": float((ratios < 1.0).mean()),
                "share_negative": float((ratios < 0.0).mean()),
                "mean_sharpe_ratio_ratio": float(sharpes.mean()),
                "sharpe_decline_ci95_low": float(1.0 - hi_s),
                "sharpe_decline_ci95_high": float(1.0 - lo_s),
            }
        regression = _pooled_regression(stack)
        pooled["regression"] = regression
        metrics["pooled"] = pooled

        baisse = 1.0 - fenetres["post_publication_return_ratio"]
        valides = baisse.notna() & fenetres["in_sample_t_stat"].notna()
        metrics["heterogeneity"] = {
            "vs_in_sample_t_ours": _spearman_permutation(
                fenetres.loc[valides, "in_sample_t_stat"].to_numpy(), baisse[valides].to_numpy(), rng, n_boot
            ),
        }
        # La lecture de l'article porte sur le NIVEAU du rendement de l'échantillon,
        # pas sur son t ; les deux sont testés, et le troisième contre le t publié.
        metrics["heterogeneity"]["vs_in_sample_mean"] = _spearman_permutation(
            fenetres.loc[valides, "in_sample_mean_monthly_pct"].to_numpy(),
            baisse[valides].to_numpy(),
            rng,
            n_boot,
        )
        # La baisse ABSOLUE, en points de rendement mensuel, contre le niveau de
        # l'échantillon : c'est la lecture littérale de l'article, et elle est
        # mécaniquement positive par retour à la moyenne des estimations.
        absolue = fenetres["in_sample_mean_monthly_pct"] - fenetres["post_publication_mean_monthly_pct"]
        valides_abs = absolue.notna() & fenetres["in_sample_mean_monthly_pct"].notna()
        metrics["heterogeneity"]["absolute_decline_vs_in_sample_mean"] = _spearman_permutation(
            fenetres.loc[valides_abs, "in_sample_mean_monthly_pct"].to_numpy(),
            absolue[valides_abs].to_numpy(),
            rng,
            n_boot,
        )
        valides_op = baisse.notna() & fenetres["op_tstat"].notna()
        metrics["heterogeneity"]["vs_op_tstat"] = _spearman_permutation(
            fenetres.loc[valides_op, "op_tstat"].to_numpy(), baisse[valides_op].to_numpy(), rng, n_boot
        )

        decennies = []
        for debut in config["pooling"]["publication_decades"]:
            masque = (
                (fenetres["publication_year"] >= debut)
                & (fenetres["publication_year"] < debut + 10)
                & baisse.notna()
            )
            if masque.sum() >= 5:
                sous = stack[stack["predictor"].isin(fenetres.index[masque])]
                decennies.append(
                    {
                        "decade": debut,
                        "n_predictors": int(masque.sum()),
                        "mean_return_decline": float(baisse[masque].mean()),
                        "regression_decline": _pooled_regression(sous)["post_publication_decline"],
                    }
                )
        decennies_df = pd.DataFrame(decennies).set_index("decade")
        _write_table(decennies_df, "by_publication_decade")
        metrics["by_publication_decade"] = decennies_df.to_dict(orient="index")

    with stage("figures"):
        ratios = fenetres["post_publication_return_ratio"].dropna() * 100
        with portfolio_style():
            fig = Figure(figsize=(10, 4.4))
            ax = fig.add_subplot(111)
            bornes = np.arange(-150, 201, 10)
            ax.hist(ratios.clip(-149, 199), bins=bornes, color=OKABE_ITO[0])
            ax.axvline(100, color="black", linewidth=0.8)
            ax.axvline(
                float(ratios.mean()),
                color=OKABE_ITO[3],
                linewidth=1.2,
                linestyle="--",
                label=f"moyenne {ratios.mean():.0f} %",
            )
            ax.axvline(42, color=OKABE_ITO[1], linewidth=1.2, linestyle=":", label="McLean et Pontiff, 42 %")
            ax.set_xlabel("Rendement après publication, en % du rendement de la fenêtre de l'article")
            ax.set_ylabel("Nombre de prédicteurs")
            ax.set_title(f"{len(ratios)} prédicteurs : ce que la publication laisse de leur rendement, en %")
            ax.legend()
            fig.tight_layout()
            save_figure(fig, FIGURES / "rapport_apres_publication")

            fig = Figure(figsize=(10, 4.6))
            ax = fig.add_subplot(111)
            x = fenetres.loc[valides, "in_sample_t_stat"]
            y = (1.0 - fenetres.loc[valides, "post_publication_return_ratio"]) * 100
            ax.scatter(x, y.clip(-150, 150), s=14, color=OKABE_ITO[0])
            ax.axhline(0, color="black", linewidth=0.6)
            ax.set_xlabel("t du rendement dans la fenêtre de l'article, au sens de Lo")
            ax.set_ylabel("Baisse après publication, en % (bornée à ±150)")
            h = metrics["heterogeneity"]["vs_in_sample_t_ours"]
            ax.set_title(
                f"{h['n']} prédicteurs : la baisse suit-elle la force de l'article ? "
                f"Corrélation de rang {h['spearman']:.2f}"
            )
            fig.tight_layout()
            save_figure(fig, FIGURES / "baisse_contre_t")

    with stage("verdict"):
        crit = VerdictCriteria(**config["verdict"])
        pub = config["published"]
        reg = metrics["pooled"]["regression"]
        checks = (
            ReplicationCheck(
                "baisse_apres_publication_regression",
                published=float(pub["post_publication_decline"]),
                ours=float(reg["post_publication_decline"]),
                tolerance=float(crit.replication_tolerance),
                tolerance_kind="relative",
                source="McLean et Pontiff (2016), résumé : 58 % après publication",
                note="régression groupée par mois, effet fixe par prédicteur",
            ),
            ReplicationCheck(
                "baisse_apres_echantillon_regression",
                published=float(pub["post_sample_decline"]),
                ours=float(reg["post_sample_decline"]),
                tolerance=float(crit.replication_tolerance),
                tolerance_kind="relative",
                source="McLean et Pontiff (2016), résumé : 26 % après l'échantillon",
                note="même régression, indicatrice d'après échantillon",
            ),
        )
        supporte = bool(
            reg["post_publication_decline"] > 0.0
            and metrics["pooled"]["post_publication"]["share_declining"] > 0.5
        )
        evidence = VerdictEvidence(
            hypothesis_supported=supporte,
            replication_checks=checks,
            notes="recherche propre sur les portefeuilles publiés de Chen et Zimmermann ; rien n'est négocié",
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
        universe=list(rendements.columns),
        date_start=str(rendements.index.min().date()),
        date_end=str(rendements.index.max().date()),
        cost_basis=CostBasis.GROSS,
        cost_assumptions={},
        n_trials=int(config["n_trials"]),
    ) as run:
        run.log_metric(
            "post_publication_decline", reg["post_publication_decline"], sample=SampleTag.OUT_OF_SAMPLE
        )
        run.log_metric("post_sample_decline", reg["post_sample_decline"], sample=SampleTag.OUT_OF_SAMPLE)
        run.set_verdict(verdict)
    LOG.info("étude terminée", extra={"verdict": verdict.value})


if __name__ == "__main__":
    main()

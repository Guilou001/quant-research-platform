"""Étude 014 : ce qui survit à la publication, sur nos huit réplications.

Le point d'entrée ne porte aucune logique réutilisable : il assemble les briques
de ``quantlab`` et écrit ses résultats dans ``results/``. Il est déterministe.

    uv run python studies/014_publication_decay/run.py
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
from quantlab.analytics.returns import resample_returns
from quantlab.analytics.visualization.figures import portfolio_style, save_figure
from quantlab.core.config import ExperimentConfig, load_config
from quantlab.core.determinism import make_generator
from quantlab.core.errors import ConfigError
from quantlab.core.logging import configure_logging, get_logger, stage
from quantlab.core.types import CostBasis, Frequency, ReturnKind, SampleTag
from quantlab.data.providers.aqr import AqrProvider
from quantlab.experiments import ExperimentRegistry
from quantlab.reporting.series import load_series
from quantlab.reporting.study import ReplicationCheck, VerdictCriteria, VerdictEvidence, decide_verdict
from quantlab.validation.bootstrap import bootstrap_confidence_interval, bootstrap_statistic

warnings.filterwarnings("ignore", category=FutureWarning, module="pandas")
STUDY_DIR = Path(__file__).resolve().parent
ROOT = STUDY_DIR.parents[1]
RESULTS = STUDY_DIR / "results"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"
MONTHLY = Frequency.MONTHLY
WINDOWS = ("in_sample", "post_sample", "post_publication")
LOG = get_logger("study.014")


def _write_table(frame: pd.DataFrame, name: str) -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    frame.to_csv(TABLES / f"{name}.csv")


def _paper_dates(spec: dict[str, Any]) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Lit la fin d'échantillon et le mois de publication dans la configuration de l'étude source."""
    config = load_config(ROOT / "studies" / spec["study"] / "config.yaml", ExperimentConfig)
    if config.paper_sample_end is None or config.publication_date is None:
        raise ConfigError(f"{spec['study']} : paper_sample_end et publication_date doivent être déclarés.")
    return pd.Timestamp(config.paper_sample_end), pd.Timestamp(config.publication_date)


def _load_series(key: str, spec: dict[str, Any]) -> pd.Series:
    """Charge la série de tête d'une stratégie, en mensuel, datée en fin de mois civile."""
    if spec["series"] == "aqr_tsmom":
        s = AqrProvider().tsmom_factors(start="1985-01-01")["TSMOM"]
    else:
        s = load_series(ROOT / "studies" / spec["study"] / "results", spec["series"])
    if s.index.to_series().diff().median() < pd.Timedelta(days=20):
        s = resample_returns(s, MONTHLY, ReturnKind.SIMPLE)
    s.index = s.index.to_period("M").to_timestamp("M")
    return s.dropna().rename(key)


def _window_of(index: pd.DatetimeIndex, fin: pd.Timestamp, pub: pd.Timestamp) -> pd.Series:
    """Étiquette chaque mois : fenêtre de l'article, après échantillon, après publication."""
    etiquettes = np.where(
        index <= fin, "in_sample", np.where(index <= pub, "post_sample", "post_publication")
    )
    return pd.Series(etiquettes, index=index)


def _describe_window(s: pd.Series) -> dict[str, float]:
    """Le rendement moyen, son t au sens de Lo (2002), et le ratio de Sharpe d'une fenêtre."""
    n = len(s)
    return {
        "n_months": n,
        "mean_monthly_pct": float(s.mean()) * 100,
        "t_stat": float(sharpe_tstat(s, frequency=MONTHLY)) if n > 1 else float("nan"),
        "sharpe": float(sharpe_ratio(s, frequency=MONTHLY)) if n > 1 else float("nan"),
    }


def _pooled_regression(stack: pd.DataFrame) -> dict[str, Any]:
    """La régression de l'article : rendement normalisé sur deux indicatrices, effet fixe par stratégie.

    Le rendement de chaque stratégie est divisé par sa moyenne dans la fenêtre de
    l'article, donc l'indicatrice mesure directement la part perdue. Les erreurs
    types sont groupées par mois, parce que les huit stratégies partagent les
    mêmes mois et donc les mêmes chocs.
    """
    y = stack["scaled"].to_numpy()
    X = pd.get_dummies(stack["strategy"], dtype=float)
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
    }


def _bootstrap_mean(values: np.ndarray, rng: np.random.Generator, n: int) -> tuple[float, float]:
    """Intervalle à 95 % de la moyenne par rééchantillonnage indépendant des stratégies."""
    distribution = bootstrap_statistic(values, lambda x: float(np.mean(x)), "iid", n, rng)
    intervalle = bootstrap_confidence_interval(distribution, 0.95, "percentile")
    return float(intervalle.low), float(intervalle.high)


def _spearman_permutations(x: np.ndarray, y: np.ndarray, rng: np.random.Generator, n: int) -> np.ndarray:
    """Les corrélations de rang de ``n`` permutations de ``y``, en un produit matriciel."""
    rx = stats.rankdata(x)
    rx = (rx - rx.mean()) / rx.std()
    ry = stats.rankdata(y)
    ry = (ry - ry.mean()) / ry.std()
    permutees = np.array([rng.permutation(ry) for _ in range(n)])
    return permutees @ rx / len(rx)


def main() -> None:
    configure_logging("INFO")
    config = yaml.safe_load((STUDY_DIR / "config.yaml").read_text(encoding="utf-8"))
    for d in (RESULTS, TABLES, FIGURES):
        d.mkdir(parents=True, exist_ok=True)
    rng = make_generator(int(config["seed"]))
    metrics: dict[str, Any] = {"published": config["published"]}
    minimum = int(config["pooling"]["min_months_per_window"])

    with stage("fenêtres"):
        lignes: list[dict[str, Any]] = []
        piles: list[pd.DataFrame] = []
        for key, spec in config["strategies"].items():
            s = _load_series(key, spec)
            fin, pub = _paper_dates(spec)
            fenetre = _window_of(s.index, fin, pub)
            ligne: dict[str, Any] = {
                "strategy": key,
                "label": spec["label"],
                "start": str(s.index.min().date()),
                "end": str(s.index.max().date()),
                "sample_end": str(fin.date()),
                "publication": str(pub.date()),
            }
            mesuree = pd.Series(True, index=s.index)
            for w in WINDOWS:
                bloc = s[fenetre == w]
                assez = len(bloc) >= minimum
                mesuree[fenetre == w] = assez
                d = _describe_window(bloc) if assez else {"n_months": len(bloc)}
                ligne.update({f"{w}_{k}": v for k, v in d.items()})
            mu = ligne["in_sample_mean_monthly_pct"] / 100
            for w in WINDOWS[1:]:
                if f"{w}_mean_monthly_pct" in ligne:
                    ligne[f"{w}_return_ratio"] = (ligne[f"{w}_mean_monthly_pct"] / 100) / mu
                    ligne[f"{w}_sharpe_ratio_ratio"] = ligne[f"{w}_sharpe"] / ligne["in_sample_sharpe"]
            lignes.append(ligne)
            piles.append(
                pd.DataFrame(
                    {"strategy": key, "window": fenetre, "scaled": s / mu, "raw": s, "measured": mesuree}
                )
            )
        fenetres = pd.DataFrame(lignes).set_index("strategy")
        _write_table(fenetres, "windows")
        stack_total = pd.concat(piles)
        _write_table(stack_total, "stacked_returns")
        # La régression ne voit que les fenêtres mesurées : le seuil de vingt-quatre
        # mois vaut pour les deux mesures, sinon elles ne se comparent pas.
        stack = stack_total[stack_total["measured"]]
        metrics["excluded_months_below_threshold"] = int((~stack_total["measured"]).sum())

    with stage("mise en commun"):
        n_boot = int(config["pooling"]["bootstrap_resamples"])
        pooled: dict[str, Any] = {}
        for w in WINDOWS[1:]:
            ratios = fenetres[f"{w}_return_ratio"].dropna()
            sharpes = fenetres[f"{w}_sharpe_ratio_ratio"].dropna()
            lo, hi = _bootstrap_mean(ratios.to_numpy(), rng, n_boot)
            lo_s, hi_s = _bootstrap_mean(sharpes.to_numpy(), rng, n_boot)
            pooled[w] = {
                "n_strategies": len(ratios),
                "mean_return_ratio": float(ratios.mean()),
                "median_return_ratio": float(ratios.median()),
                "mean_return_decline": float(1.0 - ratios.mean()),
                "decline_ci95_low": float(1.0 - hi),
                "decline_ci95_high": float(1.0 - lo),
                "n_strategies_declining": int((ratios < 1.0).sum()),
                "n_strategies_negative": int((ratios < 0.0).sum()),
                "mean_sharpe_ratio_ratio": float(sharpes.mean()),
                "sharpe_decline_ci95_low": float(1.0 - hi_s),
                "sharpe_decline_ci95_high": float(1.0 - lo_s),
            }
        regression = _pooled_regression(stack)
        pooled["regression"] = regression
        metrics["pooled"] = pooled

        # Hétérogénéité : la baisse est-elle plus forte là où le t de l'article était plus haut ?
        t_is = fenetres["in_sample_t_stat"]
        baisse = 1.0 - fenetres["post_publication_return_ratio"]
        rho, _ = stats.spearmanr(t_is, baisse)
        permutations = _spearman_permutations(t_is.to_numpy(), baisse.to_numpy(), rng, n_boot)
        metrics["heterogeneity"] = {
            "spearman_t_in_sample_vs_decline": float(rho),
            "permutation_p_value": float((np.abs(permutations) >= abs(rho)).mean()),
            "n_strategies": len(t_is),
        }

        # Robustesse : retirer une stratégie à la fois.
        retraits = []
        for key in fenetres.index:
            reste = fenetres.drop(index=key)["post_publication_return_ratio"]
            sous = stack[stack["strategy"] != key]
            retraits.append(
                {
                    "dropped": key,
                    "mean_return_decline": float(1.0 - reste.mean()),
                    "regression_decline": _pooled_regression(sous)["post_publication_decline"],
                }
            )
        retraits_df = pd.DataFrame(retraits).set_index("dropped")
        _write_table(retraits_df, "leave_one_out")
        metrics["leave_one_out"] = {
            "min_mean_return_decline": float(retraits_df["mean_return_decline"].min()),
            "max_mean_return_decline": float(retraits_df["mean_return_decline"].max()),
            "min_regression_decline": float(retraits_df["regression_decline"].min()),
            "max_regression_decline": float(retraits_df["regression_decline"].max()),
        }

    with stage("figure"):
        ordre = list(fenetres.index)
        largeur = 0.27
        x = np.arange(len(ordre))
        couleurs = dict(zip(WINDOWS, (OKABE_ITO[0], OKABE_ITO[1], OKABE_ITO[3]), strict=True))
        libelles = {
            "in_sample": "fenêtre de l'article",
            "post_sample": "après l'échantillon, avant publication",
            "post_publication": "après publication",
        }
        sharpes = fenetres[[f"{w}_sharpe" for w in WINDOWS]].loc[ordre]
        with portfolio_style():
            fig = Figure(figsize=(10, 4.6))
            ax = fig.add_subplot(111)
            for i, w in enumerate(WINDOWS):
                ax.bar(
                    x + (i - 1) * largeur,
                    sharpes[f"{w}_sharpe"],
                    width=largeur,
                    color=couleurs[w],
                    label=libelles[w],
                )
            ax.axhline(0, color="black", linewidth=0.6)
            ax.set_xticks(x, [config["strategies"][k]["label"] for k in ordre], rotation=25, ha="right")
            ax.set_ylabel("Ratio de Sharpe annualisé, brut")
            ax.set_title(f"{len(ordre)} stratégies, trois fenêtres : ce que la publication laisse")
            ax.legend(fontsize=9)
            fig.tight_layout()
            save_figure(fig, FIGURES / "sharpe_trois_fenetres")

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
                note="régression groupée par mois, huit stratégies, effet fixe par stratégie",
            ),
            ReplicationCheck(
                "baisse_apres_echantillon_regression",
                published=float(pub["post_sample_decline"]),
                ours=float(reg["post_sample_decline"]),
                tolerance=float(crit.replication_tolerance),
                tolerance_kind="relative",
                source="McLean et Pontiff (2016), résumé : 26 % après l'échantillon",
                note="même régression, indicatrice de la fenêtre entre échantillon et publication",
            ),
        )
        supporte = bool(
            reg["post_publication_decline"] > 0.0
            and metrics["pooled"]["post_publication"]["n_strategies_declining"] * 2
            > metrics["pooled"]["post_publication"]["n_strategies"]
        )
        evidence = VerdictEvidence(
            hypothesis_supported=supporte,
            replication_checks=checks,
            notes=(
                "recherche propre sur les séries brutes des huit réplications ; aucune "
                "stratégie négociée, donc aucun contrôle de robustesse de stratégie ne s'applique"
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
        universe=list(config["strategies"]),
        date_start=str(stack_total.index.min().date()),
        date_end=str(stack_total.index.max().date()),
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

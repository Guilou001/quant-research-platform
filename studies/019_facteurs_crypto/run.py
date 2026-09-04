"""Étude 019 : marché, taille et momentum sur les cryptomonnaies, actifs disparus compris.

uv run python studies/019_facteurs_crypto/run.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from quantlab.analytics.ratios import sharpe_ratio, sharpe_tstat
from quantlab.analytics.visualization.figures import cumulative_return_pct, save_figure
from quantlab.core.logging import configure_logging, get_logger, stage
from quantlab.core.types import CostBasis, Frequency, SampleTag
from quantlab.data.providers.coinmetrics import CoinMetricsProvider
from quantlab.experiments import ExperimentRegistry
from quantlab.reporting.series import save_series
from quantlab.reporting.study import VerdictCriteria, VerdictEvidence, decide_verdict

STUDY_DIR = Path(__file__).resolve().parent
RESULTS = STUDY_DIR / "results"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"
WEEKLY = Frequency.WEEKLY
LOG = get_logger("study.019")


def _write_table(frame: pd.DataFrame, name: str) -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    frame.to_csv(TABLES / f"{name}.csv")


def _weekly_panel(
    fournisseur: CoinMetricsProvider, actifs: list[str], config: dict[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rend les prix et capitalisations hebdomadaires, dernière observation de la semaine."""
    ancre = config["data"]["week_anchor"]
    debut = pd.Timestamp(config["data"]["start"])
    prix_hebdo: dict[str, pd.Series] = {}
    cap_hebdo: dict[str, pd.Series] = {}
    manquants = 0
    for actif in actifs:
        try:
            frame = fournisseur.asset_history(actif)
        except Exception:
            manquants += 1
            continue
        frame = frame[frame["date"] >= debut - pd.Timedelta(days=60)]
        if frame.empty:
            continue
        serie = frame.set_index("date")
        prix = serie["price_usd"].where(serie["price_usd"] > float(config["data"]["min_price_usd"]))
        cap = serie["market_cap_usd"]
        prix_hebdo[actif] = prix.resample(ancre).last()
        cap_hebdo[actif] = cap.resample(ancre).last()
    prix_h = pd.DataFrame(prix_hebdo).sort_index()
    cap_h = pd.DataFrame(cap_hebdo).sort_index().reindex(prix_h.index)
    LOG.info(
        "panneau hebdomadaire",
        extra={"n_assets": prix_h.shape[1], "n_weeks": len(prix_h), "missing_files": manquants},
    )
    return prix_h.loc[debut:], cap_h.loc[debut:]


def _factor_returns(
    prix: pd.DataFrame, cap: pd.DataFrame, config: dict[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Les trois facteurs, semaine par semaine, et leurs rotations, à la lecture de l'article."""
    rendements = prix.pct_change()
    seuil = float(config["data"]["min_market_cap_usd"])
    bas, haut = config["factors"]["size"]["breakpoints"]
    formation = int(config["factors"]["momentum"]["formation_weeks"])
    passe = prix / prix.shift(formation) - 1.0
    lignes = []
    poids_precedents: dict[str, pd.Series] = {}
    rotations = []
    for i in range(1, len(prix.index)):
        t_form, t = prix.index[i - 1], prix.index[i]
        eligibles = (
            cap.loc[t_form].notna()
            & (cap.loc[t_form] >= seuil)
            & prix.loc[t_form].notna()
            & prix.loc[t].notna()
        )
        univers = eligibles[eligibles].index
        if len(univers) < 10:
            continue
        r = rendements.loc[t, univers]
        c = cap.loc[t_form, univers]
        w_marche = c / c.sum()
        # Taille : le tiers du bas contre le tiers du haut, pondérés par la capitalisation.
        rang_cap = c.rank(pct=True)
        petits, grands = univers[rang_cap <= bas], univers[rang_cap > haut]
        w_taille = pd.Series(0.0, index=univers)
        w_taille[petits] = c[petits] / c[petits].sum()
        w_taille[grands] = -c[grands] / c[grands].sum()
        # Momentum : le rendement des trois semaines précédant t_form, tiers du haut contre tiers du bas.
        m = passe.loc[t_form, univers].dropna()
        w_mom = pd.Series(0.0, index=univers)
        if len(m) >= 10:
            rang_m = m.rank(pct=True)
            gagnants, perdants = m.index[rang_m > haut], m.index[rang_m <= bas]
            w_mom[gagnants] = c[gagnants] / c[gagnants].sum()
            w_mom[perdants] = -c[perdants] / c[perdants].sum()
        ligne = {"date": t, "n_assets": len(univers)}
        rot = {"date": t}
        for nom, w in (("market", w_marche), ("size", w_taille), ("momentum", w_mom)):
            ligne[nom] = float((w * r).sum())
            precedent = poids_precedents.get(nom)
            rot[nom] = (
                float((w - precedent.reindex(w.index).fillna(0.0)).abs().sum())
                if precedent is not None
                else float(w.abs().sum())
            )
            poids_precedents[nom] = w
        lignes.append(ligne)
        rotations.append(rot)
    facteurs = pd.DataFrame(lignes).set_index("date")
    rotations_df = pd.DataFrame(rotations).set_index("date")
    return facteurs, rotations_df, rendements


def _describe(s: pd.Series) -> dict[str, float]:
    s = s.dropna()
    return {
        "n_weeks": len(s),
        "mean_weekly_pct": float(s.mean() * 100),
        "sharpe": float(sharpe_ratio(s, frequency=WEEKLY)) if len(s) > 2 else float("nan"),
        "t_stat": float(sharpe_tstat(s, frequency=WEEKLY)) if len(s) > 2 else float("nan"),
        "annual_return_pct": float(((1 + s).prod() ** (52 / len(s)) - 1) * 100)
        if len(s) > 0
        else float("nan"),
    }


def main() -> None:
    configure_logging("INFO")
    config = yaml.safe_load((STUDY_DIR / "config.yaml").read_text(encoding="utf-8"))
    for d in (RESULTS, TABLES, FIGURES):
        d.mkdir(parents=True, exist_ok=True)
    metrics: dict[str, Any] = {}
    fin_article = pd.Timestamp(config["paper_sample_end"])
    publication = pd.Timestamp(config["publication_date"])

    with stage("données"):
        fournisseur = CoinMetricsProvider()
        actifs = fournisseur.assets()
        prix, cap = _weekly_panel(fournisseur, actifs, config)
        metrics["data"] = {
            "n_assets_repository": len(actifs),
            "n_assets_with_prices": int(prix.notna().any().sum()),
            "first_week": str(prix.index.min().date()),
            "last_week": str(prix.index.max().date()),
            "manifest_last": fournisseur.manifest().model_dump(mode="json"),
        }

    with stage("facteurs"):
        facteurs, rotations, _ = _factor_returns(prix, cap, config)
        _write_table(facteurs, "factors_weekly")
        _write_table(rotations, "turnover_weekly")
        metrics["universe"] = {
            "n_assets_mean": float(facteurs["n_assets"].mean()),
            "n_assets_min": int(facteurs["n_assets"].min()),
            "n_assets_max": int(facteurs["n_assets"].max()),
            "n_weeks": len(facteurs),
        }
        fenetres = {
            "in_sample": facteurs.loc[:fin_article],
            "post_sample": facteurs.loc[fin_article + pd.Timedelta(days=1) : publication],
            "post_publication": facteurs.loc[publication + pd.Timedelta(days=1) :],
        }
        metrics["gross"] = {
            w: {f: _describe(bloc[f]) for f in ("market", "size", "momentum")} for w, bloc in fenetres.items()
        }

    with stage("coûts"):
        grille = []
        nets: dict[float, pd.DataFrame] = {}
        for bps in config["costs"]["spread_grid_bps"]:
            net = (
                facteurs[["market", "size", "momentum"]]
                - rotations[["market", "size", "momentum"]] * float(bps) / 1e4
            )
            nets[float(bps)] = net
            for f in ("size", "momentum"):
                for w, bloc in fenetres.items():
                    n = net.loc[bloc.index, f]
                    grille.append({"spread_bps": float(bps), "factor": f, "window": w, **_describe(n)})
        grille_df = pd.DataFrame(grille)
        _write_table(grille_df, "cost_grid")
        base = float(config["costs"]["spread_bps"])
        metrics["net_at_base"] = {
            f: {w: _describe(nets[base].loc[bloc.index, f]) for w, bloc in fenetres.items()}
            for f in ("size", "momentum")
        }
        metrics["turnover_weekly_mean"] = {
            f: float(rotations[f].mean()) for f in ("market", "size", "momentum")
        }
        for f in ("market", "size", "momentum"):
            save_series(
                RESULTS,
                f"crypto_{f}_gross",
                facteurs[f],
                sample=SampleTag.OUT_OF_SAMPLE,
                basis=CostBasis.GROSS,
                frequency=WEEKLY,
                universe=(
                    "cryptomonnaies de Coin Metrics à plus d'un million de dollars, actifs disparus compris"
                ),
            )
        save_series(
            RESULTS,
            "crypto_momentum_net",
            nets[base]["momentum"],
            sample=SampleTag.OUT_OF_SAMPLE,
            basis=CostBasis.NET,
            frequency=WEEKLY,
            universe="cryptomonnaies de Coin Metrics à plus d'un million de dollars",
            cost_assumptions=f"{base} pb par unité négociée",
        )

    with stage("figure"):
        fig, _ = cumulative_return_pct(
            {
                "Marché, pondéré par la capitalisation": facteurs["market"],
                "Taille, petits moins grands": facteurs["size"],
                "Momentum, trois semaines, gagnants moins perdants": facteurs["momentum"],
                f"Momentum net de {base:.0f} pb": nets[base]["momentum"],
            },
            title=(
                f"Trois facteurs des cryptomonnaies, en %, "
                f"{facteurs.index.min().year}-{facteurs.index.max().year}"
            ),
        )
        save_figure(fig, FIGURES / "facteurs_crypto")

    with stage("verdict"):
        g = metrics["gross"]["in_sample"]
        supporte = all(g[f]["mean_weekly_pct"] > 0 for f in ("market", "size", "momentum"))
        oos = metrics["net_at_base"]["momentum"]["post_publication"]["sharpe"]
        evidence = VerdictEvidence(
            hypothesis_supported=bool(supporte),
            oos_sharpe=oos,
            notes=(
                "lecture de l'article depuis son résumé ; aucun chiffre publié n'est retenu "
                "comme contrôle de réplication"
            ),
        )
        verdict, reasons = decide_verdict(evidence, VerdictCriteria(**config["verdict"]))
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
        universe=["coinmetrics"],
        date_start=str(facteurs.index.min().date()),
        date_end=str(facteurs.index.max().date()),
        cost_basis=CostBasis.NET,
        cost_assumptions={"spread_bps": base},
        n_trials=int(config["n_trials"]),
    ) as run:
        run.log_metric("momentum_net_sharpe_post_publication", oos, sample=SampleTag.OUT_OF_SAMPLE)
        run.set_verdict(verdict)
    LOG.info("étude terminée", extra={"verdict": verdict.value})
    print(
        json.dumps(
            {k: metrics[k] for k in ("universe", "gross", "net_at_base", "turnover_weekly_mean", "verdict")},
            indent=1,
            default=str,
        )
    )


if __name__ == "__main__":
    main()

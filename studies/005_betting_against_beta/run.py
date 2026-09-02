"""Le point d'entrée de l'étude 005, parier contre le bêta.

Ce fichier orchestre et n'implémente rien de réutilisable. La stratégie vit dans
:mod:`quantlab.strategies.betting_against_beta`, les métriques dans
:mod:`quantlab.analytics`, les contrôles dans :mod:`quantlab.validation`.

Lancement :

.. code-block:: bash

    export QUANTLAB_USER_AGENT="votre nom votre courriel"
    uv run python studies/005_betting_against_beta/run.py
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
from scipy import stats

from quantlab.analytics.drawdown import max_drawdown
from quantlab.analytics.ratios import sharpe_ratio, sharpe_standard_error, sharpe_tstat
from quantlab.analytics.regression import beta as ols_beta
from quantlab.analytics.regression import factor_regression
from quantlab.analytics.risk import kurtosis, skewness, volatility
from quantlab.analytics.turnover import annualized_turnover, turnover_series
from quantlab.analytics.visualization import figures as viz
from quantlab.core.config import ExperimentConfig, load_config
from quantlab.core.determinism import child_generators
from quantlab.core.logging import get_logger, stage
from quantlab.core.types import AssetClass, CostBasis, Frequency, SampleTag
from quantlab.data.lake import read_table, table_exists, write_table
from quantlab.data.providers.aqr import AqrProvider
from quantlab.data.providers.french import FrenchProvider
from quantlab.data.providers.yahoo import YahooProvider, to_wide
from quantlab.execution.costs import LinearCostModel, breakeven_cost_bps
from quantlab.experiments import ExperimentRegistry
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
from quantlab.strategies.betting_against_beta import (
    BabResult,
    bab_portfolio,
    beta_identity_terms,
    financing_cost,
    frazzini_pedersen_beta,
    market_capitalization,
)
from quantlab.strategies.volatility_managed import hedged_spread
from quantlab.validation.bootstrap import block_bootstrap
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

LOG = get_logger("quantlab.studies.005")
STUDY_DIR = Path(__file__).resolve().parent
RESULTS = STUDY_DIR / "results"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"
MONTHLY = Frequency.MONTHLY
LAKE_DATASET = "study005_sp500_daily"

#: Les six fichiers de la bibliothèque de Kenneth French employés.
FRENCH_DATASETS: Mapping[str, str] = {
    "three_monthly": "F-F_Research_Data_Factors",
    "three_daily": "F-F_Research_Data_Factors_daily",
    "five_monthly": "F-F_Research_Data_5_Factors_2x3",
    "mom_monthly": "F-F_Momentum_Factor",
    "beta_portfolios": "Portfolios_Formed_on_BETA",
}

#: Le nom lisible de chaque pondération, employé dans les tableaux publiés.
WEIGHTING_LABELS: Mapping[str, str] = {
    "rank": "Rangs, celle de l'article",
    "equal": "Équipondérée",
    "cap": "Capitalisation",
}

#: Le nom lisible de chaque pondération interne aux déciles.
WITHIN_LABELS: Mapping[str, str] = {
    "value": "Capitalisation dans le décile",
    "equal": "Équipondérée dans le décile",
}


# --------------------------------------------------------------------------- #
# Les utilitaires d'écriture
# --------------------------------------------------------------------------- #
def _write_table(frame: pd.DataFrame, name: str) -> Path:
    """Écrit un tableau sous ``results/tables`` et rend son chemin."""
    TABLES.mkdir(parents=True, exist_ok=True)
    path = TABLES / f"{name}.csv"
    frame.to_csv(path, index=False)
    LOG.info("tableau écrit", extra={"name": name, "n_rows": len(frame)})
    return path


def _save_figure(fig: Any, name: str) -> Path:
    """Enregistre une figure en PNG et en PDF, et rend le chemin du PNG."""
    FIGURES.mkdir(parents=True, exist_ok=True)
    written = viz.save_figure(fig, FIGURES / name, vector=True)
    return next(p for p in written if p.suffix == ".png")


def _month_end(frame: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    """Ramène un index daté à la fin de mois calendaire, sans changer l'ordre."""
    sortie = frame.copy()
    sortie.index = pd.DatetimeIndex(sortie.index).to_period("M").to_timestamp("M")
    sortie.index.name = "date"
    return sortie


# --------------------------------------------------------------------------- #
# Le chargement
# --------------------------------------------------------------------------- #
def _load_french(provider: FrenchProvider) -> dict[str, Any]:
    """Télécharge les quatre fichiers de la bibliothèque de Kenneth French."""
    parsed = provider.parse(FRENCH_DATASETS["beta_portfolios"])
    return {
        "three_monthly": provider.fetch(FRENCH_DATASETS["three_monthly"]),
        "three_daily": provider.fetch(FRENCH_DATASETS["three_daily"]),
        "five_monthly": provider.fetch(FRENCH_DATASETS["five_monthly"]),
        "mom_monthly": provider.fetch(FRENCH_DATASETS["mom_monthly"]),
        "deciles_vw": parsed["value_weighted_returns_monthly"],
        "deciles_ew": parsed["equal_weighted_returns_monthly"],
        "n_firms": parsed["number_of_firms_in_portfolios"],
        "firm_size": parsed["average_firm_size"],
    }


def _load_prices(config: ExperimentConfig, *, refresh: bool = False) -> pd.DataFrame:
    """Télécharge les prix quotidiens de l'univers, ou les relit dans le lac."""
    if not refresh and table_exists(LAKE_DATASET, "bronze"):
        with stage("prix_lac"):
            brut = read_table(LAKE_DATASET, "bronze", engine="pandas")
            return to_wide(brut, config.data.price_field).sort_index()
    with stage("prix_yahoo", n_symbols=len(config.data.universe)):
        provider = YahooProvider(on_missing="drop", threads=True)
        morceaux = []
        taille = 60
        univers = list(config.data.universe)
        for depart in range(0, len(univers), taille):
            lot = univers[depart : depart + taille]
            morceaux.append(provider.fetch(lot, start=config.data.start, end=config.data.end))
        brut = pd.concat(morceaux, ignore_index=True)
        write_table(brut, LAKE_DATASET, "bronze", overwrite=True, notes="étude 005, jambe B2")
        return to_wide(brut, config.data.price_field).sort_index()


# --------------------------------------------------------------------------- #
# Les résumés
# --------------------------------------------------------------------------- #
def _summary(series: pd.Series, market: pd.Series | None = None) -> dict[str, float]:
    """Rend le résumé chiffré d'une série mensuelle de rendements."""
    propre = series.dropna()
    erreur = sharpe_standard_error(propre, frequency=MONTHLY)
    ligne = {
        "n_months": float(len(propre)),
        "monthly_pct": float(propre.mean()) * 100.0,
        "annual_pct": float(propre.mean()) * 1200.0,
        "annual_vol_pct": volatility(propre, frequency=MONTHLY) * 100.0,
        "sharpe": sharpe_ratio(propre, frequency=MONTHLY),
        "sharpe_se_lo": float(erreur.lo),
        "sharpe_tstat": sharpe_tstat(propre, frequency=MONTHLY),
        "mean_tstat": float(propre.mean() / (propre.std(ddof=1) / math.sqrt(len(propre)))),
        "max_drawdown_pct": max_drawdown(propre) * 100.0,
        "skewness": skewness(propre),
        "excess_kurtosis": kurtosis(propre),
    }
    if market is not None:
        aligne = market.reindex(propre.index)
        ligne["realized_beta"] = ols_beta(propre, aligne)
    return ligne


def _sharpe_difference(a: pd.Series, b: pd.Series) -> dict[str, float]:
    """Teste l'égalité de deux ratios de Sharpe sur deux fenêtres disjointes.

    Les deux fenêtres ne se recouvrent pas, donc les estimateurs sont
    indépendants et la variance de leur écart est la somme des variances. La
    statistique est le rapport de l'écart à la racine de cette somme.
    """
    sa = sharpe_ratio(a, frequency=MONTHLY)
    sb = sharpe_ratio(b, frequency=MONTHLY)
    ea = sharpe_standard_error(a, frequency=MONTHLY).lo
    eb = sharpe_standard_error(b, frequency=MONTHLY).lo
    ecart = float(sa - sb)
    erreur = float(math.sqrt(ea**2 + eb**2))
    z = ecart / erreur if erreur > 0.0 else float("nan")
    return {
        "sharpe_before": float(sa),
        "sharpe_after": float(sb),
        "difference": ecart,
        "se_difference": erreur,
        "z": float(z),
        "pvalue": float(2.0 * (1.0 - stats.norm.cdf(abs(z)))),
    }


def _regression_row(
    series: pd.Series, factors: pd.DataFrame, columns: Sequence[str], label: str
) -> dict[str, Any]:
    """Rend l'alpha mensuel et les chargements d'une régression factorielle."""
    aligne = factors.reindex(series.index).loc[:, list(columns)].dropna()
    fit = factor_regression(
        series.reindex(aligne.index),
        aligne,
        cov_type="nonrobust",
        annualize_alpha=False,
        frequency=MONTHLY,
    )
    ligne: dict[str, Any] = {
        "model": label,
        "n_months": fit.n_obs,
        "alpha_monthly_pct": fit.alpha * 100.0,
        "alpha_tstat": fit.alpha_tstat,
        "r_squared": fit.r_squared,
    }
    for nom in fit.factor_names:
        ligne[f"beta_{nom}"] = float(fit.betas[nom])
    return ligne


def _cost_series(positions: pd.DataFrame, rate_bps: float, index: pd.Index) -> pd.Series:
    """Rend le coût de rotation par période, aligné sur les dates de détention."""
    if rate_bps <= 0.0:
        return pd.Series(0.0, index=index, name="cost")
    modele = LinearCostModel(spread_bps=rate_bps)
    dates = list(positions.index)
    valeurs: list[float] = [0.0]
    for precedent, courant in itertools.pairwise(dates):
        valeurs.append(float(modele.cost(previous=positions.loc[precedent], target=positions.loc[courant])))
    return pd.Series(valeurs, index=index, name="cost")


def _net_returns(result: BabResult, rate_bps: float, spread_bps_annual: float, basis: str) -> pd.Series:
    """Rend le rendement net des frais de rotation et du coût du levier."""
    couts = _cost_series(result.positions, rate_bps, result.returns.index)
    financement = financing_cost(
        result.leverage_low,
        result.leverage_high,
        spread_bps_annual=spread_bps_annual,
        periods_per_year=12.0,
        basis=basis,  # type: ignore[arg-type]
    )
    return (result.returns - couts - financement.reindex(result.returns.index).fillna(0.0)).rename("net")


def _breakeven_financing(result: BabResult, basis: str, rate_bps: float = 0.0) -> float:
    """Rend l'écart de financement annuel qui annule le rendement moyen.

    Le coût est linéaire dans l'écart, donc le point d'annulation se calcule en
    fermé : l'écart cherché vaut le rendement mensuel moyen divisé par le
    montant emprunté moyen, ramené à l'année.

    Args:
        result: le portefeuille dont le rendement s'annule.
        basis: la base de facturation du levier, ``« net »`` ou ``« gross »``.
        rate_bps: le coût de rotation facturé au rendement avant la résolution.
            Zéro rend le point d'annulation du rendement BRUT de frais de
            rotation, la valeur de l'étude celui du rendement NET.
    """
    montant = financing_cost(
        result.leverage_low, result.leverage_high, spread_bps_annual=10_000.0, basis=basis
    )
    montant = montant.reindex(result.returns.index).dropna()
    moyen = float(montant.mean())
    if moyen <= 0.0:
        return float("nan")
    rendement = _net_returns(result, rate_bps, 0.0, basis)
    return float(rendement.reindex(montant.index).mean() / moyen)


# --------------------------------------------------------------------------- #
# La construction des jambes
# --------------------------------------------------------------------------- #
def _decile_betas(
    returns: pd.DataFrame,
    market: pd.Series,
    params: Mapping[str, Any],
    *,
    shrinkage: float,
) -> pd.DataFrame:
    """Rend les bêtas ex ante mensuels des déciles triés par bêta."""
    commun = returns.index.intersection(market.index)
    estimate = frazzini_pedersen_beta(
        returns.loc[commun],
        market.loc[commun],
        volatility_window=int(params["volatility_window_months"]),
        volatility_min_periods=int(params["volatility_min_months"]),
        correlation_window=int(params["correlation_window_months"]),
        correlation_min_periods=int(params["correlation_min_months"]),
        overlap=1,
        shrinkage_weight=shrinkage,
    )
    return estimate.beta.dropna(how="all")


def _stock_betas(
    daily_returns: pd.DataFrame,
    daily_market: pd.Series,
    *,
    volatility_window: int,
    volatility_min: int,
    correlation_window: int,
    correlation_min: int,
    overlap: int,
    alignment: str,
    shrinkage: float,
) -> pd.DataFrame:
    """Rend les bêtas ex ante de fin de mois, estimés sur données quotidiennes."""
    commun = daily_returns.index.intersection(daily_market.index)
    estimate = frazzini_pedersen_beta(
        daily_returns.loc[commun],
        daily_market.loc[commun],
        volatility_window=volatility_window,
        volatility_min_periods=volatility_min,
        correlation_window=correlation_window,
        correlation_min_periods=correlation_min,
        overlap=overlap,
        alignment=alignment,  # type: ignore[arg-type]
        shrinkage_weight=shrinkage,
    )
    return _month_end(estimate.beta.resample("ME").last())


def _turnover(result: BabResult) -> pd.Series:
    """Rend la rotation par mois, réindexée sur les dates de DÉTENTION.

    La rotation se mesure entre deux dates de formation consécutives, mais elle
    se paie sur le rendement du mois suivant. Recoller les deux index évite un
    décalage d'un mois dans le coût de rentabilité.
    """
    rotation = turnover_series(result.positions, drifted=False, convention="full_sum", include_initial=False)
    return pd.Series(rotation.to_numpy(), index=result.returns.index[1:], name="turnover")


def _alpha_at_spread(
    result: BabResult, factors: pd.DataFrame, spread: float, basis: str, rate_bps: float = 0.0
) -> float:
    """Rend l'alpha mensuel à quatre facteurs, net d'un écart de financement donné.

    L'argument ``rate_bps`` décide de la base de coût de l'alpha rendu. Zéro
    laisse la rotation gratuite, donc l'alpha est BRUT de frais de rotation.
    Les dix points de base de l'étude rendent l'alpha NET des deux coûts.
    """
    net = _net_returns(result, rate_bps, spread, basis)
    aligne = factors.reindex(net.index)[["MKT-RF", "SMB", "HML", "MOM"]].dropna()
    fit = factor_regression(
        net.reindex(aligne.index),
        aligne,
        cov_type="nonrobust",
        annualize_alpha=False,
        frequency=MONTHLY,
    )
    return float(fit.alpha) * 100.0


def _scaled_minimum(window: int, base_window: int, base_minimum: int) -> int:
    """Rend le minimum d'observations d'une fenêtre, dans la proportion de l'article.

    L'article exige 120 séances sur 252 et 750 sur 1 250. Une fenêtre plus
    courte que le minimum serait impossible à remplir, donc le minimum suit la
    fenêtre au même rapport.
    """
    return max(2, round(window * base_minimum / base_window))


def _equal_weighted_market(returns: pd.DataFrame, counts: pd.DataFrame) -> pd.Series:
    """Rend le marché équipondéré, chaque décile pesant son nombre de sociétés."""
    aligne = counts.reindex(index=returns.index, columns=returns.columns)
    poids = aligne.div(aligne.sum(axis=1), axis=0)
    return (returns * poids).sum(axis=1).rename("equal_weighted_market")


def main() -> None:
    """Mène l'étude de bout en bout et écrit tout ce qu'elle produit."""
    config = load_config(STUDY_DIR / "config.yaml", ExperimentConfig)
    params = config.params
    RESULTS.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)

    paper_end = pd.Timestamp(params["paper_sample_end"])
    publication = pd.Timestamp(params["publication_start"])
    deciles = list(params["french_decile_columns"])
    shrink_grid = [float(v) for v in params["shrinkage_weights_grid"]]
    base_shrink = float(params["shrinkage_weight"])
    weightings = list(params["weighting_methods"])
    withins = list(params["within_weightings"])
    spreads = [float(v) for v in params["financing_spreads_bps"]]
    bases = list(params["financing_bases"])
    multipliers = [float(m) for m in params["cost_multipliers"] if float(m) > 0.0]
    delays = [int(d) for d in params["execution_delays"]]
    vol_grid = [int(v) for v in params["volatility_windows_grid"]]
    corr_grid = [int(v) for v in params["correlation_windows_grid"]]
    overlap_grid = [int(v) for v in params["overlap_days_grid"]]

    # ------------------------------------------------------------------ #
    # 1. Les données, chargées avant l'ouverture du registre pour que le
    #    nombre d'essais soit exact et non estimé.
    # ------------------------------------------------------------------ #
    with stage("chargement"):
        aqr = AqrProvider()
        bab_published = aqr.bab_factors()
        french_provider = FrenchProvider()
        french = _load_french(french_provider)
        prices = _load_prices(config)

    bab_published = _month_end(bab_published)
    trois = _month_end(french["three_monthly"])
    cinq = _month_end(french["five_monthly"])
    momentum = _month_end(french["mom_monthly"])
    facteurs = trois.join(momentum[["MOM"]]).join(cinq[["RMW", "CMA"]])
    rf = trois["RF"]
    mkt_excess = trois["MKT-RF"]
    mkt_total = (mkt_excess + rf).rename("market")

    aggregates = set(params["aqr_aggregate_columns"])
    min_country = int(params["min_months_per_country"])
    pays = [
        colonne
        for colonne in bab_published.columns
        if colonne not in aggregates and int(bab_published[colonne].notna().sum()) >= min_country
    ]

    n_trials_attendus = (
        4
        + len(pays)
        + len(weightings) * len(withins) * len(shrink_grid)
        + 2 * len(shrink_grid)
        + len(params["hedge_methods"])
        + 2 * len(spreads) * len(bases)
        + len(multipliers)
        + len(delays)
        + len(vol_grid) * len(corr_grid) * len(shrink_grid)
        + len(overlap_grid)
        + 1
        + 1
    )

    registry = ExperimentRegistry()
    manifests: list[dict[str, Any]] = []
    counter = TrialCounter()

    with registry.run(
        name="005_betting_against_beta",
        hypothesis=config.hypothesis,
        config=config.model_dump(mode="json"),
        seed=config.seed,
        universe=list(config.data.universe),
        date_start=config.data.start,
        date_end=config.data.end,
        cost_basis=CostBasis.NET,
        cost_assumptions={
            "spread_bps": config.costs.spread_bps,
            "financing_spread_bps_annual": config.costs.financing_spread_bps_annual,
        },
        n_trials=n_trials_attendus,
    ) as run:
        for cle in ("three_monthly", "three_daily", "five_monthly", "mom_monthly", "beta_portfolios"):
            manifests.append(french_provider.manifest(FRENCH_DATASETS[cle]).model_dump(mode="json"))
        manifests.append(aqr.manifest(str(params["aqr_dataset"])).model_dump(mode="json"))

        sources = pd.DataFrame(
            [
                {
                    "source": "AQR",
                    "dataset": "Betting-Against-Beta-Equity-Factors-Monthly.xlsx",
                    "start": str(bab_published.index[0].date()),
                    "end": str(bab_published.index[-1].date()),
                    "n_rows": len(bab_published),
                    "n_columns": bab_published.shape[1],
                },
                {
                    "source": "Kenneth French",
                    "dataset": FRENCH_DATASETS["beta_portfolios"],
                    "start": str(french["deciles_vw"].index[0].date()),
                    "end": str(french["deciles_vw"].index[-1].date()),
                    "n_rows": len(french["deciles_vw"]),
                    "n_columns": french["deciles_vw"].shape[1],
                },
                {
                    "source": "Kenneth French",
                    "dataset": FRENCH_DATASETS["three_monthly"],
                    "start": str(trois.index[0].date()),
                    "end": str(trois.index[-1].date()),
                    "n_rows": len(trois),
                    "n_columns": trois.shape[1],
                },
                {
                    "source": "Kenneth French",
                    "dataset": FRENCH_DATASETS["three_daily"],
                    "start": str(french["three_daily"].index[0].date()),
                    "end": str(french["three_daily"].index[-1].date()),
                    "n_rows": len(french["three_daily"]),
                    "n_columns": french["three_daily"].shape[1],
                },
                {
                    "source": "Yahoo",
                    "dataset": "membres du S&P 500 relevés le 2026-09-02",
                    "start": str(pd.Timestamp(prices.index[0]).date()),
                    "end": str(pd.Timestamp(prices.index[-1]).date()),
                    "n_rows": len(prices),
                    "n_columns": prices.shape[1],
                },
            ]
        )
        _write_table(sources, "data_sources")

        # ------------------------------------------------------------------ #
        # 2. Jambe A, le facteur publié
        # ------------------------------------------------------------------ #
        with stage("jambe_a", experiment_id=run.record.experiment_id):
            usa = bab_published[str(params["aqr_us_column"])].dropna()
            fenetres = {
                "Échantillon complet du classeur": usa,
                "Jusqu'à la fin de l'article, mars 2012": usa.loc[:paper_end],
                "Après l'article, depuis avril 2012": usa.loc[usa.index > paper_end],
                "Après publication, depuis janvier 2014": usa.loc[usa.index >= publication],
            }
            lignes_a = []
            for etiquette, serie in fenetres.items():
                ligne = {"window": etiquette, "start": str(serie.index[0].date())}
                ligne.update({"end": str(serie.index[-1].date())})
                ligne.update(_summary(serie, mkt_excess))
                lignes_a.append(ligne)
                counter = counter.record("legA_windows", etiquette, ligne["sharpe"])
            windows_frame = pd.DataFrame(lignes_a)
            _write_table(windows_frame, "legA_windows")

            in_sample = fenetres["Jusqu'à la fin de l'article, mars 2012"]
            out_sample = fenetres["Après l'article, depuis avril 2012"]
            attribution = pd.DataFrame(
                [
                    _regression_row(serie, facteurs, colonnes, f"{modele}, {etiquette}")
                    for etiquette, serie in (
                        ("échantillon de l'article", in_sample),
                        ("après l'article", out_sample),
                    )
                    for modele, colonnes in (
                        ("un facteur", ["MKT-RF"]),
                        ("trois facteurs", ["MKT-RF", "SMB", "HML"]),
                        ("quatre facteurs", ["MKT-RF", "SMB", "HML", "MOM"]),
                        ("six facteurs", ["MKT-RF", "SMB", "HML", "MOM", "RMW", "CMA"]),
                    )
                ]
            )
            _write_table(attribution, "legA_attribution")

            lignes_pays = []
            for colonne in pays:
                serie = bab_published[colonne].dropna()
                avant = serie.loc[:paper_end]
                apres = serie.loc[serie.index > paper_end]
                ligne = {
                    "country": colonne,
                    "n_months": len(serie),
                    "start": str(serie.index[0].date()),
                    "sharpe_full": sharpe_ratio(serie, frequency=MONTHLY),
                    "sharpe_se_lo": float(sharpe_standard_error(serie, frequency=MONTHLY).lo),
                    "tstat_full": sharpe_tstat(serie, frequency=MONTHLY),
                    "annual_pct": float(serie.mean()) * 1200.0,
                }
                if len(avant) >= 24 and len(apres) >= 24:
                    ligne.update({f"test_{k}": v for k, v in _sharpe_difference(avant, apres).items()})
                lignes_pays.append(ligne)
                counter = counter.record("legA_countries", colonne, ligne["sharpe_full"])
            country_frame = pd.DataFrame(lignes_pays).sort_values("sharpe_full", ascending=False)
            _write_table(country_frame, "legA_countries")

            part_positive = float((country_frame["sharpe_full"] > 0.0).mean())
            difference_usa = _sharpe_difference(in_sample, out_sample)
            _write_table(
                pd.DataFrame([{"series": "AQR BAB USA", **difference_usa}]),
                "legA_sharpe_difference",
            )

        # ------------------------------------------------------------------ #
        # 3. Jambe B1, notre construction sur les déciles de Kenneth French
        # ------------------------------------------------------------------ #
        with stage("jambe_b1", experiment_id=run.record.experiment_id):
            vw = _month_end(french["deciles_vw"])[deciles]
            ew = _month_end(french["deciles_ew"])[deciles]
            n_firms = _month_end(french["n_firms"])[deciles]
            firm_size = _month_end(french["firm_size"])[deciles]
            caps = market_capitalization(n_firms, firm_size)
            marche_ew = _equal_weighted_market(ew, n_firms)
            rendements_internes = {"value": vw, "equal": ew}

            betas_par_retrecissement = {
                (interne, shrink): _decile_betas(cadre, mkt_total, params, shrinkage=shrink)
                for interne, cadre in rendements_internes.items()
                for shrink in shrink_grid
            }
            profil = pd.DataFrame(
                {
                    f"{interne}, rétrécissement {shrink:.1f}": betas_par_retrecissement[
                        (interne, shrink)
                    ].mean()
                    for interne in rendements_internes
                    for shrink in (1.0, base_shrink)
                }
            )
            profil.index.name = "portfolio"
            _write_table(profil.reset_index(), "legB_decile_betas")

            resultats_b1: dict[tuple[str, str, float], BabResult] = {}
            lignes_b1 = []
            for interne, ponderation, shrink in itertools.product(
                rendements_internes, weightings, shrink_grid
            ):
                betas = betas_par_retrecissement[(interne, shrink)]
                excedent = rendements_internes[interne].sub(rf, axis=0)
                resultat = bab_portfolio(
                    betas,
                    excedent,
                    weighting=ponderation,  # type: ignore[arg-type]
                    capitalization=caps,
                    min_names=int(params["min_names_deciles"]),
                )
                resultats_b1[(interne, ponderation, shrink)] = resultat
                ligne = {
                    "within": WITHIN_LABELS[interne],
                    "across": WEIGHTING_LABELS[ponderation],
                    "shrinkage": shrink,
                    **_summary(resultat.returns, mkt_excess),
                    "mean_leverage_low": float(resultat.leverage_low.mean()),
                    "mean_leverage_high": float(resultat.leverage_high.mean()),
                    "mean_beta_low": float(resultat.beta_low.mean()),
                    "mean_beta_high": float(resultat.beta_high.mean()),
                }
                lignes_b1.append(ligne)
                counter = counter.record("legB_deciles", f"{interne}-{ponderation}-{shrink}", ligne["sharpe"])
            weighting_frame = pd.DataFrame(lignes_b1)
            _write_table(weighting_frame, "legB_weighting")

            base_b1 = resultats_b1[("value", "rank", base_shrink)]
            realized_rows = []
            for (interne, ponderation, shrink), resultat in resultats_b1.items():
                if ponderation != "rank":
                    continue
                realized_rows.append(
                    {
                        "within": WITHIN_LABELS[interne],
                        "shrinkage": shrink,
                        "ex_ante_beta_low": float(resultat.beta_low.mean()),
                        "realized_beta_low": ols_beta(
                            resultat.low_leg, mkt_excess.reindex(resultat.low_leg.index)
                        ),
                        "ex_ante_beta_high": float(resultat.beta_high.mean()),
                        "realized_beta_high": ols_beta(
                            resultat.high_leg, mkt_excess.reindex(resultat.high_leg.index)
                        ),
                        "realized_beta_factor": ols_beta(
                            resultat.returns, mkt_excess.reindex(resultat.returns.index)
                        ),
                    }
                )
            _write_table(pd.DataFrame(realized_rows), "legB_realized_beta")

        # ------------------------------------------------------------------ #
        # 4. Jambe B2, notre construction au niveau du titre
        # ------------------------------------------------------------------ #
        with stage("jambe_b2", experiment_id=run.record.experiment_id):
            prix = prices.copy()
            prix.index = pd.DatetimeIndex(prix.index)
            quotidiens = prix.pct_change()
            trois_quotidien = french["three_daily"]
            marche_quotidien = (trois_quotidien["MKT-RF"] + trois_quotidien["RF"]).rename("market")
            mensuels = _month_end(prix.resample("ME").last().pct_change())
            excedent_titres = mensuels.sub(rf.reindex(mensuels.index), axis=0)

            def betas_titres(
                *,
                shrink: float,
                vol_window: int,
                corr_window: int,
                overlap: int,
                alignment: str,
            ) -> pd.DataFrame:
                """Rend les bêtas mensuels des titres à un réglage donné.

                Le minimum d'observations suit la fenêtre dans la même
                proportion que dans l'article, 120 séances sur 252 pour la
                volatilité et 750 sur 1 250 pour la corrélation. Garder le
                minimum fixe rendrait une fenêtre courte impossible à remplir.
                """
                return _stock_betas(
                    quotidiens,
                    marche_quotidien,
                    volatility_window=vol_window,
                    volatility_min=_scaled_minimum(
                        vol_window,
                        int(params["volatility_window_days"]),
                        int(params["volatility_min_days"]),
                    ),
                    correlation_window=corr_window,
                    correlation_min=_scaled_minimum(
                        corr_window,
                        int(params["correlation_window_days"]),
                        int(params["correlation_min_days"]),
                    ),
                    overlap=overlap,
                    alignment=alignment,
                    shrinkage=shrink,
                )

            base_reglage = {
                "vol_window": int(params["volatility_window_days"]),
                "corr_window": int(params["correlation_window_days"]),
                "overlap": int(params["overlap_days"]),
                "alignment": str(params["overlap_alignment"]),
            }
            resultats_b2: dict[tuple[str, float], BabResult] = {}
            lignes_b2 = []
            for ponderation, shrink in itertools.product(("rank", "equal"), shrink_grid):
                betas = betas_titres(shrink=shrink, **base_reglage)
                resultat = bab_portfolio(
                    betas,
                    excedent_titres,
                    weighting=ponderation,  # type: ignore[arg-type]
                    min_names=int(params["min_names_stocks"]),
                )
                resultats_b2[(ponderation, shrink)] = resultat
                ligne = {
                    "across": WEIGHTING_LABELS[ponderation],
                    "shrinkage": shrink,
                    **_summary(resultat.returns, mkt_excess),
                    "mean_leverage_low": float(resultat.leverage_low.mean()),
                    "mean_leverage_high": float(resultat.leverage_high.mean()),
                    "ex_ante_beta_low": float(resultat.beta_low.mean()),
                    "realized_beta_low": ols_beta(
                        resultat.low_leg, mkt_excess.reindex(resultat.low_leg.index)
                    ),
                    "ex_ante_beta_high": float(resultat.beta_high.mean()),
                    "realized_beta_high": ols_beta(
                        resultat.high_leg, mkt_excess.reindex(resultat.high_leg.index)
                    ),
                    "mean_n_names": float(resultat.n_names.mean()),
                    "n_missing_returns": float(resultat.n_missing_returns),
                }
                lignes_b2.append(ligne)
                counter = counter.record("legB_stocks", f"{ponderation}-{shrink}", ligne["sharpe"])
            stocks_frame = pd.DataFrame(lignes_b2)
            _write_table(stocks_frame, "legB_stocks")
            base_b2 = resultats_b2[("rank", base_shrink)]

            leverage_frame = pd.DataFrame(
                [
                    {
                        "leg": "Jambe longue, bêta faible",
                        "paper": float(params["paper_long_leverage"]),
                        "deciles_rank_value": float(base_b1.leverage_low.mean()),
                        "stocks_rank": float(base_b2.leverage_low.mean()),
                        "stocks_rank_no_shrinkage": float(resultats_b2[("rank", 1.0)].leverage_low.mean()),
                    },
                    {
                        "leg": "Jambe courte, bêta élevé",
                        "paper": float(params["paper_short_leverage"]),
                        "deciles_rank_value": float(base_b1.leverage_high.mean()),
                        "stocks_rank": float(base_b2.leverage_high.mean()),
                        "stocks_rank_no_shrinkage": float(resultats_b2[("rank", 1.0)].leverage_high.mean()),
                    },
                ]
            )
            _write_table(leverage_frame, "legB_leverage")

        # ------------------------------------------------------------------ #
        # 5. La critique de Novy-Marx et Velikov
        # ------------------------------------------------------------------ #
        with stage("critique", experiment_id=run.record.experiment_id):
            termes = beta_identity_terms(
                quotidiens,
                marche_quotidien,
                volatility_window=int(params["volatility_window_days"]),
                volatility_min_periods=int(params["volatility_min_days"]),
                correlation_window=int(params["correlation_window_days"]),
                correlation_min_periods=int(params["correlation_min_days"]),
                overlap=int(params["overlap_days"]),
                alignment=str(params["overlap_alignment"]),  # type: ignore[arg-type]
            )
            ecart_identite = float((termes["beta_fp"] - termes["beta_identity"]).abs().max().max())

            brut = betas_titres(
                shrink=1.0,
                vol_window=int(params["volatility_window_days"]),
                corr_window=int(params["correlation_window_days"]),
                overlap=int(params["overlap_days"]),
                alignment=str(params["overlap_alignment"]),
            )
            assez = brut.notna().sum(axis=1) >= int(params["min_names_stocks"])
            moyenne_transversale = brut[assez].mean(axis=1)
            dispersion = brut[assez].std(axis=1, ddof=1)
            vol_marche = _month_end(
                frazzini_pedersen_beta(
                    marche_quotidien.to_frame("market"),
                    marche_quotidien,
                    volatility_window=int(params["volatility_window_days"]),
                    volatility_min_periods=int(params["volatility_min_days"]),
                    correlation_window=int(params["correlation_window_days"]),
                    correlation_min_periods=int(params["correlation_min_days"]),
                    shrinkage_weight=1.0,
                )
                .market_volatility.resample("ME")
                .last()
            )
            artefact_rows = []
            for nom, serie in (("moyenne transversale", moyenne_transversale), ("dispersion", dispersion)):
                aligne = pd.DataFrame({"y": serie}).join(vol_marche.rename("x"), how="inner").dropna()
                pente, ordonnee, correlation, valeur_p, _ = stats.linregress(aligne["x"], aligne["y"])
                artefact_rows.append(
                    {
                        "quantity": nom,
                        "n_months": len(aligne),
                        "mean": float(serie.dropna().mean()),
                        "std": float(serie.dropna().std(ddof=1)),
                        "slope_on_market_volatility": float(pente),
                        "intercept": float(ordonnee),
                        "r_squared": float(correlation**2),
                        "pvalue": float(valeur_p),
                    }
                )
            artefact_frame = pd.DataFrame(artefact_rows)
            _write_table(artefact_frame, "nmv_beta_artifact")
            _write_table(
                pd.DataFrame(
                    [
                        {
                            "check": "identité de Novy-Marx et Velikov",
                            "max_absolute_difference": ecart_identite,
                            "n_cells": int(termes["beta_fp"].notna().sum().sum()),
                        }
                    ]
                ),
                "nmv_identity",
            )

            ecart_brut = (base_b1.low_leg - base_b1.high_leg).rename("spread")
            marche_ew_excedent = marche_ew.sub(rf).reindex(ecart_brut.index)
            series_couvertes = {
                "leverage": base_b1.returns,
                "market_value_weighted": hedged_spread(
                    ecart_brut, mkt_excess.reindex(ecart_brut.index), min_periods=60
                ).dropna(),
                "market_equal_weighted": hedged_spread(
                    ecart_brut, marche_ew_excedent, min_periods=60
                ).dropna(),
            }
            index_commun = series_couvertes["market_value_weighted"].index
            for serie in series_couvertes.values():
                index_commun = index_commun.intersection(serie.index)
            couvertures = []
            for methode in params["hedge_methods"]:
                serie = series_couvertes[methode].reindex(index_commun)
                ligne = {"hedge": methode, **_summary(serie, mkt_excess)}
                couvertures.append(ligne)
                counter = counter.record("hedge", methode, ligne["sharpe"])
            _write_table(pd.DataFrame(couvertures), "nmv_hedge")

        # ------------------------------------------------------------------ #
        # 6. Le levier et son prix
        # ------------------------------------------------------------------ #
        with stage("financement", experiment_id=run.record.experiment_id):
            series_financement = {
                "déciles, rangs, capitalisation": base_b1,
                "titres, rangs, sans rétrécissement": resultats_b2[("rank", 1.0)],
            }
            lignes_financement = []
            for nom, resultat in series_financement.items():
                for base, ecart in itertools.product(bases, spreads):
                    net = _net_returns(resultat, config.costs.spread_bps, ecart, base)
                    aligne = facteurs.reindex(net.index)[["MKT-RF", "SMB", "HML", "MOM"]].dropna()
                    fit = factor_regression(
                        net.reindex(aligne.index),
                        aligne,
                        cov_type="nonrobust",
                        annualize_alpha=False,
                        frequency=MONTHLY,
                    )
                    ligne = {
                        "series": nom,
                        "basis": base,
                        "spread_bps": ecart,
                        "net_annual_pct": float(net.mean()) * 1200.0,
                        "net_sharpe": sharpe_ratio(net, frequency=MONTHLY),
                        "alpha_4f_monthly_pct": fit.alpha * 100.0,
                        "alpha_tstat": fit.alpha_tstat,
                    }
                    lignes_financement.append(ligne)
                    counter = counter.record("financing", f"{nom}-{base}-{ecart}", ligne["net_sharpe"])
            financing_frame = pd.DataFrame(lignes_financement)

            # L'écart de financement entre linéairement dans le rendement, donc
            # l'alpha en est une fonction affine. Deux points suffisent alors à
            # résoudre exactement le point d'annulation.
            breakeven_rows = []
            for nom, resultat in (
                ("déciles, rangs, capitalisation", base_b1),
                ("titres, rangs", base_b2),
                ("titres, rangs, sans rétrécissement", resultats_b2[("rank", 1.0)]),
            ):
                for base in bases:
                    alpha_zero = _alpha_at_spread(resultat, facteurs, 0.0, base)
                    alpha_cent = _alpha_at_spread(resultat, facteurs, 100.0, base)
                    pente = alpha_cent - alpha_zero
                    annule = 100.0 * alpha_zero / (-pente) if pente < 0.0 else float("nan")
                    # Les quatre colonnes suffixées « net » facturent en plus les dix
                    # points de base de rotation de l'étude. Sans elles, l'écart qui
                    # annule l'alpha se lirait comme si la rotation était gratuite,
                    # alors que tout le reste de l'étude la facture.
                    rotation_bps = config.costs.spread_bps
                    alpha_zero_net = _alpha_at_spread(resultat, facteurs, 0.0, base, rotation_bps)
                    alpha_cent_net = _alpha_at_spread(resultat, facteurs, 100.0, base, rotation_bps)
                    pente_net = alpha_cent_net - alpha_zero_net
                    annule_net = 100.0 * alpha_zero_net / (-pente_net) if pente_net < 0.0 else float("nan")
                    breakeven_rows.append(
                        {
                            "series": nom,
                            "basis": base,
                            "mean_borrowed": float(
                                financing_cost(
                                    resultat.leverage_low,
                                    resultat.leverage_high,
                                    spread_bps_annual=10_000.0,
                                    basis=base,
                                ).mean()
                                * 12.0
                            ),
                            "breakeven_spread_bps": _breakeven_financing(resultat, base) * 10_000.0,
                            "alpha_4f_at_zero_pct": alpha_zero,
                            "alpha_zero_spread_bps": annule,
                            "breakeven_spread_net_bps": _breakeven_financing(resultat, base, rotation_bps)
                            * 10_000.0,
                            "alpha_4f_at_zero_net_pct": alpha_zero_net,
                            "alpha_zero_spread_net_bps": annule_net,
                        }
                    )
            breakeven_frame = pd.DataFrame(breakeven_rows)
            _write_table(financing_frame, "financing")
            _write_table(breakeven_frame, "financing_breakeven")

        # ------------------------------------------------------------------ #
        # 7. Les coûts de rotation
        # ------------------------------------------------------------------ #
        with stage("couts", experiment_id=run.record.experiment_id):
            cout_rows = []
            for nom, resultat in (
                ("déciles, rangs, capitalisation", base_b1),
                ("titres, rangs", base_b2),
                ("titres, rangs, sans rétrécissement", resultats_b2[("rank", 1.0)]),
            ):
                rotation = _turnover(resultat)
                net = _net_returns(resultat, config.costs.spread_bps, 0.0, str(params["financing_basis"]))
                cout_rows.append(
                    {
                        "series": nom,
                        "annual_turnover": annualized_turnover(rotation, frequency=MONTHLY),
                        "gross_annual_pct": float(resultat.returns.mean()) * 1200.0,
                        "net_annual_pct": float(net.mean()) * 1200.0,
                        "gross_sharpe": sharpe_ratio(resultat.returns, frequency=MONTHLY),
                        "net_sharpe": sharpe_ratio(net, frequency=MONTHLY),
                        "breakeven_cost_bps": breakeven_cost_bps(
                            resultat.returns.reindex(rotation.index), rotation, frequency=MONTHLY
                        ),
                    }
                )
            _write_table(pd.DataFrame(cout_rows), "costs")

            def evaluer_cout(multiplicateur: float) -> float:
                """Rend le Sharpe net de la série de référence à ce multiple de coût."""
                net = _net_returns(
                    base_b1,
                    config.costs.spread_bps * multiplicateur,
                    0.0,
                    str(params["financing_basis"]),
                )
                return sharpe_ratio(net, frequency=MONTHLY)

            analyse_cout = cost_multiplier_analysis(evaluer_cout, multipliers=multipliers, threshold=0.0)
            _write_table(analyse_cout.table, "cost_multiples")
            for multiplicateur, valeur in zip(
                analyse_cout.table["multiplier"], analyse_cout.table["metric"], strict=True
            ):
                counter = counter.record("cost_multiple", f"x{multiplicateur}", float(valeur))

        # ------------------------------------------------------------------ #
        # 8. La robustesse
        # ------------------------------------------------------------------ #
        with stage("robustesse", experiment_id=run.record.experiment_id):
            sweep_rows = []
            for vol_window, corr_window in itertools.product(vol_grid, corr_grid):
                for shrink in shrink_grid:
                    betas = betas_titres(
                        shrink=shrink,
                        vol_window=vol_window,
                        corr_window=corr_window,
                        overlap=int(params["overlap_days"]),
                        alignment=str(params["overlap_alignment"]),
                    )
                    resultat = bab_portfolio(
                        betas, excedent_titres, min_names=int(params["min_names_stocks"])
                    )
                    net = sharpe_ratio(
                        _net_returns(resultat, config.costs.spread_bps, 0.0, "net"), frequency=MONTHLY
                    )
                    sweep_rows.append(
                        {
                            "volatility_window": vol_window,
                            "correlation_window": corr_window,
                            "estimator": f"volatilité {vol_window} j, corrélation {corr_window} j",
                            # La virgule décimale du français, et non le point : la
                            # carte de chaleur affiche cette étiquette telle quelle.
                            "shrinkage_label": f"{shrink:.1f}".replace(".", ","),
                            "shrinkage": shrink,
                            "n_months": len(resultat.returns),
                            "net_sharpe": net,
                            "realized_beta": ols_beta(
                                resultat.returns, mkt_excess.reindex(resultat.returns.index)
                            ),
                        }
                    )
                    counter = counter.record("sweep", f"v{vol_window}-c{corr_window}-s{shrink}", net)
            sweep_frame = pd.DataFrame(sweep_rows)
            _write_table(sweep_frame, "parameter_sweep")

            overlap_rows = []
            for overlap in overlap_grid:
                betas = betas_titres(
                    shrink=base_shrink,
                    vol_window=int(params["volatility_window_days"]),
                    corr_window=int(params["correlation_window_days"]),
                    overlap=overlap,
                    alignment=str(params["overlap_alignment"]),
                )
                resultat = bab_portfolio(betas, excedent_titres, min_names=int(params["min_names_stocks"]))
                ligne = {
                    "overlap_days": overlap,
                    "alignment": str(params["overlap_alignment"]),
                    **_summary(resultat.returns, mkt_excess),
                }
                overlap_rows.append(ligne)
                counter = counter.record("overlap", f"o{overlap}", ligne["sharpe"])
            betas_avant = betas_titres(
                shrink=base_shrink,
                vol_window=int(params["volatility_window_days"]),
                corr_window=int(params["correlation_window_days"]),
                overlap=int(params["overlap_days"]),
                alignment="forward",
            )
            resultat_avant = bab_portfolio(
                betas_avant, excedent_titres, min_names=int(params["min_names_stocks"])
            )
            overlap_rows.append(
                {
                    "overlap_days": int(params["overlap_days"]),
                    "alignment": "forward",
                    **_summary(resultat_avant.returns, mkt_excess),
                }
            )
            counter = counter.record("overlap", "forward", overlap_rows[-1]["sharpe"])
            _write_table(pd.DataFrame(overlap_rows), "overlap_sweep")

            delay_rows = []
            for delai in delays:
                resultat = bab_portfolio(
                    betas_par_retrecissement[("value", base_shrink)],
                    vw.sub(rf, axis=0),
                    capitalization=caps,
                    min_names=int(params["min_names_deciles"]),
                    execution_lag=delai,
                )
                ligne = {"execution_lag": delai, **_summary(resultat.returns, mkt_excess)}
                delay_rows.append(ligne)
                counter = counter.record("delay", f"lag{delai}", ligne["sharpe"])
            _write_table(pd.DataFrame(delay_rows), "execution_delay")

            base_net = _net_returns(
                base_b1, config.costs.spread_bps, config.costs.financing_spread_bps_annual, "net"
            )
            counter = counter.record(
                "base", "deciles_rank_value_net", sharpe_ratio(base_net, frequency=MONTHLY)
            )
            sous_periodes = subperiod_performance(
                base_net,
                breakpoints=[pd.Timestamp(b) for b in params["subperiod_breakpoints"]],
                frequency=MONTHLY,
                min_observations=24,
            )
            sous_periodes["label"] = [
                f"{pd.Timestamp(a):%Y-%m} à {pd.Timestamp(b):%Y-%m}"
                for a, b in zip(sous_periodes["start"], sous_periodes["end"], strict=True)
            ]
            _write_table(sous_periodes, "subperiods")
            part_sous_periodes = float((sous_periodes["sharpe"] > 0.0).mean())

        # ------------------------------------------------------------------ #
        # 9. Les contrôles statistiques
        # ------------------------------------------------------------------ #
        with stage("validation", experiment_id=run.record.experiment_id):
            configurations = {
                f"{interne}-{ponderation}-{shrink}": resultat.returns
                for (interne, ponderation, shrink), resultat in resultats_b1.items()
            }
            performance_matrix = pd.DataFrame(configurations).dropna()
            pbo_result = probability_of_backtest_overfitting(
                performance_matrix, n_splits=int(config.validation.n_folds), frequency=MONTHLY
            )

            def meilleur_du_chemin(path: Any) -> float:
                """Retient la meilleure configuration du bloc d'apprentissage.

                La validation croisée combinatoire ne juge pas une série figée,
                mais le PROCESSUS de sélection. Sur chaque bloc d'apprentissage,
                la configuration de meilleur Sharpe est retenue, et son
                rendement du bloc de test suivant est collecté.
                """
                pieces: list[pd.Series] = []
                for segment in path.segments:
                    entrainement = performance_matrix.iloc[segment.train_index]
                    test = performance_matrix.iloc[segment.test_index]
                    meilleure = max(
                        performance_matrix.columns,
                        key=lambda colonne: sharpe_ratio(entrainement[colonne], frequency=MONTHLY),
                    )
                    pieces.append(test[meilleure])
                return sharpe_ratio(pd.concat(pieces).sort_index(), frequency=MONTHLY)

            cv = CombinatorialPurgedCV.from_config(config.validation)
            distribution = cpcv_performance_distribution(
                cv, performance_matrix, meilleur_du_chemin, metric_name="sharpe"
            )
            cpcv_frame = distribution.summary.rename("value").reset_index()
            cpcv_frame.columns = ["statistic", "value"]
            _write_table(cpcv_frame, "cpcv_distribution")
            _write_table(distribution.metrics.rename("sharpe").reset_index(), "cpcv_paths")

            holdout = base_net.loc[base_net.index > paper_end]
            oos_sharpe = sharpe_ratio(holdout, frequency=MONTHLY)
            oos_tstat = sharpe_tstat(holdout, frequency=MONTHLY)
            n_trials = counter.n_trials()
            trial_variance = counter.sharpe_variance()
            deflated = deflated_sharpe_ratio(
                observed_sr=oos_sharpe,
                sharpe_variance_across_trials=trial_variance,
                n_trials=n_trials,
                n_obs=float(len(holdout)),
                skew=skewness(holdout),
                kurtosis=kurtosis(holdout, excess=False),
            )
            attendu_max = expected_maximum_sharpe(n_trials, trial_variance)
            if oos_sharpe > 0.0:
                coupe = haircut_sharpe(
                    observed_sr=oos_sharpe,
                    n_tests=n_trials,
                    n_obs=len(holdout),
                    frequency=MONTHLY,
                    method="holm",
                )
                t_ajuste = coupe.adjusted_tstat
                statut = "calculé"
            else:
                t_ajuste = oos_tstat
                statut = (
                    "non défini : rabattre un ratio de Sharpe négatif n'a pas de sens, "
                    "la statistique t brute est reportée telle quelle"
                )
            deflation_frame = pd.DataFrame(
                [
                    {
                        "n_trials": n_trials,
                        "trial_sharpe_variance": trial_variance,
                        "expected_max_sharpe": attendu_max,
                        "oos_sharpe": oos_sharpe,
                        "oos_tstat": oos_tstat,
                        "deflated_sharpe": deflated,
                        "required_tstat_bonferroni": required_tstat(n_trials, 0.05, method="bonferroni"),
                        "adjusted_tstat": t_ajuste,
                        "haircut_status": statut,
                    }
                ]
            )
            _write_table(deflation_frame, "deflated_sharpe")

            valeurs_p = []
            for ligne in lignes_b1:
                t = abs(float(ligne["sharpe_tstat"]))
                valeurs_p.append(2.0 * (1.0 - 0.5 * (1.0 + math.erf(t / math.sqrt(2.0)))))
            multiplicite = adjust_pvalues(valeurs_p, method="holm", alpha=0.05)
            multiple_frame = pd.DataFrame(
                {
                    "within": [ligne["within"] for ligne in lignes_b1],
                    "across": [ligne["across"] for ligne in lignes_b1],
                    "shrinkage": [ligne["shrinkage"] for ligne in lignes_b1],
                    "sharpe": [ligne["sharpe"] for ligne in lignes_b1],
                    "tstat": [ligne["sharpe_tstat"] for ligne in lignes_b1],
                    "pvalue": valeurs_p,
                    "adjusted_pvalue": multiplicite.adjusted_pvalues,
                    "rejected": multiplicite.rejected,
                }
            ).sort_values("adjusted_pvalue")
            _write_table(multiple_frame, "multiple_testing")

            generateur = child_generators(config.seed, 1)[0]
            taille = max(1, round(float(params["bootstrap_block_months"])))
            tirages = block_bootstrap(
                holdout.to_numpy(),
                block_size=taille,
                n_resamples=int(params["bootstrap_resamples"]),
                generator=generateur,
            )
            moyennes = tirages.mean(axis=1) * 1200.0
            bootstrap_frame = pd.DataFrame(
                [
                    {
                        "n_resamples": int(params["bootstrap_resamples"]),
                        "block_months": taille,
                        "seed": config.seed,
                        "mean_annual_pct": float(moyennes.mean()),
                        "q025_annual_pct": float(np.quantile(moyennes, 0.025)),
                        "q975_annual_pct": float(np.quantile(moyennes, 0.975)),
                        "share_positive": float((moyennes > 0.0).mean()),
                    }
                ]
            )
            _write_table(bootstrap_frame, "bootstrap")

            trials_frame = pd.DataFrame(
                [{"family": famille, "n_trials": counter.n_trials(famille)} for famille in counter.families()]
                + [{"family": "TOTAL", "n_trials": n_trials}]
            )
            _write_table(trials_frame, "trials")
            if n_trials != n_trials_attendus:
                raise RuntimeError(
                    f"{n_trials} essais enregistrés contre {n_trials_attendus} annoncés au registre."
                )

        # ------------------------------------------------------------------ #
        # 10. Les figures
        # ------------------------------------------------------------------ #
        with stage("figures", experiment_id=run.record.experiment_id):
            figure_specs: list[tuple[str, str, str]] = []
            depart = max(base_b1.returns.index[0], usa.index[0])
            fig, _ = viz.equity_curve(
                {
                    "Notre BAB, déciles triés par bêta, rangs": base_b1.returns.loc[
                        base_b1.returns.index >= depart
                    ],
                    "Notre BAB, titres, rangs, sans rétrécissement": resultats_b2[("rank", 1.0)].returns,
                },
                benchmark=usa.loc[usa.index >= depart],
                benchmark_label="BAB publié par AQR, colonne USA",
                log_scale=True,
                currency="$ US",
                # Le titre ne peut pas annoncer une date de base commune : la courbe
                # des titres ne commence qu'en 2001, et l'axe le dit déjà.
                title=(
                    "Richesse cumulée du pari contre le bêta, base 1 dollar des États-Unis "
                    "au départ de chaque courbe"
                ),
            )
            figure_specs.append(
                (
                    _save_figure(fig, "equity_bab").stem,
                    "performance",
                    "Richesse cumulée du facteur publié et de nos deux reconstructions.",
                )
            )

            fig, _ = viz.underwater(base_b1.returns, title="Repli de notre BAB sur les déciles")
            figure_specs.append(
                (
                    _save_figure(fig, "underwater_bab").stem,
                    "performance",
                    "Distance au sommet précédent, en points de pourcentage.",
                )
            )

            # La carte de chaleur trie ses lignes en TEXTE, et « corrélation 750 j »
            # se placerait après « corrélation 2500 j ». L'ordre numérique est donc
            # imposé par une catégorie ordonnée, comme pour la carte par marché.
            heat_sweep = sweep_frame.copy()
            ordre_estimateur = (
                sweep_frame.sort_values(["volatility_window", "correlation_window"])["estimator"]
                .drop_duplicates()
                .tolist()
            )
            heat_sweep["estimator"] = pd.Categorical(
                heat_sweep["estimator"], categories=ordre_estimateur, ordered=True
            )
            fig, _ = viz.parameter_heatmap(
                heat_sweep,
                x="shrinkage_label",
                y="estimator",
                metric="net_sharpe",
                x_label="Poids du rétrécissement",
                y_label="Fenêtres d'estimation",
                metric_label="Ratio de Sharpe net",
                title="Ratio de Sharpe net au niveau du titre selon l'estimateur de bêta",
            )
            figure_specs.append(
                (
                    _save_figure(fig, "parameter_heatmap").stem,
                    "robustness",
                    "Ratio de Sharpe net des trente-six réglages de l'estimateur.",
                )
            )

            heat_financement = financing_frame.copy()
            # Les étiquettes sont complétées par des zéros : la carte de chaleur
            # trie ses colonnes en TEXTE, et « 25 » se placerait après « 200 ».
            heat_financement["spread_label"] = heat_financement["spread_bps"].map(lambda v: f"{v:03.0f}")
            # « net » et « gross » sont les clés du code. Le lecteur d'une figure
            # française lit « base nette » et « base brute ».
            heat_financement["ligne"] = (
                heat_financement["series"]
                + ", "
                + heat_financement["basis"].map({"net": "base nette", "gross": "base brute"})
            )
            fig, _ = viz.parameter_heatmap(
                heat_financement,
                x="spread_label",
                y="ligne",
                metric="net_sharpe",
                x_label="Écart de financement annuel, en points de base",
                y_label="Série et base de facturation",
                metric_label="Ratio de Sharpe net",
                title="Ratio de Sharpe net selon le prix du levier",
            )
            figure_specs.append(
                (
                    _save_figure(fig, "financing_heatmap").stem,
                    "costs",
                    "Ratio de Sharpe net de la série de référence selon l'écart de financement.",
                )
            )

            fig, _ = viz.cost_sensitivity(
                list(analyse_cout.table["multiplier"]),
                list(analyse_cout.table["metric"]),
                threshold=0.0,
                metric_label="Ratio de Sharpe net de la série de référence",
                title="Sensibilité au multiple de coût de rotation",
            )
            figure_specs.append(
                (
                    _save_figure(fig, "cost_sensitivity").stem,
                    "costs",
                    "Ratio de Sharpe net en fonction du multiple appliqué aux dix points de base.",
                )
            )

            fig, _ = viz.subperiod_bars(
                sous_periodes,
                metric_column="sharpe",
                error_column="sharpe_se_lo",
                metric_label="Ratio de Sharpe annualisé",
                title="Ratio de Sharpe de la série de référence par sous-période",
            )
            figure_specs.append(
                (
                    _save_figure(fig, "subperiod_bars").stem,
                    "robustness",
                    "Ratio de Sharpe annualisé et son intervalle à 95 pour cent.",
                )
            )

            ordre = list(country_frame["country"])
            pays_long = pd.concat(
                [
                    country_frame.assign(
                        window="Avant avril 2012", value=country_frame["test_sharpe_before"]
                    ),
                    country_frame.assign(
                        window="Depuis avril 2012", value=country_frame["test_sharpe_after"]
                    ),
                ]
            ).dropna(subset=["value"])
            pays_long["country"] = pd.Categorical(pays_long["country"], categories=ordre, ordered=True)
            fig, _ = viz.parameter_heatmap(
                pays_long.sort_values("country"),
                x="country",
                y="window",
                metric="value",
                x_label="Marché",
                y_label="Fenêtre",
                metric_label="Ratio de Sharpe annualisé",
                title="Ratio de Sharpe du facteur publié par marché, avant et après l'article",
                figsize=(14.0, 4.5),
            )
            figure_specs.append(
                (
                    _save_figure(fig, "country_heatmap").stem,
                    "replication",
                    "Ratio de Sharpe du facteur d'AQR par marché, de part et d'autre d'avril 2012.",
                )
            )

            correlation_source = (
                pd.DataFrame({"BAB publié, USA": usa})
                .join(base_b1.returns.rename("Nos déciles, rangs"), how="inner")
                .join(base_b2.returns.rename("Nos titres, rangs"), how="inner")
                .join(
                    resultats_b2[("rank", 1.0)].returns.rename("Nos titres, sans rétrécissement"),
                    how="inner",
                )
                .join(mkt_excess.rename("Marché"), how="inner")
                .dropna()
            )
            fig, _ = viz.correlation_heatmap(
                correlation_source, title="Corrélations mensuelles des facteurs et du marché"
            )
            figure_specs.append(
                (
                    _save_figure(fig, "correlation_heatmap").stem,
                    "factor_attribution",
                    "Corrélations de Pearson sur les mois communs aux cinq séries.",
                )
            )

            fig, _ = viz.rolling_metric(
                base_b1.returns,
                metric="sharpe",
                window=120,
                frequency=MONTHLY,
                title="Ratio de Sharpe glissant sur dix ans de notre BAB sur les déciles",
            )
            figure_specs.append(
                (
                    _save_figure(fig, "rolling_sharpe").stem,
                    "out_of_sample",
                    "Ratio de Sharpe annualisé sur fenêtre glissante de 120 mois.",
                )
            )

            fig, _ = viz.return_histogram(
                usa, title="Distribution mensuelle du facteur BAB publié, colonne USA"
            )
            figure_specs.append(
                (
                    _save_figure(fig, "return_histogram").stem,
                    "statistical_tests",
                    "Histogramme des rendements mensuels et loi normale de même moyenne.",
                )
            )

        # ------------------------------------------------------------------ #
        # 11. Le verdict
        # ------------------------------------------------------------------ #
        tolerance = float(params["verdict"]["replication_tolerance"])
        source_iii = "Frazzini et Pedersen (2013), tableau III, actions américaines"
        resume_is = _summary(in_sample, mkt_excess)
        checks = (
            ReplicationCheck(
                quantity="Rendement excédentaire mensuel, %",
                published=float(params["paper_us_monthly_excess_pct"]),
                ours=resume_is["monthly_pct"],
                tolerance=tolerance,
                source=source_iii,
            ),
            ReplicationCheck(
                quantity="Statistique t du rendement excédentaire",
                published=float(params["paper_us_tstat"]),
                ours=resume_is["mean_tstat"],
                tolerance=tolerance,
                source=source_iii,
            ),
            ReplicationCheck(
                quantity="Volatilité annualisée, %",
                published=float(params["paper_us_volatility_pct"]),
                ours=resume_is["annual_vol_pct"],
                tolerance=tolerance,
                source=source_iii,
            ),
            ReplicationCheck(
                quantity="Ratio de Sharpe annualisé",
                published=float(params["paper_us_sharpe"]),
                ours=resume_is["sharpe"],
                tolerance=tolerance,
                source=source_iii,
            ),
            ReplicationCheck(
                quantity="Alpha du modèle à trois facteurs, %/mois",
                published=float(params["paper_us_alpha_3f_pct"]),
                ours=float(
                    attribution.loc[
                        attribution["model"] == "trois facteurs, échantillon de l'article",
                        "alpha_monthly_pct",
                    ].iloc[0]
                ),
                tolerance=tolerance,
                source=source_iii,
            ),
            ReplicationCheck(
                quantity="Alpha du modèle à quatre facteurs, %/mois",
                published=float(params["paper_us_alpha_4f_pct"]),
                ours=float(
                    attribution.loc[
                        attribution["model"] == "quatre facteurs, échantillon de l'article",
                        "alpha_monthly_pct",
                    ].iloc[0]
                ),
                tolerance=tolerance,
                source=source_iii,
            ),
            ReplicationCheck(
                quantity="Part de marchés au ratio de Sharpe positif",
                published=float(params["paper_positive_country_share"]),
                ours=part_positive,
                tolerance=tolerance,
                source="Frazzini et Pedersen (2013), tableau V",
            ),
            ReplicationCheck(
                quantity="Levier de la jambe longue, dollars",
                published=float(params["paper_long_leverage"]),
                ours=float(base_b2.leverage_low.mean()),
                tolerance=tolerance,
                source="Frazzini et Pedersen (2013), page 19",
                note="Notre jambe B2, titres du S&P 500, pondération par les rangs.",
            ),
            ReplicationCheck(
                quantity="Bêta réalisé de notre facteur reconstruit",
                published=float(params["paper_us_ex_ante_beta"]),
                ours=float(ols_beta(base_b1.returns, mkt_excess.reindex(base_b1.returns.index))),
                tolerance=float(params["realized_beta_tolerance"]),
                tolerance_kind="absolute",
                source="Frazzini et Pedersen (2013), tableau III, bêta ex ante 0,00",
                note="Le bêta ex ante vaut zéro par construction, le bêta réalisé est mesuré.",
            ),
        )
        replication_frame = replication_table(checks)
        _write_table(replication_frame, "replication_checks")

        multiple_survecu = (
            analyse_cout.breakeven_multiplier
            if analyse_cout.breakeven_multiplier is not None
            else (
                float(analyse_cout.table["multiplier"].max())
                if analyse_cout.status == "survives_all"
                else 0.0
            )
        )
        criteria = VerdictCriteria(**params["verdict"])
        correlation_incumbent = float(base_net.corr(mkt_excess.reindex(base_net.index)))
        evidence = VerdictEvidence(
            hypothesis_supported=bool(resume_is["monthly_pct"] > 0.0),
            replication_checks=checks,
            oos_sharpe=oos_sharpe,
            tstat_after_multiplicity=float(t_ajuste),
            deflated_sharpe=float(deflated),
            pbo=float(pbo_result.pbo),
            positive_subperiod_share=part_sous_periodes,
            surviving_cost_multiple=float(multiple_survecu),
            portfolio_correlation=correlation_incumbent,
            notes=(
                "La série de référence est notre reconstruction sur les déciles triés par bêta "
                "de Kenneth French, pondérée par les rangs, nette de dix points de base."
            ),
        )
        verdict, reasons = decide_verdict(evidence, criteria)
        run.set_verdict(verdict)

        metric_values = {
            "rendement_mensuel_publie_pct": resume_is["monthly_pct"],
            "sharpe_publie_in_sample": resume_is["sharpe"],
            "sharpe_publie_hors_echantillon": float(
                windows_frame.loc[
                    windows_frame["window"] == "Après l'article, depuis avril 2012", "sharpe"
                ].iloc[0]
            ),
            "part_de_marches_positifs": part_positive,
            "sharpe_deciles_reference": sharpe_ratio(base_b1.returns, frequency=MONTHLY),
            "sharpe_titres_reference": sharpe_ratio(base_b2.returns, frequency=MONTHLY),
            "sharpe_titres_sans_retrecissement": sharpe_ratio(
                resultats_b2[("rank", 1.0)].returns, frequency=MONTHLY
            ),
            "beta_realise_reference": float(
                ols_beta(base_b1.returns, mkt_excess.reindex(base_b1.returns.index))
            ),
            "sharpe_hors_echantillon_net": oos_sharpe,
            "ecart_de_financement_qui_annule_le_rendement_bps": float(
                _breakeven_financing(base_b1, str(params["financing_basis"])) * 10_000.0
            ),
            "ecart_de_financement_qui_annule_lalpha_bps": float(
                breakeven_frame.loc[
                    (breakeven_frame["series"] == "déciles, rangs, capitalisation")
                    & (breakeven_frame["basis"] == str(params["financing_basis"])),
                    "alpha_zero_spread_bps",
                ].iloc[0]
            ),
            "ecart_de_financement_qui_annule_lalpha_net_bps": float(
                breakeven_frame.loc[
                    (breakeven_frame["series"] == "déciles, rangs, capitalisation")
                    & (breakeven_frame["basis"] == str(params["financing_basis"])),
                    "alpha_zero_spread_net_bps",
                ].iloc[0]
            ),
            "rotation_annualisee": float(annualized_turnover(_turnover(base_b1), frequency=MONTHLY)),
            "cout_de_rentabilite_bps": float(
                breakeven_cost_bps(base_b1.returns.iloc[1:], _turnover(base_b1), frequency=MONTHLY)
            ),
            "probabilite_de_surapprentissage": float(pbo_result.pbo),
            "sharpe_degonfle": float(deflated),
            "t_apres_correction": float(t_ajuste),
            "part_de_sous_periodes_positives": part_sous_periodes,
            "multiple_de_couts_survecu": float(multiple_survecu),
            "correlation_avec_le_marche": correlation_incumbent,
            "cpcv_sharpe_moyen": float(distribution.summary["mean"]),
            "cpcv_part_de_chemins_negatifs": float(distribution.negative_share),
            "ecart_identite_novy_marx": ecart_identite,
        }
        labels = {
            "rendement_mensuel_publie_pct": MetricLabel(SampleTag.IN_SAMPLE, CostBasis.GROSS),
            "sharpe_publie_in_sample": MetricLabel(SampleTag.IN_SAMPLE, CostBasis.GROSS),
            "sharpe_publie_hors_echantillon": MetricLabel(SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
            "part_de_marches_positifs": MetricLabel(SampleTag.IN_SAMPLE, CostBasis.GROSS),
            "sharpe_deciles_reference": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "sharpe_titres_reference": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "sharpe_titres_sans_retrecissement": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "beta_realise_reference": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "sharpe_hors_echantillon_net": MetricLabel(SampleTag.OUT_OF_SAMPLE, CostBasis.NET),
            "ecart_de_financement_qui_annule_le_rendement_bps": MetricLabel(
                SampleTag.VALIDATION, CostBasis.GROSS
            ),
            "ecart_de_financement_qui_annule_lalpha_bps": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "ecart_de_financement_qui_annule_lalpha_net_bps": MetricLabel(
                SampleTag.VALIDATION, CostBasis.NET
            ),
            "rotation_annualisee": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "cout_de_rentabilite_bps": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "probabilite_de_surapprentissage": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "sharpe_degonfle": MetricLabel(SampleTag.OUT_OF_SAMPLE, CostBasis.NET),
            "t_apres_correction": MetricLabel(SampleTag.OUT_OF_SAMPLE, CostBasis.NET),
            "part_de_sous_periodes_positives": MetricLabel(SampleTag.VALIDATION, CostBasis.NET),
            "multiple_de_couts_survecu": MetricLabel(SampleTag.VALIDATION, CostBasis.NET),
            "correlation_avec_le_marche": MetricLabel(SampleTag.VALIDATION, CostBasis.NET),
            "cpcv_sharpe_moyen": MetricLabel(SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
            "cpcv_part_de_chemins_negatifs": MetricLabel(SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
            "ecart_identite_novy_marx": MetricLabel(SampleTag.IN_SAMPLE, CostBasis.GROSS),
        }
        metrics = metrics_table(metric_values, labels)
        _write_table(metrics, "metrics")
        for nom, valeur in metric_values.items():
            run.log_metric(nom, valeur, sample=labels[nom].sample)

        payload = {
            "study": "005_betting_against_beta",
            "experiment_id": run.record.experiment_id,
            "seed": config.seed,
            "verdict": verdict.value,
            "reasons": reasons,
            "n_trials": n_trials,
            "trials_by_family": {famille: counter.n_trials(famille) for famille in counter.families()},
            "metrics": metric_values,
            "metric_samples": {nom: label.sample.value for nom, label in labels.items()},
            "cost_basis": {nom: label.cost_basis.value for nom, label in labels.items()},
            "samples": {
                "published_full": [str(usa.index[0].date()), str(usa.index[-1].date())],
                "published_in_sample": [
                    str(in_sample.index[0].date()),
                    str(in_sample.index[-1].date()),
                ],
                "deciles_window": [
                    str(base_b1.returns.index[0].date()),
                    str(base_b1.returns.index[-1].date()),
                ],
                "stocks_window": [
                    str(base_b2.returns.index[0].date()),
                    str(base_b2.returns.index[-1].date()),
                ],
                "holdout_window": [str(holdout.index[0].date()), str(holdout.index[-1].date())],
            },
            "cost_assumptions_bps": {
                "spread_bps": config.costs.spread_bps,
                "financing_spread_bps_annual": config.costs.financing_spread_bps_annual,
            },
            "n_countries": len(pays),
        }
        (RESULTS / "metrics.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        report_tables = [
            ReportTable("legA_windows", "replication", windows_frame, "Le facteur publié par fenêtre."),
            ReportTable("legA_countries", "replication", country_frame, "Le facteur publié par marché."),
            ReportTable("legA_attribution", "factor_attribution", attribution, "Alphas et chargements."),
            ReportTable("replication_checks", "replication", replication_frame, "Les contrôles chiffrés."),
            ReportTable(
                "legB_weighting", "performance", weighting_frame, "Les vingt-quatre versions des déciles."
            ),
            ReportTable("legB_stocks", "performance", stocks_frame, "Les huit versions au niveau du titre."),
            ReportTable("legB_leverage", "implementation", leverage_frame, "Le levier de chaque jambe."),
            ReportTable("nmv_hedge", "robustness", pd.DataFrame(couvertures), "Les trois couvertures."),
            ReportTable(
                "nmv_beta_artifact", "statistical_tests", artefact_frame, "Le bêta contre la volatilité."
            ),
            ReportTable("financing", "costs", financing_frame, "Le prix du levier."),
            ReportTable("financing_breakeven", "costs", breakeven_frame, "L'écart qui annule l'alpha."),
            ReportTable("costs", "costs", pd.DataFrame(cout_rows), "Rotation et coût de rentabilité."),
            ReportTable("parameter_sweep", "robustness", sweep_frame, "Trente-six réglages."),
            ReportTable("subperiods", "robustness", sous_periodes, "Les sous-périodes."),
            ReportTable("cpcv_distribution", "out_of_sample", cpcv_frame, "Validation croisée purgée."),
            ReportTable("multiple_testing", "statistical_tests", multiple_frame, "Correction de Holm."),
            ReportTable("trials", "statistical_tests", trials_frame, "Le compte des essais."),
        ]
        report_figures = [
            ReportFigure(nom, section, FIGURES / f"{nom}.png", legende)
            for nom, section, legende in figure_specs
        ]
        report = StudyReport(
            study_name="005_betting_against_beta",
            experiment_id=run.record.experiment_id,
            hypothesis=config.hypothesis,
            paper=config.paper or "",
            criteria=criteria,
            evidence=evidence,
            sections=_sections(metric_values, resume_is, weighting_frame),
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
                name="betting_against_beta",
                family="low_risk",
                paper=config.paper,
                asset_classes=[AssetClass.EQUITY],
                horizon="formation mensuelle sur bêta ex ante, détention un mois",
                economic_rationale=["contrainte institutionnelle", "friction"],
                inputs=[
                    "rendements quotidiens des membres du S&P 500, Yahoo",
                    "portefeuilles mensuels triés par bêta, Kenneth French",
                    "facteur BAB mensuel publié par AQR, série des auteurs",
                    "trois facteurs, momentum et taux sans risque, Kenneth French",
                ],
                known_risks=[
                    "Le bêta ex ante sert de diviseur, donc son bruit devient du levier.",
                    "La pondération par les rangs ignore la capitalisation.",
                    "Le levier de la jambe longue dépasse un dollar trente en moyenne.",
                    "L'univers de titres est celui d'aujourd'hui, donc il porte un biais de survie.",
                ],
                validation_status=verdict,
                verdict_experiment_id=run.record.experiment_id,
                created=pd.Timestamp.today().date(),
                last_modified=pd.Timestamp.today().date(),
                notes=(
                    "Étude 005. Le mécanisme invoqué est une contrainte de levier : qui ne peut "
                    "pas emprunter achète du bêta élevé, en fait monter le prix, et baisse son "
                    "rendement futur. La friction retenue est le prix du levier, mesurée par "
                    "l'écart de financement qui annule le rendement. Le verdict est déduit par "
                    "quantlab.reporting.study.decide_verdict."
                ),
            ),
            overwrite=True,
        )
        LOG.info("étude terminée", extra={"verdict": verdict.value, "n_trials": n_trials})


def _sections(
    metric_values: Mapping[str, float],
    resume_is: Mapping[str, float],
    weighting_frame: pd.DataFrame,
) -> dict[str, str]:
    """Rend la prose des quinze sections du rapport HTML."""
    return {
        "hypothesis": (
            "Un portefeuille long sur bêta faible et court sur bêta élevé, chaque jambe mise à "
            "l'échelle par l'inverse de son bêta, rapporte-t-il un rendement positif de bêta nul ?"
        ),
        "paper": (
            "Frazzini et Pedersen (2014), Betting against beta, Journal of Financial Economics "
            "111(1). Les chiffres cibles viennent de la version de travail du 2013-05-10."
        ),
        "methodology": (
            "Le bêta ex ante compose une corrélation à cinq ans sur rendements recouvrants de "
            "trois jours et deux volatilités à un an, puis se rétrécit vers un. Les titres sont "
            "classés, pondérés par les rangs, et chaque jambe est divisée par son bêta."
        ),
        "data": (
            "Le facteur publié vient du classeur d'AQR. Notre construction emploie les "
            "portefeuilles triés par bêta de Kenneth French et les membres actuels du S&P 500."
        ),
        "implementation": (
            "La stratégie vit dans quantlab.strategies.betting_against_beta. Le décalage d'un "
            "mois entre formation et détention se fait en un seul endroit."
        ),
        "assumptions": (
            "Le levier s'obtient au taux sans risque dans le cas de référence, hypothèse de "
            "l'article. Son prix réel est balayé séparément."
        ),
        "replication": (
            f"Le rendement excédentaire mensuel du facteur publié ressort à "
            f"{resume_is['monthly_pct']:.4f} pour cent contre 0,70 publié, et son ratio de "
            f"Sharpe à {resume_is['sharpe']:.3f} contre 0,78."
        ),
        "performance": (
            "Toutes les versions portent leur échantillon et leur base de coût dans les tableaux."
        ),
        "costs": (
            f"La rotation annualisée vaut {metric_values['rotation_annualisee']:.2f} et le coût "
            f"qui annule le rendement brut vaut {metric_values['cout_de_rentabilite_bps']:.0f} "
            "points de base."
        ),
        "robustness": (
            "Trente-six réglages de l'estimateur de bêta sont balayés, puis la fenêtre "
            "recouvrante, le délai d'exécution et les sous-périodes."
        ),
        "out_of_sample": (
            f"Le ratio de Sharpe hors échantillon de la série de référence vaut "
            f"{metric_values['sharpe_hors_echantillon_net']:.3f}, net de dix points de base."
        ),
        "statistical_tests": (
            f"La probabilité de surapprentissage vaut "
            f"{metric_values['probabilite_de_surapprentissage']:.3f} et le ratio de Sharpe "
            f"dégonflé {metric_values['sharpe_degonfle']:.3f}."
        ),
        "factor_attribution": (
            "Le facteur publié est régressé sur un, trois, quatre et six facteurs de Kenneth "
            "French, dans l'échantillon de l'article puis après lui."
        ),
        "limitations": (
            "L'univers de titres est celui d'aujourd'hui, donc il porte un biais de survie. Les "
            "portefeuilles triés par bêta ne sont publiés qu'en fréquence mensuelle."
        ),
        "verdict": (
            f"Le meilleur écart de pondération mesuré vaut "
            f"{float(weighting_frame['sharpe'].max()):.3f} de ratio de Sharpe, et le verdict est "
            "déduit par decide_verdict depuis les seuils écrits avant les résultats."
        ),
    }


if __name__ == "__main__":
    main()

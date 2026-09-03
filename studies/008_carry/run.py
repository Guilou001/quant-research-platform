"""Le point d'entrée de l'étude 008, le portage.

Ce fichier orchestre et n'implémente rien de réutilisable. La stratégie vit dans
:mod:`quantlab.strategies.carry`, les métriques dans :mod:`quantlab.analytics`,
les contrôles dans :mod:`quantlab.validation`.

Lancement :

.. code-block:: bash

    export QUANTLAB_USER_AGENT="votre nom votre courriel"
    uv run python studies/008_carry/run.py
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from quantlab.analytics.drawdown import drawdown_table, max_drawdown
from quantlab.analytics.ratios import sharpe_ratio, sharpe_tstat
from quantlab.analytics.risk import expected_shortfall, kurtosis, skewness, value_at_risk
from quantlab.analytics.turnover import annualized_turnover, holding_period, turnover_series
from quantlab.analytics.visualization import figures as viz
from quantlab.core.config import ExperimentConfig, load_config
from quantlab.core.determinism import make_generator
from quantlab.core.errors import ConfigError
from quantlab.core.logging import get_logger, stage
from quantlab.core.types import AssetClass, CostBasis, Frequency, SampleTag
from quantlab.data.providers.fred import FredProvider
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
from quantlab.strategies.carry import (
    bond_slope_carry,
    carry_portfolio,
    carry_signal,
    currency_excess_return,
    dollar_decomposition,
    momentum_signal,
    month_end_sample,
    panel_carry_regression,
    smoothed_signal,
    to_usd_per_unit,
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

LOG = get_logger("quantlab.studies.008")
STUDY_DIR = Path(__file__).resolve().parent
RESULTS = STUDY_DIR / "results"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"

MONTHLY = Frequency.MONTHLY

#: Le nom lisible de chaque devise, employé dans les tableaux publiés.
CURRENCY_LABELS: Mapping[str, str] = {
    "AUD": "Dollar australien",
    "CAD": "Dollar canadien",
    "CHF": "Franc suisse",
    "DKK": "Couronne danoise",
    "EUR": "Euro",
    "GBP": "Livre sterling",
    "JPY": "Yen",
    "NOK": "Couronne norvégienne",
    "NZD": "Dollar néo-zélandais",
    "SEK": "Couronne suédoise",
    "USD": "Dollar des États-Unis",
}

#: Le nom lisible de chaque schéma de pondération et de chaque variante de
#: signal. Les clés internes ne sortent pas des fichiers, règle du portefeuille.
SCHEME_LABELS: Mapping[str, str] = {
    "rank": "Rang",
    "sign": "Calendrier",
    "tercile": "Tiers extrêmes",
}

#: Le nom lisible de chaque variante de signal de l'article.
VARIANT_LABELS: Mapping[str, str] = {
    "carry": "Portage brut",
    "carry1_12": "Moyenne des 12 derniers mois",
    "carry2_13": "Moyenne des mois 2 à 13",
}

#: Les trois classes d'actifs de l'article qui ne sont pas reproductibles, avec
#: ce qui a été cherché et où. Recherche menée le 2026-09-02.
UNREPRODUCIBLE: tuple[dict[str, str], ...] = (
    {
        "asset_class": "Matières premières",
        "what_the_paper_needs": (
            "Le prix au comptant synthétique et le prix à terme de 24 contrats, mois par mois, "
            "de janvier 1980 à septembre 2012, plus les conventions de report du Goldman Sachs "
            "Commodity Index"
        ),
        "searched": (
            "turtletrader.com (séries continues ajustées), base des prix des matières premières "
            "de la Banque mondiale (Pink Sheet, prix au comptant mensuels seuls), Cboe "
            "(données historiques limitées à ses propres contrats), Nasdaq Data Link (base "
            "CHRIS non accessible depuis la reprise de Quandl)"
        ),
        "verdict": "non trouvé au 2026-09-02",
        "why": (
            "Aucune source gratuite ne publie la structure par terme, c'est-à-dire le prix de "
            "plusieurs échéances à la même date. Une série continue ajustée écrase justement "
            "l'écart entre échéances qui EST le portage."
        ),
    },
    {
        "asset_class": "Indices actions",
        "what_the_paper_needs": (
            "Le dividende attendu sur un mois et le taux sans risque local de 13 marchés, ou le "
            "prix du contrat à terme le plus proche interpolé à un mois, de mars 1988 à "
            "septembre 2012"
        ),
        "searched": (
            "Yahoo Finance (indices de dividendes RÉALISÉS du seul S&P 500, ^DVS et ^DIVD), "
            "CME Group (contrats sur dividendes, cotations courantes seulement), OptionMetrics "
            "(dividende implicite, payant)"
        ),
        "verdict": "non trouvé au 2026-09-02",
        "why": (
            "Le portage actions exige le dividende ATTENDU, pas le dividende versé. Les séries "
            "gratuites publient le second, et sur un seul marché."
        ),
    },
    {
        "asset_class": "Options d'achat et de vente sur indices",
        "what_the_paper_needs": (
            "La surface de volatilité implicite de 10 indices américains, par delta et par "
            "échéance, de janvier 1996 à décembre 2011, avec volume et position ouverte"
        ),
        "searched": "OptionMetrics IvyDB, la source nommée par l'article",
        "verdict": "non trouvé au 2026-09-02",
        "why": (
            "OptionMetrics est vendu sous licence universitaire ou commerciale. Aucun "
            "équivalent gratuit ne remonte à 1996 avec les deux groupes de delta exigés."
        ),
    },
)


def _write_table(frame: pd.DataFrame, name: str) -> Path:
    """Écrit un tableau sous ``results/tables`` et rend son chemin."""
    TABLES.mkdir(parents=True, exist_ok=True)
    path = TABLES / f"{name}.csv"
    frame.to_csv(path, index=False)
    LOG.info("tableau écrit", extra={"name": name, "n_rows": len(frame)})
    return path


def _save_figure(fig: Any, name: str) -> Path:
    """Écrit une figure en PNG et en PDF, et rend le chemin du PNG."""
    FIGURES.mkdir(parents=True, exist_ok=True)
    written = viz.save_figure(fig, FIGURES / name, vector=True)
    return next(p for p in written if p.suffix == ".png")


#: Les mois de taux reportés depuis le mois précédent, journalisés et publiés.
RATE_GAPS: list[dict[str, Any]] = []


def _monthly_rate(provider: FredProvider, series_id: str, max_gap_fill_months: int = 0) -> pd.Series:
    """Rend un taux FRED mensuel en décimales, daté à la fin du mois.

    Les séries de l'OCDE portent la date du PREMIER jour du mois qu'elles
    décrivent. Le taux du mois est une moyenne des jours de ce mois, donc il est
    connu à sa fin, et c'est cette date que porte la série rendue.

    Un trou d'au plus ``max_gap_fill_months`` mois à l'intérieur de la série
    est comblé par le dernier taux connu, ce qui n'emploie que le passé. Chaque
    mois comblé est journalisé et ajouté à :data:`RATE_GAPS`. Mesuré le
    2026-09-02 : le taux interbancaire américain manque pour 2020-04, et sans
    ce report les onze portages du mois sont manquants.
    """
    frame = provider.fetch(series_id)
    serie = frame.iloc[:, 0].dropna() / 100.0
    index = pd.DatetimeIndex(serie.index.to_period("M").to_timestamp(how="end").normalize(), name="date")
    monthly = pd.Series(serie.to_numpy(), index=index, name=series_id)
    if max_gap_fill_months <= 0 or len(monthly) < 2:
        return monthly
    full = pd.date_range(monthly.index.min(), monthly.index.max(), freq="ME")
    complete = monthly.reindex(full)
    filled = complete.ffill(limit=int(max_gap_fill_months))
    for date in complete.index[complete.isna() & filled.notna()]:
        RATE_GAPS.append(
            {"series": series_id, "month": str(date.date()), "value_used": float(filled.loc[date])}
        )
        LOG.warning(
            "taux reporté sur un mois manquant", extra={"series": series_id, "month": str(date.date())}
        )
    return filled.dropna().rename(series_id)


def _turnover(raw_weights: pd.DataFrame, excess: pd.DataFrame, execution_lag: int) -> pd.Series:
    """Rend la rotation payée par le rendement de chaque mois, en somme entière.

    La rotation se mesure à la date de FORMATION des poids, contre les poids
    dérivés du mois écoulé. Elle est ensuite décalée du délai d'exécution, pour
    que le coût pèse sur le mois qu'il finance et non sur celui qui l'a décidé.
    """
    brute = turnover_series(raw_weights, _drift_returns(excess, raw_weights.index), convention="full_sum")
    return brute.shift(execution_lag).rename("turnover")


def _cost_from_turnover(rotation: pd.Series, rate_bps: float) -> pd.Series:
    """Rend le coût mensuel d'une rotation, au taux unitaire demandé.

    Le taux est le DEMI-écart acheteur-vendeur, celui que
    :class:`quantlab.execution.costs.LinearCostModel` attend, et la rotation est
    en somme entière. Le produit des deux est donc le coût de la période.
    """
    model = LinearCostModel(spread_bps=rate_bps)
    return (rotation * model.rate_bps / 1e4).rename("cost")


def _drift_returns(excess: pd.DataFrame, index: pd.Index) -> pd.DataFrame:
    """Rend les rendements de dérive, les devises non cotées mises à zéro.

    La rotation se mesure contre les poids dérivés, ce qui exige un rendement
    pour chaque colonne. Une devise non cotée porte un poids nul, donc un
    rendement nul la laisse à zéro et ne change aucune rotation. Le comblement
    est explicite ici plutôt que muet dans la fonction de rotation.
    """
    return excess.reindex(index).fillna(0.0)


def _describe(series: pd.Series, label: str, alpha: float) -> dict[str, Any]:
    """Rend la ligne descriptive d'une série de rendements mensuels."""
    return {
        "series": label,
        "n_months": len(series),
        "start": str(series.index[0].date()),
        "end": str(series.index[-1].date()),
        "annual_return_pct": float(series.mean() * 12.0 * 100.0),
        "annual_vol_pct": float(series.std(ddof=1) * math.sqrt(12.0) * 100.0),
        "sharpe": sharpe_ratio(series, frequency=MONTHLY),
        "skewness": skewness(series),
        "excess_kurtosis": kurtosis(series),
        "var_pct": value_at_risk(series, alpha) * 100.0,
        "expected_shortfall_pct": expected_shortfall(series, alpha) * 100.0,
        "max_drawdown_pct": max_drawdown(series) * 100.0,
        "worst_month_pct": float(series.min() * 100.0),
    }


def _pvalue(tstat: float) -> float:
    """Rend la valeur p bilatérale d'une statistique t, loi normale."""
    return 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(tstat) / math.sqrt(2.0))))


def _spliced_rates(
    reference: Mapping[str, pd.Series], alternates: Mapping[str, pd.Series]
) -> dict[str, pd.Series]:
    """Rallonge un taux vers le passé par une série de remplacement déclarée."""
    out = dict(reference)
    for code, autre in alternates.items():
        base = reference[code]
        debut = base.index[0]
        avant = autre.loc[autre.index < debut]
        out[code] = pd.concat([avant, base]).sort_index()
    return out


def _build_panel(
    rates: Mapping[str, pd.Series],
    spots: Mapping[str, pd.Series],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rend le portage et le rendement en excès de chaque devise, contre le dollar.

    Le portage d'une devise n'est retenu que si son change est COTÉ ce mois-là.
    Sans ce masque, une monnaie dont on connaît le taux mais pas le prix
    recevrait un poids qu'aucun investisseur n'aurait pu prendre.
    """
    base = rates["USD"]
    portage: dict[str, pd.Series] = {}
    rendement: dict[str, pd.Series] = {}
    for code, spot in spots.items():
        signal = carry_signal(rates[code], base)
        negociable = spot.reindex(signal.index).notna() & signal.notna()
        portage[code] = signal.where(negociable)
        rendement[code] = currency_excess_return(spot, rates[code], base)
    portage["USD"] = pd.Series(0.0, index=base.index)
    rendement["USD"] = pd.Series(0.0, index=base.index)
    signal_frame = pd.DataFrame(portage).sort_index().loc[start:end]
    return_frame = pd.DataFrame(rendement).sort_index().reindex(signal_frame.index)
    return signal_frame, return_frame


def _sections(metric_values: Mapping[str, float], n_currencies: int) -> dict[str, str]:
    """Rend la prose des quinze sections du rapport."""
    return {
        "hypothesis": (
            "Le portage, l'écart de taux entre deux devises, prédit-il le rendement futur du "
            "change, et le portefeuille trié par portage paie-t-il son ratio de Sharpe par une "
            "asymétrie négative ?"
        ),
        "paper": (
            "Koijen, Moskowitz, Pedersen et Vrugt (2018), Carry, Journal of Financial Economics "
            "127(2). Les chiffres cibles viennent du manuscrit accepté déposé au CBS Research "
            "Portal."
        ),
        "methodology": (
            "Le portage de chaque devise vaut l'écart de taux court, équation (7). Les devises "
            "sont classées par portage, le portefeuille est long les rangs hauts et court les "
            "rangs bas, à somme nulle et deux dollars d'exposition brute."
        ),
        "data": (
            f"Dix taux de change quotidiens et {n_currencies} taux interbancaires à trois mois, "
            "tous chez FRED. Trois des quatre classes d'actifs de l'article ne sont pas "
            "reproductibles sur données gratuites, et le tableau des sources le déclare."
        ),
        "implementation": (
            "La stratégie vit dans quantlab.strategies.carry. Le sens de cotation de chaque "
            "série est déclaré dans config.yaml, et un test le confronte à la règle de nommage "
            "de FRED."
        ),
        "assumptions": (
            "La parité couverte des taux tient, donc l'écart de taux vaut les points de report. "
            "Le taux à trois mois sert de taux à un mois. Le collatéral rapporte le taux local."
        ),
        "replication": (
            f"Sur la fenêtre de l'article, le ratio de Sharpe du portage de change vaut "
            f"{metric_values['sharpe_portage_fenetre_article']:.2f} contre 0,68 publié, et le "
            f"coefficient de panel vaut {metric_values['panel_c_fenetre_article']:.2f} contre "
            "1,09 publié."
        ),
        "performance": (
            "Tous les chiffres portent leur échantillon et leur base de coût dans le tableau ci-dessous."
        ),
        "costs": (
            f"La rotation annualisée vaut {metric_values['rotation_annualisee']:.2f} et le coût "
            f"qui annule le rendement brut vaut {metric_values['cout_de_rentabilite_bps']:.0f} "
            "points de base."
        ),
        "robustness": (
            "Le schéma de pondération, la variante de signal, le délai d'exécution et le taux "
            "employé sont balayés, et chaque cellule compte comme un essai."
        ),
        "out_of_sample": (
            f"Après septembre 2012, fin de l'échantillon de l'article, le ratio de Sharpe net "
            f"tombe à {metric_values['sharpe_hors_echantillon_net']:.2f}."
        ),
        "statistical_tests": (
            "Le ratio de Sharpe dégonflé, la probabilité de surapprentissage et la validation "
            "croisée combinatoire purgée sont rapportés dans les tableaux joints."
        ),
        "factor_attribution": (
            "Le portage est comparé à un momentum de change de même construction et à "
            "l'exposition passive équipondérée aux dix devises."
        ),
        "limitations": (
            "Trois classes d'actifs sur quatre manquent. Le portage obligataire est approché par "
            "la pente, ce qui omet la descente de courbe. L'univers est celui de dix monnaies "
            "développées, contre vingt monnaies dans l'article."
        ),
        "verdict": "Le verdict est déduit des seuils écrits dans config.yaml, sans arbitrage.",
    }


def main() -> None:
    """Mène l'étude de bout en bout et écrit tout ce qu'elle produit."""
    config = load_config(STUDY_DIR / "config.yaml", ExperimentConfig)
    params = config.params
    generator = make_generator(config.seed)
    counter = TrialCounter()
    # Le second registre ne porte QUE les essais dont la mesure est un ratio de
    # Sharpe. Les quatre spécifications de panel sont des essais, donc elles
    # comptent, mais leur mesure est une statistique t. Les mêler à des ratios
    # de Sharpe dans une variance multiplierait celle-ci par soixante-deux.
    sharpe_counter = TrialCounter()
    for repertoire in (RESULTS, TABLES, FIGURES):
        repertoire.mkdir(parents=True, exist_ok=True)

    start = pd.Timestamp(config.data.start)
    end = pd.Timestamp(config.data.end)
    paper_start = pd.Timestamp(params["paper_start"])
    paper_end = pd.Timestamp(params["paper_end"])
    alpha_var = float(params["var_alpha"])
    gross = float(params["gross_exposure"])
    min_assets = int(params["min_assets_per_month"])
    published = params["published"]

    n_positive_multipliers = len([m for m in params["cost_multipliers"] if float(m) > 0.0])
    expected_trials = (
        len(params["weighting_grid"]) * len(params["signal_variant_grid"])
        + len(params["cost_bps_grid"])
        + n_positive_multipliers
        + len(params["execution_delays"])
        + 4
        + 6
    )

    registry = ExperimentRegistry()
    manifests: list[dict[str, Any]] = []

    with registry.run(
        name="008_carry",
        hypothesis=config.hypothesis,
        config=config.model_dump(mode="json"),
        seed=config.seed,
        universe=list(config.data.universe),
        date_start=config.data.start,
        date_end=config.data.end,
        cost_basis=CostBasis.NET,
        cost_assumptions={"spread_bps": config.costs.spread_bps},
        n_trials=expected_trials,
    ) as run:
        experiment_id = run.record.experiment_id

        # ------------------------------------------------------------------ #
        # 1. Les données
        # ------------------------------------------------------------------ #
        with stage("chargement", experiment_id=experiment_id):
            provider = FredProvider()
            gap_fill = int(params.get("max_gap_fill_months", 0))
            rates = {
                code: _monthly_rate(provider, sid, gap_fill) for code, sid in params["rate_series"].items()
            }
            for sid in params["rate_series"].values():
                manifests.append(provider.manifest(series_id=sid).model_dump(mode="json"))
            spots: dict[str, pd.Series] = {}
            raw_spots: dict[str, pd.Series] = {}
            for code, bloc in params["spot_series"].items():
                quotidien = provider.fetch(str(bloc["series"])).iloc[:, 0]
                raw_spots[code] = quotidien
                spots[code] = month_end_sample(to_usd_per_unit(quotidien, str(bloc["quote"])))
            alternates = {
                code: _monthly_rate(provider, sid, gap_fill)
                for code, sid in params["extended_rate_series"].items()
            }
            bond_yields = {
                code: _monthly_rate(provider, sid, gap_fill)
                for code, sid in params["bond_yield_series"].items()
            }
            _write_table(
                pd.DataFrame(RATE_GAPS or [{"series": "aucune", "month": "", "value_used": float("nan")}]),
                "rate_gaps_filled",
            )

        signal, excess = _build_panel(rates, spots, start, end)
        n_currencies = len(signal.columns)

        source_rows: list[dict[str, Any]] = []
        for code, bloc in params["spot_series"].items():
            brut = raw_spots[code].dropna()
            source_rows.append(
                {
                    "currency": CURRENCY_LABELS[code],
                    "role": "change au comptant",
                    "fred_series": str(bloc["series"]),
                    "quote_convention": str(bloc["quote"]),
                    "start": str(brut.index[0].date()),
                    "end": str(brut.index[-1].date()),
                    "n_rows": len(brut),
                }
            )
        for code, sid in params["rate_series"].items():
            serie = rates[code]
            source_rows.append(
                {
                    "currency": CURRENCY_LABELS[code],
                    "role": "taux interbancaire à trois mois",
                    "fred_series": sid,
                    "quote_convention": "pourcentage annualisé",
                    "start": str(serie.index[0].date()),
                    "end": str(serie.index[-1].date()),
                    "n_rows": len(serie),
                }
            )
        _write_table(pd.DataFrame(source_rows), "data_sources")

        coverage_rows = []
        for code in signal.columns:
            colonne = signal[code].dropna()
            rendements = excess[code].dropna()
            coverage_rows.append(
                {
                    "currency": CURRENCY_LABELS[code],
                    "first_carry": str(colonne.index[0].date()),
                    "last_carry": str(colonne.index[-1].date()),
                    "n_carry_months": len(colonne),
                    "n_return_months": len(rendements),
                    "mean_carry_annual_pct": float(colonne.mean() * 12.0 * 100.0),
                    "mean_excess_return_annual_pct": float(rendements.mean() * 12.0 * 100.0),
                }
            )
        _write_table(pd.DataFrame(coverage_rows), "currency_coverage")
        _write_table(pd.DataFrame(list(UNREPRODUCIBLE)), "asset_classes_not_reproducible")

        # ------------------------------------------------------------------ #
        # 2. Le portefeuille de référence
        # ------------------------------------------------------------------ #
        with stage("portefeuille", experiment_id=experiment_id):
            reference = carry_portfolio(
                signal,
                excess,
                scheme=str(params["weighting"]),
                gross=gross,
                min_assets=min_assets,
                execution_lag=int(params["execution_lag"]),
            )
            carry_returns = reference.returns.dropna()
            weights = reference.weights.loc[carry_returns.index]
            missing_cells = int(
                ((weights.abs() > 1e-12) & excess.reindex(weights.index).isna()).to_numpy().sum()
            )
            traded_cells = int((weights.abs() > 1e-12).to_numpy().sum())

            passive = excess.drop(columns=["USD"]).mean(axis=1).reindex(carry_returns.index).dropna()
            momentum = momentum_signal(excess, lookback=int(params["momentum_lookback_months"]))
            momentum_result = carry_portfolio(
                momentum, excess, scheme="rank", gross=gross, min_assets=min_assets
            )
            momentum_returns = momentum_result.returns.dropna()
            momentum_sharpe = sharpe_ratio(momentum_returns, frequency=MONTHLY)
            counter = counter.record("comparateur", "momentum", momentum_sharpe)
            sharpe_counter = sharpe_counter.record("comparateur", "momentum", momentum_sharpe)

            paper_window = carry_returns.loc[paper_start:paper_end]
            holdout = carry_returns.loc[carry_returns.index > paper_end]

        # ------------------------------------------------------------------ #
        # 3. Le tableau 2, panneau A
        # ------------------------------------------------------------------ #
        with stage("replication", experiment_id=experiment_id):
            passive_paper = passive.loc[paper_start:paper_end]
            momentum_paper = momentum_returns.loc[paper_start:paper_end]
            table2_rows = [
                _describe(paper_window, "Portage de change, fenêtre de l'article", alpha_var),
                _describe(passive_paper, "Passif équipondéré, fenêtre de l'article", alpha_var),
                _describe(momentum_paper, "Momentum de change, fenêtre de l'article", alpha_var),
                _describe(carry_returns, "Portage de change, échantillon complet", alpha_var),
                _describe(passive, "Passif équipondéré, échantillon complet", alpha_var),
                _describe(momentum_returns, "Momentum de change, échantillon complet", alpha_var),
            ]
            table2 = pd.DataFrame(table2_rows)
            table2["published_sharpe"] = [
                published["currency_sharpe"],
                published["currency_passive_sharpe"],
                float("nan"),
                published["currency_sharpe"],
                published["currency_passive_sharpe"],
                float("nan"),
            ]
            _write_table(table2, "replication_table2")

            panel_rows: list[dict[str, Any]] = []
            panel_specs = (
                ("actif et date", True, True),
                ("actif seulement", True, False),
                ("date seulement", False, True),
                ("aucun", False, False),
            )
            panel_reference: Any = None
            for label, entity_fe, time_fe in panel_specs:
                fit = panel_carry_regression(
                    signal.loc[paper_start:paper_end],
                    excess.loc[paper_start:paper_end],
                    entity_fixed_effects=entity_fe,
                    time_fixed_effects=time_fe,
                )
                if entity_fe and time_fe:
                    panel_reference = fit
                panel_rows.append(
                    {
                        "fixed_effects": label,
                        "window": "fenêtre de l'article",
                        "coefficient": fit.coefficient,
                        "stderr": fit.stderr,
                        "tstat": fit.tstat,
                        "tstat_vs_one": fit.tstat_vs_one,
                        "n_observations": fit.n_observations,
                        "n_periods": fit.n_periods,
                        "r_squared": fit.r_squared,
                        "published_c": published["currency_panel_c"],
                        "published_t": published["currency_panel_t"],
                    }
                )
                counter = counter.record("panel", label, fit.tstat)
            panel_full = panel_carry_regression(signal, excess)
            panel_rows.append(
                {
                    "fixed_effects": "actif et date",
                    "window": "échantillon complet",
                    "coefficient": panel_full.coefficient,
                    "stderr": panel_full.stderr,
                    "tstat": panel_full.tstat,
                    "tstat_vs_one": panel_full.tstat_vs_one,
                    "n_observations": panel_full.n_observations,
                    "n_periods": panel_full.n_periods,
                    "r_squared": panel_full.r_squared,
                    "published_c": published["currency_panel_c"],
                    "published_t": published["currency_panel_t"],
                }
            )
            panel_holdout = panel_carry_regression(
                signal.loc[signal.index > paper_end], excess.loc[excess.index > paper_end]
            )
            panel_rows.append(
                {
                    "fixed_effects": "actif et date",
                    "window": "après septembre 2012",
                    "coefficient": panel_holdout.coefficient,
                    "stderr": panel_holdout.stderr,
                    "tstat": panel_holdout.tstat,
                    "tstat_vs_one": panel_holdout.tstat_vs_one,
                    "n_observations": panel_holdout.n_observations,
                    "n_periods": panel_holdout.n_periods,
                    "r_squared": panel_holdout.r_squared,
                    "published_c": published["currency_panel_c"],
                    "published_t": published["currency_panel_t"],
                }
            )
            _write_table(pd.DataFrame(panel_rows), "panel_regression")

        # ------------------------------------------------------------------ #
        # 4. Le risque de queue et les crises
        # ------------------------------------------------------------------ #
        with stage("queue", experiment_id=experiment_id):
            scale = float(carry_returns.std(ddof=1) / momentum_returns.std(ddof=1))
            momentum_scaled = momentum_returns * scale
            tail = pd.DataFrame(
                [
                    _describe(carry_returns, "Portage de change", alpha_var),
                    _describe(
                        momentum_scaled, "Momentum de change, mis à la volatilité du portage", alpha_var
                    ),
                    _describe(passive, "Passif équipondéré", alpha_var),
                ]
            )
            tail["volatility_scale"] = [1.0, scale, 1.0]
            _write_table(tail, "tail_risk")

            episodes = drawdown_table(carry_returns).sort_values("depth").head(5).copy()
            episodes["depth_pct"] = episodes["depth"] * 100.0
            _write_table(episodes, "worst_drawdowns")

            crisis_rows: list[dict[str, Any]] = []
            for fenetre in params["crisis_windows"]:
                debut = pd.Timestamp(fenetre["start"])
                fin = pd.Timestamp(fenetre["end"])
                tranche = carry_returns.loc[debut:fin]
                if tranche.empty:
                    crisis_rows.append(
                        {
                            "label": fenetre["label"],
                            "start": str(debut.date()),
                            "end": str(fin.date()),
                            "n_months": 0,
                            "carry_cumulative_pct": float("nan"),
                            "momentum_cumulative_pct": float("nan"),
                            "passive_cumulative_pct": float("nan"),
                            "carry_worst_month_pct": float("nan"),
                        }
                    )
                    continue
                mom = momentum_returns.loc[debut:fin]
                pas = passive.loc[debut:fin]
                crisis_rows.append(
                    {
                        "label": fenetre["label"],
                        "start": str(tranche.index[0].date()),
                        "end": str(tranche.index[-1].date()),
                        "n_months": len(tranche),
                        "carry_cumulative_pct": float((np.prod(1.0 + tranche.to_numpy()) - 1.0) * 100.0),
                        "momentum_cumulative_pct": (
                            float((np.prod(1.0 + mom.to_numpy()) - 1.0) * 100.0) if len(mom) else float("nan")
                        ),
                        "passive_cumulative_pct": (
                            float((np.prod(1.0 + pas.to_numpy()) - 1.0) * 100.0) if len(pas) else float("nan")
                        ),
                        "carry_worst_month_pct": float(tranche.min() * 100.0),
                    }
                )
            _write_table(pd.DataFrame(crisis_rows), "crisis_windows")

        # ------------------------------------------------------------------ #
        # 5. Les coûts
        # ------------------------------------------------------------------ #
        with stage("couts", experiment_id=experiment_id):
            rotation = (
                _turnover(reference.raw_weights, excess, int(params["execution_lag"]))
                .reindex(carry_returns.index)
                .fillna(0.0)
            )
            annual_rotation = annualized_turnover(rotation, MONTHLY)
            breakeven = breakeven_cost_bps(carry_returns, rotation, frequency=MONTHLY)

            net_by_rate: dict[float, pd.Series] = {}
            cost_rows: list[dict[str, Any]] = []
            for taux in params["cost_bps_grid"]:
                cout = _cost_from_turnover(rotation, float(taux))
                net = (carry_returns - cout).dropna()
                net_by_rate[float(taux)] = net
                cost_rows.append(
                    {
                        "cost_bps": float(taux),
                        "n_months": len(net),
                        "gross_annual_pct": float(carry_returns.mean() * 12.0 * 100.0),
                        "net_annual_pct": float(net.mean() * 12.0 * 100.0),
                        "net_sharpe": sharpe_ratio(net, frequency=MONTHLY),
                        "annual_turnover": annual_rotation,
                        "holding_period_years": holding_period(annual_rotation),
                        "breakeven_cost_bps": breakeven,
                    }
                )
                counter = counter.record("couts", f"{taux:g}pb", cost_rows[-1]["net_sharpe"])
                sharpe_counter = sharpe_counter.record("couts", f"{taux:g}pb", cost_rows[-1]["net_sharpe"])
            _write_table(pd.DataFrame(cost_rows), "costs")

            reference_rate = float(config.costs.spread_bps)
            unit_cost = _cost_from_turnover(rotation, reference_rate)
            _univers_fx = "dix monnaies développées contre le dollar, FRED, taux à trois mois"
            save_series(
                RESULTS,
                "fx_carry_gross",
                carry_returns,
                sample=SampleTag.IN_SAMPLE,
                basis=CostBasis.GROSS,
                frequency=Frequency.MONTHLY,
                universe=_univers_fx,
                notes="fenêtre de l'article jusqu'à 2012-09 en IS, la suite en FINAL_HOLDOUT",
            )
            save_series(
                RESULTS,
                "fx_carry_net",
                (carry_returns - unit_cost).dropna(),
                sample=SampleTag.IN_SAMPLE,
                basis=CostBasis.NET,
                frequency=Frequency.MONTHLY,
                universe=_univers_fx,
                cost_assumptions=f"{reference_rate} pb par unité de rotation",
            )
            save_series(
                RESULTS,
                "fx_momentum_gross",
                momentum_returns,
                sample=SampleTag.IN_SAMPLE,
                basis=CostBasis.GROSS,
                frequency=Frequency.MONTHLY,
                universe=_univers_fx,
                notes="repère de momentum de change",
            )

            def evaluate_multiplier(multiplier: float) -> float:
                """Rend le ratio de Sharpe net au multiple de coût demandé."""
                return sharpe_ratio((carry_returns - multiplier * unit_cost).dropna(), frequency=MONTHLY)

            cost_analysis = cost_multiplier_analysis(
                evaluate_multiplier,
                multipliers=[float(m) for m in params["cost_multipliers"] if float(m) > 0.0],
                threshold=0.0,
            )
            _write_table(cost_analysis.table, "cost_multiples")
            for multiplier in params["cost_multipliers"]:
                if float(multiplier) > 0.0:
                    mesure = evaluate_multiplier(float(multiplier))
                    counter = counter.record("multiple", f"x{multiplier:g}", mesure)
                    sharpe_counter = sharpe_counter.record("multiple", f"x{multiplier:g}", mesure)

        # ------------------------------------------------------------------ #
        # 6. La robustesse
        # ------------------------------------------------------------------ #
        with stage("robustesse", experiment_id=experiment_id):
            variants: dict[str, pd.DataFrame] = {
                "carry": signal,
                "carry1_12": smoothed_signal(signal, window=12, skip=0),
                "carry2_13": smoothed_signal(signal, window=12, skip=1),
            }
            configurations: dict[str, pd.Series] = {}
            sweep_rows: list[dict[str, Any]] = []
            for scheme in params["weighting_grid"]:
                for variant_name in params["signal_variant_grid"]:
                    resultat = carry_portfolio(
                        variants[str(variant_name)],
                        excess,
                        scheme=str(scheme),
                        gross=gross,
                        min_assets=min_assets,
                    )
                    brut = resultat.returns.dropna()
                    rotation_cellule = (
                        _turnover(resultat.raw_weights, excess, int(params["execution_lag"]))
                        .reindex(brut.index)
                        .fillna(0.0)
                    )
                    net = (brut - _cost_from_turnover(rotation_cellule, reference_rate)).dropna()
                    cle = f"{scheme} | {variant_name}"
                    configurations[cle] = net
                    sweep_rows.append(
                        {
                            "weighting": str(scheme),
                            "signal_variant": str(variant_name),
                            "n_months": len(net),
                            "net_annual_pct": float(net.mean() * 12.0 * 100.0),
                            "net_sharpe": sharpe_ratio(net, frequency=MONTHLY),
                            "net_tstat": sharpe_tstat(net, frequency=MONTHLY),
                            "skewness": skewness(net),
                            "annual_turnover": annualized_turnover(rotation_cellule, MONTHLY),
                        }
                    )
                    counter = counter.record("sweep", cle, sweep_rows[-1]["net_sharpe"])
                    sharpe_counter = sharpe_counter.record("sweep", cle, sweep_rows[-1]["net_sharpe"])
            sweep = pd.DataFrame(sweep_rows)
            _write_table(sweep, "parameter_sweep")

            delay_rows: list[dict[str, Any]] = []
            for delay in params["execution_delays"]:
                retarde = carry_portfolio(
                    signal,
                    excess,
                    scheme=str(params["weighting"]),
                    gross=gross,
                    min_assets=min_assets,
                    execution_lag=int(delay),
                ).returns.dropna()
                delay_rows.append(
                    {
                        "execution_lag_months": int(delay),
                        "n_months": len(retarde),
                        "annual_return_pct": float(retarde.mean() * 12.0 * 100.0),
                        "sharpe": sharpe_ratio(retarde, frequency=MONTHLY),
                    }
                )
                counter = counter.record("delai", f"lag{delay}", delay_rows[-1]["sharpe"])
                sharpe_counter = sharpe_counter.record("delai", f"lag{delay}", delay_rows[-1]["sharpe"])
            _write_table(pd.DataFrame(delay_rows), "execution_delay")

            extended = _spliced_rates(rates, alternates)
            signal_ext, excess_ext = _build_panel(extended, spots, start, end)
            extended_result = carry_portfolio(
                signal_ext, excess_ext, scheme=str(params["weighting"]), gross=gross, min_assets=min_assets
            )
            extended_returns = extended_result.returns.dropna()
            extended_panel = panel_carry_regression(signal_ext, excess_ext)
            rate_rows = [
                {
                    "rate_source": "taux interbancaire à trois mois seul",
                    "first_jpy_carry": str(signal["JPY"].dropna().index[0].date()),
                    "first_chf_carry": str(signal["CHF"].dropna().index[0].date()),
                    "n_months": len(carry_returns),
                    "annual_return_pct": float(carry_returns.mean() * 12.0 * 100.0),
                    "sharpe": sharpe_ratio(carry_returns, frequency=MONTHLY),
                    "skewness": skewness(carry_returns),
                    "panel_c": panel_full.coefficient,
                    "panel_t": panel_full.tstat,
                },
                {
                    "rate_source": (
                        "rallongé, certificats de dépôt au Japon et argent au jour le jour en Suisse"
                    ),
                    "first_jpy_carry": str(signal_ext["JPY"].dropna().index[0].date()),
                    "first_chf_carry": str(signal_ext["CHF"].dropna().index[0].date()),
                    "n_months": len(extended_returns),
                    "annual_return_pct": float(extended_returns.mean() * 12.0 * 100.0),
                    "sharpe": sharpe_ratio(extended_returns, frequency=MONTHLY),
                    "skewness": skewness(extended_returns),
                    "panel_c": extended_panel.coefficient,
                    "panel_t": extended_panel.tstat,
                },
            ]
            _write_table(pd.DataFrame(rate_rows), "rate_source_variant")

            # ------------------------------------------------------------ #
            # Le numéraire compte-t-il comme un actif classé ?
            # ------------------------------------------------------------ #
            # L'article classe des CONTRATS de change, tous libellés contre le
            # dollar, et le dollar lui-même n'est donc pas un actif classable.
            # Notre cas de référence lui donne une colonne de portage nul, ce
            # qui lui vaut un rang et un poids. La variante ci-dessous retire
            # cette colonne et mesure ce que le choix change.
            signal_ten = signal.drop(columns=["USD"])
            excess_ten = excess.drop(columns=["USD"])
            ten_result = carry_portfolio(
                signal_ten,
                excess_ten,
                scheme=str(params["weighting"]),
                gross=gross,
                min_assets=min_assets,
                execution_lag=int(params["execution_lag"]),
            )
            ten_returns = ten_result.returns.dropna()
            ten_paper = ten_returns.loc[paper_start:paper_end]
            ten_panel_paper = panel_carry_regression(
                signal_ten.loc[paper_start:paper_end], excess_ten.loc[paper_start:paper_end]
            )
            ten_panel_full = panel_carry_regression(signal_ten, excess_ten)
            numeraire_rows = [
                {
                    "univers": "onze actifs, le dollar classé comme les autres",
                    "n_months_full": len(carry_returns),
                    "n_months_paper": len(paper_window),
                    "mean_net_foreign_weight": float(weights.drop(columns=["USD"]).sum(axis=1).mean()),
                    "paper_sharpe": sharpe_ratio(paper_window, frequency=MONTHLY),
                    "paper_skewness": skewness(paper_window),
                    "full_sharpe": sharpe_ratio(carry_returns, frequency=MONTHLY),
                    "full_skewness": skewness(carry_returns),
                    "paper_panel_c": float(panel_reference.coefficient),
                    "paper_panel_t": float(panel_reference.tstat),
                    "full_panel_c": float(panel_full.coefficient),
                    "full_panel_t": float(panel_full.tstat),
                    "published_sharpe": published["currency_sharpe"],
                    "published_skewness": published["currency_skew"],
                    "published_panel_c": published["currency_panel_c"],
                },
                {
                    "univers": "dix actifs, le dollar tenu pour numéraire seul",
                    "n_months_full": len(ten_returns),
                    "n_months_paper": len(ten_paper),
                    "mean_net_foreign_weight": float(
                        ten_result.weights.loc[ten_returns.index].sum(axis=1).mean()
                    ),
                    "paper_sharpe": sharpe_ratio(ten_paper, frequency=MONTHLY),
                    "paper_skewness": skewness(ten_paper),
                    "full_sharpe": sharpe_ratio(ten_returns, frequency=MONTHLY),
                    "full_skewness": skewness(ten_returns),
                    "paper_panel_c": float(ten_panel_paper.coefficient),
                    "paper_panel_t": float(ten_panel_paper.tstat),
                    "full_panel_c": float(ten_panel_full.coefficient),
                    "full_panel_t": float(ten_panel_full.tstat),
                    "published_sharpe": published["currency_sharpe"],
                    "published_skewness": published["currency_skew"],
                    "published_panel_c": published["currency_panel_c"],
                },
            ]
            _write_table(pd.DataFrame(numeraire_rows), "numeraire_variant")
            ten_sharpe = sharpe_ratio(ten_returns, frequency=MONTHLY)
            counter = counter.record("numeraire", "dix actifs", ten_sharpe)
            sharpe_counter = sharpe_counter.record("numeraire", "dix actifs", ten_sharpe)
            extended_sharpe = sharpe_ratio(extended_returns, frequency=MONTHLY)
            counter = counter.record("taux", "rallonge", extended_sharpe)
            sharpe_counter = sharpe_counter.record("taux", "rallonge", extended_sharpe)

            subperiods = subperiod_performance(
                net_by_rate[reference_rate],
                breakpoints=[pd.Timestamp(b) for b in params["subperiod_breakpoints"]],
                frequency=MONTHLY,
                min_observations=12,
            )
            subperiods["label"] = [
                f"{pd.Timestamp(a):%Y-%m} à {pd.Timestamp(b):%Y-%m}"
                for a, b in zip(subperiods["start"], subperiods["end"], strict=True)
            ]
            _write_table(subperiods, "subperiods")

        # ------------------------------------------------------------------ #
        # 7. La substitution obligataire
        # ------------------------------------------------------------------ #
        with stage("obligataire", experiment_id=experiment_id):
            slope_carry: dict[str, pd.Series] = {}
            slope_return: dict[str, pd.Series] = {}
            for code, rendement_long in bond_yields.items():
                tableau = bond_slope_carry(
                    rendement_long, rates[code], maturity_years=float(params["bond_maturity_years"])
                )
                slope_carry[code] = tableau["carry"]
                slope_return[code] = tableau["excess_return"]
            slope_signal = pd.DataFrame(slope_carry).sort_index().loc[start:end]
            slope_excess = pd.DataFrame(slope_return).sort_index().reindex(slope_signal.index)
            slope_result = carry_portfolio(
                slope_signal, slope_excess, scheme="rank", gross=gross, min_assets=min_assets
            )
            slope_returns = slope_result.returns.dropna()
            slope_panel = panel_carry_regression(slope_signal, slope_excess)
            slope_frame = pd.DataFrame(
                [
                    {
                        **_describe(slope_returns, "Pente obligataire, substitution déclarée", alpha_var),
                        "panel_c": slope_panel.coefficient,
                        "panel_t": slope_panel.tstat,
                        "n_panel_observations": slope_panel.n_observations,
                        "published_sharpe": published["slope_sharpe"],
                        "published_panel_c": published["slope_panel_c"],
                        "published_panel_t": published["slope_panel_t"],
                        "substitution": (
                            "La descente de courbe de l'équation (13) est OMISE. Le portage retenu "
                            "est la seule pente, et le rendement est approché par la duration."
                        ),
                    }
                ]
            )
            _write_table(slope_frame, "bond_slope_substitution")
            slope_sharpe = sharpe_ratio(slope_returns, frequency=MONTHLY)
            counter = counter.record("obligataire", "pente", slope_sharpe)
            sharpe_counter = sharpe_counter.record("obligataire", "pente", slope_sharpe)

        # ------------------------------------------------------------------ #
        # 7 bis. Les deux jambes du portage de change
        # ------------------------------------------------------------------ #
        with stage("jambes", experiment_id=experiment_id):
            available = signal.notna().shift(int(params["execution_lag"])).fillna(value=False)
            legs = dollar_decomposition(reference.weights, excess, available.reindex(reference.weights.index))
            legs = legs.loc[carry_returns.index]
            leg_rows = [
                _describe(legs["total"], "Portage complet", alpha_var),
                _describe(legs["dollar_neutral"], "Jambe neutre au dollar", alpha_var),
                _describe(legs["dollar"], "Jambe de dollar", alpha_var),
            ]
            leg_frame = pd.DataFrame(leg_rows)
            leg_frame["mean_net_foreign_weight"] = [
                float(legs["net_foreign_weight"].mean()),
                0.0,
                float(legs["net_foreign_weight"].mean()),
            ]
            leg_frame["identity_max_error"] = [
                float((legs["dollar_neutral"] + legs["dollar"] - legs["total"]).abs().max())
            ] * 3
            _write_table(leg_frame, "dollar_legs")
            neutral_sharpe = sharpe_ratio(legs["dollar_neutral"], frequency=MONTHLY)
            dollar_sharpe = sharpe_ratio(legs["dollar"], frequency=MONTHLY)
            counter = counter.record("jambes", "neutre", neutral_sharpe)
            counter = counter.record("jambes", "dollar", dollar_sharpe)
            sharpe_counter = sharpe_counter.record("jambes", "neutre", neutral_sharpe)
            sharpe_counter = sharpe_counter.record("jambes", "dollar", dollar_sharpe)

        # ------------------------------------------------------------------ #
        # 8. Les contrôles statistiques
        # ------------------------------------------------------------------ #
        with stage("validation", experiment_id=experiment_id):
            performance_matrix = pd.DataFrame(configurations).dropna()
            pbo_result = probability_of_backtest_overfitting(
                performance_matrix, n_splits=8, frequency=MONTHLY
            )

            def best_of_path(path: Any) -> float:
                """Choisit la meilleure configuration sur chaque bloc d'apprentissage.

                La validation croisée combinatoire ne dit rien d'une série figée,
                puisque tout chemin la reconstruit en entier. Elle juge donc ici
                le PROCESSUS de sélection : sur chaque bloc d'apprentissage, la
                configuration de meilleur Sharpe est retenue, et son rendement du
                bloc de test suivant est collecté.
                """
                pieces: list[pd.Series] = []
                for segment in path.segments:
                    train = performance_matrix.iloc[segment.train_index]
                    test = performance_matrix.iloc[segment.test_index]
                    best = max(
                        performance_matrix.columns,
                        key=lambda column: sharpe_ratio(train[column], frequency=MONTHLY),
                    )
                    pieces.append(test[best])
                return sharpe_ratio(pd.concat(pieces).sort_index(), frequency=MONTHLY)

            cv = CombinatorialPurgedCV.from_config(config.validation)
            distribution = cpcv_performance_distribution(
                cv, performance_matrix, best_of_path, metric_name="sharpe"
            )
            cpcv_frame = distribution.summary.rename("value").reset_index()
            cpcv_frame.columns = ["statistic", "value"]
            # La CPCV juge ici un processus de sélection qui retient presque
            # toujours la même configuration. Deux chemins qui la retiennent
            # partout rendent alors la MÊME série, donc le même ratio. Le
            # nombre de valeurs distinctes dit combien de chemins sont
            # réellement différents, et sans lui l'écart type se lit comme une
            # dispersion qui n'existe pas.
            cpcv_frame = pd.concat(
                [
                    cpcv_frame,
                    pd.DataFrame(
                        {
                            "statistic": ["distinct_paths"],
                            "value": [float(distribution.metrics.round(12).nunique())],
                        }
                    ),
                ],
                ignore_index=True,
            )
            _write_table(cpcv_frame, "cpcv_distribution")
            _write_table(distribution.metrics.rename("sharpe").reset_index(), "cpcv_paths")

            net_holdout = net_by_rate[reference_rate].loc[net_by_rate[reference_rate].index > paper_end]
            oos_sharpe = sharpe_ratio(net_holdout, frequency=MONTHLY)
            oos_tstat = sharpe_tstat(net_holdout, frequency=MONTHLY)
            n_trials = counter.n_trials()
            if n_trials != expected_trials:
                raise ConfigError(
                    f"{n_trials} essais enregistrés contre {expected_trials} déduits des grilles. "
                    "Le compte du registre et celui du ratio de Sharpe dégonflé divergeraient."
                )
            trial_variance = max(sharpe_counter.sharpe_variance(), 1e-6)
            n_sharpe_trials = sharpe_counter.n_trials()
            deflated_value = deflated_sharpe_ratio(
                observed_sr=oos_sharpe,
                sharpe_variance_across_trials=trial_variance,
                n_trials=n_trials,
                n_obs=float(len(net_holdout)),
                skew=skewness(net_holdout),
                kurtosis=kurtosis(net_holdout, excess=False),
            )
            expected_max = expected_maximum_sharpe(n_trials, trial_variance)
            if oos_sharpe > 0.0:
                cut = haircut_sharpe(
                    observed_sr=oos_sharpe,
                    n_tests=n_trials,
                    n_obs=len(net_holdout),
                    frequency=MONTHLY,
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
            _write_table(
                pd.DataFrame(
                    [
                        {
                            "observed_sharpe_oos_net": oos_sharpe,
                            "observed_tstat": oos_tstat,
                            "n_observations": len(net_holdout),
                            "n_trials": n_trials,
                            "n_sharpe_valued_trials": n_sharpe_trials,
                            "variance_of_trial_sharpes": trial_variance,
                            "expected_maximum_sharpe_under_null": expected_max,
                            "deflated_sharpe": deflated_value,
                            "required_tstat_bonferroni": required_tstat(n_trials, 0.05, method="bonferroni"),
                            "adjusted_tstat": adjusted_tstat,
                            "haircut_status": haircut_status,
                        }
                    ]
                ),
                "deflated_sharpe",
            )

            sweep_tstats = list(sweep["net_tstat"])
            sweep_pvalues = [_pvalue(float(t)) for t in sweep_tstats]
            multiplicity = adjust_pvalues(sweep_pvalues, method="holm", alpha=0.05)
            _write_table(
                pd.DataFrame(
                    {
                        "configuration": [
                            f"{a} | {b}"
                            for a, b in zip(sweep["weighting"], sweep["signal_variant"], strict=True)
                        ],
                        "net_tstat": sweep_tstats,
                        "pvalue": sweep_pvalues,
                        "adjusted_pvalue": multiplicity.adjusted_pvalues,
                        "rejected": multiplicity.rejected,
                    }
                ),
                "multiple_testing",
            )

            block_size = float(params["bootstrap_block_months"])
            draws = int(params["bootstrap_resamples"])
            sample = net_holdout.to_numpy()
            # Blocs CIRCULAIRES. Des blocs tronqués à la fin de l'échantillon
            # rendent des rééchantillons plus courts que l'original et donnent
            # au premier mois 8 % du poids des autres, mesuré. Le repli modulo
            # rend à chaque mois le même poids et à chaque tirage la même
            # longueur.
            n_obs_boot = len(sample)
            taille = int(block_size)
            n_blocs = int(np.ceil(n_obs_boot / block_size))
            replicates = np.empty(draws, dtype=float)
            for draw in range(draws):
                starts = generator.integers(0, n_obs_boot, size=n_blocs)
                positions = (starts[:, None] + np.arange(taille)[None, :]) % n_obs_boot
                joined = sample[positions.reshape(-1)[:n_obs_boot]]
                replicates[draw] = joined.mean() * 12.0
            _write_table(
                pd.DataFrame(
                    {
                        "statistic": ["rendement annualisé net du portage, après septembre 2012"],
                        "observed": [float(sample.mean() * 12.0)],
                        "p05": [float(np.quantile(replicates, 0.05))],
                        "p95": [float(np.quantile(replicates, 0.95))],
                        "share_positive": [float((replicates > 0.0).mean())],
                        "n_resamples": [draws],
                    }
                ),
                "bootstrap",
            )

            _write_table(
                pd.DataFrame(
                    [
                        {"family": family, "n_trials": counter.n_trials(family)}
                        for family in counter.families()
                    ]
                    + [{"family": "TOTAL", "n_trials": n_trials}]
                ),
                "trials",
            )

        # ------------------------------------------------------------------ #
        # 9. Les figures
        # ------------------------------------------------------------------ #
        with stage("figures", experiment_id=experiment_id):
            figure_specs: list[tuple[str, str, str]] = []
            debut_courbe = carry_returns.index[0]

            fig, _ = viz.equity_curve(
                {
                    "Portage de change": carry_returns,
                    "Momentum de change": momentum_returns,
                },
                benchmark=passive,
                benchmark_label="Passif équipondéré",
                log_scale=True,
                currency="$ US",
                title=(
                    "Richesse cumulée du portage de change, base 1 dollar des États-Unis "
                    f"au {debut_courbe:%Y-%m-%d}"
                ),
            )
            figure_specs.append(
                (
                    _save_figure(fig, "equity_carry").stem,
                    "performance",
                    "Richesse cumulée en échelle logarithmique, dollars des États-Unis.",
                )
            )

            fig, _ = viz.underwater(carry_returns, title="Repli du portefeuille de portage de change")
            figure_specs.append(
                (
                    _save_figure(fig, "underwater_carry").stem,
                    "robustness",
                    "Distance au sommet précédent, en points de pourcentage.",
                )
            )

            fig, _ = viz.return_histogram(carry_returns, title="Distribution mensuelle du portage de change")
            figure_specs.append(
                (
                    _save_figure(fig, "return_histogram").stem,
                    "statistical_tests",
                    "Histogramme des rendements mensuels et loi normale de même moyenne.",
                )
            )

            fig, _ = viz.qq_plot(
                carry_returns, title="Quantiles du portage de change contre quantiles normaux"
            )
            figure_specs.append(
                (
                    _save_figure(fig, "qq_plot_carry").stem,
                    "statistical_tests",
                    "Écart à la normalité des rendements mensuels du portage.",
                )
            )

            fig, _ = viz.rolling_metric(
                carry_returns,
                metric="sharpe",
                window=120,
                frequency=MONTHLY,
                title="Ratio de Sharpe glissant sur dix ans du portage de change",
            )
            figure_specs.append(
                (
                    _save_figure(fig, "rolling_sharpe_carry").stem,
                    "out_of_sample",
                    "Ratio de Sharpe annualisé sur fenêtre glissante de 120 mois.",
                )
            )

            fig, _ = viz.subperiod_bars(
                subperiods,
                metric_column="sharpe",
                error_column="sharpe_se_lo",
                title="Ratio de Sharpe net du portage par sous-période",
            )
            figure_specs.append(
                (
                    _save_figure(fig, "subperiod_bars").stem,
                    "robustness",
                    "Ratio de Sharpe annualisé et son intervalle à 95 pour cent, par sous-période.",
                )
            )

            fig, _ = viz.cost_sensitivity(
                list(cost_analysis.table["multiplier"]),
                list(cost_analysis.table["metric"]),
                threshold=0.0,
                metric_label="Ratio de Sharpe net du portage",
                title="Sensibilité au multiple de coût, portage de change",
            )
            figure_specs.append(
                (
                    _save_figure(fig, "cost_sensitivity").stem,
                    "costs",
                    "Ratio de Sharpe net en fonction du multiple appliqué aux deux points de base.",
                )
            )

            lisible = sweep.copy()
            lisible["signal_variant"] = lisible["signal_variant"].map(VARIANT_LABELS)
            lisible["weighting"] = lisible["weighting"].map(SCHEME_LABELS)
            fig, _ = viz.parameter_heatmap(
                lisible,
                x="signal_variant",
                y="weighting",
                metric="net_sharpe",
                x_label="Variante de signal",
                y_label="Schéma de pondération",
                metric_label="Ratio de Sharpe net",
                title="Ratio de Sharpe net selon le schéma de pondération et la variante de signal",
            )
            figure_specs.append(
                (
                    _save_figure(fig, "parameter_heatmap").stem,
                    "robustness",
                    "Une case par couple de réglages, ratio de Sharpe net de deux points de base.",
                )
            )

            correlation_source = pd.DataFrame(
                {
                    "Portage": carry_returns,
                    "Momentum": momentum_returns,
                    "Passif": passive,
                    "Pente obligataire": slope_returns,
                }
            ).dropna()
            correlation_table = correlation_source.corr().reset_index()
            correlation_table = correlation_table.rename(columns={"index": "series"})
            correlation_table.insert(1, "n_months", len(correlation_source))
            _write_table(correlation_table, "comparator_correlations")
            fig, _ = viz.correlation_heatmap(
                correlation_source,
                title="Corrélations mensuelles entre le portage et ses comparateurs",
            )
            figure_specs.append(
                (
                    _save_figure(fig, "correlation_heatmap").stem,
                    "factor_attribution",
                    "Corrélations de Pearson sur les mois communs aux quatre séries.",
                )
            )

        # ------------------------------------------------------------------ #
        # 10. Le verdict
        # ------------------------------------------------------------------ #
        paper_sharpe = sharpe_ratio(paper_window, frequency=MONTHLY)
        checks = (
            ReplicationCheck(
                quantity="ratio de Sharpe du portage de change",
                published=float(published["currency_sharpe"]),
                ours=paper_sharpe,
                tolerance=float(params["verdict"]["replication_tolerance"]),
                source="Koijen et coauteurs (2018), tableau 2, panneau A, colonne Devises",
            ),
            ReplicationCheck(
                quantity="volatilité annualisée du portage, en pourcentage",
                published=float(published["currency_vol_pct"]),
                ours=float(paper_window.std(ddof=1) * math.sqrt(12.0) * 100.0),
                tolerance=float(params["verdict"]["replication_tolerance"]),
                source="Koijen et coauteurs (2018), tableau 2, panneau A, colonne Devises",
            ),
            ReplicationCheck(
                quantity="asymétrie du portage de change",
                published=float(published["currency_skew"]),
                ours=skewness(paper_window),
                tolerance=float(params["verdict"]["replication_tolerance"]),
                source="Koijen et coauteurs (2018), tableau 2, panneau A, colonne Devises",
            ),
            ReplicationCheck(
                quantity="coefficient c de l'équation (23)",
                published=float(published["currency_panel_c"]),
                ours=float(panel_reference.coefficient),
                tolerance=float(params["verdict"]["replication_tolerance"]),
                source="Koijen et coauteurs (2018), tableau 4, ligne Devises",
            ),
            ReplicationCheck(
                quantity="statistique t du coefficient c",
                published=float(published["currency_panel_t"]),
                ours=float(panel_reference.tstat),
                tolerance=float(params["verdict"]["replication_tolerance"]),
                source="Koijen et coauteurs (2018), tableau 4, ligne Devises",
            ),
        )
        _write_table(replication_table(checks), "replication_checks")

        criteria = VerdictCriteria(**params["verdict"])
        positive_share = float((subperiods["sharpe"] > 0.0).mean())
        surviving = (
            cost_analysis.breakeven_multiplier
            if cost_analysis.breakeven_multiplier is not None
            else (
                float(cost_analysis.table["multiplier"].max())
                if cost_analysis.status == "survives_all"
                else 0.0
            )
        )
        evidence = VerdictEvidence(
            hypothesis_supported=bool(panel_reference.coefficient > 0.0 and paper_sharpe > 0.0),
            replication_checks=checks,
            oos_sharpe=oos_sharpe,
            tstat_after_multiplicity=adjusted_tstat,
            deflated_sharpe=deflated_value,
            pbo=pbo_result.pbo,
            positive_subperiod_share=positive_share,
            surviving_cost_multiple=surviving,
            portfolio_correlation=float(carry_returns.corr(passive.reindex(carry_returns.index))),
            notes=(
                "Le verdict ne porte que sur le portage de change. Les trois autres classes "
                "d'actifs de l'article ne sont pas jugées, faute de données gratuites."
            ),
        )
        verdict, reasons = decide_verdict(evidence, criteria)
        run.set_verdict(verdict)

        metric_values = {
            "sharpe_portage_fenetre_article": paper_sharpe,
            "rendement_portage_fenetre_article_pct": float(paper_window.mean() * 12.0 * 100.0),
            "volatilite_portage_fenetre_article_pct": float(
                paper_window.std(ddof=1) * math.sqrt(12.0) * 100.0
            ),
            "asymetrie_portage_fenetre_article": skewness(paper_window),
            "aplatissement_portage_fenetre_article": kurtosis(paper_window),
            "panel_c_fenetre_article": float(panel_reference.coefficient),
            "panel_t_fenetre_article": float(panel_reference.tstat),
            "panel_c_echantillon_complet": float(panel_full.coefficient),
            "panel_t_echantillon_complet": float(panel_full.tstat),
            "sharpe_portage_complet": sharpe_ratio(carry_returns, frequency=MONTHLY),
            "asymetrie_portage_complet": skewness(carry_returns),
            "asymetrie_momentum_complet": skewness(momentum_returns),
            "perte_esperee_portage_pct": expected_shortfall(carry_returns, alpha_var) * 100.0,
            "perte_esperee_momentum_pct": expected_shortfall(momentum_scaled, alpha_var) * 100.0,
            "sharpe_hors_echantillon_net": oos_sharpe,
            "rotation_annualisee": annual_rotation,
            "cout_de_rentabilite_bps": breakeven,
            "probabilite_de_surapprentissage": pbo_result.pbo,
            "sharpe_degonfle": deflated_value,
            "t_apres_correction": adjusted_tstat,
            "part_de_sous_periodes_positives": positive_share,
            "correlation_avec_le_passif": evidence.portfolio_correlation or float("nan"),
            "cpcv_sharpe_moyen": float(distribution.summary["mean"]),
            "cpcv_part_de_chemins_negatifs": float(distribution.negative_share),
            "sharpe_pente_obligataire": sharpe_ratio(slope_returns, frequency=MONTHLY),
            "panel_c_pente_obligataire": float(slope_panel.coefficient),
            "sharpe_jambe_neutre_au_dollar": sharpe_ratio(legs["dollar_neutral"], frequency=MONTHLY),
            "asymetrie_jambe_neutre_au_dollar": skewness(legs["dollar_neutral"]),
            "sharpe_jambe_de_dollar": sharpe_ratio(legs["dollar"], frequency=MONTHLY),
            "asymetrie_jambe_de_dollar": skewness(legs["dollar"]),
        }
        labels = {
            "sharpe_portage_fenetre_article": MetricLabel(SampleTag.IN_SAMPLE, CostBasis.GROSS),
            "rendement_portage_fenetre_article_pct": MetricLabel(SampleTag.IN_SAMPLE, CostBasis.GROSS),
            "volatilite_portage_fenetre_article_pct": MetricLabel(SampleTag.IN_SAMPLE, CostBasis.GROSS),
            "asymetrie_portage_fenetre_article": MetricLabel(SampleTag.IN_SAMPLE, CostBasis.GROSS),
            "aplatissement_portage_fenetre_article": MetricLabel(SampleTag.IN_SAMPLE, CostBasis.GROSS),
            "panel_c_fenetre_article": MetricLabel(SampleTag.IN_SAMPLE, CostBasis.GROSS),
            "panel_t_fenetre_article": MetricLabel(SampleTag.IN_SAMPLE, CostBasis.GROSS),
            "panel_c_echantillon_complet": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "panel_t_echantillon_complet": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "sharpe_portage_complet": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "asymetrie_portage_complet": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "asymetrie_momentum_complet": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "perte_esperee_portage_pct": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "perte_esperee_momentum_pct": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "sharpe_hors_echantillon_net": MetricLabel(SampleTag.FINAL_HOLDOUT, CostBasis.NET),
            "rotation_annualisee": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "cout_de_rentabilite_bps": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "probabilite_de_surapprentissage": MetricLabel(SampleTag.VALIDATION, CostBasis.NET),
            "sharpe_degonfle": MetricLabel(SampleTag.FINAL_HOLDOUT, CostBasis.NET),
            "t_apres_correction": MetricLabel(SampleTag.FINAL_HOLDOUT, CostBasis.NET),
            "part_de_sous_periodes_positives": MetricLabel(SampleTag.VALIDATION, CostBasis.NET),
            "correlation_avec_le_passif": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "cpcv_sharpe_moyen": MetricLabel(SampleTag.OUT_OF_SAMPLE, CostBasis.NET),
            "cpcv_part_de_chemins_negatifs": MetricLabel(SampleTag.OUT_OF_SAMPLE, CostBasis.NET),
            "sharpe_pente_obligataire": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "panel_c_pente_obligataire": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "sharpe_jambe_neutre_au_dollar": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "asymetrie_jambe_neutre_au_dollar": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "sharpe_jambe_de_dollar": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
            "asymetrie_jambe_de_dollar": MetricLabel(SampleTag.VALIDATION, CostBasis.GROSS),
        }
        metrics = metrics_table(metric_values, labels)
        _write_table(metrics, "metrics")
        for name, value in metric_values.items():
            run.log_metric(name, value, sample=labels[name].sample)

        payload = {
            "study": "008_carry",
            "experiment_id": experiment_id,
            "seed": config.seed,
            "verdict": verdict.value,
            "reasons": reasons,
            "n_trials": n_trials,
            "trials_by_family": {family: counter.n_trials(family) for family in counter.families()},
            "metrics": metric_values,
            "metric_samples": {name: label.sample.value for name, label in labels.items()},
            "cost_basis": {name: label.cost_basis.value for name, label in labels.items()},
            "samples": {
                "full_window": [
                    str(carry_returns.index[0].date()),
                    str(carry_returns.index[-1].date()),
                ],
                "paper_window": [str(paper_window.index[0].date()), str(paper_window.index[-1].date())],
                "holdout_window": [str(holdout.index[0].date()), str(holdout.index[-1].date())],
            },
            "cost_assumptions_bps": {"spread_bps": config.costs.spread_bps},
            "data_quality": {
                "weighted_cells_without_return": missing_cells,
                "weighted_cells_total": traded_cells,
            },
            "n_currencies": n_currencies,
        }
        (RESULTS / "metrics.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        report_tables = [
            ReportTable("data_sources", "data", pd.DataFrame(source_rows), "Les séries employées."),
            ReportTable(
                "asset_classes_not_reproducible",
                "data",
                pd.DataFrame(list(UNREPRODUCIBLE)),
                "Les trois classes d'actifs non reproductibles.",
            ),
            ReportTable("replication_table2", "replication", table2, "Tableau 2, panneau A."),
            ReportTable(
                "panel_regression", "replication", pd.DataFrame(panel_rows), "Équation (23), coefficient c."
            ),
            ReportTable("tail_risk", "performance", tail, "Le risque de queue, portage contre momentum."),
            ReportTable(
                "comparator_correlations",
                "factor_attribution",
                correlation_table,
                "Corrélations mensuelles entre le portage et ses comparateurs.",
            ),
            ReportTable(
                "dollar_legs",
                "factor_attribution",
                leg_frame,
                "Les deux jambes du portage, neutre au dollar et pari sur le dollar.",
            ),
            ReportTable(
                "crisis_windows", "robustness", pd.DataFrame(crisis_rows), "Le portage dans les crises."
            ),
            ReportTable("costs", "costs", pd.DataFrame(cost_rows), "Coûts et rendement net."),
            ReportTable("parameter_sweep", "robustness", sweep, "Balayage des réglages."),
            ReportTable("subperiods", "robustness", subperiods, "Sous-périodes."),
            ReportTable(
                "numeraire_variant",
                "robustness",
                pd.DataFrame(numeraire_rows),
                "Le dollar classé comme un actif, ou tenu pour numéraire seul.",
            ),
            ReportTable(
                "bond_slope_substitution",
                "out_of_sample",
                slope_frame,
                "La pente obligataire, substitution déclarée.",
            ),
            ReportTable(
                "cpcv_distribution",
                "out_of_sample",
                cpcv_frame,
                "Validation croisée combinatoire purgée.",
            ),
            ReportTable(
                "trials",
                "statistical_tests",
                pd.DataFrame([{"family": f, "n_trials": counter.n_trials(f)} for f in counter.families()]),
                "Le compte des essais.",
            ),
        ]
        report_figures = [
            ReportFigure(name, section, FIGURES / f"{name}.png", caption)
            for name, section, caption in figure_specs
        ]
        report = StudyReport(
            study_name="008_carry",
            experiment_id=experiment_id,
            hypothesis=config.hypothesis,
            paper=config.paper or "",
            criteria=criteria,
            evidence=evidence,
            sections=_sections(metric_values, n_currencies),
            metrics=metrics,
            tables=report_tables,
            figures=report_figures,
            config=config.model_dump(mode="json"),
            dataset_manifests=manifests,
        )
        generate_report(STUDY_DIR, report)
        run.log_artifact(str(RESULTS))

        alpha_registry = AlphaRegistry()
        alpha_registry.register(
            AlphaMetadata(
                name="currency_carry_koijen_2018",
                family="carry",
                paper=config.paper,
                asset_classes=[AssetClass.FX],
                horizon="formation à la fin du mois, détention un mois",
                economic_rationale=["prime de risque", "contrainte institutionnelle"],
                inputs=[
                    "taux de change quotidiens de la Réserve fédérale, série DEX",
                    "taux interbancaires à trois mois de l'OCDE, série IR3TIB01",
                ],
                known_risks=[
                    "L'asymétrie des rendements est négative et les pertes se concentrent dans les crises.",
                    "Le portage se paie sur des monnaies dont la liquidité se retire en même temps.",
                    "L'univers de dix monnaies développées est plus étroit que celui de l'article.",
                ],
                validation_status=verdict,
                verdict_experiment_id=experiment_id,
                created=pd.Timestamp.today().date(),
                last_modified=pd.Timestamp.today().date(),
                notes=(
                    "Étude 008. Le mécanisme invoqué est une prime de risque qui varie dans le "
                    "temps, dont le portage est la partie observable. La contrainte "
                    "institutionnelle est le retrait du capital d'arbitrage quand la liquidité "
                    "mondiale se dégrade, ce que mesure le comportement en crise. Le verdict est "
                    "déduit par quantlab.reporting.study.decide_verdict."
                ),
            ),
            overwrite=True,
        )
        LOG.info("étude terminée", extra={"verdict": verdict.value, "n_trials": n_trials})


if __name__ == "__main__":
    main()

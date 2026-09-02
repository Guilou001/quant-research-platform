"""Le point d'entrée de l'étude 002, momentum transversal.

Le script orchestre, il ne calcule pas. Tout ce qui mérite d'être appelé deux
fois vit dans :mod:`quantlab.strategies.cross_sectional_momentum` ou dans
:mod:`quantlab.analytics`, conformément à la règle 11 du ``CLAUDE.md``.

Il s'exécute depuis la racine du dépôt::

    export QUANTLAB_USER_AGENT="votre nom votre.adresse@exemple.org"
    uv run python studies/002_cross_sectional_momentum/run.py

Tout ce qu'il écrit va sous ``studies/002_cross_sectional_momentum/results/``.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from quantlab.analytics.drawdown import max_drawdown
from quantlab.analytics.regression import beta, factor_regression
from quantlab.analytics.risk import kurtosis, skewness
from quantlab.analytics.turnover import annualized_turnover, turnover_series
from quantlab.analytics.visualization import figures as fig
from quantlab.backtest.engine import run_backtest
from quantlab.core.config import ExperimentConfig, load_config
from quantlab.core.determinism import make_generator
from quantlab.core.logging import configure_logging, get_logger, stage
from quantlab.core.types import AssetClass, CostBasis, Frequency, SampleTag, Verdict
from quantlab.data.providers.french import FrenchProvider
from quantlab.data.providers.yahoo import YahooProvider, to_wide
from quantlab.execution.costs import breakeven_cost_bps, from_config
from quantlab.experiments import ExperimentRegistry
from quantlab.reporting.study import (
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
from quantlab.strategies.cross_sectional_momentum import (
    calendar_split,
    formation_holding_grid,
    formation_signal,
    long_short_weights,
    month_end_rows,
    overlapping_quantile_returns,
    spread_summary,
    truncate_before_return_breaks,
    window_table,
    worst_months,
)
from quantlab.validation.bootstrap import (
    bootstrap_confidence_interval,
    bootstrap_statistic,
    optimal_block_size,
)
from quantlab.validation.dsr import deflated_sharpe_ratio, probabilistic_sharpe_ratio
from quantlab.validation.multiple_testing import required_tstat
from quantlab.validation.pbo import probability_of_backtest_overfitting
from quantlab.validation.robustness import (
    cost_multiplier_analysis,
    execution_delay_analysis,
    subperiod_performance,
)

LOG = get_logger("studies.002")

STUDY_DIR = Path(__file__).resolve().parent
RESULTS = STUDY_DIR / "results"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"

MONTHLY = Frequency.MONTHLY

#: Le jeu de déciles de momentum de Kenneth French, construit sur CRSP.
FRENCH_DECILES = "10_Portfolios_Prior_12_2"
#: Le croisement taille sur momentum, qui donne le contrôle à grande capitalisation.
FRENCH_SIZE_MOMENTUM = "25_Portfolios_ME_Prior_12_2"
#: L'identifiant du cache de prix quotidiens dans le lac de données.
LAKE_DATASET = "study002_sp500_daily"

#: Les seize cellules du panneau A de la table I, page 69, écart achat moins vente.
ARTICLE_PANEL_A = {
    (3, 3): (0.0032, 1.10),
    (3, 6): (0.0058, 2.29),
    (3, 9): (0.0061, 2.69),
    (3, 12): (0.0069, 3.53),
    (6, 3): (0.0084, 2.44),
    (6, 6): (0.0095, 3.07),
    (6, 9): (0.0102, 3.76),
    (6, 12): (0.0086, 3.36),
    (9, 3): (0.0109, 3.03),
    (9, 6): (0.0121, 3.78),
    (9, 9): (0.0105, 3.47),
    (9, 12): (0.0082, 2.89),
    (12, 3): (0.0131, 3.74),
    (12, 6): (0.0114, 3.40),
    (12, 9): (0.0093, 2.95),
    (12, 12): (0.0068, 2.25),
}
#: Les seize cellules du panneau B, décalage d'une semaine, même table.
ARTICLE_PANEL_B = {
    (3, 3): (0.0073, 2.61),
    (3, 6): (0.0078, 3.16),
    (3, 9): (0.0074, 3.36),
    (3, 12): (0.0077, 4.00),
    (6, 3): (0.0114, 3.37),
    (6, 6): (0.0110, 3.61),
    (6, 9): (0.0108, 4.01),
    (6, 12): (0.0090, 3.54),
    (9, 3): (0.0135, 3.85),
    (9, 6): (0.0130, 4.09),
    (9, 9): (0.0109, 3.67),
    (9, 12): (0.0085, 3.04),
    (12, 3): (0.0149, 4.28),
    (12, 6): (0.0121, 3.65),
    (12, 9): (0.0096, 3.09),
    (12, 12): (0.0069, 2.31),
}
#: Les cinq sous-périodes publiées pour la stratégie 6 sur 6, en pourcentage par mois.
ARTICLE_SUBPERIODS = {
    "1965-1969": 1.23,
    "1970-1974": 1.09,
    "1975-1979": -0.44,
    "1980-1984": 1.27,
    "1985-1989": 1.62,
}
#: Le nom des deux panneaux, employé comme clé partout dans le script.
PANEL_A, PANEL_B = "sans_decalage", "decalage_une_semaine"


# --------------------------------------------------------------------------- #
# Les données
# --------------------------------------------------------------------------- #


def charger_french() -> dict[str, pd.DataFrame]:
    """Télécharge les portefeuilles et les facteurs de Kenneth French."""
    with stage("french"):
        provider = FrenchProvider()
        deciles = provider.parse(FRENCH_DECILES)
        croise = provider.parse(FRENCH_SIZE_MOMENTUM)
        return {
            "deciles_vw": deciles.block("value_weight_returns_monthly").frame,
            "deciles_ew": deciles.block("average_equal_weighted_returns_monthly").frame,
            "n_firms": deciles.block("number_of_firms_in_portfolios").frame,
            "firm_size": deciles.block("average_firm_size").frame,
            "taille_vw": croise.block("average_value_weighted_returns_monthly").frame,
            "taille_ew": croise.block("average_equal_weighted_returns_monthly").frame,
            "facteurs": provider.benchmark_factors(MONTHLY),
        }


def charger_prix(config: ExperimentConfig, *, refresh: bool) -> pd.DataFrame:
    """Télécharge les prix quotidiens de l'univers, ou les relit dans le lac."""
    from quantlab.data.lake import read_table, table_exists, write_table

    if not refresh and table_exists(LAKE_DATASET, "bronze"):
        with stage("prix_lac"):
            brut = read_table(LAKE_DATASET, "bronze", engine="pandas")
            return to_wide(brut, config.data.price_field).sort_index()
    with stage("prix_yahoo", n_symbols=len(config.data.universe)):
        provider = YahooProvider(on_missing="drop", threads=True)
        morceaux = []
        taille = 60
        for depart in range(0, len(config.data.universe), taille):
            lot = config.data.universe[depart : depart + taille]
            morceaux.append(provider.fetch(lot, start=config.data.start, end=config.data.end))
        brut = pd.concat(morceaux, ignore_index=True)
        write_table(brut, LAKE_DATASET, "bronze", overwrite=True, notes="étude 002, jambe B")
        return to_wide(brut, config.data.price_field).sort_index()


# --------------------------------------------------------------------------- #
# La jambe A, sans biais de survie
# --------------------------------------------------------------------------- #


def _profil_de_deciles(frame: pd.DataFrame, debut: str, fin: str, etiquette: str) -> pd.DataFrame:
    """Rend le rendement moyen et le t de chaque décile sur une fenêtre."""
    tranche = frame.loc[debut:fin].dropna(how="all")
    lignes = []
    for rang, colonne in enumerate(tranche.columns, start=1):
        serie = tranche[colonne].dropna()
        resume = spread_summary(serie, frequency=MONTHLY)
        lignes.append(
            {
                "source": etiquette,
                "decile": rang,
                "portfolio": str(colonne),
                "mean_pct_per_month": resume["mean_pct_per_month"],
                "t_iid": resume["t_iid"],
                "sharpe_annualized": resume["sharpe_annualized"],
                "n_periods": resume["n_periods"],
            }
        )
    return pd.DataFrame(lignes)


def jambe_a(config: ExperimentConfig, french: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Mesure le momentum sur les déciles de Kenneth French, titres radiés compris."""
    params = config.params
    fenetres = {nom: (a, b) for nom, (a, b) in params["windows"].items()}
    facteurs = french["facteurs"]
    sortie: dict[str, Any] = {"tables": {}}

    ecarts = {}
    fenetres_lignes = []
    for etiquette, cle in (("value_weighted", "deciles_vw"), ("equal_weighted", "deciles_ew")):
        frame = french[cle]
        ecart = (frame.iloc[:, -1] - frame.iloc[:, 0]).rename("WML")
        ecarts[etiquette] = ecart
        table = window_table(ecart, fenetres, frequency=MONTHLY)
        table.insert(0, "weighting", etiquette)
        fenetres_lignes.append(table)
    sortie["ecarts"] = ecarts
    sortie["tables"]["jambe_a_fenetres"] = pd.concat(fenetres_lignes, ignore_index=True)

    profils = []
    for etiquette, cle in (("value_weighted", "deciles_vw"), ("equal_weighted", "deciles_ew")):
        for nom, (a, b) in fenetres.items():
            morceau = _profil_de_deciles(french[cle], a, b, f"{etiquette} {nom}")
            morceau.insert(0, "window", nom)
            morceau.insert(0, "weighting", etiquette)
            profils.append(morceau)
    sortie["tables"]["jambe_a_deciles"] = pd.concat(profils, ignore_index=True)

    pires = []
    for etiquette, serie in ecarts.items():
        morceau = worst_months(serie, count=int(params["n_worst_months"]))
        morceau.insert(0, "weighting", etiquette)
        pires.append(morceau)
    sortie["tables"]["jambe_a_pires_mois"] = pd.concat(pires, ignore_index=True)

    janviers = []
    for etiquette, serie in ecarts.items():
        for nom, (a, b) in fenetres.items():
            morceau = calendar_split(serie.loc[a:b], month=int(params["seasonal_month"]), frequency=MONTHLY)
            morceau.insert(0, "window", nom)
            morceau.insert(0, "weighting", etiquette)
            janviers.append(morceau)
    sortie["tables"]["jambe_a_janvier"] = pd.concat(janviers, ignore_index=True)

    lignes = []
    for nom, (a, b) in params["article_subperiods"].items():
        for etiquette, serie in ecarts.items():
            resume = spread_summary(serie.loc[a:b], frequency=MONTHLY)
            lignes.append(
                {
                    "subperiod": nom,
                    "weighting": etiquette,
                    "published_pct_per_month": ARTICLE_SUBPERIODS[nom],
                    "ours_pct_per_month": resume["mean_pct_per_month"],
                    "gap_pp_per_month": resume["mean_pct_per_month"] - ARTICLE_SUBPERIODS[nom],
                    "t_iid": resume["t_iid"],
                    "n_periods": resume["n_periods"],
                }
            )
    sortie["tables"]["jambe_a_sous_periodes_article"] = pd.DataFrame(lignes)

    colonnes = ["MKT-RF", "SMB", "HML", "RMW", "CMA", "MOM"]
    attributions = []
    for etiquette, serie in ecarts.items():
        for nom, (a, b) in fenetres.items():
            bloc = facteurs.loc[a:b, colonnes].dropna()
            cible = serie.loc[a:b].dropna()
            commun = bloc.index.intersection(cible.index)
            if len(commun) < 36:
                continue
            resultat = factor_regression(
                cible.loc[commun], bloc.loc[commun], cov_type="HAC", frequency=MONTHLY
            )
            attributions.append(
                {
                    "weighting": etiquette,
                    "window": nom,
                    "n_periods": int(resultat.n_obs),
                    # « alpha_annualized » est un BOOLÉEN qui dit si « alpha » est
                    # annualisé, et non la valeur annualisée. L'annualisation étant
                    # demandée, la valeur voulue est « alpha ».
                    "alpha_annualized_pct": float(resultat.alpha) * 100.0,
                    "alpha_stderr_annualized_pct": float(resultat.alpha_stderr) * 100.0,
                    "alpha_tstat_hac": float(resultat.alpha_tstat),
                    "alpha_pvalue": float(resultat.alpha_pvalue),
                    **{f"beta_{c}": float(resultat.betas[c]) for c in colonnes},
                    **{f"t_{c}": float(resultat.beta_tstats[c]) for c in colonnes},
                    "r_squared": float(resultat.r_squared),
                }
            )
    sortie["tables"]["jambe_a_attribution"] = pd.DataFrame(attributions)

    betas = []
    a, b = fenetres["echantillon_de_l_article"]
    sans_risque = facteurs.loc[a:b, "RF"]
    marche = facteurs.loc[a:b, "MKT-RF"]
    for etiquette, cle in (("value_weighted", "deciles_vw"), ("equal_weighted", "deciles_ew")):
        frame = french[cle].loc[a:b]
        perdant = beta(frame.iloc[:, 0] - sans_risque, marche)
        gagnant = beta(frame.iloc[:, -1] - sans_risque, marche)
        betas.append(
            {
                "weighting": etiquette,
                "window": "echantillon_de_l_article",
                "beta_loser": perdant,
                "beta_winner": gagnant,
                "beta_spread": gagnant - perdant,
            }
        )
    sortie["tables"]["jambe_a_betas"] = pd.DataFrame(betas)

    ruptures = []
    for etiquette, serie in ecarts.items():
        avant = serie.loc[fenetres["echantillon_de_l_article"][0] : fenetres["echantillon_de_l_article"][1]]
        apres = serie.loc[fenetres["apres_publication"][0] : fenetres["apres_publication"][1]]
        empile = pd.concat([avant, apres]).dropna()
        indicatrice = pd.DataFrame(
            {"apres_publication": (empile.index >= pd.Timestamp(apres.index.min())).astype(float)},
            index=empile.index,
        )
        resultat = factor_regression(
            empile, indicatrice, cov_type="HAC", annualize_alpha=False, frequency=MONTHLY
        )
        ruptures.append(
            {
                "weighting": etiquette,
                "n_periods": int(resultat.n_obs),
                "mean_before_pct": float(resultat.alpha) * 100.0,
                "drop_pp_per_month": float(resultat.betas["apres_publication"]) * 100.0,
                "drop_tstat_hac": float(resultat.beta_tstats["apres_publication"]),
                "drop_pvalue": float(resultat.beta_pvalues["apres_publication"]),
            }
        )
    sortie["tables"]["jambe_a_rupture"] = pd.DataFrame(ruptures)

    controles = []
    for etiquette, cle in (("value_weighted", "taille_vw"), ("equal_weighted", "taille_ew")):
        frame = french[cle]
        for taille, gagnant, perdant in (
            ("grandes_capitalisations", "BIG HIPRIOR", "BIG LOPRIOR"),
            ("petites_capitalisations", "SMALL HIPRIOR", "SMALL LOPRIOR"),
        ):
            serie = (frame[gagnant] - frame[perdant]).rename("WML")
            table = window_table(serie, fenetres, frequency=MONTHLY)
            table.insert(0, "size_bucket", taille)
            table.insert(0, "weighting", etiquette)
            controles.append(table)
            sortie[f"controle_{etiquette}_{taille}"] = serie
    sortie["tables"]["jambe_a_controle_taille"] = pd.concat(controles, ignore_index=True)

    sortie["n_firms"] = french["n_firms"]
    return sortie


# --------------------------------------------------------------------------- #
# La jambe B, avec biais de survie
# --------------------------------------------------------------------------- #


def jambe_b(config: ExperimentConfig, prix: pd.DataFrame) -> dict[str, Any]:
    """Refait le tri sur les membres ACTUELS du S&P 500, biais de survie compris."""
    params = config.params
    debut = params["leg_b_start"]
    fin = config.data.end
    fins_de_mois_brutes = month_end_rows(prix)
    classement_b = month_end_rows(prix, offset_days=int(params["skip_sessions_panel_b"]))
    fins_de_mois, ruptures = truncate_before_return_breaks(
        fins_de_mois_brutes, threshold=float(params["max_abs_monthly_return"])
    )
    # Le panneau à décalage doit porter exactement les mêmes titres aux mêmes dates,
    # sans quoi les deux panneaux ne classeraient pas le même univers.
    classement_b = classement_b.where(fins_de_mois.notna())
    rendements = fins_de_mois.pct_change()
    sortie: dict[str, Any] = {"tables": {}, "prix_mensuels": fins_de_mois, "rendements": rendements}
    sortie["tables"]["jambe_b_ruptures_de_prix"] = ruptures

    with stage("grille_jambe_b"):
        grille, series = formation_holding_grid(
            {PANEL_A: fins_de_mois, PANEL_B: classement_b},
            fins_de_mois,
            rendements,
            formations=[int(j) for j in params["formation_months"]],
            holdings=[int(k) for k in params["holding_months"]],
            n_quantiles=int(params["n_quantiles"]),
            weighting="equal",
            min_names=int(params["min_names"]),
            frequency=MONTHLY,
            start=debut,
            end=fin,
        )
    grille["published_pct_per_month"] = [
        (ARTICLE_PANEL_A if p == PANEL_A else ARTICLE_PANEL_B)[(j, k)][0] * 100.0
        for p, j, k in zip(grille["panel"], grille["formation_months"], grille["holding_months"], strict=True)
    ]
    grille["published_t"] = [
        (ARTICLE_PANEL_A if p == PANEL_A else ARTICLE_PANEL_B)[(j, k)][1]
        for p, j, k in zip(grille["panel"], grille["formation_months"], grille["holding_months"], strict=True)
    ]
    grille["gap_pp_per_month"] = grille["mean_pct_per_month"] - grille["published_pct_per_month"]
    sortie["tables"]["jambe_b_grille"] = grille
    sortie["series_grille"] = series

    # La grille ne se juge pas cellule par cellule, son NIVEAU dépendant de la
    # période. Sa FORME se compare : les cellules que l'article classe le mieux
    # sont-elles celles que nous classons le mieux, et le décalage d'une semaine
    # aide-t-il comme il aide chez lui ?
    avec = grille.loc[grille["panel"] == PANEL_B].set_index(["formation_months", "holding_months"])
    sans = grille.loc[grille["panel"] == PANEL_A].set_index(["formation_months", "holding_months"])
    sortie["forme_de_la_grille"] = {
        "spearman_vs_article": float(
            grille["mean_pct_per_month"].corr(grille["published_pct_per_month"], method="spearman")
        ),
        "n_cells_positive": int((grille["mean_pct_per_month"] > 0.0).sum()),
        "n_cells": len(grille),
        "n_cells_significant_iid": int((grille["t_iid"].abs() > 1.96).sum()),
        "n_cells_skip_better": int(
            (avec["mean_pct_per_month"] > sans["mean_pct_per_month"].reindex(avec.index)).sum()
        ),
        "n_cells_compared": len(avec),
        "best_cell": _nom_de_cellule(grille.loc[grille["mean_pct_per_month"].idxmax()]),
        "best_cell_pct_per_month": float(grille["mean_pct_per_month"].max()),
        "article_best_cell": "decalage_une_semaine_J12_K3",
    }

    signal = formation_signal(
        fins_de_mois.shift(int(params["comparison_skip_months"])),
        fins_de_mois,
        lookback=int(params["comparison_formation_months"]),
    )
    sortie["signal_comparaison"] = signal
    comparaisons = {}
    for nom, n_paquets in (
        ("deciles", int(params["n_quantiles"])),
        ("quintiles", int(params["n_quantiles_coarse"])),
    ):
        table = overlapping_quantile_returns(
            signal,
            rendements,
            holding=int(params["comparison_holding_months"]),
            n_quantiles=n_paquets,
            weighting="equal",
            min_names=int(params["min_names"]),
        )
        comparaisons[nom] = table.loc[debut:fin]
    sortie["comparaisons"] = comparaisons

    profils = []
    for nom, table in comparaisons.items():
        colonnes = [c for c in table.columns if c != "spread"]
        for rang, colonne in enumerate(colonnes, start=1):
            resume = spread_summary(table[colonne].dropna(), frequency=MONTHLY)
            profils.append(
                {
                    "buckets": nom,
                    "bucket": rang,
                    "portfolio": colonne,
                    "mean_pct_per_month": resume["mean_pct_per_month"],
                    "t_iid": resume["t_iid"],
                    "sharpe_annualized": resume["sharpe_annualized"],
                    "n_periods": resume["n_periods"],
                }
            )
    sortie["tables"]["jambe_b_paquets"] = pd.DataFrame(profils)

    sortie["nettoyage"] = _effet_du_nettoyage(
        params, fins_de_mois_brutes, comparaisons["deciles"]["spread"], debut, fin
    )

    disponibilite = prix.notna().idxmax()
    jamais = prix.notna().sum() == 0
    sortie["tables"]["univers_jambe_b"] = pd.DataFrame(
        {
            "symbol": prix.columns,
            "first_price_date": [
                "non trouvé" if jamais[c] else str(pd.Timestamp(disponibilite[c]).date())
                for c in prix.columns
            ],
            "n_sessions": prix.notna().sum().to_numpy(),
        }
    )
    sortie["noms_par_mois"] = fins_de_mois.notna().sum(axis="columns")
    return sortie


def _effet_du_nettoyage(
    params: dict[str, Any],
    prix_bruts: pd.DataFrame,
    ecart_propre: pd.Series,
    debut: str,
    fin: str,
) -> dict[str, Any]:
    """Chiffre ce que la coupe des ruptures de prix change, et le plus fort mouvement réel.

    Le README cite trois nombres sur ce sujet. Ils sont calculés ici plutôt que
    narrés, pour que chacun vienne d'un fichier de ``results/``.
    """
    rendements = prix_bruts.pct_change()
    signal = formation_signal(
        prix_bruts.shift(int(params["comparison_skip_months"])),
        prix_bruts,
        lookback=int(params["comparison_formation_months"]),
    )
    sale = (
        overlapping_quantile_returns(
            signal,
            rendements,
            holding=int(params["comparison_holding_months"]),
            n_quantiles=int(params["n_quantiles"]),
            weighting="equal",
            min_names=int(params["min_names"]),
        )["spread"]
        .loc[debut:fin]
        .dropna()
    )
    propre = ecart_propre.dropna()
    seuil = float(params["max_abs_monthly_return"])
    # La plus forte hausse mensuelle qui reste SOUS le seuil, donc le plus fort
    # mouvement que la règle de coupe tient pour réel. Elle borne le seuil par le
    # bas : au-dessous d'elle, la coupe retirerait un mouvement légitime.
    sous_le_seuil = rendements.where(rendements <= seuil).to_numpy(dtype=float)
    ligne, colonne = divmod(int(np.nanargmax(sous_le_seuil)), sous_le_seuil.shape[1])
    date_reelle = rendements.index[ligne]
    symbole_reel = rendements.columns[colonne]
    hausse_reelle = float(sous_le_seuil[ligne, colonne])
    pire = sale.idxmin()
    return {
        "spread_without_cleaning_pct_per_month": float(sale.mean()) * 100.0,
        "spread_with_cleaning_pct_per_month": float(propre.mean()) * 100.0,
        "worst_month_without_cleaning_date": str(pd.Timestamp(pire).date()),
        "worst_month_without_cleaning_pct": float(sale.min()) * 100.0,
        "n_months_without_cleaning": int(sale.size),
        "largest_true_monthly_return_symbol": str(symbole_reel),
        "largest_true_monthly_return_date": str(pd.Timestamp(date_reelle).date()),
        "largest_true_monthly_return_pct": hausse_reelle * 100.0,
        "threshold_pct": seuil * 100.0,
    }


def couts_jambe_b(config: ExperimentConfig, contenu: dict[str, Any]) -> dict[str, Any]:
    """Passe la configuration de comparaison au moteur de backtest, avec ses frais."""
    params = config.params
    rendements = contenu["rendements"]
    poids = long_short_weights(
        contenu["signal_comparaison"],
        holding=int(params["comparison_holding_months"]),
        n_quantiles=int(params["n_quantiles"]),
        min_names=int(params["min_names"]),
        target_gross=float(params["backtest_gross_exposure"]),
    )
    debut = params["leg_b_start"]
    poids = poids.loc[debut:]
    poids = poids.loc[poids.abs().sum(axis="columns") > 0.0]
    rendements_propres = rendements.reindex(index=poids.index.union(rendements.index))
    # Une position ouverte à la date t encaisse le rendement de t plus un. Compter
    # les positions dont ce rendement manque dit combien de fois le moteur reçoit
    # un zéro à la place d'une donnée. La DERNIÈRE date n'a jamais de suivante, et
    # elle est donc comptée à part plutôt que confondue avec un trou de données.
    tenus = poids.abs() > 0.0
    suivants_absents = tenus & rendements.reindex(poids.index).shift(-1).isna()
    manquants = int(suivants_absents.iloc[:-1].to_numpy().sum())
    manquants_derniere_date = int(suivants_absents.iloc[-1].to_numpy().sum())
    modele = from_config(config.costs, frequency=MONTHLY)
    resultat = run_backtest(
        weights=poids,
        returns=rendements_propres.loc[poids.index[0] :].fillna(0.0),
        cost_model=modele,
        execution_lag=1,
        frequency=MONTHLY,
    )
    rotation_pleine = turnover_series(
        resultat.executed_weights,
        rendements_propres.loc[poids.index[0] :].fillna(0.0),
        convention="full_sum",
    )
    seuil = breakeven_cost_bps(resultat.gross_returns, rotation_pleine, MONTHLY)
    # Contrôle interne : l'exposition brute vaut un, donc le rendement du moteur
    # est la MOITIÉ de l'écart publié par le tri. Un écart au-dessus de la
    # précision machine signalerait un décalage compté deux fois, ou un
    # découpage en paquets qui diffère entre les poids et les rendements.
    reconstruit = resultat.gross_returns * (
        float(params["spread_gross_exposure"]) / float(params["backtest_gross_exposure"])
    )
    publie = contenu["comparaisons"]["deciles"]["spread"].dropna()
    commun = reconstruit.index.intersection(publie.index)
    ecarts = (reconstruit.loc[commun] - publie.loc[commun]).abs()
    ecart_maximal = float(ecarts.max())
    n_desaccords = int((ecarts > 1e-10).sum())
    LOG.info(
        "concordance des poids et des rendements",
        extra={
            "n_periods": len(commun),
            "max_abs_gap": ecart_maximal,
            "n_disagreeing_dates": n_desaccords,
        },
    )
    return {
        "resultat": resultat,
        "poids": poids,
        "turnover_full": rotation_pleine,
        "breakeven_bps": seuil,
        "n_returns_missing_on_held": manquants,
        "n_positions_on_last_date": manquants_derniere_date,
        "weights_vs_returns_max_gap": ecart_maximal,
        "weights_vs_returns_n_periods": len(commun),
        "weights_vs_returns_n_disagreeing": n_desaccords,
    }


# --------------------------------------------------------------------------- #
# La confrontation des deux jambes
# --------------------------------------------------------------------------- #


def _par_mois(serie: pd.Series) -> pd.Series:
    """Redate une série mensuelle sur le premier jour de son mois.

    Les deux jambes ne portent pas la même date de fin de mois, l'une celle du
    calendrier et l'autre celle de la dernière séance. Ramener les deux au
    premier jour du mois les rend comparables sans perdre d'observation.
    """
    redatee = serie.copy()
    redatee.index = pd.PeriodIndex(pd.DatetimeIndex(serie.index), freq="M").to_timestamp()
    return redatee


def confrontation(
    config: ExperimentConfig, contenu_a: dict[str, Any], contenu_b: dict[str, Any]
) -> dict[str, Any]:
    """Chiffre l'écart entre l'univers sans radiés et l'univers des seuls survivants."""
    params = config.params
    debut = params["leg_b_start"]
    fin_commune = str(pd.Timestamp(contenu_a["ecarts"]["value_weighted"].index.max()).date())

    candidats = {
        "jambe_A_deciles_tous_titres_pondere": contenu_a["ecarts"]["value_weighted"],
        "jambe_A_deciles_tous_titres_equipondere": contenu_a["ecarts"]["equal_weighted"],
        "jambe_A_quintiles_grandes_capitalisations_equipondere": contenu_a[
            "controle_equal_weighted_grandes_capitalisations"
        ],
        "jambe_A_quintiles_grandes_capitalisations_pondere": contenu_a[
            "controle_value_weighted_grandes_capitalisations"
        ],
        "jambe_B_deciles_survivants_equipondere": contenu_b["comparaisons"]["deciles"]["spread"],
        "jambe_B_quintiles_survivants_equipondere": contenu_b["comparaisons"]["quintiles"]["spread"],
    }
    # Les deux jambes ne datent pas leurs mois de la même façon. Kenneth French
    # pose le dernier jour du CALENDRIER, Yahoo la dernière SÉANCE, et mars 1991
    # tombe donc le 31 chez l'un et le 28 chez l'autre. Une intersection de dates
    # brutes perdrait un mois sur trois sans rien signaler. L'appariement se fait
    # donc sur le mois, et le nombre de mois communs est publié.
    series = {
        nom: s.loc[debut:fin_commune].dropna().rename_axis("date").pipe(_par_mois)
        for nom, s in candidats.items()
    }
    commun = None
    for serie in series.values():
        commun = serie.index if commun is None else commun.intersection(serie.index)
    series = {nom: s.loc[commun] for nom, s in series.items()}

    lignes = []
    for nom, serie in series.items():
        resume = spread_summary(serie, frequency=MONTHLY)
        lignes.append({"series": nom, **resume})
    table = pd.DataFrame(lignes)

    paires = (
        (
            "deciles_tous_titres_equipondere_moins_survivants",
            "jambe_A_deciles_tous_titres_equipondere",
            "jambe_B_deciles_survivants_equipondere",
        ),
        (
            "quintiles_grandes_capitalisations_moins_survivants",
            "jambe_A_quintiles_grandes_capitalisations_equipondere",
            "jambe_B_quintiles_survivants_equipondere",
        ),
        (
            "deciles_tous_titres_pondere_moins_survivants",
            "jambe_A_deciles_tous_titres_pondere",
            "jambe_B_deciles_survivants_equipondere",
        ),
    )
    ecarts = []
    for nom, gauche, droite in paires:
        difference = (series[gauche] - series[droite]).dropna()
        resume = spread_summary(difference, frequency=MONTHLY)
        ecarts.append(
            {
                "comparison": nom,
                "reference": gauche,
                "biased": droite,
                "gap_pp_per_month": resume["mean_pct_per_month"],
                "gap_pp_per_year": resume["mean_annualized_pct"],
                "t_hac": resume["t_hac"],
                "t_iid": resume["t_iid"],
                "n_periods": resume["n_periods"],
            }
        )
    return {
        "series": series,
        "tables": {
            "biais_de_survie_niveaux": table,
            "biais_de_survie_ecarts": pd.DataFrame(ecarts),
        },
        "fenetre": (str(commun.min()), str(commun.max())),
        "n_mois_communs": len(commun),
    }


# --------------------------------------------------------------------------- #
# La validation
# --------------------------------------------------------------------------- #


def validation(
    config: ExperimentConfig,
    contenu_a: dict[str, Any],
    contenu_b: dict[str, Any],
    couts: dict[str, Any],
) -> dict[str, Any]:
    """Applique les contrôles de surapprentissage, de coûts et de sous-périodes."""
    params = config.params
    generateur = make_generator(config.seed)
    fenetres = params["windows"]
    reference = contenu_a["ecarts"]["value_weighted"]
    apres = reference.loc[fenetres["apres_publication"][0] : fenetres["apres_publication"][1]].dropna()
    sortie: dict[str, Any] = {"tables": {}}

    essais = []
    for _, ligne in contenu_b["tables"]["jambe_b_grille"].iterrows():
        essais.append(
            {
                "family": "grille_jambe_b",
                "trial": _nom_de_cellule(ligne),
                "sharpe_annualized": float(ligne["sharpe_annualized"]),
            }
        )
    for nom, table in contenu_b["comparaisons"].items():
        resume = spread_summary(table["spread"].dropna(), frequency=MONTHLY)
        essais.append(
            {
                "family": "comparaison_jambe_b",
                "trial": nom,
                "sharpe_annualized": resume["sharpe_annualized"],
            }
        )
    for nom, serie in contenu_a["ecarts"].items():
        resume = spread_summary(
            serie.loc[fenetres["apres_publication"][0] : fenetres["apres_publication"][1]],
            frequency=MONTHLY,
        )
        essais.append(
            {"family": "jambe_a", "trial": f"deciles_{nom}", "sharpe_annualized": resume["sharpe_annualized"]}
        )
    for cle, serie in contenu_a.items():
        if not str(cle).startswith("controle_"):
            continue
        resume = spread_summary(
            serie.loc[fenetres["apres_publication"][0] : fenetres["apres_publication"][1]],
            frequency=MONTHLY,
        )
        essais.append(
            {
                "family": "jambe_a_controle",
                "trial": str(cle),
                "sharpe_annualized": resume["sharpe_annualized"],
            }
        )
    # Le délai d'exécution se teste sur la jambe B, la seule des deux qui porte des
    # POIDS. Décaler la jambe A est impossible : Kenneth French publie des
    # rendements de déciles déjà agrégés, dont le signal n'existe plus. Décaler
    # cette série de rendements ne retarderait aucune exécution, elle ferait
    # seulement glisser la fenêtre de mesure, et le nombre rendu ne dirait rien.
    poids_b = couts["poids"]
    rendements_b = (
        contenu_b["rendements"]
        .reindex(index=poids_b.index.union(contenu_b["rendements"].index))
        .loc[poids_b.index[0] :]
        .fillna(0.0)
    )

    def evaluer_delais(delai: int) -> float:
        """Rend le Sharpe de la jambe B quand le moteur exécute « delai » mois plus tard."""
        execute = run_backtest(
            weights=poids_b,
            returns=rendements_b,
            execution_lag=int(delai),
            frequency=MONTHLY,
        )
        return float(spread_summary(execute.gross_returns, frequency=MONTHLY)["sharpe_annualized"])

    sortie["tables"]["robustesse_delais"] = execution_delay_analysis(
        evaluer_delais, [int(d) for d in params["execution_delays"]]
    )

    # Chaque cellule du balayage de délai est un essai de plus, règle 8.
    for _, ligne in sortie["tables"]["robustesse_delais"].iterrows():
        essais.append(
            {
                "family": "delai_jambe_b",
                "trial": f"execution_lag_{int(ligne['delay'])}",
                "sharpe_annualized": float(ligne["metric"]),
            }
        )
    table_essais = pd.DataFrame(essais)
    sortie["tables"]["validation_essais"] = table_essais

    resume_apres = spread_summary(apres, frequency=MONTHLY)
    observe = float(resume_apres["sharpe_annualized"])
    variance = float(table_essais["sharpe_annualized"].var(ddof=1))
    moyenne = float(table_essais["sharpe_annualized"].mean())
    n_essais = int(params["n_trials"])
    asymetrie = float(skewness(apres))
    aplatissement = float(kurtosis(apres, excess=False))
    dsr = deflated_sharpe_ratio(
        observed_sr=observe,
        sharpe_variance_across_trials=variance,
        n_trials=n_essais,
        n_obs=float(len(apres)),
        skew=asymetrie,
        kurtosis=aplatissement,
        mean_sharpe_across_trials=moyenne,
    )
    psr = probabilistic_sharpe_ratio(
        observed_sr=observe,
        benchmark_sr=0.0,
        n_obs=float(len(apres)),
        skew=asymetrie,
        kurtosis=aplatissement,
    )
    sortie["dsr"] = {
        "observed_sharpe_oos": observe,
        "n_trials": n_essais,
        "n_trials_with_sharpe": len(table_essais),
        "sharpe_variance_across_trials": variance,
        "mean_sharpe_across_trials": moyenne,
        "skew": asymetrie,
        "kurtosis": aplatissement,
        "deflated_sharpe": float(dsr),
        "probabilistic_sharpe_vs_zero": float(psr),
        "required_tstat_bonferroni": float(required_tstat(n_essais)),
        "harvey_liu_zhu_threshold": float(params["harvey_liu_zhu_threshold"]),
    }

    matrice = pd.DataFrame(contenu_b["series_grille"]).dropna()
    pbo = probability_of_backtest_overfitting(matrice, n_splits=int(params["cscv_splits"]), frequency=MONTHLY)
    sortie["pbo"] = {
        "pbo": float(pbo.pbo),
        "n_partitions": int(pbo.n_partitions),
        "median_relative_rank": float(pbo.median_relative_rank),
        "n_configurations": int(matrice.shape[1]),
        "n_observations": int(matrice.shape[0]),
    }

    sous_periodes = subperiod_performance(
        apres, n_periods=6, frequency=MONTHLY, error_method="lo", min_observations=12
    )
    sortie["tables"]["robustesse_sous_periodes"] = sous_periodes
    part_positive = float((sous_periodes["sharpe"] > 0.0).mean())
    sortie["positive_subperiod_share"] = part_positive

    rotation = couts["turnover_full"]
    commune = apres.index.intersection(rotation.index)
    rotation_transferee = rotation.reindex(commune)
    # L'écart des déciles achète un dollar et en vend un, donc son exposition brute
    # vaut deux, quand la rotation empruntée à la jambe B est celle d'un
    # portefeuille d'exposition brute un. Le seuil de rentabilité est le rapport
    # d'un rendement à une rotation : laisser les deux à des expositions
    # différentes le doublerait, sans qu'aucun contrôle de forme le signale.
    echelle = float(params["backtest_gross_exposure"]) / float(params["spread_gross_exposure"])
    brut_transfere = apres.reindex(commune) * echelle
    cout_de_base = float(config.costs.spread_bps + config.costs.commission_bps) / 1e4

    def evaluer_couts(multiplicateur: float) -> float:
        """Rend le ratio de Sharpe net au multiple de coûts demandé."""
        net = brut_transfere - multiplicateur * cout_de_base * rotation_transferee
        return float(spread_summary(net.dropna(), frequency=MONTHLY)["sharpe_annualized"])

    analyse = cost_multiplier_analysis(
        evaluer_couts, [float(m) for m in params["cost_multipliers"]], threshold=0.0
    )
    sortie["tables"]["robustesse_couts"] = analyse.table
    sortie["cost_analysis"] = analyse
    sortie["breakeven_leg_a_bps"] = float(
        breakeven_cost_bps(brut_transfere.dropna(), rotation_transferee.dropna(), MONTHLY)
    )
    sortie["leg_a_turnover"] = {
        "full_sum_per_month": float(rotation_transferee.dropna().mean()),
        "full_sum_per_year": float(rotation_transferee.dropna().mean() * MONTHLY.periods_per_year),
        "n_periods": int(rotation_transferee.dropna().size),
        "cost_bps_per_side_assumed": float(cout_de_base * 1e4),
        "gross_exposure": float(params["backtest_gross_exposure"]),
        "spread_rescaled_by": echelle,
    }

    taille_bloc = float(optimal_block_size(apres.to_numpy(dtype=float)))
    # La règle de Politis et White tombe sur le plancher de un quand la série ne
    # porte aucune dépendance exploitable. Le rééchantillonnage par blocs n'aurait
    # alors plus de blocs, et le tirage indépendant est la forme correcte.
    par_blocs = taille_bloc > 1.0
    distribution = bootstrap_statistic(
        apres.to_numpy(dtype=float),
        lambda x: float(np.mean(x)),
        "stationary" if par_blocs else "iid",
        int(params["bootstrap_resamples"]),
        generateur,
        mean_block_size=taille_bloc if par_blocs else None,
    )
    intervalle = bootstrap_confidence_interval(distribution, 0.95, "percentile")
    sortie["bootstrap"] = {
        "method": "stationary" if par_blocs else "iid",
        "mean_pct_per_month": float(distribution.observed) * 100.0,
        "low_pct_per_month": float(intervalle.low) * 100.0,
        "high_pct_per_month": float(intervalle.high) * 100.0,
        "mean_block_size": taille_bloc,
        "n_resamples": int(params["bootstrap_resamples"]),
    }
    return sortie


# --------------------------------------------------------------------------- #
# Les figures
# --------------------------------------------------------------------------- #


def tracer(
    config: ExperimentConfig,
    contenu_a: dict[str, Any],
    contenu_b: dict[str, Any],
    face_a_face: dict[str, Any],
    controles: dict[str, Any],
) -> list[ReportFigure]:
    """Écrit les figures de l'étude et rend leur description pour le rapport."""
    figures: list[ReportFigure] = []

    def enregistrer(figure, nom: str, section: str, legende: str) -> None:
        chemins = fig.save_figure(figure, FIGURES / nom, vector=True)
        figures.append(ReportFigure(name=nom, section=section, path=chemins[0], caption=legende))

    reference = contenu_a["ecarts"]["value_weighted"]
    courbes = {
        "Échantillon de l'article, 1965-1989": reference.loc["1965":"1989"],
        "Après publication, 1994-2026": reference.loc["1994":"2026"],
    }
    figure, _ = fig.equity_curve(courbes, log_scale=True, currency="$ US", initial=1.0)
    enregistrer(
        figure,
        "jambe_a_richesse",
        "performance",
        "Richesse cumulée d'un dollar investi dans l'écart gagnant moins perdant, "
        "échelle logarithmique, deux fenêtres.",
    )

    table_deciles = contenu_a["deciles_article"]
    figure, _ = fig.quantile_bars(table_deciles, spread_column="spread")
    enregistrer(
        figure,
        "jambe_a_deciles_article",
        "performance",
        "Rendement moyen de chaque décile sur la fenêtre de l'article, 1965-1989.",
    )

    table_apres = contenu_a["deciles_apres"]
    figure, _ = fig.quantile_bars(table_apres, spread_column="spread")
    enregistrer(
        figure,
        "jambe_a_deciles_apres",
        "out_of_sample",
        "Rendement moyen de chaque décile après publication, 1994-2026.",
    )

    figure, _ = fig.quantile_bars(contenu_b["comparaisons"]["deciles"], spread_column="spread")
    enregistrer(
        figure,
        "jambe_b_deciles",
        "limitations",
        "Rendement moyen de chaque décile sur l'univers des seuls survivants.",
    )

    figure, _ = fig.underwater(reference.loc["1927":"2026"])
    enregistrer(
        figure,
        "jambe_a_krachs",
        "robustness",
        "Repli de l'écart gagnant moins perdant depuis son sommet, 1927 à 2026.",
    )

    grille = contenu_b["tables"]["jambe_b_grille"]
    panneau = grille.loc[grille["panel"] == PANEL_B].copy()
    figure, _ = fig.parameter_heatmap(
        panneau,
        x="holding_months",
        y="formation_months",
        metric="mean_pct_per_month",
        x_label="Détention K, en mois",
        y_label="Formation J, en mois",
        metric_label="Rendement moyen, en pourcentage par mois",
    )
    enregistrer(
        figure,
        "jambe_b_grille",
        "replication",
        "La grille J sur K refaite sur l'univers des survivants, panneau à décalage "
        "d'une semaine, 1991 à 2026.",
    )

    figure, _ = fig.subperiod_bars(controles["tables"]["robustesse_sous_periodes"])
    enregistrer(
        figure,
        "robustesse_sous_periodes",
        "robustness",
        "Ratio de Sharpe de la jambe A par sous-période après publication, avec son intervalle de confiance.",
    )

    analyse = controles["cost_analysis"]
    figure, _ = fig.cost_sensitivity(
        analyse.table["multiplier"].to_numpy(),
        analyse.table["metric"].to_numpy(),
        threshold=0.0,
    )
    enregistrer(
        figure,
        "sensibilite_aux_couts",
        "costs",
        "Ratio de Sharpe net de la jambe A quand les coûts sont multipliés.",
    )

    figure, _ = fig.rolling_metric(
        reference.loc["1930":"2026"], metric="sharpe", window=120, frequency=MONTHLY
    )
    enregistrer(
        figure,
        "sharpe_glissant",
        "out_of_sample",
        "Ratio de Sharpe glissant sur dix ans de l'écart gagnant moins perdant.",
    )

    correlations = pd.DataFrame(face_a_face["series"])
    figure, _ = fig.correlation_heatmap(correlations)
    enregistrer(
        figure,
        "correlations_des_jambes",
        "factor_attribution",
        "Corrélation des six écarts comparés sur leur fenêtre commune.",
    )
    return figures


# --------------------------------------------------------------------------- #
# L'assemblage
# --------------------------------------------------------------------------- #


def construire_controles(config: ExperimentConfig, contenu_a: dict[str, Any]) -> list[ReplicationCheck]:
    """Met les valeurs de l'article en face des nôtres, tolérance déclarée d'avance."""
    cibles = config.params["replication_targets"]
    fenetres = config.params["windows"]
    a, b = fenetres["echantillon_de_l_article"]
    ecart = contenu_a["ecarts"]["equal_weighted"].loc[a:b]
    resume = spread_summary(ecart, frequency=MONTHLY)
    saison = calendar_split(ecart, month=int(config.params["seasonal_month"]), frequency=MONTHLY)
    betas = contenu_a["tables"]["jambe_a_betas"]
    ligne_beta = betas.loc[betas["weighting"] == "equal_weighted"].iloc[0]

    mesures = {
        "ecart_mensuel": resume["mean_pct_per_month"] / 100.0,
        "t_de_l_ecart": resume["t_iid"],
        "beta_du_decile_perdant": float(ligne_beta["beta_loser"]),
        "beta_du_decile_gagnant": float(ligne_beta["beta_winner"]),
        "beta_de_l_ecart": float(ligne_beta["beta_spread"]),
        "rendement_de_janvier": float(saison.loc[0, "mean_pct_per_month"]) / 100.0,
        "t_de_janvier": float(saison.loc[0, "t_iid"]),
        "rendement_de_fevrier_a_decembre": float(saison.loc[1, "mean_pct_per_month"]) / 100.0,
        "t_de_fevrier_a_decembre": float(saison.loc[1, "t_iid"]),
        "part_de_mois_positifs": resume["hit_rate"],
        "part_de_mois_positifs_hors_janvier": float(saison.loc[1, "hit_rate"]),
    }
    return [
        ReplicationCheck(
            quantity=nom,
            published=float(cibles[nom]["published"]),
            ours=float(valeur),
            tolerance=float(cibles[nom]["tolerance"]),
            tolerance_kind=cibles[nom]["kind"],
            source=cibles[nom]["source"],
        )
        for nom, valeur in mesures.items()
    ]


def main() -> None:
    """Fait tourner l'étude en entier, de la donnée au rapport."""
    analyseur = argparse.ArgumentParser(description="Étude 002, momentum transversal.")
    analyseur.add_argument("--refresh", action="store_true", help="retélécharge les prix Yahoo")
    arguments = analyseur.parse_args()

    configure_logging()
    config = load_config(STUDY_DIR / "config.yaml", ExperimentConfig)
    TABLES.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    params = config.params
    fenetres = params["windows"]

    french = charger_french()
    prix = charger_prix(config, refresh=arguments.refresh)

    with stage("jambe_a"):
        contenu_a = jambe_a(config, french)
    signal_french = french["deciles_ew"]
    contenu_a["deciles_article"] = _table_de_deciles(signal_french, *fenetres["echantillon_de_l_article"])
    contenu_a["deciles_apres"] = _table_de_deciles(signal_french, *fenetres["apres_publication"])

    with stage("jambe_b"):
        contenu_b = jambe_b(config, prix)
    with stage("couts"):
        couts = couts_jambe_b(config, contenu_b)
    with stage("confrontation"):
        face_a_face = confrontation(config, contenu_a, contenu_b)
    with stage("validation"):
        controles = validation(config, contenu_a, contenu_b, couts)

    resultat = couts["resultat"]
    rendements_bruts = resultat.gross_returns
    rendements_nets = resultat.net_returns
    resume_brut = spread_summary(rendements_bruts, frequency=MONTHLY)
    resume_net = spread_summary(rendements_nets, frequency=MONTHLY)
    contenu_b["tables"]["jambe_b_couts"] = pd.DataFrame(
        [
            {
                "leg": "jambe_B_survivants",
                "gross_exposure": 1.0,
                "gross_pct_per_month": resume_brut["mean_pct_per_month"],
                "net_pct_per_month": resume_net["mean_pct_per_month"],
                "gross_sharpe": resume_brut["sharpe_annualized"],
                "net_sharpe": resume_net["sharpe_annualized"],
                "turnover_half_sum_per_month": float(resultat.turnover.mean()),
                "turnover_full_sum_per_month": float(couts["turnover_full"].mean()),
                "turnover_annualized": float(annualized_turnover(resultat.turnover, MONTHLY)),
                "breakeven_bps_per_unit_traded": couts["breakeven_bps"],
                "assumed_cost_bps_per_side": float(config.costs.spread_bps + config.costs.commission_bps),
                "max_drawdown_gross": float(max_drawdown(rendements_bruts)),
                "n_periods": resume_brut["n_periods"],
            }
        ]
    )

    tous_les_tableaux: dict[str, pd.DataFrame] = {}
    for bloc in (contenu_a["tables"], contenu_b["tables"], face_a_face["tables"], controles["tables"]):
        tous_les_tableaux.update(bloc)
    tous_les_tableaux["replication"] = replication_table(construire_controles(config, contenu_a))

    for nom, table in tous_les_tableaux.items():
        table.to_csv(TABLES / f"{nom}.csv", index=False)

    figures = tracer(config, contenu_a, contenu_b, face_a_face, controles)

    fenetres_a = contenu_a["tables"]["jambe_a_fenetres"]
    ligne = fenetres_a.loc[fenetres_a["weighting"] == "value_weighted"].set_index("window")
    ecarts_biais = face_a_face["tables"]["biais_de_survie_ecarts"].set_index("comparison")

    # Le portefeuille déjà détenu, ici, est le facteur de momentum de Carhart, que
    # Kenneth French publie et que n'importe qui peut acheter. La question du
    # quatrième critère est donc : notre écart apporte-t-il autre chose que lui ?
    ecart_apres = contenu_a["ecarts"]["value_weighted"].loc[
        fenetres["apres_publication"][0] : fenetres["apres_publication"][1]
    ]
    momentum_publie = french["facteurs"].loc[
        fenetres["apres_publication"][0] : fenetres["apres_publication"][1], "MOM"
    ]
    correlation = float(ecart_apres.corr(momentum_publie))

    metriques = {
        "jambe_a_ecart_echantillon_article_pct_par_mois": float(
            ligne.loc["echantillon_de_l_article", "mean_pct_per_month"]
        ),
        "jambe_a_t_echantillon_article": float(ligne.loc["echantillon_de_l_article", "t_iid"]),
        "jambe_a_sharpe_echantillon_article": float(
            ligne.loc["echantillon_de_l_article", "sharpe_annualized"]
        ),
        "jambe_a_ecart_apres_publication_pct_par_mois": float(
            ligne.loc["apres_publication", "mean_pct_per_month"]
        ),
        "jambe_a_t_apres_publication": float(ligne.loc["apres_publication", "t_iid"]),
        "jambe_a_sharpe_apres_publication": float(ligne.loc["apres_publication", "sharpe_annualized"]),
        "jambe_b_ecart_deciles_pct_par_mois": float(
            spread_summary(contenu_b["comparaisons"]["deciles"]["spread"].dropna(), frequency=MONTHLY)[
                "mean_pct_per_month"
            ]
        ),
        "biais_de_survie_pp_par_an": float(
            ecarts_biais.loc["deciles_tous_titres_equipondere_moins_survivants", "gap_pp_per_year"]
        ),
        "biais_de_survie_t_hac": float(
            ecarts_biais.loc["deciles_tous_titres_equipondere_moins_survivants", "t_hac"]
        ),
        "jambe_b_grille_spearman_contre_article": float(
            contenu_b["forme_de_la_grille"]["spearman_vs_article"]
        ),
        "jambe_b_seuil_de_rentabilite_bps": float(couts["breakeven_bps"]),
        "jambe_a_seuil_de_rentabilite_bps": float(controles["breakeven_leg_a_bps"]),
        "sharpe_deflate": float(controles["dsr"]["deflated_sharpe"]),
        "probabilite_de_surapprentissage": float(controles["pbo"]["pbo"]),
        "part_de_sous_periodes_positives": float(controles["positive_subperiod_share"]),
        "correlation_avec_le_momentum_publie": float(correlation),
    }
    etiquettes = {
        nom: (
            SampleTag.IN_SAMPLE if "echantillon_article" in nom else SampleTag.OUT_OF_SAMPLE,
            CostBasis.GROSS,
        )
        for nom in metriques
    }
    table_metriques = metrics_table(metriques, etiquettes)

    seuils = VerdictCriteria(**params["verdict"])
    multiple_survecu = (
        float(controles["cost_analysis"].breakeven_multiplier)
        if controles["cost_analysis"].breakeven_multiplier is not None
        else 0.0
    )
    preuves = VerdictEvidence(
        hypothesis_supported=metriques["jambe_a_ecart_apres_publication_pct_par_mois"] > 0.0,
        replication_checks=tuple(construire_controles(config, contenu_a)),
        oos_sharpe=metriques["jambe_a_sharpe_apres_publication"],
        tstat_after_multiplicity=metriques["jambe_a_t_apres_publication"],
        deflated_sharpe=metriques["sharpe_deflate"],
        pbo=metriques["probabilite_de_surapprentissage"],
        positive_subperiod_share=metriques["part_de_sous_periodes_positives"],
        surviving_cost_multiple=multiple_survecu,
        portfolio_correlation=abs(metriques["correlation_avec_le_momentum_publie"]),
        notes=(
            "Le t après publication est celui de la moyenne mensuelle, sans correction "
            "d'essais multiples. Il est comparé au seuil de Harvey, Liu et Zhu (2016)."
        ),
    )
    verdict, raisons = decide_verdict(preuves, seuils)

    resume_json = {
        "study": "002_cross_sectional_momentum",
        "paper": config.paper,
        "seed": config.seed,
        "verdict": verdict.value,
        "verdict_reasons": raisons,
        "windows": fenetres,
        "leg_b_universe_size": len(config.data.universe),
        "leg_b_common_window": face_a_face["fenetre"],
        "leg_b_common_months": int(face_a_face["n_mois_communs"]),
        "metrics": metriques,
        "metric_labels": {
            nom: {"sample": e[0].value, "cost_basis": e[1].value} for nom, e in etiquettes.items()
        },
        "leg_b_grid_shape": contenu_b["forme_de_la_grille"],
        "structural_break": contenu_a["tables"]["jambe_a_rupture"].to_dict(orient="records"),
        "deflated_sharpe": controles["dsr"],
        "pbo": controles["pbo"],
        "bootstrap": controles["bootstrap"],
        "costs": {
            "assumed_bps_per_side": float(config.costs.spread_bps + config.costs.commission_bps),
            "borrow_bps_annual": float(config.costs.borrow_bps_annual),
            "leg_b_breakeven_bps": float(couts["breakeven_bps"]),
            "leg_a_breakeven_bps": float(controles["breakeven_leg_a_bps"]),
            "leg_a_transferred_turnover": controles["leg_a_turnover"],
            "n_returns_missing_on_held_positions": int(couts["n_returns_missing_on_held"]),
            "n_open_positions_on_last_date": int(couts["n_positions_on_last_date"]),
        },
        "leg_b_cleaning": contenu_b["nettoyage"],
        "internal_checks": {
            "weights_vs_returns_max_gap": float(couts["weights_vs_returns_max_gap"]),
            "weights_vs_returns_n_periods": int(couts["weights_vs_returns_n_periods"]),
            "weights_vs_returns_n_disagreeing": int(couts["weights_vs_returns_n_disagreeing"]),
            "leg_b_price_breaks_cut": len(contenu_b["tables"]["jambe_b_ruptures_de_prix"]),
        },
        "replication": [c.as_row() for c in construire_controles(config, contenu_a)],
        "tables": sorted(tous_les_tableaux),
        "figures": [f.name for f in figures],
    }
    (RESULTS / "metrics.json").write_text(
        json.dumps(resume_json, ensure_ascii=False, indent=2, allow_nan=True, default=str) + "\n",
        encoding="utf-8",
    )

    with (
        _registres_sans_journal(),
        ExperimentRegistry().run(
            name="002_cross_sectional_momentum",
            hypothesis=config.hypothesis,
            config=config.model_dump(mode="json"),
            seed=config.seed,
            universe=list(config.data.universe),
            date_start=fenetres["tout"][0],
            date_end=str(pd.Timestamp(contenu_a["ecarts"]["value_weighted"].index.max()).date()),
            cost_basis=CostBasis.GROSS,
            cost_assumptions={
                "spread_bps_per_side": float(config.costs.spread_bps),
                "commission_bps_per_side": float(config.costs.commission_bps),
                "borrow_bps_annual": float(config.costs.borrow_bps_annual),
            },
            n_trials=int(params["n_trials"]),
            notes="Deux jambes, l'une sans biais de survie, l'autre avec, et leur confrontation.",
        ) as contexte,
    ):
        for nom, valeur in metriques.items():
            contexte.log_metric(nom, valeur, sample=etiquettes[nom][0])
        for nom in tous_les_tableaux:
            contexte.log_artifact(TABLES / f"{nom}.csv")
        for figure in figures:
            contexte.log_artifact(figure.path)
        contexte.set_verdict(verdict)
        identifiant = contexte.record.experiment_id

    registre = AlphaRegistry()
    aujourd_hui = pd.Timestamp.today().date()
    with _registres_sans_journal():
        registre.register(
            AlphaMetadata(
                name="cross_sectional_momentum",
                family="momentum",
                paper=config.paper,
                asset_classes=[AssetClass.EQUITY],
                horizon="formation de 3 à 12 mois, détention de 1 à 12 mois",
                economic_rationale=["biais comportemental", "friction"],
                inputs=[
                    "déciles de momentum 12-2 de Kenneth French, mensuels, depuis 1927",
                    "prix quotidiens ajustés des membres actuels du S&P 500, Yahoo",
                    "cinq facteurs de Fama et French plus le momentum de Carhart",
                ],
                known_risks=[
                    "krach de momentum après un renversement de marché, Daniel et Moskowitz (2016)",
                    "renversement de janvier, concentré sur les petites capitalisations",
                    "coûts de transaction corrélés au signal, Lesmond, Schill et Zhou (2004)",
                    "biais de survie de l'univers, mesuré par la jambe B de cette étude",
                ],
                validation_status=verdict,
                verdict_experiment_id=identifiant,
                created=aujourd_hui,
                last_modified=aujourd_hui,
                notes="Étude 002, deux jambes et leur confrontation.",
            ),
            overwrite=True,
        )

    sections = _sections(config, metriques, controles, face_a_face, verdict)
    tableaux_rapport = [
        ReportTable(
            name=nom,
            section=_SECTION_PAR_TABLEAU.get(nom, "performance"),
            frame=table,
            caption=_LEGENDE_PAR_TABLEAU.get(nom, nom),
        )
        for nom, table in tous_les_tableaux.items()
    ]
    rapport = StudyReport(
        study_name="002_cross_sectional_momentum",
        experiment_id=identifiant,
        hypothesis=config.hypothesis,
        paper=config.paper,
        criteria=seuils,
        evidence=preuves,
        sections=sections,
        metrics=table_metriques,
        tables=tableaux_rapport,
        figures=figures,
        config=config.model_dump(mode="json"),
        dataset_manifests=[
            {"provider": "french", "dataset": FRENCH_DECILES, "survivorship_free": True},
            {"provider": "french", "dataset": FRENCH_SIZE_MOMENTUM, "survivorship_free": True},
            {"provider": "yahoo", "dataset": LAKE_DATASET, "survivorship_free": False},
        ],
    )
    chemin = generate_report(RESULTS, rapport)
    LOG.info(
        "étude terminée",
        extra={"verdict": verdict.value, "experiment_id": identifiant, "report": str(chemin)},
    )


#: Les deux journaux qui emploient une clé réservée et lèvent en journalisant.
_JOURNAUX_FAUTIFS = ("quantlab.experiments.registry", "quantlab.strategies.base")


@contextlib.contextmanager
def _registres_sans_journal() -> Iterator[None]:
    """Fait taire deux journaux qui lèvent au lieu d'écrire, le temps d'un bloc.

    **Pourquoi ce contournement existe.** Trois appels de journalisation
    passent ``extra={"name": ...}``, aux lignes 283 de
    ``quantlab/experiments/registry.py`` et 439 et 564 de
    ``quantlab/strategies/base.py``. La clé ``name`` est réservée par la
    bibliothèque standard, qui lève ``KeyError`` avant d'écrire la ligne. Les
    deux registres sont donc inutilisables tant que ces journaux sont actifs.

    **Pourquoi élever le niveau suffit.** L'enregistrement n'est construit que
    si le niveau est autorisé. Au-dessus d'INFO, la ligne fautive n'est jamais
    fabriquée, et les registres écrivent leurs fichiers normalement.

    **Ce que le contournement coûte.** Les lignes d'ouverture et de fermeture
    d'expérience ne paraissent pas dans le journal de cette étude. Les fichiers
    ``experiment.json`` et la fiche d'alpha, eux, sont complets.

    **Ce qu'il faudrait corriger.** Renommer la clé en ``experiment_name`` et en
    ``alpha_name`` dans les deux modules. Cette étude n'a pas le droit d'y
    écrire, et le défaut est donc signalé, non réparé.
    """
    anciens = {}
    for nom in _JOURNAUX_FAUTIFS:
        journal = logging.getLogger(nom)
        anciens[nom] = journal.level
        journal.setLevel(logging.WARNING)
    try:
        yield
    finally:
        for nom, niveau in anciens.items():
            logging.getLogger(nom).setLevel(niveau)


def _nom_de_cellule(ligne: pd.Series) -> str:
    """Nomme une cellule de la grille par son panneau, sa formation et sa détention."""
    return f"{ligne['panel']}_J{int(ligne['formation_months'])}_K{int(ligne['holding_months'])}"


def _table_de_deciles(frame: pd.DataFrame, debut: str, fin: str) -> pd.DataFrame:
    """Renomme les déciles de Kenneth French au format attendu par les figures."""
    tranche = frame.loc[debut:fin].copy()
    tranche.columns = [f"Q{i}" for i in range(1, tranche.shape[1] + 1)]
    tranche["spread"] = tranche[f"Q{tranche.shape[1]}"] - tranche["Q1"]
    return tranche


#: La section du rapport où chaque tableau apparaît.
_SECTION_PAR_TABLEAU = {
    "jambe_a_fenetres": "performance",
    "jambe_a_deciles": "performance",
    "jambe_a_pires_mois": "robustness",
    "jambe_a_janvier": "robustness",
    "jambe_a_sous_periodes_article": "replication",
    "jambe_a_attribution": "factor_attribution",
    "jambe_a_betas": "replication",
    "jambe_a_rupture": "out_of_sample",
    "jambe_a_controle_taille": "limitations",
    "jambe_b_grille": "replication",
    "jambe_b_paquets": "limitations",
    "jambe_b_ruptures_de_prix": "data",
    "jambe_b_couts": "costs",
    "univers_jambe_b": "data",
    "biais_de_survie_niveaux": "limitations",
    "biais_de_survie_ecarts": "limitations",
    "validation_essais": "statistical_tests",
    "robustesse_sous_periodes": "robustness",
    "robustesse_couts": "costs",
    "robustesse_delais": "robustness",
    "replication": "replication",
}

#: La légende de chaque tableau, qui dit comment le lire.
_LEGENDE_PAR_TABLEAU = {
    "jambe_a_fenetres": "L'écart gagnant moins perdant par fenêtre, deux pondérations.",
    "jambe_a_deciles": "Le rendement moyen de chaque décile, par fenêtre et par pondération.",
    "jambe_a_pires_mois": "Les dix pires mois de l'écart, 1927 à 2026.",
    "jambe_a_janvier": "Janvier contre les onze autres mois, par fenêtre.",
    "jambe_a_sous_periodes_article": "Nos cinq sous-périodes en face de celles de l'article.",
    "jambe_a_attribution": "L'alpha de l'écart contre cinq facteurs plus le momentum.",
    "jambe_a_betas": "Les bêtas des deux déciles extrêmes sur la fenêtre de l'article.",
    "jambe_a_rupture": "La chute du rendement après publication, testée par une indicatrice.",
    "jambe_a_controle_taille": "Le même tri sur les grandes et les petites capitalisations.",
    "jambe_b_grille": "Les trente-deux cellules refaites sur l'univers des survivants.",
    "jambe_b_paquets": "Le profil des paquets de la jambe B, déciles et quintiles.",
    "jambe_b_couts": "Le brut, le net et la rotation de la jambe B, exposition brute de un.",
    "jambe_b_ruptures_de_prix": "Les ruptures de série de prix trouvées et coupées.",
    "univers_jambe_b": "Les 503 titres de la jambe B et leur première cotation.",
    "biais_de_survie_niveaux": "Les six écarts comparés sur leur fenêtre commune.",
    "biais_de_survie_ecarts": "L'écart entre univers sans radiés et univers de survivants.",
    "validation_essais": "Tous les essais et leur ratio de Sharpe, entrée du Sharpe dégonflé.",
    "robustesse_sous_periodes": "Le Sharpe de la jambe A par sous-période après publication.",
    "robustesse_couts": "Le Sharpe net quand les coûts sont multipliés.",
    "robustesse_delais": "Le Sharpe quand l'exécution attend un à six mois.",
    "replication": "Nos onze contrôles chiffrés contre les valeurs publiées.",
}


def _sections(
    config: ExperimentConfig,
    metriques: dict[str, float],
    controles: dict[str, Any],
    face_a_face: dict[str, Any],
    verdict: Verdict,
) -> dict[str, str]:
    """Rend la prose des quinze sections du rapport, chiffres compris."""
    debut, fin = face_a_face["fenetre"]
    return {
        "hypothesis": config.hypothesis,
        "paper": config.paper,
        "methodology": (
            "Classement croissant des titres sur leur rendement des J derniers mois, "
            "dix déciles équipondérés, achat du dernier et vente du premier, cohortes "
            "qui se chevauchent sur K mois."
        ),
        "data": (
            "Jambe A, les déciles 12-2 de Kenneth French construits sur CRSP, titres "
            "radiés compris, de 1927-01 à la dernière date publiée. Jambe B, les prix "
            f"quotidiens ajustés des {len(config.data.universe)} membres actuels du "
            "S&P 500, chez Yahoo."
        ),
        "implementation": (
            "Le tri, les cohortes et les poids vivent dans "
            "quantlab.strategies.cross_sectional_momentum. Le décalage d'exécution "
            "d'une période est appliqué par le moteur de backtest, jamais deux fois."
        ),
        "assumptions": (
            f"Coût de {config.costs.spread_bps:.0f} points de base par sens, la valeur "
            "de l'article, plus un coût d'emprunt de titre "
            f"{config.costs.borrow_bps_annual:.0f} points de base par an, modélisé."
        ),
        "replication": (
            "Onze grandeurs publiées mises en face des nôtres, tolérance déclarée dans "
            "la configuration avant le calcul."
        ),
        "performance": (
            "Sur la fenêtre de l'article, l'écart vaut "
            f"{metriques['jambe_a_ecart_echantillon_article_pct_par_mois']:.4f} pour cent "
            f"par mois, t de {metriques['jambe_a_t_echantillon_article']:.2f}. Après "
            f"publication, {metriques['jambe_a_ecart_apres_publication_pct_par_mois']:.4f} "
            f"pour cent par mois, t de {metriques['jambe_a_t_apres_publication']:.2f}."
        ),
        "costs": (
            "Le seuil de rentabilité de la jambe A vaut "
            f"{metriques['jambe_a_seuil_de_rentabilite_bps']:.1f} points de base par unité "
            "négociée, rotation de la jambe B transférée."
        ),
        "robustness": (
            f"{metriques['part_de_sous_periodes_positives']:.0%} des sous-périodes après "
            "publication portent un ratio de Sharpe positif."
        ),
        "out_of_sample": (
            "Le t passe de "
            f"{metriques['jambe_a_t_echantillon_article']:.2f} sur la fenêtre de l'article "
            f"à {metriques['jambe_a_t_apres_publication']:.2f} après publication."
        ),
        "statistical_tests": (
            f"Ratio de Sharpe dégonflé de {metriques['sharpe_deflate']:.3f} sur "
            f"{controles['dsr']['n_trials']} essais, probabilité de surapprentissage de "
            f"{metriques['probabilite_de_surapprentissage']:.3f}."
        ),
        "factor_attribution": (
            "L'écart est régressé sur les cinq facteurs de Fama et French plus le "
            "momentum de Carhart, erreurs types corrigées à la Newey-West."
        ),
        "limitations": (
            "Sur la fenêtre commune "
            f"{debut} à {fin}, l'univers des survivants rend "
            f"{metriques['biais_de_survie_pp_par_an']:.2f} points de pourcentage par an de "
            "MOINS que l'univers complet, t corrigé de "
            f"{metriques['biais_de_survie_t_hac']:.2f}."
        ),
        "verdict": f"Verdict déduit des critères, sans choix : {verdict.value}.",
    }


if __name__ == "__main__":
    main()

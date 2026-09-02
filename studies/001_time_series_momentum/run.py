"""Le point d'entrée de l'étude 001, du téléchargement au verdict.

Ce fichier n'implémente rien. Il enchaîne des appels au paquet ``quantlab``,
écrit ses sorties dans ``results/`` et rend un verdict déduit. Toute logique
réutilisable vit dans :mod:`quantlab.strategies.time_series_momentum`.

Lancement, depuis la racine du dépôt :

.. code-block:: bash

    export QUANTLAB_USER_AGENT="prénom nom courriel"
    uv run python studies/001_time_series_momentum/run.py
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from quantlab.analytics import drawdown, risk
from quantlab.analytics import returns as ret_mod
from quantlab.analytics.ratios import (
    sharpe_confidence_interval,
    sharpe_ratio,
    sharpe_standard_error,
)
from quantlab.analytics.regression import factor_regression
from quantlab.analytics.visualization import figures as fig_mod
from quantlab.backtest.engine import run_backtest
from quantlab.core.config import ExperimentConfig, load_config
from quantlab.core.determinism import make_generator
from quantlab.core.logging import get_logger, stage
from quantlab.core.paths import ensure
from quantlab.core.types import CostBasis, Frequency, SampleTag
from quantlab.data.providers.aqr import AqrProvider
from quantlab.data.providers.french import FrenchProvider
from quantlab.data.providers.yahoo import YahooProvider, to_wide
from quantlab.execution.costs import breakeven_cost_bps
from quantlab.execution.costs import from_config as cost_from_config
from quantlab.experiments import ExperimentRegistry
from quantlab.features.transforms import assert_causal
from quantlab.reporting.study import (
    MetricLabel,
    ReplicationCheck,
    VerdictCriteria,
    VerdictEvidence,
    decide_verdict,
    metrics_table,
    replication_table,
)
from quantlab.strategies.base import AlphaMetadata, AlphaRegistry
from quantlab.strategies.time_series_momentum import (
    ex_ante_volatility,
    grid_weights,
    tsmom_weights,
)
from quantlab.validation.cpcv import CombinatorialPurgedCV, cpcv_performance_distribution
from quantlab.validation.dsr import deflated_sharpe_ratio
from quantlab.validation.multiple_testing import TrialCounter, haircut_sharpe, required_tstat
from quantlab.validation.pbo import probability_of_backtest_overfitting
from quantlab.validation.robustness import (
    best_plateau,
    cost_multiplier_analysis,
    plateau_score,
    subperiod_performance,
)
from quantlab.validation.splits import ExpandingSplit

_LOG = get_logger("study.001")

STUDY_DIR = Path(__file__).resolve().parent
RESULTS = STUDY_DIR / "results"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"

MONTHLY = Frequency.MONTHLY


# --------------------------------------------------------------------------- #
# Utilitaires d'écriture
# --------------------------------------------------------------------------- #


def _write_table(frame: pd.DataFrame, name: str) -> Path:
    """Écrit un tableau en CSV sous ``results/tables`` et rend son chemin."""
    path = TABLES / f"{name}.csv"
    frame.to_csv(path, index=True)
    _LOG.info("tableau écrit", extra={"name": name, "rows": len(frame)})
    return path


def _write_figure(figure: Any, name: str) -> Path:
    """Enregistre une figure en PNG et en PDF, et rend le chemin du PNG."""
    paths = fig_mod.save_figure(figure, FIGURES / name, vector=True)
    return next(p for p in paths if p.suffix == ".png")


def _annual_stats(series: pd.Series, label: str) -> dict[str, float]:
    """Rend les huit grandeurs publiées pour une série mensuelle."""
    erreur = sharpe_standard_error(series, frequency=MONTHLY)
    intervalle = sharpe_confidence_interval(series, frequency=MONTHLY)
    return {
        "label": label,
        "n_mois": len(series),
        "debut": str(series.index.min().date()),
        "fin": str(series.index.max().date()),
        "rendement_annualise": float(ret_mod.cagr(series, frequency=MONTHLY)),
        "moyenne_annualisee": float(ret_mod.arithmetic_mean_return(series, frequency=MONTHLY)),
        "volatilite_annualisee": float(risk.volatility(series, MONTHLY)),
        "sharpe": float(sharpe_ratio(series, frequency=MONTHLY)),
        "sharpe_se_lo": float(erreur.lo),
        "sharpe_se_iid": float(erreur.iid),
        "sharpe_ic_bas": float(intervalle.low),
        "sharpe_ic_haut": float(intervalle.high),
        "pire_repli": float(drawdown.max_drawdown(series)),
        "duree_pire_repli_mois": int(drawdown.max_drawdown_duration(series)),
        "asymetrie": float(risk.skewness(series)),
        "aplatissement_excedentaire": float(risk.kurtosis(series)),
        "part_de_mois_positifs": float(risk.hit_rate(series)),
    }


def _sharpe_difference_test(a: pd.Series, b: pd.Series) -> dict[str, float]:
    """Teste l'égalité de deux ratios de Sharpe sur deux échantillons disjoints.

    Les deux fenêtres ne se recouvrent pas, donc les deux estimateurs sont
    indépendants et la variance de leur écart est la somme des variances. La
    statistique est le rapport de l'écart à la racine de cette somme, et sa loi
    sous l'hypothèse nulle est approximativement normale centrée réduite.
    """
    sa = sharpe_ratio(a, frequency=MONTHLY)
    sb = sharpe_ratio(b, frequency=MONTHLY)
    ea = sharpe_standard_error(a, frequency=MONTHLY).lo
    eb = sharpe_standard_error(b, frequency=MONTHLY).lo
    ecart = float(sa - sb)
    erreur = float(math.sqrt(ea**2 + eb**2))
    z = ecart / erreur if erreur > 0 else float("nan")
    return {
        "sharpe_a": float(sa),
        "sharpe_b": float(sb),
        "ecart": ecart,
        "erreur_type_a_lo": float(ea),
        "erreur_type_b_lo": float(eb),
        "erreur_type_de_l_ecart": erreur,
        "z": float(z),
        "p_bilaterale": float(2.0 * (1.0 - stats.norm.cdf(abs(z)))),
    }


# --------------------------------------------------------------------------- #
# Les données
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, eq=False)
class Donnees:
    """Tout ce que l'étude télécharge, aligné une fois pour toutes."""

    prix: pd.DataFrame
    rendements_quotidiens: pd.DataFrame
    exces_quotidiens: pd.DataFrame
    volatilite_quotidienne: pd.DataFrame
    dernieres_seances: pd.DatetimeIndex
    exces_mensuels: pd.DataFrame
    volatilite_mensuelle: pd.DataFrame
    facteurs_mensuels: pd.DataFrame
    tsmom_aqr: pd.DataFrame
    manifestes: list[dict[str, Any]]


def charger(config: ExperimentConfig) -> Donnees:
    """Télécharge les trois sources et construit les tableaux alignés."""
    p = config.params
    with stage("données"):
        yahoo = YahooProvider()
        brut = yahoo.fetch(
            config.data.universe,
            start=config.data.start,
            end=config.data.end,
            on_missing="drop",
        )
        prix = to_wide(brut, config.data.price_field).reindex(columns=config.data.universe)
        rendements = prix.pct_change()

        french = FrenchProvider()
        quotidiens = french.benchmark_factors(frequency=Frequency.DAILY, start=config.data.start)
        mensuels = french.benchmark_factors(frequency=Frequency.MONTHLY, start=p["aqr_start"])
        taux_quotidien = quotidiens["RF"].reindex(rendements.index).ffill()
        if bool(taux_quotidien.isna().any()):
            raise ValueError("le taux sans risque quotidien ne couvre pas toutes les séances.")
        exces_quotidiens = rendements.sub(taux_quotidien, axis=0)

        volatilite = ex_ante_volatility(
            exces_quotidiens,
            center_of_mass=float(p["volatility_center_of_mass_days"]),
            annualization_days=float(p["volatility_annualization_days"]),
            min_periods=int(p["volatility_min_periods_days"]),
        )

        cle = [rendements.index.year, rendements.index.month]
        dernieres_seances = pd.DatetimeIndex(
            sorted(rendements.index.to_series().groupby(cle).max().to_numpy())
        )
        # L'index mensuel est ramené à la FIN DE MOIS CIVILE. Sans cela, un mois
        # dont la dernière séance tombe le 30 au lieu du 31 ne s'apparie ni au
        # facteur d'AQR ni aux facteurs de Kenneth French, et trente pour cent
        # des mois disparaissent en silence de chaque régression.
        fins_de_mois = pd.DatetimeIndex(dernieres_seances.to_period("M").to_timestamp("M"))
        seances = rendements.notna().groupby(cle).sum().set_axis(fins_de_mois)
        mensuel_brut = ((1.0 + rendements).groupby(cle).prod() - 1.0).set_axis(fins_de_mois)
        mensuel_brut = mensuel_brut.where(seances >= int(p["min_trading_days_per_month"]))
        taux_mensuel = mensuels["RF"].reindex(fins_de_mois, method="ffill")
        exces_mensuels = mensuel_brut.sub(taux_mensuel, axis=0)

        aqr = AqrProvider()
        tsmom = aqr.tsmom_factors(start=p["aqr_start"])
        tsmom.index = tsmom.index.to_period("M").to_timestamp("M")

        manifestes = [
            yahoo.manifest().model_dump(mode="json"),
            french.manifest("F-F_Research_Data_Factors").model_dump(mode="json"),
            aqr.manifest("tsmom").model_dump(mode="json"),
        ]

    return Donnees(
        prix=prix,
        rendements_quotidiens=rendements,
        exces_quotidiens=exces_quotidiens,
        volatilite_quotidienne=volatilite,
        dernieres_seances=dernieres_seances,
        exces_mensuels=exces_mensuels,
        volatilite_mensuelle=volatilite.reindex(dernieres_seances).set_axis(fins_de_mois),
        facteurs_mensuels=mensuels,
        tsmom_aqr=tsmom,
        manifestes=manifestes,
    )


# --------------------------------------------------------------------------- #
# Jambe A, le facteur des auteurs hors échantillon
# --------------------------------------------------------------------------- #


def jambe_a(config: ExperimentConfig, d: Donnees) -> dict[str, Any]:
    """Mesure ce que devient le facteur publié par AQR après l'échantillon."""
    p = config.params
    tsmom = d.tsmom_aqr
    fin_papier = p["paper_sample_end"]
    debut_publication = p["publication_start"]

    fenetres = {
        "échantillon de l'article, 1985-2009": tsmom["TSMOM"].loc[:fin_papier],
        "après l'échantillon, 2010 à 2026": tsmom["TSMOM"].loc["2010-01-01":],
        "après publication, juin 2012 à 2026": tsmom["TSMOM"].loc[debut_publication:],
    }
    table_fenetres = pd.DataFrame([_annual_stats(s.dropna(), k) for k, s in fenetres.items()])

    lignes: list[dict[str, Any]] = []
    for colonne, nom in p["asset_class_columns"].items():
        serie = tsmom[colonne].dropna()
        avant = serie.loc[:fin_papier]
        apres = serie.loc[debut_publication:]
        lignes.append(
            {
                "classe": nom,
                "colonne": colonne,
                "sharpe_echantillon": float(sharpe_ratio(avant, frequency=MONTHLY)),
                "sharpe_apres_publication": float(sharpe_ratio(apres, frequency=MONTHLY)),
                "rendement_annualise_echantillon": float(ret_mod.cagr(avant, frequency=MONTHLY)),
                "rendement_annualise_apres_publication": float(ret_mod.cagr(apres, frequency=MONTHLY)),
                "pire_repli_echantillon": float(drawdown.max_drawdown(avant)),
                "pire_repli_apres_publication": float(drawdown.max_drawdown(apres)),
                **{f"test_{k}": v for k, v in _sharpe_difference_test(avant, apres).items()},
            }
        )
    table_classes = pd.DataFrame(lignes)

    test_global = _sharpe_difference_test(
        tsmom["TSMOM"].loc[:fin_papier].dropna(),
        tsmom["TSMOM"].loc[debut_publication:].dropna(),
    )
    table_test = pd.DataFrame([{"serie": "TSMOM, toutes classes", **test_global}])

    colonnes = ["MKT-RF", "SMB", "HML", "MOM"]
    attributions: list[dict[str, Any]] = []
    for label, serie in fenetres.items():
        x = serie.dropna()
        f = d.facteurs_mensuels.reindex(x.index)[colonnes].dropna()
        x = x.reindex(f.index)
        r = factor_regression(x, f, frequency=MONTHLY)
        attributions.append(
            {
                "fenetre": label,
                "n_mois": int(r.n_obs),
                "alpha_annualise": float(r.alpha),
                "alpha_mensuel": float(r.alpha) / 12.0,
                "alpha_t": float(r.alpha_tstat),
                "r_carre": float(r.r_squared),
                **{f"beta_{c}": float(r.betas[c]) for c in colonnes},
                **{f"t_{c}": float(r.beta_tstats[c]) for c in colonnes},
            }
        )
    table_attribution = pd.DataFrame(attributions)

    replis = drawdown.drawdown_table(tsmom["TSMOM"].dropna()).nsmallest(10, "depth")

    sous_periodes = subperiod_performance(
        tsmom["TSMOM"].dropna(),
        breakpoints=[pd.Timestamp(x) for x in p["aqr_subperiod_breakpoints"]],
        frequency=MONTHLY,
    )

    _write_table(table_fenetres, "jambe_a_fenetres")
    _write_table(table_classes, "jambe_a_classes_actifs")
    _write_table(table_test, "jambe_a_test_de_difference")
    _write_table(table_attribution, "jambe_a_attribution")
    _write_table(replis, "jambe_a_dix_pires_replis")
    _write_table(sous_periodes, "jambe_a_sous_periodes")

    return {
        "fenetres": table_fenetres,
        "classes": table_classes,
        "test": test_global,
        "attribution": table_attribution,
        "replis": replis,
        "sous_periodes": sous_periodes,
        "serie": tsmom["TSMOM"].dropna(),
    }


# --------------------------------------------------------------------------- #
# Jambe B, notre reconstruction
# --------------------------------------------------------------------------- #


def _backtest(
    poids: pd.DataFrame,
    rendements: pd.DataFrame,
    *,
    cost_model: object | None,
) -> Any:
    """Rejoue une suite de poids mensuels avec un décalage d'exécution de un."""
    return run_backtest(
        weights=poids,
        returns=rendements,
        cost_model=cost_model,
        execution_lag=1,
        frequency=MONTHLY,
    )


def jambe_b(config: ExperimentConfig, d: Donnees) -> dict[str, Any]:
    """Construit la stratégie de l'article sur les fonds cotés et la valide."""
    p = config.params
    debut = p["backtest_start"]

    exces = d.exces_mensuels.loc[debut:]
    volatilite = d.volatilite_mensuelle.loc[debut:]
    rendements_moteur = exces.fillna(0.0)

    profondeur = pd.DataFrame(
        {
            "premier_prix": d.prix.notna().idxmax(),
            "premiere_volatilite": d.volatilite_mensuelle.notna().idxmax(),
        }
    )
    profondeur["premier_prix"] = profondeur["premier_prix"].astype(str)
    profondeur["premiere_volatilite"] = profondeur["premiere_volatilite"].astype(str)
    _write_table(profondeur, "jambe_b_profondeur_univers")

    poids = tsmom_weights(
        d.exces_mensuels,
        d.volatilite_mensuelle,
        lookback=int(p["lookback_months"]),
        holding=int(p["holding_months"]),
        target_volatility=float(p["target_volatility"]),
    ).loc[debut:]

    modele = cost_from_config(config.costs, frequency=MONTHLY)
    resultat = _backtest(poids, rendements_moteur, cost_model=modele)
    brut = resultat.gross_returns
    net = resultat.net_returns

    fenetres = {
        "chevauchement de l'article, 2007 à 2009": (None, p["paper_sample_end"], SampleTag.IN_SAMPLE),
        "avant publication, 2007 à mai 2012": (None, "2012-05-31", SampleTag.OUT_OF_SAMPLE),
        "après publication, juin 2012 à 2026": (
            p["publication_start"],
            None,
            SampleTag.FINAL_HOLDOUT,
        ),
        "tout, 2007 à 2026": (None, None, SampleTag.OUT_OF_SAMPLE),
    }
    lignes: list[dict[str, Any]] = []
    for label, (a, b, tag) in fenetres.items():
        for base, serie in (("brut", brut), ("net", net)):
            x = serie.loc[a:b]
            lignes.append(
                {
                    **_annual_stats(x, label),
                    "base_de_cout": base,
                    "echantillon": tag.value,
                    "rotation_annuelle": float(resultat.turnover.loc[a:b].mean() * 12.0),
                    "exposition_brute_moyenne": float(resultat.gross_exposure.loc[a:b].mean()),
                    "exposition_brute_maximale": float(resultat.gross_exposure.loc[a:b].max()),
                    "exposition_nette_moyenne": float(resultat.net_exposure.loc[a:b].mean()),
                }
            )
    table_performance = pd.DataFrame(lignes)
    _write_table(table_performance, "jambe_b_performance")

    commun = (
        brut.rename("reconstruction")
        .to_frame()
        .join(d.tsmom_aqr["TSMOM"].rename("facteur_aqr"), how="inner")
        .dropna()
    )
    regression = factor_regression(commun["reconstruction"], commun[["facteur_aqr"]], frequency=MONTHLY)
    validation = {
        "n_mois_communs": len(commun),
        "debut": str(commun.index.min().date()),
        "fin": str(commun.index.max().date()),
        "correlation": float(commun.corr().iloc[0, 1]),
        "beta": float(regression.betas["facteur_aqr"]),
        "beta_t": float(regression.beta_tstats["facteur_aqr"]),
        "alpha_annualise": float(regression.alpha),
        "alpha_t": float(regression.alpha_tstat),
        "r_carre": float(regression.r_squared),
        "sharpe_reconstruction": float(sharpe_ratio(commun["reconstruction"], frequency=MONTHLY)),
        "sharpe_facteur_aqr": float(sharpe_ratio(commun["facteur_aqr"], frequency=MONTHLY)),
    }
    _write_table(pd.DataFrame([validation]), "jambe_b_validation_contre_aqr")

    signal = np.sign(
        (1.0 + d.exces_mensuels).rolling(int(p["lookback_months"])).apply(np.prod, raw=True) - 1.0
    ).loc[debut:]
    positions = signal.mul(float(p["target_volatility"])).div(volatilite)
    lignes_instruments: list[dict[str, Any]] = []
    for symbole in exces.columns:
        serie = (positions[symbole].shift(1) * exces[symbole]).dropna()
        if len(serie) < 24:
            continue
        passif = (positions[symbole].abs().shift(1) * exces[symbole]).dropna()
        lignes_instruments.append(
            {
                "symbole": symbole,
                "n_mois": len(serie),
                "sharpe_tsmom": float(sharpe_ratio(serie, frequency=MONTHLY)),
                "t_de_la_moyenne": float(
                    sharpe_ratio(serie, frequency=MONTHLY) * math.sqrt(len(serie) / 12.0)
                ),
                "sharpe_position_longue_a_risque_egal": float(sharpe_ratio(passif, frequency=MONTHLY)),
                "part_de_mois_long": float((signal[symbole] > 0).mean()),
            }
        )
    table_instruments = pd.DataFrame(lignes_instruments).set_index("symbole")
    _write_table(table_instruments, "jambe_b_instruments_isoles")

    expositions = pd.DataFrame(
        {
            "poids_moyen": resultat.executed_weights.mean(),
            "poids_absolu_moyen": resultat.executed_weights.abs().mean(),
            "poids_absolu_maximal": resultat.executed_weights.abs().max(),
            "volatilite_ex_ante_mediane": volatilite.median(),
            "part_de_mois_long": (resultat.executed_weights > 0).mean(),
        }
    ).sort_values("poids_absolu_moyen", ascending=False)
    _write_table(expositions, "jambe_b_expositions_par_instrument")

    return {
        "instruments": table_instruments,
        "part_instruments_positifs": float((table_instruments["sharpe_tsmom"] > 0).mean()),
        "n_instruments_significatifs": int((table_instruments["t_de_la_moyenne"].abs() > 1.96).sum()),
        "poids": poids,
        "resultat": resultat,
        "brut": brut,
        "net": net,
        "performance": table_performance,
        "validation": validation,
        "expositions": expositions,
        "exces": exces,
        "rendements_moteur": rendements_moteur,
        "commun": commun,
    }


# --------------------------------------------------------------------------- #
# Jambe C, la grille formation contre détention
# --------------------------------------------------------------------------- #


def jambe_c(config: ExperimentConfig, d: Donnees, b: dict[str, Any]) -> dict[str, Any]:
    """Reproduit la structure du tableau 2 de l'article sur la reconstruction."""
    p = config.params
    debut = p["backtest_start"]
    rendements = b["rendements_moteur"]

    facteurs = d.facteurs_mensuels.reindex(rendements.index)[["MKT-RF", "SMB", "HML", "MOM"]].copy()
    facteurs["OBLIG"] = rendements[p["bond_benchmark"]]
    facteurs["MATPREM"] = rendements[p["commodity_benchmark"]]
    facteurs = facteurs.dropna()

    cellules = grid_weights(
        d.exces_mensuels,
        d.volatilite_mensuelle,
        formations=tuple(p["formation_grid"]),
        holdings=tuple(p["holding_grid"]),
        target_volatility=float(p["target_volatility"]),
    )

    t_stats: dict[tuple[int, int], float] = {}
    sharpes: dict[tuple[int, int], float] = {}
    alphas: dict[tuple[int, int], float] = {}
    series: dict[str, pd.Series] = {}
    for (k, h), poids in cellules.items():
        resultat = _backtest(poids.loc[debut:], rendements, cost_model=None)
        serie = resultat.gross_returns
        series[f"k{k}_h{h}"] = serie
        sharpes[k, h] = float(sharpe_ratio(serie, frequency=MONTHLY))
        regression = factor_regression(serie.reindex(facteurs.index), facteurs, frequency=MONTHLY)
        t_stats[k, h] = float(regression.alpha_tstat)
        alphas[k, h] = float(regression.alpha)

    def _grille(valeurs: dict[tuple[int, int], float]) -> pd.DataFrame:
        """Range un dictionnaire indexé par (formation, détention) en tableau carré."""
        return pd.DataFrame(
            [[valeurs[k, h] for h in p["holding_grid"]] for k in p["formation_grid"]],
            index=pd.Index(p["formation_grid"], name="formation"),
            columns=pd.Index(p["holding_grid"], name="detention"),
        )

    grille_t = _grille(t_stats)
    grille_sharpe = _grille(sharpes)
    grille_alpha = _grille(alphas)

    _write_table(grille_t, "jambe_c_grille_t_de_l_alpha")
    _write_table(grille_sharpe, "jambe_c_grille_sharpe")
    _write_table(grille_alpha, "jambe_c_grille_alpha_annualise")

    publiee = pd.DataFrame(
        [
            [4.34, 4.68, 3.83, 4.29, 5.12, 3.02, 2.74, 1.90],
            [5.35, 4.42, 3.54, 4.73, 4.50, 2.60, 1.97, 1.52],
            [5.03, 4.54, 4.93, 5.32, 4.43, 2.79, 1.89, 1.42],
            [6.06, 6.13, 5.78, 5.07, 4.10, 2.57, 1.45, 1.19],
            [6.61, 5.60, 4.44, 3.69, 2.85, 1.68, 0.66, 0.46],
            [3.95, 3.19, 2.44, 1.95, 1.50, 0.20, -0.09, -0.33],
            [2.70, 2.20, 1.44, 0.96, 0.62, 0.28, 0.07, 0.20],
            [1.84, 1.55, 1.16, 1.00, 0.86, 0.38, 0.46, 0.74],
        ],
        index=pd.Index(p["formation_grid"], name="formation"),
        columns=pd.Index(p["holding_grid"], name="detention"),
    )
    _write_table(publiee, "jambe_c_grille_publiee")

    courtes = [k for k in p["formation_grid"] if k <= 12]
    longues = [k for k in p["formation_grid"] if k >= 24]
    profil = {
        "cellules_positives_publiees": int((publiee > 0).to_numpy().sum()),
        "cellules_positives_mesurees_t": int((grille_t > 0).to_numpy().sum()),
        "cellules_positives_mesurees_sharpe": int((grille_sharpe > 0).to_numpy().sum()),
        "t_maximal_publie": float(publiee.to_numpy().max()),
        "t_maximal_mesure": float(grille_t.to_numpy().max()),
        "sharpe_median_formations_courtes": float(np.median(grille_sharpe.loc[courtes].to_numpy())),
        "sharpe_median_formations_longues": float(np.median(grille_sharpe.loc[longues].to_numpy())),
        "t_median_formations_courtes": float(np.median(grille_t.loc[courtes].to_numpy())),
        "t_median_formations_longues": float(np.median(grille_t.loc[longues].to_numpy())),
        "correlation_de_rang_avec_la_grille_publiee": float(
            stats.spearmanr(publiee.to_numpy().ravel(), grille_t.to_numpy().ravel()).statistic
        ),
    }
    _write_table(pd.DataFrame([profil]), "jambe_c_profil")

    return {
        "t": grille_t,
        "sharpe": grille_sharpe,
        "alpha": grille_alpha,
        "publiee": publiee,
        "profil": profil,
        "series": pd.DataFrame(series),
        "facteurs": facteurs,
    }


# --------------------------------------------------------------------------- #
# Le parcours obligatoire
# --------------------------------------------------------------------------- #


def robustesse(
    config: ExperimentConfig,
    d: Donnees,
    b: dict[str, Any],
    c: dict[str, Any],
    generator: np.random.Generator,
) -> dict[str, Any]:
    """Coûts, plateau, marche en avant, validation croisée, essais multiples."""
    p = config.params
    debut = p["backtest_start"]
    rendements = b["rendements_moteur"]
    brut = b["brut"]
    net = b["net"]
    resultat = b["resultat"]

    # --- Les coûts ---
    composantes = pd.DataFrame(
        {
            "cout_moyen_mensuel": resultat.cost_breakdown.mean(),
            "cout_annualise": resultat.cost_breakdown.mean() * 12.0,
        }
    )
    _write_table(composantes, "couts_composantes")

    seuil = float(breakeven_cost_bps(brut, resultat.turnover, MONTHLY))

    def _evaluer_multiple(multiplicateur: float) -> float:
        couts = config.costs.model_copy(
            update={
                "commission_bps": config.costs.commission_bps * multiplicateur,
                "spread_bps": config.costs.spread_bps * multiplicateur,
                "slippage_bps": config.costs.slippage_bps * multiplicateur,
                "financing_spread_bps_annual": config.costs.financing_spread_bps_annual * multiplicateur,
            }
        )
        sortie = _backtest(b["poids"], rendements, cost_model=cost_from_config(couts, frequency=MONTHLY))
        return float(sharpe_ratio(sortie.net_returns, frequency=MONTHLY))

    analyse = cost_multiplier_analysis(_evaluer_multiple, tuple(p["cost_multipliers"]))
    _write_table(analyse.table, "couts_multiplicateur")

    # --- La recherche de plateau sur la grille ---
    balayage = pd.DataFrame(
        [
            {"lookback": int(k), "holding": int(h), "sharpe": float(c["sharpe"].loc[k, h])}
            for k in c["sharpe"].index
            for h in c["sharpe"].columns
        ]
    )
    plateau = plateau_score(
        balayage, ["lookback", "holding"], "sharpe", neighborhood=int(p["plateau_neighborhood"])
    )
    meilleur = best_plateau(
        balayage, ["lookback", "holding"], "sharpe", neighborhood=int(p["plateau_neighborhood"])
    )
    _write_table(plateau, "robustesse_plateau")
    _write_table(pd.DataFrame([meilleur]), "robustesse_meilleur_plateau")

    # --- La sensibilité au modèle de volatilité et au plafond de position ---
    variantes: list[dict[str, Any]] = []
    for centre in p["center_of_mass_grid"]:
        vol = (
            ex_ante_volatility(
                d.exces_quotidiens,
                center_of_mass=float(centre),
                annualization_days=float(p["volatility_annualization_days"]),
                min_periods=int(p["volatility_min_periods_days"]),
            )
            .reindex(d.dernieres_seances)
            .set_axis(d.volatilite_mensuelle.index)
        )
        poids = tsmom_weights(d.exces_mensuels, vol, lookback=int(p["lookback_months"]), holding=1).loc[
            debut:
        ]
        sortie = _backtest(poids, rendements, cost_model=cost_from_config(config.costs, frequency=MONTHLY))
        variantes.append(
            {
                "variante": f"centre de masse {centre} jours",
                "parametre": float(centre),
                "sharpe_brut": float(sharpe_ratio(sortie.gross_returns, frequency=MONTHLY)),
                "sharpe_net": float(sharpe_ratio(sortie.net_returns, frequency=MONTHLY)),
                "rotation_annuelle": float(sortie.turnover.mean() * 12.0),
                "exposition_brute_moyenne": float(sortie.gross_exposure.mean()),
            }
        )
    for plafond in p["max_position_grid"]:
        poids = tsmom_weights(
            d.exces_mensuels,
            d.volatilite_mensuelle,
            lookback=int(p["lookback_months"]),
            holding=1,
            max_position=float(plafond),
        ).loc[debut:]
        sortie = _backtest(poids, rendements, cost_model=cost_from_config(config.costs, frequency=MONTHLY))
        variantes.append(
            {
                "variante": f"position plafonnée à {plafond:g} fois",
                "parametre": float(plafond),
                "sharpe_brut": float(sharpe_ratio(sortie.gross_returns, frequency=MONTHLY)),
                "sharpe_net": float(sharpe_ratio(sortie.net_returns, frequency=MONTHLY)),
                "rotation_annuelle": float(sortie.turnover.mean() * 12.0),
                "exposition_brute_moyenne": float(sortie.gross_exposure.mean()),
            }
        )
    # La critique de Kim, Tse et Wald (2016) : sans normalisation par la volatilité.
    signe = np.sign(
        (1.0 + d.exces_mensuels).rolling(int(p["lookback_months"])).apply(np.prod, raw=True) - 1.0
    )
    poids_sans_echelle = signe.div(signe.notna().sum(axis=1).where(lambda s: s > 0), axis=0).fillna(0.0)
    sortie = _backtest(
        poids_sans_echelle.loc[debut:],
        rendements,
        cost_model=cost_from_config(config.costs, frequency=MONTHLY),
    )
    variantes.append(
        {
            "variante": "sans normalisation par la volatilité",
            "parametre": float("nan"),
            "sharpe_brut": float(sharpe_ratio(sortie.gross_returns, frequency=MONTHLY)),
            "sharpe_net": float(sharpe_ratio(sortie.net_returns, frequency=MONTHLY)),
            "rotation_annuelle": float(sortie.turnover.mean() * 12.0),
            "exposition_brute_moyenne": float(sortie.gross_exposure.mean()),
        }
    )
    table_variantes = pd.DataFrame(variantes)
    _write_table(table_variantes, "robustesse_variantes")

    # --- La marche en avant ---
    decoupe = ExpandingSplit(
        train_size=int(p["walk_forward_train_months"]),
        test_size=int(p["walk_forward_test_months"]),
        purge=int(config.validation.purge_periods),
        embargo=int(config.validation.embargo_periods),
    )
    grille_series = c["series"]
    lignes_wf: list[dict[str, Any]] = []
    rendements_wf: list[pd.Series] = []
    for i, (entrainement, test) in enumerate(decoupe.split(grille_series)):
        bloc_train = grille_series.iloc[entrainement]
        bloc_test = grille_series.iloc[test]
        scores = bloc_train.apply(lambda s: sharpe_ratio(s, frequency=MONTHLY))
        retenue = str(scores.idxmax())
        serie_test = bloc_test[retenue]
        rendements_wf.append(serie_test)
        lignes_wf.append(
            {
                "pli": i,
                "configuration_retenue": retenue,
                "sharpe_entrainement": float(scores.max()),
                "sharpe_test": float(sharpe_ratio(serie_test, frequency=MONTHLY)),
                "sharpe_test_de_la_cellule_de_l_article": float(
                    sharpe_ratio(bloc_test["k12_h1"], frequency=MONTHLY)
                ),
                "debut_test": str(bloc_test.index.min().date()),
                "fin_test": str(bloc_test.index.max().date()),
            }
        )
    table_wf = pd.DataFrame(lignes_wf)
    _write_table(table_wf, "walk_forward")
    serie_wf = pd.concat(rendements_wf).sort_index()
    serie_wf = serie_wf[~serie_wf.index.duplicated(keep="first")]
    serie_wf_article = grille_series.loc[serie_wf.index, "k12_h1"]

    # --- La validation croisée combinatoire purgée ---
    # Le chemin ne mesure pas une série figée, sinon les sept chemins rendraient
    # sept fois le même nombre. À chaque segment, la cellule de grille est
    # CHOISIE sur les plis d'entraînement purgés, puis mesurée sur le pli de
    # test. C'est le choix de configuration qui est validé, pas la série.
    cv = CombinatorialPurgedCV(
        n_folds=int(config.validation.n_folds),
        n_test_folds=int(config.validation.n_test_folds),
        purge=int(config.validation.purge_periods),
        embargo=int(config.validation.embargo_periods),
    )
    choix_par_chemin: list[dict[str, Any]] = []

    def _chemin_selectif(chemin: Any) -> float:
        """Choisit une cellule par segment, puis mesure le chemin recomposé."""
        morceaux: list[pd.Series] = []
        for segment in chemin.segments:
            entrainement = grille_series.iloc[segment.train_index]
            scores = entrainement.apply(lambda s: sharpe_ratio(s, frequency=MONTHLY))
            retenue = str(scores.idxmax())
            morceaux.append(grille_series.iloc[segment.test_index][retenue])
            choix_par_chemin.append(
                {
                    "chemin": int(chemin.path_id),
                    "pli": int(segment.fold),
                    "configuration_retenue": retenue,
                    "sharpe_entrainement": float(scores.max()),
                }
            )
        recompose = pd.concat(morceaux).sort_index()
        return float(sharpe_ratio(recompose, frequency=MONTHLY))

    distribution = cpcv_performance_distribution(
        cv, grille_series, _chemin_selectif, metric_name="sharpe_brut"
    )
    _write_table(distribution.metrics.to_frame("sharpe_brut"), "cpcv_chemins")
    _write_table(pd.DataFrame([distribution.summary]), "cpcv_synthese")
    _write_table(pd.DataFrame(choix_par_chemin), "cpcv_configurations_retenues")

    # --- La probabilité de surapprentissage ---
    pbo = probability_of_backtest_overfitting(
        grille_series, n_splits=int(config.validation.n_folds), frequency=MONTHLY
    )
    _write_table(pbo.logits.to_frame("logit"), "pbo_logits")

    # --- Les essais multiples et le Sharpe dégonflé ---
    compteur = TrialCounter(annualized=False)
    for nom in grille_series.columns:
        compteur = compteur.record(
            "tsmom_grille", nom, float(sharpe_ratio(grille_series[nom], frequency=MONTHLY, annualize=False))
        )
    for ligne in variantes:
        compteur = compteur.record(
            "tsmom_variantes",
            ligne["variante"],
            float(ligne["sharpe_brut"]) / math.sqrt(12.0),
        )
    intrants = compteur.deflation_inputs()
    n_essais = int(intrants.n_trials) + int(p["manual_trials"])

    holdout = net.loc[p["publication_start"] :]
    sharpe_mensuel_holdout = float(sharpe_ratio(holdout, frequency=MONTHLY, annualize=False))
    dsr = float(
        deflated_sharpe_ratio(
            observed_sr=sharpe_mensuel_holdout,
            sharpe_variance_across_trials=float(intrants.sharpe_variance),
            n_trials=n_essais,
            n_obs=float(len(holdout)),
            skew=float(risk.skewness(holdout)),
            kurtosis=float(risk.kurtosis(holdout, excess=False)),
        )
    )
    rasage = haircut_sharpe(
        float(sharpe_ratio(holdout, frequency=MONTHLY)),
        n_tests=n_essais,
        n_obs=len(holdout),
        frequency=MONTHLY,
        method="holm",
    )
    table_essais = pd.DataFrame(
        [
            {
                "n_essais_grille": len(grille_series.columns),
                "n_essais_variantes": len(variantes),
                "n_essais_manuels": int(p["manual_trials"]),
                "n_essais_total": n_essais,
                "variance_des_sharpe_mensuels": float(intrants.sharpe_variance),
                "sharpe_mensuel_du_holdout": sharpe_mensuel_holdout,
                "sharpe_annualise_du_holdout": float(sharpe_ratio(holdout, frequency=MONTHLY)),
                "sharpe_degonfle": dsr,
                "t_observe": float(rasage.observed_tstat),
                "t_exige_bonferroni": float(required_tstat(n_essais, method="bonferroni")),
                "p_simple": float(rasage.single_pvalue),
                "p_corrigee": float(rasage.adjusted_pvalue),
                "t_corrige": float(rasage.adjusted_tstat),
                "sharpe_rase": float(rasage.haircut_sr),
                "part_rasee": float(rasage.haircut_fraction),
            }
        ]
    )
    _write_table(table_essais, "essais_multiples")

    # --- Les sous-périodes ---
    sous_periodes = subperiod_performance(
        net,
        breakpoints=[pd.Timestamp(x) for x in p["subperiod_breakpoints"]],
        frequency=MONTHLY,
    )
    _write_table(sous_periodes, "sous_periodes")
    part_positive = float((sous_periodes["sharpe"] > 0).mean())

    # --- L'attribution factorielle de la reconstruction ---
    facteurs = c["facteurs"]
    attributions: list[dict[str, Any]] = []
    for label, serie in (("brut", brut), ("net", net)):
        r = factor_regression(serie.reindex(facteurs.index), facteurs, frequency=MONTHLY)
        attributions.append(
            {
                "serie": label,
                "n_mois": int(r.n_obs),
                "alpha_annualise": float(r.alpha),
                "alpha_t": float(r.alpha_tstat),
                "r_carre": float(r.r_squared),
                **{f"beta_{k}": float(v) for k, v in r.betas.items()},
                **{f"t_{k}": float(v) for k, v in r.beta_tstats.items()},
            }
        )
    table_attribution = pd.DataFrame(attributions)
    _write_table(table_attribution, "attribution_facteurs")

    # --- Le risque de queue ---
    lignes_queue: list[dict[str, Any]] = []
    for label, serie in (("brut", brut), ("net", net), ("facteur AQR", b["commun"]["facteur_aqr"])):
        ligne = {
            "serie": label,
            "asymetrie": float(risk.skewness(serie)),
            "aplatissement_excedentaire": float(risk.kurtosis(serie)),
            "rapport_de_queues": float(risk.tail_ratio(serie)),
            "gain_sur_peine": float(risk.gain_to_pain(serie)),
            "pire_mois": float(serie.min()),
            "meilleur_mois": float(serie.max()),
            "biais_d_annualisation": float(risk.annualization_bias(serie, MONTHLY)),
        }
        for alpha in p["tail_quantiles"]:
            ligne[f"var_historique_{alpha:g}"] = float(risk.value_at_risk(serie, alpha))
            ligne[f"perte_attendue_{alpha:g}"] = float(risk.expected_shortfall(serie, alpha))
            ligne[f"var_cornish_fisher_{alpha:g}"] = float(
                risk.value_at_risk(serie, alpha, method="cornish_fisher")
            )
        lignes_queue.append(ligne)
    table_queue = pd.DataFrame(lignes_queue)
    _write_table(table_queue, "risque_de_queue")

    # --- La corrélation au portefeuille existant, ici le marché actions ---
    marche = d.facteurs_mensuels["MKT-RF"].reindex(net.index).dropna()
    correlation_portefeuille = float(net.reindex(marche.index).corr(marche))

    _LOG.info(
        "robustesse terminée",
        extra={"n_essais": n_essais, "dsr": dsr, "pbo": float(pbo.pbo)},
    )

    return {
        "composantes": composantes,
        "seuil_de_rentabilite_bps": seuil,
        "analyse_de_couts": analyse,
        "plateau": plateau,
        "meilleur_plateau": meilleur,
        "variantes": table_variantes,
        "walk_forward": table_wf,
        "serie_walk_forward": serie_wf,
        "serie_walk_forward_article": serie_wf_article,
        "cpcv": distribution,
        "pbo": pbo,
        "essais": table_essais,
        "n_essais": n_essais,
        "dsr": dsr,
        "rasage": rasage,
        "sous_periodes": sous_periodes,
        "part_positive": part_positive,
        "attribution": table_attribution,
        "queue": table_queue,
        "correlation_portefeuille": correlation_portefeuille,
        "generator": generator,
    }


# --------------------------------------------------------------------------- #
# Les figures
# --------------------------------------------------------------------------- #


def _long(grille: pd.DataFrame) -> pd.DataFrame:
    """Met une grille carrée en forme longue, trois colonnes k, h et t."""
    return pd.DataFrame(
        [
            {"k": int(k), "h": int(h), "t": float(grille.loc[k, h])}
            for k in grille.index
            for h in grille.columns
        ]
    )


def figures(
    config: ExperimentConfig,
    d: Donnees,
    a: dict[str, Any],
    b: dict[str, Any],
    c: dict[str, Any],
    rb: dict[str, Any],
) -> list[str]:
    """Trace les neuf figures de l'étude et rend leurs noms."""
    p = config.params
    noms: list[str] = []

    fig, _ = fig_mod.equity_curve(
        {"Facteur TSMOM d'AQR": a["serie"]},
        log_scale=True,
        currency="$ US",
        title="Richesse du facteur TSMOM d'AQR, base 1 $ US au 1985-01-31",
    )
    noms.append("richesse_facteur_aqr")
    _write_figure(fig, "richesse_facteur_aqr")

    debut_commun = b["brut"].index.min()
    fig, _ = fig_mod.equity_curve(
        {
            "Notre reconstruction, brute": b["brut"],
            "Notre reconstruction, nette": b["net"],
            "Facteur TSMOM d'AQR, même fenêtre": a["serie"].loc[debut_commun:],
        },
        log_scale=False,
        currency="$ US",
        title="Richesse de la reconstruction et du facteur, base 1 $ US au 2007-01-31",
    )
    noms.append("richesse_reconstruction")
    _write_figure(fig, "richesse_reconstruction")

    fig, _ = fig_mod.underwater(
        a["serie"], title="Repli du facteur TSMOM d'AQR depuis son sommet, 1985 à 2026"
    )
    noms.append("repli_facteur_aqr")
    _write_figure(fig, "repli_facteur_aqr")

    fig, _ = fig_mod.rolling_metric(
        a["serie"],
        metric="sharpe",
        window=60,
        frequency=MONTHLY,
        title="Ratio de Sharpe du facteur TSMOM sur soixante mois glissants",
    )
    noms.append("sharpe_glissant_aqr")
    _write_figure(fig, "sharpe_glissant_aqr")

    balayage_t = _long(c["t"])
    fig, _ = fig_mod.parameter_heatmap(
        balayage_t,
        x="h",
        y="k",
        metric="t",
        x_label="Détention, en mois",
        y_label="Formation, en mois",
        metric_label="t de l'alpha",
        title="Statistique t de l'alpha, notre reconstruction, 2007 à 2026",
    )
    noms.append("grille_t_mesuree")
    _write_figure(fig, "grille_t_mesuree")

    balayage_publie = _long(c["publiee"])
    fig, _ = fig_mod.parameter_heatmap(
        balayage_publie,
        x="h",
        y="k",
        metric="t",
        x_label="Détention, en mois",
        y_label="Formation, en mois",
        metric_label="t de l'alpha",
        title="Statistique t de l'alpha publiée par l'article, 1985 à 2009",
    )
    noms.append("grille_t_publiee")
    _write_figure(fig, "grille_t_publiee")

    analyse = rb["analyse_de_couts"]
    fig, _ = fig_mod.cost_sensitivity(
        list(analyse.table["multiplier"]),
        list(analyse.table["metric"]),
        threshold=0.0,
        title="Ratio de Sharpe net selon le multiple des coûts supposés",
    )
    noms.append("sensibilite_aux_couts")
    _write_figure(fig, "sensibilite_aux_couts")

    fig, _ = fig_mod.subperiod_bars(
        rb["sous_periodes"],
        title="Ratio de Sharpe net par sous-période, notre reconstruction",
    )
    noms.append("sous_periodes")
    _write_figure(fig, "sous_periodes")

    classes = d.tsmom_aqr[list(p["asset_class_columns"])].rename(columns=p["asset_class_columns"])
    ensemble = classes.copy()
    ensemble["notre reconstruction"] = b["brut"]
    # La matrice que la figure dessine est aussi écrite en CSV : un chiffre lu
    # sur une image n'est pas un chiffre sourcé.
    _write_table(ensemble.dropna().corr(), "correlations_classes_actifs")
    fig, _ = fig_mod.correlation_heatmap(
        ensemble.dropna(),
        title="Corrélation mensuelle des jambes du facteur et de notre reconstruction",
    )
    noms.append("correlations")
    _write_figure(fig, "correlations")

    fig, _ = fig_mod.return_histogram(
        b["net"], title="Distribution des rendements mensuels nets de notre reconstruction"
    )
    noms.append("histogramme_des_rendements")
    _write_figure(fig, "histogramme_des_rendements")

    fig, _ = fig_mod.qq_plot(b["net"], title="Quantiles des rendements nets contre la loi normale")
    noms.append("quantiles_contre_la_normale")
    _write_figure(fig, "quantiles_contre_la_normale")

    return noms


# --------------------------------------------------------------------------- #
# Le verdict et les métriques
# --------------------------------------------------------------------------- #


def verdict(
    config: ExperimentConfig,
    a: dict[str, Any],
    b: dict[str, Any],
    c: dict[str, Any],
    rb: dict[str, Any],
) -> dict[str, Any]:
    """Assemble les preuves, applique les seuils, et écrit le verdict."""
    p = config.params
    publie = p["published"]
    attribution = a["attribution"].set_index("fenetre")
    ligne_papier = attribution.iloc[0]
    volatilite_papier = float(a["fenetres"].set_index("label").iloc[0]["volatilite_annualisee"])

    checks = (
        ReplicationCheck(
            quantity="volatilité annualisée du facteur, 1985-2009",
            published=float(publie["portfolio_volatility_1985_2009"]),
            ours=volatilite_papier,
            tolerance=float(p["verdict_criteria"]["replication_tolerance"]),
            source="article, section 4.2, « environ 12 % par an »",
        ),
        ReplicationCheck(
            quantity="charge du facteur sur le momentum transversal, 1985-2009",
            published=float(publie["umd_beta_1985_2009"]),
            ours=float(ligne_papier["beta_MOM"]),
            tolerance=float(p["verdict_criteria"]["replication_tolerance"]),
            source="article, tableau 3, panneau A, coefficient UMD mensuel",
            note="notre régression emploie le facteur MOM américain de Kenneth French.",
        ),
        ReplicationCheck(
            quantity="alpha mensuel du facteur, 1985-2009",
            published=float(publie["monthly_alpha_1985_2009"]),
            ours=float(ligne_papier["alpha_mensuel"]),
            tolerance=float(p["verdict_criteria"]["replication_tolerance"]),
            source="article, tableau 3, panneau A, constante mensuelle 1,58 %",
            note="le repère du marché diffère, MSCI World contre marché américain.",
        ),
        ReplicationCheck(
            quantity="t de l'alpha mensuel du facteur, 1985-2009",
            published=float(publie["monthly_alpha_tstat_1985_2009"]),
            ours=float(ligne_papier["alpha_t"]),
            tolerance=float(p["verdict_criteria"]["replication_tolerance"]),
            source="article, tableau 3, panneau A, t de 7,99",
        ),
        ReplicationCheck(
            quantity="part des instruments à ratio de Sharpe positif, pris isolément",
            published=1.0,
            ours=float(b["part_instruments_positifs"]),
            tolerance=float(p["verdict_criteria"]["replication_tolerance"]),
            source="article, section 4.1, les 58 contrats affichent un Sharpe positif",
        ),
        ReplicationCheck(
            quantity="cellules de la grille à statistique t positive",
            published=float(publie["positive_grid_cells"]),
            ours=float(c["profil"]["cellules_positives_mesurees_t"]),
            tolerance=float(p["verdict_criteria"]["replication_tolerance"]),
            source="article, tableau 2, 62 cellules positives sur 64",
        ),
    )
    table = replication_table(checks)
    _write_table(table, "replication")

    courtes = float(c["profil"]["sharpe_median_formations_courtes"])
    longues = float(c["profil"]["sharpe_median_formations_longues"])
    hypothese = bool(courtes > 0.0 and courtes > longues)

    holdout_net = b["net"].loc[p["publication_start"] :]
    evidence = VerdictEvidence(
        hypothesis_supported=hypothese,
        replication_checks=checks,
        oos_sharpe=float(sharpe_ratio(holdout_net, frequency=MONTHLY)),
        tstat_after_multiplicity=float(rb["rasage"].observed_tstat),
        deflated_sharpe=float(rb["dsr"]),
        pbo=float(rb["pbo"].pbo),
        positive_subperiod_share=float(rb["part_positive"]),
        surviving_cost_multiple=(
            float(rb["analyse_de_couts"].breakeven_multiplier)
            if rb["analyse_de_couts"].breakeven_multiplier is not None
            else float(max(p["cost_multipliers"]))
        ),
        portfolio_correlation=float(rb["correlation_portefeuille"]),
        notes=(
            "Le Sharpe hors échantillon est celui de la fenêtre postérieure à la "
            "publication, net des coûts déclarés."
        ),
    )
    criteres = VerdictCriteria(**p["verdict_criteria"])
    decision, raisons = decide_verdict(evidence, criteres)
    _write_table(
        pd.DataFrame({"raison": raisons}),
        "verdict_raisons",
    )
    return {
        "verdict": decision,
        "raisons": raisons,
        "checks": checks,
        "replication": table,
        "evidence": evidence,
        "hypothese_soutenue": hypothese,
    }


def _metriques(
    config: ExperimentConfig,
    a: dict[str, Any],
    b: dict[str, Any],
    c: dict[str, Any],
    rb: dict[str, Any],
    v: dict[str, Any],
) -> tuple[dict[str, float], pd.DataFrame]:
    """Rend le dictionnaire des métriques publiées et son tableau étiqueté."""
    p = config.params
    fenetres = a["fenetres"].set_index("label")
    perf = b["performance"].set_index(["label", "base_de_cout"])

    valeurs: dict[str, float] = {
        "aqr_sharpe_echantillon_1985_2009": float(fenetres.iloc[0]["sharpe"]),
        "aqr_sharpe_apres_publication": float(fenetres.iloc[2]["sharpe"]),
        "aqr_volatilite_echantillon_1985_2009": float(fenetres.iloc[0]["volatilite_annualisee"]),
        "aqr_pire_repli_apres_publication": float(fenetres.iloc[2]["pire_repli"]),
        "aqr_z_de_difference_des_sharpe": float(a["test"]["z"]),
        "aqr_p_de_difference_des_sharpe": float(a["test"]["p_bilaterale"]),
        "reconstruction_sharpe_brut_total": float(perf.loc[("tout, 2007 à 2026", "brut"), "sharpe"]),
        "reconstruction_sharpe_net_total": float(perf.loc[("tout, 2007 à 2026", "net"), "sharpe"]),
        "reconstruction_sharpe_net_apres_publication": float(
            perf.loc[("après publication, juin 2012 à 2026", "net"), "sharpe"]
        ),
        "reconstruction_sharpe_brut_apres_publication": float(
            perf.loc[("après publication, juin 2012 à 2026", "brut"), "sharpe"]
        ),
        "reconstruction_volatilite_totale": float(
            perf.loc[("tout, 2007 à 2026", "brut"), "volatilite_annualisee"]
        ),
        "reconstruction_exposition_brute_moyenne": float(
            perf.loc[("tout, 2007 à 2026", "brut"), "exposition_brute_moyenne"]
        ),
        "reconstruction_rotation_annuelle": float(
            perf.loc[("tout, 2007 à 2026", "brut"), "rotation_annuelle"]
        ),
        "part_instruments_a_sharpe_positif": float(b["part_instruments_positifs"]),
        "n_instruments_significatifs": float(b["n_instruments_significatifs"]),
        "correlation_avec_le_facteur_aqr": float(b["validation"]["correlation"]),
        "beta_sur_le_facteur_aqr": float(b["validation"]["beta"]),
        "alpha_annualise_sur_le_facteur_aqr": float(b["validation"]["alpha_annualise"]),
        "alpha_t_sur_le_facteur_aqr": float(b["validation"]["alpha_t"]),
        "grille_t_maximal": float(c["profil"]["t_maximal_mesure"]),
        "grille_cellules_positives": float(c["profil"]["cellules_positives_mesurees_t"]),
        "grille_sharpe_median_formations_courtes": float(c["profil"]["sharpe_median_formations_courtes"]),
        "grille_sharpe_median_formations_longues": float(c["profil"]["sharpe_median_formations_longues"]),
        "cout_de_seuil_de_rentabilite_bps": float(rb["seuil_de_rentabilite_bps"]),
        "multiple_de_couts_survecu": float(
            rb["analyse_de_couts"].breakeven_multiplier
            if rb["analyse_de_couts"].breakeven_multiplier is not None
            else max(p["cost_multipliers"])
        ),
        "n_essais_comptes": float(rb["n_essais"]),
        "sharpe_degonfle": float(rb["dsr"]),
        "probabilite_de_surapprentissage": float(rb["pbo"].pbo),
        "cpcv_sharpe_median": float(rb["cpcv"].summary["median"]),
        "cpcv_part_negative": float(rb["cpcv"].negative_share),
        "part_de_sous_periodes_positives": float(rb["part_positive"]),
        "t_apres_essais_multiples": float(rb["rasage"].observed_tstat),
        "t_exige_apres_essais_multiples": float(required_tstat(int(rb["n_essais"]), method="bonferroni")),
        "correlation_au_marche_actions": float(rb["correlation_portefeuille"]),
        "walk_forward_sharpe": float(sharpe_ratio(rb["serie_walk_forward"], frequency=MONTHLY)),
        "walk_forward_sharpe_cellule_de_l_article": float(
            sharpe_ratio(rb["serie_walk_forward_article"], frequency=MONTHLY)
        ),
        "cpcv_sharpe_ecart_type": float(rb["cpcv"].summary["std"]),
        "cpcv_sharpe_minimum": float(rb["cpcv"].summary["min"]),
    }

    brut_ou_net = {
        "aqr_sharpe_echantillon_1985_2009": (SampleTag.IN_SAMPLE, CostBasis.GROSS),
        "aqr_sharpe_apres_publication": (SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
        "aqr_volatilite_echantillon_1985_2009": (SampleTag.IN_SAMPLE, CostBasis.GROSS),
        "aqr_pire_repli_apres_publication": (SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
        "aqr_z_de_difference_des_sharpe": (SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
        "aqr_p_de_difference_des_sharpe": (SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
        "reconstruction_sharpe_brut_total": (SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
        "reconstruction_sharpe_net_total": (SampleTag.OUT_OF_SAMPLE, CostBasis.NET),
        "reconstruction_sharpe_net_apres_publication": (SampleTag.FINAL_HOLDOUT, CostBasis.NET),
        "reconstruction_sharpe_brut_apres_publication": (SampleTag.FINAL_HOLDOUT, CostBasis.GROSS),
        "reconstruction_volatilite_totale": (SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
        "reconstruction_exposition_brute_moyenne": (SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
        "reconstruction_rotation_annuelle": (SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
        "part_instruments_a_sharpe_positif": (SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
        "n_instruments_significatifs": (SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
        "correlation_avec_le_facteur_aqr": (SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
        "beta_sur_le_facteur_aqr": (SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
        "alpha_annualise_sur_le_facteur_aqr": (SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
        "alpha_t_sur_le_facteur_aqr": (SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
        "grille_t_maximal": (SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
        "grille_cellules_positives": (SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
        "grille_sharpe_median_formations_courtes": (SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
        "grille_sharpe_median_formations_longues": (SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
        "cout_de_seuil_de_rentabilite_bps": (SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
        "multiple_de_couts_survecu": (SampleTag.OUT_OF_SAMPLE, CostBasis.NET),
        "n_essais_comptes": (SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
        "sharpe_degonfle": (SampleTag.FINAL_HOLDOUT, CostBasis.NET),
        "probabilite_de_surapprentissage": (SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
        "cpcv_sharpe_median": (SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
        "cpcv_part_negative": (SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
        "part_de_sous_periodes_positives": (SampleTag.OUT_OF_SAMPLE, CostBasis.NET),
        "t_apres_essais_multiples": (SampleTag.FINAL_HOLDOUT, CostBasis.NET),
        "t_exige_apres_essais_multiples": (SampleTag.FINAL_HOLDOUT, CostBasis.NET),
        "correlation_au_marche_actions": (SampleTag.OUT_OF_SAMPLE, CostBasis.NET),
        "walk_forward_sharpe": (SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
        "walk_forward_sharpe_cellule_de_l_article": (SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
        "cpcv_sharpe_ecart_type": (SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
        "cpcv_sharpe_minimum": (SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
    }
    etiquettes = {
        nom: MetricLabel(sample=couple[0], cost_basis=couple[1]) for nom, couple in brut_ou_net.items()
    }
    return valeurs, metrics_table(valeurs, etiquettes)


# --------------------------------------------------------------------------- #
# Le programme
# --------------------------------------------------------------------------- #


def main() -> None:
    """Fait tourner l'étude entière et écrit tout dans ``results/``."""
    ensure(TABLES)
    ensure(FIGURES)
    config = load_config(STUDY_DIR / "config.yaml", ExperimentConfig)
    generator = make_generator(config.seed)

    donnees = charger(config)

    with stage("contrôle de causalité"):
        assert_causal(
            lambda s: ex_ante_volatility(
                s,
                center_of_mass=float(config.params["volatility_center_of_mass_days"]),
                annualization_days=float(config.params["volatility_annualization_days"]),
                min_periods=int(config.params["volatility_min_periods_days"]),
            ),
            donnees.exces_quotidiens[["SPY"]].dropna(),
            name="ex_ante_volatility",
        )

    with stage("jambe A"):
        a = jambe_a(config, donnees)
    with stage("jambe B"):
        b = jambe_b(config, donnees)
    with stage("jambe C"):
        c = jambe_c(config, donnees, b)
    with stage("robustesse"):
        rb = robustesse(config, donnees, b, c, generator)
    with stage("figures"):
        noms_figures = figures(config, donnees, a, b, c, rb)
    with stage("verdict"):
        v = verdict(config, a, b, c, rb)

    valeurs, table_metriques = _metriques(config, a, b, c, rb, v)
    _write_table(table_metriques, "metriques")

    charge = {
        "study": config.name,
        "paper": config.paper,
        "seed": config.seed,
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "universe": config.data.universe,
        "sample_start": str(b["brut"].index.min().date()),
        "sample_end": str(b["brut"].index.max().date()),
        "cost_assumptions_bps": config.costs.model_dump(),
        "n_trials": int(rb["n_essais"]),
        "verdict": v["verdict"].value,
        "verdict_reasons": v["raisons"],
        "metrics": valeurs,
        "figures": noms_figures,
        "dataset_manifests": donnees.manifestes,
    }
    (RESULTS / "metrics.json").write_text(
        json.dumps(charge, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )

    registre = ExperimentRegistry()
    with registre.run(
        name=config.name,
        hypothesis=config.hypothesis,
        config=config.model_dump(mode="json"),
        seed=config.seed,
        universe=list(config.data.universe),
        date_start=str(b["brut"].index.min().date()),
        date_end=str(b["brut"].index.max().date()),
        cost_basis=CostBasis.NET,
        cost_assumptions={
            k: float(x) for k, x in config.costs.model_dump().items() if isinstance(x, int | float)
        },
        n_trials=int(rb["n_essais"]),
        notes="Réplication hors échantillon de Moskowitz, Ooi et Pedersen (2012), trois jambes.",
    ) as contexte:
        for nom, valeur in valeurs.items():
            contexte.log_metric(nom, float(valeur), sample=SampleTag.OUT_OF_SAMPLE)
        contexte.log_artifact(RESULTS / "metrics.json")
        contexte.set_verdict(v["verdict"])
        identifiant = contexte.record.experiment_id

    fiche = AlphaMetadata(
        name="time_series_momentum",
        family="momentum",
        paper=config.paper,
        asset_classes=["equity_index", "bond", "commodity", "fx"],
        horizon="formation de douze mois, détention d'un mois, rééquilibrage mensuel",
        economic_rationale=["biais comportemental", "contrainte institutionnelle"],
        inputs=[
            "rendements quotidiens et mensuels de vingt-huit fonds négociés en bourse",
            "taux sans risque mensuel et quotidien de Kenneth French",
            "facteur TSMOM mensuel publié par AQR, série des auteurs",
        ],
        known_risks=[
            "le levier brut de la construction dépasse cinq fois le capital",
            "la prévisibilité mesurée par régression groupée est contestée par Huang et coauteurs (2020)",
            "les fonds cotés ne portent ni le portage ni le coût de renouvellement des contrats à terme",
        ],
        validation_status=v["verdict"],
        verdict_experiment_id=identifiant,
        created=pd.Timestamp.today().date(),
        last_modified=pd.Timestamp.today().date(),
        notes=(
            "Les deux mécanismes sont ceux de l'article : sous-réaction du prix puis "
            "surréaction retardée, et pression de couverture des intervenants commerciaux. "
            "Une réplication en échantillon est impossible faute de contrats à terme et "
            "faute de fonds cotés avant 2007. L'étude est donc un test hors échantillon."
        ),
    )
    AlphaRegistry().register(fiche, overwrite=True)

    _LOG.info(
        "étude terminée",
        extra={"verdict": v["verdict"].value, "experiment_id": identifiant},
    )


if __name__ == "__main__":
    main()

"""Les tests du momentum transversal, valeurs attendues calculées hors du code.

La règle 10 du ``CLAUDE.md`` interdit un test dont la valeur attendue vient de
la sortie de la fonction testée. Chaque valeur ci-dessous vient donc d'un calcul
à la main, d'une propriété mathématique, ou d'une fonction indépendante déjà
testée ailleurs dans le dépôt.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from quantlab.analytics.ic import quantile_returns
from quantlab.core.errors import ConfigError, InsufficientDataError
from quantlab.core.types import Frequency
from quantlab.features.transforms import assert_causal, lag
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


@pytest.fixture
def calendrier_quotidien() -> pd.DatetimeIndex:
    """Trois mois de séances ouvrées, de janvier à mars 2020."""
    return pd.bdate_range("2020-01-01", "2020-03-31")


@pytest.fixture
def panneau_mensuel() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Dix actifs sur trente mois, dont le classement est figé et connu.

    L'actif ``A0`` monte le moins vite, ``A9`` le plus vite. Le classement par
    rendement passé est donc constant, ce qui rend chaque décile prévisible.
    """
    dates = pd.date_range("2000-01-31", periods=30, freq="ME")
    taux = np.linspace(0.001, 0.010, 10)
    rendements = pd.DataFrame(
        np.tile(taux, (len(dates), 1)), index=dates, columns=[f"A{i}" for i in range(10)]
    )
    prix = (1.0 + rendements).cumprod()
    return prix, rendements


# --------------------------------------------------------------------------- #
# month_end_rows
# --------------------------------------------------------------------------- #


def test_fins_de_mois_retenues(calendrier_quotidien: pd.DatetimeIndex) -> None:
    """Les trois dernières séances ouvrées de janvier, février et mars 2020.

    Elles se lisent sur un calendrier : le 31 janvier est un vendredi, le
    28 février aussi, et le 31 mars est un mardi.
    """
    prix = pd.DataFrame({"X": np.arange(len(calendrier_quotidien), dtype=float)}, index=calendrier_quotidien)
    obtenu = month_end_rows(prix)
    assert list(obtenu.index.strftime("%Y-%m-%d")) == ["2020-01-31", "2020-02-28", "2020-03-31"]


def test_decalage_prend_la_seance_precedente(calendrier_quotidien: pd.DatetimeIndex) -> None:
    """Avec un décalage d'une séance, la valeur est celle de la veille ouvrée.

    Les valeurs valant le rang de la séance, la ligne d'index 2020-01-31 doit
    porter le rang du 30 janvier, donc une unité de moins.
    """
    prix = pd.DataFrame({"X": np.arange(len(calendrier_quotidien), dtype=float)}, index=calendrier_quotidien)
    sans = month_end_rows(prix, offset_days=0)
    avec = month_end_rows(prix, offset_days=1)
    assert avec.index.equals(sans.index)
    assert (sans["X"] - avec["X"] == 1.0).all()


def test_decalage_negatif_refuse(calendrier_quotidien: pd.DatetimeIndex) -> None:
    """Un décalage négatif regarderait vers l'avant, donc il est refusé."""
    prix = pd.DataFrame({"X": np.ones(len(calendrier_quotidien))}, index=calendrier_quotidien)
    with pytest.raises(ConfigError, match="offset_days"):
        month_end_rows(prix, offset_days=-1)


def test_index_non_trie_refuse(calendrier_quotidien: pd.DatetimeIndex) -> None:
    """Un index non trié fausserait le repérage des fins de mois."""
    prix = pd.DataFrame({"X": np.ones(len(calendrier_quotidien))}, index=calendrier_quotidien)
    with pytest.raises(ConfigError, match="trié"):
        month_end_rows(prix.iloc[::-1])


# --------------------------------------------------------------------------- #
# formation_signal
# --------------------------------------------------------------------------- #


def test_signal_sur_prix_a_croissance_constante() -> None:
    """Sur des prix qui montent de 10 % par mois, trois mois donnent 0,331.

    Le calcul est fait à la main : 1,1 au cube vaut 1,331, donc le rendement de
    formation vaut 0,331 exactement.
    """
    dates = pd.date_range("2000-01-31", periods=12, freq="ME")
    prix = pd.DataFrame({"X": 1.1 ** np.arange(12, dtype=float)}, index=dates)
    signal = formation_signal(prix, prix, lookback=3)
    assert signal["X"].iloc[3:].round(12).eq(round(1.1**3 - 1.0, 12)).all()


def test_signal_avec_prix_de_classement_recule() -> None:
    """Reculer le prix de classement d'un mois donne le rendement 12 moins 1.

    Sur des prix qui montent de 10 % par mois, une fenêtre de douze mois dont la
    borne droite recule d'un mois vaut 1,1 puissance onze moins un.
    """
    dates = pd.date_range("2000-01-31", periods=30, freq="ME")
    prix = pd.DataFrame({"X": 1.1 ** np.arange(30, dtype=float)}, index=dates)
    signal = formation_signal(prix.shift(1), prix, lookback=12)
    attendu = 1.1**11 - 1.0
    assert signal["X"].iloc[13:].round(10).eq(round(attendu, 10)).all()


def test_signal_est_causal(panneau_mensuel: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    """Le signal ne regarde jamais vers l'avant, contrôlé par ``assert_causal``."""
    prix, _ = panneau_mensuel
    assert_causal(lambda p: formation_signal(p, p, lookback=6), prix, name="momentum de formation")


def test_lookback_nul_refuse(panneau_mensuel: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    """Une fenêtre de formation vide n'a pas de sens et lève."""
    prix, _ = panneau_mensuel
    with pytest.raises(ConfigError, match="lookback"):
        formation_signal(prix, prix, lookback=0)


def test_index_differents_refuses(panneau_mensuel: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    """Deux tableaux d'index différents ne se divisent pas en silence."""
    prix, _ = panneau_mensuel
    with pytest.raises(ConfigError, match="index"):
        formation_signal(prix.iloc[1:], prix, lookback=3)


# --------------------------------------------------------------------------- #
# overlapping_quantile_returns
# --------------------------------------------------------------------------- #


def test_detention_un_mois_egale_le_tri_direct(
    panneau_mensuel: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """Avec K égal à un, la cohorte unique redonne le tri de ``quantile_returns``.

    La référence vient d'une fonction indépendante, déjà couverte par ses
    propres tests, et non de la fonction testée ici.
    """
    prix, rendements = panneau_mensuel
    signal = formation_signal(prix, prix, lookback=3)
    obtenu = overlapping_quantile_returns(signal, rendements, holding=1, n_quantiles=5)
    attendu = quantile_returns(lag(signal, 1), rendements, n_quantiles=5, weighting="equal")
    pd.testing.assert_frame_equal(obtenu, attendu)


def test_detention_deux_mois_est_la_moyenne_des_deux_cohortes(
    panneau_mensuel: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """Avec K égal à deux, le résultat est la demi-somme des deux retards.

    La valeur attendue est construite hors de la fonction, en appelant deux fois
    le tri de référence et en faisant la moyenne à la main.
    """
    prix, rendements = panneau_mensuel
    signal = formation_signal(prix, prix, lookback=3)
    obtenu = overlapping_quantile_returns(signal, rendements, holding=2, n_quantiles=5)
    un = quantile_returns(lag(signal, 1), rendements, n_quantiles=5, weighting="equal")
    deux = quantile_returns(lag(signal, 2), rendements, n_quantiles=5, weighting="equal")
    pd.testing.assert_frame_equal(obtenu, (un + deux) / 2.0)


def test_ecart_connu_sur_classement_fige(
    panneau_mensuel: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """Dix actifs, dix déciles : l'écart vaut la différence des deux rendements.

    Les taux mensuels vont de 0,1 % à 1,0 % par pas de 0,1 point. Le décile
    gagnant est donc l'actif à 1,0 % et le décile perdant celui à 0,1 %, ce qui
    fait un écart de 0,9 point exactement, à chaque date définie.
    """
    prix, rendements = panneau_mensuel
    signal = formation_signal(prix, prix, lookback=3)
    table = overlapping_quantile_returns(signal, rendements, holding=1, n_quantiles=10)
    ecart = table["spread"].dropna()
    assert ecart.round(12).eq(0.009).all()


def test_detention_nulle_refusee(panneau_mensuel: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    """Une détention de zéro mois ne détient rien, donc elle lève."""
    prix, rendements = panneau_mensuel
    signal = formation_signal(prix, prix, lookback=3)
    with pytest.raises(ConfigError, match="holding"):
        overlapping_quantile_returns(signal, rendements, holding=0)


# --------------------------------------------------------------------------- #
# long_short_weights
# --------------------------------------------------------------------------- #


def test_poids_bruts_et_nets(panneau_mensuel: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    """L'exposition brute vaut un et l'exposition nette zéro, par construction.

    Les deux propriétés se déduisent de la formule : la moitié de l'exposition
    est achetée, l'autre vendue, et les deux jambes se compensent.
    """
    prix, _ = panneau_mensuel
    signal = formation_signal(prix, prix, lookback=3)
    poids = long_short_weights(signal, holding=1, n_quantiles=10)
    actives = poids.loc[poids.abs().sum(axis="columns") > 0.0]
    assert actives.abs().sum(axis="columns").round(12).eq(1.0).all()
    assert actives.sum(axis="columns").round(12).eq(0.0).all()


def test_poids_sur_dix_actifs_et_dix_paquets(
    panneau_mensuel: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """Chaque paquet ne contient qu'un actif, donc les poids valent plus et moins un demi.

    Le classement est figé : ``A9`` est toujours gagnant et ``A0`` toujours
    perdant. Les huit autres actifs portent un poids nul.
    """
    prix, _ = panneau_mensuel
    signal = formation_signal(prix, prix, lookback=3)
    poids = long_short_weights(signal, holding=1, n_quantiles=10)
    derniere = poids.iloc[-1]
    assert derniere["A9"] == pytest.approx(0.5)
    assert derniere["A0"] == pytest.approx(-0.5)
    assert derniere.drop(["A0", "A9"]).abs().max() == pytest.approx(0.0)


def test_poids_et_rendements_concordent() -> None:
    """Les poids reproduisent l'écart publié, sur un effectif non divisible.

    Sept actifs et trois paquets : le découpage des noms en surplus décide du
    résultat. Le produit des poids par les rendements du mois suivant doit
    redonner l'écart de ``quantile_returns``, à la précision machine. L'écart
    achète un dollar et en vend un, donc son exposition brute vaut deux.
    """
    generateur = np.random.default_rng(20260902)
    dates = pd.date_range("2000-01-31", periods=24, freq="ME")
    noms = [f"A{i}" for i in range(7)]
    rendements = pd.DataFrame(generateur.normal(0.01, 0.05, (24, 7)), index=dates, columns=noms)
    prix = (1.0 + rendements).cumprod()
    signal = formation_signal(prix, prix, lookback=3)

    poids = long_short_weights(signal, holding=1, n_quantiles=3, min_names=3, target_gross=2.0)
    porte = (poids.shift(1) * rendements).sum(axis="columns")
    table = overlapping_quantile_returns(signal, rendements, holding=1, n_quantiles=3, min_names=3)
    attendu = table["spread"].dropna()
    obtenu = porte.reindex(attendu.index)
    assert np.allclose(obtenu.to_numpy(), attendu.to_numpy(), atol=1e-12)


def test_deux_cohortes_moyennent_les_poids(
    panneau_mensuel: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """Les poids à deux cohortes sont la moyenne des poids à une cohorte décalés."""
    prix, _ = panneau_mensuel
    signal = formation_signal(prix, prix, lookback=3)
    une = long_short_weights(signal, holding=1, n_quantiles=5)
    deux = long_short_weights(signal, holding=2, n_quantiles=5)
    attendu = (une + une.shift(1).fillna(0.0)) / 2.0
    pd.testing.assert_frame_equal(deux, attendu)


def test_poids_sans_decalage_interne(
    panneau_mensuel: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """Les poids de la date t viennent du signal de la date t, sans retard caché.

    Le retard appartient au moteur de backtest. Le vérifier ici empêche de le
    compter deux fois, faute que le rendement seul ne signalerait pas.
    """
    prix, _ = panneau_mensuel
    signal = formation_signal(prix, prix, lookback=3)
    poids = long_short_weights(signal, holding=1, n_quantiles=10)
    premiere = signal.dropna(how="all").index[0]
    assert poids.loc[premiere].abs().sum() == pytest.approx(1.0)


# --------------------------------------------------------------------------- #
# spread_summary et les tableaux
# --------------------------------------------------------------------------- #


def test_resume_sur_trois_valeurs_calculees_a_la_main() -> None:
    """Les valeurs 8 %, moins 8 % et 1 % donnent une moyenne et un t connus.

    La moyenne vaut 1 % sur trois, soit 0,333 %. L'écart type d'échantillon vaut
    la racine de 0,012866667 sur deux. Le t ordinaire est le quotient des deux,
    multiplié par la racine de trois.
    """
    dates = pd.date_range("2000-01-31", periods=3, freq="ME")
    serie = pd.Series([0.08, -0.08, 0.01], index=dates)
    resume = spread_summary(serie)
    ecart_type = math.sqrt(0.012866667 / 2.0)
    assert resume["mean_pct_per_month"] == pytest.approx(1.0 / 3.0, rel=1e-9)
    assert resume["t_iid"] == pytest.approx((0.01 / 3.0) / ecart_type * math.sqrt(3.0), rel=1e-6)
    assert resume["n_periods"] == 3
    assert resume["hit_rate"] == pytest.approx(2.0 / 3.0)
    assert resume["worst_month_pct"] == pytest.approx(-8.0)


def test_resume_annualise_par_douze() -> None:
    """L'annualisation d'une moyenne mensuelle multiplie par douze, sans composition."""
    dates = pd.date_range("2000-01-31", periods=6, freq="ME")
    serie = pd.Series([0.01, 0.02, 0.00, 0.03, -0.01, 0.01], index=dates)
    resume = spread_summary(serie, frequency=Frequency.MONTHLY)
    assert resume["mean_annualized_pct"] == pytest.approx(resume["mean_pct_per_month"] * 12.0)


def test_resume_refuse_une_seule_observation() -> None:
    """Une observation ne porte ni écart type ni t, donc la fonction lève."""
    serie = pd.Series([0.01], index=pd.date_range("2000-01-31", periods=1, freq="ME"))
    with pytest.raises(InsufficientDataError):
        spread_summary(serie)


def test_fenetres_partitionnent_l_echantillon() -> None:
    """Deux fenêtres qui couvrent tout rendent des effectifs qui se somment."""
    dates = pd.date_range("2000-01-31", periods=48, freq="ME")
    serie = pd.Series(np.linspace(-0.02, 0.02, 48), index=dates)
    table = window_table(serie, {"debut": ("2000", "2001"), "fin": ("2002", "2003")})
    assert list(table["window"]) == ["debut", "fin"]
    assert int(table["n_periods"].sum()) == 48


def test_separation_de_janvier_partitionne() -> None:
    """Les deux segments de la séparation de janvier se somment à l'échantillon."""
    dates = pd.date_range("2000-01-31", periods=48, freq="ME")
    serie = pd.Series(np.linspace(-0.02, 0.02, 48), index=dates)
    table = calendar_split(serie, month=1)
    assert int(table["n_periods"].sum()) == 48
    assert int(table.loc[0, "n_periods"]) == 4


def test_mois_hors_bornes_refuse() -> None:
    """Un numéro de mois hors de un à douze lève plutôt que de rendre un vide."""
    dates = pd.date_range("2000-01-31", periods=24, freq="ME")
    serie = pd.Series(np.zeros(24) + 0.01, index=dates)
    with pytest.raises(ConfigError, match="month"):
        calendar_split(serie, month=13)


def test_pires_mois_sur_serie_croissante() -> None:
    """Sur une série croissante, les pires mois sont ses premières dates."""
    dates = pd.date_range("2000-01-31", periods=20, freq="ME")
    serie = pd.Series(np.arange(20, dtype=float) / 100.0, index=dates)
    table = worst_months(serie, count=3)
    assert list(table["date"]) == ["2000-01-31", "2000-02-29", "2000-03-31"]
    assert list(table["rank"]) == [1, 2, 3]


def test_pires_mois_compte_nul_refuse() -> None:
    """Demander zéro mois n'a pas de sens et lève."""
    dates = pd.date_range("2000-01-31", periods=5, freq="ME")
    with pytest.raises(ConfigError, match="count"):
        worst_months(pd.Series(np.zeros(5), index=dates), count=0)


# --------------------------------------------------------------------------- #
# formation_holding_grid
# --------------------------------------------------------------------------- #


def test_grille_reproduit_la_cellule_directe(
    panneau_mensuel: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """La cellule de détention un de la grille égale l'appel direct.

    La référence est construite hors de la grille, par l'autre fonction publique
    du module, elle-même vérifiée contre ``quantile_returns``.
    """
    prix, rendements = panneau_mensuel
    table, series = formation_holding_grid(
        {"A": prix},
        prix,
        rendements,
        formations=[3],
        holdings=[1, 2],
        n_quantiles=5,
    )
    signal = formation_signal(prix, prix, lookback=3)
    attendu = overlapping_quantile_returns(signal, rendements, holding=1, n_quantiles=5)["spread"]
    pd.testing.assert_series_equal(series["A_J3_K1"], attendu, check_names=False)
    assert len(table) == 2
    assert set(table["holding_months"]) == {1, 2}


def test_grille_compte_ses_cellules(panneau_mensuel: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    """Deux panneaux, deux formations et deux détentions font huit cellules.

    Le compte importe : chaque cellule est un essai, et la règle 8 exige de les
    compter tous avant de dégonfler le ratio de Sharpe.
    """
    prix, rendements = panneau_mensuel
    table, series = formation_holding_grid(
        {"A": prix, "B": prix.shift(1)},
        prix,
        rendements,
        formations=[3, 6],
        holdings=[1, 3],
        n_quantiles=5,
    )
    assert len(table) == 8
    assert len(series) == 8


# --------------------------------------------------------------------------- #
# truncate_before_return_breaks
# --------------------------------------------------------------------------- #


def test_rupture_coupe_l_historique_anterieur() -> None:
    """Un prix multiplié par dix coupe tout ce qui précède, et rien d'autre.

    La série ``B`` monte de 1 % par mois puis est multipliée par dix au mois
    d'index 10. Avec un seuil de quatre, les dix premiers prix disparaissent, le
    onzième reste, et la série ``A`` n'est pas touchée.
    """
    dates = pd.date_range("2000-01-31", periods=20, freq="ME")
    valeurs = 1.01 ** np.arange(20, dtype=float)
    prix = pd.DataFrame({"A": valeurs, "B": valeurs.copy()}, index=dates)
    prix.iloc[10:, prix.columns.get_loc("B")] *= 10.0

    coupes, table = truncate_before_return_breaks(prix, threshold=4.0)
    assert list(table["symbol"]) == ["B"]
    assert table.loc[0, "months_dropped"] == 10
    assert coupes["B"].iloc[:10].isna().all()
    assert coupes["B"].iloc[10:].notna().all()
    pd.testing.assert_series_equal(coupes["A"], prix["A"])


def test_apres_coupe_aucun_rendement_ne_depasse_le_seuil() -> None:
    """La coupe laisse une série dont plus aucun rendement ne franchit le seuil."""
    dates = pd.date_range("2000-01-31", periods=20, freq="ME")
    valeurs = 1.01 ** np.arange(20, dtype=float)
    prix = pd.DataFrame({"B": valeurs}, index=dates)
    prix.iloc[10:, 0] *= 10.0
    coupes, _ = truncate_before_return_breaks(prix, threshold=4.0)
    assert (coupes.pct_change().abs().max().max() or 0.0) <= 4.0


def test_aucune_rupture_laisse_les_prix_intacts() -> None:
    """Sans dépassement, les prix rendus sont ceux d'entrée et la table est vide."""
    dates = pd.date_range("2000-01-31", periods=12, freq="ME")
    prix = pd.DataFrame({"A": 1.02 ** np.arange(12, dtype=float)}, index=dates)
    coupes, table = truncate_before_return_breaks(prix, threshold=4.0)
    pd.testing.assert_frame_equal(coupes, prix)
    assert table.empty
    assert list(table.columns) == ["symbol", "break_date", "break_return_pct", "months_dropped"]


def test_seuil_nul_refuse() -> None:
    """Un seuil nul couperait tout historique et lève donc."""
    dates = pd.date_range("2000-01-31", periods=6, freq="ME")
    prix = pd.DataFrame({"A": np.arange(1.0, 7.0)}, index=dates)
    with pytest.raises(ConfigError, match="threshold"):
        truncate_before_return_breaks(prix, threshold=0.0)

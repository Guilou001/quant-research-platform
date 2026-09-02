"""Tests du module ``quantlab.analytics.visualization.figures``.

Une image ne se teste pas, et c'est précisément la raison d'être du module :
chaque fabrique rend les nombres qu'elle dessine. Les tests portent donc sur ces
nombres, jamais sur des pixels. Ils portent aussi sur trois choses que le dessin
promet et que le lecteur vérifie sans les données, à savoir la devise, la date de
base et la mention de l'échelle logarithmique.

Chaque valeur attendue porte sa source, et aucune ne vient de la sortie du code.
Quatre sources sont admises : (a) un calcul à la main écrit dans le commentaire,
(b) une identité mathématique, (c) une valeur publiée et citée, (d) une
bibliothèque indépendante appliquée au même intrant.
"""

from __future__ import annotations

import math
import warnings

import matplotlib

matplotlib.use("Agg")

import matplotlib as mpl
import numpy as np
import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from matplotlib import pyplot as plt
from scipy import stats
from statsmodels.graphics.gofplots import ProbPlot

from quantlab.analytics.drawdown import max_drawdown
from quantlab.analytics.ratios import sharpe_ratio
from quantlab.analytics.visualization.figures import (
    DEFAULT_CURRENCY,
    HistogramData,
    correlation_heatmap,
    cost_sensitivity,
    equity_curve,
    ic_timeseries,
    monthly_returns_heatmap,
    parameter_heatmap,
    portfolio_style,
    qq_plot,
    quantile_bars,
    return_histogram,
    rolling_metric,
    save_figure,
    subperiod_bars,
    underwater,
)
from quantlab.core.determinism import make_generator
from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.types import Frequency

#: Le quantile normal à 97,5 pour cent, valeur publiée dans toute table de la loi
#: normale centrée réduite. Source (c). Il sert de repère indépendant du code.
Z_97_5 = 1.959963984540054

#: Le nombre de séances d'une année sous la convention ``Frequency.DAILY``.
SEANCES_PAR_AN = 252


def _clore(fig: mpl.figure.Figure) -> None:
    """Libère la figure, pour qu'une suite de tests ne garde pas la mémoire."""
    fig.clear()
    plt.close(fig)


def _rendements(n: int, seed: int = 11, mu: float = 0.0004, sigma: float = 0.01) -> pd.Series:
    """Rend une série de rendements quotidiens reproductible, de longueur ``n``."""
    rng = make_generator(seed)
    index = pd.date_range("2020-01-31", periods=n, freq="B")
    return pd.Series(rng.normal(mu, sigma, n), index=index, name="strategie")


# ---------------------------------------------------------------------------
# equity_curve
# ---------------------------------------------------------------------------


def test_equity_curve_reproduit_le_produit_cumule() -> None:
    """La richesse rendue égale le produit cumulé des facteurs.

    Source (b), identité de la composition : W_t = W_0 * prod(1 + r_s).
    """
    r = _rendements(120)
    fig, richesse = equity_curve({"strategie": r})
    attendu = np.cumprod(1.0 + r.to_numpy())
    np.testing.assert_allclose(richesse["strategie"].to_numpy(), attendu, rtol=1e-12)
    _clore(fig)


def test_equity_curve_calcul_a_la_main_sur_trois_periodes() -> None:
    """Trois rendements simples composés, calculés à la main.

    Source (a). Mise de 100, puis +10 %, -50 %, +100 % :
    100 * 1,10 = 110 ; 110 * 0,50 = 55 ; 55 * 2,00 = 110.
    """
    index = pd.date_range("2020-01-31", periods=3, freq="ME")
    r = pd.Series([0.10, -0.50, 1.00], index=index)
    fig, richesse = equity_curve({"essai": r}, initial=100.0)
    np.testing.assert_allclose(richesse["essai"].to_numpy(), [110.0, 55.0, 110.0], rtol=1e-12)
    _clore(fig)


def test_equity_curve_axe_porte_la_devise_la_base_et_l_echelle() -> None:
    """L'axe des ordonnées annonce la devise, la date de base et l'échelle.

    Source (a) : la convention d'axe du portefeuille, vérifiée sur le texte.
    """
    r = _rendements(60)
    fig, _ = equity_curve({"strategie": r}, log_scale=True, currency="$ CA")
    etiquette = fig.axes[0].get_ylabel()
    assert "$ CA" in etiquette
    assert "2020-01-31" in etiquette
    assert "échelle logarithmique" in etiquette
    assert fig.axes[0].get_yscale() == "log"
    _clore(fig)


def test_equity_curve_sans_log_ne_promet_pas_l_echelle_logarithmique() -> None:
    """Sans échelle logarithmique, l'axe ne la mentionne pas, mais garde la devise."""
    r = _rendements(60)
    fig, _ = equity_curve({"strategie": r}, log_scale=False)
    etiquette = fig.axes[0].get_ylabel()
    assert "échelle logarithmique" not in etiquette
    assert DEFAULT_CURRENCY in etiquette
    assert fig.axes[0].get_yscale() == "linear"
    _clore(fig)


def test_equity_curve_ajoute_le_repere_sous_son_nom() -> None:
    """Le repère devient une colonne portant le nom de sa série."""
    r = _rendements(60)
    repere = _rendements(60, seed=5)
    repere.name = "Indice de référence"
    fig, richesse = equity_curve({"strategie": r}, benchmark=repere)
    assert list(richesse.columns) == ["strategie", "Indice de référence"]
    _clore(fig)


def test_equity_curve_titre_nomme_la_meilleure_courbe() -> None:
    """Le titre est déduit des données et cite la courbe la plus haute.

    Source (a) : la seconde série double, la première perd la moitié, donc le
    titre nomme la seconde.
    """
    index = pd.date_range("2020-01-31", periods=2, freq="ME")
    faible = pd.Series([-0.25, -0.25], index=index)
    forte = pd.Series([0.50, 0.50], index=index)
    fig, _ = equity_curve({"faible": faible, "forte": forte}, log_scale=False)
    assert "forte" in fig.axes[0].get_title()
    _clore(fig)


def test_equity_curve_refuse_un_ensemble_vide() -> None:
    """Sans série, il n'y a rien à tracer."""
    with pytest.raises(ConfigError):
        equity_curve({})


def test_equity_curve_refuse_une_mise_negative() -> None:
    """Une mise de départ nulle ou négative n'a pas de sens en richesse."""
    with pytest.raises(ConfigError):
        equity_curve({"a": _rendements(10)}, initial=0.0)


def test_equity_curve_refuse_une_serie_vide() -> None:
    """Une série sans observation lève l'erreur de données insuffisantes."""
    with pytest.raises(InsufficientDataError):
        equity_curve({"a": pd.Series(dtype="float64")})


@given(
    valeurs=st.lists(
        st.floats(min_value=-0.5, max_value=0.5, allow_nan=False, allow_infinity=False),
        min_size=2,
        max_size=40,
    )
)
@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_propriete_richesse_positive_et_egale_au_produit(valeurs: list[float]) -> None:
    """La richesse reste positive et vaut le produit des facteurs.

    Source (b) : tous les facteurs 1 + r sont dans ]0,5 ; 1,5[, donc leur produit
    est strictement positif, et il égale la richesse rendue par construction.
    """
    index = pd.date_range("2020-01-31", periods=len(valeurs), freq="B")
    r = pd.Series(valeurs, index=index)
    fig, richesse = equity_curve({"p": r})
    colonne = richesse["p"].to_numpy()
    assert np.all(colonne > 0.0)
    np.testing.assert_allclose(colonne, np.cumprod(1.0 + np.asarray(valeurs)), rtol=1e-10)
    _clore(fig)


# ---------------------------------------------------------------------------
# underwater
# ---------------------------------------------------------------------------


def test_underwater_reproduit_le_calcul_a_la_main() -> None:
    """Le repli d'une richesse connue, calculé à la main.

    Source (a). Richesse 100, 120, 90, 110, 150. Sommets 100, 120, 120, 120, 150.
    Replis 0 ; 0 ; 90/120 - 1 = -0,25 ; 110/120 - 1 = -1/12 ; 0.
    """
    index = pd.date_range("2020-01-31", periods=5, freq="ME")
    richesse = pd.Series([100.0, 120.0, 90.0, 110.0, 150.0], index=index)
    fig, repli = underwater(richesse, is_wealth=True)
    attendu = [0.0, 0.0, -0.25, -1.0 / 12.0, 0.0]
    np.testing.assert_allclose(repli.to_numpy(), attendu, atol=1e-15)
    _clore(fig)


def test_underwater_minimum_egale_le_repli_maximal() -> None:
    """Le minimum de la série tracée est le repli maximal.

    Source (b), identité entre la série et son extremum, contrôlée contre
    ``analytics.drawdown.max_drawdown``.
    """
    r = _rendements(400)
    fig, repli = underwater(r)
    assert float(repli.min()) == pytest.approx(max_drawdown(r), rel=1e-12)
    _clore(fig)


def test_underwater_reste_entre_moins_un_et_zero() -> None:
    """Un repli est négatif ou nul, et ne peut pas dépasser cent pour cent.

    Source (b) : la richesse restant positive, le rapport au sommet vit dans
    ]0 ; 1], donc le repli vit dans ]-1 ; 0].
    """
    r = _rendements(300, seed=3, sigma=0.03)
    fig, repli = underwater(r)
    assert repli.max() <= 1e-15
    assert repli.min() > -1.0
    _clore(fig)


def test_underwater_axe_en_points_de_pourcentage() -> None:
    """L'axe écrit « points de pourcentage », et jamais « pt » seul."""
    fig, _ = underwater(_rendements(60))
    etiquette = fig.axes[0].get_ylabel()
    assert "points de pourcentage" in etiquette
    assert "points de %" not in etiquette
    _clore(fig)


def test_underwater_refuse_une_serie_vide() -> None:
    """Sans observation, aucun sommet n'existe."""
    with pytest.raises(InsufficientDataError):
        underwater(pd.Series(dtype="float64"))


# ---------------------------------------------------------------------------
# rolling_metric
# ---------------------------------------------------------------------------


def test_rolling_sharpe_a_fenetre_pleine_egale_le_sharpe_global() -> None:
    """À fenêtre égale à l'échantillon, la dernière valeur est le Sharpe global.

    Source (b), identité : la seule fenêtre fermée est l'échantillon entier.
    """
    r = _rendements(120)
    fig, serie = rolling_metric(r, "sharpe", len(r), frequency=Frequency.DAILY)
    attendu = sharpe_ratio(r, frequency=Frequency.DAILY)
    assert float(serie.iloc[-1]) == pytest.approx(attendu, rel=1e-12)
    assert serie.iloc[:-1].isna().all()
    _clore(fig)


def test_rolling_volatility_egale_l_ecart_type_annualise() -> None:
    """La volatilité glissante égale l'écart type annualisé de la fenêtre.

    Source (a) et (d) : l'écart type est calculé par ``numpy`` avec un degré de
    liberté, puis multiplié par la racine de 252, la convention déclarée de
    ``Frequency.DAILY``.
    """
    r = _rendements(80)
    fenetre = 20
    fig, serie = rolling_metric(r, "volatility", fenetre, frequency=Frequency.DAILY)
    derniere = r.to_numpy()[-fenetre:]
    attendu = float(np.std(derniere, ddof=1)) * math.sqrt(SEANCES_PAR_AN)
    assert float(serie.iloc[-1]) == pytest.approx(attendu, rel=1e-12)
    _clore(fig)


def test_rolling_beta_egale_la_covariance_sur_la_variance() -> None:
    """Le bêta glissant égale le rapport de la covariance à la variance.

    Source (d) : les deux moments sont recalculés par ``numpy`` sur la même
    fenêtre, sans passer par le module testé.
    """
    r = _rendements(80)
    repere = _rendements(80, seed=17)
    fenetre = 30
    fig, serie = rolling_metric(r, "beta", fenetre, benchmark=repere)
    x = repere.to_numpy()[-fenetre:]
    y = r.to_numpy()[-fenetre:]
    attendu = float(np.cov(y, x, ddof=1)[0, 1] / np.var(x, ddof=1))
    assert float(serie.iloc[-1]) == pytest.approx(attendu, rel=1e-10)
    _clore(fig)


def test_rolling_metric_refuse_le_beta_sans_repere() -> None:
    """Le bêta demande un repère, et le dire vaut mieux que rendre des NaN."""
    with pytest.raises(ConfigError):
        rolling_metric(_rendements(60), "beta", 20)


def test_rolling_metric_refuse_une_metrique_inconnue() -> None:
    """Une métrique hors des trois prévues est refusée."""
    with pytest.raises(ConfigError):
        rolling_metric(_rendements(60), "calmar", 20)  # type: ignore[arg-type]


def test_rolling_metric_refuse_une_fenetre_trop_courte() -> None:
    """Une fenêtre d'une seule observation ne définit aucune dispersion."""
    with pytest.raises(ConfigError):
        rolling_metric(_rendements(60), "volatility", 1)


def test_rolling_metric_refuse_un_echantillon_plus_court_que_la_fenetre() -> None:
    """Une fenêtre plus longue que la série ne rend aucune valeur."""
    with pytest.raises(InsufficientDataError):
        rolling_metric(_rendements(10), "volatility", 30)


# ---------------------------------------------------------------------------
# monthly_returns_heatmap
# ---------------------------------------------------------------------------


def test_monthly_heatmap_compose_les_rendements_du_mois() -> None:
    """Deux rendements quotidiens composés donnent le rendement du mois.

    Source (a). Janvier porte +10 % puis -10 % : 1,10 * 0,90 - 1 = -0,01.
    Février porte +50 % puis +50 % : 1,50 * 1,50 - 1 = 1,25.
    """
    index = pd.to_datetime(["2021-01-04", "2021-01-05", "2021-02-01", "2021-02-02"])
    r = pd.Series([0.10, -0.10, 0.50, 0.50], index=index)
    fig, table = monthly_returns_heatmap(r)
    assert float(table.loc[2021, 1]) == pytest.approx(-0.01, abs=1e-15)
    assert float(table.loc[2021, 2]) == pytest.approx(1.25, abs=1e-15)
    _clore(fig)


def test_monthly_heatmap_porte_les_douze_mois() -> None:
    """La grille porte toujours douze colonnes, même sur une année partielle."""
    index = pd.to_datetime(["2021-03-01", "2021-04-01"])
    fig, table = monthly_returns_heatmap(pd.Series([0.01, 0.02], index=index))
    assert list(table.columns) == list(range(1, 13))
    assert table.loc[2021, 1] != table.loc[2021, 1]  # NaN, mois absent
    _clore(fig)


def test_monthly_heatmap_recompose_l_annee() -> None:
    """Le produit des cases d'une année égale le rendement composé de l'année.

    Source (b), identité de la composition sur douze mois consécutifs.
    """
    r = _rendements(500)
    fig, table = monthly_returns_heatmap(r)
    annee = int(table.index[1])
    cases = table.loc[annee].dropna().to_numpy()
    debut = pd.Timestamp(year=annee, month=1, day=1)
    fin = pd.Timestamp(year=annee, month=12, day=31)
    tranche = r.loc[debut:fin].to_numpy()
    assert float(np.prod(1.0 + cases)) == pytest.approx(float(np.prod(1.0 + tranche)), rel=1e-12)
    _clore(fig)


def test_monthly_heatmap_refuse_un_index_sans_dates() -> None:
    """Sans index de dates, aucun mois ne peut être formé."""
    with pytest.raises(DataQualityError):
        monthly_returns_heatmap(pd.Series([0.01, 0.02], index=[0, 1]))


# ---------------------------------------------------------------------------
# return_histogram et qq_plot
# ---------------------------------------------------------------------------


def test_histogramme_effectifs_calcules_a_la_main() -> None:
    """Dix valeurs régulières dans cinq classes donnent deux par classe.

    Source (a). Les valeurs 0 à 9 s'étalent sur 9, donc chaque classe mesure
    1,8. Bornes 0 ; 1,8 ; 3,6 ; 5,4 ; 7,2 ; 9. La première contient 0 et 1, la
    deuxième 2 et 3, la troisième 4 et 5, la quatrième 6 et 7, la dernière 8 et
    9. Chaque effectif vaut donc deux.
    """
    r = pd.Series(np.arange(10, dtype="float64"))
    fig, donnees = return_histogram(r, bins=5, overlay_normal=False)
    assert isinstance(donnees, HistogramData)
    np.testing.assert_array_equal(donnees.counts, [2, 2, 2, 2, 2])
    np.testing.assert_allclose(donnees.edges, [0.0, 1.8, 3.6, 5.4, 7.2, 9.0], atol=1e-12)
    # densité = effectif / (nombre d'observations * largeur) = 2 / (10 * 1,8)
    np.testing.assert_allclose(donnees.density, np.full(5, 2.0 / 18.0), rtol=1e-12)
    _clore(fig)


def test_histogramme_somme_des_effectifs_egale_le_nombre_d_observations() -> None:
    """La somme des effectifs vaut le nombre d'observations.

    Source (b) : les classes couvrent tout l'intervalle et ne se recouvrent pas.
    """
    r = _rendements(500)
    fig, donnees = return_histogram(r, bins=37)
    assert int(donnees.counts.sum()) == len(r)
    _clore(fig)


def test_histogramme_densite_normale_au_point_moyen() -> None:
    """La densité normale ajustée vaut, au point moyen, l'inverse de sigma * racine(2 pi).

    Source (b), identité de la densité normale évaluée en sa moyenne.
    """
    r = _rendements(400)
    fig, donnees = return_histogram(r, bins=20, overlay_normal=True)
    assert donnees.normal_curve is not None
    grille = donnees.normal_curve.index.to_numpy()
    position = int(np.argmin(np.abs(grille - donnees.mean)))
    attendu = 1.0 / (donnees.std * math.sqrt(2.0 * math.pi))
    # la grille ne tombe pas exactement sur la moyenne, d'où la tolérance large
    assert float(donnees.normal_curve.iloc[position]) == pytest.approx(attendu, rel=1e-3)
    assert donnees.mean == pytest.approx(float(np.mean(r.to_numpy())), rel=1e-12)
    assert donnees.std == pytest.approx(float(np.std(r.to_numpy(), ddof=1)), rel=1e-12)
    _clore(fig)


def test_histogramme_sans_superposition_ne_rend_aucune_courbe() -> None:
    """Sans superposition demandée, la courbe normale est absente."""
    fig, donnees = return_histogram(_rendements(50), bins=10, overlay_normal=False)
    assert donnees.normal_curve is None
    _clore(fig)


def test_histogramme_refuse_zero_classe() -> None:
    """Un histogramme sans classe n'existe pas."""
    with pytest.raises(ConfigError):
        return_histogram(_rendements(50), bins=0)


def test_histogramme_refuse_une_seule_observation() -> None:
    """Un point unique ne porte aucune dispersion."""
    with pytest.raises(InsufficientDataError):
        return_histogram(pd.Series([0.01]))


def test_qq_plot_egale_les_quantiles_de_statsmodels() -> None:
    """Les quantiles théoriques égalent ceux de ``statsmodels``.

    Source (d). ``ProbPlot`` réglé sur ``a = 0,5`` emploie la position de tracé
    (i - 0,5) / n, celle de Hazen, la même que le module.

    Contrôle du contrôle, mesuré le 2026-09-02 : ``scipy.stats.probplot``
    emploie une AUTRE position, celle de Filliben, et ses quantiles s'écartent
    des nôtres de 0,106 sur deux cents points. Le test le vérifie aussi, pour
    que personne ne remplace un jour la référence par l'autre en croyant les
    deux interchangeables.
    """
    r = _rendements(200)
    fig, table = qq_plot(r)
    attendu = ProbPlot(r.to_numpy(), a=0.5).theoretical_quantiles
    np.testing.assert_allclose(table["theoretical"].to_numpy(), attendu, rtol=1e-12)
    filliben, _ = stats.probplot(r.to_numpy(), dist="norm", fit=False)
    assert np.max(np.abs(filliben - attendu)) > 0.1
    _clore(fig)


def test_qq_plot_echantillon_centre_et_reduit() -> None:
    """L'échantillon tracé est centré et réduit.

    Source (b) : par construction, sa moyenne vaut zéro et son écart type un.
    """
    r = _rendements(300)
    fig, table = qq_plot(r)
    valeurs = table["sample"].to_numpy()
    assert float(np.mean(valeurs)) == pytest.approx(0.0, abs=1e-12)
    assert float(np.std(valeurs, ddof=1)) == pytest.approx(1.0, rel=1e-12)
    assert np.all(np.diff(valeurs) >= -1e-15)
    _clore(fig)


def test_qq_plot_refuse_un_echantillon_constant() -> None:
    """Une série constante n'a pas d'écart type, donc pas de réduction."""
    with pytest.raises(DataQualityError):
        qq_plot(pd.Series([0.01] * 20))


# ---------------------------------------------------------------------------
# quantile_bars et ic_timeseries
# ---------------------------------------------------------------------------


def test_quantile_bars_moyennes_a_la_main() -> None:
    """Les moyennes par quantile, calculées à la main.

    Source (a). Q1 vaut (1 % + 3 %) / 2 = 2 %. Q2 vaut (2 % + 6 %) / 2 = 4 %.
    L'écart moyen vaut (1 % + 3 %) / 2 = 2 %.
    """
    index = pd.date_range("2020-01-31", periods=2, freq="ME")
    frame = pd.DataFrame({"Q1": [0.01, 0.03], "Q2": [0.02, 0.06], "spread": [0.01, 0.03]}, index=index)
    fig, donnees = quantile_bars(frame)
    assert float(donnees.means["Q1"]) == pytest.approx(0.02, abs=1e-15)
    assert float(donnees.means["Q2"]) == pytest.approx(0.04, abs=1e-15)
    assert donnees.spread_mean == pytest.approx(0.02, abs=1e-15)
    assert donnees.monotone is True
    assert "spread" not in donnees.means.index
    _clore(fig)


def test_quantile_bars_detecte_la_non_monotonie() -> None:
    """Un tri dont le deuxième quantile bat le troisième n'est pas monotone.

    Source (a) : les moyennes valent 1 %, 5 % puis 3 %, donc la suite décroît.
    """
    frame = pd.DataFrame({"Q1": [0.01], "Q2": [0.05], "Q3": [0.03]})
    fig, donnees = quantile_bars(frame)
    assert donnees.monotone is False
    assert donnees.spread_mean is None
    _clore(fig)


def test_quantile_bars_refuse_un_tableau_vide() -> None:
    """Sans date, aucune moyenne n'est définie."""
    with pytest.raises(InsufficientDataError):
        quantile_bars(pd.DataFrame({"Q1": pd.Series(dtype="float64")}))


def test_quantile_bars_refuse_un_tableau_sans_quantile() -> None:
    """Un tableau réduit à sa colonne d'écart ne porte aucun quantile."""
    with pytest.raises(ConfigError):
        quantile_bars(pd.DataFrame({"spread": [0.01, 0.02]}))


def test_ic_timeseries_moyenne_mobile_a_la_main() -> None:
    """La moyenne mobile sur trois dates, calculée à la main.

    Source (a). Sur 1 ; 2 ; 3 ; 4, la moyenne des trois dernières vaut 3.
    Celle des trois premières vaut 2.
    """
    index = pd.date_range("2020-01-31", periods=4, freq="ME")
    ic = pd.Series([1.0, 2.0, 3.0, 4.0], index=index)
    fig, table = ic_timeseries(ic, window=3)
    assert list(table.columns) == ["ic", "rolling_mean"]
    assert float(table["rolling_mean"].iloc[2]) == pytest.approx(2.0, abs=1e-15)
    assert float(table["rolling_mean"].iloc[3]) == pytest.approx(3.0, abs=1e-15)
    assert table["rolling_mean"].iloc[:2].isna().all()
    _clore(fig)


def test_ic_timeseries_conserve_la_serie_d_origine() -> None:
    """La colonne des coefficients est celle reçue, sans transformation."""
    ic = pd.Series([0.02, -0.01, 0.05], index=pd.date_range("2020-01-31", periods=3, freq="ME"))
    fig, table = ic_timeseries(ic, window=2)
    np.testing.assert_allclose(table["ic"].to_numpy(), ic.to_numpy(), rtol=1e-15)
    _clore(fig)


def test_ic_timeseries_refuse_une_fenetre_d_une_date() -> None:
    """Une moyenne mobile sur une date n'est pas une moyenne mobile."""
    ic = pd.Series([0.02, 0.01], index=pd.date_range("2020-01-31", periods=2, freq="ME"))
    with pytest.raises(ConfigError):
        ic_timeseries(ic, window=1)


def test_ic_timeseries_refuse_une_serie_vide() -> None:
    """Une série sans valeur observée ne se trace pas."""
    with pytest.raises(InsufficientDataError):
        ic_timeseries(pd.Series([np.nan, np.nan]), window=2)


# ---------------------------------------------------------------------------
# parameter_heatmap, cost_sensitivity, subperiod_bars, correlation_heatmap
# ---------------------------------------------------------------------------


def test_parameter_heatmap_reprend_chaque_ligne_du_balayage() -> None:
    """Chaque case pivote vers la ligne qui porte le même couple.

    Source (a). Le balayage porte la métrique a / 10 + b / 100, donc la case
    (a = 2, b = 30) vaut 0,2 + 0,3 = 0,5.
    """
    lignes = [
        {"lookback": a, "seuil": b, "sharpe_net": a / 10.0 + b / 100.0} for a in (1, 2, 3) for b in (10, 30)
    ]
    balayage = pd.DataFrame(lignes)
    fig, table = parameter_heatmap(balayage, "lookback", "seuil", "sharpe_net")
    assert table.shape == (2, 3)
    assert float(table.loc[30, 2]) == pytest.approx(0.5, abs=1e-15)
    assert float(table.loc[10, 1]) == pytest.approx(0.2, abs=1e-15)
    _clore(fig)


def test_parameter_heatmap_etiquettes_sans_nom_de_cle() -> None:
    """Les axes portent une étiquette lisible, pas le nom brut de la colonne."""
    balayage = pd.DataFrame({"look_back": [1, 2], "seuil": [10, 10], "m": [0.1, 0.2]})
    fig, _ = parameter_heatmap(balayage, "look_back", "seuil", "m", metric_label="Ratio net")
    assert fig.axes[0].get_xlabel() == "Look back"
    assert "Ratio net" in fig.axes[0].get_title()
    _clore(fig)


def test_parameter_heatmap_refuse_un_couple_en_double() -> None:
    """Deux lignes au même couple rendraient une case ambiguë."""
    balayage = pd.DataFrame({"x": [1, 1], "y": [2, 2], "m": [0.1, 0.9]})
    with pytest.raises(DataQualityError):
        parameter_heatmap(balayage, "x", "y", "m")


def test_parameter_heatmap_refuse_une_colonne_absente() -> None:
    """Une colonne demandée qui n'existe pas arrête l'appel."""
    balayage = pd.DataFrame({"x": [1], "y": [2], "m": [0.1]})
    with pytest.raises(ConfigError):
        parameter_heatmap(balayage, "x", "y", "absent")


def test_cost_sensitivity_interpole_le_point_de_rupture() -> None:
    """Le point de rupture, interpolé à la main entre deux multiples.

    Source (a). La métrique vaut 0,4 au multiple 2 et -0,2 au multiple 3. Le
    seuil zéro est franchi à 2 + 1 * 0,4 / (0,4 + 0,2) = 2 + 2/3 = 2,6667.
    """
    fig, analyse = cost_sensitivity([1.0, 2.0, 3.0], [1.0, 0.4, -0.2])
    assert analyse.breakeven_multiplier == pytest.approx(2.0 + 2.0 / 3.0, rel=1e-12)
    assert analyse.status == "bracketed"
    assert analyse.monotone is True
    np.testing.assert_allclose(analyse.table["metric"].to_numpy(), [1.0, 0.4, -0.2], rtol=1e-15)
    _clore(fig)


def test_cost_sensitivity_survit_a_tous_les_multiples() -> None:
    """Une métrique toujours au-dessus du seuil n'a pas de point de rupture."""
    fig, analyse = cost_sensitivity([1.0, 2.0, 5.0], [1.5, 1.2, 0.8])
    assert analyse.breakeven_multiplier is None
    assert analyse.status == "survives_all"
    assert "survit" in fig.axes[0].get_title()
    _clore(fig)


def test_cost_sensitivity_refuse_des_longueurs_differentes() -> None:
    """Un multiple sans métrique laisse une case vide, ce qui est refusé."""
    with pytest.raises(ConfigError):
        cost_sensitivity([1.0, 2.0], [0.5])


def test_cost_sensitivity_refuse_des_multiples_decroissants() -> None:
    """Des multiples mal ordonnés rendraient l'interpolation fausse."""
    with pytest.raises(ConfigError):
        cost_sensitivity([2.0, 1.0], [0.5, 0.9])


def test_subperiod_bars_intervalle_calcule_a_la_main() -> None:
    """Les bornes valent la métrique plus ou moins 1,96 erreur type.

    Source (c) pour le quantile 1,959963984540054, et (a) pour le calcul :
    1,00 plus ou moins 1,96 * 0,30 donne 0,4120 et 1,5880.
    """
    tranches = pd.DataFrame(
        {"label": ["2008-2012", "2013-2020"], "sharpe": [1.0, -0.5], "sharpe_se_lo": [0.3, 0.4]}
    )
    fig, table = subperiod_bars(tranches)
    assert list(table.columns) == ["label", "metric", "ci_low", "ci_high"]
    assert float(table["ci_low"].iloc[0]) == pytest.approx(1.0 - Z_97_5 * 0.3, rel=1e-12)
    assert float(table["ci_high"].iloc[0]) == pytest.approx(1.0 + Z_97_5 * 0.3, rel=1e-12)
    assert float(table["ci_low"].iloc[1]) == pytest.approx(-0.5 - Z_97_5 * 0.4, rel=1e-12)
    _clore(fig)


def test_subperiod_bars_sans_erreur_type_donne_un_intervalle_nul() -> None:
    """Sans colonne d'erreur, les deux bornes rejoignent la métrique."""
    tranches = pd.DataFrame({"label": ["A"], "sharpe": [0.7]})
    fig, table = subperiod_bars(tranches, error_column=None)
    assert float(table["ci_low"].iloc[0]) == pytest.approx(0.7, abs=1e-15)
    assert float(table["ci_high"].iloc[0]) == pytest.approx(0.7, abs=1e-15)
    _clore(fig)


def test_subperiod_bars_refuse_un_niveau_hors_bornes() -> None:
    """Un niveau de confiance de un ou plus n'a pas de quantile fini."""
    tranches = pd.DataFrame({"label": ["A"], "sharpe": [0.7], "sharpe_se_lo": [0.2]})
    with pytest.raises(ConfigError):
        subperiod_bars(tranches, confidence=1.0)


def test_subperiod_bars_refuse_un_tableau_vide() -> None:
    """Sans tranche, il n'y a rien à comparer."""
    with pytest.raises(InsufficientDataError):
        subperiod_bars(pd.DataFrame({"label": [], "sharpe": [], "sharpe_se_lo": []}))


def test_correlation_heatmap_paire_affine_vaut_un() -> None:
    """Une paire parfaitement affine croissante donne une corrélation de un.

    Source (b), identité : la corrélation est invariante par transformation
    affine croissante, donc y = 3 x + 2 rend exactement un.
    """
    x = _rendements(80)
    frame = pd.DataFrame({"x": x.to_numpy(), "y": 3.0 * x.to_numpy() + 2.0})
    fig, matrice = correlation_heatmap(frame)
    assert float(matrice.to_numpy()[0, 1]) == pytest.approx(1.0, abs=1e-12)
    _clore(fig)


def test_correlation_heatmap_diagonale_et_symetrie() -> None:
    """La diagonale vaut un et la matrice est symétrique.

    Source (b), deux propriétés définitionnelles de la corrélation.
    """
    rng = make_generator(23)
    frame = pd.DataFrame(rng.normal(size=(120, 4)), columns=["a", "b", "c", "d"])
    fig, matrice = correlation_heatmap(frame)
    valeurs = matrice.to_numpy()
    np.testing.assert_allclose(np.diag(valeurs), np.ones(4), atol=1e-12)
    np.testing.assert_allclose(valeurs, valeurs.T, atol=1e-12)
    _clore(fig)


def test_correlation_heatmap_accepte_des_etiquettes_lisibles() -> None:
    """Les étiquettes fournies remplacent les noms de colonnes."""
    rng = make_generator(29)
    frame = pd.DataFrame(rng.normal(size=(30, 2)), columns=["mom_12_1", "val_bm"])
    fig, matrice = correlation_heatmap(frame, labels=["Momentum", "Valeur"])
    assert list(matrice.columns) == ["Momentum", "Valeur"]
    _clore(fig)


def test_correlation_heatmap_refuse_une_seule_colonne() -> None:
    """Une seule série ne forme aucune paire."""
    with pytest.raises(InsufficientDataError):
        correlation_heatmap(pd.DataFrame({"a": [1.0, 2.0, 3.0]}))


def test_correlation_heatmap_refuse_des_etiquettes_mal_comptees() -> None:
    """Le nombre d'étiquettes doit égaler le nombre de colonnes."""
    frame = pd.DataFrame({"a": [1.0, 2.0], "b": [2.0, 1.0]})
    with pytest.raises(ConfigError):
        correlation_heatmap(frame, labels=["une seule"])


# ---------------------------------------------------------------------------
# save_figure et feuille de style
# ---------------------------------------------------------------------------


def test_save_figure_ecrit_deux_fichiers_non_vides(tmp_path) -> None:
    """L'enregistrement produit un PNG et un PDF, tous deux non vides.

    Source (a) : les deux signatures de fichier sont celles des formats, le
    PNG commençant par les octets 0x89 P N G et le PDF par « %PDF ».
    """
    fig, _ = underwater(_rendements(60))
    ecrits = save_figure(fig, tmp_path / "repli")
    assert [c.suffix for c in ecrits] == [".png", ".pdf"]
    assert all(c.exists() and c.stat().st_size > 0 for c in ecrits)
    assert ecrits[0].read_bytes()[:4] == b"\x89PNG"
    assert ecrits[1].read_bytes()[:4] == b"%PDF"
    _clore(fig)


def test_save_figure_retire_une_extension_donnee(tmp_path) -> None:
    """Une extension dans le chemin est retirée, les deux formes étant écrites."""
    fig, _ = underwater(_rendements(30))
    ecrits = save_figure(fig, tmp_path / "courbe.png")
    assert {c.name for c in ecrits} == {"courbe.png", "courbe.pdf"}
    _clore(fig)


def test_save_figure_sans_vectoriel_n_ecrit_que_le_png(tmp_path) -> None:
    """Sans PDF demandé, un seul fichier est écrit."""
    fig, _ = underwater(_rendements(30))
    ecrits = save_figure(fig, tmp_path / "png_seul", vector=False)
    assert len(ecrits) == 1
    assert ecrits[0].suffix == ".png"
    _clore(fig)


def test_save_figure_cree_le_dossier(tmp_path) -> None:
    """Un dossier absent est créé plutôt que de faire échouer l'écriture."""
    fig, _ = underwater(_rendements(30))
    cible = tmp_path / "rapport" / "figures" / "repli"
    ecrits = save_figure(fig, cible)
    assert all(c.exists() for c in ecrits)
    _clore(fig)


def test_la_feuille_de_style_ne_fuit_pas() -> None:
    """Les réglages posés par le module sont retirés à la sortie du contexte.

    Source (b) : le contexte de Matplotlib restaure l'état d'origine, et la
    fabrique n'écrit rien en dehors de lui.
    """
    avant = mpl.rcParams.copy()
    fig, _ = equity_curve({"a": _rendements(40)})
    _clore(fig)
    changees = [c for c in avant if repr(mpl.rcParams[c]) != repr(avant[c])]
    assert not changees, f"réglages modifiés hors contexte : {changees}"


def test_la_feuille_de_style_pose_la_palette_du_portefeuille() -> None:
    """Dans le contexte, la légende perd son cadre et la palette est celle de gvf.

    Source (d) : les deux valeurs attendues sont lues dans ``gvf.style``, la
    feuille commune du portefeuille, et non écrites en dur ici.
    """
    from gvf import style as gvf_style

    with portfolio_style():
        assert mpl.rcParams["legend.frameon"] is False
        couleurs = [d["color"] for d in mpl.rcParams["axes.prop_cycle"]]
    assert couleurs == gvf_style.OKABE_ITO


def test_les_axes_ecrivent_la_virgule_decimale() -> None:
    """Le formateur d'axe écrit 0,50 et non 0.50, convention française.

    Source (d) : la mise en forme vient de ``gvf.style.fr``.
    """
    fig, _ = equity_curve({"a": _rendements(40)}, log_scale=False)
    formate = fig.axes[0].yaxis.get_major_formatter()(0.5, 0)
    assert formate == "0,50"
    _clore(fig)


# ---------------------------------------------------------------------------
# Fuite temporelle : ce que le futur ne doit pas changer
#
# Le contrôle est toujours le même. On calcule la figure sur une série, puis sur
# la MÊME série dont toutes les observations postérieures à une date de coupure
# ont été remplacées. Une fenêtre fermée à droite ne lit rien après sa dernière
# observation, donc les deux courbes doivent coïncider EXACTEMENT avant la
# coupure. Source (b), identité : une fonction des observations
# t - w + 1 à t ne dépend d'aucune observation postérieure à t.
# ---------------------------------------------------------------------------

#: L'indice de coupure des tests de fuite temporelle, en observations.
COUPURE = 200


def _saccager_le_futur(serie: pd.Series, coupure: int = COUPURE, seed: int = 99) -> pd.Series:
    """Rend la série dont tout ce qui suit ``coupure`` est remplacé par du bruit.

    Le bruit est cent fois plus dispersé que l'original et centré ailleurs, si
    bien qu'aucune coïncidence numérique ne peut sauver une fenêtre fautive.
    """
    rng = make_generator(seed)
    saccagee = serie.copy()
    saccagee.iloc[coupure:] = rng.normal(0.05, 0.20, len(serie) - coupure)
    return saccagee


@pytest.mark.parametrize("metrique", ["sharpe", "volatility"])
def test_rolling_metric_ne_lit_pas_le_futur(metrique: str) -> None:
    """Saccager le futur laisse la courbe glissante intacte avant la coupure."""
    r = _rendements(300)
    fig_a, avant = rolling_metric(r, metrique, 50)
    fig_b, apres = rolling_metric(_saccager_le_futur(r), metrique, 50)
    ecart = (avant - apres).iloc[:COUPURE].abs().to_numpy()
    assert np.nanmax(ecart) == 0.0, f"{metrique} lit le futur"
    # Contrôle du contrôle : après la coupure, les deux courbes DOIVENT différer,
    # sans quoi le saccage n'aurait rien changé et le test ne prouverait rien.
    assert np.nanmax((avant - apres).iloc[COUPURE + 50 :].abs().to_numpy()) > 0.0
    _clore(fig_a)
    _clore(fig_b)


def test_rolling_beta_ne_lit_pas_le_futur() -> None:
    """Le bêta glissant ne dépend d'aucune observation postérieure à sa date."""
    r = _rendements(300)
    repere = _rendements(300, seed=41)
    fig_a, avant = rolling_metric(r, "beta", 50, benchmark=repere)
    fig_b, apres = rolling_metric(_saccager_le_futur(r), "beta", 50, benchmark=repere)
    assert np.nanmax((avant - apres).iloc[:COUPURE].abs().to_numpy()) == 0.0
    assert np.nanmax((avant - apres).iloc[COUPURE + 50 :].abs().to_numpy()) > 0.0
    _clore(fig_a)
    _clore(fig_b)


def test_rolling_metric_ne_centre_pas_sa_fenetre() -> None:
    """La première valeur calculable tombe à la ``window``-ième observation.

    Source (a) : une fenêtre centrée rendrait sa première valeur au milieu de la
    première fenêtre, donc à l'indice ``window // 2``, et laisserait des valeurs
    manquantes à la FIN. Le test vérifie les deux extrémités.
    """
    r = _rendements(120)
    fenetre = 30
    fig, serie = rolling_metric(r, "volatility", fenetre)
    assert serie.iloc[: fenetre - 1].isna().all()
    assert bool(np.isfinite(serie.iloc[fenetre - 1]))
    assert serie.iloc[fenetre - 1 :].notna().all()
    _clore(fig)


def test_ic_timeseries_ne_lit_pas_le_futur() -> None:
    """La moyenne mobile du coefficient d'information reste fermée à droite."""
    rng = make_generator(7)
    index = pd.date_range("2010-01-31", periods=120, freq="ME")
    ic = pd.Series(rng.normal(0.02, 0.10, 120), index=index)
    saccagee = ic.copy()
    saccagee.iloc[60:] = 9.0
    fig_a, avant = ic_timeseries(ic, window=12)
    fig_b, apres = ic_timeseries(saccagee, window=12)
    ecart = (avant["rolling_mean"] - apres["rolling_mean"]).iloc[:60].abs().to_numpy()
    assert np.nanmax(ecart) == 0.0
    assert float(apres["rolling_mean"].iloc[-1]) == pytest.approx(9.0, abs=1e-12)
    _clore(fig_a)
    _clore(fig_b)


def test_equity_curve_ne_remplit_pas_vers_l_arriere() -> None:
    """Une série qui commence tard garde ses cases vides avant son départ.

    Source (a) : un remplissage vers l'arrière ferait apparaître la richesse de
    « tardive » avant sa première observation, ce qui est de l'information
    future portée dans le passé.
    """
    index = pd.date_range("2020-01-31", periods=4, freq="ME")
    tot = pd.Series([0.10, 0.10, 0.10, 0.10], index=index)
    tardive = pd.Series([0.50, 0.50], index=index[2:])
    fig, richesse = equity_curve({"tot": tot, "tardive": tardive}, initial=100.0, log_scale=False)
    assert richesse["tardive"].iloc[:2].isna().all()
    np.testing.assert_allclose(richesse["tardive"].iloc[2:].to_numpy(), [150.0, 225.0], rtol=1e-12)
    _clore(fig)


@given(
    valeurs=st.lists(
        st.floats(min_value=-0.2, max_value=0.2, allow_nan=False, allow_infinity=False),
        min_size=30,
        max_size=60,
    ),
    coupure=st.integers(min_value=15, max_value=25),
)
@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_propriete_volatilite_glissante_insensible_au_futur(valeurs: list[float], coupure: int) -> None:
    """Sur n'importe quelle série, le futur ne déplace pas la volatilité passée.

    Source (b), identité : l'écart type des observations t - w + 1 à t ne
    dépend d'aucune observation postérieure à t.
    """
    index = pd.date_range("2020-01-31", periods=len(valeurs), freq="B")
    r = pd.Series(valeurs, index=index)
    modifiee = r.copy()
    modifiee.iloc[coupure:] = 0.5
    fig_a, avant = rolling_metric(r, "volatility", 10)
    fig_b, apres = rolling_metric(modifiee, "volatility", 10)
    ecart = (avant - apres).iloc[:coupure].abs().to_numpy()
    assert np.nanmax(ecart) == 0.0
    _clore(fig_a)
    _clore(fig_b)


# ---------------------------------------------------------------------------
# Les défauts trouvés par la vérification adversariale du 2026-09-02
# ---------------------------------------------------------------------------


def test_equity_curve_refuse_un_repere_qui_porte_le_nom_d_une_strategie() -> None:
    """Un repère homonyme écrasait la stratégie sans rien dire.

    Source (a), défaut mesuré le 2026-09-02. Trois mois à +10 % mènent à 1,331 ;
    trois mois à 0 % mènent à 1,000. Avant correction, le tableau rendu ne
    portait qu'une colonne « strat » valant 1,000, donc la courbe du repère
    publiée sous le nom de la stratégie.
    """
    index = pd.date_range("2020-01-31", periods=3, freq="ME")
    strategie = pd.Series([0.10, 0.10, 0.10], index=index)
    repere = pd.Series([0.0, 0.0, 0.0], index=index, name="strat")
    with pytest.raises(ConfigError, match="strat"):
        equity_curve({"strat": strategie}, benchmark=repere)


def test_equity_curve_garde_les_deux_courbes_avec_une_etiquette_distincte() -> None:
    """Avec une étiquette distincte, les deux courbes survivent.

    Source (a) : 1,10^3 = 1,331 pour la stratégie, 1,000 pour le repère plat.
    """
    index = pd.date_range("2020-01-31", periods=3, freq="ME")
    strategie = pd.Series([0.10, 0.10, 0.10], index=index)
    repere = pd.Series([0.0, 0.0, 0.0], index=index, name="strat")
    fig, richesse = equity_curve({"strat": strategie}, benchmark=repere, benchmark_label="Repère")
    assert list(richesse.columns) == ["strat", "Repère"]
    assert float(richesse["strat"].iloc[-1]) == pytest.approx(1.331, abs=1e-12)
    assert float(richesse["Repère"].iloc[-1]) == pytest.approx(1.0, abs=1e-12)
    _clore(fig)


def test_equity_curve_n_annonce_pas_une_date_de_base_commune_qui_est_fausse() -> None:
    """Quand les courbes démarrent à des dates différentes, l'axe le dit.

    Source (a), défaut mesuré le 2026-09-02. La courbe « tardive » reçoit sa
    mise le 2020-03-31, alors que l'axe annonçait « base 100,00 $ CA au
    2020-01-31 » pour les deux.
    """
    index = pd.date_range("2020-01-31", periods=4, freq="ME")
    tot = pd.Series([0.10] * 4, index=index)
    tardive = pd.Series([0.50] * 2, index=index[2:])
    fig, _ = equity_curve({"tot": tot, "tardive": tardive}, initial=100.0, log_scale=False)
    etiquette = fig.axes[0].get_ylabel()
    assert "au 2020-01-31" not in etiquette
    assert "départ de chaque courbe" in etiquette
    assert "dates de base différentes" in fig.axes[0].get_title()
    _clore(fig)


def test_equity_curve_garde_la_date_de_base_quand_les_courbes_partagent_leur_depart() -> None:
    """Deux courbes de même départ gardent l'annonce de la date de base."""
    index = pd.date_range("2020-01-31", periods=4, freq="ME")
    fig, _ = equity_curve(
        {"a": pd.Series([0.10] * 4, index=index), "b": pd.Series([0.02] * 4, index=index)},
        initial=100.0,
        log_scale=False,
    )
    assert "au 2020-01-31" in fig.axes[0].get_ylabel()
    assert "dates de base différentes" not in fig.axes[0].get_title()
    _clore(fig)


def test_rolling_sharpe_rend_une_valeur_manquante_sur_une_fenetre_constante() -> None:
    """Une fenêtre sans dispersion ne fait plus échouer le tracé entier.

    Source (a) : la série porte trente rendements strictement nuls au milieu.
    Toute fenêtre de dix entièrement contenue dans ce bloc n'a pas d'écart type,
    donc pas de ratio de Sharpe, et il en existe exactement 30 - 10 + 1 = 21.
    Les fenêtres à cheval sur le bloc gardent, elles, une dispersion.
    """
    rng = make_generator(13)
    index = pd.date_range("2020-01-01", periods=110, freq="B")
    valeurs = np.concatenate([rng.normal(0.001, 0.01, 40), np.zeros(30), rng.normal(0.001, 0.01, 40)])
    fig, serie = rolling_metric(pd.Series(valeurs, index=index), "sharpe", 10)
    calculables = serie.iloc[9:]
    assert int(calculables.isna().sum()) == 21
    assert int(calculables.notna().sum()) == len(calculables) - 21
    _clore(fig)


def test_monthly_heatmap_refuse_une_serie_plus_fine_declaree_mensuelle() -> None:
    """Deux dates dans le même mois rendaient une erreur brute de pandas.

    Source (a), défaut mesuré le 2026-09-02 : la fabrique laissait sortir
    ``ValueError: Index contains duplicate entries``, hors de la taxonomie du
    dépôt et sans nommer la cause.
    """
    r = pd.Series([0.01, 0.02], index=pd.to_datetime(["2021-01-04", "2021-01-05"]))
    with pytest.raises(DataQualityError, match="même mois"):
        monthly_returns_heatmap(r, already_monthly=True)


def test_correlation_heatmap_refuse_une_colonne_de_texte() -> None:
    """Une colonne non numérique donnait un ``ValueError`` de conversion."""
    frame = pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [3.0, 2.0, 1.0], "c": ["x", "y", "z"]})
    with pytest.raises(DataQualityError, match="non numériques"):
        correlation_heatmap(frame)


def test_correlation_heatmap_refuse_une_colonne_constante() -> None:
    """Une colonne sans dispersion publiait un titre portant « nan ».

    Source (a), défaut mesuré le 2026-09-02. La corrélation d'une constante
    n'existe pas, son dénominateur étant nul. La fabrique rendait une matrice
    dont trois cases sur quatre étaient manquantes. Le titre annonçait alors
    « moyenne hors diagonale nan et maximum nan », en émettant au passage deux
    avertissements de numpy que l'appelant ne voyait pas.
    """
    frame = pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [1.0, 1.0, 1.0]})
    with pytest.raises(DataQualityError, match="sans dispersion"):
        correlation_heatmap(frame)


def test_correlation_heatmap_n_emet_aucun_avertissement() -> None:
    """Sur une entrée saine, aucune alerte de numpy ne remonte."""
    rng = make_generator(31)
    frame = pd.DataFrame(rng.normal(size=(60, 3)), columns=["a", "b", "c"])
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        fig, _ = correlation_heatmap(frame)
    _clore(fig)


@pytest.mark.parametrize(
    ("erreur", "motif"), [(-0.3, "négative"), (float("nan"), "non finie"), (float("inf"), "non finie")]
)
def test_subperiod_bars_refuse_une_erreur_type_invalide(erreur: float, motif: str) -> None:
    """Une erreur type négative renversait l'intervalle, une NaN l'effaçait.

    Source (a), défaut mesuré le 2026-09-02. Avec une erreur type de -0,3 et un
    ratio de 1,0, les bornes rendues valaient 1,588 en bas et 0,412 en haut,
    donc ci_low au-dessus de ci_high, puis Matplotlib levait un ``ValueError``.
    """
    tranches = pd.DataFrame({"label": ["A"], "sharpe": [1.0], "sharpe_se_lo": [erreur]})
    with pytest.raises(DataQualityError, match=motif):
        subperiod_bars(tranches)


def test_quantile_bars_refuse_un_quantile_sans_moyenne() -> None:
    """Un quantile entièrement manquant faisait conclure à la non-monotonie.

    Source (a), défaut mesuré le 2026-09-02. Toute comparaison à une valeur
    manquante rend faux, donc ``np.diff`` sur [nan ; 0,015] rendait faux et le
    titre annonçait « progression irrégulière » à partir d'un trou.
    """
    frame = pd.DataFrame({"Q1": [np.nan, np.nan], "Q2": [0.01, 0.02]})
    with pytest.raises(DataQualityError, match="Q1"):
        quantile_bars(frame)


def test_parameter_heatmap_ne_compte_que_les_cases_mesurees() -> None:
    """Le titre compte les combinaisons du balayage, pas les cases du tableau.

    Source (a), défaut mesuré le 2026-09-02. Une grille de 3 par 3 privée d'un
    couple porte 8 lignes et 9 cases ; le titre annonçait 9 combinaisons.
    """
    lignes = [{"x": a, "y": b, "m": float(a + b)} for a in range(3) for b in range(3) if (a, b) != (1, 1)]
    balayage = pd.DataFrame(lignes)
    assert len(balayage) == 8
    fig, table = parameter_heatmap(balayage, "x", "y", "m")
    assert table.size == 9
    assert "8 combinaisons" in fig.axes[0].get_title()
    _clore(fig)


def test_parameter_heatmap_ouvre_toute_l_echelle_sur_une_metrique_d_un_seul_signe() -> None:
    """Une métrique qui ne change pas de signe occupe toute la rampe.

    Source (a), défaut mesuré le 2026-09-02. La métrique vaut 0,80 + 0,02 a +
    0,04 b, donc elle va de 0,80 à 1,04. L'échelle symétrique allait de -1,04 à
    1,04, et les données n'en couvraient que 0,24 / 2,08 = 11,5 pour cent.
    """
    lignes = [{"x": a, "y": b, "m": 0.80 + 0.02 * a + 0.04 * b} for a in range(5) for b in range(5)]
    fig, table = parameter_heatmap(pd.DataFrame(lignes), "x", "y", "m")
    basse, haute = fig.axes[0].images[0].get_clim()
    assert basse == pytest.approx(0.80, abs=1e-12)
    assert haute == pytest.approx(1.04, abs=1e-12)
    assert float(table.to_numpy().min()) == pytest.approx(0.80, abs=1e-12)
    assert float(table.to_numpy().max()) == pytest.approx(1.04, abs=1e-12)
    _clore(fig)


def test_parameter_heatmap_reste_symetrique_quand_la_metrique_change_de_signe() -> None:
    """Une métrique qui traverse zéro garde une échelle centrée sur zéro.

    Source (a) : les valeurs vont de -0,4 à 1,2, donc l'échelle va de -1,2 à
    1,2 et le blanc du centre marque bien le zéro.
    """
    lignes = [
        {"x": 1, "y": 1, "m": -0.4},
        {"x": 1, "y": 2, "m": 0.3},
        {"x": 2, "y": 1, "m": 1.2},
        {"x": 2, "y": 2, "m": 0.0},
    ]
    fig, _ = parameter_heatmap(pd.DataFrame(lignes), "x", "y", "m")
    basse, haute = fig.axes[0].images[0].get_clim()
    assert basse == pytest.approx(-1.2, abs=1e-12)
    assert haute == pytest.approx(1.2, abs=1e-12)
    _clore(fig)


def test_ic_timeseries_dessine_des_barres_a_la_largeur_du_pas() -> None:
    """La largeur d'une barre suit le pas de l'index, en jours.

    Source (a), défaut mesuré le 2026-09-02. Matplotlib compte les abscisses
    d'un index de dates en jours. Une largeur fixe de 0,8 couvrait 0,8 jour sur
    un pas hebdomadaire de sept jours, soit 11 pour cent de l'intervalle, et
    2,9 pour cent sur un pas mensuel. Sur un pas de sept jours, la largeur
    attendue vaut 0,8 * 7 = 5,6 jours.
    """
    rng = make_generator(17)
    index = pd.date_range("2020-01-03", periods=60, freq="W-FRI")
    ic = pd.Series(rng.normal(0.02, 0.05, 60), index=index)
    fig, _ = ic_timeseries(ic, window=8)
    assert fig.axes[0].patches[0].get_width() == pytest.approx(5.6, abs=1e-12)
    _clore(fig)


def test_ic_timeseries_garde_une_largeur_unitaire_sans_index_de_dates() -> None:
    """Sans index de dates, la largeur reste la fraction par défaut.

    Source (a) : sur un index d'entiers, l'intervalle entre deux barres vaut un,
    et la largeur vaut donc 0,8.
    """
    ic = pd.Series([0.01, 0.02, -0.01, 0.03, 0.00, 0.02], index=range(6))
    fig, _ = ic_timeseries(ic, window=2)
    assert fig.axes[0].patches[0].get_width() == pytest.approx(0.8, abs=1e-12)
    _clore(fig)

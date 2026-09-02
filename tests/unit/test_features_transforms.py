"""Contrôles de ``quantlab.features.transforms``.

Aucune valeur attendue de ce fichier ne vient de la sortie du code. Chacune
porte sa source en commentaire : (a) calcul à la main, (b) identité
mathématique, (c) valeur publiée, (d) implémentation indépendante.

Le contrôle central du module est ``assert_causal``. Il est lui-même testé dans
les deux sens : il doit accepter chaque caractéristique du module, et il doit
REFUSER un ``shift(-1)`` introduit exprès. Un contrôle qui ne refuse rien ne
contrôle rien.
"""

from __future__ import annotations

import math
from functools import partial

import hypothesis.strategies as st
import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from scipy import stats

from quantlab.analytics.drawdown import drawdown_series
from quantlab.core.errors import (
    ConfigError,
    DataQualityError,
    InsufficientDataError,
    LookAheadError,
)
from quantlab.core.types import Frequency, ReturnKind
from quantlab.features import transforms
from quantlab.features.transforms import (
    assert_causal,
    drawdown_feature,
    equivalent_window,
    ewma_volatility,
    forward_return,
    halflife_to_lambda,
    lag,
    lambda_to_halflife,
    momentum,
    percent_rank,
    realized_volatility,
    rolling_max,
    rolling_mean,
    rolling_min,
    rolling_std,
    rolling_sum,
    time_series_momentum_signal,
    zscore_time_series,
)


def _dates(n: int) -> pd.DatetimeIndex:
    """Rend un index mensuel de fin de mois, régulier et croissant."""
    return pd.date_range("2020-01-31", periods=n, freq="ME")


def _series(*values: float, name: str | None = None) -> pd.Series:
    """Rend une série indexée par le temps depuis des valeurs écrites à la main."""
    return pd.Series(list(values), index=_dates(len(values)), dtype=float, name=name)


def _frame(**columns: list[float]) -> pd.DataFrame:
    """Rend un tableau indexé par le temps depuis des colonnes écrites à la main."""
    length = len(next(iter(columns.values())))
    return pd.DataFrame(columns, index=_dates(length), dtype=float)


#: Une série de prix qui monte de 10 % par période, donc dont tout momentum se
#: calcule à la main comme une puissance de 1,1.
GEOMETRIC_PRICES = _series(*[100.0 * 1.1**k for k in range(12)])

#: Une série de prix construite pour porter un sommet, un creux et une reprise.
SHAPED_PRICES = _series(
    100.0,
    104.0,
    112.0,
    108.0,
    120.0,
    115.0,
    96.0,
    101.0,
    118.0,
    122.0,
    117.0,
    130.0,
    128.0,
    141.0,
    139.0,
    150.0,
    146.0,
    158.0,
    152.0,
    164.0,
)

#: Des rendements simples, tous strictement supérieurs à moins un.
SHAPED_RETURNS = _series(
    0.01,
    -0.02,
    0.03,
    0.00,
    -0.01,
    0.04,
    -0.03,
    0.02,
    0.01,
    -0.05,
    0.06,
    -0.01,
    0.02,
    0.03,
    -0.04,
    0.01,
    0.00,
    0.02,
    -0.02,
    0.05,
)


# --------------------------------------------------------------------------
# lag : le retard, et la garde contre le futur
# --------------------------------------------------------------------------


def test_lag_deplace_la_serie_vers_le_bas() -> None:
    """(a) Calcul à la main. Retard de 1 sur 1, 2, 3 rend manquant, 1, 2."""
    out = lag(_series(1.0, 2.0, 3.0), 1)
    assert math.isnan(out.iloc[0])
    assert out.iloc[1] == 1.0
    assert out.iloc[2] == 2.0


def test_lag_identite_de_recollement() -> None:
    """(b) Identité : lag(x, k) privé de ses k premières lignes vaut x privé des k dernières."""
    x = SHAPED_PRICES
    for k in (1, 3, 5):
        np.testing.assert_allclose(lag(x, k).to_numpy()[k:], x.to_numpy()[:-k])


def test_lag_periods_nul_ne_bouge_rien() -> None:
    """(b) Identité : un retard de zéro période est l'identité."""
    pd.testing.assert_series_equal(lag(SHAPED_PRICES, 0), SHAPED_PRICES)


def test_lag_refuse_un_retard_negatif() -> None:
    """(b) La règle du module : un shift négatif lit le futur, donc il est refusé."""
    with pytest.raises(LookAheadError, match="futur"):
        lag(SHAPED_PRICES, -1)


def test_lag_autorise_le_futur_quand_on_le_demande() -> None:
    """(a) Calcul à la main : avec allow_lookahead, 1, 2, 3 devient 2, 3, manquant."""
    out = lag(_series(1.0, 2.0, 3.0), -1, allow_lookahead=True)
    assert out.iloc[0] == 2.0
    assert out.iloc[1] == 3.0
    assert math.isnan(out.iloc[2])


def test_lag_refuse_un_periods_non_entier() -> None:
    """(b) Un retard fractionnaire n'a pas de sens sur un index de lignes."""
    with pytest.raises(ConfigError, match="entier"):
        lag(SHAPED_PRICES, 1.5)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# Les fenêtres glissantes
# --------------------------------------------------------------------------


def test_min_periods_est_obligatoire() -> None:
    """(b) La signature exige min_periods : l'omettre est une TypeError de Python."""
    for fonction in (rolling_mean, rolling_sum, rolling_min, rolling_max, rolling_std):
        with pytest.raises(TypeError):
            fonction(SHAPED_PRICES, 3)  # type: ignore[call-arg]


def test_rolling_mean_exemple_a_la_main() -> None:
    """(a) Calcul à la main sur 1, 2, 3, 4 avec une fenêtre de 2.

    Fenêtres complètes : (1+2)/2 = 1,5 ; (2+3)/2 = 2,5 ; (3+4)/2 = 3,5.
    La première ligne n'a pas de fenêtre complète, donc elle est manquante.
    """
    out = rolling_mean(_series(1.0, 2.0, 3.0, 4.0), 2, min_periods=2)
    assert math.isnan(out.iloc[0])
    np.testing.assert_allclose(out.to_numpy()[1:], [1.5, 2.5, 3.5])


def test_rolling_mean_contre_numpy() -> None:
    """(d) Implémentation indépendante : convolution numpy sur la même fenêtre."""
    window = 4
    valeurs = SHAPED_PRICES.to_numpy()
    attendu = np.convolve(valeurs, np.ones(window) / window, mode="valid")
    obtenu = rolling_mean(SHAPED_PRICES, window, min_periods=window).to_numpy()
    np.testing.assert_allclose(obtenu[window - 1 :], attendu, rtol=0, atol=1e-12)


def test_rolling_mean_serie_constante() -> None:
    """(b) Identité : la moyenne d'une constante vaut la constante."""
    out = rolling_mean(_series(*([7.0] * 6)), 3, min_periods=3)
    np.testing.assert_allclose(out.to_numpy()[2:], [7.0] * 4)


def test_rolling_std_exemple_a_la_main() -> None:
    """(a) Calcul à la main sur 1, 2, 3 avec ddof = 1.

    Moyenne 2. Écarts -1, 0, +1. Somme des carrés 2. Divisée par 3-1 = 2,
    la variance vaut 1, donc l'écart type vaut exactement 1.
    """
    out = rolling_std(_series(1.0, 2.0, 3.0), 3, min_periods=3)
    assert out.iloc[-1] == pytest.approx(1.0, abs=1e-15)


def test_rolling_std_contre_numpy() -> None:
    """(d) Implémentation indépendante : numpy avec le même degré de liberté."""
    window = 5
    obtenu = rolling_std(SHAPED_PRICES, window, min_periods=window).to_numpy()
    valeurs = SHAPED_PRICES.to_numpy()
    for fin in range(window, len(valeurs) + 1):
        attendu = np.std(valeurs[fin - window : fin], ddof=1)
        assert obtenu[fin - 1] == pytest.approx(attendu, rel=1e-12)


def test_rolling_std_serie_constante_vaut_zero() -> None:
    """(b) Identité : une constante n'a aucune dispersion."""
    out = rolling_std(_series(*([3.0] * 5)), 3, min_periods=3)
    np.testing.assert_allclose(out.to_numpy()[2:], [0.0] * 3, atol=1e-15)


def test_rolling_std_refuse_un_ddof_trop_grand() -> None:
    """(b) Avec ddof égal à min_periods, le dénominateur s'annule."""
    with pytest.raises(ConfigError, match="ddof"):
        rolling_std(SHAPED_PRICES, 3, min_periods=3, ddof=3)


def test_rolling_sum_exemple_a_la_main() -> None:
    """(a) Calcul à la main : sur une constante c et une fenêtre w, la somme vaut wc.

    Ici c = 2,5 et w = 4, donc la somme vaut 10 partout où elle est définie.
    """
    out = rolling_sum(_series(*([2.5] * 6)), 4, min_periods=4)
    np.testing.assert_allclose(out.to_numpy()[3:], [10.0] * 3)


def test_rolling_sum_de_rendements_log_donne_le_rendement_de_la_periode() -> None:
    """(b) Identité : la somme de w rendements logarithmiques est le rendement de la période.

    Sur des prix qui montent de 10 % par période, la somme de trois rendements
    logarithmiques vaut ln(1,1 puissance 3), soit 3 fois ln(1,1).
    """
    log_returns = np.log(GEOMETRIC_PRICES / GEOMETRIC_PRICES.shift(1))
    out = rolling_sum(log_returns, 3, min_periods=3)
    assert out.iloc[-1] == pytest.approx(3.0 * math.log(1.1), rel=1e-12)


def test_rolling_min_et_max_sur_une_serie_croissante() -> None:
    """(a) Calcul à la main sur 1, 2, 3, 4, 5 avec une fenêtre de 3.

    Le maximum glissant est la valeur du jour. Le minimum glissant est la valeur
    d'il y a deux périodes : 1, puis 2, puis 3.
    """
    x = _series(1.0, 2.0, 3.0, 4.0, 5.0)
    haut = rolling_max(x, 3, min_periods=3)
    bas = rolling_min(x, 3, min_periods=3)
    np.testing.assert_allclose(haut.to_numpy()[2:], [3.0, 4.0, 5.0])
    np.testing.assert_allclose(bas.to_numpy()[2:], [1.0, 2.0, 3.0])


def test_fenetre_refusee_si_elle_nest_pas_un_entier_positif() -> None:
    """(b) Une fenêtre nulle ou négative ne définit aucune moyenne."""
    with pytest.raises(ConfigError, match="window"):
        rolling_mean(SHAPED_PRICES, 0, min_periods=1)
    with pytest.raises(ConfigError, match="min_periods"):
        rolling_mean(SHAPED_PRICES, 3, min_periods=4)


# --------------------------------------------------------------------------
# La demi-vie, le facteur d'oubli et la fenêtre équivalente
# --------------------------------------------------------------------------


def test_demi_vie_de_soixante_jours_donne_le_lambda_annonce() -> None:
    """(b) Identité, recalculée indépendamment de la fonction.

    Le facteur d'oubli d'une demi-vie de 60 vaut 0,5 puissance 1/60. La valeur
    est recomposée ici par exp(ln(0,5)/60), une écriture différente de celle du
    module, et les deux doivent coïncider à la précision machine.
    """
    attendu = math.exp(math.log(0.5) / 60.0)
    assert halflife_to_lambda(60) == pytest.approx(attendu, rel=1e-15)
    assert round(halflife_to_lambda(60), 5) == 0.98851


def test_lambda_puissance_demi_vie_vaut_un_demi() -> None:
    """(b) Identité qui DÉFINIT la demi-vie : le poids est divisé par deux."""
    for halflife in (5.0, 20.0, 60.0, 250.0):
        assert halflife_to_lambda(halflife) ** halflife == pytest.approx(0.5, rel=1e-14)


def test_poids_cumule_des_soixante_derniers_jours_vaut_la_moitie() -> None:
    """(b) Identité : la part du poids total portée par les h dernières périodes.

    La somme géométrique des poids vaut 1/(1-lambda) et celle des h premiers
    termes vaut (1-lambda puissance h)/(1-lambda). Leur rapport vaut donc
    1 - lambda puissance h, soit exactement 0,5 quand h est la demi-vie.
    """
    decay = halflife_to_lambda(60)
    assert 1.0 - decay**60 == pytest.approx(0.5, rel=1e-14)


def test_lambda_to_halflife_est_la_reciproque() -> None:
    """(b) Identité : les deux conversions se composent en l'identité."""
    for halflife in (3.0, 11.0, 60.0):
        assert lambda_to_halflife(halflife_to_lambda(halflife)) == pytest.approx(halflife, rel=1e-12)


def test_riskmetrics_094_correspond_a_onze_jours() -> None:
    """(c) Valeur publiée : RiskMetrics (1996) retient lambda = 0,94 en quotidien.

    La demi-vie correspondante est ln(0,5)/ln(0,94), recalculée ici à la main.
    """
    assert lambda_to_halflife(0.94) == pytest.approx(math.log(0.5) / math.log(0.94), rel=1e-14)


def test_fenetre_equivalente_suit_le_centre_de_masse() -> None:
    """(b) Identité : 2 com + 1 vaut (1+lambda)/(1-lambda).

    Le calcul est refait ici sous la seconde forme, qui ne passe pas par le
    centre de masse.
    """
    decay = halflife_to_lambda(60)
    attendu = (1.0 + decay) / (1.0 - decay)
    assert equivalent_window(60) == pytest.approx(attendu, rel=1e-12)


# --------------------------------------------------------------------------
# ewma_volatility
# --------------------------------------------------------------------------


def test_ewma_volatility_exemple_entierement_a_la_main() -> None:
    """(a) Calcul à la main, demi-vie de 1, donc lambda = 0,5.

    Rendements 0,10 puis 0,00 puis 0,20. Carrés 0,01, 0,00 et 0,04.
    Période 0 : 0,01 / 1 = 0,01, racine 0,10.
    Période 1 : (0,00 + 0,5 x 0,01) / (1 + 0,5) = 0,005/1,5 = 1/300.
    Période 2 : (0,04 + 0 + 0,25 x 0,01) / (1 + 0,5 + 0,25) = 0,0425/1,75.
    """
    out = ewma_volatility(_series(0.10, 0.00, 0.20), 1.0, min_periods=1, annualize=False)
    assert out.iloc[0] == pytest.approx(0.10, rel=1e-14)
    assert out.iloc[1] == pytest.approx(math.sqrt(1.0 / 300.0), rel=1e-14)
    assert out.iloc[2] == pytest.approx(math.sqrt(0.0425 / 1.75), rel=1e-14)


def test_ewma_volatility_sur_rendements_constants() -> None:
    """(b) Identité : une moyenne pondérée de carrés tous égaux à c au carré vaut c au carré."""
    out = ewma_volatility(_series(*([0.02] * 10)), 5.0, min_periods=1, annualize=False)
    np.testing.assert_allclose(out.to_numpy(), [0.02] * 10, rtol=1e-13)


def test_ewma_volatility_contre_une_somme_ponderee_explicite() -> None:
    """(d) Implémentation indépendante : la somme pondérée écrite en clair.

    La référence n'utilise ni ``ewm`` ni pandas, seulement une boucle sur les
    puissances du facteur d'oubli.
    """
    halflife = 8.0
    decay = math.exp(math.log(0.5) / halflife)
    valeurs = SHAPED_RETURNS.to_numpy()
    obtenu = ewma_volatility(SHAPED_RETURNS, halflife, min_periods=1, annualize=False).to_numpy()
    for fin in range(len(valeurs)):
        poids = np.array([decay**i for i in range(fin + 1)])
        carres = valeurs[fin::-1] ** 2
        attendu = math.sqrt(float(poids @ carres) / float(poids.sum()))
        assert obtenu[fin] == pytest.approx(attendu, rel=1e-12)


def test_ewma_volatility_annualisation_vaut_racine_de_252() -> None:
    """(b) Identité : annualiser multiplie par la racine du nombre de périodes."""
    brute = ewma_volatility(SHAPED_RETURNS, 10.0, min_periods=5, annualize=False)
    annuelle = ewma_volatility(SHAPED_RETURNS, 10.0, min_periods=5, annualize=True)
    np.testing.assert_allclose((annuelle / brute).dropna().to_numpy(), math.sqrt(252.0), rtol=1e-13)


def test_ewma_volatility_respecte_min_periods() -> None:
    """(b) Les min_periods - 1 premières lignes n'ont pas assez d'observations."""
    out = ewma_volatility(SHAPED_RETURNS, 10.0, min_periods=4, annualize=False)
    assert out.iloc[:3].isna().all()
    assert not math.isnan(out.iloc[3])


def test_ewma_volatility_refuse_une_demi_vie_negative() -> None:
    """(b) Une demi-vie nulle ou négative ne définit aucun facteur d'oubli."""
    with pytest.raises(ConfigError, match="halflife"):
        ewma_volatility(SHAPED_RETURNS, 0.0, min_periods=1)


# --------------------------------------------------------------------------
# realized_volatility
# --------------------------------------------------------------------------


def test_realized_volatility_exemple_a_la_main() -> None:
    """(a) Calcul à la main sur 0,01, -0,02, 0,03, 0,00 avec une fenêtre de 2.

    Période 1 : (0,0001 + 0,0004)/2 = 0,00025, racine 0,0158113883.
    Période 2 : (0,0004 + 0,0009)/2 = 0,00065, racine 0,0254950976.
    Période 3 : (0,0009 + 0,0000)/2 = 0,00045, racine 0,0212132034.
    """
    out = realized_volatility(_series(0.01, -0.02, 0.03, 0.00), 2, annualize=False)
    assert math.isnan(out.iloc[0])
    assert out.iloc[1] == pytest.approx(math.sqrt(0.00025), rel=1e-14)
    assert out.iloc[2] == pytest.approx(math.sqrt(0.00065), rel=1e-14)
    assert out.iloc[3] == pytest.approx(math.sqrt(0.00045), rel=1e-14)


def test_realized_volatility_egale_lecart_type_a_moyenne_nulle() -> None:
    """(b) Identité : sur une fenêtre de moyenne exactement nulle, la racine de la
    moyenne des carrés est l'écart type avec ddof = 0.

    La série alterne +0,02 et -0,02, donc toute fenêtre de longueur paire a une
    moyenne nulle.
    """
    alternee = _series(*([0.02, -0.02] * 6))
    obtenu = realized_volatility(alternee, 4, annualize=False)
    np.testing.assert_allclose(obtenu.dropna().to_numpy(), 0.02, rtol=1e-14)


def test_realized_volatility_contre_numpy() -> None:
    """(d) Implémentation indépendante : moyenne des carrés calculée par numpy."""
    window = 6
    valeurs = SHAPED_RETURNS.to_numpy()
    obtenu = realized_volatility(SHAPED_RETURNS, window, annualize=False).to_numpy()
    for fin in range(window, len(valeurs) + 1):
        attendu = math.sqrt(float(np.mean(valeurs[fin - window : fin] ** 2)))
        assert obtenu[fin - 1] == pytest.approx(attendu, rel=1e-12)


def test_realized_volatility_annualisation_mensuelle() -> None:
    """(b) Identité : en mensuel, le facteur est la racine de 12."""
    brute = realized_volatility(SHAPED_RETURNS, 4, annualize=False)
    annuelle = realized_volatility(SHAPED_RETURNS, 4, frequency=Frequency.MONTHLY)
    np.testing.assert_allclose((annuelle / brute).dropna().to_numpy(), math.sqrt(12.0), rtol=1e-13)


def test_realized_volatility_ecart_de_ddof_avec_rolling_std() -> None:
    """(b) Identité : sur une fenêtre de moyenne nulle, le rapport ne tient qu'au ddof.

    La volatilité réalisée divise par w, l'écart type par w - 1, donc leur
    rapport vaut la racine de (w-1)/w. Pour w = 5 cela fait 0,8944, soit 11,80 %
    d'écart en sens inverse, ce que la docstring annonce. La série alterne
    +0,02 et -0,02, donc toute fenêtre paire a une moyenne exactement nulle.
    """
    alternee = _series(*([0.02, -0.02] * 8))
    for window in (4, 6, 8):
        rv = realized_volatility(alternee, window, annualize=False).dropna()
        sd = rolling_std(alternee, window, min_periods=window).dropna()
        attendu = math.sqrt((window - 1.0) / window)
        np.testing.assert_allclose((rv / sd).to_numpy(), attendu, rtol=1e-13)


def test_realized_volatility_min_periods_par_defaut_vaut_la_fenetre() -> None:
    """(b) Le défaut annoncé : les window - 1 premières lignes sont manquantes."""
    out = realized_volatility(SHAPED_RETURNS, 5, annualize=False)
    assert out.iloc[:4].isna().all()
    assert not math.isnan(out.iloc[4])


# --------------------------------------------------------------------------
# momentum
# --------------------------------------------------------------------------


def test_momentum_exemple_a_la_main_avec_saut() -> None:
    """(a) Calcul à la main sur des prix qui montent de 10 % par période.

    Avec lookback = 3 et skip = 1, le momentum vaut P(t-1)/P(t-3) - 1, soit
    1,1 au carré moins 1, donc exactement 0,21.
    """
    out = momentum(GEOMETRIC_PRICES, 3, skip=1)
    np.testing.assert_allclose(out.dropna().to_numpy(), 0.21, rtol=1e-12)


def test_momentum_sans_saut_couvre_toute_la_fenetre() -> None:
    """(a) Calcul à la main : sans saut, la fenêtre de 3 rend 1,1 au cube moins 1.

    1,1 au cube vaut 1,331, donc le momentum vaut 0,331.
    """
    out = momentum(GEOMETRIC_PRICES, 3, skip=0)
    np.testing.assert_allclose(out.dropna().to_numpy(), 0.331, rtol=1e-12)


def test_momentum_douze_moins_un_saute_bien_le_dernier_mois() -> None:
    """(a) Calcul à la main : la convention 12-1 lit onze périodes de rendement.

    Avec lookback = 12 et skip = 1 sur des prix qui montent de 10 %, le
    momentum vaut 1,1 puissance 11 moins 1.
    """
    prix = _series(*[100.0 * 1.1**k for k in range(20)])
    out = momentum(prix, 12, skip=1)
    np.testing.assert_allclose(out.dropna().to_numpy(), 1.1**11 - 1.0, rtol=1e-12)


def test_momentum_le_saut_arrete_la_fenetre_avant_aujourdhui() -> None:
    """(a) Calcul à la main sur des prix NON géométriques, qui séparent les deux conventions.

    Sur une série qui monte d'un taux constant, sauter une période et raccourcir
    la fenêtre d'autant donnent le même nombre, donc tout test géométrique laisse
    passer une fenêtre qui s'arrête AUJOURD'HUI. Les prix retenus ici lèvent
    l'ambiguïté. Avec lookback = 3 et skip = 1, la dernière ligne vaut
    P(18)/P(16) - 1, soit 152/146 - 1. La convention écartée donnerait
    P(19)/P(17) - 1, soit 164/150 - 1, qui en diffère de 5,2 points.
    """
    out = momentum(SHAPED_PRICES, 3, skip=1)
    attendu = 152.0 / 146.0 - 1.0
    ecarte = 164.0 / 150.0 - 1.0
    assert out.iloc[-1] == pytest.approx(attendu, rel=1e-14)
    assert out.iloc[-1] != pytest.approx(ecarte, rel=1e-3)
    # La ligne 6 se calcule de la même façon : P(5)/P(3) - 1 = 115/108 - 1.
    assert out.iloc[6] == pytest.approx(115.0 / 108.0 - 1.0, rel=1e-14)


def test_momentum_saut_nul_lit_bien_le_prix_du_jour() -> None:
    """(a) Calcul à la main : sans saut, la fenêtre se termine aujourd'hui.

    Avec lookback = 4 et skip = 0, la dernière ligne vaut P(19)/P(15) - 1, soit
    164/150 - 1. C'est le pendant du test précédent, qui fixe l'autre borne.
    """
    out = momentum(SHAPED_PRICES, 4, skip=0)
    assert out.iloc[-1] == pytest.approx(164.0 / 150.0 - 1.0, rel=1e-14)


def test_momentum_log_est_le_logarithme_du_momentum_simple() -> None:
    """(b) Identité : ln(1 + M) vaut le momentum logarithmique."""
    simple = momentum(SHAPED_PRICES, 6, skip=1, kind=ReturnKind.SIMPLE)
    logarithmique = momentum(SHAPED_PRICES, 6, skip=1, kind=ReturnKind.LOG)
    np.testing.assert_allclose(
        np.log1p(simple.dropna().to_numpy()), logarithmique.dropna().to_numpy(), rtol=1e-13
    )


def test_momentum_refuse_un_saut_plus_grand_que_la_fenetre() -> None:
    """(b) Avec skip supérieur ou égal à lookback, la fenêtre est vide ou renversée."""
    with pytest.raises(ConfigError, match="skip"):
        momentum(SHAPED_PRICES, 3, skip=3)


def test_momentum_refuse_un_prix_negatif() -> None:
    """(b) Un prix nul ou négatif rend tout rapport de prix faux."""
    with pytest.raises(DataQualityError, match="positif"):
        momentum(_series(100.0, -1.0, 110.0, 120.0), 2)


def test_momentum_sur_un_tableau_traite_chaque_colonne() -> None:
    """(a) Calcul à la main sur deux actifs, l'un à +10 %, l'autre à -10 %.

    Avec lookback = 2 et skip = 0, le premier rend 1,1 au carré moins 1 = 0,21
    et le second rend 0,9 au carré moins 1 = -0,19.
    """
    table = _frame(
        HAUSSE=[100.0 * 1.1**k for k in range(5)],
        BAISSE=[100.0 * 0.9**k for k in range(5)],
    )
    out = momentum(table, 2)
    assert out["HAUSSE"].iloc[-1] == pytest.approx(0.21, rel=1e-12)
    assert out["BAISSE"].iloc[-1] == pytest.approx(-0.19, rel=1e-12)


# --------------------------------------------------------------------------
# time_series_momentum_signal
# --------------------------------------------------------------------------


def test_signal_de_tendance_exemple_a_la_main() -> None:
    """(a) Calcul à la main sur 0,10 puis -0,05 puis 0,02, fenêtre de 2.

    Période 1 : 1,10 x 0,95 = 1,045, donc rendement cumulé +4,5 %, signal +1.
    Période 2 : 0,95 x 1,02 = 0,969, donc rendement cumulé -3,1 %, signal -1.
    """
    out = time_series_momentum_signal(_series(0.10, -0.05, 0.02), 2)
    assert math.isnan(out.iloc[0])
    assert out.iloc[1] == 1.0
    assert out.iloc[2] == -1.0


def test_signal_de_tendance_traite_le_zero_comme_plat() -> None:
    """(a) Calcul à la main : 1,25 x 0,80 vaut exactement 1, donc le cumul est nul.

    La convention déclarée du module rend alors 0, donc une position plate.
    """
    out = time_series_momentum_signal(_series(0.25, -0.20), 2)
    assert out.iloc[-1] == 0.0


def test_signal_de_tendance_zone_plate_elargie() -> None:
    """(a) Calcul à la main : un cumul logarithmique de ln(1,01) vaut 0,00995.

    Avec une tolérance de 0,02, ce cumul tombe dans la zone plate et le signal
    vaut 0 ; sans tolérance il vaudrait +1.
    """
    serie = _series(0.01, 0.00)
    assert time_series_momentum_signal(serie, 2).iloc[-1] == 1.0
    assert time_series_momentum_signal(serie, 2, zero_tolerance=0.02).iloc[-1] == 0.0


def test_signal_de_tendance_refuse_une_perte_totale() -> None:
    """(b) Un rendement simple de -1 annule le prix, et son logarithme n'existe pas."""
    with pytest.raises(DataQualityError, match="-1"):
        time_series_momentum_signal(_series(0.01, -1.0, 0.02), 2)


def test_signal_de_tendance_ne_prend_que_trois_valeurs() -> None:
    """(b) Le signe d'un réel appartient à l'ensemble des trois valeurs."""
    out = time_series_momentum_signal(SHAPED_RETURNS, 4).dropna()
    assert set(out.unique()) <= {-1.0, 0.0, 1.0}


# --------------------------------------------------------------------------
# zscore_time_series
# --------------------------------------------------------------------------


def test_zscore_exemple_a_la_main() -> None:
    """(a) Calcul à la main sur 1, 2, 3 avec une fenêtre de 3.

    Moyenne 2, écart type d'échantillon 1. Le z-score du dernier point vaut
    (3 - 2)/1, soit exactement 1.
    """
    out = zscore_time_series(_series(1.0, 2.0, 3.0), 3, min_periods=3)
    assert out.iloc[-1] == pytest.approx(1.0, abs=1e-15)


def test_zscore_contre_scipy() -> None:
    """(d) Implémentation indépendante : scipy.stats.zscore sur chaque fenêtre.

    ``scipy.stats.zscore`` normalise avec ddof choisi, et l'on ne garde que la
    dernière valeur de la fenêtre.
    """
    window = 5
    valeurs = SHAPED_PRICES.to_numpy()
    obtenu = zscore_time_series(SHAPED_PRICES, window, min_periods=window).to_numpy()
    for fin in range(window, len(valeurs) + 1):
        attendu = stats.zscore(valeurs[fin - window : fin], ddof=1)[-1]
        assert obtenu[fin - 1] == pytest.approx(attendu, rel=1e-12)


def test_zscore_dune_serie_constante_est_manquant() -> None:
    """(b) Une dispersion nulle rend le z-score indéfini, donc manquant et non infini."""
    out = zscore_time_series(_series(*([5.0] * 6)), 3, min_periods=3)
    assert out.iloc[2:].isna().all()


# --------------------------------------------------------------------------
# percent_rank
# --------------------------------------------------------------------------


def test_percent_rank_exemple_a_la_main() -> None:
    """(a) Calcul à la main sur 1, 3, 2, 5 avec une fenêtre de 3.

    Période 2 : fenêtre 1, 3, 2 ; un seul point sous 2, donc 1/2 = 0,5.
    Période 3 : fenêtre 3, 2, 5 ; les deux points sont sous 5, donc 2/2 = 1.
    """
    out = percent_rank(_series(1.0, 3.0, 2.0, 5.0), 3)
    assert out.iloc[:2].isna().all()
    assert out.iloc[2] == pytest.approx(0.5, abs=1e-15)
    assert out.iloc[3] == pytest.approx(1.0, abs=1e-15)


def test_percent_rank_partage_les_ex_aequo() -> None:
    """(a) Calcul à la main : sur une fenêtre constante, les deux ex aequo comptent une demi-unité.

    (0 + 0,5 x 2) / (3 - 1) donne exactement 0,5.
    """
    out = percent_rank(_series(*([4.0] * 5)), 3)
    np.testing.assert_allclose(out.dropna().to_numpy(), 0.5, atol=1e-15)


def test_percent_rank_contre_scipy_rankdata() -> None:
    """(d) Implémentation indépendante : scipy.stats.rankdata avec rangs moyens.

    Le rang moyen du dernier point vaut 1 + (nombre de points sous lui) plus la
    moitié des ex aequo. Le rang relatif est donc (rang - 1)/(w - 1).
    """
    window = 5
    valeurs = SHAPED_PRICES.to_numpy()
    obtenu = percent_rank(SHAPED_PRICES, window).to_numpy()
    for fin in range(window, len(valeurs) + 1):
        rangs = stats.rankdata(valeurs[fin - window : fin], method="average")
        attendu = (rangs[-1] - 1.0) / (window - 1.0)
        assert obtenu[fin - 1] == pytest.approx(attendu, rel=1e-12)


def test_percent_rank_nest_pas_percentileofscore() -> None:
    """(d) Implémentation indépendante, et l'écart documenté avec scipy.

    ``percentileofscore`` avec l'option ``mean`` divise par w et compte la
    valeur du jour parmi ses propres ex aequo. Sur 1, 2, 3, 4 elle rend 0,875
    quand cette fonction rend 1,0. Sur une fenêtre constante les deux rendent
    0,5, ce qui rend la confusion facile.
    """
    croissante = _series(1.0, 2.0, 3.0, 4.0)
    assert percent_rank(croissante, 4).iloc[-1] == pytest.approx(1.0, abs=1e-15)
    assert stats.percentileofscore([1.0, 2.0, 3.0, 4.0], 4.0, kind="mean") / 100.0 == pytest.approx(
        0.875, abs=1e-15
    )
    constante = _series(4.0, 4.0, 4.0)
    assert percent_rank(constante, 3).iloc[-1] == pytest.approx(0.5, abs=1e-15)
    assert stats.percentileofscore([4.0, 4.0, 4.0], 4.0, kind="mean") / 100.0 == pytest.approx(0.5, abs=1e-15)


def test_percent_rank_ne_calcule_rien_sur_une_fenetre_trouee() -> None:
    """(a) Calcul à la main : une fenêtre qui porte un manquant reste manquante.

    Sur 1, manquant, 3, 2, 5 avec une fenêtre de 3, seules les fenêtres des
    lignes 4 et suivantes sont pleines. La ligne 4 porte 3, 2, 5 : les deux
    points sont sous 5, donc le rang vaut 1.
    """
    trouee = _series(1.0, float("nan"), 3.0, 2.0, 5.0)
    out = percent_rank(trouee, 3)
    assert out.iloc[:4].isna().all()
    assert out.iloc[4] == pytest.approx(1.0, abs=1e-15)


def test_percent_rank_refuse_une_fenetre_de_un() -> None:
    """(b) Avec une seule observation, le dénominateur du rang relatif s'annule."""
    with pytest.raises(ConfigError, match="window"):
        percent_rank(SHAPED_PRICES, 1)


# --------------------------------------------------------------------------
# drawdown_feature
# --------------------------------------------------------------------------


def test_drawdown_feature_exemple_a_la_main() -> None:
    """(a) Calcul à la main sur 100, 120, 90, 95 avec une fenêtre de 3.

    Période 2 : plus haut 120, prix 90, donc 90/120 - 1 = -0,25.
    Période 3 : plus haut 120, prix 95, donc 95/120 - 1 = -1/4,8, soit -0,208333.
    """
    out = drawdown_feature(_series(100.0, 120.0, 90.0, 95.0), 3)
    assert out.iloc[:2].isna().all()
    assert out.iloc[2] == pytest.approx(-0.25, abs=1e-15)
    assert out.iloc[3] == pytest.approx(95.0 / 120.0 - 1.0, abs=1e-15)


def test_drawdown_feature_rejoint_le_repli_depuis_le_sommet() -> None:
    """(b) Identité : sur une fenêtre aussi longue que l'échantillon, la mémoire
    bornée devient la mémoire complète.

    La référence est ``quantlab.analytics.drawdown.drawdown_series``, écrite
    dans un autre module et testée séparément.
    """
    n = len(SHAPED_PRICES)
    borne = drawdown_feature(SHAPED_PRICES, n).iloc[-1]
    complet = drawdown_series(SHAPED_PRICES, is_wealth=True).iloc[-1]
    assert borne == pytest.approx(complet, abs=1e-14)


def test_drawdown_feature_est_nul_au_sommet() -> None:
    """(b) Identité : sur une série croissante, le prix du jour EST le plus haut."""
    out = drawdown_feature(GEOMETRIC_PRICES, 4)
    np.testing.assert_allclose(out.dropna().to_numpy(), 0.0, atol=1e-15)


# --------------------------------------------------------------------------
# forward_return : l'étiquette, et sa signalisation
# --------------------------------------------------------------------------


def test_forward_return_exemple_a_la_main() -> None:
    """(a) Calcul à la main sur 100, 110, 121 avec un horizon de 1.

    Période 0 : 110/100 - 1 = 0,10. Période 1 : 121/110 - 1 = 0,10.
    Période 2 : le futur n'est pas observé, donc manquant.
    """
    out = forward_return(_series(100.0, 110.0, 121.0), 1)
    assert out.iloc[0] == pytest.approx(0.10, rel=1e-14)
    assert out.iloc[1] == pytest.approx(0.10, rel=1e-14)
    assert math.isnan(out.iloc[2])


def test_forward_return_porte_le_prefixe_etiquette() -> None:
    """(b) La règle du module : une sortie qui lit le futur se nomme label_."""
    nommee = forward_return(_series(100.0, 110.0, 121.0, name="SPY"), 2)
    anonyme = forward_return(_series(100.0, 110.0, 121.0), 2)
    table = forward_return(_frame(A=[100.0, 110.0, 121.0]), 1)
    assert nommee.name == "label_forward_return_2_SPY"
    assert anonyme.name == "label_forward_return_2"
    assert list(table.columns) == ["label_forward_return_1_A"]


def test_forward_return_est_le_miroir_du_retard() -> None:
    """(b) Identité : l'étiquette d'horizon h à la date t est le momentum de
    fenêtre h et de saut nul mesuré h périodes plus tard."""
    horizon = 3
    etiquette = forward_return(SHAPED_PRICES, horizon).to_numpy()[:-horizon]
    passe = momentum(SHAPED_PRICES, horizon).to_numpy()[horizon:]
    np.testing.assert_allclose(etiquette, passe, rtol=1e-13)


def test_forward_return_refuse_un_horizon_nul() -> None:
    """(b) Un horizon nul ne prévoit rien."""
    with pytest.raises(ConfigError, match="horizon"):
        forward_return(SHAPED_PRICES, 0)


# --------------------------------------------------------------------------
# assert_causal : le contrôle, testé dans les deux sens
# --------------------------------------------------------------------------

#: Les caractéristiques du module, avec des paramètres qui laissent au moins une
#: fenêtre complète avant chaque coupure du contrôle.
CARACTERISTIQUES_DE_PRIX = {
    "lag": partial(lag, periods=1),
    "rolling_mean": partial(rolling_mean, window=4, min_periods=4),
    "rolling_std": partial(rolling_std, window=4, min_periods=4),
    "rolling_sum": partial(rolling_sum, window=4, min_periods=4),
    "rolling_min": partial(rolling_min, window=4, min_periods=4),
    "rolling_max": partial(rolling_max, window=4, min_periods=4),
    "momentum": partial(momentum, lookback=5, skip=1),
    "zscore_time_series": partial(zscore_time_series, window=5, min_periods=5),
    "percent_rank": partial(percent_rank, window=5),
    "drawdown_feature": partial(drawdown_feature, window=5),
}

CARACTERISTIQUES_DE_RENDEMENT = {
    "ewma_volatility": partial(ewma_volatility, halflife=6.0, min_periods=3),
    "realized_volatility": partial(realized_volatility, window=5),
    "time_series_momentum_signal": partial(time_series_momentum_signal, lookback=5),
}


@pytest.mark.parametrize("nom", sorted(CARACTERISTIQUES_DE_PRIX))
def test_assert_causal_accepte_les_caracteristiques_de_prix(nom: str) -> None:
    """(b) La règle du module, vérifiée sur chaque transformation de prix."""
    assert_causal(CARACTERISTIQUES_DE_PRIX[nom], SHAPED_PRICES, name=nom)


@pytest.mark.parametrize("nom", sorted(CARACTERISTIQUES_DE_RENDEMENT))
def test_assert_causal_accepte_les_caracteristiques_de_rendement(nom: str) -> None:
    """(b) La règle du module, vérifiée sur chaque transformation de rendement."""
    assert_causal(CARACTERISTIQUES_DE_RENDEMENT[nom], SHAPED_RETURNS, name=nom)


def test_assert_causal_attrape_un_shift_negatif_introduit_expres() -> None:
    """(b) Le contrôle doit REFUSER une fuite d'un seul pas.

    La fonction fautive est écrite ici exprès : elle rend x décalé de moins une
    période, donc la valeur de demain à la date d'aujourd'hui.
    """

    def fuite(x: pd.Series) -> pd.Series:
        return x.shift(-1)

    with pytest.raises(LookAheadError, match="futur"):
        assert_causal(fuite, SHAPED_PRICES, name="fuite")


def test_assert_causal_attrape_une_moyenne_mobile_centree() -> None:
    """(b) Le contrôle doit REFUSER une fenêtre centrée, qui lit à droite."""

    def centree(x: pd.Series) -> pd.Series:
        return x.rolling(5, center=True, min_periods=5).mean()

    with pytest.raises(LookAheadError):
        assert_causal(centree, SHAPED_PRICES, name="centree")


def test_assert_causal_attrape_une_normalisation_sur_tout_lechantillon() -> None:
    """(b) Le contrôle doit REFUSER une moyenne calculée sur l'échantillon entier.

    C'est la fuite la plus discrète du métier : elle ne décale rien, elle
    utilise seulement une statistique que le passé ne connaissait pas.
    """

    def fuite_de_normalisation(x: pd.Series) -> pd.Series:
        return (x - x.mean()) / x.std()

    with pytest.raises(LookAheadError):
        assert_causal(fuite_de_normalisation, SHAPED_PRICES, name="normalisation")


def test_assert_causal_refuse_letiquette_forward_return() -> None:
    """(b) Une étiquette qui passerait le contrôle ne serait pas une étiquette."""
    with pytest.raises(LookAheadError):
        assert_causal(partial(forward_return, horizon=1), SHAPED_PRICES, name="label")


def test_assert_causal_attrape_le_rang_sur_tout_lechantillon() -> None:
    """(b) Contre-exemple mesuré : un décalage additif conserve l'ORDRE.

    Le rang de chaque observation dans l'échantillon ENTIER est une fuite, et
    elle survivait à la seule épreuve du décalage : ajouter la même quantité à
    tout le futur ne croise aucune valeur du passé, donc aucun rang ne bouge.
    Retirer le futur change le dénominateur du rang, donc l'attrape.
    """

    def rang_global(x: pd.Series) -> pd.Series:
        return x.rank(pct=True)

    with pytest.raises(LookAheadError):
        assert_causal(rang_global, SHAPED_PRICES, name="rang_global")


def test_assert_causal_attrape_une_winsorisation_au_quantile_global() -> None:
    """(b) Contre-exemple mesuré : le seuil de winsorisation lu sur tout l'échantillon.

    Le neuvième décile monte d'autant que le futur quand on décale celui-ci,
    donc le passé écrêté ne bouge pas et le décalage ne voit rien. Le seuil
    calculé sur le seul passé, lui, diffère.
    """

    def winsorisation_globale(x: pd.Series) -> pd.Series:
        return x.clip(upper=x.quantile(0.90))

    with pytest.raises(LookAheadError):
        assert_causal(winsorisation_globale, SHAPED_PRICES, name="winsorisation")


def test_assert_causal_attrape_la_lecture_du_nombre_dobservations() -> None:
    """(b) Contre-exemple mesuré : la taille de l'échantillon est déjà du futur.

    Aucune modification des VALEURS ne peut l'attraper, puisque le nombre de
    lignes ne change pas. Seul le retrait du futur le fait.
    """

    def compte_global(x: pd.Series) -> pd.Series:
        return pd.Series(float(len(x)), index=x.index)

    with pytest.raises(LookAheadError):
        assert_causal(compte_global, SHAPED_PRICES, name="compte")


def test_assert_causal_refuse_un_controle_entierement_manquant() -> None:
    """(b) Un contrôle qui ne peut rien voir n'est pas un contrôle.

    Une caractéristique dont la sortie est manquante partout passerait la
    comparaison, puisque manquant égale manquant. Le refus est explicite.
    """

    def rien(x: pd.Series) -> pd.Series:
        return pd.Series(float("nan"), index=x.index)

    with pytest.raises(InsufficientDataError, match="rien prouver"):
        assert_causal(rien, SHAPED_PRICES, name="rien")


def test_assert_causal_refuse_une_fenetre_plus_longue_que_le_passe() -> None:
    """(b) Une fenêtre de 12 sur 20 points laisse la première coupure vide.

    La coupure au quart tombe à la sixième ligne, et une moyenne mobile de 12
    n'y est pas encore définie. Le contrôle le dit au lieu de passer.
    """
    with pytest.raises(InsufficientDataError, match="rien prouver"):
        assert_causal(partial(rolling_mean, window=12, min_periods=12), SHAPED_PRICES)


def test_assert_causal_attrape_un_changement_de_forme() -> None:
    """(b) Une sortie dont le nombre de lignes PASSÉES dépend du futur est une fuite.

    La fonction fautive ne garde que les valeurs au-dessus d'un seuil lu au
    MILIEU de l'échantillon, donc le futur décide quelles lignes passées
    survivent.
    """

    def filtre_global(x: pd.Series) -> pd.Series:
        seuil = x.iloc[len(x) // 2]
        return x[x > seuil]

    with pytest.raises(LookAheadError, match="FORME"):
        assert_causal(filtre_global, SHAPED_PRICES, name="filtre", perturbation=50.0)


def test_assert_causal_exige_un_echantillon_minimal() -> None:
    """(b) Avec trois points, les trois coupures par défaut se confondent."""
    with pytest.raises(InsufficientDataError):
        assert_causal(partial(lag, periods=1), _series(1.0, 2.0, 3.0))


def test_assert_causal_refuse_une_sortie_qui_nest_pas_pandas() -> None:
    """(b) Le contrôle compare des index : il lui faut un objet pandas."""
    with pytest.raises(TypeError):
        assert_causal(lambda x: float(x.mean()), SHAPED_PRICES)  # type: ignore[arg-type, return-value]


def test_assert_causal_refuse_une_fraction_hors_intervalle() -> None:
    """(b) Une coupure à 0 ou à 1 ne sépare pas le passé du futur."""
    with pytest.raises(ConfigError, match="intervalle"):
        assert_causal(partial(lag, periods=1), SHAPED_PRICES, cut_fractions=(1.0,))


def test_assert_causal_fonctionne_sur_un_tableau() -> None:
    """(b) La règle vaut colonne par colonne, et le contrôle accepte un DataFrame."""
    table = _frame(
        A=list(SHAPED_PRICES.to_numpy()),
        B=list(SHAPED_PRICES.to_numpy() * 0.5 + 10.0),
    )
    assert_causal(partial(rolling_mean, window=4, min_periods=4), table, name="rolling_mean")


# --------------------------------------------------------------------------
# Propriétés (hypothesis)
# --------------------------------------------------------------------------

_PRIX = st.lists(
    st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    min_size=12,
    max_size=40,
)
_RENDEMENTS = st.lists(
    st.floats(min_value=-0.5, max_value=0.5, allow_nan=False, allow_infinity=False),
    min_size=12,
    max_size=40,
)


def _le_passe_ne_bouge_pas(fonction, valeurs: list[float], coupure: int) -> None:
    """Vérifie qu'une caractéristique avant la coupure ignore les données d'après.

    Les deux épreuves d'``assert_causal`` sont rejouées ici sur des données
    tirées au hasard : le futur est d'abord décalé, puis retiré. La seconde est
    la plus forte, puisqu'une fonction causale rend la même valeur que l'avenir
    existe ou non.
    """
    origine = pd.Series(valeurs, index=_dates(len(valeurs)), dtype=float)
    modifiee = origine.copy()
    modifiee.iloc[coupure + 1 :] = modifiee.iloc[coupure + 1 :].to_numpy() + 3.75
    avant = fonction(origine).to_numpy()[: coupure + 1]
    apres = fonction(modifiee).to_numpy()[: coupure + 1]
    np.testing.assert_allclose(avant, apres, rtol=0.0, atol=1e-12, equal_nan=True)
    tronquee = fonction(origine.iloc[: coupure + 1]).to_numpy()
    np.testing.assert_allclose(avant, tronquee, rtol=0.0, atol=1e-12, equal_nan=True)


@settings(deadline=None, max_examples=60)
@given(valeurs=_PRIX, fraction=st.floats(min_value=0.1, max_value=0.9))
def test_propriete_les_caracteristiques_de_prix_ignorent_le_futur(
    valeurs: list[float], fraction: float
) -> None:
    """(b) La propriété centrale du module, tirée au hasard sur des prix.

    Une caractéristique datée t ne change pas quand on modifie les données
    postérieures à t. La coupure est tirée, les valeurs aussi.
    """
    coupure = min(max(int(fraction * len(valeurs)), 0), len(valeurs) - 2)
    for fonction in CARACTERISTIQUES_DE_PRIX.values():
        _le_passe_ne_bouge_pas(fonction, valeurs, coupure)


@settings(deadline=None, max_examples=60)
@given(valeurs=_RENDEMENTS, fraction=st.floats(min_value=0.1, max_value=0.9))
def test_propriete_les_caracteristiques_de_rendement_ignorent_le_futur(
    valeurs: list[float], fraction: float
) -> None:
    """(b) La même propriété, sur des rendements strictement supérieurs à moins un."""
    coupure = min(max(int(fraction * len(valeurs)), 0), len(valeurs) - 2)
    for fonction in CARACTERISTIQUES_DE_RENDEMENT.values():
        _le_passe_ne_bouge_pas(fonction, valeurs, coupure)


@settings(deadline=None, max_examples=80)
@given(valeurs=_PRIX)
def test_propriete_le_rang_relatif_reste_entre_zero_et_un(valeurs: list[float]) -> None:
    """(b) Le rang relatif est une proportion, donc borné par construction."""
    serie = pd.Series(valeurs, index=_dates(len(valeurs)), dtype=float)
    obtenu = percent_rank(serie, 5).dropna().to_numpy()
    assert np.all(obtenu >= 0.0)
    assert np.all(obtenu <= 1.0)


@settings(deadline=None, max_examples=80)
@given(valeurs=_PRIX)
def test_propriete_le_repli_glissant_reste_entre_moins_un_et_zero(valeurs: list[float]) -> None:
    """(b) Le prix du jour appartient à sa propre fenêtre, donc le repli est négatif ou nul."""
    serie = pd.Series(valeurs, index=_dates(len(valeurs)), dtype=float)
    obtenu = drawdown_feature(serie, 5).dropna().to_numpy()
    assert np.all(obtenu <= 1e-15)
    assert np.all(obtenu >= -1.0)


@settings(deadline=None, max_examples=80)
@given(valeurs=_RENDEMENTS)
def test_propriete_la_volatilite_glissante_est_positive(valeurs: list[float]) -> None:
    """(b) Une racine de moyenne de carrés est positive ou nulle."""
    serie = pd.Series(valeurs, index=_dates(len(valeurs)), dtype=float)
    for obtenu in (
        ewma_volatility(serie, 6.0, min_periods=3).dropna().to_numpy(),
        realized_volatility(serie, 5).dropna().to_numpy(),
    ):
        assert np.all(obtenu >= 0.0)


@settings(deadline=None, max_examples=80)
@given(valeurs=_PRIX)
def test_propriete_min_inferieur_a_mean_inferieur_a_max(valeurs: list[float]) -> None:
    """(b) Ordre garanti : le minimum d'une fenêtre ne dépasse ni sa moyenne ni son maximum."""
    serie = pd.Series(valeurs, index=_dates(len(valeurs)), dtype=float)
    bas = rolling_min(serie, 4, min_periods=4).dropna().to_numpy()
    milieu = rolling_mean(serie, 4, min_periods=4).dropna().to_numpy()
    haut = rolling_max(serie, 4, min_periods=4).dropna().to_numpy()
    assert np.all(bas <= milieu + 1e-12)
    assert np.all(milieu <= haut + 1e-12)


# --------------------------------------------------------------------------
# Cas limites
# --------------------------------------------------------------------------


def test_serie_vide_est_refusee() -> None:
    """(b) Une série sans observation ne porte aucune caractéristique."""
    vide = pd.Series([], index=pd.DatetimeIndex([]), dtype=float)
    with pytest.raises(InsufficientDataError):
        rolling_mean(vide, 3, min_periods=3)
    with pytest.raises(InsufficientDataError):
        momentum(vide, 3)


def test_serie_dun_point() -> None:
    """(a) Calcul à la main : une fenêtre de 1 sur un point rend ce point."""
    un = _series(42.0)
    assert rolling_mean(un, 1, min_periods=1).iloc[0] == 42.0
    assert math.isnan(momentum(un, 1).iloc[0])


def test_valeurs_manquantes_se_propagent_sans_les_combler() -> None:
    """(b) Une fenêtre qui porte un manquant n'atteint pas min_periods.

    Sur 1, manquant, 3, 4 avec une fenêtre de 2, les deux premières fenêtres
    complètes portent le trou, donc les lignes 1 et 2 sont manquantes, et la
    ligne 3 vaut (3+4)/2 = 3,5.
    """
    avec_trou = _series(1.0, float("nan"), 3.0, 4.0)
    out = rolling_mean(avec_trou, 2, min_periods=2)
    assert out.iloc[:3].isna().all()
    assert out.iloc[3] == pytest.approx(3.5, abs=1e-15)


def test_index_en_double_est_refuse() -> None:
    """(b) Un horodatage en double casse l'ordre, donc la causalité."""
    doublon = pd.Series([1.0, 2.0, 3.0], index=pd.DatetimeIndex(["2020-01-31"] * 3))
    with pytest.raises(DataQualityError, match="double"):
        rolling_mean(doublon, 2, min_periods=2)


def test_index_decroissant_est_refuse() -> None:
    """(b) Une fenêtre glissante sur un index décroissant lit le futur."""
    envers = pd.Series([1.0, 2.0, 3.0], index=_dates(3)[::-1])
    with pytest.raises(DataQualityError, match="croissant"):
        rolling_mean(envers, 2, min_periods=2)


def test_entree_qui_nest_pas_pandas_est_refusee() -> None:
    """(b) Le module travaille sur des objets indexés par le temps."""
    with pytest.raises(TypeError):
        rolling_mean([1.0, 2.0, 3.0], 2, min_periods=2)  # type: ignore[arg-type]


def test_all_ne_reexporte_ni_numpy_ni_pandas() -> None:
    """(b) La règle 3 du CLAUDE.md : un __all__ n'exporte pas ses dépendances."""
    assert "np" not in transforms.__all__
    assert "pd" not in transforms.__all__
    assert set(transforms.__all__) <= set(dir(transforms))

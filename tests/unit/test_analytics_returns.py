"""Tests de ``quantlab.analytics.returns``.

Règle du laboratoire appliquée ici sans exception : aucune valeur attendue ne
vient de la sortie du code testé. Chaque assertion cite sa source dans un
commentaire, parmi les quatre admises.

(a) un calcul à la main, chiffres visibles dans le commentaire ;
(b) une forme fermée ou une identité mathématique ;
(c) une valeur publiée, citée avec son emplacement ;
(d) une implémentation indépendante, ici ``scipy.stats.gmean`` et ``numpy``.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from scipy.stats import gmean

from quantlab.analytics.returns import (
    align_returns,
    arithmetic_mean_return,
    cagr,
    compound,
    cumulative_wealth,
    excess_returns,
    geometric_mean_return,
    log_to_simple,
    resample_returns,
    simple_to_log,
    to_prices,
    to_returns,
)
from quantlab.core.determinism import make_generator
from quantlab.core.errors import DataQualityError, InsufficientDataError
from quantlab.core.types import Frequency, ReturnKind


def monthly_index(n: int, start: str = "2020-01-31") -> pd.DatetimeIndex:
    """Rend un index de fins de mois consécutives."""
    return pd.date_range(start, periods=n, freq="ME")


def annual_index(n: int, start: str = "2020-12-31") -> pd.DatetimeIndex:
    """Rend un index de fins d'année consécutives."""
    return pd.date_range(start, periods=n, freq="YE")


# ---------------------------------------------------------------------------
# Conversion prix -> rendements
# ---------------------------------------------------------------------------


def test_to_returns_simple_hand_computed() -> None:
    """(a) 110/100 - 1 = 0,10 et 99/110 - 1 = -0,10, calculés à la main."""
    prices = pd.Series([100.0, 110.0, 99.0], index=monthly_index(3))
    got = to_returns(prices)
    assert got.index.equals(monthly_index(3)[1:])
    assert got.iloc[0] == pytest.approx(0.10, abs=1e-15)
    assert got.iloc[1] == pytest.approx(-0.10, abs=1e-15)


def test_to_returns_log_matches_documented_values() -> None:
    """(c) Valeurs publiées dans la docstring de ``quantlab.core.types.ReturnKind``.

    Le texte y écrit : « +0,09531 puis -0,10536 somment à -0,01005, dont
    l'exponentielle rend exactement 0,99 ». Les trois nombres sont vérifiés ici.
    """
    prices = pd.Series([100.0, 110.0, 99.0], index=monthly_index(3))
    logs = to_returns(prices, ReturnKind.LOG)
    assert logs.iloc[0] == pytest.approx(0.09531, abs=5e-6)
    assert logs.iloc[1] == pytest.approx(-0.10536, abs=5e-6)
    assert float(logs.sum()) == pytest.approx(-0.01005, abs=5e-6)
    assert float(np.exp(logs.sum())) == pytest.approx(0.99, abs=1e-12)


def test_log_and_simple_returns_are_the_same_series() -> None:
    """(b) Identité r_log = ln(1 + r_simple), exigée à 1e-12."""
    rng = make_generator(20260901)
    prices = pd.Series(
        100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.01, 250))),
        index=pd.date_range("2020-01-01", periods=250, freq="B"),
    )
    simple = to_returns(prices, ReturnKind.SIMPLE)
    logs = to_returns(prices, ReturnKind.LOG)
    assert np.max(np.abs(logs.to_numpy() - np.log1p(simple.to_numpy()))) < 1e-12


def test_simple_log_round_trip_is_exact() -> None:
    """(b) log_to_simple est la réciproque de simple_to_log, à 1e-12."""
    r = pd.Series([-0.9, -0.05, 0.0, 1e-9, 0.37], index=monthly_index(5))
    back = log_to_simple(simple_to_log(r))
    assert np.max(np.abs(back.to_numpy() - r.to_numpy())) < 1e-12


def test_simple_to_log_rejects_total_loss() -> None:
    """(b) ln(1 + r) n'est pas défini pour r <= -1, donc la garde doit lever."""
    with pytest.raises(DataQualityError):
        simple_to_log(-1.0)
    with pytest.raises(DataQualityError):
        simple_to_log(pd.Series([0.01, -1.5], index=monthly_index(2)))


def test_to_returns_rejects_non_positive_prices() -> None:
    """(b) Un prix nul rendrait un quotient infini, donc l'entrée est refusée."""
    prices = pd.Series([100.0, 0.0, 50.0], index=monthly_index(3))
    with pytest.raises(DataQualityError, match="strictement positifs"):
        to_returns(prices)


def test_to_returns_requires_two_prices() -> None:
    """(b) Un seul prix ne définit aucun rendement."""
    with pytest.raises(InsufficientDataError):
        to_returns(pd.Series([100.0], index=monthly_index(1)))


def test_duplicate_or_unsorted_index_is_refused() -> None:
    """(b) Un index en double ou décroissant fausse toute agrégation temporelle."""
    duplicated = pd.Series([1.0, 2.0], index=pd.DatetimeIndex(["2020-01-31", "2020-01-31"]))
    with pytest.raises(DataQualityError, match="double"):
        to_prices(duplicated)
    reversed_index = pd.Series([1.0, 2.0], index=pd.DatetimeIndex(["2020-02-29", "2020-01-31"]))
    with pytest.raises(DataQualityError, match="croissant"):
        to_prices(reversed_index)


def test_to_returns_keeps_interior_gaps_when_asked() -> None:
    """(a) Un prix manquant fabrique deux rendements manquants, pas un seul.

    Prix : 100, NaN, 121. Le rendement de la deuxième période est indéfini, et
    celui de la troisième aussi, faute de prix de référence.
    """
    prices = pd.Series([100.0, np.nan, 121.0], index=monthly_index(3))
    kept = to_returns(prices, dropna=False)
    assert len(kept) == 3
    assert int(kept.isna().sum()) == 3
    assert len(to_returns(prices)) == 0


# ---------------------------------------------------------------------------
# Richesse cumulée
# ---------------------------------------------------------------------------


def test_to_prices_hand_computed() -> None:
    """(a) 100 x 1,10 = 110, puis 110 x 0,90 = 99."""
    r = pd.Series([0.10, -0.10], index=monthly_index(2))
    wealth = to_prices(r, initial=100.0)
    assert wealth.iloc[0] == pytest.approx(110.0, abs=1e-12)
    assert wealth.iloc[1] == pytest.approx(99.0, abs=1e-12)


def test_total_loss_gives_zero_wealth_not_nan() -> None:
    """(a) Un rendement de -100 % annule la richesse : 1 x 1,10 x 0 x 1,50 = 0.

    Le produit cumulé doit rendre 0,0 et le rester, jamais un NaN qui se
    propagerait en silence jusqu'au ratio de Sharpe.
    """
    r = pd.Series([0.10, -1.0, 0.50], index=annual_index(3))
    wealth = cumulative_wealth(r)
    assert wealth.iloc[0] == pytest.approx(1.10, abs=1e-12)
    assert wealth.iloc[1] == 0.0
    assert wealth.iloc[2] == 0.0
    assert not wealth.isna().any()
    # (b) Le rendement composé d'une faillite vaut exactement -1.
    assert compound(r) == pytest.approx(-1.0, abs=1e-15)
    # (b) Le taux annuel composé d'un capital détruit vaut -100 %, pas un NaN.
    assert cagr(r, Frequency.ANNUAL) == -1.0


def test_total_loss_wealth_is_computed_without_any_warning() -> None:
    """(b) Mesuré le 2026-09-01 : la route logarithmique avertit, le produit non.

    ``exp(log1p(r).cumsum())`` rend la même richesse nulle sur un rendement de
    -100 %, mais numpy y émet « divide by zero encountered in log1p ». Ce test
    fige le choix du produit cumulé en transformant tout avertissement en
    erreur le temps de l'appel.
    """
    r = pd.Series([0.10, -1.0, 0.50], index=annual_index(3))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        wealth = to_prices(r)
    assert wealth.iloc[-1] == 0.0
    # La route écartée est bien celle qui avertit, ce qui rend le test discriminant.
    with pytest.raises(RuntimeWarning), warnings.catch_warnings():
        warnings.simplefilter("error")
        np.exp(np.log1p(r).cumsum())


def test_wealth_last_point_equals_compound() -> None:
    """(b) Identité V_T = V_0 (1 + R), reliant to_prices et compound."""
    rng = make_generator(7)
    r = pd.Series(rng.normal(0.004, 0.03, 120), index=monthly_index(120))
    assert float(to_prices(r).iloc[-1]) == pytest.approx(1.0 + compound(r), rel=1e-14)


def test_compound_of_monthly_returns_rebuilds_final_wealth() -> None:
    """(b) Composer douze mois redonne la richesse finale de l'indice cumulé."""
    rng = make_generator(1234)
    r = pd.Series(rng.normal(0.005, 0.04, 12), index=monthly_index(12))
    wealth = cumulative_wealth(r, initial=1000.0)
    assert float(wealth.iloc[-1]) == pytest.approx(1000.0 * (1.0 + compound(r)), rel=1e-13)


def test_compound_in_log_is_the_sum() -> None:
    """(b) En logarithme le rendement total est la somme, égale à ln(P_T/P_0)."""
    prices = pd.Series([100.0, 110.0, 99.0, 150.0], index=monthly_index(4))
    logs = to_returns(prices, ReturnKind.LOG)
    assert compound(logs, ReturnKind.LOG) == pytest.approx(float(np.log(150.0 / 100.0)), abs=1e-14)


def test_compound_skipna_false_propagates() -> None:
    """(b) Un manquant non ignoré doit ressortir en NaN plutôt que valoir zéro."""
    r = pd.Series([0.10, np.nan], index=monthly_index(2))
    assert compound(r) == pytest.approx(0.10, abs=1e-15)
    assert np.isnan(compound(r, skipna=False))


# ---------------------------------------------------------------------------
# Agrégation temporelle
# ---------------------------------------------------------------------------


def test_sum_of_monthly_logs_equals_annual_log() -> None:
    """(b) Additivité temporelle du rendement logarithmique.

    La somme des douze rendements logarithmiques mensuels de 2020 doit égaler
    ln(P_fin / P_debut) de la même année, à la précision machine.
    """
    rng = make_generator(99)
    prices = pd.Series(50.0 * np.exp(np.cumsum(rng.normal(0.0, 0.02, 24))), index=monthly_index(24))
    logs = to_returns(prices, ReturnKind.LOG)
    yearly = resample_returns(logs, Frequency.ANNUAL, ReturnKind.LOG)
    # 2020 : du prix de janvier (index 0) au prix de décembre (index 11).
    expected_2020 = float(np.log(prices.iloc[11] / prices.iloc[0]))
    assert float(yearly.iloc[0]) == pytest.approx(expected_2020, abs=1e-13)


def test_resample_simple_compounds_and_never_averages() -> None:
    """(a) Six paires (+10 %, -10 %) donnent 0,99^6 - 1 = -0,058519850599.

    0,99^2 = 0,9801 ; 0,99^3 = 0,970299 ; 0,99^6 = 0,970299^2 = 0,941480149401.
    La moyenne des douze rendements vaut exactement zéro, ce qui montre l'écart
    entre agréger et moyenner.
    """
    r = pd.Series([0.10, -0.10] * 6, index=monthly_index(12))
    annual = resample_returns(r, Frequency.ANNUAL)
    assert len(annual) == 1
    assert float(annual.iloc[0]) == pytest.approx(0.941480149401 - 1.0, abs=1e-12)
    assert float(r.mean()) == pytest.approx(0.0, abs=1e-17)


def test_resample_preserves_the_total_return() -> None:
    """(b) Composer les agrégats redonne le composé de la série fine."""
    rng = make_generator(3)
    daily = pd.Series(rng.normal(0.0004, 0.01, 504), index=pd.date_range("2020-01-01", periods=504, freq="B"))
    monthly = resample_returns(daily, Frequency.MONTHLY)
    assert compound(monthly) == pytest.approx(compound(daily), rel=1e-12)


def test_resample_frame_matches_column_by_column() -> None:
    """(b) L'agrégation d'un tableau est celle de chacune de ses colonnes."""
    rng = make_generator(11)
    idx = pd.date_range("2020-01-01", periods=252, freq="B")
    frame = pd.DataFrame({"a": rng.normal(0.0, 0.01, 252), "b": rng.normal(0.0, 0.02, 252)}, index=idx)
    aggregated = resample_returns(frame, Frequency.MONTHLY)
    for column in frame.columns:
        alone = resample_returns(frame[column], Frequency.MONTHLY)
        assert np.max(np.abs(aggregated[column].to_numpy() - alone.to_numpy())) < 1e-15


def test_resample_refuses_a_finer_frequency() -> None:
    """(b) Passer de mensuel à quotidien fabriquerait des trous, donc c'est refusé."""
    r = pd.Series([0.01] * 24, index=monthly_index(24))
    with pytest.raises(InsufficientDataError, match="fréquence plus fine"):
        resample_returns(r, Frequency.DAILY)


def test_resample_requires_a_datetime_index() -> None:
    """(b) Sans horodatage, aucune borne de période n'existe."""
    r = pd.Series([0.01, 0.02, 0.03])
    with pytest.raises(DataQualityError, match="DatetimeIndex"):
        resample_returns(r, Frequency.ANNUAL)


# ---------------------------------------------------------------------------
# CAGR et moyennes
# ---------------------------------------------------------------------------


def test_cagr_three_years_hand_computed() -> None:
    """(a) Une richesse de 1 portée à 1,331 en trois ans croît de 10 % par an.

    1,10^3 = 1,331 et 1,331^(1/3) = 1,10, donc le CAGR vaut exactement 0,10.
    """
    r = pd.Series([0.10, 0.10, 0.10], index=annual_index(3))
    assert float(to_prices(r).iloc[-1]) == pytest.approx(1.331, abs=1e-12)
    assert cagr(r, Frequency.ANNUAL) == pytest.approx(0.10, abs=1e-12)


def test_cagr_uses_years_not_observations() -> None:
    """(a) Trente-six mois font trois ans : le même 1,331 rend encore 10 %.

    Les rendements mensuels valent 1,331^(1/36) - 1, donc la richesse finale est
    1,331 et la durée trois ans.
    """
    monthly_rate = 1.331 ** (1.0 / 36.0) - 1.0
    r = pd.Series([monthly_rate] * 36, index=monthly_index(36))
    assert cagr(r, Frequency.MONTHLY) == pytest.approx(0.10, abs=1e-12)


def test_cagr_periods_argument_overrides_length() -> None:
    """(a) Douze rendements déclarés sur 24 périodes mensuelles valent deux ans.

    Le facteur de croissance est 1,10 ; sur deux ans le CAGR vaut
    1,10^(1/2) - 1 = 0,048808848170, soit racine de 1,1 moins un.
    """
    growth_rate = 1.10 ** (1.0 / 12.0) - 1.0
    r = pd.Series([growth_rate] * 12, index=monthly_index(12))
    assert cagr(r, Frequency.MONTHLY, periods=24) == pytest.approx(np.sqrt(1.10) - 1.0, abs=1e-12)


def test_cagr_equals_annualized_geometric_mean() -> None:
    """(b) Identité : le CAGR EST la moyenne géométrique annualisée."""
    rng = make_generator(555)
    r = pd.Series(rng.normal(0.006, 0.05, 240), index=monthly_index(240))
    assert geometric_mean_return(r, Frequency.MONTHLY) == pytest.approx(cagr(r, Frequency.MONTHLY), rel=1e-13)


def test_geometric_mean_matches_scipy_gmean() -> None:
    """(d) Implémentation indépendante : ``scipy.stats.gmean`` sur les facteurs.

    La moyenne géométrique des facteurs (1 + r) moins un est le rendement
    géométrique par période, sans annualisation.
    """
    rng = make_generator(2024)
    r = pd.Series(rng.normal(0.004, 0.03, 180), index=monthly_index(180))
    expected = float(gmean(1.0 + r.to_numpy())) - 1.0
    got = geometric_mean_return(r, Frequency.MONTHLY, annualize=False)
    assert got == pytest.approx(expected, rel=1e-13)


def test_arithmetic_mean_annualizes_linearly() -> None:
    """(a) Douze mois à 1 % font une moyenne annualisée de 12 %, par convention.

    L'annualisation retenue est linéaire, 0,01 x 12 = 0,12, et non composée,
    ce qui donnerait 1,01^12 - 1 = 0,126825.
    """
    r = pd.Series([0.01] * 12, index=monthly_index(12))
    assert arithmetic_mean_return(r, Frequency.MONTHLY) == pytest.approx(0.12, abs=1e-14)
    assert arithmetic_mean_return(r, Frequency.MONTHLY, annualize=False) == pytest.approx(0.01, abs=1e-15)
    # (b) La moyenne géométrique de rendements constants égale ce rendement.
    assert geometric_mean_return(r, Frequency.MONTHLY, annualize=False) == pytest.approx(0.01, abs=1e-14)
    # (a) Et son annualisation composée rend 1,01^12 - 1 = 0,126825030131.
    assert geometric_mean_return(r, Frequency.MONTHLY) == pytest.approx(0.126825030131, abs=1e-11)


def test_arithmetic_minus_geometric_is_about_half_the_variance() -> None:
    """(a) Sur (+2 %, -2 %) l'écart vaut 1 - sqrt(0,9996) = 0,000200020004.

    La moyenne arithmétique vaut exactement zéro. La moyenne géométrique vaut
    sqrt(1,02 x 0,98) - 1 = sqrt(0,9996) - 1. Le développement de sqrt(1 - u)
    en u = 0,0004 donne 1 - u/2 - u^2/8 - u^3/16, soit un écart de
    0,0002 + 0,00000002 + 0,000000000004 = 0,000200020004. La variance de
    population vaut 0,02^2 = 0,0004, dont la moitié est 0,0002 : l'approximation
    sigma^2/2 est juste à 2e-8 près.
    """
    x = 0.02
    r = pd.Series([x, -x], index=annual_index(2))
    mu_a = arithmetic_mean_return(r, Frequency.ANNUAL, annualize=False)
    mu_g = geometric_mean_return(r, Frequency.ANNUAL, annualize=False)
    assert mu_a == pytest.approx(0.0, abs=1e-17)
    assert mu_g == pytest.approx(np.sqrt(1.0 - x * x) - 1.0, abs=1e-15)
    gap = mu_a - mu_g
    assert gap == pytest.approx(0.000200020004, abs=1e-12)
    assert gap == pytest.approx(float(np.var(r.to_numpy())) / 2.0, abs=1e-7)


def test_log_convention_merges_the_two_means() -> None:
    """(b) En logarithme la composition est une somme, donc les deux moyennes coïncident."""
    rng = make_generator(31)
    prices = pd.Series(20.0 * np.exp(np.cumsum(rng.normal(0.0, 0.02, 100))), index=monthly_index(100))
    logs = to_returns(prices, ReturnKind.LOG)
    assert arithmetic_mean_return(logs, Frequency.MONTHLY, kind=ReturnKind.LOG) == pytest.approx(
        geometric_mean_return(logs, Frequency.MONTHLY, kind=ReturnKind.LOG), rel=1e-14
    )


def test_cagr_from_log_returns_matches_simple() -> None:
    """(b) Le CAGR ne dépend pas de la convention d'entrée, seulement des prix."""
    prices = pd.Series([100.0, 121.0, 133.1], index=annual_index(3, start="2019-12-31"))
    simple = to_returns(prices, ReturnKind.SIMPLE)
    logs = to_returns(prices, ReturnKind.LOG)
    assert cagr(logs, Frequency.ANNUAL, kind=ReturnKind.LOG) == pytest.approx(
        cagr(simple, Frequency.ANNUAL), abs=1e-13
    )


def test_frame_reductions_are_column_wise() -> None:
    """(b) Sur un tableau, chaque statistique doit égaler celle de sa colonne."""
    rng = make_generator(808)
    frame = pd.DataFrame(
        {"a": rng.normal(0.004, 0.03, 60), "b": rng.normal(0.002, 0.05, 60)},
        index=monthly_index(60),
    )
    for column in frame.columns:
        assert cagr(frame, Frequency.MONTHLY)[column] == pytest.approx(
            cagr(frame[column], Frequency.MONTHLY), rel=1e-14
        )
        assert compound(frame)[column] == pytest.approx(compound(frame[column]), rel=1e-14)


# ---------------------------------------------------------------------------
# Rendements en excès
# ---------------------------------------------------------------------------


def test_excess_returns_two_conventions_hand_computed() -> None:
    """(a) À 10 % de rendement et 4 % de taux, 0,06 contre 0,06/1,04 = 0,057692307692.

    La différence arithmétique vaut 0,10 - 0,04 = 0,06. La déflation
    géométrique vaut 1,10/1,04 - 1, ce qui s'écrit (0,10 - 0,04)/1,04.
    """
    r = pd.Series([0.10], index=pd.DatetimeIndex(["2020-12-31"]))
    arithmetic = excess_returns(r, 0.04, Frequency.ANNUAL, method="arithmetic")
    geometric = excess_returns(r, 0.04, Frequency.ANNUAL, method="geometric")
    assert float(arithmetic.iloc[0]) == pytest.approx(0.06, abs=1e-14)
    assert float(geometric.iloc[0]) == pytest.approx(0.057692307692, abs=1e-12)
    # (b) Identité exacte reliant les deux conventions.
    assert float(geometric.iloc[0]) == pytest.approx(0.06 / 1.04, abs=1e-15)


def test_risk_free_deannualization_composes_back_to_the_annual_rate() -> None:
    """(b) Douze taux mensuels composés doivent redonner exactement 4 % par an.

    Avec des rendements nuls, l'excès arithmétique vaut moins le taux de période.
    """
    zero = pd.Series([0.0] * 12, index=monthly_index(12))
    periodic = -excess_returns(zero, 0.04, Frequency.MONTHLY)
    assert float((1.0 + periodic).prod()) == pytest.approx(1.04, rel=1e-13)


def test_linear_deannualization_divides_by_the_period_count() -> None:
    """(a) La convention monétaire donne 0,04/12 = 0,003333333333 par mois."""
    zero = pd.Series([0.0] * 12, index=monthly_index(12))
    periodic = -excess_returns(zero, 0.04, Frequency.MONTHLY, deannualize="linear")
    assert float(periodic.iloc[0]) == pytest.approx(0.04 / 12.0, abs=1e-15)
    assert float(periodic.iloc[0]) == pytest.approx(0.003333333333, abs=1e-12)


def test_already_periodic_rate_is_left_alone() -> None:
    """(a) Un taux mensuel de 0,3 % retiré d'un rendement de 1 % laisse 0,7 %."""
    r = pd.Series([0.01] * 3, index=monthly_index(3))
    got = excess_returns(r, 0.003, Frequency.MONTHLY, annualized_rate=False)
    assert float(got.iloc[0]) == pytest.approx(0.007, abs=1e-15)


def test_excess_returns_with_a_rate_series_aligns_on_the_intersection() -> None:
    """(a) Le taux ne couvre que deux des trois mois, donc l'excès en porte deux."""
    r = pd.Series([0.01, 0.02, 0.03], index=monthly_index(3))
    rf = pd.Series([0.0, 0.0], index=monthly_index(3)[1:])
    got = excess_returns(r, rf, Frequency.MONTHLY, annualized_rate=False)
    assert len(got) == 2
    assert got.index.equals(monthly_index(3)[1:])
    assert float(got.iloc[0]) == pytest.approx(0.02, abs=1e-15)


def test_excess_returns_in_log_ignores_the_method() -> None:
    """(b) En logarithme, retirer ln(1 + rf) est la seule opération possible.

    ln(1,10/1,04) = ln(1,10) - ln(1,04), donc les deux méthodes coïncident.
    """
    logs = pd.Series([float(np.log(1.10))], index=pd.DatetimeIndex(["2020-12-31"]))
    arithmetic = excess_returns(logs, 0.04, Frequency.ANNUAL, kind=ReturnKind.LOG, method="arithmetic")
    geometric = excess_returns(logs, 0.04, Frequency.ANNUAL, kind=ReturnKind.LOG, method="geometric")
    expected = float(np.log(1.10 / 1.04))
    assert float(arithmetic.iloc[0]) == pytest.approx(expected, abs=1e-15)
    assert float(geometric.iloc[0]) == pytest.approx(expected, abs=1e-15)


def test_excess_returns_rejects_unknown_options() -> None:
    """(b) Une convention inconnue doit échouer tout de suite, pas silencieusement."""
    r = pd.Series([0.01], index=pd.DatetimeIndex(["2020-01-31"]))
    with pytest.raises(ValueError, match="method"):
        excess_returns(r, 0.0, Frequency.MONTHLY, method="moyenne")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="deannualize"):
        excess_returns(r, 0.0, Frequency.MONTHLY, deannualize="racine")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Alignement
# ---------------------------------------------------------------------------


def test_align_returns_keeps_the_intersection() -> None:
    """(a) Trois dates contre deux qui commencent un jour plus tard : deux communes."""
    a = pd.Series([1.0, 2.0, 3.0], index=pd.date_range("2020-01-01", periods=3))
    b = pd.Series([9.0, 9.0], index=pd.date_range("2020-01-02", periods=2))
    aligned_a, aligned_b = align_returns(a, b)
    assert len(aligned_a) == 2
    assert len(aligned_b) == 2
    assert aligned_a.index.equals(aligned_b.index)
    assert aligned_a.tolist() == [2.0, 3.0]


def test_align_returns_refuses_an_empty_overlap() -> None:
    """(b) Sans date commune, aucune statistique conjointe n'existe."""
    a = pd.Series([1.0], index=pd.DatetimeIndex(["2020-01-01"]))
    b = pd.Series([1.0], index=pd.DatetimeIndex(["2021-01-01"]))
    with pytest.raises(InsufficientDataError, match="recouvrement"):
        align_returns(a, b)


def test_align_returns_needs_two_objects() -> None:
    """(b) Aligner un seul objet n'a pas de sens."""
    a = pd.Series([1.0], index=pd.DatetimeIndex(["2020-01-01"]))
    with pytest.raises(ValueError, match="au moins deux"):
        align_returns(a)


# ---------------------------------------------------------------------------
# Cas limites
# ---------------------------------------------------------------------------


def test_empty_series_raise_rather_than_return_nan() -> None:
    """(b) Une série vide ne porte aucune information, donc le calcul s'arrête."""
    empty = pd.Series(dtype="float64", index=pd.DatetimeIndex([]))
    for call in (
        lambda: to_prices(empty),
        lambda: compound(empty),
        lambda: cagr(empty, Frequency.MONTHLY),
        lambda: arithmetic_mean_return(empty, Frequency.MONTHLY),
        lambda: geometric_mean_return(empty, Frequency.MONTHLY),
    ):
        with pytest.raises(InsufficientDataError):
            call()


def test_single_observation_is_handled_without_annualizing_a_lie() -> None:
    """(a) Un mois à +1 % compose sur un douzième d'année : 1,01^12 - 1 = 0,126825030131.

    Le chiffre est correct arithmétiquement et absurde financièrement, ce que la
    docstring du module déclare. Le test fige le comportement, pas la sagesse.
    """
    r = pd.Series([0.01], index=monthly_index(1))
    assert compound(r) == pytest.approx(0.01, abs=1e-15)
    assert cagr(r, Frequency.MONTHLY) == pytest.approx(0.126825030131, abs=1e-11)


def test_constant_series_has_zero_dispersion_and_equal_means() -> None:
    """(b) Sur des rendements constants, moyenne arithmétique et géométrique coïncident."""
    r = pd.Series([0.005] * 60, index=monthly_index(60))
    mu_a = arithmetic_mean_return(r, Frequency.MONTHLY, annualize=False)
    mu_g = geometric_mean_return(r, Frequency.MONTHLY, annualize=False)
    assert mu_a == pytest.approx(mu_g, abs=1e-15)
    # (a) Des prix constants ne produisent que des rendements nuls.
    flat_prices = pd.Series([42.0] * 10, index=monthly_index(10))
    assert to_returns(flat_prices).abs().max() == 0.0


def test_a_fully_missing_series_gives_nan_not_a_zero_return() -> None:
    """(b) Identité V_T = V_0 (1 + R) : si la richesse est NaN, le composé l'est aussi.

    Une série sans aucune observation valide ne porte aucun rendement total. Le
    produit d'un ensemble vide vaut 1 en pandas, donc la version sans garde
    annonçait exactement 0 %, et le CAGR annonçait 0 %/an sur une stratégie dont
    rien n'est mesuré. Mesuré le 2026-09-01 avant correction : ``compound``
    rendait 0,0 et ``to_prices`` rendait NaN sur la MÊME entrée, ce qui casse
    l'identité que la docstring de ``compound`` donne comme moyen de vérifier.
    """
    empty_of_content = pd.Series([np.nan] * 3, index=monthly_index(3))
    wealth = to_prices(empty_of_content)
    assert np.isnan(float(wealth.iloc[-1]))
    # (b) L'identité impose donc NaN des deux côtés.
    assert np.isnan(compound(empty_of_content))
    assert np.isnan(compound(empty_of_content, ReturnKind.LOG))
    assert np.isnan(cagr(empty_of_content, Frequency.MONTHLY))
    assert np.isnan(geometric_mean_return(empty_of_content, Frequency.MONTHLY))
    # (b) La moyenne arithmétique rendait déjà NaN : les quatre doivent s'accorder.
    assert np.isnan(arithmetic_mean_return(empty_of_content, Frequency.MONTHLY))
    # (b) Faillite et absence de mesure sont deux états distincts : -1,0 contre NaN.
    ruined = pd.Series([-1.0, 0.20, 0.30], index=monthly_index(3))
    assert cagr(ruined, Frequency.MONTHLY) == -1.0
    assert geometric_mean_return(ruined, Frequency.MONTHLY) == -1.0


def test_one_valid_observation_still_compounds_normally() -> None:
    """(a) 1,10 x 1 = 1,10 : la garde du manquant total ne doit rien changer ici.

    Le correctif précédent ne doit pas transformer en NaN une série qui porte au
    moins une observation. Une seule valeur suffit.
    """
    partial = pd.Series([0.10, np.nan], index=monthly_index(2))
    assert compound(partial) == pytest.approx(0.10, abs=1e-15)
    frame = pd.DataFrame({"vide": [np.nan, np.nan], "pleine": [0.10, np.nan]}, index=monthly_index(2))
    totals = compound(frame)
    assert np.isnan(float(totals["vide"]))
    assert float(totals["pleine"]) == pytest.approx(0.10, abs=1e-15)


def test_resampling_a_timezone_aware_index_emits_no_warning() -> None:
    """(b) Le garde-fou doit mesurer la même durée avec et sans fuseau horaire.

    Mesuré le 2026-09-01 avant correction : sur un index à fuseau, numpy émettait
    « no explicit representation of timezones available for np.datetime64 ». Le
    portefeuille travaille sur des barres intrajournalières horodatées en heure
    de New York, donc l'avertissement se déclenche en usage normal.
    """
    aware = pd.date_range("2020-01-01 09:30", periods=90, freq="D", tz="America/New_York")
    returns = pd.Series([0.001] * 90, index=aware)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        got = resample_returns(returns, Frequency.MONTHLY)
    # (b) Même série sans fuseau : l'agrégation ne dépend pas de l'étiquette de fuseau.
    naive = pd.Series([0.001] * 90, index=aware.tz_convert("UTC").tz_localize(None))
    expected = resample_returns(naive, Frequency.MONTHLY)
    assert np.max(np.abs(got.to_numpy() - expected.to_numpy())) < 1e-15
    # (a) Quatre-vingt-dix jours se répartissent en 31, 29 et 30, l'année 2020 étant bissextile.
    assert len(got) == 3
    assert float(got.iloc[0]) == pytest.approx(1.001**31 - 1.0, abs=1e-14)
    # (a) Février : 1,001^29 - 1 = 0,029409677870, calculé à part.
    assert float(got.iloc[1]) == pytest.approx(0.029409677870, abs=1e-12)
    assert float(got.iloc[2]) == pytest.approx(1.001**30 - 1.0, abs=1e-14)


def test_nan_inside_returns_is_treated_as_a_flat_period() -> None:
    """(a) 1,10 x 1 x 0,90 = 0,99 quand le manquant est ignoré."""
    r = pd.Series([0.10, np.nan, -0.10], index=monthly_index(3))
    assert float(to_prices(r).iloc[-1]) == pytest.approx(0.99, abs=1e-15)


# ---------------------------------------------------------------------------
# Propriétés (hypothesis)
# ---------------------------------------------------------------------------

price_lists = st.lists(
    st.floats(min_value=0.01, max_value=10_000.0, allow_nan=False, allow_infinity=False),
    min_size=2,
    max_size=60,
)
return_lists = st.lists(
    st.floats(min_value=-0.95, max_value=1.5, allow_nan=False, allow_infinity=False),
    min_size=2,
    max_size=60,
)


@given(prices=price_lists)
@settings(deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_property_price_round_trip(prices: list[float]) -> None:
    """(b) to_prices(to_returns(p), initial=p_0) reproduit p, à la constante près."""
    series = pd.Series(prices, index=pd.date_range("2000-01-31", periods=len(prices), freq="ME"))
    rebuilt = to_prices(to_returns(series), initial=float(series.iloc[0]))
    assert np.allclose(rebuilt.to_numpy(), series.to_numpy()[1:], rtol=1e-9, atol=1e-12)


@given(prices=price_lists, scale=st.floats(min_value=0.001, max_value=1000.0, allow_nan=False))
@settings(deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_property_returns_are_scale_invariant(prices: list[float], scale: float) -> None:
    """(b) Multiplier tous les prix par une constante ne change aucun rendement."""
    index = pd.date_range("2000-01-31", periods=len(prices), freq="ME")
    base = to_returns(pd.Series(prices, index=index))
    scaled = to_returns(pd.Series([p * scale for p in prices], index=index))
    assert np.allclose(base.to_numpy(), scaled.to_numpy(), rtol=1e-9, atol=1e-12)


@given(returns=return_lists, cut=st.integers(min_value=1, max_value=59))
@settings(deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_property_compound_splits_multiplicatively(returns: list[float], cut: int) -> None:
    """(b) (1 + R_total) = (1 + R_debut)(1 + R_fin), quelle que soit la coupure."""
    cut = min(cut, len(returns) - 1)
    series = pd.Series(returns, index=pd.date_range("2000-01-31", periods=len(returns), freq="ME"))
    total = 1.0 + compound(series)
    head = 1.0 + compound(series.iloc[:cut])
    tail = 1.0 + compound(series.iloc[cut:])
    assert total == pytest.approx(head * tail, rel=1e-9, abs=1e-12)


@given(returns=return_lists)
@settings(deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_property_arithmetic_never_below_geometric(returns: list[float]) -> None:
    """(b) Inégalité arithmético-géométrique, vraie sur toute série de facteurs positifs."""
    series = pd.Series(returns, index=pd.date_range("2000-01-31", periods=len(returns), freq="ME"))
    mu_a = arithmetic_mean_return(series, Frequency.MONTHLY, annualize=False)
    mu_g = geometric_mean_return(series, Frequency.MONTHLY, annualize=False)
    assert mu_a >= mu_g - 1e-12


@given(returns=return_lists)
@settings(deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_property_log_aggregation_is_a_sum(returns: list[float]) -> None:
    """(b) La somme des logarithmes égale le logarithme du facteur total."""
    series = pd.Series(returns, index=pd.date_range("2000-01-31", periods=len(returns), freq="ME"))
    logs = simple_to_log(series)
    assert float(logs.sum()) == pytest.approx(float(np.log1p(compound(series))), rel=1e-9, abs=1e-12)

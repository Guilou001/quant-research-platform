"""Contrôles du module ``quantlab.analytics.ic``.

Chaque valeur attendue vient d'une source déclarée en commentaire, jamais de la
sortie du code. Les quatre sources admises sont le calcul à la main, l'identité
mathématique, la valeur publiée et l'implémentation indépendante.
"""

from __future__ import annotations

import math

import hypothesis.strategies as st
import numpy as np
import pandas as pd
import pytest
import scipy.stats as sps
import statsmodels.api as sm
from hypothesis import HealthCheck, assume, given, settings

from quantlab.analytics.ic import (
    _newey_west_lags,
    effective_breadth,
    equicorrelated_breadth,
    fundamental_law,
    ic_by_group,
    ic_series,
    ic_summary,
    information_coefficient,
    quantile_returns,
    quantile_spread,
    rolling_ic,
)
from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.types import Frequency

ASSETS = [f"A{i}" for i in range(10)]
DATES = pd.to_datetime(["2020-01-31", "2020-02-29", "2020-03-31"])


def _hand_panels() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rend le panier construit à la main : dix actifs, trois dates.

    Date 1 : le signal ordonne les actifs exactement comme les rendements.
    Date 2 : le signal les ordonne exactement à l'envers.
    Date 3 : un cas quelconque, dont les moyennes de quantiles sont calculées
    à la main dans le test qui s'en sert.
    """
    predictions = pd.DataFrame(
        [
            [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0],
            [9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0, 0.0],
            [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0],
        ],
        index=DATES,
        columns=ASSETS,
    )
    realized = pd.DataFrame(
        [
            [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10],
            [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10],
            [0.05, -0.01, 0.02, 0.00, 0.04, -0.03, 0.06, 0.01, -0.02, 0.08],
        ],
        index=DATES,
        columns=ASSETS,
    )
    return predictions, realized


# --------------------------------------------------------------------------- #
# information_coefficient
# --------------------------------------------------------------------------- #


def test_spearman_matches_scipy() -> None:
    """Source (d) : implémentation indépendante, ``scipy.stats.spearmanr``."""
    names = list("abcdefgh")
    predictions = pd.Series([3.0, 1.0, 4.0, 1.5, 5.0, 9.0, 2.0, 6.0], index=names)
    realized = pd.Series([0.02, -0.01, 0.03, 0.00, 0.05, -0.02, 0.01, 0.04], index=names)
    expected = sps.spearmanr(predictions.to_numpy(), realized.to_numpy()).statistic
    assert information_coefficient(predictions, realized) == pytest.approx(expected, abs=1e-12)


def test_spearman_matches_scipy_with_ties() -> None:
    """Source (d) : scipy sur des ex aequo, où la convention de rang moyen décide."""
    names = list("abcdef")
    predictions = pd.Series([1.0, 1.0, 2.0, 2.0, 3.0, 3.0], index=names)
    realized = pd.Series([0.01, 0.02, 0.02, 0.03, 0.03, 0.05], index=names)
    expected = sps.spearmanr(predictions.to_numpy(), realized.to_numpy()).statistic
    assert information_coefficient(predictions, realized) == pytest.approx(expected, abs=1e-12)


def test_pearson_matches_scipy() -> None:
    """Source (d) : implémentation indépendante, ``scipy.stats.pearsonr``."""
    names = list("abcdefgh")
    predictions = pd.Series([3.0, 1.0, 4.0, 1.5, 5.0, 9.0, 2.0, 6.0], index=names)
    realized = pd.Series([0.02, -0.01, 0.03, 0.00, 0.05, -0.02, 0.01, 0.04], index=names)
    expected = sps.pearsonr(predictions.to_numpy(), realized.to_numpy()).statistic
    assert information_coefficient(predictions, realized, method="pearson") == pytest.approx(
        expected, abs=1e-12
    )


def test_perfect_ranking_gives_plus_one_and_reversed_minus_one() -> None:
    """Source (b) : identité. Rangs identiques donnent +1, rangs opposés -1."""
    names = list("abcdefg")
    predictions = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0], index=names)
    realized = pd.Series([0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07], index=names)
    assert information_coefficient(predictions, realized) == pytest.approx(1.0, abs=1e-12)
    # L'inversion porte sur les VALEURS, l'index restant en place : l'alignement se
    # fait par identifiant d'actif, si bien qu'inverser aussi l'index ne changerait rien.
    reversed_values = pd.Series(predictions.to_numpy()[::-1], index=names)
    assert information_coefficient(reversed_values, realized) == pytest.approx(-1.0, abs=1e-12)


def test_ic_survives_a_total_loss() -> None:
    """Cas limite : un rendement de -100 %. Source (d), scipy sur le même intrant."""
    names = list("abcde")
    predictions = pd.Series([5.0, 4.0, 3.0, 2.0, 1.0], index=names)
    realized = pd.Series([0.10, 0.05, 0.00, -0.50, -1.00], index=names)
    expected = sps.spearmanr(predictions.to_numpy(), realized.to_numpy()).statistic
    # Le classement est parfait, donc l'identité (b) prévoit aussi +1.
    assert expected == pytest.approx(1.0, abs=1e-12)
    assert information_coefficient(predictions, realized) == pytest.approx(1.0, abs=1e-12)


def test_ic_drops_missing_pairs_before_correlating() -> None:
    """Source (d) : scipy sur les seules paires complètes, calculées séparément."""
    names = list("abcdef")
    predictions = pd.Series([1.0, 2.0, np.nan, 4.0, 5.0, 6.0], index=names)
    realized = pd.Series([0.01, 0.02, 0.03, np.nan, 0.05, 0.06], index=names)
    kept_pred = np.array([1.0, 2.0, 5.0, 6.0])
    kept_real = np.array([0.01, 0.02, 0.05, 0.06])
    expected = sps.spearmanr(kept_pred, kept_real).statistic
    got = information_coefficient(predictions, realized, min_names=4)
    assert got == pytest.approx(expected, abs=1e-12)


def test_ic_returns_nan_below_min_names() -> None:
    """Quatre noms communs sous un plancher de cinq : la fonction rend ``nan``."""
    names = list("abcd")
    predictions = pd.Series([1.0, 2.0, 3.0, 4.0], index=names)
    realized = pd.Series([0.01, 0.02, 0.03, 0.04], index=names)
    assert math.isnan(information_coefficient(predictions, realized, min_names=5))


def test_ic_returns_nan_on_constant_cross_section() -> None:
    """Source (b) : une coupe constante a un écart type nul, la corrélation n'existe pas."""
    names = list("abcde")
    predictions = pd.Series([1.0, 1.0, 1.0, 1.0, 1.0], index=names)
    realized = pd.Series([0.01, 0.02, 0.03, 0.04, 0.05], index=names)
    assert math.isnan(information_coefficient(predictions, realized))


def test_ic_returns_nan_on_empty_and_single_point() -> None:
    """Cas limites : série vide et série d'un seul point."""
    empty = pd.Series(dtype=float)
    assert math.isnan(information_coefficient(empty, empty, min_names=2))
    one = pd.Series([1.0], index=["a"])
    assert math.isnan(information_coefficient(one, pd.Series([0.01], index=["a"]), min_names=2))


def test_ic_rejects_duplicate_asset_identifiers() -> None:
    """Un identifiant en double rendrait l'alignement ambigu."""
    predictions = pd.Series([1.0, 2.0, 3.0], index=["a", "a", "b"])
    realized = pd.Series([0.01, 0.02, 0.03], index=["a", "a", "b"])
    with pytest.raises(DataQualityError):
        information_coefficient(predictions, realized, min_names=2)


def test_ic_rejects_min_names_below_two() -> None:
    """Une corrélation exige deux points, le plancher ne peut pas descendre plus bas."""
    predictions = pd.Series([1.0, 2.0], index=["a", "b"])
    with pytest.raises(ConfigError):
        information_coefficient(predictions, predictions, min_names=1)


# --------------------------------------------------------------------------- #
# Propriétés (hypothesis)
# --------------------------------------------------------------------------- #


@st.composite
def _cross_section(draw: st.DrawFn) -> tuple[list[float], list[float]]:
    """Tire une coupe transversale de cinq à vingt-cinq actifs."""
    size = draw(st.integers(min_value=5, max_value=25))
    finite = st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False)
    predictions = draw(st.lists(finite, min_size=size, max_size=size, unique=True))
    outcomes = st.floats(min_value=-1.0, max_value=5.0, allow_nan=False, allow_infinity=False)
    realized = draw(st.lists(outcomes, min_size=size, max_size=size))
    return predictions, realized


@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(sample=_cross_section())
def test_spearman_invariant_under_increasing_transform(sample: tuple[list[float], list[float]]) -> None:
    """Source (b) : le rang ne change pas sous une transformation strictement croissante.

    La fonction cube est strictement croissante sur les réels, donc préserve
    l'ordre exact des prédictions. Le coefficient de Spearman, calculé sur les
    seuls rangs, doit donc rester le même.
    """
    predictions, realized = sample
    assume(len(set(realized)) > 1)
    transformed = [value**3 for value in predictions]
    assume(len(set(transformed)) == len(transformed))
    names = [f"A{i}" for i in range(len(predictions))]
    base = information_coefficient(pd.Series(predictions, index=names), pd.Series(realized, index=names))
    moved = information_coefficient(pd.Series(transformed, index=names), pd.Series(realized, index=names))
    assert moved == pytest.approx(base, abs=1e-9)


@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(sample=_cross_section())
def test_spearman_flips_sign_with_negated_predictions(sample: tuple[list[float], list[float]]) -> None:
    """Source (b) : nier les prédictions renverse l'ordre, donc le signe du coefficient."""
    predictions, realized = sample
    assume(len(set(realized)) > 1)
    names = [f"A{i}" for i in range(len(predictions))]
    base = information_coefficient(pd.Series(predictions, index=names), pd.Series(realized, index=names))
    flipped = information_coefficient(
        pd.Series([-value for value in predictions], index=names), pd.Series(realized, index=names)
    )
    assert flipped == pytest.approx(-base, abs=1e-9)


# --------------------------------------------------------------------------- #
# ic_series
# --------------------------------------------------------------------------- #


def test_ic_series_on_hand_panel() -> None:
    """Source (b) : ordre parfait puis ordre inversé donnent +1 puis -1."""
    predictions, realized = _hand_panels()
    got = ic_series(predictions, realized)
    assert list(got.index) == list(DATES)
    assert got.iloc[0] == pytest.approx(1.0, abs=1e-12)
    assert got.iloc[1] == pytest.approx(-1.0, abs=1e-12)
    # Date 3 : source (d), scipy sur la même coupe.
    expected = sps.spearmanr(predictions.iloc[2].to_numpy(), realized.iloc[2].to_numpy()).statistic
    assert got.iloc[2] == pytest.approx(expected, abs=1e-12)


def test_ic_series_marks_thin_dates_with_nan() -> None:
    """Une date où trop peu d'actifs sont renseignés porte ``nan``, sans arrêter le calcul."""
    predictions, realized = _hand_panels()
    thin = realized.copy()
    thin.iloc[1, 2:] = np.nan  # il ne reste que deux actifs renseignés à la date 2
    got = ic_series(predictions, thin, min_names=5)
    assert got.iloc[0] == pytest.approx(1.0, abs=1e-12)
    assert math.isnan(got.iloc[1])


def test_ic_series_requires_common_dates_and_assets() -> None:
    """Sans intersection, la fonction refuse plutôt que de rendre une série vide."""
    predictions, realized = _hand_panels()
    with pytest.raises(InsufficientDataError):
        ic_series(predictions, realized.rename(index=lambda date: date + pd.Timedelta(days=1)))
    with pytest.raises(InsufficientDataError):
        ic_series(predictions, realized.rename(columns=lambda name: f"Z{name}"))


# --------------------------------------------------------------------------- #
# ic_summary
# --------------------------------------------------------------------------- #


def test_ic_summary_hand_computed() -> None:
    """Source (a) : calcul à la main sur la série 0,10 puis 0,00.

    Moyenne = (0,10 + 0,00) / 2 = 0,05.
    Écart type d'échantillon = racine((0,05² + 0,05²) / 1) = racine(0,005) = 0,0707107.
    Rapport = 0,05 / 0,0707107 = 0,7071068 ; annualisé mensuel, fois racine(12) = 2,4494897.
    Retards de Newey-West sur deux points : plancher(4 × 0,02^(2/9)) = 1, borné à T - 1 = 1.
    Gamma zéro = (0,05² + 0,05²) / 2 = 0,0025 ; gamma un = (-0,05 × 0,05) / 2 = -0,00125.
    Variance de la moyenne = (0,0025 + 2 × 0,5 × (-0,00125)) / 2 = 0,000625.
    Erreur type = 0,025, donc t = 0,05 / 0,025 = 2,0 exactement.
    """
    summary = ic_summary(pd.Series([0.10, 0.00]))
    assert summary.n_periods == 2
    assert summary.mean == pytest.approx(0.05, abs=1e-15)
    assert summary.median == pytest.approx(0.05, abs=1e-15)
    assert summary.std == pytest.approx(0.0707106781186548, abs=1e-12)
    assert summary.ir_per_period == pytest.approx(0.7071067811865476, abs=1e-12)
    assert summary.ir_annualized == pytest.approx(2.449489742783178, abs=1e-12)
    assert summary.hac_lags == 1
    assert summary.t_stat_hac == pytest.approx(2.0, abs=1e-12)
    assert summary.hit_rate == pytest.approx(0.5, abs=1e-15)


def test_ic_summary_t_stat_matches_statsmodels_hac() -> None:
    """Source (d) : régression sur une constante, ``statsmodels`` en HAC sans correction."""
    rng = np.random.default_rng(np.random.SeedSequence(20260901))
    values = 0.03 + 0.01 * np.cumsum(rng.normal(size=150))
    lags = _newey_west_lags(150)
    fitted = sm.OLS(values, np.ones(150)).fit(
        cov_type="HAC", cov_kwds={"maxlags": lags, "use_correction": False}
    )
    summary = ic_summary(pd.Series(values))
    assert summary.hac_lags == lags
    assert summary.t_stat_hac == pytest.approx(float(fitted.tvalues[0]), rel=1e-10)


def test_ic_summary_without_lags_matches_the_student_t() -> None:
    """Sources (d) et (b) : scipy pour le t ordinaire, l'identité pour le facteur d'échelle.

    À zéro retard, la variance de la moyenne vaut gamma zéro sur T, avec gamma
    zéro normalisé par T et non par T - 1. Le t rendu vaut donc celui de
    ``scipy.stats.ttest_1samp`` multiplié par racine(T / (T - 1)).
    """
    values = np.array([0.04, -0.01, 0.02, 0.06, -0.03, 0.05, 0.00, 0.01])
    n = values.size
    reference = sps.ttest_1samp(values, popmean=0.0).statistic
    summary = ic_summary(pd.Series(values), hac_lags=0)
    assert summary.hac_lags == 0
    assert summary.t_stat_hac == pytest.approx(reference * math.sqrt(n / (n - 1)), rel=1e-12)


def test_ic_summary_ignores_missing_dates() -> None:
    """Les ``nan`` sont retirés, pas remplacés par zéro : la moyenne reste 0,05."""
    summary = ic_summary(pd.Series([0.10, np.nan, 0.00, np.nan]))
    assert summary.n_periods == 2
    assert summary.mean == pytest.approx(0.05, abs=1e-15)


def test_ic_summary_refuses_a_single_point() -> None:
    """Cas limite : un seul point, l'écart type d'échantillon n'existe pas."""
    with pytest.raises(InsufficientDataError):
        ic_summary(pd.Series([0.10]))
    with pytest.raises(InsufficientDataError):
        ic_summary(pd.Series(dtype=float))


def test_ic_summary_constant_series_has_no_dispersion() -> None:
    """Cas limite : une série constante a un écart type nul, donc un ratio non défini."""
    summary = ic_summary(pd.Series([0.05, 0.05, 0.05, 0.05]))
    assert summary.std == pytest.approx(0.0, abs=1e-15)
    assert math.isnan(summary.ir_per_period)
    assert math.isnan(summary.t_stat_hac)
    assert summary.hit_rate == pytest.approx(1.0, abs=1e-15)


def test_ic_summary_annualization_follows_the_frequency() -> None:
    """Source (b) : le rapport annualisé est le rapport par période fois racine(N)."""
    series = pd.Series([0.10, 0.00, 0.05, 0.03])
    monthly = ic_summary(series, frequency=Frequency.MONTHLY)
    daily = ic_summary(series, frequency=Frequency.DAILY)
    assert daily.ir_annualized == pytest.approx(monthly.ir_annualized * math.sqrt(252.0 / 12.0), rel=1e-12)


# --------------------------------------------------------------------------- #
# rolling_ic et ic_by_group
# --------------------------------------------------------------------------- #


def test_rolling_ic_hand_computed() -> None:
    """Source (a) : fenêtre de deux sur la série 0,10 puis 0,00 puis 0,20.

    Première fenêtre pleine : moyenne (0,10 + 0,00) / 2 = 0,05, écart type
    racine(0,005) = 0,0707107, rapport 0,7071068, annualisé mensuel 2,4494897.
    Seconde : moyenne (0,00 + 0,20) / 2 = 0,10, écart type racine(0,02) = 0,1414214,
    rapport 0,7071068, donc la même valeur annualisée.
    """
    table = rolling_ic(pd.Series([0.10, 0.00, 0.20]), window=2)
    assert math.isnan(table["mean"].iloc[0])
    assert table["mean"].iloc[1] == pytest.approx(0.05, abs=1e-15)
    assert table["std"].iloc[1] == pytest.approx(0.0707106781186548, abs=1e-12)
    assert table["ir_annualized"].iloc[1] == pytest.approx(2.449489742783178, abs=1e-12)
    assert table["mean"].iloc[2] == pytest.approx(0.10, abs=1e-15)
    assert table["std"].iloc[2] == pytest.approx(0.1414213562373095, abs=1e-12)
    assert table["ir_annualized"].iloc[2] == pytest.approx(2.449489742783178, abs=1e-12)


def test_rolling_ic_rejects_a_window_of_one() -> None:
    """Une fenêtre d'un point n'a pas d'écart type."""
    with pytest.raises(ConfigError):
        rolling_ic(pd.Series([0.1, 0.2]), window=1)


def test_ic_by_group_hand_computed() -> None:
    """Source (a) : deux régimes, moyennes et écarts types calculés à la main.

    Régime « haut » : 0,10 et 0,00, moyenne 0,05, écart type racine(0,005) = 0,0707107.
    Régime « bas » : 0,20 et -0,40, moyenne -0,10, écart type racine(0,18) = 0,4242641.
    Chaque régime porte une valeur strictement positive sur deux, donc 0,5.
    """
    ic = pd.Series([0.10, 0.00, 0.20, -0.40], index=pd.RangeIndex(4))
    groups = pd.Series(["haut", "haut", "bas", "bas"], index=pd.RangeIndex(4))
    table = ic_by_group(ic, groups)
    assert list(table.index) == ["haut", "bas"]
    assert table.loc["haut", "mean"] == pytest.approx(0.05, abs=1e-15)
    assert table.loc["haut", "std"] == pytest.approx(0.0707106781186548, abs=1e-12)
    assert table.loc["bas", "mean"] == pytest.approx(-0.10, abs=1e-15)
    assert table.loc["bas", "std"] == pytest.approx(0.4242640687119285, abs=1e-12)
    assert table.loc["bas", "hit_rate"] == pytest.approx(0.5, abs=1e-15)
    assert table.loc["bas", "n_periods"] == 2


def test_ic_by_group_requires_a_common_index() -> None:
    """Sans date commune, la fonction refuse plutôt que de rendre un tableau vide."""
    ic = pd.Series([0.1, 0.2], index=[0, 1])
    groups = pd.Series(["a", "b"], index=[7, 8])
    with pytest.raises(InsufficientDataError):
        ic_by_group(ic, groups)


# --------------------------------------------------------------------------- #
# quantile_returns et quantile_spread
# --------------------------------------------------------------------------- #


def test_quantile_returns_hand_computed() -> None:
    """Source (a) : dix actifs, cinq quantiles, donc deux noms par paquet.

    Date 1, le signal ordonne comme les rendements 1 % à 10 % :
    Q1 = (0,01 + 0,02) / 2 = 0,015 ; Q2 = (0,03 + 0,04) / 2 = 0,035 ;
    Q3 = (0,05 + 0,06) / 2 = 0,055 ; Q4 = (0,07 + 0,08) / 2 = 0,075 ;
    Q5 = (0,09 + 0,10) / 2 = 0,095 ; écart = 0,095 - 0,015 = 0,08.

    Date 2, signal exactement inversé, donc les quantiles sont retournés :
    Q1 = 0,095, Q5 = 0,015, écart = -0,08.

    Date 3, signal croissant de A0 à A9, rendements
    0,05, -0,01, 0,02, 0,00, 0,04, -0,03, 0,06, 0,01, -0,02, 0,08 :
    Q1 = (0,05 - 0,01) / 2 = 0,02 ; Q2 = (0,02 + 0,00) / 2 = 0,01 ;
    Q3 = (0,04 - 0,03) / 2 = 0,005 ; Q4 = (0,06 + 0,01) / 2 = 0,035 ;
    Q5 = (-0,02 + 0,08) / 2 = 0,03 ; écart = 0,03 - 0,02 = 0,01.
    """
    predictions, realized = _hand_panels()
    table = quantile_returns(predictions, realized, n_quantiles=5)
    assert list(table.columns) == ["Q1", "Q2", "Q3", "Q4", "Q5", "spread"]
    expected_first = [0.015, 0.035, 0.055, 0.075, 0.095, 0.08]
    expected_second = [0.095, 0.075, 0.055, 0.035, 0.015, -0.08]
    expected_third = [0.02, 0.01, 0.005, 0.035, 0.03, 0.01]
    assert table.iloc[0].to_numpy() == pytest.approx(expected_first, abs=1e-15)
    assert table.iloc[1].to_numpy() == pytest.approx(expected_second, abs=1e-15)
    assert table.iloc[2].to_numpy() == pytest.approx(expected_third, abs=1e-15)


def test_quantile_returns_value_weighting_hand_computed() -> None:
    """Source (a) : pondération par la valeur dans le dernier quantile de la date 1.

    Le quantile Q5 porte A8 et A9, de valeurs 30 et 70, donc de poids 0,3 et 0,7.
    Rendement pondéré = 0,3 × 0,09 + 0,7 × 0,10 = 0,027 + 0,070 = 0,097.
    Les quantiles Q1 à Q4 ne portent que des valeurs égales à 10, donc restent
    identiques à la pondération égale.
    """
    predictions, realized = _hand_panels()
    weights = pd.DataFrame(
        [[10.0] * 8 + [30.0, 70.0]] * 3,
        index=DATES,
        columns=ASSETS,
    )
    table = quantile_returns(predictions, realized, weighting="value", value_panel=weights)
    assert table.loc[DATES[0], "Q5"] == pytest.approx(0.097, abs=1e-15)
    assert table.loc[DATES[0], "Q1"] == pytest.approx(0.015, abs=1e-15)
    assert table.loc[DATES[0], "spread"] == pytest.approx(0.082, abs=1e-15)


def test_quantile_returns_value_weighting_needs_its_panel() -> None:
    """La pondération par valeur sans tableau de valeurs est une configuration incomplète."""
    predictions, realized = _hand_panels()
    with pytest.raises(ConfigError):
        quantile_returns(predictions, realized, weighting="value")


def test_quantile_returns_rejects_negative_values() -> None:
    """Un poids négatif n'est pas une capitalisation, la fonction refuse."""
    predictions, realized = _hand_panels()
    weights = pd.DataFrame(-1.0, index=DATES, columns=ASSETS)
    with pytest.raises(DataQualityError):
        quantile_returns(predictions, realized, weighting="value", value_panel=weights)


def test_quantile_returns_marks_thin_dates_with_nan() -> None:
    """Cas limite : moins d'actifs que de quantiles, la ligne entière porte ``nan``."""
    predictions, realized = _hand_panels()
    thin = realized.copy()
    thin.iloc[1, 3:] = np.nan  # il ne reste que trois actifs à la date 2
    table = quantile_returns(predictions, thin, n_quantiles=5)
    assert table.iloc[1].isna().all()
    assert table.iloc[0, 0] == pytest.approx(0.015, abs=1e-15)


def test_quantile_returns_rejects_a_single_quantile() -> None:
    """Un seul quantile ne définit aucun écart."""
    predictions, realized = _hand_panels()
    with pytest.raises(ConfigError):
        quantile_returns(predictions, realized, n_quantiles=1)


def test_quantile_spread_hand_computed() -> None:
    """Source (a) : moyenne des trois écarts 0,08, -0,08 et 0,01.

    Moyenne = (0,08 - 0,08 + 0,01) / 3 = 0,01 / 3 = 0,003333333.
    Annualisation mensuelle = 0,003333333 × 12 = 0,04.
    Écart type d'échantillon : écarts à la moyenne 0,0766667, -0,0833333, 0,0066667 ;
    somme des carrés = 0,00587778 + 0,00694444 + 0,00004444 = 0,01286667 ;
    divisée par 2 puis racine = 0,0802081.
    Deux écarts sur trois sont positifs, donc 0,6666667.
    """
    predictions, realized = _hand_panels()
    table = quantile_returns(predictions, realized, n_quantiles=5)
    result = quantile_spread(table)
    assert result.n_periods == 3
    assert result.low == "Q1"
    assert result.high == "Q5"
    assert result.mean == pytest.approx(1.0 / 300.0, abs=1e-15)
    assert result.mean_annualized == pytest.approx(0.04, abs=1e-15)
    assert result.std == pytest.approx(0.0802080627701064, abs=1e-12)
    assert result.hit_rate == pytest.approx(2.0 / 3.0, abs=1e-15)


def test_quantile_spread_t_matches_statsmodels_hac() -> None:
    """Source (d) : ``statsmodels`` en HAC sans correction sur la même série d'écarts."""
    rng = np.random.default_rng(np.random.SeedSequence(11))
    dates = pd.date_range("2015-01-31", periods=90, freq="ME")
    assets = [f"A{i}" for i in range(20)]
    signal = pd.DataFrame(rng.normal(size=(90, 20)), index=dates, columns=assets)
    outcome = 0.01 * signal + 0.02 * rng.normal(size=(90, 20))
    table = quantile_returns(signal, outcome, n_quantiles=5)
    spread = table["spread"].to_numpy(dtype=float)
    lags = _newey_west_lags(spread.size)
    fitted = sm.OLS(spread, np.ones(spread.size)).fit(
        cov_type="HAC", cov_kwds={"maxlags": lags, "use_correction": False}
    )
    result = quantile_spread(table)
    assert result.hac_lags == lags
    assert result.t_stat_hac == pytest.approx(float(fitted.tvalues[0]), rel=1e-10)


def test_quantile_spread_rejects_an_unknown_column() -> None:
    """Une colonne demandée mais absente est une erreur de configuration, pas un ``nan``."""
    predictions, realized = _hand_panels()
    table = quantile_returns(predictions, realized, n_quantiles=5)
    with pytest.raises(ConfigError):
        quantile_spread(table, high="Q9")


# --------------------------------------------------------------------------- #
# La loi fondamentale
# --------------------------------------------------------------------------- #


def test_fundamental_law_hand_computed() -> None:
    """Source (a) : coefficient 0,05 et cent paris donnent 0,05 × racine(100) = 0,05 × 10 = 0,50."""
    assert fundamental_law(0.05, 100) == pytest.approx(0.50, abs=1e-15)


def test_fundamental_law_transfer_coefficient_scales_linearly() -> None:
    """Source (a) : un coefficient de transfert de 0,5 fait 0,5 × 0,05 × 10 = 0,25."""
    assert fundamental_law(0.05, 100, transfer_coefficient=0.5) == pytest.approx(0.25, abs=1e-15)


def test_fundamental_law_doubling_breadth_multiplies_by_root_two() -> None:
    """Source (b) : la racine de la largeur double le résultat par racine(2)."""
    assert fundamental_law(0.03, 400) == pytest.approx(fundamental_law(0.03, 200) * math.sqrt(2.0), rel=1e-12)


def test_fundamental_law_zero_skill_gives_zero() -> None:
    """Source (b) : sans compétence, aucun nombre de paris ne produit de ratio."""
    assert fundamental_law(0.0, 10_000) == pytest.approx(0.0, abs=1e-15)


@pytest.mark.parametrize(
    ("ic", "breadth", "transfer"),
    [(1.5, 100, 1.0), (0.05, 0.0, 1.0), (0.05, -10.0, 1.0), (0.05, 100, 1.4), (0.05, 100, -0.1)],
)
def test_fundamental_law_rejects_arguments_out_of_domain(ic: float, breadth: float, transfer: float) -> None:
    """Chaque argument a un domaine, et la fonction refuse d'en sortir en silence."""
    with pytest.raises(ConfigError):
        fundamental_law(ic, breadth, transfer_coefficient=transfer)


def test_effective_breadth_of_independent_bets_equals_their_count() -> None:
    """Source (b) : sur l'identité, chaque part vaut 1/N, la somme des carrés 1/N, donc N."""
    for size in (2, 7, 50):
        assert effective_breadth(np.eye(size)) == pytest.approx(float(size), rel=1e-12)
        assert effective_breadth(np.eye(size), method="entropy") == pytest.approx(float(size), rel=1e-12)


def test_effective_breadth_matches_the_equicorrelated_closed_form() -> None:
    """Source (b) : forme fermée du spectre d'une matrice à corrélation uniforme.

    Les valeurs propres sont 1 + (N - 1) rho une fois et 1 - rho répétée N - 1 fois,
    de somme N. Le taux de participation vaut donc
    N carré / ((1 + (N - 1) rho) carré + (N - 1)(1 - rho) carré).
    Pour N = 500 et rho = 0,3 : 250 000 / (150,7 carré + 499 × 0,49)
    = 250 000 / (22 710,49 + 244,51) = 250 000 / 22 955 = 10,890873.
    """
    size, rho = 500, 0.3
    matrix = np.full((size, size), rho)
    np.fill_diagonal(matrix, 1.0)
    top = (1.0 + (size - 1) * rho) ** 2
    rest = (size - 1) * (1.0 - rho) ** 2
    expected = size**2 / (top + rest)
    assert expected == pytest.approx(10.890873448050534, rel=1e-12)
    assert effective_breadth(matrix) == pytest.approx(expected, rel=1e-10)


def test_effective_breadth_entropy_lies_between_one_and_n() -> None:
    """Source (b) : bornes de l'entropie de Shannon appliquées aux parts de variance."""
    size, rho = 20, 0.6
    matrix = np.full((size, size), rho)
    np.fill_diagonal(matrix, 1.0)
    entropy = effective_breadth(matrix, method="entropy")
    participation = effective_breadth(matrix)
    assert 1.0 <= participation <= size
    assert participation <= entropy <= size


def test_effective_breadth_accepts_a_dataframe() -> None:
    """Une matrice de corrélation arrive souvent en pandas, la fonction l'accepte."""
    frame = pd.DataFrame(np.eye(4), index=list("abcd"), columns=list("abcd"))
    assert effective_breadth(frame) == pytest.approx(4.0, rel=1e-12)


@pytest.mark.parametrize(
    "matrix",
    [
        np.array([[1.0, 0.2, 0.0]]),
        np.array([[1.0, 0.2], [0.9, 1.0]]),
        np.array([[2.0, 0.2], [0.2, 2.0]]),
    ],
    ids=["non carrée", "non symétrique", "diagonale non unitaire"],
)
def test_effective_breadth_rejects_a_matrix_that_is_not_a_correlation(matrix: np.ndarray) -> None:
    """Une matrice qui n'est pas une corrélation donnerait un nombre de paris faux."""
    with pytest.raises(ConfigError):
        effective_breadth(matrix)


def test_effective_breadth_rejects_a_non_positive_semidefinite_matrix() -> None:
    """Source (b) : une corrélation de 1,5 est impossible, la valeur propre 1 - 1,5 le prouve."""
    matrix = np.array([[1.0, 1.5], [1.5, 1.0]])
    with pytest.raises(DataQualityError):
        effective_breadth(matrix)


def test_equicorrelated_breadth_hand_computed() -> None:
    """Source (a) : 500 / (1 + 499 × 0,3) = 500 / 150,7 = 3,3178500.

    À corrélation nulle, la formule rend exactement le nombre de paris.
    """
    assert equicorrelated_breadth(500, 0.3) == pytest.approx(500.0 / 150.7, rel=1e-12)
    assert equicorrelated_breadth(500, 0.3) == pytest.approx(3.3178500331785, rel=1e-12)
    assert equicorrelated_breadth(500, 0.0) == pytest.approx(500.0, rel=1e-15)
    assert equicorrelated_breadth(1, 0.9) == pytest.approx(1.0, rel=1e-15)


def test_equicorrelated_breadth_rejects_an_impossible_correlation() -> None:
    """La corrélation moyenne d'un ensemble de N variables ne descend pas sous -1/(N-1)."""
    with pytest.raises(ConfigError):
        equicorrelated_breadth(5, -0.5)
    with pytest.raises(ConfigError):
        equicorrelated_breadth(5, 1.0)


def test_correlated_bets_are_worth_far_less_than_independent_ones() -> None:
    """Source (a) : l'exemple chiffré des cinq cents paris corrélés à 0,3.

    Indépendants : 0,05 × racine(500) = 0,05 × 22,360680 = 1,118034.
    Effectifs au taux de participation : 10,890873 paris, donc
    0,05 × racine(10,890873) = 0,05 × 3,300132 = 0,165007.
    Le rapport des deux vaut 1,118034 / 0,165007 = 6,7757.
    La forme fermée sous corrélation uniforme est plus sévère : 3,3178500 paris,
    donc 0,05 × 1,8214966 = 0,0910748.
    """
    size, rho, ic = 500, 0.3, 0.05
    matrix = np.full((size, size), rho)
    np.fill_diagonal(matrix, 1.0)
    naive = fundamental_law(ic, size)
    effective = fundamental_law(ic, effective_breadth(matrix))
    severe = fundamental_law(ic, equicorrelated_breadth(size, rho))
    assert naive == pytest.approx(1.1180339887498949, rel=1e-12)
    assert effective == pytest.approx(0.1650066168980091, rel=1e-10)
    assert severe == pytest.approx(0.0910748323245574, rel=1e-12)
    assert naive / effective == pytest.approx(6.7757, rel=1e-4)


# --------------------------------------------------------------------------- #
# Les trous trouvés par réintroduction de bogue le 2026-09-01
#
# Les quatre tests qui suivent ferment des trous mesurés : la suite d'origine
# passait à 56 sur 56 avec, respectivement, le rang minimum au lieu du rang
# moyen dans le coefficient de Spearman, le rang moyen au lieu du rang d'ordre
# dans le tri par quantiles, la borne des retards supprimée, et la médiane
# remplacée par la moyenne. Chacun a été vérifié en réintroduisant le défaut.
# --------------------------------------------------------------------------- #


def test_spearman_tie_convention_is_the_average_rank() -> None:
    """Source (d) : scipy sur des ex aequo de tailles INÉGALES.

    Le test d'ex aequo précédent portait trois groupes de deux, cas où les rangs
    moyens et les rangs minimum diffèrent d'une constante. La corrélation de
    Pearson étant invariante par transformation affine, ce cas ne distingue pas
    les deux conventions. Ici le premier groupe compte trois noms et les trois
    autres un seul. La différence n'est donc plus affine : les rangs moyens
    valent 2, 2, 2, 4, 5, 6 et les rangs minimum 1, 1, 1, 4, 5, 6. Le rang moyen
    rend 0,9411239 et le rang minimum 0,9376145.
    """
    names = list("abcdef")
    predictions = pd.Series([1.0, 1.0, 1.0, 2.0, 3.0, 4.0], index=names)
    realized = pd.Series([0.01, 0.02, 0.03, 0.04, 0.05, 0.06], index=names)
    expected = sps.spearmanr(predictions.to_numpy(), realized.to_numpy()).statistic
    got = information_coefficient(predictions, realized)
    assert got == pytest.approx(expected, abs=1e-12)
    # Le rang minimum donnerait une autre valeur : la convention est donc testée.
    with_min_rank = np.corrcoef(
        predictions.rank(method="min").to_numpy(), realized.rank(method="average").to_numpy()
    )[0, 1]
    assert abs(got - with_min_rank) > 1e-4


def test_quantile_returns_break_ties_by_column_order() -> None:
    """Source (a) : ex aequo de signal, six actifs, trois quantiles.

    Le signal vaut 1, 1, 1, 2, 3, 4 sur A0 à A5, donc les trois premiers sont
    ex aequo. La convention déclarée départage par l'ordre des colonnes, ce que
    fait le rang d'ordre : rangs 1 à 6, donc des paquets de deux noms chacun.
    Q1 = (0,10 + 0,20) / 2 = 0,15 ; Q2 = (0,30 + 0,40) / 2 = 0,35 ;
    Q3 = (0,50 + 0,60) / 2 = 0,55 ; écart = 0,55 - 0,15 = 0,40.

    Le rang moyen donnerait 2, 2, 2, 4, 5, 6, donc des paquets de trois, un et
    deux noms, et un Q1 de (0,10 + 0,20 + 0,30) / 3 = 0,20. La convention est
    donc bien départagée par ce test.
    """
    dates = pd.to_datetime(["2020-01-31"])
    assets = [f"A{i}" for i in range(6)]
    predictions = pd.DataFrame([[1.0, 1.0, 1.0, 2.0, 3.0, 4.0]], index=dates, columns=assets)
    realized = pd.DataFrame([[0.10, 0.20, 0.30, 0.40, 0.50, 0.60]], index=dates, columns=assets)
    table = quantile_returns(predictions, realized, n_quantiles=3)
    assert table.iloc[0].to_numpy() == pytest.approx([0.15, 0.35, 0.55, 0.40], abs=1e-15)


def test_hac_lags_are_capped_at_the_sample_length() -> None:
    """Source (b) : un retard d'ordre T ou plus n'a aucune paire à corréler.

    Sur quatre dates, un retard demandé de 50 se ramène à trois. Au-delà, les
    autocovariances portent sur un ensemble vide et n'ajoutent rien, mais le
    nombre de retards ANNONCÉ serait faux, ce qui ferait publier une correction
    calculée sur des paires inexistantes.
    """
    values = pd.Series([0.04, -0.01, 0.02, 0.06])
    summary = ic_summary(values, hac_lags=50)
    assert summary.hac_lags == 3
    # Source (b) : au-delà de T - 1, la variance ne bouge plus, donc le t non plus.
    assert summary.t_stat_hac == pytest.approx(ic_summary(values, hac_lags=3).t_stat_hac, rel=1e-12)


def test_ic_summary_median_differs_from_the_mean_on_a_skewed_series() -> None:
    """Source (a) : série 0,00 / 0,01 / 0,02 / 0,03 / 0,40.

    Médiane = la troisième valeur triée = 0,02.
    Moyenne = 0,46 / 5 = 0,092. Les deux diffèrent, donc la médiane est testée.
    """
    summary = ic_summary(pd.Series([0.00, 0.01, 0.02, 0.03, 0.40]))
    assert summary.median == pytest.approx(0.02, abs=1e-15)
    assert summary.mean == pytest.approx(0.092, abs=1e-15)


# --------------------------------------------------------------------------- #
# Conventions corrigées le 2026-09-01
# --------------------------------------------------------------------------- #


def test_rolling_ic_gives_no_ratio_on_a_constant_window() -> None:
    """Source (b) : un écart type nul ne définit aucun rapport, donc ``nan``.

    La division brute rendrait :math:`+\\infty`, chiffre qui n'a pas de sens et
    qui se propagerait dans un tableau publié. La convention est celle de
    :func:`ic_summary`, qui rend déjà ``nan`` sur une série constante.
    """
    table = rolling_ic(pd.Series([0.05, 0.05, 0.05, 0.05]), window=3)
    assert table["std"].iloc[2] == pytest.approx(0.0, abs=1e-15)
    assert math.isnan(table["ir_annualized"].iloc[2])
    assert math.isnan(table["ir_annualized"].iloc[3])
    assert not np.isinf(table["ir_annualized"].to_numpy()).any()


def test_quantile_returns_rejects_duplicate_dates_and_assets() -> None:
    """Un identifiant en double fausserait le tri en silence, la fonction refuse.

    Sans cette garde, un actif présent deux fois entre deux fois dans les rangs
    et pèse double dans son quantile, sans que rien ne le signale.
    """
    predictions, realized = _hand_panels()
    doubled_assets = pd.concat([predictions, predictions.iloc[:, :1]], axis="columns", sort=False)
    with pytest.raises(DataQualityError):
        quantile_returns(doubled_assets, realized, n_quantiles=5)
    doubled_dates = pd.concat([predictions, predictions.iloc[:1]], axis="index", sort=False)
    with pytest.raises(DataQualityError):
        quantile_returns(doubled_dates, realized, n_quantiles=5)


def test_quantile_returns_rejects_a_floor_below_the_quantile_count() -> None:
    """Un plancher sous le nombre de quantiles laisserait un paquet vide.

    L'argument était auparavant relevé en silence à ``n_quantiles``, ce qui
    changeait le sens d'un argument explicite sans le dire.
    """
    predictions, realized = _hand_panels()
    with pytest.raises(ConfigError):
        quantile_returns(predictions, realized, n_quantiles=5, min_names=3)


def test_ic_series_rejects_duplicate_dates_and_assets() -> None:
    """La garde de ``ic_series`` sur les doublons n'était couverte par aucun test.

    Vérifié par réintroduction le 2026-09-01 : la garde entière pouvait être
    supprimée sans qu'un seul des 63 tests échoue. Une date en double compterait
    deux fois dans la série, un actif en double pèserait double dans la
    corrélation transversale.

    Le message est vérifié, et pas seulement le type. Sans la garde du tableau,
    la coupe transversale finit quand même par lever ``DataQualityError``, mais
    en annonçant un identifiant d'ACTIF en double là où le défaut porte sur une
    DATE. Un diagnostic faux coûte plus cher qu'une absence de diagnostic.
    """
    predictions, realized = _hand_panels()
    doubled_dates = pd.concat([predictions, predictions.iloc[:1]], axis="index", sort=False)
    with pytest.raises(DataQualityError, match="dates en double"):
        ic_series(doubled_dates, realized)
    doubled_assets = pd.concat([predictions, predictions.iloc[:, :1]], axis="columns", sort=False)
    with pytest.raises(DataQualityError, match="actifs en double"):
        ic_series(doubled_assets, realized)

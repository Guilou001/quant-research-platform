"""Contrôles du module ``quantlab.analytics.ratios``.

Règle du laboratoire appliquée ici sans exception : aucune valeur attendue ne
vient de la sortie du code. Chaque test dit d'où sort la sienne, parmi quatre
sources.

- (a) un calcul à la main écrit dans le commentaire, chiffres visibles.
- (b) une forme fermée ou une identité mathématique.
- (c) une valeur publiée, citée.
- (d) une implémentation indépendante, ``scipy`` ou ``numpy``, sur le même intrant.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from scipy import stats

from quantlab.analytics.ratios import (
    adjusted_sharpe_ratio,
    calmar_ratio,
    information_ratio,
    lo_autocorrelation_factor,
    omega_ratio,
    sharpe_confidence_interval,
    sharpe_ratio,
    sharpe_standard_error,
    sharpe_tstat,
    sortino_ratio,
)
from quantlab.core.determinism import make_generator
from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.types import Frequency

MONTHLY = Frequency.MONTHLY

#: Quatre rendements mensuels servant à presque tous les calculs à la main.
#: Moyenne 1,5 %, écarts -0,5, +1,5, -3,5 et +2,5 points de pourcentage.
FOUR_RETURNS = pd.Series([0.01, 0.03, -0.02, 0.04])

#: Quatre rendements dont les écarts à la moyenne sont symétriques : la moyenne
#: vaut 1 % et les écarts valent +2, -2, +1 et -1 point de pourcentage.
SYMMETRIC_RETURNS = pd.Series([0.03, -0.01, 0.02, 0.00])


# ---------------------------------------------------------------------------
# Ratio de Sharpe : calcul à la main
# ---------------------------------------------------------------------------


def test_sharpe_periodic_matches_hand_computation() -> None:
    """Source (a). Calcul à la main sur les quatre rendements de 1, 3, -2 et 4 %.

    Moyenne : (0,01 + 0,03 - 0,02 + 0,04) / 4 = 0,06 / 4 = 0,015.
    Écarts : -0,005 ; +0,015 ; -0,035 ; +0,025.
    Carrés : 0,000025 ; 0,000225 ; 0,001225 ; 0,000625, somme 0,0021.
    Variance d'échantillon : 0,0021 / 3 = 0,0007.
    Écart type : racine de 0,0007 = 0,0264575131106459.
    Sharpe mensuel : 0,015 / 0,0264575131106459 = 0,566946709513841.
    """
    expected = 0.015 / math.sqrt(0.0007)
    assert expected == pytest.approx(0.566946709513841, rel=1e-12)
    measured = sharpe_ratio(FOUR_RETURNS, frequency=MONTHLY, annualize=False)
    assert measured == pytest.approx(expected, rel=1e-12)


def test_sharpe_annualized_matches_hand_computation() -> None:
    """Source (a). Le Sharpe mensuel multiplié par la racine de douze.

    0,566946709513841 fois 3,4641016151377544 vaut 1,9639610121239313.
    """
    expected = (0.015 * 12.0) / (math.sqrt(0.0007) * math.sqrt(12.0))
    assert expected == pytest.approx(1.9639610121239313, rel=1e-12)
    assert sharpe_ratio(FOUR_RETURNS, frequency=MONTHLY) == pytest.approx(expected, rel=1e-12)


def test_sharpe_annualization_is_square_root_of_n() -> None:
    """Source (b). Identité d'annualisation SR_ann = SR_p multiplié par racine de N."""
    periodic = sharpe_ratio(FOUR_RETURNS, frequency=MONTHLY, annualize=False)
    annual = sharpe_ratio(FOUR_RETURNS, frequency=MONTHLY)
    assert annual == pytest.approx(periodic * math.sqrt(12.0), rel=1e-12)


def test_sharpe_risk_free_is_subtracted_before_annualizing() -> None:
    """Source (a). Le taux annuel se ramène au mois AVANT la soustraction.

    Taux annuel de 2,4 %. Ramené au mois : 1,024 puissance un douzième moins un,
    soit 0,0019776... et non 0,002. Le numérateur annualisé vaut alors
    (0,015 - 0,0019776...) fois 12, et le dénominateur ne bouge pas, la
    soustraction d'une constante ne changeant aucun écart à la moyenne.

    La convention fautive, qui retranche 2,4 % au rendement DÉJÀ annualisé,
    donne 0,015 fois 12 moins 0,024 au numérateur. Les deux diffèrent, et le
    test le prouve plutôt que de l'affirmer.
    """
    monthly_rate = 1.024 ** (1.0 / 12.0) - 1.0
    denominator = math.sqrt(0.0007) * math.sqrt(12.0)
    expected = (0.015 - monthly_rate) * 12.0 / denominator
    measured = sharpe_ratio(FOUR_RETURNS, risk_free=0.024, frequency=MONTHLY)
    assert measured == pytest.approx(expected, rel=1e-12)

    wrong_convention = (0.015 * 12.0 - 0.024) / denominator
    assert measured != pytest.approx(wrong_convention, rel=1e-6)


def test_sharpe_accepts_a_periodic_risk_free_series() -> None:
    """Source (b). Un taux périodique constant en série égale le même taux scalaire."""
    constant = pd.Series([0.001] * 4)
    from_series = sharpe_ratio(FOUR_RETURNS, risk_free=constant, frequency=MONTHLY, risk_free_kind="periodic")
    from_scalar = sharpe_ratio(FOUR_RETURNS, risk_free=0.001, frequency=MONTHLY, risk_free_kind="periodic")
    assert from_series == pytest.approx(from_scalar, rel=1e-12)


def test_sharpe_geometric_numerator_matches_hand_computation() -> None:
    """Source (a). Numérateur composé sur les mêmes quatre rendements.

    Patrimoine : 1,01 fois 1,03 = 1,0403 ; fois 0,98 = 1,019494 ; fois 1,04
    = 1,06027376.
    Croissance annualisée : 1,06027376 puissance (12 / 4) moins un,
    soit 19,1939 %.
    Dénominateur inchangé : racine de 0,0007 fois racine de 12.
    """
    wealth = 1.01 * 1.03 * 0.98 * 1.04
    assert wealth == pytest.approx(1.06027376, rel=1e-12)
    expected = (wealth**3.0 - 1.0) / (math.sqrt(0.0007) * math.sqrt(12.0))
    measured = sharpe_ratio(FOUR_RETURNS, frequency=MONTHLY, method="geometric")
    assert measured == pytest.approx(expected, rel=1e-12)


def test_sharpe_geometric_exceeds_arithmetic_here_and_the_two_differ() -> None:
    """Source (b). Les deux numérateurs ne coïncident jamais hors volatilité nulle.

    Sur cette série, le numérateur composé annualisé vaut 19,19 % contre 18,00 %
    pour l'arithmétique. La règle usuelle « géométrique inférieur à
    arithmétique » porte sur la moyenne PAR PÉRIODE, et elle tient bien ici :
    1,47 % par mois en géométrique contre 1,50 % en arithmétique. Composer ce
    1,47 % sur douze mois donne pourtant plus que douze fois 1,50 %.
    """
    arithmetic = sharpe_ratio(FOUR_RETURNS, frequency=MONTHLY, method="arithmetic")
    geometric = sharpe_ratio(FOUR_RETURNS, frequency=MONTHLY, method="geometric")
    assert arithmetic != pytest.approx(geometric, rel=1e-6)
    # Les deux numérateurs annualisés, calculés à la main :
    # arithmétique 0,015 fois 12 = 0,18 ; géométrique 1,06027376 au cube moins un,
    # soit 0,191939028552.
    arithmetic_numerator = 0.015 * 12.0
    geometric_numerator = (1.01 * 1.03 * 0.98 * 1.04) ** 3.0 - 1.0
    assert arithmetic_numerator == pytest.approx(0.18, rel=1e-12)
    assert geometric_numerator == pytest.approx(0.191939028552, rel=1e-11)


def test_sharpe_is_scale_invariant_when_risk_free_is_zero() -> None:
    """Source (b). Multiplier tous les rendements par k > 0 laisse le Sharpe INCHANGÉ.

    Le résultat exact demandé par la spécification : le Sharpe n'est PAS
    multiplié par k, il est invariant. Moyenne et écart type sont tous deux
    homogènes de degré un, donc le facteur se simplifie dans le rapport. La
    propriété tombe dès que le taux sans risque est non nul, puisque lui ne se
    met pas à l'échelle, et le second bloc du test le montre.
    """
    base = sharpe_ratio(FOUR_RETURNS, frequency=MONTHLY)
    for scale in (0.5, 2.0, 137.0):
        scaled = sharpe_ratio(FOUR_RETURNS * scale, frequency=MONTHLY)
        assert scaled == pytest.approx(base, rel=1e-12)

    with_rate = sharpe_ratio(FOUR_RETURNS, risk_free=0.024, frequency=MONTHLY)
    with_rate_scaled = sharpe_ratio(FOUR_RETURNS * 2.0, risk_free=0.024, frequency=MONTHLY)
    assert with_rate != pytest.approx(with_rate_scaled, rel=1e-6)


def test_sharpe_geometric_is_not_scale_invariant() -> None:
    """Source (a). La composition est non linéaire, donc l'invariance disparaît.

    Numérateur à l'échelle 1 : 1,06027376 au cube moins un = 19,1939 %.
    Numérateur à l'échelle 2 : 1,02 fois 1,06 fois 0,96 fois 1,08, soit
    1,12098816, au cube moins un = 40,8650 %, alors que le dénominateur, lui,
    a exactement doublé. Le rapport change donc.
    """
    base = sharpe_ratio(FOUR_RETURNS, frequency=MONTHLY, method="geometric")
    doubled = sharpe_ratio(FOUR_RETURNS * 2.0, frequency=MONTHLY, method="geometric")
    assert base != pytest.approx(doubled, rel=1e-6)
    wealth_doubled = 1.02 * 1.06 * 0.96 * 1.08
    assert wealth_doubled == pytest.approx(1.12098816, rel=1e-12)
    assert wealth_doubled**3.0 - 1.0 == pytest.approx(0.408650, rel=1e-6)
    expected_doubled = (wealth_doubled**3.0 - 1.0) / (2.0 * math.sqrt(0.0007) * math.sqrt(12.0))
    assert doubled == pytest.approx(expected_doubled, rel=1e-12)


@settings(deadline=None, max_examples=200)
@given(
    values=st.lists(
        st.floats(min_value=-0.5, max_value=0.5, allow_nan=False, allow_infinity=False),
        min_size=5,
        max_size=80,
    ),
    scale=st.floats(min_value=0.05, max_value=50.0, allow_nan=False, allow_infinity=False),
)
def test_property_sharpe_scale_invariance(values: list[float], scale: float) -> None:
    """Propriété, source (b). Invariance d'échelle du Sharpe à taux sans risque nul."""
    series = pd.Series(values, dtype="float64")
    assume(float(series.std(ddof=1)) > 1e-3)
    base = sharpe_ratio(series, frequency=MONTHLY)
    scaled = sharpe_ratio(series * scale, frequency=MONTHLY)
    assert scaled == pytest.approx(base, rel=1e-9, abs=1e-9)


@settings(deadline=None, max_examples=100)
@given(
    values=st.lists(
        st.floats(min_value=-0.3, max_value=0.3, allow_nan=False, allow_infinity=False),
        min_size=5,
        max_size=60,
    )
)
def test_property_sharpe_sign_follows_mean(values: list[float]) -> None:
    """Propriété, source (b). Le signe du Sharpe est celui de la moyenne excédentaire."""
    series = pd.Series(values, dtype="float64")
    assume(float(series.std(ddof=1)) > 1e-3)
    assume(abs(float(series.mean())) > 1e-6)
    measured = sharpe_ratio(series, frequency=MONTHLY)
    assert math.copysign(1.0, measured) == math.copysign(1.0, float(series.mean()))


# ---------------------------------------------------------------------------
# Cas limites du Sharpe
# ---------------------------------------------------------------------------


def test_sharpe_constant_series_raises_instead_of_returning_infinity() -> None:
    """Source (b). Écart type nul : le ratio n'est pas défini, l'infini est refusé."""
    constant = pd.Series([0.01] * 10)
    with pytest.raises(InsufficientDataError):
        sharpe_ratio(constant, frequency=MONTHLY)


def test_sharpe_empty_series_raises() -> None:
    with pytest.raises(InsufficientDataError):
        sharpe_ratio(pd.Series([], dtype="float64"), frequency=MONTHLY)


def test_sharpe_single_observation_raises() -> None:
    with pytest.raises(InsufficientDataError):
        sharpe_ratio(pd.Series([0.01]), frequency=MONTHLY)


def test_sharpe_drops_missing_values_without_replacing_them() -> None:
    """Source (b). Retirer un trou donne le même résultat que ne jamais l'avoir eu."""
    with_gap = pd.Series([0.01, np.nan, 0.03, -0.02, 0.04])
    assert sharpe_ratio(with_gap, frequency=MONTHLY) == pytest.approx(
        sharpe_ratio(FOUR_RETURNS, frequency=MONTHLY), rel=1e-12
    )


def test_sharpe_series_of_only_missing_values_raises() -> None:
    with pytest.raises(InsufficientDataError):
        sharpe_ratio(pd.Series([np.nan, np.nan, np.nan]), frequency=MONTHLY)


def test_sharpe_infinite_value_raises_data_quality_error() -> None:
    with pytest.raises(DataQualityError):
        sharpe_ratio(pd.Series([0.01, np.inf, 0.02]), frequency=MONTHLY)


def test_sharpe_unknown_method_raises_config_error() -> None:
    with pytest.raises(ConfigError):
        sharpe_ratio(FOUR_RETURNS, frequency=MONTHLY, method="harmonique")  # type: ignore[arg-type]


def test_total_loss_is_handled_by_the_two_compounding_paths() -> None:
    """Source (a). Un rendement de -100 % réduit le patrimoine à zéro.

    Rendements +10 %, -100 %, +5 %. Le patrimoine vaut 1,1 puis 0 puis 0. La
    croissance composée est donc de -100 % exactement, et le pire repli de
    100 %, si bien que le ratio de Calmar vaut -1.
    """
    ruined = pd.Series([0.10, -1.00, 0.05])
    assert calmar_ratio(ruined, frequency=MONTHLY) == pytest.approx(-1.0, rel=1e-12)
    numerator = sharpe_ratio(ruined, frequency=MONTHLY, method="geometric", annualize=False)
    assert numerator < 0.0


def test_return_below_minus_one_raises_data_quality_error() -> None:
    """Source (b). Perdre plus que le capital n'est pas composable."""
    with pytest.raises(DataQualityError):
        calmar_ratio(pd.Series([0.10, -1.50, 0.05]), frequency=MONTHLY)


# ---------------------------------------------------------------------------
# Erreur type, intervalle et statistique de test
# ---------------------------------------------------------------------------


def test_iid_standard_error_matches_hand_computation() -> None:
    """Source (a). Formule i.i.d. sur les quatre rendements.

    Sharpe mensuel 0,566946709513841, son carré 0,321428571428571.
    1 + 0,321428571428571 / 2 = 1,160714285714286.
    Divisé par T = 4 : 0,290178571428571.
    Racine : 0,538682254607084.
    """
    expected = math.sqrt((1.0 + (0.015 / math.sqrt(0.0007)) ** 2 / 2.0) / 4.0)
    assert expected == pytest.approx(0.538682254607084, rel=1e-12)
    errors = sharpe_standard_error(FOUR_RETURNS, frequency=MONTHLY, annualize=False, lags=0)
    assert errors.iid == pytest.approx(expected, rel=1e-12)
    assert errors.n_observations == 4
    assert errors.lags == 0


def test_iid_standard_error_annualizes_by_square_root_of_n() -> None:
    """Source (b). Point estimé et erreur type se mettent à la même échelle."""
    periodic = sharpe_standard_error(FOUR_RETURNS, frequency=MONTHLY, annualize=False, lags=0)
    annual = sharpe_standard_error(FOUR_RETURNS, frequency=MONTHLY, annualize=True, lags=0)
    assert annual.iid == pytest.approx(periodic.iid * math.sqrt(12.0), rel=1e-12)
    assert annual.lo == pytest.approx(periodic.lo * math.sqrt(12.0), rel=1e-12)
    assert annual.sharpe == pytest.approx(periodic.sharpe * math.sqrt(12.0), rel=1e-12)


def test_lo_standard_error_at_zero_lag_matches_the_moment_identity() -> None:
    """Source (b) et (d). Identité de moments contrôlée avec ``scipy.stats``.

    Sans retard, la méthode delta de Lo (2002) se réduit à

        T fois la variance = 1 - SR fois S + (SR au carré) fois (K - 1) / 4,

    où S est l'asymétrie et K l'aplatissement NON centré, tous deux en moments
    d'échantillon non corrigés. Le ratio de Sharpe qui entre dans l'identité est
    celui de population, donc écart type à zéro degré de liberté retiré.

    Aucun terme du membre de droite ne passe par le module : les moments
    viennent de ``scipy`` et le ratio de ``numpy``.
    """
    generator = make_generator(20260901)
    sample = pd.Series(generator.standard_normal(500) * 0.02 + 0.004)

    skewness = float(stats.skew(sample.to_numpy(), bias=True))
    kurtosis = float(stats.kurtosis(sample.to_numpy(), fisher=False, bias=True))
    values = sample.to_numpy()
    population_sharpe = float(values.mean() / values.std(ddof=0))
    n_obs = len(sample)
    expected_variance = (
        1.0 - population_sharpe * skewness + population_sharpe**2 * (kurtosis - 1.0) / 4.0
    ) / n_obs

    errors = sharpe_standard_error(sample, frequency=MONTHLY, annualize=False, lags=0)
    assert errors.lo**2 == pytest.approx(expected_variance, rel=1e-12)


def test_lo_and_iid_standard_errors_agree_on_an_independent_normal_sample() -> None:
    """Source (b). Sans autocorrélation ni asymétrie, les deux formules coïncident.

    L'échantillon est normal et indépendant par construction, donc l'hypothèse
    i.i.d. est exacte et l'écart entre les deux erreurs types ne vient que du
    bruit d'estimation des moments. Tolérance de 10 %, déclarée, sur 5 000 tirages
    de graine fixe.
    """
    generator = make_generator(20260902)
    sample = pd.Series(generator.standard_normal(5000) * 0.02 + 0.004)
    errors = sharpe_standard_error(sample, frequency=MONTHLY, annualize=False)
    assert errors.lo == pytest.approx(errors.iid, rel=0.10)


def test_lo_standard_error_exceeds_iid_on_a_positively_autocorrelated_series() -> None:
    """Source (b). L'autocorrélation positive gonfle l'erreur type robuste.

    Une série autorégressive d'ordre un à coefficient 0,6 viole l'hypothèse
    i.i.d. La covariance de Newey et West compte alors des autocovariances
    positives, donc la variance estimée du ratio de Sharpe monte. Le sens de
    l'inégalité est la propriété testée, pas sa valeur.
    """
    generator = make_generator(20260903)
    innovations = generator.standard_normal(2000) * 0.02
    values = np.empty_like(innovations)
    values[0] = innovations[0]
    for t in range(1, len(innovations)):
        values[t] = 0.6 * values[t - 1] + innovations[t]
    series = pd.Series(values + 0.004)
    errors = sharpe_standard_error(series, frequency=MONTHLY, annualize=False, lags=10)
    assert errors.lo > errors.iid


def test_standard_error_rejects_impossible_lag_counts() -> None:
    with pytest.raises(ConfigError):
        sharpe_standard_error(FOUR_RETURNS, frequency=MONTHLY, lags=-1)
    with pytest.raises(ConfigError):
        sharpe_standard_error(FOUR_RETURNS, frequency=MONTHLY, lags=4)


def test_default_lag_count_follows_the_newey_west_rule() -> None:
    """Source (a) et (c). Règle de sélection automatique, arithmétique visible.

    La règle usuelle retient la partie entière de 4 fois (T / 100) puissance
    deux neuvièmes.

    - T = 100 : (100 / 100) puissance 2/9 vaut 1, donc 4 fois 1 = 4, soit 4 retards.
    - T = 500 : 5 puissance 2/9 vaut 1,4299691483, donc 5,7198765932, soit 5.
    - T = 1000 : 10 puissance 2/9 vaut 1,6681005372, donc 6,6724021488, soit 6.

    Ce contrôle manquait. Le coefficient 4 se remplaçait par 3 sans qu'aucun
    test du fichier ne bouge, MESURÉ, tous les autres passant ``lags`` en clair.
    """
    assert math.floor(4.0 * (500.0 / 100.0) ** (2.0 / 9.0)) == 5
    assert math.floor(4.0 * (1000.0 / 100.0) ** (2.0 / 9.0)) == 6

    generator = make_generator(20260905)
    for size, expected_lags in ((100, 4), (500, 5), (1000, 6)):
        sample = pd.Series(generator.standard_normal(size) * 0.02 + 0.004)
        errors = sharpe_standard_error(sample, frequency=MONTHLY)
        assert errors.n_observations == size
        assert errors.lags == expected_lags


def _newey_west_sharpe_standard_error(values: np.ndarray, lags: int) -> float:
    """Erreur type de Lo (2002) réécrite ici, sans rien emprunter au module.

    Boucles explicites sur les dates, poids de Bartlett 1 - j / (m + 1),
    gradient (1 / sigma ; -mu / (2 sigma au cube)) appliqué aux deux moments
    (r - mu) et (r - mu) au carré moins sigma au carré. C'est une seconde
    implémentation, source (d), et non une relecture de la première.
    """
    n = values.size
    mean = float(values.mean())
    deviations = values - mean
    variance = float((deviations**2).mean())
    moments = np.column_stack((deviations, deviations**2 - variance))
    covariance = np.zeros((2, 2))
    for t in range(n):
        covariance += np.outer(moments[t], moments[t])
    covariance /= n
    for lag in range(1, lags + 1):
        cross = np.zeros((2, 2))
        for t in range(lag, n):
            cross += np.outer(moments[t], moments[t - lag])
        cross /= n
        covariance += (1.0 - lag / (lags + 1.0)) * (cross + cross.T)
    gradient = np.array([1.0 / math.sqrt(variance), -mean / (2.0 * variance**1.5)])
    return math.sqrt(float(gradient @ covariance @ gradient) / n)


@pytest.mark.parametrize("lags", [0, 1, 3, 8])
def test_lo_standard_error_matches_an_independent_implementation(lags: int) -> None:
    """Source (d). Seconde implémentation en boucles, sur la même série.

    Le contrôle porte sur la FORME du noyau autant que sur le résultat. Un poids
    de Bartlett écrit 1 - j / m au lieu de 1 - j / (m + 1) passait les soixante
    autres tests du fichier, MESURÉ, aucun ne fixant la pondération.
    """
    generator = make_generator(20260906)
    innovations = generator.standard_normal(400) * 0.02
    values = np.empty_like(innovations)
    values[0] = innovations[0]
    for t in range(1, len(innovations)):
        values[t] = 0.5 * values[t - 1] + innovations[t]
    values = values + 0.004

    errors = sharpe_standard_error(pd.Series(values), frequency=MONTHLY, annualize=False, lags=lags)
    assert errors.lo == pytest.approx(_newey_west_sharpe_standard_error(values, lags), rel=1e-12)


def test_confidence_interval_is_centred_and_has_the_normal_width() -> None:
    """Source (d). Le quantile vient de ``scipy.stats.norm``, pas du module."""
    interval = sharpe_confidence_interval(
        FOUR_RETURNS, frequency=MONTHLY, method="iid", confidence=0.95, lags=0
    )
    errors = sharpe_standard_error(FOUR_RETURNS, frequency=MONTHLY, lags=0)
    quantile = float(stats.norm.ppf(0.975))
    assert quantile == pytest.approx(1.959963984540054, rel=1e-12)
    assert interval.sharpe == pytest.approx(errors.sharpe, rel=1e-12)
    assert interval.high - interval.low == pytest.approx(2.0 * quantile * errors.iid, rel=1e-12)
    assert interval.low < interval.sharpe < interval.high


def test_confidence_interval_rejects_a_level_outside_the_unit_interval() -> None:
    with pytest.raises(ConfigError):
        sharpe_confidence_interval(FOUR_RETURNS, frequency=MONTHLY, confidence=1.0)


def test_tstat_equals_sharpe_over_standard_error_and_ignores_annualization() -> None:
    """Source (b). Le rapport ne dépend pas de l'échelle, les deux termes la portent."""
    errors = sharpe_standard_error(FOUR_RETURNS, frequency=MONTHLY, annualize=False, lags=0)
    expected = errors.sharpe / errors.iid
    assert sharpe_tstat(FOUR_RETURNS, frequency=MONTHLY, method="iid", lags=0) == pytest.approx(
        expected, rel=1e-12
    )
    annual = sharpe_standard_error(FOUR_RETURNS, frequency=MONTHLY, annualize=True, lags=0)
    assert annual.sharpe / annual.iid == pytest.approx(expected, rel=1e-12)


def test_tstat_is_smaller_than_the_naive_mean_test() -> None:
    """Source (a). L'incertitude sur l'écart type abaisse la statistique.

    Le test classique de la moyenne vaut SR fois racine de T, soit
    0,566946709513841 fois 2 = 1,133893419027682. La version i.i.d. divise par
    racine de (1 + SR au carré / 2), soit racine de 1,160714285714286 =
    1,077364509214168, donc 1,052469623168435.
    """
    naive = (0.015 / math.sqrt(0.0007)) * math.sqrt(4.0)
    assert naive == pytest.approx(1.133893419027682, rel=1e-12)
    expected = naive / math.sqrt(1.0 + (0.015 / math.sqrt(0.0007)) ** 2 / 2.0)
    assert expected == pytest.approx(1.052469623168435, rel=1e-12)
    measured = sharpe_tstat(FOUR_RETURNS, frequency=MONTHLY, method="iid", lags=0)
    assert measured == pytest.approx(expected, rel=1e-12)
    assert measured < naive


# ---------------------------------------------------------------------------
# Facteur d'annualisation sous autocorrélation
# ---------------------------------------------------------------------------


def test_lo_factor_without_autocorrelation_is_the_square_root_of_q() -> None:
    """Source (b). À rho nul, la formule redonne racine de q."""
    assert lo_autocorrelation_factor(0.0, periods=12) == pytest.approx(math.sqrt(12.0), rel=1e-12)


def test_lo_factor_ar1_matches_hand_computation() -> None:
    """Source (a). Cas q = 12, rho = 0,3, processus autorégressif d'ordre un.

    Somme des (12 - k) fois 0,3 puissance k, pour k de 1 à 11 :

    - 11 fois 0,3 = 3,3
    - 10 fois 0,09 = 0,9
    - 9 fois 0,027 = 0,243
    - 8 fois 0,0081 = 0,0648
    - 7 fois 0,00243 = 0,01701
    - 6 fois 0,000729 = 0,004374
    - 5 fois 0,0002187 = 0,0010935
    - 4 fois 0,00006561 = 0,00026244
    - 3 fois 0,000019683 = 0,000059049
    - 2 fois 0,0000059049 = 0,0000118098
    - 1 fois 0,00000177147 = 0,00000177147

    Total : 4,53061257027.
    Variance agrégée : 12 + 2 fois 4,53061257027 = 21,06122514054.
    Racine : 4,589251049...
    eta = 12 / 4,589251049 = 2,614805746.
    Surestimation du Sharpe annualisé usuel : 3,464101615 / 2,614805746 - 1
    = 0,3248, soit 32,48 %.

    Le chiffre de 65 % souvent attribué à Lo (2002) pour une autocorrélation de
    0,3 ne sort pas de cette formule. Le second bloc du test l'encadre : la
    surestimation vaut 63,3018 % à rho = 0,50 et 65,1582 % à rho = 0,51, donc
    65 % tombe entre les deux. La docstring du module porte cette attribution
    comme NON VÉRIFIÉE.
    """
    hand_sum = sum((12 - k) * 0.3**k for k in range(1, 12))
    assert hand_sum == pytest.approx(4.53061257027, rel=1e-11)
    expected = 12.0 / math.sqrt(12.0 + 2.0 * hand_sum)
    assert expected == pytest.approx(2.614805746, rel=1e-9)
    assert lo_autocorrelation_factor(0.3, periods=12) == pytest.approx(expected, rel=1e-12)

    overstatement = math.sqrt(12.0) / lo_autocorrelation_factor(0.3, periods=12) - 1.0
    assert overstatement == pytest.approx(0.3248, abs=1e-4)

    at_050 = math.sqrt(12.0) / lo_autocorrelation_factor(0.50, periods=12) - 1.0
    at_051 = math.sqrt(12.0) / lo_autocorrelation_factor(0.51, periods=12) - 1.0
    assert at_050 == pytest.approx(0.633018, abs=1e-6)
    assert at_051 == pytest.approx(0.651582, abs=1e-6)
    assert at_050 < 0.65 < at_051


def test_lo_factor_accepts_an_explicit_autocorrelation_sequence() -> None:
    """Source (a). Cas q = 3, rho1 = 0,2, rho2 = 0,1.

    Variance agrégée : 3 + 2 fois (2 fois 0,2 + 1 fois 0,1) = 3 + 1,0 = 4,0.
    eta = 3 / 2 = 1,5.
    """
    assert lo_autocorrelation_factor([0.2, 0.1], periods=3) == pytest.approx(1.5, rel=1e-12)


def test_lo_factor_rejects_a_too_short_sequence() -> None:
    with pytest.raises(ConfigError):
        lo_autocorrelation_factor([0.2], periods=3)


# ---------------------------------------------------------------------------
# Sharpe ajusté de Pezier et White
# ---------------------------------------------------------------------------


def test_adjusted_sharpe_matches_hand_computation() -> None:
    """Source (a). Correction de Pezier et White sur la série symétrique.

    Rendements 3, -1, 2 et 0 %. Moyenne 1 %, écarts +2, -2, +1 et -1 point.
    Moment d'ordre deux : (0,0004 + 0,0004 + 0,0001 + 0,0001) / 4 = 0,00025.
    Moment d'ordre trois : nul, la série étant symétrique.
    Moment d'ordre quatre : (1,6e-7 + 1,6e-7 + 1e-8 + 1e-8) / 4 = 8,5e-8.
    Aplatissement : 8,5e-8 / 0,00025 au carré = 8,5e-8 / 6,25e-8 = 1,36.
    Excès d'aplatissement : 1,36 - 3 = -1,64.
    Écart type d'échantillon : racine de (0,001 / 3) = 0,0182574185835055.
    Sharpe mensuel : 0,01 / 0,0182574185835055 = 0,547722557505166.
    Son carré vaut exactement 0,3.
    Crochet : 1 + 0 - (-1,64 / 24) fois 0,3 = 1 + 0,0205 = 1,0205.
    Sharpe ajusté mensuel : 0,547722557505166 fois 1,0205 = 0,558950869934022.
    """
    expected = (0.01 / math.sqrt(0.001 / 3.0)) * 1.0205
    assert expected == pytest.approx(0.558950869934022, rel=1e-12)
    measured = adjusted_sharpe_ratio(SYMMETRIC_RETURNS, frequency=MONTHLY, annualize=False)
    assert measured == pytest.approx(expected, rel=1e-12)


def test_adjusted_sharpe_annualizes_by_square_root_of_n() -> None:
    """Source (a). La correction vaut sur la période, puis racine de N.

    Le Sharpe ajusté mensuel calculé à la main plus haut vaut 0,558950869934022.
    Annualisé, il vaut 0,558950869934022 fois 3,4641016151377544, soit
    1,9362626113210988. La convention concurrente, qui multiplierait par douze,
    donnerait 6,707410439208266.

    Ce contrôle manquait. Une annualisation en N passait les soixante autres
    tests du fichier, MESURÉ, tous les tests du Sharpe ajusté demandant
    ``annualize=False``.
    """
    hand_periodic = (0.01 / math.sqrt(0.001 / 3.0)) * 1.0205
    assert hand_periodic == pytest.approx(0.558950869934022, rel=1e-12)
    annual = adjusted_sharpe_ratio(SYMMETRIC_RETURNS, frequency=MONTHLY)
    assert annual == pytest.approx(1.9362626113210988, rel=1e-12)
    assert annual == pytest.approx(hand_periodic * math.sqrt(12.0), rel=1e-12)
    assert annual != pytest.approx(hand_periodic * 12.0, rel=1e-6)


def test_adjusted_sharpe_moments_agree_with_scipy() -> None:
    """Source (d). Les moments du module contre ceux de ``scipy.stats``.

    Le module calcule l'asymétrie et l'aplatissement avec ``numpy`` ; le test
    reconstruit la formule de Pezier et White avec les moments de ``scipy``,
    implémentation indépendante, et les deux doivent coïncider. Le ratio de
    Sharpe périodique du membre de droite vient lui aussi de ``numpy`` seul.
    """
    generator = make_generator(20260904)
    sample = pd.Series(generator.standard_normal(400) * 0.03 + 0.005)
    values = sample.to_numpy()
    skewness = float(stats.skew(values, bias=True))
    excess_kurtosis = float(stats.kurtosis(values, fisher=True, bias=True))
    periodic_sharpe = float(values.mean() / values.std(ddof=1))
    expected = periodic_sharpe * (
        1.0 + (skewness / 6.0) * periodic_sharpe - (excess_kurtosis / 24.0) * periodic_sharpe**2
    )
    measured = adjusted_sharpe_ratio(sample, frequency=MONTHLY, annualize=False)
    assert measured == pytest.approx(expected, rel=1e-12)


def test_adjusted_sharpe_penalises_a_fat_left_tail() -> None:
    """Source (b). Asymétrie négative et queues épaisses abaissent le ratio.

    Onze gains de 1 % et une perte de 8 % : la moyenne reste positive, mais la
    série est fortement asymétrique à gauche. La correction doit donc rendre
    moins que le Sharpe brut, et le sens de l'inégalité est la propriété testée.
    """
    tail = pd.Series([0.01] * 11 + [-0.08])
    raw = sharpe_ratio(tail, frequency=MONTHLY, annualize=False)
    adjusted = adjusted_sharpe_ratio(tail, frequency=MONTHLY, annualize=False)
    assert adjusted < raw


def test_adjusted_sharpe_requires_four_observations() -> None:
    with pytest.raises(InsufficientDataError):
        adjusted_sharpe_ratio(pd.Series([0.01, 0.02, 0.03]), frequency=MONTHLY)


# ---------------------------------------------------------------------------
# Sortino
# ---------------------------------------------------------------------------


def test_sortino_matches_hand_computation() -> None:
    """Source (a). Semi-écart type de baisse sous une cible de 1 % par mois.

    Rendements 3, -1, 2 et 0 %. Écarts à la cible : +2, -2, +1 et -1 point.
    Seuls les écarts négatifs comptent : -0,02 et -0,01.
    Somme des carrés : 0,0004 + 0,0001 = 0,0005, divisée par T = 4 : 0,000125.
    Semi-écart type : racine de 0,000125 = 0,0111803398874989.
    Numérateur, taux sans risque nul : 0,01.
    Sortino mensuel : 0,01 / 0,0111803398874989 = 0,894427190999916.
    """
    expected = 0.01 / math.sqrt(0.000125)
    assert expected == pytest.approx(0.894427190999916, rel=1e-12)
    measured = sortino_ratio(
        SYMMETRIC_RETURNS,
        frequency=MONTHLY,
        annualize=False,
        target=0.01,
        target_kind="periodic",
    )
    assert measured == pytest.approx(expected, rel=1e-12)


def test_sortino_equals_sqrt_two_times_sharpe_on_a_symmetric_sample() -> None:
    """Source (b). L'identité vraie, et la fausse identité qu'elle remplace.

    On lit souvent « Sortino égale Sharpe quand la série est symétrique et que
    la cible vaut la moyenne ». C'est faux comme énoncé utile : si la cible EST
    la moyenne et que le taux sans risque vaut aussi la moyenne, les deux ratios
    valent zéro, et l'égalité est vide. Le premier bloc du test le montre.

    L'identité non triviale tient à ceci : pour une série symétrique autour de
    sa moyenne, la moitié de la variance de population vient des écarts
    négatifs. Le semi-écart type sous la moyenne vaut donc sigma divisé par
    racine de deux, et

        Sortino(cible = moyenne) = racine de deux fois Sharpe de population.

    Vérification à la main : semi-écart type 0,0111803398874989, écart type de
    population racine de 0,00025 = 0,0158113883008419, et leur rapport vaut
    exactement 0,7071067811865476.
    """
    trivial_sortino = sortino_ratio(
        SYMMETRIC_RETURNS,
        frequency=MONTHLY,
        annualize=False,
        risk_free=0.01,
        risk_free_kind="periodic",
        target=0.01,
        target_kind="periodic",
    )
    trivial_sharpe = sharpe_ratio(
        SYMMETRIC_RETURNS,
        frequency=MONTHLY,
        annualize=False,
        risk_free=0.01,
        risk_free_kind="periodic",
        ddof=0,
    )
    assert trivial_sortino == pytest.approx(0.0, abs=1e-15)
    assert trivial_sharpe == pytest.approx(0.0, abs=1e-15)

    assert math.sqrt(0.000125) / math.sqrt(0.00025) == pytest.approx(1.0 / math.sqrt(2.0), rel=1e-15)
    sortino = sortino_ratio(
        SYMMETRIC_RETURNS,
        frequency=MONTHLY,
        annualize=False,
        target=0.01,
        target_kind="periodic",
    )
    population_sharpe = sharpe_ratio(SYMMETRIC_RETURNS, frequency=MONTHLY, annualize=False, ddof=0)
    assert sortino == pytest.approx(math.sqrt(2.0) * population_sharpe, rel=1e-14)
    assert sortino != pytest.approx(population_sharpe, rel=1e-3)


def test_sortino_annualizes_like_the_sharpe_ratio() -> None:
    """Source (b). Numérateur en N, dénominateur en racine de N."""
    periodic = sortino_ratio(
        SYMMETRIC_RETURNS, frequency=MONTHLY, annualize=False, target=0.01, target_kind="periodic"
    )
    annual = sortino_ratio(SYMMETRIC_RETURNS, frequency=MONTHLY, target=0.01, target_kind="periodic")
    assert annual == pytest.approx(periodic * math.sqrt(12.0), rel=1e-12)


def test_sortino_without_any_downside_raises() -> None:
    """Source (b). Dénominateur nul : le ratio n'est pas défini."""
    only_gains = pd.Series([0.01, 0.02, 0.03, 0.04])
    with pytest.raises(InsufficientDataError):
        sortino_ratio(only_gains, frequency=MONTHLY, target=0.0, target_kind="periodic")


def test_sortino_denominator_divides_by_all_observations() -> None:
    """Source (a). La convention du dénominateur, prouvée par un contre-exemple.

    Une seule baisse de -2 % sous une cible nulle, dans une série de quatre.
    La convention du module divise par 4 : racine de (0,0004 / 4) = 0,01.
    La convention concurrente diviserait par 1, la seule baisse, et donnerait
    0,02, donc un ratio deux fois plus petit. Le test verrouille la première.

    Rendements 2, -2, 4 et 0 %, moyenne 1 %, donc Sortino = 0,01 / 0,01 = 1.
    """
    series = pd.Series([0.02, -0.02, 0.04, 0.00])
    measured = sortino_ratio(series, frequency=MONTHLY, annualize=False, target=0.0, target_kind="periodic")
    assert measured == pytest.approx(1.0, rel=1e-12)


# ---------------------------------------------------------------------------
# Calmar
# ---------------------------------------------------------------------------


def test_calmar_matches_separately_recomputed_cagr_over_max_drawdown() -> None:
    """Source (a). Croissance annualisée et pire repli recalculés séparément.

    Rendements mensuels +10, -20, +15 et +5 %.
    Patrimoine : 1,1 ; 0,88 ; 1,012 ; 1,0626.
    Sommets successifs : 1,0 ; 1,1 ; 1,1 ; 1,1 ; 1,1.
    Replis : 0 ; 0 ; (1,1 - 0,88) / 1,1 = 0,2 ; (1,1 - 1,012) / 1,1 = 0,08 ;
    (1,1 - 1,0626) / 1,1 = 0,034. Pire repli : 0,2.
    Croissance annualisée : 1,0626 puissance (12 / 4) moins un, soit
    1,0626 au cube moins un. 1,0626 au carré vaut 1,12911876, multiplié par
    1,0626 il vient 1,199801594376, donc une croissance de 0,199801594376.
    Calmar : 0,199801594376 / 0,2 = 0,99900797188.
    """
    series = pd.Series([0.10, -0.20, 0.15, 0.05])
    wealth = 1.10 * 0.80 * 1.15 * 1.05
    assert wealth == pytest.approx(1.0626, rel=1e-12)
    cagr = wealth**3.0 - 1.0
    assert cagr == pytest.approx(0.199801594376, rel=1e-12)
    max_drawdown = (1.10 - 0.88) / 1.10
    assert max_drawdown == pytest.approx(0.20, rel=1e-12)
    assert calmar_ratio(series, frequency=MONTHLY) == pytest.approx(cagr / max_drawdown, rel=1e-12)


def test_calmar_measures_the_drawdown_from_the_starting_capital() -> None:
    """Source (a). Le sommet initial vaut 1, donc une baisse d'entrée compte.

    Rendements -10 % puis +30 %. Patrimoine 0,9 puis 1,17. Le pire repli vaut
    (1 - 0,9) / 1 = 0,1, mesuré depuis le capital de départ et non depuis le
    premier sommet postérieur. Croissance annualisée sur deux mois : 1,17
    puissance six moins un.
    """
    series = pd.Series([-0.10, 0.30])
    wealth = 0.90 * 1.30
    assert wealth == pytest.approx(1.17, rel=1e-12)
    expected_cagr = 1.17**6.0 - 1.0
    assert calmar_ratio(series, frequency=MONTHLY) == pytest.approx(expected_cagr / 0.10, rel=1e-12)


def test_calmar_without_any_drawdown_raises() -> None:
    """Source (b). Sans repli, le ratio serait infini."""
    monotone = pd.Series([0.01, 0.02, 0.03])
    with pytest.raises(InsufficientDataError):
        calmar_ratio(monotone, frequency=MONTHLY)


# ---------------------------------------------------------------------------
# Ratio de l'information
# ---------------------------------------------------------------------------


def test_information_ratio_matches_hand_computation() -> None:
    """Source (a). Écart actif calculé à la main sur quatre observations.

    Portefeuille : 2, 1, 3 et 0 %. Repère : 1 % chaque mois.
    Écart actif : +1, 0, +2 et -1 point, soit 0,01 ; 0,00 ; 0,02 ; -0,01.
    Moyenne : 0,02 / 4 = 0,005.
    Écarts à la moyenne : +0,005 ; -0,005 ; +0,015 ; -0,015.
    Carrés : 0,000025 ; 0,000025 ; 0,000225 ; 0,000225, somme 0,0005.
    Variance d'échantillon : 0,0005 / 3 = 0,000166666...
    Écart type mensuel : 0,0129099444873581.
    Écart de suivi annualisé : 0,0129099444873581 fois racine de 12 = 0,04472136.
    Ratio : 0,005 fois 12 / 0,04472136 = 0,06 / 0,04472136 = 1,341640786.
    """
    portfolio = pd.Series([0.02, 0.01, 0.03, 0.00])
    benchmark = pd.Series([0.01, 0.01, 0.01, 0.01])
    tracking_error = math.sqrt(0.0005 / 3.0) * math.sqrt(12.0)
    assert tracking_error == pytest.approx(0.04472135954999579, rel=1e-12)
    expected = 0.005 * 12.0 / tracking_error
    assert expected == pytest.approx(1.341640786499874, rel=1e-12)
    measured = information_ratio(portfolio, benchmark, frequency=MONTHLY)
    assert measured == pytest.approx(expected, rel=1e-12)


def test_information_ratio_ignores_the_risk_free_rate() -> None:
    """Source (b). Le taux se simplifie dans la différence, donc rien ne bouge."""
    portfolio = pd.Series([0.02, 0.01, 0.03, 0.00])
    benchmark = pd.Series([0.01, 0.01, 0.01, 0.01])
    shifted = information_ratio(portfolio - 0.002, benchmark - 0.002, frequency=MONTHLY)
    assert shifted == pytest.approx(information_ratio(portfolio, benchmark, frequency=MONTHLY), rel=1e-12)


def test_information_ratio_aligns_on_common_dates() -> None:
    """Source (b). Une date sans repère ne peut produire aucun écart actif."""
    index = pd.date_range("2024-01-31", periods=5, freq="ME")
    portfolio = pd.Series([0.02, 0.01, 0.03, 0.00, 0.05], index=index)
    benchmark = pd.Series([0.01, 0.01, 0.01, 0.01], index=index[:4])
    aligned = information_ratio(portfolio, benchmark, frequency=MONTHLY)
    truncated = information_ratio(
        pd.Series(portfolio.to_numpy()[:4]), pd.Series([0.01] * 4), frequency=MONTHLY
    )
    assert aligned == pytest.approx(truncated, rel=1e-12)


def test_information_ratio_of_a_perfect_replication_raises() -> None:
    """Source (b). Écart de suivi nul : le ratio n'est pas défini."""
    portfolio = pd.Series([0.02, 0.01, 0.03, 0.00])
    with pytest.raises(InsufficientDataError):
        information_ratio(portfolio, portfolio, frequency=MONTHLY)


def test_information_ratio_rejects_mismatched_lengths_without_dates() -> None:
    with pytest.raises(DataQualityError):
        information_ratio([0.01, 0.02, 0.03], [0.01, 0.02], frequency=MONTHLY)


# ---------------------------------------------------------------------------
# Omega
# ---------------------------------------------------------------------------


def test_omega_matches_hand_computation() -> None:
    """Source (a). Seuil nul sur les rendements 3, -1, 2 et 0 %.

    Dépassements : 0,03 ; 0 ; 0,02 ; 0, somme 0,05.
    Manques : 0 ; 0,01 ; 0 ; 0, somme 0,01.
    Omega : 0,05 / 0,01 = 5.
    """
    measured = omega_ratio(SYMMETRIC_RETURNS, frequency=MONTHLY, threshold=0.0, threshold_kind="periodic")
    assert measured == pytest.approx(5.0, rel=1e-12)


def test_omega_equals_one_at_the_sample_mean() -> None:
    """Source (b). Identité exacte : la somme des écarts au seuil vaut T fois la moyenne moins le seuil."""
    mean = float(SYMMETRIC_RETURNS.mean())
    assert mean == pytest.approx(0.01, rel=1e-15)
    measured = omega_ratio(SYMMETRIC_RETURNS, frequency=MONTHLY, threshold=mean, threshold_kind="periodic")
    assert measured == pytest.approx(1.0, rel=1e-12)


def test_omega_satisfies_its_algebraic_decomposition() -> None:
    """Source (b). Omega vaut 1 plus l'excédent moyen divisé par la perte moyenne.

    L'identité vient de E[max(r - tau, 0)] - E[max(tau - r, 0)] = moyenne - tau.
    """
    threshold = 0.005
    values = SYMMETRIC_RETURNS.to_numpy()
    shortfall = float(np.mean(np.maximum(threshold - values, 0.0)))
    expected = 1.0 + (float(values.mean()) - threshold) / shortfall
    measured = omega_ratio(
        SYMMETRIC_RETURNS, frequency=MONTHLY, threshold=threshold, threshold_kind="periodic"
    )
    assert measured == pytest.approx(expected, rel=1e-12)


def test_omega_annual_threshold_is_compounded_not_divided() -> None:
    """Source (a). Le seuil annuel par défaut se ramène au mois par composition.

    Un seuil annuel de 12 % vaut 1,12 puissance un douzième moins un, soit
    0,009488792934583046 par mois. Sur les rendements 3, -1, 2 et 0 %, les
    dépassements valent 0,020511207065416954 et 0,010511207065416955, somme
    0,031022414130833908. Les manques valent 0,019488792934583046 et
    0,009488792934583046, somme 0,028977585869166093. Omega vaut donc
    1,0705658597959202.

    La convention fautive, la division du taux annuel par douze, place le seuil
    à 1 % exactement, c'est-à-dire à la moyenne de l'échantillon, où Omega vaut
    1 par identité. Les deux conventions sont donc séparables à l'œil nu ici.
    """
    monthly = 1.12 ** (1.0 / 12.0) - 1.0
    assert monthly == pytest.approx(0.009488792934583046, rel=1e-15)
    values = SYMMETRIC_RETURNS.to_numpy()
    gains = float(np.sum(np.maximum(values - monthly, 0.0)))
    losses = float(np.sum(np.maximum(monthly - values, 0.0)))
    assert gains == pytest.approx(0.031022414130833908, rel=1e-12)
    assert losses == pytest.approx(0.028977585869166093, rel=1e-12)

    measured = omega_ratio(SYMMETRIC_RETURNS, frequency=MONTHLY, threshold=0.12)
    assert measured == pytest.approx(gains / losses, rel=1e-12)
    assert measured == pytest.approx(1.0705658597959202, rel=1e-12)
    assert measured != pytest.approx(1.0, rel=1e-6)


def test_omega_without_any_shortfall_raises() -> None:
    with pytest.raises(InsufficientDataError):
        omega_ratio(
            pd.Series([0.01, 0.02, 0.03]),
            frequency=MONTHLY,
            threshold=0.0,
            threshold_kind="periodic",
        )


@settings(deadline=None, max_examples=150)
@given(
    values=st.lists(
        st.floats(min_value=-0.4, max_value=0.4, allow_nan=False, allow_infinity=False),
        min_size=4,
        max_size=60,
    )
)
def test_property_omega_decreases_with_the_threshold(values: list[float]) -> None:
    """Propriété, source (b). Monter le seuil ne peut pas augmenter Omega."""
    series = pd.Series(values, dtype="float64")
    low_threshold, high_threshold = -0.05, 0.05
    assume(float(series.min()) < low_threshold)
    assume(float(series.max()) > high_threshold)
    low = omega_ratio(series, frequency=MONTHLY, threshold=low_threshold, threshold_kind="periodic")
    high = omega_ratio(series, frequency=MONTHLY, threshold=high_threshold, threshold_kind="periodic")
    assert low >= high - 1e-12


@settings(deadline=None, max_examples=100)
@given(
    values=st.lists(
        st.floats(min_value=-0.4, max_value=0.4, allow_nan=False, allow_infinity=False),
        min_size=4,
        max_size=60,
    ),
    scale=st.floats(min_value=0.1, max_value=20.0, allow_nan=False, allow_infinity=False),
)
def test_property_omega_at_zero_is_scale_invariant(values: list[float], scale: float) -> None:
    """Propriété, source (b). Au seuil nul, numérateur et dénominateur portent le même facteur."""
    series = pd.Series(values, dtype="float64")
    assume(float(series.min()) < -1e-3)
    assume(float(series.max()) > 1e-3)
    base = omega_ratio(series, frequency=MONTHLY, threshold=0.0, threshold_kind="periodic")
    scaled = omega_ratio(series * scale, frequency=MONTHLY, threshold=0.0, threshold_kind="periodic")
    assert scaled == pytest.approx(base, rel=1e-9)


# ---------------------------------------------------------------------------
# Conventions transversales
# ---------------------------------------------------------------------------


def test_annual_rate_is_compounded_not_divided() -> None:
    """Source (a). Un taux annuel de 12 % vaut 0,9489 % par mois, pas 1 %.

    1,12 puissance un douzième moins un = 0,00948879293...
    Le test vérifie que le module emploie cette conversion et non la division.
    """
    monthly = 1.12 ** (1.0 / 12.0) - 1.0
    assert monthly == pytest.approx(0.00948879293, rel=1e-9)
    by_compounding = sharpe_ratio(FOUR_RETURNS, risk_free=0.12, frequency=MONTHLY)
    by_hand = sharpe_ratio(FOUR_RETURNS, risk_free=monthly, frequency=MONTHLY, risk_free_kind="periodic")
    assert by_compounding == pytest.approx(by_hand, rel=1e-12)
    by_division = sharpe_ratio(
        FOUR_RETURNS, risk_free=0.12 / 12.0, frequency=MONTHLY, risk_free_kind="periodic"
    )
    assert by_compounding != pytest.approx(by_division, rel=1e-6)


def test_measured_periods_per_year_overrides_the_convention() -> None:
    """Source (d). Le comptage mesuré vient de ``quantlab.core.calendars``.

    La convention quotidienne vaut 252. Le comptage réel des séances de la
    Bourse de New York sur 2010 à 2019 en donne un autre, et le Sharpe annualisé
    doit suivre la racine de ce nombre-là.
    """
    from quantlab.core.calendars import annualization_factor

    measured = annualization_factor(Frequency.DAILY, measured_over=("2010-01-01", "2019-12-31"))
    assert 250.0 < measured < 253.0
    periodic = sharpe_ratio(FOUR_RETURNS, frequency=Frequency.DAILY, annualize=False)
    annual = sharpe_ratio(FOUR_RETURNS, frequency=Frequency.DAILY, periods_per_year=measured)
    assert annual == pytest.approx(periodic * math.sqrt(measured), rel=1e-12)
    assert annual != pytest.approx(periodic * math.sqrt(252.0), rel=1e-6)


def test_bad_periods_per_year_raises_config_error() -> None:
    with pytest.raises(ConfigError):
        sharpe_ratio(FOUR_RETURNS, frequency=MONTHLY, periods_per_year=0.0)

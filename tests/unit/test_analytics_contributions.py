"""Tests de la décomposition du risque.

Chaque valeur attendue vient d'une source déclarée en commentaire, jamais de la
sortie du code : (a) calcul à la main, (b) identité mathématique, (c) valeur
publiée, (d) implémentation indépendante.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from quantlab.analytics.contributions import (
    FactorRiskDecomposition,
    check_covariance,
    diversification_ratio,
    effective_number_of_bets,
    factor_risk_contribution,
    group_risk_contribution,
    marginal_risk_contribution,
    portfolio_volatility,
    risk_contribution,
    risk_contribution_pct,
)
from quantlab.core.determinism import child_generators
from quantlab.core.errors import DataQualityError, InsufficientDataError

# Cas de référence à deux actifs, entièrement calculé à la main.
# Volatilités 0,20 et 0,10, corrélation 0,5, donc covariance 0,5 x 0,20 x 0,10 = 0,01.
NAMES = ["a", "b"]
COV_2 = pd.DataFrame([[0.04, 0.01], [0.01, 0.01]], index=NAMES, columns=NAMES)
W_2 = pd.Series([0.6, 0.4], index=NAMES)


def _frame(values: list[list[float]], names: list[str]) -> pd.DataFrame:
    return pd.DataFrame(values, index=names, columns=names)


# --------------------------------------------------------------------------
# Le cas à deux actifs, calculé à la main
# --------------------------------------------------------------------------


def test_portfolio_volatility_matches_hand_computation() -> None:
    # (a) Sigma w = (0,04 x 0,6 + 0,01 x 0,4 ; 0,01 x 0,6 + 0,01 x 0,4) = (0,028 ; 0,010).
    #     w' Sigma w = 0,6 x 0,028 + 0,4 x 0,010 = 0,0168 + 0,0040 = 0,0208.
    assert portfolio_volatility(W_2, COV_2) == pytest.approx(math.sqrt(0.0208), rel=1e-12)


def test_marginal_risk_contribution_matches_hand_computation() -> None:
    # (a) MR = (Sigma w) / sigma_p = (0,028 ; 0,010) / racine(0,0208).
    expected = np.array([0.028, 0.010]) / math.sqrt(0.0208)
    measured = marginal_risk_contribution(W_2, COV_2)
    assert measured.index.tolist() == NAMES
    assert measured.to_numpy() == pytest.approx(expected, rel=1e-12)


def test_risk_contribution_matches_hand_computation() -> None:
    # (a) RC = w x MR = (0,6 x 0,028 ; 0,4 x 0,010) / racine(0,0208)
    #        = (0,0168 ; 0,0040) / racine(0,0208).
    expected = np.array([0.0168, 0.0040]) / math.sqrt(0.0208)
    assert risk_contribution(W_2, COV_2).to_numpy() == pytest.approx(expected, rel=1e-12)


def test_risk_contribution_pct_matches_hand_computation() -> None:
    # (a) RC% = w_i (Sigma w)_i / (w' Sigma w) = 0,0168/0,0208 = 21/26 et 0,0040/0,0208 = 5/26,
    #     soit 0,807692307692 et 0,192307692308.
    expected = np.array([21.0 / 26.0, 5.0 / 26.0])
    measured = risk_contribution_pct(W_2, COV_2)
    assert measured.to_numpy() == pytest.approx(expected, rel=1e-12)
    # (b) La somme a 1 est le theoreme d'Euler, et non une normalisation : le
    #     denominateur est la variance w' Sigma w, pas la somme des parts.
    assert measured.sum() == pytest.approx(1.0, abs=1e-15)


def test_diversification_ratio_matches_hand_computation() -> None:
    # (a) w' sigma = 0,6 x 0,20 + 0,4 x 0,10 = 0,16 ; sigma_p = racine(0,0208).
    assert diversification_ratio(W_2, COV_2) == pytest.approx(0.16 / math.sqrt(0.0208), rel=1e-12)


def test_negative_contribution_on_a_hedging_line() -> None:
    # (a) Volatilités 0,20 et 0,10, corrélation -0,9, donc covariance -0,018.
    #     w = (1 ; 0,5). Sigma w = (0,04 - 0,009 ; -0,018 + 0,005) = (0,031 ; -0,013).
    #     w' Sigma w = 0,031 - 0,0065 = 0,0245.
    #     RC = (1 x 0,031 ; 0,5 x (-0,013)) / racine(0,0245) = (0,031 ; -0,0065) / racine(0,0245).
    cov = _frame([[0.04, -0.018], [-0.018, 0.01]], NAMES)
    weights = pd.Series([1.0, 0.5], index=NAMES)
    expected = np.array([0.031, -0.0065]) / math.sqrt(0.0245)
    measured = risk_contribution(weights, cov)
    assert measured.to_numpy() == pytest.approx(expected, rel=1e-12)
    assert measured.iloc[1] < 0.0
    # (b) L'identité d'Euler tient malgré la contribution négative.
    assert measured.sum() == pytest.approx(math.sqrt(0.0245), rel=1e-12)


# --------------------------------------------------------------------------
# La parité de risque à deux actifs non corrélés
# --------------------------------------------------------------------------


def test_inverse_volatility_weights_give_exactly_equal_contributions() -> None:
    # (a) Volatilités 0,20 et 0,05, corrélation nulle. Poids inversement
    #     proportionnels : 1/0,20 = 5 et 1/0,05 = 20, donc 5/25 = 0,2 et 20/25 = 0,8.
    #     Sigma w = (0,04 x 0,2 ; 0,0025 x 0,8) = (0,008 ; 0,002).
    #     RC = (0,2 x 0,008 ; 0,8 x 0,002) = (0,0016 ; 0,0016), donc parfaitement égales.
    cov = _frame([[0.04, 0.0], [0.0, 0.0025]], NAMES)
    weights = pd.Series([0.2, 0.8], index=NAMES)
    measured = risk_contribution(weights, cov)
    assert measured.iloc[0] == pytest.approx(measured.iloc[1], rel=1e-14)
    shares = risk_contribution_pct(weights, cov)
    assert shares.to_numpy() == pytest.approx(np.array([0.5, 0.5]), abs=1e-14)
    # (a) sigma_p = racine(0,0016 + 0,0016) = racine(0,0032).
    assert measured.sum() == pytest.approx(math.sqrt(0.0032), rel=1e-14)


# --------------------------------------------------------------------------
# L'identité d'Euler
# --------------------------------------------------------------------------


def test_euler_identity_holds_on_random_covariances() -> None:
    # (b) La volatilité est homogène de degré 1 en w, donc somme(RC) = sigma_p exactement.
    for index, rng in enumerate(child_generators(20260901, 8)):
        size = 3 + index
        factors = rng.normal(size=(size, size + 4))
        cov_values = factors @ factors.T / (size + 4)
        names = [f"actif_{position}" for position in range(size)]
        cov = pd.DataFrame(cov_values, index=names, columns=names)
        weights = pd.Series(rng.normal(size=size), index=names)
        volatility = portfolio_volatility(weights, cov)
        contributions = risk_contribution(weights, cov)
        assert contributions.sum() == pytest.approx(volatility, abs=1e-12)
        assert risk_contribution_pct(weights, cov).sum() == pytest.approx(1.0, abs=1e-12)


def test_portfolio_volatility_equals_independent_sample_standard_deviation() -> None:
    # (d) Implémentation indépendante : l'écart type empirique de la série des
    #     rendements du portefeuille, calculé par numpy, égale racine(w' S w)
    #     quand S est la covariance empirique du même échantillon.
    rng = child_generators(4242, 1)[0]
    returns = rng.normal(scale=0.01, size=(500, 4))
    names = [f"actif_{position}" for position in range(4)]
    cov = pd.DataFrame(np.cov(returns, rowvar=False, ddof=1), index=names, columns=names)
    weights = pd.Series(rng.normal(size=4), index=names)
    expected = float(np.std(returns @ weights.to_numpy(), ddof=1))
    assert portfolio_volatility(weights, cov) == pytest.approx(expected, rel=1e-12)


# --------------------------------------------------------------------------
# Ratio de diversification et nombre effectif de paris
# --------------------------------------------------------------------------


def test_diversification_ratio_is_one_under_perfect_correlation() -> None:
    # (b) Avec des corrélations toutes égales à 1, Sigma = sigma sigma',
    #     donc sigma_p = w' sigma et le rapport vaut exactement 1.
    cov = _frame([[0.04, 0.02], [0.02, 0.01]], NAMES)
    weights = pd.Series([0.7, 0.3], index=NAMES)
    assert diversification_ratio(weights, cov) == pytest.approx(1.0, rel=1e-12)


def test_effective_number_of_bets_matches_hand_computation() -> None:
    # (a) Covariance diagonale de variances 0,04 et 0,01, poids 0,5 et 0,5.
    #     Les composantes principales sont les actifs eux-mêmes.
    #     Variances portées : 0,25 x 0,04 = 0,0100 et 0,25 x 0,01 = 0,0025, total 0,0125.
    #     Parts : 0,0100/0,0125 = 0,8 et 0,0025/0,0125 = 0,2.
    #     N = exp(-(0,8 ln 0,8 + 0,2 ln 0,2)) = exp(0,50040242) = 1,6493849.
    cov = _frame([[0.04, 0.0], [0.0, 0.01]], NAMES)
    weights = pd.Series([0.5, 0.5], index=NAMES)
    expected = math.exp(-(0.8 * math.log(0.8) + 0.2 * math.log(0.2)))
    assert effective_number_of_bets(weights, cov) == pytest.approx(expected, rel=1e-12)
    assert expected == pytest.approx(1.6493849, abs=1e-7)


def test_effective_number_of_bets_with_unequal_weights() -> None:
    # (a) Même covariance diagonale, poids 0,75 et 0,25, donc des poids inégaux :
    #     ce cas sépare le carré de l'exposition de sa valeur absolue.
    #     Variances portées : 0,5625 x 0,04 = 0,022500 et 0,0625 x 0,01 = 0,000625.
    #     Total 0,023125. Parts : 22500/23125 = 36/37 et 625/23125 = 1/37.
    #     Entropie : -(36/37 x (-0,02739884) + 1/37 x (-3,61091791)) = 0,12425085.
    #     N = exp(0,12425085) = 1,132300 à un millionième près, calcul à la main
    #     par développement en série de l'exponentielle.
    cov = _frame([[0.04, 0.0], [0.0, 0.01]], NAMES)
    weights = pd.Series([0.75, 0.25], index=NAMES)
    expected = math.exp(-((36 / 37) * math.log(36 / 37) + (1 / 37) * math.log(1 / 37)))
    assert effective_number_of_bets(weights, cov) == pytest.approx(expected, rel=1e-12)
    assert expected == pytest.approx(1.132300, abs=1e-6)


def test_effective_number_of_bets_on_a_non_symmetric_eigenbasis() -> None:
    # (a) Les trois cas precedents utilisent des covariances diagonales ou de rang 1,
    #     dont la base propre rendue par numpy est symetrique. Elles ne separent donc
    #     pas E' w de E w. Mesure le 2026-09-01 : avec E w au lieu de E' w, les
    #     36 tests d'origine passaient tous. Ce cas ferme le trou.
    #     Base orthonormee rationnelle, colonnes (2,1,2)/3, (-2,2,1)/3, (1,2,-2)/3 :
    #     chaque colonne est de norme (4+1+4)/9 = 1 et les produits croises sont nuls.
    #     Elle n'est pas symetrique. Valeurs propres imposees 0,01, 0,02 et 0,04.
    #     Sigma = E Lambda E' vaut alors, multipliee par 9 :
    #         [[0,16 ; 0,02 ; -0,08], [0,02 ; 0,25 ; -0,10], [-0,08 ; -0,10 ; 0,22]].
    #     Avec w = (0,6 ; 0,3 ; 0,1), les expositions principales x = E' w valent
    #         (2 x 0,6 + 1 x 0,3 + 2 x 0,1)/3 = 1,7/3
    #         (-2 x 0,6 + 2 x 0,3 + 1 x 0,1)/3 = -0,5/3
    #         (1 x 0,6 + 2 x 0,3 - 2 x 0,1)/3 = 1,0/3
    #     Variances portees, multipliees par 9 : 2,89 x 0,01 = 0,0289 ; 0,25 x 0,02
    #     = 0,005 ; 1 x 0,04 = 0,04. Total 0,0739.
    #     Parts : 289/739, 50/739 et 400/739, de somme 739/739 = 1.
    #     N = exp(-somme p ln p) = exp(0,88166) = 2,4148533.
    basis = np.array([[2.0, -2.0, 1.0], [1.0, 2.0, 2.0], [2.0, 1.0, -2.0]]) / 3.0
    eigenvalues = np.array([0.01, 0.02, 0.04])
    names = ["a", "b", "c"]
    cov = pd.DataFrame(basis @ np.diag(eigenvalues) @ basis.T, index=names, columns=names)
    weights = pd.Series([0.6, 0.3, 0.1], index=names)
    shares = np.array([289.0, 50.0, 400.0]) / 739.0
    expected = math.exp(-float((shares * np.log(shares)).sum()))
    assert effective_number_of_bets(weights, cov) == pytest.approx(expected, rel=1e-12)
    assert expected == pytest.approx(2.4148533, abs=1e-7)


def test_effective_number_of_bets_is_one_under_perfect_correlation() -> None:
    # (b) Une covariance de rang 1 n'a qu'une valeur propre non nulle, donc une
    #     seule source de risque, donc une entropie nulle et N = exp(0) = 1.
    cov = _frame([[0.04, 0.02], [0.02, 0.01]], NAMES)
    weights = pd.Series([0.7, 0.3], index=NAMES)
    assert effective_number_of_bets(weights, cov) == pytest.approx(1.0, rel=1e-10)


def test_effective_number_of_bets_stays_between_one_and_the_asset_count() -> None:
    # (b) Borne de l'entropie : elle vaut au plus ln(n) sur n composantes.
    for index, rng in enumerate(child_generators(777, 6)):
        size = 2 + index
        factors = rng.normal(size=(size, size + 3))
        names = [f"actif_{position}" for position in range(size)]
        cov = pd.DataFrame(factors @ factors.T / (size + 3), index=names, columns=names)
        weights = pd.Series(rng.normal(size=size), index=names)
        measured = effective_number_of_bets(weights, cov)
        assert 1.0 - 1e-12 <= measured <= size + 1e-12


# --------------------------------------------------------------------------
# Décomposition factorielle
# --------------------------------------------------------------------------


def test_factor_decomposition_matches_hand_computation() -> None:
    # (a) Un facteur de variance 0,04, deux actifs d'exposition 1, variances
    #     spécifiques 0,01 chacune, poids 0,5 et 0,5.
    #     x = B' w = 1. Variance de facteur = 1 x 0,04 x 1 = 0,04.
    #     Variance spécifique = 0,25 x 0,01 + 0,25 x 0,01 = 0,005.
    #     Variance totale = 0,045, donc sigma_p = racine(0,045) = 0,21213203.
    #     Contribution du facteur = 0,04 / racine(0,045) = 0,18856181.
    #     Contribution spécifique de chaque actif = 0,0025 / racine(0,045) = 0,01178511.
    weights = pd.Series([0.5, 0.5], index=NAMES)
    exposures = pd.DataFrame([[1.0], [1.0]], index=NAMES, columns=["marche"])
    factor_cov = pd.DataFrame([[0.04]], index=["marche"], columns=["marche"])
    specific = pd.Series([0.01, 0.01], index=NAMES)

    result = factor_risk_contribution(weights, exposures, factor_cov, specific)
    assert isinstance(result, FactorRiskDecomposition)
    assert result.total_volatility == pytest.approx(math.sqrt(0.045), rel=1e-12)
    assert result.factor_volatility == pytest.approx(math.sqrt(0.04), rel=1e-12)
    assert result.specific_volatility == pytest.approx(math.sqrt(0.005), rel=1e-12)
    assert result.factor_contributions.iloc[0] == pytest.approx(0.04 / math.sqrt(0.045), rel=1e-12)
    assert result.specific_contributions.to_numpy() == pytest.approx(
        np.array([0.0025, 0.0025]) / math.sqrt(0.045), rel=1e-12
    )
    # (a) 0,04/0,045 = 8/9 et 0,005/0,045 = 1/9.
    assert result.factor_share == pytest.approx(8.0 / 9.0, rel=1e-12)
    assert result.specific_share == pytest.approx(1.0 / 9.0, rel=1e-12)


def test_factor_decomposition_sums_to_the_total_variance() -> None:
    # (b) Sigma = B F B' + D par construction, donc la somme des deux blocs
    #     égale w' Sigma w, et la somme de toutes les contributions égale sigma_p.
    for index, rng in enumerate(child_generators(31415, 5)):
        assets = 4 + index
        factors = 2 + index % 3
        asset_names = [f"actif_{position}" for position in range(assets)]
        factor_names = [f"facteur_{position}" for position in range(factors)]
        loadings = pd.DataFrame(rng.normal(size=(assets, factors)), index=asset_names, columns=factor_names)
        raw = rng.normal(size=(factors, factors + 2))
        factor_cov = pd.DataFrame(raw @ raw.T / (factors + 2), index=factor_names, columns=factor_names)
        specific = pd.Series(rng.uniform(0.001, 0.02, size=assets), index=asset_names)
        weights = pd.Series(rng.normal(size=assets), index=asset_names)

        result = factor_risk_contribution(weights, loadings, factor_cov, specific)
        assert abs(result.variance_residual) <= 1e-14 * result.total_volatility**2

        implied = loadings.to_numpy() @ factor_cov.to_numpy() @ loadings.to_numpy().T + np.diag(
            specific.to_numpy()
        )
        implied_cov = pd.DataFrame(implied, index=asset_names, columns=asset_names)
        # (b) La volatilité du modèle est celle de la covariance qu'il implique.
        assert result.total_volatility == pytest.approx(portfolio_volatility(weights, implied_cov), rel=1e-12)
        total = result.factor_contributions.sum() + result.specific_contributions.sum()
        assert total == pytest.approx(result.total_volatility, rel=1e-12)
        # (b) La part de facteur se recalcule par un autre chemin : x' F x rapporte
        #     a la variance de la covariance implicite. La somme des deux parts a 1
        #     serait vraie par construction et ne testerait rien.
        exposure = loadings.to_numpy().T @ weights.to_numpy()
        independent_share = float(exposure @ factor_cov.to_numpy() @ exposure) / float(
            weights.to_numpy() @ implied @ weights.to_numpy()
        )
        assert result.factor_share == pytest.approx(independent_share, rel=1e-12)
        assert result.specific_share == pytest.approx(1.0 - independent_share, rel=1e-12)


def test_factor_decomposition_rejects_negative_specific_variance() -> None:
    weights = pd.Series([0.5, 0.5], index=NAMES)
    exposures = pd.DataFrame([[1.0], [1.0]], index=NAMES, columns=["marche"])
    factor_cov = pd.DataFrame([[0.04]], index=["marche"], columns=["marche"])
    specific = pd.Series([0.01, -0.01], index=NAMES)
    with pytest.raises(DataQualityError, match="négative"):
        factor_risk_contribution(weights, exposures, factor_cov, specific)


def test_factor_decomposition_rejects_misaligned_labels() -> None:
    weights = pd.Series([0.5, 0.5], index=NAMES)
    exposures = pd.DataFrame([[1.0], [1.0]], index=["a", "c"], columns=["marche"])
    factor_cov = pd.DataFrame([[0.04]], index=["marche"], columns=["marche"])
    specific = pd.Series([0.01, 0.01], index=NAMES)
    with pytest.raises(DataQualityError, match="expositions"):
        factor_risk_contribution(weights, exposures, factor_cov, specific)


# --------------------------------------------------------------------------
# Agrégation par groupe
# --------------------------------------------------------------------------


def test_group_risk_contribution_sums_member_contributions() -> None:
    # (b) L'agrégation est une somme de contributions additives : la contribution
    #     d'un groupe est la somme de celles de ses membres, sans reste.
    names = ["a", "b", "c", "d"]
    rng = child_generators(2718, 1)[0]
    factors = rng.normal(size=(4, 8))
    cov = pd.DataFrame(factors @ factors.T / 8, index=names, columns=names)
    weights = pd.Series([0.4, 0.3, 0.2, 0.1], index=names)
    groups = {"a": "energie", "b": "financieres", "c": "energie", "d": "financieres"}

    detail = risk_contribution(weights, cov)
    table = group_risk_contribution(weights, cov, groups)

    assert table.index.tolist() == ["energie", "financieres"]
    assert table.loc["energie", "risk_contribution"] == pytest.approx(detail["a"] + detail["c"], rel=1e-14)
    assert table.loc["financieres", "risk_contribution"] == pytest.approx(
        detail["b"] + detail["d"], rel=1e-14
    )
    # (a) Poids agrégés : 0,4 + 0,2 = 0,6 et 0,3 + 0,1 = 0,4.
    assert table["weight"].tolist() == pytest.approx([0.6, 0.4], rel=1e-14)
    # (b) Euler à l'échelle des groupes.
    assert table["risk_contribution"].sum() == pytest.approx(portfolio_volatility(weights, cov), rel=1e-12)
    assert table["risk_contribution_pct"].sum() == pytest.approx(1.0, rel=1e-12)


def test_group_risk_contribution_accepts_a_series_mapping() -> None:
    groups = pd.Series(["un", "un"], index=NAMES)
    table = group_risk_contribution(W_2, COV_2, groups)
    assert table.index.tolist() == ["un"]
    # (b) Un seul groupe reçoit toute la volatilité.
    assert table.loc["un", "risk_contribution"] == pytest.approx(math.sqrt(0.0208), rel=1e-12)


def test_group_risk_contribution_rejects_an_asset_without_group() -> None:
    with pytest.raises(DataQualityError, match="sans groupe"):
        group_risk_contribution(W_2, COV_2, {"a": "un"})


# --------------------------------------------------------------------------
# Entrées invalides
# --------------------------------------------------------------------------


def test_asymmetric_covariance_is_rejected() -> None:
    cov = _frame([[0.04, 0.02], [0.01, 0.01]], NAMES)
    with pytest.raises(DataQualityError, match="symétrique"):
        portfolio_volatility(W_2, cov)


def test_non_positive_semidefinite_covariance_is_rejected() -> None:
    # (a) La matrice [[1, 2], [2, 1]] a pour valeurs propres 1 + 2 = 3 et 1 - 2 = -1,
    #     donc un portefeuille (1 ; -1) aurait une variance de -2.
    cov = _frame([[1.0, 2.0], [2.0, 1.0]], NAMES)
    with pytest.raises(DataQualityError, match="semi-définie positive"):
        check_covariance(cov)
    with pytest.raises(DataQualityError, match="semi-définie positive"):
        risk_contribution(W_2, cov)


def test_rank_deficient_covariance_is_accepted() -> None:
    # (b) Une covariance de rang 1 est semi-définie positive : ses valeurs propres
    #     sont 0 et 0,05, donc aucune n'est négative au-delà de l'arrondi.
    cov = _frame([[0.04, 0.02], [0.02, 0.01]], NAMES)
    check_covariance(cov)
    assert portfolio_volatility(W_2, cov) > 0.0


def test_empty_inputs_raise_insufficient_data() -> None:
    empty = pd.DataFrame(dtype=float)
    with pytest.raises(InsufficientDataError):
        portfolio_volatility(pd.Series(dtype=float), empty)


def test_single_asset_portfolio_is_degenerate_but_valid() -> None:
    # (a) Un seul actif de volatilité 0,20 et de poids 1 : sigma_p = 0,20,
    #     RC = 0,20, part = 1, ratio de diversification = 1, un seul pari.
    cov = pd.DataFrame([[0.04]], index=["a"], columns=["a"])
    weights = pd.Series([1.0], index=["a"])
    assert portfolio_volatility(weights, cov) == pytest.approx(0.2, rel=1e-14)
    assert risk_contribution(weights, cov).iloc[0] == pytest.approx(0.2, rel=1e-14)
    assert risk_contribution_pct(weights, cov).iloc[0] == pytest.approx(1.0, rel=1e-14)
    assert diversification_ratio(weights, cov) == pytest.approx(1.0, rel=1e-14)
    assert effective_number_of_bets(weights, cov) == pytest.approx(1.0, rel=1e-14)


def test_constant_series_of_weights_on_a_zero_covariance() -> None:
    # (b) Une covariance nulle donne une volatilité nulle, donc une dérivée
    #     indéfinie : la volatilité se calcule encore, la décomposition non.
    cov = _frame([[0.0, 0.0], [0.0, 0.0]], NAMES)
    assert portfolio_volatility(W_2, cov) == 0.0
    with pytest.raises(DataQualityError, match="volatilité"):
        risk_contribution(W_2, cov)


def test_nan_weight_is_rejected() -> None:
    weights = pd.Series([0.6, float("nan")], index=NAMES)
    with pytest.raises(DataQualityError, match="non finie"):
        portfolio_volatility(weights, COV_2)


def test_nan_covariance_is_rejected() -> None:
    cov = _frame([[0.04, float("nan")], [float("nan"), 0.01]], NAMES)
    with pytest.raises(DataQualityError, match="non finie"):
        portfolio_volatility(W_2, cov)


def test_misaligned_labels_are_rejected() -> None:
    weights = pd.Series([0.6, 0.4], index=["a", "z"])
    with pytest.raises(DataQualityError, match="mêmes actifs"):
        portfolio_volatility(weights, COV_2)


def test_duplicate_labels_are_rejected() -> None:
    cov = pd.DataFrame([[0.04, 0.01], [0.01, 0.01]], index=["a", "a"], columns=["a", "a"])
    with pytest.raises(DataQualityError, match="double"):
        check_covariance(cov)


def test_non_square_covariance_is_rejected() -> None:
    cov = pd.DataFrame([[0.04, 0.01]], index=["a"], columns=NAMES)
    with pytest.raises(DataQualityError, match="carrée"):
        check_covariance(cov)


def test_weights_are_realigned_on_the_covariance_order() -> None:
    # (b) La décomposition ne dépend pas de l'ordre des étiquettes : les poids
    #     sont réalignés sur l'index de la covariance avant tout calcul.
    reversed_weights = pd.Series([0.4, 0.6], index=["b", "a"])
    assert portfolio_volatility(reversed_weights, COV_2) == pytest.approx(math.sqrt(0.0208), rel=1e-12)


# --------------------------------------------------------------------------
# Propriétés (hypothesis)
# --------------------------------------------------------------------------

_ENTRIES = st.floats(min_value=-2.0, max_value=2.0, allow_nan=False, allow_infinity=False)
_WEIGHTS = st.floats(min_value=-3.0, max_value=3.0, allow_nan=False, allow_infinity=False)
_SIZE = 3


@st.composite
def _psd_case(draw: st.DrawFn) -> tuple[pd.DataFrame, pd.Series]:
    """Tire une covariance semi-définie positive et un vecteur de poids."""
    entries = draw(st.lists(_ENTRIES, min_size=_SIZE * _SIZE, max_size=_SIZE * _SIZE))
    raw = np.array(entries, dtype=float).reshape(_SIZE, _SIZE)
    # A A' est semi-définie positive par construction ; le terme diagonal
    # garantit qu'elle est en plus inversible, donc que sigma_p ne s'annule pas.
    values = raw @ raw.T + 0.05 * np.eye(_SIZE)
    names = [f"actif_{position}" for position in range(_SIZE)]
    weights = np.array(draw(st.lists(_WEIGHTS, min_size=_SIZE, max_size=_SIZE)), dtype=float)
    return pd.DataFrame(values, index=names, columns=names), pd.Series(weights, index=names)


@settings(deadline=None, max_examples=60)
@given(case=_psd_case())
def test_risk_contribution_pct_is_scale_invariant(case: tuple[pd.DataFrame, pd.Series]) -> None:
    # (b) RC% = w_i (Sigma w)_i / (w' Sigma w) est homogène de degré 0 en w
    #     et de degré 0 en Sigma : les deux facteurs se simplifient.
    cov, weights = case
    assume(portfolio_volatility(weights, cov) > 1e-6)
    reference = risk_contribution_pct(weights, cov)
    scaled_weights = risk_contribution_pct(weights * 3.0, cov)
    scaled_cov = risk_contribution_pct(weights, cov * 7.0)
    assert scaled_weights.to_numpy() == pytest.approx(reference.to_numpy(), abs=1e-10)
    assert scaled_cov.to_numpy() == pytest.approx(reference.to_numpy(), abs=1e-10)


@settings(deadline=None, max_examples=60)
@given(case=_psd_case())
def test_risk_contribution_is_homogeneous_of_degree_one(case: tuple[pd.DataFrame, pd.Series]) -> None:
    # (b) RC(c w) = c RC(w) pour c > 0, et somme(RC) = sigma_p à chaque échelle.
    cov, weights = case
    volatility = portfolio_volatility(weights, cov)
    assume(volatility > 1e-6)
    reference = risk_contribution(weights, cov)
    doubled = risk_contribution(weights * 2.0, cov)
    assert doubled.to_numpy() == pytest.approx(2.0 * reference.to_numpy(), rel=1e-10)
    assert reference.sum() == pytest.approx(volatility, rel=1e-12)


@settings(deadline=None, max_examples=60)
@given(case=_psd_case())
def test_diversification_ratio_is_at_least_one_when_long_only(
    case: tuple[pd.DataFrame, pd.Series],
) -> None:
    # (b) Sous-additivité de la norme : pour des poids positifs,
    #     racine(w' Sigma w) <= somme(w_i sigma_i), donc le ratio est au moins 1.
    cov, weights = case
    long_only = weights.abs()
    assume(long_only.sum() > 1e-6)
    assume(portfolio_volatility(long_only, cov) > 1e-6)
    assert diversification_ratio(long_only, cov) >= 1.0 - 1e-10

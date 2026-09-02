"""Tests des optimiseurs de portefeuille.

Chaque optimiseur est vérifié par la propriété qui le DÉFINIT, recalculée par un
chemin indépendant : forme fermée (a), calcul à la main (b), ou
``quantlab.analytics.contributions`` (d). Aucune valeur attendue ne vient de la
sortie du module.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from quantlab.analytics.contributions import risk_contribution
from quantlab.core.determinism import make_generator
from quantlab.core.errors import DataQualityError
from quantlab.portfolio.optimizers import (
    DEFAULT_SOLVER_TOLERANCE,
    EqualWeight,
    HierarchicalRiskParity,
    InverseVolatility,
    MaximumDiversification,
    MeanVarianceWithCosts,
    MinimumVariance,
    RiskParity,
    compare_optimizers,
)

ASSETS = ["A", "B", "C", "D"]


def _cov(seed: int = 1, n: int = 4) -> pd.DataFrame:
    """Une covariance définie positive tirée au hasard, A A' + diagonale."""
    g = make_generator(seed)
    a = g.normal(size=(n, n))
    m = a @ a.T / n + np.diag(np.linspace(0.5, 1.5, n))
    m = m * 0.01
    names = ASSETS[:n] if n <= 4 else [f"X{i}" for i in range(n)]
    return pd.DataFrame(m, index=names, columns=names)


def test_equiponderation_rend_un_sur_n() -> None:
    """Source (a) : 1/N par actif."""
    w = EqualWeight().optimize(covariance=_cov())
    assert np.allclose(w.to_numpy(), 0.25)
    assert EqualWeight().check(w, _cov()).passed


def test_inverse_de_volatilite_forme_fermee() -> None:
    """Source (b) : variances 0,04 et 0,01, volatilités 0,2 et 0,1, poids 1/3 et 2/3."""
    cov = pd.DataFrame(np.diag([0.04, 0.01]), index=["a", "b"], columns=["a", "b"])
    w = InverseVolatility().optimize(covariance=cov)
    assert w["a"] == pytest.approx(1 / 3) and w["b"] == pytest.approx(2 / 3)
    assert InverseVolatility().check(w, cov).passed


def test_variance_minimale_sur_deux_actifs_non_correles_est_l_inverse_de_variance() -> None:
    """Source (a) : sans corrélation, w_i est proportionnel à 1/sigma_i^2 : 0,04 et 0,01 donnent 0,2 et 0,8."""
    cov = pd.DataFrame(np.diag([0.04, 0.01]), index=["a", "b"], columns=["a", "b"])
    w = MinimumVariance().optimize(covariance=cov)
    assert w["a"] == pytest.approx(0.2, abs=1e-5) and w["b"] == pytest.approx(0.8, abs=1e-5)
    assert MinimumVariance().check(w, cov).passed


def test_variance_minimale_bat_toute_alternative_admissible() -> None:
    """Source (a) : l'optimum a une variance inférieure à mille portefeuilles long only tirés au hasard."""
    cov = _cov(3)
    w = MinimumVariance().optimize(covariance=cov)
    c = cov.to_numpy()
    v_opt = float(w.to_numpy() @ c @ w.to_numpy())
    g = make_generator(9)
    for _ in range(1000):
        x = g.random(4)
        x = x / x.sum()
        assert float(x @ c @ x) >= v_opt - 1e-9
    assert MinimumVariance().check(w, cov).passed


def test_parite_de_risque_egalise_les_contributions_par_un_calcul_independant() -> None:
    """Source (d) : quantlab.analytics.contributions recalcule les contributions ; elles doivent être égales."""
    cov = _cov(4)
    w = RiskParity().optimize(covariance=cov)
    rc = risk_contribution(w, cov)
    assert np.allclose(rc.to_numpy(), rc.mean(), rtol=1e-6)
    assert w.sum() == pytest.approx(1.0, abs=1e-10) and (w > 0).all()
    assert RiskParity().check(w, cov).passed


def test_parite_de_risque_sans_correlation_egale_l_inverse_de_volatilite() -> None:
    """Source (a) : sur une covariance diagonale, parité de risque et inverse de volatilité coïncident."""
    cov = pd.DataFrame(np.diag([0.04, 0.01, 0.0225]), index=["a", "b", "c"], columns=["a", "b", "c"])
    rp = RiskParity().optimize(covariance=cov)
    iv = InverseVolatility().optimize(covariance=cov)
    assert np.allclose(rp.to_numpy(), iv.to_numpy(), atol=1e-6)


def test_budget_de_risque_inegal_est_respecte() -> None:
    """Source (a) : avec un budget 3:1:1:1, la contribution du premier vaut trois fois celle des autres."""
    cov = _cov(5)
    budget = pd.Series([3.0, 1.0, 1.0, 1.0], index=ASSETS)
    w = RiskParity(budget=budget).optimize(covariance=cov)
    rc = risk_contribution(w, cov)
    assert rc["A"] / rc["B"] == pytest.approx(3.0, rel=1e-5)
    assert RiskParity(budget=budget).check(w, cov).passed


def test_diversification_maximale_est_un_maximum_local() -> None:
    """Source (a) : aucun transfert de masse entre deux actifs n'améliore le ratio."""
    cov = _cov(6)
    w = MaximumDiversification().optimize(covariance=cov)
    assert w.sum() == pytest.approx(1.0, abs=1e-6)
    assert MaximumDiversification().check(w, cov).passed


def test_hrp_rend_des_poids_positifs_de_somme_un() -> None:
    """Source (a) : les seules propriétés garanties de la méthode."""
    cov = _cov(7, n=6)
    w = HierarchicalRiskParity().optimize(covariance=cov)
    assert HierarchicalRiskParity().check(w, cov).passed


def test_hrp_sur_une_covariance_diagonale_egale_l_inverse_de_variance() -> None:
    """Source (a) : sans corrélation, chaque bissection alloue en inverse de variance, donc le total aussi.

    Variances 0,04, 0,01, 0,02, 0,05 : inverses 25, 100, 50, 20, somme 195, poids 25/195, 100/195, 50/195, 20/195.
    """
    cov = pd.DataFrame(np.diag([0.04, 0.01, 0.02, 0.05]), index=ASSETS, columns=ASSETS)
    w = HierarchicalRiskParity().optimize(covariance=cov)
    attendu = np.array([25, 100, 50, 20]) / 195
    assert np.allclose(np.sort(w.to_numpy()), np.sort(attendu), atol=1e-12)
    assert w["B"] == pytest.approx(100 / 195)


def test_moyenne_variance_sans_contrainte_egale_la_forme_fermee() -> None:
    """Source (a) : w* = Sigma^-1 alpha / lambda."""
    cov = _cov(8)
    alpha = pd.Series([0.05, 0.02, -0.01, 0.03], index=ASSETS)
    opt = MeanVarianceWithCosts(risk_aversion=4.0)
    w = opt.optimize(alpha=alpha, covariance=cov)
    closed = np.linalg.solve(cov.to_numpy(), alpha.to_numpy()) / 4.0
    assert np.allclose(w.to_numpy(), closed, atol=1e-5)
    assert opt.check(w, cov, alpha).passed


def test_le_cout_de_transaction_rend_l_optimiseur_reticent_a_bouger() -> None:
    """Source (a) : avec un coût, la rotation depuis w_old est plus faible ; à coût nul elle est maximale."""
    cov = _cov(9)
    alpha = pd.Series([0.05, 0.02, -0.01, 0.03], index=ASSETS)
    previous = pd.Series([0.25, 0.25, 0.25, 0.25], index=ASSETS)
    sans = MeanVarianceWithCosts(risk_aversion=4.0, cost_per_unit=0.0).optimize(
        alpha=alpha, covariance=cov, previous=previous
    )
    avec = MeanVarianceWithCosts(risk_aversion=4.0, cost_per_unit=0.02).optimize(
        alpha=alpha, covariance=cov, previous=previous
    )
    rotation_sans = float((sans - previous).abs().sum())
    rotation_avec = float((avec - previous).abs().sum())
    assert rotation_avec < rotation_sans


def test_les_bornes_sont_respectees() -> None:
    """Source (a) : exposition brute et poids maximal."""
    cov = _cov(10)
    alpha = pd.Series([0.08, 0.02, -0.04, 0.03], index=ASSETS)
    opt = MeanVarianceWithCosts(risk_aversion=1.0, max_gross=1.5, max_weight=0.6)
    w = opt.optimize(alpha=alpha, covariance=cov)
    assert w.abs().sum() <= 1.5 + DEFAULT_SOLVER_TOLERANCE and w.abs().max() <= 0.6 + DEFAULT_SOLVER_TOLERANCE
    assert opt.check(w, cov, alpha).passed


def test_une_covariance_mal_formee_est_refusee() -> None:
    """Source (a) : lignes et colonnes doivent porter les mêmes actifs."""
    cov = pd.DataFrame(np.eye(2), index=["a", "b"], columns=["a", "c"])
    with pytest.raises(DataQualityError):
        EqualWeight().optimize(covariance=cov)


def test_compare_optimizers_rend_une_ligne_par_optimiseur_et_les_controles_passent() -> None:
    """Source (a) : le tableau de comparaison et ses contrôles indépendants."""
    cov = _cov(11)
    table = compare_optimizers(
        cov,
        {"ew": EqualWeight(), "iv": InverseVolatility(), "mv": MinimumVariance(), "rp": RiskParity()},
    )
    assert list(table.index) == ["ew", "iv", "mv", "rp"]
    assert table["check_passed"].all()
    assert table.loc["mv", "volatility"] <= table.loc["ew", "volatility"] + 1e-12


@settings(max_examples=20, deadline=None)
@given(seed=st.integers(min_value=20, max_value=2000))
def test_propriete_parite_de_risque_toujours_egale(seed: int) -> None:
    """Source (d) : quelle que soit la covariance, les contributions rendues sont égales."""
    cov = _cov(seed, n=5)
    w = RiskParity().optimize(covariance=cov)
    rc = risk_contribution(w, cov).to_numpy()
    assert np.allclose(rc, rc.mean(), rtol=1e-5)

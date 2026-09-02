"""Tests des estimateurs de covariance.

Sources des valeurs attendues : (a) identité mathématique, (b) calcul à la main
écrit en commentaire, (d) implémentation indépendante, ``numpy`` ou
``scikit-learn``. Aucune ne vient de la sortie du module.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sklearn.covariance import LedoitWolf as SkLedoitWolf

from quantlab.core.determinism import make_generator
from quantlab.core.errors import DataQualityError, InsufficientDataError
from quantlab.core.types import Frequency
from quantlab.portfolio.covariance import (
    ConstantCorrelationShrinkage,
    DenoisedCovariance,
    EWMACovariance,
    FactorCovariance,
    LedoitWolfCovariance,
    SampleCovariance,
    annualize_covariance,
    condition_number,
    is_psd,
    nearest_psd,
    risk_model_report,
    to_correlation,
)


def _panel(seed: int, n_periods: int = 120, n_assets: int = 6) -> pd.DataFrame:
    """Un panel à structure factorielle : facteur commun chargé à 0,6 plus bruit propre."""
    g = make_generator(seed)
    f = g.normal(size=n_periods)
    data = {f"A{i}": 0.6 * f + g.normal(size=n_periods) for i in range(n_assets)}
    return pd.DataFrame(data, index=pd.date_range("2015-01-31", periods=n_periods, freq="ME")) * 0.01


def test_empirique_egale_numpy() -> None:
    """Source (d) : numpy.cov avec ddof=1 sur les mêmes données."""
    r = _panel(1)
    cov = SampleCovariance().covariance(r)
    attendu = np.cov(r.to_numpy(), rowvar=False, ddof=1)
    assert np.allclose(cov.to_numpy(), attendu, atol=1e-15)
    assert list(cov.index) == list(r.columns)


def test_ewma_sur_deux_observations_se_deroule_a_la_main() -> None:
    """Source (b). Deux actifs, deux périodes, demi-vie 1 donc lambda = 0,5, moyenne supposée nulle.

    r1 = (0,02 ; 0,00), r2 = (0,00 ; 0,04).
    S1 = 0,5 * r1 r1' = [[0,0002, 0], [0, 0]] ; poids cumulé 0,5.
    S2 = 0,5 * S1 + 0,5 * r2 r2' = [[0,0001, 0], [0, 0,0008]] ; poids cumulé 0,75.
    Normalisé : [[0,0001/0,75, 0], [0, 0,0008/0,75]] = [[1,3333e-4, 0], [0, 1,0667e-3]].
    """
    r = pd.DataFrame(
        [[0.02, 0.00], [0.00, 0.04]],
        columns=["a", "b"],
        index=pd.date_range("2020-01-31", periods=2, freq="ME"),
    )
    cov = EWMACovariance(halflife=1.0, assume_zero_mean=True).covariance(r)
    assert cov.loc["a", "a"] == pytest.approx(0.0001 / 0.75, rel=1e-9)
    assert cov.loc["b", "b"] == pytest.approx(0.0008 / 0.75, rel=1e-9)
    assert abs(cov.loc["a", "b"]) < 1e-15


def test_ewma_demi_vie_de_soixante_donne_lambda_de_la_docstring() -> None:
    """Source (b) : 0,5^(1/60) = 0,98851, et le poids cumulé des 60 derniers points vaut 50 %."""
    m = EWMACovariance(halflife=60)
    assert m.decay == pytest.approx(0.5 ** (1 / 60), abs=1e-12)
    assert m.decay == pytest.approx(0.98851, abs=5e-6)
    poids = (1 - m.decay) * m.decay ** np.arange(60)
    assert poids.sum() == pytest.approx(0.5, abs=1e-12)


def test_ewma_a_demi_vie_infinie_tend_vers_l_empirique_de_moyenne_nulle() -> None:
    """Source (a) : lambda -> 1 donne des poids uniformes, donc la covariance non centrée moyenne."""
    r = _panel(2)
    cov = EWMACovariance(halflife=1e7, assume_zero_mean=True).covariance(r)
    x = r.to_numpy()
    attendu = (x.T @ x) / len(x)
    assert np.allclose(cov.to_numpy(), attendu, rtol=1e-4)


def test_ledoit_wolf_identite_egale_scikit_learn() -> None:
    """Source (d) : sklearn.covariance.LedoitWolf sur les mêmes données."""
    r = _panel(3)
    ours = LedoitWolfCovariance().covariance(r)
    ref = SkLedoitWolf(assume_centered=False).fit(r.to_numpy())
    assert np.allclose(ours.to_numpy(), ref.covariance_, atol=1e-15)
    assert LedoitWolfCovariance().shrinkage(r) == pytest.approx(float(ref.shrinkage_))


def test_la_cible_a_correlation_constante_a_des_correlations_egales() -> None:
    """Source (a) : hors diagonale, toutes les corrélations de la cible valent la moyenne."""
    r = _panel(4)
    cible = to_correlation(ConstantCorrelationShrinkage().target(r)).to_numpy()
    hors = cible[~np.eye(len(cible), dtype=bool)]
    assert np.allclose(hors, hors[0], atol=1e-12)
    corr_emp = to_correlation(SampleCovariance(ddof=0).covariance(r)).to_numpy()
    moy = (corr_emp.sum() - len(corr_emp)) / (len(corr_emp) * (len(corr_emp) - 1))
    assert hors[0] == pytest.approx(moy, abs=1e-12)


def _panel_heterogene(seed: int, n_periods: int, n_assets: int = 8) -> pd.DataFrame:
    """Un panel dont les chargements varient, donc dont la vraie corrélation N'EST PAS constante."""
    g = make_generator(seed)
    f = g.normal(size=n_periods)
    data = {f"A{i}": (0.1 + 0.15 * i) * f + g.normal(size=n_periods) for i in range(n_assets)}
    return pd.DataFrame(data, index=pd.date_range("2015-01-31", periods=n_periods, freq="ME")) * 0.01


def test_l_intensite_reste_dans_zero_un_et_decroit_avec_l_echantillon() -> None:
    """Source (a) : delta = min(1, max(0, kappa/T)), et kappa reste borné quand la cible est FAUSSE.

    Quand la vraie matrice n'est pas à corrélation constante, gamma tend vers une
    limite positive, donc kappa reste fini et delta décroît en 1/T.
    """
    court = ConstantCorrelationShrinkage().shrinkage(_panel_heterogene(5, n_periods=24))
    long = ConstantCorrelationShrinkage().shrinkage(_panel_heterogene(5, n_periods=2400))
    assert 0.0 <= long <= court <= 1.0
    assert long < 0.1


def test_l_intensite_tend_vers_un_quand_la_cible_est_exacte() -> None:
    """Source (a) : si la vraie matrice EST à corrélation constante, gamma tend vers zéro et delta vers un.

    Le panel de ``_panel`` charge tous les actifs à 0,6 sur un même facteur avec
    un bruit de même variance, donc ses corrélations vraies sont toutes égales.
    Rétrécir entièrement vers la cible est alors la bonne réponse, et c'est
    exactement ce que la forme fermée de Ledoit et Wolf doit rendre.
    """
    delta = ConstantCorrelationShrinkage().shrinkage(_panel(5, n_periods=2400, n_assets=8))
    assert delta > 0.9


def test_le_modele_factoriel_conserve_la_diagonale_et_redonne_l_empirique_a_k_egal_n() -> None:
    """Source (a) : D absorbe le résidu, donc la diagonale est exacte ; k = N redonne S."""
    r = _panel(6, n_assets=5)
    s = SampleCovariance().covariance(r)
    f2 = FactorCovariance(n_factors=2).covariance(r)
    assert np.allclose(np.diag(f2.to_numpy()), np.diag(s.to_numpy()), atol=1e-15)
    f5 = FactorCovariance(n_factors=5).covariance(r)
    assert np.allclose(f5.to_numpy(), s.to_numpy(), atol=1e-12)


def test_nearest_psd_repare_une_matrice_indefinie() -> None:
    """Source (b) : [[1, 2], [2, 1]] a pour valeurs propres 3 et -1 ; après projection, min >= epsilon."""
    m = pd.DataFrame([[1.0, 2.0], [2.0, 1.0]], index=["a", "b"], columns=["a", "b"])
    assert not is_psd(m)
    fixed = nearest_psd(m, epsilon=1e-8)
    assert is_psd(fixed)
    assert np.linalg.eigvalsh(fixed.to_numpy()).min() >= 1e-8 - 1e-12
    assert np.linalg.eigvalsh(fixed.to_numpy()).max() == pytest.approx(3.0)


def test_conditionnement_et_annualisation() -> None:
    """Source (b) : diag(4, 1) a un conditionnement de 4 ; annualiser multiplie par N."""
    m = pd.DataFrame(np.diag([4.0, 1.0]), index=["a", "b"], columns=["a", "b"])
    assert condition_number(m) == pytest.approx(4.0)
    assert annualize_covariance(m, Frequency.MONTHLY).loc["a", "a"] == pytest.approx(48.0)


def test_trop_peu_de_periodes_ou_d_actifs_est_refuse() -> None:
    """Source (a) : une covariance sur une période, ou sur un seul actif, n'existe pas."""
    with pytest.raises(InsufficientDataError):
        SampleCovariance().covariance(_panel(7, n_periods=1))
    with pytest.raises(InsufficientDataError):
        SampleCovariance().covariance(_panel(7)[["A0"]])
    with pytest.raises(DataQualityError):
        FactorCovariance(n_factors=99).covariance(_panel(7))


def test_le_rapport_compare_les_estimateurs() -> None:
    """Source (a) : l'empirique est à distance nulle d'elle-même, et le rétrécissement en réduit le conditionnement."""
    r = _panel(8, n_periods=40, n_assets=10)
    rep = risk_model_report(
        r, {"sample": SampleCovariance(), "lw": LedoitWolfCovariance(), "cc": ConstantCorrelationShrinkage()}
    )
    assert rep.loc["sample", "frobenius_distance_to_sample"] == pytest.approx(0.0, abs=1e-15)
    assert rep.loc["lw", "condition_number"] < rep.loc["sample", "condition_number"]
    assert 0.0 <= rep.loc["cc", "shrinkage"] <= 1.0


@settings(max_examples=25, deadline=None)
@given(seed=st.integers(min_value=100, max_value=5000), n=st.integers(min_value=3, max_value=8))
def test_propriete_tous_les_estimateurs_sont_symetriques_et_psd(seed: int, n: int) -> None:
    """Source (a) : une covariance est symétrique et semi-définie positive, quel que soit l'estimateur."""
    r = _panel(seed, n_periods=60, n_assets=n)
    for model in (
        SampleCovariance(),
        EWMACovariance(halflife=20),
        LedoitWolfCovariance(),
        ConstantCorrelationShrinkage(),
        FactorCovariance(n_factors=2),
        DenoisedCovariance(),
    ):
        cov = model.covariance(r).to_numpy()
        assert np.allclose(cov, cov.T, atol=1e-12)
        assert is_psd(cov, tol=-1e-9)

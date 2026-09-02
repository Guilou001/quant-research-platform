"""Tests de la comparaison de trajectoires.

Chaque valeur attendue vient d'une identité mathématique (a), d'un calcul à la
main écrit en commentaire (b) ou de ``statsmodels`` (d). Aucune ne vient de la
sortie du module.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from quantlab.analytics.comparison import (
    FundProxy,
    compare_trajectories,
    comparison_table,
    drawdown_overlap,
    fund_returns_from_prices,
    load_fund_registry,
    similarity_reading,
)
from quantlab.core.determinism import make_generator
from quantlab.core.errors import InsufficientDataError
from quantlab.core.types import Frequency


def _serie(seed: int, n: int = 120, mu: float = 0.005, sigma: float = 0.03) -> pd.Series:
    g = make_generator(seed)
    idx = pd.date_range("2015-01-31", periods=n, freq="ME")
    return pd.Series(g.normal(mu, sigma, n), index=idx, name=f"s{seed}")


def test_une_serie_comparee_a_elle_meme_rend_les_identites() -> None:
    """Source (a) : corr 1, bêta 1, alpha 0, R2 1, recouvrement 1, erreur de suivi 0."""
    s = _serie(1)
    c = compare_trajectories(s, s, frequency=Frequency.MONTHLY)
    assert c.correlation == pytest.approx(1.0, abs=1e-12)
    assert c.beta == pytest.approx(1.0, abs=1e-9)
    assert c.alpha_annual == pytest.approx(0.0, abs=1e-9)
    assert c.r_squared == pytest.approx(1.0, abs=1e-12)
    assert c.tracking_error_annual == pytest.approx(0.0, abs=1e-9)
    assert c.drawdown_overlap == pytest.approx(1.0)
    assert c.sharpe_strategy == c.sharpe_fund
    assert c.n_periods == 120


def test_une_serie_comparee_a_son_oppose_rend_moins_un() -> None:
    """Source (a) : la corrélation de x avec -x vaut -1 et le bêta -1."""
    s = _serie(2)
    c = compare_trajectories(s, -s, frequency=Frequency.MONTHLY)
    assert c.correlation == pytest.approx(-1.0, abs=1e-12)
    assert c.beta == pytest.approx(-1.0, abs=1e-9)
    assert similarity_reading(c) == "opposé"


def test_le_beta_et_l_alpha_egalent_statsmodels() -> None:
    """Source (d) : la régression du fonds sur la stratégie, refaite avec statsmodels."""
    s = _serie(3)
    g = make_generator(4)
    fonds = (0.002 + 1.4 * s + pd.Series(g.normal(0, 0.01, len(s)), index=s.index)).rename("f")
    c = compare_trajectories(s, fonds, frequency=Frequency.MONTHLY)
    ols = sm.OLS(fonds.values, sm.add_constant(s.values)).fit()
    assert c.beta == pytest.approx(float(ols.params[1]), abs=1e-9)
    # L'alpha du module est ANNUALISÉ : douze fois la constante mensuelle.
    assert c.alpha_annual == pytest.approx(float(ols.params[0]) * 12, rel=1e-6)
    assert c.r_squared == pytest.approx(float(ols.rsquared), abs=1e-9)


def test_le_recouvrement_des_replis_est_un_rapport_de_jaccard() -> None:
    """Source (b) : construit à la main.

    Série A : perd 10 % au mois 2 puis remonte, en repli (sous -5 %) aux mois 2
    et 3 sur cinq. Série B : perd 10 % au mois 3 puis remonte, en repli aux mois
    3 et 4. Intersection {3}, union {2, 3, 4} : Jaccard = 1/3.
    """
    idx = pd.date_range("2020-01-31", periods=5, freq="ME")
    a = pd.Series([0.00, -0.10, 0.02, 0.10, 0.02], index=idx)
    b = pd.Series([0.00, 0.00, -0.10, 0.02, 0.10], index=idx)
    assert drawdown_overlap(a, b, threshold=0.05) == pytest.approx(1 / 3)


def test_sans_aucun_repli_le_recouvrement_est_indefini() -> None:
    """Source (a) : la question ne se pose pas, et un NaN vaut mieux qu'un zéro trompeur."""
    idx = pd.date_range("2020-01-31", periods=6, freq="ME")
    a = pd.Series([0.01] * 6, index=idx)
    assert np.isnan(drawdown_overlap(a, a))


def test_un_recouvrement_trop_court_est_refuse() -> None:
    """Source (a) : vingt-trois mois communs sous un minimum de vingt-quatre."""
    s = _serie(5, n=23)
    with pytest.raises(InsufficientDataError):
        compare_trajectories(s, s, frequency=Frequency.MONTHLY, min_periods=24)


def test_les_rendements_mensuels_des_fonds_se_composent_et_ne_se_moyennent_pas() -> None:
    """Source (b) : trois jours à +1 %, +2 %, -1 % donnent 1,01 x 1,02 x 0,99 - 1 = 1,9898 %."""
    prix = pd.DataFrame(
        {"X": [100.0, 101.0, 103.02, 101.9898]},
        index=pd.to_datetime(["2020-01-28", "2020-01-29", "2020-01-30", "2020-01-31"]),
    )
    r = fund_returns_from_prices(prix, frequency=Frequency.MONTHLY)
    assert float(r["X"].iloc[-1]) == pytest.approx(1.01 * 1.02 * 0.99 - 1, rel=1e-9)


def test_la_lecture_suit_les_seuils_declares() -> None:
    """Source (a) : les seuils sont ceux de la docstring de similarity_reading."""
    s = _serie(6)
    g = make_generator(7)
    proche = (s + pd.Series(g.normal(0, 0.005, len(s)), index=s.index)).rename("p")
    c = compare_trajectories(s, proche, frequency=Frequency.MONTHLY)
    assert c.correlation > 0.7
    assert similarity_reading(c) in {"même phénomène", "même phénomène, à une autre échelle"}
    amplifie = (3.0 * s).rename("a")
    c2 = compare_trajectories(s, amplifie, frequency=Frequency.MONTHLY)
    assert similarity_reading(c2) == "même phénomène, à une autre échelle"


def test_le_tableau_omet_les_couples_trop_courts_au_lieu_de_les_remplir() -> None:
    """Source (a) : un fonds de dix mois n'entre pas dans le tableau."""
    s = _serie(8)
    court = _serie(9, n=10)
    t = comparison_table({"s": s}, {"long": s, "court": court}, frequency=Frequency.MONTHLY)
    assert list(t["fund"]) == ["long"]


def test_le_registre_des_fonds_se_charge_et_refuse_une_cle_inconnue(tmp_path) -> None:
    """Source (a) : StrictModel refuse toute clé inconnue."""
    bon = tmp_path / "f.yaml"
    bon.write_text(
        "funds:\n  - ticker: AAA\n    name: A\n    family: x\n    strategy_hint: y\n    inception: '2020-01-01'\n",
        encoding="utf-8",
    )
    fonds = load_fund_registry(bon)
    assert len(fonds) == 1 and isinstance(fonds[0], FundProxy)
    mauvais = tmp_path / "g.yaml"
    mauvais.write_text(
        "funds:\n  - ticker: AAA\n    name: A\n    family: x\n    strategy_hint: y\n    inception: '2020'\n    frais: 1\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_fund_registry(mauvais)


@settings(max_examples=40, deadline=None)
@given(k=st.floats(min_value=0.2, max_value=5.0), seed=st.integers(min_value=10, max_value=10_000))
def test_propriete_le_beta_suit_l_echelle_et_la_correlation_ne_bouge_pas(k: float, seed: int) -> None:
    """Source (a) : le fonds k fois la stratégie a un bêta k et une corrélation 1."""
    s = _serie(seed)
    c = compare_trajectories(s, (k * s).rename("k"), frequency=Frequency.MONTHLY)
    assert c.beta == pytest.approx(k, rel=1e-6)
    assert c.correlation == pytest.approx(1.0, abs=1e-9)

"""Tests de la comparaison annuelle aux grands fonds fermés.

Chaque valeur attendue vient d'un calcul à la main (a), d'une identité (b) ou
d'une propriété de construction (c). Aucune ne vient de la sortie du module.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from quantlab.analytics.comparison import (
    HedgeFundRecord,
    annual_comparison_table,
    annual_returns,
    compare_annual,
    fisher_interval,
    hedge_fund_table,
    load_hedge_fund_registry,
    scale_to_volatility,
)
from quantlab.analytics.visualization.figures import (
    annual_returns_heatmap,
    annual_returns_lines,
    correlation_bars,
)
from quantlab.core.determinism import make_generator
from quantlab.core.errors import ConfigError, InsufficientDataError
from quantlab.core.types import Frequency

REGISTRY_YAML = """
consulted: "2026-09-02"
funds:
  - key: alpha
    name: Alpha
    manager: A
    style: quant
    annual_returns_pct: {2019: 10.0, 2020: -5.0, 2021: 20.0}
    gross_returns_pct: {2019: 15.0}
    verification: {2019-2020: page, 2021: resume}
    sources:
      - years: "2019-2021"
        text: "test"
        url: https://example.org
  - key: beta
    name: Beta
    manager: B
    style: macro
    annual_returns_pct: {2020: 3.0}
"""


def test_le_registre_se_lit_et_les_pour_cent_deviennent_des_fractions(tmp_path: Path) -> None:
    """Source (a). 10 % devient 0,10 ; l'année absente est manquante, pas nulle."""
    chemin = tmp_path / "hf.yaml"
    chemin.write_text(REGISTRY_YAML, encoding="utf-8")
    records = load_hedge_fund_registry(chemin)
    assert [r.key for r in records] == ["alpha", "beta"]
    table = hedge_fund_table(records)
    assert table.loc[2019, "alpha"] == pytest.approx(0.10)
    assert table.loc[2020, "alpha"] == pytest.approx(-0.05)
    assert np.isnan(table.loc[2019, "beta"])
    assert table.loc[2020, "beta"] == pytest.approx(0.03)
    brut = hedge_fund_table(records, basis="gross")
    assert list(brut.columns) == ["alpha"]
    assert brut.loc[2019, "alpha"] == pytest.approx(0.15)


def test_le_degre_de_verification_lit_les_plages_et_les_annees() -> None:
    """Une plage 2019-2020 couvre ses deux bornes ; une année hors registre est non déclarée."""
    record = HedgeFundRecord(
        key="x",
        name="X",
        manager="M",
        style="s",
        annual_returns_pct={2019: 1.0, 2020: 2.0, 2021: 3.0},
        verification={"2019-2020": "page", 2021: "resume"},
    )
    assert record.verification_of(2019) == "page"
    assert record.verification_of(2020) == "page"
    assert record.verification_of(2021) == "resume"
    assert record.verification_of(2018) == "non déclaré"


def test_douze_mois_a_un_pour_cent_composent_a_12_6825_pour_cent() -> None:
    """Source (a). 1,01^12 - 1 = 0,126825. L'année incomplète est écartée."""
    idx = pd.date_range("2020-01-31", periods=18, freq="ME")
    monthly = pd.Series(0.01, index=idx)
    annual = annual_returns(monthly)
    assert list(annual.index) == [2020]
    assert annual.loc[2020] == pytest.approx(1.01**12 - 1.0, rel=1e-12)
    partial = annual_returns(monthly, require_complete=False)
    assert list(partial.index) == [2020, 2021]
    assert partial.loc[2021] == pytest.approx(1.01**6 - 1.0, rel=1e-12)


def test_aucune_annee_complete_leve() -> None:
    """Six mois seuls ne font pas une année."""
    idx = pd.date_range("2020-01-31", periods=6, freq="ME")
    with pytest.raises(InsufficientDataError):
        annual_returns(pd.Series(0.01, index=idx))


def test_intervalle_de_fisher_a_la_main() -> None:
    """Source (a). r = 0,5, n = 12 : z = 0,5493, demi-largeur 1,96/3 = 0,6533.

    tanh(0,5493 - 0,6533) = -0,1036 et tanh(0,5493 + 0,6533) = 0,8345.
    """
    lo, hi = fisher_interval(0.5, 12)
    assert lo == pytest.approx(-0.1036, abs=5e-4)
    assert hi == pytest.approx(0.8345, abs=5e-4)
    assert all(math.isnan(v) for v in fisher_interval(0.5, 3))
    lo1, hi1 = fisher_interval(1.0, 10)
    assert lo1 > 0.99 and hi1 > 0.99


def test_une_serie_comparee_a_son_double_a_une_correlation_de_un() -> None:
    """Source (b). Corr 1, intervalle au-dessus de 0,99, taux de victoire nul si le fonds est le double."""
    years = pd.Index(range(2010, 2022))
    g = make_generator(1)
    ours = pd.Series(g.normal(0.05, 0.1, len(years)), index=years)
    fund = 2.0 * ours + 0.5
    c = compare_annual(ours, fund, strategy_name="nous", fund_name="double")
    assert c.n_years == 12
    assert c.correlation == pytest.approx(1.0)
    assert c.corr_lo > 0.99
    assert c.hit_rate == 0.0
    assert c.reading == "co-mouvement établi"
    assert c.mean_fund == pytest.approx(2.0 * c.mean_strategy + 0.5)
    assert c.vol_fund == pytest.approx(2.0 * c.vol_strategy)


def test_serie_opposee_et_trop_peu_d_annees() -> None:
    """Source (b). L'opposé donne -1 ; quatre années communes ne publient rien."""
    years = pd.Index(range(2010, 2022))
    g = make_generator(2)
    ours = pd.Series(g.normal(0.05, 0.1, len(years)), index=years)
    opposed = compare_annual(ours, -ours)
    assert opposed.correlation == pytest.approx(-1.0)
    assert opposed.reading == "mouvements opposés"
    short = compare_annual(ours, ours.iloc[:4])
    assert short.n_years == 4
    assert math.isnan(short.correlation)
    assert short.reading.startswith("trop peu")


def test_sans_annee_commune_le_tableau_le_dit() -> None:
    """Un fonds sans année commune apparaît avec zéro année, il n'est pas omis."""
    ours = pd.Series([0.1, 0.2, 0.0, 0.05, 0.1, -0.02], index=pd.Index(range(2015, 2021)))
    funds = pd.DataFrame({"far": pd.Series({1990: 0.3, 1991: 0.2}), "near": ours * 0.5})
    table = annual_comparison_table(ours, funds, strategy_name="nous")
    far = table.set_index("fund").loc["far"]
    assert far["n_years"] == 0
    assert far["reading"] == "aucune année commune"
    near = table.set_index("fund").loc["near"]
    assert near["correlation"] == pytest.approx(1.0)
    with pytest.raises(InsufficientDataError):
        compare_annual(ours, funds["far"].dropna())


def test_la_mise_a_l_echelle_atteint_la_cible_et_garde_le_sharpe() -> None:
    """Source (b). La volatilité rendue vaut la cible ; le rapport moyenne sur écart type est inchangé."""
    idx = pd.date_range("2015-01-31", periods=120, freq="ME")
    g = make_generator(3)
    s = pd.Series(g.normal(0.004, 0.02, 120), index=idx)
    scaled = scale_to_volatility(s, 0.10, frequency=Frequency.MONTHLY)
    assert scaled.std(ddof=1) * math.sqrt(12) == pytest.approx(0.10, rel=1e-12)
    assert scaled.mean() / scaled.std(ddof=1) == pytest.approx(s.mean() / s.std(ddof=1), rel=1e-12)
    with pytest.raises(InsufficientDataError):
        scale_to_volatility(pd.Series(0.0, index=idx), 0.10, frequency=Frequency.MONTHLY)


def _annual_frame() -> pd.DataFrame:
    g = make_generator(4)
    years = pd.Index(range(2010, 2020), name="year")
    frame = pd.DataFrame(g.normal(0.08, 0.15, size=(10, 3)), index=years, columns=["nous", "f1", "f2"])
    frame.loc[2012, "f2"] = np.nan
    return frame


def test_les_figures_annuelles_rendent_le_tableau_trace() -> None:
    """Chaque fabrique rend le tableau dessiné, et le titre est déduit des données."""
    frame = _annual_frame()
    fig, drawn = annual_returns_lines(frame, highlight="nous")
    assert drawn.equals(frame)
    assert "2010-2019" in fig.axes[0].get_title()
    fig2, drawn2 = annual_returns_heatmap(frame, highlight="nous")
    assert next(iter(drawn2.columns)) == "nous"
    assert set(drawn2.columns) == set(frame.columns)
    assert "non trouvée" in fig2.axes[0].get_title()
    with pytest.raises(ConfigError):
        annual_returns_lines(frame, highlight="absent")


def test_les_barres_de_correlation_sont_triees_et_tolerent_le_manquant() -> None:
    """Le tableau rendu est trié par corrélation, les manquants en premier."""
    table = pd.DataFrame(
        {
            "fund": ["a", "b", "c"],
            "correlation": [0.3, np.nan, -0.2],
            "corr_lo": [-0.1, np.nan, -0.6],
            "corr_hi": [0.6, np.nan, 0.3],
            "n_years": [10, 2, 8],
        }
    )
    fig, drawn = correlation_bars(table)
    assert list(drawn["fund"]) == ["b", "c", "a"]
    assert "3 fonds" in fig.axes[0].get_title()
    with pytest.raises(ConfigError):
        correlation_bars(table.drop(columns=["corr_lo"]))

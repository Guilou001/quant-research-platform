"""L'empilement, vérifié à la main : identité à un, exemple de la spécification 007, cible de volatilité."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantlab.core.errors import ConfigError
from quantlab.execution.leverage import apply_leverage, volatility_target_exposure

MOIS = pd.date_range("2020-01-31", periods=3, freq="ME")


def test_une_exposition_constante_a_un_sans_cout_rend_le_rendement_d_origine() -> None:
    r = pd.Series([0.02, -0.01, 0.015], index=MOIS)
    e = pd.Series(1.0, index=MOIS)
    resultat = apply_leverage(r, e, financing_spread_annual=0.006, periods_per_year=12)
    assert np.allclose(resultat.net, r, atol=1e-12)
    assert float(resultat.financing_cost.sum()) == 0.0


def test_l_exemple_de_la_specification_007() -> None:
    """Exposition 1,5, rendement -1 %, écart 0,6 % par an : -1,5 % moins 0,025 %, soit -1,525 %."""
    r = pd.Series([0.02, -0.01, 0.015], index=MOIS)
    e = pd.Series(1.5, index=MOIS)
    resultat = apply_leverage(r, e, financing_spread_annual=0.006, periods_per_year=12)
    # Le premier mois tient l'exposition initiale, un, la décision n'étant connue qu'après.
    assert resultat.exposure.tolist() == [1.0, 1.5, 1.5]
    assert resultat.net.iloc[1] == pytest.approx(-0.01525, abs=1e-12)
    assert resultat.financing_cost.iloc[1] == pytest.approx(0.00025, abs=1e-12)


def test_un_changement_d_exposition_coute_par_unite_negociee() -> None:
    r = pd.Series([0.0, 0.0, 0.0], index=MOIS)
    e = pd.Series([1.5, 1.5, 1.5], index=MOIS)
    resultat = apply_leverage(
        r, e, financing_spread_annual=0.0, periods_per_year=12, trade_cost_per_unit=0.0004
    )
    # Passage de 1 à 1,5 au deuxième mois : un demi-dollar négocié à 4 points de base.
    assert resultat.trading_cost.tolist() == pytest.approx([0.0, 0.0002, 0.0], abs=1e-12)


def test_la_cible_de_volatilite_rend_la_cible_sur_la_volatilite_de_la_fenetre() -> None:
    """Rendements alternés de +1 % et -1 % sur 36 mois : la variance vaut 0,0001 fois 36 sur 35."""
    index = pd.date_range("2015-01-31", periods=36, freq="ME")
    r = pd.Series(np.tile([0.01, -0.01], 18), index=index)
    ecart_type = np.sqrt(0.0001 * 36 / 35) * np.sqrt(12)
    e = volatility_target_exposure(r, target_vol=0.10, window=36, periods_per_year=12, max_leverage=5.0)
    assert e.iloc[:35].isna().all()
    assert e.iloc[-1] == pytest.approx(0.10 / ecart_type, rel=1e-12)
    plafonne = volatility_target_exposure(
        r, target_vol=0.10, window=36, periods_per_year=12, max_leverage=1.5
    )
    assert plafonne.iloc[-1] == pytest.approx(1.5, abs=1e-12)


def test_les_parametres_absurdes_sont_refuses() -> None:
    r = pd.Series([0.01, -0.01], index=MOIS[:2])
    with pytest.raises(ConfigError):
        volatility_target_exposure(r, target_vol=0.0, window=2, periods_per_year=12, max_leverage=1.0)
    with pytest.raises(ConfigError):
        apply_leverage(r, pd.Series(1.0, index=MOIS[:2]), financing_spread_annual=-0.01, periods_per_year=12)

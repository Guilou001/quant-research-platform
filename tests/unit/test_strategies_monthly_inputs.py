"""Le passage des prix quotidiens aux tableaux mensuels de la stratégie, calculé à la main."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantlab.core.errors import DataQualityError
from quantlab.strategies.time_series_momentum import monthly_inputs_from_prices


def _prix() -> pd.DataFrame:
    """Deux instruments sur janvier et février 2020, plus une séance isolée en mars."""
    dates = pd.to_datetime(
        ["2020-01-29", "2020-01-30", "2020-01-31", "2020-02-27", "2020-02-28", "2020-03-02"]
    )
    return pd.DataFrame(
        {"A": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0], "B": [50.0, 49.0, 49.5, 50.5, 50.0, 51.0]},
        index=dates,
    )


def _taux(index: pd.DatetimeIndex) -> tuple[pd.Series, pd.Series]:
    quotidien = pd.Series(0.0001, index=index)
    mensuel = pd.Series(
        [0.001, 0.002, 0.003], index=pd.to_datetime(["2020-01-31", "2020-02-29", "2020-03-31"])
    )
    return quotidien, mensuel


def test_le_rendement_mensuel_est_le_rapport_des_fins_de_mois_moins_le_taux() -> None:
    """Février pour A : 104 / 102 - 1 = 1,9608 %, moins 0,2 % de taux mensuel."""
    prix = _prix()
    quotidien, mensuel = _taux(prix.index)
    entrees = monthly_inputs_from_prices(prix, quotidien, mensuel, min_periods=2, min_trading_days=2)
    fevrier = pd.Timestamp("2020-02-29")
    assert entrees.monthly_excess.loc[fevrier, "A"] == pytest.approx(104.0 / 102.0 - 1.0 - 0.002)
    assert entrees.monthly_excess.loc[fevrier, "B"] == pytest.approx(50.0 / 49.5 - 1.0 - 0.002)
    # Janvier compte deux rendements (le premier prix n'en a pas) : 102 / 100 - 1 moins 0,1 %.
    assert entrees.monthly_excess.loc[pd.Timestamp("2020-01-31"), "A"] == pytest.approx(0.02 - 0.001)


def test_un_mois_a_une_seule_seance_est_absent() -> None:
    prix = _prix()
    quotidien, mensuel = _taux(prix.index)
    entrees = monthly_inputs_from_prices(prix, quotidien, mensuel, min_periods=2, min_trading_days=2)
    assert np.isnan(entrees.monthly_excess.loc[pd.Timestamp("2020-03-31"), "A"])
    assert entrees.monthly_sessions.loc[pd.Timestamp("2020-03-31"), "A"] == 1


def test_les_mois_sont_dates_en_fin_de_mois_civile() -> None:
    prix = _prix()
    quotidien, mensuel = _taux(prix.index)
    entrees = monthly_inputs_from_prices(prix, quotidien, mensuel, min_periods=2, min_trading_days=2)
    assert list(entrees.monthly_excess.index) == list(
        pd.to_datetime(["2020-01-31", "2020-02-29", "2020-03-31"])
    )
    assert list(entrees.last_sessions) == list(pd.to_datetime(["2020-01-31", "2020-02-28", "2020-03-02"]))


def test_la_volatilite_de_decision_ignore_la_derniere_seance() -> None:
    """Changer le rendement du 28 février ne change pas la volatilité lue ce jour-là."""
    prix = _prix()
    quotidien, mensuel = _taux(prix.index)
    base = monthly_inputs_from_prices(prix, quotidien, mensuel, min_periods=2, min_trading_days=2)
    modifie = prix.copy()
    modifie.loc["2020-02-28", "A"] = 120.0
    autre = monthly_inputs_from_prices(modifie, quotidien, mensuel, min_periods=2, min_trading_days=2)
    fevrier = pd.Timestamp("2020-02-29")
    assert base.monthly_volatility.loc[fevrier, "A"] == pytest.approx(
        autre.monthly_volatility.loc[fevrier, "A"]
    )
    assert base.monthly_excess.loc[fevrier, "A"] != autre.monthly_excess.loc[fevrier, "A"]


def test_un_taux_quotidien_absent_au_depart_est_refuse() -> None:
    """Le taux se reporte vers l'avant, jamais vers l'arrière : un début sans taux est refusé."""
    prix = _prix()
    quotidien = pd.Series(0.0001, index=prix.index[2:])
    mensuel = _taux(prix.index)[1]
    with pytest.raises(DataQualityError):
        monthly_inputs_from_prices(prix, quotidien, mensuel, min_periods=2, min_trading_days=2)

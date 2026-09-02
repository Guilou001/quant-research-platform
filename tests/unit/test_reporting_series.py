"""Tests de l'enregistrement des séries d'étude."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantlab.core.determinism import make_generator
from quantlab.core.errors import DataQualityError
from quantlab.core.types import CostBasis, Frequency, SampleTag
from quantlab.reporting.series import load_series, load_series_index, save_series


def _serie(n: int = 60) -> pd.Series:
    g = make_generator(11)
    return pd.Series(g.normal(0.004, 0.03, n), index=pd.date_range("2018-01-31", periods=n, freq="ME"))


def test_aller_retour_exact(tmp_path) -> None:
    """Source (a) : relire ce qu'on a écrit rend la même série, au flottant près."""
    s = _serie()
    save_series(
        tmp_path,
        "gross",
        s,
        sample=SampleTag.OUT_OF_SAMPLE,
        basis=CostBasis.GROSS,
        frequency=Frequency.MONTHLY,
        universe="essai",
    )
    r = load_series(tmp_path, "gross")
    assert np.allclose(r.to_numpy(), s.to_numpy(), rtol=0, atol=1e-11)
    assert (r.index == s.index).all()
    idx = load_series_index(tmp_path)
    assert idx["gross"]["n_periods"] == 60 and idx["gross"]["sample"] == "OOS"


def test_un_pourcentage_non_converti_est_refuse(tmp_path) -> None:
    """Source (b) : 1,5 en fraction serait +150 % en un mois, donc un pourcentage oublié."""
    s = _serie()
    s.iloc[3] = 1.5
    with pytest.raises(DataQualityError):
        save_series(
            tmp_path,
            "x",
            s,
            sample=SampleTag.IN_SAMPLE,
            basis=CostBasis.GROSS,
            frequency=Frequency.MONTHLY,
            universe="essai",
        )


def test_une_serie_nette_declare_ses_couts(tmp_path) -> None:
    """Source (a) : règle 5, une performance nette porte ses hypothèses de coût."""
    with pytest.raises(DataQualityError):
        save_series(
            tmp_path,
            "net",
            _serie(),
            sample=SampleTag.IN_SAMPLE,
            basis=CostBasis.NET,
            frequency=Frequency.MONTHLY,
            universe="essai",
        )
    save_series(
        tmp_path,
        "net",
        _serie(),
        sample=SampleTag.IN_SAMPLE,
        basis=CostBasis.NET,
        frequency=Frequency.MONTHLY,
        universe="essai",
        cost_assumptions="3 pb par côté",
    )


def test_les_doublons_de_date_sont_refuses(tmp_path) -> None:
    """Source (a) : deux valeurs à la même date ne font pas une série."""
    s = _serie(4)
    s = pd.concat([s, s.iloc[:1]])
    with pytest.raises(DataQualityError):
        save_series(
            tmp_path,
            "d",
            s,
            sample=SampleTag.IN_SAMPLE,
            basis=CostBasis.GROSS,
            frequency=Frequency.MONTHLY,
            universe="essai",
        )

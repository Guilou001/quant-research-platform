"""La décomposition nuit et journée, sur trois jours écrits à la main."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantlab.analytics.returns import overnight_intraday_split
from quantlab.core.errors import DataQualityError

INDEX = pd.to_datetime(["2020-01-02", "2020-01-03", "2020-01-06"])


def _tableaux() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ouverture = pd.DataFrame({"X": [100.0, 103.0, 99.0]}, index=INDEX)
    cloture = pd.DataFrame({"X": [102.0, 101.0, 104.0]}, index=INDEX)
    # Un facteur d'ajustement de 0,5 le troisième jour, une division par deux.
    ajustee = pd.DataFrame({"X": [102.0, 101.0, 52.0]}, index=INDEX)
    return ouverture, cloture, ajustee


def test_la_nuit_et_la_journee_recomposent_la_cloture_a_cloture() -> None:
    ouverture, cloture, ajustee = _tableaux()
    nuit, jour = overnight_intraday_split(ouverture, cloture, ajustee)
    recompose = (1.0 + nuit) * (1.0 + jour) - 1.0
    attendu = ajustee / ajustee.shift(1) - 1.0
    assert np.allclose(recompose.iloc[1:], attendu.iloc[1:], atol=1e-12)
    assert nuit.iloc[0].isna().all()


def test_les_deux_parts_du_deuxieme_jour_a_la_main() -> None:
    """Le 3 janvier ouvre à 103 après une clôture à 102 : +0,98 % la nuit, puis 101 / 103 : -1,94 % le jour."""
    ouverture, cloture, ajustee = _tableaux()
    nuit, jour = overnight_intraday_split(ouverture, cloture, ajustee)
    assert nuit.loc["2020-01-03", "X"] == pytest.approx(103.0 / 102.0 - 1.0)
    assert jour.loc["2020-01-03", "X"] == pytest.approx(101.0 / 103.0 - 1.0)


def test_l_ouverture_est_ajustee_par_le_facteur_de_la_cloture() -> None:
    """Le 6 janvier, le facteur vaut 52 / 104 = 0,5 : l'ouverture ajustée vaut 49,5 et la nuit 49,5 / 101 - 1."""
    ouverture, cloture, ajustee = _tableaux()
    nuit, jour = overnight_intraday_split(ouverture, cloture, ajustee)
    assert nuit.loc["2020-01-06", "X"] == pytest.approx(49.5 / 101.0 - 1.0)
    assert jour.loc["2020-01-06", "X"] == pytest.approx(52.0 / 49.5 - 1.0)


def test_un_prix_nul_est_refuse() -> None:
    ouverture, cloture, ajustee = _tableaux()
    ouverture.iloc[1, 0] = 0.0
    with pytest.raises(DataQualityError):
        overnight_intraday_split(ouverture, cloture, ajustee)

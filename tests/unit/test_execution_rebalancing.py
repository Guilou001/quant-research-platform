"""Le rapprochement partiel vers la cible, calculé à la main sur deux actifs et trois périodes."""

from __future__ import annotations

import pandas as pd
import pytest

from quantlab.core.errors import ConfigError, DataQualityError
from quantlab.execution.rebalancing import partial_rebalance

INDEX = pd.to_datetime(["2020-01-31", "2020-02-29", "2020-03-31"])
CIBLES = pd.DataFrame({"A": [0.6, 0.6, 0.2], "B": [0.4, 0.4, 0.8]}, index=INDEX)
RENDEMENTS = pd.DataFrame({"A": [0.0, 0.10, 0.0], "B": [0.0, -0.05, 0.0]}, index=INDEX)


def test_a_taux_un_les_poids_decides_sont_la_cible() -> None:
    decides = partial_rebalance(CIBLES, RENDEMENTS, 1.0)
    pd.testing.assert_frame_equal(decides, CIBLES)


def test_a_taux_nul_rien_n_est_jamais_negocie() -> None:
    decides = partial_rebalance(CIBLES, RENDEMENTS, 0.0)
    assert (decides == 0.0).all().all()


def test_a_taux_un_demi_le_calcul_a_la_main_se_retrouve() -> None:
    """Janvier : rien de détenu, on va à mi-chemin, 0,3 / 0,2.

    Février : les 0,3 / 0,2 dérivent avec +10 % et -5 % : 0,33 et 0,19 sur une
    valeur de 1,02, soit 0,32353 et 0,18627 ; la cible 0,6 / 0,4 est à
    mi-chemin : 0,46176 et 0,29314. Mars : sans rendement, la dérive est nulle,
    et la cible 0,2 / 0,8 est à mi-chemin : 0,33088 et 0,54657.
    """
    decides = partial_rebalance(CIBLES, RENDEMENTS, 0.5)
    assert decides.loc["2020-01-31"].tolist() == pytest.approx([0.3, 0.2])
    a_fev = (0.33 / 1.02 + 0.6) / 2
    b_fev = (0.19 / 1.02 + 0.4) / 2
    assert decides.loc["2020-02-29"].tolist() == pytest.approx([a_fev, b_fev])
    assert decides.loc["2020-03-31"].tolist() == pytest.approx([(a_fev + 0.2) / 2, (b_fev + 0.8) / 2])


def test_la_rotation_decroit_avec_le_taux() -> None:
    def rotation(taux: float) -> float:
        decides = partial_rebalance(CIBLES, RENDEMENTS, taux)
        return float(decides.diff().abs().sum().sum())

    assert rotation(0.25) < rotation(0.5) < rotation(1.0)


def test_les_entrees_fausses_sont_refusees() -> None:
    with pytest.raises(ConfigError):
        partial_rebalance(CIBLES, RENDEMENTS, 1.5)
    with pytest.raises(DataQualityError):
        partial_rebalance(CIBLES, RENDEMENTS.iloc[:2], 0.5)
    with pytest.raises(DataQualityError):
        partial_rebalance(CIBLES.assign(A=[0.6, None, 0.2]), RENDEMENTS, 0.5)

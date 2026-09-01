"""Le mélange aléatoire d'une série temporelle doit être impossible, pas déconseillé.

Un découpage mélangé place des observations de 2020 dans l'entraînement et des
observations de 2015 dans le test. Le modèle apprend l'avenir et le rend au
passé, et la mesure hors échantillon devient une mesure dans l'échantillon. Elle
est alors excellente, ce qui rend la faute d'autant plus difficile à repérer.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantlab.core.errors import LookAheadError, QuantLabError


def test_le_decoupage_melange_leve_une_erreur_explicite() -> None:
    """Le garde-fou lève, et son message dit pourquoi plutôt que « interdit »."""
    from quantlab.validation.splits import train_test_split_forbidden

    with pytest.raises(QuantLabError) as info:
        train_test_split_forbidden(np.arange(100))
    message = str(info.value).lower()
    assert "temporel" in message or "mélange" in message or "chronolog" in message


@pytest.mark.parametrize("ancre", [True, False])
def test_aucun_pli_ne_place_l_entrainement_apres_le_test(ancre: bool) -> None:
    """Dans tout pli d'un walk-forward, l'entraînement précède entièrement le test.

    La propriété se vérifie sur les deux variantes, ancrée et glissante, parce
    qu'une erreur d'indice ne se manifeste pas forcément dans les deux.
    """
    from quantlab.validation.splits import WalkForward

    index = pd.bdate_range("2015-01-01", periods=500, freq="B")
    donnees = pd.DataFrame({"x": np.arange(len(index))}, index=index)
    cv = WalkForward(train_size=200, test_size=50, anchored=ancre)
    plis = list(cv.split(donnees))
    assert plis, "le découpage ne produit aucun pli"
    for entrainement, test in plis:
        assert entrainement.max() < test.min(), "une observation d'entraînement suit une observation de test"


def test_assert_chronological_attrape_le_cas_construit() -> None:
    """La garde appelée par les autres modules attrape un chevauchement évident."""
    from quantlab.validation.splits import assert_chronological

    with pytest.raises(LookAheadError):
        assert_chronological(np.array([0, 1, 2, 90]), np.array([50, 51, 52]))

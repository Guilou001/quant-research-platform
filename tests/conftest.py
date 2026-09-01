"""Les objets partagés par les tests, et la raison de chacun.

Trois principes gouvernent ces fixtures.

Le premier est le déterminisme : aucune donnée de test n'est tirée sans graine,
et les graines dérivées passent par ``child_generators`` plutôt que par une
addition, qui ne garantit pas l'indépendance des flux.

Le deuxième est l'isolement : aucun test n'écrit dans le vrai lac de données. La
fixture ``lake_root`` déplace la racine du laboratoire vers un répertoire
temporaire pour la durée du test.

Le troisième est l'indépendance des valeurs attendues. Une fixture rend des
données dont les propriétés sont connues par construction, pour que le test
compare à une vérité et non à la sortie du code qu'il teste.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from quantlab.core.determinism import child_generators, make_generator

#: La graine de référence des tests. Une seule, déclarée ici, jamais ailleurs.
TEST_SEED = 20260901


@pytest.fixture
def rng() -> np.random.Generator:
    """Rend le générateur aléatoire de référence des tests."""
    return make_generator(TEST_SEED)


@pytest.fixture
def rngs() -> list[np.random.Generator]:
    """Rend huit générateurs dont les flux sont indépendants par construction."""
    return child_generators(TEST_SEED, 8)


@pytest.fixture
def lake_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Déplace la racine du laboratoire vers un répertoire temporaire.

    Sans cette fixture, un test qui écrit une table écrirait dans le vrai lac,
    et le prochain test lirait ce qu'il n'a pas écrit. L'isolement est ce qui
    rend la suite rejouable dans n'importe quel ordre.
    """
    monkeypatch.setenv("QUANTLAB_ROOT", str(tmp_path))
    for layer in ("raw", "bronze", "silver", "gold"):
        (tmp_path / "data" / layer).mkdir(parents=True, exist_ok=True)
    (tmp_path / "metadata" / "manifests").mkdir(parents=True, exist_ok=True)
    (tmp_path / "artifacts").mkdir(parents=True, exist_ok=True)
    yield tmp_path


@pytest.fixture
def business_dates() -> pd.DatetimeIndex:
    """Rend 504 jours ouvrés à partir du 2 janvier 2020, soit deux ans environ.

    Le nombre est fixe et connu, ce qui permet à un test de vérifier une
    longueur sans la recalculer depuis la sortie de la fonction testée.
    """
    return pd.bdate_range("2020-01-02", periods=504, freq="B")


@pytest.fixture
def gaussian_returns(business_dates: pd.DatetimeIndex, rng: np.random.Generator) -> pd.Series:
    """Rend des rendements gaussiens de moyenne et d'écart type connus.

    La moyenne vaut 0,0004 par jour et l'écart type 0,01, ce qui donne environ
    10 % de rendement annualisé et 15,9 % de volatilité annualisée sous la
    convention de 252 séances. Ces valeurs sont des PARAMÈTRES, pas des
    mesures : l'échantillon tiré s'en écarte, et un test qui les compare doit
    tolérer un écart justifié par l'erreur type.
    """
    values = rng.normal(loc=0.0004, scale=0.01, size=len(business_dates))
    return pd.Series(values, index=business_dates, name="strategy")


@pytest.fixture
def known_wealth() -> pd.Series:
    """Rend une série de richesse dont les grandeurs se calculent à la main.

    Valeurs : 100, 120, 90, 110, 150. Le sommet vaut 120 avant la chute à 90,
    donc le pire repli vaut (90 - 120) / 120 = -0,25 exactement. Le
    recouvrement a lieu à 150, deux périodes après le creux.
    """
    idx = pd.bdate_range("2024-01-01", periods=5, freq="B")
    return pd.Series([100.0, 120.0, 90.0, 110.0, 150.0], index=idx, name="wealth")


@pytest.fixture
def panel_returns(business_dates: pd.DatetimeIndex, rng: np.random.Generator) -> pd.DataFrame:
    """Rend un panel de huit actifs, dont la structure de corrélation est posée.

    Chaque actif charge un facteur commun avec un coefficient de 0,6 et porte un
    bruit propre. La corrélation théorique entre deux actifs vaut donc
    0,6^2 / (0,6^2 + 1) = 0,265, valeur MODÉLISÉE que les tests peuvent viser
    avec une tolérance d'échantillonnage déclarée.
    """
    n = len(business_dates)
    factor = rng.normal(size=n)
    data = {f"A{i}": 0.6 * factor + rng.normal(size=n) for i in range(8)}
    frame = pd.DataFrame(data, index=business_dates) * 0.01
    return frame


@pytest.fixture
def pit_records() -> pd.DataFrame:
    """Rend le cas canonique du point-in-time, avec une correction de comptes.

    Trois lignes pour une même entreprise :

    - le trimestre clos le 2015-03-31, déposé le 2015-05-15, valeur 100 ;
    - le même trimestre, corrigé et redéposé le 2015-08-20, valeur 95 ;
    - le trimestre clos le 2015-06-30, déposé le 2015-08-05, valeur 110.

    Les tests attendus sont donc connus sans faire tourner le code. Au
    2015-03-31, rien n'est connaissable. Au 2015-06-01, la valeur du premier
    trimestre vaut 100. Au 2015-09-01, elle vaut 95.
    """
    return pd.DataFrame(
        {
            "entity": ["ACME"] * 3,
            "period_end": [
                dt.date(2015, 3, 31),
                dt.date(2015, 3, 31),
                dt.date(2015, 6, 30),
            ],
            "filing_date": [
                dt.date(2015, 5, 15),
                dt.date(2015, 8, 20),
                dt.date(2015, 8, 5),
            ],
            "available_from": [
                dt.date(2015, 5, 15),
                dt.date(2015, 8, 20),
                dt.date(2015, 8, 5),
            ],
            "value": [100.0, 95.0, 110.0],
        }
    )

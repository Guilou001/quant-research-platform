"""Vérifie les exemples du cours avec des résultats calculés à la main."""

import json
from pathlib import Path

import pytest

from quantlab.reporting.education import build_learning, fill_template, teaching_examples


def test_prediction_and_ranking_disagree() -> None:
    """Les erreurs valent 4 + 0 + 4 contre 16 + 9 + 4, en pourcentages carrés."""
    values = teaching_examples()
    assert values["forecast_r2"] == pytest.approx(21 / 29)
    assert values["forecast_rank"] == pytest.approx(-1)
    assert values["forecast_squared_error"] == pytest.approx(0.0008)
    assert values["zero_squared_error"] == pytest.approx(0.0029)


def test_compounding_and_multiple_search() -> None:
    """110 dollars diminués de 10 % laissent 99 dollars sur les 100 initiaux."""
    values = teaching_examples()
    assert values["compound_gain_loss"] == pytest.approx(-0.01)
    assert values["false_positive_100"] == pytest.approx(1 - (19 / 20) ** 100)


def test_unknown_value_cannot_be_published() -> None:
    """Un chiffre absent arrête la publication plutôt que de passer silencieusement."""
    with pytest.raises(KeyError):
        fill_template("Le résultat vaut {{inconnu}}", {})


def test_published_documents_match_sources() -> None:
    """Toute correction d'une source numérique doit atteindre les documents."""
    build_learning(Path(__file__).resolve().parents[2], check=True)


@pytest.mark.parametrize(
    "key, expected",
    [
        ("survival_complete", -9 / 25),
        ("survival_selected", 1 / 15),
        ("night_return", 1 / 50),
        ("session_return", -1 / 102),
        ("daily_return", 1 / 100),
        ("portfolio_a", -0.01),
        ("portfolio_b", 0.0584),
        ("portfolio_equal", 0.0296),
        ("execution_cost_dollars", 0.4),
        ("roundtrip_cost_share", 0.1),
        ("partial_target_dollars", 60),
        ("carry_before_funding", -0.034),
    ],
)
def test_worked_examples_match_hand_arithmetic(key: str, expected: float) -> None:
    """Les fractions et les montants attendus proviennent des exemples écrits."""
    assert teaching_examples()[key] == pytest.approx(expected)


def test_notebook_runs_in_order_without_network() -> None:
    """Le carnet importe les exemples du paquet et s'exécute dans un état neuf."""
    root = Path(__file__).resolve().parents[2]
    notebook = json.loads((root / "notebooks/01_comprendre_les_resultats.ipynb").read_text())
    scope = {}
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            exec("".join(cell["source"]), scope)

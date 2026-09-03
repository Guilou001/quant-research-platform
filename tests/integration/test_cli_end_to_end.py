"""La ligne de commande de bout en bout, hors réseau.

Trois commandes sont appelées comme un utilisateur le ferait, sur des fichiers
écrits par le test. Les valeurs attendues sont calculées à la main dans le
test, jamais copiées de la sortie du code.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from quantlab.cli import app

runner = CliRunner()


def _ecrire_cas(tmp_path: Path) -> tuple[Path, Path]:
    poids = tmp_path / "poids.csv"
    rendements = tmp_path / "rendements.csv"
    poids.write_text("date,A,B\n2020-01-31,0.6,0.4\n2020-02-29,0.6,0.4\n2020-03-31,0.6,0.4\n")
    rendements.write_text("date,A,B\n2020-01-31,0.0,0.0\n2020-02-29,0.10,-0.05\n2020-03-31,0.02,0.01\n")
    return poids, rendements


def test_info_repond() -> None:
    resultat = runner.invoke(app, ["info"])
    assert resultat.exit_code == 0, resultat.output
    assert "quantlab" in resultat.output.lower() or "version" in resultat.output.lower()


def test_backtest_rend_le_rendement_moyen_calcule_a_la_main(tmp_path: Path) -> None:
    """Janvier sans position, février 0,6 × 10 % − 0,4 × 5 % = 4 %, mars 0,6 × 2 % + 0,4 × 1 % = 1,6 %.

    Le décalage d'exécution vaut une période : la cible du 31 janvier est
    détenue en février. La moyenne des trois périodes vaut (0 + 0,04 + 0,016) / 3.
    """
    poids, rendements = _ecrire_cas(tmp_path)
    sortie = tmp_path / "resume.json"
    resultat = runner.invoke(app, ["backtest", str(poids), str(rendements), "--out", str(sortie)])
    assert resultat.exit_code == 0, resultat.output
    resume = json.loads(sortie.read_text())
    assert resume["n_periods"] == 3
    assert resume["gross_mean"] == pytest.approx((0.0 + 0.04 + 0.016) / 3)
    assert resume["net_mean"] == pytest.approx(resume["gross_mean"])
    assert resume["cost_total"] == 0.0


def test_backtest_facture_le_cout_declare(tmp_path: Path) -> None:
    """À 100 points de base par unité négociée, entrer 0,6 + 0,4 = 1,0 unité coûte 1 % en février."""
    poids, rendements = _ecrire_cas(tmp_path)
    sortie = tmp_path / "resume.json"
    resultat = runner.invoke(
        app, ["backtest", str(poids), str(rendements), "--spread-bps", "100", "--out", str(sortie)]
    )
    assert resultat.exit_code == 0, resultat.output
    resume = json.loads(sortie.read_text())
    assert resume["cost_total"] > 0.0
    assert resume["net_mean"] < resume["gross_mean"]
    # La première transaction, en février, négocie exactement une unité.
    assert resume["cost_total"] >= 0.01 - 1e-12


def test_portfolio_equipondere_rend_un_demi_par_actif(tmp_path: Path) -> None:
    rendements = tmp_path / "rendements.csv"
    lignes = ["date,A,B"] + [
        f"2020-{m:02d}-28,{0.01 * ((m % 3) - 1):.4f},{0.02 * ((m % 2) - 0.5):.4f}" for m in range(1, 13)
    ]
    rendements.write_text("\n".join(lignes) + "\n")
    sortie = tmp_path / "poids.csv"
    resultat = runner.invoke(
        app, ["portfolio", str(rendements), "--method", "equal_weight", "--out", str(sortie)]
    )
    assert resultat.exit_code == 0, resultat.output
    contenu = sortie.read_text().strip().splitlines()
    valeurs = {ligne.split(",")[0]: float(ligne.split(",")[1]) for ligne in contenu[1:]}
    assert valeurs == {"A": pytest.approx(0.5), "B": pytest.approx(0.5)}

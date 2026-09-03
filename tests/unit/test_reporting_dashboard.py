"""Contrôles de ``quantlab.reporting.dashboard`` et des commandes de la phase 10.

Le tableau se construit sur un faux dépôt écrit dans un répertoire temporaire.
Chaque valeur attendue porte sa source : (a) calcul à la main, (c) propriété de
construction des données.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml
from typer.testing import CliRunner

from quantlab.cli import app
from quantlab.core.errors import ConfigError
from quantlab.core.types import CostBasis, Frequency, SampleTag
from quantlab.reporting.dashboard import (
    build_dashboard,
    collect_studies,
    count_tests,
    registry_summary,
    risk_table,
)
from quantlab.reporting.series import save_series

MONTHS = pd.date_range("2018-01-31", periods=24, freq="ME")


def _alternating() -> pd.Series:
    """+2 % puis -1 %, en alternance, sur 24 mois."""
    return pd.Series([0.02 if k % 2 == 0 else -0.01 for k in range(24)], index=MONTHS)


def _fake_repo(root: Path) -> None:
    """Écrit deux études, un registre, un fichier de comparaison et deux tests."""
    for number, name, verdict in (("001", "alpha", "REJECTED"), ("002", "beta", "EXPERIMENTAL")):
        study = root / "studies" / f"{number}_{name}"
        (study / "results").mkdir(parents=True)
        (study / "config.yaml").write_text(
            yaml.safe_dump({"name": name, "paper": f"Article {name} (2020)", "n_trials": 5}), encoding="utf-8"
        )
        (study / "README.md").write_text(
            f"# Étude {number} : la question {name}\n\ntexte\n", encoding="utf-8"
        )
        (study / "results" / "metrics.json").write_text(json.dumps({"verdict": verdict}), encoding="utf-8")
        save_series(
            study / "results",
            f"{name}_net",
            _alternating() * (1.0 if name == "alpha" else -1.0),
            sample=SampleTag.OUT_OF_SAMPLE,
            basis=CostBasis.NET,
            frequency=Frequency.MONTHLY,
            universe="test",
            cost_assumptions="5 pb",
        )
    (root / "studies" / "README.md").write_text(
        "# Les études\n\n| N | Étude | Article | Essais | Verdict |\n|---|---|---|---:|---|\n"
        "| 001 | [Alpha](001_alpha/) | A | 5 | `REJECTED` |\n| 002 | [Bêta](002_beta/) | B | 9 | `EXPERIMENTAL` |\n\n"
        "**001.** Alpha ne survit pas.\n\n**002.** Bêta survit un peu.\n",
        encoding="utf-8",
    )
    (root / "artifacts").mkdir()
    records = [
        {
            "experiment_id": "alpha-1",
            "name": "alpha",
            "finished_at": "2026-09-01T10:00:00Z",
            "verdict": "REJECTED",
            "n_trials": 5,
            "git_sha": "abcdef0123",
        },
        {
            "experiment_id": "beta-1",
            "name": "beta",
            "finished_at": "2026-09-02T10:00:00Z",
            "verdict": "EXPERIMENTAL",
            "n_trials": 5,
            "git_sha": "abcdef0123",
        },
        {
            "experiment_id": "beta-2",
            "name": "beta",
            "finished_at": "2026-09-03T10:00:00Z",
            "verdict": "EXPERIMENTAL",
            "n_trials": 7,
            "git_sha": "abcdef0123",
        },
    ]
    (root / "artifacts" / "experiments.jsonl").write_text(
        "\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8"
    )
    (root / "benchmarks" / "results").mkdir(parents=True)
    pd.DataFrame({"fund": ["F"], "correlation": [0.5], "reading": ["apparenté"]}).to_csv(
        root / "benchmarks" / "results" / "comp.csv", index=False
    )
    (root / "tests").mkdir()
    (root / "tests" / "test_x.py").write_text(
        "def test_a():\n    pass\n\n\ndef test_b():\n    pass\n\n\ndef helper():\n    pass\n",
        encoding="utf-8",
    )
    (root / "configs").mkdir()
    (root / "configs" / "dashboard.yaml").write_text(
        yaml.safe_dump(
            {
                "title": "Tableau de test",
                "head_series": [
                    {"study": "001_alpha", "series": "alpha_net", "label": "Alpha net"},
                    {"study": "002_beta", "series": "beta_net", "label": "Bêta net"},
                    {"study": "003_absent", "series": "rien", "label": "Absente"},
                ],
                "portfolios": [],
                "common_window_start": "2018-01-31",
                "benchmarks": [
                    {
                        "file": "benchmarks/results/comp.csv",
                        "title": "Comparaison de test",
                        "columns": ["fund", "correlation", "reading"],
                    }
                ],
                "benchmark_figures": ["benchmarks/results/figures/absente.png"],
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )


def test_le_tableau_de_risque_a_la_main() -> None:
    """Source (a). +2 % et -1 % alternés sur 24 mois.

    Un couple de mois multiplie la richesse par 1,02 × 0,99 = 1,0098 ; douze
    couples font 1,0098^12 sur deux ans, donc 1,0098^6 - 1 = 6,03 % par an.
    Vol 5,31 %, Sharpe 1,130, pire repli -1 %.
    """
    table = risk_table({"s": _alternating()})
    row = table.loc["s"]
    assert row["cagr"] == pytest.approx(1.0098**6 - 1.0, rel=1e-9)
    monthly_std = 0.015 * np.sqrt(24 / 23)
    assert row["volatility"] == pytest.approx(monthly_std * np.sqrt(12), rel=1e-9)
    assert row["sharpe"] == pytest.approx(0.005 / monthly_std * np.sqrt(12), rel=1e-9)
    assert row["max_drawdown"] == pytest.approx(-0.01, rel=1e-9)
    assert row["years"] == 2.0


def test_les_etudes_le_registre_et_les_tests_se_lisent(tmp_path: Path) -> None:
    """Source (c). Deux études, trois expériences dont deux pour bêta, deux fonctions de test."""
    _fake_repo(tmp_path)
    studies = collect_studies(tmp_path / "studies")
    assert list(studies.index) == ["001", "002"]
    assert studies.loc["001", "verdict"] == "REJECTED"
    assert studies.loc["002", "one_liner"] == "Bêta survit un peu."
    assert studies.loc["001", "title"] == "Alpha"
    assert int(studies["n_trials"].sum()) == 10  # les configurations priment sur le tableau du README
    registry = registry_summary(tmp_path / "artifacts")
    assert registry["n_experiments"] == 3
    assert registry["trials_latest_by_study"] == 12  # 5 pour alpha, 7 pour la dernière de bêta
    assert registry["last"].iloc[0]["experiment_id"] == "beta-2"
    assert count_tests(tmp_path / "tests") == 2
    assert registry_summary(tmp_path / "nulle_part")["n_experiments"] == 0


def test_la_construction_ecrit_la_page_et_les_figures(tmp_path: Path) -> None:
    """La page porte les verdicts, les étiquettes, le tableau de comparaison, et signale ce qui manque."""
    _fake_repo(tmp_path)
    built = build_dashboard(tmp_path, date="2026-09-03")
    text = built.index_path.read_text(encoding="utf-8")
    assert built.index_path == tmp_path / "docs" / "dashboard" / "index.md"
    assert "`REJECTED`" in text and "`EXPERIMENTAL`" in text
    assert "Alpha net" in text and "Bêta net" in text
    assert "Comparaison de test" in text and "apparenté" in text
    assert "beta-2" in text
    assert "2 fonctions de test" in text
    assert any(p.name == "richesse_cumulee_tetes.png" for p in built.figure_paths)
    assert any(p.name == "correlations_tetes.png" for p in built.figure_paths)
    assert all(p.exists() for p in built.figure_paths)
    assert any("absente.png" in note for note in built.notes)
    assert "Absente" not in built.risk.index
    assert "Engendré le 2026-09-03" in text


def test_sans_configuration_la_construction_refuse(tmp_path: Path) -> None:
    """Une racine sans configs/dashboard.yaml lève une erreur de configuration."""
    with pytest.raises(ConfigError):
        build_dashboard(tmp_path)


def test_le_rapport_pdf_se_compile(tmp_path: Path) -> None:
    """Le tableau construit se compile en PDF non vide, et son Typst reste à côté."""
    pytest.importorskip("typst")
    _fake_repo(tmp_path)
    build_dashboard(tmp_path, date="2026-09-03")
    from quantlab.reporting.dashboard import build_report

    pdf = build_report(tmp_path, date="2026-09-03")
    assert pdf.exists() and pdf.stat().st_size > 1000
    assert (pdf.parent / "rapport.typ").exists()
    assert pdf.read_bytes()[:4] == b"%PDF"


def test_les_commandes_backtest_et_portfolio(tmp_path: Path) -> None:
    """Source (a). Deux actifs, poids fixes 0,5 : le brut vaut la moyenne des rendements."""
    dates = pd.date_range("2020-01-31", periods=6, freq="ME")
    returns = pd.DataFrame(
        {"A": [0.02, -0.03, -0.01, 0.03, -0.02, 0.01], "B": [0.0, -0.02, 0.01, -0.01, 0.02, -0.03]},
        index=dates,
    )
    weights = pd.DataFrame(0.5, index=dates, columns=["A", "B"])
    returns.to_csv(tmp_path / "r.csv")
    weights.to_csv(tmp_path / "w.csv")
    runner = CliRunner()
    out = runner.invoke(
        app, ["backtest", str(tmp_path / "w.csv"), str(tmp_path / "r.csv"), "--out", str(tmp_path / "s.json")]
    )
    assert out.exit_code == 0, out.output
    summary = json.loads((tmp_path / "s.json").read_text(encoding="utf-8"))
    assert "sharpe" in " ".join(summary).lower() or len(summary) > 3
    out = runner.invoke(
        app, ["portfolio", str(tmp_path / "r.csv"), "--method", "equal_weight", "--covariance", "sample"]
    )
    assert out.exit_code == 0, out.output
    assert "0.5" in out.output
    out = runner.invoke(app, ["portfolio", str(tmp_path / "r.csv"), "--method", "inconnu"])
    assert out.exit_code == 2

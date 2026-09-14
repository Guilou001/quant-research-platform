"""Publie le cours depuis des textes communs et des résultats déjà enregistrés.

Les exemples fictifs utilisent les fonctions du laboratoire. Les valeurs de
marché viennent des fichiers indiqués dans le registre éditorial. Aucun modèle
de placement n'est ajusté pendant la construction de la documentation.
"""

from __future__ import annotations

import hashlib
import json
import posixpath
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import norm, spearmanr

from quantlab.analytics.returns import compound
from quantlab.models.evaluation import oos_r2
from quantlab.validation.bootstrap import block_bootstrap

REPOSITORY = "https://github.com/Guilou001/quant-research-platform"
PLACEHOLDER = re.compile(r"\{\{([a-zA-Z0-9_]+)\}\}")


def teaching_examples() -> dict[str, Any]:
    """Calcule des exemples annoncés comme fictifs, avec des graines fixes.

    Les trois actions démontrent que précision et classement diffèrent. Les
    chemins normaux illustrent la sélection sous absence de signal. Les blocs
    conservent des mois voisins lors du rééchantillonnage d'une série fictive.
    Ces sorties ne décrivent aucune performance de marché.
    """
    realized = pd.Series([0.04, 0.03, 0.02], index=["A", "B", "C"])
    predicted = pd.Series([0.02, 0.03, 0.04], index=realized.index)
    seed = np.random.SeedSequence(20260913)
    search_seed, test_seed, block_seed = seed.spawn(3)
    search = np.random.default_rng(search_seed).normal(0.0, 0.04, size=(1000, 360))
    test = np.random.default_rng(test_seed).normal(0.0, 0.04, size=(1000, 360))
    # L'indice du gagnant dépend uniquement de la période de sélection.
    winner = int(np.argmax(search.mean(axis=1)))
    returns = np.array([-0.04, -0.03, -0.02, 0.01, 0.02, 0.03, -0.03, -0.02, 0.01, 0.02, 0.03, 0.04])
    draws = block_bootstrap(returns, 3, 2000, np.random.default_rng(block_seed))
    return {
        "forecast_r2": oos_r2(realized, predicted),
        "forecast_rank": float(spearmanr(realized, predicted).statistic),
        "forecast_squared_error": float(((realized - predicted) ** 2).sum()),
        "zero_squared_error": float((realized**2).sum()),
        "compound_gain_loss": float(compound(pd.Series([0.10, -0.10]))),
        "survival_complete": (120 + 110 + 90) / 500 - 1,
        "survival_selected": (120 + 110 + 90) / 300 - 1,
        "night_return": 102 / 100 - 1,
        "session_return": 101 / 102 - 1,
        "daily_return": float(compound(pd.Series([102 / 100 - 1, 101 / 102 - 1]))),
        "portfolio_a": float(compound(pd.Series([0.10, -0.10]))),
        "portfolio_b": float(compound(pd.Series([-0.02, 0.08]))),
        "portfolio_equal": float(compound(pd.Series([(0.10 - 0.02) / 2, (-0.10 + 0.08) / 2]))),
        "execution_cost_dollars": (200 + 200) * 0.001,
        "roundtrip_cost_share": 250 * 0.0004,
        "partial_target_dollars": 20 + 0.5 * (100 - 20),
        "carry_before_funding": 1.05 * 0.92 - 1,
        "false_positive_100": float(-np.expm1(100 * np.log1p(-0.05))),
        "winner": winner,
        "search_means": search.mean(axis=1).tolist(),
        "test_means": test.mean(axis=1).tolist(),
        "winner_search_mean": float(search[winner].mean()),
        "winner_test_mean": float(test[winner].mean()),
        "block_means": draws.mean(axis=1).tolist(),
        "block_interval": np.quantile(draws.mean(axis=1), [0.025, 0.975]).tolist(),
        "independent_threshold_100": float(norm.ppf(0.95 ** (1 / 100))),
    }


def format_value(value: Any, digits: int | None = None, scale: float = 1.0) -> str:
    """Formate les nombres en français sans changer leur unité implicite."""
    if digits is None:
        return str(value)
    if not np.isfinite(float(value)):
        raise ValueError("Une valeur non finie ne peut pas entrer dans le texte.")
    return f"{float(value) * scale:,.{digits}f}".replace(",", " ").replace(".", ",")


def load_values(root: Path) -> tuple[dict[str, str], dict[str, Any]]:
    """Lit chaque valeur avec sa source exacte et conserve les empreintes."""
    specifications = json.loads((root / "documentation/values.json").read_text())
    rendered: dict[str, str] = {}
    audit: dict[str, Any] = {}
    examples = teaching_examples()
    for name, spec in specifications.items():
        if spec["source"] == "teaching_examples":
            value = examples[spec["key"]]
            source = root / "src/quantlab/reporting/education.py"
        else:
            source = root / spec["source"]
            if source.suffix == ".json":
                value = json.loads(source.read_text())
                for key in spec["path"]:
                    value = value[key]
            else:
                frame = pd.read_csv(source)
                for column, expected in spec["where"].items():
                    frame = frame.loc[frame[column] == expected]
                if len(frame) != 1:
                    raise ValueError(f"Sélection ambiguë pour {name}, {len(frame)} lignes.")
                value = frame.iloc[0][spec["column"]]
        rendered[name] = format_value(value, spec.get("digits"), spec.get("scale", 1.0))
        audit[name] = {
            "source": source.relative_to(root).as_posix(),
            "selector": spec,
            "value": value.item() if isinstance(value, np.generic) else value,
            "rendered": rendered[name],
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        }
    return rendered, audit


def fill_template(text: str, values: dict[str, str]) -> str:
    """Refuse un champ absent au lieu de laisser un chiffre à compléter."""
    text = PLACEHOLDER.sub(lambda match: values[match[1]], text)
    if "{{" in text:
        raise ValueError("Champ éditorial non résolu.")
    return text


def resolve_links(text: str, destination: Path, *, web: bool) -> str:
    """Adapte les liens de la source commune au README ou au site."""

    def replace(match: re.Match[str]) -> str:
        """Résout un lien déclaré depuis l'emplacement du document publié."""
        target = match[1]
        if web and not target.startswith("docs/"):
            return "(" + REPOSITORY + "/blob/main/" + target + ")"
        relative = posixpath.relpath(target, destination.parent.as_posix())
        return "(" + relative + ")"

    return re.sub(r"\(repo:([^\)]+)\)", replace, text)


def publication_texts(root: Path) -> tuple[dict[Path, str], dict[str, Any]]:
    """Construit le site, les présentations d'étude et le manuscrit commun."""
    values, audit = load_values(root)
    outputs: dict[Path, str] = {}
    manuscript = [
        "# Comprendre et vérifier une recherche en finance\n",
        "Guillaume Vaudescal · 13 septembre 2026\n",
        "Un cours appliqué et vingt et une études à lire avec leurs hypothèses.\n",
        "Les exemples fictifs enseignent les calculs. Les études décrivent des résultats historiques.\n",
        "Version pédagogique. Les expériences initiales sont conservées dans les annexes techniques.\n",
    ]
    for folder, target_folder in [("chapters", "guide"), ("studies", "etudes")]:
        for source in sorted((root / "documentation" / folder).glob("*.md")):
            text = fill_template(source.read_text(), values)
            destination = Path("docs") / target_folder / source.name
            outputs[destination] = resolve_links(text, destination, web=True)
            if folder == "studies":
                readme = Path("studies") / source.stem / "README.md"
                outputs[readme] = resolve_links(text, readme, web=False)
            if source.stem != "index":
                # Les liens du manuel restent utilisables hors du site.
                book_text = re.sub(
                    r"(?<!!)\[([^\]]+)\]\(repo:([^\)]+)\)",
                    lambda m: f"[{m[1]}]({REPOSITORY}/blob/main/{m[2]})",
                    text,
                )
                book_text = resolve_links(book_text, Path("docs/manuel.md"), web=False)
                book_text = re.sub(r"^(#+) ", r"#\1 ", book_text, flags=re.M)
                manuscript.append(book_text)
    outputs[Path("docs/manuel.md")] = "\n\n".join(manuscript)
    studies = [
        (path.stem, fill_template(path.read_text(), values).splitlines()[0].removeprefix("# "))
        for path in sorted((root / "documentation/studies").glob("*.md"))
    ]
    catalogue = [
        "# Les vingt et une études",
        "",
        "Chaque présentation explique la question, un exemple fictif et les résultats historiques.",
        "Les annexes conservent les méthodes et les tableaux détaillés.",
        "",
        "| Étude | Question et résultat à explorer |",
        "|---|---|",
    ]
    for name, title in studies:
        catalogue.append(f"| {name[:3]} | [{title[4:]}]({name}.md) |")
    outputs[Path("docs/etudes/index.md")] = "\n".join(catalogue) + "\n"
    summaries = json.loads((root / "documentation/summaries.json").read_text())
    study_index = (root / "documentation/study_catalogue.md").read_text()
    study_index += "\n\n".join(
        f"**{number}.** {fill_template(text, values)}" for number, text in summaries.items()
    )
    study_index += (
        "\n\n## Refaire et documenter\n\n"
        "Chaque dossier contient un README guidé, une ANNEXE_TECHNIQUE et un script run.py.\n"
        "Les paramètres et les sorties gardent leur emplacement dans l'étude.\n"
        "Les textes éditoriaux communs se modifient dans documentation, puis se régénèrent avec make learn.\n"
    )
    outputs[Path("studies/README.md")] = study_index
    return outputs, audit


def build_learning(root: Path, *, check: bool = False) -> list[Path]:
    """Publie ou contrôle les textes sans recalculer les études historiques."""
    outputs, audit = publication_texts(root)
    outputs[Path("documentation/publication_values.json")] = (
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n"
    )
    stale = []
    for relative, text in outputs.items():
        path = root / relative
        if check:
            if not path.exists() or path.read_text() != text:
                stale.append(relative)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
    if stale:
        raise ValueError("Documents à régénérer " + ", ".join(map(str, stale)))
    if check:
        for manifest_path in ("docs/guide/figures/manifest.json", "rapport/manuel_manifest.json"):
            manifest = json.loads((root / manifest_path).read_text())
            for category in ("sources", "outputs"):
                for relative, expected in manifest[category].items():
                    if hashlib.sha256((root / relative).read_bytes()).hexdigest() != expected:
                        raise ValueError(f"Document ou source modifiée, régénérer la publication, {relative}")
    return list(outputs)

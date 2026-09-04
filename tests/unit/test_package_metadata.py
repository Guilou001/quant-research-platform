"""La version et l'adresse du dépôt n'existent qu'une fois, et les copies sont vérifiées.

La version vit dans ``pyproject.toml`` et le paquet la lit par ses métadonnées ;
``CITATION.cff`` la recopie, et ce test empêche la copie de prendre du retard.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import quantlab

RACINE = Path(__file__).resolve().parents[2]


def test_la_version_du_paquet_est_celle_du_pyproject() -> None:
    projet = tomllib.loads((RACINE / "pyproject.toml").read_text(encoding="utf-8"))
    assert quantlab.__version__ == projet["project"]["version"]


def test_citation_cff_porte_la_meme_version_et_la_meme_adresse() -> None:
    texte = (RACINE / "CITATION.cff").read_text(encoding="utf-8")
    version = re.search(r"^version:\s*(\S+)$", texte, flags=re.M)
    adresse = re.search(r'^repository-code:\s*"([^"]+)"$', texte, flags=re.M)
    assert version is not None and version.group(1) == quantlab.__version__
    assert adresse is not None and adresse.group(1) == quantlab.REPOSITORY_URL


def test_mkdocs_et_pyproject_pointent_sur_le_depot() -> None:
    projet = tomllib.loads((RACINE / "pyproject.toml").read_text(encoding="utf-8"))
    urls = projet["project"].get("urls", {})
    assert quantlab.REPOSITORY_URL in urls.values()
    mkdocs = (RACINE / "mkdocs.yml").read_text(encoding="utf-8")
    assert quantlab.REPOSITORY_URL in mkdocs

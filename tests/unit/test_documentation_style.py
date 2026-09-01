"""Les règles de prose, appliquées aux fichiers Markdown comme au code.

Le code est déjà tenu par ``test_architecture.py``. La documentation représente
la moitié de la valeur du dépôt, et rien ne la tenait. Ces quatre tests la
tiennent : typographie, lexique, longueur de phrase, et le gabarit des fiches de
littérature.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
DOCS = RACINE / "docs"

#: Les fichiers Markdown soumis aux règles de prose.
FICHIERS = sorted(
    [*DOCS.rglob("*.md"), RACINE / "README.md", RACINE / "CLAUDE.md", RACINE / "CONTRIBUTING.md"]
)

#: Le gabarit imposé aux fiches de littérature, dans cet ordre exact.
SECTIONS_LITTERATURE = [
    "## La question de recherche",
    "## L'intuition économique",
    "## Les données",
    "## L'univers",
    "## La méthodologie",
    "## Les équations qui comptent",
    "## Les résultats originaux",
    "## Les critiques connues",
    "## Les problèmes de réplication connus",
    "## Les biais possibles",
    "## Nos décisions d'implémentation",
    "## Nos écarts avec l'article",
    "## Nos résultats",
]

_LEXIQUE_PROSCRIT = (
    "il convient de noter",
    "force est de constater",
    "il est intéressant de noter",
    "au cœur de",
    "incontournable",
    "joue un rôle clé",
    "pierre angulaire",
    "s'inscrit dans une démarche",
    "plongeons dans",
    "penchons-nous sur",
    "n'hésitez pas à",
    "dans un monde où",
)


_ABREVIATIONS = ("p.", "pp.", "al.", "vol.", "no.", "fig.", "cf.", "env.", "etc.", "ex.", "art.")
_SENTINELLE = "\x00"


def _proteger_abreviations(texte: str) -> str:
    """Remplace le point des abréviations par une sentinelle avant le découpage.

    Sans cette protection, « p. 40 » et « et al. (2016) » coupent une phrase en
    deux, et le comptage des mots devient faux dans les deux sens.
    """
    for abrev in _ABREVIATIONS:
        texte = texte.replace(abrev, abrev[:-1] + _SENTINELLE)
    return texte


def _prose_blocks(texte: str) -> list[str]:
    """Rend les blocs de prose d'un Markdown, le reste retiré.

    Sont retirés les blocs de code, les tableaux, les blocs de formule, les
    titres et les listes. Toute ligne retirée ferme le bloc en cours, ce qui
    empêche deux fragments séparés par un tableau de se souder.
    """
    blocs: list[str] = []
    courant: list[str] = []
    dans_code = False
    dans_math = False

    def fermer() -> None:
        if courant:
            blocs.append(" ".join(courant))
            courant.clear()

    for ligne in texte.splitlines():
        nu = ligne.strip()
        if nu.startswith("```"):
            dans_code = not dans_code
            fermer()
            continue
        if dans_code:
            fermer()
            continue
        if nu.startswith("\\[") or nu.startswith("$$"):
            dans_math = True
        if dans_math:
            if nu.endswith("\\]") or (nu.endswith("$$") and len(nu) > 2):
                dans_math = False
            fermer()
            continue
        if not nu or nu.startswith(("#", "|", ">", "-", "*", "1.", "2.", "3.", "4.", "5.")):
            fermer()
            continue
        if "\\(" in ligne or "\\frac" in ligne or "\\sum" in ligne or "\\sqrt" in ligne:
            fermer()
            continue
        courant.append(nu)
    fermer()
    return blocs


@pytest.mark.parametrize("chemin", FICHIERS, ids=lambda p: str(p.relative_to(RACINE)))
def test_aucun_tiret_long(chemin: Path) -> None:
    """La typographie du portefeuille interdit le cadratin et le demi-cadratin."""
    fautifs = [
        f"ligne {i} : {ligne.strip()[:70]}"
        for i, ligne in enumerate(chemin.read_text(encoding="utf-8").splitlines(), start=1)
        if "—" in ligne or "–" in ligne
    ]
    assert not fautifs, f"{chemin.relative_to(RACINE)}\n" + "\n".join(fautifs)


@pytest.mark.parametrize("chemin", FICHIERS, ids=lambda p: str(p.relative_to(RACINE)))
def test_lexique(chemin: Path) -> None:
    """Les tournures de remplissage n'entrent pas dans la documentation."""
    texte = chemin.read_text(encoding="utf-8").lower()
    trouves = [mot for mot in _LEXIQUE_PROSCRIT if mot in texte]
    assert not trouves, f"{chemin.relative_to(RACINE)} contient : {trouves}"


@pytest.mark.parametrize("chemin", FICHIERS, ids=lambda p: str(p.relative_to(RACINE)))
def test_longueur_des_phrases(chemin: Path) -> None:
    """Aucune phrase de prose ne dépasse trente-cinq mots.

    La limite vient de ``METHODE.md``. Les formules, les tableaux et les blocs
    de code sont retirés avant le comptage : ce sont des objets, pas des
    phrases.
    """
    coupure = re.compile(r"(?<=[.!?])\s+")
    fautifs: list[str] = []
    for bloc in _prose_blocks(chemin.read_text(encoding="utf-8")):
        for phrase in coupure.split(_proteger_abreviations(bloc)):
            mots = phrase.split()
            if len(mots) > 35:
                fautifs.append(f"({len(mots)} mots) {phrase.replace(_SENTINELLE, '.')[:100]}")
    assert not fautifs, f"{chemin.relative_to(RACINE)}\n" + "\n".join(fautifs[:10])


LITTERATURE = sorted(p for p in (DOCS / "literature").glob("*.md") if p.name != "index.md")


@pytest.mark.parametrize("chemin", LITTERATURE, ids=lambda p: p.stem)
def test_gabarit_des_fiches(chemin: Path) -> None:
    """Chaque fiche de littérature porte les sections du gabarit, dans l'ordre.

    Le gabarit n'est pas un caprice de forme. Il garantit que la section « Les
    critiques connues » existe, donc qu'on a cherché les réfutations avant de
    répliquer, et que les sections « Nos ... » restent vides tant que l'étude
    n'a pas tourné.
    """
    texte = chemin.read_text(encoding="utf-8")
    positions: list[int] = []
    manquantes: list[str] = []
    for section in SECTIONS_LITTERATURE:
        idx = texte.find(section)
        if idx < 0:
            manquantes.append(section)
        else:
            positions.append(idx)
    assert not manquantes, f"{chemin.name} : sections manquantes {manquantes}"
    assert positions == sorted(positions), f"{chemin.name} : sections dans le désordre"

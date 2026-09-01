"""Les règles d'architecture, vérifiées mécaniquement plutôt que par vigilance.

Une règle qui repose sur l'attention d'un relecteur est une règle qui tiendra
jusqu'au jour où personne ne relit. Les six tests ci-dessous font tenir six
règles du ``CLAUDE.md`` sans relecture.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "quantlab"


def _modules(*subpackages: str) -> list[Path]:
    """Rend les fichiers Python des sous-paquets demandés, tests exclus."""
    roots = [SRC / s for s in subpackages] if subpackages else [SRC]
    out: list[Path] = []
    for root in roots:
        if root.exists():
            out.extend(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)
    return sorted(out)


def _imported_names(path: Path) -> set[str]:
    """Rend les modules importés par un fichier, en lisant son arbre syntaxique.

    La lecture syntaxique vaut mieux qu'une recherche textuelle : elle ignore
    les mentions d'un nom dans une docstring ou un commentaire, qui sont
    fréquentes dans ce dépôt puisque la documentation cite les bibliothèques.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _is_protocol_stub(node: ast.AST) -> bool:
    """Dit si le nœud est une méthode dont le corps se réduit à « ... »."""
    if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        return False
    corps = [n for n in node.body if not isinstance(n, ast.Expr) or not isinstance(n.value, ast.Constant)]
    if corps:
        return False
    return all(
        isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and n.value.value is Ellipsis
        for n in node.body
    )


_MARQUEURS_NON_PROSE = (
    ">>>",
    "...",
    "|",
    "$",
    ".. ",
    "- ",
    "* ",
    "+ ",
    "=",
    "#",
    "```",
    ":math:",
)
_SIGNES_LATEX = (
    "\\frac",
    "\\sum",
    "\\qquad",
    "\\sqrt",
    "\\left",
    "\\right",
    "\\mathbb",
    "\\times",
    "\\top",
    "\\Sigma",
    "_{",
    "^{",
    "\\alpha",
    "\\sigma",
    "\\lambda",
    "\\rho",
    "\\theta",
    "\\hat",
    "\\bar",
    "\\text",
    "\\underbrace",
    "\\mathcal",
    "\\approx",
    "\\le",
    "\\ge",
)


#: Les abréviations qui portent un point sans terminer une phrase. Sans cette
#: liste, « p. 40 » et « et al. (2016) » coupent une phrase en deux, et le
#: comptage des mots devient faux dans les deux sens.
_ABREVIATIONS = ("p.", "pp.", "al.", "vol.", "no.", "fig.", "cf.", "env.", "etc.", "ex.", "art.")
_SENTINELLE = "\x00"


def _proteger_abreviations(texte: str) -> str:
    """Remplace le point des abréviations par une sentinelle avant le découpage."""
    for abrev in _ABREVIATIONS:
        texte = texte.replace(abrev, abrev[:-1] + _SENTINELLE)
    return texte


def _prose_blocks(doc: str) -> list[str]:
    """Rend les blocs de prose d'une docstring, formules et tableaux retirés.

    Un bloc est une suite de lignes de texte. Toute ligne retirée ferme le bloc
    en cours, ce qui empêche deux fragments séparés par une formule de se
    souder en une phrase interminable.
    """
    blocs: list[str] = []
    courant: list[str] = []
    dans_math = False
    indent_math = 0

    def fermer() -> None:
        if courant:
            blocs.append(" ".join(courant))
            courant.clear()

    for ligne in doc.splitlines():
        nu = ligne.strip()
        if nu.startswith(".. math::"):
            dans_math = True
            indent_math = len(ligne) - len(ligne.lstrip())
            fermer()
            continue
        if dans_math:
            if nu == "" or len(ligne) - len(ligne.lstrip()) > indent_math:
                continue
            dans_math = False
        if not nu or nu.startswith(_MARQUEURS_NON_PROSE) or any(s in ligne for s in _SIGNES_LATEX):
            fermer()
            continue
        courant.append(nu)
    fermer()
    return blocs


def test_analytics_ne_connait_pas_polars() -> None:
    """L'analytique parle pandas, le lac parle Polars, et la frontière tient.

    C'est la règle d'ADR-001. Un import de Polars dans ``analytics`` signifie
    qu'une conversion a lieu au milieu d'un calcul, ce que l'architecture cherche
    précisément à éviter.
    """
    fautifs = [
        str(p.relative_to(SRC))
        for p in _modules("analytics")
        if any(n == "polars" or n.startswith("polars.") for n in _imported_names(p))
    ]
    assert not fautifs, f"ces modules d'analytique importent Polars : {fautifs}"


def test_la_recherche_ne_connait_pas_les_fournisseurs() -> None:
    """Aucune stratégie n'importe un fournisseur de données.

    C'est la règle d'ADR-003, et c'est elle qui rend ``YahooProvider``
    remplaçable. Un import direct la casse, quelle que soit l'intention.
    """
    interdits = ("quantlab.data.providers", "yfinance", "requests")
    fautifs: list[str] = []
    for p in _modules("strategies", "signals", "features", "portfolio", "risk", "models"):
        for n in _imported_names(p):
            if any(n == i or n.startswith(i + ".") for i in interdits):
                fautifs.append(f"{p.relative_to(SRC)} importe {n}")
    assert not fautifs, "\n".join(fautifs)


def test_aucun_print_dans_le_paquet() -> None:
    """Le journal structuré remplace ``print``, sans exception.

    Un ``print`` rend une ligne que personne ne peut filtrer ni rattacher à une
    expérience. La règle 59 du plan et le module ``core.logging`` existent pour
    cela.
    """
    fautifs: list[str] = []
    for p in _modules():
        tree = ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print":
                fautifs.append(f"{p.relative_to(SRC)}:{node.lineno}")
    assert not fautifs, f"appels à print() : {fautifs}"


def test_aucun_tiret_cadratin_dans_la_prose() -> None:
    """La convention typographique du portefeuille interdit les tirets longs.

    Le tiret cadratin et le demi-cadratin sont proscrits partout, y compris pour
    une incise. Virgules, parenthèses, ou deux phrases.
    """
    fautifs: list[str] = []
    for p in _modules():
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
            if "—" in line or "–" in line:
                fautifs.append(f"{p.relative_to(SRC)}:{i}: {line.strip()[:70]}")
    assert not fautifs, "tirets longs trouvés :\n" + "\n".join(fautifs)


@pytest.mark.parametrize(
    "mot",
    [
        "il convient de noter",
        "force est de constater",
        "au cœur de",
        "incontournable",
        "joue un rôle clé",
        "pierre angulaire",
        "s'inscrit dans une démarche",
        "plongeons dans",
        "penchons-nous sur",
    ],
)
def test_lexique_proscrit(mot: str) -> None:
    """Les tournures de remplissage n'entrent pas dans la documentation."""
    fautifs: list[str] = []
    for p in _modules():
        texte = p.read_text(encoding="utf-8").lower()
        if mot in texte:
            fautifs.append(str(p.relative_to(SRC)))
    assert not fautifs, f"« {mot} » trouvé dans : {fautifs}"


def test_toute_fonction_publique_est_documentee() -> None:
    """Une fonction publique sans docstring n'existe pas dans ce dépôt.

    La règle 3 du ``CLAUDE.md`` exige une documentation par formule importante.
    Ce test tient la version faible mais mécanique de la règle : au moins une
    docstring, sur toute fonction et toute classe dont le nom ne commence pas
    par un souligné.
    """
    fautifs: list[str] = []
    for p in _modules():
        tree = ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                if node.name.startswith("_"):
                    continue
                if _is_protocol_stub(node):
                    # Une méthode de Protocol dont le corps est « ... » est décrite
                    # par la docstring de son protocole ; l'exiger deux fois n'ajoute rien.
                    continue
                if ast.get_docstring(node) is None:
                    fautifs.append(f"{p.relative_to(SRC)}:{node.lineno} {node.name}")
    assert not fautifs, "sans docstring :\n" + "\n".join(fautifs)


def test_chaque_module_porte_une_docstring() -> None:
    """Un module sans docstring de tête ne dit pas quel problème il traite."""
    fautifs = [
        str(p.relative_to(SRC))
        for p in _modules()
        if ast.get_docstring(ast.parse(p.read_text(encoding="utf-8"))) is None
    ]
    assert not fautifs, f"modules sans docstring : {fautifs}"


def test_aucune_phrase_de_plus_de_trente_cinq_mots() -> None:
    """Les phrases de la documentation restent sous trente-cinq mots.

    La limite vient de ``METHODE.md``. Elle porte sur la prose seule : formules,
    tableaux et blocs de code sont retirés avant le comptage.
    """
    coupure = re.compile(r"(?<=[.!?])\s+")
    fautifs: list[str] = []
    for p in _modules():
        tree = ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
        docs = [ast.get_docstring(tree)]
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                docs.append(ast.get_docstring(node))
        for doc in filter(None, docs):
            for bloc in _prose_blocks(doc):
                for phrase in coupure.split(_proteger_abreviations(bloc)):
                    mots = phrase.split()
                    if len(mots) > 35:
                        propre = phrase.replace(_SENTINELLE, ".")
                        fautifs.append(f"{p.relative_to(SRC)} ({len(mots)} mots) : {propre[:90]}...")
    assert not fautifs, "phrases trop longues :\n" + "\n".join(fautifs[:20])

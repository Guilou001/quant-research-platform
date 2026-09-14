"""Compile le manuscrit commun en manuel paginé, avec un sommaire."""

import hashlib
import json
import re
from pathlib import Path

import typst
from gvf import markdown, rapport


def compile_manual(root: Path) -> Path:
    """Utilise le même convertisseur que le rapport existant du laboratoire."""
    text = (root / "docs/manuel.md").read_text()
    text = text.replace("Guillaume Vaudescal · 13 septembre 2026\n", "", 1)
    text = re.sub(r"!\[([^\]]*)\]\((?!https?://|/)([^)]+)\)", r"![\1](docs/\2)", text)
    document = markdown.convertir(text, racine="..")
    source = rapport.GABARIT.format(
        titre=markdown.chaine(document.titre),
        titre_affiche=markdown.ligne(document.titre),
        pied="Comprendre et vérifier une recherche en finance",
        date="13 septembre 2026",
        depot="https://github.com/Guilou001/quant-research-platform",
        depot_court="github.com/Guilou001/quant-research-platform",
        corps=document.corps,
    )
    # Chaque chapitre ou étude commence sur une nouvelle page.
    source = source.replace("leading: 0.68em, spacing: 1.1em", "leading: 0.46em, spacing: 0.75em")
    source = source.replace("margin: (x: 2.2cm, y: 2.4cm)", "margin: (x: 2.2cm, y: 2.1cm)")
    source = source.replace(
        "#set heading(numbering: none)",
        "#set heading(numbering: none)\n#show table: it => block(breakable: false, it)\n",
    )
    source = re.sub(r"^== ", "#pagebreak(weak: true)\n== ", source, flags=re.M)
    first_chapter = source.find("== 01 ")
    if first_chapter < 0:
        raise ValueError("Le premier chapitre est absent du manuscrit Typst.")
    source = (
        source[:first_chapter]
        + "#pagebreak()\n#outline(title: [Parcours de lecture], depth: 2)\n#pagebreak()\n"
        + source[first_chapter:]
    )
    destination = root / "rapport/manuel.pdf"
    typ_path = destination.with_suffix(".typ")
    typ_path.parent.mkdir(parents=True, exist_ok=True)
    typ_path.write_text(source)
    destination.write_bytes(typst.compile(typ_path, root=root))
    sources = ["docs/manuel.md", "scripts/learning_pdf.py"]
    sources += sorted(
        path.relative_to(root).as_posix() for path in (root / "docs/guide/figures").glob("*.png")
    )
    manifest = {
        "sources": {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in sources},
        "outputs": {
            path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (destination, typ_path)
        },
    }
    destination.with_name("manuel_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return destination

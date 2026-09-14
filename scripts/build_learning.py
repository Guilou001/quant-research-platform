"""Construit les textes du cours et, sur demande, leurs figures et leur PDF."""

import argparse
from pathlib import Path

from quantlab.reporting.education import build_learning


def main() -> None:
    """Expose une construction hors réseau et une vérification sans écriture."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--figures", action="store_true")
    parser.add_argument("--pdf", action="store_true")
    args = parser.parse_args()
    if args.check and (args.figures or args.pdf):
        parser.error("--check ne produit aucun fichier")
    root = Path(__file__).resolve().parents[1]
    paths = build_learning(root, check=args.check)
    if args.figures:
        from learning_figures import draw_all

        draw_all(root)
    if args.pdf:
        from learning_pdf import compile_manual

        compile_manual(root)
    print(f"{len(paths)} documents {'vérifiés' if args.check else 'écrits'}")


if __name__ == "__main__":
    main()

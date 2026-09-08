"""Draw the README figure from published results, without rerunning the study.

Run from the repository with ``uv run python scripts/figure_presentation.py``.
The input tables remain the numerical source of truth.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FuncFormatter

ROOT = Path(__file__).resolve().parents[1]
BLUE, ORANGE, GREEN, GREY = "#176B96", "#C56628", "#14816D", "#718096"
plt.rcParams.update(
    {
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "font.family": "DejaVu Sans",
        "font.size": 11,
        "axes.titlesize": 15,
        "axes.labelsize": 11,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.edgecolor": "#CBD5E0",
        "text.color": "#172B3A",
        "axes.labelcolor": "#172B3A",
        "xtick.color": "#425466",
        "ytick.color": "#425466",
        "axes.axisbelow": True,
    }
)


def number(value, decimals=2):
    return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")


def finish(fig, axes, title, note, path="results/figures/presentation.png"):
    for ax in np.asarray(axes, dtype=object).ravel():
        ax.grid(axis="x", color="#EDF0F3", linewidth=0.8)
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:g}".replace(".", ",")))
    fig.suptitle(title, x=0.02, ha="left", fontweight="bold", fontsize=16)
    fig.text(0.02, 0.015, note, ha="left", va="bottom", fontsize=9, color="#526575")
    fig.tight_layout(rect=(0, 0.075, 1, 0.91))
    destination = ROOT / path
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main():
    import json

    p = ROOT / "studies/016_publication_decay_212/results/metrics.json"
    summary = json.loads(p.read_text())["pooled"]["post_publication"]
    n = int(summary["n_predictors"])
    lower = round(n * summary["share_declining"])
    fig, ax = plt.subplots(figsize=(10, 3.6))
    ax.barh([0], [lower], color=BLUE, height=0.5)
    ax.barh([0], [n - lower], left=[lower], color=GREY, height=0.5)
    ax.text(
        lower / 2,
        0,
        f"{lower} baissent",
        ha="center",
        va="center",
        color="white",
        fontsize=15,
        fontweight="bold",
    )
    ax.text(
        lower + (n - lower) / 2,
        0,
        f"{n - lower} ne\nbaissent pas",
        ha="center",
        va="center",
        color="white",
        fontsize=10,
    )
    ax.set_xlim(0, n)
    ax.set_yticks([])
    ax.set_xlabel("Nombre de portefeuilles comparables")
    finish(
        fig,
        [ax],
        f"Après publication, le rendement baisse dans {lower} cas sur {n}",
        "Étude 016 · actions américaines · rendements avant "
        "frais · fenêtres propres à chaque article, données 1926–2024\n"
        "Comparaison descriptive. Elle ne permet pas d'attribuer la baisse à la publication.",
        path="docs/figures/presentation_publication.png",
    )


if __name__ == "__main__":
    main()

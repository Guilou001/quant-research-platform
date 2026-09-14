"""Dessine les exemples du cours et les résultats conservés, sur fond blanc."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter

from quantlab.reporting.education import load_values, teaching_examples

BLUE, ORANGE, TEAL, GREY = "#176B96", "#C56628", "#14816D", "#718096"


def draw_all(root: Path) -> None:
    """Produit huit figures avec des unités et conserve leurs empreintes."""
    directory = root / "docs/guide/figures"
    directory.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.edgecolor": "#CBD5E0",
            "text.color": "#172B3A",
            "axes.labelcolor": "#172B3A",
            "axes.axisbelow": True,
            "svg.hashsalt": "quantlab-education-20260913",
        }
    )
    _, audit = load_values(root)
    values = {key: float(spec["value"]) for key, spec in audit.items()}
    examples = teaching_examples()
    outputs: list[Path] = []

    def finish(fig, axes, name: str, title: str, note: str) -> None:
        """Écrit deux formats vectoriel et matriciel depuis la même figure."""
        for ax in np.asarray(axes, dtype=object).ravel():
            ax.grid(axis="x", color="#EDF0F3")
            ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:g}".replace(".", ",")))
        fig.suptitle(title, x=0.035, ha="left", fontsize=17, weight="bold")
        fig.text(0.035, 0.018, note, color="#526575", fontsize=9, va="bottom")
        fig.tight_layout(rect=(0.01, 0.11, 0.99, 0.88))
        for extension in ("png", "svg"):
            destination = directory / f"{name}.{extension}"
            metadata = {"Date": None} if extension == "svg" else {}
            fig.savefig(destination, dpi=170, facecolor="white", metadata=metadata)
            if extension == "svg":
                normalized = "\n".join(line.rstrip() for line in destination.read_text().splitlines())
                destination.write_text(normalized + "\n")
            outputs.append(destination)
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4.8))
    y = np.arange(3)
    ax.barh(y + 0.18, [2, 3, 4], height=0.32, label="Prévu", color=BLUE)
    ax.barh(y - 0.18, [4, 3, 2], height=0.32, label="Observé", color=ORANGE)
    ax.set_yticks(y, ["Action A", "Action B", "Action C"])
    ax.invert_yaxis()
    ax.set(xlim=(0, 5), xlabel="Rendement excédentaire mensuel en pourcentage")
    ax.legend(frameon=False, loc="lower right")
    finish(
        fig,
        ax,
        "prevision_classement",
        "Des niveaux proches, des préférences inversées",
        "Exemple fictif · trois actions, un mois · R² de 72,4 % contre la prévision nulle\n"
        "Le modèle préfère C, mais A réalise le meilleur rendement.",
    )

    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.barh([0, 1], [64, 106.6666666667], height=0.48, color=[ORANGE, BLUE])
    ax.set_yticks([0, 1], ["Les cinq entreprises", "Les trois survivantes seulement"])
    ax.invert_yaxis()
    ax.axvline(100, color=GREY, ls="--")
    ax.set(xlim=(0, 128), xlabel="Capital final pour 100 dollars fictifs au départ")
    for y, value in enumerate([64, 106.6666666667]):
        ax.text(value + 2, y, f"{value:.2f} $".replace(".", ","), va="center")
    finish(
        fig,
        ax,
        "survie_exemple",
        "Oublier deux pertes change la lecture du passé",
        "Exemple fictif · même mise initiale par entreprise · une période, sans frais\n"
        "Les cinq placements de 100 dollars deviennent 120, 110, 90, 0 et 0 dollars.",
    )

    fig, ax = plt.subplots(figsize=(10, 4.4))
    for y, left, width, label, color in [
        (2, 2010, 8, "Apprendre", BLUE),
        (1, 2018, 2, "Choisir", TEAL),
        (0, 2020, 3, "Évaluer", ORANGE),
    ]:
        ax.barh(y, width, left=left, color=color, height=0.5)
        ax.text(left + width / 2, y, label, color="white", ha="center", va="center", weight="bold")
    ax.set_yticks([])
    ax.set_xticks([2010, 2014, 2018, 2020, 2023])
    ax.set(xlim=(2009.5, 2023.5), xlabel="Année, frontières au début de l'année indiquée")
    finish(
        fig,
        ax,
        "calendrier",
        "Trois périodes pour trois rôles différents",
        "Calendrier fictif · paramètres retenus avant la période finale\n"
        "Une cible qui chevauche la frontière demande une purge adaptée à son horizon.",
    )

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), sharex=True)
    for ax, key, winner_key, label in zip(
        axes,
        ["search_means", "test_means"],
        ["winner_search_mean", "winner_test_mean"],
        ["Période de sélection", "Nouvelle période indépendante"],
        strict=True,
    ):
        ax.hist(np.array(examples[key]) * 100, bins=30, color=BLUE, alpha=0.8)
        ax.axvline(examples[winner_key] * 100, color=ORANGE, lw=2, label="Gagnant choisi au départ")
        ax.axvline(0, color=GREY, ls=":")
        ax.set(title=label, xlabel="Moyenne mensuelle en pourcentage", ylabel="Nombre de séries")
        ax.legend(frameon=False, fontsize=8)
    finish(
        fig,
        axes,
        "selection_hasard",
        "Le meilleur tirage n'a pas reçu un avantage",
        "Simulation fictive · 1 000 séries indépendantes · 360 mois par période\n"
        "Rendements normaux de moyenne zéro et de dispersion 4 % par mois · graine 20260913",
    )

    fig, ax = plt.subplots(figsize=(10, 4.8))
    means = np.array(examples["block_means"]) * 100
    low, high = np.array(examples["block_interval"]) * 100
    ax.hist(means, bins=25, color=BLUE, alpha=0.85)
    ax.axvline(0, color=ORANGE, lw=2, label="Moyenne nulle")
    for endpoint in (low, high):
        ax.axvline(endpoint, color=TEAL, ls="--")
    ax.set(xlabel="Moyenne mensuelle rééchantillonnée en pourcentage", ylabel="Nombre de tirages")
    ax.legend(frameon=False)
    finish(
        fig,
        ax,
        "bootstrap",
        "Les rééchantillonnages ne donnent pas une seule moyenne",
        "Exemple fictif · douze mois · blocs circulaires de trois mois · 2 000 tirages\n"
        "Pointillés verts aux quantiles 2,5 % et 97,5 % · illustration, sans garantie de couverture",
    )

    table_path = root / "studies/016_publication_decay_212/results/tables/windows.csv"
    frame = pd.read_csv(table_path)
    ratios = frame.set_index("predictor")["post_publication_return_ratio"].dropna() * 100
    central = ratios.between(-100, 200)
    extreme = ratios.loc[~central].sort_values()
    fig, axes = plt.subplots(1, 2, figsize=(12, 8.3), gridspec_kw={"width_ratios": [1.3, 1]})
    axes[0].scatter(ratios[central].sort_values(), np.arange(central.sum()), color=BLUE, s=15, alpha=0.7)
    axes[0].set(title=f"{central.sum()} valeurs entre -100 et 200 %", ylabel="Portefeuilles triés")
    axes[1].scatter(extreme, np.arange(len(extreme)), color=ORANGE, s=28)
    references = frame.set_index("predictor")
    labels = []
    for identifier in extreme.index:
        row = references.loc[identifier]
        author = str(row["authors"]).split(",")[0].split(" and ")[0].split(" et al.")[0]
        labels.append(f"{author} et coll. ({int(row['publication_year'])})")
    axes[1].set_yticks(np.arange(len(extreme)), labels)
    axes[1].tick_params(axis="y", labelsize=8)
    axes[1].set(title=f"{len(extreme)} valeurs hors de cette plage")
    for ax in axes:
        ax.axvline(100, color=GREY, ls="--")
        ax.set_xlabel("Part du rendement moyen conservée en pourcentage", fontsize=9)
    finish(
        fig,
        axes,
        "publication_distribution",
        f"Après publication, {len(ratios)} rapports à regarder ensemble",
        "Étude 016 · actions américaines · rendements bruts · "
        "fenêtres propres aux articles, données 1926 à 2024\n"
        "Aucune valeur écrêtée · à droite, références abrégées des stratégies · 100 % signifie aucune baisse",
    )

    fig, ax = plt.subplots(figsize=(10, 4.8))
    keys = ["s018_night", "s018_day", "s018_residual", "s018_total"]
    numbers = [values[k] for k in keys]
    # Le registre conserve déjà ces quatre valeurs en pourcentage annuel.
    ax.barh(range(4), numbers, color=[BLUE, ORANGE, GREY, TEAL], height=0.5)
    ax.set_yticks(range(4), ["Nuit", "Séance", "Résidu", "Total excédentaire"])
    ax.invert_yaxis()
    ax.axvline(0, color=GREY)
    ax.set(xlim=(-5, 13), xlabel="Rendement moyen annualisé en pourcentage")
    for y, value in enumerate(numbers):
        ax.text(
            value + (0.2 if value >= 0 else -0.2),
            y,
            f"{value:.2f}".replace(".", ","),
            ha="left" if value >= 0 else "right",
            va="center",
        )
    finish(
        fig,
        ax,
        "nuit_journee",
        "La nuit et la séance ne s'additionnent pas seules",
        "Étude 018 · 28 fonds · janvier 2007 à juin 2026 · avant frais\n"
        "Résidu conservé · composition et convention du taux sans risque à lire dans l'étude",
    )

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    axes[0].barh([1, 0], [values["s021_sharpe"], values["s021_single"]], color=[BLUE, GREY], height=0.45)
    axes[0].set_yticks([1, 0], ["Portefeuille", "Meilleure composante"])
    axes[0].set(xlim=(0, 0.9), xlabel="Ratio de Sharpe annualisé", title="Même fenêtre de 187 mois")
    axes[1].barh([0], [values["s021_t"]], color=TEAL, height=0.45)
    axes[1].axvline(3, color=ORANGE, ls="--", label="Seuil déclaré de 3")
    axes[1].set(
        yticks=[], xlim=(0, 3.6), ylim=(-0.7, 0.7), xlabel="Statistique t", title="Période finale de 78 mois"
    )
    axes[1].legend(frameon=False, fontsize=9)
    finish(
        fig,
        axes,
        "verdict_portefeuille",
        "Un résultat positif peut manquer le critère retenu",
        "Étude 021 · trois composantes · décembre 2010 à juin 2026 · coûts modélisés inclus\n"
        "Période finale de janvier 2020 à juin 2026 · "
        "seuils du protocole, sans test d'égalité des deux Sharpes",
    )

    sources = {spec["source"] for spec in audit.values()} | {
        "scripts/learning_figures.py",
        "documentation/values.json",
        table_path.relative_to(root).as_posix(),
    }
    manifest = {
        "sources": {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in sorted(sources)},
        "outputs": {
            path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in outputs
        },
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

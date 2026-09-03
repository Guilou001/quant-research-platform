"""Phase 9, étape 3 : la réconciliation des deux moteurs, mois par mois.

Le script relit la valeur liquidative que l'algorithme LEAN a journalisée,
en tire les rendements mensuels, retranche le terme de financement qui sépare
un rendement total d'un rendement excédentaire, et compare le résultat à la
série du laboratoire calculée sur les mêmes entrées. Il compare aussi les
décisions elles-mêmes, poids par poids, et il vérifie sur les exécutions à
quel prix LEAN a réellement rempli chaque ordre. Tout écart est mesuré ; le
rapport ``lean/README.md`` dit lequel est expliqué et par quoi.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from quantlab.analytics.ratios import sharpe_ratio
from quantlab.analytics.visualization.figures import equity_curve, save_figure
from quantlab.backtest.lean_bridge import (
    monthly_returns_from_values,
    parse_portfolio_value_log,
    reconcile_monthly,
)
from quantlab.core.types import Frequency

RACINE = Path(__file__).resolve().parent
ENTREES = RACINE / "data" / "inputs"
TABLES = RACINE / "results" / "tables"
FIGURES = RACINE / "results" / "figures"
MONTHLY = Frequency.MONTHLY
# Seuil déclaré avant la première lecture : au-delà, un mois est un écart à expliquer.
SEUIL_ECART_MENSUEL = 1e-4


def _lire_journal(variante: int) -> str:
    chemin = RACINE / "data" / f"results_delai_{variante}" / "TsmomControl-log.txt"
    return chemin.read_text(encoding="utf-8")


def _decisions_lean(journal: str) -> pd.DataFrame:
    """Relit les lignes DECISION : date, nombre d'instruments, poids cibles."""
    lignes: dict[pd.Timestamp, dict[str, float]] = {}
    comptes: dict[pd.Timestamp, int] = {}
    for ligne in journal.splitlines():
        position = ligne.find("DECISION,")
        if position < 0:
            continue
        champs = ligne[position + len("DECISION,") :].strip().split(",", 2)
        date = pd.Timestamp(champs[0]).to_period("M").to_timestamp("M")
        comptes[date] = int(champs[1])
        poids = {}
        if len(champs) > 2 and champs[2]:
            for morceau in champs[2].split(";"):
                symbole, valeur = morceau.split(":")
                poids[symbole] = float(valeur)
        lignes[date] = poids
    tableau = pd.DataFrame(lignes).T.sort_index().fillna(0.0)
    tableau.attrs["counts"] = pd.Series(comptes).sort_index()
    return tableau


def _prix_de_remplissage(variante: int, prix: pd.DataFrame) -> dict[str, Any]:
    """Compare chaque prix d'exécution de LEAN aux clôtures des jours voisins."""
    chemin = RACINE / "data" / f"results_delai_{variante}" / "TsmomControl-order-events.json"
    evenements = json.loads(chemin.read_text(encoding="utf-8"))
    remplis = [e for e in evenements if e.get("status") == "filled"]
    dates_seances = prix.index
    veille_exacte = 0
    jour_exact = 0
    autre = 0
    exemples: list[dict[str, Any]] = []
    for e in remplis:
        symbole = str(e["symbol"]).split(" ")[0]
        instant = pd.Timestamp(float(e["time"]), unit="s", tz="UTC").tz_convert("America/New_York")
        jour = pd.Timestamp(instant.date())
        if jour not in dates_seances or symbole not in prix.columns:
            autre += 1
            continue
        position = dates_seances.get_loc(jour)
        cloture_jour = float(prix.iloc[position][symbole])
        cloture_veille = float(prix.iloc[position - 1][symbole]) if position > 0 else float("nan")
        remplissage = float(e["fillPrice"])
        if abs(remplissage - cloture_veille) < 1.5e-4:
            veille_exacte += 1
        elif abs(remplissage - cloture_jour) < 1.5e-4:
            jour_exact += 1
        else:
            autre += 1
            if len(exemples) < 5:
                exemples.append(
                    {
                        "symbol": symbole,
                        "fill_day": str(jour.date()),
                        "fill_price": remplissage,
                        "close_previous_day": cloture_veille,
                        "close_fill_day": cloture_jour,
                    }
                )
    return {
        "n_fills": len(remplis),
        "n_fills_at_previous_close": veille_exacte,
        "n_fills_at_same_day_close": jour_exact,
        "n_fills_elsewhere": autre,
        "examples_elsewhere": exemples,
        "first_fill_time_new_york": str(
            pd.Timestamp(float(remplis[0]["time"]), unit="s", tz="UTC").tz_convert("America/New_York")
        )
        if remplis
        else None,
    }


def _resume(tableau: pd.DataFrame) -> dict[str, Any]:
    ecart = tableau["difference"]
    return {
        "n_months": len(tableau),
        "first_month": str(tableau.index.min().date()),
        "last_month": str(tableau.index.max().date()),
        "max_abs_difference": float(ecart.abs().max()),
        "mean_difference": float(ecart.mean()),
        "rms_difference": float(np.sqrt((ecart**2).mean())),
        "n_months_above_threshold": int((ecart.abs() > SEUIL_ECART_MENSUEL).sum()),
        "threshold": SEUIL_ECART_MENSUEL,
        "correlation": float(tableau["lab"].corr(tableau["lean_excess"])),
        "sharpe_lab": float(sharpe_ratio(tableau["lab"], frequency=MONTHLY)),
        "sharpe_lean_excess": float(sharpe_ratio(tableau["lean_excess"], frequency=MONTHLY)),
        "sharpe_lean_total": float(sharpe_ratio(tableau["lean_total"], frequency=MONTHLY)),
        "wealth_lab": float((1.0 + tableau["lab"]).prod()),
        "wealth_lean_excess": float((1.0 + tableau["lean_excess"]).prod()),
        "annual_return_lab_pct": float(((1.0 + tableau["lab"]).prod() ** (12 / len(tableau)) - 1) * 100),
        "annual_return_lean_excess_pct": float(
            ((1.0 + tableau["lean_excess"]).prod() ** (12 / len(tableau)) - 1) * 100
        ),
        "financing_mean_annual_pct": float(tableau["financing"].mean() * 12 * 100),
    }


def main() -> None:
    """Réconcilie la variante de base, puis celle retardée d'une séance si elle existe."""
    TABLES.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    prix = pd.read_parquet(ENTREES / "prices.parquet")
    lab = pd.read_csv(TABLES / "lab_monthly_gross.csv", index_col="date", parse_dates=True)["lab_gross"]
    financement = pd.read_csv(TABLES / "lab_financing.csv", index_col="date", parse_dates=True)["financing"]
    cibles_lab = pd.read_csv(TABLES / "lab_target_weights.csv", index_col="date", parse_dates=True)

    metriques: dict[str, Any] = {"threshold_monthly": SEUIL_ECART_MENSUEL}
    tableaux: dict[int, pd.DataFrame] = {}
    for variante in (0, 1):
        try:
            journal = _lire_journal(variante)
        except FileNotFoundError:
            metriques[f"delay_{variante}"] = "non exécuté"
            continue
        valeurs = parse_portfolio_value_log(journal)
        valeurs.to_csv(TABLES / f"lean_portfolio_value_delay_{variante}.csv", index_label="date")
        mensuel = monthly_returns_from_values(valeurs)
        # Le premier mois avec position est février 2007 ; janvier 2007 vaut zéro
        # des deux côtés, et il est gardé pour que les deux séries aient 234 mois.
        mensuel = mensuel.loc[lab.index.min() :]
        tableau = reconcile_monthly(lab, mensuel, financement)
        tableau.to_csv(TABLES / f"reconciliation_monthly_delay_{variante}.csv", index_label="date")
        tableaux[variante] = tableau
        resume = _resume(tableau)
        resume["fills"] = _prix_de_remplissage(variante, prix)

        decisions = _decisions_lean(journal)
        communes = decisions.index.intersection(cibles_lab.index)
        colonnes = cibles_lab.columns
        ecart_poids = (
            decisions.reindex(communes).reindex(columns=colonnes).fillna(0.0) - cibles_lab.loc[communes]
        ).abs()
        comptes_lab = (cibles_lab.loc[communes].abs() > 0).sum(axis=1)
        comptes_lean = decisions.attrs["counts"].reindex(communes)
        resume["decisions"] = {
            "n_decision_dates_common": len(communes),
            "n_decision_dates_lean": len(decisions),
            "max_abs_weight_difference": float(ecart_poids.max().max()),
            "mean_abs_weight_difference": float(ecart_poids.mean().mean()),
            "n_dates_instrument_count_differs": int((comptes_lab != comptes_lean).sum()),
            "n_sign_disagreements": int(
                (
                    np.sign(decisions.reindex(communes).reindex(columns=colonnes).fillna(0.0))
                    != np.sign(cibles_lab.loc[communes])
                )
                .sum()
                .sum()
            ),
        }
        pd.DataFrame(
            {
                "lab_instruments": comptes_lab,
                "lean_instruments": comptes_lean,
                "max_abs_weight_difference": ecart_poids.max(axis=1),
            }
        ).to_csv(TABLES / f"decisions_delay_{variante}.csv", index_label="date")
        metriques[f"delay_{variante}"] = resume

    if 0 in tableaux and 1 in tableaux:
        base, retard = tableaux[0], tableaux[1]
        communs = base.index.intersection(retard.index)
        cout = base.loc[communs, "lean_excess"] - retard.loc[communs, "lean_excess"]
        metriques["one_day_delay"] = {
            "n_months": len(communs),
            "annual_return_base_pct": float(
                ((1 + base.loc[communs, "lean_excess"]).prod() ** (12 / len(communs)) - 1) * 100
            ),
            "annual_return_delayed_pct": float(
                ((1 + retard.loc[communs, "lean_excess"]).prod() ** (12 / len(communs)) - 1) * 100
            ),
            "mean_monthly_cost_bps": float(cout.mean() * 1e4),
            "sharpe_base": float(sharpe_ratio(base.loc[communs, "lean_excess"], frequency=MONTHLY)),
            "sharpe_delayed": float(sharpe_ratio(retard.loc[communs, "lean_excess"], frequency=MONTHLY)),
            "correlation": float(base.loc[communs, "lean_excess"].corr(retard.loc[communs, "lean_excess"])),
        }

    (RACINE / "results" / "metrics.json").write_text(
        json.dumps(metriques, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )

    if 0 in tableaux:
        base = tableaux[0]
        series = {
            "Laboratoire, brut, excédentaire": base["lab"],
            "LEAN, après retrait du financement": base["lean_excess"],
        }
        if 1 in tableaux:
            series["LEAN, ordres retardés d'une séance"] = tableaux[1]["lean_excess"]
        fig, _ = equity_curve(
            series,
            log_scale=False,
            currency="$",
            title="Le même momentum de série temporelle dans les deux moteurs, 2007 à 2026",
        )
        save_figure(fig, FIGURES / "richesse_deux_moteurs")
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(10, 3.8))
        ax.bar(base.index, base["difference"] * 1e4, width=20, color="#0072B2")
        ax.axhline(0, color="black", linewidth=0.6)
        ax.set_ylabel("LEAN moins laboratoire, points de base")
        ax.set_title("Écart mensuel entre les deux moteurs après retrait du financement")
        fig.tight_layout()
        save_figure(fig, FIGURES / "ecart_mensuel")
        plt.close(fig)

    print(json.dumps({k: v for k, v in metriques.items()}, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()

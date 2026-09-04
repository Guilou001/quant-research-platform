"""Phase 9, étape 3 : la réconciliation des deux moteurs, mois par mois.

Le script relit la valeur liquidative que l'algorithme LEAN a journalisée pour
chaque variante trouvée dans ``lean/data/results_*``, en tire les rendements
mensuels, retranche le terme de financement qui sépare un rendement total d'un
rendement excédentaire, et compare le résultat à la série du laboratoire
calculée sur les mêmes entrées. Il compare aussi les décisions elles-mêmes,
poids par poids, et vérifie sur les exécutions à quel prix LEAN a rempli chaque
ordre. Tout écart est mesuré ; le rapport ``lean/README.md`` dit lequel est
expliqué et par quoi.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from gvf.style import OKABE_ITO
from matplotlib.figure import Figure

from quantlab.analytics.ratios import sharpe_ratio
from quantlab.analytics.returns import cagr, cumulative_wealth
from quantlab.analytics.visualization.figures import equity_curve, portfolio_style, save_figure
from quantlab.backtest.lean_bridge import (
    monthly_returns_from_values,
    parse_portfolio_value_log,
    reconcile_monthly,
)
from quantlab.core.errors import DataQualityError
from quantlab.core.types import Frequency

RACINE = Path(__file__).resolve().parent
ENTREES = RACINE / "data" / "inputs"
TABLES = RACINE / "results" / "tables"
FIGURES = RACINE / "results" / "figures"
MONTHLY = Frequency.MONTHLY
BASE = "delai_0"
#: Seuil déclaré avant la première lecture : au-delà, un mois est un écart à expliquer.
SEUIL_ECART_MENSUEL = 1e-4
#: Tolérance sur un prix d'exécution, la moitié du dix-millième de dollar de LEAN plus l'arrondi.
TOLERANCE_PRIX = 1.5e-4
LIBELLES = {
    "delai_0": "LEAN, ordres à la fin de mois, ouverture égale à la clôture de la veille",
    "delai_1": "LEAN, ordres retardés d'une séance",
    "realopen_delai_0": "LEAN, ordres à la fin de mois, ouverture réelle du lendemain",
}


def _variantes() -> list[str]:
    """Les variantes exécutées, lues sur le disque, la base en premier."""
    noms = sorted(p.name.removeprefix("results_") for p in (RACINE / "data").glob("results_*") if p.is_dir())
    if BASE in noms:
        noms.remove(BASE)
        noms.insert(0, BASE)
    return noms


def _journal(variante: str) -> str:
    return (RACINE / "data" / f"results_{variante}" / "TsmomControl-log.txt").read_text(encoding="utf-8")


def _decisions_lean(journal: str) -> tuple[pd.DataFrame, pd.Series]:
    """Relit les lignes DECISION : poids cibles par date, et nombre d'instruments."""
    poids: dict[pd.Timestamp, dict[str, float]] = {}
    comptes: dict[pd.Timestamp, int] = {}
    for ligne in journal.splitlines():
        position = ligne.find("DECISION,")
        if position < 0:
            continue
        champs = ligne[position + len("DECISION,") :].strip().split(",", 2)
        date = pd.Timestamp(champs[0]).to_period("M").to_timestamp("M")
        comptes[date] = int(champs[1])
        cibles = {}
        if len(champs) > 2 and champs[2]:
            for morceau in champs[2].split(";"):
                symbole, valeur = morceau.split(":")
                cibles[symbole] = float(valeur)
        poids[date] = cibles
    return pd.DataFrame(poids).T.sort_index().fillna(0.0), pd.Series(comptes).sort_index()


def _prix_de_remplissage(variante: str, prix: pd.DataFrame, ouvertures: pd.DataFrame) -> dict[str, Any]:
    """Compare chaque prix d'exécution de LEAN aux clôtures voisines et à l'ouverture réelle."""
    chemin = RACINE / "data" / f"results_{variante}" / "TsmomControl-order-events.json"
    evenements = json.loads(chemin.read_text(encoding="utf-8"))
    remplis = pd.DataFrame([e for e in evenements if e.get("status") == "filled"])
    if remplis.empty:
        return {"n_fills": 0}
    remplis["symbol"] = remplis["symbol"].astype(str).str.split(" ").str[0]
    instants = pd.to_datetime(remplis["time"].astype(float), unit="s", utc=True).dt.tz_convert(
        "America/New_York"
    )
    jours = pd.DatetimeIndex(instants.dt.tz_localize(None).dt.normalize())
    positions = prix.index.get_indexer(jours)
    colonnes = prix.columns.get_indexer(remplis["symbol"])
    valides = (positions > 0) & (colonnes >= 0)
    valeurs = prix.to_numpy()
    cloture_jour = np.full(len(remplis), np.nan)
    cloture_veille = np.full(len(remplis), np.nan)
    ouverture_jour = np.full(len(remplis), np.nan)
    cloture_jour[valides] = valeurs[positions[valides], colonnes[valides]]
    cloture_veille[valides] = valeurs[positions[valides] - 1, colonnes[valides]]
    ouverture_jour[valides] = ouvertures.to_numpy()[positions[valides], colonnes[valides]]
    remplissage = remplis["fillPrice"].astype(float).to_numpy()
    a_la_veille = np.abs(remplissage - cloture_veille) < TOLERANCE_PRIX
    au_jour = np.abs(remplissage - cloture_jour) < TOLERANCE_PRIX
    a_l_ouverture = np.abs(remplissage - ouverture_jour) < TOLERANCE_PRIX
    return {
        "n_fills": len(remplis),
        "n_fills_at_previous_close": int(a_la_veille.sum()),
        "n_fills_at_same_day_close": int((au_jour & ~a_la_veille).sum()),
        "n_fills_at_real_open": int(a_l_ouverture.sum()),
        "n_fills_elsewhere": int((~a_la_veille & ~au_jour & ~a_l_ouverture).sum()),
        "first_fill_time_new_york": str(instants.iloc[0]),
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
        "wealth_lab": float(cumulative_wealth(tableau["lab"]).iloc[-1]),
        "wealth_lean_excess": float(cumulative_wealth(tableau["lean_excess"]).iloc[-1]),
        "annual_return_lab_pct": float(cagr(tableau["lab"], MONTHLY)) * 100,
        "annual_return_lean_excess_pct": float(cagr(tableau["lean_excess"], MONTHLY)) * 100,
        "financing_mean_annual_pct": float(tableau["financing"].mean() * 12 * 100),
    }


def _comparer_decisions(journal: str, cibles_lab: pd.DataFrame) -> tuple[dict[str, Any], pd.DataFrame]:
    decisions, comptes_lean = _decisions_lean(journal)
    communes = decisions.index.intersection(cibles_lab.index)
    lean_al = decisions.reindex(communes).reindex(columns=cibles_lab.columns).fillna(0.0)
    lab_al = cibles_lab.loc[communes]
    ecart_poids = (lean_al - lab_al).abs()
    comptes_lab = (lab_al.abs() > 0).sum(axis=1)
    resume = {
        "n_decision_dates_lab": len(cibles_lab),
        "n_decision_dates_lean": len(decisions),
        "n_decision_dates_common": len(communes),
        "max_abs_weight_difference": float(ecart_poids.max().max()),
        "mean_abs_weight_difference": float(ecart_poids.mean().mean()),
        "n_dates_instrument_count_differs": int((comptes_lab != comptes_lean.reindex(communes)).sum()),
        "n_sign_disagreements": int((np.sign(lean_al) != np.sign(lab_al)).sum().sum()),
    }
    table = pd.DataFrame(
        {
            "lab_instruments": comptes_lab,
            "lean_instruments": comptes_lean.reindex(communes),
            "max_abs_weight_difference": ecart_poids.max(axis=1),
        }
    )
    return resume, table


def main() -> None:
    """Réconcilie chaque variante trouvée, la base d'abord, puis mesure ce que les autres coûtent."""
    TABLES.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    prix = pd.read_parquet(ENTREES / "prices.parquet")
    ouvertures = pd.read_parquet(ENTREES / "opens.parquet")
    lab = pd.read_csv(TABLES / "lab_monthly_gross.csv", index_col="date", parse_dates=True)["lab_gross"]
    financement = pd.read_csv(TABLES / "lab_financing.csv", index_col="date", parse_dates=True)["financing"]
    cibles_lab = pd.read_csv(TABLES / "lab_target_weights.csv", index_col="date", parse_dates=True)

    variantes = _variantes()
    if BASE not in variantes:
        raise DataQualityError(f"la variante de base {BASE} n'a pas été exécutée.")
    metriques: dict[str, Any] = {"threshold_monthly": SEUIL_ECART_MENSUEL, "variants": variantes}
    tableaux: dict[str, pd.DataFrame] = {}
    for variante in variantes:
        journal = _journal(variante)
        valeurs = parse_portfolio_value_log(journal)
        valeurs.to_csv(TABLES / f"lean_portfolio_value_{variante}.csv", index_label="date")
        mensuel = monthly_returns_from_values(valeurs).loc[lab.index.min() :]
        tableau = reconcile_monthly(lab, mensuel, financement)
        tableau.to_csv(TABLES / f"reconciliation_monthly_{variante}.csv", index_label="date")
        tableaux[variante] = tableau
        resume = _resume(tableau)
        resume["label"] = LIBELLES.get(variante, variante)
        resume["n_lab_months_not_reconciled"] = len(lab.index.difference(tableau.index))
        resume["fills"] = _prix_de_remplissage(variante, prix, ouvertures)
        resume["decisions"], table_decisions = _comparer_decisions(journal, cibles_lab)
        table_decisions.to_csv(TABLES / f"decisions_{variante}.csv", index_label="date")
        metriques[variante] = resume

    base = tableaux[BASE]
    for variante, tableau in tableaux.items():
        if variante == BASE:
            continue
        communs = base.index.intersection(tableau.index)
        base_x = base.loc[communs, "lean_excess"]
        autre_x = tableau.loc[communs, "lean_excess"]
        metriques[f"{variante}_versus_base"] = {
            "n_months": len(communs),
            "annual_return_base_pct": float(cagr(base_x, MONTHLY)) * 100,
            "annual_return_variant_pct": float(cagr(autre_x, MONTHLY)) * 100,
            "mean_monthly_cost_bps": float((base_x - autre_x).mean() * 1e4),
            "sharpe_base": float(sharpe_ratio(base_x, frequency=MONTHLY)),
            "sharpe_variant": float(sharpe_ratio(autre_x, frequency=MONTHLY)),
            "correlation": float(base_x.corr(autre_x)),
        }

    texte = json.dumps(metriques, indent=2, ensure_ascii=False, default=str)
    (RACINE / "results" / "metrics.json").write_text(texte, encoding="utf-8")

    debut, fin = base.index.min().year, base.index.max().year
    series = {"Laboratoire, brut, excédentaire": base["lab"]}
    for variante, tableau in tableaux.items():
        series[LIBELLES.get(variante, variante)] = tableau["lean_excess"]
    fig, _ = equity_curve(
        series,
        log_scale=False,
        currency="$",
        title=f"Le même momentum de série temporelle dans les deux moteurs, {debut} à {fin}",
    )
    save_figure(fig, FIGURES / "richesse_deux_moteurs")

    with portfolio_style():
        fig = Figure(figsize=(10, 3.8))
        ax = fig.add_subplot(111)
        ax.bar(base.index, base["difference"] * 1e4, width=20, color=OKABE_ITO[0])
        ax.axhline(0, color="black", linewidth=0.6)
        ax.set_ylabel("LEAN moins laboratoire, points de base")
        ax.set_title(f"Écart mensuel entre les deux moteurs après retrait du financement, {debut} à {fin}")
        fig.tight_layout()
        save_figure(fig, FIGURES / "ecart_mensuel")

    print(texte)


if __name__ == "__main__":
    main()

"""Phase 9, étape 2 : la série du laboratoire sur les entrées communes.

Le script rejoue la jambe B de l'étude 001 avec les fonctions du laboratoire,
sur les prix exportés par ``export_inputs.py`` plutôt que sur un nouveau
téléchargement. Il écrit la série mensuelle brute, les poids exécutés et le
terme de financement qui sépare un rendement excédentaire d'un rendement
total. C'est cette série que LEAN doit retrouver.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from quantlab.backtest.engine import run_backtest
from quantlab.core.config import ExperimentConfig, load_config
from quantlab.core.types import Frequency
from quantlab.strategies.time_series_momentum import ex_ante_volatility, tsmom_weights

RACINE = Path(__file__).resolve().parent
ETUDE = RACINE.parent / "studies" / "001_time_series_momentum"
ENTREES = RACINE / "data" / "inputs"
TABLES = RACINE / "results" / "tables"


def main() -> None:
    """Rejoue l'étude 001 sur les entrées communes et écrit sa série."""
    config = load_config(ETUDE / "config.yaml", ExperimentConfig)
    p = config.params
    TABLES.mkdir(parents=True, exist_ok=True)

    prix = pd.read_parquet(ENTREES / "prices.parquet")
    rf_quotidien = pd.read_csv(ENTREES / "rf_daily.csv", index_col="date", parse_dates=True)["rf"]
    rf_mensuel = pd.read_csv(ENTREES / "rf_monthly.csv", index_col="date", parse_dates=True)["rf"]

    rendements = prix.pct_change()
    taux = rf_quotidien.reindex(rendements.index).ffill()
    exces_quotidiens = rendements.sub(taux, axis=0)
    volatilite = ex_ante_volatility(
        exces_quotidiens,
        center_of_mass=float(p["volatility_center_of_mass_days"]),
        annualization_days=float(p["volatility_annualization_days"]),
        min_periods=int(p["volatility_min_periods_days"]),
    )
    cle = [rendements.index.year, rendements.index.month]
    dernieres = pd.DatetimeIndex(sorted(rendements.index.to_series().groupby(cle).max().to_numpy()))
    fins = pd.DatetimeIndex(dernieres.to_period("M").to_timestamp("M"))
    seances = rendements.notna().groupby(cle).sum().set_axis(fins)
    mensuel_brut = ((1.0 + rendements).groupby(cle).prod() - 1.0).set_axis(fins)
    mensuel_brut = mensuel_brut.where(seances >= int(p["min_trading_days_per_month"]))
    taux_mensuel = rf_mensuel.reindex(fins, method="ffill")
    exces_mensuels = mensuel_brut.sub(taux_mensuel, axis=0)
    volatilite_mensuelle = volatilite.reindex(dernieres).set_axis(fins)

    debut = p["backtest_start"]
    poids = tsmom_weights(
        exces_mensuels,
        volatilite_mensuelle,
        lookback=int(p["lookback_months"]),
        holding=int(p["holding_months"]),
        target_volatility=float(p["target_volatility"]),
    ).loc[debut:]
    resultat = run_backtest(
        weights=poids,
        returns=exces_mensuels.loc[debut:].fillna(0.0),
        cost_model=None,
        execution_lag=1,
        frequency=Frequency.MONTHLY,
    )
    brut = resultat.gross_returns.rename("lab_gross")
    executes = resultat.executed_weights
    financement = (executes.sum(axis=1) * taux_mensuel.reindex(executes.index)).rename("financing")

    brut.to_csv(TABLES / "lab_monthly_gross.csv", index_label="date")
    executes.to_csv(TABLES / "lab_executed_weights.csv", index_label="date")
    financement.to_csv(TABLES / "lab_financing.csv", index_label="date")
    poids.to_csv(TABLES / "lab_target_weights.csv", index_label="date")
    volatilite_mensuelle.loc[debut:].to_csv(TABLES / "lab_monthly_volatility.csv", index_label="date")

    publiee = pd.read_csv(
        ETUDE / "results" / "series" / "tsmom_etf_gross.csv", index_col="date", parse_dates=True
    )["value"]
    communs = brut.index.intersection(publiee.index)
    ecart = (brut.reindex(communs) - publiee.reindex(communs)).abs()
    resume = {
        "n_months": len(brut),
        "first_month": str(brut.index.min().date()),
        "last_month": str(brut.index.max().date()),
        "n_months_common_with_published": len(communs),
        "max_abs_gap_vs_published": float(ecart.max()),
        "mean_abs_gap_vs_published": float(ecart.mean()),
        "n_months_gap_above_1e-6": int((ecart > 1e-6).sum()),
        "n_decisions_with_positions": int((poids.abs().sum(axis=1) > 0).sum()),
        "gross_leverage_mean": float(executes.abs().sum(axis=1).mean()),
        "gross_leverage_max": float(executes.abs().sum(axis=1).max()),
    }
    (TABLES / "lab_reference_summary.json").write_text(json.dumps(resume, indent=2))
    print(json.dumps(resume, indent=2))


if __name__ == "__main__":
    main()

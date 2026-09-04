"""Phase 9, étape 1 : les entrées communes aux deux moteurs.

Le script télécharge une seule fois les prix des vingt-huit fonds cotés de
l'étude 001 et le taux sans risque de Kenneth French, puis il les écrit sous
trois formes. La première, ``lean/data/inputs/``, est celle que le moteur du
laboratoire relit. La deuxième, ``lean/data/lean/``, est celle que LEAN lit,
avec pour chaque jour une ouverture égale à la clôture de la veille, si bien
que LEAN exécute au prix que le laboratoire suppose. La troisième,
``lean/data/lean_realopen/``, porte l'ouverture réelle de Yahoo, ajustée par le
même facteur que la clôture, si bien que LEAN exécute au prix que le marché
donnait le lendemain. Les paramètres de la stratégie sont écrits à côté des
données, dans ``custom/params.json``, et l'algorithme les lit là : rien n'est
recopié à la main dans son code.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from quantlab.backtest.lean_bridge import write_lean_daily_zip
from quantlab.core.config import ExperimentConfig, load_config
from quantlab.core.logging import get_logger
from quantlab.core.types import Frequency
from quantlab.data.providers.french import FrenchProvider
from quantlab.data.providers.yahoo import YahooProvider, to_wide

RACINE = Path(__file__).resolve().parent
ETUDE = RACINE.parent / "studies" / "001_time_series_momentum" / "config.yaml"
ENTREES = RACINE / "data" / "inputs"
LEAN_DATA = RACINE / "data" / "lean"
LEAN_DATA_REAL_OPEN = RACINE / "data" / "lean_realopen"
_LOG = get_logger(__name__)


def _parametres(config: ExperimentConfig) -> dict[str, object]:
    """Ce que l'algorithme LEAN doit savoir, lu dans la configuration de l'étude 001."""
    p = config.params
    return {
        "universe": list(config.data.universe),
        "start": str(config.data.start),
        "end": str(config.data.end),
        "first_trade_date": str(p["backtest_start"]),
        "lookback_months": int(p["lookback_months"]),
        "target_volatility": float(p["target_volatility"]),
        "volatility_center_of_mass_days": float(p["volatility_center_of_mass_days"]),
        "volatility_annualization_days": float(p["volatility_annualization_days"]),
        "volatility_min_periods_days": int(p["volatility_min_periods_days"]),
        "min_trading_days_per_month": int(p["min_trading_days_per_month"]),
    }


def main() -> None:
    """Télécharge, écrit les trois formes, et publie le décompte des trous."""
    config = load_config(ETUDE, ExperimentConfig)
    ENTREES.mkdir(parents=True, exist_ok=True)
    for dossier in (LEAN_DATA, LEAN_DATA_REAL_OPEN):
        (dossier / "custom").mkdir(parents=True, exist_ok=True)

    yahoo = YahooProvider()
    brut = yahoo.fetch(config.data.universe, start=config.data.start, end=config.data.end, on_missing="drop")
    prix = to_wide(brut, config.data.price_field).reindex(columns=config.data.universe)
    volume = to_wide(brut, "volume").reindex(columns=config.data.universe)
    # L'ouverture réelle, ajustée par le facteur qui relie la clôture ajustée à la clôture brute.
    facteur = prix / to_wide(brut, "close").reindex(columns=config.data.universe)
    ouvertures = to_wide(brut, "open").reindex(columns=config.data.universe) * facteur
    prix.to_parquet(ENTREES / "prices.parquet")
    volume.to_parquet(ENTREES / "volume.parquet")
    ouvertures.to_parquet(ENTREES / "opens.parquet")

    french = FrenchProvider()
    quotidien = french.benchmark_factors(frequency=Frequency.DAILY, start=config.data.start)["RF"]
    mensuel = french.benchmark_factors(frequency=Frequency.MONTHLY, start=config.params["aqr_start"])["RF"]
    parametres = _parametres(config)
    for dossier in (ENTREES, LEAN_DATA / "custom", LEAN_DATA_REAL_OPEN / "custom"):
        quotidien.rename("rf").to_csv(dossier / "rf_daily.csv", index_label="date")
        mensuel.rename("rf").to_csv(dossier / "rf_monthly.csv", index_label="date")
        (dossier / "params.json").write_text(json.dumps(parametres, indent=2))

    trous: dict[str, int] = {}
    premiers: dict[str, str] = {}
    ouvertures_absentes: dict[str, int] = {}
    for symbole in config.data.universe:
        serie = prix[symbole]
        premier = serie.first_valid_index()
        if premier is None:
            continue
        premiers[symbole] = str(premier.date())
        trous[symbole] = int(serie.loc[premier:].isna().sum())
        write_lean_daily_zip(LEAN_DATA, symbole, serie, volume[symbole])
        ouverture = ouvertures[symbole].loc[premier:]
        # Une ouverture absente ou nulle chez Yahoo prend la clôture de la veille,
        # la convention synthétique, et le compte est publié.
        manquantes = ouverture.isna() | (ouverture <= 0)
        ouvertures_absentes[symbole] = int(manquantes.sum())
        ouverture = ouverture.where(~manquantes, serie.loc[premier:].shift(1)).fillna(serie.loc[premier])
        write_lean_daily_zip(LEAN_DATA_REAL_OPEN, symbole, serie, volume[symbole], opens=ouverture)

    # Les deux bases de référence de LEAN, copiées d'un jeu à l'autre si elles existent déjà.
    for nom in ("market-hours", "symbol-properties"):
        source = LEAN_DATA / nom
        cible = LEAN_DATA_REAL_OPEN / nom
        if source.is_dir() and not cible.is_dir():
            shutil.copytree(source, cible)

    resume = {
        "n_symbols": int(prix.notna().any().sum()),
        "first_date": str(prix.index.min().date()),
        "last_date": str(prix.index.max().date()),
        "n_union_dates": len(prix),
        "interior_gaps_by_symbol": trous,
        "interior_gaps_total": int(sum(trous.values())),
        "real_opens_missing_by_symbol": ouvertures_absentes,
        "real_opens_missing_total": int(sum(ouvertures_absentes.values())),
        "first_price_by_symbol": premiers,
        "rf_daily_span": [str(quotidien.index.min().date()), str(quotidien.index.max().date())],
        "rf_monthly_span": [str(mensuel.index.min().date()), str(mensuel.index.max().date())],
        "params": parametres,
        "yahoo_manifest": yahoo.manifest().model_dump(mode="json"),
    }
    (ENTREES / "summary.json").write_text(json.dumps(resume, indent=2, ensure_ascii=False))
    _LOG.info(
        "entrées LEAN écrites",
        extra={"n_symbols": resume["n_symbols"], "interior_gaps": resume["interior_gaps_total"]},
    )
    print(
        json.dumps(
            {k: v for k, v in resume.items() if k not in ("yahoo_manifest", "first_price_by_symbol")},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

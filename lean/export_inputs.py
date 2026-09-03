"""Phase 9, étape 1 : les entrées communes aux deux moteurs.

Le script télécharge une seule fois les prix des vingt-huit fonds cotés de
l'étude 001 et le taux sans risque de Kenneth French, puis il les écrit sous
deux formes. La première, ``lean/data/inputs/``, est celle que le moteur du
laboratoire relira ; la seconde, ``lean/data/lean/``, est celle que LEAN lit.
Les deux moteurs voient donc exactement les mêmes nombres, et tout écart entre
eux vient de leur façon de calculer, jamais d'une révision de Yahoo entre deux
téléchargements.
"""

from __future__ import annotations

import json
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
_LOG = get_logger(__name__)


def main() -> None:
    """Télécharge, écrit les deux formes, et publie le décompte des trous."""
    config = load_config(ETUDE, ExperimentConfig)
    ENTREES.mkdir(parents=True, exist_ok=True)
    (LEAN_DATA / "custom").mkdir(parents=True, exist_ok=True)

    yahoo = YahooProvider()
    brut = yahoo.fetch(config.data.universe, start=config.data.start, end=config.data.end, on_missing="drop")
    prix = to_wide(brut, config.data.price_field).reindex(columns=config.data.universe)
    volume = to_wide(brut, "volume").reindex(columns=config.data.universe)
    prix.to_parquet(ENTREES / "prices.parquet")
    volume.to_parquet(ENTREES / "volume.parquet")

    french = FrenchProvider()
    quotidien = french.benchmark_factors(frequency=Frequency.DAILY, start=config.data.start)["RF"]
    mensuel = french.benchmark_factors(frequency=Frequency.MONTHLY, start=config.params["aqr_start"])["RF"]
    for dossier in (ENTREES, LEAN_DATA / "custom"):
        quotidien.rename("rf").to_csv(dossier / "rf_daily.csv", index_label="date")
        mensuel.rename("rf").to_csv(dossier / "rf_monthly.csv", index_label="date")

    trous: dict[str, int] = {}
    premiers: dict[str, str] = {}
    for symbole in config.data.universe:
        serie = prix[symbole]
        premier = serie.first_valid_index()
        if premier is None:
            continue
        premiers[symbole] = str(premier.date())
        trous[symbole] = int(serie.loc[premier:].isna().sum())
        write_lean_daily_zip(LEAN_DATA, symbole, serie, volume[symbole])

    resume = {
        "n_symbols": int(prix.notna().any().sum()),
        "first_date": str(prix.index.min().date()),
        "last_date": str(prix.index.max().date()),
        "n_union_dates": len(prix),
        "interior_gaps_by_symbol": trous,
        "interior_gaps_total": int(sum(trous.values())),
        "first_price_by_symbol": premiers,
        "rf_daily_span": [str(quotidien.index.min().date()), str(quotidien.index.max().date())],
        "rf_monthly_span": [str(mensuel.index.min().date()), str(mensuel.index.max().date())],
        "yahoo_manifest": yahoo.manifest().model_dump(mode="json"),
    }
    (ENTREES / "summary.json").write_text(json.dumps(resume, indent=2, ensure_ascii=False))
    _LOG.info(
        "entrées LEAN écrites",
        extra={"n_symbols": resume["n_symbols"], "interior_gaps": resume["interior_gaps_total"]},
    )
    print(json.dumps({k: v for k, v in resume.items() if k != "yahoo_manifest"}, indent=2))


if __name__ == "__main__":
    main()

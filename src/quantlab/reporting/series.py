"""Enregistrer la série de rendements d'une étude, dans un format que tout le reste lit.

**Le problème.** Les huit premières études ont écrit des tableaux de synthèse et
des figures, mais pas leur série mensuelle de rendements. Or c'est cette série,
et rien d'autre, que consomment la phase 7 (combiner les stratégies) et la
comparaison aux fonds réels. Un résultat de recherche dont on ne garde que le
résumé ne se combine pas.

**Le remède.** Une fonction, un format, un emplacement. Chaque étude écrit ses
séries de tête dans ``results/series/<nom>.csv``, deux colonnes ``date`` et
``value``, dates en fin de période, valeurs en fraction et non en pourcentage.
Un fichier compagnon ``results/series/index.json`` dit, pour chaque série, son
échantillon, sa base brute ou nette, sa fréquence et sa période, parce qu'une
série sans ces mentions ne se publie pas (règle 5 du ``CLAUDE.md``).

**Comment vérifier.** ``load_series`` relit exactement ce que ``save_series``
a écrit, à la précision du flottant, et le test du module le prouve sur une
série tirée au hasard.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from quantlab.core.errors import DataQualityError
from quantlab.core.logging import get_logger
from quantlab.core.types import CostBasis, Frequency, SampleTag

__all__ = ["SERIES_DIRNAME", "SERIES_INDEX", "load_series", "load_series_index", "save_series"]

_log = get_logger(__name__)

#: Le sous-répertoire de ``results/`` où vivent les séries.
SERIES_DIRNAME = "series"
#: Le fichier qui décrit chaque série enregistrée.
SERIES_INDEX = "index.json"


def save_series(
    results_dir: str | Path,
    name: str,
    series: pd.Series,
    *,
    sample: SampleTag,
    basis: CostBasis,
    frequency: Frequency,
    universe: str,
    cost_assumptions: str = "aucune",
    notes: str = "",
) -> Path:
    """Écrit une série de rendements et l'inscrit à l'index des séries.

    Args:
        results_dir: le répertoire ``results/`` de l'étude.
        name: le nom de la série, sans extension, en anglais et en minuscules.
        series: les rendements, indexés par date, en fraction.
        sample: l'échantillon auquel la série appartient.
        basis: brut ou net de frais.
        frequency: la fréquence d'observation.
        universe: l'univers, en une ligne lisible.
        cost_assumptions: les hypothèses de coût, en une ligne, si la base est nette.
        notes: tout ce qui aide à relire la série plus tard.

    Returns:
        Le chemin du fichier écrit.

    Raises:
        DataQualityError: si la série est vide, si son index n'est pas daté, s'il
            porte des doublons, ou si une valeur dépasse une unité en valeur
            absolue, signe presque certain d'un pourcentage non converti.
    """
    s = series.dropna()
    if s.empty:
        raise DataQualityError(f"la série « {name} » est vide")
    if not isinstance(s.index, pd.DatetimeIndex):
        raise DataQualityError(f"la série « {name} » n'est pas indexée par des dates")
    if s.index.has_duplicates:
        raise DataQualityError(f"la série « {name} » porte des dates en double")
    if (s.abs() > 1.0).any():
        raise DataQualityError(
            f"la série « {name} » porte une valeur au-delà de 100 % : pourcentage non converti ?"
        )
    if basis is CostBasis.NET and cost_assumptions == "aucune":
        raise DataQualityError(f"la série nette « {name} » doit déclarer ses hypothèses de coût")

    directory = Path(results_dir) / SERIES_DIRNAME
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.csv"
    s = s.sort_index()
    pd.DataFrame({"date": s.index.strftime("%Y-%m-%d"), "value": s.to_numpy()}).to_csv(
        path, index=False, float_format="%.12g"
    )

    index_path = directory / SERIES_INDEX
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.is_file() else {}
    index[name] = {
        "sample": sample.value,
        "basis": basis.value,
        "frequency": frequency.value,
        "universe": universe,
        "cost_assumptions": cost_assumptions,
        "start": s.index.min().strftime("%Y-%m-%d"),
        "end": s.index.max().strftime("%Y-%m-%d"),
        "n_periods": len(s),
        "notes": notes,
    }
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    _log.info(
        "série enregistrée", extra={"series": name, "n": len(s), "sample": sample.value, "basis": basis.value}
    )
    return path


def load_series(results_dir: str | Path, name: str) -> pd.Series:
    """Relit une série enregistrée par :func:`save_series`."""
    path = Path(results_dir) / SERIES_DIRNAME / f"{name}.csv"
    frame = pd.read_csv(path)
    s = pd.Series(frame["value"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"]), name=name)
    s.index.name = "date"
    return s


def load_series_index(results_dir: str | Path) -> dict[str, dict[str, object]]:
    """Relit l'index des séries d'une étude, vide si aucune n'a été écrite."""
    path = Path(results_dir) / SERIES_DIRNAME / SERIES_INDEX
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))

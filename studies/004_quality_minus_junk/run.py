"""Le point d'entrée de l'étude 004, qualité moins camelote.

Ce fichier orchestre et n'implémente rien de réutilisable. La construction du
score vit dans :mod:`quantlab.strategies.quality_minus_junk`, les métriques dans
:mod:`quantlab.analytics`, les contrôles dans :mod:`quantlab.validation`.

Lancement :

.. code-block:: bash

    export QUANTLAB_USER_AGENT="votre nom votre courriel"
    uv run python studies/004_quality_minus_junk/run.py

Le premier lancement télécharge soixante-neuf archives trimestrielles de la SEC,
soit environ cinq gigaoctets, puis les prix quotidiens d'environ mille six cents
titres. Les deux sont mis en cache sous ``data/raw``, et les lancements suivants
n'y retouchent pas.
"""

from __future__ import annotations

import hashlib
import json
import math
import warnings
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from quantlab.analytics.drawdown import max_drawdown
from quantlab.analytics.ic import QuantileWeighting, quantile_returns
from quantlab.analytics.ratios import sharpe_ratio, sharpe_standard_error, sharpe_tstat
from quantlab.analytics.regression import factor_regression
from quantlab.analytics.risk import hit_rate, kurtosis, skewness
from quantlab.analytics.turnover import annualized_turnover, turnover_series
from quantlab.analytics.visualization import figures as viz
from quantlab.core.config import ExperimentConfig, load_config
from quantlab.core.determinism import make_generator
from quantlab.core.errors import ConfigError, InsufficientDataError
from quantlab.core.logging import get_logger, stage
from quantlab.core.types import AssetClass, CostBasis, Frequency, SampleTag
from quantlab.data.point_in_time import PITFrame, assert_no_lookahead
from quantlab.data.providers.aqr import AqrProvider
from quantlab.data.providers.base import HttpClient
from quantlab.data.providers.french import FrenchProvider
from quantlab.data.providers.sec import SecProvider
from quantlab.data.providers.yahoo import YahooProvider, to_wide
from quantlab.execution.costs import breakeven_cost_bps
from quantlab.experiments import ExperimentRegistry
from quantlab.reporting.series import save_series
from quantlab.reporting.study import (
    MetricLabel,
    ReplicationCheck,
    ReportFigure,
    ReportTable,
    StudyReport,
    VerdictCriteria,
    VerdictEvidence,
    decide_verdict,
    generate_report,
    metrics_table,
    replication_table,
)
from quantlab.strategies.base import AlphaMetadata, AlphaRegistry
from quantlab.strategies.quality_minus_junk import (
    COMPONENT_VARIABLES,
    DERA_TAGS,
    annual_records,
    apply_size_screen,
    component_scores,
    dera_quarter_url,
    dera_quarters,
    drop_return_outliers,
    frazzini_pedersen_beta,
    idiosyncratic_volatility,
    lagged_records,
    latest_records,
    parse_dera_archive,
    quality_minus_junk,
    quality_score,
    quality_variables,
    quarterly_roe_volatility,
    screen_in_force,
    size_screens,
    three_component_proxy,
    usable_prices,
)
from quantlab.validation.cpcv import CombinatorialPurgedCV, cpcv_performance_distribution
from quantlab.validation.dsr import deflated_sharpe_ratio, expected_maximum_sharpe
from quantlab.validation.multiple_testing import (
    TrialCounter,
    adjust_pvalues,
    haircut_sharpe,
    required_tstat,
)
from quantlab.validation.pbo import probability_of_backtest_overfitting
from quantlab.validation.robustness import cost_multiplier_analysis, subperiod_performance

warnings.filterwarnings("ignore", category=FutureWarning, module="pandas")

LOG = get_logger("quantlab.studies.004")
STUDY_DIR = Path(__file__).resolve().parent
RESULTS = STUDY_DIR / "results"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"
CACHE = Path("data/raw")
MONTHLY = Frequency.MONTHLY

#: Le tableau VI de la version de travail du 19 juin 2014, colonne des
#: États-Unis. RAPPORTÉ, lu dans ``docs/literature/asness_frazzini_pedersen_2019_qmj.md``.
PAPER_US: Mapping[str, float] = {
    "excess_return_monthly_pct": 0.40,
    "excess_return_tstat": 4.38,
    "alpha_1f_monthly_pct": 0.55,
    "alpha_1f_tstat": 7.27,
    "alpha_3f_monthly_pct": 0.68,
    "alpha_3f_tstat": 11.10,
    "alpha_4f_monthly_pct": 0.66,
    "alpha_4f_tstat": 10.20,
    "sharpe_annual": 0.58,
    "information_ratio_annual": 1.46,
    "beta_market": -0.25,
    "beta_size": -0.38,
    "beta_value": -0.12,
    "beta_momentum": 0.02,
}

#: Les alphas à quatre facteurs des quatre composantes, mêmes source et statut.
PAPER_COMPONENTS: Mapping[str, float] = {
    "profitability": 0.53,
    "safety": 0.57,
    "growth": 0.38,
    "payout": 0.21,
}

#: Le nom lisible de chaque composante, employé dans les tableaux publiés.
COMPONENT_LABELS: Mapping[str, str] = {
    "profitability": "Rentabilité",
    "growth": "Croissance",
    "safety": "Sûreté",
    "payout": "Distribution",
}


# --------------------------------------------------------------------------- #
# Les écritures
# --------------------------------------------------------------------------- #


def _write_table(frame: pd.DataFrame, name: str) -> Path:
    """Écrit un tableau sous ``results/tables`` et rend son chemin."""
    TABLES.mkdir(parents=True, exist_ok=True)
    path = TABLES / f"{name}.csv"
    frame.to_csv(path, index=False)
    LOG.info("tableau écrit", extra={"name": name, "n_rows": len(frame)})
    return path


def _save_figure(fig: Any, name: str) -> Path:
    """Écrit une figure en PNG et en PDF, et rend le chemin du PNG."""
    FIGURES.mkdir(parents=True, exist_ok=True)
    written = viz.save_figure(fig, FIGURES / name, vector=True)
    return next(p for p in written if p.suffix == ".png")


# --------------------------------------------------------------------------- #
# Les données
# --------------------------------------------------------------------------- #


def _load_dera(params: Mapping[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Télécharge et lit les jeux trimestriels de la SEC, avec cache sur disque."""
    root = Path(str(params["dera_cache_dir"]))
    parsed = root / "parsed"
    parsed.mkdir(parents=True, exist_ok=True)
    client: HttpClient | None = None
    quarters = dera_quarters(
        int(params["dera_first_year"]),
        int(params["dera_first_quarter"]),
        int(params["dera_last_year"]),
        int(params["dera_last_quarter"]),
    )
    subs: list[pd.DataFrame] = []
    nums: list[pd.DataFrame] = []
    for year, quarter in quarters:
        sub_path = parsed / f"sub_{year}q{quarter}.parquet"
        num_path = parsed / f"num_{year}q{quarter}.parquet"
        if not (sub_path.exists() and num_path.exists()):
            archive = root / f"{year}q{quarter}.zip"
            if not archive.exists():
                if client is None:
                    client = HttpClient(require_email_contact=True)
                url = dera_quarter_url(str(params["dera_base_url"]), year, quarter)
                archive.write_bytes(client.get(url).content)
            submissions, numbers = parse_dera_archive(archive.read_bytes())
            submissions.to_parquet(sub_path, index=False)
            numbers.to_parquet(num_path, index=False)
        subs.append(pd.read_parquet(sub_path))
        nums.append(pd.read_parquet(num_path))
    submissions = pd.concat(subs, ignore_index=True).drop_duplicates(subset=["adsh"], keep="last")
    numbers = pd.concat(nums, ignore_index=True)
    numbers = numbers.drop_duplicates(subset=["adsh", "tag", "ddate", "qtrs"], keep="last")
    LOG.info("jeux DERA lus", extra={"quarters": len(quarters), "numbers": len(numbers)})
    return submissions, numbers


def _screens(records: pd.DataFrame, params: Mapping[str, Any]) -> dict[pd.Timestamp, frozenset[int]]:
    """Rend les cribles d'univers, un par mois de recalcul écrit dans la configuration."""
    month = int(params["universe_screen_month"])
    dates = [
        d
        for d in pd.date_range(params["construction_start"], params["construction_end"], freq="ME")
        if d.month == month
    ]
    return size_screens(
        records,
        dates,
        max_names=int(params["universe_max_names"]),
        lookback_years=int(params["universe_screen_lookback_years"]),
    )


def _universe_map(records: pd.DataFrame, params: Mapping[str, Any]) -> pd.DataFrame:
    """Rend la correspondance identifiant de déposant vers symbole boursier.

    Le crible par la taille borne le nombre de symboles demandés à Yahoo. La
    liste téléchargée est la RÉUNION des cribles annuels, ce qui évite un second
    téléchargement chaque année. La section transversale, elle, ne reçoit que le
    crible en vigueur à sa date, appliqué plus loin par ``apply_size_screen``.
    """
    keep: set[int] = set()
    for names in _screens(records, params).values():
        keep |= set(names)
    provider = SecProvider()
    mapping = provider.ticker_to_cik()
    frame = pd.DataFrame([{"ticker": ticker, "entity_id": int(cik)} for ticker, cik in mapping.items()])
    frame = frame.drop_duplicates(subset=["entity_id"], keep="first")
    frame = frame[frame["entity_id"].isin(keep)].copy()
    frame["symbol"] = frame["ticker"].str.upper().str.replace(".", "-", regex=False)
    frame["candidates"] = len(keep)
    LOG.info("univers cartographié", extra={"candidates": len(keep), "mapped": len(frame)})
    return frame.sort_values("symbol").reset_index(drop=True)


def _load_prices(symbols: Sequence[str], params: Mapping[str, Any]) -> dict[str, pd.DataFrame]:
    """Télécharge les prix quotidiens des symboles demandés, avec cache sur disque."""
    root = CACHE / "qmj_prices"
    root.mkdir(parents=True, exist_ok=True)
    close_path, adj_path = root / "close.parquet", root / "adj_close.parquet"
    if not (close_path.exists() and adj_path.exists()):
        provider = YahooProvider(on_missing="drop", threads=True)
        closes: list[pd.DataFrame] = []
        adjusted: list[pd.DataFrame] = []
        for start in range(0, len(symbols), 100):
            block = list(symbols[start : start + 100])
            frame = provider.fetch(
                block,
                start=str(params["price_start"]),
                end=str(params["construction_end"]),
                auto_adjust=False,
            )
            closes.append(to_wide(frame, "close"))
            adjusted.append(to_wide(frame, "adj_close"))
        pd.concat(closes, axis=1).sort_index().to_parquet(close_path)
        pd.concat(adjusted, axis=1).sort_index().to_parquet(adj_path)
    close = pd.read_parquet(close_path)
    adjusted = pd.read_parquet(adj_path)
    return {"close": close, "adj_close": adjusted}


# --------------------------------------------------------------------------- #
# Les mesures de série
# --------------------------------------------------------------------------- #


def _series_summary(series: pd.Series, label: str) -> dict[str, float | str]:
    """Rend le résumé d'une série mensuelle, chaque métrique venant de la bibliothèque."""
    clean = series.dropna()
    return {
        "serie": label,
        "debut": str(clean.index[0].date()),
        "fin": str(clean.index[-1].date()),
        "n_mois": len(clean),
        "rendement_mensuel_pct": float(clean.mean() * 100.0),
        "ecart_type_mensuel_pct": float(clean.std(ddof=1) * 100.0),
        "tstat": float(sharpe_tstat(clean, frequency=MONTHLY)),
        "sharpe_annuel": float(sharpe_ratio(clean, frequency=MONTHLY)),
        "pire_repli": float(max_drawdown(clean)),
        "asymetrie": float(skewness(clean)),
        "aplatissement": float(kurtosis(clean)),
        "part_de_mois_positifs": float(hit_rate(clean)),
    }


def _sharpe_difference_test(a: pd.Series, b: pd.Series) -> dict[str, float]:
    """Teste l'égalité de deux ratios de Sharpe sur deux échantillons disjoints.

    Les deux fenêtres ne se recouvrent pas, donc les deux estimateurs sont
    indépendants et la variance de leur écart est la somme des variances. La
    statistique est le rapport de l'écart à la racine de cette somme, et sa loi
    sous l'hypothèse nulle est approximativement normale centrée réduite.
    """
    sa = sharpe_ratio(a, frequency=MONTHLY)
    sb = sharpe_ratio(b, frequency=MONTHLY)
    ea = sharpe_standard_error(a, frequency=MONTHLY).lo
    eb = sharpe_standard_error(b, frequency=MONTHLY).lo
    ecart = float(sa - sb)
    erreur = float(math.sqrt(ea**2 + eb**2))
    z = ecart / erreur if erreur > 0 else float("nan")
    return {
        "sharpe_avant": float(sa),
        "sharpe_apres": float(sb),
        "ecart": ecart,
        "erreur_type_de_l_ecart": erreur,
        "z": float(z),
        "p_bilaterale": float(2.0 * (1.0 - stats.norm.cdf(abs(z)))),
    }


def _regression_row(
    returns: pd.Series, factors: pd.DataFrame, label: str, names: Sequence[str]
) -> dict[str, float | str]:
    """Rend une ligne de régression sur les facteurs nommés."""
    fit = factor_regression(returns, factors[list(names)], frequency=MONTHLY)
    row: dict[str, float | str] = {
        "modele": label,
        "n_mois": int(fit.n_obs),
        "alpha_mensuel_pct": float(fit.alpha / 12.0 * 100.0),
        "alpha_tstat": float(fit.alpha_tstat),
        "r2_ajuste": float(fit.adj_r_squared),
    }
    for name in names:
        row[f"beta_{name}"] = float(fit.betas[name])
        row[f"tstat_{name}"] = float(fit.beta_tstats[name])
    return row


# --------------------------------------------------------------------------- #
# La construction du panneau de caractéristiques
# --------------------------------------------------------------------------- #


def _enriched_panel(panel: pd.DataFrame) -> pd.DataFrame:
    """Ajoute les postes de l'exercice précédent, dans chaque date de décision.

    Les variations d'un exercice à l'autre, celle du fonds de roulement en tête,
    se lisent sur deux exercices consécutifs. Le décalage se fait à l'intérieur
    du groupe formé par la date de décision et la société, jamais entre deux
    dates de décision.
    """
    ordered = panel.sort_values(["as_of", "entity_id", "period_end"]).copy()
    grouped = ordered.groupby(["as_of", "entity_id"], observed=True)
    for item in ("WC", "IB", "BE", "SHROUT", "TOTD", "GP"):
        ordered[f"prev_{item}"] = grouped[item].shift(1)
    ordered["DELTA_WC"] = ordered["WC"] - ordered["prev_WC"]
    return ordered


def _npop_terms(panel: pd.DataFrame, years: int) -> pd.DataFrame:
    """Rend le numérateur et le dénominateur du taux de distribution net.

    Le numérateur est la somme, sur les ``years`` derniers exercices, du résultat
    moins la variation des fonds propres. Le dénominateur est la somme du profit
    brut sur les mêmes exercices.
    """
    ordered = panel.sort_values(["as_of", "entity_id", "period_end"])
    ordered = ordered.groupby(["as_of", "entity_id"], observed=True).tail(years)
    ordered = ordered.assign(
        _num=ordered["IB"] - (ordered["BE"] - ordered["prev_BE"]),
        _den=ordered["GP"],
    )
    grouped = ordered.groupby(["as_of", "entity_id"], observed=True)
    out = pd.DataFrame(
        {
            "NPOP_NUMERATOR": grouped["_num"].sum(min_count=years),
            "NPOP_DENOMINATOR": grouped["_den"].sum(min_count=years),
        }
    ).reset_index()
    return out


def _feature_signature(params: Mapping[str, Any]) -> str:
    """Rend l'empreinte des paramètres dont dépend le panneau de caractéristiques.

    Le cache du panneau ne vaut que pour les paramètres qui l'ont produit. Un
    changement de fenêtre, de crible d'univers ou de réglage de bêta doit donc
    l'invalider, et cette empreinte est ce qui le déclenche.
    """
    keys = (
        "construction_start",
        "construction_end",
        "price_start",
        "growth_years",
        "npop_years",
        "universe_max_names",
        "max_staleness_days",
        "lag_tolerance_days",
        "beta_vol_window_days",
        "beta_corr_window_days",
        "beta_corr_overlap_days",
        "beta_min_vol_days",
        "beta_min_corr_days",
        "beta_shrinkage_weight",
        "beta_shrinkage_target",
        "ivol_window_days",
        "ivol_min_days",
        "ivol_skip_last_day",
        "evol_min_quarters",
        "evol_max_quarters",
        "ohlson_cpi",
        "max_period_return",
        "min_period_return",
        "dera_first_year",
        "dera_last_year",
    )
    payload = json.dumps({k: params[k] for k in keys}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _cached_features(
    records: pd.DataFrame,
    submissions: pd.DataFrame,
    numbers: pd.DataFrame,
    prices: Mapping[str, pd.DataFrame],
    universe: pd.DataFrame,
    market_daily: pd.Series,
    dates: pd.DatetimeIndex,
    params: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Rend le panneau de caractéristiques, relu du cache quand il existe."""
    root = CACHE / "qmj_features" / _feature_signature(params)
    files = {name: root / f"{name}.parquet" for name in ("variables", "equity", "returns")}
    meta = root / "coverage.json"
    if all(path.exists() for path in files.values()) and meta.exists():
        LOG.info("panneau de caractéristiques relu du cache", extra={"path": str(root)})
        return (
            pd.read_parquet(files["variables"]),
            pd.read_parquet(files["equity"]),
            pd.read_parquet(files["returns"]),
            json.loads(meta.read_text(encoding="utf-8")),
        )
    variables, equity_panel, monthly_returns, coverage = _build_features(
        records, submissions, numbers, prices, universe, market_daily, dates, params
    )
    root.mkdir(parents=True, exist_ok=True)
    variables.to_parquet(files["variables"], index=False)
    equity_panel.to_parquet(files["equity"])
    monthly_returns.to_parquet(files["returns"])
    meta.write_text(json.dumps(coverage, ensure_ascii=False, indent=2), encoding="utf-8")
    return variables, equity_panel, monthly_returns, coverage


def _build_features(
    records: pd.DataFrame,
    submissions: pd.DataFrame,
    numbers: pd.DataFrame,
    prices: Mapping[str, pd.DataFrame],
    universe: pd.DataFrame,
    market_daily: pd.Series,
    dates: pd.DatetimeIndex,
    params: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Assemble le panneau des vingt et une variables, sans information future.

    Returns:
        Le tableau des variables, la valeur boursière, le rendement mensuel et
        les diagnostics de couverture.
    """
    symbols = universe.set_index("entity_id")["symbol"]
    available = [s for s in symbols.unique() if s in prices["close"].columns]
    kept = symbols[symbols.isin(available)]
    close, removed_close = usable_prices(prices["close"][list(dict.fromkeys(kept.tolist()))])
    adjusted, removed_adjusted = usable_prices(prices["adj_close"][close.columns])

    monthly_close = close.resample("ME").last()
    monthly_adjusted = adjusted.resample("ME").last()
    monthly_returns, dropped_monthly = drop_return_outliers(
        monthly_adjusted.pct_change(),
        max_return=float(params["max_period_return"]),
        min_return=float(params["min_period_return"]),
    )
    daily_returns, dropped_daily = drop_return_outliers(
        adjusted.pct_change(),
        max_return=float(params["max_period_return"]),
        min_return=float(params["min_period_return"]),
    )

    entity_of_symbol = {symbol: entity for entity, symbol in kept.items()}
    columns = pd.Index([entity_of_symbol[s] for s in close.columns], name="entity_id")
    monthly_close.columns = columns
    monthly_returns.columns = columns

    slim = records[records["entity_id"].isin(set(kept.index))].copy()
    pit = PITFrame(slim)
    blocks: list[pd.DataFrame] = []
    for moment in dates:
        visible = pit.as_of(moment)
        if visible.empty:
            continue
        visible = visible.sort_values(["entity_id", "period_end"])
        visible = visible.groupby("entity_id", observed=True).tail(int(params["growth_years"]) + 2)
        visible.insert(0, "as_of", moment)
        blocks.append(visible)
    panel = pd.concat(blocks, ignore_index=True)
    assert_no_lookahead(panel, "as_of")

    panel = _enriched_panel(panel)
    current = latest_records(panel, max_staleness_days=int(params["max_staleness_days"]))
    lagged = lagged_records(
        panel,
        current,
        years=int(params["growth_years"]),
        tolerance_days=int(params["lag_tolerance_days"]),
    )
    features = current.merge(lagged, on=["as_of", "entity_id"], how="left")
    features = features.merge(
        _npop_terms(panel, int(params["npop_years"])), on=["as_of", "entity_id"], how="left"
    )
    features = features.rename(
        columns={"prev_IB": "IB_previous", "prev_SHROUT": "lag1_SHROUT", "prev_TOTD": "lag1_TOTD"}
    )

    # La valeur boursière, prix de fin de mois multiplié par le nombre d'actions
    # du dernier exercice connu. Le prix employé n'est PAS ajusté des dividendes,
    # sans quoi le produit ne serait plus une capitalisation.
    price_long = monthly_close.stack(future_stack=True).rename("price").reset_index()  # noqa: PD013
    price_long.columns = ["as_of", "entity_id", "price"]
    features = features.merge(price_long, on=["as_of", "entity_id"], how="left")
    features["ME"] = features["price"] * features["SHROUT"]

    betas = frazzini_pedersen_beta(
        daily_returns.rename(columns=entity_of_symbol),
        market_daily,
        dates,
        volatility_window=int(params["beta_vol_window_days"]),
        correlation_window=int(params["beta_corr_window_days"]),
        overlap=int(params["beta_corr_overlap_days"]),
        min_volatility_days=int(params["beta_min_vol_days"]),
        min_correlation_days=int(params["beta_min_corr_days"]),
        shrinkage_weight=float(params["beta_shrinkage_weight"]),
        shrinkage_target=float(params["beta_shrinkage_target"]),
    )
    sigma = idiosyncratic_volatility(
        daily_returns.rename(columns=entity_of_symbol),
        market_daily,
        betas,
        dates,
        window=int(params["ivol_window_days"]),
        min_days=int(params["ivol_min_days"]),
        skip_last_day=bool(params["ivol_skip_last_day"]),
    )
    for panel_frame, name in ((betas, "beta"), (sigma, "ivol_raw")):
        long = panel_frame.stack(future_stack=True).rename(name).reset_index()  # noqa: PD013
        long.columns = ["as_of", "entity_id", name]
        features = features.merge(long, on=["as_of", "entity_id"], how="left")

    evol = quarterly_roe_volatility(
        submissions,
        numbers,
        dates,
        max_quarters=int(params["evol_max_quarters"]),
        min_quarters=int(params["evol_min_quarters"]),
    )
    features = features.merge(evol, on=["as_of", "entity_id"], how="left")
    if "evol_raw" not in features.columns:
        features["evol_raw"] = np.nan

    variables = quality_variables(features, cpi=float(params["ohlson_cpi"]))
    equity_panel = features.pivot(index="as_of", columns="entity_id", values="ME")  # noqa: PD010
    coverage = {
        "n_symbols_downloaded": int(prices["close"].shape[1]),
        "n_symbols_matched": len(close.columns),
        "n_entities": int(features["entity_id"].nunique()),
        "n_rows": len(features),
        "evol_rows": int(evol.shape[0]),
        "removed_close_cells": int(removed_close),
        "removed_adjusted_cells": int(removed_adjusted),
        "dropped_monthly_returns": len(dropped_monthly),
        "dropped_daily_returns": len(dropped_daily),
        "largest_dropped_monthly": (
            float(dropped_monthly["value"].abs().max()) if len(dropped_monthly) else 0.0
        ),
    }
    return variables, equity_panel, monthly_returns, coverage


# --------------------------------------------------------------------------- #
# Le programme
# --------------------------------------------------------------------------- #


def main() -> None:
    """Mène l'étude de bout en bout et écrit tout ce qu'elle produit."""
    config = load_config(STUDY_DIR / "config.yaml", ExperimentConfig)
    params = config.params
    verdict_params = dict(params["verdict"])
    criteria = VerdictCriteria(
        **{k: v for k, v in verdict_params.items() if k != "min_construction_correlation"}
    )
    min_construction_correlation = float(verdict_params["min_construction_correlation"])
    generator = make_generator(config.seed)
    RESULTS.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)

    countries = list(params["aqr_country_columns"])
    sweep_size = (
        len(params["quality_quantile_grid"])
        * len(params["size_quantile_grid"])
        * len(params["weighting_grid"])
    )
    expected_trials = (
        len(countries)
        + sweep_size
        + len(params["execution_delays"])
        + len(params["cost_bps_grid"])
        + len([m for m in params["cost_multipliers"] if float(m) > 0.0])
        + len(COMPONENT_VARIABLES)
        + len(params["french_datasets"])
        # Un pour la construction de référence, un pour le tri par décile, un
        # pour la variante d'univers qui remplace le crible du jour par la
        # réunion des cribles.
        + 3
    )

    registry = ExperimentRegistry()
    manifests: list[dict[str, Any]] = []
    counter = TrialCounter()

    with registry.run(
        name="004_quality_minus_junk",
        hypothesis=config.hypothesis,
        config=config.model_dump(mode="json"),
        seed=config.seed,
        universe=list(config.data.universe),
        date_start=config.data.start,
        date_end=config.data.end,
        cost_basis=CostBasis.NET,
        cost_assumptions={"spread_bps": config.costs.spread_bps},
        n_trials=expected_trials,
    ) as run:
        # ------------------------------------------------------------------ #
        # 1. Les données
        # ------------------------------------------------------------------ #
        with stage("chargement", experiment_id=run.record.experiment_id):
            aqr = AqrProvider()
            qmj = aqr.qmj_factors()
            sheets = {key: aqr.fetch("qmj", name) for key, name in dict(params["aqr_factor_sheets"]).items()}
            manifests.append(aqr.manifest("qmj").model_dump(mode="json"))

            french = FrenchProvider()
            french_daily = french.fetch("F-F_Research_Data_Factors_daily")
            manifests.append(french.manifest("F-F_Research_Data_Factors_daily").model_dump(mode="json"))
            sorted_portfolios = {
                component: french.fetch(name) for component, name in dict(params["french_datasets"]).items()
            }
            for name in dict(params["french_datasets"]).values():
                manifests.append(french.manifest(name).model_dump(mode="json"))

            submissions, numbers = _load_dera(params)
            records = annual_records(submissions, numbers)
            universe = _universe_map(records, params)
            prices = _load_prices(universe["symbol"].tolist(), params)
            manifests.append(
                YahooProvider()
                .manifest(
                    symbols=list(prices["close"].columns),
                    start=str(params["price_start"]),
                    end=str(params["construction_end"]),
                    rows=int(prices["close"].size),
                    auto_adjust=False,
                    adjusted=False,
                )
                .model_dump(mode="json")
            )
            manifests.append(
                SecProvider()
                .manifest(
                    ciks=sorted({str(c) for c in universe["entity_id"]}),
                    tags=sorted(DERA_TAGS),
                    start=f"{int(params['dera_first_year'])}-01-01",
                    end=str(params["construction_end"]),
                    rows=len(records),
                )
                .model_dump(mode="json")
            )

        factors = pd.DataFrame(
            {
                "MKT": sheets["market"]["USA"],
                "SMB": sheets["size"]["USA"],
                "HML": sheets["value"]["USA"],
                "UMD": sheets["momentum"]["USA"],
            }
        ).dropna()
        market_daily = (french_daily["MKT-RF"] + french_daily["RF"]).rename("MKT")

        # ------------------------------------------------------------------ #
        # 2. Jambe A, le facteur publié
        # ------------------------------------------------------------------ #
        paper_end = pd.Timestamp(params["paper_us_end"])
        usa = qmj["USA"].dropna()
        in_sample = usa[usa.index <= paper_end]
        holdout = usa[usa.index > paper_end]

        published_rows = [
            _series_summary(usa, "QMJ États-Unis, échantillon complet"),
            _series_summary(in_sample, "QMJ États-Unis, fenêtre de l'article"),
            _series_summary(holdout, "QMJ États-Unis, après publication"),
        ]
        published_frame = pd.DataFrame(published_rows)
        _write_table(published_frame, "published_factor")

        regression_rows = [
            _regression_row(in_sample, factors, "un facteur, fenêtre de l'article", ["MKT"]),
            _regression_row(
                in_sample, factors, "trois facteurs, fenêtre de l'article", ["MKT", "SMB", "HML"]
            ),
            _regression_row(
                in_sample, factors, "quatre facteurs, fenêtre de l'article", ["MKT", "SMB", "HML", "UMD"]
            ),
            _regression_row(holdout, factors, "un facteur, après publication", ["MKT"]),
            _regression_row(holdout, factors, "trois facteurs, après publication", ["MKT", "SMB", "HML"]),
            _regression_row(
                holdout, factors, "quatre facteurs, après publication", ["MKT", "SMB", "HML", "UMD"]
            ),
        ]
        regression_frame = pd.DataFrame(regression_rows)
        _write_table(regression_frame, "published_regressions")

        difference = _sharpe_difference_test(in_sample, holdout)
        difference_frame = pd.DataFrame([{"serie": "QMJ États-Unis", **difference}])
        _write_table(difference_frame, "sharpe_difference")

        country_rows = []
        for country in countries:
            series = qmj[country].dropna()
            if len(series) < 60:
                continue
            before = series[series.index <= paper_end]
            after = series[series.index > paper_end]
            row = {
                "pays": country,
                "n_mois": len(series),
                "sharpe_total": float(sharpe_ratio(series, frequency=MONTHLY)),
                "tstat_total": float(sharpe_tstat(series, frequency=MONTHLY)),
            }
            if len(before) >= 60:
                row["sharpe_avant"] = float(sharpe_ratio(before, frequency=MONTHLY))
            if len(after) >= 24:
                row["sharpe_apres"] = float(sharpe_ratio(after, frequency=MONTHLY))
                row["tstat_apres"] = float(sharpe_tstat(after, frequency=MONTHLY))
            country_rows.append(row)
            counter = counter.record("qmj-pays", country, row["sharpe_total"])
        country_frame = pd.DataFrame(country_rows).sort_values("sharpe_total", ascending=False)
        _write_table(country_frame, "countries")

        subperiods = subperiod_performance(
            usa,
            breakpoints=[pd.Timestamp(b) for b in params["subperiod_breakpoints"]],
            frequency=MONTHLY,
            min_observations=12,
        )
        subperiods["label"] = [
            f"{pd.Timestamp(a):%Y} à {pd.Timestamp(b):%Y}"
            for a, b in zip(subperiods["start"], subperiods["end"], strict=True)
        ]
        _write_table(subperiods, "subperiods")

        # ------------------------------------------------------------------ #
        # 3. Jambe B, notre construction
        # ------------------------------------------------------------------ #
        with stage("construction", experiment_id=run.record.experiment_id):
            dates = pd.DatetimeIndex(
                pd.date_range(params["construction_start"], params["construction_end"], freq="ME")
            )
            variables, equity_panel, monthly_returns, coverage = _cached_features(
                records, submissions, numbers, prices, universe, market_daily, dates, params
            )
            # Le crible d'univers s'applique ICI, avant le passage par les rangs.
            # Appliqué plus tard, il laisserait la cote d'une société dépendre de
            # sociétés hors univers ; pas appliqué du tout, il ferait entrer dès
            # 2015 celles qui n'ont franchi le seuil de taille qu'après.
            screens = _screens(records, params)
            unscreened = variables
            variables = apply_size_screen(variables, screens)
            coverage["rows_before_screen"] = len(unscreened)
            coverage["rows_after_screen"] = len(variables)
            scores, variable_counts = component_scores(
                variables,
                min_variables=dict(params["min_variables_per_component"]),
                min_names=int(params["universe_min_names"]),
            )
            quality = quality_score(
                scores,
                min_components=int(params["min_components"]),
                min_names=int(params["universe_min_names"]),
            )
            forward = monthly_returns.shift(-int(params["execution_lag_months"]))
            factor = quality_minus_junk(
                quality,
                equity_panel,
                forward,
                quality_quantile=float(params["quality_quantile"]),
                size_quantile=float(params["size_quantile"]),
                weighting=str(params["weighting"]),
                min_names_per_leg=int(params["min_names_per_leg"]),
            )

        ours = factor.returns.dropna()
        counter = counter.record(
            "qmj-construction", "reference", float(sharpe_ratio(ours, frequency=MONTHLY))
        )

        # La variante qui mesure le prix de la fuite. Elle refait le facteur sur
        # la RÉUNION des cribles annuels, donc sur l'univers que seul un regard
        # en avant permet de dresser. L'écart avec la série de référence est le
        # rendement que l'information future ajoutait.
        with stage("variante d'univers", experiment_id=run.record.experiment_id):
            loose_scores, _ = component_scores(
                unscreened,
                min_variables=dict(params["min_variables_per_component"]),
                min_names=int(params["universe_min_names"]),
            )
            loose_quality = quality_score(
                loose_scores,
                min_components=int(params["min_components"]),
                min_names=int(params["universe_min_names"]),
            )
            loose = quality_minus_junk(
                loose_quality,
                equity_panel,
                forward,
                quality_quantile=float(params["quality_quantile"]),
                size_quantile=float(params["size_quantile"]),
                weighting=str(params["weighting"]),
                min_names_per_leg=int(params["min_names_per_leg"]),
            ).returns.dropna()
        variant_rows = [
            _series_summary(ours, "Crible du jour, la série publiée"),
            _series_summary(loose, "Réunion des cribles, l'univers non connaissable"),
        ]
        _write_table(pd.DataFrame(variant_rows), "universe_screen_variant")
        counter = counter.record("qmj-univers", "reunion", float(sharpe_ratio(loose, frequency=MONTHLY)))

        coverage_rows = [
            {
                "grandeur": "sociétés candidates au crible de taille",
                "valeur": float(universe["candidates"].iloc[0]),
            },
            {"grandeur": "sociétés retrouvées dans la carte des symboles", "valeur": float(len(universe))},
            {"grandeur": "symboles rendus par Yahoo", "valeur": float(coverage["n_symbols_matched"])},
            {"grandeur": "sociétés au panneau de caractéristiques", "valeur": float(coverage["n_entities"])},
            {"grandeur": "lignes du panneau", "valeur": float(coverage["n_rows"])},
            {"grandeur": "lignes de volatilité des bénéfices", "valeur": float(coverage["evol_rows"])},
            {"grandeur": "mois du facteur reconstruit", "valeur": float(len(ours))},
            {
                "grandeur": "cases de prix retirées par le nettoyage",
                "valeur": float(coverage["removed_close_cells"] + coverage["removed_adjusted_cells"]),
            },
            {
                "grandeur": "lignes du panneau avant le crible du jour",
                "valeur": float(coverage["rows_before_screen"]),
            },
            {
                "grandeur": "lignes du panneau après le crible du jour",
                "valeur": float(coverage["rows_after_screen"]),
            },
        ]
        _write_table(pd.DataFrame(coverage_rows), "universe_coverage")

        names_frame = factor.counts.reset_index().rename(columns={"index": "date"})
        _write_table(names_frame, "leg_counts")

        # Ce que la réunion des cribles ferait entrer, date par date. La colonne
        # « hors crible du jour » compte les sociétés que seul un crible POSTÉRIEUR
        # admet : elles n'étaient pas connaissables comme grandes ce jour-là.
        union = frozenset().union(*screens.values())
        screen_rows = []
        for moment in sorted(pd.unique(unscreened["as_of"])):
            stamp = pd.Timestamp(moment)
            if stamp.month != int(params["universe_screen_month"]):
                continue
            block = unscreened[unscreened["as_of"] == stamp]
            present = set(block["entity_id"].astype("int64"))
            allowed = set(screen_in_force(screens, stamp))
            screen_rows.append(
                {
                    "date": stamp.date().isoformat(),
                    "crible_du_jour": len(allowed),
                    "reunion_des_cribles": len(union),
                    "societes_au_panneau": len(present),
                    "retenues_par_le_crible_du_jour": len(present & allowed),
                    "hors_crible_du_jour": len(present - allowed),
                    "part_hors_crible": (
                        float(len(present - allowed) / len(present)) if present else float("nan")
                    ),
                }
            )
        _write_table(pd.DataFrame(screen_rows), "universe_screen")

        component_counts = pd.DataFrame(
            {
                COMPONENT_LABELS[name]: frame.replace(0, np.nan).mean(axis=1)
                for name, frame in variable_counts.items()
            }
        )
        _write_table(component_counts.reset_index(), "component_variable_counts")

        variable_coverage = (
            variables.drop(columns=["as_of", "entity_id"]).notna().mean().rename("part_renseignee")
        )
        variable_frame = variable_coverage.reset_index()
        variable_frame.columns = ["variable", "part_renseignee"]
        variable_frame["composante"] = [
            next(c for c, names in COMPONENT_VARIABLES.items() if v in names)
            for v in variable_frame["variable"]
        ]
        _write_table(variable_frame, "variable_coverage")

        # ------------------------------------------------------------------ #
        # 4. Le contrôle qui compte, notre facteur contre le facteur publié
        # ------------------------------------------------------------------ #
        common = ours.index.intersection(usa.index)
        pair = pd.DataFrame({"ours": ours.reindex(common), "published": usa.reindex(common)}).dropna()
        correlation = float(pair["ours"].corr(pair["published"]))
        against_published = factor_regression(
            pair["ours"], pair[["published"]].rename(columns={"published": "QMJ_AQR"}), frequency=MONTHLY
        )
        comparison_rows = [
            _series_summary(pair["ours"], "Notre facteur, fenêtre commune"),
            _series_summary(pair["published"], "QMJ publié, fenêtre commune"),
        ]
        comparison_frame = pd.DataFrame(comparison_rows)
        comparison_frame["correlation_avec_le_publie"] = [correlation, 1.0]
        _write_table(comparison_frame, "construction_vs_published")

        against_frame = pd.DataFrame(
            [
                {
                    "n_mois": int(against_published.n_obs),
                    "alpha_mensuel_pct": float(against_published.alpha / 12.0 * 100.0),
                    "alpha_tstat": float(against_published.alpha_tstat),
                    "beta_qmj_publie": float(against_published.betas["QMJ_AQR"]),
                    "tstat_beta": float(against_published.beta_tstats["QMJ_AQR"]),
                    "r2_ajuste": float(against_published.adj_r_squared),
                    "correlation": correlation,
                }
            ]
        )
        _write_table(against_frame, "regression_on_published")

        component_rows = []
        component_series: dict[str, pd.Series] = {}
        for component in COMPONENT_VARIABLES:
            single = quality_minus_junk(
                scores[component],
                equity_panel,
                forward,
                quality_quantile=float(params["quality_quantile"]),
                size_quantile=float(params["size_quantile"]),
                weighting=str(params["weighting"]),
                min_names_per_leg=int(params["min_names_per_leg"]),
            ).returns.dropna()
            component_series[component] = single
            row = _series_summary(single, COMPONENT_LABELS[component])
            row["composante"] = component
            row["correlation_avec_le_publie"] = float(single.reindex(common).corr(usa.reindex(common)))
            row["alpha_papier_mensuel_pct"] = PAPER_COMPONENTS[component]
            component_rows.append(row)
            counter = counter.record("qmj-composantes", component, float(row["sharpe_annuel"]))
        component_frame = pd.DataFrame(component_rows)
        _write_table(component_frame, "components")

        # Les dix portefeuilles de qualité, l'objet que l'article publie avant
        # son facteur. Le décalage est celui de « forward », donc identique à
        # celui du facteur.
        deciles = quantile_returns(
            quality,
            forward,
            n_quantiles=10,
            weighting=QuantileWeighting.VALUE,
            value_panel=equity_panel,
            min_names=int(params["universe_min_names"]),
        ).dropna()
        decile_frame = pd.DataFrame(
            {
                "portefeuille": list(deciles.columns),
                "rendement_mensuel_pct": [float(deciles[c].mean() * 100.0) for c in deciles.columns],
                "ecart_type_mensuel_pct": [float(deciles[c].std(ddof=1) * 100.0) for c in deciles.columns],
                "sharpe_annuel": [
                    float(sharpe_ratio(deciles[c], frequency=MONTHLY)) for c in deciles.columns
                ],
            }
        )
        _write_table(decile_frame, "quality_deciles")
        counter = counter.record(
            "qmj-deciles", "spread", float(sharpe_ratio(deciles["spread"], frequency=MONTHLY))
        )

        # ------------------------------------------------------------------ #
        # 5. Le repli à trois composantes, sans biais du survivant
        # ------------------------------------------------------------------ #
        proxy_legs: dict[str, tuple[pd.Series, pd.Series]] = {}
        legs_config = dict(params["french_legs"])
        for component, table in sorted_portfolios.items():
            long_name, short_name = legs_config[component]
            proxy_legs[component] = (table[long_name].dropna(), table[short_name].dropna())
        proxy = three_component_proxy(proxy_legs).dropna()
        proxy = proxy[proxy.index >= pd.Timestamp(params["french_start"])]
        proxy_rows = []
        for name in [*proxy_legs, "proxy"]:
            series = proxy[name].dropna()
            row = _series_summary(series, name)
            row["correlation_avec_le_publie"] = float(
                series.reindex(usa.index.intersection(series.index)).corr(
                    usa.reindex(usa.index.intersection(series.index))
                )
            )
            proxy_rows.append(row)
            if name != "proxy":
                counter = counter.record("qmj-repli", name, float(row["sharpe_annuel"]))
        proxy_frame = pd.DataFrame(proxy_rows)
        _write_table(proxy_frame, "three_component_proxy")

        # Le diagnostic qui sépare deux causes d'une corrélation faible : notre
        # score peut être faux, ou notre univers peut être trop étroit. Les
        # jambes de Kenneth French portent la même idée sur un univers complet,
        # donc les corréler à nos composantes tranche entre les deux.
        diagnostic_block = pd.DataFrame(
            {
                "Notre facteur": ours,
                **{
                    f"Notre {COMPONENT_LABELS[name].lower()}": component_series[name]
                    for name in COMPONENT_VARIABLES
                },
                "QMJ publié": usa,
                "Rentabilité (French)": proxy["profitability"],
                "Croissance (French)": proxy["growth"],
                "Sûreté (French)": proxy["safety"],
                "Marché": factors["MKT"],
            }
        ).dropna()
        diagnostic_frame = diagnostic_block.corr().reset_index()
        diagnostic_frame = diagnostic_frame.rename(columns={"index": "serie"})
        diagnostic_frame.insert(1, "n_mois", len(diagnostic_block))
        _write_table(diagnostic_frame, "component_vs_proxy")

        # Notre facteur passé au même modèle que le facteur publié.
        ours_regression = pd.DataFrame(
            [
                _regression_row(
                    ours, factors, "quatre facteurs, notre construction", ["MKT", "SMB", "HML", "UMD"]
                ),
                _regression_row(
                    usa.reindex(ours.index).dropna(),
                    factors,
                    "quatre facteurs, QMJ publié sur la même fenêtre",
                    ["MKT", "SMB", "HML", "UMD"],
                ),
            ]
        )
        _write_table(ours_regression, "our_factor_regressions")
        save_series(
            RESULTS,
            "qmj_ours_gross",
            ours.dropna(),
            sample=SampleTag.VALIDATION,
            basis=CostBasis.GROSS,
            frequency=Frequency.MONTHLY,
            universe="déposants DERA de la SEC, grandes capitalisations",
            notes="quatre composantes, 21 variables, point-in-time ; corrèle 0,106 avec le facteur publié",
        )
        save_series(
            RESULTS,
            "qmj_published_usa_gross",
            usa.dropna(),
            sample=SampleTag.VALIDATION,
            basis=CostBasis.GROSS,
            frequency=Frequency.MONTHLY,
            universe="facteur QMJ d'AQR, colonne USA",
            notes="cible de réplication, construction des auteurs",
        )

        # La qualité des rendements employés, mesurée plutôt que supposée.
        extreme = monthly_returns.stack(future_stack=True).dropna()  # noqa: PD013
        quality_of_returns = pd.DataFrame(
            [
                {"grandeur": "rendements mensuels non manquants", "valeur": float(len(extreme))},
                {"grandeur": "rendement mensuel maximal", "valeur": float(extreme.max())},
                {"grandeur": "rendement mensuel minimal", "valeur": float(extreme.min())},
                {
                    "grandeur": "rendements au-dessus de cent pour cent",
                    "valeur": float((extreme > 1.0).sum()),
                },
                {
                    "grandeur": "rendements au-dessous de moins cinquante pour cent",
                    "valeur": float((extreme < -0.5).sum()),
                },
                {"grandeur": "centile 99,9", "valeur": float(extreme.quantile(0.999))},
                {"grandeur": "centile 0,1", "valeur": float(extreme.quantile(0.001))},
                {
                    "grandeur": "prix de clôture bruts retirés parce que nuls ou négatifs",
                    "valeur": float(coverage["removed_close_cells"]),
                },
                {
                    "grandeur": "prix ajustés retirés parce que nuls ou négatifs",
                    "valeur": float(coverage["removed_adjusted_cells"]),
                },
                {
                    "grandeur": "rendements mensuels retirés par le garde-fou",
                    "valeur": float(coverage["dropped_monthly_returns"]),
                },
                {
                    "grandeur": "rendements quotidiens retirés par le garde-fou",
                    "valeur": float(coverage["dropped_daily_returns"]),
                },
                {
                    "grandeur": "plus grand rendement mensuel retiré",
                    "valeur": float(coverage["largest_dropped_monthly"]),
                },
            ]
        )
        _write_table(quality_of_returns, "return_quality")

        # ------------------------------------------------------------------ #
        # 6. La robustesse
        # ------------------------------------------------------------------ #
        # Une case de grille qui ne remplit jamais ses quatre coins est un essai
        # RATÉ, pas une case absente. La règle 8 du CLAUDE.md interdit de la
        # cacher : elle entre dans le tableau avec son état, et dans le compte
        # des essais avec un ratio de Sharpe posé à zéro.
        sweep_rows = []
        sweep_series: dict[str, pd.Series] = {}
        for quality_cut in params["quality_quantile_grid"]:
            for size_cut in params["size_quantile_grid"]:
                for weighting in params["weighting_grid"]:
                    label = f"q{quality_cut}_t{size_cut}_{weighting}"
                    base_row = {
                        "quality_quantile": float(quality_cut),
                        "size_quantile": float(size_cut),
                        "ponderation": str(weighting),
                    }
                    try:
                        built = quality_minus_junk(
                            quality,
                            equity_panel,
                            forward,
                            quality_quantile=float(quality_cut),
                            size_quantile=float(size_cut),
                            weighting=str(weighting),
                            min_names_per_leg=int(params["min_names_per_leg"]),
                        ).returns.dropna()
                    except InsufficientDataError:
                        sweep_rows.append(
                            {
                                **base_row,
                                "n_mois": 0,
                                "rendement_mensuel_pct": float("nan"),
                                "sharpe_annuel": 0.0,
                                "correlation_avec_le_publie": float("nan"),
                                "etat": "aucune date ne remplit les quatre coins",
                            }
                        )
                        counter = counter.record("qmj-balayage", label, 0.0)
                        continue
                    sweep_series[label] = built
                    value = float(sharpe_ratio(built, frequency=MONTHLY))
                    sweep_rows.append(
                        {
                            **base_row,
                            "n_mois": len(built),
                            "rendement_mensuel_pct": float(built.mean() * 100.0),
                            "sharpe_annuel": value,
                            "correlation_avec_le_publie": float(
                                built.reindex(common).corr(usa.reindex(common))
                            ),
                            "etat": "calculé",
                        }
                    )
                    counter = counter.record("qmj-balayage", label, value)
        sweep_frame = pd.DataFrame(sweep_rows)
        _write_table(sweep_frame, "parameter_sweep")

        delay_rows = []
        for delay in params["execution_delays"]:
            built = quality_minus_junk(
                quality,
                equity_panel,
                monthly_returns.shift(-int(delay)),
                quality_quantile=float(params["quality_quantile"]),
                size_quantile=float(params["size_quantile"]),
                weighting=str(params["weighting"]),
                min_names_per_leg=int(params["min_names_per_leg"]),
            ).returns.dropna()
            value = float(sharpe_ratio(built, frequency=MONTHLY))
            delay_rows.append(
                {
                    "delai_mois": int(delay),
                    "n_mois": len(built),
                    "rendement_mensuel_pct": float(built.mean() * 100.0),
                    "sharpe_annuel": value,
                }
            )
            counter = counter.record("qmj-delai", f"delai_{delay}", value)
        _write_table(pd.DataFrame(delay_rows), "execution_delay")

        # ------------------------------------------------------------------ #
        # 7. Les coûts
        # ------------------------------------------------------------------ #
        # La convention est la SOMME ENTIÈRE, celle des études 003, 005, 006 et
        # 008 : le facteur achète d'un côté et vend de l'autre, et chaque côté
        # paie son écart. La demi-somme, qui est le défaut du module, ne
        # facturerait qu'un côté et diviserait le coût par deux.
        rotation = turnover_series(
            factor.weights, drifted=False, convention="full_sum", include_initial=False
        )
        annual_rotation = float(annualized_turnover(rotation, MONTHLY))
        aligned_rotation = rotation.reindex(ours.index).dropna()
        breakeven = float(breakeven_cost_bps(ours.reindex(aligned_rotation.index), aligned_rotation, MONTHLY))
        cost_rows = []
        for rate in params["cost_bps_grid"]:
            net = ours.reindex(aligned_rotation.index) - float(rate) * 1e-4 * aligned_rotation
            value = float(sharpe_ratio(net, frequency=MONTHLY))
            cost_rows.append(
                {
                    "cout_bps": float(rate),
                    "rendement_mensuel_pct": float(net.mean() * 100.0),
                    "sharpe_annuel": value,
                    "rotation_annualisee": annual_rotation,
                }
            )
            counter = counter.record("qmj-couts", f"bps_{rate}", value)
        _write_table(pd.DataFrame(cost_rows), "costs")

        reference_rate = float(config.costs.spread_bps)
        gross_aligned = ours.reindex(aligned_rotation.index)
        net_reference = gross_aligned - reference_rate * 1e-4 * aligned_rotation

        def evaluate_cost(multiplier: float) -> float:
            """Rend le ratio de Sharpe net de notre facteur à ce multiple de coût."""
            net_at = gross_aligned - reference_rate * 1e-4 * multiplier * aligned_rotation
            return float(sharpe_ratio(net_at.dropna(), frequency=MONTHLY))

        cost_analysis = cost_multiplier_analysis(
            evaluate_cost,
            multipliers=[float(m) for m in params["cost_multipliers"] if float(m) > 0.0],
            threshold=0.0,
        )
        _write_table(cost_analysis.table, "cost_multiples")
        for multiplier, value in zip(
            cost_analysis.table["multiplier"], cost_analysis.table["metric"], strict=True
        ):
            counter = counter.record("qmj-multiples", f"x{multiplier}", float(value))

        # Le facteur publié, mis au même régime de frais que notre construction.
        # La rotation employée est la NÔTRE, celle d'AQR n'étant pas publiée :
        # ce chiffre est donc MODÉLISÉ, et il est déclaré comme tel.
        holdout_cost = reference_rate * 1e-4 * annual_rotation / 12.0
        holdout_net = (holdout - holdout_cost).rename("qmj_net")
        oos_sharpe = float(sharpe_ratio(holdout_net, frequency=MONTHLY))

        # ------------------------------------------------------------------ #
        # 8. Les tests statistiques
        # ------------------------------------------------------------------ #
        n_trials = counter.n_trials()
        if n_trials != expected_trials:
            raise ConfigError(
                f"{n_trials} essais enregistrés contre {expected_trials} déduits des grilles. "
                "Le compte du registre et celui du ratio de Sharpe dégonflé divergeraient."
            )
        trials_frame = pd.DataFrame(
            [{"famille": family, "essais": counter.n_trials(family)} for family in counter.families()]
            + [{"famille": "TOTAL", "essais": n_trials}]
        )
        _write_table(trials_frame, "trials")

        trial_variance = max(float(counter.sharpe_variance()), 1e-6)
        oos_tstat = float(sharpe_tstat(holdout_net, frequency=MONTHLY))
        deflated_value = float(
            deflated_sharpe_ratio(
                observed_sr=oos_sharpe,
                sharpe_variance_across_trials=trial_variance,
                n_trials=n_trials,
                n_obs=float(len(holdout_net)),
                skew=float(skewness(holdout_net)),
                kurtosis=float(kurtosis(holdout_net, excess=False)),
            )
        )
        expected_max = float(expected_maximum_sharpe(n_trials, trial_variance))
        if oos_sharpe > 0.0:
            cut = haircut_sharpe(
                observed_sr=oos_sharpe,
                n_tests=n_trials,
                n_obs=len(holdout_net),
                frequency=MONTHLY,
                method="holm",
            )
            adjusted_tstat = float(cut.adjusted_tstat)
            haircut_status = "calculé"
        else:
            adjusted_tstat = oos_tstat
            haircut_status = (
                "non défini : rabattre un ratio de Sharpe négatif n'a pas de sens, "
                "donc la statistique t brute est reportée telle quelle"
            )
        _write_table(
            pd.DataFrame(
                [
                    {
                        "sharpe_observe_oos_net": oos_sharpe,
                        "tstat_observe": oos_tstat,
                        "n_observations": len(holdout_net),
                        "essais": n_trials,
                        "variance_des_essais": trial_variance,
                        "sharpe_attendu_du_maximum": expected_max,
                        "sharpe_degonfle": deflated_value,
                        "tstat_exige_bonferroni": float(required_tstat(n_trials, 0.05, method="bonferroni")),
                        "tstat_apres_correction": adjusted_tstat,
                        "etat_du_rabais": haircut_status,
                    }
                ]
            ),
            "deflated_sharpe",
        )

        country_pvalues = [
            float(2.0 * (1.0 - stats.norm.cdf(abs(row["tstat_apres"]))))
            for row in country_rows
            if "tstat_apres" in row
        ]
        country_names = [row["pays"] for row in country_rows if "tstat_apres" in row]
        multiplicity = adjust_pvalues(country_pvalues, method="holm", alpha=0.05)
        multiple_frame = pd.DataFrame(
            {
                "pays": country_names,
                "tstat_apres_publication": [
                    row["tstat_apres"] for row in country_rows if "tstat_apres" in row
                ],
                "p_brute": country_pvalues,
                "p_corrigee_holm": multiplicity.adjusted_pvalues,
                "rejetee": multiplicity.rejected,
            }
        ).sort_values("p_corrigee_holm")
        _write_table(multiple_frame, "multiple_testing")

        performance_matrix = pd.DataFrame(sweep_series).dropna()
        pbo_result = probability_of_backtest_overfitting(performance_matrix, n_splits=8, frequency=MONTHLY)
        _write_table(
            pd.DataFrame(
                [
                    {
                        "configurations": int(performance_matrix.shape[1]),
                        "mois": int(performance_matrix.shape[0]),
                        "pbo": float(pbo_result.pbo),
                    }
                ]
            ),
            "pbo",
        )

        def best_of_path(path: Any) -> float:
            """Choisit la meilleure configuration sur chaque bloc d'apprentissage.

            La validation croisée combinatoire ne dit rien d'une série figée,
            puisque tout chemin la reconstruit en entier. Elle juge donc ici le
            PROCESSUS de sélection : sur chaque bloc d'apprentissage, la
            configuration de meilleur Sharpe est retenue, et son rendement du
            bloc de test suivant est collecté.
            """
            pieces: list[pd.Series] = []
            for segment in path.segments:
                train = performance_matrix.iloc[segment.train_index]
                test = performance_matrix.iloc[segment.test_index]
                best = max(
                    performance_matrix.columns,
                    key=lambda column: sharpe_ratio(train[column], frequency=MONTHLY),
                )
                pieces.append(test[best])
            return float(sharpe_ratio(pd.concat(pieces).sort_index(), frequency=MONTHLY))

        cpcv = CombinatorialPurgedCV.from_config(config.validation)
        distribution = cpcv_performance_distribution(
            cpcv, performance_matrix, best_of_path, metric_name="sharpe"
        )
        cpcv_frame = distribution.summary.rename("valeur").reset_index()
        cpcv_frame.columns = ["statistique", "valeur"]
        _write_table(cpcv_frame, "cpcv_distribution")

        block_size = float(params["bootstrap_block_months"])
        draws = int(params["bootstrap_resamples"])
        sample = holdout_net.to_numpy()
        replicates = np.empty(draws, dtype=float)
        for draw in range(draws):
            starts = generator.integers(0, len(sample), size=int(np.ceil(len(sample) / block_size)))
            pieces = [sample[s : s + int(block_size)] for s in starts]
            joined = np.concatenate(pieces)[: len(sample)]
            replicates[draw] = joined.mean() * 12.0
        _write_table(
            pd.DataFrame(
                {
                    "statistique": ["rendement annualisé du facteur publié, net, après publication"],
                    "observe": [float(sample.mean() * 12.0)],
                    "p05": [float(np.quantile(replicates, 0.05))],
                    "p95": [float(np.quantile(replicates, 0.95))],
                    "part_positive": [float((replicates > 0.0).mean())],
                    "tirages": [draws],
                }
            ),
            "bootstrap",
        )

        # ------------------------------------------------------------------ #
        # 9. Le verdict
        # ------------------------------------------------------------------ #
        tolerance = float(criteria.replication_tolerance)
        in_sample_summary = published_rows[1]
        checks = (
            ReplicationCheck(
                quantity="Rendement excédentaire mensuel, États-Unis",
                published=PAPER_US["excess_return_monthly_pct"],
                ours=float(in_sample_summary["rendement_mensuel_pct"]),
                tolerance=tolerance,
                source="Tableau VI, version de travail du 19 juin 2014",
                note="Notre fenêtre commence en juillet 1957, celle de l'article en juin 1956.",
            ),
            ReplicationCheck(
                quantity="Ratio de Sharpe annualisé, États-Unis",
                published=PAPER_US["sharpe_annual"],
                ours=float(in_sample_summary["sharpe_annuel"]),
                tolerance=tolerance,
                source="Tableau VI, version de travail du 19 juin 2014",
            ),
            ReplicationCheck(
                quantity="Alpha à quatre facteurs, mensuel, États-Unis",
                published=PAPER_US["alpha_4f_monthly_pct"],
                ours=float(regression_rows[2]["alpha_mensuel_pct"]),
                tolerance=tolerance,
                source="Tableau VI, version de travail du 19 juin 2014",
            ),
            ReplicationCheck(
                quantity="Chargement sur la taille, quatre facteurs",
                published=PAPER_US["beta_size"],
                ours=float(regression_rows[2]["beta_SMB"]),
                tolerance=tolerance,
                source="Tableau VI, version de travail du 19 juin 2014",
            ),
            ReplicationCheck(
                quantity="Chargement sur le marché, quatre facteurs",
                published=PAPER_US["beta_market"],
                ours=float(regression_rows[2]["beta_MKT"]),
                tolerance=tolerance,
                source="Tableau VI, version de travail du 19 juin 2014",
            ),
            ReplicationCheck(
                quantity="Corrélation de notre construction avec le facteur publié",
                published=1.0,
                ours=correlation,
                tolerance=1.0 - min_construction_correlation,
                tolerance_kind="absolute",
                source="Contrôle propre à l'étude, seuil écrit dans config.yaml",
                note=(
                    "La cible d'une réplication parfaite vaut un, et le seuil accepté "
                    "vit dans la configuration."
                ),
            ),
        )
        replication_frame = replication_table(checks)
        _write_table(replication_frame, "replication_checks")

        positive_share = float((subperiods["sharpe"] > 0).mean())
        evidence = VerdictEvidence(
            hypothesis_supported=bool(float(ours.mean()) > 0.0 and correlation > 0.0),
            replication_checks=checks,
            oos_sharpe=oos_sharpe,
            tstat_after_multiplicity=float(adjusted_tstat),
            deflated_sharpe=deflated_value,
            pbo=float(pbo_result.pbo),
            positive_subperiod_share=positive_share,
            surviving_cost_multiple=(
                float(cost_analysis.table["multiplier"].max())
                if cost_analysis.status == "survives_all"
                else float(cost_analysis.breakeven_multiplier or 0.0)
            ),
            portfolio_correlation=float(holdout.corr(factors["MKT"].reindex(holdout.index))),
            notes=(
                "La jambe A porte le facteur publié par AQR. La jambe B porte notre construction "
                "depuis les fondamentaux point-in-time de la SEC, sur onze années seulement."
            ),
        )
        verdict, reasons = decide_verdict(evidence, criteria)
        run.set_verdict(verdict)

        # ------------------------------------------------------------------ #
        # 10. Les figures
        # ------------------------------------------------------------------ #
        figure_specs: list[tuple[str, str, str]] = []
        with viz.portfolio_style():
            fig, _ = viz.equity_curve(
                {
                    "QMJ publié (AQR)": usa,
                    "Marché américain": factors["MKT"].reindex(usa.index).dropna(),
                },
                log_scale=True,
                title="Le facteur publié et le marché américain, 1957 à 2026",
            )
            _save_figure(fig, "published_equity")
            figure_specs.append(
                ("published_equity", "performance", "Richesse cumulée du facteur publié et du marché.")
            )

            fig, _ = viz.equity_curve(
                {"Notre construction": pair["ours"], "QMJ publié (AQR)": pair["published"]},
                log_scale=False,
                title="Notre construction contre le facteur publié, fenêtre commune",
            )
            _save_figure(fig, "construction_vs_published")
            figure_specs.append(
                (
                    "construction_vs_published",
                    "replication",
                    "Les deux séries sur les mois qu'elles partagent.",
                )
            )

            fig, _ = viz.rolling_metric(
                usa,
                metric="sharpe",
                window=120,
                frequency=MONTHLY,
                title="Ratio de Sharpe glissant sur dix ans du facteur publié",
            )
            _save_figure(fig, "rolling_sharpe")
            figure_specs.append(
                ("rolling_sharpe", "robustness", "Ratio de Sharpe glissant du facteur publié.")
            )

            fig, _ = viz.underwater(usa, title="Repli cumulé du facteur publié")
            _save_figure(fig, "underwater_published")
            figure_specs.append(("underwater_published", "performance", "Le repli cumulé du facteur publié."))

            fig, _ = viz.subperiod_bars(
                subperiods,
                metric_column="sharpe",
                error_column="sharpe_se_lo",
                title="Ratio de Sharpe du facteur publié, par sous-période",
            )
            _save_figure(fig, "subperiod_bars")
            figure_specs.append(("subperiod_bars", "robustness", "Sept sous-périodes, sept Sharpe."))

            correlation_block = pd.DataFrame(
                {
                    "Notre construction": pair["ours"],
                    "QMJ publié": pair["published"],
                    "Marché": factors["MKT"].reindex(pair.index),
                    "Taille": factors["SMB"].reindex(pair.index),
                    "Valeur": factors["HML"].reindex(pair.index),
                    "Momentum": factors["UMD"].reindex(pair.index),
                }
            ).dropna()
            fig, _ = viz.correlation_heatmap(
                correlation_block, title="Corrélations mensuelles sur la fenêtre commune"
            )
            _save_figure(fig, "correlation_heatmap")
            figure_specs.append(("correlation_heatmap", "factor_attribution", "Les corrélations mensuelles."))

            fig, _ = viz.cost_sensitivity(
                [row["multiplier"] for row in cost_analysis.table.to_dict("records")],
                [row["metric"] for row in cost_analysis.table.to_dict("records")],
                threshold=0.0,
                metric_label="Ratio de Sharpe net de notre construction",
                title="Sensibilité au multiple de coût, notre construction",
            )
            _save_figure(fig, "cost_sensitivity")
            figure_specs.append(("cost_sensitivity", "costs", "Le Sharpe net contre le multiple de coût."))

            fig, _ = viz.quantile_bars(
                deciles,
                spread_column="spread",
                title="Les dix portefeuilles de qualité, pondérés par la valeur",
            )
            _save_figure(fig, "quality_deciles")
            figure_specs.append(
                ("quality_deciles", "performance", "Le rendement moyen de chaque décile de qualité.")
            )

            fig, _ = viz.parameter_heatmap(
                sweep_frame[(sweep_frame["etat"] == "calculé") & (sweep_frame["ponderation"] == "value")],
                x="size_quantile",
                y="quality_quantile",
                metric="sharpe_annuel",
                x_label="Coupure de taille",
                y_label="Part de chaque extrémité de qualité",
                metric_label="Ratio de Sharpe annualisé",
                title="Balayage des réglages, pondération par la valeur",
            )
            _save_figure(fig, "parameter_heatmap")
            figure_specs.append(("parameter_heatmap", "robustness", "Le Sharpe de chaque case de la grille."))

            fig, _ = viz.return_histogram(usa, title="Distribution mensuelle du facteur publié")
            _save_figure(fig, "return_histogram")
            figure_specs.append(
                ("return_histogram", "performance", "La distribution des rendements mensuels.")
            )

        # ------------------------------------------------------------------ #
        # 11. Les métriques et le rapport
        # ------------------------------------------------------------------ #
        metric_values = {
            "publie_rendement_mensuel_is_pct": float(in_sample_summary["rendement_mensuel_pct"]),
            "publie_sharpe_is": float(in_sample_summary["sharpe_annuel"]),
            "publie_alpha_4f_is_pct": float(regression_rows[2]["alpha_mensuel_pct"]),
            "publie_rendement_mensuel_oos_pct": float(published_rows[2]["rendement_mensuel_pct"]),
            "publie_sharpe_oos_brut": float(published_rows[2]["sharpe_annuel"]),
            "publie_sharpe_oos_net": oos_sharpe,
            "publie_alpha_4f_oos_pct": float(regression_rows[5]["alpha_mensuel_pct"]),
            "ecart_de_sharpe_z": float(difference["z"]),
            "notre_rendement_mensuel_pct": float(pair["ours"].mean() * 100.0),
            "notre_sharpe": float(sharpe_ratio(pair["ours"], frequency=MONTHLY)),
            "correlation_avec_le_publie": correlation,
            "beta_sur_le_publie": float(against_published.betas["QMJ_AQR"]),
            "alpha_sur_le_publie_mensuel_pct": float(against_published.alpha / 12.0 * 100.0),
            "rotation_annualisee": annual_rotation,
            "cout_de_rentabilite_bps": breakeven,
            "sharpe_net_reference": float(sharpe_ratio(net_reference, frequency=MONTHLY)),
            "probabilite_de_surapprentissage": float(pbo_result.pbo),
            "sharpe_degonfle": deflated_value,
            "t_apres_correction": float(adjusted_tstat),
            "part_de_sous_periodes_positives": positive_share,
            "correlation_avec_le_marche": float(evidence.portfolio_correlation or float("nan")),
            "cpcv_sharpe_moyen": float(distribution.summary["mean"]),
            "cpcv_part_de_chemins_negatifs": float(distribution.negative_share),
            "proxy_sharpe": float(proxy_frame.loc[proxy_frame["serie"] == "proxy", "sharpe_annuel"].iloc[0]),
            "proxy_correlation": float(
                proxy_frame.loc[proxy_frame["serie"] == "proxy", "correlation_avec_le_publie"].iloc[0]
            ),
        }
        labels = {
            "publie_rendement_mensuel_is_pct": MetricLabel(SampleTag.IN_SAMPLE, CostBasis.GROSS),
            "publie_sharpe_is": MetricLabel(SampleTag.IN_SAMPLE, CostBasis.GROSS),
            "publie_alpha_4f_is_pct": MetricLabel(SampleTag.IN_SAMPLE, CostBasis.GROSS),
            "publie_rendement_mensuel_oos_pct": MetricLabel(SampleTag.FINAL_HOLDOUT, CostBasis.GROSS),
            "publie_sharpe_oos_brut": MetricLabel(SampleTag.FINAL_HOLDOUT, CostBasis.GROSS),
            "publie_sharpe_oos_net": MetricLabel(SampleTag.FINAL_HOLDOUT, CostBasis.NET),
            "publie_alpha_4f_oos_pct": MetricLabel(SampleTag.FINAL_HOLDOUT, CostBasis.GROSS),
            "ecart_de_sharpe_z": MetricLabel(SampleTag.FINAL_HOLDOUT, CostBasis.GROSS),
            "notre_rendement_mensuel_pct": MetricLabel(SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
            "notre_sharpe": MetricLabel(SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
            "correlation_avec_le_publie": MetricLabel(SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
            "beta_sur_le_publie": MetricLabel(SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
            "alpha_sur_le_publie_mensuel_pct": MetricLabel(SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
            "rotation_annualisee": MetricLabel(SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
            "cout_de_rentabilite_bps": MetricLabel(SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
            "sharpe_net_reference": MetricLabel(SampleTag.OUT_OF_SAMPLE, CostBasis.NET),
            "probabilite_de_surapprentissage": MetricLabel(SampleTag.OUT_OF_SAMPLE, CostBasis.GROSS),
            "sharpe_degonfle": MetricLabel(SampleTag.FINAL_HOLDOUT, CostBasis.NET),
            "t_apres_correction": MetricLabel(SampleTag.FINAL_HOLDOUT, CostBasis.NET),
            "part_de_sous_periodes_positives": MetricLabel(SampleTag.IN_SAMPLE, CostBasis.GROSS),
            "correlation_avec_le_marche": MetricLabel(SampleTag.FINAL_HOLDOUT, CostBasis.GROSS),
            "cpcv_sharpe_moyen": MetricLabel(SampleTag.FINAL_HOLDOUT, CostBasis.NET),
            "cpcv_part_de_chemins_negatifs": MetricLabel(SampleTag.FINAL_HOLDOUT, CostBasis.NET),
            "proxy_sharpe": MetricLabel(SampleTag.IN_SAMPLE, CostBasis.GROSS),
            "proxy_correlation": MetricLabel(SampleTag.IN_SAMPLE, CostBasis.GROSS),
        }
        metrics = metrics_table(metric_values, labels)
        _write_table(metrics, "metrics")
        for name, value in metric_values.items():
            run.log_metric(name, value, sample=labels[name].sample)

        payload = {
            "study": "004_quality_minus_junk",
            "experiment_id": run.record.experiment_id,
            "seed": config.seed,
            "generator_draw": float(generator.random()),
            "verdict": verdict.value,
            "reasons": reasons,
            "n_trials": n_trials,
            "trials_by_family": {family: counter.n_trials(family) for family in counter.families()},
            "metrics": metric_values,
            "metric_samples": {name: label.sample.value for name, label in labels.items()},
            "cost_basis": {name: label.cost_basis.value for name, label in labels.items()},
            "samples": {
                "published_full": [str(usa.index[0].date()), str(usa.index[-1].date())],
                "published_paper_window": [str(in_sample.index[0].date()), str(in_sample.index[-1].date())],
                "published_holdout": [str(holdout.index[0].date()), str(holdout.index[-1].date())],
                "construction": [str(ours.index[0].date()), str(ours.index[-1].date())],
                "common_window": [str(pair.index[0].date()), str(pair.index[-1].date())],
                "proxy": [str(proxy.index[0].date()), str(proxy.index[-1].date())],
            },
            "cost_assumptions_bps": {"spread_bps": config.costs.spread_bps},
            "universe": coverage,
        }
        (RESULTS / "metrics.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        report_tables = [
            ReportTable(
                "replication_checks", "replication", replication_frame, "Les six contrôles chiffrés."
            ),
            ReportTable(
                "published_factor", "performance", published_frame, "Le facteur publié, trois fenêtres."
            ),
            ReportTable(
                "published_regressions", "factor_attribution", regression_frame, "Les six régressions."
            ),
            ReportTable("countries", "robustness", country_frame, "Les vingt-quatre pays."),
            ReportTable("subperiods", "robustness", subperiods, "Les sous-périodes."),
            ReportTable(
                "construction_vs_published",
                "replication",
                comparison_frame,
                "Notre facteur contre le publié.",
            ),
            ReportTable(
                "regression_on_published", "replication", against_frame, "La régression de l'un sur l'autre."
            ),
            ReportTable("components", "replication", component_frame, "Les quatre composantes."),
            ReportTable("quality_deciles", "performance", decile_frame, "Les dix portefeuilles de qualité."),
            ReportTable(
                "component_vs_proxy",
                "replication",
                diagnostic_frame,
                "Nos composantes contre les jambes de Kenneth French.",
            ),
            ReportTable(
                "our_factor_regressions",
                "factor_attribution",
                ours_regression,
                "Notre facteur au modèle à quatre facteurs.",
            ),
            ReportTable("return_quality", "data", quality_of_returns, "La qualité des rendements employés."),
            ReportTable("three_component_proxy", "robustness", proxy_frame, "Le repli à trois composantes."),
            ReportTable(
                "universe_coverage", "data", pd.DataFrame(coverage_rows), "La couverture de l'univers."
            ),
            ReportTable(
                "variable_coverage", "data", variable_frame, "La couverture des vingt et une variables."
            ),
            ReportTable("parameter_sweep", "robustness", sweep_frame, "Le balayage des réglages."),
            ReportTable("execution_delay", "robustness", pd.DataFrame(delay_rows), "Le délai d'exécution."),
            ReportTable("costs", "costs", pd.DataFrame(cost_rows), "Les frais et le rendement net."),
            ReportTable(
                "cpcv_distribution", "out_of_sample", cpcv_frame, "La validation croisée combinatoire."
            ),
            ReportTable("multiple_testing", "statistical_tests", multiple_frame, "La correction de Holm."),
            ReportTable("trials", "statistical_tests", trials_frame, "Le compte des essais."),
        ]
        report_figures = [
            ReportFigure(name, section, FIGURES / f"{name}.png", caption)
            for name, section, caption in figure_specs
        ]
        report = StudyReport(
            study_name="004_quality_minus_junk",
            experiment_id=run.record.experiment_id,
            hypothesis=config.hypothesis,
            paper=config.paper or "",
            criteria=criteria,
            evidence=evidence,
            sections=_sections(metric_values, verdict.value),
            metrics=metrics,
            tables=report_tables,
            figures=report_figures,
            config=config.model_dump(mode="json"),
            dataset_manifests=manifests,
        )
        generate_report(STUDY_DIR, report)
        run.log_artifact(str(RESULTS))

        alpha_registry = AlphaRegistry()
        alpha_registry.register(
            AlphaMetadata(
                name="quality_minus_junk_us",
                family="quality",
                paper=config.paper,
                asset_classes=[AssetClass.EQUITY],
                horizon="formation mensuelle sur données comptables annuelles, détention un mois",
                economic_rationale=["biais comportemental", "contrainte institutionnelle"],
                inputs=[
                    "facteur QMJ mensuel d'AQR, vingt-quatre pays",
                    "jeux trimestriels de données financières de la SEC, dates de dépôt comprises",
                    "prix quotidiens de Yahoo Finance pour environ mille six cents titres américains",
                    "portefeuilles triés de Kenneth French pour le repli à trois composantes",
                ],
                known_risks=[
                    "Notre construction ne couvre que onze années, les jeux DERA commençant en 2009.",
                    "L'univers vient de la carte des symboles d'aujourd'hui, donc il survit.",
                    "La version publiée de l'article n'a pas été obtenue, les définitions viennent de 2014.",
                    "La rotation employée pour chiffrer les frais du facteur publié est la nôtre.",
                ],
                validation_status=verdict,
                verdict_experiment_id=run.record.experiment_id,
                created=pd.Timestamp.today().date(),
                last_modified=pd.Timestamp.today().date(),
                notes=(
                    "Étude 004. Le mécanisme invoqué est une mauvaise évaluation : le marché paie la "
                    "qualité, mais trop peu, et l'écart de prix ne suffit pas à annuler l'écart de "
                    "rendement. Le verdict est déduit par quantlab.reporting.study.decide_verdict."
                ),
            ),
            overwrite=True,
        )
        LOG.info("étude terminée", extra={"verdict": verdict.value, "n_trials": n_trials})


def _sections(metric_values: Mapping[str, float], verdict: str) -> dict[str, str]:
    """Rend la prose des quinze sections du rapport HTML."""
    return {
        "hypothesis": (
            "Un portefeuille long des sociétés rentables, en croissance, sûres et distributrices, "
            "et court des autres, dégage-t-il un rendement excédentaire positif ? Et le score "
            "reconstruit depuis les fondamentaux publics reproduit-il le facteur publié ?"
        ),
        "paper": (
            "Asness, Frazzini et Pedersen (2019), Quality Minus Junk, Review of Accounting Studies "
            "24(1). La version publiée n'a pas été obtenue ; les chiffres cibles viennent de la "
            "version de travail du 19 juin 2014."
        ),
        "methodology": (
            "Vingt et une variables comptables et boursières deviennent des cotes de rang "
            "transversales, s'agrègent en quatre composantes, puis en un score. Le facteur est un "
            "tri conditionnel, la taille d'abord, la qualité ensuite, pondéré par la valeur."
        ),
        "data": (
            "Le facteur publié vient d'AQR. Les fondamentaux viennent des jeux trimestriels de la "
            "SEC, dont la date de dépôt rend le point-in-time natif. Les prix viennent de Yahoo, "
            "dont le biais du survivant est déclaré."
        ),
        "implementation": (
            "La construction vit dans quantlab.strategies.quality_minus_junk. Le décalage "
            "d'exécution se fait en un seul endroit, dans le tableau de rendements avancés que "
            "l'étude fournit au constructeur du facteur."
        ),
        "assumptions": (
            "Une donnée comptable entre par sa date de dépôt. Une société sans rendement au mois "
            "suivant sort de sa jambe, et les poids restants sont renormalisés. L'indice des prix "
            "de la cote d'Ohlson vaut un, ce qui ne déplace aucun rang."
        ),
        "replication": (
            f"Le facteur publié rend {metric_values['publie_rendement_mensuel_is_pct']:.2f} pour cent "
            f"par mois sur la fenêtre de l'article, contre 0,40 publié. Notre construction corrèle à "
            f"{metric_values['correlation_avec_le_publie']:.2f} avec lui."
        ),
        "performance": (
            "Tous les chiffres portent leur échantillon et leur base de coût dans le tableau des métriques."
        ),
        "costs": (
            f"La rotation annualisée de notre construction vaut "
            f"{metric_values['rotation_annualisee']:.2f} et le coût qui annule le rendement brut "
            f"vaut {metric_values['cout_de_rentabilite_bps']:.0f} points de base."
        ),
        "robustness": (
            "Les parts de qualité, la coupure de taille, la pondération et le délai d'exécution "
            "sont balayés, et chaque case compte pour un essai."
        ),
        "out_of_sample": (
            f"Le facteur publié rend {metric_values['publie_sharpe_oos_brut']:.2f} de ratio de "
            f"Sharpe après la publication, contre {metric_values['publie_sharpe_is']:.2f} avant. "
            f"L'écart des deux vaut {metric_values['ecart_de_sharpe_z']:.2f} erreur type."
        ),
        "statistical_tests": (
            "Le ratio de Sharpe dégonflé, la probabilité de surapprentissage et la correction de "
            "Holm sur les pays sont rapportés dans les tableaux joints."
        ),
        "factor_attribution": (
            "Le facteur publié charge négativement le marché et la taille, ce que la table des "
            "régressions chiffre sur les deux fenêtres."
        ),
        "limitations": (
            "Notre construction ne couvre que onze années. L'univers survit par construction. La "
            "version publiée de l'article reste inaccessible."
        ),
        "verdict": f"Le verdict déduit vaut {verdict}, et il vient des seuils écrits dans config.yaml.",
    }


if __name__ == "__main__":
    main()

"""La ligne de commande du laboratoire.

Elle ne porte aucune logique. Chaque commande valide ses arguments, appelle une
fonction du paquet et affiche le résultat. Elle est donc testable, et surtout
remplaçable : un carnet, un script ou une tâche planifiée appelle les mêmes
fonctions sans passer par elle.

Les commandes des phases non implémentées existent et disent honnêtement
qu'elles ne sont pas implémentées, avec le numéro de leur phase. Une commande
absente laisserait croire à un oubli ; une commande qui ment serait pire.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer

from quantlab import __version__
from quantlab.core.logging import configure_logging, get_logger
from quantlab.core.paths import Layer, configs_dir, data_dir, project_root, studies_dir

app = typer.Typer(
    name="quant",
    help="Laboratoire de recherche quantitative : répliquer, mesurer, refuser.",
    no_args_is_help=True,
    add_completion=False,
)
data_app = typer.Typer(help="Le lac de données : état, contrôles, provenance.", no_args_is_help=True)
exp_app = typer.Typer(help="Le registre des expériences.", no_args_is_help=True)
study_app = typer.Typer(help="Les études de réplication.", no_args_is_help=True)
app.add_typer(data_app, name="data")
app.add_typer(exp_app, name="experiments")
app.add_typer(study_app, name="study")
dashboard_app = typer.Typer(help="Le tableau de bord et le rapport institutionnel.", no_args_is_help=True)
app.add_typer(dashboard_app, name="dashboard")

_log = get_logger(__name__)


def _echo_table(rows: list[tuple[str, str]], title: str | None = None) -> None:
    """Affiche un tableau à deux colonnes, aligné sur la plus longue clé."""
    if title:
        typer.echo(f"\n{title}")
        typer.echo("-" * len(title))
    if not rows:
        typer.echo("  (aucune entrée)")
        return
    width = max(len(k) for k, _ in rows)
    for key, value in rows:
        typer.echo(f"  {key:<{width}}  {value}")


@app.callback()
def main(
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Journal en DEBUG.")] = False,
    json_logs: Annotated[bool, typer.Option("--json-logs", help="Journal en JSON par ligne.")] = False,
) -> None:
    """Installe le journal avant toute commande."""
    configure_logging("DEBUG" if verbose else "INFO", json_output=json_logs)


@app.command()
def info() -> None:
    """Affiche les versions, les chemins et l'état du lac.

    C'est la première commande à lancer sur une machine neuve : elle dit ce qui
    est installé et où le laboratoire écrira.
    """
    from importlib import metadata

    rows = [("quantlab", __version__), ("python", sys.version.split()[0])]
    for pkg in ("numpy", "pandas", "polars", "duckdb", "scipy", "statsmodels", "skfolio"):
        try:
            rows.append((pkg, metadata.version(pkg)))
        except metadata.PackageNotFoundError:
            rows.append((pkg, "non installé"))
    _echo_table(rows, "Versions")

    _echo_table(
        [
            ("racine", str(project_root())),
            ("données", str(data_dir())),
            ("configurations", str(configs_dir())),
            ("études", str(studies_dir())),
        ],
        "Chemins",
    )

    lake_rows: list[tuple[str, str]] = []
    for layer in Layer:
        directory = data_dir(layer)
        n = len([p for p in directory.iterdir() if p.is_dir()]) if directory.is_dir() else 0
        lake_rows.append((layer.value, f"{n} jeu(x)"))
    _echo_table(lake_rows, "Lac de données")


@data_app.command("list")
def data_list(
    layer: Annotated[str, typer.Option(help="raw, bronze, silver ou gold.")] = "gold",
) -> None:
    """Liste les jeux présents dans un étage du lac."""
    directory = data_dir(Layer(layer))
    if not directory.is_dir():
        typer.echo(f"étage « {layer} » vide")
        raise typer.Exit()
    rows = [
        (p.name, f"{sum(f.stat().st_size for f in p.rglob('*') if f.is_file()) / 1e6:.1f} Mo")
        for p in sorted(directory.iterdir())
        if p.is_dir()
    ]
    _echo_table(rows, f"Étage {layer}")


@data_app.command("manifest")
def data_manifest(dataset_id: str, layer: str = "gold") -> None:
    """Affiche le manifeste d'un jeu, c'est-à-dire sa provenance complète."""
    from quantlab.data.manifest import manifest_path_for, read_manifest

    path = manifest_path_for(dataset_id, Layer(layer))
    if not Path(path).is_file():
        typer.secho(f"aucun manifeste pour « {dataset_id} » en {layer}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    manifest = read_manifest(path)
    typer.echo(json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2))


@data_app.command("check")
def data_check(dataset_id: str, layer: str = "silver") -> None:
    """Fait tourner les contrôles de qualité sur un jeu et affiche le rapport.

    La suite lancée est celle qui s'applique à toute table de prix. Les
    contrôles qui demandent un paramètre propre au jeu, comme le calendrier
    d'échange attendu ou le fuseau, se lancent depuis un script d'étude avec
    ``functools.partial``, parce qu'ils n'ont pas de valeur par défaut
    défendable.
    """
    from quantlab.data.lake import read_table
    from quantlab.data.quality import checks as q

    suite = [
        q.check_monotonic_index,
        q.check_no_duplicate_timestamps,
        q.check_positive_prices,
        q.check_ohlc_consistency,
        q.check_extreme_returns,
        q.check_stale_prices,
        q.check_split_anomaly,
    ]
    frame = read_table(dataset_id, Layer(layer), engine="pandas")
    report = q.run_checks(frame, suite)
    echoue = False
    for result in report.results:
        colour = typer.colors.GREEN if result.passed else typer.colors.RED
        typer.secho(
            f"  [{'OK   ' if result.passed else 'ÉCHEC'}] {result.name} : {result.message}",
            fg=colour,
        )
        echoue = echoue or not result.passed
    if echoue:
        raise typer.Exit(code=1)


@exp_app.command("list")
def experiments_list(limit: int = 20) -> None:
    """Liste les dernières expériences enregistrées."""
    from quantlab.experiments import ExperimentRegistry

    records = ExperimentRegistry().read_all()[-limit:]
    rows = [
        (
            r.experiment_id,
            f"{r.name}  verdict={r.verdict or 'aucun'}  essais={r.n_trials}",
        )
        for r in records
    ]
    _echo_table(rows, f"Expériences (dernières {limit})")


@exp_app.command("show")
def experiments_show(experiment_id: str) -> None:
    """Affiche une expérience complète, configuration et métriques comprises."""
    from quantlab.experiments import ExperimentRegistry

    record = ExperimentRegistry().get(experiment_id)
    typer.echo(json.dumps(record.model_dump(mode="json"), ensure_ascii=False, indent=2))


@exp_app.command("trials")
def experiments_trials(prefix: str) -> None:
    """Compte les essais d'une famille, et la variance de leurs ratios de Sharpe.

    Ces deux nombres alimentent le ratio de Sharpe dégonflé. Les afficher avant
    de conclure évite de publier un chiffre qui ignore combien on a cherché.
    """
    from quantlab.experiments import ExperimentRegistry

    registry = ExperimentRegistry()
    n_trials, variance = registry.trial_count(prefix)
    _echo_table(
        [
            ("essais menés", str(n_trials)),
            ("variance des Sharpe", f"{variance:.6f}"),
            ("lectures du holdout", str(registry.holdout_reads(prefix))),
        ],
        f"Famille « {prefix} »",
    )


@study_app.command("list")
def study_list() -> None:
    """Liste les études présentes et leur état."""
    directory = studies_dir()
    rows = [
        (p.name, "README présent" if (p / "README.md").is_file() else "README manquant")
        for p in sorted(directory.iterdir())
        if p.is_dir()
    ]
    _echo_table(rows, "Études")


@study_app.command("run")
def study_run(
    name: str,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Affiche la commande sans l'exécuter.")] = False,
) -> None:
    """Fait tourner une étude de réplication, de la donnée au verdict.

    Le nom se donne par son numéro ou son répertoire, « 001 » comme
    « 001_time_series_momentum ». L'étude s'exécute dans un processus séparé,
    par son propre ``run.py``, si bien que son état ne survit pas à l'appel et
    que deux études ne partagent rien d'autre que le paquet.
    """
    import subprocess

    directory = _resolve_study(name)
    script = directory / "run.py"
    if not script.is_file():
        typer.secho(f"l'étude {directory.name} n'a pas de run.py", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    command = [sys.executable, str(script)]
    typer.echo(f"étude {directory.name} : {' '.join(command)}")
    if dry_run:
        raise typer.Exit()
    completed = subprocess.run(command, cwd=str(project_root()), check=False)
    raise typer.Exit(code=completed.returncode)


def _resolve_study(name: str) -> Path:
    """Rend le répertoire d'une étude depuis son numéro ou son nom complet.

    Raises:
        typer.Exit: si aucun répertoire ne correspond, ou si plusieurs
            correspondent, ce qui ne doit pas arriver puisque les numéros
            sont uniques.
    """
    root = studies_dir()
    candidates = [
        p for p in root.iterdir() if p.is_dir() and (p.name == name or p.name.startswith(f"{name}_"))
    ]
    if len(candidates) == 1:
        return candidates[0]
    known = ", ".join(sorted(p.name for p in root.iterdir() if p.is_dir()))
    typer.secho(
        f"étude « {name} » introuvable ou ambiguë. Études connues : {known}",
        fg=typer.colors.RED,
    )
    raise typer.Exit(code=1)


@app.command("backtest")
def backtest(
    weights: Annotated[str, typer.Argument(help="CSV de poids cibles, dates en lignes, actifs en colonnes.")],
    returns: Annotated[str, typer.Argument(help="CSV de rendements de période, mêmes actifs.")],
    frequency: Annotated[str, typer.Option(help="daily, weekly, monthly.")] = "monthly",
    spread_bps: Annotated[
        float, typer.Option(help="Coût proportionnel par unité négociée, en points de base.")
    ] = 0.0,
    execution_lag: Annotated[int, typer.Option(help="Décalage d'exécution en périodes, jamais zéro.")] = 1,
    out: Annotated[
        str | None, typer.Option(help="Fichier JSON du résumé ; sinon la sortie standard.")
    ] = None,
) -> None:
    """Rejoue des poids sur des rendements et rend le résumé brut et net."""
    import pandas as pd

    from quantlab.backtest.engine import run_backtest
    from quantlab.core.errors import InsufficientDataError
    from quantlab.core.types import Frequency
    from quantlab.execution.costs import LinearCostModel

    w = pd.read_csv(weights, index_col=0, parse_dates=True)
    r = pd.read_csv(returns, index_col=0, parse_dates=True)
    model = LinearCostModel(spread_bps=spread_bps) if spread_bps > 0 else None
    result = run_backtest(
        weights=w, returns=r, cost_model=model, execution_lag=execution_lag, frequency=Frequency(frequency)
    )
    try:
        raw = result.summary()
    except InsufficientDataError as exc:
        raw = {
            "n_periods": len(result.net_returns),
            "gross_mean": float(result.gross_returns.mean()),
            "net_mean": float(result.net_returns.mean()),
            "cost_total": float(result.costs.sum()),
            "note": f"résumé complet indisponible : {exc}",
        }
    summary = {k: (str(v) if not isinstance(v, int | float) else v) for k, v in raw.items()}
    text = json.dumps(summary, ensure_ascii=False, indent=2, default=str)
    if out:
        Path(out).write_text(text, encoding="utf-8")
        typer.echo(f"résumé écrit : {out}")
    else:
        typer.echo(text)


@app.command("portfolio")
def portfolio(
    returns: Annotated[str, typer.Argument(help="CSV de rendements, dates en lignes, actifs en colonnes.")],
    method: Annotated[
        str, typer.Option(help="equal_weight, inverse_volatility, minimum_variance, risk_parity, hrp.")
    ] = "risk_parity",
    covariance: Annotated[str, typer.Option(help="sample, ewma, ledoit_wolf.")] = "ledoit_wolf",
    out: Annotated[str | None, typer.Option(help="Fichier CSV des poids ; sinon la sortie standard.")] = None,
) -> None:
    """Construit des poids depuis une matrice de rendements, par un optimiseur de la phase 5."""
    import pandas as pd

    from quantlab.portfolio import covariance as cov_module
    from quantlab.portfolio import optimizers

    estimators = {
        "sample": cov_module.SampleCovariance,
        "ewma": cov_module.EWMACovariance,
        "ledoit_wolf": cov_module.LedoitWolfCovariance,
    }
    methods = {
        "equal_weight": optimizers.EqualWeight,
        "inverse_volatility": optimizers.InverseVolatility,
        "minimum_variance": optimizers.MinimumVariance,
        "risk_parity": optimizers.RiskParity,
        "hrp": optimizers.HierarchicalRiskParity,
    }
    if covariance not in estimators or method not in methods:
        typer.secho(
            f"covariance parmi {sorted(estimators)}, méthode parmi {sorted(methods)}.", fg=typer.colors.RED
        )
        raise typer.Exit(code=2)
    r = pd.read_csv(returns, index_col=0, parse_dates=True)
    sigma = estimators[covariance]().covariance(r)
    weights = pd.Series(methods[method]().optimize(covariance=sigma)).rename("weight")
    if out:
        weights.to_csv(out)
        typer.echo(f"poids écrits : {out}")
    else:
        typer.echo(weights.to_csv())


@dashboard_app.command("build")
def dashboard_build(
    date: Annotated[str | None, typer.Option(help="Date affichée, aujourd'hui par défaut.")] = None,
) -> None:
    """Engendre docs/dashboard/index.md et ses figures depuis les fichiers du dépôt."""
    from quantlab.reporting.dashboard import build_dashboard

    built = build_dashboard(project_root(), date=date)
    typer.echo(f"tableau écrit : {built.index_path}")
    typer.echo(f"{len(built.studies)} études, {len(built.risk)} séries, {len(built.figure_paths)} figures")
    for note in built.notes:
        typer.secho(note, fg=typer.colors.YELLOW)


@dashboard_app.command("report")
def dashboard_report(
    date: Annotated[str | None, typer.Option(help="Date affichée, aujourd'hui par défaut.")] = None,
) -> None:
    """Compile le tableau de bord en rapport/rapport.pdf."""
    from quantlab.reporting.dashboard import build_report

    path = build_report(project_root(), date=date)
    typer.echo(f"rapport écrit : {path}")


@app.command("report")
def report(
    date: Annotated[str | None, typer.Option(help="Date affichée, aujourd'hui par défaut.")] = None,
) -> None:
    """Engendre le tableau de bord puis le rapport institutionnel, en une commande."""
    from quantlab.reporting.dashboard import build_dashboard, build_report

    built = build_dashboard(project_root(), date=date)
    path = build_report(project_root(), date=date)
    typer.echo(f"tableau : {built.index_path}\nrapport : {path}")


if __name__ == "__main__":  # pragma: no cover
    app()

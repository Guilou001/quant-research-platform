"""Le tableau de bord du laboratoire, engendré depuis ses fichiers, et son rapport PDF.

**Le problème.** Onze études, trente-neuf séries, deux registres de comparaison
et un registre d'expériences vivent dans des fichiers séparés. Un lecteur qui
arrive ne peut pas voir d'un seul écran ce que le laboratoire a établi, et un
tableau écrit à la main divergerait des fichiers dès la prochaine exécution.

**Ce que le module fait.** Il lit les configurations et les métriques des
études, les séries enregistrées, les comparaisons mesurées et le registre
d'expériences, puis écrit une page Markdown et ses figures. La même page se
compile en PDF par le générateur de rapport du portefeuille. Aucun chiffre
n'est retapé : tout vient d'un fichier, et la page dit lequel.

**Ce qu'il ne fait pas.** Il ne recalcule aucune étude et ne sort pas sur le
réseau. Ce qui n'est pas dans les fichiers n'est pas sur le tableau.
"""

from __future__ import annotations

import ast
import datetime as dt
import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from pydantic import Field

from quantlab import REPOSITORY_URL
from quantlab.analytics.drawdown import max_drawdown
from quantlab.analytics.ratios import sharpe_ratio
from quantlab.analytics.returns import cagr, resample_returns
from quantlab.analytics.risk import volatility
from quantlab.analytics.visualization.figures import correlation_heatmap, equity_curve, save_figure
from quantlab.core.config import StrictModel
from quantlab.core.errors import ConfigError, InsufficientDataError
from quantlab.core.logging import get_logger
from quantlab.core.types import Frequency
from quantlab.reporting.series import load_series, load_series_index

__all__ = [
    "DEFAULT_CONFIG",
    "DEFAULT_OUTPUT",
    "DEFAULT_REPORT",
    "BenchmarkRef",
    "DashboardBuild",
    "DashboardConfig",
    "SeriesRef",
    "build_dashboard",
    "build_report",
    "collect_studies",
    "count_tests",
    "load_named_series",
    "registry_summary",
    "risk_table",
]

_LOG = get_logger(__name__)

#: Les chemins par défaut, relatifs à la racine du dépôt.
DEFAULT_CONFIG = Path("configs") / "dashboard.yaml"
DEFAULT_OUTPUT = Path("docs") / "dashboard"
DEFAULT_REPORT = Path("rapport") / "rapport.pdf"

#: Le nombre de dernières expériences listées.
LAST_EXPERIMENTS: int = 12

#: Le motif d'une ligne de verdict d'un fichier ``metrics.json``.
_STUDY_DIR = re.compile(r"^(\d{3})_(.+)$")
_README_TITLE = re.compile(r"^#\s+(.*)$", re.M)
_ONE_LINER = re.compile(r"^\*\*(\d{3})\.\*\*\s+(.*?)(?=\n\n|\Z)", re.S | re.M)
_TABLE_ROW = re.compile(r"^\|\s*(\d{3})\s*\|\s*\[([^\]]+)\]\([^)]*\)\s*\|[^|]*\|\s*(\d+)\s*\|", re.M)


class SeriesRef(StrictModel):
    """Une série enregistrée d'une étude, et son étiquette sur le tableau."""

    study: str
    series: str
    label: str


class BenchmarkRef(StrictModel):
    """Un fichier de comparaison déjà mesuré, et les colonnes reprises."""

    file: str
    title: str
    columns: list[str] = Field(default_factory=list)


class DashboardConfig(StrictModel):
    """Ce que le tableau montre, lu dans ``configs/dashboard.yaml``."""

    title: str
    head_series: list[SeriesRef]
    portfolios: list[SeriesRef] = Field(default_factory=list)
    common_window_start: str | None = None
    benchmarks: list[BenchmarkRef] = Field(default_factory=list)
    benchmark_figures: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class DashboardBuild:
    """Ce qu'une construction a écrit.

    Attributes:
        index_path: la page Markdown.
        figure_paths: les figures écrites, PNG et PDF.
        studies: le tableau des études.
        risk: le tableau de risque des séries.
    """

    index_path: Path
    figure_paths: tuple[Path, ...]
    studies: pd.DataFrame
    risk: pd.DataFrame
    notes: tuple[str, ...] = field(default_factory=tuple)


def _fr(value: float, decimals: int = 2) -> str:
    """Écrit un nombre en typographie française, virgule décimale et espace fine."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "n.d."
    text = f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")
    return text


def _git_sha(root: Path) -> str:
    """Rend le commit courant en sept caractères, ou « non disponible »."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short=7", "HEAD"], cwd=root, capture_output=True, text=True, check=True
        )
        return out.stdout.strip() or "non disponible"
    except (OSError, subprocess.CalledProcessError):
        return "non disponible"


def collect_studies(studies_root: Path) -> pd.DataFrame:
    """Lit chaque étude numérotée : configuration, verdict et phrase de résultat.

    Args:
        studies_root: le répertoire ``studies/``.

    Returns:
        Un tableau, une ligne par étude, trié par numéro : ``number``,
        ``directory``, ``title``, ``paper``, ``n_trials``, ``verdict``,
        ``one_liner``, ``n_series``. Une étude sans ``metrics.json`` porte le
        verdict « non exécutée ».
    """
    one_liners: dict[str, str] = {}
    table_titles: dict[str, str] = {}
    table_trials: dict[str, int] = {}
    readme = studies_root / "README.md"
    if readme.exists():
        text_readme = readme.read_text(encoding="utf-8")
        for number, text in _ONE_LINER.findall(text_readme):
            one_liners[number] = " ".join(text.split())
        for number, title, trials in _TABLE_ROW.findall(text_readme):
            table_titles[number] = title.strip()
            table_trials[number] = int(trials)
    rows: list[dict[str, Any]] = []
    for directory in sorted(studies_root.iterdir()):
        match = _STUDY_DIR.match(directory.name)
        if not directory.is_dir() or not match:
            continue
        config_path = directory / "config.yaml"
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
        metrics_path = directory / "results" / "metrics.json"
        metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}
        title = table_titles.get(match.group(1), directory.name)
        study_readme = directory / "README.md"
        if match.group(1) not in table_titles and study_readme.exists():
            found = _README_TITLE.search(study_readme.read_text(encoding="utf-8"))
            if found:
                title = found.group(1).strip()
        index_path = directory / "results" / "series" / "index.json"
        n_series = len(load_series_index(directory / "results")) if index_path.exists() else 0
        rows.append(
            {
                "number": match.group(1),
                "directory": directory.name,
                "title": title,
                "paper": " ".join(str(config.get("paper", "")).split()),
                "n_trials": int(
                    config.get("n_trials") or metrics.get("n_trials") or table_trials.get(match.group(1), 0)
                ),
                "verdict": str(metrics.get("verdict", "non exécutée")),
                "one_liner": one_liners.get(match.group(1), ""),
                "n_series": n_series,
            }
        )
    return pd.DataFrame(rows).set_index("number") if rows else pd.DataFrame()


def registry_summary(artifacts_root: Path) -> dict[str, Any]:
    """Résume le registre d'expériences : compte, dernières exécutions, essais déclarés.

    Args:
        artifacts_root: le répertoire ``artifacts/`` qui porte ``experiments.jsonl``.

    Returns:
        ``n_experiments``, ``last`` (un tableau des dernières exécutions) et
        ``trials_latest_by_study`` (la somme des essais de la dernière
        exécution de chaque étude). Un registre absent rend des zéros.
    """
    path = artifacts_root / "experiments.jsonl"
    if not path.exists():
        return {"n_experiments": 0, "last": pd.DataFrame(), "trials_latest_by_study": 0}
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    frame = pd.DataFrame(
        [
            {
                "experiment_id": r.get("experiment_id"),
                "name": r.get("name"),
                "finished_at": r.get("finished_at"),
                "verdict": r.get("verdict"),
                "n_trials": r.get("n_trials"),
                "git_sha": str(r.get("git_sha", ""))[:7],
            }
            for r in records
        ]
    )
    frame = frame.sort_values("finished_at")
    latest = frame.dropna(subset=["name"]).groupby("name").tail(1)
    return {
        "n_experiments": len(frame),
        "last": frame.tail(LAST_EXPERIMENTS).iloc[::-1].reset_index(drop=True),
        "trials_latest_by_study": int(pd.to_numeric(latest["n_trials"], errors="coerce").fillna(0).sum()),
    }


def count_tests(tests_root: Path) -> int:
    """Compte les fonctions de test par analyse syntaxique, sans les exécuter."""
    total = 0
    for path in sorted(tests_root.rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        total += sum(
            1
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith("test_")
        )
    return total


def load_named_series(studies_root: Path, refs: list[SeriesRef]) -> dict[str, pd.Series]:
    """Charge des séries enregistrées et les ramène au mensuel.

    Args:
        studies_root: le répertoire ``studies/``.
        refs: les références, étude et nom de série.

    Returns:
        Les séries mensuelles, indexées par étiquette. Une série absente est
        journalisée et omise plutôt que remplacée.
    """
    out: dict[str, pd.Series] = {}
    for ref in refs:
        results = studies_root / ref.study / "results"
        try:
            index = load_series_index(results)
            meta = index[ref.series]
            series = load_series(results, ref.series)
        except (FileNotFoundError, KeyError) as exc:
            _LOG.warning(
                "série absente du tableau",
                extra={"study": ref.study, "series": ref.series, "error": str(exc)},
            )
            continue
        if meta.get("frequency") == "daily":
            series = resample_returns(series, Frequency.MONTHLY)
        series.index = pd.DatetimeIndex(series.index).to_period("M").to_timestamp("M")
        out[ref.label] = series.rename(ref.label)
    return out


def risk_table(series_by_label: dict[str, pd.Series]) -> pd.DataFrame:
    """Rend, par série mensuelle, la fenêtre, le rendement composé, la volatilité, le Sharpe et le pire repli.

    Toutes les mesures viennent de :mod:`quantlab.analytics` ; le tableau ne
    fait que les ranger. Une série sans dispersion rend un Sharpe manquant.
    """
    rows: list[dict[str, Any]] = []
    for label, s in series_by_label.items():
        clean = s.dropna()
        if len(clean) < 2:
            continue
        try:
            sharpe = float(sharpe_ratio(clean, frequency=Frequency.MONTHLY))
        except InsufficientDataError:
            sharpe = float("nan")
        rows.append(
            {
                "label": label,
                "start": clean.index.min().date(),
                "end": clean.index.max().date(),
                "years": round(len(clean) / 12.0, 1),
                "cagr": float(cagr(clean, Frequency.MONTHLY)),
                "volatility": float(volatility(clean, Frequency.MONTHLY)),
                "sharpe": sharpe,
                "max_drawdown": float(max_drawdown(clean)),
            }
        )
    return pd.DataFrame(rows).set_index("label") if rows else pd.DataFrame()


def _table(frame: pd.DataFrame, columns: list[tuple[str, str, int | None]]) -> str:
    """Écrit un tableau Markdown depuis un DataFrame, colonnes choisies et décimales déclarées."""
    header = "| " + " | ".join(title for _, title, _ in columns) + " |"
    align = "|" + "|".join("---:" if d is not None else "---" for _, _, d in columns) + "|"
    lines = [header, align]
    for _, row in frame.iterrows():
        cells = []
        for key, _, decimals in columns:
            value = row[key]
            if decimals is not None and isinstance(value, int | float):
                cells.append(_fr(float(value), decimals))
            else:
                cells.append(str(value))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _benchmark_block(root: Path, ref: BenchmarkRef) -> str:
    """Écrit un bloc de comparaison depuis son fichier, colonnes reprises telles quelles."""
    path = root / ref.file
    if not path.exists():
        return f"### {ref.title}\n\nFichier absent : `{ref.file}`.\n"
    frame = pd.read_csv(path)
    columns = [c for c in ref.columns if c in frame.columns] or list(frame.columns)
    spec = [(c, c, 3 if pd.api.types.is_float_dtype(frame[c]) else None) for c in columns]
    return f"### {ref.title}\n\nSource : `{ref.file}`.\n\n" + _table(frame, spec) + "\n"


def build_dashboard(
    root: Path,
    *,
    config_path: Path | None = None,
    out_dir: Path | None = None,
    date: str | None = None,
) -> DashboardBuild:
    """Engendre la page du tableau de bord et ses figures depuis les fichiers du dépôt.

    Args:
        root: la racine du dépôt.
        config_path: la configuration, ``configs/dashboard.yaml`` par défaut.
        out_dir: le répertoire de sortie, ``docs/dashboard`` par défaut.
        date: la date affichée, aujourd'hui par défaut.

    Returns:
        Ce qui a été écrit, et les deux tableaux calculés.

    Raises:
        ConfigError: la configuration manque ou aucune série n'est chargeable.
    """
    root = Path(root).resolve()
    config_path = root / (config_path or DEFAULT_CONFIG)
    out_dir = root / (out_dir or DEFAULT_OUTPUT)
    if not config_path.exists():
        raise ConfigError(f"configuration du tableau absente : {config_path}")
    config = DashboardConfig.model_validate(yaml.safe_load(config_path.read_text(encoding="utf-8")))
    studies_root = root / "studies"
    figures_dir = out_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    stamp = date or dt.date.today().isoformat()
    notes: list[str] = []

    studies = collect_studies(studies_root)
    heads = load_named_series(studies_root, config.head_series)
    portfolios = load_named_series(studies_root, config.portfolios)
    if not heads:
        raise ConfigError("aucune série de tête n'a pu être chargée.")
    risk = risk_table({**heads, **portfolios})
    registry = registry_summary(root / "artifacts")
    n_tests = count_tests(root / "tests") if (root / "tests").exists() else 0

    figure_paths: list[Path] = []
    start = pd.Timestamp(config.common_window_start) if config.common_window_start else None
    window = {k: (v.loc[start:] if start is not None else v) for k, v in heads.items()}
    window = {k: v for k, v in window.items() if len(v.dropna()) > 12}
    if window:
        common_start = max(v.dropna().index.min() for v in window.values())
        aligned = {k: v.loc[common_start:].dropna() for k, v in window.items()}
        fig, _ = equity_curve(
            aligned,
            currency="$ US",
            title=f"Richesse cumulée des {len(aligned)} séries de tête, {common_start.year}-{stamp[:4]}",
        )
        figure_paths += save_figure(fig, figures_dir / "richesse_cumulee_tetes.png")
        frame = pd.DataFrame(aligned).dropna()
        if frame.shape[1] >= 2 and len(frame) > 12:
            span = f"{frame.index.min().year}-{frame.index.max().year}"
            fig, _ = correlation_heatmap(frame, title=f"Corrélations mensuelles des séries de tête, {span}")
            figure_paths += save_figure(fig, figures_dir / "correlations_tetes.png")
    if portfolios:
        pstart = max(v.dropna().index.min() for v in portfolios.values())
        fig, _ = equity_curve(
            {k: v.loc[pstart:].dropna() for k, v in portfolios.items()},
            currency="$ US",
            title=f"Richesse cumulée des portefeuilles et modèles, {pstart.year}-{stamp[:4]}",
        )
        figure_paths += save_figure(fig, figures_dir / "richesse_cumulee_portefeuilles.png")
    for rel in config.benchmark_figures:
        source = root / rel
        if source.exists():
            target = figures_dir / source.name
            shutil.copyfile(source, target)
            figure_paths.append(target)
        else:
            notes.append(f"figure de comparaison absente : {rel}")

    verdicts = studies["verdict"].value_counts().to_dict() if not studies.empty else {}
    n_trials_total = int(studies["n_trials"].sum()) if not studies.empty else 0
    verdict_line = ", ".join(f"{n} `{v}`" for v, n in sorted(verdicts.items())) or "aucun"
    lines: list[str] = [
        f"# {config.title}",
        "",
        f"Engendré le {stamp} par `quant dashboard build`, commit `{_git_sha(root)}`. Chaque chiffre",
        "vient d'un fichier du dépôt, nommé sous chaque tableau. Rien ici n'est un conseil en",
        "investissement.",
        "",
        "## L'état en quatre nombres",
        "",
        f"- **{len(studies)} études** menées, verdicts : {verdict_line}.",
        f"- **{n_trials_total} essais déclarés** dans les configurations, qui entrent dans le ratio de "
        "Sharpe dégonflé.",
        f"- **{registry['n_experiments']} expériences** au registre, {registry['trials_latest_by_study']} "
        "essais sur les dernières exécutions.",
        f"- **{n_tests} fonctions de test**, dont les gardiens d'architecture et de style.",
        "",
        "## Les verdicts",
        "",
        "Source : `studies/*/config.yaml` et `studies/*/results/metrics.json` ; la phrase de résultat vient",
        "de `studies/README.md`.",
        "",
    ]
    if not studies.empty:
        rows = studies.reset_index()
        rows["étude"] = rows["number"] + " " + rows["title"]
        rows["verdict_md"] = "`" + rows["verdict"] + "`"
        lines.append(
            _table(
                rows,
                [
                    ("étude", "Étude", None),
                    ("n_trials", "Essais", 0),
                    ("verdict_md", "Verdict", None),
                    ("one_liner", "Ce qui a été mesuré", None),
                ],
            )
        )
    lines += [
        "",
        "## Les séries, et ce qu'elles valent",
        "",
        "Une série de tête par étude, nette de coûts quand une version nette existe, plus les",
        "portefeuilles construits dessus. Mensuel, brut de frais de gestion. Source :",
        "`studies/*/results/series/`, mesures de `quantlab.analytics`. Les figures de richesse",
        "cumulée partent de la première date commune à toutes les séries tracées, donc de la plus",
        "courte d'entre elles.",
        "",
    ]
    if not risk.empty:
        rows = risk.reset_index()
        rows["cagr_pct"] = rows["cagr"] * 100
        rows["vol_pct"] = rows["volatility"] * 100
        rows["dd_pct"] = rows["max_drawdown"] * 100
        lines.append(
            _table(
                rows,
                [
                    ("label", "Série", None),
                    ("start", "Début", None),
                    ("end", "Fin", None),
                    ("years", "Années", 1),
                    ("cagr_pct", "Rendement composé (%)", 2),
                    ("vol_pct", "Volatilité (%)", 2),
                    ("sharpe", "Sharpe", 3),
                    ("dd_pct", "Pire repli (%)", 1),
                ],
            )
        )
    lines += ["", "## Les trajectoires", ""]
    for path in figure_paths:
        if path.suffix == ".png":
            lines += [f"![{path.stem}](figures/{path.name})", ""]
    lines += ["## Les comparaisons aux fonds réels", ""]
    for ref in config.benchmarks:
        lines += [_benchmark_block(root, ref), ""]
    lines += [
        "## Les dernières expériences du registre",
        "",
        "Source : `artifacts/experiments.jsonl`, non suivi par git, régénéré par chaque exécution.",
        "",
    ]
    last = registry["last"]
    if isinstance(last, pd.DataFrame) and not last.empty:
        last = last.copy()
        last["verdict"] = last["verdict"].fillna("").astype(str)
        last["finished_at"] = last["finished_at"].fillna("").astype(str).str.slice(0, 19)
        lines.append(
            _table(
                last,
                [
                    ("experiment_id", "Expérience", None),
                    ("finished_at", "Terminée", None),
                    ("verdict", "Verdict", None),
                    ("n_trials", "Essais", 0),
                    ("git_sha", "Commit", None),
                ],
            )
        )
    else:
        lines.append("Registre absent sur cette machine.")
    lines += [
        "",
        "## Comment lire ce tableau",
        "",
        "Aucune étude n'atteint `ROBUST`, et c'est le résultat du laboratoire, pas son échec : les",
        "facteurs publiés se répliquent dans leur fenêtre et ne survivent pas à la publication, aux",
        "coûts ou à la taille. Le parcours qui l'établit est décrit dans",
        "[la méthodologie](../methodology/gauntlet.md), et chaque verdict dans le README de son étude.",
        "",
    ]
    for note in notes:
        lines.append(f"- {note}")
    index_path = out_dir / "index.md"
    index_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    _LOG.info("tableau de bord écrit", extra={"path": str(index_path), "n_figures": len(figure_paths)})
    return DashboardBuild(index_path, tuple(figure_paths), studies, risk, tuple(notes))


def build_report(
    root: Path, *, markdown_path: Path | None = None, destination: Path | None = None, date: str | None = None
) -> Path:
    """Compile la page du tableau de bord en un rapport PDF, par le générateur du portefeuille.

    Args:
        root: la racine du dépôt.
        markdown_path: la page source, ``docs/dashboard/index.md`` par défaut.
        destination: le PDF écrit, ``rapport/rapport.pdf`` par défaut.
        date: la date affichée en tête.

    Returns:
        Le chemin du PDF.

    Raises:
        ConfigError: la page source n'existe pas ; construire le tableau d'abord.
    """
    import typst
    from gvf import markdown as gvf_markdown
    from gvf import rapport as gvf_rapport

    root = Path(root).resolve()
    markdown_path = root / (markdown_path or DEFAULT_OUTPUT / "index.md")
    destination = root / (destination or DEFAULT_REPORT)
    if not markdown_path.exists():
        raise ConfigError(f"page absente : {markdown_path}. Lancer « quant dashboard build » d'abord.")
    text = markdown_path.read_text(encoding="utf-8")
    page_dir = markdown_path.parent.relative_to(root).as_posix()
    text = re.sub(r"!\[([^\]]*)\]\((?!https?://|/)([^)]+)\)", rf"![\1]({page_dir}/\2)", text)
    to_root = "/".join([".."] * len(destination.parent.relative_to(root).parts)) or "."
    document = gvf_markdown.convertir(text, racine=to_root)
    source = gvf_rapport.GABARIT.format(
        titre=gvf_markdown.chaine(document.titre),
        titre_affiche=gvf_markdown.ligne(document.titre),
        pied=gvf_markdown.ligne(root.name),
        date=date or dt.date.today().isoformat(),
        depot=REPOSITORY_URL,
        depot_court=REPOSITORY_URL.removeprefix("https://"),
        corps=document.corps,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    typ_path = destination.parent / f"{destination.stem}.typ"
    typ_path.write_text(source, encoding="utf-8")
    destination.write_bytes(typst.compile(typ_path, root=root))
    _LOG.info("rapport écrit", extra={"path": str(destination), "bytes": destination.stat().st_size})
    return destination

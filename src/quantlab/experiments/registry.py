"""Le registre d'expériences : un fichier, pas un serveur.

**Le problème.** Un résultat sans sa trace est un résultat qu'on ne peut ni
refaire, ni défendre, ni compter. Refaire, parce que la configuration exacte a
disparu. Défendre, parce que la version des données n'est plus connue. Compter,
parce que le nombre d'essais menés est l'intrant du ratio de Sharpe dégonflé.

**Le remède.** Un répertoire par expérience sous ``artifacts/``, plus un index en
JSON par ligne que DuckDB lit comme une table. Rien à démarrer, rien à
synchroniser, tout se versionne et se lit dans une revue de code. Le
raisonnement complet vit dans ``ADR-009``.

**Ce qui est enregistré.** L'empreinte du commit, la configuration, la graine
et les versions des dépendances. Puis les empreintes des jeux de données, les
dates de début et de fin, l'univers, les hypothèses de coût, les métriques et le
verdict. Une expérience à laquelle il manque l'un de ces champs ne se ferme
pas.

Usage :

.. code-block:: python

    registry = ExperimentRegistry()
    with registry.run(name="tsmom", hypothesis="...", config=cfg) as run:
        run.log_metric("sharpe_is", 1.24, sample=SampleTag.IN_SAMPLE)
        run.log_metric("sharpe_oos", 0.41, sample=SampleTag.OUT_OF_SAMPLE)
        run.set_verdict(Verdict.EXPERIMENTAL)
"""

from __future__ import annotations

import datetime as dt
import json
import platform
import subprocess
import sys
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path
from typing import Any

from pydantic import Field

from quantlab.core.config import StrictModel
from quantlab.core.errors import QuantLabError
from quantlab.core.logging import get_logger
from quantlab.core.paths import artifacts_dir, ensure
from quantlab.core.types import CostBasis, SampleTag, Verdict

_log = get_logger(__name__)

#: Les paquets dont la version entre dans la trace. Un changement de l'un d'eux
#: peut déplacer un chiffre, donc il doit être visible dans le registre.
TRACKED_PACKAGES = (
    "numpy",
    "scipy",
    "pandas",
    "polars",
    "statsmodels",
    "arch",
    "scikit-learn",
    "skfolio",
    "duckdb",
)

#: Le nom du fichier d'index, en JSON par ligne pour être lisible par DuckDB.
INDEX_FILE = "experiments.jsonl"


class ExperimentRecord(StrictModel):
    """Une ligne du registre : tout ce qui permet de refaire une expérience.

    Le modèle est gelé et refuse les clés inconnues. Une trace incomplète vaut
    mieux qu'une trace fausse, et une trace fausse est ce qu'on obtient quand un
    champ mal orthographié passe pour une valeur par défaut.
    """

    experiment_id: str
    name: str
    hypothesis: str
    created_at: dt.datetime
    finished_at: dt.datetime | None = None
    git_sha: str | None = Field(default=None, description="None quand le dépôt n'est pas un dépôt git.")
    git_dirty: bool | None = None
    seed: int | None = None
    python_version: str
    platform: str
    package_versions: dict[str, str] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    dataset_hashes: dict[str, str] = Field(default_factory=dict)
    universe: list[str] = Field(default_factory=list)
    date_start: str | None = None
    date_end: str | None = None
    cost_basis: CostBasis | None = None
    cost_assumptions: dict[str, float] = Field(default_factory=dict)
    n_trials: int = Field(default=1, description="Nombre de configurations essayées dans cette expérience.")
    metrics: dict[str, float] = Field(default_factory=dict)
    metric_samples: dict[str, SampleTag] = Field(default_factory=dict)
    artifacts: list[str] = Field(default_factory=list)
    verdict: Verdict | None = None
    holdout_reads: int = Field(default=0, description="Combien de fois le holdout final a été consulté.")
    notes: str = ""


def current_git_sha(root: Path | None = None) -> tuple[str | None, bool | None]:
    """Rend l'empreinte du commit courant et l'état de l'arbre de travail.

    Args:
        root: le répertoire du dépôt. Le répertoire courant par défaut.

    Returns:
        Le couple ``(sha, dirty)``. Vaut ``(None, None)`` quand l'emplacement
        n'est pas un dépôt git, ce qui est une information et non une erreur :
        un résultat produit hors dépôt n'est pas rattachable à une version.
    """
    cwd = str(root) if root else None
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None, None
    return sha, bool(status)


def package_versions(packages: tuple[str, ...] = TRACKED_PACKAGES) -> dict[str, str]:
    """Rend la version installée de chaque paquet suivi.

    Un paquet absent porte la valeur ``"non installé"`` plutôt que d'être omis :
    savoir qu'il manquait fait partie de la trace.
    """
    out: dict[str, str] = {}
    for name in packages:
        try:
            out[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            out[name] = "non installé"
    return out


@dataclass
class RunContext:
    """Le contexte ouvert d'une expérience en cours.

    Il porte l'enregistrement en construction et le répertoire où déposer les
    artefacts. Il se ferme automatiquement à la sortie du bloc ``with``, même en
    cas d'exception : une expérience qui plante laisse une trace disant qu'elle
    a planté, ce qui vaut mieux qu'aucune trace.
    """

    record: ExperimentRecord
    directory: Path
    _metrics: dict[str, float] = field(default_factory=dict)
    _samples: dict[str, SampleTag] = field(default_factory=dict)
    _artifacts: list[str] = field(default_factory=list)
    _verdict: Verdict | None = None
    _holdout_reads: int = 0

    def log_metric(self, name: str, value: float, *, sample: SampleTag) -> None:
        """Enregistre une métrique avec l'échantillon auquel elle appartient.

        Args:
            name: le nom de la métrique, par exemple ``"sharpe"``.
            value: sa valeur.
            sample: ``IS``, ``VALIDATION``, ``OOS`` ou ``FINAL_HOLDOUT``.

        Note:
            L'étiquette d'échantillon est obligatoire, sans valeur par défaut.
            C'est la règle 5 du ``CLAUDE.md`` : un ratio de Sharpe sans son
            échantillon est un chiffre sans signification.
        """
        self._metrics[name] = float(value)
        self._samples[name] = sample
        if sample is SampleTag.FINAL_HOLDOUT:
            self._holdout_reads += 1
            _log.warning(
                "holdout final consulté",
                extra={"metric": name, "experiment_id": self.record.experiment_id},
            )

    def log_artifact(self, path: str | Path) -> None:
        """Rattache un fichier produit à l'expérience."""
        self._artifacts.append(str(path))

    def set_verdict(self, verdict: Verdict) -> None:
        """Fixe le verdict de l'expérience."""
        self._verdict = verdict

    def path(self, *parts: str) -> Path:
        """Rend un chemin dans le répertoire de l'expérience, créé au besoin."""
        p = self.directory.joinpath(*parts)
        ensure(p.parent)
        return p


class ExperimentRegistry:
    """Le registre : il ouvre, ferme et relit les expériences."""

    def __init__(self, root: Path | None = None) -> None:
        """Ouvre le registre.

        Args:
            root: le répertoire des artefacts. ``artifacts/`` par défaut.
        """
        self.root = ensure(root or artifacts_dir())
        self.index_path = self.root / INDEX_FILE

    @contextmanager
    def run(
        self,
        *,
        name: str,
        hypothesis: str,
        config: dict[str, Any] | None = None,
        seed: int | None = None,
        universe: list[str] | None = None,
        date_start: str | None = None,
        date_end: str | None = None,
        cost_basis: CostBasis | None = None,
        cost_assumptions: dict[str, float] | None = None,
        dataset_hashes: dict[str, str] | None = None,
        n_trials: int = 1,
        notes: str = "",
    ) -> Iterator[RunContext]:
        """Ouvre une expérience, la ferme et l'écrit à la sortie du bloc.

        Args:
            name: le nom court de l'expérience.
            hypothesis: l'hypothèse économique, en une phrase falsifiable.
            config: la configuration complète, sérialisée.
            seed: la graine des tirages.
            universe: les identifiants de l'univers.
            date_start: première date de l'échantillon.
            date_end: dernière date de l'échantillon.
            cost_basis: brut ou net.
            cost_assumptions: les hypothèses de coût, en points de base.
            dataset_hashes: les empreintes des jeux consommés.
            n_trials: le nombre de configurations essayées.
            notes: tout ce qui ne rentre pas ailleurs.

        Yields:
            Le contexte où déposer métriques, artefacts et verdict.
        """
        experiment_id = f"{name}-{uuid.uuid4().hex[:10]}"
        sha, dirty = current_git_sha()
        record = ExperimentRecord(
            experiment_id=experiment_id,
            name=name,
            hypothesis=hypothesis,
            created_at=dt.datetime.now(dt.UTC),
            git_sha=sha,
            git_dirty=dirty,
            seed=seed,
            python_version=sys.version.split()[0],
            platform=platform.platform(),
            package_versions=package_versions(),
            config=config or {},
            dataset_hashes=dataset_hashes or {},
            universe=universe or [],
            date_start=date_start,
            date_end=date_end,
            cost_basis=cost_basis,
            cost_assumptions=cost_assumptions or {},
            n_trials=n_trials,
            notes=notes,
        )
        directory = ensure(self.root / experiment_id)
        ctx = RunContext(record=record, directory=directory)
        _log.info("expérience ouverte", extra={"experiment_id": experiment_id, "name": name})
        try:
            yield ctx
        finally:
            final = record.model_copy(
                update={
                    "finished_at": dt.datetime.now(dt.UTC),
                    "metrics": ctx._metrics,
                    "metric_samples": ctx._samples,
                    "artifacts": ctx._artifacts,
                    "verdict": ctx._verdict,
                    "holdout_reads": ctx._holdout_reads,
                }
            )
            self._write(final, directory)
            _log.info(
                "expérience fermée",
                extra={
                    "experiment_id": experiment_id,
                    "verdict": final.verdict,
                    "n_metrics": len(final.metrics),
                },
            )

    def _write(self, record: ExperimentRecord, directory: Path) -> None:
        """Écrit l'enregistrement dans son répertoire et dans l'index."""
        payload = record.model_dump(mode="json")
        (directory / "experiment.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (directory / "metrics.json").write_text(
            json.dumps(
                {k: {"value": v, "sample": record.metric_samples.get(k)} for k, v in record.metrics.items()},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        with self.index_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def read_all(self) -> list[ExperimentRecord]:
        """Relit toutes les expériences enregistrées, dans l'ordre d'écriture."""
        if not self.index_path.is_file():
            return []
        out: list[ExperimentRecord] = []
        for line in self.index_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(ExperimentRecord.model_validate(json.loads(line)))
        return out

    def get(self, experiment_id: str) -> ExperimentRecord:
        """Rend une expérience par son identifiant.

        Raises:
            QuantLabError: si l'identifiant est inconnu.
        """
        for record in self.read_all():
            if record.experiment_id == experiment_id:
                return record
        raise QuantLabError(f"expérience inconnue : {experiment_id}")

    def trial_count(self, name_prefix: str) -> tuple[int, float]:
        """Compte les essais d'une famille et la variance de leurs Sharpe.

        C'est la fonction qui alimente le ratio de Sharpe dégonflé. Elle agrège
        le champ ``n_trials`` de chaque expérience dont le nom commence par le
        préfixe, et la variance des ratios de Sharpe enregistrés.

        Args:
            name_prefix: le préfixe de la famille, par exemple ``"tsmom"``.

        Returns:
            Le couple ``(nombre d'essais, variance des Sharpe)``. La variance
            vaut ``0.0`` quand moins de deux Sharpe sont enregistrés, et ce cas
            doit être traité par l'appelant plutôt que masqué.
        """
        records = [r for r in self.read_all() if r.name.startswith(name_prefix)]
        n_trials = sum(r.n_trials for r in records)
        sharpes = [v for r in records for k, v in r.metrics.items() if k.lower().startswith("sharpe")]
        if len(sharpes) < 2:
            return n_trials, 0.0
        mean = sum(sharpes) / len(sharpes)
        variance = sum((s - mean) ** 2 for s in sharpes) / (len(sharpes) - 1)
        return n_trials, variance

    def holdout_reads(self, name_prefix: str = "") -> int:
        """Compte les consultations du holdout final.

        Ce nombre se publie à côté des résultats. Après lecture, le holdout
        n'est plus hors échantillon, et le lecteur doit savoir combien de fois
        il a été regardé.
        """
        return sum(r.holdout_reads for r in self.read_all() if r.name.startswith(name_prefix))

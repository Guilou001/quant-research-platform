"""Le journal structuré, et pourquoi ``print`` est banni.

**Le problème.** Un ``print`` dispersé rend une ligne de texte que personne ne
peut filtrer, corréler à une expérience, ni retrouver six mois plus tard. Quand
trente backtests tournent, la sortie devient illisible au moment précis où elle
servirait.

**Le remède.** Un journal qui porte des champs plutôt que des phrases :
identifiant d'expérience, stratégie, étape, durée. La sortie humaine reste
lisible en console ; la sortie machine, en JSON par ligne, se relit avec
``duckdb`` comme n'importe quelle table.

Usage :

.. code-block:: python

    log = get_logger(__name__)
    with stage("chargement", experiment_id="exp-0042"):
        log.info("prix chargés", extra={"tickers": 8, "rows": 12_345})
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

# Pas de valeur par défaut mutable : un dictionnaire partagé entre contextes
# serait modifiable depuis n'importe où. Les lecteurs passent leur propre
# repli vide à « get ».
_CONTEXT: ContextVar[dict[str, Any]] = ContextVar("quantlab_log_context")

_RESERVED = frozenset(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys() | {"asctime", "message", "taskName"}
)


def bound_context() -> dict[str, Any]:
    """Rend les champs actuellement attachés au journal."""
    return dict(_CONTEXT.get({}))


@contextmanager
def bind(**fields: Any) -> Iterator[None]:
    """Attache des champs à toutes les lignes émises dans le bloc."""
    token = _CONTEXT.set({**_CONTEXT.get({}), **fields})
    try:
        yield
    finally:
        _CONTEXT.reset(token)


class _ContextFilter(logging.Filter):
    """Recopie les champs du contexte dans chaque enregistrement."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Ajoute les champs du contexte à l'enregistrement, puis le laisse passer."""
        for key, value in _CONTEXT.get({}).items():
            if key not in record.__dict__:
                record.__dict__[key] = value
        return True


class JsonFormatter(logging.Formatter):
    """Met une ligne de journal en JSON, un objet par ligne.

    Le format retenu est le JSON par ligne parce qu'il se lit avec
    ``duckdb.read_json_auto`` sans étape intermédiaire : le journal d'un mois de
    recherche devient une table interrogeable.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Rend une ligne JSON portant l'horodatage, le niveau et les champs liés."""
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


class HumanFormatter(logging.Formatter):
    """Met une ligne de journal en texte court, pour la console."""

    def format(self, record: logging.LogRecord) -> str:
        """Rend une ligne courte pour la console, champs liés en suffixe."""
        extras = {k: v for k, v in record.__dict__.items() if k not in _RESERVED and not k.startswith("_")}
        suffix = "  " + " ".join(f"{k}={v}" for k, v in extras.items()) if extras else ""
        horodatage = self.formatTime(record, "%H:%M:%S")
        return f"{horodatage} {record.levelname:<7} {record.name}  {record.getMessage()}{suffix}"


def configure_logging(
    level: str | int = "INFO",
    *,
    json_output: bool | None = None,
    stream: Any = None,
) -> None:
    """Installe le journal du processus. À appeler une fois, au démarrage.

    Args:
        level: seuil d'émission, ``"DEBUG"`` à ``"CRITICAL"``.
        json_output: force le format. Sans valeur, la variable d'environnement
            ``QUANTLAB_LOG_JSON`` décide, et la console reste en texte.
        stream: flux de sortie, ``sys.stderr`` par défaut.
    """
    if json_output is None:
        json_output = os.environ.get("QUANTLAB_LOG_JSON", "").lower() in {"1", "true", "yes"}
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(JsonFormatter() if json_output else HumanFormatter())
    handler.addFilter(_ContextFilter())
    root = logging.getLogger("quantlab")
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    root.propagate = False


def get_logger(name: str) -> logging.Logger:
    """Rend le journal d'un module, sous la racine ``quantlab``."""
    if not name.startswith("quantlab"):
        name = f"quantlab.{name}"
    return logging.getLogger(name)


@contextmanager
def stage(name: str, **fields: Any) -> Iterator[dict[str, Any]]:
    """Chronomètre une étape et la journalise, qu'elle réussisse ou non.

    Args:
        name: le nom de l'étape, par exemple ``"chargement"`` ou ``"backtest"``.
        **fields: champs à attacher, typiquement ``experiment_id``.

    Yields:
        Un dictionnaire mutable où l'étape peut déposer ce qu'elle veut voir
        journalisé à la sortie, par exemple un nombre de lignes traitées.
    """
    log = get_logger("quantlab.stage")
    payload: dict[str, Any] = {}
    started = time.perf_counter()
    with bind(stage=name, **fields):
        log.info("étape démarrée")
        try:
            yield payload
        except Exception as exc:
            log.error(
                "étape échouée",
                extra={"duration_s": round(time.perf_counter() - started, 4), "error": repr(exc)},
            )
            raise
        log.info(
            "étape terminée",
            extra={"duration_s": round(time.perf_counter() - started, 4), **payload},
        )


def new_experiment_id(prefix: str = "exp") -> str:
    """Rend un identifiant d'expérience court et unique."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"

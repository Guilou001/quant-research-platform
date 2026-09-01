"""La trace des expériences : ce qui a été essayé, et combien de fois.

Le décompte des essais n'est pas de la comptabilité. C'est un intrant de calcul :
le ratio de Sharpe dégonflé de Bailey et López de Prado (2014) a besoin du nombre
d'essais menés et de la dispersion de leurs résultats. Sous-déclarer ce nombre
rend le test inopérant, et c'est la raison de la règle 8 du ``CLAUDE.md``.
"""

from quantlab.experiments.registry import (
    ExperimentRecord,
    ExperimentRegistry,
    RunContext,
    current_git_sha,
)

__all__ = [
    "ExperimentRecord",
    "ExperimentRegistry",
    "RunContext",
    "current_git_sha",
]

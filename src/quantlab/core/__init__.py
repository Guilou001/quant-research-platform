"""Noyau : les contrats que tout le reste respecte.

Rien dans ``core`` ne connaît une source de données particulière, une
bibliothèque d'optimisation ou un moteur de backtest. C'est l'inversion de
dépendance qui rend remplaçable ``YahooProvider`` par un fournisseur
professionnel sans réécrire une seule stratégie.
"""

from quantlab.core.errors import (
    ConfigError,
    DataQualityError,
    InsufficientDataError,
    LookAheadError,
    QuantLabError,
)
from quantlab.core.types import AssetClass, Frequency, ReturnKind

__all__ = [
    "AssetClass",
    "ConfigError",
    "DataQualityError",
    "Frequency",
    "InsufficientDataError",
    "LookAheadError",
    "QuantLabError",
    "ReturnKind",
]

"""Phase 4. La mise à l'échelle transversale d'un signal, et son passage aux poids.

Un signal n'est pas un portefeuille. Ce sous-paquet porte les transformations qui
comparent les actifs entre eux à une date donnée, jamais un actif à son propre
passé, et la fonction qui déclare comment le signal devient des poids.

Le contenu vit dans :mod:`quantlab.signals.standardize`.
"""

from __future__ import annotations

from quantlab.signals.standardize import (
    cross_sectional_rank,
    cross_sectional_zscore,
    demean_by_group,
    neutralize_to_zero_net,
    robust_zscore,
    scale_to_gross,
    scale_to_net,
    signal_to_weights,
    winsorize,
)

__all__ = [
    "cross_sectional_rank",
    "cross_sectional_zscore",
    "demean_by_group",
    "neutralize_to_zero_net",
    "robust_zscore",
    "scale_to_gross",
    "scale_to_net",
    "signal_to_weights",
    "winsorize",
]

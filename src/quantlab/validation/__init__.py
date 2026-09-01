"""Ce qui sépare un résultat d'une coïncidence.

Le sous-paquet répond à une question et à une seule : ce chiffre survit-il au
fait que nous avons beaucoup cherché ? Huit modules y concourent, dans l'ordre
où on les emploie.

``splits``
    Le découpage du temps. Chronologique d'abord, puis walk-forward ancré ou
    glissant. La règle qui gouverne tout le reste est que l'entraînement précède
    le test, et :func:`splits.assert_chronological` la vérifie sur chaque pli.

``purging``
    La purge et l'embargo de López de Prado (2018), nécessaires dès qu'une
    étiquette couvre plusieurs périodes et déborde donc sur la période de test.

``cpcv``
    La validation croisée combinatoire purgée, qui rend une DISTRIBUTION de
    performance au lieu d'un point. Une stratégie de ratio de Sharpe 1,2 en
    moyenne qui s'étale de -0,3 à 2,6 n'est pas une stratégie de Sharpe 1,2.

``bootstrap``
    Le rééchantillonnage qui préserve la dépendance temporelle : blocs, blocs
    circulaires, et bootstrap stationnaire de Politis et Romano (1994).

``dsr``
    Le ratio de Sharpe probabiliste et le ratio de Sharpe dégonflé de Bailey et
    López de Prado. Ils exigent de connaître le nombre d'essais menés, ce qui
    est la raison de la règle 8 du ``CLAUDE.md``.

``pbo``
    La probabilité de surapprentissage de backtest, qui juge le PROCESSUS DE
    SÉLECTION et non la stratégie retenue.

``multiple_testing``
    Les corrections pour tests multiples, de Bonferroni au contrôle du taux de
    fausses découvertes, plus le contrôle de réalité de White et le test SPA de
    Hansen.

``robustness``
    Les balayages de paramètres, la recherche de plateaux plutôt que de pics,
    les sous-périodes, et le multiple de coûts à partir duquel la stratégie
    meurt.

L'interdit fondateur est écrit dans le code :
:func:`splits.train_test_split_forbidden` lève une erreur qui explique pourquoi
mélanger une série temporelle au hasard place l'avenir dans l'entraînement.
"""

from quantlab.validation import (
    bootstrap,
    cpcv,
    dsr,
    multiple_testing,
    pbo,
    purging,
    robustness,
    splits,
)
from quantlab.validation.splits import (
    ExpandingSplit,
    RollingSplit,
    TimeSplit,
    WalkForward,
    assert_chronological,
    chronological_split,
    split_report,
    train_test_split_forbidden,
)

__all__ = [
    "ExpandingSplit",
    "RollingSplit",
    "TimeSplit",
    "WalkForward",
    "assert_chronological",
    "bootstrap",
    "chronological_split",
    "cpcv",
    "dsr",
    "multiple_testing",
    "pbo",
    "purging",
    "robustness",
    "split_report",
    "splits",
    "train_test_split_forbidden",
]

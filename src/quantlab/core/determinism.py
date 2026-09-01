"""Le déterminisme : deux exécutions du même code rendent le même nombre.

**Le problème.** Un résultat qui bouge d'une exécution à l'autre ne peut être ni
vérifié, ni comparé, ni défendu. Pire, il masque les vrais changements : quand
un chiffre bouge après une modification, on ne sait pas si c'est la
modification ou le tirage.

**Le remède.** Une graine par expérience, déclarée dans la configuration,
propagée explicitement. Aucune fonction du laboratoire n'appelle
``numpy.random`` sans générateur : elles reçoivent un
``numpy.random.Generator`` en argument.

**Le piège mesuré à connaître.** Dériver des graines par ``seed + 1``,
``seed + 2`` ne donne PAS des tirages indépendants avec certains générateurs :
les flux se recouvrent. Le portefeuille en a fait l'expérience au dépôt 15, où
seize « graines indépendantes » recyclaient les trajectoires de leur voisine et
faussaient une mesure de biais. :func:`child_generators` utilise
``SeedSequence.spawn``, qui garantit l'indépendance par construction.
"""

from __future__ import annotations

import os
import random
from collections.abc import Iterator
from contextlib import contextmanager

import numpy as np


def make_generator(seed: int) -> np.random.Generator:
    """Rend un générateur aléatoire à partir d'une graine entière."""
    return np.random.default_rng(np.random.SeedSequence(seed))


def child_generators(seed: int, n: int) -> list[np.random.Generator]:
    """Rend ``n`` générateurs dont les flux sont indépendants par construction.

    Args:
        seed: la graine de l'expérience.
        n: le nombre de générateurs voulus, un par essai.

    Returns:
        Une liste de générateurs sans recouvrement de flux.

    Note:
        À utiliser partout où plusieurs essais doivent être indépendants :
        bootstrap, Monte-Carlo, essais multiples d'un même backtest. Ne jamais
        écrire ``default_rng(seed + i)`` à la place.
    """
    if n < 1:
        raise ValueError("n doit valoir au moins 1")
    return [np.random.default_rng(s) for s in np.random.SeedSequence(seed).spawn(n)]


@contextmanager
def deterministic(seed: int) -> Iterator[np.random.Generator]:
    """Fixe toutes les sources d'aléa du processus le temps du bloc.

    Fixe la graine de ``random``, celle de NumPy en interface héritée, et la
    variable ``PYTHONHASHSEED`` pour les codes qui dépendent de l'ordre
    d'itération d'un ensemble.

    Yields:
        Le générateur à passer explicitement aux fonctions du bloc.
    """
    py_state = random.getstate()
    # L'interface héritée de NumPy est visée VOLONTAIREMENT ici : le but du
    # bloc est justement de neutraliser l'état global que des bibliothèques
    # tierces continuent d'utiliser, puis de le rendre intact.
    np_state = np.random.get_state()  # noqa: NPY002
    old_hashseed = os.environ.get("PYTHONHASHSEED")
    random.seed(seed)
    np.random.seed(seed % (2**32 - 1))  # noqa: NPY002
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:
        yield make_generator(seed)
    finally:
        random.setstate(py_state)
        np.random.set_state(np_state)  # noqa: NPY002
        if old_hashseed is None:
            os.environ.pop("PYTHONHASHSEED", None)
        else:
            os.environ["PYTHONHASHSEED"] = old_hashseed

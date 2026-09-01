r"""La purge et l'embargo : retirer de l'entraînement ce qui connaît déjà le test.

**Le problème.** Une validation croisée ordinaire suppose que les observations
sont interchangeables. En finance, elles ne le sont pas. Une observation datée du
3 mars porte souvent une étiquette qui décrit le rendement des vingt séances
suivantes, donc jusqu'au 31 mars. Si le pli de test commence le 10 mars, cette
observation d'entraînement contient déjà une partie de la réponse. Le modèle
apprend le test, et le score dit « hors échantillon » mesure de la mémoire.

**La réponse du module.** Deux retraits, de López de Prado (2018), chapitre 7.
La purge retire de l'entraînement toute observation dont l'étiquette recouvre la
portée temporelle du test. L'embargo retire en plus les quelques observations qui
suivent cette portée, dont les traits partagent de l'information avec le test par
autocorrélation. Le mot « en plus » est à prendre au pied de la lettre :
:func:`purged_embargoed_split` ancre l'embargo là où la purge s'arrête, faute de
quoi il ne retirerait rien de neuf.

**La convention de ce module.** Les ensembles sont désignés par des positions
entières dans l'index, comme les découpages de ``scikit-learn`` et de
``skfolio``. L'index, lui, porte les dates. Une observation en position
:math:`i` a pour étiquette l'intervalle fermé
:math:`[\mathrm{index}[i],\ \mathrm{fin}[i]]`, où ``fin`` vient de
:func:`make_label_endtimes`. Rien n'est décalé en silence.

**Ce que la purge coûte, chiffré.** La purge retire des observations, donc elle
rétrécit l'entraînement. L'ordre de grandeur se calcule à la main, et le
résultat est MODÉLISÉ, pas mesuré :

- 1 000 observations quotidiennes, horizon d'étiquette de 20 jours, 10 plis ;
- chaque pli de test compte 1 000 / 10 = 100 observations, l'entraînement 900 ;
- une observation en position :math:`p` avant le test voit son étiquette finir en
  :math:`p + 20`, donc elle touche le test dès que :math:`p \ge d - 20`, où
  :math:`d` est la première position du test ;
- cela fait exactement 20 observations purgées à la frontière qui précède le
  test, soit 20 / 1 000 = 2,0 % de l'échantillon ;
- la frontière qui suit le test en coûte 20 autres, la portée du test s'étendant
  jusqu'à la fin de l'étiquette de sa dernière observation, en :math:`f + 20` ;
- un pli intérieur a deux frontières, donc il perd 40 / 900, soit 4,4 % de
  l'entraînement. Le premier et le dernier pli n'en ont qu'une, donc 20 / 900,
  soit 2,2 % ;
- un embargo de 1 % retire 10 observations DE PLUS, au-delà de la frontière
  déjà purgée, ce qui porte la perte d'un pli intérieur à 50 / 900, soit 5,6 %.

Le même calcul avec un horizon d'un an, 250 séances, donne 500 / 900 = 55,6 %
de l'entraînement retiré sur un pli intérieur, 250 avant et 250 après. La purge
n'est donc anodine que si l'horizon d'étiquette reste petit devant la taille
d'un pli. :func:`overlap_fraction` mesure cette part sur un cas réel plutôt que
de la supposer.

**Pourquoi la purge ne suffit pas.** Elle raisonne sur les étiquettes, donc elle
ne voit que la fuite qui passe par elles. Une observation postérieure au test
peut avoir une étiquette entièrement postérieure et rester contaminée : ses
traits sont calculés sur des fenêtres qui chevauchent le test, et les rendements
sont autocorrélés à court terme. L'embargo ferme cette porte-là, en aveugle,
sans hypothèse sur la façon dont les traits sont construits.

**Provenance.** López de Prado (2018), *Advances in Financial Machine
Learning*, Wiley, chapitre 7, sections 7.4.1 et 7.4.2, extraits 7.1 et 7.2. Les
trois conditions de recouvrement de l'extrait 7.1 sont reprises telles quelles,
ainsi que la règle d'embargo en pourcentage de l'échantillon de l'extrait 7.2.
L'équivalence des trois conditions avec l'intersection de deux intervalles est
démontrée dans la docstring de :func:`purge`.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.logging import get_logger

log = get_logger(__name__)

#: Fraction d'embargo par défaut, 1 % des observations. Statut : **précepte, et
#: sa source exacte est NON VÉRIFIÉE au 2026-09-01**. La valeur circule dans la
#: littérature appliquée en renvoi à López de Prado (2018), section 7.4.2, mais
#: aucune source consultable ce jour-là n'a permis de retrouver le chiffre dans
#: le texte. Trois recherches et deux récupérations de pages, dont un résumé
#: chapitre par chapitre de l'ouvrage, ne rendent que « a small embargo », sans
#: fraction. Le module ``splits`` porte la même réserve, et les deux ne doivent
#: pas diverger. Conséquence pratique : la valeur ne sert que de point de départ,
#: elle se règle sur ses propres données, et une étude qui la garde telle quelle
#: doit le déclarer.
DEFAULT_EMBARGO_FRACTION = 0.01

_NAT = np.datetime64("NaT", "ns")


# --------------------------------------------------------------------------- #
# Validation des entrées
# --------------------------------------------------------------------------- #


def _checked_index(index: pd.DatetimeIndex) -> np.ndarray:
    """Valide l'index du calendrier et rend ses valeurs NumPy.

    Args:
        index: l'index complet des observations, dans l'ordre du temps.

    Returns:
        Les dates en ``datetime64[ns]``.

    Raises:
        ConfigError: si l'index n'est pas un ``pandas.DatetimeIndex``.
        DataQualityError: si l'index porte des dates manquantes, s'il n'est pas
            croissant, ou s'il porte des doublons.
    """
    if not isinstance(index, pd.DatetimeIndex):
        raise ConfigError(f"index doit être un pandas.DatetimeIndex, pas {type(index).__name__}")
    if index.hasnans:
        raise DataQualityError("index porte des dates manquantes")
    if not index.is_monotonic_increasing:
        raise DataQualityError("index doit être croissant : les positions encodent l'ordre du temps")
    if not index.is_unique:
        raise DataQualityError("index porte des dates en double")
    return index.to_numpy()


def _checked_positions(values: Any, n_observations: int, name: str) -> np.ndarray:
    """Valide un ensemble de positions entières et le rend trié.

    Args:
        values: les positions, sous n'importe quelle forme acceptée par NumPy.
        n_observations: la taille de l'index, qui borne les positions.
        name: le nom de l'argument, pour le message d'erreur.

    Returns:
        Les positions triées, en ``int64``. L'ordre d'entrée n'est pas conservé.

    Raises:
        ConfigError: si une position sort des bornes ou apparaît deux fois.
    """
    arr = np.asarray(values).ravel()
    if arr.size == 0:
        return np.empty(0, dtype=np.int64)
    if not np.issubdtype(arr.dtype, np.integer):
        raise ConfigError(f"{name} doit porter des positions entières, pas {arr.dtype}")
    arr = arr.astype(np.int64)
    if arr.min() < 0 or arr.max() >= n_observations:
        raise ConfigError(f"{name} sort des bornes de l'index de taille {n_observations}")
    if np.unique(arr).size != arr.size:
        raise ConfigError(f"{name} porte des positions en double")
    return np.sort(arr)


def _checked_label_ends(label_end_times: pd.Series, index: pd.DatetimeIndex, used: np.ndarray) -> np.ndarray:
    """Valide les fins d'étiquette et rend leurs valeurs NumPy.

    La vérification des valeurs manquantes ne porte que sur les positions
    réellement jugées. Une étiquette non observable en fin d'échantillon peut
    donc rester ``NaT`` sans bloquer un pli qui ne la touche pas.

    Args:
        label_end_times: la fin d'étiquette de chaque observation, indexée
            exactement comme ``index``.
        index: l'index complet des observations.
        used: les positions dont la valeur sera lue.

    Returns:
        Les fins d'étiquette en ``datetime64[ns]``.

    Raises:
        ConfigError: si la série n'est pas alignée sur l'index, ou si son type
            n'est pas une date.
        DataQualityError: si une fin lue est manquante ou antérieure au début de
            sa propre étiquette.
    """
    if not isinstance(label_end_times, pd.Series):
        raise ConfigError("label_end_times doit être une pandas.Series")
    if not label_end_times.index.equals(index):
        raise ConfigError("label_end_times doit être indexée exactement comme index")
    if not pd.api.types.is_datetime64_any_dtype(label_end_times):
        raise ConfigError(f"label_end_times doit porter des dates, pas {label_end_times.dtype}")
    ends = label_end_times.to_numpy()
    if used.size and pd.isna(ends[used]).any():
        raise DataQualityError(
            "une étiquette lue n'a pas de fin connue : retirez ces observations du découpage"
        )
    starts = index.to_numpy()
    if used.size and (ends[used] < starts[used]).any():
        raise DataQualityError("une étiquette se termine avant de commencer")
    return ends


# --------------------------------------------------------------------------- #
# Les étiquettes et leur portée temporelle
# --------------------------------------------------------------------------- #


def label_spans(
    index: pd.DatetimeIndex,
    horizon: int | pd.Timedelta | dt.timedelta | pd.DateOffset,
    *,
    clip_tail: bool = True,
) -> pd.DataFrame:
    r"""Rend le début et la fin de l'étiquette de chaque observation.

    **Le problème.** Tout le reste du module a besoin d'une seule information :
    jusqu'à quand une observation regarde. Sans elle, aucune purge n'est
    calculable, et c'est le point que les découpages standards ignorent.

    **L'intuition.** Une observation datée de :math:`t` sert à prédire quelque
    chose qui ne sera connu qu'en :math:`t + h`. Son étiquette occupe donc
    l'intervalle :math:`[t,\ t + h]`, et non le seul instant :math:`t`.

    .. math::

        \text{début}_i = \mathrm{index}[i], \qquad
        \text{fin}_i = \mathrm{index}[\min(i + h,\ n - 1)]

    Définition de chaque variable :

    - :math:`i` la position de l'observation dans l'index, de 0 à :math:`n - 1` ;
    - :math:`h` l'horizon, en nombre de périodes de l'index ;
    - :math:`n` le nombre d'observations.

    Quand ``horizon`` est une durée plutôt qu'un entier, la fin vaut
    :math:`t + h` en temps de calendrier, puis se plafonne à la dernière date.

    Args:
        index: l'index complet des observations, croissant et sans doublon.
        horizon: le nombre de périodes de l'index, ou une durée
            (``pandas.Timedelta``, ``datetime.timedelta``, ``pandas.DateOffset``).
        clip_tail: quand vrai, les dernières étiquettes se plafonnent à la
            dernière date de l'index. Quand faux, elles valent ``NaT``.

    Returns:
        Un tableau à deux colonnes, ``start`` et ``end``, indexé comme ``index``.

    Raises:
        ConfigError: si ``horizon`` est négatif, ou si l'index n'est pas un
            ``DatetimeIndex``.
        DataQualityError: si l'index n'est pas croissant, unique et complet.

    Note:
        **Hypothèses.** L'horizon est le même pour toutes les observations.
        C'est faux pour la méthode des trois barrières de López de Prado (2018),
        chapitre 3, où l'étiquette se ferme dès qu'un seuil est touché. Dans ce
        cas, construisez la série de fins vous-même et passez-la telle quelle :
        le reste du module ne suppose rien d'autre qu'une fin par observation.

        **Limites.** Le plafonnement de la queue est un choix déclaré, pas une
        vérité. Les :math:`h` dernières observations n'ont pas d'étiquette
        observable, et ``clip_tail=False`` les marque ``NaT`` pour que l'appelant
        les écarte lui-même. Le plafonnement par défaut évite de propager des
        valeurs manquantes dans un découpage qui ne les touche pas.

        **Alternative.** Certaines implémentations décrivent l'étiquette par une
        durée fixe en jours de calendrier. Sur un index de séances, cela déplace
        la fin d'un ou deux jours autour des fins de semaine, donc les deux
        conventions ne purgent pas exactement les mêmes observations.

        **Vérification.** Avec ``horizon=0``, la fin égale le début partout, et
        la purge ne retire alors rien. Avec ``horizon=h``, la fin de
        l'observation :math:`i` est la date de l'observation :math:`i + h` tant
        que :math:`i + h < n`.
    """
    values = _checked_index(index)
    n = values.size
    if n == 0:
        raise InsufficientDataError("index vide : aucune étiquette à construire")

    if isinstance(horizon, bool):
        raise ConfigError("horizon doit être un entier ou une durée, pas un booléen")
    if isinstance(horizon, int | np.integer):
        if horizon < 0:
            raise ConfigError(f"horizon doit être positif ou nul, reçu {horizon}")
        targets = np.arange(n, dtype=np.int64) + int(horizon)
        clipped = values[np.minimum(targets, n - 1)]
        ends = clipped if clip_tail else np.where(targets < n, clipped, _NAT)
    else:
        shifted = (index + horizon).to_numpy()
        if (shifted < values).any():
            raise ConfigError("horizon doit être positif ou nul")
        ends = (
            np.minimum(shifted, values[-1]) if clip_tail else np.where(shifted <= values[-1], shifted, _NAT)
        )

    return pd.DataFrame({"start": values, "end": ends}, index=index)


def make_label_endtimes(
    index: pd.DatetimeIndex,
    horizon_periods: int,
    *,
    clip_tail: bool = True,
) -> pd.Series:
    """Rend la date de fin d'étiquette de chaque observation.

    C'est l'intrant de tout le reste du module. La fonction ne fait que déléguer
    à :func:`label_spans` et garder la colonne ``end``.

    Args:
        index: l'index complet des observations, croissant et sans doublon.
        horizon_periods: le nombre de périodes de l'index couvertes par une
            étiquette. Zéro décrit une étiquette instantanée.
        clip_tail: quand vrai, les dernières fins se plafonnent à la dernière
            date. Quand faux, elles valent ``NaT``.

    Returns:
        Une série de dates, indexée comme ``index``, nommée ``label_end``.

    Note:
        Pour un horizon exprimé en durée de calendrier, appelez directement
        :func:`label_spans`, qui accepte un ``Timedelta`` ou un ``DateOffset``.
    """
    ends = label_spans(index, horizon_periods, clip_tail=clip_tail)["end"]
    return ends.rename("label_end")


# --------------------------------------------------------------------------- #
# Portée du test et recouvrement
# --------------------------------------------------------------------------- #


def _merged_test_spans(
    test_positions: np.ndarray, starts: np.ndarray, ends: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Fusionne les étiquettes du test en intervalles disjoints et triés.

    La fusion sert deux fins. Elle rend le test correct quand ses positions ne
    sont pas contiguës, ce qui est le cas de la validation croisée
    combinatoire. Elle permet ensuite de décider chaque recouvrement par une
    seule recherche dichotomique.

    Args:
        test_positions: les positions du test, triées.
        starts: les dates de début de toutes les observations.
        ends: les dates de fin d'étiquette de toutes les observations.

    Returns:
        Deux tableaux de même longueur, les débuts et les fins des intervalles
        fusionnés, triés et sans recouvrement.
    """
    span_start = starts[test_positions]
    span_end = ends[test_positions]
    order = np.argsort(span_start, kind="stable")
    span_start = span_start[order]
    span_end = span_end[order]

    merged_start = [span_start[0]]
    merged_end = [span_end[0]]
    for i in range(1, span_start.size):
        if span_start[i] <= merged_end[-1]:
            merged_end[-1] = max(merged_end[-1], span_end[i])
        else:
            merged_start.append(span_start[i])
            merged_end.append(span_end[i])
    return (
        np.array(merged_start, dtype=starts.dtype),
        np.array(merged_end, dtype=ends.dtype),
    )


def _overlap_mask(
    train_positions: np.ndarray,
    starts: np.ndarray,
    ends: np.ndarray,
    span_start: np.ndarray,
    span_end: np.ndarray,
) -> np.ndarray:
    """Dit, pour chaque observation d'entraînement, si son étiquette touche le test.

    L'astuce qui rend le calcul vectoriel : les intervalles de test fusionnés
    sont triés et disjoints, donc leurs fins croissent aussi. Il suffit alors de
    tester le dernier intervalle dont le début n'est pas postérieur à la fin de
    l'étiquette examinée. Si celui-là ne touche pas, aucun autre ne touche.

    Args:
        train_positions: les positions candidates à l'entraînement, triées.
        starts: les dates de début de toutes les observations.
        ends: les dates de fin d'étiquette de toutes les observations.
        span_start: les débuts des intervalles de test fusionnés.
        span_end: leurs fins.

    Returns:
        Un masque booléen de la taille de ``train_positions``, vrai là où
        l'étiquette recouvre le test.
    """
    left = starts[train_positions]
    right = ends[train_positions]
    last = np.searchsorted(span_start, right, side="right") - 1
    mask = np.zeros(left.size, dtype=bool)
    reachable = last >= 0
    if reachable.any():
        mask[reachable] = span_end[last[reachable]] >= left[reachable]
    return mask


def _reach_bounds(
    positions: np.ndarray, span_start: np.ndarray, span_end: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Rend les bornes de position de chaque intervalle de test fusionné.

    Les intervalles sont donnés en dates ; il faut les positions de l'index pour
    compter des périodes et pour ancrer l'embargo. Les bornes sont fermées à
    gauche et ouvertes à droite, à la manière d'une tranche NumPy.

    Args:
        positions: les dates de l'index complet.
        span_start: les débuts des intervalles de test fusionnés.
        span_end: leurs fins.

    Returns:
        Deux tableaux d'entiers, la première position de chaque intervalle et la
        position qui suit sa dernière.
    """
    lo = np.searchsorted(positions, span_start, side="left")
    hi = np.searchsorted(positions, span_end, side="right")
    return lo, hi


def _test_reach_positions(test_positions: np.ndarray, positions: np.ndarray, ends: np.ndarray) -> np.ndarray:
    """Rend toutes les positions de l'index couvertes par la portée du test.

    C'est le test élargi à ses propres étiquettes. La purge retire déjà tout
    l'entraînement qui touche cet ensemble, donc l'embargo ancré dessus commence
    exactement là où la purge s'arrête.

    Args:
        test_positions: les positions du test, triées.
        positions: les dates de l'index complet.
        ends: les fins d'étiquette de toutes les observations.

    Returns:
        Les positions couvertes, triées et sans doublon.
    """
    span_start, span_end = _merged_test_spans(test_positions, positions, ends)
    lo, hi = _reach_bounds(positions, span_start, span_end)
    blocks = [np.arange(a, b, dtype=np.int64) for a, b in zip(lo, hi, strict=True)]
    return np.unique(np.concatenate(blocks)) if blocks else np.empty(0, dtype=np.int64)


# --------------------------------------------------------------------------- #
# La purge
# --------------------------------------------------------------------------- #


def purge(
    train_indices: Any,
    test_indices: Any,
    label_end_times: pd.Series,
    index: pd.DatetimeIndex,
) -> np.ndarray:
    r"""Retire de l'entraînement toute observation dont l'étiquette touche le test.

    **Le problème.** Un pli de test occupe une plage de dates, et ses étiquettes
    la débordent vers l'avant. Une observation d'entraînement dont l'étiquette
    entre dans cette plage a vu une partie du test avant d'être notée.

    **L'intuition.** Deux segments de temps, l'un pour l'observation
    d'entraînement, l'autre pour le test. S'ils se touchent, on jette
    l'observation d'entraînement. C'est tout le mécanisme.

    Le schéma, sur un exemple à quatorze observations et un horizon de deux
    périodes. Le test occupe les positions 6 à 9, donc sa portée temporelle
    court de la date 6 à la date 11, puisque l'étiquette de l'observation 9 finit
    en 11 :

    .. code-block:: text

        | position         0  1  2  3  4  5  6  7  8  9 10 11 12 13
        | rôle demandé     E  E  E  E  E  E  T  T  T  T  E  E  E  E
        | fin d'étiquette  2  3  4  5  6  7  8  9 10 11 12 13 13 13
        | portée du test                     *  *  *  *  *  *
        | purge                        x  x              x  x
        | entraînement     E  E  E  E        .  .  .  .        E  E

    Quatre observations partent. Les positions 4 et 5 précèdent le test mais
    leurs étiquettes finissent en 6 et 7, donc dedans. Les positions 10 et 11
    suivent le test, et pourtant elles commencent encore à l'intérieur de sa
    portée. Les positions 3 et 12 survivent, la première parce que son étiquette
    finit en 5, la seconde parce qu'elle commence en 12.

    **La règle, telle que l'extrait 7.1 l'écrit.** Une observation
    d'entraînement :math:`i` d'étiquette :math:`[a_i, b_i]` est retirée dès
    qu'une des trois conditions suivantes est vraie face à une étiquette de test
    :math:`[s_j, e_j]` :

    .. math::

        s_j \le a_i \le e_j
        \quad\text{ou}\quad
        s_j \le b_i \le e_j
        \quad\text{ou}\quad
        (a_i \le s_j \ \text{et}\ e_j \le b_i)

    Définition de chaque variable :

    - :math:`a_i` la date de l'observation d'entraînement, début de son étiquette ;
    - :math:`b_i` la date de fin de cette étiquette ;
    - :math:`s_j` la date d'une observation de test, début de son étiquette ;
    - :math:`e_j` la date de fin de cette étiquette.

    **Ces trois conditions n'en font qu'une.** Leur réunion est exactement
    l'intersection non vide de deux intervalles fermés :

    .. math::

        [a_i, b_i] \cap [s_j, e_j] \ne \emptyset
        \iff a_i \le e_j \ \text{et}\ b_i \ge s_j

    La démonstration tient en deux lignes. Si l'une des trois conditions est
    vraie, une borne de l'un des segments tombe dans l'autre, donc
    l'intersection contient au moins ce point. Réciproquement, si l'intersection
    est non vide, elle vaut :math:`[\max(a_i, s_j),\ \min(b_i, e_j)]`, dont la
    borne gauche appartient aux deux segments. L'implémentation retient la forme
    courte, qui se vectorise et évite trois passages sur les données.

    Args:
        train_indices: les positions candidates à l'entraînement.
        test_indices: les positions du test.
        label_end_times: la fin d'étiquette de chaque observation, indexée
            exactement comme ``index``. Voir :func:`make_label_endtimes`.
        index: l'index complet des observations.

    Returns:
        Les positions d'entraînement conservées, triées, en ``int64``.

    Raises:
        ConfigError: si les positions sortent des bornes, se répètent, ou si
            ``label_end_times`` n'est pas alignée sur ``index``.
        DataQualityError: si l'index est mal formé, ou si une étiquette lue n'a
            pas de fin connue.

    Note:
        **Hypothèses.** L'index est croissant et unique, et l'étiquette d'une
        observation est un intervalle fermé qui commence à sa propre date. Rien
        n'est supposé sur la contiguïté du test : la fonction fusionne d'abord
        les étiquettes de test en intervalles disjoints.

        **Provenance.** López de Prado (2018), *Advances in Financial Machine
        Learning*, extrait 7.1, ``getTrainTimes``.

        **Limites.** La purge ne voit que la fuite qui passe par l'étiquette.
        Un trait calculé sur une fenêtre glissante de 60 jours reste contaminé
        60 jours après la fin du test, et la purge n'en sait rien. C'est le rôle
        de :func:`embargo`.

        **Alternative.** La validation croisée bloquée écarte simplement une
        marge fixe de chaque côté du test. Elle est plus simple, mais elle ne
        s'adapte ni à un horizon variable ni à un test non contigu.

        **Vérification.** Trois contrôles. Un horizon nul ne retire rien, les
        segments se réduisant à des points disjoints. Un ensemble purgé est
        toujours inclus dans l'ensemble de départ. Après purge, aucune étiquette
        d'entraînement ne recoupe la portée du test, ce que
        :func:`leakage_report` recompte à zéro.
    """
    positions = _checked_index(index)
    n = positions.size
    train_positions = _checked_positions(train_indices, n, "train_indices")
    test_positions = _checked_positions(test_indices, n, "test_indices")
    if test_positions.size == 0 or train_positions.size == 0:
        return train_positions

    used = np.union1d(train_positions, test_positions)
    ends = _checked_label_ends(label_end_times, index, used)
    span_start, span_end = _merged_test_spans(test_positions, positions, ends)
    mask = _overlap_mask(train_positions, positions, ends, span_start, span_end)
    return train_positions[~mask]


# --------------------------------------------------------------------------- #
# L'embargo
# --------------------------------------------------------------------------- #


def _test_run_ends(test_positions: np.ndarray) -> np.ndarray:
    """Rend la dernière position de chaque suite contiguë de positions de test."""
    breaks = np.flatnonzero(np.diff(test_positions) > 1)
    return np.concatenate([test_positions[breaks], test_positions[-1:]])


def embargo(train_indices: Any, test_indices: Any, embargo_size: int) -> np.ndarray:
    r"""Retire de l'entraînement les observations qui suivent immédiatement le test.

    **Le problème.** La purge raisonne sur les étiquettes, donc elle laisse
    passer une fuite qu'aucune étiquette ne porte. Une observation datée du
    lendemain de la fin du test a des traits calculés sur des fenêtres qui
    recouvrent le test, et son rendement est corrélé au dernier rendement du
    test. Le modèle qui l'apprend apprend un peu du test.

    **Pourquoi la fuite va aussi dans ce sens.** L'autocorrélation des
    rendements est le mécanisme. Une volatilité, une moyenne mobile, un signal
    de momentum sont des fonctions du passé récent, donc du test lui-même quand
    l'observation le suit de peu. Ce n'est pas la même chose qu'un débordement
    d'étiquette : ici c'est le trait, et non la cible, qui contient le test.

    **Pourquoi seulement vers l'avant.** Le côté antérieur au test est déjà
    traité par la purge, qui retire toute étiquette débordant sur le test. Une
    observation antérieure dont l'étiquette s'arrête avant le test n'apprend
    rien de lui, l'information ne remontant pas le temps. L'asymétrie n'est donc
    pas une approximation : elle vient de la direction du temps.

    .. math::

        \mathcal{T}_{\text{embargo}} = \mathcal{T} \setminus
        \{\, p \in \mathcal{T} \ :\ \exists\, e \in E,\
        e < p \le e + m \,\}

    Définition de chaque variable :

    - :math:`\mathcal{T}` les positions d'entraînement reçues ;
    - :math:`E` les dernières positions de chaque bloc contigu de test ;
    - :math:`p` une position d'entraînement candidate ;
    - :math:`m` la taille de l'embargo, en nombre de périodes de l'index.

    Args:
        train_indices: les positions candidates à l'entraînement.
        test_indices: les positions qui servent d'ancre. Ce sont les positions du
            test quand l'embargo s'emploie seul. Quand il suit une purge, passez
            la portée du test, étiquettes comprises, comme le fait
            :func:`purged_embargoed_split`.
        embargo_size: le nombre de périodes retirées après chaque bloc d'ancres.
            Zéro désactive l'embargo. Voir
            :func:`embargo_size_from_fraction` pour la règle du 1 %.

    Returns:
        Les positions d'entraînement conservées, triées, en ``int64``.

    Raises:
        ConfigError: si ``embargo_size`` est négatif, ou si les positions se
            répètent.

    Note:
        **Hypothèses.** Les positions encodent l'ordre du temps, une période
        d'index valant une période d'embargo. Sur un index de séances, un
        embargo de 5 vaut donc une semaine de bourse et non sept jours.

        **Provenance.** López de Prado (2018), extrait 7.2, ``getEmbargoTimes``.
        L'auteur y exprime la taille en fraction du nombre d'observations.

        **Le piège de l'ancre.** Ancrer l'embargo sur la dernière observation du
        test, et non sur la fin de sa portée, le rend inopérant après une purge.
        La purge a déjà vidé les :math:`h` positions qui suivent le test, donc
        un embargo de taille :math:`m \le h` n'ajoute rien.
        :func:`purged_embargoed_split` évite le piège en lui passant la portée.

        **Limites.** La taille juste n'est pas connue. Elle devrait dépendre de
        la longueur de la mémoire des traits, que personne ne mesure en général,
        et le 1 % de l'auteur est un précepte, pas une mesure. Un embargo trop
        court laisse la fuite, un embargo trop long ampute l'entraînement sans
        contrepartie.

        **Alternative.** Un embargo symétrique, appliqué des deux côtés, se
        rencontre dans plusieurs implémentations. Il retire davantage sans rien
        ajouter quand la purge est déjà passée, la fuite antérieure étant
        entièrement portée par les étiquettes.

        **Vérification.** Avec un test contigu et assez d'observations après
        lui, un embargo de taille :math:`m` retire exactement :math:`m`
        observations d'entraînement. C'est le contrôle direct du test unitaire.
    """
    if isinstance(embargo_size, bool) or not isinstance(embargo_size, int | np.integer):
        raise ConfigError(f"embargo_size doit être un entier, pas {type(embargo_size).__name__}")
    if embargo_size < 0:
        raise ConfigError(f"embargo_size doit être positif ou nul, reçu {embargo_size}")

    train_arr = np.asarray(train_indices).ravel()
    test_arr = np.asarray(test_indices).ravel()
    bound = int(max(train_arr.max(initial=-1), test_arr.max(initial=-1))) + 1
    train_positions = _checked_positions(train_arr, max(bound, 1), "train_indices")
    test_positions = _checked_positions(test_arr, max(bound, 1), "test_indices")
    if embargo_size == 0 or test_positions.size == 0 or train_positions.size == 0:
        return train_positions

    run_ends = _test_run_ends(test_positions)
    candidate = train_positions[:, None]
    banned = ((candidate > run_ends) & (candidate <= run_ends + int(embargo_size))).any(axis=1)
    return train_positions[~banned]


def embargo_size_from_fraction(n_observations: int, fraction: float = DEFAULT_EMBARGO_FRACTION) -> int:
    r"""Rend la taille d'embargo correspondant à une fraction de l'échantillon.

    **Le problème.** L'extrait 7.2 exprime l'embargo en pourcentage du nombre
    d'observations, pas en nombre de périodes. Cette fonction fait la conversion
    à un seul endroit, plutôt que dans chaque appelant.

    .. math::

        m = \left\lfloor \delta \, T \right\rfloor

    Définition de chaque variable :

    - :math:`m` la taille de l'embargo, en périodes ;
    - :math:`\delta` la fraction demandée, 0,01 par défaut ;
    - :math:`T` le nombre d'observations de l'échantillon.

    Args:
        n_observations: le nombre total d'observations :math:`T`.
        fraction: la fraction :math:`\delta`, entre 0 et 1 inclus.

    Returns:
        La taille d'embargo, entière et positive ou nulle. La partie entière
        inférieure suit l'extrait 7.2, qui tronque.

    Raises:
        ConfigError: si le nombre d'observations est négatif, ou si la fraction
            sort de l'intervalle de 0 à 1.

    Note:
        La valeur par défaut est un PRÉCEPTE de López de Prado (2018), sans
        mesure derrière. Avec 1 000 observations, elle donne 10 périodes.
    """
    if n_observations < 0:
        raise ConfigError(f"n_observations doit être positif ou nul, reçu {n_observations}")
    if not 0.0 <= fraction <= 1.0:
        raise ConfigError(f"fraction doit être entre 0 et 1, reçu {fraction}")
    return math.floor(fraction * n_observations)


# --------------------------------------------------------------------------- #
# Les deux ensemble
# --------------------------------------------------------------------------- #


def purged_embargoed_split(
    train_indices: Any,
    test_indices: Any,
    label_end_times: pd.Series,
    index: pd.DatetimeIndex,
    embargo_size: int = 0,
) -> np.ndarray:
    r"""Applique la purge, puis l'embargo au-delà de la frontière déjà purgée.

    **Le point qui décide, et qu'il est facile de rater.** L'embargo ne s'ancre
    PAS sur la dernière observation du test. Il s'ancre sur la fin de la portée
    du test, étiquettes comprises. Sans cela, il ne retirerait rien de neuf tant
    que sa taille resterait sous l'horizon d'étiquette, puisque la purge a déjà
    vidé cette zone.

    Le compte, sur un pli de test contigu :math:`[d, f]`, un horizon
    :math:`h` et un embargo :math:`m` :

    .. math::

        \text{purgé} = [d - h,\ d - 1] \cup [f + 1,\ f + h],
        \qquad
        \text{embargoué} = [f + h + 1,\ f + h + m]

    Les deux ensembles sont disjoints, donc l'embargo retire bien :math:`m`
    observations de plus. C'est ce que fait ``skfolio``, dont
    ``CombinatorialPurgedCV`` retire ``purged_size + embargo_size`` observations
    après un bloc de test. L'extrait 7.3 de López de Prado démarre son embargo
    une position plus tôt, sur une observation que la purge a déjà retirée. Il
    n'en ajoute donc que :math:`m - 1`. L'écart entre les deux conventions vaut
    une observation, et le choix retenu ici est celui de ``skfolio``.

    Args:
        train_indices: les positions candidates à l'entraînement.
        test_indices: les positions du test.
        label_end_times: la fin d'étiquette de chaque observation, indexée
            exactement comme ``index``.
        index: l'index complet des observations.
        embargo_size: le nombre de périodes retirées au-delà de la portée de
            chaque bloc de test. Voir :func:`embargo_size_from_fraction`.

    Returns:
        Les positions d'entraînement conservées, triées, en ``int64``.

    Note:
        **Vérification.** Sur un découpage sans étiquette débordante, horizon
        nul, la fonction se réduit à l'embargo seul. Sur un horizon :math:`h` et
        un embargo :math:`m`, elle retire exactement :math:`h` observations
        avant le test et :math:`h + m` après, tant que l'échantillon les porte.
        Le test unitaire compare le résultat à celui de ``skfolio``.

        Le nombre d'observations retirées par chaque étape est journalisé au
        niveau ``DEBUG``. Un entraînement qui fond de moitié est une information
        de recherche, pas un détail d'exécution.
    """
    positions = _checked_index(index)
    n = positions.size
    train_positions = _checked_positions(train_indices, n, "train_indices")
    test_positions = _checked_positions(test_indices, n, "test_indices")
    kept_after_purge = purge(train_positions, test_positions, label_end_times, index)

    anchor = test_positions
    if embargo_size and test_positions.size and kept_after_purge.size:
        used = np.union1d(train_positions, test_positions)
        ends = _checked_label_ends(label_end_times, index, used)
        anchor = _test_reach_positions(test_positions, positions, ends)
    kept = embargo(kept_after_purge, anchor, embargo_size)
    log.debug(
        "découpage purgé et embargoué",
        extra={
            "n_train_initial": int(train_positions.size),
            "n_purged": int(train_positions.size - kept_after_purge.size),
            "n_embargoed": int(kept_after_purge.size - kept.size),
            "n_train_final": int(kept.size),
        },
    )
    return kept


# --------------------------------------------------------------------------- #
# Le diagnostic
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class LeakageReport:
    """Le compte de ce qui fuit d'un entraînement vers un test.

    Attributes:
        n_train: le nombre d'observations d'entraînement examinées.
        n_test: le nombre d'observations de test.
        n_overlapping: le nombre d'observations d'entraînement dont l'étiquette
            recouvre la portée du test. C'est exactement ce que :func:`purge`
            retirerait.
        overlap_fraction: la part contaminée de l'entraînement, entre 0 et 1.
        max_overlap_periods: le recouvrement maximal, compté en observations de
            l'index situées à la fois dans une étiquette d'entraînement et dans
            la portée du test.
        test_span_start: la première date de la portée du test.
        test_span_end: la dernière date de cette portée, fins d'étiquette
            comprises.
        n_test_blocks: le nombre d'intervalles disjoints formés par le test.
    """

    n_train: int
    n_test: int
    n_overlapping: int
    overlap_fraction: float
    max_overlap_periods: int
    test_span_start: pd.Timestamp | None
    test_span_end: pd.Timestamp | None
    n_test_blocks: int

    def as_dict(self) -> dict[str, Any]:
        """Rend le rapport sous forme de dictionnaire, prêt pour un tableau."""
        return dict(asdict(self))


def leakage_report(
    train_indices: Any,
    test_indices: Any,
    label_end_times: pd.Series,
    index: pd.DatetimeIndex,
) -> LeakageReport:
    r"""Compte ce qui fuit d'un entraînement vers un test, sans rien retirer.

    **Le problème.** La purge retire des observations, mais elle ne dit pas
    combien ni de combien. Or la décision d'accepter un découpage se prend sur
    ces deux nombres : une contamination de 2 % ne se traite pas comme une
    contamination de 30 %.

    **L'intuition.** On compte deux choses. Combien d'observations
    d'entraînement touchent le test, et de combien de périodes la pire d'entre
    elles y entre. Le premier nombre dit l'étendue du problème, le second sa
    profondeur.

    .. math::

        c_i = \#\{\, t \ :\ a_i \le \mathrm{index}[t] \le b_i
        \ \text{et}\ \mathrm{index}[t] \in \mathcal{S} \,\}

    Définition de chaque variable :

    - :math:`c_i` le recouvrement de l'observation :math:`i`, en périodes ;
    - :math:`[a_i, b_i]` l'étiquette de l'observation d'entraînement :math:`i` ;
    - :math:`\mathcal{S}` la réunion des étiquettes de test ;
    - :math:`t` une position de l'index complet.

    Le rapport rend :math:`\max_i c_i` et le nombre d'observations dont
    l'étiquette recoupe :math:`\mathcal{S}`.

    Args:
        train_indices: les positions candidates à l'entraînement.
        test_indices: les positions du test.
        label_end_times: la fin d'étiquette de chaque observation, indexée
            exactement comme ``index``.
        index: l'index complet des observations.

    Returns:
        Un :class:`LeakageReport` gelé.

    Raises:
        InsufficientDataError: si l'entraînement est vide, la part contaminée
            n'étant alors pas définie.
        ConfigError: si les positions ou l'alignement de la série sont invalides.
        DataQualityError: si l'index ou les fins d'étiquette sont mal formés.

    Note:
        **Hypothèses.** Les mêmes que :func:`purge`, dont la fonction reprend le
        prédicat de recouvrement à l'identique. Les deux comptes sont donc
        cohérents par construction.

        **Limites.** ``max_overlap_periods`` compte des observations de l'index,
        pas des jours de calendrier. Si une fin d'étiquette fournie à la main ne
        tombe sur aucune date de l'index, un recouvrement réel peut se compter
        zéro alors que ``n_overlapping`` le signale. Le cas ne se produit pas
        avec les fins construites par :func:`make_label_endtimes`.

        **Alternative.** Mesurer la fuite par la performance, en comparant le
        score avant et après purge. C'est plus parlant et beaucoup plus cher,
        puisqu'il faut réestimer le modèle. Le compte ci-dessus se calcule avant
        toute estimation.

        **Vérification.** Après :func:`purge`, un second rapport sur l'ensemble
        conservé rend ``n_overlapping`` nul. Avec un horizon nul, le rapport
        rend zéro sur tout découpage disjoint.
    """
    positions = _checked_index(index)
    n = positions.size
    train_positions = _checked_positions(train_indices, n, "train_indices")
    test_positions = _checked_positions(test_indices, n, "test_indices")
    if train_positions.size == 0:
        raise InsufficientDataError("entraînement vide : la part contaminée n'est pas définie")
    if test_positions.size == 0:
        return LeakageReport(
            n_train=int(train_positions.size),
            n_test=0,
            n_overlapping=0,
            overlap_fraction=0.0,
            max_overlap_periods=0,
            test_span_start=None,
            test_span_end=None,
            n_test_blocks=0,
        )

    used = np.union1d(train_positions, test_positions)
    ends = _checked_label_ends(label_end_times, index, used)
    span_start, span_end = _merged_test_spans(test_positions, positions, ends)
    mask = _overlap_mask(train_positions, positions, ends, span_start, span_end)

    # Les positions de l'index qui tombent dans la portée du test, puis leur
    # somme cumulée : le recouvrement d'une étiquette est alors une soustraction.
    in_reach = np.zeros(n, dtype=np.int64)
    lo, hi = _reach_bounds(positions, span_start, span_end)
    for start, stop in zip(lo, hi, strict=True):
        in_reach[start:stop] = 1
    cumulative = np.concatenate([[0], np.cumsum(in_reach)])

    left = train_positions
    right = np.searchsorted(positions, ends[train_positions], side="right")
    overlap_periods = cumulative[right] - cumulative[left]

    return LeakageReport(
        n_train=int(train_positions.size),
        n_test=int(test_positions.size),
        n_overlapping=int(mask.sum()),
        overlap_fraction=float(mask.mean()),
        max_overlap_periods=int(overlap_periods.max(initial=0)),
        test_span_start=pd.Timestamp(span_start.min()),
        test_span_end=pd.Timestamp(span_end.max()),
        n_test_blocks=int(span_start.size),
    )


def overlap_fraction(
    train_indices: Any,
    test_indices: Any,
    label_end_times: pd.Series,
    index: pd.DatetimeIndex,
) -> float:
    """Rend la part de l'entraînement que la purge retirerait.

    C'est le nombre qui décide si la purge change quelque chose. En dessous de
    quelques pour cent, elle rogne les marges. Au-dessus de vingt pour cent, la
    question n'est plus la purge mais l'horizon d'étiquette, trop long pour la
    taille des plis.

    Args:
        train_indices: les positions candidates à l'entraînement.
        test_indices: les positions du test.
        label_end_times: la fin d'étiquette de chaque observation, indexée
            exactement comme ``index``.
        index: l'index complet des observations.

    Returns:
        La part contaminée, entre 0 et 1.

    Raises:
        InsufficientDataError: si l'entraînement est vide.

    Note:
        La fonction délègue à :func:`leakage_report`, donc les deux comptes ne
        peuvent pas diverger.
    """
    return leakage_report(train_indices, test_indices, label_end_times, index).overlap_fraction

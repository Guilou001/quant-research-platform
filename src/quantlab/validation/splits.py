r"""Le découpage du temps, et la raison pour laquelle il ne se mélange jamais.

**Le problème.** Une mesure hors échantillon ne vaut que si l'échantillon de
test était réellement inconnu au moment de l'apprentissage. Sur une série
temporelle, cette condition ne s'obtient pas par hasard : elle s'obtient par la
forme du découpage. Un découpage mal fait rend un chiffre flatteur qui ne
survivra pas au premier mois de production.

**L'intuition.** Le temps a un sens, et la validation doit l'imiter. Un modèle
qui décide au 31 mars 2015 ne dispose que du passé de cette date. Le découpage
correct place donc toujours l'entraînement avant le test, jamais autour.

**Le mécanisme exact de la fuite par mélange.** ``train_test_split(shuffle=True)``
tire les observations au hasard. Une observation de 2020 part alors en
entraînement, une observation de 2015 part en test. Le modèle apprend l'avenir,
puis on lui demande de le rendre au passé. La mesure annoncée hors échantillon
devient une mesure dans l'échantillon, sans que rien ne le signale.

**Trois canaux, et non un seul.** Le premier est le mélange direct décrit
ci-dessus. Le deuxième est le recouvrement des étiquettes : une étiquette
construite sur le rendement des vingt jours suivants déborde sur la période de
test voisine. Le troisième est la persistance des variables explicatives : une
moyenne mobile sur soixante jours calculée après le bloc de test contient ce
bloc de test.

**Ce que le module oppose à chacun.** Le mélange est interdit par une fonction
qui lève, :func:`train_test_split_forbidden`. Le recouvrement des étiquettes est
traité par la purge, qui retire les observations d'entraînement collées à
gauche du bloc de test. La persistance est traitée par l'embargo, qui retire les
observations collées à droite.

**La formule du nombre de plis.** Pour :math:`n` observations, une fenêtre
d'entraînement de :math:`L_{tr}` observations, un bloc de test de :math:`L_{te}`
observations et un pas :math:`s`, le nombre de plis vaut :

.. math::

    K = \left\lfloor \frac{n - L_{tr} - L_{te}}{s} \right\rfloor + 1
    \qquad \text{si } n \ge L_{tr} + L_{te}

où :math:`\lfloor \cdot \rfloor` est la partie entière par défaut. Le bloc de
test du pli :math:`k`, avec :math:`k = 0, \dots, K-1`, occupe les positions :

.. math::

    S_k = \left[\, L_{tr} + k s,\; L_{tr} + k s + L_{te} \,\right)

Les fenêtres d'entraînement s'écrivent, pour la variante glissante puis pour la
variante ancrée, en notant :math:`p` la purge et :math:`E` l'ensemble sous
embargo :

.. math::

    R_k = \left[\, k s,\; L_{tr} + k s - p \,\right) \setminus E
    \qquad
    A_k = \left[\, 0,\; L_{tr} + k s - p \,\right) \setminus E

.. math::

    E = \bigcup_{k=0}^{K-1}
        \left[\, L_{tr} + k s + L_{te},\;
                 L_{tr} + k s + L_{te} + e \,\right)

où :math:`e` est la taille de l'embargo. La fenêtre glissante garde une longueur
constante de :math:`L_{tr} - p` observations. La fenêtre ancrée croît d'un pas à
chaque pli.

**Une conséquence de ces formules, contre-intuitive et vérifiée.** L'embargo du
pli :math:`j` ne mord sur la fenêtre d'entraînement du pli :math:`k` que si sa
zone commence avant la fin de cette fenêtre, soit :

.. math::

    L_{tr} + j s + L_{te} < L_{tr} + k s - p
    \qquad \Longleftrightarrow \qquad
    (k - j)\, s > L_{te} + p

Avec un pas égal au bloc de test et sans purge, la condition se lit
:math:`k \ge j + 2`. Le pli qui suit immédiatement un bloc de test ne perd donc
rien, et chacun des suivants perd :math:`e` observations par bloc de test
antérieur. Mesuré sur cent positions, avec une fenêtre de 50, un bloc de test de
10 et un embargo de 5, les cinq fenêtres ancrées portent 50, 60, 65, 70 puis 75
observations. Les cinq fenêtres glissantes portent 50, 50, 45, 40 puis 35.

**Les hypothèses.** L'index est trié par ordre chronologique croissant, sans
doublon. Une observation porte une seule date, celle à laquelle elle était
connaissable. Les positions sont contiguës : le module compte en observations,
pas en jours de calendrier.

**La provenance.** L'analyse glissante vient de Pardo (1992), *Design, Testing
and Optimization of Trading Systems*, reprise et développée dans Pardo (2008),
*The Evaluation and Optimization of Trading Strategies*, 2e édition, Wiley,
chapitre 11. La purge et l'embargo viennent de López de Prado (2018), *Advances
in Financial Machine Learning*, Wiley, sections 7.4.1 et 7.4.2. Le contre
exemple du mélange sur données dépendantes est traité par Bergmeir et Benítez
(2012), *Information Sciences*, volume 191, pages 192 à 213. Une règle générale s'y ajoute :
toute étape qui touche aux données doit entrer dans la validation croisée. Elle
vient de Hastie, Tibshirani et Friedman (2009), *The Elements of Statistical
Learning*, 2e édition, section « The Wrong and Right Way to Do Cross-validation ».
Statut de ces références, par honnêteté et non par prudence. **Deux ont été
vérifiées en ligne le 2026-09-01** pour les auteurs, l'année et la pagination :
Bergmeir et Benítez, et Bailey et coauteurs. **Deux ne l'ont pas été** : Pardo
(2008), dont le chapitre est cité sans page, et López de Prado (2018), dont les
sections 7.4.1 et 7.4.2 n'ont pu être consultées. La section de Hastie,
Tibshirani et Friedman est citée par son titre, non vérifié. La fraction
d'embargo de 1 % que porte :mod:`quantlab.validation.purging` relève de la même
réserve : elle est un précepte dont la source exacte reste non vérifiée.

**Les limites.** Le module découpe des positions, pas du calendrier. Une purge
de dix observations vaut dix séances sur une série quotidienne et dix mois sur
une série mensuelle. Le module ignore aussi l'horizon réel des étiquettes : il
ne sait pas qu'une étiquette à vingt jours exige une purge d'au moins vingt
observations, et c'est à l'appelant de le déclarer.

**Les alternatives.** La validation croisée en k blocs mélangés est plus
efficace en données et fausse ici. La séparation simple en deux morceaux est
correcte mais rend une seule mesure, donc sans erreur type. La validation croisée
combinatoire purgée de López de Prado rend plusieurs chemins hors échantillon,
au prix d'un recouvrement entre eux dont il faut tenir compte.

**Pourquoi ce choix ici.** L'analyse glissante donne plusieurs mesures hors
échantillon tout en respectant l'ordre du temps, ce qui permet de regarder la
stabilité d'un résultat plutôt que son seul niveau moyen.

**Comment vérifier.** Trois contrôles vivent dans
``tests/unit/test_validation_splits.py``. Un découpage à la main sur cent dates
retrouve des bornes connues d'avance. Le nombre de plis est comparé à la formule
ci-dessus calculée à la main. Une propriété ``hypothesis`` vérifie que la
dernière position d'entraînement précède strictement la première position de
test, pour tout réglage admissible.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from itertools import pairwise
from typing import Any

import numpy as np
import pandas as pd

from quantlab.core.errors import (
    ConfigError,
    DataQualityError,
    InsufficientDataError,
    LookAheadError,
)
from quantlab.core.logging import get_logger
from quantlab.core.types import SampleTag

_LOG = get_logger(__name__)

#: Purge par défaut. Zéro, parce qu'une purge non nulle est une hypothèse sur
#: l'horizon des étiquettes, et qu'une hypothèse se déclare.
DEFAULT_PURGE: int = 0

#: Embargo par défaut. Zéro, pour la même raison que la purge.
DEFAULT_EMBARGO: int = 0

#: Les quatre segments d'un découpage chronologique, dans l'ordre du temps.
SEGMENT_NAMES: tuple[str, str, str, str] = ("train", "validation", "test", "final_holdout")

#: L'étiquette d'échantillon attachée à chaque segment. Elle voyage avec le
#: chiffre jusqu'au rapport, sans quoi un ratio de Sharpe perd sa signification.
SEGMENT_TAGS: dict[str, SampleTag] = {
    "train": SampleTag.IN_SAMPLE,
    "validation": SampleTag.VALIDATION,
    "test": SampleTag.OUT_OF_SAMPLE,
    "final_holdout": SampleTag.FINAL_HOLDOUT,
}

#: Les colonnes du tableau rendu par :func:`split_report` pour un découpage fixe.
TIME_SPLIT_REPORT_COLUMNS: tuple[str, ...] = ("segment", "tag", "start", "end", "n_obs", "share")

#: Les colonnes du tableau rendu par :func:`split_report` pour une analyse glissante.
WALK_FORWARD_REPORT_COLUMNS: tuple[str, ...] = ("fold", "part", "start", "end", "n_obs", "share")

_SHUFFLE_MESSAGE = (
    "Le mélange aléatoire est interdit sur une série temporelle. "
    "Mécanisme de la fuite : le tirage au hasard place des observations de 2020 "
    "dans l'entraînement et des observations de 2015 dans le test. Le modèle "
    "apprend l'avenir, puis on lui demande de le rendre au passé. Ce qui est "
    "annoncé comme une mesure hors échantillon devient une mesure dans "
    "l'échantillon, et rien dans la sortie ne le signale. "
    "Employer à la place quantlab.validation.splits.chronological_split pour un "
    "découpage fixe, ou WalkForward pour plusieurs mesures hors échantillon. "
    "Référence : Bergmeir et Benítez (2012), Information Sciences 191, 192-213."
)


def _as_index(values: Any, *, label: str) -> pd.Index:
    """Rend un ``pandas.Index`` trié et sans doublon, ou lève.

    Args:
        values: l'objet à contrôler.
        label: le nom employé dans les messages d'erreur.

    Returns:
        L'objet inchangé, une fois les trois contrôles passés.

    Raises:
        TypeError: l'objet n'est pas un ``pandas.Index``.
        DataQualityError: l'index porte des doublons ou n'est pas croissant.
    """
    if not isinstance(values, pd.Index):
        raise TypeError(f"{label} doit être un pandas.Index, reçu {type(values).__name__}")
    if values.has_duplicates:
        doublons = values[values.duplicated()].tolist()[:5]
        raise DataQualityError(
            f"{label} porte des étiquettes en double, par exemple {doublons}. "
            "Deux observations à la même date rendent l'ordre du temps ambigu."
        )
    if len(values) > 1 and not values.is_monotonic_increasing:
        raise DataQualityError(
            f"{label} n'est pas croissant. Le découpage chronologique suppose "
            "un index trié par date, du plus ancien au plus récent."
        )
    return values


def _as_bound(index: pd.Index, value: Any, *, label: str) -> Any:
    """Rend une borne comparable à l'index, en réglant le fuseau horaire.

    Args:
        index: l'index sur lequel la borne sera comparée.
        value: la borne, sous forme de texte, de date ou d'horodatage.
        label: le nom employé dans les messages d'erreur.

    Returns:
        La borne convertie. Un index temporel rend un ``pandas.Timestamp``,
        localisé sur le fuseau de l'index quand celui-ci en porte un.

    Raises:
        ConfigError: la borne n'est pas convertible en horodatage.
    """
    if not isinstance(index, pd.DatetimeIndex):
        return value
    try:
        moment = pd.Timestamp(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{label} n'est pas une date lisible : {value!r}") from exc
    if index.tz is not None and moment.tz is None:
        return moment.tz_localize(index.tz)
    if index.tz is None and moment.tz is not None:
        return moment.tz_localize(None)
    return moment


def _n_observations(data: Any, *, label: str = "X") -> int:
    """Rend le nombre d'observations d'un objet de données.

    Args:
        data: un tableau, une série, un index, une suite, ou directement un
            entier valant le nombre d'observations.
        label: le nom employé dans les messages d'erreur.

    Returns:
        Le nombre de lignes.

    Raises:
        ConfigError: l'objet est absent ou n'a pas de longueur.
        InsufficientDataError: l'objet est vide.
    """
    if data is None:
        raise ConfigError(
            f"{label} est absent. Le nombre de plis dépend de la longueur des "
            "données, il ne peut pas être deviné."
        )
    if isinstance(data, bool):
        raise ConfigError(f"{label} est un booléen, ce qui n'est pas un jeu de données")
    if isinstance(data, int | np.integer):
        n = int(data)
    else:
        try:
            n = len(data)
        except TypeError as exc:
            raise ConfigError(f"{label} n'a pas de longueur : {type(data).__name__}") from exc
    if n < 1:
        raise InsufficientDataError(f"{label} est vide, aucun découpage n'est possible")
    return n


def assert_chronological(
    train_idx: Any,
    test_idx: Any,
    *,
    label: str = "pli",
) -> None:
    """Vérifie qu'aucune observation d'entraînement ne suit une observation de test.

    **Le problème.** Un découpage peut être correct en intention et faux en
    pratique, par une erreur de borne d'une seule unité. Le chiffre qui en sort
    reste plausible, donc personne ne le remet en cause.

    **L'intuition.** La condition à tenir est une inégalité entre deux nombres.
    La dernière position d'entraînement doit précéder strictement la première
    position de test. La vérifier coûte deux comparaisons.

    **La règle.** Pour un ensemble d'entraînement :math:`T` et un ensemble de
    test :math:`S`, tous deux non vides :

    .. math::

        \\max(T) < \\min(S)

    où :math:`\\max(T)` est la dernière position d'entraînement et
    :math:`\\min(S)` la première position de test. L'inégalité est stricte, une
    observation partagée entre les deux ensembles étant déjà une fuite.

    Args:
        train_idx: les positions ou les dates d'entraînement.
        test_idx: les positions ou les dates de test.
        label: le nom du pli, repris dans le message d'erreur.

    Raises:
        InsufficientDataError: l'un des deux ensembles est vide. Un pli dont un
            côté est vide ne rend aucune mesure, et le signaler vaut mieux que
            de rendre un ``NaN``.
        LookAheadError: au moins une observation d'entraînement se situe à la
            hauteur ou après la première observation de test.

    Note:
        Cette fonction est le garde-fou commun de tout le sous-paquet de
        validation. Tout découpage produit ailleurs passe par elle avant d'être
        rendu à l'appelant.

    Example:
        >>> import numpy as np
        >>> assert_chronological(np.array([0, 1, 2]), np.array([3, 4]))

    Note:
        Vérification de l'implémentation : le test
        ``test_assert_chronological_leve_sur_un_recouvrement`` construit un cas
        où une seule position d'entraînement dépasse, et attend la levée.
    """
    train = np.asarray(train_idx)
    test = np.asarray(test_idx)
    if train.size == 0 or test.size == 0:
        raise InsufficientDataError(
            f"{label} : ensemble vide (entraînement {train.size}, test {test.size}). "
            "Un pli dont un côté est vide ne rend aucune mesure."
        )
    dernier_train = train.max()
    premier_test = test.min()
    if dernier_train >= premier_test:
        n_fautives = int((train >= premier_test).sum())
        raise LookAheadError(
            f"{label} : {n_fautives} observation(s) d'entraînement se situent à la hauteur "
            f"ou après la première observation de test. Dernier entraînement {dernier_train!r}, "
            f"premier test {premier_test!r}. Le modèle verrait l'avenir de sa propre évaluation."
        )


def train_test_split_forbidden(*args: Any, **kwargs: Any) -> None:
    """Lève toujours. Le mélange aléatoire n'a pas cours sur une série temporelle.

    **Le problème.** ``sklearn.model_selection.train_test_split`` mélange par
    défaut. Appelé sur des rendements, il produit une mesure qui paraît hors
    échantillon et qui ne l'est pas.

    **Le mécanisme de la fuite, en une phrase.** Le tirage au hasard envoie des
    observations de 2020 dans l'entraînement et des observations de 2015 dans le
    test. Le modèle apprend l'avenir, puis on lui demande de le rendre au passé.

    **Ce que cela change sur un chiffre.** Le test
    ``test_le_melange_gonfle_la_mesure_hors_echantillon`` simule une marche
    aléatoire et compare deux découpages. Le mélange laisse une erreur
    quadratique voisine de la variance d'un seul incrément. L'analyse glissante,
    elle, paie la distance qui sépare la fin de l'entraînement du point à
    prévoir.

    Args:
        *args: ignorés. La fonction lève avant de les regarder.
        **kwargs: ignorés, pour la même raison.

    Raises:
        LookAheadError: toujours, avec le mécanisme de la fuite en clair et le
            nom des fonctions à employer à la place.

    Note:
        Cette fonction existe pour être lisible dans le code et dans la
        documentation. Un commentaire s'oublie, un appel qui lève ne s'oublie
        pas.
    """
    _LOG.error("appel refusé au découpage mélangé", extra={"n_args": len(args), "n_kwargs": len(kwargs)})
    raise LookAheadError(_SHUFFLE_MESSAGE)


@dataclass(frozen=True, eq=False, slots=True)
class TimeSplit:
    """Un découpage fixe du temps en quatre segments ordonnés.

    **Le problème.** Une étude qui n'a qu'un découpage en deux morceaux paie son
    réglage sur le morceau de test, donc mesure sa performance sur des données
    qui ont servi à choisir. Le nombre publié est alors optimiste, et l'ampleur
    du biais croît avec le nombre d'essais.

    **L'intuition.** Séparer trois usages plutôt que deux. On apprend sur le
    premier segment, on règle sur le deuxième, on mesure sur le troisième. Un
    quatrième segment reste fermé jusqu'à la publication.

    **Ce que le quatrième segment ajoute.** Le troisième segment finit par se
    contaminer à force d'être regardé. Le segment scellé ne sert qu'une fois, à
    la fin, et son chiffre est le seul qu'on puisse défendre comme jamais vu.

    **Les hypothèses.** Les quatre segments sont strictement ordonnés dans le
    temps. Chacun est trié et sans doublon. L'ordre strict interdit le
    recouvrement, puisque deux segments ordonnés ne partagent aucune position.

    **La provenance.** La séparation en trois est celle de Hastie, Tibshirani et
    Friedman (2009), *The Elements of Statistical Learning*, 2e édition,
    section 7.2. Le segment scellé est la réponse au biais de sélection décrit
    par Bailey, Borwein, López de Prado et Zhu (2014), *Notices of the AMS*,
    volume 61, numéro 5, pages 458 à 471. Statut : rapporté.

    **Les limites.** Le découpage est fixe, donc il rend une seule mesure par
    segment, sans erreur type. Pour une erreur type, il faut plusieurs plis,
    donc :class:`WalkForward`.

    **Les alternatives.** Un découpage en deux morceaux est plus simple et
    laisse le réglage sans garde-fou. Une validation croisée glissante rend
    plusieurs mesures et coûte plus cher en calcul.

    **Pourquoi ce choix ici.** Le laboratoire publie des verdicts. Un verdict
    exige un chiffre jamais vu, donc un segment scellé, donc quatre segments.

    **Comment vérifier.** Le test
    ``test_chronological_split_bornes_a_la_main`` découpe cent dates
    quotidiennes à des bornes connues et compare les longueurs à un comptage
    fait à la main.

    Attributes:
        train: les dates d'apprentissage.
        validation: les dates de réglage.
        test: les dates de mesure hors échantillon.
        final_holdout: les dates scellées, éventuellement vides.
    """

    train: pd.Index
    validation: pd.Index
    test: pd.Index
    final_holdout: pd.Index

    def __post_init__(self) -> None:
        """Contrôle que les quatre segments sont triés et strictement ordonnés."""
        for name in SEGMENT_NAMES:
            _as_index(getattr(self, name), label=f"segment « {name} »")
        remplis = [(name, getattr(self, name)) for name in SEGMENT_NAMES if len(getattr(self, name)) > 0]
        for (nom_gauche, gauche), (nom_droit, droit) in pairwise(remplis):
            if gauche[-1] >= droit[0]:
                raise DataQualityError(
                    f"les segments « {nom_gauche} » et « {nom_droit} » se recouvrent : "
                    f"« {nom_gauche} » finit le {gauche[-1]!r} et « {nom_droit} » commence "
                    f"le {droit[0]!r}. Deux segments ordonnés ne partagent aucune date."
                )

    @property
    def n_observations(self) -> int:
        """Le nombre total d'observations couvertes par les quatre segments."""
        return sum(len(getattr(self, name)) for name in SEGMENT_NAMES)

    @property
    def segments(self) -> dict[str, pd.Index]:
        """Les quatre segments dans l'ordre du temps, sous forme de dictionnaire."""
        return {name: getattr(self, name) for name in SEGMENT_NAMES}

    @staticmethod
    def tag_of(segment: str) -> SampleTag:
        """Rend l'étiquette d'échantillon d'un segment.

        Args:
            segment: le nom du segment, parmi :data:`SEGMENT_NAMES`.

        Returns:
            L'étiquette à attacher aux chiffres calculés sur ce segment.

        Raises:
            ConfigError: le nom demandé n'est pas un segment.
        """
        try:
            return SEGMENT_TAGS[segment]
        except KeyError as exc:
            raise ConfigError(
                f"segment inconnu : {segment!r}. Les segments sont {list(SEGMENT_NAMES)}."
            ) from exc

    def describe(self) -> str:
        """Rend une phrase qui dit combien d'observations chaque segment porte."""
        parts = [f"{name} {len(getattr(self, name))}" for name in SEGMENT_NAMES]
        return f"{self.n_observations} observation(s) : " + ", ".join(parts)


def chronological_split(
    index: pd.Index,
    train_end: Any,
    validation_end: Any,
    final_holdout_start: Any | None = None,
) -> TimeSplit:
    """Découpe un index en quatre segments ordonnés, sans recouvrement ni trou.

    **Le problème.** Un découpage écrit à la main dans un carnet dérive. Les
    bornes changent d'une cellule à l'autre, et la mesure finale ne sait plus
    quelles données l'ont produite.

    **L'intuition.** Poser les bornes une fois, dans un objet gelé, et laisser le
    code vérifier que la partition est complète. Trois bornes suffisent à
    définir quatre segments.

    **La règle de partition.** Pour un index :math:`\\{t_1, \\dots, t_n\\}`, une
    borne d'entraînement :math:`b_1`, une borne de validation :math:`b_2` et un
    début de segment scellé :math:`b_3` :

    .. math::

        T = \\{ t \\le b_1 \\},\\quad
        V = \\{ b_1 < t \\le b_2 \\},\\quad
        S = \\{ b_2 < t < b_3 \\},\\quad
        H = \\{ t \\ge b_3 \\}

    où :math:`T` est l'apprentissage, :math:`V` le réglage, :math:`S` la mesure
    hors échantillon et :math:`H` le segment scellé. Sans :math:`b_3`, le
    segment scellé est vide et :math:`S` prend tout ce qui suit :math:`b_2`. Les
    quatre ensembles sont disjoints et leur réunion redonne l'index, ce que la
    fonction vérifie avant de rendre.

    Args:
        index: l'index des dates, trié et sans doublon.
        train_end: la dernière date d'apprentissage, incluse.
        validation_end: la dernière date de réglage, incluse.
        final_holdout_start: la première date du segment scellé, incluse. Sans
            valeur, aucun segment n'est scellé.

    Returns:
        Un :class:`TimeSplit` gelé portant les quatre segments.

    Raises:
        TypeError: ``index`` n'est pas un ``pandas.Index``.
        DataQualityError: l'index n'est pas trié, porte des doublons, ou la
            partition obtenue ne le recouvre pas exactement.
        ConfigError: les bornes ne sont pas strictement croissantes.
        InsufficientDataError: l'index est vide, ou un segment attendu ressort
            vide.

    Example:
        >>> import pandas as pd
        >>> dates = pd.date_range("2020-01-01", periods=10, freq="D")
        >>> split = chronological_split(dates, "2020-01-05", "2020-01-07")
        >>> len(split.train), len(split.validation), len(split.test)
        (5, 2, 3)

    Note:
        Hypothèses. L'index est chronologique et chaque date est la date à
        laquelle l'observation était connaissable. Les bornes sont incluses à
        gauche du segment qu'elles ferment.

    Note:
        Limites. La fonction ne connaît pas l'horizon des étiquettes. Une
        étiquette à vingt jours déborde du segment d'apprentissage sur le
        segment de réglage, et il revient à l'appelant de reculer ``train_end``
        d'autant.

    Note:
        Alternatives. Un découpage par proportions, soixante pour cent puis
        vingt et vingt, est plus rapide à écrire. Il déplace les bornes dès que
        l'historique s'allonge, donc rend deux études incomparables. Les bornes
        en dates sont retenues pour cette raison.

    Note:
        Vérification. Le test ``test_chronological_split_bornes_a_la_main``
        compte les dates de chaque segment à la main sur cent jours calendaires.
    """
    index = _as_index(index, label="index")
    if len(index) == 0:
        raise InsufficientDataError(
            "index est vide, aucun découpage n'est possible. Trois bornes ne "
            "partagent rien quand il n'y a rien à partager."
        )
    borne_train = _as_bound(index, train_end, label="train_end")
    borne_validation = _as_bound(index, validation_end, label="validation_end")
    if borne_train >= borne_validation:
        raise ConfigError(
            f"train_end ({borne_train!r}) doit précéder strictement validation_end ({borne_validation!r})."
        )
    borne_holdout = (
        None
        if final_holdout_start is None
        else _as_bound(index, final_holdout_start, label="final_holdout_start")
    )
    if borne_holdout is not None and borne_holdout <= borne_validation:
        raise ConfigError(
            f"final_holdout_start ({borne_holdout!r}) doit suivre strictement validation_end "
            f"({borne_validation!r}), sinon le segment de test est vide."
        )

    valeurs = index.to_numpy()
    masque_train = valeurs <= borne_train
    masque_validation = (valeurs > borne_train) & (valeurs <= borne_validation)
    if borne_holdout is None:
        masque_test = valeurs > borne_validation
        masque_holdout = np.zeros(len(index), dtype=bool)
    else:
        masque_test = (valeurs > borne_validation) & (valeurs < borne_holdout)
        masque_holdout = valeurs >= borne_holdout

    split = TimeSplit(
        train=index[masque_train],
        validation=index[masque_validation],
        test=index[masque_test],
        final_holdout=index[masque_holdout],
    )

    attendus = ["train", "validation", "test"]
    if borne_holdout is not None:
        attendus.append("final_holdout")
    vides = [name for name in attendus if len(getattr(split, name)) == 0]
    if vides:
        raise InsufficientDataError(
            f"les segments {vides} ressortent vides avec ces bornes sur un index de "
            f"{len(index)} observation(s), du {index[0]!r} au {index[-1]!r}."
        )

    if split.n_observations != len(index):
        raise DataQualityError(
            f"la partition couvre {split.n_observations} observation(s) sur {len(index)}. "
            "Un tel écart signale un index non trié ou une borne mal comparée."
        )
    _LOG.info("découpage chronologique", extra={"description": split.describe()})
    return split


@dataclass(frozen=True, slots=True)
class WalkForward:
    """L'analyse glissante, ancrée ou à fenêtre fixe, purgée et sous embargo.

    **Le problème.** Un découpage fixe rend une seule mesure hors échantillon.
    Cette mesure ne dit pas si le résultat tient sur toute la période ou s'il
    vient d'un seul régime de marché. Un ratio de Sharpe moyen de 1,0 porté par
    deux années sur quinze n'est pas un résultat.

    **L'intuition.** Refaire le geste du gérant. On estime sur ce qu'on connaît,
    on décide pour la période qui suit, puis on avance d'un pas et on
    recommence. Chaque pas rend une mesure hors échantillon, et la suite de ces
    mesures dit la stabilité.

    **Les deux variantes, et quand chacune se choisit.** La variante ANCRÉE part
    toujours du début de l'historique, si bien que la fenêtre d'entraînement
    croît. Elle convient quand le mécanisme économique est supposé stable, et
    quand les données sont rares. La variante GLISSANTE garde une longueur
    constante. Elle convient quand le marché change de régime, puisqu'elle
    oublie le passé lointain. Le prix de l'oubli est une estimation plus
    bruitée, celui de l'ancrage est une réaction plus lente.

    **La règle qui compte plus que le choix.** Le choix se déclare AVANT de voir
    les résultats. Essayer les deux et retenir celle qui rend le plus beau
    chiffre est une sélection sur le test, donc une mesure dans l'échantillon
    déguisée. Le laboratoire écrit la variante dans la configuration de l'étude,
    et un changement ultérieur compte comme un essai de plus au sens de
    l'inflation des ratios.

    **La purge et l'embargo.** La purge retire :math:`p` observations à la fin de
    la fenêtre d'entraînement, celles dont l'étiquette déborde sur le bloc de
    test. L'embargo retire :math:`e` observations placées juste après chaque
    bloc de test, celles dont les variables explicatives sont calculées sur une
    fenêtre qui remonte dans ce bloc. Les deux sont de López de Prado (2018),
    sections 7.4.1 et 7.4.2.

    **Les hypothèses.** Les observations sont ordonnées et contiguës. La purge et
    l'embargo se comptent en observations, pas en jours. La fenêtre glissante
    garde :math:`L_{tr} - p` observations une fois la purge appliquée, la purge
    mordant sur la longueur demandée plutôt que de la décaler.

    **Les limites.** Le module ne connaît ni l'horizon des étiquettes ni la
    profondeur des variables explicatives. Il applique les nombres qu'on lui
    donne. Une purge trop courte laisse la fuite ouverte, sans que rien ne le
    signale.

    **Les alternatives.** La validation croisée en blocs mélangés est plus
    efficace en données et fausse ici. La validation croisée combinatoire purgée
    rend plusieurs chemins hors échantillon, ce que l'analyse glissante ne fait
    pas, au prix d'un recouvrement entre chemins.

    **Pourquoi ce choix ici.** L'analyse glissante est le seul découpage qui
    reproduise l'ordre réel des décisions, et c'est cet ordre que le laboratoire
    cherche à mesurer.

    **Comment vérifier.** Le nombre de plis se recalcule à la main par la formule
    du module. Le test ``test_nombre_de_plis_calcule_a_la_main`` compare les deux.

    Attributes:
        train_size: la longueur de la fenêtre d'entraînement, en observations.
        test_size: la longueur du bloc de test, en observations.
        step: le pas entre deux blocs de test. Sans valeur, il vaut
            ``test_size``, ce qui donne des blocs de test qui se touchent.
        anchored: ``True`` pour la variante ancrée, ``False`` pour la glissante.
        purge: le nombre d'observations retirées à la fin de l'entraînement.
        embargo: le nombre d'observations mises sous embargo après chaque bloc
            de test.

    Example:
        >>> import numpy as np
        >>> cv = WalkForward(train_size=50, test_size=10)
        >>> cv.get_n_splits(np.zeros(100))
        5
    """

    train_size: int
    test_size: int
    step: int | None = None
    anchored: bool = False
    purge: int = DEFAULT_PURGE
    embargo: int = DEFAULT_EMBARGO

    def __post_init__(self) -> None:
        """Contrôle que les cinq réglages sont des entiers dans leur domaine."""
        for name in ("train_size", "test_size", "purge", "embargo"):
            value = getattr(self, name)
            if not isinstance(value, int | np.integer) or isinstance(value, bool):
                raise ConfigError(f"{name} doit être un entier, reçu {type(value).__name__}")
        if self.train_size < 1:
            raise ConfigError(f"train_size doit valoir au moins 1, reçu {self.train_size}")
        if self.test_size < 1:
            raise ConfigError(f"test_size doit valoir au moins 1, reçu {self.test_size}")
        if self.purge < 0:
            raise ConfigError(f"purge ne peut pas être négative, reçu {self.purge}")
        if self.embargo < 0:
            raise ConfigError(f"embargo ne peut pas être négatif, reçu {self.embargo}")
        if self.purge >= self.train_size:
            raise ConfigError(
                f"purge ({self.purge}) doit rester sous train_size ({self.train_size}), "
                "sans quoi la fenêtre d'entraînement est vide."
            )
        if self.step is not None:
            if not isinstance(self.step, int | np.integer) or isinstance(self.step, bool):
                raise ConfigError(f"step doit être un entier, reçu {type(self.step).__name__}")
            if self.step < 1:
                raise ConfigError(f"step doit valoir au moins 1, reçu {self.step}")

    @property
    def effective_step(self) -> int:
        """Le pas réellement appliqué, égal à ``test_size`` quand ``step`` est absent."""
        return self.test_size if self.step is None else int(self.step)

    def _n_folds(self, n: int) -> int:
        """Rend le nombre de plis pour ``n`` observations, ou lève.

        Args:
            n: le nombre d'observations disponibles.

        Returns:
            Le nombre de plis, par la formule du module.

        Raises:
            InsufficientDataError: ``n`` ne permet pas même un seul pli.
        """
        span = self.train_size + self.test_size
        if n < span:
            raise InsufficientDataError(
                f"{n} observation(s) ne suffisent pas : un pli exige au moins "
                f"train_size + test_size = {span} observation(s)."
            )
        return (n - span) // self.effective_step + 1

    def get_n_splits(self, X: Any = None, y: Any = None, groups: Any = None) -> int:
        """Rend le nombre de plis, comme le veut l'interface scikit-learn.

        Args:
            X: les données, ou directement le nombre d'observations.
            y: ignoré, présent pour l'interface.
            groups: ignoré, présent pour l'interface.

        Returns:
            Le nombre de plis que :meth:`split` produira.

        Raises:
            ConfigError: ``X`` est absent ou n'a pas de longueur.
            InsufficientDataError: les données ne permettent aucun pli.
        """
        del y, groups
        return self._n_folds(_n_observations(X))

    def _embargoed(self, n: int, n_folds: int) -> np.ndarray:
        """Rend le masque des positions sous embargo, réunion sur tous les plis.

        Args:
            n: le nombre d'observations.
            n_folds: le nombre de plis.

        Returns:
            Un tableau de booléens de longueur ``n``, vrai là où la position est
            sous embargo.

        Note:
            Les zones d'embargo des plis à venir ne peuvent pas croiser la
            fenêtre d'entraînement d'un pli antérieur, puisqu'elles commencent
            après un bloc de test plus tardif. Les réunir toutes revient donc au
            même que de ne réunir que les précédentes, en une seule passe.
        """
        masque = np.zeros(n, dtype=bool)
        if self.embargo == 0:
            return masque
        for k in range(n_folds):
            fin_test = self.train_size + k * self.effective_step + self.test_size
            masque[fin_test : min(fin_test + self.embargo, n)] = True
        return masque

    def split(
        self, X: Any = None, y: Any = None, groups: Any = None
    ) -> Iterator[tuple[np.ndarray, np.ndarray]]:
        """Produit les plis, du plus ancien au plus récent.

        Args:
            X: les données, ou directement le nombre d'observations.
            y: ignoré, présent pour l'interface.
            groups: ignoré, présent pour l'interface.

        Yields:
            Des paires ``(train_idx, test_idx)`` de positions entières, triées
            par ordre croissant.

        Raises:
            ConfigError: ``X`` est absent ou n'a pas de longueur.
            InsufficientDataError: les données ne permettent aucun pli, ou la
                purge et l'embargo vident la fenêtre d'entraînement d'un pli.
            LookAheadError: un pli produit ne respecte pas l'ordre du temps.
                C'est un bogue du module, pas une erreur de l'appelant.
        """
        del y, groups
        n = _n_observations(X)
        n_folds = self._n_folds(n)
        step = self.effective_step
        sous_embargo = self._embargoed(n, n_folds)
        positions = np.arange(n)
        for k in range(n_folds):
            debut_test = self.train_size + k * step
            fin_test = debut_test + self.test_size
            fin_train = debut_test - self.purge
            debut_train = 0 if self.anchored else max(0, debut_test - self.train_size)
            masque = np.zeros(n, dtype=bool)
            masque[debut_train:fin_train] = True
            masque &= ~sous_embargo
            train_idx = positions[masque]
            test_idx = positions[debut_test:fin_test]
            if train_idx.size == 0:
                raise InsufficientDataError(
                    f"pli {k} : la fenêtre d'entraînement est vide après purge ({self.purge}) "
                    f"et embargo ({self.embargo})."
                )
            assert_chronological(train_idx, test_idx, label=f"pli {k}")
            yield train_idx, test_idx


class ExpandingSplit(WalkForward):
    """L'analyse glissante ancrée, nommée pour ce qu'elle fait.

    La fenêtre d'entraînement part de la première observation et croît d'un pas
    à chaque pli. C'est :class:`WalkForward` avec ``anchored=True``, et rien
    d'autre. Le nom existe pour que la configuration d'une étude dise la
    variante retenue sans qu'on ait à lire un booléen.

    Se choisit quand le mécanisme économique est supposé stable et quand les
    données sont rares. Le choix se déclare avant de voir les résultats.
    """

    def __init__(
        self,
        train_size: int,
        test_size: int,
        step: int | None = None,
        *,
        purge: int = DEFAULT_PURGE,
        embargo: int = DEFAULT_EMBARGO,
    ) -> None:
        """Construit une analyse glissante ancrée.

        Args:
            train_size: la longueur de la fenêtre d'entraînement du premier pli.
            test_size: la longueur du bloc de test.
            step: le pas entre deux blocs de test, ``test_size`` par défaut.
            purge: le nombre d'observations retirées à la fin de l'entraînement.
            embargo: le nombre d'observations sous embargo après chaque test.
        """
        super().__init__(
            train_size=train_size,
            test_size=test_size,
            step=step,
            anchored=True,
            purge=purge,
            embargo=embargo,
        )


class RollingSplit(WalkForward):
    """L'analyse glissante à fenêtre fixe, nommée pour ce qu'elle fait.

    La fenêtre d'entraînement garde une longueur constante et avance d'un pas à
    chaque pli. C'est :class:`WalkForward` avec ``anchored=False``, et rien
    d'autre.

    Se choisit quand le marché change de régime, puisque la fenêtre oublie le
    passé lointain. Le prix de cet oubli est une estimation plus bruitée. Le
    choix se déclare avant de voir les résultats.
    """

    def __init__(
        self,
        train_size: int,
        test_size: int,
        step: int | None = None,
        *,
        purge: int = DEFAULT_PURGE,
        embargo: int = DEFAULT_EMBARGO,
    ) -> None:
        """Construit une analyse glissante à fenêtre fixe.

        Args:
            train_size: la longueur constante de la fenêtre d'entraînement.
            test_size: la longueur du bloc de test.
            step: le pas entre deux blocs de test, ``test_size`` par défaut.
            purge: le nombre d'observations retirées à la fin de l'entraînement.
            embargo: le nombre d'observations sous embargo après chaque test.
        """
        super().__init__(
            train_size=train_size,
            test_size=test_size,
            step=step,
            anchored=False,
            purge=purge,
            embargo=embargo,
        )


def _bounds(index: pd.Index, positions: np.ndarray) -> tuple[Any, Any]:
    """Rend la première et la dernière étiquette d'un jeu de positions."""
    if positions.size == 0:
        return pd.NaT, pd.NaT
    return index[positions[0]], index[positions[-1]]


def _time_split_report(split: TimeSplit, index: pd.Index) -> pd.DataFrame:
    """Rend le tableau des quatre segments d'un découpage fixe."""
    total = len(index)
    lignes = []
    for name in SEGMENT_NAMES:
        segment = getattr(split, name)
        n_obs = len(segment)
        lignes.append(
            {
                "segment": name,
                "tag": TimeSplit.tag_of(name).value,
                "start": segment[0] if n_obs else pd.NaT,
                "end": segment[-1] if n_obs else pd.NaT,
                "n_obs": n_obs,
                "share": n_obs / total,
            }
        )
    return pd.DataFrame(lignes, columns=list(TIME_SPLIT_REPORT_COLUMNS))


def _walk_forward_report(split: WalkForward, index: pd.Index) -> pd.DataFrame:
    """Rend le tableau des plis d'une analyse glissante, deux lignes par pli."""
    total = len(index)
    lignes = []
    for k, (train_idx, test_idx) in enumerate(split.split(total)):
        for part, positions in (("train", train_idx), ("test", test_idx)):
            debut, fin = _bounds(index, positions)
            lignes.append(
                {
                    "fold": k,
                    "part": part,
                    "start": debut,
                    "end": fin,
                    "n_obs": int(positions.size),
                    "share": positions.size / total,
                }
            )
    return pd.DataFrame(lignes, columns=list(WALK_FORWARD_REPORT_COLUMNS))


def split_report(split: TimeSplit | WalkForward, index: pd.Index) -> pd.DataFrame:
    """Rend un tableau lisible du découpage, dates comprises.

    **Le problème.** Un découpage vit dans du code, donc personne ne le regarde.
    L'erreur de borne d'une unité se voit en une seconde sur un tableau et
    jamais dans une boucle.

    **L'intuition.** Rendre les mêmes nombres que ceux dont le calcul se sert,
    sous une forme qu'un lecteur peut vérifier ligne à ligne.

    Args:
        split: un :class:`TimeSplit` ou un :class:`WalkForward`.
        index: l'index des dates, trié et sans doublon. Il fixe le total dont on
            calcule les parts, et il traduit les positions en dates.

    Returns:
        Un tableau. Pour un :class:`TimeSplit`, une ligne par segment, avec les
        colonnes de :data:`TIME_SPLIT_REPORT_COLUMNS`. Pour un
        :class:`WalkForward`, deux lignes par pli, avec les colonnes de
        :data:`WALK_FORWARD_REPORT_COLUMNS`. La colonne ``share`` rapporte le
        nombre d'observations au total de l'index.

    Raises:
        TypeError: ``split`` n'est ni un découpage fixe ni une analyse glissante.
        DataQualityError: l'index n'est pas trié ou porte des doublons, ou les
            segments d'un :class:`TimeSplit` ne recouvrent pas l'index.

    Note:
        Pour une analyse glissante, les parts ne somment pas à un. Les blocs
        d'entraînement se recouvrent d'un pli à l'autre, et c'est voulu.

    Example:
        >>> import pandas as pd
        >>> dates = pd.date_range("2020-01-01", periods=10, freq="D")
        >>> report = split_report(WalkForward(train_size=5, test_size=5), dates)
        >>> list(report["part"])
        ['train', 'test']
    """
    index = _as_index(index, label="index")
    if isinstance(split, TimeSplit):
        if split.n_observations != len(index):
            raise DataQualityError(
                f"le découpage couvre {split.n_observations} observation(s) et l'index en "
                f"porte {len(index)}. Le tableau serait faux."
            )
        return _time_split_report(split, index)
    if isinstance(split, WalkForward):
        return _walk_forward_report(split, index)
    raise TypeError(f"split doit être un TimeSplit ou un WalkForward, reçu {type(split).__name__}")

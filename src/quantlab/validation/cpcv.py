r"""La validation croisée combinatoire purgée, et pourquoi un backtest doit rendre une distribution.

**(1) Le problème.** Un backtest ordinaire rend un seul chemin. La stratégie
s'estime sur le passé, se mesure sur le futur, et le rapport imprime un ratio de
Sharpe. Ce nombre unique ne dit pas ce qu'il serait devenu si l'histoire avait
été découpée autrement. Il change pourtant, dans de larges proportions. Le
chercheur qui essaie vingt stratégies et publie la meilleure publie surtout le
maximum d'une variable aléatoire. Bailey, Borwein, López de Prado et Zhu
appellent ce défaut le surajustement de backtest.

**(2) L'intuition.** Le temps se découpe en N tranches contiguës, appelées plis.
Au lieu de tester sur une seule tranche comme le fait la validation croisée en
k blocs, on teste sur k tranches à la fois. Chaque choix de k plis parmi N donne
un entraînement et un test. En recollant les morceaux dans l'ordre du temps, on
reconstitue plusieurs histoires hors échantillon complètes au lieu d'une seule.
Chacune couvre l'échantillon entier, et chacune a été produite par des modèles
entraînés sur des données différentes.

**(3) Le décompte, en formules.**

.. math::

    S(N, k) = \binom{N}{k}
    \qquad
    \varphi(N, k) = \frac{k}{N} \binom{N}{k} = \binom{N-1}{k-1}

**(4) Les variables.** :math:`N` est le nombre de plis et :math:`k` le nombre
de plis mis en test à chaque fois. :math:`S` est le nombre de combinaisons, donc
de modèles à estimer. Enfin :math:`\varphi` est le nombre de chemins de test
distincts.

La seconde égalité se démontre en deux lignes, et le laboratoire la vérifie dans
un test plutôt que de la croire. Chaque combinaison place k plis en test, donc
les combinaisons offrent :math:`k \binom{N}{k}` places de test. Par symétrie,
chaque pli occupe la même part de ces places, soit :math:`\frac{k}{N}
\binom{N}{k}` places pour un pli donné. Un chemin consomme exactement une place
par pli, puisqu'il couvre l'échantillon une fois et une seule. Le nombre de
chemins est donc le nombre de places d'un pli quelconque.

**Le cas de référence, calculé à la main.** Pour N = 6 et k = 2, il y a
:math:`\binom{6}{2} = 15` combinaisons et :math:`15 \times 2 / 6 = 5` chemins.
Quinze estimations de modèle rendent cinq histoires complètes. Statut de ces
deux nombres : calculés à la main, et retrouvés par ``skfolio`` 1.0.3.

**(5) Les hypothèses.** Les plis sont contigus dans le temps, sans quoi la purge
n'a pas de sens. Les observations portent une étiquette dont l'horizon est borné
par la taille de purge déclarée. La distribution des chemins n'est pas celle
d'un échantillon indépendant, puisque les chemins partagent leurs observations
et leurs modèles. Elle décrit la sensibilité au découpage, pas l'erreur
d'échantillonnage.

**La purge.** Une observation d'entraînement dont l'étiquette recouvre la
période de test contient de l'information de test. La purge retire du jeu
d'entraînement les observations situées de part et d'autre de chaque bloc de
test, sur la longueur déclarée. Sans elle, une étiquette calculée sur vingt
séances à venir laisse fuir vingt séances de futur dans l'entraînement.

**L'embargo.** La purge ne suffit pas quand les variables explicatives sont
autocorrélées. Une observation qui suit immédiatement le bloc de test partage sa
mémoire, par une moyenne mobile ou un modèle de type ARMA. L'embargo retire ces
observations, et lui seul agit après le bloc de test. La convention retenue ici
est celle de ``skfolio`` : la purge s'applique aux deux frontières, l'embargo à
la frontière de droite seulement.

**(6) Provenance.** López de Prado (2018), *Advances in Financial Machine
Learning*, Wiley. Le chapitre 7 porte la purge et l'embargo, le chapitre 12 la
validation croisée combinatoire et ses chemins multiples. Le surajustement de
backtest et la probabilité qui le mesure viennent de Bailey, Borwein,
López de Prado et Zhu, *The Probability of Backtest Overfitting*, Journal of
Computational Finance, 2016.

Statut de ces deux références. Celle du livre est rapportée : les numéros de
chapitre sont vérifiés contre la documentation de ``skfolio`` 1.0.3. Le texte du
livre lui-même n'a été relu dans aucune des deux sessions qui ont écrit puis
vérifié ce module. Celle de l'article est mesurée dans Crossref le 2026-09-01 :
identifiant 10.21314/jcf.2016.322, parution datée de septembre 2016. Le document
de travail qui la précède porte l'identifiant 10.2139/ssrn.2326253, déposé en
2013 et révisé en février 2015. La date de 2014 qu'on lit souvent n'est aucune
des trois.

**(7) Les limites.** Le coût d'abord : le nombre de combinaisons croît comme un
coefficient binomial, et chacune demande une estimation complète. Pour N = 20 et
k = 10, il faut 184 756 estimations, ce qui rend la méthode inutilisable sans
réduire N. Ensuite l'illusion d'indépendance : les chemins se recouvrent
largement, donc l'écart type de leur distribution n'est pas l'erreur type d'une
moyenne, et aucun test de Student ne s'y applique. Enfin, la purge suppose un
horizon d'étiquette connu ; s'il est sous-estimé, la fuite subsiste et le
résultat reste flatteur.

**(8) Les alternatives.** La validation croisée par blocs à un seul pli de test
rend un chemin, donc aucune dispersion. La validation glissante, celle de
``skfolio.model_selection.WalkForward``, respecte l'ordre du temps de bout en
bout et reste la plus proche de l'exploitation réelle, mais elle ne rend qu'un
chemin elle aussi. Le bootstrap par blocs rend une distribution sans respecter
la causalité du découpage. Aucune ne remplace les autres.

**(9) Pourquoi cette méthode.** Le laboratoire publie des verdicts. Un verdict
tiré d'un chiffre unique ne survit pas à la première objection, celle du
découpage. La distribution des chemins répond à cette objection avec un nombre,
la part de chemins négatifs, plutôt qu'avec une opinion.

**(10) Comment vérifier l'implémentation.** Quatre contrôles, tous dans
``tests/unit/test_validation_cpcv.py``. Le décompte contre des valeurs calculées
à la main. La couverture, chaque chemin recouvrant l'échantillon exactement une
fois. La purge, sur un exemple de douze observations dont les index retirés se
comptent sur les doigts. Et la comparaison des décomptes avec ``skfolio``, une
implémentation indépendante.

**Ce que la distribution apporte, en un exemple.** Une stratégie dont le ratio
de Sharpe vaut 1,2 en moyenne sur les chemins, mais s'étale de -0,3 à 2,6, n'est
pas une stratégie de Sharpe 1,2. La moyenne seule cache qu'un chemin sur les
cinq finit sous zéro. Le laboratoire publie donc la distribution, et la moyenne
n'en est qu'un résumé parmi cinq.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from quantlab.core.config import ValidationConfig
from quantlab.core.errors import ConfigError, InsufficientDataError
from quantlab.core.logging import get_logger

if TYPE_CHECKING:  # pragma: no cover - importé pour l'annotation seulement
    from skfolio.model_selection import CombinatorialPurgedCV as SkfolioCPCV

_LOG = get_logger(__name__)

#: Plafond par défaut du nombre de combinaisons. Chaque combinaison coûte une
#: estimation de modèle, si bien qu'un paramétrage qui en produit des centaines
#: de milliers est presque toujours une erreur de saisie. La même valeur est
#: retenue par ``skfolio`` 1.0.3, ce qui garde les deux implémentations
#: comparables sur le même paramétrage.
DEFAULT_MAX_SPLITS: int = 100_000

#: Niveau du quantile bas publié par défaut dans le résumé de distribution.
DEFAULT_LOWER_QUANTILE: float = 0.05

#: Niveau du quantile haut publié par défaut dans le résumé de distribution.
DEFAULT_UPPER_QUANTILE: float = 0.95

#: Les écarts de convention entre cette implémentation et celle de ``skfolio``
#: 1.0.3, mesurés par introspection le 2026-09-01. Ils sont énoncés ici une fois,
#: puis recopiés dans chaque comparaison plutôt que laissés à la mémoire du
#: lecteur.
CONVENTION_DIFFERENCES: tuple[str, ...] = (
    "Forme rendue par split : ici (train, test) avec les plis de test concaténés, "
    "conformément à scikit-learn ; skfolio rend (train, [test_1, ..., test_k]), "
    "une liste d'un tableau par pli de test.",
    "Reste de la division : ici les premiers plis reçoivent une observation de plus, "
    "convention de sklearn.model_selection.KFold et de numpy.array_split ; skfolio taille "
    "des plis égaux au quotient, puis verse le reste dans le dernier pli tant que ce reste "
    "tient dans un pli. Au-delà, ses observations de queue ne rejoignent aucun pli et ne "
    "sont jamais prédites hors échantillon : mesuré sur skfolio 1.0.3 le 2026-09-01, "
    "13 observations en 5 plis en laissent une dehors.",
    "Noms des paramètres : purge et embargo ici, purged_size et embargo_size chez skfolio, "
    "pour des conventions de purge identiques.",
    "Domaine autorisé : skfolio exige n_folds au moins 3 et n_test_folds au moins 2 ; "
    "ici n_test_folds vaut au moins 1, le cas 1 dégénérant en validation croisée purgée "
    "à un seul chemin.",
    "Garde sur la purge : skfolio refuse dès que purged_size + embargo_size atteint la "
    "taille d'un pli moins un, et il le refuse à l'appel de split, pas à la construction ; "
    "ici le refus vient du constat qu'un entraînement est vide, ce qui dépend de la "
    "combinaison et non du seul paramétrage.",
)


def _n_samples(X: Any) -> int:
    """Rend le nombre d'observations d'un intrant, sans le convertir.

    La conversion est évitée parce qu'elle coûte une copie du tableau de
    données, alors que le découpage ne lit que sa longueur.

    Args:
        X: un tableau, un ``DataFrame``, une série ou toute séquence dont la
            longueur est le nombre d'observations.

    Returns:
        Le nombre de lignes.

    Raises:
        ConfigError: l'intrant n'a ni forme ni longueur.
    """
    shape = getattr(X, "shape", None)
    if shape is not None and len(shape) >= 1:
        return int(shape[0])
    try:
        return len(X)
    except TypeError as exc:
        raise ConfigError(
            f"l'intrant de type {type(X).__name__} n'a ni attribut « shape » ni longueur, "
            "donc son nombre d'observations est inconnu"
        ) from exc


@dataclass(frozen=True, eq=False)
class PathSegment:
    """Un morceau de chemin de test : un pli, et le modèle qui l'a prédit.

    Un chemin se compose de N morceaux, un par pli. Chaque morceau porte les
    observations de son pli et les index d'entraînement de la combinaison qui l'a
    produit. Deux morceaux voisins viennent de combinaisons différentes, donc de
    modèles entraînés sur des données différentes.

    Attributes:
        fold: le numéro du pli, de 0 à N-1, dans l'ordre du temps.
        split: le numéro de la combinaison dont provient la prédiction.
        train_index: les index d'entraînement de cette combinaison, purge et
            embargo déjà retirés.
        test_index: les index du pli, contigus et croissants.
    """

    fold: int
    split: int
    train_index: np.ndarray
    test_index: np.ndarray


@dataclass(frozen=True, eq=False)
class TestPath:
    """Un chemin de test : une histoire hors échantillon complète.

    C'est l'objet qui distingue la méthode combinatoire de la validation croisée
    ordinaire. Un chemin recouvre l'échantillon entier, exactement une fois, en
    recollant les prédictions hors échantillon de N modèles différents. La
    performance se calcule sur ce recollement, et non sur un pli isolé.

    Attributes:
        path_id: le numéro du chemin, de 0 à :math:`\\varphi(N, k) - 1`.
        segments: les morceaux, un par pli, rangés dans l'ordre du temps.
    """

    path_id: int
    segments: tuple[PathSegment, ...]

    # Le nom commence par « Test », donc pytest tenterait de ramasser la classe
    # comme un cas de test dans tout fichier qui l'importe. Cet attribut le lui
    # interdit. Il ne change rien au comportement de la classe.
    __test__ = False

    @property
    def test_index(self) -> np.ndarray:
        """Les index de test du chemin entier, dans l'ordre du temps.

        Returns:
            La concaténation des index de chaque morceau. Elle vaut
            ``numpy.arange(n)`` puisque les plis sont contigus, disjoints et
            couvrants.
        """
        return np.concatenate([segment.test_index for segment in self.segments])

    @property
    def split_ids(self) -> tuple[int, ...]:
        """Les combinaisons employées, une par pli, dans l'ordre du temps."""
        return tuple(segment.split for segment in self.segments)

    @property
    def n_observations(self) -> int:
        """Le nombre d'observations couvertes par le chemin."""
        return int(sum(segment.test_index.size for segment in self.segments))


class CombinatorialPurgedCV:
    r"""La validation croisée combinatoire purgée, écrite pour être lue.

    **Le problème.** Obtenir plusieurs mesures hors échantillon d'une même
    stratégie sur une même histoire, sans jamais laisser une observation de test
    influencer le modèle qui la prédit.

    **L'intuition.** Découper le temps en N plis contigus, mettre k plis en test
    à chaque tour, et parcourir toutes les façons de choisir ces k plis.

    .. math::

        S(N, k) = \binom{N}{k}
        \qquad
        \varphi(N, k) = \frac{k}{N} \binom{N}{k} = \binom{N-1}{k-1}

    Les variables sont celles de la docstring du module : N le nombre de plis,
    k le nombre de plis de test, S le nombre de combinaisons et
    :math:`\varphi` le nombre de chemins.

    **Hypothèses.** Les observations sont rangées dans l'ordre du temps, sans
    doublon d'horodatage. La longueur de purge borne l'horizon des étiquettes.

    **Provenance.** López de Prado (2018), chapitres 7 et 12.

    **Limites.** Le coût croît comme un binomial. Les chemins se recouvrent,
    donc leur dispersion n'est pas une erreur type.

    **Alternatives.** ``skfolio.model_selection.WalkForward`` pour un seul
    chemin respectant l'ordre du temps de bout en bout, et
    ``skfolio.model_selection.CombinatorialPurgedCV`` pour la même méthode dans
    sa forme optimisée.

    **Pourquoi celle-ci.** L'implémentation de ``skfolio`` est vectorisée et
    rapide ; elle n'est pas lisible ligne à ligne par un lecteur qui découvre la
    méthode. Celle-ci l'est, et :func:`compare_with_skfolio` prouve que les deux
    décomptent la même chose.

    **Comment vérifier.** Les décomptes contre les valeurs calculées à la main
    du test, la couverture de chaque chemin, et les index purgés d'un exemple de
    douze observations.

    Args:
        n_folds: le nombre de plis contigus, au moins 2.
        n_test_folds: le nombre de plis mis en test par combinaison, au moins 1
            et strictement inférieur à ``n_folds``.
        purge: le nombre d'observations retirées de l'entraînement de chaque
            côté d'un bloc de test. Il se règle sur l'horizon de l'étiquette,
            pas sur une intuition.
        embargo: le nombre d'observations retirées en plus après un bloc de
            test, pour couper l'autocorrélation des variables explicatives.
        max_splits: le plafond du nombre de combinaisons acceptées.

    Raises:
        ConfigError: un paramètre est hors de son domaine, ou le paramétrage
            produit plus de combinaisons que ``max_splits``.
    """

    def __init__(
        self,
        n_folds: int = 10,
        n_test_folds: int = 2,
        purge: int = 0,
        embargo: int = 0,
        *,
        max_splits: int = DEFAULT_MAX_SPLITS,
    ) -> None:
        if n_folds < 2:
            raise ConfigError(f"n_folds doit valoir au moins 2, reçu {n_folds}")
        if n_test_folds < 1:
            raise ConfigError(f"n_test_folds doit valoir au moins 1, reçu {n_test_folds}")
        if n_test_folds >= n_folds:
            raise ConfigError(
                f"n_test_folds ({n_test_folds}) doit être strictement inférieur à n_folds "
                f"({n_folds}), sans quoi aucun entraînement ne reste"
            )
        if purge < 0:
            raise ConfigError(f"purge ne peut pas être négative, reçu {purge}")
        if embargo < 0:
            raise ConfigError(f"embargo ne peut pas être négatif, reçu {embargo}")
        n_splits = math.comb(n_folds, n_test_folds)
        if n_splits > max_splits:
            raise ConfigError(
                f"n_folds={n_folds} et n_test_folds={n_test_folds} produisent {n_splits} "
                f"combinaisons, au-delà du plafond max_splits={max_splits}. Chaque "
                "combinaison coûte une estimation de modèle."
            )
        self.n_folds = int(n_folds)
        self.n_test_folds = int(n_test_folds)
        self.purge = int(purge)
        self.embargo = int(embargo)
        self.max_splits = int(max_splits)

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(n_folds={self.n_folds}, n_test_folds={self.n_test_folds}, "
            f"purge={self.purge}, embargo={self.embargo})"
        )

    @classmethod
    def from_config(
        cls, config: ValidationConfig, *, max_splits: int = DEFAULT_MAX_SPLITS
    ) -> CombinatorialPurgedCV:
        """Construit le découpage depuis la configuration de l'expérience.

        Les quatre paramètres viennent du fichier YAML validé, jamais du code
        appelant. C'est la règle du laboratoire : un paramètre écrit en dur est
        un paramètre que personne ne retrouvera.

        Args:
            config: la section de validation de l'expérience.
            max_splits: le plafond du nombre de combinaisons acceptées.

        Returns:
            Le découpage configuré.
        """
        return cls(
            n_folds=config.n_folds,
            n_test_folds=config.n_test_folds,
            purge=config.purge_periods,
            embargo=config.embargo_periods,
            max_splits=max_splits,
        )

    @property
    def n_splits(self) -> int:
        r"""Le nombre de combinaisons, donc d'estimations de modèle à payer.

        Returns:
            :math:`\binom{N}{k}`, avec N le nombre de plis et k le nombre de
            plis de test.
        """
        return math.comb(self.n_folds, self.n_test_folds)

    @property
    def n_paths(self) -> int:
        r"""Le nombre de chemins de test distincts.

        La formule est celle du module :

        .. math::

            \varphi(N, k) = \frac{k}{N} \binom{N}{k} = \binom{N-1}{k-1}

        La division tombe juste, la seconde écriture le prouve. Le calcul se
        fait ici sous la première forme, celle qui se lit comme un partage de
        places de test entre les plis.

        Returns:
            Le nombre de chemins, un entier.
        """
        return self.n_splits * self.n_test_folds // self.n_folds

    def get_n_splits(self, X: Any = None, y: Any = None, groups: Any = None) -> int:
        """Rend le nombre de combinaisons, signature de scikit-learn.

        Args:
            X: ignoré, présent pour l'interface.
            y: ignoré, présent pour l'interface.
            groups: ignoré, présent pour l'interface.

        Returns:
            Le nombre de combinaisons.
        """
        del X, y, groups
        return self.n_splits

    def test_fold_combinations(self) -> tuple[tuple[int, ...], ...]:
        """Rend les combinaisons de plis de test, dans l'ordre lexicographique.

        L'ordre importe : c'est lui qui numérote les combinaisons, et le même
        ordre est retenu par ``skfolio``, ce qui rend les deux implémentations
        comparables combinaison par combinaison.

        Returns:
            Un tuple de ``n_splits`` tuples de ``n_test_folds`` numéros de plis.
        """
        return tuple(itertools.combinations(range(self.n_folds), self.n_test_folds))

    def fold_boundaries(self, n_samples: int) -> np.ndarray:
        """Rend les bornes des plis contigus, du premier index au dernier.

        Le reste de la division se répartit sur les premiers plis, un par pli,
        comme le fait ``sklearn.model_selection.KFold``. Treize observations en
        cinq plis donnent donc les tailles 3, 3, 3, 2 et 2.

        Args:
            n_samples: le nombre d'observations.

        Returns:
            Un tableau de ``n_folds + 1`` bornes, la borne de droite étant
            exclue. Le pli ``i`` couvre ``range(bornes[i], bornes[i + 1])``.

        Raises:
            InsufficientDataError: moins d'observations que de plis, un pli au
                moins serait vide.
        """
        if n_samples < self.n_folds:
            raise InsufficientDataError(
                f"{n_samples} observations pour {self.n_folds} plis : un pli au moins serait vide"
            )
        sizes = np.full(self.n_folds, n_samples // self.n_folds, dtype=int)
        sizes[: n_samples % self.n_folds] += 1
        return np.concatenate([[0], np.cumsum(sizes)])

    def path_assignment(self) -> np.ndarray:
        """Range les combinaisons en chemins, un chemin par colonne.

        **Le mécanisme.** Chaque pli est mis en test dans exactement
        ``n_paths`` combinaisons. La ligne ``i`` de la matrice liste ces
        combinaisons, par numéro croissant. La colonne ``j`` prend une
        combinaison par pli, ce qui donne un recouvrement complet de
        l'échantillon, donc un chemin.

        Cette affectation est celle de López de Prado (2018), chapitre 12, et
        celle de ``skfolio.model_selection.CombinatorialPurgedCV``. Elle n'est
        pas la seule possible : toute permutation des colonnes d'une ligne donne
        un autre appariement, tout aussi licite. Le résultat agrégé sur les
        chemins ne change pas, seul l'ordre des chemins change.

        Returns:
            Une matrice d'entiers de forme ``(n_folds, n_paths)``.
        """
        rows: list[list[int]] = [[] for _ in range(self.n_folds)]
        for split_id, combination in enumerate(self.test_fold_combinations()):
            for fold in combination:
                rows[fold].append(split_id)
        return np.array(rows, dtype=int)

    def _train_mask(self, n_samples: int, blocks: list[tuple[int, int]]) -> np.ndarray:
        """Rend le masque des observations admissibles à l'entraînement.

        Trois retraits, dans cet ordre : le bloc de test, la purge à sa gauche,
        puis la purge et l'embargo à sa droite. Deux blocs de test voisins n'ont
        pas besoin d'être fusionnés : la purge de l'un ne mord que sur l'autre,
        déjà exclu.

        Args:
            n_samples: le nombre d'observations.
            blocks: les blocs de test, bornes de droite exclues.

        Returns:
            Un masque booléen, vrai là où l'observation reste utilisable.
        """
        mask = np.ones(n_samples, dtype=bool)
        after = self.purge + self.embargo
        for start, stop in blocks:
            mask[start:stop] = False
            mask[max(0, start - self.purge) : start] = False
            mask[stop : min(n_samples, stop + after)] = False
        return mask

    def split(self, X: Any, y: Any = None, groups: Any = None) -> Iterator[tuple[np.ndarray, np.ndarray]]:
        """Engendre les couples (entraînement, test), interface de scikit-learn.

        Les plis de test sont concaténés en un seul tableau, comme l'exige
        scikit-learn. ``skfolio`` rend au contraire la liste de ses plis de
        test, ce qui interdit de passer son objet à un utilitaire de
        scikit-learn sans adaptation. La différence est documentée dans
        :data:`CONVENTION_DIFFERENCES`.

        Args:
            X: le tableau de données, dont seule la longueur est lue.
            y: ignoré, présent pour l'interface.
            groups: ignoré, présent pour l'interface.

        Yields:
            Un couple de tableaux d'index entiers, croissants et disjoints.

        Raises:
            InsufficientDataError: un pli serait vide, ou la purge et l'embargo
                vident l'entraînement d'une combinaison.
        """
        del y, groups
        n_samples = _n_samples(X)
        bounds = self.fold_boundaries(n_samples)
        _LOG.debug(
            "découpage combinatoire",
            extra={
                "n_samples": n_samples,
                "n_folds": self.n_folds,
                "n_test_folds": self.n_test_folds,
                "n_splits": self.n_splits,
                "n_paths": self.n_paths,
            },
        )
        for split_id, combination in enumerate(self.test_fold_combinations()):
            blocks = [(int(bounds[f]), int(bounds[f + 1])) for f in combination]
            test_index = np.concatenate([np.arange(start, stop) for start, stop in blocks])
            train_index = np.flatnonzero(self._train_mask(n_samples, blocks))
            if train_index.size == 0:
                raise InsufficientDataError(
                    f"la combinaison {split_id} (plis de test {combination}) laisse un "
                    f"entraînement vide : purge={self.purge}, embargo={self.embargo} retirent "
                    f"tout ce qui restait sur {n_samples} observations"
                )
            yield train_index, test_index


def test_paths(cv: CombinatorialPurgedCV, X: Any) -> list[TestPath]:
    """Reconstitue les chemins de test, une histoire hors échantillon par chemin.

    **Le problème.** Les combinaisons prises une à une donnent des morceaux de
    performance sur des périodes différentes, incomparables entre eux. Un ratio
    de Sharpe mesuré sur un sixième de l'histoire n'est pas un ratio de Sharpe.

    **L'intuition.** Recoller les morceaux. Chaque pli est prédit par plusieurs
    combinaisons ; en prenant une combinaison par pli, on obtient une couverture
    complète de l'échantillon. Le rangement retenu épuise les places de test
    sans en consommer deux fois, ce qui donne :math:`\\varphi(N, k)` chemins.
    Ce n'est pas le seul rangement qui y parvient : voir
    :meth:`CombinatorialPurgedCV.path_assignment`, qui dit lequel est retenu et
    ce qui change quand on en prend un autre.

    Args:
        cv: le découpage, déjà paramétré.
        X: le tableau de données, dont seule la longueur est lue.

    Returns:
        La liste des chemins, dans l'ordre de leur numéro. Chaque chemin porte
        ``n_folds`` morceaux rangés dans l'ordre du temps.

    Raises:
        InsufficientDataError: le découpage lui-même est impossible.

    Note:
        La vérification à faire tenir : la concaténation des index de test d'un
        chemin vaut ``numpy.arange(n)``, sans trou ni doublon. Le test
        ``test_chaque_chemin_couvre_l_echantillon_une_fois`` l'impose.
    """
    n_samples = _n_samples(X)
    bounds = cv.fold_boundaries(n_samples)
    splits = list(cv.split(X))
    assignment = cv.path_assignment()
    paths: list[TestPath] = []
    for path_id in range(cv.n_paths):
        segments = tuple(
            PathSegment(
                fold=fold,
                split=int(assignment[fold, path_id]),
                train_index=splits[int(assignment[fold, path_id])][0],
                test_index=np.arange(int(bounds[fold]), int(bounds[fold + 1])),
            )
            for fold in range(cv.n_folds)
        )
        paths.append(TestPath(path_id=path_id, segments=segments))
    return paths


@dataclass(frozen=True, eq=False)
class PerformanceDistribution:
    """La performance d'une stratégie sur tous les chemins, et son résumé.

    Attributes:
        metrics: la métrique de chaque chemin, indexée par son numéro.
        summary: les onze nombres du résumé, décrits dans
            :func:`cpcv_performance_distribution`.
    """

    metrics: pd.Series
    summary: pd.Series

    @property
    def negative_share(self) -> float:
        """La part de chemins dont la métrique est strictement négative."""
        return float(self.summary["negative_share"])


def _summarize(
    metrics: pd.Series,
    *,
    lower_quantile: float,
    upper_quantile: float,
) -> pd.Series:
    """Résume une distribution de chemins en onze nombres.

    Args:
        metrics: la métrique de chaque chemin.
        lower_quantile: le niveau du quantile bas, entre 0 et 1.
        upper_quantile: le niveau du quantile haut, entre 0 et 1.

    Returns:
        Une série indexée par les noms du résumé.
    """
    return pd.Series(
        {
            "count": float(metrics.size),
            "mean": float(metrics.mean()),
            "median": float(metrics.median()),
            "std": float(metrics.std(ddof=1)),
            "min": float(metrics.min()),
            "max": float(metrics.max()),
            "quantile_low": float(metrics.quantile(lower_quantile)),
            "quantile_high": float(metrics.quantile(upper_quantile)),
            "quantile_low_level": float(lower_quantile),
            "quantile_high_level": float(upper_quantile),
            "negative_share": float((metrics < 0).mean()),
        },
        name=metrics.name,
        dtype=float,
    )


def cpcv_performance_distribution(
    cv: CombinatorialPurgedCV,
    X: Any,
    backtest_fn: Callable[[TestPath], float],
    *,
    metric_name: str = "metric",
    lower_quantile: float = DEFAULT_LOWER_QUANTILE,
    upper_quantile: float = DEFAULT_UPPER_QUANTILE,
) -> PerformanceDistribution:
    """Applique un backtest à chaque chemin et rend la distribution obtenue.

    **Le problème.** Publier un seul chiffre de performance revient à publier un
    tirage sans dire de quelle loi. Le lecteur ne peut ni le contredire ni le
    situer.

    **L'intuition.** Rejouer la même stratégie sur chacun des chemins, puis
    regarder l'étalement. Une stratégie dont le ratio de Sharpe vaut 1,2 en
    moyenne mais va de -0,3 à 2,6 n'est pas une stratégie de Sharpe 1,2. La part
    de chemins négatifs est le nombre qui le dit en un coup d'œil.

    **Les hypothèses.** ``backtest_fn`` est déterministe et sans état : appelée
    deux fois sur le même chemin, elle rend le même nombre. Elle n'utilise que
    les index du chemin, jamais l'histoire entière. Si elle tire au hasard, elle
    reçoit son générateur par ``quantlab.core.determinism.child_generators``.

    **Les limites.** Les chemins partagent leurs observations et leurs modèles,
    donc leurs métriques sont corrélées. L'écart type rendu ici mesure la
    sensibilité au découpage, et non l'erreur type d'une moyenne. En tirer un
    intervalle de confiance à 95 % par la règle des deux erreurs types serait
    une faute.

    Args:
        cv: le découpage, déjà paramétré.
        X: le tableau de données, dont seule la longueur est lue.
        backtest_fn: la fonction qui rend la métrique d'un chemin, par exemple
            le ratio de Sharpe annualisé de ses rendements hors échantillon.
        metric_name: le nom donné à la série, par exemple ``"sharpe"``.
        lower_quantile: le niveau du quantile bas du résumé.
        upper_quantile: le niveau du quantile haut du résumé.

    Returns:
        La distribution et son résumé. Le résumé porte le nombre de chemins, la
        moyenne, la médiane et l'écart type d'échantillon. Il porte ensuite le
        minimum, le maximum, les deux quantiles et les deux niveaux employés. Il
        finit par la part de chemins dont la métrique est strictement négative.

    Raises:
        ConfigError: les niveaux de quantile ne sont pas ordonnés dans ]0, 1[.

    Note:
        L'écart type emploie ``ddof=1``. Avec un seul chemin il vaut ``NaN``,
        ce qui est le comportement voulu : la dispersion d'un point unique
        n'existe pas.
    """
    if not 0.0 < lower_quantile < upper_quantile < 1.0:
        raise ConfigError(
            f"les niveaux de quantile doivent vérifier 0 < bas < haut < 1, reçus "
            f"bas={lower_quantile} et haut={upper_quantile}"
        )
    paths = test_paths(cv, X)
    metrics = pd.Series(
        [float(backtest_fn(path)) for path in paths],
        index=pd.Index([path.path_id for path in paths], name="path"),
        name=metric_name,
        dtype=float,
    )
    summary = _summarize(metrics, lower_quantile=lower_quantile, upper_quantile=upper_quantile)
    _LOG.info(
        "distribution de performance sur les chemins",
        extra={
            "metric": metric_name,
            "n_paths": int(metrics.size),
            "mean": round(float(metrics.mean()), 6),
            "negative_share": round(float((metrics < 0).mean()), 6),
        },
    )
    return PerformanceDistribution(metrics=metrics, summary=summary)


def _build_skfolio(*, n_folds: int, n_test_folds: int, purged_size: int, embargo_size: int) -> SkfolioCPCV:
    """Construit l'objet de ``skfolio``, en important le paquet à l'appel.

    L'import est différé parce que ``skfolio`` vit dans un extra facultatif du
    projet. Un import en tête de module rendrait le laboratoire entier
    inutilisable sans lui.

    Args:
        n_folds: le nombre de plis.
        n_test_folds: le nombre de plis de test.
        purged_size: la purge, dans le vocabulaire de ``skfolio``.
        embargo_size: l'embargo, dans le vocabulaire de ``skfolio``.

    Returns:
        L'objet de validation croisée de ``skfolio``.

    Raises:
        ConfigError: le paquet n'est pas installé, ou refuse le paramétrage.
    """
    try:
        from skfolio.model_selection import CombinatorialPurgedCV as _SkfolioCPCV
    except ImportError as exc:
        raise ConfigError(
            "skfolio est absent de l'environnement. Il vit dans l'extra « portfolio » : "
            "uv sync --extra portfolio"
        ) from exc
    try:
        return _SkfolioCPCV(
            n_folds=n_folds,
            n_test_folds=n_test_folds,
            purged_size=purged_size,
            embargo_size=embargo_size,
        )
    except ValueError as exc:
        raise ConfigError(
            f"skfolio refuse n_folds={n_folds} et n_test_folds={n_test_folds} : {exc}. "
            "Son domaine est plus étroit que le nôtre, voir CONVENTION_DIFFERENCES."
        ) from exc


def skfolio_cpcv(config: ValidationConfig) -> SkfolioCPCV:
    """Rend le découpage combinatoire de ``skfolio`` configuré comme le nôtre.

    La fabrique tient en une correspondance de noms, et c'est tout ce qu'elle
    fait. Elle existe pour qu'un seul endroit du laboratoire connaisse cette
    correspondance, et pour que la comparaison des deux implémentations porte
    bien sur le même paramétrage.

    ==================  ======================
    ``ValidationConfig``  ``skfolio``
    ==================  ======================
    ``n_folds``           ``n_folds``
    ``n_test_folds``      ``n_test_folds``
    ``purge_periods``     ``purged_size``
    ``embargo_periods``   ``embargo_size``
    ==================  ======================

    Args:
        config: la section de validation de l'expérience.

    Returns:
        Un ``skfolio.model_selection.CombinatorialPurgedCV``.

    Raises:
        ConfigError: ``skfolio`` est absent, ou refuse le paramétrage. Son
            domaine exige au moins trois plis et au moins deux plis de test.
    """
    return _build_skfolio(
        n_folds=config.n_folds,
        n_test_folds=config.n_test_folds,
        purged_size=config.purge_periods,
        embargo_size=config.embargo_periods,
    )


@dataclass(frozen=True, eq=False)
class SkfolioComparison:
    """Le résultat de la confrontation des deux implémentations.

    Attributes:
        n_observations: la longueur de l'intrant commun.
        n_folds: le nombre de plis, commun aux deux.
        n_test_folds: le nombre de plis de test, commun aux deux.
        n_splits_quantlab: le nombre de combinaisons de notre implémentation.
        n_splits_skfolio: le nombre de combinaisons de ``skfolio``.
        splits_gap: l'écart entre les deux, nul quand elles s'accordent.
        n_paths_quantlab: le nombre de chemins de notre implémentation.
        n_paths_skfolio: le nombre de chemins de ``skfolio``.
        paths_gap: l'écart entre les deux, nul quand elles s'accordent.
        fold_sizes_quantlab: les tailles de plis, mesurées sur nos découpes.
        fold_sizes_skfolio: les tailles de plis, mesurées sur celles de
            ``skfolio``. Elles diffèrent des nôtres dès que le nombre
            d'observations n'est pas multiple du nombre de plis.
        same_test_sets: vrai quand les jeux de test coïncident combinaison par
            combinaison. Vaut ``None`` quand ``skfolio`` n'a pas pu découper.
        notes: les écarts de convention connus, plus le message d'erreur de
            ``skfolio`` quand il a refusé le paramétrage.
    """

    n_observations: int
    n_folds: int
    n_test_folds: int
    n_splits_quantlab: int
    n_splits_skfolio: int
    splits_gap: int
    n_paths_quantlab: int
    n_paths_skfolio: int
    paths_gap: int
    fold_sizes_quantlab: tuple[int, ...]
    fold_sizes_skfolio: tuple[int, ...]
    same_test_sets: bool | None
    notes: tuple[str, ...]

    @property
    def counts_agree(self) -> bool:
        """Vrai quand les deux implémentations décomptent la même chose."""
        return self.splits_gap == 0 and self.paths_gap == 0


def compare_with_skfolio(cv: CombinatorialPurgedCV, X: Any) -> SkfolioComparison:
    """Confronte notre découpage à celui de ``skfolio`` sur le même intrant.

    **Le problème.** Une implémentation pédagogique est une implémentation de
    plus, donc une occasion d'erreur de plus. Sans confrontation, sa lisibilité
    ne prouve rien.

    **L'intuition.** Les deux décomptes se comparent directement. Le nombre de
    combinaisons et le nombre de chemins ne dépendent que de N et de k, donc un
    écart signale une faute de formule sans ambiguïté.

    **Ce qui diffère par convention.** Les tailles de plis, quand le nombre
    d'observations n'est pas multiple du nombre de plis. Le reste va aux
    premiers plis chez nous, au dernier chez ``skfolio``, et seulement tant que
    ce reste tient dans un pli. Les jeux de test coïncident donc exactement
    quand la division tombe juste. Le champ ``notes`` porte la liste complète
    des écarts. L'un d'eux n'est pas une simple convention : au-delà d'un pli de
    reste, ``skfolio`` laisse des observations de queue hors de tout pli de
    test, et ne les prédit jamais hors échantillon.

    Args:
        cv: notre découpage, déjà paramétré.
        X: le tableau de données commun aux deux.

    Returns:
        La comparaison, décomptes et tailles de plis compris.

    Raises:
        ConfigError: ``skfolio`` est absent, ou refuse le paramétrage.
    """
    n_samples = _n_samples(X)
    sk = _build_skfolio(
        n_folds=cv.n_folds,
        n_test_folds=cv.n_test_folds,
        purged_size=cv.purge,
        embargo_size=cv.embargo,
    )
    bounds = cv.fold_boundaries(n_samples)
    fold_sizes_quantlab = tuple(int(b) for b in np.diff(bounds))

    notes = list(CONVENTION_DIFFERENCES)
    fold_sizes_skfolio: tuple[int, ...] = ()
    same_test_sets: bool | None = None
    try:
        sk_splits = list(sk.split(np.asarray(X, dtype=float).reshape(n_samples, -1)))
    except ValueError as exc:
        notes.append(f"skfolio n'a pas pu découper cet intrant : {exc}")
    else:
        folds: dict[int, int] = {}
        for _, test_list in sk_splits:
            for block in test_list:
                folds[int(block[0])] = int(block.size)
        fold_sizes_skfolio = tuple(folds[start] for start in sorted(folds))
        our_tests = [test for _, test in cv.split(X)]
        same_test_sets = len(sk_splits) == len(our_tests) and all(
            np.array_equal(np.sort(np.concatenate(sk_test)), np.sort(our_test))
            for (_, sk_test), our_test in zip(sk_splits, our_tests, strict=True)
        )

    return SkfolioComparison(
        n_observations=n_samples,
        n_folds=cv.n_folds,
        n_test_folds=cv.n_test_folds,
        n_splits_quantlab=cv.n_splits,
        n_splits_skfolio=int(sk.n_splits),
        splits_gap=cv.n_splits - int(sk.n_splits),
        n_paths_quantlab=cv.n_paths,
        n_paths_skfolio=int(sk.n_test_paths),
        paths_gap=cv.n_paths - int(sk.n_test_paths),
        fold_sizes_quantlab=fold_sizes_quantlab,
        fold_sizes_skfolio=fold_sizes_skfolio,
        same_test_sets=same_test_sets,
        notes=tuple(notes),
    )


def optimal_folds(
    n_observations: int,
    target_train_size: int,
    target_n_test_paths: int,
    *,
    weight_train_size: float = 1.0,
    weight_n_test_paths: float = 1.0,
) -> tuple[int, int]:
    r"""Cherche le couple de plis qui approche au mieux deux cibles à la fois.

    **Le problème.** N et k se choisissent d'ordinaire au jugé, alors qu'ils
    fixent deux choses opposées. Beaucoup de chemins demande k grand, donc un
    entraînement court. Un entraînement long demande k petit, donc peu de
    chemins.

    **L'intuition.** Poser les deux cibles, puis minimiser une distance
    relative pondérée entre ce qu'un couple donne et ce qu'on visait.

    .. math::

        c(N, k) = w_{t}\,
        \left| \frac{\bar{n}(N, k) - n^{*}}{n^{*}} \right|
        + w_{p}\,
        \left| \frac{\varphi(N, k) - \varphi^{*}}{\varphi^{*}} \right|

    :math:`\bar{n}(N, k)` est la taille moyenne d'entraînement, :math:`n^{*}` la
    taille visée, :math:`\varphi^{*}` le nombre de chemins visé, et
    :math:`w_{t}`, :math:`w_{p}` les deux poids.

    **Provenance.** Fonction de coût et recherche exhaustive de ``skfolio``
    1.0.3, ``skfolio.model_selection.optimal_folds_number``. Ce module ne fait
    que l'appeler, pour que la formule vive à un seul endroit.

    **Les limites.** Le résultat dépend entièrement des deux cibles et de leurs
    poids, qui restent des choix. La fonction ne dit pas si ces choix sont bons,
    et la purge n'entre pas dans son calcul.

    Args:
        n_observations: le nombre d'observations disponibles.
        target_train_size: la taille d'entraînement visée, en observations.
        target_n_test_paths: le nombre de chemins visé.
        weight_train_size: le poids de l'écart à la taille d'entraînement.
        weight_n_test_paths: le poids de l'écart au nombre de chemins.

    Returns:
        Le couple ``(n_folds, n_test_folds)`` retenu.

    Raises:
        ConfigError: ``skfolio`` est absent de l'environnement.
    """
    try:
        from skfolio.model_selection import optimal_folds_number
    except ImportError as exc:
        raise ConfigError(
            "skfolio est absent de l'environnement. Il vit dans l'extra « portfolio » : "
            "uv sync --extra portfolio"
        ) from exc
    n_folds, n_test_folds = optimal_folds_number(
        n_observations=n_observations,
        target_train_size=target_train_size,
        target_n_test_paths=target_n_test_paths,
        weight_train_size=weight_train_size,
        weight_n_test_paths=weight_n_test_paths,
    )
    return int(n_folds), int(n_test_folds)

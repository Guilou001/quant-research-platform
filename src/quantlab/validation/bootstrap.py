r"""Le rééchantillonnage qui préserve la dépendance temporelle.

**Le problème.** Un ratio de Sharpe de 1,2 mesuré sur cinq ans est un nombre, pas
un verdict. Pour trancher, il faut savoir de combien ce nombre aurait bougé si
l'histoire s'était déroulée autrement. Aucune formule fermée ne le dit pour une
statistique quelconque, et c'est à quoi sert le bootstrap.

**L'intuition du bootstrap.** L'échantillon observé est la meilleure image
disponible de la population dont il sort. Rejouer l'échantillon contre lui-même,
avec remise, imite donc le tirage d'un nouvel échantillon. La dispersion des
statistiques ainsi obtenues estime la dispersion de la statistique vraie. Efron
(1979) pose l'idée, et sa portée tient à ce qu'elle ne demande aucune loi.

**Le piège, et la raison d'être de ce module.** Le bootstrap i.i.d. tire les
observations une par une, donc il détruit l'ordre du temps. Or les rendements
sont autocorrélés, et cette dépendance change la variance de leur moyenne.

.. math::

    \operatorname{Var}(\bar{x}) \approx \frac{\sigma^2}{T}
    \left(1 + 2\sum_{k \ge 1} \rho_k\right)

Exemple travaillé, statut modélisé. Sur un processus autorégressif d'ordre un de
coefficient 0,2, la somme des autocorrélations vaut 0,2 / 0,8, si bien que le
facteur entre parenthèses vaut 1,5. L'erreur type vraie est donc racine de 1,5,
soit 1,22 fois celle qu'annonce le bootstrap i.i.d. L'intervalle i.i.d. est
18,4 % trop étroit, et le test correspondant rejette trop souvent. Un ratio de
Sharpe déclaré significatif à 5 % l'est en réalité à un seuil bien plus lâche.

**Le remède : rééchantillonner des blocs, pas des points.** Un bloc de
:math:`b` observations consécutives emporte avec lui la dépendance interne à ces
:math:`b` dates. Seules les jointures entre blocs cassent la structure, et leur
nombre décroît quand :math:`b` croît. Trois variantes vivent ici.

- Le bootstrap par blocs mobiles de Künsch (1989) tire des blocs de longueur
  fixe dont le départ est uniforme dans la série.
- Le bootstrap par blocs circulaires de Politis et Romano (1992) recolle la
  série en anneau, ce qui rend à chaque observation la même chance d'être tirée.
- Le bootstrap stationnaire de Politis et Romano (1994) tire des longueurs de
  bloc géométriques, ce qui rend la série rééchantillonnée stationnaire.

**Le compromis sur la longueur de bloc, qui n'a pas de solution gratuite.** Un
bloc court préserve mal la dépendance : à la limite d'un bloc de longueur un, on
retrouve le bootstrap i.i.d. et son intervalle trop étroit. Un bloc long préserve
la dépendance mais réduit le nombre de blocs distincts. Sur 1 000 observations
avec des blocs de 200, il ne reste que 801 départs possibles et cinq blocs par
rééchantillon, donc peu de variété et une variance d'estimation qui monte. Le
biais décroît en :math:`b`, la variance croît en :math:`b`, et l'optimum de
l'erreur quadratique se situe en :math:`b \propto T^{1/3}`. C'est exactement la
forme que rend :func:`optimal_block_size`.

**Ce que le module ne fait pas.** Il ne corrige pas l'asymétrie de la
distribution bootstrap par la méthode BCa d'Efron (1987). Le choix est déclaré
dans :func:`bootstrap_confidence_interval`, avec ce qu'il coûte.

Références :

- Efron, B. (1979), « Bootstrap Methods: Another Look at the Jackknife »,
  *Annals of Statistics*, 7(1), 1-26.
- Künsch, H. R. (1989), « The Jackknife and the Bootstrap for General Stationary
  Observations », *Annals of Statistics*, 17(3), 1217-1241.
- Politis, D. N. et Romano, J. P. (1992), « A Circular Block-Resampling
  Procedure for Stationary Data », dans *Exploring the Limits of Bootstrap*,
  Wiley, 263-270.
- Politis, D. N. et Romano, J. P. (1994), « The Stationary Bootstrap », *Journal
  of the American Statistical Association*, 89(428), 1303-1313.
- Politis, D. N. et White, H. (2004), « Automatic Block-Length Selection for the
  Dependent Bootstrap », *Econometric Reviews*, 23(1), 53-70.
- Patton, A., Politis, D. N. et White, H. (2009), « Correction to Automatic
  Block-Length Selection for the Dependent Bootstrap », *Econometric Reviews*,
  28(4), 372-375.
- Efron, B. (1987), « Better Bootstrap Confidence Intervals », *Journal of the
  American Statistical Association*, 82(397), 171-185.
- Davison, A. C. et Hinkley, D. V. (1997), *Bootstrap Methods and their
  Application*, Cambridge University Press, chapitres 4 et 5.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

import numpy as np
import numpy.typing as npt
import pandas as pd

from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.logging import get_logger

log = get_logger(__name__)

#: Tout ce qui se convertit en observations rangées par le temps, lignes = dates.
type BootstrapInput = pd.Series | pd.DataFrame | npt.NDArray[np.floating] | Sequence[float]

#: Les deux constructions d'intervalle implémentées ici.
type IntervalMethod = Literal["percentile", "basic"]

#: Les règles de choix automatique de la longueur de bloc implémentées ici.
type BlockSizeRule = Literal["politis_white"]

#: Une statistique quelconque appliquée à un rééchantillon.
type StatisticFn = Callable[[npt.NDArray[np.float64]], float]

#: Niveau de confiance par défaut des intervalles. 0,95 est la convention de la
#: littérature citée, et non une propriété du bootstrap.
DEFAULT_CONFIDENCE_LEVEL: float = 0.95

#: Nombre minimal d'observations sous lequel un rééchantillonnage ne veut rien
#: dire. Deux est le minimum arithmétique, une seule observation rendant toujours
#: le même rééchantillon.
MIN_OBSERVATIONS: int = 2

#: Nombre minimal d'observations exigé par la règle de Politis et White. Seize
#: est un plancher d'arithmétique, choisi pour que les sommes d'autocovariances
#: restent non vides, et non une recommandation statistique. La règle est
#: asymptotique, et sur seize points son résultat est à lire comme un ordre de
#: grandeur.
MIN_OBSERVATIONS_BLOCK_RULE: int = 16

#: Plancher par défaut de la longueur de bloc rendue par :func:`optimal_block_size`.
#: Un bloc de longueur un est le bootstrap i.i.d., donc la plus petite valeur
#: qu'une fonction de rééchantillonnage sait consommer.
DEFAULT_BLOCK_SIZE_FLOOR: float = 1.0


class BootstrapMethod(StrEnum):
    """La façon de tirer les indices d'un rééchantillon.

    ``IID`` tire les observations une par une, ``MOVING_BLOCK`` et
    ``CIRCULAR_BLOCK`` tirent des blocs de longueur fixe, ``STATIONARY`` tire des
    blocs de longueur géométrique. Le choix n'est pas cosmétique : sur une série
    autocorrélée, ``IID`` rend une erreur type trop petite, et le module en donne
    l'ampleur chiffrée dans sa documentation de tête.
    """

    IID = "iid"
    MOVING_BLOCK = "moving_block"
    CIRCULAR_BLOCK = "circular_block"
    STATIONARY = "stationary"


# --------------------------------------------------------------------------- #
# Résultats structurés
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True, eq=False)
class BootstrapDistribution:
    """La distribution bootstrap d'une statistique, et de quoi la relire.

    Attributes:
        observed: la statistique calculée sur l'échantillon d'origine.
        replicates: les statistiques calculées sur chaque rééchantillon.
        method: la méthode de rééchantillonnage employée.
        n_resamples: le nombre de rééchantillons tirés.
        n_observations: le nombre d'observations de l'échantillon d'origine.
        block_size: la longueur de bloc employée, fixe ou moyenne selon la
            méthode. Vaut ``None`` pour le bootstrap i.i.d.

    Note:
        La distribution est centrée sur ``observed`` et non sur la vraie valeur
        du paramètre. C'est pourquoi la valeur p de :func:`bootstrap_pvalue`
        recentre les répliques avant de compter.
    """

    observed: float
    replicates: npt.NDArray[np.float64]
    method: BootstrapMethod
    n_resamples: int
    n_observations: int
    block_size: float | None

    @property
    def standard_error(self) -> float:
        r"""L'erreur type bootstrap, écart type des répliques.

        Returns:
            L'écart type d'échantillon des répliques, dénominateur
            :math:`B - 1`.

        Note:
            C'est l'estimateur d'Efron (1979) de l'erreur type de la statistique.
            Il ne dépend d'aucune hypothèse de loi, mais il dépend entièrement de
            la méthode de rééchantillonnage : sur une série autocorrélée, la
            méthode ``IID`` le sous-estime.
        """
        return float(np.std(self.replicates, ddof=1))

    @property
    def bias(self) -> float:
        r"""Le biais bootstrap, moyenne des répliques moins la valeur observée.

        Returns:
            :math:`\overline{\theta^*} - \hat{\theta}`.

        Note:
            Un biais non nul signale une statistique non linéaire, par exemple un
            ratio de Sharpe dont le dénominateur est estimé. Le corriger en
            retranchant ce biais est possible, et ce module ne le fait pas. La
            correction ajoute de la variance, et Efron et Tibshirani (1993,
            chapitre 10) la déconseillent quand le biais est petit devant
            l'erreur type.
        """
        return float(np.mean(self.replicates) - self.observed)

    def quantile(self, probability: float) -> float:
        """Rend le quantile empirique des répliques.

        Args:
            probability: la probabilité voulue, strictement entre 0 et 1.

        Returns:
            Le quantile empirique, interpolation linéaire de NumPy.

        Raises:
            ConfigError: si la probabilité sort de l'intervalle ouvert.
        """
        if not 0.0 <= probability <= 1.0:
            raise ConfigError(f"la probabilité doit être entre 0 et 1, reçu {probability}")
        return float(np.quantile(self.replicates, probability))


@dataclass(frozen=True, slots=True)
class BootstrapInterval:
    """Un intervalle de confiance bootstrap, et sa fabrication.

    Attributes:
        low: la borne basse.
        high: la borne haute.
        confidence_level: le niveau de confiance, par exemple 0,95.
        observed: la statistique de l'échantillon d'origine.
        method: ``"percentile"`` ou ``"basic"``.
        n_resamples: le nombre de répliques ayant servi aux quantiles.
    """

    low: float
    high: float
    confidence_level: float
    observed: float
    method: IntervalMethod
    n_resamples: int

    @property
    def width(self) -> float:
        """La largeur de l'intervalle, borne haute moins borne basse."""
        return self.high - self.low

    def contains(self, value: float) -> bool:
        """Dit si une valeur tombe dans l'intervalle, bornes comprises.

        Args:
            value: la valeur testée, typiquement la vraie valeur du paramètre
                dans une étude de couverture.

        Returns:
            Vrai si la valeur est entre les deux bornes.
        """
        return bool(self.low <= value <= self.high)


@dataclass(frozen=True, slots=True)
class BlockSizeSelection:
    """Le résultat de la règle de Politis et White, avec ses grandeurs internes.

    Attributes:
        stationary: la longueur de bloc optimale du bootstrap stationnaire.
        circular: celle du bootstrap par blocs circulaires.
        n_observations: le nombre d'observations de la série.
        m_hat: le retard au-delà duquel le corrélogramme est jugé négligeable.
        lag_window_width: la largeur de la fenêtre de retards, deux fois m_hat.
        long_run_variance: la variance de long terme estimée, notée g(0).
        curvature: la grandeur G du papier, somme pondérée par le retard.
        upper_bound: le plafond de longueur de bloc appliqué.
        truncated: vrai si le plafond a mordu sur au moins une des deux valeurs.

    Note:
        Les grandeurs internes sont publiées pour que la règle soit vérifiable
        pas à pas. Le rapport ``circular / stationary`` vaut la racine cubique de
        3/2 tant que le plafond ne mord pas, et ce contrôle ne dépend d'aucune
        donnée.
    """

    stationary: float
    circular: float
    n_observations: int
    m_hat: int
    lag_window_width: int
    long_run_variance: float
    curvature: float
    upper_bound: float
    truncated: bool


# --------------------------------------------------------------------------- #
# Préparation et contrôle des entrées
# --------------------------------------------------------------------------- #


def _as_array(data: BootstrapInput, *, what: str, min_obs: int = MIN_OBSERVATIONS) -> npt.NDArray[np.float64]:
    """Rend les observations sous forme de tableau de flottants, lignes = dates.

    Args:
        data: les observations, série, tableau ou séquence.
        what: le nom du calcul, cité dans les messages d'erreur.
        min_obs: le nombre minimal de lignes exigé.

    Returns:
        Un tableau de dimension un ou deux, sans copie inutile.

    Raises:
        ConfigError: si l'entrée n'a ni une ni deux dimensions.
        DataQualityError: si une valeur manque.
        InsufficientDataError: si les lignes sont moins nombreuses que ``min_obs``.

    Note:
        Les valeurs manquantes lèvent au lieu d'être retirées. Retirer une ligne
        soude deux dates qui ne se touchaient pas, ce qui fabrique une adjacence
        que le bootstrap par blocs prendra ensuite pour de la dépendance réelle.
    """
    values = np.asarray(data, dtype=float)
    if values.ndim not in (1, 2):
        raise ConfigError(f"{what} attend une série ou un tableau, dimension reçue {values.ndim}")
    if values.size and np.isnan(values).any():
        raise DataQualityError(
            f"{what} refuse les valeurs manquantes : traitez-les avant de rééchantillonner"
        )
    if values.shape[0] < min_obs:
        raise InsufficientDataError(
            f"{what} exige au moins {min_obs} observations, {values.shape[0]} fournie(s)"
        )
    return values


def _check_positive_int(value: int, *, name: str) -> int:
    """Vérifie qu'un entier est strictement positif et le rend."""
    if int(value) != value or value < 1:
        raise ConfigError(f"{name} doit être un entier strictement positif, reçu {value}")
    return int(value)


def _check_generator(generator: np.random.Generator) -> np.random.Generator:
    """Vérifie que le générateur est bien un générateur NumPy moderne.

    Args:
        generator: le générateur passé par l'appelant.

    Returns:
        Le générateur lui-même.

    Raises:
        ConfigError: si l'objet n'est pas un ``numpy.random.Generator``.

    Note:
        Le contrôle est explicite parce que l'erreur qu'il attrape est
        silencieuse autrement. Un ``numpy.random.RandomState`` accepte
        ``integers`` sous un autre nom, et le laboratoire perdrait sa garantie de
        reproductibilité sans que rien ne le signale.
    """
    if not isinstance(generator, np.random.Generator):
        raise ConfigError(
            "generator doit être un numpy.random.Generator, "
            "obtenu par quantlab.core.determinism.make_generator ou child_generators"
        )
    return generator


def _resolve_size(size: int | None, n_observations: int) -> int:
    """Rend la longueur voulue d'un rééchantillon, par défaut celle de l'échantillon."""
    if size is None:
        return n_observations
    return _check_positive_int(size, name="size")


# --------------------------------------------------------------------------- #
# Tirage des indices
# --------------------------------------------------------------------------- #


def geometric_block_lengths(
    n_blocks: int,
    mean_block_size: float,
    generator: np.random.Generator,
) -> npt.NDArray[np.int64]:
    r"""Tire des longueurs de bloc selon la loi géométrique de Politis et Romano.

    **(1) Le problème.** Le bootstrap par blocs de longueur fixe rend une série
    qui n'est pas stationnaire, parce que la position d'une observation dans son
    bloc dépend de son rang. Il faut une longueur aléatoire.

    **(2) L'intuition.** À chaque pas, on jette une pièce biaisée : avec
    probabilité :math:`p` le bloc s'arrête, sinon il continue d'une observation.
    Le nombre de pas avant l'arrêt suit la loi géométrique, dont la propriété
    d'absence de mémoire est exactement ce qui rend la série stationnaire.

    **(3) La formule.**

    .. math::

        P(L = m) = (1 - p)^{m-1} p, \quad m = 1, 2, \dots,
        \qquad \mathbb{E}[L] = \frac{1}{p}

    **(4) Les variables.**

    - :math:`L` la longueur d'un bloc, entière et au moins égale à 1 ;
    - :math:`p` la probabilité d'arrêt à chaque pas ;
    - :math:`\mathbb{E}[L]` la longueur moyenne, l'inverse de :math:`p`.

    **(5) Les hypothèses.** Les longueurs sont indépendantes entre elles et
    indépendantes des points de départ des blocs.

    **(6) La provenance.** Politis et Romano (1994), *Journal of the American
    Statistical Association*, 89(428), 1303-1313, section 2.

    **(7) Les limites.** La loi géométrique n'a pas de borne supérieure. Un bloc
    tiré peut donc dépasser la longueur de la série, auquel cas le
    rééchantillonnage fait plusieurs fois le tour de l'anneau.

    **(8) Les alternatives.** Une longueur fixe donne le bootstrap de Künsch
    (1989), plus simple et non stationnaire. Une longueur uniforme existe dans la
    littérature et perd la propriété d'absence de mémoire.

    **(9) Pourquoi celle-ci.** C'est la seule loi discrète sans mémoire, donc la
    seule pour laquelle la probabilité qu'un bloc continue ne dépend pas de sa
    longueur déjà parcourue. Sans cela, la série rééchantillonnée trahirait la
    position des jointures.

    **(10) Comment vérifier.** La moyenne d'un grand tirage doit approcher
    ``mean_block_size``, et la fréquence des longueurs doit suivre la loi
    ci-dessus. Le test du module compare les deux à ``scipy.stats.geom``.

    Args:
        n_blocks: le nombre de longueurs à tirer.
        mean_block_size: la longueur moyenne voulue, strictement supérieure à 1.
        generator: le générateur aléatoire, passé explicitement.

    Returns:
        Un vecteur de ``n_blocks`` entiers valant au moins 1.

    Raises:
        ConfigError: si la longueur moyenne ne dépasse pas 1, ou si le nombre de
            blocs n'est pas un entier positif.
    """
    _check_positive_int(n_blocks, name="n_blocks")
    _check_generator(generator)
    if not mean_block_size > 1.0:
        raise ConfigError(
            f"mean_block_size doit dépasser 1, reçu {mean_block_size} ; "
            "une moyenne de 1 rend le bootstrap i.i.d."
        )
    if not np.isfinite(mean_block_size):
        raise ConfigError("mean_block_size doit être fini")
    return generator.geometric(1.0 / mean_block_size, size=n_blocks).astype(np.int64)


def _iid_indices(
    n_observations: int, size: int, n_resamples: int, generator: np.random.Generator
) -> npt.NDArray[np.intp]:
    """Tire des indices uniformes avec remise, sans aucune structure de bloc."""
    return generator.integers(0, n_observations, size=(n_resamples, size), dtype=np.intp)


def _fixed_block_indices(
    n_observations: int,
    block_size: int,
    size: int,
    n_resamples: int,
    generator: np.random.Generator,
    *,
    circular: bool,
) -> npt.NDArray[np.intp]:
    """Tire des indices par blocs de longueur fixe, en anneau ou non.

    Args:
        n_observations: la longueur de la série d'origine.
        block_size: la longueur d'un bloc.
        size: la longueur voulue du rééchantillon.
        n_resamples: le nombre de rééchantillons.
        generator: le générateur aléatoire.
        circular: vrai pour recoller la série en anneau.

    Returns:
        Une matrice d'indices de forme ``(n_resamples, size)``.

    Raises:
        ConfigError: en version non circulaire, si le bloc dépasse la série.
    """
    if not circular and block_size > n_observations:
        raise ConfigError(
            f"block_size={block_size} dépasse les {n_observations} observations ; "
            "utilisez la version circulaire ou réduisez le bloc"
        )
    n_blocks = math.ceil(size / block_size)
    high = n_observations if circular else n_observations - block_size + 1
    starts = generator.integers(0, high, size=(n_resamples, n_blocks), dtype=np.intp)
    offsets = np.arange(block_size, dtype=np.intp)
    indices = (starts[:, :, None] + offsets[None, None, :]).reshape(n_resamples, n_blocks * block_size)
    indices = indices[:, :size]
    if circular:
        indices = indices % n_observations
    return np.ascontiguousarray(indices)


def _stationary_indices(
    n_observations: int,
    mean_block_size: float,
    size: int,
    n_resamples: int,
    generator: np.random.Generator,
) -> npt.NDArray[np.intp]:
    """Tire des indices par blocs géométriques, la série étant recollée en anneau.

    Args:
        n_observations: la longueur de la série d'origine.
        mean_block_size: la longueur moyenne d'un bloc.
        size: la longueur voulue du rééchantillon.
        n_resamples: le nombre de rééchantillons.
        generator: le générateur aléatoire.

    Returns:
        Une matrice d'indices de forme ``(n_resamples, size)``.

    Note:
        Les longueurs sont tirées par :func:`geometric_block_lengths`, une par
        bloc, jusqu'à couvrir la longueur voulue. Le dernier bloc est tronqué,
        ce qui est la construction de Politis et Romano (1994).
    """
    indices = np.empty((n_resamples, size), dtype=np.intp)
    for row in range(n_resamples):
        lengths = geometric_block_lengths(size, mean_block_size, generator)
        ends = np.cumsum(lengths)
        # ends[size - 1] >= size puisque chaque longueur vaut au moins 1, donc la
        # recherche trouve toujours un bloc de couverture.
        n_blocks = int(np.searchsorted(ends, size, side="left")) + 1
        lengths = lengths[:n_blocks]
        ends = ends[:n_blocks]
        starts = generator.integers(0, n_observations, size=n_blocks, dtype=np.intp)
        block_of = np.repeat(np.arange(n_blocks, dtype=np.intp), lengths)
        within = np.arange(int(ends[-1]), dtype=np.intp) - np.repeat(ends - lengths, lengths)
        indices[row] = ((starts[block_of] + within) % n_observations)[:size]
    return indices


def bootstrap_indices(
    n_observations: int,
    method: BootstrapMethod | str,
    n_resamples: int,
    generator: np.random.Generator,
    *,
    size: int | None = None,
    block_size: int | None = None,
    mean_block_size: float | None = None,
) -> npt.NDArray[np.intp]:
    """Rend la matrice d'indices d'un rééchantillonnage, sans toucher aux données.

    Séparer les indices des données sert à une chose précise : rééchantillonner
    plusieurs séries alignées avec exactement le même tirage. Un signal et son
    rendement futur doivent bouger ensemble, sans quoi le lien entre les deux est
    détruit par le rééchantillonnage lui-même.

    Args:
        n_observations: la longueur de la série d'origine.
        method: la méthode de rééchantillonnage, valeur de :class:`BootstrapMethod`.
        n_resamples: le nombre de rééchantillons à tirer.
        generator: le générateur aléatoire, passé explicitement.
        size: la longueur voulue d'un rééchantillon. Par défaut celle de la série.
        block_size: la longueur de bloc des deux méthodes à bloc fixe.
        mean_block_size: la longueur moyenne du bootstrap stationnaire.

    Returns:
        Une matrice d'entiers de forme ``(n_resamples, size)``, valeurs dans
        l'intervalle des indices valides.

    Raises:
        ConfigError: si un paramètre manque pour la méthode demandée, ou si un
            paramètre est incohérent.
    """
    _check_positive_int(n_observations, name="n_observations")
    _check_positive_int(n_resamples, name="n_resamples")
    _check_generator(generator)
    resolved = _resolve_size(size, n_observations)
    kind = BootstrapMethod(method)
    if kind is BootstrapMethod.IID:
        return _iid_indices(n_observations, resolved, n_resamples, generator)
    if kind is BootstrapMethod.STATIONARY:
        if mean_block_size is None:
            raise ConfigError("le bootstrap stationnaire exige mean_block_size")
        return _stationary_indices(n_observations, mean_block_size, resolved, n_resamples, generator)
    if block_size is None:
        raise ConfigError(f"la méthode {kind} exige block_size")
    _check_positive_int(block_size, name="block_size")
    return _fixed_block_indices(
        n_observations,
        int(block_size),
        resolved,
        n_resamples,
        generator,
        circular=kind is BootstrapMethod.CIRCULAR_BLOCK,
    )


# --------------------------------------------------------------------------- #
# Les trois rééchantillonneurs
# --------------------------------------------------------------------------- #


def iid_bootstrap(
    data: BootstrapInput,
    n_resamples: int,
    generator: np.random.Generator,
    *,
    size: int | None = None,
) -> npt.NDArray[np.float64]:
    r"""Rééchantillonne les observations une par une, avec remise.

    **Avertissement, à lire avant l'appel.** Cette fonction détruit la structure
    temporelle. Elle ne doit servir que sur des données réellement indépendantes,
    par exemple des tirages simulés ou une coupe transversale. Sur des rendements
    autocorrélés, elle rend une erreur type trop petite, donc un intervalle trop
    étroit et une significativité surestimée. La documentation de tête du module
    chiffre le manque à 18,4 % de largeur pour une autocorrélation de 0,2.

    **(1) Le problème.** Estimer la dispersion d'une statistique sans connaître
    la loi des données.

    **(2) L'intuition.** La distribution empirique est le meilleur substitut de
    la loi inconnue. Tirer dedans avec remise imite un nouvel échantillon.

    **(3) La formule.** Le rééchantillon :math:`X^*` est indexé par des indices
    indépendants et uniformes.

    .. math::

        I_1, \dots, I_n \overset{\text{i.i.d.}}{\sim} \mathcal{U}\{1, \dots, n\},
        \qquad X^*_t = X_{I_t}

    **(4) Les variables.**

    - :math:`n` le nombre d'observations d'origine ;
    - :math:`I_t` l'indice tiré pour la position :math:`t` ;
    - :math:`X^*_t` la valeur rééchantillonnée à cette position.

    **(5) Les hypothèses.** Les observations sont indépendantes et de même loi.
    C'est l'hypothèse que les rendements financiers violent le plus souvent.

    **(6) La provenance.** Efron (1979), *Annals of Statistics*, 7(1), 1-26.

    **(7) Les limites.** Aucune dépendance n'est préservée, ni temporelle, ni
    transversale entre lignes. La loi des extrêmes n'est pas bien approchée non
    plus, le maximum d'un rééchantillon ne pouvant jamais dépasser celui de
    l'échantillon.

    **(8) Les alternatives.** :func:`block_bootstrap` et
    :func:`stationary_bootstrap` préservent la dépendance temporelle.

    **(9) Pourquoi la garder.** Elle est le repère face auquel se lit l'apport
    des méthodes à blocs. Comparer son erreur type à celle d'un bootstrap par
    blocs mesure, sur la série étudiée, ce que l'hypothèse d'indépendance coûte.

    **(10) Comment vérifier.** Chaque valeur rééchantillonnée appartient à
    l'échantillon d'origine, et sur des données simulées indépendantes,
    l'intervalle de la moyenne couvre la vraie moyenne dans 95 % des répétitions.

    Args:
        data: les observations, série, tableau ou séquence. Les lignes sont des
            dates, les colonnes éventuelles des actifs.
        n_resamples: le nombre de rééchantillons à tirer.
        generator: le générateur aléatoire, passé explicitement.
        size: la longueur voulue d'un rééchantillon. Par défaut celle des données.

    Returns:
        Un tableau de forme ``(n_resamples, size)`` pour une série, ou
        ``(n_resamples, size, n_colonnes)`` pour un tableau.

    Raises:
        DataQualityError: si une valeur manque.
        InsufficientDataError: s'il y a moins de deux observations.
    """
    values = _as_array(data, what="iid_bootstrap")
    indices = bootstrap_indices(values.shape[0], BootstrapMethod.IID, n_resamples, generator, size=size)
    return values[indices]


def block_bootstrap(
    data: BootstrapInput,
    block_size: int,
    n_resamples: int,
    generator: np.random.Generator,
    *,
    circular: bool = True,
    size: int | None = None,
) -> npt.NDArray[np.float64]:
    r"""Rééchantillonne des blocs d'observations consécutives, de longueur fixe.

    **(1) Le problème.** Le bootstrap i.i.d. casse l'ordre du temps, donc il
    perd l'autocorrélation qui fait justement la difficulté des rendements.

    **(2) L'intuition.** Découper la série en tranches consécutives et tirer les
    tranches, pas les points. La dépendance à l'intérieur d'une tranche part avec
    elle, et seules les jointures entre tranches sont fausses.

    **(3) La formule.** Avec :math:`b` la longueur de bloc et :math:`k` le nombre
    de blocs nécessaires pour couvrir :math:`n` positions, la version circulaire
    tire des départs uniformes sur l'anneau.

    .. math::

        S_1, \dots, S_k \overset{\text{i.i.d.}}{\sim} \mathcal{U}\{0, \dots, n-1\},
        \qquad X^*_{(j-1)b + i} = X_{\,(S_j + i - 1) \bmod n \,+\, 1}

    En version non circulaire, les départs sont uniformes sur
    :math:`\{1, \dots, n - b + 1\}` et aucun repli n'a lieu.

    **(4) Les variables.**

    - :math:`b` la longueur de bloc, ``block_size`` ;
    - :math:`k = \lceil n / b \rceil` le nombre de blocs concaténés ;
    - :math:`S_j` le départ du bloc :math:`j` ;
    - :math:`X^*` la série rééchantillonnée, tronquée à la longueur voulue.

    **(5) Les hypothèses.** La série est stationnaire et sa dépendance est de
    portée courte devant :math:`b`. Une autocorrélation de longue mémoire n'est
    pas capturée par des blocs de taille raisonnable.

    **(6) La provenance.** Künsch (1989), *Annals of Statistics*, 17(3),
    1217-1241, pour la version à blocs mobiles. Politis et Romano (1992), dans
    *Exploring the Limits of Bootstrap*, Wiley, 263-270, pour la version
    circulaire.

    **(7) Les limites.** Deux, et elles sont de nature différente. D'abord la
    série rééchantillonnée n'est pas stationnaire, puisque la loi d'une
    observation dépend de sa position dans son bloc. Ensuite la version non
    circulaire sous-échantillonne les bords : la première observation ne peut
    apparaître qu'en tête de bloc, alors qu'une observation centrale peut
    apparaître à n'importe laquelle des :math:`b` positions. La version
    circulaire corrige ce second défaut, et c'est pourquoi elle est le défaut.

    **(8) Les alternatives.** :func:`stationary_bootstrap` rend la stationnarité
    au prix d'une longueur de bloc aléatoire.

    **(9) Pourquoi cette méthode.** Elle est la plus simple qui préserve la
    dépendance, et son unique paramètre se choisit par
    :func:`optimal_block_size`.

    **(10) Comment vérifier.** La version circulaire rend des rééchantillons de
    longueur exactement égale à l'originale, chaque observation ayant la même
    probabilité d'apparaître. Un bloc de longueur 1 redonne le bootstrap i.i.d.

    Args:
        data: les observations, lignes = dates.
        block_size: la longueur d'un bloc, entier strictement positif.
        n_resamples: le nombre de rééchantillons à tirer.
        generator: le générateur aléatoire, passé explicitement.
        circular: vrai pour recoller la série en anneau, ce qui est le défaut.
        size: la longueur voulue d'un rééchantillon. Par défaut celle des données.

    Returns:
        Un tableau de forme ``(n_resamples, size)`` ou
        ``(n_resamples, size, n_colonnes)``.

    Raises:
        ConfigError: si le bloc dépasse la série en version non circulaire.
    """
    values = _as_array(data, what="block_bootstrap")
    method = BootstrapMethod.CIRCULAR_BLOCK if circular else BootstrapMethod.MOVING_BLOCK
    indices = bootstrap_indices(
        values.shape[0], method, n_resamples, generator, size=size, block_size=block_size
    )
    return values[indices]


def stationary_bootstrap(
    data: BootstrapInput,
    mean_block_size: float,
    n_resamples: int,
    generator: np.random.Generator,
    *,
    size: int | None = None,
) -> npt.NDArray[np.float64]:
    r"""Rééchantillonne des blocs de longueur géométrique, sur la série en anneau.

    **(1) Le problème.** Le bootstrap par blocs de longueur fixe rend une série
    qui n'est pas stationnaire. La position d'une observation dans son bloc est
    connue de la construction, donc la loi de :math:`X^*_t` dépend de :math:`t`.
    Les blocs commencent aux positions 1, :math:`b+1`, :math:`2b+1`, et une
    observation qui tombe en tête de bloc n'a pas le même voisinage qu'une autre.

    **(2) L'intuition, et pourquoi la stationnarité revient.** Rendre la longueur
    de bloc aléatoire et sans mémoire. Si le bloc s'arrête avec une probabilité
    constante à chaque pas, alors savoir qu'un bloc dure déjà depuis cinq
    observations n'apprend rien sur sa durée restante. Aucune position n'est
    marquée, et Politis et Romano (1994) montrent que la série rééchantillonnée
    est alors strictement stationnaire, conditionnellement aux données.

    **(3) La formule.** Les longueurs suivent la loi géométrique, les départs
    sont uniformes sur l'anneau.

    .. math::

        L_1, L_2, \dots \overset{\text{i.i.d.}}{\sim} \text{Géom}(p),
        \qquad P(L = m) = (1-p)^{m-1} p,
        \qquad p = \frac{1}{\ell}

    **(4) Les variables.**

    - :math:`\ell` la longueur moyenne de bloc, ``mean_block_size`` ;
    - :math:`p` la probabilité d'arrêt à chaque pas, l'inverse de :math:`\ell` ;
    - :math:`L_j` la longueur du bloc :math:`j` ;
    - :math:`n` la longueur de la série d'origine.

    **(5) Les hypothèses.** La série est stationnaire et faiblement dépendante.
    Le mélange doit être assez rapide pour que la dépendance au-delà de quelques
    longueurs moyennes de bloc soit négligeable.

    **(6) La provenance.** Politis et Romano (1994), *Journal of the American
    Statistical Association*, 89(428), 1303-1313.

    **(7) Les limites.** La variance de l'estimateur bootstrap est un peu plus
    grande que celle du bootstrap par blocs circulaires à longueur moyenne égale.
    Lahiri (1999) l'établit, et c'est le prix de la stationnarité. Un bloc tiré
    peut aussi dépasser la longueur de la série, la construction faisant alors
    plusieurs fois le tour de l'anneau.

    **(8) Les alternatives.** :func:`block_bootstrap` en version circulaire, plus
    efficace en variance et non stationnaire.

    **(9) Pourquoi cette méthode.** Quand la statistique dépend de la loi jointe
    de la série et pas seulement d'une moyenne, la non-stationnarité du bloc fixe
    se voit dans le résultat. La longueur aléatoire l'efface.

    **(10) Comment vérifier.** Les longueurs de bloc tirées suivent une loi
    géométrique de moyenne ``mean_block_size``, ce que le test du module contrôle
    sur un grand tirage contre ``scipy.stats.geom``.

    Args:
        data: les observations, lignes = dates.
        mean_block_size: la longueur moyenne d'un bloc, strictement supérieure à 1.
        n_resamples: le nombre de rééchantillons à tirer.
        generator: le générateur aléatoire, passé explicitement.
        size: la longueur voulue d'un rééchantillon. Par défaut celle des données.

    Returns:
        Un tableau de forme ``(n_resamples, size)`` ou
        ``(n_resamples, size, n_colonnes)``.

    Raises:
        ConfigError: si la longueur moyenne ne dépasse pas 1.
    """
    values = _as_array(data, what="stationary_bootstrap")
    indices = bootstrap_indices(
        values.shape[0],
        BootstrapMethod.STATIONARY,
        n_resamples,
        generator,
        size=size,
        mean_block_size=mean_block_size,
    )
    return values[indices]


# --------------------------------------------------------------------------- #
# Choix automatique de la longueur de bloc
# --------------------------------------------------------------------------- #


def _flat_top_weight(lag: int, window_width: int) -> float:
    r"""Rend le poids de la fenêtre à sommet plat de Politis et Romano (1995).

    Args:
        lag: le retard, entier positif.
        window_width: la largeur de la fenêtre, notée M.

    Returns:
        Le poids, valant 1 jusqu'à la moitié de la fenêtre puis décroissant
        linéairement jusqu'à zéro.

    Note:
        Le sommet plat est ce qui distingue cette fenêtre de celle de Bartlett.
        Sur la première moitié des retards le poids vaut exactement 1, donc les
        autocovariances proches ne sont pas rétrécies. C'est ce qui donne à
        l'estimateur spectral son biais d'ordre supérieur.
    """
    ratio = lag / window_width
    if ratio <= 0.5:
        return 1.0
    if ratio <= 1.0:
        return 2.0 * (1.0 - ratio)
    return 0.0


def _politis_white(values: npt.NDArray[np.float64]) -> BlockSizeSelection:
    """Applique la règle de Politis et White (2004), corrigée en 2009.

    Args:
        values: la série, vecteur de flottants sans valeur manquante.

    Returns:
        Le résultat structuré, longueurs optimales et grandeurs internes.

    Raises:
        DataQualityError: si la variance de long terme estimée est nulle, ce qui
            rend la longueur optimale non définie.
    """
    n = values.shape[0]
    centered = values - values.mean()
    upper_bound = math.ceil(min(3.0 * math.sqrt(n), n / 3.0))
    # K_N du papier, note c : le nombre de retards consécutifs qui doivent tous
    # être négligeables. Le papier écrit max(5, racine(log10 n)) sans arrondi ; la
    # montée à l'entier supérieur ne change rien, la racine du logarithme décimal
    # restant sous 5 pour tout n inférieur à 10 puissance 25.
    k_n = max(5, math.ceil(math.sqrt(math.log10(n))))
    m_max = min(math.ceil(math.sqrt(n)) + k_n, n - 2)
    threshold = 2.0 * math.sqrt(math.log10(n) / n)

    autocovariance = np.empty(m_max + 1)
    abs_autocorrelation = np.empty(m_max + 1)
    for lag in range(m_max + 1):
        head = centered[lag:]
        tail = centered[: n - lag]
        cross = float(head @ tail)
        autocovariance[lag] = cross / n
        var_head = float(centered[lag + 1 :] @ centered[lag + 1 :])
        var_tail = float(centered[: -(lag + 1)] @ centered[: -(lag + 1)])
        abs_autocorrelation[lag] = abs(cross) / math.sqrt(var_head * var_tail)

    m_hat: int | None = None
    for lag in range(k_n, m_max + 1):
        if bool(np.all(abs_autocorrelation[lag - k_n : lag] < threshold)):
            m_hat = lag - k_n
            break
    window_width = min(2 * max(m_hat, 1), m_max) if m_hat is not None else m_max

    curvature = 0.0
    long_run_variance = float(autocovariance[0])
    for lag in range(1, window_width + 1):
        weight = _flat_top_weight(lag, window_width)
        curvature += 2.0 * weight * lag * float(autocovariance[lag])
        long_run_variance += 2.0 * weight * float(autocovariance[lag])
    if long_run_variance == 0.0:
        raise DataQualityError(
            "la variance de long terme estimée est nulle, la longueur de bloc optimale "
            "n'est pas définie sur cette série"
        )

    d_stationary = 2.0 * long_run_variance**2
    d_circular = (4.0 / 3.0) * long_run_variance**2
    b_stationary = (2.0 * curvature**2 / d_stationary) ** (1.0 / 3.0) * n ** (1.0 / 3.0)
    b_circular = (2.0 * curvature**2 / d_circular) ** (1.0 / 3.0) * n ** (1.0 / 3.0)
    truncated = b_stationary > upper_bound or b_circular > upper_bound
    return BlockSizeSelection(
        stationary=min(b_stationary, float(upper_bound)),
        circular=min(b_circular, float(upper_bound)),
        n_observations=n,
        m_hat=m_hat if m_hat is not None else window_width,
        lag_window_width=window_width,
        long_run_variance=long_run_variance,
        curvature=curvature,
        upper_bound=float(upper_bound),
        truncated=truncated,
    )


def politis_white_block_sizes(data: BootstrapInput) -> BlockSizeSelection:
    r"""Rend les deux longueurs de bloc optimales et les grandeurs qui les fabriquent.

    **(1) Le problème.** La longueur de bloc décide du résultat, et rien dans les
    données ne la donne d'emblée. Trop courte, la dépendance est perdue. Trop
    longue, la variété des rééchantillons s'effondre.

    **(2) L'intuition.** L'erreur quadratique de l'estimateur bootstrap se
    décompose en un biais qui décroît avec la longueur de bloc et une variance
    qui croît avec elle. Minimiser la somme donne une longueur qui grandit comme
    la racine cubique du nombre d'observations, et dont la constante se lit dans
    le corrélogramme.

    **(3) La formule.**

    .. math::

        b^{OPT}_i = \left(\frac{2 \hat{G}^2}{d_i}\, n\right)^{1/3},
        \qquad d_i = c_i \left(\hat{g}(0)\right)^2

    .. math::

        \hat{G} = \sum_{k=-M}^{M} \lambda\!\left(\frac{k}{M}\right) |k|
        \hat{\gamma}(k),
        \qquad
        \hat{g}(0) = \sum_{k=-M}^{M} \lambda\!\left(\frac{k}{M}\right)
        \hat{\gamma}(k)

    .. math::

        \lambda(s) = \min\bigl(1,\, 2(1 - |s|)\bigr)^{+},
        \qquad
        \hat{\gamma}(k) = \frac{1}{n} \sum_{t=k+1}^{n}
        (x_t - \bar{x})(x_{t-k} - \bar{x})

    **(4) Les variables.**

    - :math:`n` le nombre d'observations ;
    - :math:`\hat{\gamma}(k)` l'autocovariance empirique au retard :math:`k` ;
    - :math:`\lambda` la fenêtre à sommet plat de Politis et Romano (1995) ;
    - :math:`M` la largeur de fenêtre, égale à deux fois le retard au-delà
      duquel le corrélogramme est jugé négligeable ;
    - :math:`\hat{g}(0)` la variance de long terme, densité spectrale en zéro ;
    - :math:`\hat{G}` la somme pondérée par le retard, qui mesure la persistance ;
    - :math:`c_i` la constante de méthode, 2 pour le bootstrap stationnaire et
      4/3 pour le bootstrap par blocs circulaires.

    **(5) Les hypothèses.** La série est stationnaire, ses autocovariances sont
    sommables, et la statistique visée est une moyenne ou s'y ramène. La règle
    optimise l'erreur quadratique de l'estimateur de variance, pas celle d'un
    quantile.

    **(6) La provenance.** Politis et White (2004), *Econometric Reviews*, 23(1),
    53-70. Les constantes :math:`c_i` sont celles de la correction de Patton,
    Politis et White (2009), *Econometric Reviews*, 28(4), 372-375, qui suit la
    rectification des résultats de Lahiri (1999) par Nordman (2008).

    **(7) Les limites, et l'écart déclaré avec le programme des auteurs.** Trois
    différences séparent ce code du programme MATLAB de Patton, et elles portent
    toutes sur le choix du retard :math:`\hat{m}`. D'abord les
    autocorrélations sont calculées sur la longueur maximale disponible à chaque
    retard, alors que le programme des auteurs les calcule sur un échantillon
    commun tronqué à :math:`M_{max}`. Ensuite le corrélogramme est normalisé par
    la racine du produit des deux variances décalées, et non par la variance
    unique de la série. Enfin, quand aucune suite de :math:`K_N` autocorrélations
    négligeables n'existe, ce code retient :math:`M = M_{max}`, là où le
    programme des auteurs retient le dernier retard individuellement
    significatif. Ces trois écarts sont ceux de l'implémentation de ``arch``, qui
    déclare les deux premiers. Ils ne changent qu'un paramètre de réglage, jamais
    la formule finale, mais ils peuvent déplacer :math:`\hat{m}` d'un retard sur
    une série limite. Le résultat n'est donc pas la règle des auteurs au chiffre
    près, et c'est écrit ici plutôt que passé sous silence.

    **(7 bis) Ce que le contrôle contre ``arch`` ne prouve pas.** Ce code est une
    transcription de la même règle, donc leur accord atteste la transcription et
    non la règle. Le contrôle indépendant est la valeur de population sur un
    AR(1), écrite au point (10).

    **(8) Les alternatives.** Hall, Horowitz et Jing (1995) proposent un choix
    par sous-échantillonnage, plus coûteux et sans forme fermée. Le choix
    manuel reste légitime s'il est déclaré.

    **(9) Pourquoi cette règle.** Elle est la seule à donner une longueur en une
    passe, sans rééchantillonnage préalable, et c'est celle qu'implémentent les
    bibliothèques de référence, ce qui la rend vérifiable.

    **(10) Comment vérifier.** Deux contrôles indépendants des données. Le
    rapport des deux longueurs vaut la racine cubique de 3/2 tant que le plafond
    ne mord pas. Et sur un processus autorégressif d'ordre un de coefficient
    connu, la valeur de population se calcule en forme fermée, ce que le test du
    module fait.

    Args:
        data: la série, un vecteur d'observations rangées par le temps.

    Returns:
        Le résultat structuré, longueurs optimales et grandeurs internes.

    Raises:
        ConfigError: si la série n'est pas unidimensionnelle.
        InsufficientDataError: si la série porte moins de seize observations.
        DataQualityError: si la variance de long terme estimée est nulle.
    """
    values = _as_array(data, what="politis_white_block_sizes", min_obs=MIN_OBSERVATIONS_BLOCK_RULE)
    if values.ndim != 1:
        raise ConfigError(
            "la règle de Politis et White s'applique à une série ; "
            "pour un tableau, appelez-la colonne par colonne"
        )
    return _politis_white(values)


def optimal_block_size(
    data: BootstrapInput,
    method: BlockSizeRule = "politis_white",
    *,
    bootstrap: BootstrapMethod | str = BootstrapMethod.STATIONARY,
    floor: float = DEFAULT_BLOCK_SIZE_FLOOR,
) -> float:
    """Rend la longueur de bloc optimale pour la méthode de bootstrap visée.

    La fonction est la façade de :func:`politis_white_block_sizes`, dont elle ne
    garde qu'un nombre. La docstring de cette dernière porte la formule, les
    hypothèses et l'écart déclaré avec le programme des auteurs.

    Args:
        data: la série, un vecteur d'observations rangées par le temps.
        method: la règle de sélection. Seule ``"politis_white"`` existe ici.
        bootstrap: la méthode visée, qui décide de la constante employée. Le
            bootstrap stationnaire prend 2, les deux méthodes à bloc fixe 4/3.
        floor: la valeur minimale rendue. Un bloc de longueur 1 est le bootstrap
            i.i.d., donc la plus petite valeur consommable en aval.

    Returns:
        La longueur de bloc optimale, réelle et non arrondie. Les fonctions à
        bloc fixe attendent un entier, l'arrondi restant à la charge de
        l'appelant pour qu'il soit visible.

    Raises:
        ConfigError: si la règle demandée n'existe pas, ou si la série n'est pas
            unidimensionnelle.

    Note:
        Une valeur qui touche le plancher signale une dépendance non détectable,
        et non une erreur. Sur du bruit blanc, la grandeur G du papier tend vers
        zéro, donc la longueur optimale aussi.
    """
    if method != "politis_white":
        raise ConfigError(f"règle de sélection inconnue : {method}")
    if floor < 1.0:
        raise ConfigError(f"floor doit valoir au moins 1, reçu {floor}")
    selection = politis_white_block_sizes(data)
    kind = BootstrapMethod(bootstrap)
    if kind is BootstrapMethod.IID:
        raise ConfigError("le bootstrap i.i.d. n'a pas de longueur de bloc")
    raw = selection.stationary if kind is BootstrapMethod.STATIONARY else selection.circular
    if raw < floor:
        log.debug(
            "longueur de bloc portée au plancher",
            extra={"raw": raw, "floor": floor, "n_observations": selection.n_observations},
        )
    return max(raw, floor)


# --------------------------------------------------------------------------- #
# Distribution, intervalles et valeur p
# --------------------------------------------------------------------------- #


def bootstrap_statistic(
    data: BootstrapInput,
    statistic_fn: StatisticFn,
    method: BootstrapMethod | str,
    n_resamples: int,
    generator: np.random.Generator,
    *,
    block_size: int | None = None,
    mean_block_size: float | None = None,
    size: int | None = None,
) -> BootstrapDistribution:
    r"""Applique une statistique à chaque rééchantillon et rend sa distribution.

    **(1) Le problème.** Une statistique quelconque, ratio de Sharpe ou rendement
    moyen, n'a pas d'erreur type en forme fermée dès qu'elle est non linéaire ou
    que les données sont dépendantes.

    **(2) L'intuition.** Rejouer le tirage :math:`B` fois et regarder de combien
    la statistique bouge. Sa dispersion sur les répliques estime sa dispersion
    d'échantillonnage.

    **(3) La formule.**

    .. math::

        \hat{\theta}^*_b = s(X^*_b), \quad b = 1, \dots, B,
        \qquad
        \widehat{se} = \sqrt{\frac{1}{B-1} \sum_{b=1}^{B}
        \left(\hat{\theta}^*_b - \overline{\theta^*}\right)^2}

    **(4) Les variables.**

    - :math:`s` la statistique, ``statistic_fn`` ;
    - :math:`X^*_b` le rééchantillon numéro :math:`b` ;
    - :math:`B` le nombre de rééchantillons, ``n_resamples`` ;
    - :math:`\widehat{se}` l'erreur type bootstrap.

    **(5) Les hypothèses.** Celles de la méthode de rééchantillonnage choisie. La
    statistique doit de plus être une fonctionnelle régulière de la loi
    empirique, ce que la médiane et les quantiles extrêmes ne sont pas.

    **(6) La provenance.** Efron (1979), et Efron et Tibshirani (1993),
    *An Introduction to the Bootstrap*, chapitres 6 et 8.

    **(7) Les limites.** Le nombre de répliques introduit sa propre erreur de
    Monte-Carlo. Efron et Tibshirani (1993) tiennent 200 répliques pour
    suffisantes sur une erreur type et en recommandent au moins 1 000 pour un
    intervalle de confiance, dont les quantiles extrêmes convergent plus
    lentement. Statut de ces deux nombres : précepte d'auteurs, sans mesure ici.

    **(8) Les alternatives.** La méthode delta donne une erreur type analytique
    quand la statistique est différentiable et la loi connue. Le jackknife coûte
    :math:`n` évaluations au lieu de :math:`B`.

    **(9) Pourquoi cette méthode.** Elle ne demande rien à la statistique, ce qui
    permet de faire passer le même contrôle à un ratio de Sharpe, à une perte
    maximale et à un coefficient d'information.

    **(10) Comment vérifier.** Sur la moyenne d'un échantillon simulé
    indépendant, l'erreur type bootstrap doit approcher l'écart type divisé par
    la racine du nombre d'observations, dont la valeur est connue.

    Args:
        data: les observations, lignes = dates.
        statistic_fn: la statistique, appliquée au tableau d'un rééchantillon.
        method: la méthode de rééchantillonnage, valeur de :class:`BootstrapMethod`.
        n_resamples: le nombre de rééchantillons à tirer.
        generator: le générateur aléatoire, passé explicitement.
        block_size: la longueur de bloc des deux méthodes à bloc fixe.
        mean_block_size: la longueur moyenne du bootstrap stationnaire.
        size: la longueur voulue d'un rééchantillon. Par défaut celle des données.

    Returns:
        La distribution bootstrap, statistique observée et répliques.

    Raises:
        ConfigError: si un paramètre manque pour la méthode demandée.
        DataQualityError: si une réplique n'est pas un nombre fini.
    """
    values = _as_array(data, what="bootstrap_statistic")
    kind = BootstrapMethod(method)
    indices = bootstrap_indices(
        values.shape[0],
        kind,
        n_resamples,
        generator,
        size=size,
        block_size=block_size,
        mean_block_size=mean_block_size,
    )
    replicates = np.empty(indices.shape[0], dtype=float)
    for position, row in enumerate(indices):
        replicates[position] = float(statistic_fn(values[row]))
    if not np.isfinite(replicates).all():
        raise DataQualityError(
            "une réplique n'est pas un nombre fini ; la statistique est probablement "
            "indéfinie sur un rééchantillon dégénéré"
        )
    if kind is BootstrapMethod.STATIONARY:
        effective_block: float | None = float(mean_block_size) if mean_block_size is not None else None
    elif kind is BootstrapMethod.IID:
        effective_block = None
    else:
        effective_block = float(block_size) if block_size is not None else None
    return BootstrapDistribution(
        observed=float(statistic_fn(values)),
        replicates=replicates,
        method=kind,
        n_resamples=int(indices.shape[0]),
        n_observations=int(values.shape[0]),
        block_size=effective_block,
    )


def bootstrap_confidence_interval(
    distribution: BootstrapDistribution,
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
    method: IntervalMethod = "percentile",
) -> BootstrapInterval:
    r"""Rend un intervalle de confiance bootstrap, par percentile ou par la méthode basique.

    **(1) Le problème.** L'erreur type seule ne suffit pas à borner un paramètre
    quand la distribution bootstrap est asymétrique. Il faut des bornes lues dans
    cette distribution.

    **(2) L'intuition, et la différence entre les deux méthodes.** La méthode par
    percentile prend directement les quantiles des répliques. La méthode basique
    part de l'idée que la distribution de :math:`\hat{\theta}^* - \hat{\theta}`
    imite celle de :math:`\hat{\theta} - \theta`, puis renverse cette relation.
    Le renversement retourne l'intervalle autour de la valeur observée.

    **(3) Les formules.** Avec :math:`\alpha = 1 - \text{niveau}` et
    :math:`q^*_u` le quantile empirique des répliques d'ordre :math:`u` :

    .. math::

        \text{percentile} : \left[q^*_{\alpha/2},\; q^*_{1-\alpha/2}\right]

    .. math::

        \text{basique} : \left[2\hat{\theta} - q^*_{1-\alpha/2},\;
        2\hat{\theta} - q^*_{\alpha/2}\right]

    **(4) Les variables.**

    - :math:`\hat{\theta}` la statistique observée ;
    - :math:`q^*_u` le quantile d'ordre :math:`u` des répliques ;
    - :math:`\alpha` la probabilité totale rejetée, répartie également.

    **(5) Les hypothèses.** La méthode par percentile suppose qu'il existe une
    transformation croissante rendant la distribution de la statistique
    symétrique et de dispersion constante. La méthode basique suppose que la
    distribution de l'écart ne dépend pas du paramètre.

    **(6) La provenance.** Efron (1979) pour le percentile. Davison et Hinkley
    (1997), *Bootstrap Methods and their Application*, section 5.2, pour la
    méthode basique.

    **(7) Les limites, et pourquoi le percentile est biaisé sur une loi
    asymétrique.** La distribution bootstrap est centrée sur
    :math:`\hat{\theta}`, pas sur :math:`\theta`. Quand l'estimateur est biaisé
    ou que sa loi est asymétrique, l'intervalle par percentile hérite du décalage
    au lieu de le corriger. Exemple travaillé : si l'estimateur surestime le
    paramètre, les répliques se massent au-dessus de la vraie valeur, et les deux
    bornes montent ensemble. La couverture réelle tombe alors sous le niveau
    annoncé, d'un côté plus que de l'autre. La méthode basique corrige ce
    décalage par la réflexion autour de :math:`\hat{\theta}`, au prix de bornes
    qui peuvent sortir du domaine du paramètre, par exemple une variance
    négative.

    **(8) Les alternatives, dont BCa qui n'est pas implémentée ici.** L'intervalle
    BCa d'Efron (1987) corrige à la fois le biais et l'asymétrie. Il estime une
    correction de biais par la part des répliques sous la valeur observée, et une
    accélération par le jackknife. Sa couverture est exacte au deuxième ordre là
    où le percentile ne l'est qu'au premier. Il n'est pas implémenté ici parce
    que l'accélération demande :math:`n` réévaluations de la statistique, ce que
    le laboratoire préfère décider étude par étude. La bibliothèque ``scipy``
    l'offre sous ``scipy.stats.bootstrap`` pour des données indépendantes.

    **(9) Pourquoi ces deux-là.** Elles n'exigent aucun calcul de plus que les
    répliques déjà tirées. Leur écart mesure l'asymétrie de la distribution
    bootstrap. Un écart important entre les deux est le signal qu'il faut passer
    à BCa.

    **(10) Comment vérifier.** Sur des données simulées indépendantes, la
    couverture de la moyenne doit approcher le niveau annoncé, et le test du
    module la mesure sur deux cents répétitions.

    Args:
        distribution: la distribution bootstrap, rendue par
            :func:`bootstrap_statistic`.
        confidence_level: le niveau de confiance, strictement entre 0 et 1.
        method: ``"percentile"`` ou ``"basic"``.

    Returns:
        L'intervalle, avec ses bornes et la méthode employée.

    Raises:
        ConfigError: si le niveau sort de l'intervalle ouvert, ou si la méthode
            est inconnue.
    """
    if not 0.0 < confidence_level < 1.0:
        raise ConfigError(f"confidence_level doit être strictement entre 0 et 1, reçu {confidence_level}")
    if method not in ("percentile", "basic"):
        raise ConfigError(f"méthode d'intervalle inconnue : {method}")
    alpha = 1.0 - confidence_level
    low_quantile = distribution.quantile(alpha / 2.0)
    high_quantile = distribution.quantile(1.0 - alpha / 2.0)
    if method == "percentile":
        low, high = low_quantile, high_quantile
    else:
        low = 2.0 * distribution.observed - high_quantile
        high = 2.0 * distribution.observed - low_quantile
    return BootstrapInterval(
        low=low,
        high=high,
        confidence_level=confidence_level,
        observed=distribution.observed,
        method=method,
        n_resamples=distribution.n_resamples,
    )


def bootstrap_pvalue(distribution: BootstrapDistribution, null_value: float = 0.0) -> float:
    r"""Rend la valeur p bilatérale de la statistique sous l'hypothèse nulle déclarée.

    **(1) Le problème.** Savoir si une statistique observée est compatible avec
    une valeur de référence, par exemple un ratio de Sharpe nul ou un rendement
    moyen nul, sans supposer la loi des données.

    **(2) L'intuition, et le recentrage qui décide de tout.** La distribution
    bootstrap est centrée sur la valeur OBSERVÉE, pas sur la valeur nulle. Elle
    ne décrit donc pas le monde sous l'hypothèse nulle. Retrancher la valeur
    observée à chaque réplique donne des écarts, et ces écarts sont ce que le
    hasard produit autour de n'importe quel centre. Comparer l'écart réellement
    observé à cette collection donne la valeur p.

    **(3) La formule.**

    .. math::

        p = \frac{1 + \#\left\{b : \left|\hat{\theta}^*_b - \hat{\theta}\right|
        \ge \left|\hat{\theta} - \theta_0\right|\right\}}{B + 1}

    **(4) Les variables.**

    - :math:`\hat{\theta}` la statistique observée ;
    - :math:`\theta_0` la valeur sous l'hypothèse nulle, ``null_value`` ;
    - :math:`\hat{\theta}^*_b` la réplique numéro :math:`b` ;
    - :math:`B` le nombre de répliques.

    **(5) Les hypothèses.** L'hypothèse nulle testée est l'égalité du paramètre à
    ``null_value``, contre l'alternative bilatérale. Le recentrage suppose que la
    forme de la distribution de l'écart ne dépend pas du paramètre, hypothèse dite
    de pivotalité approchée.

    **(6) La provenance.** Davison et Hinkley (1997), section 4.4. Le 1 ajouté au
    numérateur et au dénominateur vient de leur équation 4.10, et Phipson et
    Smyth (2010) montrent qu'il est nécessaire pour que le test tienne son
    niveau.

    **(7) Les limites.** La valeur p ne peut pas descendre sous
    :math:`1/(B+1)`. Avec 999 répliques, le plancher vaut 0,001, ce qui suffit
    pour un seuil à 5 % et pas pour un seuil à 0,1 %. Le recentrage suppose de
    plus que seule la position change sous l'hypothèse nulle, ce qui est faux si
    la variance de la statistique dépend du paramètre.

    **(8) Les alternatives.** Un rééchantillonnage sous contrainte, qui impose
    l'hypothèse nulle aux données avant de tirer, évite le recentrage. Le test de
    réalité de White (2000) le fait pour la comparaison de stratégies multiples.

    **(9) Pourquoi cette méthode.** Elle réutilise les répliques déjà calculées,
    donc elle ne coûte rien de plus qu'un intervalle de confiance, et elle
    s'applique à une statistique quelconque.

    **(10) Comment vérifier.** Sous l'hypothèse nulle vraie, la valeur p doit
    être approximativement uniforme sur zéro-un, donc inférieure à 5 % dans 5 %
    des répétitions. Sur des données simulées loin de la valeur nulle, elle doit
    tomber au plancher.

    Args:
        distribution: la distribution bootstrap, rendue par
            :func:`bootstrap_statistic`.
        null_value: la valeur du paramètre sous l'hypothèse nulle.

    Returns:
        La valeur p bilatérale, dans l'intervalle allant de 1/(B+1) à 1.

    Raises:
        ConfigError: si la valeur nulle n'est pas finie.
    """
    if not math.isfinite(null_value):
        raise ConfigError(f"null_value doit être fini, reçu {null_value}")
    deviations = np.abs(distribution.replicates - distribution.observed)
    observed_deviation = abs(distribution.observed - null_value)
    exceedances = int(np.count_nonzero(deviations >= observed_deviation))
    return (1.0 + exceedances) / (distribution.n_resamples + 1.0)

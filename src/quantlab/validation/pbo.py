r"""La probabilité de surapprentissage de backtest, et ce qu'elle juge vraiment.

**Le problème.** Un chercheur essaie mille variantes d'une même idée, garde la
meilleure, et publie son ratio de Sharpe. Ce nombre ne veut rien dire. Le
maximum de mille tirages de bruit est grand par construction, et il l'est
d'autant plus qu'on a tiré souvent. Les contrôles classiques ne le voient pas :
un échantillon de réserve unique donne un seul verdict, dont on ignore s'il
tient au hasard du découpage.

**La réponse du module.** La probabilité de surapprentissage de backtest, la
part des découpages où la configuration retenue dans l'échantillon finit sous
la médiane hors échantillon, mesure la qualité du PROCESSUS DE SÉLECTION. Elle
ne mesure pas la qualité d'une stratégie. C'est une distinction de fond, et
elle décide de la lecture de tous les chiffres qui suivent.

**Ce qu'une valeur signifie.** Une probabilité de 0,5 dit que choisir la
meilleure configuration dans l'échantillon ne classe pas mieux, dehors, qu'un
tirage au sort. La règle de décision proposée par les auteurs est de rejeter
un processus dont l'estimation dépasse 0,05, par analogie avec le seuil usuel
de Neyman-Pearson.

**Pourquoi une valeur haute condamne même un bon résultat.** La grandeur porte
sur la procédure, pas sur la configuration survivante. Une procédure qui
sélectionne au hasard rendra parfois une stratégie qui gagne. Ce gain ne se
reproduira pas, faute d'un mécanisme qui l'ait produit. Publier ce résultat
revient à publier le gagnant d'une loterie en le présentant comme un savoir.

**La méthode.** La validation croisée combinatoire symétrique découpe les
lignes en :math:`S` sous-ensembles, puis forme toutes les partitions en deux
moitiés de taille :math:`S/2`. Elle choisit la meilleure configuration dans la
moitié d'entraînement, et lit son RANG dans la moitié complémentaire. Le
nombre de partitions vaut :math:`\binom{S}{S/2}`, soit 12 870 pour le
:math:`S = 16` retenu par l'article.

**Deux écarts relevés dans le manuscrit.** Le premier est un nombre. Le
manuscrit déposé sur davidhbailey.com écrit « if :math:`S = 16`, we will form
12,780 combinations ». Le coefficient binomial vaut 12 870, vérifié par
``math.comb(16, 8)``. Les deux chiffres diffèrent d'une transposition, et
c'est 12 870 que ce module calcule.

Le second est une étiquette. L'étape c de l'algorithme 2.3 annonce noter « the
nth column of J (the testing set) », puis conclut la même phrase par « the IS
ranking of the N strategies ». L'étape d demande ensuite de refaire c sur
l'autre moitié pour obtenir les rangs hors échantillon. La parenthèse de
l'étape c contredit donc sa propre fin, et le module suit la lecture cohérente
avec les étapes d et e : la première note porte sur la moitié d'entraînement.
Statut : mesuré le 2026-09-01 sur le manuscrit de davidhbailey.com. Non
vérifié, la version publiée au *Journal of Computational Finance* n'ayant pas
été consultée.

**La symétrie, et ce qu'elle économise.** Chaque moitié sert une fois
d'entraînement et une fois de test, puisque le complément d'une moitié est
lui-même une des :math:`\binom{S}{S/2}` moitiés énumérées. Le module évalue
donc la performance une seule fois par moitié, ce qui divise par deux le
travail. Mesuré le 2026-09-01 sur cette machine : :math:`S = 16` sur vingt
configurations et 512 périodes demande 17,1 secondes de bout en bout. Le
compte est de 257 400 appels au ratio de Sharpe, soit 66 microsecondes par
appel. Le chiffre dépend de la machine et vaut comme ordre de grandeur.

**Provenance.** Bailey, D. H., Borwein, J. M., López de Prado, M. et Zhu, Q. J.
(2016), « The Probability of Backtest Overfitting », *Journal of Computational
Finance* 20(4), 39-69. La procédure suivie ici est l'algorithme 2.3, les
statistiques de la section 3, et les définitions 2.1 et 2.2.

**Limite mesurée sur la pente de dégradation.** L'article annonce une pente
négative « dans la plupart des cas pratiques », et la mesure lui donne raison
au sens strict de cette phrase. En moyenne, la pente sur les paires retenues
est négative sous le bruit pur comme sous une persistance forte. Sur une
matrice prise seule, elle peut être positive, et le balayage chiffré est dans
:class:`PerformanceDegradation`.

La cause est une identité de variances, décrite au même endroit, et non un
défaut d'implémentation. La pente qui sépare les deux régimes est celle de la
régression sur TOUTES les configurations, exposée sous le nom
``all_configurations_slope``.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial

import numpy as np
import pandas as pd
from scipy.integrate import cumulative_trapezoid
from scipy.stats import rankdata

from quantlab.analytics.ratios import sharpe_ratio
from quantlab.analytics.regression import factor_regression
from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.logging import get_logger
from quantlab.core.types import Frequency

log = get_logger(__name__)

__all__ = [
    "CSCVResult",
    "PBOResult",
    "PerformanceDegradation",
    "PerformanceFunction",
    "StochasticDominanceResult",
    "combinatorially_symmetric_cv",
    "logits",
    "number_of_partitions",
    "performance_degradation",
    "probability_of_backtest_overfitting",
    "sharpe_performance",
    "stochastic_dominance",
]

#: La fonction qui note un bloc de périodes. Elle reçoit un tableau dont les
#: lignes sont des périodes et les colonnes des configurations, et rend un
#: vecteur d'une performance par configuration, dans l'ordre des colonnes.
type PerformanceFunction = Callable[[pd.DataFrame], np.ndarray]

#: Le nombre de sous-ensembles retenu par l'article, qui donne 12 870 partitions.
DEFAULT_N_SPLITS = 16

#: Le nombre minimal de lignes par sous-ensemble. Deux est le plancher
#: arithmétique : un écart type d'échantillon n'est pas défini en deçà.
DEFAULT_MIN_ROWS_PER_SPLIT = 2

#: Le nombre minimal de configurations. Un rang relatif n'a pas de sens sur une
#: seule colonne, la sélection étant alors sans objet.
MIN_CONFIGURATIONS = 2

#: La tolérance numérique des comparaisons de fonctions de répartition. Elle
#: absorbe l'erreur d'arrondi de l'intégration, pas une différence réelle.
DEFAULT_DOMINANCE_TOLERANCE = 1e-12


@dataclass(frozen=True, slots=True)
class CSCVResult:
    """Le produit brut de la validation croisée combinatoire symétrique.

    Attributes:
        n_splits: le nombre :math:`S` de sous-ensembles de lignes.
        n_partitions: le nombre de partitions, égal à :math:`\\binom{S}{S/2}`.
        n_configurations: le nombre :math:`N` de configurations comparées.
        n_observations: le nombre de lignes réellement utilisées.
        n_dropped_rows: le nombre de lignes de queue écartées, la division de
            :math:`T` par :math:`S` devant tomber juste.
        rows_per_split: le nombre de lignes par sous-ensemble.
        trials: une ligne par partition. Les colonnes portent la configuration
            retenue, sa performance dans l'échantillon, sa performance hors
            échantillon, son rang hors échantillon, son rang relatif et son
            logit.
        in_sample_performance: la performance de chaque configuration sur la
            moitié d'entraînement, une ligne par partition.
        out_of_sample_performance: la même chose sur la moitié complémentaire.
    """

    n_splits: int
    n_partitions: int
    n_configurations: int
    n_observations: int
    n_dropped_rows: int
    rows_per_split: int
    trials: pd.DataFrame
    in_sample_performance: pd.DataFrame
    out_of_sample_performance: pd.DataFrame


@dataclass(frozen=True, slots=True)
class PBOResult:
    """La probabilité de surapprentissage et ce qui permet de la relire.

    Attributes:
        pbo: la part des partitions dont le logit est négatif ou nul, soit la
            part où la configuration retenue tombe sous la médiane dehors.
        n_partitions: le nombre de partitions sur lesquelles la part est
            calculée, donc le dénominateur.
        logits: la série des logits, indexée par numéro de partition. Sa forme
            se lit en histogramme, comme la figure 2 de l'article.
        median_rank: le rang hors échantillon médian de la configuration
            retenue, entre 1 pour la pire et :math:`N` pour la meilleure.
        median_relative_rank: le même rang divisé par :math:`N + 1`, donc entre
            0 et 1. La valeur neutre est 0,5.
    """

    pbo: float
    n_partitions: int
    logits: pd.Series
    median_rank: float
    median_relative_rank: float


@dataclass(frozen=True, slots=True)
class PerformanceDegradation:
    r"""La dégradation hors échantillon, mesurée par deux pentes et une perte.

    **Ce que mesure ``slope``.** C'est la pente de la régression de l'article,
    celle des paires retenues :math:`(R_{n^*}^c, \bar{R}_{n^*}^c)`. Une pente
    négative dit que mieux faire dans l'échantillon annonce faire pire dehors.

    **Pourquoi cette pente ne sépare pas les deux régimes.** Les deux moitiés
    partitionnent une matrice fixe. Pour une performance additive, la
    performance de la moitié d'entraînement et celle de son complément somment
    à une constante propre à la configuration. En notant
    :math:`u = (x + y) / 2` et :math:`\varepsilon = (x - y) / 2`, l'identité
    :math:`\operatorname{Cov}(x, y) = \operatorname{Var}(u) -
    \operatorname{Var}(\varepsilon)` est algébrique et ne suppose aucun modèle.

    **La conséquence.** La pente est positive seulement si la dispersion de la
    qualité PLEIN ÉCHANTILLON des configurations retenues dépasse celle du
    bruit de demi-échantillon. Or la sélection par le maximum concentre le
    choix sur les meilleures configurations, ce qui écrase le premier terme et
    gonfle le second. Elle vaut exactement moins un quand une seule
    configuration gagne toujours, ce qu'un test vérifie.

    **Ce que la mesure dit, et ce qu'elle ne dit pas.** Balayage du 2026-09-01,
    :math:`S = 6` sur 240 périodes, douze régimes de quarante tirages croisant
    trois nombres de configurations, 5, 12 et 30, et quatre rapports de
    persistance au bruit, de 0 à 8.

    La pente MOYENNE est négative dans les douze régimes, entre -0,51 et -0,95.
    Sur un tableau PRIS UN À UN, elle est positive jusqu'à 25 % des tirages
    selon le régime, et elle monte à +1,05. Le signe lu sur une seule matrice
    n'est donc pas un verdict.

    **Le seuil de moins un.** La même décomposition donne
    :math:`\beta + 1 = 2\operatorname{Cov}(u, x) / \operatorname{Var}(x)`,
    donc la pente descend sous moins un dès que la sélection rend cette
    covariance négative. Le cas se produit sous le bruit pur, une configuration
    médiocre n'étant retenue que les fois où son bruit d'échantillon est haut.
    Mesuré le 2026-09-01 sur 120 tirages nuls, la plus basse des pentes vaut
    -1,67.

    **Ce qui sépare les deux régimes.** La pente ``all_configurations_slope``,
    calculée sur toutes les paires configuration par partition, vaut zéro sous
    l'hypothèse nulle et tend vers un quand la qualité persiste. Cette pente
    n'est pas dans l'article, et le module la déclare comme un ajout.

    **Ce que cette pente est vraiment.** C'est la corrélation de Pearson entre
    la performance dans l'échantillon et la performance hors échantillon, prise
    sur toutes les paires. La raison tient à la symétrie de la procédure.
    L'ensemble des performances hors échantillon est une permutation de
    l'ensemble des performances dans l'échantillon. Les deux colonnes ont donc
    la même variance, et la pente se confond avec la corrélation.

    **Trois conséquences.** La pente groupée est bornée entre moins un et un,
    ce que la pente de l'article n'est pas. Elle ne dépend pas du sens de la
    régression, donc inverser les deux moitiés la laisse inchangée. Et sa
    valeur se vérifie contre ``scipy.stats.pearsonr``, qui ne partage aucune
    ligne avec ce module. Statut : mesuré le 2026-09-01, écart de 2e-16.

    Attributes:
        slope: la pente de l'article, sur les seules paires retenues.
        intercept: la constante de cette même régression.
        r_squared: la part de variance expliquée par cette même régression.
        t_stat: le t de Student de la pente, matrice de covariance non robuste.
        n_pairs: le nombre de paires, égal au nombre de partitions.
        all_configurations_slope: la pente sur toutes les configurations.
        probability_of_loss: la part des partitions où la configuration retenue
            perd de l'argent hors échantillon, soit
            :math:`\operatorname{Prob}[\bar{R}_{n^*}^c < 0]`.
    """

    slope: float
    intercept: float
    r_squared: float
    t_stat: float
    n_pairs: int
    all_configurations_slope: float
    probability_of_loss: float


@dataclass(frozen=True, slots=True)
class StochasticDominanceResult:
    """La comparaison de la sélection au tirage au sort, ordre un et ordre deux.

    Attributes:
        grid: les abscisses où les deux fonctions de répartition sont évaluées,
            soit toutes les valeurs observées, triées.
        selected_cdf: la répartition empirique de la performance hors
            échantillon de la configuration retenue.
        benchmark_cdf: la répartition empirique de la MOYENNE hors échantillon
            des :math:`N` configurations, une valeur par partition. C'est le
            repère écrit dans la formule de l'article.
        second_order_curve: la courbe :math:`SD_2`, intégrale de la différence
            des deux répartitions.
        first_order: vrai si la sélection domine au premier ordre.
        second_order: vrai si elle domine au second ordre.
        max_cdf_gap: le plus grand écart en faveur de la sélection, en
            probabilité, borné en bas à zéro. La borne rend le champ lisible
            comme un gain, au prix de ne pas distinguer une sélection neutre
            d'une sélection partout perdante. Le signe se lit alors sur
            ``first_order`` et sur ``second_order_curve``.
        n_partitions: le nombre de points de chaque échantillon.

    Note:
        Le repère de l'article est une moyenne, pas un tirage. La prose de la
        section 3.3 parle de « randomly choosing one model configuration among
        the N alternatives », mais la formule écrit
        :math:`\\mathrm{Mean}(\\bar R)`. Les deux ne coïncident pas.

        La moyenne des :math:`N` configurations d'une partition est
        l'ESPÉRANCE d'un tirage au sort, et non la LOI de son résultat. Elle a
        la même moyenne et une variance divisée par :math:`N` environ. Ce
        repère est donc plus dur à battre au second ordre qu'un tirage réel,
        puisqu'un décideur averse au risque préfère la moyenne à la loterie.

        Le module suit la formule, comme l'exige la réplication. Un repère par
        mise en commun des :math:`N \\times \\#(C_S)` performances hors
        échantillon donnerait la loi du tirage au sort, et un verdict plus
        indulgent. Il n'est pas calculé ici.
    """

    grid: np.ndarray
    selected_cdf: np.ndarray
    benchmark_cdf: np.ndarray
    second_order_curve: np.ndarray
    first_order: bool
    second_order: bool
    max_cdf_gap: float
    n_partitions: int


def number_of_partitions(n_splits: int) -> int:
    r"""Rend le nombre de partitions de la validation croisée, et garde la parité.

    **Le problème.** La méthode exige deux moitiés de même taille. Un nombre
    impair de sous-ensembles ne se partage pas en deux parts égales, et la
    procédure n'a alors pas de définition.

    **L'intuition.** Choisir la moitié d'entraînement revient à choisir
    :math:`S/2` sous-ensembles parmi :math:`S`, sans ordre. C'est un
    coefficient binomial.

    .. math::

        \#(C_S) = \binom{S}{S/2}

    Args:
        n_splits: le nombre :math:`S` de sous-ensembles de lignes. Il doit être
            pair et valoir au moins deux.

    Returns:
        Le nombre de partitions.

    Raises:
        ConfigError: si ``n_splits`` est impair, ou inférieur à deux.

    Note:
        Valeurs de contrôle, calculées à la main :
        :math:`\binom{4}{2} = 6`, :math:`\binom{6}{3} = 20`,
        :math:`\binom{8}{4} = 70`, :math:`\binom{16}{8} = 12\,870`.
        Le manuscrit de l'article imprime 12 780 pour ce dernier cas, ce qui
        est une transposition de chiffres. Statut : mesuré.
    """
    if n_splits < 2:
        raise ConfigError(f"n_splits doit valoir au moins 2, reçu {n_splits}")
    if n_splits % 2 != 0:
        raise ConfigError(
            f"n_splits doit être PAIR pour former deux moitiés de taille égale, reçu {n_splits}"
        )
    return math.comb(n_splits, n_splits // 2)


def logits(ranks: np.ndarray | pd.Series | list[float], n_configurations: int | None = None) -> np.ndarray:
    r"""Rend le logit des rangs relatifs, la transformation employée par l'article.

    **Le problème.** Un rang hors échantillon est borné entre 1 et :math:`N`.
    Comparer deux valeurs bornées est malcommode, et la borne écrase les
    différences aux extrémités.

    **L'intuition.** Le rang relatif :math:`\bar\omega = \bar r / (N + 1)` vit
    dans l'intervalle ouvert de 0 à 1. Son logit l'étale sur la droite réelle
    entière, et il place le point neutre, la médiane, exactement à zéro.

    .. math::

        \bar\omega_c = \frac{\bar r^{\,c}_{n^*}}{N + 1}
        \qquad
        \lambda_c = \ln\!\left(\frac{\bar\omega_c}{1 - \bar\omega_c}\right)

    Où :math:`\bar r^{\,c}_{n^*}` est le rang, dans la moitié de test de la
    partition :math:`c`, de la configuration :math:`n^*` choisie dans la moitié
    d'entraînement. Le rang 1 est celui de la plus mauvaise, le rang :math:`N`
    celui de la meilleure. Le diviseur :math:`N + 1` garde le rang relatif
    strictement entre 0 et 1, donc le logit fini.

    Args:
        ranks: soit des rangs absolus entre 1 et ``n_configurations``, soit des
            rangs déjà relatifs, strictement entre 0 et 1.
        n_configurations: le nombre :math:`N` de configurations. Passé, les
            rangs sont lus comme absolus et divisés par :math:`N + 1`. Laissé à
            ``None``, ils sont lus comme déjà relatifs.

    Returns:
        Les logits, dans l'ordre des rangs reçus.

    Raises:
        ConfigError: si l'entrée est vide, si ``n_configurations`` est
            inférieur à deux, ou si les valeurs sortent de leur domaine.

    Note:
        Hypothèses. Les rangs viennent d'une même population de :math:`N`
        configurations, et les ex aequo ont reçu un rang moyen. Limite. Le
        logit est symétrique, donc il traite un rang 1 sur 20 et un rang 20 sur
        20 comme deux écarts de même taille en sens opposés. Alternative. Le
        rang relatif brut se lit tout aussi bien, mais sa distribution est
        uniforme sous l'hypothèse nulle et non centrée, ce qui rend la lecture
        graphique moins directe. Vérification. Un rang médian doit rendre un
        logit nul, et le rang le plus haut un logit égal à
        :math:`\ln N` en valeur absolue à l'arrondi près.
    """
    values = np.asarray(ranks, dtype=float)
    if values.size == 0:
        raise ConfigError("ranks est vide : aucun logit à calculer")
    if not np.isfinite(values).all():
        raise DataQualityError("ranks porte une valeur non finie")
    if n_configurations is None:
        relative = values
        if not np.all((relative > 0.0) & (relative < 1.0)):
            raise ConfigError(
                "sans n_configurations, ranks doit porter des rangs relatifs strictement entre 0 et 1"
            )
    else:
        if n_configurations < MIN_CONFIGURATIONS:
            raise ConfigError(f"n_configurations doit valoir au moins 2, reçu {n_configurations}")
        if not np.all((values >= 1.0) & (values <= float(n_configurations))):
            raise ConfigError(f"les rangs absolus doivent tenir entre 1 et {n_configurations}")
        relative = values / (n_configurations + 1.0)
    return np.log(relative / (1.0 - relative))


def sharpe_performance(
    block: pd.DataFrame,
    *,
    frequency: Frequency = Frequency.DAILY,
    annualize: bool = True,
    ddof: int = 1,
) -> np.ndarray:
    """Note chaque colonne d'un bloc par son ratio de Sharpe.

    C'est la fonction de performance par défaut de la validation croisée, et
    c'est celle que l'article emploie dans ses exemples. Le calcul est délégué
    à :func:`quantlab.analytics.ratios.sharpe_ratio`, seule implémentation du
    ratio dans le laboratoire.

    Args:
        block: un tableau dont les lignes sont des périodes et les colonnes des
            configurations.
        frequency: la fréquence d'observation déclarée des lignes.
        annualize: vrai pour multiplier par la racine du nombre de périodes par
            an. Le choix ne change aucun rang, l'annualisation étant une
            multiplication par une constante positive.
        ddof: le degré de liberté retiré à l'écart type.

    Returns:
        Un vecteur d'une performance par colonne, dans l'ordre des colonnes.
    """
    return np.array(
        [
            sharpe_ratio(block[column], frequency=frequency, annualize=annualize, ddof=ddof)
            for column in block.columns
        ],
        dtype=float,
    )


def _validate_matrix(performance_matrix: pd.DataFrame) -> pd.DataFrame:
    """Vérifie la forme du tableau d'entrée avant tout calcul."""
    if not isinstance(performance_matrix, pd.DataFrame):
        raise ConfigError("performance_matrix doit être un pandas.DataFrame")
    if performance_matrix.columns.has_duplicates:
        raise ConfigError("les noms de configurations doivent être uniques")
    n_rows, n_columns = performance_matrix.shape
    if n_columns < MIN_CONFIGURATIONS:
        raise ConfigError(
            f"il faut au moins {MIN_CONFIGURATIONS} configurations pour classer, reçu {n_columns}"
        )
    frame = performance_matrix.astype(float)
    if not np.isfinite(frame.to_numpy()).all():
        raise DataQualityError("performance_matrix porte une valeur manquante ou infinie")
    if n_rows < 1:
        raise InsufficientDataError("performance_matrix ne porte aucune ligne")
    return frame


def combinatorially_symmetric_cv(
    performance_matrix: pd.DataFrame,
    n_splits: int = DEFAULT_N_SPLITS,
    *,
    performance: PerformanceFunction | None = None,
    frequency: Frequency = Frequency.DAILY,
    min_rows_per_split: int = DEFAULT_MIN_ROWS_PER_SPLIT,
) -> CSCVResult:
    r"""Applique la validation croisée combinatoire symétrique de l'article.

    **Le problème.** Un échantillon de réserve unique donne un seul verdict
    hors échantillon, et ce verdict dépend de l'endroit où l'on a coupé.
    Couper ailleurs donne un autre chiffre, sans qu'on sache lequel croire.

    **L'intuition.** Plutôt qu'une coupure, on les fait toutes. Les lignes sont
    réparties en :math:`S` blocs, et chaque choix de :math:`S/2` blocs forme
    une moitié d'entraînement dont le complément sert de moitié de test. La
    procédure est symétrique : chaque moitié joue les deux rôles, une fois
    chacun.

    .. math::

        M \in \mathbb{R}^{T \times N}
        \quad\longrightarrow\quad
        (M_1, \dots, M_S), \qquad
        \#(C_S) = \binom{S}{S/2}

    .. math::

        n^* = \arg\max_n R^c_n,
        \qquad
        \bar\omega_c = \frac{\bar r^{\,c}_{n^*}}{N + 1},
        \qquad
        \lambda_c = \ln\!\left(\frac{\bar\omega_c}{1 - \bar\omega_c}\right)

    Où :math:`M` est le tableau d'entrée, :math:`T` le nombre de périodes,
    :math:`N` le nombre de configurations, :math:`R^c_n` la performance de la
    configuration :math:`n` sur la moitié d'entraînement de la partition
    :math:`c`, :math:`\bar r^{\,c}` le rang des performances sur la moitié de
    test, et :math:`\lambda_c` le logit du rang relatif.

    Args:
        performance_matrix: les périodes en lignes, les configurations en
            colonnes. Les valeurs sont des gains et pertes par période, sur
            lesquelles la fonction de performance sait travailler.
        n_splits: le nombre :math:`S` de blocs. Il doit être pair.
        performance: la fonction qui note un bloc. Par défaut le ratio de
            Sharpe à la fréquence déclarée.
        frequency: la fréquence d'observation, transmise à la fonction par
            défaut. Elle est sans effet si ``performance`` est fournie.
        min_rows_per_split: le nombre minimal de lignes par bloc.

    Returns:
        Le produit brut de la procédure, dont la lecture est décrite par
        :class:`CSCVResult`.

    Raises:
        ConfigError: si ``n_splits`` est impair, si le tableau porte moins de
            deux colonnes, ou si la fonction de performance rend une forme
            inattendue.
        DataQualityError: si le tableau ou une performance porte une valeur non
            finie.
        InsufficientDataError: si un bloc porterait moins de
            ``min_rows_per_split`` lignes.

    Note:
        Hypothèses de l'article. Le tableau est plein et synchrone, une ligne
        valant la même période pour toutes les colonnes. La mesure de
        performance doit garder un sens sur un demi-échantillon.

        Ce que fait le module quand :math:`T` n'est pas divisible par
        :math:`S`. Les lignes de queue sont écartées, et leur nombre est
        journalisé puis rendu dans ``n_dropped_rows``. La méthode exige des
        blocs de dimensions égales.

        Ex aequo. Le choix de la meilleure configuration prend la première
        colonne en cas d'égalité stricte, et les rangs ex aequo reçoivent le
        rang moyen. Avec une mesure continue, ces cas sont de probabilité
        nulle.

        Ordre des lignes. Les blocs sont recollés dans leur ordre d'origine,
        comme le demande l'algorithme. L'ordre est sans effet sur le ratio de
        Sharpe, mais il compte pour une mesure de perte maximale.

        Vérification. Le nombre de partitions doit valoir
        :math:`\binom{S}{S/2}`, et la performance hors échantillon d'une
        partition doit être exactement la performance dans l'échantillon de la
        partition complémentaire.
    """
    frame = _validate_matrix(performance_matrix)
    n_partitions = number_of_partitions(n_splits)
    n_rows, n_configurations = frame.shape
    rows_per_split = n_rows // n_splits
    if rows_per_split < min_rows_per_split:
        raise InsufficientDataError(
            f"{n_rows} lignes découpées en {n_splits} blocs donnent {rows_per_split} lignes par bloc, "
            f"moins que le minimum de {min_rows_per_split}"
        )
    n_used = rows_per_split * n_splits
    n_dropped = n_rows - n_used
    if n_dropped:
        log.warning(
            "lignes de queue écartées pour égaliser les blocs",
            extra={"n_dropped_rows": n_dropped, "n_splits": n_splits},
        )
    trimmed = frame.iloc[:n_used]
    score = performance if performance is not None else partial(sharpe_performance, frequency=frequency)

    subsets = list(itertools.combinations(range(n_splits), n_splits // 2))
    position = {subset: index for index, subset in enumerate(subsets)}
    scores = np.empty((n_partitions, n_configurations), dtype=float)
    for index, subset in enumerate(subsets):
        rows = np.concatenate(
            [np.arange(block * rows_per_split, (block + 1) * rows_per_split) for block in subset]
        )
        values = np.asarray(score(trimmed.iloc[rows]), dtype=float)
        if values.shape != (n_configurations,):
            raise ConfigError(
                f"la fonction de performance doit rendre {n_configurations} valeurs, "
                f"forme reçue {values.shape}"
            )
        scores[index] = values
    if not np.isfinite(scores).all():
        raise DataQualityError("la fonction de performance a rendu une valeur non finie")

    all_blocks = set(range(n_splits))
    complement = np.array([position[tuple(sorted(all_blocks - set(s)))] for s in subsets], dtype=int)
    in_sample = scores
    out_of_sample = scores[complement]

    selected = in_sample.argmax(axis=1)
    ranks = rankdata(out_of_sample, axis=1)
    partitions = np.arange(n_partitions)
    out_of_sample_rank = ranks[partitions, selected]
    relative_rank = out_of_sample_rank / (n_configurations + 1.0)

    index = pd.RangeIndex(n_partitions, name="partition")
    columns = frame.columns
    trials = pd.DataFrame(
        {
            "selected": pd.Series(columns[selected], index=index),
            "in_sample_performance": in_sample[partitions, selected],
            "out_of_sample_performance": out_of_sample[partitions, selected],
            "out_of_sample_rank": out_of_sample_rank,
            "relative_rank": relative_rank,
            "logit": logits(relative_rank),
        },
        index=index,
    )
    return CSCVResult(
        n_splits=n_splits,
        n_partitions=n_partitions,
        n_configurations=n_configurations,
        n_observations=n_used,
        n_dropped_rows=n_dropped,
        rows_per_split=rows_per_split,
        trials=trials,
        in_sample_performance=pd.DataFrame(in_sample, index=index, columns=columns),
        out_of_sample_performance=pd.DataFrame(out_of_sample, index=index, columns=columns),
    )


def _ensure_result(
    performance_matrix: pd.DataFrame | CSCVResult,
    n_splits: int,
    *,
    performance: PerformanceFunction | None,
    frequency: Frequency,
    min_rows_per_split: int,
) -> CSCVResult:
    """Rend un résultat de validation croisée, en le calculant s'il le faut."""
    if isinstance(performance_matrix, CSCVResult):
        return performance_matrix
    return combinatorially_symmetric_cv(
        performance_matrix,
        n_splits,
        performance=performance,
        frequency=frequency,
        min_rows_per_split=min_rows_per_split,
    )


def probability_of_backtest_overfitting(
    performance_matrix: pd.DataFrame | CSCVResult,
    n_splits: int = DEFAULT_N_SPLITS,
    *,
    performance: PerformanceFunction | None = None,
    frequency: Frequency = Frequency.DAILY,
    min_rows_per_split: int = DEFAULT_MIN_ROWS_PER_SPLIT,
) -> PBOResult:
    r"""Rend la probabilité de surapprentissage de backtest.

    **Le problème.** Choisir la meilleure de mille configurations garantit un
    beau chiffre dans l'échantillon. Rien ne dit que ce choix vaut mieux qu'un
    tirage au sort une fois dehors.

    **L'intuition.** On répète le choix sur toutes les partitions, et on compte
    la part des fois où la configuration retenue finit dans la moitié basse du
    classement hors échantillon. Une procédure sans valeur y tombe une fois sur
    deux.

    .. math::

        \phi = \int_{-\infty}^{0} f(\lambda)\,d\lambda
        = \operatorname{Prob}\!\left[\lambda_c \le 0\right]
        = \operatorname{Prob}\!\left[\bar r^{\,c}_{n^*} \le \frac{N+1}{2}\right]

    Où :math:`f` est la fréquence relative des logits sur l'ensemble des
    partitions, :math:`\lambda_c` le logit de la partition :math:`c`,
    :math:`\bar r^{\,c}_{n^*}` le rang hors échantillon de la configuration
    retenue, et :math:`N` le nombre de configurations.

    Args:
        performance_matrix: le tableau des périodes par configurations, ou un
            :class:`CSCVResult` déjà calculé. Dans ce second cas, les autres
            arguments sont sans effet.
        n_splits: le nombre :math:`S` de blocs, pair.
        performance: la fonction qui note un bloc, ratio de Sharpe par défaut.
        frequency: la fréquence transmise à la fonction par défaut.
        min_rows_per_split: le nombre minimal de lignes par bloc.

    Returns:
        La probabilité et de quoi la relire, décrites par :class:`PBOResult`.

    Note:
        Ce que la grandeur mesure. Elle juge le PROCESSUS DE SÉLECTION, pas la
        stratégie retenue. Deux processus qui rendent la même stratégie peuvent
        avoir des probabilités opposées, et c'est le processus qui se
        reproduira, pas le tirage.

        Ce qu'une valeur vaut. Zéro dit que la sélection tient dehors. La
        valeur 0,5 dit qu'elle ne vaut pas mieux qu'un tirage au sort. Un
        dit qu'elle choisit systématiquement ce qui échouera. Les auteurs
        proposent de rejeter au-delà de 0,05.

        Pourquoi une valeur haute condamne même un bon résultat. La stratégie
        survivante peut gagner par chance. Une procédure qui ne trie pas ne
        reproduira pas ce gain, et le chiffre publié n'apprend donc rien sur
        l'avenir.

        Convention d'égalité. L'intégrale de l'article est fermée en zéro, donc
        un logit exactement nul compte comme un surapprentissage. Le module
        applique cette convention, et un test la verrouille sur deux colonnes
        identiques, où les six logits valent zéro et la probabilité vaut un.

        Deux chemins mènent au logit nul, et non un seul. Le premier tient à la
        parité : quand :math:`N` est impair, le rang entier :math:`(N + 1) / 2`
        existe, et il pousse la probabilité vers le haut d'environ
        :math:`1 / (2N)` sous l'hypothèse nulle. Le second tient aux ex aequo :
        deux configurations à égalité de part et d'autre de la médiane
        reçoivent le rang moyen :math:`(N + 1) / 2`, quelle que soit la parité
        de :math:`N`. Avec une mesure continue, ce second chemin est de
        probabilité nulle.

        Limite. La probabilité dépend de la grille de configurations soumise.
        Une grille de mille variantes d'une même idée et une grille de mille
        idées distinctes ne se comparent pas.

        Vérification. Sur un tableau de bruit pur où aucune configuration n'est
        meilleure, la valeur doit tourner autour de 0,5. Sur un tableau où une
        configuration domine partout, elle doit valoir zéro.
    """
    result = _ensure_result(
        performance_matrix,
        n_splits,
        performance=performance,
        frequency=frequency,
        min_rows_per_split=min_rows_per_split,
    )
    series = result.trials["logit"]
    return PBOResult(
        pbo=float((series <= 0.0).mean()),
        n_partitions=result.n_partitions,
        logits=series,
        median_rank=float(result.trials["out_of_sample_rank"].median()),
        median_relative_rank=float(result.trials["relative_rank"].median()),
    )


def performance_degradation(
    performance_matrix: pd.DataFrame | CSCVResult,
    n_splits: int = DEFAULT_N_SPLITS,
    *,
    performance: PerformanceFunction | None = None,
    frequency: Frequency = Frequency.DAILY,
    min_rows_per_split: int = DEFAULT_MIN_ROWS_PER_SPLIT,
) -> PerformanceDegradation:
    r"""Régresse la performance hors échantillon sur celle dans l'échantillon.

    **Le problème.** La probabilité de surapprentissage compte des rangs, donc
    elle ignore les montants. Une procédure peut classer correctement et perdre
    de l'argent quand même.

    **L'intuition.** On garde les paires de performances de la configuration
    retenue, dans l'échantillon et dehors, et on les régresse. La pente dit ce
    qu'un point de performance gagné dans l'échantillon annonce dehors.

    .. math::

        \bar{R}^{\,c}_{n^*} = \alpha + \beta\,R^c_{n^*} + \epsilon_c

    Où :math:`R^c_{n^*}` est la performance de la configuration retenue sur la
    moitié d'entraînement de la partition :math:`c`, et
    :math:`\bar{R}^{\,c}_{n^*}` sa performance sur la moitié complémentaire.
    Une pente :math:`\beta` négative est le signe d'un surapprentissage sévère.

    Args:
        performance_matrix: le tableau des périodes par configurations, ou un
            :class:`CSCVResult` déjà calculé.
        n_splits: le nombre :math:`S` de blocs, pair.
        performance: la fonction qui note un bloc, ratio de Sharpe par défaut.
        frequency: la fréquence transmise à la fonction par défaut.
        min_rows_per_split: le nombre minimal de lignes par bloc.

    Returns:
        Les deux pentes et la probabilité de perte, décrites par
        :class:`PerformanceDegradation`.

    Note:
        Provenance. Section 3.2 de l'article, qui associe la dégradation et la
        probabilité de perte dans la même figure.

        Hypothèses. La régression est un ajustement par moindres carrés
        ordinaires sur des points qui ne sont pas indépendants, les partitions
        se recouvrant par construction. Son t de Student est donc indicatif, et
        le module le rend sans matrice de covariance robuste.

        Limite mesurée. Le signe de ``slope`` ne sépare pas la persistance du
        bruit. Le raisonnement est dans :class:`PerformanceDegradation`, et il
        repose sur une identité de variances, non sur une simulation.

        Alternative. La pente ``all_configurations_slope``, calculée sur toutes
        les paires, vaut zéro sous l'hypothèse nulle et monte vers un quand la
        qualité des configurations persiste.

        Vérification. Quand la mesure est la moyenne arithmétique et qu'une
        seule configuration gagne toujours, l'identité
        :math:`y = 2m - x` impose une pente de moins un exactement.
    """
    result = _ensure_result(
        performance_matrix,
        n_splits,
        performance=performance,
        frequency=frequency,
        min_rows_per_split=min_rows_per_split,
    )
    in_sample = result.trials["in_sample_performance"].rename("in_sample")
    out_of_sample = result.trials["out_of_sample_performance"].rename("out_of_sample")
    fit = factor_regression(
        out_of_sample,
        in_sample,
        cov_type="nonrobust",
        annualize_alpha=False,
    )
    pooled_index = pd.RangeIndex(result.n_partitions * result.n_configurations)
    pooled_fit = factor_regression(
        pd.Series(result.out_of_sample_performance.to_numpy().ravel(), index=pooled_index),
        pd.Series(result.in_sample_performance.to_numpy().ravel(), index=pooled_index, name="in_sample"),
        cov_type="nonrobust",
        annualize_alpha=False,
    )
    return PerformanceDegradation(
        slope=float(fit.betas.iloc[0]),
        intercept=float(fit.alpha),
        r_squared=float(fit.r_squared),
        t_stat=float(fit.beta_tstats.iloc[0]),
        n_pairs=int(fit.n_obs),
        all_configurations_slope=float(pooled_fit.betas.iloc[0]),
        probability_of_loss=float((out_of_sample < 0.0).mean()),
    )


def _empirical_cdf(sample: np.ndarray, grid: np.ndarray) -> np.ndarray:
    """Rend la répartition empirique d'un échantillon, évaluée sur une grille."""
    ordered = np.sort(sample)
    return np.searchsorted(ordered, grid, side="right") / float(ordered.size)


def stochastic_dominance(
    performance_matrix: pd.DataFrame | CSCVResult,
    n_splits: int = DEFAULT_N_SPLITS,
    *,
    performance: PerformanceFunction | None = None,
    frequency: Frequency = Frequency.DAILY,
    min_rows_per_split: int = DEFAULT_MIN_ROWS_PER_SPLIT,
    tolerance: float = DEFAULT_DOMINANCE_TOLERANCE,
) -> StochasticDominanceResult:
    r"""Compare la sélection au tirage au sort, au premier et au second ordre.

    **Le problème.** La probabilité de surapprentissage résume tout en un
    nombre, donc elle cache la forme des deux distributions. Deux procédures de
    même probabilité peuvent offrir des risques très différents.

    **L'intuition.** On compare la distribution de ce que rapporte la
    configuration retenue à celle de la MOYENNE des :math:`N` configurations de
    la même partition. La dominance au premier ordre dit que la première est
    préférable pour tout décideur qui préfère plus à moins. Celle au second
    ordre le dit pour tout décideur averse au risque.

    **Ce que le repère est, et n'est pas.** La moyenne des :math:`N`
    configurations est l'espérance d'un tirage au sort, et non la loi de son
    résultat. Elle est donc plus dure à battre au second ordre. L'écart entre
    la prose de l'article et sa formule est traité dans
    :class:`StochasticDominanceResult`.

    .. math::

        \operatorname{Prob}[\bar R_{n^*} \ge x]
        \ \ge\ \operatorname{Prob}[\mathrm{Mean}(\bar R) \ge x]
        \quad \forall x

    .. math::

        SD_2[x] = \int_{-\infty}^{x}
        \bigl(\operatorname{Prob}[\mathrm{Mean}(\bar R) \le u]
        - \operatorname{Prob}[\bar R_{n^*} \le u]\bigr)\,du \ \ge\ 0
        \quad \forall x

    Où :math:`\bar R_{n^*}` est la performance hors échantillon de la
    configuration retenue, une valeur par partition, et
    :math:`\mathrm{Mean}(\bar R)` la moyenne hors échantillon des :math:`N`
    configurations de la même partition, qui est l'espérance d'un tirage au
    sort.

    Args:
        performance_matrix: le tableau des périodes par configurations, ou un
            :class:`CSCVResult` déjà calculé.
        n_splits: le nombre :math:`S` de blocs, pair.
        performance: la fonction qui note un bloc, ratio de Sharpe par défaut.
        frequency: la fréquence transmise à la fonction par défaut.
        min_rows_per_split: le nombre minimal de lignes par bloc.
        tolerance: la marge numérique des comparaisons, en probabilité pour le
            premier ordre et en aire pour le second.

    Returns:
        Les deux verdicts et les courbes qui les portent, décrits par
        :class:`StochasticDominanceResult`.

    Note:
        Provenance. Section 3.3 de l'article, qui renvoie à Hadar et Russell
        (1969) pour la théorie de la dominance stochastique.

        Hypothèses. Les répartitions sont empiriques, donc en escalier, et
        l'intégrale du second ordre est approchée par la méthode des trapèzes
        sur la grille des valeurs observées.

        Limite. Les deux verdicts sont des constats d'échantillon et non des
        tests. Un échantillon fini peut montrer une dominance qui n'existe pas
        dans la population, et la procédure ne rend aucune valeur p.

        Alternative. Un test de Kolmogorov-Smirnov unilatéral donnerait un
        niveau de confiance, au prix d'une hypothèse d'indépendance que les
        partitions ne respectent pas.

        Vérification. La dominance au premier ordre entraîne celle au second,
        donc un cas où le premier verdict est vrai et le second faux signale un
        défaut d'implémentation.
    """
    result = _ensure_result(
        performance_matrix,
        n_splits,
        performance=performance,
        frequency=frequency,
        min_rows_per_split=min_rows_per_split,
    )
    selected = result.trials["out_of_sample_performance"].to_numpy()
    benchmark = result.out_of_sample_performance.to_numpy().mean(axis=1)
    grid = np.unique(np.concatenate([selected, benchmark]))
    selected_cdf = _empirical_cdf(selected, grid)
    benchmark_cdf = _empirical_cdf(benchmark, grid)
    gap = benchmark_cdf - selected_cdf
    first_order = bool(np.all(gap >= -tolerance) and np.any(gap > tolerance))
    if grid.size < 2:
        second_order_curve = np.zeros_like(grid)
    else:
        second_order_curve = cumulative_trapezoid(gap, grid, initial=0.0)
    second_order = bool(np.all(second_order_curve >= -tolerance) and np.any(second_order_curve > tolerance))
    return StochasticDominanceResult(
        grid=grid,
        selected_cdf=selected_cdf,
        benchmark_cdf=benchmark_cdf,
        second_order_curve=second_order_curve,
        first_order=first_order,
        second_order=second_order,
        max_cdf_gap=float(gap.max(initial=0.0)),
        n_partitions=result.n_partitions,
    )

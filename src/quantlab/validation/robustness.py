r"""La robustesse : chercher un plateau plutôt qu'un pic.

**Le problème.** Un balayage de paramètres rend toujours un maximum. La question
n'est pas de le trouver, elle est de savoir s'il décrit un mécanisme ou le bruit
de l'échantillon. Les deux se ressemblent dans un tableau de résultats, et ils
ne se distinguent qu'en regardant le voisinage du point retenu.

**L'exemple qui tranche.** Une moyenne mobile de 179 séances rend un ratio de
Sharpe de 0,10. Celle de 180 séances rend 1,80. Celle de 181 séances rend 0,05.
Aucun mécanisme économique ne distingue 180 séances de 179 : le marché ne
connaît pas ce nombre. Le pic mesure donc l'échantillon, pas le monde. Le même
tableau lu autrement, 0,70 puis 0,80 puis 0,75 sur les trois mêmes fenêtres,
décrit une régularité qui survivra peut-être, parce qu'elle ne dépend pas d'un
réglage au grain près.

**Le remède, et son nom.** On classe les points de la grille non par leur propre
métrique mais par celle de leur voisinage. Un point entouré de bons voisins
garde un bon rang ; un pic isolé perd le sien. Le point retenu au sens du
plateau n'est presque jamais le meilleur point au sens de la métrique brute, et
c'est le but recherché.

**La grille se fixe avant de voir les résultats.** Élargir une grille après
coup, parce que le maximum touchait un bord, revient à choisir la grille en
fonction de la réponse. Le nombre d'essais devient alors inconnaissable, et
toute correction pour essais multiples devient impossible à calculer. La règle
du laboratoire est donc simple : la grille est déclarée dans la configuration de
l'étude, et son élargissement ouvre une nouvelle étude.

**Le prix de la recherche, chiffré.** Un balayage large augmente
mécaniquement le nombre d'essais, donc dégonfle le ratio de Sharpe exigé. Sous
l'hypothèse nulle où aucune configuration n'a de valeur, l'espérance du maximum
de :math:`N` ratios de Sharpe indépendants d'écart type :math:`\sigma` s'écrit,
d'après Bailey et López de Prado (2014) :

.. math::

    \mathbb{E}\left[\max_{n \le N} \widehat{SR}_n\right] \approx \sigma
    \left[ (1 - \gamma)\, Z^{-1}\!\left(1 - \frac{1}{N}\right)
    + \gamma\, Z^{-1}\!\left(1 - \frac{1}{N e}\right) \right]

où :math:`\gamma \approx 0{,}5772` est la constante d'Euler-Mascheroni et
:math:`Z^{-1}` la fonction quantile de la loi normale centrée réduite. Passer de
10 à 1000 essais fait passer cette espérance de :math:`1{,}57\,\sigma` à
:math:`3{,}26\,\sigma`, soit une exigence multipliée par 2,07 pour la même
absence de signal. Ces deux nombres sont MESURÉS, rendus par
:func:`quantlab.validation.dsr.expected_maximum_sharpe` à variance unitaire, et
un test les recalcule depuis la forme fermée ci-dessus.

**La borne à ne pas confondre avec cette espérance.** L'approximation
asymptotique :math:`\sigma\sqrt{2\ln N}` circule comme si elle était le
résultat précédent. Elle le surestime de 40 % à dix essais, 2,15 contre 1,57,
faute du terme correctif en :math:`\ln\ln N`. Surtout, elle écrase le rapport
entre 1000 et 10 essais à 1,73 au lieu de 2,07. La recherche multiple paraît
alors moins coûteuse qu'elle ne l'est, ce qui est l'erreur exactement inverse
de celle qu'on veut éviter ici.

**Ce que l'expression retenue ne fait pas.** Elle reste une approximation de
valeurs extrêmes. Sur 400 000 tirages de dix normales centrées réduites,
l'espérance du maximum vaut 1,54, soit 2 % sous les 1,57 de la formule, chiffre
MESURÉ le 2026-09-01. L'écart est sans conséquence devant les 40 % de la borne
en racine, et le laboratoire emploie la forme ci-dessus dans
``quantlab.validation.dsr``.

**La conséquence pratique.** Toutes les combinaisons évaluées se conservent,
y compris les mauvaises. Elles sont l'intrant du ratio de Sharpe dégonflé et de
la probabilité de surapprentissage, et les cacher fausse précisément le test qui
sert à détecter le surapprentissage. C'est la règle 8 du ``CLAUDE.md``.

**Provenance de la notion de plateau.** L'idée est ancienne dans la pratique et
rare dans la littérature évaluée par les pairs. Pardo (2008), *The Evaluation
and Optimization of Trading Strategies*, 2e édition, Wiley, consacre un chapitre
à la forme du profil d'optimisation. Wu, Lin, Huang et Wu (2024),
*Knowledge-Based Systems* 293, article 111630, DOI 10.1016/j.knosys.2024.111630,
proposent un algorithme de recherche de plateau de paramètres. Statut de cette
seconde référence : existence RAPPORTÉE, vérifiée dans Crossref le 2026-09-01,
texte intégral NON TROUVÉ hors abonnement. Leur définition quantitative n'a donc
pas été lue, et celle de ce module ne la reprend pas.

**Statut de la définition retenue ici : PRÉCEPTE.** Aucune définition canonique
du score de plateau n'existe dans la littérature consultée. Celle de
:func:`plateau_score` est un choix de ce laboratoire, documenté, testable, et
révisable. Elle ne se cite pas comme une mesure publiée.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd

from quantlab.analytics.drawdown import max_drawdown
from quantlab.analytics.ratios import sharpe_ratio, sharpe_standard_error, sharpe_tstat
from quantlab.analytics.returns import cagr, compound
from quantlab.analytics.risk import hit_rate, volatility
from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.logging import get_logger
from quantlab.core.types import CostBasis, Frequency, ReturnSeries, SampleTag

__all__ = [
    "DEFAULT_COST_MULTIPLIERS",
    "DEFAULT_DELAYS",
    "DEFAULT_NEIGHBORHOOD",
    "DEFAULT_SURVIVAL_THRESHOLD",
    "CostAnalysis",
    "RobustnessReport",
    "best_plateau",
    "cost_multiplier_analysis",
    "execution_delay_analysis",
    "parameter_sweep",
    "plateau_score",
    "sensitivity_analysis",
    "subperiod_performance",
]

_LOG = get_logger(__name__)

#: Signature d'une fonction d'évaluation de grille. Elle reçoit les paramètres
#: par mot-clé et rend soit une métrique, soit un dictionnaire de métriques.
EvaluateFn = Callable[..., float | Mapping[str, float]]

#: Les quatre façons d'agréger le voisinage d'un point de grille.
PlateauAggregator = Literal["median", "mean", "min", "quantile"]

#: Les deux façons de rapporter une variation relative à une élasticité.
ElasticityMethod = Literal["point", "arc"]

#: Ce qu'on fait d'une combinaison dont l'évaluation lève une exception.
ErrorPolicy = Literal["raise", "record"]

#: Multiples de coût balayés par défaut. Précepte : le 1 sert de référence, le
#: 10 sert de borne haute au-delà de laquelle aucune stratégie liquide ne vit.
DEFAULT_COST_MULTIPLIERS: tuple[float, ...] = (1.0, 2.0, 3.0, 5.0, 10.0)

#: Décalages d'exécution balayés par défaut, en nombre de périodes. Précepte.
DEFAULT_DELAYS: tuple[int, ...] = (0, 1, 2, 5)

#: Rayon de voisinage par défaut, en pas de grille. Précepte : un pas de chaque
#: côté suffit à distinguer un pic isolé, et coûte le moins de points de bord.
DEFAULT_NEIGHBORHOOD = 1

#: Seuil de survie par défaut d'une métrique. Zéro convient à un ratio de Sharpe
#: ou à un rendement excédentaire, et à rien d'autre. Précepte déclaré.
DEFAULT_SURVIVAL_THRESHOLD = 0.0

#: Nombre minimal d'observations exigé dans une sous-période. L'erreur type de
#: Lo (2002) estime un moment d'ordre quatre, qui n'existe pas en deçà.
MIN_SUBPERIOD_OBSERVATIONS = 4

#: Sous ce seuil relatif, un dénominateur est tenu pour nul et l'élasticité
#: correspondante devient indéfinie plutôt que gigantesque.
DEFAULT_ZERO_TOLERANCE = 1e-12

#: Noms de colonnes que le module produit et qu'un paramètre ne peut pas porter.
_RESERVED_COLUMNS = frozenset(
    {
        "trial",
        "error",
        "plateau_score",
        "neighborhood_size",
        "neighborhood_missing",
        "neighborhood_complete",
        "isolation",
        "plateau_fraction",
    }
)


# --------------------------------------------------------------------------- #
# Aides internes. Aucune n'est publique : elles fixent des conventions que les
# fonctions exportées documentent chacune pour son compte.
# --------------------------------------------------------------------------- #


def _check_grid(param_grid: Mapping[str, Sequence[Any]]) -> dict[str, tuple[Any, ...]]:
    """Valide une grille de paramètres et fige ses valeurs en tuples.

    Args:
        param_grid: nom de paramètre vers valeurs à balayer.

    Returns:
        La même grille, valeurs figées, ordre des clés préservé.

    Raises:
        ConfigError: grille vide, axe vide, doublon de valeur, ou nom réservé.
    """
    if not param_grid:
        raise ConfigError("la grille de paramètres est vide")
    figee: dict[str, tuple[Any, ...]] = {}
    for nom, valeurs in param_grid.items():
        if nom in _RESERVED_COLUMNS:
            raise ConfigError(f"« {nom} » est un nom de colonne réservé par ce module")
        suite = tuple(valeurs)
        if not suite:
            raise ConfigError(f"l'axe « {nom} » de la grille ne porte aucune valeur")
        if len(set(map(repr, suite))) != len(suite):
            raise ConfigError(f"l'axe « {nom} » porte deux fois la même valeur")
        figee[nom] = suite
    return figee


def _metric_row(sortie: float | Mapping[str, float], metric_name: str) -> dict[str, float]:
    """Met la sortie d'une fonction d'évaluation sous forme de colonnes.

    Args:
        sortie: un nombre, ou un dictionnaire de métriques nommées.
        metric_name: le nom donné à la colonne quand la sortie est un nombre.

    Raises:
        DataQualityError: si une métrique n'est pas convertible en flottant.
    """
    brut: Mapping[str, Any] = dict(sortie) if isinstance(sortie, Mapping) else {metric_name: sortie}
    ligne: dict[str, float] = {}
    for cle, valeur in brut.items():
        try:
            ligne[str(cle)] = float(valeur)
        except (TypeError, ValueError) as exc:
            raise DataQualityError(f"la métrique « {cle} » ne se convertit pas en flottant") from exc
    return ligne


def _grid_codes(frame: pd.DataFrame, param_cols: Sequence[str]) -> np.ndarray:
    """Rend la position de chaque ligne sur la grille, un entier par paramètre.

    Le passage aux positions rend le voisinage indépendant de l'espacement des
    valeurs. Une grille de fenêtres 10, 20, 40, 80 a des pas géométriques ; en
    positions, le voisin de 20 reste 10 d'un côté et 40 de l'autre.

    Args:
        frame: le tableau du balayage.
        param_cols: les colonnes de paramètres.

    Returns:
        Un tableau d'entiers de forme (lignes, paramètres).

    Raises:
        ConfigError: si une colonne demandée est absente.
        DataQualityError: si une valeur de paramètre est manquante.
    """
    colonnes: list[np.ndarray] = []
    for col in param_cols:
        if col not in frame.columns:
            raise ConfigError(f"la colonne de paramètre « {col} » est absente du balayage")
        serie = frame[col]
        if bool(serie.isna().any()):
            raise DataQualityError(f"la colonne « {col} » porte une valeur manquante")
        uniques = pd.Index(serie.unique())
        try:
            ordonnees = uniques.sort_values()
        except TypeError:
            ordonnees = pd.Index(sorted(uniques, key=repr))
        rangs = pd.Series(np.arange(len(ordonnees), dtype=np.int64), index=ordonnees)
        colonnes.append(serie.map(rangs).to_numpy(dtype=np.int64))
    return np.column_stack(colonnes)


def _neighbourhoods(codes: np.ndarray, neighborhood: int) -> tuple[list[np.ndarray], int]:
    """Rend, pour chaque ligne, les positions de son voisinage sur la grille.

    Le voisinage est le cube de rayon ``neighborhood`` en distance de Tchebychev
    sur les positions de grille, le point lui-même inclus. Le coût est de
    :math:`(2k+1)^d` recherches par point, où :math:`k` est le rayon et
    :math:`d` le nombre de paramètres.

    Args:
        codes: les positions de grille rendues par :func:`_grid_codes`.
        neighborhood: le rayon du cube, en pas de grille.

    Returns:
        La liste des positions voisines, et la taille du cube plein.

    Raises:
        ConfigError: si le rayon est négatif.
        DataQualityError: si deux lignes portent la même combinaison.
    """
    if neighborhood < 0:
        raise ConfigError(f"neighborhood vaut {neighborhood}, il doit être positif ou nul")
    table: dict[tuple[int, ...], int] = {}
    for position, ligne in enumerate(codes.tolist()):
        cle = tuple(ligne)
        if cle in table:
            raise DataQualityError("deux lignes du balayage portent la même combinaison de paramètres")
        table[cle] = position
    pas = range(-neighborhood, neighborhood + 1)
    decalages = list(itertools.product(pas, repeat=codes.shape[1]))
    voisinages: list[np.ndarray] = []
    for ligne in codes.tolist():
        trouves: list[int] = []
        for decalage in decalages:
            cle = tuple(a + b for a, b in zip(ligne, decalage, strict=True))
            position = table.get(cle)
            if position is not None:
                trouves.append(position)
        voisinages.append(np.asarray(trouves, dtype=np.int64))
    return voisinages, len(decalages)


def _aggregate(valeurs: np.ndarray, aggregator: PlateauAggregator, quantile: float | None) -> float:
    """Agrège les métriques d'un voisinage selon la convention demandée.

    Args:
        valeurs: les métriques du voisinage, valeurs manquantes déjà retirées.
        aggregator: ``median``, ``mean``, ``min`` ou ``quantile``.
        quantile: le niveau exigé par ``quantile``, entre 0 et 1.

    Raises:
        ConfigError: agrégateur inconnu, ou niveau de quantile absent ou hors bornes.
    """
    if valeurs.size == 0:
        return float("nan")
    if aggregator == "median":
        return float(np.median(valeurs))
    if aggregator == "mean":
        return float(np.mean(valeurs))
    if aggregator == "min":
        return float(np.min(valeurs))
    if aggregator == "quantile":
        if quantile is None or not 0.0 <= quantile <= 1.0:
            raise ConfigError(f"quantile vaut {quantile}, il doit être un niveau entre 0 et 1")
        return float(np.quantile(valeurs, quantile))
    raise ConfigError(f"agrégateur inconnu : « {aggregator} »")


def _relative_change(nouveau: float, base: float, *, method: ElasticityMethod, tol: float) -> float:
    """Rend la variation relative d'une grandeur, en point ou en arc.

    La version en point rapporte l'écart à la valeur initiale. La version en
    arc, dite du point milieu, le rapporte à la moyenne des deux valeurs. Elle
    est donc symétrique entre l'aller et le retour.

    Args:
        nouveau: la valeur après perturbation.
        base: la valeur de départ.
        method: ``point`` ou ``arc``.
        tol: en deçà de ce dénominateur, la variation est indéfinie.

    Raises:
        ConfigError: si la méthode est inconnue.
    """
    if method == "point":
        denominateur = base
    elif method == "arc":
        denominateur = 0.5 * (base + nouveau)
    else:
        raise ConfigError(f"méthode d'élasticité inconnue : « {method} »")
    if not math.isfinite(denominateur) or abs(denominateur) < tol:
        return float("nan")
    return (nouveau - base) / denominateur


def _subperiod_bounds(
    index: pd.Index,
    breakpoints: Sequence[Any] | None,
    n_periods: int | None,
) -> list[tuple[int, int]]:
    """Rend les bornes en positions des sous-périodes, fin exclue.

    Args:
        index: l'index de la série de rendements, supposé trié.
        breakpoints: les étiquettes qui OUVRENT une nouvelle sous-période.
        n_periods: le nombre de tranches contiguës de tailles voisines.

    Raises:
        ConfigError: si les deux arguments sont donnés, ou aucun, ou mal formés.
    """
    n = len(index)
    if (breakpoints is None) == (n_periods is None):
        raise ConfigError("donner exactement un argument parmi breakpoints et n_periods")
    if n_periods is not None:
        if n_periods < 1:
            raise ConfigError(f"n_periods vaut {n_periods}, il doit valoir au moins 1")
        if n_periods > n:
            raise ConfigError(f"{n_periods} sous-périodes demandées pour {n} observations")
        tranches = np.array_split(np.arange(n), n_periods)
        return [(int(t[0]), int(t[-1]) + 1) for t in tranches]
    coupures: list[int] = []
    precedent = 0
    for etiquette in breakpoints or ():
        position = int(index.searchsorted(etiquette, side="left"))
        if not 0 < position < n:
            raise ConfigError(f"la coupure « {etiquette} » tombe hors de l'index ou à son bord")
        if position <= precedent:
            raise ConfigError("les coupures doivent être strictement croissantes")
        coupures.append(position)
        precedent = position
    bornes = [0, *coupures, n]
    return [(bornes[i], bornes[i + 1]) for i in range(len(bornes) - 1)]


# --------------------------------------------------------------------------- #
# Le balayage de grille
# --------------------------------------------------------------------------- #


def parameter_sweep(
    param_grid: Mapping[str, Sequence[Any]],
    evaluate_fn: EvaluateFn,
    n_jobs: int = 1,
    *,
    metric_name: str = "metric",
    on_error: ErrorPolicy = "raise",
) -> pd.DataFrame:
    """Balaie une grille de paramètres et rend une ligne par combinaison.

    **(1) Le problème.** Une étude qui ne publie que sa meilleure configuration
    rend impossible toute correction pour essais multiples. Le nombre d'essais
    entre dans le ratio de Sharpe dégonflé, et personne ne peut le reconstituer
    après coup.

    **(2) L'intuition.** On garde tout. Le tableau rendu porte les mauvaises
    combinaisons comme les bonnes, et sa hauteur est le nombre d'essais.

    **(3) La formule.** Le balayage est le produit cartésien des axes :

    .. math::

        N = \\prod_{j=1}^{d} \\left| G_j \\right|

    **(4) Les variables.** :math:`d` le nombre de paramètres, :math:`G_j`
    l'ensemble des valeurs balayées sur l'axe :math:`j`, :math:`N` le nombre de
    combinaisons, donc le nombre d'essais.

    **(5) Les hypothèses.** La fonction d'évaluation est déterministe à
    paramètres donnés. Si elle tire au hasard, elle reçoit son générateur par la
    grille, et jamais par un appel implicite à ``numpy.random``.

    **(6) La provenance.** Le comptage des essais et sa raison viennent de
    Bailey et López de Prado (2014) pour le Sharpe dégonflé, et de Harvey, Liu
    et Zhu (2016) pour la correction des tests multiples.

    **(7) Les limites.** Le produit cartésien explose : cinq axes de dix valeurs
    font cent mille évaluations. Une grille grossière déclarée d'avance vaut
    mieux qu'une grille fine choisie après coup.

    **(8) Les alternatives.** Le tirage aléatoire de configurations, moins cher
    à dimension élevée, et l'optimisation bayésienne. Aucun des deux ne rend une
    grille régulière, donc aucun ne se prête au score de plateau tel que défini
    ici.

    **(9) Pourquoi ce choix.** La grille régulière est le seul dessin où le
    voisinage d'un point a un sens géométrique simple.

    **(10) Comment vérifier.** La hauteur du tableau vaut le produit des
    longueurs des axes, et les colonnes de paramètres reproduisent exactement le
    produit cartésien attendu.

    Args:
        param_grid: nom de paramètre vers valeurs à balayer, ordre préservé.
        evaluate_fn: reçoit les paramètres par mot-clé, rend un nombre ou un
            dictionnaire de métriques nommées.
        n_jobs: nombre de fils d'exécution. Au-delà de 1, le gain n'existe que
            si la fonction relâche le verrou global, ce que fait NumPy et ne
            fait pas du Python pur. L'ordre des lignes ne dépend jamais de ce
            réglage.
        metric_name: nom de la colonne quand la fonction rend un nombre.
        on_error: ``raise`` arrête au premier échec, ``record`` inscrit la
            combinaison avec une métrique manquante et le message d'erreur.

    Returns:
        Un tableau long, une ligne par combinaison, colonnes ``trial``, les
        paramètres, les métriques, et ``error``.

    Raises:
        ConfigError: grille mal formée, ou ``n_jobs`` inférieur à 1.
    """
    grille = _check_grid(param_grid)
    if n_jobs < 1:
        raise ConfigError(f"n_jobs vaut {n_jobs}, il doit valoir au moins 1")
    noms = list(grille)
    combinaisons = [dict(zip(noms, v, strict=True)) for v in itertools.product(*grille.values())]

    def evaluer(params: dict[str, Any]) -> tuple[dict[str, float], str]:
        """Évalue une combinaison et rend ses métriques et son message d'erreur."""
        try:
            return _metric_row(evaluate_fn(**params), metric_name), ""
        except Exception as exc:
            if on_error == "raise":
                raise
            return {}, f"{type(exc).__name__}: {exc}"

    if n_jobs == 1:
        resultats = [evaluer(p) for p in combinaisons]
    else:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=n_jobs) as pool:
            resultats = list(pool.map(evaluer, combinaisons))

    lignes: list[dict[str, Any]] = []
    for rang, (params, (metriques, message)) in enumerate(zip(combinaisons, resultats, strict=True)):
        lignes.append({"trial": rang, **params, **metriques, "error": message})
    tableau = pd.DataFrame.from_records(lignes)
    colonnes_metriques = [c for c in tableau.columns if c not in {"trial", "error", *noms}]
    ordre = ["trial", *noms, *colonnes_metriques, "error"]
    tableau = tableau.reindex(columns=ordre)
    tableau["error"] = tableau["error"].fillna("").astype("string")
    echecs = int((tableau["error"] != "").sum())
    _LOG.info(
        "balayage terminé",
        extra={"n_trials": len(tableau), "n_failed": echecs, "n_axes": len(noms)},
    )
    return tableau


# --------------------------------------------------------------------------- #
# Le score de plateau
# --------------------------------------------------------------------------- #


def plateau_score(
    sweep_df: pd.DataFrame,
    param_cols: Sequence[str],
    metric_col: str,
    neighborhood: int = DEFAULT_NEIGHBORHOOD,
    *,
    aggregator: PlateauAggregator = "median",
    quantile: float | None = None,
    threshold: float | None = None,
) -> pd.DataFrame:
    r"""Note chaque point de la grille par la tenue de son voisinage.

    **(1) Le problème.** Distinguer un pic isolé, qui décrit le bruit de
    l'échantillon, d'un plateau, qui décrit peut-être un mécanisme. La métrique
    du point seul ne le dit pas : elle vaut 1,80 dans les deux cas.

    **(2) L'intuition.** On remplace la métrique du point par celle de son
    voisinage. Un point entouré de bons voisins garde sa note ; un pic isolé la
    perd, puisque ses voisins sont mauvais et qu'ils pèsent dans l'agrégat.

    **(3) La formule, PRÉCEPTE de ce laboratoire.** Soit :math:`g(p)` la
    position de la combinaison :math:`p` sur la grille, à valeurs entières. Le
    voisinage de rayon :math:`k` est le cube de Tchebychev, point compris :

    .. math::

        \mathcal{V}_k(p) = \left\{ q \in \mathcal{G} :
        \left\| g(q) - g(p) \right\|_\infty \le k \right\}

    Le score et l'isolement valent :

    .. math::

        S_k(p) = \operatorname*{med}_{q \in \mathcal{V}_k(p)} m(q),
        \qquad
        I_k(p) = m(p) - S_k(p)

    **(4) Les variables.** :math:`m(\cdot)` la métrique balayée, :math:`k` le
    rayon en pas de grille, :math:`\mathcal{G}` l'ensemble des combinaisons
    évaluées, :math:`S_k` le score de plateau, :math:`I_k` l'isolement.

    **Échelle des deux nombres.** Le score est dans l'unité de la métrique : un
    score de 0,92 sur une grille de ratios de Sharpe est un ratio de Sharpe.
    L'isolement l'est aussi. Il est proche de zéro sur un plateau, nettement
    positif sur un pic, négatif dans un creux local. Aucun des deux n'est borné.

    **(5) Les hypothèses.** La grille est régulière et les axes sont ordonnés,
    sans quoi la notion de voisin n'a pas de sens. Les combinaisons absentes du
    tableau sont traitées comme non évaluées, jamais comme mauvaises.

    **(6) La provenance.** L'idée de plateau vient de la pratique, Pardo (2008)
    la décrit sous le nom de profil d'optimisation. Wu, Lin, Huang et Wu (2024)
    en proposent une recherche automatique. La formule ci-dessus n'est reprise
    d'aucun des deux : elle est un PRÉCEPTE, et se cite comme tel.

    **(7) Les limites.** Trois, et elles comptent. Un point de bord a moins de
    voisins, donc un score construit sur moins de preuves, ce que la colonne
    ``neighborhood_complete`` signale et que :func:`best_plateau` filtre. Le
    score dépend du pas de la grille : une grille deux fois plus fine élargit le
    plateau apparent sans rien changer au monde. Enfin la médiane d'un voisinage
    à trous se calcule sur ce qui reste, et la colonne
    ``neighborhood_missing`` compte les trous.

    **(8) Les alternatives.** Le rapport :math:`m(p) / S_k(p)` plutôt que la
    différence, écarté ici. Son dénominateur est un ratio de Sharpe, donc
    souvent proche de zéro, et le rapport explose alors sans que rien de
    financier ne se passe. La moyenne du voisinage plutôt que sa médiane,
    disponible par ``aggregator``, plus sensible à un unique voisin
    catastrophique. Le minimum du voisinage, disponible aussi, lecture du pire
    cas.

    **(9) Pourquoi ce choix.** La médiane résiste à un artefact isolé de la
    grille tout en punissant un voisinage majoritairement mauvais. La différence
    reste définie quel que soit le signe de la métrique.

    **(10) Comment vérifier.** Deux identités. Sur une grille de métrique
    constante, le score vaut la constante partout et l'isolement vaut zéro
    partout. Avec un rayon nul, le score vaut la métrique elle-même et
    l'isolement vaut zéro, chaque point étant son seul voisin.

    Args:
        sweep_df: le tableau rendu par :func:`parameter_sweep`.
        param_cols: les colonnes qui portent les axes de la grille.
        metric_col: la colonne à noter, orientée de sorte que plus vaut mieux.
        neighborhood: le rayon du cube, en pas de grille.
        aggregator: la façon d'agréger le voisinage.
        quantile: le niveau exigé quand ``aggregator`` vaut ``quantile``.
        threshold: seuil facultatif. Quand il est donné, la colonne
            ``plateau_fraction`` porte la part du voisinage qui l'atteint.

    Returns:
        Une copie de ``sweep_df`` augmentée de six colonnes : ``plateau_score``,
        ``isolation``, ``neighborhood_size``, ``neighborhood_missing``,
        ``neighborhood_complete`` et ``plateau_fraction``. Les colonnes de même
        nom déjà présentes sont écrasées.

    Raises:
        ConfigError: colonne absente, rayon négatif, agrégateur inconnu.
        DataQualityError: combinaison de paramètres en double.
        InsufficientDataError: si le tableau est vide.
    """
    if len(sweep_df) == 0:
        raise InsufficientDataError("le balayage ne porte aucune ligne")
    if metric_col not in sweep_df.columns:
        raise ConfigError(f"la colonne de métrique « {metric_col} » est absente du balayage")
    if not param_cols:
        raise ConfigError("param_cols ne nomme aucun axe de grille")

    frame = sweep_df.reset_index(drop=True)
    codes = _grid_codes(frame, param_cols)
    voisinages, taille_cube = _neighbourhoods(codes, neighborhood)
    metriques = frame[metric_col].to_numpy(dtype="float64")
    valide = np.isfinite(metriques)

    scores = np.empty(len(frame), dtype="float64")
    tailles = np.empty(len(frame), dtype="int64")
    manquants = np.empty(len(frame), dtype="int64")
    complets = np.empty(len(frame), dtype=bool)
    fractions = np.full(len(frame), np.nan, dtype="float64")

    for position, voisins in enumerate(voisinages):
        retenus = voisins[valide[voisins]]
        valeurs = metriques[retenus]
        scores[position] = _aggregate(valeurs, aggregator, quantile)
        tailles[position] = retenus.size
        manquants[position] = voisins.size - retenus.size
        complets[position] = voisins.size == taille_cube and manquants[position] == 0
        if threshold is not None and retenus.size > 0:
            fractions[position] = float(np.mean(valeurs >= threshold))

    note = frame.copy()
    note["plateau_score"] = scores
    note["isolation"] = metriques - scores
    note["neighborhood_size"] = tailles
    note["neighborhood_missing"] = manquants
    note["neighborhood_complete"] = complets
    note["plateau_fraction"] = fractions
    return note


def best_plateau(
    sweep_df: pd.DataFrame,
    param_cols: Sequence[str],
    metric_col: str,
    neighborhood: int = DEFAULT_NEIGHBORHOOD,
    *,
    aggregator: PlateauAggregator = "median",
    quantile: float | None = None,
    threshold: float | None = None,
    require_full_neighborhood: bool = True,
) -> pd.Series:
    """Rend le meilleur point au sens du plateau, qui n'est pas le meilleur point.

    **L'écart avec le maximum brut, sur un exemple travaillé.** Une grille croise
    quatre fenêtres rapides et quatre fenêtres lentes. La métrique vaut environ
    1,00 sur un bloc de neuf cases contiguës, et 0,10 partout ailleurs, sauf une
    case isolée à 3,00. Le maximum brut retient la case à 3,00, dont les huit
    voisins valent 0,10 : sa médiane de voisinage vaut donc 0,10, et son
    isolement vaut 2,90. Le centre du bloc, lui, garde une médiane de voisinage
    de 1,00 et un isolement nul. Cette fonction retient le centre du bloc, dont
    la métrique brute est trois fois plus petite. C'est le comportement voulu, et
    le test qui le vérifie construit exactement cette grille à la main.

    **La règle de départage, déclarée.** À score de plateau égal, le point de
    plus forte métrique brute l'emporte. À égalité encore, le premier dans
    l'ordre du balayage l'emporte. Aucun tirage au sort n'intervient.

    **Pourquoi les bords sont écartés par défaut.** Un point du bord de la
    grille n'a jamais été entouré : la moitié de son voisinage n'a pas été
    évaluée. Sa médiane est alors calculée sur les cases favorables qui
    subsistent, ce qui lui donne un avantage mécanique. Le laboratoire préfère
    exiger un voisinage plein, quitte à ne retenir aucun point, plutôt que
    couronner un bord. La conséquence pratique est que la grille se dessine
    assez large pour que la zone intéressante soit intérieure.

    Args:
        sweep_df: le tableau rendu par :func:`parameter_sweep`.
        param_cols: les colonnes qui portent les axes de la grille.
        metric_col: la colonne à noter, orientée de sorte que plus vaut mieux.
        neighborhood: le rayon du cube, en pas de grille.
        aggregator: la façon d'agréger le voisinage.
        quantile: le niveau exigé quand ``aggregator`` vaut ``quantile``.
        threshold: seuil facultatif transmis à :func:`plateau_score`.
        require_full_neighborhood: n'accepte que les points dont le voisinage
            est entièrement évalué.

    Returns:
        La ligne gagnante, paramètres et colonnes de plateau comprises.

    Raises:
        InsufficientDataError: si aucun point ne remplit les conditions.
    """
    note = plateau_score(
        sweep_df,
        param_cols,
        metric_col,
        neighborhood,
        aggregator=aggregator,
        quantile=quantile,
        threshold=threshold,
    )
    eligible = np.isfinite(note["plateau_score"].to_numpy(dtype="float64"))
    if require_full_neighborhood:
        eligible &= note["neighborhood_complete"].to_numpy(dtype=bool)
    if not eligible.any():
        raise InsufficientDataError(
            "aucun point de la grille n'a de voisinage plein et de score défini ; "
            "élargir la grille ou réduire le rayon"
        )
    candidats = note.loc[eligible].reset_index(drop=True)
    ordre = np.lexsort(
        (
            np.arange(len(candidats)),
            -candidats[metric_col].to_numpy(dtype="float64"),
            -candidats["plateau_score"].to_numpy(dtype="float64"),
        )
    )
    gagnant = candidats.iloc[int(ordre[0])]
    _LOG.info(
        "plateau retenu",
        extra={
            "plateau_score": float(gagnant["plateau_score"]),
            "raw_metric": float(gagnant[metric_col]),
            "isolation": float(gagnant["isolation"]),
        },
    )
    return gagnant


# --------------------------------------------------------------------------- #
# La sensibilité à un paramètre
# --------------------------------------------------------------------------- #


def sensitivity_analysis(
    base_params: Mapping[str, Any],
    evaluate_fn: EvaluateFn,
    perturbations: Mapping[str, Sequence[float]],
    *,
    metric_name: str = "metric",
    method: ElasticityMethod = "point",
    zero_tolerance: float = DEFAULT_ZERO_TOLERANCE,
) -> pd.DataFrame:
    r"""Fait varier un paramètre à la fois et rend l'élasticité de la métrique.

    **(1) Le problème.** Savoir quel réglage porte le résultat. Une stratégie
    dont la performance double quand un seuil bouge de 5 % n'est pas réglée,
    elle est ajustée à l'échantillon.

    **(2) L'intuition.** L'élasticité répond en une phrase : quand ce paramètre
    monte de 1 %, de combien de pour cent la métrique bouge. Une élasticité
    proche de zéro dit que le paramètre ne décide de rien, ce qui est la
    meilleure nouvelle possible.

    **(3) La formule.** Version en point, rapportée à la configuration de base :

    .. math::

        \varepsilon_j = \frac{\left[m(\theta_j') - m(\theta)\right] / m(\theta)}
                             {\left(\theta_j' - \theta_j\right) / \theta_j}

    Version en arc, dite du point milieu, où chaque écart se rapporte à la
    moyenne des deux états :

    .. math::

        \varepsilon_j^{arc} = \frac{\Delta m}{\bar{m}} \Big/ \frac{\Delta \theta_j}{\bar{\theta}_j}

    **(4) Les variables.** :math:`\theta` la configuration de base,
    :math:`\theta_j'` la même avec le seul paramètre :math:`j` remplacé,
    :math:`m(\cdot)` la métrique, :math:`\bar{m}` et :math:`\bar{\theta}_j` les
    moyennes des deux états.

    **(5) Les hypothèses.** Les paramètres agissent séparément dans le voisinage
    exploré. Faux dès qu'il y a interaction, et c'est justement ce que le
    balayage complet mesure, là où cette analyse ne le voit pas.

    **(6) La provenance.** L'élasticité est la notion standard de la microéconomie,
    et la forme en arc est celle d'Allen (1938), *Mathematical Analysis for
    Economists*. Rien de propre à la finance quantitative n'entre ici.

    **(7) Les limites.** L'élasticité en point n'est pas symétrique : mesurée de
    2 vers 3 elle ne vaut pas l'opposé de celle mesurée de 3 vers 2. Elle est
    indéfinie quand la valeur de base du paramètre ou de la métrique est nulle,
    et la fonction rend alors une valeur manquante plutôt qu'un très grand
    nombre. Elle ne voit qu'un axe à la fois.

    **(8) Les alternatives.** La dérivée partielle numérique, qui garde l'unité
    des grandeurs et ne se compare donc pas d'un paramètre à l'autre. Les
    indices de Sobol, qui décomposent la variance et attrapent les interactions,
    au prix de plusieurs milliers d'évaluations.

    **(9) Pourquoi ce choix.** L'élasticité est sans dimension, donc comparable
    entre une fenêtre en jours et un seuil en points de base, ce qui est la
    seule question posée ici.

    **(10) Comment vérifier.** Sur :math:`m(x) = c\,x`, l'élasticité vaut
    exactement 1 pour toute perturbation et pour tout :math:`c` non nul. Sur
    :math:`m(x) = x^2` en partant de 2 vers 3, la version en point vaut
    exactement 2,5 et la version en arc exactement 25/13.

    Args:
        base_params: la configuration de référence, passée telle quelle.
        evaluate_fn: reçoit les paramètres par mot-clé et rend la métrique.
        perturbations: nom de paramètre vers valeurs de remplacement à essayer.
        metric_name: la métrique retenue quand la fonction rend un dictionnaire.
        method: ``point`` ou ``arc``.
        zero_tolerance: seuil sous lequel un dénominateur est tenu pour nul.

    Returns:
        Un tableau long, une ligne par couple paramètre et valeur essayée.

    Raises:
        ConfigError: paramètre perturbé absent de la base, ou méthode inconnue.
        DataQualityError: si la métrique de base n'est pas finie.
    """
    if not perturbations:
        raise ConfigError("aucune perturbation demandée")
    inconnus = [k for k in perturbations if k not in base_params]
    if inconnus:
        raise ConfigError(f"paramètres perturbés absents de la configuration de base : {inconnus}")

    base_metrique = _metric_row(evaluate_fn(**dict(base_params)), metric_name)
    if metric_name not in base_metrique:
        raise ConfigError(f"la métrique « {metric_name} » est absente de la sortie de l'évaluation")
    m0 = base_metrique[metric_name]
    if not math.isfinite(m0):
        raise DataQualityError("la métrique de la configuration de base n'est pas finie")

    lignes: list[dict[str, Any]] = []
    for nom, valeurs in perturbations.items():
        p0 = base_params[nom]
        for valeur in valeurs:
            params = {**dict(base_params), nom: valeur}
            m1 = _metric_row(evaluate_fn(**params), metric_name)[metric_name]
            try:
                base_numerique = float(p0)
                essai_numerique = float(valeur)
            except (TypeError, ValueError):
                variation_param = float("nan")
            else:
                variation_param = _relative_change(
                    essai_numerique, base_numerique, method=method, tol=zero_tolerance
                )
            variation_metrique = _relative_change(m1, m0, method=method, tol=zero_tolerance)
            elasticite = (
                variation_metrique / variation_param
                if math.isfinite(variation_param) and abs(variation_param) >= zero_tolerance
                else float("nan")
            )
            lignes.append(
                {
                    "parameter": nom,
                    "base_value": p0,
                    "value": valeur,
                    "base_metric": m0,
                    "metric": m1,
                    "relative_param_change": variation_param,
                    "relative_metric_change": variation_metrique,
                    "elasticity": elasticite,
                    "method": method,
                }
            )
    return pd.DataFrame.from_records(lignes)


# --------------------------------------------------------------------------- #
# La performance par sous-période
# --------------------------------------------------------------------------- #


def subperiod_performance(
    returns: ReturnSeries,
    breakpoints: Sequence[Any] | None = None,
    n_periods: int | None = None,
    *,
    frequency: Frequency = Frequency.DAILY,
    risk_free: float = 0.0,
    error_method: Literal["lo", "iid"] = "lo",
    min_observations: int = MIN_SUBPERIOD_OBSERVATIONS,
    labels: Sequence[str] | None = None,
) -> pd.DataFrame:
    r"""Rend la performance par sous-période, ratios de Sharpe et erreurs types.

    **(1) Le problème.** Une stratégie dont le ratio de Sharpe vaut 1,2 sur
    trente ans peut n'avoir gagné que pendant trois d'entre elles. Le chiffre
    d'ensemble ne le dit pas ; le découpage le dit.

    **(2) L'intuition.** On recalcule tout sur chaque tranche, et on publie
    l'erreur type à côté du point. Une tranche de deux ans porte un Sharpe dont
    l'intervalle de confiance couvre presque toujours zéro, et l'afficher évite
    de conclure sur du vide.

    **(3) Les formules.** Le ratio de Sharpe et ses deux erreurs types viennent
    de ``quantlab.analytics.ratios`` et ne sont pas réimplémentés ici, règle 12
    du ``CLAUDE.md``. Sur une tranche de :math:`T` observations :

    .. math::

        \widehat{SR}_{ann} = \frac{\bar{r} - r_f}{\hat{\sigma}} \sqrt{N},
        \qquad
        \widehat{SE}_{iid} = \sqrt{\frac{1 + \frac{1}{2}\widehat{SR}_p^2}{T}}

    **(4) Les variables.** :math:`\bar{r}` la moyenne de la tranche,
    :math:`\hat{\sigma}` son écart type d'échantillon, :math:`N` le nombre de
    périodes par an, :math:`\widehat{SR}_p` le ratio périodique, :math:`T` la
    longueur de la tranche.

    **(5) Les hypothèses.** Les coupures sont fixées d'avance. Une coupure
    choisie après lecture des rendements fabrique la conclusion qu'elle est
    censée tester, et c'est la faute la plus fréquente de cette analyse.

    **(6) La provenance.** La pratique du découpage par décennie est celle de
    Fama et French dans leurs tables de sous-périodes. Les erreurs types
    viennent de Jobson et Korkie (1981) corrigés par Memmel (2003), et de Lo
    (2002) pour la version robuste à l'autocorrélation.

    **(7) Les limites.** Découper divise la puissance du test. Trois tranches de
    dix ans donnent trois Sharpe dont chacun a une erreur type environ 1,7 fois
    plus grande que celle du Sharpe d'ensemble, puisque l'erreur type décroît en
    racine de la longueur. Une tranche perdante n'est donc pas une preuve de
    rupture.

    **(8) Les alternatives.** Le ratio de Sharpe glissant, qui montre la même
    chose en continu sans découpage arbitraire. Les tests de rupture de Bai et
    Perron (2003), qui cherchent la date de rupture au lieu de la supposer, au
    prix d'une correction pour recherche de date.

    **(9) Pourquoi ce choix.** Un découpage déclaré d'avance se lit et se
    conteste. Une recherche de rupture est plus fine et beaucoup plus facile à
    mal utiliser.

    **(10) Comment vérifier.** Sur une série dont chaque moitié alterne deux
    valeurs symétriques autour de sa moyenne, le ratio annualisé de la moitié
    vaut exactement :math:`(m/s)\sqrt{T-1}` avec :math:`N = T`, forme fermée que
    le test emploie.

    Args:
        returns: les rendements simples, indexés par date croissante.
        breakpoints: les étiquettes qui OUVRENT une nouvelle sous-période. La
            première observation à cette étiquette ou après elle ouvre la
            tranche suivante.
        n_periods: le nombre de tranches contiguës de tailles voisines. Exclusif
            avec ``breakpoints``.
        frequency: la fréquence d'observation, qui fixe l'annualisation.
        risk_free: le taux sans risque annuel, soustrait avant annualisation.
        error_method: l'erreur type employée pour la statistique de test.
        min_observations: la longueur minimale d'une tranche.
        labels: les noms des tranches. Sans valeur, elles sont numérotées.

    Returns:
        Un tableau, une ligne par sous-période, colonnes ``label``, ``start``,
        ``end``, ``n_observations``, ``total_return``, ``cagr``, ``volatility``,
        ``sharpe``, ``sharpe_se_iid``, ``sharpe_se_lo``, ``t_stat``,
        ``max_drawdown`` et ``hit_rate``.

    Raises:
        ConfigError: découpage mal formé, ou nombre d'étiquettes incohérent.
        InsufficientDataError: si une tranche est plus courte que le minimum.
    """
    serie = returns.dropna().astype("float64")
    if not serie.index.is_monotonic_increasing:
        raise ConfigError("l'index des rendements n'est pas croissant")
    bornes = _subperiod_bounds(serie.index, breakpoints, n_periods)
    if labels is not None and len(labels) != len(bornes):
        raise ConfigError(f"{len(labels)} étiquettes pour {len(bornes)} sous-périodes")

    lignes: list[dict[str, Any]] = []
    for rang, (debut, fin) in enumerate(bornes):
        tranche = serie.iloc[debut:fin]
        if len(tranche) < min_observations:
            raise InsufficientDataError(
                f"la sous-période {rang} porte {len(tranche)} observations, {min_observations} exigées"
            )
        erreurs = sharpe_standard_error(tranche, frequency=frequency, risk_free=risk_free, annualize=True)
        lignes.append(
            {
                "label": labels[rang] if labels is not None else f"P{rang + 1}",
                "start": tranche.index[0],
                "end": tranche.index[-1],
                "n_observations": len(tranche),
                "total_return": float(compound(tranche)),
                "cagr": float(cagr(tranche, frequency)),
                "volatility": volatility(tranche, frequency, annualize=True),
                "sharpe": sharpe_ratio(tranche, frequency=frequency, risk_free=risk_free),
                "sharpe_se_iid": erreurs.iid,
                "sharpe_se_lo": erreurs.lo,
                "t_stat": sharpe_tstat(
                    tranche, frequency=frequency, risk_free=risk_free, method=error_method
                ),
                "max_drawdown": max_drawdown(tranche),
                "hit_rate": hit_rate(tranche),
            }
        )
    return pd.DataFrame.from_records(lignes)


# --------------------------------------------------------------------------- #
# Les coûts, et le point de rupture
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True, eq=False)
class CostAnalysis:
    """Ce que la stratégie devient quand les coûts supposés se révèlent faux.

    La comparaison de deux instances n'a pas de sens, un tableau pandas n'ayant
    pas de valeur de vérité unique ; ``eq=False`` retire donc l'égalité produite
    d'office par ``dataclass``.

    Attributes:
        table: une ligne par multiple testé, colonnes ``multiplier``,
            ``metric`` et ``survives``.
        breakeven_multiplier: le multiple auquel la métrique atteint le seuil,
            interpolé linéairement entre les deux multiples qui l'encadrent.
            Vaut ``None`` quand aucun encadrement n'existe.
        threshold: le seuil de survie retenu.
        status: ``bracketed`` si le point de rupture est encadré,
            ``survives_all`` si la stratégie tient jusqu'au dernier multiple,
            ``dead_at_first`` si elle est déjà morte au premier.
        monotone: vrai si la métrique décroît faiblement avec le multiple, ce
            qu'une vraie courbe de coût fait toujours.
    """

    table: pd.DataFrame
    breakeven_multiplier: float | None
    threshold: float
    status: str
    monotone: bool


def cost_multiplier_analysis(
    evaluate_fn: Callable[[float], float],
    multipliers: Sequence[float] = DEFAULT_COST_MULTIPLIERS,
    *,
    threshold: float = DEFAULT_SURVIVAL_THRESHOLD,
) -> CostAnalysis:
    r"""Rend le multiple des coûts supposés auquel la stratégie meurt.

    **(1) Le problème.** Un backtest net de frais suppose un coût unitaire. Ce
    coût est une hypothèse, souvent optimiste, et le rendement publié en dépend
    linéairement. La question utile n'est donc pas « combien rapporte-t-elle »
    mais « à partir de quel coût ne rapporte-t-elle plus ».

    **(2) L'intuition.** On multiplie le coût supposé par 1, 2, 3, 5 puis 10, et
    on regarde où la métrique traverse zéro. Une stratégie qui meurt à 1,3 fois
    ses coûts supposés est une stratégie morte, l'incertitude sur un coût
    d'exécution dépassant couramment 30 %.

    **(3) La formule.** Le rendement net est affine en le multiple tant que la
    rotation ne change pas :

    .. math::

        m(\lambda) = m_{brut} - \lambda \, c, \qquad
        \lambda^{*} = \frac{m_{brut} - \tau}{c}

    Entre deux multiples testés qui encadrent le seuil, l'interpolation retenue
    est linéaire :

    .. math::

        \lambda^{*} = \lambda_i + (\lambda_{i+1} - \lambda_i)
        \frac{m(\lambda_i) - \tau}{m(\lambda_i) - m(\lambda_{i+1})}

    **(4) Les variables.** :math:`\lambda` le multiple des coûts supposés,
    :math:`c` le coût total à multiple unitaire, :math:`\tau` le seuil de
    survie, :math:`\lambda^{*}` le multiple de rupture.

    **(5) Les hypothèses.** La rotation ne réagit pas au coût. C'est faux d'un
    vrai gérant, qui négocie moins quand négocier coûte plus cher, et cela rend
    le multiple de rupture calculé ici PESSIMISTE.

    **(6) La provenance.** La pratique vient de Novy-Marx et Velikov (2016),
    *Review of Financial Studies* 29(1), qui mesurent la survie de dizaines
    d'anomalies après coûts. La forme affine du rendement net en le coût est
    élémentaire et ne se cite pas.

    **(7) Les limites.** L'interpolation suppose la linéarité entre deux points
    testés, ce qui est exact pour un coût proportionnel et faux pour un modèle
    d'impact en racine. Sur une grille grossière, le multiple rendu porte donc
    une erreur d'interpolation qu'un balayage plus fin réduit.

    **(8) Les alternatives.** Résoudre :math:`m(\lambda) = \tau` par recherche
    de racine, plus précis et beaucoup plus coûteux quand chaque évaluation est
    un backtest complet. Balayer le coût unitaire en points de base plutôt qu'en
    multiple, plus lisible pour un exécutant, moins comparable entre stratégies.

    **(9) Pourquoi ce choix.** Le multiple est sans dimension, donc il compare
    une stratégie sur actions et une stratégie sur contrats à terme. Cinq points
    suffisent à répondre à la seule question posée, celle de l'ordre de grandeur.

    **(10) Comment vérifier.** Sur une fonction affine décroissante connue, le
    multiple rendu vaut exactement le point mort analytique, l'interpolation
    linéaire étant exacte sur une droite.

    Args:
        evaluate_fn: reçoit le multiple et rend la métrique nette correspondante.
        multipliers: les multiples à essayer, strictement croissants et positifs.
        threshold: le seuil sous lequel la stratégie est déclarée morte.

    Returns:
        Une instance de :class:`CostAnalysis`.

    Raises:
        ConfigError: multiples vides, non croissants, ou non positifs.
        DataQualityError: si une métrique rendue n'est pas finie.
    """
    lambdas = [float(m) for m in multipliers]
    if len(lambdas) < 2:
        raise ConfigError("il faut au moins deux multiples pour encadrer un point de rupture")
    if any(a >= b for a, b in itertools.pairwise(lambdas)):
        raise ConfigError("les multiples doivent être strictement croissants")
    if lambdas[0] <= 0.0:
        raise ConfigError("les multiples doivent être strictement positifs")

    metriques: list[float] = []
    for lam in lambdas:
        valeur = float(evaluate_fn(lam))
        if not math.isfinite(valeur):
            raise DataQualityError(f"la métrique au multiple {lam} n'est pas finie")
        metriques.append(valeur)

    survit = [m > threshold for m in metriques]
    table = pd.DataFrame({"multiplier": lambdas, "metric": metriques, "survives": survit})
    monotone = all(a >= b for a, b in itertools.pairwise(metriques))

    if not survit[0]:
        return CostAnalysis(table, None, threshold, "dead_at_first", monotone)
    if all(survit):
        return CostAnalysis(table, None, threshold, "survives_all", monotone)

    rupture = next(i for i, vivant in enumerate(survit) if not vivant)
    gauche, droite = rupture - 1, rupture
    ecart = metriques[gauche] - metriques[droite]
    if abs(ecart) < DEFAULT_ZERO_TOLERANCE:
        breakeven = lambdas[droite]
    else:
        part = (metriques[gauche] - threshold) / ecart
        breakeven = lambdas[gauche] + (lambdas[droite] - lambdas[gauche]) * part
    _LOG.info("multiple de rupture des coûts", extra={"breakeven": breakeven, "threshold": threshold})
    return CostAnalysis(table, float(breakeven), threshold, "bracketed", monotone)


# --------------------------------------------------------------------------- #
# Le décalage d'exécution
# --------------------------------------------------------------------------- #


def execution_delay_analysis(
    evaluate_fn: Callable[[int], float],
    delays: Sequence[int] = DEFAULT_DELAYS,
    *,
    retention_threshold: float = 0.5,
) -> pd.DataFrame:
    r"""Rend ce que coûte un décalage d'exécution, en périodes.

    **(1) Le problème.** Un backtest suppose souvent qu'on négocie au prix qui a
    servi à calculer le signal. Personne ne fait cela : le signal se calcule à la
    clôture et l'ordre part le lendemain. Un signal qui s'effondre avec une
    période de retard n'est pas exploitable, quel que soit son ratio de Sharpe.

    **(2) L'intuition.** On refait le backtest en décalant l'exécution d'une, de
    deux puis de cinq périodes, et on regarde ce qui reste. La décroissance
    mesure la vitesse à laquelle l'information contenue dans le signal se
    dissipe dans les prix.

    **(3) La formule.** Rétention et perte relative au décalage nul :

    .. math::

        R(h) = \frac{m(h)}{m(0)}, \qquad D(h) = m(h) - m(0)

    **(4) Les variables.** :math:`h` le décalage en périodes, :math:`m(h)` la
    métrique obtenue avec ce décalage, :math:`R` la rétention, :math:`D` la
    perte en unités de la métrique.

    **(5) Les hypothèses.** La métrique de référence est celle du plus petit
    décalage fourni, et elle est strictement positive. Si elle ne l'est pas, la
    rétention est indéfinie et la fonction rend une valeur manquante, la perte
    absolue restant lisible.

    **(6) La provenance.** Le contrôle vient de Jegadeesh et Titman (1993), qui
    sautent une semaine entre la formation et la détention. Ce saut écarte les
    effets de microstructure. López de Prado (2018) en fait un contrôle
    systématique.

    **(7) Les limites.** Le décalage se mesure en périodes de la série, donc en
    séances pour du quotidien. Il ne dit rien du délai en secondes, qui est la
    grandeur qui compte pour un signal intrajournalier.

    **(8) Les alternatives.** Le décalage fractionnaire, obtenu en négociant sur
    plusieurs séances, plus réaliste et moins lisible. La mesure directe du
    coefficient d'information à horizons croissants, qui répond à la même
    question sur le signal plutôt que sur le portefeuille.

    **(9) Pourquoi ce choix.** Le décalage entier se lit sans convention
    supplémentaire, et il reproduit exactement la contrainte d'exploitation
    d'une stratégie à la clôture.

    **(10) Comment vérifier.** Sur une métrique construite comme
    :math:`m(h) = m_0 \, \rho^{\,h}`, la rétention rendue vaut exactement
    :math:`\rho^{\,h}`, identité que le test emploie.

    Args:
        evaluate_fn: reçoit le décalage en périodes et rend la métrique.
        delays: les décalages à essayer, strictement croissants et positifs ou nuls.
        retention_threshold: la part de la métrique de référence en dessous de
            laquelle le signal est déclaré non exploitable. Précepte déclaré.

    Returns:
        Un tableau, colonnes ``delay``, ``metric``, ``decay``, ``retention``
        et ``survives``.

    Raises:
        ConfigError: décalages vides, non croissants ou négatifs.
        DataQualityError: si une métrique rendue n'est pas finie.
    """
    horizons = [int(h) for h in delays]
    if not horizons:
        raise ConfigError("aucun décalage à essayer")
    if any(a >= b for a, b in itertools.pairwise(horizons)):
        raise ConfigError("les décalages doivent être strictement croissants")
    if horizons[0] < 0:
        raise ConfigError("les décalages doivent être positifs ou nuls")

    metriques: list[float] = []
    for h in horizons:
        valeur = float(evaluate_fn(h))
        if not math.isfinite(valeur):
            raise DataQualityError(f"la métrique au décalage {h} n'est pas finie")
        metriques.append(valeur)

    reference = metriques[0]
    utilisable = reference > DEFAULT_ZERO_TOLERANCE
    retention = [m / reference if utilisable else float("nan") for m in metriques]
    return pd.DataFrame(
        {
            "delay": horizons,
            "metric": metriques,
            "decay": [m - reference for m in metriques],
            "retention": retention,
            "survives": [bool(r >= retention_threshold) if math.isfinite(r) else False for r in retention],
        }
    )


# --------------------------------------------------------------------------- #
# Le rapport
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True, eq=False)
class RobustnessReport:
    """Le dossier de robustesse d'une étude, ses six pièces réunies.

    Chaque pièce est facultative, parce qu'une étude peut légitimement s'arrêter
    avant. Ce qui n'est pas facultatif est l'étiquette d'échantillon et la base
    de coût : la règle 5 du ``CLAUDE.md`` interdit de publier un chiffre de
    performance sans elles.

    L'égalité automatique est retirée pour la même raison que dans
    :class:`CostAnalysis`.

    Attributes:
        sample: l'échantillon d'où sortent tous les chiffres du rapport.
        cost_basis: brut ou net de frais.
        metric_col: le nom de la métrique balayée.
        sweep: le balayage complet, toutes combinaisons comprises.
        plateau: la ligne retenue par :func:`best_plateau`.
        sensitivity: le tableau des élasticités.
        subperiods: la performance par sous-période.
        costs: l'analyse des multiples de coût.
        delays: l'analyse des décalages d'exécution.
    """

    sample: SampleTag
    cost_basis: CostBasis
    metric_col: str = "metric"
    sweep: pd.DataFrame | None = None
    plateau: pd.Series | None = None
    sensitivity: pd.DataFrame | None = None
    subperiods: pd.DataFrame | None = None
    costs: CostAnalysis | None = None
    delays: pd.DataFrame | None = None

    @property
    def n_trials(self) -> int:
        """Le nombre de combinaisons évaluées, intrant du Sharpe dégonflé.

        Returns:
            La hauteur du balayage, ou zéro quand aucun balayage n'est joint.
        """
        return 0 if self.sweep is None else len(self.sweep)

    def to_frame(self) -> pd.DataFrame:
        """Rend un tableau lisible, une ligne par grandeur qui décide.

        Le tableau est long plutôt que large, pour que l'ajout d'une pièce
        n'oblige pas à changer les colonnes. La colonne ``value`` porte le
        nombre quand il en existe un, et la colonne ``detail`` porte ce qui ne
        se met pas en nombre.

        Returns:
            Un tableau à quatre colonnes : ``section``, ``quantity``, ``value``
            et ``detail``.
        """
        lignes: list[dict[str, Any]] = [
            {
                "section": "échantillon",
                "quantity": "étiquette",
                "value": float("nan"),
                "detail": f"{self.sample.value}, {self.cost_basis.value}",
            }
        ]
        if self.sweep is not None:
            echecs = 0
            if "error" in self.sweep.columns:
                echecs = int((self.sweep["error"].fillna("") != "").sum())
            lignes.append(
                {
                    "section": "balayage",
                    "quantity": "combinaisons évaluées",
                    "value": float(self.n_trials),
                    "detail": f"{echecs} en échec",
                }
            )
            if self.metric_col in self.sweep.columns:
                brut = self.sweep[self.metric_col].astype("float64")
                lignes.append(
                    {
                        "section": "balayage",
                        "quantity": "meilleure métrique brute",
                        "value": float(brut.max()),
                        "detail": "maximum de la grille, sans voisinage",
                    }
                )
        if self.plateau is not None:
            lignes.append(
                {
                    "section": "plateau",
                    "quantity": "score de plateau",
                    "value": float(self.plateau["plateau_score"]),
                    "detail": "médiane du voisinage, précepte",
                }
            )
            lignes.append(
                {
                    "section": "plateau",
                    "quantity": "métrique du point retenu",
                    "value": float(self.plateau[self.metric_col]),
                    "detail": "au sens du plateau, pas du maximum",
                }
            )
            lignes.append(
                {
                    "section": "plateau",
                    "quantity": "isolement",
                    "value": float(self.plateau["isolation"]),
                    "detail": "métrique moins score, proche de zéro sur un plateau",
                }
            )
        if self.sensitivity is not None and len(self.sensitivity) > 0:
            absolues = self.sensitivity["elasticity"].abs()
            if bool(absolues.notna().any()):
                rang = int(absolues.idxmax())
                lignes.append(
                    {
                        "section": "sensibilité",
                        "quantity": "élasticité la plus forte",
                        "value": float(self.sensitivity.loc[rang, "elasticity"]),
                        "detail": str(self.sensitivity.loc[rang, "parameter"]),
                    }
                )
        if self.subperiods is not None and len(self.subperiods) > 0:
            pire = int(self.subperiods["sharpe"].idxmin())
            positives = float((self.subperiods["sharpe"] > 0).mean())
            lignes.append(
                {
                    "section": "sous-périodes",
                    "quantity": "pire ratio de Sharpe",
                    "value": float(self.subperiods.loc[pire, "sharpe"]),
                    "detail": str(self.subperiods.loc[pire, "label"]),
                }
            )
            lignes.append(
                {
                    "section": "sous-périodes",
                    "quantity": "part de sous-périodes positives",
                    "value": positives,
                    "detail": f"{len(self.subperiods)} tranches",
                }
            )
        if self.costs is not None:
            lignes.append(
                {
                    "section": "coûts",
                    "quantity": "multiple de rupture",
                    "value": float("nan")
                    if self.costs.breakeven_multiplier is None
                    else float(self.costs.breakeven_multiplier),
                    "detail": self.costs.status,
                }
            )
        if self.delays is not None and len(self.delays) > 0:
            dernier = self.delays.iloc[-1]
            lignes.append(
                {
                    "section": "délai",
                    "quantity": "rétention au plus grand décalage",
                    "value": float(dernier["retention"]),
                    "detail": f"décalage de {int(dernier['delay'])} périodes",
                }
            )
        return pd.DataFrame.from_records(lignes)

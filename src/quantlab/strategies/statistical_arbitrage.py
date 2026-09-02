r"""L'arbitrage statistique par composantes principales, et le résidu qu'il négocie.

**Le problème.** Deux actions du même secteur bougent ensemble, et l'écart entre
elles revient parfois à sa moyenne. Le pairs trading exploite cet écart deux à
deux. Avellaneda et Lee (2010) remplacent la seconde action par un portefeuille
de facteurs extraits de la matrice de corrélation, ce qui donne un résidu par
titre au lieu d'un écart par paire.

**Le remède.** Ce module sépare cinq objets que l'article mélange dans une seule
chaîne. Les portefeuilles propres vivent dans :func:`eigen_portfolios`. Le
modèle de retour à la moyenne vit dans :func:`ornstein_uhlenbeck_fit`. Le
s-score vit dans :func:`s_scores`. La règle tout ou rien vit dans
:func:`update_positions`. La couverture par les facteurs vit dans
:func:`hedged_dollar_weights`. La chaîne complète est
:func:`statistical_arbitrage_weights`, qui ne fait que les enchaîner.

**La règle de causalité.** Toute grandeur datée du jour :math:`t` n'emploie que
les rendements des jours :math:`t` et antérieurs. Aucune statistique n'est
calculée sur l'échantillon entier, ni la volatilité qui pondère les
portefeuilles propres, ni la moyenne en travers des titres du s-score. La
détention se décale d'un jour dans le moteur de backtest, jamais ici.

**Le biais du survivant.** :data:`SURVIVORSHIP_BIAS_RISK` vaut vrai. Un univers
choisi aujourd'hui retire les titres dont l'écart ne s'est jamais refermé, qui
sont précisément ceux que la stratégie aurait perdus. Ce module ne peut pas
corriger ce biais, il l'affiche.

**Provenance.** Avellaneda, M. et Lee, J.-H. (2010), « Statistical arbitrage in
the US equities market », *Quantitative Finance* 10(7), 761-782. Deux critiques
sont retenues. Yeo et Papanicolaou (2017), *Risk and Decision Analysis* 6,
263-290, montrent que l'estimateur de la vitesse de rappel est biaisé.
Guijarro-Ordonez, Pelger et Zanotti (2021), arXiv:2106.04028, battent largement
le repère paramétrique par un modèle appris.

**Les limites.** Rien ici ne connaît les frais, qui vivent dans
:mod:`quantlab.execution.costs`. Rien ici ne calcule un ratio de Sharpe, qui
vit dans :mod:`quantlab.analytics.ratios`. Ce module rend des poids, et le
jugement se prend ailleurs.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from quantlab.analytics.regression import rolling_beta
from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.logging import get_logger
from quantlab.signals.standardize import scale_to_gross

__all__ = [
    "PAPER_CHARACTERISTIC_DAYS",
    "PAPER_RULE",
    "SURVIVORSHIP_BIAS_RISK",
    "TRADING_DAYS_PER_YEAR",
    "EigenDecomposition",
    "OrnsteinUhlenbeckFit",
    "StatisticalArbitrageResult",
    "TradingRule",
    "characteristic_time_days",
    "eigen_portfolios",
    "hedged_dollar_weights",
    "market_hedged_book",
    "mean_reversion_half_life",
    "ornstein_uhlenbeck_fit",
    "residual_regression",
    "s_scores",
    "statistical_arbitrage_weights",
    "update_positions",
]

_LOG = get_logger(__name__)

#: Vrai, et non négociable pour cette famille de stratégies. L'univers est
#: choisi parmi les titres qui cotent encore, donc il exclut par construction
#: ceux dont l'écart ne s'est jamais refermé. Une étude qui emploie ce module
#: déclare ce risque et ne peut pas conclure au-delà de la réplication.
SURVIVORSHIP_BIAS_RISK: bool = True

#: Le nombre conventionnel de séances par an, celui qu'emploie l'article dans
#: ses formules d'annualisation de l'annexe A.
TRADING_DAYS_PER_YEAR: float = 252.0

#: Le temps caractéristique maximal accepté par l'article, en séances. Le filtre
#: s'écrit chez lui :math:`\kappa > 252/30`, ce qui est la même condition.
PAPER_CHARACTERISTIC_DAYS: float = 30.0

#: Le plancher de variance sous lequel un résidu est déclaré dégénéré. Une
#: variance nulle rendrait un s-score infini, et la division ne lèverait pas.
_VARIANCE_FLOOR: float = 1e-18


@dataclass(frozen=True)
class TradingRule:
    """Les quatre seuils de la règle tout ou tien du s-score.

    **Le problème.** Les quatre seuils de l'équation (16) de l'article ne sont
    pas symétriques, et les confondre change le nombre de passages. L'article
    ouvre à 1,25 des deux côtés, ferme une vente sous 0,75 et une position
    acheteuse au-dessus de -0,50.

    **La convention de signe.** Les quatre attributs sont des nombres positifs,
    et le signe vit dans la comparaison. Un s-score très négatif dit que le
    résidu est bas, donc que le titre est bon marché face à ses facteurs, donc
    qu'il s'achète.

    **Les limites.** La règle est sans mémoire du temps passé en position. Une
    position dont le s-score ne revient jamais reste ouverte tant que le filtre
    de vitesse la tolère, et c'est ce filtre qui la ferme.

    Attributes:
        name: le nom court de la variante, employé dans les tableaux publiés.
        open_long: seuil d'achat, la position s'ouvre quand ``s < -open_long``.
        open_short: seuil de vente, la position s'ouvre quand ``s > open_short``.
        close_long: seuil de sortie d'un achat, quand ``s > -close_long``.
        close_short: seuil de sortie d'une vente, quand ``s < close_short``.
    """

    name: str
    open_long: float = 1.25
    open_short: float = 1.25
    close_long: float = 0.50
    close_short: float = 0.75

    def __post_init__(self) -> None:
        """Refuse un nom vide et un seuil de sortie au-delà du seuil d'entrée."""
        if not self.name.strip():
            raise ConfigError("une règle de négociation porte un nom non vide.")
        for label, value in (
            ("open_long", self.open_long),
            ("open_short", self.open_short),
            ("close_long", self.close_long),
            ("close_short", self.close_short),
        ):
            if not math.isfinite(value) or value < 0.0:
                raise ConfigError(f"seuil {label} invalide dans « {self.name} » : {value}.")
        if self.close_long > self.open_long:
            raise ConfigError(
                f"« {self.name} » ferme l'achat à -{self.close_long} et l'ouvre à "
                f"-{self.open_long} : la position se fermerait le jour même de son ouverture."
            )
        if self.close_short > self.open_short:
            raise ConfigError(
                f"« {self.name} » ferme la vente à {self.close_short} et l'ouvre à "
                f"{self.open_short} : la position se fermerait le jour même de son ouverture."
            )


#: La règle calibrée par l'article, page 770, sur une fenêtre de simulation qui
#: est incluse dans les périodes dont il publie la performance.
PAPER_RULE: TradingRule = TradingRule(name="article")


@dataclass(frozen=True)
class EigenDecomposition:
    """La décomposition retenue d'une matrice de corrélation.

    Attributes:
        eigenvalues: les valeurs propres retenues, par ordre décroissant.
        eigenvectors: la matrice des vecteurs propres retenus, un par colonne.
        weights: les poids des portefeuilles propres, une ligne par facteur.
        variance_share: la part de la trace portée par les valeurs retenues.
        n_components: le nombre de facteurs retenus.
    """

    eigenvalues: np.ndarray
    eigenvectors: np.ndarray
    weights: np.ndarray
    variance_share: float
    n_components: int


@dataclass(frozen=True)
class OrnsteinUhlenbeckFit:
    """Les paramètres du processus de retour à la moyenne, titre par titre.

    Chaque attribut est un tableau d'une valeur par titre, dans l'ordre des
    colonnes fournies. Les titres non stationnaires portent ``nan`` partout sauf
    dans ``ar1_slope`` et ``stationary``, qui disent pourquoi.

    Attributes:
        intercept: l'ordonnée à l'origine de l'autorégression, notée *a*.
        ar1_slope: la pente de l'autorégression, notée *b*.
        kappa: la vitesse de rappel annualisée.
        equilibrium: le niveau d'équilibre du résidu cumulé, noté *m*.
        sigma: la volatilité instantanée du bruit.
        sigma_eq: l'écart type d'équilibre du résidu cumulé.
        residual_variance: la variance des résidus de l'autorégression.
        stationary: vrai quand la pente tient dans l'intervalle ouvert zéro un.
    """

    intercept: np.ndarray
    ar1_slope: np.ndarray
    kappa: np.ndarray
    equilibrium: np.ndarray
    sigma: np.ndarray
    sigma_eq: np.ndarray
    residual_variance: np.ndarray
    stationary: np.ndarray


@dataclass(frozen=True)
class StatisticalArbitrageResult:
    """Tout ce que la chaîne quotidienne produit, poids compris.

    Attributes:
        weights: un tableau de poids cibles par règle de négociation. Une ligne
            entièrement manquante marque un jour sans décision, que le moteur de
            backtest lit comme un jour sans transaction.
        s_score: le s-score de chaque titre à chaque date de décision.
        characteristic_days: le temps caractéristique de rappel, en séances.
        equilibrium_volatility: l'écart type d'équilibre du résidu cumulé.
        drift: la dérive annualisée du titre face à ses facteurs, notée alpha.
        eligible: vrai quand le titre passe le filtre de vitesse à cette date.
        membership: vrai quand le titre appartient à l'univers à cette date.
        positions: la position par titre et par date, valant plus un, moins
            un ou zéro, une entrée par règle. C'est le livre tout ou rien de
            l'article, avant couverture et avant mise à l'échelle.
        n_positions: le nombre de positions ouvertes, par règle et par date.
        n_factors: le nombre de facteurs retenus à chaque date.
        variance_share: la part de variance portée par ces facteurs.
        n_members: la taille de l'univers à chaque date.
    """

    weights: dict[str, pd.DataFrame]
    s_score: pd.DataFrame
    characteristic_days: pd.DataFrame
    equilibrium_volatility: pd.DataFrame
    drift: pd.DataFrame
    eligible: pd.DataFrame
    membership: pd.DataFrame
    positions: dict[str, pd.DataFrame]
    n_positions: pd.DataFrame
    n_factors: pd.Series
    variance_share: pd.Series
    n_members: pd.Series
    diagnostics: dict[str, float] = field(default_factory=dict)


def mean_reversion_half_life(
    kappa: np.ndarray | float, *, periods_per_year: float = TRADING_DAYS_PER_YEAR
) -> np.ndarray | float:
    r"""Rend la demi-vie du retour à la moyenne, en périodes.

    **Le problème.** La vitesse de rappel :math:`\kappa` est un nombre par an
    dont personne n'a l'intuition. La demi-vie est le temps qu'il faut à un
    écart pour se réduire de moitié, et elle se compare directement à la fenêtre
    d'estimation.

    **L'intuition.** L'espérance du processus décroît vers son équilibre comme
    une exponentielle de taux :math:`\kappa`. Le temps qui divise l'écart par
    deux est donc celui qui annule le logarithme de deux.

    **La formule.**

    .. math::  h = \frac{\ln 2}{\kappa} \times N

    **Les variables.** :math:`\kappa` est la vitesse de rappel annualisée,
    :math:`N` le nombre de périodes par an, :math:`h` la demi-vie en périodes.

    **Les hypothèses.** Le processus est un Ornstein-Uhlenbeck à paramètres
    constants sur la fenêtre. La vitesse est strictement positive, sans quoi le
    processus ne revient pas et la demi-vie n'existe pas.

    **Les limites.** La demi-vie ne dit rien de la dispersion autour de
    l'équilibre, qui est l'autre moitié du signal. Un résidu qui revient vite
    mais dont l'amplitude est nulle ne rapporte rien.

    **Une alternative écartée.** Le temps caractéristique :math:`1/\kappa` est
    ce que l'article emploie, et :func:`characteristic_time_days` le rend. Les
    deux diffèrent du facteur :math:`\ln 2`, et les confondre déplace le filtre
    de vitesse de 44 pour cent.

    **La provenance.** Uhlenbeck, G. E. et Ornstein, L. S. (1930), *Physical
    Review* 36, 823-841. Statut de cette référence : rapportée, non revérifiée
    au texte ici.

    **Comment vérifier l'implémentation.** Une vitesse égale au logarithme de
    deux rend une demi-vie d'exactement une année, donc de 252 séances.

    Args:
        kappa: la vitesse de rappel annualisée, un nombre ou un tableau.
        periods_per_year: le nombre de périodes par an.

    Returns:
        La demi-vie, dans l'unité de ``periods_per_year``. Vaut ``nan`` là où la
        vitesse n'est pas strictement positive.
    """
    values = np.asarray(kappa, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(values > 0.0, math.log(2.0) / values * periods_per_year, np.nan)
    return float(out) if out.ndim == 0 else out


def characteristic_time_days(
    kappa: np.ndarray | float, *, periods_per_year: float = TRADING_DAYS_PER_YEAR
) -> np.ndarray | float:
    r"""Rend le temps caractéristique de rappel, en périodes.

    **Le problème.** Le filtre de l'article s'écrit :math:`\kappa > 252/30`, ce
    qui est une condition sur un nombre par an. La lire en séances la rend
    vérifiable à la main.

    **La formule.**

    .. math::  \tau = \frac{N}{\kappa}

    **Les variables.** :math:`\kappa` est la vitesse annualisée, :math:`N` le
    nombre de périodes par an, :math:`\tau` le temps caractéristique.

    **L'intuition.** C'est le temps au bout duquel un écart est divisé par le
    nombre d'Euler, soit une réduction de 63 pour cent.

    **Les hypothèses et les limites.** Les mêmes que pour
    :func:`mean_reversion_half_life`, dont cette fonction est le cousin sans le
    facteur :math:`\ln 2`.

    **Une alternative écartée.** La demi-vie est plus lisible, mais elle ne
    correspond pas au seuil publié, et l'étude doit reproduire le seuil publié.

    **La provenance.** Avellaneda et Lee (2010), page 771, qui posent
    :math:`\tau_i = 1/\kappa_i` puis le seuil de trente séances.

    **Comment vérifier l'implémentation.** Une vitesse de 8,4 par an rend
    exactement trente séances, ce qui est le seuil de l'article.

    Args:
        kappa: la vitesse de rappel annualisée, un nombre ou un tableau.
        periods_per_year: le nombre de périodes par an.

    Returns:
        Le temps caractéristique, en périodes. Vaut ``nan`` là où la vitesse
        n'est pas strictement positive.
    """
    values = np.asarray(kappa, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(values > 0.0, periods_per_year / values, np.nan)
    return float(out) if out.ndim == 0 else out


def eigen_portfolios(
    window_returns: np.ndarray,
    *,
    n_components: int | None = None,
    variance_share: float | None = None,
) -> EigenDecomposition:
    r"""Rend les portefeuilles propres d'une fenêtre de rendements.

    **Le problème.** Le retour à la moyenne n'a de sens que sur un résidu. Il
    faut donc d'abord retirer ce qui bouge en commun, et l'article le fait sans
    modèle de facteurs imposé, en lisant les modes propres de la matrice de
    corrélation empirique.

    **L'intuition.** La première composante est le mouvement du marché entier,
    la deuxième oppose des groupes de titres, et ainsi de suite. Chaque
    composante donne un portefeuille, et ces portefeuilles remplacent les
    indices sectoriels du pairs trading classique.

    **La formule.** Sur la fenêtre de :math:`T` séances et :math:`N` titres, la
    matrice de corrélation :math:`\rho` se diagonalise. Le portefeuille propre
    :math:`j` investit dans le titre :math:`i` le montant

    .. math::  Q_{j,i} = \frac{v^{(j)}_i}{\sigma_i}

    où :math:`v^{(j)}` est le vecteur propre de rang :math:`j` et
    :math:`\sigma_i` l'écart type du titre :math:`i` sur la fenêtre. Le
    rendement du facteur vaut :math:`F_{j,t} = \sum_i Q_{j,i} R_{i,t}`.

    **Les variables.** :math:`R` est la matrice des rendements de la fenêtre,
    :math:`\rho` leur matrice de corrélation, :math:`v^{(j)}` le vecteur propre
    associé à la :math:`j`-ième plus grande valeur propre.

    **Les hypothèses.** Les rendements de la fenêtre sont de loi stable, et la
    corrélation empirique estime la corrélation vraie. La seconde hypothèse est
    la plus fragile : avec 252 séances et deux cents titres, il y a plus de
    coefficients à estimer que de points pour les estimer.

    **Les limites.** La division par la volatilité donne au portefeuille propre
    un poids en dollars, pas en parts. Sa somme n'est ni un ni zéro, et
    l'échelle est absorbée par les bêtas de la régression aval.

    **Une alternative écartée.** La théorie des matrices aléatoires nettoie le
    spectre avant d'en garder le haut, ce que Laloux et coauteurs (2000)
    proposent. L'article la cite et ne l'applique pas, donc ce module ne
    l'applique pas non plus.

    **La provenance.** Avellaneda et Lee (2010), section 3, pages 764 à 767.

    **Comment vérifier l'implémentation.** Sur deux titres de corrélation
    :math:`\rho`, les valeurs propres valent exactement :math:`1+\rho` et
    :math:`1-\rho`, et le premier vecteur propre est la diagonale. Le test du
    module le vérifie sur un cas construit.

    Args:
        window_returns: la fenêtre de rendements, une ligne par séance et une
            colonne par titre, sans valeur manquante.
        n_components: le nombre fixe de facteurs à retenir.
        variance_share: la part de la trace à atteindre, entre zéro et un. Un
            seul des deux arguments se donne.

    Returns:
        La décomposition retenue.

    Raises:
        ConfigError: si les deux critères sont donnés, ou aucun, ou si
            ``variance_share`` sort de l'intervalle unité.
        InsufficientDataError: si la fenêtre porte moins de deux titres ou moins
            de séances que de titres plus un.
        DataQualityError: si la fenêtre porte une valeur manquante ou un titre
            de variance nulle.
    """
    if (n_components is None) == (variance_share is None):
        raise ConfigError(
            "eigen_portfolios prend exactement un critère : « n_components » ou « variance_share »."
        )
    matrix = np.asarray(window_returns, dtype=float)
    if matrix.ndim != 2:
        raise ConfigError(f"window_returns doit être une matrice à deux dimensions, reçu {matrix.ndim}.")
    n_obs, n_assets = matrix.shape
    if n_assets < 2:
        raise InsufficientDataError(f"{n_assets} titre(s) dans la fenêtre, il en faut au moins deux.")
    if n_obs < 3:
        raise InsufficientDataError(f"{n_obs} séance(s) dans la fenêtre, il en faut au moins trois.")
    if not np.isfinite(matrix).all():
        raise DataQualityError("la fenêtre de rendements porte une valeur manquante ou infinie.")

    volatilities = matrix.std(axis=0, ddof=1)
    if bool((volatilities <= 0.0).any()):
        raise DataQualityError("un titre de la fenêtre a une volatilité nulle, sa corrélation n'existe pas.")
    standardized = (matrix - matrix.mean(axis=0)) / volatilities
    correlation = standardized.T @ standardized / (n_obs - 1)
    values, vectors = np.linalg.eigh(correlation)
    order = np.argsort(values)[::-1]
    values = values[order]
    vectors = vectors[:, order]

    trace = float(values.sum())
    if variance_share is not None:
        if not 0.0 < variance_share <= 1.0:
            raise ConfigError(f"variance_share doit tenir dans l'intervalle unité, reçu {variance_share}.")
        cumulative = np.cumsum(np.clip(values, 0.0, None)) / trace
        kept = int(np.searchsorted(cumulative, variance_share) + 1)
        kept = min(kept, n_assets)
    else:
        kept = int(n_components)  # type: ignore[arg-type]
        if kept < 1:
            raise ConfigError(f"n_components doit valoir au moins un, reçu {kept}.")
        kept = min(kept, n_assets)

    retained_values = values[:kept]
    retained_vectors = vectors[:, :kept]
    weights = (retained_vectors / volatilities[:, None]).T
    return EigenDecomposition(
        eigenvalues=retained_values,
        eigenvectors=retained_vectors,
        weights=weights,
        variance_share=float(np.clip(retained_values, 0.0, None).sum() / trace),
        n_components=kept,
    )


def residual_regression(
    window_returns: np.ndarray, factor_returns: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    r"""Régresse chaque titre sur les facteurs et rend le résidu cumulé.

    **Le problème.** Le rendement d'un titre porte une partie commune et une
    partie propre. Seule la seconde peut revenir à une moyenne, et il faut la
    séparer sur une fenêtre courte, choisie par l'article à soixante séances
    parce que c'est la durée d'un cycle de publication de résultats.

    **L'intuition.** Une régression par titre donne le résidu quotidien. La
    somme cumulée de ces résidus est la trajectoire de l'écart, et c'est elle
    qui se modélise.

    **La formule.** Pour le titre :math:`i` et la séance :math:`k` de la
    fenêtre,

    .. math::

        R_{i,k} = \beta_{i,0} + \sum_{j=1}^{M} \beta_{i,j} F_{j,k} + \epsilon_{i,k},
        \qquad
        X_{i,k} = \sum_{l=1}^{k} \epsilon_{i,l}

    La dérive annualisée vaut :math:`\alpha_i = \beta_{i,0} \times 252`.

    **Les variables.** :math:`R` est la matrice des rendements de la fenêtre,
    :math:`F` celle des rendements de facteurs, :math:`\beta_{i,0}` l'ordonnée à
    l'origine, :math:`X` le résidu cumulé.

    **Les hypothèses.** Les bêtas sont constants sur la fenêtre, et les facteurs
    sont exogènes. La seconde est fausse par construction, les facteurs étant
    des combinaisons des titres régressés, et l'article ne s'en émeut pas.

    **Les limites, et c'est le piège de l'article.** La régression force la
    somme des résidus à zéro, donc :math:`X_{i,T} = 0` par construction. Le
    résidu cumulé ne finit jamais loin de zéro, et le s-score qui en découle
    n'est pas celui de sa définition théorique. L'annexe A de l'article le dit,
    et :func:`s_scores` en tire la conséquence.

    **Une alternative écartée.** Estimer les bêtas sur une fenêtre longue et les
    résidus sur une fenêtre courte lèverait l'artefact, au prix d'un écart avec
    l'article que la réplication doit d'abord mesurer.

    **La provenance.** Avellaneda et Lee (2010), section 4 et annexe A.

    **Comment vérifier l'implémentation.** Sur des rendements engendrés comme
    combinaison exacte des facteurs, le résidu est nul à la précision machine et
    le résidu cumulé aussi.

    Args:
        window_returns: la fenêtre de rendements, séances en lignes.
        factor_returns: les rendements des facteurs, mêmes séances en lignes.

    Returns:
        Le triplet formé des bêtas hors ordonnée à l'origine, une ligne par
        titre, des dérives annualisées, et des résidus cumulés.

    Raises:
        ConfigError: si les deux matrices n'ont pas le même nombre de lignes.
    """
    returns = np.asarray(window_returns, dtype=float)
    factors = np.asarray(factor_returns, dtype=float)
    if returns.shape[0] != factors.shape[0]:
        raise ConfigError(f"{returns.shape[0]} séances de rendements contre {factors.shape[0]} de facteurs.")
    design = np.column_stack([np.ones(returns.shape[0]), factors])
    coefficients, *_ = np.linalg.lstsq(design, returns, rcond=None)
    residuals = returns - design @ coefficients
    betas = coefficients[1:, :].T
    drift = coefficients[0, :] * TRADING_DAYS_PER_YEAR
    return betas, drift, np.cumsum(residuals, axis=0)


def ornstein_uhlenbeck_fit(
    cumulative_residuals: np.ndarray, *, periods_per_year: float = TRADING_DAYS_PER_YEAR
) -> OrnsteinUhlenbeckFit:
    r"""Estime le processus de retour à la moyenne par une autorégression d'ordre un.

    **Le problème.** Le résidu cumulé est une trajectoire. Pour en tirer un
    signal, il faut savoir à quelle vitesse il revient et de combien il s'écarte
    en régime, donc estimer quatre nombres par titre sur soixante points.

    **L'intuition.** La solution exacte du processus en temps continu, échantillonnée
    à pas constant, est exactement une autorégression d'ordre un. Estimer
    l'autorégression revient donc à estimer le processus, sans approximation de
    discrétisation.

    **La formule.** L'autorégression :math:`X_{n+1} = a + b X_n + \zeta_{n+1}`
    s'identifie au processus par

    .. math::

        \kappa = -\ln(b) \times N, \qquad
        m = \frac{a}{1-b}, \qquad
        \sigma = \sqrt{\frac{\mathrm{Var}(\zeta)\, 2\kappa}{1-b^{2}}}, \qquad
        \sigma_{eq} = \sqrt{\frac{\mathrm{Var}(\zeta)}{1-b^{2}}}

    **Les variables.** :math:`b` est la pente de l'autorégression, :math:`a` son
    ordonnée à l'origine, :math:`\kappa` la vitesse de rappel annualisée,
    :math:`m` le niveau d'équilibre, :math:`\sigma_{eq}` l'écart type
    d'équilibre, :math:`N` le nombre de périodes par an.

    **Les hypothèses.** Les paramètres sont constants sur la fenêtre. Le bruit
    est gaussien et indépendant. La seconde hypothèse est contredite par les
    faits stylisés des rendements, et Krauss (2017) le rappelle pour toute cette
    famille de modèles.

    **Les limites.** L'estimateur de :math:`b` par les moindres carrés est
    biaisé vers le bas sur un échantillon court, donc :math:`\kappa` est biaisé
    vers le haut. Yeo et Papanicolaou (2017) le notent, et le biais joue sur le
    filtre de vitesse autant que sur le dénominateur du s-score.

    **Une alternative écartée.** Le maximum de vraisemblance exact du processus
    donne le même estimateur à l'ordre principal, pour un coût plus élevé, et
    les mêmes auteurs le disent également biaisé.

    **La provenance.** Avellaneda et Lee (2010), annexe A, pages 781 et 782.

    **Comment vérifier l'implémentation.** Une trajectoire construite à la main
    avec :math:`a = 0{,}2` et :math:`b = 0{,}5` rend exactement ces deux
    nombres, donc un équilibre de 0,4 et une vitesse de
    :math:`-\ln(0{,}5)\times 252`.

    Args:
        cumulative_residuals: les résidus cumulés, une ligne par séance et une
            colonne par titre.
        periods_per_year: le nombre de périodes par an.

    Returns:
        Les paramètres estimés, un tableau par grandeur.

    Raises:
        InsufficientDataError: si la fenêtre porte moins de quatre points.
    """
    values = np.asarray(cumulative_residuals, dtype=float)
    if values.ndim == 1:
        values = values[:, None]
    if values.shape[0] < 4:
        raise InsufficientDataError(
            f"{values.shape[0]} points de résidu cumulé, il en faut au moins quatre pour "
            "estimer une autorégression et la variance de son bruit."
        )
    lagged = values[:-1, :]
    leading = values[1:, :]
    lagged_mean = lagged.mean(axis=0)
    leading_mean = leading.mean(axis=0)
    centred_lagged = lagged - lagged_mean
    centred_leading = leading - leading_mean
    denominator = (centred_lagged * centred_lagged).sum(axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        slope = np.where(
            denominator > 0.0, (centred_lagged * centred_leading).sum(axis=0) / denominator, np.nan
        )
    intercept = leading_mean - slope * lagged_mean
    noise = leading - intercept - slope * lagged
    residual_variance = noise.var(axis=0, ddof=1)

    stationary = np.isfinite(slope) & (slope > 0.0) & (slope < 1.0) & (residual_variance > _VARIANCE_FLOOR)
    with np.errstate(divide="ignore", invalid="ignore"):
        kappa = np.where(stationary, -np.log(np.where(stationary, slope, 0.5)) * periods_per_year, np.nan)
        equilibrium = np.where(stationary, intercept / (1.0 - slope), np.nan)
        variance_eq = np.where(stationary, residual_variance / (1.0 - slope**2), np.nan)
        sigma_eq = np.sqrt(variance_eq)
        sigma = np.sqrt(variance_eq * 2.0 * kappa)
    return OrnsteinUhlenbeckFit(
        intercept=intercept,
        ar1_slope=slope,
        kappa=kappa,
        equilibrium=equilibrium,
        sigma=sigma,
        sigma_eq=sigma_eq,
        residual_variance=residual_variance,
        stationary=stationary,
    )


def s_scores(
    fit: OrnsteinUhlenbeckFit,
    *,
    centre_across_names: bool = True,
    drift: np.ndarray | None = None,
) -> np.ndarray:
    r"""Rend le s-score de l'annexe A, et non celui de la définition théorique.

    **Le problème.** L'équation (15) de l'article définit le s-score comme la
    distance du résidu cumulé courant à son équilibre, en écarts types. Or ce
    résidu cumulé vaut zéro par construction à la dernière date de la fenêtre,
    puisque la régression y force la somme des résidus. La définition rendue
    telle quelle ne calcule donc pas ce que l'article négocie.

    **L'intuition.** Une fois le zéro imposé, la distance à l'équilibre se
    réduit à l'opposé de l'équilibre lui-même. Un titre dont l'équilibre est
    positif est un titre dont le résidu, actuellement à zéro, est bas face à son
    régime, donc un titre à acheter.

    **La formule, celle de l'équation (A2).**

    .. math::

        s_i = \frac{\langle m \rangle - m_i}{\sigma_{eq,i}}
        \qquad
        s^{mod}_i = s_i - \frac{\alpha_i}{\kappa_i\, \sigma_{eq,i}}

    où :math:`\langle m \rangle` est la moyenne des équilibres en travers des
    titres retenus à cette date.

    **Les variables.** :math:`m_i` est l'équilibre du titre :math:`i`,
    :math:`\sigma_{eq,i}` son écart type d'équilibre, :math:`\alpha_i` sa dérive
    annualisée, :math:`\kappa_i` sa vitesse de rappel.

    **Les hypothèses.** Le centrage en travers des titres suppose que la moyenne
    des équilibres mesure un décalage commun sans contenu, ce que l'article
    n'établit pas et que ce module reproduit par fidélité.

    **Les limites.** Le centrage rend le signal transversal, donc mécaniquement
    équilibré entre achats et ventes. Un mouvement commun à tout l'univers ne
    produit aucun signal, ce qui est voulu, mais interdit aussi de mesurer un
    retour à la moyenne du marché entier.

    **Une alternative écartée.** Le s-score sans centrage est disponible par
    ``centre_across_names=False``, et l'étude le compte comme un essai. L'article
    ne publie aucun rétrotest de cette variante.

    **La provenance.** Avellaneda et Lee (2010), équations (15) et (17), et
    annexe A, équation (A2), page 782.

    **Comment vérifier l'implémentation.** Avec deux titres d'équilibres 1 et 3
    et d'écarts types d'équilibre 1 et 2, la moyenne vaut 2, donc les s-scores
    valent exactement 1 et -0,5.

    Args:
        fit: les paramètres estimés du processus.
        centre_across_names: retirer la moyenne des équilibres en travers des
            titres, comme le fait l'équation (A2).
        drift: les dérives annualisées. Fournies, elles rendent le s-score
            modifié de l'équation (17).

    Returns:
        Le tableau des s-scores, ``nan`` pour les titres non stationnaires.
    """
    equilibrium = np.where(fit.stationary, fit.equilibrium, np.nan)
    sigma_eq = np.where(fit.stationary & (fit.sigma_eq > 0.0), fit.sigma_eq, np.nan)
    centre = 0.0
    if centre_across_names and bool(np.isfinite(equilibrium).any()):
        centre = float(np.nanmean(equilibrium))
    with np.errstate(divide="ignore", invalid="ignore"):
        score = (centre - equilibrium) / sigma_eq
        if drift is not None:
            kappa = np.where(fit.stationary, fit.kappa, np.nan)
            score = score - np.asarray(drift, dtype=float) / (kappa * sigma_eq)
    return score


def update_positions(
    previous: np.ndarray, s_score: np.ndarray, eligible: np.ndarray, rule: TradingRule
) -> np.ndarray:
    r"""Applique la règle tout ou rien du s-score, position par position.

    **Le problème.** Un signal continu se traduit en position de mille façons.
    L'article choisit la plus brutale : la position vaut plus un, moins un ou
    zéro, et elle ne s'ajuste jamais entre ces trois valeurs. Ce choix décide de
    la rotation, donc du verdict de coût.

    **L'intuition.** On entre quand l'écart est grand et on sort quand il s'est
    refermé, avec un seuil de sortie plus bas que le seuil d'entrée. Cet écart
    entre les deux seuils est ce qui empêche d'entrer et de sortir tous les
    jours autour d'un même niveau.

    **La règle, telle qu'écrite page 770.** Ouvrir un achat quand
    :math:`s < -1{,}25`. Ouvrir une vente quand :math:`s > 1{,}25`. Fermer un
    achat quand :math:`s > -0{,}50`. Fermer une vente quand :math:`s < 0{,}75`.

    **Les variables.** ``previous`` porte la position de la veille, ``s_score``
    le signal du jour, ``eligible`` le résultat du filtre de vitesse.

    **Les hypothèses.** L'ordre est exécuté en entier au prix retenu par le
    moteur de backtest. Aucune position n'est partiellement remplie.

    **Les limites.** La règle est asymétrique entre l'achat et la vente, et
    l'article ne justifie pas cette asymétrie autrement que par une simulation
    de calibrage menée sur une fenêtre incluse dans sa période de résultats.

    **Une alternative écartée.** Une position proportionnelle au s-score
    tournerait moins, ce que l'article ne teste pas. L'étude la compte comme un
    écart et non comme une réplication, donc elle reste hors de ce module.

    **La provenance.** Avellaneda et Lee (2010), équation (16) et le paragraphe
    qui la suit, page 770.

    **Comment vérifier l'implémentation.** Un titre sans position et de s-score
    -1,30 devient acheteur. Le lendemain, à -1,00, il le reste. Le surlendemain,
    à -0,40, il se ferme. Le test du module déroule cette table à la main.

    Args:
        previous: les positions de la veille, valeurs dans moins un, zéro, un.
        s_score: les s-scores du jour, ``nan`` autorisé.
        eligible: vrai quand le titre passe le filtre de vitesse.
        rule: les quatre seuils.

    Returns:
        Les nouvelles positions, du même type que ``previous``.
    """
    scores = np.asarray(s_score, dtype=float)
    tradable = np.asarray(eligible, dtype=bool) & np.isfinite(scores)
    positions = np.where(tradable, np.asarray(previous, dtype=float), 0.0)

    close_long = (positions > 0.0) & (scores > -rule.close_long)
    close_short = (positions < 0.0) & (scores < rule.close_short)
    positions = np.where(close_long | close_short, 0.0, positions)

    flat = positions == 0.0
    positions = np.where(flat & tradable & (scores < -rule.open_long), 1.0, positions)
    positions = np.where(flat & tradable & (scores > rule.open_short), -1.0, positions)
    return positions


def hedged_dollar_weights(
    positions: np.ndarray,
    betas: np.ndarray,
    eigenportfolio_weights: np.ndarray,
    *,
    gross_leverage: float,
) -> np.ndarray:
    r"""Traduit des positions en poids par titre, couverture des facteurs comprise.

    **Le problème.** Acheter un dollar d'un titre expose au marché et à son
    secteur. L'article vend en face les portefeuilles de facteurs dans les
    proportions données par la régression, de sorte que seule la partie
    résiduelle reste détenue.

    **L'intuition.** Les portefeuilles de facteurs sont eux-mêmes faits des
    titres de l'univers. La couverture se replie donc sur l'espace des titres,
    et la position finale est un seul vecteur de poids, sans instrument
    supplémentaire.

    **La formule.** Avec :math:`q` le vecteur des positions, :math:`B` la
    matrice des bêtas et :math:`Q` celle des portefeuilles propres,

    .. math::

        \tilde{w} = q - Q^{\top} B^{\top} q,
        \qquad
        w = \frac{L\, \tilde{w}}{\sum_i \left| \tilde{w}_i \right|}

    **Les variables.** :math:`q_i` vaut plus un, moins un ou zéro, :math:`B` a
    un titre par ligne et un facteur par colonne, :math:`Q` un facteur par ligne
    et un titre par colonne, :math:`L` l'exposition brute visée.

    **Les hypothèses.** Les bêtas de la fenêtre valent encore demain, et les
    portefeuilles propres sont négociables au même prix que leurs composantes.

    **Les limites.** La normalisation à exposition brute constante rend le ratio
    de Sharpe indépendant du levier retenu, puisque les rendements sont
    proportionnels à :math:`L`. Le levier ne décide donc que du niveau de
    volatilité, jamais du classement des variantes.

    **Une alternative écartée.** L'article fixe un levier de deux plus deux,
    calibré par rétrotest sur 2002 à 2004, donc sur une fenêtre incluse dans sa
    période de résultats. La normalisation retenue ici évite ce calibrage, et
    l'écart est déclaré par l'étude.

    **La mise à l'échelle n'est pas réécrite ici.** Elle est déléguée à
    :func:`quantlab.signals.standardize.scale_to_gross`, seul endroit du paquet
    où une exposition brute se vise, règle 12 du ``CLAUDE.md``.

    **La provenance.** Avellaneda et Lee (2010), section 5, page 771, pour la
    couverture, et page 772 pour le levier.

    **Comment vérifier l'implémentation.** Un seul titre acheté, un seul facteur
    de bêta un dont le portefeuille propre est ce même titre, rend un poids
    exactement nul avant normalisation, ce qui est la couverture parfaite.

    Args:
        positions: les positions par titre, valeurs dans moins un, zéro, un.
        betas: les bêtas, un titre par ligne et un facteur par colonne.
        eigenportfolio_weights: les portefeuilles propres, un facteur par ligne.
        gross_leverage: l'exposition brute visée, strictement positive.

    Returns:
        Les poids par titre. Tous nuls quand aucune position n'est ouverte.

    Raises:
        ConfigError: si le levier n'est pas strictement positif ou si les
            dimensions ne s'accordent pas.
    """
    if not math.isfinite(gross_leverage) or gross_leverage <= 0.0:
        raise ConfigError(f"gross_leverage doit être strictement positif, reçu {gross_leverage}.")
    q = np.asarray(positions, dtype=float)
    b = np.asarray(betas, dtype=float)
    factor_weights = np.asarray(eigenportfolio_weights, dtype=float)
    if b.shape[0] != q.shape[0]:
        raise ConfigError(f"{b.shape[0]} lignes de bêtas contre {q.shape[0]} positions.")
    if b.shape[1] != factor_weights.shape[0]:
        raise ConfigError(
            f"{b.shape[1]} colonnes de bêtas contre {factor_weights.shape[0]} portefeuilles propres."
        )
    raw = q - factor_weights.T @ (b.T @ q)
    if float(np.abs(raw).sum()) <= 0.0:
        return np.zeros_like(raw)
    return scale_to_gross(pd.Series(raw), gross_leverage).to_numpy()


def market_hedged_book(
    positions: pd.DataFrame,
    returns: pd.DataFrame,
    market: pd.Series,
    *,
    window: int,
    benchmark: str,
) -> pd.DataFrame:
    r"""Rend le livre de l'article : actions tout ou rien, couverture par le seul repère.

    **Le problème.** La couverture de :func:`hedged_dollar_weights` replie les
    portefeuilles propres sur les titres, donc elle négocie la jambe de
    facteurs. L'article ne la négocie pas quand les facteurs viennent d'une
    analyse en composantes principales.

    **Ce que l'article écrit.** Les portefeuilles propres ne sont pas des
    instruments cotés. Les auteurs négocient donc les seules actions du signal,
    puis achètent ou vendent le fonds indiciel du marché de façon à annuler le
    bêta d'ensemble, sections 5.1 et 5.3, page 771 et page 772.

    **La formule.** Avec :math:`q_i` la position tout ou rien du titre
    :math:`i` et :math:`\beta_i` son bêta au repère,

    .. math::

        w_i = q_i, \qquad w_{repère} = - \sum_i q_i \beta_i

    **Les variables.** Le bêta se lit sur une fenêtre glissante de ``window``
    séances, donc il n'emploie que le passé. La colonne ``benchmark`` est
    ajoutée au livre, et elle n'existe pas dans ``positions``.

    **L'échelle ne change rien.** Multiplier tout le livre par une constante
    multiplie le rendement, le coût et la rotation par la même constante. Le
    ratio de Sharpe et le coût de seuil de rentabilité n'en dépendent donc pas,
    et aucun levier n'est visé ici.

    **Les limites.** Le bêta glissant est estimé, donc la neutralité au marché
    est approchée et non exacte. Le repère est supposé négociable au même coût
    que les actions, ce qui flatte légèrement la couverture.

    **La provenance.** Avellaneda et Lee (2010), section 5.1 pour la couverture
    par le fonds indiciel et section 5.3 pour son emploi avec les composantes
    principales. Leur équation de compte de résultat, page 771, ne porte que des
    positions en actions.

    **Comment vérifier l'implémentation.** Un titre de bêta un, acheté seul,
    rend une jambe de repère égale à moins un. Un test du module l'exige.

    Args:
        positions: le livre tout ou rien, une colonne par titre, valeurs dans
            moins un, zéro, un. Une ligne entièrement manquante marque un jour
            sans décision.
        returns: les rendements des titres, mêmes colonnes que ``positions``.
        market: les rendements du repère de marché.
        window: la fenêtre du bêta glissant, en séances.
        benchmark: le nom de la colonne de repère à créer.

    Returns:
        Le livre complet, les titres puis la colonne de repère.

    Raises:
        ConfigError: si le repère porte déjà une colonne dans ``positions``, ou
            si les colonnes des deux tableaux ne coïncident pas.
        DataQualityError: si une position ouverte tombe sur un bêta manquant.
    """
    if benchmark in positions.columns:
        raise ConfigError(f"le repère {benchmark} est déjà une colonne du livre.")
    if list(positions.columns) != list(returns.columns):
        raise ConfigError("positions et returns ne portent pas les mêmes colonnes.")
    betas = pd.DataFrame(
        {
            name: rolling_beta(returns[name], market, window, min_periods=window).reindex(positions.index)
            for name in positions.columns
        },
        index=positions.index,
    )
    ouvertes = positions.fillna(0.0) != 0.0
    if bool((ouvertes & betas.isna()).to_numpy().any()):
        raise DataQualityError("une position ouverte tombe sur un bêta glissant manquant.")
    decide = positions.notna().any(axis=1)
    couverture = -(positions * betas).sum(axis=1, skipna=True)
    book = positions.copy()
    book[benchmark] = couverture.where(decide)
    return book


def _rolling_membership(valid: np.ndarray, window: int) -> np.ndarray:
    """Rend le masque des titres ayant ``window`` rendements valides consécutifs."""
    counts = pd.DataFrame(valid.astype(float)).rolling(window).sum().to_numpy()
    return counts == float(window)


def statistical_arbitrage_weights(
    returns: pd.DataFrame,
    *,
    rules: Sequence[TradingRule],
    correlation_window: int = 252,
    estimation_window: int = 60,
    n_components: int | None = 15,
    variance_share: float | None = None,
    max_characteristic_days: float | None = PAPER_CHARACTERISTIC_DAYS,
    gross_leverage: float = 4.0,
    reestimation_days: int = 1,
    hedge_at_entry: bool = True,
    centre_across_names: bool = True,
    use_modified_s_score: bool = False,
    tradable: pd.DataFrame | None = None,
    min_names: int = 30,
    periods_per_year: float = TRADING_DAYS_PER_YEAR,
) -> StatisticalArbitrageResult:
    r"""Déroule la chaîne quotidienne complète et rend les poids de décision.

    **Le problème.** Les huit étapes de l'article sont refaites chaque séance,
    et chacune peut lire l'avenir si elle est écrite distraitement. La chaîne
    vit donc en un seul endroit, où la fenêtre glissante est explicite.

    **L'intuition.** À chaque séance, on regarde en arrière et rien d'autre. Un
    an de rendements donne les facteurs, trois mois donnent les résidus, et le
    s-score du jour décide de la position du jour, détenue le lendemain.

    **Les huit étapes, dans l'ordre.** Matrice de corrélation sur la fenêtre
    longue. Vecteurs propres et portefeuilles propres. Choix du nombre de
    facteurs. Régression du titre sur les facteurs, sur la fenêtre courte.
    Résidu cumulé. Autorégression d'ordre un. Filtre de vitesse. Règle tout ou
    rien, puis couverture et normalisation.

    **Les variables.** ``correlation_window`` est la fenêtre longue, en séances,
    ``estimation_window`` la fenêtre courte, ``n_components`` le nombre de
    facteurs, ``max_characteristic_days`` le seuil du filtre de vitesse.

    **Les hypothèses.** Un titre appartient à l'univers d'une date quand il
    porte un rendement valide à chacune des séances de la fenêtre longue. Un
    titre qui cesse de coter sort donc de l'univers dès la séance suivante.

    **Les limites.** Le seuil de capitalisation de l'article, un milliard de
    dollars à la date de négociation, n'est pas reproductible sans une série de
    capitalisation en temps réel. L'argument ``tradable`` reçoit tout masque de
    remplacement, et l'étude déclare lequel.

    **La couverture est figée à l'entrée, et c'est la décision qui décide de
    tout.** L'article parle de positions tout ou rien, sans ajustement continu.
    Il chiffre par ailleurs son résultat net à cinq points de base par
    transaction. Recalculer la couverture chaque jour ferait retourner la
    totalité de la jambe de facteurs à chaque séance, ce qu'aucun rendement
    publié dans l'article ne pourrait payer. L'argument ``hedge_at_entry`` porte les deux
    lectures, et l'étude publie l'écart de rotation entre elles.

    **Le plafond de facteurs, et pourquoi il existe.** Le nombre de facteurs
    retenus est borné par la fenêtre d'estimation moins deux. Sans cette borne,
    une coupure à 75 pour cent de la variance demanderait plus de facteurs que
    la régression n'a de points, et les résidus seraient nuls par
    surparamétrage. Le compte des jours où la borne mord vit dans
    ``diagnostics``, et l'étude le publie.

    **Une alternative écartée.** Réestimer les facteurs moins souvent que les
    résidus diviserait le calcul, au prix d'un écart avec l'article qui refait
    tout chaque jour. L'argument ``reestimation_days`` balaie cette variante en
    entier plutôt qu'à moitié.

    **La provenance.** Avellaneda et Lee (2010), sections 3 à 5.

    **Comment vérifier l'implémentation.** La chaîne rebâtie sur un échantillon
    tronqué rend exactement les mêmes poids sur les dates communes. Le test du
    module l'exige, et c'est la preuve qu'aucune statistique de fin
    d'échantillon ne remonte le temps.

    Args:
        returns: les rendements quotidiens, une colonne par titre. Les valeurs
            manquantes marquent l'absence de cotation.
        rules: les règles de négociation à dérouler en parallèle.
        correlation_window: la fenêtre de la matrice de corrélation, en séances.
        estimation_window: la fenêtre de la régression résiduelle, en séances.
        n_components: le nombre fixe de facteurs.
        variance_share: la part de variance visée, si le nombre est variable.
        max_characteristic_days: le temps caractéristique maximal accepté, en
            séances. ``None`` retire le filtre.
        gross_leverage: l'exposition brute visée.
        reestimation_days: le nombre de séances entre deux décisions.
        hedge_at_entry: figer la couverture d'une position au jour où elle
            s'ouvre. Faux, la couverture se recalcule chaque séance.
        centre_across_names: centrer le s-score en travers des titres.
        use_modified_s_score: employer le s-score modifié par la dérive.
        tradable: un masque supplémentaire, par exemple de liquidité.
        min_names: la taille minimale de l'univers pour décider d'une position.
        periods_per_year: le nombre de séances par an.

    Returns:
        Le résultat complet, un tableau de poids par règle.

    Raises:
        ConfigError: si une fenêtre est trop courte, si aucune règle n'est
            donnée, ou si deux règles portent le même nom.
        InsufficientDataError: si l'échantillon est plus court que la somme des
            deux fenêtres.
    """
    if not isinstance(returns, pd.DataFrame):
        raise ConfigError(f"returns doit être un pandas.DataFrame, reçu {type(returns).__name__}.")
    if not isinstance(returns.index, pd.DatetimeIndex):
        raise ConfigError("returns doit porter un DatetimeIndex.")
    if not returns.index.is_monotonic_increasing:
        raise DataQualityError("returns n'est pas trié par date croissante.")
    if returns.index.has_duplicates:
        raise DataQualityError("returns porte des dates en double.")
    if not rules:
        raise ConfigError("aucune règle de négociation fournie.")
    names = [rule.name for rule in rules]
    if len(set(names)) != len(names):
        raise ConfigError(f"deux règles portent le même nom : {names}.")
    if correlation_window < estimation_window:
        raise ConfigError(
            f"la fenêtre de corrélation ({correlation_window}) doit couvrir la fenêtre "
            f"d'estimation ({estimation_window})."
        )
    if estimation_window < 10:
        raise ConfigError(f"estimation_window doit valoir au moins dix séances, reçu {estimation_window}.")
    if reestimation_days < 1:
        raise ConfigError(f"reestimation_days doit valoir au moins un, reçu {reestimation_days}.")
    if len(returns) <= correlation_window:
        raise InsufficientDataError(
            f"{len(returns)} séances pour une fenêtre de corrélation de {correlation_window}."
        )

    index = returns.index
    columns = returns.columns
    n_dates = len(index)
    n_assets = len(columns)
    values = returns.to_numpy(dtype=float)
    valid = np.isfinite(values)
    filled = np.where(valid, values, 0.0)
    member = _rolling_membership(valid, correlation_window)
    if tradable is not None:
        extra = tradable.reindex(index=index, columns=columns).to_numpy()
        member = member & np.nan_to_num(extra, nan=0.0).astype(bool)

    s_panel = np.full((n_dates, n_assets), np.nan)
    tau_panel = np.full((n_dates, n_assets), np.nan)
    sigma_panel = np.full((n_dates, n_assets), np.nan)
    drift_panel = np.full((n_dates, n_assets), np.nan)
    eligible_panel = np.zeros((n_dates, n_assets), dtype=bool)
    factor_counts = np.full(n_dates, np.nan)
    share_values = np.full(n_dates, np.nan)
    member_counts = member.sum(axis=1).astype(float)

    weight_panels = {rule.name: np.full((n_dates, n_assets), np.nan) for rule in rules}
    position_panels = {rule.name: np.full((n_dates, n_assets), np.nan) for rule in rules}
    position_counts = {rule.name: np.zeros(n_dates) for rule in rules}
    positions = {rule.name: np.zeros(n_assets) for rule in rules}
    books = {rule.name: np.zeros((n_assets, n_assets)) for rule in rules}

    slope_cap = None if max_characteristic_days is None else math.exp(-1.0 / float(max_characteristic_days))
    start = correlation_window - 1
    gram = filled[:correlation_window].T @ filled[:correlation_window]
    column_sums = filled[:correlation_window].sum(axis=0)
    n_decisions = 0
    n_degenerate = 0
    n_capped = 0
    factor_cap = estimation_window - 2

    for position_index in range(start, n_dates):
        if position_index > start:
            arriving = filled[position_index]
            leaving = filled[position_index - correlation_window]
            gram += np.outer(arriving, arriving) - np.outer(leaving, leaving)
            column_sums += arriving - leaving
        if (position_index - start) % reestimation_days != 0:
            continue

        active = np.flatnonzero(member[position_index])
        required = min_names if n_components is None else max(min_names, int(n_components) + 5)
        if active.size < required:
            for rule in rules:
                positions[rule.name] = np.zeros(n_assets)
                books[rule.name][:] = 0.0
                weight_panels[rule.name][position_index] = 0.0
                position_panels[rule.name][position_index] = 0.0
            continue

        sub_gram = gram[np.ix_(active, active)]
        means = column_sums[active] / correlation_window
        covariance = (sub_gram - correlation_window * np.outer(means, means)) / (correlation_window - 1)
        variances = np.diag(covariance)
        if bool((variances <= 0.0).any()):
            n_degenerate += 1
            for rule in rules:
                positions[rule.name] = np.zeros(n_assets)
                books[rule.name][:] = 0.0
                weight_panels[rule.name][position_index] = 0.0
                position_panels[rule.name][position_index] = 0.0
            continue
        inverse_sigma = 1.0 / np.sqrt(variances)
        correlation = covariance * inverse_sigma[:, None] * inverse_sigma[None, :]
        eigenvalues, eigenvectors = np.linalg.eigh(correlation)
        order = np.argsort(eigenvalues)[::-1]
        eigenvalues = eigenvalues[order]
        eigenvectors = eigenvectors[:, order]
        trace = float(eigenvalues.sum())
        if variance_share is not None:
            cumulative = np.cumsum(np.clip(eigenvalues, 0.0, None)) / trace
            kept = min(int(np.searchsorted(cumulative, variance_share) + 1), active.size - 1)
        else:
            kept = min(int(n_components), active.size - 1)  # type: ignore[arg-type]
        if kept > factor_cap:
            kept = factor_cap
            n_capped += 1
        kept = max(kept, 1)
        factor_weights = (eigenvectors[:, :kept] * inverse_sigma[:, None]).T

        window = values[position_index - estimation_window + 1 : position_index + 1][:, active]
        factors = window @ factor_weights.T
        betas, drift, cumulative_residuals = residual_regression(window, factors)
        fit = ornstein_uhlenbeck_fit(cumulative_residuals, periods_per_year=periods_per_year)
        scores = s_scores(
            fit,
            centre_across_names=centre_across_names,
            drift=drift if use_modified_s_score else None,
        )
        eligible = fit.stationary.copy()
        if slope_cap is not None:
            eligible &= fit.ar1_slope < slope_cap

        s_panel[position_index, active] = scores
        tau_panel[position_index, active] = characteristic_time_days(
            fit.kappa, periods_per_year=periods_per_year
        )
        sigma_panel[position_index, active] = np.where(fit.stationary, fit.sigma_eq, np.nan)
        drift_panel[position_index, active] = drift
        eligible_panel[position_index, active] = eligible
        factor_counts[position_index] = float(kept)
        share_values[position_index] = float(np.clip(eigenvalues[:kept], 0.0, None).sum() / trace)
        n_decisions += 1

        unit_book = np.eye(active.size) - betas @ factor_weights
        for rule in rules:
            previous = positions[rule.name][active]
            state = update_positions(previous, scores, eligible, rule)
            fresh = np.zeros(n_assets)
            fresh[active] = state
            position_counts[rule.name][position_index] = float(np.abs(state).sum())
            if hedge_at_entry:
                book = books[rule.name]
                book[fresh == 0.0, :] = 0.0
                for local in np.flatnonzero((state != 0.0) & (state != previous)):
                    line = np.zeros(n_assets)
                    line[active] = state[local] * unit_book[local]
                    book[active[local]] = line
                raw = book.sum(axis=0)
            else:
                raw = np.zeros(n_assets)
                raw[active] = state @ unit_book
            positions[rule.name] = fresh
            position_panels[rule.name][position_index] = fresh
            if float(np.abs(raw).sum()) > 0.0:
                raw = scale_to_gross(pd.Series(raw), gross_leverage).to_numpy()
            weight_panels[rule.name][position_index] = raw

    _LOG.info(
        "chaîne d'arbitrage statistique terminée",
        extra={
            "n_decisions": n_decisions,
            "n_assets": n_assets,
            "n_rules": len(rules),
            "n_degenerate": n_degenerate,
            "n_capped": n_capped,
        },
    )
    return StatisticalArbitrageResult(
        weights={
            name: pd.DataFrame(panel, index=index, columns=columns) for name, panel in weight_panels.items()
        },
        s_score=pd.DataFrame(s_panel, index=index, columns=columns),
        characteristic_days=pd.DataFrame(tau_panel, index=index, columns=columns),
        equilibrium_volatility=pd.DataFrame(sigma_panel, index=index, columns=columns),
        drift=pd.DataFrame(drift_panel, index=index, columns=columns),
        eligible=pd.DataFrame(eligible_panel, index=index, columns=columns),
        membership=pd.DataFrame(member, index=index, columns=columns),
        positions={
            name: pd.DataFrame(panel, index=index, columns=columns) for name, panel in position_panels.items()
        },
        n_positions=pd.DataFrame(position_counts, index=index),
        n_factors=pd.Series(factor_counts, index=index, name="n_factors"),
        variance_share=pd.Series(share_values, index=index, name="variance_share"),
        n_members=pd.Series(member_counts, index=index, name="n_members"),
        diagnostics={
            "n_decisions": float(n_decisions),
            "n_degenerate_windows": float(n_degenerate),
            "n_capped_windows": float(n_capped),
            "factor_cap": float(factor_cap),
            "survivorship_bias_risk": float(SURVIVORSHIP_BIAS_RISK),
        },
    )

r"""La décomposition du risque d'un portefeuille, et pourquoi elle est exacte.

**Le problème.** Un portefeuille affiche une volatilité unique, par exemple
12 % par an. Cette volatilité ne dit pas d'où vient le risque. Une ligne qui
pèse 3 % du capital peut en porter 30 %, et personne ne le voit dans le tableau
des poids. La question posée ici est donc : combien chaque ligne, chaque
secteur, chaque facteur ajoute-t-il à la volatilité du tout ?

**Pourquoi la réponse est exacte et non approximative.** La volatilité
:math:`\sigma_p(w) = \sqrt{w' \Sigma w}` est une fonction homogène de degré 1
en :math:`w` : multiplier tous les poids par :math:`c > 0` multiplie la
volatilité par :math:`c`. Le théorème d'Euler sur les fonctions homogènes dit
alors que la fonction est égale à la somme de ses dérivées partielles
pondérées par les variables.

.. math::

    \sigma_p(w) \;=\; \sum_{i=1}^{n} w_i \frac{\partial \sigma_p}{\partial w_i}
    \;=\; \sum_{i=1}^{n} \underbrace{w_i \frac{(\Sigma w)_i}{\sigma_p}}_{RC_i}

L'égalité est une identité algébrique, valable pour tout :math:`w` non nul et
toute covariance. La somme des contributions au risque redonne EXACTEMENT la
volatilité du portefeuille, à l'erreur d'arrondi machine près. C'est ce qui
distingue cette décomposition d'une attribution approchée : il n'y a pas de
résidu à répartir, pas de terme croisé laissé de côté. Le test
``test_euler_identity_holds_on_random_covariances`` vérifie l'identité à
1e-12 sur des matrices tirées au hasard.

**Contribution au risque n'est pas contribution à la perte en cas de crise.**
La confusion est fréquente et coûte cher. La contribution au risque mesure la
sensibilité de la volatilité à une hausse marginale du poids, sous une loi
supposée stable. Elle décrit le comportement moyen, autour du centre de la
distribution. La contribution à la perte d'un jour de crise dépend, elle, des
corrélations observées CE jour-là, qui ne sont pas celles de l'échantillon.
Deux mécanismes séparent les deux mesures. D'abord les corrélations montent
en crise, souvent vers 1, ce qui rapproche toutes les lignes et efface la
diversification mesurée en régime calme. Ensuite les queues sont épaisses et
asymétriques, si bien qu'une ligne de faible volatilité peut porter le gros de
la perte d'un jour donné. Sous hypothèse gaussienne, la contribution au risque
égale la contribution attendue à la perte au-delà d'un seuil, résultat de Qian
(2006) ; hors de cette hypothèse, l'égalité tombe. Le laboratoire mesure donc
les deux séparément, et ne présente jamais l'une pour l'autre.

**La limite de fond.** Tout ce module suppose :math:`\Sigma` connue. Elle ne
l'est pas : elle est estimée, sur une fenêtre choisie, avec une erreur qui
croît quand le nombre d'actifs approche le nombre d'observations. Sur
:math:`n` actifs et :math:`T` observations, la covariance empirique porte
:math:`n(n+1)/2` paramètres estimés sur :math:`nT` nombres. À 100 actifs et
250 jours, cela fait 5 050 paramètres pour 25 000 observations, et les plus
petites valeurs propres sont alors gravement sous-estimées. La conséquence
pratique : une contribution au risque calculée sur une covariance empirique
brute est un chiffre bruyant, dont le rang entre lignes peut s'inverser d'une
fenêtre à l'autre. Le remède est un estimateur régularisé, celui de Ledoit et
Wolf (2004) par exemple, et la publication de la fenêtre utilisée à côté du
chiffre. Ce module ne choisit pas l'estimateur : il reçoit la covariance et
décompose, ce qui rend la décision d'estimation visible ailleurs.

Provenance des méthodes, statut rapporté. Litterman (1996) pour la
décomposition marginale, Qian (2006) pour son interprétation financière. Puis
Maillard, Roncalli et Teiletche (2010) pour la parité de risque, Choueifaty et
Coignard (2008) pour le ratio de diversification, et Meucci (2009) pour le
nombre effectif de paris.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd

from quantlab.core.errors import DataQualityError, InsufficientDataError
from quantlab.core.types import Weights

__all__ = [
    "DEFAULT_MIN_VOLATILITY",
    "DEFAULT_PSD_TOLERANCE",
    "DEFAULT_SYMMETRY_TOLERANCE",
    "FactorRiskDecomposition",
    "check_covariance",
    "diversification_ratio",
    "effective_number_of_bets",
    "factor_risk_contribution",
    "group_risk_contribution",
    "marginal_risk_contribution",
    "portfolio_volatility",
    "risk_contribution",
    "risk_contribution_pct",
]

#: Écart de symétrie toléré, en relatif au plus grand élément de la matrice.
#: Une covariance calculée par ``numpy`` est symétrique à l'arrondi près, donc
#: 1e-10 laisse passer l'arrondi et refuse une vraie asymétrie.
DEFAULT_SYMMETRY_TOLERANCE: float = 1e-10

#: Valeur propre négative tolérée, en relatif au plus grand élément. Une
#: covariance de rang déficient rend des valeurs propres nulles à 1e-16 près,
#: parfois du mauvais signe ; 1e-10 les accepte et refuse une matrice qui
#: décrirait une variance négative.
DEFAULT_PSD_TOLERANCE: float = 1e-10

#: Volatilité en deçà de laquelle la décomposition n'est plus définie. La
#: dérivée de la racine carrée diverge en zéro, donc un portefeuille de
#: volatilité nulle n'a pas de contribution marginale.
DEFAULT_MIN_VOLATILITY: float = 1e-14


def check_covariance(
    covariance: pd.DataFrame,
    *,
    symmetry_tolerance: float = DEFAULT_SYMMETRY_TOLERANCE,
    psd_tolerance: float = DEFAULT_PSD_TOLERANCE,
) -> None:
    """Vérifie qu'une matrice est une covariance utilisable, ou lève.

    Trois conditions sont contrôlées : la matrice est carrée et étiquetée de
    la même façon en lignes et en colonnes, elle est symétrique, et elle est
    semi-définie positive. La troisième est la seule qui porte du sens
    financier : une valeur propre négative signifie qu'un portefeuille aurait
    une variance négative, ce qui n'existe pas.

    Args:
        covariance: la matrice à contrôler, indexée par les actifs.
        symmetry_tolerance: écart de symétrie toléré, relatif à l'échelle de la
            matrice définie ci-dessous.
        psd_tolerance: valeur propre négative tolérée, même échelle.

    Note:
        L'échelle vaut ``max(|Sigma|.max(), 1.0)``. Le plancher à 1 rend la
        tolérance ABSOLUE pour une covariance de petite amplitude. Sur des
        rendements quotidiens, dont les variances valent quelques 1e-4, le
        contrôle laisse donc passer une valeur propre de -1e-11, négligeable
        devant l'arrondi mais non nulle. Ce choix est délibéré : sans plancher,
        une covariance presque nulle rejetterait son propre bruit d'arrondi.

    Raises:
        InsufficientDataError: la matrice est vide.
        DataQualityError: la matrice n'est pas carrée, ses étiquettes de lignes
            et de colonnes diffèrent, elle porte des doublons, elle contient un
            nombre non fini, elle n'est pas symétrique, ou elle n'est pas
            semi-définie positive.

    Note:
        Le contrôle de symétrie précède celui des valeurs propres pour une
        raison technique : ``numpy.linalg.eigvalsh`` ne lit que le triangle
        inférieur et ignorerait donc l'asymétrie en silence.
    """
    if covariance.shape[0] != covariance.shape[1]:
        raise DataQualityError(f"la covariance n'est pas carrée : forme {covariance.shape}")
    if covariance.shape[0] == 0:
        raise InsufficientDataError("la covariance est vide, aucune décomposition possible")
    if covariance.index.has_duplicates:
        raise DataQualityError("la covariance porte des étiquettes d'actif en double")
    if not covariance.index.equals(covariance.columns):
        raise DataQualityError(
            "les lignes et les colonnes de la covariance ne portent pas les mêmes étiquettes"
        )

    values = covariance.to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise DataQualityError("la covariance contient au moins une valeur non finie")

    scale = max(float(np.abs(values).max()), 1.0)
    asymmetry = float(np.abs(values - values.T).max())
    if asymmetry > symmetry_tolerance * scale:
        raise DataQualityError(
            f"la covariance n'est pas symétrique : écart maximal {asymmetry:.3e} "
            f"pour une tolérance de {symmetry_tolerance * scale:.3e}"
        )

    smallest = float(np.linalg.eigvalsh(values).min())
    if smallest < -psd_tolerance * scale:
        raise DataQualityError(
            f"la covariance n'est pas semi-définie positive : plus petite valeur propre "
            f"{smallest:.3e} pour une tolérance de {-psd_tolerance * scale:.3e}"
        )


def _aligned(
    weights: Weights,
    covariance: pd.DataFrame,
    *,
    symmetry_tolerance: float,
    psd_tolerance: float,
) -> tuple[np.ndarray, np.ndarray, pd.Index]:
    """Contrôle et aligne les poids sur la covariance, dans l'ordre de celle-ci.

    Returns:
        Le vecteur de poids, la matrice de covariance et l'index commun.

    Raises:
        InsufficientDataError: les poids sont vides.
        DataQualityError: les étiquettes ne se correspondent pas, ou un poids
            n'est pas fini.
    """
    check_covariance(covariance, symmetry_tolerance=symmetry_tolerance, psd_tolerance=psd_tolerance)
    if len(weights) == 0:
        raise InsufficientDataError("le vecteur de poids est vide")
    if weights.index.has_duplicates:
        raise DataQualityError("le vecteur de poids porte des étiquettes d'actif en double")

    missing = covariance.index.difference(weights.index)
    extra = weights.index.difference(covariance.index)
    if len(missing) > 0 or len(extra) > 0:
        raise DataQualityError(
            f"poids et covariance ne portent pas les mêmes actifs : "
            f"{len(missing)} absent(s) des poids, {len(extra)} absent(s) de la covariance"
        )

    aligned = weights.reindex(covariance.index).to_numpy(dtype=float)
    if not np.isfinite(aligned).all():
        raise DataQualityError("le vecteur de poids contient au moins une valeur non finie")
    return aligned, covariance.to_numpy(dtype=float), covariance.index


def _volatility(weights: np.ndarray, covariance: np.ndarray) -> float:
    """Rend la volatilité du portefeuille, variance négative d'arrondi ramenée à zéro."""
    variance = float(weights @ covariance @ weights)
    return float(np.sqrt(max(variance, 0.0)))


def _require_positive_volatility(volatility: float, minimum_volatility: float) -> float:
    """Rend la volatilité, ou lève si elle est trop petite pour diviser."""
    if volatility <= minimum_volatility:
        raise DataQualityError(
            f"la volatilité du portefeuille vaut {volatility:.3e}, en deçà du seuil "
            f"{minimum_volatility:.3e} : la décomposition n'est pas définie en zéro"
        )
    return volatility


def portfolio_volatility(
    weights: Weights,
    covariance: pd.DataFrame,
    *,
    symmetry_tolerance: float = DEFAULT_SYMMETRY_TOLERANCE,
    psd_tolerance: float = DEFAULT_PSD_TOLERANCE,
) -> float:
    r"""Rend la volatilité du portefeuille pour la période de la covariance.

    **Le problème.** Le risque d'un panier n'est pas la moyenne des risques de
    ses lignes. Il dépend de la façon dont elles bougent ensemble.

    **L'intuition.** Additionner des risques revient à additionner des
    vecteurs, pas des nombres. Deux actifs de même volatilité qui bougent en
    sens contraire se compensent, et le panier est plus calme que chacune de
    ses lignes.

    .. math::

        \sigma_p = \sqrt{w' \Sigma w}
                 = \sqrt{\sum_i \sum_j w_i w_j \sigma_{ij}}

    Args:
        weights: les poids du portefeuille, indexés par actif. Ils ne somment
            pas nécessairement à 1 : un portefeuille à somme nulle est légitime.
        covariance: la covariance des rendements des mêmes actifs, dans la
            période et la fréquence choisies par l'appelant.
        symmetry_tolerance: voir :func:`check_covariance`.
        psd_tolerance: voir :func:`check_covariance`.

    Returns:
        La volatilité, dans l'unité de la covariance. Une covariance de
        rendements quotidiens rend une volatilité quotidienne, jamais annuelle.

    Raises:
        InsufficientDataError: poids ou covariance vides.
        DataQualityError: covariance invalide, ou étiquettes qui ne
            correspondent pas.

    Variables :
        :math:`w_i` le poids de l'actif :math:`i` ; :math:`\sigma_{ij}` la
        covariance des rendements de :math:`i` et :math:`j` ; :math:`\Sigma` la
        matrice qui les rassemble.

    Hypothèses :
        La covariance décrit la période où les poids sont détenus, et elle est
        constante sur cette période. Aucune hypothèse de loi n'est faite : la
        formule est une identité de variance, valable au-delà du cas gaussien.

    Limites :
        La covariance est estimée. Sur une fenêtre courte, la volatilité
        rendue hérite d'une erreur d'estimation qui n'est pas affichée ici.

    Alternatives :
        Calculer directement l'écart type de la série des rendements du
        portefeuille. Les deux coïncident quand les poids sont fixes et que la
        covariance est l'estimateur empirique de la même fenêtre. La forme
        quadratique est retenue parce qu'elle se dérive, donc se décompose.

    Provenance :
        Markowitz (1952), « Portfolio Selection », Journal of Finance 7(1),
        pages 77 à 91. Statut rapporté.

    Example:
        >>> import pandas as pd
        >>> cov = pd.DataFrame([[0.04, 0.01], [0.01, 0.01]], index=["a", "b"], columns=["a", "b"])
        >>> w = pd.Series([0.6, 0.4], index=["a", "b"])
        >>> round(portfolio_volatility(w, cov), 6)
        0.144222

    Note:
        Vérification : sur deux actifs de volatilités 0,2 et 0,1, corrélés à
        0,5 et pondérés 0,6 et 0,4, la variance vaut 0,0208 à la main et la
        racine 0,144222.
    """
    w, cov, _ = _aligned(
        weights, covariance, symmetry_tolerance=symmetry_tolerance, psd_tolerance=psd_tolerance
    )
    return _volatility(w, cov)


def marginal_risk_contribution(
    weights: Weights,
    covariance: pd.DataFrame,
    *,
    minimum_volatility: float = DEFAULT_MIN_VOLATILITY,
    symmetry_tolerance: float = DEFAULT_SYMMETRY_TOLERANCE,
    psd_tolerance: float = DEFAULT_PSD_TOLERANCE,
) -> pd.Series:
    r"""Rend la contribution marginale au risque de chaque actif.

    **Le problème.** De combien la volatilité du portefeuille bouge-t-elle si
    j'ajoute un euro sur une ligne ? La réponse ne dépend pas de la seule
    volatilité de cette ligne, mais de sa covariance avec tout le reste.

    **L'intuition.** Un actif volatil mais décorrélé du portefeuille peut
    laisser la volatilité totale inchangée, voire la réduire. Ce qui compte
    n'est pas le risque de la ligne, c'est le risque qu'elle partage avec le
    portefeuille déjà en place.

    .. math::

        MR_i = \frac{\partial \sigma_p}{\partial w_i}
             = \frac{(\Sigma w)_i}{\sigma_p}
             = \beta_{i,p} \, \sigma_p

    La troisième écriture dit tout : la contribution marginale est le bêta de
    l'actif par rapport au portefeuille, multiplié par la volatilité du
    portefeuille. Un actif de bêta nul ne change rien au premier ordre.

    Args:
        weights: les poids du portefeuille, indexés par actif.
        covariance: la covariance des rendements des mêmes actifs.
        minimum_volatility: seuil en deçà duquel la division est refusée.
        symmetry_tolerance: voir :func:`check_covariance`.
        psd_tolerance: voir :func:`check_covariance`.

    Returns:
        Une série indexée comme la covariance, nommée
        ``marginal_risk_contribution``, dans l'unité de la volatilité.

    Raises:
        DataQualityError: la volatilité du portefeuille est sous
            ``minimum_volatility``, donc la dérivée n'existe pas.

    Variables :
        :math:`(\Sigma w)_i` la covariance de l'actif :math:`i` avec le
        portefeuille ; :math:`\beta_{i,p}` le bêta de :math:`i` sur le
        portefeuille ; :math:`\sigma_p` la volatilité du portefeuille.

    Hypothèses :
        Dérivée locale, donc valable pour une variation infinitésimale du
        poids. Un ajout de 10 % du capital sur une ligne n'est pas
        infinitésimal, et l'effet réel diffère de la contribution marginale.

    Limites :
        La mesure suppose que la covariance ne change pas quand le portefeuille
        change, ce qui est faux dès que la taille de la position influence le
        marché.

    Alternatives :
        Recalculer la volatilité après un déplacement fini de poids, ce qui
        donne l'effet total plutôt que marginal. Utile pour les gros
        déplacements, inutilisable pour une décomposition additive.

    Provenance :
        Litterman (1996), « Hot Spots and Hedges », Goldman Sachs Risk
        Management Series. Statut rapporté.

    Note:
        Vérification : la moyenne des contributions marginales pondérée par les
        poids redonne exactement la volatilité, ce qui est le théorème d'Euler.
    """
    w, cov, index = _aligned(
        weights, covariance, symmetry_tolerance=symmetry_tolerance, psd_tolerance=psd_tolerance
    )
    volatility = _require_positive_volatility(_volatility(w, cov), minimum_volatility)
    return pd.Series(cov @ w / volatility, index=index, name="marginal_risk_contribution")


def risk_contribution(
    weights: Weights,
    covariance: pd.DataFrame,
    *,
    minimum_volatility: float = DEFAULT_MIN_VOLATILITY,
    symmetry_tolerance: float = DEFAULT_SYMMETRY_TOLERANCE,
    psd_tolerance: float = DEFAULT_PSD_TOLERANCE,
) -> pd.Series:
    r"""Rend la part de volatilité portée par chaque actif, en unité de volatilité.

    **Le problème.** Répartir la volatilité du portefeuille entre ses lignes,
    sans reste et sans double compte.

    **L'intuition.** Chaque ligne reçoit sa contribution marginale multipliée
    par son poids, comme on facture un prix unitaire multiplié par une
    quantité. La somme des factures fait exactement le total, et ce n'est pas
    une coïncidence : c'est le théorème d'Euler appliqué à une fonction
    homogène de degré 1.

    .. math::

        RC_i = w_i \frac{(\Sigma w)_i}{\sigma_p}
        \qquad \text{avec} \qquad
        \sum_{i=1}^{n} RC_i = \sigma_p

    Args:
        weights: les poids du portefeuille, indexés par actif.
        covariance: la covariance des rendements des mêmes actifs.
        minimum_volatility: seuil en deçà duquel la division est refusée.
        symmetry_tolerance: voir :func:`check_covariance`.
        psd_tolerance: voir :func:`check_covariance`.

    Returns:
        Une série nommée ``risk_contribution``, de même unité que la
        volatilité, dont la somme égale la volatilité du portefeuille.

    Raises:
        DataQualityError: volatilité nulle, covariance invalide ou étiquettes
            incohérentes.

    Variables :
        :math:`w_i` le poids ; :math:`(\Sigma w)_i` la covariance de l'actif
        avec le portefeuille ; :math:`\sigma_p` la volatilité du portefeuille.

    Hypothèses :
        Covariance connue et stable sur la période. Positions détenues telles
        quelles, sans rééquilibrage à l'intérieur de la période.

    Limites :
        Une contribution peut être négative. C'est le cas d'une couverture, et
        ce n'est pas une anomalie : la ligne réduit la volatilité du tout. En
        revanche, cela interdit de lire les contributions comme des parts d'un
        gâteau, puisqu'une part négative existe.

    Alternatives :
        Décomposer la valeur à risque ou la perte attendue plutôt que la
        volatilité, ce qui décrit la queue de distribution au lieu du centre.
        La volatilité est retenue ici parce que sa décomposition est exacte
        sans hypothèse de loi.

    Provenance :
        Qian (2006), « On the Financial Interpretation of Risk Contribution:
        Risk Budgets Do Add Up », Journal of Investment Management. Statut
        rapporté.

    Example:
        >>> import pandas as pd
        >>> cov = pd.DataFrame([[0.04, 0.0], [0.0, 0.0025]], index=["a", "b"], columns=["a", "b"])
        >>> w = pd.Series([0.2, 0.8], index=["a", "b"])
        >>> risk_contribution(w, cov).round(6).tolist()
        [0.028284, 0.028284]

    Note:
        Vérification : sur deux actifs non corrélés de volatilités 0,2 et 0,05,
        des poids inversement proportionnels aux volatilités, soit 0,2 et 0,8,
        donnent deux contributions rigoureusement égales. C'est la parité de
        risque à deux actifs, et elle se calcule à la main.
    """
    w, cov, index = _aligned(
        weights, covariance, symmetry_tolerance=symmetry_tolerance, psd_tolerance=psd_tolerance
    )
    volatility = _require_positive_volatility(_volatility(w, cov), minimum_volatility)
    return pd.Series(w * (cov @ w) / volatility, index=index, name="risk_contribution")


def risk_contribution_pct(
    weights: Weights,
    covariance: pd.DataFrame,
    *,
    minimum_volatility: float = DEFAULT_MIN_VOLATILITY,
    symmetry_tolerance: float = DEFAULT_SYMMETRY_TOLERANCE,
    psd_tolerance: float = DEFAULT_PSD_TOLERANCE,
) -> pd.Series:
    r"""Rend la part relative de risque de chaque actif, de somme égale à 1.

    La contribution relative est la contribution en unité de volatilité
    divisée par la volatilité du portefeuille. Elle se réécrit sans passer par
    la racine carrée, ce qui montre qu'elle ne dépend que des variances et des
    covariances.

    .. math::

        RC^{\%}_i = \frac{RC_i}{\sigma_p}
                  = \frac{w_i (\Sigma w)_i}{w' \Sigma w}
        \qquad \text{avec} \qquad \sum_i RC^{\%}_i = 1

    Args:
        weights: les poids du portefeuille, indexés par actif.
        covariance: la covariance des rendements des mêmes actifs.
        minimum_volatility: seuil en deçà duquel la division est refusée.
        symmetry_tolerance: voir :func:`check_covariance`.
        psd_tolerance: voir :func:`check_covariance`.

    Returns:
        Une série nommée ``risk_contribution_pct``, sans unité, de somme 1.

    Variables :
        :math:`w_i` le poids ; :math:`(\Sigma w)_i` la covariance de l'actif
        avec le portefeuille ; :math:`w' \Sigma w` la variance du portefeuille.

    Hypothèses :
        Les mêmes que pour :func:`risk_contribution`, dont cette quantité est
        le quotient. Aucune hypothèse de loi n'est ajoutée.

    Limites :
        La somme vaut 1 même quand une part est négative, donc la lecture en
        pourcentage cesse d'être intuitive dès qu'une ligne couvre les autres.

    Alternatives :
        Publier les contributions en unité de volatilité, ce que fait
        :func:`risk_contribution`. La forme relative est retenue pour comparer
        deux portefeuilles de volatilités différentes, où les unités ne se
        comparent pas.

    Provenance :
        Litterman (1996) pour la décomposition, Maillard, Roncalli et Teiletche
        (2010) pour son emploi en budget de risque, où la cible est justement
        une répartition de ces parts. Statut rapporté.

    Note:
        Cette forme est invariante d'échelle deux fois : multiplier tous les
        poids par une constante positive ne la change pas, et multiplier la
        covariance entière par une constante positive non plus. C'est la
        propriété testée par ``test_risk_contribution_pct_is_scale_invariant``.

    Note:
        Le dénominateur est la variance :math:`w' \Sigma w`, jamais la somme
        des contributions. Les deux sont égales par le théorème d'Euler, mais
        diviser par la somme rendrait le total égal à 1 par construction, et
        l'assertion qui le vérifie ne testerait plus rien. Mesuré le
        2026-09-01 : avec un tel dénominateur, quatre vecteurs de contributions
        faux, dont un de signe inversé, sommaient encore à 1 à 1e-16 près.

    Note:
        Vérification : sur le cas à deux actifs de :func:`portfolio_volatility`,
        les parts valent 0,0168/0,0208 et 0,0040/0,0208, soit 21/26 et 5/26.
    """
    w, cov, index = _aligned(
        weights, covariance, symmetry_tolerance=symmetry_tolerance, psd_tolerance=psd_tolerance
    )
    variance = float(w @ cov @ w)
    _require_positive_volatility(float(np.sqrt(max(variance, 0.0))), minimum_volatility)
    return pd.Series(w * (cov @ w) / variance, index=index, name="risk_contribution_pct")


def diversification_ratio(
    weights: Weights,
    covariance: pd.DataFrame,
    *,
    minimum_volatility: float = DEFAULT_MIN_VOLATILITY,
    symmetry_tolerance: float = DEFAULT_SYMMETRY_TOLERANCE,
    psd_tolerance: float = DEFAULT_PSD_TOLERANCE,
) -> float:
    r"""Rend le ratio de diversification, soit le risque évité par la corrélation.

    **Le problème.** Mesurer d'un seul nombre ce que la diversification a
    rapporté, sans se contenter de compter les lignes. Un portefeuille de
    cinquante actions d'un même secteur est concentré, quel que soit le nombre
    de lignes.

    **L'intuition.** Comparer le risque que le portefeuille aurait si tout
    bougeait ensemble au risque qu'il a réellement. Le premier est la moyenne
    pondérée des volatilités, le second la volatilité du portefeuille. Leur
    rapport vaut 1 quand rien n'est diversifié, et grandit avec la
    décorrélation.

    .. math::

        DR(w) = \frac{\sum_i w_i \sigma_i}{\sqrt{w' \Sigma w}}
              = \frac{w' \sigma}{\sigma_p}

    Args:
        weights: les poids du portefeuille, indexés par actif.
        covariance: la covariance des rendements des mêmes actifs.
        minimum_volatility: seuil en deçà duquel la division est refusée.
        symmetry_tolerance: voir :func:`check_covariance`.
        psd_tolerance: voir :func:`check_covariance`.

    Returns:
        Le ratio, sans unité.

    Variables :
        :math:`\sigma_i` la volatilité de l'actif :math:`i`, racine du terme
        diagonal de :math:`\Sigma` ; :math:`\sigma` le vecteur de ces
        volatilités ; :math:`\sigma_p` la volatilité du portefeuille.

    Hypothèses :
        Aucune sur la loi des rendements. La borne inférieure de 1 exige en
        revanche des poids positifs : elle vient de la sous-additivité de la
        norme, et un poids négatif peut la faire tomber sous 1.

    Limites :
        Le ratio ignore les rendements attendus. Un portefeuille très
        diversifié peut être un mauvais portefeuille. De plus il croît
        mécaniquement quand on ajoute des lignes de faible corrélation même
        minuscules, si bien qu'il se manipule.

    Alternatives :
        Le nombre effectif de paris de Meucci, implémenté dans
        :func:`effective_number_of_bets`, qui compte des sources de risque
        indépendantes au lieu de comparer deux volatilités. Le ratio de
        diversification est retenu ici parce qu'il se calcule sans
        décomposition spectrale, donc sans choix de rotation.

    Provenance :
        Choueifaty et Coignard (2008), « Toward Maximum Diversification »,
        Journal of Portfolio Management, automne 2008, pages 40 à 51. Statut
        rapporté. Le numéro de volume n'a pas été vérifié.

    Note:
        Vérification : quand toutes les corrélations valent 1, la covariance
        s'écrit :math:`\sigma \sigma'`, la volatilité du portefeuille vaut
        :math:`w' \sigma` et le ratio vaut exactement 1. Ce cas est testé.
    """
    w, cov, _ = _aligned(
        weights, covariance, symmetry_tolerance=symmetry_tolerance, psd_tolerance=psd_tolerance
    )
    volatility = _require_positive_volatility(_volatility(w, cov), minimum_volatility)
    asset_volatilities = np.sqrt(np.clip(np.diag(cov), 0.0, None))
    return float(w @ asset_volatilities) / volatility


def effective_number_of_bets(
    weights: Weights,
    covariance: pd.DataFrame,
    *,
    minimum_volatility: float = DEFAULT_MIN_VOLATILITY,
    symmetry_tolerance: float = DEFAULT_SYMMETRY_TOLERANCE,
    psd_tolerance: float = DEFAULT_PSD_TOLERANCE,
) -> float:
    r"""Rend le nombre effectif de paris, variante par composantes principales.

    **Le problème.** Compter les sources de risque réellement indépendantes
    d'un portefeuille. Dix actions du même secteur ne font pas dix paris, elles
    en font un seul répété dix fois.

    **L'intuition.** On change de base : au lieu des actifs, on regarde les
    portefeuilles principaux, des combinaisons non corrélées entre elles
    obtenues par décomposition spectrale de la covariance. La variance du
    portefeuille se répartit alors entre ces sources indépendantes, et cette
    répartition est une distribution de probabilité. Son entropie mesure
    l'étalement, et son exponentielle rend un nombre de paris.

    .. math::

        \Sigma = E \Lambda E' , \qquad
        \tilde{w} = E' w , \qquad
        p_k = \frac{\tilde{w}_k^2 \lambda_k}{w' \Sigma w}

    .. math::

        N_{Ent} = \exp\left(-\sum_{k=1}^{n} p_k \ln p_k\right)

    **La variante implémentée.** C'est la variante par composantes
    principales, celle de l'article de 2009. Meucci, Santangelo et Deguest
    (2015) proposent ensuite une rotation dite de torsion minimale, qui choisit
    des facteurs non corrélés les plus proches possibles des actifs d'origine.
    Elle n'est pas implémentée ici, et son absence est déclarée plutôt que
    comblée.

    Args:
        weights: les poids du portefeuille, indexés par actif.
        covariance: la covariance des rendements des mêmes actifs.
        minimum_volatility: seuil en deçà duquel la division est refusée.
        symmetry_tolerance: voir :func:`check_covariance`.
        psd_tolerance: voir :func:`check_covariance`.

    Returns:
        Un nombre entre 1 et le nombre d'actifs. Il vaut 1 quand toute la
        variance passe par une seule composante, et :math:`n` quand les
        :math:`n` composantes en portent autant l'une que l'autre.

    Variables :
        :math:`E` la matrice des vecteurs propres, :math:`\Lambda` la
        diagonale des valeurs propres. :math:`\tilde{w}_k` est l'exposition du
        portefeuille au :math:`k`-ième portefeuille principal, et :math:`p_k`
        la part de variance qu'il porte.

    Hypothèses :
        La covariance est semi-définie positive, donc diagonalisable en base
        orthonormée. Les composantes de variance nulle sont exclues du calcul
        d'entropie, puisque :math:`0 \ln 0` vaut 0 par prolongement.

    Limites :
        Deux limites sérieuses. D'abord la mesure dépend de la rotation
        choisie : quand deux valeurs propres sont égales, les vecteurs propres
        ne sont pas déterminés et le résultat change avec la base retenue. Sur
        une covariance :math:`0{,}04 \times I` à deux actifs équipondérés, la
        base canonique donne 2 et une rotation de 45 degrés donne 1, pour le
        même portefeuille. Ensuite les composantes principales n'ont pas
        d'interprétation économique, ce qui rend le chiffre difficile à
        expliquer à un comité.

    Alternatives :
        Le ratio de diversification, plus simple et sans choix de base, ou la
        version à torsion minimale déjà citée. La variante spectrale est
        retenue ici parce qu'elle ne demande aucun modèle de facteurs et se
        vérifie sur des cas fermés.

    Provenance :
        Meucci (2009), « Managing Diversification », Risk, mai 2009, pages 74 à
        79. Statut rapporté.

    Note:
        Vérification sur un cas simple. Une covariance diagonale de variances
        0,04 et 0,01, avec des poids égaux à 0,5, donne des parts de 0,8 et 0,2.
        Le nombre effectif vaut alors
        :math:`\exp(-0{,}8 \ln 0{,}8 - 0{,}2 \ln 0{,}2)`, soit 1,6493. Ce cas
        est calculé à la main dans les tests.
    """
    w, cov, _ = _aligned(
        weights, covariance, symmetry_tolerance=symmetry_tolerance, psd_tolerance=psd_tolerance
    )
    _require_positive_volatility(_volatility(w, cov), minimum_volatility)
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    principal_exposures = eigenvectors.T @ w
    variances = np.square(principal_exposures) * np.clip(eigenvalues, 0.0, None)
    total = float(variances.sum())
    shares = variances[variances > 0.0] / total
    entropy = float(-(shares * np.log(shares)).sum())
    return float(np.exp(entropy))


@dataclass(frozen=True, eq=False)
class FactorRiskDecomposition:
    """Le partage du risque entre facteurs communs et risque spécifique.

    Attributes:
        total_volatility: la volatilité du portefeuille sous le modèle.
        factor_volatility: la racine de la variance portée par les facteurs.
        specific_volatility: la racine de la variance idiosyncrasique.
        factor_contributions: la contribution de chaque facteur à la
            volatilité totale, en unité de volatilité.
        specific_contributions: la contribution spécifique de chaque actif,
            même unité.
        variance_residual: l'écart entre la variance calculée depuis la
            covariance implicite et la somme des deux blocs. Il doit valoir
            zéro à l'arrondi machine près, et sa publication est le contrôle
            de l'identité.
    """

    total_volatility: float
    factor_volatility: float
    specific_volatility: float
    factor_contributions: pd.Series
    specific_contributions: pd.Series
    variance_residual: float

    @property
    def factor_share(self) -> float:
        """La part de la variance totale portée par les facteurs communs."""
        return self.factor_volatility**2 / self.total_volatility**2

    @property
    def specific_share(self) -> float:
        """La part de la variance totale portée par le risque spécifique."""
        return self.specific_volatility**2 / self.total_volatility**2


def factor_risk_contribution(
    weights: Weights,
    exposures: pd.DataFrame,
    factor_covariance: pd.DataFrame,
    specific_variance: pd.Series,
    *,
    minimum_volatility: float = DEFAULT_MIN_VOLATILITY,
    symmetry_tolerance: float = DEFAULT_SYMMETRY_TOLERANCE,
    psd_tolerance: float = DEFAULT_PSD_TOLERANCE,
) -> FactorRiskDecomposition:
    r"""Sépare le risque du portefeuille entre facteurs communs et risque propre.

    **Le problème.** Sur mille actions, la covariance empirique porte 500 500
    paramètres, estimés sur quelques centaines de jours. Elle est alors de rang
    déficient et ses valeurs propres extrêmes sont fausses. Un modèle de
    facteurs remplace ces paramètres par un petit nombre d'expositions.

    **L'intuition.** Chaque actif est décrit par ses expositions à quelques
    forces communes, plus un résidu qui n'appartient qu'à lui. Le risque du
    portefeuille se scinde alors en deux blocs qui ne se recouvrent pas : ce
    qui vient des forces communes, et ce qui vient des résidus.

    .. math::

        \Sigma = B F B' + D, \qquad
        x = B' w, \qquad
        \sigma_p^2 = \underbrace{x' F x}_{\text{facteurs}}
                   + \underbrace{\sum_i w_i^2 d_i}_{\text{sp\'ecifique}}

    Le théorème d'Euler s'applique dans la base des facteurs de la même façon
    que dans celle des actifs, ce qui donne les contributions par facteur.

    .. math::

        FRC_k = \frac{x_k (F x)_k}{\sigma_p}, \qquad
        SRC_i = \frac{w_i^2 d_i}{\sigma_p}, \qquad
        \sum_k FRC_k + \sum_i SRC_i = \sigma_p

    Args:
        weights: les poids du portefeuille, indexés par actif.
        exposures: la matrice :math:`B`, lignes = actifs, colonnes = facteurs.
        factor_covariance: la matrice :math:`F`, indexée par les facteurs dans
            les deux dimensions.
        specific_variance: le vecteur :math:`d` des variances résiduelles,
            indexé par actif. Aucune valeur négative n'est acceptée.
        minimum_volatility: seuil en deçà duquel la division est refusée.
        symmetry_tolerance: voir :func:`check_covariance`.
        psd_tolerance: voir :func:`check_covariance`.

    Returns:
        Un :class:`FactorRiskDecomposition`, qui porte les deux blocs, les
        contributions détaillées et le résidu de l'identité de variance.

    Raises:
        DataQualityError: étiquettes incohérentes entre les quatre entrées,
            variance spécifique négative, valeur non finie, ou volatilité
            totale sous le seuil.

    Variables :
        :math:`B` les expositions, :math:`F` la covariance des facteurs,
        :math:`D` la diagonale des variances spécifiques, :math:`x` les
        expositions du portefeuille aux facteurs.

    Hypothèses :
        Les résidus sont non corrélés entre eux et avec les facteurs. C'est
        l'hypothèse qui rend :math:`D` diagonale, et c'est elle qui casse en
        premier : deux titres du même secteur gardent une corrélation
        résiduelle que le modèle ignore.

    Limites :
        La séparation dépend entièrement du jeu de facteurs choisi. Un risque
        que le modèle ne nomme pas se retrouve dans le bloc spécifique, où il
        paraît diversifiable alors qu'il ne l'est pas. La part spécifique d'un
        modèle pauvre est donc trompeusement rassurante.

    Alternatives :
        La décomposition directe par actif, :func:`risk_contribution`, qui ne
        demande aucun modèle mais hérite du bruit de la covariance empirique.
        Le modèle de facteurs est retenu quand le nombre d'actifs approche le
        nombre d'observations.

    Provenance :
        Rosenberg (1974), « Extra-Market Components of Covariance in Security
        Returns », Journal of Financial and Quantitative Analysis 9(2),
        pages 263 à 274. Puis Grinold et Kahn (1999), « Active Portfolio
        Management », 2e édition. Statut rapporté.

    Note:
        Vérification : la fonction reconstruit :math:`\Sigma = B F B' + D`,
        calcule :math:`w' \Sigma w` par ce chemin, et publie l'écart avec la
        somme des deux blocs dans ``variance_residual``. Un test exige que cet
        écart reste sous 1e-14 en relatif.
    """
    check_covariance(
        factor_covariance,
        symmetry_tolerance=symmetry_tolerance,
        psd_tolerance=psd_tolerance,
    )
    if len(weights) == 0:
        raise InsufficientDataError("le vecteur de poids est vide")
    if not exposures.index.equals(weights.index):
        raise DataQualityError("les lignes des expositions ne portent pas les mêmes actifs que les poids")
    if not exposures.columns.equals(factor_covariance.index):
        raise DataQualityError(
            "les colonnes des expositions ne portent pas les mêmes facteurs que leur covariance"
        )
    if not specific_variance.index.equals(weights.index):
        raise DataQualityError("la variance spécifique ne porte pas les mêmes actifs que les poids")

    w = weights.to_numpy(dtype=float)
    loadings = exposures.to_numpy(dtype=float)
    factor_cov = factor_covariance.to_numpy(dtype=float)
    specific = specific_variance.to_numpy(dtype=float)
    if not (np.isfinite(w).all() and np.isfinite(loadings).all() and np.isfinite(specific).all()):
        raise DataQualityError("une des entrées du modèle de facteurs porte une valeur non finie")
    if (specific < 0.0).any():
        raise DataQualityError("une variance spécifique est négative, ce qui n'existe pas")

    factor_exposure = loadings.T @ w
    factor_variance = float(factor_exposure @ factor_cov @ factor_exposure)
    specific_variance_total = float(np.square(w) @ specific)
    total_variance = factor_variance + specific_variance_total
    total_volatility = _require_positive_volatility(
        float(np.sqrt(max(total_variance, 0.0))), minimum_volatility
    )

    implied_covariance = loadings @ factor_cov @ loadings.T + np.diag(specific)
    residual = float(w @ implied_covariance @ w) - total_variance

    factor_contributions = pd.Series(
        factor_exposure * (factor_cov @ factor_exposure) / total_volatility,
        index=factor_covariance.index,
        name="factor_risk_contribution",
    )
    specific_contributions = pd.Series(
        np.square(w) * specific / total_volatility,
        index=weights.index,
        name="specific_risk_contribution",
    )
    return FactorRiskDecomposition(
        total_volatility=total_volatility,
        factor_volatility=float(np.sqrt(max(factor_variance, 0.0))),
        specific_volatility=float(np.sqrt(max(specific_variance_total, 0.0))),
        factor_contributions=factor_contributions,
        specific_contributions=specific_contributions,
        variance_residual=residual,
    )


def _group_labels(groups: Mapping[str, str] | pd.Series, assets: pd.Index) -> np.ndarray:
    """Rend l'étiquette de groupe de chaque actif, dans l'ordre de ``assets``.

    Raises:
        DataQualityError: un actif n'a pas de groupe déclaré.
    """
    mapping = groups.to_dict() if isinstance(groups, pd.Series) else dict(groups)
    missing = [asset for asset in assets if asset not in mapping]
    if missing:
        raise DataQualityError(f"{len(missing)} actif(s) sans groupe déclaré, dont {missing[0]!r}")
    return np.array([mapping[asset] for asset in assets], dtype=object)


def group_risk_contribution(
    weights: Weights,
    covariance: pd.DataFrame,
    groups: Mapping[str, str] | pd.Series,
    *,
    minimum_volatility: float = DEFAULT_MIN_VOLATILITY,
    symmetry_tolerance: float = DEFAULT_SYMMETRY_TOLERANCE,
    psd_tolerance: float = DEFAULT_PSD_TOLERANCE,
) -> pd.DataFrame:
    r"""Agrège poids et contributions au risque par secteur, classe ou stratégie.

    **Le problème.** Une liste de trois cents contributions par ligne ne se lit
    pas. Un comité veut savoir ce que portent l'énergie, les financières et le
    reste.

    **L'intuition.** Comme la décomposition est additive et sans reste, une
    contribution de groupe est la simple somme des contributions de ses
    membres. Aucun terme croisé ne se perd en chemin.

    .. math::

        RC_g = \sum_{i \in g} RC_i , \qquad \sum_g RC_g = \sigma_p

    Args:
        weights: les poids du portefeuille, indexés par actif.
        covariance: la covariance des rendements des mêmes actifs.
        groups: la correspondance actif vers groupe, dictionnaire ou série
            indexée par actif. Chaque actif de la covariance doit y figurer.
        minimum_volatility: seuil en deçà duquel la division est refusée.
        symmetry_tolerance: voir :func:`check_covariance`.
        psd_tolerance: voir :func:`check_covariance`.

    Returns:
        Un tableau indexé par groupe, dans l'ordre de première apparition dans
        la covariance. Il porte trois colonnes : ``weight`` la somme des poids,
        ``risk_contribution`` la somme des contributions, et
        ``risk_contribution_pct`` la part de volatilité du groupe.

    Raises:
        DataQualityError: un actif n'a pas de groupe, ou une entrée est
            invalide.

    Hypothèses :
        Les groupes forment une partition : un actif appartient à un groupe et
        à un seul. Une appartenance partielle, un conglomérat par exemple,
        n'est pas représentable ici.

    Limites :
        Le tableau compare des groupes de tailles différentes. Un groupe de
        cinquante lignes portera mécaniquement plus qu'un groupe de deux, et la
        colonne des poids est là pour que la lecture en tienne compte.

    Alternatives :
        Un modèle de facteurs sectoriels, qui sépare l'effet du secteur de
        celui du titre. L'agrégation directe est retenue quand la question est
        « qui porte le risque » et non « pourquoi ».

    Provenance :
        Litterman (1996) pour la décomposition, Roncalli (2013), « Introduction
        to Risk Parity and Budgeting », pour son usage en budget de risque par
        poche. Statut rapporté.

    Note:
        Vérification : la somme de la colonne ``risk_contribution`` égale la
        volatilité du portefeuille, et celle de ``risk_contribution_pct``
        vaut 1. Les deux sont testées.
    """
    w, cov, index = _aligned(
        weights, covariance, symmetry_tolerance=symmetry_tolerance, psd_tolerance=psd_tolerance
    )
    volatility = _require_positive_volatility(_volatility(w, cov), minimum_volatility)
    contributions = w * (cov @ w) / volatility
    frame = pd.DataFrame(
        {
            "group": _group_labels(groups, index),
            "weight": w,
            "risk_contribution": contributions,
        },
        index=index,
    )
    table = frame.groupby("group", sort=False)[["weight", "risk_contribution"]].sum()
    table["risk_contribution_pct"] = table["risk_contribution"] / volatility
    return table

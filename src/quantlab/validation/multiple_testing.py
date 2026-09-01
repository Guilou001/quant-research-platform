r"""Les corrections pour tests multiples, et le décompte honnête des essais.

**La réponse d'abord.** Un seuil de :math:`t = 2` ne veut plus rien dire dès que
plusieurs stratégies ont été essayées. Ce module rend le seuil qu'il faut
franchir à la place, et de combien un ratio de Sharpe doit être rabattu.

**Le problème.** Un test unique au seuil de 5 % se trompe une fois sur vingt.
Vingt tests indépendants menés sous l'hypothèse nulle produisent donc en moyenne
une découverte, et au moins une avec probabilité :math:`1 - 0{,}95^{20} = 0{,}642`.
Ce nombre est MODÉLISÉ, calcul direct. Le chercheur ne publie que la meilleure
des vingt, et il publie du bruit.

**Ce que le module contient.** Quatre procédures de correction des valeurs p,
un rabais de ratio de Sharpe et un seuil de :math:`t` exigé. Puis les deux
tests de comparaison multiple par bootstrap, celui de White (2000) et celui de
Hansen (2005). Enfin un registre qui compte les essais menés.

**Erreur familiale ou taux de fausses découvertes.** Les deux quantités
contrôlées ne sont pas la même chose, et le choix entre elles est une décision
de recherche, pas un détail technique.

Le taux d'erreur familial, la probabilité de commettre au moins une fausse
découverte dans toute la famille de tests, est ce que contrôlent Bonferroni et
Holm. Le contrôle est absolu : avec :math:`M` tests au seuil :math:`\alpha/M`,
la probabilité d'au moins un faux positif reste sous :math:`\alpha`, quel que
soit le nombre de tests. Le prix est la puissance, c'est-à-dire la capacité à
détecter ce qui existe vraiment. Avec 300 facteurs, le seuil individuel tombe à
0,017 %, et presque rien ne passe.

Le taux de fausses découvertes, la part attendue de fausses découvertes PARMI
les découvertes annoncées, est ce que contrôlent Benjamini et Hochberg (1995).
La différence est de nature. Accepter que 5 % des facteurs retenus soient faux
n'est pas la même promesse que d'écarter toute chance d'en retenir un seul de
faux. La seconde promesse coûte beaucoup plus cher, et la première suffit
souvent quand la suite du travail filtre les candidats.

**Pourquoi Benjamini-Yekutieli est plus dur que Benjamini-Hochberg.** La
procédure de 1995 contrôle le taux de fausses découvertes sous indépendance,
ou sous une forme précise de dépendance positive. Benjamini et Yekutieli (2001)
montrent que le contrôle survit à une dépendance ARBITRAIRE si l'on divise le
seuil par :math:`c(M) = \sum_{j=1}^{M} 1/j`. Ce facteur vaut 2,93 pour dix tests
et 6,33 pour 316. Le seuil est donc de deux à six fois plus dur, et c'est le
prix de ne rien supposer sur la structure de corrélation des essais.

**Le seuil de 3,0 de Harvey, Liu et Zhu.** Leur article recommande qu'un facteur
nouvellement découvert dépasse :math:`t = 3{,}0`, ce qui correspond à une valeur
p bilatérale de 0,27 %. Statut RAPPORTÉ, lu dans le résumé de la version NBER
w20592 le 2026-09-01. Ils ajoutent que 3,0 est probablement trop bas, leur
décompte de 316 facteurs ne couvrant ni les essais non publiés, ni la plupart
des documents de travail.

Références principales, toutes consultées le 2026-09-01 :

- Harvey, C. R., Liu, Y. et Zhu, H. (2016). « ... and the Cross-Section of
  Expected Returns ». *Review of Financial Studies*, 29(1), p. 5-68.
  Version NBER w20592 lue en entier.
- Harvey, C. R. et Liu, Y. (2015). « Backtesting ». *Journal of Portfolio
  Management*, 42(1), p. 13-28.
- White, H. (2000). « A Reality Check for Data Snooping ». *Econometrica*,
  68(5), p. 1097-1126.
- Hansen, P. R. (2005). « A Test for Superior Predictive Ability ». *Journal of
  Business and Economic Statistics*, 23(4), p. 365-380. Lu en entier.
- Benjamini, Y. et Hochberg, Y. (1995) ; Benjamini, Y. et Yekutieli, D. (2001).
- Bailey, D. et López de Prado, M. (2014). « The Deflated Sharpe Ratio ».
  *Journal of Portfolio Management*, 40(5), p. 94-107.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Literal, Protocol

import numpy as np
import pandas as pd
from scipy import stats

from quantlab.analytics.returns import align_returns
from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.logging import get_logger
from quantlab.core.types import Frequency, ReturnFrame, ReturnSeries

log = get_logger(__name__)

#: Les quatre procédures reconnues par ce module.
MultipleTestingMethod = Literal["bonferroni", "holm", "benjamini_hochberg", "benjamini_yekutieli"]

#: Les noms alternatifs acceptés. « bhy » est le nom qu'emploient Harvey, Liu et
#: Zhu (2016) pour la variante de Benjamini, Hochberg et Yekutieli sous
#: dépendance arbitraire, celle de Benjamini et Yekutieli (2001).
_METHOD_ALIASES: dict[str, str] = {
    "bonferroni": "bonferroni",
    "holm": "holm",
    "bh": "benjamini_hochberg",
    "fdr_bh": "benjamini_hochberg",
    "benjamini_hochberg": "benjamini_hochberg",
    "by": "benjamini_yekutieli",
    "bhy": "benjamini_yekutieli",
    "fdr_by": "benjamini_yekutieli",
    "benjamini_yekutieli": "benjamini_yekutieli",
}

#: Seuil de valeur de :math:`t` recommandé par Harvey, Liu et Zhu (2016) pour un
#: facteur nouvellement découvert. Statut RAPPORTÉ, résumé de la version NBER
#: w20592 lu le 2026-09-01. Les auteurs le jugent eux-mêmes trop bas.
HLZ_RECOMMENDED_TSTAT: float = 3.0

#: Seuils de :math:`t` publiés par Harvey, Liu et Zhu (2016) pour 2012, avec 316
#: facteurs recensés. Statut RAPPORTÉ, section 4.6 et figure 3 de la version
#: NBER. Bonferroni et Holm au seuil familial de 5 %, Benjamini-Yekutieli au
#: taux de fausses découvertes de 1 % puis de 5 %.
HLZ_2012_THRESHOLDS: dict[str, float] = {
    "bonferroni": 3.78,
    "holm": 3.64,
    "benjamini_yekutieli_1pct": 3.39,
    "benjamini_yekutieli_5pct": 2.78,
}

#: Nombre de facteurs recensés par Harvey, Liu et Zhu (2016) en 2012, documents
#: de travail compris. Statut RAPPORTÉ.
HLZ_2012_FACTOR_COUNT: int = 316


def _normalize_method(method: str) -> str:
    """Rend le nom canonique d'une procédure, ou lève une :class:`ConfigError`."""
    key = method.strip().lower()
    if key not in _METHOD_ALIASES:
        attendus = sorted(set(_METHOD_ALIASES))
        raise ConfigError(f"method vaut {method!r}, attendu l'un de {attendus}")
    return _METHOD_ALIASES[key]


def _as_pvalues(pvalues: Sequence[float] | np.ndarray | pd.Series) -> np.ndarray:
    """Valide un vecteur de valeurs p et le rend en tableau NumPy de flottants.

    Args:
        pvalues: les valeurs p brutes, une par test.

    Returns:
        Un tableau unidimensionnel de flottants.

    Raises:
        InsufficientDataError: si le vecteur est vide.
        DataQualityError: si une valeur manque ou sort de l'intervalle unité.
    """
    arr = np.asarray(pvalues, dtype=float).ravel()
    if arr.size == 0:
        raise InsufficientDataError("le vecteur de valeurs p est vide")
    if not np.all(np.isfinite(arr)):
        raise DataQualityError("une valeur p est manquante ou infinie")
    if np.any(arr < 0.0) or np.any(arr > 1.0):
        raise DataQualityError("une valeur p sort de l'intervalle [0, 1]")
    return arr


def _check_alpha(alpha: float) -> float:
    """Valide un seuil de signification strictement compris entre 0 et 1."""
    if not (0.0 < alpha < 1.0):
        raise ConfigError(f"alpha vaut {alpha}, attendu strictement entre 0 et 1")
    return float(alpha)


def benjamini_yekutieli_constant(n_tests: int) -> float:
    r"""Rend le facteur de pénalité de dépendance arbitraire de Benjamini-Yekutieli.

    **(1) Le problème.** La procédure de Benjamini et Hochberg (1995) ne contrôle
    le taux de fausses découvertes que sous indépendance, ou sous une dépendance
    positive d'une forme précise. Des essais de stratégies sont corrélés dans
    tous les sens, y compris négativement.

    **(2) L'intuition.** Benjamini et Yekutieli (2001) rendent le contrôle valide
    sous n'importe quelle structure de dépendance en resserrant le seuil d'un
    facteur qui croît comme le logarithme du nombre de tests. Aucune hypothèse
    n'est alors faite sur la corrélation.

    **(3) La formule.**

    .. math::

        c(M) = \sum_{j=1}^{M} \frac{1}{j}

    **(4) Les variables.** :math:`M` est le nombre de tests de la famille.

    **(5) Les hypothèses.** Aucune. C'est précisément l'objet de ce facteur.

    **(6) La provenance.** Benjamini, Y. et Yekutieli, D. (2001), « The Control of
    the False Discovery Rate in Multiple Testing under Dependency », *Annals of
    Statistics*, 29(4), p. 1165-1188. Notation reprise par Harvey, Liu et Zhu
    (2016), section 4.4.3.

    **(7) Les limites.** Le facteur est une borne du pire cas. Sous dépendance
    positive, il est inutilement dur, et le taux de fausses découvertes réellement
    obtenu tombe bien sous le seuil visé.

    **(8) Les alternatives.** Garder :math:`c(M) = 1`, qui est la procédure de
    Benjamini-Hochberg, valide sous dépendance positive de régression.

    **(9) Pourquoi celle-ci.** Les corrélations entre essais d'une même famille
    de stratégies ne sont pas connues, et les supposer positives est une
    supposition gratuite.

    **(10) Comment vérifier.** Le nombre harmonique de dix vaut 2,928968, et
    celui de 316 vaut 6,334539. Le test du module les compare à une somme écrite
    à la main.

    Args:
        n_tests: le nombre de tests de la famille, au moins 1.

    Returns:
        Le nombre harmonique :math:`c(M)`, supérieur ou égal à 1.

    Raises:
        ConfigError: si le nombre de tests est inférieur à 1.
    """
    if n_tests < 1:
        raise ConfigError(f"n_tests vaut {n_tests}, attendu au moins 1")
    return float(np.sum(1.0 / np.arange(1, n_tests + 1, dtype=float)))


@dataclass(frozen=True, slots=True, eq=False)
class MultipleTestingResult:
    """Le résultat d'une correction pour tests multiples.

    Attributes:
        method: le nom canonique de la procédure appliquée.
        alpha: le seuil visé, taux d'erreur familial ou taux de fausses
            découvertes selon la procédure.
        n_tests: le nombre de tests de la famille.
        pvalues: les valeurs p brutes, dans l'ordre reçu.
        adjusted_pvalues: les valeurs p ajustées, dans l'ordre reçu. Une valeur
            ajustée se compare directement à ``alpha``.
        rejected: les hypothèses nulles rejetées, dans l'ordre reçu.
        effective_threshold: le seuil effectif sur les valeurs p BRUTES. C'est la
            plus grande valeur p brute déclarée significative si au moins une
            l'est. Sinon, c'est le seuil qu'aurait dû franchir la plus petite
            valeur p pour l'être.
        controls: ce que la procédure contrôle, ``"FWER"`` ou ``"FDR"``.
    """

    method: str
    alpha: float
    n_tests: int
    pvalues: np.ndarray
    adjusted_pvalues: np.ndarray
    rejected: np.ndarray
    effective_threshold: float
    controls: Literal["FWER", "FDR"]

    @property
    def n_rejected(self) -> int:
        """Le nombre d'hypothèses nulles rejetées."""
        return int(np.count_nonzero(self.rejected))


def bonferroni(
    pvalues: Sequence[float] | np.ndarray | pd.Series,
    alpha: float = 0.05,
) -> MultipleTestingResult:
    r"""Applique la correction de Bonferroni, en une seule étape.

    **(1) Le problème.** Mener :math:`M` tests au seuil individuel de 5 % laisse
    une probabilité proche de 1 de commettre au moins une fausse découverte dès
    que :math:`M` dépasse quelques dizaines.

    **(2) L'intuition.** L'inégalité de Boole borne la probabilité d'une union
    par la somme des probabilités. Diviser le seuil individuel par le nombre de
    tests suffit donc à borner la probabilité d'au moins un faux positif, sans
    rien supposer sur la dépendance entre les tests.

    **(3) La formule.**

    .. math::

        p_i^{\text{Bonferroni}} = \min\left[M p_i,\; 1\right],
        \qquad
        \text{rejeter } H_i \text{ si } p_i \le \frac{\alpha}{M}

    **(4) Les variables.** :math:`p_i` la valeur p brute du test :math:`i`,
    :math:`M` le nombre de tests, :math:`\alpha` le taux d'erreur familial visé.

    **(5) Les hypothèses.** Aucune sur la dépendance des tests. C'est la
    propriété qui explique sa longévité.

    **(6) La provenance.** Formulation reprise de Harvey, Liu et Zhu (2016),
    section 4.4.1, qui l'écrivent exactement sous cette forme.

    **(7) Les limites.** La procédure perd toute puissance quand le nombre de
    tests est grand. Avec 316 facteurs, le seuil individuel tombe à 0,0158 %,
    ce qui exige une valeur de :math:`t` de 3,78 en bilatéral, MESURÉ.

    **(8) Les alternatives.** Holm, uniformément plus puissante et tout aussi
    valide. Benjamini-Hochberg, qui contrôle une autre quantité.

    **(9) Pourquoi celle-ci.** Elle sert de repère, parce qu'elle est la plus
    connue et la plus sévère des quatre. Un résultat qui la passe ne dépend
    d'aucune hypothèse de dépendance.

    **(10) Comment vérifier.** Le test du module la compare à
    ``statsmodels.stats.multitest.multipletests(method="bonferroni")``.

    Args:
        pvalues: les valeurs p brutes, une par test.
        alpha: le taux d'erreur familial visé.

    Returns:
        Le résultat complet, valeurs p ajustées comprises.

    Raises:
        DataQualityError: si une valeur p sort de l'intervalle unité.
        InsufficientDataError: si le vecteur est vide.
        ConfigError: si ``alpha`` n'est pas strictement entre 0 et 1.
    """
    p = _as_pvalues(pvalues)
    a = _check_alpha(alpha)
    m = p.size
    adjusted = np.minimum(m * p, 1.0)
    seuil = a / m
    rejected = p <= seuil
    return MultipleTestingResult(
        method="bonferroni",
        alpha=a,
        n_tests=m,
        pvalues=p,
        adjusted_pvalues=adjusted,
        rejected=rejected,
        effective_threshold=float(p[rejected].max()) if rejected.any() else seuil,
        controls="FWER",
    )


def holm(
    pvalues: Sequence[float] | np.ndarray | pd.Series,
    alpha: float = 0.05,
) -> MultipleTestingResult:
    r"""Applique la correction séquentielle descendante de Holm (1979).

    **(1) Le problème.** Bonferroni applique le même seuil dur à tous les tests,
    y compris au plus significatif d'entre eux, alors qu'une fois une hypothèse
    rejetée il ne reste plus que :math:`M-1` tests à protéger.

    **(2) L'intuition.** Trier les valeurs p, puis relâcher le seuil d'un cran à
    chaque rejet. Le premier test affronte :math:`\alpha/M`, le deuxième
    :math:`\alpha/(M-1)`, et ainsi de suite. La procédure s'arrête au premier
    échec, et tout ce qui suit est conservé.

    **(3) La formule.** Avec les valeurs p triées
    :math:`p_{(1)} \le \cdots \le p_{(M)}` :

    .. math::

        p_{(i)}^{\text{Holm}} =
        \min\left[\max_{j \le i}\left\{(M - j + 1)\, p_{(j)}\right\},\; 1\right]

    La règle équivalente rejette :math:`H_{(1)}, \ldots, H_{(k-1)}`, où
    :math:`k` est le plus petit indice tel que
    :math:`p_{(k)} > \alpha / (M + 1 - k)`.

    **(4) Les variables.** :math:`p_{(i)}` la :math:`i`-ième plus petite valeur p,
    :math:`M` le nombre de tests, :math:`\alpha` le taux d'erreur familial.

    **(5) Les hypothèses.** Aucune sur la dépendance, comme Bonferroni.

    **(6) La provenance.** Holm, S. (1979), « A Simple Sequentially Rejective
    Multiple Test Procedure », *Scandinavian Journal of Statistics*, 6(2),
    p. 65-70. Formulation reprise de Harvey, Liu et Zhu (2016), section 4.4.2.

    **(7) Les limites.** Le gain sur Bonferroni est faible quand peu
    d'hypothèses sont fausses. Sur le plus petit des essais, les deux procédures
    coïncident exactement, puisque :math:`\alpha/M = \alpha/(M+1-1)`.

    **(8) Les alternatives.** Hochberg (1988) et Hommel (1988), plus puissantes
    mais valides seulement sous dépendance positive.

    **(9) Pourquoi celle-ci.** Elle domine uniformément Bonferroni, sans coûter
    d'hypothèse supplémentaire. Tout ce que Bonferroni rejette, Holm le rejette.

    **(10) Comment vérifier.** Le test du module la compare à
    ``statsmodels.stats.multitest.multipletests(method="holm")``, et vérifie que
    Holm rejette au moins tout ce que rejette Bonferroni.

    Args:
        pvalues: les valeurs p brutes, une par test.
        alpha: le taux d'erreur familial visé.

    Returns:
        Le résultat complet, valeurs p ajustées comprises.
    """
    p = _as_pvalues(pvalues)
    a = _check_alpha(alpha)
    m = p.size
    ordre = np.argsort(p, kind="stable")
    triees = p[ordre]
    facteurs = np.arange(m, 0, -1, dtype=float)
    adjusted_triees = np.minimum(np.maximum.accumulate(facteurs * triees), 1.0)
    adjusted = np.empty_like(adjusted_triees)
    adjusted[ordre] = adjusted_triees
    rejected = adjusted <= a
    seuil_du_plus_petit = a / m
    return MultipleTestingResult(
        method="holm",
        alpha=a,
        n_tests=m,
        pvalues=p,
        adjusted_pvalues=adjusted,
        rejected=rejected,
        effective_threshold=(float(p[rejected].max()) if rejected.any() else seuil_du_plus_petit),
        controls="FWER",
    )


def _step_up_fdr(p: np.ndarray, alpha: float, penalty: float) -> tuple[np.ndarray, np.ndarray, float]:
    """Applique une procédure ascendante de contrôle du taux de fausses découvertes.

    La pénalité vaut 1 pour Benjamini-Hochberg et :math:`c(M)` pour
    Benjamini-Yekutieli. Le reste du calcul est identique.

    Args:
        p: les valeurs p brutes.
        alpha: le taux de fausses découvertes visé.
        penalty: le facteur :math:`c(M)`.

    Returns:
        Les valeurs p ajustées dans l'ordre reçu, les rejets, et le seuil
        effectif sur les valeurs p brutes.
    """
    m = p.size
    ordre = np.argsort(p, kind="stable")
    triees = p[ordre]
    rangs = np.arange(1, m + 1, dtype=float)
    brut = penalty * m / rangs * triees
    adjusted_triees = np.minimum(np.minimum.accumulate(brut[::-1])[::-1], 1.0)
    adjusted = np.empty_like(adjusted_triees)
    adjusted[ordre] = adjusted_triees
    rejected = adjusted <= alpha
    seuil = float(p[rejected].max()) if rejected.any() else alpha / (m * penalty)
    return adjusted, rejected, seuil


def benjamini_hochberg(
    pvalues: Sequence[float] | np.ndarray | pd.Series,
    alpha: float = 0.05,
) -> MultipleTestingResult:
    r"""Contrôle le taux de fausses découvertes par la procédure de 1995.

    **(1) Le problème.** Contrôler la probabilité de commettre au moins une
    fausse découverte est trop dur quand des centaines d'hypothèses sont testées.
    La question utile devient : parmi ce que j'annonce, quelle part est fausse ?

    **(2) L'intuition.** Trier les valeurs p, puis chercher le plus GRAND rang
    dont la valeur p reste sous une droite passant par l'origine et de pente
    :math:`\alpha/M`. Tout ce qui est en dessous de ce rang est retenu. Plus il y
    a de vraies découvertes, plus la barre se relâche.

    **(3) La formule.** Rejeter :math:`H_{(1)}, \ldots, H_{(k)}`, où :math:`k`
    est le plus grand indice tel que :math:`p_{(k)} \le k\alpha/M`. La valeur p
    ajustée équivalente se lit de la plus grande à la plus petite :

    .. math::

        p_{(i)}^{\text{BH}} = \min\left[\min_{j \ge i}
        \left\{\frac{M}{j} p_{(j)}\right\},\; 1\right]

    **(4) Les variables.** :math:`p_{(i)}` la :math:`i`-ième plus petite valeur p,
    :math:`M` le nombre de tests, :math:`\alpha` le taux de fausses découvertes.

    **(5) Les hypothèses.** Indépendance des tests, ou dépendance positive de
    régression sur chaque sous-ensemble. Sous dépendance quelconque, le contrôle
    n'est plus garanti.

    **(6) La provenance.** Benjamini, Y. et Hochberg, Y. (1995), « Controlling
    the False Discovery Rate », *Journal of the Royal Statistical Society B*,
    57(1), p. 289-300.

    **(7) Les limites.** Le contrôle porte sur une ESPÉRANCE. Sur une famille
    donnée, la part de faux positifs réalisée peut dépasser le seuil visé, et la
    procédure ne dit rien de cette dispersion.

    **(8) Les alternatives.** Benjamini-Yekutieli quand la dépendance est
    inconnue. Storey (2002) quand la part d'hypothèses nulles vraies est estimée.

    **(9) Pourquoi celle-ci.** Sur une famille d'essais de stratégies, retenir
    dix candidats dont un est faux est un résultat exploitable. N'en retenir
    aucun par crainte du faux unique ne l'est pas.

    **(10) Comment vérifier.** Le test du module la compare à
    ``statsmodels.stats.multitest.multipletests(method="fdr_bh")``.

    Args:
        pvalues: les valeurs p brutes, une par test.
        alpha: le taux de fausses découvertes visé.

    Returns:
        Le résultat complet, valeurs p ajustées comprises.
    """
    p = _as_pvalues(pvalues)
    a = _check_alpha(alpha)
    adjusted, rejected, seuil = _step_up_fdr(p, a, 1.0)
    return MultipleTestingResult(
        method="benjamini_hochberg",
        alpha=a,
        n_tests=p.size,
        pvalues=p,
        adjusted_pvalues=adjusted,
        rejected=rejected,
        effective_threshold=seuil,
        controls="FDR",
    )


def benjamini_yekutieli(
    pvalues: Sequence[float] | np.ndarray | pd.Series,
    alpha: float = 0.05,
) -> MultipleTestingResult:
    r"""Contrôle le taux de fausses découvertes sous dépendance arbitraire.

    **(1) Le problème.** Les essais d'une même famille de stratégies partagent
    leurs données, leurs actifs et souvent leur signal. La dépendance positive
    exigée par Benjamini-Hochberg n'est ni vérifiée, ni vérifiable ici.

    **(2) L'intuition.** Resserrer la droite de rejet d'un facteur qui suffit au
    pire cas de dépendance. Ce facteur est le nombre harmonique, qui croît comme
    le logarithme du nombre de tests, donc lentement.

    **(3) La formule.** Rejeter :math:`H_{(1)}, \ldots, H_{(k)}`, où :math:`k`
    est le plus grand indice tel que
    :math:`p_{(k)} \le \frac{k}{M\, c(M)}\alpha`, avec
    :math:`c(M) = \sum_{j=1}^{M} 1/j`. La valeur p ajustée s'écrit
    séquentiellement, en partant de la plus grande :

    .. math::

        p_{(i)}^{\text{BY}} =
        \begin{cases}
        p_{(M)} & i = M \\
        \min\left[p_{(i+1)}^{\text{BY}},\;
        \dfrac{M\, c(M)}{i} p_{(i)}\right] & i \le M-1
        \end{cases}

    **(4) Les variables.** Celles de Benjamini-Hochberg, plus le facteur
    :math:`c(M)`.

    **(5) Les hypothèses.** Aucune sur la structure de dépendance.

    **(6) La provenance.** Benjamini et Yekutieli (2001). Écriture séquentielle
    reprise de Harvey, Liu et Zhu (2016), section 4.4.3, qui la notent BHY.

    **(7) Les limites.** Le facteur est celui du pire cas, et il est très
    conservateur quand les essais sont en fait positivement corrélés. Sur 316
    tests, il multiplie le seuil exigé par 6,33, MESURÉ.

    **(8) Les alternatives.** Benjamini-Hochberg si l'on accepte l'hypothèse de
    dépendance positive. Une correction par bootstrap qui estime la dépendance
    plutôt que de la borner, comme Romano et Wolf (2005).

    **(9) Pourquoi celle-ci.** C'est la seule des quatre qui contrôle le taux de
    fausses découvertes sans rien supposer, et Harvey, Liu et Zhu en font leur
    recommandation principale.

    **(10) Comment vérifier.** Le test du module la compare à
    ``statsmodels.stats.multitest.multipletests(method="fdr_by")``, et vérifie
    qu'elle est toujours au moins aussi dure que Benjamini-Hochberg.

    Args:
        pvalues: les valeurs p brutes, une par test.
        alpha: le taux de fausses découvertes visé.

    Returns:
        Le résultat complet, valeurs p ajustées comprises.
    """
    p = _as_pvalues(pvalues)
    a = _check_alpha(alpha)
    adjusted, rejected, seuil = _step_up_fdr(p, a, benjamini_yekutieli_constant(p.size))
    return MultipleTestingResult(
        method="benjamini_yekutieli",
        alpha=a,
        n_tests=p.size,
        pvalues=p,
        adjusted_pvalues=adjusted,
        rejected=rejected,
        effective_threshold=seuil,
        controls="FDR",
    )


_PROCEDURES = {
    "bonferroni": bonferroni,
    "holm": holm,
    "benjamini_hochberg": benjamini_hochberg,
    "benjamini_yekutieli": benjamini_yekutieli,
}


def adjust_pvalues(
    pvalues: Sequence[float] | np.ndarray | pd.Series,
    *,
    method: str = "holm",
    alpha: float = 0.05,
) -> MultipleTestingResult:
    """Applique la procédure nommée, sans avoir à choisir la fonction à la main.

    Args:
        pvalues: les valeurs p brutes, une par test.
        method: ``"bonferroni"``, ``"holm"``, ``"benjamini_hochberg"`` ou
            ``"benjamini_yekutieli"``. Les alias ``"bh"``, ``"by"`` et ``"bhy"``
            sont acceptés.
        alpha: le seuil visé.

    Returns:
        Le résultat de la procédure choisie.

    Raises:
        ConfigError: si la procédure est inconnue.
    """
    return _PROCEDURES[_normalize_method(method)](pvalues, alpha)


def required_tstat(
    n_tests: int,
    alpha: float = 0.05,
    *,
    method: str = "bonferroni",
) -> float:
    r"""Rend le seuil de :math:`t` qu'un essai doit franchir après correction.

    **(1) Le problème.** Un chercheur qui a essayé 300 stratégies veut savoir
    quelle valeur de :math:`t` compte encore comme une découverte. Le seuil de
    1,96 ne répond plus à cette question.

    **(2) L'intuition.** La correction agit sur les valeurs p, pas sur les
    statistiques. Il suffit donc de convertir le seuil corrigé en une valeur de
    :math:`t`. La loi normale centrée réduite y remplace la loi de Student.

    **(3) La formule.** Pour Bonferroni, Holm et Benjamini-Hochberg, le seuil qui
    s'applique au PLUS SIGNIFICATIF des essais est le même :

    .. math::

        t^{*} = \Phi^{-1}\!\left(1 - \frac{\alpha}{2M}\right)

    Pour Benjamini-Yekutieli, il se resserre du facteur :math:`c(M)` :

    .. math::

        t^{*}_{BY} = \Phi^{-1}\!\left(1 - \frac{\alpha}{2 M c(M)}\right)

    **(4) Les variables.** :math:`M` le nombre d'essais, :math:`\alpha` le seuil
    visé, :math:`\Phi^{-1}` la fonction quantile de la loi normale centrée
    réduite. Le facteur 2 vient du test BILATÉRAL, convention de Harvey, Liu et
    Zhu, vérifiée sur leurs propres nombres.

    **(5) Les hypothèses.** Deux, et elles comptent. La loi normale approche la
    loi de Student, ce qui est raisonnable au-delà de cent observations. Et
    l'essai considéré est le plus significatif des :math:`M`, ce qui est le cas
    d'usage : on rabat le meilleur candidat, pas un candidat au hasard.

    **(6) La provenance.** Harvey, Liu et Zhu (2016), sections 4.4 et 4.6. Ils
    écrivent explicitement transformer les valeurs p corrigées en valeurs de
    :math:`t` en supposant la loi normale.

    **(7) Les limites, et c'est le point important.** Pour Holm et pour les deux
    procédures de taux de fausses découvertes, le vrai seuil DÉPEND des autres
    essais. Cette fonction ne connaît pas leurs valeurs p. Ce qu'elle rend est
    donc le seuil GARANTI, celui qui s'applique quand aucun autre essai n'est
    significatif. C'est une borne supérieure du seuil réel.

    L'écart n'est pas anecdotique. Harvey, Liu et Zhu obtiennent 3,39 en 2012
    avec Benjamini-Yekutieli à 1 %, parce qu'ils appliquent la procédure aux 316
    valeurs p observées. Cette fonction rend 4,56 pour les mêmes entrées, MESURÉ,
    parce qu'elle n'a pas ces valeurs p. Leur chiffre de 3,39 est RAPPORTÉ.

    **(8) Les alternatives.** Passer par :func:`adjust_pvalues` avec le vecteur
    complet des valeurs p des essais, ce qui rend le seuil exact. Ou passer par
    le ratio de Sharpe dégonflé, qui répond à la même question par la théorie des
    valeurs extrêmes.

    **(9) Pourquoi celle-ci.** Elle donne un ordre de grandeur immédiat, sans
    exiger le registre complet des essais, et elle se trompe du bon côté.

    **(10) Comment vérifier.** À 316 essais et 5 %, la formule de Bonferroni doit
    rendre 3,78, valeur publiée par Harvey, Liu et Zhu pour 2012. Le test du
    module le contrôle.

    Args:
        n_tests: le nombre d'essais menés, au moins 1.
        alpha: le seuil visé, familial pour Bonferroni et Holm, taux de fausses
            découvertes pour les deux autres.
        method: la procédure, mêmes noms que :func:`adjust_pvalues`.

    Returns:
        Le seuil de :math:`t` en valeur absolue, pour un test bilatéral.

    Raises:
        ConfigError: si le nombre d'essais est inférieur à 1, si ``alpha`` sort
            de l'intervalle ouvert, ou si la procédure est inconnue.

    Example:
        Sans aucun essai concurrent, le seuil retombe sur le seuil usuel.

        >>> round(required_tstat(1, 0.05), 4)
        1.96
    """
    if n_tests < 1:
        raise ConfigError(f"n_tests vaut {n_tests}, attendu au moins 1")
    a = _check_alpha(alpha)
    canonique = _normalize_method(method)
    penalite = benjamini_yekutieli_constant(n_tests) if canonique == "benjamini_yekutieli" else 1.0
    return float(stats.norm.ppf(1.0 - a / (2.0 * n_tests * penalite)))


@dataclass(frozen=True, slots=True)
class HaircutResult:
    """Le rabais appliqué à un ratio de Sharpe pour tenir compte des essais.

    Attributes:
        method: la procédure de correction appliquée.
        n_tests: le nombre d'essais déclarés.
        n_obs: le nombre d'observations de la série de rendements.
        frequency: la fréquence d'observation.
        observed_sr: le ratio de Sharpe annoncé, dans l'unité reçue.
        observed_tstat: la statistique :math:`t` correspondante.
        single_pvalue: la valeur p bilatérale d'un test unique.
        adjusted_pvalue: la valeur p après correction pour tests multiples.
        adjusted_tstat: la statistique :math:`t` que rend la valeur p corrigée.
        haircut_sr: le ratio de Sharpe rabattu, dans la même unité que
            ``observed_sr``.
        haircut_fraction: la part du ratio de Sharpe effacée par le rabais.
        annualized: vrai si les deux ratios sont exprimés en annualisé.
    """

    method: str
    n_tests: int
    n_obs: int
    frequency: Frequency
    observed_sr: float
    observed_tstat: float
    single_pvalue: float
    adjusted_pvalue: float
    adjusted_tstat: float
    haircut_sr: float
    haircut_fraction: float
    annualized: bool


def haircut_sharpe(
    observed_sr: float,
    *,
    n_tests: int,
    n_obs: int,
    frequency: Frequency,
    method: str = "holm",
    annualized: bool = True,
    other_pvalues: Sequence[float] | np.ndarray | None = None,
    periods_per_year: float | None = None,
) -> HaircutResult:
    r"""Rabat un ratio de Sharpe pour tenir compte du nombre d'essais menés.

    **(1) Le problème.** Un ratio de Sharpe de 1,0 sur dix ans de données
    mensuelles est très significatif s'il vient d'un essai unique. Il ne l'est
    plus s'il est le meilleur de cent essais. Le nombre annoncé est le même, et
    ce qu'il vaut ne l'est pas.

    **(2) L'intuition.** Un ratio de Sharpe est une statistique de test
    déguisée. On le convertit en valeur de :math:`t`, on corrige la valeur p
    associée pour le nombre d'essais, puis on refait le chemin en sens inverse.
    Le ratio de Sharpe qui ressort est celui qui aurait produit cette valeur p
    corrigée dans un test unique.

    **(3) La formule.** Avec :math:`T` observations et :math:`N` périodes par an :

    .. math::

        t = \widehat{SR}_{\text{p\'eriodique}} \sqrt{T},
        \qquad
        p = 2\left(1 - \Phi(t)\right)

    .. math::

        p^{\text{adj}} = \text{correction}(p, M),
        \qquad
        t^{\text{adj}} = \Phi^{-1}\!\left(1 - \frac{p^{\text{adj}}}{2}\right)

    .. math::

        \widehat{SR}^{\text{adj}} = \frac{t^{\text{adj}}}{\sqrt{T}},
        \qquad
        \text{rabais} =
        \frac{\widehat{SR} - \widehat{SR}^{\text{adj}}}{\widehat{SR}}

    **(4) Les variables.** :math:`\widehat{SR}` le ratio de Sharpe annoncé,
    :math:`T` le nombre d'observations, :math:`M` le nombre d'essais,
    :math:`\Phi` la fonction de répartition normale centrée réduite. Le ratio
    annualisé se relie au périodique par :math:`\widehat{SR}_{\text{ann}} =
    \widehat{SR}_{\text{p\'eriodique}}\sqrt{N}`.

    **(5) Les hypothèses.** Rendements indépendants et de variance finie, loi
    normale pour l'approximation de la statistique, et essais dont le nombre est
    connu. Aucune des trois n'est innocente.

    **(6) La provenance.** Harvey, C. R. et Liu, Y. (2015), « Backtesting »,
    *Journal of Portfolio Management*, 42(1), p. 13-28. La correspondance
    :math:`t = \widehat{SR}\sqrt{T}` et la définition du rabais en pourcentage
    sont celles de leur article et de leur code publié.

    **(7) Ce que cette implémentation FAIT et NE FAIT PAS.** Elle fait le chemin
    aller-retour décrit ci-dessus, avec les quatre procédures du module. Elle ne
    fait PAS trois choses de l'article original, et les taire serait mentir.

    D'abord, Harvey et Liu SIMULENT la distribution des valeurs p des essais non
    observés, à partir d'un modèle ajusté sur les facteurs publiés. Sans le
    vecteur des autres essais, les trois premières procédures rendent la même
    DÉCISION sur le meilleur essai, leur seuil de rejet au premier rang valant
    :math:`\alpha/M` dans les trois cas.

    La valeur p ajustée rendue, elle, n'est exacte que pour Bonferroni et Holm.
    Pour Benjamini-Hochberg comme pour Benjamini-Yekutieli, c'est une BORNE
    SUPÉRIEURE, donc un rabais trop dur plutôt que trop doux. Le détail et un
    contre-exemple chiffré vivent dans :func:`_adjusted_pvalue_of_best`.
    L'argument ``other_pvalues`` permet de fournir les autres valeurs p et de
    retrouver alors les procédures complètes, exactement.

    Ensuite, elle n'applique aucune correction d'autocorrélation des rendements,
    là où l'article en propose une qui réduit le nombre d'observations
    effectives. Une autocorrélation positive rend donc ce rabais TROP FAIBLE.

    Enfin, elle ne déduit pas un nombre d'essais indépendants depuis leur
    corrélation moyenne. :class:`TrialCounter` le fait séparément, selon Bailey
    et López de Prado (2014).

    **(8) Les alternatives.** Le ratio de Sharpe dégonflé traite le même
    problème par la loi du maximum plutôt que par une correction de valeurs p
    brutes. Son rabais vit dans ``quantlab.validation.dsr.haircut``, qui rapporte le
    seuil de chance au ratio observé. Les deux nombres ne sont pas le même, et
    les deux docstrings le disent. Les tests de White et de Hansen, eux,
    travaillent sur les séries de rendements plutôt que sur un ratio résumé.

    **(9) Pourquoi celle-ci.** Elle ne demande que trois nombres, ce qui la rend
    applicable à un résultat publié dont on ne possède pas les rendements.

    **(10) Comment vérifier.** À un seul essai, le rabais doit être exactement
    nul, quelle que soit la procédure. Le rabais doit croître avec le nombre
    d'essais. Le test du module contrôle les deux, plus un calcul à la main.

    Args:
        observed_sr: le ratio de Sharpe annoncé, strictement positif.
        n_tests: le nombre d'essais menés, au moins 1.
        n_obs: le nombre d'observations de la série, au moins 2.
        frequency: la fréquence d'observation, qui donne l'annualisation.
        method: la procédure de correction, mêmes noms que :func:`adjust_pvalues`.
        annualized: vrai si ``observed_sr`` est annualisé, ce qui est l'usage.
        other_pvalues: les valeurs p des autres essais, si elles sont connues.
            Sans elles, la correction porte sur le seul essai observé.
        periods_per_year: comptage mesuré du nombre de périodes par an, qui
            remplace la convention de la fréquence.

    Returns:
        Le détail complet du rabais.

    Raises:
        ConfigError: si un argument sort de son domaine.
    """
    if observed_sr <= 0.0:
        raise ConfigError(
            f"observed_sr vaut {observed_sr}, attendu strictement positif : "
            "rabattre un ratio de Sharpe négatif n'a pas de sens"
        )
    if n_tests < 1:
        raise ConfigError(f"n_tests vaut {n_tests}, attendu au moins 1")
    if n_obs < 2:
        raise ConfigError(f"n_obs vaut {n_obs}, attendu au moins 2")
    canonique = _normalize_method(method)
    ppy = frequency.periods_per_year if periods_per_year is None else float(periods_per_year)
    if ppy <= 0.0:
        raise ConfigError(f"periods_per_year vaut {ppy}, attendu strictement positif")

    sr_periodique = observed_sr / math.sqrt(ppy) if annualized else observed_sr
    tstat = sr_periodique * math.sqrt(n_obs)
    p_simple = 2.0 * float(stats.norm.sf(tstat))

    if other_pvalues is None:
        p_ajustee = _adjusted_pvalue_of_best(p_simple, n_tests, canonique)
    else:
        autres = _as_pvalues(other_pvalues)
        vecteur = np.concatenate(([p_simple], autres))
        p_ajustee = float(adjust_pvalues(vecteur, method=canonique).adjusted_pvalues[0])

    p_ajustee = min(max(p_ajustee, 0.0), 1.0)
    t_ajustee = float(stats.norm.isf(p_ajustee / 2.0))
    sr_periodique_ajuste = t_ajustee / math.sqrt(n_obs)
    sr_ajuste = sr_periodique_ajuste * math.sqrt(ppy) if annualized else sr_periodique_ajuste

    return HaircutResult(
        method=canonique,
        n_tests=n_tests,
        n_obs=n_obs,
        frequency=frequency,
        observed_sr=float(observed_sr),
        observed_tstat=tstat,
        single_pvalue=p_simple,
        adjusted_pvalue=p_ajustee,
        adjusted_tstat=t_ajustee,
        haircut_sr=sr_ajuste,
        haircut_fraction=(observed_sr - sr_ajuste) / observed_sr,
        annualized=annualized,
    )


def _adjusted_pvalue_of_best(pvalue: float, n_tests: int, method: str) -> float:
    """Rend la valeur p ajustée du MEILLEUR essai, sans connaître les autres.

    Les trois procédures partagent le même SEUIL DE REJET au premier rang :
    celui de Holm vaut :math:`\\alpha/(M+1-1) = \\alpha/M`, celui de
    Benjamini-Hochberg vaut :math:`1 \\cdot \\alpha/M`, celui de Bonferroni
    vaut :math:`\\alpha/M`. La DÉCISION sur le meilleur essai est donc la même
    dans les trois cas.

    La valeur p AJUSTÉE, elle, ne coïncide que pour Holm. La récurrence de Holm
    part de :math:`M p_{(1)}` et ne fait ensuite que croître, donc la valeur
    ajustée du premier rang vaut exactement :math:`M p_{(1)}`. C'est une
    identité.

    Pour Benjamini-Hochberg, la récurrence prend au contraire le minimum sur les
    rangs suivants, :math:`\\min_{j \\ge 1} (M/j) p_{(j)}`, qui peut être
    STRICTEMENT inférieur. Avec :math:`M = 10`, :math:`p_{(1)} = 0{,}004` et
    :math:`p_{(2)} = 0{,}005`, la valeur ajustée exacte vaut
    :math:`\\min(0{,}04\\ ;\\ 0{,}025) = 0{,}025`, quand cette fonction rend
    0,04. La valeur rendue est donc une BORNE SUPÉRIEURE, et le rabais qui en
    découle est trop dur plutôt que trop doux.

    Pour Benjamini-Yekutieli, la valeur rendue est de même la BORNE SUPÉRIEURE
    :math:`M c(M) p`, atteinte quand aucun autre essai n'est significatif.

    Dans les deux cas de borne, fournir le vecteur complet par ``other_pvalues``
    rend la valeur exacte.

    Args:
        pvalue: la valeur p brute du meilleur essai.
        n_tests: le nombre d'essais.
        method: le nom canonique de la procédure.

    Returns:
        La valeur p ajustée, bornée à 1.
    """
    penalite = benjamini_yekutieli_constant(n_tests) if method == "benjamini_yekutieli" else 1.0
    return min(n_tests * penalite * pvalue, 1.0)


class IndexResampler(Protocol):
    """Le contrat que doit respecter un tireur d'indices par blocs.

    Une implémentation reçoit la longueur de la série et rend une matrice
    d'indices entiers, une ligne par rééchantillon. Le module de tests multiples
    n'en connaît rien d'autre, ce qui permet de brancher le bootstrap
    stationnaire du laboratoire sans le recopier.
    """

    def __call__(
        self,
        n_observations: int,
        *,
        n_resamples: int,
        block_size: float,
        generator: np.random.Generator,
    ) -> np.ndarray:
        """Rend une matrice d'indices de forme ``(n_resamples, n_observations)``."""
        ...


def _default_resampler(
    n_observations: int,
    *,
    n_resamples: int,
    block_size: float,
    generator: np.random.Generator,
) -> np.ndarray:
    """Délègue au bootstrap stationnaire du laboratoire.

    Args:
        n_observations: la longueur de la série d'origine.
        n_resamples: le nombre de rééchantillons voulus.
        block_size: la longueur moyenne des blocs contigus.
        generator: le générateur aléatoire, propagé explicitement.

    Returns:
        La matrice d'indices rendue par
        ``quantlab.validation.bootstrap.bootstrap_indices``.

    Note:
        Le module de bootstrap sépare le tirage des INDICES du tirage des
        données, et c'est cette porte-là qu'il faut prendre ici. Les colonnes
        de stratégies doivent bouger ensemble, sur exactement le même tirage,
        sans quoi la structure de corrélation entre stratégies est détruite par
        le rééchantillonnage lui-même. ``stationary_bootstrap`` rééchantillonne
        une série à la fois et ne conviendrait donc pas.

    Raises:
        ConfigError: si le module de bootstrap n'est pas disponible. Passer
            alors un ``resampler`` explicite.
    """
    try:
        from quantlab.validation.bootstrap import BootstrapMethod, bootstrap_indices
    except ImportError as exc:  # pragma: no cover - dépend de l'état du paquet
        raise ConfigError(
            "quantlab.validation.bootstrap est introuvable ; passez un argument resampler explicite"
        ) from exc
    return np.asarray(
        bootstrap_indices(
            n_observations,
            BootstrapMethod.STATIONARY,
            n_resamples,
            generator,
            mean_block_size=block_size,
        ),
        dtype=np.intp,
    )


def _relative_performance(
    strategy_returns: ReturnFrame,
    benchmark_returns: ReturnSeries,
) -> tuple[np.ndarray, list[str]]:
    """Rend la matrice des surperformances par rapport au repère.

    Args:
        strategy_returns: les rendements des stratégies, une colonne chacune.
        benchmark_returns: les rendements du repère.

    Returns:
        La matrice :math:`d` de forme ``(n, m)`` et la liste des noms de
        colonnes, dans l'ordre.

    Raises:
        InsufficientDataError: si moins de trois dates communes subsistent.
        DataQualityError: si la matrice porte des manquants.
    """
    if strategy_returns.shape[1] == 0:
        raise InsufficientDataError("aucune stratégie à comparer au repère")
    strat, bench = align_returns(strategy_returns, benchmark_returns)
    diff = strat.sub(bench, axis=0)
    if diff.isna().to_numpy().any():
        raise DataQualityError("la matrice de surperformance porte des valeurs manquantes")
    if len(diff) < 3:
        raise InsufficientDataError(
            f"{len(diff)} dates communes, il en faut au moins 3 pour un bootstrap par blocs"
        )
    return diff.to_numpy(dtype=float), [str(c) for c in diff.columns]


def _bootstrap_means(d: np.ndarray, indices: np.ndarray) -> np.ndarray:
    """Rend les moyennes des séries rééchantillonnées.

    Args:
        d: la matrice de surperformance, de forme ``(n, m)``.
        indices: les indices tirés, de forme ``(B, n)``.

    Returns:
        Une matrice ``(B, m)`` où la ligne ``b`` porte les moyennes du
        rééchantillon ``b``.
    """
    n_bootstrap = indices.shape[0]
    moyennes = np.empty((n_bootstrap, d.shape[1]), dtype=float)
    for b in range(n_bootstrap):
        moyennes[b] = d[indices[b]].mean(axis=0)
    return moyennes


def _politis_romano_variance(d: np.ndarray, q: float, variance_floor: float) -> np.ndarray:
    r"""Rend la variance de long terme de chaque colonne, sous le noyau du bootstrap.

    **Le problème.** La variance de :math:`\sqrt{n}\,\bar{d}_k` n'est pas la
    variance de :math:`d_k` divisée par :math:`n` dès que la série est
    autocorrélée. Studentiser avec la mauvaise variance fausse le test de Hansen.

    **La formule**, telle que Hansen (2005) l'écrit en section 3 :

    .. math::

        \hat{\omega}_k^2 = \hat{\gamma}_{0,k}
        + 2 \sum_{i=1}^{n-1} \kappa(n,i)\, \hat{\gamma}_{i,k},
        \qquad
        \kappa(n,i) = \frac{n-i}{n}(1-q)^i + \frac{i}{n}(1-q)^{n-i}

    avec :math:`\hat{\gamma}_{i,k} = n^{-1}\sum_{j=1}^{n-i}
    (d_{k,j}-\bar{d}_k)(d_{k,j+i}-\bar{d}_k)`.

    Les poids sont ceux qu'induit le bootstrap stationnaire lui-même, ce que
    Hansen préfère à une estimation par les rééchantillons, jugée trop bruitée.

    Args:
        d: la matrice de surperformance, de forme ``(n, m)``.
        q: la probabilité de redémarrer un bloc, égale à l'inverse de la
            longueur moyenne des blocs.
        variance_floor: plancher déclaré appliqué à la variance, qui évite une
            division par zéro sur une colonne constante.

    Returns:
        Le vecteur des :math:`\hat{\omega}_k^2`, de longueur ``m``.
    """
    n = d.shape[0]
    centre = d - d.mean(axis=0, keepdims=True)
    taille = 1 << (2 * n - 1).bit_length()
    spectre = np.fft.rfft(centre, n=taille, axis=0)
    autocov = np.fft.irfft(spectre * np.conj(spectre), n=taille, axis=0)[:n] / n
    lags = np.arange(1, n, dtype=float)
    poids = (n - lags) / n * (1.0 - q) ** lags + lags / n * (1.0 - q) ** (n - lags)
    omega2 = autocov[0] + 2.0 * (poids[:, None] * autocov[1:]).sum(axis=0)
    return np.maximum(omega2, variance_floor)


@dataclass(frozen=True, slots=True, eq=False)
class RealityCheckResult:
    """Le verdict du contrôle de réalité de White (2000).

    Attributes:
        statistic: la statistique :math:`V_n = \\max_k \\sqrt{n}\\,\\bar{d}_k`.
        pvalue: la valeur p par bootstrap, part des rééchantillons dont la
            statistique dépasse celle observée.
        n_bootstrap: le nombre de rééchantillons.
        n_observations: le nombre de dates communes retenues.
        strategies: les noms des stratégies, dans l'ordre des colonnes.
        best_strategy: le nom de la stratégie de plus forte surperformance
            moyenne.
        mean_outperformance: la surperformance moyenne de chaque stratégie.
    """

    statistic: float
    pvalue: float
    n_bootstrap: int
    n_observations: int
    strategies: tuple[str, ...]
    best_strategy: str
    mean_outperformance: np.ndarray


def whites_reality_check(
    strategy_returns_matrix: ReturnFrame,
    benchmark_returns: ReturnSeries,
    *,
    n_bootstrap: int = 1000,
    generator: np.random.Generator,
    block_size: float = 10.0,
    resampler: IndexResampler | None = None,
) -> RealityCheckResult:
    r"""Teste si la MEILLEURE d'un ensemble de stratégies bat vraiment le repère.

    **(1) Le problème.** Comparer la meilleure de vingt stratégies à un repère
    avec un test de Student ordinaire rejette bien trop souvent. Le test ignore
    que la stratégie comparée a été CHOISIE pour son résultat.

    **(2) L'intuition.** Prendre le maximum comme statistique de test, et en
    obtenir la loi sous l'hypothèse nulle par rééchantillonnage. Le bootstrap
    fabrique des mondes où aucune stratégie ne bat le repère, en recentrant les
    surperformances sur zéro. On regarde ensuite à quelle fréquence le maximum
    de ces mondes dépasse le maximum observé.

    **(3) La formule.** Avec :math:`d_{k,t}` la surperformance de la stratégie
    :math:`k` à la date :math:`t` :

    .. math::

        V_n = \max_{k=1,\ldots,m} \sqrt{n}\, \bar{d}_k,
        \qquad
        V_{n,b}^{*} = \max_{k} \sqrt{n}\left(\bar{d}_{k,b}^{*} - \bar{d}_k\right)

    .. math::

        p = \frac{1}{B}\sum_{b=1}^{B}
        \mathbb{1}\left\{V_{n,b}^{*} > V_n\right\}

    **(4) Les variables.** :math:`n` le nombre de dates, :math:`m` le nombre de
    stratégies, :math:`B` le nombre de rééchantillons, :math:`\bar{d}_{k,b}^{*}`
    la moyenne de la série rééchantillonnée.

    **(5) Les hypothèses.** Stationnarité et mélange de la série des
    surperformances, nombre de stratégies fixe, et hypothèse nulle prise dans sa
    configuration la moins favorable, celle où toutes les moyennes valent
    exactement zéro.

    **(6) La provenance.** White, H. (2000), « A Reality Check for Data
    Snooping », *Econometrica*, 68(5), p. 1097-1126. Écriture reprise de Hansen
    (2005), section 2.1, qui la redonne dans la même notation.

    **(7) Les limites, et c'est ce que Hansen corrige.** Le recentrage suppose
    que TOUTES les stratégies ont une espérance nulle. Ajouter des stratégies
    manifestement mauvaises ne coûte donc rien à l'hypothèse nulle. Cela gonfle
    pourtant le maximum des rééchantillons, ce qui fait monter la valeur p
    rendue. Le test se dilue, et un chercheur peut le manipuler en ajoutant du
    ballast.

    Le test n'est pas non plus studentisé : une stratégie très volatile pèse plus
    dans le maximum qu'une stratégie régulière de même moyenne.

    **(8) Les alternatives.** :func:`hansen_spa`, qui corrige les deux défauts.
    La procédure par étapes de Romano et Wolf (2005), qui rend la liste de TOUTES
    les stratégies significatives et pas seulement un verdict global.

    **(9) Pourquoi celle-ci.** Elle reste le point de comparaison de toute la
    littérature, et l'écart entre sa valeur p et celle de Hansen mesure
    directement la présence de mauvaises stratégies dans l'ensemble.

    **(10) Comment vérifier.** Sous bruit pur, la part de rejets doit tourner
    autour du seuil nominal. Avec une stratégie qui bat réellement le repère de
    plusieurs erreurs types, la valeur p doit s'effondrer. Le test du module
    contrôle les deux.

    Args:
        strategy_returns_matrix: les rendements des stratégies candidates, une
            colonne par stratégie.
        benchmark_returns: les rendements du repère.
        n_bootstrap: le nombre de rééchantillons. La résolution de la valeur p
            vaut :math:`1/B`.
        generator: le générateur aléatoire, propagé explicitement.
        block_size: la longueur moyenne des blocs du bootstrap stationnaire. Elle
            doit couvrir la mémoire de la série ; une valeur de 1 revient à un
            tirage indépendant, qui détruit l'autocorrélation.
        resampler: le tireur d'indices. Sans valeur, le bootstrap stationnaire
            du laboratoire est utilisé.

    Returns:
        La statistique, la valeur p et le détail par stratégie.

    Raises:
        ConfigError: si le nombre de rééchantillons ou la longueur de bloc sort
            de son domaine.
        InsufficientDataError: si les séries n'ont pas assez de dates communes.
    """
    d, noms = _relative_performance(strategy_returns_matrix, benchmark_returns)
    n, _ = d.shape
    indices = _draw_indices(n, n_bootstrap, block_size, generator, resampler)

    moyennes = d.mean(axis=0)
    racine = math.sqrt(n)
    statistique = float(np.max(racine * moyennes))
    moyennes_boot = _bootstrap_means(d, indices)
    statistiques_boot = np.max(racine * (moyennes_boot - moyennes), axis=1)
    pvalue = float(np.mean(statistiques_boot > statistique))

    log.debug(
        "contrôle de réalité de White calculé",
        extra={"n_observations": n, "n_strategies": len(noms), "n_bootstrap": n_bootstrap},
    )
    return RealityCheckResult(
        statistic=statistique,
        pvalue=pvalue,
        n_bootstrap=int(indices.shape[0]),
        n_observations=n,
        strategies=tuple(noms),
        best_strategy=noms[int(np.argmax(moyennes))],
        mean_outperformance=moyennes,
    )


def _draw_indices(
    n: int,
    n_bootstrap: int,
    block_size: float,
    generator: np.random.Generator,
    resampler: IndexResampler | None,
) -> np.ndarray:
    """Tire les indices du bootstrap et vérifie la forme rendue.

    Args:
        n: la longueur de la série.
        n_bootstrap: le nombre de rééchantillons demandé.
        block_size: la longueur moyenne des blocs.
        generator: le générateur aléatoire.
        resampler: le tireur, ou ``None`` pour celui du laboratoire.

    Returns:
        La matrice d'indices, de forme ``(n_bootstrap, n)``.

    Raises:
        ConfigError: si un argument sort de son domaine, ou si le tireur rend
            une matrice de mauvaise forme.
    """
    if n_bootstrap < 1:
        raise ConfigError(f"n_bootstrap vaut {n_bootstrap}, attendu au moins 1")
    if block_size < 1.0 or block_size > n:
        raise ConfigError(f"block_size vaut {block_size}, attendu entre 1 et {n}")
    tireur = _default_resampler if resampler is None else resampler
    indices = np.asarray(
        tireur(n, n_resamples=n_bootstrap, block_size=block_size, generator=generator),
        dtype=np.intp,
    )
    if indices.shape != (n_bootstrap, n):
        raise ConfigError(f"le tireur a rendu une matrice {indices.shape}, attendu {(n_bootstrap, n)}")
    return indices


@dataclass(frozen=True, slots=True, eq=False)
class SuperiorPredictiveAbilityResult:
    """Le verdict du test de capacité prédictive supérieure de Hansen (2005).

    Attributes:
        statistic: la statistique studentisée
            :math:`T_n^{SPA} = \\max\\left[\\max_k \\sqrt{n}\\bar{d}_k /
            \\hat{\\omega}_k,\\ 0\\right]`.
        pvalue_consistent: la valeur p du recentrage cohérent, celle qu'il faut
            lire et publier.
        pvalue_lower: la valeur p du recentrage inférieur, borne LIBÉRALE.
        pvalue_upper: la valeur p du recentrage supérieur, borne CONSERVATRICE.
            C'est l'analogue studentisé du contrôle de réalité de White.
        n_bootstrap: le nombre de rééchantillons.
        n_observations: le nombre de dates communes retenues.
        strategies: les noms des stratégies, dans l'ordre des colonnes.
        best_strategy: le nom de la stratégie de plus forte statistique
            studentisée.
        studentized_means: les :math:`\\sqrt{n}\\bar{d}_k / \\hat{\\omega}_k`.
        long_run_variances: les :math:`\\hat{\\omega}_k^2`.
        n_poor_alternatives: le nombre de stratégies déclarées mauvaises par le
            seuil en :math:`\\sqrt{2\\log\\log n}`, donc écartées du recentrage.
    """

    statistic: float
    pvalue_consistent: float
    pvalue_lower: float
    pvalue_upper: float
    n_bootstrap: int
    n_observations: int
    strategies: tuple[str, ...]
    best_strategy: str
    studentized_means: np.ndarray
    long_run_variances: np.ndarray
    n_poor_alternatives: int


def hansen_spa(
    strategy_returns_matrix: ReturnFrame,
    benchmark_returns: ReturnSeries,
    *,
    n_bootstrap: int = 1000,
    generator: np.random.Generator,
    block_size: float = 10.0,
    resampler: IndexResampler | None = None,
    variance_floor: float = 1e-16,
) -> SuperiorPredictiveAbilityResult:
    r"""Teste la capacité prédictive supérieure, en corrigeant les deux défauts de White.

    **(1) Le problème.** Le contrôle de réalité de White se laisse diluer. Ajouter
    à l'ensemble des stratégies manifestement mauvaises fait monter sa valeur p
    sans que rien ne change pour la bonne stratégie. Le chercheur honnête est
    puni d'avoir montré tous ses essais.

    **(2) L'intuition.** Deux gestes. D'abord diviser chaque surperformance
    moyenne par son propre écart type de long terme, ce qui empêche une stratégie
    très volatile de dominer le maximum. Ensuite recentrer chaque colonne selon
    ce que les données disent d'elle. Une stratégie dont la moyenne est très
    négative ne peut pas être à la frontière de l'hypothèse nulle. On la laisse
    donc à sa vraie moyenne au lieu de la ramener à zéro.

    **(3) La formule.** La statistique :

    .. math::

        T_n^{SPA} = \max\left[\max_{k=1,\ldots,m}
        \frac{\sqrt{n}\,\bar{d}_k}{\hat{\omega}_k},\; 0\right]

    Le recentrage, avec trois choix possibles :

    .. math::

        Z_{k,b,t}^{*} = d_{k,b,t}^{*} - g^{i}(\bar{d}_k),
        \qquad i = l, c, u

    .. math::

        g^{l}(x) = \max(0, x),
        \quad
        g^{c}(x) = x \cdot \mathbb{1}\left\{x \ge
        -\sqrt{\frac{\hat{\omega}_k^2}{n} 2\log\log n}\right\},
        \quad
        g^{u}(x) = x

    La valeur p :

    .. math::

        T_{b,n}^{SPA*} = \max\left[\max_k
        \frac{\sqrt{n}\,\bar{Z}_{k,b}^{*}}{\hat{\omega}_k},\; 0\right],
        \qquad
        \hat{p}^{SPA} = \frac{1}{B}\sum_{b=1}^{B}
        \mathbb{1}\left\{T_{b,n}^{SPA*} > T_n^{SPA}\right\}

    **(4) Les variables.** :math:`\hat{\omega}_k^2` la variance de long terme de
    :math:`\sqrt{n}\bar{d}_k`, estimée sous le noyau du bootstrap stationnaire ;
    :math:`n` le nombre de dates ; :math:`B` le nombre de rééchantillons ;
    :math:`\log\log n` le logarithme itéré, qui croît assez lentement pour que le
    seuil reste utile sur des échantillons réalistes.

    **(5) Les hypothèses.** Mêmes conditions de mélange que chez White, plus la
    positivité de chaque :math:`\hat{\omega}_k^2`, et un échantillon assez long
    pour que :math:`\log\log n` soit positif, donc :math:`n \ge 3`.

    **(6) La provenance.** Hansen, P. R. (2005), « A Test for Superior Predictive
    Ability », *Journal of Business and Economic Statistics*, 23(4), p. 365-380.
    Les trois fonctions de recentrage sont celles de sa section 3, recopiées
    telles quelles. L'estimateur de variance est celui qu'il recommande, plutôt
    que la variance des rééchantillons qu'une version antérieure employait.

    **(7) Ce que cette implémentation FAIT et NE FAIT PAS.** Elle implémente le
    test tel que l'article le décrit, avec les trois recentrages et l'estimateur
    de variance recommandé, pas une variante simplifiée.

    Un écart est déclaré. Hansen note qu'un plancher est nécessaire quand
    :math:`\hat{\omega}_k^2` ressort négatif ou nul en échantillon fini, ce que
    la somme pondérée d'autocovariances autorise. L'argument
    ``variance_floor`` porte ce plancher, et sa valeur est déclarée dans le
    résultat plutôt que cachée.

    La limite de fond est celle de l'article. La valeur p cohérente dépend d'un
    seuil de taux :math:`\sqrt{2\log\log n}`, et Hansen écrit lui-même qu'une
    autre vitesse donnerait une autre valeur p en échantillon fini. Les bornes
    inférieure et supérieure sont là pour mesurer cette sensibilité, et un écart
    large entre elles signale la présence de mauvaises stratégies.

    **(8) Les alternatives.** Le contrôle de réalité de White, plus simple et
    plus conservateur. Romano et Wolf (2005), qui identifient chaque stratégie
    significative au lieu de rendre un verdict d'ensemble.

    **(9) Pourquoi celle-ci.** Elle rend le test insensible au ballast, ce qui
    permet de déclarer TOUS les essais menés sans se pénaliser. C'est exactement
    la propriété dont un laboratoire qui compte ses ratés a besoin.

    **(10) Comment vérifier.** Trois contrôles. Les trois valeurs p doivent être
    ordonnées, la borne inférieure sous la cohérente, elle-même sous la
    supérieure. Ajouter des stratégies très mauvaises doit laisser la valeur p
    cohérente à peu près intacte et faire monter celle de White. Et sous bruit
    pur, le taux de rejet doit rester proche du seuil nominal.

    Args:
        strategy_returns_matrix: les rendements des stratégies candidates.
        benchmark_returns: les rendements du repère.
        n_bootstrap: le nombre de rééchantillons.
        generator: le générateur aléatoire, propagé explicitement.
        block_size: la longueur moyenne des blocs du bootstrap stationnaire.
        resampler: le tireur d'indices, celui du laboratoire sans valeur.
        variance_floor: plancher déclaré sur la variance de long terme.

    Returns:
        Les trois valeurs p et le détail par stratégie.

    Raises:
        ConfigError: si un argument sort de son domaine.
        InsufficientDataError: si les séries n'ont pas assez de dates communes.
    """
    if variance_floor <= 0.0:
        raise ConfigError(f"variance_floor vaut {variance_floor}, attendu strictement positif")
    d, noms = _relative_performance(strategy_returns_matrix, benchmark_returns)
    n, _ = d.shape
    if n < 3:
        raise InsufficientDataError(f"{n} dates, il en faut au moins 3 pour log log n")
    indices = _draw_indices(n, n_bootstrap, block_size, generator, resampler)

    q = 1.0 / block_size
    omega2 = _politis_romano_variance(d, q, variance_floor)
    omega = np.sqrt(omega2)
    racine = math.sqrt(n)
    moyennes = d.mean(axis=0)
    studentisees = racine * moyennes / omega
    statistique = float(max(studentisees.max(), 0.0))

    seuil_pauvre = -np.sqrt(omega2 / n * 2.0 * math.log(math.log(n)))
    recentrages = {
        "lower": np.maximum(0.0, moyennes),
        "consistent": np.where(moyennes >= seuil_pauvre, moyennes, 0.0),
        "upper": moyennes,
    }
    moyennes_boot = _bootstrap_means(d, indices)
    valeurs_p: dict[str, float] = {}
    for nom, centre in recentrages.items():
        boot = np.max(racine * (moyennes_boot - centre) / omega, axis=1)
        boot = np.maximum(boot, 0.0)
        valeurs_p[nom] = float(np.mean(boot > statistique))

    log.debug(
        "test SPA de Hansen calculé",
        extra={"n_observations": n, "n_strategies": len(noms), "n_bootstrap": n_bootstrap},
    )
    return SuperiorPredictiveAbilityResult(
        statistic=statistique,
        pvalue_consistent=valeurs_p["consistent"],
        pvalue_lower=valeurs_p["lower"],
        pvalue_upper=valeurs_p["upper"],
        n_bootstrap=int(indices.shape[0]),
        n_observations=n,
        strategies=tuple(noms),
        best_strategy=noms[int(np.argmax(studentisees))],
        studentized_means=studentisees,
        long_run_variances=omega2,
        n_poor_alternatives=int(np.count_nonzero(moyennes < seuil_pauvre)),
    )


@dataclass(frozen=True, slots=True)
class Trial:
    """Un essai mené, avec sa famille et son ratio de Sharpe.

    Attributes:
        family: la famille de stratégies, par exemple ``"momentum-actions"``.
            Le ratio de Sharpe dégonflé se calcule PAR famille, la dispersion
            des essais n'étant pas la même en haute fréquence et en macro.
        name: le nom de l'essai, unique dans sa famille.
        sharpe: le ratio de Sharpe mesuré, dans l'unité déclarée par le registre.
    """

    family: str
    name: str
    sharpe: float


@dataclass(frozen=True, slots=True)
class DeflationInputs:
    """Les intrants du ratio de Sharpe dégonflé, prêts à l'emploi.

    Attributes:
        family: la famille comptée, ou ``"*"`` pour l'ensemble du registre.
        n_trials: le nombre d'essais menés, ratés compris.
        mean_sharpe: la moyenne des ratios de Sharpe essayés.
        sharpe_variance: leur variance sans biais, celle qui entre dans le
            maximum attendu.
        average_correlation: la corrélation moyenne déclarée entre essais.
        n_independent_trials: le nombre d'essais INDÉPENDANTS implicite, selon
            l'équation (9) de Bailey et López de Prado (2014).
        best_sharpe: le meilleur ratio de Sharpe de la famille.
    """

    family: str
    n_trials: int
    mean_sharpe: float
    sharpe_variance: float
    average_correlation: float
    n_independent_trials: float
    best_sharpe: float


@dataclass(frozen=True, slots=True)
class TrialCounter:
    """Le registre des essais menés, par famille de stratégies.

    **Le problème.** Le ratio de Sharpe dégonflé et le rabais de Harvey et Liu
    exigent tous deux le nombre d'essais. C'est l'information que presque aucun
    backtest publié ne porte, et la seule que le chercheur possède vraiment.

    **Ce que fait cette classe.** Elle accumule les essais, y compris les ratés,
    et rend les deux quantités dont le ratio dégonflé a besoin : leur nombre et
    la variance de leurs ratios de Sharpe. La règle 8 du ``CLAUDE.md`` interdit
    de cacher une expérience ratée, et ce registre est l'endroit où cette règle
    devient un nombre.

    **Pourquoi une classe gelée.** Chaque ajout rend un NOUVEAU registre plutôt
    que de modifier celui-ci. Un compte d'essais qui change sous les pieds d'un
    calcul déjà lancé est exactement le genre de défaut qu'on ne retrouve pas.

    Attributes:
        trials: les essais enregistrés, dans l'ordre d'ajout.
        annualized: vrai si les ratios de Sharpe sont annualisés. La variance des
            essais entre dans le seuil de rejet du ratio dégonflé, et mélanger
            les deux échelles y fausse le résultat d'un facteur égal au nombre
            de périodes par an.
    """

    trials: tuple[Trial, ...] = ()
    annualized: bool = True

    def record(self, family: str, name: str, sharpe: float) -> TrialCounter:
        """Rend un nouveau registre augmenté d'un essai.

        Args:
            family: la famille de stratégies de l'essai.
            name: le nom de l'essai, unique dans sa famille.
            sharpe: le ratio de Sharpe mesuré.

        Returns:
            Un registre neuf, celui-ci restant inchangé.

        Raises:
            ConfigError: si le ratio de Sharpe n'est pas fini, ou si le couple
                famille et nom est déjà enregistré.
        """
        if not math.isfinite(sharpe):
            raise ConfigError(f"le ratio de Sharpe de {name!r} vaut {sharpe}, attendu fini")
        if any(t.family == family and t.name == name for t in self.trials):
            raise ConfigError(f"l'essai {name!r} est déjà enregistré dans la famille {family!r}")
        return replace(self, trials=(*self.trials, Trial(family, name, float(sharpe))))

    def families(self) -> tuple[str, ...]:
        """Rend les familles présentes, dans l'ordre de première apparition."""
        vues: list[str] = []
        for essai in self.trials:
            if essai.family not in vues:
                vues.append(essai.family)
        return tuple(vues)

    def _sharpes(self, family: str | None) -> np.ndarray:
        """Rend les ratios de Sharpe d'une famille, ou de tout le registre."""
        valeurs = [t.sharpe for t in self.trials if family is None or t.family == family]
        return np.asarray(valeurs, dtype=float)

    def n_trials(self, family: str | None = None) -> int:
        """Compte les essais menés.

        Args:
            family: la famille visée, ou ``None`` pour tout le registre.

        Returns:
            Le nombre d'essais, ratés compris.
        """
        return int(self._sharpes(family).size)

    def mean_sharpe(self, family: str | None = None) -> float:
        """Rend la moyenne des ratios de Sharpe essayés.

        Args:
            family: la famille visée, ou ``None`` pour tout le registre.

        Returns:
            La moyenne arithmétique.

        Raises:
            InsufficientDataError: si aucun essai n'est enregistré.
        """
        valeurs = self._sharpes(family)
        if valeurs.size == 0:
            raise InsufficientDataError(f"aucun essai enregistré pour {family!r}")
        return float(valeurs.mean())

    def sharpe_variance(self, family: str | None = None) -> float:
        r"""Rend la variance sans biais des ratios de Sharpe essayés.

        **Pourquoi cette quantité.** Le seuil de rejet du ratio de Sharpe
        dégonflé vaut :math:`\sqrt{V[\widehat{SR}_n]}` multiplié par le maximum
        attendu de :math:`N` normales centrées réduites. La variance des essais
        pilote donc entièrement l'ampleur du dégonflage.

        Args:
            family: la famille visée, ou ``None`` pour tout le registre.

        Returns:
            La variance à :math:`n-1` degrés de liberté.

        Raises:
            InsufficientDataError: si moins de deux essais sont enregistrés.
        """
        valeurs = self._sharpes(family)
        if valeurs.size < 2:
            raise InsufficientDataError(
                f"{valeurs.size} essai pour {family!r}, il en faut au moins 2 pour une variance"
            )
        return float(valeurs.var(ddof=1))

    def deflation_inputs(
        self,
        family: str | None = None,
        *,
        average_correlation: float = 0.0,
    ) -> DeflationInputs:
        r"""Rend les intrants du ratio de Sharpe dégonflé.

        **La formule du nombre d'essais indépendants**, équation (9) de Bailey et
        López de Prado (2014) :

        .. math::

            \hat{N} = \hat{\rho} + (1 - \hat{\rho}) M

        Elle interpole entre les deux cas extrêmes. Une corrélation moyenne de 1
        ramène :math:`M` essais identiques à un seul, et une corrélation nulle
        les laisse tous distincts.

        **Limite déclarée.** Les auteurs signalent eux-mêmes que la corrélation
        moyenne ne capte qu'une dépendance linéaire. Ils ajoutent que son
        estimation devient sans objet quand le nombre d'essais dépasse la
        longueur de l'échantillon, la matrice de corrélation étant alors
        elle-même surajustée.

        **Où porter ces intrants.** ``n_trials`` va dans l'argument
        ``n_trials`` de :func:`quantlab.validation.dsr.deflated_sharpe_ratio`,
        ``sharpe_variance`` dans ``sharpe_variance_across_trials``, et
        ``mean_sharpe`` dans ``mean_sharpe_across_trials``. Le champ
        ``n_independent_trials`` remplace le premier quand la corrélation
        moyenne entre essais est déclarée.

        Args:
            family: la famille visée, ou ``None`` pour tout le registre.
            average_correlation: la corrélation moyenne DÉCLARÉE entre les essais
                de la famille, entre 0 et 1. Zéro signifie qu'on les traite comme
                indépendants, ce qui est l'hypothèse la plus dure.

        Returns:
            Les intrants prêts pour le ratio de Sharpe dégonflé.

        Raises:
            ConfigError: si la corrélation sort de l'intervalle unité.
            InsufficientDataError: si moins de deux essais sont enregistrés.
        """
        if not (0.0 <= average_correlation <= 1.0):
            raise ConfigError(f"average_correlation vaut {average_correlation}, attendu entre 0 et 1")
        valeurs = self._sharpes(family)
        m = int(valeurs.size)
        variance = self.sharpe_variance(family)
        rho = float(average_correlation)
        return DeflationInputs(
            family="*" if family is None else family,
            n_trials=m,
            mean_sharpe=float(valeurs.mean()),
            sharpe_variance=variance,
            average_correlation=rho,
            n_independent_trials=rho + (1.0 - rho) * m,
            best_sharpe=float(valeurs.max()),
        )


__all__ = [
    "HLZ_2012_FACTOR_COUNT",
    "HLZ_2012_THRESHOLDS",
    "HLZ_RECOMMENDED_TSTAT",
    "DeflationInputs",
    "HaircutResult",
    "IndexResampler",
    "MultipleTestingMethod",
    "MultipleTestingResult",
    "RealityCheckResult",
    "SuperiorPredictiveAbilityResult",
    "Trial",
    "TrialCounter",
    "adjust_pvalues",
    "benjamini_hochberg",
    "benjamini_yekutieli",
    "benjamini_yekutieli_constant",
    "bonferroni",
    "haircut_sharpe",
    "hansen_spa",
    "holm",
    "required_tstat",
    "whites_reality_check",
]

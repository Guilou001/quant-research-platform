r"""Transformer un alpha et une covariance en poids, et prouver que les poids sont ceux qu'on croit.

**Le problème.** Un signal n'est pas un portefeuille. Entre les deux se
trouvent une covariance, des contraintes, des coûts, et une fonction objectif
dont chaque terme change la réponse. La formulation centrale du laboratoire est

.. math::

    \max_w \; \alpha^\top w - \frac{\lambda}{2} w^\top \Sigma w - \gamma \, \| w - w_{old} \|_1

où :math:`\alpha` est l'alpha attendu par actif, :math:`\Sigma` la covariance,
:math:`\lambda` l'aversion au risque, :math:`w_{old}` le portefeuille détenu, et
:math:`\gamma` le coût proportionnel d'un aller simple. Les optimiseurs
classiques en sont des cas particuliers : la variance minimale pose
:math:`\alpha = 0`, l'équipondération n'optimise rien et sert de repère.

**Le repère obligatoire.** DeMiguel, Garlappi et Uppal (2009) montrent que
l'équipondération bat la plupart des optimisations hors échantillon sur des
horizons d'estimation réalistes. Toute comparaison d'optimiseurs dans ce dépôt
inclut donc :class:`EqualWeight` et :class:`InverseVolatility`, et une méthode
qui ne les bat pas hors échantillon n'apporte rien.

**Ce que ce module fait de plus qu'appeler une bibliothèque.** Chaque optimiseur
porte un contrôle indépendant de son résultat, exposé par ``check``. La parité
de risque vérifie que les contributions sont égales par
:mod:`quantlab.analytics.contributions`. La variance minimale vérifie les
conditions de premier ordre, la diversification maximale son ratio, et
l'inverse de volatilité sa forme fermée. C'est ce qui transforme un résultat de
``skfolio`` ou de ``cvxpy`` en un résultat qu'on peut défendre (ADR-011).

**Ce que ce module ne fait pas.** Il ne choisit pas l'optimiseur. Le choix se
fait hors échantillon, par la phase 7, jamais parce qu'une méthode gagne dans
l'échantillon.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from quantlab.analytics.contributions import diversification_ratio, portfolio_volatility, risk_contribution
from quantlab.core.errors import DataQualityError, InsufficientDataError
from quantlab.core.logging import get_logger
from quantlab.core.types import Weights
from quantlab.portfolio.covariance import is_psd, nearest_psd

try:  # skfolio est une dépendance optionnelle, extra « portfolio »
    from skfolio.prior import BasePrior as _BasePrior
except ImportError:  # pragma: no cover
    _BasePrior = object  # type: ignore[assignment,misc]

__all__ = [
    "DEFAULT_RISK_AVERSION",
    "DEFAULT_SOLVER_TOLERANCE",
    "DEFAULT_TOLERANCE",
    "EqualWeight",
    "HierarchicalRiskParity",
    "InverseVolatility",
    "MaximumDiversification",
    "MeanVarianceWithCosts",
    "MinimumVariance",
    "OptimizerCheck",
    "RiskParity",
    "compare_optimizers",
]

_log = get_logger(__name__)

#: Aversion au risque par défaut de la moyenne-variance. Un seul chiffre, à
#: régler par étude ; ce n'est pas une mesure.
DEFAULT_RISK_AVERSION = 5.0
#: Tolérance des contrôles de premier ordre et d'égalité des contributions.
DEFAULT_TOLERANCE = 1e-6
#: Précision à laquelle un solveur convexe respecte une borne. Les solveurs de
#: ``cvxpy`` s'arrêtent vers 1e-5 en relatif, et exiger mieux fait échouer un
#: contrôle sur du bruit numérique.
DEFAULT_SOLVER_TOLERANCE = 1e-4


@dataclass(frozen=True)
class OptimizerCheck:
    """Le résultat du contrôle indépendant d'un optimiseur.

    ``passed`` dit si la propriété qui DÉFINIT l'optimiseur est vérifiée sur les
    poids rendus, et ``detail`` chiffre l'écart. Un optimiseur dont le contrôle
    échoue rend des poids qui portent un autre nom que le sien.
    """

    name: str
    passed: bool
    detail: dict[str, float] = field(default_factory=dict)


def _align(
    alpha: pd.Series | None, covariance: pd.DataFrame
) -> tuple[pd.Index, np.ndarray, np.ndarray | None]:
    """Rend l'index commun, la covariance et l'alpha alignés, ou lève."""
    if not isinstance(covariance, pd.DataFrame) or covariance.shape[0] != covariance.shape[1]:
        raise DataQualityError("la covariance doit être un DataFrame carré indexé par actif")
    if covariance.shape[0] < 2:
        raise InsufficientDataError("il faut au moins deux actifs")
    if not (covariance.index == covariance.columns).all():
        raise DataQualityError("la covariance doit porter les mêmes actifs en lignes et en colonnes")
    cov = nearest_psd(covariance) if not is_psd(covariance) else covariance
    idx = cov.index
    a = None
    if alpha is not None:
        a = alpha.reindex(idx).to_numpy(dtype=float)
        if np.isnan(a).any():
            raise DataQualityError("l'alpha manque pour au moins un actif de la covariance")
    return idx, cov.to_numpy(dtype=float), a


def _weights(values: np.ndarray, idx: pd.Index) -> Weights:
    return pd.Series(np.asarray(values, dtype=float), index=idx, name="weight")


@dataclass(frozen=True)
class EqualWeight:
    r"""Le portefeuille équipondéré, :math:`w_i = 1/N`. Le repère que tout le monde doit battre.

    Il n'estime rien, donc il ne se trompe sur rien. DeMiguel, Garlappi et Uppal
    (2009) mesurent qu'il faut environ 3 000 mois de données pour qu'une
    moyenne-variance à 25 actifs le batte de façon fiable, résultat rapporté
    dans ``docs/literature/demiguel_garlappi_uppal_2009.md``.
    """

    def optimize(
        self, *, alpha: pd.Series | None = None, covariance: pd.DataFrame, previous: Weights | None = None
    ) -> Weights:
        """Rend :math:`1/N` par actif de la covariance."""
        idx, _, _ = _align(None, covariance)
        return _weights(np.full(len(idx), 1.0 / len(idx)), idx)

    def check(self, weights: Weights, covariance: pd.DataFrame) -> OptimizerCheck:
        """Vérifie que tous les poids sont égaux."""
        spread = float(weights.max() - weights.min())
        return OptimizerCheck("equal_weight", spread < DEFAULT_TOLERANCE, {"max_minus_min": spread})


@dataclass(frozen=True)
class InverseVolatility:
    r"""Les poids inversement proportionnels à la volatilité, :math:`w_i \propto 1/\sigma_i`.

    C'est la parité de risque qui ignore les corrélations. Elle est exacte quand
    les actifs sont non corrélés, et une approximation utile sinon, parce qu'elle
    n'inverse aucune matrice et ne souffre donc pas du conditionnement.
    """

    def optimize(
        self, *, alpha: pd.Series | None = None, covariance: pd.DataFrame, previous: Weights | None = None
    ) -> Weights:
        """Rend les poids normalisés à somme un."""
        idx, cov, _ = _align(None, covariance)
        vol = np.sqrt(np.diag(cov))
        if (vol <= 0).any():
            raise DataQualityError("une volatilité nulle interdit l'inverse de volatilité")
        w = 1.0 / vol
        return _weights(w / w.sum(), idx)

    def check(self, weights: Weights, covariance: pd.DataFrame) -> OptimizerCheck:
        """Vérifie que :math:`w_i \\sigma_i` est constant."""
        vol = np.sqrt(np.diag(covariance.to_numpy(dtype=float)))
        prod = weights.to_numpy() * vol
        spread = float(prod.max() - prod.min())
        return OptimizerCheck(
            "inverse_volatility", spread < DEFAULT_TOLERANCE * prod.mean() * 10, {"spread": spread}
        )


@dataclass(frozen=True)
class MinimumVariance:
    r"""Le portefeuille de variance minimale, long seulement, somme un.

    .. math::

        \min_w \; w^\top \Sigma w \quad \text{s.c.} \quad \mathbf{1}^\top w = 1, \; w \ge 0

    **Pourquoi c'est un bon test de la covariance.** Il n'utilise que
    :math:`\Sigma`, aucun rendement attendu, donc sa performance hors échantillon
    mesure la qualité de l'estimateur de covariance et rien d'autre.

    **Le contrôle.** Aux conditions de Karush, Kuhn et Tucker, la contribution
    marginale :math:`(\Sigma w)_i` est égale pour tous les actifs détenus, et
    supérieure ou égale pour les actifs à poids nul. ``check`` le vérifie.

    **La provenance.** Markowitz (1952) pour la formulation. Clarke, de Silva
    et Thorley (2006) pour l'étude empirique du portefeuille de variance
    minimale. Ils montrent qu'il concentre les positions sur peu de titres à
    faible bêta, ce que la borne ``max_weight`` tempère.
    """

    max_weight: float = 1.0
    long_only: bool = True

    def optimize(
        self, *, alpha: pd.Series | None = None, covariance: pd.DataFrame, previous: Weights | None = None
    ) -> Weights:
        """Rend les poids par ``cvxpy``."""
        import cvxpy as cp

        idx, cov, _ = _align(None, covariance)
        n = len(idx)
        w = cp.Variable(n)
        constraints: list[Any] = [cp.sum(w) == 1, w <= self.max_weight]
        if self.long_only:
            constraints.append(w >= 0)
        problem = cp.Problem(cp.Minimize(cp.quad_form(w, cp.psd_wrap(cov))), constraints)
        problem.solve()
        if w.value is None:
            raise DataQualityError(f"variance minimale : le solveur rend « {problem.status} »")
        return _weights(np.clip(w.value, 0.0 if self.long_only else -np.inf, None), idx)

    def check(self, weights: Weights, covariance: pd.DataFrame, tol: float = 1e-5) -> OptimizerCheck:
        """Vérifie les conditions de premier ordre sur les actifs détenus."""
        cov = covariance.to_numpy(dtype=float)
        w = weights.reindex(covariance.index).to_numpy(dtype=float)
        marginal = cov @ w
        held = w > 1e-8
        if held.sum() == 0:
            return OptimizerCheck("minimum_variance", False, {"held": 0.0})
        spread_held = float(marginal[held].max() - marginal[held].min())
        floor_ok = bool((marginal[~held] >= marginal[held].min() - tol).all()) if (~held).any() else True
        scale = float(np.abs(marginal[held]).mean()) or 1.0
        return OptimizerCheck(
            "minimum_variance",
            spread_held / scale < tol * 100 and floor_ok,
            {"kkt_spread_relative": spread_held / scale, "n_held": float(held.sum())},
        )


@dataclass(frozen=True)
class RiskParity:
    r"""La parité de risque : chaque actif contribue autant au risque total.

    .. math::

        w_i \, \frac{(\Sigma w)_i}{\sqrt{w^\top \Sigma w}} = \frac{\sigma_p}{N}
        \quad \forall i

    **L'intuition.** Un 60/40 en capital est un 90/10 en risque, parce que les
    actions sont trois fois plus volatiles que les obligations. La parité de
    risque égalise les contributions, ce qui revient à budgéter le risque plutôt
    que le capital.

    **La méthode.** Le problème est convexe sous la reformulation de Spinu
    (2013) : minimiser :math:`\frac{1}{2} w^\top \Sigma w - \frac{1}{N}\sum_i
    \ln w_i`, puis normaliser. ``skfolio.optimization.RiskBudgeting`` le
    résout, et ce module l'enveloppe.

    **Le contrôle.** :func:`quantlab.analytics.contributions.risk_contribution`
    recalcule les contributions de façon indépendante et ``check`` exige qu'elles
    soient égales à la tolérance près. C'est la définition même de la méthode,
    donc le contrôle est exact et non approximatif.

    **La provenance.** Maillard, Roncalli et Teiletche (2010), « The Properties
    of Equally Weighted Risk Contribution Portfolios », Journal of Portfolio
    Management 36(4). Spinu (2013) pour la formulation convexe.
    """

    budget: pd.Series | None = None

    def optimize(
        self, *, alpha: pd.Series | None = None, covariance: pd.DataFrame, previous: Weights | None = None
    ) -> Weights:
        """Rend les poids à contributions égales, ou proportionnelles au budget."""
        from scipy.optimize import minimize

        idx, cov, _ = _align(None, covariance)
        n = len(idx)
        b = np.full(n, 1.0 / n) if self.budget is None else self.budget.reindex(idx).to_numpy(dtype=float)
        if np.isnan(b).any() or (b <= 0).any():
            raise DataQualityError("le budget de risque doit être strictement positif pour chaque actif")
        b = b / b.sum()

        # Formulation de Spinu (2013) : convexe, minimum unique, poids positifs.
        def objective(x: np.ndarray) -> float:
            """La fonction de Spinu (2013), convexe, dont le minimum est la parité."""
            return float(0.5 * x @ cov @ x - b @ np.log(x))

        def gradient(x: np.ndarray) -> np.ndarray:
            """Son gradient, nul exactement là où les contributions sont égales au budget."""
            return cov @ x - b / x

        x0 = 1.0 / np.sqrt(np.diag(cov))
        res = minimize(
            objective,
            x0,
            jac=gradient,
            method="L-BFGS-B",
            bounds=[(1e-10, None)] * n,
            options={"maxiter": 10_000, "ftol": 1e-16, "gtol": 1e-12},
        )
        if not res.success and res.fun > objective(x0):
            raise DataQualityError(f"parité de risque : {res.message}")
        w = res.x / res.x.sum()
        return _weights(w, idx)

    def check(
        self, weights: Weights, covariance: pd.DataFrame, tol: float = DEFAULT_TOLERANCE
    ) -> OptimizerCheck:
        """Vérifie l'égalité des contributions au risque par un calcul indépendant."""
        rc = risk_contribution(weights, covariance)
        n = len(rc)
        b = (
            np.full(n, 1.0 / n)
            if self.budget is None
            else (self.budget.reindex(rc.index) / self.budget.sum()).to_numpy()
        )
        target = b * float(rc.sum())
        gap = float(np.abs(rc.to_numpy() - target).max())
        return OptimizerCheck("risk_parity", gap < tol * max(float(rc.sum()), 1e-12) * 10, {"max_gap": gap})


@dataclass(frozen=True)
class MaximumDiversification:
    r"""Le portefeuille qui maximise le ratio de diversification de Choueifaty et Coignard (2008).

    .. math::

        DR(w) = \frac{w^\top \sigma}{\sqrt{w^\top \Sigma w}}

    où :math:`\sigma` est le vecteur des volatilités. Le ratio vaut un pour un
    seul actif et croît avec la décorrélation du panier. Le résout ``skfolio``,
    et ``check`` recalcule le ratio par
    :func:`quantlab.analytics.contributions.diversification_ratio` et vérifie
    qu'aucune perturbation locale des poids ne l'améliore.
    """

    def optimize(
        self, *, alpha: pd.Series | None = None, covariance: pd.DataFrame, previous: Weights | None = None
    ) -> Weights:
        """Rend les poids par ``skfolio``."""
        from skfolio.optimization import MaximumDiversification as _MD

        idx, cov, _ = _align(None, covariance)
        model = _MD(prior_estimator=_CovariancePrior(covariance=cov, assets=idx))
        model.fit(pd.DataFrame(np.zeros((3, len(idx))), columns=idx))
        return _weights(model.weights_, idx)

    def check(self, weights: Weights, covariance: pd.DataFrame, step: float = 1e-4) -> OptimizerCheck:
        """Vérifie qu'aucun transfert de masse entre deux actifs n'améliore le ratio."""
        base = float(diversification_ratio(weights, covariance))
        best_gain = 0.0
        w = weights.copy()
        for i in w.index:
            for j in w.index:
                if i == j or w[i] < step:
                    continue
                trial = w.copy()
                trial[i] -= step
                trial[j] += step
                best_gain = max(best_gain, float(diversification_ratio(trial, covariance)) - base)
        return OptimizerCheck(
            "maximum_diversification", best_gain < 1e-6, {"best_local_gain": best_gain, "ratio": base}
        )


class _CovariancePrior(_BasePrior):  # type: ignore[misc]
    """Un prior skfolio qui rend une covariance donnée, sans réestimer.

    ``skfolio`` estime ses moments depuis des rendements. Quand la covariance
    vient de notre propre estimateur, on la lui remet telle quelle par ce prior,
    ce qui garde une seule source de vérité pour :math:`\\Sigma`.

    ``skfolio`` clone ses estimateurs par ``sklearn.base.clone``, qui
    reconstruit l'objet depuis ``get_params``. Les deux arguments du
    constructeur portent donc le nom exact des attributs, et ils ont une valeur
    par défaut, sans quoi le clonage échoue avant tout calcul.
    """

    def __init__(self, covariance: np.ndarray | None = None, assets: pd.Index | None = None) -> None:
        self.covariance = covariance
        self.assets = assets

    def fit(self, X: pd.DataFrame, y: Any = None) -> _CovariancePrior:
        """Rend la distribution portant la covariance fournie et une moyenne nulle."""
        from skfolio.prior import ReturnDistribution

        if self.covariance is None or self.assets is None:
            raise DataQualityError("le prior de covariance exige une matrice et ses actifs")
        n = len(self.assets)
        self.return_distribution_ = ReturnDistribution(
            mu=np.zeros(n), covariance=np.asarray(self.covariance, dtype=float), returns=np.zeros((3, n))
        )
        return self


@dataclass(frozen=True)
class HierarchicalRiskParity:
    r"""La parité de risque hiérarchique de López de Prado (2016), écrite ici.

    **L'intuition.** Plutôt qu'inverser la covariance, regrouper les actifs par
    ressemblance de corrélation, puis répartir le risque de haut en bas de
    l'arbre par bissection récursive. Aucune inversion, donc aucune sensibilité
    au conditionnement.

    **Les trois étapes de l'article.** Le regroupement hiérarchique sur la
    distance de corrélation :math:`d_{ij} = \sqrt{(1 - \rho_{ij}) / 2}`, par
    liaison simple. La quasi-diagonalisation, qui réordonne les actifs selon
    l'arbre pour rapprocher ceux qui se ressemblent. La bissection récursive,
    qui coupe la liste en deux, alloue à chaque moitié en proportion inverse de
    sa variance, et recommence dans chaque moitié. La variance d'une moitié est
    celle de son portefeuille à variance inverse.

    **Pourquoi l'écrire plutôt que l'appeler.** ``skfolio`` calcule la distance
    depuis des rendements et non depuis une covariance fournie, ce qui
    l'empêche de servir avec nos propres estimateurs. Soixante lignes suffisent,
    et les écrire montre ce que la méthode fait réellement, conformément à
    l'ADR-011.

    **La limite déclarée.** La méthode n'est pas un optimum de quoi que ce soit,
    et son résultat dépend de la méthode de liaison. La fiche
    ``docs/literature/lopez_de_prado_2016_hrp.md`` rapporte les critiques, dont
    celle que la méthode se comporte souvent comme l'inverse de volatilité.

    **Comment vérifier.** Sur une covariance diagonale, l'arbre n'apporte rien
    et la bissection récursive rend exactement l'inverse de variance, ce que le
    test vérifie en forme fermée. Les poids sont positifs et somment à un par
    construction.
    """

    linkage: str = "single"

    def optimize(
        self, *, alpha: pd.Series | None = None, covariance: pd.DataFrame, previous: Weights | None = None
    ) -> Weights:
        """Rend les poids par regroupement, quasi-diagonalisation et bissection."""
        from scipy.cluster.hierarchy import leaves_list, linkage
        from scipy.spatial.distance import squareform

        idx, cov, _ = _align(None, covariance)
        sd = np.sqrt(np.diag(cov))
        corr = np.clip(cov / np.outer(sd, sd), -1.0, 1.0)
        dist = np.sqrt(np.clip((1.0 - corr) / 2.0, 0.0, None))
        np.fill_diagonal(dist, 0.0)
        tree = linkage(squareform(dist, checks=False), method=self.linkage)
        order = list(leaves_list(tree))

        def inverse_variance_weights(items: list[int]) -> np.ndarray:
            """Les poids en inverse de variance d'un groupe d'actifs."""
            sub = cov[np.ix_(items, items)]
            ivp = 1.0 / np.diag(sub)
            return ivp / ivp.sum()

        def cluster_variance(items: list[int]) -> float:
            """La variance du portefeuille en inverse de variance d'un groupe."""
            w = inverse_variance_weights(items)
            sub = cov[np.ix_(items, items)]
            return float(w @ sub @ w)

        weights = np.ones(len(idx))
        clusters = [order]
        while clusters:
            next_clusters: list[list[int]] = []
            for items in clusters:
                if len(items) <= 1:
                    continue
                half = len(items) // 2
                left, right = items[:half], items[half:]
                v_left, v_right = cluster_variance(left), cluster_variance(right)
                share_left = 1.0 - v_left / (v_left + v_right)
                weights[left] *= share_left
                weights[right] *= 1.0 - share_left
                next_clusters.extend([left, right])
            clusters = next_clusters
        return _weights(weights / weights.sum(), idx)

    def check(self, weights: Weights, covariance: pd.DataFrame) -> OptimizerCheck:
        """Vérifie somme un et positivité, seules propriétés garanties."""
        s = float(weights.sum())
        return OptimizerCheck(
            "hrp",
            abs(s - 1.0) < 1e-8 and bool((weights >= -1e-12).all()),
            {"sum": s, "min": float(weights.min())},
        )


@dataclass(frozen=True)
class MeanVarianceWithCosts:
    r"""La formulation centrale du laboratoire, coûts de transaction compris.

    .. math::

        \max_w \; \alpha^\top w - \frac{\lambda}{2} w^\top \Sigma w
        - \gamma \, \| w - w_{old} \|_1
        \quad \text{s.c.} \quad \sum_i |w_i| \le G, \; |w_i| \le m

    :math:`G` est l'exposition brute maximale et :math:`m` le poids absolu
    maximal. Le terme en :math:`\gamma` est le coût d'un aller simple par unité
    négociée, en fraction, et il rend l'optimiseur RÉTICENT à bouger : avec
    :math:`\gamma > 0`, un alpha qui change peu ne déclenche aucune transaction,
    ce qui est le comportement voulu et ce qui distingue cette formulation d'une
    moyenne-variance naïve.

    **Pourquoi l'aversion au risque est un paramètre déclaré.** Elle fixe
    l'échelle du portefeuille, donc son levier. Un chiffre dans la
    configuration, jamais dans le code.

    **Le contrôle.** À :math:`\gamma = 0` et sans contrainte active, la solution
    fermée est :math:`w^* = \Sigma^{-1}\alpha / \lambda`, et ``check`` la compare
    au résultat du solveur.
    """

    risk_aversion: float = DEFAULT_RISK_AVERSION
    cost_per_unit: float = 0.0
    max_gross: float | None = None
    max_weight: float | None = None
    long_only: bool = False

    def optimize(
        self, *, alpha: pd.Series, covariance: pd.DataFrame, previous: Weights | None = None
    ) -> Weights:
        """Rend les poids par ``cvxpy``."""
        import cvxpy as cp

        idx, cov, a = _align(alpha, covariance)
        assert a is not None
        n = len(idx)
        w = cp.Variable(n)
        w_old = np.zeros(n) if previous is None else previous.reindex(idx).fillna(0.0).to_numpy(dtype=float)
        objective = a @ w - 0.5 * self.risk_aversion * cp.quad_form(w, cp.psd_wrap(cov))
        if self.cost_per_unit > 0:
            objective = objective - self.cost_per_unit * cp.norm1(w - w_old)
        constraints: list[Any] = []
        if self.max_gross is not None:
            constraints.append(cp.norm1(w) <= self.max_gross)
        if self.max_weight is not None:
            constraints.append(cp.abs(w) <= self.max_weight)
        if self.long_only:
            constraints.append(w >= 0)
        problem = cp.Problem(cp.Maximize(objective), constraints)
        problem.solve()
        if w.value is None:
            raise DataQualityError(f"moyenne-variance : le solveur rend « {problem.status} »")
        return _weights(w.value, idx)

    def check(
        self, weights: Weights, covariance: pd.DataFrame, alpha: pd.Series | None = None
    ) -> OptimizerCheck:
        """Compare à la forme fermée quand elle existe, sinon vérifie les bornes."""
        if (
            alpha is None
            or self.cost_per_unit > 0
            or self.max_gross is not None
            or self.max_weight is not None
            or self.long_only
        ):
            gross = float(weights.abs().sum())
            ok = (self.max_gross is None or gross <= self.max_gross + DEFAULT_SOLVER_TOLERANCE) and (
                self.max_weight is None
                or float(weights.abs().max()) <= self.max_weight + DEFAULT_SOLVER_TOLERANCE
            )
            return OptimizerCheck("mean_variance_bounds", ok, {"gross": gross})
        idx, cov, a = _align(alpha, covariance)
        closed = np.linalg.solve(cov, a) / self.risk_aversion
        gap = float(np.abs(weights.reindex(idx).to_numpy() - closed).max())
        return OptimizerCheck(
            "mean_variance_closed_form", gap < 1e-5 * max(1.0, float(np.abs(closed).max())), {"max_gap": gap}
        )


def compare_optimizers(
    covariance: pd.DataFrame,
    optimizers: dict[str, Any],
    *,
    alpha: pd.Series | None = None,
) -> pd.DataFrame:
    """Applique plusieurs optimiseurs à la même covariance et rend leurs diagnostics.

    Le tableau porte, par optimiseur, la volatilité du portefeuille, le ratio
    de diversification, le nombre effectif de positions
    :math:`1 / \\sum_i w_i^2`, l'exposition brute, et le verdict du contrôle
    indépendant. Il compare des portefeuilles DANS L'ÉCHANTILLON, ce qui ne dit
    rien de leur mérite : seule la phase 7 tranche, hors échantillon.
    """
    rows = []
    for name, opt in optimizers.items():
        kwargs: dict[str, Any] = {"covariance": covariance}
        if alpha is not None:
            kwargs["alpha"] = alpha
        w = opt.optimize(**kwargs)
        chk = (
            opt.check(w, covariance, alpha)
            if isinstance(opt, MeanVarianceWithCosts)
            else opt.check(w, covariance)
        )
        rows.append(
            {
                "optimizer": name,
                "volatility": float(portfolio_volatility(w, covariance)),
                "diversification_ratio": float(diversification_ratio(w, covariance)),
                "effective_positions": float(1.0 / (w**2).sum()) if (w**2).sum() > 0 else float("nan"),
                "gross_exposure": float(w.abs().sum()),
                "check_passed": chk.passed,
                "check_name": chk.name,
            }
        )
    return pd.DataFrame(rows).set_index("optimizer")

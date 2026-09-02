r"""Estimer la matrice de covariance, et savoir de combien elle se trompe.

**Le problème.** La covariance empirique de :math:`N` actifs sur :math:`T`
périodes porte :math:`N(N+1)/2` paramètres. Avec cinquante actifs et cinq ans de
mensuel, c'est 1 275 paramètres estimés sur 60 observations. Un optimiseur
nourri de cette matrice ne répartit pas le risque, il exploite les erreurs
d'estimation. Il surpondère ce dont la variance a été sous-estimée par hasard,
et Michaud (1989) l'appelle pour cette raison un « maximiseur d'erreurs ».

**Les remèdes, du plus simple au plus structuré.** Lisser dans le temps, par
une moyenne mobile exponentielle qui suit les changements de régime. Rétrécir
vers une cible structurée, ce que font Ledoit et Wolf (2004) avec l'intensité
optimale en forme fermée. Imposer une structure factorielle, qui ramène
:math:`N(N+1)/2` paramètres à :math:`N(k+1) + k(k+1)/2`. Débruiter le spectre,
en séparant les valeurs propres porteuses de signal de celles que la théorie des
matrices aléatoires attribue au bruit.

**Ce que ce module ne décide pas.** Aucun estimateur n'est meilleur en général.
Chacun se compare HORS ÉCHANTILLON sur la variance réalisée du portefeuille
qu'il produit. La fonction :func:`risk_model_report` donne les diagnostics qui
aident à choisir : conditionnement, plus petite valeur propre, distance à
l'empirique, intensité de rétrécissement.

**La provenance.** Ledoit et Wolf (2004a), « A Well-Conditioned Estimator for
Large-Dimensional Covariance Matrices », JMVA 88, pour la cible identité.
Ledoit et Wolf (2004b), « Honey, I Shrunk the Sample Covariance Matrix », JPM
30(4), pour la cible à corrélation constante. RiskMetrics (1996) pour la
moyenne exponentielle. Laloux, Cizeau, Bouchaud et Potters (1999) pour le
débruitage par Marchenko-Pastur. Les deux fiches Ledoit-Wolf sont vérifiées
dans ``docs/literature/ledoit_wolf_2004.md``.

**Comment vérifier.** La covariance empirique égale ``numpy.cov``. Le
rétrécissement vers l'identité égale ``sklearn.covariance.LedoitWolf``. La
cible à corrélation constante a toutes ses corrélations hors diagonale égales.
Le modèle factoriel conserve exactement la diagonale de l'empirique. Tous
rendent une matrice symétrique et semi-définie positive, et les tests le
vérifient sur des tirages aléatoires.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from quantlab.core.errors import DataQualityError, InsufficientDataError
from quantlab.core.logging import get_logger
from quantlab.core.types import Frequency, ReturnFrame

__all__ = [
    "DEFAULT_EWMA_HALFLIFE",
    "DEFAULT_PSD_EPSILON",
    "ConstantCorrelationShrinkage",
    "DenoisedCovariance",
    "EWMACovariance",
    "FactorCovariance",
    "LedoitWolfCovariance",
    "RiskModelReport",
    "SampleCovariance",
    "annualize_covariance",
    "condition_number",
    "is_psd",
    "nearest_psd",
    "risk_model_report",
    "to_correlation",
]

_log = get_logger(__name__)

#: Demi-vie par défaut de la moyenne exponentielle, en périodes. Soixante
#: séances font environ un trimestre ; c'est un précepte, pas une mesure.
DEFAULT_EWMA_HALFLIFE = 60
#: Plancher des valeurs propres lors de la projection sur le cône des matrices
#: semi-définies positives. Assez petit pour ne rien déformer, assez grand pour
#: qu'une inversion ne divise pas par zéro.
DEFAULT_PSD_EPSILON = 1e-10


def _validate(returns: ReturnFrame, min_periods: int) -> pd.DataFrame:
    """Rend le tableau nettoyé ou lève, au lieu de rendre une matrice de NaN."""
    if not isinstance(returns, pd.DataFrame):
        raise DataQualityError("la covariance attend un DataFrame dates x actifs")
    clean = returns.dropna(how="any")
    if len(clean) < min_periods:
        raise InsufficientDataError(
            f"{len(clean)} périodes complètes, il en faut au moins {min_periods} pour estimer une covariance"
        )
    if clean.shape[1] < 2:
        raise InsufficientDataError("il faut au moins deux actifs")
    return clean


def _frame(matrix: np.ndarray, columns: pd.Index) -> pd.DataFrame:
    """Rend une matrice symétrisée en DataFrame indexé par actif."""
    sym = 0.5 * (matrix + matrix.T)
    return pd.DataFrame(sym, index=columns, columns=columns)


def is_psd(cov: pd.DataFrame | np.ndarray, tol: float = -1e-10) -> bool:
    """Dit si la matrice est semi-définie positive, à une tolérance numérique près."""
    values = np.linalg.eigvalsh(np.asarray(cov, dtype=float))
    return bool(values.min() >= tol)


def nearest_psd(cov: pd.DataFrame, epsilon: float = DEFAULT_PSD_EPSILON) -> pd.DataFrame:
    r"""Projette une matrice symétrique sur le cône des matrices semi-définies positives.

    **Le problème.** Une covariance estimée sur des séries de longueurs inégales,
    ou débruitée, ou rétrécie maladroitement, peut avoir une valeur propre
    négative. Un optimiseur qui l'inverse rend alors des poids absurdes.

    **La méthode.** Décomposer en valeurs propres, remplacer chaque valeur sous
    ``epsilon`` par ``epsilon``, recomposer :

    .. math::

        \Sigma^{+} = V \, \max(\Lambda, \varepsilon) \, V^\top

    C'est la projection de Frobenius la plus simple. Higham (2002) donne une
    projection qui préserve aussi la diagonale unité d'une corrélation ; elle
    n'est pas nécessaire ici parce que ce module travaille en covariance.

    Args:
        cov: la matrice à corriger.
        epsilon: le plancher des valeurs propres.

    Returns:
        La matrice corrigée, inchangée si elle était déjà semi-définie positive.
    """
    a = np.asarray(cov, dtype=float)
    a = 0.5 * (a + a.T)
    values, vectors = np.linalg.eigh(a)
    if values.min() >= epsilon:
        return _frame(a, cov.columns)
    fixed = (vectors * np.maximum(values, epsilon)) @ vectors.T
    return _frame(fixed, cov.columns)


def condition_number(cov: pd.DataFrame) -> float:
    """Rend le rapport de la plus grande à la plus petite valeur propre.

    Un conditionnement de :math:`10^6` signifie qu'une erreur relative de
    :math:`10^{-6}` sur la matrice devient une erreur relative de l'ordre de un
    sur son inverse, donc sur les poids d'un optimiseur de variance minimale.
    """
    values = np.linalg.eigvalsh(np.asarray(cov, dtype=float))
    smallest = values.min()
    if smallest <= 0:
        return float("inf")
    return float(values.max() / smallest)


def to_correlation(cov: pd.DataFrame) -> pd.DataFrame:
    """Rend la matrice de corrélation d'une covariance."""
    a = np.asarray(cov, dtype=float)
    d = np.sqrt(np.diag(a))
    if (d <= 0).any():
        raise DataQualityError("une variance nulle ou négative interdit la corrélation")
    return _frame(a / np.outer(d, d), cov.columns)


def annualize_covariance(cov: pd.DataFrame, frequency: Frequency) -> pd.DataFrame:
    r"""Annualise une covariance périodique en la multipliant par :math:`N`.

    La covariance croît linéairement avec l'horizon sous l'hypothèse
    d'indépendance temporelle, donc :math:`\Sigma_{ann} = N \, \Sigma`. La
    volatilité, sa racine, croît en :math:`\sqrt{N}`, ce qui est la même règle
    vue de l'autre côté. L'hypothèse et sa limite sont celles de
    :func:`quantlab.analytics.risk.annualization_bias`.
    """
    return cov * frequency.periods_per_year


@dataclass(frozen=True)
class SampleCovariance:
    r"""La covariance empirique, le point de départ et le repère de tous les autres.

    .. math::

        \hat{\Sigma} = \frac{1}{T - \delta} \sum_{t=1}^{T} (r_t - \bar r)(r_t - \bar r)^\top

    :math:`T` est le nombre de périodes, :math:`\delta` le ``ddof``, un par
    défaut pour l'estimateur sans biais. Elle est sans biais mais bruitée, et
    son bruit croît avec :math:`N/T`. Elle satisfait le protocole
    :class:`quantlab.core.protocols.RiskModel`.
    """

    ddof: int = 1
    min_periods: int = 2

    def covariance(self, returns: ReturnFrame) -> pd.DataFrame:
        """Rend la covariance empirique des rendements."""
        clean = _validate(returns, max(self.min_periods, self.ddof + 1))
        return _frame(np.cov(clean.to_numpy(dtype=float), rowvar=False, ddof=self.ddof), clean.columns)


@dataclass(frozen=True)
class EWMACovariance:
    r"""La covariance à pondération exponentielle de RiskMetrics (1996).

    **L'intuition.** Le passé récent dit plus sur le risque de demain que le
    passé lointain, et une pondération qui décroît géométriquement le formalise
    sans fenêtre à couper.

    .. math::

        \Sigma_t = \lambda \, \Sigma_{t-1} + (1 - \lambda) \, r_t r_t^\top,
        \qquad \lambda = 0{,}5^{1/h}

    :math:`h` est la demi-vie en périodes, :math:`\lambda` le facteur de
    décroissance, et :math:`r_t` le vecteur des rendements CENTRÉS ou non selon
    ``assume_zero_mean``. RiskMetrics suppose la moyenne nulle, ce qui est
    raisonnable en quotidien et discutable en mensuel ; le défaut ici centre.

    **La correspondance à retenir.** Une demi-vie de 60 périodes donne
    :math:`\lambda = 0{,}98853`, et le poids cumulé des 60 dernières périodes
    vaut exactement 50 %, ce qui est la définition de la demi-vie. RiskMetrics
    publiait :math:`\lambda = 0{,}94` en quotidien, soit une demi-vie de 11,2
    séances, et :math:`0{,}97` en mensuel, soit 22,8 mois.

    **Les limites.** Le nombre effectif d'observations vaut environ
    :math:`(1+\lambda)/(1-\lambda)`, soit 173 pour une demi-vie de 60, ce qui
    reste peu pour cinquante actifs. L'estimateur n'est pas garanti bien
    conditionné, et ``nearest_psd`` est appliqué à la sortie.

    **Comment vérifier.** Sur deux observations, la récursion se déroule à la
    main, et le test du module le fait. Quand la demi-vie tend vers l'infini,
    l'estimateur tend vers la covariance empirique de moyenne nulle.
    """

    halflife: float = DEFAULT_EWMA_HALFLIFE
    assume_zero_mean: bool = False
    min_periods: int = 2

    @property
    def decay(self) -> float:
        """Le facteur :math:`\\lambda = 0{,}5^{1/h}`."""
        if self.halflife <= 0:
            raise DataQualityError("la demi-vie doit être strictement positive")
        return float(0.5 ** (1.0 / self.halflife))

    def covariance(self, returns: ReturnFrame) -> pd.DataFrame:
        """Rend la covariance exponentielle à la dernière date du tableau."""
        clean = _validate(returns, self.min_periods)
        x = clean.to_numpy(dtype=float)
        if not self.assume_zero_mean:
            x = x - x.mean(axis=0)
        lam = self.decay
        n = x.shape[1]
        sigma = np.zeros((n, n))
        weight_sum = 0.0
        # Récurrence explicite, normalisée par la somme des poids pour qu'un
        # échantillon court ne soit pas écrasé vers zéro par l'initialisation.
        for row in x:
            sigma = lam * sigma + (1.0 - lam) * np.outer(row, row)
            weight_sum = lam * weight_sum + (1.0 - lam)
        return nearest_psd(_frame(sigma / weight_sum, clean.columns))


@dataclass(frozen=True)
class LedoitWolfCovariance:
    r"""Le rétrécissement de Ledoit et Wolf (2004a) vers l'identité mise à l'échelle.

    .. math::

        \hat{\Sigma}_{LW} = (1 - \delta) \, S + \delta \, \mu I,
        \qquad \mu = \frac{\mathrm{tr}(S)}{N}

    :math:`S` est la covariance empirique, :math:`\mu I` la cible, et
    :math:`\delta \in [0, 1]` l'intensité optimale, celle qui minimise
    l'espérance de la distance de Frobenius à la vraie matrice. Elle a une
    forme fermée, et elle tend vers zéro quand :math:`T` croît à :math:`N` fixé,
    vers un quand :math:`N/T` explose.

    **Pourquoi ici.** La cible identité ne suppose rien, ce qui en fait le
    rétrécissement par défaut quand on ne sait rien de la structure.

    **Comment vérifier.** Le résultat égale ``sklearn.covariance.LedoitWolf``
    exactement, à l'option ``assume_centered`` près, et le test du module le
    prouve. C'est le seul estimateur de ce module qui appelle scikit-learn.
    """

    min_periods: int = 2

    def covariance(self, returns: ReturnFrame) -> pd.DataFrame:
        """Rend la covariance rétrécie vers l'identité."""
        from sklearn.covariance import LedoitWolf

        clean = _validate(returns, self.min_periods)
        est = LedoitWolf(assume_centered=False).fit(clean.to_numpy(dtype=float))
        _log.debug("rétrécissement identité", extra={"shrinkage": float(est.shrinkage_)})
        return _frame(est.covariance_, clean.columns)

    def shrinkage(self, returns: ReturnFrame) -> float:
        """Rend l'intensité :math:`\\delta` retenue, entre zéro et un."""
        from sklearn.covariance import LedoitWolf

        clean = _validate(returns, self.min_periods)
        return float(LedoitWolf(assume_centered=False).fit(clean.to_numpy(dtype=float)).shrinkage_)


@dataclass(frozen=True)
class ConstantCorrelationShrinkage:
    r"""Le rétrécissement de Ledoit et Wolf (2004b) vers la corrélation constante.

    **L'intuition.** Les actions se ressemblent : leur corrélation moyenne dit
    déjà beaucoup. La cible :math:`F` garde les variances empiriques et remplace
    chaque corrélation par la corrélation moyenne :math:`\bar\rho`. Rétrécir
    vers :math:`F` tire les corrélations extrêmes, souvent des artefacts
    d'échantillon, vers le centre.

    .. math::

        F_{ij} = \bar\rho \sqrt{S_{ii} S_{jj}} \ (i \ne j), \qquad F_{ii} = S_{ii}

    .. math::

        \hat{\Sigma} = \delta^{*} F + (1 - \delta^{*}) S,
        \qquad \delta^{*} = \max\!\left(0, \min\!\left(1, \frac{\kappa}{T}\right)\right),
        \qquad \kappa = \frac{\pi - \rho}{\gamma}

    :math:`\pi` estime la somme des variances asymptotiques des éléments de
    :math:`S`, :math:`\rho` la somme des covariances asymptotiques entre
    :math:`S` et :math:`F`, et :math:`\gamma` la distance de Frobenius au carré
    entre :math:`F` et :math:`S`. Les trois sont transcrits de l'annexe B de
    l'article, que la fiche de littérature a confrontée au texte.

    **Comment vérifier.** La cible a toutes ses corrélations hors diagonale
    égales, :math:`\delta^{*}` reste dans :math:`[0, 1]`, et il décroît vers
    zéro quand :math:`T` croît. Les tests le vérifient ; un contrôle contre
    l'implémentation de référence en MATLAB de Ledoit et Wolf reste **non
    fait**, faute d'accès, et il est écrit comme tel.
    """

    min_periods: int = 3

    def _pieces(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
        t, n = x.shape
        xc = x - x.mean(axis=0)
        sample = (xc.T @ xc) / t
        var = np.diag(sample)
        sd = np.sqrt(var)
        corr = sample / np.outer(sd, sd)
        rbar = (corr.sum() - n) / (n * (n - 1))
        target = rbar * np.outer(sd, sd)
        np.fill_diagonal(target, var)

        # pi : somme des variances asymptotiques des entrées de S.
        y = xc**2
        pi_mat = (y.T @ y) / t - sample**2
        pi_hat = pi_mat.sum()

        # rho : diagonale plus terme croisé de l'annexe B.
        rho_diag = np.trace(pi_mat)
        term1 = ((xc**3).T @ xc) / t
        term2 = var[:, None] * sample
        theta = term1 - term2
        np.fill_diagonal(theta, 0.0)
        rho_off = (rbar * (np.outer(1.0 / sd, sd) * theta)).sum()
        rho_hat = rho_diag + rho_off

        gamma_hat = float(((target - sample) ** 2).sum())
        kappa = (pi_hat - rho_hat) / gamma_hat if gamma_hat > 0 else 0.0
        delta = float(max(0.0, min(1.0, kappa / t)))
        return sample, target, delta

    def shrinkage(self, returns: ReturnFrame) -> float:
        """Rend l'intensité :math:`\\delta^{*}` retenue."""
        clean = _validate(returns, self.min_periods)
        return self._pieces(clean.to_numpy(dtype=float))[2]

    def target(self, returns: ReturnFrame) -> pd.DataFrame:
        """Rend la cible à corrélation constante :math:`F`."""
        clean = _validate(returns, self.min_periods)
        _, target, _ = self._pieces(clean.to_numpy(dtype=float))
        return _frame(target, clean.columns)

    def covariance(self, returns: ReturnFrame) -> pd.DataFrame:
        """Rend la covariance rétrécie vers la corrélation constante."""
        clean = _validate(returns, self.min_periods)
        sample, target, delta = self._pieces(clean.to_numpy(dtype=float))
        _log.debug("rétrécissement corrélation constante", extra={"shrinkage": delta})
        return nearest_psd(_frame(delta * target + (1.0 - delta) * sample, clean.columns))


@dataclass(frozen=True)
class FactorCovariance:
    r"""Un modèle factoriel statistique par composantes principales.

    .. math::

        \Sigma = B F B^\top + D

    :math:`B` porte les chargements des :math:`N` actifs sur :math:`k`
    composantes principales, :math:`F` la covariance diagonale de ces
    composantes, et :math:`D` la variance résiduelle propre à chaque actif. Le
    nombre de paramètres tombe de :math:`N(N+1)/2` à :math:`N(k+1) + k`.

    **Pourquoi c'est mieux conditionné.** Le bruit d'estimation vit dans les
    petites valeurs propres, et le modèle les remplace par une diagonale. Le
    prix est un biais : les corrélations hors des :math:`k` facteurs sont
    ramenées à zéro.

    **Comment vérifier.** La diagonale de :math:`\Sigma` égale exactement celle
    de l'empirique, parce que :math:`D` absorbe ce que les facteurs
    n'expliquent pas. Avec :math:`k = N`, le modèle rend l'empirique.
    """

    n_factors: int = 3
    min_periods: int = 3

    def covariance(self, returns: ReturnFrame) -> pd.DataFrame:
        """Rend la covariance du modèle factoriel."""
        clean = _validate(returns, self.min_periods)
        x = clean.to_numpy(dtype=float)
        n = x.shape[1]
        if not 1 <= self.n_factors <= n:
            raise DataQualityError(f"n_factors doit être entre 1 et {n}, reçu {self.n_factors}")
        sample = np.cov(x, rowvar=False, ddof=1)
        values, vectors = np.linalg.eigh(sample)
        order = np.argsort(values)[::-1][: self.n_factors]
        loadings = vectors[:, order]
        factor_cov = np.diag(values[order])
        systematic = loadings @ factor_cov @ loadings.T
        specific = np.diag(np.maximum(np.diag(sample) - np.diag(systematic), 0.0))
        return _frame(systematic + specific, clean.columns)


@dataclass(frozen=True)
class DenoisedCovariance:
    r"""Le débruitage du spectre par la loi de Marchenko-Pastur, via ``skfolio``.

    **L'intuition.** Sur une matrice de corrélation purement aléatoire de
    dimensions :math:`N \times T`, les valeurs propres se répartissent entre
    deux bornes connues, :math:`(1 \pm \sqrt{N/T})^2`. Celles qui les dépassent
    portent du signal, les autres du bruit, et on remplace ces dernières par
    leur moyenne.

    **La provenance.** Laloux, Cizeau, Bouchaud et Potters (1999), « Noise
    Dressing of Financial Correlation Matrices », Physical Review Letters 83.
    L'implémentation est celle de ``skfolio.moments.DenoiseCovariance``, ce
    module n'en étant que l'enveloppe, conformément à l'ADR-011.

    **La limite.** La borne suppose des rendements indépendants dans le temps
    et de variance finie. Des rendements à queues épaisses élargissent le
    spectre du bruit, et le seuil devient trop bas.
    """

    min_periods: int = 3

    def covariance(self, returns: ReturnFrame) -> pd.DataFrame:
        """Rend la covariance débruitée."""
        from skfolio.moments import DenoiseCovariance as _Denoise

        clean = _validate(returns, self.min_periods)
        est = _Denoise().fit(clean)
        return nearest_psd(_frame(np.asarray(est.covariance_, dtype=float), clean.columns))


@dataclass(frozen=True)
class RiskModelReport:
    """Les diagnostics qui aident à choisir un estimateur."""

    name: str
    n_assets: int
    n_periods: int
    condition_number: float
    smallest_eigenvalue: float
    frobenius_distance_to_sample: float
    mean_correlation: float
    shrinkage: float | None


def risk_model_report(returns: ReturnFrame, models: dict[str, object]) -> pd.DataFrame:
    """Compare plusieurs estimateurs sur le même tableau de rendements.

    Args:
        returns: les rendements, dates en lignes, actifs en colonnes.
        models: les estimateurs, par nom, chacun satisfaisant ``RiskModel``.

    Returns:
        Une ligne par estimateur. La distance à l'empirique dit de combien
        l'estimateur s'écarte des données, et le conditionnement de combien un
        optimiseur amplifiera ses erreurs.
    """
    sample = SampleCovariance().covariance(returns)
    rows = []
    for name, model in models.items():
        cov = model.covariance(returns)  # type: ignore[attr-defined]
        a = cov.to_numpy(dtype=float)
        corr = to_correlation(cov).to_numpy()
        n = a.shape[0]
        rows.append(
            RiskModelReport(
                name=name,
                n_assets=n,
                n_periods=len(returns.dropna()),
                condition_number=condition_number(cov),
                smallest_eigenvalue=float(np.linalg.eigvalsh(a).min()),
                frobenius_distance_to_sample=float(np.linalg.norm(a - sample.to_numpy(), "fro")),
                mean_correlation=float((corr.sum() - n) / (n * (n - 1))),
                shrinkage=float(model.shrinkage(returns)) if hasattr(model, "shrinkage") else None,
            ).__dict__
        )
    return pd.DataFrame(rows).set_index("name")

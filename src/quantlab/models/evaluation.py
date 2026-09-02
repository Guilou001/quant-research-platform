"""Mesurer une prévision transversale : le R² hors échantillon et le test de Diebold et Mariano.

**Le problème.** Un modèle qui prévoit des rendements mensuels explique, au
mieux, quelques millièmes de leur variabilité. La métrique doit distinguer
0,4 % de 0,0 %. Elle doit tomber sous zéro quand le modèle fait pire que ne
rien prévoir. Et elle ne doit pas déclarer un modèle meilleur qu'un autre sur
du bruit autocorrélé.

**Ce que le module fait.** Le R² hors échantillon de Gu, Kelly et Xiu (2020),
dont le dénominateur est la somme des carrés SANS centrage. Et le test de
Diebold et Mariano (1995) sur les pertes moyennées par date, avec un écart type
corrigé à la Newey-West.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

from quantlab.analytics.regression import newey_west_lags
from quantlab.core.errors import ConfigError, InsufficientDataError
from quantlab.models.panel import DATE_LEVEL, ENTITY_LEVEL

__all__ = [
    "MIN_PERIODS_DM",
    "DieboldMarianoResult",
    "diebold_mariano",
    "oos_r2",
    "predictions_to_wide",
    "r2_by_date",
    "squared_errors",
]

#: Le nombre minimal de dates pour un test de Diebold et Mariano.
MIN_PERIODS_DM: int = 8


def _aligned(realized: pd.Series, predicted: pd.Series) -> tuple[np.ndarray, np.ndarray, pd.Index]:
    """Rend les deux séries alignées sur leur index commun, manquants retirés."""
    joined = pd.concat([realized.rename("y"), predicted.rename("p")], axis=1, join="inner").dropna()
    if joined.empty:
        raise InsufficientDataError("aucune observation commune entre réalisé et prévu.")
    return joined["y"].to_numpy(dtype=float), joined["p"].to_numpy(dtype=float), joined.index


def oos_r2(realized: pd.Series, predicted: pd.Series, *, center: float = 0.0) -> float:
    r"""Rend le R² hors échantillon, part de la somme des carrés que la prévision explique.

    **Le problème.** Le R² ordinaire compare la prévision à la moyenne de
    l'échantillon de test, une information que personne n'avait au moment de
    prévoir. Il flatte tout modèle d'un montant qui ne vient pas de lui.

    **L'intuition.** Comparer la prévision à zéro, la prévision de celui qui
    ne sait rien. Un modèle qui fait pire que zéro a un R² négatif, et cela se
    voit.

    **La formule.**

    .. math::

        R^2_{oos} = 1 - \frac{\sum_{i,t}(r_{i,t+1} - \hat r_{i,t+1})^2}
                             {\sum_{i,t}(r_{i,t+1} - c)^2}

    **Les variables.** :math:`r` le rendement réalisé, :math:`\hat r` la
    prévision, :math:`c` le centre, zéro par défaut.

    **Les hypothèses.** Les rendements sont en excès du taux sans risque, de
    sorte que zéro est une prévision sensée.

    **La provenance.** Gu, Kelly et Xiu (2020), équation (16), rapporté ; la
    note 34 chiffre à trois points l'écart avec un centrage sur la moyenne
    historique.

    **Les limites.** Le R² agrège des titres et des dates ; un modèle bon
    certaines années et mauvais d'autres se lit par :func:`r2_by_date`.

    **Les alternatives.** Le centrage sur la moyenne d'apprentissage, permis
    par ``center``.

    **Pourquoi cette méthode ici.** C'est la métrique de l'article répliqué,
    et sa cible publiée.

    **Comment vérifier.** Prévoir exactement rend 1, prévoir zéro rend 0, et
    prévoir :math:`r + 1` sur :math:`(1, 2, 3)` rend :math:`1 - 3/14`.

    Args:
        realized: les rendements réalisés, indexés par (date, titre) ou par date.
        predicted: les prévisions, même index.
        center: la prévision de référence au dénominateur.

    Returns:
        Le R² hors échantillon, en fraction, éventuellement négatif.

    Raises:
        InsufficientDataError: aucune observation commune, ou dénominateur nul.
    """
    y, p, _ = _aligned(realized, predicted)
    denominator = float(np.sum((y - float(center)) ** 2))
    if denominator <= 0.0:
        raise InsufficientDataError("le dénominateur du R² est nul : les réalisés valent tous le centre.")
    return 1.0 - float(np.sum((y - p) ** 2)) / denominator


def r2_by_date(realized: pd.Series, predicted: pd.Series, *, center: float = 0.0) -> pd.Series:
    """Rend le R² hors échantillon date par date, sur un panneau indexé par (date, titre)."""
    y, p, index = _aligned(realized, predicted)
    if index.nlevels != 2:
        raise ConfigError("r2_by_date exige un index (date, titre).")
    frame = pd.DataFrame({"num": (y - p) ** 2, "den": (y - float(center)) ** 2}, index=index)
    grouped = frame.groupby(level=DATE_LEVEL).sum()
    out = 1.0 - grouped["num"] / grouped["den"].where(grouped["den"] > 0.0)
    return out.rename("r2_oos")


def squared_errors(realized: pd.Series, predicted: pd.Series) -> pd.Series:
    """Rend la perte quadratique de chaque observation commune."""
    y, p, index = _aligned(realized, predicted)
    return pd.Series((y - p) ** 2, index=index, name="squared_error")


@dataclass(frozen=True)
class DieboldMarianoResult:
    """Le résultat d'un test de Diebold et Mariano entre deux modèles.

    Attributes:
        statistic: la statistique, positive quand le second modèle perd moins.
        pvalue: la valeur p bilatérale, loi normale.
        mean_difference: la perte moyenne du premier moins celle du second.
        n_periods: le nombre de dates.
        lags: le nombre de retards de la correction de Newey-West.
    """

    statistic: float
    pvalue: float
    mean_difference: float
    n_periods: int
    lags: int


def _mean_by_date(loss: pd.Series) -> pd.Series:
    """Ramène une perte par (date, titre) à une perte moyenne par date."""
    if loss.index.nlevels == 2:
        return loss.groupby(level=DATE_LEVEL).mean()
    return loss


def diebold_mariano(loss_a: pd.Series, loss_b: pd.Series, *, lags: int | None = None) -> DieboldMarianoResult:
    r"""Teste si deux modèles ont la même perte de prévision, en corrigeant l'autocorrélation.

    **Le problème.** Deux R² hors échantillon diffèrent toujours. Savoir si la
    différence dépasse le bruit demande un test, et les pertes mensuelles de
    prévision sont autocorrélées, ce qui ruine le t de Student ordinaire.

    **L'intuition.** On regarde la différence de perte, date par date, et on
    teste si sa moyenne est nulle avec un écart type qui compte les
    autocovariances. Les pertes de chaque date sont d'abord moyennées sur les
    titres, comme dans l'article, pour que le test porte sur des dates et non
    sur des couples (date, titre) massivement dépendants.

    **La formule.**

    .. math::

        d_t = \bar L^{(a)}_t - \bar L^{(b)}_t, \qquad
        DM = \frac{\bar d}{\sqrt{\hat V / T}}, \qquad
        \hat V = \hat\gamma_0 + 2\sum_{k=1}^{L}\left(1 - \tfrac{k}{L+1}\right)\hat\gamma_k

    **Les variables.** :math:`\bar L_t` la perte moyenne de la date
    :math:`t`, :math:`\hat\gamma_k` l'autocovariance empirique d'ordre
    :math:`k` de :math:`d`, :math:`L` le nombre de retards.

    **Les hypothèses.** La différence de perte est stationnaire. Le nombre de
    retards suit la règle de Stock et Watson de
    :func:`quantlab.analytics.regression.newey_west_lags` quand il n'est pas
    donné. Aucune correction de petit échantillon n'est appliquée.

    **La provenance.** Diebold et Mariano (1995), Comparing predictive
    accuracy, Journal of Business and Economic Statistics 13, rapporté ; Gu,
    Kelly et Xiu (2020), section 3.4, pour la moyenne transversale préalable.

    **Les limites.** Le test compare deux modèles à la fois ; sur treize
    modèles, il y a 78 paires, et le nombre de comparaisons entre dans le
    compte des essais.

    **Les alternatives.** Le test de Giacomini et White (2006), conditionnel.

    **Pourquoi cette méthode ici.** C'est celui de l'article, et il est
    exact sur la statistique de ce module.

    **Comment vérifier.** Des pertes identiques rendent zéro et une valeur p
    de un ; la statistique égale le t de Student HAC d'une régression de
    :math:`d_t` sur une constante, sans correction de petit échantillon.

    Args:
        loss_a: la perte du premier modèle, par (date, titre) ou par date.
        loss_b: la perte du second modèle, même index.
        lags: le nombre de retards, ou ``None`` pour la règle empirique.

    Returns:
        La statistique, sa valeur p et ses ingrédients.

    Raises:
        InsufficientDataError: moins de :data:`MIN_PERIODS_DM` dates communes.
    """
    a = _mean_by_date(loss_a)
    b = _mean_by_date(loss_b)
    d = (a - b).dropna()
    n = len(d)
    if n < MIN_PERIODS_DM:
        raise InsufficientDataError(f"{n} date(s) commune(s), {MIN_PERIODS_DM} exigées pour le test.")
    values = d.to_numpy(dtype=float)
    mean = float(values.mean())
    centered = values - mean
    n_lags = int(newey_west_lags(n)) if lags is None else int(lags)
    if n_lags < 0:
        raise ConfigError(f"lags doit être positif ou nul, reçu {lags!r}.")
    variance = float(np.dot(centered, centered)) / n
    for k in range(1, min(n_lags, n - 1) + 1):
        gamma = float(np.dot(centered[k:], centered[:-k])) / n
        variance += 2.0 * (1.0 - k / (n_lags + 1.0)) * gamma
    if variance <= 0.0 or not math.isfinite(variance):
        return DieboldMarianoResult(0.0, 1.0, mean, n, n_lags)
    statistic = mean / math.sqrt(variance / n)
    pvalue = float(2.0 * (1.0 - stats.norm.cdf(abs(statistic))))
    return DieboldMarianoResult(float(statistic), pvalue, mean, n, n_lags)


def predictions_to_wide(predictions: pd.Series) -> pd.DataFrame:
    """Rend un tableau large, dates en lignes et titres en colonnes, depuis des prévisions longues."""
    if predictions.index.nlevels != 2:
        raise ConfigError("les prévisions sont indexées par (date, titre).")
    return predictions.unstack(ENTITY_LEVEL).sort_index()  # noqa: PD010 - un pivot sans agrégation est voulu

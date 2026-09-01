r"""Les mesures de risque hors perte maximale, et ce que chacune refuse de voir.

**Le problème.** Un chiffre unique ne décrit pas le risque d'une stratégie. La
variance le résume par la dispersion moyenne, ce qui suffit pour un portefeuille
gaussien et pour aucun autre. Deux séries de même écart type peuvent perdre
2 % ou 40 % dans leur pire mois, et la variance ne fait aucune différence entre
les deux.

**Pourquoi la variance n'épuise pas le risque.** Trois raisons, mesurables
chacune.

1. Elle est symétrique. Un gain de 5 % et une perte de 5 % pèsent le même poids
   dans l'écart type, alors que l'investisseur ne les vit pas de la même façon.
   La déviation à la baisse de Sortino et Satchell (2001) sépare les deux.
2. Elle ne dit rien de la forme de la queue. Sous loi normale, un rendement
   inférieur à quatre écarts types arrive une fois tous les 125 ans en
   quotidien, une seule queue comptée (chiffre mesuré, 125,3 ans). Sur les
   rendements réels des actions, l'aplatissement excédentaire dépasse couramment
   5, chiffre RAPPORTÉ par la littérature et non mesuré dans ce dépôt, et
   l'événement arrive des dizaines de fois plus souvent.
3. Elle suppose l'indépendance temporelle dès qu'on l'annualise. La racine de
   252 est fausse quand les rendements sont autocorrélés, et
   :func:`annualization_bias` mesure de combien plutôt que de le supposer nul.

**Ce que ce module rend.** Quatre familles de mesures. La dispersion, avec
l'écart type et les déviations à la baisse et à la hausse. La forme, avec
l'asymétrie et l'aplatissement. La queue, avec la valeur à risque et la perte
moyenne au-delà. Le biais d'annualisation de Lo (2002), enfin. La perte
maximale, elle, vit dans son propre module et n'est pas dupliquée ici.

**Convention de signe, valable dans tout le module.** La valeur à risque et la
perte attendue au-delà sont exprimées en PERTE POSITIVE. Une valeur à risque de
0,0905 se lit « perdre 9,05 % ou davantage arrive avec probabilité alpha ». Le
signe n'est jamais forcé : sur une série qui ne perd jamais, la valeur à risque
sort négative, et c'est une information, pas une anomalie à corriger.

**Sous-additivité, et pourquoi elle sépare les deux mesures.** Artzner, Delbaen,
Eber et Heath (1999) posent quatre axiomes pour une mesure de risque cohérente.
L'un d'eux est la sous-additivité : le risque d'une somme ne dépasse pas la
somme des risques, autrement dit la diversification ne peut pas nuire. La valeur à risque
viole cet axiome. Contre-exemple à deux obligations indépendantes, chacune
faisant défaut avec probabilité 4 % pour une perte de 100, sinon 0. À
alpha = 5 %, la valeur à risque de chaque obligation seule vaut 0, puisque
96 % > 95 % des tirages ne perdent rien. Le portefeuille des deux perd au moins
100 avec probabilité 1 - 0,96² = 7,84 % > 5 %, donc sa valeur à risque vaut 100,
soit plus que 0 + 0. La perte attendue au-delà, elle, est sous-additive, ce
qu'Acerbi et Tasche (2002) établissent, et c'est la raison pour laquelle Bâle
III l'a substituée à la valeur à risque en 2019.

Références :

- Artzner, P., Delbaen, F., Eber, J.-M. et Heath, D. (1999), « Coherent Measures
  of Risk », *Mathematical Finance*, 9(3), 203-228.
- Acerbi, C. et Tasche, D. (2002), « On the Coherence of Expected Shortfall »,
  *Journal of Banking and Finance*, 26(7), 1487-1503.
- Lo, A. W. (2002), « The Statistics of Sharpe Ratios », *Financial Analysts
  Journal*, 58(4), 36-52.
- Sortino, F. et Satchell, S. (2001), *Managing Downside Risk in Financial
  Markets*, Butterworth-Heinemann.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Literal

import numpy as np
import numpy.typing as npt
from scipy import integrate, stats

from quantlab.core.calendars import annualization_factor
from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.logging import get_logger
from quantlab.core.types import Frequency, ReturnSeries

__all__ = [
    "DEFAULT_ALPHA",
    "DEFAULT_QUANTILE_METHOD",
    "DEFAULT_TAIL_LOWER",
    "DEFAULT_TAIL_UPPER",
    "annualization_bias",
    "cornish_fisher_quantile",
    "downside_deviation",
    "expected_shortfall",
    "expected_shortfall_factor",
    "gain_to_pain",
    "hit_rate",
    "kurtosis",
    "lo_annualization_factor",
    "sample_autocorrelation",
    "semi_variance",
    "skewness",
    "tail_ratio",
    "upside_deviation",
    "value_at_risk",
    "volatility",
]

log = get_logger(__name__)

#: Tout ce qui se convertit en vecteur de rendements de période, sans réindexation.
type ReturnsInput = ReturnSeries | npt.NDArray[np.floating] | Sequence[float]

#: Les trois façons d'estimer une queue implémentées ici.
type VarMethod = Literal["historical", "gaussian", "cornish_fisher"]

#: Les deux conventions de dénominateur de la déviation à la baisse.
type DownsideDenominator = Literal["total", "below"]

#: Probabilité de queue par défaut. 5 % est la convention de la gestion d'actifs ;
#: la réglementation bancaire travaille plutôt à 1 % (valeur à risque) et 2,5 %
#: (perte attendue au-delà, Bâle III).
DEFAULT_ALPHA: float = 0.05

#: Méthode d'interpolation du quantile empirique, au sens de ``numpy.quantile``.
#: « linear » est le défaut de NumPy et de pandas, donc celui qui se compare le
#: plus facilement au reste de la littérature appliquée.
DEFAULT_QUANTILE_METHOD: str = "linear"

#: Bornes du rapport de queue. 95 % et 5 % sont l'usage des bibliothèques de
#: mesure de performance, dont ``empyrical`` ; source académique primaire non
#: trouvée pour ce choix précis, et la docstring de :func:`tail_ratio` le redit.
DEFAULT_TAIL_UPPER: float = 0.95
DEFAULT_TAIL_LOWER: float = 0.05


# --------------------------------------------------------------------------- #
# Préparation des entrées
# --------------------------------------------------------------------------- #


def _to_array(returns: ReturnsInput, *, min_obs: int, what: str) -> npt.NDArray[np.float64]:
    """Rend un vecteur de flottants sans valeur manquante, ou lève.

    Args:
        returns: la série de rendements de période.
        min_obs: le nombre minimal d'observations valides que le calcul exige.
        what: le nom du calcul, cité dans le message d'erreur.

    Returns:
        Les rendements valides, dans leur ordre d'origine.

    Raises:
        InsufficientDataError: si les valeurs valides sont moins nombreuses que
            ``min_obs``.

    Note:
        Les valeurs manquantes sont retirées, jamais remplacées. Combler un
        rendement manquant par zéro fabrique une séance calme qui n'a pas eu
        lieu, ce qui abaisse la volatilité mesurée sans que personne le voie.
    """
    values = np.asarray(returns, dtype=float).ravel()
    valid = values[~np.isnan(values)]
    if valid.size < min_obs:
        raise InsufficientDataError(
            f"{what} exige au moins {min_obs} observation(s) valide(s), {valid.size} fournie(s)"
        )
    return valid


def _check_alpha(alpha: float) -> None:
    """Vérifie que la probabilité de queue est dans l'intervalle ouvert (0, 1)."""
    if not 0.0 < alpha < 1.0:
        raise ConfigError(f"alpha doit être strictement entre 0 et 1, reçu {alpha}")


def _scale(frequency: Frequency, annualize: bool) -> float:
    """Rend le multiplicateur d'annualisation d'un écart type, ou 1 s'il est inutile."""
    if not annualize:
        return 1.0
    return math.sqrt(annualization_factor(frequency))


# --------------------------------------------------------------------------- #
# Dispersion
# --------------------------------------------------------------------------- #


def volatility(
    returns: ReturnsInput,
    frequency: Frequency = Frequency.DAILY,
    *,
    annualize: bool = True,
    ddof: int = 1,
) -> float:
    r"""Rend l'écart type des rendements, annualisé par défaut.

    **Le problème.** Mesurer la dispersion d'une série de rendements avec un
    seul nombre, comparable d'une fréquence à l'autre.

    **L'intuition.** L'écart type est la distance moyenne, au sens quadratique,
    entre un rendement et son espérance. La mise au carré donne plus de poids
    aux écarts extrêmes qu'une moyenne des écarts absolus, ce qui est un choix
    et non une nécessité.

    .. math::

        \hat{\sigma} = \sqrt{\frac{1}{n - \mathrm{ddof}}
                       \sum_{t=1}^{n} (r_t - \bar{r})^2}
        \qquad
        \hat{\sigma}_{ann} = \hat{\sigma}\sqrt{N}

    Définition des variables : :math:`r_t` le rendement de la période
    :math:`t` ; :math:`\bar{r}` sa moyenne d'échantillon ; :math:`n` le nombre
    d'observations valides ; :math:`\mathrm{ddof}` le nombre de degrés de
    liberté retirés ; :math:`N` le nombre de périodes par an de la fréquence.

    **Pourquoi ddof = 1.** La moyenne :math:`\bar{r}` est estimée sur les mêmes
    données, donc les écarts à cette moyenne sont mécaniquement plus petits que
    les écarts à la vraie espérance. Diviser par :math:`n` sous-estime la
    variance ; diviser par :math:`n-1`, la correction de Bessel, rend un
    estimateur sans biais de la VARIANCE. Restriction à énoncer tout de suite :
    la racine d'un estimateur sans biais de la variance n'est pas un estimateur
    sans biais de l'écart type, l'inégalité de Jensen l'interdit. Le biais
    résiduel vaut environ :math:`-\sigma/(4n)`, soit -0,1 % sur 250 séances,
    et il est ignoré ici comme dans toute la littérature appliquée.

    **Hypothèses.** Rendements de même loi et indépendants dans le temps pour
    que l'annualisation par racine de :math:`N` soit valable. Espérance et
    variance finies, ce que les lois stables d'exposant inférieur à 2 ne
    garantissent pas.

    **Provenance.** La correction du dénominateur porte le nom de F. W. Bessel.
    La règle de la racine du temps est du folklore financier ; sa critique
    chiffrée est de Lo (2002).

    **Limites.** La volatilité est symétrique, aveugle à la forme de la queue et
    instable dans le temps. Sur les rendements quotidiens d'actions, elle est
    fortement autocorrélée, ce qui est la raison d'être des modèles GARCH.

    **Alternatives.** Trois, selon ce qui gêne. L'écart absolu moyen, plus
    robuste aux valeurs extrêmes. L'estimateur de Rogers et Satchell fondé sur
    les extrêmes intrajournaliers, plus efficace à nombre d'observations égal.
    Un GARCH(1,1) quand la volatilité conditionnelle est ce qui intéresse.

    **Pourquoi celle-ci ici.** C'est le dénominateur du ratio de Sharpe et
    l'entrée des optimiseurs à variance moyenne. Elle doit être présente,
    déclarée, et accompagnée des mesures qui disent ce qu'elle rate.

    **Comment vérifier.** Sur une série constante, elle vaut exactement zéro.
    Elle est homogène de degré un : multiplier les rendements par :math:`c > 0`
    multiplie le résultat par :math:`c`. Sur les mêmes données et le même
    ``ddof``, elle égale ``numpy.std`` à la précision machine.

    Args:
        returns: les rendements de période, valeurs manquantes retirées.
        frequency: la fréquence d'observation, qui fixe :math:`N`.
        annualize: si faux, rend l'écart type par période, sans mise à l'échelle.
        ddof: degrés de liberté retirés du dénominateur, 1 par défaut.

    Returns:
        L'écart type, annualisé ou par période.

    Raises:
        InsufficientDataError: moins de ``ddof + 1`` observations valides.

    Example:
        Sur quatre rendements de -1 %, +1 %, -1 %, +1 %, la moyenne vaut 0 et la
        somme des carrés 0,0004. Avec ddof = 1, la variance vaut
        0,0004 / 3 = 1,3333e-4 et l'écart type par période 0,011547.
    """
    values = _to_array(returns, min_obs=ddof + 1, what="volatility")
    return float(np.std(values, ddof=ddof) * _scale(frequency, annualize))


def semi_variance(
    returns: ReturnsInput,
    threshold: float = 0.0,
    *,
    frequency: Frequency = Frequency.DAILY,
    annualize: bool = False,
    denominator: DownsideDenominator = "total",
) -> float:
    r"""Rend la semi-variance sous le seuil, le carré de la déviation à la baisse.

    **Le problème.** La variance compte les surprises heureuses comme du risque.
    La semi-variance ne retient que les écarts défavorables.

    **L'intuition.** On garde la même mécanique que la variance, la moyenne des
    carrés des écarts, et on remplace chaque écart favorable par zéro avant
    d'élever au carré. Ce qui dépasse le seuil vers le haut ne coûte rien.

    .. math::

        SV = \frac{1}{D} \sum_{t=1}^{n} \min(r_t - \tau, 0)^2

    Définition des variables : :math:`\tau` le seuil, exprimé dans l'unité des
    rendements et donc par période ; :math:`D` le dénominateur, discuté dans
    :func:`downside_deviation` ; :math:`n` le nombre d'observations.

    **Hypothèses.** Le seuil est constant. Un seuil qui bouge, par exemple un
    taux sans risque variable, se soustrait des rendements en amont.

    **Provenance.** Markowitz (1959), chapitre 9, qui préférait la semi-variance
    à la variance et l'a écartée pour son coût de calcul en 1959.

    **Limites.** Elle ignore la moitié de l'information, ce qui rend son
    estimation plus bruitée à échantillon égal. Elle n'est pas additive entre
    actifs, donc il n'existe pas de décomposition simple d'un portefeuille.

    **Alternatives.** La variance complète, la perte attendue au-delà, la perte
    maximale.

    **Pourquoi ici.** C'est le dénominateur du ratio de Sortino, et le carré
    exact de :func:`downside_deviation`, identité qui sert de test.

    **Comment vérifier.** Avec un seuil nul et une série sans rendement
    négatif, elle vaut zéro. La somme de la semi-variance et de sa symétrique à
    la hausse égale la moyenne des carrés des écarts au seuil, sous la
    convention « total ».

    Args:
        returns: les rendements de période.
        threshold: le seuil par période sous lequel un écart compte, 0 par défaut.
        frequency: la fréquence, utile seulement si ``annualize`` est vrai.
        annualize: si vrai, multiplie par le nombre de périodes par an, une
            variance s'annualisant linéairement et non en racine.
        denominator: « total » divise par le nombre total d'observations,
            « below » par le seul nombre d'observations sous le seuil.

    Returns:
        La semi-variance, dans l'unité d'un rendement au carré.
    """
    deviation = downside_deviation(
        returns,
        threshold,
        frequency=frequency,
        annualize=False,
        denominator=denominator,
    )
    factor = annualization_factor(frequency) if annualize else 1.0
    return float(deviation**2 * factor)


def downside_deviation(
    returns: ReturnsInput,
    threshold: float = 0.0,
    *,
    frequency: Frequency = Frequency.DAILY,
    annualize: bool = True,
    denominator: DownsideDenominator = "total",
) -> float:
    r"""Rend la déviation à la baisse sous un seuil, convention Sortino-Satchell.

    **Le problème.** Un investisseur ne craint pas la dispersion, il craint la
    perte. Une stratégie qui saute parfois de +20 % et jamais de -20 % a une
    volatilité élevée et un risque faible.

    **L'intuition.** On remplace chaque écart à la moyenne par l'écart au seuil
    quand il est défavorable, et par zéro quand il ne l'est pas. La série des
    écarts favorables est écrasée à zéro, pas retirée.

    .. math::

        DD = \sqrt{\frac{1}{D} \sum_{t=1}^{n} \min(r_t - \tau, 0)^2}
        \qquad
        DD_{ann} = DD \sqrt{N}

    Définition des variables : :math:`r_t` le rendement de la période
    :math:`t` ; :math:`\tau` le seuil par période ; :math:`n` le nombre
    d'observations valides ; :math:`D` le dénominateur ; :math:`N` le nombre de
    périodes par an.

    **Les deux conventions du dénominateur, et laquelle est appliquée.** Le
    choix de :math:`D` n'est pas cosmétique et change le chiffre du simple au
    double.

    - :math:`D = n`, le nombre TOTAL d'observations. C'est la convention de
      Sortino et Satchell (2001), celle que cette fonction applique par défaut.
      Elle lit la quantité comme un moment partiel d'ordre deux de la loi
      entière : les périodes au-dessus du seuil contribuent un zéro, et ce zéro
      compte. Conséquence à connaître : une stratégie qui perd rarement obtient
      une déviation à la baisse faible parce que le zéro pèse, ce qui est le
      comportement voulu.
    - :math:`D = n_-`, le nombre d'observations SOUS le seuil. C'est l'écart
      type conditionnel des seules pertes, disponible ici par
      ``denominator="below"``. Il répond à une autre question, « quand ça perd,
      de combien », et il n'est pas comparable au premier.

    Ordre de grandeur mesuré sur une loi normale centrée d'écart type 1 : la
    moitié des observations tombant sous zéro, la convention « below » rend un
    chiffre plus grand d'un facteur :math:`\sqrt{2} \approx 1{,}414`. Mélanger
    les deux conventions dans un même tableau fabrique donc un écart de 41 %
    qui ne vient d'aucune donnée.

    **Hypothèses.** Seuil constant et exprimé par période. Pour un seuil annuel,
    le convertir avant l'appel, en divisant par :math:`N` pour un seuil
    arithmétique ou par :math:`(1+\tau_{ann})^{1/N} - 1` pour un seuil
    géométrique.

    **Provenance.** Sortino, F. et Satchell, S. (2001), *Managing Downside Risk
    in Financial Markets*. La racine du moment partiel inférieur d'ordre deux
    remonte à Bawa (1975) et Fishburn (1977).

    **Limites.** Plus bruitée que l'écart type, puisqu'elle n'utilise qu'une
    partie de l'échantillon. Très sensible au seuil : passer de 0 au taux sans
    risque déplace le résultat de plusieurs points sur des rendements mensuels.

    **Alternatives.** La perte attendue au-delà, qui regarde la queue plutôt que
    la moitié inférieure ; la perte maximale, qui regarde le chemin.

    **Pourquoi ici.** Elle est le dénominateur du ratio de Sortino, et son
    ambiguïté de dénominateur est une source d'erreur documentée dans la
    pratique, ce que le paramètre explicite rend impossible à commettre en
    silence.

    **Comment vérifier.** Sur une série dont tous les rendements dépassent le
    seuil, elle vaut exactement zéro en convention « total ». Son carré égale
    :func:`semi_variance`. Sur une série symétrique autour du seuil, la
    convention « below » rend :math:`\sqrt{2}` fois la convention « total » à
    la précision de l'échantillon.

    Args:
        returns: les rendements de période.
        threshold: le seuil par période, 0 par défaut.
        frequency: la fréquence d'observation, qui fixe :math:`N`.
        annualize: si faux, rend la déviation par période.
        denominator: « total » (Sortino-Satchell, défaut) ou « below ».

    Returns:
        La déviation à la baisse, annualisée par défaut.

    Raises:
        ConfigError: si ``denominator`` n'est ni « total » ni « below ».
        InsufficientDataError: série vide, ou convention « below » sans aucune
            observation sous le seuil, cas où l'estimateur n'est pas défini.

    Example:
        Sur cinq rendements de +2 %, -1 %, +3 %, -3 %, +1 % et un seuil nul, les
        écarts défavorables valent -1 % et -3 %. La somme des carrés vaut
        0,0001 + 0,0009 = 0,001. En convention « total », la moyenne vaut
        0,001 / 5 = 0,0002 et la déviation par période 0,014142. En convention
        « below », 0,001 / 2 = 0,0005 et 0,022361.
    """
    if denominator not in {"total", "below"}:
        raise ConfigError(f"denominator doit valoir « total » ou « below », reçu {denominator!r}")
    values = _to_array(returns, min_obs=1, what="downside_deviation")
    shortfall = np.minimum(values - threshold, 0.0)
    if denominator == "total":
        count = values.size
    else:
        count = int(np.count_nonzero(shortfall < 0.0))
        if count == 0:
            raise InsufficientDataError(
                "aucune observation sous le seuil : la convention « below » n'est pas définie"
            )
    return float(math.sqrt(float(np.sum(shortfall**2)) / count) * _scale(frequency, annualize))


def upside_deviation(
    returns: ReturnsInput,
    threshold: float = 0.0,
    *,
    frequency: Frequency = Frequency.DAILY,
    annualize: bool = True,
    denominator: DownsideDenominator = "total",
) -> float:
    r"""Rend la déviation à la hausse au-dessus du seuil, symétrique exacte de la baisse.

    **Le problème.** Une déviation à la baisse seule ne dit pas si la stratégie
    est asymétrique ou simplement volatile. Il faut la moitié haute pour le
    savoir, mesurée exactement de la même façon.

    **L'intuition.** La même somme de carrés, sur les seuls écarts favorables.

    .. math::

        UD = \sqrt{\frac{1}{D} \sum_{t=1}^{n} \max(r_t - \tau, 0)^2}

    Définition des variables : identique à :func:`downside_deviation`, le
    minimum étant remplacé par un maximum.

    **Hypothèses, provenance, limites.** Les mêmes que
    :func:`downside_deviation`, dont elle est le miroir. Le moment partiel
    supérieur d'ordre deux est chez Bawa (1975).

    **Pourquoi ici.** Elle vérifie la mise en œuvre de sa symétrique. Sous la
    convention « total », la somme des deux semi-variances égale la moyenne des
    carrés des écarts au seuil, identité exacte que les tests emploient.

    **Alternatives.** Le rapport de la déviation à la hausse sur celle à la
    baisse, dit ratio de volatilité, qui résume l'asymétrie en un nombre ;
    l'asymétrie de :func:`skewness`, qui la mesure au troisième moment.

    **Comment vérifier.** ``upside_deviation(-r, -tau) == downside_deviation(r, tau)``
    à la précision machine, en convention « total ».

    Args:
        returns: les rendements de période.
        threshold: le seuil par période, 0 par défaut.
        frequency: la fréquence d'observation.
        annualize: si faux, rend la déviation par période.
        denominator: « total » (défaut) ou « below », qui compte alors les
            observations AU-DESSUS du seuil.

    Returns:
        La déviation à la hausse, annualisée par défaut.

    Raises:
        ConfigError: si ``denominator`` est inconnu.
        InsufficientDataError: série vide, ou aucune observation au-dessus du
            seuil en convention « below ».
    """
    if denominator not in {"total", "below"}:
        raise ConfigError(f"denominator doit valoir « total » ou « below », reçu {denominator!r}")
    values = _to_array(returns, min_obs=1, what="upside_deviation")
    surplus = np.maximum(values - threshold, 0.0)
    if denominator == "total":
        count = values.size
    else:
        count = int(np.count_nonzero(surplus > 0.0))
        if count == 0:
            raise InsufficientDataError(
                "aucune observation au-dessus du seuil : la convention « below » n'est pas définie"
            )
    return float(math.sqrt(float(np.sum(surplus**2)) / count) * _scale(frequency, annualize))


# --------------------------------------------------------------------------- #
# Forme de la distribution
# --------------------------------------------------------------------------- #


def skewness(returns: ReturnsInput, *, bias: bool = False) -> float:
    r"""Rend l'asymétrie des rendements, estimateur non biaisé par défaut.

    **Le problème.** Deux séries de même moyenne et de même variance peuvent
    avoir des queues opposées. L'asymétrie dit de quel côté la queue est longue.

    **L'intuition.** Le moment centré d'ordre trois, normalisé par le cube de
    l'écart type, change de signe selon que les grands écarts sont surtout
    positifs ou surtout négatifs. Une asymétrie négative signale des pertes
    rares et grosses, profil des stratégies de vente de volatilité.

    .. math::

        g_1 = \frac{\frac{1}{n}\sum (r_t - \bar{r})^3}
                   {\left[\frac{1}{n}\sum (r_t - \bar{r})^2\right]^{3/2}}
        \qquad
        G_1 = \frac{\sqrt{n(n-1)}}{n-2}\, g_1

    Définition des variables : :math:`g_1` l'estimateur des moments, biaisé ;
    :math:`G_1` l'estimateur ajusté de Fisher et Pearson ; :math:`n` le nombre
    d'observations.

    **Quel estimateur.** Par défaut :math:`G_1`, obtenu par
    ``scipy.stats.skew(x, bias=False)``, c'est-à-dire l'ajusté de
    Fisher-Pearson, celui d'Excel et de SAS. Avec ``bias=True``, l'estimateur
    des moments :math:`g_1`, celui de Stata par défaut. Sur 250 observations,
    le rapport des deux vaut 1,006, donc la différence est visible sur trois
    décimales, pas sur le signe.

    **Hypothèses.** Moment d'ordre trois fini. Sur des rendements très à queue
    lourde, l'estimateur ne converge pas et son écart type d'échantillon est
    trompeur.

    **Provenance.** Joanes, D. N. et Gill, C. A. (1998), « Comparing measures of
    sample skewness and kurtosis », *The Statistician*, 47(1), 183-189, qui
    compare les trois estimateurs usuels.

    **Limites.** Très bruitée. Sous loi normale, l'écart type asymptotique de
    :math:`G_1` vaut :math:`\sqrt{6/n}`, soit 0,155 sur 250 observations : une
    asymétrie mesurée à -0,20 n'est pas distinguable de zéro sur une année de
    données quotidiennes.

    **Alternatives.** L'asymétrie de Bowley, fondée sur les quartiles, bien plus
    robuste ; l'asymétrie de Pearson par mode et médiane.

    **Pourquoi ici.** Elle entre dans le développement de Cornish-Fisher, donc
    dans la valeur à risque modifiée, et son signe qualifie la stratégie.

    **Comment vérifier.** Elle vaut zéro sur toute série symétrique autour de sa
    moyenne. Elle est invariante par changement d'échelle positif et par
    translation. Elle égale ``scipy.stats.skew`` sur les mêmes données.

    Args:
        returns: les rendements de période.
        bias: si vrai, rend :math:`g_1` sans correction d'échantillon.

    Returns:
        L'asymétrie, nombre sans unité.

    Raises:
        InsufficientDataError: moins de trois observations valides.
    """
    values = _to_array(returns, min_obs=3, what="skewness")
    return float(stats.skew(values, bias=bias))


def kurtosis(returns: ReturnsInput, *, excess: bool = True, bias: bool = False) -> float:
    r"""Rend l'aplatissement des rendements, excédentaire et non biaisé par défaut.

    **Le problème.** Savoir à quelle fréquence la série produit des mouvements
    que la loi normale déclarerait impossibles.

    **L'intuition.** Le moment centré d'ordre quatre, normalisé, pèse les grands
    écarts à la puissance quatre. Une valeur supérieure à 3, ou supérieure à 0
    en version excédentaire, signale des queues plus épaisses que la normale.

    .. math::

        g_2 = \frac{\frac{1}{n}\sum (r_t - \bar{r})^4}
                   {\left[\frac{1}{n}\sum (r_t - \bar{r})^2\right]^{2}} - 3
        \qquad
        G_2 = \frac{n-1}{(n-2)(n-3)}\left[(n+1)g_2 + 6\right]

    Définition des variables : :math:`g_2` l'aplatissement excédentaire des
    moments ; :math:`G_2` sa correction d'échantillon ; :math:`n` le nombre
    d'observations.

    **Quel estimateur.** Par défaut :math:`G_2`, soit
    ``scipy.stats.kurtosis(x, fisher=True, bias=False)``, l'estimateur non
    biaisé sous loi normale, celui d'Excel. Avec ``excess=False``, la fonction
    ajoute 3 et rend l'aplatissement brut, dont la valeur de référence normale
    est 3 et non 0. Avec ``bias=True``, l'estimateur des moments.

    **Hypothèses.** Moment d'ordre quatre fini, ce qu'une loi de Student à trois
    degrés de liberté ne satisfait pas.

    **Provenance.** Joanes et Gill (1998), même article que pour l'asymétrie.

    **Limites.** Encore plus bruitée que l'asymétrie : écart type asymptotique
    :math:`\sqrt{24/n}` sous normalité, soit 0,31 sur 250 observations. Elle est
    en outre dominée par les quelques points les plus extrêmes, si bien que
    retirer une seule séance de krach peut la diviser par deux.

    **Alternatives.** L'aplatissement de Moors, fondé sur les octiles ; l'indice
    de queue de Hill, qui estime directement l'exposant de la queue.

    **Pourquoi ici.** C'est le second ingrédient de Cornish-Fisher, et le chiffre
    qui justifie de ne pas se contenter d'une valeur à risque gaussienne.

    **Comment vérifier.** Sur une loi normale simulée de grande taille, la
    version excédentaire tend vers zéro. Elle égale ``scipy.stats.kurtosis`` sur
    les mêmes données et les mêmes options.

    Args:
        returns: les rendements de période.
        excess: si vrai, retranche 3 et rend l'aplatissement excédentaire.
        bias: si vrai, rend l'estimateur des moments sans correction.

    Returns:
        L'aplatissement, nombre sans unité.

    Raises:
        InsufficientDataError: moins de quatre observations valides.
    """
    values = _to_array(returns, min_obs=4, what="kurtosis")
    return float(stats.kurtosis(values, fisher=excess, bias=bias))


# --------------------------------------------------------------------------- #
# Queue : Cornish-Fisher, valeur à risque, perte attendue au-delà
# --------------------------------------------------------------------------- #


def cornish_fisher_quantile(z: float, skew: float, excess_kurtosis: float) -> float:
    r"""Rend le quantile normal corrigé de l'asymétrie et de l'aplatissement.

    **Le problème.** Le quantile gaussien ignore la forme des queues. Sur des
    rendements d'actions, il place le seuil de perte trop près du centre et fait
    paraître sûr ce qui ne l'est pas.

    **L'intuition.** Le développement de Cornish-Fisher déplace le quantile
    normal d'un terme proportionnel à l'asymétrie et d'un terme proportionnel à
    l'aplatissement excédentaire. C'est un développement asymptotique, donc une
    correction locale et non un changement de loi.

    .. math::

        z_{CF} = z + \frac{z^2 - 1}{6}S
                   + \frac{z^3 - 3z}{24}K
                   - \frac{2z^3 - 5z}{36}S^2

    Définition des variables : :math:`z` le quantile de la loi normale centrée
    réduite au niveau voulu ; :math:`S` l'asymétrie ; :math:`K` l'aplatissement
    EXCÉDENTAIRE, donc nul sous loi normale.

    **Hypothèses.** Asymétrie et aplatissement petits. Le développement est
    tronqué à l'ordre deux en :math:`S` et à l'ordre un en :math:`K`.

    **Provenance.** Cornish, E. A. et Fisher, R. A. (1937), « Moments and
    cumulants in the specification of distributions », *Revue de l'Institut
    International de Statistique*, 5(4), 307-320. Son usage en valeur à risque
    vient de Zangari, P. (1996), « A VaR methodology for portfolios that include
    options », *RiskMetrics Monitor*.

    **Limites, la principale d'abord.** La fonction :math:`z \mapsto z_{CF}` peut
    cesser d'être croissante quand :math:`S` et :math:`K` sortent d'un domaine
    étroit, décrit par Maillard (2018). Hors de ce domaine, le résultat n'est
    plus le quantile d'aucune loi de probabilité, et un aplatissement de 8, banal
    sur des rendements quotidiens, suffit à sortir du domaine. La fonction ne
    refuse pas ces entrées, elle les calcule ; c'est à l'appelant de déclarer
    l'asymétrie et l'aplatissement qu'il a mesurés.

    **Alternatives.** La valeur à risque historique, sans hypothèse de forme ;
    l'ajustement d'une loi de Student ou d'une loi des valeurs extrêmes
    généralisée sur les dépassements.

    **Pourquoi ici.** Elle donne une correction fermée, sans estimation
    supplémentaire, à partir de deux moments qu'on mesure de toute façon. Elle
    sert de pont entre la valeur à risque gaussienne et l'historique.

    **Comment vérifier.** Avec :math:`S = K = 0`, elle rend exactement
    :math:`z`. En :math:`z = 1`, les deux premiers termes s'annulent
    partiellement et il reste :math:`1 - K/12 + S^2/12`. En :math:`z = 0`, elle
    rend :math:`-S/6`.

    Args:
        z: le quantile normal centré réduit à corriger.
        skew: l'asymétrie de la série.
        excess_kurtosis: l'aplatissement EXCÉDENTAIRE, zéro sous normalité.

    Returns:
        Le quantile corrigé, dans l'échelle centrée réduite.

    Example:
        Avec :math:`z = 1`, :math:`S = 0{,}6` et :math:`K = 2{,}4`, le calcul
        donne :math:`1 - 2{,}4/12 + 0{,}36/12 = 1 - 0{,}2 + 0{,}03 = 0{,}83`.
    """
    z2 = z * z
    z3 = z2 * z
    return float(
        z
        + (z2 - 1.0) * skew / 6.0
        + (z3 - 3.0 * z) * excess_kurtosis / 24.0
        - (2.0 * z3 - 5.0 * z) * skew * skew / 36.0
    )


def expected_shortfall_factor(
    alpha: float = DEFAULT_ALPHA,
    skew: float = 0.0,
    excess_kurtosis: float = 0.0,
    *,
    quad_limit: int = 200,
) -> float:
    r"""Rend le multiplicateur d'écart type de la perte attendue au-delà.

    **Le problème.** La perte attendue au-delà mélange trois choses : la position
    de la loi, son échelle, et la forme de sa queue. Isoler la forme donne un
    nombre qui ne dépend d'aucune donnée, donc vérifiable contre une table.

    **L'intuition.** Dans un modèle de position et d'échelle, la perte attendue
    au-delà s'écrit :math:`ES = \sigma \, f(\alpha) - \mu`, où :math:`f` ne
    dépend que de la forme de la loi. Cette fonction rend :math:`f`.

    .. math::

        f(\alpha) = -\frac{1}{\alpha}\int_0^{\alpha} z_{CF}(p)\, dp
        \qquad
        f_{gauss}(\alpha) = \frac{\varphi(z_\alpha)}{\alpha}

    Définition des variables : :math:`z_{CF}(p)` le quantile de Cornish-Fisher
    au niveau :math:`p` ; :math:`z_\alpha = \Phi^{-1}(\alpha)` ; :math:`\varphi`
    la densité normale centrée réduite ; :math:`\alpha` la probabilité de queue.

    **Le cas gaussien est traité en forme fermée.** Quand l'asymétrie et
    l'aplatissement excédentaire sont tous deux nuls, l'intégrale vaut
    :math:`-\varphi(z_\alpha)` exactement, et la fonction rend
    :math:`\varphi(z_\alpha)/\alpha` sans quadrature. Sinon, l'intégrale est
    calculée par ``scipy.integrate.quad``, déterministe et sans tirage.

    **Hypothèses.** La loi est entièrement décrite par sa position, son échelle
    et le développement de Cornish-Fisher. Les limites de ce développement,
    décrites dans :func:`cornish_fisher_quantile`, se transmettent telles quelles.

    **Provenance.** La forme fermée gaussienne est chez McNeil, Frey et
    Embrechts (2015), *Quantitative Risk Management*, 2e édition, chapitre 2.
    L'intégration du quantile est la définition même de la perte attendue
    au-delà chez Acerbi et Tasche (2002).

    **Limites.** Hors du cas gaussien, le facteur n'a de sens que si le
    développement de Cornish-Fisher est monotone sur :math:`(0, \alpha)`. Quand
    il ne l'est pas, la quadrature intègre une fonction qui n'est plus un
    quantile, et le nombre rendu perd son interprétation sans qu'aucune erreur
    ne soit levée.

    **Alternatives.** Le facteur d'une loi de Student ajustée, qui reste un
    quantile valable partout ; le facteur empirique, la moyenne de la queue
    observée, qui n'impose aucune forme mais exige beaucoup d'observations.

    **Pourquoi ici.** Séparer la forme des données rend la vérification
    possible : la valeur gaussienne 2,062713 est tabulée dans les manuels, donc
    le test ne dépend d'aucun chiffre sorti de ce code.

    **Comment vérifier.** Avec ``skew=0`` et ``excess_kurtosis=0``, la voie
    numérique et la forme fermée coïncident. À :math:`\alpha = 5\%`, la valeur
    vaut 2,062713, et le quantile correspondant 1,644854 : la perte moyenne
    au-delà dépasse le seuil de 25 %.

    Args:
        alpha: la probabilité de queue, strictement entre 0 et 1.
        skew: l'asymétrie de la loi.
        excess_kurtosis: son aplatissement excédentaire.
        quad_limit: nombre maximal de sous-intervalles de la quadrature.

    Returns:
        Le multiplicateur :math:`f(\alpha)`, sans unité.

    Raises:
        ConfigError: si ``alpha`` sort de l'intervalle ouvert (0, 1).
    """
    _check_alpha(alpha)
    z_alpha = float(stats.norm.ppf(alpha))
    if skew == 0.0 and excess_kurtosis == 0.0:
        return float(stats.norm.pdf(z_alpha) / alpha)
    integral, _ = integrate.quad(
        lambda p: cornish_fisher_quantile(float(stats.norm.ppf(p)), skew, excess_kurtosis),
        0.0,
        alpha,
        limit=quad_limit,
    )
    return float(-integral / alpha)


def value_at_risk(
    returns: ReturnsInput,
    alpha: float = DEFAULT_ALPHA,
    *,
    method: VarMethod = "historical",
    ddof: int = 1,
    quantile_method: str = DEFAULT_QUANTILE_METHOD,
) -> float:
    r"""Rend la valeur à risque, exprimée en PERTE POSITIVE.

    **Le problème.** Résumer la queue gauche par un seuil : quelle perte n'est
    dépassée qu'avec probabilité :math:`\alpha` sur une période.

    **L'intuition.** On coupe la distribution des rendements au quantile
    :math:`\alpha` et on change le signe. Le résultat est une perte, donc
    positif dès que le quantile est négatif.

    .. math::

        VaR_\alpha = -q_\alpha(r)
        \qquad
        VaR^{gauss}_\alpha = -(\mu + \sigma z_\alpha)
        \qquad
        VaR^{CF}_\alpha = -(\mu + \sigma z_{CF})

    Définition des variables : :math:`q_\alpha(r)` le quantile empirique des
    rendements au niveau :math:`\alpha` ; :math:`\mu` et :math:`\sigma` la
    moyenne et l'écart type d'échantillon ; :math:`z_\alpha = \Phi^{-1}(\alpha)`,
    négatif pour :math:`\alpha < 0{,}5` ; :math:`z_{CF}` le quantile corrigé de
    :func:`cornish_fisher_quantile`.

    **La convention de signe, déclarée.** Le résultat est une perte positive.
    Sur une série qui ne perd jamais, il ressort négatif : la « pire » perte
    est un gain. Aucun repliement à zéro n'est appliqué, parce qu'un repliement
    silencieux ferait passer un portefeuille de trésorerie pour un portefeuille
    risqué de risque nul.

    **Hypothèses, par méthode.**

    - « historical » : les rendements passés sont un tirage représentatif de la
      loi future. Aucune hypothèse de forme, mais aucune extrapolation non plus,
      donc la valeur à risque ne peut pas dépasser la pire perte observée.
    - « gaussian » : rendements normaux, indépendants, de moyenne et variance
      stables. C'est l'hypothèse de RiskMetrics (1996).
    - « cornish_fisher » : normalité corrigée par les moments d'ordre trois et
      quatre, avec les limites du développement.

    **L'ampleur de l'erreur gaussienne sur des rendements leptokurtiques.**
    Chiffre modélisé, sur une loi de Student standardisée à variance unitaire,
    ce qui est un repère usuel pour les rendements quotidiens d'actions. À
    :math:`\alpha = 1\%`, le quantile gaussien vaut 2,326 écarts types. Avec
    cinq degrés de liberté, aplatissement excédentaire 6, le vrai quantile vaut
    2,606, soit 12 % de plus. Avec quatre degrés de liberté, aplatissement
    infini au sens de la loi, il vaut 2,650, soit 14 % de plus. Autrement dit,
    une valeur à risque gaussienne à 1 % sous-estime la perte d'environ un
    huitième, et la sous-estimation grandit quand :math:`\alpha` diminue. À
    :math:`\alpha = 5\%`, l'erreur change de sens : le quantile de Student à
    cinq degrés vaut 1,561 contre 1,645 pour la normale, donc la valeur à risque
    gaussienne SURESTIME la perte de 5 %. La queue épaisse se paie au centre.

    **Provenance.** J.P. Morgan et Reuters (1996), *RiskMetrics Technical
    Document*, 4e édition, pour la version gaussienne ; Zangari (1996) pour la
    version Cornish-Fisher ; Jorion, P. (2006), *Value at Risk*, 3e édition,
    pour la synthèse.

    **Limites, celle qui décide d'abord.** La valeur à risque n'est pas
    sous-additive, donc elle peut monter quand on diversifie. Artzner et alii
    (1999) le démontrent par le contre-exemple à deux obligations rappelé en
    tête de module. Elle ne dit rien non plus de ce qui se passe au-delà du
    seuil, si bien que deux portefeuilles de même valeur à risque peuvent perdre
    12 % ou 90 % dans le pire cas.

    **Alternatives.** La perte attendue au-delà, sous-additive, retenue par
    Bâle III ; la théorie des valeurs extrêmes pour les très petits
    :math:`\alpha` ; la valeur à risque conditionnelle d'un GARCH quand la
    volatilité varie.

    **Pourquoi ici.** Elle reste le langage commun des tables de risque et des
    régulateurs, et le laboratoire doit pouvoir la reproduire. Elle n'est jamais
    publiée seule : la perte attendue au-delà l'accompagne.

    **Comment vérifier.** Sur une série construite dont le quantile est connu à
    la main, la version historique rend ce quantile changé de signe. La version
    Cornish-Fisher coïncide avec la gaussienne quand l'asymétrie et
    l'aplatissement excédentaire injectés sont nuls. Elle est homogène de degré
    un et décroissante en :math:`\alpha`.

    Args:
        returns: les rendements de période.
        alpha: la probabilité de queue, 5 % par défaut.
        method: « historical », « gaussian » ou « cornish_fisher ».
        ddof: degrés de liberté de l'écart type des méthodes paramétriques.
        quantile_method: interpolation du quantile empirique, au sens de
            ``numpy.quantile``.

    Returns:
        La valeur à risque de période, en perte positive.

    Raises:
        ConfigError: ``alpha`` hors de (0, 1), ou méthode inconnue.
        InsufficientDataError: données insuffisantes pour la méthode demandée.

    Example:
        Prenons vingt rendements réguliers de -10 % à +9 % par pas de 1 %. Le
        quantile linéaire à 5 % se place en position 19 x 0,05 = 0,95 entre
        -0,10 et -0,09, soit -0,10 + 0,95 x 0,01 = -0,0905. La valeur à risque
        vaut donc 0,0905.
    """
    _check_alpha(alpha)
    if method == "historical":
        values = _to_array(returns, min_obs=1, what="value_at_risk")
        return float(-np.quantile(values, alpha, method=quantile_method))
    if method == "gaussian":
        values = _to_array(returns, min_obs=ddof + 1, what="value_at_risk")
        mu = float(np.mean(values))
        sigma = float(np.std(values, ddof=ddof))
        return float(-(mu + sigma * float(stats.norm.ppf(alpha))))
    if method == "cornish_fisher":
        values = _to_array(returns, min_obs=4, what="value_at_risk")
        mu = float(np.mean(values))
        sigma = float(np.std(values, ddof=ddof))
        z_cf = cornish_fisher_quantile(
            float(stats.norm.ppf(alpha)),
            skewness(values),
            kurtosis(values, excess=True),
        )
        return float(-(mu + sigma * z_cf))
    raise ConfigError(
        f"method doit valoir « historical », « gaussian » ou « cornish_fisher », reçu {method!r}"
    )


def expected_shortfall(
    returns: ReturnsInput,
    alpha: float = DEFAULT_ALPHA,
    *,
    method: VarMethod = "historical",
    ddof: int = 1,
    quantile_method: str = DEFAULT_QUANTILE_METHOD,
) -> float:
    r"""Rend la perte moyenne au-delà de la valeur à risque, en perte positive.

    **Le problème.** La valeur à risque dit où commence la queue et se tait sur
    ce qu'il y a dedans. La perte attendue au-delà répond à la seule question
    qui compte quand la queue se réalise : quand ça casse, combien.

    **L'intuition.** On moyenne les pertes qui dépassent le seuil, au lieu de
    lire le seuil lui-même.

    .. math::

        ES_\alpha = \mathbb{E}\left[L \mid L > VaR_\alpha\right]
        \qquad
        ES^{gauss}_\alpha = \sigma\frac{\varphi(z_\alpha)}{\alpha} - \mu

    Définition des variables : :math:`L = -r` la perte ; :math:`\varphi` la
    densité normale centrée réduite ; :math:`z_\alpha = \Phi^{-1}(\alpha)` ;
    :math:`\mu` et :math:`\sigma` la moyenne et l'écart type des rendements.

    **Ce que fait chaque méthode.** La version historique moyenne les rendements
    inférieurs ou égaux au quantile empirique, puis change le signe. La version
    gaussienne applique la forme fermée ci-dessus. La version Cornish-Fisher
    intègre le quantile corrigé sur :math:`[0, \alpha]`, par
    :func:`expected_shortfall_factor`.

    **Hypothèses.** Les mêmes que :func:`value_at_risk`, méthode par méthode.
    La version historique exige en outre assez d'observations dans la queue :
    à :math:`\alpha = 5\%` sur 250 séances, la moyenne porte sur douze ou treize
    points, et son erreur type est grande.

    **Provenance.** Artzner, Delbaen, Eber et Heath (1999) pour la cohérence,
    Acerbi et Tasche (2002) pour la démonstration de sous-additivité. Puis le
    Comité de Bâle (2019), *Minimum capital requirements for market risk*, pour
    l'adoption réglementaire à 2,5 %.

    **Limites.** Elle est plus difficile à valider a posteriori que la valeur à
    risque : Gneiting (2011) montre qu'elle n'est pas « élicitable » seule, ce
    qui interdit le contrôle par simple comptage de dépassements. Acerbi et
    Székely (2014) proposent les tests employés dans le portefeuille.

    **Alternatives.** La valeur à risque, plus simple à contrôler ; le déficit
    espéré par théorie des valeurs extrêmes pour les queues très fines.

    **Pourquoi ici.** Elle est sous-additive, donc elle récompense la
    diversification au lieu de la punir, et elle regarde dans la queue plutôt
    qu'à son bord.

    **Comment vérifier.** L'inégalité :math:`ES \geq VaR` est vraie par
    construction pour toute méthode, et sert de test de propriété. La version
    gaussienne se compare à l'espérance d'une normale tronquée, calculée par une
    implémentation indépendante. À :math:`\alpha = 5\%`, le rapport
    :math:`ES/VaR` d'une loi normale centrée vaut 2,062713 / 1,644854 = 1,254.

    Args:
        returns: les rendements de période.
        alpha: la probabilité de queue, 5 % par défaut.
        method: « historical », « gaussian » ou « cornish_fisher ».
        ddof: degrés de liberté de l'écart type des méthodes paramétriques.
        quantile_method: interpolation du quantile empirique.

    Returns:
        La perte moyenne au-delà de la valeur à risque, en perte positive.

    Raises:
        ConfigError: ``alpha`` hors de (0, 1), ou méthode inconnue.
        InsufficientDataError: données insuffisantes pour la méthode demandée.
    """
    _check_alpha(alpha)
    if method == "historical":
        values = _to_array(returns, min_obs=1, what="expected_shortfall")
        cutoff = float(np.quantile(values, alpha, method=quantile_method))
        tail = values[values <= cutoff]
        if tail.size == 0:  # pragma: no cover - le quantile empirique majore toujours le minimum
            raise InsufficientDataError("aucune observation au-delà du seuil de valeur à risque")
        return float(-np.mean(tail))
    if method in {"gaussian", "cornish_fisher"}:
        min_obs = ddof + 1 if method == "gaussian" else 4
        values = _to_array(returns, min_obs=min_obs, what="expected_shortfall")
        mu = float(np.mean(values))
        sigma = float(np.std(values, ddof=ddof))
        if method == "gaussian":
            factor = expected_shortfall_factor(alpha)
        else:
            factor = expected_shortfall_factor(
                alpha,
                skewness(values),
                kurtosis(values, excess=True),
            )
        return float(sigma * factor - mu)
    raise ConfigError(
        f"method doit valoir « historical », « gaussian » ou « cornish_fisher », reçu {method!r}"
    )


# --------------------------------------------------------------------------- #
# Biais d'annualisation : Lo (2002)
# --------------------------------------------------------------------------- #


def sample_autocorrelation(
    returns: ReturnsInput,
    max_lags: int,
    *,
    relative_tolerance: float = 1e-12,
) -> npt.NDArray[np.float64]:
    r"""Rend les autocorrélations d'échantillon des retards 1 à ``max_lags``.

    **Le problème.** Annualiser une volatilité par la racine du temps suppose des
    rendements indépendants dans le temps. Cette fonction mesure de combien cette
    hypothèse est fausse sur la série qu'on a réellement.

    **L'intuition.** On corrèle la série avec elle-même décalée de :math:`k`
    périodes. Un coefficient positif dit qu'une bonne période appelle une bonne
    période, ce qui fait grossir la variance d'une somme de périodes.

    .. math::

        \hat{\rho}_k = \frac{\sum_{t=k+1}^{n}(r_t - \bar{r})(r_{t-k} - \bar{r})}
                            {\sum_{t=1}^{n}(r_t - \bar{r})^2}

    Définition des variables : :math:`k` le retard ; :math:`n` le nombre
    d'observations ; :math:`\bar{r}` la moyenne d'échantillon.

    **Quel estimateur.** Le dénominateur porte sur les :math:`n` termes et non
    sur les :math:`n-k` du numérateur. Cet estimateur, dit non ajusté, est
    biaisé vers zéro, et c'est voulu : il garantit une suite d'autocorrélations
    définie positive, ce que la version ajustée ne garantit pas. C'est celui de
    ``statsmodels.tsa.stattools.acf(adjusted=False)``.

    **Limites.** L'écart type d'un :math:`\hat{\rho}_k` sous indépendance vaut
    environ :math:`1/\sqrt{n}`, soit 0,063 sur 250 observations. Un retard
    isolé à 0,10 sur une année de données quotidiennes n'est pas distinguable
    de zéro.

    **Hypothèses.** Stationnarité au second ordre : la moyenne et les
    covariances ne dépendent pas de la date. Une série à tendance viole cette
    hypothèse et rend des autocorrélations proches de 1 qui ne mesurent que la
    tendance.

    **Provenance.** Box, G. et Jenkins, G. (1970), *Time Series Analysis*,
    chapitre 2.

    **Alternatives.** L'estimateur ajusté, de dénominateur :math:`n-k`, sans
    biais mais qui peut rendre une suite non définie positive ; l'autocorrélation
    partielle, qui isole l'apport propre de chaque retard.

    **Pourquoi ici.** C'est l'entrée de :func:`lo_annualization_factor`, et le
    choix du dénominateur y compte : la formule de Lo somme des covariances et
    doit rendre une variance positive.

    **Comment vérifier.** Sur les mêmes données, elle égale
    ``statsmodels.tsa.stattools.acf(x, adjusted=False, fft=False)[1:]`` à la
    précision machine. Sur une série constante, elle lève.

    **La détection d'une série constante, et pourquoi elle est relative.** Une
    comparaison exacte à zéro ne suffit pas. Sur vingt valeurs toutes égales à
    0,02, la moyenne n'est pas représentable en binaire, les écarts valent
    environ 4e-18 et leur somme des carrés 1,2e-34, donc strictement positive.
    Le test porte donc sur le rapport entre la somme des carrés des écarts et
    la somme des carrés des valeurs, mesuré ici à 3e-32 : sous
    ``relative_tolerance``, la série est déclarée constante.

    Args:
        returns: les rendements de période.
        max_lags: le plus grand retard estimé, au moins 1.
        relative_tolerance: seuil sous lequel la variance relative est traitée
            comme nulle. 1e-12 par défaut, soit vingt ordres de grandeur
            au-dessus du bruit d'arrondi mesuré sur une série constante.

    Returns:
        Un vecteur de longueur ``max_lags``, du retard 1 au retard ``max_lags``.

    Raises:
        ConfigError: si ``max_lags`` est inférieur à 1.
        InsufficientDataError: moins de ``max_lags + 2`` observations.
        DataQualityError: si la série est constante, cas où l'autocorrélation
            n'est pas définie faute de variance.
    """
    if max_lags < 1:
        raise ConfigError(f"max_lags doit valoir au moins 1, reçu {max_lags}")
    values = _to_array(returns, min_obs=max_lags + 2, what="sample_autocorrelation")
    centred = values - values.mean()
    denominator = float(np.dot(centred, centred))
    magnitude = float(np.dot(values, values))
    if denominator <= relative_tolerance * magnitude:
        raise DataQualityError("série constante : l'autocorrélation n'est pas définie")
    return np.array(
        [float(np.dot(centred[k:], centred[:-k]) / denominator) for k in range(1, max_lags + 1)],
        dtype=float,
    )


def lo_annualization_factor(
    autocorrelations: npt.NDArray[np.floating] | Sequence[float],
    periods_per_year: float,
) -> float:
    r"""Rend le facteur d'annualisation de Lo (2002), qui remplace la racine de N.

    **Le problème.** Multiplier un écart type de période par :math:`\sqrt{N}`
    suppose des rendements non corrélés dans le temps. Sur un fonds peu liquide
    dont les positions sont valorisées avec retard, l'autocorrélation d'ordre un
    dépasse couramment 0,20, et la volatilité annuelle est alors sous-estimée,
    donc le ratio de Sharpe surestimé.

    **L'intuition.** La variance d'une somme de :math:`N` termes corrélés
    contient les covariances croisées. Chaque paire de dates distantes de
    :math:`k` apparaît :math:`N-k` fois dans la somme, d'où la pondération
    triangulaire.

    .. math::

        \sigma_{ann} = \sigma \sqrt{N + 2\sum_{k=1}^{N-1}(N-k)\rho_k}

    Définition des variables : :math:`\sigma` l'écart type d'une période ;
    :math:`N` le nombre de périodes par an ; :math:`\rho_k` l'autocorrélation
    d'ordre :math:`k` des rendements.

    **Hypothèses.** Rendements stationnaires au second ordre. Les
    autocorrélations sont supposées connues ; en pratique elles sont estimées,
    et l'incertitude de leur estimation n'est pas propagée ici.

    **Provenance.** Lo, A. W. (2002), « The Statistics of Sharpe Ratios »,
    *Financial Analysts Journal*, 58(4), 36-52, équation (7).

    **Limites.** La somme tronquée peut rendre une variance négative si les
    autocorrélations fournies sont fortement négatives, cas où la fonction lève
    plutôt que de rendre la racine d'un nombre négatif. Et sur données réelles,
    estimer 251 autocorrélations quotidiennes ajoute plus de bruit qu'elle
    n'enlève de biais, ce que :func:`annualization_bias` gère par une troncature
    déclarée.

    **Alternatives.** Rééchantillonner la série à la fréquence annuelle et
    mesurer directement, au prix d'un nombre d'observations divisé par
    :math:`N` ; un estimateur de variance de long terme à noyau, Newey et
    West (1987).

    **Pourquoi ici.** Elle chiffre un biais que le laboratoire refuse de
    supposer nul, et sa forme fermée en fait une fonction testable exactement.

    **Comment vérifier.** Avec des autocorrélations toutes nulles, elle rend
    exactement :math:`\sqrt{N}`. Avec :math:`N = 2` et :math:`\rho_1 = 0{,}5`,
    elle rend :math:`\sqrt{2 + 2 \times 1 \times 0{,}5} = \sqrt{3}`.

    Args:
        autocorrelations: les :math:`\rho_k` du retard 1 au retard fourni. Les
            retards au-delà sont traités comme nuls, troncature déclarée.
        periods_per_year: le nombre :math:`N` de périodes par an.

    Returns:
        Le facteur qui multiplie l'écart type de période, à comparer à
        :math:`\sqrt{N}`.

    Raises:
        ConfigError: si ``periods_per_year`` n'est pas strictement positif, ou
            si plus de :math:`N-1` autocorrélations sont fournies.
        DataQualityError: si la somme pondérée rend une variance négative.
    """
    if periods_per_year <= 0:
        raise ConfigError(f"periods_per_year doit être strictement positif, reçu {periods_per_year}")
    rho = np.asarray(autocorrelations, dtype=float).ravel()
    if rho.size > 0 and rho.size > periods_per_year - 1:
        raise ConfigError(
            f"la formule de Lo n'emploie que les retards 1 à N-1, soit {periods_per_year - 1:.0f} "
            f"au plus, {rho.size} fournis"
        )
    lags = np.arange(1, rho.size + 1, dtype=float)
    variance_factor = periods_per_year + 2.0 * float(np.sum((periods_per_year - lags) * rho))
    if variance_factor < 0.0:
        raise DataQualityError(
            f"la somme de Lo rend une variance annuelle négative ({variance_factor:.4f}) : "
            "les autocorrélations fournies ne sont pas compatibles avec une série stationnaire "
            "à cette troncature"
        )
    return float(math.sqrt(variance_factor))


def annualization_bias(
    returns: ReturnsInput,
    frequency: Frequency = Frequency.DAILY,
    max_lags: int | None = None,
) -> float:
    r"""Rend de combien l'annualisation par racine de N se trompe, en rapport.

    **Le problème.** La volatilité annualisée par :math:`\sqrt{N}` est fausse
    dès que les rendements sont autocorrélés, et personne ne sait de combien
    sans le mesurer. Le biais se propage tel quel dans tous les ratios de
    Sharpe publiés, en sens inverse.

    **L'intuition.** On compare la formule de Lo, qui tient compte des
    covariances entre dates, à la racine du temps, qui les suppose nulles.

    .. math::

        \text{rapport} = \frac{\sqrt{N + 2\sum_{k=1}^{m}(N-k)\hat{\rho}_k}}
                              {\sqrt{N}}

    Définition des variables : :math:`N` le nombre de périodes par an ;
    :math:`\hat{\rho}_k` l'autocorrélation d'échantillon d'ordre :math:`k` ;
    :math:`m` le nombre de retards réellement estimés, les suivants étant
    traités comme nuls.

    **Comment lire le résultat.** Un rapport supérieur à 1 dit que la racine du
    temps SOUS-ESTIME la volatilité annuelle, donc surestime le ratio de Sharpe
    du même facteur. Un rapport de 1,15 signifie que le ratio de Sharpe publié
    doit être divisé par 1,15, soit 13 % de moins.

    **La troncature, déclarée.** La formule de Lo somme jusqu'au retard
    :math:`N-1`, soit 251 retards en quotidien. Estimer 251 autocorrélations
    ajoute un bruit d'écart type
    :math:`2\sqrt{\sum_k (N-k)^2 / n}` à un facteur de variance qui vaut
    :math:`N` : sur 5 000 observations quotidiennes, ce bruit atteint 65 pour
    une base de 252, donc l'estimation devient inutilisable. Le nombre de
    retards par défaut suit donc la règle automatique de Newey et West (1994),
    :math:`m = \lfloor 4(n/100)^{2/9} \rfloor`, bornée par :math:`N-1`, par le
    quart de l'échantillon et par 1 au minimum. Sur 5 000 observations, elle
    retient 9 retards.

    **Hypothèses.** Stationnarité au second ordre, et autocorrélations nulles
    au-delà du retard :math:`m`. La seconde est une décision, pas un fait, et
    c'est pourquoi ``max_lags`` est exposé.

    **Provenance.** Lo, A. W. (2002), *Financial Analysts Journal*, 58(4),
    36-52, équation (7). La règle de retard automatique est de Newey, W. et
    West, K. (1994), « Automatic Lag Selection in Covariance Matrix
    Estimation », *Review of Economic Studies*, 61(4), 631-653.

    **Limites.** Le rapport est lui-même estimé, donc bruité. Sur une série
    indépendante de 20 000 observations quotidiennes avec 5 retards, son écart
    type théorique vaut environ 0,016. Sur une année de données quotidiennes, il
    dépasse 0,10 et le rapport ne veut plus rien dire.

    **Alternatives.** Mesurer la volatilité directement à la fréquence annuelle,
    ou par recouvrement glissant sur des fenêtres d'un an, deux voies coûteuses
    en nombre d'observations.

    **Pourquoi ici.** Le portefeuille de recherche refuse d'annualiser sans
    savoir de combien il se trompe. Ce rapport est le chiffre qui accompagne
    toute volatilité annualisée publiée.

    **Comment vérifier.** Sur une série indépendante simulée à graine fixe, le
    rapport vaut 1 à la tolérance déclarée. Sur des autocorrélations toutes
    nulles, la fonction sous-jacente
    :func:`lo_annualization_factor` rend exactement :math:`\sqrt{N}`, donc un
    rapport de 1 exactement.

    Args:
        returns: les rendements de période.
        frequency: la fréquence, qui fixe :math:`N`.
        max_lags: le nombre de retards estimés. Sans valeur, la règle de Newey
            et West (1994) décrite ci-dessus.

    Returns:
        Le rapport entre la volatilité annualisée corrigée et la volatilité
        annualisée par racine de :math:`N`. Vaut 1 exactement pour une série
        déjà annuelle, qu'on n'annualise pas.

    Raises:
        ConfigError: si ``max_lags`` est fourni et inférieur à 1.
        InsufficientDataError: si la série est trop courte pour les retards
            demandés.
        DataQualityError: série constante, ou variance annuelle corrigée
            négative.

    Example:
        Un fonds à valorisation retardée sort à 1,12 sur ses rendements mensuels.
        Sa volatilité annuelle publiée est donc à multiplier par 1,12, et son
        ratio de Sharpe à diviser par le même nombre. Cela fait 11 % de moins :
        la lecture en pourcentage se prend sur l'inverse du rapport,
        1 / 1,12 = 0,893, jamais sur le rapport lui-même.
    """
    values = _to_array(returns, min_obs=3, what="annualization_bias")
    periods = annualization_factor(frequency)
    if periods <= 1.0:
        # Une série déjà annuelle n'est pas annualisée : le rapport vaut 1 par construction.
        return 1.0
    n = values.size
    if max_lags is None:
        automatic = int(4.0 * (n / 100.0) ** (2.0 / 9.0))
        max_lags = max(1, min(automatic, int(periods) - 1, n // 4))
    elif max_lags < 1:
        raise ConfigError(f"max_lags doit valoir au moins 1, reçu {max_lags}")
    rho = sample_autocorrelation(values, max_lags)
    corrected = lo_annualization_factor(rho, periods)
    log.debug(
        "biais d'annualisation mesuré",
        extra={"n": n, "lags": max_lags, "periods_per_year": periods},
    )
    return float(corrected / math.sqrt(periods))


# --------------------------------------------------------------------------- #
# Mesures de queue et de régularité
# --------------------------------------------------------------------------- #


def tail_ratio(
    returns: ReturnsInput,
    *,
    upper: float = DEFAULT_TAIL_UPPER,
    lower: float = DEFAULT_TAIL_LOWER,
    quantile_method: str = DEFAULT_QUANTILE_METHOD,
) -> float:
    r"""Rend le rapport de la queue droite à la queue gauche.

    **Le problème.** L'asymétrie du troisième moment est dominée par les points
    les plus extrêmes, donc très instable. Comparer deux quantiles plutôt que
    deux moments donne une mesure d'asymétrie qu'un seul point ne renverse pas.

    .. math::

        TR = \frac{|q_{u}(r)|}{|q_{l}(r)|}

    Définition des variables : :math:`q_u` le quantile supérieur, 95 % par
    défaut ; :math:`q_l` le quantile inférieur, 5 % par défaut.

    **Comment lire.** Un rapport supérieur à 1 dit que les meilleurs jours sont
    plus gros que les pires, en valeur absolue. Une stratégie de suivi de
    tendance sort typiquement au-dessus de 1, une stratégie de vente de
    volatilité en dessous.

    **Hypothèses.** Aucune sur la forme de la loi. Les deux quantiles doivent
    être estimables, donc l'échantillon doit couvrir les deux queues.

    **Provenance.** Usage répandu dans les bibliothèques de mesure de
    performance, dont ``empyrical``. Aucune source académique primaire trouvée
    pour cette définition précise.

    **Limites.** Deux quantiles extrêmes estimés sur peu de points, donc très
    bruité. Il ne dit rien de ce qui se passe au-delà des seuils.

    **Alternatives.** Le rapport des pertes attendues au-delà des deux côtés,
    qui regarde dans les queues plutôt qu'à leur bord ; l'asymétrie.

    **Pourquoi ici.** Il sert de contrôle de cohérence à :func:`skewness` : les
    deux doivent pointer dans le même sens, et un désaccord signale que
    l'asymétrie mesurée tient à une poignée d'observations.

    **Comment vérifier.** Il vaut 1 sur toute série symétrique autour de zéro,
    et il est invariant par changement d'échelle positif.

    Args:
        returns: les rendements de période.
        upper: le quantile supérieur, entre 0 et 1.
        lower: le quantile inférieur, entre 0 et 1.
        quantile_method: interpolation, au sens de ``numpy.quantile``.

    Returns:
        Le rapport des deux queues, sans unité.

    Raises:
        ConfigError: quantiles hors de (0, 1), ou inférieur au-dessus du supérieur.
        InsufficientDataError: série vide.
        DataQualityError: si le quantile inférieur vaut exactement zéro, cas où
            le rapport n'est pas défini.
    """
    _check_alpha(upper)
    _check_alpha(lower)
    if lower >= upper:
        raise ConfigError(f"lower ({lower}) doit être strictement inférieur à upper ({upper})")
    values = _to_array(returns, min_obs=1, what="tail_ratio")
    numerator = abs(float(np.quantile(values, upper, method=quantile_method)))
    denominator = abs(float(np.quantile(values, lower, method=quantile_method)))
    if denominator == 0.0:
        raise DataQualityError(
            f"le quantile inférieur à {lower:.0%} vaut zéro : le rapport de queue n'est pas défini"
        )
    return numerator / denominator


def hit_rate(returns: ReturnsInput, threshold: float = 0.0) -> float:
    r"""Rend la part des périodes dont le rendement dépasse strictement le seuil.

    **Le problème.** Savoir à quelle fréquence une stratégie a raison, séparément
    de combien elle gagne quand elle a raison. Les deux se compensent, et un
    chiffre unique de performance les confond.

    **L'intuition.** On compte les périodes gagnantes et on divise par leur
    nombre total. Rien de plus, et c'est la source de sa limite.

    .. math::

        HR = \frac{1}{n}\sum_{t=1}^{n} \mathbf{1}\{r_t > \tau\}

    Définition des variables : :math:`\mathbf{1}` l'indicatrice ; :math:`\tau`
    le seuil, nul par défaut ; :math:`n` le nombre d'observations valides.

    **La règle d'égalité, déclarée.** La comparaison est STRICTE. Un rendement
    exactement égal au seuil ne compte pas comme un succès. Le choix importe
    sur des séries à beaucoup de zéros, par exemple une stratégie qui reste
    souvent hors du marché. Compter les zéros comme des succès ferait monter le
    taux de réussite sans qu'aucune position ait gagné.

    **Limites, et c'est la principale.** Un taux de réussite élevé ne dit rien
    de la rentabilité. Une stratégie qui gagne 1 % neuf fois sur dix et perd
    20 % une fois sur dix affiche 90 % de réussite et perd de l'argent. Il se
    lit avec le rapport gain sur peine, jamais seul.

    **Hypothèses.** Aucune sur la loi des rendements. Les périodes doivent être
    de même durée, sans quoi la proportion mélange des unités différentes.

    **Provenance.** Mesure d'usage courant chez les praticiens. Source académique
    primaire non trouvée : elle circule par les manuels de négociation et les
    bibliothèques de mesure de performance, sans article fondateur identifié.

    **Alternatives.** Le rapport gain sur peine, le facteur de profit, la valeur
    espérée par transaction.

    **Pourquoi ici.** Il se lit avec :func:`gain_to_pain`, et le couple des deux
    dit ce qu'aucun des deux ne dit seul : la fréquence des gains et leur taille
    relative aux pertes.

    **Comment vérifier.** Sur dix rendements dont six positifs, il vaut
    exactement 0,6.

    Args:
        returns: les rendements de période.
        threshold: le seuil à dépasser, nul par défaut.

    Returns:
        Une proportion entre 0 et 1.

    Raises:
        InsufficientDataError: série vide.
    """
    values = _to_array(returns, min_obs=1, what="hit_rate")
    return float(np.count_nonzero(values > threshold) / values.size)


def gain_to_pain(returns: ReturnsInput) -> float:
    r"""Rend le rapport gain sur peine de Schwager, somme des rendements sur pertes.

    **Le problème.** Mesurer ce que la stratégie rapporte par unité de douleur
    subie en chemin, sans passer par un écart type qui compte les bonnes
    surprises comme du risque.

    .. math::

        GPR = \frac{\sum_{t=1}^{n} r_t}{\sum_{t=1}^{n} \max(-r_t, 0)}

    Définition des variables : le numérateur est la somme de TOUS les
    rendements, gains et pertes ; le dénominateur la somme des seules pertes,
    en valeur absolue.

    **L'intuition.** Combien d'unités de rendement total la stratégie rend pour
    chaque unité de perte subie en chemin. Schwager retient 1,0 en mensuel
    comme un bon résultat et 2,0 comme excellent, précepte d'auteur sans mesure
    publiée derrière.

    **Hypothèses.** Rendements de même fréquence, sans composition : la somme
    arithmétique n'est pas le rendement cumulé, ce qui rend le chiffre comparable
    entre stratégies mais impropre à décrire une richesse.

    **Provenance.** Schwager, J. (2012), *Hedge Fund Market Wizards*, appendice
    sur les mesures de performance.

    **Limites.** Il dépend de la fréquence : le même flux mesuré en quotidien et
    en mensuel donne deux chiffres différents, le quotidien étant plus bas
    puisqu'il compte plus de pertes. Il n'est donc jamais comparable d'une
    fréquence à l'autre.

    **Alternatives.** Le ratio de Sortino, le facteur de profit, le ratio de
    Calmar quand c'est la perte maximale qui inquiète.

    **Pourquoi ici.** Il complète :func:`hit_rate` : une stratégie qui gagne
    souvent mais perd gros affiche un taux de réussite flatteur et un rapport
    gain sur peine sous 1, et c'est le second qui décide.

    **Comment vérifier.** Sur des rendements de +3 %, -1 %, +2 %, -1 %, la somme
    vaut 0,03 et la peine 0,02, donc le rapport vaut 1,5.

    Args:
        returns: les rendements de période.

    Returns:
        Le rapport gain sur peine, sans unité.

    Raises:
        InsufficientDataError: série vide, ou série sans aucun rendement
            négatif, cas où le rapport n'est pas défini.
    """
    values = _to_array(returns, min_obs=1, what="gain_to_pain")
    pain = float(np.sum(np.maximum(-values, 0.0)))
    if pain == 0.0:
        raise InsufficientDataError("aucun rendement négatif : le rapport gain sur peine n'est pas défini")
    return float(np.sum(values) / pain)

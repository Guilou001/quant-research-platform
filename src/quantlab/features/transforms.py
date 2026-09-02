r"""Les transformations qui font une caractéristique, et la règle qui les gouverne.

**La règle du module, valable partout et sans exception.** Une caractéristique
datée :math:`t` n'utilise que de l'information disponible à :math:`t` inclus.
Une moyenne mobile centrée est interdite, parce qu'elle lit :math:`t+1`. Un
``shift`` négatif est interdit, pour la même raison. La seule sortie de ce
module qui regarde devant est :func:`forward_return`, et elle porte le préfixe
``label_`` pour qu'aucun modèle ne la prenne pour un intrant.

**Pourquoi cette règle mérite un module entier.** Une fuite d'information ne se
voit pas dans une trace d'exécution : le code tourne, les tableaux ont la bonne
forme, et le ratio de Sharpe monte. Elle ne se voit que si on la CHERCHE. La
fonction :func:`assert_causal` la cherche de deux façons, en modifiant les
données après une date puis en les retirant, et exige que la caractéristique
avant cette date ne bouge dans aucun des deux cas.

**Les trois familles réunies ici.** Les retards et les fenêtres glissantes
forment la première, purement mécanique. Les mesures de risque glissantes, la
volatilité exponentielle et la volatilité réalisée, forment la deuxième. Les
signaux de tendance, le momentum et son signe, forment la troisième.

**Ce que ce module ne fait pas.** Il ne normalise rien dans la dimension
transversale. Le z-score entre actifs à une date donnée vit dans
:mod:`quantlab.signals`, et il ne se confond pas avec celui de
:func:`zscore_time_series`, qui compare une série à son propre passé. Il ne
mesure pas la performance non plus : le ratio de Sharpe vit dans
:mod:`quantlab.analytics.ratios`, le repli depuis le sommet dans
:mod:`quantlab.analytics.drawdown`.

**Statut des chiffres cités.** Les exemples numériques des docstrings sont
MODÉLISÉS, calculés depuis les formules qui les précèdent. La correspondance
entre demi-vie et facteur d'oubli est une identité, donc vérifiable, et le test
``test_features_transforms.py`` la vérifie contre :math:`0{,}5^{1/60}` recalculé
indépendamment.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence

import numpy as np
import pandas as pd

from quantlab.core.calendars import annualization_factor
from quantlab.core.errors import (
    ConfigError,
    DataQualityError,
    InsufficientDataError,
    LookAheadError,
)
from quantlab.core.types import Frequency, ReturnKind

__all__ = [
    "CAUSALITY_TOLERANCE",
    "DEFAULT_CUT_FRACTIONS",
    "DEFAULT_PERTURBATION",
    "LABEL_PREFIX",
    "MIN_CAUSALITY_OBS",
    "MIN_RANK_WINDOW",
    "assert_causal",
    "drawdown_feature",
    "equivalent_window",
    "ewma_volatility",
    "forward_return",
    "halflife_to_lambda",
    "lag",
    "lambda_to_halflife",
    "momentum",
    "percent_rank",
    "realized_volatility",
    "rolling_max",
    "rolling_mean",
    "rolling_min",
    "rolling_std",
    "rolling_sum",
    "time_series_momentum_signal",
    "zscore_time_series",
]

#: Les fractions de l'échantillon où :func:`assert_causal` coupe le passé du
#: futur. Trois coupures valent mieux qu'une : une fuite d'un seul pas peut
#: rester invisible sur une coupure placée au mauvais endroit.
DEFAULT_CUT_FRACTIONS: tuple[float, ...] = (0.25, 0.5, 0.75)

#: La quantité ajoutée aux observations postérieures à la coupure. Elle est
#: additive et positive, ce qui garde des prix strictement positifs et déplace
#: aussi bien un rendement nul qu'un rendement quelconque.
DEFAULT_PERTURBATION: float = 1.0

#: L'écart maximal toléré entre la caractéristique de référence et celle
#: recalculée sur données perturbées. Une vraie fuite déplace la sortie de
#: l'ordre de grandeur de la perturbation, donc très au-dessus de ce seuil.
CAUSALITY_TOLERANCE: float = 1e-12

#: Le nombre d'observations sous lequel le contrôle de causalité ne prouve rien.
#: Avec trois points, les trois coupures par défaut se confondent.
MIN_CAUSALITY_OBS: int = 4

#: Le préfixe imposé à toute sortie qui contient de l'information future. Un
#: nom de colonne est le dernier garde-fou avant qu'une étiquette entre dans une
#: matrice d'intrants.
LABEL_PREFIX: str = "label_"

#: La taille minimale d'une fenêtre de rang. Avec une seule observation, le rang
#: relatif n'a pas de dénominateur.
MIN_RANK_WINDOW: int = 2

#: Le paramètre de type des fonctions qui conservent la forme de leur entrée.
type PandasObj = pd.Series | pd.DataFrame


def _validate[T: (pd.Series, pd.DataFrame)](data: T, *, name: str, minimum: int = 1) -> None:
    r"""Refuse une entrée qui rendrait la caractéristique fausse en silence.

    Args:
        data: la série ou le tableau à contrôler.
        name: le nom de l'argument, pour le message d'erreur.
        minimum: nombre d'observations exigé.

    Raises:
        TypeError: si l'objet n'est ni une ``Series`` ni un ``DataFrame``.
        InsufficientDataError: si l'objet porte moins de lignes que ``minimum``.
        DataQualityError: si l'index porte des doublons ou décroît.

    Note:
        Un index non croissant est fatal ici. Une fenêtre glissante sur un index
        mal trié lit des observations postérieures à sa propre date, donc
        fabrique exactement la fuite que ce module interdit.
    """
    if not isinstance(data, pd.Series | pd.DataFrame):
        raise TypeError(f"{name} doit être une Series ou un DataFrame pandas, reçu {type(data)!r}")
    if len(data) < minimum:
        raise InsufficientDataError(f"{name} porte {len(data)} observation(s), il en faut au moins {minimum}")
    index = data.index
    if index.has_duplicates:
        raise DataQualityError(f"l'index de {name} porte des horodatages en double")
    if len(index) > 1 and not index.is_monotonic_increasing:
        raise DataQualityError(f"l'index de {name} n'est pas croissant")


def _check_window(window: int, *, minimum: int = 1, name: str = "window") -> int:
    r"""Refuse une longueur qui n'a pas de sens, et rend l'entier validé.

    Args:
        window: la longueur demandée.
        minimum: la longueur minimale acceptée.
        name: le nom de l'argument, pour le message d'erreur.

    Returns:
        La longueur, convertie en entier.

    Raises:
        ConfigError: si la longueur n'est pas un entier au moins égal au minimum.
    """
    if not isinstance(window, int) or isinstance(window, bool):
        raise ConfigError(f"{name} doit être un entier, reçu {type(window)!r}")
    if window < minimum:
        raise ConfigError(f"{name} doit valoir au moins {minimum}, reçu {window}")
    return window


def _check_min_periods(min_periods: int, *, window: int | None = None) -> int:
    r"""Refuse un ``min_periods`` incohérent, et rend l'entier validé.

    Args:
        min_periods: le nombre d'observations valides exigé dans la fenêtre.
        window: la longueur de fenêtre, quand elle est bornée.

    Returns:
        Le ``min_periods`` validé.

    Raises:
        ConfigError: si la valeur n'est pas un entier positif, ou dépasse la
            fenêtre.
    """
    if not isinstance(min_periods, int) or isinstance(min_periods, bool):
        raise ConfigError(f"min_periods doit être un entier, reçu {type(min_periods)!r}")
    if min_periods < 1:
        raise ConfigError(f"min_periods doit valoir au moins 1, reçu {min_periods}")
    if window is not None and min_periods > window:
        raise ConfigError(f"min_periods ({min_periods}) dépasse la fenêtre ({window})")
    return min_periods


def _require_positive_prices(prices: PandasObj, *, name: str) -> None:
    r"""Refuse un prix nul ou négatif, qui rendrait tout rapport de prix faux.

    Args:
        prices: la série ou le tableau de prix.
        name: le nom de l'argument, pour le message d'erreur.

    Raises:
        DataQualityError: si au moins un prix est nul ou négatif.
    """
    non_positive = np.asarray(prices <= 0)
    if bool(non_positive.any()):
        raise DataQualityError(
            f"{name} doit être strictement positif ; "
            f"{int(non_positive.sum())} valeur(s) nulle(s) ou négative(s) trouvée(s)"
        )


def _annualizer(frequency: Frequency, annualize: bool) -> float:
    r"""Rend le facteur multiplicatif d'annualisation d'une volatilité.

    Args:
        frequency: la fréquence d'observation de la série.
        annualize: si faux, le facteur vaut 1 et la sortie reste par période.

    Returns:
        La racine du nombre de périodes par an, ou 1.
    """
    if not annualize:
        return 1.0
    return math.sqrt(annualization_factor(frequency))


def lag[T: (pd.Series, pd.DataFrame)](x: T, periods: int = 1, *, allow_lookahead: bool = False) -> T:
    r"""Décale une série vers le futur, de sorte que ``t`` porte la valeur de ``t - periods``.

    **Le problème.** Une donnée connue à la date :math:`t` sert à décider pour
    la date :math:`t+1`, jamais pour :math:`t`. Le retard est l'outil qui aligne
    l'information sur la décision qu'elle autorise.

    **L'intuition.** On fait glisser la colonne vers le bas. La ligne du jour
    porte alors ce qu'on savait la veille, et les premières lignes deviennent
    manquantes puisque rien ne les précède.

    .. math::

        \mathrm{lag}(x, k)_t = x_{t-k}

    où :math:`k` est le nombre de périodes de retard.

    **Hypothèses.** L'index est croissant et sans doublon, ce qui est vérifié.
    Le pas de l'index est régulier, ce qui n'est PAS vérifié : un retard compte
    des LIGNES, pas des jours. Sur un index à trous, un retard de 1 peut valoir
    une semaine.

    **Provenance.** Convention universelle des séries temporelles. La discipline
    de l'appliquer aux signaux avant le backtest est exposée par López de Prado,
    « Advances in Financial Machine Learning » (2018), chapitre 7.

    **Limites.** Un retard ne corrige pas une donnée publiée en retard. Un
    résultat trimestriel arrêté au 31 mars et publié le 15 mai n'est pas
    connaissable par un retard d'une ligne ; il faut la date de disponibilité,
    et c'est le travail de :mod:`quantlab.data.point_in_time`.

    **Alternatives.** ``pandas.Series.shift`` fait le même calcul, sans garde.
    C'est précisément la garde qui est l'apport ici.

    **Pourquoi cette méthode.** Un ``periods`` négatif regarde devant. Il est
    refusé par défaut, et le passer consciemment demande ``allow_lookahead``,
    donc une décision écrite dans le code appelant.

    **Comment vérifier.** ``lag(x, 1).iloc[1:]`` doit être égal à
    ``x.iloc[:-1]``, valeur par valeur, et la première ligne doit être
    manquante.

    Args:
        x: la série ou le tableau à décaler.
        periods: le nombre de périodes de retard, positif vers le passé.
        allow_lookahead: autorise un ``periods`` négatif, donc une lecture du
            futur. Réservé à la construction d'étiquettes.

    Returns:
        L'objet décalé, de même forme et de même index que l'entrée.

    Raises:
        ConfigError: si ``periods`` n'est pas un entier.
        LookAheadError: si ``periods`` est négatif sans ``allow_lookahead``.

    Example:
        >>> import pandas as pd
        >>> s = pd.Series([1.0, 2.0, 3.0], index=pd.date_range("2020-01-31", periods=3, freq="ME"))
        >>> lag(s, 1).tolist()
        [nan, 1.0, 2.0]
    """
    _validate(x, name="x", minimum=1)
    if not isinstance(periods, int) or isinstance(periods, bool):
        raise ConfigError(f"periods doit être un entier, reçu {type(periods)!r}")
    if periods < 0 and not allow_lookahead:
        raise LookAheadError(
            f"lag(periods={periods}) lirait {abs(periods)} période(s) dans le futur. "
            "Une caractéristique n'a pas le droit de le faire. Pour une étiquette, "
            "utiliser forward_return, ou passer allow_lookahead=True en connaissance de cause."
        )
    return x.shift(periods)


def rolling_mean[T: (pd.Series, pd.DataFrame)](x: T, window: int, *, min_periods: int) -> T:
    r"""Rend la moyenne des ``window`` dernières observations, celle du jour comprise.

    **Le problème.** Lisser une série bruitée sans lire le futur. La moyenne
    mobile CENTRÉE, celle des manuels de statistique descriptive, lit autant à
    droite qu'à gauche. Elle est interdite ici.

    **L'intuition.** On additionne les valeurs de la fenêtre qui se termine
    aujourd'hui, et on divise par leur nombre.

    .. math::

        \mathrm{MA}_t = \frac{1}{w} \sum_{i=0}^{w-1} x_{t-i}

    où :math:`w` est la longueur de fenêtre.

    **Pourquoi ``min_periods`` est obligatoire.** Le défaut de pandas pour
    ``rolling`` vaut ``min_periods = window``, et c'est le bon choix ici : il
    rend manquant tout point dont la fenêtre est incomplète. Une fenêtre
    incomplète produit une moyenne calculée sur moins de données que le reste de
    la série, donc plus bruitée, sans que rien ne le signale. Le paramètre est
    exigé plutôt que défaillant par défaut, pour que le choix soit écrit.

    **Hypothèses.** L'index est croissant, ce qui est vérifié. Le pas est
    régulier, ce qui n'est pas vérifié : la fenêtre compte des lignes.

    **Provenance.** Convention universelle. La discipline du ``min_periods``
    explicite vient de la même source que le reste du module, López de Prado
    (2018), chapitre 7.

    **Limites.** Une moyenne mobile simple donne le même poids à l'observation
    d'aujourd'hui et à celle d'il y a ``window`` périodes, puis un poids nul à
    la suivante. Cette coupure nette est un artefact.

    **Alternatives.** La moyenne exponentielle, dont le poids décroît sans
    coupure, est le choix de :func:`ewma_volatility` pour cette raison.

    **Pourquoi cette méthode.** La fenêtre rectangulaire reste la référence
    quand on veut pouvoir refaire le calcul à la main.

    **Comment vérifier.** Sur une série constante égale à :math:`c`, la moyenne
    mobile vaut :math:`c` partout où elle est définie.

    Args:
        x: la série ou le tableau à lisser.
        window: la longueur de fenêtre, en nombre de lignes.
        min_periods: le nombre d'observations valides exigé dans la fenêtre.

    Returns:
        La moyenne glissante, de même forme et de même index que l'entrée.

    Raises:
        ConfigError: si la fenêtre ou ``min_periods`` est incohérent.

    Example:
        >>> import pandas as pd
        >>> s = pd.Series([1.0, 2.0, 3.0], index=pd.date_range("2020-01-31", periods=3, freq="ME"))
        >>> rolling_mean(s, 2, min_periods=2).tolist()
        [nan, 1.5, 2.5]
    """
    _validate(x, name="x", minimum=1)
    window = _check_window(window)
    min_periods = _check_min_periods(min_periods, window=window)
    return x.rolling(window=window, min_periods=min_periods).mean()


def rolling_std[T: (pd.Series, pd.DataFrame)](x: T, window: int, *, min_periods: int, ddof: int = 1) -> T:
    r"""Rend l'écart type des ``window`` dernières observations, celle du jour comprise.

    **Le problème.** Mesurer la dispersion locale d'une série, et la voir bouger
    dans le temps.

    **L'intuition.** On calcule la moyenne de la fenêtre, puis la distance
    quadratique moyenne à cette moyenne, puis sa racine.

    .. math::

        s_t = \sqrt{\frac{1}{w - \mathrm{ddof}}
              \sum_{i=0}^{w-1} (x_{t-i} - \bar{x}_t)^2}

    où :math:`\bar{x}_t` est la moyenne de la fenêtre qui se termine en
    :math:`t`, et :math:`w` sa longueur.

    **Pourquoi ``min_periods`` est obligatoire.** Même raison que pour
    :func:`rolling_mean`, en plus grave : un écart type sur deux points est un
    nombre, mais il ne mesure rien.

    **Hypothèses.** Les observations de la fenêtre sont tirées d'une même loi.
    C'est faux sur des rendements financiers, dont la volatilité change, et
    c'est justement ce que la fenêtre glissante cherche à suivre.

    **Provenance.** Correction de Bessel, standard. Le choix ``ddof = 1`` est
    celui de :func:`quantlab.analytics.risk.volatility`, et les deux fonctions
    restent comparables.

    **Limites.** La racine d'un estimateur sans biais de la variance n'est pas
    un estimateur sans biais de l'écart type. Le biais est de l'ordre de
    :math:`1/(4w)` en relatif, donc 0,4 % pour une fenêtre de 60.

    **Alternatives.** :func:`ewma_volatility` pour une pondération décroissante,
    :func:`realized_volatility` pour la version à moyenne nulle.

    **Pourquoi cette méthode.** C'est la brique dont :func:`zscore_time_series`
    a besoin, et une seule définition de l'écart type glissant circule.

    **Comment vérifier.** Sur une série constante, l'écart type glissant vaut
    zéro partout où il est défini.

    Args:
        x: la série ou le tableau à mesurer.
        window: la longueur de fenêtre, en nombre de lignes.
        min_periods: le nombre d'observations valides exigé dans la fenêtre.
        ddof: le nombre de degrés de liberté retirés au dénominateur.

    Returns:
        L'écart type glissant, de même forme et de même index que l'entrée.

    Raises:
        ConfigError: si la fenêtre, ``min_periods`` ou ``ddof`` est incohérent.
    """
    _validate(x, name="x", minimum=1)
    window = _check_window(window)
    min_periods = _check_min_periods(min_periods, window=window)
    if not isinstance(ddof, int) or isinstance(ddof, bool) or ddof < 0:
        raise ConfigError(f"ddof doit être un entier positif ou nul, reçu {ddof!r}")
    if ddof >= min_periods:
        raise ConfigError(
            f"ddof ({ddof}) doit rester strictement sous min_periods ({min_periods}), "
            "sinon le dénominateur peut s'annuler ou devenir négatif"
        )
    return x.rolling(window=window, min_periods=min_periods).std(ddof=ddof)


def rolling_sum[T: (pd.Series, pd.DataFrame)](x: T, window: int, *, min_periods: int) -> T:
    r"""Rend la somme des ``window`` dernières observations, celle du jour comprise.

    Sert surtout aux rendements logarithmiques, qui s'additionnent dans le
    temps. La somme de ``window`` rendements logarithmiques est le rendement
    logarithmique de la période entière, ce que la somme de rendements simples
    ne donne pas.

    **Pourquoi ``min_periods`` est obligatoire.** Une somme sur une fenêtre
    incomplète est une somme sur une période plus courte, donc mécaniquement
    plus petite. Rien ne le signale dans la sortie, et le paramètre exigé oblige
    à trancher.

    **Comment vérifier.** Sur une série constante égale à :math:`c` et une
    fenêtre de longueur :math:`w`, la somme glissante vaut :math:`wc`.

    Args:
        x: la série ou le tableau à sommer.
        window: la longueur de fenêtre, en nombre de lignes.
        min_periods: le nombre d'observations valides exigé dans la fenêtre.

    Returns:
        La somme glissante, de même forme et de même index que l'entrée.

    Raises:
        ConfigError: si la fenêtre ou ``min_periods`` est incohérent.
    """
    _validate(x, name="x", minimum=1)
    window = _check_window(window)
    min_periods = _check_min_periods(min_periods, window=window)
    return x.rolling(window=window, min_periods=min_periods).sum()


def rolling_min[T: (pd.Series, pd.DataFrame)](x: T, window: int, *, min_periods: int) -> T:
    r"""Rend le minimum des ``window`` dernières observations, celle du jour comprise.

    **Pourquoi ``min_periods`` est obligatoire.** Un minimum sur une fenêtre
    incomplète est le minimum d'un plus petit échantillon, donc plus haut en
    espérance. La statistique d'ordre est sensible à la taille de la fenêtre
    d'une façon que la moyenne n'a pas.

    **Comment vérifier.** Sur une série strictement croissante, le minimum
    glissant vaut la valeur d'il y a ``window - 1`` périodes.

    Args:
        x: la série ou le tableau à parcourir.
        window: la longueur de fenêtre, en nombre de lignes.
        min_periods: le nombre d'observations valides exigé dans la fenêtre.

    Returns:
        Le minimum glissant, de même forme et de même index que l'entrée.

    Raises:
        ConfigError: si la fenêtre ou ``min_periods`` est incohérent.
    """
    _validate(x, name="x", minimum=1)
    window = _check_window(window)
    min_periods = _check_min_periods(min_periods, window=window)
    return x.rolling(window=window, min_periods=min_periods).min()


def rolling_max[T: (pd.Series, pd.DataFrame)](x: T, window: int, *, min_periods: int) -> T:
    r"""Rend le maximum des ``window`` dernières observations, celle du jour comprise.

    **Pourquoi ``min_periods`` est obligatoire.** Symétrique de
    :func:`rolling_min` : un maximum sur une fenêtre incomplète est plus bas en
    espérance, et c'est ce qui rendrait un repli glissant trop faible au début
    de l'échantillon.

    **Comment vérifier.** Sur une série strictement croissante, le maximum
    glissant vaut la valeur du jour.

    Args:
        x: la série ou le tableau à parcourir.
        window: la longueur de fenêtre, en nombre de lignes.
        min_periods: le nombre d'observations valides exigé dans la fenêtre.

    Returns:
        Le maximum glissant, de même forme et de même index que l'entrée.

    Raises:
        ConfigError: si la fenêtre ou ``min_periods`` est incohérent.
    """
    _validate(x, name="x", minimum=1)
    window = _check_window(window)
    min_periods = _check_min_periods(min_periods, window=window)
    return x.rolling(window=window, min_periods=min_periods).max()


def halflife_to_lambda(halflife: float) -> float:
    r"""Rend le facteur d'oubli d'une moyenne exponentielle depuis sa demi-vie.

    La demi-vie est le nombre de périodes au bout duquel le poids d'une
    observation est divisé par deux. Le facteur d'oubli, souvent noté
    :math:`\lambda`, est le rapport entre deux poids consécutifs.

    .. math::

        \lambda = 0{,}5^{1/h}

    où :math:`h` est la demi-vie, en nombre de périodes.

    Args:
        halflife: la demi-vie, strictement positive.

    Returns:
        Le facteur d'oubli, strictement compris entre 0 et 1.

    Raises:
        ConfigError: si la demi-vie n'est pas strictement positive.

    Example:
        >>> round(halflife_to_lambda(60), 6)
        0.988514
    """
    if halflife <= 0:
        raise ConfigError(f"halflife doit être strictement positive, reçu {halflife}")
    return float(0.5 ** (1.0 / halflife))


def lambda_to_halflife(decay: float) -> float:
    r"""Rend la demi-vie d'une moyenne exponentielle depuis son facteur d'oubli.

    C'est la réciproque de :func:`halflife_to_lambda`.

    .. math::

        h = \frac{\ln 0{,}5}{\ln \lambda}

    Args:
        decay: le facteur d'oubli, strictement compris entre 0 et 1.

    Returns:
        La demi-vie, en nombre de périodes.

    Raises:
        ConfigError: si le facteur d'oubli sort de l'intervalle ouvert.

    Example:
        >>> round(lambda_to_halflife(0.94), 4)
        11.2023
    """
    if not 0.0 < decay < 1.0:
        raise ConfigError(f"decay doit être strictement compris entre 0 et 1, reçu {decay}")
    return float(math.log(0.5) / math.log(decay))


def equivalent_window(halflife: float) -> float:
    r"""Rend la fenêtre rectangulaire de même centre de masse qu'une demi-vie donnée.

    **Le problème.** Une demi-vie ne se compare pas à une longueur de fenêtre,
    et les deux se côtoient dans toute étude qui mélange moyennes mobiles et
    moyennes exponentielles. Il faut une passerelle.

    **L'intuition.** Le centre de masse d'une pondération est l'âge moyen des
    observations qu'elle utilise. Deux pondérations de même centre de masse
    regardent aussi loin en arrière, en moyenne.

    .. math::

        \mathrm{com} = \frac{\lambda}{1 - \lambda},
        \qquad
        w_{eq} = 2\,\mathrm{com} + 1

    où :math:`\lambda` est le facteur d'oubli et :math:`w_{eq}` la longueur de
    la fenêtre rectangulaire équivalente.

    **D'où vient le facteur deux.** Le centre de masse d'une fenêtre
    rectangulaire de longueur :math:`w` vaut :math:`(w-1)/2`. Égaler les deux
    centres de masse donne la relation ci-dessus.

    **Exemple chiffré, modélisé.** Une demi-vie de 60 périodes donne
    :math:`\lambda = 0{,}988514`, un centre de masse de 86,06 périodes, et une
    fenêtre équivalente de 173,13 périodes. La fenêtre équivalente vaut donc
    presque trois fois la demi-vie, ce qui surprend la première fois.

    **Limites.** L'égalité des centres de masse ne rend pas les deux
    pondérations interchangeables. La moyenne exponentielle garde un poids non
    nul sur toute l'histoire, la rectangulaire coupe net.

    Args:
        halflife: la demi-vie, strictement positive.

    Returns:
        La longueur de la fenêtre rectangulaire de même centre de masse.

    Raises:
        ConfigError: si la demi-vie n'est pas strictement positive.
    """
    decay = halflife_to_lambda(halflife)
    center_of_mass = decay / (1.0 - decay)
    return float(2.0 * center_of_mass + 1.0)


def ewma_volatility[T: (pd.Series, pd.DataFrame)](
    returns: T,
    halflife: float,
    *,
    min_periods: int,
    annualize: bool = True,
    frequency: Frequency = Frequency.DAILY,
) -> T:
    r"""Rend la volatilité par moyenne mobile exponentielle des carrés de rendements.

    **Le problème.** La volatilité change dans le temps, et une fenêtre
    rectangulaire la fait sauter. Le jour où un choc sort de la fenêtre, la
    volatilité estimée chute d'un coup, sans qu'il se soit rien passé ce
    jour-là. C'est l'effet fantôme.

    **L'intuition.** On garde toute l'histoire, mais on donne à chaque
    observation un poids qui décroît géométriquement avec son âge. Rien ne sort
    jamais de la fenêtre, donc rien ne saute.

    .. math::

        \hat{\sigma}^2_t = \frac{\sum_{i=0}^{t} \lambda^i r_{t-i}^2}
                                   {\sum_{i=0}^{t} \lambda^i},
        \qquad
        \lambda = 0{,}5^{1/h}

    Définition des variables. :math:`r_{t-i}` est le rendement observé
    :math:`i` périodes avant :math:`t`. :math:`\lambda` est le facteur
    d'oubli, :math:`h` la demi-vie en périodes, et :math:`i` l'âge de
    l'observation.

    **La correspondance entre demi-vie, facteur d'oubli et fenêtre.** Les trois
    façons de dire la même chose sont reliées par des identités. Le facteur
    d'oubli vaut :math:`\lambda = 0{,}5^{1/h}`. Le poids cumulé des :math:`h`
    dernières périodes vaut :math:`1 - \lambda^{h}`, donc exactement la moitié
    du poids total. La fenêtre rectangulaire de même centre de masse vaut
    :math:`(1+\lambda)/(1-\lambda)`.

    **L'exemple chiffré, modélisé.** Une demi-vie de 60 jours donne
    :math:`\lambda = 0{,}5^{1/60} = 0{,}988514`. Le poids cumulé des 60
    derniers jours vaut :math:`1 - 0{,}988514^{60} = 0{,}5`, soit 50 %. La
    fenêtre rectangulaire équivalente vaut 173,13 jours, ce que rend
    :func:`equivalent_window`.

    **Hypothèses.** La moyenne des rendements est supposée NULLE, ce qui est la
    convention RiskMetrics. Sur du quotidien, l'espérance vaut quelques points
    de base et son carré est négligeable devant la variance. Sur du mensuel ou
    de l'annuel, cette hypothèse devient fausse et il faut préférer
    :func:`rolling_std`, qui retire la moyenne.

    **Pourquoi ``min_periods``.** Les premières estimations reposent sur
    quelques carrés seulement. Le paramètre exige de dire combien
    d'observations suffisent, plutôt que de publier une volatilité fondée sur
    trois points.

    **Provenance.** J.P. Morgan et Reuters, « RiskMetrics Technical Document »
    (1996), 4e édition, qui retient :math:`\lambda = 0{,}94` en quotidien et
    :math:`\lambda = 0{,}97` en mensuel. La valeur 0,94 correspond à une
    demi-vie de 11,20 jours, ce que rend :func:`lambda_to_halflife`.

    **Limites.** Le modèle n'a aucun retour à la moyenne : après un choc, la
    volatilité estimée décroît vers zéro et non vers une moyenne de long terme.
    C'est le cas limite d'un GARCH(1,1) dont les paramètres somment à un, donc
    un modèle intégré.

    **Alternatives.** Un GARCH(1,1) estimé par maximum de vraisemblance ajoute
    le retour à la moyenne, au prix d'une estimation. Le paquet ``arch`` le
    fournit, et :mod:`quantlab.analytics.risk` documente le sujet.

    **Pourquoi cette méthode ici.** Une caractéristique doit être bon marché et
    stable. La moyenne exponentielle n'a aucun paramètre estimé, donc aucune
    fuite possible par estimation sur l'échantillon entier.

    **Comment vérifier.** Sur une série de rendements constants égaux à
    :math:`c`, la volatilité non annualisée vaut :math:`|c|` partout où elle est
    définie, quelle que soit la demi-vie. Le test vérifie aussi que
    :math:`\lambda^{h}` vaut exactement 0,5.

    Args:
        returns: les rendements, simples ou logarithmiques, indexés par le temps.
        halflife: la demi-vie de la pondération, en nombre de périodes.
        min_periods: le nombre d'observations valides exigé avant de rendre une
            estimation.
        annualize: multiplie par la racine du nombre de périodes par an.
        frequency: la fréquence d'observation, qui fixe ce nombre.

    Returns:
        La volatilité glissante, de même forme et de même index que l'entrée.

    Raises:
        ConfigError: si la demi-vie ou ``min_periods`` est incohérent.
    """
    _validate(returns, name="returns", minimum=1)
    if halflife <= 0:
        raise ConfigError(f"halflife doit être strictement positive, reçu {halflife}")
    min_periods = _check_min_periods(min_periods)
    variance = returns.pow(2).ewm(halflife=halflife, min_periods=min_periods, adjust=True).mean()
    return variance.pow(0.5) * _annualizer(frequency, annualize)


def realized_volatility[T: (pd.Series, pd.DataFrame)](
    returns: T,
    window: int,
    *,
    min_periods: int | None = None,
    frequency: Frequency = Frequency.DAILY,
    annualize: bool = True,
) -> T:
    r"""Rend la volatilité réalisée sur une fenêtre glissante, à moyenne supposée nulle.

    **Le problème.** Estimer la volatilité d'une période sans supposer de
    modèle, en n'utilisant que les carrés des rendements observés.

    **L'intuition.** La variance d'une variable centrée est l'espérance de son
    carré. On remplace l'espérance par la moyenne des carrés sur la fenêtre, et
    on prend la racine.

    .. math::

        RV_t = \frac{1}{m_t} \sum_{i=0}^{w-1} r_{t-i}^2,
        \qquad
        \hat{\sigma}_t = \sqrt{RV_t}\,\sqrt{N}

    Définition des variables. :math:`w` est la longueur de fenêtre,
    :math:`m_t` le nombre d'observations valides qu'elle contient, et :math:`N`
    le nombre de périodes par an.

    **Ce qui la sépare de** :func:`rolling_std`. Deux choses, et elles se
    compensent en partie. La volatilité réalisée ne retire pas la moyenne, donc
    surestime quand la dérive est forte. Elle divise par :math:`m_t` et non par
    :math:`m_t - 1`, donc sous-estime légèrement.

    **L'écart entre les deux, chiffré.** Le seul effet du dénominateur vaut
    :math:`\sqrt{w/(w-1)} - 1`, soit 11,8 % pour une fenêtre de 5, 2,60 % pour
    20 et 0,84 % pour 60. Ce sont des identités. Le retrait de la moyenne joue en
    sens inverse et sans borne : sur 300 rendements quotidiens simulés de moyenne
    nulle et d'écart type 1 %, l'écart relatif médian est de 9,4 % à
    :math:`w = 5`, 2,1 % à 20 et 0,69 % à 60, avec un maximum de 816 % à
    :math:`w = 5`. Ces six chiffres sont MODÉLISÉS sous ces hypothèses. La règle
    à retenir : les deux fonctions ne sont interchangeables sur aucune fenêtre
    courte.

    **Hypothèses.** L'espérance des rendements est nulle sur la fenêtre. Les
    rendements sont non corrélés, sans quoi la somme des carrés n'estime plus la
    variance de la période.

    **Provenance.** Andersen, Bollerslev, Diebold et Labys, « The Distribution
    of Realized Exchange Rate Volatility », Journal of the American Statistical
    Association (2001). Ils travaillent sur des rendements intrajournaliers ;
    l'usage sur des rendements quotidiens est une adaptation courante.

    **Limites.** La mesure est d'autant plus précise que la fréquence est fine,
    et la version quotidienne reste bruitée. Un saut de prix isolé domine la
    fenêtre entière.

    **Ce qu'elle n'est pas, et le piège qui va avec.** La valeur datée :math:`t`
    décrit la fenêtre qui se TERMINE en :math:`t`. Elle est donc causale, mais
    elle n'est pas une prévision de la période suivante. La confondre avec une
    volatilité prévue est une erreur de dimensionnement de position, pas une
    fuite : le chiffre reste connu à :math:`t`.

    **Alternatives.** :func:`ewma_volatility` pour une pondération sans
    coupure, l'estimateur de Parkinson quand on dispose du haut et du bas de
    séance.

    **Pourquoi cette méthode ici.** Elle ne demande aucune estimation, donc
    aucune fuite possible, et elle se recalcule à la main sur trois lignes.

    **Comment vérifier.** Sur des rendements de moyenne exactement nulle,
    :math:`\sqrt{RV}` égale l'écart type d'échantillon avec ``ddof = 0``.

    Args:
        returns: les rendements, indexés par le temps.
        window: la longueur de fenêtre, en nombre de lignes.
        min_periods: le nombre d'observations valides exigé. Vaut ``window``
            quand rien n'est passé, ce qui est le choix recommandé.
        frequency: la fréquence d'observation de la série.
        annualize: multiplie par la racine du nombre de périodes par an.

    Returns:
        La volatilité glissante, de même forme et de même index que l'entrée.

    Raises:
        ConfigError: si la fenêtre ou ``min_periods`` est incohérent.
    """
    _validate(returns, name="returns", minimum=1)
    window = _check_window(window)
    effective = window if min_periods is None else min_periods
    effective = _check_min_periods(effective, window=window)
    mean_square = returns.pow(2).rolling(window=window, min_periods=effective).mean()
    return mean_square.pow(0.5) * _annualizer(frequency, annualize)


def momentum[T: (pd.Series, pd.DataFrame)](
    prices: T,
    lookback: int,
    skip: int = 0,
    *,
    kind: ReturnKind = ReturnKind.SIMPLE,
) -> T:
    r"""Rend le rendement sur la fenêtre, en sautant les ``skip`` dernières périodes.

    **Le problème.** Mesurer la tendance passée d'un actif sans que la mesure
    soit polluée par un effet qui va dans l'autre sens.

    **L'intuition.** On compare le prix d'il y a ``skip`` périodes à celui d'il
    y a ``lookback`` périodes. La fenêtre commence donc loin et s'arrête AVANT
    aujourd'hui, ce qui laisse un trou volontaire.

    .. math::

        M_t = \frac{P_{t-s}}{P_{t-\ell}} - 1
        \qquad\text{ou}\qquad
        M^{\log}_t = \ln\!\left(\frac{P_{t-s}}{P_{t-\ell}}\right)

    Définition des variables. :math:`P_t` est le prix ajusté en fin de période
    :math:`t`, :math:`\ell` la longueur de fenêtre, et :math:`s` le nombre de
    périodes sautées, avec :math:`s < \ell`.

    **Pourquoi le saut existe.** Le mois le plus récent porte un RENVERSEMENT à
    court terme, et non une continuation. Un actif qui vient de monter fort sur
    un mois a tendance à redescendre le mois suivant, effet documenté par
    Narasimhan Jegadeesh (1990) et Bruce Lehmann (1990). Ce renversement contamine
    le signal de momentum et l'affaiblit. Le sauter isole la continuation de
    moyen terme, celle qui porte la prime.

    **La convention 12 moins 1.** En mensuel, ``lookback = 12`` et ``skip = 1``
    donnent le rendement des onze mois qui s'arrêtent il y a un mois. C'est
    exactement le signal de Jegadeesh et Titman.

    **Hypothèses.** Les prix sont ajustés des divisions et des dividendes, ce
    qui n'est pas vérifiable ici. Un prix non ajusté fabrique un faux momentum
    de moins 50 % le jour d'une division par deux. Les prix sont strictement
    positifs, ce qui est vérifié.

    **Provenance.** Jegadeesh et Titman, « Returns to Buying Winners and
    Selling Losers », Journal of Finance (1993). Le saut d'un mois est repris
    par Fama et French (2012) et par la construction du facteur ``UMD`` de la
    bibliothèque de Kenneth French.

    **Limites.** Le momentum s'effondre après un renversement de marché. Daniel
    et Moskowitz, « Momentum Crashes », Journal of Financial Economics (2016),
    documentent 1932 et 2009. Leur article étant antérieur, il ne dit rien de
    2020, et le comportement du signal cette année-là est ici NON VÉRIFIÉ.

    **Alternatives.** Le momentum de série temporelle, qui compare l'actif à
    lui-même plutôt qu'aux autres, vit dans
    :func:`time_series_momentum_signal`. Le momentum résiduel, calculé sur le
    résidu d'une régression factorielle, demande
    :mod:`quantlab.analytics.regression`.

    **Pourquoi cette méthode ici.** Le rapport de deux prix décalés est la forme
    la plus simple qui rende le saut EXPLICITE dans la signature, donc
    impossible à oublier.

    **Comment vérifier.** Sur des prix qui montent de 10 % par période, avec
    ``lookback = 3`` et ``skip = 1``, le momentum vaut :math:`1{,}1^2 - 1`, soit
    exactement 0,21.

    Args:
        prices: les prix ajustés, indexés par le temps.
        lookback: la longueur de fenêtre, en nombre de lignes.
        skip: le nombre de périodes récentes sautées.
        kind: convention de rendement, simple ou logarithmique.

    Returns:
        Le momentum, de même forme et de même index que l'entrée.

    Raises:
        ConfigError: si ``lookback`` ou ``skip`` est incohérent.
        DataQualityError: si un prix est nul ou négatif.

    Example:
        >>> import pandas as pd
        >>> dates = pd.date_range("2020-01-31", periods=4, freq="ME")
        >>> p = pd.Series([100.0, 110.0, 121.0, 133.1], index=dates)
        >>> float(round(momentum(p, 3, skip=1).iloc[-1], 10))
        0.21
    """
    _validate(prices, name="prices", minimum=1)
    lookback = _check_window(lookback, name="lookback")
    if not isinstance(skip, int) or isinstance(skip, bool) or skip < 0:
        raise ConfigError(f"skip doit être un entier positif ou nul, reçu {skip!r}")
    if skip >= lookback:
        raise ConfigError(
            f"skip ({skip}) doit rester strictement sous lookback ({lookback}), "
            "sinon la fenêtre de mesure est vide ou renversée"
        )
    _require_positive_prices(prices, name="prices")
    ratio = prices.shift(skip) / prices.shift(lookback)
    if kind is ReturnKind.LOG:
        return np.log(ratio)
    return ratio - 1.0


def time_series_momentum_signal[T: (pd.Series, pd.DataFrame)](
    returns: T,
    lookback: int,
    *,
    zero_tolerance: float = 0.0,
) -> T:
    r"""Rend le signe du rendement cumulé sur la fenêtre, dans l'ensemble des trois valeurs.

    **Le problème.** Décider d'être long, court ou absent d'un actif, sans le
    comparer aux autres. C'est la question du suivi de tendance, et elle se
    pose actif par actif.

    **L'intuition.** On cumule les rendements des ``lookback`` dernières
    périodes, celle du jour comprise, et on ne garde que le signe. Positif, on
    est long ; négatif, on est court.

    .. math::

        S_t = \operatorname{sgn}\!\left(
              \sum_{i=0}^{w-1} \ln(1 + r_{t-i}) \right)

    Définition des variables. :math:`r_{t-i}` est le rendement simple observé
    :math:`i` périodes avant :math:`t`, et :math:`w` la longueur de fenêtre.

    **Pourquoi passer par le logarithme.** Le rendement cumulé est un produit de
    facteurs. Son signe est celui de la somme des logarithmes, dès lors que tous
    les facteurs sont positifs. La somme évite le produit cumulé, qui perd de la
    précision sur les longues séries.

    **Le traitement du zéro, déclaré.** Un rendement cumulé exactement nul rend
    le signal 0, donc une position PLATE. C'est un choix, et l'alternative
    consistant à rester long par défaut biaiserait le signal vers la hausse. Le
    paramètre ``zero_tolerance`` élargit cette zone plate : toute somme de
    logarithmes dont la valeur absolue ne dépasse pas le seuil rend 0. Le défaut
    vaut zéro, donc seul le zéro exact est plat.

    **Hypothèses.** Les rendements sont simples et strictement supérieurs à
    moins un, ce qui est vérifié. Un rendement de moins un est une perte totale,
    et le logarithme n'y est pas défini.

    **Provenance.** Moskowitz, Ooi et Pedersen, « Time Series Momentum »,
    Journal of Financial Economics (2012). Ils retiennent une fenêtre de douze
    mois et documentent le signal sur 58 instruments à terme.

    **Limites.** Le signe jette l'amplitude. Deux actifs dont l'un a monté de
    2 % et l'autre de 60 % reçoivent le même signal, ce qui est délibéré mais
    coûteux quand les volatilités diffèrent. Une mise à l'échelle par la
    volatilité, comme dans l'article, corrige ce défaut en aval.

    **Alternatives.** Le momentum transversal de :func:`momentum`, qui classe
    les actifs entre eux. Le croisement de deux moyennes mobiles, qui rend un
    signal proche mais réagit plus lentement.

    **Pourquoi cette méthode ici.** Un signal à trois valeurs se rééquilibre
    peu, donc coûte peu en rotation, et sa lecture ne demande aucune
    normalisation.

    **Comment vérifier.** Sur les rendements 0,25 puis moins 0,20, le produit
    vaut exactement 1, donc le rendement cumulé est nul et le signal vaut 0.

    Args:
        returns: les rendements simples, indexés par le temps.
        lookback: la longueur de fenêtre, en nombre de lignes.
        zero_tolerance: la demi-largeur de la zone plate, en rendement
            logarithmique cumulé.

    Returns:
        Le signal, à valeurs dans moins un, zéro et plus un, manquant tant que
        la fenêtre est incomplète.

    Raises:
        ConfigError: si la fenêtre ou la tolérance est incohérente.
        DataQualityError: si un rendement vaut moins un ou moins.
    """
    _validate(returns, name="returns", minimum=1)
    lookback = _check_window(lookback, name="lookback")
    if zero_tolerance < 0:
        raise ConfigError(f"zero_tolerance doit être positive ou nulle, reçu {zero_tolerance}")
    too_low = np.asarray(returns <= -1.0)
    if bool(too_low.any()):
        raise DataQualityError(
            f"returns porte {int(too_low.sum())} valeur(s) inférieure(s) ou égale(s) à -1. "
            "Un rendement simple de -1 est une perte totale, et son logarithme n'existe pas."
        )
    cumulative = np.log1p(returns).rolling(window=lookback, min_periods=lookback).sum()
    signal = np.sign(cumulative)
    return signal.where(cumulative.abs() > zero_tolerance, other=cumulative * 0.0)


def zscore_time_series[T: (pd.Series, pd.DataFrame)](
    x: T,
    window: int,
    *,
    min_periods: int,
    ddof: int = 1,
) -> T:
    r"""Rend le z-score d'une série contre son PROPRE passé, fenêtre glissante.

    **Le problème.** Une grandeur brute ne se compare pas dans le temps. Un
    écart de rendement de 2 % est énorme en 2017 et ordinaire en mars 2020. Il
    faut le rapporter à la dispersion du moment.

    **L'intuition.** On retire à la valeur du jour la moyenne de sa fenêtre,
    puis on divise par l'écart type de cette même fenêtre. Le résultat se lit en
    nombre d'écarts types.

    .. math::

        z_t = \frac{x_t - \bar{x}_t}{s_t}

    Définition des variables. :math:`\bar{x}_t` et :math:`s_t` sont la moyenne
    et l'écart type de la fenêtre qui se termine en :math:`t`, celle-ci
    comprise.

    **À ne pas confondre avec le z-score transversal.** Celui-ci compare une
    série à son passé, à une date donnée et pour un seul actif. Le z-score
    transversal, qui vit dans :mod:`quantlab.signals`, compare les actifs entre
    eux à une date donnée. Les deux portent le même nom et répondent à deux
    questions différentes.

    **Hypothèses.** La fenêtre est assez longue pour que la moyenne et l'écart
    type veuillent dire quelque chose. Les observations de la fenêtre sont
    tirées d'une même loi, ce qui est faux dès qu'un régime change.

    **Provenance.** Standardisation classique. Son emploi glissant sur des
    signaux financiers est courant, et Grinold et Kahn (2000) le discutent au
    chapitre sur la construction des prévisions.

    **Limites.** Un écart type nul rend le z-score indéfini, et la fonction rend
    alors un manquant plutôt qu'un infini. Sur une fenêtre courte, le z-score
    est borné en valeur absolue par :math:`(w-1)/\sqrt{w}`, ce qui écrase les
    valeurs extrêmes.

    **Alternatives.** Le rang glissant de :func:`percent_rank`, insensible aux
    valeurs aberrantes. La winsorisation avant standardisation, qui vit dans
    :mod:`quantlab.signals`.

    **Pourquoi cette méthode ici.** Elle réutilise :func:`rolling_mean` et
    :func:`rolling_std`, donc une seule définition de la moyenne et de l'écart
    type glissants circule dans le dépôt.

    **Comment vérifier.** Sur la fenêtre 1, 2, 3, la moyenne vaut 2 et l'écart
    type d'échantillon vaut 1, donc le z-score du dernier point vaut exactement
    1.

    Args:
        x: la série ou le tableau à standardiser.
        window: la longueur de fenêtre, en nombre de lignes.
        min_periods: le nombre d'observations valides exigé dans la fenêtre.
        ddof: le nombre de degrés de liberté retirés à l'écart type.

    Returns:
        Le z-score glissant, de même forme et de même index que l'entrée.

    Raises:
        ConfigError: si la fenêtre, ``min_periods`` ou ``ddof`` est incohérent.
    """
    center = rolling_mean(x, window, min_periods=min_periods)
    dispersion = rolling_std(x, window, min_periods=min_periods, ddof=ddof)
    return (x - center) / dispersion.where(dispersion > 0.0)


def _rank_of_last(values: np.ndarray) -> float:
    r"""Rend le rang relatif de la dernière valeur d'une fenêtre, ex aequo partagés.

    Args:
        values: les valeurs de la fenêtre, la dernière étant celle du jour.

    Returns:
        Le rang relatif, entre 0 et 1 inclus.
    """
    current = values[-1]
    others = values[:-1]
    below = float(np.count_nonzero(others < current))
    ties = float(np.count_nonzero(others == current))
    return (below + 0.5 * ties) / float(others.size)


def percent_rank[T: (pd.Series, pd.DataFrame)](x: T, window: int) -> T:
    r"""Rend le rang relatif de la valeur du jour dans sa fenêtre, entre 0 et 1.

    **Le problème.** Le z-score suppose une dispersion mesurable et se laisse
    tirer par une valeur aberrante. Sur une série à queues épaisses, un seul
    point extrême écrase tous les autres.

    **L'intuition.** On oublie les valeurs et on ne garde que l'ordre. Le rang
    relatif dit quelle proportion de la fenêtre se situe sous la valeur du jour.

    .. math::

        PR_t = \frac{\#\{i \ge 1 : x_{t-i} < x_t\}
                      + \tfrac{1}{2}\#\{i \ge 1 : x_{t-i} = x_t\}}{w - 1}

    Définition des variables. La fenêtre porte :math:`w` observations, celle du
    jour comprise, donc :math:`w-1` points de comparaison, et :math:`i`
    parcourt ces points.

    **La convention des ex aequo, déclarée.** Un ex aequo compte pour une
    demi-unité. Cette convention du rang médian donne 0,5 sur une fenêtre
    constante, là où compter les ex aequo comme inférieurs donnerait 1 et les
    ignorer donnerait 0. Ni l'une ni l'autre de ces deux réponses n'est neutre.

    **Bornes.** Le minimum strict de la fenêtre rend 0, le maximum strict rend
    1, et la médiane rend environ 0,5. La sortie est donc directement lisible
    comme un quantile empirique.

    **Hypothèses.** La fenêtre est complète : tout point dont la fenêtre porte
    un manquant rend un manquant. La longueur de fenêtre vaut au moins deux,
    sans quoi le dénominateur s'annule.

    **Provenance.** Statistique de rang classique. La forme retenue est celle du
    rang moyen de ``scipy.stats.rankdata``, avec l'option ``average``, ramené à
    l'intervalle unité par :math:`(r-1)/(w-1)` où :math:`r` est le rang de la
    valeur du jour dans sa fenêtre.

    **Ce n'est PAS ``percentileofscore``, et l'écart est mesuré.** La fonction
    ``scipy.stats.percentileofscore`` avec l'option ``mean`` divise par
    :math:`w` et compte la valeur du jour parmi ses propres ex aequo. Sur la
    fenêtre 1, 2, 3, 4 elle rend 0,875 quand cette fonction rend 1,0, chiffres
    mesurés. Les deux coïncident sur une fenêtre constante, à 0,5, ce qui rend
    la confusion facile.

    **Limites.** Le rang jette l'amplitude. Une hausse de 1 % et une hausse de
    30 % reçoivent le même rang si elles occupent la même place dans la fenêtre.
    Le rang est aussi coûteux à calculer, puisqu'il compare chaque fenêtre point
    par point.

    **Alternatives.** :func:`zscore_time_series` quand l'amplitude compte. Le
    quantile glissant quand on veut un seuil plutôt qu'une position.

    **Pourquoi cette méthode ici.** Elle est bornée par construction, donc elle
    ne fabrique jamais de valeur extrême qui dominerait une optimisation en
    aval.

    **Comment vérifier.** Sur la fenêtre 1, 3, 2 la valeur du jour est 2, un
    seul point est sous elle, et le rang vaut 1 divisé par 2, soit 0,5.

    Args:
        x: la série ou le tableau à classer.
        window: la longueur de fenêtre, au moins deux lignes.

    Returns:
        Le rang relatif glissant, de même forme et de même index que l'entrée.

    Raises:
        ConfigError: si la fenêtre est plus courte que deux lignes.
    """
    _validate(x, name="x", minimum=1)
    window = _check_window(window, minimum=MIN_RANK_WINDOW)
    return x.rolling(window=window, min_periods=window).apply(_rank_of_last, raw=True)


def drawdown_feature[T: (pd.Series, pd.DataFrame)](prices: T, window: int) -> T:
    r"""Rend la perte relative depuis le plus haut de la fenêtre, valeur négative ou nulle.

    **Le problème.** Savoir si un actif est proche de son sommet récent ou loin
    en dessous. C'est une information de régime, et elle ne se lit ni dans le
    rendement ni dans la volatilité.

    **L'intuition.** On repère le plus haut prix atteint sur la fenêtre qui se
    termine aujourd'hui, puis on mesure de combien le prix du jour est en
    dessous, en proportion.

    .. math::

        D_t = \frac{P_t}{\max_{0 \le i < w} P_{t-i}} - 1

    Définition des variables. :math:`P_t` est le prix ajusté du jour, et
    :math:`w` la longueur de fenêtre.

    **Ce qui la sépare du repli depuis le sommet.** La fonction
    :func:`quantlab.analytics.drawdown.drawdown_series` mesure le repli depuis
    le sommet de TOUTE l'histoire, ce qui est la bonne mesure pour juger un
    portefeuille a posteriori. Celle-ci borne la mémoire à ``window``
    observations, ce qui la rend stationnaire et donc utilisable comme
    caractéristique.

    **Hypothèses.** Les prix sont ajustés et strictement positifs, ce qui est
    vérifié. La fenêtre compte des lignes et non des jours de calendrier.

    **Provenance.** Mesure standard du suivi de tendance. Grossman et Zhou,
    « Optimal Investment Strategies for Controlling Drawdowns », Mathematical
    Finance (1993), en font une variable d'état de la décision d'allocation.

    **Limites.** La valeur est bornée entre moins un et zéro, et elle passe
    beaucoup de temps collée à zéro sur un marché haussier. Sa distribution est
    donc très asymétrique, ce qui gêne une régression linéaire.

    **Alternatives.** La distance au plus haut en nombre d'écarts types, plus
    symétrique. Le nombre de périodes depuis le dernier sommet, qui mesure la
    durée plutôt que l'ampleur.

    **Pourquoi cette méthode ici.** Elle se compose de :func:`rolling_max`,
    donc elle hérite de son contrôle de causalité sans le réécrire.

    **Comment vérifier.** Sur les prix 100, 120 et 90 avec une fenêtre de trois,
    le plus haut vaut 120. Le repli du dernier point vaut donc 90 divisé par 120
    moins un, soit exactement moins 0,25.

    Args:
        prices: les prix ajustés, indexés par le temps.
        window: la longueur de fenêtre, en nombre de lignes.

    Returns:
        Le repli glissant, de même forme et de même index que l'entrée.

    Raises:
        ConfigError: si la fenêtre est incohérente.
        DataQualityError: si un prix est nul ou négatif.
    """
    _validate(prices, name="prices", minimum=1)
    window = _check_window(window)
    _require_positive_prices(prices, name="prices")
    peak = rolling_max(prices, window, min_periods=window)
    return prices / peak - 1.0


def forward_return[T: (pd.Series, pd.DataFrame)](
    prices: T,
    horizon: int = 1,
    *,
    kind: ReturnKind = ReturnKind.SIMPLE,
) -> T:
    r"""Rend le rendement FUTUR sur ``horizon`` périodes, qui est une ÉTIQUETTE.

    **AVERTISSEMENT, à lire avant tout usage.** Cette sortie contient de
    l'information postérieure à sa propre date. Elle ne doit JAMAIS entrer dans
    un modèle comme intrant, ni dans une matrice de caractéristiques, ni dans un
    signal, ni dans un filtre. Son seul emploi légitime est la cible qu'un
    modèle apprend à prévoir. Le nom de la sortie porte le préfixe ``label_``
    pour que la confusion se voie à l'écran.

    **Le problème.** Un modèle supervisé a besoin d'une cible. Cette cible est
    par nature future, sans quoi il n'y aurait rien à prévoir.

    **L'intuition.** On divise le prix dans ``horizon`` périodes par celui
    d'aujourd'hui. Les dernières lignes deviennent manquantes, puisque leur
    futur n'est pas encore observé.

    .. math::

        y_t = \frac{P_{t+h}}{P_t} - 1

    Définition des variables. :math:`h` est l'horizon de prévision, en nombre de
    lignes, et :math:`P_t` le prix ajusté du jour.

    **Le recouvrement des étiquettes.** Avec :math:`h > 1`, deux étiquettes
    consécutives partagent :math:`h-1` périodes. Elles sont donc corrélées, et
    toute validation croisée naïve surestime la performance. La réponse du
    laboratoire est la purge et l'embargo, qui vivent dans
    :mod:`quantlab.validation.purging`.

    **Hypothèses.** Les prix sont ajustés et strictement positifs, ce qui est
    vérifié. L'horizon compte des lignes, donc l'index doit être régulier pour
    que l'horizon soit une durée.

    **Provenance.** López de Prado, « Advances in Financial Machine Learning »
    (2018), chapitre 3, qui construit les étiquettes et montre au chapitre 7
    pourquoi leur recouvrement casse la validation croisée.

    **Limites.** Une étiquette à horizon fixe ignore le chemin. Un actif qui
    perd 40 % avant de revenir à son point de départ reçoit une étiquette nulle.
    La méthode des trois barrières corrige ce défaut, au prix de deux seuils à
    choisir.

    **Alternatives.** L'étiquette binaire du signe, plus robuste au bruit. La
    méthode des trois barrières, qui rend l'étiquette et sa date de réalisation.

    **Pourquoi cette méthode ici.** C'est la cible la plus simple, et sa
    simplicité rend visible le seul risque qu'elle porte, celui d'être prise
    pour une caractéristique.

    **Comment vérifier.** :func:`assert_causal` doit ÉCHOUER sur cette fonction,
    et le test le vérifie. Une étiquette qui passerait le contrôle de causalité
    ne serait pas une étiquette.

    Args:
        prices: les prix ajustés, indexés par le temps.
        horizon: le nombre de périodes de prévision, strictement positif.
        kind: convention de rendement, simple ou logarithmique.

    Returns:
        L'étiquette, de même forme et de même index que l'entrée, dont le nom
        porte le préfixe ``label_``.

    Raises:
        ConfigError: si l'horizon n'est pas un entier strictement positif.
        DataQualityError: si un prix est nul ou négatif.
    """
    _validate(prices, name="prices", minimum=1)
    horizon = _check_window(horizon, name="horizon")
    _require_positive_prices(prices, name="prices")
    ratio = prices.shift(-horizon) / prices
    out = np.log(ratio) if kind is ReturnKind.LOG else ratio - 1.0
    stem = f"{LABEL_PREFIX}forward_return_{horizon}"
    if isinstance(out, pd.Series):
        suffix = "" if prices.name is None else f"_{prices.name}"
        return out.rename(f"{stem}{suffix}")
    return out.rename(columns=lambda column: f"{stem}_{column}")


def _compare_before_cut(
    reference: PandasObj,
    candidate: PandasObj,
    label: object,
    *,
    tolerance: float,
    name: str,
    cause: str,
) -> PandasObj:
    r"""Compare deux sorties jusqu'à la coupure incluse, et rend la partie de référence.

    Args:
        reference: la caractéristique calculée sur les données d'origine.
        candidate: la caractéristique calculée sur les données modifiées.
        label: l'étiquette d'index de la coupure, incluse dans la comparaison.
        tolerance: l'écart absolu maximal toléré.
        name: le nom employé dans le message d'erreur.
        cause: la modification appliquée au futur, dite en français.

    Returns:
        La partie de la référence antérieure ou égale à la coupure.

    Raises:
        LookAheadError: si l'index ou les valeurs diffèrent avant la coupure.
    """
    before = reference.loc[:label]
    after = candidate.loc[:label]
    if not before.index.equals(after.index):
        raise LookAheadError(
            f"{name} change la FORME de son passé quand {cause}, "
            f"à la coupure {label!r}. C'est une fuite d'information."
        )
    same = np.allclose(
        np.asarray(before, dtype=float),
        np.asarray(after, dtype=float),
        rtol=0.0,
        atol=tolerance,
        equal_nan=True,
    )
    if not same:
        raise LookAheadError(
            f"{name} change avant la coupure {label!r} quand {cause}. La caractéristique lit le futur."
        )
    return before


def assert_causal(
    feature: Callable[[PandasObj], PandasObj],
    source: PandasObj,
    *,
    cut_fractions: Sequence[float] = DEFAULT_CUT_FRACTIONS,
    perturbation: float = DEFAULT_PERTURBATION,
    tolerance: float = CAUSALITY_TOLERANCE,
    name: str = "feature",
) -> None:
    r"""Vérifie qu'une caractéristique ne lit pas le futur, sur des données construites.

    **Le problème.** Une fuite d'information ne se signale par aucune erreur.
    Le code tourne, les tableaux ont la bonne forme, et le résultat est faux
    dans le sens flatteur. Une relecture attentive attrape les fuites évidentes
    et laisse passer les autres.

    **L'intuition.** Si une caractéristique datée :math:`t` n'utilise que le
    passé, alors modifier les données APRÈS :math:`t` ne doit rien changer avant
    :math:`t`. On modifie donc, on recalcule, et on compare.

    **Le protocole, deux épreuves par coupure.** On calcule la caractéristique
    de référence sur les données d'origine, puis on coupe l'échantillon. La
    première épreuve ajoute ``perturbation`` à toutes les observations
    postérieures à la coupure. La seconde RETIRE ces observations et recalcule
    sur le seul passé. Les deux sorties sont comparées à la référence sur la
    partie antérieure ou égale à la coupure, index compris.

    **Pourquoi la seconde épreuve existe, et ce qu'elle attrape.** Un décalage
    additif conserve l'ORDRE des observations. Trois fuites classiques y
    survivent donc, et le test du module les donne comme contre-exemples
    mesurés. Ce sont le rang sur tout l'échantillon ``x.rank(pct=True)``, la
    winsorisation à un quantile global, et une caractéristique qui lit le nombre
    total d'observations. Retirer le futur les fait toutes tomber, puisqu'une
    fonction causale rend la même valeur que l'avenir existe ou non.

    **Pourquoi trois coupures.** Une seule coupure peut tomber au mauvais
    endroit. Une fuite d'un seul pas placée en début d'échantillon reste
    invisible à une coupure placée aux trois quarts.

    **Pourquoi une perturbation additive.** Elle déplace aussi bien un rendement
    nul qu'un rendement quelconque, là où un facteur multiplicatif laisserait un
    zéro inchangé. Positive, elle garde des prix strictement positifs, donc les
    fonctions qui l'exigent ne lèvent pas d'erreur.

    **Le refus d'un contrôle vide.** Une caractéristique dont la sortie est
    entièrement manquante avant la coupure passerait sans rien prouver. Ce cas
    lève :class:`InsufficientDataError` plutôt que de rendre un succès, parce
    qu'un contrôle qui ne peut rien voir n'est pas un contrôle.

    **Ce que le contrôle ne prouve pas.** Il prouve que la fonction n'a pas lu
    le futur SUR CES DONNÉES. Une fuite conditionnelle, active seulement sur
    certaines valeurs, peut lui échapper. Le contrôle est nécessaire, il n'est
    pas suffisant.

    **Limites.** L'index doit être croissant et porter au moins quatre
    observations. La comparaison porte sur les valeurs et sur l'index : une
    caractéristique dont le nombre de lignes passées change avec le futur est
    déjà une fuite. La seconde épreuve appelle la fonction sur un échantillon
    court, donc une caractéristique qui exige une longueur minimale lèvera sa
    propre erreur.

    **Provenance.** Le principe est celui du test de non-anticipation employé
    par López de Prado (2018), chapitre 7, et la mise en oeuvre par perturbation
    est celle retenue dans ce dépôt.

    **Comment vérifier le contrôle lui-même.** Il doit ÉCHOUER sur une fonction
    qui appelle ``shift(-1)``, sur une moyenne mobile centrée, sur une
    normalisation calculée sur tout l'échantillon, et sur les trois fuites
    d'ordre citées plus haut. Le test le vérifie une par une. Un contrôle qui ne
    refuse rien ne contrôle rien.

    Args:
        feature: la fonction à contrôler, qui prend les données et rend la
            caractéristique.
        source: les données d'entrée, indexées par le temps.
        cut_fractions: les positions de coupure, en fraction de l'échantillon.
        perturbation: la quantité ajoutée après la coupure.
        tolerance: l'écart absolu maximal toléré avant la coupure.
        name: le nom employé dans le message d'erreur.

    Raises:
        LookAheadError: si la caractéristique change avant la coupure.
        ConfigError: si une fraction de coupure sort de l'intervalle ouvert.
        InsufficientDataError: si l'échantillon est trop court, ou si la sortie
            est entièrement manquante avant une coupure.
        TypeError: si la caractéristique ne rend ni Series ni DataFrame.
    """
    _validate(source, name="source", minimum=MIN_CAUSALITY_OBS)
    reference = feature(source)
    if not isinstance(reference, pd.Series | pd.DataFrame):
        raise TypeError(f"{name} doit rendre une Series ou un DataFrame, reçu {type(reference)!r}")

    total = len(source)
    for fraction in cut_fractions:
        if not 0.0 < fraction < 1.0:
            raise ConfigError(
                f"chaque fraction de coupure doit tenir dans l'intervalle ouvert, reçu {fraction}"
            )
        cut = min(max(math.floor(fraction * total), 0), total - 2)
        label = source.index[cut]

        perturbed = source.copy()
        perturbed.iloc[cut + 1 :] = perturbed.iloc[cut + 1 :].to_numpy() + perturbation
        before = _compare_before_cut(
            reference,
            feature(perturbed),
            label,
            tolerance=tolerance,
            name=name,
            cause=f"les données postérieures sont décalées de {perturbation}",
        )

        _compare_before_cut(
            reference,
            feature(source.iloc[: cut + 1]),
            label,
            tolerance=tolerance,
            name=name,
            cause="le futur est retiré de l'échantillon",
        )

        observed = np.asarray(before, dtype=float)
        if observed.size == 0 or not bool(np.isfinite(observed).any()):
            raise InsufficientDataError(
                f"{name} ne rend aucune valeur finie avant la coupure {label!r}, "
                "donc le contrôle passerait sans rien prouver. Raccourcir la fenêtre "
                "ou allonger l'échantillon."
            )

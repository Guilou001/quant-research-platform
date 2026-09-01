"""La perte depuis le sommet : mesure, épisodes, et pourquoi elle n'est pas comparable.

**Le problème.** Un investisseur ne quitte pas une stratégie parce que sa
volatilité est haute. Il la quitte parce qu'il a perdu 40 % depuis le sommet,
sans savoir quand le capital reviendra. Le drawdown mesure exactement
cela : l'écart entre la richesse d'aujourd'hui et le plus haut niveau atteint
jusqu'ici.

**La convention de signe du laboratoire, déclarée une fois pour toutes.** Le
drawdown est NÉGATIF ou nul. Il vaut zéro quand la richesse touche un nouveau
sommet, et -0,25 quand elle a perdu un quart depuis son sommet. Les fonctions
qui rendent un niveau de drawdown (:func:`max_drawdown`,
:func:`average_drawdown`, :func:`conditional_drawdown_at_risk`) rendent donc un
nombre négatif. Les deux fonctions qui rendent une norme de la série
(:func:`ulcer_index`, :func:`pain_index`) rendent un nombre positif, une racine
de moyenne de carrés et une moyenne de valeurs absolues ne pouvant pas être
négatives.

**Le point de méthode qui invalide la moitié des comparaisons publiées.** Le
drawdown maximal d'un backtest croît mécaniquement avec la longueur de
l'échantillon, même sans aucun changement du processus qui engendre les
rendements. La raison est le maximum : ajouter des observations ne peut jamais
faire baisser un maximum, seulement le laisser égal ou le faire monter. Une
stratégie observée sur vingt ans affiche donc un pire drawdown qu'une stratégie
identique observée sur cinq ans, et l'écart ne dit rien sur leurs risques
respectifs.

L'ordre de grandeur est connu. Pour une marche aléatoire sans dérive de
volatilité :math:`\\sigma` par période, observée sur :math:`T` périodes,
l'espérance du drawdown maximal vaut

.. math::

    \\mathbb{E}[MDD_T] = \\sqrt{\\frac{\\pi}{2}}\\, \\sigma \\sqrt{T}
    \\approx 1{,}2533\\, \\sigma \\sqrt{T}

Résultat RAPPORTÉ, dû à Magdon-Ismail, Atiya, Pratap et Abu-Mostafa (2004),
« On the maximum drawdown of a Brownian motion », *Journal of Applied
Probability*, 41(1), 147-161. Les mêmes auteurs le reprennent sous forme
praticienne dans Magdon-Ismail et Atiya (2004), « Maximum drawdown », *Risk*,
17(10), 99-102. Le cas à dérive
non nulle n'a pas de forme fermée élémentaire dans ces travaux, il s'exprime par
une série que les auteurs tabulent.

Conséquence chiffrée, MODÉLISÉE depuis cette formule. À 1 % de volatilité
quotidienne, l'espérance du drawdown maximal passe de 19,9 % sur un an de
252 séances à 28,1 % sur deux ans, sans que rien ait changé dans la stratégie.
Quadrupler la fenêtre double le drawdown attendu. Le test
``test_max_drawdown_croit_en_racine_du_temps`` du module de tests vérifie cette
croissance par simulation, et c'est la seule vérification chiffrée que le
laboratoire porte sur ce résultat.

**Ce qu'il faut faire à la place.** Comparer deux drawdowns maximaux exige la
même fenêtre, ou une normalisation par :math:`\\sqrt{T}`, ou l'usage d'une
mesure qui ne soit pas un maximum. L'indice d'ulcère et l'indice de peine
moyennent sur toute la période, et ne souffrent donc pas de ce biais de
longueur. Le drawdown conditionnel en souffre beaucoup moins, sa moyenne
portant sur une fraction fixe des observations.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from quantlab.core.errors import DataQualityError, InsufficientDataError
from quantlab.core.types import ReturnSeries

__all__ = [
    "EPISODE_COLUMNS",
    "average_drawdown",
    "conditional_drawdown_at_risk",
    "drawdown_series",
    "drawdown_table",
    "max_drawdown",
    "max_drawdown_duration",
    "pain_index",
    "pain_ratio",
    "time_to_recovery",
    "ulcer_index",
]

#: Colonnes du tableau d'épisodes, dans leur ordre de lecture.
EPISODE_COLUMNS: tuple[str, ...] = (
    "start",
    "trough",
    "end",
    "depth",
    "length",
    "time_to_trough",
    "recovery",
    "recovered",
)


def _check_index(series: pd.Series) -> None:
    """Refuse un index non ordonné ou porteur de doublons.

    Un index en désordre fausse silencieusement le maximum courant, qui suppose
    que la ligne suivante est postérieure à la précédente. Le portefeuille en a
    déjà payé le prix au paquet ``gvf.marches``. Des horodatages lus dans la
    mauvaise unité y mettaient les prix en face des mauvaises minutes, avec le
    bon nombre de lignes et les bonnes colonnes.

    Raises:
        DataQualityError: si l'index porte un doublon ou n'est pas croissant.
    """
    if series.index.has_duplicates:
        raise DataQualityError("l'index porte des dates en double, le maximum courant serait faux")
    if not series.index.is_monotonic_increasing:
        raise DataQualityError("l'index n'est pas croissant, le maximum courant serait faux")


def _as_wealth(returns_or_wealth: ReturnSeries, is_wealth: bool) -> pd.Series:
    """Rend la courbe de richesse et son plancher de sommet initial.

    Args:
        returns_or_wealth: rendements simples de période, ou niveaux de richesse.
        is_wealth: ``True`` si la série est déjà une richesse.

    Returns:
        La courbe de richesse, indexée comme l'entrée.

    Raises:
        InsufficientDataError: si la série est vide.
        DataQualityError: en présence de valeurs manquantes, d'un rendement
            strictement inférieur à -100 %, d'une richesse négative ou d'une
            richesse initiale nulle.
    """
    series = pd.Series(returns_or_wealth).astype("float64")
    if series.empty:
        raise InsufficientDataError("série vide : le drawdown demande au moins une observation")
    _check_index(series)
    if series.isna().any():
        raise DataQualityError(
            "la série porte des valeurs manquantes ; décidez explicitement quoi en faire "
            "avant d'appeler ce module, un NaN dans un maximum courant se propage en silence"
        )
    if is_wealth:
        if (series < 0).any():
            raise DataQualityError("une richesse négative n'a pas de drawdown interprétable")
        if series.iloc[0] <= 0:
            raise DataQualityError("la richesse initiale doit être strictement positive")
        return series
    if (series < -1.0).any():
        raise DataQualityError(
            "un rendement simple inférieur à -100 % rendrait la richesse négative ; "
            "vérifiez l'unité, un rendement en pourcentage n'est pas un rendement en fraction"
        )
    return (1.0 + series).cumprod()


def drawdown_series(returns_or_wealth: ReturnSeries, is_wealth: bool = False) -> pd.Series:
    """Rend la perte relative depuis le sommet, période par période, négative ou nulle.

    **Le problème.** La volatilité traite une hausse et une baisse de la même
    façon, alors que l'investisseur ne les vit pas de la même façon. Le drawdown
    ne regarde que ce qui a été perdu depuis le meilleur moment déjà vécu.

    **L'intuition.** On garde en mémoire le plus haut niveau de richesse atteint
    jusqu'ici, le sommet courant. Le drawdown du jour est l'écart relatif entre
    la richesse du jour et ce sommet. Il est nul les jours de nouveau record, et
    négatif tous les autres jours.

    .. math::

        NAV_t = \\prod_{s \\le t} (1 + r_s), \\qquad
        Peak_t = \\max_{s \\le t} NAV_s, \\qquad
        DD_t = \\frac{NAV_t - Peak_t}{Peak_t}

    Définition de chaque variable. :math:`r_s` est le rendement simple de la
    période :math:`s`. :math:`NAV_t` est la richesse cumulée à la fin de la
    période :math:`t`, partant de 1. :math:`Peak_t` est le maximum courant de
    cette richesse, borné par en dessous par le capital de départ. :math:`DD_t`
    est le drawdown, exprimé en fraction du sommet et non en points de
    pourcentage.

    **Hypothèses.** Les observations sont ordonnées dans le temps et sans trou de
    numéraire. Les rendements sont SIMPLES et nets de tout ce que l'appelant
    voulait retirer : ce module ne connaît ni frais ni fiscalité. La richesse
    est mesurée en fin de période, si bien qu'un creux intrapériode plus profond
    n'est pas vu, et c'est une sous-estimation systématique du drawdown vrai.

    **Convention déclarée du capital initial.** Quand l'entrée est une série de
    rendements, le capital de départ vaut 1 et compte comme un sommet. Un premier
    rendement de -5 % rend donc un drawdown de -5 %, et non de 0 %. Quand
    l'entrée est déjà une richesse, le premier point est le premier sommet, donc
    son drawdown vaut zéro par construction. Les deux conventions se rejoignent
    si l'appelant préfixe lui-même sa courbe de richesse par son capital initial.

    **Provenance.** La mesure est ancienne et sans auteur unique. Sa
    forme moderne vient de Chekhlov, Uryasev et Zabarankin (2005), « Drawdown
    measure in portfolio optimization », *International Journal of Theoretical
    and Applied Finance*, 8(1), 13-58. Ces auteurs la définissent exactement
    comme ci-dessus, et en font une mesure de risque optimisable.

    **Limites.** Le drawdown est un extremum de trajectoire, donc une statistique
    d'ordre : il est très bruité et dépend de la longueur de l'échantillon, comme
    la docstring du module l'établit. Il ignore la fréquence des pertes, deux
    trajectoires très différentes pouvant partager le même drawdown maximal.

    **Alternatives.** La volatilité mesure la dispersion mais pas la trajectoire.
    La valeur à risque mesure une queue de distribution période par période sans
    tenir compte de l'enchaînement des pertes. L'indice d'ulcère, calculé par
    :func:`ulcer_index`, résume la même série en une norme moins bruitée.

    **Pourquoi cette méthode ici.** Le drawdown répond à la question que pose
    réellement un comité d'investissement. Combien le capital a-t-il perdu
    depuis son meilleur niveau, et pendant combien de temps.

    **Comment vérifier.** Sur la richesse (100, 120, 90, 110, 150), le sommet
    vaut (100, 120, 120, 120, 150) et le drawdown (0, 0, -0,25, -1/12, 0). Le
    calcul se fait à la main en trois lignes, et c'est le test principal du
    module. La négativité du résultat est DÉMONTRÉE et non imposée : la
    fonction ne plafonne rien à zéro, si bien qu'un sommet mal calculé rend
    des valeurs positives et se voit.

    Args:
        returns_or_wealth: rendements simples de période, ou niveaux de richesse
            si ``is_wealth`` vaut ``True``.
        is_wealth: ``True`` quand la série est une richesse cumulée.

    Returns:
        Une série de mêmes index et longueur que l'entrée, à valeurs dans
        :math:`[-1, 0]`.

    Raises:
        InsufficientDataError: si la série est vide.
        DataQualityError: si la série porte des NaN, un index non croissant ou
            des valeurs incompatibles avec la convention retenue.

    Example:
        >>> import pandas as pd
        >>> wealth = pd.Series([100.0, 120.0, 90.0, 110.0, 150.0])
        >>> drawdown_series(wealth, is_wealth=True).round(4).tolist()
        [0.0, 0.0, -0.25, -0.0833, 0.0]
    """
    wealth = _as_wealth(returns_or_wealth, is_wealth)
    peak = wealth.cummax()
    if not is_wealth:
        peak = peak.clip(lower=1.0)
    # Aucun plafonnement à zéro ici, et le choix est délibéré. Le sommet majore
    # la richesse par construction, la division en virgule flottante préserve
    # cette borne, donc le plafonnement serait sans effet. Il serait pire que
    # sans effet : il rendrait la propriété « drawdown négatif ou nul » vraie
    # quoi qu'il arrive. Mesuré le 2026-09-01, un sommet remplacé par une
    # moyenne courante passait le test de propriété tant que le plafonnement
    # était en place, et échoue depuis son retrait.
    return (wealth / peak - 1.0).rename("drawdown")


def max_drawdown(returns_or_wealth: ReturnSeries, is_wealth: bool = False) -> float:
    r"""Rend la pire perte depuis un sommet de toute la période, négative ou nulle.

    **Le problème.** Un comité d'investissement demande d'abord un seul nombre :
    combien le capital a-t-il perdu, au pire, depuis son meilleur niveau. Le
    drawdown maximal est ce nombre.

    **L'intuition.** On prend la série des drawdowns et on garde son minimum.

    .. math::

        MDD = \min_{t \le T} DD_t
        = \min_{t \le T} \left( \frac{NAV_t}{\max_{s \le t} NAV_s} - 1 \right)

    :math:`NAV_t` est la richesse cumulée à la fin de la période :math:`t`,
    :math:`DD_t` son drawdown, et :math:`T` le nombre de périodes observées.

    **Hypothèses.** Celles de :func:`drawdown_series`. La valeur est bornée par
    -1 quand les rendements ne descendent pas sous -100 %, une richesse restant
    alors positive ou nulle.

    **Provenance.** La mesure est de pratique courante et sans auteur unique.
    Son comportement statistique, lui, est établi par Magdon-Ismail, Atiya,
    Pratap et Abu-Mostafa (2004), « On the maximum drawdown of a Brownian
    motion », *Journal of Applied Probability*, 41(1), 147-161.

    **Limites.** C'est une statistique d'un seul point, donc la moins
    reproductible de toutes celles du module. Elle croît mécaniquement avec la
    longueur de l'échantillon, et la docstring du module donne la loi.

    **Alternatives.** :func:`conditional_drawdown_at_risk` moyenne une queue au
    lieu d'un point. :func:`ulcer_index` et :func:`pain_index` moyennent toute
    la trajectoire et ne dépendent pas de la longueur de l'échantillon.

    **Pourquoi cette méthode ici.** C'est le chiffre que le lecteur attend, et
    le dénominateur du ratio de Calmar. Le module le rend, et déclare au même
    endroit pourquoi il ne se compare pas d'une fenêtre à l'autre.

    **Comment vérifier.** Deux contrôles indépendants dans le module de tests.
    Le premier lit le minimum à la main sur la série de référence. Le second
    fait une recherche exhaustive en :math:`O(n^2)` sur toutes les paires de
    positions, sans tenir aucun maximum courant.

    Args:
        returns_or_wealth: rendements simples, ou richesse si ``is_wealth``.
        is_wealth: ``True`` quand la série est une richesse cumulée.

    Returns:
        Le drawdown maximal, en fraction du sommet, négatif ou nul.

    Note:
        Ce chiffre ne se compare qu'à fenêtre égale. La docstring du module dit
        pourquoi, et donne la loi de croissance en racine du temps.

    Example:
        >>> import pandas as pd
        >>> max_drawdown(pd.Series([100.0, 120.0, 90.0, 110.0, 150.0]), is_wealth=True)
        -0.25
    """
    return float(drawdown_series(returns_or_wealth, is_wealth).min())


def _episode_bounds(drawdown: pd.Series) -> list[tuple[int, int, int]]:
    """Rend les épisodes sous forme de positions (début, creux, fin ou -1).

    Un épisode est une suite maximale de périodes consécutives de drawdown
    strictement négatif. Sa fin est la première période de retour à zéro, et
    vaut -1 quand l'échantillon se termine sous l'eau.
    """
    values = drawdown.to_numpy(dtype="float64")
    under_water = values < 0.0
    episodes: list[tuple[int, int, int]] = []
    position = 0
    n = len(values)
    while position < n:
        if not under_water[position]:
            position += 1
            continue
        start = position
        while position < n and under_water[position]:
            position += 1
        stop = position  # première position hors de l'eau, ou n
        trough = start + int(np.argmin(values[start:stop]))
        end = stop if stop < n else -1
        episodes.append((start, trough, end))
    return episodes


def _labels(index: pd.Index, positions: np.ndarray, missing: np.ndarray) -> pd.Series:
    """Rend les étiquettes d'index aux positions données, avec des valeurs manquantes.

    Note:
        ``Index.take`` ne remplit pas les positions à -1 comme on l'attendrait :
        mesuré le 2026-09-01, un ``RangeIndex(5).take([0, -1], allow_fill=True)``
        rend ``RangeIndex(0, 8, 4)``, donc la dernière étiquette au lieu d'un
        trou. Le masquage explicite ci-dessous évite ce piège.
    """
    safe = np.where(missing, 0, positions)
    values = pd.Series(index.take(safe))
    if not missing.any():
        return values
    if pd.api.types.is_integer_dtype(values.dtype):
        values = values.astype("Int64")
    elif not (
        pd.api.types.is_float_dtype(values.dtype) or pd.api.types.is_datetime64_any_dtype(values.dtype)
    ):
        values = values.astype(object)
    return values.mask(missing)


def drawdown_table(returns_or_wealth: ReturnSeries, is_wealth: bool = False) -> pd.DataFrame:
    """Rend un épisode de drawdown par ligne, du premier au dernier, chronologiquement.

    **Le problème.** Le drawdown maximal résume une trajectoire par un seul
    nombre et cache tout le reste : combien d'épisodes, combien de temps sous
    l'eau, combien de temps pour revenir. Deux stratégies de même drawdown
    maximal peuvent avoir passé trois mois ou six ans sous leur sommet.

    **Définition d'un épisode.** Une suite maximale de périodes consécutives de
    drawdown strictement négatif. L'épisode commence à la première période
    perdante, touche son creux au minimum de la suite, et se termine à la
    première période de retour au sommet. Un épisode encore ouvert à la fin de
    l'échantillon est marqué ``recovered = False`` et NON ignoré : l'ignorer
    reviendrait à effacer précisément la perte que l'investisseur porte encore.

    **Les colonnes, et leur unité.**

    - ``start`` : étiquette de la première période sous l'eau ;
    - ``trough`` : étiquette du creux, la première en cas d'égalité ;
    - ``end`` : étiquette de la période de retour à zéro, manquante si non recouvré ;
    - ``depth`` : profondeur du creux, négative, en fraction du sommet ;
    - ``length`` : nombre de périodes de drawdown strictement négatif ;
    - ``time_to_trough`` : nombre de périodes du début au creux, bornes incluses ;
    - ``recovery`` : nombre de périodes écoulées du creux au retour à zéro, manquant
      si non recouvré ;
    - ``recovered`` : vrai si le sommet a été retrouvé avant la fin de l'échantillon.

    **Identité à vérifier.** Pour tout épisode recouvré,
    ``length == time_to_trough + recovery - 1``. Elle tient parce que les deux
    comptes se recouvrent d'exactement une période, celle du creux. C'est le
    contrôle qui attrape une erreur de borne, et le module de tests le porte.

    **Hypothèses.** Une période vaut une ligne, quelle que soit sa durée
    calendaire. Sur une série quotidienne trouée, ``length`` compte des séances
    et non des jours, et le lecteur qui veut des jours doit passer par l'index.

    **Provenance.** La décomposition en épisodes est de pratique courante et sans
    auteur unique. La distinction entre durée sous l'eau et durée de
    recouvrement, en revanche, est celle de Chekhlov, Uryasev et Zabarankin
    (2005), qui montrent que la seconde gouverne l'inconfort du détenteur.

    **Limites.** La définition par le seuil zéro fabrique des épisodes minuscules
    dès qu'une série oscille près de son sommet : une perte de 0,01 % suivie d'un
    record compte comme un épisode. Un lecteur qui veut les épisodes qui comptent
    filtre sur ``depth``.

    **Alternatives.** Certaines implémentations font commencer l'épisode à la
    date du sommet plutôt qu'à la première période perdante. Le choix change
    toutes les durées d'exactement une période. Celui retenu ici a une propriété
    utile : il reste défini quand le sommet précède le début de l'échantillon.

    **Pourquoi cette méthode ici.** Elle rend le tableau lisible sans note de bas
    de page, chaque durée étant un compte de lignes vérifiable à l'œil sur un
    petit exemple.

    Args:
        returns_or_wealth: rendements simples, ou richesse si ``is_wealth``.
        is_wealth: ``True`` quand la série est une richesse cumulée.

    Returns:
        Un tableau à huit colonnes, une ligne par épisode, dans l'ordre
        chronologique. Le tableau est vide, colonnes comprises, quand la série
        ne descend jamais sous son sommet.

    Example:
        >>> import pandas as pd
        >>> table = drawdown_table(pd.Series([100.0, 120.0, 90.0, 110.0, 150.0]), is_wealth=True)
        >>> [int(table.loc[0, c]) for c in ("start", "trough", "end", "length", "recovery")]
        [2, 2, 4, 2, 2]
        >>> table["depth"].tolist()
        [-0.25]
    """
    drawdown = drawdown_series(returns_or_wealth, is_wealth)
    index = drawdown.index
    episodes = _episode_bounds(drawdown)
    if not episodes:
        return pd.DataFrame(
            {
                "start": index[:0],
                "trough": index[:0],
                "end": index[:0],
                "depth": pd.Series(dtype="float64"),
                "length": pd.Series(dtype="int64"),
                "time_to_trough": pd.Series(dtype="int64"),
                "recovery": pd.array([], dtype="Int64"),
                "recovered": pd.Series(dtype="bool"),
            }
        )
    starts = np.array([e[0] for e in episodes], dtype="int64")
    troughs = np.array([e[1] for e in episodes], dtype="int64")
    ends = np.array([e[2] for e in episodes], dtype="int64")
    open_episode = ends < 0
    values = drawdown.to_numpy(dtype="float64")
    last_negative = np.where(open_episode, len(values) - 1, ends - 1)
    recovery = pd.array(np.where(open_episode, 0, ends - troughs), dtype="Int64")
    recovery[open_episode] = pd.NA
    never = np.zeros(len(starts), dtype=bool)
    return pd.DataFrame(
        {
            "start": _labels(index, starts, never),
            "trough": _labels(index, troughs, never),
            "end": _labels(index, ends, open_episode),
            "depth": values[troughs],
            "length": last_negative - starts + 1,
            "time_to_trough": troughs - starts + 1,
            "recovery": recovery,
            "recovered": ~open_episode,
        }
    )


def average_drawdown(
    returns_or_wealth: ReturnSeries,
    is_wealth: bool = False,
    top: int | None = None,
) -> float:
    """Rend la profondeur moyenne des épisodes de drawdown, négative ou nulle.

    **Le problème.** Le drawdown maximal ne retient qu'un seul épisode, celui
    qui se trouve avoir été le pire, et cet épisode est souvent un accident. La
    moyenne des épisodes dit à quoi ressemble une mauvaise passe ordinaire.

    .. math::

        \\overline{DD} = \\frac{1}{K} \\sum_{k=1}^{K} \\min_{t \\in E_k} DD_t

    :math:`E_k` est le k-ième épisode au sens de :func:`drawdown_table`,
    :math:`K` le nombre d'épisodes retenus. La moyenne porte sur les
    PROFONDEURS d'épisodes, une par épisode, et non sur les périodes.

    **Hypothèses.** Chaque épisode pèse autant que les autres, qu'il ait duré
    trois jours ou trois ans. C'est un choix, et il diffère de celui de
    :func:`pain_index`, qui pondère chaque période également et compte donc les
    périodes au sommet comme des zéros.

    **Provenance.** La moyenne des :math:`N` pires drawdowns est la brique du
    ratio de Sterling et du ratio de Burke, décrits par Bacon (2008),
    *Practical Portfolio Performance Measurement and Attribution*, 2e édition,
    chapitre 4. L'argument ``top`` sert exactement à cela.

    **Limites.** Le nombre d'épisodes dépend du seuil zéro, donc du bruit de
    haute fréquence : une même trajectoire échantillonnée en quotidien et en
    mensuel ne donne pas le même nombre d'épisodes ni la même moyenne.

    **Alternatives.** L'indice de peine moyenne sur toutes les périodes,
    l'indice d'ulcère pénalise les épisodes profonds par le carré, et le
    drawdown conditionnel ne moyenne que la queue.

    **Pourquoi cette méthode ici.** Elle rend comparable la mauvaise passe
    typique de deux stratégies, là où le maximum ne compare que leurs accidents.

    **Comment vérifier.** Sur une série à deux épisodes de -0,25 et -0,05, la
    fonction rend -0,15 exactement, et -0,25 avec ``top=1``.

    Args:
        returns_or_wealth: rendements simples, ou richesse si ``is_wealth``.
        is_wealth: ``True`` quand la série est une richesse cumulée.
        top: si donné, ne moyenne que les ``top`` épisodes les plus profonds.
            Sans valeur, moyenne tous les épisodes.

    Returns:
        La profondeur moyenne, négative, ou ``0.0`` si la série ne descend
        jamais sous son sommet.

    Raises:
        ValueError: si ``top`` est inférieur à 1.
    """
    if top is not None and top < 1:
        raise ValueError("top doit valoir au moins 1")
    depths = drawdown_table(returns_or_wealth, is_wealth)["depth"]
    if depths.empty:
        return 0.0
    if top is not None:
        depths = depths.nsmallest(top)
    return float(depths.mean())


def max_drawdown_duration(returns_or_wealth: ReturnSeries, is_wealth: bool = False) -> int:
    """Rend la plus longue durée passée sous un sommet, en nombre de périodes.

    La durée compte les périodes de drawdown strictement négatif du plus long
    épisode, colonne ``length`` de :func:`drawdown_table`. Un épisode encore
    ouvert à la fin de l'échantillon compte pour ce qu'il a déjà duré, ce qui
    SOUS-ESTIME sa vraie durée, inconnue à ce jour.

    Args:
        returns_or_wealth: rendements simples, ou richesse si ``is_wealth``.
        is_wealth: ``True`` quand la série est une richesse cumulée.

    Returns:
        Un nombre de périodes, nul si la série ne descend jamais sous son sommet.

    Note:
        L'unité est la période de la série, pas le jour calendaire. Sur une
        série mensuelle, 14 se lit « quatorze mois ».

    Note:
        **L'épisode retenu est le plus LONG, pas le plus profond.** Les deux
        diffèrent souvent. Le module de tests le pose sur une série où le pire
        creux dure deux périodes et le plus long en dure trois. Provenance : la
        distinction entre profondeur et durée sous l'eau est celle de Chekhlov,
        Uryasev et Zabarankin (2005). Limite : un épisode encore ouvert compte
        pour ce qu'il a déjà duré. Alternative : :func:`time_to_recovery`, qui
        compte du creux au retour.
    """
    lengths = drawdown_table(returns_or_wealth, is_wealth)["length"]
    return 0 if lengths.empty else int(lengths.max())


def time_to_recovery(returns_or_wealth: ReturnSeries, is_wealth: bool = False) -> int | None:
    """Rend le nombre de périodes du pire creux à son retour au sommet.

    Le creux retenu est celui du drawdown maximal, donc l'épisode le plus
    profond et non le plus long. La valeur est ``None`` quand ce creux n'a pas
    encore été recouvré à la fin de l'échantillon, information qu'il serait faux
    de remplacer par un nombre.

    Args:
        returns_or_wealth: rendements simples, ou richesse si ``is_wealth``.
        is_wealth: ``True`` quand la série est une richesse cumulée.

    Returns:
        Le nombre de périodes écoulées entre le creux et le retour à zéro,
        ``0`` si la série ne descend jamais sous son sommet, ``None`` si le pire
        creux n'est pas recouvré.

    Note:
        **L'épisode retenu est le plus PROFOND, pas le plus long.** Sur la
        richesse (100, 90, 80, 100, 95, 96, 97, 100), le pire creux se recouvre
        en une période. Le plus long épisode, lui, en demande trois, et la
        fonction rend donc 1. Le module de tests porte ce contrôle, sans lequel
        un tri inversé passerait inaperçu. Alternative :
        :func:`max_drawdown_duration`, qui compte les périodes sous l'eau au
        lieu des périodes de retour.

    Example:
        Sur la richesse (100, 120, 90, 110, 150), le creux est à la position 2
        et le retour au sommet à la position 4, donc deux périodes.
    """
    table = drawdown_table(returns_or_wealth, is_wealth)
    if table.empty:
        return 0
    worst = table["depth"].idxmin()
    if not bool(table.loc[worst, "recovered"]):
        return None
    return int(table.loc[worst, "recovery"])


def ulcer_index(returns_or_wealth: ReturnSeries, is_wealth: bool = False) -> float:
    """Rend la racine de la moyenne des carrés des drawdowns, positive ou nulle.

    **Le problème.** Le drawdown maximal ne regarde qu'un instant de la
    trajectoire et jette le reste. Une stratégie qui passe cinq ans à -20 % et
    une autre qui touche -20 % un seul jour ont le même drawdown maximal, et
    n'ont rien en commun pour celui qui détient le fonds.

    **L'intuition.** On mesure la douleur comme une énergie : on carre le
    drawdown de chaque période, on en prend la moyenne, et on rend la racine.
    Le carré fait que deux périodes à -10 % pèsent moins qu'une seule à -20 %,
    ce qui correspond à l'idée qu'une perte profonde fait plus mal que deux
    petites.

    .. math::

        UI = \\sqrt{\\frac{1}{T} \\sum_{t=1}^{T} DD_t^{2}}

    :math:`DD_t` est le drawdown de la période :math:`t`, en fraction, tel que
    le rend :func:`drawdown_series`. :math:`T` est le nombre total de périodes,
    y compris celles passées au sommet, qui comptent comme des zéros.

    **Hypothèses.** Toutes les périodes pèsent également, y compris celles où
    rien ne se passe. L'indice dépend donc de la proportion de temps passé au
    sommet, ce qui est voulu : une stratégie qui touche souvent ses records est
    moins douloureuse.

    **Provenance.** Martin et McCann (1989), *The Investor's Guide to Fidelity
    Funds*, John Wiley & Sons, où l'indice est introduit sous ce nom. Les
    auteurs le calculent sur des drawdowns exprimés en POURCENTAGE, si bien que
    leur indice vaut cent fois celui rendu ici. Cette fonction reste en
    fraction, comme le reste du laboratoire, et la conversion est une simple
    multiplication par cent, l'indice étant homogène de degré un.

    **Limites.** L'indice n'a pas d'unité interprétable seule : 0,08 ne se lit
    pas « 8 % de perte », il se compare à l'indice d'une autre stratégie sur la
    MÊME période. Il dépend aussi de la fréquence d'échantillonnage, un même
    parcours mesuré en mensuel gommant les creux intramensuels.

    **Alternatives.** L'indice de peine, :func:`pain_index`, remplace le carré
    par la valeur absolue et pénalise donc moins les creux profonds. Le drawdown
    conditionnel, :func:`conditional_drawdown_at_risk`, ne regarde que la queue.

    **Pourquoi cette méthode ici.** L'indice d'ulcère utilise toute la
    trajectoire, il ne dépend pas de la longueur de l'échantillon comme un
    maximum, et il se compare donc entre deux fenêtres de tailles différentes.

    **Comment vérifier.** Sur la richesse (100, 120, 90, 110, 150), les
    drawdowns sont (0, 0, -0,25, -1/12, 0). La somme des carrés vaut
    0,0625 + 0,00694444 = 0,06944444, divisée par 5 elle donne 0,01388889, dont
    la racine vaut 0,11785113. Une série strictement croissante a tous ses
    drawdowns nuls, donc un indice nul, et c'est le second test.

    Args:
        returns_or_wealth: rendements simples, ou richesse si ``is_wealth``.
        is_wealth: ``True`` quand la série est une richesse cumulée.

    Returns:
        Un nombre positif ou nul, en fraction du sommet.

    Example:
        >>> import pandas as pd
        >>> round(ulcer_index(pd.Series([100.0, 120.0, 90.0, 110.0, 150.0]), is_wealth=True), 8)
        0.11785113
    """
    drawdown = drawdown_series(returns_or_wealth, is_wealth).to_numpy(dtype="float64")
    return float(np.sqrt(np.mean(np.square(drawdown))))


def pain_index(returns_or_wealth: ReturnSeries, is_wealth: bool = False) -> float:
    """Rend la profondeur moyenne du drawdown sur toutes les périodes, positive ou nulle.

    **Le problème.** L'indice d'ulcère écrase les petits creux par le carré, ce
    qui le rend difficile à interpréter en niveau. La moyenne des valeurs
    absolues, elle, se lit directement : « en moyenne, le capital est resté
    3,2 % sous son sommet ».

    .. math::

        PI = \\frac{1}{T} \\sum_{t=1}^{T} |DD_t| = -\\frac{1}{T} \\sum_{t=1}^{T} DD_t

    :math:`DD_t` est le drawdown de la période :math:`t`, négatif ou nul, et
    :math:`T` le nombre total de périodes, celles au sommet comprises.

    **Hypothèses.** Mêmes que pour :func:`ulcer_index` : toutes les périodes
    pèsent également, et l'indice dépend de la fréquence d'échantillonnage.

    **Provenance.** L'indice de peine est décrit par Becker (1998), « Aspects of
    investment performance measurement », et exposé sous cette forme par Bacon
    (2008), *Practical Portfolio Performance Measurement and Attribution*,
    2e édition, chapitre 4. Le nom de la mesure vient du rapport qui l'utilise,
    le ratio de peine.

    **Limites.** Il traite deux périodes à -10 % comme une période à -20 %. C'est
    faux du point de vue de celui qui détient, puisque la seconde peut le faire
    vendre et les deux premières non.

    **Alternatives.** L'indice d'ulcère, quand on veut pénaliser la profondeur.
    Le drawdown conditionnel, quand seule la queue intéresse.

    **Pourquoi cette méthode ici.** Il est le dénominateur du ratio de peine, et
    il donne l'unique chiffre de drawdown qui se lit sans référence, en
    pourcentage moyen sous le sommet.

    **Comment vérifier.** Sur la richesse (100, 120, 90, 110, 150), la somme des
    valeurs absolues vaut 0,25 + 0,0833333 = 0,3333333, divisée par 5 elle donne
    0,0666667.

    Args:
        returns_or_wealth: rendements simples, ou richesse si ``is_wealth``.
        is_wealth: ``True`` quand la série est une richesse cumulée.

    Returns:
        Un nombre positif ou nul, en fraction du sommet.
    """
    drawdown = drawdown_series(returns_or_wealth, is_wealth).to_numpy(dtype="float64")
    return float(-np.mean(drawdown))


def pain_ratio(
    returns_or_wealth: ReturnSeries,
    *,
    annualized_excess_return: float,
    is_wealth: bool = False,
) -> float:
    """Rend le rapport du rendement annualisé en excès à l'indice de peine.

    **Le problème.** Un rendement ne se juge pas seul. Le ratio de Sharpe le
    rapporte à la volatilité, qui punit autant les hausses que les baisses. Le
    ratio de peine le rapporte à ce qui a réellement été subi, le temps passé
    sous le sommet.

    .. math::

        PainRatio = \\frac{R_{ann} - R_f}{PI}

    :math:`R_{ann} - R_f` est le rendement annualisé en excès du taux sans
    risque, fourni par l'appelant, et :math:`PI` l'indice de peine calculé par
    :func:`pain_index` sur la même série et la même période.

    **Pourquoi le rendement est un ARGUMENT et non un calcul.** La règle 12 du
    laboratoire interdit d'implémenter deux fois une métrique financière. Le
    rendement annualisé vit dans le module des rendements, pas ici, et cette
    fonction ne le recalcule donc pas. L'appelant passe un chiffre mesuré et
    déclare lui-même sa convention d'annualisation.

    **Hypothèses.** Le rendement en excès et l'indice de peine portent sur la
    MÊME période et la MÊME série. Rien dans la signature ne peut le vérifier,
    et c'est la limite principale de cette fonction.

    **Provenance.** Bacon (2008), *Practical Portfolio Performance Measurement
    and Attribution*, 2e édition, chapitre 4, qui définit le ratio de peine
    exactement comme ce rapport.

    **Limites.** Le dénominateur tend vers zéro pour une série qui ne descend
    presque jamais sous son sommet, et le ratio explose alors sans que rien
    d'économique ne le justifie. Une série strictement croissante n'a pas de
    ratio de peine, et la fonction lève plutôt que de rendre un infini.

    **Alternatives.** Le ratio de Calmar rapporte le même numérateur au drawdown
    maximal, donc à un extremum bruité. Le ratio d'ulcère utilise l'indice
    d'ulcère au dénominateur et pénalise davantage les creux profonds.

    **Pourquoi cette méthode ici.** Le dénominateur moyenne sur toute la
    période, ce qui le rend beaucoup plus stable qu'un drawdown maximal et
    comparable entre fenêtres de longueurs différentes.

    **Comment vérifier.** Avec un indice de peine de 0,0666667 et un rendement
    en excès de 0,10, le ratio vaut 1,5 exactement.

    Args:
        returns_or_wealth: rendements simples, ou richesse si ``is_wealth``.
        annualized_excess_return: le rendement annualisé net du taux sans
            risque, en fraction, mesuré ailleurs.
        is_wealth: ``True`` quand la série est une richesse cumulée.

    Returns:
        Le ratio, sans unité.

    Raises:
        InsufficientDataError: si l'indice de peine est nul, la série n'étant
            jamais descendue sous son sommet.
    """
    pain = pain_index(returns_or_wealth, is_wealth)
    if pain == 0.0:
        raise InsufficientDataError(
            "indice de peine nul : la série ne descend jamais sous son sommet, "
            "le ratio de peine n'est pas défini"
        )
    return float(annualized_excess_return / pain)


def conditional_drawdown_at_risk(
    returns_or_wealth: ReturnSeries,
    alpha: float = 0.05,
    is_wealth: bool = False,
) -> float:
    """Rend la moyenne des ``alpha`` pires drawdowns de la série, négative ou nulle.

    **Le problème.** Le drawdown maximal repose sur une seule observation, la
    pire, donc sur l'accident le moins reproductible de l'échantillon. La
    moyenne de tous les drawdowns, elle, est écrasée par les longues périodes
    passées près du sommet. Il manque une mesure de queue qui ne dépende pas
    d'un seul point.

    **L'intuition.** On classe les drawdowns du pire au meilleur et on moyenne
    la fraction ``alpha`` la plus mauvaise. Avec ``alpha = 0,05`` sur 1 000
    observations, c'est la moyenne des 50 pires. Le résultat est plus stable que
    le minimum et plus informatif que la moyenne.

    .. math::

        CDaR_\\alpha = -\\frac{1}{\\alpha T}
        \\left[ \\sum_{i=1}^{m} L_{(i)} + (\\alpha T - m)\\, L_{(m+1)} \\right],
        \\qquad m = \\lfloor \\alpha T \\rfloor

    :math:`L_t = -DD_t \\ge 0` est la perte depuis le sommet à la période
    :math:`t`. Les :math:`L_{(1)} \\ge L_{(2)} \\ge \\dots` sont ces mêmes pertes
    classées par ordre décroissant. :math:`T` est le nombre de périodes et
    :math:`\\alpha` la fraction de queue retenue. Le terme fractionnaire assure
    la continuité en :math:`\\alpha`, la formule se réduisant à la moyenne des
    :math:`m` pires quand :math:`\\alpha T` est entier.

    **Convention d'``alpha``, à lire avant usage.** Ici ``alpha`` est la
    FRACTION DE QUEUE : 0,05 veut dire « les 5 % pires ». Chekhlov, Uryasev et
    Zabarankin notent au contraire :math:`\\alpha` le niveau de confiance, si
    bien que leur :math:`CDaR_{0,95}` est notre ``alpha = 0,05``. Les deux
    lectures se croisent et la confusion inverse la mesure, donc elle est
    déclarée ici plutôt que supposée connue.

    **Hypothèses.** L'estimation est empirique et non paramétrique : elle ne
    suppose aucune loi. Elle suppose en revanche que les drawdowns observés sont
    représentatifs, ce qui est fort, puisqu'ils sont fortement autocorrélés par
    construction. Le nombre d'observations INDÉPENDANTES est de l'ordre du
    nombre d'épisodes, pas du nombre de périodes.

    **Provenance.** Chekhlov, Uryasev et Zabarankin (2005), « Drawdown measure
    in portfolio optimization », *International Journal of Theoretical and
    Applied Finance*, 8(1), 13-58. La forme empirique à poids fractionnaire vient
    d'ailleurs. C'est celle de la valeur à risque conditionnelle de Rockafellar
    et Uryasev (2000), « Optimization of conditional value-at-risk », *Journal
    of Risk*, 2(3), 21-41, appliquée ici à la série des drawdowns.

    **Limites.** À ``alpha`` petit et échantillon court, la mesure retombe sur
    une poignée d'observations et retrouve l'instabilité du maximum. Elle hérite
    aussi de la dépendance à la fréquence d'échantillonnage.

    **Alternatives.** Le drawdown maximal, cas limite quand ``alpha`` tend vers
    zéro. L'indice de peine, cas limite quand ``alpha`` vaut 1. L'indice
    d'ulcère, qui pondère par le carré au lieu de tronquer.

    **Pourquoi cette méthode ici.** C'est la seule mesure de drawdown convexe en
    les poids du portefeuille, donc la seule directement optimisable par
    programmation linéaire, ce que Chekhlov, Uryasev et Zabarankin établissent.

    **Comment vérifier.** Deux identités bornent l'implémentation, et le module
    de tests les porte toutes les deux. Quand :math:`\\alpha T \\le 1`, la
    fonction rend exactement le drawdown maximal. Quand :math:`\\alpha = 1`,
    elle rend l'opposé de l'indice de peine.

    Args:
        returns_or_wealth: rendements simples, ou richesse si ``is_wealth``.
        alpha: la fraction de queue moyennée, dans ``]0, 1]``. Valeur par
            défaut 0,05, soit les 5 % pires drawdowns, convention la plus
            répandue dans la littérature de risque.
        is_wealth: ``True`` quand la série est une richesse cumulée.

    Returns:
        Un nombre négatif ou nul, en fraction du sommet.

    Raises:
        ValueError: si ``alpha`` sort de ``]0, 1]``.

    Example:
        >>> import pandas as pd
        >>> wealth = pd.Series([100.0, 120.0, 90.0, 110.0, 150.0])
        >>> round(conditional_drawdown_at_risk(wealth, alpha=0.4, is_wealth=True), 6)
        -0.166667
    """
    if not 0.0 < alpha <= 1.0:
        raise ValueError("alpha doit être dans ]0, 1]")
    drawdown = drawdown_series(returns_or_wealth, is_wealth).to_numpy(dtype="float64")
    losses = np.sort(-drawdown)[::-1]
    n = losses.size
    weight_total = alpha * n
    m = int(np.floor(weight_total))
    if m >= n:
        return float(-losses.mean())
    tail = losses[:m].sum() + (weight_total - m) * losses[m]
    return float(-tail / weight_total)

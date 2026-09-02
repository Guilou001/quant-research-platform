r"""La mise à l'échelle transversale d'un signal, et pourquoi elle décide du portefeuille.

**Le problème.** Un modèle rend un nombre par actif et par date. Ce nombre n'est
pas un poids. Il n'a ni unité stable, ni moyenne nulle, ni somme bornée. Le
rendement attendu sorti d'une régression vaut 0,004 par mois, celui sorti d'un
tri de momentum vaut 12 en pourcentage annuel, et les deux ordonnent le même
univers. Passer de l'un à l'autre demande trois décisions : comment comparer
deux actifs à la même date, que faire des valeurs extrêmes, et quelle exposition
brute viser. Chacune change le portefeuille.

**La doctrine du module.** Un signal n'est pas un portefeuille. La conversion
est un choix déclaré, pas une conséquence automatique du modèle, et
:func:`signal_to_weights` porte ce choix dans sa signature plutôt que dans les
habitudes de celui qui appelle.

**Transversal, jamais temporel.** Toutes les fonctions de ce module travaillent
ligne par ligne sur un panel dont les lignes sont des dates et les colonnes des
actifs. La distinction n'est pas de forme. Standardiser dans le temps compare un
actif à son propre passé, et la moyenne employée contient alors des observations
postérieures à la date traitée, sauf à borner explicitement la fenêtre. C'est la
faute que :mod:`quantlab.validation` cherche ensuite en vain, parce qu'elle est
déjà dans les données. Standardiser en transversal compare les actifs entre eux
à une date donnée, avec la seule information de cette date, et le problème ne se
pose pas.

**Ce que chaque transformation garde et ce qu'elle jette.**

- Le z-score garde l'ordre et les distances relatives, il jette l'échelle. Un
  signal deux fois plus dispersé rend le même z-score.
- Le rang garde l'ordre seul. Il jette la distance, donc la conviction.
- L'écrêtage garde tout sauf les extrêmes, qu'il ramène à une borne mesurée sur
  la coupe elle-même.
- Le z-score robuste garde l'ordre et les distances, mais mesure le centre et la
  dispersion sur la médiane, que quelques valeurs extrêmes ne déplacent pas.

**Provenance.** La conversion d'un score en rendement attendu suit Grinold et
Kahn (2000), *Active Portfolio Management*, 2e édition. Leur règle approximative
écrit l'alpha comme le produit de trois termes : le coefficient d'information,
la volatilité résiduelle et le score standardisé. Le z-score est donc l'échelle
naturelle du passage au portefeuille, et non un choix esthétique. Qian, Hua et
Sorensen (2007), *Quantitative Equity Portfolio Management*, chapitre 3,
détaillent la standardisation transversale et la neutralisation sectorielle.
L'écrêtage porte le nom de Charles P. Winsor et se lit dans Dixon (1960),
« Simplified estimation from censored normal samples », *Annals of Mathematical
Statistics* 31(2), 385-391. Le facteur 1,4826 de l'écart absolu médian vient de
Hampel (1974), repris par Rousseeuw et Croux (1993), « Alternatives to the
median absolute deviation », *Journal of the American Statistical Association*
88(424), 1273-1283. Statut de ces quatre références : rapporté.

**Convention des valeurs manquantes.** Dans un panel de signal, ``NaN`` veut
dire que l'actif n'est pas dans l'univers à cette date. Il ressort ``NaN``, il
n'est jamais comblé, et il ne compte pas dans les statistiques de la ligne. Dans
un vecteur de poids, au contraire, ``NaN`` est refusé : un portefeuille dont un
poids est inconnu n'est pas un portefeuille. La frontière entre les deux
conventions est :func:`signal_to_weights`, qui rend zéro pour un actif hors
univers d'une date par ailleurs exploitable, et une ligne entièrement ``NaN``
pour une date dont l'univers est trop mince.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Literal

import numpy as np
import pandas as pd

from quantlab.core.errors import (
    ConfigError,
    DataQualityError,
    InsufficientDataError,
    LookAheadError,
)
from quantlab.core.types import WeightFrame, Weights

__all__ = [
    "DEFAULT_LOWER_QUANTILE",
    "DEFAULT_MIN_GROUP_NAMES",
    "DEFAULT_MIN_NAMES",
    "DEFAULT_RANK_SCALE",
    "DEFAULT_TARGET_GROSS",
    "DEFAULT_UPPER_QUANTILE",
    "MAD_SCALE",
    "MIN_DISPERSION",
    "MIN_RELATIVE_DISPERSION",
    "RankMethod",
    "SignalCrossSection",
    "SignalPanel",
    "WeightingMethod",
    "WinsorAxis",
    "cross_sectional_rank",
    "cross_sectional_zscore",
    "demean_by_group",
    "neutralize_to_zero_net",
    "robust_zscore",
    "scale_to_gross",
    "scale_to_net",
    "signal_to_weights",
    "winsorize",
]

#: Un panel de signal : lignes = dates, colonnes = actifs.
type SignalPanel = pd.DataFrame
#: Une coupe transversale de signal à une date, indexée par actif.
type SignalCrossSection = pd.Series

#: Les méthodes de rang acceptées, celles de ``pandas.DataFrame.rank``. La
#: méthode ``dense`` est volontairement absente : elle compte les valeurs
#: distinctes, si bien que le rang maximal d'une ligne n'est plus le nombre
#: d'actifs et que la mise à l'échelle linéaire ne remplirait plus l'intervalle
#: demandé.
type RankMethod = Literal["average", "min", "max", "first"]

#: Les deux axes possibles d'un écrêtage. ``cross_section`` écrête ligne par
#: ligne, donc date par date ; ``time`` écrête colonne par colonne, donc actif
#: par actif, ce qui regarde le passé et le futur du même actif.
type WinsorAxis = Literal["cross_section", "time"]

#: Nombre minimal d'actifs sous lequel une statistique transversale ne veut rien
#: dire. Cinq est un plancher déclaré, pas une mesure. Mesuré, par l'inégalité
#: de Samuelson (1968) : un z-score calculé sur n noms est borné en valeur
#: absolue par (n-1)/racine(n), soit 1,79 pour cinq noms et 3,00 pour dix.
DEFAULT_MIN_NAMES = 5

#: Nombre minimal d'actifs par groupe dans :func:`demean_by_group`. Un vaut
#: « aucun filtrage » et laisse passer les groupes singletons, dont le signal
#: devient mécaniquement nul.
DEFAULT_MIN_GROUP_NAMES = 1

#: Quantile bas de l'écrêtage par défaut, soit un pour cent.
DEFAULT_LOWER_QUANTILE = 0.01

#: Quantile haut de l'écrêtage par défaut, soit quatre-vingt-dix-neuf pour cent.
DEFAULT_UPPER_QUANTILE = 0.99

#: Intervalle de sortie du rang normalisé. Le choix symétrique autour de zéro
#: donne une coupe de moyenne nulle quand les rangs sont moyennés.
DEFAULT_RANK_SCALE = (-1.0, 1.0)

#: Exposition brute visée par défaut, soit un dollar investi par dollar de
#: capital, achats et ventes confondus.
DEFAULT_TARGET_GROSS = 1.0

#: Facteur de cohérence de l'écart absolu médian. Il vaut l'inverse du quantile
#: à 75 % de la loi normale centrée réduite, soit 1 / 0,67449 = 1,48260 à cinq
#: décimales. Sous une loi normale, l'écart absolu médian multiplié par ce
#: facteur estime l'écart type. La valeur est écrite en dur ici et vérifiée
#: contre ``scipy.stats.norm.ppf`` dans les tests, pour que le module ne dépende
#: pas de SciPy à l'exécution.
MAD_SCALE = 1.4826022185056018

#: Seuil absolu employé sur une grandeur DÉJÀ normalisée, dont l'échelle vaut
#: un par construction : la moyenne des scores de :func:`signal_to_weights`,
#: qui vivent entre -1 et 1 en rang et autour de l'unité en z-score. Il ne sert
#: jamais à juger la dispersion d'un signal brut, dont l'unité est inconnue.
MIN_DISPERSION = 1e-12

#: Dispersion RELATIVE sous laquelle une coupe est tenue pour constante. Le
#: seuil se rapporte à l'échelle de la coupe, mesurée par sa plus grande valeur
#: absolue. La raison tient en une phrase : le z-score et le rang sont
#: invariants par changement d'unité, donc leur garde doit l'être aussi. Un
#: seuil absolu de 1e-12 rend ``NaN`` sur un signal exprimé en 1e-13, alors que
#: le même signal multiplié par mille passe, ce qui fait dépendre le
#: portefeuille du choix de l'unité. Mesuré : sur les entiers de 1 à 10
#: multipliés par 1e-13, la version à seuil absolu rendait dix ``NaN`` là où la
#: version relative rend les mêmes z-scores qu'à l'échelle unité.
MIN_RELATIVE_DISPERSION = 1e-12


class WeightingMethod(StrEnum):
    """Les trois façons de convertir une coupe de signal en poids.

    Chacune suppose autre chose sur ce que le signal mesure, et le choix se
    justifie dans la docstring de :func:`signal_to_weights`.
    """

    RANK = "rank"
    ZSCORE = "zscore"
    EQUAL_LONG_SHORT = "equal_long_short"


#: Les valeurs acceptées pour l'argument ``method`` du rang.
_RANK_METHODS: tuple[str, ...] = ("average", "min", "max", "first")

#: Les valeurs acceptées pour l'argument ``axis`` de l'écrêtage.
_WINSOR_AXES: tuple[str, ...] = ("cross_section", "time")


def _validated_panel(panel: pd.DataFrame, *, label: str = "panel") -> pd.DataFrame:
    """Rend le panel converti en flottants, après quatre refus explicites.

    Args:
        panel: le tableau à contrôler, lignes = dates, colonnes = actifs.
        label: le nom employé dans les messages d'erreur.

    Returns:
        Une copie du panel en ``float64``.

    Raises:
        ConfigError: si l'objet n'est pas un ``DataFrame``, ou si une colonne
            n'est pas convertible en nombre.
        DataQualityError: si un actif ou une date apparaît deux fois, ou si une
            valeur infinie est présente.
    """
    if not isinstance(panel, pd.DataFrame):
        raise ConfigError(f"{label} doit être un DataFrame dates x actifs, pas un {type(panel).__name__}")
    if panel.columns.has_duplicates:
        doublons = panel.columns[panel.columns.duplicated()].tolist()
        raise DataQualityError(f"{label} porte des actifs en double : {doublons}")
    if panel.index.has_duplicates:
        doublons = panel.index[panel.index.duplicated()].tolist()
        raise DataQualityError(f"{label} porte des dates en double : {doublons}")
    try:
        converti = panel.astype(float)
    except (TypeError, ValueError) as erreur:
        raise ConfigError(f"{label} porte une colonne non numérique : {erreur}") from erreur
    valeurs = converti.to_numpy(dtype=float)
    if valeurs.size and bool(np.isinf(valeurs).any()):
        raise DataQualityError(
            f"{label} porte des valeurs infinies. Un signal infini se borne en amont, "
            "sans quoi toute statistique de la coupe devient infinie."
        )
    return converti


def _validated_weights(weights: pd.Series, *, label: str = "weights") -> pd.Series:
    """Rend le vecteur de poids en flottants, après trois refus explicites.

    Args:
        weights: les poids, indexés par actif.
        label: le nom employé dans les messages d'erreur.

    Returns:
        Une copie des poids en ``float64``.

    Raises:
        ConfigError: si l'objet n'est pas une ``Series`` ou n'est pas numérique.
        DataQualityError: si un actif apparaît deux fois, ou si un poids est
            manquant ou infini.
        InsufficientDataError: si le vecteur est vide.
    """
    if not isinstance(weights, pd.Series):
        raise ConfigError(f"{label} doit être une Series indexée par actif, pas un {type(weights).__name__}")
    if weights.index.has_duplicates:
        doublons = weights.index[weights.index.duplicated()].tolist()
        raise DataQualityError(f"{label} porte des actifs en double : {doublons}")
    if len(weights) == 0:
        raise InsufficientDataError(f"{label} est vide : un portefeuille sans actif n'a pas d'exposition")
    try:
        converti = weights.astype(float)
    except (TypeError, ValueError) as erreur:
        raise ConfigError(f"{label} n'est pas numérique : {erreur}") from erreur
    valeurs = converti.to_numpy(dtype=float)
    if not bool(np.isfinite(valeurs).all()):
        raise DataQualityError(
            f"{label} porte un poids manquant ou infini. Un poids inconnu n'est pas un poids : "
            "il se comble en amont, par zéro si l'actif n'est pas détenu."
        )
    return converti


def _validated_cross_section(signal: pd.Series, *, label: str = "signal") -> pd.Series:
    """Rend une coupe de signal en flottants, les valeurs manquantes conservées.

    La différence avec :func:`_validated_weights` tient à une seule règle : un
    signal manquant est licite, il dit que l'actif n'est pas dans l'univers.

    Args:
        signal: la coupe, indexée par actif.
        label: le nom employé dans les messages d'erreur.

    Returns:
        Une copie de la coupe en ``float64``.

    Raises:
        ConfigError: si l'objet n'est pas une ``Series`` numérique.
        DataQualityError: si un actif apparaît deux fois, ou si une valeur est
            infinie.
    """
    if not isinstance(signal, pd.Series):
        raise ConfigError(f"{label} doit être une Series indexée par actif, pas un {type(signal).__name__}")
    if signal.index.has_duplicates:
        doublons = signal.index[signal.index.duplicated()].tolist()
        raise DataQualityError(f"{label} porte des actifs en double : {doublons}")
    try:
        converti = signal.astype(float)
    except (TypeError, ValueError) as erreur:
        raise ConfigError(f"{label} n'est pas numérique : {erreur}") from erreur
    valeurs = converti.to_numpy(dtype=float)
    if valeurs.size and bool(np.isinf(valeurs).any()):
        raise DataQualityError(f"{label} porte des valeurs infinies, qu'aucune statistique ne supporte")
    return converti


def _checked_min_names(min_names: int, *, floor: int = 2) -> int:
    """Rend ``min_names`` après avoir vérifié qu'il atteint le plancher.

    Args:
        min_names: le nombre d'actifs exigé.
        floor: le plancher sous lequel la statistique n'est pas définie.

    Returns:
        La valeur validée.

    Raises:
        ConfigError: si ``min_names`` est sous le plancher.
    """
    if int(min_names) < floor:
        raise ConfigError(
            f"min_names doit valoir au moins {floor}, la statistique n'étant pas définie en deçà"
        )
    return int(min_names)


def _row_counts(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Rend le masque des valeurs présentes et le compte par ligne.

    Args:
        values: le tableau à deux dimensions, lignes = dates.

    Returns:
        Le masque booléen des valeurs finies, et le nombre de valeurs finies par
        ligne.
    """
    presentes = np.isfinite(values)
    return presentes, presentes.sum(axis=1)


def _dispersion_floor(values: np.ndarray) -> np.ndarray:
    """Rend le plancher de dispersion de chaque ligne, à l'échelle de la ligne.

    L'échelle d'une coupe est sa plus grande valeur absolue. Une coupe
    entièrement nulle ou vide reçoit un plancher nul, si bien qu'une dispersion
    strictement positive reste acceptée quelle que soit sa petitesse.

    Args:
        values: le tableau à deux dimensions, lignes = dates.

    Returns:
        Un plancher par ligne, proportionnel à :data:`MIN_RELATIVE_DISPERSION`.
    """
    finies = np.where(np.isfinite(values), np.abs(values), 0.0)
    echelles = finies.max(axis=1) if finies.shape[1] else np.zeros(finies.shape[0])
    return MIN_RELATIVE_DISPERSION * echelles


def _rebuild(values: np.ndarray, model: pd.DataFrame) -> pd.DataFrame:
    """Rend un ``DataFrame`` portant l'index et les colonnes du panel d'origine.

    Args:
        values: le tableau calculé.
        model: le panel d'origine, dont l'index et les colonnes sont repris.

    Returns:
        Le tableau habillé.
    """
    return pd.DataFrame(values, index=model.index, columns=model.columns, dtype=float)


def _ranks_1d(values: np.ndarray, method: str) -> np.ndarray:
    """Rend les rangs d'un vecteur sans valeur manquante, de 1 à sa longueur.

    Args:
        values: le vecteur de signal, toutes valeurs présentes.
        method: la règle de départage des ex aequo.

    Returns:
        Les rangs, le plus petit signal recevant le rang 1.
    """
    return pd.Series(values).rank(method=method).to_numpy(dtype=float)


def cross_sectional_zscore(
    panel: SignalPanel,
    *,
    min_names: int = DEFAULT_MIN_NAMES,
    ddof: int = 1,
) -> SignalPanel:
    r"""Rend le signal centré et réduit à l'intérieur de chaque date.

    **Le problème.** Deux signaux qui ordonnent le même univers n'ont ni la même
    unité ni la même dispersion. Les additionner, les comparer d'un mois à
    l'autre ou les convertir en poids exige d'abord une échelle commune.

    **L'intuition.** À chaque date, on retire la moyenne de la coupe et on divise
    par sa dispersion. Le résultat se lit en écarts types transversaux : un
    z-score de +2 dit que l'actif est deux dispersions au-dessus de la moyenne
    des actifs du jour, quelle que soit l'unité de départ.

    .. math::

        z_{i,t} = \frac{x_{i,t} - \bar{x}_t}{s_t},
        \qquad
        \bar{x}_t = \frac{1}{n_t}\sum_{j \in \mathcal{U}_t} x_{j,t},
        \qquad
        s_t^2 = \frac{1}{n_t - \nu}\sum_{j \in \mathcal{U}_t} (x_{j,t} - \bar{x}_t)^2

    Définition de chaque variable :

    - :math:`x_{i,t}` la valeur brute du signal sur l'actif :math:`i` à la date
      :math:`t` ;
    - :math:`\mathcal{U}_t` l'univers des actifs renseignés à cette date, et
      :math:`n_t` son cardinal ;
    - :math:`\bar{x}_t` la moyenne transversale, calculée sur cette seule date ;
    - :math:`s_t` la dispersion transversale de cette seule date ;
    - :math:`\nu` le degré de liberté retiré, l'argument ``ddof``.

    **Ce que la transformation préserve.** L'ordre, exactement. La division par
    une dispersion strictement positive est une transformation croissante, donc
    le classement des actifs est intact et le coefficient d'information de rang
    ne bouge pas d'un millième. Les distances relatives survivent aussi : le
    rapport entre deux écarts au centre est le même avant et après.

    **Ce qu'elle détruit.** L'échelle, donc l'information de niveau. Une date où
    tous les actifs sont attirants et une date où aucun ne l'est rendent la même
    coupe de z-scores, puisque la moyenne est retirée dans les deux cas. Un
    portefeuille construit sur des z-scores est donc toujours pleinement
    investi, y compris le jour où le signal ne voit rien. C'est le prix de la
    comparabilité, et il se paie en risque de marché non voulu.

    **Hypothèses.** La dispersion transversale existe, donc la coupe n'est pas
    constante. Les actifs de la ligne sont comparables entre eux, ce que la
    neutralisation sectorielle de :func:`demean_by_group` sert à obtenir quand
    ils ne le sont pas.

    **Provenance.** La standardisation transversale est la forme employée par
    Grinold et Kahn (2000) dans la règle approximative de l'alpha, et détaillée
    par Qian, Hua et Sorensen (2007), chapitre 3. Statut : rapporté.

    **Limites.** La moyenne et l'écart type sont les deux statistiques les plus
    sensibles aux valeurs extrêmes. Un seul actif aberrant déplace le centre de
    toute la coupe et gonfle la dispersion, ce qui écrase les z-scores de tous
    les autres. Écrêter avant de standardiser est la parade usuelle, et
    :func:`winsorize` la fournit. Le z-score suppose aussi une distribution
    à peu près symétrique, ce que les signaux de valorisation ne sont pas.

    **Alternatives.** :func:`robust_zscore` remplace la moyenne par la médiane et
    l'écart type par l'écart absolu médian. :func:`cross_sectional_rank` ignore
    les niveaux et ne garde que l'ordre.

    **Pourquoi cette méthode ici.** C'est l'échelle que suppose la règle
    approximative de l'alpha, qui multiplie le score standardisé par le
    coefficient d'information et par la volatilité résiduelle. Utiliser des
    rangs à cet endroit changerait l'unité du résultat sans le dire.

    **Comment vérifier.** Sur une ligne complète, la moyenne des z-scores vaut
    zéro et leur écart type d'échantillon vaut un, à la précision machine. Une
    transformation affine croissante du signal doit laisser le résultat
    inchangé, y compris quand le facteur vaut 1e-13. Le plancher de dispersion
    est en effet relatif à l'échelle de la coupe. Sans cela, le choix de l'unité
    déciderait du portefeuille. Les contrôles sont dans
    ``tests/unit/test_signals_standardize.py``.

    Args:
        panel: le signal brut, lignes = dates, colonnes = actifs. Un ``NaN``
            signale un actif hors univers à cette date.
        min_names: le nombre d'actifs renseignés sous lequel la ligne entière
            rend ``NaN``. Défaut cinq, plancher déclaré.
        ddof: le degré de liberté retiré au dénominateur de la variance. Un par
            défaut, soit la variance d'échantillon.

    Returns:
        Un panel de même forme, en écarts types transversaux. Une ligne rend
        ``NaN`` si elle porte moins de ``min_names`` actifs, ou si sa dispersion
        est sous :data:`MIN_DISPERSION`.

    Raises:
        ConfigError: si ``min_names`` est inférieur à deux, ou si ``ddof`` est
            négatif.
        DataQualityError: si le panel porte un doublon ou une valeur infinie.

    Example:
        >>> import pandas as pd
        >>> panel = pd.DataFrame([[1.0, 2.0, 3.0, 4.0, 5.0]], columns=list("abcde"))
        >>> round(float(cross_sectional_zscore(panel).iloc[0, 0]), 6)
        -1.264911
    """
    if ddof < 0:
        raise ConfigError("ddof doit être positif ou nul")
    seuil = _checked_min_names(min_names, floor=max(2, ddof + 1))
    valide = _validated_panel(panel)
    valeurs = valide.to_numpy(dtype=float)
    if valeurs.size == 0:
        return _rebuild(valeurs, valide)
    presentes, comptes = _row_counts(valeurs)
    remplies = np.where(presentes, valeurs, 0.0)
    denominateur = np.maximum(comptes, 1)
    moyennes = remplies.sum(axis=1) / denominateur
    ecarts = np.where(presentes, valeurs - moyennes[:, None], 0.0)
    variances = (ecarts**2).sum(axis=1) / np.maximum(comptes - ddof, 1)
    dispersions = np.sqrt(variances)
    exploitable = (comptes >= seuil) & (dispersions > _dispersion_floor(valeurs))
    dispersions = np.where(exploitable, dispersions, np.nan)
    centres = np.where(exploitable, moyennes, np.nan)
    return _rebuild((valeurs - centres[:, None]) / dispersions[:, None], valide)


def cross_sectional_rank(
    panel: SignalPanel,
    *,
    min_names: int = DEFAULT_MIN_NAMES,
    method: RankMethod = "average",
    scale: tuple[float, float] = DEFAULT_RANK_SCALE,
) -> SignalPanel:
    r"""Rend le rang du signal dans sa date, ramené à l'intervalle demandé.

    **Le problème.** Le z-score suppose que les niveaux veulent dire quelque
    chose. Beaucoup de signaux n'ont de sens que par leur ordre, et leurs
    niveaux sont pollués par des valeurs extrêmes qu'aucune théorie ne justifie.

    **L'intuition.** On classe les actifs de la date, du pire au meilleur, puis
    on étire ce classement sur l'intervalle voulu. Le plus mauvais reçoit la
    borne basse, le meilleur la borne haute, et les autres se répartissent
    régulièrement entre les deux.

    .. math::

        \rho_{i,t} = a + (b - a)\,\frac{r_{i,t} - 1}{n_t - 1}

    Définition de chaque variable :

    - :math:`r_{i,t}` le rang de l'actif dans sa date, de 1 pour le signal le
      plus faible à :math:`n_t` pour le plus fort, les ex aequo recevant le rang
      moyen par défaut ;
    - :math:`n_t` le nombre d'actifs renseignés à la date ;
    - :math:`a` et :math:`b` les bornes de l'intervalle demandé.

    **Pourquoi le rang résiste aux valeurs extrêmes.** Une observation aberrante
    ne peut déplacer un rang que d'une position à la fois, quelle que soit son
    ampleur. Multiplier par mille le signal du meilleur actif ne change rien au
    résultat, alors que la même opération déplace la moyenne et l'écart type de
    la coupe, donc les z-scores de tous les actifs. Le rang borne l'influence
    d'une seule observation par construction, sans seuil à calibrer.

    **Ce que le rang coûte.** Il jette l'information de distance. Un actif deux
    fois plus attirant que son voisin reçoit le même écart de rang qu'un actif à
    peine meilleur, soit une unité. Sur un signal dont la distribution est très
    asymétrique, où le premier décile porte l'essentiel de la prime, cette perte
    est chère : le portefeuille achète le dixième meilleur actif presque autant
    que le meilleur. C'est la même perte que subit le coefficient d'information
    de Spearman, décrite dans :mod:`quantlab.analytics.ic`.

    **Hypothèses.** Les ex aequo se départagent par la méthode demandée. Le
    défaut ``average`` conserve la somme des rangs, donc une moyenne exactement
    au milieu de l'intervalle, ce dont :func:`signal_to_weights` a besoin pour
    rendre une somme nulle.

    **Provenance.** Le tri par rangs est la construction de portefeuille de
    Jegadeesh et Titman (1993) et de Fama et French (1993). La normalisation
    linéaire du rang est décrite par Qian, Hua et Sorensen (2007), chapitre 3.
    Statut : rapporté.

    **Limites.** Une coupe constante rend la borne médiane pour tous les actifs,
    et non ``NaN`` : le rang moyen est défini même sans ordre. Le résultat est
    alors inutilisable comme signal, ce que :func:`signal_to_weights` détecte à
    son tour. Le rang dépend aussi du nombre d'actifs : la même position
    absolue rend un nombre différent selon que l'univers en porte cinquante ou
    cinq cents.

    **Alternatives.** :func:`cross_sectional_zscore` garde les distances.
    Une transformation des rangs par la fonction quantile normale, dite score
    normal, rend une coupe gaussienne et redonne du poids aux extrémités.

    **Pourquoi cette méthode ici.** Sur des signaux de valorisation, dont les
    dénominateurs approchent zéro et créent des valeurs aberrantes sans
    signification économique, le rang est la seule échelle qui ne demande aucun
    écrêtage arbitraire.

    **Comment vérifier.** Toute transformation strictement croissante du signal
    laisse le résultat inchangé, à l'identique et non à une tolérance près. Sur
    une ligne sans ex aequo, le minimum vaut ``a`` et le maximum vaut ``b``. Les
    deux contrôles sont dans ``tests/unit/test_signals_standardize.py``.

    Args:
        panel: le signal brut, lignes = dates, colonnes = actifs.
        min_names: le nombre d'actifs sous lequel la ligne rend ``NaN``.
        method: la règle de départage des ex aequo, parmi ``average``, ``min``,
            ``max`` et ``first``. ``first`` départage par l'ordre des colonnes.
        scale: les bornes de l'intervalle de sortie, la basse d'abord.

    Returns:
        Un panel de même forme, à valeurs dans l'intervalle demandé.

    Raises:
        ConfigError: si ``min_names`` est inférieur à deux, si la méthode est
            inconnue, ou si les bornes ne sont pas strictement croissantes.
        DataQualityError: si le panel porte un doublon ou une valeur infinie.
    """
    if method not in _RANK_METHODS:
        raise ConfigError(f"method doit valoir l'un de {_RANK_METHODS}, reçu {method!r}")
    if len(scale) != 2:
        raise ConfigError("scale doit porter exactement deux bornes")
    borne_basse, borne_haute = float(scale[0]), float(scale[1])
    if not borne_basse < borne_haute:
        raise ConfigError(f"scale doit être strictement croissant, reçu ({borne_basse}, {borne_haute})")
    seuil = _checked_min_names(min_names, floor=2)
    valide = _validated_panel(panel)
    valeurs = valide.to_numpy(dtype=float)
    if valeurs.size == 0:
        return _rebuild(valeurs, valide)
    _, comptes = _row_counts(valeurs)
    rangs = valide.rank(axis=1, method=method).to_numpy(dtype=float)
    exploitable = comptes >= seuil
    etendue = np.where(exploitable, np.maximum(comptes - 1, 1), np.nan)
    return _rebuild(borne_basse + (borne_haute - borne_basse) * (rangs - 1.0) / etendue[:, None], valide)


def winsorize(
    panel: SignalPanel,
    *,
    lower: float = DEFAULT_LOWER_QUANTILE,
    upper: float = DEFAULT_UPPER_QUANTILE,
    axis: WinsorAxis = "cross_section",
    allow_lookahead: bool = False,
) -> SignalPanel:
    r"""Ramène les valeurs extrêmes aux quantiles demandés, sans rien supprimer.

    **Le problème.** Un signal porte des valeurs aberrantes. Un rapport
    cours-bénéfice dont le dénominateur approche zéro rend un nombre immense qui
    ne dit rien de l'entreprise. Laissé tel quel, il capture à lui seul la
    moyenne et l'écart type de la coupe, donc le portefeuille.

    **L'intuition.** On mesure deux bornes sur la coupe elle-même, par exemple
    ses quantiles à 1 % et 99 %, puis on ramène à ces bornes tout ce qui les
    dépasse. L'actif reste dans l'univers, avec une valeur crédible.

    .. math::

        \tilde{x}_{i,t} = \min\big(\max(x_{i,t}, q_{\alpha,t}), q_{\beta,t}\big)

    Définition de chaque variable :

    - :math:`q_{\alpha,t}` le quantile de niveau :math:`\alpha` de la coupe à la
      date :math:`t`, interpolé linéairement entre les deux statistiques d'ordre
      qui l'encadrent ;
    - :math:`q_{\beta,t}` le quantile haut de la même coupe ;
    - :math:`\tilde{x}_{i,t}` la valeur écrêtée.

    **L'axe du temps est refusé par défaut.** L'écrêtage sur l'axe ``time``
    mesure ses bornes sur l'histoire entière de l'actif. Il exige donc un aveu
    explicite, faute de quoi il lève :class:`LookAheadError`.

    **L'écrêtage contre la troncature.** La troncature supprime l'observation,
    l'écrêtage la garde en la bornant. La différence n'est pas cosmétique. Une
    troncature change le nombre d'actifs de la date, donc l'univers, donc le
    dénominateur de toutes les statistiques transversales qui suivent. Elle
    interdit aussi de détenir un actif qui, lui, existe toujours dans le
    portefeuille réel. Un gérant qui tronque se retrouve avec une position dont
    le signal a disparu, et il doit inventer une règle pour la traiter.
    L'écrêtage évite ce trou : l'univers est stable et chaque actif garde un
    signal.

    **Hypothèses.** La valeur extrême est un défaut de mesure ou un cas
    particulier, non l'information elle-même. C'est faux pour un signal de
    détresse financière, où l'extrême est précisément le sujet. Le seuil est
    déclaré par l'appelant plutôt que deviné.

    **Provenance.** L'écrêtage porte le nom de Charles P. Winsor et se lit dans
    Dixon (1960), « Simplified estimation from censored normal samples »,
    *Annals of Mathematical Statistics* 31(2), 385-391. Tukey (1962), « The
    future of data analysis », *Annals of Mathematical Statistics* 33(1), 1-67,
    en fait un des gestes de base de l'analyse robuste. Statut : rapporté.

    **Limites, et une limite mesurable.** Le nombre d'actifs décide de l'effet
    réel du seuil. Mesuré par l'arithmétique de l'interpolation linéaire : le
    quantile bas de niveau :math:`\alpha` tombe entre la première et la deuxième
    valeur ordonnée tant que :math:`\alpha (n-1) < 1`. Pour un seuil à 1 %, cela
    vaut jusqu'à cent noms. Sur un univers de cent actifs, l'écrêtage à 1 % ne
    touche donc qu'une seule valeur par queue, et il ne la remonte même pas
    jusqu'à la deuxième. Annoncer « nous écrêtons à 1 % » sur un univers mince
    revient à ne presque rien faire. L'écrêtage biaise par ailleurs toute
    statistique de queue, et une variance calculée après écrêtage est trop
    petite.

    **Alternatives.** La troncature, décrite plus haut. Une transformation par
    les rangs, qui rend l'écrêtage inutile. Un estimateur robuste, qui laisse les
    données intactes et change la statistique, ce que fait
    :func:`robust_zscore`.

    **Pourquoi cette méthode ici.** L'écrêtage garde l'univers constant, ce dont
    dépendent la rotation mesurée et l'attribution qui suivent dans le pipeline.

    **Comment vérifier.** Sur une ligne connue, les bornes doivent coïncider avec
    ``numpy.nanquantile`` en interpolation linéaire, et les valeurs intérieures
    doivent être inchangées à l'identique. Le contrôle est dans
    ``tests/unit/test_signals_standardize.py``.

    Args:
        panel: le signal brut, lignes = dates, colonnes = actifs.
        lower: le niveau du quantile bas, entre zéro et un.
        upper: le niveau du quantile haut, strictement supérieur à ``lower``.
        axis: ``cross_section`` écrête date par date, ``time`` écrête actif par
            actif sur toute l'histoire.
        allow_lookahead: l'aveu exigé par l'axe ``time``, qui lit le futur de
            chaque date. Sans lui, cet axe lève :class:`LookAheadError`.

    Returns:
        Un panel de même forme, valeurs extrêmes ramenées aux bornes.

    Raises:
        ConfigError: si les niveaux sortent de l'intervalle unité, s'ils ne sont
            pas strictement ordonnés, ou si l'axe est inconnu.
        DataQualityError: si le panel porte un doublon ou une valeur infinie.
        LookAheadError: si l'axe ``time`` est demandé sans ``allow_lookahead``.
    """
    if axis not in _WINSOR_AXES:
        raise ConfigError(f"axis doit valoir l'un de {_WINSOR_AXES}, reçu {axis!r}")
    if axis == "time" and not allow_lookahead:
        raise LookAheadError(
            "l'axe time mesure ses bornes sur l'histoire entière de l'actif, donc sur des dates "
            "postérieures à celle qu'il écrête. Mesuré : sur la colonne dont les deux valeurs sont "
            "5 puis 50, le quantile bas à 10 % vaut 9,5 et remonte la première date de 5 à 9,5 ; "
            "remplacer la seconde valeur par un million porte cette même première date à 100 004,5. "
            "Passer allow_lookahead=True pour décrire un échantillon, jamais dans un backtest."
        )
    if not 0.0 <= lower < upper <= 1.0:
        raise ConfigError(f"les niveaux doivent vérifier 0 <= lower < upper <= 1, reçu ({lower}, {upper})")
    valide = _validated_panel(panel)
    valeurs = valide.to_numpy(dtype=float)
    if valeurs.size == 0:
        return _rebuild(valeurs, valide)
    travail = valeurs if axis == "cross_section" else valeurs.T
    _, comptes = _row_counts(travail)
    basses = np.full(travail.shape[0], np.nan)
    hautes = np.full(travail.shape[0], np.nan)
    lignes = np.flatnonzero(comptes > 0)
    if lignes.size:
        bloc = travail[lignes]
        basses[lignes] = np.nanquantile(bloc, lower, axis=1)
        hautes[lignes] = np.nanquantile(bloc, upper, axis=1)
    ecrete = np.clip(travail, basses[:, None], hautes[:, None])
    return _rebuild(ecrete if axis == "cross_section" else ecrete.T, valide)


def robust_zscore(panel: SignalPanel, *, min_names: int = DEFAULT_MIN_NAMES) -> SignalPanel:
    r"""Rend le signal centré sur la médiane et réduit par l'écart absolu médian.

    **Le problème.** La moyenne et l'écart type sont les deux statistiques que
    déplace le plus facilement une seule observation aberrante. Sur un signal de
    valorisation, une entreprise dont le bénéfice approche zéro suffit à écraser
    les z-scores de tout l'univers.

    **L'intuition.** On remplace la moyenne par la médiane et l'écart type par la
    médiane des écarts à la médiane. Ni l'une ni l'autre ne bouge quand une
    valeur extrême s'éloigne encore. Il reste à remettre le résultat à l'échelle
    d'un écart type, sans quoi les deux mesures ne seraient pas comparables.

    .. math::

        z^{\text{rob}}_{i,t} = \frac{x_{i,t} - m_t}{c \cdot \mathrm{MAD}_t},
        \qquad
        \mathrm{MAD}_t = \operatorname{med}_j \left| x_{j,t} - m_t \right|,
        \qquad
        c = \frac{1}{\Phi^{-1}(0{,}75)}

    Définition de chaque variable :

    - :math:`m_t` la médiane transversale de la date :math:`t` ;
    - :math:`\mathrm{MAD}_t` l'écart absolu médian de la même coupe ;
    - :math:`\Phi^{-1}` la fonction quantile de la loi normale centrée réduite ;
    - :math:`c` le facteur de cohérence, égal à 1,48260 à cinq décimales.

    **D'où vient le facteur 1,48260.** Sous une loi normale d'écart type
    :math:`\sigma`, la moitié des observations tombe à moins de
    :math:`0{,}67449\,\sigma` de la médiane, puisque le quantile à 75 % de la
    loi centrée réduite vaut 0,67449. L'écart absolu médian estime donc
    :math:`0{,}67449\,\sigma` et non :math:`\sigma`. Le multiplier par l'inverse
    de ce nombre, soit 1,48260, redonne un estimateur de l'écart type. La
    constante est écrite en dur dans :data:`MAD_SCALE` et vérifiée contre
    ``1 / scipy.stats.norm.ppf(0.75)`` dans les tests. Statut de la valeur :
    mesuré, par identité avec la fonction quantile de SciPy.

    **Hypothèses.** Le facteur de cohérence ne vaut que sous la loi normale. Sur
    une distribution à queues épaisses, l'écart absolu médian multiplié par
    1,48260 sous-estime l'écart type théorique, ce qui est voulu : c'est la
    dispersion du corps de la distribution que l'on veut mesurer.

    **Provenance.** Hampel (1974), « The influence curve and its role in robust
    estimation », *Journal of the American Statistical Association* 69(346),
    383-393. Rousseeuw et Croux (1993), même revue, 88(424), 1273-1283, donnent
    la constante et discutent des estimateurs plus efficaces. Statut : rapporté.

    **Limites.** L'écart absolu médian vaut zéro dès que plus de la moitié des
    valeurs de la coupe sont identiques, ce qui arrive sur un signal discret ou
    très creux. La ligne rend alors ``NaN`` plutôt qu'une division par presque
    zéro. Le point de rupture de l'estimateur atteint 50 %, contre 0 % pour
    l'écart type. Son efficacité sous la loi normale ne vaut en revanche que
    37 %, soit environ deux fois et demie plus d'observations pour la même
    précision. Statut de ces deux nombres : rapporté, d'après Rousseeuw et Croux
    (1993).

    **Alternatives.** L'écrêtage suivi d'un z-score ordinaire, qui garde
    l'efficacité mais demande un seuil arbitraire. L'estimateur Qn de Rousseeuw
    et Croux, plus efficace et plus coûteux. Le rang, qui abandonne les
    distances.

    **Pourquoi cette méthode ici.** Elle ne demande aucun seuil à calibrer, et
    elle laisse les données intactes : c'est la statistique qui change, pas
    l'échantillon.

    **Comment vérifier.** Sur les valeurs 1, 2, 3, 4 et 5, la médiane vaut 3 et
    l'écart absolu médian vaut 1, si bien que le z-score robuste du 5 vaut
    2 / 1,48260 = 1,34898. Le contrôle est dans
    ``tests/unit/test_signals_standardize.py``.

    Args:
        panel: le signal brut, lignes = dates, colonnes = actifs.
        min_names: le nombre d'actifs sous lequel la ligne rend ``NaN``.

    Returns:
        Un panel de même forme, en écarts types robustes.

    Raises:
        ConfigError: si ``min_names`` est inférieur à deux.
        DataQualityError: si le panel porte un doublon ou une valeur infinie.
    """
    seuil = _checked_min_names(min_names, floor=2)
    valide = _validated_panel(panel)
    valeurs = valide.to_numpy(dtype=float)
    if valeurs.size == 0:
        return _rebuild(valeurs, valide)
    _, comptes = _row_counts(valeurs)
    medianes = np.full(valeurs.shape[0], np.nan)
    dispersions = np.full(valeurs.shape[0], np.nan)
    lignes = np.flatnonzero(comptes >= seuil)
    if lignes.size:
        bloc = valeurs[lignes]
        centre = np.nanmedian(bloc, axis=1)
        medianes[lignes] = centre
        dispersions[lignes] = MAD_SCALE * np.nanmedian(np.abs(bloc - centre[:, None]), axis=1)
    dispersions = np.where(dispersions > _dispersion_floor(valeurs), dispersions, np.nan)
    return _rebuild((valeurs - medianes[:, None]) / dispersions[:, None], valide)


def demean_by_group(
    panel: SignalPanel,
    groups: Mapping[str, str] | pd.Series,
    *,
    min_names: int = DEFAULT_MIN_GROUP_NAMES,
) -> SignalPanel:
    r"""Retire à chaque actif la moyenne de son groupe, date par date.

    **Le problème.** Un signal transversal compare des actifs entre eux. Si le
    signal est plus fort dans un secteur que dans les autres, le portefeuille qui
    en sort est un pari sectoriel déguisé. Le gérant croit acheter du momentum
    et achète de l'énergie.

    **L'intuition.** À chaque date et dans chaque groupe, on retire la moyenne du
    groupe. Chaque actif est alors comparé à ses pairs et non à l'univers
    entier. La moyenne de chaque groupe est nulle par construction, donc un
    portefeuille proportionnel au signal ne porte plus d'exposition nette au
    groupe.

    .. math::

        \tilde{x}_{i,t} = x_{i,t} - \frac{1}{|\mathcal{G}(i)_t|}
        \sum_{j \in \mathcal{G}(i)_t} x_{j,t}

    Définition de chaque variable :

    - :math:`\mathcal{G}(i)_t` l'ensemble des actifs renseignés à la date
      :math:`t` qui partagent le groupe de l'actif :math:`i` ;
    - :math:`|\mathcal{G}(i)_t|` le nombre d'actifs de ce groupe à cette date.

    **La forme la plus simple de neutralisation.** Retirer une moyenne par groupe
    revient à régresser le signal sur les indicatrices de groupe et à garder le
    résidu. La forme générale, qui neutralise aussi des expositions continues
    comme la taille ou le bêta, demande une régression transversale et vit
    ailleurs. Ici, aucune matrice à inverser : la projection sur des indicatrices
    disjointes est une moyenne par bloc.

    **Hypothèses.** Les groupes forment une partition de l'univers, chaque actif
    appartenant à un et un seul. Le groupe est connu à la date, ce qui suppose
    une table de secteurs point-in-time : un secteur attribué aujourd'hui et
    appliqué à 2005 est une fuite d'information.

    **Provenance.** La neutralisation sectorielle par retrait de moyenne est
    décrite par Qian, Hua et Sorensen (2007), chapitre 3. Statut : rapporté.

    **Limites.** Un groupe qui ne porte qu'un actif rend un signal exactement
    nul pour cet actif, à toutes les dates. Ce n'est pas un défaut de calcul,
    c'est ce que veut dire « comparer un actif à ses pairs » quand il n'en a
    aucun. L'argument ``min_names`` permet de rendre ``NaN`` plutôt que zéro, ce
    qui distingue « aucune opinion » de « opinion neutre ». La neutralisation
    retire aussi du rendement quand la rotation sectorielle est elle-même
    rémunérée.

    **Alternatives.** Une régression transversale sur des expositions continues,
    qui neutralise la taille ou le bêta. Une contrainte de neutralité posée dans
    l'optimiseur, qui garde le signal intact et déplace le compromis vers la
    construction de portefeuille.

    **Pourquoi cette méthode ici.** Elle est exacte, sans inversion de matrice,
    et son résultat se vérifie à l'oeil : la somme de chaque groupe vaut zéro.

    **Comment vérifier.** Après passage, la moyenne de chaque groupe vaut zéro à
    la précision machine, à chaque date. Le contrôle est dans
    ``tests/unit/test_signals_standardize.py``.

    Args:
        panel: le signal brut, lignes = dates, colonnes = actifs.
        groups: l'étiquette de groupe de chaque actif, dictionnaire ou
            ``Series`` indexée par actif. Tous les actifs du panel doivent y
            figurer.
        min_names: le nombre d'actifs renseignés qu'un groupe doit atteindre à
            une date pour que sa moyenne soit retirée. En deçà, les actifs du
            groupe rendent ``NaN`` à cette date. Défaut un, soit aucun filtrage.

    Returns:
        Un panel de même forme, chaque groupe de chaque date étant de moyenne
        nulle.

    Raises:
        ConfigError: si un actif du panel n'a pas de groupe, ou si ``min_names``
            est inférieur à un.
        DataQualityError: si le panel porte un doublon ou une valeur infinie, ou
            si la table de groupes porte un actif en double.
    """
    if int(min_names) < 1:
        raise ConfigError("min_names doit valoir au moins un groupe non vide")
    valide = _validated_panel(panel)
    etiquettes = pd.Series(groups) if not isinstance(groups, pd.Series) else groups.copy()
    if etiquettes.index.has_duplicates:
        doublons = etiquettes.index[etiquettes.index.duplicated()].tolist()
        raise DataQualityError(f"la table de groupes porte des actifs en double : {doublons}")
    etiquettes = etiquettes.reindex(valide.columns)
    if bool(etiquettes.isna().any()):
        manquants = etiquettes.index[etiquettes.isna()].tolist()
        raise ConfigError(
            f"ces actifs n'ont pas de groupe : {manquants}. Un actif sans groupe ne peut pas être "
            "comparé à ses pairs, et le combler par un groupe fourre-tout serait une décision cachée."
        )
    sortie = valide.copy()
    for etiquette in pd.unique(etiquettes):
        colonnes = etiquettes.index[etiquettes == etiquette]
        bloc = valide.loc[:, colonnes]
        presents = bloc.notna().sum(axis=1)
        moyennes = bloc.mean(axis=1).where(presents >= int(min_names))
        sortie.loc[:, colonnes] = bloc.sub(moyennes, axis=0)
    return sortie


def scale_to_gross(weights: Weights, target_gross: float = DEFAULT_TARGET_GROSS) -> Weights:
    r"""Met les poids à l'échelle pour que leur exposition brute atteigne la cible.

    **Le problème.** Un vecteur de scores standardisés n'a aucune raison de
    sommer, en valeur absolue, au montant que le mandat autorise. Sans mise à
    l'échelle, l'exposition brute dépend de la dispersion du signal du jour,
    donc le risque bouge pour une raison qui n'est pas une opinion.

    **L'intuition.** On multiplie tous les poids par un même nombre positif. Les
    proportions entre positions restent identiques, seule leur taille change.

    .. math::

        w^{\star}_i = w_i \cdot \frac{G}{\sum_j |w_j|}

    Définition de chaque variable :

    - :math:`w_i` le poids brut de l'actif :math:`i` ;
    - :math:`G` l'exposition brute visée, soit la somme des valeurs absolues
      après mise à l'échelle ;
    - :math:`\sum_j |w_j|` l'exposition brute avant mise à l'échelle.

    **Ce que la mise à l'échelle préserve.** Tout, sauf la taille. L'ordre, les
    signes, les rapports entre positions et l'exposition nette rapportée à
    l'exposition brute sont inchangés. L'exposition nette en niveau, elle, est
    multipliée par le même facteur.

    **Hypothèses.** L'exposition brute de départ est strictement positive. Un
    vecteur nul ne peut atteindre aucune cible strictement positive, et la
    fonction refuse plutôt que de rendre des poids infinis.

    **Provenance.** Convention de gestion, pas de résultat académique. Une
    exposition brute de 1,0 décrit un portefeuille pleinement investi sans
    levier ; un long-short dit « 130/30 » a une exposition brute de 1,6 et une
    exposition nette de 1,0. Statut : précepte.

    **Limites.** La mise à l'échelle ne borne aucune position individuelle. Un
    signal très concentré peut sortir un poids de 80 % tout en respectant une
    exposition brute de 1,0. Les bornes par position appartiennent à
    l'optimiseur, non à ce module.

    **Alternatives.** Cibler la volatilité plutôt que l'exposition brute, ce qui
    demande une matrice de covariance et vit dans :mod:`quantlab.risk`. Cibler
    l'exposition nette, ce que fait :func:`scale_to_net` par un autre geste.

    **Pourquoi cette méthode ici.** L'exposition brute est la seule mesure de
    taille qui ne demande aucun modèle de risque, donc la seule qui ne peut pas
    se tromper d'hypothèse.

    **Comment vérifier.** La somme des valeurs absolues du résultat vaut la
    cible, et le rapport entre deux poids quelconques est inchangé.

    Args:
        weights: les poids bruts, indexés par actif, sans valeur manquante.
        target_gross: l'exposition brute visée, positive ou nulle.

    Returns:
        Les poids mis à l'échelle, de même index.

    Raises:
        ConfigError: si la cible est négative.
        DataQualityError: si un poids manque, ou si l'exposition brute de départ
            est nulle alors que la cible ne l'est pas.
        InsufficientDataError: si le vecteur est vide.
    """
    if target_gross < 0.0:
        raise ConfigError(f"target_gross doit être positif ou nul, reçu {target_gross}")
    valide = _validated_weights(weights)
    if target_gross == 0.0:
        return valide * 0.0
    brut = float(np.abs(valide.to_numpy(dtype=float)).sum())
    # Une somme de valeurs absolues ne s'annule que si tous les poids sont nuls.
    # Le test exact est donc le bon, et il est le seul qui ne dépende pas de
    # l'unité : un seuil absolu refuserait des poids en 1e-13 que la mise à
    # l'échelle sait pourtant porter à la cible.
    if brut == 0.0:
        raise DataQualityError(
            "l'exposition brute de départ est nulle : aucun facteur ne porte un vecteur nul "
            f"à une exposition de {target_gross}."
        )
    return valide * (target_gross / brut)


def scale_to_net(weights: Weights, target_net: float = 0.0) -> Weights:
    r"""Décale tous les poids d'une même constante pour atteindre l'exposition nette visée.

    **Le problème.** Un portefeuille tiré d'un signal standardisé porte une
    exposition nette qui n'a pas été choisie. Elle vaut ce que vaut la somme des
    scores, laquelle dépend de la forme de la distribution du jour.

    **L'intuition.** On ajoute la même quantité à chaque poids jusqu'à ce que
    leur somme atteigne la cible. Les écarts entre positions sont intacts : le
    portefeuille garde exactement les mêmes paris relatifs.

    .. math::

        w^{\star}_i = w_i + \frac{N - \sum_j w_j}{n}

    Définition de chaque variable :

    - :math:`N` l'exposition nette visée, soit la somme des poids après
      l'opération ;
    - :math:`n` le nombre d'actifs du vecteur ;
    - :math:`\sum_j w_j` l'exposition nette de départ.

    **Pourquoi un décalage et non un facteur.** Le nom parle d'échelle, le geste
    est une translation, et c'est la seule définition qui reste valable à la
    cible par défaut. Multiplier des poids ne peut amener leur somme à zéro
    qu'en annulant toutes les positions, ce qui détruit le portefeuille au lieu
    de le neutraliser. La translation, elle, atteint n'importe quelle cible en
    conservant les écarts, donc l'information du signal.

    **Ce que le décalage change quand même.** L'exposition brute. Ajouter une
    constante déplace chaque position, y compris celles qui changent de signe au
    passage. Il suit que les deux mises à l'échelle ne commutent pas : viser
    d'abord l'exposition nette, puis l'exposition brute, casse la première. La
    seule séquence qui tient les deux à la fois est un cas particulier, celui de
    la cible nette nulle, que la mise à l'échelle brute préserve puisqu'elle
    multiplie une somme déjà nulle.

    **Hypothèses.** Chaque actif peut recevoir le décalage, donc aucune borne de
    position n'est imposée ici. Le vecteur ne porte aucune valeur manquante.

    **Provenance.** Convention de gestion. Statut : précepte.

    **Limites.** Le décalage donne un poids non nul à des actifs que le signal
    ne recommandait pas, puisqu'il touche tout le monde. Sur un univers large,
    il crée une multitude de très petites positions, coûteuses à négocier et
    sans contenu informatif.

    **Alternatives.** Neutraliser par la vente d'un indice plutôt qu'en déplaçant
    chaque poids, ce qui concentre l'ajustement sur un seul instrument. Poser la
    contrainte dans l'optimiseur, qui la respectera au moindre coût.

    **Pourquoi cette méthode ici.** Elle est exacte, sans paramètre, et elle
    conserve tous les écarts, donc le classement du signal.

    **Comment vérifier.** La somme du résultat vaut la cible, et toute différence
    entre deux poids est inchangée à la précision machine.

    Args:
        weights: les poids bruts, indexés par actif, sans valeur manquante.
        target_net: l'exposition nette visée, zéro par défaut.

    Returns:
        Les poids décalés, de même index.

    Raises:
        ConfigError: si l'objet n'est pas une ``Series`` numérique.
        DataQualityError: si un poids manque ou est infini.
        InsufficientDataError: si le vecteur est vide.
    """
    valide = _validated_weights(weights)
    net = float(valide.to_numpy(dtype=float).sum())
    return valide + (float(target_net) - net) / float(len(valide))


def neutralize_to_zero_net(weights: Weights) -> Weights:
    """Ramène la somme des poids à zéro sans toucher aux écarts entre positions.

    **Le problème.** Un portefeuille long-short doit être neutre au marché au
    premier ordre, c'est-à-dire de somme nulle. Un signal standardisé n'y arrive
    pas tout seul dès que sa distribution est asymétrique ou que des ex aequo
    déplacent la moyenne des rangs.

    **L'intuition.** On retire à chaque poids la moyenne des poids. Les écarts
    entre positions sont conservés, donc le classement et les paris relatifs
    aussi. C'est le cas particulier de :func:`scale_to_net` à la cible zéro, et
    il porte un nom parce que c'est le seul dont on se sert dans un backtest
    long-short.

    **Hypothèses.** Aucun poids manquant, et aucune borne de position à
    respecter à cet endroit.

    **Provenance.** Convention de gestion. Statut : précepte.

    **Limites.** La neutralité obtenue est celle des dollars, pas celle du bêta.
    Un portefeuille de somme nulle dont la jambe longue est plus sensible au
    marché que la jambe courte reste exposé, et seule une neutralisation par le
    bêta corrige cela. L'opération change aussi l'exposition brute, donc
    l'appliquer après :func:`scale_to_gross` défait la cible brute.

    **Alternatives.** Une neutralisation par le bêta, qui pondère le décalage par
    la sensibilité au marché de chaque actif. Une contrainte d'égalité dans
    l'optimiseur.

    **Pourquoi cette méthode ici.** Elle est exacte et conserve l'information du
    signal, alors qu'une mise à l'échelle multiplicative ne peut atteindre une
    somme nulle qu'en supprimant toutes les positions.

    **Comment vérifier.** La somme du résultat vaut zéro à la précision machine,
    et la différence entre deux poids quelconques est inchangée. L'ordre
    recommandé est de neutraliser d'abord, puis d'appeler
    :func:`scale_to_gross`, qui préserve une somme nulle.

    Args:
        weights: les poids bruts, indexés par actif, sans valeur manquante.

    Returns:
        Les poids de somme nulle, de même index.

    Raises:
        DataQualityError: si un poids manque ou est infini.
        InsufficientDataError: si le vecteur est vide.
    """
    return scale_to_net(weights, target_net=0.0)


def _weights_from_row(
    values: np.ndarray,
    *,
    method: WeightingMethod,
    n_quantiles: int | None,
    long_only: bool,
    target_gross: float,
    min_names: int,
    rank_method: str,
) -> np.ndarray:
    """Rend les poids d'une seule coupe transversale.

    Args:
        values: la coupe de signal, valeurs manquantes comprises.
        method: la règle de conversion.
        n_quantiles: le nombre de paquets, pour la méthode par quantiles.
        long_only: si vrai, aucune position vendeuse.
        target_gross: l'exposition brute visée.
        min_names: le nombre d'actifs sous lequel la coupe rend ``NaN``.
        rank_method: la règle de départage des ex aequo.

    Returns:
        Un vecteur de poids de même longueur, entièrement ``NaN`` si la coupe
        n'est pas exploitable, et zéro sur les actifs hors univers sinon.
    """
    indefini = np.full(values.shape, np.nan)
    presentes = np.isfinite(values)
    nombre = int(presentes.sum())
    if nombre < min_names:
        return indefini
    if method is WeightingMethod.EQUAL_LONG_SHORT and n_quantiles is not None and nombre < n_quantiles:
        return indefini
    positions = np.flatnonzero(presentes)
    coupe = values[positions]
    plancher = MIN_RELATIVE_DISPERSION * float(np.abs(coupe).max())
    if not coupe.max() - coupe.min() > plancher:
        # Une coupe constante n'ordonne rien. La règle vaut pour les trois
        # méthodes, et elle porte tout son poids sur les départages autres que
        # la moyenne. Mesuré sur cinq signaux égaux avec rank_method="first" :
        # sans cette ligne, les rangs 1 à 5 sortent les poids -1/3, -1/6, 0,
        # 1/6 et 1/3, soit un portefeuille entier tiré de l'ordre des colonnes.
        return indefini

    if method is WeightingMethod.RANK:
        rangs = _ranks_1d(coupe, rank_method)
        scores = (rangs - 1.0) / (nombre - 1.0)
        if not long_only:
            scores = 2.0 * scores - 1.0
    elif method is WeightingMethod.ZSCORE:
        centre = coupe.mean()
        dispersion = coupe.std(ddof=1)
        if not dispersion > plancher:
            return indefini
        scores = (coupe - centre) / dispersion
        if long_only:
            scores = np.maximum(scores, 0.0)
    else:
        rangs = _ranks_1d(coupe, "first")
        paquets = np.floor((rangs - 1.0) * float(n_quantiles) / float(nombre))
        haut = paquets == float(n_quantiles) - 1.0
        bas = paquets == 0.0
        if not coupe[haut].min() > coupe[bas].max():
            # Les deux paquets extrêmes portent le même signal : leur séparation
            # ne vient que de l'ordre des colonnes, donc d'aucune information.
            # Rendre un portefeuille ici fabriquerait des paris à partir de rien.
            return indefini
        if long_only:
            scores = haut.astype(float) / float(haut.sum())
        else:
            scores = haut.astype(float) / float(haut.sum()) - bas.astype(float) / float(bas.sum())

    if not long_only:
        # Le recentrage rend la somme nulle à la précision machine. Sans lui,
        # des ex aequo départagés autrement que par la moyenne laisseraient une
        # exposition nette résiduelle que personne n'a choisie. Il ne s'applique
        # que si la somme s'écarte déjà de zéro, pour ne pas remplacer par un
        # résidu d'arrondi les zéros exacts du paquet central.
        moyenne = float(scores.mean())
        if abs(moyenne) > MIN_DISPERSION:
            scores = scores - moyenne
    brut = float(np.abs(scores).sum())
    if not brut > 0.0:
        return indefini
    sortie = np.zeros_like(values)
    sortie[positions] = scores * (target_gross / brut)
    return sortie


def signal_to_weights(
    signal: SignalPanel | SignalCrossSection,
    *,
    method: WeightingMethod | str = WeightingMethod.RANK,
    n_quantiles: int | None = None,
    long_only: bool = False,
    target_gross: float = DEFAULT_TARGET_GROSS,
    min_names: int = DEFAULT_MIN_NAMES,
    rank_method: RankMethod = "average",
) -> WeightFrame | Weights:
    r"""Convertit un signal en poids de portefeuille, selon une règle déclarée.

    **Le problème, et la doctrine du module.** Un signal n'est pas un
    portefeuille. Passer de l'un à l'autre suppose une réponse à trois questions
    que le modèle ne pose jamais. Combien de conviction accorder à un écart de
    signal, quelle exposition brute porter, et faut-il vendre à découvert. Une
    conversion implicite répond à ces trois questions en silence, et le backtest
    qui suit mesure alors la conversion autant que le signal.

    **L'intuition.** Chaque méthode traduit le signal en un score, puis met ce
    score à l'échelle de l'exposition brute visée. En long-short, le score est
    recentré, si bien que la somme des poids vaut zéro et que le portefeuille ne
    porte pas de pari directionnel.

    .. math::

        w_{i,t} = s_{i,t} \cdot \frac{G}{\sum_j |s_{j,t}|},
        \qquad
        \sum_j w_{j,t} = 0 \ \text{en long-short}

    Définition de chaque variable :

    - :math:`s_{i,t}` le score de l'actif, produit par la méthode choisie ;
    - :math:`G` l'exposition brute visée, ``target_gross`` ;
    - :math:`w_{i,t}` le poids de l'actif à la date.

    **Les trois méthodes, et ce que chacune suppose.**

    - ``rank`` étire le classement sur l'intervalle de -1 à +1, puis met à
      l'échelle. Suppose que seul l'ordre porte de l'information. Insensible aux
      valeurs extrêmes, elle achète le deuxième actif presque autant que le
      premier. C'est le défaut du module, parce qu'elle ne peut pas exploser.
    - ``zscore`` prend le signal centré et réduit de la date. Suppose que
      l'ampleur de l'écart mesure la conviction, donc que le signal est
      cardinal. Elle concentre le portefeuille sur les extrêmes, ce qui augmente
      le rendement attendu et la sensibilité aux données aberrantes. À employer
      après :func:`winsorize` ou sur un signal déjà robuste.
    - ``equal_long_short`` achète à poids égaux le meilleur paquet et vend à
      poids égaux le pire, les actifs du milieu recevant zéro. Suppose que le
      signal ne sépare bien que les extrémités du classement. C'est la
      construction des tris de la littérature, donc la seule directement
      comparable aux tableaux publiés.

    **Le piège des ex aequo, et le refus qu'il déclenche.** Découper en paquets
    demande un ordre total, que les ex aequo ne donnent pas. Départager par
    l'ordre des colonnes, comme le fait la convention de ce module, suffit à
    fabriquer un portefeuille à partir d'une coupe constante. Le premier tiers
    des colonnes serait vendu et le dernier acheté, sans qu'aucune donnée le
    justifie. La date est donc refusée, et rend ``NaN``, dès que le plus petit
    signal du paquet haut n'est pas strictement supérieur au plus grand du
    paquet bas. Les ex aequo restants, ceux qui tombent sur une frontière
    intérieure, sont départagés par l'ordre des colonnes, convention déclarée
    ici et partagée avec :func:`quantlab.analytics.ic.quantile_returns`.

    **Une coupe constante ne rend aucun portefeuille.** Les trois méthodes
    refusent une date dont tous les signaux sont égaux, et rendent ``NaN``. Le
    z-score y est contraint par sa division, le rang ne l'est pas. Avec un
    départage par l'ordre des colonnes, il rendrait même un portefeuille
    complet : mesuré sur cinq signaux égaux, les poids -1/3, -1/6, 0, 1/6 et
    1/3. La règle est donc posée avant le calcul, pour les trois méthodes.

    **L'unité du signal ne décide de rien.** Le plancher qui déclare une coupe
    constante est relatif à son échelle. Un signal multiplié par 1e-13 rend donc
    les mêmes poids, ce qu'un seuil absolu ne donnait pas.

    **Ce que ``long_only`` change.** La jambe vendeuse disparaît, et avec elle la
    moitié de l'information portée par le classement du jour. En rang, le score
    va de 0 à 1, donc le dernier actif du classement reçoit un poids exactement
    nul. En z-score, les
    scores négatifs sont ramenés à zéro, ce qui est une troncature assumée. Dans
    les deux cas, l'exposition nette égale l'exposition brute : le portefeuille
    est un portefeuille d'actions ordinaire, dont le rendement contient celui du
    marché.

    **Hypothèses.** Le signal est déjà décalé du bon nombre de périodes, cette
    fonction n'en décale aucune. Aucun coût, aucune borne de position et aucune
    contrainte de liquidité n'entrent ici, et le résultat est donc un
    portefeuille cible, pas un portefeuille exécutable.

    **Provenance.** La conversion d'un score standardisé en poids proportionnels
    suit Grinold et Kahn (2000), chapitre sur la construction de portefeuille.
    Le tri par paquets extrêmes vient de Jegadeesh et Titman (1993), « Returns
    to buying winners and selling losers », *Journal of Finance* 48(1), 65-91.
    Statut : rapporté.

    **Limites.** Des poids proportionnels au signal ne sont optimaux que sous
    des hypothèses fortes, à savoir des rendements résiduels indépendants et de
    même volatilité. Dès que les corrélations comptent, un optimiseur fait
    mieux, et :mod:`quantlab.portfolio` existe pour cela. La rotation n'est pas
    contrôlée non plus : deux dates voisines peuvent rendre des portefeuilles
    très différents, ce que mesure :func:`quantlab.analytics.turnover.turnover`.

    **Alternatives.** Une optimisation moyenne-variance sous contraintes, qui
    tient compte des corrélations et des coûts. Une pondération par la
    capitalisation à l'intérieur des paquets, qui rapproche le résultat de ce
    qui est encaissable sur des petites capitalisations.

    **Pourquoi cette méthode ici.** Elle est transparente et reproductible : le
    poids de chaque actif se recalcule à la main depuis son rang. Aucun résultat
    ne dépend d'un solveur, ce qui rend la comparaison avec la littérature
    possible.

    **Comment vérifier.** En long-short, la somme des poids d'une date vaut zéro
    à 1e-12 et la somme de leurs valeurs absolues vaut ``target_gross``. En
    ``long_only``, tous les poids sont positifs ou nuls et leur somme vaut
    ``target_gross``. Les contrôles sont dans
    ``tests/unit/test_signals_standardize.py``.

    Args:
        signal: le signal, panel dates x actifs ou coupe indexée par actif.
        method: ``rank``, ``zscore`` ou ``equal_long_short``.
        n_quantiles: le nombre de paquets, exigé par ``equal_long_short`` et
            refusé par les deux autres méthodes.
        long_only: si vrai, aucune position vendeuse.
        target_gross: l'exposition brute visée par date.
        min_names: le nombre d'actifs sous lequel une date rend ``NaN``.
        rank_method: la règle de départage des ex aequo de la méthode ``rank``.

    Returns:
        Des poids de même forme que l'entrée. Un actif hors univers d'une date
        exploitable reçoit zéro, une date inexploitable rend ``NaN`` partout.

    Raises:
        ConfigError: si la méthode est inconnue, si ``n_quantiles`` est donné à
            une méthode qui ne l'emploie pas, s'il manque à
            ``equal_long_short``, s'il est inférieur à deux, ou si
            ``target_gross`` n'est pas strictement positif.
        DataQualityError: si le signal porte un doublon ou une valeur infinie.

    Example:
        >>> import pandas as pd
        >>> coupe = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0], index=list("abcde"))
        >>> poids = signal_to_weights(coupe)
        >>> round(abs(float(poids.sum())), 12), round(float(poids.abs().sum()), 12)
        (0.0, 1.0)
    """
    regle = WeightingMethod(method)
    if regle is WeightingMethod.EQUAL_LONG_SHORT:
        if n_quantiles is None:
            raise ConfigError("equal_long_short exige n_quantiles : le nombre de paquets se déclare")
        if int(n_quantiles) < 2:
            raise ConfigError(f"n_quantiles doit valoir au moins deux, reçu {n_quantiles}")
    elif n_quantiles is not None:
        raise ConfigError(
            f"n_quantiles n'a pas de sens pour la méthode {regle.value} : "
            "l'ignorer en silence cacherait une intention de l'appelant."
        )
    if not target_gross > 0.0:
        raise ConfigError(f"target_gross doit être strictement positif, reçu {target_gross}")
    if rank_method not in _RANK_METHODS:
        raise ConfigError(f"rank_method doit valoir l'un de {_RANK_METHODS}, reçu {rank_method!r}")
    seuil = _checked_min_names(min_names, floor=2)

    reglages: dict[str, Any] = {
        "method": regle,
        "n_quantiles": None if n_quantiles is None else int(n_quantiles),
        "long_only": long_only,
        "target_gross": float(target_gross),
        "min_names": seuil,
        "rank_method": rank_method,
    }
    if isinstance(signal, pd.Series):
        coupe = _validated_cross_section(signal)
        poids = _weights_from_row(coupe.to_numpy(dtype=float), **reglages)
        return pd.Series(poids, index=coupe.index, dtype=float)
    valide = _validated_panel(signal, label="signal")
    valeurs = valide.to_numpy(dtype=float)
    if valeurs.size == 0:
        return _rebuild(valeurs, valide)
    sortie = np.vstack([_weights_from_row(ligne, **reglages) for ligne in valeurs])
    return _rebuild(sortie, valide)

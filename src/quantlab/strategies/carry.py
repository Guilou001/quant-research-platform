r"""Le portage, et la seule convention qui décide de son signe.

**Le problème.** Koijen, Moskowitz, Pedersen et Vrugt (2018) appellent portage
le rendement qu'un contrat rapporte si son prix au comptant ne bouge pas. En
change, ce portage se réduit à l'écart de taux d'intérêt entre deux pays, ce
que donne l'équation (7) de l'article. Une série de change se cote dans un sens
ou dans l'autre, dollars par unité étrangère ou unités étrangères par dollar,
et confondre les deux inverse le signe du portage sans rien casser ailleurs.

**Le remède.** La conversion de cotation vit dans :func:`to_usd_per_unit`, qui
exige que le sens soit DÉCLARÉ et refuse de le deviner depuis un nom de série.
Le portage vit dans :func:`carry_signal`, le rendement dans
:func:`currency_excess_return`, et les deux prennent des taux annualisés en
décimales. Aucune autre fonction du module ne touche à une cotation.

**La règle de causalité.** Le portage porte la date de fin du mois où il est
connu. Le rendement porte la date de fin du mois où il est réalisé. Le passage
de l'un à l'autre se fait dans :func:`carry_portfolio`, qui décale les poids
d'une période et d'une seule. Le décalage vit à cet endroit unique, et un test
le vérifie en perturbant une valeur.

**Provenance.** Koijen, R. S. J., Moskowitz, T. J., Pedersen, L. H. et Vrugt,
E. B. (2018), « Carry », *Journal of Financial Economics* 127(2), 197-225. La
critique du portage de change comme objet unique vient de Daniel, Hodrick et Lu
(2017), *Critical Finance Review* 6(2), 211-262, et de Bekaert et Panayotov
(2020), *Journal of Financial and Quantitative Analysis* 55(4), 1063-1094.

**Les limites.** Rien ici ne connaît les frais, qui vivent dans
:mod:`quantlab.execution.costs`. Rien ici ne connaît le hors échantillon, qui
vit dans :mod:`quantlab.validation`. Ce module rend des séries et des
coefficients, et le jugement se prend ailleurs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.logging import get_logger

__all__ = [
    "MONTHS_PER_YEAR",
    "PanelRegressionResult",
    "PortfolioResult",
    "QuoteConvention",
    "WeightingScheme",
    "bond_slope_carry",
    "carry_portfolio",
    "carry_signal",
    "currency_excess_return",
    "dollar_decomposition",
    "modified_duration",
    "momentum_signal",
    "month_end_sample",
    "panel_carry_regression",
    "portfolio_carry",
    "rank_weights",
    "sign_weights",
    "smoothed_signal",
    "tercile_weights",
    "to_usd_per_unit",
    "weights_from_signal",
]

_LOG = get_logger(__name__)

#: Le nombre de mois d'une année, employé pour ramener un taux annualisé à la
#: période de détention d'un mois.
MONTHS_PER_YEAR: float = 12.0

#: Les deux sens de cotation reconnus. Le sens se DÉCLARE, il ne se devine pas.
QuoteConvention = Literal["usd_per_unit", "unit_per_usd"]

#: Les trois façons de passer d'un signal à des poids.
WeightingScheme = Literal["rank", "sign", "tercile"]

#: Le plancher sous lequel une exposition brute est jugée nulle. Sans lui, une
#: date où tous les signaux sont égaux rendrait une division par zéro muette.
GROSS_FLOOR: float = 1e-12


# --------------------------------------------------------------------------- #
# Les contrôles d'entrée
# --------------------------------------------------------------------------- #


def _as_frame(values: pd.DataFrame, *, label: str) -> pd.DataFrame:
    """Contrôle qu'une entrée est un tableau daté, trié et flottant."""
    if not isinstance(values, pd.DataFrame):
        raise ConfigError(f"{label} doit être un pandas.DataFrame, reçu {type(values).__name__}.")
    if not isinstance(values.index, pd.DatetimeIndex):
        raise ConfigError(f"{label} doit porter un DatetimeIndex.")
    if not values.index.is_monotonic_increasing:
        raise DataQualityError(f"{label} n'est pas trié par date croissante.")
    if values.index.has_duplicates:
        raise DataQualityError(f"{label} porte des dates en double.")
    if values.columns.has_duplicates:
        raise DataQualityError(f"{label} porte des colonnes en double.")
    return values.astype(float)


def _as_series(values: pd.Series, *, label: str) -> pd.Series:
    """Contrôle qu'une entrée est une série datée, triée et flottante."""
    if not isinstance(values, pd.Series):
        raise ConfigError(f"{label} doit être une pandas.Series, reçu {type(values).__name__}.")
    if not isinstance(values.index, pd.DatetimeIndex):
        raise ConfigError(f"{label} doit porter un DatetimeIndex.")
    if not values.index.is_monotonic_increasing:
        raise DataQualityError(f"{label} n'est pas trié par date croissante.")
    if values.index.has_duplicates:
        raise DataQualityError(f"{label} porte des dates en double.")
    return values.astype(float)


# --------------------------------------------------------------------------- #
# La cotation, et le mois
# --------------------------------------------------------------------------- #


def to_usd_per_unit(spot: pd.Series, quote: QuoteConvention) -> pd.Series:
    r"""Ramène une série de change à la convention « dollars par unité étrangère ».

    **Le problème.** La Réserve fédérale publie ses taux de change dans les deux
    sens. ``DEXUSUK`` cote des dollars par livre, ``DEXJPUS`` cote des yens par
    dollar. Le rendement d'une position longue sur une devise s'écrit avec le
    prix de cette devise EN DOLLARS. Prendre la série brute dans un cas sur deux
    inverse le signe de la variation de change, donc le signe du rendement.

    **L'intuition.** Une seule cotation est correcte pour la formule, et le sens
    de la série se déclare au lieu de se lire dans son nom. Un nom de série est
    une convention de fournisseur, pas une garantie.

    **La formule.** Avec :math:`S` la série rendue et :math:`X` la série reçue :

    .. math::

        S_t = X_t \quad \text{si la cotation est en dollars par unité},
        \qquad S_t = \frac{1}{X_t} \quad \text{sinon}.

    Args:
        spot: la série de change, datée et triée.
        quote: ``« usd_per_unit »`` ou ``« unit_per_usd »``, déclaré.

    Returns:
        La série cotée en dollars par unité étrangère.

    Raises:
        ConfigError: si le sens déclaré n'est pas reconnu.
        DataQualityError: si une valeur est nulle ou négative, ce qui rendrait
            l'inversion absurde.

    Example:
        .. code-block:: python

            yens = pd.Series([100.0, 125.0], index=pd.to_datetime(["2020-01-31", "2020-02-29"]))
            to_usd_per_unit(yens, "unit_per_usd").round(4).tolist()  # [0.01, 0.008]
    """
    serie = _as_series(spot, label="spot")
    if quote not in ("usd_per_unit", "unit_per_usd"):
        raise ConfigError(f"sens de cotation inconnu : {quote!r}. Attendu usd_per_unit ou unit_per_usd.")
    finis = serie.dropna()
    if (finis <= 0.0).any():
        raise DataQualityError("une cotation de change nulle ou négative interdit l'inversion")
    if quote == "usd_per_unit":
        return serie
    return 1.0 / serie


def month_end_sample(daily: pd.Series) -> pd.Series:
    """Rend la dernière observation valide de chaque mois, datée à la fin du mois.

    Le prix retenu est celui de la dernière séance connue du mois, ce qui est
    l'information dont dispose un investisseur à cet instant. La date portée est
    la fin de mois calendaire, pour que toutes les séries s'alignent.

    Args:
        daily: la série quotidienne, datée et triée.

    Returns:
        La série mensuelle, indexée par fins de mois calendaires.

    Raises:
        InsufficientDataError: si la série ne porte aucune observation valide.
    """
    serie = _as_series(daily, label="daily").dropna()
    if serie.empty:
        raise InsufficientDataError("la série quotidienne ne porte aucune observation valide")
    periodes = serie.index.to_period("M")
    dernier = serie.groupby(periodes).last()
    index = pd.DatetimeIndex(dernier.index.to_timestamp(how="end").normalize(), name="date")
    return pd.Series(dernier.to_numpy(), index=index, name=serie.name)


# --------------------------------------------------------------------------- #
# Le portage et le rendement de change
# --------------------------------------------------------------------------- #


def carry_signal(foreign_rate: pd.Series, base_rate: pd.Series) -> pd.Series:
    r"""Rend le portage mensuel d'une devise, équation (7) de l'article.

    **Le problème.** L'article définit le portage par l'écart entre le prix au
    comptant et le prix à terme. En change, la parité couverte des taux fait de
    cet écart une fonction du seul différentiel de taux, et les points de report
    ne sont donc pas nécessaires pour le calculer.

    **L'intuition.** Placer un dollar à l'étranger rapporte le taux étranger et
    coûte le taux local. Si le change ne bouge pas, ce différentiel est tout le
    rendement. C'est exactement ce que le mot portage désigne.

    **La formule**, équation (7) du manuscrit, ramenée à une détention d'un
    mois. Avec :math:`r^{*}` le taux étranger annualisé et :math:`r` le taux
    local annualisé, tous deux en décimales :

    .. math::

        C_t = \frac{\left( r^{*}_t - r_t \right) / 12}{1 + r_t / 12}

    Args:
        foreign_rate: le taux court étranger, annualisé, en décimales.
        base_rate: le taux court local, annualisé, en décimales.

    Returns:
        Le portage du mois, en rendement mensuel décimal, sur l'index commun.

    Raises:
        DataQualityError: si un taux local rend le dénominateur nul.

    Example:
        .. code-block:: python

            index = pd.to_datetime(["2020-01-31"])
            etranger = pd.Series([0.05], index=index)
            local = pd.Series([0.02], index=index)
            round(float(carry_signal(etranger, local).iloc[0]), 6)  # 0.002496
    """
    etranger = _as_series(foreign_rate, label="foreign_rate")
    local = _as_series(base_rate, label="base_rate")
    commun = etranger.index.intersection(local.index)
    etranger = etranger.reindex(commun)
    local = local.reindex(commun)
    denominateur = 1.0 + local / MONTHS_PER_YEAR
    if (denominateur.dropna().abs() < GROSS_FLOOR).any():
        raise DataQualityError("un taux local annule le dénominateur du portage")
    return (etranger - local) / MONTHS_PER_YEAR / denominateur


def currency_excess_return(
    spot_usd_per_unit: pd.Series,
    foreign_rate: pd.Series,
    base_rate: pd.Series,
) -> pd.Series:
    r"""Rend le rendement en excès d'une position longue sur une devise.

    **Le problème.** Le rendement d'un portage de change n'est pas l'écart de
    taux : c'est cet écart PLUS la variation du change sur la période de
    détention. C'est la décomposition qui ouvre l'article, et c'est elle qui
    rend le test intéressant.

    **La formule.** Avec :math:`S` le prix de la devise en dollars, un dollar
    placé à l'étranger et financé localement rapporte, sur un mois :

    .. math::

        rx_{t+1} = \left( 1 + \frac{r^{*}_t}{12} \right) \frac{S_{t+1}}{S_t}
        - \left( 1 + \frac{r_t}{12} \right)

    **La datation.** Le rendement porte la date :math:`t+1`, celle du mois où il
    est réalisé. Les deux taux portent la date :math:`t`, celle du mois où ils
    sont connus. Le décalage est donc déjà dans cette fonction, et il ne se
    répète pas ailleurs.

    Args:
        spot_usd_per_unit: le change en dollars par unité étrangère, mensuel.
        foreign_rate: le taux court étranger annualisé, en décimales.
        base_rate: le taux court local annualisé, en décimales.

    Returns:
        Le rendement en excès mensuel, daté du mois de réalisation.

    Example:
        .. code-block:: python

            index = pd.to_datetime(["2020-01-31", "2020-02-29"])
            spot = pd.Series([1.0, 1.0], index=index)
            haut = pd.Series([0.05, 0.05], index=index)
            bas = pd.Series([0.02, 0.02], index=index)
            round(float(currency_excess_return(spot, haut, bas).iloc[-1]), 6)  # 0.0025
    """
    spot = _as_series(spot_usd_per_unit, label="spot_usd_per_unit")
    etranger = _as_series(foreign_rate, label="foreign_rate")
    local = _as_series(base_rate, label="base_rate")
    commun = spot.index.intersection(etranger.index).intersection(local.index)
    spot = spot.reindex(commun)
    etranger = etranger.reindex(commun)
    local = local.reindex(commun)
    croissance = spot / spot.shift(1)
    portage_brut = (1.0 + etranger.shift(1) / MONTHS_PER_YEAR) * croissance
    financement = 1.0 + local.shift(1) / MONTHS_PER_YEAR
    return portage_brut - financement


def smoothed_signal(signal: pd.DataFrame, *, window: int, skip: int = 0) -> pd.DataFrame:
    """Rend la moyenne du signal sur une fenêtre, éventuellement décalée.

    L'article emploie deux variantes de contrôle. La première, « carry1-12 »,
    moyenne le portage des douze derniers mois pour effacer les effets de
    saison. La seconde, « carry2-13 », saute en plus un mois, pour qu'aucune
    donnée ne serve à la fois au signal et au rendement.

    Args:
        signal: le tableau des signaux, une colonne par actif.
        window: le nombre de mois moyennés, au moins un.
        skip: le nombre de mois sautés avant la fenêtre, zéro ou plus.

    Returns:
        Le tableau lissé, de même forme, les premiers mois valant ``NaN``.

    Raises:
        ConfigError: si la fenêtre est nulle ou négative, ou si le saut est
            négatif.
    """
    tableau = _as_frame(signal, label="signal")
    if window < 1:
        raise ConfigError(f"window doit valoir au moins 1, reçu {window}")
    if skip < 0:
        raise ConfigError(f"skip ne peut pas être négatif, reçu {skip}")
    decale = tableau.shift(skip) if skip else tableau
    return decale.rolling(window=window, min_periods=window).mean()


def momentum_signal(excess_returns: pd.DataFrame, *, lookback: int) -> pd.DataFrame:
    """Rend le rendement cumulé passé, signal de momentum de comparaison.

    Le signal du mois :math:`t` cumule les rendements des ``lookback`` mois qui
    se terminent en :math:`t` inclus. Il ne contient donc aucune information
    postérieure à la date qu'il porte.

    Args:
        excess_returns: les rendements en excès, une colonne par actif.
        lookback: le nombre de mois cumulés, au moins un.

    Returns:
        Le tableau des rendements cumulés, de même forme.

    Raises:
        ConfigError: si la fenêtre est nulle ou négative.
    """
    tableau = _as_frame(excess_returns, label="excess_returns")
    if lookback < 1:
        raise ConfigError(f"lookback doit valoir au moins 1, reçu {lookback}")
    log_un_plus = np.log1p(tableau)
    cumul = log_un_plus.rolling(window=lookback, min_periods=lookback).sum()
    return np.expm1(cumul)


# --------------------------------------------------------------------------- #
# Les poids
# --------------------------------------------------------------------------- #


def _scale_to_gross(brut: pd.DataFrame, gross: float) -> pd.DataFrame:
    """Met chaque ligne à l'exposition brute demandée, les lignes nulles à zéro."""
    somme = brut.abs().sum(axis=1)
    facteur = pd.Series(0.0, index=brut.index)
    utilisables = somme > GROSS_FLOOR
    facteur.loc[utilisables] = gross / somme.loc[utilisables]
    return brut.mul(facteur, axis=0)


def rank_weights(signal: pd.DataFrame, *, gross: float = 2.0, min_assets: int = 2) -> pd.DataFrame:
    r"""Rend les poids du tri par rang de l'article, à somme nulle.

    **Le problème.** Un tri par portage doit être long sur les portages hauts et
    court sur les portages bas, sans que l'échelle dépende du nombre d'actifs
    disponibles ce mois-là. L'univers de l'article varie dans le temps, les
    monnaies entrant à des dates différentes.

    **La formule** de la section 3 du manuscrit. Avec :math:`\text{rg}` le rang
    croissant du portage et :math:`N_t` le nombre d'actifs cotés à la date
    :math:`t` :

    .. math::

        w^i_t = z_t \left( \text{rg}\left( C^i_t \right) - \frac{N_t + 1}{2} \right),
        \qquad \sum_i \left| w^i_t \right| = 2

    **Ce que la formule garantit.** La somme des poids vaut zéro, parce que la
    somme des écarts au rang médian vaut zéro. L'exposition brute vaut deux, un
    dollar long et un dollar court, quel que soit le nombre d'actifs.

    Args:
        signal: le tableau des signaux, une colonne par actif, daté.
        gross: l'exposition brute imposée à chaque date.
        min_assets: le nombre minimal d'actifs exigé pour qu'une date compte.

    Returns:
        Le tableau des poids, mêmes index et colonnes, zéro là où le signal
        manque ou là où l'univers est trop maigre.

    Raises:
        ConfigError: si l'exposition brute n'est pas positive, ou si le nombre
            minimal d'actifs est inférieur à deux.
    """
    tableau = _as_frame(signal, label="signal")
    if gross <= 0.0:
        raise ConfigError(f"gross doit être positif, reçu {gross}")
    if min_assets < 2:
        raise ConfigError(f"min_assets doit valoir au moins 2, reçu {min_assets}")
    rangs = tableau.rank(axis=1, method="average")
    disponibles = tableau.notna().sum(axis=1)
    centre = (disponibles + 1.0) / 2.0
    brut = rangs.sub(centre, axis=0).fillna(0.0)
    brut = brut.mul((disponibles >= min_assets).astype(float), axis=0)
    return _scale_to_gross(brut, gross)


def sign_weights(signal: pd.DataFrame, *, gross: float = 2.0, min_assets: int = 2) -> pd.DataFrame:
    r"""Rend les poids de la stratégie de calendrier, équation (24) de l'article.

    **Le problème.** Le tri par rang est toujours investi, même quand tous les
    portages sont du même signe. La stratégie de calendrier répond à une autre
    question : faut-il détenir cet actif, indépendamment des autres ?

    **La formule**, équation (24), avec la moyenne du signal jusqu'à la date
    courante comme référence :

    .. math::

        w^i_t = z_t \left( 2\, \mathbb{I}\left( C^i_t - \bar{C}^i_t > 0 \right) - 1 \right)

    **La moyenne employée est celle du passé.** Elle se calcule sur les mois un
    à :math:`t` inclus, donc elle est connue au moment de décider. L'article
    écrit lui aussi une moyenne historique jusqu'à la date courante.

    Args:
        signal: le tableau des signaux, une colonne par actif, daté.
        gross: l'exposition brute imposée à chaque date.
        min_assets: le nombre minimal d'actifs exigé pour qu'une date compte.

    Returns:
        Le tableau des poids, mêmes index et colonnes.

    Raises:
        ConfigError: si l'exposition brute n'est pas positive, ou si le nombre
            minimal d'actifs est inférieur à deux.
    """
    tableau = _as_frame(signal, label="signal")
    if gross <= 0.0:
        raise ConfigError(f"gross doit être positif, reçu {gross}")
    if min_assets < 2:
        raise ConfigError(f"min_assets doit valoir au moins 2, reçu {min_assets}")
    moyenne = tableau.expanding(min_periods=1).mean()
    ecart = tableau - moyenne
    brut = ecart.map(lambda x: np.nan if pd.isna(x) else (1.0 if x > 0.0 else -1.0))
    brut = brut.astype(float).fillna(0.0)
    disponibles = tableau.notna().sum(axis=1)
    brut = brut.mul((disponibles >= min_assets).astype(float), axis=0)
    return _scale_to_gross(brut, gross)


def tercile_weights(signal: pd.DataFrame, *, gross: float = 2.0, min_assets: int = 3) -> pd.DataFrame:
    """Rend les poids d'un tri par tiers, long le tiers haut, court le tiers bas.

    Le tri par rang répartit le poids sur tout l'univers. Le tri par tiers le
    concentre sur les extrêmes, ce qui augmente le portage du portefeuille et sa
    rotation. La comparaison des deux mesure ce que la concentration apporte.

    Args:
        signal: le tableau des signaux, une colonne par actif, daté.
        gross: l'exposition brute imposée à chaque date.
        min_assets: le nombre minimal d'actifs exigé, au moins trois.

    Returns:
        Le tableau des poids, mêmes index et colonnes.

    Raises:
        ConfigError: si l'exposition brute n'est pas positive, ou si le nombre
            minimal d'actifs est inférieur à trois.
    """
    tableau = _as_frame(signal, label="signal")
    if gross <= 0.0:
        raise ConfigError(f"gross doit être positif, reçu {gross}")
    if min_assets < 3:
        raise ConfigError(f"min_assets doit valoir au moins 3, reçu {min_assets}")
    rangs = tableau.rank(axis=1, method="first")
    disponibles = tableau.notna().sum(axis=1)
    taille = np.maximum(np.floor(disponibles.to_numpy() / 3.0), 1.0)
    seuil_bas = pd.Series(taille, index=tableau.index)
    seuil_haut = disponibles - seuil_bas
    longs = rangs.gt(seuil_haut, axis=0)
    courts = rangs.le(seuil_bas, axis=0)
    brut = longs.astype(float) - courts.astype(float)
    brut = brut.mul((disponibles >= min_assets).astype(float), axis=0)
    return _scale_to_gross(brut, gross)


def weights_from_signal(
    signal: pd.DataFrame,
    *,
    scheme: WeightingScheme = "rank",
    gross: float = 2.0,
    min_assets: int = 2,
) -> pd.DataFrame:
    """Choisit le schéma de pondération déclaré et rend les poids correspondants.

    Args:
        signal: le tableau des signaux, une colonne par actif, daté.
        scheme: ``« rank »``, ``« sign »`` ou ``« tercile »``.
        gross: l'exposition brute imposée à chaque date.
        min_assets: le nombre minimal d'actifs exigé pour qu'une date compte.

    Returns:
        Le tableau des poids.

    Raises:
        ConfigError: si le schéma demandé n'est pas reconnu.
    """
    if scheme == "rank":
        return rank_weights(signal, gross=gross, min_assets=min_assets)
    if scheme == "sign":
        return sign_weights(signal, gross=gross, min_assets=min_assets)
    if scheme == "tercile":
        return tercile_weights(signal, gross=gross, min_assets=max(min_assets, 3))
    raise ConfigError(f"schéma de pondération inconnu : {scheme!r}")


# --------------------------------------------------------------------------- #
# Le portefeuille
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, eq=False)
class PortfolioResult:
    """Ce que rend un portefeuille de portage, poids compris.

    Attributes:
        returns: le rendement du portefeuille, daté du mois de réalisation.
        weights: les poids DÉJÀ décalés, donc ceux appliqués au rendement de la
            même ligne.
        raw_weights: les poids avant décalage, datés du mois où ils sont formés.
        carry: le portage du portefeuille, équation (22), daté du mois où il est
            connu.
        n_assets: le nombre d'actifs pesés à chaque date.
    """

    returns: pd.Series
    weights: pd.DataFrame
    raw_weights: pd.DataFrame
    carry: pd.Series
    n_assets: pd.Series


def portfolio_carry(weights: pd.DataFrame, signal: pd.DataFrame) -> pd.Series:
    r"""Rend le portage du portefeuille de portage, équation (22) de l'article.

    Le portage du portefeuille est la somme des portages des positions longues
    moins la somme des portages des positions courtes, chacun pondéré. Il est
    positif par construction dès que le tri va dans le sens du signal.

    .. math::

        C^{\text{carry trade}}_t = \sum_{w^i_t > 0} w^i_t C^i_t
        - \sum_{w^i_t < 0} \left| w^i_t \right| C^i_t

    Args:
        weights: les poids, datés du mois où ils sont formés.
        signal: les portages, datés du même mois.

    Returns:
        Le portage du portefeuille, une valeur par date.
    """
    poids = _as_frame(weights, label="weights")
    valeurs = _as_frame(signal, label="signal")
    alignes = valeurs.reindex(index=poids.index, columns=poids.columns)
    produit = poids * alignes.fillna(0.0)
    return produit.sum(axis=1)


def carry_portfolio(
    signal: pd.DataFrame,
    excess_returns: pd.DataFrame,
    *,
    scheme: WeightingScheme = "rank",
    gross: float = 2.0,
    min_assets: int = 2,
    execution_lag: int = 1,
) -> PortfolioResult:
    """Construit le portefeuille trié par portage, avec son décalage d'exécution.

    **Le seul endroit où le décalage vit.** Les poids sont formés depuis le
    signal daté :math:`t`, puis décalés de ``execution_lag`` périodes avant
    d'être appliqués au rendement. Le rendement du mois :math:`t+1` n'emploie
    donc que de l'information connue à la fin du mois :math:`t`.

    **Pourquoi un décalage nul est refusé.** Un décalage nul multiplie un poids
    par le rendement du mois qui l'a produit, ce qui invente du rendement à
    partir de rien.

    Args:
        signal: le signal daté du mois où il est connu, une colonne par actif.
        excess_returns: les rendements en excès, datés du mois de réalisation.
        scheme: le schéma de pondération, voir :func:`weights_from_signal`.
        gross: l'exposition brute imposée à chaque date.
        min_assets: le nombre minimal d'actifs exigé pour qu'une date compte.
        execution_lag: le nombre de périodes de décalage, au moins un.

    Returns:
        Le résultat complet, rendements, poids et portage du portefeuille.

    Raises:
        ConfigError: si le décalage est inférieur à un.
        InsufficientDataError: si aucune date ne réunit un signal et un
            rendement.
    """
    if execution_lag < 1:
        raise ConfigError(
            f"execution_lag doit valoir au moins 1, reçu {execution_lag}. "
            "Un décalage nul emploie le rendement du mois qui a produit le poids."
        )
    valeurs = _as_frame(signal, label="signal")
    rendements = _as_frame(excess_returns, label="excess_returns")
    colonnes = [c for c in valeurs.columns if c in rendements.columns]
    if not colonnes:
        raise InsufficientDataError("aucune colonne commune entre le signal et les rendements")
    valeurs = valeurs.loc[:, colonnes]
    rendements = rendements.loc[:, colonnes]

    bruts = weights_from_signal(valeurs, scheme=scheme, gross=gross, min_assets=min_assets)
    portage = portfolio_carry(bruts, valeurs)
    decales = bruts.shift(execution_lag)

    index = valeurs.index.union(rendements.index).sort_values()
    decales = decales.reindex(index).fillna(0.0)
    alignes = rendements.reindex(index)
    utilisable = (decales.abs().sum(axis=1) > GROSS_FLOOR) & alignes.notna().any(axis=1)
    if not bool(utilisable.any()):
        raise InsufficientDataError("aucune date ne réunit un poids non nul et un rendement")

    contributions = decales * alignes.fillna(0.0)
    rendement = contributions.sum(axis=1).where(utilisable)
    rendement = rendement.loc[utilisable]
    rendement.name = "carry"
    n_actifs = (bruts.abs() > GROSS_FLOOR).sum(axis=1)
    _LOG.info(
        "portefeuille de portage construit",
        extra={"scheme": scheme, "n_months": len(rendement), "n_assets_max": int(n_actifs.max())},
    )
    return PortfolioResult(
        returns=rendement,
        weights=decales.loc[utilisable],
        raw_weights=bruts,
        carry=portage,
        n_assets=n_actifs,
    )


def dollar_decomposition(
    weights: pd.DataFrame,
    excess_returns: pd.DataFrame,
    available: pd.DataFrame,
    *,
    base_column: str = "USD",
) -> pd.DataFrame:
    r"""Sépare le rendement du portage en une jambe neutre au dollar et une jambe de dollar.

    **Le problème.** Daniel, Hodrick et Lu (2017) montrent que le portage de
    change n'est pas un objet unique. Sa partie neutre au dollar porte
    l'asymétrie négative et la corrélation aux facteurs de risque. Sa partie
    exposée au dollar rapporte davantage et n'a presque pas d'asymétrie. Juger
    la somme des deux revient à mélanger deux objets aux propriétés opposées.

    **L'intuition.** Un tri par rang à somme nulle sur onze actifs, dont le
    dollar lui-même, laisse une exposition nette aux devises étrangères égale à
    l'opposé du poids du dollar. Cette exposition nette est un pari sur le
    dollar, et non sur l'écart de portage entre deux monnaies.

    **La formule.** Avec :math:`\mathcal{F}_t` les devises étrangères cotées à
    la date :math:`t`, :math:`n_t` leur nombre et :math:`N_t` la somme de leurs
    poids :

    .. math::

        \sum_{i \in \mathcal{F}_t} w^i_t rx^i_{t+1}
        = \underbrace{\sum_{i \in \mathcal{F}_t}
          \left( w^i_t - \frac{N_t}{n_t} \right) rx^i_{t+1}}_{\text{neutre au dollar}}
        + \underbrace{N_t \, \frac{1}{n_t} \sum_{i \in \mathcal{F}_t} rx^i_{t+1}}_{\text{jambe de dollar}}

    **Ce que la décomposition garantit.** Les poids de la première jambe
    somment à zéro sur les devises étrangères, donc elle ne porte aucun pari sur
    le dollar. La somme des deux jambes redonne le rendement total, à la
    précision machine. Un rendement manquant sur une devise pourtant négociable
    est traité comme nul dans les deux jambes, sans quoi l'identité se briserait
    sans rien signaler.

    Args:
        weights: les poids DÉJÀ décalés, ceux appliqués au rendement de la même
            ligne.
        excess_returns: les rendements en excès, datés du mois de réalisation.
        available: le tableau booléen des actifs négociables à la date de
            formation, décalé comme les poids.
        base_column: la colonne du numéraire, exclue des deux jambes.

    Returns:
        Un tableau à quatre colonnes, ``total``, ``dollar_neutral``, ``dollar``
        et ``net_foreign_weight``.

    Raises:
        ConfigError: si la colonne du numéraire manque.
    """
    poids = _as_frame(weights, label="weights")
    rendements = _as_frame(excess_returns, label="excess_returns")
    if base_column not in poids.columns:
        raise ConfigError(f"la colonne du numéraire « {base_column} » manque dans les poids")
    etrangeres = [c for c in poids.columns if c != base_column]
    index = poids.index
    masque = available.reindex(index=index, columns=etrangeres).fillna(value=False).astype(bool)
    w = poids.loc[:, etrangeres].where(masque, 0.0)
    rx = rendements.reindex(index=index, columns=etrangeres).where(masque)
    compte = masque.sum(axis=1).astype(float)
    net = w.sum(axis=1)
    part = (net / compte.where(compte > 0.0)).fillna(0.0)
    neutres = w.sub(part, axis=0).where(masque, 0.0)
    panier = (rx.fillna(0.0).sum(axis=1) / compte.where(compte > 0.0)).fillna(0.0)
    jambe_dollar = net * panier
    jambe_neutre = (neutres * rx.fillna(0.0)).sum(axis=1)
    total = (w * rx.fillna(0.0)).sum(axis=1)
    return pd.DataFrame(
        {
            "total": total,
            "dollar_neutral": jambe_neutre,
            "dollar": jambe_dollar,
            "net_foreign_weight": net,
        }
    )


# --------------------------------------------------------------------------- #
# La régression de panel, équation (23)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class PanelRegressionResult:
    """Le coefficient de l'équation (23), et ce qui permet de le juger.

    Attributes:
        coefficient: le coefficient du portage, noté c dans l'article.
        stderr: son erreur type, groupée par date si demandé.
        tstat: le rapport du coefficient à son erreur type.
        tstat_vs_one: le rapport de l'écart à un à cette même erreur type.
        n_observations: le nombre de couples actif et date retenus.
        n_entities: le nombre d'actifs distincts.
        n_periods: le nombre de dates distinctes.
        r_squared: la part de variance expliquée après retrait des effets fixes.
        entity_fixed_effects: les effets fixes d'actif ont-ils été retirés.
        time_fixed_effects: les effets fixes de date ont-ils été retirés.
        cluster: le groupement des erreurs types, ``« time »`` ou ``« none »``.
    """

    coefficient: float
    stderr: float
    tstat: float
    tstat_vs_one: float
    n_observations: int
    n_entities: int
    n_periods: int
    r_squared: float
    entity_fixed_effects: bool
    time_fixed_effects: bool
    cluster: str


def _within_transform(
    frame: pd.DataFrame,
    *,
    entity_fe: bool,
    time_fe: bool,
    tol: float = 1e-12,
    max_iter: int = 200,
) -> pd.DataFrame:
    """Retire les effets fixes par projections alternées, panel non équilibré compris.

    Un panel équilibré se démoyenne en une passe. Un panel où les actifs
    n'entrent pas aux mêmes dates ne le fait pas, et la double moyenne doit se
    répéter jusqu'à convergence. C'est l'algorithme des projections alternées.
    """
    courant = frame.copy()
    colonnes = ["y", "x"]
    for _ in range(max_iter):
        avant = courant.loc[:, colonnes].to_numpy(copy=True)
        if entity_fe:
            courant[colonnes] = courant[colonnes] - courant.groupby("entity")[colonnes].transform("mean")
        if time_fe:
            courant[colonnes] = courant[colonnes] - courant.groupby("period")[colonnes].transform("mean")
        if float(np.max(np.abs(courant.loc[:, colonnes].to_numpy() - avant))) < tol:
            break
    return courant


def panel_carry_regression(
    signal: pd.DataFrame,
    excess_returns: pd.DataFrame,
    *,
    entity_fixed_effects: bool = True,
    time_fixed_effects: bool = True,
    cluster: Literal["time", "none"] = "time",
    execution_lag: int = 1,
) -> PanelRegressionResult:
    r"""Estime le coefficient c de l'équation (23), le test central de l'article.

    **Le problème.** Sous la parité non couverte des taux, un portage élevé doit
    être exactement compensé par une dépréciation attendue, donc ne rien
    prédire. Sous des primes de risque qui varient dans le temps, il prédit un
    rendement élevé. Un seul coefficient sépare les deux thèses.

    **La formule**, équation (23) du manuscrit, avec :math:`a_i` un effet fixe
    d'actif et :math:`b_t` un effet fixe de date :

    .. math::

        rx^i_{t+1} = a_i + b_t + c\, C^i_t + \varepsilon^i_{t+1}

    **Comment lire le coefficient.** Il vaut zéro si le marché annule le portage
    par une variation de change compensatrice. Il vaut un si le portage passe
    entièrement dans le rendement. Il dépasse un si le prix s'apprécie en plus.

    **Les effets fixes de date.** Ils retirent le mouvement commun du dollar,
    donc le coefficient ne se lit plus que dans la coupe transversale. C'est ce
    que fait l'article, et c'est ce qui rend la mesure comparable à la sienne.

    Args:
        signal: le portage, daté du mois où il est connu.
        excess_returns: les rendements en excès, datés du mois de réalisation.
        entity_fixed_effects: retirer la moyenne propre à chaque actif.
        time_fixed_effects: retirer la moyenne propre à chaque date.
        cluster: ``« time »`` groupe les erreurs types par date, ``« none »``
            les laisse ordinaires.
        execution_lag: le décalage entre le signal et le rendement, au moins un.

    Returns:
        Le coefficient, son erreur type et les comptes qui permettent de le
        juger.

    Raises:
        ConfigError: si le décalage est inférieur à un, ou si le groupement
            demandé n'est pas reconnu.
        InsufficientDataError: si moins de trois couples valides subsistent, ou
            si le portage ne varie plus après retrait des effets fixes.
    """
    if execution_lag < 1:
        raise ConfigError(f"execution_lag doit valoir au moins 1, reçu {execution_lag}")
    if cluster not in ("time", "none"):
        raise ConfigError(f"groupement inconnu : {cluster!r}. Attendu time ou none.")
    valeurs = _as_frame(signal, label="signal")
    rendements = _as_frame(excess_returns, label="excess_returns")
    colonnes = [c for c in valeurs.columns if c in rendements.columns]
    if not colonnes:
        raise InsufficientDataError("aucune colonne commune entre le signal et les rendements")

    index = valeurs.index.union(rendements.index).sort_values()
    decale = valeurs.loc[:, colonnes].reindex(index).shift(execution_lag)
    futur = rendements.loc[:, colonnes].reindex(index)
    long_x = decale.melt(ignore_index=False, var_name="entity", value_name="x")
    long_y = futur.melt(ignore_index=False, var_name="entity", value_name="y")
    long_x = long_x.set_index("entity", append=True)
    long_y = long_y.set_index("entity", append=True)
    panel = pd.concat([long_y, long_x], axis=1).dropna()
    if len(panel) < 3:
        raise InsufficientDataError(f"panel trop court : {len(panel)} observations valides")
    panel = panel.reset_index()
    panel.columns = ["period", "entity", "y", "x"]

    demoyenne = _within_transform(panel, entity_fe=entity_fixed_effects, time_fe=time_fixed_effects)
    x = demoyenne["x"].to_numpy()
    y = demoyenne["y"].to_numpy()
    xx = float(x @ x)
    if xx < GROSS_FLOOR:
        raise InsufficientDataError("le portage ne varie plus après retrait des effets fixes")
    coefficient = float(x @ y) / xx
    residus = y - coefficient * x

    n_obs = len(panel)
    n_entites = int(panel["entity"].nunique())
    n_periodes = int(panel["period"].nunique())
    n_params = 1 + (n_entites if entity_fixed_effects else 0) + (n_periodes - 1 if time_fixed_effects else 0)
    ddl = max(n_obs - n_params, 1)

    if cluster == "time":
        groupes = panel["period"].to_numpy()
        scores = pd.Series(x * residus).groupby(groupes).sum().to_numpy()
        meat = float(scores @ scores)
        n_groupes = len(scores)
        correction = (n_groupes / max(n_groupes - 1, 1)) * ((n_obs - 1) / ddl)
        variance = correction * meat / (xx**2)
    else:
        variance = float(residus @ residus) / ddl / xx

    stderr = float(np.sqrt(max(variance, 0.0)))
    tstat = coefficient / stderr if stderr > 0.0 else float("nan")
    tstat_vs_un = (coefficient - 1.0) / stderr if stderr > 0.0 else float("nan")
    total = float(y @ y)
    r2 = 1.0 - float(residus @ residus) / total if total > 0.0 else float("nan")
    return PanelRegressionResult(
        coefficient=coefficient,
        stderr=stderr,
        tstat=tstat,
        tstat_vs_one=tstat_vs_un,
        n_observations=n_obs,
        n_entities=n_entites,
        n_periods=n_periodes,
        r_squared=r2,
        entity_fixed_effects=entity_fixed_effects,
        time_fixed_effects=time_fixed_effects,
        cluster=cluster,
    )


# --------------------------------------------------------------------------- #
# La substitution obligataire
# --------------------------------------------------------------------------- #


def modified_duration(yield_annual: pd.Series, *, maturity_years: float) -> pd.Series:
    r"""Rend la duration modifiée d'une obligation au pair, formule fermée.

    La duration modifiée est la sensibilité du prix d'une obligation à une
    variation de taux d'un point. Pour une obligation au pair de coupon annuel
    égal au taux, elle vaut :

    .. math::

        D^{mod} = \frac{1}{y} \left( 1 - \frac{1}{\left( 1 + y \right)^{\tau}} \right)

    Args:
        yield_annual: le taux annualisé, en décimales.
        maturity_years: l'échéance en années, strictement positive.

    Returns:
        La duration modifiée, en années.

    Raises:
        ConfigError: si l'échéance n'est pas strictement positive.
    """
    taux = _as_series(yield_annual, label="yield_annual")
    if maturity_years <= 0.0:
        raise ConfigError(f"maturity_years doit être positif, reçu {maturity_years}")
    proche_de_zero = taux.abs() < 1e-8
    duree = (1.0 - (1.0 + taux) ** (-maturity_years)) / taux.where(~proche_de_zero, np.nan)
    return duree.fillna(float(maturity_years))


def bond_slope_carry(
    long_yield: pd.Series,
    short_rate: pd.Series,
    *,
    maturity_years: float = 10.0,
) -> pd.DataFrame:
    r"""Approche le portage obligataire par la pente, et rend le rendement associé.

    **Ce que cette fonction n'est pas.** L'article calcule le portage
    obligataire depuis le prix d'un contrat à terme synthétique, équations (11)
    à (13). Sa décomposition sépare la pente de la descente de courbe, le gain
    de prix obtenu quand l'obligation vieillit à courbe inchangée. Nous ne
    gardons que la pente, faute d'une courbe zéro-coupon complète et gratuite
    pour dix marchés. La descente de courbe est donc OMISE, et c'est une
    substitution déclarée.

    **Les deux quantités rendues.** Le portage approché vaut la pente ramenée au
    mois. Le rendement en excès approché ajoute l'effet de prix d'une variation
    de taux, par la duration modifiée :

    .. math::

        C_t \simeq \frac{y_t - r_t}{12},
        \qquad rx_{t+1} \simeq \frac{y_t - r_t}{12} - D^{mod}_t \left( y_{t+1} - y_t \right)

    Args:
        long_yield: le taux long annualisé, en décimales, mensuel.
        short_rate: le taux court annualisé, en décimales, mensuel.
        maturity_years: l'échéance du titre long, en années.

    Returns:
        Un tableau à trois colonnes, ``carry``, ``excess_return`` et
        ``duration``. Le portage porte la date où il est connu, le rendement la
        date où il est réalisé.
    """
    long = _as_series(long_yield, label="long_yield")
    court = _as_series(short_rate, label="short_rate")
    commun = long.index.intersection(court.index)
    long = long.reindex(commun)
    court = court.reindex(commun)
    pente = (long - court) / MONTHS_PER_YEAR
    duree = modified_duration(long, maturity_years=maturity_years)
    variation = long.diff()
    rendement = pente.shift(1) - duree.shift(1) * variation
    return pd.DataFrame({"carry": pente, "excess_return": rendement, "duration": duree})

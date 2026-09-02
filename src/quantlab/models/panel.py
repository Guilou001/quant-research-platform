"""Le panneau transversal : des caractéristiques par titre et par date, rangées sans lire l'avenir.

**Le problème.** Un modèle d'apprentissage transversal apprend, à chaque date,
à ordonner des titres selon leur rendement à venir. Il lui faut un tableau où
chaque ligne est un couple (date, titre), chaque colonne une caractéristique
connue à cette date, et une étiquette qui est le rendement du mois SUIVANT.
Deux fuites guettent ce tableau : une caractéristique qui lit l'avenir, et une
mise à l'échelle qui emploie des dates futures.

**Ce que le module fait.** Il construit le panneau long, indexé par (date,
titre), à partir de tableaux larges, dates en lignes et titres en colonnes. Il
met chaque caractéristique à l'échelle par son rang TRANSVERSAL à la date, dans
l'intervalle :math:`[-1, 1]`, comme Gu, Kelly et Xiu (2020), et remplace un
manquant par zéro, la médiane de cette échelle. Il construit l'étiquette par un
décalage explicite d'une période vers le passé, et son nom porte le préfixe
``label_`` pour se signaler.

**Ce qu'il ne fait pas.** Il ne calcule aucune caractéristique comptable, qui
viennent du panneau point-in-time de l'étude 004, et il ne standardise rien
dans le temps, ce qui est le rôle de :mod:`quantlab.features`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.logging import get_logger
from quantlab.features.transforms import momentum, rolling_max, rolling_std

__all__ = [
    "DATE_LEVEL",
    "ENTITY_LEVEL",
    "LABEL_NAME",
    "Panel",
    "make_panel",
    "price_features",
    "rank_features",
    "to_long",
    "to_wide",
]

_LOG = get_logger(__name__)

#: Les deux niveaux de l'index d'un panneau long.
DATE_LEVEL: str = "date"
ENTITY_LEVEL: str = "entity"

#: Le nom de l'étiquette, préfixé pour se signaler comme information future.
LABEL_NAME: str = "label_forward_return"

#: Le nombre minimal de titres à une date pour qu'un rang ait un sens.
MIN_NAMES_FOR_RANK: int = 2


def to_long(wide: pd.DataFrame, name: str) -> pd.Series:
    """Empile un tableau large, dates en lignes et titres en colonnes, en série longue.

    Args:
        wide: le tableau, indexé par date, une colonne par titre.
        name: le nom de la série rendue.

    Returns:
        Une série indexée par (date, titre), les manquants conservés.

    Raises:
        ConfigError: l'index n'est pas temporel.
    """
    if not isinstance(wide.index, pd.DatetimeIndex):
        raise ConfigError(f"{name} : un tableau large est indexé par date.")
    stacked = wide.stack(future_stack=True)  # noqa: PD013 - l'empilement conserve les manquants, ce que melt ne fait pas
    stacked.index = stacked.index.set_names([DATE_LEVEL, ENTITY_LEVEL])
    return stacked.rename(name).astype(float)


def to_wide(long: pd.Series) -> pd.DataFrame:
    """Rend un tableau large, dates en lignes et titres en colonnes, depuis une série longue."""
    if long.index.nlevels != 2:
        raise ConfigError("une série longue est indexée par (date, titre).")
    return long.unstack(ENTITY_LEVEL).sort_index()  # noqa: PD010 - un pivot sans agrégation est voulu


def rank_features(features: pd.DataFrame, *, min_names: int = MIN_NAMES_FOR_RANK) -> pd.DataFrame:
    r"""Met chaque caractéristique à l'échelle par son rang transversal, dans [-1, 1].

    **Le problème.** Un ratio comptable et une volatilité n'ont ni la même
    unité ni la même dispersion. Une valeur aberrante d'une seule société
    écrase toutes les autres, dans un modèle linéaire comme dans un arbre.

    **L'intuition.** À chaque date, on oublie les valeurs et on garde l'ordre.
    Le plus petit vaut moins un, le plus grand plus un, la médiane zéro. Un
    manquant reçoit zéro, c'est-à-dire la médiane : le modèle n'apprend rien
    de lui, il ne le rejette pas non plus.

    **La formule.**

    .. math::

        \tilde c_{i,t} = 2\,\frac{\operatorname{rang}(c_{i,t}) - 1}{n_t - 1} - 1

    **Les variables.** :math:`\operatorname{rang}` le rang moyen parmi les
    :math:`n_t` titres non manquants de la date :math:`t`.

    **Les hypothèses.** L'ordre porte l'information, pas le niveau. Une date
    avec un seul titre non manquant rend zéro pour lui.

    **La provenance.** Gu, Kelly et Xiu (2020), section 2.1, rapporté : les
    caractéristiques sont transformées en rangs transversaux normalisés dans
    l'intervalle :math:`[-1, 1]`, et les manquants sont fixés à zéro.

    **Les limites.** La mise à l'échelle efface la distance entre deux titres
    voisins, et un modèle qui voudrait exploiter les extrêmes ne le peut plus.

    **Les alternatives.** Le z-score transversal, sensible aux aberrants, et la
    winsorisation, qui garde le niveau.

    **Pourquoi cette méthode ici.** Elle rend les caractéristiques comparables
    entre dates sans lire aucune date future, et c'est celle de l'article.

    **Comment vérifier.** Trois valeurs 10, 20, 30 rendent -1, 0, 1 ; un
    manquant rend 0 ; deux valeurs égales reçoivent le même rang moyen.

    Args:
        features: le panneau long, indexé par (date, titre), une colonne par
            caractéristique.
        min_names: le nombre minimal de titres non manquants à une date pour
            ranger ; en dessous, la date rend zéro partout.

    Returns:
        Le panneau mis à l'échelle, sans manquant.

    Raises:
        ConfigError: l'index n'a pas les deux niveaux attendus.
    """
    if features.index.nlevels != 2:
        raise ConfigError("un panneau long est indexé par (date, titre).")
    dates = features.index.get_level_values(0)
    out = np.zeros(features.shape, dtype=float)
    values = features.to_numpy(dtype=float)
    for date in pd.unique(dates):
        rows = np.flatnonzero(dates == date)
        block = values[rows]
        for j in range(block.shape[1]):
            column = block[:, j]
            valid = np.isfinite(column)
            n = int(valid.sum())
            if n < min_names:
                continue
            ranks = pd.Series(column[valid]).rank(method="average").to_numpy()
            scaled = 2.0 * (ranks - 1.0) / (n - 1.0) - 1.0
            out[rows[valid], j] = scaled
    return pd.DataFrame(out, index=features.index, columns=features.columns)


@dataclass(frozen=True)
class Panel:
    """Un panneau prêt pour l'apprentissage : caractéristiques rangées et étiquette alignée.

    Attributes:
        features: le panneau long des caractéristiques, indexé par (date,
            titre), déjà mis à l'échelle et sans manquant.
        label: le rendement de la période SUIVANTE, même index, manquant quand
            il n'est pas observé.
        feature_names: les colonnes de ``features``, dans l'ordre.
    """

    features: pd.DataFrame
    label: pd.Series

    def __post_init__(self) -> None:
        if not self.features.index.equals(self.label.index):
            raise ConfigError("caractéristiques et étiquette doivent partager le même index (date, titre).")
        if self.label.name != LABEL_NAME:
            raise ConfigError(f"l'étiquette doit s'appeler {LABEL_NAME!r}, reçu {self.label.name!r}.")

    @property
    def feature_names(self) -> tuple[str, ...]:
        """Les noms des caractéristiques, dans l'ordre des colonnes."""
        return tuple(str(c) for c in self.features.columns)

    @property
    def dates(self) -> pd.DatetimeIndex:
        """Les dates du panneau, uniques et croissantes."""
        return pd.DatetimeIndex(sorted(pd.unique(self.features.index.get_level_values(DATE_LEVEL))))

    def rows_at(self, dates: pd.Index) -> np.ndarray:
        """Rend les positions des lignes dont la date est dans ``dates``."""
        return np.flatnonzero(self.features.index.get_level_values(DATE_LEVEL).isin(dates))

    def observed(self) -> Panel:
        """Rend le sous-panneau dont l'étiquette est observée."""
        keep = self.label.notna().to_numpy()
        return Panel(self.features.iloc[keep], self.label.iloc[keep])


def make_panel(
    features: pd.DataFrame,
    returns: pd.DataFrame,
    *,
    horizon: int = 1,
    min_names: int = MIN_NAMES_FOR_RANK,
) -> Panel:
    r"""Assemble le panneau : caractéristiques rangées à la date, étiquette du mois suivant.

    **Le problème.** L'étiquette est la seule information future admise, et
    elle doit l'être explicitement. Une étiquette construite par un décalage
    dans le mauvais sens fait apprendre au modèle le rendement qui vient de se
    produire, et le résultat est spectaculaire et faux.

    **L'intuition.** La ligne datée :math:`t` porte des caractéristiques
    connues à :math:`t` et le rendement de :math:`t+1`. C'est le geste du
    gérant : décider en fin de mois, encaisser le mois suivant.

    .. math::

        y_{i,t} = r_{i,t+h}

    **Les variables.** :math:`r` le rendement de période du tableau large,
    :math:`h` l'horizon en périodes.

    **Les hypothèses.** Les caractéristiques datées :math:`t` n'emploient que
    de l'information à :math:`t` inclus, ce que ce module ne vérifie pas et que
    :func:`quantlab.features.transforms.assert_causal` vérifie en test.

    **La provenance.** Gu, Kelly et Xiu (2020), équation (1).

    **Les limites.** Un titre dont le rendement de :math:`t+1` manque a une
    étiquette manquante ; il reste dans le panneau pour la prévision, pas pour
    l'apprentissage.

    **Les alternatives.** Une étiquette en excès du taux sans risque ou du
    rendement de marché, que l'étude applique en amont sur le tableau large.

    **Pourquoi cette méthode ici.** Un seul endroit décale, et il le dit.

    **Comment vérifier.** Sur un tableau où le rendement de :math:`t+1` est
    connu à la main, l'étiquette de :math:`t` le retrouve, et la dernière date
    n'a pas d'étiquette.

    Args:
        features: le panneau long brut des caractéristiques, indexé par (date,
            titre), manquants admis.
        returns: le tableau large des rendements de période, dates en lignes.
        horizon: le nombre de périodes entre la décision et l'encaissement.
        min_names: voir :func:`rank_features`.

    Returns:
        Le panneau, caractéristiques rangées et étiquette alignée.

    Raises:
        ConfigError: l'horizon n'est pas strictement positif.
        InsufficientDataError: aucune ligne ne porte d'étiquette observée.
    """
    if int(horizon) < 1:
        raise ConfigError(f"horizon doit valoir au moins 1, reçu {horizon!r}.")
    ranked = rank_features(features, min_names=min_names)
    forward = returns.sort_index().shift(-int(horizon))
    label = to_long(forward, LABEL_NAME).reindex(ranked.index)
    panel = Panel(ranked, label)
    n_observed = int(label.notna().sum())
    if n_observed == 0:
        raise InsufficientDataError(
            "aucune étiquette observée : les dates des rendements et des caractéristiques ne se "
            "recouvrent pas."
        )
    _LOG.info(
        "panneau assemblé",
        extra={"n_rows": len(ranked), "n_features": ranked.shape[1], "n_labelled": n_observed},
    )
    return panel


def price_features(returns: pd.DataFrame, market_equity: pd.DataFrame | None = None) -> pd.DataFrame:
    r"""Construit les caractéristiques de prix d'un tableau de rendements mensuels.

    **Le problème.** Les caractéristiques comptables arrivent en retard et
    changent peu ; les tendances de prix portent, dans Gu, Kelly et Xiu (2020),
    la première famille de variables influentes. Il en faut quelques-unes,
    calculées sans lire l'avenir.

    **Les six caractéristiques.** Le momentum à douze mois sautant le dernier,
    ``mom_12_1``. Le renversement à un mois, ``rev_1``. Le renversement à long
    terme de 36 à 13 mois, ``mom_36_13``. La volatilité des douze derniers
    rendements, ``vol_12``. Le plus grand rendement mensuel des douze derniers,
    ``max_12``. Et la taille en logarithme de la capitalisation, ``size``,
    quand elle est fournie.

    .. math::

        mom_{12,1} = \prod_{k=1}^{11}(1 + r_{t-k}) - 1

    **Les hypothèses.** Le tableau est mensuel, sans trou de date. Un titre
    absent un mois a une caractéristique manquante, pas nulle.

    **La provenance.** Jegadeesh et Titman (1993) pour le momentum, De Bondt
    et Thaler (1985) pour le renversement à long terme, Bali, Cakici et
    Whitelaw (2011) pour le rendement le plus élevé. Les trois sont rapportés
    par Gu, Kelly et Xiu (2020), annexe A.

    **Les limites.** Six caractéristiques contre quatre-vingt-quatorze dans
    l'article ; ni volume, ni écart acheteur-vendeur, ni jours sans
    transaction, que le cache de l'étude 004 ne porte pas.

    **Les alternatives.** Les mêmes sur des rendements quotidiens, plus fines
    et plus bruitées.

    **Pourquoi cette méthode ici.** Les fabriques de :mod:`quantlab.features`
    portent déjà la règle causale, et le test le vérifie sur ce constructeur.

    **Comment vérifier.** :func:`quantlab.features.transforms.assert_causal`
    appliqué au constructeur entier ne trouve aucune fuite ; et sur un
    rendement constant de 1 %, ``mom_12_1`` vaut :math:`1{,}01^{11} - 1`.

    Args:
        returns: le tableau large des rendements mensuels simples.
        market_equity: le tableau large de la capitalisation, ou ``None``.

    Returns:
        Le panneau long des caractéristiques de prix, manquants conservés.

    Raises:
        DataQualityError: le tableau porte une valeur infinie.
    """
    values = returns.sort_index().astype(float)
    if bool(np.isinf(values.to_numpy(dtype=float)).any()):
        raise DataQualityError("un rendement infini ne se compose pas.")
    prices = (1.0 + values.fillna(0.0)).cumprod().where(values.notna())
    columns = {
        "mom_12_1": momentum(prices, lookback=12, skip=1),
        "rev_1": values,
        "mom_36_13": momentum(prices, lookback=36, skip=12),
        "vol_12": rolling_std(values, 12, min_periods=12),
        "max_12": rolling_max(values, 12, min_periods=12),
    }
    if market_equity is not None:
        equity = market_equity.sort_index().astype(float).reindex(values.index)
        columns["size"] = np.log(equity.where(equity > 0.0))
    long = pd.concat({name: to_long(frame, name) for name, frame in columns.items()}, axis=1)
    long.columns = list(columns)
    return long

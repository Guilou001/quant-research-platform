r"""Le coefficient d'information : ce qu'un signal transversal prédit vraiment.

**Le problème.** Un signal transversal, c'est-à-dire un nombre attribué à chaque
actif à chaque date, prétend classer les actifs du plus mauvais au meilleur. La
question n'est pas de savoir s'il a raison en moyenne sur un titre, mais si son
ORDRE est le bon. Un modèle qui prévoit +2 % pour tous les titres d'un panier
qui monte de 20 % a une erreur quadratique énorme et un classement parfait. Un
modèle bien calibré en niveau, mais qui inverse deux titres sur trois, ne
rapporte rien au gérant qui achète les premiers et vend les derniers.

**La réponse du module.** Le coefficient d'information, la corrélation
transversale entre la prédiction et le rendement réalisé de la période suivante,
mesure exactement cet ordre. Sa version de Spearman le fait sur les rangs, donc
sans se laisser dicter le résultat par trois valeurs extrêmes.

**La convention d'alignement, qui décide de tout.** Ce module ne décale AUCUNE
série. Le tableau ``realized_panel`` que vous lui passez doit déjà porter, à la
ligne de la date :math:`t`, le rendement gagné APRÈS :math:`t`. Le décalage est
laissé à l'appelant pour une raison : un décalage caché dans une fonction de
mesure est la façon la plus courante de publier un coefficient d'information
gonflé par de l'information future. Voir la règle 1 du laboratoire, et
:class:`quantlab.core.errors.LookAheadError`.

**Provenance.** Grinold (1989), « The fundamental law of active management »,
*Journal of Portfolio Management* 15(3), 30-37. Grinold et Kahn (1999),
*Active Portfolio Management*, 2e édition, chapitres 5 et 6. Clarke, de Silva et
Thorley (2002), « Portfolio constraints and the fundamental law of active
management », *Financial Analysts Journal* 58(5), 48-66.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from enum import StrEnum

import numpy as np
import pandas as pd

from quantlab.core.calendars import annualization_factor
from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.logging import get_logger
from quantlab.core.types import Frequency

__all__ = [
    "DEFAULT_MIN_NAMES",
    "DEFAULT_MIN_PERIODS",
    "BreadthMethod",
    "ICMethod",
    "ICSummary",
    "QuantileWeighting",
    "SpreadTest",
    "effective_breadth",
    "equicorrelated_breadth",
    "fundamental_law",
    "ic_by_group",
    "ic_series",
    "ic_summary",
    "information_coefficient",
    "quantile_returns",
    "quantile_spread",
    "rolling_ic",
]

log = get_logger(__name__)

#: Nombre minimal d'actifs sous lequel un coefficient transversal ne veut rien dire.
#: Cinq est un plancher déclaré, pas une mesure. Modélisé : sous l'hypothèse nulle
#: d'indépendance, l'écart type de la corrélation de Spearman vaut environ
#: :math:`1/\sqrt{n-1}`, soit 0,50 pour cinq noms.
DEFAULT_MIN_NAMES = 5

#: Nombre minimal de dates exigé pour résumer une série de coefficients. Deux est
#: le minimum arithmétique, l'écart type d'échantillon n'étant pas défini en deçà.
DEFAULT_MIN_PERIODS = 2


class ICMethod(StrEnum):
    """La corrélation employée pour le coefficient d'information.

    ``SPEARMAN`` corrèle les rangs, ``PEARSON`` corrèle les valeurs. Le choix
    n'est pas cosmétique : sur un panier d'actions, la distribution des
    rendements a des queues épaisses, et une seule valeur extrême déplace la
    corrélation de Pearson de plusieurs points. Le rang, lui, est borné par
    construction.
    """

    SPEARMAN = "spearman"
    PEARSON = "pearson"


class QuantileWeighting(StrEnum):
    """La pondération à l'intérieur d'un quantile.

    ``EQUAL`` donne le même poids à chaque nom, ``VALUE`` un poids proportionnel
    à une grandeur fournie, typiquement la capitalisation boursière. L'écart
    entre les deux mesure la part du résultat qui vient des petites
    capitalisations, souvent la moins négociable.
    """

    EQUAL = "equal"
    VALUE = "value"


class BreadthMethod(StrEnum):
    """La façon de compter les paris effectivement indépendants.

    ``PARTICIPATION_RATIO`` rend l'inverse de la somme des carrés des valeurs
    propres normalisées, ``ENTROPY`` l'exponentielle de leur entropie de
    Shannon. Les deux valent :math:`N` sur une matrice identité et chutent quand
    la corrélation monte ; l'entropie chute moins vite.
    """

    PARTICIPATION_RATIO = "participation_ratio"
    ENTROPY = "entropy"


@dataclass(frozen=True, slots=True)
class ICSummary:
    """Le résumé chiffré d'une série de coefficients d'information.

    Attributes:
        n_periods: le nombre de dates où le coefficient est défini.
        mean: la moyenne des coefficients.
        median: leur médiane, moins sensible à une date extrême que la moyenne.
        std: leur écart type d'échantillon, dénominateur :math:`n - 1`.
        ir_per_period: le rapport moyenne sur écart type, non annualisé.
        ir_annualized: le même rapport multiplié par la racine du nombre de
            périodes par an.
        t_stat_hac: le t de Student de la moyenne, écart type corrigé de
            l'autocorrélation et de l'hétéroscédasticité.
        hac_lags: le nombre de retards retenus pour cette correction.
        hit_rate: la part des dates où le coefficient est strictement positif.
    """

    n_periods: int
    mean: float
    median: float
    std: float
    ir_per_period: float
    ir_annualized: float
    t_stat_hac: float
    hac_lags: int
    hit_rate: float

    def as_dict(self) -> dict[str, float]:
        """Rend le résumé sous forme de dictionnaire, prêt pour un tableau."""
        return dict(asdict(self))


@dataclass(frozen=True, slots=True)
class SpreadTest:
    """Le test du rendement d'un écart long-short entre deux quantiles.

    Attributes:
        n_periods: le nombre de dates où l'écart est défini.
        mean: le rendement moyen de l'écart, par période.
        mean_annualized: la moyenne multipliée par le nombre de périodes par an,
            annualisation arithmétique déclarée, sans composition.
        std: l'écart type d'échantillon des rendements de l'écart.
        t_stat_hac: le t de Student de la moyenne, corrigé à la Newey-West.
        hac_lags: le nombre de retards retenus.
        hit_rate: la part des dates où l'écart est strictement positif.
        low: le nom de la colonne vendue.
        high: le nom de la colonne achetée.
    """

    n_periods: int
    mean: float
    mean_annualized: float
    std: float
    t_stat_hac: float
    hac_lags: int
    hit_rate: float
    low: str
    high: str


# --------------------------------------------------------------------------- #
# Outils internes
# --------------------------------------------------------------------------- #


def _newey_west_lags(n_periods: int) -> int:
    r"""Rend le nombre de retards de la règle automatique de Newey et West (1994).

    .. math::

        L = \left\lfloor 4 \left(\frac{T}{100}\right)^{2/9} \right\rfloor

    Args:
        n_periods: le nombre d'observations :math:`T`.

    Returns:
        Le nombre de retards, au moins zéro et au plus :math:`T - 1`.

    Note:
        Règle usuelle, pas une optimisation. Newey et West (1994), « Automatic
        lag selection in covariance matrix estimation », *Review of Economic
        Studies* 61(4), 631-653.
    """
    if n_periods < 2:
        return 0
    lags = math.floor(4.0 * (n_periods / 100.0) ** (2.0 / 9.0))
    return max(0, min(lags, n_periods - 1))


def _hac_variance_of_mean(values: np.ndarray, lags: int) -> float:
    r"""Rend la variance de la moyenne corrigée à la Newey-West.

    **Le problème.** Le t de Student ordinaire divise la moyenne par
    :math:`s / \sqrt{T}`, ce qui suppose des observations indépendantes. Une
    série de coefficients d'information ne l'est pas : un signal lent garde le
    même classement plusieurs mois d'affilée, si bien que le t ordinaire compte
    la même information plusieurs fois et gonfle la significativité.

    .. math::

        \widehat{\operatorname{Var}}(\bar{x}) = \frac{1}{T}
        \left[ \hat\gamma_0 + 2 \sum_{\ell=1}^{L}
        \left(1 - \frac{\ell}{L+1}\right) \hat\gamma_\ell \right],
        \qquad
        \hat\gamma_\ell = \frac{1}{T} \sum_{t=\ell+1}^{T}
        (x_t - \bar{x})(x_{t-\ell} - \bar{x})

    Args:
        values: les observations, sans valeur manquante.
        lags: le nombre de retards :math:`L` du noyau de Bartlett.

    Returns:
        L'estimateur de la variance de la moyenne. Vaut zéro sur une série
        constante.

    Note:
        Newey et West (1987), *Econometrica* 55(3), 703-708. Aucune correction
        de petit échantillon n'est appliquée, ce qui correspond à
        ``statsmodels`` avec ``use_correction=False``. Le noyau de Bartlett rend
        l'estimateur positif ou nul par construction.
    """
    n = values.size
    centered = values - values.mean()
    total = float(centered @ centered) / n
    for lag in range(1, lags + 1):
        weight = 1.0 - lag / (lags + 1.0)
        gamma = float(centered[lag:] @ centered[:-lag]) / n
        total += 2.0 * weight * gamma
    return total / n


def _hac_t_stat(values: np.ndarray, lags: int | None) -> tuple[float, int]:
    """Rend le t de Student de la moyenne et le nombre de retards employé."""
    n = values.size
    if n < DEFAULT_MIN_PERIODS:
        return float("nan"), 0
    chosen = _newey_west_lags(n) if lags is None else int(lags)
    if chosen < 0:
        raise ConfigError("hac_lags doit être positif ou nul")
    chosen = min(chosen, n - 1)
    variance = _hac_variance_of_mean(values, chosen)
    if variance <= 0.0:
        return float("nan"), chosen
    return float(values.mean() / math.sqrt(variance)), chosen


def _aligned_pair(predictions: pd.Series, realized: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Rend les deux séries restreintes aux actifs communs et sans valeur manquante."""
    for name, series in (("predictions", predictions), ("realized", realized)):
        if series.index.has_duplicates:
            raise DataQualityError(f"{name} porte des identifiants d'actif en double")
    joined = pd.concat({"pred": predictions, "real": realized}, axis="columns", join="inner").dropna()
    return joined["pred"], joined["real"]


def _correlation(predictions: pd.Series, realized: pd.Series, method: ICMethod) -> float:
    """Rend la corrélation demandée, ou ``nan`` si l'une des séries est constante."""
    left = predictions.astype(float)
    right = realized.astype(float)
    if method is ICMethod.SPEARMAN:
        left = left.rank(method="average")
        right = right.rank(method="average")
    x = left.to_numpy()
    y = right.to_numpy()
    if x.std(ddof=1) == 0.0 or y.std(ddof=1) == 0.0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def _summary_fields(values: np.ndarray, periods_per_year: float, hac_lags: int | None) -> ICSummary:
    """Rend le résumé d'un vecteur déjà nettoyé, sans exiger de taille minimale."""
    n = int(values.size)
    if n == 0:
        return ICSummary(0, *([float("nan")] * 6), 0, float("nan"))
    mean = float(values.mean())
    median = float(np.median(values))
    std = float(values.std(ddof=1)) if n >= DEFAULT_MIN_PERIODS else float("nan")
    ir = mean / std if std and not math.isnan(std) else float("nan")
    t_stat, lags = _hac_t_stat(values, hac_lags)
    return ICSummary(
        n_periods=n,
        mean=mean,
        median=median,
        std=std,
        ir_per_period=ir,
        ir_annualized=ir * math.sqrt(periods_per_year),
        t_stat_hac=t_stat,
        hac_lags=lags,
        hit_rate=float((values > 0.0).mean()),
    )


# --------------------------------------------------------------------------- #
# Le coefficient d'information
# --------------------------------------------------------------------------- #


def information_coefficient(
    predictions: pd.Series,
    realized: pd.Series,
    *,
    method: ICMethod | str = ICMethod.SPEARMAN,
    min_names: int = DEFAULT_MIN_NAMES,
) -> float:
    r"""Rend le coefficient d'information transversal d'une seule date.

    **Le problème.** Un signal attribue un nombre à chaque actif. Savoir s'il
    « marche » revient à savoir si ce nombre ordonne correctement les rendements
    à venir, et non s'il en devine le niveau.

    **L'intuition.** On classe les actifs par prédiction, on les classe par
    rendement réalisé, et on regarde si les deux classements se ressemblent. Un
    coefficient de +1 dit que l'ordre est exactement le bon, zéro que le signal
    n'apprend rien, -1 que le signal est parfaitement à l'envers, ce qui est une
    découverte et non un échec.

    .. math::

        \mathrm{IC}_t = \operatorname{corr}\big(
        \operatorname{rg}(\hat{r}_{i,t}), \operatorname{rg}(r_{i,t+1})
        \big)_{i \in \mathcal{U}_t}

    Définition de chaque variable :

    - :math:`\hat{r}_{i,t}` la prédiction portée sur l'actif :math:`i` à la date
      :math:`t` ;
    - :math:`r_{i,t+1}` le rendement que l'actif :math:`i` a réellement gagné
      après :math:`t` ;
    - :math:`\operatorname{rg}(\cdot)` le rang dans la coupe transversale, les
      ex aequo recevant le rang moyen ;
    - :math:`\mathcal{U}_t` l'univers des actifs cotés à la date :math:`t` ;
    - :math:`\operatorname{corr}` la corrélation linéaire de Pearson, appliquée
      aux rangs, ce qui donne la corrélation de Spearman.

    **Hypothèses.** Les deux séries portent le même identifiant d'actif dans
    leur index. Le rendement réalisé est déjà aligné sur la date de la
    prédiction, sans décalage à faire ici. L'univers est le même pour les deux,
    l'intersection étant prise sans avertissement.

    **Provenance.** Grinold (1989) définit le coefficient d'information comme la
    corrélation entre prévision et réalisation. Spearman (1904), « The proof and
    measurement of association between two things », *American Journal of
    Psychology* 15(1), 72-101, pour la corrélation des rangs.

    **Limites.** Un coefficient élevé ne dit rien du rendement encaissable : il
    ignore les coûts, la capacité et la concentration du signal. Modélisé : sur
    douze actifs, l'écart type du coefficient sous l'hypothèse nulle vaut
    :math:`1/\sqrt{11} = 0{,}30`, si bien qu'une valeur isolée ne s'interprète
    pas. La corrélation des
    rangs traite l'écart entre le premier et le deuxième comme l'écart entre le
    neuvième et le dixième, ce qui écrase l'information de conviction.

    **Alternatives.** La corrélation de Pearson garde les niveaux mais subit les
    valeurs extrêmes. Le tau de Kendall est plus robuste encore et plus lent à
    calculer. Le rendement d'un portefeuille trié par quantiles, que rend
    :func:`quantile_returns`, mesure ce qui est encaissable plutôt que ce qui
    est corrélé.

    **Pourquoi Spearman par défaut.** Les rendements d'actions ont des queues
    épaisses, et une seule valeur extrême déplace la corrélation de Pearson de
    plusieurs points. Le classement est aussi ce que consomme réellement un
    portefeuille construit par tri.

    **Comment vérifier.** Une prédiction égale au rendement réalisé, ou à
    n'importe quelle transformation strictement croissante de celui-ci, doit
    rendre +1 à la précision machine ; l'ordre inversé, -1. La valeur doit
    coïncider avec ``scipy.stats.spearmanr`` sur les mêmes intrants. Les deux
    contrôles sont dans ``tests/unit/test_analytics_ic.py``.

    Args:
        predictions: le signal, indexé par identifiant d'actif.
        realized: le rendement réalisé après la date, même index.
        method: ``"spearman"`` pour les rangs, ``"pearson"`` pour les valeurs.
        min_names: le nombre d'actifs communs sous lequel la fonction rend
            ``nan``. Défaut cinq, plancher déclaré.

    Returns:
        Le coefficient d'information, entre -1 et 1. Rend ``nan`` si moins de
        ``min_names`` actifs sont communs et renseignés, ou si l'une des deux
        coupes est constante, la corrélation n'étant alors pas définie.

    Raises:
        ConfigError: si ``min_names`` est inférieur à deux.
        DataQualityError: si un identifiant d'actif apparaît deux fois.

    Example:
        >>> import pandas as pd
        >>> pred = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0], index=list("abcde"))
        >>> real = pd.Series([0.01, 0.02, 0.03, 0.04, 0.05], index=list("abcde"))
        >>> round(information_coefficient(pred, real), 12)
        1.0

    Note:
        Le ``nan`` rendu sur un univers trop mince est délibéré. Une date sans
        assez de noms est un événement normal en début d'échantillon, et la
        série de coefficients doit porter le trou plutôt que d'arrêter le
        pipeline. Le comptage des trous se lit sur ``n_periods`` du résumé.
    """
    if min_names < 2:
        raise ConfigError("min_names doit valoir au moins 2, une corrélation exigeant deux points")
    kind = ICMethod(method)
    left, right = _aligned_pair(predictions, realized)
    if len(left) < min_names:
        return float("nan")
    return _correlation(left, right, kind)


def ic_series(
    predictions_panel: pd.DataFrame,
    realized_panel: pd.DataFrame,
    *,
    method: ICMethod | str = ICMethod.SPEARMAN,
    min_names: int = DEFAULT_MIN_NAMES,
) -> pd.Series:
    """Rend la série temporelle des coefficients d'information, une valeur par date.

    Les deux tableaux ont les dates en lignes et les actifs en colonnes.
    L'intersection est prise sur les deux axes, sans réordonnancement : l'ordre
    des dates et des colonnes du tableau de prédictions gouverne.

    Args:
        predictions_panel: le signal, dates en lignes, actifs en colonnes.
        realized_panel: les rendements déjà alignés sur la date du signal.
        method: ``"spearman"`` ou ``"pearson"``.
        min_names: le seuil transversal, voir :func:`information_coefficient`.

    Returns:
        Une série nommée ``"ic"``, indexée par les dates communes, portant
        ``nan`` aux dates où l'univers est trop mince.

    Raises:
        DataQualityError: si une date apparaît deux fois dans un index.
        InsufficientDataError: si les deux tableaux n'ont aucune date commune,
            ou aucun actif commun.

    Note:
        Aucun décalage n'est fait ici. Si ``realized_panel`` porte le rendement
        de la période en cours et non de la suivante, le coefficient mesure de
        l'information future, et le chiffre publié est faux sans que rien ne le
        signale.
    """
    for name, frame in (("predictions_panel", predictions_panel), ("realized_panel", realized_panel)):
        if frame.index.has_duplicates:
            raise DataQualityError(f"{name} porte des dates en double")
        if frame.columns.has_duplicates:
            raise DataQualityError(f"{name} porte des actifs en double")

    dates = predictions_panel.index.intersection(realized_panel.index, sort=False)
    assets = predictions_panel.columns.intersection(realized_panel.columns, sort=False)
    if len(dates) == 0:
        raise InsufficientDataError("aucune date commune entre les deux tableaux")
    if len(assets) == 0:
        raise InsufficientDataError("aucun actif commun entre les deux tableaux")

    left = predictions_panel.loc[dates, assets]
    right = realized_panel.loc[dates, assets]
    kind = ICMethod(method)
    values = [
        information_coefficient(left.loc[date], right.loc[date], method=kind, min_names=min_names)
        for date in dates
    ]
    out = pd.Series(values, index=dates, name="ic", dtype=float)
    log.debug(
        "série de coefficients d'information calculée",
        extra={"n_dates": len(out), "n_assets": len(assets), "n_nan": int(out.isna().sum())},
    )
    return out


def ic_summary(
    ic: pd.Series,
    *,
    frequency: Frequency = Frequency.MONTHLY,
    hac_lags: int | None = None,
    min_periods: int = DEFAULT_MIN_PERIODS,
) -> ICSummary:
    r"""Rend le résumé d'une série de coefficients d'information.

    **Le problème.** Un coefficient moyen de 0,03 peut être une mine d'or ou du
    bruit. Ce qui tranche est sa stabilité, et le nombre de dates sur lesquelles
    il a été mesuré.

    **L'intuition.** Le rapport de la moyenne à l'écart type joue pour un signal
    le rôle que le ratio de Sharpe joue pour une stratégie : il dit combien de
    fois la régularité dépasse le bruit.

    .. math::

        \mathrm{IR}_{\mathrm{IC}} = \frac{\overline{\mathrm{IC}}}
        {\sigma(\mathrm{IC})} \sqrt{N},
        \qquad
        t = \frac{\overline{\mathrm{IC}}}
        {\sqrt{\widehat{\operatorname{Var}}_{\mathrm{HAC}}(\overline{\mathrm{IC}})}}

    Définition de chaque variable :

    - :math:`\overline{\mathrm{IC}}` la moyenne des coefficients sur les dates
      où ils sont définis ;
    - :math:`\sigma(\mathrm{IC})` leur écart type d'échantillon, dénominateur
      :math:`n - 1` ;
    - :math:`N` le nombre de périodes par an de la fréquence déclarée ;
    - :math:`\widehat{\operatorname{Var}}_{\mathrm{HAC}}` la variance de la
      moyenne corrigée de l'autocorrélation, voir :func:`_hac_variance_of_mean`.

    **Hypothèses.** Les dates sont régulièrement espacées à la fréquence
    déclarée. Les coefficients manquants sont retirés, pas remplacés par zéro,
    ce qui suppose que leur absence ne dépend pas de leur valeur.

    **Provenance.** Grinold et Kahn (1999), chapitre 6, pour le rapport de la
    moyenne à l'écart type. Newey et West (1987) pour la correction du t.

    **Limites.** Le t corrigé reste optimiste sur moins de cinquante dates, la
    correction HAC étant asymptotique. La part de dates positives ne dit rien de
    l'ampleur : un signal qui gagne petit sept fois et perd gros trois fois
    affiche 70 % et ne rapporte rien.

    **Alternatives.** Un bootstrap par blocs donne un intervalle sans hypothèse
    asymptotique et coûte plus cher. Le ratio de Sharpe dégonflé de Bailey et
    López de Prado (2014) corrige en plus l'essai multiple, ce que ce résumé ne
    fait pas.

    **Pourquoi ce choix.** La correction HAC est le minimum honnête sur une
    série de signal, dont l'autocorrélation est la règle et non l'exception. Le
    nombre de retards suit une règle automatique publiée plutôt qu'un chiffre
    choisi à la main.

    **Comment vérifier.** Le t doit coïncider avec celui d'une régression de la
    série sur une constante, ``statsmodels`` en ``cov_type="HAC"`` avec
    ``use_correction=False``. Ce contrôle est dans les tests.

    Args:
        ic: la série des coefficients, valeurs manquantes admises.
        frequency: la fréquence des dates, qui fixe l'annualisation.
        hac_lags: le nombre de retards. ``None`` applique la règle automatique
            de Newey et West (1994).
        min_periods: le nombre de dates valides exigé, deux par défaut.

    Returns:
        Un :class:`ICSummary`.

    Raises:
        InsufficientDataError: si moins de ``min_periods`` dates sont valides.

    Example:
        Sur une série qui vaut 0,10 puis 0,00, la moyenne fait 0,05, l'écart
        type d'échantillon :math:`0,10 / \sqrt{2} = 0,0707`, et le rapport des
        deux 0,7071.
    """
    values = pd.Series(ic).dropna().to_numpy(dtype=float)
    if values.size < min_periods:
        raise InsufficientDataError(
            f"{values.size} coefficient(s) valide(s), {min_periods} exigé(s) pour un résumé"
        )
    return _summary_fields(values, annualization_factor(frequency), hac_lags)


def rolling_ic(
    ic: pd.Series,
    *,
    window: int,
    min_periods: int | None = None,
    frequency: Frequency = Frequency.MONTHLY,
) -> pd.DataFrame:
    """Rend la moyenne, l'écart type et le ratio d'information glissants du coefficient.

    **Le problème.** Un coefficient moyen calculé sur vingt ans peut cacher dix
    ans de signal et dix ans de rien. La moyenne glissante montre quand le
    signal a cessé de fonctionner, ce que la moyenne globale efface.

    Args:
        ic: la série des coefficients.
        window: la largeur de la fenêtre, en nombre de dates.
        min_periods: le nombre minimal d'observations valides dans la fenêtre.
            ``None`` exige la fenêtre pleine.
        frequency: la fréquence, qui fixe l'annualisation du ratio.

    Returns:
        Un tableau indexé comme ``ic``, colonnes ``mean``, ``std`` et
        ``ir_annualized``.

    Raises:
        ConfigError: si ``window`` est inférieur à deux.

    Note:
        La fenêtre est fermée à droite et inclut la date courante, comme partout
        dans pandas. Un signal lu en temps réel à la date :math:`t` ne voit donc
        rien d'autre que le passé, la valeur de :math:`t` incluse.

    Note:
        Une fenêtre d'écart type nul rend ``nan`` sur le ratio, et non l'infini.
        La division brute donnerait un infini signé sur une fenêtre constante,
        chiffre qui n'a aucun sens et qui se propagerait dans un tableau publié.
        La convention est celle de :func:`ic_summary`, qui rend déjà ``nan`` dans
        ce cas.
    """
    if window < DEFAULT_MIN_PERIODS:
        raise ConfigError("window doit valoir au moins 2, l'écart type exigeant deux points")
    series = pd.Series(ic, dtype=float)
    roll = series.rolling(window=window, min_periods=min_periods)
    mean = roll.mean()
    std = roll.std(ddof=1)
    defined = std > 0.0
    ratio = (mean / std.where(defined)).where(defined)
    ir = ratio * math.sqrt(annualization_factor(frequency))
    return pd.DataFrame({"mean": mean, "std": std, "ir_annualized": ir})


def ic_by_group(
    ic: pd.Series,
    groups: pd.Series,
    *,
    frequency: Frequency = Frequency.MONTHLY,
    hac_lags: int | None = None,
) -> pd.DataFrame:
    """Rend le résumé du coefficient d'information par groupe de dates.

    Sert à découper par régime, par exemple les mois de volatilité haute contre
    basse, ou les phases de hausse contre baisse du marché.

    **Une mise en garde qui compte plus que la formule.** Les groupes se
    définissent AVANT de regarder les résultats. Un découpage choisi après coup
    parce qu'il fait ressortir un sous-échantillon flatteur est un essai
    multiple déguisé, et le t affiché ne vaut plus rien. La règle 8 du
    laboratoire exige que les découpages essayés soient tous consignés.

    Args:
        ic: la série des coefficients.
        groups: l'étiquette de régime de chaque date, même index que ``ic``.
        frequency: la fréquence, pour l'annualisation.
        hac_lags: le nombre de retards de la correction du t.

    Returns:
        Un tableau indexé par étiquette de groupe, dans l'ordre de première
        apparition, portant les mêmes colonnes qu'un :class:`ICSummary`. Un
        groupe d'une seule date porte ``nan`` sur l'écart type et les ratios.

    Raises:
        InsufficientDataError: si aucune date n'est commune aux deux séries.
    """
    joined = pd.concat({"ic": pd.Series(ic, dtype=float), "group": groups}, axis="columns", join="inner")
    joined = joined.dropna(subset=["ic", "group"])
    if joined.empty:
        raise InsufficientDataError("aucune date commune entre les coefficients et les groupes")
    periods_per_year = annualization_factor(frequency)
    rows: dict[object, dict[str, float]] = {}
    for label in pd.unique(joined["group"]):
        values = joined.loc[joined["group"] == label, "ic"].to_numpy(dtype=float)
        rows[label] = _summary_fields(values, periods_per_year, hac_lags).as_dict()
    return pd.DataFrame.from_dict(rows, orient="index")


# --------------------------------------------------------------------------- #
# Le tri par quantiles
# --------------------------------------------------------------------------- #


def _quantile_labels(n_quantiles: int) -> list[str]:
    """Rend les noms de colonnes ``Q1`` à ``Qn``, du plus bas signal au plus haut."""
    return [f"Q{k}" for k in range(1, n_quantiles + 1)]


def _bucket_of_rank(ranks: np.ndarray, n_names: int, n_quantiles: int) -> np.ndarray:
    r"""Rend le numéro de quantile de chaque rang, à partir de zéro.

    .. math::

        q_i = \min\left(
        \left\lfloor \frac{Q \, (\mathrm{rg}_i - 1)}{n} \right\rfloor,
        Q - 1 \right)

    Args:
        ranks: les rangs croissants, de 1 à ``n_names``, sans ex aequo.
        n_names: le nombre d'actifs classés.
        n_quantiles: le nombre de paquets voulus.

    Returns:
        Le numéro de paquet de chaque actif, de zéro à ``n_quantiles - 1``.

    Note:
        Ce découpage à partir des rangs est préféré à ``pandas.qcut`` sur les
        valeurs : il ne peut pas échouer sur des bornes en double, cas fréquent
        quand un signal prend peu de valeurs distinctes.

    Note:
        Quand ``n_names`` n'est pas divisible par ``n_quantiles``, les noms en
        surplus ne vont PAS tous aux premiers paquets. Ils se répartissent selon
        la partie entière de la formule, et le motif dépend du reste de la
        division. Mesuré sur cinq quantiles, sept noms donnent des paquets de
        2, 1, 2, 1 et 1. Douze noms donnent 3, 2, 3, 2 et 2. Treize noms donnent
        3, 3, 2, 3 et 2. L'écart entre le plus gros et le plus petit paquet ne
        dépasse jamais un nom. Écart déclaré, non corrigé.
    """
    return np.minimum((n_quantiles * (ranks - 1)) // n_names, n_quantiles - 1)


def quantile_returns(
    predictions_panel: pd.DataFrame,
    realized_panel: pd.DataFrame,
    *,
    n_quantiles: int = 5,
    weighting: QuantileWeighting | str = QuantileWeighting.EQUAL,
    value_panel: pd.DataFrame | None = None,
    min_names: int | None = None,
) -> pd.DataFrame:
    r"""Rend le rendement de chaque quantile de signal, date par date, et leur écart.

    **Le problème.** Le coefficient d'information dit que l'ordre est bon, il ne
    dit pas combien un gérant encaisse. Le tri par quantiles répond à la seconde
    question : on achète le paquet des meilleurs signaux, on vend celui des
    pires, et on regarde ce que rapporte l'écart.

    **L'intuition.** Trier plutôt que corréler a un mérite : le résultat est un
    rendement, en pourcentage, comparable à celui d'un fonds. Le défaut est
    symétrique : le tri jette l'information sur l'ampleur du signal à
    l'intérieur d'un paquet.

    .. math::

        r^{(q)}_{t} = \sum_{i \in \mathcal{Q}_{q,t}} w_{i,t} \, r_{i,t+1},
        \qquad
        \text{écart}_t = r^{(Q)}_t - r^{(1)}_t

    Définition de chaque variable :

    - :math:`\mathcal{Q}_{q,t}` l'ensemble des actifs du quantile :math:`q` à la
      date :math:`t`, le quantile 1 portant les signaux les plus bas ;
    - :math:`w_{i,t}` le poids de l'actif dans son quantile, égal à
      :math:`1/|\mathcal{Q}_{q,t}|` en pondération égale, proportionnel à la
      valeur fournie sinon ;
    - :math:`r_{i,t+1}` le rendement réalisé après la date, déjà aligné ;
    - :math:`Q` le nombre de quantiles.

    **Hypothèses.** Le rééquilibrage a lieu à chaque date de l'index, sans coût.
    Les rendements sont ceux d'un actif détenu la période entière. Les ex aequo
    de signal sont départagés par l'ordre des colonnes, convention déclarée qui
    n'a d'effet que sur un signal très discret.

    **Provenance.** Le tri par déciles remonte à Jegadeesh et Titman (1993),
    « Returns to buying winners and selling losers », *Journal of Finance*
    48(1), 65-91. La construction par paquets triés vient de Fama et French
    (1993).

    **Limites.** Aucun coût, aucune contrainte de liquidité, aucun décalage
    d'exécution. Le résultat brut d'un écart long-short surestime donc ce qui
    est encaissable, d'autant plus que la rotation est forte. La pondération
    égale donne un poids identique à une capitalisation de cent millions et à
    une de cent milliards, ce qui gonfle presque toujours le rendement affiché.

    **Alternatives.** Une régression transversale à la Fama-MacBeth rend une
    prime par unité de signal plutôt qu'un écart entre paquets. Un portefeuille
    optimisé sous contraintes mesure ce qui reste après contraintes, ce que
    fait ``quantlab.portfolio``.

    **Pourquoi ce choix.** Le tri est le seul chiffre directement lisible par un
    gérant, et le seul comparable aux tableaux publiés dans la littérature.

    **Comment vérifier.** Sur un panier construit à la main, chaque moyenne de
    quantile se recalcule à la main. Un signal égal au rendement réalisé doit
    donner un écart positif à chaque date. Les deux contrôles sont dans les
    tests.

    Args:
        predictions_panel: le signal, dates en lignes, actifs en colonnes.
        realized_panel: les rendements déjà alignés sur la date du signal.
        n_quantiles: le nombre de paquets, cinq par défaut.
        weighting: ``"equal"`` ou ``"value"``.
        value_panel: la grandeur de pondération, exigée si ``weighting="value"``.
            Ses valeurs doivent être positives ou nulles.
        min_names: le nombre d'actifs sous lequel la date rend une ligne de
            ``nan``. ``None`` exige un actif par quantile, soit ``n_quantiles``.
            Une valeur inférieure à ``n_quantiles`` est refusée : un quantile
            vide n'a pas de rendement, et relever le plancher en silence
            changerait le sens de l'argument sans le dire.

    Returns:
        Un tableau indexé par date, colonnes ``Q1`` à ``Qn`` puis ``spread``,
        cette dernière valant ``Qn`` moins ``Q1``.

    Raises:
        ConfigError: si ``n_quantiles`` est inférieur à deux, si ``min_names``
            est inférieur à ``n_quantiles``, ou si la pondération par valeur est
            demandée sans ``value_panel``.
        DataQualityError: si ``value_panel`` porte une valeur négative, ou si un
            tableau porte une date ou un actif en double.
        InsufficientDataError: s'il n'y a aucune date ou aucun actif commun.

    Example:
        Dix actifs, cinq quantiles, donc deux noms par paquet. Si le signal
        classe les actifs dans l'ordre de leurs rendements 1 %, 2 %, ..., 10 %,
        alors ``Q1`` vaut 1,5 %, ``Q5`` vaut 9,5 %, et l'écart 8,0 %.
    """
    if n_quantiles < 2:
        raise ConfigError("n_quantiles doit valoir au moins 2")
    if min_names is not None and int(min_names) < n_quantiles:
        raise ConfigError(
            f"min_names vaut {min_names} pour {n_quantiles} quantiles : un paquet resterait vide"
        )
    scheme = QuantileWeighting(weighting)
    if scheme is QuantileWeighting.VALUE and value_panel is None:
        raise ConfigError("la pondération par valeur exige value_panel")

    frames = [("predictions_panel", predictions_panel), ("realized_panel", realized_panel)]
    if value_panel is not None:
        frames.append(("value_panel", value_panel))
    for name, frame in frames:
        if frame.index.has_duplicates:
            raise DataQualityError(f"{name} porte des dates en double")
        if frame.columns.has_duplicates:
            raise DataQualityError(f"{name} porte des actifs en double")

    dates = predictions_panel.index.intersection(realized_panel.index, sort=False)
    assets = predictions_panel.columns.intersection(realized_panel.columns, sort=False)
    if scheme is QuantileWeighting.VALUE and value_panel is not None:
        dates = dates.intersection(value_panel.index, sort=False)
        assets = assets.intersection(value_panel.columns, sort=False)
    if len(dates) == 0:
        raise InsufficientDataError("aucune date commune entre les tableaux")
    if len(assets) == 0:
        raise InsufficientDataError("aucun actif commun entre les tableaux")

    floor_names = n_quantiles if min_names is None else int(min_names)
    labels = _quantile_labels(n_quantiles)
    signals = predictions_panel.loc[dates, assets]
    outcomes = realized_panel.loc[dates, assets]
    values = value_panel.loc[dates, assets] if scheme is QuantileWeighting.VALUE else None
    if values is not None and bool((values.to_numpy(dtype=float) < 0).any()):
        raise DataQualityError("value_panel porte une valeur négative, une pondération l'exige positive")

    rows: list[dict[str, float]] = []
    for date in dates:
        row = dict.fromkeys(labels, float("nan"))
        frame = pd.DataFrame({"signal": signals.loc[date], "outcome": outcomes.loc[date]})
        if values is not None:
            frame["value"] = values.loc[date]
        frame = frame.dropna()
        n_names = len(frame)
        if n_names >= floor_names:
            ranks = frame["signal"].rank(method="first").to_numpy(dtype=np.int64)
            buckets = _bucket_of_rank(ranks, n_names, n_quantiles)
            for index, label in enumerate(labels):
                mask = buckets == index
                if not mask.any():
                    continue
                outcome = frame["outcome"].to_numpy(dtype=float)[mask]
                if values is None:
                    row[label] = float(outcome.mean())
                    continue
                weight = frame["value"].to_numpy(dtype=float)[mask]
                total = float(weight.sum())
                row[label] = float(weight @ outcome / total) if total > 0.0 else float("nan")
        rows.append(row)

    table = pd.DataFrame(rows, index=dates, columns=labels, dtype=float)
    table["spread"] = table[labels[-1]] - table[labels[0]]
    return table


def quantile_spread(
    quantile_table: pd.DataFrame,
    *,
    low: str | None = None,
    high: str | None = None,
    frequency: Frequency = Frequency.MONTHLY,
    hac_lags: int | None = None,
) -> SpreadTest:
    r"""Rend le rendement moyen de l'écart long-short et son t de Student corrigé.

    **Le problème.** Un écart moyen positif ne prouve rien tant que sa
    variabilité n'est pas rapportée. Le t de Student le fait, à condition de ne
    pas supposer les périodes indépendantes, ce qu'elles ne sont pas.

    .. math::

        \bar{s} = \frac{1}{T} \sum_{t=1}^{T} s_t,
        \qquad
        t = \frac{\bar{s}}
        {\sqrt{\widehat{\operatorname{Var}}_{\mathrm{HAC}}(\bar{s})}},
        \qquad
        s_t = r^{(Q)}_t - r^{(1)}_t

    Args:
        quantile_table: le tableau rendu par :func:`quantile_returns`.
        low: le nom de la colonne vendue. ``None`` prend la première colonne de
            quantile, soit le signal le plus bas.
        high: le nom de la colonne achetée. ``None`` prend la dernière.
        frequency: la fréquence, qui fixe l'annualisation arithmétique.
        hac_lags: le nombre de retards, règle automatique si ``None``.

    Returns:
        Un :class:`SpreadTest`.

    Raises:
        ConfigError: si un nom de colonne demandé est absent du tableau.
        InsufficientDataError: si moins de deux dates portent un écart défini.

    Note:
        L'annualisation multiplie la moyenne par le nombre de périodes par an,
        sans composition. Un écart long-short n'est pas un actif détenu, la
        composition géométrique n'y a donc pas de sens évident, et le choix
        arithmétique est déclaré plutôt que caché.

    Example:
        Trois dates d'écarts 8 %, -8 % et 1 % donnent une moyenne de 0,3333 %.
    """
    columns = [name for name in quantile_table.columns if name != "spread"]
    if not columns:
        raise ConfigError("le tableau ne porte aucune colonne de quantile")
    low_name = columns[0] if low is None else low
    high_name = columns[-1] if high is None else high
    for name in (low_name, high_name):
        if name not in quantile_table.columns:
            raise ConfigError(f"colonne « {name} » absente du tableau")

    spread = (quantile_table[high_name] - quantile_table[low_name]).dropna().to_numpy(dtype=float)
    if spread.size < DEFAULT_MIN_PERIODS:
        raise InsufficientDataError(f"{spread.size} écart(s) défini(s), deux exigés pour un test")
    t_stat, lags = _hac_t_stat(spread, hac_lags)
    periods_per_year = annualization_factor(frequency)
    return SpreadTest(
        n_periods=int(spread.size),
        mean=float(spread.mean()),
        mean_annualized=float(spread.mean() * periods_per_year),
        std=float(spread.std(ddof=1)),
        t_stat_hac=t_stat,
        hac_lags=lags,
        hit_rate=float((spread > 0.0).mean()),
        low=str(low_name),
        high=str(high_name),
    )


# --------------------------------------------------------------------------- #
# La loi fondamentale de la gestion active
# --------------------------------------------------------------------------- #


def fundamental_law(ic: float, breadth: float, *, transfer_coefficient: float = 1.0) -> float:
    r"""Rend le ratio d'information promis par la loi fondamentale de Grinold.

    **Le problème.** Deux gérants annoncent la même compétence. L'un suit
    quarante titres, l'autre quatre mille. Faut-il attendre la même performance
    ajustée du risque ? Non, et la loi fondamentale dit de combien l'écart
    devrait être.

    **L'intuition.** La compétence par pari est faible et à peu près constante
    dans le métier ; ce qui se multiplie est le nombre de fois où on la joue.
    Chaque pari indépendant ajoute du signal proportionnellement à son nombre et
    du bruit proportionnellement à la racine de ce nombre, si bien que le
    rapport des deux croît comme la racine du nombre de paris. C'est le même
    mécanisme qui fait qu'un casino gagne à coup sûr avec un avantage de 1,35 %
    sur des dizaines de milliers de tours.

    .. math::

        \mathrm{IR} \approx \mathrm{TC} \times \mathrm{IC} \times \sqrt{\mathrm{BR}}

    Définition de chaque variable :

    - :math:`\mathrm{IR}` le ratio d'information, l'alpha annuel divisé par
      l'erreur de suivi annuelle ;
    - :math:`\mathrm{IC}` le coefficient d'information, la corrélation entre
      prévision et réalisation, mesurée par :func:`information_coefficient` ;
    - :math:`\mathrm{BR}` la largeur, le nombre de paris INDÉPENDANTS pris par
      an, et non le nombre de titres suivis ;
    - :math:`\mathrm{TC}` le coefficient de transfert, entre zéro et un, la
      corrélation entre le portefeuille voulu et le portefeuille réellement
      détenu après contraintes.

    **Les hypothèses, qui sont fortes.** Elles sont cinq :

    1. les paris sont indépendants ;
    2. le coefficient d'information est le même sur tous les paris, et stable
       dans le temps ;
    3. le portefeuille est construit sans contrainte, sauf à employer le
       coefficient de transfert ;
    4. le risque de chaque pari est correctement estimé ;
    5. le coefficient d'information est connu et non estimé, alors qu'en
       pratique il est lui-même bruité.

    **Provenance.** Grinold (1989), « The fundamental law of active
    management », *Journal of Portfolio Management* 15(3), 30-37. Grinold et
    Kahn (1999), *Active Portfolio Management*, 2e édition, chapitre 6, pour la
    dérivation complète. Clarke, de Silva et Thorley (2002), « Portfolio
    constraints and the fundamental law of active management », *Financial
    Analysts Journal* 58(5), 48-66, pour le coefficient de transfert. Rapporté
    par ces trois auteurs, non revérifié ici : une simple interdiction de vente à
    découvert fait tomber le coefficient de transfert nettement sous un sur un
    portefeuille d'actions long seulement.

    **Limites.** La première hypothèse est presque toujours fausse : cinq cents
    actions d'un même marché partagent un facteur commun, donc ne sont pas cinq
    cents paris. La largeur ne se compte pas, elle s'estime, et
    :func:`effective_breadth` en propose une mesure déclarée. La loi est de plus
    une approximation au premier ordre : elle ignore l'erreur d'estimation du
    coefficient d'information, ce qui la rend optimiste. L'ampleur chiffrée de
    cette surestimation n'a pas été retrouvée dans une source vérifiée, et aucun
    nombre n'est donc avancé ici.

    **Alternatives.** La version généralisée de Clarke, de Silva et Thorley
    remplace l'hypothèse d'absence de contrainte par le coefficient de
    transfert. Buckle (2004) l'écrit en temps continu. Une simulation directe du
    processus d'investissement rend le même chiffre sans hypothèse fermée, au
    prix d'un modèle complet.

    **Pourquoi ce choix.** La formule sert ici de repère et non de prévision.
    Elle dit ce qu'un ratio d'information de 2,0 exigerait de compétence, et
    montre le plus souvent que le chiffre annoncé est hors d'atteinte. C'est un
    test de vraisemblance appliqué aux résultats du laboratoire.

    **Comment vérifier.** Un coefficient de 0,05 et cent paris indépendants
    donnent :math:`0,05 \times 10 = 0,50`. Un coefficient de zéro donne zéro,
    quel que soit le nombre de paris. Doubler la largeur multiplie le résultat
    par :math:`\sqrt{2}`. Les trois contrôles sont dans les tests.

    Args:
        ic: le coefficient d'information moyen par pari, entre -1 et 1.
        breadth: le nombre de paris indépendants par an, strictement positif.
        transfer_coefficient: le coefficient de transfert, entre zéro et un.
            Un par défaut, ce qui suppose un portefeuille sans contrainte,
            hypothèse à déclarer chaque fois qu'elle est retenue.

    Returns:
        Le ratio d'information annuel implicite.

    Raises:
        ConfigError: si un argument sort de son domaine.

    Example:
        >>> round(fundamental_law(0.05, 100), 4)
        0.5
        >>> round(fundamental_law(0.05, 100, transfer_coefficient=0.5), 4)
        0.25

    Note:
        Chiffre à garder en tête, modélisé : atteindre un ratio d'information de
        1,0 sur cent paris annuels indépendants exige un coefficient de 0,10,
        puisque :math:`0{,}10 \times \sqrt{100} = 1{,}0`. La plage atteinte par
        les signaux publics n'est pas mesurée ici et aucun ordre de grandeur
        n'est avancé ; le chiffre du laboratoire se lit sur la moyenne rendue
        par :func:`ic_summary`.
    """
    if not -1.0 <= ic <= 1.0:
        raise ConfigError("ic doit se situer entre -1 et 1")
    if breadth <= 0.0:
        raise ConfigError("breadth doit être strictement positif")
    if not 0.0 <= transfer_coefficient <= 1.0:
        raise ConfigError("transfer_coefficient doit se situer entre 0 et 1")
    return float(transfer_coefficient * ic * math.sqrt(breadth))


def effective_breadth(
    correlation_matrix: pd.DataFrame | np.ndarray,
    *,
    method: BreadthMethod | str = BreadthMethod.PARTICIPATION_RATIO,
    tolerance: float = 1e-8,
) -> float:
    r"""Rend le nombre de paris effectivement indépendants d'un ensemble corrélé.

    **Le problème.** La loi fondamentale multiplie la compétence par la racine
    du nombre de paris INDÉPENDANTS. Un gérant qui suit cinq cents actions
    canadiennes n'a pas cinq cents paris : elles partagent un facteur de marché,
    et le même choc les déplace ensemble. Compter les titres au lieu des paris
    est l'erreur qui fait annoncer des ratios d'information impossibles.

    **L'intuition.** Les valeurs propres d'une matrice de corrélation mesurent
    combien de directions de risque distinctes existent réellement. Si une seule
    direction porte presque toute la variance, il n'y a qu'un pari, quel que
    soit le nombre de lignes. La méthode du taux de participation compte ces
    directions comme on compte des parts de marché avec un indice de
    concentration.

    .. math::

        p_k = \frac{\lambda_k}{\sum_{j=1}^{N} \lambda_j},
        \qquad
        \mathrm{BR}_{\mathrm{eff}} = \frac{1}{\sum_{k=1}^{N} p_k^2},
        \qquad
        \mathrm{BR}_{\mathrm{entropie}} = \exp\!\left(
        - \sum_{k=1}^{N} p_k \ln p_k \right)

    Définition de chaque variable :

    - :math:`\lambda_k` la :math:`k`-ième valeur propre de la matrice de
      corrélation, toutes positives ou nulles ;
    - :math:`p_k` la part de variance portée par la direction :math:`k`, les
      parts sommant à un ;
    - :math:`N` le nombre d'actifs.

    **Hypothèses.** La matrice est une vraie matrice de corrélation, symétrique,
    de diagonale unitaire, semi-définie positive. Les paris sont supposés portés
    par les actifs eux-mêmes, à poids comparables ; un portefeuille très
    concentré a une largeur effective plus faible que ce chiffre.

    **Provenance.** L'inverse de la somme des carrés est l'indice de
    Herfindahl-Hirschman appliqué aux valeurs propres. Meucci (2009),
    « Managing diversification », *Risk* 22(5), 74-79, l'emploie en finance sous
    le nom de nombre effectif de paris, avec la variante entropique.

    **Limites.** Le chiffre dépend de la matrice estimée, elle-même bruitée
    quand le nombre d'actifs approche le nombre d'observations. Il ignore les
    poids du portefeuille. Il ne dit rien de la stabilité de la corrélation, qui
    monte précisément quand elle nuit le plus, en marché baissier.

    **Alternatives.** La forme fermée sous corrélation uniforme, que rend
    :func:`equicorrelated_breadth`, est plus sévère et plus lisible. Le nombre
    de facteurs retenus par un critère d'information donne une autre lecture,
    entière celle-là.

    **Pourquoi ce choix.** Le taux de participation ne demande aucun réglage,
    vaut exactement :math:`N` sur des paris indépendants, et se recalcule à la
    main sur une matrice à corrélation uniforme, donc se teste.

    **Comment vérifier.** Sur la matrice identité de taille :math:`N`, toutes
    les valeurs propres valent un, chaque part vaut :math:`1/N`, la somme des
    carrés vaut :math:`1/N` et le résultat vaut exactement :math:`N`. Sur une
    matrice à corrélation uniforme :math:`\rho`, les valeurs propres sont
    :math:`1 + (N-1)\rho` une fois, puis :math:`1 - \rho` répétée :math:`N-1`
    fois. D'où la forme fermée

    .. math::

        \mathrm{BR}_{\mathrm{eff}} = \frac{N^2}
        {\big(1 + (N-1)\rho\big)^2 + (N-1)(1-\rho)^2}

    que le test compare au calcul numérique.

    Args:
        correlation_matrix: la matrice de corrélation des rendements des paris.
        method: ``"participation_ratio"`` ou ``"entropy"``.
        tolerance: l'écart admis sur la symétrie et sur la diagonale unitaire.

    Returns:
        Le nombre de paris effectivement indépendants, entre un et :math:`N`.

    Raises:
        ConfigError: si la matrice n'est pas carrée, pas symétrique, ou si sa
            diagonale n'est pas unitaire.
        DataQualityError: si la matrice n'est pas semi-définie positive au-delà
            de la tolérance, une valeur propre nettement négative signalant une
            matrice mal estimée.

    Example:
        Modélisé, sur une matrice construite et non estimée : cinq cents actifs
        corrélés à 0,3 rendent 10,89 paris effectifs au taux de participation,
        contre 500 s'ils étaient indépendants. Avec un coefficient d'information
        de 0,05, la loi fondamentale passe donc d'un ratio de 1,118 à 0,165,
        divisé par 6,8. La forme fermée sous corrélation uniforme est plus sévère
        encore, à 3,32 paris et un ratio de 0,091.
    """
    kind = BreadthMethod(method)
    matrix = np.asarray(
        correlation_matrix.to_numpy() if isinstance(correlation_matrix, pd.DataFrame) else correlation_matrix,
        dtype=float,
    )
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ConfigError("la matrice de corrélation doit être carrée")
    if matrix.shape[0] < 1:
        raise ConfigError("la matrice de corrélation doit porter au moins une ligne")
    if not np.allclose(matrix, matrix.T, atol=tolerance):
        raise ConfigError("la matrice de corrélation doit être symétrique")
    if not np.allclose(np.diag(matrix), 1.0, atol=tolerance):
        raise ConfigError("la diagonale d'une matrice de corrélation vaut 1")

    eigenvalues = np.linalg.eigvalsh(matrix)
    if eigenvalues.min() < -math.sqrt(tolerance):
        raise DataQualityError("matrice non semi-définie positive, corrélation mal estimée")
    eigenvalues = np.clip(eigenvalues, 0.0, None)
    total = float(eigenvalues.sum())
    if total <= 0.0:
        raise DataQualityError("matrice de corrélation dégénérée, trace nulle")
    shares = eigenvalues / total
    if kind is BreadthMethod.PARTICIPATION_RATIO:
        return float(1.0 / np.square(shares).sum())
    positive = shares[shares > 0.0]
    return float(math.exp(-float((positive * np.log(positive)).sum())))


def equicorrelated_breadth(n_bets: int, average_correlation: float) -> float:
    r"""Rend la largeur effective en forme fermée sous corrélation uniforme.

    **Le problème.** Le taux de participation exige une matrice estimée. Quand
    on ne dispose que d'une corrélation moyenne, cette forme fermée donne
    directement le nombre de paris équivalents, et sert de repère sévère.

    .. math::

        \mathrm{BR}_{\mathrm{eff}} = \frac{N}{1 + (N-1)\rho}

    Définition de chaque variable :

    - :math:`N` le nombre de paris nominaux ;
    - :math:`\rho` leur corrélation moyenne deux à deux.

    **Où la formule vient.** La variance de la MOYENNE de :math:`N` variables de
    variance un et de corrélation :math:`\rho` vaut
    :math:`\big(1 + (N-1)\rho\big) / N`. La moyenne de :math:`M` variables
    indépendantes de variance un a pour variance :math:`1/M`. Égaler les deux
    donne :math:`M = N / \big(1 + (N-1)\rho\big)`.

    **Hypothèses.** Corrélation identique pour toutes les paires, variances
    égales, poids égaux. Aucune des trois n'est vraie sur un marché, ce qui fait
    de ce chiffre un repère et non une mesure.

    **Provenance.** Résultat classique de la diversification, présenté sous
    cette forme dans Grinold et Kahn (1999), chapitre 6, et repris par Clarke,
    de Silva et Thorley (2002).

    **Limites.** La formule s'écroule vers :math:`1/\rho` quand :math:`N`
    devient grand. À corrélation 0,3, aucun nombre d'actions ne dépasse 3,33
    paris effectifs, ce qui est trop pessimiste dès qu'il existe des secteurs
    faiblement liés entre eux.

    **Alternative retenue ailleurs.** :func:`effective_breadth` sur la matrice
    complète, moins sévère et plus fidèle à une structure sectorielle.

    **Comment vérifier.** À :math:`\rho = 0`, la formule rend exactement
    :math:`N`. À :math:`N = 500` et :math:`\rho = 0{,}3`, elle rend
    :math:`500 / 150{,}7 = 3{,}3179`, calcul repris dans les tests.

    Args:
        n_bets: le nombre de paris nominaux, au moins un.
        average_correlation: la corrélation moyenne deux à deux, strictement
            supérieure à :math:`-1/(N-1)` et strictement inférieure à un.

    Returns:
        Le nombre de paris équivalents indépendants.

    Raises:
        ConfigError: si un argument sort de son domaine.
    """
    if n_bets < 1:
        raise ConfigError("n_bets doit valoir au moins 1")
    if n_bets == 1:
        return 1.0
    lower = -1.0 / (n_bets - 1)
    if not lower < average_correlation < 1.0:
        raise ConfigError(
            f"average_correlation doit se situer strictement entre {lower:.6f} et 1 pour {n_bets} paris"
        )
    return float(n_bets / (1.0 + (n_bets - 1) * average_correlation))

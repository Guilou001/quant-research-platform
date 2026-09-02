"""Le momentum transversal de Jegadeesh et Titman (1993), en briques réutilisables.

**Le problème.** Une réplication de « Returns to Buying Winners and Selling
Losers » demande le même tri à seize combinaisons de formation et de détention,
sur deux univers, avec et sans décalage. Écrire ce tri seize fois dans un script
d'étude garantit qu'une des seize versions finira par différer des autres.

**Ce que le module contient.** Le classement par rendement passé, la formation
des paquets et la détention à cohortes qui se chevauchent. Puis les poids longs
courts que le moteur de backtest consomme, et les résumés de série qui servent
aux tableaux. Rien d'autre.

**Ce qu'il ne contient pas.** Aucune métrique financière n'est recalculée ici.
Le ratio de Sharpe, le t de Student corrigé à la Newey-West et la rotation
viennent de ``quantlab.analytics``, conformément à la règle 12 du ``CLAUDE.md``.

**Provenance.** Narasimhan Jegadeesh et Sheridan Titman, « Returns to Buying
Winners and Selling Losers: Implications for Stock Market Efficiency »,
*The Journal of Finance*, 48(1), 1993, pages 65 à 91.

**Le piège de nommage.** Dans l'article de 1993, P1 désigne les PERDANTS et P10
les gagnants. L'article de 2001 des mêmes auteurs inverse la convention. Ce
module suit celle de 1993 : le premier paquet vend, le dernier achète.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd

from quantlab.analytics.ic import ic_summary, quantile_returns
from quantlab.core.errors import ConfigError, InsufficientDataError
from quantlab.core.logging import get_logger
from quantlab.core.types import Frequency
from quantlab.features.transforms import lag

__all__ = [
    "SPREAD_COLUMN",
    "calendar_split",
    "formation_holding_grid",
    "formation_signal",
    "long_short_weights",
    "month_end_rows",
    "overlapping_quantile_returns",
    "spread_summary",
    "truncate_before_return_breaks",
    "window_table",
    "worst_months",
]

_LOG = get_logger(__name__)

#: Le nom de la colonne d'écart rendue par :func:`quantlab.analytics.ic.quantile_returns`.
SPREAD_COLUMN = "spread"


def month_end_rows(prices: pd.DataFrame, *, offset_days: int = 0) -> pd.DataFrame:
    """Rend les prix de fin de mois, éventuellement reculés de quelques séances.

    **Le problème.** L'article classe les titres à une date de fin de mois, puis
    le panneau B attend une semaine avant de former le portefeuille. Les deux
    dates ne tombent pas sur la même ligne d'un calendrier quotidien, et la
    seconde n'est pas une fin de mois.

    **L'intuition.** On garde l'index des fins de mois comme référence de temps,
    et on y pose les prix relevés ``offset_days`` séances plus tôt. Le tableau
    rendu reste donc mensuel, ce qui laisse toute la suite du calcul alignée.

    **Les hypothèses.** L'index des prix est trié, sans doublon, et porte des
    séances de bourse. Un index qui contiendrait des jours fériés déplacerait le
    décalage de quelques jours calendaires sans le dire.

    **Les limites.** Le décalage est compté en séances, pas en jours. Cinq
    séances valent une semaine ordinaire, et davantage autour d'un jour férié.

    **Comment vérifier.** Sur un calendrier de trois mois complets, la fonction
    rend trois lignes, et leurs dates sont les dernières séances de chaque mois.
    Avec ``offset_days=1``, les valeurs sont celles de l'avant-dernière séance.

    Args:
        prices: les prix quotidiens, dates en lignes, actifs en colonnes.
        offset_days: le nombre de séances de recul, positif ou nul.

    Returns:
        Un tableau indexé par les dates de fin de mois, aux mêmes colonnes.

    Raises:
        ConfigError: si le décalage est négatif ou n'est pas un entier.
        InsufficientDataError: si l'historique est plus court que le décalage.
    """
    if isinstance(offset_days, bool) or not isinstance(offset_days, int) or offset_days < 0:
        raise ConfigError(f"offset_days doit être un entier positif ou nul, reçu {offset_days!r}")
    if prices.empty:
        raise InsufficientDataError("aucun prix fourni")
    index = pd.DatetimeIndex(prices.index)
    if index.has_duplicates:
        raise ConfigError("l'index des prix porte des dates en double")
    if not index.is_monotonic_increasing:
        raise ConfigError("l'index des prix n'est pas trié")

    positions = pd.Series(np.arange(len(index)), index=index)
    last = positions.groupby([index.year, index.month]).max().to_numpy()
    kept = last[last >= offset_days]
    if kept.size == 0:
        raise InsufficientDataError(f"aucune fin de mois ne dispose de {offset_days} séance(s) de recul")
    frame = prices.iloc[kept - offset_days].copy()
    frame.index = index[kept]
    frame.index.name = prices.index.name
    return frame


def truncate_before_return_breaks(
    prices: pd.DataFrame, *, threshold: float
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Coupe l'historique d'un titre avant une rupture de série de prix.

    **Le problème.** Une réorganisation, un regroupement d'actions ou une
    reclassification de catégorie change la base de la série de prix. Le
    fournisseur ne rétropropage pas toujours l'ajustement, et le mois de la
    rupture porte alors un rendement qu'aucun actionnaire n'a encaissé. Un tri
    transversal place ce titre au sommet du décile gagnant, pour rien.

    **L'intuition.** Le nombre aberrant n'est pas le seul dommage. Les prix
    ANTÉRIEURS à la rupture sont exprimés dans une autre base, donc tout
    rendement calculé sur eux est faux. On garde ce qui suit la rupture, et on
    jette ce qui la précède.

    **La règle.** Pour chaque titre, on cherche le dernier mois dont le
    rendement dépasse le seuil en valeur absolue. Tous les prix strictement
    antérieurs à ce mois deviennent manquants. Le rendement du mois de rupture
    devient manquant à son tour, faute de prix de départ.

    **Les hypothèses.** Un rendement mensuel au-dessus du seuil est une erreur
    et non un mouvement réel. Le seuil doit donc être choisi bien au-dessus du
    plus fort mouvement plausible de l'univers, et déclaré.

    **Les limites.** La règle ne voit pas une rupture qui laisse le rendement
    sous le seuil. Elle ne voit pas non plus une base fausse sans à-coup, cas
    d'un ajustement de dividende manquant réparti sur des années.

    **Une alternative écartée.** Remplacer la valeur aberrante par la médiane du
    titre garderait l'historique, mais fabriquerait un prix que personne n'a
    coté, et laisserait la base antérieure fausse.

    **Comment vérifier.** Prendre un titre dont le prix est multiplié par dix en
    un mois, et poser un seuil de quatre. La série ne commence alors qu'au mois
    de la rupture, et plus aucun rendement ne dépasse le seuil.

    Args:
        prices: les prix mensuels, dates en lignes, actifs en colonnes.
        threshold: le rendement mensuel absolu au-dessus duquel une observation
            est tenue pour une rupture, en fraction décimale.

    Returns:
        Le couple formé des prix coupés et du tableau des ruptures trouvées.

    Raises:
        ConfigError: si le seuil n'est pas strictement positif.
    """
    if not np.isfinite(threshold) or threshold <= 0.0:
        raise ConfigError(f"threshold doit être strictement positif, reçu {threshold!r}")
    rendements = prices.pct_change()
    coupes = prices.copy()
    lignes: list[dict[str, object]] = []
    for colonne in prices.columns:
        depassements = rendements[colonne].abs() > threshold
        if not bool(depassements.any()):
            continue
        position = int(np.flatnonzero(depassements.to_numpy())[-1])
        date = prices.index[position]
        lignes.append(
            {
                "symbol": str(colonne),
                "break_date": str(pd.Timestamp(date).date()),
                "break_return_pct": float(rendements[colonne].iloc[position]) * 100.0,
                "months_dropped": position,
            }
        )
        coupes.iloc[:position, coupes.columns.get_loc(colonne)] = np.nan
    table = pd.DataFrame(lignes, columns=["symbol", "break_date", "break_return_pct", "months_dropped"])
    _LOG.info(
        "ruptures de série de prix coupées",
        extra={"n_symbols": len(table), "threshold": float(threshold)},
    )
    return coupes, table


def formation_signal(
    ranking_prices: pd.DataFrame,
    base_prices: pd.DataFrame,
    *,
    lookback: int,
) -> pd.DataFrame:
    """Rend le rendement de formation, celui sur lequel les titres sont classés.

    **Le problème.** Le panneau A de l'article classe sur les J derniers mois et
    forme aussitôt. Le panneau B laisse passer une semaine. Les deux signaux
    partagent la même borne de gauche et diffèrent par la borne de droite.

    **La formule.**

    .. math::

        S_{i,t} = \\frac{P^{\\text{cl}}_{i,t}}{P_{i,t-J}} - 1

    où :math:`P^{\\text{cl}}_{i,t}` est le prix de classement de l'actif
    :math:`i` à la date :math:`t`, déjà reculé du décalage voulu, et
    :math:`P_{i,t-J}` son prix de fin de mois J mois plus tôt.

    **Les hypothèses.** Les prix sont ajustés des divisions et des dividendes.
    Les deux tableaux portent le même index mensuel et les mêmes colonnes.

    **Les limites.** Le signal ne dit rien de la liquidité ni du prix nominal,
    deux filtres que Jegadeesh et Titman (2001) ajoutent et que 1993 ignore.

    **Une alternative écartée.** Un rendement cumulé calculé par composition des
    rendements mensuels donne le même nombre à l'arrondi près, pour un coût de
    calcul plus élevé et un traitement des manquants moins clair.

    **Comment vérifier.** Sur des prix qui montent de 10 % par mois et sans
    décalage, ``lookback=3`` donne exactement :math:`1{,}1^3 - 1`, soit 0,331.

    Args:
        ranking_prices: les prix de classement, à la borne de droite.
        base_prices: les prix de fin de mois, qui fournissent la borne de gauche.
        lookback: la longueur de la fenêtre de formation, en mois.

    Returns:
        Le signal, dates en lignes, actifs en colonnes.

    Raises:
        ConfigError: si ``lookback`` n'est pas un entier strictement positif, ou
            si les deux tableaux ne portent pas le même index.
    """
    if isinstance(lookback, bool) or not isinstance(lookback, int) or lookback < 1:
        raise ConfigError(f"lookback doit être un entier strictement positif, reçu {lookback!r}")
    if not ranking_prices.index.equals(base_prices.index):
        raise ConfigError("les prix de classement et de base ne partagent pas leur index")
    denominator = base_prices.shift(lookback)
    return ranking_prices.divide(denominator).subtract(1.0)


def overlapping_quantile_returns(
    signal: pd.DataFrame,
    realized: pd.DataFrame,
    *,
    holding: int,
    n_quantiles: int = 10,
    weighting: str = "equal",
    min_names: int | None = None,
) -> pd.DataFrame:
    """Rend les paquets de la stratégie à cohortes qui se chevauchent.

    **Le problème.** L'article ne détient pas une seule cohorte. Au mois t, il
    détient celle ouverte au mois t moins un, celle ouverte au mois t moins
    deux, et ainsi de suite jusqu'à t moins K. Un huitième du portefeuille se
    renouvelle chaque mois quand K vaut huit.

    **L'intuition.** Le rendement du mois est la moyenne des rendements des K
    cohortes vivantes. Chaque cohorte pèse le même montant, donc 1 sur K, et le
    portefeuille reste équipondéré à l'intérieur de chaque cohorte.

    **La formule.**

    .. math::

        r^{(q)}_t = \\frac{1}{K} \\sum_{k=1}^{K} r^{(q)}_{t \\mid t-k}

    où :math:`r^{(q)}_{t \\mid t-k}` est le rendement du mois t du paquet q
    formé à la date t moins k.

    **Le décalage d'exécution.** La somme part de k égal à un, jamais de zéro.
    Le signal de la date t ne gouverne donc que des rendements postérieurs, ce
    qui ferme la porte à l'information future exigée par la règle 1.

    **Les hypothèses.** Chaque cohorte est rééquilibrée mensuellement vers
    l'équipondération, la convention publiée par l'article. Aucun coût n'est
    retiré, aucune contrainte de liquidité n'est posée.

    **Les limites.** Le rendement rendu est brut. La rotation qu'il suppose ne
    se lit pas dans ce tableau et se mesure sur les poids de
    :func:`long_short_weights`.

    **Une alternative écartée.** Détenir une seule cohorte et rééquilibrer tous
    les K mois donne une série plus bruyante, dont le résultat dépend du mois de
    départ retenu. L'article écarte ce choix pour la même raison.

    **Comment vérifier.** Avec ``holding=1``, la fonction rend exactement le
    tableau de :func:`quantlab.analytics.ic.quantile_returns` appliqué au signal
    retardé d'un mois. Le test le vérifie ligne par ligne.

    Args:
        signal: le signal de formation, dates en lignes, actifs en colonnes.
        realized: les rendements réalisés du mois, au même index.
        holding: le nombre de mois de détention, K dans l'article.
        n_quantiles: le nombre de paquets, dix dans l'article.
        weighting: ``"equal"`` ou ``"value"``.
        min_names: le plancher de noms sous lequel une date rend des manquants.

    Returns:
        Un tableau aux colonnes ``Q1`` à ``Qn`` puis ``spread``.

    Raises:
        ConfigError: si ``holding`` n'est pas un entier strictement positif.
    """
    if isinstance(holding, bool) or not isinstance(holding, int) or holding < 1:
        raise ConfigError(f"holding doit être un entier strictement positif, reçu {holding!r}")
    tables = [
        quantile_returns(
            lag(signal, k),
            realized,
            n_quantiles=n_quantiles,
            weighting=weighting,
            min_names=min_names,
        )
        for k in range(1, holding + 1)
    ]
    total = tables[0]
    for table in tables[1:]:
        total = total.add(table)
    return total.divide(float(holding))


def long_short_weights(
    signal: pd.DataFrame,
    *,
    holding: int,
    n_quantiles: int = 10,
    min_names: int | None = None,
    target_gross: float = 1.0,
) -> pd.DataFrame:
    """Rend les poids longs courts du portefeuille à coût nul, cohorte par cohorte.

    **Le problème.** Les rendements de paquets ne portent aucune information de
    rotation, donc aucun coût ne s'en déduit. Le moteur de backtest, lui, exige
    des poids par actif et par date.

    **L'intuition.** À chaque date, on achète le dernier paquet et on vend le
    premier, à parts égales à l'intérieur de chacun. Le portefeuille du mois est
    la moyenne des K cohortes vivantes, exactement comme les rendements.

    **La formule.** Pour la cohorte formée à la date :math:`t-k`,

    .. math::

        w_{i,t \\mid t-k} = \\frac{G}{2}
        \\left( \\frac{\\mathbb{1}[i \\in Q_n]}{|Q_n|}
              - \\frac{\\mathbb{1}[i \\in Q_1]}{|Q_1|} \\right)

    où :math:`G` est l'exposition brute visée et :math:`Q_1`, :math:`Q_n` les
    paquets perdant et gagnant de cette cohorte. Le poids publié est la moyenne
    sur les K cohortes.

    **Où vit le décalage d'exécution.** Nulle part ici. Les poids de la date t
    sont construits sur les signaux des dates t à t moins K plus un, donc sur de
    l'information disponible à t. C'est le moteur de backtest qui applique le
    décalage d'une période, et l'appeler avec ``execution_lag=1`` redonne
    exactement les cohortes de :func:`overlapping_quantile_returns`. Poser le
    décalage aux deux endroits le compterait deux fois.

    **Les hypothèses.** L'exposition brute vaut G à chaque date où le tri
    existe, et l'exposition nette vaut zéro. Les poids ne dérivent pas entre
    deux dates, le moteur de backtest s'en chargeant.

    **Le choix de l'exposition brute.** L'écart publié par l'article achète un
    dollar de gagnants et vend un dollar de perdants, donc son exposition brute
    vaut DEUX. La valeur par défaut vaut un, celle d'un portefeuille déployable
    dont la moitié est achetée et l'autre vendue, et qui rapporte donc la moitié
    de l'écart publié. Reproduire une table de l'article demande
    ``target_gross=2.0``.

    **Les limites.** Les cohortes sont figées à leur poids de formation, sans
    tenir compte de leur dérive. La rotation mesurée est donc celle d'un
    portefeuille rééquilibré chaque mois, la convention de l'article.

    **Une alternative écartée.** Pondérer chaque titre par son rendement passé
    diminué de la moyenne donne la stratégie de force relative pondérée que
    l'article analyse. Sa corrélation avec le tri par déciles vaut 0,95 selon
    l'article, et elle ne se compare à aucune table publiée.

    **Comment vérifier.** Sur dix actifs et dix paquets, chaque paquet ne
    contient qu'un actif. Le poids du meilleur vaut alors G sur deux, celui du
    pire moins G sur deux, et les huit autres sont nuls. Le test
    ``test_poids_et_rendements_concordent`` va plus loin, en retrouvant l'écart
    publié à partir des seuls poids retardés d'une période.

    Args:
        signal: le signal de formation, dates en lignes, actifs en colonnes.
        holding: le nombre de mois de détention.
        n_quantiles: le nombre de paquets.
        min_names: le plancher de noms sous lequel la date ne porte aucun poids.
        target_gross: l'exposition brute visée, un par défaut.

    Returns:
        Les poids, dates en lignes, actifs en colonnes, valeurs manquantes
        remplacées par zéro.

    Raises:
        ConfigError: si ``holding``, ``n_quantiles`` ou ``target_gross`` sortent
            de leur domaine.
    """
    if isinstance(holding, bool) or not isinstance(holding, int) or holding < 1:
        raise ConfigError(f"holding doit être un entier strictement positif, reçu {holding!r}")
    if n_quantiles < 2:
        raise ConfigError("n_quantiles doit valoir au moins 2")
    if target_gross <= 0.0:
        raise ConfigError("target_gross doit être strictement positif")
    plancher = n_quantiles if min_names is None else int(min_names)
    if plancher < n_quantiles:
        raise ConfigError(f"min_names vaut {plancher} pour {n_quantiles} paquets")

    cohortes = [
        _cohort_weights(lag(signal, k), n_quantiles=n_quantiles, min_names=plancher, gross=target_gross)
        for k in range(holding)
    ]
    total = cohortes[0]
    for cohorte in cohortes[1:]:
        total = total.add(cohorte)
    return total.divide(float(holding))


def _cohort_weights(signal: pd.DataFrame, *, n_quantiles: int, min_names: int, gross: float) -> pd.DataFrame:
    """Rend les poids d'une seule cohorte, achat du dernier paquet, vente du premier.

    Le découpage en paquets recopie la formule de
    :func:`quantlab.analytics.ic.quantile_returns`, soit le paquet
    ``min(floor(Q (rang - 1) / n), Q - 1)`` à partir de zéro. Deux découpages
    différents feraient diverger les poids des rendements publiés, et le test
    ``test_poids_et_rendements_concordent`` le vérifie sur un effectif que le
    nombre de paquets ne divise pas.
    """
    valides = signal.notna().sum(axis="columns")
    rangs = signal.rank(axis="columns", method="first", ascending=True)
    denominateur = valides.to_numpy(dtype=float).reshape(-1, 1)
    with np.errstate(invalid="ignore", divide="ignore"):
        brut = np.floor(n_quantiles * (rangs.to_numpy(dtype=float) - 1.0) / denominateur)
    paquet = pd.DataFrame(
        np.minimum(brut, float(n_quantiles - 1)), index=signal.index, columns=signal.columns
    )

    gagnants = (paquet == float(n_quantiles - 1)).astype(float)
    perdants = (paquet == 0.0).astype(float)
    n_gagnants = gagnants.sum(axis="columns").replace(0.0, np.nan)
    n_perdants = perdants.sum(axis="columns").replace(0.0, np.nan)
    poids = gagnants.divide(n_gagnants, axis="index").subtract(perdants.divide(n_perdants, axis="index"))
    poids = poids.multiply(gross / 2.0)
    poids.loc[(valides < min_names).to_numpy(), :] = 0.0
    return poids.fillna(0.0)


def spread_summary(
    series: pd.Series,
    *,
    frequency: Frequency = Frequency.MONTHLY,
    hac_lags: int | None = None,
) -> dict[str, float]:
    """Résume une série de rendements d'écart, avec ses deux t de Student.

    **Le problème.** L'article publie un t de Student ordinaire, calculé sans
    correction d'autocorrélation. La littérature moderne publie un t corrigé à
    la Newey-West. Comparer nos chiffres aux siens exige les deux.

    **La formule des deux t.** Le t ordinaire vaut

    .. math::

        t_{\\text{iid}} = \\frac{\\bar{r}}{s} \\sqrt{n}

    où :math:`s` est l'écart type d'échantillon. Le t corrigé remplace
    :math:`s^2/n` par la variance de long terme de la moyenne, estimée avec la
    fenêtre de Bartlett.

    **Pourquoi la correction compte ici.** Les cohortes se chevauchent quand K
    dépasse un mois, ce qui autocorrèle mécaniquement la série. Le t ordinaire
    surestime alors la précision, et l'article ne le corrige pas.

    **Les hypothèses.** La série est stationnaire sur la fenêtre retenue. Les
    dates manquantes sont retirées avant le calcul, et non comblées.

    **Les limites.** Le t corrigé dépend du nombre de retards, choisi par une
    règle automatique quand l'appelant n'en impose aucun. Deux règles usuelles
    donnent des nombres de retards différents sur le même échantillon.

    **Comment vérifier.** Sur trois valeurs 8 %, moins 8 % et 1 %, la moyenne
    vaut 0,3333 %, et le t ordinaire se recalcule à la main.

    Args:
        series: la série de rendements, indexée par date.
        frequency: la fréquence, qui fixe l'annualisation arithmétique.
        hac_lags: le nombre de retards de la correction, automatique si absent.

    Returns:
        Un dictionnaire à dix clés, prêt pour une ligne de tableau.

    Raises:
        InsufficientDataError: si moins de deux dates portent une valeur.
    """
    valeurs = series.dropna()
    if valeurs.size < 2:
        raise InsufficientDataError(f"{valeurs.size} observation(s), deux exigées")
    resume = ic_summary(valeurs, frequency=frequency, hac_lags=hac_lags)
    n = int(resume.n_periods)
    t_iid = float(resume.ir_per_period * math.sqrt(n)) if n > 0 else float("nan")
    return {
        "n_periods": n,
        "start": str(valeurs.index.min().date()),
        "end": str(valeurs.index.max().date()),
        "mean_pct_per_month": float(resume.mean) * 100.0,
        "mean_annualized_pct": float(resume.mean) * Frequency(frequency).periods_per_year * 100.0,
        "std_pct_per_month": float(resume.std) * 100.0,
        "t_iid": t_iid,
        "t_hac": float(resume.t_stat_hac),
        "hac_lags": int(resume.hac_lags),
        "sharpe_annualized": float(resume.ir_annualized),
        "hit_rate": float(resume.hit_rate),
        "worst_month_pct": float(valeurs.min()) * 100.0,
    }


def window_table(
    series: pd.Series,
    windows: Mapping[str, tuple[str, str]],
    *,
    frequency: Frequency = Frequency.MONTHLY,
    hac_lags: int | None = None,
) -> pd.DataFrame:
    """Rend le résumé d'une série sur plusieurs fenêtres nommées.

    **Le problème.** L'étude compare la même stratégie sur la fenêtre de
    l'article, sur celle qui la précède et sur celle qui la suit. Recopier
    l'appel de résumé pour chaque fenêtre invite l'erreur de bornes.

    **Les hypothèses.** Les bornes sont inclusives et données en texte, au
    format que pandas comprend sur un index de dates.

    **Les limites.** Une fenêtre vide ou trop courte lève plutôt que de rendre
    une ligne de manquants. Un résultat absent est un résultat, et il doit se
    voir.

    **Comment vérifier.** Deux fenêtres qui couvrent ensemble tout l'échantillon
    rendent deux lignes dont les effectifs se somment à celui de la série.

    Args:
        series: la série de rendements.
        windows: les fenêtres, nom vers couple de bornes inclusives.
        frequency: la fréquence de la série.
        hac_lags: le nombre de retards de la correction, automatique si absent.

    Returns:
        Un tableau à une ligne par fenêtre, la colonne ``window`` en tête.
    """
    lignes = []
    for nom, (debut, fin) in windows.items():
        resume = spread_summary(series.loc[debut:fin], frequency=frequency, hac_lags=hac_lags)
        lignes.append({"window": nom, "bounds": f"{debut} à {fin}", **resume})
    return pd.DataFrame(lignes)


def calendar_split(
    series: pd.Series,
    *,
    month: int = 1,
    frequency: Frequency = Frequency.MONTHLY,
) -> pd.DataFrame:
    """Sépare un mois de calendrier du reste de l'année, et résume les deux.

    **Le problème.** L'article mesure que sa stratégie perd 6,86 % en janvier et
    gagne 1,66 % les onze autres mois. Le chiffre d'ensemble mélange donc deux
    régimes de signe opposé.

    **L'intuition.** Les perdants de l'année écoulée sont vendus en décembre
    pour matérialiser une moins-value fiscale, puis rachetés en janvier. Le
    paquet vendu par la stratégie monte alors, et la stratégie perd.

    **Les hypothèses.** L'index porte une date par mois. Un index quotidien
    donnerait des effectifs par mois de calendrier sans rapport avec l'article.

    **Les limites.** La séparation ne prouve pas le mécanisme fiscal, elle
    mesure une saisonnalité. Les deux sous-séries comptent onze fois moins et
    onze fois plus d'observations, donc leurs t ne sont pas comparables entre
    eux.

    **Comment vérifier.** Les effectifs des deux lignes se somment à celui de la
    série entière.

    Args:
        series: la série de rendements mensuels.
        month: le mois isolé, janvier par défaut.
        frequency: la fréquence de la série.

    Returns:
        Un tableau à deux lignes, le mois isolé puis le reste.

    Raises:
        ConfigError: si ``month`` sort de l'intervalle un à douze.
    """
    if isinstance(month, bool) or not isinstance(month, int) or not 1 <= month <= 12:
        raise ConfigError(f"month doit être un entier de 1 à 12, reçu {month!r}")
    mois = pd.DatetimeIndex(series.index).month
    lignes = [
        {"segment": f"mois {month}", **spread_summary(series[mois == month], frequency=frequency)},
        {"segment": f"hors mois {month}", **spread_summary(series[mois != month], frequency=frequency)},
    ]
    return pd.DataFrame(lignes)


def worst_months(series: pd.Series, *, count: int = 10) -> pd.DataFrame:
    """Rend les pires mois d'une série, du plus mauvais au moins mauvais.

    **Le problème.** Daniel et Moskowitz (2016) montrent que le momentum ne se
    juge pas sur sa moyenne. Il s'effondre par épisodes, et deux mois de 1932
    portent l'essentiel de la perte historique.

    **Les hypothèses.** Les valeurs manquantes sont retirées avant le tri.

    **Les limites.** Une liste de pires mois ne dit rien de leur prévisibilité.
    Daniel et Moskowitz montrent qu'ils suivent des baisses de marché, ce que ce
    tableau ne teste pas.

    **Comment vérifier.** Sur une série strictement croissante, la fonction rend
    ses ``count`` premières dates.

    Args:
        series: la série de rendements.
        count: le nombre de mois rendus.

    Returns:
        Un tableau à trois colonnes, la date, le rendement et son rang.

    Raises:
        ConfigError: si ``count`` n'est pas un entier strictement positif.
    """
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ConfigError(f"count doit être un entier strictement positif, reçu {count!r}")
    pires = series.dropna().nsmallest(count)
    return pd.DataFrame(
        {
            "date": [str(pd.Timestamp(d).date()) for d in pires.index],
            "return_pct": pires.to_numpy(dtype=float) * 100.0,
            "rank": np.arange(1, pires.size + 1),
        }
    )


def formation_holding_grid(
    ranking_prices: Mapping[str, pd.DataFrame],
    base_prices: pd.DataFrame,
    realized: pd.DataFrame,
    *,
    formations: Sequence[int],
    holdings: Sequence[int],
    n_quantiles: int = 10,
    weighting: str = "equal",
    min_names: int | None = None,
    frequency: Frequency = Frequency.MONTHLY,
    start: str | None = None,
    end: str | None = None,
) -> tuple[pd.DataFrame, dict[str, pd.Series]]:
    """Rend la grille J sur K de l'article, un résumé par cellule.

    **Le problème.** L'article publie trente-deux cellules, seize par panneau.
    Les recalculer une à une multiplie les occasions de décaler un signal d'un
    mois sans que rien ne le signale.

    **L'économie de calcul.** Pour une formation J donnée, les cohortes de
    toutes les détentions K sont les mêmes objets, retardés de un à K mois. Le
    tri n'est donc fait qu'une fois par retard, et non une fois par cellule.

    **Les hypothèses.** Les panneaux diffèrent seulement par le prix de
    classement. Chaque panneau porte le même index mensuel que les rendements.

    **Les limites.** Chaque cellule est un essai, et la grille en compte autant
    qu'elle a de cases. Le compte revient à l'appelant, qui le passe au ratio de
    Sharpe dégonflé, comme l'exige la règle 8.

    **Comment vérifier.** La cellule de détention un d'un panneau reproduit
    exactement l'appel direct à :func:`overlapping_quantile_returns` avec
    ``holding=1``.

    Args:
        ranking_prices: les prix de classement, un tableau par panneau.
        base_prices: les prix de fin de mois, communs aux panneaux.
        realized: les rendements mensuels réalisés.
        formations: les longueurs de formation J, en mois.
        holdings: les longueurs de détention K, en mois.
        n_quantiles: le nombre de paquets.
        weighting: la pondération à l'intérieur d'un paquet.
        min_names: le plancher de noms.
        frequency: la fréquence des séries.
        start: la première date retenue, incluse.
        end: la dernière date retenue, incluse.

    Returns:
        Le couple formé du tableau des cellules et du dictionnaire des séries
        d'écart, une par cellule, dont les clés nomment panneau, J et K.
    """
    lignes: list[dict[str, object]] = []
    series: dict[str, pd.Series] = {}
    k_max = int(max(holdings))
    for panneau, prix in ranking_prices.items():
        for j in formations:
            signal = formation_signal(prix, base_prices, lookback=int(j))
            tables = [
                quantile_returns(
                    lag(signal, k),
                    realized,
                    n_quantiles=n_quantiles,
                    weighting=weighting,
                    min_names=min_names,
                )
                for k in range(1, k_max + 1)
            ]
            cumul = tables[0]
            for k in range(1, k_max + 1):
                if k > 1:
                    cumul = cumul.add(tables[k - 1])
                if k not in holdings:
                    continue
                moyenne = cumul.divide(float(k))
                ecart = moyenne[SPREAD_COLUMN].loc[start:end]
                cle = f"{panneau}_J{j}_K{k}"
                series[cle] = ecart
                colonnes = [c for c in moyenne.columns if c != SPREAD_COLUMN]
                lignes.append(
                    {
                        "panel": panneau,
                        "formation_months": int(j),
                        "holding_months": int(k),
                        "loser_pct_per_month": float(moyenne[colonnes[0]].loc[start:end].mean()) * 100.0,
                        "winner_pct_per_month": float(moyenne[colonnes[-1]].loc[start:end].mean()) * 100.0,
                        **spread_summary(ecart, frequency=frequency),
                    }
                )
    _LOG.info(
        "grille de formation et de détention calculée",
        extra={"n_cells": len(lignes), "panels": list(ranking_prices)},
    )
    return pd.DataFrame(lignes), series

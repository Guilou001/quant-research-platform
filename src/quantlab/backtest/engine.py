r"""Le moteur de backtest, et le jour de décalage qui décide de tout.

**Le problème.** Un backtest transforme une suite de poids en une suite de
rendements. L'opération paraît mécanique, et elle porte pourtant la faute la
plus coûteuse de la recherche quantitative : négocier au prix qui a servi à
décider. Un signal calculé sur la clôture du jour *t* ne s'exécute pas à cette
clôture, parce qu'au moment où le prix est connu, la séance est finie.

**L'ampleur, chiffrée.** Prenons un signal sans aucune information, le signe du
rendement du jour même. Exécuté sur la barre du signal, il rend
:math:`|r_t|` chaque jour, donc un rendement positif tous les jours sans
exception. Avec un rendement quotidien d'écart type 1 %, la moyenne de
:math:`|r_t|` vaut :math:`\sigma \sqrt{2/\pi} = 0{,}798\ \%`, et 252 séances
composées à ce rythme multiplient la mise par
:math:`1{,}00798^{252} = 7{,}41`. Le signal le plus vide qui soit affiche alors
641 % par an. Statut de ce chiffre : modélisé, sous deux
hypothèses déclarées, 252 séances et des rendements normaux centrés. Décalé
d'une seule séance, le même signal rend une espérance nulle.

**La décision du laboratoire.** ``execution_lag`` vaut 1 par défaut. Passer
zéro reste possible, pour mesurer précisément l'ampleur de la fuite, et exige
l'argument ``allow_same_bar_execution=True``, dont le nom dit ce qu'on fait.
Sans lui, le moteur lève :class:`~quantlab.core.errors.LookAheadError`.

**La convention de datation, écrite une fois pour toutes.** La ligne datée *t*
de ``returns`` porte le rendement réalisé entre *t-1* et *t*. La ligne datée *t*
de ``weights`` porte la cible décidée avec l'information disponible à *t*. Le
moteur applique donc ``weights`` décalé de ``execution_lag`` lignes : avec un
décalage de un, la cible décidée à *t* gagne le rendement de *t+1*, jamais celui
de *t*.

**Ce que ce module ne fait pas.** Il ne calcule aucune métrique. Le ratio de
Sharpe vit dans :mod:`quantlab.analytics.ratios`, le repli dans
:mod:`quantlab.analytics.drawdown`, la rotation dans
:mod:`quantlab.analytics.turnover`. Un moteur qui recalculerait une volatilité
créerait une seconde définition, et deux définitions finissent toujours par
diverger.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from quantlab.analytics.drawdown import max_drawdown
from quantlab.analytics.ratios import calmar_ratio, sharpe_ratio, sortino_ratio
from quantlab.analytics.returns import cagr, compound, cumulative_wealth
from quantlab.analytics.risk import hit_rate, volatility
from quantlab.analytics.turnover import annualized_turnover, drifted_weights, turnover
from quantlab.core.calendars import annualization_factor
from quantlab.core.errors import (
    ConfigError,
    DataQualityError,
    InsufficientDataError,
    LookAheadError,
)
from quantlab.core.logging import get_logger
from quantlab.core.types import CostBasis, Frequency, ReturnFrame, SampleTag, WeightFrame

__all__ = [
    "DEFAULT_EXECUTION_LAG",
    "FORECAST_FLOOR",
    "MIN_SUMMARY_OBSERVATIONS",
    "TOTAL_COST_COLUMN",
    "BacktestResult",
    "CostCallable",
    "apply_execution_lag",
    "equity_curve",
    "rebalance_dates",
    "run_backtest",
    "volatility_target",
]

_LOG = get_logger(__name__)

#: Le décalage d'exécution par défaut, en périodes. Un, jamais zéro : voir la
#: docstring du module pour l'ampleur mesurée de ce que zéro invente.
DEFAULT_EXECUTION_LAG: int = 1

#: Le nom de la colonne de coût quand le modèle rend un seul nombre plutôt
#: qu'une ventilation par composante.
TOTAL_COST_COLUMN: str = "total"

#: Le nombre minimal de périodes sous lequel :meth:`BacktestResult.summary`
#: refuse de rendre des métriques. Deux points ne font pas une volatilité.
MIN_SUMMARY_OBSERVATIONS: int = 2

#: Le plancher de volatilité ANNUALISÉE sous lequel le levier est jugé infini
#: et rabattu sur son plafond. Un point de pourcentage vaut 0,01 en fraction,
#: donc ce seuil vaut un dix-milliardième de point : il n'écarte que le zéro
#: numérique, jamais une volatilité que le marché produirait. Statut : précepte.
FORECAST_FLOOR: float = 1e-12

#: Le type d'un modèle de coût accepté par :func:`run_backtest`. Soit un objet
#: portant une méthode ``cost``, celle du protocole
#: :class:`quantlab.core.protocols.CostModel`, soit une fonction de même
#: signature. Le retour est un nombre, ou une ventilation par composante.
CostCallable = Callable[..., float | Mapping[str, float]]


def _as_frame(data: object, *, label: str) -> pd.DataFrame:
    """Vérifie que l'objet est un tableau pandas non vide et bien indexé."""
    if not isinstance(data, pd.DataFrame):
        raise TypeError(f"{label} doit être un pandas.DataFrame, reçu {type(data).__name__}")
    if data.empty:
        raise InsufficientDataError(f"{label} est vide : rien à rejouer.")
    if data.index.has_duplicates:
        raise DataQualityError(f"{label} porte des dates en double.")
    if not data.index.is_monotonic_increasing:
        raise DataQualityError(f"{label} n'est pas trié par date croissante.")
    return data


def rebalance_dates(index: pd.Index, frequency: Frequency) -> pd.Index:
    """Rend les dates auxquelles le portefeuille a le droit de négocier.

    **Le problème.** Une politique mensuelle rejouée sur des données
    quotidiennes ne négocie pas tous les jours. Choisir les dates de
    rééquilibrage revient à choisir la rotation, donc les coûts, donc la
    performance nette.

    **La règle retenue.** La dernière date observée de chaque période
    calendaire. Elle a deux mérites sur le premier jour du mois suivant : elle
    existe toujours, puisqu'elle est prise dans l'index, et elle ne suppose
    aucun calendrier de bourse.

    Args:
        index: l'index des dates observées, trié et sans doublon.
        frequency: le rythme voulu. ``DAILY`` veut dire « à chaque période
            observée », et rend l'index entier.

    Returns:
        Le sous-index des dates de rééquilibrage, dans l'ordre.

    Raises:
        InsufficientDataError: l'index est vide.
        DataQualityError: l'index porte des doublons ou n'est pas trié.
        ConfigError: la fréquence demandée exige un index de dates, et l'index
            n'en est pas un.

    Example:
        Sur les séances de janvier et février 2020 et une fréquence mensuelle,
        la fonction rend le 31 janvier et le 28 février, les deux dernières
        séances observées de chaque mois.

    Note:
        **Alternatives.** Rééquilibrer à date fixe, le troisième vendredi par
        exemple, se fait en passant directement l'index voulu à
        :func:`run_backtest`. Une politique à bandes, déclenchée par un écart
        plutôt que par le calendrier, ne se décrit pas par cette fonction : ses
        dates dépendent des prix, donc du déroulé du backtest.

        **Comment vérifier.** La sortie est incluse dans l'entrée, elle est
        triée, et sa longueur vaut le nombre de périodes calendaires couvertes.
        Un index quotidien couvrant trois mois rend trois dates en mensuel.
    """
    if len(index) == 0:
        raise InsufficientDataError("index vide : aucune date de rééquilibrage.")
    if index.has_duplicates:
        raise DataQualityError("l'index porte des dates en double.")
    if not index.is_monotonic_increasing:
        raise DataQualityError("l'index n'est pas trié par date croissante.")
    if frequency is Frequency.DAILY:
        return index

    code = {
        Frequency.WEEKLY: "W",
        Frequency.MONTHLY: "M",
        Frequency.QUARTERLY: "Q",
        Frequency.ANNUAL: "Y",
    }[frequency]
    if not isinstance(index, pd.DatetimeIndex):
        raise ConfigError(
            f"la fréquence {frequency.value} exige un pandas.DatetimeIndex, "
            f"reçu {type(index).__name__}. En DAILY, tout index convient."
        )
    periods = index.to_period(code)
    is_last = np.empty(len(index), dtype=bool)
    is_last[-1] = True
    if len(index) > 1:
        is_last[:-1] = periods[1:] != periods[:-1]
    return index[is_last]


def apply_execution_lag(weights: WeightFrame, lag: int) -> WeightFrame:
    r"""Décale les poids cibles du nombre de périodes séparant la décision de l'exécution.

    **Le problème.** La cible décidée à la clôture de *t* ne peut pas être
    détenue pendant la séance *t*, qui est terminée. Sans ce décalage, le
    backtest négocie au prix qui a servi à décider.

    **La formule.**

    .. math::  \tilde{w}_t = w_{t - \ell}

    Args:
        weights: les poids cibles, une ligne par date de décision.
        lag: le nombre de périodes entre la décision et la détention. Zéro veut
            dire « détenu pendant la période même du signal », ce qui est la
            fuite.

    Returns:
        Les poids décalés, indexés comme l'entrée. Les ``lag`` premières lignes
        sont manquantes, puisque aucune décision ne les précède.

    Raises:
        TypeError: l'entrée n'est pas un tableau pandas.
        LookAheadError: le décalage est négatif, ce qui ferait détenir
            aujourd'hui une cible décidée demain.

    Example:
        Trois dates et un décalage de un. La cible du 2 janvier est détenue le
        3 janvier, celle du 3 janvier le 4, et la ligne du 2 janvier reste
        manquante.

    Note:
        **Variables.** :math:`w_t` est la cible décidée à la date *t*,
        :math:`\ell` le décalage, :math:`\tilde{w}_t` la cible détenue pendant
        la période *t*.

        **Hypothèses.** L'index est trié, et deux lignes consécutives sont
        séparées d'une période. Un index quotidien avec des trous décale d'une
        ligne, pas d'un jour de calendrier, ce qui est le comportement voulu
        pour des séances de bourse.

        **Limites.** Le décalage est uniforme. Il ne modélise ni l'exécution
        partielle, ni le refus d'un ordre sur un titre suspendu, qui
        appartiennent au modèle d'exécution.

        **Comment vérifier.** Un décalage de zéro rend l'entrée inchangée. Un
        décalage de :math:`\ell` rend un tableau dont les :math:`\ell` premières
        lignes sont manquantes et dont la ligne *k* vaut la ligne
        :math:`k - \ell` de l'entrée, ce qu'une comparaison directe des tableaux
        vérifie sans passer par ce code.
    """
    if not isinstance(weights, pd.DataFrame):
        raise TypeError(f"weights doit être un pandas.DataFrame, reçu {type(weights).__name__}")
    if lag < 0:
        raise LookAheadError(
            f"décalage d'exécution négatif ({lag}). Il ferait détenir aujourd'hui une cible "
            "décidée plus tard, ce qui est la définition de la fuite d'information."
        )
    if lag == 0:
        return weights.copy()
    return weights.shift(lag)


@dataclass(frozen=True, slots=True, eq=False)
class BacktestResult:
    """Le produit d'un backtest, ses séries et ses hypothèses réunies.

    L'objet est gelé parce qu'un résultat de backtest se lit et ne se corrige
    pas. Une correction se fait en relançant le moteur avec d'autres arguments,
    ce qui laisse une trace, alors qu'une écriture sur place n'en laisse aucune.

    L'égalité automatique est retirée, un tableau pandas n'ayant pas de valeur
    de vérité unique.

    Attributes:
        gross_returns: le rendement de chaque période avant frais.
        net_returns: le même, frais retirés. L'identité
            ``net = gross - costs`` tient à la précision machine.
        costs: le coût de chaque période, en fraction de la valeur liquidative,
            compté positivement.
        cost_breakdown: le même coût ventilé par composante, une colonne par
            poste. La somme des colonnes redonne ``costs``.
        turnover: la rotation de chaque période, mesurée contre les poids
            dérivés, dans la convention en demi-somme.
        target_weights: les cibles telles que fournies, avant décalage.
        executed_weights: les poids réellement détenus pendant chaque période,
            après décalage et après filtrage par les dates de rééquilibrage.
        drifted_weights: les poids atteints par la seule dérive du marché à
            l'entrée de chaque période, avant toute transaction.
        gross_exposure: la somme des valeurs absolues des poids détenus.
        net_exposure: la somme signée des poids détenus.
        leverage: le levier porté pendant la période, moyenne de l'exposition
            brute au début et à la fin. Il diffère de ``gross_exposure``, qui ne
            regarde que le début.
        frequency: la fréquence des périodes.
        metadata: l'échantillon, les hypothèses de coût, le décalage et la
            période couverte.
    """

    gross_returns: pd.Series
    net_returns: pd.Series
    costs: pd.Series
    cost_breakdown: pd.DataFrame
    turnover: pd.Series
    target_weights: pd.DataFrame
    executed_weights: pd.DataFrame
    drifted_weights: pd.DataFrame
    gross_exposure: pd.Series
    net_exposure: pd.Series
    leverage: pd.Series
    frequency: Frequency
    metadata: dict[str, Any]

    def to_frame(self) -> pd.DataFrame:
        """Rend les séries scalaires du résultat dans un seul tableau daté.

        Returns:
            Un tableau indexé par date, colonnes ``gross_return``,
            ``net_return``, ``cost``, ``turnover``, ``gross_exposure``,
            ``net_exposure`` et ``leverage``.

        Note:
            Les poids restent hors de ce tableau : ils portent une seconde
            dimension, l'actif, qu'une table à une ligne par date ne peut pas
            recevoir sans se replier.
        """
        return pd.DataFrame(
            {
                "gross_return": self.gross_returns,
                "net_return": self.net_returns,
                "cost": self.costs,
                "turnover": self.turnover,
                "gross_exposure": self.gross_exposure,
                "net_exposure": self.net_exposure,
                "leverage": self.leverage,
            }
        )

    def summary(self) -> dict[str, float | int | str]:
        """Rend le tableau de bord chiffré du backtest, calculé par ``analytics``.

        Aucune métrique n'est calculée ici. Chaque ligne appelle la fonction du
        paquet d'analytique qui la définit, si bien qu'une correction apportée
        là se propage sans recopie.

        Returns:
            Un dictionnaire. Les rendements et le repli sont en fraction, la
            rotation en fraction de la valeur du portefeuille par an, les ratios
            sans unité.

        Raises:
            InsufficientDataError: la série compte moins de
                ``MIN_SUMMARY_OBSERVATIONS`` périodes.

        Note:
            **Le coût annualisé.** La ligne ``cost_drag_annual`` est l'écart des
            deux taux de croissance annuels composés, brut et net. Elle n'est
            pas la moyenne annualisée des coûts : composer avant de soustraire
            n'est pas soustraire avant de composer, et l'écart croît avec la
            durée.

            **Comment vérifier.** Un backtest sans coût rend un
            ``cost_drag_annual`` nul et deux totaux identiques. Une stratégie
            dont le rendement est constant rend un ratio de Sharpe infini, que
            le plancher de volatilité de ``analytics.ratios`` intercepte.
        """
        net = self.net_returns
        if len(net) < MIN_SUMMARY_OBSERVATIONS:
            raise InsufficientDataError(
                f"{len(net)} période(s) : moins de {MIN_SUMMARY_OBSERVATIONS}, aucune métrique n'a de sens."
            )
        gross = self.gross_returns
        freq = self.frequency
        return {
            "n_periods": len(net),
            "sample": str(self.metadata["sample"]),
            "cost_basis": str(CostBasis.NET),
            "total_return_gross": float(compound(gross)),
            "total_return_net": float(compound(net)),
            "cagr_gross": float(cagr(gross, freq)),
            "cagr_net": float(cagr(net, freq)),
            "cost_drag_annual": float(cagr(gross, freq)) - float(cagr(net, freq)),
            "volatility_annual": volatility(net, freq),
            "sharpe_ratio": sharpe_ratio(net, frequency=freq),
            "sortino_ratio": sortino_ratio(net, frequency=freq),
            "calmar_ratio": calmar_ratio(net, frequency=freq),
            "max_drawdown": max_drawdown(net),
            "hit_rate": hit_rate(net),
            "turnover_annual": annualized_turnover(self.turnover, freq),
            "cost_total": float(self.costs.sum()),
            "gross_exposure_mean": float(self.gross_exposure.mean()),
            "leverage_mean": float(self.leverage.mean()),
        }


def _resolve_cost_model(cost_model: object) -> CostCallable | None:
    """Rend la fonction de coût à appeler, ou ``None`` si aucun modèle n'est fourni."""
    if cost_model is None:
        return None
    if hasattr(cost_model, "cost"):
        return cost_model.cost  # type: ignore[attr-defined,no-any-return]
    if callable(cost_model):
        return cost_model
    raise ConfigError(
        f"cost_model doit porter une méthode « cost » ou être appelable. Reçu {type(cost_model).__name__}."
    )


def _cost_components(raw: float | Mapping[str, float], *, date: object) -> dict[str, float]:
    """Normalise le retour d'un modèle de coût en ventilation par composante."""
    if isinstance(raw, Mapping):
        components = {str(k): float(v) for k, v in raw.items()}
    else:
        components = {TOTAL_COST_COLUMN: float(raw)}
    for name, value in components.items():
        if not np.isfinite(value):
            raise DataQualityError(f"coût non fini ({value}) pour la composante {name!r} à la date {date}.")
    return components


def _check_returns_complete(returns: ReturnFrame, columns: pd.Index) -> None:
    """Refuse un tableau de rendements troué sur les actifs détenus."""
    used = returns.loc[:, columns]
    missing = used.isna().to_numpy().sum()
    if missing > 0:
        raise DataQualityError(
            f"{int(missing)} rendement(s) manquant(s) sur les actifs détenus. Un trou ne se "
            "remplace pas par zéro en silence : traiter l'entrée et la sortie d'univers en "
            "amont, en portant un poids nul et un rendement nul."
        )


def _rebalance_mask(index: pd.Index, rebalance: Frequency | pd.Index | None) -> pd.Series:
    """Rend, pour chaque date de l'index, le droit de négocier ce jour-là."""
    if rebalance is None:
        return pd.Series(True, index=index)
    dates = rebalance_dates(index, rebalance) if isinstance(rebalance, Frequency) else pd.Index(rebalance)
    inconnues = dates.difference(index)
    if len(inconnues) > 0:
        raise ConfigError(
            f"{len(inconnues)} date(s) de rééquilibrage absentes de l'index des rendements, "
            f"dont {inconnues[0]}. Une date à laquelle aucun rendement n'existe ne se négocie pas."
        )
    return pd.Series(index.isin(dates), index=index)


def run_backtest(
    *,
    weights: WeightFrame,
    returns: ReturnFrame,
    cost_model: object | None = None,
    execution_lag: int = DEFAULT_EXECUTION_LAG,
    frequency: Frequency,
    rebalance: Frequency | pd.Index | None = None,
    initial_capital: float = 1.0,
    allow_same_bar_execution: bool = False,
) -> BacktestResult:
    r"""Rejoue une suite de poids sur l'histoire et rend ses rendements bruts et nets.

    **Le problème.** Passer de poids à performance suppose de trancher quatre
    questions, et chacune déplace le résultat. Quand la cible est-elle détenue ?
    Que deviennent les poids entre deux rééquilibrages ? Contre quoi la rotation
    se mesure-t-elle ? Quand le coût est-il payé ?

    **Les quatre réponses du moteur.** La cible décidée à *t* est détenue à
    partir de *t + ℓ*. Entre deux rééquilibrages, les poids dérivent avec le
    marché plutôt que de rester figés. La rotation se mesure contre ces poids
    dérivés, jamais contre la cible précédente. Le coût est payé dans la période
    où la transaction a lieu.

    **La formule du rendement de période.**

    .. math::

        r_t^{brut} = \sum_{i=1}^{N} w_{i,t}\, r_{i,t}
        \qquad
        r_t^{net} = r_t^{brut} - c_t
        \qquad
        c_t = C\!\left(b_t \rightarrow w_t\right)

    Args:
        weights: les poids cibles, une ligne par date de décision, une colonne
            par actif. Ses dates doivent exister dans ``returns``.
        returns: les rendements simples de période, une ligne par date, une
            colonne par actif. La ligne datée *t* porte le rendement réalisé
            entre *t-1* et *t*.
        cost_model: un objet portant une méthode ``cost`` ou une fonction de
            même signature, appelée avec ``previous``, ``target`` et
            ``context``. Le contexte porte les poids d'avant transaction, la
            cible, l'échange, et le rendement de la période PRÉCÉDENTE. Celui de
            la période en cours en est absent, parce qu'il n'est pas réalisé
            quand la transaction a lieu. Son retour est un nombre ou une
            ventilation par composante. ``None`` rend un backtest sans frais,
            dont le seul usage est de mesurer ce que les frais retirent.
        execution_lag: le nombre de périodes entre la décision et la détention.
        frequency: la fréquence des périodes, qui sert à annualiser en aval.
        rebalance: les dates auxquelles négocier. ``None`` autorise toute date
            portant une cible. Une fréquence sélectionne les fins de période.
            Un index sélectionne exactement ces dates.
        initial_capital: la richesse de départ, qui met la courbe de richesse à
            l'échelle sans toucher aux rendements.
        allow_same_bar_execution: autorise ``execution_lag=0``. À réserver à la
            mesure de la fuite elle-même.

    Returns:
        Le :class:`BacktestResult` complet.

    Raises:
        LookAheadError: le décalage est nul sans autorisation explicite, ou il
            est négatif.
        ConfigError: un actif ou une date de ``weights`` manque dans
            ``returns``, le capital initial n'est pas strictement positif, ou le
            modèle de coût n'est ni appelable ni porteur d'une méthode ``cost``.
        DataQualityError: un rendement manque sur un actif détenu, une ligne de
            poids est partiellement manquante, ou un coût n'est pas fini.
        InsufficientDataError: l'un des deux tableaux est vide.

    Example:
        Deux actifs et un décalage de un. La cible du 2 janvier, 60 % et 40 %,
        est détenue le 3 janvier. Si les rendements du 3 janvier valent +10 % et
        -5 %, le rendement brut de la journée vaut 4 %, et les poids dérivent
        vers 63,46 % et 36,54 % pour la journée suivante.

    Note:
        **Variables.** :math:`w_{i,t}` est le poids détenu pendant la période
        *t*, :math:`b_{i,t}` le poids dérivé à l'entrée de la période, avant
        transaction, :math:`r_{i,t}` le rendement simple de l'actif *i*,
        :math:`c_t` le coût de la période et :math:`N` le nombre d'actifs.

        **Hypothèses.** Les poids sont des fractions de valeur liquidative. Le
        rééquilibrage est instantané et complet, sans exécution partielle. Aucun
        flux externe n'entre ni ne sort. Le coût est prélevé sur le rendement de
        la période, ce qui suppose la transaction faite à son début. La dérive
        des poids se calcule sur la valeur liquidative avant frais. Le coût
        réduit donc la richesse sans redistribuer les poids, et cet écart du
        second ordre n'a pas été mesuré ici.

        **Provenance.** Le décalage d'une barre suit Bailey et López de Prado
        (2014), sur la surévaluation des backtests. La mesure de la rotation
        contre les poids dérivés suit Grinold et Kahn (2000). Statut de ces deux
        références : rapportées, non revérifiées au texte ici.

        **Limites.** Le moteur est vectoriel sur les poids, pas sur les ordres.
        Il ignore la liquidité, la taille du portefeuille, le refus d'un ordre,
        et la différence entre l'ouverture et la clôture. Ces effets vivent dans
        le modèle de coût et dans le modèle d'exécution, où ils se mesurent
        séparément.

        **Alternatives.** Un moteur événementiel rejoue le carnet d'ordres et
        capte ce que celui-ci ignore, au prix d'une complexité et d'un temps de
        calcul sans commune mesure. Le laboratoire garde le moteur vectoriel
        pour la recherche, et contrôle les résultats retenus sur un moteur
        événementiel externe.

        **Pourquoi cette méthode ici.** La recherche compare des centaines de
        variantes. Un moteur qui coûte une seconde par variante permet la
        validation croisée combinatoire ; un moteur qui coûte une minute ne la
        permet pas.

        **Comment vérifier.** Trois contrôles indépendants du code. Des poids
        constants sans frais ni décalage rendent exactement le rendement pondéré
        du panier, que produit un simple produit matriciel. Un signal égal au
        signe du rendement de la période rend un rendement positif tous les
        jours avec un décalage nul, et une espérance nulle avec un décalage de
        un. Un portefeuille laissé dériver affiche une rotation nulle, alors
        qu'une mesure contre les cibles précédentes en affiche une positive.
    """
    frame_w = _as_frame(weights, label="weights")
    frame_r = _as_frame(returns, label="returns")

    if not isinstance(execution_lag, int | np.integer) or isinstance(execution_lag, bool):
        raise ConfigError(f"execution_lag doit être un entier, reçu {type(execution_lag).__name__}.")
    lag = int(execution_lag)
    if lag == 0 and not allow_same_bar_execution:
        raise LookAheadError(
            "execution_lag=0 fait négocier à la barre qui a servi à décider. Sur un signal égal "
            "au signe du rendement du jour, cette seule convention rend un gain tous les jours. "
            "Passer allow_same_bar_execution=True pour mesurer la fuite volontairement."
        )
    if initial_capital <= 0.0:
        raise ConfigError(f"initial_capital doit être strictement positif, reçu {initial_capital}.")

    absents = frame_w.columns.difference(frame_r.columns)
    if len(absents) > 0:
        raise ConfigError(f"actifs présents dans weights et absents de returns : {absents.tolist()}")
    hors_index = frame_w.index.difference(frame_r.index)
    if len(hors_index) > 0:
        raise ConfigError(
            f"{len(hors_index)} date(s) de weights absentes de returns, dont {hors_index[0]}. "
            "Une cible datée d'un jour sans rendement ne se détient pas."
        )

    assets = frame_w.columns
    index = frame_r.index
    _check_returns_complete(frame_r, assets)
    used_returns = frame_r.loc[:, assets].astype(float)

    targets = frame_w.astype(float).reindex(index)
    executed = apply_execution_lag(targets, lag)
    tradable = _rebalance_mask(index, rebalance)
    cost_fn = _resolve_cost_model(cost_model)

    zeros = pd.Series(0.0, index=assets)
    position_start_prev: pd.Series | None = None
    previous_returns: pd.Series | None = None

    gross_values: list[float] = []
    cost_values: list[float] = []
    turnover_values: list[float] = []
    breakdown_rows: list[dict[str, float]] = []
    held_rows: list[pd.Series] = []
    drift_rows: list[pd.Series] = []
    leverage_values: list[float] = []

    for date in index:
        period_returns = used_returns.loc[date]
        if position_start_prev is None or previous_returns is None:
            base = zeros
        else:
            base = drifted_weights(position_start_prev, previous_returns)

        row = executed.loc[date]
        wanted = bool(tradable.loc[date]) and bool(row.notna().any())
        if wanted and bool(row.isna().any()):
            raise DataQualityError(
                f"ligne de poids partiellement manquante à la date {date}. Un actif sans cible "
                "n'est pas un actif à poids nul : le dire explicitement."
            )

        if wanted:
            target = row.astype(float)
            if position_start_prev is None or previous_returns is None:
                period_turnover = turnover(base, target, drifted=False)
            else:
                period_turnover = turnover(
                    position_start_prev,
                    target,
                    drifted=True,
                    period_returns=previous_returns,
                )
            components = _components_for(
                cost_fn,
                base=base,
                target=target,
                previous_returns=previous_returns,
                period_turnover=period_turnover,
                date=date,
            )
        else:
            target = base
            period_turnover = 0.0
            components = {}

        gross = float((target * period_returns).sum())
        period_cost = float(sum(components.values()))
        end_of_period = drifted_weights(target, period_returns)

        gross_values.append(gross)
        cost_values.append(period_cost)
        turnover_values.append(float(period_turnover))
        breakdown_rows.append(components)
        held_rows.append(target)
        drift_rows.append(base)
        leverage_values.append(0.5 * (float(target.abs().sum()) + float(end_of_period.abs().sum())))

        position_start_prev = target
        previous_returns = period_returns

    gross_returns = pd.Series(gross_values, index=index, name="gross_return")
    costs = pd.Series(cost_values, index=index, name="cost")
    net_returns = (gross_returns - costs).rename("net_return")
    turnover_series_ = pd.Series(turnover_values, index=index, name="turnover")
    held = pd.DataFrame(held_rows, index=index, columns=assets)
    drift = pd.DataFrame(drift_rows, index=index, columns=assets)
    breakdown = pd.DataFrame(breakdown_rows, index=index).fillna(0.0)
    if breakdown.empty:
        breakdown = pd.DataFrame({TOTAL_COST_COLUMN: 0.0}, index=index)

    metadata: dict[str, Any] = {
        "sample": SampleTag.IN_SAMPLE,
        "cost_basis": CostBasis.NET,
        "cost_model": "aucun" if cost_model is None else type(cost_model).__name__,
        "cost_components": list(breakdown.columns),
        "execution_lag": lag,
        "same_bar_execution": lag == 0,
        "rebalance": _describe_rebalance(rebalance),
        "frequency": frequency,
        "start": index[0],
        "end": index[-1],
        "n_periods": len(index),
        "n_assets": len(assets),
        "initial_capital": float(initial_capital),
        "turnover_convention": "half_sum",
        "drift_basis": "nav",
    }
    _LOG.info(
        "backtest terminé",
        extra={
            "n_periods": metadata["n_periods"],
            "execution_lag": lag,
            "cost_total": float(costs.sum()),
        },
    )
    return BacktestResult(
        gross_returns=gross_returns,
        net_returns=net_returns,
        costs=costs,
        cost_breakdown=breakdown,
        turnover=turnover_series_,
        target_weights=targets,
        executed_weights=held,
        drifted_weights=drift,
        gross_exposure=held.abs().sum(axis=1).rename("gross_exposure"),
        net_exposure=held.sum(axis=1).rename("net_exposure"),
        leverage=pd.Series(leverage_values, index=index, name="leverage"),
        frequency=frequency,
        metadata=metadata,
    )


def _describe_rebalance(rebalance: Frequency | pd.Index | None) -> str:
    """Rend la description textuelle de la politique de rééquilibrage, pour les métadonnées."""
    if rebalance is None:
        return "toute date portant une cible"
    if isinstance(rebalance, Frequency):
        return rebalance.value
    return f"index explicite de {len(rebalance)} dates"


def _components_for(
    cost_fn: CostCallable | None,
    *,
    base: pd.Series,
    target: pd.Series,
    previous_returns: pd.Series | None,
    period_turnover: float,
    date: object,
) -> dict[str, float]:
    """Appelle le modèle de coût et rend sa ventilation, ou un dictionnaire vide.

    Le contexte ne porte que de l'information antérieure à la transaction. La
    colonne de rendement est celle de la période PRÉCÉDENTE, celle qui a produit
    les poids dérivés. Le rendement de la période en cours reste dehors : la
    transaction a lieu à son début, quand ce rendement n'est pas encore réalisé.

    Args:
        cost_fn: la fonction de coût résolue, ou ``None``.
        base: les poids dérivés d'avant transaction.
        target: les poids visés.
        previous_returns: les rendements de la période précédente, ou ``None``
            à la toute première période, où aucune n'existe.
        period_turnover: la rotation de la transaction.
        date: la date, pour le message d'erreur et pour les attributs.

    Returns:
        La ventilation du coût par composante.
    """
    if cost_fn is None:
        return {}
    if previous_returns is None:
        known = pd.Series(np.nan, index=target.index, dtype=float)
    else:
        known = previous_returns.reindex(target.index)
    context = pd.DataFrame(
        {
            "previous": base,
            "target": target,
            "trade": target - base,
            "previous_return": known,
        }
    )
    context.attrs["date"] = date
    context.attrs["turnover"] = float(period_turnover)
    raw = cost_fn(previous=base, target=target, context=context)
    return _cost_components(raw, date=date)


def volatility_target(
    returns_forecast: pd.Series,
    target_annual: float,
    frequency: Frequency,
    leverage_cap: float,
    leverage_floor: float = 0.0,
    smoothing: int | None = None,
) -> pd.Series:
    r"""Rend le levier qui vise une volatilité annuelle constante, plafond compris.

    **Le problème.** Une stratégie dont la volatilité varie dans le temps ne
    délivre pas le risque annoncé. Elle en délivre trop dans les régimes agités,
    et pas assez dans les régimes calmes, si bien que sa performance est
    dominée par une poignée de mois.

    **L'intuition.** Si le risque prévu vaut la moitié de la cible, on double la
    position ; s'il vaut le double, on la divise par deux.

    **La formule.**

    .. math::

        L_t = \operatorname{clip}\!\left(
            \frac{\sigma^{*}}{\hat{\sigma}_t \sqrt{N}},\; L_{min},\; L_{max}
        \right)

    **Le plafond n'est pas un détail de mise en oeuvre.** Le levier est
    l'inverse d'une quantité qui peut s'approcher de zéro, donc il n'est pas
    borné. Une volatilité prévue de 0,1 % annualisée contre une cible de 10 %
    demande un levier de cent. Ce cas n'est pas théorique : il suffit d'une
    fenêtre d'estimation tombant sur une série de séances plates, ou d'un titre
    suspendu dont le prix ne bouge plus. Sans plafond, une seule date de ce type
    prend toute la performance du backtest, dans un sens ou dans l'autre, et le
    reste de l'échantillon devient décoratif.

    Args:
        returns_forecast: la volatilité prévue pour chaque période, exprimée
            dans l'unité d'un rendement de période et non annualisée. Elle doit
            être construite avec l'information antérieure à la date, typiquement
            par une fenêtre glissante suivie d'un décalage.
        target_annual: la volatilité annuelle visée, en fraction. 0,10 vise
            10 % par an.
        frequency: la fréquence des périodes, qui fixe le facteur
            d'annualisation :math:`\sqrt{N}`.
        leverage_cap: le levier maximal autorisé. Obligatoire, pour la raison
            écrite ci-dessus.
        leverage_floor: le levier minimal, nul par défaut.
        smoothing: la longueur d'une moyenne mobile appliquée au levier après
            écrêtage, pour éviter de négocier le bruit de l'estimateur. ``None``
            ne lisse pas.

    Returns:
        La série des leviers, indexée comme la prévision, nommée ``leverage``.
        Les dates dont la prévision manque portent un levier manquant.

    Raises:
        TypeError: la prévision n'est pas une série pandas.
        InsufficientDataError: la prévision est vide ou entièrement manquante.
        DataQualityError: l'index est troué au milieu, non trié, porte des
            doublons, ou une volatilité prévue est négative.
        ConfigError: la cible est négative, le plafond n'est pas strictement
            positif, le plancher dépasse le plafond, ou le lissage n'est pas un
            entier positif.

    Example:
        Une prévision quotidienne de 1,26 % par séance s'annualise à
        :math:`0{,}0126 \times \sqrt{252} = 20{,}0\ \%`. Pour une cible de 10 %,
        le levier vaut exactement 0,50.

    Note:
        **Variables.** :math:`\hat{\sigma}_t` est la volatilité prévue par
        période, :math:`N` le nombre de périodes par an, :math:`\sigma^{*}` la
        cible annuelle, :math:`L_t` le levier appliqué à la date *t*.

        **Hypothèses.** La volatilité est persistante, ce qui rend une prévision
        possible. Les rendements sont non corrélés dans le temps, sans quoi la
        racine de *N* n'annualise pas correctement, et
        ``analytics.risk.annualization_bias`` mesure l'ampleur de l'écart.

        **Provenance.** La cible de volatilité est la forme retenue par
        Moskowitz, Ooi et Pedersen (2012) pour le momentum de séries
        temporelles. Harvey, Hoyle, Rattray, Sargaison, Taylor et Van Hemert
        (2018) mesurent ce qu'elle apporte vraiment. Statut de ces deux
        références : rapportées, non revérifiées au texte ici.

        **L'alignement, et ce que la fonction peut en vérifier.** La prévision
        doit être connue avant la période qu'elle dimensionne. La fonction
        vérifie ce qui se vérifie depuis la série seule : index trié, sans
        doublon, et sans trou au milieu. Elle ne peut pas prouver que la valeur
        datée *t* n'a pas été calculée avec le rendement de *t*, cette
        information n'existant pas dans la série. Le contrôle correspondant
        appartient à l'appelant, et le laboratoire le tient par un test qui
        compare la volatilité réalisée à la cible.

        **Limites.** Viser la volatilité ne vise pas le repli maximal. Une
        stratégie à volatilité constante peut perdre 40 % dans une tendance
        lente, sans qu'aucune volatilité ne s'élève. Le levier ajoute aussi un
        coût de rotation, absent de cette formule et à mesurer dans le backtest.

        **Alternatives.** Une prévision par modèle GARCH remplace la fenêtre
        glissante et réagit plus vite. Un levier fonction du repli courant vise
        une autre grandeur. Ce module rend le levier, pas la prévision, ce qui
        laisse le choix de l'estimateur entièrement libre.

        **Comment vérifier.** Trois contrôles. Une prévision constante
        s'annualisant au double de la cible rend exactement 0,5. Une prévision
        nulle rend le plafond, jamais l'infini. Sur une série simulée à
        volatilité connue, la volatilité réalisée de la stratégie levée
        s'approche de la cible, l'écart restant s'expliquant par l'erreur
        d'estimation de la fenêtre.
    """
    if not isinstance(returns_forecast, pd.Series):
        raise TypeError(
            f"returns_forecast doit être un pandas.Series, reçu {type(returns_forecast).__name__}"
        )
    if target_annual < 0.0:
        raise ConfigError(f"target_annual doit être positif ou nul, reçu {target_annual}.")
    if leverage_cap <= 0.0:
        raise ConfigError(
            f"leverage_cap doit être strictement positif, reçu {leverage_cap}. Le plafond est "
            "la seule borne d'une quantité qui diverge quand la volatilité prévue tend vers zéro."
        )
    if leverage_floor < 0.0 or leverage_floor > leverage_cap:
        raise ConfigError(
            f"leverage_floor ({leverage_floor}) doit tenir entre zéro et leverage_cap ({leverage_cap})."
        )
    if smoothing is not None and (not isinstance(smoothing, int) or smoothing < 1):
        raise ConfigError(f"smoothing doit être un entier supérieur ou égal à un, reçu {smoothing!r}.")

    forecast = returns_forecast.astype(float)
    _verify_forecast_alignment(forecast)

    factor = float(np.sqrt(annualization_factor(frequency)))
    annualized = forecast * factor
    values = annualized.to_numpy()
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        raw = np.where(values > FORECAST_FLOOR, target_annual / values, np.inf)
    levered = pd.Series(raw, index=forecast.index).where(forecast.notna())
    clipped = levered.clip(lower=leverage_floor, upper=leverage_cap)
    if smoothing is not None:
        clipped = clipped.rolling(window=smoothing, min_periods=1).mean()
    return clipped.rename("leverage")


def _verify_forecast_alignment(forecast: pd.Series) -> None:
    """Vérifie ce qu'une série de prévisions permet de vérifier seule.

    L'index doit être trié et sans doublon, sans quoi « la valeur précédente »
    n'a pas de sens. Les valeurs manquantes sont admises au début, où une
    fenêtre glissante n'a pas encore assez d'observations, et refusées au
    milieu, où elles signalent un trou de données.

    Args:
        forecast: la série de volatilités prévues, déjà convertie en flottants.

    Raises:
        InsufficientDataError: la série est vide ou entièrement manquante.
        DataQualityError: index non trié, index à doublons, trou au milieu, ou
            volatilité négative.
    """
    if forecast.empty:
        raise InsufficientDataError("returns_forecast est vide : aucun levier à calculer.")
    if forecast.index.has_duplicates:
        raise DataQualityError("returns_forecast porte des dates en double.")
    if not forecast.index.is_monotonic_increasing:
        raise DataQualityError("returns_forecast n'est pas trié par date croissante.")

    present = forecast.notna().to_numpy()
    if not present.any():
        raise InsufficientDataError("returns_forecast est entièrement manquant.")
    first = int(np.argmax(present))
    if not present[first:].all():
        raise DataQualityError(
            "returns_forecast porte un trou après sa première valeur connue. Une prévision "
            "absente au milieu de l'échantillon dimensionne une position au hasard."
        )
    negatives = forecast.dropna() < 0.0
    if bool(negatives.any()):
        raise DataQualityError("returns_forecast porte au moins une volatilité négative.")


def equity_curve(result: BacktestResult) -> pd.Series:
    """Rend la richesse cumulée nette du backtest, capital initial compris.

    Args:
        result: le résultat rendu par :func:`run_backtest`.

    Returns:
        La série de richesse, indexée comme les rendements, partant du capital
        initial composé du premier rendement net.

    Note:
        Le calcul appartient à
        :func:`quantlab.analytics.returns.cumulative_wealth`. Cette fonction ne
        fait que lui passer la série nette et le capital initial lu dans les
        métadonnées, pour qu'une même courbe ne se calcule pas de deux façons.
    """
    initial = float(result.metadata.get("initial_capital", 1.0))
    return cumulative_wealth(result.net_returns, initial=initial).rename("equity")

"""La capacité d'une stratégie : à partir de quelle taille son alpha net s'annule.

**Le problème.** Un backtest rend un rendement par dollar, comme si le dollar
suivant coûtait le même prix que le premier. Il ne dit rien de ce qui arrive
quand la stratégie gère cent millions plutôt qu'un million. Chaque ordre devient
alors une part plus grande du volume du marché, et le prix bouge contre lui. Une
stratégie au ratio de Sharpe brut de 2 et à la capacité de dix millions de
dollars n'intéresse aucun fonds.

**Ce que le module fait.** Il rejoue les mêmes poids à plusieurs tailles de
capital, avec un coût d'impact qui croît en racine carrée de la participation
au volume. Il rend la courbe du rendement net contre la taille, et le point où
cette courbe traverse zéro est la capacité.

**Ce qu'il ne fait pas.** Il ne calibre pas le coefficient d'impact, qu'aucune
donnée gratuite ne permet de mesurer. Il ne modélise ni carnet d'ordres ni
exécution étalée au-delà d'un nombre de jours déclaré. Tout chiffre sorti d'ici
porte le statut MODÉLISÉ.

**La forme fermée qui vérifie le moteur.** Sous la loi en racine carrée,
l'impact d'une transaction vaut
:math:`\\kappa \\sigma |\\delta| \\sqrt{|\\delta| A / (k \\cdot ADV)}`, où
:math:`A` est le capital et :math:`k` le nombre de jours d'exécution. Il est
donc proportionnel à :math:`\\sqrt{A}`. Le rendement net moyen s'écrit
:math:`g - s - \\sqrt{A}\\,K`, avec :math:`g` le brut moyen, :math:`s` le
demi-écart moyen payé et :math:`K` la charge d'impact moyenne au capital unité.
La capacité vaut alors :math:`((g - s) / K)^2`. Cette formule fermée sert de
contrôle indépendant de la courbe que le moteur rend point par point, et les
tests exigent que les deux coïncident tant qu'aucune participation n'est
écrêtée.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

import pandas as pd

from quantlab.analytics.ratios import sharpe_ratio
from quantlab.backtest.engine import BacktestResult, run_backtest
from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError, QuantLabError
from quantlab.core.logging import get_logger
from quantlab.core.types import Frequency, ReturnFrame, WeightFrame, Weights
from quantlab.execution.costs import (
    ADV_FRACTION_COLUMN,
    DEFAULT_PARTICIPATION_CAP,
    VOLATILITY_COLUMN,
    BaseCostModel,
    CostBreakdown,
    LinearCostModel,
    SqrtImpactModel,
    signed_trades,
)

__all__ = [
    "DEFAULT_ADV_WINDOW",
    "DEFAULT_AUM_GRID",
    "DEFAULT_EXECUTION_DAYS",
    "DEFAULT_MISSING_LIQUIDITY",
    "DEFAULT_VOLATILITY_WINDOW",
    "IMPACT_COMPONENT",
    "SPREAD_COMPONENT",
    "UNIT_AUM",
    "CapacityCurve",
    "ImpactAtScale",
    "average_daily_dollar_volume",
    "breakeven_aum",
    "capacity_curve",
    "interpolate_crossing",
    "realized_daily_volatility",
]

_LOG = get_logger(__name__)

#: La fenêtre du volume quotidien moyen, en séances. Un mois de bourse.
DEFAULT_ADV_WINDOW: int = 21

#: La fenêtre de la volatilité réalisée quotidienne, en séances.
DEFAULT_VOLATILITY_WINDOW: int = 21

#: Le nombre de jours sur lesquels un rééquilibrage est étalé, par défaut.
DEFAULT_EXECUTION_DAYS: int = 1

#: La grille de tailles de capital, en dollars, du million à dix milliards.
DEFAULT_AUM_GRID: tuple[float, ...] = (1e6, 3e6, 1e7, 3e7, 1e8, 3e8, 1e9, 3e9, 1e10)

#: Le capital unité auquel la charge d'impact est mesurée pour la forme fermée.
UNIT_AUM: float = 1.0

#: La part du ratio de Sharpe de référence au-delà de laquelle la taille est jugée tenable.
HALF_SHARPE_SHARE: float = 0.5

#: Les deux composantes que le modèle rend au moteur, en fraction du capital.
SPREAD_COMPONENT: str = "spread"
IMPACT_COMPONENT: str = "impact"

#: Ce que fait le modèle quand un actif négocié n'a plus de volume ni de volatilité.
MissingLiquidity = Literal["raise", "last_known"]
DEFAULT_MISSING_LIQUIDITY: MissingLiquidity = "raise"

#: La tolérance du contrôle de la forme fermée, en rendement moyen par période.
BREAKEVEN_CHECK_TOLERANCE: float = 1e-9


# ---------------------------------------------------------------------------
# Les deux entrées de l'impact, calculées sans regarder l'avenir
# ---------------------------------------------------------------------------


def _validated_frame(frame: pd.DataFrame, *, label: str) -> pd.DataFrame:
    """Rend le tableau en flottants, index trié, ou lève ``ConfigError``.

    Args:
        frame: un tableau indexé par date, une colonne par actif.
        label: le nom employé dans le message d'erreur.

    Returns:
        Le même tableau, converti en flottants et trié par date.

    Raises:
        ConfigError: l'index n'est pas temporel, ou porte des doublons.
    """
    if not isinstance(frame, pd.DataFrame):
        raise ConfigError(f"{label} doit être un DataFrame, reçu {type(frame).__name__}.")
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise ConfigError(f"{label} doit être indexé par date.")
    if frame.index.has_duplicates:
        raise ConfigError(f"{label} porte des dates en double.")
    return frame.astype(float).sort_index()


def average_daily_dollar_volume(
    prices: pd.DataFrame,
    volumes: pd.DataFrame,
    *,
    window: int = DEFAULT_ADV_WINDOW,
    min_periods: int | None = None,
) -> pd.DataFrame:
    r"""Rend le volume quotidien moyen en dollars, connu la veille de chaque date.

    **Le problème.** L'impact d'un ordre se mesure contre le volume que le
    marché échange d'habitude. Ce volume doit être connu au moment de décider,
    donc calculé sur les séances qui PRÉCÈDENT la date de décision, jamais sur
    la séance elle-même.

    **L'intuition.** La médiane d'un mois de volumes en dollars, décalée d'une
    séance. La médiane plutôt que la moyenne, parce qu'une seule séance de
    volume triple, un jour de rééquilibrage d'indice par exemple, doublerait
    la moyenne et flatterait la capacité.

    **La formule.**

    .. math::

        ADV_{i,t} = \operatorname{med}\left\{ P_{i,u} V_{i,u} : t - w \le u < t \right\}

    **Les variables.** :math:`P` est le prix de clôture non ajusté, :math:`V`
    le volume en titres, :math:`w` la fenêtre en séances. Le produit est en
    dollars par séance.

    **Les hypothèses.** Le prix employé est le prix de clôture du jour, non
    ajusté des dividendes, parce que le volume s'exprime en titres du jour.
    Un prix ajusté donnerait des dollars qui n'ont jamais été échangés.

    **La provenance.** La fenêtre d'un mois et la médiane suivent l'usage des
    bureaux d'exécution, sans article de référence ; statut précepte.

    **Les limites.** Le volume de Yahoo est un volume consolidé de fin de
    journée, sans distinction entre séance régulière et hors séance. Il
    inclut les transactions de bloc, qui ne sont pas de la liquidité
    disponible à un ordre ordinaire.

    **Les alternatives.** Une moyenne mobile exponentielle réagit plus vite à
    un changement de régime de liquidité. Une médiane sur trois mois lisse
    davantage.

    **Pourquoi cette méthode ici.** Un seul paramètre, robuste aux séances
    aberrantes, et un décalage explicite qui ferme la fuite temporelle.

    **Comment vérifier.** Un volume aberrant injecté à la date :math:`t` ne
    change pas la valeur rendue à :math:`t`, seulement celles de :math:`t+1`
    et des séances suivantes. C'est ce qu'un test fait.

    Args:
        prices: les prix de clôture non ajustés, une colonne par actif.
        volumes: les volumes en titres, mêmes colonnes et mêmes dates.
        window: la fenêtre en séances.
        min_periods: le nombre minimal de séances observées avant de rendre
            une valeur. Par défaut la fenêtre entière.

    Returns:
        Le volume quotidien moyen en dollars, décalé d'une séance, manquant
        tant que la fenêtre n'est pas remplie.

    Raises:
        ConfigError: la fenêtre n'est pas strictement positive, ou les deux
            tableaux ne partagent pas leurs colonnes.
    """
    if int(window) <= 0:
        raise ConfigError(f"window doit être strictement positif, reçu {window!r}.")
    p = _validated_frame(prices, label="prices")
    v = _validated_frame(volumes, label="volumes")
    if set(p.columns) != set(v.columns):
        raise ConfigError("prices et volumes doivent porter les mêmes actifs.")
    v = v.reindex(index=p.index, columns=p.columns)
    dollars = p * v
    periods = int(window) if min_periods is None else int(min_periods)
    return dollars.rolling(int(window), min_periods=periods).median().shift(1)


def realized_daily_volatility(
    returns: pd.DataFrame,
    *,
    window: int = DEFAULT_VOLATILITY_WINDOW,
    min_periods: int | None = None,
) -> pd.DataFrame:
    r"""Rend l'écart type quotidien réalisé, connu la veille de chaque date.

    **Le problème.** Le modèle d'impact multiplie la participation par la
    volatilité de l'actif. Une volatilité qui inclut la séance de décision
    regarde l'avenir, comme le fait toute mesure non décalée.

    **L'intuition.** L'écart type des rendements quotidiens du mois écoulé,
    décalé d'une séance. Rien d'annualisé : l'impact d'un ordre exécuté sur
    une séance se compare à un mouvement de prix d'une séance.

    **La formule.**

    .. math::

        \sigma_{i,t} = \operatorname{std}\left\{ r_{i,u} : t - w \le u < t \right\}

    **Les variables.** :math:`r` le rendement simple quotidien, :math:`w` la
    fenêtre en séances, l'écart type avec un degré de liberté retiré.

    **Les hypothèses.** La volatilité d'hier est celle d'aujourd'hui, ce qui
    est faux un jour de choc et vrai en moyenne.

    **La provenance.** Almgren, Thum, Hauptmann et Li (2005) emploient la
    volatilité quotidienne dans leur loi d'impact ; rapporté, non revérifié
    au texte ici.

    **Les limites.** Une fenêtre courte réagit aux chocs mais bruite le
    coût ; une fenêtre longue fait l'inverse. Le choix est déclaré et non
    optimisé.

    **Les alternatives.** Une pondération exponentielle, ou une volatilité
    implicite quand elle existe.

    **Pourquoi cette méthode ici.** La même fenêtre que le volume, pour que
    les deux entrées de l'impact décrivent le même mois.

    **Comment vérifier.** Sur une série constante, la valeur rendue est
    zéro ; sur deux rendements alternés :math:`\pm x`, elle vaut
    :math:`x\sqrt{w/(w-1)}`.

    Args:
        returns: les rendements simples quotidiens, une colonne par actif.
        window: la fenêtre en séances.
        min_periods: le nombre minimal de séances avant de rendre une valeur.

    Returns:
        L'écart type quotidien, en fraction décimale, décalé d'une séance.

    Raises:
        ConfigError: la fenêtre est inférieure à deux.
    """
    if int(window) < 2:
        raise ConfigError(f"window doit valoir au moins 2, reçu {window!r}.")
    r = _validated_frame(returns, label="returns")
    periods = int(window) if min_periods is None else int(min_periods)
    return r.rolling(int(window), min_periods=periods).std(ddof=1).shift(1)


# ---------------------------------------------------------------------------
# Le modèle de coût à une taille de capital donnée
# ---------------------------------------------------------------------------


class ImpactAtScale(BaseCostModel):
    r"""Le coût d'un rééquilibrage à une taille de capital donnée, statut MODÉLISÉ.

    **Le problème.** Le moteur de backtest raisonne en poids, sans dollars.
    Le modèle d'impact raisonne en participation, c'est-à-dire en dollars
    négociés rapportés aux dollars échangés par le marché. Il faut donc un
    modèle qui connaisse le capital, le volume de chaque actif à chaque date,
    et qui fasse la conversion.

    **L'intuition.** Un poids qui bouge de :math:`\delta` déplace
    :math:`|\delta| A` dollars. Étalé sur :math:`k` séances contre un volume
    quotidien :math:`ADV`, cet ordre représente une participation de
    :math:`|\delta| A / (k \cdot ADV)`. Le reste est la loi en racine carrée
    de :class:`~quantlab.execution.costs.SqrtImpactModel`, à laquelle ce
    modèle délègue le calcul.

    **La formule.**

    .. math::

        C_t = \underbrace{c_s \sum_i |\delta_{i,t}|}_{\text{demi-écart}}
            + \underbrace{\kappa \sum_i |\delta_{i,t}|\, \sigma_{i,t}
              \sqrt{\frac{|\delta_{i,t}|\, A}{k \cdot ADV_{i,t}}}}_{\text{impact}}

    **Les variables.** :math:`A` le capital, :math:`k` les jours
    d'exécution, :math:`c_s` le demi-écart en fraction, :math:`\kappa` le
    coefficient d'impact, :math:`\sigma` la volatilité quotidienne,
    :math:`ADV` le volume quotidien moyen en dollars.

    **Les hypothèses.** Le capital est constant sur tout l'historique. Le
    volume et la volatilité employés à une date sont les derniers connus à
    cette date ou avant. Les actifs sont indépendants les uns des autres.

    **La provenance.** La loi en racine carrée vient d'Almgren, Thum,
    Hauptmann et Li (2005) et de Gatheral (2010), rapportés dans
    :class:`~quantlab.execution.costs.SqrtImpactModel`. La conversion par le
    capital est de simple arithmétique.

    **Les limites.** Le coefficient n'est calibré nulle part. Le capital
    constant surestime la participation des débuts d'historique d'un fonds
    réel, qui grossit. Une participation qui dépasse le plafond est écrêtée,
    et le coût rendu est alors un minorant : le modèle le journalise et le
    compte, il ne le cache pas.

    **Les alternatives.** Un capital qui suit une trajectoire déclarée. Un
    modèle d'impact à exposant estimé plutôt que fixé à un demi.

    **Pourquoi cette méthode ici.** Elle réutilise les deux modèles de coût
    existants sans en réécrire la formule, et elle rend au moteur les deux
    composantes séparément, ce qui permet la forme fermée du module.

    **Comment vérifier.** Multiplier le capital par quatre double l'impact
    et laisse le demi-écart inchangé. Étaler l'exécution sur quatre séances
    divise l'impact par deux. Doubler le volume le divise par racine de
    deux. Les tests font les trois.

    Args:
        aum: le capital géré, en dollars, strictement positif.
        adv_dollars: le volume quotidien moyen en dollars, une colonne par
            actif, indexé par date, tel que rend
            :func:`average_daily_dollar_volume`.
        volatility: la volatilité quotidienne en fraction, mêmes actifs,
            telle que rend :func:`realized_daily_volatility`.
        coefficient: le coefficient :math:`\kappa`, déclaré et non calibré.
        spread_bps: le demi-écart payé, en points de base du montant négocié.
        execution_days: le nombre de séances sur lesquelles chaque
            rééquilibrage est étalé.
        participation_cap: la participation quotidienne maximale, au-delà
            de laquelle le coût est un minorant.
        on_missing_liquidity: ``raise`` pour refuser toute transaction sur un
            actif sans volume ni volatilité connus à la date ; ``last_known``
            pour lui prêter le dernier volume strictement positif et la
            dernière volatilité connus. Le second cas sert aux sorties de cote,
            où un titre garde des cotations fantômes à volume nul et où la
            stratégie solde encore sa position. Chaque emprunt est compté dans
            le journal de participation.

    Raises:
        ConfigError: un paramètre est hors domaine.
    """

    def __init__(
        self,
        *,
        aum: float,
        adv_dollars: pd.DataFrame,
        volatility: pd.DataFrame,
        coefficient: float = 1.0,
        spread_bps: float = 0.0,
        execution_days: int = DEFAULT_EXECUTION_DAYS,
        participation_cap: float = DEFAULT_PARTICIPATION_CAP,
        on_missing_liquidity: MissingLiquidity = DEFAULT_MISSING_LIQUIDITY,
    ) -> None:
        capital = float(aum)
        if not math.isfinite(capital) or capital <= 0.0:
            raise ConfigError(f"aum doit être fini et strictement positif, reçu {aum!r}.")
        days = int(execution_days)
        if days < 1:
            raise ConfigError(f"execution_days doit valoir au moins 1, reçu {execution_days!r}.")
        self.aum = capital
        self.execution_days = days
        self.adv_dollars = _validated_frame(adv_dollars, label="adv_dollars")
        self.volatility = _validated_frame(volatility, label="volatility")
        if on_missing_liquidity not in ("raise", "last_known"):
            raise ConfigError(
                f"on_missing_liquidity doit valoir 'raise' ou 'last_known', reçu {on_missing_liquidity!r}."
            )
        self.on_missing_liquidity: MissingLiquidity = on_missing_liquidity
        self._adv_last_known = self.adv_dollars.where(self.adv_dollars > 0.0).ffill()
        self._volatility_last_known = self.volatility.ffill()
        self.coefficient = float(coefficient)
        self.spread_bps = float(spread_bps)
        self.participation_cap = float(participation_cap)
        self._impact = SqrtImpactModel(coefficient=self.coefficient, participation_cap=self.participation_cap)
        self._linear = LinearCostModel(spread_bps=self.spread_bps) if self.spread_bps > 0.0 else None
        #: Une ligne par rééquilibrage : date, participation maximale, nombre
        #: d'actifs écrêtés, nombre d'actifs négociés. Sert au diagnostic.
        self.participation_log: list[dict[str, Any]] = []

    @staticmethod
    def _row_at(frame: pd.DataFrame, date: pd.Timestamp, *, label: str) -> pd.Series:
        """Rend la dernière ligne datée au plus tard à ``date``.

        Args:
            frame: le tableau indexé par date.
            date: la date de décision.
            label: le nom du tableau pour le message d'erreur.

        Returns:
            La ligne retenue, indexée par actif.

        Raises:
            InsufficientDataError: aucune ligne n'existe à cette date ou avant.
        """
        position = int(frame.index.searchsorted(date, side="right")) - 1
        if position < 0:
            raise InsufficientDataError(
                f"{label} ne porte aucune valeur à la date {date.date()} ni avant. "
                "L'impact ne se chiffre pas sur un volume inconnu."
            )
        return frame.iloc[position]

    def _enriched_context(self, context: pd.DataFrame, assets: pd.Index) -> pd.DataFrame:
        """Construit le contexte que le modèle en racine carrée exige.

        Args:
            context: le contexte fourni par le moteur, dont l'attribut ``date``.
            assets: l'union des actifs détenus et visés.

        Returns:
            Un tableau indexé par actif portant la volatilité et le volume
            quotidien moyen en FRACTION du capital, multiplié par le nombre de
            jours d'exécution.
        """
        date = pd.Timestamp(context.attrs["date"])
        adv_row = self._row_at(self.adv_dollars, date, label="adv_dollars").reindex(assets)
        vol_row = self._row_at(self.volatility, date, label="volatility").reindex(assets)
        self._borrowed = pd.Index([])
        if self.on_missing_liquidity == "last_known":
            faulty = assets[adv_row.isna() | (adv_row <= 0.0) | vol_row.isna()]
            if len(faulty) > 0:
                adv_row.loc[faulty] = self._row_at(self._adv_last_known, date, label="adv_dollars").reindex(
                    faulty
                )
                vol_row.loc[faulty] = self._row_at(
                    self._volatility_last_known, date, label="volatility"
                ).reindex(faulty)
                self._borrowed = faulty
        enriched = pd.DataFrame(index=assets)
        for column in context.columns:
            enriched[column] = context[column].reindex(assets)
        enriched[VOLATILITY_COLUMN] = vol_row.to_numpy(dtype=float)
        enriched[ADV_FRACTION_COLUMN] = adv_row.to_numpy(dtype=float) * self.execution_days / self.aum
        enriched.attrs = dict(context.attrs)
        return enriched

    def breakdown(
        self,
        *,
        previous: Weights,
        target: Weights,
        context: pd.DataFrame | None = None,
    ) -> CostBreakdown:
        """Rend le demi-écart et l'impact du rééquilibrage à la date du contexte.

        Args:
            previous: les poids détenus avant le rééquilibrage.
            target: les poids visés.
            context: le tableau du moteur, dont ``attrs["date"]`` est exigé.

        Returns:
            La décomposition, dont seuls ``spread_bps`` et ``impact_bps`` sont
            non nuls.

        Raises:
            ConfigError: le contexte est absent ou ne porte pas de date.
            DataQualityError: un actif négocié n'a ni volume ni volatilité.
        """
        if context is None or "date" not in context.attrs:
            raise ConfigError(
                "ImpactAtScale exige context.attrs['date'] : le volume et la volatilité "
                "se lisent à la date de la transaction, et le moteur de backtest la fournit."
            )
        base = pd.Series(previous, dtype=float)
        goal = pd.Series(target, dtype=float)
        trades = signed_trades(base, goal, context)
        moved = trades[trades.abs() > 0.0]
        enriched = self._enriched_context(context, trades.index)
        if not moved.empty:
            adv_fraction = enriched.loc[moved.index, ADV_FRACTION_COLUMN]
            sigma = enriched.loc[moved.index, VOLATILITY_COLUMN]
            faulty = moved.index[adv_fraction.isna() | (adv_fraction <= 0.0) | sigma.isna()]
            if len(faulty) > 0:
                raise DataQualityError(
                    "volume quotidien moyen ou volatilité manquants sur des actifs négociés à la date "
                    f"{pd.Timestamp(context.attrs['date']).date()} : {faulty.tolist()}. Relâcher "
                    "min_periods des deux entrées si la lacune est une sortie de cote, sinon la déclarer."
                )
            participation = moved.abs() / adv_fraction
            self.participation_log.append(
                {
                    "date": pd.Timestamp(context.attrs["date"]),
                    "max_participation": float(participation.max()),
                    "asset_max": str(participation.idxmax()),
                    "n_clipped": int((participation > self.participation_cap).sum()),
                    "n_traded": len(moved),
                    "n_last_known": len(self._borrowed.intersection(moved.index)),
                }
            )
        impact = self._impact.breakdown(previous=base, target=goal, context=enriched)
        if self._linear is None:
            return impact
        return impact + self._linear.breakdown(previous=base, target=goal, context=context)

    def cost(
        self,
        *,
        previous: Weights,
        target: Weights,
        context: pd.DataFrame | None = None,
    ) -> Mapping[str, float]:  # type: ignore[override]
        """Rend les deux composantes en fraction du capital, pour le moteur.

        Le moteur additionne les composantes et les garde en colonnes séparées,
        ce qui permet de lire l'impact seul dans ``cost_breakdown``.

        Args:
            previous: les poids détenus avant le rééquilibrage.
            target: les poids visés.
            context: le tableau du moteur.

        Returns:
            Un dictionnaire ``{"spread": ..., "impact": ...}`` en fraction.
        """
        parts = self.breakdown(previous=previous, target=target, context=context)
        return {
            SPREAD_COMPONENT: parts.spread_bps / 10_000.0,
            IMPACT_COMPONENT: parts.impact_bps / 10_000.0,
        }

    def clipped_share(self) -> float:
        """Rend la part des rééquilibrages où au moins un actif a été écrêté."""
        if not self.participation_log:
            return 0.0
        clipped = sum(1 for row in self.participation_log if row["n_clipped"] > 0)
        return clipped / len(self.participation_log)

    def max_participation(self) -> float:
        """Rend la plus grande participation quotidienne rencontrée, ou zéro."""
        if not self.participation_log:
            return 0.0
        return max(float(row["max_participation"]) for row in self.participation_log)

    def last_known_share(self) -> float:
        """Rend la part des rééquilibrages où au moins un actif a emprunté son dernier volume connu."""
        if not self.participation_log:
            return 0.0
        borrowed = sum(1 for row in self.participation_log if row.get("n_last_known", 0) > 0)
        return borrowed / len(self.participation_log)

    def binding_assets(self, top: int = 5) -> list[tuple[str, float]]:
        """Rend les actifs qui portent le plus souvent la participation maximale, avec leur pire valeur.

        Args:
            top: le nombre d'actifs rendus.

        Returns:
            Des paires (actif, participation maximale), les plus fréquents d'abord.
        """
        if not self.participation_log:
            return []
        frame = pd.DataFrame(self.participation_log)
        worst = frame.groupby("asset_max")["max_participation"].agg(["size", "max"])
        worst = worst.sort_values(["size", "max"], ascending=False).head(top)
        return [(str(name), float(row["max"])) for name, row in worst.iterrows()]

    def __repr__(self) -> str:
        """Rend la représentation lisible du modèle et de ses paramètres."""
        return (
            f"ImpactAtScale(aum={self.aum:g}, coefficient={self.coefficient}, "
            f"spread_bps={self.spread_bps}, execution_days={self.execution_days})"
        )


# ---------------------------------------------------------------------------
# La courbe de capacité
# ---------------------------------------------------------------------------


def breakeven_aum(gross_mean: float, spread_mean: float, impact_load_mean: float) -> float | None:
    r"""Rend le capital qui annule le rendement net moyen, en forme fermée.

    **Le problème.** Lire la capacité sur une grille de tailles donne un
    intervalle, pas un nombre, et le nombre dépend de la grille.

    **L'intuition.** L'impact croît comme la racine du capital. Le rendement
    net moyen est donc une droite en :math:`\sqrt{A}`, et une droite se
    coupe à zéro sans grille.

    **La formule.**

    .. math::

        \bar{r}^{net}(A) = g - s - \sqrt{A}\, K = 0
        \quad \Longleftrightarrow \quad
        A^{\ast} = \left(\frac{g - s}{K}\right)^{2}

    **Les variables.** :math:`g` le rendement brut moyen par période,
    :math:`s` le coût de demi-écart moyen par période, :math:`K` la charge
    d'impact moyenne par période mesurée au capital unité.

    **Les hypothèses.** Aucune participation ne dépasse le plafond en
    dessous de :math:`A^{\ast}`. Quand elle le dépasse, la loi en racine
    carrée n'est plus crédible, et la capacité retenue devient le capital où
    le plafond est atteint.

    **La provenance.** Arithmétique sur la loi en racine carrée ; aucune
    référence externe.

    **Les limites.** La formule porte sur la moyenne arithmétique, pas sur le
    rendement composé ni sur le ratio de Sharpe. Le ratio de Sharpe s'annule
    au même point, puisque son numérateur est cette moyenne.

    **Les alternatives.** L'interpolation sur la grille, que
    :func:`interpolate_crossing` fait, et que le test compare à cette forme.

    **Pourquoi cette méthode ici.** Elle rend un contrôle indépendant du
    moteur : si la courbe rendue point par point ne passe pas par zéro à
    :math:`A^{\ast}`, l'un des deux calculs est faux.

    **Comment vérifier.** Relancer le moteur au capital :math:`A^{\ast}` et
    constater que le rendement net moyen vaut zéro à la précision machine,
    ce que :func:`capacity_curve` fait et publie.

    Args:
        gross_mean: le rendement brut moyen par période.
        spread_mean: le coût de demi-écart moyen par période, positif.
        impact_load_mean: la charge d'impact moyenne au capital unité, positive.

    Returns:
        ``None`` si aucune transaction ne porte d'impact, la capacité n'étant
        alors pas bornée par ce modèle. Sinon zéro si l'alpha net de demi-écart
        est déjà négatif. Sinon le capital d'annulation en dollars.

    Raises:
        ConfigError: une entrée n'est pas finie, ou une charge est négative.
    """
    values = (float(gross_mean), float(spread_mean), float(impact_load_mean))
    if not all(math.isfinite(v) for v in values):
        raise ConfigError(f"les trois moyennes doivent être finies, reçu {values}.")
    g, s, k = values
    if s < 0.0 or k < 0.0:
        raise ConfigError("spread_mean et impact_load_mean sont des coûts, donc positifs ou nuls.")
    if k == 0.0:
        return None
    if g - s <= 0.0:
        return 0.0
    return ((g - s) / k) ** 2


def interpolate_crossing(
    aums: Sequence[float],
    values: Sequence[float],
    threshold: float = 0.0,
) -> float | None:
    r"""Rend le capital où une métrique traverse un seuil, par interpolation en logarithme.

    **Le problème.** La grille de tailles est géométrique, donc une
    interpolation linéaire en dollars favoriserait le grand point de chaque
    paire.

    **L'intuition.** Interpoler en :math:`\log A`, où la grille est régulière,
    entre les deux premiers points qui encadrent le seuil.

    **La formule.**

    .. math::

        \log A^{\ast} = \log A_j + \left(\log A_{j+1} - \log A_j\right)
        \frac{m_j - \tau}{m_j - m_{j+1}}

    **Les variables.** :math:`A_j` deux tailles consécutives, :math:`m_j` la
    métrique à chacune, :math:`\tau` le seuil.

    **Les hypothèses.** La métrique décroît avec la taille, et elle est à peu
    près affine en logarithme entre deux points de la grille.

    **La provenance.** La même interpolation que
    :func:`quantlab.validation.robustness.cost_multiplier_analysis`,
    transposée en logarithme.

    **Les limites.** Une grille de neuf points par décade et demie laisse une
    incertitude d'un facteur trois sur le point rendu. La forme fermée de
    :func:`breakeven_aum` n'a pas cette limite quand elle s'applique.

    **Les alternatives.** Une bissection sur le moteur, plus coûteuse.

    **Pourquoi cette méthode ici.** Elle sert aux seuils que la forme fermée
    ne couvre pas, comme la moitié du ratio de Sharpe.

    **Comment vérifier.** Entre un million à :math:`+1` et cent millions à
    :math:`-1`, le seuil zéro est franchi à dix millions.

    Args:
        aums: les tailles de la grille, strictement croissantes et positives.
        values: la métrique à chaque taille.
        threshold: le seuil à franchir vers le bas.

    Returns:
        Le capital interpolé, ou ``None`` si le seuil n'est jamais franchi.

    Raises:
        ConfigError: les deux suites diffèrent en longueur, ou la grille n'est
            pas strictement croissante et positive.
    """
    a = [float(x) for x in aums]
    m = [float(x) for x in values]
    if len(a) != len(m):
        raise ConfigError(f"{len(a)} tailles pour {len(m)} valeurs.")
    if any(x <= 0.0 for x in a) or any(a[i] >= a[i + 1] for i in range(len(a) - 1)):
        raise ConfigError("la grille de tailles doit être strictement croissante et positive.")
    if not m or m[0] <= threshold:
        return a[0] if m and m[0] <= threshold else None
    for j in range(len(a) - 1):
        if m[j] > threshold >= m[j + 1]:
            if m[j] == m[j + 1]:
                return a[j + 1]
            share = (m[j] - threshold) / (m[j] - m[j + 1])
            return float(math.exp(math.log(a[j]) + (math.log(a[j + 1]) - math.log(a[j])) * share))
    return None


@dataclass(frozen=True)
class CapacityCurve:
    """La courbe du rendement net contre la taille, et ce qu'elle établit.

    Attributes:
        table: une ligne par taille de capital, avec le ratio de Sharpe net,
            le rendement net annualisé, les coûts annualisés en points de base
            par composante, la participation maximale et le statut.
        sharpe_reference: le ratio de Sharpe à taille nulle, demi-écart payé
            et impact nul.
        return_reference_annual: le rendement arithmétique annualisé à taille
            nulle.
        gross_mean: le rendement brut moyen par période.
        spread_mean: le coût de demi-écart moyen par période.
        impact_load_mean: la charge d'impact moyenne au capital unité.
        breakeven_aum: la capacité en forme fermée, ou ``None`` si aucune
            transaction ne porte d'impact.
        breakeven_check: le rendement net moyen rendu par le moteur au capital
            de forme fermée, qui doit valoir zéro ; ``None`` si non calculable.
        breakeven_clipped: vrai si le moteur a écrêté au moins une
            participation au capital de forme fermée. Le net que le moteur y
            rend est alors OPTIMISTE, puisque l'écrêtage minore le coût, et le
            contrôle ``breakeven_check`` ressort positif au lieu de nul.
        binding_assets: les actifs qui portent le plus souvent la plus grosse
            participation d'un rééquilibrage, avec leur pire valeur au capital
            unité ; ce sont eux qui fixent ``participation_cap_aum``.
        participation_cap_aum: le capital à partir duquel la plus grosse
            transaction de l'historique dépasse le plafond de participation.
            Au-delà, le modèle d'impact ne se prétend plus crédible.
        capacity_aum: la capacité retenue, le plus petit des deux capitaux
            précédents ; ``None`` si aucun des deux ne borne.
        half_sharpe_aum: le capital où le ratio de Sharpe net tombe à la
            moitié de sa valeur de référence, interpolé sur la grille ;
            ``None`` si la référence n'est pas strictement positive.
        frequency: la fréquence des périodes.
        coefficient: le coefficient d'impact employé.
        execution_days: les jours d'exécution employés.
        participation_cap: le plafond de participation employé.
        n_periods: le nombre de périodes évaluées.
        notes: les remarques du calcul, dont les écrêtages.
    """

    table: pd.DataFrame
    sharpe_reference: float
    return_reference_annual: float
    gross_mean: float
    spread_mean: float
    impact_load_mean: float
    breakeven_aum: float | None
    breakeven_check: float | None
    breakeven_clipped: bool
    binding_assets: tuple[tuple[str, float], ...]
    participation_cap_aum: float | None
    capacity_aum: float | None
    half_sharpe_aum: float | None
    frequency: Frequency
    coefficient: float
    execution_days: int
    participation_cap: float
    n_periods: int
    notes: tuple[str, ...] = field(default_factory=tuple)

    def summary(self) -> dict[str, Any]:
        """Rend les grandeurs scalaires, prêtes pour un fichier de métriques."""
        return {
            "sharpe_reference": self.sharpe_reference,
            "return_reference_annual": self.return_reference_annual,
            "gross_mean_per_period": self.gross_mean,
            "spread_mean_per_period": self.spread_mean,
            "impact_load_mean_unit_aum": self.impact_load_mean,
            "breakeven_aum": self.breakeven_aum,
            "breakeven_check_mean_net": self.breakeven_check,
            "breakeven_clipped": self.breakeven_clipped,
            "binding_assets": [list(pair) for pair in self.binding_assets],
            "participation_cap_aum": self.participation_cap_aum,
            "capacity_aum": self.capacity_aum,
            "half_sharpe_aum": self.half_sharpe_aum,
            "frequency": str(self.frequency),
            "coefficient": self.coefficient,
            "execution_days": self.execution_days,
            "participation_cap": self.participation_cap,
            "n_periods": self.n_periods,
            "status": "modélisé",
            "notes": list(self.notes),
        }


def _safe_sharpe(series: pd.Series, frequency: Frequency) -> float:
    """Rend le ratio de Sharpe, ou NaN quand la série n'a aucune dispersion.

    Des poids nuls donnent un rendement identiquement nul, dont le ratio n'est
    pas défini. La courbe le dit par un NaN plutôt que par une erreur.
    """
    try:
        return float(sharpe_ratio(series, frequency=frequency))
    except QuantLabError:
        return float("nan")


def _run_at(
    aum: float,
    *,
    weights: WeightFrame,
    returns: ReturnFrame,
    adv_dollars: pd.DataFrame,
    volatility: pd.DataFrame,
    frequency: Frequency,
    coefficient: float,
    spread_bps: float,
    execution_days: int,
    participation_cap: float,
    execution_lag: int,
    rebalance: Frequency | pd.Index | None,
    on_missing_liquidity: MissingLiquidity = DEFAULT_MISSING_LIQUIDITY,
) -> tuple[BacktestResult, ImpactAtScale]:
    """Rejoue les poids à un capital donné et rend le résultat avec son modèle."""
    model = ImpactAtScale(
        aum=aum,
        adv_dollars=adv_dollars,
        volatility=volatility,
        coefficient=coefficient,
        spread_bps=spread_bps,
        execution_days=execution_days,
        participation_cap=participation_cap,
        on_missing_liquidity=on_missing_liquidity,
    )
    result = run_backtest(
        weights=weights,
        returns=returns,
        cost_model=model,
        execution_lag=execution_lag,
        frequency=frequency,
        rebalance=rebalance,
    )
    return result, model


def _component(result: BacktestResult, name: str) -> pd.Series:
    """Rend une composante de coût du résultat, ou des zéros si elle est absente."""
    if name in result.cost_breakdown.columns:
        return result.cost_breakdown[name].astype(float)
    return pd.Series(0.0, index=result.net_returns.index)


def capacity_curve(
    weights: WeightFrame,
    returns: ReturnFrame,
    *,
    adv_dollars: pd.DataFrame,
    volatility: pd.DataFrame,
    frequency: Frequency,
    aum_grid: Sequence[float] = DEFAULT_AUM_GRID,
    coefficient: float = 1.0,
    spread_bps: float = 0.0,
    execution_days: int = DEFAULT_EXECUTION_DAYS,
    participation_cap: float = DEFAULT_PARTICIPATION_CAP,
    execution_lag: int = 1,
    rebalance: Frequency | pd.Index | None = None,
    evaluate_from: object | None = None,
    on_missing_liquidity: MissingLiquidity = DEFAULT_MISSING_LIQUIDITY,
) -> CapacityCurve:
    r"""Rejoue les poids à chaque taille de la grille et rend la courbe de capacité.

    **Le problème.** Une stratégie se publie avec un ratio de Sharpe et sans
    taille. La question d'un allocateur est l'inverse : à combien de dollars
    ce ratio tient-il encore ?

    **L'intuition.** Le même historique de poids est rejoué avec un coût
    d'impact qui dépend de la taille. Le rendement brut ne change pas et le
    coût croît comme la racine de la taille. La courbe du net contre la taille
    dit donc où la stratégie meurt.

    **La formule.** Deux passages au capital unité isolent :math:`g`,
    :math:`s` et :math:`K` ; la forme fermée de :func:`breakeven_aum` rend
    :math:`A^{\ast}` ; un passage par taille de la grille rend le ratio de
    Sharpe net ; un dernier passage à :math:`A^{\ast}` vérifie que le net
    moyen y vaut zéro.

    **Les variables.** Voir :func:`breakeven_aum` et :class:`ImpactAtScale`.

    **Les hypothèses.** Celles d':class:`ImpactAtScale`, plus un capital
    constant sur tout l'historique.

    **La provenance.** La courbe rendement net contre capital est la lecture
    usuelle de la capacité, sans article de référence ; statut précepte.

    **Les limites.** Le coefficient d'impact est déclaré, non mesuré, et la
    capacité lui est proportionnelle à la puissance moins deux : le diviser par
    deux la multiplie par quatre. Toute étude doit publier la sensibilité.

    **Les alternatives.** Une bissection sur le moteur au lieu de la forme
    fermée. Un capital qui croît dans le temps.

    **Pourquoi cette méthode ici.** La forme fermée et la grille se
    contrôlent l'une l'autre, et la vérification au capital d'annulation est
    publiée dans l'objet rendu.

    **Comment vérifier.** ``breakeven_check`` vaut zéro à la précision
    machine quand ``breakeven_clipped`` est faux. Sinon, le moteur rend un
    net moyen POSITIF à :math:`A^{\ast}`, parce que l'écrêtage minore le
    coût, et la capacité retenue est le capital où le plafond est atteint,
    qui se déduit de la participation au capital unité par une simple règle
    de trois.

    Args:
        weights: les poids cibles, une ligne par date de décision.
        returns: les rendements de période, mêmes actifs.
        adv_dollars: le volume quotidien moyen en dollars par actif.
        volatility: la volatilité quotidienne par actif.
        frequency: la fréquence des rendements.
        aum_grid: les tailles de capital, en dollars, strictement croissantes.
        coefficient: le coefficient d'impact.
        spread_bps: le demi-écart, en points de base du montant négocié.
        execution_days: les séances sur lesquelles chaque rééquilibrage s'étale.
        participation_cap: le plafond de participation quotidienne.
        execution_lag: le décalage d'exécution du moteur.
        rebalance: les dates de rééquilibrage, ou ``None`` pour toutes.
        evaluate_from: la première date incluse dans les statistiques, pour
            écarter une période de mise en route.
        on_missing_liquidity: voir :class:`ImpactAtScale` ; ``last_known``
            prête son dernier volume connu à un titre sorti de la cote.

    Returns:
        La courbe, ses grandeurs de forme fermée et ses contrôles.

    Raises:
        ConfigError: la grille est vide, non croissante ou non positive.
        InsufficientDataError: aucune période ne reste après ``evaluate_from``.
    """
    grid = [float(a) for a in aum_grid]
    if not grid or any(a <= 0.0 for a in grid) or any(grid[i] >= grid[i + 1] for i in range(len(grid) - 1)):
        raise ConfigError("aum_grid doit être non vide, strictement croissante et positive.")
    common: dict[str, Any] = {
        "weights": weights,
        "returns": returns,
        "adv_dollars": adv_dollars,
        "volatility": volatility,
        "frequency": frequency,
        "coefficient": coefficient,
        "execution_days": int(execution_days),
        "participation_cap": float(participation_cap),
        "execution_lag": int(execution_lag),
        "rebalance": rebalance,
        "on_missing_liquidity": on_missing_liquidity,
    }

    def _window(series: pd.Series) -> pd.Series:
        """Restreint une série à la fenêtre d'évaluation."""
        return series if evaluate_from is None else series.loc[pd.Timestamp(evaluate_from) :]

    unit, unit_model = _run_at(UNIT_AUM, spread_bps=float(spread_bps), **common)
    gross = _window(unit.gross_returns)
    if gross.empty:
        raise InsufficientDataError("aucune période ne reste après evaluate_from.")
    spread_cost = _window(_component(unit, SPREAD_COMPONENT))
    impact_load = _window(_component(unit, IMPACT_COMPONENT))
    notes: list[str] = []
    binding = unit_model.binding_assets()
    if unit_model.last_known_share() > 0.0:
        notes.append(
            f"dernier volume connu prêté sur {unit_model.last_known_share():.2%} des rééquilibrages, "
            "sorties de cote à cotations fantômes"
        )
    if unit_model.clipped_share() > 0.0:
        notes.append(
            "participation écrêtée au capital unité : le volume de certains actifs est nul ou infime"
        )

    periods_per_year = frequency.periods_per_year
    unit_participation = unit_model.max_participation()
    cap_aum = float(participation_cap) / unit_participation if unit_participation > 0.0 else None
    reference = gross - spread_cost
    sharpe_reference = _safe_sharpe(reference, frequency)
    g, s, k = float(gross.mean()), float(spread_cost.mean()), float(impact_load.mean())
    a_star = breakeven_aum(g, s, k)

    rows: list[dict[str, Any]] = []
    for aum in grid:
        result, model = _run_at(aum, spread_bps=float(spread_bps), **common)
        net = _window(result.net_returns)
        impact = _window(_component(result, IMPACT_COMPONENT))
        spread = _window(_component(result, SPREAD_COMPONENT))
        rows.append(
            {
                "aum": aum,
                "sharpe_net": _safe_sharpe(net, frequency),
                "return_net_annual": float(net.mean() * periods_per_year),
                "impact_bps_annual": float(impact.mean() * periods_per_year * 10_000.0),
                "spread_bps_annual": float(spread.mean() * periods_per_year * 10_000.0),
                "max_participation": model.max_participation(),
                "clipped_share": model.clipped_share(),
                "status": "minorant" if model.clipped_share() > 0.0 else "exact",
            }
        )
    table = pd.DataFrame(rows).set_index("aum")

    check: float | None = None
    clipped_at_star = False
    if a_star is not None and a_star > 0.0:
        verify, verify_model = _run_at(a_star, spread_bps=float(spread_bps), **common)
        check = float(_window(verify.net_returns).mean())
        clipped_at_star = verify_model.clipped_share() > 0.0
        if clipped_at_star:
            notes.append(
                "la participation dépasse le plafond avant le capital d'annulation : le moteur y écrête le "
                "coût, le net rendu y est optimiste, et la capacité retenue est le capital où le plafond "
                "est atteint"
            )
        elif abs(check) > BREAKEVEN_CHECK_TOLERANCE:
            raise DataQualityError(
                f"la forme fermée et le moteur se contredisent : net moyen {check:.3e} au capital "
                f"{a_star:.4g} alors qu'aucune participation n'est écrêtée."
            )
    elif a_star is None:
        notes.append("aucune transaction ne porte d'impact : la capacité n'est pas bornée par ce modèle")
    else:
        notes.append("l'alpha net de demi-écart est déjà négatif : la capacité vaut zéro")

    bounds = [b for b in (a_star, cap_aum) if b is not None]
    capacity = min(bounds) if bounds else None
    half = (
        interpolate_crossing(
            list(table.index), list(table["sharpe_net"]), threshold=HALF_SHARPE_SHARE * sharpe_reference
        )
        if math.isfinite(sharpe_reference) and sharpe_reference > 0.0
        else None
    )
    _LOG.info(
        "courbe de capacité calculée",
        extra={
            "n_aum": len(grid),
            "breakeven_aum": a_star,
            "capacity_aum": capacity,
            "clipped": clipped_at_star,
        },
    )
    return CapacityCurve(
        table=table,
        sharpe_reference=sharpe_reference,
        return_reference_annual=float(reference.mean() * periods_per_year),
        gross_mean=g,
        spread_mean=s,
        impact_load_mean=k,
        breakeven_aum=a_star,
        breakeven_check=check,
        breakeven_clipped=clipped_at_star,
        binding_assets=tuple(binding),
        participation_cap_aum=cap_aum,
        capacity_aum=capacity,
        half_sharpe_aum=half,
        frequency=frequency,
        coefficient=float(coefficient),
        execution_days=int(execution_days),
        participation_cap=float(participation_cap),
        n_periods=len(gross),
        notes=tuple(notes),
    )

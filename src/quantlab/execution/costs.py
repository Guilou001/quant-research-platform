r"""Le modèle de coût, et la décomposition qui empêche de tricher avec.

**Le problème.** Un rendement net est un rendement brut moins un nombre, et ce
nombre est presque toujours sous-estimé. La littérature publie des Sharpe bruts,
les praticiens paient des Sharpe nets, et l'écart entre les deux tue la majorité
des signaux à haute rotation. Un backtest sans modèle de coût explicite ne
mesure pas une stratégie : il mesure une hypothèse implicite de gratuité.

**Le remède.** Le coût se décompose en six termes, et chacun s'active
séparément :

.. math::

    C = Commission + Spread + Slippage + Impact + Borrow + Financing

Une étude qui publie un rendement net dit lesquels des six elle a activés, avec
quels paramètres. :class:`CostBreakdown` porte le détail terme par terme, si
bien qu'un lecteur peut refaire la soustraction lui-même.

**La convention d'unité.**
Toute grandeur dont le nom finit par ``_bps`` est en points de base de la valeur
liquidative, soit un dix-millième du capital.

La rotation, elle, est une fraction du capital, et ce module retient la SOMME
ENTIÈRE :

.. math::

    \tau_t = \sum_i \left| w_{i,t} - b_{i,t} \right|

Cette somme compte les deux côtés d'un rééquilibrage. La raison est que le
courtier facture la vente et l'achat, pas leur demi-somme. La fonction
:func:`quantlab.analytics.turnover.turnover` rend par défaut la demi-somme ; ce
module l'appelle donc toujours avec ``convention="full_sum"``. L'attribut
:attr:`CostBreakdown.traded_fraction` porte cette convention-là.

**Le contrat temporel, qui n'est vérifiable que chez l'appelant.** Les modèles
lisent leurs entrées dans un tableau ``context`` indexé par actif, sans aucune
date. Ce module ne peut donc pas prouver qu'une volatilité, un volume ou un
rendement de dérive ont été estimés avant le rééquilibrage qu'ils chiffrent.
Trois colonnes portent ce risque, et les constantes qui les nomment disent
laquelle vaut quoi. Une étude qui y passe une grandeur réalisée sur la période
négociée introduit une fuite temporelle que le coût rendu ne signalera pas.

**Ce que ce module ne fait pas.** Il ne simule aucun carnet d'ordres, aucune
file d'attente, aucun croisement. Le terme d'impact est stylisé, calibré nulle
part, et son statut est MODÉLISÉ au sens de la grille du dépôt. Le seul chiffre
de ce module dont le statut soit MESURÉ est celui que rend
:func:`breakeven_cost_bps`, parce qu'il ne dépend que des rendements et des
rotations réellement observés dans l'étude.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from quantlab.analytics.turnover import drifted_weights, turnover
from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.logging import get_logger
from quantlab.core.types import Frequency, ReturnSeries, Weights

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from quantlab.core.config import CostConfig

__all__ = [
    "ADV_FRACTION_COLUMN",
    "BPS_PER_UNIT",
    "DEFAULT_PARTICIPATION_CAP",
    "MAX_DROPPED_FRACTION",
    "MIN_ADV_FRACTION",
    "MIN_BREAKEVEN_OBSERVATIONS",
    "PERIOD_RETURN_COLUMN",
    "SQRT_IMPACT_NAME",
    "VOLATILITY_COLUMN",
    "BaseCostModel",
    "BorrowCostModel",
    "CompositeCostModel",
    "CostBreakdown",
    "FinancingCostModel",
    "LinearCostModel",
    "SqrtImpactModel",
    "breakeven_cost_bps",
    "from_config",
    "signed_trades",
]

_LOG = get_logger(__name__)

#: Le nombre de points de base dans une unité de capital. Il sert à convertir un
#: taux en points de base vers une fraction décimale, et jamais autrement.
BPS_PER_UNIT: float = 10_000.0

#: Nom de la colonne de ``context`` portant le rendement simple de la période
#: ÉCOULÉE, celle qui se termine au rééquilibrage, actif par actif. Sa présence
#: déclenche le calcul des poids dérivés, donc la mesure de la rotation contre
#: ce qui se négocie réellement. Y passer le rendement de la période À VENIR
#: ferait entrer de l'information future dans la rotation facturée, et ce module
#: ne peut pas le détecter : la colonne arrive sans date.
PERIOD_RETURN_COLUMN: str = "period_return"

#: Nom de la colonne de ``context`` portant la volatilité PRÉVUE de l'actif pour
#: la période à venir, en fraction décimale. Exigée par
#: :class:`SqrtImpactModel`. Elle s'estime sur l'information disponible AVANT le
#: rééquilibrage. Une volatilité réalisée sur la période qu'on est en train de
#: négocier est de l'information future, et elle flatte toujours dans le même
#: sens : les jours agités deviennent chers après coup, jamais avant.
VOLATILITY_COLUMN: str = "volatility"

#: Nom de la colonne de ``context`` portant le volume quotidien moyen de l'actif
#: rapporté à la valeur liquidative du portefeuille. Une valeur de 5,0 signifie
#: que le titre échange chaque jour cinq fois la taille du portefeuille entier.
#: Comme la volatilité, ce volume se mesure sur une fenêtre qui se ferme AVANT
#: le rééquilibrage, jamais sur la séance qu'on négocie.
ADV_FRACTION_COLUMN: str = "adv_fraction"

#: Part maximale du volume quotidien moyen retenue par défaut. Au-delà, le
#: modèle en racine carrée n'a plus de calibration publiée derrière lui.
DEFAULT_PARTICIPATION_CAP: float = 0.10

#: Volume quotidien moyen sous lequel un actif est jugé non négociable. Diviser
#: par un nombre plus petit rendrait une participation arbitrairement grande.
MIN_ADV_FRACTION: float = 1e-12

#: Nombre minimal de périodes exigé par :func:`breakeven_cost_bps`. Douze
#: observations sont déjà peu, mais en deçà le rapport de deux moyennes n'a plus
#: aucune stabilité.
MIN_BREAKEVEN_OBSERVATIONS: int = 12

#: Part maximale des périodes qu'un alignement a le droit de perdre dans
#: :func:`breakeven_cost_bps`. Au-delà, les deux séries ne décrivent pas la même
#: étude, et le rapport de leurs moyennes porterait sur un sous-échantillon que
#: personne n'a choisi. Un dixième laisse passer un décalage de bord de fenêtre.
MAX_DROPPED_FRACTION: float = 0.10

#: Le seul nom de modèle d'impact reconnu par :func:`from_config`.
SQRT_IMPACT_NAME: str = "sqrt"


# ---------------------------------------------------------------------------
# La décomposition
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CostBreakdown:
    """Le coût d'un rééquilibrage, terme par terme, en points de base.

    Chaque champ est une fraction de la valeur liquidative multipliée par dix
    mille. Le total n'est pas stocké : il est recalculé par la propriété
    :attr:`total_bps`, ce qui lui interdit de diverger de ses composantes.

    Attributes:
        commission_bps: la commission du courtier, sur les deux côtés négociés.
        spread_bps: le demi-écart acheteur-vendeur payé, sur les deux côtés.
        slippage_bps: le glissement fixe déclaré, au-delà du demi-écart.
        impact_bps: l'impact de marché modélisé, statut MODÉLISÉ.
        borrow_bps: le coût d'emprunt de titre, sur l'exposition vendeuse.
        financing_bps: le coût de financement du levier au-delà de un.
        traded_fraction: la rotation qui a produit ces coûts, en convention de
            somme entière, donc les deux côtés comptés.
    """

    commission_bps: float = 0.0
    spread_bps: float = 0.0
    slippage_bps: float = 0.0
    impact_bps: float = 0.0
    borrow_bps: float = 0.0
    financing_bps: float = 0.0
    traded_fraction: float = 0.0

    @property
    def total_bps(self) -> float:
        """La somme des six composantes, en points de base du capital."""
        return (
            self.commission_bps
            + self.spread_bps
            + self.slippage_bps
            + self.impact_bps
            + self.borrow_bps
            + self.financing_bps
        )

    @property
    def total_fraction(self) -> float:
        """Le total exprimé en fraction du capital, prêt à être soustrait."""
        return self.total_bps / BPS_PER_UNIT

    def as_dict(self) -> dict[str, float]:
        """Rend la décomposition sous forme de dictionnaire, total compris.

        Returns:
            Un dictionnaire dont les clés sont les noms des champs, augmenté de
            ``total_bps``. Destiné aux tableaux de rapport.
        """
        return {
            "commission_bps": self.commission_bps,
            "spread_bps": self.spread_bps,
            "slippage_bps": self.slippage_bps,
            "impact_bps": self.impact_bps,
            "borrow_bps": self.borrow_bps,
            "financing_bps": self.financing_bps,
            "traded_fraction": self.traded_fraction,
            "total_bps": self.total_bps,
        }

    def __add__(self, other: CostBreakdown) -> CostBreakdown:
        """Additionne deux décompositions issues du même rééquilibrage.

        Args:
            other: la seconde décomposition, portant la même rotation.

        Returns:
            La décomposition dont chaque composante est la somme des deux.

        Raises:
            TypeError: l'opérande n'est pas une :class:`CostBreakdown`.
            ConfigError: les deux décompositions ne portent pas la même
                rotation, donc ne décrivent pas le même rééquilibrage.
        """
        if not isinstance(other, CostBreakdown):
            return NotImplemented
        if not np.isclose(self.traded_fraction, other.traded_fraction, rtol=0.0, atol=_TRADE_TOL):
            raise ConfigError(
                f"rotations incompatibles : {self.traded_fraction} contre {other.traded_fraction}. "
                "Deux décompositions ne s'additionnent que si elles décrivent le même rééquilibrage."
            )
        return CostBreakdown(
            commission_bps=self.commission_bps + other.commission_bps,
            spread_bps=self.spread_bps + other.spread_bps,
            slippage_bps=self.slippage_bps + other.slippage_bps,
            impact_bps=self.impact_bps + other.impact_bps,
            borrow_bps=self.borrow_bps + other.borrow_bps,
            financing_bps=self.financing_bps + other.financing_bps,
            traded_fraction=max(self.traded_fraction, other.traded_fraction),
        )


#: Tolérance absolue sur l'égalité de deux rotations dans :meth:`CostBreakdown.__add__`.
#: Elle absorbe l'accumulation d'erreurs de virgule flottante d'une somme de
#: valeurs absolues, sans laisser passer deux rééquilibrages différents.
_TRADE_TOL: float = 1e-12


# ---------------------------------------------------------------------------
# Les entrées communes
# ---------------------------------------------------------------------------


def _validated_weights(values: Weights, *, label: str) -> pd.Series:
    """Contrôle un vecteur de poids et le rend en flottants.

    Args:
        values: le vecteur à contrôler.
        label: le nom employé dans les messages d'erreur.

    Returns:
        Le même vecteur converti en ``float``.

    Raises:
        TypeError: l'objet n'est pas une ``pandas.Series``.
        DataQualityError: l'index porte des doublons, la série n'est pas
            numérique, ou une valeur est manquante.
    """
    if not isinstance(values, pd.Series):
        raise TypeError(f"{label} doit être une pandas.Series, reçu {type(values).__name__}")
    if values.index.has_duplicates:
        doublons = values.index[values.index.duplicated()].tolist()
        raise DataQualityError(f"{label} porte des étiquettes en double : {doublons}")
    try:
        numeric = values.astype(float)
    except (TypeError, ValueError) as exc:
        raise DataQualityError(f"{label} n'est pas numérique : {exc}") from exc
    if bool(numeric.isna().any()):
        manquants = numeric.index[numeric.isna()].tolist()
        raise DataQualityError(
            f"{label} contient des valeurs manquantes sur {manquants}. "
            "Un poids inconnu se déclare en amont, jamais en le remplaçant par zéro ici."
        )
    return numeric


def _reference_weights(previous: pd.Series, context: pd.DataFrame | None) -> pd.Series:
    """Rend les poids de référence contre lesquels la rotation se mesure.

    Si ``context`` porte la colonne :data:`PERIOD_RETURN_COLUMN`, la référence
    est le vecteur des poids dérivés, ceux vers lesquels le marché a déplacé le
    portefeuille depuis le dernier rééquilibrage. Sinon la référence reste le
    vecteur de départ, ce qui suppose une dérive nulle.

    Args:
        previous: les poids détenus avant le rééquilibrage.
        context: le tableau de contexte, indexé par actif, ou ``None``.

    Returns:
        Le vecteur de référence, indexé comme ``previous``.
    """
    if context is None or PERIOD_RETURN_COLUMN not in context.columns:
        return previous
    return drifted_weights(previous, context[PERIOD_RETURN_COLUMN])


def _signed_trades(
    previous: pd.Series,
    target: pd.Series,
    context: pd.DataFrame | None,
) -> pd.Series:
    """Rend la variation signée de chaque poids, en fraction du capital.

    Args:
        previous: les poids détenus avant le rééquilibrage.
        target: les poids visés.
        context: le tableau de contexte, ou ``None``.

    Returns:
        Une série indexée par l'union des deux univers, positive à l'achat et
        négative à la vente.
    """
    base = _reference_weights(previous, context)
    universe = base.index.union(target.index)
    return target.reindex(universe, fill_value=0.0) - base.reindex(universe, fill_value=0.0)


def signed_trades(
    previous: Weights,
    target: Weights,
    context: pd.DataFrame | None = None,
) -> pd.Series:
    """Rend la variation signée de chaque poids, la définition partagée des modèles.

    C'est la même transaction que celle que chaque modèle de coût facture. Elle
    est exposée pour que la capacité, qui a besoin de la participation par
    actif, ne réécrive pas la règle de dérive.

    Args:
        previous: les poids détenus avant le rééquilibrage.
        target: les poids visés.
        context: le tableau de contexte, ou ``None``.

    Returns:
        Une série indexée par l'union des deux univers, positive à l'achat et
        négative à la vente.
    """
    return _signed_trades(previous, target, context)


def _traded_fraction(
    previous: pd.Series,
    target: pd.Series,
    context: pd.DataFrame | None,
) -> float:
    """Rend la rotation en convention de somme entière, les deux côtés comptés.

    La formule n'est pas réécrite ici : le calcul est délégué à
    :func:`quantlab.analytics.turnover.turnover`, seul endroit du paquet où la
    rotation est définie.

    Args:
        previous: les poids détenus avant le rééquilibrage.
        target: les poids visés.
        context: le tableau de contexte, ou ``None``.

    Returns:
        La somme des variations de poids en valeur absolue.
    """
    base = _reference_weights(previous, context)
    return turnover(base, target, drifted=False, convention="full_sum")


def _short_exposure(weights: pd.Series) -> float:
    """Rend l'exposition vendeuse, somme des poids négatifs en valeur absolue."""
    return float(np.abs(np.minimum(weights.to_numpy(), 0.0)).sum())


def _gross_exposure(weights: pd.Series) -> float:
    """Rend l'exposition brute, somme des poids en valeur absolue."""
    return float(np.abs(weights.to_numpy()).sum())


def _positive_rate(value: float, *, name: str) -> float:
    """Refuse un taux négatif ou non fini, et le rend en flottant.

    Args:
        value: le taux à contrôler.
        name: le nom du paramètre, employé dans le message d'erreur.

    Returns:
        Le taux converti en ``float``.

    Raises:
        ConfigError: le taux est négatif, ``NaN`` ou infini.
    """
    rate = float(value)
    if not np.isfinite(rate) or rate < 0.0:
        raise ConfigError(f"{name} doit être fini et positif ou nul, reçu {value!r}.")
    return rate


# ---------------------------------------------------------------------------
# La base commune des modèles
# ---------------------------------------------------------------------------


class BaseCostModel(abc.ABC):
    """La base des modèles de coût, qui déduit ``cost`` de ``breakdown``.

    Un modèle concret n'implémente que :meth:`breakdown`. La méthode
    :meth:`cost`, exigée par le protocole
    :class:`quantlab.core.protocols.CostModel`, en découle mécaniquement, ce qui
    interdit qu'un total et son détail se contredisent.
    """

    @abc.abstractmethod
    def breakdown(
        self,
        *,
        previous: Weights,
        target: Weights,
        context: pd.DataFrame | None = None,
    ) -> CostBreakdown:
        """Rend le coût du passage de ``previous`` à ``target``, terme par terme.

        Args:
            previous: les poids détenus avant le rééquilibrage.
            target: les poids visés après le rééquilibrage.
            context: un tableau indexé par actif portant les colonnes dont le
                modèle a besoin. Voir les constantes de nom de colonne du module.

        Returns:
            La décomposition du coût, en points de base du capital.
        """

    def cost(
        self,
        *,
        previous: Weights,
        target: Weights,
        context: pd.DataFrame | None = None,
    ) -> float:
        """Rend le coût total en fraction du capital, prêt à être soustrait.

        Args:
            previous: les poids détenus avant le rééquilibrage.
            target: les poids visés après le rééquilibrage.
            context: le tableau de contexte du modèle.

        Returns:
            Un nombre positif ou nul, en fraction décimale de la valeur
            liquidative. Le rendement net d'une période vaut le rendement brut
            moins ce nombre.
        """
        return self.breakdown(previous=previous, target=target, context=context).total_fraction


# ---------------------------------------------------------------------------
# Le coût proportionnel
# ---------------------------------------------------------------------------


class LinearCostModel(BaseCostModel):
    r"""Le coût proportionnel au montant négocié, en trois postes déclarés.

    **Le problème.** Le poste le plus grand du coût de transaction d'un fonds de
    taille moyenne n'est ni l'impact ni le financement : c'est ce qu'on paie
    mécaniquement à chaque passage d'ordre, commission comprise. Il se chiffre
    exactement dès que la rotation est connue.

    **L'intuition.** Chaque dollar négocié coûte un nombre fixe de points de
    base. Le coût de la période est donc le produit de ce taux par le montant
    négocié, lui-même égal à la rotation multipliée par le capital.

    **La formule.**

    .. math::

        C_{bps} = (c + s + g) \times \sum_{i} \left| w_{i,t} - b_{i,t} \right|

    **La convention du demi-écart, sans ambiguïté.** Le paramètre ``spread_bps``
    désigne le DEMI-écart acheteur-vendeur, celui qu'on paie sur un aller
    simple, et non l'écart entier. Exemple chiffré. Un titre cote 99,95 à
    l'achat et 100,05 à la vente, milieu 100,00. L'écart entier vaut 0,10, soit
    10 points de base du milieu ; le demi-écart vaut 0,05, soit 5 points de
    base, et c'est 5 qu'il faut passer ici. Acheter puis revendre la totalité du
    portefeuille fait une rotation de 2,0 en somme entière, donc 2,0 fois 5, soit
    10 points de base : l'écart entier, payé une fois sur l'aller-retour. La
    convention est cohérente.

    Args:
        commission_bps: la commission du courtier, en points de base du montant
            négocié, par côté.
        spread_bps: le DEMI-écart acheteur-vendeur payé par côté, en points de
            base du prix milieu.
        slippage_bps: le glissement supplémentaire déclaré, en points de base du
            montant négocié, par côté.

    Raises:
        ConfigError: un des trois taux est négatif ou non fini.

    Example:
        Une rotation de 40 % en somme entière, une commission de 1 point de
        base, un demi-écart de 2,5 points et un glissement de 0,5 point. Le taux
        vaut 4,0 points de base, et le coût 4,0 fois 0,40, soit 1,60 point de
        base du capital.

    Note:
        **Variables.** :math:`c` est la commission, :math:`s` le demi-écart,
        :math:`g` le glissement, tous en points de base. :math:`w_{i,t}` est le
        poids cible de l'actif *i* et :math:`b_{i,t}` son poids de référence.

        **Hypothèses.** Le coût unitaire ne dépend ni de la taille de l'ordre ni
        de l'urgence. L'écart acheteur-vendeur est constant dans le temps et
        identique sur tous les actifs. Ces deux hypothèses sont fausses, et la
        seconde l'est d'autant plus que l'univers mélange des capitalisations.

        **Provenance.** La forme proportionnelle est celle de Grinold et Kahn
        (2000), *Active Portfolio Management*, chapitre sur les coûts de
        transaction. Statut : rapportée, non revérifiée au texte dans la session
        qui a écrit ce module.

        **Limites.** Aucune dépendance à la taille, donc aucune notion de
        capacité. Un fonds de dix millions et un fonds de dix milliards paient
        ici le même taux, ce qui est faux. La dépendance à la taille vit dans
        :class:`SqrtImpactModel`.

        **Alternatives.** Un écart mesuré titre par titre et jour par jour,
        estimé sur des données de carnet, remplacerait ce taux unique. Le
        laboratoire ne dispose pas de ces données, et un taux unique DÉCLARÉ vaut
        mieux qu'un taux variable inventé.

        **Pourquoi cette méthode ici.** Elle rend le coût linéaire en rotation,
        donc inversible : le seuil de rentabilité de
        :func:`breakeven_cost_bps` a une solution en forme fermée.

        **Comment vérifier.** Trois contrôles. Une rotation nulle rend un coût
        nul. Doubler la rotation double le coût, exactement. Le coût d'un
        aller-retour complet vaut deux fois le taux unitaire.
    """

    def __init__(
        self,
        commission_bps: float = 0.0,
        spread_bps: float = 0.0,
        slippage_bps: float = 0.0,
    ) -> None:
        self.commission_bps = _positive_rate(commission_bps, name="commission_bps")
        self.spread_bps = _positive_rate(spread_bps, name="spread_bps")
        self.slippage_bps = _positive_rate(slippage_bps, name="slippage_bps")

    @property
    def rate_bps(self) -> float:
        """La somme des trois taux, en points de base du montant négocié."""
        return self.commission_bps + self.spread_bps + self.slippage_bps

    def breakdown(
        self,
        *,
        previous: Weights,
        target: Weights,
        context: pd.DataFrame | None = None,
    ) -> CostBreakdown:
        """Rend les trois postes proportionnels du rééquilibrage.

        Args:
            previous: les poids détenus avant le rééquilibrage.
            target: les poids visés.
            context: facultatif. S'il porte :data:`PERIOD_RETURN_COLUMN`, la
                rotation se mesure contre les poids dérivés.

        Returns:
            La décomposition, dont seuls les trois postes proportionnels sont
            non nuls.
        """
        base = _validated_weights(previous, label="previous")
        goal = _validated_weights(target, label="target")
        traded = _traded_fraction(base, goal, context)
        return CostBreakdown(
            commission_bps=self.commission_bps * traded,
            spread_bps=self.spread_bps * traded,
            slippage_bps=self.slippage_bps * traded,
            traded_fraction=traded,
        )

    def __repr__(self) -> str:
        """Rend la représentation lisible du modèle et de ses trois taux."""
        return (
            f"LinearCostModel(commission_bps={self.commission_bps}, "
            f"spread_bps={self.spread_bps}, slippage_bps={self.slippage_bps})"
        )


# ---------------------------------------------------------------------------
# L'impact de marché
# ---------------------------------------------------------------------------


class SqrtImpactModel(BaseCostModel):
    r"""L'impact de marché en racine carrée de la participation, statut MODÉLISÉ.

    **Le problème.** Un ordre déplace le prix contre celui qui le passe, et ce
    déplacement croît avec la taille. Un modèle proportionnel ignore cette
    croissance, donc annonce qu'une stratégie garde son rendement à n'importe
    quelle taille, ce qui est faux et flatte toujours dans le même sens.

    **L'intuition.** Le coût de déplacement n'est pas linéaire en taille. Passer
    deux fois plus de volume ne coûte pas deux fois plus, parce que le carnet se
    reconstitue pendant l'exécution. La racine carrée est la forme empirique
    retenue par la littérature.

    **La formule.**

    .. math::

        I_i = \kappa \, \sigma_i \sqrt{\frac{Q_i}{ADV_i}}
        \qquad
        C_{bps} = 10^4 \sum_i \left| \delta_i \right| I_i

    **Provenance.** Almgren, Thum, Hauptmann et Li (2005), *Direct estimation of
    equity market impact*, Risk 18, estiment un exposant proche de 0,6 sur des
    ordres institutionnels américains. Gatheral (2010), *No-dynamic-arbitrage
    and market impact*, Quantitative Finance 10, montre que la racine carrée est
    la seule forme compatible avec l'absence d'arbitrage dynamique sous une
    décroissance exponentielle de l'impact. Statut des deux références :
    rapporté, non revérifié au texte dans la session qui a écrit ce module.

    Args:
        coefficient: le facteur :math:`\kappa`, sans unité. Il n'est calibré
            nulle part dans ce dépôt et vaut ce que l'étude déclare.
        participation_cap: la part maximale du volume quotidien moyen au-delà
            de laquelle la participation est écrêtée.

    Raises:
        ConfigError: le coefficient est négatif, ou le plafond de participation
            n'est pas strictement positif.

    Example:
        Un actif de volatilité 2 % sur la période est négocié à hauteur de 20 %
        du capital, pour un volume quotidien moyen valant cinq fois ce montant.
        La participation vaut 0,20 / 5, soit 0,04, dont la racine vaut 0,20.
        Avec un coefficient de 0,5, l'impact unitaire vaut 0,5 fois 0,02 fois
        0,20, soit 0,002. Le coût vaut alors 0,20 fois 0,002, donc 4 points de
        base.

    Note:
        **Variables.** :math:`\kappa` est le coefficient, :math:`\sigma_i` la
        volatilité de l'actif sur la période en fraction décimale, :math:`Q_i`
        le montant négocié sur l'actif, :math:`ADV_i` son volume quotidien
        moyen, :math:`\delta_i` la variation de poids signée.

        **Aucune microstructure derrière ce modèle.** Il n'y a ici ni carnet
        d'ordres, ni file d'attente, ni croisement, ni horaire d'exécution. La
        forme fonctionnelle est empruntée, le coefficient est déclaré par
        l'utilisateur, et rien dans ce dépôt ne le calibre. Tout chiffre sorti de
        cette classe porte le statut MODÉLISÉ, jamais MESURÉ.

        **Hypothèses.** L'ordre est exécuté sur une journée, la participation
        est uniforme, et l'impact est intégralement permanent au sens où rien
        n'en est récupéré. Les actifs sont indépendants : aucun impact croisé
        n'est modélisé, alors qu'il existe entre titres du même secteur.

        **Le plafond de participation, et pourquoi il est optimiste.** Au-delà
        de ``participation_cap``, la participation est écrêtée à cette valeur.
        Le coût rendu est alors un MINORANT du coût réel, puisqu'une
        participation plus grande coûterait plus cher. Un avertissement est
        journalisé à chaque écrêtage. Une étude qui en déclenche doit conclure
        que la taille visée dépasse la capacité, pas que le coût est celui-là.

        **Limites.** L'exposant est figé à un demi alors qu'Almgren et ses
        coauteurs estiment 0,6. La volatilité et le volume quotidien moyen sont
        pris comme donnés, sans erreur d'estimation. Rien ne dépend de l'urgence
        ni de la corrélation entre les ordres du même jour.

        **Alternatives.** Le modèle d'Almgren complet sépare impact temporaire
        et permanent et ajoute un terme de risque de retard. Le modèle
        propagateur de Bouchaud décrit la décroissance de l'impact dans le temps.
        Les deux exigent une calibration sur données d'exécution que le
        laboratoire n'a pas.

        **Pourquoi cette méthode ici.** Elle rend le coût CONVEXE en taille avec
        un seul paramètre déclaré. Cela suffit à répondre à la question d'une
        étude de capacité : à partir de quelle taille le rendement net s'annule.

        **Comment vérifier.** Trois contrôles. Une variation de poids nulle rend
        un coût nul, quelle que soit la volatilité. Multiplier par quatre le
        montant négocié d'un actif multiplie son impact unitaire par deux, donc
        son coût par huit. Doubler le volume quotidien moyen divise l'impact
        unitaire par racine de deux.
    """

    def __init__(
        self,
        coefficient: float = 1.0,
        participation_cap: float = DEFAULT_PARTICIPATION_CAP,
    ) -> None:
        self.coefficient = _positive_rate(coefficient, name="coefficient")
        cap = float(participation_cap)
        if not np.isfinite(cap) or cap <= 0.0:
            raise ConfigError(f"participation_cap doit être fini et strictement positif, reçu {cap!r}.")
        self.participation_cap = cap

    def _required_column(self, context: pd.DataFrame | None, name: str) -> pd.Series:
        """Rend une colonne exigée du contexte, ou lève ``ConfigError``.

        Args:
            context: le tableau de contexte, ou ``None``.
            name: le nom de la colonne recherchée.

        Returns:
            La colonne demandée, convertie en flottants.

        Raises:
            ConfigError: le contexte est absent ou ne porte pas la colonne.
        """
        if context is None or name not in context.columns:
            raise ConfigError(
                f"SqrtImpactModel exige la colonne {name!r} dans context. "
                f"Colonnes attendues : {VOLATILITY_COLUMN!r} et {ADV_FRACTION_COLUMN!r}."
            )
        return context[name].astype(float)

    def breakdown(
        self,
        *,
        previous: Weights,
        target: Weights,
        context: pd.DataFrame | None = None,
    ) -> CostBreakdown:
        """Rend l'impact modélisé du rééquilibrage, actif par actif puis sommé.

        Args:
            previous: les poids détenus avant le rééquilibrage.
            target: les poids visés.
            context: un tableau indexé par actif portant
                :data:`VOLATILITY_COLUMN` et :data:`ADV_FRACTION_COLUMN`, et
                facultativement :data:`PERIOD_RETURN_COLUMN`.

        Returns:
            La décomposition, dont seul ``impact_bps`` est non nul.

        Raises:
            ConfigError: une colonne exigée manque au contexte.
            DataQualityError: un actif négocié est absent du contexte, porte une
                volatilité manquante, ou un volume quotidien moyen non
                strictement positif.
        """
        base = _validated_weights(previous, label="previous")
        goal = _validated_weights(target, label="target")
        trades = _signed_trades(base, goal, context)
        traded = _traded_fraction(base, goal, context)

        moved = trades[trades.abs() > 0.0]
        if moved.empty:
            return CostBreakdown(traded_fraction=traded)

        volatility = self._required_column(context, VOLATILITY_COLUMN)
        adv_fraction = self._required_column(context, ADV_FRACTION_COLUMN)

        absents = moved.index.difference(volatility.index.intersection(adv_fraction.index))
        if len(absents) > 0:
            raise DataQualityError(
                f"actifs négociés absents du contexte d'impact : {absents.tolist()}. "
                "Un actif sans volatilité ni volume ne se chiffre pas à zéro en silence."
            )

        sigma = volatility.reindex(moved.index)
        adv = adv_fraction.reindex(moved.index)
        if bool(sigma.isna().any()) or bool(adv.isna().any()):
            raise DataQualityError(
                "volatilité ou volume quotidien moyen manquant sur un actif négocié. "
                "Ces deux entrées se déclarent, elles ne se supposent pas."
            )
        if bool((adv <= MIN_ADV_FRACTION).any()):
            illiquides = adv.index[adv <= MIN_ADV_FRACTION].tolist()
            raise DataQualityError(
                f"volume quotidien moyen nul ou négatif sur {illiquides}. "
                "Un actif qui n'échange pas ne se négocie pas non plus dans le modèle."
            )

        participation = moved.abs() / adv
        depassements = participation[participation > self.participation_cap]
        if not depassements.empty:
            _LOG.warning(
                "participation écrêtée au plafond, le coût rendu est un minorant",
                extra={
                    "participation_cap": self.participation_cap,
                    "actifs": depassements.index.tolist(),
                    "participation_max": float(depassements.max()),
                },
            )
            participation = participation.clip(upper=self.participation_cap)

        unit_impact = self.coefficient * sigma * np.sqrt(participation)
        impact = float((moved.abs() * unit_impact).sum())
        return CostBreakdown(impact_bps=BPS_PER_UNIT * impact, traded_fraction=traded)

    def __repr__(self) -> str:
        """Rend la représentation lisible du modèle et de ses deux paramètres."""
        return f"SqrtImpactModel(coefficient={self.coefficient}, participation_cap={self.participation_cap})"


# ---------------------------------------------------------------------------
# Le portage : emprunt de titre et financement
# ---------------------------------------------------------------------------


class BorrowCostModel(BaseCostModel):
    r"""Le coût d'emprunt de titre, payé sur la seule exposition vendeuse.

    **Le problème.** Vendre à découvert exige d'emprunter le titre, et
    l'emprunt se paie. Un backtest long-short qui l'oublie publie un rendement
    net qui n'existe pour personne. L'oubli est d'autant plus grand que la
    stratégie vend les titres difficiles à emprunter, ce que font la plupart des
    signaux de qualité et de valorisation.

    **L'intuition.** Le coût est un loyer. Il court avec le temps sur le montant
    vendu à découvert, indépendamment de toute transaction.

    **La formule.**

    .. math::

        C_{bps} = \frac{a}{M} \sum_i \max(-w_i, 0)

    Args:
        annual_bps: le taux d'emprunt annuel, en points de base du montant
            vendu à découvert.
        frequency: la fréquence de rééquilibrage, qui fixe la durée d'une
            période. Une période est facturée par appel.
        periods_per_year: nombre de périodes par an, s'il faut le forcer. Par
            défaut celui de la fréquence.

    Raises:
        ConfigError: le taux est négatif, ou le nombre de périodes par an n'est
            pas strictement positif.

    Example:
        Taux annuel de 300 points de base, fréquence quotidienne, exposition
        vendeuse de 50 % du capital.
        Le coût d'une séance vaut 300 / 252 fois 0,50, soit 25/42 point de base,
        environ 0,595.

    Note:
        **Variables.** :math:`a` est le taux annuel en points de base, :math:`M`
        le nombre de périodes par an, :math:`w_i` le poids CIBLE de l'actif *i*.

        **L'exposition retenue est celle d'après le rééquilibrage.** Le loyer
        court sur la position détenue pendant la période qui commence, donc sur
        ``target``. Une étude qui facture sur la position d'avant décale son
        coût d'une période.

        **L'hypothèse optimiste, écrite en clair.** La disponibilité à l'emprunt
        est SUPPOSÉE acquise, à ce taux, pour tous les titres et à toute date.
        C'est faux, et c'est faux dans un seul sens. Les titres les plus chers à
        emprunter sont précisément ceux que les signaux veulent vendre, et le
        rappel de titre force à racheter au pire moment. Toute étude de ce
        laboratoire doit donc rejouer son résultat à une, deux et cinq fois ce
        taux, et publier les trois. Un résultat qui ne survit pas au double est
        un résultat qui dépend d'une hypothèse de courtier.

        **Provenance.** D'Avolio (2002), *The market for borrowing stock*,
        Journal of Financial Economics 66, mesure la dispersion des taux
        d'emprunt sur le marché américain et documente sa concentration sur les
        petites capitalisations. Statut : rapporté, non revérifié au texte dans
        la session qui a écrit ce module.

        **Limites.** Un taux unique pour tout l'univers, constant dans le temps.
        Aucun rappel de titre, aucune indisponibilité, aucun échec de règlement.
        Le rabais sur le produit de la vente, qui joue en sens inverse, n'est pas
        modélisé non plus.

        **Alternatives.** Un taux par titre issu d'un fournisseur de prêt de
        titres, ou une exclusion pure et simple des titres réputés difficiles à
        emprunter. Le laboratoire n'a pas de données de prêt, et le taux unique
        déclaré reste vérifiable par le lecteur.

        **Pourquoi cette méthode ici.** Elle sépare proprement un coût de
        portage, qui dépend du temps, d'un coût de transaction, qui dépend de la
        rotation. Les deux se cumulent sans se recouvrir.

        **Comment vérifier.** Trois contrôles. Un portefeuille sans vente à
        découvert rend zéro. Douze périodes mensuelles cumulent exactement le
        taux annuel appliqué à une exposition vendeuse constante. Doubler le taux
        double le coût.
    """

    def __init__(
        self,
        annual_bps: float = 0.0,
        frequency: Frequency = Frequency.DAILY,
        *,
        periods_per_year: float | None = None,
    ) -> None:
        self.annual_bps = _positive_rate(annual_bps, name="annual_bps")
        self.frequency = frequency
        self.periods_per_year = _periods_per_year(frequency, periods_per_year)

    @property
    def period_bps(self) -> float:
        """Le taux d'emprunt d'une seule période, en points de base."""
        return self.annual_bps / self.periods_per_year

    def breakdown(
        self,
        *,
        previous: Weights,
        target: Weights,
        context: pd.DataFrame | None = None,
    ) -> CostBreakdown:
        """Rend le loyer d'emprunt d'une période sur l'exposition vendeuse cible.

        Args:
            previous: les poids détenus avant le rééquilibrage. Ils ne servent
                qu'à mesurer la rotation reportée dans la décomposition.
            target: les poids visés, qui portent l'exposition vendeuse facturée.
            context: facultatif, transmis à la mesure de rotation.

        Returns:
            La décomposition, dont seul ``borrow_bps`` est non nul.
        """
        base = _validated_weights(previous, label="previous")
        goal = _validated_weights(target, label="target")
        traded = _traded_fraction(base, goal, context)
        return CostBreakdown(
            borrow_bps=self.period_bps * _short_exposure(goal),
            traded_fraction=traded,
        )

    def __repr__(self) -> str:
        """Rend la représentation lisible du modèle et de son taux annuel."""
        return f"BorrowCostModel(annual_bps={self.annual_bps}, frequency={self.frequency.value!r})"


class FinancingCostModel(BaseCostModel):
    r"""Le coût de financement du levier, payé au-delà d'une exposition brute de un.

    **Le problème.** Une stratégie qui affiche un Sharpe médiocre se rattrape
    souvent en multipliant ses poids. L'opération est gratuite dans un tableur
    et payante chez un courtier : le capital emprunté porte intérêt. Un backtest
    à levier trois qui ne facture rien surestime son rendement de plusieurs
    points par an.

    **L'intuition.** Seule la part de l'exposition brute qui dépasse le capital
    propre est financée. Un portefeuille long-short à exposition brute de deux
    finance une unité de capital.

    **La formule.**

    .. math::

        C_{bps} = \frac{f}{M} \max\!\left(\sum_i |w_i| - 1, \; 0\right)

    Args:
        spread_over_rf_bps: l'écart annuel facturé AU-DESSUS du taux sans
            risque, en points de base.
        frequency: la fréquence de rééquilibrage, qui fixe la durée d'une
            période.
        periods_per_year: nombre de périodes par an, s'il faut le forcer.

    Raises:
        ConfigError: l'écart est négatif, ou le nombre de périodes par an n'est
            pas strictement positif.

    Example:
        Un écart annuel de 100 points de base, une fréquence quotidienne et une
        exposition brute de 1,20. La part financée vaut 0,20, et le coût d'une
        séance 100 / 252 fois 0,20, soit 5/63 point de base, environ 0,0794.

    Note:
        **Variables.** :math:`f` est l'écart annuel en points de base, :math:`M`
        le nombre de périodes par an, :math:`w_i` le poids cible de l'actif *i*.

        **Pourquoi seulement l'écart, et pas le taux entier.** Les rendements
        d'une étude sont comparés à un repère, et le taux sans risque figure
        déjà des deux côtés de cette comparaison. Facturer le taux entier ici le
        compterait deux fois. Ce que le courtier ajoute au taux sans risque, lui,
        n'est nulle part ailleurs, et c'est ce qui est facturé.

        **Hypothèses.** L'écart est le même à l'achat et à la vente, constant
        dans le temps, et le portefeuille se finance intégralement au jour le
        jour. Aucun appel de marge n'est simulé, alors qu'un appel de marge force
        à liquider, donc à payer aussi des coûts de transaction.

        **Limites, et un recouvrement à déclarer.** Le produit de la vente à
        découvert est ici sans rendement, ce qui est pessimiste, alors que
        l'hypothèse de disponibilité à l'emprunt de :class:`BorrowCostModel` est
        optimiste. Les deux écarts ne se compensent pas, et sur un livre
        neutralisé ils portent en partie sur le MÊME montant. Contre-exemple
        chiffré. Un livre à 1,00 d'achats et 1,00 de ventes a une exposition
        brute de 2,00, donc une part financée de 1,00 ici, et une exposition
        vendeuse de 1,00 chez :class:`BorrowCostModel`. La jambe vendeuse est
        alors facturée deux fois, une fois comme loyer de titre et une fois
        comme financement. Chez un courtier, le produit de la vente sert de
        collatéral et ne se finance pas. Une étude qui active les deux modèles
        sur un livre neutralisé surestime donc son coût de portage de l'écart de
        financement appliqué à la jambe vendeuse.

        **Alternatives.** Un modèle de marge réglementaire, qui calcule
        l'exigence par le portefeuille plutôt que par l'exposition brute, serait
        plus exact pour un livre couvert. Il exige les règles du courtier, qui ne
        sont pas publiques.

        **Pourquoi cette méthode ici.** Le levier est le paramètre le plus facile
        à pousser dans une étude et le plus dangereux à laisser gratuit. Une
        formule d'une ligne, appliquée à l'exposition brute, suffit à rendre son
        coût visible.

        **Comment vérifier.** Trois contrôles. Une exposition brute de un rend
        zéro, et toute exposition inférieure aussi. Doubler la part financée
        double le coût. Le coût annuel d'un levier constant de deux vaut
        exactement l'écart annuel déclaré.
    """

    def __init__(
        self,
        spread_over_rf_bps: float = 0.0,
        frequency: Frequency = Frequency.DAILY,
        *,
        periods_per_year: float | None = None,
    ) -> None:
        self.spread_over_rf_bps = _positive_rate(spread_over_rf_bps, name="spread_over_rf_bps")
        self.frequency = frequency
        self.periods_per_year = _periods_per_year(frequency, periods_per_year)

    @property
    def period_bps(self) -> float:
        """L'écart de financement d'une seule période, en points de base."""
        return self.spread_over_rf_bps / self.periods_per_year

    def breakdown(
        self,
        *,
        previous: Weights,
        target: Weights,
        context: pd.DataFrame | None = None,
    ) -> CostBreakdown:
        """Rend le coût de financement d'une période sur le levier cible.

        Args:
            previous: les poids détenus avant le rééquilibrage, employés pour la
                rotation reportée dans la décomposition.
            target: les poids visés, qui portent l'exposition brute facturée.
            context: facultatif, transmis à la mesure de rotation.

        Returns:
            La décomposition, dont seul ``financing_bps`` est non nul.
        """
        base = _validated_weights(previous, label="previous")
        goal = _validated_weights(target, label="target")
        traded = _traded_fraction(base, goal, context)
        financed = max(_gross_exposure(goal) - 1.0, 0.0)
        return CostBreakdown(
            financing_bps=self.period_bps * financed,
            traded_fraction=traded,
        )

    def __repr__(self) -> str:
        """Rend la représentation lisible du modèle et de son écart annuel."""
        return (
            f"FinancingCostModel(spread_over_rf_bps={self.spread_over_rf_bps}, "
            f"frequency={self.frequency.value!r})"
        )


def _periods_per_year(frequency: Frequency, override: float | None) -> float:
    """Rend le nombre de périodes par an, forcé ou déduit de la fréquence.

    Args:
        frequency: la fréquence déclarée par le modèle.
        override: la valeur forcée, ou ``None`` pour la convention.

    Returns:
        Le nombre de périodes par an.

    Raises:
        ConfigError: la valeur forcée n'est pas strictement positive et finie.

    Note:
        Le prorata sur une année complète est exact quelle que soit la
        convention retenue. Le loyer d'une séance vaut le taux annuel divisé par
        252, et 252 séances le rendent en entier. Le choix de 252 plutôt que 365
        déplace donc le coût d'une période, jamais celui d'une année.
    """
    if override is None:
        return float(frequency.periods_per_year)
    value = float(override)
    if not np.isfinite(value) or value <= 0.0:
        raise ConfigError(f"periods_per_year doit être fini et strictement positif, reçu {override!r}.")
    return value


# ---------------------------------------------------------------------------
# La composition
# ---------------------------------------------------------------------------


class CompositeCostModel(BaseCostModel):
    """La somme de plusieurs modèles, dont ``breakdown`` conserve le détail.

    **Le problème.** Un modèle de coût unique qui rendrait un seul nombre
    empêche de savoir quel poste domine. La question « le signal meurt-il de la
    commission ou de l'impact ? » n'a alors pas de réponse, et la correction ne
    peut pas être ciblée.

    **Le remède.** Chaque composante reste un objet séparé, et la composition
    additionne les décompositions terme par terme. Le total et le détail sortent
    du même appel.

    Args:
        models: les modèles à additionner, dans l'ordre voulu. Une liste vide
            est acceptée et rend un coût nul, ce qui est la façon explicite de
            dire qu'une étude est brute de frais.

    Raises:
        ConfigError: un élément de la liste n'expose pas de méthode
            ``breakdown``.

    Example:
        Un modèle linéaire à 4 points de base et un modèle d'impact à 7 points
        de base, sur le même rééquilibrage.
        Le total vaut 11 points de base, et la décomposition garde 4 et 7
        séparés.

    Note:
        L'addition passe par :meth:`CostBreakdown.__add__`, qui refuse deux
        décompositions portant des rotations différentes. Une composition ne
        peut donc pas mélanger deux rééquilibrages par accident.
    """

    def __init__(self, models: Sequence[BaseCostModel] | Iterable[BaseCostModel] = ()) -> None:
        collected = list(models)
        for model in collected:
            if not hasattr(model, "breakdown"):
                raise ConfigError(
                    f"{type(model).__name__} n'expose pas de méthode breakdown et ne peut pas "
                    "entrer dans un CompositeCostModel."
                )
        self.models: tuple[BaseCostModel, ...] = tuple(collected)

    def breakdown(
        self,
        *,
        previous: Weights,
        target: Weights,
        context: pd.DataFrame | None = None,
    ) -> CostBreakdown:
        """Rend la somme des décompositions de tous les modèles composés.

        Args:
            previous: les poids détenus avant le rééquilibrage.
            target: les poids visés.
            context: le tableau de contexte, transmis tel quel à chaque modèle.

        Returns:
            La décomposition agrégée. Sur une composition vide, elle porte la
            rotation mesurée et des composantes toutes nulles.
        """
        base = _validated_weights(previous, label="previous")
        goal = _validated_weights(target, label="target")
        total = CostBreakdown(traded_fraction=_traded_fraction(base, goal, context))
        for model in self.models:
            total = total + model.breakdown(previous=base, target=goal, context=context)
        return total

    def __len__(self) -> int:
        """Rend le nombre de modèles composés."""
        return len(self.models)

    def __repr__(self) -> str:
        """Rend la représentation lisible de la composition."""
        return f"CompositeCostModel({list(self.models)!r})"


def from_config(
    config: CostConfig,
    *,
    frequency: Frequency = Frequency.DAILY,
) -> CompositeCostModel:
    """Construit le modèle de coût décrit par une configuration d'étude.

    Les composantes dont le taux vaut zéro ne sont pas instanciées. Une étude
    qui déclare des coûts nuls obtient donc une composition vide, et son rapport
    dira qu'elle est brute de frais plutôt que de le laisser deviner.

    Args:
        config: la section de coûts de la configuration, validée par pydantic.
        frequency: la fréquence de rééquilibrage de l'étude, qui fixe le prorata
            des coûts de portage.

    Returns:
        La composition des modèles activés par la configuration.

    Raises:
        ConfigError: ``impact_model`` porte un nom inconnu. Le seul nom reconnu
            est celui de :data:`SQRT_IMPACT_NAME`.

    Example:
        Une configuration à 1 point de base de commission, 2,5 points de
        demi-écart, aucun impact et 300 points d'emprunt annuel rend une
        composition de deux modèles, un linéaire et un d'emprunt.
    """
    models: list[BaseCostModel] = []
    if config.commission_bps or config.spread_bps or config.slippage_bps:
        models.append(
            LinearCostModel(
                commission_bps=config.commission_bps,
                spread_bps=config.spread_bps,
                slippage_bps=config.slippage_bps,
            )
        )
    if config.impact_model is not None:
        if config.impact_model != SQRT_IMPACT_NAME:
            raise ConfigError(
                f"modèle d'impact inconnu : {config.impact_model!r}. Seul {SQRT_IMPACT_NAME!r} est reconnu."
            )
        models.append(SqrtImpactModel(coefficient=config.impact_coefficient))
    if config.borrow_bps_annual:
        models.append(BorrowCostModel(annual_bps=config.borrow_bps_annual, frequency=frequency))
    if config.financing_spread_bps_annual:
        models.append(
            FinancingCostModel(
                spread_over_rf_bps=config.financing_spread_bps_annual,
                frequency=frequency,
            )
        )
    _LOG.info(
        "modèle de coût construit depuis la configuration",
        extra={"composantes": [type(m).__name__ for m in models], "frequence": frequency.value},
    )
    return CompositeCostModel(models)


# ---------------------------------------------------------------------------
# Le seuil de rentabilité
# ---------------------------------------------------------------------------


def _reject_thin_overlap(
    *,
    kept: int,
    sizes: dict[str, int],
    max_dropped_fraction: float,
) -> None:
    """Refuse un alignement qui perd trop de périodes d'une des deux séries.

    Args:
        kept: le nombre de périodes communes après jointure.
        sizes: la longueur de chaque série d'entrée, par nom.
        max_dropped_fraction: la part maximale tolérée de périodes perdues.

    Raises:
        ConfigError: le seuil n'est pas dans l'intervalle de zéro à un.
        DataQualityError: une des deux séries perd plus que le seuil.
    """
    limit = float(max_dropped_fraction)
    if not np.isfinite(limit) or limit < 0.0 or limit > 1.0:
        raise ConfigError(f"max_dropped_fraction doit être entre 0 et 1, reçu {max_dropped_fraction!r}.")
    for nom, taille in sizes.items():
        if taille == 0:
            continue
        perdu = 1.0 - kept / taille
        if perdu > limit:
            raise DataQualityError(
                f"l'alignement retient {kept} périodes sur les {taille} de {nom}, "
                f"soit {perdu:.1%} de perte pour un maximum de {limit:.1%}. "
                "Deux séries qui se recouvrent aussi peu ne décrivent pas la même étude."
            )


def breakeven_cost_bps(
    gross_returns: ReturnSeries,
    turnover_values: pd.Series,
    frequency: Frequency = Frequency.DAILY,
    *,
    min_observations: int = MIN_BREAKEVEN_OBSERVATIONS,
    max_dropped_fraction: float = MAX_DROPPED_FRACTION,
) -> float:
    r"""Rend le coût unitaire qui annule exactement l'alpha brut.

    **Le problème.** Un backtest annonce un rendement brut et un jeu
    d'hypothèses de coût. Le lecteur ne sait pas si le résultat tient parce que
    le signal est bon ou parce que les coûts supposés sont bas. La question
    utile n'est donc pas « combien reste-t-il après 5 points de base ? » mais
    « à partir de quel coût ne reste-t-il rien ? ».

    **L'intuition.** Le rendement net d'une période vaut le rendement brut moins
    le coût unitaire multiplié par la rotation de cette période. Le coût qui
    annule la moyenne du net est donc le rapport de la moyenne du brut à la
    moyenne des rotations.

    **La formule.**

    .. math::

        \bar{r}^{net}(c) = \frac{1}{T}\sum_t (r_t - c\,\tau_t) = 0
        \quad \Longleftrightarrow \quad
        c^{\ast} = \frac{\bar{r}}{\bar{\tau}}
        \qquad
        c^{\ast}_{bps} = 10^4 \, c^{\ast}

    Args:
        gross_returns: les rendements bruts de frais, une valeur par période.
        turnover_values: la rotation de chaque période, dans la même unité que
            celle du modèle de coût employé. Les deux séries sont alignées sur
            l'intersection de leurs index.
        frequency: la fréquence des deux séries. Elle sert au diagnostic
            journalisé, et le résultat n'en dépend pas.
        min_observations: nombre minimal de périodes communes exigé.
        max_dropped_fraction: part maximale des périodes qu'une des deux séries
            a le droit de perdre à l'alignement. Au-delà, la fonction lève.

    Returns:
        Le coût unitaire d'annulation, en points de base du montant négocié.
        Un nombre négatif signale que l'alpha brut est DÉJÀ négatif, donc
        qu'aucun coût positif ne le sauve.

    Raises:
        TypeError: une des deux entrées n'est pas une ``pandas.Series``.
        InsufficientDataError: moins de ``min_observations`` périodes communes.
        DataQualityError: un index porte des dates en double, l'alignement perd
            plus de ``max_dropped_fraction`` des périodes d'une des deux séries,
            une valeur manquante subsiste, une rotation est négative, ou la
            rotation moyenne est nulle.

    Example:
        Un signal rapporte 2 points de base par séance et tourne de 0,40 par
        séance, en moyenne.
        Son seuil de rentabilité vaut 2 / 0,40, soit 5 points de base par unité
        négociée. Au-delà de 5 points, il perd de l'argent.

    Note:
        **Variables.** :math:`r_t` est le rendement brut de la période *t*,
        :math:`\tau_t` sa rotation, :math:`T` le nombre de périodes,
        :math:`c^{\ast}` le coût unitaire d'annulation en fraction décimale.

        **La convention de rotation décide de la lecture du résultat.** Le
        chiffre rendu est un coût par unité de la rotation fournie. Une rotation
        en somme entière rend un coût par unité de montant négocié, directement
        comparable au demi-écart d'un titre. Une rotation en demi-somme rendrait
        le double, et la comparaison serait fausse d'un facteur deux.

        **Pourquoi la moyenne arithmétique.** L'égalité de la moyenne à zéro a
        une solution en forme fermée, ce qui rend le nombre vérifiable à la
        main. Le coût qui annule la richesse composée n'en a pas et se résout
        par bissection. Les deux diffèrent au second ordre, d'autant plus que la
        volatilité est grande.

        **Hypothèses.** Le coût est proportionnel à la rotation, donc linéaire.
        Sous un modèle d'impact convexe, le vrai seuil est PLUS BAS que celui-ci,
        parce que le coût croît plus vite que la rotation. Le chiffre rendu est
        donc un MAJORANT dès qu'un impact non linéaire existe.

        **Provenance.** La lecture par seuil de rentabilité est celle de
        Novy-Marx et Velikov (2016), *A taxonomy of anomalies and their trading
        costs*, Review of Financial Studies 29.
        Ces deux auteurs classent les anomalies par le coût qui les annule.
        Statut : rapporté, non revérifié au texte dans la session qui a écrit ce
        module.

        **Limites.** Un seuil élevé ne prouve pas qu'une stratégie est
        exploitable : il ne dit rien de la capacité, ni de la stabilité du signal
        hors échantillon. Un seuil bas, lui, suffit à conclure, et c'est la
        raison d'être de ce nombre.

        **Alternatives.** Rejouer la stratégie sur une grille de coûts et lire
        où la courbe croise zéro donne la même réponse à la résolution de la
        grille près, pour beaucoup plus de calcul. Voir
        ``quantlab.validation.robustness.cost_multiplier_analysis``.

        **L'alignement se trompe en silence.** Les deux séries sont jointes sur
        l'intersection de leurs dates. Une étude qui fournit 250 rendements et
        12 rotations obtiendrait un seuil calculé sur 12 périodes, sans rien qui
        le signale. Deux garde-fous ferment ce chemin.

        Le premier refuse un index qui porte deux fois la même date. Pandas
        apparie alors chaque doublon d'un côté à chaque doublon de l'autre.
        Contre-exemple chiffré : quatre dates, dupliquées deux fois dans les
        rendements et trois fois dans les rotations, rendent 4 x 2 x 3 = 24
        lignes appariées. Le plancher de douze observations est franchi alors
        que l'étude ne porte que sur quatre périodes réelles.

        Le second refuse une intersection qui perd plus de
        ``max_dropped_fraction`` des périodes d'un des deux côtés.

        **Comment vérifier.** Quatre contrôles. Appliquer le coût rendu à la
        série brute annule la moyenne du net à la précision machine. Multiplier
        tous les rendements bruts par deux double le seuil, exactement. Un index
        dupliqué fait lever. Une intersection maigre fait lever aussi.
    """
    if not isinstance(gross_returns, pd.Series):
        raise TypeError(f"gross_returns doit être une pandas.Series, reçu {type(gross_returns).__name__}")
    if not isinstance(turnover_values, pd.Series):
        raise TypeError(f"turnover_values doit être une pandas.Series, reçu {type(turnover_values).__name__}")

    for serie, nom in ((gross_returns, "gross_returns"), (turnover_values, "turnover_values")):
        if serie.index.has_duplicates:
            doublons = serie.index[serie.index.duplicated()].tolist()
            raise DataQualityError(
                f"{nom} porte des dates en double : {doublons[:5]}. "
                "L'alignement apparierait alors chaque doublon d'un côté à chaque doublon de "
                "l'autre, ce qui gonfle le nombre d'observations sans ajouter de période."
            )

    returns, rotations = gross_returns.astype(float).align(turnover_values.astype(float), join="inner")
    _reject_thin_overlap(
        kept=len(returns),
        sizes={"gross_returns": len(gross_returns), "turnover_values": len(turnover_values)},
        max_dropped_fraction=max_dropped_fraction,
    )
    if len(returns) < min_observations:
        raise InsufficientDataError(
            f"{len(returns)} périodes communes, {min_observations} exigées. "
            "Un rapport de deux moyennes calculé sur moins n'est pas interprétable."
        )
    if bool(returns.isna().any()) or bool(rotations.isna().any()):
        raise DataQualityError(
            "valeurs manquantes après alignement des rendements et des rotations. "
            "Une période sans rotation connue se retire explicitement en amont."
        )
    if bool((rotations < 0.0).any()):
        raise DataQualityError(
            "rotation négative rencontrée. Une rotation est une somme de valeurs absolues."
        )

    mean_turnover = float(rotations.mean())
    if mean_turnover <= 0.0:
        raise DataQualityError(
            "rotation moyenne nulle : la stratégie ne négocie jamais, donc aucun coût unitaire "
            "ne peut annuler son rendement. Le seuil de rentabilité n'est pas défini."
        )

    mean_gross = float(returns.mean())
    breakeven = BPS_PER_UNIT * mean_gross / mean_turnover
    _LOG.info(
        "seuil de rentabilité calculé",
        extra={
            "periodes": len(returns),
            "rendement_brut_annualise": mean_gross * frequency.periods_per_year,
            "rotation_annualisee": mean_turnover * frequency.periods_per_year,
            "seuil_bps": breakeven,
        },
    )
    return breakeven

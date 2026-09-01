r"""La rotation du portefeuille, et la convention qui la rend comparable.

**Le problème.** Le coût d'une stratégie est le produit de deux nombres, la
rotation et le coût unitaire. Le second se discute, le premier se croit acquis,
et c'est là que l'erreur entre. Selon qu'on compare les poids cibles aux poids
de la période précédente ou aux poids vers lesquels le marché les a fait
dériver, le même portefeuille affiche deux rotations différentes, parfois d'un
facteur deux. Un backtest qui se trompe de convention paie des frais qui
n'existent pas, ou en oublie qui existent.

**L'écart est mesurable, et il n'est pas petit.** Un portefeuille équipondéré
qu'on ne rééquilibre jamais a une rotation nulle : rien n'est acheté, rien n'est
vendu. Mesurée contre les poids cibles de la période précédente, sa rotation est
pourtant positive, puisque les poids observés ont bougé tout seuls. Sur deux
actifs partis de moitié-moitié dont l'un gagne 20 % et l'autre rien, la mesure
naïve annonce 1/22, soit 4,55 % de rotation, pour zéro transaction. Ce chiffre
est calculé, donc mesuré. Répétée douze fois l'an et multipliée par dix points
de base de coût, l'erreur retire 5,5 points de base de rendement annuel à une
stratégie qui ne négocie pas. Ce dernier chiffre est modélisé : il suppose douze
rééquilibrages et un coût unitaire de dix points de base, deux hypothèses
déclarées ici et vérifiables nulle part ailleurs.

**Les deux conventions de comptage.** La rotation d'une période vaut la somme
des variations de poids en valeur absolue, divisée par deux :

.. math::

    T_t = \frac{1}{2} \sum_{i=1}^{N} \left| w_{i,t} - w_{i,t}^{drift} \right|

Le facteur un demi compte un aller-retour une fois. Vendre trois points de A
pour acheter trois points de B fait six points de variation absolue et trois
points réellement négociés d'un côté, donc une rotation de 3 %. La convention
sans le facteur un demi, la somme entière, compte les deux côtés et rend le
double. Les deux se défendent ; ce qui ne se défend pas est de ne pas dire
laquelle est employée, puis de la multiplier par un coût unitaire calibré sur
l'autre.

**Provenance.** La forme en demi-somme est celle de Grinold et Kahn (2000),
*Active Portfolio Management*, 2e édition, chapitre sur les coûts de
transaction. La règle de publication des fonds américains, formulaire N-1A de la
SEC, retient le plus petit des achats et des ventes divisé par l'actif net moyen
mensuel. Elle donne la même grandeur pour un fonds pleinement investi, puisque
le plus petit des deux côtés est le montant négocié une fois. Statut de cette
seconde référence : rapporté, non revérifié au texte réglementaire dans la
session qui a écrit ce module.
"""

from __future__ import annotations

import math
from typing import Literal

import numpy as np
import pandas as pd

from quantlab.core.calendars import DEFAULT_CALENDAR, annualization_factor
from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.logging import get_logger
from quantlab.core.types import Frequency, ReturnFrame, ReturnSeries, WeightFrame, Weights

__all__ = [
    "DEFAULT_BASIS",
    "DEFAULT_CONVENTION",
    "MIN_GROWTH",
    "annualized_turnover",
    "drifted_weights",
    "holding_period",
    "trade_frame",
    "turnover",
    "turnover_series",
]

_LOG = get_logger(__name__)

#: Les deux façons de compter une rotation. ``half_sum`` compte le montant
#: négocié d'un seul côté, ``full_sum`` compte les deux côtés.
TurnoverConvention = Literal["half_sum", "full_sum"]

#: Les deux dénominateurs possibles de la dérive des poids. Ils coïncident si et
#: seulement si les poids somment à un.
DriftBasis = Literal["nav", "invested"]

#: Convention de rotation par défaut du laboratoire.
DEFAULT_CONVENTION: TurnoverConvention = "half_sum"

#: Base de dérive par défaut : la valeur liquidative, qui reste définie pour un
#: portefeuille long-short dont les poids somment à zéro.
DEFAULT_BASIS: DriftBasis = "nav"

#: Croissance de capital sous laquelle la dérive n'est plus définie. Un
#: portefeuille dont la valeur liquidative tombe à ce niveau n'a plus de poids
#: relatifs interprétables : diviser par ce nombre rendrait des poids arbitraires.
MIN_GROWTH: float = 1e-8

_CONVENTION_FACTOR: dict[str, float] = {"half_sum": 0.5, "full_sum": 1.0}


def _reject_missing(values: pd.Series, *, label: str) -> None:
    """Lève ``DataQualityError`` si la série porte au moins un ``NaN``.

    Le refus est séparé du reste de la validation parce qu'il ne porte pas sur
    la même population. La forme se contrôle sur la série entière ; les valeurs
    manquantes ne se contrôlent que sur les actifs réellement détenus.

    Args:
        values: la série à contrôler.
        label: le nom employé dans le message d'erreur.

    Raises:
        DataQualityError: au moins une valeur est manquante.
    """
    if bool(values.isna().any()):
        manquants = values.index[values.isna()].tolist()
        raise DataQualityError(
            f"{label} contient des valeurs manquantes sur {manquants}. "
            "Un NaN de poids ou de rendement se comble explicitement en amont, jamais ici."
        )


def _validated_series(values: pd.Series, *, label: str, require_complete: bool = True) -> pd.Series:
    """Rend la série en flottants après contrôle de forme, ou lève.

    Args:
        values: la série à contrôler.
        label: le nom employé dans le message d'erreur.
        require_complete: refuser les valeurs manquantes. Le mettre à faux sert
            aux séries dont seule une partie sera lue, un tableau de rendements
            couvrant un univers plus large que le portefeuille détenu.

    Returns:
        La même série, convertie en ``float``.

    Raises:
        TypeError: l'objet n'est pas une ``pandas.Series``.
        DataQualityError: l'index porte des doublons, la série n'est pas
            numérique, ou elle contient au moins un ``NaN`` quand
            ``require_complete``.
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
    if require_complete:
        _reject_missing(numeric, label=label)
    return numeric


def _convention_factor(convention: TurnoverConvention) -> float:
    """Rend le facteur multiplicatif de la convention, ou lève ``ConfigError``."""
    try:
        return _CONVENTION_FACTOR[convention]
    except KeyError as exc:
        attendues = ", ".join(sorted(_CONVENTION_FACTOR))
        raise ConfigError(f"convention inconnue : {convention!r}. Attendu : {attendues}.") from exc


def drifted_weights(
    previous_weights: Weights,
    period_returns: ReturnSeries,
    *,
    basis: DriftBasis = DEFAULT_BASIS,
    min_growth: float = MIN_GROWTH,
) -> Weights:
    r"""Rend les poids d'avant rééquilibrage, ceux vers lesquels le marché a dérivé.

    **Le problème.** Entre deux rééquilibrages, personne ne négocie et les poids
    changent quand même : la ligne qui monte pèse plus lourd le lendemain. Le
    poids à partir duquel se mesure une transaction n'est donc pas le poids cible
    de la période précédente, mais celui-ci.

    **L'intuition.** Chaque position vaut, en fin de période, ce qu'elle valait
    multiplié par un plus son rendement. Le poids est cette valeur rapportée à la
    valeur totale du portefeuille, elle aussi mise à jour.

    **La formule.**

    .. math::

        w_{i,t}^{drift} = \frac{w_{i,t-1}\,(1 + r_{i,t})}{D_t}
        \qquad
        D_t^{nav} = 1 + \sum_{j} w_{j,t-1}\, r_{j,t}
        \qquad
        D_t^{inv} = \sum_{j} w_{j,t-1}\,(1 + r_{j,t})

    Args:
        previous_weights: les poids détenus au début de la période, indexés par
            actif. Ils ne somment pas nécessairement à un.
        period_returns: les rendements simples de la période, indexés par actif.
            L'index doit couvrir tous les actifs détenus. Les actifs en trop sont
            ignorés, y compris quand leur rendement est manquant : un titre
            absent du portefeuille à cette date n'a pas à être coté. Un actif
            détenu dont le rendement manque fait lever.
        basis: le dénominateur retenu. ``"nav"`` divise par la croissance de la
            valeur liquidative, ``"invested"`` par la valeur investie.
        min_growth: seuil sous lequel le dénominateur est jugé dégénéré.

    Returns:
        Les poids dérivés, indexés comme ``previous_weights``.

    Raises:
        InsufficientDataError: les poids sont vides.
        DataQualityError: un actif détenu n'a pas de rendement, une valeur est
            manquante, ou le dénominateur est trop proche de zéro.
        ConfigError: la base demandée n'existe pas.

    Example:
        Deux actifs partis de 60 % et 40 %, le premier gagnant 10 % et le second
        perdant 5 %. Les valeurs deviennent 0,66 et 0,38, la valeur liquidative
        1,04, et les poids dérivés 66/104 = 0,634615 et 38/104 = 0,365385.

    Note:
        **Variables.** :math:`w_{i,t-1}` est le poids de l'actif *i* au début de
        la période, :math:`r_{i,t}` son rendement simple sur la période,
        :math:`D_t` le dénominateur choisi, :math:`N` le nombre d'actifs.

        **Hypothèses.** Les rendements sont des rendements simples, dividendes
        réinvestis dans la ligne qui les verse. Aucun flux externe n'entre ni ne
        sort pendant la période. Aucune action de société ne redéfinit l'actif.

        **Le cas long-short, et le choix retenu.** La forme classique divise par
        la somme des valeurs, :math:`D_t^{inv}`. Cette somme vaut un pour un
        portefeuille long-short à financement neutre, mais elle vaut zéro pour un
        portefeuille en dollars neutres, et elle peut devenir négative sur un
        livre à découvert net. Diviser par zéro n'a pas de sens, et diviser par un
        nombre négatif retourne tous les signes des poids en silence, ce qui est
        pire. Le laboratoire retient donc par défaut la croissance de la valeur
        liquidative, :math:`D_t^{nav} = 1 + w' r`, qui est le rendement du
        portefeuille augmenté de un. Elle reste strictement positive tant que
        le capital n'est pas détruit. Elle vaut exactement :math:`D_t^{inv}`
        quand les poids somment à un, et elle rend une exposition nette mise à
        jour plutôt que renormalisée. Quand la croissance passe
        sous ``min_growth``, la fonction lève plutôt que de rendre des poids
        arbitraires.

        **Limites.** La dérive ainsi calculée ignore les frais de garde, les
        appels de marge d'un livre à découvert et le coût d'emprunt du titre.
        L'ampleur de ce que ces trois postes déplacent n'a pas été mesurée ici :
        non vérifié. Ils se traitent dans le modèle de coût, pas dans la dérive,
        parce qu'ils dépendent du courtier et du contrat, pas des rendements.

        **Alternatives.** Certaines maisons figent les poids entre deux
        rééquilibrages et mesurent la rotation contre les poids cibles, ce qui
        revient à ignorer la dérive. C'est plus simple et faux dès que la
        dispersion des rendements est grande. D'autres suivent des quantités de
        titres plutôt que des poids, ce qui est exact mais exige le prix et le
        nombre de parts, donc une comptabilité complète.

        **Pourquoi cette méthode ici.** Le laboratoire ne tient pas de
        comptabilité de parts. Les poids et les rendements suffisent à retrouver
        la dérive exactement, sans hypothèse supplémentaire.

        **Comment vérifier.** Trois contrôles indépendants du code. Sur un
        portefeuille pleinement investi, si tous les rendements sont égaux, les
        poids dérivés valent les poids de départ, quel que soit le rendement
        commun. Si les poids somment à un, les poids dérivés somment à un. Si un
        actif perd 100 %, son poids dérivé est nul et les autres se repartagent
        le total.
    """
    weights = _validated_series(previous_weights, label="previous_weights")
    if weights.empty:
        raise InsufficientDataError("previous_weights est vide : aucune dérive à calculer.")
    returns = _validated_series(period_returns, label="period_returns", require_complete=False)

    absents = weights.index.difference(returns.index)
    if len(absents) > 0:
        raise DataQualityError(
            f"rendement manquant pour {absents.tolist()}. Un actif détenu sans rendement "
            "ne se remplace pas par zéro en silence."
        )
    aligned_returns = returns.reindex(weights.index)
    _reject_missing(aligned_returns, label="period_returns")

    grown = weights * (1.0 + aligned_returns)
    if basis == "nav":
        denominator = 1.0 + float((weights * aligned_returns).sum())
    elif basis == "invested":
        denominator = float(grown.sum())
    else:
        raise ConfigError(f"base de dérive inconnue : {basis!r}. Attendu : nav, invested.")

    if abs(denominator) < min_growth:
        raise DataQualityError(
            f"dénominateur de dérive dégénéré ({denominator:.3e}) pour la base {basis!r}. "
            "Les poids relatifs ne sont plus définis : capital détruit, ou portefeuille "
            "en dollars neutres traité avec la base « invested »."
        )
    return grown / denominator


def turnover(
    previous: Weights,
    target: Weights,
    *,
    drifted: bool = True,
    period_returns: ReturnSeries | None = None,
    convention: TurnoverConvention = DEFAULT_CONVENTION,
    basis: DriftBasis = DEFAULT_BASIS,
    min_growth: float = MIN_GROWTH,
) -> float:
    r"""Rend la rotation d'un rééquilibrage, en fraction de la valeur du portefeuille.

    **Le problème.** Le coût de transaction d'une période est la rotation
    multipliée par un coût unitaire. Une rotation mal définie fausse donc tout
    coût, dans les deux sens et sans laisser de trace.

    **L'intuition.** On mesure le chemin parcouru par les poids, puis on le
    divise par deux parce qu'un aller-retour se paie une fois du côté acheteur.
    Cette lecture suppose que le rééquilibrage s'autofinance, tout achat étant
    payé par une vente. Elle cesse d'être exacte dès que de l'encaisse entre ou
    sort, et la note ci-dessous en donne le contre-exemple chiffré.

    **La formule.**

    .. math::

        T_t = \frac{1}{2} \sum_{i=1}^{N} \left| w_{i,t} - b_{i,t} \right|
        \qquad
        b_{i,t} = \begin{cases}
            w_{i,t}^{drift} & \text{si } \texttt{drifted} \\
            w_{i,t-1} & \text{sinon}
        \end{cases}

    Args:
        previous: les poids détenus avant le rééquilibrage.
        target: les poids visés après le rééquilibrage.
        drifted: mesurer contre les poids dérivés plutôt que contre les poids
            de départ. Vrai par défaut, parce que c'est ce qui se négocie.
        period_returns: les rendements de la période, exigés si ``drifted``.
        convention: ``"half_sum"`` ou ``"full_sum"``.
        basis: la base de dérive passée à :func:`drifted_weights`.
        min_growth: le seuil de dégénérescence du dénominateur de dérive.

    Returns:
        La rotation de la période, en fraction de la valeur du portefeuille.

    Raises:
        ConfigError: ``drifted`` est vrai sans ``period_returns``, ou la
            convention est inconnue.
        InsufficientDataError: les deux vecteurs de poids sont vides.
        DataQualityError: une valeur manque, ou la dérive est dégénérée.

    Example:
        Poids de départ 60 % et 40 %, rendements +10 % et -5 %, cible
        moitié-moitié. Les poids dérivés valent 33/52 et 19/52. Les écarts
        valent 7/52 des deux côtés, leur somme 14/52, et la rotation 7/52, soit
        13,46 %. Mesurée sans la dérive, contre 60 % et 40 %, elle vaut 10,00 %,
        soit un quart de moins.

    Note:
        **Variables.** :math:`w_{i,t}` est le poids cible, :math:`b_{i,t}` le
        poids de référence, dérivé ou non, :math:`N` le nombre d'actifs de
        l'union des deux index.

        **Hypothèses.** Un actif absent d'un des deux vecteurs porte un poids
        nul, ce qui est la lecture correcte d'une entrée ou d'une sortie
        d'univers. Les deux vecteurs sont exprimés dans la même unité, la
        fraction de valeur liquidative.

        **Provenance.** Grinold et Kahn (2000), *Active Portfolio Management*,
        pour la demi-somme ; la règle N-1A de la SEC pour l'équivalence avec le
        plus petit des achats et des ventes, rapportée et non revérifiée ici.

        **La limite principale, mesurée.** La demi-somme égale le montant
        négocié d'un seul côté quand les achats égalent les ventes, donc quand la
        somme des poids ne change pas. Sinon elle tombe entre les deux côtés sans
        valoir ni l'un ni l'autre. Contre-exemple calculé à la main. Un
        portefeuille détient 60 % de A, 20 % de B et 20 % d'encaisse, A gagne
        50 %, et la cible devient moitié-moitié sans encaisse. Les poids dérivés
        valent 18/26 et 4/26, les variations -5/26 et +9/26. La demi-somme rend
        alors 7/26, soit 26,92 %, quand les achats font 9/26 et les ventes 5/26.
        La règle N-1A de la SEC, qui retient le plus petit des deux côtés,
        rendrait 5/26. L'écart entre les achats et les ventes, 4/26, est
        exactement l'encaisse consommée. Un modèle de coût qui facture les deux
        côtés séparément prend donc :func:`trade_frame`, pas cette fonction.

        **Limites.** La rotation ne dit rien de la difficulté d'exécution. Deux
        points de rotation sur un titre qui échange un milliard par jour et deux
        points sur une petite capitalisation illiquide coûtent des sommes sans
        rapport. Le passage de la rotation au coût appartient au modèle de coût,
        qui prend la taille, la liquidité et l'urgence.

        **Alternatives.** La somme entière, sans le facteur un demi, est employée
        quand le modèle de coût facture chaque côté séparément. La rotation en
        dollars, la même formule multipliée par la valeur liquidative, est
        préférée par les tables d'exécution. Ce module rend une fraction, et la
        conversion en dollars appartient à l'appelant.

        **Pourquoi cette méthode ici.** La demi-somme se multiplie directement
        par un coût aller simple, qui est la forme sous laquelle les coûts
        d'exécution sont publiés.

        **Comment vérifier.** Trois contrôles. Un rééquilibrage vers les poids de
        référence eux-mêmes rend zéro. Un renversement complet d'un portefeuille
        long-only pleinement investi rend un, qui est le maximum atteignable. La
        demi-somme vaut exactement la moitié de la distance de Manhattan entre
        les deux vecteurs, que ``scipy.spatial.distance.cityblock`` calcule
        indépendamment.
    """
    factor = _convention_factor(convention)
    base = _validated_series(previous, label="previous")
    goal = _validated_series(target, label="target")
    if base.empty and goal.empty:
        raise InsufficientDataError("previous et target sont vides : aucune rotation à mesurer.")

    if drifted:
        if period_returns is None:
            raise ConfigError(
                "period_returns est exigé quand drifted vaut True. Passer drifted=False "
                "mesure contre les poids cibles précédents, ce qui est une autre convention."
            )
        base = drifted_weights(base, period_returns, basis=basis, min_growth=min_growth)

    universe = base.index.union(goal.index)
    diff = goal.reindex(universe, fill_value=0.0) - base.reindex(universe, fill_value=0.0)
    return factor * float(np.abs(diff.to_numpy()).sum())


def trade_frame(
    weight_frame: WeightFrame,
    returns_frame: ReturnFrame | None = None,
    *,
    drifted: bool = True,
    basis: DriftBasis = DEFAULT_BASIS,
    include_initial: bool = False,
    min_growth: float = MIN_GROWTH,
) -> pd.DataFrame:
    r"""Rend les variations de poids négociées à chaque date de rééquilibrage.

    **Le problème.** Une rotation scalaire perd le signe, et un coût réel n'est
    pas symétrique : vendre à découvert coûte l'emprunt du titre, acheter ne le
    coûte pas. Un module qui ne rendrait que la rotation interdirait donc tout
    modèle de coût asymétrique.

    **L'intuition.** On garde la variation de chaque ligne, avec son signe, au
    lieu de l'écraser dans une somme de valeurs absolues.

    **La formule.**

    .. math::

        \delta_{i,t} = w_{i,t} - b_{i,t}

    où :math:`w_{i,t}` est le poids cible de l'actif *i* à la date *t* et
    :math:`b_{i,t}` son poids de référence, dérivé ou non. La quantité
    :math:`\delta_{i,t}` est la fraction de valeur liquidative achetée, en
    positif, ou vendue, en négatif.

    **Provenance.** Les modèles d'impact de marché prennent en entrée le volume
    signé plutôt que son module, dont celui d'Almgren, Thum, Hauptmann et Li
    (2005). Statut de cette référence : rapportée, non revérifiée au texte dans
    la session qui a écrit ce module. La rotation de :func:`turnover_series` est
    la contraction de ce tableau, jamais l'inverse.

    **Hypothèses.** Le rééquilibrage est instantané à la date portée par la
    ligne, et le rendement de la période est déjà réalisé quand il a lieu.

    **Limites.** Les variations sont exprimées en fraction de valeur
    liquidative, pas en titres ni en dollars. La conversion appartient à
    l'appelant, qui seul connaît la taille du portefeuille.

    **Alternatives.** Un journal d'ordres réels serait exact et exigerait une
    comptabilité de parts, que le laboratoire ne tient pas.

    **Pourquoi cette méthode ici.** Un seul calcul sert deux consommateurs. Le
    modèle de coût lit les signes, la rotation lit les valeurs absolues, et la
    formule ne vit donc qu'à un endroit.

    **Comment vérifier.** La somme d'une ligne vaut zéro pour un portefeuille
    pleinement investi rééquilibré, puisque tout achat est financé par une
    vente. Cette identité sert de contrôle dans les tests.

    Args:
        weight_frame: les poids cibles, lignes = dates de rééquilibrage,
            colonnes = actifs. L'index doit être trié et sans doublon.
        returns_frame: les rendements simples de chaque période, la ligne datée
            *t* portant le rendement réalisé entre la date *t-1* et la date *t*.
            Exigé si ``drifted``.
        drifted: mesurer les variations contre les poids dérivés.
        basis: la base de dérive.
        include_initial: compter la première ligne comme une construction depuis
            l'encaisse, tous les poids de référence étant nuls. Faux par défaut,
            parce que la mise en place initiale n'est pas de la rotation
            récurrente et gonfle la moyenne annualisée.
        min_growth: le seuil de dégénérescence de la dérive.

    Returns:
        Un tableau de variations de poids, lignes = dates négociées, colonnes =
        actifs de ``weight_frame``.

    Raises:
        ConfigError: ``drifted`` est vrai sans ``returns_frame``.
        InsufficientDataError: moins de deux dates sans ``include_initial``.
        DataQualityError: index en double, index non trié, poids non
            numériques, valeur manquante, ou rendement absent à une date de
            rééquilibrage.
    """
    if not isinstance(weight_frame, pd.DataFrame):
        raise TypeError(f"weight_frame doit être un pandas.DataFrame, reçu {type(weight_frame).__name__}")
    if weight_frame.index.has_duplicates:
        raise DataQualityError("weight_frame porte des dates en double.")
    if not weight_frame.index.is_monotonic_increasing:
        raise DataQualityError("weight_frame doit être trié par date croissante.")
    if drifted and returns_frame is None:
        raise ConfigError("returns_frame est exigé quand drifted vaut True.")

    n_dates = len(weight_frame.index)
    if n_dates < 2 and not include_initial:
        raise InsufficientDataError(
            f"weight_frame porte {n_dates} date(s). Il en faut au moins deux pour une rotation, "
            "ou include_initial=True pour compter la construction initiale."
        )
    if n_dates == 0:
        raise InsufficientDataError(
            "weight_frame ne porte aucune date. Rendre un tableau vide laisserait passer "
            "une rotation nulle qui n'a jamais été mesurée."
        )

    try:
        weights = weight_frame.astype(float)
    except (TypeError, ValueError) as exc:
        raise DataQualityError(f"weight_frame n'est pas numérique : {exc}") from exc
    zeros = pd.Series(0.0, index=weights.columns, dtype=float)

    rows: list[pd.Series] = []
    dates: list[object] = []
    positions = range(0, n_dates) if include_initial else range(1, n_dates)
    for position in positions:
        date = weights.index[position]
        goal = _validated_series(weights.iloc[position], label=f"weight_frame[{date}]")
        if position == 0:
            base = zeros
        else:
            base = _validated_series(
                weights.iloc[position - 1], label=f"weight_frame[{weights.index[position - 1]}]"
            )
            if drifted and returns_frame is not None:
                base = drifted_weights(
                    base,
                    _period_returns_at(returns_frame, date),
                    basis=basis,
                    min_growth=min_growth,
                )
        rows.append(goal - base.reindex(goal.index, fill_value=0.0))
        dates.append(date)

    result = pd.DataFrame(rows, index=pd.Index(dates, name=weights.index.name), columns=weights.columns)
    _LOG.debug(
        "variations de poids calculées",
        extra={"dates": len(result.index), "assets": len(result.columns), "drifted": drifted},
    )
    return result


def _period_returns_at(returns_frame: ReturnFrame, date: object) -> pd.Series:
    """Rend la ligne de rendements datée, ou lève ``DataQualityError``."""
    if not isinstance(returns_frame, pd.DataFrame):
        raise TypeError(f"returns_frame doit être un pandas.DataFrame, reçu {type(returns_frame).__name__}")
    if returns_frame.index.has_duplicates:
        raise DataQualityError("returns_frame porte des dates en double.")
    if date not in returns_frame.index:
        raise DataQualityError(
            f"aucun rendement à la date de rééquilibrage {date}. La ligne datée t doit porter "
            "le rendement réalisé entre t-1 et t."
        )
    return returns_frame.loc[date]


def turnover_series(
    weight_frame: WeightFrame,
    returns_frame: ReturnFrame | None = None,
    *,
    drifted: bool = True,
    convention: TurnoverConvention = DEFAULT_CONVENTION,
    basis: DriftBasis = DEFAULT_BASIS,
    include_initial: bool = False,
    min_growth: float = MIN_GROWTH,
) -> pd.Series:
    """Rend la rotation de chaque date de rééquilibrage.

    Args:
        weight_frame: les poids cibles, une ligne par date de rééquilibrage.
        returns_frame: les rendements de période, exigés si ``drifted``.
        drifted: mesurer contre les poids dérivés.
        convention: ``"half_sum"`` ou ``"full_sum"``.
        basis: la base de dérive.
        include_initial: compter la construction initiale depuis l'encaisse.
        min_growth: le seuil de dégénérescence de la dérive.

    Returns:
        Une série de rotations indexée par date, nommée ``"turnover"``.

    Note:
        Une seule définition de la rotation existe dans le paquet : cette
        fonction applique le facteur de convention aux variations rendues par
        :func:`trade_frame`. La formule ne vit donc qu'à un endroit.
    """
    factor = _convention_factor(convention)
    trades = trade_frame(
        weight_frame,
        returns_frame,
        drifted=drifted,
        basis=basis,
        include_initial=include_initial,
        min_growth=min_growth,
    )
    values = factor * trades.abs().sum(axis=1)
    return values.rename("turnover")


def annualized_turnover(
    turnover_values: pd.Series | float,
    frequency: Frequency = Frequency.MONTHLY,
    *,
    measured_over: tuple[str, str] | None = None,
    calendar: str = DEFAULT_CALENDAR,
) -> float:
    r"""Rend la rotation annuelle, la moyenne par période multipliée par le nombre de périodes.

    **Le problème.** Deux stratégies rééquilibrées à des rythmes différents ne
    se comparent pas sur leur rotation par période. Une rotation de 10 % par
    mois et une rotation de 10 % par trimestre négocient l'une trois fois plus
    que l'autre, et le même nombre s'affiche.

    **L'intuition.** La rotation est un flux, pas une variance : elle
    s'annualise en multipliant par le nombre de périodes de l'année, sans racine
    carrée. La racine carrée appartient à l'écart type, parce que ce sont les
    variances qui s'additionnent, pas les écarts types.

    **La formule.**

    .. math::

        T_{ann} = \bar{T} \times N
        \qquad
        \bar{T} = \frac{1}{|\mathcal{O}|} \sum_{t \in \mathcal{O}} T_t

    Args:
        turnover_values: les rotations par période, ou une rotation moyenne déjà
            calculée. Les ``NaN`` sont retirés avant la moyenne.
        frequency: la fréquence des rééquilibrages.
        measured_over: si donné et si la fréquence est quotidienne, compte les
            séances réelles de la période au lieu d'appliquer 252.
        calendar: le marché servant au comptage.

    Returns:
        La rotation annuelle, en fraction de la valeur du portefeuille.

    Raises:
        InsufficientDataError: la série est vide ou entièrement manquante.

    Example:
        Douze rééquilibrages mensuels à 10 % chacun donnent 1,2 par an, soit
        120 % de la valeur du portefeuille négociée dans l'année.

    Note:
        **Variables.** :math:`T_t` est la rotation de la période *t*,
        :math:`\mathcal{O}` l'ensemble des périodes observées, celles dont la
        rotation n'est pas manquante, :math:`N` le nombre de périodes par an, et
        :math:`T_{ann}` la rotation annuelle.

        **Hypothèses.** Le rythme de rééquilibrage est régulier, et les périodes
        manquantes le sont au hasard. La seconde hypothèse est forte : si les
        périodes manquantes sont précisément les périodes agitées, celles où la
        rotation est la plus grande, la moyenne des périodes restantes
        sous-estime la rotation vraie.

        **Provenance.** L'usage de multiplier un flux par le nombre de périodes
        est celui du calcul de rotation des fonds, formulaire N-1A de la SEC,
        qui rapporte les transactions d'un exercice entier à l'actif net moyen.
        Statut : rapporté, non revérifié au texte réglementaire ici.

        **Limites.** L'hypothèse de régularité tombe pour une politique à
        bandes, déclenchée par un seuil plutôt que par le calendrier. Une année
        calme y porte deux rééquilibrages et une année agitée neuf, si bien que
        la moyenne par période ne se multiplie plus par un nombre fixe.

        **Alternatives.** Pour une politique à bandes, la mesure juste somme les
        rotations observées et divise par le nombre d'années couvertes. Elle
        n'est pas implémentée ici, et cette absence est délibérée : elle exige
        un index daté, que ``turnover_values`` ne porte pas toujours.

        **Pourquoi cette méthode ici.** Les études du laboratoire rééquilibrent
        à date fixe, ce qui satisfait l'hypothèse de régularité par
        construction.

        **Comment vérifier.** Une série constante à *x* en fréquence mensuelle
        rend exactement *12x*. Le facteur vient de
        :func:`quantlab.core.calendars.annualization_factor`, donc il peut être
        mesuré sur un calendrier réel plutôt que supposé.
    """
    if isinstance(turnover_values, pd.Series):
        clean = turnover_values.astype(float).dropna()
        if clean.empty:
            raise InsufficientDataError("aucune rotation observée : la série est vide ou toute manquante.")
        mean_per_period = float(clean.mean())
    else:
        mean_per_period = float(turnover_values)
    factor = annualization_factor(frequency, measured_over=measured_over, calendar=calendar)
    return mean_per_period * factor


def holding_period(turnover_annual: float) -> float:
    """Rend la durée de détention moyenne impliquée par une rotation annuelle, en années.

    **L'intuition.** Une rotation de deux par an veut dire que l'équivalent du
    portefeuille est remplacé deux fois dans l'année, donc qu'une position vit
    six mois en moyenne.

    .. math::

        H = \\frac{1}{T_{ann}}

    Args:
        turnover_annual: la rotation annuelle, en fraction de la valeur du
            portefeuille, telle que rendue par :func:`annualized_turnover`.

    Returns:
        La durée de détention moyenne en années. Une rotation nulle rend
        l'infini, qui est la lecture correcte d'un portefeuille jamais négocié.

    Raises:
        ValueError: la rotation est négative, ce qui n'a pas de sens puisque la
            rotation est une somme de valeurs absolues.

    Example:
        Une rotation annuelle de 1,2 donne 1/1,2 = 0,833 an, soit dix mois.

    Note:
        **Variables.** :math:`T_{ann}` est la rotation annuelle, :math:`H` la
        durée de détention en années.

        **Hypothèses.** Le portefeuille est stationnaire, et chaque
        rééquilibrage remplace une fraction constante de lignes tirées au hasard.

        **Limites, et elles sont fortes.** L'inverse de la rotation est une
        moyenne, et la distribution des durées est souvent bimodale. Un fonds
        garde la moitié de ses lignes trois ans et négocie l'autre moitié chaque
        mois. Sa rotation annuelle donne alors une durée moyenne que presque
        aucune position ne connaît. La grandeur ne se lit pas non plus comme un
        horizon de signal. Un signal à un an rééquilibré mensuellement pour
        contrôler le risque affiche une durée de détention bien plus courte que
        son horizon.

        **Alternatives.** La durée de détention mesurée, la moyenne des durées
        de vie réelles des positions, est exacte et exige un registre de
        positions. Le taux de survie à *k* périodes, la part des positions encore
        détenues *k* périodes plus tard, décrit la distribution entière plutôt
        que sa moyenne.

        **Pourquoi cette méthode ici.** Elle se calcule depuis la seule rotation,
        déjà mesurée, et sert à ranger des stratégies par ordre de grandeur, pas
        à décider d'un horizon.

        **Comment vérifier.** Le produit de la rotation et de la durée vaut un,
        par construction, pour toute rotation strictement positive.
    """
    if turnover_annual < 0.0:
        raise ValueError(
            f"rotation annuelle négative ({turnover_annual}). Une rotation est une somme de "
            "valeurs absolues, donc positive ou nulle."
        )
    if turnover_annual == 0.0:
        return math.inf
    return 1.0 / turnover_annual

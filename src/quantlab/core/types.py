"""Les types du laboratoire, et la convention d'annualisation.

Ce module fixe trois choses que le reste du code ne rediscute jamais : ce qu'est
un rendement, à quelle fréquence il est observé, et par quel nombre on annualise.

**La frontière pandas / Polars.** Le lac de données parle Parquet, DuckDB et
Polars ; l'analytique parle pandas indexé par le temps. La conversion se fait une
fois, à la sortie de la couche *gold*, et jamais dans l'autre sens à l'intérieur
d'un calcul. La raison est mesurable : ``statsmodels``, ``arch`` et ``skfolio``
prennent tous du pandas, si bien qu'un pipeline tout-Polars paierait une
conversion par appel. Le détail du raisonnement vit dans ``ADR-001``.
"""

from __future__ import annotations

from enum import StrEnum

import pandas as pd

#: Une série de rendements indexée par la date d'observation (fin de période).
type ReturnSeries = pd.Series
#: Un tableau de rendements, lignes = dates, colonnes = actifs ou stratégies.
type ReturnFrame = pd.DataFrame
#: Un vecteur de poids de portefeuille, indexé par actif. Ne somme pas
#: nécessairement à 1 : un portefeuille long-short à somme nulle est légitime.
type Weights = pd.Series
#: Une suite de poids dans le temps, lignes = dates de rééquilibrage.
type WeightFrame = pd.DataFrame


class ReturnKind(StrEnum):
    r"""Rendement simple ou rendement logarithmique.

    Le rendement simple, la variation relative du prix d'une période à l'autre,
    s'agrège dans la dimension des actifs : le rendement d'un portefeuille est
    la moyenne pondérée des rendements simples de ses lignes. Le rendement
    logarithmique, le logarithme du rapport des prix, s'agrège dans la dimension
    du temps : la somme des rendements logarithmiques d'une période est le
    rendement logarithmique de la période entière.

    .. math::

        r_t = \frac{P_t}{P_{t-1}} - 1
        \qquad
        r_t^{\log} = \ln\!\left(\frac{P_t}{P_{t-1}}\right)
        = \ln(1 + r_t)

    Aucune des deux n'est « la bonne » : chacune est additive dans une dimension
    et pas dans l'autre. La règle du laboratoire est donc de composer les
    portefeuilles en rendement simple, de cumuler dans le temps en rendement
    logarithmique, et de dire lequel est affiché à chaque fois.

    Conséquence chiffrée à connaître. Une hausse de 10 % suivie d'une baisse de
    10 % laisse 0,99, soit une perte de 1 %, alors que la moyenne arithmétique
    des deux rendements simples vaut zéro. En logarithme, +0,09531 puis -0,10536
    somment à -0,01005, dont l'exponentielle rend exactement 0,99.
    """

    SIMPLE = "simple"
    LOG = "log"


class Frequency(StrEnum):
    r"""La fréquence d'observation d'une série, et son facteur d'annualisation.

    **Pourquoi 252 et pas 365.** L'annualisation d'une volatilité multiplie
    l'écart type de la période par la racine du nombre de périodes dans l'année.
    Pour du quotidien, ce nombre est celui des séances de bourse, pas celui des
    jours du calendrier : un marché fermé ne produit pas de rendement.

    .. math::

        \sigma_{ann} = \sigma_{p\acute{e}riode} \sqrt{N}

    **Hypothèse cachée derrière la racine.** Cette formule suppose des
    rendements non corrélés dans le temps. Si les rendements sont
    autocorrélés, elle est fausse, et l'erreur va dans les deux sens :
    l'autocorrélation positive, fréquente sur les fonds peu liquides, fait
    sous-estimer la volatilité annuelle, donc surestimer le ratio de Sharpe.
    ``quantlab.analytics.risk.annualization_bias`` mesure l'ampleur du biais sur
    une série donnée plutôt que de le supposer nul.

    **252 est une convention, pas une mesure.** Le nombre réel de séances varie
    d'une année et d'un marché à l'autre. ``quantlab.core.calendars`` sait
    compter les séances effectives d'un calendrier d'échange, et
    ``sessions_per_year`` rend le compte mesuré. La constante ci-dessous sert de
    valeur par défaut déclarée, jamais de vérité.
    """

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"

    @property
    def periods_per_year(self) -> float:
        """Le facteur d'annualisation conventionnel de la fréquence.

        Returns:
            Le nombre de périodes par an retenu par convention : 252 séances,
            52 semaines, 12 mois, 4 trimestres, 1 an.

        Note:
            Convention déclarée, non mesurée. Pour le nombre réel de séances
            d'un marché, voir :func:`quantlab.core.calendars.sessions_per_year`.
        """
        return {
            Frequency.DAILY: 252.0,
            Frequency.WEEKLY: 52.0,
            Frequency.MONTHLY: 12.0,
            Frequency.QUARTERLY: 4.0,
            Frequency.ANNUAL: 1.0,
        }[self]

    @property
    def pandas_alias(self) -> str:
        """L'alias de rééchantillonnage pandas correspondant, fin de période."""
        return {
            Frequency.DAILY: "B",
            Frequency.WEEKLY: "W-FRI",
            Frequency.MONTHLY: "ME",
            Frequency.QUARTERLY: "QE",
            Frequency.ANNUAL: "YE",
        }[self]


class AssetClass(StrEnum):
    """La classe d'actif d'un instrument.

    Elle sert à deux choses et à rien d'autre : construire un portefeuille
    équipondéré par classe comme le fait Moskowitz, Ooi et Pedersen (2012), et
    découper une attribution de performance. Elle ne porte aucune hypothèse de
    modèle.
    """

    EQUITY = "equity"
    EQUITY_INDEX = "equity_index"
    BOND = "bond"
    RATE = "rate"
    FX = "fx"
    COMMODITY = "commodity"
    CREDIT = "credit"
    CASH = "cash"
    MULTI = "multi"


class Verdict(StrEnum):
    """Le verdict standardisé d'une étude.

    Un verdict ne se choisit pas : il se déduit des contrôles qui ont tourné,
    selon les seuils déclarés dans la configuration de l'étude. Voir
    ``quantlab.experiments.verdict``.

    - ``REJECTED``            l'hypothèse économique ne survit pas aux données ;
    - ``EXPERIMENTAL``        un résultat existe, les contrôles ne sont pas passés ;
    - ``REPLICATED``          les chiffres de l'article sont retrouvés dans nos tolérances ;
    - ``ROBUST``              le résultat survit aux coûts, aux sous-périodes et au hors échantillon ;
    - ``PORTFOLIO_CANDIDATE`` il est robuste **et** apporte au portefeuille existant.

    Le passage de ``ROBUST`` à ``PORTFOLIO_CANDIDATE`` ne dépend pas de la
    stratégie seule mais de sa corrélation avec les autres : une stratégie de
    Sharpe 0,8 décorrélée bat une stratégie de Sharpe 1,5 déjà détenue.
    """

    REJECTED = "REJECTED"
    EXPERIMENTAL = "EXPERIMENTAL"
    REPLICATED = "REPLICATED"
    ROBUST = "ROBUST"
    PORTFOLIO_CANDIDATE = "PORTFOLIO_CANDIDATE"


class SampleTag(StrEnum):
    """L'échantillon auquel un chiffre de performance appartient.

    Toute mesure publiée par le laboratoire porte cette étiquette. Un ratio de
    Sharpe sans elle est un chiffre sans signification : le même nombre vaut une
    découverte hors échantillon et rien du tout dans l'échantillon
    d'entraînement.
    """

    IN_SAMPLE = "IS"
    VALIDATION = "VALIDATION"
    OUT_OF_SAMPLE = "OOS"
    FINAL_HOLDOUT = "FINAL_HOLDOUT"


class CostBasis(StrEnum):
    """Une performance est brute de frais, ou nette, et jamais implicite."""

    GROSS = "gross"
    NET = "net"

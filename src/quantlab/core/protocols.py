"""Les interfaces du laboratoire : ce que chaque brique promet, et rien de plus.

**Le problème.** Une stratégie qui appelle ``yfinance.download`` est une
stratégie qu'on ne peut plus faire tourner sur une autre source, ni tester sans
réseau, ni rejouer à l'identique dans deux ans. Le couplage à un fournisseur
n'est pas un détail d'implémentation : il décide de ce qui restera
reproductible.

**Le remède.** Les stratégies dépendent d'un ``DataProvider``, qui est une
promesse et non une bibliothèque. ``YahooProvider`` la tient aujourd'hui, un
fournisseur professionnel la tiendra demain, et pas une ligne de stratégie ne
change. C'est l'inversion de dépendance, et c'est la seule raison pour laquelle
ce module existe.

Les protocoles sont déclarés avec ``typing.Protocol`` et ``runtime_checkable``,
donc structurels : une classe les satisfait en portant les bonnes méthodes, sans
hériter de quoi que ce soit. Composition plutôt qu'héritage.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    import pandas as pd

    from quantlab.core.types import ReturnFrame, ReturnSeries, WeightFrame, Weights
    from quantlab.data.manifest import DatasetManifest


@runtime_checkable
class DataProvider(Protocol):
    """Rend des données brutes horodatées, et la provenance qui va avec.

    La provenance n'est pas un ornement. Sans elle, la question « quelle donnée
    exacte a produit ce résultat ? » n'a pas de réponse, et le résultat n'est
    pas reproductible, quelle que soit la qualité du code qui l'a produit.
    """

    name: str

    def fetch(self, *, start: dt.date, end: dt.date, **kwargs: Any) -> pd.DataFrame:
        """Télécharge la donnée brute de la période demandée."""
        ...

    def manifest(self, **kwargs: Any) -> DatasetManifest:
        """Décrit ce qui vient d'être téléchargé : source, licence, empreinte."""
        ...


@runtime_checkable
class PointInTimeDataset(Protocol):
    """Un jeu de données qui sait ce qu'il était à une date passée.

    L'unique méthode qui compte est :meth:`as_of`. Elle sépare la période
    économique décrite par une donnée de la date à laquelle cette donnée est
    devenue connaissable, et ne rend jamais la seconde avant la première.
    """

    def as_of(self, date: dt.date | str) -> pd.DataFrame:
        """Rend l'état du jeu tel qu'il était connaissable à ``date``."""
        ...


@runtime_checkable
class FeatureTransformer(Protocol):
    """Transforme des données en caractéristiques utilisables par un modèle.

    Le contrat impose que ``fit`` ne voie que le passé. C'est là que se
    glissent la plupart des fuites : une normalisation calculée sur
    l'échantillon entier fait fuiter la moyenne du futur dans le passé.
    """

    def fit(self, X: pd.DataFrame, y: pd.Series | None = None) -> FeatureTransformer: ...
    def transform(self, X: pd.DataFrame) -> pd.DataFrame: ...


@runtime_checkable
class AlphaModel(Protocol):
    """Produit un signal transversal ou temporel à partir de caractéristiques.

    Un signal n'est pas un portefeuille et n'a pas d'unité de position : c'est
    une prévision ordonnée. La conversion en poids appartient au
    :class:`PortfolioOptimizer`.
    """

    name: str

    def predict(self, features: pd.DataFrame) -> pd.Series:
        """Rend un score par actif, à une date donnée ou pour un panel."""
        ...


@runtime_checkable
class RiskModel(Protocol):
    """Estime la matrice de covariance des rendements servant à l'optimisation."""

    def covariance(self, returns: ReturnFrame) -> pd.DataFrame: ...


@runtime_checkable
class CostModel(Protocol):
    r"""Chiffre le coût d'un passage d'un portefeuille à un autre.

    Le coût se décompose et chaque terme est activable séparément :

    .. math::

        C = Commission + Spread + Slippage + Impact + Borrow + Financing
    """

    def cost(self, *, previous: Weights, target: Weights, context: pd.DataFrame) -> float: ...


@runtime_checkable
class PortfolioOptimizer(Protocol):
    r"""Transforme un alpha attendu et un modèle de risque en poids cibles.

    Formulation centrale :

    .. math::

        \max_w \; \alpha^\top w
        - \\frac{\\lambda}{2} w^\\top \\Sigma w
        - \\gamma \\, C(w - w_{old})
    """

    def optimize(
        self,
        *,
        alpha: pd.Series,
        covariance: pd.DataFrame,
        previous: Weights | None = None,
    ) -> Weights: ...


@runtime_checkable
class ExecutionModel(Protocol):
    """Traduit des poids cibles en poids réellement atteints.

    Elle porte le décalage d'exécution, les contraintes de participation au
    volume et le refus de négocier ce qui n'est pas négociable.
    """

    def execute(self, *, target: Weights, context: pd.DataFrame) -> Weights: ...


@runtime_checkable
class BacktestEngine(Protocol):
    """Rejoue une suite de portefeuilles sur l'histoire et rend ses rendements."""

    name: str

    def run(self, *, weights: WeightFrame, prices: pd.DataFrame) -> ReturnSeries: ...


@runtime_checkable
class PerformanceAnalyzer(Protocol):
    """Rend le tableau de bord chiffré d'une série de rendements."""

    def analyze(self, returns: ReturnSeries, **kwargs: Any) -> dict[str, float]: ...


@runtime_checkable
class ReportGenerator(Protocol):
    """Écrit le rapport d'une expérience, figures et tableaux compris."""

    def generate(self, experiment_id: str) -> str: ...

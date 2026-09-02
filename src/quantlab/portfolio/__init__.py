"""Construction de portefeuille : un signal n'est pas un portefeuille.

Le sous-paquet transforme un alpha attendu et un modèle de risque en poids
cibles, sous contraintes, coûts compris. Il est le seul endroit du dépôt qui
importe ``skfolio``, ``cvxpy`` ou ``Riskfolio-Lib``, conformément à
l'ADR-011 : les stratégies parlent aux protocoles ``RiskModel`` et
``PortfolioOptimizer``, jamais à une bibliothèque.

``covariance``
    Six estimateurs de la matrice de covariance, de l'empirique au débruité,
    chacun avec son contrôle indépendant, et un rapport qui les compare.

``optimizers``
    Sept optimiseurs, de l'équipondération qui sert de repère à la
    moyenne-variance avec coûts qui est la formulation centrale du laboratoire.
    Chacun porte un contrôle indépendant de la propriété qui le définit.
"""

from quantlab.portfolio import covariance, optimizers

__all__ = ["covariance", "optimizers"]

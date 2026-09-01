"""Mesurer la performance et le risque, une seule fois pour tout le dépôt.

Une métrique financière vit ici et nulle part ailleurs. La règle vient d'une
expérience : quand le ratio de Sharpe existe en quatre exemplaires, il finit par
exister en quatre versions, et personne ne sait laquelle a produit le chiffre
publié. C'est la règle 12 du ``CLAUDE.md``.

Trois conventions gouvernent le sous-paquet, et chacune est déclarée à
l'endroit où elle s'applique.

La **valeur à risque** et la **perte espérée** s'expriment en perte POSITIVE.
Le **repli depuis le sommet** s'exprime en valeurs NÉGATIVES. Les deux
conventions sont opposées, et les tests les vérifient.

Le numérateur d'un ratio s'annualise en :math:`N`, son dénominateur en
:math:`\\sqrt{N}`, et le taux sans risque se soustrait AVANT l'annualisation.

La **rotation** se mesure contre les poids dérivés, ceux vers lesquels le marché
a fait glisser le portefeuille, et non contre les poids cibles.
"""

from quantlab.analytics import (
    contributions,
    drawdown,
    ic,
    ratios,
    regression,
    returns,
    risk,
    turnover,
)

__all__ = [
    "contributions",
    "drawdown",
    "ic",
    "ratios",
    "regression",
    "returns",
    "risk",
    "turnover",
]

# La construction de portefeuille

**Implémenté le 2026-09-02**, phase 5, dans `quantlab.portfolio`.

Un signal n'est pas un portefeuille. Entre les deux se trouvent une
covariance, des contraintes, des coûts, et une fonction objectif dont chaque
terme change la réponse :

\[
\max_w \; \alpha^\top w - \frac{\lambda}{2} w^\top \Sigma w - \gamma \, C(w - w_{old})
\]

## Six estimateurs de covariance

`quantlab.portfolio.covariance` porte l'empirique, la moyenne exponentielle de
RiskMetrics, le rétrécissement de Ledoit et Wolf vers l'identité et vers la
corrélation constante, le modèle factoriel par composantes principales, et le
débruitage par Marchenko-Pastur. Chacun satisfait le protocole `RiskModel`, et
`risk_model_report` les compare : conditionnement, plus petite valeur propre,
distance à l'empirique, intensité de rétrécissement.

Aucun n'est meilleur en général. Le choix se fait hors échantillon, sur la
variance réalisée du portefeuille produit.

## Sept optimiseurs, chacun avec son contrôle

`quantlab.portfolio.optimizers` porte l'équipondération et l'inverse de
volatilité, qui sont les repères, puis la variance minimale, la parité de
risque, la diversification maximale, la parité hiérarchique et la
moyenne-variance avec coûts. Chacun expose `check`, qui recalcule par un
chemin indépendant la propriété qui le définit. Contributions égales pour la
parité de risque, conditions de premier ordre pour la variance minimale, forme
fermée pour la moyenne-variance sans contrainte.

`skfolio` est le moteur là où il convient, et il reste invisible depuis les
stratégies, conformément à [ADR-011](../architecture/adr/adr-011-skfolio-moteur-de-portefeuille.md).
La parité hiérarchique est écrite ici plutôt qu'appelée, parce que `skfolio`
calcule sa distance depuis des rendements et non depuis une covariance fournie.

## Ce que la phase 7 en a fait

L'étude `009_multi_strategy` combine les huit séries de la phase 4 avec ces
six allocations, poids réestimés chaque année sur le passé. Quatre sur six
battent la meilleure stratégie seule ; la référence déclarée à l'avance n'en
fait pas partie, et le verdict est `REJECTED`. Le détail vit dans
[Les stratégies](../strategies/index.md).

# Spécification 003 : ne négocier qu'une partie du chemin vers la cible

**Statut** : acceptée le 2026-09-04.
**Règles concernées** : 2, 3, 9, 12, 13.

## Ce que cela doit faire

Le moteur du laboratoire rééquilibre chaque mois vers la cible entière, et
paie donc toute la rotation que la cible demande. Gârleanu et Pedersen (2013) montrent qu'avec des coûts de transaction, la
position optimale ne saute pas à la cible. Elle s'en rapproche d'une fraction
fixe à chaque période, et la cible elle-même, le portefeuille visé, escompte
chaque signal par sa vitesse d'extinction. En mots simples : quand chaque pas coûte, on ne court pas vers
un point qui bouge, on marche vers là où il sera.

Le mécanisme est une fonction de `quantlab.execution` qui transforme une
suite de poids cibles en une suite de poids détenus, par une règle de
rapprochement partiel à taux déclaré. Une étude mesure ensuite ce que la
règle change au net des stratégies et à leur rotation.

## Ce que le dépôt porte déjà, et qui sera appelé plutôt que recopié

`quantlab.backtest.engine.run_backtest` et sa dérive des poids ;
`quantlab.execution.costs.LinearCostModel` ; `quantlab.analytics.turnover` ;
les séries et les poids de l'étude 001 par `monthly_inputs_from_prices` et
`tsmom_weights` ; le registre des essais et le moteur de verdict.

## Les critères d'acceptation, mesurables

1. À taux un, la règle rend la cible elle-même ; à taux nul, elle ne bouge
   jamais ; entre les deux, la rotation mesurée par `quantlab.analytics.turnover`
   décroît avec le taux. Testé sur un cas à la main de trois périodes.
2. Sur l'étude 001, le taux est choisi sur la fenêtre d'avant publication,
jamais sur le holdout, et le holdout est lu une seule fois par taux. Le
compte des essais est celui de la grille de taux.
3. La rotation annuelle et le coût annuel sont publiés pour chaque taux, et
   le ratio de Sharpe net du holdout aussi.

## Les décisions de conception, et ce qu'elles écartent

La forme retenue est celle du rapprochement partiel à taux constant, le
premier des deux principes de l'article. Le second, l'escompte des signaux
par leur vitesse d'extinction, exige d'estimer cette vitesse par signal et
n'est pas fait ici. Cela est déclaré comme un écart avec l'article, et l'étude
s'appelle donc « viser devant la cible, forme simple ». La forme fermée
complète de l'article est écartée pour cette étude parce qu'elle suppose des
coûts quadratiques et un signal autorégressif par actif, deux objets que les
huit séries ne portent pas.

## Le plan, en étapes vérifiables

1. `partial_rebalance(weights, rate)` dans `quantlab.execution`, testée à la
   main.
2. L'étude 017 sur l'étude 001 : grille de taux, choix sur l'avant
   publication, lecture du holdout, coûts de l'étude 001.
3. Si le net s'améliore, la même règle sur les stratégies dont les poids sont
   reconstructibles, dans une étude suivante.

## Hors périmètre

La forme fermée complète de l'article, et son application aux contrats à
terme sur matières premières.

# quant-research-platform

Un laboratoire de recherche quantitative en source ouverte, dont le but n'est
pas de trouver une stratégie qui gagne, mais de savoir laquelle ne gagne pas.

La question à laquelle toute cette infrastructure sert à répondre tient en une
phrase :

> Cette anomalie semble fonctionner. Est-ce réellement de l'alpha robuste,
> économiquement plausible, investissable, et suffisamment indépendant de nos
> autres sources de rendement pour mériter du capital ?

## Pourquoi ce projet existe

Un backtest flatteur ne prouve rien. Prenez mille stratégies aléatoires, et
testez-les sur trente ans de données. La meilleure affichera un ratio de Sharpe
supérieur à 2 sans porter le moindre signal. Ce n'est pas une possibilité
théorique, c'est la conséquence mécanique du maximum de mille tirages.

Tout ce que porte ce dépôt sert à distinguer un rendement d'un tirage chanceux :
données point-in-time, décompte des essais, ratio de Sharpe dégonflé,
probabilité de surapprentissage, coûts explicites, second moteur de backtest
indépendant.

## Par où commencer

| Vous voulez | Allez à |
|---|---|
| installer et faire tourner | [Installation](getting_started/installation.md) |
| comprendre l'architecture | [Architecture](architecture/index.md) |
| comprendre la méthode | [Ce qui sépare un résultat d'une coïncidence](methodology/index.md) |
| voir le parcours d'une stratégie | [Le parcours](methodology/gauntlet.md) |
| lire les formules | [Formules de référence](methodology/formules.md) |
| savoir ce que les données ne donnent pas | [Limites des données gratuites](data/free_data_limitations.md) |
| lire les articles répliqués | [Littérature](literature/index.md) |
| suivre les décisions | [ADR](architecture/adr/index.md) |

## L'état d'avancement

| Phase | Contenu | État |
|---|---|---|
| 0 | architecture, configuration, journal, intégration continue, documentation | **fait** |
| 1 | fournisseurs de données, lac, provenance, point-in-time, qualité | **fait** |
| 2 | analytique : rendements, risque, ratios, régression, IC, rotation, contributions | **fait** |
| 3 | validation : découpages, purge, embargo, CPCV, bootstrap, DSR, PBO, tests multiples | **fait** |
| 4 | réplications académiques, de TSMOM à l'arbitrage statistique | **fait**, huit études |
| 5 | moteur de portefeuille et de risque | **fait**, six estimateurs de covariance, sept optimiseurs |
| 6 | moteur de coûts et de capacité | **fait**, impact à l'échelle du capital, étude 010 |
| 7 | portefeuille multi-stratégies | **fait**, étude 009 |
| 8 | apprentissage automatique transversal | **fait**, panneau point-in-time, six méthodes, étude 011 |
| 9 | validation indépendante sous LEAN | non commencé |
| 10 | tableau de bord et rapport institutionnel | **fait**, `quant dashboard build` et `quant report` |
| 11 | recherche propre | non commencé |

## Avertissement

Rien ici n'est un conseil en investissement. Les résultats présentés sont des
mesures faites sur des données historiques, avec des hypothèses déclarées, et un
résultat historique ne dit rien de l'avenir. Les limites des données utilisées
sont écrites et ne sont jamais contournées par une approximation.

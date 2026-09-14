# 007 Un retour à la moyenne paie-t-il les échanges nécessaires ?

L'arbitrage statistique cherche des écarts temporaires entre une action et les mouvements communs de son univers.
Il achète un écart jugé trop bas et vend un écart jugé trop haut.
Le mot arbitrage ne signifie pas ici un gain certain sans risque.

## Un exemple fictif

Une action baisse de 3 % alors que son groupe comparable baisse de 1 %.
Son écart relatif vaut moins deux points de pourcentage.
Une règle de retour à la moyenne peut acheter cet écart en couvrant une partie du mouvement commun.

L'écart peut toutefois refléter une mauvaise nouvelle durable.
La convergence attendue reste une hypothèse, et les échanges ont un coût même lorsqu'elle ne se réalise pas.

## La méthode de référence

Avellaneda et Lee extraient des mouvements communs, puis modélisent les écarts résiduels.
La [fiche de l'article](repo:docs/literature/avellaneda_lee_2010.md) explique les composantes principales et la règle de retour à la moyenne.
Le laboratoire précise notamment si la couverture exige de négocier les titres sous-jacents.

Cette convention change la rotation et doit accompagner la comparaison.

## Le chiffre qui aide à décider

Le seuil de coût qui annule le rendement brut vaut {{s007_cost}} points de base par unité négociée sur l'historique de la reconstruction.
La période de comparaison avec l'article, de 1997 à 2007, donne un Sharpe brut de {{s007_gross}}.
Ces deux mesures portent sur des fenêtres différentes.

Un beau Sharpe brut ne suffit donc pas à payer les positions.
Les variantes de couverture déplacent le seuil de coût, sans dépasser les cinq points de base retenus dans l'article.

## Ce qui limite la portée du résultat

Les titres sont sélectionnés parmi ceux encore disponibles.
Cette sélection empêche de présenter la reconstruction comme un univers historique complet.
Le résultat net après publication reste défavorable dans les conventions étudiées.

L'[étude 010](repo:docs/etudes/010_capacity.md) ajoute ensuite les contraintes de taille.

## Vérifier le résultat

Les [mesures enregistrées](repo:studies/007_statistical_arbitrage/results/metrics.json) donnent les nombres et leurs fenêtres.
L'[annexe technique](repo:studies/007_statistical_arbitrage/ANNEXE_TECHNIQUE.md) conserve les tableaux, les hypothèses, les limites et les commandes de calcul.
Le [script de l'étude](repo:studies/007_statistical_arbitrage/run.py) relie ces choix aux fonctions du laboratoire.

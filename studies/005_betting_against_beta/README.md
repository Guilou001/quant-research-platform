# 005 Le choix d'un bêta peut changer tout un portefeuille

Le **bêta** mesure la sensibilité d'un placement aux mouvements du marché dans un modèle linéaire.
Une stratégie dite « contre le bêta » achète des titres de faible sensibilité et vend des titres de forte sensibilité.
Elle ajuste leurs tailles pour comparer les deux groupes à risque de marché estimé comparable.

## Un exemple fictif

Une position dont le bêta est estimé à 0,5 reçoit un multiplicateur de deux pour viser une exposition de marché égale à un.
Si l'estimation retenue devient 0,8, le multiplicateur descend à 1,25.
Le choix de l'estimateur modifie donc directement le montant investi.

La **réduction vers une valeur de référence** rapproche une estimation incertaine d'un repère.
Elle peut stabiliser les estimations, mais elle change aussi les poids.

## Le lien avec Frazzini et Pedersen

Leur article relie cette stratégie aux contraintes qui limitent l'emprunt de certains investisseurs.
La [fiche de littérature](../../docs/literature/frazzini_pedersen_2014_bab.md) distingue cette explication des critiques portant sur la construction du facteur.
Les cibles proviennent d'une version de travail, pas d'une lecture intégrale de la version publiée.

Le laboratoire compare la série AQR à des reconstructions sur déciles et sur titres.

## Une sensibilité mesurée

Sur les titres, de janvier 2001 à juin 2026, le Sharpe passe de 0,394 sans réduction du bêta à -0,001 avec la réduction de référence.
Ces comparaisons de construction précèdent la grille complète des coûts.

Le facteur publié et le facteur reconstruit ne donnent donc pas la même conclusion.
Ce résultat montre une dépendance importante au réglage de l'estimateur.
Il ne démontre pas que toute réduction statistique est mauvaise.

## Comment lire le verdict

Le rejet porte sur les critères du portefeuille construit dans l'étude.
Il ne réfute pas toute la théorie des contraintes d'emprunt.
La [discussion sur l'estimation du risque](../../docs/literature/ledoit_wolf_2004.md) explique pourquoi stabiliser une estimation exige une comparaison adaptée.

## Vérifier le résultat

Les [mesures enregistrées](results/metrics.json) donnent les nombres et leurs fenêtres.
L'[annexe technique](ANNEXE_TECHNIQUE.md) conserve les tableaux, les hypothèses, les limites et les commandes de calcul.
Le [script de l'étude](run.py) relie ces choix aux fonctions du laboratoire.

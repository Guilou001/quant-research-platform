# 010 Combien de capital une stratégie peut-elle accueillir ?

Une stratégie peut être facile à exécuter avec une petite somme et devenir difficile avec un gros ordre.
L'étude estime la taille compatible avec des hypothèses de coût et de participation au volume.
Les résultats sont modélisés, faute d'observations d'exécution permettant de calibrer tous les paramètres.

## Un exemple fictif

Un fonds échange pour un million de dollars dans une journée.
Un ordre de 100 000 dollars représente 10 % de ce volume.
Un ordre de 500 000 dollars en représente 50 %.

Fixer un plafond de participation à 10 % limite donc le premier ordre à 100 000 dollars dans cet exemple.
Cela ne garantit pas qu'il pourra s'exécuter sans déplacer le prix.

## Ce que l'étude peut calculer

Le suivi de tendance sur fonds cotés et l'arbitrage statistique disposent de positions et de volumes.
Les six autres composantes sont principalement des séries de facteurs publiés.
Leur capacité ne peut pas être calculée de la même façon sans les positions détaillées.

Le [contexte d'exécution](../literature/almgren_chriss_2001.md) explique pourquoi taille, calendrier et impact sont liés.
Cette étude n'est pas une réplication complète de ce modèle.

## Le résultat principal

Pour le suivi de tendance, sur janvier 2007 à juin 2026, la contrainte de participation retient environ 84 940 dollars de capital.
La valeur est beaucoup plus faible que certaines tailles de la grille illustrative.
Elle correspond à la contrainte imposée aux rééquilibrages et aux volumes du jeu de données.

Ce nombre n'est pas une capacité commerciale mesurée.
Changer le nombre de jours d'exécution, le plafond ou l'univers modifierait l'estimation.

## Une limite peut intervenir avant une autre

L'arbitrage statistique ne couvre déjà pas les frais de base dans la convention retenue.
Ajouter l'impact ne peut pas rétablir sa rentabilité.
Pour le suivi de tendance, la participation limite la taille avant certains seuils d'annulation par l'impact.

La comparaison enseigne donc quel obstacle devient contraignant dans le modèle, avec ses hypothèses.

## Vérifier le résultat

Les [mesures enregistrées](https://github.com/Guilou001/quant-research-platform/blob/main/studies/010_capacity/results/metrics.json) donnent les nombres et leurs fenêtres.
L'[annexe technique](https://github.com/Guilou001/quant-research-platform/blob/main/studies/010_capacity/ANNEXE_TECHNIQUE.md) conserve les tableaux, les hypothèses, les limites et les commandes de calcul.
Le [script de l'étude](https://github.com/Guilou001/quant-research-platform/blob/main/studies/010_capacity/run.py) relie ces choix aux fonctions du laboratoire.

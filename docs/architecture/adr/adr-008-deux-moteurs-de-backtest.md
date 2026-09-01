# ADR-008 : deux moteurs de backtest indépendants, et la réconciliation est un livrable

**Statut** : acceptée le 2026-09-01. Mise en œuvre prévue en phases 4 et 9.

## Contexte

Un backtest vectorisé est rapide et approximatif. Il suppose que l'ordre est
exécuté au prix retenu, ignore l'ordre d'arrivée des événements, et traite le
rééquilibrage comme une opération instantanée. Ces approximations sont
acceptables pour explorer, et trompeuses pour conclure.

Un moteur événementiel est lent et réaliste. Il modélise l'arrivée des barres,
les ordres, les exécutions partielles, les frais du courtier et les actions de
société.

Le risque de n'en avoir qu'un est différent selon lequel. Avec le seul moteur
vectorisé, on publie des résultats qu'aucune exécution ne reproduirait. Avec le
seul moteur événementiel, on explore si lentement qu'on n'explore pas.

## Décision

Trois moteurs, avec des rôles distincts et un ordre imposé.

1. **Le moteur du laboratoire**, écrit ici, sur poids et rendements. Il est la
   référence pour les études de facteurs, où la notion d'ordre n'a pas de sens.
2. **VectorBT**, pour les balayages de paramètres et les cartes de robustesse.
3. **LEAN**, en réimplémentation indépendante des stratégies retenues.

Une stratégie ne devient candidate au portefeuille qu'après être passée par une
implémentation indépendante sous LEAN, écrite sans recopier le code du
laboratoire.

Les deux résultats n'ont pas à coïncider au centième. Les écarts doivent être
**expliqués**, et l'explication est un livrable : un rapport de réconciliation
qui compare les horodatages, les exécutions, les prix, les coûts, les actions de
société, les dates de rééquilibrage et les calendriers.

## Conséquences

Le coût est doublé sur les stratégies retenues, et il ne l'est que sur elles.
Une stratégie rejetée à l'étape de robustesse ne coûte jamais une
réimplémentation.

Un écart inexpliqué entre les deux moteurs bloque le verdict. C'est voulu : un
écart qu'on ne sait pas expliquer est un bogue qu'on n'a pas trouvé, dans l'un
des deux.

## Options écartées

**Un seul moteur, le nôtre.** Rejetée parce qu'un moteur écrit par la même
personne que la stratégie partage ses angles morts. Le contrôle indépendant vaut
précisément par son indépendance.

**LEAN dès le début.** Rejetée pour la vitesse : une carte de robustesse sur
deux paramètres et vingt valeurs demande quatre cents backtests, ce qui reste
possible en vectorisé et devient un obstacle en événementiel.

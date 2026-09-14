# Ce qui sépare une observation d'une conclusion

Un bon résultat historique constitue une observation à expliquer.
Sa force dépend du protocole, des données et du nombre de choix effectués.
Le laboratoire conserve ces éléments pour que le lecteur puisse les vérifier.

## Commencer par une explication testable

Une règle peut rémunérer un risque, exploiter une erreur de prix ou répondre à une contrainte.
Ces mécanismes sont des hypothèses.
Une expérience doit préciser quelles observations les soutiendraient et lesquelles les affaibliraient.

Le [premier chapitre](../guide/01_question.md) donne des exemples.
Une comparaison avant et après publication peut décrire une évolution, sans isoler la publication comme cause.

## Respecter la chronologie

L'information doit être disponible avant la décision.
Les périodes d'apprentissage, de choix des paramètres et d'évaluation ont des rôles distincts.
Une séparation supplémentaire peut être nécessaire lorsque les rendements prévus chevauchent les frontières.

Les [données datées](../data/point_in_time.md) et le [calendrier du test](../guide/03_calendrier.md) expliquent ces précautions.
Un découpage correct ne répare pas un univers incomplet.

## Compter les choix et mesurer l'incertitude

Le meilleur résultat parmi de nombreux essais bénéficie d'une sélection.
Son niveau dépend du nombre d'essais, de leur dépendance, de la durée et de la distribution des rendements.
Aucune règle générale ne garantit un Sharpe supérieur à deux pour mille stratégies aléatoires testées pendant trente ans.

Le [chapitre sur le hasard](../guide/04_hasard.md) propose une simulation aux hypothèses explicites.
Le DSR et la PBO apportent des diagnostics complémentaires, avec leurs propres hypothèses.
Le DSR n'est pas un Sharpe diminué ni une probabilité de profit futur.

Une différence entre stratégies demande aussi une mesure d'incertitude.
Le rééchantillonnage par blocs peut conserver une partie de la dépendance des mois voisins.
Il doit employer les mêmes dates pour les stratégies comparées.

## Passer de la prévision à la décision

La précision des prévisions, la qualité du classement et le résultat du portefeuille ne sont pas interchangeables.
L'[étude 011](../etudes/011_cross_sectional_ml.md) montre leur divergence.

La performance dépend ensuite des poids, des risques communs et des frais.
Ces éléments ne forment pas une identité multiplicative universelle.
On calcule les flux et les coûts selon les conventions déclarées, puis on les compare à un repère pertinent.

## Formuler le verdict

Le [parcours de validation](gauntlet.md) décrit les contrôles du logiciel.
Le [chapitre de conclusion](../guide/08_conclusion.md) explique comment lire leurs résultats.

Un contrôle non calculable indique une preuve manquante.
Un contrôle calculé sous le seuil indique un critère non satisfait.
Les deux situations restent distinctes, même si le moteur utilise une catégorie commune.

Les [formules](formules.md), la [validation](../validation/index.md) et les annexes donnent les détails techniques.

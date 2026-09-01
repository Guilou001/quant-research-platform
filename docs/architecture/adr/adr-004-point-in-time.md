# ADR-004 : quatre dates par observation, et une seule gouverne l'accès

**Statut** : acceptée le 2026-09-01.

## Contexte

Une donnée fondamentale porte deux temps que rien n'oblige à distinguer, et que
tout oblige à ne pas confondre. Le premier est la période économique décrite :
le trimestre clos le 31 mars 2015. Le second est le moment où l'information est
devenue connaissable : le dépôt accepté par la SEC le 15 mai 2015.

Un backtest qui utilise le bénéfice du premier trimestre à partir du 31 mars
utilise une information que personne n'avait. L'alpha qu'il mesure est celui
d'un devin, pas d'un gérant.

Le piège est qu'aucune erreur ne se produit. Le code tourne, les colonnes sont
justes, le ratio de Sharpe est excellent, et le résultat est faux.

## Décision

Toute donnée fondamentale ou macroéconomique porte quatre dates :

| Champ | Ce qu'il dit |
|---|---|
| `period_end` | la fin de la période économique décrite |
| `filing_date` | la date du dépôt auprès du régulateur |
| `accepted_timestamp` | l'horodatage d'acceptation, quand il existe |
| `available_from` | la date à partir de laquelle nous nous autorisons à l'utiliser |

Seul `available_from` gouverne l'accès. Sa valeur par défaut est `filing_date`,
avec un décalage conservateur configurable. Elle ne vaut **jamais** `period_end`.

`PITFrame.as_of(date)` rend, pour chaque entité et chaque période, la dernière
observation dont `available_from` est antérieure ou égale à la date demandée.
Les corrections de comptes sont conservées toutes, et c'est `as_of` qui choisit
celle qui était connue.

Une construction où `available_from` précède `period_end` lève `LookAheadError`
et arrête le pipeline.

## Conséquences

Les données fondamentales entrent en retard, ce qui réduit l'alpha mesuré. C'est
l'effet recherché : la différence entre l'alpha avec et sans point-in-time est
précisément l'ampleur de la fuite.

Conserver les corrections multiplie le volume des tables par le nombre de
révisions. Le coût est réel et accepté, parce que jeter les révisions détruit la
propriété qu'on cherche à garantir.

Le test anti-fuite canonique est obligatoire dans la suite : dépôt accepté le
2015-05-15, date de portefeuille le 2015-03-31, accès refusé.

## Options écartées

**Un décalage fixe de quarante-cinq jours après la fin de trimestre.** Rejetée
parce qu'elle est fausse dans les deux sens : certains déposants publient en
trois semaines, d'autres demandent un délai. L'approximation crée de la fuite
là où le déposant est lent et jette de l'information là où il est rapide. Elle
reste disponible comme repli explicite quand la vraie date manque, et le
manifeste le déclare alors.

**Ne garder que la dernière valeur connue.** Rejetée parce qu'elle détruit
exactement la propriété recherchée.

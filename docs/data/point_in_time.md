# Le point-in-time, ou la seule règle qui ne se négocie pas

Une donnée porte deux temps. La période économique qu'elle décrit, et le moment
où elle est devenue connaissable. Les confondre suffit à fabriquer de l'alpha
qui n'existe pas.

## Le mécanisme, en une ligne du temps

```
31 mars 2015          15 mai 2015                    30 juin 2015
     │                     │                              │
     ▼                     ▼                              ▼
 fin du trimestre     dépôt du 10-Q              fin du trimestre suivant
 (period_end)         (filing_date)
                           │
                           └──► available_from : à partir d'ici,
                                et pas un jour avant
```

Un backtest qui utilise le bénéfice du premier trimestre à partir du 31 mars
utilise une information que personne n'avait le 31 mars. Il mesure l'alpha d'un
devin.

Le piège est qu'aucune erreur ne se produit. Le code tourne, les colonnes sont
justes, le ratio de Sharpe est excellent, et le résultat est faux. C'est
pourquoi la règle est structurelle et non affaire de vigilance.

## Les quatre dates

| Champ | Ce qu'il dit | Qui le fournit |
|---|---|---|
| `period_end` | fin de la période économique décrite | le champ `end` du XBRL |
| `filing_date` | date du dépôt auprès du régulateur | le champ `filed` |
| `accepted_timestamp` | horodatage d'acceptation | l'index EDGAR, quand il existe |
| `available_from` | à partir de quand nous nous autorisons à l'utiliser | **nous**, par une règle déclarée |

`available_from` vaut `filing_date` par défaut, avec un décalage conservateur
configurable. Il ne vaut **jamais** `period_end`.

## Les corrections de comptes

Le même trimestre est souvent déclaré plusieurs fois, avec des valeurs
différentes : une première publication, puis une correction. Un module qui ne
garde que la dernière valeur détruit exactement la propriété recherchée, parce
qu'il fait connaître la correction avant qu'elle existe.

`PITFrame` garde toutes les déclarations. C'est `as_of(date)` qui choisit, pour
chaque entité et chaque période, la dernière dont `available_from` précède la
date demandée.

## Le test qui doit exister

```python
# dépôt accepté le 2015-05-15, décision de portefeuille le 2015-03-31
frame.as_of("2015-03-31")  # ne contient PAS la ligne du trimestre clos ce jour
```

Ce test est obligatoire dans la suite et n'a pas le droit d'être désactivé. Il
vit dans `tests/antibias/`.

## Le côté macroéconomique

Le problème est identique et la solution s'appelle ALFRED. FRED rend la valeur
révisée d'aujourd'hui ; ALFRED rend la valeur telle qu'elle était publiée à une
date donnée.

Une règle du type « acheter quand la croissance accélère » testée sur les
données révisées voit des accélérations que personne n'a vues à l'époque, parce
que les premières estimations sont corrigées ensuite. Le laboratoire utilise
donc les millésimes ALFRED pour tout backtest macro, et le manifeste porte
`point_in_time=True` pour ALFRED et `False` pour FRED. C'est toute la différence
entre les deux sources.

## Ce que le point-in-time ne corrige pas

Il ne corrige pas le biais de survie, qui est un problème d'**univers** et non
de dates ; voir [le biais de survie](survivorship_bias.md).

Il ne corrige pas non plus le fait que nous connaissons l'histoire. Choisir
d'étudier le momentum en 2026 parce qu'il a fonctionné entre 1993 et 2026 est un
biais de sélection que nulle date de dépôt ne répare. Seul le décompte des
essais et le ratio de Sharpe dégonflé s'en approchent.

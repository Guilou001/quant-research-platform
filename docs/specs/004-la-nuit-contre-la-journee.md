# Spécification 004 : décomposer un rendement en sa part de nuit et sa part de journée

**Statut** : acceptée le 2026-09-04.
**Règles concernées** : 2, 3, 12, 13.

## Ce que cela doit faire

Un rendement de clôture à clôture se décompose en deux morceaux qui
s'ajoutent presque : de la clôture de la veille à l'ouverture, la nuit, et de
l'ouverture à la clôture, la journée. Lou, Polk et Skouras (2019) rapportent
que le momentum gagne la nuit et que la valeur gagne le jour. Le laboratoire
doit pouvoir décomposer ainsi chacune de ses séries de tête construites sur
des fonds cotés, et dire laquelle des deux parts porte le rendement.

Le mécanisme est une fonction de `quantlab.analytics.returns` qui, depuis les
prix d'ouverture et de clôture ajustés, rend les deux composantes quotidiennes,
puis une étude qui applique les poids d'une stratégie à chaque composante.

## Ce que le dépôt porte déjà, et qui sera appelé plutôt que recopié

`quantlab.data.providers.yahoo` pour les ouvertures, les clôtures et les
clôtures ajustées. L'ajustement de l'ouverture par le facteur de la clôture,
déjà écrit dans l'export LEAN. `monthly_inputs_from_prices` et
`tsmom_weights` pour les poids de l'étude 001, et `run_backtest`.

## Les critères d'acceptation, mesurables

1. Sur trois jours de prix construits à la main, la nuit et la journée
   composées redonnent le rendement de clôture à clôture à 1e-12.
2. L'ouverture ajustée vaut l'ouverture brute multipliée par le rapport de la
   clôture ajustée à la clôture brute, testé.
3. Pour l'étude 001, le rendement mensuel de la stratégie se retrouve à 1e-10
   comme somme composée de ses parts de nuit et de journée.

## Les décisions de conception, et ce qu'elles écartent

Les composantes se composent au lieu de s'additionner, ce qui rend l'identité
exacte. Les fonds cotés remplacent les actions individuelles de l'article,
parce que les séries de tête du laboratoire sont sur fonds cotés ; l'écart est
déclaré.

## Le plan, en étapes vérifiables

1. `overnight_intraday_split(open, close, adj_close)` testée à la main.
2. L'étude 018 sur l'étude 001, puis sur les fonds de facteurs de
   `benchmarks/funds.yaml`.

## Hors périmètre

Les actions individuelles, faute d'univers sans biais de survie ; les données
à la minute, inutiles pour cette décomposition.

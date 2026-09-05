# Spécification 007 : lire les indices de stratégie du Cboe, et empiler une exposition financée au taux court

**Statut** : acceptée le 2026-09-04.
**Règles concernées** : 2, 3, 5, 12, 13.

## Ce que cela doit faire

Deux briques manquent à l'étude 021, le portefeuille de primes pré-inscrit.
La première lit la prime de volatilité. Le Cboe publie chaque jour le niveau
de ses indices de vente de puts et d'achat-vente d'options, en un fichier CSV
par indice : PUT, WPUT, BXM, BXMD et CLL, plus le VIX. Mesuré le 2026-09-04 : le fichier de PUT compte 4 957 lignes depuis le
1991-03-04, mais sept points isolés avant le 2007-01-03, puis une ligne par
séance. Un rendement calculé à travers un trou de plusieurs années est faux,
et le fournisseur sait ne garder que le segment continu. Le fournisseur rend, pour un
indice, une table datée de niveaux, et son manifeste.

La seconde brique est l'empilement. Elle tient une exposition variable à un
portefeuille, réglée sur sa volatilité passée et plafonnée. La part au-delà
d'un dollar est financée au taux court plus un écart. Le module rend le
rendement net de ce financement et du coût de chaque changement d'exposition.

En mots simples : la première brique télécharge ce que rapporte la vente
d'assurance sur le S&P 500. La seconde dit ce que coûte de tenir un dollar
et demi de portefeuille avec un dollar de capital.

## Ce que le dépôt porte déjà, et qui sera appelé plutôt que recopié

`BaseProvider` et son cache brut, et le manifeste `DatasetManifest`. Le
passage des niveaux aux rendements par `quantlab.analytics.returns.to_returns`
et `resample_returns`. Le ratio de Sharpe de `quantlab.analytics.ratios`, la
rotation et les coûts linéaires de `quantlab.execution.costs`. Le moteur
`run_backtest` et les optimiseurs à règle de `quantlab.portfolio.optimizers`.
Le taux sans risque vient du fichier des facteurs de Kenneth French, déjà lu
par les études 001 et 002.

## Les critères d'acceptation, mesurables

1. `parse_history_csv` lit un extrait écrit à la main de quatre lignes en
   dates du mois, du jour et de l'année, rend des dates triées et des niveaux
   flottants, et lève `DataQualityError` si la colonne de l'indice manque ou
   si une date se répète.
2. Le manifeste d'une lecture porte la licence du Cboe, usage personnel et
   non commercial, la première et la dernière date lues, et la fréquence
   quotidienne.
3. Le rendement mensuel de PUT, lu sur le segment continu du fichier réel,
   commence le 2007-01-03 et a sur 2007-2018 une volatilité annualisée entre
   9 % et 13 %, la valeur publiée par le Cboe et Wilshire pour 1986-2018
   étant 9,9 %. Test réseau, écarté de `make test`.
4. Une exposition constante à un et sans coût rend le rendement d'origine à
   1e-12 près.
5. Un exemple à la main : exposition 1,5, rendement du mois -1 %, écart de
   financement 0,6 % par an, rend -1,525 % ; le demi-dollar emprunté coûte
   0,025 % dans le mois.
6. Sur une série de rendements alternés de +1 % et -1 %, l'exposition à
   cible de volatilité rend exactement la cible divisée par la volatilité de
   la fenêtre. Elle rend le plafond quand la cible dépasse ce qu'il permet.
7. `make test` ne fait aucun appel réseau.

## Les décisions de conception, et ce qu'elles écartent

Les niveaux du Cboe plutôt qu'une reconstruction par Black-Scholes au VIX.
Le dépôt 16 du portefeuille a fait cette reconstruction et l'a trouvée trop
riche de 523 points de base par an, le prix du skew. L'indice officiel porte
les prix réellement négociés. Le fichier CSV public plutôt que la boutique de
données du Cboe, payante. Les rendements en excédent du taux sans risque dans tout le module
d'empilement, ce qui rend le taux court lui-même neutre et ne laisse que
l'écart de financement. C'est la convention des fonds à parité de risque et
de Hurst, Ooi et Pedersen. L'exposition est décidée avec
l'information de la période précédente et appliquée à la suivante, jamais le
même mois, règle 1.

## Le plan, en étapes vérifiables

1. `quantlab.data.providers.cboe`, avec `parse_history_csv`, `daily_segment`,
   `CboeIndexProvider.history` et le manifeste ; les critères 1, 2 et 7.
2. `quantlab.execution.leverage`, avec `volatility_target_exposure` et
   `apply_leverage` ; les critères 4, 5 et 6.
3. Le test réseau du critère 3, marqué `network`.
4. L'étude 021, dont le `config.yaml` est la spécification de recherche,
   ADR-016, et dont tous les seuils sont écrits avant le premier chiffre.

## Hors périmètre

Les options individuelles et leur surface de volatilité, qu'aucune source
libre ne donne. Le financement réel d'un compte sur marge, dont le taux
dépasse le taux court de bien plus que l'écart modélisé, déclaré dans
l'étude. Tout conseil de placement : l'étude rend un verdict, pas une
recommandation.

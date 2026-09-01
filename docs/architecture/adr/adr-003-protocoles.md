# ADR-003 : les briques se parlent par protocoles structurels

**Statut** : acceptée le 2026-09-01.

## Contexte

Une stratégie qui appelle `yfinance.download` est une stratégie qu'on ne peut
plus faire tourner sur une autre source, ni tester sans réseau, ni rejouer à
l'identique dans deux ans. Le couplage à un fournisseur décide de ce qui restera
reproductible.

Le problème se pose de la même façon pour l'optimiseur, le modèle de coût et le
moteur de backtest. Un jour, `YahooProvider` deviendra un fournisseur
professionnel, et ce jour-là il ne faudra pas réécrire les stratégies.

## Décision

Les frontières sont déclarées avec `typing.Protocol` et `runtime_checkable`,
dans `quantlab.core.protocols`. Onze protocoles sont posés : `DataProvider`,
`PointInTimeDataset`, `FeatureTransformer`, `AlphaModel`, `RiskModel`,
`CostModel`, `PortfolioOptimizer`, `ExecutionModel`, `BacktestEngine`,
`PerformanceAnalyzer`, `ReportGenerator`.

Le typage est **structurel** : une classe satisfait un protocole en portant les
bonnes méthodes, sans hériter de rien. C'est la composition plutôt que
l'héritage, et cela permet à une classe d'une bibliothèque tierce de satisfaire
notre protocole sans que nous la modifiions.

## Conséquences

Une brique se remplace sans toucher à ses appelants. Les tests d'une stratégie
tournent contre un fournisseur factice, hors réseau, en une fraction de seconde.

Le coût est la discipline : un protocole ne sert à rien si le code importe
quand même la classe concrète. La vérification est mécanique et sera testée,
aucun module de `strategies/` ne devant importer de module de `providers/`.

## Options écartées

**Classes de base abstraites.** Rejetées pour la rigidité : elles imposent
l'héritage, donc empêchent une classe tierce de satisfaire l'interface. Elles
restent utilisées là où du code est réellement partagé, comme `BaseProvider`,
qui porte le client HTTP et le cache brut.

**Injection de dépendances par conteneur.** Rejetée pour le poids : un
conteneur d'injection résout un problème que ce projet n'a pas, celui du
câblage de dizaines de services au démarrage. Passer les dépendances en
arguments suffit et se lit mieux.

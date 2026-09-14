# 009 Huit stratégies différentes font-elles un meilleur portefeuille ?

Le portefeuille rassemble les huit premières stratégies.
Il compare plusieurs allocations, dont une référence choisie avant de lire les performances.
La question porte sur l'amélioration du mélange relativement aux composantes, avec leurs données et leurs limites.

## Un exemple fictif

Deux stratégies gagnent en moyenne autant.
Si elles perdent exactement les mêmes mois, les combiner protège peu.
Si leurs fluctuations se compensent en partie, le risque du mélange peut diminuer.

Cette intuition ne garantit pas qu'une allocation estimée battra une règle simple.
Les corrélations et les volatilités doivent être estimées, puis converties en positions.

## Le contexte de recherche

La [loi fondamentale](repo:docs/literature/grinold_1989.md) relie la qualité des prévisions à la diversité effective des paris, sous des hypothèses.
[DeMiguel et coauteurs](repo:docs/literature/demiguel_garlappi_uppal_2009.md) motivent la comparaison avec une allocation à parts égales.
L'[étude 003](repo:docs/etudes/003_value_and_momentum.md) fournit un exemple de diversification observée.

## Lire les fenêtres séparément

La référence en parité de risque présente un Sharpe de {{s009_before}} avant la période finale et de {{s009_after}} sur les 78 mois de janvier 2020 à juin 2026.
Le portefeuille s'appuie sur des séries de stratégies brutes.
Les coûts de réallocation ne remplacent pas les frais nécessaires à construire chaque composante.

Une autre allocation paraît meilleure dans certaines comparaisons.
La désigner comme nouvelle référence après avoir vu son résultat constituerait un nouveau choix guidé par les données.

## Ce que le rejet signifie

La référence ne satisfait pas le critère de supériorité fixé dans cette étude.
La conclusion ne dit pas que diversifier est inutile.
Elle dit que ce mélange et cette règle n'ont pas apporté la preuve demandée.

L'[étude 012](repo:docs/etudes/012_multi_strategy_net.md) reprend la comparaison avec les coûts propres aux composantes.
Elle permet de voir ce que la lecture des seules séries brutes masquait.

## Vérifier le résultat

Les [mesures enregistrées](repo:studies/009_multi_strategy/results/metrics.json) donnent les nombres et leurs fenêtres.
L'[annexe technique](repo:studies/009_multi_strategy/ANNEXE_TECHNIQUE.md) conserve les tableaux, les hypothèses, les limites et les commandes de calcul.
Le [script de l'étude](repo:studies/009_multi_strategy/run.py) relie ces choix aux fonctions du laboratoire.

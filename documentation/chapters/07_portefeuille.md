# 07 Comprendre ce que la diversification apporte

Deux stratégies peuvent perdre à des moments différents.
Leur mélange peut alors réduire les fluctuations du portefeuille.
La diversification dépend de ces mouvements communs, autant que du rendement moyen de chaque stratégie.

La **corrélation** résume une association linéaire.
Une corrélation faible ne garantit pas une indépendance complète.
Deux stratégies peuvent notamment partager des pertes lors d'événements rares.

## Deux périodes fictives

La stratégie A gagne 10 %, puis perd 10 %.
La stratégie B perd 2 %, puis gagne 8 %.
Un portefeuille remis à parts égales avant chaque période gagne 4 %, puis perd 1 %.

Sur 100 dollars initiaux, A termine à 99 dollars et B à 105,84 dollars.
Le mélange termine à 102,96 dollars.
Il fluctue moins dans cet exemple, sans battre le capital final de B.

L'exemple montre aussi la composition des rendements.
Gagner 10 %, puis perdre 10 %, ne ramène pas au point de départ.
La perte de la seconde période s'applique aux 110 dollars obtenus après la première.

## Ce que les données du laboratoire montrent

L'[étude 003](repo:docs/etudes/003_value_and_momentum.md) observe une corrélation négative entre valeur et momentum.
Leur association historique améliore le rapport entre rendement moyen et dispersion.
Les dates utilisées pour calculer les signaux influencent toutefois cette relation.

L'[étude 009](repo:docs/etudes/009_multi_strategy.md) compare plusieurs règles d'allocation sur des séries brutes.
L'[étude 012](repo:docs/etudes/012_multi_strategy_net.md) reprend l'exercice après les coûts propres aux stratégies.
Les conclusions financières changent parce que les séries à combiner ont changé.

## Trois choix qui ne disent pas la même chose

Une allocation à parts égales répartit le capital également.
Une allocation inversement proportionnelle à la volatilité réduit le poids des stratégies qui fluctuent davantage.
Une allocation fondée sur les contributions au risque tient aussi compte de leurs mouvements communs.

Ces règles exigent des estimations différentes.
Une estimation de risque instable peut produire des poids instables et davantage de frais.
Le repère simple aide à mesurer si cette complexité apporte assez.

## Choisir la comparaison avant le résultat

L'[étude 021](repo:docs/etudes/021_portefeuille_de_primes.md) demande au mélange de dépasser sa meilleure composante selon un critère fixé.
Le portefeuille ne satisfait pas ce critère sur la période complète.
Son intérêt éventuel pour un investisseur ayant d'autres contraintes reste une question distincte.

Les références [Markowitz](repo:docs/literature/markowitz_1952.md), [DeMiguel et coauteurs](repo:docs/literature/demiguel_garlappi_uppal_2009.md) et [Ledoit et Wolf](repo:docs/literature/ledoit_wolf_2004.md) expliquent les choix de risque et d'estimation.
Le [dernier chapitre](repo:docs/guide/08_conclusion.md) aide à formuler ce que les preuves autorisent.

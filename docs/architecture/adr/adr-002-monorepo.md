# ADR-002 : un dépôt unique, des études autonomes à l'intérieur

**Statut** : acceptée le 2026-09-01.

## Contexte

Le portefeuille de projets existant compte trente-huit dépôts indépendants, un
par sujet, et cette organisation lui a bien servi : chaque dépôt se lit seul et
répond à une offre d'emploi précise.

Elle ne convient pas ici. Quinze réplications académiques indépendantes
produiraient quinze pipelines de données, quinze implémentations du ratio de
Sharpe, quinze conventions de rotation, et aucune possibilité de combiner les
alphas obtenus. Le jour où la question devient « cette stratégie apporte-t-elle
quelque chose au portefeuille existant ? », il faudrait tout réconcilier.

## Décision

Un dépôt unique porte le code partagé dans `src/quantlab/`, et chaque
réplication vit dans `studies/NNN_nom/` avec son propre README, sa
configuration, son rapport et son verdict.

Une étude est autonome à la lecture et dépendante au calcul. Elle se lit sans
connaître les autres ; elle appelle le ratio de Sharpe du paquet partagé, jamais
le sien.

Si une étude devient exceptionnellement propre, elle pourra être extraite dans
un dépôt vitrine, mais la source de vérité restera ici.

## Conséquences

Une correction dans une métrique corrige toutes les études d'un coup, ce qui est
l'effet recherché et aussi le risque : un changement de convention change tous
les résultats publiés. La parade est la règle 2 du `CLAUDE.md`, qui exige de
modifier la docstring, le test et le journal de recherche dans le même commit,
et les tests de régression qui gèlent des résultats connus.

L'intégration continue tourne sur tout le dépôt à chaque modification, ce qui
coûte plus cher qu'un dépôt par étude. Le compromis est accepté tant que la
suite reste sous quelques minutes.

## Options écartées

**Quinze dépôts indépendants.** Rejetée pour les cinq raisons ci-dessus, dont la
plus grave est l'impossibilité de calculer la matrice de covariance des
rendements de stratégies, qui est le but final du projet.

**Un dépôt de bibliothèque plus des dépôts d'étude.** Rejetée pour le coût de
publication : chaque changement de la bibliothèque exigerait une version, une
publication et une mise à jour dans chaque étude. Le portefeuille a déjà fait
ce choix avec `gv-fintools`, et c'est justifié là où les dépôts sont vraiment
indépendants. Ici les études partagent leurs données et leurs verdicts.

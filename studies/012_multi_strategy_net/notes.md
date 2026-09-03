# Notes de l'étude 012

## Ce qui a été décidé avant de voir un chiffre

Tout est celui de l'étude 009 : référence à la parité de risque, holdout au
2020-01-31, seuils du verdict, vingt essais. Seule la table des séries change,
et le choix de chaque série est écrit dans le README avant l'exécution.

## Ce qui a surpris

Rien dans les corrélations, tout dans les signes. La corrélation moyenne vaut
0,093 contre 0,095 et la largeur effective 5,48 contre 5,37 : le passage au net
ne touche pas la structure de dépendance. Mais trois séries sur huit sont
négatives nettes, et l'arbitrage statistique, à -0,932, retire 0,379 de Sharpe
à la parité de risque là où il en apportait 0,250 en brut.

La parité de risque fait pire que la variance minimale et que la
moyenne-variance. C'est attendu quand des paris ont une espérance négative :
allouer par le risque seul leur donne du poids, et seule une allocation qui
regarde aussi la moyenne les évite. Cela ne réhabilite pas la moyenne-variance,
dont le Sharpe de 0,250 reste sous la meilleure jambe.

## Les essais ratés

Aucun. Le script de l'étude 009 a tourné du premier coup sur la nouvelle
table ; l'étude 008 venait d'être corrigée et sa série nette portait son avril
2020.

## Ce qui reste ouvert

Les deux séries brutes faute de version nette, la qualité et la gestion de
volatilité, gardent un avantage qu'elles n'auraient pas ; leur chiffrer un
coût demanderait les poids par titre du facteur publié, que personne ne
publie. Et l'étude 009 devrait, à terme, s'effacer devant celle-ci dans les
comparaisons aux fonds réels : un fonds est net, et un portefeuille qui ne
l'est pas ne se compare pas à lui.

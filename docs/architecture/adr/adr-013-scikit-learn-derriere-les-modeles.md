# ADR-013 : scikit-learn est le moteur d'apprentissage, derrière le protocole AlphaModel

**Statut** : acceptée le 2026-09-02, phase 8.

## Contexte

La phase 8 compare des méthodes d'apprentissage transversal, du linéaire
pénalisé aux ensembles d'arbres, sur un même panneau et un même découpage,
comme Gu, Kelly et Xiu (2020). Écrire ces estimateurs soi-même n'apprendrait
rien et produirait des bogues que `scikit-learn` a corrigés depuis dix ans.
Mais laisser `scikit-learn` entrer dans les stratégies rendrait chaque étude
dépendante d'une API tierce, ce que l'ADR-011 a déjà refusé pour `skfolio`.

Trois questions se posaient. Où vit la bibliothèque. Comment les
hyperparamètres se règlent sans lire le bloc de test. Et comment les
caractéristiques se mettent à l'échelle sans lire les dates futures.

## Décision

`scikit-learn` n'est importé que dans `quantlab.models` et dans
`quantlab.portfolio`, et le test d'architecture ajoute son nom à la liste des
moteurs interdits ailleurs. Chaque méthode est une spécification nommée, avec
sa famille et sa grille d'hyperparamètres déclarée dans la configuration de
l'étude. Le modèle ajusté satisfait le protocole `AlphaModel` par un nom et une
méthode `predict`, et rien d'autre du paquet ne sait qu'il y a un estimateur
derrière.

Les hyperparamètres se choisissent sur les dernières dates de la fenêtre
d'entraînement, séparées de l'ajustement par la même purge que le test. Le
modèle retenu est ensuite réajusté sur tout l'entraînement, puis prévoit le
bloc de test. Le bloc de test n'est jamais consulté, et une vérification d'ordre
des dates lève une erreur si un pli l'enfreignait.

Les caractéristiques se mettent à l'échelle par leur rang transversal à chaque
date, dans l'intervalle de moins un à plus un, un manquant valant zéro. Cette
transformation n'emploie que la date courante, donc aucune date future.
L'étiquette est le rendement en excès du mois suivant, construite par un
décalage explicite d'une seule fonction, et son nom porte le préfixe qui
signale l'information future.

## Conséquences

Une méthode nouvelle s'ajoute par une fabrique et une entrée de grille, sans
toucher à l'analyse glissante ni à l'évaluation. Le compte des configurations
entre dans les essais déclarés, donc dans le ratio de Sharpe dégonflé.

Le prix est un réajustement sur tout l'entraînement après validation, qui
s'écarte de l'article, et une validation courte, deux ans, donc bruitée. Les
deux sont déclarés dans l'étude 011.

Les réseaux de neurones de l'article ne sont pas dans la grille de l'étude
011. La fabrique existe, mais cinq réseaux à régulariser sur onze ans de
données ne changeraient pas la conclusion et multiplieraient les essais.

## Options écartées

**Écrire les estimateurs.** Rejetée pour la même raison qu'en ADR-011.

**Régler les hyperparamètres par validation croisée à l'intérieur de
l'entraînement.** Rejetée pour cette phase : plus stable, mais plus coûteuse,
et l'article valide sur une fenêtre finale unique.

**Standardiser par z-score transversal.** Rejetée parce qu'une seule société
aberrante écrase les autres, et parce que l'article emploie les rangs.

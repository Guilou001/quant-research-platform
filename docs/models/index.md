# L'apprentissage transversal

**Implémenté le 2026-09-02**, phase 8 de la feuille de route. Trois modules
dans `quantlab.models`, et une étude, la 011, qui les applique au panneau
point-in-time de l'étude 004.

## Le panneau : une ligne par couple (date, titre), rangée à la date

Les caractéristiques d'un titre à une date se comparent aux autres titres de
la même date, par leur rang, dans l'intervalle de moins un à plus un. Un
manquant vaut zéro, la médiane de cette échelle. L'étiquette est le rendement
en excès du mois suivant, construite par un décalage explicite, et son nom
porte le préfixe `label_`. Six caractéristiques de prix se calculent depuis les
rendements mensuels, et un test vérifie que perturber l'avenir ne change pas le
passé.

\[
\tilde c_{i,t} = 2\,\frac{\operatorname{rang}(c_{i,t}) - 1}{n_t - 1} - 1
\qquad
y_{i,t} = r_{i,t+1} - r^{f}_{t+1}
\]

## Les modèles : une spécification, une grille, une analyse glissante

Huit fabriques, du linéaire aux arbres et au perceptron, enveloppent
`scikit-learn` derrière le protocole `AlphaModel`. À chaque pli, les dates
d'entraînement précèdent les dates de test, une purge d'un mois les sépare, et
la configuration se choisit sur les vingt-quatre derniers mois de
l'entraînement. Le bloc de test n'est jamais consulté, et une erreur se lève
si un pli l'enfreint. La décision est l'[ADR-013](../architecture/adr/adr-013-scikit-learn-derriere-les-modeles.md).

## L'évaluation : un R² qui peut être négatif, et un test qui compte l'autocorrélation

\[
R^2_{oos} = 1 - \frac{\sum_{i,t}(r_{i,t+1} - \hat r_{i,t+1})^2}{\sum_{i,t} r_{i,t+1}^2}
\]

Le dénominateur ne centre pas : prévoir zéro rend zéro, et prévoir plus mal
que zéro rend un nombre négatif. La régression complète de Gu, Kelly et Xiu
(2020) le fait, à moins 3,46 %. Deux modèles se comparent par le test de
Diebold et Mariano sur les pertes moyennées par date, avec un écart type
corrigé à la Newey-West, ce qu'un test confronte au t HAC de `statsmodels`.
L'importance d'une variable se mesure par permutation hors échantillon.

## Ce que la phase ne fait pas

Vingt-sept caractéristiques contre quatre-vingt-quatorze dans l'article, et
onze ans de données contre soixante. Pas de réseau de neurones dans la grille
de l'étude, pas de produit croisé avec des variables macroéconomiques. Le
réajustement sur tout l'entraînement après validation s'écarte de l'article,
et c'est déclaré.

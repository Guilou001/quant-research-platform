# La construction de portefeuille

**Non implémenté au 2026-09-01.** C'est la phase 5 de la feuille de route.

Un signal n'est pas un portefeuille. La phase 5 apporte la chaîne qui les
sépare : alpha attendu, modèle de risque, modèle de coût, contraintes,
optimiseur, portefeuille cible.

La formulation centrale est écrite dans
[Formules de référence](../methodology/formules.md) :

\[
\max_w \; \alpha^\top w - \frac{\lambda}{2} w^\top \Sigma w - \gamma \, C(w - w_{old})
\]

Deux repères obligatoires encadreront toute comparaison d'optimiseurs :
l'équipondération et l'inverse de la volatilité. DeMiguel, Garlappi et Uppal
(2009) montrent que le premier est beaucoup plus difficile à battre que la
théorie ne le laisse croire, et une méthode qui ne le bat pas hors échantillon
n'apporte rien.

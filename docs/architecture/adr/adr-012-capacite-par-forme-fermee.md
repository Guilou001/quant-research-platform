# ADR-012 : la capacité se mesure en rejouant les poids à plusieurs tailles, et une forme fermée contrôle le moteur

**Statut** : acceptée le 2026-09-02, phase 6.

## Contexte

Le moteur de backtest raisonne en poids, sans dollars. Le modèle d'impact en
racine carrée, écrit en phase 6 dans `quantlab.execution.costs`, raisonne en
participation, c'est-à-dire en dollars négociés rapportés aux dollars que le
marché échange. Rien ne reliait les deux : aucune étude ne pouvait dire à
quelle taille de capital son alpha net s'annule, alors que c'est la première
question qu'un allocateur pose.

Trois façons de combler ce trou ont été considérées. Modifier le moteur pour
qu'il porte un capital et des volumes. Écrire un second moteur dédié à la
capacité. Ou envelopper le modèle d'impact dans un modèle de coût qui connaît
le capital et lit les volumes à la date que le moteur lui donne.

## Décision

Le moteur ne change pas. Un modèle de coût, `ImpactAtScale`, porte le capital,
le volume quotidien moyen et la volatilité de chaque actif. Il enrichit le
contexte que le moteur lui passe, puis délègue le calcul à `SqrtImpactModel` et
à `LinearCostModel`. Il rend deux composantes séparées, le demi-écart et
l'impact, que le moteur garde en colonnes distinctes.

La courbe de capacité rejoue les mêmes poids à chaque taille d'une grille
géométrique. Mais elle ne se contente pas de la grille. Deux passages au capital
unité isolent le brut moyen, le demi-écart moyen et la charge d'impact moyenne.
La loi en racine carrée donne alors le capital d'annulation en forme fermée,
`((g - s) / K) ** 2`. Un dernier passage du moteur à ce capital vérifie que le
rendement net moyen y vaut zéro à la précision machine, et cette vérification
est publiée dans l'objet rendu.

Deux entrées de l'impact sont calculées sans regarder l'avenir. Le volume
quotidien moyen est la médiane d'un mois de volumes en dollars, décalée d'une
séance. La volatilité est l'écart type d'un mois de rendements quotidiens,
décalé de même. Un test injecte un volume aberrant à une date et vérifie que la
valeur rendue à cette date ne bouge pas.

Le plafond de participation borne la crédibilité du modèle. Quand la plus grosse
transaction de l'historique le dépasse avant le capital d'annulation, la
capacité retenue est le capital où le plafond est atteint. Ce capital se déduit
de la participation au capital unité par une règle de trois. Au-delà, le net
rendu par le moteur est déclaré optimiste.

## Conséquences

Une étude de capacité tient en une page : rebâtir les poids d'une stratégie,
joindre les volumes, appeler `capacity_curve`. La forme fermée et la grille se
contrôlent l'une l'autre, et un désaccord entre elles hors écrêtage lève une
erreur plutôt qu'un chiffre.

Le prix est un capital constant sur tout l'historique, ce qui surestime la
participation des premières années d'un fonds réel. Et le coefficient d'impact
reste déclaré : la capacité lui est proportionnelle à la puissance moins deux,
donc toute étude publie sa sensibilité.

Le statut de tout chiffre de capacité est **modélisé**. Aucune donnée gratuite
ne porte de coût d'exécution réel, et rien ici ne calibre le coefficient.

## Options écartées

**Modifier le moteur.** Rejetée parce que le moteur est la brique la plus
testée du dépôt, et qu'un capital en dollars y introduirait une seconde unité
là où tout est en fraction.

**Un second moteur.** Rejetée parce que la réconciliation de deux moteurs est
déjà un livrable de la phase 9, et qu'un troisième multiplierait les
divergences à expliquer.

**Une bissection sur le moteur au lieu de la forme fermée.** Rejetée parce que
la forme fermée est exacte sous le modèle et rend un contrôle indépendant du
moteur ; la bissection n'aurait contrôlé que le moteur par lui-même.

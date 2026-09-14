# 02 Savoir ce que l'investisseur pouvait connaître

Une donnée financière possède plusieurs dates.
La fin d'un trimestre indique la période décrite. Le dépôt du rapport indique quand son contenu devient accessible.
Employer le chiffre dès la première date peut donner au modèle une information venue du futur.

Le terme **point-in-time** désigne ici une lecture qui respecte la disponibilité historique de l'information.
Il faut également examiner les corrections apportées plus tard et la date à laquelle notre fournisseur les rend accessibles.

## Un exemple fictif

Une entreprise clôture son trimestre le 31 mars et publie son bénéfice le 10 mai.
Un portefeuille formé le 30 avril ne peut pas utiliser ce bénéfice.
Celui formé après sa publication peut l'utiliser, sous réserve de la convention d'heure et d'exécution.

Le bénéfice est corrigé en août.
Le test d'avril ne doit connaître ni le chiffre de mai, ni sa correction d'août.
Conserver seulement la dernière version d'un fichier empêche parfois de restituer cette chronologie.

## Une autre question indépendante

Quelles entreprises étaient accessibles à l'investisseur ?
Prendre la liste des entreprises présentes aujourd'hui pour simuler 1996 utilise une sélection faite après 1996.
Certaines entreprises disparues ont fait faillite. D'autres ont été acquises avec une prime.

Le **biais de survie** vient de cette sélection des observations conservées.
Son effet dépend des entreprises manquantes et de la règle de placement.
Il ne gonfle pas nécessairement tous les rendements ou tous les ratios de Sharpe.

![Capital final avec et sans les deux entreprises disparues dans un exemple fictif](repo:docs/guide/figures/survie_exemple.png)

Dans cet exemple, cinq placements de 100 dollars deviennent 120, 110, 90, 0 et 0 dollars.
Le portefeuille complet perd 36 %. Ne garder que les trois premiers fait apparaître un gain de 6,67 %.
Les montants sont fictifs. Le graphique illustre un mécanisme possible, sans mesurer le biais du panel réel.

## Lire les limites d'une source

L'[étude 013](repo:docs/etudes/013_cross_sectional_ml_long.md) montre pourquoi un historique plus long ne répare pas une sélection incomplète.
L'[étude 015](repo:docs/etudes/015_univers_polygon.md) distingue une liste de titres radiés de leurs prix effectivement accessibles.
L'[étude 020](repo:docs/etudes/020_meilleures_idees_13f.md) utilise la date de dépôt des déclarations de gestionnaires, mais reste limitée par les prix manquants.

Les facteurs publiés à partir de CRSP peuvent inclure les titres radiés.
Ils ne restituent pas nécessairement toutes les versions historiques des données.
Un univers complet et une information correctement datée sont deux qualités distinctes.

Le [guide des données datées](repo:docs/data/point_in_time.md) décrit les champs employés par le code.
Le [chapitre suivant](repo:docs/guide/03_calendrier.md) organise les périodes du test.

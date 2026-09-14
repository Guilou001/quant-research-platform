# Les entreprises absentes changent la question étudiée

Utiliser aujourd'hui la liste des membres d'un indice pour simuler un portefeuille ancien sélectionne les entreprises avec une information postérieure.
Certaines entreprises présentes à l'époque manquent.
D'autres n'étaient pas encore admissibles à l'indice.

## Comprendre le mécanisme

Une entreprise peut disparaître après une faillite, une fusion ou une acquisition.
Une acquisition peut rémunérer favorablement ses anciens actionnaires.
Il serait donc incorrect d'assimiler toutes les radiations à des pertes totales.

Le biais de survie modifie l'univers des positions.
Son effet sur le rendement et le risque dépend de la stratégie, notamment des titres qu'elle achète et de ceux qu'elle vend.
Il ne relève pas nécessairement le Sharpe de toute règle.

L'[exemple à cinq entreprises](../guide/02_donnees.md) montre un cas fictif où oublier deux pertes relève fortement le résultat.
L'[étude 002](../etudes/002_cross_sectional_momentum.md) illustre pourquoi le sens de l'effet peut différer pour une stratégie acheteuse et vendeuse.

## Deux qualités différentes des données

Un univers historique peut inclure les entreprises disparues.
Une base datée peut indiquer quand une information était accessible.
L'une de ces qualités ne garantit pas l'autre.

Les facteurs de Kenneth French et d'Open Source Asset Pricing reposent sur des constructions incluant les titres radiés.
Leurs versions récentes peuvent néanmoins contenir des révisions historiques.
Il faut donc lire séparément les champs d'univers et de disponibilité temporelle.

Les fonds négociés en bourse simplifient certaines reconstructions multi-actifs.
Ils peuvent aussi fermer ou fusionner.
Choisir seulement les fonds disponibles aujourd'hui conserve un risque de sélection.

## Ce que le dépôt a effectivement vérifié

L'[étude 013](../etudes/013_cross_sectional_ml_long.md) ne dispose pas d'un panel complet de titres historiques.
L'[étude 015](../etudes/015_univers_polygon.md) a obtenu un référentiel de radiations, sans les prix anciens suffisants dans l'accès testé.
Ces constats sont datés et doivent être remesurés si l'accès aux sources change.

Le champ du manifeste comporte trois valeurs.

| Valeur de survivorship_free | Sens déclaré |
|---|---|
| True | L'inclusion des titres disparus a été vérifiée dans le périmètre décrit |
| False | Le périmètre vérifié omet des titres disparus |
| None | Cette propriété n'a pas été vérifiée |

Le champ résume une vérification.
Il ne certifie pas automatiquement toutes les autres propriétés du fournisseur.
Les [limites des données gratuites](free_data_limitations.md) et les annexes donnent les détails nécessaires.

# 2026-09-03 : quarante ans de survivants, et ce que la survie fabrique

## Question

L'étude 011 avait rejeté les arbres sur onze ans. Elle laissait ouverte la
question de savoir si c'est l'historique qui leur manquait ou le signal. Le
laboratoire a un panneau quotidien de 503 survivants du S&P 500 depuis 1985,
sans caractéristique comptable. Les deux faits se confrontent : le temps
contre le biais.

## Hypothèse

Écrite dans `config.yaml` avant le premier chiffre. Sur quarante ans de
grandes capitalisations survivantes, avec les seules caractéristiques de prix,
un ensemble d'arbres ordonne les rendements du mois suivant mieux qu'une
régression pénalisée. L'écart survit aux coûts. Si l'étude 011 a échoué
faute d'historique, celle-ci doit réussir ; si elle échoue aussi, c'est le
signal qui manque.

## Expérience

L'étude 013 : le script de l'étude 011 avec un chargeur sur la couche bronze
du lac, cinq caractéristiques de prix, dix ans d'entraînement, trente plis de
1996 à 2025, dix-sept essais. Puis, parce que le résultat était trop propre, un
contrôle de biais de survie. Il mesure le même écart décile haut moins bas de
trois signaux, sur nos survivants et sur les déciles CRSP de Kenneth French,
qui incluent les sociétés radiées.

## Résultat

L'hypothèse est fausse au sens du protocole, et le reste est un avertissement.

| Mesure | Régression, référence | Arbres, modèle complexe |
|---|---:|---:|
| R² mensuel hors échantillon | 1,64 % | 1,56 % |
| Corrélation de rang moyenne, t | 0,027, 2,9 | 0,024, 2,8 |
| Sharpe net du décile, 365 mois | 0,601 | 0,849 |
| Diebold et Mariano contre la référence | | -0,55, p 0,58 |

| Signal, décile haut moins bas, 1996-2025 | Survivants, %/an | Kenneth French, %/an |
|---|---:|---:|
| Momentum de douze mois | 1,5 | 7,3 |
| Rendement du dernier mois | -5,5 | 0,0 |
| Rendement de 36 à 13 mois | -7,1 | 1,7 |

Statut : mesuré, coûts modélisés. Les arbres ne prévoient pas mieux que la
régression, avec quarante ans comme avec onze. Mais tout le reste passe, R²
quatre fois celui de l'article, cinq sous-périodes sur cinq positives, Sharpe
dégonflé de 1,00, et le contrôle dit pourquoi. La survie affaiblit le momentum
de 5,8 points par an et fabrique deux renversements. Acheter les perdants du
dernier mois rapporte 5,5 % par an chez les survivants et rien sur le CRSP.
Acheter les perdants de long terme rapporte 7,1 % contre -1,7 %. L'importance par
permutation désigne exactement le renversement de long terme et la volatilité.
Un titre encore dans l'indice a remonté par construction.

## Décision

Verdict `REJECTED`. La réponse à la question de l'étude 011 est que le temps
ne change rien à la comparaison des méthodes. Et une règle s'ajoute au
laboratoire : les contrôles statistiques testent la stabilité d'un signal, pas
son existence pour un investisseur de l'époque. Aucune étude sur actions
individuelles ne conclut sans univers qui inclut les radiations.

## Question suivante

Un univers avec radiations, que les données gratuites ne donnent pas. C'est la
première dépense de données qui aurait un sens, avant toute autre phase.

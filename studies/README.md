# Les études

Une étude est une réplication académique autonome à la lecture et dépendante au
calcul. Elle se lit sans connaître les autres, et elle appelle le ratio de
Sharpe du paquet partagé plutôt que le sien.

## L'arborescence d'une étude

```
studies/NNN_nom_de_l_etude/
├── README.md            la fiche complète, gabarit ci-dessous
├── config.yaml          la configuration validée par Pydantic
├── run.py               le point d'entrée, appelé par « quant study run »
├── notes.md             le journal propre à l'étude
└── results/             les sorties, régénérables
```

Rien d'autre. Toute logique réutilisable monte dans `src/quantlab/`, parce
qu'une métrique implémentée dans une étude finit par diverger de la même
métrique implémentée dans la suivante.

## Le gabarit du README d'étude

```
# <Titre>

## La question de recherche
## L'article
## L'intuition économique
## La définition mathématique
## Les données
## La méthodologie originale
## Notre implémentation
## Nos écarts avec l'article
## Les résultats
## La robustesse
## Les coûts
## Le hors échantillon
## Les limites
## Le verdict
```

La section « Les résultats » porte chaque chiffre avec ses cinq mentions
obligatoires : échantillon, brut ou net, hypothèses de coût, période, univers.

## L'ordre prévu

| Numéro | Étude | Article | État |
|---|---|---|---|
| 001 | Momentum temporel | Moskowitz, Ooi et Pedersen (2012) | non commencé |
| 002 | Momentum transversal | Jegadeesh et Titman (1993) | non commencé |
| 003 | Valeur et momentum | Asness, Moskowitz et Pedersen (2013) | non commencé |
| 004 | Qualité moins camelote | Asness, Frazzini et Pedersen (2019) | non commencé |
| 005 | Parier contre le bêta | Frazzini et Pedersen (2014) | non commencé |
| 006 | Portage | Koijen, Moskowitz, Pedersen et Vrugt (2018) | non commencé, sous réserve de données |
| 007 | Arbitrage statistique | Avellaneda et Lee (2010) | non commencé |
| 008 | Gestion de la volatilité | Moreira et Muir (2017) | non commencé |
| 009 | Apprentissage et évaluation d'actifs | Gu, Kelly et Xiu (2020) | non commencé |

Chaque étude produit son rapport et son verdict **avant** que la suivante
commence. C'est ce qui empêche d'accumuler neuf chantiers ouverts.

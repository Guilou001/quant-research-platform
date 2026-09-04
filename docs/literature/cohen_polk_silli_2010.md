# Best Ideas

| | |
|---|---|
| **Auteurs** | Randolph B. Cohen, Christopher Polk, Bernhard Silli |
| **Année** | 2010 |
| **Revue ou source** | Document de travail |
| **Lien** | Non lu ; le titre et le résultat sont rapportés par la littérature sur les clones de déclarations 13F |
| **Statut de réplication** | lecture reprise dans l'étude 020, sur les jeux 13F de la SEC, sans chiffre de référence |

Ce que cette fiche porte est rapporté de seconde main, statut **rapporté**.
Aucun chiffre de l'article n'est repris, et chaque section le dit quand elle
n'a rien.

## La question de recherche

La plus grosse position d'un gérant de fonds, sa meilleure idée, bat-elle
le marché, et le reste de son portefeuille le fait-il ?

En mots simples : les gérants ont-ils des idées, et sont-elles dans leur plus
grosse position ?

## L'intuition économique

Un gérant diversifie par obligation, pas par conviction. La position où sa
conviction l'emporte sur la diversification est celle qui porte son
information, s'il en a.

## Les données

Positions des fonds communs américains. Non consulté au-delà.

## L'univers

Fonds communs d'actions américains. Période non consultée.

## La méthodologie

Rapportée : la position au plus fort poids actif de chaque gérant, agrégée
sur les gérants, contre un modèle de facteurs. Le détail n'a pas été lu.

## Les équations qui comptent

Non consultées. L'étude 020 n'en reprend aucune ; elle définit la meilleure
idée comme la plus grosse position en valeur, ce qui n'est pas le poids actif.

## Les résultats originaux

Rapportés : un rendement anormal positif des meilleures idées, non chiffré
ici faute de lecture.

## Les critiques connues

Non recherchées.

## Les problèmes de réplication connus

Non recherchés. L'étude 020 en a trouvé deux qui lui sont propres : la valeur
des jeux 13F en milliers de dollars jusqu'en 2022, et les fonds indiciels
comme plus grosse position.

## Les biais possibles

Le biais de survie des prix, mesuré à 28,9 % des idées dans l'étude 020. Et
le poids actif de l'article, qui exige un indice de référence par fonds que
les déclarations 13F ne portent pas.

## Nos décisions d'implémentation

Déclarations 13F-HR non amendées, dix à cinquante positions, cent millions
de dollars, plus grosse position d'au moins 5 %, formation le
quarante-sixième jour après la fin de période, fonds écartés.

## Nos écarts avec l'article

La plus grosse position en valeur au lieu du poids actif. Les déclarants 13F
au lieu des fonds communs. 2013 à 2026 au lieu de la fenêtre de l'article.
SPY au lieu d'un modèle de facteurs.

## Nos résultats

Étude 020, `REJECTED` : +0,27 % par an sur le marché, t 0,26, alpha -0,69 %
par an, bêta 1,08 ; 28,9 % des idées sans prix chez la source gratuite.

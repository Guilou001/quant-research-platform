# Open source cross-sectional asset pricing

| | |
|---|---|
| **Auteurs** | Andrew Y. Chen, Tom Zimmermann |
| **Année** | 2022 |
| **Revue ou source** | Critical Finance Review, vol. 11, no 2, p. 207-264 |
| **Lien** | Données et documentation : <https://www.openassetpricing.com/data/>, publication d'octobre 2025, lue le 2026-09-04 ; code : <https://github.com/OpenSourceAP/CrossSection>, GPL-2.0 ; l'article lui-même n'a pas été lu en entier |
| **Statut de réplication** | données consommées par l'étude 016 ; l'article n'est pas répliqué |

Ce que cette fiche porte vient de la page des données, du dépôt de code et du
résumé de l'article, statut **rapporté**. Ce qui n'y figure pas est marqué non
consulté.

## La question de recherche

Les centaines de prédicteurs de rendements d'actions publiés depuis les années
1970 se retrouvent-ils quand on les reconstruit tous, avec le même code, sur
les mêmes données ? Et que valent-ils une fois reconstruits ?

En mots simples : si l'on refait tous les devoirs de la littérature avec une
seule règle, combien tiennent ?

## L'intuition économique

Aucune : c'est un travail de reconstruction, dont la valeur est de rendre
comparables des résultats publiés dans des conditions différentes. Sa
contribution est l'outil, pas un mécanisme.

## Les données

CRSP et Compustat pour les rendements et les comptes, IBES pour les
prévisions d'analystes. Des sources ponctuelles s'ajoutent signal par signal. Les
portefeuilles publiés sont mensuels, de 1926 à 2024 dans la publication
d'octobre 2025, en pourcentage. Les rendements de radiation de CRSP sont
compris, ce qui fait de ces séries la seule source libre sans biais de survie
que le laboratoire connaisse. Non consulté au-delà de la page des données.

## L'univers

Les actions ordinaires américaines de CRSP. Les filtres de chaque signal
suivent l'article d'origine, documentés signal par signal dans la fiche
publiée avec les données.

## La méthodologie

Chaque prédicteur est reconstruit selon son article d'origine, puis un
portefeuille long moins court est formé par tri, décile ou quintile selon
l'article. La pondération, égale ou par la capitalisation, et la période de
détention suivent aussi l'article. La fiche des signaux porte, par
prédicteur, les auteurs, l'année, la revue, la fin de l'échantillon d'origine
et le rendement et le t rapportés dans l'article.

## Les équations qui comptent

Aucune formule propre : la mesure est le rendement moyen du portefeuille long
moins court et son t.

## Les résultats originaux

Rapportés, résumé de l'article. Pour les 161 caractéristiques nettement
significatives dans leur article d'origine, 98 % des portefeuilles long moins
court reconstruits ont un t supérieur à 1,96. La régression des t
reconstruits sur les t d'origine a une pente de 0,88 et un R² de 82 %.

## Les critiques connues

Le laboratoire n'en a consulté aucune. Une limite évidente : un portefeuille
reconstruit selon l'article reproduit aussi ses choix de construction, et un
signal peut tenir par sa construction plus que par son mécanisme.

## Les problèmes de réplication connus

La fiche des signaux note, prédicteur par prédicteur, les écarts de
construction avec l'article d'origine ; non consultée ligne par ligne.

## Les biais possibles

Les prédicteurs sont ceux qui ont été publiés, donc ceux qui ont réussi dans
leur échantillon. La fiche donne l'année de publication et non le mois, si
bien qu'une fenêtre construite sur l'année contient des mois d'après parution.

## Nos décisions d'implémentation

`quantlab.data.providers.osap` télécharge les deux fichiers par leur adresse
directe, les garde dans le cache brut avec leur empreinte et divise les
rendements par cent. Son manifeste déclare que la licence n'est pas énoncée
et que la citation est demandée.

## Nos écarts avec l'article

Aucun : les portefeuilles sont lus tels quels. La fin d'échantillon et la
publication sont prises au 31 décembre de l'année donnée.

## Nos résultats

Étude 016 : sur 208 prédicteurs, le rendement après publication vaut en
moyenne 53 % de celui de la fenêtre de l'article, 42 % en médiane. 83 % des
prédicteurs baissent et 16 % deviennent négatifs.

## Notre contrôle de robustesse

Voir l'étude 016 : mise en commun par la moyenne des rapports, par la
régression à effet fixe, par décennie de publication.

## Références

Chen, A. Y. et Zimmermann, T. (2022). Open Source Cross-Sectional Asset
Pricing. Critical Finance Review, 11(2), 207-264.

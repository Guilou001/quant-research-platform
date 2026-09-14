# 016 Que reste-t-il d'une stratégie après sa publication ?

Le rendement diminue après publication pour {{s016_declining}} % des {{s016_n}} portefeuilles comparables de cette étude.
Cette observation ne désigne pas, à elle seule, la cause de la baisse.
La sélection initiale, l'évolution des marchés et l'exploitation de l'information peuvent produire des effets qui se superposent.

## Une baisse de moitié ne signifie pas une perte de moitié

Prenons un exemple fictif. Une règle gagne en moyenne 1 % par mois dans l'échantillon qui a servi à la découvrir.
Après publication, elle gagne 0,4 % par mois. Elle conserve `0,4 / 1 = 40 %` de son rendement moyen antérieur.
La baisse du rendement moyen vaut donc 60 %. Le portefeuille ne perd pas nécessairement 60 % de sa valeur.

Changeons maintenant le rendement initial. Une règle passe de 0,1 % à 0,2 % par mois.
Son rendement double, mais l'amélioration en niveau n'est que de 0,1 point de pourcentage mensuel.
Les rapports deviennent instables quand leur dénominateur est proche de zéro.
Il faut regarder les niveaux et les proportions avant de résumer plusieurs stratégies ensemble.

## Pourquoi McLean et Pontiff séparent les périodes

McLean et Pontiff étudient 97 variables auparavant associées aux rendements d'actions.
Ils distinguent l'échantillon des recherches initiales, la période suivante et celle après publication.
Leur résumé rapporte des baisses de 26 % hors échantillon et de 58 % après publication.
Ces nombres concernent leur dispositif et leur ensemble de variables.
[Article de référence](https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12365).

La séparation temporelle aide à examiner des explications concurrentes.
Une découverte sélectionnée pour son résultat exceptionnel peut décevoir dès la période suivante, même si personne ne lit l'article.
La diffusion de l'idée peut aussi modifier les prix. Une comparaison descriptive ne suffit pas à isoler cette seconde explication.

## Comment le laboratoire construit sa comparaison

Les portefeuilles proviennent d'Open Source Asset Pricing, le projet de Chen et Zimmermann.
Leurs séries sont construites depuis CRSP et comprennent les rendements de radiation des actions.
Le fichier téléchargé contient 212 portefeuilles. Le minimum d'observations laisse {{s016_n}} comparaisons après publication.

Chaque portefeuille possède ses propres dates. Une règle publiée en 1990 et une autre publiée en 2018 ne partagent pas la même période suivante.
Les séries couvrent collectivement 1926 à 2024, avec des durées différentes selon les règles.
Les rendements sont bruts de frais.

| Élément | Recherche source | Adaptation du laboratoire |
|---|---|---|
| Ensemble étudié | 97 variables chez McLean et Pontiff | Portefeuilles disponibles chez Chen et Zimmermann |
| Dates | Fenêtres des recherches et publication | Publication connue à l'année dans les métadonnées utilisées |
| Construction | Dispositif des auteurs | Séries déjà construites par le fournisseur universitaire |
| Résumé | Estimations du papier | Moyenne, médiane et régression publiées séparément |

Le tableau décrit des différences de méthode. L'étude constitue une extension descriptive, avec des limites documentées, plutôt qu'une reproduction exacte des tables du papier.
La [fiche de littérature](repo:docs/literature/mclean_pontiff_2016.md) conserve le statut de lecture des sources.

## Lire ensemble la moyenne, la médiane et la régression

| Mesure | Résultat après publication |
|---|---:|
| Rendement antérieur conservé, médiane des rapports | {{s016_median}} % |
| Rendement antérieur conservé, moyenne des rapports | {{s016_mean}} % |
| Portefeuilles dont le rendement diminue | {{s016_declining}} % |
| Baisse estimée par la régression retenue | {{s016_regression}} % |
| Statistique t de cette baisse dans la régression | {{s016_regression_t}} |

La **médiane** partage les rapports en deux groupes de même taille. La moyenne additionne les rapports et divise par leur nombre.
Quelques rapports extrêmes peuvent déplacer fortement la moyenne. Leur désaccord n'est donc pas une erreur de calcul.

La régression emploie encore une autre pondération et une autre mesure d'incertitude.
Sa statistique t rapporte le coefficient à son erreur type. Sa taille ne permet pas ici de distinguer nettement l'estimation de zéro aux seuils usuels.
Un grand nombre de baisses individuelles ne garantit pas que toute estimation agrégée sera précise.
Sources numériques dans les [fenêtres individuelles](repo:studies/016_publication_decay_212/results/tables/windows.csv)
et les [résultats enregistrés](repo:studies/016_publication_decay_212/results/metrics.json).

![Les rapports avant et après publication](repo:docs/guide/figures/publication_distribution.png)

Chaque point représente un portefeuille et indique la part de rendement moyen conservée. La ligne verticale à 100 % marque l'absence de baisse.
Le panneau central montre les valeurs courantes. Le panneau séparé conserve les valeurs extrêmes et leurs étiquettes.
Aucune valeur n'est remplacée par la borne de l'axe.

## Ce que nous ne pouvons pas attribuer à la publication

Les portefeuilles récemment publiés ont une période suivante plus courte et exposée à des conditions de marché différentes.
La date de publication n'est pas assignée au hasard. Les différences par décennie ne constituent donc pas une expérience causale.

Les historiques téléchargés sont également une version récente des données.
Inclure les actions disparues ne garantit pas que toutes les informations soient celles disponibles à chaque date historique.
Ces deux problèmes doivent être examinés séparément.

## Vérifier et poursuivre

Le vérificateur relit chaque rapport dans le fichier des fenêtres. Les champs des textes sont calculés depuis les sorties enregistrées.
L'[annexe technique](repo:studies/016_publication_decay_212/ANNEXE_TECHNIQUE.md) contient les autres regroupements et les conventions.
Le [chapitre sur le hasard](repo:docs/guide/04_hasard.md) explique comment la sélection initiale peut rendre une découverte trop favorable.

# 08 Écrire une conclusion à la hauteur des preuves

Un résultat utile peut être négatif, incertain ou limité par les données.
Sa valeur vient de ce que l'on a appris et de la possibilité de vérifier le raisonnement.
Le lecteur doit pouvoir séparer le nombre observé de l'explication proposée.

## Quatre statuts pour les chiffres

Un résultat **mesuré** vient d'un calcul sur les données indiquées.
Un résultat **rapporté** provient d'une source citée.
Un résultat **modélisé** dépend d'hypothèses telles qu'un coût de transaction supposé.
Un résultat **non calculable** manque des données nécessaires.

Une hypothèse de coût peut être modélisée et le rendement correspondant calculé exactement.
L'exactitude du calcul ne transforme pas l'hypothèse en coût réellement payé.

## Un résultat non significatif reste informatif

Supposons, dans un exemple fictif, un gain estimé de deux points de pourcentage par an.
Une procédure d'incertitude donne un intervalle allant de moins trois à plus sept points.
L'estimation centrale est positive, mais zéro appartient à l'intervalle.

Ce résultat ne démontre ni une amélioration, ni une égalité parfaite.
Il peut motiver davantage de données ou une expérience plus précise.
Il ne justifie pas de présenter les deux méthodes comme interchangeables.

## Lire les verdicts du logiciel

| Verdict | Lecture utile |
|---|---|
| REJECTED | Les critères retenus pour cette étude ne sont pas satisfaits |
| EXPERIMENTAL | Une partie des preuves existe, avec des limites qui empêchent un statut supérieur |
| REPLICATED | Les contrôles de comparaison configurés passent, dans le périmètre déclaré |
| ROBUST | Les critères supplémentaires du laboratoire passent, sous leurs hypothèses |

Ces mots sont des catégories du moteur de décision.
Ils ne remplacent pas la lecture des contrôles.
Un critère absent doit être distingué d'un critère calculé qui échoue.

Dans l'[étude 021](repo:docs/etudes/021_portefeuille_de_primes.md), le contrôle nommé « réplication » compare en réalité le portefeuille à une composante.
Son libellé ne prouve pas la reproduction d'un article.
La présentation explique donc le contenu du contrôle avant son statut.

## Refaire le raisonnement

Pour chaque conclusion, retrouvez la question, la période, l'univers, le repère et les coûts.
Examinez ensuite l'incertitude et les explications concurrentes.
Le [registre des valeurs](repo:documentation/publication_values.json) relie les chiffres du cours aux fichiers de résultats.

Les textes des chapitres et des études ont une source éditoriale commune dans le dossier documentation.
La construction publie le site, les README et le manuscrit du PDF.
Le contrôle de fraîcheur échoue lorsqu'une source numérique change sans régénération des textes.

Les annexes conservent les détails de l'expérience historique.
Les [notes de relecture](repo:docs/research_journal/pedagogie-2026-09-13.md) expliquent les corrections d'interprétation.
Le [catalogue des études](repo:docs/etudes/index.md) permet de poursuivre selon la question qui vous intéresse.

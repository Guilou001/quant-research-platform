# ADR-010 : la prose est en français, le code en anglais

**Statut** : acceptée le 2026-09-01.

## Contexte

Le projet vise deux lecteurs. Un recruteur montréalais, qui lit le français et
juge la clarté du raisonnement. Un ingénieur, qui lit le code et attend les
conventions de son métier.

Servir les deux dans une seule langue en dessert un. Un code aux identifiants
français se lit mal par quiconque connaît `scikit-learn`. Une documentation en
anglais perd la précision de raisonnement que le portefeuille cherche depuis
trente-huit dépôts.

## Décision

- **Le code est en anglais** : noms de modules, de classes, de fonctions, de
  variables, de colonnes, de commandes.
- **La prose est en français** : docstrings, commentaires, documentation,
  README, rapports d'étude, fiches de littérature, journal de recherche.
- Le README principal porte un **résumé anglais** en tête, court, pour le
  lecteur qui ne lit pas le français.
- Les termes techniques consacrés restent en anglais quand la traduction
  française n'existe pas ou trompe, et sont alors définis à leur première
  occurrence.

## Conséquences

Un contributeur non francophone lit le code et pas la documentation. C'est
accepté : le projet est d'abord un travail de recherche personnel et une pièce
de portefeuille, pas une bibliothèque à contribution ouverte.

Le style de la prose suit `METHODE.md` du portefeuille, ce qui rend les
docstrings plus longues que la moyenne. C'est l'intention : la documentation
d'une formule est la moitié de sa valeur, et un lecteur doit pouvoir apprendre
la finance quantitative en lisant le projet.

## Options écartées

**Tout en anglais.** Rejetée parce qu'elle rompt avec les trente-huit dépôts du
portefeuille et perd le registre de précision qui les distingue.

**Documentation bilingue intégrale.** Rejetée pour le coût de maintenance : deux
versions divergent, et la version divergente est toujours celle qu'on ne relit
pas.

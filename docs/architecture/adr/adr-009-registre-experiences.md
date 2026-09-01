# ADR-009 : le registre d'expériences est un fichier, pas un serveur

**Statut** : acceptée le 2026-09-01.

## Contexte

Chaque expérience doit laisser une trace complète : configuration, empreinte de
commit, version des données, paramètres, métriques, artefacts, horodatage,
graine, identifiant. Sans cette trace, deux choses deviennent impossibles.
Refaire l'expérience, d'abord. Compter le nombre d'essais, ensuite, ce qui est
l'intrant du ratio de Sharpe dégonflé.

MLflow fait ce travail et le fait bien. Il demande en échange un serveur, une
base de données, et un état qui vit à côté du dépôt.

## Décision

Le registre est un ensemble de fichiers dans `artifacts/`, un répertoire par
expérience, plus un index en JSON par ligne que DuckDB lit directement comme une
table.

Chaque expérience porte un `metrics.json`, un `config.yaml`, un
`data_manifest.json`, ses figures, ses tableaux et son `report.html`.

L'index se relit avec une requête SQL, ce qui suffit à répondre aux deux
questions qui comptent : combien d'essais ont été menés sur cette famille de
stratégies, et quel commit a produit ce chiffre.

## Conséquences

Le registre se versionne, se copie et se lit sans démarrer quoi que ce soit. Un
lecteur qui clone le dépôt voit l'historique de recherche.

Il ne porte ni interface web, ni comparaison graphique de courbes, ni suivi de
modèles en production. MLflow reste envisageable en phase 8 si l'entraînement de
modèles le justifie, et le format de fichier ne l'empêche pas.

Le décompte des essais dépend de l'honnêteté de l'enregistrement. La règle 8 du
`CLAUDE.md` la rend explicite : aucune expérience ratée n'est cachée, et les
échecs vont dans `docs/research_journal/rejected_ideas.md`. Cacher un essai
fausse le test qui sert précisément à détecter le surapprentissage.

## Options écartées

**MLflow dès le départ.** Rejetée pour la dépendance opérationnelle : un serveur
à démarrer avant de pouvoir lire un résultat de l'an dernier, et un état qui
n'est pas dans le dépôt.

**Une base SQLite.** Rejetée pour la lisibilité : un fichier binaire ne se lit
pas dans une revue de code et ne se compare pas entre deux commits.

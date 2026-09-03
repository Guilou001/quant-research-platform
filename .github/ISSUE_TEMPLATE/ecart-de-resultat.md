---
name: Un chiffre ne se retrouve pas
about: Un chiffre d'un README, d'un rapport ou d'une étude diffère de ce que le code produit
title: "Étude NNN : <la métrique> vaut X dans le README et Y à l'exécution"
labels: ecart-de-resultat
---

## Le chiffre publié

Fichier et ligne où il est écrit, et sa valeur.

## Le chiffre obtenu

La commande exacte, la version du dépôt (`git rev-parse HEAD`), la date de
l'exécution, et la valeur obtenue. Les données de Yahoo sont révisées entre
deux téléchargements : un écart au cinquième chiffre est attendu, un écart au
second ne l'est pas.

## Ce qui a été vérifié

Ce que vous avez déjà exclu : la version des dépendances, le cache du lac, la
fenêtre de dates de la configuration.

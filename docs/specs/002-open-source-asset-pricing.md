# Spécification 002 : lire les 212 portefeuilles d'Open Source Asset Pricing

**Statut** : acceptée le 2026-09-04, livrée le 2026-09-04.
**Règles concernées** : 4, 5, 13.

## Ce que cela doit faire

Le laboratoire doit pouvoir lire, sans les recopier, les rendements mensuels
des 212 portefeuilles long moins court de Chen et Zimmermann (2022). Il doit
lire aussi la fiche de chaque prédicteur : auteurs, année de publication, fin
d'échantillon de l'article. C'est la seule source libre de rendements transversaux
construits sur CRSP, donc sans biais de survie, et elle donne à l'étude 014 les
deux cents unités qui lui manquaient. Le mécanisme est un fournisseur au patron des autres. Deux fichiers CSV
publiés sur Google Drive sont téléchargés par le client HTTP poli, gardés dans
le cache brut avec leur empreinte, et rendus en tableaux datés en fin de mois.

## Ce que le dépôt porte déjà, et qui sera appelé plutôt que recopié

`quantlab.data.providers.base.BaseProvider` pour le client, le cache brut et
`fetch_cached` ; `quantlab.data.manifest.DatasetManifest` ; le protocole
`DataProvider` de `quantlab.core.protocols`.

## Les critères d'acceptation, mesurables

1. `long_short_returns()` rend 212 colonnes, 1 188 mois de 1926-01 à 2024-12,
   en fractions et non en pourcentages, datées en fin de mois civile ; mesuré
   sur le fichier d'octobre 2025.
2. Une valeur lue à la main dans le fichier, AM en décembre 2024, 1,801 %, se
   retrouve à 0,01801.
3. `signal_documentation()` rend 212 lignes de type « Predictor », toutes avec
   une année de publication et une fin d'échantillon.
4. Le manifeste porte la citation demandée par les auteurs, le statut de la
   licence, non énoncée sur la page des données, et l'empreinte du fichier.
5. `make test` ne fait aucun appel réseau.

## Les décisions de conception, et ce qu'elles écartent

Les identifiants des fichiers Google Drive sont des constantes du module, ce
qui est un nombre qui décide de quelque chose et vit donc dans le code avec sa
date de lecture. L'alternative, le paquet `openassetpricing` de PyPI, est
écartée : il ajoute une dépendance pour deux requêtes HTTP.

## Le plan, en étapes vérifiables

1. Le module et ses deux analyseurs purs, testés sur un extrait écrit à la
   main.
2. L'étude 016, qui refait l'étude 014 sur les 212 prédicteurs.

## Hors périmètre

Les caractéristiques au niveau des titres, 1,6 Go, qui exigent CRSP pour être
appariées à des rendements et n'ont donc pas d'usage libre ici.

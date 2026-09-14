# 015 Une liste de titres disparus suffit-elle pour refaire leur histoire ?

Pour tester un ancien portefeuille, il faut savoir quels titres existaient et retrouver leurs rendements.
Une liste historique répond à la première question.
Elle ne répond pas automatiquement à la seconde.

Cette étude mesure les accès obtenus avec le forfait utilisé au début de septembre 2026.
Elle constitue un audit de source, pas une étude de performance ni une conclusion permanente sur l'offre du fournisseur.

## Un exemple fictif

Un référentiel confirme qu'une entreprise cotait en 2008 et qu'elle a disparu en 2009.
Sans son prix d'achat, ses distributions et sa valeur de sortie, on ne peut pas calculer le rendement du placement.
La disparition pourrait venir d'une faillite ou d'une acquisition.

La connaître ne permet donc pas d'imposer arbitrairement une perte de 100 %.

## Ce que les requêtes ont montré

L'extraction conserve {{s015_delisted}} actions ordinaires radiées et datées depuis 2004.
La requête de prix ancienne nécessaire à l'expérience n'a toutefois pas fourni l'historique attendu avec cet accès.
Le référentiel est utile, mais les prix obtenus ne suffisent pas à construire l'univers demandé depuis 1996.

Les réponses, les dates et les paramètres appartiennent au résultat de l'audit.
Un refus d'accès ponctuel ne doit pas être interprété comme une impossibilité définitive.

## Pourquoi ce résultat est important

L'[étude 013](repo:docs/etudes/013_cross_sectional_ml_long.md) reste limitée par un panel de survivants.
Ce référentiel permet de documenter l'étendue des absences.
Il ne chiffre pas leur effet exact sur la performance faute de rendements complets.

Le [cahier de l'univers historique](repo:docs/specs/001-univers-sans-biais-de-survie.md) définit ce que la source devait fournir.
Le statut de rejet signifie que cette source, dans les conditions testées, ne satisfait pas cette demande.

## La suite raisonnable

Une nouvelle extraction doit redater les accès et conserver les réponses.
Elle doit aussi vérifier les acquisitions, les identifiants et les rendements de sortie.
L'amélioration recherchée est une histoire des investissements possibles, au-delà d'une liste de symboles.

## Vérifier le résultat

Les [mesures enregistrées](repo:studies/015_univers_polygon/results/metrics.json) donnent les nombres et leurs fenêtres.
L'[annexe technique](repo:studies/015_univers_polygon/ANNEXE_TECHNIQUE.md) conserve les tableaux, les hypothèses, les limites et les commandes de calcul.
Le [script de l'étude](repo:studies/015_univers_polygon/run.py) relie ces choix aux fonctions du laboratoire.

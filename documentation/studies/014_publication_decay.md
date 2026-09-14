# 014 Les huit premières stratégies s'affaiblissent-elles après publication ?

L'étude compare la période de chaque article, la période suivante et la période après publication.
Elle utilise les huit premières stratégies du laboratoire.
Cet ensemble mélange plusieurs classes d'actifs et ne reproduit pas l'univers de l'article de référence.

## Un exemple fictif

Une stratégie rapporte en moyenne 1 % par mois avant publication et 0,3 % après.
Elle conserve 30 % de son rendement moyen initial, ce qui correspond à une baisse de 70 %.
Elle ne perd pas pour autant 70 % de sa valeur.

Une autre passe de 0,1 % à 0,2 %.
Elle double son rendement moyen malgré un faible changement absolu.
Les rapports deviennent donc sensibles aux petites moyennes initiales.

## Le contexte de McLean et Pontiff

Les auteurs examinent 97 caractéristiques d'actions.
Notre comparaison porte sur huit séries de stratégies différentes.
La [fiche de littérature](repo:docs/literature/mclean_pontiff_2016.md) indique les résultats obtenus depuis le résumé et les limites d'accès au texte complet.

Le laboratoire sépare la moyenne des rapports d'une régression.
Ces deux calculs ne répondent pas exactement à la même question.

## Le constat

Les huit séries présentent un rendement moyen plus faible après publication dans les fenêtres retenues.
La baisse moyenne calculée par les rapports vaut {{s014_decline}} %, avant les coûts propres à une mise en œuvre.
Les dates diffèrent selon les articles.

Huit séries constituent un petit ensemble, avec des dépendances entre certaines stratégies.
Un rééchantillonnage de stratégies ne suffit pas à éliminer ces limites.

## Ce que l'on ne peut pas en déduire

La publication peut attirer la concurrence, mais cette comparaison ne l'isole pas comme cause.
Les conditions de marché et la sélection initiale des résultats changent également.
Un intervalle contenant une valeur publiée n'établit pas une réplication exacte.

L'[étude 016](repo:docs/etudes/016_publication_decay_212.md) élargit l'analyse à des portefeuilles d'actions américains et distingue plus précisément les mesures.

## Vérifier le résultat

Les [mesures enregistrées](repo:studies/014_publication_decay/results/metrics.json) donnent les nombres et leurs fenêtres.
L'[annexe technique](repo:studies/014_publication_decay/ANNEXE_TECHNIQUE.md) conserve les tableaux, les hypothèses, les limites et les commandes de calcul.
Le [script de l'étude](repo:studies/014_publication_decay/run.py) relie ces choix aux fonctions du laboratoire.

# Notes de l'étude 016

## Ce qui a été décidé avant de voir un chiffre

Le protocole de l'étude 014, les dates au 31 décembre de l'année donnée par
la fiche, le seuil de vingt-quatre mois pour les deux mesures, l'exclusion
des prédicteurs à rendement non positif dans la fenêtre de l'article, quatre
décennies. Neuf essais.

## Ce qui a surpris

La proportion perdue ne dépend pas de la force du prédicteur, alors que le
niveau perdu en dépend fortement. Les deux sont vrais en même temps, et le
second suit du premier par simple retour à la moyenne : un prédicteur dont
l'estimation est haute par chance redescend davantage en points. La lecture
de l'article, « les meilleurs perdent plus », vaut en points et non en part.

Les 47 prédicteurs publiés depuis 2010 ont perdu 94 % de leur rendement. La
fenêtre d'après publication de ces prédicteurs commence en 2016 au plus tôt,
et le résultat ne distingue pas ce qui vient de la publication de ce qui vient
de la période.

## Les essais ratés

La première version calculait un t naïf par fenêtre ; il a été remplacé par
celui de `quantlab.analytics.ratios` avant toute lecture, comme dans l'étude
014 après son audit.

Le téléchargement direct depuis Google Drive fonctionne pour ces deux
fichiers, de 3,3 Mo et 0,2 Mo ; un fichier plus gros exigerait la page de
confirmation de Google, non traitée.

## Ce qui reste ouvert

Refaire la mesure avec des dates de publication au mois, que la fiche ne donne
pas, et distinguer la publication de la décennie pour les prédicteurs récents
en comparant, à date égale, ceux publiés avant et après 2010.

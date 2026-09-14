# 006 Réduire l'exposition quand le marché devient agité

La volatilité mesure l'ampleur des fluctuations.
Une gestion en volatilité réduit la position lorsque les variations récentes deviennent plus grandes.
L'étude demande si cette règle améliore une performance réellement accessible avec l'information passée.

## Un exemple fictif

Une règle simplifiée investit un montant inversement proportionnel à la variance récente.
Si cette variance double, le montant investi est divisé par deux.
Cela réduit l'exposition, mais peut aussi faire manquer une reprise rapide après une crise.

Le choix de la constante qui règle l'échelle du portefeuille compte.
La calculer sur toutes les dates utilise des observations qui n'existaient pas encore au début du test.

## Le lien avec Moreira et Muir

La [fiche de littérature](repo:docs/literature/moreira_muir_2017.md) détaille la version de travail consultée.
Le laboratoire retrouve un alpha de {{s006_alpha}} % par an pour le marché sur août 1926 à avril 2015, avant frais.
Cet **alpha** est la constante d'une régression après prise en compte de l'exposition au facteur de référence.

Un alpha estimé sur toute une période n'est pas automatiquement le rendement d'un portefeuille dont tous les poids étaient connus à chaque date.

## Une comparaison qui change la lecture

Avec une mise à l'échelle estimée sur le passé, l'alpha mesuré sur août 1936 à juin 2026 vaut {{s006_future}} % par an, avant frais.
Il s'agit d'une analyse de validation sur une fenêtre différente, pas d'une comparaison toutes choses égales.

L'étude construit également une position couverte, avec un bêta de couverture estimé dans le temps.
Son résultat net sur la période finale ne satisfait pas les critères.
Les tableaux détaillés séparent bien cette position et la régression descriptive.

## La leçon méthodologique

Une identité calculable après la dernière observation peut expliquer un résultat historique.
Elle ne fournit pas forcément une décision réalisable avant cette observation.
Le [chapitre du calendrier](repo:docs/guide/03_calendrier.md) donne le vocabulaire pour distinguer ces deux usages.

## Vérifier le résultat

Les [mesures enregistrées](repo:studies/006_volatility_managed/results/metrics.json) donnent les nombres et leurs fenêtres.
L'[annexe technique](repo:studies/006_volatility_managed/ANNEXE_TECHNIQUE.md) conserve les tableaux, les hypothèses, les limites et les commandes de calcul.
Le [script de l'étude](repo:studies/006_volatility_managed/run.py) relie ces choix aux fonctions du laboratoire.

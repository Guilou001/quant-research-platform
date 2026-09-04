# Notes de l'étude 014

## Ce qui a été décidé avant de voir un chiffre

Les huit séries, avec la fin d'échantillon et le mois de publication de chaque
article lus dans sa fiche de littérature. Le seuil de vingt-quatre mois par
fenêtre, la moyenne des rapports et la régression comme deux mesures, la
tolérance de 10 % du laboratoire contre 58 % et 26 %. Douze essais. La graine
20260903.

## Ce qui a surpris

La fenêtre d'après échantillon. L'article y mesure 26 % de baisse, et la
lecture la plus courante de ce chiffre est le surapprentissage des auteurs
d'origine. Nos huit n'y perdent presque rien, 3 % par la moyenne et 8 % par la
régression, et trois des six fenêtres mesurées ont un ratio de Sharpe plus
haut que dans l'article, quatre un rendement moyen plus haut. La raison est la sélection, et elle a été écrite au
verdict plutôt qu'au tableau des limites, parce qu'elle change la lecture de
tout le reste.

Le t de la régression, -1,77 pour une baisse que huit stratégies sur huit
montrent. Les erreurs types groupées par mois voient huit unités, pas 5 958
observations, et c'est la bonne façon de compter.

La revue de code du 2026-09-03 a trouvé que la régression voyait les deux
fenêtres de moins de vingt-quatre mois que la moyenne des rapports excluait,
que les dates étaient recopiées à la main, et que le t venait d'une formule
naïve à côté du t de Lo du laboratoire. Les trois sont corrigés : la
régression exclut 45 mois, les dates sont lues dans la configuration de
chaque étude, et le t est celui de `quantlab.analytics.ratios`. La baisse
d'après échantillon passe de 4 % à 8 %, la corrélation de rang de -0,05 à
0,12, et rien d'autre ne bouge au-delà de la troisième décimale.

## Les essais ratés

La première version chargeait pour l'étude 001 la série reconstruite sur fonds
cotés, qui commence en 2007 : trente-six mois dans la fenêtre de l'article, et
un rapport sans sens. La série des auteurs, celle qu'AQR publie depuis 1985,
l'a remplacée avant le premier tableau, et c'est écrit dans la configuration.

Le résumé de l'article n'a pu être lu que par l'interface Crossref, l'éditeur
et SSRN refusant l'accès automatisé. La fiche de littérature dit ce qui vient
du résumé et marque le reste non consulté.

## Ce qui reste ouvert

La même mesure sur les quelque deux cents portefeuilles du jeu de Chen et
Zimmermann, que le laboratoire sait lire, donnerait des unités en nombre
suffisant pour tester l'hétérogénéité. Et une date de première circulation
par article, plutôt que le numéro de la revue, rapprocherait la fenêtre
d'après échantillon de ce que les investisseurs pouvaient lire.

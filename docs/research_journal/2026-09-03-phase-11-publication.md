# 2026-09-03 : ce que la publication laisse, huit stratégies ensemble

## Question

Chaque étude du laboratoire mesurait seule ce que sa stratégie devenait après
son article. Mises ensemble, les huit rendent-elles la baisse que McLean et
Pontiff mesurent sur 97 caractéristiques, 26 % dès la fin de l'échantillon et
58 % après publication ?

## Hypothèse

Écrite dans `config.yaml` avant le premier chiffre. Les huit perdent 58 % de
leur rendement mensuel moyen après publication et 26 % dès la fin de
l'échantillon, à la tolérance du laboratoire.

## Expérience

L'étude 014 : les huit séries de tête les plus longues, brutes, et trois
fenêtres par article aux dates de sa fiche. Deux mises en commun : la moyenne
des rapports de rendement, avec un intervalle par rééchantillonnage des
stratégies, et la régression des rendements normalisés sur deux indicatrices.
Cette régression porte un effet fixe par stratégie et des erreurs types
groupées par mois. Douze essais.

## Résultat

| Mesure | Après échantillon | Après publication | Article |
|---|---:|---:|---:|
| Baisse du rendement moyen | 3 % sur 6 | 73 % sur 8, intervalle 54 à 94 | 26 puis 58 |
| Baisse par la régression | 4 %, t -0,13 | 67 %, t -1,76 | |
| Stratégies qui baissent | 2 sur 6 | 8 sur 8 | |

Statut mesuré. La moitié de l'hypothèse tient dans son ordre de grandeur, et
l'autre moitié ne tient pas : sur ces huit, la perte arrive avec la
publication, pas avant. La cause est la sélection, ces huit sont celles que
leurs années suivantes n'ont pas démenties. Le t de -1,76 dit qu'avec huit
unités, la mesure est un ordre de grandeur, pas un chiffre.

## Décision

Verdict `EXPERIMENTAL` : 0,667 contre 0,58, écart relatif 15 %, hors des 10 %.
La phase 11 est ouverte et sa première étude est faite. Le laboratoire dit
désormais en une phrase ce que ses huit réplications disaient une par une : la
publication laisse un quart à un tiers du rendement de l'article.

## Question suivante

La même mesure sur les portefeuilles de Chen et Zimmermann, pour avoir assez
d'unités et tester l'hétérogénéité que l'article annonce.

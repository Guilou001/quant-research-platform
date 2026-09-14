# Étude 013 : la question de l'étude 011 sur quarante ans de survivants

La [présentation guidée](README.md) explique les résultats et les précautions de lecture.
Cette annexe conserve les méthodes, les tableaux et les commandes de l’expérience initiale.
Les [corrections de rédaction](../../docs/research_journal/pedagogie-2026-09-13.md) précisent les interprétations révisées.

**Verdict : `REJECTED`, et le résultat est un avertissement plus qu'un
échec.** Sur 502 survivants du S&P 500 d'aujourd'hui rejoués depuis 1986, avec
cinq caractéristiques de prix seulement, les six méthodes rendent un R² mensuel
hors échantillon de 1,6 % à 1,7 %, quatre fois celui de Gu, Kelly et Xiu (2020),
une corrélation de rang positive à t 2,9, et des déciles long moins court dont
le ratio de Sharpe net va de 0,60 pour la régression à 0,85 pour les arbres,
sur 365 mois, avec un t de 5,1 et cinq sous-périodes sur cinq positives. Les
arbres ne battent pourtant pas la régression au test de Diebold et Mariano,
statistique -0,55, valeur p 0,58, ce qui est l'hypothèse de l'étude et ce qui
la rejette. Le panel sélectionne les entreprises présentes aujourd'hui.
La comparaison avec Kenneth French montre des écarts importants, sans isoler l'effet pur de cette sélection.
Les univers et certaines conventions de signal diffèrent également.

## La question de recherche

L'étude 011 avait rejeté les arbres sur onze ans et vingt-sept
caractéristiques, et sa question suivante était : est-ce l'historique qui
manque, ou le signal ? Cette étude donne aux mêmes méthodes quarante ans, au
prix d'un panneau de survivants et de cinq caractéristiques au lieu de
vingt-sept.

## L'article

Gu, S., Kelly, B. et Xiu, D. (2020), *Empirical Asset Pricing via Machine
Learning*, Review of Financial Studies 33(5), 2223-2273. Fiche :
[docs/literature/gu_kelly_xiu_2020.md](../../docs/literature/gu_kelly_xiu_2020.md).

## L'intuition économique

La question reprend celle de l'étude 011, avec un historique plus long et moins de caractéristiques.
Des interactions peuvent aider les arbres, mais leur présence ne garantit pas une amélioration détectable dans cet échantillon.
La sélection des survivants peut modifier les relations apprises, sans qu'une survie implique mécaniquement une remontée de chaque titre.

## La définition mathématique

Celle de l'étude 011 : rangs transversaux dans l'intervalle de moins un à plus
un, étiquette du mois suivant en excès du taux sans risque, R² hors échantillon
sans centrage, test de Diebold et Mariano à variance corrigée.

## Les données

| Source | Contenu | Mesure |
|---|---|---|
| Couche bronze du lac, `study002_sp500_daily` | prix ajustés Yahoo de 503 titres, 1985-01 à 2026-08 | 502 titres retenus, 486 mois de 1986-01 à 2026-06 |
| Kenneth French | taux sans risque mensuel, déciles de momentum et de renversement | même fenêtre |

Cinq caractéristiques de prix : momentum de douze mois sautant le dernier,
renversement à un mois, renversement de 36 à 13 mois, volatilité de douze
mois, rendement mensuel le plus élevé sur douze mois. Pas de taille, le panneau
ne portant pas la capitalisation. Panneau final : 184 177 lignes, 183 675
étiquetées, 379 titres par mois en moyenne. Source : `results/metrics.json`,
clé `coverage`.

**Le biais, déclaré et mesuré.** L'univers est celui du S&P 500 d'aujourd'hui,
rejoué dans le passé. L'étude 002 a mesuré ce que cela fait au momentum, et la
section sur le biais de survie ci-dessous le refait pour trois signaux.

## La méthodologie originale

Celle de l'article, résumée dans l'étude 011.

## Notre implémentation

Le script de l'étude 011 avec un autre chargeur. Six méthodes, treize
configurations. Analyse glissante ancrée, dix ans d'entraînement, un an de
test, purge d'un mois, trente plis de 1996-01 à 2025-12, configuration choisie
sur les vingt-quatre derniers mois de l'entraînement. Référence déclarée, la
régression pénalisée en carré ; modèle complexe, les arbres amplifiés. Forêt à
cent arbres au lieu de deux cents, déclaré. Déciles long moins court à 10
points de base par unité négociée.

## Nos écarts avec l'article

Ceux de l'étude 011, plus deux : cinq caractéristiques au lieu de
vingt-sept, et un univers de survivants au lieu de tout le CRSP.

## Les résultats

Tous les chiffres : `results/tables/evaluation.csv`, `diebold_mariano.csv`,
`portfolios.csv`, `folds.csv`, `metrics.json`. Hors échantillon, 365 mois de
1996-02 à 2026-06, brut de frais de gestion.

| Méthode | R² mensuel hors échantillon | Corrélation de rang moyenne, t | Sharpe net du décile long moins court | Sharpe brut | Rotation annuelle |
|---|---:|---:|---:|---:|---:|
| Moindres carrés | 1,64 % | 0,027, t 2,92 | 0,604 | 0,721 | 14,3 |
| Pénalisée en carré, référence | 1,64 % | 0,027, t 2,92 | 0,601 | 0,719 | 14,3 |
| Pénalisée en valeur absolue | 1,69 % | 0,029, t 2,95 | 0,650 | 0,749 | 13,0 |
| Filet élastique | 1,61 % | 0,020, t 1,78 | 0,654 | 0,737 | 10,2 |
| Arbres amplifiés, modèle complexe | 1,56 % | 0,024, t 2,77 | **0,849** | 0,936 | 11,1 |
| Forêt aléatoire | **1,69 %** | 0,026, t 3,13 | 0,807 | 0,899 | 12,1 |

Le tableau montre des écarts entre le panel retenu et les portefeuilles de Kenneth French.
Il ne mesure pas une intervention qui changerait uniquement la présence des titres disparus.
Le signal long utilise aussi des horizons différents, de 36 à 13 mois ici contre 60 à 13 mois dans le repère.
Ces écarts empêchent d'attribuer toute la performance au seul biais de survie.
Les tests statistiques ne réparent pas pour autant l'incomplétude du panel.

## La robustesse

Dix-sept essais déclarés. Sharpe dégonflé des arbres 1,000 pour ce compte,
probabilité de surapprentissage 0,057, cinq sous-périodes de six ans toutes
positives, ratios de 0,43, 1,45, 0,77, 0,79 et 1,12. Corrélation mensuelle avec
la parité de risque de l'étude 009 : -0,44. Tout cela vaut pour un panneau de
survivants, et la section précédente dit ce que cela vaut.

## Les coûts

À 10 points de base et 11 rotations par an, les coûts retirent 0,09 de Sharpe
aux arbres, 0,936 brut contre 0,849 net. Le décile survit à dix fois ce coût,
0,074 à 100 points de base. Statut modélisé.

## Le hors échantillon

Tout est hors échantillon au sens de l'analyse glissante ; il n'y a pas de
holdout séparé, comme dans l'étude 011.

## Les limites

| Limite | Statut |
|---|---|
| Univers de survivants, rejoué dans le passé | mesuré, section sur le biais de survie |
| Cinq caractéristiques, aucune comptable | reconnu |
| R² quatre fois celui de l'article | mesuré, lu comme un signe du biais et non comme un mérite |
| Forêt à cent arbres | déclaré |
| Coûts proportionnels seulement | modélisé |

## Le verdict

`REJECTED`, sur deux critères écrits avant le premier chiffre : les arbres ne
battent pas la régression au test de Diebold et Mariano, et le R² s'écarte
de la cible publiée de 169 % en relatif. Les huit autres critères passent, et
c'est là que le verdict dit moins que la mesure : un panneau de survivants
fait passer tous les contrôles statistiques du laboratoire à une stratégie qui
n'était pas négociable. La réponse à la question de l'étude 011 est donc
double. Avec quarante ans, la non-linéarité ne prévoit toujours pas mieux que
le linéaire. Et sans univers exempt de biais de survie, aucun des deux ne peut
être cru.

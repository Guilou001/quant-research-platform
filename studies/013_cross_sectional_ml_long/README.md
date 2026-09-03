# Étude 013 : la question de l'étude 011 sur quarante ans de survivants

**Verdict : `REJECTED`, et le résultat est un avertissement plus qu'un
échec.** Sur 502 survivants du S&P 500 d'aujourd'hui rejoués depuis 1986, avec
cinq caractéristiques de prix seulement, les six méthodes rendent un R² mensuel
hors échantillon de 1,6 % à 1,7 %, quatre fois celui de Gu, Kelly et Xiu (2020),
une corrélation de rang positive à t 2,9, et des déciles long moins court dont
le ratio de Sharpe net va de 0,60 pour la régression à 0,85 pour les arbres,
sur 365 mois, avec un t de 5,1 et cinq sous-périodes sur cinq positives. Les
arbres ne battent pourtant pas la régression au test de Diebold et Mariano,
statistique -0,55, valeur p 0,58, ce qui est l'hypothèse de l'étude et ce qui
la rejette. Et le panneau est un panneau de survivants : un titre qui a chuté
en 2008 et figure encore dans l'indice a remonté par construction, ce qu'un
modèle apprend sans effort. La section sur le biais de survie chiffre ce que la
survie fait à chacun des trois signaux qui ont un équivalent sans biais chez
Kenneth French.

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

Celle de l'étude 011 : si les interactions entre caractéristiques existent,
les arbres gagnent avec assez de données ; sinon, leur souplesse n'attrape que
le bruit. À quoi s'ajoute ici un mécanisme qui n'a rien d'économique : dans un
univers de survivants, les titres qui ont le plus baissé sont ceux qui ont le
plus remonté, puisque ceux qui ne sont pas remontés ont disparu de l'univers.
Un modèle qui achète les perdants de long terme et vend les gagnants y trouve
un rendement qui n'existait pas pour un investisseur de l'époque.

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

Comment lire ce tableau, en trois constats. Le premier est que tout est
positif, à toutes les échelles et pour toutes les méthodes, ce qui n'arrive
dans aucune autre étude du laboratoire. Le deuxième est que le R² vaut quatre
fois celui de l'article, sur un univers plus petit et avec cinq variables au
lieu de quatre-vingt-quatorze, ce qui ne se lit pas comme un mérite. Le
troisième est que les arbres et la forêt gagnent sur les déciles, 0,85 et 0,81
contre 0,60, mais pas sur la perte de prévision.

**Le test qui décide.** Diebold et Mariano contre la référence, 360 mois, cinq
retards : arbres amplifiés -0,55 (p 0,58), forêt +0,17 (p 0,87), pénalisée en
valeur absolue +1,57 (p 0,12), filet -0,55 (p 0,58), moindres carrés -1,27
(p 0,20). Aucune méthode ne prévoit mieux que la référence.

**Les plis.** Le R² des arbres par année de test va de -7,6 % en 2015 à +9,2 %
en 2013 ; huit années sur trente sont négatives. La corrélation de rang par
tranche de cinq ans reste positive pour les six méthodes de 1996 à 2026.

**Ce qui porte les arbres.** L'importance par permutation sur le dernier
bloc : volatilité de douze mois 0,82 point de R², renversement de long terme
0,20, momentum 0,15, renversement à un mois négatif. Le modèle est d'abord
un tri par la volatilité, puis un achat des perdants de long terme, le geste
que le biais de survie récompense.

## Le biais de survie, mesuré

Source : `results/tables/survivorship_control.csv`. Pour chacun des trois
signaux qui ont un décile publié par Kenneth French, le même écart, décile
haut moins décile bas du signal, est calculé sur nos survivants et sur les
déciles CRSP, qui incluent les sociétés radiées. Fenêtre de test, 1996-01 à
2025-12, 360 mois, brut. Le renversement de long terme de French porte sur 60
à 13 mois, le nôtre sur 36 à 13, écart déclaré.

| Signal, décile haut moins bas | Survivants, %/an | Survivants, Sharpe | Kenneth French, %/an | Kenneth French, Sharpe | Corrélation des deux |
|---|---:|---:|---:|---:|---:|
| Momentum de douze mois sautant le dernier | 1,5 | 0,05 | 7,3 | 0,24 | 0,83 |
| Rendement du dernier mois | -5,5 | -0,26 | 0,0 | 0,00 | 0,82 |
| Rendement de 36 à 13 mois | -7,1 | -0,39 | 1,7 | 0,08 | 0,59 |

Comment lire ce tableau, en trois constats. Le premier est que la survie ne
flatte pas le momentum, elle l'affaiblit de 5,8 points par an, ce que l'étude
002 avait mesuré. Le deuxième est qu'elle fabrique deux renversements : acheter
les perdants du dernier mois rapporte 5,5 % par an chez les survivants et rien
sur le CRSP ; acheter les perdants de long terme rapporte 7,1 % par an chez les
survivants et coûte 1,7 % sur le CRSP. Un titre encore dans l'indice a
remonté, et un modèle l'apprend sans effort. Le troisième est que l'importance
par permutation désigne précisément le renversement de long terme et la
volatilité comme les deux variables qui portent les arbres. Le rendement des
déciles de cette étude est donc, pour l'essentiel, celui du biais, et aucun
des huit critères statistiques qu'il passe ne pouvait le voir : ils testent la
stabilité d'un signal, pas son existence pour un investisseur de l'époque.

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

# Feuille de route : ce qu'il faut construire pour des stratégies meilleures, et ce qu'il ne faut pas attendre

**La réponse en une phrase**. Le laboratoire ne manque ni de moteur ni de
contrôles, il manque de largeur, de données sans biais de survie et d'un
modèle d'exécution. Les six chantiers ci-dessous les apportent dans l'ordre
où la littérature et nos propres mesures disent qu'ils comptent. Aucun ne
promet le rendement d'un grand fonds fermé, pour des raisons mesurées.

Écrite le 2026-09-03, après l'audit des phases 9 et 11. Chaque affirmation
porte son statut : mesuré dans ce dépôt, rapporté d'une source nommée, ou
modélisé sous hypothèse déclarée.

## D'où l'on part, mesuré

Quatorze études, 809 essais, aucune stratégie qui mérite du capital. Les huit
stratégies répliquées valent 5,4 paris indépendants ensemble (étude 009). Leur
rendement après publication vaut un quart à un tiers de celui de l'article
(étude 014), et les coûts emportent le reste (étude 012). Les deux stratégies
chiffrables ont une capacité de 85 000 dollars et de zéro (étude 010). Un
panneau de survivants fait passer tous les contrôles à une stratégie qui
n'existait pas (étude 013). La convention d'exécution du moteur mensuel vaut
25 points de base par an, et une séance de retard en vaut 71 (phase 9).

## Pourquoi un grand fonds fermé n'est pas l'objectif, rapporté et mesuré

Le rendement d'un gestionnaire actif suit la loi fondamentale de Grinold
(1989) : le ratio d'information vaut la qualité de prédiction multipliée par
la racine du nombre de paris indépendants. Rapporté, et c'est le modèle
mental du README. Le seul grand fonds dont les rendements ont été analysés
académiquement est Medallion, décrit par Cornell (2020, Journal of Portfolio
Management, résumé lu le 2026-09-03). C'est un fonds à levier d'environ 12,5
fois, à bêta de marché voisin de -1, à détention de l'ordre de deux jours, sur
des centaines de milliers d'ordres par jour. Il est fermé au capital
extérieur depuis 1993, et son rendement estimé avant frais et après
financement est de 32,6 % par an selon le même article. Rapporté, non revérifié à la source.

Ce que le laboratoire mesure de son côté tient en trois nombres. Huit paris
mensuels, un alpha qui décroît de 67 à 73 % après publication, une capacité
de 85 000 dollars sur le seul momentum de fonds cotés. Le rapport des largeurs, quelques paris par mois
contre des centaines de milliers par jour, suffit à expliquer l'écart des
ratios de Sharpe sans invoquer une qualité de signal différente. Un dépôt en
données libres ne rejoindra pas ce régime, et la feuille de route ne le
prétend pas. Elle vise ce qui est atteignable : des stratégies qui passent le
parcours de vingt étapes et atteignent `ROBUST`, ce qu'aucune n'a fait.

## Les six chantiers, dans l'ordre

| Ordre | Chantier | Ce qu'il débloque | Ce qu'il coûte | Statut de l'attente |
|---|---|---|---|---|
| 1 | Un univers d'actions sans biais de survie | tout travail transversal sur actions ; l'étude 013 est aujourd'hui non concluante par construction | **mesuré le 2026-09-04, étude 015** : le forfait gratuit de Polygon donne deux ans de prix et refuse 2008 ; le référentiel des radiations, lui, est entier | mesuré, le biais fabrique 7,1 %/an de faux renversement |
| 2 | La largeur : 210 signaux plutôt que 5 | la loi fondamentale, de 5,4 paris à des dizaines ; l'étude 014 refaite sur 200 prédicteurs | **fait le 2026-09-04, étude 016** : fournisseur écrit, 208 prédicteurs mesurés | mesuré : médiane 58 % de baisse après publication, part perdue indépendante de la force |
| 3 | L'exécution : viser devant la cible | réduire la rotation qui tue l'arbitrage statistique et coûte 71 pb/an au momentum | **fait le 2026-09-04, étude 017**, forme simple | mesuré, `REJECTED` : la rotation divisée par 1,6 ne rattrape pas le retard sur le signal |
| 4 | L'horizon : nuit contre journée | savoir quand chacune des huit stratégies gagne ; les barres à la minute existent déjà | **fait le 2026-09-04, étude 018** | mesuré : le momentum temporel gagne 10,2 %/an la nuit et perd 3,0 % le jour, t 3,8 |
| 5 | Les données publiques point-in-time que personne ne lit | 13F, formulaires 4 d'initiés, dérive post-annonce sur XBRL, l'atout du laboratoire | **fait pour les 13F le 2026-09-04, étude 020** : fournisseur des jeux 13F, unité lue déclaration par déclaration, correspondance OpenFIGI ; formulaires 4 et dérive post-annonce restent à faire | mesuré, `REJECTED` : +0,27 %/an sur le marché, t 0,26, bêta 1,08 ; 28,9 % des idées sans prix |
| 6 | Un marché moins efficace : les cryptomonnaies | les mêmes facteurs, marché, taille, momentum, sur un marché jeune et ouvert | **fait le 2026-09-04, étude 019** : fournisseur Coin Metrics écrit, 139 actifs à prix daté | mesuré, `REJECTED` : les cinq sixièmes du rendement perdus après publication, le momentum tourne 204 % par semaine |
| 7 | Le portefeuille de primes, pré-inscrit | tendance, valeur et momentum, vente de puts, inverse de volatilité, empilement à cible de volatilité | **fait le 2026-09-04, étude 021** : spécification 007, fournisseur Cboe et module d'empilement écrits et testés | mesuré, `REJECTED` de justesse : Sharpe net 0,629, holdout 0,88, mais la meilleure jambe seule fait 0,696 et la tendance sur fonds cotés coûte 0,25 |

Comment lire ce tableau, en trois constats. Le premier est que le chantier 1
conditionne les chantiers 2 et 5 : sans univers avec radiations, un signal
transversal sur actions ne peut pas être cru, et le laboratoire l'a mesuré.
Le deuxième est que les chantiers 3 et 4 n'exigent aucune donnée nouvelle et
s'appliquent aux huit stratégies existantes, donc ils viennent en premier si
le budget de données est nul. Le troisième est que la colonne de droite
porte des chiffres rapportés, ceux des articles, et que chaque chantier se
termine par une étude du laboratoire qui les mesure à son tour.

## Chantier 1 : un univers qui garde les sociétés radiées

La question : que vaut un signal transversal quand on sait qui a disparu ? La
spécification est écrite,
[001-univers-sans-biais-de-survie](specs/001-univers-sans-biais-de-survie.md),
avec quatre critères d'acceptation mesurables, dont la reprise du contrôle de
l'étude 013. La source candidate est Polygon, dont la documentation annonce
que les titres radiés gardent leur historique et que les symboles ne sont pas
réemployés en silence. Rapporté, à mesurer sur le forfait de l'auteur avant
de coder. L'alternative sans coût n'existe pas : les sources libres du dépôt
ne donnent aucune radiation, mesuré le 2026-09-01.

## Chantier 2 : la largeur par les 210 signaux de Chen et Zimmermann

La question : combien de paris indépendants un univers d'actions porte-t-il
réellement, une fois 210 caractéristiques publiées mises ensemble ? Le jeu
d'Open Source Asset Pricing, cité dans le tableau des sources du README,
porte 210 prédicteurs mensuels de 1925 à 2022 et le code qui les construit.
Chen et Zimmermann (2022, Critical Finance Review) rapportent que 98 % des
161 signaux nettement significatifs à l'origine gardent un t supérieur à
1,96 chez eux. Deux études en sortent. La première refait l'étude 014 sur
deux cents prédicteurs au lieu de huit, ce qui donne enfin la puissance pour
tester l'hétérogénéité que McLean et Pontiff annoncent. La seconde nourrit les
six méthodes de l'étude 011 avec ces caractéristiques, sur l'univers du
chantier 1, et mesure la largeur effective par la formule d'équicorrélation
du README. Limite déclarée : la licence du jeu est à lire avant tout usage,
et ses signaux sont construits sur CRSP, donc leur rejeu sur un autre univers
est une réplication, pas une copie.

## Chantier 3 : viser devant la cible

La question : quelle part de la rotation est nécessaire ? Le moteur rééquilibre
vers la cible à chaque date, et l'étude 007 a mesuré que l'arbitrage
statistique meurt à 3,92 points de base. Gârleanu et Pedersen (2013, Journal
of Finance) donnent la règle en forme fermée : ne négocier qu'une fraction du
chemin vers un portefeuille cible qui pondère chaque signal par la vitesse à
laquelle il s'éteint. Rapporté : ils l'appliquent à des contrats à terme sur
matières premières et rapportent un rendement net supérieur aux références
naïves, avec un Sharpe brut plus bas et des replis moins profonds. Le
laboratoire a tout ce qu'il faut pour le mesurer : les huit séries, leurs
coûts, et un optimiseur qui accepte déjà un coût de transaction. L'étude
compare, pour chaque stratégie, la cible complète et la cible partielle,
nettes, sur le holdout.

## Chantier 4 : la nuit contre la journée

La question : quand chacune des huit stratégies gagne-t-elle ? Lou, Polk et
Skouras (2019, Journal of Financial Economics) rapportent, sur quatorze
stratégies, que le momentum gagne la nuit et que la valeur, la rentabilité et
l'investissement gagnent le jour. Les signes sont opposés d'une période à
l'autre. Le portefeuille de Guillaume porte déjà les barres à la minute et les
deux fournisseurs, dépôts 21 à 24, et `gvf.marches` les lit. L'étude
décompose les huit séries de tête en composante de nuit et de jour, sur les
fonds cotés qui les portent, et dit laquelle des deux tient après publication.
Ce n'est pas une stratégie nouvelle, c'est une mesure qui décide où placer
l'exécution des chantiers suivants.

## Chantier 5 : ce que la SEC publie et que peu de gens lisent en point-in-time

La question : un signal construit sur des dépôts publics datés à la seconde
survit-il à ses coûts ? Le laboratoire est le seul du portefeuille à porter
des fondamentaux point-in-time, et la SEC répond depuis le 2026-09-01. Trois
sources, dans l'ordre du rapport signal sur coût attendu. Les positions 13F
des gestionnaires, avec leur délai de quarante-cinq jours. Cohen, Polk et
Silli (2010) rapportent que les plus grosses positions actives des
gestionnaires battent leur portefeuille, et des travaux ultérieurs rapportent
un alpha des clones même après le délai. Les formulaires 4 des initiés. La
dérive après annonce de résultats sur les dates d'acceptation XBRL. La
littérature récente rapporte qu'elle décline et ne subsiste que sur les
petites capitalisations, ce qui en fait un bon test du chantier 1 plus qu'une
source de rendement. Chacune est une étude à part entière avec son article de
référence, et chacune dépend du chantier 1 pour l'univers.

## Chantier 6 : un marché moins efficace, avec le même parcours

La question : les facteurs qui ont décru sur les actions existent-ils encore
là où le capital académique est arrivé tard ? Liu, Tsyvinski et Wu (2022,
Journal of Finance) rapportent trois facteurs, marché, taille et momentum,
sur 1 827 monnaies de 2014 à 2020. Le momentum hebdomadaire y est de l'ordre
de 3 % dans leur échantillon, et il tient hors échantillon dans leur propre
découpage. Les données d'échange sont libres et continues. Le laboratoire y
appliquerait exactement son parcours, coûts compris, avec l'avantage que la
fenêtre après publication commence en 2022 et se mesure déjà. Limite
déclarée : un marché de dix ans donne dix ans, et le ratio de Sharpe dégonflé
le sait.

## Ce qui reste hors feuille de route, et pourquoi

Le levier, l'intrajournalier à grande échelle et l'exécution propriétaire des
grands fonds ne se construisent pas en données libres. Un dépôt qui les
simulerait publierait des chiffres qu'aucune exécution ne reproduirait,
contre la règle 7. Un modèle de risque factoriel maison et un ciblage de volatilité au niveau du
portefeuille sont utiles mais ne créent pas de rendement. L'étude 006 a
mesuré que le ciblage seul rapporte -1,30 % par an net. Ils viendront avec le
chantier 2, quand il y aura un portefeuille à tenir. Enfin, la phase 9 ne se refait que pour une stratégie `ROBUST`, et le
pont est prêt.

## Ce qui décide, à chaque chantier

Le même verdict qu'aujourd'hui, écrit avant le premier chiffre dans la
configuration de l'étude. Un chantier réussit si une stratégie atteint
`ROBUST` sous les vingt étapes, coûts et univers avec radiations compris, ou
si la mesure qu'il visait est publiée avec son statut. Un chantier qui rend
`REJECTED` a réussi aussi, et il entre au registre des idées rejetées avec
ses essais.

## Sources

Rapportées, consultées le 2026-09-03 sauf mention. Grinold (1989), *The
Fundamental Law of Active Management*, Journal of Portfolio Management.
Cornell (2020), *Medallion Fund: The Ultimate Counterexample?*, Journal of
Portfolio Management, résumé et billet de l'auteur. Chen et Zimmermann (2022),
*Open Source Cross-Sectional Asset Pricing*, Critical Finance Review 11(2),
207-264, et openassetpricing.com. Gârleanu et Pedersen (2013), *Dynamic
Trading with Predictable Returns and Transaction Costs*, Journal of Finance
68(6), 2309-2340. Lou, Polk et Skouras (2019), *A Tug of War: Overnight
versus Intraday Expected Returns*, Journal of Financial Economics 134(1),
192-213. Cohen, Polk et Silli (2010), *Best Ideas*, document de travail, cité
par la littérature sur les clones 13F. Liu, Tsyvinski et Wu (2022), *Common
Risk Factors in Cryptocurrency*, Journal of Finance 77(2), 1133-1177.
Documentation de Polygon sur les titres radiés, page produit. Aucun de ces
articles n'a été lu en entier pour cette page ; leurs résumés l'ont été.

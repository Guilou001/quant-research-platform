# Les repères de comparaison

Un résultat sans repère ne se lit pas. Ce répertoire porte les comparaisons
auxquelles toute stratégie est confrontée, et la règle qui gouverne leur choix.

## La règle

Le repère se choisit **avant** de voir le résultat, et il est celui qu'un
investisseur aurait réellement pu détenir à la place. Choisir un repère faible
après coup est la façon la plus simple de faire passer une stratégie médiocre
pour bonne.

## Les repères retenus

| Repère | Quand il s'applique |
|---|---|
| Taux sans risque | toute stratégie, comme plancher absolu |
| S&P 500 total return | toute stratégie actions long only |
| Portefeuille 60/40 | toute stratégie multi-actifs |
| Équipondéré de l'univers | toute stratégie de sélection, c'est le repère le plus dur |
| Facteurs de Fama et French | toute stratégie actions, en régression |
| Jeux de facteurs AQR | les réplications de BAB, QMJ, valeur et momentum |
| Les résultats de l'article original | toute réplication |

L'équipondéré mérite une note. DeMiguel, Garlappi et Uppal (2009) montrent
qu'il est beaucoup plus difficile à battre que la théorie ne le laisse croire.
Une stratégie d'allocation qui ne le bat pas hors échantillon n'apporte rien,
quelle que soit son élégance.

## Les fonds réels, pour comparer les trajectoires

Le registre `funds.yaml` porte douze fonds cotés, un ou deux par famille de
stratégie, qui vendent au public ce que le laboratoire reconstruit. Le module
`quantlab.analytics.comparison` mesure si une stratégie et un fonds bougent
ensemble : corrélation des rendements, pente de l'un sur l'autre, part de
trajectoire expliquée, recouvrement des replis, corrélation glissante.

Trois choses à savoir avant de lire une comparaison. Les fonds sont nets de
frais et les reconstructions brutes, donc l'alpha du fonds sur la stratégie
porte les frais avec le signe moins. Les fonds de facteurs datent presque tous
de 2013, donc la comparaison couvre une dizaine d'années, après publication des
articles. Et il faut comparer ce qui se compare : un fonds long seulement suit
la jambe longue d'un facteur, pas son écart long moins court.

## Résultat mesuré le 2026-09-02

Les facteurs publiés par les auteurs contre les fonds qui les vendent,
mensuels, période commune. Fichier :
`results/facteurs_publies_contre_fonds_reels_2026-09-02.csv`.

| Facteur publié | Fonds | Mois | Corrélation | Bêta | R² | Replis communs | Lecture |
|---|---|---:|---:|---:|---:|---:|---|
| TSMOM (AQR) | AQMIX, le fonds des auteurs | 197 | **0,755** | 0,575 | 0,570 | 0,679 | même phénomène |
| TSMOM (AQR) | KMLM | 66 | 0,669 | 0,667 | 0,447 | 0,725 | apparenté |
| TSMOM (AQR) | DBMF | 85 | 0,603 | 0,496 | 0,363 | 0,485 | apparenté, autre échelle |
| Décile gagnant 12-2 (Ken French) | MTUM, long seulement | 159 | **0,887** | 0,658 | 0,787 | 0,571 | même phénomène |
| BAB USA (AQR) | BTAL | 178 | 0,484 | 0,829 | 0,234 | 0,240 | apparenté |
| BAB USA (AQR) | USMV, long seulement | 177 | 0,192 | 0,248 | 0,037 | 0,271 | distinct |
| QMJ USA (AQR) | QUAL, long seulement | 156 | **-0,372** | -0,555 | 0,138 | 0,122 | distinct |
| Momentum long-court (VME) | MTUM, long seulement | 159 | 0,249 | 0,332 | 0,062 | 0,273 | distinct |
| Valeur long-court (VME) | VLUE, long seulement | 159 | 0,159 | 0,225 | 0,025 | 0,375 | distinct |
| TSMOM (AQR) | QSPIX, multi-stratégies | 152 | 0,133 | 0,125 | 0,018 | 0,451 | distinct |
| BAB USA (AQR) | QMNIX, neutre au marché | 141 | 0,167 | 0,178 | 0,028 | 0,191 | distinct |

Comment lire ce tableau, en quatre constats. Le premier est que le facteur
TSMOM et le fonds que ses propres auteurs gèrent bougent ensemble, 0,755 de
corrélation et 68 % de replis communs, à une échelle réduite de moitié : le
fonds vise une volatilité plus basse que le facteur. Le deuxième est que le
décile gagnant de Ken French explique 79 % de la trajectoire de MTUM, alors que
l'écart long moins court n'en explique que 6 % : un fonds long seulement suit la
jambe longue, et comparer l'écart au fonds est une erreur de catégorie. Le
troisième est que QMJ et QUAL sont corrélés NÉGATIVEMENT, -0,372, parce que le
facteur qualité porte un bêta de marché négatif alors que le fonds long
seulement en porte un proche de un. Le quatrième est que BTAL, la mise en oeuvre
cotée la plus proche du BAB, n'en capte que 23 % de la trajectoire et perd de
l'argent là où le facteur en gagne, avec un alpha de -8,16 % par an qui est le
prix de sa construction en dollars égaux et de ses 245 points de base de frais.

Ce que ce tableau n'établit pas : il compare des facteurs PUBLIÉS aux fonds, pas
nos propres reconstructions. Celles-ci sont enregistrées depuis le 2026-09-02
dans le `results/series/` de chaque étude, et l'étude 009 compare son
portefeuille à QSPIX par le même module : corrélation 0,341, lecture
« distinct ».

## Les grands fonds fermés, sur rendements annuels rapportés

Les fonds qui dominent le classement du secteur, Medallion, Wellington,
Composite, Millennium ou Pure Alpha, ne vendent pas leur part et ne publient
aucune série de rendements. Ce qui existe est annuel, rapporté par la presse ou
par un livre, et souvent contradictoire d'une source à l'autre. Le registre
`hedge_funds.yaml` porte ces chiffres, année par année, avec la source de chacun
et le degré de vérification atteint le 2026-09-02 : 51 valeurs lues à la source,
8 lues dans le seul titre d'un article, 22 tirées d'un résumé de recherche. Une
année absente est une année non trouvée, jamais une année à zéro.

La comparaison est faite par `compare_hedge_funds.py` contre la parité de risque
de l'étude 009, la référence déclarée avant tout calcul, nette de coûts de
transaction et brute de frais de gestion. Fichiers :
`results/fonds_fermes_contre_portefeuille_009_2026-09-02.csv`,
`results/fonds_fermes_rendements_annuels_2026-09-02.csv` et les quatre figures
de `results/figures/fonds_fermes_*`.

Quatre choses à savoir avant de lire le tableau. La comparaison porte sur des
années civiles COMMUNES, et il y en a peu : neuf avec Medallion, sept avec
Wellington, six avec Composite. Une corrélation sur sept points porte un
intervalle de confiance qui couvre presque tout, et il est écrit à côté. Les
fonds sont nets de frais, le portefeuille du laboratoire ne l'est pas. Le
portefeuille tourne à 3,6 % de volatilité annualisée, mesuré, quand ces fonds en
portent de 6 à 20 % ; la colonne « à 10 % de volatilité » met le rendement à
l'échelle par un facteur constant, statut modélisé, sans rien changer au ratio
de Sharpe. Enfin, l'année 2020 manque au portefeuille : la série de portage de
change de l'étude 008 n'a pas d'avril 2020, l'intersection de l'étude 009 a donc
onze mois cette année-là, et une année incomplète n'est pas comparée. Ce trou
est un défaut à corriger dans l'étude 008.

| Fonds | Années communes | Corrélation annuelle | Intervalle à 95 % | Moyenne du fonds | Moyenne du laboratoire | Même chose à 10 % de vol. | Pire année du fonds | Lecture |
|---|---:|---:|---|---:|---:|---:|---:|---|
| Medallion (Renaissance) | 9, 2010-2018 | 0,38 | -0,38 à 0,83 | 37,6 % | 3,5 % | 9,8 % | 29,0 % | aucun co-mouvement établi |
| Wellington (Citadel) | 7, 2018-2025 | **0,79** | 0,10 à 0,97 | 19,0 % | 1,3 % | 3,4 % | 9,1 % | co-mouvement établi |
| Composite (D.E. Shaw) | 6, 2019-2025 | 0,76 | -0,14 à 0,97 | 16,7 % | 1,2 % | 3,1 % | 9,6 % | aucun co-mouvement établi |
| Pure Alpha (Bridgewater) | 5, 2018-2025 | 0,24 | -0,81 à 0,93 | 10,6 % | -0,2 % | -1,0 % | -7,6 % | aucun co-mouvement établi |
| TCI Master Fund | 6, 2017-2025 | -0,62 | -0,95 à 0,38 | 21,2 % | 1,8 % | 5,0 % | -18,0 % | aucun co-mouvement établi |
| Millennium, Point72, Balyasny | 4 chacun | non publiée | | 10,7 à 14,1 % | | | | trop peu d'années |
| Oculus, Apex, Elliott | 2 à 3 | non publiée | | | | | | trop peu d'années |

Statut : moyennes des fonds rapportées ; moyennes du laboratoire mesurées sur
les années communes ; colonne à 10 % de volatilité modélisée.

Comment lire ce tableau, en quatre constats. Le premier est que le portefeuille
du laboratoire n'est pas dans la même catégorie que ces fonds, et que la mise à
l'échelle ne l'y met pas : à 10 % de volatilité il rend 7,1 % par an en moyenne
sur 2010-2025, contre 37,6 % pour Medallion net de frais sur 2010-2018, dont
Cornell (2019) rapporte un ratio de Sharpe supérieur à 2 quand le nôtre vaut
0,65. Le deuxième est que le seul co-mouvement dont l'intervalle exclut zéro
est celui avec Wellington, 0,79 sur sept années, et que sa borne basse est à
0,10 : c'est un indice, pas une preuve. Le troisième est que le portefeuille
ne bat aucun de ces fonds une seule année sur les années communes, sauf
Pure Alpha deux années sur cinq et TCI une sur six, les deux fonds qui ont
connu une année négative. Le quatrième est que la corrélation négative avec
TCI, un fonds d'actions concentré, dit ce que le portefeuille est : un panier
de facteurs neutres au marché, qui ne monte pas quand les actions montent.

Ce que la comparaison n'établit pas : rien sur la trajectoire mensuelle, que
ces fonds ne publient pas, et rien de robuste sur moins de dix années communes.
Les repères solides restent les fonds cotés de `funds.yaml`, dont la série
mensuelle est mesurée.

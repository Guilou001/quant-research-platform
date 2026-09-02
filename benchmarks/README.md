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
encore nos propres reconstructions. Les huit études n'ont pas enregistré leurs
séries de rendements mensuels, et c'est la première correction de la phase
suivante.

# Étude 012 : le portefeuille de l'étude 009 sur les séries nettes de chaque stratégie

**Verdict : `REJECTED`, et plus nettement que l'étude 009.** Sur les séries
nettes de leurs propres coûts, la parité de risque déclarée à l'avance rend un
ratio de Sharpe hors échantillon de -0,128 sur 2010-2026, contre 0,535 pour la
meilleure stratégie seule, le mélange de valeur et de momentum. Aucune des six
allocations ne bat cette jambe. Le gain de diversification que l'étude 009
mesurait sur les séries brutes venait pour l'essentiel de l'arbitrage
statistique, dont la version nette rend -0,932 et retire à elle seule 0,379
de Sharpe au portefeuille. Tous les chiffres viennent de `results/`, fichier
cité à chaque tableau.

## La question de recherche

L'étude 009 avait combiné huit séries BRUTES, pour qu'elles soient comparables,
et trouvé que trois allocations sur six battaient la meilleure jambe. Le
journal posait la question suivante : le même exercice avec les séries NETTES
donne-t-il encore un mélange au-dessus de la meilleure jambe ? Les coûts propres
à l'arbitrage statistique, qui apportait le plus, sont ceux qui le tuent dans
l'étude 007.

## L'article

Les mêmes trois références que l'étude 009 : Grinold (1989) pour la loi
fondamentale, DeMiguel, Garlappi et Uppal (2009) pour le repère
équipondéré, Asness, Moskowitz et Pedersen (2013) pour la corrélation entre
valeur et momentum.

## L'intuition économique

Combiner des paris peu corrélés multiplie l'avantage par la racine de leur
nombre effectif. Mais la loi fondamentale suppose que chaque pari a un
avantage : un pari dont l'espérance nette est négative ne se diversifie pas, il
se paie. Passer du brut au net ne change pas les corrélations, il change le
signe de trois des huit paris.

## La définition mathématique

Celle de l'étude 009, inchangée : covariance de Ledoit et Wolf réestimée
chaque année sur le seul passé, six optimiseurs de `quantlab.portfolio`, un
holdout du 2020-01-31 jamais consulté avant la validation, 5 points de base
par unité de rotation du rééquilibrage entre stratégies.

## Les données

Source : `config.yaml` et `results/series/index.json` de chaque étude.

| Stratégie | Série employée | Base |
|---|---|---|
| Momentum temporel | `tsmom_etf_net` | nette, étude 001 |
| Momentum transversal | `xsmom_survivors_net` | nette, survivants, étude 002 |
| Valeur et momentum | `value_momentum_blend_net` | nette, étude 003 |
| Qualité | `qmj_published_usa_gross` | brute, aucune version nette n'existe |
| Bêta défensif | `bab_kf_deciles_net` | nette, étude 005 |
| Gestion de volatilité | `hedged_spread_real_time_gross` | brute, aucune version nette n'existe |
| Arbitrage statistique | `statarb_net` | nette, 5 points de base, étude 007 |
| Portage de change | `fx_carry_net` | nette, étude 008, série corrigée du 2026-09-03 |

Deux écarts avec l'étude 009 vont au-delà du passage au net. Le momentum
transversal passe des déciles CRSP de Kenneth French, sans coût, à la version
sur survivants qui porte ses coûts, parce que seule celle-ci a une version
nette. Et deux séries restent brutes, faute de version nette ; elles sont
déclarées telles quelles plutôt que chargées d'un coût inventé. Fenêtre commune
2007-01 à 2026-06, 234 mois.

## La méthodologie originale

Celle de l'étude 009, reprise sans modification : le seul changement est la
table des séries.

## Notre implémentation

Le script est celui de l'étude 009, copié, avec un nom d'étude et une table de
séries différents. Référence déclarée avant tout calcul : la parité de risque.
Vingt essais déclarés, les mêmes.

## Nos écarts avec l'article

Ceux de l'étude 009, plus le passage au net.

## Les résultats

**Seules, trois stratégies sur huit sont négatives nettes.** Source :
`results/tables/strategies_alone.csv`, 2007-01 à 2026-06, 234 mois.

| Stratégie | Sharpe | Volatilité %/an | Pire repli |
|---|---:|---:|---:|
| Valeur et momentum, net | **0,535** | 3,0 | -11,6 % |
| Qualité, brut | 0,297 | 9,9 | -36,0 % |
| Momentum temporel, net | 0,217 | 17,2 | -35,9 % |
| Portage de change, net | 0,106 | 6,9 | -27,9 % |
| Bêta défensif, net | -0,085 | 11,7 | -46,1 % |
| Gestion de volatilité, brut | -0,240 | 14,9 | -77,7 % |
| Momentum transversal, survivants, net | -0,286 | 11,9 | -74,2 % |
| Arbitrage statistique, net | **-0,932** | 10,1 | -86,4 % |

**Aucune allocation ne bat la meilleure jambe.** Source :
`results/tables/portfolios_walk_forward.csv`, net, 199 mois du 2009-12 au
2026-06, échantillon `OOS`.

| Allocation | Sharpe | Vol. %/an | Pire repli | Avant 2020 | Holdout 2020-2026 |
|---|---:|---:|---:|---:|---:|
| Équipondération | -0,182 | 4,8 | -25,8 % | 0,044 | -0,433 |
| Inverse de volatilité | -0,084 | 3,9 | -19,6 % | 0,124 | -0,314 |
| **Parité de risque, référence** | **-0,128** | 3,4 | -18,7 % | 0,100 | -0,396 |
| Variance minimale | 0,123 | 2,8 | -11,2 % | 0,252 | -0,023 |
| Parité hiérarchique | 0,057 | 2,9 | -12,5 % | 0,058 | 0,057 |
| Moyenne-variance | 0,250 | 5,1 | -14,3 % | 0,370 | 0,137 |

Comment lire ce tableau, en trois constats. Le premier est que les
corrélations n'ont presque pas bougé, moyenne 0,093 et largeur effective 5,48
contre 0,095 et 5,37 dans l'étude 009 : la diversification est intacte, ce
sont les paris qui ont perdu leur signe. Le deuxième est que la parité de
risque, qui alloue par le risque et non par l'espérance, donne du poids aux
séries négatives, et rend moins que la variance minimale ou la
moyenne-variance ; aucune ne dépasse pourtant 0,535. Le troisième est que
le holdout est négatif pour quatre allocations sur six.

**L'apport marginal a changé de signe pour l'arbitrage statistique.** Source :
`results/tables/marginal_contribution.csv`.

| Stratégie retirée | Sharpe sans elle | Apport marginal |
|---|---:|---:|
| Valeur et momentum | -0,269 | **+0,141** |
| Qualité | -0,241 | +0,113 |
| Momentum temporel | -0,203 | +0,075 |
| Portage de change | -0,203 | +0,075 |
| Bêta défensif | -0,201 | +0,073 |
| Momentum transversal | -0,103 | -0,025 |
| Gestion de volatilité | 0,006 | -0,134 |
| Arbitrage statistique | 0,251 | **-0,379** |

Sans l'arbitrage statistique, la parité de risque monterait à 0,251 ; dans
l'étude 009 il apportait +0,250. La même série, brute puis nette, est passée du
premier apport au premier fardeau, et c'est le résultat de l'étude.

## La robustesse

Vingt essais déclarés. Probabilité de surapprentissage 0,10, Sharpe dégonflé
0,034, une sous-période sur quatre positive, 2014-2018 à 0,568 ; les trois
autres sont négatives. Source : `results/tables/subperiods.csv` et
`results/metrics.json`.

## Les coûts

Source : `results/tables/cost_multiples.csv`. Le portefeuille est déjà négatif
à un multiple de un, -0,128, et descend à -0,165 à vingt fois le coût de
rééquilibrage ; aucun multiple n'est survécu. La rotation entre stratégies,
0,07 par an, n'y est pour rien : ce sont les coûts internes des séries qui
décident.

## Le hors échantillon

Holdout du 2020-01-31 au 2026-06-30, 78 mois, consulté à la seule étape de
validation : parité de risque à -0,396, t de -0,967. Contre QSPIX sur 153
mois, corrélation 0,36, ratio de Sharpe -0,161 contre 0,649 pour le fonds.
Source : `results/tables/benchmark_fund.csv`.

## Les limites

Deux séries sur huit restent brutes, faute de version nette, ce qui flatte le
résultat. Les coûts internes de chaque série sont ceux de son étude, tous
modélisés. Le momentum transversal net porte un biais de survie déclaré dans
l'étude 002. La fenêtre de 234 mois est courte pour huit stratégies.

## Le verdict

**`REJECTED`**, déduit par `quantlab.reporting.study.decide_verdict` depuis les
seuils écrits avant les résultats. Source : `results/tables/verdict_reasons.csv`.
L'hypothèse échoue, -0,128 contre 0,535 ; le signe du Sharpe hors échantillon
échoue, -0,396 ; le t vaut -0,967 contre 3 exigés ; le Sharpe dégonflé 0,034
contre 0,95 ; une sous-période sur quatre est positive contre 60 % exigés ;
aucun multiple de coûts n'est survécu. Ce que l'étude établit : la
diversification de l'étude 009 était réelle et sans valeur, parce qu'elle
diversifiait des paris dont la moitié perd une fois leurs coûts payés.

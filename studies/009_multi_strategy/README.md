# Huit sources d'alpha, un portefeuille

**Le mélange bat la meilleure stratégie seule pour quatre allocations sur six,
et pas pour celle qui avait été désignée à l'avance.** La parité de risque,
choisie comme référence dans `config.yaml` avant tout calcul, rend un ratio de
Sharpe hors échantillon de 0,652 contre 0,693 pour l'arbitrage statistique pris
seul. La parité de risque hiérarchique rend 0,900 sur la même fenêtre, avec un
pire repli de -4,3 %. Prendre cette dernière comme référence après l'avoir vue
gagner serait exactement le surapprentissage que ce laboratoire existe pour
mesurer, et le verdict est donc `REJECTED`. Tous les chiffres viennent de
`results/`, fichier cité à chaque tableau.

## La question de recherche

Huit stratégies dont aucune n'a atteint `ROBUST` peuvent-elles, ensemble,
valoir plus que la meilleure d'entre elles ? En mots simples : est-ce que huit
paris médiocres et différents font un bon pari ?

La question est celle de la phase 7, et c'est la raison d'être du laboratoire.
Une stratégie de ratio de Sharpe 0,7 décorrélée des autres vaut plus qu'une
stratégie de 1,5 qui répète une position existante, et cette étude mesure de
combien.

## L'article

Trois textes fondent l'étude. Grinold (1989) pour la loi fondamentale,
\(IR \approx IC\sqrt{BR}\), où \(BR\) est le nombre de paris effectivement
indépendants. DeMiguel, Garlappi et Uppal (2009) pour le repère que toute
optimisation doit battre, l'équipondération. Asness, Moskowitz et Pedersen
(2013) pour la forme du gain, mesurée dans l'étude 003 : deux jambes corrélées
à -0,58 portent un Sharpe de 1,10 quand la meilleure seule en porte 0,59.

## L'intuition économique

Le gain ne vient d'aucune stratégie en particulier. Il vient de ce que leurs
mauvais mois ne tombent pas aux mêmes dates. Le momentum perd dans les
renversements brutaux, le portage dans les crises de change, la gestion de
volatilité dans les rebonds, et un portefeuille qui les détient toutes traverse
chaque épisode avec une partie seulement de son capital en difficulté.

Ce qui ferait disparaître le gain : que les corrélations montent vers un dans
les crises, ce que l'étude mesure par sous-période plutôt que de le supposer.

## La définition mathématique

Le portefeuille de stratégies se construit chaque année sur le seul passé.

\[
w_t = f(\hat{\Sigma}_{t-1}), \qquad
r^{p}_{t+1} = w_t^\top r_{t+1} - c \, \|w_t - w^{d}_{t}\|_1
\]

où \(\hat{\Sigma}_{t-1}\) est la covariance de Ledoit et Wolf estimée sur les
rendements connus à \(t-1\), \(f\) l'un des six optimiseurs, \(w^{d}_{t}\) les
poids dérivés par le marché, et \(c\) le coût par unité de rotation. Le
décalage d'exécution vaut un mois.

La largeur effective, le nombre de paris réellement indépendants, est le
rapport de participation des valeurs propres de la matrice de corrélation,
calculé par `quantlab.analytics.ic.effective_breadth`.

## Les données

| Stratégie | Étude | Série | Base | Ce qu'elle mesure |
|---|---|---|---|---|
| `tsmom` | 001 | `tsmom_etf_gross` | brut | notre reconstruction sur 28 fonds |
| `xsmom` | 002 | `xsmom_kf_deciles_spread_gross` | brut | déciles CRSP, sans biais de survie |
| `value_mom` | 003 | `value_momentum_blend_gross` | brut | mélange à parts égales des facteurs VME |
| `quality` | 004 | `qmj_published_usa_gross` | brut | le facteur publié, notre construction étant trop courte |
| `bab` | 005 | `bab_kf_deciles_gross` | brut | déciles de bêta CRSP, réglage de l'article |
| `vol_managed` | 006 | `hedged_spread_real_time_gross` | brut | la seule version tenable en direct |
| `statarb` | 007 | `statarb_gross` | brut | quotidien composé en mensuel, biais de survie déclaré |
| `fx_carry` | 008 | `fx_carry_gross` | brut | dix monnaies contre le dollar |

Comment lire ce tableau, en trois constats. Les huit séries sont brutes de
frais, pour que l'allocation compare des rendements de même nature ; le coût
de rééquilibrage du portefeuille, lui, est facturé. La fenêtre commune est
l'intersection des huit, du 2007-01-31 au 2026-06-30, soit 233 mois, bornée
par la reconstruction TSMOM sur fonds négociés. Deux séries portent un biais
déclaré dans leur étude, `statarb` par son univers et `quality` parce que
c'est le facteur publié et non le nôtre.

## La méthodologie originale

DeMiguel, Garlappi et Uppal (2009) comparent quatorze règles d'allocation à
l'équipondération sur sept jeux de données, hors échantillon, avec des fenêtres
d'estimation de 60 et 120 mois. Leur résultat est que l'estimation coûte plus
qu'elle ne rapporte à ces horizons.

## Notre implémentation

1. Chargement des huit séries par `quantlab.reporting.series.load_series`,
   passage du quotidien au mensuel par composition, alignement sur la fenêtre
   commune.
2. Matrice de corrélation et largeur effective sur toute la fenêtre.
3. Chaque stratégie seule : Sharpe, erreur type de Lo, repli, asymétrie.
4. Six allocations en marche avant : les poids sont estimés sur les 36 premiers
   mois puis tous les douze mois sur le passé seul, tenus entre deux
   estimations, et le livre dérive entre-temps. Équipondération, inverse de
   volatilité, parité de risque, variance minimale plafonnée à 50 %, parité
   hiérarchique, et moyenne-variance nourrie de la moyenne passée, qui est le
   test de DeMiguel et coauteurs.
5. Apport marginal : la référence sans chacune des huit, une à une.
6. Multiples de coûts de un à vingt sur la référence.
7. Comparaison au fonds QSPIX d'AQR, multi-stratégies coté.
8. Validation sur le holdout du 2020-01-31 à la fin, jamais consulté avant :
   Sharpe, erreur type, PBO, Sharpe dégonflé à vingt essais, sous-périodes.

## Nos écarts avec l'article

La référence est déclarée avant le résultat, et c'est la parité de risque, non
l'équipondération de DeMiguel et coauteurs, parce que la question de l'étude
porte sur le budget de risque. La fenêtre d'estimation est en expansion et non
glissante. Les stratégies sont brutes et le portefeuille net. Le nombre
d'essais compte les six allocations, les huit retraits, les cinq multiples de
coûts et le repère, soit vingt.

## Les résultats

### Les huit se corrèlent peu, et deux se corrèlent négativement

Source : `results/tables/correlation_matrix.csv` et `results/metrics.json`.

| Mesure | Valeur |
|---|---:|
| Corrélation moyenne des 28 paires | **0,097** |
| Paire la plus négative, gestion de volatilité contre portage | -0,499 |
| Paire la plus positive, qualité contre bêta défensif | +0,588 |
| Largeur effective, sur huit stratégies | **5,39** |

Comment lire ce tableau, en deux constats. Huit stratégies valent 5,4 paris
indépendants, ce qui est la quantité que la loi fondamentale multiplie sous la
racine. Et la paire la plus corrélée, qualité et bêta défensif, l'est parce
que les deux achètent des titres défensifs à faible bêta.

### Seule, aucune ne dépasse 0,7

Source : `results/tables/strategies_alone.csv`. Échantillon `OOS` pour toutes
sauf l'arbitrage statistique et le portage, dont la fenêtre chevauche leur
article. Brut de frais, 2007-01 à 2026-06, 233 mois.

| Stratégie | Sharpe | Erreur type | Volatilité %/an | Pire repli |
|---|---:|---:|---:|---:|
| Arbitrage statistique | **0,693** | 0,229 | 10,3 | -22,4 % |
| Valeur et momentum | 0,544 | 0,266 | 3,0 | -11,4 % |
| Momentum temporel | 0,379 | 0,201 | 17,3 | -31,7 % |
| Qualité | 0,315 | 0,263 | 9,9 | -36,0 % |
| Momentum transversal | 0,302 | 0,278 | 30,5 | -80,8 % |
| Portage de change | 0,119 | 0,244 | 7,0 | -27,9 % |
| Bêta défensif | -0,057 | 0,224 | 11,7 | -45,4 % |
| Gestion de volatilité | -0,193 | 0,264 | 14,5 | -73,7 % |

Comment lire ce tableau, en trois constats. Aucune erreur type ne descend sous
0,20, donc aucun de ces Sharpe n'est distinguable de 0,3 avec confiance. Deux
stratégies sont négatives sur la fenêtre, et l'étude les garde, parce que
retirer les perdantes après coup serait choisir sur le résultat. Le momentum
transversal porte un repli de 80,8 %, celui de 2009, ce qui rappelle que cette
série est un écart long moins court non mis à l'échelle.

### Le mélange bat la meilleure seule pour quatre allocations sur six

Source : `results/tables/portfolios_walk_forward.csv`. Net de 5 points de base
par unité de rotation, poids réestimés chaque année sur le passé, 198 mois du
2010-01 au 2026-06, échantillon `OOS`.

| Allocation | Sharpe | Erreur type | Vol. %/an | Pire repli | Rotation/an | Avant 2020 | Holdout 2020-2026 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Équipondération | 0,489 | 0,261 | 6,4 | -13,7 % | 0,07 | 0,765 | 0,214 |
| Inverse de volatilité | 0,579 | 0,258 | 4,4 | -9,8 % | 0,07 | 0,962 | 0,190 |
| **Parité de risque, référence** | **0,652** | 0,256 | 3,6 | -7,3 % | 0,07 | 1,031 | 0,239 |
| Variance minimale | 0,725 | 0,253 | 2,9 | -7,1 % | 0,07 | 1,036 | 0,394 |
| Parité hiérarchique | **0,900** | 0,254 | 3,0 | -4,3 % | 0,07 | 1,187 | 0,583 |
| Moyenne-variance | 0,699 | 0,239 | 7,5 | -19,8 % | 0,15 | 1,175 | 0,187 |

Comment lire ce tableau, en quatre constats. Le premier est que la
diversification travaille : quatre allocations sur six dépassent les 0,693 de
la meilleure stratégie seule, avec une volatilité trois fois plus basse. Le
deuxième est que la référence déclarée à l'avance, la parité de risque, n'en
fait pas partie, à 0,652. Le troisième est que la parité hiérarchique domine
tout, Sharpe, repli et holdout, et que cette domination ne peut pas être
retenue comme résultat, parce qu'elle est observée après coup parmi six essais.
Le quatrième est que toutes les allocations perdent au moins la moitié de leur
Sharpe dans le holdout, ce qui est le résultat le plus honnête du tableau.

### Deux stratégies retirent plus qu'elles n'apportent

Source : `results/tables/marginal_contribution.csv`. Sharpe de la parité de
risque avec et sans chaque stratégie, mêmes mois, net.

| Stratégie retirée | Sharpe sans elle | Apport marginal |
|---|---:|---:|
| Arbitrage statistique | 0,433 | **+0,219** |
| Valeur et momentum | 0,570 | +0,082 |
| Momentum transversal | 0,588 | +0,064 |
| Portage de change | 0,593 | +0,059 |
| Momentum temporel | 0,617 | +0,035 |
| Qualité | 0,626 | +0,027 |
| Bêta défensif | 0,721 | **-0,069** |
| Gestion de volatilité | 0,803 | **-0,151** |

Comment lire ce tableau, en deux constats. Retirer la gestion de volatilité
fait monter le Sharpe de 0,652 à 0,803, donc elle coûte au portefeuille, ce
qui est cohérent avec son verdict `REJECTED` en étude 006. Et l'apport de
l'arbitrage statistique, le plus grand, est aussi le plus fragile, cette série
portant un biais de survie déclaré et un coût de seuil de rentabilité de 3,92
points de base mesuré en étude 007.

### Le fonds multi-stratégies coté ne suit pas la même trajectoire

Source : `results/tables/benchmark_fund.csv`. Parité de risque contre QSPIX,
152 mois communs.

| Corrélation | Bêta | R² | Lecture |
|---|---:|---:|---|
| 0,341 | 1,097 | 0,117 | distinct |

Comment lire cette ligne : le fonds d'AQR explique 12 % de notre trajectoire.
Les deux sont multi-stratégies, mais pas des mêmes stratégies ni aux mêmes
poids, et le fonds est net de 150 points de base de frais.

## La robustesse

Source : `results/tables/subperiods.csv`, quatre sous-périodes de 49 à 50
mois de la parité de risque nette.

| Sous-période | Sharpe | t de Lo |
|---|---:|---:|
| 2009-12 à 2014-01 | 0,873 | 1,87 |
| 2014-02 à 2018-03 | 1,461 | 3,30 |
| 2018-04 à 2022-05 | 0,320 | 0,61 |
| 2022-06 à 2026-06 | 0,151 | 0,30 |

Comment lire ce tableau : les quatre sont positives, ce qui passe le critère,
mais la pente descend, et les deux dernières ne sont pas distinguables de zéro.

La probabilité de surapprentissage vaut 0,229 sur les six allocations, sous le
seuil de 0,5 : le classement des allocations dans l'échantillon prédit
correctement leur classement dehors.

## Les coûts

Source : `results/tables/cost_multiples.csv`. La rotation annuelle de 0,07 rend
le portefeuille presque insensible au coût : à vingt fois le coût supposé, soit
100 points de base par unité de rotation, le Sharpe net passe de 0,652 à 0,617.
Le critère du multiple survécu passe à vingt. La conclusion ne vaut que pour
le rééquilibrage du portefeuille ; les coûts propres à chaque stratégie sont
ceux de leur étude, et l'arbitrage statistique ne les survit pas.

## Le hors échantillon

Le holdout du 2020-01-31 au 2026-06-30, 77 mois, n'a été consulté qu'à
l'étape de validation. Parité de risque nette : Sharpe 0,239, erreur type de
Lo 0,409, t de 0,585. Sharpe dégonflé à vingt essais : 0,474. Rien de cela ne
franchit un seuil.

## Les limites

Les huit séries sont brutes de frais, donc le mélange est comparé à des
jambes qui ne paient rien ; les coûts par stratégie, mesurés dans chaque étude,
ramèneraient plusieurs d'entre elles sous zéro. La fenêtre de 233 mois est
courte pour huit stratégies, et 36 mois d'estimation initiale le sont plus
encore. La série de qualité est le facteur publié et non notre construction.
L'arbitrage statistique porte un biais de survie. La corrélation avec un
portefeuille existant n'a pas de sens ici, ce portefeuille étant le premier.

## Le verdict

**`REJECTED`**, déduit par `quantlab.reporting.study.decide_verdict` depuis les
seuils écrits dans `config.yaml` avant que les résultats existent. Source :
`results/tables/verdict_reasons.csv`.

| Critère | Mesuré | Seuil | Résultat |
|---|---:|---:|---|
| Hypothèse, le mélange bat la meilleure jambe | 0,652 contre 0,693 | supérieur | **échoué** |
| Signe du Sharpe hors échantillon | 0,239 | au-dessus de 0 | réussi |
| Sharpe hors échantillon | 0,239 | 0,500 | échoué |
| t après correction pour essais multiples | 0,585 | 3,000 | échoué |
| Sharpe dégonflé, vingt essais | 0,474 | 0,950 | échoué |
| Probabilité de surapprentissage | 0,229 | 0,500 | réussi |
| Part de sous-périodes positives | 1,000 | 0,600 | réussi |
| Multiple de coûts survécu | 20 | 2 | réussi |
| Corrélation au portefeuille existant | sans objet | 0,600 | échoué |

Ce que le verdict dit, et ce qu'il ne dit pas. Il dit que la référence
déclarée à l'avance ne bat pas la meilleure jambe et que rien ne survit au
holdout. Il ne dit pas que la diversification ne marche pas : quatre
allocations sur six la font travailler, et le laboratoire ne les retient pas
parce qu'il les a vues gagner après coup. C'est la différence entre un résultat
et une coïncidence bien choisie, et c'est la phrase pour laquelle le
laboratoire existe.

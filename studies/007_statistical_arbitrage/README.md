# Arbitrage statistique

## La question de recherche

Le résidu d'une action face aux composantes principales de son univers revient-il à sa moyenne assez
vite, et assez loin, pour payer la rotation qu'il exige ?

**La réponse, en un chiffre.** Le coût qui annule le rendement brut vaut **3,92 points de base par
unité négociée**, contre les **5 points de base par transaction** que l'article lui-même retient.
Source : `results/tables/costs.csv`, statut mesuré ; les 5 points de base sont rapportés, page 771 de
l'article. La stratégie ne survit donc pas à sa propre hypothèse de coût, et elle meurt à **0,784
fois** celle-ci (`results/tables/cost_multiples.csv`).

**Ce chiffre dépend d'une lecture, et sa fourchette est publiée.** Notre couverture replie les
portefeuilles propres sur les titres, donc elle négocie la jambe de facteurs, ce que l'article ne
fait pas pour ses variantes en composantes principales. Refait dans sa lecture, le coût de seuil vaut
**4,24 points de base**, et **4,95** sans aucune couverture
(`results/tables/conventions.csv`). Les trois livres restent sous les 5 points de base de l'article,
donc la conclusion tient, mais le multiple qui l'exprime va de 0,78 à 0,99.

**Ce que l'étude retrouve, et ce qu'elle ne retrouve pas.** Le ratio de Sharpe BRUT sur la fenêtre de
l'article vaut **1,460** contre 1,44 publié, soit 1,4 % d'écart. Le même chiffre NET des cinq points
de base tombe à **0,181**. La décroissance après 2002 que l'article documente est retrouvée, et elle
est plus forte : le ratio brut passe de 1,841 sur 1997-2002 à 0,807 sur 2003-2007
(`results/tables/decay.csv`).

**Le verdict est `REJECTED`**, déduit par `quantlab.reporting.study.decide_verdict`. Après la
publication de l'article, de janvier 2010 à juin 2026, le ratio de Sharpe net vaut **-1,061** avec
une statistique t de -4,20 sur 4 147 séances (`results/tables/decay.csv`).

**Une réserve qui borne tout ce qui suit.** L'univers est choisi parmi les titres qui cotent encore
aujourd'hui. `SURVIVORSHIP_BIAS_RISK` vaut vrai dans
`src/quantlab/strategies/statistical_arbitrage.py`, et l'étude ne peut pas conclure au-delà de la
réplication, quelle que soit la valeur des critères. Chaque chiffre ci-dessous vient d'un fichier de
`results/`, et le fichier est nommé.

## L'article

Avellaneda, M. et Lee, J.-H. (2010), « Statistical Arbitrage in the US Equities Market »,
*Quantitative Finance* 10(7), 761-782, DOI 10.1080/14697680903124632.

Le fac-similé de l'article publié a été lu intégralement, et ses chiffres sont recopiés dans
`docs/literature/avellaneda_lee_2010.md`. Statut de ces chiffres : **rapportés**.

Aucune réfutation publiée de l'article n'a été trouvée. Trois travaux le prolongent ou le
contredisent par la bande, et l'étude les prend au sérieux.

| Auteurs | Source | Ce qu'ils opposent |
|---|---|---|
| Yeo et Papanicolaou (2017) | *Risk and Decision Analysis* 6, 263-290 | L'estimateur de la vitesse de rappel est biaisé, et le coût décide : leur même case rend 1,42 sans coût, 1,32 à 5 points de base, 0,01 à 10. |
| Guijarro-Ordonez, Pelger et Zanotti (2021) | arXiv:2106.04028 | Leur repère paramétrique à quinze composantes rend 0,62 sur 2002-2016, contre 2,30 pour un modèle appris. |
| Krauss (2017) | *Journal of Economic Surveys* 31(2), 513-545 | La loi normale du processus contredit les faits stylisés des rendements. |

## L'intuition économique

Le rendement existe parce que celui qui prend le contre-pied fournit de la liquidité, et que ce
service se paie.

Une action monte ou baisse par rapport à son secteur pour une raison qui n'est pas toujours une
information. Un gérant liquide une ligne, un indice se rebalance, un carnet d'ordres se vide. Celui
qui achète ce que personne ne veut, et vend ce que tout le monde veut, encaisse le retour à
l'équilibre. Khandani et Lo (2007) décrivent le même mécanisme pour les stratégies de
contre-tendance, et les auteurs se placent explicitement dans cette famille.

L'article ajoute une condition que l'appariement deux à deux laisse implicite. Le retour à la moyenne
n'a de sens que sur un résidu, c'est-à-dire sur ce qui reste du rendement après avoir retiré les
facteurs communs. Les prix eux-mêmes ne reviennent pas à une moyenne, le marché monte. Le résidu, lui,
le peut.

**Ce qui ferait disparaître le rendement.** Trois extinctions, dans l'ordre de vraisemblance. La
rotation coûte plus que le retour à la moyenne ne rapporte, et c'est celle que l'étude mesure.
L'encombrement force plusieurs gérants à déboucler en même temps, ce qu'août 2007 a montré. Enfin
retirer trop de facteurs vide le résidu de sa variance, et les auteurs mesurent qu'une coupure à
75 % de la variance expliquée « leads invariably to steady losses ».

## La définition mathématique

**Le modèle de rendement**, équation (11) de l'article. Le rendement d'un titre se décompose en une
partie portée par les facteurs et une partie propre :

\[ \frac{dS_i(t)}{S_i(t)} = \alpha_i\, dt + \sum_{j=1}^{M} \beta_{ij} F_j(t)\, dt + dX_i(t) \]

**Le processus d'Ornstein-Uhlenbeck**, équation (12), qui régit le résidu cumulé. C'est un processus
rappelé vers une valeur d'équilibre à une vitesse constante :

\[ dX_i(t) = \kappa_i\left(m_i - X_i(t)\right) dt + \sigma_i\, dW_i(t), \qquad \kappa_i > 0 \]

La vitesse de rappel \(\kappa_i\) se lit en deux temps. Le temps caractéristique
\(\tau_i = 1/\kappa_i\) est celui au bout duquel un écart se divise par le nombre d'Euler. La
demi-vie \(\ln 2 / \kappa_i\) est celui au bout duquel il se divise par deux, et elle vaut donc 69 %
du temps caractéristique.

**La loi d'équilibre**, équation (14). Quand le temps tend vers l'infini, le résidu suit une loi
normale de moyenne \(m_i\) et d'écart type

\[ \sigma_{eq,i} = \frac{\sigma_i}{\sqrt{2\kappa_i}} \]

**La stationnarité décide de tout.** L'estimation passe par une autorégression d'ordre un,
\(X_{n+1} = a + b X_n + \zeta_{n+1}\), dont la pente \(b\) doit tenir dans l'intervalle ouvert de
zéro à un. Une pente négative ou supérieure à un décrit un résidu qui ne revient pas, donc un signal
sans objet, et le titre est écarté ce jour-là. Le passage aux paramètres du processus s'écrit

\[ \kappa = -\ln(b) \times 252, \qquad m = \frac{a}{1-b}, \qquad
\sigma_{eq} = \sqrt{\frac{\mathrm{Var}(\zeta)}{1 - b^{2}}} \]

**Le s-score n'est pas celui de sa définition**, et c'est le piège central de cette réplication. La
régression force la somme des résidus à zéro sur sa fenêtre, donc le résidu cumulé vaut zéro à la
dernière date par construction. L'article le dit à son annexe A et en tire l'équation (A2), qui est
la formule effectivement négociée :

\[ s_i = \frac{\langle m \rangle - m_i}{\sigma_{eq,i}} \]

où \(\langle m \rangle\) est la moyenne des équilibres en travers des titres retenus ce jour-là.

**La règle tout ou rien**, équation (16), avec les seuils calibrés page 770. Acheter quand
\(s < -1{,}25\), vendre quand \(s > 1{,}25\), fermer un achat quand \(s > -0{,}50\), fermer une vente
quand \(s < 0{,}75\).

**Le filtre de vitesse**, page 771. Un titre n'est négociable que si \(\kappa > 252/30\), donc si son
temps caractéristique reste sous trente séances, donc si \(0 < b < 0{,}9672\).

## Les données

Cours de clôture quotidiens ajustés des dividendes et des divisions, fournisseur Yahoo, du
1995-01-03 au 2026-06-30. Sources : `results/tables/universe.csv`,
`results/tables/universe_coverage.csv` et `results/tables/liquidity_filter.csv`.

| Grandeur | Valeur |
|---|---:|
| Identifiants demandés, repère de marché compris | 225 |
| Identifiants rendus | 225 |
| Titres cotant dès le 1996-01-02 | 187 |
| Titres cotant dès le 2000-01-03 | 201 |
| Titres cotant dès le 2010-01-04 | 218 |
| Taille médiane de l'univers négociable | 217 |
| Taille minimale de l'univers négociable | 132 |

**Comment lire ce tableau, en trois constats.** Un, l'univers n'est pas figé : il compte 187 titres
au début et 218 à la fin, et un titre n'entre que lorsqu'il porte 252 rendements valides consécutifs.
Deux, la taille médiane de 217 titres est très inférieure aux 1 417 titres de la photographie du
1er janvier 2007 publiée par l'article, ce qui est le premier de nos écarts. Trois, la taille
minimale de 132 titres survient au début de l'échantillon, quand la profondeur de Yahoo est la plus
faible.

**Le biais du survivant, mesuré en direct plutôt qu'affirmé.** Dix-huit titres retirés de l'indice
depuis 1995 ont été demandés un par un à Yahoo. Source : `results/tables/delisted_probe.csv`.

| Résultat | Titres |
|---|---|
| Refusés par Yahoo, aucune donnée | LEH, BSC, ENE, WCOM, EK, NT, MON, RTN, UTX, CELG, ABC, ATVI, SYMC, DPS, GMGMQ |
| Rendus avec une histoire complète | AET, ESRX, TWX |

**Comment lire ce tableau, en trois constats.** Un, quinze demandes sur dix-huit reviennent vides,
donc l'histoire de ces sociétés a disparu du fournisseur au moment où elles ont cessé de coter.
Deux, les trois titres rendus s'arrêtent à leur date d'acquisition, entre juin 2018 et décembre 2018,
et ils sont intégrés à l'univers pour ne pas aggraver le biais. Trois, ce comptage est une
démonstration et non une correction : les quinze absents sont exactement le genre de titres dont
l'écart ne s'est jamais refermé.

**Un piège d'identifiant, mesuré le 2026-09-02.** Yahoo refuse le symbole GPS et rend le symbole GAP
avec une histoire complète depuis le 1995-01-03. Le fournisseur ne porte donc l'histoire que sous le
symbole COURANT, et savoir qu'il faut demander GAP pour l'année 1995 suppose de connaître un
changement de nom de 2024. C'est une information future logée dans l'identifiant lui-même, et elle
est inévitable sur cette source.

**Le seuil de liquidité, substitut déclaré.** L'article exige une capitalisation supérieure à un
milliard de dollars **à la date de négociation**. Aucune série de capitalisation en temps réel n'est
accessible gratuitement, donc le filtre retenu porte sur la médiane du volume en dollars sur la
fenêtre de corrélation, au seuil de 5 millions de dollars. Il retire **2,49 %** des couples titre et
date (`results/tables/liquidity_filter.csv`).

## La méthodologie originale

La chaîne compte huit étapes, refaites chaque séance.

**Un.** Matrice de corrélation des rendements quotidiens sur 252 séances, titres centrés et réduits.
**Deux.** Vecteurs propres classés par valeur propre décroissante, et portefeuilles propres dont le
poids sur le titre \(i\) vaut le coefficient du vecteur propre divisé par la volatilité du titre.
**Trois.** Nombre de facteurs, fixé à quinze ou déduit d'une part de variance à atteindre.
**Quatre.** Régression du rendement de chaque titre sur les rendements des facteurs, sur 60 séances.
**Cinq.** Somme cumulée des résidus. **Six.** Autorégression d'ordre un sur ce résidu cumulé.
**Sept.** Filtre de vitesse. **Huit.** Règle tout ou rien, puis vente des facteurs correspondants.

Deux paramètres de gestion complètent la règle. Le levier vaut « 2 plus 2 », choisi par rétrotest sur
2002-2004 pour viser une volatilité annuelle proche de 10 %. Le glissement retenu vaut 0,05 % par
transaction. L'article ne corrige rien pour les tests multiples, ni sur les cinq variantes de nombre
de facteurs, ni sur les onze années qu'il publie une par une.

## Notre implémentation

La stratégie vit dans `src/quantlab/strategies/statistical_arbitrage.py`, et `run.py` ne fait
qu'orchestrer. Le module sépare cinq objets que la chaîne mélange : les portefeuilles propres,
l'estimation du processus, le s-score, la règle tout ou rien, et la couverture.

**Le décalage se fait en un seul endroit.** Le module rend des poids de décision datés du jour du
signal, et `run_backtest` les décale d'une séance avec `execution_lag=1`. Aucun poids ne peut donc
être détenu pendant la séance qui a servi à le calculer.

**L'absence d'information future se prouve par troncature.** Une chaîne tenable doit rendre les mêmes
poids passés quand on lui retire la fin de l'échantillon. Deux tests de
`tests/unit/test_strategies_statistical_arbitrage.py` l'exigent à l'exactitude machine, et un
troisième contrôle l'inverse : perturber les rendements à partir de la date de coupure DOIT changer
les poids de cette date. La mutation le confirme, avancer la fenêtre d'estimation d'une séance fait
échouer trois tests.

**Le s-score suit l'équation (A2) et non l'équation (15).** L'écart type d'équilibre est publié à
côté du s-score, et un test vérifie que leur produit est de moyenne transversale exactement nulle,
propriété qui définit le centrage.

**La couverture est figée au jour de l'entrée.** C'est la lecture compatible avec les positions tout
ou rien de l'article. La lecture opposée, recalculer la couverture chaque séance avec les bêtas du
jour, est rejouée en robustesse et comptée comme un essai.

**L'exposition brute est fixée à 4 et jamais calibrée.** La mise à l'échelle est déléguée à
`quantlab.signals.standardize.scale_to_gross`. Le levier ne décide donc que du niveau de volatilité :
le rendement et le coût lui sont tous deux proportionnels, donc le ratio de Sharpe n'en dépend pas.

**Un plafond de facteurs protège la régression.** Le nombre de facteurs est borné par la fenêtre
d'estimation moins deux, sans quoi une coupure de variance haute demanderait plus de facteurs que la
régression n'a de points. Sur les 7 673 décisions du cas de référence, le plafond n'a mordu aucune
fois (`results/tables/pipeline_diagnostics.csv`).

Aucun paramètre ne vit dans le code. Le fichier `config.yaml` porte les 4 nombres de facteurs et
les 4 fenêtres de la grille, ainsi que les 4 coupures de variance. Il porte aussi les 4 règles de
seuils, les 6 taux de coût et les 8 seuils du verdict.

## Nos écarts avec l'article

**Notre univers porte 217 titres en médiane, contre 1 417 dans l'article.** C'est l'écart le plus
lourd et il joue dans les deux sens. Moins de titres donnent moins de résidus indépendants, donc un
signal plus bruité. Moins de titres donnent aussi une matrice de corrélation de rang plein sur 252
séances, là où celle de l'article ne l'est pas.

**Nous négocions la jambe de facteurs, et l'article ne la négocie pas.** Notre couverture replie
les portefeuilles propres sur les titres, donc chaque position porte une jambe d'actions et une jambe
de facteurs, et les deux se paient. L'article fait autrement dès que les facteurs ne sont pas des
instruments cotés. Sa section 5.1 l'écrit : les fonds synthétiques n'étant pas négociables, les
auteurs négocient les seules actions du signal et achètent ou vendent le fonds indiciel du marché
pour annuler le bêta d'ensemble. Sa section 5.3 renvoie à cette phrase pour la variante à quinze
composantes principales, et son équation de compte de résultat, page 771, ne porte aucune position
autre qu'une action. L'écart est mesuré plus bas, et il déplace le coût de seuil de 3,92 à 4,24
points de base.

**Notre univers porte le biais du survivant, et l'article dit l'éviter.** Sa condition de
capitalisation s'applique à la date de négociation, sur l'ensemble des actions américaines. La nôtre
part d'une liste de grandes capitalisations qui cotent encore, à laquelle trois titres retirés ont
été rendus. `SURVIVORSHIP_BIAS_RISK` vaut vrai, et l'étude ne peut pas dépasser la réplication de ce
seul fait.

**Notre seuil de sélection est la liquidité et non la capitalisation.** Le substitut est déclaré, et
sa sévérité est mesurée à 2,49 % des couples titre et date.

**Notre exécution est décalée d'une séance.** L'article exécute au cours de clôture du jour du
signal. Notre décalage rend l'exercice plus difficile, jamais plus facile, et il n'est pas
négociable dans ce laboratoire.

**Nous ne fixons pas le levier par rétrotest.** L'article choisit « 2 plus 2 » sur 2002-2004, fenêtre
incluse dans les périodes dont il publie la performance. Nous fixons l'exposition brute à 4 par
convention, et le ratio de Sharpe n'en dépend pas.

**Nous ne reproduisons ni les fonds sectoriels réels, ni les fonds synthétiques, ni les signaux en
temps de transaction.** L'affectation sectorielle par titre à la date passée n'est pas publiée, et la
normalisation du facteur de volume n'est décrite qu'en une phrase. Statut : **non trouvé**, et le
détail est dans `notes.md`.

**Nous corrigeons pour les tests multiples**, ce que l'article ne fait pas, et le compte de 49 essais
entre dans le ratio de Sharpe dégonflé.

## Les résultats

### Le ratio de Sharpe brut se réplique, le ratio net ne se réplique pas

Source : `results/tables/decay.csv`. Univers de 217 titres en médiane, exposition brute 4, règle de
l'article, couverture figée à l'entrée. Le net est net de 5 points de base par unité négociée.

| Fenêtre | Échantillon | Séances | Sharpe brut | Sharpe net | Rendement net %/an | Volatilité %/an | Pire repli |
|---|---|---:|---:|---:|---:|---:|---:|
| 1997-01 à 2007-12, celle de l'article | IS | 2 767 | **1,460** | **0,181** | 2,47 | 13,63 | -42,9 % |
| 1997-01 à 2002-12 | IS | 1 509 | 1,841 | 0,778 | 12,98 | 16,69 | -20,8 % |
| 2003-01 à 2007-12 | IS | 1 258 | 0,807 | **-1,181** | -10,13 | 8,58 | -42,9 % |
| 2002-01 à 2007-12, celle de la table 8 | IS | 1 510 | 1,189 | -0,558 | -5,45 | 9,77 | -42,9 % |
| 2008-01 à 2009-12 | VALIDATION | 505 | 1,123 | 0,161 | 2,95 | 18,32 | -24,1 % |
| 2010-01 à 2026-06, après publication | OOS | 4 147 | 0,650 | **-1,061** | -10,50 | 9,90 | -85,5 % |

**Comment lire ce tableau, en trois constats.** Un, le ratio brut de 1,460 sur la fenêtre de
l'article coïncide avec le 1,44 publié à 1,4 % près, ce qui atteste la chaîne de calcul et rend
interprétable tout écart sur le net. Deux, l'écart entre 1,460 et 0,181 est entièrement le coût. Sur
l'échantillon complet, 344,0 unités négociées par an à 5 points de base coûtent 17,20 points de
rendement, contre 13,50 points de rendement brut. Trois, le ratio brut décroît de 1,841 à 0,807
puis à 0,650, donc le signal
s'affaiblit sans disparaître, et c'est le coût qui décide du signe.

### La décroissance après 2002 est retrouvée, année par année

Source : `results/tables/annual_sharpe.csv`. La colonne publiée vient de la table 6, page 774,
statut **rapporté**.

| Année | Sharpe brut | Sharpe net | Publié | Année | Sharpe brut | Sharpe net | Publié |
|---|---:|---:|---:|---|---:|---:|---:|
| 1997 | 0,91 | -0,45 | 1,4 | 2003 | 0,81 | **-1,06** | 0,9 |
| 1998 | 1,57 | 0,45 | 1,4 | 2004 | 1,25 | -0,72 | 2,2 |
| 1999 | 2,81 | 1,74 | 0,2 | 2005 | 1,03 | -1,08 | 1,2 |
| 2000 | 1,48 | 0,69 | 2,2 | 2006 | 0,88 | -1,08 | 1,0 |
| 2001 | 1,90 | 0,81 | 2,6 | 2007 | **0,04** | -2,00 | **-0,7** |
| 2002 | 2,46 | 1,26 | 3,4 | | | | |

**Comment lire ce tableau, en trois constats.** Un, les onze années portent un ratio brut positif,
contre dix des onze années publiées, et la seule année négative de l'article, 2007, est aussi notre
plus mauvaise à 0,04. Deux, le ratio net change de signe en 2003 et ne redevient jamais positif
avant 2008, ce qui est exactement la coupure que l'article situe entre ses deux périodes de
résultats. Trois, nos années fortes ne sont pas les leurs : 1999 rend 2,81 chez nous contre 0,2 chez
eux, et 2002 rend 2,47 contre 3,4.

**Pourquoi une année ne se compare pas.** Sous Lo (2002), l'erreur type d'un ratio de Sharpe annualisé
estimé sur \(T\) années vaut environ \(\sqrt{(1 + SR^2/2)/T}\). Pour une seule année et un ratio vrai
de 1,4, elle vaut environ 1,4, statut **modélisé**. Les colonnes annuelles se lisent donc comme des
indications de sens, et la seule comparaison qui porte est celle des lignes d'ensemble.

### Le processus estimé se retrouve, et le filtre de vitesse ne sert à rien

Source : `results/tables/ou_diagnostics.csv`, médianes en travers des titres et des séances.

| Fenêtre | Temps de retour, séances | Demi-vie, séances | Volatilité d'équilibre, pb | Part stationnaire | Part éligible |
|---|---:|---:|---:|---:|---:|
| Tout, 1996-2026 | 7,64 | 5,29 | 175,2 | 1,000 | 0,990 |
| 1997-2007, celle de l'article | **7,56** | 5,24 | **209,9** | 1,000 | 0,991 |
| 2010-2026, après publication | 7,69 | 5,33 | 152,6 | 1,000 | 0,990 |
| Valeurs publiées, page 771 | **7** | non publiée | **300** | non publiée | non publiée |

**Comment lire ce tableau, en trois constats.** Un, le temps de retour à la moyenne médian vaut 7,56
séances contre les 7 jours annoncés, soit un écart de 0,56 séance, et c'est le contrôle le plus
serré de l'étude. Deux, la volatilité d'équilibre du résidu vaut 210 points de base contre les 300
annoncés, écart cohérent avec un univers de grandes capitalisations plus calme que l'ensemble du
marché. Trois, 99 % des titres passent le filtre de vitesse. Ce filtre écarte les temps de retour
supérieurs à 30 séances, et le nôtre en vaut 7,6, donc le garde-fou de l'article ne mord pas sur
notre univers.

### Les huit contrôles de réplication

Source : `results/tables/replication_checks.csv`. La tolérance relative de 0,50 est écrite dans
`config.yaml` avant que les résultats existent.

| Grandeur | Publié | Nous | Écart relatif | Tolérance | Résultat |
|---|---:|---:|---:|---:|---|
| Temps de retour médian, séances | 7,00 | 7,56 | 0,080 | 3 absolue | **répliqué** |
| Volatilité d'équilibre, points de base | 300,0 | 209,9 | 0,300 | 150 absolue | **répliqué** |
| Nombre de facteurs à 55 % de variance | 20,0 | 11,0 | 0,450 | 10 absolue | **répliqué** |
| Sharpe net, 15 composantes, 1997-2007 | 1,44 | 0,18 | 0,874 | 0,50 | écart |
| Sharpe net, 15 composantes, 2003-2007 | 0,90 | -1,18 | 2,312 | 0,50 | écart |
| Sharpe net, 1 portefeuille propre, 2002-2007 | 0,70 | -0,12 | 1,172 | 0,50 | écart |
| Sharpe net, 55 % de variance, 2002-2007 | 0,70 | -0,67 | 1,952 | 0,50 | écart |
| Sharpe net, 65 % de variance, 2002-2007 | 0,40 | -1,02 | 3,540 | 0,50 | écart |

**Comment lire ce tableau, en trois constats.** Un, les trois contrôles qui portent sur la STRUCTURE
du modèle passent tous, mais deux d'entre eux passent de justesse. La volatilité d'équilibre est à
30 % de la valeur publiée et le nombre de facteurs à 45 %, chiffres lisibles dans la colonne d'écart
relatif. Seul le temps de retour à la moyenne, à 8 %, est une réplication serrée. Deux, les cinq
contrôles qui portent sur la PERFORMANCE nette échouent tous, et l'écart croît avec le nombre de
facteurs, de 0,87 à 3,54. Trois, la réplication n'est donc pas acquise au sens du laboratoire, et
c'est la deuxième barrière qui ferme le verdict.

**Pourquoi la tolérance vaut 0,50 et non les 0,10 du laboratoire.** Sous Lo (2002), l'erreur type
d'un ratio de Sharpe vrai de 1,44 estimé sur onze ans vaut \(\sqrt{(1 + 1{,}44^2/2)/11}\), soit 0,43,
donc 30 % de la valeur publiée, statut **modélisé**. Une tolérance plus serrée que l'incertitude de
la cible ferait échouer le contrôle par la seule variance d'échantillonnage de l'article. Le
raisonnement et le chiffre sont écrits dans `config.yaml`.

### La figure de richesse cumulée

`results/figures/equity_curve.png`. **Mode d'emploi.** L'axe vertical porte une échelle logarithmique
en dollars des États-Unis, base 1 dollar au 3 janvier 1996, première séance négociée. Trois courbes :
la stratégie brute, la même nette de cinq points de base, et le fonds indiciel du S&P 500. Regarder
d'abord l'écart vertical entre la courbe brute et la courbe nette, qui est le coût, puis le moment où
la courbe nette décroche du fonds indiciel, vers 2003.

### La couverture par les portefeuilles propres laisse une exposition résiduelle

La stratégie est censée être neutre au marché, puisque chaque position vend les facteurs qui la
portent. Mesuré, elle ne l'est pas tout à fait : son bêta au fonds indiciel vaut **0,112** et sa
corrélation quotidienne **0,177** (`results/tables/metrics.csv`, échantillon complet, net de frais).

**Ce que cela veut dire, en trois constats.** Un, une corrélation de 0,177 reste faible et elle passe
le critère de verdict, fixé à 0,60 au plus. Deux, elle n'est pas nulle parce que la couverture est
figée au jour de l'entrée : les bêtas vieillissent pendant que la position reste ouverte. Trois, la
variante à couverture recalculée chaque séance porterait une exposition résiduelle plus faible, et
son effet sur le coût est mesuré plus bas.

`results/figures/correlation_heatmap.png`. **Mode d'emploi.** Trois lignes et trois colonnes, une par
série : le marché, la stratégie brute et la stratégie nette. Lire la première ligne, celle qui donne
la corrélation de chaque série au marché, et ignorer la diagonale qui vaut un par construction.

**Où trouver chaque chiffre avec son étiquette.** Le fichier `results/tables/metrics.csv` porte les
vingt métriques publiées, chacune avec son échantillon et sa base de coût, comme la règle 5 du
laboratoire l'exige. Une précision s'impose sur l'étiquette. Six d'entre elles sont mesurées sur la
TOTALITÉ du backtest, de janvier 1996 à juin 2026 : la volatilité, le pire repli, le bêta, la
corrélation, la rotation et le coût de seuil. Cette période contient le hors échantillon. Elles
portent quand même l'étiquette `IS`, la plus sévère des trois disponibles, faute d'une étiquette pour
l'échantillon entier.

## La robustesse

### Le ratio brut tient partout, le coût de seuil ne tient nulle part

Source : `results/tables/parameter_grid.csv`. Seize cellules, règle de l'article, échantillon complet
de 1996-01 à 2026-06, exposition brute 4.

Ratio de Sharpe NET, net de 5 points de base :

| Facteurs | 30 séances | 60 séances | 90 séances | 120 séances |
|---|---:|---:|---:|---:|
| 5 | -0,21 | 0,18 | **0,33** | 0,25 |
| 10 | -0,80 | 0,13 | 0,25 | 0,31 |
| 15 | -1,16 | **-0,30** | -0,07 | 0,10 |
| 20 | **-1,90** | -0,60 | -0,40 | -0,22 |

Coût de seuil de rentabilité, en points de base par unité négociée :

| Facteurs | 30 séances | 60 séances | 90 séances | 120 séances |
|---|---:|---:|---:|---:|
| 5 | 4,28 | 6,00 | **7,10** | 6,70 |
| 10 | 2,86 | 5,56 | 6,23 | 6,61 |
| 15 | 2,33 | **3,92** | 4,69 | 5,47 |
| 20 | **1,37** | 3,09 | 3,55 | 4,13 |

**Comment lire ces deux tableaux, en trois constats.** Un, le coût de seuil décroît avec le nombre de
facteurs dans les quatre colonnes sans une seule exception, et il croît avec la fenêtre d'estimation
dans onze des douze passages d'une colonne à la suivante. Deux, la meilleure cellule atteint 7,10 points de base, ce qui laisse
2,10 points de marge sur les 5 points de base de l'article, et c'est la seule marge que l'étude ait
trouvée. Trois, le cas de référence de l'article, quinze facteurs et soixante séances, est le onzième
sur seize en ratio net.

**L'avertissement de l'article se retrouve, par un autre chemin.** Les auteurs écrivent que trop de
facteurs mènent au bruit, et ils l'attribuent à un résidu vidé de sa variance. Notre mesure montre le
mécanisme complémentaire : de 5 à 20 facteurs, à fenêtre de 60 séances, la rotation annuelle passe de
292,7 à 369,1, donc le coût monte plus vite que le rendement.

`results/figures/parameter_heatmap.png`. **Mode d'emploi.** Une ligne par nombre de facteurs, une
colonne par fenêtre d'estimation, une couleur par ratio de Sharpe net. Chercher un plateau de couleur
homogène plutôt qu'une case isolée : une bonne cellule entourée de mauvaises est du bruit.

### Les coupures de variance rejouent la table 8, et la contredisent

Source : `results/tables/variants.csv`, échantillon complet, net de 5 points de base.

| Variante | Facteurs médians | Sharpe brut | Sharpe net | Rotation annuelle | Coût de seuil, pb |
|---|---:|---:|---:|---:|---:|
| Un seul portefeuille propre | 1 | 0,721 | **0,189** | 264,1 | **6,87** |
| 45 % de la variance | 4 | 0,920 | 0,146 | 296,7 | 5,96 |
| 55 % de la variance | 11 | 1,024 | 0,006 | 328,9 | 5,03 |
| 65 % de la variance | 21 | 1,075 | -0,412 | 373,9 | 3,61 |
| 75 % de la variance | 37 | 1,061 | -1,110 | 467,0 | 2,43 |
| Trente composantes | 30 | 1,141 | -0,909 | 414,7 | 2,78 |

**Comment lire ce tableau, en trois constats.** Un, le ratio BRUT croît avec le nombre de facteurs
jusqu'à 65 % de variance, donc retirer plus de risque systématique améliore bien le signal, ce que
l'article dit. Deux, la rotation croît plus vite, de 264,1 à 467,0, si bien que le ratio NET décroît
sans exception et change de signe entre 55 % et 65 % de variance. Trois, la coupure à 75 % perd de
l'argent de façon régulière, ce que l'article annonce. Notre mesure en donne la cause : son coût de
seuil tombe à 2,44 points de base, soit moitié moins que le coût qu'elle supposerait.

**La conclusion de l'article sur le nombre de facteurs n'est pas retrouvée.** Il classe quinze
facteurs devant les coupures variables. Notre classement net est l'inverse exact : un seul
portefeuille propre rend 0,189, la coupure à 45 % rend 0,146, et quinze facteurs rendent -0,304.

### Le livre que l'article négocie coûte plus cher à annuler que le nôtre

Source : `results/tables/conventions.csv`, échantillon complet, net de 5 points de base. Les trois
livres ne portent pas la même exposition brute, et cela ne change rien aux colonnes comparées. Le
rendement, le coût et la rotation sont tous proportionnels à l'exposition brute. Le ratio de Sharpe
et le coût de seuil n'en dépendent donc pas.

| Livre | Exposition brute médiane | Rotation annuelle | Coût de seuil, pb | Sharpe brut, tout | Sharpe net, fenêtre de l'article | t net après publication |
|---|---:|---:|---:|---:|---:|---:|
| Le nôtre, jambe de facteurs négociée | 4,00 | 344,0 | **3,92** | 1,107 | 0,181 | -4,20 |
| Celui de l'article, actions plus fonds indiciel | 80,50 | 7 343,7 | **4,24** | 1,142 | 0,471 | -3,79 |
| Actions seules, sans aucune couverture | 73,00 | 8 339,0 | **4,95** | 1,251 | 0,725 | -1,28 |

**Comment lire ce tableau, en trois constats.** Un, cesser de négocier la jambe de facteurs porte le
coût de seuil de 3,92 à 4,24 points de base, et retirer toute couverture le porte à
4,95 : notre convention est donc celle des trois qui condamne le plus la stratégie. Deux, les
trois livres restent sous les 5 points de base de l'article, le plus favorable donnant 4,95 divisé
par 5, soit 0,99. La conclusion tient donc dans les trois lectures, et c'est le multiple qui bouge,
de 0,78 à 0,99. Trois, la statistique t d'après publication passe de -4,20 à -3,79 dans la lecture de
l'article, donc la perte y reste établie. Elle tombe à -1,28 sans couverture, où elle cesse d'être
distinguable du hasard.

**Ce que cette mesure ne dit pas.** Le livre de l'article n'est pas seulement moins coûteux, il est
aussi différent : son ratio de Sharpe brut d'ensemble vaut 1,142 contre 1,107 chez nous, et
il garde une exposition sectorielle que notre couverture retire. La coïncidence à 1,4 % entre notre
ratio brut et le 1,44 publié tient donc à notre convention, et elle n'atteste la chaîne que sous
cette convention.

### Les autres réglages ne sauvent rien

Sources : `results/tables/variants.csv` et `results/tables/trading_rules.csv`.

| Variante | Sharpe brut | Sharpe net | Rotation annuelle | Coût de seuil, pb |
|---|---:|---:|---:|---:|
| Cas de référence | 1,107 | -0,304 | 344,0 | 3,92 |
| Fenêtre de corrélation de 126 séances | 1,118 | -0,287 | 351,2 | 3,98 |
| Fenêtre de corrélation de 504 séances | 1,126 | -0,263 | 331,4 | 4,05 |
| Décider tous les 5 jours | 0,797 | 0,140 | 176,5 | 5,47 |
| Décider tous les 21 jours | 0,448 | **0,190** | **85,9** | **6,58** |
| Filtre de vitesse à 15 séances | 1,031 | -0,726 | 428,9 | 2,93 |
| Filtre de vitesse retiré | 1,108 | -0,246 | 330,2 | 4,09 |
| s-score sans centrage transversal | 1,152 | -0,249 | 343,9 | 4,11 |
| s-score modifié par la dérive | 0,447 | -0,884 | 302,4 | 1,69 |
| Couverture recalculée chaque séance | 1,203 | -0,355 | 370,2 | 3,86 |
| Seuils de sortie symétriques à 0,75 | 1,251 | -0,285 | 384,5 | 4,07 |
| Seuils d'entrée à 2,00 | 0,671 | -0,487 | 341,5 | 2,88 |
| Seuils d'entrée à 0,75 | 1,120 | -0,352 | 321,3 | 3,80 |

**Comment lire ce tableau, en trois constats.** Un, le seul réglage qui déplace vraiment le coût de
seuil est la fréquence de décision. Passer du quotidien au mensuel divise la rotation par quatre et
porte le coût de seuil de 3,92 à 6,58 points de base, au prix de 58 % du rendement brut. Deux, la
couverture recalculée chaque séance n'ajoute que 7,6 % de rotation, donc la convention que nous
avions crue décisive ne l'est pas, et `notes.md` le raconte. Trois, le s-score modifié par la dérive,
que l'article définit sans le rétrotester, divise le ratio brut par deux et demi.

### Les sous-périodes ne sont positives qu'une fois sur quatre

Source : `results/tables/subperiods.csv`, net de 5 points de base.

| Sous-période | Séances | Sharpe | Erreur type de Lo | t | Pire repli |
|---|---:|---:|---:|---:|---:|
| 1996-01 à 2002-12 | 1 761 | **0,905** | 0,382 | 2,37 | -20,8 % |
| 2002-12 à 2007-12 | 1 258 | -1,149 | 0,437 | -2,63 | -42,9 % |
| 2007-12 à 2015-12 | 2 015 | -0,270 | 0,380 | -0,71 | -45,7 % |
| 2015-12 à 2026-06 | 2 638 | **-1,244** | 0,309 | -4,03 | -78,1 % |

**Comment lire ce tableau, en trois constats.** Un, une sous-période sur quatre est positive, ce qui
donne la part de 0,25 comparée au seuil de 0,60 dans le verdict. Deux, les deux tranches extrêmes
portent une statistique t supérieure à 2 en valeur absolue et de signes opposés, donc le renversement
n'est pas du bruit. Trois, le pire repli s'aggrave de tranche en tranche, de 21 % à 78 %.

`results/figures/subperiod_bars.png`. **Mode d'emploi.** Une barre par sous-période, la moustache
étant l'intervalle à 95 % construit sur l'erreur type de Lo. Vérifier que chaque moustache traverse
zéro avant de commenter la hauteur d'une barre : ici seule la troisième tranche le fait.

## Les coûts

C'est la section qui décide, et son chiffre ouvre ce document.

Source : `results/tables/costs.csv`. Rotation mesurée en convention de somme entière, celle qui
compte les deux côtés du rééquilibrage, donc directement comparable à un demi-écart acheteur-vendeur
payé par côté.

| Grandeur | Valeur | Statut |
|---|---:|---|
| Rotation annuelle, somme entière | **344,0** | mesuré |
| Rendement brut annuel | 13,50 % | mesuré |
| Coût qui annule le rendement brut | **3,92 pb** | mesuré |
| Glissement retenu par l'article, page 771 | **5 pb** | rapporté |
| Multiple du coût de l'article auquel la stratégie meurt | **0,784** | mesuré |

**Comment lire ce tableau, en trois constats.** Un, le coût de seuil de 3,92 points de base est
inférieur au coût que l'article suppose, donc la stratégie perd de l'argent sous les hypothèses de
l'article lui-même. Deux, la rotation découle du renouvellement des positions. Les 344,0 unités négociées sur une
exposition brute de 4 valent 43 allers-retours du livre entier par an, donc une position tient 5,9
séances en moyenne. C'est un peu moins que les 7,6 séances du temps de retour à la moyenne. Trois,
aucune des 37 configurations dont le coût de seuil est publié ne dépasse 7,10 points de base.

**Ce que nous ne comparons pas.** Aucun écart acheteur-vendeur n'a été mesuré ici, faute de données
de carnet. Un chiffre repris d'ailleurs serait **non trouvé** dans cette étude, donc la seule
comparaison publiée est celle du coût de seuil aux cinq points de base que l'article retient.

Effet du taux de coût sur le ratio de Sharpe net, cas de référence (`results/tables/costs.csv`) :

| Taux, pb | Sharpe net, tout | Sharpe net, 1997-2007 | Sharpe net, après publication | Rendement net %/an |
|---:|---:|---:|---:|---:|
| 0 | 1,107 | **1,460** | 0,650 | 13,50 |
| 1 | 0,825 | 1,204 | 0,308 | 10,06 |
| 2 | 0,543 | 0,948 | -0,034 | 6,62 |
| 5 | -0,304 | 0,181 | -1,061 | -3,71 |
| 10 | -1,716 | -1,097 | -2,770 | -20,92 |
| 20 | -4,531 | -3,647 | -6,164 | -55,34 |

**Comment lire ce tableau, en trois constats.** Un, le ratio net décroît linéairement avec le taux,
parce que la rotation ne dépend pas du coût supposé. Deux, la période postérieure à la publication
tourne au négatif dès 2 points de base, donc le signal y est déjà trop faible pour payer un coût même
très optimiste. Trois, à coût nul le ratio d'ensemble vaut 1,107 sur trente ans, ce qui montre que le
signal existe et que le débat porte entièrement sur son prix.

`results/figures/cost_sensitivity.png`. **Mode d'emploi.** L'axe horizontal porte le multiple appliqué
aux cinq points de base, l'axe vertical le ratio de Sharpe net, et la ligne verticale marque le
croisement de zéro. Lire l'abscisse de ce croisement : 0,784, donc la stratégie meurt avant
d'atteindre le coût que l'article suppose.

## Le hors échantillon

### Après la publication, la stratégie perd, et elle perd de façon significative

L'article paraît en 2010. Sur les 4 147 séances qui suivent, de janvier 2010 à juin 2026, la
stratégie rend un ratio de Sharpe net de **-1,061**. Sa statistique t vaut **-4,20**, échantillon
`OOS`, net de 5 points de base (`results/tables/decay.csv`). Le ratio brut de la même période vaut
0,650, donc le signal survit et le coût l'emporte.

Le rééchantillonnage par blocs de 21 séances, 2 000 tirages, graine 20260902, place le rendement
annualisé à **-10,50 %**. Son intervalle va de -14,46 % à -6,72 %, et **aucun tirage sur 2 000
n'est positif** (`results/tables/bootstrap.csv`).

### Les seize cellules de la grille perdent toutes, et neuf le font significativement

Source : `results/tables/multiple_testing.csv`, correction de Holm sur les seize statistiques t de la
période postérieure à la publication.

| Configuration | t | Valeur p ajustée | Rejeté à 5 % |
|---|---:|---:|---|
| 20 facteurs, 30 séances | **-10,56** | 0,0000 | oui |
| 15 facteurs, 30 séances | -7,21 | 0,0000 | oui |
| 20 facteurs, 60 séances | -5,79 | 0,0000 | oui |
| 10 facteurs, 30 séances | -5,75 | 0,0000 | oui |
| 20 facteurs, 90 séances | -4,43 | 0,0001 | oui |
| 15 facteurs, 60 séances | -4,20 | 0,0003 | oui |
| 5 facteurs, 30 séances | -3,77 | 0,0016 | oui |
| 20 facteurs, 120 séances | -3,23 | 0,0110 | oui |
| 15 facteurs, 90 séances | -2,91 | 0,0290 | oui |
| 15 facteurs, 120 séances | -2,49 | 0,0896 | non |
| 10 facteurs, 120 séances | -2,32 | 0,1220 | non |
| 10 facteurs, 60 séances | -2,05 | 0,2017 | non |
| 10 facteurs, 90 séances | -1,55 | 0,4836 | non |
| 5 facteurs, 120 séances | -1,44 | 0,4836 | non |
| 5 facteurs, 90 séances | -1,29 | 0,4836 | non |
| 5 facteurs, 60 séances | -1,08 | 0,4836 | non |

**Comment lire ce tableau, en trois constats.** Un, les seize statistiques t sont négatives, donc
aucun réglage de la grille ne rend une performance positive après la publication. Deux, neuf d'entre
elles survivent à la correction de Holm, donc la perte est établie et non conjecturée. Trois, les
cellules qui résistent le mieux sont celles à peu de facteurs et à longue fenêtre, exactement celles
dont le coût de seuil est le plus élevé.

### Les contrôles de surapprentissage disent quelque chose d'inattendu

| Contrôle | Valeur mesurée | Fichier |
|---|---:|---|
| Nombre d'essais comptés | 49 | `trials.csv` |
| Variance des ratios de Sharpe essayés | 4,522 | `deflated_sharpe.csv` |
| Probabilité de surapprentissage | **0,014** | `metrics.json` |
| Sharpe moyen des 7 chemins de validation croisée | **0,150** | `cpcv_distribution.csv` |
| Part de chemins négatifs | 0,000 | `cpcv_distribution.csv` |
| Ratio de Sharpe dégonflé | 0,000 | `deflated_sharpe.csv` |
| t exigé par Bonferroni sur 49 essais | 3,28 | `deflated_sharpe.csv` |
| t observé après publication | **-4,20** | `deflated_sharpe.csv` |

**Comment lire ce tableau, en trois constats.** Un, la probabilité de surapprentissage vaut 0,014 et
les sept chemins de validation croisée sont tous positifs, donc choisir la meilleure cellule sur le
passé aurait bien donné une cellule correcte ensuite. Deux, cela ne sauve rien : le niveau atteint
reste un ratio de Sharpe moyen de 0,150, très loin des 1,44 publiés. Trois, le surapprentissage n'est
donc pas le défaut de cette stratégie, et c'est utile à écrire, parce que la critique la plus
fréquente contre une grille de 49 essais ne s'applique pas ici.

**Un mot sur la validation croisée.** Elle juge le PROCESSUS de sélection et non une série figée. Sur
chaque bloc d'apprentissage, la meilleure des seize cellules est retenue, puis son rendement du bloc
de test est collecté. Une série figée rendrait sept chemins identiques, ce qui ne mesurerait rien.

`results/figures/rolling_sharpe.png`, `results/figures/underwater.png`,
`results/figures/return_histogram.png` et `results/figures/qq_plot.png`. **Mode d'emploi.** La
première trace le ratio de Sharpe net sur fenêtre glissante de 252 séances : chercher si la courbe
passe durablement au-dessus de zéro, ce qu'elle fait avant 2003 et plus après. La deuxième montre la
distance au sommet précédent, en points de pourcentage. Les deux dernières comparent la distribution
observée à la loi normale, et l'écart aux extrémités mesure ce que le ratio de Sharpe ignore.

## Les limites

**Le biais du survivant est sévère et il n'est pas corrigé.** L'univers part de grandes
capitalisations qui cotent encore, et quinze titres retirés sur dix-huit demandés sont introuvables
chez le fournisseur. Ces quinze sont précisément les sociétés dont l'écart ne s'est jamais refermé,
donc les positions les plus coûteuses manquent. L'étude ne peut pas dépasser la réplication de ce
seul fait, et `SURVIVORSHIP_BIAS_RISK` le déclare dans le code.

**Notre univers est six fois plus petit que celui de l'article.** Deux cent dix-sept titres en
médiane contre 1 417. Aucune correction n'existe, et l'effet joue dans les deux sens, ce qui est
écrit plus haut.

**Le seuil de capitalisation de l'article n'est pas reproduit.** Le substitut est un seuil de
liquidité, il retire 2,49 % des couples titre et date, et il ne mesure pas la même chose.

**Le désaccord sur le ratio de Sharpe net n'est refermé qu'au quart.** Notre ratio brut coïncide
avec le chiffre publié et notre ratio net ne coïncide pas. La lecture de la couverture explique une
part mesurée de l'écart : le livre de l'article rend 0,471 sur sa fenêtre contre 0,181 chez nous,
pour 1,44 publié, soit 23 % de la distance parcourue. Les trois autres lectures essayées ne referment
rien, et le détail est dans `notes.md`. Statut du reste : **déclaré non résolu**.

**La coupure à 75 % de variance retient 37 facteurs pour 60 observations.** Le coût de rotation n'est
donc pas la seule cause possible de sa perte : une régression à 22 degrés de liberté sous-estime la
variance résiduelle, donc gonfle les s-scores. L'étude ne sépare pas les deux causes.

**Aucun coût de financement ni d'emprunt de titres n'est retranché.** L'exposition brute vaut 4 et la
moitié est vendeuse. Un investisseur réel paierait l'emprunt des titres vendus, et l'omission ne peut
que renforcer la conclusion.

**L'exécution est supposée intégrale au cours de clôture.** La stratégie étant tout ou rien, elle
concentre ses ordres au moment le plus encombré de la séance, ce que le moteur vectoriel ignore.

**L'estimateur de la vitesse de rappel est biaisé sur soixante points.** Yeo et Papanicolaou (2017)
le notent pour les moindres carrés comme pour le maximum de vraisemblance. Le biais joue sur le
filtre de vitesse et sur le dénominateur du s-score, et il n'est pas corrigé ici.

**Trois variantes de l'article ne sont pas reproduites.** Les fonds sectoriels réels, les fonds
synthétiques et les signaux en temps de transaction. Les deux premiers demandent une affectation
sectorielle non publiée, le troisième une normalisation décrite en une phrase. Statut : **non
trouvé**.

**Le compte de 49 essais couvre les évaluations de performance et rien d'autre.** Les mesures
descriptives, comme le temps de retour à la moyenne, ne peuvent pas être sélectionnées comme
résultat et ne sont pas comptées.

**Aucun résultat ne porte sur l'avenir.** Tous les chiffres sont mesurés sur des périodes nommées.

## Le verdict

**`REJECTED`**, déduit par `quantlab.reporting.study.decide_verdict` depuis les seuils écrits dans
`config.yaml` avant que les résultats existent. Voici les dix critères, avec la valeur mesurée en
face du seuil.

| Critère | Mesuré | Seuil | Résultat |
|---|---:|---:|---|
| Signe économique attendu | rendement brut positif | positif | RÉUSSI |
| Signe du Sharpe hors échantillon | **-1,061** | rejet à 0 ou moins | **ÉCHOUÉ** |
| Réplication, 8 contrôles chiffrés | 3 sur 8 dans la tolérance | tous exigés | ÉCHOUÉ |
| Sharpe hors échantillon | -1,061 | minimum 0,50 | ÉCHOUÉ |
| t après correction pour essais multiples | -4,204 | minimum 3,00 | ÉCHOUÉ |
| Ratio de Sharpe dégonflé | 0,000 | minimum 0,95 | ÉCHOUÉ |
| Probabilité de surapprentissage | 0,014 | maximum 0,50 | RÉUSSI |
| Part de sous-périodes positives | 0,250 | minimum 0,60 | ÉCHOUÉ |
| Multiple de coûts survécu | 0,784 | minimum 2,00 | ÉCHOUÉ |
| Corrélation absolue avec le portefeuille détenu | 0,177 | maximum 0,60 | RÉUSSI |

**Comment lire ce tableau, en trois constats.** Un, le verdict est `REJECTED` parce que le signe du
ratio de Sharpe hors échantillon est un critère de rejet qui précède tous les autres. Deux, la
réplication échoue aussi, et elle échouerait même si le hors échantillon était bon, donc deux
barrières distinctes se referment. Trois, deux critères réussissent, la probabilité de
surapprentissage et la corrélation au marché, ce qui écarte les deux explications les plus commodes
de l'échec.

**Le plafond déclaré d'avance.** Même si tous les critères avaient réussi, le biais du survivant
interdisait à cette étude de dépasser `REPLICATED`. Le verdict mécanique est plus bas que ce plafond,
donc le plafond n'a pas eu à s'appliquer, et il est enregistré dans la note de l'expérience et dans
la fiche d'alpha `configs/strategies/statistical_arbitrage_pca.yaml`.

**Ce que l'étude établit, en trois phrases.** Le ratio de Sharpe brut de l'article se retrouve à
1,4 % près sur sa propre fenêtre, et son processus de retour à la moyenne se retrouve à 0,56 séance
près. Le coût qui annule ce rendement brut vaut 3,92 points de base dans notre convention de couverture,
et 4,24 dans celle de l'article, donc moins que ses 5 points de base dans les deux lectures. La stratégie perd donc de l'argent sous les hypothèses de son auteur. Après la publication, le ratio net vaut -1,061 avec une statistique t de -4,20, et aucun des
seize réglages de la grille n'échappe à ce signe.

**La prochaine décision.** Le seul chemin qui déplace vraiment le coût de seuil est de décider moins
souvent : passer au mensuel le porte de 3,92 à 6,58 points de base. C'est l'objet qu'une étude
suivante devrait reprendre, en cherchant le pas de temps qui maximise le coût de seuil plutôt que le
ratio de Sharpe.

## Reproduire

```bash
export QUANTLAB_USER_AGENT="votre nom votre courriel"
uv run python studies/007_statistical_arbitrage/run.py
uv run pytest tests/unit/test_strategies_statistical_arbitrage.py -o addopts="" -q
```

L'exécution télécharge 225 séries quotidiennes chez Yahoo, en demande 18 de plus une par une pour la
sonde de titres retirés, déroule 32 fois la chaîne complète, et réécrit l'ensemble de `results/`.
Elle dure environ seize minutes sur un ordinateur portable, et la graine 20260902 gouverne le seul
tirage aléatoire de l'étude, celui du rééchantillonnage par blocs.

**La reproduction n'est pas exacte au bit près, et la raison est la source.** Quatre exécutions
complètes ont été menées le 2026-09-02. Leur coût de seuil de rentabilité a valu 3,928, puis 3,921,
puis 3,919, puis 3,923, puis 3,920 points de base. Leur ratio de Sharpe brut sur la fenêtre de
l'article a valu 1,4605, puis 1,4596, puis 1,4588, puis 1,4601, puis 1,4597. L'écart maximal entre
exécutions vaut donc 0,23 % sur le coût de seuil et 0,12 % sur le ratio brut. Les chiffres des quatre
premières ne sont plus dans `results/`, qui porte la cinquième, et ils sont cités ici pour mesurer
l'écart.

Yahoo révise ses cours ajustés, donc l'entrée change entre deux appels. Le code, lui, est
déterministe : la seule source d'aléa est le rééchantillonnage par blocs, dont la graine est propagée
par `child_generators`. Le chiffre le moins stable de l'étude est le ratio de Sharpe moyen des sept
chemins de validation croisée. Il a valu 0,150 puis 0,139 puis 0,151 puis 0,150 sur les quatre
dernières exécutions, parce qu'il dépend d'une sélection entre seize cellules voisines. Les chiffres
publiés ci-dessus sont ceux de la cinquième exécution, et tous viennent des fichiers de
`results/`.

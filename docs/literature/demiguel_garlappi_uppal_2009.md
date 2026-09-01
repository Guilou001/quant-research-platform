# Optimal versus naive diversification

| | |
|---|---|
| **Auteurs** | Victor DeMiguel, Lorenzo Garlappi, Raman Uppal |
| **Année** | 2009 (version publiée) ; document de travail de juin 2006 consulté |
| **Revue ou source** | The Review of Financial Studies, vol. 22, no 5, p. 1915-1953 |
| **Lien** | https://users.nber.org/~confer/2006/si2006/ap/uppal.pdf (document de travail intitulé « 1/N », première version mars 2005, version de juin 2006, lu intégralement le 2026-09-01) ; version publiée : https://academic.oup.com/rfs/article-abstract/22/5/1915/1592901 (péage) ; SSRN : https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1376199 |
| **Statut de réplication** | non commencé |

**Version publiée non consultée au 2026-09-01, péage Oxford Academic. Tous les chiffres
de cette fiche viennent du document de travail de juin 2006, sauf mention contraire.**
Les deux résumés concordent sur les résultats saillants, quatorze modèles, sept jeux de
données, 3 000 et 6 000 mois. Les tableaux détaillés peuvent différer. Ils doivent être
recontrôlés sur la version publiée avant de servir de cible.

## La question de recherche

Le gain de la diversification optimale survit-il à l'erreur d'estimation ? Les auteurs
comparent hors échantillon quatorze règles d'allocation issues du modèle
espérance-variance et de ses extensions à une règle sans paramètre : mettre \(1/N\) de la
richesse dans chacun des \(N\) actifs. La domination théorique de l'optimisation est acquise depuis Markowitz (1952). La
question posée ici est autre : combien de données faudrait-il pour que cette domination
se voie dans les rendements réalisés ?

## L'intuition économique

Le gain de l'optimisation est du second ordre, le coût de l'erreur d'estimation est du
premier ordre, et l'échantillon dont dispose un gérant fait pencher la balance du mauvais
côté. Ce n'est ni une prime de risque ni un biais comportemental, c'est une friction
statistique.

Le mécanisme se lit dans la proposition 1. La perte espérée du portefeuille
espérance-variance estimé contient un terme en \(N/M\). Ici \(N\) est le nombre d'actifs
et \(M\) la fenêtre d'estimation, le nombre de mois servant à estimer les paramètres. Le nombre de paramètres à estimer croît en \(N\), voire en \(N^2\) pour
la matrice de covariance, alors que l'information croît en \(M\). La règle \(1/N\), elle,
n'estime rien : sa perte ne dépend que de son écart structurel à l'optimum,
\(S_*^2 - S_{ew}^2\), et cet écart ne se creuse pas quand \(N\) augmente.

Deux choses feraient disparaître le résultat. La première est l'allongement de la
fenêtre, mais l'article montre que la longueur requise se compte en milliers de mois.
La seconde est l'écart entre le ratio de Sharpe du portefeuille tangent et celui de
\(1/N\) : si l'optimum ex ante était très supérieur à \(1/N\), le seuil tomberait.
L'article calibre justement ce rapport sur les données. Le Sharpe de \(1/N\) y vaut
environ la moitié de celui du portefeuille espérance-variance en échantillon, et cette
moitié suffit à rendre le seuil inatteignable.

## Les données

Sept jeux de données empiriques, tous en rendements mensuels excédentaires au bon du
Trésor américain à 90 jours du site de Ken French. Le tableau 2 du document de travail
les liste, avec \(N\) le nombre d'actifs risqués et, après le signe plus, le nombre de
portefeuilles de facteurs disponibles.

| # | Jeu (abréviation) | N | Période | Source |
|---|---|---|---|---|
| 1 | Dix secteurs du S&P 500 et le marché américain (S&PSectors) | 10+1 | 01/1981-12/2002 | Roberto Wessels |
| 2 | Dix portefeuilles d'industries et le marché (Industry) | 10+1 | 07/1963-11/2004 | Ken French |
| 3 | Huit indices pays et l'indice mondial (International) | 8+1 | 01/1970-07/2001 | MSCI |
| 4 | SMB, HML et le marché (MKT/SMB/HML) | 2+1 | 07/1963-11/2004 | Ken French |
| 5 | Vingt portefeuilles taille et valeur comptable sur marché, plus le marché (FF-1-factor) | 20+1 | 07/1963-11/2004 | Ken French |
| 6 | Les vingt mêmes, plus MKT, SMB, HML (FF-3-factor) | 20+3 | 07/1963-11/2004 | Ken French |
| 7 | Les vingt mêmes, plus MKT, SMB, HML, MOM (FF-4-factor) | 20+4 | 07/1963-11/2004 | Ken French |
| 8 | Données simulées, N dans {10, 25, 50} | 2 000 ans | modèle de marché | simulation |

Trois précisions du tableau 2, à respecter pour toute réplication. Un, les vingt
portefeuilles taille et valeur sont les 25 de Fama et French moins les 5 contenant les
plus grandes firmes. Cette exclusion est reprise de Wang (2005) : MKT, SMB et HML sont
presque une combinaison linéaire des 25. Deux, les jeux 5, 6 et 7 ne diffèrent que par
les portefeuilles de facteurs adjoints. Trois, les résultats du jeu FF-3-factor ne sont
pas publiés, jugés quasi identiques à ceux de FF-1-factor, ce qui ramène à six colonnes
le tableau des ratios de Sharpe.

## L'univers

Le \(N\) effectif des tableaux compte les portefeuilles de facteurs. Le tableau 3 porte
les en-têtes suivants : S&PSectors \(N = 11\), Industry \(N = 11\), International
\(N = 9\), Mkt/SMB/HML \(N = 3\), FF-1-factor \(N = 21\), FF-4-factor \(N = 24\). Le
portefeuille évalué ne contient que des actifs risqués ; le cas incluant l'actif sans
risque est traité en robustesse et donne des résultats qualitativement semblables.

## La méthodologie

Fenêtre glissante, réestimation mensuelle, aucune donnée future. La fenêtre d'estimation
vaut \(M = 120\) mois pour les résultats publiés, et \(M = 60\) en contrôle, non reporté
faute de place et déclaré sans différence. À chaque mois \(t \geq M\), les paramètres
sont estimés sur les \(M\) mois précédents, les poids en découlent, et le rendement du
mois \(t+1\) est enregistré. Le résultat est une série de \(T - M\) rendements hors
échantillon par stratégie et par jeu de données.

Trois mesures de performance : ratio de Sharpe hors échantillon, rendement équivalent
certain, et rotation, définie comme la somme moyenne des valeurs absolues des
transactions sur les \(N\) actifs. La valeur p de l'écart entre deux ratios de Sharpe
suit Jobson et Korkie (1981) avec la correction de Memmel (2003).

Les quatorze modèles du tableau 1, dans l'ordre de l'article :

1. espérance-variance sur estimateurs d'échantillon (mv) ;
2. a priori bayésien diffus, non reporté, jugé trop proche de mv à ces longueurs de fenêtre ;
3. Bayes-Stein (bs) ;
4. Bayesian Data-and-Model (dm) ;
5. variance minimale (min) ;
6. portefeuille de marché pondéré par la capitalisation (vw) ;
7. modèle à facteur manquant de MacKinlay et Pastor 2000 (mp) ;
8. à 10. mv, bs et min sous contrainte de vente à découvert (mv-c, bs-c, min-c) ;
11. variance minimale sous contraintes généralisées (g-min-c) ;
12. trois fonds de Kan et Zhou (mv-min) ;
13. mélange de variance minimale et de \(1/N\) (ew-min) ;
14. multi-a priori de Garlappi, Uppal et Wang, non reporté, montré comme moyenne pondérée
    de mv et min.

**Ce que les auteurs déclarent ne pas évaluer, et pourquoi.** Ni Ledoit (1996), ni Ledoit
et Wolf (2003), ni Chan, Karceski et Lakonishok (1999), ni Best et Grauer (1992) ne
figurent parmi les quatorze modèles. La raison est écrite chez Jagannathan et Ma (2003,
p. 1654). Sous contrainte de vente à découvert, « the sample covariance
matrix performs almost as well as those constructed using factor models, shrinkage
estimators or daily returns ». Vérifié dans le texte du document de travail. Aucun
estimateur à rétrécissement n'est donc testé dans cet article, contrairement à ce que
laissent croire beaucoup de résumés secondaires. Voir `ledoit_wolf_2004.md`.

## Les équations qui comptent

Le portefeuille estimé est \(\hat{x} = \frac{1}{\gamma}\hat{\Sigma}^{-1}\hat{\mu}\), sous
hypothèse de normalité jointe, avec \(\hat{\mu} \sim N(\mu, \Sigma/M)\) et
\(M\hat{\Sigma} \sim W_N(M-1, \Sigma)\), une loi de Wishart à \(M-1\) degrés de liberté.

Soit \(S_*^2 = \mu^{\top}\Sigma^{-1}\mu\) le carré du ratio de Sharpe du portefeuille
tangent et \(S_{ew}^2 = (1_N^{\top}\mu)^2 / (1_N^{\top}\Sigma 1_N)\) celui de \(1/N\). La
proposition 1 donne les trois conditions sous lesquelles \(1/N\) a la perte espérée la
plus faible.

Moyennes inconnues, covariances connues :

\[ S_*^2 - S_{ew}^2 - \frac{N}{M} < 0. \]

Moyennes connues, covariances inconnues :

\[ k S_*^2 - S_{ew}^2 < 0, \qquad k = \left(\frac{M}{M-N-2}\right)\left(2 - \frac{M(M-2)}{(M-N-1)(M-N-4)}\right) < 1. \]

Les deux inconnues :

\[ k S_*^2 - S_{ew}^2 - h < 0, \qquad h = \frac{NM(M-2)}{(M-N-1)(M-N-2)(M-N-4)} > 0. \]

La fenêtre critique est définie comme
\(M^*_{mv} \equiv \inf\{M : L_{mv}(x^*, \hat{x}) < L_{ew}(x^*, w_{ew})\}\), le plus petit
nombre de périodes d'estimation à partir duquel le portefeuille espérance-variance bat
\(1/N\) en moyenne.

## Les résultats originaux

**Aucun des quatorze modèles ne bat \(1/N\) de façon constante**, ni en ratio de Sharpe,
ni en équivalent certain, ni en rotation. C'est la phrase du résumé, identique dans les
deux versions.

Les ratios de Sharpe mensuels du tableau 3, document de travail de juin 2006 :

| Stratégie | S&PSectors | Industry | Inter'l | Mkt/SMB/HML | FF 1-facteur | FF 4-facteurs |
|---|---|---|---|---|---|---|
| 1/N | 0,1876 | 0,1353 | 0,1277 | 0,2240 | 0,1623 | 0,1753 |
| mv en échantillon | 0,3848 | 0,2124 | 0,2090 | 0,2851 | 0,5098 | 0,5364 |
| mv hors échantillon | 0,0794 | -0,0363 | -0,0719 | 0,2186 | -0,0684 | -0,0031 |
| bs | 0,0811 | -0,0319 | -0,0528 | 0,2536 | -0,0636 | -0,0042 |
| min | 0,0820 | 0,1554 | 0,1490 | 0,2493 | 0,2778 | -0,0183 |
| vw | 0,1444 | 0,1138 | 0,1239 | 0,1138 | 0,1138 | 0,1138 |
| mp | 0,1863 | 0,1249 | 0,1209 | 0,0558 | 0,1525 | 0,1516 |

L'écart entre les deux premières lignes de mv mesure exactement le coût de l'estimation.
Sur S&PSectors, 0,3848 en échantillon tombe à 0,0794 hors échantillon, contre 0,1876 pour
\(1/N\). Sur International, 0,2090 devient -0,0719, contre 0,1277 pour \(1/N\).

**La fenêtre critique, résultat le plus cité, se lit dans la figure 1**, six panneaux
calibrés sur des couples de ratios de Sharpe ex ante. Voici les six lectures données dans
le texte.

| Panneau | \(S_*\) | \(S_{ew}\) | N = 25 | N = 50 | N = 100 |
|---|---|---|---|---|---|
| A | 0,40 | 0,20 | > 200 mois | ~600 mois | > 1 200 mois |
| B | 0,40 | 0,10 | 270 mois | 530 mois | 1 060 mois |
| C | 0,20 | 0,10 | ~1 000 mois | ~2 000 mois | non donné |
| D | 0,20 | 0,05 | non donné | > 1 500 mois | non donné |
| E | 0,15 | 0,12 | **> 3 000 mois** | **> 6 000 mois** | non donné |
| F | 0,15 | 0,08 | > 1 600 mois | > 3 200 mois | non donné |

Ce sont les panneaux E et F qui sont calibrés sur le marché boursier américain, les
valeurs \(S_{ew} = 0{,}12\) et \(S_{ew} = 0{,}08\) venant des tableaux 7 et 8 sur données
simulées. Ce sont donc les 3 000 et 6 000 mois du panneau E que reprend le résumé,
soit 250 et 500 ans, alors que la pratique estime sur 120 mois. Les panneaux A à D sont
calibrés sur les Sharpe en échantillon du tableau 3, 0,40 pour S&PSectors, 0,20 pour
Industry et International, 0,15 pour le marché pondéré.

Trois lectures se perdent souvent et méritent d'être écrites. Un, le chiffre de 3 000
mois n'est pas le résultat empirique de l'article, c'est une valeur analytique tirée de
la proposition 1 sous normalité jointe. Deux, il vaut pour la règle espérance-variance
sur estimateurs d'échantillon, pas pour ses extensions ; l'article dit que sur données
simulées les extensions ne réduisent que modérément cette fenêtre. Trois, le seuil
n'est pas monotone entre panneaux. Abaisser \(S_{ew}\) de 0,20 à 0,10 fait passer le
seuil de plus de 200 à 270 mois à 25 actifs, mais de 600 à 530 mois à 50 actifs.

**Coquille du document de travail de juin 2006, section 5.** Le texte écrit deux fois
« In Panel E » de suite. La seconde occurrence porte sur le cas \(S_{ew} = 0{,}08\), qui
est le panneau F d'après la calibration annoncée deux paragraphes plus haut. À revérifier
sur la version publiée avant de citer les 1 600 et 3 200 mois.

## Les critiques connues

Elles sont nombreuses et portent presque toutes sur le protocole, pas sur la proposition 1.

**Le protocole choisit des portefeuilles à forte rotation et à forte erreur.** Kirby et
Ostdiek (2012), « It's All in the Timing: Simple Active Portfolio Strategies that
Outperform Naive Diversification », Journal of Financial and Quantitative Analysis 47(2),
p. 437-467. Ils soutiennent que le résultat de DGU tient largement au plan
expérimental, centré sur des portefeuilles sujets à un risque d'estimation élevé et à une
rotation extrême. Ils proposent deux règles à faible rotation, le calage sur la
volatilité et le calage rendement sur risque, qui battent \(1/N\) même avec des coûts de
transaction élevés. Abrégé de la revue lu le 2026-09-01, texte intégral non consulté,
aucun chiffre relevé.

**Le coupable serait le modèle de rendement, pas l'optimiseur.** Kritzman, Page et
Turkington (2010), « In Defense of Optimization: The Fallacy of 1/N », Financial Analysts
Journal 66(2), p. 31-39. Ils rapportent que la supériorité apparente de \(1/N\) vient de
l'usage d'échantillons glissants courts pour estimer les espérances, qui produisent des
attentes invraisemblables. Avec des échantillons longs ou des hypothèses plus plausibles,
les portefeuilles optimisés dominent hors échantillon. Article non consulté au
2026-09-01 ; l'abrégé de l'éditeur, lu ce jour-là, porte la thèse mais aucun chiffre.
Les treize jeux de données, les 1 028 séries et les plus de 50 000 portefeuilles optimisés
sont rapportés par deux sources secondaires concordantes, non revérifiés sur l'article.
Les longueurs de fenêtre de 5, 10 et 20 ans, citées par une note de lecture
(https://reasonabledeviations.com/notes/papers/defense_optimisation/), n'ont été
retrouvées dans aucune source de l'éditeur : **non trouvé au 2026-09-01**.

**Il ne faut pas choisir, il faut combiner.** Tu et Zhou (2011), « Markowitz meets Talmud:
A combination of sophisticated and naive diversification strategies », Journal of
Financial Economics 99(1), p. 204-215. Ils construisent la combinaison optimale de
\(1/N\) avec quatre règles savantes : Markowitz, Jorion (1986), MacKinlay et Pastor
(2000) et Kan et Zhou (2007). Ils rapportent que les règles combinées battent \(1/N\)
dans la plupart des cas. Rapporté depuis la notice d'éditeur, article non consulté.

**La critique symétrique, contre ceux qui disent battre \(1/N\).** Zakamulin (2017),
« Superiority of optimized portfolios to naive diversification: fact or fiction? »,
Finance Research Letters 22, p. 122-128. Il rapporte que les portefeuilles optimisés qui
battent \(1/N\) sont inclinés vers les actifs les moins volatils, et qu'après contrôle de
l'effet de faible volatilité il ne reste aucune preuve de surperformance. Cette critique
va dans le sens de DGU, pas contre. Abrégé de la revue lu le 2026-09-01, texte intégral
non consulté, aucun chiffre relevé.

**La réponse des auteurs eux-mêmes.** DeMiguel, Garlappi, Nogales et Uppal (2009),
« A Generalized Approach to Portfolio Optimization: Improving Performance by Constraining
Portfolio Norms », Management Science 55(5), p. 798-812. La variance minimale sous
contrainte de norme sur le vecteur de poids donne des portefeuilles qui tiennent hors
échantillon. Article non consulté ; à lire avant d'écrire que DGU concluent à
l'inutilité de l'optimisation, ce qu'ils ne font pas.

## Les problèmes de réplication connus

**Aucun problème de réplication publié n'a été trouvé au 2026-09-01.** Ce qui suit est
une liste d'obstacles matériels relevés dans l'article lui-même, pas des échecs rapportés.

Le jeu S&PSectors n'est pas public. Les dix portefeuilles sectoriels du S&P 500 viennent
de Roberto Wessels, remercié en note de première page ; il n'existe pas de lien de
téléchargement. Le jeu International vient de MSCI, sous licence. Les jeux 2, 4, 5, 6 et
7 viennent du site de Ken French et sont librement accessibles. Les données ont été
révisées depuis 2004, et les rendements ne seront pas identiques au millésime des auteurs.

Les périodes s'arrêtent en 11/2004 et 12/2002. Toute réplication étendue à aujourd'hui
n'est plus une réplication et doit être déclarée comme extension.

Trois choix de mise en oeuvre pèsent sur les chiffres et doivent être copiés à
l'identique :

1. l'exclusion des 5 portefeuilles de plus grandes firmes parmi les 25 de Fama et French ;
2. la fenêtre \(M = 120\) ;
3. la correction de Memmel (2003) sur le test de Jobson et Korkie. Faute de cette correction, les valeurs p seront fausses sans qu'aucun
test mécanique ne le signale.

## Les biais possibles

**Le protocole fixe une rotation mensuelle intégrale pour toutes les stratégies.** Le
\(1/N\) est rééquilibré chaque mois lui aussi, mais sa rotation ne vient que des
variations de prix, alors que celle des règles optimisées vient des variations des poids
estimés. Le tableau 5 mesure cet écart, et c'est précisément le point d'attaque de Kirby
et Ostdiek.

**La calibration des panneaux E et F est modélisée, pas mesurée.** Les 3 000 et 6 000
mois dépendent du couple \((S_*, S_{ew})\) retenu et de l'hypothèse de normalité jointe
avec paramètres constants. Ce sont des chiffres modélisés, à déclarer comme tels partout
où ils sont repris.

**Le nombre d'actifs reste petit.** Le plus grand jeu compte 24 colonnes. Les résultats
ne disent rien direct du cas où \(N\) dépasse la fenêtre, cas que traitent Ledoit et
Wolf. Voir `ledoit_wolf_2004.md`.

**Les portefeuilles évalués sont des portefeuilles de portefeuilles.** Les actifs sont
des portefeuilles déjà diversifiés, sectoriels ou factoriels, dont les rendements sont
fortement corrélés. Le gain marginal de l'optimisation y est structurellement plus faible
que sur des titres individuels, ce qui joue en faveur de \(1/N\).

**Aucun coût de transaction n'est déduit des ratios de Sharpe.** La rotation est mesurée
séparément, en troisième critère, pas intégrée aux rendements. Une réplication qui
soustrait des coûts change les trois tableaux et n'est plus comparable.

## Nos décisions d'implémentation

non commencé au 2026-09-01

## Nos écarts avec l'article

non commencé au 2026-09-01

## Nos résultats

non commencé au 2026-09-01

## Notre contrôle de robustesse

non commencé au 2026-09-01

## Références

- DeMiguel, V., Garlappi, L. et Uppal, R. (2009), « Optimal Versus Naive Diversification:
  How Inefficient is the 1/N Portfolio Strategy? », Review of Financial Studies 22(5),
  p. 1915-1953. Document de travail « 1/N », juin 2006, consulté :
  https://users.nber.org/~confer/2006/si2006/ap/uppal.pdf
- DeMiguel, V., Garlappi, L., Nogales, F. et Uppal, R. (2009), « A Generalized Approach to
  Portfolio Optimization: Improving Performance by Constraining Portfolio Norms »,
  Management Science 55(5), p. 798-812.
  https://pubsonline.informs.org/doi/10.1287/mnsc.1080.0986
- Kirby, C. et Ostdiek, B. (2012), « It's All in the Timing », Journal of Financial and
  Quantitative Analysis 47(2), p. 437-467.
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1530022
- Kritzman, M., Page, S. et Turkington, D. (2010), « In Defense of Optimization: The
  Fallacy of 1/N », Financial Analysts Journal 66(2), p. 31-39.
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1591171
- Tu, J. et Zhou, G. (2011), « Markowitz meets Talmud », Journal of Financial Economics
  99(1), p. 204-215. https://econpapers.repec.org/RePEc:eee:jfinec:v:99:y:2011:i:1:p:204-215
- Zakamulin, V. (2017), « Superiority of optimized portfolios to naive diversification:
  Fact or fiction? », Finance Research Letters 22, p. 122-128.
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2786291
- Memmel, C. (2003), « Performance hypothesis testing with the Sharpe ratio », Finance
  Letters 1, p. 21-23. Cité par l'article ; non consulté.
- Jobson, J. D. et Korkie, B. (1981), « Performance hypothesis testing with the Sharpe and
  Treynor measures », Journal of Finance 36, p. 889-908. Cité par l'article ; non consulté.
- Markowitz, H. (1952). Fiche interne : `markowitz_1952.md`
- Ledoit, O. et Wolf, M. (2004). Fiche interne : `ledoit_wolf_2004.md`

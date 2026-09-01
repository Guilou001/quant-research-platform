# Momentum de série temporelle

| | |
|---|---|
| **Auteurs** | Tobias J. Moskowitz, Yao Hua Ooi, Lasse Heje Pedersen |
| **Année** | 2012 |
| **Revue ou source** | *Journal of Financial Economics*, vol. 104, n° 2, mai 2012, pages 228 à 250 |
| **Lien** | [doi:10.1016/j.jfineco.2011.11.003](https://doi.org/10.1016/j.jfineco.2011.11.003) ; version consultée le 2026-09-01 : [NYU Stern](https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf) ; [SSRN 2089463](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2089463) ; données mensuelles [AQR](https://www.aqr.com/Insights/Datasets/Time-Series-Momentum-Factors-Monthly) |
| **Statut de réplication** | non commencé |

Article consulté intégralement le 2026-09-01, sur le fac-similé de la version publiée,
23 pages, annexe A comprise. Tous les chiffres ci-dessous en sont extraits, sauf
mention contraire, et portent le statut **rapporté**.

## La question de recherche

Le rendement passé d'un instrument prédit-il son propre rendement futur, sans aucune
comparaison avec les autres instruments ? L'article répond oui, sur des contrats à
terme de quatre classes d'actifs, avec une persistance de un à douze mois suivie d'un
renversement partiel.

La question se distingue de celle de Jegadeesh et Titman (1993) par un point qui
change tout. Le momentum transversal classe les titres les uns par rapport aux autres et achète les
mieux classés. Le momentum de série temporelle regarde chaque instrument seul, et
décide long ou court selon le signe de son propre rendement passé.
Le premier est nécessairement neutre en investissement net, le second ne l'est pas.

Cette distinction n'est pas cosmétique. Les théories comportementales invoquées pour
expliquer le momentum, celles de Barberis, Shleifer et Vishny (1998), de Daniel,
Hirshleifer et Subrahmanyam (1998) et de Hong et Stein (1999), portent toutes sur un
**actif risqué unique**. Elles prédisent donc directement une prévisibilité de série
temporelle, et seulement indirectement une prévisibilité transversale. L'article
mesure la quantité que ces théories prédisent réellement.

## L'intuition économique

Le rendement devrait exister parce que deux populations d'intervenants échangent du
risque à un prix qui ne s'ajuste pas instantanément. L'article nomme deux mécanismes
distincts et les oppose par une prédiction testable.

Le premier mécanisme est comportemental. Le prix sous-réagit d'abord à l'information,
puis surréagit avec retard, quand les suiveurs de tendance entrent à leur tour. La
signature de ce mécanisme est le renversement : ce qui a été poussé trop loin revient
en arrière. L'article mesure ce renversement, sur les quatre années qui suivent la
première année.

Le second mécanisme est une contrainte institutionnelle, la pression de couverture.
Un producteur de matières premières est structurellement vendeur de contrats à terme,
pour fixer son prix de vente ; quelqu'un doit prendre l'autre côté, et ce quelqu'un
demande à être payé. L'article le mesure sur les positions déclarées à la Commodity
Futures Trading Commission, l'organisme fédéral américain qui exige des gros
intervenants qu'ils se déclarent commerciaux ou non commerciaux. Le résultat est que
les spéculateurs suivent la tendance environ un an, réduisent ensuite leur position et
prennent le côté opposé avant le renversement, et gagnent au détriment des couvreurs.

Ces deux mécanismes ne prédisent pas la même chose, et l'article les sépare. Il décompose le rendement d'un contrat à terme en deux morceaux. La variation de prix
capte la diffusion de l'information ; le rendement de portage capte la déformation de
la courbe des contrats sous l'effet de la pression de couverture. Les chocs sur les deux
composantes sont associés au momentum, mais **seuls les chocs de prix se renversent
partiellement**. Une prime payée pour fournir de la liquidité ne se rend pas ; une
erreur de prix se corrige.

Ce qui ferait disparaître ce rendement se lit en creux dans ce que l'article ne
mesure pas. Il ne chiffre **aucun** coût de transaction, aucun coût de renouvellement
des contrats, aucun coût de marge, et la stratégie retenue rebalance tous les mois sur
58 instruments. La capacité et l'encombrement en sont l'autre face : la stratégie est
celle que vendent les fonds à terme gérés, dont l'article montre justement qu'ils y
sont exposés.

## Les données

Des contrats à terme et des contrats à terme de gré à gré, de janvier 1965 à décembre
2009. Le rendement quotidien excédentaire du contrat le plus liquide est calculé chaque
jour, ce contrat étant en général le plus proche de l'échéance ou le suivant. Ces
rendements sont ensuite composés en un indice cumulé, dont se déduit le rendement à
n'importe quel horizon. Les sources
sont principalement Datastream, Bloomberg et les bourses elles-mêmes.

Avant que les contrats à terme n'existent, les séries sont **prolongées par des
substituts**. Les actions prennent les indices MSCI par pays, les taux prennent les
indices obligataires JP Morgan par pays. Les devises prennent les taux au comptant de
Datastream avec les taux courts interbancaires de Bloomberg. Les taux au comptant et à terme de
Citigroup couvrent les devises depuis 1989, sauf le dollar canadien depuis 1992 et le
dollar néo-zélandais depuis 1996.

Les positions de traders viennent des rapports Commitments of Traders de la Commodity
Futures Trading Commission, hebdomadaires, positions du mardi, de janvier 1986 à
décembre 2009. Elles ne couvrent pas tous les contrats : la plupart des matières
premières et des devises, mais parmi les actions et les obligations, seulement les
contrats américains.

Trois indices servent de repères, obtenus via Datastream : MSCI World, l'indice
obligataire agrégé Barclays et le S&P GSCI. S'y ajoutent les facteurs SMB, HML et UMD
du site de Kenneth French, puis les facteurs de valeur et de momentum « partout » de
Asness, Moskowitz et Pedersen (2010).

**L'évaluation des stratégies porte sur 1985-2009**, et non sur l'échantillon complet,
pour que l'ensemble des instruments soit disponible et que les marchés soient
suffisamment liquides. Les auteurs indiquent que les résultats sont semblables et
généralement plus significatifs en remontant à 1965.

## L'univers

**58 instruments, dont 55 seulement sont nommés.** Le décompte du texte est explicite. Il annonce 24 matières premières, 12 paires de
devises croisées construites à partir de neuf devises sous-jacentes, neuf indices
d'actions de marchés développés et treize contrats obligataires souverains. La somme
fait bien 58.

Mais le tableau 1 ne publie que **55 lignes**, parce qu'il ne rapporte que les neuf
paires contre le dollar américain. Les douze paires croisées ne sont listées nulle
part. L'annexe A confirme les trois autres décomptes. Elle parle de « dix taux de
change » en énumérant neuf pays plus les États-Unis, qui est la devise de base. La
liste exacte des 58 séries **ne peut donc pas être reconstruite depuis l'article** :
statut **mesuré** sur le fac-similé le 2026-09-01, par comptage des lignes du tableau 1.

Ce n'est pas une chicane de comptage. Huang, Li, Wang et Zhou (2020), qui utilisent le
jeu de données de Moskowitz, Ooi et Pedersen lui-même, écrivent « approximativement
55 actifs ». La page de données d'AQR, consultée le 2026-09-01, annonce de son côté
« 58 instruments liquides sous-jacents » et des rendements qui commencent en janvier
1985.

**Les 24 matières premières.** Rendement annualisé moyen et volatilité annualisée sur
la période propre à chaque contrat.

| Contrat | Début | Rendement moyen | Volatilité |
|---|---|---|---|
| Aluminium | janvier 1979 | 0,97 % | 23,50 % |
| Brut Brent | avril 1989 | 13,87 % | 32,51 % |
| Bovins vivants | janvier 1965 | 4,52 % | 17,14 % |
| Cacao | janvier 1965 | 5,61 % | 32,38 % |
| Café | mars 1974 | 5,72 % | 38,62 % |
| Cuivre | janvier 1977 | 8,90 % | 27,39 % |
| Maïs | janvier 1965 | -3,19 % | 24,37 % |
| Coton | août 1967 | 1,41 % | 24,35 % |
| Brut WTI | mars 1983 | 11,61 % | 34,72 % |
| Gazole | octobre 1984 | 11,95 % | 33,18 % |
| Or | décembre 1969 | 5,36 % | 21,37 % |
| Fioul de chauffage | décembre 1978 | 9,79 % | 33,78 % |
| Porcs maigres | février 1966 | 3,39 % | 26,01 % |
| Gaz naturel | avril 1990 | -9,74 % | 53,30 % |
| Nickel | janvier 1993 | 12,69 % | 35,76 % |
| Platine | janvier 1992 | 13,15 % | 20,95 % |
| Argent | janvier 1965 | 3,17 % | 31,11 % |
| Soja | janvier 1965 | 5,57 % | 27,26 % |
| Tourteau de soja | septembre 1983 | 6,14 % | 24,59 % |
| Huile de soja | octobre 1990 | 1,07 % | 25,39 % |
| Sucre | janvier 1965 | 4,44 % | 42,87 % |
| Essence sans plomb | décembre 1984 | 15,92 % | 37,36 % |
| Blé | janvier 1965 | -1,84 % | 25,11 % |
| Zinc | janvier 1991 | 1,98 % | 24,76 % |

**Les neuf indices d'actions.**

| Contrat | Début | Rendement moyen | Volatilité |
|---|---|---|---|
| ASX SPI 200, Australie | janvier 1977 | 7,25 % | 18,33 % |
| DAX, Allemagne | janvier 1975 | 6,33 % | 20,41 % |
| IBEX 35, Espagne | janvier 1980 | 9,37 % | 21,84 % |
| CAC 40, France | janvier 1975 | 6,73 % | 20,87 % |
| FTSE/MIB, Italie | juin 1978 | 6,13 % | 24,59 % |
| TOPIX, Japon | juillet 1976 | 2,29 % | 18,66 % |
| AEX, Pays-Bas | janvier 1975 | 7,72 % | 19,18 % |
| FTSE 100, Royaume-Uni | janvier 1975 | 6,97 % | 17,77 % |
| S&P 500, États-Unis | janvier 1965 | 3,47 % | 15,45 % |

**Les treize contrats obligataires.**

| Contrat | Début | Rendement moyen | Volatilité |
|---|---|---|---|
| Australie 3 ans | janvier 1992 | 1,34 % | 2,57 % |
| Australie 10 ans | décembre 1985 | 3,83 % | 8,53 % |
| Zone euro 2 ans | mars 1997 | 1,02 % | 1,53 % |
| Zone euro 5 ans | janvier 1993 | 2,56 % | 3,22 % |
| Zone euro 10 ans | décembre 1979 | 2,40 % | 5,74 % |
| Zone euro 30 ans | décembre 1998 | 4,71 % | 11,70 % |
| Canada 10 ans | décembre 1984 | 4,04 % | 7,36 % |
| Japon 10 ans | décembre 1981 | 3,66 % | 5,40 % |
| Royaume-Uni 10 ans | décembre 1979 | 3,00 % | 9,12 % |
| États-Unis 2 ans | avril 1996 | 1,65 % | 1,86 % |
| États-Unis 5 ans | janvier 1990 | 3,17 % | 4,25 % |
| États-Unis 10 ans | décembre 1979 | 3,80 % | 9,30 % |
| États-Unis 30 ans | janvier 1990 | 9,50 % | 18,56 % |

**Les neuf paires de devises publiées**, toutes contre le dollar américain.

| Contrat | Début | Rendement moyen | Volatilité |
|---|---|---|---|
| Dollar australien | mars 1972 | 1,85 % | 10,86 % |
| Euro, mark avant lui | septembre 1971 | 1,57 % | 11,21 % |
| Dollar canadien | mars 1972 | 0,60 % | 6,29 % |
| Yen | septembre 1971 | 1,35 % | 11,66 % |
| Couronne norvégienne | février 1978 | 1,37 % | 10,56 % |
| Dollar néo-zélandais | février 1978 | 2,31 % | 12,01 % |
| Couronne suédoise | février 1978 | -0,05 % | 11,06 % |
| Franc suisse | septembre 1971 | 1,34 % | 12,33 % |
| Livre sterling | septembre 1971 | 1,39 % | 10,32 % |

Les rendements moyens sont relevés sur l'image des pages. Le signe moins de ce fichier
se perd à l'extraction du texte, et quatre valeurs sont négatives.

Les auteurs signalent en note avoir vérifié la robustesse sur des instruments moins
liquides. Ils citent les bovins d'engraissement, le blé du Kansas, le bois, le jus
d'orange, le caoutchouc et l'étain, puis des devises et des actions de marchés
émergents, puis des contrats de taux moins liquides. Ces résultats **ne sont pas
publiés**.

## La méthodologie

Trois étages, du plus général au plus précis.

**Premier étage, les régressions groupées.** Le rendement mensuel de chaque instrument
est régressé sur son propre rendement retardé de h mois, les deux étant divisés par la
volatilité estimée ex ante. Toutes les dates et tous les contrats sont empilés, et les
écarts types sont regroupés par mois, ce qui corrige la corrélation entre instruments
à une même date. Les retards vont de 1 à 60 mois. Une seconde version ne garde que le
**signe** du rendement passé.

**Deuxième étage, la grille de stratégies.** Pour chaque instrument et chaque mois, la
position est longue si le rendement excédentaire des k derniers mois est positif,
courte sinon, et elle est tenue h mois. La taille de la position est inversement
proportionnelle à la volatilité ex ante. Les valeurs de k et de h sont 1, 3, 6, 9, 12,
24, 36 et 48 mois, soit 64 cellules.

Les observations ne se chevauchent pas, contrairement à ce que le mot « détention de h
mois » laisserait croire. Une **unique** série mensuelle est construite, comme chez Jegadeesh et Titman (1993).
Le rendement du mois t est la moyenne des rendements de tous les portefeuilles encore
actifs à cette date, celui formé le mois précédent, celui d'avant, et ainsi de suite.

**Troisième étage, le facteur TSMOM.** Une seule cellule est retenue pour l'analyse
détaillée, k égale 12 et h égale 1. Chaque position est dimensionnée pour porter une
volatilité annualisée ex ante de 40 %, et le portefeuille diversifié est la moyenne
équipondérée des instruments disponibles à chaque date.

## Les équations qui comptent

**La volatilité ex ante**, qui gouverne tout le dimensionnement :

\[ \sigma_t^2 = 261 \sum_{i=0}^{\infty} (1-\delta)\,\delta^{\,i}\,\left(r_{t-1-i} - \bar{r}_t\right)^2 \]

où 261 est le nombre de jours de bourse qui annualise la variance, les poids
\((1-\delta)\delta^i\) somment à un, et \(\bar{r}_t\) est la moyenne des rendements
pondérée de la même façon. Le paramètre \(\delta\) est choisi pour que le centre de
masse des poids, \(\sum_i (1-\delta)\delta^i i = \delta/(1-\delta)\), vaille 60 jours.

Deux détails d'implémentation se cachent ici. Le facteur d'annualisation est **261**,
pas 252 : statut mesuré sur le texte. Et l'article publie la condition sur le centre de
masse, jamais la valeur de \(\delta\), qui vaut donc \(60/61\), soit environ 0,98361 :
statut **modélisé**, calculé depuis la condition publiée.

Le modèle est le même pour tous les actifs à toutes les dates. Les auteurs précisent
utiliser l'estimation de volatilité en \(t-1\) sur les rendements de \(t\), pour
qu'aucune information future n'entre dans le dimensionnement.

**La régression sur le rendement retardé**, où \(s\) indexe l'instrument :

\[ \frac{r^s_t}{\sigma^s_{t-1}} = \alpha + \beta_h \frac{r^s_{t-h}}{\sigma^s_{t-h-1}} + \varepsilon^s_t \]

**La régression sur le seul signe**, dont le membre de droite est déjà sans dimension :

\[ \frac{r^s_t}{\sigma^s_{t-1}} = \alpha + \beta_h \operatorname{sign}\left(r^s_{t-h}\right) + \varepsilon^s_t \]

**Le rendement TSMOM d'un instrument**, l'équation à recopier exactement :

\[ r^{\text{TSMOM},s}_{t,t+1} = \operatorname{sign}\left(r^s_{t-12,t}\right) \frac{40\,\%}{\sigma^s_t}\, r^s_{t,t+1} \]

L'indice de \(\sigma\) est bien \(t\) alors que le rendement porte sur \(t\) à
\(t+1\). La volatilité est donc celle connue à la date de décision, et le décalage
reste celui décrit plus haut. Écrire \(\sigma^s_{t+1}\) par symétrie
introduirait une fuite d'information.

**La régression d'évaluation**, celle dont le tableau 2 publie les t de la constante :

\[ r^{\text{TSMOM}(k,h)}_t = \alpha + \beta_1 MKT_t + \beta_2 BOND_t + \beta_3 GSCI_t
   + s\,SMB_t + h\,HML_t + m\,UMD_t + \varepsilon_t \]

**Le portefeuille diversifié**, sur les \(S_t\) instruments disponibles à la date t :

\[ r^{\text{TSMOM}}_{t,t+1} = \frac{1}{S_t} \sum_{s=1}^{S_t} \operatorname{sign}\left(r^s_{t-12,t}\right) \frac{40\,\%}{\sigma^s_t}\, r^s_{t,t+1} \]

Le choix de 40 % est déclaré sans conséquence par les auteurs, et il l'est en effet
pour le ratio de Sharpe, puisqu'il multiplie tous les rendements par une constante. Il
ne l'est pas pour le niveau : c'est lui qui produit les 12 % de volatilité annualisée
du portefeuille diversifié. La justification donnée est que 40 % ressemble au risque
d'une action individuelle moyenne.

## Les résultats originaux

**Les 12 premiers retards prédisent positivement, les suivants négativement.** Les t
de Student des régressions groupées sont positifs pour les retards de 1 à 12 mois,
dont neuf significatifs, et majoritairement négatifs au-delà. Les renversements les
plus significatifs surviennent dans l'année qui suit la période de continuation. Les
deux spécifications, sur le rendement et sur le seul signe, donnent le même profil, et
le refaire classe par classe le reproduit.

**La grille des 64 cellules.** Le tableau 2 publie les t des alphas, c'est-à-dire des constantes de régression. Le
rendement de chaque stratégie y est régressé sur l'indice MSCI World, l'indice
obligataire, l'indice S&P GSCI et les facteurs SMB, HML et UMD. Pour
l'ensemble des classes d'actifs :

| Formation \ Détention | 1 | 3 | 6 | 9 | 12 | 24 | 36 | 48 |
|---|---|---|---|---|---|---|---|---|
| 1 | 4,34 | 4,68 | 3,83 | 4,29 | 5,12 | 3,02 | 2,74 | 1,90 |
| 3 | 5,35 | 4,42 | 3,54 | 4,73 | 4,50 | 2,60 | 1,97 | 1,52 |
| 6 | 5,03 | 4,54 | 4,93 | 5,32 | 4,43 | 2,79 | 1,89 | 1,42 |
| 9 | 6,06 | 6,13 | 5,78 | 5,07 | 4,10 | 2,57 | 1,45 | 1,19 |
| 12 | **6,61** | 5,60 | 4,44 | 3,69 | 2,85 | 1,68 | 0,66 | 0,46 |
| 24 | 3,95 | 3,19 | 2,44 | 1,95 | 1,50 | 0,20 | -0,09 | -0,33 |
| 36 | 2,70 | 2,20 | 1,44 | 0,96 | 0,62 | 0,28 | 0,07 | 0,20 |
| 48 | 1,84 | 1,55 | 1,16 | 1,00 | 0,86 | 0,38 | 0,46 | 0,74 |

Deux cellules seulement sont négatives, celles de la formation à 24 mois pour des
détentions de 36 et 48 mois. Les signes ont été relevés sur l'image de la page, le
signe moins de ce fichier étant perdu par l'extraction du texte.

**Chaque contrat, pris seul, gagne.** Les 58 contrats affichent un ratio de Sharpe
brut positif pour la stratégie à douze mois, et 52 sont significativement différents
de zéro au seuil de 5 %. Comparée à une position toujours longue sur le même
instrument, la stratégie dégage un alpha positif dans 90 % des cas, dont 26 % sont
significatifs, et aucun des rares alphas négatifs ne l'est.

**Le portefeuille diversifié.** Sa volatilité annualisée est de 12 % par an sur
1985-2009, un niveau comparable à celui des facteurs de Fama et French (1993). Son
ratio de Sharpe est annoncé « supérieur à un », soit environ 2,5 fois celui du
portefeuille de marché actions. **Le chiffre exact du ratio de Sharpe du portefeuille
diversifié n'est pas imprimé dans le texte de l'article : non trouvé au 2026-09-01.**
L'usage de marge est estimé entre 5 % et 20 %.

**Les alphas.** Contre l'indice MSCI World et les facteurs SMB, HML et UMD, l'alpha
mensuel est de 1,58 % avec un t de 7,99. Sur données trimestrielles non chevauchantes,
il est de 4,75 % avec un t de 7,73, pour un R carré de 23 %.

| Régression mensuelle | MSCI World | SMB | HML | UMD | Constante | R carré |
|---|---|---|---|---|---|---|
| coefficient | 0,09 | -0,05 | -0,01 | 0,28 | 1,58 % | 14 % |
| t de Student | 1,89 | -0,84 | -0,21 | 6,78 | 7,99 | |

| Régression trimestrielle | MSCI World | SMB | HML | UMD | Constante | R carré |
|---|---|---|---|---|---|---|
| coefficient | 0,07 | -0,18 | 0,01 | 0,32 | 4,75 % | 23 % |
| t de Student | 1,00 | -1,44 | 0,11 | 4,44 | 7,73 | |

Contre les facteurs de valeur et de momentum « partout » de Asness, Moskowitz et
Pedersen (2010), l'alpha mensuel tombe à 1,09 % avec un t de 5,40. Le trimestriel tombe
à 2,93 % avec un t de 4,12.

| Régression mensuelle | MSCI World | Valeur partout | Momentum partout | Constante | R carré |
|---|---|---|---|---|---|
| coefficient | 0,11 | 0,14 | 0,66 | 1,09 % | 30 % |
| t de Student | 2,67 | 2,02 | 9,74 | 5,40 | |

| Régression trimestrielle | MSCI World | Valeur partout | Momentum partout | Constante | R carré |
|---|---|---|---|---|---|
| coefficient | 0,12 | 0,26 | 0,71 | 2,93 % | 34 % |
| t de Student | 1,81 | 2,45 | 6,47 | 4,12 | |

**Le texte de l'article contredit son propre tableau 3 sur un point.** Il écrit qu'il
ne trouve de charge significative ni sur l'indice de marché ni sur le facteur de
valeur « partout ». Or le panneau B publie un t de 2,67 pour le premier et de 2,02
pour le second, en données mensuelles. Statut **mesuré** sur le fac-similé le
2026-09-01, par lecture de l'image de la page.

**La stratégie ressemble à un stellage**, l'achat simultané d'une option d'achat et
d'une option de vente au même prix d'exercice, qui gagne dès que le sous-jacent bouge
fort. Le panneau C du tableau 3, en données trimestrielles, donne un coefficient de
1,99 sur le carré du rendement du marché, avec un t de 3,88. Le coefficient
sur le rendement lui-même vaut -0,01, avec un t de -0,17. Les gains sont donc les plus
grands lors des plus fortes variations, à la hausse comme à la baisse. Les profits sont importants en
octobre, novembre et décembre 2008, après des pertes au troisième trimestre, et la
stratégie perd nettement en mars, avril et mai 2009, quand la crise se retourne.

**Hors échantillon, avant l'échantillon.** Sur 1966-1985, avec le nombre limité
d'instruments disponibles, le facteur affiche un rendement significatif et un ratio de
Sharpe annualisé de 1,1.

**La structure de corrélation, qui est le résultat le plus dérangeant.** À l'intérieur d'une classe d'actifs, la corrélation moyenne deux à deux des stratégies
vaut 0,37 et 0,38 pour les actions et les taux. Elle tombe à 0,10 pour les matières
premières et à 0,07 pour les devises. Les positions longues passives sont plus corrélées que les stratégies, sauf
pour les devises. Entre classes d'actifs, en revanche, toutes les corrélations des
stratégies sont positives, de 0,05 à 0,21, et **chacune dépasse** la corrélation
correspondante des positions longues passives, dont plusieurs sont négatives. Il
existe donc une composante commune aux stratégies de tendance qui n'existe pas dans
les actifs eux-mêmes, et aucun modèle comportemental n'en rend compte.

**La liquidité n'explique pas le classement.** La corrélation entre le ratio de Sharpe
d'un contrat et son illiquidité, mesurée par le rang normalisé du volume quotidien
dans sa classe, vaut -0,16.

**La décomposition.** L'autocovariance domine, pour le momentum de série temporelle
comme pour le momentum transversal. Pour l'ensemble des actifs, la contribution
mensuelle se répartit en 0,54 % d'autocovariance et 0,29 % du terme de moyenne au
carré. Le total du côté série temporelle vaut 0,83 %.

**Le lien avec le momentum transversal.** Régressé sur le facteur TSMOM, le momentum transversal appliqué aux mêmes actifs donne
une pente de 0,66 avec un t de 15,17, pour un R carré de 44 %. Sa constante, 0,16 %,
n'est pas significative, avec un t de 1,17 (tableau 5, panneau C). La régression
inverse, TSMOM sur le momentum transversal, garde la même pente et le même R carré.
Sa constante vaut pourtant 0,76 % par mois avec un t de 5,90, donc significative
(tableau 5, panneau A). C'est cette asymétrie qui autorise la conclusion : le momentum de série
temporelle explique le momentum transversal, et pas l'inverse.

## Les critiques connues

**L'objection principale, publiée dans la même revue : Huang, Li, Wang et Zhou
(2020).** *Time series momentum: is it there?*, *Journal of Financial Economics*, vol.
135, n° 3, pages 774 à 794. Article consulté le 2026-09-01 sur le tiré à part de la
version publiée. Ils utilisent **le jeu de données de Moskowitz, Ooi et Pedersen
lui-même**, et non un jeu reconstruit, ce qui rend l'objection difficile à écarter par
un argument de données.

Leur démonstration se fait en trois temps.

*Un, actif par actif, il n'y a presque rien.* En régressant le rendement mensuel de
chaque actif sur son propre rendement des douze mois précédents, **47 des 55 actifs
ont un t inférieur à 1,65**, le seuil à 10 %. En calculant le R carré hors échantillon
de Campbell et Thompson (2008), qui compare la prévision à la moyenne historique,
**seuls trois actifs** sont significatifs à 10 %.

*Deux, le t de la régression groupée n'est pas ce qu'il paraît.* Ils reproduisent le t
de 4,34 de la régression groupée sur le retard de douze mois. Ils avancent trois
raisons pour lesquelles cette régression rejette trop souvent l'hypothèse nulle. La
pente est biaisée vers le haut quand les actifs ont des moyennes différentes et qu'on
ne contrôle pas les effets fixes, ce qui est le résultat de Hjalmarsson (2010). Le
rendement des douze derniers mois est un prédicteur persistant, source de distorsions
de taille connues depuis Stambaugh (1999). Et la normalisation par la volatilité, sans
effets fixes, aggrave le biais.

Ils mesurent alors l'ampleur de ce rejet excessif par deux amorçages, c'est-à-dire des
rééchantillonnages qui construisent la distribution du t sous l'hypothèse d'absence de
prévisibilité. **Les valeurs critiques à 5 % sont de 12,53 pour l'amorçage
paramétrique sauvage et de 4,83 pour l'amorçage non paramétrique par paires.** Les
deux dépassent le 4,34 observé. Le résultat tient dans toutes les variantes testées,
par classe d'actifs, sur d'autres périodes, et sans normalisation par la volatilité.

*Trois, la stratégie gagne sans avoir besoin de prévisibilité.* Ils construisent une
stratégie témoin, dite TSH, qui achète un actif si sa **moyenne historique** est
positive et le vend sinon. Cette stratégie est rentable même si les rendements sont
indépendants dans le temps, du moment que certains actifs ont une moyenne plus élevée
que d'autres. Or TSM et TSH se comportent pratiquement de la même façon, et l'écart de
leurs rendements moyens comme de leurs rendements ajustés du risque est indiscernable
de zéro. Dans les deux cas, la performance vient de la jambe longue, la jambe courte
n'ayant pas de rendement significatif. La pente prédictive de Lewellen (2015) vaudrait un si la prévision était parfaite.
Elle est proche de zéro pour les prévisions TSM. Et régresser les prévisions TSM sur
les prévisions TSH donne une pente proche de un. Enfin, en simulant mille échantillons à degré de momentum imposé, TSM ne domine
TSH que lorsque la pente atteint 0,4, alors que la pente estimée sur données réelles,
avec effets fixes, vaut **0,08**.

Leur conclusion, telle qu'elle est écrite : la preuve du momentum de série temporelle
est faible, particulièrement sur une large coupe d'actifs.

**Le gain vient de la normalisation par la volatilité.** Kim, Tse et Wald (2016),
*Time series momentum and volatility scaling*, *Journal of Financial Markets*.
Sans normalisation par la volatilité, les alphas de la stratégie ressemblent à ceux
d'un achat et conservation. Autrement dit, ce qui est mesuré serait l'effet d'une
allocation à risque égal plutôt qu'une prévisibilité. Statut : rapporté depuis le
résumé en ligne et depuis la citation qu'en font Huang et coauteurs, article **non
consulté**.

**L'avantage sur le momentum transversal vient de la position longue nette.** Goyal et
Jegadeesh (2018), *Cross-sectional and time-series tests of return predictability:
what is the difference ?*, *The Review of Financial Studies*, vol. 31, n° 5, pages
1784 à 1824. Une stratégie transversale est neutre par construction. Une stratégie de série
temporelle porte une position longue nette qui varie dans le temps. Comme les marchés
passent plus de temps en hausse qu'en baisse, cette position nette rapporte.
Statut : rapporté depuis le résumé en ligne, article **non consulté**.

**Les réponses des auteurs.** Hurst, Ooi et Pedersen (2017), *A century of evidence on trend-following investing*,
*The Journal of Portfolio Management*, remontent à 1880. Ils y reconstruisent une
stratégie de momentum de série temporelle et la disent rentable sur les 110 années
qui suivent.
Babu, Levine, Ooi, Pedersen et Stamelos (2020), *Trends everywhere*, *The Journal of
Investment Management*, ajoutent 82 titres non examinés auparavant et 16
facteurs actions long-court. Ces travaux répondent sur le
terrain de l'échantillon, en apportant des données nouvelles, et non sur celui de
l'inférence, qui est le terrain de Huang et coauteurs. Statut : rapporté depuis les
résumés en ligne, articles **non consultés**.

Il n'a pas été trouvé, au 2026-09-01, de réponse publiée de Moskowitz, Ooi et Pedersen
qui traite directement des valeurs critiques d'amorçage : non trouvé.

## Les problèmes de réplication connus

**Les 58 instruments ne sont pas énumérables.** Trois séries manquent à l'appel, et
les douze paires croisées ne sont nommées nulle part. Toute réplication portera donc
sur au plus 55 séries, comme celle de Huang et coauteurs.

**Les séries sont raboutées avant l'existence des contrats à terme.** Un indice MSCI
pays, un indice obligataire JP Morgan ou un taux au comptant avec un taux interbancaire
ne se comportent pas comme un contrat à terme, notamment sur le rendement de portage.
Le raboutage n'est pas reproductible depuis des sources gratuites.

**La duration des contrats obligataires est normalisée.** Les rendements quotidiens sont ramenés à une duration constante. Elle vaut 2 ans pour
les contrats à 2 et 3 ans, 4 ans pour les 5 ans, 7 ans pour les 10 ans, et 20 ans pour
les 30 ans. Un code qui l'oublie
donne des volatilités relatives fausses entre contrats obligataires.

**Le facteur d'annualisation est 261 et non 252.** L'écart sur la volatilité vaut
\(\sqrt{261/252}-1\), soit 1,77 %, et il se reporte tel quel sur la taille de position :
statut **modélisé**, calculé depuis le seul chiffre publié.

**Le paramètre de lissage doit être déduit.** L'article donne le centre de masse, 60
jours, pas le \(\delta\) qui en découle.

**La série mensuelle unique est une moyenne de cohortes actives**, pas une série de
rendements de détention chevauchants. Confondre les deux change la volatilité de la
stratégie et donc son ratio de Sharpe.

**Aucun coût n'est chargé nulle part.** Le mot « coût de transaction » n'apparaît dans
l'article que dans une citation de la littérature ; mesuré par recherche dans le texte
complet le 2026-09-01. Une réplication qui charge des coûts n'est plus une réplication
et doit le déclarer.

**Deux sources publiques existent pour comparer, et l'une est la série de l'article
elle-même.** AQR publie deux jeux, tous deux consultés le 2026-09-01. Le premier,
« Time series momentum: original paper data », déclare être le jeu d'origine de
Moskowitz, Ooi et Pedersen (2012), de janvier 1985 à décembre 2009, sur les 58
instruments. C'est donc une cible de réplication directe, et non un simple analogue.
Le second, « Time series momentum factors, monthly », est la version prolongée et mise
à jour du même facteur, à partir de janvier 1985. Les deux portent la même
construction, formation à douze mois et détention d'un mois.

## Les biais possibles

**L'absence totale de coûts.** Le rebalancement est mensuel sur 58 instruments, avec
un changement de position à chaque changement de signe. Les coûts de renouvellement des
contrats à terme, les commissions et l'écart acheteur-vendeur ne sont chiffrés nulle
part.

**Le remplissage rétrospectif des séries.** Les substituts d'avant les contrats à
terme ont pu être choisis en connaissant leur comportement.

**La sélection sur la liquidité.** L'univers est celui des contrats « parmi les plus
liquides du monde ». Le choix est justifié par le réalisme de l'exécution, mais il est
fait en fin de période, sur ce qui est devenu liquide.

**L'inflation statistique de la régression groupée.** C'est l'objection de Huang et
coauteurs, et elle porte sur la méthode d'inférence, pas sur les données.

**La fenêtre principale contient un événement dominant.** 1985-2009 se termine sur la
crise de 2008, où la stratégie réalise ses plus gros gains. La figure 3 le montre
explicitement.

**L'exploration de la grille.** Soixante-quatre cellules sont publiées, et la cellule
retenue pour l'analyse détaillée est celle qui porte le t le plus élevé de la première
colonne, 6,61. Les auteurs justifient ce choix par la convention de la littérature
transversale, ce qui est un argument recevable, mais qui ne supprime pas le fait que
la cellule est aussi la meilleure.

**Le renversement mesuré au-delà de douze mois affaiblit la lecture par le risque**,
mais il repose sur les retards longs, dont les t sont les plus faibles de la table.

## Nos décisions d'implémentation

Non commencé au 2026-09-01.

## Nos écarts avec l'article

Non commencé au 2026-09-01.

## Nos résultats

Non commencé au 2026-09-01.

## Notre contrôle de robustesse

Non commencé au 2026-09-01.

## Références

- Moskowitz, T. J., Ooi, Y. H. et Pedersen, L. H. (2012). Time series momentum.
  *Journal of Financial Economics*, 104(2), 228-250.
  [doi:10.1016/j.jfineco.2011.11.003](https://doi.org/10.1016/j.jfineco.2011.11.003)
- Huang, D., Li, J., Wang, L. et Zhou, G. (2020). Time series momentum: is it there?
  *Journal of Financial Economics*, 135(3), 774-794.
  [doi:10.1016/j.jfineco.2019.08.004](https://doi.org/10.1016/j.jfineco.2019.08.004) ;
  [tiré à part](https://down.aefweb.net/WorkingPapers/w717.pdf)
- Kim, A. Y., Tse, Y. et Wald, J. K. (2016). Time series momentum and volatility
  scaling. *Journal of Financial Markets*, 30, 103-124.
  [Page éditeur](https://www.sciencedirect.com/science/article/abs/pii/S1386418116301379)
- Goyal, A. et Jegadeesh, N. (2018). Cross-sectional and time-series tests of return
  predictability: what is the difference? *The Review of Financial Studies*, 31(5),
  1784-1824. [Page éditeur](https://academic.oup.com/rfs/article-abstract/31/5/1784/4636242)
- Hurst, B., Ooi, Y. H. et Pedersen, L. H. (2017). A century of evidence on
  trend-following investing. *The Journal of Portfolio Management*.
  [SSRN 2993026](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2993026)
- Babu, A., Levine, A., Ooi, Y. H., Pedersen, L. H. et Stamelos, E. (2020). Trends
  everywhere. *The Journal of Investment Management*.
  [SSRN 3386035](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3386035) ;
  [page AQR](https://www.aqr.com/Insights/Research/Working-Paper/Trends-Everywhere),
  consultée le 2026-09-01.
- Jegadeesh, N. et Titman, S. (1993). Returns to buying winners and selling losers.
  *The Journal of Finance*, 48(1), 65-91. Fiche du laboratoire :
  [jegadeesh_titman_1993.md](jegadeesh_titman_1993.md)
- AQR Capital Management. Time series momentum factors, données mensuelles.
  [Page de données](https://www.aqr.com/Insights/Datasets/Time-Series-Momentum-Factors-Monthly),
  consultée le 2026-09-01.
- AQR Capital Management (2018). Time series momentum: original paper data, janvier
  1985 à décembre 2009.
  [Page de données](https://www.aqr.com/Insights/Datasets/Time-Series-Momentum-Original-Paper-Data),
  consultée le 2026-09-01.

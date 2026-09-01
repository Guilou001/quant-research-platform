# Pairs Trading: Performance of a Relative-Value Arbitrage Rule

| | |
|---|---|
| **Auteurs** | Evan Gatev (Boston College), William N. Goetzmann (Yale), K. Geert Rouwenhorst (Yale) |
| **Année** | 2006 (première version diffusée en 1999 comme NBER Working Paper 7032, mars 1999) |
| **Revue ou source** | The Review of Financial Studies, vol. 19, no 3 (2006), p. 797-827, doi:10.1093/rfs/hhj020, publication en accès anticipé le 13 février 2006 |
| **Lien** | Fac-similé de l'article publié, consulté et lu intégralement le 2026-09-01 : http://stat.wharton.upenn.edu/~steele/Courses/434/434Context/PairsTrading/PairsTradingGGR.pdf ; notice de l'éditeur : https://academic.oup.com/rfs/article-abstract/19/3/797/1646694 ; document de travail : https://www.nber.org/papers/w7032 ; page SSRN : https://papers.ssrn.com/sol3/papers.cfm?abstract_id=141615 |
| **Statut de réplication** | non commencé |

## La question de recherche

Une règle mécanique qui n'observe que les prix passés peut-elle rapporter un excès de
rendement durable, et si oui, à quoi ce rendement paie-t-il ? Les auteurs prennent la
description que les praticiens donnent du « pairs trading », l'appariement de deux titres
dont les prix ont bougé ensemble. On achète alors le retardataire et on vend le meneur.
Cette description est testée telle quelle.

La tension qui rend la question intéressante tient en deux faits. Le premier : la règle
n'utilise aucune information fondamentale, donc un marché efficient ne devrait lui laisser
aucun rendement ajusté du risque. Le second : la règle est employée depuis les années 1980
par des équipes payées cher pour cela. L'article tranche en faveur de la seconde branche : il
mesure un excès annualisé d'environ 11 % pour ses portefeuilles de tête (**rapporté**, résumé,
p. 797). Il cherche ensuite à quel risque cette rémunération correspond.

## L'intuition économique

Le rendement existe parce que quelqu'un doit être payé pour faire respecter la loi du prix
unique. Cette loi pose que deux placements au flux identique dans chaque état de la nature
valent aujourd'hui le même prix. Deux titres proches substituts s'écartent sur un choc de
liquidité, c'est-à-dire un ordre pressé qui déplace le prix sans information nouvelle. Celui
qui absorbe ce choc prend un risque réel, celui que l'écart continue de se creuser, ou que le
titre vendu à découvert lui soit rappelé au pire moment. L'excès de rendement est le prix de
ce service.

Le mécanisme demande de séparer deux moments. La convergence se comprend seule, puisque des
arbitragistes existent et qu'ils la poursuivent. La divergence, elle, demande une friction :
si l'écart était exploitable sans coût, il ne s'ouvrirait pas. Les auteurs retiennent
l'explication suggérée par l'éditrice Maureen O'Hara, celle du coût de la vente à découvert,
et la testent (section 3.9, p. 823-825).

Une seconde explication, psychologique, court dans l'article sans être privilégiée. Nunzio
Tartaglia, cité p. 799, dit que les gens n'aiment pas acheter un titre qui vient de baisser.
Le pairs trading serait alors la discipline vendue à des investisseurs qui sur-réagissent.
Les auteurs testent cette hypothèse et la rejettent en partie. Les profits ne s'expliquent
pas par le renversement à un mois de Jegadeesh (1990) et de Lehmann (1990). Et la
contribution des jambes acheteuse et vendeuse est asymétrique, ce qu'un simple retour à la
moyenne ne produirait pas.

Ce qui ferait disparaître le rendement est nommé, mesuré, et déjà partiellement observé dans
l'article : l'entrée de capitaux et la baisse des coûts de transaction. La base TASS citée
p. 818 donne 4 G$ d'actifs de fonds de couverture en 1977 contre 137 G$ en 2000, dont 119 G$
en stratégies dites neutres au marché, de valeur relative ou d'arbitrage. Le rendement brut du
portefeuille des vingt meilleures paires passe de 1,18 % par mois avant 1989 à 0,38 % après
(table 8, p. 822). Le rendement ajusté du risque, lui, ne tombe que de 0,67 % à 0,42 %. Les auteurs en tirent
leur conclusion : ce qui a changé n'est pas l'anomalie, mais le facteur commun latent qui la
rémunérait, devenu dormant.

## Les données

Fichiers quotidiens du CRSP, le centre de recherche sur les prix des titres de l'université de
Chicago, de 1962 à décembre 2002. Pour chaque titre, les auteurs construisent un indice
cumulé de rendement total, dividendes réinvestis, et c'est cet indice qui sert de « prix » dans
tout l'article.

La série de rendements mensuels publiée compte 474 observations, ce qui place son premier mois
en juillet 1963. Les trois emplacements où le papier date lui-même son échantillon ne
concordent pas. La note de la table 1 (p. 807) écrit « between July 1963 and December 2002
(474 observations) ». Celle de la table 4 (p. 814) écrit « between June 1963 and December
2002 ». Et les figures 2 et 3 (p. 817) portent « May 1963-December 2002 ». Seule la première
est compatible avec 474 mois. Cette contradiction est signalée ici plutôt que tranchée en
silence.

Le traitement des radiations est déclaré : quand un titre d'une paire sort du CRSP, la
position est fermée au rendement de radiation, ou au dernier prix disponible (p. 804).
Les auteurs refont le calcul sous l'hypothèse extrême d'un rendement de -100 % sur la seule
jambe acheteuse. Le rendement mensuel moyen des vingt meilleures paires ressort alors à
1,32 %, pour un écart type de 1,9 % (note 4, p. 804).

## L'univers

Toutes les actions du CRSP qui n'ont aucune journée sans transaction pendant la période de
formation de douze mois. Ce filtre unique tient lieu de critère de liquidité et rend
l'appariement possible.

Le nombre moyen de paires du portefeuille « toutes paires » est de 2 057 (note de la table 1,
p. 807). L'article ne publie nulle part le nombre de titres retenus. La note de la table 3
(p. 812) donne en revanche les effectifs moyens des quatre groupes sectoriels, qui partitionnent
l'univers. Soit 156 services publics, 61 transports, 371 finance et 1 729 industrie, donc
2 317 titres en moyenne.
La table 2 (p. 809) donne la composition des vingt meilleures paires. Décile de taille moyen
de 2,71, poids de 0,74 dans les trois premiers déciles de capitalisation et de 0,91 dans les
cinq premiers, aux points de coupure du CRSP. Les paires ne sont donc pas faites de petits
titres.

Un fait domine cette composition et pèse sur toute lecture : 71 % des titres des vingt
meilleures paires sont des services publics (p. 809). Les auteurs l'expliquent par la
volatilité plus faible de ce secteur et par sa corrélation aux taux d'intérêt. Ils refont donc
l'exercice à l'intérieur de quatre groupes sectoriels de Standard and Poor's, services publics,
transport, finance et industrie, chaque titre étant classé par son code SIC.

## La méthodologie

La règle tient en six décisions, toutes fixées avant l'étude et jamais retouchées ensuite.

**Un.** Période de formation de douze mois, période de négociation de six mois. Les auteurs
écrivent que les deux durées sont choisies arbitrairement et n'ont pas bougé depuis le début
de l'étude (p. 803).

**Deux.** Appariement par distance euclidienne. Après avoir écarté les titres à journée sans
transaction, ils construisent l'indice cumulé de rendement total de chaque titre et le
normalisent. Ils choisissent ensuite, pour chaque titre, le partenaire qui minimise la somme
des carrés des écarts entre les deux séries de prix normalisées. L'appariement est exhaustif.

**Trois.** Portefeuilles étudiés : les cinq meilleures paires, les vingt meilleures, les vingt
qui suivent les cent premières (rangs 101 à 120), et toutes les paires. Le portefeuille 101 à
120 sert de témoin, parce que les paires de tête partagent des caractéristiques que les autres
n'ont pas.

**Quatre.** Ouverture à deux écarts types. La position s'ouvre quand les prix divergent de plus
de deux écarts types historiques, estimés sur la période de formation. Un dollar est vendu sur
le titre le plus cher, un dollar acheté sur le moins cher. La table 2 (p. 809) traduit ce seuil
en écart de prix. Il vaut 4,76 % pour les cinq meilleures paires et 5,28 % pour les vingt
meilleures. Il monte à 7,56 % pour les rangs 101 à 120, et à 16,89 % pour toutes les paires.

**Cinq.** Fermeture au croisement. La position se dénoue au croisement suivant des prix. Si les
prix ne se croisent pas avant la fin de l'intervalle, les gains ou pertes sont arrêtés au
dernier jour de négociation. Une paire refermée peut se rouvrir dans la même période, et le
fait souvent. La table 2 (p. 809) donne 2,02 aller-retours par paire pour les cinq meilleures,
et une durée moyenne de position ouverte de 3,75 mois.

**Six.** Variante à un jour d'attente. Le reste de l'article utilise une règle qui ouvre le
lendemain de la divergence et ferme le lendemain du croisement, pour neutraliser le rebond
entre cours acheteur et cours vendeur.

Deux mesures de rendement coexistent et ne doivent pas être confondues. Le rendement sur
capital engagé divise le gain par le nombre de paires sélectionnées, y compris celles qui
n'ouvrent jamais. Le rendement pleinement investi le divise par le nombre de paires qui ont
effectivement ouvert. La première est la mesure prudente, la seconde suppose que le capital
inutilisé sert ailleurs.

Enfin, la stratégie est lancée au début de chaque mois. Six cohortes décalées d'un mois
tournent donc en parallèle, et les rendements mensuels sont moyennés entre elles, comme chez
Jegadeesh et Titman (1993). Les tests utilisent des écarts types de Newey-West à six retards.

## Les équations qui comptent

Le critère d'appariement n'est pas numéroté dans l'article, qui le décrit en prose p. 803
comme « the sum of squared deviations between the two normalized price series ». Sous forme
explicite, avec \(P_{it}\) l'indice cumulé de rendement total du titre \(i\) normalisé sur la
période de formation de longueur \(T\) :

\[ \mathrm{SSD}_{ij} = \sum_{t=1}^{T} \left( P_{it} - P_{jt} \right)^{2} \]

et le partenaire retenu pour \(i\) est le \(j\) qui minimise cette somme.

La règle d'ouverture porte sur l'écart des mêmes séries, comparé à deux fois son écart type
estimé sur la période de formation :

\[ \left| P_{it} - P_{jt} \right| > 2\,\hat{\sigma}_{ij} \]

Le rendement quotidien de chaque jambe est une moyenne pondérée par les valeurs courantes,
équations (2) et (3) de l'article, p. 805 :

\[ r_{P,t} = \frac{\sum_{i \in P} w_{i,t}\, r_{i,t}}{\sum_{i \in P} w_{i,t}}, \qquad
w_{i,t} = w_{i,t-1}\left(1 + r_{i,t-1}\right) = \left(1 + r_{i,1}\right)\cdots\left(1 + r_{i,t-1}\right) \]

Les poids se composent, ce qui donne à la position l'interprétation d'un achat conservé, et
les rendements quotidiens sont ensuite composés en rendements mensuels.

La justification théorique repose sur la coïntégration, la propriété qu'une combinaison
linéaire de séries non stationnaires soit, elle, stationnaire. L'équation (1), p. 801, pose
le modèle de prix :

\[ p_{it} = \sum_{l} \beta_{il}\, p_{lt} + e_{it}, \qquad k < n \]

où \(e_{it}\) est faiblement dépendant au sens de Bossaerts (1988). Il existe alors \(r = n - k\)
vecteurs coïntégrants indépendants. Le pairs trading suppose en plus que certains de ces
vecteurs n'ont que deux coordonnées non nulles, hypothèse que les auteurs posent sans la
tester.

## Les résultats originaux

Tous les nombres de cette section sont **rapportés**, lus dans le fac-similé de l'article
publié cité en tête.

**Rendements bruts, sans attente (table 1, panneau A, p. 807).** Rendement mensuel moyen
en excès du portefeuille pleinement investi : 1,308 % pour les cinq meilleures paires
(t de Newey-West 8,84) et 1,436 % pour les vingt meilleures (t = 11,56). Puis 1,081 % pour les
rangs 101 à 120 (t = 11,54) et 1,104 % pour toutes les paires (t = 11,16). Sur capital engagé :
0,784 %, 0,805 %, 0,679 % et 0,614 %.

**Rendements avec un jour d'attente (table 1, panneau B, p. 807).** 0,745 % (t = 6,26),
0,895 % (t = 9,29), 0,795 % (t = 9,40) et 0,715 % (t = 7,92). Sur capital engagé : 0,463 %,
0,520 %, 0,503 % et 0,396 %. La chute vaut 30 à 55 points de base pour le portefeuille
pleinement investi et 20 à 35 points de base sur capital engagé.

**Distribution.** Sur les 474 mois, le portefeuille des vingt meilleures paires connaît 71
mois de rendement négatif contre 124 pour celui des cinq meilleures (p. 806). Les rendements
sont asymétriques à droite : coefficient d'asymétrie de 1,39 pour les vingt meilleures paires
sans attente, contre 0,62 pour les cinq meilleures.

**Coûts de transaction (p. 810).** Les auteurs déduisent le coût du seul écart entre les
deux panneaux de la table 1. La perte de 324 points de base par six mois liée à l'attente d'un
jour couvre deux aller-retours, soit 162 points de base par paire et par aller-retour. Ils
l'interprètent comme un écart effectif de 81 points de base. Pour le portefeuille toutes
paires, l'écart effectif ressort à 70 points de base. Ils notent que cette estimation indirecte
dépasse les 37 points de base mesurés par Peterson et Fialkowski (1994) sur le CRSP en 1991.
Les profits bruts allant de 437 à 549 points de base par semestre, le profit net après 324
points de base de coût va de 113 à 225 points de base par semestre.

**Par secteur, avec un jour d'attente (table 3, p. 811-812).** Rendement mensuel moyen des vingt
meilleures paires : 1,084 % pour les services publics (t = 10,26) et 0,577 % pour le transport
(t = 4,26). Puis 0,775 % pour la finance (t = 7,60) et 0,607 % pour l'industrie (t = 6,93). Aucun
secteur n'est déficitaire.

**Risque (table 4, p. 814).** Ratios de Sharpe mensuels de la règle à un jour d'attente : 0,35
pour les cinq meilleures paires, 0,59 pour les vingt meilleures, 0,55 pour les rangs 101 à 120
et 0,45 pour toutes les paires. La prime d'actions du S&P 500 rend 0,09 sur la même mesure. Les auteurs régressent ensuite sur
les trois facteurs de Fama et French, augmentés du momentum de Carhart et d'un facteur de
renversement à un mois. Les constantes restent significativement positives : 0,545 %
(t = 3,81), 0,764 % (t = 7,08), 0,714 % (t = 8,66) et 0,512 % (t = 5,30). Le coefficient de marché des
vingt meilleures paires vaut -0,032 (t = -0,64), celui du momentum -0,048 (t = -2,45), celui
du renversement 0,072 (t = 1,27). Le \(R^2\) va de 0,05 à 0,54.

**Perte extrême (table 5, p. 815).** Pire mois de la période : -12,6 % pour les cinq
meilleures paires, -8,2 % pour les vingt meilleures. Un mois sur cent perd plus de 4,32 % et
1,94 % respectivement. Pire jour : -10,08 % et -6,72 %.

**Paires aléatoires (table 6, p. 819).** Le test remplace, aux mêmes dates d'ouverture,
les titres de la vraie paire par deux titres tirés dans le même décile de performance du mois
précédent, sur 200 réplications. Le rendement mensuel moyen des paires simulées est
légèrement négatif : -0,137 % pour les cinq meilleures et -0,111 % pour les vingt meilleures,
sans attente. Le profit ne vient donc pas du renversement à un mois.

**Jambes séparées (table 7, p. 821).** Le rendement mensuel moyen de la jambe acheteuse des
vingt meilleures paires est de 1,330 %, celui de la jambe vendeuse de 0,435 %. Après
régression sur les cinq facteurs, la constante de la jambe acheteuse est de 0,243 %. Elle n'est
pas significative pour les cinq ni pour les vingt meilleures paires. Celle de la jambe
vendeuse est de -0,521 %. Le rendement ajusté du risque vient donc surtout de la position
vendeuse.

**Sous-périodes (table 8, p. 822).** Avant 1989, rendement mensuel moyen de 1,181 % pour les
vingt meilleures paires, constante de 0,670 % (t = 4,41). Après 1988, rendement de 0,375 %,
constante de 0,417 % (t = 3,77). La corrélation entre les résidus factoriels du portefeuille
des vingt meilleures paires et ceux des rangs 101 à 120 vaut 0,42 avant 1989 et 0,20 après
(p. 823).

**Vente à découvert (table 9, p. 825).** En n'appariant que des titres des trois premiers
déciles de taille, le rendement des vingt meilleures paires passe de 0,895 % à 0,914 %. En
simulant un rappel des titres empruntés les jours de volume élevé, il tombe à 0,85 %
(t = 9,07), soit une perte de 4 à 13 points de base par mois.

**Test hors échantillon (p. 800).** La première version du document date de 1999 et couvrait
les données jusqu'à fin 1998. Sur 1999-2002, sans aucune retouche de la règle, le rendement en
excès du portefeuille pleinement investi des vingt meilleures paires atteint 10,4 % par an.
L'écart type annuel vaut 3,8 % et le t de Newey-West 4,82.

## Les critiques connues

**La rentabilité décline, et le déclin est confirmé par les auteurs mêmes.** Do et Faff (2010),
« Does Simple Pairs Trading Still Work? », Financial Analysts Journal 66(4), p. 83-95,
reproduisent la méthode sur le CRSP jusqu'en juin 2009. Le rendement mensuel moyen en excès du
portefeuille des vingt meilleures paires passe de 0,86 % sur 1962-1988 à 0,37 % sur 1989-2002
puis à 0,24 % sur 2003-2009. Ces trois chiffres sont **rapportés** depuis le résumé de
l'éditeur, relevé le 2026-09-01 sur RePEc, qui seul les porte tous les trois
(https://econpapers.repec.org/article/tafufajxx/v_3a66_3ay_3a2010_3ai_3a4_3ap_3a83-95.htm).
La fiche du CFA Institute
(https://rpc.cfainstitute.org/research/financial-analysts-journal/2010/does-simple-pairs-trading-still-work)
ne donne, elle, aucun des trois. L'article lui-même est derrière un péage et **n'a pas été
consulté au 2026-09-01**. Cette fiche du CFA Institute confirme en revanche deux énoncés. La
stratégie tient bien pendant les périodes de turbulence prolongée, dont la crise de 2008. Et un
algorithme raffiné ajoute 22 points de base par mois sur les titres bancaires.

**Après coûts complets, la règle de base ne rapporte presque plus rien.** Do et Faff (2012),
« Are Pairs Trading Profits Robust to Trading Costs? », Journal of Financial Research 35(2),
p. 261-287. Leur résumé, consulté au dépôt institutionnel de Bond University
(https://research.bond.edu.au/en/publications/are-pairs-trading-profits-robust-to-trading-costs/),
porte ceci : « After controlling for commissions, market impact, and short selling fees, pairs trading
remains profitable, albeit at much more modest levels. Specifically, we document a
risk-adjusted return of about 30 basis points per month among portfolios of well-matched pairs
that are formed within refined industry groups. » Et la phrase qui compte le plus pour une
réplication : « Notably, both these types of contrarian investing are largely unprofitable
after 2002. » Article intégral non consulté au 2026-09-01, résumé consulté.

**Le déclin se retrouve sur un échantillon plus long.** Rad, Low et Faff (2016), « The
profitability of pairs trading strategies: distance, cointegration and copula methods »,
Quantitative Finance 16(10), p. 1541-1558, texte consulté le 2026-09-01 sur
https://randlow.github.io/2016_QF_PairsTrading.pdf. Sur tout le marché américain de 1962 à
2014, avec des coûts de transaction variables dans le temps, la méthode de distance rend
91 points de base par mois avant coûts et 38 après. Les auteurs notent aussi qu'à partir de
2009 la fréquence des occasions de négociation par la méthode de distance et par la
coïntégration se réduit considérablement, alors qu'elle reste stable pour la méthode par
copules.

**Le critère de distance est analytiquement mal choisi.** Krauss (2017), « Statistical
Arbitrage Pairs Trading Strategies: Review and Outlook », Journal of Economic Surveys 31(2),
p. 513-545, version de travail consultée le 2026-09-01 (FAU IWF Discussion Paper 09/2015,
https://www.iwf.rw.fau.de/files/2016/03/09-2015.pdf). Son argument est décomposable et se
vérifie en deux lignes. En notant \(V(\cdot)\) la variance empirique,

\[ \frac{1}{T}\sum_{t=1}^{T}\left(P_{it}-P_{jt}\right)^{2}
= V\!\left(P_{it}-P_{jt}\right) + \left(\frac{1}{T}\sum_{t=1}^{T}\left(P_{it}-P_{jt}\right)\right)^{2} \]

Minimiser la distance revient donc à minimiser la somme de la variance de l'écart et du carré
de sa moyenne. Or l'arbitragiste veut au contraire un écart à forte variance, puisque son
profit est le produit du nombre d'aller-retours par le gain par aller-retour. Krauss note que
la paire idéale au sens de la distance, celle d'écart nul, ne rapporte rien du tout. Et la
table 2 de l'article montre bien une volatilité d'écart décroissante à mesure qu'on monte
dans le classement.

**Aucun test de coïntégration n'est fait.** Toujours Krauss (2017) : l'article invoque
Bossaerts (1988), qui construit pourtant un test rigoureux par analyse des corrélations
canoniques, mais n'en applique aucun à ses propres paires. La corrélation élevée peut donc
être fallacieuse, et une relation fallacieuse ne revient pas à sa moyenne. Krauss ajoute que
Do et Faff corrigent ce défaut de deux façons, en imposant l'appariement dans les quarante-huit
industries de Fama et French, et en privilégiant les paires à nombreux croisements de zéro.
Mais ils testent alors vingt-neuf combinaisons d'algorithmes, ce qui les expose au
sur-ajustement.

**Les auteurs formulent eux-mêmes deux objections.** Première, l'écart type de la paire de tête
est le plus petit de tous les couples possibles, donc il sous-estime l'écart type vrai. Les
positions s'ouvrent alors trop tôt pour couvrir les frais, même quand la convergence arrive
(p. 811). Seconde, la règle ouvre des positions jusqu'à la veille de la fin de
l'intervalle, ce qui n'a pas de sens (p. 811). Dans les deux cas ils écrivent que des résultats
non publiés confirment le problème, sans les donner.

## Les problèmes de réplication connus

**Les données ne sont pas gratuites.** Le CRSP est payant, et il n'a pas d'équivalent libre
couvrant 1962-2002 avec les rendements de radiation. Une réplication sur données gratuites
souffrira d'un biais de survie, la disparition des titres radiés du fichier téléchargé, et ce
biais joue dans le sens favorable puisque la jambe acheteuse est celle du perdant relatif.

**La date de départ n'est pas la même à trois endroits de l'article.** Juillet 1963 dans la
note de la table 1, juin 1963 dans celle de la table 4, mai 1963 sur les figures 2 et 3. Le
compte de 474 observations tranche pour juillet 1963, mais toute réplication qui reproduit un
tableau et une figure devra choisir, et le dire.

**Le filtre de liquidité dépend d'une convention du CRSP.** La phrase « screen out all stocks that have one or more days with no trade » suppose une
définition opérationnelle du jour sans transaction, prix manquant ou volume nul. L'article ne
la donne pas. Sur douze mois de
séances, ce filtre est sévère et le nombre de titres retenus y est très sensible.

**Le dénominateur du rendement pleinement investi.** Il faut compter les paires qui ouvrent au
moins une fois dans la période de six mois, pas les positions ouvertes. Confondre les deux
change le résultat de plusieurs dizaines de points de base, puisqu'une paire ouvre en moyenne
1,96 fois pour les vingt meilleures (table 2, p. 809).

**La renormalisation en début de période de négociation.** Krauss (2017) écrit que les prix sont
renormalisés au premier jour de la période de négociation. L'article, lui, dit seulement que
la normalisation sert à l'appariement pendant la période de formation, et ne le répète pas pour
la période de négociation. Les deux sources ne disent pas la même chose et le choix change le
seuil de déclenchement. À trancher explicitement lors de la réplication.

**Le seuil est-il centré ?** L'article écrit que la position s'ouvre « when prices diverge by
more than two historical standard deviations ». Il ne précise pas si l'écart est comparé à
zéro ou à sa moyenne de formation. La décomposition de Krauss rappelée plus haut montre que la
moyenne de l'écart n'est pas nulle en général.

**Le coût de calcul.** Avec les 2 317 titres que donne la note de la table 3, l'appariement
exhaustif demande environ 2,7 millions de distances par période de formation, et il y a
474 périodes qui se chevauchent. Ce compte est **modélisé** : il applique \(n(n-1)/2\) à
l'effectif moyen, et l'effectif d'une période donnée n'est pas publié. La réplication naïve en
boucle est impraticable ; il faut passer par des
opérations matricielles.

**Six cohortes décalées.** Le rendement publié n'est pas celui d'une stratégie mais la moyenne
de six stratégies dont les périodes de formation sont décalées d'un mois. Oublier ce
chevauchement fausse à la fois le niveau et l'écart type, et c'est aussi la raison des
corrections de Newey-West à six retards.

## Les biais possibles

**Rebond entre cours acheteur et cours vendeur.** C'est le biais que l'article traite le mieux,
en le mesurant. La règle vend le gagnant, dont le dernier prix est plus souvent un cours
vendeur, et achète le perdant, dont le dernier prix est plus souvent un cours acheteur.
L'attente d'un jour retire 30 à 55 points de base par mois au portefeuille pleinement investi.
Les auteurs écrivent explicitement qu'ils ne savent pas départager ce qui, dans cette chute,
relève du rebond et ce qui relève d'un vrai retour à la moyenne rapide.

**Fouille de données.** Les auteurs s'en défendent de deux façons. Ils déclarent n'avoir
exploré aucune variante de la règle. Et ils exhibent un échantillon de contrôle non simulé,
1999-2002, obtenu par le seul délai entre la version de 1999 et celle de 2006. C'est la
défense la plus solide de l'article. Elle ne couvre toutefois pas les choix initiaux, douze
mois de formation, six mois de négociation, deux écarts types, qu'ils reconnaissent avoir
fixés arbitrairement.

**Concentration sectorielle.** 71 % des titres des vingt meilleures paires sont des services
publics. Le portefeuille hérite donc d'une exposition aux taux d'intérêt. Les auteurs notent
p. 816 que la rentabilité augmente quand les écarts de taux longs diminuent. Ils ajoutent que
cette sensibilité vaut aussi pour les portefeuilles plus diversifiés, donc qu'elle ne vient pas
seulement des services publics.

**Coût de la vente à découvert.** Traité et chiffré, section 3.9. Restreindre aux trois premiers
déciles de taille ne change presque rien, et simuler des rappels d'emprunt les jours de fort
volume coûte 4 à 13 points de base par mois. Les auteurs citent Geczy, Musto et Reed (2002)
pour un taux de rétrocession de 4 à 15 points de base par an chez les grands intervenants.

**Biais de sélection sur l'écart type du déclencheur.** La paire de tête est celle dont l'écart
a la plus faible dispersion mesurée. Cette dispersion est donc l'extrême inférieur d'un très
grand nombre de tirages, et elle sous-estime la dispersion vraie. Les positions s'ouvrent en
conséquence trop tôt. Les auteurs le disent p. 811 sans le quantifier.

**Rendement de radiation.** Le test extrême, -100 % sur la seule jambe acheteuse à la radiation,
laisse 1,32 % par mois pour les vingt meilleures paires. Le biais existe donc mais ne renverse
pas le résultat.

## Nos décisions d'implémentation

non commencé au 2026-09-01

## Nos écarts avec l'article

non commencé au 2026-09-01

## Nos résultats

non commencé au 2026-09-01

## Notre contrôle de robustesse

non commencé au 2026-09-01

## Références

- Gatev, E., Goetzmann, W. N. et Rouwenhorst, K. G. (2006), « Pairs Trading: Performance of a
  Relative-Value Arbitrage Rule », The Review of Financial Studies 19(3), p. 797-827.
  Fac-similé consulté :
  http://stat.wharton.upenn.edu/~steele/Courses/434/434Context/PairsTrading/PairsTradingGGR.pdf
- Gatev, E., Goetzmann, W. N. et Rouwenhorst, K. G. (1999), « Pairs Trading: Performance of a
  Relative Value Arbitrage Rule », NBER Working Paper 7032. https://www.nber.org/papers/w7032
- Do, B. et Faff, R. (2010), « Does Simple Pairs Trading Still Work? », Financial Analysts
  Journal 66(4), p. 83-95. Article non consulté ; résumé de l'éditeur consulté le 2026-09-01 :
  https://www.tandfonline.com/doi/abs/10.2469/faj.v66.n4.1
- Do, B. et Faff, R. (2012), « Are Pairs Trading Profits Robust to Trading Costs? », Journal of
  Financial Research 35(2), p. 261-287. Article non consulté ; résumé consulté le 2026-09-01 :
  https://research.bond.edu.au/en/publications/are-pairs-trading-profits-robust-to-trading-costs/
- Rad, H., Low, R. K. Y. et Faff, R. (2016), « The profitability of pairs trading strategies:
  distance, cointegration and copula methods », Quantitative Finance 16(10), p. 1541-1558.
  Texte consulté : https://randlow.github.io/2016_QF_PairsTrading.pdf
- Krauss, C. (2017), « Statistical Arbitrage Pairs Trading Strategies: Review and Outlook »,
  Journal of Economic Surveys 31(2), p. 513-545. Version de travail consultée, FAU IWF
  Discussion Paper 09/2015 : https://www.iwf.rw.fau.de/files/2016/03/09-2015.pdf
- Bossaerts, P. (1988), « Common Nonstationary Components of Asset Prices », Journal of
  Economic Dynamics and Control 12, p. 347-364. Pagination relevée dans la bibliographie de
  l'article, p. 826 ; le numéro de fascicule n'y figure pas et n'est pas écrit ici. Non
  consulté.
- Jegadeesh, N. (1990), « Evidence of Predictable Behavior of Security Returns », The Journal
  of Finance 45, p. 881-898. Pagination relevée dans la bibliographie de l'article, p. 826. Non
  consulté.
- Jegadeesh, N. et Titman, S. (1993), « Returns to Buying Winners and Selling Losers:
  Implications for Stock Market Efficiency », The Journal of Finance 48, p. 65-91. Titre et
  pagination relevés dans la bibliographie de l'article, p. 826. Non consulté.
- Peterson, M. et Fialkowski, D. (1994), « Posted versus Effective Spreads: Good Prices or Bad
  Quotes? », Journal of Financial Economics 35, p. 269-292. Titre et pagination relevés dans la
  bibliographie de l'article, p. 827. Non consulté.
- Avellaneda, M. et Lee, J.-H. (2010), « Statistical arbitrage in the US equities market »,
  Quantitative Finance 10(7), p. 761-782. Fiche interne : `avellaneda_lee_2010.md`

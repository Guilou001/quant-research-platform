# Carry

| | |
|---|---|
| **Auteurs** | Ralph S. J. Koijen, Tobias J. Moskowitz, Lasse Heje Pedersen, Evert B. Vrugt |
| **Année** | 2018 |
| **Revue ou source** | Journal of Financial Economics, 127(2), 197-225, DOI 10.1016/j.jfineco.2017.11.002 |
| **Lien** | Manuscrit accepté (CC BY-NC-ND) : <https://research-api.cbs.dk/ws/files/57294842/lasse_heje_pedersen_et_al_carry_acceptedmanuscript.pdf> ; document de travail NBER 19325 : <https://www.nber.org/papers/w19325> |
| **Statut de réplication** | non commencé |

Version consultée le 2026-09-01 : le **manuscrit accepté** déposé au CBS Research Portal, 57 pages,
sous licence CC BY-NC-ND. C'est la version acceptée par la revue, donc postérieure à l'arbitrage,
mais sans la pagination Elsevier. La version publiée, derrière un péage, n'a pas été ouverte, et
aucune comparaison ligne à ligne avec elle n'a donc été faite. Tous les chiffres ci-dessous sont
**rapportés** depuis ce manuscrit, avec leur numéro de tableau.

## La question de recherche

Le rendement attendu d'un actif se laisse-t-il lire d'avance, sans modèle d'évaluation, dans le seul
écart entre son prix au comptant et son prix à terme ? Les auteurs appellent cet écart le portage,
le rendement qu'un contrat à terme rapporte si le prix ne bouge pas d'ici l'échéance. La littérature
ne l'avait mesuré qu'en devises, où il se réduit à l'écart de taux d'intérêt entre deux pays.

La tension qui fait l'article : sous la parité des taux d'intérêt non couverte, un portage élevé doit
être exactement annulé par une dépréciation attendue, donc ne rien prédire. Sous des primes de
risque qui varient dans le temps, un portage élevé signale au contraire un rendement attendu élevé.
Les deux thèses se distinguent par un seul coefficient, et il est mesurable dans neuf classes
d'actifs à la fois.

## L'intuition économique

Le portage devrait rapporter parce qu'il est la partie observable d'une prime de risque qui varie
dans le temps, et non parce qu'il annonce une évolution du prix. Le mécanisme se lit sur l'action :
si le rendement exigé d'un titre monte alors que ses dividendes ne changent pas, son prix baisse,
donc son rendement en dividende monte. Le portage monte avec la prime exigée, mécaniquement.

Trois canaux sont testés comme source de cette prime, et aucun ne suffit. Le portage perd de
l'argent quand la liquidité mondiale se dégrade et quand la volatilité implicite monte, et ses trois
pires épisodes tombent sur des récessions mondiales (section 4.4 et annexe D). Le prix du risque de
liquidité ressort positif et celui du risque de volatilité négatif, tous deux significatifs. Les alphas
résistent pourtant : actions, pente obligataire, Treasuries, crédit et options de vente restent
significatifs à 5 % après ajustement.

Ce qui ferait disparaître le rendement. Si les primes de risque cessaient de varier, la régression
de l'équation (23) rendrait un coefficient nul, et le marché reprendrait exactement le portage. Deux
autres extinctions sont possibles. Un capital d'arbitrage devenu assez abondant pour effacer la
compensation exigée en récession. Ou des coûts de transaction montés au niveau des demi-écarts qui
annulent déjà la stratégie sur options (tableau 9, plus bas). Le test direct est
le coefficient \(c\), pas le rendement de la stratégie.

## Les données

Neuf jeux, aucun redistribuable en entier, périodes déclarées dans le tableau 1 du manuscrit.

| Classe | Instruments | Début | Fin |
|---|---|---|---|
| Actions | 13 contrats à terme sur indices nationaux | mars 1988 | septembre 2012 |
| Devises | 20 contrats de change à terme à un mois, plus les États-Unis à portage nul par construction | novembre 1983 (certaines devises février 1997, euro février 1999) | septembre 2012 |
| Matières premières | 24 contrats à terme | janvier 1980 | septembre 2012 |
| Obligations d'État | 10 marchés, contrats à terme synthétiques depuis les taux zéro-coupon de Jonathan Wright jusqu'à mai 2009, puis Bloomberg | novembre 1983 | septembre 2012 |
| Pente 10 ans moins 2 ans | les mêmes 10 marchés | novembre 1983 | septembre 2012 |
| Treasuries américains | 6 portefeuilles CRSP, échéances 1-12, 13-24, 25-36, 37-48, 49-60 et 61-120 mois ; taux de Gurkaynak, Sack et Wright pour le portage | août 1971 | septembre 2012 |
| Crédit américain | indices Barclays, qualités AAA, AA, A et BAA, durations intermédiaire (environ 5 ans) et longue (environ 10 ans) | janvier 1973 | septembre 2012 |
| Options d'achat sur indices | OptionMetrics, 10 indices américains | janvier 1996 | décembre 2011 |
| Options de vente sur indices | OptionMetrics, les mêmes indices | janvier 1996 | décembre 2011 |

Les options sont prises entre 30 et 60 jours d'échéance, le dernier jour de bourse du mois, et tenues
un mois. Deux groupes de delta seulement. Hors de la monnaie, \(\Delta^{call} \in [0{,}2 ; 0{,}4)\)
ou \(\Delta^{put} \in [-0{,}4 ; -0{,}2)\). À la monnaie, \(\Delta^{call} \in [0{,}4 ; 0{,}6)\) ou
\(\Delta^{put} \in [-0{,}6 ; -0{,}4)\). Les échéances non standard sont exclues, et un seul contrat
par groupe de delta est retenu, par volume puis par position ouverte.

Deux incohérences de dates dans le manuscrit, relevées sans être tranchées. La figure 1 annonce un
échantillon « de 1983 à 2012 » pour le facteur mondial de portage. La figure 2 et la figure D.1
annoncent « 1972 à 2012 » pour le même objet. La première période de repli, datée d'août 1972,
donne raison à la seconde date.

## L'univers

Neuf classes d'actifs, ce que les auteurs appellent des classes après avoir séparé le niveau et la
pente des courbes obligataires, puis les options d'achat et les options de vente. Le tableau 2
compte bien neuf lignes de stratégie.

Le regroupement grossier du panneau B rassemble actions, obligations et devises en cinq régions :
Amérique du Nord, Royaume-Uni, Europe continentale, Asie, Nouvelle-Zélande et Australie. Les matières
premières y sont réparties en trois groupes, agriculture et bétail, métaux, énergie. Le crédit, les
Treasuries et les options en sont exclus.

## La méthodologie

Un tri transversal par rang de portage, rééquilibré chaque mois, avec deux dollars d'exposition
brute en permanence. Le poids de chaque titre est proportionnel à l'écart entre son rang de portage
et le rang médian de sa classe. Le portefeuille est donc long sur les portages hauts, court sur les
portages bas, et à somme nulle.

Le facteur mondial de portage, que les auteurs notent GCF, pondère chaque classe par 10 % divisé par
sa volatilité de plein échantillon. Chaque classe contribue donc autant à la volatilité totale. Cette
précaution est nécessaire ici : les options ont environ trois cents fois la volatilité des
Treasuries. Une moyenne simple serait entièrement pilotée par elles (note 21 du manuscrit).

Trois variantes servent de contrôle. La stratégie « carry1-12 » trie sur la moyenne du signal de
portage des douze derniers mois, ce qui efface les effets de saison des actions et des matières
premières. La stratégie « carry2-13 » saute en plus un mois, pour qu'aucune donnée ne serve à la
fois au signal et au rendement. La stratégie de calendrier, enfin, achète ou vend chaque titre selon
que son portage dépasse zéro ou dépasse sa moyenne historique jusqu'à la date courante.

Les positions obligataires sont dimensionnées par leur duration, la sensibilité du prix d'une
obligation à une variation de taux. Sans cet ajustement, un portefeuille long de 1 $ à dix ans et
court de 1 $ à un an serait dominé par le dix ans.

## Les équations qui comptent

La décomposition qui ouvre l'article :

\[ r_{t+1} = \underbrace{C_t + E_t\!\left(\frac{\Delta S_{t+1}}{X_t}\right)}_{E_t(r_{t+1})} + u_{t+1} \]

Le portage d'un contrat à terme, quand le prix au comptant ne bouge pas, avec \(X_t\) le capital
alloué à la position (équation 4) :

\[ C_t = \frac{S_t - F_t}{X_t} \]

Pour une position entièrement collatéralisée, \(X_t = F_t\), d'où l'équation (6) :

\[ C_t = \frac{S_t - F_t}{F_t} \]

Devises, équation (7). Le portage est l'écart de taux, à un facteur d'échelle proche de un près :

\[ C_t = \frac{S_t - F_t}{F_t} = \left(r^{f*}_t - r^{f}_t\right)\frac{1}{1 + r^{f}_t} \]

Actions, équation (8). Le portage est le rendement en dividende attendu, net du taux sans risque
local :

\[ C_t = \left(\frac{E^{Q}_t(D_{t+1})}{S_t} - r^{f}_t\right)\frac{S_t}{F_t} \]

Matières premières, équation (9), avec \(\delta_t\) le rendement de commodité attendu net des coûts
de stockage, c'est-à-dire l'avantage à détenir le bien physique plutôt que le contrat :

\[ C_t = \left(\delta_t - r^{f}\right)\frac{1}{1 + r^{f} - \delta_t} \]

Titres à échéance finie, équation (10). C'est le point technique de l'article : au numérateur, le
prix au comptant d'un titre de maturité \(\tau - 1\), pas \(\tau\), parce qu'au dénouement le
sous-jacent aura vieilli d'une période :

\[ C^{\tau}_t = \frac{S^{\tau-1}_t - F^{\tau}_t}{F^{\tau}_t} \]

Obligations, équation (11), puis sa réécriture par le taux à terme (équation 12) et son
approximation par la duration modifiée (équation 13) :

\[ C^{\tau}_t = \frac{(1+y^{\tau}_t)^{\tau}}{(1+r^{f}_t)(1+y^{\tau-1}_t)^{\tau-1}} - 1
= \frac{f^{\tau-1,\tau}_t - r^{f}_t}{1+r^{f}_t} \]

\[ C^{\tau}_t \simeq \underbrace{(y^{\tau}_t - r^{f}_t)}_{\text{pente}} - \underbrace{D^{mod}\left(y^{\tau-1}_t - y^{\tau}_t\right)}_{\text{descente de courbe}} \]

C'est l'équation qui relie le portage obligataire à la pente de la courbe des taux, prédicteur
classique. Elle montre ce que le portage ajoute : la descente de courbe, le gain de prix obtenu
quand l'obligation vieillit à courbe inchangée.

Ajustement de duration, équation (14), et pente de courbe par pays, équation (15) :

\[ C^{\tau}_t(X = F^{\tau}_t D^{\tau}_t) = \frac{C^{\tau}_t(X = F^{\tau}_t)}{D^{\tau}_t} \]

Options, équation (16), avec \(G^{j}\) le prix d'une option de type \(j\) :

\[ C^{j}_t(\tau, K) = \frac{G^{j}(\tau-1, K; S_t, \sigma_{t,\tau-1})}{(1+r^{f}_t)\,G^{j}(\tau, K; S_t, \sigma_{t,\tau})} - 1 \]

Portage du portefeuille de portage, équation (22), toujours positif par construction :

\[ C^{\text{carry trade}}_t = \sum_{w^i_t > 0} w^i_t C^i_t - \sum_{w^i_t < 0} |w^i_t| C^i_t > 0 \]

Le test central, équation (23), une régression de panel du rendement futur sur le portage avec
effets fixes de contrat et de temps, écarts types groupés par date. Le coefficient \(c\) vaut zéro
sous la parité non couverte et l'hypothèse des anticipations, un si le marché ne reprend rien du
portage, et plus de un si le prix s'apprécie en plus.

Stratégie de calendrier, équation (24) :

\[ w^i_t = z_t\left(2\,\mathbb{I}(C^i_t - \bar{C} > 0) - 1\right) \]

## Les résultats originaux

Toutes les valeurs sont **rapportées** depuis le manuscrit accepté, tableau par tableau.

**Tableau 2, panneau A.** Rendement annualisé en excès, écart type, asymétrie, aplatissement en
excès et ratio de Sharpe annualisé de la stratégie de portage, comparés à une exposition passive
équipondérée dans la même classe.

| Classe | Portage : moyenne | Écart type | Asymétrie | Aplatissement | Sharpe | Passif : Sharpe |
|---|---|---|---|---|---|---|
| Actions mondiales | 9,58 % | 10,48 % | 0,24 | 5,14 | **0,91** | 0,33 |
| Obligations 10 ans (niveau) | 3,85 % | 7,45 % | -0,43 | 6,66 | 0,52 | 0,74 |
| Obligations 10 ans moins 2 ans (pente) | 0,68 % | 0,66 % | 0,33 | 4,92 | **1,03** | 0,01 |
| Treasuries (échéance) | 0,46 % | 0,67 % | 0,47 | 10,46 | 0,68 | 0,57 |
| Matières premières | 11,22 % | 18,78 % | -0,40 | 4,55 | 0,60 | 0,08 |
| Devises | 5,29 % | 7,80 % | -0,68 | 4,46 | 0,68 | 0,36 |
| Crédit | 0,24 % | 0,52 % | 1,31 | 18,18 | 0,47 | 0,34 |
| Options d'achat | 63,55 % | 171,51 % | -2,82 | 14,49 | 0,37 | -0,23 |
| Options de vente | 178,90 % | 99,30 % | -1,75 | 10,12 | **1,80** | -1,01 |
| **Facteur mondial de portage** | **7,18 %** | **5,96 %** | **-0,03** | **5,40** | **1,20** | 0,40 |

Deux chiffres à retenir, et ils ne coïncident pas tout à fait. L'introduction annonce « un ratio de
Sharpe annualisé de 0,8 en moyenne » ; le corps du texte, page 20 du manuscrit, écrit 0,78 comme
moyenne des neuf classes. Le facteur mondial est à 1,20, contre 0,40 pour l'équivalent passif
diversifié. Le repère passif prend trois valeurs selon ce qu'on en fait. La moyenne des neuf
expositions passives prises une par une vaut 0,13. Elle passe à 0,41 en vendant à découvert les
deux stratégies d'options. Le portefeuille passif diversifié à volatilité égalisée, lui, vaut 0,40.
Une réplication doit dire lequel des trois elle vise.

La diversification rapporte moins qu'elle ne le devrait si les neuf portages étaient indépendants :
le gain attendu serait alors d'un facteur trois, il est mesuré à environ 60 % (page 25 du
manuscrit). Sur les 36 corrélations deux à deux du tableau 7, 24 sont positives et 10 significatives
à 5 %.

**Tableau 2, panneau C.** La variante carry1-12 rend un Sharpe de 1,12 pour le facteur mondial,
contre 1,20, avec environ moitié moins de rotation.

**Tableau 4.** Coefficient \(c\) de l'équation (23), spécification avec effets fixes de contrat et de
temps.

| Classe | \(c\) | \(t\) |
|---|---|---|
| Actions mondiales | 1,22 | 4,18 |
| Obligations 10 ans | 1,44 | 3,08 |
| Pente 10 ans moins 2 ans | 0,81 | 4,91 |
| Treasuries | 0,45 | 2,65 |
| Matières premières | 0,01 | 0,13 |
| Devises | 1,09 | 2,69 |
| Crédit | 1,46 | 2,01 |
| Options d'achat | 0,16 | 0,77 |
| Options de vente | 0,60 | 4,16 |

Lu dans le tableau, le coefficient dépasse un pour les actions, le niveau obligataire et le crédit.
Il reste sous un pour la pente, les Treasuries, les matières premières et les options. Il vaut
environ un en devises. Le corps du texte range la pente parmi les coefficients supérieurs à un, ce
que son propre tableau ne donne pas.

Deux réserves écrites par les auteurs eux-mêmes. Le coefficient n'est significativement différent de
un que dans quelques cas seulement. Et les matières premières comme les options d'achat ne
produisent aucune prédiction significative dans cette régression, alors que leurs stratégies de tri
rapportent.

**Tableau 6.** Stratégies de calendrier. Avec la moyenne historique comme référence, le facteur
mondial rend un Sharpe de 0,94 ; avec zéro, 0,93. La corrélation entre les deux séries est de 59 %.
Les options d'achat sont la seule classe négative avec la référence de moyenne (-0,14).

**Tableau 9.** Coûts de transaction, exprimés en demi-écarts acheteur-vendeur, estimés d'après
Bollerslev, Hood, Huss et Pedersen (2016) sauf pour le crédit et les options, mesurés eux dans
OptionMetrics. À cinq demi-écarts, le Sharpe des
actions passe de 0,91 à 0,82, celui des devises de 0,68 à 0,63, celui des matières premières de 0,60
à 0,53. Les options ne survivent pas : les options de vente tombent de 1,80 à 0,42 dès un demi-écart
et à -2,71 à cinq ; les options d'achat de 0,37 à -0,77 puis -3,18. La rotation est de 6,4 et 6,7
pour les deux classes d'options. La rotation n'est pas propre aux options : celle des actions vaut
6,2, plus haut que celle des options de vente. Les sept autres lignes du panneau A vont de 0,5 à 3,6.

**Annexe D.** Les trois pires reculs cumulés du facteur mondial : août 1972 à septembre 1975, mars
1980 à juin 1982, août 2008 à février 2009. Les deux premiers sont aussi les plus longs, et le
troisième par la durée va de mai 1997 à octobre 1998.
Un indicateur de récession mondiale, moyenne pondérée par le PIB de témoins régionaux construits
selon la méthode du NBER, est nettement plus bas pendant ces reculs.

## Les critiques connues

Aucune réfutation publiée visant directement Koijen, Moskowitz, Pedersen et Vrugt (2018) n'a été
trouvée au 2026-09-01, après recherche. Une discussion de congrès et deux articles sur le portage de
change constituent l'essentiel de la contestation trouvée.

**Collin-Dufresne (2012)**, discussion de « Carry » à la réunion de l'American Finance Association,
janvier 2012, portant sur une version antérieure du manuscrit dont les chiffres diffèrent de la
version publiée. Deux objections de fond. La première est un défaut de mesure. Le rendement d'un
contrat à terme dépend du collatéral immobilisé. Omettre l'intérêt sur ce collatéral biaise les
profits vers le haut dès lors que les actifs à portage élevé sont ceux des pays à taux bas. La seconde est
d'interprétation. Le portage est un rapport entre le prix et une grandeur stable liée aux
fondamentaux, dividende ou taux. Le résultat redit alors qu'un prix bas relativement aux
fondamentaux annonce une appréciation, sans dire ce qui meut le prix. Le discutant relève aussi que
l'asymétrie fortement négative n'apparaît qu'en devises, ce qui affaiblit l'explication par le
risque de krach. Discussion consultée le 2026-09-01 dans son texte intégral.

**Daniel, Hodrick et Lu (2017)**, *The Carry Trade: Risks and Drawdowns*, Critical Finance Review,
6(2), 211-262. Le portage de change n'est pas un objet unique. Il se décompose en deux parties. La première est neutre
au dollar : rendement moyen positif, asymétrie fortement négative, corrélation aux facteurs de risque
et pertes extrêmes marquées. La seconde porte l'exposition au dollar : rendement moyen plus élevé,
asymétrie négligeable, corrélation inconditionnelle nulle aux facteurs standard. Voici le point qui
dérange. Après contrôle des trois facteurs de Fama et French, l'alpha de la partie neutre au dollar
tombe à un \(t\) de 1,54, avec un \(R^2\) de 0,10. Le portage complet, lui, garde un alpha de 3,39
avec un \(t\) de 3,76 et un \(R^2\) de 0,04. Le marché explique environ 30 % du rendement moyen de
la partie neutre au dollar, et le facteur de valeur 15 % de plus. Chiffres **rapportés**, lus le
2026-09-01 dans la version publiée, sur l'échantillon de février 1976 à août 2013.

**Bekaert et Panayotov (2020)**, *Good Carry, Bad Carry*, Journal of Financial and Quantitative
Analysis, 55(4), 1063-1094. Parmi les portages construits sur les monnaies du G10, certains
affichent des ratios de Sharpe élevés et parfois une asymétrie positive, d'autres des Sharpe
nettement plus faibles et une asymétrie fortement négative. Les « bons » portages n'utilisent pas
les monnaies habituelles, ni le dollar australien ni le yen. Les prédicteurs de rendement de portage
identifiés dans la littérature prédisent les mauvais portages et pas les bons. Sur les quinze
combinaisons de trois prédicteurs et cinq portages, la pente est significative trois fois pour les
bons contre treize fois pour les mauvais. Le \(R^2\) moyen de prévision vaut 0,7 % contre 2,2 %.
La menace pour l'article de 2018 est directe : si le tri par rang de portage mélange des
sous-portefeuilles aux propriétés opposées, la moyenne agrégée masque la structure. Chiffres
**rapportés**, lus le 2026-09-01 dans le document de travail NBER 25420 de janvier 2019. Le texte
publié n'a pas été ouvert, la revue étant derrière un péage ; son abrégé reprend les deux premières
phrases de celui du document de travail.

**Une contradiction interne, mesurée dans le manuscrit.** Le corps du texte écrit que le coefficient
\(c\) dépasse un pour les actions, le niveau et la pente obligataires et le crédit. Son propre
tableau 4 donne 0,81 pour la pente, avec effets fixes de contrat et de temps. Le texte et le tableau
ne disent donc pas la même chose sur cette classe.

**Une critique structurelle, la nôtre.** Les rendements des options de vente atteignent
178,90 % par an, pour un écart type de 99,30 %. Aucune des huit autres classes n'est du même ordre de
grandeur. Ils survivent à un demi-écart de coût de transaction et pas à deux. Le
tableau 9 le dit lui-même. L'article inclut pourtant cette classe dans la moyenne de 0,78 et dans le
facteur mondial, où la pondération par l'inverse de la volatilité en limite l'effet.

## Les problèmes de réplication connus

Aucun n'est documenté par une tentative publiée que nous ayons trouvée au 2026-09-01. Les obstacles
ci-dessous sont déduits de la section 3.1 du manuscrit et de la nature des sources.

1. **Aucun code ni jeu de données publié.** Le manuscrit ne renvoie à aucun dépôt. Les remerciements
   citent AQR Capital Management pour les données de marché et les conventions, Tarek Hassan, Rui
   Mano et Adrien Verdelhan pour les devises.
2. **Les prix à terme sont propriétaires.** Les 13 indices actions, les 24 matières premières et les
   20 contrats de change ne sont pas téléchargeables librement sur ces profondeurs d'historique.
3. **OptionMetrics est payant.** Sans lui, les deux classes d'options, dont celle qui affiche le
   meilleur ratio de Sharpe de l'article, sont hors d'atteinte.
4. **Les obligations mondiales sont synthétiques, et une de leurs deux sources est payante.**
   L'annexe B nomme les dix pays et les deux fournisseurs de taux zéro-coupon : les données de
   Jonathan Wright, utilisées d'abord dans Wright (2011), jusqu'à mai 2009 inclus, puis Bloomberg à
   partir de juin 2009. La seconde moitié de la période n'est donc pas reproductible sans un terminal Bloomberg.
   Le prix du contrat synthétique se calcule chaque mois sur le zéro-coupon à dix ans et sur celui à
   neuf ans et onze mois, obtenu par interpolation linéaire. La note 12 ajoute que la corrélation
   entre les rendements de ces contrats synthétiques et les vrais contrats à terme dépasse 0,95 dans
   les six pays où les deux existent.
5. **Deux conventions non entièrement spécifiées.** D'abord l'interpolation entre les deux contrats les
   plus proches de l'échéance, qui sert à construire un contrat à un mois sur actions. Ensuite
   l'extrapolation de la courbe des contrats à terme, qui donne un prix au comptant synthétique sur
   matières premières. Les auteurs annoncent suivre les conventions de report du Goldman Sachs
   Commodity Index, sans les détailler.
6. **Les dates de fin de la version publiée.** L'échantillon s'arrête en septembre 2012 pour huit
   classes et en décembre 2011 pour les options, alors que la publication date de 2018. Toute
   réplication portera donc sur une fenêtre qui n'a jamais été hors échantillon pour l'article.

Trois sources sont envisageables pour une réplication partielle. Les taux zéro-coupon de Gurkaynak,
Sack et Wright, cités par les auteurs et publiés par la Réserve fédérale. Les portefeuilles
obligataires du CRSP, sous licence universitaire. Les indices de crédit Barclays, propriétaires. La partie devises
est la plus reproductible, l'écart de taux se reconstruisant depuis des taux publics.

## Les biais possibles

**Biais de survie sur les instruments.** Les 24 matières premières et les 13 indices actions sont ceux
qui existent et se négocient en 2012. Le manuscrit ne dit pas si des contrats disparus ont été
retenus. Non trouvé dans le texte consulté.

**Chevauchement du signal et du rendement.** Le portage à un mois est calculé sur des prix qui
servent aussi au rendement du mois suivant. Les auteurs traitent ce point avec la variante
carry2-13, qui saute un mois, et rapportent des rendements « quasiment identiques ». C'est le
contrôle le plus sérieux de l'article.

**Effets de saison.** Les auteurs reconnaissent que le portage des matières premières et des actions
porte des effets de calendrier marqués, et c'est la raison déclarée de la variante carry1-12. Le
coefficient de panel des matières premières, à 0,01 avec un \(t\) de 0,13, est cohérent avec un
signal dominé par la saison plutôt que par la prime.

**Choix du dimensionnement des positions.** Le portage est linéaire dans le capital alloué
\(X_t\), par construction (équations 3 et 4). Les auteurs le disent ouvertement : un investisseur qui
double son effet de levier, c'est-à-dire qui divise par deux le capital immobilisé, double son
portage mesuré. Le classement des classes entre elles dépend donc de la convention retenue, duration
pour les obligations, collatéralisation complète ailleurs.

**Pondération par la volatilité de plein échantillon.** Le facteur mondial pondère chaque classe par
10 % divisé par sa volatilité mesurée sur toute la période, une information qui n'était pas
disponible au moment des décisions. C'est un regard en avant, faible sur la volatilité qui est
stable, mais réel.

**Sélection des options.** Le filtre retient le contrat au plus fort volume, puis à la plus forte
position ouverte, puis le plus dans la monnaie. La note 17 précise que les résultats sont plus forts
avec les cinq groupes de delta de Frazzini et Pedersen (2011) qu'avec les deux retenus. Le choix a
donc été arrêté après avoir vu les deux options.

**Pas d'ajustement pour tests multiples.** Neuf classes d'actifs, deux définitions de portage, trois
variantes de signal et quatre spécifications d'effets fixes. Aucune correction n'est appliquée aux
seuils de significativité.

## Nos décisions d'implémentation

non commencé au 2026-09-01

## Nos écarts avec l'article

non commencé au 2026-09-01

## Nos résultats

Étude `008_carry`, verdict **`REPLICATED`**, menée le 2026-09-02.

Le test central se reproduit sur les devises, et trois classes d'actifs
sur quatre ne sont pas reproductibles sur données gratuites. Le coefficient de
panel du rendement futur sur le portage vaut 1,084 contre 1,09 publié, t de
2,159, sur 3 177 couples devise-mois de novembre 1983 à septembre 2012. Le
portefeuille de portage rend un ratio de Sharpe de 0,602 contre 0,68 publié,
une asymétrie de -0,666 contre -0,68.

Après la fin de l'échantillon, le coefficient tombe à 0,303 avec un t de 0,294
sur 1 782 couples : la prédiction s'éteint. Le portefeuille rend un Sharpe net
de 0,144 sur 164 mois, intervalle par blocs [-1,17 % ; +2,80 %] par an.

Les matières premières exigent une structure par terme, les indices actions un
dividende attendu, les options une base payante : non trouvé au 2026-09-02,
écrit comme tel plutôt qu'approximé. Verdict `REPLICATED`, sur le portage de
change seul, statut mesuré, source `studies/008_carry/results/`.

## Notre contrôle de robustesse

non commencé au 2026-09-01

## Références

- Koijen, R. S. J., Moskowitz, T. J., Pedersen, L. H. et Vrugt, E. B. (2018). Carry. *Journal of
  Financial Economics*, 127(2), 197-225. DOI 10.1016/j.jfineco.2017.11.002. Manuscrit accepté :
  <https://research-api.cbs.dk/ws/files/57294842/lasse_heje_pedersen_et_al_carry_acceptedmanuscript.pdf>
- Koijen, R. S. J., Moskowitz, T. J., Pedersen, L. H. et Vrugt, E. B. (2013). Carry. *NBER Working
  Paper* 19325. <https://www.nber.org/papers/w19325>
- Daniel, K., Hodrick, R. J. et Lu, Z. (2017). The Carry Trade: Risks and Drawdowns. *Critical
  Finance Review*, 6(2), 211-262. DOI 10.1561/104.00000051
- Bekaert, G. et Panayotov, G. (2020). Good Carry, Bad Carry. *Journal of Financial and Quantitative
  Analysis*, 55(4), 1063-1094.
- Asness, C. S., Moskowitz, T. J. et Pedersen, L. H. (2013). Value and Momentum Everywhere. *Journal
  of Finance*, 68(3), 929-985. Source des facteurs de valeur, de momentum et du choc de liquidité
  mondiale utilisés dans les tableaux 8 et 11.
- Moskowitz, T. J., Ooi, Y. H. et Pedersen, L. H. (2012). Time Series Momentum. *Journal of Financial
  Economics*, 104(2), 228-250. Source du facteur de momentum de séries temporelles du tableau 8.
- Bollerslev, T., Hood, B., Huss, J. et Pedersen, L. H. (2016). Risk Everywhere: Modeling and
  Managing Volatility. Document non publié, Duke University, tel que cité dans la bibliographie du
  manuscrit. Source des estimations de coûts de transaction du tableau 9. Paru depuis dans la
  *Review of Financial Studies*, 31(7), 2729-2773 (2018), DOI 10.1093/rfs/hhy041.
- Lettau, M., Maggiori, M. et Weber, M. (2014). Conditional Risk Premia in Currency Markets and Other
  Asset Classes. *Journal of Financial Economics*, 114, 197-225. Source de la mesure de risque de
  baisse du tableau 10.
- Frazzini, A. et Pedersen, L. H. (2011). Embedded Leverage. Document non publié, AQR Capital
  Management et New York University. Source des filtres sur options, note 17 du manuscrit.
- Collin-Dufresne, P. (2012). Discussion of « Carry ». Présentation à la réunion de l'American
  Finance Association, janvier 2012. <https://www.epfl.ch/labs/sfi-pcd/wp-content/uploads/2021/07/Discussion-of-Carry-2012.pdf>
- Wright, J. H. (2011). Term Premia and Inflation Uncertainty: Empirical Evidence from an
  International Panel Dataset. Source des taux zéro-coupon des dix marchés obligataires jusqu'en mai
  2009, nommée dans l'annexe B du manuscrit. Pagination non vérifiée.

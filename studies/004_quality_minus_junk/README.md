# Qualité moins camelote

## La question de recherche

Le marché paie-t-il la qualité, et la paie-t-il assez pour que l'écart de rendement
disparaisse ? Et le score de qualité se reconstruit-il depuis les seules données publiques ?

**La réponse, en quatre phrases.** Le facteur publié par AQR se réplique bien : nous
mesurons 0,347 pour cent par mois sur la fenêtre de l'article contre 0,40 publié, et un
ratio de Sharpe de 0,559 contre 0,58. Après la publication, ce même facteur tombe à 0,209
de ratio de Sharpe, et l'écart avec la fenêtre d'origine vaut 1,07 erreur type, donc il
n'est pas significatif. **Notre construction depuis les fondamentaux point-in-time de la
SEC ne reproduit PAS le facteur publié** : la corrélation vaut 0,098 sur les cent
trente-deux mois communs, contre un seuil de 0,50 écrit d'avance. Le verdict déduit est
`EXPERIMENTAL`.

Ces quatre phrases ne se contredisent pas. La série publiée est réplicable parce qu'AQR la
publie ; le SCORE qui la produit ne l'est pas avec les données que nous avons, et la
section « Les résultats » chiffre les trois raisons.

Tout chiffre MESURÉ ci-dessous vient d'un fichier de `results/`, et le fichier est nommé.
Les chiffres de l'article sont RAPPORTÉS, et leur source est la fiche de littérature.

## L'article

Asness, C. S., Frazzini, A. et Pedersen, L. H. (2019), « Quality Minus Junk »,
*Review of Accounting Studies* 24(1), 34-112, DOI 10.1007/s11142-018-9470-2.

**La version publiée n'a pas été obtenue.** Springer renvoie une page de protection
anti-robot sous un code 200, et quatre autres voies échouent. Tous les chiffres cibles
viennent de la **version de travail du 19 juin 2014**, dont le tableau VI et l'annexe A1
sont recopiés dans `docs/literature/asness_frazzini_pedersen_2019_qmj.md`. Statut de ces
chiffres : **rapportés**.

Cette lacune n'est pas de forme. Novy-Marx et Medhat (2025, NBER 33601) décrivent le score
de la version publiée avec **trois** composantes, sans la distribution, alors que la
version de travail en définit quatre. La page de données d'AQR, consultée le 2026-09-01,
en annonce quatre. La contradiction n'est pas tranchée, et l'étude suit la version de
travail.

Deux critiques comptent pour la lecture des résultats.

| Auteurs | Ce qu'ils opposent |
|---|---|
| Novy-Marx et Medhat (2025) | Contre le seul facteur de rentabilité, l'alpha de QMJ tombe à -1 point de base, t -0,11. Un investisseur qui détient déjà la rentabilité n'a rien à gagner à ajouter QMJ. |
| Novy-Marx et Velikov (2022) | L'estimateur de bêta employé dans la composante de sûreté mélange bêta de marché et volatilité du titre. Toutes leurs objections s'appliquent donc à cette composante. |

## L'intuition économique

Le rendement vient d'un prix trop bas payé pour une caractéristique persistante et
observable, et le mécanisme se lit dans le modèle de Gordon réécrit :

\[ \frac{P}{B} = \frac{\text{rentabilité} \times \text{taux de distribution}}{\text{rendement exigé} - \text{croissance}} \]

Les quatre grandeurs du membre de droite sont exactement les quatre composantes du score.
Une société plus rentable, qui croît davantage, dont le rendement exigé est plus faible
parce qu'elle est plus sûre, ou qui distribue davantage, devrait valoir plus cher par unité
de valeur comptable. Ce n'est pas une prédiction de rendement mais une prédiction de PRIX,
et c'est ce qui distingue l'article de la littérature sur les anomalies.

Le fait mesuré par les auteurs est que ce prix ne monte pas assez. Une hausse d'un écart
type du score s'accompagne au mieux d'une hausse de 0,32 écart type du prix, et la qualité
n'explique que 12 pour cent de la variance transversale des prix.

**Ce qui ferait disparaître le rendement.** Trois extinctions, dans l'ordre de
vraisemblance. Le prix de la qualité monte, et l'écart de rendement se referme. Le facteur
est absorbé par la rentabilité seule, ce que soutiennent Novy-Marx et Medhat. Enfin les
frais de rotation annulent le gain, ce que la section « Les coûts » chiffre.

## La définition mathématique

Le score agrège quatre composantes, chacune agrégeant ses propres variables. Chaque
variable devient un rang transversal, le rang est centré et réduit, les cotes se somment
par composante, et la somme est standardisée à son tour :

\[ z(x) = \frac{r - \mu_r}{\sigma_r}, \qquad \text{Qualité} = z\left(z_{\text{rent}} + z_{\text{crois}} + z_{\text{sûr}} + z_{\text{distr}}\right) \]

Les vingt et une variables de l'annexe A1, par composante.

| Composante | Variables |
|---|---|
| Rentabilité | profit brut sur actif, résultat sur fonds propres, résultat sur actif, flux de trésorerie sur actif, marge brute, opposé des régularisations |
| Croissance | la variation sur cinq ans des six mêmes numérateurs, divisée par le dénominateur retardé de cinq ans |
| Sûreté | opposé du bêta, opposé de la volatilité résiduelle, opposé du levier, opposé de la cote O d'Ohlson, cote Z d'Altman, opposé de la volatilité des bénéfices |
| Distribution | opposé de la croissance du nombre d'actions, opposé de la croissance de la dette, taux de distribution net sur cinq ans |

Le facteur est l'intersection de deux paquets de taille et de trois paquets de qualité, le
tri étant CONDITIONNEL, la taille d'abord :

\[ QMJ = \tfrac{1}{2}\left(Q^{petit} + Q^{grand}\right) - \tfrac{1}{2}\left(J^{petit} + J^{grand}\right) \]

Le fonds de roulement vaut \(WC = ACT - LCT - CHE + DLC + TXP\), la dette totale vaut
\(TOTD = DLTT + DLC + MIBT + PSTK\), et les fonds propres comptables valent les capitaux
propres moins les actions privilégiées.

## Les données

Trois sources, et chacune répond à une question que les deux autres ne peuvent pas traiter.
Source du tableau : `results/tables/universe_coverage.csv` et `results/metrics.json`.

| Source | Ce qu'elle apporte | Couverture |
|---|---|---|
| AQR, facteurs QMJ mensuels | le facteur publié, vingt-quatre pays | 828 mois, 1957-07 à 2026-06 pour les États-Unis |
| SEC, jeux trimestriels de données financières | les fondamentaux point-in-time, date de dépôt comprise | 69 trimestres, 2009 T2 à 2026 T2 |
| Yahoo Finance | les prix quotidiens de l'univers | 1 526 titres, 2009-01 à 2026-06 |
| Kenneth French, portefeuilles triés | le repli à trois composantes, sans biais du survivant | 756 mois, 1963-07 à 2026-06 |

**Comment lire ce tableau, en trois constats.** Un, la date de dépôt des jeux de la SEC
rend le point-in-time NATIF : la colonne `filed` dit quand chaque exercice est devenu
public, et rien d'autre ne gouverne l'accès. Deux, ces jeux commencent au deuxième
trimestre 2009, ce qui fixe à lui seul la fenêtre de notre construction. Trois, les prix de
Yahoo ne sont pas sans biais du survivant, et la section suivante mesure ce que cela coûte.

**L'univers, et son biais.** La liste des symboles téléchargés se bâtit en quatre temps,
tous mesurés dans `results/tables/universe_coverage.csv`.

| Étape | Compte |
|---|---:|
| Sociétés retenues par au moins un crible annuel de taille | 2 534 |
| Sociétés retrouvées dans la carte des symboles d'aujourd'hui | 1 557 |
| Symboles pour lesquels Yahoo rend des prix | 1 526 |
| Sociétés présentes au panneau de caractéristiques | 1 526 |

**Ce que ce tableau dit, en deux constats.** Un, **977 sociétés sur 2 534, soit 38,6 pour
cent, ne sont plus dans la carte des symboles**. Ce sont des radiations, des fusions et des
faillites, et leur absence est le biais du survivant, mesuré ici plutôt que supposé. Deux,
le sens du biais est connu : la jambe COURTE du facteur, celle de la camelote, perd ses
pires membres, donc le rendement du facteur est sous-estimé, pas flatté.

**Le crible de taille s'applique DATE PAR DATE, et le tableau ci-dessous dit ce que
coûterait l'inverse.** Source : `results/tables/universe_screen.csv`. La réunion des douze
cribles annuels sert à borner la liste téléchargée, une fois pour toutes. La section
transversale d'une date, elle, ne reçoit que le crible en vigueur ce jour-là.

| Fin de juin | Crible du jour | Sociétés au panneau | Retenues | Hors crible du jour | Part |
|---|---:|---:|---:|---:|---:|
| 2015 | 1 605 | 1 159 | 902 | 257 | 22,2 % |
| 2020 | 1 553 | 1 329 | 1 105 | 224 | 16,9 % |
| 2026 | 1 542 | 1 518 | 1 347 | 171 | 11,3 % |

**Comment lire ce tableau, en trois constats.** Un, en juin 2015, **257 des 1 159 sociétés
du panneau, soit 22,2 pour cent, n'appartenaient pas encore au crible de ce jour-là** : un
crible postérieur seul les admet, parce qu'elles n'ont grossi qu'après. Deux, la part
tombe à 11,3 pour cent en 2026, ce qui est attendu, la fenêtre de croissance restante se
raccourcissant. Trois, sur l'ensemble des dates, le crible du jour retire 30 716 lignes du
panneau, qui passe de 178 005 à 147 289.

**La couverture des vingt et une variables**, mesurée dans
`results/tables/variable_coverage.csv`, va de 35,8 à 100 pour cent. Les six moins
renseignées sont la croissance du flux de trésorerie (0,358) et la cote O d'Ohlson (0,362).
Puis la croissance des régularisations (0,368), le taux de distribution net (0,435), la
croissance de la marge brute (0,460) et celle du profit brut sur actif (0,468). Une banque
ne déclare ni coût des ventes ni profit brut, ce qui explique la moitié des trous. Le nombre
moyen de variables réellement employées par composante et par date vit dans
`results/tables/component_variable_counts.csv`.

**La taille des quatre coins du tri** est publiée dans `results/tables/leg_counts.csv`. Elle
part de 77 sociétés par coin en juin 2015 et finit à 120 ou 121 en mai 2026, la croissance
venant des sociétés qui accumulent les cinq exercices exigés par les variables de
croissance.

## La méthodologie originale

L'article trie, il n'estime rien. Chaque mois, chaque variable devient un rang transversal
par pays, les rangs se standardisent, se somment par composante, et les quatre composantes
se somment en un score. Les portefeuilles se forment à l'intersection de deux paquets de
taille et de trois paquets de qualité, avec des coupures au trentième et au soixante-dixième
centile, et se pondèrent par la valeur. Les portefeuilles mondiaux s'obtiennent en
pondérant chaque pays par sa capitalisation retardée.

Deux tests accompagnent le facteur. Le rendement se régresse sur un, trois puis quatre
facteurs, et l'ordonnée à l'origine se lit comme un alpha. Le PRIX de la qualité se mesure
par régression transversale à la Fama-MacBeth du rapport valeur de marché sur valeur
comptable contre le score.

L'article ne corrige rien pour les tests multiples, ni sur les vingt-quatre pays, ni sur les
quatre composantes.

## Notre implémentation

La construction vit dans `src/quantlab/strategies/quality_minus_junk.py`, et `run.py`
n'orchestre. Le module sépare cinq objets que la formule mélange. La lecture des archives
de la SEC et le recollement des balises en postes comptables. Puis les vingt et une
variables, le passage par les rangs, et le tri conditionnel.

**La date de dépôt gouverne l'accès, et rien d'autre.** Chaque exercice entre dans un
`PITFrame` avec sa fin de période et sa date de dépôt. À chaque fin de mois, l'étude appelle
`as_of` et n'obtient que ce qui était public ce jour-là, puis `assert_no_lookahead` vérifie
la propriété sur le panneau entier. Le test canonique du module refuse au 31 décembre 2014
un rapport déposé le 31 mars 2015, et un contrôle inverse prouve que le test attrape bien
une fuite fabriquée.

**Le décalage d'exécution se fait en un seul endroit.** Le score porte la date de formation
et le constructeur du facteur reçoit un tableau de rendements DÉJÀ avancé d'un mois. Le
constructeur ne décale rien lui-même, ce qui rend le décalage visible d'un seul coup d'œil,
et un test le vérifie en perturbant les rendements postérieurs à une date.

**Le bêta suit Frazzini et Pedersen.** L'écart type se mesure sur un an de rendements
quotidiens, la corrélation sur cinq ans de rendements cumulés sur trois jours, et le produit
est rétréci à 0,6 vers un. Un test le vérifie sur un titre qui vaut exactement deux fois le
marché, dont le bêta rétréci doit valoir 1,6.

**Le crible d'univers s'applique avant le passage par les rangs.** Il se recalcule chaque
fin de juin sur la seule donnée déposée à cette date, et il gouverne les douze mois
suivants. L'appliquer plus tard laisserait la cote d'une société dépendre de sociétés hors
univers ; ne pas l'appliquer ferait entrer dès 2015 celles qui n'ont grossi qu'après. Un
test du module compare les deux lectures et exige que la seconde soit refusée.

**La rotation se compte en SOMME ENTIÈRE.** Le facteur achète d'un côté et vend de
l'autre, et chaque côté paie son écart. La demi-somme, qui est le défaut du module de
rotation, ne facturerait qu'un côté et diviserait le coût par deux. La convention retenue
est celle des études 003, 005, 006 et 008.

**Deux filtres de qualité de données ont été ajoutés en cours de route**, et `notes.md` dit
pourquoi. `usable_prices` retire les prix nuls ou négatifs, soit **3 511 cases**.
`drop_return_outliers` retire les rendements hors des bornes déclarées, soit **18
rendements mensuels et 20 rendements quotidiens**, dont un de **309,9**, c'est-à-dire
30 990 pour cent. Source : `results/tables/return_quality.csv`.

Aucun paramètre ne vit dans le code. Le fichier `config.yaml` porte les 5 parts de qualité,
les 2 coupures de taille, les 2 pondérations et les 3 délais d'exécution. Il porte aussi les
4 taux de coût, les 7 multiples de coût, les 24 pays et les 9 seuils du verdict.

## Nos écarts avec l'article

**Notre construction ne couvre que onze années.** Les jeux de la SEC commencent au deuxième
trimestre 2009 et six variables demandent cinq exercices d'historique, donc la première
formation possible tombe en juin 2015. L'article couvre juin 1956 à décembre 2012.

**Notre univers survit par construction.** Il vient de la carte des symboles d'aujourd'hui,
donc 38,6 pour cent des sociétés candidates ont disparu. L'article emploie CRSP, radiations
comprises, avec la règle de moins trente pour cent de Shumway sur les disparitions liées à
la performance. Cette règle n'est pas reproductible ici, faute de date et de motif de
radiation.

**Notre univers est filtré par la taille, l'article ne filtre rien.** Le crible garde à
chaque fin de juin les 1 200 plus grosses sociétés par actif et les 1 200 plus grosses par
chiffre d'affaires, connaissables ce jour-là. La conséquence est mesurable et elle est le
cœur du résultat : notre facteur charge -0,099 sur la taille (t -0,69) là où le facteur
publié charge -0,577 (t -6,72) sur les MÊMES mois. Source :
`results/tables/our_factor_regressions.csv`.

**La composante se calcule sur la moyenne, non sur la somme.** Une somme portant une valeur
manquante vaut manquant, ce qui sortirait toutes les banques de l'univers. La moyenne des
cotes renseignées, avec un plancher de variables déclaré, les garde. L'écart est nul sur une
ligne complète, ce qu'un test vérifie par identité algébrique.

**L'indice des prix de la cote O vaut un.** Il entre par un logarithme commun à toutes les
sociétés d'une même date, donc il ne déplace aucun rang transversal. Un test le prouve
plutôt que de l'affirmer.

**Le quatrième trimestre est sous-représenté dans la volatilité des bénéfices.** La plupart
des déposants ne balisent pas leur quatrième trimestre, qui n'apparaît que dans le total
annuel.

**Nous corrigeons pour les tests multiples**, ce que l'article ne fait pas, et le résultat
change les conclusions par pays.

**L'échantillon mondial n'est pas reconstruit.** Compustat Global exige un abonnement, donc
la jambe B ne couvre que les États-Unis.

## Les résultats

### Le facteur publié se réplique, et sa prime a fondu après la publication

C'est le premier résultat, et il tient dans un tableau. Source :
`results/tables/published_factor.csv`.

| Fenêtre | Mois | Rendement mensuel | t | Sharpe annualisé | Pire repli |
|---|---:|---:|---:|---:|---:|
| Complète, 1957-07 à 2026-06 | 828 | 0,312 % | 3,46 | 0,473 | -36,0 % |
| Fenêtre de l'article, 1957-07 à 2012-12 | 666 | 0,347 % | 3,66 | 0,559 | -28,2 % |
| Après publication, 2013-01 à 2026-06 | 162 | 0,168 % | 0,72 | 0,209 | -36,0 % |

**Comment lire ce tableau, en trois constats.** Un, la fenêtre de l'article rend 0,347 pour
cent par mois contre 0,40 publié, soit 13,2 pour cent d'écart relatif, et un ratio de Sharpe
de 0,559 contre 0,58, soit 3,5 pour cent. Les deux tiennent dans la tolérance de 25 pour
cent écrite d'avance. Deux, le rendement mensuel tombe de moitié après la publication et sa
statistique t passe de 3,66 à 0,72, donc l'échantillon d'après ne rejette plus zéro. Trois,
le pire repli du facteur arrive APRÈS la publication, pas avant.

**Notre fenêtre ne commence pas où celle de l'article commence.** Le fichier d'AQR part de
juillet 1957, l'article de juin 1956. Les treize mois manquants ne sont pas reconstructibles
et l'écart est déclaré dans le contrôle de réplication.

Deux figures montrent la même série autrement, `results/figures/published_equity.png` et
`results/figures/underwater_published.png`. **Mode d'emploi.** La première porte une échelle
logarithmique en ordonnée, donc une pente constante vaut un taux de croissance constant. La
courbe du facteur s'y compare à celle du marché américain, sur la même base de un dollar. La
seconde porte le repli cumulé, c'est-à-dire l'écart au plus haut atteint. Elle vaut zéro au
sommet, et le creux le plus profond du facteur se lit à droite, après 2020.

Une troisième figure, `results/figures/return_histogram.png`, donne la distribution
mensuelle avec une loi normale de même moyenne et de même écart type par-dessus. **Mode
d'emploi.** Les barres sont les rendements observés et la courbe est la normale de
référence. L'écart entre les deux, au centre et dans les queues, dit ce que le ratio de
Sharpe seul ne dit pas.

### La baisse d'après publication n'est pas significative

Source : `results/tables/sharpe_difference.csv`. Les deux fenêtres ne se recouvrent pas,
donc les deux estimateurs sont indépendants et la variance de leur écart est la somme des
variances.

| Grandeur | Valeur |
|---|---:|
| Sharpe avant, 1957-07 à 2012-12 | 0,559 |
| Sharpe après, 2013-01 à 2026-06 | 0,209 |
| Écart | 0,350 |
| Erreur type de l'écart | 0,328 |
| Statistique z | 1,068 |
| Valeur p bilatérale | 0,286 |

**Le constat.** L'écart de 0,35 point de ratio de Sharpe vaut 1,07 erreur type, donc il ne
se distingue pas du bruit. Treize ans et demi ne suffisent pas à trancher une baisse de
cette taille, et c'est un fait sur la PUISSANCE du test, pas sur l'absence d'effet.

### Les régressions retrouvent le signe et l'ordre de grandeur des chargements

Source : `results/tables/published_regressions.csv`.

| Modèle | Alpha mensuel | t | Marché | Taille | Valeur | Momentum | R² ajusté |
|---|---:|---:|---:|---:|---:|---:|---:|
| Un facteur, fenêtre de l'article | 0,469 % | 5,67 | -0,255 | | | | 0,278 |
| Trois facteurs, fenêtre de l'article | 0,601 % | 8,77 | -0,244 | -0,307 | -0,253 | | 0,492 |
| Quatre facteurs, fenêtre de l'article | 0,522 % | 7,52 | -0,230 | -0,300 | -0,230 | 0,087 | 0,516 |
| Quatre facteurs, après publication | 0,294 % | 1,85 | -0,196 | -0,512 | 0,124 | 0,028 | 0,415 |

**Comment lire ce tableau, en quatre constats.** Un, l'alpha à quatre facteurs vaut 0,522
pour cent par mois contre 0,66 publié, soit 21,0 pour cent d'écart, dans la tolérance. Deux,
les chargements sur le marché et sur la taille se retrouvent au dixième près, -0,230 contre
-0,25 et -0,300 contre -0,38 : le facteur est bien long des grandes sociétés à bêta faible
et court des petites à bêta élevé. Trois, le chargement sur la valeur, -0,230 contre -0,12
publié, est celui qui s'écarte le plus, et il n'entre pas dans les contrôles de réplication
pour cette raison. Quatre, après la publication, l'alpha tombe à 0,294 pour cent avec un t
de 1,85, et le chargement sur la taille double.

### Notre construction ne reproduit pas le facteur publié, et trois mesures disent pourquoi

C'est le résultat central de la jambe B. Sources :
`results/tables/construction_vs_published.csv` et
`results/tables/regression_on_published.csv`.

| Série, fenêtre commune 2015-06 à 2026-05 | Mois | Rendement mensuel | Sharpe | Corrélation avec le publié |
|---|---:|---:|---:|---:|
| Notre construction | 132 | 0,130 % | 0,152 | 0,098 |
| QMJ publié | 132 | 0,162 % | 0,187 | 1,000 |

La régression de l'une sur l'autre rend un bêta de 0,098 (t 1,16), un alpha de 0,115 pour
cent par mois (t 0,42) et un R² ajusté de 0,002.

**Comment lire ces deux tableaux, en trois constats.** Un, les deux séries ont presque le
même NIVEAU, 0,130 contre 0,162 pour cent par mois, et presque la même volatilité, 2,97
contre 2,99 pour cent. Deux, elles n'ont presque rien en commun mois par mois : le R² de
0,002 dit que notre série n'explique pas un quart de pour cent de la variance de la
sienne. Trois, le contrôle de réplication échoue donc, 0,098 contre un seuil de 0,50 écrit
d'avance.

La figure `results/figures/construction_vs_published.png` superpose les deux richesses
cumulées sur les mois communs. **Mode d'emploi.** Les deux courbes partent de un dollar à
la même date et l'échelle est linéaire, la fenêtre étant courte. Elles finissent presque au
même niveau, et c'est le CHEMIN entre les deux qui diffère : leurs écarts mensuels ne se
compensent pas, ce que la corrélation de 0,098 chiffre.

La figure `results/figures/correlation_heatmap.png` porte la matrice complète. **Mode
d'emploi.** Chaque case est une corrélation mensuelle, le bleu marquant le négatif et le
rouge le positif. La ligne du facteur publié montre son lien fort au marché, et celle de
notre construction montre l'absence de lien à quoi que ce soit.

**La première raison, mesurée : la taille.** Source :
`results/tables/our_factor_regressions.csv`.

| Modèle à quatre facteurs, 132 mois | Alpha mensuel | Marché | Taille | Valeur | R² ajusté |
|---|---:|---:|---:|---:|---:|
| Notre construction | 0,167 % | -0,038 | -0,099 | -0,097 | -0,010 |
| QMJ publié, mêmes mois | 0,245 % | -0,207 | -0,577 | 0,141 | 0,462 |

Le facteur publié est, sur ces cent trente-deux mois, à 46 pour cent une combinaison de
facteurs connus, et le chargement qui domine est celui de la taille, -0,577 avec un t de
-6,72. Notre construction, elle, ne charge rien : son R² ajusté est négatif et son
chargement sur la taille vaut -0,099 avec un t de -0,69. Deux séries dont l'une est à
moitié un pari sur la taille et l'autre pas ne peuvent pas se corréler fortement, quel que
soit le score qui les produit. Notre univers, borné aux grandes sociétés, ne porte pas la
dispersion de taille que le facteur publié exploite.

**La deuxième raison, mesurée : nos composantes ne se séparent pas.** Source :
`results/tables/component_vs_proxy.csv`. Notre rentabilité corrèle à 0,924 avec notre
facteur, notre sûreté à 0,766, notre croissance à 0,561 et notre distribution à 0,478.
Entre elles, rentabilité et sûreté corrèlent à 0,617. L'article annonce une corrélation
moyenne deux à deux de 0,40 entre composantes ; les nôtres sont plus élevées, donc les
quatre composantes mesurent en partie la même chose.

**La troisième raison, mesurée : nos composantes sont presque orthogonales aux jambes de
Kenneth French qui portent la même idée.** Toujours dans `component_vs_proxy.csv`, notre
rentabilité corrèle à 0,149 avec la jambe de rentabilité de Kenneth French, alors que cette
même jambe corrèle à 0,671 avec le QMJ publié. Le score que nous calculons n'ordonne donc
pas les sociétés comme un tri de rentabilité ordinaire les ordonne.

### Et pourtant le score trie bien les rendements

C'est la contradiction de l'étude, et elle est mesurée. Source :
`results/tables/quality_deciles.csv`, dix portefeuilles pondérés par la valeur, formés sur
notre score, détenus le mois suivant.

| Portefeuille | Rendement mensuel | Écart type mensuel | Sharpe annualisé |
|---|---:|---:|---:|
| Q1, la camelote | 0,477 % | 8,923 % | 0,185 |
| Q5 | 1,289 % | 5,174 % | 0,863 |
| Q10, la qualité | 1,416 % | 4,495 % | 1,091 |
| Écart Q10 moins Q1 | 0,938 % | 7,564 % | 0,430 |

**Comment lire ce tableau, en trois constats.** Un, l'écart entre le dernier et le premier
décile vaut 0,938 pour cent par mois, là où l'article publie 47 à 68 points de base : notre
score sépare donc PLUS que le sien, sur une fenêtre beaucoup plus courte. Deux, la
volatilité décroît de façon presque monotone du premier au dernier décile, de 8,92 à 4,50
pour cent, ce qui est la signature attendue d'un score de qualité. Trois, le premier décile
concentre le risque : sa volatilité est deux fois celle du dernier, ce qui rappelle que
l'écart de décile n'est pas un portefeuille détenable sans levier ni contrainte.

La figure `results/figures/quality_deciles.png` dessine ces onze barres. **Mode d'emploi.**
Une barre par décile, de la camelote à gauche à la qualité à droite, plus une barre d'écart
détachée. Une suite croissante est ce qu'un signal utile produit, et une suite en dents de
scie signalerait un tri sans contenu.

La conclusion qui s'impose est précise. Notre pipeline n'est pas cassé, puisqu'il ordonne
les rendements. Ce qu'il ne fait pas, c'est reproduire l'objet qu'AQR publie, et la raison
principale est la neutralisation de la taille imposée par notre univers.

### Les quatre composantes ne se classent pas comme dans l'article

Source : `results/tables/components.csv`, chaque composante triée seule, même tri
conditionnel, mêmes cent trente-deux mois.

| Composante | Rendement mensuel | t | Sharpe | Corrélation avec le publié | Alpha publié à quatre facteurs |
|---|---:|---:|---:|---:|---:|
| Croissance | 0,386 % | 1,58 | 0,557 | -0,017 | 0,38 % |
| Distribution | 0,259 % | 1,89 | 0,613 | 0,131 | 0,21 % |
| Rentabilité | 0,108 % | 0,44 | 0,145 | 0,099 | 0,53 % |
| Sûreté | -0,242 % | -0,92 | -0,255 | 0,037 | 0,57 % |

**Comment lire ce tableau, en trois constats.** Un, l'ordre est INVERSÉ par rapport à
l'article : la croissance et la distribution mènent, la rentabilité et la sûreté suivent,
alors que l'article donne la sûreté et la rentabilité en tête. Deux, aucune des quatre ne
dépasse une statistique t de 1,9, donc aucune ne rejette zéro sur onze années. Trois, la
sûreté perd 0,242 pour cent par mois, ce qui est cohérent avec la décennie 2015-2026, où le
pari contre le bêta a mal payé, mais ne dit rien de la composante elle-même.

### Le repli à trois composantes, lui, suit le facteur publié

Source : `results/tables/three_component_proxy.csv`, 756 mois, 1963-07 à 2026-06.

| Jambe | Rendement mensuel | t | Sharpe | Corrélation avec le publié |
|---|---:|---:|---:|---:|
| Rentabilité, HI 30 moins LO 30 | 0,221 % | 2,13 | 0,294 | 0,721 |
| Croissance, LO 30 moins HI 30 sur l'investissement | 0,182 % | 1,76 | 0,237 | 0,164 |
| Sûreté, LO 20 moins HI 20 sur le bêta | -0,300 % | -1,34 | -0,178 | 0,635 |
| Moyenne des trois | 0,034 % | 0,30 | 0,040 | 0,684 |

**Comment lire ce tableau, en trois constats.** Un, cette approximation grossière, faite de
RENDEMENTS de portefeuilles déjà formés et non de cotes de sociétés, corrèle à 0,684 avec le
facteur publié, soit sept fois plus que notre construction complète. Deux, elle ne rapporte
pourtant presque rien, 0,034 pour cent par mois sur soixante-trois ans, parce que la jambe
de sûreté perd autant que les deux autres gagnent. Trois, la corrélation élevée vient de
l'univers : les portefeuilles de Kenneth French sont bâtis sur tout CRSP, avec des coupures
du NYSE, donc ils portent la dispersion de taille que notre univers n'a pas.

Ce tableau est le contre-poids du précédent. Il montre que la faible corrélation de notre
construction ne vient pas de l'idée de qualité, qui se retrouve, mais de l'univers sur
lequel nous la mesurons.

### Le facteur publié est positif dans les vingt-quatre pays, mais pas après correction

Source : `results/tables/countries.csv` et `results/tables/multiple_testing.csv`.

Sur l'échantillon complet, **les vingt-quatre pays ont tous un ratio de Sharpe positif**, la
Finlande étant la plus faible à 0,009 et la Suède la plus forte à 0,775. Aucun n'est
négatif, alors que l'article annonce la Nouvelle-Zélande faiblement négative. Après la
publication, huit pays gardent une statistique t supérieure à deux, mais **la correction de
Holm sur les vingt-quatre tests n'en laisse que deux**, la Suède et la Norvège.

**Le constat.** Un facteur positif dans les vingt-quatre pays est une preuve solide dans
l'échantillon d'origine et une preuve faible après, parce que vingt-quatre tests donnent
presque toujours deux ou trois succès par hasard.

## La robustesse

### Ce que l'univers non connaissable ajoutait

Source : `results/tables/universe_screen_variant.csv`. La série publiée applique à chaque
date le crible de taille de cette date. La variante applique la RÉUNION des douze cribles
annuels, donc un univers que personne ne pouvait dresser en 2015.

| Univers, 132 mois | Rendement mensuel | t | Sharpe | Pire repli |
|---|---:|---:|---:|---:|
| Crible du jour, la série publiée | 0,130 % | 0,46 | 0,152 | -25,1 % |
| Réunion des cribles, non connaissable | 0,140 % | 0,48 | 0,161 | -24,6 % |

**Comment lire ce tableau, en trois constats.** Un, l'information future vaut 0,010 point
de rendement mensuel et 0,009 point de ratio de Sharpe, soit 7,5 pour cent du rendement de
la série retenue. Deux, le signe est celui qu'on attend : une société admise par un
crible postérieur est une société qui a grossi, donc une société dont la composante de
croissance devait payer. Trois, l'écart est petit devant l'erreur type du rendement lui-même, dont la
statistique t vaut 0,46, donc il ne renverse aucune conclusion. Il est corrigé quand même,
parce qu'un rendement qui dépend d'une donnée future n'est pas un rendement.

### Le balayage des réglages

Source : `results/tables/parameter_sweep.csv`, vingt cases, chacune comptée comme un essai.

| Part de qualité | Coupure de taille | Pondération | Rendement mensuel | Sharpe | Corrélation |
|---|---|---|---:|---:|---:|
| 0,10 | 0,50 | valeur | 0,515 % | 0,362 | 0,123 |
| 0,20 | 0,80 | valeur | 0,386 % | 0,385 | 0,065 |
| 0,30 | 0,50 | valeur | 0,130 % | 0,152 | 0,098 |
| 0,45 | 0,80 | valeur | 0,246 % | 0,431 | 0,070 |
| 0,30 | 0,50 | égale | -0,171 % | -0,211 | 0,089 |
| 0,10 | 0,80 | quelconque | aucune date | 0,000 | non défini |

**Comment lire ce tableau, en quatre constats.** Un, la grille compte **dix cases pondérées
par la valeur et dix à pondération égale**, dont une paire sans résultat ; **les neuf cases
calculées à pondération par la valeur sont toutes positives et les neuf à pondération égale
toutes négatives**. Le rendement vient donc des grandes sociétés, et les petites de la
jambe longue ont perdu contre les petites de la jambe courte sur cette décennie. Deux, la
part de qualité la plus étroite paie le mieux en RENDEMENT, 0,515 pour cent par mois à dix
pour cent contre 0,130 à trente. Le meilleur ratio de Sharpe, 0,431, revient pourtant à la
part la plus large sur la coupure de taille haute. Trois, la corrélation avec le facteur
publié ne dépasse jamais 0,123, quelle que soit la case, donc aucun réglage ne sauve la
réplication. Quatre, **deux cases n'ont produit aucune date** : couper la taille au
quatre-vingtième centile puis prendre les dix pour cent extrêmes laisse moins de vingt
sociétés par coin. Ces deux essais RATÉS entrent quand même dans le compte, avec un ratio
de Sharpe posé à zéro.

La figure `results/figures/parameter_heatmap.png` porte les dix cases pondérées par la
valeur. **Mode d'emploi.** Les lignes sont les parts de qualité et les colonnes les coupures
de taille, la couleur portant le ratio de Sharpe. Un signal robuste montre un PLATEAU de
cases voisines et de couleurs proches, alors qu'une case isolée bien colorée est le signe
d'un réglage choisi après coup.

La figure `results/figures/rolling_sharpe.png` porte le ratio de Sharpe glissant sur dix ans
du facteur publié. **Mode d'emploi.** Chaque point résume les cent vingt mois qui le
précèdent, donc la courbe est lisse par construction et ses variations lentes se lisent
comme des régimes, pas comme des mois.

La figure `results/figures/subperiod_bars.png` reprend le tableau des sous-périodes. **Mode
d'emploi.** Une barre par tranche et une moustache d'erreur type à 95 pour cent. Une
moustache qui traverse zéro dit que la tranche ne rejette pas l'absence de prime, ce qui est
le cas de cinq des sept.

### Le délai d'exécution

Source : `results/tables/execution_delay.csv`.

| Délai | Mois | Rendement mensuel | Sharpe |
|---|---:|---:|---:|
| Un mois | 132 | 0,130 % | 0,152 |
| Deux mois | 131 | 0,131 % | 0,157 |
| Trois mois | 130 | 0,045 % | 0,054 |

**Le constat.** Le rendement ne bouge pas quand on attend un mois de plus, 0,131 contre
0,130 pour cent, puis il perd les deux tiers au troisième mois. Le signal n'est donc pas
porté par le seul mois qui suit la formation, ce qui convient à un score bâti sur des
comptes annuels. Un signal qui s'éteindrait au premier mois serait suspect, celui-ci
s'éteint au troisième.

### Les sous-périodes

Source : `results/tables/subperiods.csv`, sept tranches, coupures écrites d'avance dans
`config.yaml`. **Les sept ratios de Sharpe sont positifs**, de 0,012 sur 2020-2026 à 1,685
sur 1980-1990. Cinq des sept portent une erreur type qui couvre zéro, donc la part de
sous-périodes positives de 1,000 dit la constance du SIGNE, pas la force de la preuve.

### La validation croisée combinatoire et la probabilité de surapprentissage

Sources : `results/tables/cpcv_distribution.csv` et `results/tables/pbo.csv`.

La validation croisée combinatoire purgée juge le PROCESSUS de sélection : sur chaque bloc
d'apprentissage, la meilleure des dix-huit configurations est retenue, et son rendement du
bloc de test suivant est collecté. Sur sept chemins, le ratio de Sharpe moyen vaut 0,301, le
minimum 0,180 et **aucun chemin n'est négatif**. La probabilité de surapprentissage vaut
**0,000** sur dix-huit configurations et cent trente-deux mois.

**Le constat, et sa réserve.** Une probabilité de surapprentissage nulle veut dire que la
configuration choisie sur la première moitié reste la meilleure sur la seconde. Elle ne dit
rien de la qualité du signal. Ici, la meilleure configuration est toujours pondérée par la
valeur et les neuf configurations calculées à pondération égale perdent sur toutes les
partitions. Le classement est donc stable pour une raison qui n'a rien à voir avec le
score.

## Les coûts

Aucun coût n'est publié par l'article, qui ne mesure ni rotation ni frais. Source :
`results/tables/costs.csv` et `results/tables/cost_multiples.csv`.

La **rotation annualisée** de notre construction vaut **4,928**, comptée en somme entière
sur une exposition brute de deux. Autrement dit, 20,5 pour cent du livre change de mains
chaque mois. Le **coût qui annule le rendement brut** vaut **25,9 points de base**, mesuré
par le rapport du rendement moyen à la rotation moyenne.

Les quatre lignes ci-dessous portent sur les 131 mois où la rotation est définie, le
premier mois n'ayant pas de portefeuille antérieur à comparer.

| Coût unitaire | Rendement mensuel net | Sharpe net |
|---|---:|---:|
| 0 point de base | 0,106 % | 0,124 |
| 5 points de base | 0,086 % | 0,100 |
| 10 points de base, le cas de référence | 0,065 % | 0,076 |
| 20 points de base | 0,024 % | 0,028 |

Au multiple de coût, la stratégie survit jusqu'à deux fois l'hypothèse de référence, avec
un ratio de Sharpe de 0,028, et meurt à trois fois, à -0,020. Le point de rupture interpolé
vaut 2,590, ce que `decide_verdict` compare au minimum de 2,00.

La figure `results/figures/cost_sensitivity.png` porte la courbe complète. **Mode d'emploi.**
L'axe horizontal est le multiple appliqué au coût de référence et l'axe vertical le ratio de
Sharpe net. La ligne horizontale à zéro marque le seuil de survie, et l'abscisse où la
courbe la traverse est le point de rupture publié ci-dessus.

**Comment lire ces deux tableaux, en trois constats.** Un, la rotation est modérée pour un
signal fondamental annuel, et vingt-six points de base de coût de rentabilité laissent une
marge face aux dix points de base retenus. Deux, cette marge est mince : le seuil de survie
tombe entre deux et trois fois l'hypothèse de référence, contre un minimum exigé de deux.
Trois, la marge porte de toute façon un rendement déjà faible, et passer de 0,124 à 0,076
de ratio de Sharpe ne change rien à un chiffre qui ne rejette pas zéro.

## Le hors échantillon

Le vrai hors échantillon de cette étude n'est pas notre construction, il est **le facteur
publié après sa publication**. L'article s'arrête en décembre 2012, donc aucun de ses choix
n'a pu s'ajuster à ce qui suit.

Source : `results/metrics.json` et `results/tables/deflated_sharpe.csv`.

| Grandeur, 2013-01 à 2026-06, 162 mois | Valeur |
|---|---:|
| Ratio de Sharpe brut | 0,209 |
| Ratio de Sharpe net de dix points de base sur notre rotation | 0,158 |
| Statistique t | 0,547 |
| Nombre d'essais comptés | 67 |
| Variance des ratios de Sharpe des essais | 0,062 |
| Ratio de Sharpe attendu du maximum sous l'hypothèse nulle | 0,596 |
| **Ratio de Sharpe dégonflé** | **0,000** |
| Statistique t exigée par Bonferroni sur 67 tests | 3,372 |
| Statistique t après rabais de Holm | 0,000 |

**Comment lire ce tableau, en quatre constats.** Un, le ratio de Sharpe net de 0,158 est
inférieur au maximum de 0,596 qu'on attendrait du hasard après soixante-sept essais, donc
le ratio dégonflé vaut zéro. Deux, le coût employé pour passer du brut au net est MODÉLISÉ.
La rotation d'AQR n'est pas publiée, donc c'est la nôtre qui sert, et elle est mesurée sur
2015-2026, une fenêtre incluse dans celle qu'elle sert à déflater. Trois, ce chiffre se lit
donc comme un ordre de grandeur, pas comme une mesure, et il joue CONTRE la série publiée.
Quatre, le rééchantillonnage par blocs de douze mois sur 2 000 tirages, dans
`results/tables/bootstrap.csv`, rend un rendement annualisé observé de 1,53 pour cent. Son
intervalle va de -3,42 à 6,85 pour cent, avec 70,9 pour cent de tirages positifs, donc la
série d'après publication est compatible avec zéro comme avec une prime réduite.

**Le compte des essais** est publié dans `results/tables/trials.csv`. Il se répartit en dix
familles. Vingt-quatre pays, 20 cases de balayage, 6 multiples de coût et 4 taux de coût en
font 54. Les 13 autres sont 4 composantes, 3 délais, 3 jambes de repli, 1 construction de
référence, 1 variante d'univers et 1 tri par décile. Les deux cases de balayage qui n'ont produit aucune date y figurent,
avec un ratio de Sharpe posé à zéro. Le compte est volontairement large : la case de
référence y entre trois fois, comme construction, comme case du balayage et comme délai
d'un mois. Compter large rend le ratio de Sharpe dégonflé plus sévère, jamais plus
flatteur.

## Les limites

**L'article publié n'a pas été lu, et cela peut invalider la définition du score.**
Novy-Marx et Medhat décrivent trois composantes, la version de travail en donne quatre. Si
la version publiée a retiré la distribution, notre score porte une composante de trop, et
c'est un écart de définition, pas de mise en œuvre.

**Onze années ne suffisent à rien trancher.** Le facteur publié lui-même n'a qu'un ratio de
Sharpe de 0,187 sur ces mois, avec une statistique t de 0,59. Aucune conclusion sur notre
construction ne peut donc être plus forte que celle qu'on tirerait de la sienne.

**L'univers survit, et le crible de taille l'aggrave.** Les deux effets vont dans le même
sens : ils retirent les petites sociétés en difficulté, qui sont la matière première de la
jambe courte.

**Le crible du jour a été mesuré contre la réunion des cribles.** Retenir la réunion, donc
laisser entrer dès 2015 les sociétés qui n'ont grossi qu'après, porte le rendement mensuel
de 0,130 à 0,140 pour cent et le ratio de Sharpe de 0,152 à 0,161. Le chiffre publié est
celui du crible du jour, et la variante est publiée dans
`results/tables/universe_screen_variant.csv`.

**Le point-in-time est natif mais incomplet.** La date de dépôt est réelle, ce qui écarte le
biais d'anticipation ordinaire. En revanche, la valeur retenue à une date de décision est la
DERNIÈRE version connue ce jour-là, donc une correction publiée entre deux formations entre
dans le score, comme elle serait entrée dans la réalité.

**Aucun rendement de radiation n'est appliqué.** Yahoo ne publie ni date ni motif de
radiation, donc la règle de moins trente pour cent de Shumway n'est pas reproductible.

**Deux bornes de qualité de données ont été posées après avoir vu les données.** Elles sont
déclarées dans `notes.md`, avec les trois séries de prix qui les ont motivées, et les
comptes retirés sont publiés.

**La rotation employée pour déflater la série publiée est la nôtre.** Elle se mesure sur
2015-2026, donc sur une fenêtre incluse dans le hors échantillon qu'elle sert à corriger.
Le sens de l'erreur est connu, puisque le coût réduit la performance de la série publiée.

**Le prix de la qualité n'est pas mesuré.** La régression transversale à la Fama-MacBeth du
rapport valeur de marché sur valeur comptable contre le score, qui est la moitié de
l'article, n'a pas été menée. C'est un report assumé, et la fenêtre de onze années le rendait
peu concluant.

## Le verdict

Le verdict est déduit par `quantlab.reporting.study.decide_verdict` depuis les seuils écrits
dans `config.yaml` avant le premier résultat. Il vaut **`EXPERIMENTAL`**. Les six contrôles
chiffrés vivent dans `results/tables/replication_checks.csv`, et les vingt-cinq métriques
avec leur échantillon et leur base de coût dans `results/tables/metrics.csv`.

| Critère | Seuil | Mesuré | Résultat |
|---|---|---:|---|
| Hypothèse économique, signe attendu | signe positif | positif | réussi |
| Rendement excédentaire mensuel, États-Unis | écart relatif ≤ 0,25 | 0,132 | réussi |
| Ratio de Sharpe annualisé, États-Unis | écart relatif ≤ 0,25 | 0,035 | réussi |
| Alpha à quatre facteurs, mensuel | écart relatif ≤ 0,25 | 0,210 | réussi |
| Chargement sur la taille | écart relatif ≤ 0,25 | 0,211 | réussi |
| Chargement sur le marché | écart relatif ≤ 0,25 | 0,081 | réussi |
| **Corrélation de notre construction avec le publié** | **≥ 0,50** | **0,098** | **échoué** |
| Ratio de Sharpe hors échantillon | ≥ 0,30 | 0,158 | échoué |
| Statistique t après correction | ≥ 3,00 | 0,000 | échoué |
| Ratio de Sharpe dégonflé | ≥ 0,95 | 0,000 | échoué |
| Probabilité de surapprentissage | ≤ 0,50 | 0,000 | réussi |
| Part de sous-périodes positives | ≥ 0,60 | 1,000 | réussi |
| Multiple de coûts survécu | ≥ 2,00 | 2,590 | réussi |
| Corrélation avec le portefeuille existant | ≤ 0,60 | 0,493 | réussi |

**Comment lire ce tableau, en trois constats.** Un, les cinq contrôles qui visent la SÉRIE
publiée passent tous, donc le facteur d'AQR est bien celui que l'article décrit. Deux, le
contrôle qui vise notre SCORE échoue largement, 0,098 contre 0,50, et c'est lui qui empêche
le verdict de monter. Trois, les trois critères statistiques hors échantillon échouent
ensemble pour une seule raison : soixante-sept essais comptés contre un ratio de Sharpe de
0,158 sur cent soixante-deux mois ne laissent aucune place au hasard favorable.

**Ce que le verdict ne dit pas.** Il ne dit pas que la qualité ne paie pas. Il dit que la
série publiée ne se distingue plus du bruit après sa publication, et que notre reconstruction
du score depuis des données publiques ne produit pas le même objet. Les dix portefeuilles de
qualité, eux, restent ordonnés, avec un écart de 0,938 pour cent par mois entre le dernier
et le premier décile.

La prochaine décision est nommée : obtenir le texte publié pour trancher entre trois et
quatre composantes, puis refaire la jambe B sur un univers qui porte les radiations.

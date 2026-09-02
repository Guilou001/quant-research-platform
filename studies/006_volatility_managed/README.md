# Portefeuilles gérés en volatilité

## La question de recherche

Gérer un facteur par sa volatilité passée crée-t-il de l'alpha, ou seulement l'illusion qu'en donne
une constante de calibrage choisie après coup ?

**La réponse, en trois phrases.** L'alpha en échantillon est réel et se réplique presque à la
décimale : nous retrouvons 4,74 % par an pour le marché contre 4,86 publiés, sur exactement 1 065
mois comme l'article. La stratégie tenable, celle dont la constante et le bêta de couverture sont
estimés sur le seul passé, rapporte **-0,32 % par an avant frais** sur 1946-2026. Son ratio de Sharpe
hors échantillon vaut **-0,36** net de dix points de base, et le verdict déduit est donc `REJECTED`.

Ces deux phrases ne se contredisent pas, et c'est le résultat de l'étude. L'alpha de la régression
d'engendrement mesure le gain d'une combinaison à poids optimaux calculés sur tout l'échantillon.
Personne ne connaît ces poids avant la dernière date. Chaque chiffre ci-dessous vient d'un fichier de
`results/`, et le fichier est nommé.

**Une précaution sur le -0,32 %.** Ce chiffre dépend du bêta de couverture, et il passe à +0,13 de
ratio de Sharpe si l'on fige ce bêta sur tout l'échantillon. Le ratio de Sharpe hors échantillon, lui,
tient dans les deux lectures, -0,308 et -0,286 avant frais. C'est donc lui qui porte le verdict, et la
section « Le hors échantillon » chiffre l'écart.

## L'article

Moreira, A. et Muir, T. (2017), « Volatility-Managed Portfolios », *The Journal of Finance* 72(4),
1611-1644, DOI 10.1111/jofi.12513.

La version publiée n'a pas été obtenue : Wiley renvoie une erreur 403. Les chiffres cibles viennent
du **document de travail NBER 22208 d'avril 2016**, dont le tableau 1, panneau A, est recopié dans
`docs/literature/moreira_muir_2017.md`. Statut de ces chiffres : **rapportés**.

Trois publications répondent à l'article, et l'étude les prend au sérieux.

| Auteurs | Revue | Ce qu'ils opposent |
|---|---|---|
| Liu, Tang et Zhou (2019) | *Journal of Portfolio Management* 46(1) | La constante de calibrage est un regard en avant. Le pire recul cumulé atteint 68 % à 93 % une fois la constante estimée en temps réel. |
| Cederburg, O'Doherty, Wang et Yan (2020) | *Journal of Financial Economics* 138(1) | L'alpha n'est pas exploitable. La combinaison reconstruite hors échantillon rend un équivalent certain plus faible dans 72 cas sur 103. |
| Xu (2024) | *Critical Finance Review*, à paraître | Concède le diagnostic et propose une formation corrigée. |

## L'intuition économique

Le rendement de la stratégie tient à un écart de prévisibilité, et non à une friction.

La variance d'un facteur se prévoit très bien à un mois : celle du mois passé explique l'essentiel de
celle du mois suivant. Le rendement attendu, lui, se prévoit mal. L'investisseur moyenne-variance
maximise le rapport du rendement attendu à la variance, et ce rapport se dégrade donc quand la
variance monte, faute d'une hausse compensatrice de la moyenne. Réduire l'exposition après un mois
agité exploite cette dégradation.

Les auteurs le résument par une proportionnalité : l'alpha est positif si et seulement si le prix du
risque baisse quand la variance monte. C'est ce que les modèles structurels d'aversion au risque
variable prédisent à l'envers, et c'est pourquoi le résultat est intéressant.

**Ce qui ferait disparaître le rendement.** Trois extinctions, dans l'ordre de vraisemblance. La
volatilité cesse d'être moins persistante que la prime. Les coûts de rotation annulent le gain. Enfin
la constante de calibrage, qui rend le résultat lisible, cesse d'être connue au moment d'agir. Cette
troisième extinction est celle que l'étude mesure.

## La définition mathématique

Le portefeuille géré, équation (1) de l'article :

\[ f^{\sigma}_{t+1} = \frac{c}{\hat{\sigma}^2_t(f)}\, f_{t+1} \]

La variance réalisée du mois, équation (2), somme des carrés des rendements quotidiens du mois :

\[ \hat{\sigma}^2_t(f) = \sum_{d=1}^{n_t} \left( f_{t,d} - \bar{f}_t \right)^2 \]

La régression d'engendrement, équation (3), dont l'ordonnée à l'origine est lue comme un alpha :

\[ f^{\sigma}_{t+1} = \alpha + \beta f_{t+1} + \epsilon_{t+1} \]

Trois grandeurs dérivées. Le ratio d'appréciation, le rapport de l'alpha à la volatilité résiduelle,
mesure le ratio de Sharpe additionnel qu'apporte le titre géré. Le ratio de Sharpe atteignable en
combinant les deux titres vaut la racine de la somme des deux carrés. Le gain d'utilité de l'équation
(4) en est la traduction en pourcentage de l'utilité d'origine.

La constante \(c\) est choisie pour que la série gérée ait exactement le même écart type que la série
d'origine, **sur l'échantillon entier**. Elle ne change pas le ratio de Sharpe de la série gérée
seule, et les auteurs s'en tiennent à cet argument. Elle change tout le reste, à commencer par
l'alpha, le bêta, et le poids qu'un portefeuille lui donnerait.

## Les données

Huit des neuf facteurs du tableau 1 sont couverts sur données gratuites, le neuvième est déclaré non
trouvé. Source : `results/tables/factor_coverage.csv` et `results/tables/data_sources.csv`.

| Facteur | Source quotidienne et mensuelle | Couvert |
|---|---|---|
| Marché, taille, valeur | Kenneth French, trois facteurs | oui |
| Momentum | Kenneth French, facteur de Carhart | oui |
| Rentabilité RMW, investissement CMA | Kenneth French, cinq facteurs | oui |
| Rentabilité sur fonds propres ROE, investissement IA | global-q.org, facteurs q de Hou, Xue et Zhang | oui |
| Portage de change | série quotidienne non publiée | **non trouvé** |

**Comment lire ce tableau, en trois constats.** Un, les facteurs q sont en libre accès et n'exigent
ni compte ni contrepartie : les fichiers `q5_factors_daily_2025.csv` et `q5_factors_monthly_2025.csv`
répondent 200 sur `global-q.org`, mesuré le 2026-09-02, et leurs empreintes SHA-256 sont écrites dans
`results/metrics.json`. Deux, le portage de change échoue pour une raison précise et non par manque
de recherche. La page de données d'Adrien Verdelhan, lue le 2026-09-02, publie cinq
séries de change et de taux, toutes mensuelles ou annuelles, la plus longue partant de 1983. La mesure de volatilité de l'article demande les variations
**quotidiennes** de change des portefeuilles extrêmes, qui ne sont publiées nulle part. Trois, aucune
approximation ne remplace cette colonne, la consigne étant de ne pas combler une information
absente.

Le facteur « parier contre le bêta » n'est pas davantage utilisable, alors que Cederburg et
coauteurs le substituent au portage. Le classeur d'AQR ne publie que des rendements mensuels, et la
variance réalisée exige des rendements quotidiens.

Couverture des séries employées, mesurée le 2026-09-02 dans `results/tables/data_sources.csv`.

| Fichier | Première séance | Dernière séance | Séances |
|---|---|---|---:|
| Trois facteurs, quotidien | 1926-07-01 | 2026-06-30 | 26 274 |
| Cinq facteurs, quotidien | 1963-07-01 | 2026-06-30 | 15 854 |
| Momentum, quotidien | 1926-11-03 | 2026-06-30 | 26 173 |
| Facteurs q, quotidien | 1967-01-03 | 2025-12-31 | 14 848 |

**Ce que ces données ne sont pas.** Elles ne sont pas point-in-time : la bibliothèque de Kenneth
French révise ses séries à chaque millésime de CRSP. Elles sont en revanche construites sur l'univers
CRSP complet, radiations comprises, donc sans biais du survivant. Les deux déclarations vivent dans
le manifeste écrit par `FrenchProvider.manifest`.

## La méthodologie originale

L'article applique une formule sans estimer aucun paramètre, puis teste par régression.

La variance réalisée du mois \(t\) se calcule sur les rendements quotidiens du facteur. Le facteur du
mois \(t+1\) est divisé par cette variance, donc par une grandeur connue à la fin du mois \(t\). La
série obtenue est multipliée par la constante \(c\). La régression du facteur géré sur le facteur
d'origine rend l'alpha du tableau 1.

Quatre contrôles accompagnent le résultat principal. L'article ajoute les trois facteurs de Fama et
French au dénominateur de la régression. Il croise ensuite le facteur géré avec un témoin de
récession. Il retranche un coût de transaction d'un point de base, puis de dix. Il majore enfin ce
coût de quatre points quand la volatilité implicite double.

L'article ne corrige rien pour les tests multiples, ni sur les neuf facteurs, ni sur les sept
combinaisons du tableau 2, ni sur les trois sous-périodes.

## Notre implémentation

La stratégie vit dans `src/quantlab/strategies/volatility_managed.py`, et `run.py` ne fait
qu'orchestrer. Le module sépare trois objets que la formule mélange : la mesure de variance, la
constante de mise à l'échelle, et le portefeuille lui-même.

**Le décalage se fait en un seul endroit.** `managed_weights` porte le `shift(1)` qui fait que le
poids du mois \(t+1\) emploie la variance du mois \(t\). Trois tests de
`tests/unit/test_strategies_volatility_managed.py` le vérifient en perturbant une valeur et en
exigeant que rien d'antérieur ne bouge. Le contrôle a été validé par mutation : remplacer les trois
`shift(1)` par `shift(0)` fait échouer huit tests sur quarante-trois.

**Trois mesures de variance sont disponibles.** La variance réalisée, avec ou sans centrage. Le
lissage exponentiel des carrés quotidiens. Un GARCH(1,1) dont les paramètres sont réestimés tous les
120 mois sur les seules séances passées, puis figés pour filtrer la variance en avant. Ce dernier
point compte : un GARCH ajusté une fois sur tout l'échantillon connaîtrait la crise de 2008 en 1930.

**Deux constantes sont disponibles.** Celle de plein échantillon, qui est celle de l'article. Celle
en expansion, calculée sur les mois 1 à \(t-1\) et employée au mois \(t\), qui est celle qu'un
investisseur aurait pu poser.

**L'absence d'information future se prouve par troncature.** Une chaîne tenable doit rendre les mêmes
valeurs passées quand on lui retire la fin de l'échantillon. La chaîne complète a donc été rebâtie à quatre dates
d'arrêt, 1990-12, 2005-06, 2015-04 et 2020-12. L'écart maximal sur les mois communs vaut exactement
zéro, sur 533 à 893 mois selon la coupure. Deux tests portent cette
propriété, dont un contrôle inverse qui exige que la constante de plein échantillon, elle, BOUGE quand
on tronque. Le contrôle par mutation le confirme : remplacer l'écart type en expansion par l'écart
type de plein échantillon fait échouer trois tests.

**Deux séries tenables sont construites.** L'écart couvert vaut le facteur géré moins le bêta fois le
facteur d'origine, le bêta étant estimé sur une fenêtre en expansion. Son ratio de Sharpe est le
ratio d'appréciation qu'un investisseur aurait réellement obtenu. La combinaison moyenne-variance
reconstruit les poids mois après mois, comme le fait Cederburg et coauteurs.

Aucun paramètre ne vit dans le code. Le fichier `config.yaml` porte les 4 dates de départ
candidates, les 5 seuils de jours de bourse, les 4 demi-vies et les 5 plafonds de levier. Il porte
aussi les 4 taux de coût, les 4 fenêtres de constante et les 8 seuils du verdict.

## Nos écarts avec l'article

**Nous n'employons pas le portage de change**, et nous le déclarons plutôt que de lui substituer une
série de complaisance.

**Nos facteurs q sont d'un millésime plus récent.** L'article emploie les données de 2015 fournies
par Lu Zhang ; nous employons le millésime 2025 publié sur `global-q.org`. Les rendements de 1967 y
sont recalculés, donc l'écart sur ROE, +4,98 contre 5,48 publiés, mélange une différence de méthode
et une différence de millésime, et nous ne savons pas les séparer.

**Notre colonne d'erreur quadratique suit une convention déduite, non écrite.** L'article imprime
51,39 pour le marché et annonce un ratio d'appréciation de 0,33 avec un alpha de 4,86. La seule
lecture qui rend les deux nombres compatibles est que sa colonne « RMSE » vaut la volatilité
résiduelle annualisée multipliée par racine de douze. Nous rendons 50,72 contre 51,39, soit 1,3 %
d'écart, et la convention est codée dans `PAPER_RMSE_SCALE` avec son test.

**Nous ne centrons pas la variance réalisée dans le cas de référence.** L'équation (2) de l'article
retranche la moyenne du mois ; notre cas de référence somme les carrés bruts, et le centrage est
rejoué en robustesse. L'écart est négligeable, le ratio de Sharpe net passant de -0,080 à -0,075.

**Nous corrigeons pour les tests multiples**, ce que l'article ne fait pas, et le résultat change les
conclusions par facteur.

**Nous ajoutons deux objets que l'article n'a pas.** La constante estimée en expansion, qui est
l'objet de l'étude, et l'écart couvert par un bêta estimé sur le passé, qui sert de mesure hors
échantillon. L'article ne publie ni l'une ni l'autre, et il rapporte l'alpha de régression là où nous
rapportons un rendement détenable. Ces deux choix sont ceux de l'étude, et la section « Le hors
échantillon » mesure ce que le second coûte.

**Notre échantillon des facteurs q part de juin 1967**, alors que l'article n'écrit aucune date de
départ. Le mois est déduit de son compte publié de 575, et il est déclaré dans `config.yaml` sous
`global_q_start`. C'est une convention retenue par identification, non une lecture.

## Les résultats

### Le compte de mois de l'article vient de sa date de fin, avril 2015

C'était le premier front. La réplication préliminaire du 2026-09-02 rendait 1 073 mois contre 1 065
publiés, et l'écart de huit mois restait inexpliqué.

**L'explication est la date de fin, et elle est exacte pour six facteurs sur six.** Source :
`results/tables/front1_end_date.csv`.

| Facteur | Fin décembre 2015 | Fin avril 2015 | Publié |
|---|---:|---:|---:|
| Marché | 1 073 | **1 065** | 1 065 |
| Taille | 1 073 | **1 065** | 1 065 |
| Valeur | 1 073 | **1 065** | 1 065 |
| Momentum | 1 068 | **1 060** | 1 060 |
| Rentabilité RMW | 629 | **621** | 621 |
| Investissement CMA | 629 | **621** | 621 |

**Comment lire ce tableau, en trois constats.** Un, l'écart de huit mois est le même dans le long
échantillon qui commence en 1926 et dans le court qui commence en 1963, ce qui exclut toute cause
proportionnelle à la longueur. Deux, arrêter l'échantillon en avril 2015 rend le compte exact pour
les six, y compris le momentum dont le décalage de cinq mois par rapport au marché se retrouve seul.
Trois, l'article annonce « 1926-2015 » sans dire quel mois de 2015, et la réponse est donc lisible
dans ses seuls comptes.

**Les deux explications concurrentes sont réfutées, pas ignorées.** Source :
`results/tables/front1_month_counts.csv`.

| Hypothèse testée | Marché | Rentabilité RMW |
|---|---:|---:|
| Départ en juillet ou août 1926, fin décembre 2015 | 1 073 | 629 |
| Départ en novembre 1926 | 1 070 | 629 |
| Départ en janvier 1927 | 1 068 | 629 |
| Au moins 18 séances dans le mois, fin décembre 2015 | 1 066 | 624 |
| Au moins 20 séances dans le mois | 977 | 552 |

**Comment lire ce tableau, en trois constats.** Un, aucune des quatre dates de départ plausibles ne
rend 1 065 : la plus proche, janvier 1927, rend 1 068. Deux, l'exigence de dix-huit séances approche
le compte du marché à une unité près, mais elle retire cinq mois au seul échantillon de 1963. Elle
rendrait 624 au lieu de 621, donc elle ne produit pas le même écart de huit dans les deux
échantillons. Trois, seule la date de fin explique les deux écarts avec un unique mécanisme.

**Les deux facteurs q se referment avec un départ en juin 1967.** À la fin d'avril 2015, notre
millésime rend 579 mois contre 575 publiés. En faisant partir l'échantillon en juin 1967, il rend
exactement 575, valeur portée par la colonne `n_months_with_q_start` du même fichier. Le millésime
courant commence en janvier 1967, et nous ne savons pas si le millésime de 2015 commençait plus tard
ou si les auteurs ont coupé. La correction est **déclarée** et appliquée à toute la suite.

### Le tableau 1, panneau A, se réplique sur les huit facteurs accessibles

Source : `results/tables/replication_table1.csv`. Échantillon `IS`, brut de frais, d'août 1926 à avril
2015 pour les quatre premiers, de juillet 1963 pour RMW et CMA, de juin 1967 pour ROE et IA, univers
des facteurs publiés.

| Facteur | N | Bêta | Bêta publié | Alpha %/an | Alpha publié | Erreur type | Publiée | R² | R² publié |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Marché | 1 065 | 0,622 | 0,61 | **4,74** | 4,86 | 1,57 | 1,56 | 0,388 | 0,37 |
| Taille | 1 065 | 0,626 | 0,62 | -0,86 | -0,58 | 0,92 | 0,91 | 0,392 | 0,38 |
| Valeur | 1 065 | 0,542 | 0,57 | 1,82 | 1,97 | 1,10 | 1,02 | 0,294 | 0,32 |
| Momentum | 1 060 | 0,462 | 0,47 | **12,57** | 12,51 | 1,57 | 1,71 | 0,213 | 0,22 |
| Rentabilité RMW | 621 | 0,586 | 0,62 | 2,49 | 2,44 | 0,88 | 0,83 | 0,343 | 0,38 |
| Investissement CMA | 621 | 0,684 | 0,68 | 0,25 | 0,38 | 0,71 | 0,67 | 0,468 | 0,46 |
| Rentabilité ROE | 575 | 0,678 | 0,63 | 4,98 | 5,48 | 0,96 | 0,97 | 0,460 | 0,40 |
| Investissement IA | 575 | 0,675 | 0,68 | 1,65 | 1,55 | 0,71 | 0,67 | 0,456 | 0,47 |

**Comment lire ce tableau, en trois constats.** Un, les huit comptes de mois sont exacts, ce qui
signifie que nous régressons sur les mêmes dates que l'article et non sur un échantillon voisin.
Deux, le momentum se retrouve à cinq centièmes de point près, 12,57 contre 12,51. L'erreur type du
marché se retrouve à un centième, 1,57 contre 1,56, et ce sont les deux contrôles les plus serrés.
Trois, les deux écarts les plus larges sont la taille, -0,86 contre -0,58, et ROE, 4,98 contre 5,48,
et le second s'explique en partie par le millésime des facteurs q.

Les huit contrôles chiffrés de `results/tables/replication_checks.csv` passent tous, à la tolérance
relative de 25 % déclarée dans `config.yaml` avant de voir les résultats. Le contrôle du nombre de
mois est déclaré en tolérance **absolue nulle** : 1 065 contre 1 065.

**Un contrôle indépendant du levier exigé.** Cederburg et coauteurs rapportent un 99e centile du
poids supérieur à 400 % pour les neuf facteurs, et de 864 % pour le momentum. Nous mesurons 589 %
pour le marché et **814 % pour le momentum**, avec un poids médian de 0,95 et 0,87 respectivement
(`results/tables/leverage_profile.csv`). L'ordre de grandeur et le classement se retrouvent sur une
implémentation indépendante.

### La figure de richesse cumulée

`results/figures/equity_market.png`. **Mode d'emploi.** L'axe vertical est une échelle logarithmique
en dollars des États-Unis, base 1 dollar au 31 août 1936, date choisie parce que c'est le premier
mois où la version en temps réel existe. Trois courbes : le marché sans gestion, le marché géré avec
la constante ex post, le marché géré avec la constante en temps réel. Regarder d'abord l'écart
vertical final, puis les épisodes de 1929-1932 et de 2008, où les trois courbes se séparent le plus.

## La robustesse

### Aucun réglage ne sauve la version tenable

Source : `results/tables/parameter_sweep.csv`. Trente-cinq cellules, écart couvert en temps réel, net
de dix points de base, échantillon `VALIDATION` d'août 1946 à juin 2026, 959 mois pour les
trente premières et 908 pour les cinq du GARCH.

| Mesure de variance | Sans plafond | Plafond 1 | Plafond 1,5 | Plafond 3 | Plafond 6 |
|---|---:|---:|---:|---:|---:|
| Variance réalisée | -0,080 | -0,061 | **-0,039** | -0,093 | -0,103 |
| Variance réalisée centrée | -0,075 | -0,057 | -0,037 | -0,098 | -0,103 |
| Lissage exponentiel, 5 séances | -0,089 | -0,039 | **-0,024** | -0,071 | -0,106 |
| Lissage exponentiel, 11 séances | -0,137 | -0,057 | -0,054 | -0,082 | -0,135 |
| Lissage exponentiel, 22 séances | -0,150 | -0,071 | -0,068 | -0,090 | -0,145 |
| Lissage exponentiel, 66 séances | -0,072 | -0,051 | -0,062 | -0,052 | -0,066 |
| GARCH(1,1) réestimé | -0,261 | -0,194 | -0,235 | -0,228 | -0,261 |

**Comment lire ce tableau, en trois constats.** Un, les trente-cinq cellules sont négatives, sans
exception, donc le résultat ne dépend d'aucun réglage particulier. Deux, la moins mauvaise cellule,
-0,024, emploie un lissage à cinq séances et un plafond de levier à 1,5, et elle reste négative.
Trois, le GARCH réestimé fait systématiquement pire que la variance réalisée, ce qui contredit
l'annexe A.1 de l'article annonçant que des modèles de variance plus élaborés améliorent le résultat,
au moins pour la version tenable.

`results/figures/parameter_heatmap.png` porte les mêmes trente-cinq cellules. **Mode d'emploi.** Une
ligne par mesure de variance, une colonne par plafond de levier, une couleur par ratio de Sharpe net.
Chercher une plage de couleur homogène plutôt qu'une case isolée : une bonne cellule entourée de
mauvaises est du bruit.

### La fenêtre de la constante déplace l'alpha de deux points

Source : `results/tables/constant_window.csv`.

| Fenêtre minimale | N | Alpha %/an | t | Ratio d'appréciation | Sharpe de l'écart couvert |
|---|---:|---:|---:|---:|---:|
| 60 mois | 1 139 | 4,08 | 2,04 | 0,212 | 0,220 |
| 120 mois | 1 079 | 2,44 | 1,25 | 0,133 | -0,020 |
| 240 mois | 959 | 2,95 | 1,64 | 0,186 | -0,115 |
| 360 mois | 839 | 2,82 | 1,60 | 0,193 | 0,000 |

**Comment lire ce tableau, en trois constats.** Un, aucune fenêtre ne rend un t supérieur à 2,04,
alors que la version ex post en rend 3,03 sur l'échantillon de l'article. Deux, l'alpha ne décroît
pas régulièrement avec la fenêtre, ce qui signale que la variation vient du changement d'échantillon
autant que du réglage. Trois, le ratio de Sharpe de l'écart couvert, la seule colonne réellement
tenable, reste entre -0,115 et 0,220 selon un choix qui n'a aucune raison économique d'être fait dans
un sens plutôt que dans l'autre.

### Le délai d'exécution détruit ce qui reste

Source : `results/tables/execution_delay.csv`. Alpha du marché géré, constante en temps réel.

| Délai | N | Alpha %/an | Sharpe |
|---|---:|---:|---:|
| 1 mois, cas de référence | 1 079 | 2,44 | 0,453 |
| 2 mois | 1 078 | 0,70 | 0,381 |
| 3 mois | 1 077 | **-1,91** | 0,280 |

**Comment lire ce tableau, en trois constats.** Un, retarder d'un seul mois retire 1,73 point
d'alpha, soit 71 % du total. Deux, à trois mois l'alpha devient négatif, ce qui confirme que le signal
vit dans la persistance à très court terme de la variance et nulle part ailleurs. Trois, cette
décroissance est cohérente avec la remarque de l'article selon laquelle les alphas baissent quand on
allonge la période de rééquilibrage.

### Les sous-périodes ne sont positives qu'une fois sur deux

Source : `results/tables/subperiods.csv`, écart couvert en temps réel, brut de frais.

| Sous-période | N | Sharpe | t |
|---|---:|---:|---:|
| 1946-08 à 1955-11 | 112 | 0,142 | 0,41 |
| 1955-12 à 1985-11 | 360 | 0,076 | 0,41 |
| 1985-12 à 2015-03 | 352 | -0,095 | -0,47 |
| 2015-04 à 2026-06 | 135 | -0,309 | -1,00 |

**Comment lire ce tableau, en trois constats.** Un, deux sous-périodes sur quatre sont positives, ce
qui donne la part de 0,50 comparée au seuil de 0,60 dans le verdict. Deux, aucune des quatre
statistiques t n'atteint 1 en valeur absolue, donc aucune sous-période ne dit rien à elle seule.
Trois, le signe se dégrade dans le temps, la dernière tranche étant la plus mauvaise.

`results/figures/subperiod_bars.png`. **Mode d'emploi.** Une barre par sous-période, la moustache
étant l'intervalle à 95 % construit sur l'erreur type de Lo. Vérifier que chaque moustache traverse
zéro avant de commenter la hauteur d'une barre.

### Le risque de queue de la version tenable

Source : `results/tables/tail_risk.csv`. Échantillon complet de chaque série, brut de frais sauf la
dernière ligne.

| Série | N | Vol. %/an | Asymétrie | Kurtosis en excès | Pire repli |
|---|---:|---:|---:|---:|---:|
| Marché | 1 199 | 18,4 | 0,15 | 7,39 | -84,6 % |
| Marché géré, constante ex post | 1 199 | 18,4 | -0,03 | 5,42 | -62,3 % |
| Marché géré, constante en temps réel | 1 079 | 24,9 | -0,91 | 17,12 | **-93,1 %** |
| Écart couvert en temps réel, net | 959 | 16,2 | 0,40 | 5,01 | -94,0 % |

**Comment lire ce tableau, en trois constats.** Un, la constante ex post fait exactement ce qu'on lui
demande, égaliser la volatilité à 18,4 % par an, et elle réduit le pire repli de 84,6 % à 62,3 %.
Deux, la même stratégie en temps réel porte une volatilité de 24,9 %, soit 35 % de plus que le
marché, et son pire repli atteint -93,1 %. Trois, ce chiffre tombe dans la fourchette de 68 % à 93 %
que Liu, Tang et Zhou (2019) annoncent pour la version en temps réel, résultat **rapporté** que nous
retrouvons par une implémentation indépendante.

`results/figures/underwater_real_time.png` et `results/figures/return_histogram.png`. **Mode
d'emploi.** La première montre la distance au sommet précédent, en points de pourcentage, et sert à
juger la durée d'un repli autant que sa profondeur. La seconde superpose la loi normale de même
moyenne et de même écart type : l'écart entre l'histogramme et la courbe est ce que l'asymétrie de
-0,91 et la kurtosis de 17,12 chiffrent.

## Les coûts

La stratégie change de levier tous les mois, donc la rotation décide. Source :
`results/tables/costs.csv`. Rotation mesurée en convention de somme entière sur les deux jambes, la
jambe gérée et la jambe de couverture.

| Version | Rotation par an | Brut %/an | Net à 10 pb %/an | Sharpe net | Coût qui annule |
|---|---:|---:|---:|---:|---:|
| Écart couvert, constante et bêta ex post, 1926-2026 | 8,04 | **4,35** | 3,54 | 0,247 | **53,6 pb** |
| Écart couvert, constante et bêta en temps réel, 1946-2026 | 9,74 | **-0,32** | -1,30 | -0,080 | -3,7 pb |

**Comment lire ce tableau, en trois constats.** Un, la conclusion de l'article sur les coûts tient
pour sa propre version : il faudrait 53,6 points de base par unité de rotation pour annuler le
rendement brut, contre les 10 points de base de Frazzini, Israel et Moskowitz (2015) que l'article
retient. Deux, la version tenable n'a pas de seuil de rentabilité, son rendement brut étant déjà
négatif, et le coût qui l'annule est donc lui-même négatif. Trois, la rotation est du même ordre dans
les deux versions, entre 8 et 9,7 par an, donc l'écart ne vient pas des frais mais du rendement brut.

Le multiple de coût survécu vaut zéro (`results/tables/cost_multiples.csv`) : la stratégie tenable est
déjà morte à la moitié du coût de référence.

`results/figures/cost_sensitivity.png`. **Mode d'emploi.** L'axe horizontal porte le multiple appliqué
aux dix points de base, l'axe vertical le ratio de Sharpe net, et la ligne horizontale marque zéro.
Chercher l'abscisse où la courbe croise zéro : ici elle ne la croise pas, la courbe partant déjà
au-dessous.

## Le hors échantillon

### La constante ex post ne gonfle pas l'alpha, elle réduit le bruit

C'est le résultat le plus important de l'étude, et il n'est pas celui qu'on attendait. Source :
`results/tables/front3_constant.csv`, échantillon commun aux deux versions, brut de frais.

| Facteur | N | Alpha ex post | Alpha temps réel | t ex post | t temps réel | Appréciation ex post | Appréciation temps réel |
|---|---:|---:|---:|---:|---:|---:|---:|
| Marché | 1 079 | 2,60 | 2,44 | 1,79 | **1,25** | 0,190 | **0,133** |
| Taille | 1 079 | -0,84 | -0,25 | -0,96 | -0,22 | -0,101 | -0,023 |
| Valeur | 1 079 | 1,16 | 1,81 | 1,12 | 1,18 | 0,119 | 0,126 |
| Momentum | 1 074 | 11,26 | 11,07 | 7,31 | 4,82 | 0,782 | 0,516 |
| Rentabilité RMW | 635 | 2,72 | 1,50 | 3,25 | 3,05 | 0,450 | 0,421 |
| Investissement CMA | 635 | 0,64 | 0,43 | 0,90 | 0,75 | 0,125 | 0,104 |
| Rentabilité ROE | 583 | 6,15 | 4,65 | 6,01 | 5,85 | 0,880 | 0,857 |
| Investissement IA | 583 | 1,90 | 1,31 | 2,28 | 1,92 | 0,330 | 0,277 |

**Comment lire ce tableau, en trois constats.** Un, l'alpha du marché ne perd que 0,16 point en
passant de la constante ex post à la constante en temps réel, sur les mêmes 1 079 mois. La fuite ne
crée donc pas l'alpha, contrairement à ce qu'un lecteur pressé de la critique attendrait. Deux, la
statistique t chute pourtant de 1,79 à 1,25 et le ratio d'appréciation de 0,190 à 0,133, soit une
perte de 30 %. Trois, l'explication est dans la dernière colonne de `front3_constant.csv` : la
version en temps réel porte une volatilité de 1,58 fois celle du marché, contre 1,20 pour la version
ex post. La constante ex post agit donc en réduisant le bruit résiduel, et non en gonflant le
numérateur.

**La comparaison à l'échantillon de l'article demande une précaution.** L'alpha du marché passe de
4,74 % sur 1 065 mois à 2,60 % sur les 1 079 mois communs. Ces deux nombres ne mesurent pas la même
chose : la fenêtre commune commence en août 1936 et perd donc la Grande Dépression, où la stratégie
gagnait le plus. La chute de 4,74 à 2,60 est un effet d'échantillon, celle de 2,60 à 2,44 est l'effet
de la constante, et les mélanger doublerait l'accusation portée contre l'article.

### L'écart couvert en temps réel ne rapporte rien du tout

L'alpha de régression n'est pas un rendement. La série que l'on peut réellement détenir vaut le
facteur géré moins un bêta estimé sur le passé. Mesuré sur 959 mois d'août 1946 à juin 2026, elle
rapporte **-0,32 % par an brut**, avec un ratio de Sharpe de -0,020
(`results/tables/costs.csv`). Sur l'échantillon postérieur à l'article, de mai 2015 à juin 2026, elle
rend un ratio de Sharpe de **-0,362** net de dix points de base, échantillon `OOS`,
134 mois.

Le rééchantillonnage par blocs de douze mois, 2 000 tirages, graine 20260902, place le rendement
annualisé hors échantillon à -5,41 %. Son intervalle va de -13,79 % à +3,06 %, et 13,4 % des tirages
sont positifs (`results/tables/bootstrap.csv`).

### Le bêta de couverture décide du signe sur l'échantillon complet, mais pas hors échantillon

C'est l'objection la plus forte contre le chiffre précédent, et elle est chiffrée plutôt qu'écartée.
Source : `results/tables/hedge_sensitivity.csv`, écart couvert du marché, brut de frais.

| Bêta de couverture | Bêta médian | Sharpe, 959 mois | Sharpe hors échantillon | Corrélation avec le marché |
|---|---:|---:|---:|---:|
| En expansion, tenable | 1,441 | **-0,020** | -0,308 | **-0,407** |
| De plein échantillon, non tenable | 1,070 | **+0,130** | -0,286 | -0,101 |

**Comment lire ce tableau, en trois constats.** Un, le bêta estimé sur le passé vaut 1,441 en médiane
là où le bêta de plein échantillon vaut 1,070, donc la couverture tenable vend trop de marché et
laisse une corrélation résiduelle de -0,407 au lieu de -0,101. Deux, cette sur-couverture décide du
signe sur les quatre-vingts ans : -0,020 avec le bêta en expansion, +0,130 avec le bêta figé. Le
chiffre de -0,32 % par an ne se lit donc pas comme une propriété de la stratégie seule, il porte aussi
le coût d'estimer un bêta en temps réel. Trois, hors échantillon les deux lectures s'accordent, -0,308
contre -0,286, donc le verdict ne dépend pas de ce choix. La ligne de plein échantillon est un
diagnostic rétrospectif, elle est comptée dans les essais et ne remplace pas le cas de référence.

### Le résultat ne survit pas non plus dans sa version ex post après 2015

Source : `results/tables/extension_full_sample.csv`. Alpha de la régression d'engendrement avec la
constante ex post, sur les 134 mois postérieurs à avril 2015.

| Facteur | Alpha %/an | t |
|---|---:|---:|
| Marché | 1,26 | 0,32 |
| Taille | -0,74 | -0,80 |
| Valeur | -1,78 | -1,80 |
| Momentum | 1,23 | 0,88 |
| Rentabilité RMW | 0,67 | 1,14 |
| Investissement CMA | -1,32 | -1,37 |
| Rentabilité ROE | **2,80** | **3,32** |
| Investissement IA | -2,43 | -2,27 |

**Comment lire ce tableau, en trois constats.** Un, le marché, colonne principale de l'article,
tombe de 4,74 % à 1,26 % avec un t de 0,32, donc il ne dit plus rien sur les onze années qui suivent
la publication. Deux, un seul facteur sur huit garde un alpha significatif, la rentabilité sur fonds
propres, et un autre devient significativement négatif, l'investissement de Hou, Xue et Zhang. Trois,
ce contraste rejoint le résultat de Cederburg et coauteurs, chez qui les gains significatifs se
concentrent sur le momentum et sur ROE.

### La combinaison moyenne-variance en temps réel ne renverse pas le classement

Source : `results/tables/front3_combination.csv`, seize cellules, marché seulement.

| Aversion | Fenêtre | Sharpe combinaison | Sharpe marché seul | Équivalent certain combinaison | Équivalent certain marché seul |
|---|---:|---:|---:|---:|---:|
| 3 | 60 mois | 0,550 | 0,527 | 4,46 % | 3,96 % |
| 3 | 120 mois | 0,519 | 0,509 | 4,36 % | 4,29 % |
| 3 | 240 mois | 0,381 | 0,412 | 1,69 % | 1,96 % |
| 3 | 360 mois | 0,405 | 0,395 | 2,70 % | 2,59 % |

**Comment lire ce tableau, en trois constats.** Un, la combinaison l'emporte dans 12 des 16 cellules
du fichier complet, ce qui **ne reproduit pas** le renversement annoncé par Cederburg et coauteurs,
qui mesurent 0,42 contre 0,46 pour le marché. Deux, l'avantage est minuscule au réglage de référence,
sept points de base d'équivalent certain par an, et il change de signe à 240 mois. Trois, le poids
médian donné à la jambe gérée vaut 0,196 contre un poids de marché plus grand, donc la règle
moyenne-variance neutralise elle-même la stratégie plutôt que de la rejeter.

Notre protocole diffère du leur sur trois points déclarés. Nous n'employons que le marché et non
103 stratégies. Notre échantillon va jusqu'en juin 2026 et non décembre 2016. Notre constante est
déjà estimée en temps réel dans la jambe gérée. Le désaccord est donc **déclaré non résolu**.

### Les contrôles de surapprentissage

| Contrôle | Valeur mesurée | Fichier |
|---|---:|---|
| Nombre d'essais comptés | 89 | `trials.csv` |
| Probabilité de surapprentissage | **0,700** | `metrics.json` |
| Sharpe moyen des 7 chemins de validation croisée | **-0,119** | `cpcv_distribution.csv` |
| Part de chemins négatifs | 1,000 | `cpcv_distribution.csv` |
| Ratio de Sharpe dégonflé | 7,0e-37, arrondi à 0,000 | `deflated_sharpe.csv` |
| t exigé par Bonferroni sur 89 essais | 3,45 | `deflated_sharpe.csv` |
| t observé hors échantillon | -1,18 | `deflated_sharpe.csv` |

**Comment lire ce tableau, en trois constats.** Un, la validation croisée combinatoire purgée juge
ici le PROCESSUS de sélection : sur chaque bloc d'apprentissage, la meilleure des trente-cinq
configurations est retenue, puis évaluée sur le bloc de test suivant. Deux, les sept chemins ainsi
reconstruits sont tous négatifs, donc choisir la meilleure configuration sur le passé n'a jamais
produit un ratio de Sharpe positif ensuite. Trois, le rabais de Harvey et Liu n'est pas calculable,
rabattre un ratio de Sharpe négatif n'ayant pas de sens, et la statistique t brute est reportée telle
quelle, ce que la colonne `haircut_status` déclare.

**La correction pour tests multiples change les conclusions par facteur.** Source :
`results/tables/multiple_testing.csv`, correction de Holm sur les huit statistiques t de la version en
temps réel.

| Facteur | t | Valeur p ajustée | Rejeté à 5 % |
|---|---:|---:|---|
| Momentum | 4,82 | 0,0000098 | oui |
| Rentabilité ROE | 5,85 | 0,000000039 | oui |
| Rentabilité RMW | 3,05 | 0,0139 | oui |
| Investissement IA | 1,92 | 0,276 | non |
| Marché | 1,25 | **0,845** | non |
| Valeur | 1,18 | 0,845 | non |
| Investissement CMA | 0,75 | 0,909 | non |
| Taille | -0,22 | 0,909 | non |

**Comment lire ce tableau, en trois constats.** Un, le marché, qui porte tout le récit de l'article,
ne survit pas à la correction, avec une valeur p ajustée de 0,845. Deux, trois facteurs survivent, et
ce sont exactement ceux que Cederburg et coauteurs trouvent significatifs, momentum et ROE en tête.
Trois, la gestion en volatilité du momentum est le seul résultat que les trois articles du débat
acceptent, et notre correction ne l'entame pas.

`results/figures/rolling_sharpe_spread.png` et `results/figures/qq_plot_spread.png`. **Mode d'emploi.**
La première trace le ratio de Sharpe de l'écart couvert sur fenêtre glissante de 120 mois : chercher
si la courbe passe durablement au-dessus de zéro plutôt que de commenter un pic. La seconde compare
les quantiles observés aux quantiles normaux, et l'écart aux extrémités mesure ce que le ratio de
Sharpe ignore.

## Les limites

**Le portage de change manque.** Une colonne du tableau 1 sur neuf n'est pas reproductible sans une
série que personne ne publie. Statut : **non trouvé**, cherché sur la page de données d'Adrien
Verdelhan le 2026-09-02.

**Les facteurs q sont d'un autre millésime.** L'écart sur ROE mélange une différence de méthode et
une différence de données, et l'étude ne sait pas les séparer.

**Le départ de juin 1967 pour les facteurs q est une déduction, pas une lecture.** Il rend le compte
publié exact, ce qui est un argument et non une preuve.

**Aucun coût de financement du levier n'est retranché.** Le poids dépasse 2 dans 17 % des mois pour le
marché et 25 % pour le momentum, et un investisseur réel paierait pour ce levier. La stratégie
tenable étant déjà perdante sans ce coût, l'omission ne peut que renforcer la conclusion.

**Le choix de l'écart couvert comme mesure hors échantillon est une décision de l'étude.** Un lecteur
qui préférerait juger sur le seul facteur géré verrait un ratio de Sharpe positif, celui du marché
lui-même, qui ne dit rien sur la gestion en volatilité. Le bêta de couverture est ce qui isole
l'apport de la stratégie, et il est estimé sur le passé.

**La couverture en temps réel vend trop de marché.** Son bêta médian vaut 1,441 contre 1,070 pour le
bêta de plein échantillon, si bien que l'écart couvert garde une corrélation de -0,407 avec le marché
au lieu d'être orthogonal. Sur les 959 mois, ce seul choix décide du signe, -0,020 contre +0,130. Hors
échantillon les deux lectures s'accordent, et c'est pourquoi le verdict n'en dépend pas.

**Le compte de 89 essais couvre les évaluations de performance, pas les 160 comptes de mois du front
1.** Ces derniers ne mesurent aucune performance et ne peuvent pas être sélectionnés comme résultat.
Deux essais restent hors du compte et sont nommés ici. La variante de Newey-West n'a pas été
exécutée. Les huit régressions d'extension postérieures à 2015 portent la série de l'article, et non
une stratégie candidate. Porter le compte de 89 à 200 laisse le ratio dégonflé sous 1e-29 et le seuil de
Bonferroni à 3,66 contre un t observé de -1,18, donc aucun critère ne bascule.

**Le désaccord avec Cederburg et coauteurs sur la combinaison moyenne-variance n'est pas résolu.**
Notre combinaison l'emporte de peu là où la leur perd. Trois différences de protocole sont déclarées
plus haut, et aucune n'a été isolée.

**La régression emploie des erreurs types ordinaires**, comme l'article. Une correction de
Newey-West est disponible dans `spanning_regression` par l'argument `cov_type` et n'a pas été
retenue pour rester comparable au tableau 1.

**Les facteurs q s'arrêtent en décembre 2025.** Le millésime publié sur `global-q.org` ne va pas
plus loin, si bien que les colonnes ROE et IA de l'extension portent 128 mois postérieurs à l'article
contre 134 pour les six facteurs de Kenneth French, ce que la colonne `n_months_after_paper` de
`results/tables/extension_full_sample.csv` montre.

**Aucun résultat ne porte sur l'avenir.** Tous les chiffres sont mesurés sur des périodes nommées.

## Le verdict

**`REJECTED`**, déduit par `quantlab.reporting.study.decide_verdict` depuis les seuils écrits dans
`config.yaml` avant que les résultats existent. Voici les neuf critères, avec la valeur mesurée en
face du seuil.

| Critère | Mesuré | Seuil | Résultat |
|---|---:|---:|---|
| Signe économique attendu | alpha en échantillon positif | positif | RÉUSSI |
| Signe du Sharpe hors échantillon | **-0,362** | rejet à 0 ou moins | **ÉCHOUÉ** |
| Réplication, 8 contrôles chiffrés | 8 sur 8 dans la tolérance | tous exigés | RÉUSSI |
| Sharpe hors échantillon | -0,362 | minimum 0,50 | ÉCHOUÉ |
| t après correction pour essais multiples | -1,179 | minimum 3,00 | ÉCHOUÉ |
| Ratio de Sharpe dégonflé | 0,000 | minimum 0,95 | ÉCHOUÉ |
| Probabilité de surapprentissage | 0,700 | maximum 0,50 | ÉCHOUÉ |
| Part de sous-périodes positives | 0,500 | minimum 0,60 | ÉCHOUÉ |
| Multiple de coûts survécu | 0,000 | minimum 2,00 | ÉCHOUÉ |
| Corrélation absolue avec le portefeuille détenu | 0,407, soit -0,407 signée | maximum 0,60 | RÉUSSI |

**Comment lire ce tableau, en trois constats.** Un, le verdict est `REJECTED` et non `REPLICATED`
parce que l'échelle du laboratoire fait du signe du ratio de Sharpe hors échantillon un critère de
rejet, qui précède tous les autres. Deux, la corrélation est jugée en valeur absolue par
`decide_verdict`, et sa valeur signée vaut -0,407 : l'écart couvert est net vendeur de marché, ce que
la section précédente chiffre. Trois, les huit contrôles de réplication passent, donc le rejet ne porte
pas sur la fidélité de notre implémentation à l'article mais sur ce que la stratégie rapporte à qui la
détient.

**Un seul seuil est plus large que celui du laboratoire, et il ne change rien.** La tolérance de
réplication vaut 0,25 dans `config.yaml` contre 0,10 par défaut dans
`quantlab.reporting.study`. Le plus grand écart relatif mesuré vaut 0,092, celui de ROE, donc les huit
contrôles passeraient aussi au seuil par défaut. Les sept autres seuils sont exactement ceux du
laboratoire.

**Ce que l'étude établit, en trois phrases.** Le tableau 1 de Moreira et Muir se réplique
exactement, comptes de mois compris, et son échantillon se termine en avril 2015. La constante de
calibrage rétrospective ne crée pas l'alpha, elle divise la volatilité résiduelle, ce qui gonfle la
statistique t de 1,25 à 1,79 et le ratio d'appréciation de 0,133 à 0,190. La série que l'on peut
détenir rapporte -0,32 % par an brut sur quatre-vingts ans, et -1,30 % net de dix points de base.

**La prochaine décision.** Le seul résultat qui survit à la correction pour tests multiples est la
gestion en volatilité du momentum, avec une statistique t de 4,82 en temps réel. C'est l'objet que
l'étude 002 devra reprendre, et c'est aussi ce que Barroso et Santa-Clara (2015) et Daniel et
Moskowitz (2016) documentaient avant Moreira et Muir.

## Reproduire

```bash
export QUANTLAB_USER_AGENT="votre nom votre courriel"
uv run python studies/006_volatility_managed/run.py
uv run pytest tests/unit/test_strategies_volatility_managed.py -o addopts="" -q
```

L'exécution télécharge six fichiers de la bibliothèque de Kenneth French et deux fichiers de
`global-q.org`, met les archives en cache dans la couche `raw` du lac, et réécrit l'ensemble de
`results/`. Deux exécutions consécutives rendent des tableaux identiques au fichier près, seul
l'identifiant d'expérience changeant, ce qui a été vérifié par comparaison des répertoires. La
reproduction a été refaite le 2026-09-02 après effacement complet de `results/` : les vingt-six
fichiers CSV et les neuf figures en PNG sont revenus octet pour octet.

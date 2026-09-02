# Portage

## La question de recherche

Le portage, l'écart de taux entre deux devises, prédit-il le rendement futur du change, et le
portefeuille qui l'exploite paie-t-il son ratio de Sharpe par une asymétrie négative ?

**La réponse, en quatre phrases.** Sur la fenêtre de l'article, le test central se reproduit
presque exactement : le coefficient de panel vaut **1,084** contre 1,09 publié, et l'asymétrie
**-0,666** contre -0,68. Le ratio de Sharpe vaut 0,602 contre 0,68, et les cinq contrôles chiffrés
passent, donc le verdict déduit est `REPLICATED`. Après septembre 2012, fin de l'échantillon de
l'article, le même coefficient tombe à **0,303** avec une statistique t de 0,29, et le ratio de
Sharpe net à **0,144**. Le portage de change reste donc une prime mesurable et cesse d'être un
prédicteur significatif sur les treize années suivantes.

**Une réserve pèse sur ces deux quasi-égalités, et elle vient de nous.** Notre classement compte le
dollar comme un actif, ce que l'article ne fait pas. Retirer cette colonne laisse le ratio de Sharpe
complet intact, 0,532 contre 0,528, et fait passer l'asymétrie complète de **-0,570 à +0,253**. Sur
la fenêtre de l'article, le coefficient tombe de 1,084 à **0,897** et sa statistique t de 2,159 à
**1,700**. Le tableau `results/tables/numeraire_variant.csv` chiffre l'écart, et la section
« La robustesse » le lit.

**Le second résultat est une absence, et il était attendu.** Trois des quatre classes d'actifs de
l'article ne sont pas reproductibles sur données gratuites. La consigne du laboratoire était de le
documenter plutôt que d'en fabriquer une approximation, et la section « Les données » nomme ce qui a
été cherché et où. Le verdict ne porte donc que sur le portage de change.

Chaque chiffre ci-dessous vient d'un fichier de `results/`, et le fichier est nommé.

## L'article

Koijen, R. S. J., Moskowitz, T. J., Pedersen, L. H. et Vrugt, E. B. (2018), « Carry », *Journal of
Financial Economics* 127(2), 197-225, DOI 10.1016/j.jfineco.2017.11.002.

La version publiée est derrière un péage et n'a pas été ouverte. Les chiffres cibles viennent du
**manuscrit accepté** déposé au CBS Research Portal, sous licence CC BY-NC-ND, recopié dans
`docs/literature/koijen_moskowitz_pedersen_vrugt_2018.md`. Statut de ces chiffres : **rapportés**.

Trois publications répondent à l'article, et l'étude les prend au sérieux.

| Auteurs | Revue | Ce qu'ils opposent |
|---|---|---|
| Collin-Dufresne (2012) | Discussion à l'American Finance Association | L'intérêt sur le collatéral est omis, ce qui biaise les profits vers le haut. L'asymétrie fortement négative n'apparaît qu'en devises. |
| Daniel, Hodrick et Lu (2017) | *Critical Finance Review* 6(2) | Le portage de change se décompose en une partie neutre au dollar et une partie exposée au dollar, aux propriétés opposées. |
| Bekaert et Panayotov (2020) | *Journal of Financial and Quantitative Analysis* 55(4) | Certains portages du G10 ont une asymétrie positive, d'autres une asymétrie fortement négative, et le tri par rang les mélange. |

**Comment lire ce tableau, en trois constats.** Un, les trois objections visent le portage de CHANGE,
la seule classe que nous reproduisons, donc elles sont toutes testables ici. Deux, celle de Daniel,
Hodrick et Lu est mesurée dans la section « Les résultats », par une décomposition en deux jambes.
Trois, celle de Bekaert et Panayotov est mesurée dans la section « La robustesse », par la variante
qui fait entrer le yen dès 1979.

## L'intuition économique

Le portage devrait rapporter parce qu'il est la partie observable d'une prime de risque qui varie
dans le temps, et non parce qu'il annonce une évolution du prix.

La tension qui fait l'article tient en une comparaison. Sous la parité non couverte des taux
d'intérêt, un taux étranger élevé est exactement compensé par une dépréciation attendue de cette
devise, donc le portage ne prédit rien. Sous des primes de risque qui varient, un portage élevé
signale au contraire un rendement attendu élevé. Un seul coefficient sépare les deux thèses, et il
se mesure.

Le mécanisme se lit sur l'action. Si le rendement exigé d'un titre monte alors que ses dividendes ne
changent pas, son prix baisse, donc son rendement en dividende monte. Le portage monte avec la prime
exigée, mécaniquement.

**Ce qui ferait disparaître le rendement.** Trois extinctions, dans l'ordre de vraisemblance. Les
primes de risque cessent de varier, et le coefficient de l'équation (23) tombe à zéro. Le capital
d'arbitrage devient assez abondant pour effacer la compensation exigée en récession. Les coûts de
transaction montent au niveau qui annule le rendement brut. La première extinction est celle que
l'étude mesure hors échantillon, et la troisième est chiffrée dans la section « Les coûts ».

## La définition mathématique

La décomposition qui ouvre l'article sépare le rendement en une partie connue et une partie
inattendue :

\[ r_{t+1} = \underbrace{C_t + E_t\!\left(\frac{\Delta S_{t+1}}{X_t}\right)}_{E_t(r_{t+1})} + u_{t+1} \]

Le portage d'un contrat à terme entièrement collatéralisé, équation (6) :

\[ C_t = \frac{S_t - F_t}{F_t} \]

En change, la parité couverte des taux fait de cet écart une fonction du seul différentiel de taux,
équation (7). Avec \(r^{f*}\) le taux étranger et \(r^{f}\) le taux local :

\[ C_t = \frac{S_t - F_t}{F_t} = \left(r^{f*}_t - r^{f}_t\right)\frac{1}{1 + r^{f}_t} \]

Le rendement en excès d'une position longue sur la devise, financée en dollars, avec \(S\) le prix de
la devise en dollars :

\[ rx_{t+1} = \left(1 + \frac{r^{f*}_t}{12}\right)\frac{S_{t+1}}{S_t} - \left(1 + \frac{r^{f}_t}{12}\right) \]

Les poids du tri par rang, section 3 du manuscrit, avec \(N_t\) le nombre d'actifs cotés :

\[ w^i_t = z_t\left(\text{rg}\left(C^i_t\right) - \frac{N_t + 1}{2}\right), \qquad \sum_i \left|w^i_t\right| = 2 \]

Le test central, équation (23), une régression de panel du rendement futur sur le portage, avec un
effet fixe d'actif et un effet fixe de date :

\[ rx^i_{t+1} = a_i + b_t + c\,C^i_t + \varepsilon^i_{t+1} \]

Le coefficient \(c\) vaut zéro sous la parité non couverte, un si le portage passe entièrement dans
le rendement, et plus de un si le prix s'apprécie en plus.

## Les données

Une classe d'actifs sur quatre est couverte, et les trois autres sont déclarées non trouvées.
Source : `results/tables/data_sources.csv` et `results/tables/asset_classes_not_reproducible.csv`.

| Classe de l'article | Ce que l'article emploie | Couverte |
|---|---|---|
| Devises | 20 contrats de change à terme à un mois | **oui**, par les écarts de taux |
| Obligations, pente 10 ans moins 2 ans | contrats synthétiques sur taux zéro-coupon | **substitution déclarée** |
| Matières premières | 24 contrats à terme, structure par terme | **non trouvé au 2026-09-02** |
| Indices actions | 13 contrats à terme, dividendes attendus | **non trouvé au 2026-09-02** |
| Options d'achat et de vente | OptionMetrics, 10 indices | **non trouvé au 2026-09-02** |

**Comment lire ce tableau, en trois constats.** Un, la partie devises est la plus reproductible
parce que la parité couverte des taux ramène le portage à un écart de taux, et que les taux courts
sont publics. Deux, la pente obligataire est approchée et non répliquée, et la section « Nos écarts »
chiffre l'effet de la substitution. Trois, les trois dernières lignes ne sont pas des renoncements
de commodité, et le tableau `asset_classes_not_reproducible.csv` nomme les sources consultées.

**Ce qui a été cherché pour les trois classes manquantes, le 2026-09-02.** Pour les matières
premières, il faut le prix de plusieurs échéances à la même date, ce que ne donne aucune source
gratuite. Les séries continues ajustées de `turtletrader.com` écrasent justement l'écart entre
échéances qui EST le portage. La base des prix de la Banque mondiale publie des prix au comptant
mensuels et aucun prix à terme. Le Cboe ne diffuse que ses propres contrats. La base `CHRIS` de
Nasdaq Data Link, héritée de Quandl, n'est plus accessible librement.

Pour les indices actions, le portage exige le dividende ATTENDU sur le mois à venir, et les séries
gratuites publient le dividende VERSÉ. Les indices `^DVS` et `^DIVD` de Yahoo Finance ne couvrent que
le S&P 500, quand l'article en demande treize. Les contrats sur dividendes du CME ne remontent pas à
1988 en libre accès. Pour les options, OptionMetrics est la source nommée par l'article, et elle est
vendue sous licence.

Couverture des séries employées, mesurée le 2026-09-02 dans `results/tables/currency_coverage.csv`.

| Devise | Premier portage | Mois de portage | Portage moyen %/an | Rendement moyen %/an |
|---|---|---:|---:|---:|
| Dollar australien | 1971-01 | 665 | 2,16 | 1,87 |
| Dollar canadien | 1971-01 | 665 | 0,58 | 0,18 |
| Livre sterling | 1971-01 | 660 | 1,44 | 0,89 |
| Dollar néo-zélandais | 1973-12 | 630 | **3,14** | **2,08** |
| Couronne norvégienne | 1979-01 | 569 | 1,62 | 0,83 |
| Couronne suédoise | 1982-01 | 533 | 0,70 | 0,10 |
| Couronne danoise | 1987-01 | 473 | 0,32 | 0,94 |
| Euro | 1999-01 | 324 | -0,63 | -0,04 |
| Franc suisse | 1999-07 | 323 | -1,84 | 0,92 |
| Yen | 2002-04 | 289 | **-1,73** | **-2,19** |
| Dollar des États-Unis | 1971-01 | 665 | 0,00 | 0,00 |

**Comment lire ce tableau, en trois constats.** Un, l'univers est déséquilibré dans le temps, comme
celui de l'article où les monnaies entrent à des dates différentes. Trois monnaies cotent dès 1971 et
le yen n'entre qu'en 2002, faute d'un taux interbancaire publié plus tôt. Deux, le classement des
portages moyens est celui que la littérature décrit, le dollar néo-zélandais en tête, le franc suisse
et le yen en bas. Trois, les deux monnaies au portage le plus élevé portent aussi les deux rendements
les plus élevés, et la seule dont le signe s'inverse est le franc suisse, portage -1,84 et rendement
+0,92.

**Ce que ces données ne sont pas.** Le taux interbancaire de l'OCDE est une moyenne du mois, et non
un point de fin de mois. Il est connu à la fin du mois qu'il décrit, donc il n'introduit aucune
information future, mais il n'est pas le taux exact auquel se traite un contrat à terme. Les séries
de change de la Réserve fédérale sont des cotations de midi à New York, et non des clôtures de
Londres.

## La méthodologie originale

L'article trie neuf classes d'actifs par rang de portage, rééquilibre chaque mois, et maintient deux
dollars d'exposition brute en permanence. Le poids de chaque titre est proportionnel à l'écart entre
son rang de portage et le rang médian de sa classe. Le portefeuille est donc long les portages hauts,
court les portages bas, et à somme nulle.

Le facteur mondial de portage pondère chaque classe par 10 % divisé par sa volatilité de plein
échantillon. Cette précaution est nécessaire, les options ayant environ trois cents fois la
volatilité des Treasuries.

Trois variantes servent de contrôle. La stratégie « carry1-12 » trie sur la moyenne du signal des
douze derniers mois, ce qui efface les effets de saison. La stratégie « carry2-13 » saute en plus un
mois, pour qu'aucune donnée ne serve à la fois au signal et au rendement. La stratégie de calendrier
achète ou vend chaque titre selon que son portage dépasse sa moyenne historique.

Le test central est la régression de panel de l'équation (23), avec effets fixes de contrat et de
temps, et des écarts types groupés par date. L'article n'applique aucune correction pour tests
multiples, ni sur les neuf classes, ni sur les trois variantes de signal, ni sur les quatre
spécifications d'effets fixes.

## Notre implémentation

La stratégie vit dans `src/quantlab/strategies/carry.py`, et `run.py` ne fait qu'orchestrer. Le
module sépare quatre objets que la formule mélange : la convention de cotation, le portage, les poids
et la régression de panel.

**Le sens de cotation est déclaré, jamais deviné.** La Réserve fédérale publie ses taux de change
dans les deux sens. `DEXUSUK` cote des dollars par livre, `DEXJPUS` cote des yens par dollar. Se
tromper de sens inverse la variation de change, donc le signe du rendement. Le sens vit dans
`config.yaml` sous `spot_series`, et `to_usd_per_unit` refuse un sens non déclaré. Un test confronte
chacune des dix déclarations à la règle de nommage de FRED, `DEXUS??` contre `DEX??US`. Le contrôle a
été validé par mutation : inverser les deux branches de la conversion fait échouer un test qui
mesure le signe du rendement sur une devise qui s'apprécie.

**Le décalage se fait en un seul endroit.** `carry_portfolio` porte le `shift(execution_lag)` qui
fait que le poids du mois \(t+1\) emploie le portage du mois \(t\). Un décalage nul lève une erreur
au lieu de tourner. Trois tests vérifient la propriété en perturbant le signal après une date, en
tronquant l'échantillon, et en comparant le poids appliqué à celui du mois précédent. Le contrôle a
été validé par mutation : remplacer `shift(execution_lag)` par `shift(0)` fait échouer le test de
perturbation.

**Une devise n'entre que si son change est coté.** Le portage se calcule dès que les deux taux
existent, mais une monnaie dont le prix n'est pas publié n'est pas négociable. Le signal est donc
masqué par la disponibilité du change à la date de formation. Sans ce masque, l'euro recevrait un
poids dès janvier 1994, cinq ans avant sa première cotation.

**La régression de panel est vérifiée contre une autre implémentation.** Les effets fixes sont
retirés par projections alternées, ce que le panel non équilibré exige. Deux tests comparent le
coefficient et son erreur type groupée à une régression à variables muettes explicites ajustée par
`statsmodels`, et les deux se retrouvent à la sixième décimale. Le contrôle a été validé par
mutation : retirer la correction d'échantillon fini fait échouer un test de couverture.

**La rotation a une seule définition.** Elle se mesure contre les poids dérivés, en convention de
somme entière, par `quantlab.analytics.turnover`, puis se décale du délai d'exécution pour que le
coût pèse sur le mois qu'il finance. Le même objet alimente le coût net et le seuil de rentabilité,
donc les deux ne peuvent pas diverger.

Aucun paramètre ne vit dans le code. Le fichier `config.yaml` porte les 34 séries FRED, les 3 schémas
de pondération et les 3 variantes du signal de portage. Il porte aussi les 5 taux de coût, les 7
multiples, les 3 délais, les 5 fenêtres de crise et les 8 seuils du verdict.

## Nos écarts avec l'article

**Notre portage vient d'un écart de taux, pas de points de report.** L'article calcule le portage de
change depuis le prix d'un contrat à terme à un mois. Nous employons l'équation (7), qui suppose la
parité couverte des taux d'intérêt. Cette parité s'est écartée après 2008, et l'écart mesuré par la
littérature atteint quelques dizaines de points de base par an sur certaines monnaies. Notre portage
est donc légèrement faux après 2008, dans un sens qui n'est pas mesuré ici.

**Notre taux est à trois mois, pas à un mois.** Aucune série gratuite ne publie un taux interbancaire
à un mois pour dix pays sur cinquante ans. Le taux à trois mois est divisé par douze pour une
détention d'un mois, ce qui suppose une courbe plate sur ce segment.

**Nous classons le dollar comme un actif, ce que l'article ne fait pas.** L'article classe des
contrats de change, tous libellés contre le dollar, donc le dollar n'y est pas classable et les poids
étrangers somment à zéro. Nous lui donnons une colonne de portage nul, et il reçoit donc un rang et
un poids. Deux conséquences se mesurent, et la section « La robustesse » les chiffre. Le portefeuille
porte une exposition nette aux devises étrangères de 0,136 sur deux dollars d'exposition brute. Et le
dollar compte dans le plancher de quatre actifs, ce qui fait commencer la série 35 mois plus tôt.
C'est l'écart qui pèse le plus sur nos chiffres de tête, et il n'était pas déclaré avant l'audit du
2026-09-02.

**Notre univers compte dix monnaies développées, contre vingt monnaies dont des émergentes.** C'est
l'écart le plus lourd, et il joue dans le sens de la prudence : les monnaies émergentes portent les
portages les plus élevés et les asymétries les plus marquées. Notre ratio de Sharpe et notre
asymétrie devraient donc être plus faibles en valeur absolue, ce que la mesure confirme.

**Notre échantillon déborde des deux côtés du sien.** Il commence en février 1971, à la fin de
Bretton Woods, et finit en juin 2026. L'article couvre novembre 1983 à septembre 2012. Toutes les
comparaisons chiffrées sont faites sur SA fenêtre, et la fenêtre complète est rapportée à part.

**Le biais de survie de l'univers est déclaré.** Les dix monnaies retenues sont celles qui existent
et se cotent en 2026. Aucune monnaie disparue n'y figure, alors que les monnaies européennes
antérieures à l'euro auraient dû l'être. L'article ne dit pas non plus ce qu'il fait de ce point.

**Nous n'employons pas le facteur mondial de portage.** Il pondère chaque classe par sa volatilité de
plein échantillon, ce qui est un regard en avant, et il exige les neuf classes que nous n'avons pas.

**Nous corrigeons pour les tests multiples**, ce que l'article ne fait pas, et le résultat change les
conclusions par configuration.

**Nous ajoutons deux objets que l'article n'a pas.** La décomposition en jambe neutre au dollar et
jambe de dollar, qui répond à Daniel, Hodrick et Lu (2017). Et la comparaison à un momentum de change
de même construction, qui isole ce qui est propre au portage.

## Les résultats

### Le tableau 2, panneau A, se retrouve sur la colonne des devises

Source : `results/tables/replication_table2.csv`. Échantillon `IS`, brut de frais, de novembre 1983 à
septembre 2012, univers de dix monnaies développées contre le dollar.

| Série | N | Moyenne %/an | Écart type %/an | Asymétrie | Aplatissement | Sharpe | Sharpe publié |
|---|---:|---:|---:|---:|---:|---:|---:|
| Portage de change | 347 | 5,03 | 8,36 | **-0,666** | 2,85 | **0,602** | 0,68 |
| Passif équipondéré | 347 | 3,19 | 8,17 | -0,201 | 0,94 | **0,391** | 0,36 |
| Momentum de change | 347 | 0,87 | 8,83 | -0,209 | 1,19 | 0,099 | non publié |

**Comment lire ce tableau, en quatre constats.** Un, l'asymétrie se retrouve à deux centièmes près,
-0,666 contre -0,68, et c'est le contrôle le plus serré de l'étude. Deux, cette quasi-égalité ne
survit PAS au retrait du dollar du classement : l'asymétrie vaut alors -0,522, comme le montre la
section « La robustesse ». Trois, le repère passif se retrouve aussi, 0,391 contre 0,36, alors
qu'aucun réglage ne visait ce nombre. Quatre, l'aplatissement en excès manque, 2,85 contre 4,46, ce
que l'absence des monnaies émergentes explique en partie sans qu'on puisse le prouver ici.

Les cinq contrôles chiffrés de `results/tables/replication_checks.csv` passent tous, à la tolérance
relative de 0,50 déclarée dans `config.yaml` avant de voir les résultats. Le plus grand écart relatif
mesuré vaut 0,197, celui de la statistique t du coefficient de panel.

### Le coefficient de l'équation (23) se reproduit à un demi pour cent près

Source : `results/tables/panel_regression.csv`. Écarts types groupés par date.

| Effets fixes | Fenêtre | c | Erreur type | t | t contre un | N | R² |
|---|---|---:|---:|---:|---:|---:|---:|
| Actif et date | article | **1,084** | 0,502 | 2,159 | 0,168 | 3 177 | 0,005 |
| Actif seulement | article | 1,566 | 0,531 | 2,951 | 1,067 | 3 177 | 0,012 |
| Date seulement | article | 1,086 | 0,377 | 2,880 | 0,229 | 3 177 | 0,009 |
| Aucun | article | 1,451 | 0,405 | 3,585 | 1,115 | 3 177 | 0,018 |
| Actif et date | complète | 1,188 | 0,371 | **3,201** | 0,507 | 5 785 | 0,006 |
| Actif et date | après 2012-09 | **0,303** | 1,031 | **0,294** | -0,676 | 1 782 | 0,000 |

**Comment lire ce tableau, en quatre constats.** Un, la spécification de l'article rend 1,084 contre
1,09 publié, soit un écart relatif de 0,005, et sa statistique t rend 2,159 contre 2,69. Deux, cet
écart de 0,005 monte à 0,177 si le dollar sort du classement, et la statistique t tombe à 1,700, ce
que la section « La robustesse » chiffre. Trois, la parité non couverte des taux, qui prédit un
coefficient nul, est rejetée sur la fenêtre de l'article et sur la fenêtre complète, mais pas après
2012 où l'erreur type triple. Quatre, la colonne « t contre un » ne rejette jamais l'hypothèse que le
portage passe ENTIÈREMENT dans le rendement, ce qui est aussi la lecture des auteurs.

**Le choix des effets fixes déplace le coefficient de 0,48.** Retirer l'effet fixe de date le fait
passer de 1,084 à 1,566, parce que le mouvement commun du dollar rentre alors dans la mesure. Les
quatre spécifications comptent comme quatre essais dans `results/tables/trials.csv`.

### Le portage perd exactement quand le momentum gagne

Source : `results/tables/crisis_windows.csv`. Rendements cumulés, bruts de frais, sur des fenêtres
nommées dans `config.yaml` avant de voir les résultats.

| Épisode | Mois | Portage % | Momentum % | Passif % | Pire mois du portage % |
|---|---:|---:|---:|---:|---:|
| Recul 1 de l'annexe D, 1972-08 à 1975-09 | 38 | -7,86 | **+9,33** | -6,75 | -5,13 |
| Recul 2 de l'annexe D, 1980-03 à 1982-06 | 28 | **+25,75** | +14,05 | -17,66 | -1,21 |
| Recul 3 de l'annexe D, 2008-08 à 2009-02 | 7 | **-22,78** | **+8,73** | -20,59 | -10,45 |
| Mécanisme de change européen, 1992-08 à 1992-10 | 3 | -2,38 | -1,17 | -5,97 | -7,31 |
| Pandémie, 2020-01 à 2020-03 | 3 | -7,71 | **+7,29** | -6,59 | -5,19 |

**Comment lire ce tableau, en trois constats.** Un, le troisième recul de l'annexe D se retrouve
entièrement, le portage perdant 22,8 % en sept mois, et il contient le pire mois de tout
l'échantillon à -10,45 %. Deux, le momentum GAGNE dans quatre épisodes sur cinq, dont les deux où le
portage perd le plus, ce qui en fait la couverture naturelle du portage. Trois, le deuxième recul de
l'annexe D est POSITIF chez nous à +25,75 %, et l'explication est que l'annexe D décrit le facteur
mondial des neuf classes, pas le portage de change seul.

Les cinq pires reculs du portage de change vivent dans `results/tables/worst_drawdowns.csv`. Le pire
va de juillet 2007 à janvier 2009, atteint -27,87 %, et met 184 mois à se refermer.

### La jambe neutre au dollar n'explique pas l'asymétrie

Source : `results/tables/dollar_legs.csv`. Échantillon complet, brut de frais, décomposition de
Daniel, Hodrick et Lu (2017).

| Jambe | %/an | Écart type %/an | Sharpe | Asymétrie | Perte espérée à 5 % | Pire repli % |
|---|---:|---:|---:|---:|---:|---:|
| Portage complet | 3,87 | 7,33 | 0,528 | **-0,570** | 4,94 | -27,87 |
| Neutre au dollar | 3,15 | 6,52 | 0,483 | -0,205 | 4,30 | -25,69 |
| Pari sur le dollar | 0,72 | 2,40 | 0,299 | -0,306 | 1,67 | -15,78 |

**Comment lire ce tableau, en trois constats.** Un, l'identité tient à 1,4e-17, colonne
`identity_max_error`, donc la somme des deux jambes est bien le rendement total. Deux, l'exposition
nette aux devises étrangères vaut 0,136 en moyenne sur deux dollars d'exposition brute, soit 6,8 %.
Le tri par rang n'est donc pas aussi neutre au dollar qu'il en a l'air. Trois, et c'est le résultat
inattendu, AUCUNE des deux jambes n'est aussi asymétrique que leur somme, -0,205 et -0,306 contre
-0,570. L'asymétrie naît de la façon dont les deux jambes se combinent, et non d'une des deux.

Ce constat ne reproduit pas celui de Daniel, Hodrick et Lu, chez qui la partie neutre au dollar porte
l'asymétrie. Une quatrième différence s'est ajoutée à l'audit du 2026-09-02, et elle est de notre
fait : le pari sur le dollar n'existe ici que parce que le dollar est classé comme un actif. Un tri
sur les dix seules devises rend une asymétrie de +0,253 sur l'échantillon complet. Trois autres
différences de protocole sont déclarées. Leur portage est construit sur six
portefeuilles triés par taux, le nôtre sur onze actifs pesés par rang. Leur échantillon va de février
1976 à août 2013, le nôtre de février 1971 à juin 2026. Leur univers compte des monnaies émergentes,
pas le nôtre. Le désaccord est **déclaré non résolu**.

### Les figures

`results/figures/equity_carry.png`. **Mode d'emploi.** L'axe vertical est une échelle logarithmique
en dollars des États-Unis, base 1 dollar au 28 février 1971. Trois courbes, le portage, le momentum
et le passif équipondéré. Regarder d'abord l'écart vertical final, puis les décrochements de 2008 et
de 2020, où le portage se sépare du momentum.

`results/figures/underwater_carry.png` et `results/figures/return_histogram.png`. **Mode d'emploi.**
La première montre la distance au sommet précédent, en points de pourcentage, et sert à juger la
DURÉE d'un repli autant que sa profondeur. La seconde superpose la loi normale de même moyenne et de
même écart type, et l'écart à gauche est ce que l'asymétrie de -0,570 chiffre.

`results/figures/qq_plot_carry.png` et `results/figures/rolling_sharpe_carry.png`. **Mode d'emploi.**
La première compare les quantiles observés aux quantiles normaux, et le décrochement de la queue
gauche mesure ce que le ratio de Sharpe ignore. La seconde trace le ratio de Sharpe sur fenêtre
glissante de 120 mois, et la question à lui poser est si la courbe passe DURABLEMENT au-dessus de
zéro plutôt que de commenter un pic.

`results/figures/correlation_heatmap.png` et `results/tables/comparator_correlations.csv`. **Mode
d'emploi.** Corrélations de Pearson sur les 652 mois communs aux quatre séries. Lire d'abord la case
du portage contre le momentum, qui vaut **0,098**, et celle du portage contre le passif, qui vaut
0,369. Le momentum n'est donc pas une couverture au sens de la corrélation, et la section sur les
crises montre où il en devient une.

## La robustesse

### Neuf réglages sur neuf rendent un ratio de Sharpe positif

Source : `results/tables/parameter_sweep.csv`. Échantillon `VALIDATION`, net de deux points de base,
de février 1971 à juin 2026.

| Schéma de pondération | carry | carry1-12 | carry2-13 |
|---|---:|---:|---:|
| Rang | **0,516** | 0,368 | 0,322 |
| Calendrier | 0,257 | 0,221 | 0,241 |
| Tiers extrêmes | 0,472 | 0,398 | 0,359 |

**Comment lire ce tableau, en trois constats.** Un, les neuf cellules sont positives, donc le
résultat ne dépend d'aucun réglage particulier. Deux, le signal brut bat ses deux versions lissées
dans les trois schémas, ce qui contredit l'article pour qui « carry1-12 » ne perd presque rien. Le
lissage retire ici entre 0,02 et 0,19 point de ratio de Sharpe. Trois, la stratégie de calendrier est
la plus faible des trois, et c'est aussi la seule dont l'asymétrie disparaît, de -0,570 à **-0,048**
dans la colonne `skewness` du même fichier.

`results/figures/parameter_heatmap.png` porte les mêmes neuf cellules. **Mode d'emploi.** Une ligne
par schéma de pondération, une colonne par variante de signal, une couleur par ratio de Sharpe net.
Les deux axes y sont rangés par ordre alphabétique et non dans l'ordre du tableau ci-dessus. Chercher
une plage de couleur homogène plutôt qu'une case isolée.

### Le dollar classé comme un actif porte la moitié de la réplication

Source : `results/tables/numeraire_variant.csv`. C'est l'objection la plus forte contre nos chiffres
de tête, et elle vient de notre propre implémentation plutôt que de la littérature.

| Univers | Mois | Exposition nette | Sharpe article | Asymétrie article | Sharpe complet | Asymétrie complète | c article | t article |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Onze actifs, le dollar classé | 664 | **0,136** | **0,602** | **-0,666** | 0,528 | **-0,570** | **1,084** | **2,159** |
| Dix actifs, le dollar numéraire | 629 | 0,000 | **0,488** | **-0,522** | 0,532 | **+0,253** | **0,897** | **1,700** |

**Comment lire ce tableau, en quatre constats.** Un, l'asymétrie de la fenêtre de l'article passe de
-0,666 à -0,522 quand le dollar sort du classement, donc notre contrôle le plus serré doit
l'essentiel de sa précision à un écart avec l'article. Deux, sur l'échantillon complet l'asymétrie
CHANGE DE SIGNE, de -0,570 à +0,253, alors que le ratio de Sharpe ne bouge pas, 0,528 contre 0,532.
L'asymétrie négative du portefeuille complet vient donc du pari sur le dollar et non du tri par
portage. Trois, le coefficient de panel de la fenêtre de l'article tombe de 1,084 à 0,897 et sa
statistique t de 2,159 à 1,700. La parité non couverte des taux n'est donc plus rejetée à 5 % sur
cette fenêtre. Quatre, la série perd 35 mois, de 664 à 629, parce que le dollar comptait dans le
plancher de quatre actifs avant l'entrée de la quatrième devise en décembre 1973.

**Ce que cela ne renverse pas.** Les cinq contrôles de réplication passeraient encore à la tolérance
de 0,50 dans l'univers de dix actifs, l'écart relatif de l'asymétrie valant alors 0,232 et celui du
coefficient 0,177. Le coefficient de panel reste positif et significatif sur l'échantillon complet,
1,075 avec un t de 2,693. Le verdict ne change donc pas, et ce sont les deux quasi-égalités annoncées
en tête qui perdent leur force.

### Rallonger les deux monnaies de financement dégrade le résultat et aggrave l'asymétrie

Source : `results/tables/rate_source_variant.csv`. C'est l'objection la plus forte contre notre
univers, et elle est chiffrée plutôt qu'écartée.

| Source de taux | Premier portage du yen | Premier portage du franc | Sharpe | Asymétrie | c |
|---|---|---|---:|---:|---:|
| Interbancaire à trois mois seul | 2002-04 | 1999-07 | **0,528** | **-0,570** | 1,188 |
| Rallongé par d'autres instruments | 1979-05 | 1972-01 | **0,424** | **-0,894** | 1,062 |

**Comment lire ce tableau, en trois constats.** Un, le yen et le franc suisse sont les deux monnaies
de financement classiques, et notre cas de référence ne les voit qu'à partir de 2002 et de 1999. Deux,
les faire entrer plus tôt fait TOMBER le ratio de Sharpe de 0,528 à 0,424, et rend l'asymétrie
nettement plus négative, de -0,570 à -0,894. Les deux séries de remplacement sont les certificats de
dépôt au Japon et l'argent au jour le jour en Suisse. Trois, le coefficient de panel bouge peu, de
1,188 à 1,062, donc le test central ne dépend pas de ce choix.

Cette variante mélange trois instruments de taux différents, ce qui est une substitution déclarée. Le
cas de référence garde une seule famille d'instruments, et la variante montre dans quel sens il se
trompe. Elle appuie le diagnostic de Bekaert et Panayotov (2020) : le portage du yen porte une part
importante de l'asymétrie du portefeuille.

### Le délai d'exécution érode lentement

Source : `results/tables/execution_delay.csv`. Portage brut de frais, échantillon complet.

| Délai | N | Rendement %/an | Sharpe |
|---|---:|---:|---:|
| 1 mois, cas de référence | 664 | 3,87 | 0,528 |
| 2 mois | 663 | 3,54 | 0,495 |
| 3 mois | 662 | 3,04 | 0,426 |

**Comment lire ce tableau, en trois constats.** Un, deux mois de retard ne retirent que 0,03 point de
ratio de Sharpe, donc le signal ne vit pas dans la microstructure. Deux, la décroissance reste
régulière à trois mois, ce qui est cohérent avec un écart de taux qui bouge lentement. Trois, cette
lenteur est aussi ce qui rend la stratégie peu coûteuse, et la section suivante le chiffre.

### Les quatre sous-périodes sont positives

Source : `results/tables/subperiods.csv`, portage net de deux points de base.

| Sous-période | N | Sharpe | t |
|---|---:|---:|---:|
| 1971-02 à 1985-11 | 178 | 0,536 | 1,71 |
| 1985-12 à 1999-11 | 168 | **0,744** | 2,52 |
| 1999-12 à 2012-08 | 153 | 0,530 | 1,42 |
| 2012-09 à 2026-06 | 165 | **0,149** | 0,64 |

**Comment lire ce tableau, en trois constats.** Un, les quatre sont positives, ce qui donne la part
de 1,00 comparée au seuil de 0,60 dans le verdict. Deux, une seule atteint une statistique t
supérieure à deux, celle de 1985 à 1999. Trois, la dernière tranche, qui est aussi la période
postérieure à l'article, vaut le tiers des trois autres.

`results/figures/subperiod_bars.png`. **Mode d'emploi.** Une barre par sous-période, la moustache
étant l'intervalle à 95 % construit sur l'erreur type de Lo. Vérifier que chaque moustache traverse
zéro avant de commenter la hauteur d'une barre. Ici trois des quatre la traversent.

### Le risque de queue, contre un momentum de même volatilité

Source : `results/tables/tail_risk.csv`. Le momentum est multiplié par 0,904 pour porter exactement
la volatilité du portage. Ce facteur est calculé sur les 664 mois, donc il n'était pas connu
d'avance, et c'est un écart déclaré. L'asymétrie et l'aplatissement n'en dépendent pas, la perte
espérée si.

| Série | %/an | Sharpe | Asymétrie | Aplatissement | Perte espérée à 5 % | Pire mois % | Pire repli % |
|---|---:|---:|---:|---:|---:|---:|---:|
| Portage | 3,87 | **0,528** | **-0,570** | 3,28 | 4,94 | **-11,17** | -27,87 |
| Momentum à volatilité égale | 1,07 | 0,146 | -0,250 | 2,85 | **5,02** | -10,23 | **-31,63** |
| Passif équipondéré | 0,68 | 0,092 | -0,092 | 0,85 | 4,69 | -9,04 | -44,08 |

**Comment lire ce tableau, en trois constats.** Un, le contraste annoncé par l'article existe sur
l'asymétrie, -0,570 contre -0,250, et le portage rapporte 3,6 fois plus pour la même volatilité.
Deux, il n'existe PAS sur la perte espérée au-delà de la valeur à risque, 4,94 pour le portage contre
5,02 pour le momentum, ni sur le pire repli, -27,87 contre -31,63. Le rapport de la perte espérée à
la volatilité, qui ne dépend d'aucune mise à l'échelle, dit la même chose, 2,333 contre 2,373. Les
deux quotients se calculent depuis la ligne du momentum de `results/tables/replication_table2.csv`,
qui porte la volatilité NON mise à l'échelle. Trois, la conclusion est donc que
l'asymétrie du portage se joue sur des mois isolés, son pire mois valant -11,17 %, et non sur des
séquences longues où le momentum fait pire.

Ce résultat nuance l'article sans le contredire. L'article mesure l'asymétrie et l'aplatissement, ce
que nous retrouvons. Il ne compare pas sa stratégie à un momentum de même volatilité sur la perte
espérée, et c'est cette comparaison qui manque au récit du portage comme prime de risque de krach.

## Les coûts

La stratégie change de rang lentement, donc les coûts ne décident pas. Source :
`results/tables/costs.csv`. Rotation mesurée en convention de somme entière contre les poids dérivés.

| Coût unitaire | Rotation par an | Brut %/an | Net %/an | Sharpe net | Coût qui annule |
|---|---:|---:|---:|---:|---:|
| 0 point de base | 4,28 | 3,87 | 3,87 | 0,528 | **90,3 pb** |
| 1 point de base | 4,28 | 3,87 | 3,82 | 0,522 | 90,3 pb |
| 2 points de base, cas de référence | 4,28 | 3,87 | 3,78 | **0,516** | 90,3 pb |
| 5 points de base | 4,28 | 3,87 | 3,65 | 0,498 | 90,3 pb |
| 10 points de base | 4,28 | 3,87 | 3,44 | 0,469 | 90,3 pb |

**Comment lire ce tableau, en trois constats.** Un, il faudrait un demi-écart de 90,3 points de base
pour annuler le rendement brut, contre les 2 points retenus comme cas de référence, soit 45 fois
plus. Deux, la rotation de 4,28 par an correspond à une durée de détention de 0,234 année, soit 2,8
mois, ce que la colonne `holding_period_years` du même fichier donne. Trois, ce résultat est cohérent
avec le tableau 9 de l'article, où cinq demi-écarts font passer le Sharpe des devises de 0,68 à 0,63.

Le multiple de coût survécu vaut 10, le plus grand testé
(`results/tables/cost_multiples.csv`) : à dix fois le coût de référence, le ratio de Sharpe net vaut
encore 0,410.

`results/figures/cost_sensitivity.png`. **Mode d'emploi.** L'axe horizontal porte le multiple
appliqué aux deux points de base, l'axe vertical le ratio de Sharpe net, et la ligne horizontale
marque zéro. Chercher l'abscisse où la courbe croise zéro : ici elle ne la croise pas dans la plage
testée.

## Le hors échantillon

### La prédiction disparaît après septembre 2012

C'est le résultat central de l'étude, et il ne porte pas sur le rendement mais sur le test de
l'article. Source : `results/tables/panel_regression.csv`, dernière ligne.

Sur 1 782 couples de devise et de mois, d'octobre 2012 à juin 2026, le coefficient de l'équation (23)
vaut **0,303** avec une erreur type de 1,031, donc une statistique t de **0,294**. Il valait 1,084
avec un t de 2,159 sur la fenêtre de l'article. La parité non couverte des taux, qui prédit un
coefficient nul, n'est plus rejetée. Le R² tombe de 0,005 à 0,0001.

### Le rendement se maintient, mais faiblement

Le portefeuille net de deux points de base rend un ratio de Sharpe de **0,144** sur 164 mois,
échantillon `FINAL_HOLDOUT` (`results/metrics.json`). Le rendement annualisé vaut **0,82 %**
(`results/tables/bootstrap.csv`).

Le rééchantillonnage par blocs CIRCULAIRES de douze mois, 2 000 tirages, graine 20260902, place ce
rendement entre **-1,28 %** et **+2,75 %** à 90 %, et 74,25 % des tirages sont positifs.
L'intervalle contient zéro, donc la période postérieure à l'article ne permet de rejeter ni la
présence ni l'absence de prime. Les blocs sont circulaires depuis l'audit du 2026-09-02. Des blocs
tronqués à la fin de l'échantillon donnaient au premier mois 8,3 % du poids des autres, et rendaient
46 % des tirages plus courts que les 164 mois d'origine.

### Les contrôles de surapprentissage

| Contrôle | Valeur mesurée | Fichier |
|---|---:|---|
| Nombre d'essais comptés | 33 | `trials.csv` |
| Essais dont la mesure est un ratio de Sharpe | 29 | `deflated_sharpe.csv` |
| Variance des ratios de Sharpe essayés | 0,0118 | `deflated_sharpe.csv` |
| Probabilité de surapprentissage | **0,100** | `metrics.json` |
| Sharpe moyen des 7 chemins de validation croisée | **0,448** | `cpcv_distribution.csv` |
| Chemins de validation croisée réellement distincts | **3 sur 7** | `cpcv_distribution.csv` |
| Part de chemins négatifs | 0,000 | `cpcv_distribution.csv` |
| Maximum attendu sous l'hypothèse nulle | 0,230 | `deflated_sharpe.csv` |
| Ratio de Sharpe dégonflé | **0,149** | `deflated_sharpe.csv` |
| t exigé par Bonferroni sur 33 essais | 3,17 | `deflated_sharpe.csv` |
| t observé hors échantillon | 0,615 | `deflated_sharpe.csv` |
| t après rabais de Harvey et Liu | 0,000 | `deflated_sharpe.csv` |

**Comment lire ce tableau, en quatre constats.** Un, la validation croisée combinatoire purgée juge
le PROCESSUS de sélection : sur chaque bloc d'apprentissage, la meilleure des neuf configurations est
retenue, puis évaluée sur le bloc de test suivant. Les sept chemins ainsi reconstruits sont tous
positifs, entre 0,434 et 0,506, donc choisir la meilleure configuration sur le passé n'a jamais
détruit le résultat. Deux, ces sept chemins ne portent que TROIS valeurs distinctes, parce que le
tri par rang sur signal brut est retenu dans presque tous les blocs. L'écart type de 0,025 se lit
donc comme une dispersion de trois chemins, pas de sept. Trois, la probabilité de surapprentissage
vaut 0,100, sous le seuil de 0,50, ce qui dit la même chose autrement. Quatre, le ratio de Sharpe
dégonflé vaut 0,149 parce que le maximum attendu sous l'hypothèse nulle, 0,230, dépasse le Sharpe
observé de 0,144 sur les 164 mois postérieurs à l'article.

**La correction pour tests multiples ne laisse survivre que deux configurations sur neuf.** Source :
`results/tables/multiple_testing.csv`, correction de Holm sur les neuf statistiques t du balayage,
échantillon complet net de frais.

| Configuration | t | Valeur p ajustée | Rejeté à 5 % |
|---|---:|---:|---|
| Rang, signal brut | 3,416 | **0,0057** | oui |
| Tiers extrêmes, signal brut | 3,168 | **0,0123** | oui |
| Tiers extrêmes, carry1-12 | 2,582 | 0,0687 | non |
| Rang, carry1-12 | 2,373 | 0,1058 | non |
| Tiers extrêmes, carry2-13 | 2,372 | 0,1058 | non |
| Rang, carry2-13 | 2,071 | 0,1535 | non |
| Calendrier, signal brut | 1,825 | 0,2042 | non |
| Calendrier, carry2-13 | 1,732 | 0,2042 | non |
| Calendrier, carry1-12 | 1,567 | 0,2042 | non |

**Comment lire ce tableau, en trois constats.** Un, les deux configurations qui survivent emploient
toutes deux le signal BRUT, sans lissage. Deux, les trois variantes de calendrier sont les trois
dernières, ce qui rejoint le tableau 6 de l'article où le calendrier fait moins bien que le tri. Trois,
la correction porte sur l'échantillon complet, pas sur le hors échantillon, où aucune configuration
n'atteindrait le seuil.

### La substitution obligataire ne reproduit pas la pente de l'article

Source : `results/tables/bond_slope_substitution.csv`. Échantillon complet, brut de frais, onze
marchés.

| Grandeur | Mesurée | Publiée |
|---|---:|---:|
| Ratio de Sharpe | **0,336** | 1,03 |
| Asymétrie | **+1,740** | 0,33 |
| Aplatissement en excès | 25,65 | 4,92 |
| Coefficient c | 1,353 | 0,81 |
| Statistique t de c | 3,120 | 4,91 |

**Comment lire ce tableau, en trois constats.** Un, le portage est ici la seule PENTE, et la descente
de courbe de l'équation (13) est omise faute d'une courbe zéro-coupon gratuite pour dix marchés. Deux,
le ratio de Sharpe manque le tiers du chiffre publié, et l'asymétrie change de signe et d'ordre de
grandeur, donc cette ligne n'est PAS une réplication et ne compte dans aucun contrôle du verdict.
Trois, ce que la substitution conserve est le coefficient de panel, 1,353 avec un t de 3,120, donc la
pente prédit bien le rendement obligataire même mal mesurée.

L'écart d'asymétrie a une cause identifiable et non vérifiée ici. Notre rendement obligataire est
approché par la duration modifiée appliquée à la variation du taux long, ce qui ignore la convexité.
Une approximation linéaire d'une relation convexe surestime les pertes quand les taux montent, donc
elle déforme la queue.

## Les limites

**Trois classes d'actifs sur quatre manquent.** Le facteur mondial de portage, qui porte le résultat
principal de l'article avec un ratio de Sharpe de 1,20, n'est pas calculable. Statut : **non trouvé
au 2026-09-02**, sources consultées listées dans `results/tables/asset_classes_not_reproducible.csv`.

**Le portage de change vient d'un écart de taux, pas de points de report.** La parité couverte des
taux s'est écartée après 2008, et cet écart n'est pas mesuré ici. L'effet sur le portage est du
second ordre pour les monnaies du G10, mais il n'est pas nul, et il n'est pas quantifié.

**L'intérêt sur le collatéral n'est pas modélisé séparément.** C'est la première objection de
Collin-Dufresne (2012). Notre rendement en excès retranche déjà le taux local sur la totalité de la
position, ce qui suppose une position entièrement collatéralisée. Un investisseur qui immobilise
moins de capital verrait un portage plus grand, et la comparaison entre classes en dépendrait.

**Le yen et le franc suisse n'entrent qu'en 2002 et en 1999 dans le cas de référence.** La variante
qui les rallonge mesure ce que ce choix coûte, 0,10 point de ratio de Sharpe et 0,32 point
d'asymétrie, mais elle mélange trois instruments de taux différents.

**Trois cellules sur 5 376 portent un poids non nul sans rendement.** Elles sont traitées comme un
rendement nul, ce que la clé `data_quality` de `results/metrics.json` publie. La part est de 0,06 %,
donc l'effet est négligeable, et il est déclaré plutôt que silencieux.

**L'univers de dix monnaies porte un biais de survie.** Ce sont les monnaies qui existent en 2026.
Les monnaies européennes remplacées par l'euro en 1999 n'y sont pas, alors que le mark et le franc
français étaient des jambes de portage courantes avant cette date.

**La couronne danoise et l'euro sont presque le même actif depuis 1999.** Le Danemark tient une
parité étroite avec l'euro, donc deux des onze colonnes sont fortement redondantes sur le dernier
quart de l'échantillon. L'article inclut lui aussi les deux, mais avec dix-huit autres monnaies pour
diluer la redondance.

**Le demi-écart de deux points de base est un PRÉCEPTE, pas une mesure.** Aucune série publique ne
donne les fourchettes acheteur-vendeur du change au comptant sur cinquante-cinq ans. Le seuil de
rentabilité de 90,3 points de base rend cette hypothèse peu déterminante.

**Le compte de 33 essais couvre les évaluations de performance et les quatre spécifications de
panel.** Deux essais restent hors du compte et sont nommés ici. La comparaison des trois séries dans
les cinq fenêtres de crise ne sélectionne aucune stratégie. La décomposition en deux jambes est un
diagnostic rétrospectif, et elle est pourtant comptée, ce qui est le choix prudent.

**La variance des essais ne porte que sur les 29 dont la mesure est un ratio de Sharpe.** La colonne
`n_sharpe_valued_trials` de `results/tables/deflated_sharpe.csv` le publie, à côté des 33 essais
comptés. Les quatre spécifications de panel comptent comme essais, et leur mesure est une statistique
t. Les mélanger à des ratios de Sharpe multipliait la variance par 62 et poussait le ratio de Sharpe
dégonflé à 6,8e-91. Ce dernier chiffre vient de l'audit du 2026-09-02 et ne se trouve dans aucun
fichier de `results/`, la version corrigée l'ayant remplacé.

**La comparaison au momentum emploie une volatilité de PLEIN échantillon.** Le facteur de 0,904 est
calculé sur les 664 mois, donc aucun investisseur ne l'aurait connu d'avance. L'asymétrie et
l'aplatissement n'en dépendent pas, la perte espérée si. Le rapport de la perte espérée à la
volatilité, lui, s'en affranchit : 2,333 pour le portage contre 2,373 pour le momentum, calculés
depuis `results/tables/replication_table2.csv`. La conclusion tient.

**Les sept chemins de validation croisée ne portent que trois valeurs distinctes.** Le processus de
sélection retient presque toujours la même configuration, donc les chemins se répètent. La dispersion
publiée est celle de trois séries, et l'écart type de 0,025 se lit avec cette réserve.

**Le désaccord avec Daniel, Hodrick et Lu sur la jambe neutre au dollar n'est pas résolu.** Quatre
différences de protocole sont déclarées dans la section « Les résultats », et une seule a été isolée,
celle du dollar classé comme un actif.

**Le dollar classé comme un actif porte l'asymétrie de l'échantillon complet.** Un tri sur les dix
seules devises rend une asymétrie de +0,253 au lieu de -0,570, pour un ratio de Sharpe inchangé.
C'est la limite la plus lourde de l'étude, et le tableau `numeraire_variant.csv` la chiffre.

**Aucun résultat ne porte sur l'avenir.** Tous les chiffres sont mesurés sur des périodes nommées.

## Le verdict

**`REPLICATED`**, déduit par `quantlab.reporting.study.decide_verdict` depuis les seuils écrits dans
`config.yaml` avant que les résultats existent. Voici les dix critères, avec la valeur mesurée en
face du seuil.

| Critère | Mesuré | Seuil | Résultat |
|---|---:|---:|---|
| Signe économique attendu | c positif et Sharpe positif | positif | RÉUSSI |
| Signe du Sharpe hors échantillon | 0,144 | rejet à 0 ou moins | RÉUSSI |
| Réplication, 5 contrôles chiffrés | 5 sur 5 dans la tolérance | tous exigés | RÉUSSI |
| Sharpe hors échantillon | **0,144** | minimum 0,50 | **ÉCHOUÉ** |
| t après correction pour essais multiples | **0,000** | minimum 3,00 | **ÉCHOUÉ** |
| Ratio de Sharpe dégonflé | **0,149** | minimum 0,95 | **ÉCHOUÉ** |
| Probabilité de surapprentissage | 0,100 | maximum 0,50 | RÉUSSI |
| Part de sous-périodes positives | 1,000 | minimum 0,60 | RÉUSSI |
| Multiple de coûts survécu | 10,000 | minimum 2,00 | RÉUSSI |
| Corrélation absolue avec le portefeuille détenu | 0,370 | maximum 0,60 | RÉUSSI |

**Comment lire ce tableau, en trois constats.** Un, le verdict s'arrête à `REPLICATED` et n'atteint
pas `ROBUST` parce que trois des six contrôles de robustesse échouent, et les trois portent sur la
même chose : ce que la stratégie a fait APRÈS la fin de l'échantillon de l'article. Deux, les cinq
contrôles de réplication passent, donc le rejet ne porte pas sur la fidélité de notre implémentation.
Trois, la corrélation avec le passif équipondéré vaut 0,370, sous le seuil, donc le portage apporterait
bien de la diversification si sa performance hors échantillon se tenait.

**Un seul seuil est plus large que celui du laboratoire, et il est déclaré.** La tolérance de
réplication vaut 0,50 dans `config.yaml` contre 0,10 par défaut dans `quantlab.reporting.study`. La
raison est écrite dans le fichier. Notre univers compte dix monnaies développées contre vingt monnaies
dont des émergentes. Notre portage vient d'un écart de taux et non de points de report, et notre
échantillon déborde des deux côtés du sien.
Trois des cinq contrôles passeraient au seuil par défaut, ceux de l'asymétrie
à 0,020, du coefficient c à 0,005 et de la volatilité à 0,072. Les deux autres ne passeraient pas, le
ratio de Sharpe à 0,115 et la statistique t à 0,197. Les sept autres seuils sont exactement ceux du
laboratoire.

**Ce que l'étude établit, en quatre phrases.** Le portage de change de Koijen, Moskowitz, Pedersen
et Vrugt se reproduit sur données gratuites, coefficient de panel et asymétrie compris, alors que
trois de ses quatre classes d'actifs ne se reproduisent pas du tout. Le test central de l'article
s'éteint après sa date de fin, le coefficient passant de 1,084 avec un t de 2,159 à 0,303 avec un t
de 0,294. Le récit de l'asymétrie survit sur l'asymétrie elle-même et pas sur la perte espérée, où un
momentum de même volatilité fait légèrement pire. Mais l'asymétrie de l'échantillon complet tient
entièrement au dollar classé comme un actif, écart avec l'article que la section « La robustesse »
chiffre à 0,823 point d'asymétrie.

**La prochaine décision.** Le momentum de change gagne dans quatre des cinq épisodes de tension où le
portage perd, et sa corrélation au portage vaut 0,098 sur 652 mois
(`results/tables/comparator_correlations.csv`). C'est le mélange des deux qu'il faut mesurer ensuite,
comme l'étude 003 le fait pour valeur et momentum.

## Reproduire

```bash
export QUANTLAB_USER_AGENT="votre nom votre courriel"
uv run python studies/008_carry/run.py
uv run pytest tests/unit/test_strategies_carry.py -o addopts="" -q
```

L'exécution télécharge 34 séries de FRED, met les réponses brutes en cache dans la couche `raw` du
lac, et réécrit l'ensemble de `results/`. Deux exécutions consécutives rendent des tableaux
identiques au fichier près, seul l'identifiant d'expérience changeant, ce qui a été vérifié le
2026-09-02 par comparaison des répertoires. Les 49 tests du module passent, et six mutations
volontaires ont été rejouées pour vérifier qu'ils attrapent le défaut qu'ils prétendent garder.

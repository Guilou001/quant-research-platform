# Acheter les gagnants, vendre les perdants

| | |
|---|---|
| **Auteurs** | Narasimhan Jegadeesh, Sheridan Titman |
| **Année** | 1993 |
| **Revue ou source** | *The Journal of Finance*, vol. XLVIII, n° 1, mars 1993, pages 65 à 91 |
| **Lien** | [doi:10.1111/j.1540-6261.1993.tb04702.x](https://doi.org/10.1111/j.1540-6261.1993.tb04702.x) ; fac-similé consulté le 2026-09-01 : [bauer.uh.edu](https://www.bauer.uh.edu/rsusmel/phd/jegadeesh-titman93.pdf) ; [JSTOR 2328882](https://www.jstor.org/stable/2328882) |
| **Statut de réplication** | non commencé |

Article consulté intégralement le 2026-09-01, sur le fac-similé JSTOR de la version
publiée, 28 pages. Tous les chiffres ci-dessous en sont extraits, sauf mention
contraire, et portent le statut **rapporté**.

## La question de recherche

Les stratégies qui achètent les titres montés et vendent les titres descendus sur
trois à douze mois rapportent-elles, et cela contredit-il l'efficience du marché ?
L'article répond oui aux deux questions, sur les actions du NYSE et de l'AMEX de
1965 à 1989.

La question naît d'une contradiction entre deux résultats vrais. De Bondt et Thaler
(1985) montrent qu'à trois à cinq ans les perdants battent les gagnants, ce qui
plaide pour la surréaction. Jegadeesh (1990) et Lehmann (1990) trouvent le même
renversement à une semaine et à un mois. Entre les deux horizons, rien n'est
mesuré. Or c'est précisément là que travaillent les praticiens. L'article cite les
classements Value Line, dont l'un des éléments est un facteur de momentum calculé sur
les rendements passés de trois à douze mois (note 3).

L'article ferme ce trou. Il ne se contente pas de mesurer le gain, il le décompose
pour dire si sa source est une prime de risque ou une erreur de prix.

## L'intuition économique

Le rendement devrait exister parce que le prix intègre trop lentement l'information
propre à l'entreprise. Une nouvelle spécifique ne se reflète pas d'un coup dans le
cours, l'ajustement s'étale sur plusieurs mois, et le titre continue donc de monter
après la nouvelle qui l'a fait monter.

Le mécanisme est une sous-réaction, c'est-à-dire un ajustement du prix plus lent que
l'arrivée de l'information. Il se distingue de trois explications concurrentes, et
l'article les élimine une à une.

La première explication concurrente est la dispersion transversale des rendements
espérés. Si certains titres ont durablement une espérance de rendement plus élevée,
ils sortent souvent gagnants du classement passé et rapportent ensuite davantage,
sans aucune inefficience. Cette dispersion est le premier terme de la décomposition
donnée plus bas, et elle correspondrait à une prime de risque. Les auteurs la
rejettent en mesurant les bêtas : le décile perdant a un bêta de 1,36 et le décile
gagnant de 1,28, donc le portefeuille à coût nul porte un bêta **négatif** de -0,08.
La stratégie gagne en portant moins de risque de marché, pas plus.

La deuxième est la synchronisation du facteur commun. Si le rendement du facteur
était autocorrélé positivement, la stratégie choisirait des titres à bêta élevé
juste avant les hausses du facteur. Les auteurs mesurent l'autocovariance des
rendements semestriels de l'indice équipondéré à -0,0028, donc négative : ce terme
retranche du gain au lieu d'y ajouter.

La troisième est l'effet de retard de Lo et MacKinlay (1990), où certains titres
réagissent au facteur commun avec un décalage. L'article construit un modèle à
sensibilité contemporaine et retardée pour la tester. Si le retard portait les profits,
ceux-ci monteraient avec le rendement du marché au carré du semestre précédent. La
pente mesurée est de -2,29, avec un t de -1,74, et elle reste négative dans les deux
demi-échantillons, -2,55 et -1,83 (page 75). Le signe est donc l'inverse de celui que
l'explication exige.

Reste l'autocovariance des composantes propres à chaque titre, mesurée en moyenne à
+0,0012, qui est la signature de la sous-réaction.

Ce qui ferait disparaître ce rendement est écrit dans l'article lui-même : le gain
se dissipe. Le portefeuille formé sur six mois cumule 9,51 % au douzième mois qui
suit, puis retombe à 5,56 % au vingt-quatrième et à 4,06 % au trente-sixième. Une
prime de risque ne se rend pas ; une erreur de prix se corrige. Trois autres forces peuvent l'annuler en pratique, et la littérature critique citée
plus bas s'en occupe. Ce sont les coûts de transaction, la capacité limitée du marché
à absorber la stratégie, et l'encombrement une fois le résultat publié.

## Les données

Le fichier des rendements quotidiens du CRSP, dans la version disponible au moment
de l'étude, qui couvre juillet 1962 à décembre 1989. Les rendements mensuels sont
obtenus en **composant les rendements quotidiens**, et non en lisant le fichier
mensuel du CRSP.

La période d'analyse est janvier 1965 à décembre 1989, soit 300 mois. Le début est
contraint par la stratégie la plus gourmande : la combinaison 12 mois de formation
et 12 mois de détention exige 23 mois de rendements retardés.

Deux périodes supplémentaires servent au contre-test : 1927-1940 et 1941-1964.

La section sur les annonces de résultats utilise une seconde source, la base
trimestrielle industrielle COMPUSTAT, d'où viennent les dates d'annonce. Elle porte sur
janvier 1980 à décembre 1989, la période couverte par la version 1990 de ce fichier, et
compte en moyenne 429,2 annonces trimestrielles par mois appariées à des rendements.

## L'univers

Toutes les actions du NYSE et de l'AMEX disposant de rendements sur les J mois qui
précèdent la date de formation. L'article n'applique ni filtre de prix, ni filtre de
capitalisation, ni exclusion des microcapitalisations.

Le nombre de titres retenus, par mois ou en moyenne, **n'est pas publié dans
l'article** : non trouvé au 2026-09-01.

Deux découpages servent aux tests de robustesse. Trois sous-échantillons de taille,
notés S1 pour les plus petites capitalisations, S2 pour les moyennes et S3 pour les
plus grandes. Trois sous-échantillons de bêta ex ante, construits de la même façon.

## La méthodologie

Seize combinaisons de périodes, doublées par le traitement du décalage, soit 32
stratégies. La période de formation J et la période de détention K prennent chacune
les valeurs 3, 6, 9 et 12 mois. Le panneau A forme le portefeuille immédiatement
après la mesure des rendements passés ; le panneau B attend **une semaine**.

Le classement se fait en ordre **croissant** des rendements des J derniers mois,
puis dix portefeuilles déciles équipondérés sont formés. Le décile de plus faible
rendement passé est le portefeuille vendu, celui de plus fort rendement passé est le
portefeuille acheté. Le portefeuille à coût nul est la différence des deux.

Les cohortes se chevauchent, pour augmenter la puissance des tests. Au mois t, la
stratégie détient les portefeuilles constitués au mois t, au mois t-1, et ainsi de
suite jusqu'à t-K+1. Elle solde celui qui avait été ouvert au mois t-K. Une fraction
\(1/K\) des positions est donc renouvelée chaque mois.

Deux conventions de détention ont été calculées. La première achète et conserve, la
seconde rééquilibre chaque mois vers l'équipondération. Les résultats étant très
proches, et l'achat et conservation donnant un rendement légèrement supérieur, seuls
les rendements rééquilibrés sont publiés.

**Deux pièges de nommage, à retenir avant d'écrire une ligne de code.** Premièrement, dans l'article de 1993, P1 désigne le décile de plus **faible**
rendement passé, donc les perdants, et P10 les gagnants. Dans Jegadeesh et Titman
(2001), la convention est **inversée**, et P1 y désigne les gagnants. Deuxièmement, le décalage du
panneau B est d'**une semaine**, pas d'un mois. La convention dite « 12 moins 1 »,
qui saute le mois le plus récent, appartient à la littérature postérieure et ne
figure nulle part dans cet article.

## Les équations qui comptent

Le modèle à un facteur qui sert de cadre à la décomposition :

\[ r_{it} = \mu_i + b_i f_t + e_{it} \]

où \(\mu_i\) est le rendement espéré inconditionnel du titre i et \(f_t\) le rendement
inattendu d'un portefeuille imitant le facteur. Le terme \(b_i\) est la sensibilité du
titre au facteur, et \(e_{it}\) la composante propre à l'entreprise. Pour la stratégie 6 mois
sur 6 mois étudiée en détail, une période vaut six mois.

La stratégie analytique associée, dite stratégie de force relative pondérée, pèse
chaque titre par son rendement passé diminué du rendement de l'indice équipondéré.
Son profit espéré est la covariance transversale suivante :

\[ E\left[(r_{it} - \bar{r}_t)(r_{i,t-1} - \bar{r}_{t-1})\right] > 0 \]

Cette stratégie pondérée rapporte 4,5 % par dollar investi à l'achat, sur six mois,
avec un t de Student de 2,99, et sa corrélation avec la stratégie par déciles est de
0,95. C'est ce qui autorise à raisonner sur elle et à conclure sur l'autre.

La décomposition en trois sources, qui est le cœur de l'article :

\[ E\left[(r_{it} - \bar{r}_t)(r_{i,t-1} - \bar{r}_{t-1})\right]
   = \sigma_\mu^2 + \sigma_b^2\,\mathrm{Cov}(f_t, f_{t-1})
   + \overline{\mathrm{Cov}_i(e_{it}, e_{i,t-1})} \]

où \(\sigma_\mu^2\) et \(\sigma_b^2\) sont les variances transversales des
rendements espérés et des sensibilités au facteur. Le premier terme est la
dispersion des rendements espérés, le deuxième la synchronisation du facteur, le
troisième la covariance sérielle moyenne des composantes propres. Les deux premiers
sont compatibles avec une rémunération du risque ; seul le troisième signale une
inefficience.

L'autocovariance de l'indice équipondéré, qui permet de signer le deuxième terme :

\[ \mathrm{Cov}(\bar{r}_t, \bar{r}_{t-1}) = \bar{b}^2\,\mathrm{Cov}(f_t, f_{t-1}) \]

Le modèle de retard, qui teste l'explication de Lo et MacKinlay :

\[ r_{it} = \mu_i + b_{1i} f_t + b_{2i} f_{t-1} + e_{it} \]

où \(b_{2i} > 0\) signifie que le titre réagit au facteur avec un retard, et
\(b_{2i} < 0\) qu'il surréagit puis se corrige. Le profit de la stratégie pondérée
devient alors \(\sigma_\mu^2 + \delta \sigma_f^2\), avec
\(\delta = \frac{1}{N}\sum_i (b_{1i} - \bar{b}_1)(b_{2i} - \bar{b}_2)\), et
l'autocovariance de l'indice devient :

\[ \mathrm{Cov}(\bar{r}_t, \bar{r}_{t-1}) = \bar{b}_1 \bar{b}_2 \sigma_f^2 \]

Le paramètre \(\bar{b}_2\) signe l'autocorrélation de l'indice mais n'affecte pas le
profit de la stratégie ; c'est \(\delta\) qui décide. Le profit conditionnel au
rendement passé du facteur vaut \(\sigma_\mu^2 + \delta f_{t-1}^2\), donc au rendement
du facteur **au carré**. C'est cette forme qui donne le test de la page 75, décrit plus
haut, et l'exposant 2 est celui qu'exige le texte de l'article ainsi que la cohérence
avec \(E[f^2] = \sigma_f^2\) dans l'expression précédente.

Les expressions du profit dans le modèle de retard sont transcrites depuis un fac-
similé océrisé, où plusieurs symboles sont dégradés. Leur structure est sûre, et les
exposants ont été recoupés avec le texte, mais la graphie exacte des indices est
**à vérifier** sur un exemplaire propre avant implémentation.

## Les résultats originaux

Les 32 stratégies rapportent toutes un profit positif. Une seule n'est pas
significative, la stratégie 3 mois sur 3 mois sans décalage.

**Panneau A, sans décalage. Rendements mensuels moyens, t de Student entre
parenthèses. J en lignes, K en colonnes.**

| J | Portefeuille | K = 3 | K = 6 | K = 9 | K = 12 |
|---|---|---|---|---|---|
| 3 | vente | 0,0108 (2,16) | 0,0091 (1,87) | 0,0092 (1,92) | 0,0087 (1,87) |
| 3 | achat | 0,0140 (3,57) | 0,0149 (3,78) | 0,0152 (3,83) | 0,0156 (3,89) |
| 3 | achat moins vente | 0,0032 (1,10) | 0,0058 (2,29) | 0,0061 (2,69) | 0,0069 (3,53) |
| 6 | vente | 0,0087 (1,67) | 0,0079 (1,56) | 0,0072 (1,48) | 0,0080 (1,66) |
| 6 | achat | 0,0171 (4,28) | 0,0174 (4,33) | 0,0174 (4,31) | 0,0166 (4,13) |
| 6 | achat moins vente | 0,0084 (2,44) | 0,0095 (3,07) | 0,0102 (3,76) | 0,0086 (3,36) |
| 9 | vente | 0,0077 (1,47) | 0,0065 (1,29) | 0,0071 (1,43) | 0,0082 (1,66) |
| 9 | achat | 0,0186 (4,56) | 0,0186 (4,53) | 0,0176 (4,30) | 0,0164 (4,03) |
| 9 | achat moins vente | 0,0109 (3,03) | 0,0121 (3,78) | 0,0105 (3,47) | 0,0082 (2,89) |
| 12 | vente | 0,0060 (1,17) | 0,0065 (1,29) | 0,0075 (1,48) | 0,0087 (1,74) |
| 12 | achat | 0,0192 (4,63) | 0,0179 (4,36) | 0,0168 (4,10) | 0,0155 (3,81) |
| 12 | achat moins vente | 0,0131 (3,74) | 0,0114 (3,40) | 0,0093 (2,95) | 0,0068 (2,25) |

**Panneau B, décalage d'une semaine entre la mesure et la formation.**

| J | Portefeuille | K = 3 | K = 6 | K = 9 | K = 12 |
|---|---|---|---|---|---|
| 3 | vente | 0,0083 (1,67) | 0,0079 (1,64) | 0,0084 (1,77) | 0,0083 (1,79) |
| 3 | achat | 0,0156 (3,95) | 0,0158 (3,98) | 0,0158 (3,96) | 0,0160 (3,98) |
| 3 | achat moins vente | 0,0073 (2,61) | 0,0078 (3,16) | 0,0074 (3,36) | 0,0077 (4,00) |
| 6 | vente | 0,0066 (1,28) | 0,0068 (1,35) | 0,0067 (1,38) | 0,0076 (1,58) |
| 6 | achat | 0,0179 (4,47) | 0,0178 (4,41) | 0,0175 (4,32) | 0,0166 (4,13) |
| 6 | achat moins vente | 0,0114 (3,37) | 0,0110 (3,61) | 0,0108 (4,01) | 0,0090 (3,54) |
| 9 | vente | 0,0058 (1,13) | 0,0058 (1,15) | 0,0066 (1,34) | 0,0078 (1,59) |
| 9 | achat | 0,0193 (4,72) | 0,0188 (4,56) | 0,0176 (4,30) | 0,0164 (4,04) |
| 9 | achat moins vente | 0,0135 (3,85) | 0,0130 (4,09) | 0,0109 (3,67) | 0,0085 (3,04) |
| 12 | vente | 0,0048 (0,93) | 0,0058 (1,15) | 0,0070 (1,40) | 0,0085 (1,71) |
| 12 | achat | 0,0196 (4,73) | 0,0179 (4,36) | 0,0167 (4,09) | 0,0154 (3,79) |
| 12 | achat moins vente | 0,0149 (4,28) | 0,0121 (3,65) | 0,0096 (3,09) | 0,0069 (2,31) |

**La meilleure stratégie est 12 mois de formation sur 3 mois de détention.** Elle
rapporte 1,31 % par mois sans décalage et 1,49 % par mois avec le décalage d'une
semaine, ce dernier chiffre portant le t le plus élevé de la table, 4,28. La
probabilité d'obtenir un t aussi grand sur 32 tests est inférieure à 0,0006 par
l'inégalité de Bonferroni, une borne sur la probabilité d'un t extrême quand
plusieurs tests ne sont pas indépendants.

La stratégie dite « 12 moins 1 », qui saute le mois le plus récent, n'existe pas dans
cet article. La grille ne saute jamais un mois, et le seul décalage testé est d'une
semaine. Le chiffre le plus proche est donc 1,49 % par mois, t de 4,28, pour la
formation à 12 mois et la détention à 3 mois avec décalage hebdomadaire.

**La stratégie 6 sur 6**, celle que l'article analyse en détail, rapporte 0,95 % par
mois sans décalage, avec un t de 3,07, et 1,10 % avec un t de 3,61 dans le panneau B.

**Bêtas et capitalisations, stratégie 6 sur 6.** Le décile perdant P1 porte un bêta
de 1,36 pour une capitalisation moyenne de 208,24 millions de dollars ; le décile
gagnant P10 porte 1,28 pour 495,13 millions. Le bêta du portefeuille à coût nul vaut
-0,08. Les deux déciles extrêmes contiennent des titres plus petits que la moyenne,
et les perdants sont les plus petits des deux.

**Après coûts.** La rotation moyenne est de 84,8 % par semestre, dont 86,6 % du côté
achat et 83,1 % du côté vente. Avec un coût de transaction de 0,5 % par sens, le
rendement ajusté du risque reste de 9,29 % par an, significativement différent de
zéro. Il reste positif dans chacun des trois sous-échantillons de taille. Le coût
retenu est jugé conservateur au regard des 23 points de base estimés par Berkowitz,
Logue et Noser (1988) pour les institutionnels.

**Le mois de janvier renverse tout.** La stratégie 6 sur 6 perd 6,86 % en janvier,
avec un t de -3,52, et gagne 1,66 % par mois de février à décembre, avec un t de
6,67. Elle est positive dans 67 % des mois, et dans 71 % en excluant janvier. La
perte de janvier est d'autant plus forte que les firmes sont petites : -7,97 % pour
S1 contre -1,61 % pour S3, ce dernier chiffre n'étant pas significatif. Avril,
novembre et décembre sont les mois les plus favorables, avril étant positif 24 fois
sur 25.

**Sous-périodes de cinq ans**, stratégie 6 sur 6, tous titres. Le rendement mensuel
moyen vaut 1,23 % pour 1965-1969, 1,09 % pour 1970-1974, **-0,44 % pour 1975-1979**,
1,27 % pour 1980-1984 et 1,62 % pour 1985-1989. La seule sous-période négative tient
principalement aux rendements de janvier des petites firmes.

**Le renversement après un an.** Le rendement cumulé du portefeuille à coût nul atteint 9,51 % au douzième mois qui
suit la formation, avec un t de 3,67. Il retombe ensuite à 5,56 % au vingt-quatrième
et à 4,06 % au trente-sixième, ce dernier n'étant plus significatif. Le bêta du portefeuille passe de -0,20 contre l'indice pondéré par
la capitalisation à 0,02, une évolution de sens contraire à ce qu'exigerait une
explication par le risque.

**Le contre-test antérieur à 1965.** Sur 1927-1940, la stratégie 6 sur 6 perd :
environ -5 % dès le premier mois et un cumul de -40,81 % au trente-sixième. Deux
causes sont avancées, la proximité de la faillite de nombreux perdants, qui leur
donne un bêta très élevé, et le retour à la moyenne du marché. Juillet 1932 en
donne la mesure : l'indice équipondéré rebondit de 43 % après une baisse de 40 %, et
la stratégie perd 40 % ce mois-là, puis 68 % le mois suivant. Quatre autres mois des
années 1930 lui coûtent plus de 40 %, tous lors de hausses marquées du marché. Sur
1941-1964, en revanche, le profil des rendements ressemble à celui de 1965-1989.

## Les critiques connues

**Les coûts de transaction annulent le gain.** Lesmond, Schill et Zhou (2004, *Journal of Financial Economics*, vol. 71, pages 349 à
380) partent de deux mesures. La stratégie à six mois rapporte environ 6 % par
semestre brut, et elle exige quatre transactions par semestre, deux ouvertures et deux
clôtures. Le seuil de rentabilité
est donc de 1,5 % par transaction, et ils ne trouvent aucune preuve que les coûts
soient inférieurs à ce seuil sur les titres concernés. Leur argument de fond porte sur
la corrélation transversale : les titres qui produisent les plus gros gains de force
relative sont précisément ceux dont les coûts sont les plus élevés. Statut : rapporté,
article consulté le 2026-09-01.

**La capacité est bornée mais pas nulle.** Korajczyk et Sadka (2004, *The Journal of
Finance*, vol. 59, pages 1039 à 1082) estiment la taille de fonds au-delà de laquelle
le rendement anormal s'annule. Avec une pondération par la liquidité, ils obtiennent
5 milliards de dollars ou davantage, rapportés à la capitalisation de décembre 1999.
Statut : rapporté depuis le résumé en ligne, article **non consulté**.

**Ce n'est pas le momentum récent qui prédit.** Novy-Marx (2012, *Journal of
Financial Economics*, vol. 103, pages 429 à 453) montre que la performance des mois
-12 à -7 avant la formation prédit mieux que celle des six derniers mois. Il annonce
des résultats semblables sur les indices d'actions internationaux, les matières
premières et les devises. Sa période d'échantillon n'est pas donnée dans le résumé et
n'a pas été retrouvée : non trouvé au 2026-09-01. L'écart chiffré entre les deux
fenêtres n'a pas été récupéré non plus. Si ce résultat tient, la fenêtre de formation
de l'article de 1993 mélange un signal utile et un signal inutile. Statut : rapporté
depuis le résumé en ligne, article **non consulté**.

**La stratégie s'effondre par intermittence.** Daniel et Moskowitz (2016, *Journal of Financial Economics*, vol. 122, pages 221 à
247) mesurent que les deux pires mois du momentum américain sur 1927-2013 se suivent,
juillet et août 1932. Le décile perdant y gagne 232 % quand le décile gagnant ne gagne
que 32 %. De mars à mai 2009, le décile
perdant gagne 163 % contre 8 % pour les gagnants, alors que le marché monte de 26 %.
L'effondrement vient donc du côté vendeur, qui monte en flèche. Ces épisodes suivent
des baisses de marché et surviennent quand la volatilité est haute, ce qui les rend
partiellement prévisibles. Statut : rapporté, article consulté le 2026-09-01.

**La réplication moderne réduit le gain sans l'effacer.** Hou, Xue et Zhang (2020, *The Review of Financial Studies*, vol. 33, pages 2019 à
2133) rejouent 452 anomalies. Ils imposent des bornes de déciles NYSE et des
rendements pondérés par la capitalisation, deux choix qui réduisent le poids des
microcapitalisations. 65 % des anomalies ne
franchissent pas le seuil de 1,96 en valeur absolue du t. Le momentum est l'une des
deux catégories qui survivent le mieux, avec un taux de réplication de 63,2 %. Pour la
stratégie 6 sur 6 précisément, ils obtiennent 0,82 % par mois avec un t de 3,5. Ce
chiffre est celui de la pondération par la capitalisation avec bornes NYSE, contre
1,1 % et un t de 3,61 dans l'article de 1993. Le même calcul sur l'échantillon
d'origine donne 1,06 % avec un t de 3,82. Statut : rapporté, article consulté le
2026-09-01.

**Le résultat tient hors échantillon.** Jegadeesh et Titman (2001, *The Journal of Finance*) rejouent leur propre stratégie 6
sur 6 sur 1990-1998. L'univers y est élargi au Nasdaq, mais purgé des titres sous 5
dollars au début de la période de détention et du décile de plus petite
capitalisation. Ce décile est découpé sur les seules bornes du NYSE. Les gagnants battent les perdants de 1,39 % par mois, contre 1,17 %
sur 1965-1989 avec ce même univers. Le résultat de 1993 n'est donc pas un artefact
d'exploration de données. Statut : rapporté, article consulté le 2026-09-01.

## Les problèmes de réplication connus

**Une réplication soignée n'atterrit pas exactement sur le chiffre publié.** Hou, Xue et Zhang décrivent une procédure équipondérée sur tous les titres, sur la
période d'origine, qu'ils déclarent la plus proche de celle de 1993. Elle donne 1,18 %
par mois avec un t de 4,22, là où l'article publie 1,1 % avec un t de 3,61 pour la
même stratégie. L'écart
de huit points de base est le meilleur ordre de grandeur disponible pour juger notre
propre réplication. Sur l'échantillon étendu, le même calcul tombe à 0,7 % avec un t
de 2,63.

**Les rendements mensuels sont composés depuis le fichier quotidien.** Lire le fichier
mensuel du CRSP donne des nombres proches mais non identiques, notamment sur les mois
qui contiennent une suspension de cotation.

**Le nommage des déciles s'inverse entre 1993 et 2001.** Un code qui suit l'article de
2001 en croyant suivre celui de 1993 produit exactement l'opposé du signal.

**Le décalage est d'une semaine.** Implémenter un saut d'un mois, par habitude prise
de la littérature ultérieure, ne reproduit ni le panneau A ni le panneau B.

**La convention de détention n'est pas neutre.** Les cohortes sont rééquilibrées
mensuellement vers l'équipondération. L'article signale que l'achat et conservation
rapporte légèrement plus, sans publier de combien : non trouvé.

**Le traitement des radiations n'est pas décrit.** L'article ne dit pas s'il applique
un rendement de radiation aux titres sortis de la cote. C'est le décile perdant qui en
contient le plus, donc l'enjeu est du bon côté pour gonfler le gain : non trouvé au
2026-09-01.

**Le nombre de titres n'est pas publié**, ce qui prive d'un contrôle simple sur la
construction de l'univers.

## Les biais possibles

**L'exploration de données.** L'article la nomme lui-même, en rappelant que Jensen et
Bennington (1970) avaient attribué le résultat de Levy (1967) à une sélection parmi 68
règles. Deux garde-fous sont posés : la borne de Bonferroni sur 32 tests, et le
contre-test sur 1927-1964, hors de l'échantillon d'origine.

**Le poids des microcapitalisations.** L'équipondération donne à chaque titre le même
poids qu'à une très grande capitalisation, alors que le décile perdant a une
capitalisation moyenne de 208 millions de dollars. C'est le mécanisme central du
diagnostic de Hou, Xue et Zhang.

**Le rebond acheteur-vendeur.** Un titre coté au cours acheteur en fin de période de
classement paraît perdant, puis rebondit mécaniquement. Le panneau B, avec son
décalage d'une semaine, est précisément la parade, et les rendements y sont plus
élevés, ce qui montre que le biais joue en sens inverse ici.

**Le coût de la vente à découvert.** La moitié du portefeuille est vendue à découvert,
sur les titres les plus petits et les moins liquides. Le coût d'emprunt des titres
n'entre pas dans les 0,5 % par sens.

**La saisonnalité de janvier.** La perte de janvier est concentrée sur les petites
firmes et n'est pas significative pour les grandes. Un test qui exclut janvier
mesure autre chose que la stratégie complète, et doit le dire.

**La sélection par la disponibilité des données.** Exiger J mois de rendements exclut
les introductions récentes, ce qui n'est pas neutre sur un décile gagnant.

## Nos décisions d'implémentation

Non commencé au 2026-09-01.

## Nos écarts avec l'article

Non commencé au 2026-09-01.

## Nos résultats

Non commencé au 2026-09-01.

## Notre contrôle de robustesse

Non commencé au 2026-09-01.

## Références

- Jegadeesh, N. et Titman, S. (1993). Returns to buying winners and selling losers:
  implications for stock market efficiency. *The Journal of Finance*, 48(1), 65-91.
  [doi:10.1111/j.1540-6261.1993.tb04702.x](https://doi.org/10.1111/j.1540-6261.1993.tb04702.x)
- Jegadeesh, N. et Titman, S. (2001). Profitability of momentum strategies: an
  evaluation of alternative explanations. *The Journal of Finance*, 56(2), 699-720.
  [Fac-similé](http://www-stat.wharton.upenn.edu/~steele/Courses/434/434Context/Momentum/MomentumStrategiesJF2001.pdf)
- Lesmond, D. A., Schill, M. J. et Zhou, C. (2004). The illusory nature of momentum
  profits. *Journal of Financial Economics*, 71(2), 349-380.
  [Fac-similé](https://www.bauer.uh.edu/rsusmel/phd/Lesmond_et%20al%20_2004_JFE.pdf)
- Korajczyk, R. A. et Sadka, R. (2004). Are momentum profits robust to trading costs?
  *The Journal of Finance*, 59(3), 1039-1082.
  [Page éditeur](https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.2004.00656.x)
- Novy-Marx, R. (2012). Is momentum really momentum? *Journal of Financial
  Economics*, 103(3), 429-453.
  [Page éditeur](https://www.sciencedirect.com/science/article/abs/pii/S0304405X11001152)
- Daniel, K. et Moskowitz, T. J. (2016). Momentum crashes. *Journal of Financial
  Economics*, 122(2), 221-247.
  [Fac-similé](https://www.kentdaniel.net/papers/published/jfe_16.pdf)
- Hou, K., Xue, C. et Zhang, L. (2020). Replicating anomalies. *The Review of
  Financial Studies*, 33(5), 2019-2133.
  [Fac-similé](https://global-q.org/uploads/1/2/2/6/122679606/houxuezhang2020rfs.pdf)
- De Bondt, W. F. M. et Thaler, R. (1985). Does the stock market overreact?
  *The Journal of Finance*, 40(3), 793-805. Cité par l'article.
- Lo, A. W. et MacKinlay, A. C. (1990). When are contrarian profits due to stock
  market overreaction? *The Review of Financial Studies*, 3(2), 175-205. Cité par
  l'article.

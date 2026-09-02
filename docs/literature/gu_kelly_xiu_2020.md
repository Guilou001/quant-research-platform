# Empirical Asset Pricing via Machine Learning

| | |
|---|---|
| **Auteurs** | Shihao Gu, Bryan T. Kelly, Dacheng Xiu |
| **Année** | 2020 (document de travail NBER n° 25398, décembre 2018) |
| **Revue ou source** | The Review of Financial Studies, vol. 33, n° 5, p. 2223-2274 |
| **Lien** | [PDF de l'auteur](https://dachxiu.chicagobooth.edu/download/ML.pdf), [page RFS](https://academic.oup.com/rfs/article/33/5/2223/5758276), [NBER w25398](https://www.nber.org/system/files/working_papers/w25398/w25398.pdf) |
| **Statut de réplication** | non commencé |

Deux versions ont été consultées le 2026-09-01 et lues intégralement : le PDF de
l'éditeur mis en ligne par Dacheng Xiu, et le document de travail NBER n° 25398.
La pagination diffère selon la source : l'en-tête de course du PDF de l'éditeur
imprime « 2223-2274 » alors que la notice de l'éditeur en ligne annonce
2223-2273. La contradiction est signalée et non tranchée. L'annexe internet, où
vivent les tables A.7 à A.11 citées ci-dessous, n'a PAS été consultée.

## La question de recherche

De combien un modèle non linéaire mesure-t-il mieux la prime de risque d'une
action qu'une régression linéaire, et d'où vient le gain ? La prime de risque, la
rémunération espérée pour porter le risque d'un titre, se mesure mal parce que le
rendement observé est dominé par des nouvelles imprévisibles. Les auteurs posent
que le problème n'est pas le manque de prédicteurs mais la forme imposée à la
fonction qui les relie au rendement.

La tension qui organise l'article tient en deux faits vrais. La littérature
recense 330 signaux prédictifs au niveau du titre (rapporté, Green, Hand et
Zhang 2013, compté en note 2 p. 2225). Et pourtant aucune régression linéaire
ne dépasse une poignée de dixièmes de pourcent de pouvoir prédictif mensuel. Soit
les signaux sont faux, soit la régression est le mauvais instrument.

## L'intuition économique

Un rendement se prédit parce que la prime de risque varie dans le temps et selon
la firme, et non parce que le marché serait lent. C'est la lecture que
revendiquent les auteurs : ils écrivent \(E_t(r_{i,t+1}) = g^{\star}(z_{i,t})\)
et la seule nouveauté est la forme de \(g^{\star}\). Une régression linéaire
impose que l'effet d'une caractéristique soit constant et additif. Si la vraie
prime dépend d'interactions, par exemple d'un momentum dont le prix change selon
le taux court, la régression mesure mal une prime qui existe pourtant.
L'apprentissage automatique ne crée alors aucune anomalie, il répare un
instrument de mesure.

Cette lecture est contestable, et l'article l'affaiblit lui-même. Le prédicteur
le mieux classé est le renversement à un mois, la propension d'un titre à
inverser le rendement de son mois écoulé. Il est en tête de la figure 5,
p. 2255, qui somme les rangs d'importance des 94 caractéristiques sur onze
modèles. Et l'article ne publie aucun nombre pour ce classement. Cinq des sept
premiers signaux sont des variables de tendance de prix (rapporté, p. 2254).
Viennent ensuite les variables de liquidité : rotation, capitalisation, volume
en dollars,
illiquidité d'Amihud, écart acheteur-vendeur. Un tel classement décrit le prix
de l'immédiateté, ce que coûte de trouver une contrepartie tout de suite,
plutôt qu'une compensation de risque systématique.

Deux mécanismes restent donc en lice, et ils ne meurent pas de la même façon. Si
la source est une prime de risque conditionnelle, rien ne la fait disparaître :
elle est le prix payé pour porter un risque, et sa publication ne l'annule pas.
Si la source est une friction, trois choses l'usent, la baisse des coûts de
transaction, l'entrée de capital après publication, et l'accès des arbitragistes
aux titres peu liquides. Le test qui sépare les deux est le rendement net de
coûts, sur les grandes capitalisations seules.

Or l'article donne les deux moitiés de la réponse et elles pointent en sens
contraires. La précision de prévision est MEILLEURE sur les grandes valeurs, 0,70 %
mensuel contre 0,45 % sur les petites pour le réseau à trois couches. Le profit,
lui, est bien plus gros à pondération égale qu'à pondération par la
capitalisation, ratio de Sharpe 2,45 contre 1,35. Le premier fait plaide pour la
prime de risque, le second pour la friction, et l'article ne tranche pas.

Encore faut-il que le premier fait tienne à tous les horizons, et il ne tient
pas. À douze mois, le classement s'inverse. Le même réseau à trois couches
explique 5,17 % sur les mille plus petites contre 4,73 % sur les mille plus
grandes. Le renversement vaut pour onze des treize modèles (rapporté, table 2 du
document NBER, p. 28). L'argument de la prime de risque repose donc sur le
seul horizon mensuel, celui-là même où le renversement à un mois domine le
classement des prédicteurs.

## Les données

Rendements mensuels totaux du CRSP pour toutes les firmes cotées au NYSE, à
l'AMEX et au NASDAQ, de mars 1957 à décembre 2016, soit soixante ans (p. 2248).
L'échantillon compte près de 30 000 titres, avec plus de 6 200 titres par mois en
moyenne (rapporté, p. 2248). Le taux des bons du Trésor sert de taux sans risque
pour former les rendements excédentaires.

Le jeu de prédicteurs se compose de trois blocs. Quatre-vingt-quatorze
caractéristiques de firme, huit variables macroéconomiques agrégées, et
soixante-quatorze indicatrices sectorielles à deux chiffres du code SIC. Chaque
caractéristique est croisée avec chaque variable macroéconomique et avec une
constante, ce qui donne \(94 \times (8+1) + 74 = 920\) variables explicatives
(p. 2249). Les huit variables macroéconomiques sont celles de Welch et Goyal
(2008), et la table 4 (p. 2257) les nomme :

- rendement en dividendes, rendement en bénéfices ;
- ratio valeur comptable sur valeur de marché agrégé, émissions nettes de titres ;
- taux à trois mois, pente de la courbe, prime de défaut, variance du marché.

Découpage temporel, fixé une fois pour toutes : dix-huit ans d'apprentissage
(1957-1974), douze ans de validation (1975-1986), et trente ans de test hors
échantillon (1987-2016). Le réajustement se fait une fois par an, la fenêtre
d'apprentissage s'allonge d'un an à chaque fois, et la fenêtre de validation
garde sa taille en roulant de douze mois (p. 2249).

## L'univers

Toutes les actions ordinaires du CRSP des trois places citées, sans filtre de
taille ni de prix pour l'analyse principale. Deux sous-échantillons d'évaluation
sont découpés chaque mois dans les prévisions du modèle complet : les mille plus
grandes capitalisations et les mille plus petites. Le modèle n'est jamais
réestimé sur ces sous-échantillons.

Pour les portefeuilles, les titres sont classés en déciles selon la prévision,
reconstitués chaque mois, en pondération par la capitalisation puis en
pondération égale. Un contrôle exclut les titres sous le vingtième centile de la
distribution de taille du NYSE (p. 2267).

## La méthodologie

Treize modèles sont comparés sur le même découpage et le même jeu de variables.
Quatre sont linéaires : régression complète (MCO), régression à trois variables
seulement (taille, valeur comptable sur valeur de marché, momentum), moindres
carrés partiels, et régression sur composantes principales. Deux sont pénalisés
ou semi-paramétriques : filet élastique et modèle linéaire généralisé à pénalité
de groupe. Deux sont des ensembles d'arbres : forêt aléatoire et arbres de
régression amplifiés par gradient. Restent cinq réseaux de neurones, de une à
cinq couches cachées.

Pour les MCO, le filet élastique, le modèle linéaire généralisé et les arbres
amplifiés, les auteurs retiennent la version robuste à perte de Huber. Cette
perte est quadratique près de zéro et linéaire au-delà d'un seuil, ce qui borne
l'influence des rendements extrêmes. Elle fait mieux que la perte quadratique
dans leur comparaison (p. 2250).

Les réseaux de neurones sont régularisés par cinq moyens simultanés (p.
2245-2246). Pénalité \(\ell_1\) sur les poids, décroissance adaptative du pas
d'apprentissage par l'algorithme Adam de Kingma et Ba (2014), arrêt anticipé,
normalisation par lots, et agrégation de plusieurs initialisations aléatoires
dont les prévisions sont moyennées. Le NOMBRE de graines utilisées n'est pas
écrit dans le corps de l'article. Il figure peut-être dans l'annexe internet,
non consultée. Un dépôt de réplication tiers affirme que l'article en emploie
dix, sans citer d'où il tient ce chiffre ; c'est **non vérifié** et ce n'est pas
une source primaire.

L'évaluation repose sur un \(R^2\) hors échantillon, la part de la variabilité
du rendement futur que la prévision explique sur des données qui n'ont servi ni
à estimer ni à régler le modèle. Le dénominateur retenu est la somme des carrés
des rendements excédentaires SANS centrage, et non l'écart à la moyenne
historique. Les auteurs justifient ce choix et en donnent le prix. Mesuré
contre la moyenne historique, le \(R^2\) mensuel de toutes les méthodes monte
d'environ trois points de pourcentage. Celui de la régression à trois variables
atteint alors 3,74 % par mois (note 34, p. 2252 de la version RFS, reprise p. 28
du document NBER). Les comparaisons entre modèles se font par le test de
Diebold et Mariano (1995).

## Les équations qui comptent

Le modèle de rendement excédentaire, additivement séparable entre prime et bruit :

\[ r_{i,t+1} = E_t(r_{i,t+1}) + \epsilon_{i,t+1}, \qquad E_t(r_{i,t+1}) = g^{\star}(z_{i,t}) \]

Le vecteur de variables explicatives, produit de Kronecker entre l'état
macroéconomique commun \(x_t\) et les caractéristiques de firme \(c_{i,t}\) :

\[ z_{i,t} = x_t \otimes c_{i,t} \]

Ce produit est la traduction empirique de l'équation d'Euler conditionnelle
\(E_t(r_{i,t+1}) = \beta_{i,t}' \lambda_t\). Si les expositions sont linéaires
dans les caractéristiques et le prix du risque linéaire dans l'état, alors le
produit croisé suffit à représenter le modèle de bêtas (p. 2249).

Le critère d'évaluation, avec \(\mathcal{T}_3\) l'échantillon de test :

\[ R^2_{\mathrm{oos}} = 1 - \frac{\sum_{(i,t) \in \mathcal{T}_3} \left(r_{i,t+1} - \hat{r}_{i,t+1}\right)^2}{\sum_{(i,t) \in \mathcal{T}_3} r_{i,t+1}^2} \]

La traduction d'un pouvoir prédictif en ratio de Sharpe, empruntée à Campbell et
Thompson (2008) et utilisée p. 2263 :

\[ SR^{\star} = \sqrt{\frac{SR^2 + R^2}{1 - R^2}} \]

## Les résultats originaux

Tous les nombres de cette section sont **rapportés**, tirés de la table 1, de
la table 2, de la table 7 et de la table 8 de l'article. La table 1 n'était pas
extractible du PDF de l'éditeur. Ses valeurs viennent de la table 1 du document
de travail NBER n° 25398, p. 26. Elles concordent avec le texte de la version
RFS partout où celui-ci les cite.

### Pouvoir prédictif mensuel, en pourcentage

| Sous-échantillon | MCO | MCO-3 | MCP | RCP | Filet | MLG | Forêt | Arbres ampl. | RN1 | RN2 | RN3 | RN4 | RN5 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Tous | -3,46 | 0,16 | 0,27 | 0,26 | 0,11 | 0,19 | 0,33 | 0,34 | 0,33 | 0,39 | **0,40** | 0,39 | 0,36 |
| 1 000 plus grandes | -11,28 | 0,31 | -0,14 | 0,06 | 0,25 | 0,14 | 0,63 | 0,52 | 0,49 | 0,62 | **0,70** | 0,67 | 0,64 |
| 1 000 plus petites | -1,30 | 0,17 | 0,42 | 0,34 | 0,20 | 0,30 | 0,35 | 0,32 | 0,38 | 0,46 | 0,45 | **0,47** | 0,42 |

MCP désigne les moindres carrés partiels, RCP la régression sur composantes
principales, MLG le modèle linéaire généralisé, RN\(k\) le réseau à \(k\) couches
cachées. Les colonnes MCO, MCO-3, filet, MLG et arbres amplifiés emploient la
perte de Huber.

Trois faits ressortent de cette table, et le signe compte autant que la taille.
Le meilleur modèle explique **0,40 % de la variabilité mensuelle**, soit quatre
millièmes. La régression complète sur les 920 variables fait **PIRE que de
prévoir zéro partout**, à -3,46 %, ce qui mesure directement le sur-ajustement.
Et le gain se concentre sur les GRANDES capitalisations, 0,70 % contre 0,45 %,
alors que l'intuition attendait l'inverse.

À l'horizon annuel (table 2, NBER p. 28), l'ordre des méthodes ne change pas
mais le niveau est presque dix fois plus haut. Sur l'échantillon complet :
-34,86 % pour les MCO, 3,40 % pour le réseau à trois couches et 3,60 % pour
celui à quatre couches. Le classement entre grandes et petites capitalisations,
lui, s'inverse. Sur les mille plus petites, le réseau à trois couches explique
5,17 % contre 4,73 % sur les mille plus grandes. Onze des treize modèles
prédisent mieux les petites que les grandes à cet horizon.

### Portefeuilles

Le décile long moins court construit sur le réseau à quatre couches rapporte
2,3 % par mois, soit 27,1 % par an. Sa volatilité mensuelle vaut 5,8 %, soit
20,1 % par an, d'où un **ratio de Sharpe annualisé de 1,35** en pondération par
la capitalisation (p. 2264-2265). Le même portefeuille en pondération égale
atteint **2,45** (table A.9, citée p. 2265, annexe non consultée). La
régression de référence à trois variables donne 0,61 et 0,83 sur les deux mêmes
pondérations (p. 2228).

Le contrôle qui compte pour juger la friction est l'exclusion des plus petits
titres. En retirant ceux qui tombent sous le vingtième centile de taille du
NYSE, le ratio de Sharpe en pondération égale du réseau à quatre couches
**tombe de 2,45 à 1,69** (p. 2267). Un tiers du profit tenait donc aux titres
les plus petits.

En chronométrage d'indice, un investisseur module son exposition au S&P 500
selon la prévision agrégée du réseau à trois couches. Il obtient un ratio de
Sharpe de 0,77 contre 0,51 pour l'achat et conservation, soit 26 points de
pourcentage de plus (p. 2264).

### Rotation et alpha

La rotation mensuelle des portefeuilles de réseaux de neurones se tient entre
110 % et 130 % (table 8, p. 2267). Pour situer, la rotation d'un décile de
renversement à court terme vaut 172,6 % par mois et celle d'un décile de taille
22,9 %. L'alpha du réseau à quatre couches contre le modèle à cinq facteurs de
Fama-French augmenté du momentum vaut 1,76 % par mois, avec un \(t\) de 6,00,
en pondération par la capitalisation. En pondération égale il vaut 3,08 % par
mois, avec un \(t\) de 12,28 (table 8).

**L'article ne chiffre aucun coût de transaction, nulle part.** Ce n'est pas une
lacune cachée : il ne prétend pas mesurer un rendement net.

### Variables influentes

Les modèles s'accordent sur quatre groupes (p. 2254). Les tendances de prix,
renversement à un mois, momentum à douze mois, variation du momentum, momentum
sectoriel, rendement maximum récent, renversement à trente-six mois. La
liquidité, rotation et sa volatilité, log de la capitalisation, volume en
dollars, illiquidité d'Amihud, jours sans transaction, écart acheteur-vendeur.
Les mesures de risque, volatilité totale et idiosyncrasique, bêta et bêta au
carré. Enfin les ratios de valorisation et signaux comptables. Côté
macroéconomique, le ratio valeur comptable sur valeur de marché agrégé domine
dans les réseaux, à 27,9 % de l'importance pour le réseau à trois couches
(table 4).

## Les critiques connues

**Avramov, Cheng et Metzker (2023)** répliquent l'approche puis lui appliquent
des restrictions économiques. Leur verdict, tel que publié dans le résumé,
tient en deux temps. L'exclusion des micro-capitalisations, des sociétés en
détresse financière ou des épisodes de forte volatilité de marché atténue
considérablement la rentabilité. Et la performance se dégrade encore en
présence de coûts de transaction raisonnables, à cause d'une rotation élevée et
de positions extrêmes. *Machine Learning vs. Economic Restrictions: Evidence
from Stock Return Predictability*, Management Science, vol. 69, n° 5, p.
2587-2619. L'AMPLEUR chiffrée de l'atténuation n'a pas été retrouvée :
l'article est derrière un péage et seul le résumé a été consulté, via
[RePEc](https://ideas.repec.org/a/inm/ormnsc/v69y2023i5p2587-2619.html).

**Leippold, Wang et Zhou (2022)** refont l'exercice sur le marché chinois et
trouvent un classement différent des prédicteurs. La liquidité y arrive en
tête, et le poids des investisseurs particuliers renforce la prédictibilité de
court terme. Contrairement au cas américain, les grandes valeurs et les
entreprises d'État sont les plus prévisibles à long horizon. Leur performance
hors échantillon reste économiquement significative après coûts de transaction.
*Machine learning in the Chinese stock market*, Journal of Financial Economics,
vol. 145, n° 2, p. 64-82. Résumé consulté via
[EconPapers](https://econpapers.repec.org/RePEc:eee:jfinec:v:145:y:2022:i:2:p:64-82),
texte intégral non consulté.

**Bagnara (2024)** passe la littérature en revue de façon critique et range les
contributions en cinq familles selon la méthode employée. Sa mise en garde
générale : ces techniques offrent de la souplesse et de la précision mais
demandent une prudence particulière, car elles s'écartent fortement de
l'économétrie traditionnelle. *Asset Pricing and Machine Learning: A critical
review*, Journal of Economic Surveys, vol. 38, n° 1, p. 27-56. Seul le résumé a
été consulté ; l'accès Wiley renvoie une erreur 403.

Aucune critique publiée mettant en cause la SENSIBILITÉ AUX GRAINES ALÉATOIRES de
ces résultats précis n'a été trouvée au 2026-09-01, malgré une recherche ciblée.
C'est un résultat de recherche, pas une absence de problème : la littérature
générale sur la reproductibilité en apprentissage automatique documente
abondamment cette fragilité.

## Les problèmes de réplication connus

Les quatre-vingt-quatorze caractéristiques ne sont pas publiées avec l'article.
Les auteurs déclarent en note 30, p. 2248, avoir adapté le code SAS diffusé par
Jeremiah Green. Ils déclarent s'être écartés de ses définitions pour coller de
plus près aux articles d'origine, et avoir remonté l'échantillon jusqu'en 1957. Le code de
départ existe donc, mais pas la version adaptée qui produit les nombres publiés.
Toute réplication passe par une reconstruction, ou par une base de substitution
comme le projet Open Source Asset Pricing de Chen et Zimmermann. L'écart de
construction se répercutera sur des \(R^2\) de quelques dixièmes de pourcent.
**C'est le risque principal du
projet** : à cette échelle, une différence de définition pèse autant que le
modèle.

La réplication publique de Tidy Finance, consultée le 2026-09-01
([blog.tidy-finance.org](https://blog.tidy-finance.org/posts/gu-kelly-xiu-replication/)),
est un guide d'implémentation en R et non une réplication de résultats. Elle ne
publie AUCUN \(R^2\) hors échantillon comparable, se limite à la forêt aléatoire,
part de 1960 au lieu de 1957 et prolonge les caractéristiques jusqu'en 2021. Ses
auteurs signalent eux-mêmes que l'écart de trois ans peut expliquer une partie de
la divergence de performance.

Le dépôt public de réplication partielle
[duongtran14](https://github.com/duongtran14/Partial-replication-of-Gu-Kelly-Xiu-2020-Empirical-Asset-Pricing-via-Machine-Learning.)
n'entraîne les réseaux qu'avec cinq graines faute de ressources, et son auteur
attribue à cela une partie de sa perte de précision. Il écrit que l'article
original en utilise dix, sans dire d'où il tient ce nombre. Le corps de
l'article ne l'écrit nulle part : la valeur dix est **non vérifiée**.

Les tables A.7 à A.11, qui portent la pondération égale, l'exclusion des
micro-capitalisations et les modèles MCO à sept et quinze variables, vivent dans
l'annexe internet. Elle n'a pas été consultée, donc les valeurs 2,45 et 1,69
citées plus haut proviennent du corps de l'article qui les résume, pas des tables
elles-mêmes.

## Les biais possibles

**Le choix de dénominateur gonfle mécaniquement toute comparaison avec la
littérature antérieure.** L'article l'écrit et le chiffre : mesuré contre la
moyenne historique, le \(R^2\) de toutes les méthodes monte d'environ trois
points. Un lecteur qui compare 0,40 % à un chiffre publié ailleurs contre la
moyenne historique compare deux quantités différentes.

**Les micro-capitalisations dominent le nombre de titres, pas la valeur.** Avec
plus de 6 200 titres par mois en moyenne, l'essentiel du panier est composé de
titres que personne ne peut négocier en taille. Les fonctions objectif des
modèles minimisent une erreur de prévision à pondération égale, donc
l'entraînement est piloté par ces titres. Le passage de 2,45 à 1,69 en excluant
le vingtième centile du NYSE mesure directement cette dépendance.

**La rotation de 110 à 130 % par mois n'est jamais confrontée à un coût.** Le
décile long moins court du réseau à quatre couches tourne à 126,81 % par mois
et rapporte 2,26 % par mois en pondération par la capitalisation (table 8). En
traitant cette rotation comme la fraction de la valeur brute échangée chaque
mois, dix points de base de coût par dollar échangé retirent 0,13 point de
rendement mensuel. Il faut donc **178 points de base** de coût pour annuler la
stratégie. Ce calcul est **modélisé**, avec deux hypothèses déclarées ici et
absentes de l'article : la lecture de la rotation, et un coût constant par
dollar échangé. Ce seuil de 178 points de base est le premier chiffre que notre
réplication devra confronter aux coûts réels des titres concernés.

**Un seul chemin de test.** Les trente ans hors échantillon sont uniques, et
treize modèles y sont comparés. Le ratio de Sharpe le plus élevé est donc un
maximum sur treize essais sur un seul échantillon, sans correction de sélection
de type déflation du ratio de Sharpe. Les auteurs contrôlent la significativité
des différences de prévision par le test de Diebold-Mariano, ce qui ne corrige
pas la sélection sur la performance de portefeuille.

**Les délais comptables sont déclarés, la radiation ne l'est pas.** La note 30,
p. 2248, fixe la règle. Pour prévoir le rendement du mois \(t+1\), les auteurs
n'utilisent que les caractéristiques mensuelles arrêtées à la fin du mois \(t\),
les trimestrielles arrêtées en \(t-4\) et les annuelles arrêtées en \(t-6\). Les
valeurs manquantes sont remplacées par la médiane transversale du mois. Le
traitement des rendements de radiation du CRSP, lui, n'apparaît nulle part dans
les deux versions lues : le mot ne figure ni dans le texte RFS ni dans le
document NBER. C'est un **non trouvé**, et il pèse, puisque les micro-capitalisations
dominent le nombre de titres et sont celles qui sortent de la cote.

## Nos décisions d'implémentation

Étude 011 du 2026-09-02. Le panneau est celui de l'étude 004 : vingt et une
variables comptables et de risque point-in-time par société et par mois, plus
la capitalisation et les rendements mensuels. Il couvre 1 526 grandes
capitalisations américaines de 2015-06 à 2026-06. Six caractéristiques de prix s'y ajoutent,
momentum à douze mois, renversement à un mois et à long terme, volatilité,
rendement mensuel le plus élevé, taille. Les rangs transversaux dans
l'intervalle de moins un à plus un et le manquant à zéro suivent l'article.
L'étiquette est le rendement en excès du taux sans risque de Kenneth French du
mois suivant. Six méthodes, treize configurations en tout : moindres carrés,
régression pénalisée en carré, en valeur absolue, filet élastique, arbres
amplifiés par gradient, forêt aléatoire. Le modèle simple à battre, la
régression pénalisée en carré, et le modèle complexe de l'hypothèse, les
arbres amplifiés, sont désignés dans la configuration avant tout résultat.

## Nos écarts avec l'article

| Point | Article | Étude 011 |
|---|---|---|
| Univers | tout le CRSP, 1957-2016 | 1 526 grandes capitalisations, 2015-2026, biais de survie déclaré |
| Caractéristiques | 94 par titre, 8 macroéconomiques en produit croisé | 27 par titre, aucune macroéconomique |
| Découpage | 18 ans d'entraînement, 12 de validation, test glissant d'un an | 5 ans d'entraînement, 2 de validation à la fin, test d'un an, ancré |
| Après validation | modèle validé conservé | réajusté sur tout l'entraînement |
| Perte | Huber pour les linéaires | quadratique, la fabrique de Huber existe sans être dans la grille |
| Réseaux de neurones | cinq, de une à cinq couches | aucun dans la grille |
| Coûts | aucun | 10 points de base par unité négociée, statut modélisé |

## Nos résultats

Étude 011, hors échantillon de 2020-07 à 2026-06, 72 mois, six plis. Le R²
mensuel sans centrage vaut 0,41 % pour les moindres carrés et la régression
pénalisée en carré. Il vaut 0,45 % pour la pénalisée en valeur absolue,
0,44 % pour le filet élastique, 0,35 % pour les arbres amplifiés et 0,48 %
pour la forêt. Les six sont dans la plage publiée de 0,3 % à 0,7 %. Le
classement de l'article ne se retrouve pas : la forêt est en tête et les
arbres amplifiés en queue. Aucune méthode ne bat la référence linéaire au test
de Diebold et Mariano, la statistique des arbres valant -0,45 avec une valeur
p de 0,65. La corrélation de rang moyenne est négative pour les six méthodes,
ce que l'article ne rapporte pas et que son R² ne peut pas montrer. Les
déciles long moins court, nets de 10 points de base, rendent un ratio de
Sharpe de 0,663 pour les arbres et de 0,277 pour la régression. L'article
publie 1,35 et 0,61, bruts, en pondération par la capitalisation. Verdict
`REJECTED`.

## Notre contrôle de robustesse

Dix-sept essais déclarés. Sharpe dégonflé des arbres 0,82, probabilité de
surapprentissage entre les six portefeuilles 0,37, trois sous-périodes de deux
ans positives et croissantes, survie à cinq fois les coûts et mort à dix. Le
R² par bloc de test change de signe, +3,4 % puis -6,8 % sur les deux premiers
plis des arbres, et il est négatif pour les six méthodes sur 2021-2022.
L'importance par permutation désigne la volatilité de douze mois et
l'endettement, donc un tri de solidité financière que les facteurs de l'étude
004 portaient déjà.

## Références

- Gu, S., Kelly, B. T. et Xiu, D. (2020). Empirical Asset Pricing via Machine
  Learning. *The Review of Financial Studies*, 33(5), 2223-2274.
  <https://dachxiu.chicagobooth.edu/download/ML.pdf>
- Gu, S., Kelly, B. T. et Xiu, D. (2018). Empirical Asset Pricing via Machine
  Learning. *NBER Working Paper* n° 25398.
  <https://www.nber.org/system/files/working_papers/w25398/w25398.pdf>
- Avramov, D., Cheng, S. et Metzker, L. (2023). Machine Learning vs. Economic
  Restrictions: Evidence from Stock Return Predictability. *Management Science*,
  69(5), 2587-2619.
  <https://ideas.repec.org/a/inm/ormnsc/v69y2023i5p2587-2619.html>
- Leippold, M., Wang, Q. et Zhou, W. (2022). Machine learning in the Chinese stock
  market. *Journal of Financial Economics*, 145(2), 64-82.
  <https://econpapers.repec.org/RePEc:eee:jfinec:v:145:y:2022:i:2:p:64-82>
- Bagnara, M. (2024). Asset Pricing and Machine Learning: A critical review.
  *Journal of Economic Surveys*, 38(1), 27-56.
  <https://onlinelibrary.wiley.com/doi/abs/10.1111/joes.12532>
- Campbell, J. Y. et Thompson, S. B. (2008). Predicting Excess Stock Returns Out
  of Sample. *The Review of Financial Studies*, 21(4), 1509-1531. Cité par
  Gu, Kelly et Xiu p. 2263, non consulté.
- Green, J., Hand, J. R. M. et Zhang, X. F. (2013). The supraview of return
  predictive signals. *Review of Accounting Studies*, 18, 692-730. Source du
  compte de 330 signaux, cité par Gu, Kelly et Xiu en note 2, non consulté.
- Green, J., Hand, J. R. M. et Zhang, X. F. (2017). The characteristics that
  provide independent information about average US monthly stock returns.
  *The Review of Financial Studies*, 30, 4389-4436. Source des 94
  caractéristiques, non consulté.
- Welch, I. et Goyal, A. (2008). A Comprehensive Look at the Empirical Performance
  of Equity Premium Prediction. *The Review of Financial Studies*, 21(4),
  1455-1508. Source des 8 variables macroéconomiques, non consulté.
- Tidy Finance (s. d.). Replicating Gu, Kelly & Xiu (2020).
  <https://blog.tidy-finance.org/posts/gu-kelly-xiu-replication/>

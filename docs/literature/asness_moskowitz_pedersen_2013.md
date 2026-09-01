# Value and Momentum Everywhere

| | |
|---|---|
| **Auteurs** | Clifford S. Asness, Tobias J. Moskowitz, Lasse Heje Pedersen |
| **Année** | 2013 |
| **Revue ou source** | The Journal of Finance, vol. 68, n° 3, juin 2013, p. 929-985 (DOI 10.1111/jofi.12021) |
| **Lien** | Version publiée consultée le 2026-09-01 : [w4.stern.nyu.edu](https://w4.stern.nyu.edu/facdir/lpederse/papers/ValMomEverywhere.pdf). Page SSRN : [abstract 2174501](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2174501). Données de l'article : [AQR](https://www.aqr.com/Insights/Datasets/Value-and-Momentum-Everywhere-Factors-Monthly) |
| **Statut de réplication** | non commencé |

## La question de recherche

La valeur et le momentum se comportent-ils comme deux anomalies séparées, ou comme
deux faces d'un même phénomène mondial ? La littérature d'avant 2013 étudiait chacune
dans son coin, le plus souvent sur les actions américaines. Les auteurs les mesurent
ensemble, dans huit marchés à la fois. Ils posent alors une question de tarification. Un
modèle unique à trois facteurs peut-il expliquer les rendements de la valeur et du
momentum partout, plutôt qu'un modèle spécialisé par classe d'actif ?

La tension qui rend la question intéressante est arithmétique. Les deux stratégies
rapportent en moyenne, et pourtant leurs rendements sont négativement corrélés. Une
théorie qui explique le ratio de Sharpe de la valeur seule doit donc franchir une barre
plus haute : elle doit expliquer celui de la combinaison, nettement supérieur.

## L'intuition économique

Le rendement de la combinaison devrait exister parce que les deux signaux prennent des
positions opposées sur la même information de prix, tout en étant tous deux rémunérés.
Le mécanisme se lit en deux temps.

Côté momentum, l'explication proposée par les auteurs est le risque de financement,
c'est-à-dire le risque que les intermédiaires à effet de dette voient leur capacité
d'emprunt se restreindre. Le momentum achète ce que tout le monde vient d'acheter, donc
il tient les positions les plus encombrées. Quand un choc de liquidité force des ventes,
la pression de prix frappe d'abord ces positions encombrées, parce que tous sortent par
la même porte au même moment (p. 932-933). Côté valeur, la position est contrarienne, et
moins encombrée par construction. Elle subit donc moins le choc, et elle gagne là où le
momentum perd. L'article mesure ce chargement de signe opposé, et il ne le trouve
significatif qu'en regardant tous les marchés ensemble (p. 930-931, 958-964).

Reste que ce mécanisme n'explique qu'une partie. Les auteurs écrivent eux-mêmes que le
risque de liquidité n'explique qu'une petite fraction des primes. Le chargement négatif
de la valeur rend même la prime de valeur plus énigmatique. Et la combinaison 50/50,
immunisée contre le risque de liquidité, garde un alpha substantiel (p. 931).

Ce qui ferait disparaître le gain de diversification est identifié dans l'article même,
et c'est le point le plus utile pour nous. Une part de la corrélation négative est
mécanique : le ratio valeur comptable sur valeur de marché porte le prix courant au
dénominateur, et le signal de momentum porte ce même prix au numérateur. Un titre qui
monte devient donc simultanément cher et gagnant. Les auteurs retardent d'un an le prix
utilisé dans le ratio, de sorte que les deux signaux ne partagent plus aucune donnée de
prix. La corrélation passe alors de -0,53 à -0,28 (p. 950, rapporté). Autrement
dit, à peu près la moitié de la corrélation négative vient du chevauchement des deux
formules, et non d'un mécanisme économique. Un praticien qui construit sa valeur sur
un prix décalé récupère un gain de diversification bien plus faible.

Deuxième cause de disparition possible, documentée par les auteurs sur leur propre
échantillon : l'arrivée de capital d'arbitrage fait monter la corrélation des
stratégies entre marchés. La corrélation moyenne entre stratégies de valeur passe de
0,31 sur 1972-1991 à 0,71 sur 1992-2011. Celle des stratégies de momentum passe de 0,46 à
0,77 (table VII, panneau A, rapporté). Le gain de diversification géographique s'érode
donc, même si la corrélation valeur-momentum se creuse en sens inverse et compense.

## Les données

Toutes les séries sont mensuelles et s'arrêtent en juillet 2011. Les dates de début
diffèrent par marché, ce qui interdit de traiter l'échantillon comme un panneau
équilibré.

| Marché | Période | Source des prix et rendements | Source des valeurs comptables |
|---|---|---|---|
| Actions américaines | 01/1972 à 07/2011 | CRSP, codes de titre 10 et 11 | Compustat |
| Actions britanniques | 01/1972 à 07/2011 | Datastream | Worldscope |
| Actions européennes | 01/1974 à 07/2011 | Datastream | Worldscope |
| Actions japonaises | 01/1974 à 07/2011 | Datastream | Worldscope |
| Contrats à terme sur indices pays | 01/1978 à 07/2011 | MSCI et Bloomberg | MSCI |
| Devises | 01/1979 à 07/2011 | Datastream (comptant), MSCI et Libor | sans objet |
| Obligations d'État | 01/1982 à 07/2011 | Bloomberg, Morgan Markets | sans objet |
| Contrats à terme sur matières premières | 01/1972 à 07/2011 | LME, ICE, CME, CBOT, NYMEX, COMEX, NYBOT, TOCOM | sans objet |

Les prévisions d'inflation utilisées pour la valeur obligataire viennent des
estimations d'analystes compilées par Consensus Economics (p. 936).

Les rendements de contrats à terme sur matières premières composent les rendements
quotidiens du contrat le plus liquide. Ce contrat est généralement le plus proche ou le
deuxième plus proche de l'échéance. Le rendement de la marge n'est pas inclus
(p. 935-936).

## L'univers

Huit marchés, choisis pour être liquides et donc conservateurs. Les auteurs restreignent
l'univers d'actions à peu près au quintile supérieur de chaque marché, ce qui affaiblit
volontairement les primes mesurées.

- **Actions individuelles**, quatre marchés. La règle de filtrage est explicite. Les
  titres sont classés par capitalisation de début de mois en ordre décroissant. L'univers
  retient ensuite le nombre de titres qui cumulent 90 % de la capitalisation totale du
  marché (p. 933-934). Sont exclus les certificats américains d'actions étrangères, les
  sociétés immobilières cotées, les financières, les fonds fermés, les actions
  étrangères et les titres sous un dollar. Un titre doit avoir une valeur comptable des
  six mois précédents et douze mois d'historique de rendement. Cet univers représente en
  moyenne les 17 % plus grandes sociétés aux États-Unis, et les 13 %, 20 % et 26 % au
  Royaume-Uni, en Europe et au Japon (p. 934-935). Nombre moyen de titres, et minimum
  entre parenthèses : 724 (354) aux États-Unis, 147 (76) au Royaume-Uni, 290 (96) en
  Europe, 471 (148) au Japon. L'univers américain compte 354 sociétés en janvier 1972 et
  676 en juillet 2011, donc plus large et plus liquide que le Russell 1000 (p. 934).
- **Indices actions par pays** : 18 marchés développés, minimum 8 à un instant donné,
  les 18 disponibles après 1980. Cinq d'entre eux (Autriche, Belgique, Danemark,
  Norvège, Portugal) ne sont pas des contrats à terme mais des swaps sur indice
  (p. 935).
- **Devises** : 10, minimum 7, les 10 disponibles après 1980 (p. 935).
- **Obligations d'État** : 10 pays, minimum 5, les 10 disponibles après 1990 (p. 936).
- **Matières premières** : 27 contrats, minimum 10, les 27 disponibles après 1995
  (p. 936).

De ces huit marchés, les auteurs tirent 48 actifs de test : 3 portefeuilles (bas, moyen,
haut) x 2 caractéristiques x 8 classes d'actifs (p. 938).

## La méthodologie

Les signaux sont volontairement les plus banals possibles, pour limiter le pêchage de
données, c'est-à-dire la sélection d'une règle parce qu'elle a bien marché dans
l'échantillon.

**Momentum**, identique partout : rendement cumulé des douze derniers mois en sautant le
mois le plus récent, noté MOM2-12. Le saut sert à éviter le renversement à un mois
(p. 937). Les auteurs signalent que le momentum est plus fort sans ce saut hors actions,
donc que leur choix est conservateur.

**Valeur**, une définition par classe d'actif :

- actions : ratio valeur comptable sur valeur de marché, la valeur comptable retardée de
  six mois pour garantir sa disponibilité, la valeur de marché prise à la date courante ;
- indices pays : le même ratio du mois précédent, calculé sur l'indice MSCI du pays ;
- matières premières : logarithme du prix comptant d'il y a cinq ans (moyenne de 4,5 à
  5,5 ans) divisé par le prix comptant courant ;
- devises : opposé du rendement à cinq ans du taux de change, corrigé de l'écart
  d'inflation, donc la variation à cinq ans de la parité de pouvoir d'achat ;
- obligations : variation à cinq ans du taux des obligations à dix ans.

**Construction des portefeuilles.** Dans chaque marché, les titres sont classés puis
coupés en trois groupes égaux. Les actions sont pondérées par leur capitalisation en
début de mois, les autres classes à poids égaux. Les auteurs rapportent à la fois
l'écart haut moins bas (P3-P1) et un portefeuille pondéré par le rang, appelé « facteur ».
Les moyennes mondiales pondèrent chaque marché par l'inverse de son écart type
d'échantillon (note 11, p. 945).

**Rendements bruts.** Aucune de ces performances n'est nette de coûts de transaction.
Les auteurs l'écrivent explicitement (p. 976). Ils renvoient à Frazzini, Israel et
Moskowitz (2012) pour l'argument que les coûts réels d'une grande institution sont bien
inférieurs aux modèles calibrés de Korajczyk et Sadka (2004) et de Lesmond, Schill et
Zhou (2003).

## Les équations qui comptent

Le poids du titre \(i\) à la date \(t\), pour le signal \(S\) qui vaut valeur ou momentum,
est proportionnel à son rang moins le rang moyen :

\[
w^{S}_{it} = c_t \left( \operatorname{rang}(S_{it}) - \frac{\sum_i \operatorname{rang}(S_{it})}{N} \right)
\]

La constante \(c_t\) met le portefeuille à un dollar long et un dollar court, et les poids
somment à zéro (équation 1, p. 938). Le rendement du facteur suit :

\[
r^{S}_{t} = \sum_i w^{S}_{it}\, r_{it}, \qquad S \in \{\text{valeur}, \text{momentum}\}
\]

La combinaison 50/50, celle qui porte le résultat de l'article, est la moyenne simple :

\[
r^{COMBO}_{t} = 0{,}5\, r^{VALEUR}_{t} + 0{,}5\, r^{MOM}_{t}
\]

Le modèle à trois facteurs régresse chacun des 48 portefeuilles de test sur le marché
mondial et sur les deux facteurs agrégés à travers toutes les classes d'actifs :

\[
R^{p}_{i,t} - r_{f,t} = \alpha^{p}_{i} + \beta^{p}_{i} MKT_t + v^{p}_{i} VAL^{\text{everywhere}}_{t} + m^{p}_{i} MOM^{\text{everywhere}}_{t} + \varepsilon^{p}_{i,t}
\]

où les deux facteurs mondiaux sont des moyennes pondérées par volatilité égale à travers
les huit classes (équation 5, p. 966).

## Les résultats originaux

Tous les chiffres de cette section sont **rapportés**, lus dans la version publiée
consultée le 2026-09-01. Aucun n'a été recalculé.

### La corrélation négative entre valeur et momentum, par classe d'actif

C'est le résultat qui nous intéresse. La table I donne la corrélation des rendements
résiduels de la valeur et du momentum dans chaque marché, pour les deux constructions
de portefeuille.

| Marché | Corrélation (P3-P1) | Corrélation (facteur) |
|---|---|---|
| Actions américaines | -0,53 | -0,65 |
| Actions britanniques | -0,43 | -0,62 |
| Actions européennes | -0,52 | -0,55 |
| Actions japonaises | -0,60 | -0,64 |
| Actions, agrégat mondial | -0,52 | -0,60 |
| Indices actions par pays | -0,34 | -0,37 |
| Devises | -0,42 | -0,43 |
| Obligations d'État | -0,17 | -0,35 |
| Matières premières | -0,39 | -0,46 |
| Hors actions, agrégat | -0,40 | -0,49 |
| Toutes classes d'actifs | -0,53 | -0,60 |

Le texte résume les quatre marchés d'actions par une corrélation « en moyenne autour de
-0,60 » (p. 945). Les obligations sont l'exception : -0,17 sur l'écart haut moins bas,
la corrélation la moins négative du tableau.

Avec des mesures de valeur obligataire différentes, le signe s'inverse même. La table I,
panneau C, donne +0,22 (P3-P1) pour la valeur définie comme l'écart de terme, et +0,03
pour la moyenne composite des trois mesures. Une réplication qui choisirait une autre
définition de la valeur obligataire n'obtiendrait donc pas la corrélation négative.

### Les corrélations croisées entre marchés

La table II, panneau A, calcule les corrélations sur rendements trimestriels, pour
atténuer les décalages de fuseau horaire.

| | Valeur actions | Valeur hors actions | Momentum actions | Momentum hors actions |
|---|---|---|---|---|
| Valeur actions | 0,68 | 0,15 | -0,53 | -0,26 |
| Valeur hors actions | | 0,07 | -0,16 | -0,13 |
| Momentum actions | | | 0,65 | 0,37 |
| Momentum hors actions | | | | 0,21 |

Les cases en diagonale ne sont pas des unités : ce sont les corrélations moyennes de
chaque marché avec la moyenne des autres marchés du même groupe, le marché lui-même
exclu (p. 948-950). Toutes les valeurs du tableau sauf 0,07 sont significatives au seuil
de 5 % selon le test F joint rapporté par les auteurs.

### Le gain de diversification

Le ratio de Sharpe annualisé de la combinaison dépasse celui de chaque composante, dans
chacun des huit marchés. Colonne « facteur » de la table I :

| Marché | Valeur | Momentum | Combinaison 50/50 |
|---|---|---|---|
| Actions américaines | 0,26 | 0,45 | 0,86 |
| Actions britanniques | 0,38 | 0,48 | 1,07 |
| Actions européennes | 0,54 | 0,75 | 1,20 |
| Actions japonaises | 0,77 | 0,13 | 0,88 |
| Actions, agrégat mondial | 0,51 | 0,59 | 1,28 |
| Indices actions par pays | 0,60 | 0,63 | 1,00 |
| Devises | 0,44 | 0,32 | 0,69 |
| Obligations d'État | 0,07 | 0,17 | 0,20 |
| Matières premières | 0,31 | 0,51 | 0,77 |
| Hors actions, agrégat | 0,55 | 0,62 | 1,14 |
| Toutes classes d'actifs | 0,72 | 0,74 | 1,59 |

Le chiffre à retenir est le dernier : 1,59 pour la combinaison mondiale, contre 0,72 et
0,74 pour ses deux jambes. Sur l'écart haut moins bas, les mêmes trois chiffres valent
0,73, 0,67 et 1,42. Le rendement moyen annualisé du facteur combiné mondial est de 6,8 %
pour un écart type de 4,3 %, avec un t de Student de 9,83.

Le Japon donne le cas d'école. Le momentum y rapporte un ratio de Sharpe de 0,13, non
significatif (t de 0,81), mais la valeur y atteint 0,77, et la combinaison 0,88, soit
plus que la valeur seule. Un poids positif sur un momentum non rentable améliore donc
la frontière, ce que les auteurs confirment par optimisation statique (p. 945).

### Le modèle à trois facteurs

Sur les 48 actifs de test, le modèle à trois facteurs donne un \(R^2\) transversal de
0,71 et un alpha absolu moyen de 18 points de base par mois (p. 966). La table VI le
compare aux autres modèles :

| Modèle | Statistique F de GRS | Valeur p | Alpha absolu moyen | \(R^2\) transversal |
|---|---|---|---|---|
| MEDAF mondial | 6,02 | 0,000 | 0,0035 | 0,52 |
| Marché plus risque de liquidité | 5,02 | 0,000 | 0,0031 | 0,54 |
| Six facteurs macroéconomiques | 4,09 | 0,000 | 0,0027 | 0,56 |
| Marché, valeur et momentum partout | 2,66 | 0,000 | 0,0018 | 0,72 |
| Fama-French à quatre facteurs | 6,70 | 0,000 | 0,0035 | 0,55 |

Le modèle proposé fait mieux que tous les autres sur les trois colonnes. Il reste rejeté :
la valeur p du test de Gibbons, Ross et Shanken vaut 0,000, comme pour tous les modèles
du tableau. Les auteurs présentent donc un modèle qui domine, pas un modèle qui tient.

## Les critiques connues

**La corrélation négative est en partie une identité comptable, et l'article le montre.**
Retarder d'un an le prix dans le ratio valeur comptable sur valeur de marché fait passer
la corrélation valeur-momentum de -0,53 à -0,28 (p. 950). Ce n'est pas une critique
externe, c'est un contrôle des auteurs, mais il borne fortement l'interprétation
économique du résultat principal.

**Le modèle n'apporte rien à l'intérieur d'une classe d'actif, et le MEDAF fait presque
aussi bien entre classes.** Dobrynskaya (2018), « Pricing within and across asset
classes », Finance Research Letters, vol. 25, p. 10-15, DOI 10.1016/j.frl.2017.09.017,
compare les deux modèles sur des portefeuilles de valeur et de momentum. Le MEDAF y est
presque aussi bon que le modèle des trois auteurs pour expliquer les rendements à travers
les classes d'actifs. Leur modèle y est presque aussi mauvais que le MEDAF pour les
expliquer à l'intérieur d'une seule classe. Conclusion lue dans le résumé publié, page
RePEc consultée le 2026-09-01 ; le texte intégral n'a pas été consulté, la page
ScienceDirect répondant 403.

**Le momentum s'effondre par crises.** Daniel et Moskowitz, « Momentum crashes », Journal
of Financial Economics, vol. 122, 2016, p. 221-247, DOI 10.1016/j.jfineco.2015.12.002,
documentent des effondrements du momentum concentrés dans les états de panique. Ceux-ci
suivent une baisse de marché, arrivent par forte volatilité et coïncident avec les
reprises. Caractérisation lue
dans le résumé publié le 2026-09-01 ; le texte intégral n'a pas été consulté. Le coauteur
est le même que celui de l'article de 2013.

**Les coûts de transaction sont hors du tableau.** L'article travaille en rendements
bruts et le dit (p. 976). Le débat existant est cité dans l'article. Korajczyk et Sadka
(2004) et Lesmond, Schill et Zhou (2003) concluent que les capacités du momentum sont
faibles. Frazzini, Israel et Moskowitz (2012), tous liés à AQR, concluent l'inverse à
partir de données de transactions réelles. Deux sources se contredisent, et l'article
tranche pour celle de ses auteurs.

**La crise de réplication en finance.** Hou, Xue et Zhang, « Replicating anomalies »,
Review of Financial Studies, vol. 33, 2020, p. 2019-2133, DOI 10.1093/rfs/hhy131,
échouent à répliquer une majorité d'anomalies publiées. Jensen, Kelly et Pedersen,
« Is there a replication crisis in finance? », Journal of Finance, 2023, DOI
10.1111/jofi.13249, répondent que la plupart des facteurs survivent, Pedersen étant
coauteur de l'article de 2013. Les deux camps sont vérifiés par Crossref et par la page
Wiley ; ni l'un ni l'autre n'a été consulté au fond.

**Le comportement après publication n'est pas dans l'article.** L'échantillon s'arrête
en juillet 2011 et la valeur a connu ensuite un recul long, discuté chez Israel, Laursen
et Richardson, « Is (systematic) value investing dead? », 2020, DOI
10.2139/ssrn.3554267. Référence vérifiée par Crossref, article non consulté. Aucun
chiffre de performance postérieure à 2011 n'est avancé ici.

## Les problèmes de réplication connus

**Le noyau des données n'est pas public.** Huit fournisseurs se partagent les entrées.
Le côté américain repose sur CRSP et Compustat. Les trois autres marchés d'actions
reposent sur Datastream et Worldscope. Les indices viennent de MSCI, les taux de
Bloomberg et de Morgan Markets, les prévisions d'inflation de Consensus Economics.
Aucune de ces huit sources n'est gratuite. Une réplication à partir de zéro est donc hors
de portée sans budget de données.

**Les facteurs eux-mêmes sont publiés, pas leurs entrées.** AQR diffuse les facteurs VME
mensuels depuis janvier 1972, mis à jour, ainsi que le jeu de données original de
l'article, arrêté en juillet 2011. Page consultée le 2026-09-01. Cela permet de vérifier
les corrélations et les ratios de Sharpe publiés, mais pas de reconstruire les
portefeuilles ni de tester une variante de signal.

**La règle d'univers, elle, est publiée en clair.** L'univers retient les titres qui
cumulent 90 % de la capitalisation du marché. Cela donne une cible de contrôle
vérifiable, à savoir 354 titres américains en janvier 1972 et 676 en juillet 2011. Une
réplication qui n'obtient pas ces deux comptes s'est trompée de filtre avant de calculer
le moindre rendement.

**L'annexe internet porte plusieurs contrôles cités dans le texte.** Les corrélations
individuelles par paire, le contrôle du prix retardé d'un an et la mesure de valeur par
rendement passé à cinq ans y sont, et non dans l'article. Cette annexe n'a pas été
consultée au 2026-09-01.

## Les biais possibles

**Choix des mesures de valeur par classe d'actif.** Cinq définitions différentes de la
valeur cohabitent, chacune choisie pour ressembler à l'esprit du ratio comptable. Les
auteurs plaident la simplicité contre le pêchage de données, mais rien ne prouve que ces
cinq définitions aient été fixées avant de voir les résultats. Le panneau C montre que
le choix compte. Selon la mesure retenue pour les obligations, le ratio de Sharpe de la
valeur passe de 0,07 à 1,10, et la corrélation avec le momentum de -0,17 à +0,22.

**Survie et disponibilité hors États-Unis.** CRSP est construit pour éviter le biais de
survie, c'est-à-dire l'exclusion des sociétés disparues. Datastream et Worldscope, qui
couvrent les trois autres marchés, n'offrent pas la même garantie et leur couverture
historique s'améliore avec le temps. L'article ne traite pas ce point.

**Panneau déséquilibré.** Les huit marchés commencent entre 1972 et 1982. Les moyennes
mondiales des premières années reposent donc sur les seuls actions et matières premières.
Toute lecture d'un rendement mondial avant 1982 mélange deux compositions différentes.

**Chevauchement des signaux.** Déjà cité en intuition, ce biais mérite d'être compté
comme tel : la corrélation négative est en partie une conséquence de la construction, et
le gain de diversification en hérite.

**Conflit d'intérêts déclaré.** Asness est à AQR, Pedersen à AQR et dans deux
universités, Moskowitz est consultant d'AQR (note de première page). AQR vend des
stratégies de valeur et de momentum. Le fait est déclaré dans l'article, il n'invalide
rien, il oriente le choix des contrôles.

## Nos décisions d'implémentation

Non commencé au 2026-09-01.

## Nos écarts avec l'article

Non commencé au 2026-09-01.

## Nos résultats

Non commencé au 2026-09-01.

## Notre contrôle de robustesse

Non commencé au 2026-09-01.

## Références

Sources consultées de première main le 2026-09-01 :

- Asness, C. S., Moskowitz, T. J. et Pedersen, L. H. (2013). « Value and Momentum
  Everywhere ». The Journal of Finance, 68(3), 929-985. DOI 10.1111/jofi.12021.
  Texte intégral lu à l'adresse
  <https://w4.stern.nyu.edu/facdir/lpederse/papers/ValMomEverywhere.pdf>.
- AQR Capital Management. « Value and Momentum Everywhere: Factors, Monthly ».
  <https://www.aqr.com/Insights/Datasets/Value-and-Momentum-Everywhere-Factors-Monthly>.
  Facteurs depuis janvier 1972, mise à jour indiquée au 2026-06-30.
- AQR Capital Management. « Value and Momentum Everywhere », page de l'article.
  <https://www.aqr.com/Insights/Research/Journal-Article/Value-and-Momentum-Everywhere>.

Références citées par métadonnées vérifiées mais non consultées au fond :

- Dobrynskaya, V. (2018). « Pricing within and across asset classes ». Finance Research
  Letters, 25, 10-15. DOI 10.1016/j.frl.2017.09.017. Résumé lu sur
  <https://ideas.repec.org/a/eee/finlet/v25y2018icp10-15.html> ; page ScienceDirect en 403.
- Daniel, K. et Moskowitz, T. J. (2016). « Momentum crashes ». Journal of Financial
  Economics, 122(2), 221-247. DOI 10.1016/j.jfineco.2015.12.002. Résumé lu, texte
  intégral non consulté.
- Hou, K., Xue, C. et Zhang, L. (2020). « Replicating anomalies ». The Review of
  Financial Studies, 33(5), 2019-2133. DOI 10.1093/rfs/hhy131.
- Jensen, T. I., Kelly, B. et Pedersen, L. H. (2023). « Is there a replication crisis in
  finance? ». The Journal of Finance. DOI 10.1111/jofi.13249.
- Israel, R., Laursen, K. et Richardson, S. A. (2020). « Is (systematic) value investing
  dead? ». DOI 10.2139/ssrn.3554267.

Références internes à l'article de 2013, citées telles qu'elles y figurent :

- Frazzini, A., Israel, R. et Moskowitz, T. J. (2012). « Trading costs of asset pricing
  anomalies ».
- Korajczyk, R. A. et Sadka, R. (2004). « Are momentum profits robust to trading
  costs? ». Journal of Finance.
- Lesmond, D. A., Schill, M. J. et Zhou, C. (2003), cité p. 976.
- Gibbons, M. R., Ross, S. A. et Shanken, J. (1989), test joint des alphas.

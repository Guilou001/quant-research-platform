# Le seuil de t après correction pour tests multiples

| | |
|---|---|
| **Auteurs** | Campbell R. Harvey, Yan Liu et Heqing Zhu. Compléments méthodologiques : Halbert White (2000) et Peter Reinhard Hansen (2005) |
| **Année** | 2016 pour Harvey, Liu et Zhu ; 2000 pour White ; 2005 pour Hansen |
| **Revue ou source** | *Review of Financial Studies*, vol. 29, n° 1, p. 5-68. *Econometrica*, vol. 68, p. 1097-1126. *Journal of Business & Economic Statistics*, vol. 23, n° 4, octobre 2005 |
| **Lien** | [NBER 20592](https://www.nber.org/system/files/working_papers/w20592/w20592.pdf), [SSRN 2249314](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2249314), [Hansen, dépôt UNC](https://cdr.lib.unc.edu/downloads/zp38wf793) |
| **Statut de réplication** | non commencé |

Avertissement de source, à lire avant tout chiffre. La version consultée en
entier de Harvey, Liu et Zhu est le document de travail NBER n° 20592, daté
d'octobre 2014, 101 pages. La version publiée dans la *Review of Financial
Studies* n'a PAS été consultée. Tous les nombres de cette fiche viennent donc du
document de travail, et un écart avec la version publiée est possible. La
référence de revue est **rapportée**, lue sur RePEc le 2026-09-01.

L'article de White (2000) n'a pas été consulté. Sa formulation est reprise de
Hansen (2005), consulté en entier, et d'un article appliqué de Hsu et Kuan qui
la restitue.

## La question de recherche

Quel seuil de t un facteur nouvellement découvert doit-il franchir, une fois pris
en compte que des centaines d'autres ont été essayés sur les mêmes données ?

Le t de Student, rapport d'un coefficient estimé à son erreur type, sert depuis
toujours de juge à 1,96. Les auteurs posent qu'après des centaines de tentatives
sur le même échantillon, ce seuil n'a plus aucun sens économique ni statistique.
Leur question porte donc sur la valeur du seuil, et sur son évolution dans le
temps à mesure que le nombre de facteurs publiés augmente.

White (2000) et Hansen (2005) posent une question voisine dans un autre cadre.
Parmi \(m\) modèles de prévision comparés à un repère, existe-t-il au moins un
modèle réellement supérieur, une fois corrigé le fait qu'on ait cherché le
meilleur ?

## L'intuition économique

Le rendement d'un facteur publié devrait exister moins souvent que son t de
Student ne le suggère, et la raison n'est pas économique mais institutionnelle.

Le mécanisme a deux temps. Premier temps, la multiplicité : tester \(M\)
hypothèses au seuil individuel de 5 % garantit qu'environ \(0{,}05 M\) d'entre
elles seront déclarées significatives par pur hasard. Avec 316 facteurs testés,
cela fait une quinzaine de faux positifs attendus, sans qu'aucun mécanisme réel
n'existe.

Second temps, la contrainte institutionnelle, et c'est elle qui décide. La
culture de la recherche en finance récompense la découverte d'un facteur neuf et
ne publie presque jamais une réplication ou un échec. Les essais ratés restent
donc dans le tiroir. Le lecteur ne voit qu'un échantillon trié, et le
dénominateur du calcul de multiplicité lui est caché.

Qu'est-ce qui ferait disparaître le phénomène ? Un registre public des essais,
sur le modèle de l'enregistrement préalable des essais cliniques, qui rendrait
\(M\) observable. Ou une norme de publication qui accepte les résultats négatifs.
Les auteurs notent que ni l'une ni l'autre n'existe en finance, alors que la
médecine s'y est mise.

Une objection s'impose ici, et elle est réelle. Si les facteurs publiés étaient
majoritairement des flukes, leurs rendements devraient s'effondrer après
publication. Chen et Zimmermann (2020) mesurent que la correction pour biais de
publication ne retire que 12,3 % du rendement en échantillon. La section sur les
critiques y revient.

## Les données

Les données de Harvey, Liu et Zhu sont bibliographiques, non financières. Ils
recensent à la main les t de Student publiés dans la littérature sur la coupe
transversale des rendements.

Le recensement porte sur 313 travaux publiés ou en document de travail, et
catalogue 316 facteurs distincts. Le premier test empirique retenu remonte à
1967. Ces trois nombres sont **rapportés**, lus aux pages 3 et 21 du document
NBER. La liste complète des facteurs, avec citations et hyperliens, est publiée
par les auteurs sous forme de classeur téléchargeable.

Les auteurs déclarent une limite majeure : leur collection sous-représente la
population des facteurs, parce que seuls les facteurs publiés y figurent et que
les revues privilégient les grandes revues. Leur seuil est donc un MINORANT du
vrai seuil.

Une seconde source apparaît en section 5.3 : la base S&P Capital IQ, plus de 400
facteurs d'actions américaines sur 1985-2014, sert à estimer la corrélation
moyenne entre rendements de facteurs. Statut **rapporté**.

Hansen (2005) applique sa méthode à des prévisions de l'inflation annuelle
américaine comparées à une marche aléatoire. White (2000) est appliqué par
Sullivan, Timmermann et White (1999) à des règles d'analyse technique. Aucune de
ces deux bases n'a été consultée.

## L'univers

L'unité d'observation est le facteur, c'est-à-dire une variable proposée pour
expliquer la coupe transversale des rendements espérés. L'univers est la
littérature elle-même.

Les auteurs distinguent deux façons de produire un t pour un facteur. La voie
dite de gauche régresse les rendements d'un portefeuille long-court sur des
facteurs de risque usuels et prend le t de la constante. La voie dite de droite
utilise les sensibilités comme variables explicatives et prend le t de la prime
de risque. Ils privilégient la seconde, et se rabattent sur la première quand
elle manque.

Ils comptent aussi 113 facteurs qualifiés de « communs », par opposition aux
facteurs propres à une entreprise. Ce sous-ensemble sert de contrôle de
robustesse contre le reproche de surcompter.

Pour White et Hansen, l'univers est un ensemble de \(m\) modèles de prévision ou
de règles de négociation, comparés à un repère unique déclaré à l'avance.

## La méthodologie

Trois corrections classiques sont appliquées à la même série de valeurs p, puis
retraduites en t.

La procédure est décrite page 23 du document NBER. À chaque date, l'ensemble des
t disponibles est converti en valeurs p. Les trois méthodes d'ajustement
produisent des valeurs p de référence. Celles-ci sont reconverties en t, en
supposant que la loi normale centrée réduite approche bien la loi de Student. Le
résultat est extrapolé linéairement sur vingt ans.

Deux notions de risque d'erreur cohabitent, et les confondre fausse tout.
L'erreur de première espèce par famille, la probabilité qu'au moins une hypothèse
nulle vraie soit rejetée, est contrôlée par Bonferroni et par Holm. Le taux de
fausses découvertes, la proportion attendue de faux positifs parmi les rejets,
est contrôlé par Benjamini, Hochberg et Yekutieli.

Les seuils retenus pour les résultats principaux sont 5 % pour l'erreur par
famille et 1 % pour le taux de fausses découvertes. Le second est plus strict
parce que le taux de fausses découvertes est un contrôle plus faible. Au seuil de
5 %, il ne trierait plus rien de plus que le test individuel.

Deux extensions occupent la seconde moitié de l'article. La section 4.7.2 traite
le cas où le nombre d'essais dépasse le nombre de découvertes, par une simulation
qui reconstruit la loi sous-jacente des t de tous les essais tentés. La section 5
construit un modèle structurel qui incorpore la corrélation entre rendements de
stratégies contemporaines, sans exiger de disposer des séries elles-mêmes.

White (2000) et Hansen (2005) suivent une autre voie, celle de l'amorce. Plutôt
que d'ajuster des valeurs p analytiquement, ils rééchantillonnent les séries de
performance relative pour construire la loi du maximum sous l'hypothèse nulle.

## Les équations qui comptent

Notation. \(M\) est le nombre d'hypothèses testées, \(p_i\) la valeur p du test
\(i\), et \(p_{(1)} \leq p_{(2)} \leq \cdots \leq p_{(M)}\) les valeurs p
ordonnées. \(\alpha_w\) est le seuil pour l'erreur par famille, \(\alpha_d\) le
seuil pour le taux de fausses découvertes.

**Bonferroni.** Rejeter toute hypothèse dont la valeur p ne dépasse pas
\(\alpha_w / M\). La valeur p ajustée est :

\[
p_i^{\text{Bonferroni}} = \min\left[M\,p_i,\; 1\right]
\]

Cette procédure contrôle l'erreur par famille au niveau \(M_0 \alpha_w / M\), où
\(M_0\) est le nombre d'hypothèses nulles vraies, sans aucune hypothèse sur la
structure de dépendance.

**Holm.** Ordonner les valeurs p. Soit \(k\) le plus PETIT indice tel que
\(p_{(k)} > \alpha_w / (M+1-k)\). Rejeter \(H_{(1)}, \ldots, H_{(k-1)}\) et
conserver les suivantes. La valeur p ajustée est :

\[
p_{(i)}^{\text{Holm}} = \min\left[\max_{j \leq i}\left\{(M-j+1)\,p_{(j)}\right\},\; 1\right]
\]

Pour \(k=1\) Holm coïncide avec Bonferroni. Au-delà, le seuil est moins strict,
donc Holm découvre au moins autant que Bonferroni.

**Benjamini, Hochberg et Yekutieli.** Ordonner les valeurs p. Soit \(k\) le plus
GRAND indice tel que \(p_{(k)} \leq \dfrac{k}{M \times c(M)}\alpha_d\). Rejeter
\(H_{(1)}, \ldots, H_{(k)}\). La valeur p ajustée se définit à rebours, en
partant de la plus grande :

\[
p_{(i)}^{\text{BHY}} =
\begin{cases}
p_{(M)} & \text{si } i = M,\\[4pt]
\min\left[p_{(i+1)}^{\text{BHY}},\; \dfrac{M \times c(M)}{i}\,p_{(i)}\right]
& \text{si } i \leq M-1,
\end{cases}
\qquad
c(M) = \sum_{j=1}^{M} \frac{1}{j}
\]

Le choix de \(c(M)\) décide de la généralité. Avec \(c(M) = 1\), la procédure ne
vaut que sous indépendance ou dépendance positive. Avec la somme harmonique
ci-dessus, elle vaut sous toute forme de dépendance.

**Contrôle de Bonferroni sous indépendance**, note 38 du document. Avec \(n\)
tests indépendants et toutes les nulles vraies :

\[
FWER = 1 - \left(1-\frac{\alpha}{n}\right)^{n}
\;\xrightarrow[n \to \infty]{}\; 1 - e^{-\alpha} \approx \alpha
\]

**Statistique du contrôle de réalité de White**, telle que Hansen (2005) la pose.
Soit \(d_{k,t}\) la performance du modèle \(k\) relativement au repère à la date
\(t\), \(\bar{d}_k\) sa moyenne sur \(n\) observations, et
\(\mu = E(d_t)\). L'hypothèse nulle est \(\mu \leq 0\), soit l'absence de modèle
supérieur au repère, et la statistique est :

\[
T_n^{RC} = \max\left(n^{1/2}\bar{d}_1, \ldots, n^{1/2}\bar{d}_m\right)
\]

Sa loi sous la nulle est obtenue par amorce stationnaire. À la réplique \(j\), on
recentre chaque moyenne rééchantillonnée sur la moyenne observée :

\[
V_n^{*}(j) = \max_{k=1,\ldots,m} \sqrt{n}\left(\bar{f}_k^{*}(j) - \bar{f}_k\right),
\qquad j = 1, \ldots, B
\]

et la valeur p se lit en situant la statistique observée dans cette distribution
empirique.

**Statistique de capacité prédictive supérieure de Hansen.** Elle studentise
chaque moyenne par son écart type, où \(\hat{\omega}_k^2\) estime
\(\omega_k^2 \equiv \mathrm{var}(n^{1/2}\bar{d}_k)\) :

\[
T_n^{SPA} = \max\left(\max_{k=1,\ldots,m}\frac{n^{1/2}\bar{d}_k}{\hat{\omega}_k},\; 0\right)
\]

**Recentrage de Hansen.** La loi de référence n'est plus centrée en zéro pour
tous les modèles, mais en un estimateur de \(\mu\) compatible avec la nulle. Le
choix recommandé laisse à zéro les modèles dont la statistique studentisée reste
au-dessus du seuil, et conserve la moyenne observée, très négative, pour les
autres :

\[
\hat{\mu}_k^{c} = \bar{d}_k \cdot
\mathbf{1}\!\left\{ n^{1/2}\bar{d}_k / \hat{\omega}_k \leq -\sqrt{2\log\log n} \right\}
\]

Deux variantes bornent la valeur p obtenue, l'une par le bas et l'autre par le
haut, avec \(\hat{\mu}^{l} \leq \hat{\mu}^{c} \leq \hat{\mu}^{u}\) :

\[
\hat{\mu}_k^{l} = \min(\bar{d}_k, 0), \qquad \hat{\mu}_k^{u} = 0
\]

Le second redonne exactement la configuration la moins favorable, celle que le
contrôle de réalité utilise implicitement. Hansen prévient qu'une version
antérieure de son article a été citée à tort comme « écartant les mauvais
modèles ». L'estimateur \(\hat{\mu}^{c}\) les garde tous, et c'est la raison
d'être du recentrage : un modèle légèrement négatif pèse encore sur la valeur
critique.

## Les résultats originaux

Le seuil recommandé est un t supérieur à 3,0, et ce nombre n'est PAS la sortie
d'une formule. C'est un arrondi prudent vers le bas de plusieurs seuils calculés,
et les auteurs écrivent qu'il y a de bonnes raisons de le juger trop bas.

Les seuils calculés, tous **rapportés**, lus aux pages 23, 25 et 27 du document
NBER, pour un nombre d'essais égal au nombre de découvertes :

| Procédure | Seuil de t en 2012 | Valeur p | Seuil en 2032 |
|---|---|---|---|
| Bonferroni, \(\alpha_w = 5\%\) | 3,78 | 0,02 % | 4,00 (p = 0,01 %) |
| Holm, \(\alpha_w = 5\%\), 316 facteurs | 3,64 | 0,03 % | non publié |
| Holm, \(\alpha_w = 5\%\), 113 facteurs | 3,29 | 0,10 % | non publié |
| BHY, \(\alpha_d = 1\%\) | 3,39 | 0,07 % | non publié |
| BHY, \(\alpha_d = 5\%\) | 2,78 | 0,54 % | 2,81 (p = 0,50 %) |

Le seuil de Bonferroni part de 1,96 en début de période et croît de façon
monotone avec le nombre de découvertes. Celui de BHY ne croît pas : il fluctue
avant 2000 puis se stabilise à 3,39 après 2010, propriété que les auteurs
rattachent à la loi des grands nombres appliquée au taux de fausses découvertes.

Les seuils calculés quand le nombre d'essais dépasse le nombre de découvertes,
par la simulation de l'appendice A, également **rapportés** :

| Procédure | Seuil de t |
|---|---|
| Bonferroni | 4,01 |
| Holm | 3,96 |
| BHY, \(\alpha_d = 1\%\) | 3,68 |
| BHY, \(\alpha_d = 5\%\) | 3,18 |

Cette simulation estime que 71 % de tous les facteurs essayés manquent à
l'appel. La phrase des auteurs est explicite. Le seuil minimal est 3,18, celui de
BHY au seuil de 5 % dans le cas où des essais sont cachés, et toutes les autres
configurations donnent des seuils plus élevés.

Le chiffre de 3,0 correspond à une valeur p de 0,27 %, **rapporté** en
conclusion. Il est donc plus bas que 3,18, plus bas que 3,39 et plus bas que
3,78. C'est une recommandation, pas un résultat de calcul, et la fiche doit le
dire au lecteur qui voudra l'implémenter.

**Combien de facteurs publiés tombent ?** Sur 296 facteurs déclarés significatifs,
158 seraient de fausses découvertes sous Bonferroni, 142 sous Holm, 132 sous BHY
à 1 % et 80 sous BHY à 5 %. **Rapporté**, page 35.

**Corrélation entre facteurs.** La fonction objectif du modèle structurel atteint
son minimum pour une corrélation moyenne de 0,20. La base S&P Capital IQ donne
environ 0,15 sur 1985-2014. Quatre travaux sont cités. McLean et Pontiff (2014)
donnent 0,05, Green, Hand et Zhang (2012) une fourchette de 0,06 à 0,20. Barras,
Scaillet et Wermers (2010) plaident pour une corrélation nulle entre rendements
de fonds, et Ferson et Chen (2013) pour une fourchette de 0,04 à 0,09. Les
auteurs concluent à une corrélation faible, voisine de 0,20.

**Un contrôle par une quatrième méthode.** Le contrôle de la proportion de
fausses découvertes de Lehmann et Romano donne 2,70, soit une valeur p de 0,69 %,
au seuil de 0,10 pour la proportion et de 5 % pour le test. Les auteurs
avertissent que leur définition de l'erreur de première espèce diffère, si bien
que ce seuil n'est PAS comparable aux trois autres ; ils n'en retiennent que la
concordance de la conclusion.

**Ce que les auteurs concèdent.** Un facteur dérivé d'une théorie pourrait
mériter un seuil plus bas qu'un facteur trouvé par exploration pure. Mais un t de
2,0 « n'est plus approprié », écrivent-ils, même pour un facteur théorique. Ils
notent aussi qu'environ
70 % des facteurs que leur méthode déclare vrais ont un ratio de Sharpe inférieur
à 0,5, ce qui limite la portée économique du verdict statistique.

**Résultat de Hansen (2005).** Dans un exemple stylisé à deux modèles, la
studentisation fait passer la puissance du test de niveau 5 % d'environ 15 % à
environ 53 %, soit plus du triple. **Rapporté**, figure 1 de l'article.

**Résultat théorique de Hansen, corollaire 1.** Seules les contraintes actives,
celles dont la performance relative vraie est nulle, comptent dans la loi
asymptotique. La conséquence est nette : la valeur p du contrôle de réalité peut
être gonflée artificiellement en ajoutant de mauvaises prévisions à l'ensemble
comparé, ce qui érode sa puissance jusqu'à zéro.

## Les critiques connues

Les critiques de Harvey, Liu et Zhu sont abondantes et sérieuses, et l'une d'elles
inverse la conclusion.

**Produire ces facteurs par bidouillage prendrait des siècles.** Chen (2021),
*The Journal of Finance*, 76(5), p. 2447-2480, mène l'expérience de pensée
inverse. Il suppose les 300 et quelques facteurs publiés tous faux, puis demande
combien de bidouillage de valeurs p il faudrait pour les fabriquer. Sa réponse :
avec 10 000 chercheurs produisant huit facteurs par jour, il faudrait des
centaines d'années. La raison tient à ce que des dizaines de t publiés dépassent
6,0, dont la valeur p correspondante est infinitésimale. Chen ajoute qu'une
structure plus riche laisse le bidouillage sans prise sur la centaine de t
publiés au-dessus de 4,0. Statut **rapporté**, résumé lu le 2026-09-01 sur
RePEc, article non consulté.

**Le taux de fausses découvertes est borné bas.** Chen (2022), « Most claimed
statistical findings in cross-sectional return predictability are likely true »
(arXiv 2206.15365, révision du 2025-11-19), construit deux bornes de ce taux à
partir des seules statistiques sommaires des travaux antérieurs. La borne simple
donne un taux inférieur ou égal à 25 %, donc au moins 75 % de résultats vrais, et
elle tient dans huit des neuf travaux examinés. La borne affinée donne 9 %, donc
au moins 91 % de vrais. Ce texte est un document de travail donné pour
« forthcoming » au *Journal of Finance: Insights* sur la page de son auteur,
mention **non vérifiée** auprès de la revue. Statut **rapporté**, résumé lu le
2026-09-01. Que Harvey, Liu et Zhu figurent ou non parmi les neuf travaux
examinés est **non trouvé**.

**La mesure empirique du biais de publication le contredit.** Chen et Zimmermann
(2020), *The Review of Asset Pricing Studies*, 10(2), p. 249-289, estiment les
rendements corrigés du biais de publication sur 156 portefeuilles long-court
publiés. La correction ne retire que 12,3 % du rendement en échantillon, avec une
erreur type de 1,7 point de pourcentage. Ces deux nombres sont **rapportés**, lus
le 2026-09-01 dans le résumé de l'éditeur. Leur explication est que la dispersion
des rendements entre facteurs est trop grande pour être produite par du bruit
exploré. Ils rapportent aussi qu'un seuil de t de 1,8 suffit à contrôler la
multiplicité parmi les facteurs capables de passer une évaluation par les pairs.
Ils le calculent avec les statistiques que recommandent Harvey, Liu et Zhu.
Ce dernier point est **rapporté** depuis le résumé de la version de travail de la
Réserve fédérale, mai 2018 ; il ne figure pas dans le résumé de l'éditeur.
L'article n'a pas été consulté.

**Les auteurs eux-mêmes ont changé de cadre.** Harvey et Liu (2020), *The Journal
of Finance*, 75(5), p. 2503-2553, proposent de calibrer conjointement l'erreur de
première espèce et celle de seconde espèce, par une double amorce. Leur constat
est que les méthodes existantes manquent de puissance pour détecter les gérants
performants. Autrement dit, contrôler seulement les faux positifs coûte des
découvertes manquées, et cet arbitrage est absent de l'article de 2016. Statut
**rapporté**, résumé lu, article non consulté.

**Le contrôle de réalité de White est manipulable.** C'est le corollaire 1 de
Hansen (2005), déjà cité : ajouter des modèles sans intérêt à l'ensemble comparé
augmente artificiellement la valeur p. Cette critique est établie, publiée et
vérifiée sur l'article original consulté.

**La conservation sous dépendance positive coupe dans les deux sens.** Harvey,
Liu et Zhu le reconnaissent en section 4.7.1. Si les t sont positivement
corrélés, leurs trois méthodes découvrent trop peu. Mais leur couverture
incomplète des essais joue en sens inverse. Ils ne tranchent pas, et présentent
les deux effets comme se compensant partiellement.

## Les problèmes de réplication connus

**La version consultée n'est pas la version publiée.** Le document NBER date
d'octobre 2014, la publication de 2016. Les seuils reproduits ici peuvent avoir
bougé entre les deux. Tout test qui viserait à retrouver 3,78 ou 3,39 doit
d'abord vérifier ces nombres dans la *Review of Financial Studies*.

**Le chiffre de 3,0 n'a pas de formule.** Chercher à le reproduire par un calcul
est une erreur de conception. Ce qui se reproduit, ce sont les seuils du tableau
ci-dessus, et le calcul demande la série datée des t publiés, que les auteurs
diffusent dans leur classeur.

**La reconversion des valeurs p en t suppose la normalité.** L'article le déclare
page 23 : la loi normale centrée réduite est réputée bien approcher la loi de
Student. Une implémentation qui utiliserait la vraie loi de Student, avec un
nombre de degrés de liberté propre à chaque étude, ne retrouverait pas exactement
les mêmes seuils.

**Le choix de \(c(M)\) change le résultat de BHY.** Poser \(c(M) = 1\), qui est
la version de Benjamini et Hochberg de 1995, donne des seuils moins stricts que
la somme harmonique retenue ici. Avec 316 tests, cette somme vaut environ 6,3, ce
qui multiplie par autant la sévérité du seuil. Statut **mesuré**, calcul du
2026-09-01 sur \(\sum_{j=1}^{316} 1/j\).

**Le seuil de Holm dépend du décompte des facteurs.** Passer de 316 à 113
facteurs fait tomber le seuil de 3,64 à 3,29. Le nombre de facteurs est donc un
paramètre de décision, pas une donnée neutre, et il doit être déclaré.

**La statistique de White exige un repère déclaré à l'avance.** Le repère de
Sullivan, Timmermann et White est l'absence de position, donc un rendement nul.
Changer de repère change la performance relative de tous les modèles et donc la
valeur p. Ce choix n'est pas neutre et doit être écrit dans la configuration.

**Le seuil de Hansen dépend d'un taux de convergence arbitraire.** Le seuil
\(-\sqrt{2\log\log n}\) n'est pas le seul possible : l'article mentionne qu'une
version antérieure utilisait \(\tfrac{1}{4}n^{1/4}\). Des taux différents donnent
des valeurs p différentes en échantillon fini, ce qui est exactement la raison
pour laquelle Hansen propose les deux bornes \(\hat{\mu}^{l}\) et
\(\hat{\mu}^{u}\).

## Les biais possibles

**Le dénominateur reste inconnu.** Tout repose sur \(M\), le nombre d'essais, que
personne n'observe. La simulation de l'appendice A l'estime à partir d'un modèle
de la loi des t cachés, ce qui remplace une inconnue par une hypothèse.

**Les t collectés proviennent de conventions hétérogènes.** Les auteurs
choisissent le t de la voie de droite quand il existe et celui de la voie de
gauche sinon. Ils retiennent parfois le t du rendement moyen d'une stratégie
long-court sans contrôle de risque. Ces trois quantités ne mesurent pas la même
chose.

**La dépendance entre études du même facteur est réduite mais pas éliminée.** Les
auteurs n'incluent, sauf exception, que l'article d'origine d'un facteur. Ils
reconnaissent que quelques doublons subsistent, dont quatre mesures différentes
de volatilité idiosyncratique et plusieurs ratios ayant le prix au dénominateur.

**Le seuil ne dit rien de la taille de l'effet.** Un facteur peut franchir un t
de 3,0 et garder un ratio de Sharpe de 0,3. C'est le cas d'environ 70 % des
facteurs que leur modèle déclare vrais. Un seuil statistique ne remplace pas un
critère économique.

**L'extrapolation à 2032 est une projection linéaire.** Elle suppose que le
rythme de production de facteurs des dernières années se poursuit. Statut de ces
deux nombres, 4,00 et 2,81 : **modélisé**, et non mesuré.

**Le rejet d'un facteur par une règle de multiplicité n'est pas une réfutation
économique.** La méthode dit qu'un facteur ne se distingue pas du hasard, compte
tenu du nombre d'essais. Elle ne dit pas que le mécanisme n'existe pas. La
confusion entre les deux est la lecture fautive la plus probable de cet article.

## Nos décisions d'implémentation

non commencé au 2026-09-01

## Nos écarts avec l'article

non commencé au 2026-09-01

## Nos résultats

non commencé au 2026-09-01

## Notre contrôle de robustesse

non commencé au 2026-09-01

## Références

1. Harvey, C. R., Liu, Y. et Zhu, H. (2016). « ... and the Cross-Section of
   Expected Returns ». *The Review of Financial Studies*, 29(1), p. 5-68.
   Version consultée : document de travail NBER n° 20592, octobre 2014.
   <https://www.nber.org/system/files/working_papers/w20592/w20592.pdf>
2. White, H. (2000). « A Reality Check for Data Snooping ». *Econometrica*, 68,
   p. 1097-1126. Non consulté ; formulation reprise de Hansen (2005) et de
   Hsu et Kuan.
3. Hansen, P. R. (2005). « A Test for Superior Predictive Ability ». *Journal of
   Business & Economic Statistics*, 23(4), octobre 2005. Pagination de la revue
   **non trouvée** : l'exemplaire de dépôt consulté n'en porte pas. DOI
   10.1198/073500105000000063. Consulté en entier.
   <https://cdr.lib.unc.edu/downloads/zp38wf793>
4. Benjamini, Y. et Hochberg, Y. (1995). « Controlling the False Discovery Rate:
   A Practical and Powerful Approach to Multiple Testing ». *Journal of the Royal
   Statistical Society*, série B, 57(1), p. 289-300. Non consulté.
5. Benjamini, Y. et Yekutieli, D. (2001). Source du choix de \(c(M)\) comme somme
   harmonique. Non consulté.
6. Holm, S. (1979). « A Simple Sequentially Rejective Multiple Test Procedure ».
   *Scandinavian Journal of Statistics*, 6, p. 65-70. Non consulté.
7. Chen, A. Y. (2021). « The Limits of p-Hacking: Some Thought Experiments ».
   *The Journal of Finance*, 76(5), p. 2447-2480.
   <https://onlinelibrary.wiley.com/doi/10.1111/jofi.13036>. Non consulté, résumé
   lu sur RePEc.
8. Chen, A. Y. (2022). « Most claimed statistical findings in cross-sectional
   return predictability are likely true ». arXiv 2206.15365, révision du
   2025-11-19. <https://arxiv.org/abs/2206.15365>. Source des deux bornes du taux
   de fausses découvertes. Non consulté, résumé lu.
9. Chen, A. Y. et Zimmermann, T. (2020). « Publication Bias and the Cross-Section
   of Stock Returns ». *The Review of Asset Pricing Studies*, 10(2), p. 249-289.
   DOI 10.1093/rapstu/raz011. Non consulté.
10. Harvey, C. R. et Liu, Y. (2020). « False (and Missed) Discoveries in Financial
   Economics ». *The Journal of Finance*, 75(5), p. 2503-2553. Non consulté.
11. Sullivan, R., Timmermann, A. et White, H. (1999). « Data-Snooping, Technical
    Trading Rules, and the Bootstrap ». *Journal of Finance*, 54, p. 1647-1692.
    Non consulté.
12. Hsu, P.-H. et Kuan, C.-M. « Re-Examining the Profitability of Technical
    Analysis with White's Reality Check ». Document de travail, National Taiwan
    University. <https://homepage.ntu.edu.tw/~ckuan/pdf/snoop01.pdf>. Consulté
    pour la formulation du contrôle de réalité.

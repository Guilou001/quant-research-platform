# Le ratio de Sharpe dégonflé

| | |
|---|---|
| **Auteurs** | David H. Bailey et Marcos López de Prado |
| **Année** | 2014 |
| **Revue ou source** | *Journal of Portfolio Management*, vol. 40, n° 5, p. 94-107. Version de travail du 31 juillet 2014 consultée en entier |
| **Lien** | [SSRN 2460551](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551), texte intégral sur [davidhbailey.com](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf) |
| **Statut de réplication** | non commencé |

Article consulté le 2026-09-01, dans sa version de travail de 22 pages. Le volume
40, le numéro 5 et la page de départ 94 sont **rapportés**, lus le 2026-09-01 sur
la page de la revue (`jpm.pm-research.com/content/40/5/94`). La page de fin, 107,
provient de la bibliographie de Bailey, Borwein, López de Prado et Zhu et n'a pas
été vérifiée sur le numéro imprimé.

## La question de recherche

Quel seuil un ratio de Sharpe doit-il franchir pour compter comme une découverte,
quand on ignore combien d'essais l'ont précédé ?

Les auteurs posent que l'information la plus importante manquant à presque tout
backtest publié est le nombre d'essais tentés. Un backtest, simulation historique
du comportement passé d'une stratégie, ne se juge pas sans ce nombre. Leur phrase
est nette : sans contrôle de l'étendue de la recherche, un backtest ne vaut rien,
quelle que soit la performance affichée.

La question a deux volets que l'article traite ensemble. Le premier est le biais
de sélection, le fait de ne publier que les essais gagnants. Le second est la
non-normalité des rendements, qui gonfle le ratio de Sharpe estimé sur un
échantillon court.

## L'intuition économique

Le rendement apparent ne devrait pas exister, et c'est exactement le propos.
Aucune prime de risque, aucun biais comportemental et aucune friction ne
soutiennent le ratio de Sharpe du meilleur essai. Ce qui le soutient est
arithmétique : le maximum de \(N\) tirages d'une loi centrée en zéro est positif,
et croît avec \(N\).

Le mécanisme est celui de la malédiction du vainqueur, le fait que le gagnant
d'une sélection soit choisi en partie pour son erreur de mesure favorable. Si les
ratios de Sharpe des essais d'une même famille de stratégies ont une moyenne
nulle et une variance non nulle, alors chercher plus longtemps produit un
meilleur candidat sans aucune compétence. La théorie des valeurs extrêmes chiffre
ce gain gratuit, et l'article en fait le seuil de rejet.

Une seconde intuition, plus dure, occupe la section « Backtest overfitting under
memory effects » de l'article. Les séries financières ont de la mémoire : une
tension accumulée se dénoue. Un backtest surajusté choisit la règle qui profite
du motif aléatoire le plus extrême de l'échantillon, motif que la mémoire va
précisément défaire. Le surapprentissage ne dilue donc pas la performance future,
il l'inverse. Les auteurs renvoient à Bailey, Borwein, López de Prado et Zhu
(2014), *Notices of the AMS*, pour la preuve formelle, qu'ils ne reproduisent
pas ici.

Qu'est-ce qui ferait disparaître le phénomène ? Trois choses, et une seule est à
la portée du chercheur. Que \(N\) vaille un, c'est-à-dire qu'un essai unique ait
été déclaré avant de voir les données. Que la variance des ratios de Sharpe
essayés soit nulle, ce qui n'arrive pas. Que la série n'ait pas de mémoire, ce
que les auteurs jugent rare en finance.

## Les données

Aucune donnée de marché. L'article est analytique, et sa seule expérience est une
simulation de Monte Carlo décrite en appendice 2, dont le code Python est publié
dans l'article même.

Cette expérience compare la formule analytique du maximum attendu à la moyenne
empirique de maxima simulés. Les paramètres du code publié sont quatre. La
moyenne des essais parcourt 101 valeurs régulièrement espacées entre -100 et 100.
Le nombre d'essais parcourt 10 à 1000 par pas de 10. L'écart type est fixé à 1,
et chaque point reçoit 10 000 tirages. Ces valeurs sont **rapportées**, lues dans
le « Snippet 1 » de l'article.

Résultats de l'expérience, **rapportés**. Pour une variance des essais de 1, la
formule surestime la simulation de moins de 0,05 sous 50 essais, et de 0,006
seulement à 1000 essais. Pour une variance de 4, l'erreur maximale vaut environ
0,11, soit le double, ce qui est cohérent avec la mise à l'échelle en racine
carrée de la variance.

## L'univers

Il n'y a pas d'univers de titres. L'unité d'analyse est l'essai, c'est-à-dire une
configuration de stratégie testée, et l'ensemble analysé est la classe de
stratégies à laquelle cet essai appartient.

L'article insiste sur ce point : la moyenne et la variance des ratios de Sharpe
essayés dépendent de la classe. Ils attendent une moyenne plus élevée pour la
négociation à haute fréquence que pour le macro discrétionnaire. Le seuil de
rejet est donc propre à la famille de stratégies, pas universel.

L'exemple travaillé porte sur une saisonnalité du marché des titres du Trésor
américain, autour du cycle d'adjudication. Aucune donnée réelle ne l'accompagne :
les chiffres sont posés par l'énoncé.

## La méthodologie

La méthode tient en trois pas, et le troisième est le seul apport propre à cet
article.

Premier pas, dériver le maximum attendu de \(N\) ratios de Sharpe indépendants.
Les auteurs supposent ces ratios normaux, de moyenne et de variance propres à la
classe de stratégies, puis appliquent une approximation de la loi du maximum
issue de la théorie des valeurs extrêmes.

Deuxième pas, reprendre le ratio de Sharpe probabiliste de Bailey et López de
Prado (2012), la probabilité que le vrai ratio de Sharpe dépasse un seuil donné.
Ce ratio corrige la longueur de l'échantillon, l'asymétrie et l'aplatissement des
rendements. Sa forme exacte est reproduite plus bas, lue dans l'original.

Troisième pas, remplacer le seuil arbitraire du ratio probabiliste par le maximum
attendu sous l'hypothèse nulle d'absence de compétence. Le ratio dégonflé n'est
donc pas une statistique nouvelle : c'est le ratio probabiliste évalué en un
seuil que le nombre d'essais détermine.

L'appendice 3 traite le cas où les \(M\) essais menés ne sont pas indépendants,
et propose de déduire un nombre d'essais indépendants implicite à partir de leur
corrélation moyenne.

## Les équations qui comptent

Notation, valable pour tout ce qui suit. \(\{\widehat{SR}_n\}\) est l'ensemble
des ratios de Sharpe estimés sur les \(N\) essais indépendants, \(E[\cdot]\) et
\(V[\cdot]\) leur moyenne et leur variance à travers les essais. \(Z\) est la
fonction de répartition de la loi normale centrée réduite et \(Z^{-1}\) son
inverse. \(\gamma \approx 0{,}5772\) est la constante d'Euler-Mascheroni, et
\(e\) le nombre d'Euler.

**Maximum attendu de \(N\) variables normales centrées réduites**, équation (5)
de l'article, valable pour \(N\) grand :

\[
E[\max_n z_n] \approx (1-\gamma)\,Z^{-1}\!\left[1-\frac{1}{N}\right]
\;+\; \gamma\,Z^{-1}\!\left[1-\frac{1}{N}e^{-1}\right]
\]

**Maximum attendu des ratios de Sharpe essayés**, équation (1) :

\[
E\!\left[\max_n \{\widehat{SR}_n\}\right] \approx
E\!\left[\{\widehat{SR}_n\}\right]
+ \sqrt{V\!\left[\{\widehat{SR}_n\}\right]}
\left( (1-\gamma)\,Z^{-1}\!\left[1-\frac{1}{N}\right]
+ \gamma\,Z^{-1}\!\left[1-\frac{1}{N}e^{-1}\right] \right)
\]

**Seuil de rejet sous l'hypothèse nulle**, celui que l'équation (2) utilise. Il
s'obtient en posant \(E[\{\widehat{SR}_n\}] = 0\), c'est-à-dire en supposant
qu'aucune compétence n'existe dans la classe de stratégies :

\[
\widehat{SR}_0 = \sqrt{V\!\left[\{\widehat{SR}_n\}\right]}
\left( (1-\gamma)\,Z^{-1}\!\left[1-\frac{1}{N}\right]
+ \gamma\,Z^{-1}\!\left[1-\frac{1}{N}e^{-1}\right] \right)
\]

**Le ratio de Sharpe dégonflé**, équation (2) :

\[
\widehat{DSR} \equiv \widehat{PSR}\!\left(\widehat{SR}_0\right) =
Z\!\left[
\frac{\left(\widehat{SR}-\widehat{SR}_0\right)\sqrt{T-1}}
{\sqrt{\,1 - \hat{\gamma}_3\,\widehat{SR}
+ \dfrac{\hat{\gamma}_4-1}{4}\,\widehat{SR}^{\,2}\,}}
\right]
\]

où \(\widehat{SR}\) est le ratio de Sharpe estimé de la stratégie retenue, \(T\)
la longueur de l'échantillon en nombre d'observations, \(\hat{\gamma}_3\)
l'asymétrie des rendements et \(\hat{\gamma}_4\) leur aplatissement. Attention à
ce dernier : l'article travaille avec l'aplatissement BRUT, valant 3 pour une
loi normale, et non l'excès d'aplatissement. Son exemple pose explicitement
\(\hat{\gamma}_4 = 3\) pour le cas normal.

**Le ratio de Sharpe probabiliste**, source de la forme ci-dessus, équation (11)
de Bailey et López de Prado (2012), consulté le 2026-09-01. Le seuil \(SR^{*}\)
y est libre, et c'est lui que l'article de 2014 remplace par \(\widehat{SR}_0\) :

\[
\widehat{PSR}(SR^{*}) = Z\!\left[
\frac{\left(\widehat{SR}-SR^{*}\right)\sqrt{n-1}}
{\sqrt{\,1 - \hat{\gamma}_3\,\widehat{SR}
+ \dfrac{\hat{\gamma}_4-1}{4}\,\widehat{SR}^{\,2}\,}}
\right]
\]

**La longueur minimale d'historique**, équation (13) du même article de 2012.
C'est le nombre d'observations qu'il faut pour que le ratio probabiliste dépasse
\(1-\alpha\), et elle porte un terme additif de 1 :

\[
\widehat{MinTRL} = n^{*} = 1 +
\left[1 - \hat{\gamma}_3\,\widehat{SR}
+ \frac{\hat{\gamma}_4-1}{4}\,\widehat{SR}^{\,2}\right]
\left(\frac{Z_{\alpha}}{\widehat{SR}-SR^{*}}\right)^{2}
\]

**Corrélation moyenne des essais**, équation (8), pour une matrice de corrélation
\(M \times M\) d'entrées \(\rho_{i,j}\) :

\[
\rho = \frac{\sum_{i=1}^{M}\sum_{j=1}^{M}\rho_{i,j} - M}{M(M-1)}
= \frac{2\sum_{i=1}^{M}\sum_{j=i+1}^{M}\rho_{i,j}}{M(M-1)}
\]

**Nombre d'essais indépendants implicite**, équation (9), obtenu par
interpolation entre les deux cas extrêmes \(\rho \to 1 \Rightarrow N \to 1\) et
\(\rho \to 0 \Rightarrow N \to M\) :

\[
\widehat{N} = \hat{\rho} + (1-\hat{\rho})\,M
\]

## Les résultats originaux

L'exemple travaillé de l'article est son seul résultat chiffré, et il conclut au
rejet. Un stratège annonce un ratio de Sharpe annualisé de 2,5 sur cinq ans de
données quotidiennes, et l'investisseur refuse.

Les entrées, toutes **rapportées**, lues à la page 9 et 10 de la version de
travail : \(N = 100\) essais indépendants, \(V[\{\widehat{SR}_n\}] = 1/2\) en
unités annualisées, \(T = 1250\), \(\hat{\gamma}_3 = -3\) et
\(\hat{\gamma}_4 = 10\), avec 250 observations par an.

Les sorties, **rapportées** : \(\widehat{SR}_0 \approx 0{,}1132\) non annualisé,
et \(\widehat{DSR} \approx 0{,}9004\), donc sous le seuil de 0,95. L'article
ajoute deux points de comparaison. Avec \(N = 46\) essais seulement, le ratio
dégonflé aurait valu 0,9505, au-dessus du seuil. Avec des rendements normaux
(\(\hat{\gamma}_3 = 0\), \(\hat{\gamma}_4 = 3\)), il aurait fallu \(N = 88\)
essais pour retomber à 0,9505.

Ces quatre nombres ont été recalculés depuis les formules ci-dessus, et ils se
retrouvent : 0,113172 pour le seuil, 0,9004 pour le ratio dégonflé, 0,9505 à
\(N = 46\) et 0,9505 à \(N = 88\) dans le cas normal. Statut **mesuré**, calcul
du 2026-09-01, indépendant du code des auteurs.

Le seuil de rejet annualisé vaut 1,7894 pour \(N = 100\), statut **mesuré**.
Autrement dit, il faudrait un ratio de Sharpe annualisé supérieur à 1,79 pour
seulement égaler ce qu'une classe de stratégies sans compétence produit après
cent essais.

Il n'y a pas de résultat empirique sur données réelles dans cet article. Aucun
portefeuille, aucun fonds, aucune période de marché n'y est testé.

## Les critiques connues

Aucune réfutation publiée et consacrée au ratio dégonflé n'a été trouvée au
2026-09-01. Quatre objections sérieuses existent pourtant, dont trois sont
formulées par les auteurs eux-mêmes ou par des travaux voisins.

**Le nombre d'essais indépendants n'est pas observable.** L'article y consacre
son appendice 3 et y reconnaît deux défauts. La corrélation ne capte qu'une
dépendance linéaire. Surtout, quand le nombre d'essais dépasse la longueur de
l'échantillon, ce qui est le cas courant, la matrice de corrélation est mal
conditionnée et son estimation est elle-même surajustée. Les auteurs écrivent
qu'estimer une corrélation moyenne devient alors sans objet, puisqu'il y a plus
de corrélations que de paires indépendantes d'observations.

**Le contrôle est trop sévère.** Harvey et Liu (2020, *Journal of Finance*,
75(5), p. 2503-2553) soutiennent que les méthodes existantes de tests multiples
manquent de puissance pour détecter les gérants réellement performants. Leur
argument est que contrôler seulement l'erreur de première espèce ignore le coût
des découvertes manquées. Statut **rapporté**, résumé lu, article non consulté
en entier.

**Il existe une méthode concurrente que l'article reconnaît.** Harvey et Liu
(2014) calculent un seuil par la voie de Benjamini et Hochberg. Les auteurs du
ratio dégonflé écrivent que ce seuil joue le même rôle que leur maximum attendu,
et encouragent à calculer le ratio dégonflé avec les deux. La méthode n'est donc
pas présentée comme la seule bonne.

**Les auteurs l'ont eux-mêmes réécrit.** López de Prado et Porcu ont déposé le
2025-09-23 un article intitulé « The Deflated Sharpe Ratio: A Unified Framework
for Search-Adjusted Performance Inference » (SSRN 7198158). Il unifie trois
variantes nommées DSR-L, DSR-LS et DSR-EO. La première est la version d'origine,
à seuil de position seulement. La deuxième ajoute la dispersion du maximum
sélectionné, la troisième emploie la loi complète de la recherche quand
l'inférence de queue exacte est disponible. Statut **rapporté** : la page SSRN a
renvoyé une erreur 403 le 2026-09-01, et ce résumé provient d'une recherche
indexée, non de l'article.

## Les problèmes de réplication connus

**Le piège d'unités est le principal.** Dans l'exemple de l'article, la variance
des essais vaut 1/2 en unités ANNUALISÉES, et le seuil sort non annualisé parce
que la formule le divise par 250. Le ratio de Sharpe de la stratégie retenue,
lui, entre non annualisé, soit \(2{,}5/\sqrt{250}\). Mélanger les deux échelles
donne un résultat faux sans lever d'erreur. Une implémentation doit choisir une
échelle unique et la déclarer.

**L'aplatissement est brut, pas en excès.** Passer un excès d'aplatissement de 7
au lieu de l'aplatissement brut de 10 change le ratio dégonflé de 0,9004 à
0,9018 dans l'exemple de l'article. Statut **mesuré**, calcul du 2026-09-01.
L'écart est petit ici parce que le terme d'asymétrie domine, mais il n'y a
aucune raison qu'il le reste ailleurs.

**Le dénominateur porte \(\sqrt{T-1}\), pas \(\sqrt{T}\).** Sur l'exemple,
utiliser \(\sqrt{T}\) donne 0,9005 au lieu de 0,9004, statut **mesuré**. La
différence est négligeable à \(T = 1250\) et ne l'est plus sur un échantillon
court.

**La convention du ratio probabiliste diverge selon les sources, et l'original
tranche.** Une source secondaire consultée le 2026-09-01, le blogue Portfolio
Optimizer, écrit le ratio probabiliste avec \(\sqrt{T}\) et non \(\sqrt{T-1}\),
et donne la longueur minimale d'historique sans son terme additif de 1.
L'original de Bailey et López de Prado (2012), *Journal of Risk*, 15(2),
p. 3-44, a été consulté le 2026-09-01 sur le miroir de David H. Bailey. Il porte
\(\sqrt{n-1}\) à son équation (11) et le « 1 + » à son équation (13), tous deux
lus sur l'image des pages 9 et 11. C'est donc la source secondaire qui dévie, et
toute implémentation doit suivre l'original.

**Le texte de l'article ne contient pas ses propres nombres en clair.** Dans le
fichier PDF de la version de travail, les valeurs \(N = 100\) et
\(V[\{\widehat{SR}_n\}] = 1/2\) figurent à l'intérieur des équations, dans une
police dont le texte ne s'extrait pas. Elles ont été lues sur une image de la
page 10. Une extraction automatique du texte les perd en silence.

## Les biais possibles

**La variance des essais est estimée sur les essais rapportés.** Or ce sont
justement les essais retenus qui sont rapportés. Le paramètre qui sert à corriger
le biais de sélection est donc lui-même exposé au biais de sélection, et rien
dans l'article ne corrige cette circularité.

**La normalité des ratios de Sharpe essayés est une hypothèse, pas un fait.** Les
auteurs la justifient par l'idée qu'une classe de stratégies partage un motif
commun. C'est une justification d'intuition. Une queue épaisse dans la
distribution des essais rendrait le seuil trop bas.

**L'approximation exige un grand nombre d'essais.** La preuve de l'appendice 1
suppose \(N \to \infty\). L'appendice 2 mesure que la formule surestime le
maximum quand le nombre d'essais tombe sous 50. Appliquer le test à une poignée
d'essais rejette donc trop.

**Le résultat est une probabilité, pas un ratio.** Le nom trompe : le ratio
dégonflé vaut entre 0 et 1. Le lire comme un ratio de Sharpe corrigé est une
erreur d'interprétation, et elle est facile à commettre.

**Le nombre d'essais est déclaré par celui qu'on évalue.** Toute la construction
repose sur une information que le chercheur a intérêt à minorer. L'article le
reconnaît en demandant aux investisseurs et aux arbitres de revues de l'exiger,
mais aucun mécanisme ne la vérifie.

## Nos décisions d'implémentation

non commencé au 2026-09-01

## Nos écarts avec l'article

non commencé au 2026-09-01

## Nos résultats

non commencé au 2026-09-01

## Notre contrôle de robustesse

non commencé au 2026-09-01

## Références

1. Bailey, D. et López de Prado, M. (2014). « The Deflated Sharpe Ratio:
   Correcting for Selection Bias, Backtest Overfitting and Non-Normality ».
   *Journal of Portfolio Management*, 40(5), p. 94-107.
   <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551>
2. Bailey, D. et López de Prado, M. (2012). « The Sharpe Ratio Efficient
   Frontier ». *Journal of Risk*, 15(2), p. 3-44. Source du ratio de Sharpe
   probabiliste et de la longueur minimale d'historique. Consulté le 2026-09-01,
   version de travail de 46 pages.
   <https://www.davidhbailey.com/dhbpapers/sharpe-frontier.pdf>
3. Bailey, D., Borwein, J., López de Prado, M. et Zhu, Q. J. (2014).
   « Pseudo-Mathematics and Financial Charlatanism: The Effects of Backtest
   Overfitting on Out-of-Sample Performance ». *Notices of the AMS*, 61(5),
   p. 458-471. Source de l'argument de mémoire. Non consulté, référence lue dans
   la bibliographie de l'article de 2017.
4. Harvey, C. et Liu, Y. (2014). « Backtesting ». Document de travail, Duke
   University. <https://ssrn.com/abstract=2345489>. Seuil concurrent, cité par
   l'article. Non consulté.
5. Harvey, C. et Liu, Y. (2020). « False (and Missed) Discoveries in Financial
   Economics ». *The Journal of Finance*, 75(5), p. 2503-2553.
   <https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12951>. Non consulté.
6. López de Prado, M. et Porcu, E. (2025). « The Deflated Sharpe Ratio: A
   Unified Framework for Search-Adjusted Performance Inference ». SSRN 7198158.
   Page inaccessible le 2026-09-01 (erreur 403).
7. Lo, A. (2002). « The Statistics of Sharpe Ratios ». *Financial Analysts
   Journal*, 58(4), p. 36-52. Cité par l'article pour l'effet des échantillons
   courts. Non consulté.

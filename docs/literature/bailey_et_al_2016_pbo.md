# La probabilité de surapprentissage d'un backtest

| | |
|---|---|
| **Auteurs** | David H. Bailey, Jonathan M. Borwein, Marcos López de Prado et Qiji Jim Zhu |
| **Année** | 2016 pour la mise en ligne, 2017 pour le numéro imprimé |
| **Revue ou source** | *Journal of Computational Finance*, vol. 20, n° 4, p. 39-69, DOI 10.21314/JCF.2016.322. Version de travail datée du 27 février 2015, 34 pages, consultée en entier |
| **Lien** | [SSRN 2326253](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253), texte intégral sur [davidhbailey.com](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf) |
| **Statut de réplication** | non commencé |

Note de datation. La fiche de la revue donne une première mise en ligne au
2016-09-19 et un numéro d'avril 2017. La consigne de ce laboratoire nomme
l'article « 2016 », ce qui correspond à la mise en ligne et au DOI. Les deux
dates sont **rapportées**, lues sur la page de la revue le 2026-09-01.

## La question de recherche

Comment mesurer si le procédé qui a choisi une stratégie parmi \(N\) essais a
lui-même produit le résultat ?

La question n'est pas de savoir si une stratégie est bonne. Elle est de savoir si
la SÉLECTION est saine. Les auteurs partent d'un constat : la méthode de retenue,
qui met une partie des données de côté pour l'épreuve, ne fonctionne pas sur un
backtest. Ils lui opposent cinq objections en section 1, dont la dernière porte
le raisonnement. Dès que le chercheur essaie plus d'une configuration, le
surapprentissage est présent, et la retenue ne compte pas les essais tentés avant
la sélection.

Ils cherchent donc une statistique qui réponde à une question différente : quelle
est la probabilité que la configuration retenue comme la meilleure en échantillon
se classe sous la médiane hors échantillon ?

## L'intuition économique

Aucun mécanisme économique ne soutient la performance mesurée ici, et l'article
le dit dès son épigraphe de Wittgenstein : toute action peut être rendue conforme
à une règle. Ce qui produit la performance est le nombre de règles essayées.

Le mécanisme précis est le suivant. Le chercheur dispose d'une grille de
configurations, par exemple deux longueurs de moyenne mobile, un seuil d'entrée,
un seuil de sortie et un arrêt de perte. La grille compte des millions de points.
Sur un échantillon fini, l'une d'elles épouse le bruit. Le classement en
échantillon de cette configuration est alors élevé pour une raison qui ne se
reproduit pas.

L'article ajoute un pas que le simple biais de sélection ne contient pas. Quand
la série a de la mémoire, le motif extrême qui a fait gagner la configuration
retenue doit se défaire. La performance hors échantillon n'est alors pas nulle en
moyenne : elle est négative. C'est ce qui rend le classement hors échantillon
INFÉRIEUR à la médiane, et non simplement égal à elle.

Qu'est-ce qui ferait disparaître le phénomène ? Que la grille compte un seul
point, décidé avant de voir les données. Ou que la relation exploitée soit réelle
et stable, auquel cas le meilleur en échantillon reste bon hors échantillon.
L'article le montre par construction dans son second exemple, où un effet mensuel
est injecté volontairement dans les données.

## Les données

Deux jeux de données servent d'illustration, et l'un des deux est simulé.

**Exemple simulé**, section 6. Une série de 1 000 prix quotidiens, environ quatre
ans, tirée d'une marche aléatoire. La grille de stratégie compte quatre
paramètres. Le jour d'entrée parcourt l'intervalle 1 à 22, la durée de détention
l'intervalle 1 à 20, l'arrêt de perte l'intervalle 0 à 10, et le sens vaut -1 ou
1. Le maillage compte 8 800 points. Tous ces nombres sont **rapportés**.

Le calcul de contrôle donne 22 × 20 × 11 × 2 = 9 680, et non 8 800. Statut
**mesuré**, calcul du 2026-09-01. L'écart s'expliquerait par un intervalle
d'arrêt de perte à dix valeurs plutôt que onze, ce qui donnerait 8 800
exactement, mais l'article écrit l'intervalle 0 à 10. Divergence non arbitrée.

**Second exemple simulé**, même construction, mais les rendements des cinq
premières observations aléatoires de chaque mois sont recentrés sur un quart
d'écart type. Un effet saisonnier réel est donc présent, et la méthode doit le
reconnaître.

**Stratégie réelle**, figures 3 et 5. L'article mentionne une stratégie
d'investissement réelle sans nommer ni l'actif, ni la période, ni le gérant.
Aucune donnée n'est publiée et l'exemple n'est donc pas reproductible.

## L'univers

Il n'y a pas d'univers de titres. L'objet analysé est une matrice \(M\) de
dimension \(T \times N\), où chaque colonne porte la série de profits et pertes
d'une configuration, et chaque ligne un instant commun à toutes.

Deux conditions seulement sont imposées. La matrice doit être pleine, avec le
même nombre de lignes par colonne et des observations synchrones. Et la mesure de
performance retenue doit se calculer sur un sous-échantillon de chaque colonne.
Si des configurations négocient à des fréquences différentes, il faut agréger les
observations sur un index commun.

Cette généralité est revendiquée : la méthode marche pour le ratio de Sharpe,
mais aussi pour le ratio de Sortino, l'alpha de Jensen ou le ratio de Sharpe
probabiliste.

## La méthodologie

La validation croisée combinatoire symétrique découpe l'échantillon en tranches,
forme toutes les moitiés possibles, et compare le classement en échantillon au
classement hors échantillon.

Le détail, tel que l'algorithme 2.3 le donne :

1. Former la matrice \(M\) des \(N\) séries de profits et pertes, de dimension
   \(T \times N\).
2. Découper \(M\) par lignes en un nombre PAIR \(S\) de sous-matrices disjointes
   de même dimension, chacune de taille \(T/S \times N\).
3. Former toutes les combinaisons de ces sous-matrices prises par groupes de
   \(S/2\).
4. Pour chaque combinaison, exécuter les sept gestes étiquetés a) à g) par
   l'article.
    - a) Reconstituer l'ensemble d'entraînement \(J\) en joignant les \(S/2\)
      sous-matrices dans leur ordre d'origine.
    - b) Former l'ensemble de test \(\bar{J}\) comme complémentaire de \(J\) dans
      \(M\), dans l'ordre d'origine lui aussi.
    - c) Calculer la performance des \(N\) colonnes sur \(J\), et en tirer le
      classement en échantillon.
    - d) Refaire c) sur \(\bar{J}\), et en tirer le classement hors échantillon.
    - e) Repérer la colonne \(n^*\) la mieux classée sur \(J\).
    - f) Former son rang relatif hors échantillon.
    - g) Transformer ce rang relatif en logit.
5. Rassembler tous les logits et en former la distribution.

Trois propriétés motivent ce découpage. Les ensembles d'entraînement et de test
ont la même taille, donc les deux ratios de Sharpe ont la même précision. Chaque
ensemble d'entraînement sert aussi d'ensemble de test, d'où le mot symétrique.
Et les sous-échantillons ne sont pas tirés au hasard parmi les observations, ce
qui, selon les auteurs, préserve les dépendances temporelles.

L'article compare explicitement sa méthode à la validation croisée à \(k\) blocs
et à la validation avec omission d'une observation. Son argument est qu'un ratio
de Sharpe ne se calcule pas de façon fiable sur un bloc trop petit, et qu'un
\(k\) petit ramène la méthode à une simple retenue.

## Les équations qui comptent

Notation. \(N\) est le nombre de configurations essayées, \(T\) le nombre
d'observations, \(S\) le nombre pair de tranches. \(\Omega\) est l'ensemble des
\(N!\) permutations de \((1, 2, \ldots, N)\), c'est-à-dire l'espace des
classements. \(r\) est le classement en échantillon, \(\bar{r}\) le classement
hors échantillon. Le rang \(N\) désigne la meilleure position.

**Le sous-ensemble des classements où la configuration \(n\) est première** :

\[
\Omega_n^{*} = \{ f \in \Omega \mid f_n = N \}
\]

**Définition du surapprentissage**, équation (2.1). Le procédé de sélection
surapprend si la configuration optimale en échantillon a un classement attendu
sous la médiane hors échantillon :

\[
\sum_{n=1}^{N} E\!\left[\bar{r}_n \mid r \in \Omega_n^{*}\right]
\; \mathrm{Prob}\!\left[r \in \Omega_n^{*}\right] \;\leq\; N/2
\]

**Définition de la probabilité de surapprentissage**, équation (2.2) :

\[
PBO = \sum_{n=1}^{N}
\mathrm{Prob}\!\left[\bar{r}_n < N/2 \mid r \in \Omega_n^{*}\right]
\; \mathrm{Prob}\!\left[r \in \Omega_n^{*}\right]
\]

**Nombre de combinaisons**, équation (2.3) :

\[
\binom{S}{S/2} = \binom{S-1}{S/2-1}\frac{S}{S/2} = \cdots
= \prod_{i=0}^{S/2-1} \frac{S-i}{S/2-i}
\]

**Rang relatif hors échantillon de la configuration choisie en échantillon**,
étape f) de l'algorithme, où \(n^*\) est la meilleure colonne en échantillon :

\[
\bar{\omega}_c := \frac{\bar{r}^{\,c}_{n^*}}{N+1} \in (0,1)
\]

**Logit**, étape g). C'est la transformation qui envoie le rang relatif sur toute
la droite réelle, et qui vaut zéro exactement à la médiane :

\[
\lambda_c = \ln\!\left(\frac{\bar{\omega}_c}{1-\bar{\omega}_c}\right)
\]

**Fréquence relative des logits**, équation (2.4), où \(\chi\) est la fonction
caractéristique et \(\#(C_S)\) le nombre de combinaisons :

\[
f(\lambda) = \sum_{c \in C_S} \frac{\chi_{\{\lambda\}}(\lambda_c)}{\#(C_S)},
\qquad \int_{-\infty}^{+\infty} f(\lambda)\,d\lambda = 1
\]

**Estimateur de la probabilité de surapprentissage**, section 3.1. C'est la masse
de la distribution des logits sur les valeurs négatives :

\[
\phi = \int_{-\infty}^{0} f(\lambda)\,d\lambda
\]

**Dominance stochastique du premier ordre**, section 3.3. Elle vaut si
\(\mathrm{Prob}[R_{n^*} \geq x] \geq \mathrm{Prob}[\mathrm{Mean}(R) \geq x]\)
pour tout \(x\), avec inégalité stricte pour au moins un \(x\).

**Dominance stochastique du second ordre**, critère moins exigeant :

\[
SD_2[x] = \int_{-\infty}^{x}
\Big( \mathrm{Prob}[\mathrm{Mean}(R) \leq u]
- \mathrm{Prob}[R_{n^*} \leq u] \Big) du \;\geq\; 0
\]

La variable d'intégration est notée \(u\) ici. L'article écrit \(dx\) et réemploie
donc \(x\) à la fois comme borne et comme variable muette, ce qui n'est pas
implémentable tel quel.

## Les résultats originaux

Quatre résultats chiffrés, tous **rapportés**, tous issus d'exemples et non d'une
étude empirique.

**Premier exemple simulé, marche aléatoire pure.** La configuration optimale est
jour d'entrée 11, durée 4, arrêt de perte -1, sens 1. Le ratio de Sharpe annualisé
en échantillon vaut 1,27, et la statistique du ratio de Sharpe probabiliste vaut
2,83, ce qui donne moins de 1 % de probabilité que le vrai ratio soit négatif.
La méthode donne pourtant une probabilité de surapprentissage de 55 %, et 53 %
des ratios de Sharpe hors échantillon sont négatifs alors que tous ceux en
échantillon sont positifs, entre 1 et 2,2. La distribution hors échantillon des
configurations retenues ne domine pas la distribution générale.

**Second exemple simulé, effet mensuel injecté.** La configuration optimale est
jour d'entrée 1, durée 4, arrêt de perte -10, sens 1, pour un ratio de Sharpe
annualisé de 1,54. La probabilité de surapprentissage tombe à 13 %, et 13 % des
ratios hors échantillon sont négatifs. La dominance stochastique est cette fois
présente.

**Exemple des figures 2 et 4.** Environ 78 % des ratios de Sharpe hors
échantillon sont négatifs alors que tous ceux en échantillon sont positifs, entre
1 et 3. La probabilité de surapprentissage vaut 74 %.

**Stratégie réelle, figures 3 et 5.** La probabilité de perte hors échantillon
est d'environ 3 %, et la distribution des configurations retenues domine la
distribution générale.

Le seuil de décision proposé est un précepte, pas une mesure. Les auteurs
suggèrent de rejeter les modèles dont la probabilité de surapprentissage dépasse
0,05, par analogie avec l'usage du cadre de Neyman et Pearson.

Une conclusion de méthode compte autant que ces nombres. Un ratio de Sharpe élevé
en échantillon ne dit rien sur la représentativité du résultat. La relation entre
performance en échantillon et performance hors échantillon est négative :
au-delà d'un point, chercher le maximum devient nuisible.

## Les critiques connues

Aucune réfutation publiée et consacrée à cette méthode n'a été trouvée au
2026-09-01. Trois critiques documentées existent, dont une venue des auteurs.

**Les auteurs déclarent eux-mêmes des limites.** Leur conclusion écrit que la
mise en œuvre par validation croisée combinatoire symétrique a des limites, et
que d'autres cadres pourraient convenir mieux, en particulier pour les problèmes
porteurs d'information de structure. La section 5 ajoute que la probabilité de
surapprentissage ne doit jamais servir de fonction objectif : l'optimiser
reviendrait à surajuster le critère de surapprentissage.

**Une méthode voisine la bat dans une comparaison contrôlée.** Arian, Norouzi M.
et Seco (2024), *Knowledge-Based Systems*, vol. 305, article 112477, comparent
plusieurs procédés de test hors échantillon dans un environnement synthétique.
Ils concluent à la supériorité de la validation croisée combinatoire PURGÉE, qui
retire les observations dont l'information chevauche l'ensemble de test. Deux
mesures portent ce verdict : une probabilité de surapprentissage plus basse et un
ratio de Sharpe dégonflé plus élevé. Statut **rapporté** : résumé lu le 2026-09-01, article derrière un
péage, non consulté.

**La préservation des dépendances temporelles est contestée.** Recombiner des
tranches non contiguës rompt l'ordre du temps entre les tranches, même si l'ordre
tient à l'intérieur de chacune. Et les ensembles de test se recouvrent
massivement, puisque chaque tranche apparaît dans une grande part des
combinaisons, ce qui rend les logits fortement corrélés entre eux. Statut
**rapporté**, provenance : synthèses secondaires en ligne lues le 2026-09-01,
sans article de revue identifié. Cette objection est à vérifier sur source
primaire avant d'être citée ailleurs.

## Les problèmes de réplication connus

**L'article se trompe sur son propre exemple combinatoire.** Il écrit deux fois,
en section 2.2 et en section 4, qu'avec \(S = 16\) on forme 12 780 combinaisons.
Le coefficient binomial vaut 12 870. Statut **mesuré**, calcul du 2026-09-01. Il
s'agit d'une inversion de chiffres, et un test dont la valeur attendue serait
recopiée de l'article échouerait. La coquille est isolée : les deux autres
décomptes de la même section se retrouvent exactement, 2 704 156 pour
\(S = 24\) et 924 pour \(S = 12\), également **mesurés** le 2026-09-01.

**L'étape c) de l'algorithme porte une étiquette fausse.** Elle demande de
calculer la performance de la colonne \(n\) « de \(J\) (l'ensemble de test) ».
Or \(J\) est l'ensemble d'ENTRAÎNEMENT : l'étape a) le définit ainsi, et la fin
de l'étape c) le confirme en appelant le résultat le classement en échantillon.
Vérifié sur l'image de la page 12 de la version de travail.

**La médiane n'est pas définie deux fois de la même façon.** L'équation (2.2)
compte les cas où le rang hors échantillon est inférieur à \(N/2\). L'estimateur
compte les logits négatifs, c'est-à-dire les rangs inférieurs à \((N+1)/2\).
Les deux seuils diffèrent, et l'implémentation doit choisir. Statut **mesuré**
par lecture des deux formules.

**La conclusion contredit la définition.** La section 7 écrit que la probabilité
de surapprentissage est celle qu'une stratégie optimale en échantillon fasse
moins bien que la MOYENNE hors échantillon, alors que la définition 2.2 dit la
MÉDIANE. La prose de la définition 2.2 est elle-même bancale : elle compare une
performance attendue à un rang médian.

**La stratégie réelle reçoit deux probabilités différentes.** La section 3.2
écrit d'abord que la part des configurations retenues classées sous la médiane
hors échantillon vaut 4 %, puis, deux phrases plus loin, que la probabilité de
surapprentissage vaut 0,04 %. Un facteur cent sépare les deux, et rien ne dit
lequel est le bon.

**Le ratio de Sharpe du premier exemple change de valeur.** La section 6 annonce
1,27 puis, quelques lignes plus loin, compare « 1,54 contre 1,3 ». Le lecteur ne
sait pas lequel des deux est le nombre de l'expérience.

**Le maillage annoncé ne correspond pas au produit de ses intervalles.** L'article
annonce 8 800 points pour des intervalles qui en donnent 9 680, comme la section
sur les données le détaille.

**Le code n'est pas dans cet article.** Il renvoie à l'appendice 4 de l'article
des *Notices of the AMS* de 2014 pour l'implémentation en Python. Cet appendice
n'a pas été consulté.

## Les biais possibles

**Le recouvrement des ensembles de test corrèle les logits, et l'article compte
comme s'il n'en était rien.** Avec \(S = 16\), chaque tranche apparaît dans
exactement la moitié des combinaisons, 6 435 sur 12 870, statut **mesuré**,
calcul du 2026-09-01. Les logits ne sont donc pas des tirages indépendants. Or la
section 4 borne l'erreur d'estimation par \(\sigma[\hat{p}] = \sqrt{p(1-p)/N}\).
C'est la formule de l'écart type d'une proportion sur un échantillon INDÉPENDANT
de taille \(N\). Elle rend \(\sigma[f(\lambda)] < 0{,}0045\) et « moins de 0,01
d'erreur d'estimation à 95 % de confiance ». Recalculé le 2026-09-01,
\(\sqrt{0{,}25/12\,870} = 0{,}00441\), donc la borne publiée est bien celle de
cette formule. Elle sous-estime la dispersion réelle d'un facteur inconnu.

**La méthode ne voit que ce qui est dans l'échantillon.** Un changement de régime
absent des données ne peut pas être détecté. Une probabilité de surapprentissage
basse mesurée sur une seule phase de marché ne dit rien du comportement dans une
autre.

**Elle ne détecte ni fuite d'information future, ni erreur de construction des
variables.** Si toutes les colonnes de la matrice partagent la même fuite, les
classements en échantillon et hors échantillon seront cohérents, et la
probabilité de surapprentissage sera basse. La méthode déclarera saine une
sélection qui repose sur une donnée impossible à connaître à la date.

**La grille des essais est choisie par le chercheur.** Ajouter des configurations
manifestement mauvaises abaisse le rang médian et peut faire paraître bon le rang
hors échantillon du candidat retenu. Aucun garde-fou de l'article n'empêche cette
manipulation.

**Le nombre de tranches arbitre entre deux exigences opposées, et l'article
tranche sans démonstration.** La section 4 recommande \(S = 16\) pour deux
raisons qu'elle nomme. Ce nombre engendre assez de logits pour estimer une
proportion. Et sur quatre ans de données quotidiennes il découpe en trimestres,
ce qui préserverait la structure de corrélation sérielle. La règle est donc un
**précepte** adossé à un cas d'espèce, pas un critère. Un \(S\) trop petit
sous-représente la queue gauche des logits, un \(S\) trop grand hache les effets
saisonniers, et rien ne dit où se situe l'optimum pour une série donnée.

**Le rejet à 0,05 est un précepte.** Rien dans l'article ne calibre ce seuil sur
une erreur de première espèce mesurée. Les auteurs l'écrivent comme un usage
coutumier.

## Nos décisions d'implémentation

non commencé au 2026-09-01

## Nos écarts avec l'article

non commencé au 2026-09-01

## Nos résultats

non commencé au 2026-09-01

## Notre contrôle de robustesse

non commencé au 2026-09-01

## Références

1. Bailey, D., Borwein, J., López de Prado, M. et Zhu, Q. J. (2016). « The
   Probability of Backtest Overfitting ». *Journal of Computational Finance*,
   20(4), p. 39-69. DOI 10.21314/JCF.2016.322.
   <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253>
2. Bailey, D., Borwein, J., López de Prado, M. et Zhu, Q. J. (2014).
   « Pseudo-Mathematics and Financial Charlatanism: The Effects of Backtest
   Overfitting on Out-of-Sample Performance ». *Notices of the AMS*, 61(5),
   p. 458-471. Contient l'appendice 4 avec le code Python de l'expérience.
   Non consulté.
3. Bailey, D. et López de Prado, M. (2012). « The Sharpe Ratio Efficient
   Frontier ». *Journal of Risk*, 15(2), p. 3-44. Source du ratio de Sharpe
   probabiliste utilisé dans l'exemple. Non consulté.
4. Bailey, D. et López de Prado, M. (2014). « The Deflated Sharpe Ratio ».
   *Journal of Portfolio Management*, 40(5), p. 94-107. Fiche voisine du même
   groupe.
5. Arian, H. R., Norouzi M., D. et Seco, L. A. (2024). « Backtest overfitting in
   the machine learning era: A comparison of out-of-sample testing methods in a
   synthetic controlled environment ». *Knowledge-Based Systems*, 305, 112477.
   <https://dl.acm.org/doi/10.1016/j.knosys.2024.112477>. Non consulté.

# Building Diversified Portfolios that Outperform Out of Sample

Article non consulté au 2026-09-01 ; la fiche repose sur des sources secondaires citées.

| | |
|---|---|
| **Auteurs** | Marcos López de Prado |
| **Année** | 2016 |
| **Revue ou source** | The Journal of Portfolio Management, vol. 42, no 4, p. 59-69, DOI 10.3905/jpm.2016.42.4.059 (notice Crossref vérifiée le 2026-09-01, date de parution 2016-05-31). Version de travail : SSRN 2708678, dont la date exacte est **non vérifiée**, SSRN étant inaccessible |
| **Lien** | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2708678 (erreur HTTP 403 depuis cet environnement le 2026-09-01) ; page éditeur : https://jpm.pm-research.com/content/42/4/59 (péage) |
| **Statut de réplication** | non commencé |

Cinq voies ont été tentées pour obtenir le texte : SSRN, la page éditeur, Semantic
Scholar, ResearchGate et une recherche ciblée de copies hébergées par des universités.
Aucune n'a rendu le texte. Ce qui suit distingue donc systématiquement ce qui vient de
sources secondaires consultées de ce qui n'a pas pu être vérifié.

## La question de recherche

Pourquoi l'optimiseur quadratique de Markowitz, exact en échantillon, se comporte-t-il mal
hors échantillon ? López de Prado attaque trois défauts de la méthode de la ligne
critique, l'algorithme de Markowitz qui résout la frontière efficiente sous contraintes.
Ces défauts sont l'instabilité, la concentration et la sous-performance (rapporté par le
résumé SSRN, relayé par la recherche du 2026-09-01).

La réponse proposée n'est pas une meilleure estimation de \( \Sigma \). C'est une méthode
d'allocation qui n'inverse jamais \( \Sigma \), et qui fonctionne donc sur une matrice mal
conditionnée, voire singulière, là où un optimiseur quadratique échoue.

## L'intuition économique

Aucune prime de risque n'est en jeu ici, et il faut le dire d'entrée pour ne pas chercher
un mécanisme qui n'existe pas. Le gain revendiqué est un gain d'erreur d'estimation, pas
un gain de rendement attendu.

Le mécanisme se nomme. Une optimisation moyenne-variance passe par \( \Sigma^{-1} \), et
l'inversion amplifie l'erreur d'estimation dans la proportion du conditionnement de la
matrice, c'est-à-dire du rapport entre sa plus grande et sa plus petite valeur propre.
Quand deux actifs sont très corrélés, ce rapport explose, l'optimiseur lit une occasion
d'arbitrage dans du bruit, et il y met tout l'argent. Le portefeuille en échantillon est
optimal, le portefeuille hors échantillon est une position pariant sur une corrélation mal
mesurée.

La parité de risque hiérarchique remplace l'inversion par une descente d'arbre. Elle
regroupe les actifs par ressemblance de corrélation, puis réordonne la matrice pour que
les grandes valeurs se rapprochent de la diagonale. Elle répartit ensuite le capital de
haut en bas entre deux moitiés, en proportion inverse de leur variance. À aucun moment un
système linéaire n'est résolu, donc à aucun moment l'erreur n'est amplifiée par un
conditionnement.

Ce qui ferait disparaître l'avantage se nomme aussi, et Cotton (2024) l'écrit sous forme
d'expérience de pensée dont il dit que les deux camps peuvent l'accepter. À la limite d'une
information parfaite sur \( \Sigma \), l'optimisation explicite est le meilleur usage de
cette information. À l'autre limite, où les écarts entre covariances estimées et une
moyenne d'ensemble sont pure illusion, mieux vaut une heuristique de diversification,
voire des poids uniformes. Aucune des deux écoles ne domine l'autre ; chacune a son
territoire. Autrement dit, l'avantage de la méthode hiérarchique décroît à mesure que
l'estimation de \( \Sigma \) se rapproche de la vérité. Que ce soit précisément le nombre
d'observations rapporté au nombre d'actifs qui gouverne cette qualité d'information est une
lecture de cette fiche, et non un énoncé de Cotton. Pfitzinger et Katzke (2019) observent
bien la conclusion attendue sur données réelles, où l'optimisation ne s'effondre pas, ce
qui est repris plus bas.

Deuxième borne, moins souvent dite. La bissection récursive répartit le capital entre deux
groupes selon leurs variances internes, et **ignore la covariance entre les deux
groupes**. Cotton donne le contre-exemple minimal. Prenons une matrice \( \Sigma \) dont
les deux premiers actifs ont une corrélation \( \rho \) et dont le troisième est
indépendant. Une règle qui ne regarde que la diagonale rend le portefeuille symétrique
\( (1/3, 1/3, 1/3) \) quel que soit \( \rho \). Plus généralement, une allocation diagonale
sur-alloue aux sous-portefeuilles les plus corrélés en interne, et attire donc les dollars
là où la diversification est en partie illusoire.

## Les données

Les données sont **synthétiques**, et la configuration de l'expérience est **rapportée au
second degré** : elle vient de la page Wikipédia consacrée à la méthode, consultée le
2026-09-01, et non de l'article. Cette page porte un avertissement de conflit d'intérêts,
mise en garde qui vaut pour tous les chiffres qui suivent.

La configuration qu'elle publie tient en cinq nombres. Dix séries temporelles de rendements
gaussiens, de 520 observations chacune, soit deux années de données quotidiennes. Une
fenêtre glissante de 260 observations. Un rééquilibrage toutes les 22 observations, soit un
rééquilibrage mensuel. Et 10 000 répétitions de l'ensemble.

La structure de corrélation vraie reste **non trouvée**. Wikipédia dit « rendements
gaussiens » sans plus. Bechis (2020, p. 94), qui rejoue l'expérience, en donne bien une
description. Loi gaussienne centrée, matrice de covariance aléatoire, variances tirées
d'une loi multimodale. Puis corrélations d'une loi uniforme sur l'espace des matrices de
corrélation. Mais c'est la description de sa propre réplication, pas une citation de
l'article. Elle est donc **non vérifiée** comme description de l'original.

Aucune donnée de marché n'entre dans la démonstration principale. Pfitzinger et Katzke
(2019, p. 13) le confirment en opposant leurs propres résultats à ceux de López de Prado,
« qui observe HRP surpasser la variance minimale sur des rendements simulés ».

## L'univers

Dix séries pour l'expérience Monte-Carlo, d'après Wikipédia (rapporté au second degré). La
même page rapporte un exemple numérique distinct, comparant l'allocation hiérarchique, la
ligne critique et le portefeuille à variance inverse. La part des cinq premiers actifs y
vaut 62,57 % pour la méthode hiérarchique et 92,66 % pour la ligne critique, et la ligne
critique met un poids nul sur trois actifs. Le nombre total d'actifs de cet exemple est
**non trouvé** ; la page indique seulement que la matrice de covariance employée porte un
conditionnement d'environ 150,93.

Ce que l'on sait de l'applicabilité, par les sources secondaires : la méthode ne réclame
pas l'inversibilité de \( \Sigma \) et calcule un portefeuille sur une matrice dégénérée
ou singulière. Pfitzinger et Katzke (2019) l'appliquent à des univers de 20 à 200 actions
sur six univers boursiers.

## La méthodologie

Trois étapes, dans cet ordre. La description qui suit est celle de Pfitzinger et Katzke
(2019, section 2), source consultée, recoupée par Wikipédia.

**Un, la classification hiérarchique.** Les corrélations sont converties en distances,
puis les actifs sont agrégés de proche en proche jusqu'à former un dendrogramme, l'arbre
qui dit quel actif rejoint quel groupe et à quelle distance. López de Prado emploie le
saut minimum, le critère qui définit la distance entre deux groupes comme la plus courte
distance entre un membre de l'un et un membre de l'autre.

**Deux, la quasi-diagonalisation.** La matrice de covariance est réordonnée en suivant
l'arbre, de sorte que les fortes corrélations viennent se placer près de la diagonale.
Aucun changement de base n'a lieu : c'est une permutation de lignes et de colonnes. Cotton
(2024) le formule ainsi, et c'est la formulation la plus juste : permuter les indices
d'une matrice de covariance revient à tenter de la diagonaliser en n'utilisant que des
matrices de permutation.

La justification de l'étape est claire. La combinaison de séries non corrélées qui
minimise la variance est la pondération par l'inverse des variances. Une pondération par
l'inverse des variances convient donc aux actifs dont la matrice de corrélation est à peu
près diagonale, et l'étape deux sert à s'en rapprocher.

**Trois, la bissection récursive.** Le capital est divisé de haut en bas. À chaque
scission, les deux sous-ensembles reçoivent des parts inversement proportionnelles à leur
variance interne, cette variance étant elle-même calculée sur une pondération par
l'inverse des variances à l'intérieur du groupe. On recommence jusqu'à ce que chaque
groupe se réduise à un actif.

Wikipédia rapporte une complexité en \( O(\log N) \) au mieux et \( O(N) \) au pire, sans
en préciser l'unité de compte (rapporté, non vérifié).

## Les équations qui comptent

**La distance de corrélation**, celle qui transforme une corrélation en une vraie distance
:

\[ d_{i,j} = \sqrt{\frac{1 - \rho_{i,j}}{2}} \]

où \( \rho_{i,j} \) est la corrélation entre les rendements des actifs \( i \) et \( j \).
Deux actifs parfaitement corrélés sont à distance 0, deux actifs indépendants à distance
\( 1/\sqrt{2} \), deux actifs parfaitement opposés à distance 1. Source : Wikipédia,
recoupée par l'annexe A.1 de Pfitzinger et Katzke (2019).

**Le portefeuille à variance inverse**, qui sert de comparaison et de brique interne :

\[ w_i = \frac{\sigma_i^{-2}}{\sum_{j=1}^{N} \sigma_j^{-2}} \]

où \( \sigma_i \) est l'écart type du rendement de l'actif \( i \). Source : Pfitzinger et
Katzke (2019), équation 4.2, consultée.

**La règle de scission.** À chaque nœud, les deux sous-groupes \( A \) et \( D \)
reçoivent des parts dans le rapport \( 1/\nu(A) : 1/\nu(D) \). La mesure de risque
\( \nu(\cdot) \) est ici la variance du portefeuille à variance inverse construit sur le
sous-groupe. La notation \( \nu \) et cette lecture du mécanisme viennent de Cotton (2024,
section 2), source consultée. Le facteur d'allocation s'écrit

\[ \alpha = 1 - \frac{\nu(A)}{\nu(A) + \nu(D)} \]

le groupe \( A \) recevant \( \alpha \) et le groupe \( D \) recevant \( 1 - \alpha \).
Cette dernière forme est **rapportée** depuis un extrait de code cité par Bechis (2020, p.
90) et non depuis l'article original.

Ce qui n'apparaît nulle part dans ces équations mérite d'être écrit : la covariance entre
\( A \) et \( D \), c'est-à-dire le bloc hors diagonale, n'entre pas dans le partage. Voir
la section des critiques.

## Les résultats originaux

**Mise en garde préalable, indispensable.** Les chiffres de cette section proviennent de
l'article Wikipédia « Hierarchical Risk Parity », consulté le 2026-09-01, et non de
l'article original. Cette page porte un avertissement de l'encyclopédie signalant qu'un
contributeur important semble avoir un lien étroit avec son sujet. Les chiffres sont donc
**rapportés au second degré**. Ils sont arithmétiquement cohérents entre eux, contrôle fait
ci-dessous, ce qui n'atteste pas leur fidélité à l'article.

**Exemple numérique.** Part des cinq premiers actifs : 62,57 % pour la méthode
hiérarchique, 92,66 % pour la ligne critique. Écart type : 0,4640 contre 0,4486. La
méthode hiérarchique est donc, sur cet exemple, moins concentrée et plus volatile en
échantillon, ce qui est cohérent avec sa thèse.

**Expérience Monte-Carlo**, 10 000 itérations sur données synthétiques. Variances hors
échantillon : \( \sigma^2_{HRP} = 0{,}0671 \), \( \sigma^2_{IVP} = 0{,}0928 \),
\( \sigma^2_{CLA} = 0{,}1157 \).

**Le sens des deux pourcentages, et il faut le lire dans le bon sens.** Wikipédia écrit que
la ligne critique montre la plus forte variance, « dépassant celle du HRP de 72,47 % ».
Elle écrit de même que la variance du portefeuille à variance inverse reste « supérieure de
38,24 % » à celle du HRP. Les deux énoncés sont cohérents avec les trois variances
publiées, et le calcul le vérifie : \( 0{,}1157/0{,}0671 - 1 = 72{,}4\,\% \) et
\( 0{,}0928/0{,}0671 - 1 = 38{,}3\,\% \).

Le piège de réplication est ici, et il tient à une convention d'écriture. Une variance
supérieure de 72,47 % ne signifie **pas** une réduction de 72,47 % dans l'autre sens :
partir du HRP pour aller vers la ligne critique donne +72,4 %, partir de la ligne critique
pour aller vers le HRP donne \( 1 - 0{,}0671/0{,}1157 = 42{,}0\,\% \) de variance en
moins. Un code qui viserait « 72,47 % de réduction » manquerait sa cible de trente points
tout en étant correct.

**Ratio de Sharpe.** Wikipédia annonce une amélioration d'environ 31,3 % sur la ligne
critique. Ce chiffre n'est recoupé par aucune autre source consultée et n'est **pas
vérifiable** ici.

**L'énoncé qualitatif est recoupé, mais pas toujours contre le même comparateur.** Les
expériences Monte-Carlo de 2016 donnent à la méthode hiérarchique une variance hors
échantillon plus faible que la ligne critique. Et cela alors même que la variance minimale
est l'objectif de cette dernière. L'énoncé vient de Wikipédia et du résumé SSRN relayé par
la recherche. Pfitzinger et Katzke le recoupent, mais leurs deux phrases ne disent pas la
même chose. À leur page 2, le comparateur est la pondération **à variance inverse**, contre
laquelle López de Prado obtient une volatilité plus basse. À leur page 13, le comparateur
devient la **variance minimale**, sur rendements simulés, et c'est cette seconde phrase qui
recoupe l'énoncé ci-dessus.

## Les critiques connues

Elles sont réelles, nombreuses et convergentes. Quatre sont documentées ici, dont trois
depuis des textes consultés en entier.

**L'ordre des actifs change les poids.** C'est la critique la plus grave, parce qu'elle
porte sur une propriété élémentaire attendue de toute méthode d'allocation. Nanakorn et
Palmgren (2021, KTH, p. 40) l'énoncent ainsi. L'arbre construit à l'étape 1 n'est pas
utilisé à l'étape 3. De ce fait, la bissection récursive fait dépendre les poids de la
position des actifs dans le jeu de données. Échanger la place de deux actifs et permuter
en conséquence les lignes et colonnes de la matrice de covariance ne change pas le jeu de
données, mais peut changer les poids. Les auteurs notent que le fait avait déjà été relevé
par Raffinot (2018a, 2018b), Huang (2020) et Lau et al. (2017).

**La rotation est élevée, ce qui contredit la thèse de stabilité.** Toujours Nanakorn et
Palmgren (2021, p. 57), sur des contrats à terme d'indices actions et d'obligations. La
rotation du portefeuille hiérarchique original vaut environ 1,4 fois celle du portefeuille
à variance minimale long seulement, qui vient en deuxième. Elle vaut plus de 4 fois celle
du troisième. Leur commentaire est direct : ce résultat n'est pas cohérent avec le
raisonnement qui motive la méthode, à savoir que les portefeuilles issus d'une
optimisation sont numériquement instables. Leurs deux variantes, qui utilisent réellement
l'arbre de l'étape 1, améliorent le ratio de Sharpe d'environ 10 % et réduisent la
rotation de 60 à 65 %.

**Le résultat hors échantillon ne se reproduit pas sur données réelles.** Deux sources.

Nanakorn et Palmgren (2021, p. 57) trouvent que la méthode hiérarchique se comporte comme
le portefeuille à variance inverse. Cela vaut en rendement logarithmique annualisé, en
volatilité et en ratio de Sharpe, résultat qui contredit selon elles les simulations de
López de Prado. Elle est de plus battue par l'équipondération, l'inverse de la volatilité
et la contribution égale au risque en rendement, et par la variance minimale en volatilité
et en perte maximale.

Pfitzinger et Katzke (2019, p. 13) travaillent sur dix ans de rendements quotidiens, de
2008 à 2017, et six univers d'actions, dont la Bourse de Johannesbourg. Le portefeuille à variance minimale y
atteint une volatilité hors échantillon systématiquement faible, résultat qu'ils opposent
explicitement à López de Prado (2016). Leur explication est mesurée par des simulations
complémentaires. La source première de la sous-performance de l'optimisation est l'erreur
sur les **rendements**, pas sur les volatilités. Une méthode à variance minimale, qui
n'estime aucun rendement, souffre donc moins qu'on ne l'annonce.

**L'allocation ignore l'information hors diagonale.** Cotton (2024, arXiv 2411.05807),
consulté. Sa critique est mathématique et non empirique. La méthode ne fait qu'un usage
défensif et indirect de la covariance, par une simple réordonnance des actifs, ce qui
suggère un lien avec l'optimisation sans le fournir. Il construit une famille de méthodes
hiérarchiques où la sous-covariance transmise à chaque branche est corrigée par un
complément de Schur. Cette correction restaure l'information de corrélation entre les deux
groupes et permet, à la limite, de retrouver le portefeuille à variance minimale. Sa
conclusion, qu'il qualifie lui-même de prudente, est qu'un investisseur convaincu par
l'allocation descendante devrait sérieusement envisager sa règle plutôt que celle de 2016.

**La critique dont seul le résumé a été lu.** Jain et Jain (2019) publient dans *Risks*
« Can Machine Learning-Based Portfolios Outperform Traditional Risk-Based Portfolios? The
Need to Account for Covariance Misspecification » (vol. 7, no 3, article 74, DOI
10.3390/risks7030074). Leur résumé, obtenu par la notice Crossref le 2026-09-01, place la
méthode hiérarchique en position intermédiaire. Quand les estimations de covariance sont
grossières, la pondération par l'inverse de la volatilité est la plus robuste, la méthode
hiérarchique vient ensuite, et la variance minimale comme la diversification maximale sont
les plus sensibles. Résultat **rapporté** ; seul le résumé a été lu, le corps de l'article
n'a pas été consulté.

**Les travaux favorables**, pour ne pas donner une image faussement noire. Raffinot
(2017), « Hierarchical Clustering-Based Asset Allocation », *The Journal of Portfolio
Management*, vol. 44, no 2, p. 89-99, conclut à une performance ajustée du risque
supérieure pour les portefeuilles fondés sur la classification hiérarchique. Le détail de
ce travail est **non vérifié** au 2026-09-01. Ni le nombre de jeux de données, ni la
procédure de comparaison n'ont pu être établis. La notice Crossref ne porte pas de résumé
et l'article est sous péage. Antonov, Lipton et López de Prado (2024), SSRN 4748151,
apportent des arguments théoriques en faveur de la méthode (rapporté, non consulté ; l'un
des auteurs est celui de l'article étudié).

## Les problèmes de réplication connus

**Le premier problème est en amont de tout le reste : l'article n'est pas accessible.**
Cinq voies ont échoué. La configuration Monte-Carlo et les variances cibles existent, mais
au second degré seulement, par une page d'encyclopédie qui porte un avertissement de
conflit d'intérêts. La structure de corrélation vraie et la graine aléatoire, elles, ne sont
connues par aucune source. Une réplication devra ou bien obtenir le texte par une bibliothèque, ou bien
déclarer qu'elle reproduit une méthode et des cibles de seconde main, non des chiffres
d'origine.

**Le deuxième est le choix des paramètres libres.** L'algorithme comporte au moins quatre
décisions que l'article fixe sans les imposer. Le critère d'agrégation, la métrique de
distance, la mesure de risque \( \nu \) de chaque scission, et l'allocation à l'intérieur
d'un groupe. López de Prado retient le saut minimum pour la première. Pfitzinger et Katzke
(2019) montrent que changer le critère d'agrégation change les résultats de façon notable,
ce qui rend le nom « parité de risque hiérarchique » ambigu par lui-même.

**Le troisième est la dépendance à l'ordre**, décrite plus haut. Deux implémentations
correctes appliquées au même jeu de données peuvent rendre des poids différents si elles
n'ont pas rangé les colonnes dans le même ordre. Un test de réplication doit donc inclure
une permutation des colonnes et vérifier explicitement ce qu'elle produit, plutôt que de
supposer l'invariance.

**Le quatrième est le sens des pourcentages publiés.** Les 72,47 % et les 38,24 % sont des
excès de variance mesurés à partir du HRP, et non des réductions mesurées à partir des
comparateurs. Prendre le premier chiffre pour une réduction ferait viser 72,47 % là où la
réduction vaut 42,0 %, et déclarer défaillant un code correct. Toute cible de réplication
doit donc porter la variance elle-même, pas le pourcentage.

## Les biais possibles

**La comparaison porte sur des données synthétiques engendrées par l'auteur.** La
structure de corrélation vraie est choisie, et c'est elle qui décide si une méthode par
regroupement a un avantage. Une structure vraie en blocs favorise mécaniquement une
méthode qui cherche des blocs. La question n'est pas de savoir si l'expérience est
truquée, elle ne l'est pas, mais de savoir de quelle population de matrices vraies elle
est tirée, et cette population est **non trouvée**. Le point pèse d'autant plus que
l'expérience ne compte que dix séries : à dix actifs, le regroupement hiérarchique n'a que
quelques scissions à faire, et rien ne dit que le classement tiendrait à cent.

**Le comparateur est l'algorithme de la ligne critique sans régularisation.** Ni
rétrécissement à la Ledoit et Wolf, ni contrainte de poids, ni filtrage des valeurs
propres. Comparer une heuristique robuste à un optimiseur volontairement nu place la barre
bas. Cotton (2024) le dit d'ailleurs à l'envers, en observant que ses expériences portent
sur les configurations idéalisées où l'allocation descendante bat l'optimisation.

**L'absence de coûts de transaction.** Aucune source consultée ne mentionne de frais dans
l'expérience de 2016. Or la rotation mesurée par Nanakorn et Palmgren est le point faible
majeur de la méthode sur données réelles. Une comparaison sans frais ne peut pas voir ce
défaut.

**Le biais de l'auteur qui juge sa propre méthode.** Il n'est pas une accusation, c'est
une raison mécanique de chercher des réplications indépendantes, et la section précédente
en donne trois, dont deux défavorables.

## Nos décisions d'implémentation

non commencé au 2026-09-01

## Nos écarts avec l'article

non commencé au 2026-09-01

## Nos résultats

non commencé au 2026-09-01

## Notre contrôle de robustesse

non commencé au 2026-09-01

## Références

**Source primaire, non consultée au 2026-09-01**

- López de Prado, M. (2016), « Building Diversified Portfolios that Outperform Out of
  Sample », *The Journal of Portfolio Management*, vol. 42, no 4, p. 59-69. DOI
  10.3905/jpm.2016.42.4.059. SSRN 2708678 :
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2708678 (HTTP 403 depuis cet
  environnement). Page éditeur : https://jpm.pm-research.com/content/42/4/59

**Sources secondaires consultées le 2026-09-01**

- Cotton, P. (2024), « Schur Complementary Allocation: A Unification of Hierarchical Risk
  Parity and Minimum Variance Portfolios », arXiv:2411.05807v1, 29 octobre 2024. Consulté
  intégralement : https://arxiv.org/pdf/2411.05807
- Nanakorn, N. et Palmgren, E. (2021), « Hierarchical Clustering in Risk-Based Portfolio
  Construction », mémoire de deuxième cycle en mathématiques, KTH, Stockholm, travail
  encadré chez Lynx Asset Management. Consulté intégralement :
  https://www.diva-portal.org/smash/get/diva2:1609991/FULLTEXT01.pdf
- Pfitzinger, J. et Katzke, N. (2019), « A Constrained Hierarchical Risk Parity Algorithm
  with Cluster-based Capital Allocation », Stellenbosch Economic Working Papers WP14/2019,
  novembre 2019. Consulté intégralement :
  https://www.ekon.sun.ac.za/wpapers/2019/wp142019/wp142019.pdf
- Bechis, L. (2020), « Machine Learning Portfolio Optimization: Hierarchical Risk Parity
  and Modern Portfolio Theory », mémoire, LUISS. Consulté :
  https://tesi.luiss.it/28022/1/709261_BECHIS_LUCA.pdf
- Wikipédia, « Hierarchical Risk Parity », consulté le 2026-09-01 :
  https://en.wikipedia.org/wiki/Hierarchical_Risk_Parity. **Page portant un avertissement
  de conflit d'intérêts.** Seule source trouvée pour les chiffres de l'expérience
  Monte-Carlo.

**Sources citées mais non consultées au 2026-09-01**

- Raffinot, T. (2017), « Hierarchical Clustering-Based Asset Allocation », *The Journal of
  Portfolio Management*, vol. 44, no 2, p. 89-99. DOI 10.3905/jpm.2018.44.2.089, notice
  Crossref vérifiée le 2026-09-01 ; le résumé n'a pas pu être obtenu, la notice n'en portant
  aucun.
- Jain, P. et Jain, S. (2019), « Can Machine Learning-Based Portfolios Outperform
  Traditional Risk-Based Portfolios? The Need to Account for Covariance Misspecification »,
  *Risks*, vol. 7, no 3, article 74. DOI 10.3390/risks7030074. Résumé consulté par la notice
  Crossref le 2026-09-01, corps de l'article non consulté.
- Antonov, A., Lipton, A. et López de Prado, M. (2024), « Overcoming Markowitz's
  Instability with the Help of the Hierarchical Risk Parity (HRP): Theoretical Evidence »,
  SSRN 4748151.
- Huang (2020) et Lau et al. (2017), cités par Nanakorn et Palmgren comme ayant relevé
  avant elles la non-utilisation de l'arbre à l'étape 3.

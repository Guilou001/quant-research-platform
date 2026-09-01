# Global Portfolio Optimization

| | |
|---|---|
| **Auteurs** | Fischer Black, Robert Litterman |
| **Année** | 1992 |
| **Revue ou source** | Financial Analysts Journal, vol. 48, no 5 (septembre-octobre 1992), p. 28-43. DOI 10.2469/faj.v48.n5.28 |
| **Lien** | https://people.duke.edu/~charvey/Teaching/BA453_2006/Black_Litterman_Global_Portfolio_Optimization_1992.pdf (fac-similé de l'article publié, seize pages, les seize consultées et lues le 2026-09-01 ; le fichier est une image numérisée sans couche de texte, donc les tableaux se lisent page par page et non par extraction automatique) ; notice de l'éditeur : https://rpc.cfainstitute.org/research/financial-analysts-journal/1992/faj-v48-n5-28 |
| **Statut de réplication** | non commencé |

## La question de recherche

Pourquoi les modèles d'allocation quantitatifs ne servent-ils presque jamais en gestion
globale ? Black et Litterman répondent en deux temps. Ces modèles réclament de
l'investisseur ce qu'il n'a pas, un vecteur complet de rendements espérés sur tous les
actifs et toutes les devises. Et leur solution est démesurément sensible à ce vecteur.

La tension est mesurable dans l'article même. Un investisseur qui n'exprime aucune vue
prend les moyennes historiques. Sans contrainte de vente à découvert, il obtient une
exposition de -78,7 % sur le mark, de -95,7 % sur l'obligation canadienne et de +54,5 %
sur l'obligation américaine (tableau III, rapporté). Interdire la vente à découvert
n'arrange rien : la position sur le mark passe à -160,0 %, et sur les quatorze positions
obligataires et actions possibles, deux seulement sont non nulles. Le modèle est donc
inutilisable, non parce qu'il est faux, mais parce que son entrée est inconnaissable.

## L'intuition économique

Aucune prime de rendement n'est promise ici, et c'est ce qui distingue cet article des
autres du corpus. Le mécanisme invoqué est un mécanisme d'équilibre, pas une anomalie. Si
tous les investisseurs détenaient le portefeuille de marché, un seul vecteur de rendements
espérés rendrait ces poids optimaux au sens moyenne-variance. Ce vecteur, la prime de
risque d'équilibre, le rendement excédentaire qui égalise l'offre et la demande de chaque
actif, se lit à l'envers depuis les capitalisations boursières.

L'argument économique tient en une phrase. Un investisseur sans opinion n'a aucune raison
de s'écarter du marché. Le point neutre d'une optimisation doit donc être le marché, et
non la moyenne historique. Celle-ci recommande d'acheter ce qui a monté et de vendre ce
qui a baissé. Black et Litterman l'écrivent. Employer les rendements passés comme vues
neutres revient à supposer que les poids constants ayant le mieux performé sont neutres.
Ils sont au contraire un jeu de poids très particulier.

Ce qui ferait disparaître le mécanisme se nomme sans peine. Il repose entièrement sur le
MEDAF mondial, le modèle d'équilibre où le portefeuille de marché est efficient, augmenté
de la couverture universelle de Black. Si le portefeuille de marché n'est pas efficient,
le point de départ est faux, et toute moyenne a posteriori hérite de cette erreur sans
qu'aucune vue ne la corrige. L'article assume cette dépendance : sa note 9 énumère les
hypothèses de la couverture universelle, un monde sans impôts, sans contraintes de capital
et sans inflation, et reconnaît que certains les jugeront trop restrictives.

Deuxième borne, plus pratique. Le modèle ne produit pas de stratégie. Black et Litterman
l'écrivent dans leur section de simulations. Leur approche ne produit pas, en elle-même,
de stratégie d'investissement, elle exige un jeu de vues. Toute simulation teste donc
autant la stratégie qui engendre les vues que le modèle. La performance vient des vues,
jamais de la mécanique bayésienne.

## Les données

Sept pays, rendements mensuels de janvier 1975 à août 1991, en dollars américains :
États-Unis, Japon, Allemagne, France, Royaume-Uni, Canada et Australie (rapporté, p. 30).

Vingt séries de rendements excédentaires, comptées sur le tableau II. Trois par pays
(actions, obligations, devise) pour six pays, et deux pour les États-Unis dont la devise
sert de numéraire. Soit six devises, sept marchés obligataires et sept marchés d'actions.
L'article confirme le décompte ailleurs, en parlant de « quatorze actifs potentiels » pour
les seules obligations et actions (p. 30). Deux sources se contredisent sur ce point :
Hirani et Wallström (2014, p. 22) écrivent que la simulation de Black et Litterman portait
sur 21 actifs avec des vues sur 7 à la fois. Le compte tiré du tableau II est 20.

Conventions de rendement, données en note de bas de page du tableau I. Les obligations et
les actions sont exprimées en dollars, couvertes en devise, en excès du taux interbancaire
de Londres ; les devises, en excès du taux de change à terme à un mois.

Le tableau I publie, pour les vingt séries, la moyenne totale, la moyenne annualisée et
l'écart type annualisé du rendement excédentaire. Le tableau II publie la matrice de
corrélation complète de ces vingt séries sur janvier 1975 à août 1991. Les deux ensemble
donnent une matrice de covariance reconstructible, ce qui est décisif pour la réplication.

Les vues chiffrées de la section des sept pays viennent de deux publications de Goldman
Sachs de l'été 1991. The International Fixed Income Analyst du 2 août 1991 pour les taux,
et The International Economics Analyst de juillet-août 1991 pour les changes.

Statut de la matrice de covariance dans le modèle : la note 4 déclare que les vraies
covariances des rendements excédentaires sont traitées comme connues, et annonce un autre
article sur leur incertitude. La simulation historique, elle, réestime la covariance à
chaque mois sur les données disponibles jusque-là (p. 40).

## L'univers

Sept pays, trois classes d'actifs, aucune action individuelle. La constante de couverture
universelle, la part du risque de change couverte à l'équilibre, est fixée à 80 % dans
tout l'article. Black et Litterman jugent raisonnable une plage de 75 % à 85 %. Ils
donnent la correspondance mesurée sur leurs données mensuelles : 75 % correspond à une
prime de risque de 5,9 % sur les actions américaines, 85 % à une prime de 9,8 % (p. 32).

Le portefeuille d'équilibre, c'est-à-dire les poids de capitalisation avec 80 % du risque
de change couvert, porte un rendement excédentaire espéré de 5,7 % et une volatilité
annualisée de 10,7 % (p. 39). Toutes les frontières de l'article sont normalisées sur ce
niveau de 10,7 %, choisi parce que c'est le risque du portefeuille d'équilibre (note 6).

## La méthodologie

Trois étapes, dans cet ordre.

**Un, l'optimisation inverse.** Les poids de capitalisation boursière et la matrice de
covariance donnent les primes d'équilibre \( \Pi \). Aucune donnée de rendement n'entre
dans ce calcul, seulement des capitalisations et un risque.

**Deux, l'ajout des vues.** L'investisseur écrit chaque vue comme une combinaison linéaire
de rendements espérés, égale à un chiffre, à une erreur près dont la variance mesure son
manque de confiance. Une vue relative du type « A battra B de 2 % » s'écrit avec une ligne
de \( P \) valant \( [1, -1, 0] \).

**Trois, la moyenne a posteriori et l'optimisation.** La formule combine l'équilibre et
les vues, puis le vecteur combiné alimente une optimisation moyenne-variance sans
contrainte, à niveau de risque donné.

La simulation historique suit un protocole roulant, décrit p. 40. À partir de juillet 1981
et chaque mois pendant dix ans : estimer la covariance sur les données disponibles,
calculer les primes d'équilibre, ajouter les vues de la stratégie. Puis en déduire les
rendements excédentaires espérés, optimiser sans contrainte à risque donné, relever le
rendement réalisé du mois, et recommencer. Trois stratégies sont comparées entre elles et
à des placements passifs, sur le même univers et la même période.

## Les équations qui comptent

**L'optimisation inverse.** Les primes de risque d'équilibre sont

\[ \Pi = \delta \Sigma W \]

où \( \Pi \) est le vecteur \( n \times 1 \) des primes d'équilibre et \( \delta \) une
constante de proportionnalité déduite des formules de la couverture universelle de Black.
\( \Sigma \) est la matrice \( n \times n \) de covariance des rendements excédentaires,
et \( W \) le vecteur des poids de marché. Pour une obligation ou une action, \( W_i \)
est la capitalisation du marché \( i \) divisée par la somme des capitalisations. Pour la
devise du pays \( j \), \( W_i = \lambda W_j^c \), où \( W_j^c \) est le poids du pays
\( j \) et \( \lambda \) la constante de couverture universelle. Ce sont les points 3 et 6
de l'appendice de l'article.

**L'a priori.** Le rendement excédentaire espéré \( E[R] \) est inobservable. Sa loi a
priori est normale, centrée sur \( \Pi \), de covariance \( \tau \Sigma \), avec
\( \tau \) une constante (appendice, point 7).

**Les vues.** Elles s'écrivent

\[ P \, E[R] = Q + \varepsilon, \qquad \varepsilon \sim \mathcal{N}(0, \Omega) \]

où \( P \) est une matrice connue \( k \times n \) dont chaque ligne est le portefeuille
sur lequel porte une vue. \( Q \) est le vecteur \( k \times 1 \) des rendements annoncés
par ces vues. Et \( \varepsilon \) est un vecteur aléatoire normal inobservable, de
moyenne nulle et de matrice de covariance **diagonale** \( \Omega \).

**La moyenne a posteriori**, telle qu'imprimée au point 8 de l'appendice :

\[ \overline{E[R]} = \left[ (\tau \Sigma)^{-1} + P' \Omega^{-1} P \right]^{-1}
\left[ (\tau \Sigma)^{-1} \Pi + P' \Omega^{-1} Q \right] \]

Chaque terme, un à un. \( \overline{E[R]} \) est le vecteur \( n \times 1 \) de rendements
excédentaires espérés qui entre ensuite dans l'optimiseur. \( (\tau \Sigma)^{-1} \) est la
précision de l'équilibre, l'inverse de sa covariance, donc le poids accordé au point
neutre. \( P' \Omega^{-1} P \) est la précision apportée par les vues, projetée sur
l'espace des actifs. \( \Pi \) est le point neutre, \( Q \) ce que disent les vues. La
formule est donc une moyenne pondérée par les précisions : l'équilibre tire vers
\( \Pi \), les vues vers \( Q \), et le rapport des deux précisions arbitre.

**Le cas limite d'une confiance totale.** Quand \( \Omega \to 0 \), la moyenne converge
vers la moyenne conditionnelle (p. 35)

\[ \pi' + \tau \Sigma P' \left[ P \tau \Sigma P' \right]^{-1} \left[ Q - P \pi' \right] \]

qui résout la minimisation de \( (E[R] - \pi) \, \tau \Sigma^{-1} (E[R] - \pi)' \) sous la
contrainte \( P \, E[R]' = Q \).

### Ce que valent \( \tau \) et \( \Omega \) dans l'article

Sur \( \tau \), l'article dit deux choses et pas une de plus. Premièrement, c'est une
constante, et \( \tau \Sigma \) est la covariance de l'incertitude sur la moyenne.
Deuxièmement, page 34 : parce que l'incertitude sur la moyenne est bien plus petite que
l'incertitude sur le rendement lui-même, \( \tau \) sera proche de zéro.

**Aucune valeur numérique de \( \tau \) n'apparaît nulle part dans les seize pages de
l'article.** Ni dans le corps, ni dans les tableaux, ni dans les notes, ni dans
l'appendice. Les seize pages ont été lues pour l'établir.

Sur \( \Omega \), l'article dit trois choses. C'est une matrice **diagonale**, et cette
diagonalité correspond à l'hypothèse que les vues sont des tirages indépendants de la loi
des rendements futurs. À la limite où \( \Omega \) tend vers zéro, la moyenne converge
vers la moyenne conditionnelle sous contrainte, autrement dit vers la confiance totale. Et
une confiance moindre rapproche le résultat de l'équilibre. Dans l'exemple à trois actifs,
une vue de 2 % assortie d'une variance de 1 ramène l'écart espéré à 1,6 %, plus près de la
valeur d'équilibre de 0 (p. 37).

**Aucune règle de fabrication de \( \Omega \) n'est donnée.** Dans la section des sept
pays, les auteurs déclarent mettre une confiance de 100 % dans les vues des économistes,
ce qui revient à faire tendre \( \Omega \) vers zéro. Ils baissent ensuite cette confiance
sans jamais publier le chiffre correspondant (tableaux XII, XIII et XIV).

### Ce qu'en font les praticiens

C'est ici que la littérature s'écarte de l'article, et l'écart est grand.

**He et Litterman (1999)** calibrent la confiance de chaque vue de sorte que le rapport
\( \omega_k / \tau \) égale la variance du portefeuille de la vue, \( p_k \Sigma p_k' \).
Ils écrivent explicitement, en note 6 de leur article, qu'il n'y a alors pas besoin de
spécifier \( \tau \) séparément puisque seul le rapport \( \omega / \tau \) entre dans la
formule. Leur paramètre d'aversion au risque vaut \( \delta = 2{,}5 \) (note 3, mesuré
dans le document). Le paramètre le plus discuté de la littérature s'annule donc chez les
auteurs eux-mêmes.

**Idzorek (2004)** confirme l'annulation et la chiffre. En posant \( \tau = 0{,}025 \) et
en appliquant la règle de He et Litterman, il obtient une diagonale de \( \Omega \) valant
0,000709, 0,000141 et 0,000866 sur ses trois vues. Passer de \( \tau = 0{,}025 \) à
\( \tau = 15 \) change ces valeurs du tout au tout et laisse le vecteur combiné inchangé.

**Les valeurs recommandées se contredisent**, et Idzorek en dresse le relevé. Lee fixe
\( \tau \) entre 0,01 et 0,05 puis calibre sur une cible d'erreur de suivi. Satchell et
Scowcroft (2000) le posent souvent à 1. Blamont et Firoozye (2003) lisent
\( \tau \Sigma \) comme l'erreur type de \( \Pi \), ce qui donne \( \tau \) voisin de
l'inverse du nombre d'observations. Hirani et Wallström (2014) retiennent
\( \tau = 0{,}05 \) en se réglant sur He et Litterman (2002). L'écart entre 0,01 et 1 est
d'un facteur cent, sur un paramètre dont l'article original ne dit que « proche de zéro ».

**La conséquence pratique tient en une ligne.** Si \( \Omega \) est construit
proportionnellement à \( \tau \), le vecteur combiné ne dépend pas de \( \tau \), et le
débat est vide. Si \( \Omega \) est spécifié indépendamment, par exemple par le degré de
confiance en pourcentage d'Idzorek, alors \( \tau \) pilote seul le partage entre
l'équilibre et les vues, et sa valeur décide du portefeuille.

## Les résultats originaux

Tous les chiffres ci-dessous sont **rapportés**, relevés dans les tableaux de l'article.

**Les primes d'équilibre** (tableau VI, rendements excédentaires annualisés en
pourcentage, constante de couverture 80 %). Devises : Allemagne 1,01 ; France 1,10 ; Japon
1,40 ; Royaume-Uni 0,91 ; Canada 0,60 ; Australie 0,63. Obligations : 2,29 ; 2,23 ; 2,88 ;
3,28 ; États-Unis 1,87 ; Canada 2,54 ; Australie 1,74. Actions : 6,27 ; 8,48 ; 8,72 ;
10,27 ; États-Unis 7,32 ; Canada 7,28 ; Australie 6,45.

**Le portefeuille d'équilibre** (tableau VII) redonne exactement les poids de
capitalisation avec 80 % de couverture : actions américaines 29,7 %, japonaises 23,7 %,
obligations américaines 16,3 %.

**La démonstration de sensibilité, qui est le cœur de l'article.** Un investisseur pense
que la reprise américaine sera faible. Le taux de l'obligation de référence baissera d'un
point de base au lieu de monter d'un, et les actions américaines monteront de 2,7 % au
lieu de 3,3 %. Il traduit cette vue très modeste en déplaçant de +0,8 point le rendement
excédentaire espéré des obligations américaines et de -2,5 points celui des actions
américaines, tout le reste inchangé. Le portefeuille optimal sans contrainte devient alors
(tableau VIII) : obligations américaines 112,9 %, actions américaines -30,6 %, obligations
canadiennes -42,4 %, obligations allemandes -13,6 %. Un déplacement de deux chiffres
produit un portefeuille que personne ne détiendrait.

**Ce que donne l'approche par les vues sur le même cas.** La même idée s'écrit aussi comme
une vue relative : l'écart de rendement espéré entre actions et obligations américaines
sera de 2,0 points sous l'écart d'équilibre de 5,5 points. Les rendements combinés du
tableau IX donnent alors le portefeuille du tableau X : obligations américaines 67,0 %,
actions américaines 3,3 %, actions japonaises 29,5 %. Le portefeuille s'incline dans le
sens de la vue sans exploser.

**Le cas des vues fortes.** Les prévisions des économistes de Goldman Sachs au 31 juillet
1991 (tableau XI) impliquent, entre autres, un rendement excédentaire annualisé de -8,85 %
sur le yen et de +5,68 % sur l'obligation australienne. Avec une confiance de 100 % et
sans contrainte, le portefeuille optimal (tableau XII) revient extrême : obligations
australiennes 108,3 %, obligations françaises -65,4 %, exposition au dollar australien
-51,4 %. Baisser la confiance sur toutes les vues ramène le portefeuille vers l'équilibre
(tableau XIII), et la baisser sélectivement le rééquilibre encore (tableau XIV).

**La valeur de la diversification mondiale** (tableau XVIII, à risque constant de 10,7 %).
Sans couverture de change, passer d'un portefeuille domestique obligations et actions à un
portefeuille mondial ajoute 74 points de base de rendement excédentaire espéré, soit +15,5
%. Avec couverture de change, l'ajout est de 85 points de base, soit +17,9 %. Sur les
obligations seules et avec couverture, le gain atteint 106 points de base, soit +49,5 %.

**La simulation historique** (figures A et B, juillet 1981 à août 1991). Cent dollars
placés dans chacune des trois stratégies et dans le portefeuille d'équilibre, ce dernier
étant le portefeuille de marché mondial actions et obligations couvert à 80 %. Les
stratégies sont construites à risque égal à celui du portefeuille d'équilibre. Verdict
écrit par les auteurs (p. 42). Les stratégies investissant dans les devises à haut
rendement et dans les marchés d'actions à fort rapport dividende sur taux obligataire ont
remarquablement bien performé sur dix ans. La stratégie obligataire à haut rendement,
elle, n'a pas ajouté de valeur. Les niveaux finaux exacts des quatre courbes ne sont pas
imprimés en chiffres dans l'article, seulement tracés : **non trouvé**.

## Les critiques connues

**Le paramètre \( \tau \).** C'est la critique la plus fournie. O'Toole (2017), « The
Black-Litterman model: active risk targeting and the parameter tau », Journal of Asset
Management, DOI 10.1057/s41260-017-0055-6, consacre un article entier à ce seul paramètre.
Walters lui a également consacré un texte séparé, « The Factor Tau in the Black-Litterman
Model » (SSRN 1701467). Ces deux articles sont **rapportés et non consultés** au
2026-09-01 : la page Springer exige une authentification et SSRN renvoie une erreur 403
depuis cet environnement. La critique elle-même est vérifiable sans eux, puisqu'elle tient
dans la contradiction relevée plus haut entre Lee, Satchell et Scowcroft, et Blamont et
Firoozye, contradiction documentée par Idzorek (2004, p. 14), source consultée.

**Le modèle n'est pas unique.** Walters classe la littérature en deux modèles de
référence, le canonique et l'alternatif, ce dernier étant celui d'Idzorek (2004) et de
Meucci (2009). Hirani et Wallström (2014, p. 20) en tirent la conséquence gênante. Les
réglages d'une simulation ne se traduisent pas nécessairement dans le langage d'une autre.
Les études empiriques en deviennent difficiles à comparer entre elles. La différence
qu'ils relèvent porte sur ce qui met la matrice de confiance à l'échelle : Meucci (2009) la
divise par un paramètre de confiance d'ensemble, He et Litterman (1999) par \( \tau \).
Le traitement de \( \tau \) chez Meucci au-delà de 2009 est **non vérifié** au 2026-09-01.

**La covariance est supposée connue.** Ce n'est pas un reproche extérieur, c'est la note 4
de l'article, qui déclare traiter les vraies covariances comme connues et renvoie à un
autre article le traitement de leur incertitude. Or c'est \( \Sigma \) qui produit
\( \Pi \) par optimisation inverse et \( \tau \Sigma \) par a priori. Une erreur sur
\( \Sigma \) contamine donc les deux termes de la formule à la fois.

**Le modèle hérite des hypothèses du MEDAF mondial.** Note 9 de l'article : la couverture
universelle suppose un monde sans impôts, sans contraintes de capital et sans inflation.
Les auteurs répondent que l'idée centrale s'appliquerait à un autre équilibre, moins
restrictif, sans en construire aucun.

**Le modèle ne produit aucune performance par lui-même.** Section des simulations
historiques, p. 40, écrit par les auteurs : l'approche ne produit pas de stratégie
d'investissement, et toute simulation teste aussi la stratégie qui engendre les vues. La
figure A ne mesure donc pas le modèle, elle mesure trois stratégies passées à travers lui.

## Les problèmes de réplication connus

**Ce qui est reproductible.** Les tableaux I et II donnent les écarts types annualisés et
la matrice de corrélation complète des vingt séries, sur janvier 1975 à août 1991. La
matrice de covariance de l'article est donc reconstructible à la lecture, ce qui est rare
et vaut d'être noté.

**Ce qui manque.** Quatre choses, et chacune bloque une partie du chemin.

La valeur de \( \tau \) n'est pas publiée, comme établi plus haut. Si l'on suit la
calibration de He et Litterman (1999), l'absence est sans conséquence sur le vecteur
combiné ; sinon, elle est bloquante.

La valeur de \( \delta \) n'est pas publiée non plus. L'appendice dit seulement que c'est
une constante de proportionnalité fondée sur les formules de Black. On peut la retrouver
en imposant que \( \delta \Sigma W \) reproduise le tableau VI, ce qui fait de la
réplication une résolution inverse plutôt qu'un calcul direct.

Les capitalisations boursières \( W \) ne sont pas publiées. Le tableau VII donne les
poids optimaux d'équilibre, qui sont précisément les poids de capitalisation avec 80 % de
couverture, donc \( W \) se lit dans le tableau VII plutôt qu'il ne se retrouve ailleurs.

Les valeurs de \( \Omega \) employées dans les tableaux XIII et XIV, ceux de la confiance
réduite, ne sont pas publiées. Ces deux tableaux ne sont donc pas reproductibles.

**La simulation historique n'est pas reproductible.** Elle exige les rendements mensuels
de vingt séries de juillet 1981 à août 1991. Il y faut aussi les rendements en dividende
et les taux obligataires de sept pays, et les capitalisations boursières mois par mois.
Rien de tout cela n'est publié.

**Le décompte des actifs est incertain.** Vingt selon le tableau II, vingt et un selon
Hirani et Wallström (2014). Un travail de réplication doit trancher explicitement.

## Les biais possibles

**Le choix des stratégies de la simulation est postérieur aux données.** Trois stratégies
sont retenues, portant sur les devises à haut rendement, les obligations à haut rendement
et les actions à fort rapport dividende sur taux. Les auteurs disent les avoir choisies
parce qu'elles sont simples, comparables et représentatives, et non pour les promouvoir.
Le paramètre de la règle des actions, qui multiplie par 50 l'écart de rapport dividende
sur taux obligataire, n'est justifié nulle part : il est **non trouvé**.

**Aucun coût de transaction.** La simulation réoptimise chaque mois sans contrainte de
poids ni frais. L'absence de frais est **rapportée** par Hirani et Wallström (2014, p. 24).
Pour comparer leurs résultats à ceux de 1992, ils fixent leur commission de courtage à 0
% en suivant l'approche de Black et Litterman.

**Aucune vente à découvert n'est interdite dans la simulation.** Les portefeuilles des
tableaux XII et XIII portent des positions supérieures à 100 % et fortement négatives. Un
investisseur réel ne les tiendrait pas, et le rendement mesuré n'est donc pas atteignable.

**La période est unique et courte.** Dix ans, un seul échantillon, aucune fenêtre témoin,
aucun test hors échantillon. Les auteurs le concèdent en une phrase : la performance
passée ne garantit certainement pas la performance future.

**Le survivant de l'échantillon.** Sept pays développés choisis en 1991, sur des données
remontant à 1975. Aucun marché disparu, aucun contrôle des capitaux, aucune période
d'hyperinflation. L'article n'aborde pas la question.

## Nos décisions d'implémentation

non commencé au 2026-09-01

## Nos écarts avec l'article

non commencé au 2026-09-01

## Nos résultats

non commencé au 2026-09-01

## Notre contrôle de robustesse

non commencé au 2026-09-01

## Références

**Source primaire, consultée intégralement le 2026-09-01**

- Black, F. et Litterman, R. (1992), « Global Portfolio Optimization », *Financial
  Analysts Journal*, vol. 48, no 5, p. 28-43. DOI 10.2469/faj.v48.n5.28. Fac-similé :
  https://people.duke.edu/~charvey/Teaching/BA453_2006/Black_Litterman_Global_Portfolio_Optimization_1992.pdf

**Sources secondaires consultées le 2026-09-01**

- He, G. et Litterman, R. (1999), « The Intuition Behind Black-Litterman Model
  Portfolios », Goldman Sachs Investment Management Research, décembre 1999. Consulté :
  https://people.duke.edu/~charvey/Teaching/BA453_2006/GS_The_intuition_behind.pdf.
  Notice SSRN : https://papers.ssrn.com/sol3/papers.cfm?abstract_id=334304
- Idzorek, T. M. (2004), « A Step-by-Step Guide to the Black-Litterman Model: Incorporating
  User-Specified Confidence Levels », document de travail daté du 20 juillet 2004, Zephyr
  Associates. C'est cette version qui a été consultée, et non le chapitre publié en 2007.
  Consulté :
  https://people.duke.edu/~charvey/Teaching/BA453_2006/Idzorek_onBL.pdf
- Hirani, S. et Wallström, J. (2014), « The Black-Litterman Asset Allocation Model: An
  Empirical Comparison to the Classical Mean-Variance Framework », mémoire de maîtrise,
  Université de Linköping, ISRN LIU-IEI-FIL-A--14/01735--SE. Consulté :
  https://liu.diva-portal.org/smash/get/diva2:758241/FULLTEXT01.pdf

**Sources citées mais non consultées au 2026-09-01**

- Black, F. et Litterman, R. (1990), « Asset Allocation: Combining Investor Views with
  Market Equilibrium », Goldman, Sachs & Co., septembre 1990. Citée en note 15 de
  l'article de 1992.
- Black, F. (1989), « Universal Hedging: How to Optimize Currency Risk and Reward in
  International Equity Portfolios », *Financial Analysts Journal*, juillet-août 1989.
  Citée en notes 3 et 18 de l'article de 1992 ; c'est la note 18, appelée au point 6 de
  l'appendice, qui en fait la source de \( \delta \).
- O'Toole, R. (2017), « The Black-Litterman model: active risk targeting and the parameter
  tau », *Journal of Asset Management*, vol. 18, no 7, p. 580-587. DOI
  10.1057/s41260-017-0055-6, notice Crossref vérifiée le 2026-09-01. Texte inaccessible sans
  authentification.
- Walters, J. (2014), « The Black-Litterman Model in Detail », SSRN 1314585, et (2013),
  « The Factor Tau in the Black-Litterman Model », SSRN 1701467. SSRN renvoie une erreur
  403 depuis cet environnement.
- Theil, H. (1971), *Principles of Econometrics*, Wiley. Citée en note 14 de l'article de
  1992 pour l'estimation mixte.

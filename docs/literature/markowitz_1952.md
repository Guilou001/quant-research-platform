# Portfolio Selection

| | |
|---|---|
| **Auteurs** | Harry M. Markowitz |
| **Année** | 1952 |
| **Revue ou source** | The Journal of Finance, vol. 7, no 1 (mars 1952), p. 77-91 |
| **Lien** | http://www.efalken.com/LowVolClassics/markowitz_JF1952.pdf (fac-similé JSTOR de l'article publié, consulté et lu intégralement le 2026-09-01) ; notice de l'éditeur : https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.1952.tb01525.x |
| **Statut de réplication** | non commencé |

## La question de recherche

Quelle règle de choix de portefeuille explique et justifie la diversification ? Markowitz
pose que la sélection se fait en deux étapes : d'abord former des croyances sur l'avenir
des titres à partir de l'observation, ensuite passer de ces croyances à un portefeuille.
Il annonce dès la première page qu'il ne traite que la seconde (p. 77). C'est en fermeture,
p. 91, qu'il renvoie la première à « another story », dont il dit n'avoir lu que la
première page du premier chapitre.

La tension qu'il résout est simple. La règle alors reçue, maximiser la valeur actualisée
des rendements anticipés, ne recommande jamais de diversifier. Or la diversification est
observée et sensée. Une règle qui ne l'implique pas doit donc être rejetée, comme
hypothèse descriptive et comme maxime.

## L'intuition économique

Le rendement espéré d'un portefeuille est linéaire dans les poids, sa variance ne l'est
pas. C'est toute la mécanique de l'article. Maximiser une grandeur linéaire sous des
poids qui somment à un donne toujours une solution en coin : tout l'argent sur le titre
au meilleur rendement anticipé. Markowitz le démontre en trois lignes, page 78. Ajouter
la variance comme grandeur indésirable brise cette linéarité, parce que la variance d'une
somme pondérée fait intervenir les covariances, la mesure de la tendance de deux titres à
dévier ensemble de leur moyenne.

Le mécanisme qui fait exister le gain est donc l'imparfaite corrélation entre titres, et
rien d'autre. Deux portefeuilles de même variance combinés donnent typiquement une
variance moindre, et Markowitz précise en note 12 le seul cas où ce n'est pas vrai : la
corrélation parfaite. C'est aussi ce qui ferait disparaître le gain. Si les rendements
étaient parfaitement corrélés, l'ensemble efficient se réduirait à des portefeuilles non
diversifiés, et la règle rejoindrait celle qu'elle remplace.

Markowitz écarte au passage une intuition concurrente, celle de la loi des grands
nombres. Répartir sur beaucoup de titres n'annule pas la variance : « The returns from
securities are too intercorrelated. Diversification cannot eliminate all variance »
(p. 79). D'où sa conséquence pratique, énoncée p. 89 : il ne suffit pas de détenir
soixante titres, il faut éviter ceux dont les covariances mutuelles sont fortes, donc
diversifier entre industries plutôt qu'à l'intérieur d'une seule.

## Les données

Aucune. L'article ne contient ni série de rendements, ni tableau de chiffres, ni exemple
numérique. Vérifié par lecture intégrale du fac-similé JSTOR le 2026-09-01 : les seules
figures sont sept schémas géométriques sans échelle chiffrée.

Markowitz dit seulement d'où les paramètres devraient venir. Il suggère de partir des moyennes et covariances observées sur une période passée, puis
d'ajuster à la main. Sa phrase de la page 91 : « I believe that better methods, which
take into account more information, can be found ». Cette phrase est le premier énoncé du problème d'erreur d'estimation que la
littérature ultérieure passera cinquante ans à traiter.

## L'univers

Trois titres pour l'exposé principal, quatre pour l'extension, N pour l'énoncé général.
Markowitz écrit explicitement qu'il ne dérive pas ses résultats analytiquement pour le
cas à N titres. Il les présente géométriquement pour les cas à 3 et 4 titres
(p. 79). Les ventes à découvert sont exclues, donc \(X_i \geq 0\). Les croyances de
probabilité sont statiques, hypothèse qu'il déclare comme une limite.

## La méthodologie

Géométrie plane, pas d'algorithme. Dans le cas à trois titres, la contrainte
\(X_1 + X_2 + X_3 = 1\) permet d'éliminer \(X_3\) et de travailler dans le plan
\((X_1, X_2)\). L'ensemble atteignable est le triangle \(abc\) de la figure 2.

Deux familles de courbes structurent le plan. Les courbes d'isomoyenne, l'ensemble des
portefeuilles de même rendement espéré, forment un système de droites parallèles. Les
courbes d'isovariance, l'ensemble des portefeuilles de même variance, forment un système
d'ellipses concentriques. Le centre de ce système est le portefeuille de variance
minimale.

L'ensemble efficient se lit alors comme un parcours. On part du point de variance minimale atteignable. On suit ensuite la droite critique, le
lieu des points qui minimisent la variance à rendement espéré donné, jusqu'à ce qu'elle
coupe une frontière. On longe enfin cette frontière jusqu'au point de rendement espéré
maximal.

## Les équations qui comptent

Le rendement du portefeuille est une somme pondérée de variables aléatoires, dont
l'espérance et la variance s'écrivent

\[ E = \sum_{i=1}^{N} X_i \mu_i, \qquad V = \sum_{i=1}^{N}\sum_{j=1}^{N} \sigma_{ij} X_i X_j, \]

sous \(\sum_i X_i = 1\) et \(X_i \geq 0\), où \(\sigma_{ij} = \rho_{ij}\sigma_i\sigma_j\)
est la covariance entre les titres \(i\) et \(j\).

Le rejet de la règle du rendement actualisé tient en une identité. Avec
\(R = \sum_i X_i R_i\) et des \(R_i\) indépendants des \(X_i\), le rendement \(R\) est
une moyenne pondérée à poids non négatifs. Son maximum est donc atteint en mettant
\(X_i = 1\) sur le plus grand \(R_i\).

La droite d'isomoyenne du cas à trois titres, pour \(\mu_2 \neq \mu_3\), s'écrit
\(X_2 = a + b X_1\) de pente

\[ b = -\frac{\mu_1 - \mu_3}{\mu_2 - \mu_3}, \qquad a = \frac{E_0 - \mu_3}{\mu_2 - \mu_3}. \]

Changer \(E_0\) déplace l'ordonnée à l'origine sans toucher la pente, ce qui établit le
parallélisme des droites d'isomoyenne.

## Les résultats originaux

Aucun chiffre : les résultats sont des énoncés de forme. Quatre méritent d'être retenus,
tous vérifiés dans le texte publié.

Un, la règle du rendement actualisé maximal n'implique jamais la supériorité d'un
portefeuille diversifié, quelle que soit la façon dont les taux d'actualisation sont
choisis (p. 77-78).

Deux, l'ensemble des portefeuilles efficients est une suite de segments de droite
connectés, dans le cas à 3 titres, à 4 titres et à N titres (p. 87).

Trois, dans le plan \((E, V)\), la section de la parabole de variance au-dessus de
l'ensemble efficient est une suite de segments de parabole connectés. Ce résultat vaut
pour un nombre quelconque de titres (p. 87).

Quatre, remplacer la variance par l'écart type ou par le coefficient de dispersion
\(\sigma/E\) laisse le choix de l'investisseur à l'intérieur du même ensemble efficient
(p. 89).

## Les critiques connues

Elles portent toutes sur l'application de la règle, jamais sur son algèbre.

**L'erreur d'estimation transforme l'optimiseur en amplificateur d'erreur.** Michaud
(1989), « The Markowitz optimization enigma: is optimized optimal? », Financial Analysts
Journal 45(1), p. 31-42, référence vérifiée dans Crossref le 2026-09-01, nomme le
phénomène « error maximization ». L'optimiseur mise le
plus fort sur les coefficients les plus faux, puisque ce sont eux qui paraissent les plus
attrayants. Ledoit et Wolf (2003, section 1 de la version de travail de « Honey, I Shrunk
the Sample Covariance Matrix ») reprennent le terme à leur compte, vérifié dans le texte.

**Les poids sont hypersensibles aux moyennes.** Best et Grauer (1991), Review of
Financial Studies 4(2), p. 315-342, référence vérifiée dans Crossref le 2026-09-01. Sous
la seule contrainte budgétaire, poids, moyenne
et variance d'un portefeuille efficient sont extrêmement sensibles à un changement des
espérances. Sous contraintes de non-négativité, une hausse faible de la moyenne d'un
seul actif chasse la moitié des titres du portefeuille, sans presque rien changer à son
rendement espéré ni à son écart type. Rapporté depuis la notice de l'éditeur, article non
consulté au 2026-09-01.

**Les erreurs sur les moyennes coûtent bien plus que celles sur les covariances.** Chopra
et Ziemba (1993), Journal of Portfolio Management 19(2), p. 6-11, référence vérifiée dans
Crossref le 2026-09-01. Le rapport souvent cité est de 11 pour 2 pour 1 entre moyennes,
variances et covariances à tolérance au risque 50 : **chiffre non vérifié au 2026-09-01**. Le fac-similé disponible est une image
numérisée dont le texte n'est pas extractible, et les résumés secondaires consultés
donnent des rapports différents, « environ 10 fois » et « plus de 20 fois ». À vérifier
sur le tirage papier avant tout usage.

**Hors échantillon, la règle perd contre 1/N.** DeMiguel, Garlappi et Uppal (2009). Voir
la fiche `demiguel_garlappi_uppal_2009.md`, qui donne les chiffres et les objections qui
leur ont été faites.

**Ce qui n'est pas une critique de Markowitz.** La critique de Roll (1977) est souvent
citée ici. Elle porte sur la testabilité du MEDAF, pas sur la règle espérance-variance,
et ne dit rien du choix de portefeuille de 1952. Ne pas la ranger dans cette section.

**Une objection anticipée dans l'article même.** Le critère de variance pénalise
symétriquement les écarts vers le haut et vers le bas. Markowitz le voit et l'écrit p. 90
et 91 : si l'utilité dépend aussi du troisième moment \(M_3\), avec
\(\partial U/\partial M_3 \neq 0\), alors certains paris actuariellement équitables sont
acceptés, ce que la règle E-V exclut. Il en tire lui-même la portée de sa règle, valable
pour l'investissement plutôt que pour la spéculation.

## Les problèmes de réplication connus

Il n'y a rien à répliquer numériquement. L'article ne publie aucun chiffre, donc aucune
cible de réplication au sens du présent dépôt. Ce qui se vérifie, ce sont des propriétés :
parallélisme des isomoyennes, forme elliptique des isovariances, et le fait que la
frontière soit polygonale par morceaux sous contraintes d'inégalité.

Deux pièges d'attribution méritent d'être notés. Le premier : l'algorithme de la droite
critique n'est PAS dans l'article de 1952. Markowitz y écrit « There are techniques by
which we can compute the set of efficient portfolios [...] We will not present these
techniques here » (p. 82), vérifié dans le texte. L'algorithme paraît en 1956 dans Naval
Research Logistics Quarterly 3(1-2), p. 111-133, référence vérifiée dans Crossref le
2026-09-01. Le second : l'article de 1952 ne contient ni
actif sans risque, ni ratio de Sharpe, ni portefeuille tangent, tous postérieurs.

## Les biais possibles

**Croyances statiques.** Markowitz déclare l'hypothèse comme une limite p. 79 et annonce
un traitement général ultérieur. Toute mise en oeuvre par fenêtre glissante suppose donc
implicitement une stationnarité que l'article ne revendique pas.

**Paramètres traités comme connus.** Les \(\mu_i\) et \(\sigma_{ij}\) entrent dans la
règle comme des données, pas comme des estimations. C'est la porte par laquelle entrent
toutes les critiques d'erreur d'estimation ci-dessus.

**Absence de ventes à découvert.** L'exclusion \(X_i \geq 0\) est posée d'entrée et
justifiée en note 4 : sans elle, sous la règle du rendement actualisé, une somme infinie
irait sur le titre au plus fort rendement. Une réplication qui autorise le découvert
change l'ensemble efficient et n'est plus l'article.

**Aucun coût de transaction.** L'article n'en parle pas. Toute conclusion sur la
performance réalisée d'un portefeuille E-V doit les réintroduire.

## Nos décisions d'implémentation

non commencé au 2026-09-01

## Nos écarts avec l'article

non commencé au 2026-09-01

## Nos résultats

non commencé au 2026-09-01

## Notre contrôle de robustesse

non commencé au 2026-09-01

## Références

- Markowitz, H. (1952), « Portfolio Selection », The Journal of Finance 7(1), p. 77-91.
  Fac-similé consulté : http://www.efalken.com/LowVolClassics/markowitz_JF1952.pdf
- Markowitz, H. (1956), « The optimization of a quadratic function subject to linear
  constraints », Naval Research Logistics Quarterly 3(1-2), p. 111-133.
  https://onlinelibrary.wiley.com/doi/abs/10.1002/nav.3800030110
- Michaud, R. (1989), « The Markowitz Optimization Enigma: Is Optimized Optimal? »,
  Financial Analysts Journal 45(1), p. 31-42.
- Best, M. et Grauer, R. (1991), « On the Sensitivity of Mean-Variance-Efficient
  Portfolios to Changes in Asset Means », Review of Financial Studies 4(2), p. 315-342.
  https://academic.oup.com/rfs/article-abstract/4/2/315/1571031
- Chopra, V. et Ziemba, W. (1993), « The Effect of Errors in Means, Variances, and
  Covariances on Optimal Portfolio Choice », Journal of Portfolio Management 19(2),
  p. 6-11. https://jpm.pm-research.com/content/19/2/6
- DeMiguel, V., Garlappi, L. et Uppal, R. (2009), « Optimal Versus Naive Diversification »,
  Review of Financial Studies 22(5), p. 1915-1953. Fiche interne :
  `demiguel_garlappi_uppal_2009.md`
- Ledoit, O. et Wolf, M. (2004), « Honey, I Shrunk the Sample Covariance Matrix »,
  Journal of Portfolio Management 30(4), p. 110-119. Fiche interne : `ledoit_wolf_2004.md`

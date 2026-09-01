# Rétrécissement de la matrice de covariance

| | |
|---|---|
| **Auteurs** | Olivier Ledoit, Michael Wolf |
| **Année** | 2004 (les deux articles) |
| **Revue ou source** | Journal of Multivariate Analysis, vol. 88, no 2, p. 365-411, « A Well-Conditioned Estimator for Large-Dimensional Covariance Matrices » ; The Journal of Portfolio Management, vol. 30, no 4, p. 110-119, « Honey, I Shrunk the Sample Covariance Matrix » |
| **Lien** | JMVA : https://perso.ens-lyon.fr/patrick.flandrin/LedoitWolf_JMA2004.pdf (article publié, 47 pages, lu le 2026-09-01). Honey : https://www.econ.uzh.ch/dam/jcr:ffffffff-961c-1dd9-ffff-ffffb4762fbf/honey.pdf (version de travail de novembre 2003, 22 pages, lue le 2026-09-01). Notice éditeur : https://www.pm-research.com/content/iijpormgmt/30/4/110 |
| **Statut de réplication** | non commencé |

Les deux articles sont traités dans une fiche unique parce qu'ils partagent la même
mécanique et ne diffèrent que par la cible. Le JMVA rétrécit vers l'identité et démontre
le théorème ; le JPM rétrécit vers la corrélation constante et mesure le gain d'un
gérant. La version consultée du second est le document de travail de novembre 2003, non
la version imprimée du JPM.

## La question de recherche

Comment estimer une matrice de covariance quand le nombre de variables n'est pas
négligeable devant le nombre d'observations ? La matrice de covariance d'échantillon est
sans biais, mais elle est mal conditionnée, ce qui veut dire que l'inverser amplifie
l'erreur d'estimation. Quand \(N \geq T\), elle n'est même plus inversible. Or c'est son
inverse qui entre dans le portefeuille espérance-variance.

## L'intuition économique

Les coefficients extrêmes de la matrice d'échantillon sont extrêmes parce qu'ils
contiennent beaucoup d'erreur, pas parce que la vérité est extrême. L'optimiseur mise le
plus fort exactement là. C'est ce que Michaud (1989) appelle l'amplification d'erreur, et
les auteurs reprennent le terme au premier paragraphe de « Honey ».

Le mécanisme est un arbitrage entre biais et variance. La matrice d'échantillon est sans
biais mais très dispersée ; une matrice fortement structurée, un modèle à un facteur ou
une corrélation constante, est peu dispersée mais biaisée. Une combinaison convexe des
deux est meilleure que chacune, et le poids optimal se calcule au lieu de se deviner.

Ce qui ferait disparaître le gain est écrit noir sur blanc dans le JMVA : si la matrice
d'échantillon est déjà précise, il ne faut pas la rétrécir beaucoup, et la rétrécir
n'apporterait pas grand-chose. Tout est gouverné par le rapport \(\beta^2/\delta^2\),
mesure normalisée de l'erreur de la matrice d'échantillon. Le rétrécissement cesse de
compter quand le rapport du nombre de variables au nombre d'observations est négligeable,
et seulement alors.

Une objection sérieuse existe, et les auteurs la citent eux-mêmes. Jagannathan et Ma
(2003) montrent qu'interdire la vente à découvert applique déjà un rétrécissement
implicite à la matrice de covariance. Un gérant contraint récolterait donc une partie du
gain sans rien faire. La réponse de « Honey » est qu'il vaut mieux le faire
explicitement, avec l'intensité optimale, plutôt qu'implicitement à intensité subie.

## Les données

**JMVA 2004 : aucune donnée réelle.** L'article est théorique. Ses chiffres viennent de
1 000 simulations de Monte-Carlo à variables normales, matrice vraie diagonale sans perte
de généralité, valeurs propres tirées d'une loi log-normale de moyenne d'ensemble
\(m = 1\).

**Honey 2003-2004 : actions américaines mensuelles de DataStream.** Les auteurs
construisent eux-mêmes plusieurs indices pondérés par la capitalisation. Chaque début de
mois ils retiennent les \(N\) plus grosses capitalisations, dont les valeurs de marché
donnent les poids de l'indice, et la liste des constituants comme les poids sont mis à
jour chaque mois. La période hors échantillon va de 02/1983 à 12/2002, soit 239
rendements excédentaires mensuels.

Statistiques annualisées des indices de référence construits, tableau 1 du document de
travail :

| | N = 30 | N = 50 | N = 100 | N = 225 | N = 500 |
|---|---|---|---|---|---|
| Moyenne | 13,63 | 13,50 | 13,29 | 13,45 | 13,42 |
| Écart type | 15,12 | 15,02 | 14,76 | 14,56 | 14,52 |

## L'univers

Cinq tailles d'indice, \(N = 30, 50, 100, 225, 500\). Elles sont choisies pour couvrir le
DJIA, le Xetra DAX, le DJ STOXX 50, le FTSE 100, le NASDAQ-100, le NIKKEI 225 et le
S&P 500. La
fenêtre d'estimation est fixe : les 60 derniers rendements mensuels de la liste courante
des constituants, donc \(T = 60\). Les deux plus grands univers ont \(N \gg T\), et la
matrice d'échantillon y est singulière. C'est là que le rétrécissement cesse d'être un
raffinement pour devenir la condition d'existence du calcul.

Côté simulations du JMVA, les valeurs centrales sont \(p/n = 1/2\), \(\alpha^2 = 1/2\) et
\(p \times n = 800\), donc \(p = 20\) et \(n = 40\).

## La méthodologie

**JMVA.** Le critère est la norme de Frobenius relative, définie de sorte que la matrice
identité ait une norme égale à un en toute dimension : \(\|A\|^2 = \mathrm{tr}(AA^t)/p\).
Le cadre asymptotique est dit général : le nombre de variables \(p_n\) et le nombre
d'observations \(n\) tendent ensemble vers l'infini, avec \(p_n/n\) borné, sans exiger que
ce rapport converge. L'estimateur est d'abord dérivé avec les paramètres vrais, puis
chacun est remplacé par un estimateur convergent, et un théorème montre que la
substitution ne change pas les propriétés asymptotiques.

**Honey.** Le gérant minimise la variance d'erreur de suivi \(x^{\top}\Sigma x\) sous
quatre contraintes : gain visé \(x^{\top}\alpha \geq g\), somme des écarts nulle
\(x^{\top}1 = 0\), interdiction de la vente à découvert \(x \geq -w_B\), et plafond de
position \(x \leq c\,1 - w_B\). Les valeurs retenues sont \(g = 300\) points de base
annualisés et \(c = 0{,}10\).

Les prévisions de rendement excédentaire sont fabriquées avec vue rétrospective, en
ajoutant du bruit gaussien aux rendements excédentaires réalisés. Le bruit est calibré
pour que le ratio d'information ex ante non contraint vaille approximativement 1,5 quel
que soit \(N\), via la loi fondamentale de la gestion active \(IR \approx IC\sqrt{B}\)
avec \(B = 12N\). Le coefficient d'information vaut donc \(IC = 1{,}5/\sqrt{12N}\), soit
0,0791 à \(N = 30\), 0,0433 à \(N = 100\) et 0,0194 à \(N = 500\). Comme les prévisions
sont aléatoires, tout le protocole est répété 50 fois et les tableaux donnent des
moyennes.

Le point à retenir pour la lecture des résultats : seul l'estimateur de covariance change
d'une ligne à l'autre. Les prévisions de rendement, les contraintes et l'optimiseur sont
identiques. L'écart mesuré est donc imputable au modèle de risque et à rien d'autre.

## Les équations qui comptent

**Cible identité, article du JMVA.** Quatre scalaires gouvernent tout, avec
\(\langle A_1, A_2\rangle = \mathrm{tr}(A_1A_2^t)/p\) :

\[ \mu = \langle \Sigma, I\rangle, \quad \alpha^2 = \|\Sigma - \mu I\|^2, \quad \beta^2 = E\|S - \Sigma\|^2, \quad \delta^2 = E\|S - \mu I\|^2, \]

et le lemme 2.1 les relie par \(\alpha^2 + \beta^2 = \delta^2\). Le théorème 2.1 donne la
combinaison linéaire optimale de l'identité et de la matrice d'échantillon :

\[ \Sigma^{*} = \frac{\beta^2}{\delta^2}\,\mu I \;+\; \frac{\alpha^2}{\delta^2}\,S, \qquad E\|\Sigma^{*} - \Sigma\|^2 = \frac{\alpha^2\beta^2}{\delta^2}. \]

**L'intensité de rétrécissement est \(\beta^2/\delta^2\)**, et elle est égale au gain
relatif en perte moyenne sur la matrice d'échantillon, que les auteurs appellent PRIAL.
La même quantité mesure donc combien on rétrécit et combien on gagne.

L'estimateur utilisable remplace les quatre inconnues par leurs contreparties
d'échantillon. Avec \(x_k^n\) la \(k\)-ième colonne des observations :

\[ m_n = \langle S_n, I_n\rangle, \quad d_n^2 = \|S_n - m_n I_n\|_n^2, \quad \bar{b}_n^2 = \frac{1}{n^2}\sum_{k=1}^{n}\left\|x_k^n (x_k^n)^{t} - S_n\right\|_n^2, \]

\[ b_n^2 = \min(\bar{b}_n^2, d_n^2), \quad a_n^2 = d_n^2 - b_n^2, \qquad \hat{\Sigma}_n^{*} = \frac{b_n^2}{d_n^2} m_n I_n + \frac{a_n^2}{d_n^2} S_n. \]

La troncature \(b_n^2 = \min(\bar{b}_n^2, d_n^2)\) vient du lemme 2.1, qui impose
\(\beta^2 \leq \delta^2\) ; elle est rarement mordante et sert à garantir \(a_n^2 \geq 0\).

**Ce que vaut l'intensité quand N dépasse T.** Le théorème 3.1 donne
\(E\|S_n - \Sigma_n\|_n^2 \approx \frac{p_n}{n}(m_n^2 + \theta_n^2)\), où \(\theta_n^2\)
est nul dans le cas normal. En reportant dans \(\delta^2 = \alpha^2 + \beta^2\) et en
normalisant \(m = 1\) comme le fait la section 4.2, l'intensité asymptotique s'écrit

\[ \frac{\beta^2}{\delta^2} = \frac{p/n}{p/n + \alpha^2}. \]

Elle croît de 0 à 100 % selon une courbe en S quand \(p/n\) va de zéro à l'infini, ce que
la section 4.3.1 énonce et que la figure 6 confirme. **Quand le nombre de variables dépasse
largement le nombre d'observations, l'intensité tend vers un et l'estimateur tend vers la
cible pure \(\mu I\)**. Cette cible est l'identité mise à l'échelle de la variance moyenne
d'échantillon. Aux valeurs centrales \(p/n = 1/2\) et \(\alpha^2 = 1/2\), elle vaut
exactement 50 %.

Deux garanties accompagnent ce régime. L'estimateur reste inversible même pour
\(p_n > n\), où la déficience de rang rend \(S_n\) singulière, et le théorème 3.5 montre
que son conditionnement reste borné en probabilité si celui de la matrice vraie l'est.

**Cible corrélation constante, article du JPM.** La cible \(F\) garde les variances
d'échantillon et remplace toutes les corrélations par leur moyenne \(\bar{r}\) :

\[ f_{ii} = s_{ii}, \qquad f_{ij} = \bar{r}\sqrt{s_{ii}s_{jj}}, \qquad \hat{\Sigma}_{\text{Shrink}} = \hat{\delta}^{*}F + (1-\hat{\delta}^{*})S. \]

Sous \(N\) fixe et \(T \to \infty\), l'intensité optimale se comporte comme une constante
divisée par \(T\), et cette constante s'écrit

\[ \kappa = \frac{\pi - \rho}{\gamma}, \]

avec trois ingrédients tous sommés sur les \(N^2\) entrées.
\(\pi = \sum_i\sum_j \mathrm{AsyVar}[\sqrt{T}s_{ij}]\) est la somme des variances
asymptotiques des entrées de la matrice d'échantillon.
\(\rho = \sum_i\sum_j \mathrm{AsyCov}[\sqrt{T}f_{ij}, \sqrt{T}s_{ij}]\) est la somme des
covariances asymptotiques entre cible et échantillon.
\(\gamma = \sum_i\sum_j (\phi_{ij} - \sigma_{ij})^2\) mesure la mauvaise spécification
de la cible de population.

Les estimateurs convergents sont
\(\hat{\pi}_{ij} = \frac{1}{T}\sum_t \{(y_{it}-\bar{y}_{i\cdot})(y_{jt}-\bar{y}_{j\cdot}) - s_{ij}\}^2\),
\(\hat{\gamma} = \sum_i\sum_j (f_{ij}-s_{ij})^2\), et pour \(\hat{\rho}\)

\[ \hat{\rho} = \sum_{i=1}^{N}\hat{\pi}_{ii} + \sum_{i=1}^{N}\sum_{j \neq i} \frac{\bar{r}}{2}\left(\sqrt{\tfrac{s_{jj}}{s_{ii}}}\,\hat{\vartheta}_{ii,ij} + \sqrt{\tfrac{s_{ii}}{s_{jj}}}\,\hat{\vartheta}_{jj,ij}\right), \]

où \(\hat{\vartheta}_{ii,ij} = \frac{1}{T}\sum_t \{(y_{it}-\bar{y}_{i\cdot})^2 - s_{ii}\}\{(y_{it}-\bar{y}_{i\cdot})(y_{jt}-\bar{y}_{j\cdot}) - s_{ij}\}\),
et symétriquement pour \(\hat{\vartheta}_{jj,ij}\). L'intensité utilisée en pratique est
alors

\[ \hat{\delta}^{*} = \max\left\{0,\ \min\left(\frac{\hat{\kappa}}{T},\ 1\right)\right\}. \]

**Ce que vaut cette intensité quand N dépasse T.** La formule ne change pas : c'est la
troncature à 1 qui absorbe le cas, et les auteurs écrivent qu'elle joue très rarement.
L'article ne donne pas de forme fermée de \(\hat{\delta}^{*}\) en fonction de \(N/T\), et
il ne faut donc rien en déduire. Ce qu'il établit, en note 5, c'est que l'estimateur reste
défini positif quand \(N\) dépasse \(T\), parce qu'il combine une cible définie positive
et une matrice d'échantillon semi-définie positive. Son annexe B explique aussi pourquoi ses
concurrents ne le peuvent pas. Les estimateurs de rétrécissement issus de la théorie de
la décision en petit échantillon, comme celui de Frost et Savarino (1986), ont des
fonctions de perte qui font intervenir l'inverse de la matrice. Ils cassent donc dès
\(N \geq T\). La perte de Frobenius, elle, ne fait pas intervenir cet inverse.

## Les résultats originaux

**JMVA, tableau 2, 1 000 simulations aux valeurs centrales \(p = 20\), \(n = 40\),
\(\alpha^2 = 1/2\).** Le PRIAL asymptotique attendu est de 50 % et le PRIAL simulé de
49,3 %, ce qui montre que le comportement asymptotique est presque atteint dès 20
variables et 40 observations.

| Estimateur | S | \(\hat{\Sigma}^{*}\) | \(\hat{\Sigma}_{EB}\) | \(\hat{\Sigma}_{SH}\) | \(\hat{\Sigma}_{MX}\) |
|---|---|---|---|---|---|
| Risque | 0,5372 | 0,2723 | 0,5120 | 0,3076 | 0,3222 |
| Erreur type | (0,0033) | (0,0013) | (0,0031) | (0,0014) | (0,0014) |
| PRIAL | 0,0 % | 49,3 % | 4,7 % | 42,7 % | 40,0 % |

Trois conclusions de la section 4.3.5, reprises telles quelles. L'approximation
asymptotique décrit bien le fini dès que \(n\) et \(p\) sont de l'ordre de 20.
L'estimateur améliore la matrice d'échantillon dans toutes les situations simulées.
Il n'est jamais nettement moins bon que les deux concurrents \(\hat{\Sigma}_{SH}\) et
\(\hat{\Sigma}_{MX}\), lesquels font parfois pire que la matrice d'échantillon quand la
dispersion des valeurs propres est forte.

**Honey, tableau 2, ratios d'information ex post annualisés, gain fixé à 300 points de
base, moyennes sur 50 répétitions.** Les quatre lignes comparées :

- « Sample », la matrice de covariance d'échantillon ;
- « Shrink-CC », l'estimateur à corrélation constante du présent article ;
- « Shrink-SF », l'estimateur à facteur unique de Ledoit et Wolf (2003) ;
- « PC-5 », un modèle à cinq composantes principales.

| N | Sample | Shrink-CC | Shrink-SF | PC-5 |
|---|---|---|---|---|
| 30 | 0,97 | **1,24** | 1,18 | 1,17 |
| 50 | 0,79 | **1,14** | 1,08 | 1,11 |
| 100 | 0,59 | **0,91** | 0,89 | 0,91 |
| 225 | 0,37 | 0,54 | **0,57** | 0,55 |
| 500 | 0,20 | 0,30 | **0,33** | 0,31 |

Écarts types annualisés des rendements excédentaires, même tableau : Shrink-CC fait mieux
que la matrice d'échantillon dans les cinq cas. Trois exemples, 2,03 contre 2,26 à
\(N = 30\), 2,06 contre 2,93 à \(N = 100\), et 5,77 contre 8,53 à \(N = 500\).

Il n'est pas pour autant le plus bas des quatre estimateurs, et le texte de l'article peut
le laisser croire. Sa liste à puces annonce « in all scenarios, the shrinkage estimator
yields the lowest (average) standard deviation of excess return ». Mais elle ne compare
qu'à la matrice d'échantillon, comme le dit sa phrase d'introduction. Son propre tableau 2
donne 4,30 à Shrink-SF contre 4,97 à Shrink-CC pour \(N = 225\), et 5,05 à PC-5 contre
5,77 pour \(N = 500\). La rotation mensuelle moyenne du tableau 3
est la plus élevée pour la matrice d'échantillon dans tous les cas : 0,39 contre 0,33 à
\(N = 30\), 0,85 contre 0,75 à \(N = 500\).

La conclusion de l'article tient en une phrase. Pour un rendement excédentaire annuel
visé de 300 points de base au-dessus de l'indice, la hausse typique du ratio
d'information réalisé est de l'ordre de 50 %. Ce chiffre se retrouve sur la
table : 0,20 devient 0,30 à \(N = 500\), 0,59 devient 0,91 à \(N = 100\).

Deux nuances que le résumé ne porte pas. La cible à corrélation constante bat la cible à
facteur unique pour \(N \leq 100\) et perd contre elle pour \(N \geq 225\). Et le ratio
d'information décroît quand \(N\) croît, pour toutes les méthodes, effet que les auteurs
attribuent à la contrainte de position longue seule sur un indice pondéré large.

## Les critiques connues

**Le rétrécissement linéaire est asymptotiquement sous-optimal, et ce sont les auteurs
qui le disent.** Une intensité unique appliquée à toutes les valeurs propres est trop
rigide. Ledoit et Wolf y répondent par le rétrécissement non linéaire, qui traite chaque valeur
propre séparément. Trois jalons : Annals of Statistics en 2012 et 2017, puis « Nonlinear
Shrinkage of the Covariance Matrix for Portfolio Selection: Markowitz Meets Goldilocks »,
Review of Financial Studies 30(12), p. 4349-4388, 2017. Ce dernier rapporte que le non
linéaire domine le linéaire sur données boursières historiques. Articles non consultés au
2026-09-01 ; le fait de la domination est rapporté depuis les notices d'éditeur.

**Les contraintes de portefeuille font déjà le travail.** Jagannathan et Ma (2003),
Journal of Finance 58(4), p. 1651-1683, volume et pagination vérifiés dans Crossref le
2026-09-01. La bibliographie de « Honey » imprime « 54(4):1651-1684 », qui est faux : le
volume 54 du Journal of Finance est celui de 1999. DeMiguel, Garlappi et Uppal citent
textuellement leur phrase de la page 1654. Sous contrainte de vente à découvert,
« the sample covariance matrix performs almost as well as those constructed using factor
models, shrinkage estimators or daily returns ». Vérifié dans le texte du document de travail de
DGU, dont c'est la justification explicite pour NE PAS évaluer Ledoit (1996) ni Ledoit et
Wolf (2003) parmi leurs quatorze modèles. C'est l'objection la plus lourde contre l'usage
pratique du rétrécissement, et elle est admise par les auteurs eux-mêmes en introduction
de « Honey ».

**Le gain mesuré dépend d'un gérant fabriqué.** Les prévisions de rendement de « Honey »
sont construites en ajoutant du bruit aux rendements réalisés, donc avec vue
rétrospective. Elles sont calibrées pour un ratio d'information ex ante de 1,5. C'est une
hypothèse déclarée par les auteurs en section 4 et en annexe C, pas un défaut caché. Reste
que le chiffre de « +50 % de ratio d'information » est conditionnel à un gérant qui a
réellement cette compétence de prévision.

**Aucune critique publiée du théorème lui-même n'a été trouvée au 2026-09-01.** Les
recherches menées n'ont ramené que des travaux d'extension, non des réfutations. Résultat
négatif, écrit comme tel.

## Les problèmes de réplication connus

**Aucun échec de réplication publié n'a été trouvé au 2026-09-01.** Ce qui suit relève des
pièges de mise en oeuvre, tous vérifiés sur les articles ou sur la documentation des
bibliothèques.

**Le piège principal : « le » rétrécissement de Ledoit-Wolf n'existe pas, il y en a au
moins trois.** Trois cibles coexistent : l'identité de l'article du JMVA, le facteur unique de Ledoit
et Wolf (2003, Journal of Empirical Finance 10(5), p. 603-621), et la corrélation
constante de « Honey ». Elles donnent des matrices et des intensités différentes.
`sklearn.covariance.LedoitWolf` met en oeuvre la première : sa documentation écrit
`(1 - shrinkage) * cov + shrinkage * mu * np.identity(n_features)` avec
`mu = trace(cov) / n_features`, et cite le JMVA 2004. `pypfopt.risk_models.CovarianceShrinkage`
offre les trois par un seul appel, `ledoit_wolf(shrinkage_target=...)`, dont l'argument
vaut `constant_variance` par défaut, ou `single_factor`, ou `constant_correlation`. Un résultat comparé à
la mauvaise cible sera faux sans qu'aucun test ne le signale. Vérifié sur la
documentation en ligne des deux paquets le 2026-09-01.

**La convention de norme change les nombres, pas les poids.** Le JMVA divise la norme de
Frobenius par \(p\), de sorte que l'identité ait une norme égale à un. La plupart des
implémentations utilisent la norme de Frobenius ordinaire. Le rapport
\(\beta^2/\delta^2\) est invariant, mais les valeurs de \(\alpha^2\), \(\beta^2\) et
\(\delta^2\) prises isolément diffèrent d'un facteur \(p\). Comparer ces intermédiaires
sans corriger la convention produit un faux écart.

**Le dénominateur de la matrice d'échantillon.** Le JMVA définit \(S_n = X_nX_n^t/n\),
donc sans correction de degré de liberté et sans retrait de la moyenne. Une
implémentation qui divise par \(n-1\) et centre les données ne calcule pas exactement le
même objet. À déclarer.

**Les données de « Honey » ne sont pas reproductibles à l'identique.** Elles viennent de
DataStream, sous licence, et les indices sont construits par les auteurs mois par mois.
De plus les prévisions de rendement sont tirées au hasard 50 fois, sans graine publiée,
donc les tableaux ne sont reproductibles qu'en moyenne, à l'erreur de simulation près.

**Le code Matlab d'origine.** L'article annonce que le code est librement téléchargeable
depuis http://www.ledoit.net. Ce domaine a répondu par une erreur de certificat au
2026-09-01 depuis cet environnement ; **disponibilité du code non vérifiée**.

## Les biais possibles

**Rendements indépendants et identiquement distribués dans le temps.** L'annexe A de
« Honey » pose l'hypothèse explicitement, avec moments d'ordre quatre finis. Les
rendements d'actions ne sont pas homoscédastiques, et l'intensité estimée sur une fenêtre
qui traverse un changement de régime n'a pas la propriété d'optimalité annoncée.

**Le cadre asymptotique du JMVA borne \(p_n/n\).** L'hypothèse 1 exige l'existence d'une
constante \(K_1\) telle que \(p_n/n \leq K_1\). Les résultats ne couvrent donc pas un
rapport qui exploserait.

**La cible à corrélation constante suppose des actifs d'une même classe.** La note 4 de
« Honey » le dit : le modèle ne conviendrait pas si les actifs venaient de classes
différentes, actions et obligations par exemple. Un portefeuille multi-actifs demande une
autre cible.

**Le protocole de « Honey » ne déduit aucun coût de transaction.** La rotation est mesurée
séparément, au tableau 3, et les auteurs écrivent qu'elle est en général trop élevée pour
être attrayante, aucun effort n'ayant été fait pour la limiter. Les ratios d'information
publiés sont donc bruts.

**La performance mesurée est relative à un indice, pas absolue.** L'objectif est la
variance d'erreur de suivi, et la remarque 2 de l'article rappelle qu'un portefeuille
efficient en erreur de suivi n'est pas efficient en espérance-variance.

## Nos décisions d'implémentation

non commencé au 2026-09-01

## Nos écarts avec l'article

non commencé au 2026-09-01

## Nos résultats

non commencé au 2026-09-01

## Notre contrôle de robustesse

non commencé au 2026-09-01

## Références

- Ledoit, O. et Wolf, M. (2004), « A Well-Conditioned Estimator for Large-Dimensional
  Covariance Matrices », Journal of Multivariate Analysis 88(2), p. 365-411.
  https://perso.ens-lyon.fr/patrick.flandrin/LedoitWolf_JMA2004.pdf
- Ledoit, O. et Wolf, M. (2004), « Honey, I Shrunk the Sample Covariance Matrix »,
  Journal of Portfolio Management 30(4), p. 110-119. Version de travail de novembre 2003
  consultée : https://www.econ.uzh.ch/dam/jcr:ffffffff-961c-1dd9-ffff-ffffb4762fbf/honey.pdf
- Ledoit, O. et Wolf, M. (2003), « Improved estimation of the covariance matrix of stock
  returns with an application to portfolio selection », Journal of Empirical Finance
  10(5), p. 603-621. Cible à facteur unique ; non consulté.
- Ledoit, O. et Wolf, M. (2017), « Nonlinear Shrinkage of the Covariance Matrix for
  Portfolio Selection: Markowitz Meets Goldilocks », Review of Financial Studies 30(12),
  p. 4349-4388. https://academic.oup.com/rfs/article-abstract/30/12/4349/3863121
- Jagannathan, R. et Ma, T. (2003), « Risk Reduction in Large Portfolios: Why Imposing the
  Wrong Constraints Helps », Journal of Finance 58(4), p. 1651-1683. Volume et pagination
  vérifiés dans Crossref le 2026-09-01, contre le « 54(4):1651-1684 » de la bibliographie
  de « Honey » ; article non consulté.
- Michaud, R. (1989), « The Markowitz Optimization Enigma: Is Optimized Optimal? »,
  Financial Analysts Journal 45, p. 31-42.
- Frost, P. et Savarino, J. (1986), « An empirical Bayes approach to portfolio selection »,
  Journal of Financial and Quantitative Analysis 21, p. 293-305. Cité ; non consulté.
- Grinold, R. et Kahn, R. (2000), Active Portfolio Management, McGraw-Hill, 2e édition.
  Source de la loi fondamentale et de la définition de rotation utilisées ; non consulté.
- Documentation `sklearn.covariance.LedoitWolf` :
  https://scikit-learn.org/stable/modules/generated/sklearn.covariance.LedoitWolf.html
- Documentation `pypfopt.risk_models` :
  https://pyportfolioopt.readthedocs.io/en/latest/RiskModels.html
- Markowitz, H. (1952). Fiche interne : `markowitz_1952.md`
- DeMiguel, V., Garlappi, L. et Uppal, R. (2009). Fiche interne :
  `demiguel_garlappi_uppal_2009.md`

# Statistical Arbitrage in the US Equities Market

| | |
|---|---|
| **Auteurs** | Marco Avellaneda (Courant Institute, New York University, et Finance Concepts, Paris), Jeong-Hyun Lee (Courant Institute) |
| **Année** | 2010 (reçu le 1er juillet 2008, version finale le 17 juin 2009, mise en ligne le 4 janvier 2010) |
| **Revue ou source** | Quantitative Finance, vol. 10, no 7 (août-septembre 2010), p. 761-782, doi:10.1080/14697680903124632 |
| **Lien** | Fac-similé de l'article publié, consulté et lu intégralement le 2026-09-01 : https://traders.studentorg.berkeley.edu/papers/Statistical%20arbitrage%20in%20the%20US%20equities%20market.pdf ; notice de l'éditeur : https://www.tandfonline.com/doi/abs/10.1080/14697680903124632 ; page SSRN : https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1153505 |
| **Statut de réplication** | non commencé |

## La question de recherche

Peut-on remplacer l'appariement deux à deux par une décomposition factorielle et gagner
davantage ? L'article prend le pairs trading au sérieux comme cas particulier, puis le
généralise : au lieu d'apparier une action à une autre, il l'apparie à un portefeuille de
facteurs, et négocie le résidu.

Deux façons de construire ces facteurs sont mises en concurrence, sur le même univers et la
même règle. La première est l'analyse en composantes principales de la matrice de corrélation
des rendements. La seconde est la régression sur des fonds négociés en bourse sectoriels. La question secondaire, qui
devient la plus intéressante à la lecture, est celle du nombre de facteurs à retirer. Trop peu,
et le résidu garde du risque systématique. Trop, et il ne reste plus assez de variance pour
payer les frais.

## L'intuition économique

Le rendement existe parce que celui qui prend le contre-pied fournit de la liquidité, et que
ce service se paie. Une action monte ou baisse par rapport à son secteur pour une raison qui
n'est pas toujours une information : un gérant liquide une ligne, un indice se rebalance, un
carnet d'ordres se vide. Celui qui achète ce que personne ne veut, et vend ce que tout le
monde veut, encaisse le retour à l'équilibre. C'est le mécanisme que Khandani et Lo (2007)
décrivent pour les stratégies de contre-tendance, et les auteurs se placent explicitement dans
la même famille (p. 780).

L'article ajoute une condition que le pairs trading classique laisse implicite. Le retour à la
moyenne n'a de sens que sur un résidu, c'est-à-dire sur ce qui reste du rendement après avoir
retiré les facteurs communs. Les prix eux-mêmes ne reviennent pas à une moyenne, le marché
monte. Le résidu, lui, le peut, et l'article le modélise par un processus d'Ornstein-Uhlenbeck,
un processus qui est rappelé vers une valeur d'équilibre à une vitesse constante.

Ce qui ferait disparaître le rendement est nommé, et l'article en donne deux formes. La
première est l'encombrement : en août 2007, plusieurs gérants ont dû réduire leurs positions en
même temps, et toutes les variantes testées subissent le même creux (figure 20, p. 779). La
seconde est plus mécanique et vaut comme avertissement de conception. Si l'on retire trop de
facteurs, le résidu n'a presque plus de variance et les frais l'emportent. Les auteurs mesurent
qu'une coupure à 75 % de la variance expliquée « leads invariably to steady losses » (p. 777).
Ils concluent par un mot qui résume la leçon : « Using too many factors lead to noise trading ».

La conjecture finale de l'article relie la stratégie au cycle. Elle marche mieux quand un petit
nombre de facteurs suffit à expliquer la moitié de la variance, c'est-à-dire en période de
tension, et moins bien quand la variance est répartie sur beaucoup de modes. Le nombre de
vecteurs propres nécessaires varie en sens inverse de l'indice VIX (figure 12, p. 774).

## Les données

Cours de clôture quotidiens, ajustés des dividendes. Les auteurs n'identifient pas leur
fournisseur dans l'article consulté.

Les signaux par analyse en composantes principales remontent à 1996. Les rendements de
stratégie ne sont publiés qu'à partir de 1997, parce qu'il faut une année entière de données
pour calculer la première matrice de corrélation (note de la table 6, p. 774). Les signaux par
fonds négociés en bourse réels ne commencent qu'en 2002, date à laquelle les fonds sectoriels
existent. Avant 2002, les auteurs utilisent des fonds « synthétiques ». Ce sont des indices sectoriels
pondérés par la capitalisation, construits avec les titres de l'univers présents à la date du
signal (note de bas de page, p. 763).

L'échantillon de rendements va donc de 1996 ou 1997 à 2007 selon la variante. La figure 12
pousse une mesure descriptive jusqu'à février 2008.

## L'univers

Toutes les actions américaines dont la capitalisation boursière dépasse un milliard de dollars
américains **à la date de négociation**. Les auteurs insistent sur ce point p. 763. La
condition porte sur la capitalisation au moment du signal, et non sur celle observée au moment
où l'article a été écrit. C'est ce qui évite le biais du survivant.

La table 3 (p. 767) donne la photographie au 1er janvier 2007. Elle compte 1 417 titres
répartis en quinze secteurs, capitalisation moyenne de 11 291 M$, maximum de 432 200 M$,
minimum de 1 000 M$. Les quinze fonds sectoriels servant de facteurs, avec le nombre de titres de chacun au
1er janvier 2007, sont les suivants.

| Fonds | Secteur | Titres | Fonds | Secteur | Titres |
|---|---|---|---|---|---|
| HHH | Internet | 22 | XLE | Énergie | 75 |
| IYR | Immobilier | 87 | XLF | Finance | 210 |
| IYT | Transport | 46 | XLI | Industrie | 141 |
| OIH | Exploration pétrolière | 42 | XLK | Technologie | 158 |
| RKH | Banques régionales | 69 | XLP | Consommation de base | 61 |
| RTH | Distribution | 60 | XLV | Santé | 109 |
| SMH | Semi-conducteurs | 55 | XLY | Consommation discrétionnaire | 207 |
| UTH | Services publics | 75 | | | |

Deux de ces symboles sont imprimés « XU » et « XIV » dans la table 3 du fac-similé consulté, à
la place de XLI et XLV. Les entêtes de colonne des tables 4, 5, 6, 7 et 9 les écrivent
correctement, et le rapprochement avec les secteurs nommés ne laisse pas de doute. Il s'agit
d'un défaut d'impression ou d'extraction, et non d'un choix des auteurs.

## La méthodologie

La chaîne compte huit étapes, refaites chaque jour de bourse.

**Un. Matrice de corrélation.** Sur une fenêtre de 252 jours de bourse, soit un an, précédant
la date de négociation. Les rendements quotidiens sont d'abord centrés et réduits titre par
titre, de sorte que la matrice a des uns sur sa diagonale. Les auteurs justifient cette durée en deux temps.
Une fenêtre beaucoup plus longue prendrait en compte un passé économiquement caduc. Une fenêtre
plus courte ne donnerait pas assez de points face aux 500 ou 1 000 lignes de la matrice.

**Deux. Vecteurs propres et portefeuilles propres.** Les valeurs propres sont classées par ordre
décroissant. Le portefeuille propre associé à la \(j\)-ième valeur investit dans le titre \(i\)
un montant proportionnel au coefficient du vecteur propre divisé par la volatilité du titre.
Les rendements de ces portefeuilles sont les facteurs.

**Trois. Nombre de facteurs, deux variantes.** Un nombre fixe, quinze, choisi parce qu'il est
proche du nombre de secteurs. Ou un nombre variable, celui qu'il faut pour que la somme des
valeurs propres retenues atteigne un pourcentage donné de la trace de la matrice, donc de la
variance totale. Le pourcentage de référence est 55 %, et 45 % et 65 % sont aussi testés. La
conclusion de l'article (p. 779-780) donne la fourchette observée : entre dix et trente facteurs
selon la date.

**Quatre. Régression sur soixante jours.** Le rendement de chaque titre est régressé sur les
rendements des facteurs, sur une fenêtre de 60 jours de bourse. Cette longueur est choisie
parce qu'elle correspond à peu près à un cycle de publication de résultats (p. 763). La même longueur est
utilisée pour tous les titres.

**Cinq. Résidu cumulé.** Les résidus de cette régression sont sommés dans le temps pour former
un processus \(X_k\), version discrète du processus d'Ornstein-Uhlenbeck à estimer.

**Six. Estimation par autorégression d'ordre un.** Une régression de \(X_{n+1}\) sur \(X_n\)
donne la vitesse de rappel, le niveau d'équilibre et la volatilité résiduelle.

**Sept. Filtre de vitesse.** Seuls les titres dont le retour à la moyenne est rapide sont
retenus, avec un seuil de \(\kappa > 252/30 = 8{,}4\). Cela correspond à un temps
caractéristique inférieur à la moitié de la fenêtre d'estimation, environ un mois et demi. Quand \(\kappa\) passe sous ce
seuil, le modèle est rejeté pour ce titre : aucune position n'est ouverte, et une position
ouverte est fermée (p. 771).

**Huit. Règle de négociation.** Achat à l'ouverture si le s-score descend sous -1,25, vente à
l'ouverture s'il dépasse +1,25, fermeture d'une position vendeuse sous +0,75, fermeture d'une
position acheteuse au-dessus de -0,50. Les positions sont tout ou rien, sans ajustement
continu, ce que les auteurs appellent « bang-bang » (p. 771). Entrer signifie acheter un dollar
du titre et vendre les montants correspondants des facteurs.

Deux paramètres de gestion complètent la règle. Le levier est de « 2 plus 2 », choisi par essai
sur 2002-2004 pour viser une volatilité annuelle proche de 10 %. Les stratégies fondées sur les
fonds réels sont couvertes secteur par secteur. Celles fondées sur les fonds synthétiques et
sur l'analyse en composantes principales sont couvertes globalement avec SPY, le fonds
indiciel qui suit le S&P 500. Le glissement retenu est de 0,05 % par transaction, soit 10 points de base
par aller-retour.

## Les équations qui comptent

**Le modèle de rendement.** Pour la variante à fonds sectoriels, équation (11), p. 768 :

\[ \frac{dS_i(t)}{S_i(t)} = \alpha_i\, dt + \beta_i \frac{dI(t)}{I(t)} + dX_i(t) \]

où \(S_i(t)\) est le prix du titre \(i\) ajusté des dividendes et \(I(t)\) le fonds sectoriel
qui lui est assigné. La composante idiosyncrasique du rendement est
\(d\tilde{X}_i(t) = \alpha_i\, dt + dX_i(t)\), où \(\alpha_i\, dt\) est le taux de rendement en
excès du titre par rapport à son secteur.

**Le processus d'Ornstein-Uhlenbeck**, équation (12), p. 768 :

\[ dX_i(t) = \kappa_i\left(m_i - X_i(t)\right) dt + \sigma_i\, dW_i(t), \qquad \kappa_i > 0 \]

Les quatre paramètres sont propres à chaque titre. \(\kappa_i\) est la vitesse de rappel,
\(m_i\) le niveau d'équilibre vers lequel le résidu revient, \(\sigma_i\) la volatilité
instantanée du bruit, et \(W_i\) un mouvement brownien. Les auteurs les supposent constants sur
la fenêtre de 60 jours.

La solution, équation (13), p. 769 :

\[ X_i(t_0 + \Delta t) = e^{-\kappa_i \Delta t} X_i(t_0) + \left(1 - e^{-\kappa_i \Delta t}\right) m_i
+ \sigma_i \int_{t_0}^{t_0+\Delta t} e^{-\kappa_i (t_0 + \Delta t - s)}\, dW_i(s) \]

Quand \(\Delta t\) tend vers l'infini, la loi d'équilibre est normale, équation (14), p. 769 :

\[ \mathbb{E}\{X_i(t)\} = m_i, \qquad \mathrm{Var}\{X_i(t)\} = \frac{\sigma_i^{2}}{2\kappa_i} \]

Le temps caractéristique de retour à la moyenne est \(\tau_i = 1/\kappa_i\).

**Le s-score**, équation (15), p. 769. En posant l'écart type d'équilibre

\[ \sigma_{eq,i} = \frac{\sigma_i}{\sqrt{2\kappa_i}} = \sigma_i \sqrt{\frac{\tau_i}{2}} \]

le s-score est la distance à l'équilibre exprimée en écarts types :

\[ s_i = \frac{X_i(t) - m_i}{\sigma_{eq,i}} \]

**Le s-score modifié**, équation (17), p. 770, qui réintroduit la dérive \(\alpha_i\) :

\[ s_{mod,i} = s_i - \frac{\alpha_i}{\kappa_i\, \sigma_{eq,i}} = s_i - \frac{\alpha_i \tau_i}{\sigma_{eq,i}} \]

L'espérance de rendement du résidu sur \(dt\) vaut alors
\(\kappa_i\left(\alpha_i/\kappa_i - \sigma_{eq,i} s_i\right) dt\). Vendre à découvert devient
plus difficile quand la dérive est positive, ce qui insère une composante de momentum dans le
signal.

**Les règles d'entrée et de sortie**, équation (16), p. 770, avec les valeurs calibrées données
juste en dessous :

\[ s_{bo} = s_{so} = 1{,}25, \qquad s_{bc} = 0{,}75, \qquad s_{sc} = 0{,}50 \]

**L'estimation, annexe A, p. 781-782.** La régression sur 60 jours donne
\(\alpha = \beta_0 \times 252\). Le résidu cumulé est \(X_k = \sum_{j=1}^{k}\epsilon_j\), pour
\(k = 1,\ldots,60\). L'autorégression \(X_{n+1} = a + b X_n + \zeta_{n+1}\) pour
\(n = 1,\ldots,59\) donne, par identification avec la solution (13) :

\[ \kappa = -\log(b) \times 252, \qquad m = \frac{a}{1-b}, \qquad
\sigma = \sqrt{\frac{\mathrm{Var}(\zeta)\, \cdot 2\kappa}{1 - b^{2}}}, \qquad
\sigma_{eq} = \sqrt{\frac{\mathrm{Var}(\zeta)}{1 - b^{2}}} \]

Le filtre \(\kappa > 252/30\) correspond exactement à \(0 < b < 0{,}9672\).

**Le piège de construction, à retenir avant toute réplication.** La régression force les
résidus à être de moyenne nulle, donc \(X_{60} = 0\) par construction. Les auteurs l'écrivent
et le qualifient d'artefact, dû au fait que les bêtas et les résidus sont estimés sur le même
échantillon. Le s-score effectivement calculé n'est donc pas \((X(t)-m)/\sigma_{eq}\) mais son
opposé sur \(m\) seul :

\[ s = -\frac{m}{\sigma_{eq}} = -\frac{a \sqrt{1-b^{2}}}{(1-b)\sqrt{\mathrm{Var}(\zeta)}} \]

Enfin, les auteurs centrent la moyenne en travers des titres, ce qui donne la formule
effectivement utilisée, équation (A2), p. 782 :

\[ s = -\frac{a\sqrt{1-b^{2}}}{(1-b)\sqrt{\mathrm{Var}(\zeta)}}
+ \left\langle \frac{a}{1-b} \right\rangle \sqrt{\frac{1-b^{2}}{\mathrm{Var}(\zeta)}} \]

où les crochets désignent la moyenne sur les différents titres. Une réplication qui calcule le
s-score depuis la définition théorique sans passer par (A2) n'obtiendra pas les mêmes signaux.

## Les résultats originaux

Tous les nombres de cette section sont **rapportés**, lus dans le fac-similé de l'article
publié cité en tête. Tous les ratios de Sharpe sont nets du glissement de 5 points de base par
transaction.

**Résumé de l'article (p. 761).** Ratio de Sharpe annuel moyen de 1,44 pour les stratégies par
analyse en composantes principales sur 1997-2007, mais de 0,9 seulement sur 2003-2007. Les
stratégies par fonds sectoriels rendent 1,1 sur 1997-2007, avec une dégradation comparable
depuis 2002. Avec l'information de volume, elles atteignent 1,51 sur 2003-2007.

**Quinze facteurs par analyse en composantes principales (table 6, p. 774).** Ratio de Sharpe
du portefeuille par année, de 1997 à 2002 : 1,4 ; 1,4 ; 0,2 ; 2,2 ; 2,6 ; 3,4. Puis de 2003 à
2007 : 0,9 ; 2,2 ; 1,2 ; 1,0 ; -0,7. Depuis l'origine : 1,44. Quatre années dépassent 2,0, et ce sont 2000, 2001, 2002 et 2004.

**Fonds synthétiques (table 4, p. 769).** Ratio de Sharpe du portefeuille, de 1996 à 2001 : 1,7 ; 3,6 ; 3,4 ; 0,8 ; 0,3 ; 2,9. Puis de
2002 à 2007 : 2,0 ; 0,1 ; 0,8 ; -1,3 ; -0,5 ; -0,5. Depuis l'origine : 1,1. Les trois dernières
années sont perdantes.

**Fonds sectoriels réels (table 5, p. 769).** Ratio de Sharpe du portefeuille : 2,7 en 2002,
0,8 en 2003, 1,6 en 2004, 0,1 en 2005, 0,7 en 2006 et -0,2 en 2007. Depuis l'origine : 0,9.

**Nombre variable de facteurs (table 8, p. 776), sur 2002-2007.** Ratios de Sharpe depuis
l'origine : 0,7 avec un seul portefeuille propre, 0,9 avec quinze, 0,6 à 45 % de variance
expliquée, 0,7 à 55 % et 0,4 à 65 %. Les auteurs concluent que 55 % est le meilleur des trois
seuils variables, et qu'il reste légèrement inférieur au choix fixe de quinze facteurs. Une
coupure à 75 % perd de l'argent de façon régulière.

**Signaux en temps de transaction, fonds réels (table 9, p. 776).** Ratio de Sharpe du
portefeuille : 0,9 en 2003, 3,1 en 2004, 1,6 en 2005, 1,5 en 2006 et 0,4 en 2007. Depuis 2003 :
1,51. C'est le meilleur résultat de l'article après 2002. La pondération revient à diviser le
rendement du jour par le volume échangé, donc à croire davantage un mouvement de contre-tendance
survenu sur faible volume.

**Ordres de grandeur des paramètres estimés (p. 771).** Dérive de l'ordre de 15 points de base,
temps de retour à la moyenne moyen de 7 jours, volatilité d'équilibre du résidu de l'ordre de
300 points de base. Le décalage moyen que la dérive induit sur le s-score vaut donc environ
\(0{,}15 \times 7 / 300 \approx 0{,}3\), ce que les auteurs jugent négligeable devant les
seuils de 1,25. Ils ne publient donc aucun rétrotest avec le s-score modifié.

**Août 2007 (section 7, p. 777-779).** Toutes les variantes subissent le même creux, suivi
d'une reprise partielle dans la deuxième semaine d'août. Les auteurs reproduisent le résultat
de Khandani et Lo (2007). Ils notent que le choc a été plus marqué dans la technologie et la
consommation discrétionnaire que dans la finance et l'immobilier, ce qui appuie l'explication
par le débouclage forcé des positions.

## Les critiques connues

**Aucune réfutation publiée de l'article lui-même n'a été trouvée au 2026-09-01.** Les trois
travaux ci-dessous portent sur l'estimateur, sur la performance hors de la fenêtre d'origine,
ou sur la classe de modèles ; aucun ne conteste les chiffres publiés.

**L'estimateur de la vitesse de rappel est biaisé.** Yeo et Papanicolaou (2017), « Risk control
of mean-reversion time in statistical arbitrage », Risk and Decision Analysis 6, p. 263-290,
manuscrit consulté le 2026-09-01 sur http://math.stanford.edu/~papanico/pubftp/RDA_manuscript.pdf.
Ils écrivent en note 16 que les moindres carrés, le maximum de vraisemblance et la méthode des
moments généralisés donnent tous un estimateur biaisé du paramètre de retour à la moyenne. Or
c'est ce paramètre qui pilote à la fois le filtre à 8,4 et le dénominateur du s-score.

**Et le résultat dépend fortement des paramètres.** Toujours Yeo et Papanicolaou, qui font
varier la fenêtre d'estimation entre 30 et 120 jours et le nombre de facteurs entre 5 et 20,
sur cinq régimes de 2005 à 2014. Prenons la configuration la plus proche de celle de l'article, 60 jours et 15 facteurs, avec
5 points de base de coût. Leur portefeuille tiré au hasard donne un ratio de Sharpe moyen de
0,03 sur les cinq régimes (leur table 6). Leur portefeuille contrôlé
par la vitesse de rappel donne 1,32 dans la même case (leur table 4). Le coût décide
également : à la même case, 1,42 sans coût (table 15), 1,32 à 5 points de base (table 4) et
0,01 à 10 points de base (table 14).

**Le modèle paramétrique est battu largement par des modèles appris.** Guijarro-Ordonez, Pelger
et Zanotti (2021), « Deep Learning Statistical Arbitrage », arXiv:2106.04028, texte consulté le
2026-09-01 sur https://arxiv.org/pdf/2106.04028. Ils prennent le processus d'Ornstein-Uhlenbeck
avec règle de seuil comme repère paramétrique, en citant l'article et son extension par Yeo et
Papanicolaou. Leur échantillon porte sur des actions américaines quotidiennes, avec négociation hors
échantillon de janvier 2002 à décembre 2016, et sans coûts de transaction dans cette table.
Avec quinze facteurs extraits par analyse en composantes principales, ce repère donne un ratio
de Sharpe annualisé de 0,62. Leur modèle à convolution et transformeur, sur les mêmes résidus,
donne 2,30 (leur table I). L'écart n'est pas une réfutation : leur fenêtre de signal vaut 30 jours et non
60, et leur univers n'est pas celui de l'article.

**La loi normale du processus est en conflit avec les faits stylisés.** Krauss (2017),
« Statistical Arbitrage Pairs Trading Strategies: Review and Outlook », Journal of Economic
Surveys 31(2), p. 513-545, version de travail consultée le 2026-09-01 (FAU IWF Discussion Paper
09/2015, https://www.iwf.rw.fau.de/files/2016/03/09-2015.pdf). Il attribue cette critique à
Cummins et Bucca (2012) et l'applique à toute la famille des modèles en temps continu, dont
celui de l'article. Il ajoute que la simplicité analytique compense largement ce défaut. Sa
table 1 recense l'article dans la catégorie « autres, analyse en composantes principales » et
laisse la colonne du rendement annuel vide, faute d'un chiffre comparable publié.

**Les auteurs constatent eux-mêmes la dégradation.** Le résumé de l'article oppose 1,44 sur
1997-2007 à 0,9 sur 2003-2007 pour la même stratégie. La table 4 montre trois années perdantes
d'affilée, 2005, 2006 et 2007, pour la variante à fonds synthétiques. L'article se termine en
demandant que d'autres travaux, « particularly after 2007 », vérifient la conjecture sur le
nombre de facteurs.

## Les problèmes de réplication connus

**Le s-score n'est pas celui de sa définition.** C'est le point le plus important, et il est
écrit dans l'article même, annexe A. Comme \(X_{60} = 0\) par construction, le s-score se
réduit à \(-m/\sigma_{eq}\), puis à la forme centrée en travers des titres de l'équation (A2).
Une réplication fidèle doit implémenter (A2), pas (15).

**Les seuils sont calibrés sur une fenêtre incluse dans la période rapportée, et cette fenêtre
est écrite deux fois différemment.** Page 770, les auteurs écrivent avoir choisi les seuils en
simulant de 2000 à 2004. Deux phrases plus loin, ils écrivent que fermer à 0,75 fait
légèrement mieux qu'à 0,50 « in the training period of 2000-2002 ». Les deux fenêtres sont incluses dans les
périodes 1997-2007 et 2002-2007 dont les ratios de Sharpe sont publiés. Le levier de « 2 plus
2 » est lui aussi choisi par rétrotest sur 2002-2004.

**La capitalisation doit être connue à la date passée.** Le seuil d'un milliard de dollars
s'applique à la date de négociation. Une réplication qui utilise la capitalisation courante
réintroduit précisément le biais du survivant que les auteurs disent éviter.

**Les fonds synthétiques ne sont pas décrits assez précisément pour être reconstruits.** Ce
sont des indices sectoriels pondérés par la capitalisation, formés avec les titres de l'univers
présents à la date du signal. L'affectation d'un titre à l'un des quinze secteurs n'est pas
publiée. La table 3 ne donne qu'une photographie au 1er janvier 2007.

**La matrice de corrélation n'est pas de rang plein.** Avec 1 417 titres et 252 jours, il y a
beaucoup plus de coefficients à estimer que de points. Les auteurs l'écrivent p. 764, sans
employer le mot de singularité. Ils s'en accommodent en ne gardant que le haut du spectre. Une réplication doit décider quoi faire des valeurs
propres nulles, et le choix n'est pas dans l'article.

**Un renvoi de l'article ne mène pas où il annonce.** Page 769, la section 4 renvoie à la table
5 pour les « typical descriptive statistics for signal estimation ». Or la table 5 du
fac-similé consulté donne des ratios de Sharpe par secteur pour les fonds sectoriels réels. Le
tableau de statistiques descriptives des paramètres estimés est absent du texte publié. Une
réplication n'a donc pas de valeur de référence pour \(\kappa\), \(m\) et \(\sigma_{eq}\), et
doit s'appuyer sur les seuls ordres de grandeur donnés en prose p. 771.

**La couverture n'est pas la même selon la variante.** Les stratégies à fonds réels sont
neutres au bêta secteur par secteur. Celles à fonds synthétiques et à composantes principales
sont neutres au bêta au niveau du portefeuille entier, avec SPY. Comparer les tables sans tenir
compte de cette différence conduit à des conclusions fausses, et les auteurs le signalent
p. 779-780.

**Le temps de transaction n'est décrit qu'en une phrase.** Introduction, p. 763, reprise en
section 6, p. 777 : estimer les signaux en temps de transaction équivaut, pour des données de
clôture, à multiplier les rendements quotidiens par un facteur inversement proportionnel au
volume de la veille. La
normalisation exacte de ce facteur n'est pas donnée, alors que c'est la variante qui obtient le
meilleur résultat après 2002.

## Les biais possibles

**Calibration en échantillon.** Deux paramètres au moins, les seuils du s-score et le levier,
sont choisis sur des fenêtres incluses dans les périodes dont la performance est publiée. Ce
n'est pas dissimulé, mais cela interdit de lire 1,44 comme un résultat hors échantillon au sens
strict. L'article affirme pourtant p. 763 que la simulation est « always out-of-sample », du
fait de la fenêtre glissante de 60 jours. Les deux énoncés portent sur deux choses différentes,
l'estimation d'une part, le choix des règles d'autre part, et seule la première est hors
échantillon.

**Aucun coût de financement ni d'emprunt de titres.** L'équation de compte de résultat, p. 771,
suppose explicitement qu'il n'y a pas d'écart entre taux prêteur et taux emprunteur. Pour une
stratégie à levier 2 plus 2 tenue dix ans, cette hypothèse n'est pas neutre. Le coût de
l'emprunt de titres, lui, n'apparaît nulle part.

**Exécution au cours de clôture.** Toutes les transactions sont supposées faites au cours de
clôture du jour du signal, avec 5 points de base de glissement forfaitaire. La stratégie étant
tout ou rien, elle concentre ses ordres au moment le plus encombré de la séance.

**Biais de taille.** Le seuil d'un milliard de dollars limite l'univers aux grandes
capitalisations. Cela protège du biais du survivant et du coût d'emprunt, mais rend le résultat
non transposable aux petites capitalisations, où le retour à la moyenne serait sans doute plus
fort et le coût aussi.

**Précision des ratios de Sharpe annuels.** **Modélisé.** Sous l'hypothèse de rendements
indépendants et de même loi, l'erreur type du ratio de Sharpe annualisé estimé sur \(T\) années
vaut approximativement \(\sqrt{(1 + SR^{2}/2)/T}\), résultat établi par Lo (2002). Pour une
seule année et un ratio vrai de 1,4, cette erreur type vaut environ 1,4. Les ratios annuels des
tables 4 à 10 doivent donc être lus comme des indications de sens, jamais comme des valeurs
mesurées. Seules les lignes « since inception », qui portent sur six à douze ans, supportent
une comparaison.

**Le nombre de facteurs est un paramètre libre choisi après coup.** Quinze est retenu parce
qu'il est proche du nombre de secteurs, et la conclusion (p. 779) reconnaît que le nombre
adéquat varie entre dix et trente selon la date. Les tables 6, 7 et 8 publient les résultats
pour cinq variantes de ce choix, ce qui est honnête, mais offre autant de degrés de liberté à
qui voudrait retenir la meilleure.

## Nos décisions d'implémentation

non commencé au 2026-09-01

## Nos écarts avec l'article

non commencé au 2026-09-01

## Nos résultats

non commencé au 2026-09-01

## Notre contrôle de robustesse

non commencé au 2026-09-01

## Références

- Avellaneda, M. et Lee, J.-H. (2010), « Statistical arbitrage in the US equities market »,
  Quantitative Finance 10(7), p. 761-782. Fac-similé consulté :
  https://traders.studentorg.berkeley.edu/papers/Statistical%20arbitrage%20in%20the%20US%20equities%20market.pdf
- Yeo, J. et Papanicolaou, G. (2017), « Risk control of mean-reversion time in statistical
  arbitrage », Risk and Decision Analysis 6, p. 263-290. Manuscrit consulté :
  http://math.stanford.edu/~papanico/pubftp/RDA_manuscript.pdf
- Guijarro-Ordonez, J., Pelger, M. et Zanotti, G. (2021), « Deep Learning Statistical
  Arbitrage », arXiv:2106.04028. Texte consulté : https://arxiv.org/pdf/2106.04028
- Krauss, C. (2017), « Statistical Arbitrage Pairs Trading Strategies: Review and Outlook »,
  Journal of Economic Surveys 31(2), p. 513-545. Version de travail consultée, FAU IWF
  Discussion Paper 09/2015 : https://www.iwf.rw.fau.de/files/2016/03/09-2015.pdf
- Lo, A. W. (2002), « The Statistics of Sharpe Ratios », Financial Analysts Journal 58(4),
  p. 36-52. Notice consultée :
  https://rpc.cfainstitute.org/research/financial-analysts-journal/2002/the-statistics-of-sharpe-ratios
- Khandani, A. et Lo, A. W. (2007), « What Happened to the Quants in August 2007? », document
  de travail SSRN. Cité par l'article, non consulté.
- Jolliffe, I. T. (2002), « Principal Component Analysis », Springer. Cité par l'article, non
  consulté.
- Laloux, L., Cizeau, P., Potters, M. et Bouchaud, J.-P. (2000), « Random matrix theory and
  financial correlations », International Journal of Theoretical and Applied Finance 3(3),
  p. 391-397. Cité par l'article, non consulté.
- Cummins, M. et Bucca, A. (2012), « Quantitative spread trading on crude oil and refined
  products markets », Quantitative Finance 12(12), p. 1857-1875. Cité par Krauss (2017), non
  consulté.
- Gatev, E., Goetzmann, W. N. et Rouwenhorst, K. G. (2006), « Pairs Trading: Performance of a
  Relative-Value Arbitrage Rule », The Review of Financial Studies 19(3), p. 797-827. Fiche
  interne : `gatev_goetzmann_rouwenhorst_2006.md`

# Optimal Execution of Portfolio Transactions

| | |
|---|---|
| **Auteurs** | Robert Almgren et Neil Chriss ; complément de Jim Gatheral (2010) |
| **Année** | 2001 pour l'article publié, document de travail daté de décembre 2000 ; 2010 pour Gatheral |
| **Revue ou source** | Journal of Risk, vol. 3, n° 2, p. 5-39 ; Gatheral, Quantitative Finance, vol. 10, n° 7, p. 749-759 |
| **Lien** | [document de travail, décembre 2000](https://www.smallake.kr/wp-content/uploads/2016/03/optliq.pdf) ; [Gatheral sur SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1292353) |
| **Statut de réplication** | non commencé |

Deux précisions d'accès, au 2026-09-01. La version d'Almgren et Chriss lue est le
document de travail de décembre 2000, quarante-deux pages, non la version du
Journal of Risk qui est derrière un péage. La pagination publiée fait
d'ailleurs l'objet de sources contradictoires : les notices bibliographiques
courantes donnent p. 5-39, alors que Gatheral cite lui-même « Journal of Risk 3
5-40 (2001) » dans sa propre bibliographie. La contradiction est signalée et non
tranchée.

**L'article de Gatheral (2010) n'a pas été consulté ; la fiche repose sur ses
propres exposés du même travail.** SSRN et Taylor & Francis renvoient tous deux
une erreur 403 depuis cet environnement. Deux présentations de Gatheral ont été
lues intégralement à la place. Elles portent les mêmes énoncés, les mêmes
démonstrations et les mêmes exemples numériques. La première est « No-Dynamic-Arbitrage and Market Impact », École polytechnique, 5 janvier 2009,
quarante-sept planches. La seconde est « Optimal order execution », Scuola
Normale Superiore de Pise, 13 juillet 2012, quatre-vingts planches.

## La question de recherche

À quelle vitesse liquider une position, quand se dépêcher coûte cher et attendre
est risqué ? Un ordre trop gros pour le carnet fait bouger le prix contre son
émetteur, donc l'étaler réduit le coût. Mais l'étaler expose la position restante
à la volatilité du titre, donc au risque de recevoir bien moins que le prix
initial.

La tension est double et les deux termes sont vrais. Bertsimas et Lo (1998)
définissent la meilleure exécution comme celle qui minimise le coût espéré, ce
qui donne une trajectoire linéaire quelle que soit la liquidité du titre. Or un
courtier confronté à un petit ordre l'exécute immédiatement, ce qu'aucun modèle
sans aversion au risque ne peut expliquer (p. 23 du document de travail).

## L'intuition économique

Le coût d'exécution existe parce que la liquidité est un service rare, et
quelqu'un doit être payé pour le rendre. Un teneur de marché qui accepte votre
bloc porte l'inventaire jusqu'à ce qu'il trouve la contrepartie, et exige d'être
rémunéré pour le risque de détention. Ce n'est ni un biais de comportement ni une
inefficience : c'est un prix d'équilibre pour un service.

Les auteurs séparent ce prix en deux effets distincts, et la distinction commande
tout le reste. L'**impact temporaire** vient de ce qu'on épuise les offres
successives du carnet pendant qu'on négocie, et la liquidité revient ensuite.
L'**impact permanent** est le déplacement du prix d'équilibre lui-même, parce que
le marché infère de votre volume une information et révise sa valorisation
(p. 8). Le premier ne touche que vos propres exécutions, le second frappe tout ce
qui reste à vendre.

Ce mécanisme prédit sa propre disparition, et c'est ce qui le rend testable.
L'impact temporaire s'efface si le carnet se reconstitue instantanément, donc il
décroît quand les teneurs de marché sont nombreux et rapides. L'impact permanent
s'efface si votre ordre ne porte aucune information, donc il devrait être plus
faible pour un rééquilibrage annoncé que pour une vente discrétionnaire.

L'argument d'inventaire donne aussi la FORME de l'impact, et c'est ce qui
opposera Gatheral à Almgren et Chriss. Le teneur de marché exige un rendement
proportionnel au risque de son inventaire, ce risque vaut \(\sigma\sqrt{T}\) avec
\(T\) la durée de détention, et cette durée croît avec la taille de la position.
Le rendement exigé est donc proportionnel à \(\sqrt{n}\), pas à \(n\) (Gatheral,
planches de janvier 2009, « Why \(\sqrt{n}\) ? »). Almgren et Chriss supposent un
impact linéaire ; l'argument d'inventaire dit racine carrée.

## Les données

Aucune. C'est un article de modélisation en forme fermée, et son seul contenu
empirique est un jeu de paramètres illustratif, entièrement énoncé dans sa table 1
(p. 25 du document de travail).

| Paramètre | Valeur | Unité |
|---|---|---|
| Prix initial \(S_0\) | 50 | $/action |
| Position initiale \(X\) | 1 000 000 | actions |
| Durée de liquidation \(T\) | 5 | jours |
| Nombre de périodes \(N\) | 5 | |
| Volatilité annuelle 30 %, soit \(\sigma\) | 0,95 | ($/action)/jour\(^{1/2}\) |
| Croissance annuelle 10 %, soit \(\alpha\) | 0,02 | ($/action)/jour |
| Écart acheteur-vendeur de 1/8, soit \(\epsilon\) | 0,0625 | $/action |
| Impact permanent \(\gamma\) | \(2,5 \times 10^{-7}\) | $/action\(^2\) |
| Impact temporaire \(\eta\) | \(2,5 \times 10^{-6}\) | ($/action)/(action/jour) |
| Aversion au risque \(\lambda_u\) | \(10^{-6}\) | 1/$ |
| Quantile de VaR à 95 %, \(\lambda_v\) | 1,645 | |

Une ligne de cette table se lit de travers si on la prend au pied de la lettre.
Le libellé « Bid-ask spread = 1/8 » annonce un écart de 1/8, mais \(\epsilon\)
vaut 1/16, soit la MOITIÉ de l'écart, parce que les auteurs prennent pour coût
fixe la demi-fourchette (p. 24). Une réplication qui poserait
\(\epsilon = 0{,}125\) doublerait le terme fixe du coût.

Les deux paramètres d'impact ne sont pas estimés, ils sont posés par règle
empirique et leur statut est celui d'un **précepte**. Pour \(\eta\), les auteurs
supposent qu'échanger un pour cent du volume quotidien coûte un écart
acheteur-vendeur, d'où \(\eta = (1/8)/(0{,}01 \times 5\times 10^6)\). Pour
\(\gamma\), ils supposent que vendre dix pour cent du volume quotidien déplace le
prix d'un écart, d'où \(\gamma = (1/8)/(0{,}1 \times 5 \times 10^6)\) (p. 24).

## L'univers

Un titre unique dans le corps de l'article, avec un volume médian quotidien de
cinq millions d'actions. L'annexe A étend le résultat à un portefeuille de
plusieurs titres et produit là aussi des trajectoires en forme fermée, la
corrélation entre titres pesant alors fortement sur le comportement optimal
(p. 6).

Chez Gatheral, l'univers de validation empirique est différent, et il est réel.
Ce sont les métaordres propriétaires de Capital Fund Management sur les marchés
à terme, de juin 2007 à décembre 2010, près de 500 000 transactions (rapporté,
planches de juillet 2012). Ils ont été publiés par Tóth et autres (2011),
*Physical Review X*. Ces données ne sont pas accessibles.

## La méthodologie

Le problème est discret et statique. On divise \([0, T]\) en \(N\) intervalles de
longueur \(\tau = T/N\), et l'on note \(x_k\) le nombre d'actions encore détenues
à la date \(t_k = k\tau\), avec \(x_0 = X\) et \(x_N = 0\). La quantité vendue
dans l'intervalle \(k\) s'écrit \(n_k = x_{k-1} - x_k\).

La stratégie recherchée est **statique** : la règle qui fixe \(n_k\) ne dépend que
de l'information disponible en \(t_0\). Les auteurs démontrent ensuite que sous
leur dynamique de prix, la stratégie optimale l'est aussi parmi les stratégies
dynamiques, celles qui réagissent au prix observé (note 10, p. 13).

La construction se fait en trois temps. On écrit le coût espéré \(E(x)\) et sa
variance \(V(x)\) comme fonctions de la trajectoire. On construit la frontière
efficiente en résolvant \(\min_x E(x)\) sous contrainte \(V(x) \le V_*\), ce que
le multiplicateur de Lagrange \(\lambda\) transforme en programme sans contrainte.
On annule enfin les dérivées partielles, ce qui donne une équation aux différences
linéaire dont la solution s'écrit avec des sinus hyperboliques.

## Les équations qui comptent

Le prix de marché suit une marche aléatoire arithmétique dont la dérive est
l'impact permanent \(g\) de notre propre volume :

\[ S_k = S_{k-1} + \sigma \tau^{1/2} \xi_k - \tau\, g\!\left(\frac{n_k}{\tau}\right) \]

Le prix effectivement reçu s'en écarte de l'impact temporaire \(h\), qui ne se
propage PAS au prix de marché suivant :

\[ \tilde{S}_k = S_{k-1} - h\!\left(\frac{n_k}{\tau}\right) \]

Le coût de la transaction est le manque à gagner par rapport à la valeur
comptable initiale, ce que Perold (1988) appelle *implementation shortfall*. Son
espérance et sa variance valent, équations (4) et (5) p. 10 :

\[ E(x) = \sum_{k=1}^{N} \tau\, x_k\, g\!\left(\frac{n_k}{\tau}\right) + \sum_{k=1}^{N} n_k\, h\!\left(\frac{n_k}{\tau}\right), \qquad V(x) = \sigma^2 \sum_{k=1}^{N} \tau\, x_k^2 \]

Le premier terme de \(E\) frappe la position ENCORE DÉTENUE \(x_k\), le second
seulement la quantité vendue \(n_k\). C'est toute la différence entre permanent
et temporaire, et elle se lit dans les indices.

Avec des fonctions d'impact linéaires, équations (6) et (7) p. 10-11 :

\[ g(v) = \gamma v, \qquad h\!\left(\frac{n_k}{\tau}\right) = \epsilon\, \mathrm{sgn}(n_k) + \frac{\eta}{\tau}\, n_k \]

le coût espéré se simplifie en une forme quadratique, équation (8) p. 11 :

\[ E(x) = \tfrac{1}{2}\gamma X^2 + \epsilon \sum_{k=1}^{N} |n_k| + \frac{\tilde{\eta}}{\tau} \sum_{k=1}^{N} n_k^2, \qquad \tilde{\eta} = \eta - \tfrac{1}{2}\gamma\tau \]

### La fonction objectif

\[ \boxed{\;\min_{x}\; U(x) = E(x) + \lambda\, V(x) = \tfrac{1}{2}\gamma X^2 + \epsilon \sum_{k=1}^{N} |n_k| + \frac{\tilde{\eta}}{\tau} \sum_{k=1}^{N} n_k^2 + \lambda \sigma^2 \sum_{k=1}^{N} \tau\, x_k^2 \;} \]

Le paramètre \(\lambda\) est le taux auquel on pénalise la variance du coût
contre le coût lui-même, et il vaut la courbure d'une fonction d'utilité lisse
(p. 13). En faisant varier \(\lambda\) de zéro à l'infini, la solution balaie
toute la frontière efficiente.

**Deux des quatre termes ne dépendent pas de la trajectoire.** Pour un programme
de vente pure, tous les \(n_k\) ont le même signe, donc \(\sum |n_k| = |X|\), et
\(\tfrac{1}{2}\gamma X^2\) est fixé par la seule position de départ. Il reste
\(\tilde{\eta}\) et \(\lambda\sigma^2\). Or \(\tilde{\eta} = \eta - \gamma\tau/2\)
tend vers \(\eta\) quand \(\tau \to 0\). **Dans la limite continue, l'impact
permanent disparaît entièrement du problème d'optimisation** : il coûte, mais il
ne change pas d'un iota le chemin optimal. Les auteurs le disent d'un mot pour
le terme \(\tfrac{1}{2}\gamma X^2\), « this parameter gives a fixed cost
independent of path » (p. 24). Ce qu'ils n'écrivent pas, et qui se déduit de
leurs propres équations, c'est que la dépendance résiduelle en \(\gamma\) passe
tout entière par \(\tilde{\eta}\) et s'évanouit avec le pas de temps.

### La solution

L'annulation des dérivées donne l'équation aux différences (16), p. 14 :

\[ \frac{1}{\tau^2}\left(x_{j-1} - 2 x_j + x_{j+1}\right) = \tilde{\kappa}^2\, x_j, \qquad \tilde{\kappa}^2 = \frac{\lambda\sigma^2}{\tilde{\eta}} = \frac{\lambda \sigma^2}{\eta\left(1 - \frac{\gamma\tau}{2\eta}\right)} \]

où \(\kappa\) résout \(\dfrac{2}{\tau^2}\left(\cosh(\kappa\tau) - 1\right) = \tilde{\kappa}^2\). La trajectoire optimale, équation (17), et la liste des lots, équation (18) :

\[ x_j = \frac{\sinh\!\big(\kappa (T - t_j)\big)}{\sinh(\kappa T)}\, X, \qquad n_j = \frac{2\sinh\!\left(\tfrac{1}{2}\kappa\tau\right)}{\sinh(\kappa T)}\, \cosh\!\Big(\kappa\big(T - t_{j-\frac{1}{2}}\big)\Big)\, X \]

Pour un pas court, \(\kappa \simeq \sqrt{\lambda\sigma^2/\eta}\) (équation 19,
p. 15). L'inverse \(\theta = 1/\kappa\) est la **demi-vie** de la transaction, le
temps au bout duquel la position est divisée par \(e\). Elle ne dépend PAS de la
durée imposée \(T\) : un vendeur averse au risque liquide sur l'échelle de temps
\(\theta\) même sans contrainte de temps (p. 15).

Ce ratio \(\kappa T = T/\theta\) dit ce qui contraint la transaction. Si
\(T \gg \theta\), l'essentiel se vend bien avant l'échéance et la trajectoire
ressemble à la vente immédiate. Si \(T \ll \theta\), les coûts temporaires
dominent et la trajectoire tend vers la droite à taux constant.

## Les résultats originaux

**La frontière efficiente est lisse et convexe, et elle est différentiable en son
minimum.** Ce minimum est la stratégie de Bertsimas et Lo, la vente à taux
constant, celle qui minimise le coût espéré sans regarder la variance. La
différentiabilité au minimum a une conséquence pratique. En s'écartant un peu de
la stratégie naïve, on obtient une réduction de variance du PREMIER ordre contre
une hausse de coût du SECOND ordre (p. 6). Les auteurs en tirent qu'il
n'est jamais rationnel d'échanger la stratégie strictement neutre au risque
(p. 22-23).

**Deux paniers de tailles différentes du même titre se liquident exactement de la
même façon**, sur la même échelle de temps, à \(\lambda\) fixé. C'est contraire à
l'intuition et les auteurs le disent : c'est une conséquence de l'impact linéaire,
qui fait croître variance et coût d'impact tous deux quadratiquement avec la
taille (p. 16). Ils recommandent de changer \(\eta\) selon la taille du problème,
en reconnaissant que le modèle n'est qu'approché.

**Sur le cas type**, \(\kappa \approx 0{,}6\) par jour et \(\kappa T \approx 3\),
un régime intermédiaire entre les deux extrêmes (p. 24). La position non
négociée pendant cinq jours aurait un écart-type de \(\sigma\sqrt{T} = 2{,}12\)
$/action, soit 2,12 M$ sur le million d'actions.

**Avec une dérive \(\alpha\)**, le problème acquiert un point fixe
\(\bar{x} = \alpha/(2\lambda\sigma^2)\), la position optimale d'un problème de
portefeuille sans horizon (équation 25, p. 26). Les trajectoires convergent vers
\(\bar{x}\) au lieu de zéro tant que la contrainte de liquidation ne mord pas.

### Ce que la racine carrée de Gatheral change

Gatheral remplace la séparation permanent/temporaire par un unique noyau de
décroissance, la fonction qui dit quelle part de l'impact d'un lot survit après
un délai donné :

\[ S_t = S_0 + \int_0^t f(\dot{x}_s)\, G(t-s)\, ds + \int_0^t \sigma\, dZ_s, \qquad C[\Pi] = \int_0^T \dot{x}_t\, dt \int_0^t f(\dot{x}_s)\, G(t-s)\, ds \]

Almgren et Chriss deviennent un cas particulier : leur composante temporaire
correspond à \(G(t-s) = \delta(t-s)\), une décroissance instantanée, avec
\(f(v) = \eta\sigma v^{\beta}\) et \(\beta = 0{,}6\) selon l'estimation d'Almgren
(2005). Leur composante permanente correspond à \(G \equiv 1\).

Le principe imposé est celui de **non-manipulation** : un aller-retour, un
programme dont le volume net est nul, ne peut pas avoir un coût espéré négatif.
Quatre conséquences en découlent, et elles concernent directement le modèle
d'Almgren et Chriss.

**Un.** Si l'impact est permanent, la non-manipulation force \(f(v) = -f(-v)\),
puis, en développant en puissances du taux de résilience, force \(f\) à être
LINÉAIRE. Le \(\gamma v\) d'Almgren et Chriss n'est donc pas un choix de commodité
mathématique : c'est le seul impact permanent admissible. Huberman et Stanzl
(2004) obtiennent la même conclusion par la voie du quasi-arbitrage.

**Deux.** Si l'impact décroît exponentiellement, la manipulation est possible dès
que \(f\) n'est pas linéaire. Gatheral donne un contre-exemple explicite avec
\(f(v) = \sqrt{v}\), \(v_1 = 0{,}2\), \(v_2 = 1\), \(\rho = 1\) et \(T = 1\) : le
coût de l'aller-retour vaut \(-0{,}001705\), donc un profit. **Ce nombre a été
recalculé ici et retrouvé à \(-0{,}0017050\)** (mesuré, 2026-09-01, à partir des
formules (16) des planches de janvier 2009). La stratégie consiste à accumuler
lentement, en fractionnant au maximum, puis à liquider vite.

**Trois.** Avec une décroissance en loi de puissance \(G(\tau) = \tau^{-\gamma}\)
et un impact en loi de puissance \(f(v) \propto v^{\delta}\), la
non-manipulation impose

\[ \gamma + \delta \ge 1 \]

Empiriquement, \(\delta \approx 0{,}6\) selon Almgren et \(\gamma \approx 0{,}4\)
selon Bouchaud, donc \(\gamma + \delta \approx 1\) : le marché se tient EXACTEMENT
sur la frontière de non-arbitrage (planches de janvier 2009).

**Quatre, et c'est ce qui touche la fonction objectif.** Le coût par action d'une
exécution à taux constant sur une durée \(T\) vaut

\[ \frac{C}{X} \propto \left(\frac{n}{V}\right)^{\delta} T^{\,1-\gamma-\delta} \]

Si \(\gamma + \delta = 1\), **l'exposant de \(T\) s'annule et le coût espéré ne
dépend plus de la durée**. Avec \(\gamma = \delta = 1/2\) on retrouve la formule
en racine carrée que les logiciels de courtage emploient depuis les années 1990,
\(\Delta P = \text{coût d'écart} + \alpha\sigma\sqrt{Q/V}\).

La portée pour Almgren et Chriss est directe. Leur arbitrage repose sur le fait
que ralentir DIMINUE le coût et AUGMENTE le risque. Si le coût espéré d'une
exécution à taux constant ne dépend plus de la durée, la moitié « coût » de
l'arbitrage disparaît, et avec elle la raison d'accepter du risque de marché.
Pire, sous le processus en racine carrée pur, aucune stratégie optimale
N'EXISTE : la concavité de \(f\) permet de faire tendre le coût vers zéro en
multipliant les tranches. Il faut rendre \(f\) convexe pour les gros taux pour
qu'un optimum revienne. Cet optimum consiste alors à négocier par bouffées
séparées de silences. La vente à taux constant n'est donc jamais optimale
(planches de juillet 2012).

L'exemple chiffré de Gatheral donne l'ordre de grandeur du gain. Il s'agit de
vendre 540 000 actions d'IBM en une séance, sur un titre de volatilité
quotidienne 2 % et de volume quotidien 6 millions. Les ordres enfants durent
quinze minutes, de 09:45 à 15:45, et la part de volume est plafonnée à 25 %. Le
coût d'une exécution à taux constant vaut \(0{,}02 \times \sqrt{540/6000} =
60{,}0\) points de base, **recalculé et retrouvé ici** (mesuré, 2026-09-01).
Une stratégie à deux tranches coûte 49,6 points de base, soit 17 % de moins.
Une stratégie quasi optimale à sept tranches coûte 40,8 points de base, soit 32
% de moins (rapporté, planches de juillet 2012, table 1).

## Les critiques connues

**Huberman et Stanzl (2004)**, *Price Manipulation and Quasi-Arbitrage*,
Econometrica, vol. 72, n° 4, p. 1247-1275. Quand l'impact est permanent et
indépendant du temps, seules des fonctions d'impact linéaires excluent le
quasi-arbitrage et supportent des prix viables. Quand il existe aussi un impact
temporaire, seul le permanent doit être linéaire, le temporaire pouvant prendre
une forme plus générale. Le résumé a été consulté, l'article non.

**Almgren (2005)**, *Equity market impact*, Risk, juillet 2005, p. 57-62. Estime
l'exposant de l'impact temporaire à \(\beta \approx 0{,}6\), donc concave, alors
que le modèle de 2001 le suppose linéaire. Cité par Gatheral, non consulté
directement.

**Gatheral (2010)**, dont les quatre conséquences sont détaillées plus haut.

**Lorenz et Almgren (2011)**, *Mean-Variance Optimal Adaptive Execution*, Applied
Mathematical Finance, vol. 18, n° 5, p. 395-422. Leur résumé dit qu'une
stratégie adaptative améliore strictement la stratégie statique optimale au sens
moyenne-variance. Il ajoute que la règle est « agressive quand on est dans la
monnaie ». On accélère quand le prix évolue en sa faveur, en dépensant une part
du gain pour réduire le risque. La lecture usuelle en tire l'incohérence dynamique de la
variance du coût, c'est-à-dire qu'une trajectoire optimale en \(t_0\) cesse de
l'être en cours de route ; cette formulation est une INTERPRÉTATION, elle ne
figure pas telle quelle dans le résumé consulté. Résumé consulté, article non
consulté.

**Obizhaeva et Wang**, cités par Gatheral, modélisent la résilience du carnet
d'ordres avec \(G(t-s) = e^{-\rho(t-s)}\) et \(f(v) \propto v\). Sous ce noyau, la
stratégie optimale n'est pas continue : un bloc à l'ouverture, un bloc à la
fermeture, et un taux constant \(\rho\) entre les deux. Rien à voir avec la
sinusoïde hyperbolique d'Almgren et Chriss.

**Alfonsi, Schied et Slynko (2012)** ajoutent une irrégularité que la
non-manipulation classique ne capte pas. Ils l'appellent *manipulation
déclenchée par la transaction* : le coût d'un programme de vente peut baisser
si l'on y insère des achats. Leur théorème, tel que rapporté par Gatheral en
juillet 2012, donne la condition qui l'exclut. Si le noyau \(G\) est convexe et
d'intégrale finie près de zéro, la stratégie optimale existe, est unique et est
monotone. Si \(G\) n'est pas convexe au voisinage de zéro, la manipulation
déclenchée apparaît.

## Les problèmes de réplication connus

Il n'y a pas de données à retrouver, donc pas de problème de réplication au sens
habituel. Répliquer, ici, c'est refaire l'arithmétique de la table 1 et redessiner
les figures 1 et 2. Le jeu de paramètres est entièrement publié, ce qui rend la
vérification décidable.

**Une incohérence a été trouvée dans le document de travail de décembre 2000.** La
table 1, p. 25, annonce « Static holdings 11,000 shares » pour
\(\lambda_u = 10^{-6}\). Le texte de la section 4.1, p. 26, écrit au contraire
« the parameters of Section 3.4 give approximately x̄ = 1,100 shares, or 0.11% of
our initial portfolio ». Or la formule (25) donne

\[ \bar{x} = \frac{\alpha}{2\lambda\sigma^2} = \frac{0{,}02}{2 \times 10^{-6} \times 0{,}95^2} = 11\,080 \text{ actions} \]

soit 1,11 % du portefeuille initial d'un million d'actions. **La table est juste
et le texte est faux d'un facteur dix.** Calcul **mesuré** le 2026-09-01 sur le
document de travail de décembre 2000. La version du Journal of Risk n'a pas été
vérifiée et a pu corriger la coquille.

**Quatre autres nombres du cas type ont été recalculés et concordent** (mesuré,
2026-09-01). L'approximation \(\sqrt{\lambda\sigma^2/\eta}\) vaut 0,6008, le
\(\tilde{\kappa}\) corrigé vaut 0,6164 et le \(\kappa\) exact de l'équation
implicite vaut 0,6071. Les trois sont compatibles avec le « \(\kappa \approx
0{,}6\) par jour, \(\kappa T \approx 3\) » de l'article. Enfin
\(\sigma\sqrt{T}\) vaut 2,124 $/action contre les 2,12 imprimés.

Du côté de Gatheral, le point dur est ailleurs : **l'article publié n'est pas
accessible**. Les deux jeux de planches consultés portent les énoncés et les
exemples, mais pas nécessairement toutes les hypothèses techniques des
démonstrations. Toute réplication devra obtenir la version Quantitative Finance
avant de traiter les lemmes comme établis.

## Les biais possibles

**La marche aléatoire arithmétique sans dérive.** Les auteurs l'assument pour des
horizons courts, où la différence avec un mouvement géométrique est négligeable
(note 8, p. 8). Le cas type porte pourtant sur cinq jours, ce qui est déjà le
haut de la fourchette.

**Les paramètres d'impact sont posés, pas estimés.** \(\eta\) et \(\gamma\)
viennent de deux règles empiriques déclarées comme telles dans l'article. Leur
statut est celui d'un précepte, et un projet de réplication qui les calibre sur
des données réelles ne réplique plus le même objet.

**L'impact temporaire linéaire est contredit empiriquement.** Almgren (2005)
estime \(\beta \approx 0{,}6\). L'écart n'est pas cosmétique : c'est lui qui
supprime l'existence même d'un optimum sous décroissance en loi de puissance.

**Le risque est mesuré par la variance du coût, et une stratégie révisable fait
strictement mieux.** C'est le résultat de Lorenz et Almgren (2011). La stratégie
de 2001 n'est donc optimale que sous engagement préalable de ne pas réviser, ce
que l'article assume en démontrant l'optimalité statique sous SA dynamique de
prix (note 10, p. 13).

**Aucune saisonnalité intrajournalière du volume.** La stratégie « naïve » à taux
constant en TEMPS n'est donc pas la stratégie à taux constant en VOLUME que les
courtiers appellent VWAP. Sur une séance en U, les deux diffèrent nettement, et
le repère de comparaison change.

**Le paramètre \(\lambda\) n'est pas observable.** L'article propose deux voies de
calibration, une position statique cible qui donne \(\lambda = \alpha/(2\sigma^2\bar{x})\), et la
voie de la valeur en risque avec \(\lambda_v = 1{,}645\) à 95 %. Le résultat
publié dépend de ce choix, et il n'a pas de contrepartie de marché.

**Deux points non vérifiés au 2026-09-01.** Le contenu de l'annexe A sur les
portefeuilles multi-titres n'a pas été lu en détail. La section 4, sur la
corrélation sérielle et les changements de régime, non plus.

## Nos décisions d'implémentation

non commencé au 2026-09-01

## Nos écarts avec l'article

non commencé au 2026-09-01

## Nos résultats

L'étude 010 du 2026-09-02 n'applique pas le programme d'exécution d'Almgren et
Chriss. Elle emploie la loi d'impact en racine carrée, celle que la note
attribue à Almgren (2005) et à Gatheral (2010), pour mesurer la capacité de
deux stratégies. Statut modélisé, coefficient déclaré à un. Le momentum de
série temporelle sur 28 fonds cotés a un capital d'annulation de 44,0 M$ en
forme fermée. Mais la participation dépasse dix pour cent du volume quotidien
dès 84 940 $, sur des fonds de devises, et c'est cette borne qui est retenue.
L'arbitrage statistique a une capacité nulle, son brut ne couvrant pas les cinq
points de base de demi-écart sur 1996-2026, et l'impact y ajouterait 9,3 % par
an au premier million.

## Notre contrôle de robustesse

La forme fermée et le moteur se contrôlent l'un l'autre : relancé au capital
d'annulation, le moteur rend un net moyen nul à 1e-12 quand rien n'est écrêté,
ce qu'un test exige. Diviser le coefficient par deux multiplie le capital
d'annulation par quatre, étaler l'exécution sur cinq séances le multiplie par
cinq, mesuré à la quatrième décimale sur les deux stratégies. La borne par le
plafond de participation, elle, est fragile : c'est un maximum sur tous les
rééquilibrages, et changer le nombre de séances valides d'une fenêtre l'a
déplacée d'un facteur cinq.

## Références

- Almgren, R. et Chriss, N. (2000). Optimal Execution of Portfolio Transactions.
  Document de travail, décembre 2000, 42 p. Publié dans *Journal of Risk*, 3(2),
  5-39 (2001). <https://www.smallake.kr/wp-content/uploads/2016/03/optliq.pdf>
- Gatheral, J. (2010). No-dynamic-arbitrage and market impact. *Quantitative
  Finance*, 10(7), 749-759.
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1292353> (non accessible
  au 2026-09-01)
- Gatheral, J. (2009). No-Dynamic-Arbitrage and Market Impact. Planches, École
  polytechnique, 5 janvier 2009, 47 p.
  <https://pdfs.semanticscholar.org/3683/ecb4dae470f4df219d65bb6491d3c7fd4b78.pdf>
- Gatheral, J. (2012). Optimal order execution. Planches, Scuola Normale
  Superiore, Pise, 13 juillet 2012, 80 p.
  <http://mathfinance.sns.it/wp-content/uploads/2010/12/Gatheral_Optim_Exec.pdf>
- Huberman, G. et Stanzl, W. (2004). Price Manipulation and Quasi-Arbitrage.
  *Econometrica*, 72(4), 1247-1275.
  <https://econpapers.repec.org/RePEc:ecm:emetrp:v:72:y:2004:i:4:p:1247-1275>
- Almgren, R. (2005). Equity market impact. *Risk*, juillet 2005, 57-62. Cité par
  Gatheral, non consulté.
- Lorenz, J. et Almgren, R. (2011). Mean-Variance Optimal Adaptive Execution.
  *Applied Mathematical Finance*, 18(5), 395-422. Non consulté.
- Alfonsi, A., Schied, A. et Slynko, A. (2012). Order book resilience, price
  manipulation, and the positive portfolio problem. *SIAM Journal on Financial
  Mathematics*, 3(1), 511-533. Cité par Gatheral, non consulté.
- Tóth, B., Lempérière, Y., Deremble, C., de Lataillade, J., Kockelkoren, J. et
  Bouchaud, J.-P. (2011). Anomalous price impact and the critical nature of
  liquidity in financial markets. *Physical Review X*, 021006, 1-11. Cité par
  Gatheral, non consulté.
- Bertsimas, D. et Lo, A. W. (1998). Optimal control of execution costs. *Journal
  of Financial Markets*, 1, 1-50. Cité par Almgren et Chriss, non consulté.

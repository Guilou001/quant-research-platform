# Glossaire

Chaque entrée commence par une définition **fonctionnelle** en une phrase : ce
que la notion sert à faire, pas à quelle famille elle appartient. Le détail
suit. Aucune définition ne s'appuie sur un terme défini plus bas.

Le glossaire complète les définitions, il ne les remplace pas : un terme
technique se définit d'abord à sa première apparition dans le texte qui
l'emploie.

---

## A

**Actions de société.** Les événements qui changent le nombre ou la nature des
titres détenus sans que le détenteur négocie : division, dividende, fusion,
scission. Une division deux pour un divise le prix par deux sans appauvrir
personne, et un rendement calculé sur les prix bruts affiche alors une perte de
50 % qui n'existe pas.

**Alpha.** La part du rendement qu'un modèle de facteurs n'explique pas. C'est
la constante d'une régression des rendements de la stratégie sur ceux des
facteurs de référence. Un alpha significatif contre trois facteurs disparaît
souvent contre cinq, ce qui montre qu'il n'était pas de l'alpha mais une
exposition non modélisée.

**Annualisation.** L'opération qui ramène une mesure faite à une fréquence
donnée à son équivalent annuel. Le rendement s'annualise en \(N\), la volatilité
en \(\sqrt{N}\), et cette asymétrie fait qu'un ratio de Sharpe annualisé vaut
\(\sqrt{N}\) fois le ratio périodique.

**Autocorrélation.** La corrélation d'une série avec elle-même décalée dans le
temps. Elle casse l'hypothèse d'indépendance derrière presque toutes les
formules d'erreur type, et une autocorrélation positive fait surestimer le ratio
de Sharpe.

## B

**Backtest.** La simulation d'une stratégie sur des données passées. Il mesure
ce qui se serait passé sous des hypothèses déclarées, et ne dit rien de l'avenir.

**Bêta.** La sensibilité d'un actif aux mouvements du marché, mesurée par
\(\mathrm{Cov}(r_i, r_m)/\mathrm{Var}(r_m)\). Un bêta estimé sur un échantillon
court est bruité, ce qui justifie de le rétrécir vers un (Vasicek 1973, Blume
1975).

**Biais de survie.** L'erreur qui consiste à tester une stratégie sur les seules
entités encore existantes aujourd'hui. Il gonfle le rendement et réduit le
risque mesuré en même temps, donc surestime doublement le ratio de Sharpe.

**Bootstrap par blocs.** Un rééchantillonnage qui tire des segments contigus
plutôt que des observations isolées. Il préserve la dépendance temporelle qu'un
bootstrap indépendant détruirait.

## C

**Capacité.** Le montant de capital au-delà duquel l'impact de marché mange
l'alpha. Une stratégie de ratio de Sharpe élevé et de capacité faible est
inutilisable, et l'identifier tôt évite du travail.

**CDaR.** La perte moyenne des pires drawdowns, au-delà d'un quantile. Elle est
au drawdown ce que la perte espérée est à la valeur à risque.

**Coefficient d'information (IC).** La corrélation, à une date donnée, entre les
prédictions transversales et les rendements réalisés. C'est la mesure de qualité
d'un signal avant toute construction de portefeuille.

**Cointégration.** La propriété de deux séries non stationnaires dont une
combinaison linéaire l'est. Elle fonde l'arbitrage statistique par paires, et sa
disparition explique la mort d'une paire.

**CPCV.** Validation croisée combinatoire purgée : découper l'échantillon en
blocs, en tester plusieurs à la fois, et répéter sur toutes les combinaisons.
Elle rend une distribution de performance au lieu d'un point unique.

## D

**Deflated Sharpe Ratio (ratio de Sharpe dégonflé).** Le ratio de Sharpe corrigé
du nombre d'essais menés et de leur dispersion. Il répond à « ce résultat
survit-il au fait que j'ai beaucoup cherché ? », et il exige de connaître le
nombre d'essais, y compris les ratés.

**Drawdown.** La perte depuis le plus haut atteint,
\((NAV_t - \max_{s\le t} NAV_s)/\max_{s\le t} NAV_s\). Son maximum croît
mécaniquement avec la longueur de l'échantillon, donc comparer deux drawdowns
maximaux sur des périodes de longueurs différentes n'a pas de sens.

## E

**Embargo.** Le retrait des observations immédiatement postérieures à une
période de test, en plus du purging. Il ferme la fuite que l'autocorrélation
crée dans le sens inverse du temps.

**Erreur type.** L'écart type de l'estimateur, qui dit à quel point la mesure
serait différente sur un autre échantillon. Un ratio de Sharpe de 0,4 avec une
erreur type de 0,3 est indiscernable de zéro.

## F

**Facteur.** Une source de rendement commune à plusieurs titres : marché,
taille, valeur, rentabilité, investissement, momentum. Une stratégie qui ne fait
que charger un facteur connu ne produit pas d'alpha, elle achète du bêta.

**Fuite d'information (data leakage).** La présence, dans les données
d'entraînement, d'une information indisponible au moment de la décision. C'est
la faute la plus grave d'un laboratoire quantitatif, parce qu'elle ne provoque
aucune erreur et produit d'excellents résultats.

## H

**HAC (Newey-West).** Une estimation de la matrice de covariance des
coefficients robuste à l'hétéroscédasticité et à l'autocorrélation. Elle corrige
la **variance** estimée des coefficients, pas le biais des coefficients
eux-mêmes.

**Holdout final.** La part des données gelée jusqu'à la fin, qui ne sert jamais
à choisir un paramètre. Une fois consultée, elle n'est plus hors échantillon, et
le nombre de consultations se compte.

**HRP.** *Hierarchical Risk Parity*, une allocation qui regroupe les actifs par
similarité avant de répartir le risque, sans inverser la matrice de covariance
(López de Prado, 2016). Elle évite l'instabilité de l'inversion sur des matrices
mal conditionnées.

## I

**Impact de marché.** La part du coût due au fait que négocier déplace le prix.
Il croît approximativement comme \(\sigma\sqrt{Q/ADV}\), et c'est lui qui borne
la capacité.

**Information Ratio.** Le rendement excédentaire par rapport à un indice, divisé
par l'écart type de cet excédent. Il mesure la qualité d'une gestion active
relative, là où le Sharpe mesure une performance absolue.

## L

**Largeur effective (effective breadth).** Le nombre de paris **réellement
indépendants**, qui est presque toujours plus petit que le nombre de positions.
Mille prédictions fortement corrélées ne valent pas mille paris, et c'est ce que
la loi fondamentale de la gestion active cache derrière son \(\sqrt{BR}\).

**Levier.** Le rapport de l'exposition brute au capital. Il n'est jamais
gratuit : il porte un coût de financement, et le supposer nul embellit toute
stratégie qui l'emploie.

**Loi fondamentale de la gestion active.** \(IR \approx IC\sqrt{BR}\), de
Grinold (1989). Elle dit que la qualité de prédiction et le nombre de paris
indépendants comptent tous les deux, et que le second entre en racine.

## M

**Manifeste.** L'ensemble des métadonnées d'un jeu de données : source, date de
téléchargement, période, licence, empreinte, traitement des actions de société,
caractère point-in-time. Sans lui, la question « quelle donnée a produit ce
résultat ? » n'a pas de réponse.

**Momentum.** La tendance d'un actif à prolonger sa performance récente. En
transversal, on achète les gagnants et vend les perdants ; en temporel, on suit
le signe du rendement passé de chaque actif indépendamment.

## N

**Neutralisation.** Le retrait d'une exposition non voulue d'un signal, par
régression et conservation du résidu. Une stratégie qui n'est que longue
technologie n'a pas d'alpha, elle a une exposition sectorielle.

## P

**PBO.** *Probability of Backtest Overfitting* : la probabilité que la
configuration la meilleure dans l'échantillon soit sous la médiane hors
échantillon. Une PBO élevée condamne le **processus de sélection**, quel que
soit le résultat obtenu.

**Point-in-time.** La propriété d'un jeu de données qui sait ce qu'il était à
une date passée. C'est la seule règle non négociable du laboratoire : un dépôt
accepté le 15 mai n'est pas connaissable le 31 mars.

**Purging.** Le retrait, de l'échantillon d'entraînement, des observations dont
l'étiquette déborde sur la période de test. Il est nécessaire dès qu'une
étiquette couvre plusieurs périodes.

## R

**Rendement logarithmique.** \(\ln(P_t/P_{t-1})\), additif dans le temps mais
pas entre actifs. Le rendement simple est additif entre actifs mais pas dans le
temps, et aucun des deux n'est le bon en général.

**Rétrécissement (shrinkage).** Le déplacement d'un estimateur bruité vers une
cible structurée, pour réduire l'erreur quadratique au prix d'un biais. Sur une
matrice de covariance, Ledoit et Wolf (2004) en donnent l'intensité optimale.

**Risk parity.** Une allocation où chaque composante contribue également au
risque total, plutôt qu'également au capital. Elle repose sur la décomposition
exacte \(\sum_i RC_i = \sigma_p\), qui tient par le théorème d'Euler.

**Rotation (turnover).** La part du portefeuille effectivement négociée à un
rééquilibrage, \(\frac{1}{2}\sum_i |w_{i,t} - w_{i,t}^{\text{dérivé}}|\). La
comparer aux poids cibles plutôt qu'aux poids dérivés fait payer des frais
fantômes.

## S

**Sharpe (ratio de).** Le rendement excédentaire moyen divisé par sa volatilité.
Il suppose l'indépendance temporelle, ignore la forme de la distribution, est
biaisé vers le haut quand il est sélectionné parmi plusieurs essais, et ne dit
rien de la capacité.

**Sortino (ratio de).** Comme le Sharpe, mais avec l'écart baissier au
dénominateur. La convention du dénominateur compte : diviser par le nombre total
d'observations et non par le seul nombre d'observations sous le seuil.

## T

**Tests multiples.** Le fait que chercher parmi \(N\) candidats revient à faire
\(N\) tests, ce qui rend le seuil usuel de \(t = 2\) très insuffisant. Harvey,
Liu et Zhu (2016) le montrent sur la littérature des facteurs.

## V

**Valeur à risque (VaR).** La perte qui n'est dépassée qu'avec une probabilité
\(\alpha\). Elle n'est pas sous-additive : la VaR d'un portefeuille peut
dépasser la somme des VaR de ses parties, ce qui la rend impropre à une
décomposition.

**Perte espérée (Expected Shortfall, CVaR).** La perte moyenne **au-delà** de la
valeur à risque, \(\mathbb{E}[L \mid L > VaR_\alpha]\). Elle est sous-additive
(Artzner, Delbaen, Eber et Heath, 1999), donc décomposable, ce qui explique
qu'elle ait remplacé la VaR dans la réglementation bancaire.

**Volatility targeting.** L'ajustement du levier à \(\sigma^*/\hat{\sigma}_t\)
pour viser une volatilité constante. Quand la volatilité prévue approche zéro,
le levier explose, et un plafond est la seule chose qui l'empêche.

## W

**Walk-forward.** Une validation qui avance dans le temps : estimer sur le
passé, mesurer sur le futur immédiat, décaler, recommencer. En version ancrée,
la fenêtre d'entraînement croît ; en version glissante, elle garde une longueur
fixe.

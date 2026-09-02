# Betting Against Beta

| | |
|---|---|
| **Auteurs** | Andrea Frazzini et Lasse Heje Pedersen |
| **Année** | 2014 pour la version publiée, 2013 pour la version de travail consultée |
| **Revue ou source** | Journal of Financial Economics, vol. 111, no 1 (janvier 2014), p. 1-25 |
| **Lien** | https://pages.stern.nyu.edu/~lpederse/papers/BettingAgainstBeta.pdf (version de travail du 10 mai 2013, 80 pages, téléchargée et lue le 2026-09-01) ; notice de l'éditeur : https://econpapers.repec.org/RePEc:eee:jfinec:v:111:y:2014:i:1:p:1-25 |
| **Statut de réplication** | non commencé |

Version publiée non consultée au 2026-09-01 : ScienceDirect est payant. Tous les
chiffres ci-dessous sont **rapportés** depuis la version de travail du 10 mai 2013. Cette
version cite déjà, dans ses remerciements, l'éditeur du JFE William Schwert et deux
rapporteurs anonymes, donc elle est postérieure à l'acceptation. Le résumé de la version
publiée, récupéré sur EconPapers le 2026-09-01, énonce les cinq mêmes prédictions.

## La question de recherche

Comment un arbitragiste sans contrainte exploite-t-il la platitude de la droite de marché
des titres, et cette platitude est-elle universelle ? Frazzini et Pedersen partent d'une
tension entre deux faits vrais. Le modèle d'évaluation des actifs financiers suppose que
tout agent détient le portefeuille au meilleur rapport rendement sur risque puis lève ou
réduit son levier selon son goût du risque. Or beaucoup d'investisseurs, particuliers,
caisses de retraite, fonds communs, ne peuvent pas emprunter et surpondèrent donc
directement les titres risqués.

Les auteurs posent cinq questions explicites (p. 2). Comment parie-t-on contre le bêta ?
Quelle est l'ampleur de l'effet face à la taille, la valeur et le momentum ? L'effet
existe-t-il ailleurs qu'aux États-Unis et sur d'autres classes d'actifs ? Comment la prime
varie-t-elle dans le temps et en coupe transversale ? Et qui parie contre le bêta ?

## L'intuition économique

Le rendement excédentaire vient d'une contrainte institutionnelle, pas d'une prime de
risque ni d'un biais de perception. L'agent qui ne peut pas emprunter et qui veut du
rendement doit acheter des titres à bêta élevé, le bêta étant la sensibilité du rendement
d'un titre à celui du marché. Sa demande fait monter le prix de ces titres, donc baisser
leur rendement futur. L'agent qui peut emprunter fait l'inverse : il achète du bêta faible
et l'amplifie par le levier.

Le mécanisme se lit dans une seule équation. À l'équilibre, le rendement exigé d'un titre
\(s\) s'écrit

\[ E_t\left(r^s_{t+1}\right) = r^f + \psi_t + \beta^s_t \lambda_t \]

où \(\psi_t\), la moyenne pondérée des multiplicateurs de Lagrange des contraintes de
portefeuille, mesure à quel point les contraintes de financement mordent, et où
\(\lambda_t = E_t(r^M_{t+1}) - r^f - \psi_t\). Quand \(\psi_t\) augmente, l'ordonnée à
l'origine monte et la pente baisse : la droite s'aplatit. L'alpha d'un titre vaut alors
\(\alpha^s_t = \psi_t (1 - \beta^s_t)\), donc il décroît mécaniquement dans le bêta
(proposition 1, p. 9-10).

Ce qui ferait disparaître l'effet est nommable et vérifiable : la disparition de la
contrainte. Si le levier devenait accessible et bon marché à tous, \(\psi_t\) tomberait à
zéro et l'équation redeviendrait celle du modèle d'évaluation standard. Les auteurs
observent l'inverse, la demande de fonds négociés en bourse à levier intégré étant selon
eux la preuve que beaucoup d'investisseurs ne peuvent pas emprunter directement (p. 2).

Une objection sérieuse existe, et elle est traitée plus bas. Si les titres à bêta élevé
sont ceux que les joueurs de loterie recherchent, le même profil de rendements s'obtient
sans aucune contrainte de financement. Bali, Brown, Murray et Tang (2017) défendent cette
lecture.

## Les données

Cinq classes d'actifs, dont trois reposent sur des sources non publiques. L'échantillon
d'actions couvre 55 600 titres et 20 pays (p. 14).

- **Actions américaines** : toutes les actions ordinaires de la base CRSP, de janvier 1926
  à mars 2012 ; bêtas calculés contre l'indice CRSP pondéré par la valeur ; rendements
  excédentaires au-dessus du bon du Trésor américain.
- **Actions internationales** : fichier quotidien XpressFeed Global, 19 marchés développés
  MSCI hors États-Unis ; bêtas contre l'indice MSCI local. Le corps du texte annonce
  janvier 1989 à mars 2012 (p. 15), le tableau IV annonce janvier 1984 à mars 2012.
  Contradiction interne, mesurée le 2026-09-01, non arbitrée par le texte.
- **Obligations d'État** : CRSP U.S. Treasury Database, portefeuilles obligataires de
  Fama, échéances de 1 à 10 ans, janvier 1952 à mars 2012, rendements mensuels.
- **Crédit** : indices agrégés de Barclays Capital (base Bond.Hub), janvier 1973 à mars
  2012 ; quatre indices de crédit américains par échéance et neuf portefeuilles de AAA à
  Ca-D. L'indice de détresse a été fourni aux auteurs par Credit Suisse.
- **Contrats à terme et de gré à gré** : données de prix internes d'AQR Capital Management,
  janvier 1963 à mars 2012, sur indices d'actions par pays, obligations par pays, changes
  et matières premières.
- **Écart TED**, la différence entre le taux LIBOR eurodollar à trois mois et le taux du
  Trésor américain à trois mois, de décembre 1984 à mars 2012.
- **Détentions** : fonds communs (CRSP Mutual Fund et Thomson CDA/Spectrum, mars 1980 à
  mars 2012) et particuliers d'un courtier à escompte, environ 78 000 ménages de janvier
  1991 à novembre 1996. S'y ajoutent les rachats d'entreprise (base AQR/CNH Partners,
  janvier 1963 à mars 2012) et Berkshire Hathaway (formulaires 13F, mars 1980 à mars 2012).

Les facteurs de taille, de valeur et de momentum viennent de la bibliothèque de Ken
French. Le facteur de risque de liquidité de Pastor et Stambaugh vient de WRDS et n'existe
que de 1968 à 2011. C'est ce qui fait baisser le t du modèle à cinq facteurs.

## L'univers

Toutes les actions ordinaires disponibles, sans filtre de taille ni de liquidité annoncé
dans la section de données. Les portefeuilles en déciles du tableau III utilisent les
points de coupure du NYSE, équipondèrent les titres à l'intérieur de chaque décile et se
rééquilibrent chaque mois pour tenir cette équipondération. Le facteur BAB lui-même coupe
à la médiane de la classe d'actifs, ou à la médiane du pays pour les actions internationales (p. 18-19). Le texte ne
dit pas si cette médiane se calcule sur toutes les actions CRSP ou sur les seules actions
du NYSE. L'écart entre les deux lectures est grand, parce que les petites capitalisations
dominent le compte.

Contraintes minimales de données : au moins 120 jours de bourse non manquants pour une
volatilité, au moins 750 jours pour une corrélation. En données mensuelles, au moins 12 et
36 observations.

## La méthodologie

Le bêta n'est pas estimé par régression. Frazzini et Pedersen le construisent comme le
produit d'un rapport de volatilités et d'une corrélation, chacun mesuré sur son propre
horizon (p. 16-17). Cette décision, plus que toute autre, sépare une réplication d'une
approximation, et c'est elle que Novy-Marx et Velikov attaquent.

Les portefeuilles sont pondérés par les rangs de bêta, pas par la capitalisation. Le rang
le plus bas reçoit le poids le plus fort dans le portefeuille à bêta faible, et
symétriquement du côté à bêta élevé. Les deux jambes sont ensuite remises à un bêta de un
par division par leur bêta ex ante, ce qui rend le facteur autofinancé et de bêta nul par
construction. Le rééquilibrage est mensuel.

Aux États-Unis, ce montage achète en moyenne 1,40 $ d'actions à bêta faible, financés par la
vente de 1,40 $ de titres sans risque. Il vend à découvert 0,70 $ d'actions à bêta élevé
(p. 19). Le déséquilibre vient du calcul : la jambe longue a un bêta plus faible, donc elle
demande plus de levier pour atteindre un.

Les tests temporels régressent le rendement du facteur sur le niveau et la variation de
l'écart TED, cet écart servant d'indicateur de la tension du financement.

## Les équations qui comptent

**Le bêta ex ante.** La formule à répliquer exactement :

\[ \hat{\beta}^{ts}_i = \hat{\rho} \, \frac{\hat{\sigma}_i}{\hat{\sigma}_m} \]

avec, et ce sont les quatre points où une réplication dérape :

1. \(\hat{\sigma}_i\) et \(\hat{\sigma}_m\) sont des écarts types glissants sur **un an**
   de rendements logarithmiques d'**un jour**, avec au moins 120 jours non manquants.
2. \(\hat{\rho}\) est estimée sur un horizon de **cinq ans**, avec au moins 750 jours non
   manquants, à partir de rendements logarithmiques **recouvrants de trois jours** :
   \[ r^{3d}_{i,t} = \sum_{k=0}^{2} \ln\left(1 + r^i_{t+k}\right) \]
   Le recouvrement à trois jours corrige la négociation non synchrone, qui n'affecte que
   les corrélations. Noter l'indice \(t+k\) : la fenêtre part de \(t\) et regarde en avant.
3. Le rétrécissement s'écrit
   \[ \hat{\beta}_i = w_i \hat{\beta}^{TS}_i + (1 - w_i)\hat{\beta}^{XS} \]
   avec \(w = 0{,}6\) et \(\beta^{XS} = 1\) pour toutes les périodes et tous les actifs.
   **Attention au sens** : le poids 0,6 porte sur l'estimation temporelle et 0,4 sur la
   valeur un, et non l'inverse. Vérifié le 2026-09-01 sur l'image de la page 17 du PDF,
   l'extraction textuelle ayant perdu les symboles.
4. La note 14 donne le facteur bayésien de Vasicek que les auteurs ont renoncé à utiliser,
   \(w_i = 1 - \sigma^2_{i,TS} / (\sigma^2_{i,TS} + \sigma^2_{XS})\), et précise que sa
   moyenne vaut 0,61 sur l'ensemble des actions américaines. C'est de là que vient le
   choix de 0,6.

Le rétrécissement ne change pas le classement des titres, donc pas leur affectation aux
portefeuilles. Il change en revanche le levier appliqué à chaque jambe, puisque les bêtas
servent de diviseurs.

**Les poids.** Soit \(z\) le vecteur \(n \times 1\) des rangs de bêta,
\(z_i = \mathrm{rank}(\beta_{it})\), et \(\bar{z} = \mathbf{1}'_n z / n\) le rang moyen :

\[ w_H = k (z - \bar{z})^{+}, \qquad w_L = k (z - \bar{z})^{-} \]

où \(k = 2 / \left(\mathbf{1}'_n \lvert z - \bar{z}\rvert\right)\), et où \(x^{+}\) et
\(x^{-}\) désignent les éléments positifs et négatifs du vecteur \(x\). Cette constante
donne \(\mathbf{1}'_n w_H = 1\) et \(\mathbf{1}'_n w_L = 1\), ce qui fournit un test de
réplication immédiat.

**Le facteur.**

\[ r^{BAB}_{t+1} = \frac{1}{\beta^L_t}\left(r^L_{t+1} - r^f\right) - \frac{1}{\beta^H_t}\left(r^H_{t+1} - r^f\right) \]

avec \(r^L_{t+1} = r'_{t+1} w_L\), \(r^H_{t+1} = r'_{t+1} w_H\), \(\beta^L_t = \beta'_t w_L\)
et \(\beta^H_t = \beta'_t w_H\).

**La prédiction testable.** La proposition 2 donne le rendement attendu du facteur :

\[ E_t\left(r^{BAB}_{t+1}\right) = \frac{\beta^H_t - \beta^L_t}{\beta^L_t \beta^H_t}\,\psi_t \geq 0 \]

croissant dans l'écart de bêta et dans la tension du financement. La proposition 3 ajoute
\(\partial r^{BAB}_t / \partial m^k_t \leq 0\) : un durcissement des exigences de marge
fait perdre le facteur au moment même où son rendement exigé monte.

## Les résultats originaux

**Actions américaines, janvier 1926 à mars 2012** (tableau III, p. T3, tous rapportés) :

| Grandeur | Valeur | t |
|---|---|---|
| Rendement excédentaire du facteur BAB | 0,70 % par mois | 7,12 |
| Alpha du modèle à un facteur | 0,73 % par mois | 7,44 |
| Alpha du modèle à trois facteurs | 0,73 % par mois | 7,39 |
| Alpha du modèle à quatre facteurs | 0,55 % par mois | 5,59 |
| Alpha du modèle à cinq facteurs | 0,55 % par mois | 4,09 |
| Volatilité annualisée | 10,7 % | |
| Ratio de Sharpe annualisé | 0,78 | |
| Bêta ex ante | 0,00 | |
| Bêta réalisé | -0,06 | |

Le bêta réalisé n'est pas exactement nul, et les auteurs l'attribuent au bruit des bêtas
ex ante (p. 22). Les dix portefeuilles triés par bêta montrent la platitude annoncée. Du premier au dernier
décile, le rendement excédentaire va de 0,91 % à 0,97 % par mois. Sur la même échelle,
l'alpha à trois facteurs passe de 0,40 % à -0,49 %, le ratio de Sharpe de 0,70 à 0,28 et
le bêta ex ante de 0,64 à 1,70.

**Actions internationales groupées** (tableau IV) : alphas de 0,28 % à 0,64 % par mois
selon le modèle de risque, t de 2,09 à 4,81.

**Par pays** (tableau V) : ratio de Sharpe positif dans 18 des 19 marchés développés, seule
l'Autriche étant négative et non significative. L'alpha à quatre facteurs est positif dans
13 des 19. Le rendement de BAB est significativement positif dans 6 pays, et aucun alpha
négatif n'est significatif.

**Autres classes d'actifs** (rapportés, p. 24-26) :

| Classe | Alpha mensuel | t | Sharpe annualisé |
|---|---|---|---|
| Obligations d'État américaines | 0,17 % | 6,26 | 0,81 |
| Crédit par échéance | 0,11 % | 5,14 | 0,82 |
| Crédit couvert du risque de taux | 0,17 % | 4,44 | non trouvé |
| Crédit par cote | 0,57 % | 3,72 | non trouvé |
| Tous contrats à terme combinés | 0,25 % | 2,53 | non trouvé |
| Sélection de pays | 0,26 % | 2,42 | non trouvé |
| Moyenne de tous les facteurs BAB | 0,54 % | 6,98 | non trouvé |

Sur les contrats à terme pris séparément, les ratios de Sharpe vont de 0,11 à 0,51 et
seul le bloc des indices d'actions permet de rejeter l'hypothèse nulle.

L'exemple chiffré des obligations mérite d'être retenu, parce qu'il rend la contrainte
tangible. Une caisse qui vise 2,9 % de rendement excédentaire l'obtient en plaçant 1 $ sur
des obligations de plus de dix ans. Pour la même cible avec des obligations à un an, il lui
faudrait 11 $ si tous les ratios de Sharpe étaient égaux, donc emprunter 10 $. Comme les
titres courts offrent en réalité de meilleurs ratios, 5 $ suffisent. Un levier de cinq
contre un reste hors de portée de beaucoup de caisses, et le marché s'équilibre à ce prix
(p. 24).

## Les critiques connues

**Novy-Marx et Velikov (2022), la critique centrale.** « Betting against betting against
beta », Journal of Financial Economics 143(1), p. 80-106. Version de travail de novembre
2018 consultée intégralement le 2026-09-01 sur
https://mysimon.rochester.edu/novy-marx/research/BABAB.pdf (46 pages). Les chiffres
ci-dessous viennent de cette version, pas de la version publiée, et l'échantillon y court
de janvier 1968 à décembre 2017.

Ils identifient trois procédures non standard, et en tirent trois conséquences distinctes.

1. *La pondération par les rangs.* Elle produit des portefeuilles quasi indiscernables de
   portefeuilles équipondérés, parce que la capitalisation n'entre nulle part dans les
   poids. Résultat mesuré : pour chaque dollar investi dans BAB, la stratégie engage en
   moyenne 1,05 $ sur des titres du dernier centile de capitalisation. Près d'un tiers de
   cette somme va au dernier millième, des sociétés valant moins de 92 M$ en fin
   d'échantillon (p. 17-18). La jambe longue met en moyenne 95,4 cents par dollar sur le
   décile NYSE le plus petit, qui pèse 1,7 % du marché, contre 26,3 cents de vente à
   découvert.
2. *La couverture par le levier.* Diviser chaque jambe par son bêta estimé revient à se
   couvrir avec un marché équipondéré. La version couverte directement par le marché
   équipondéré fait mieux que BAB (Sharpe 1,26 contre 1,08). Celle couverte par le marché
   pondéré par la capitalisation, plus conforme à la théorie, tombe à 0,80 (p. 15). La
   comparaison se lit à volatilité égale : les trois séries sont ramenées à la volatilité
   d'échantillon de BAB, 11,9 %, celle de la version équipondérée n'étant que de 9,6 %.
3. *L'estimateur de bêta.* Ils établissent l'identité
   \[ \beta^{FP}_i = \frac{\sigma^i_1 / \sigma^i_5}{\sigma^{mkt}_1 / \sigma^{mkt}_5}\, \beta^i_5 \]
   où \(\beta^i_5\) est le bêta de régression sur cinq ans. Le bêta de Frazzini et Pedersen
   mélange donc le bêta de marché et la volatilité du titre. Conséquence mesurée : le bêta
   ainsi calculé du portefeuille de marché, qui vaut un par définition, a une moyenne de
   1,05 et un écart type de 0,09. La volatilité de marché explique 47 % de sa variation
   temporelle et près de 58 % de celle de la dispersion transversale des bêtas. La
   « compression des bêtas » de la proposition 4 est alors un artefact. Toute variable
   corrélée à la volatilité de marché la prédit. La volatilité de l'écart TED cesse de
   la prédire une fois la volatilité de marché contrôlée.

Conséquences chiffrées sur la performance. Les coûts de transaction, calculés par la
méthode de Novy-Marx et Velikov (2016), valent en moyenne 60 points de base par mois sur
1968-2017 et 26 sur les dix dernières années. Ils amputent la rentabilité de plus de 55 %.
Nette de coûts, la stratégie rapporte encore 48 points de base par mois (t = 3,30). Mais son
alpha généralisé contre le modèle à cinq facteurs de Fama et French tombe à 16 points de
base (t = 1,20). La version pondérée par la capitalisation rapporte 56 points de base par
mois (t = 3,48), pour un Sharpe de 0,49 contre 1,08. Elle charge 0,45 sur le facteur de
rentabilité (t = 6,59) et 0,50 sur celui d'investissement (t = 4,86). Enfin l'arbitrage de
bêta de Black (1972), plus simple, obtient un Sharpe de 1,09 contre 1,08 pour BAB, avec une
corrélation de 84 %.

**Bali, Brown, Murray et Tang (2017).** « A Lottery-Demand-Based Explanation of the Beta
Anomaly », Journal of Financial and Quantitative Analysis 52(6), p. 2369-2397. Résumé
récupéré sur EconPapers le 2026-09-01, article intégral non consulté. Leur thèse : l'anomalie
disparaît quand les portefeuilles triés par bêta sont neutralisés à la demande de loterie,
quand les régressions la contrôlent, ou quand le modèle de facteurs en inclut un. Elle se
concentre dans les titres à faible détention institutionnelle. C'est une explication
concurrente et non une réfutation des chiffres.

**La réponse des auteurs.** Asness, Frazzini, Gormsen et Pedersen (2020), « Betting against
correlation: Testing theories of the low-risk effect », Journal of Financial Economics
135(3), p. 629-652. Résumé récupéré sur EconPapers le 2026-09-01, article intégral non
consulté. Le bêta se décompose en volatilité et corrélation, et seule la volatilité est
liée au risque idiosyncrasique. Ils construisent un facteur qui parie contre la corrélation
seule, qui performe aux États-Unis et à l'international, ce qui soutient la thèse des
contraintes de levier. Leur conclusion est mixte : le facteur de corrélation est lié à la
dette sur marge, les facteurs de risque idiosyncrasique au sentiment, donc les deux
explications contribuent.

**Herculano (2024).** « Betting Against (Bad) Beta », version du 28 août 2024, arXiv
2409.00416, déposée sur arXiv le 2024-08-31, première page consultée le 2026-09-01. En
s'appuyant sur la distinction de
Campbell et Vuolteenaho (2004) entre bon et mauvais bêta, il montre qu'un portefeuille à
bêta faible peut pencher vers le mauvais bêta, et propose un double tri. Sa conclusion
dépend explicitement d'une bonne maîtrise des coûts de transaction. Version publiée :
Quantitative Finance 25(6), p. 949-958, juin 2025, notice vérifiée sur Crossref le
2026-09-01, texte non récupéré.

**La réponse d'AQR aux coûts de transaction.** Un extrait de recherche du 2026-09-01
attribue à AQR deux arguments. Ses coûts de négociation réels seraient bien inférieurs aux
estimations de la littérature. Et pondération par la valeur, par les rangs et
équipondération donneraient des résultats comparables sur l'échantillon complet depuis les
années 1920. Les deux pages qui rapportent cet argument, Alpha Architect et TalkMarkets,
renvoient un code 403, testées à nouveau le 2026-09-01. Aucun document d'AQR n'a été
récupéré. **Non vérifié**, à ne pas citer en l'état.

## Les problèmes de réplication connus

**Deux séries BAB officielles ne coïncident pas.** AQR publie un « original paper dataset »,
qui s'arrête en mars 2012, et un « BAB equity factor » tenu à jour. Novy-Marx et Velikov
(2018, p. 6-7) mesurent que les deux ne sont corrélées qu'à 96,2 % après 1967, et que
l'ancienne a un ratio de Sharpe significativement plus élevé. Choisir la cible de
réplication est donc déjà une décision. Leur propre reconstruction atteint une corrélation
mensuelle de 98,5 % avec la série d'origine et le même ratio de Sharpe de 1,01 sur janvier
1968 à mars 2012.

**Trois sources de données ne sont pas publiques** : les prix de contrats à terme d'AQR,
l'indice de détresse fourni par Credit Suisse, et la base Bond.Hub de Barclays. La base de
détentions du courtier à escompte et celle des rachats d'AQR/CNH ne le sont pas davantage.
Les blocs actions et obligations d'État restent reconstructibles, le reste non.

**La contradiction de dates sur l'échantillon international**, 1989 dans le texte contre
1984 dans le tableau IV, n'est pas résolue par l'article. Il faudra trancher et le déclarer.

**L'univers de la médiane de bêta n'est pas spécifié.** Les déciles utilisent les points de
coupure du NYSE, la coupure du facteur utilise « la médiane de la classe d'actifs ». Selon
qu'on prend la médiane sur toutes les actions ou sur les seules actions du NYSE, la
composition des deux jambes change beaucoup, puisque les petites capitalisations dominent
le nombre.

**Le sens du rétrécissement se lit à l'envers si l'on se fie à l'extraction textuelle du
PDF.** Les symboles mathématiques y sont perdus. La lecture de l'image de la page 17,
faite le 2026-09-01, donne 0,6 sur l'estimation temporelle et 0,4 sur un.

**La fenêtre recouvrante de trois jours regarde en avant.** L'article écrit
\(r^{3d}_{i,t} = \sum_{k=0}^{2} \ln(1 + r^i_{t+k})\), donc l'observation datée \(t\)
contient \(t+1\) et \(t+2\). Sur une corrélation glissante à cinq ans qui s'arrête à la fin
du mois précédent, l'effet est négligeable, mais l'alignement doit être écrit et testé.

**Le facteur de liquidité n'existe que de 1968 à 2011.** C'est pourquoi le t de l'alpha à
cinq facteurs (4,09) est plus bas que celui à quatre facteurs (5,59), pour un alpha
identique de 0,55 %.

**Le traitement des rendements de radiation n'est pas décrit** dans la section de données
de BAB, contrairement à l'article Quality Minus Junk des mêmes auteurs, qui applique
-30 % à la manière de Shumway (1997). Décision à prendre et à déclarer.

## Les biais possibles

**La négociation non synchrone est doublement en cause.** Elle biaise les bêtas des petites
capitalisations vers le bas, et ces titres se retrouvent donc préférentiellement du côté
long. Novy-Marx et Velikov (2018, section 5) en tirent que le bêta de BAB mesuré à horizon
long dépasse celui mesuré à horizon court, donc que la stratégie n'est pas neutre au
marché comme prévu. La correction par rendements de trois jours atténue le problème sans
l'annuler.

**Le bruit d'estimation se transforme en levier.** Les bêtas ex ante servent de diviseurs
dans l'équation (17). Un bêta sous-estimé sur la jambe longue produit un levier excessif,
et l'erreur ne se compense pas entre les deux jambes. Les auteurs le reconnaissent et
choisissent d'appuyer l'inférence sur les rendements anormaux réalisés (p. 18).

**La capacité et le coût de la vente à découvert ne sont pas modélisés.** La jambe courte
porte 26,3 cents par dollar sur le décile le plus petit selon Novy-Marx et Velikov, et ces
titres sont chers à emprunter quand ils sont empruntables.

**Le survivant et la radiation dans XpressFeed Global.** Les rendements de radiation ne
sont pas disponibles hors États-Unis, ce que les auteurs écrivent ailleurs. Le sens du
biais est connu : il flatte les portefeuilles chargés en titres fragiles, donc plutôt la
jambe courte.

**Le choix du facteur de rétrécissement pourrait être un degré de liberté.** Les auteurs
déclarent que les résultats sont « très similaires » avec le facteur de Vasicek complet, et
justifient 0,6 par une moyenne empirique de 0,61. La déclaration n'est pas chiffrée dans le
texte principal.

**L'écart TED comme indicateur de financement est contesté.** Novy-Marx et Velikov montrent
qu'il est corrélé à la volatilité de marché, et que c'est cette dernière qui porte le
résultat de compression. Un test de la proposition 4 qui n'orthogonalise pas à la
volatilité de marché ne prouve rien.

## Nos décisions d'implémentation

non commencé au 2026-09-01

## Nos écarts avec l'article

non commencé au 2026-09-01

## Nos résultats

Étude `005_betting_against_beta`, verdict **`REJECTED`**, menée le 2026-09-02.

Le facteur publié ne s'affaiblit pas après l'article, et un détail
d'estimation décide de tout. Sur la colonne USA du classeur d'AQR, le ratio de
Sharpe vaut 0,703 jusqu'à 2012-03 et 0,689 après, écart 0,015, p = 0,960. Le
rendement mensuel se réplique, 0,676 % contre 0,70 publié.

Notre reconstruction au niveau du titre suit la méthode exacte de l'article.
C'est le rétrécissement du bêta de 0,6 vers un qui tranche. Le ratio de Sharpe
du facteur reconstruit passe de 0,394 sans rétrécissement à -0,001 au réglage de
l'article, alors que le classement des titres est identique dans les deux cas.
Le bêta réalisé du facteur passe de +0,081 à -0,182. Le constat rejoint la
critique de Novy-Marx et Velikov. Verdict `REJECTED`, statut mesuré, source
`studies/005_betting_against_beta/results/`.

## Notre contrôle de robustesse

non commencé au 2026-09-01

## Références

- Frazzini, A. et Pedersen, L. H. (2014), « Betting against beta », Journal of Financial
  Economics 111(1), p. 1-25. Version de travail du 2013-05-10 consultée :
  https://pages.stern.nyu.edu/~lpederse/papers/BettingAgainstBeta.pdf
  Notice : https://econpapers.repec.org/RePEc:eee:jfinec:v:111:y:2014:i:1:p:1-25
- Novy-Marx, R. et Velikov, M. (2022), « Betting against betting against beta », Journal of
  Financial Economics 143(1), p. 80-106. Version de travail de novembre 2018 consultée :
  https://mysimon.rochester.edu/novy-marx/research/BABAB.pdf
  Notice : https://econpapers.repec.org/RePEc:eee:jfinec:v:143:y:2022:i:1:p:80-106
- Bali, T. G., Brown, S. J., Murray, S. et Tang, Y. (2017), « A Lottery-Demand-Based
  Explanation of the Beta Anomaly », Journal of Financial and Quantitative Analysis 52(6),
  p. 2369-2397.
  https://econpapers.repec.org/RePEc:cup:jfinqa:v:52:y:2017:i:06:p:2369-2397_00
- Asness, C., Frazzini, A., Gormsen, N. J. et Pedersen, L. H. (2020), « Betting against
  correlation: Testing theories of the low-risk effect », Journal of Financial Economics
  135(3), p. 629-652.
  https://econpapers.repec.org/RePEc:eee:jfinec:v:135:y:2020:i:3:p:629-652
- Herculano, M. C. (2025), « Betting Against (Bad) Beta », Quantitative Finance 25(6),
  p. 949-958. Version arXiv 2409.00416 consultée : https://arxiv.org/pdf/2409.00416
- Black, F. (1972), « Capital Market Equilibrium with Restricted Borrowing », Journal of
  Business 45(3), p. 444-455. Cité par l'article comme origine de l'idée, non consulté.
- Black, F., Jensen, M. et Scholes, M. (1972), « The Capital Asset Pricing Model: Some
  Empirical Tests ». Cité par l'article, non consulté.
- Vasicek, O. A. (1973), « A Note on using Cross-sectional Information in Bayesian
  Estimation of Security Betas », Journal of Finance. Source du rétrécissement, non consulté.
- Novy-Marx, R. et Velikov, M. (2016), méthode d'estimation des coûts de transaction
  employée dans la critique de 2022. Non consulté.
- Asness, C., Frazzini, A. et Pedersen, L. H. (2019), « Quality minus junk », Review of
  Accounting Studies 24(1), p. 34-112. Le score de sûreté de cet article utilise le bêta
  défini ici. Fiche interne : `asness_frazzini_pedersen_2019_qmj.md`

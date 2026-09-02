# Quality Minus Junk

| | |
|---|---|
| **Auteurs** | Clifford S. Asness, Andrea Frazzini et Lasse Heje Pedersen |
| **Année** | 2019 pour la version publiée, 2014 pour la version de travail consultée |
| **Revue ou source** | Review of Accounting Studies, vol. 24, no 1 (mars 2019), p. 34-112 |
| **Lien** | Version publiée, sous licence CC BY mais inaccessible : https://doi.org/10.1007/s11142-018-9470-2. Version de travail du 19 juin 2014 consultée intégralement : https://www.nhh.no/globalassets/departments/business-and-management-science/seminars/2015-fall/020915.pdf. Version du 9 octobre 2013 également consultée : http://www.efalken.com/LowVolClassics/Asness_Frazzini_Pedersen_QMJ.pdf |
| **Statut de réplication** | non commencé |

Version publiée non consultée au 2026-09-01, et c'est un problème pour cette fiche
précise. Le fichier de Springer est en libre accès selon Unpaywall. Mais l'adresse
`link.springer.com/content/pdf/10.1007/s11142-018-9470-2.pdf` renvoie une page de
protection anti-robot sous un code 200, et la copie du dépôt de la Copenhagen Business
School renvoie un 403. Quatre autres voies ont échoué. **Tous les chiffres ci-dessous sont
rapportés depuis la version de travail du 19 juin 2014.** La section « Les problèmes de
réplication connus » explique pourquoi. Les définitions ont probablement changé entre cette
version et l'article publié.

## La question de recherche

Le marché paie-t-il pour la qualité, et le paie-t-il assez ? Asness, Frazzini et Pedersen
posent d'abord une définition qui n'est pas une liste. Une action de qualité est une
action dont les caractéristiques justifient, toutes choses égales par ailleurs, de payer
un prix plus élevé. La question devient alors mesurable en deux temps. Un, les actions de
qualité se paient-elles plus cher ? Deux, si oui, la différence de prix suffit-elle à
annuler l'écart de rendement ?

La tension qu'ils exhibent tient en une phrase. Les actions de qualité se paient
effectivement plus cher, mais si peu que le rendement ajusté du risque reste élevé.

## L'intuition économique

Le rendement vient d'un prix trop bas payé pour une caractéristique persistante et
observable. Le mécanisme se lit dans le modèle de Gordon réécrit (équation 1, p. 3) :

\[ \frac{P}{B} = \frac{\text{rentabilité} \cdot \text{taux de distribution}}{\text{rendement exigé} - \text{croissance}} \]

Les quatre grandeurs du membre de droite sont exactement les quatre composantes de la
qualité. Une entreprise plus rentable, qui croît davantage, dont le rendement exigé est
plus faible parce qu'elle est plus sûre, ou qui distribue davantage, devrait valoir plus
cher par unité de valeur comptable. Ce n'est pas une prédiction de rendement mais une
prédiction de prix, et c'est ce qui distingue l'article de la littérature sur les
anomalies.

Le fait mesuré est que ce prix ne monte pas assez. Une hausse d'un écart type du score de
qualité s'accompagne au mieux d'une hausse de 0,32 écart type du prix rapporté à la valeur
comptable. Et la qualité n'explique que 12 % de la variance transversale des prix aux
États-Unis, 6 % à l'international (p. 14, rapporté). Si le marché payait la qualité à son
prix, l'écart de rendement disparaîtrait sans que le pouvoir explicatif change de nature.

Trois explications restent alors ouvertes, et les auteurs en éliminent une. Une prime de
risque exigerait que les actions de qualité soient plus risquées. Or leur bêta est plus
faible, leur exposition au facteur de taille est négative, et le facteur ne perd pas dans
les creux de marché. Reste la mauvaise évaluation, avec ou sans limite à l'arbitrage.

Ce qui ferait disparaître l'effet est donc nommable : que le prix de la qualité monte. Les
auteurs en font une variable et montrent qu'un prix bas de la qualité prédit un rendement
futur élevé du facteur, ce prix ayant atteint son creux pendant la bulle internet.

## Les données

Un échantillon de 39 308 actions couvrant 24 pays développés entre juin 1951 et décembre
2012 (p. 8, rapporté). Deux sous-échantillons servent aux tests.

- **Échantillon long américain** : toutes les actions ordinaires de la base fusionnée
  CRSP/XpressFeed, code de titre CRSP 10 ou 11. La première date disponible est juin 1951,
  les données comptables commençant à l'exercice 1950. Comme certaines variables mesurent
  une croissance sur cinq ans, les régressions et les tests de rendement commencent en
  **juin 1956** et vont jusqu'à décembre 2012.
- **Échantillon large mondial** : 24 marchés développés, ceux de l'indice MSCI World
  Developed au 31 décembre 2012, code de titre XpressFeed 0. Le corps du texte annonce
  janvier 1986 à décembre 2012 (p. 9), les tableaux annoncent juin 1986 à décembre 2012.
  Contradiction interne mesurée le 2026-09-01. La couverture commence en 1982 pour le
  Canada et en 1986 pour la plupart des autres pays.

Trois conventions de traitement conditionnent la réplication.

1. **Alignement comptable** : les variables comptables de l'exercice clos dans l'année
   civile \(t-1\) sont rattachées à juin de l'année \(t\).
2. **Rendements de radiation** : ceux de CRSP quand ils existent. Quand une entreprise
   disparaît sans rendement de radiation et que la disparition est liée à la performance,
   les auteurs appliquent -30 % à la manière de Shumway (1997). Aucun rendement de
   radiation n'est disponible pour l'échantillon international.
3. **Devise** : tous les rendements sont en dollars américains, sans couverture de change,
   et les rendements excédentaires se mesurent au-dessus du bon du Trésor américain.

Les facteurs de marché, de taille, de valeur et de momentum utilisés en variables
explicatives sont ceux d'Asness et Frazzini (2013). Ils sont construits pays par pays, puis
agrégés en pondérant chaque pays par sa capitalisation totale retardée.

## L'univers

Toutes les actions ordinaires des 24 marchés, sans filtre de liquidité annoncé. Une seule
exclusion explicite : le calcul du rapport valeur comptable sur valeur de marché exige une
valeur comptable positive.

Les tris se font pays par pays, et les portefeuilles mondiaux s'obtiennent en pondérant
chaque pays par sa capitalisation totale retardée. Pour les tris par taille, le point de
coupure est la médiane du NYSE aux États-Unis et le 80e centile par pays à l'international,
ce qui correspond approximativement au NYSE selon les auteurs.

Deux exigences minimales limitent l'univers effectif. La volatilité des bénéfices demande
au moins douze trimestres non manquants sur soixante, ou cinq exercices annuels non
manquants faute de données trimestrielles. Les mesures de croissance sur cinq ans écartent
mécaniquement les entreprises de moins de cinq ans d'historique comptable.

## La méthodologie

Le score de qualité s'obtient par cotes centrées réduites de rangs, agrégées en quatre
composites puis en un score unique. Chaque mois, chaque variable est convertie en rangs
transversaux, puis ces rangs sont centrés et réduits. Formellement, pour une variable
\(x\) de vecteur de rangs \(r = \mathrm{rank}(x)\) :

\[ z(x) = \frac{r - \mu_r}{\sigma_r} \]

Le passage par les rangs limite l'effet des valeurs extrêmes et donne au coefficient de
régression une lecture directe en écarts types. Chaque composite est la cote centrée
réduite de la somme des cotes de ses variables, et le score final la cote centrée réduite
de la somme des quatre composites.

Deux jeux de portefeuilles servent aux tests. Le premier trie les actions en dix
portefeuilles de qualité par pays, avec points de coupure du NYSE aux États-Unis,
pondération par la valeur et rééquilibrage mensuel. Le second est le facteur QMJ, construit
comme l'intersection de six portefeuilles pondérés par la valeur formés sur la taille et la
qualité. Le tri est conditionnel, la taille d'abord, la qualité ensuite. Le facteur est
long des 30 % les plus élevés en qualité et court des 30 % les plus bas, à l'intérieur de
l'univers des grandes puis de celui des petites (p. 5).

Le prix de la qualité se mesure par régression transversale à la Fama-MacBeth. La cote du
rapport valeur de marché sur valeur comptable est régressée sur le score de qualité, avec
erreurs types corrigées de l'hétéroscédasticité et de l'autocorrélation à douze retards
(Newey-West). Les effets fixes de pays et d'industrie s'implémentent en changeant l'univers
de standardisation des cotes, pas en ajoutant des indicatrices.

## Les équations qui comptent

**Le score de qualité** agrège quatre composites, chacun agrégeant ses propres variables.
La liste qui suit est celle de l'annexe A1 de la version du 19 juin 2014, lue sur images
le 2026-09-01 parce que l'extraction textuelle du PDF perd les symboles. Les noms entre
parenthèses sont les postes CRSP/XpressFeed, et les postes annuels sauf mention contraire.

\[ \text{Qualité} = z\left(z_{\text{rentabilité}} + z_{\text{croissance}} + z_{\text{sûreté}} + z_{\text{distribution}}\right) \]

**1. Rentabilité**, six variables.

\[ \text{Rentabilité} = z\left(z_{gpoa} + z_{roe} + z_{roa} + z_{cfoa} + z_{gmar} + z_{acc}\right) \]

| Variable | Définition de l'annexe |
|---|---|
| GPOA | profit brut sur actif, \((REVT - COGS)/AT\) |
| ROE | résultat net sur fonds propres comptables, \(IB/BE\) |
| ROA | résultat net sur actif, \(IB/AT\) |
| CFOA | \((IB + DP - \Delta WC - CAPX)/AT\) |
| GMAR | marge brute, \((REVT - COGS)/SALE\) |
| ACC | faibles régularisations, \(-(\Delta WC - DP)/AT\) |

Le fonds de roulement vaut \(WC = ACT - LCT - CHE + DLC + TXP\). Les fonds propres
comptables \(BE\) valent les capitaux propres moins les actions privilégiées : on prend
\(SEQ\), sinon \(CEQ + PSTK\), sinon \(AT - (LT + MIB)\) ; on retranche ensuite la valeur
des privilégiées, \(PSTKRV\), \(PSTKL\) ou \(PSTK\) selon disponibilité.

**2. Croissance**, six variables, chacune étant la variation sur cinq ans du numérateur
divisée par le dénominateur retardé de cinq ans.

\[ \text{Croissance} = z\left(z_{\Delta gpoa} + z_{\Delta roe} + z_{\Delta roa} + z_{\Delta cfoa} + z_{\Delta gmar} + z_{\Delta acc}\right) \]

Soit, avec \(GP = REVT - COGS\), \(CF = IB + DP - \Delta WC - CAPX\) et
\(MWCPD = -(\Delta WC - DP)\) :
\((GP_t - GP_{t-5})/AT_{t-5}\), \((IB_t - IB_{t-5})/BE_{t-5}\),
\((IB_t - IB_{t-5})/AT_{t-5}\), \((CF_t - CF_{t-5})/AT_{t-5}\),
\((GP_t - GP_{t-5})/SALE_{t-5}\) et \((MWCPD_t - MWCPD_{t-5})/A_{t-5}\).

Le piège est au dénominateur : la croissance de la marge brute se divise par les ventes
retardées, pas par l'actif retardé.

**3. Sûreté**, six variables.

\[ \text{Sûreté} = z\left(z_{bab} + z_{ivol} + z_{lev} + z_{o} + z_{z} + z_{evol}\right) \]

| Variable | Définition de l'annexe |
|---|---|
| BAB | \(-\beta\), le bêta étant estimé comme dans Frazzini et Pedersen, produit de l'écart type quotidien glissant sur un an et de la corrélation glissante sur cinq ans de rendements de trois jours |
| IVOL | \(-\sigma^i\), écart type glissant sur un an du rendement excédentaire quotidien ajusté du bêta, en sautant le dernier jour de bourse |
| LEV | \(-(DLTT + DLC + MIBT + PSTK)/AT\) |
| O | l'opposé de la cote O d'Ohlson (1980) |
| Z | la cote Z d'Altman (1968) |
| EVOL | l'opposé de l'écart type du ROE trimestriel sur soixante trimestres, douze non manquants exigés |

La cote O s'écrit, avec le signe négatif initial qui la retourne en mesure de sûreté :

\[
\begin{aligned}
O = -\big(&-1{,}32 - 0{,}407 \log(ADJASSET/CPI) + 6{,}03\, TLTA - 1{,}43\, WCTA \\
&+ 0{,}076\, CLCA - 1{,}72\, OENEG - 2{,}37\, NITA - 1{,}83\, FUTL \\
&+ 0{,}285\, INTWO - 0{,}521\, CHIN\big)
\end{aligned}
\]

où \(ADJASSET = AT + 0{,}1 (ME - BE)\), \(TLTA = (DLC + DLTT)/ADJASSET\),
\(WCTA = (ACT - LCT)/ADJASSET\), \(CLCA = LCT/ACT\), \(OENEG = \mathbf{1}(LT > AT)\),
\(NITA = IB/AT\), \(FUTL = PT/LT\), \(INTWO = \mathbf{1}(\max\{IB_t, IB_{t-1}\} < 0)\) et
\(CHIN = (IB_t - IB_{t-1}) / (\lvert IB_t \rvert + \lvert IB_{t-1} \rvert)\). Le \(CPI\)
est l'indice des prix à la consommation.

La cote Z vaut \(Z = (1{,}2\, WC + 1{,}4\, RE + 3{,}3\, EBIT + 0{,}6\, ME + SALE)/AT\).

**4. Distribution**, trois variables.

\[ \text{Distribution} = z\left(z_{eiss} + z_{diss} + z_{npop}\right) \]

\(EISS = -\log(SHROUT\_ADJ_t / SHROUT\_ADJ_{t-1})\) sur le nombre d'actions ajusté des
fractionnements ; \(DISS = -\log(TOTD_t / TOTD_{t-1})\) avec
\(TOTD = DLTT + DLC + MIBT + PSTK\) ; \(NPOP\) est la somme sur cinq ans de
\(IB - \Delta BE\) divisée par la somme sur cinq ans de \(REVT - COGS\).

Le compte donne 6 + 6 + 6 + 3 = **21 variables**. Le corps du texte annonce « 22 quality
measures » (p. 19 de la version du 19 juin 2014, même phrase dans celle du 9 octobre
2013). Écart mesuré le 2026-09-01, non résolu par le texte.

**Le facteur.** QMJ est la moyenne des deux portefeuilles de qualité moins la moyenne des
deux portefeuilles de rebut, chacun pondéré par la valeur :

\[ QMJ = \tfrac{1}{2}\left(\text{petite qualité} + \text{grande qualité}\right) - \tfrac{1}{2}\left(\text{petit rebut} + \text{grand rebut}\right) \]

**Le prix de la qualité.** En notant \(P_i = z(MB_i)\) la cote du rapport valeur de marché
sur valeur comptable :

\[ P^t_i = a + b\, \text{Qualité}^t_i + \varepsilon^t_i \]

Le coefficient \(b\) se lit directement : une hausse d'un écart type de la qualité
s'accompagne d'une hausse de \(b\) écart type du prix.

## Les résultats originaux

**Le facteur QMJ** (tableau VI de la version du 19 juin 2014, tous rapportés) :

| Grandeur | États-Unis, 1956-2012 | t | Monde, 1986-2012 | t |
|---|---|---|---|---|
| Rendement excédentaire | 0,40 % par mois | 4,38 | 0,38 % par mois | 3,22 |
| Alpha à un facteur | 0,55 % par mois | 7,27 | 0,52 % par mois | 5,75 |
| Alpha à trois facteurs | 0,68 % par mois | 11,10 | 0,61 % par mois | 7,68 |
| Alpha à quatre facteurs | 0,66 % par mois | 10,20 | 0,45 % par mois | 5,50 |
| Ratio de Sharpe annualisé | 0,58 | | 0,62 | |
| Ratio d'information annualisé | 1,46 | | 1,16 | |

Chargements à quatre facteurs aux États-Unis : marché -0,25 (t -17,02), taille -0,38
(t -17,50), valeur -0,12 (t -5,03), momentum 0,02 (t 0,82), R² ajusté 0,57. Le facteur est
donc long des grandes capitalisations à bêta faible et court des petites à bêta élevé, ce
qui est la lecture directe des signes.

Attention à une incohérence interne : le corps du texte annonce un t de 11,20 pour l'alpha
à quatre facteurs américain, le tableau VI imprime 10,20. Mesuré le 2026-09-01.

**Les quatre composantes prises séparément** (États-Unis, alphas à quatre facteurs) :
rentabilité 0,53 % (t 8,71), sûreté 0,57 % (t 7,97), croissance 0,38 % (t 6,13),
distribution 0,21 % (t 3,43). La corrélation moyenne deux à deux entre composantes vaut
0,40 aux États-Unis et 0,45 dans le monde, et 0,38 sur les résidus à quatre facteurs dans
les deux cas. Toutes les corrélations sont positives sauf celle entre croissance et
distribution.

**Les déciles de qualité.** L'écart de rendement brut entre le dernier et le premier décile
va de 47 à 68 points de base par mois selon l'échantillon, avec des t de 2,80 à 3,22.
Corrigé du risque, l'écart grandit. Il va de 71 à 97 points de base aux États-Unis selon le
modèle (t de 4,92 à 9,02), et de 89 à 112 points de base dans le monde (t de 5,00 à 6,06).
L'alpha dépasse le rendement brut parce que les actions de qualité ont des expositions plus
faibles, au marché en particulier.

**Par pays.** Le facteur délivre des rendements et des alphas positifs dans 23 des 24 pays,
la seule exception, faiblement négative, étant la Nouvelle-Zélande. Les alphas à quatre
facteurs sont significatifs dans 17 des 24.

**Le prix de la qualité.** Coefficient maximal de 0,32 dans la spécification univariée,
hautement significatif. Le pouvoir explicatif reste faible : 12 % de la variance
transversale des prix aux États-Unis, 6 % dans le monde.

**L'effet taille ressuscité.** Le facteur de taille a un alpha de 13 points de base par
mois, non significatif, contre les autres facteurs standards. En ajoutant la qualité au
membre de droite, cet alpha passe à 64 points de base (t 6,39). Lecture des auteurs : à
qualité comparable, les petites capitalisations battent bien les grandes.

**Qualité à prix raisonnable.** La combinaison de QMJ et du facteur de valeur au meilleur
ratio de Sharpe met environ 70 % sur QMJ aux États-Unis et environ 60 % dans le monde. Le
ratio de Sharpe atteint alors environ 0,7 et 0,9 respectivement.

## Les critiques connues

**Novy-Marx et Medhat (2025), la réfutation la plus directe.** « Profitability
Retrospective: What Have We Learned? », NBER Working Paper 33601, mars 2025, consulté le
2026-09-01 sur https://www.nber.org/system/files/working_papers/w33601/w33601.pdf. Leur
échantillon court de juillet 1974 à juin 2024, la date de départ étant fixée par la
disponibilité des surprises de bénéfices.

Le résultat qui compte tient en trois nombres. QMJ rapporte 39 points de base par mois
(t 3,98) et un alpha à trois facteurs de 64 points de base (t 8,16). Contre le seul facteur
de rentabilité, son alpha tombe à **-1 point de base (t -0,11)**. Rentabilité et dérive
post-annonce expliquent conjointement plus de la moitié de sa variance, et QMJ charge deux
fois moins sur la dérive que sur la rentabilité. Autrement dit, un investisseur qui détient
déjà un facteur de rentabilité n'a rien à gagner à ajouter QMJ.

Ils ajoutent une objection de construction. QMJ combine quatre stratégies dont le bon
comportement en test rétrospectif était déjà publié. Ce sont la rentabilité de Novy-Marx
(2013), les régularisations de Sloan (1996), le momentum fondamental de Ball et Brown
(1968) et l'arbitrage de bêta de Black (1972). Obtenir un écart de rendement significatif en combinant
des stratégies à écart significatif ne surprend pas. Ils renvoient à Novy-Marx (2015) sur les
degrés de liberté d'une stratégie à signaux multiples.

**Une critique par héritage.** Le score de sûreté utilise le bêta de Frazzini et Pedersen.
Toutes les objections de Novy-Marx et Velikov (2022) à cet estimateur, dont l'identité qui
montre qu'il mélange bêta de marché et volatilité du titre, s'appliquent donc à la
composante de sûreté de QMJ. Voir la fiche `frazzini_pedersen_2014_bab.md`.

**Aucune réfutation publiée de la partie « prix de la qualité » n'a été trouvée au
2026-09-01.** Les recherches ont porté sur les échecs de réplication, l'exploration de
données et l'absorption par d'autres facteurs. La Review of Accounting Studies ne semble
pas avoir publié de commentaire de discutant accompagnant l'article, ce qui est courant dans
cette revue. Recherche menée le 2026-09-01. Le résultat négatif reste provisoire, faute
d'accès au sommaire du numéro.

## Les problèmes de réplication connus

**Les définitions de l'article publié diffèrent probablement de celles des versions de
travail, et c'est le point le plus grave de cette fiche.** Novy-Marx et Medhat (2025,
p. 7-8) décrivent le score de qualité de la version publiée comme la somme de cotes de
**trois** sous-composites, « profitability », « growth » et « safety », sans mentionner la
distribution. Ils décrivent la croissance comme la croissance sur cinq ans **par action**
des cinq premières mesures de rentabilité, chacune exprimée en revenu résiduel. Ils
énumèrent pour la sûreté le bêta faible, le levier faible, les deux cotes de faillite et la
faible volatilité des bénéfices, sans la volatilité idiosyncrasique.

Les versions de travail de 2013 et de 2014 disent autre chose. Elles donnent quatre
composites, une croissance en variation de numérateur sur dénominateur retardé, sans notion
par action ni revenu résiduel, et une volatilité idiosyncrasique présente dans la sûreté. Deux lectures sont
possibles, et rien dans les sources consultées ne permet de trancher. Soit les définitions
ont changé entre 2014 et la publication de 2018, soit Novy-Marx et Medhat résument
approximativement. **La réplication ne doit pas commencer avant que le texte publié ait été
lu.** Sans cela, ce sera une approximation présentée comme une réplication.

**Le résumé de l'article publié ne nomme que trois caractéristiques.** Récupéré le
2026-09-01 par l'interface d'OpenAlex, faute d'accès au texte, il annonce « profitability,
growth, and safety ». Celui de la version du 19 juin 2014 en annonce quatre, des titres
« safe, profitable, growing, and well managed ». Cela va dans le sens de la lecture
de Novy-Marx et Medhat. Un fait la contredit : la page de données d'AQR, consultée le
2026-09-01, définit encore la qualité par « profitability, growth, safety and payout ». La
question reste donc ouverte, et seul le texte publié la tranchera.

**Les 22 mesures annoncées contre les 21 définies.** Le corps du texte parle de 22 mesures
de qualité, l'annexe A1 en définit 21. Écart non résolu.

**La contradiction de dates sur l'échantillon mondial**, janvier 1986 dans le texte contre
juin 1986 dans les tableaux, doit être tranchée et déclarée.

**Le t de l'alpha à quatre facteurs américain**, 11,20 dans le texte contre 10,20 dans le
tableau VI. Un contrôle de réplication qui vise le mauvais des deux échouera pour la
mauvaise raison.

**Des coquilles de postes comptables dans l'annexe.** L'annexe A1 écrit `RETV` là où le
poste Compustat des ventes est `REVT`, et `NB` là où le résultat net est `IB` dans la
formule de flux de trésorerie sur actif. La lecture correcte se déduit du contexte, mais
une transcription mécanique produirait des variables vides.

**XpressFeed n'est pas gratuit.** La base Compustat Global, ex-XpressFeed, exige un
abonnement WRDS. Sans lui, l'échantillon mondial de 24 pays n'est pas reconstructible, et
seul le bloc américain via CRSP reste envisageable, lui-même payant. Un substitut public
devra être déclaré comme substitut, avec l'écart mesuré.

**AQR publie les rendements du facteur, pas ses composantes.** La page
`aqr.com/Insights/Datasets/Quality-Minus-Junk-Factors-Monthly`, consultée le 2026-09-01,
annonce les États-Unis et 23 marchés internationaux, un échantillon long américain à partir
de 1956 et un échantillon mondial à partir de 1986. Elle ne publie pas les définitions
détaillées des variables et renvoie à l'article. Elle est donc
une cible de réplication utilisable pour la série, pas pour le score.

**La volatilité des bénéfices a deux définitions selon les données disponibles**, sur
soixante trimestres ou sur cinq exercices annuels, la seconde s'appliquant à une partie de
l'échantillon international. Le mélange des deux dans une même cote transversale doit être
déclaré.

## Les biais possibles

**Le biais du survivant et la radiation.** Aucun rendement de radiation n'est disponible
hors des États-Unis, et la règle des -30 % de Shumway ne s'applique donc qu'au bloc
américain. Le sens de l'effet est prévisible : sans rendement de radiation, la jambe courte
en actions de rebut est flattée, donc le facteur est sous-estimé à l'international.

**La date d'entrée en vigueur des données comptables.** L'alignement de l'exercice clos en
\(t-1\) à juin de \(t\) est prudent, mais Compustat corrige rétroactivement les données
publiées. Une base non historisée expose à un biais d'anticipation qui ne se voit pas dans
les résultats. Le fait qu'aucune variable de la fiche ne porte de date de publication rend
ce biais invisible à tout test interne.

**Le nombre de degrés de liberté du score.** Vingt et une variables, quatre agrégations,
un choix de standardisation par rangs, un choix de coupures à 30 %. Les auteurs répondent
qu'ils prennent des mesures « off-the-shelf » pour éviter l'exploration de données, et que
la présence de nombreuses mesures rend leur constat de faible pouvoir explicatif d'autant
plus surprenant. C'est un argument sérieux pour la partie « prix » et faible pour la
partie « rendement », comme le soutiennent Novy-Marx et Medhat.

**La corrélation moyenne de 0,40 entre composantes n'est pas une preuve.** Les auteurs y
voient un appui à leur décision d'agréger. Elle est aussi compatible avec le fait que les
quatre composantes captent partiellement une même chose, la rentabilité, ce que la
régression de Novy-Marx et Medhat mesure directement.

**La pondération par la valeur masque le problème inverse de BAB.** Là où le facteur BAB
surcharge les micro-capitalisations, QMJ est pondéré par la valeur et charge négativement
la taille. Le risque de capacité est donc faible et le risque de concentration sur quelques
grandes valeurs est élevé, notamment dans les petits pays. Aucune mesure de concentration
n'est publiée dans les versions consultées.

**La volatilité idiosyncrasique saute le dernier jour de bourse**, ce qui est une précaution
contre l'autocorrélation d'ordre un des rendements. Ne pas la reproduire change la variable
sans que rien ne le signale.

## Nos décisions d'implémentation

non commencé au 2026-09-01

## Nos écarts avec l'article

non commencé au 2026-09-01

## Nos résultats

Étude `004_quality_minus_junk`, verdict **`EXPERIMENTAL`**, menée le 2026-09-02.

Le facteur publié se réplique, notre construction ne le reproduit pas, et
la cause est mesurée. Sur la fenêtre de l'article, 1957-07 à 2012-12, le facteur
QMJ d'AQR pour les États-Unis rend 0,347 % par mois contre 0,40 publié. Son
ratio de Sharpe vaut 0,559 contre 0,58, et son alpha à quatre facteurs 0,522 %
contre 0,66. Après publication, 2013-01 à 2026-06, la prime tombe à 0,168 % par mois
avec un t de 0,72, sans que la baisse soit significative, p = 0,286.

Notre facteur, bâti sur 21 variables et quatre composantes depuis les
fondamentaux point-in-time des jeux DERA de la SEC, corrèle 0,106 avec le
facteur publié sur 132 mois. La cause est l'univers : restreint aux grandes
capitalisations, il perd la charge de taille de -0,577 que porte le facteur
publié. Les dix portefeuilles de qualité restent pourtant ordonnés, du Sharpe
0,151 au premier décile à 1,093 au dixième. Statut mesuré, source
`studies/004_quality_minus_junk/results/`.

## Notre contrôle de robustesse

non commencé au 2026-09-01

## Références

- Asness, C. S., Frazzini, A. et Pedersen, L. H. (2019), « Quality minus junk », Review of
  Accounting Studies 24(1), p. 34-112. https://doi.org/10.1007/s11142-018-9470-2
  Version publiée non consultée. Versions de travail consultées :
  https://www.nhh.no/globalassets/departments/business-and-management-science/seminars/2015-fall/020915.pdf
  (19 juin 2014) et http://www.efalken.com/LowVolClassics/Asness_Frazzini_Pedersen_QMJ.pdf
  (9 octobre 2013). Notice : https://research.cbs.dk/en/publications/quality-minus-junk-2/
  Métadonnées de la version publiée (volume, pagination, licence CC BY) vérifiées sur
  Crossref, résumé publié récupéré sur OpenAlex, les deux le 2026-09-01.
- Novy-Marx, R. et Medhat, M. (2025), « Profitability Retrospective: What Have We
  Learned? », NBER Working Paper 33601.
  https://www.nber.org/system/files/working_papers/w33601/w33601.pdf
- Novy-Marx, R. et Velikov, M. (2022), « Betting against betting against beta », Journal of
  Financial Economics 143(1), p. 80-106. Porte sur l'estimateur de bêta employé dans le
  score de sûreté. https://mysimon.rochester.edu/novy-marx/research/BABAB.pdf
- Frazzini, A. et Pedersen, L. H. (2014), « Betting against beta », Journal of Financial
  Economics 111(1), p. 1-25. Fiche interne : `frazzini_pedersen_2014_bab.md`
- Novy-Marx, R. (2013), « The Other Side of Value: The Gross Profitability Premium »,
  Journal of Financial Economics. Cité par l'article, non consulté.
- Sloan, R. G. (1996), « Do Stock Prices Reflect Information in Accruals and Cash Flows
  About Future Earnings? », The Accounting Review 71, p. 289-315. Cité par l'article, non
  consulté.
- Ohlson, J. (1980) et Altman, E. (1968), sources des deux cotes de faillite du score de
  sûreté. Citées par l'annexe, non consultées.
- Shumway, T. (1997), source de la convention de -30 % sur les radiations liées à la
  performance. Citée par l'article, non consultée.
- Asness, C. et Frazzini, A. (2013), source des facteurs de comparaison et de la définition
  du rapport valeur comptable sur valeur de marché. Bibliothèque de données annoncée à
  http://www.econ.yale.edu/~af227/data_library.htm, non récupérée.
- AQR Capital Management, « Quality Minus Junk: Factors, Monthly », page consultée le
  2026-09-01. https://www.aqr.com/Insights/Datasets/Quality-Minus-Junk-Factors-Monthly

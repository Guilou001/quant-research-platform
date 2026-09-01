# Volatility-Managed Portfolios

| | |
|---|---|
| **Auteurs** | Alan Moreira, Tyler Muir |
| **Année** | 2017 |
| **Revue ou source** | The Journal of Finance, 72(4), 1611-1644, DOI 10.1111/jofi.12513 |
| **Lien** | Document de travail NBER 22208 : <https://www.nber.org/system/files/working_papers/w22208/w22208.pdf> ; page SSRN : <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2659431> ; version publiée : <https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12513> |
| **Statut de réplication** | non commencé |

Version publiée non consultée au 2026-09-01 : Wiley renvoie une erreur 403. Les chiffres ci-dessous
viennent du **document de travail NBER 22208, avril 2016**, dont l'échantillon s'arrête en 2015.
Aucun chiffre de la version publiée au Journal of Finance n'a été obtenu, ni directement ni par une
source tierce, et la fiche ne prétend nulle part en donner un.

## La question de recherche

Un investisseur qui réduit son exposition après un mois agité, et l'augmente après un mois calme,
gagne-t-il quelque chose ? La question paraît triviale et ne l'est pas, parce qu'elle oppose deux
faits établis.

Premier fait : la volatilité d'un facteur se prévoit très bien à un mois, sa valeur du mois passé
suffisant à prédire l'essentiel de celle du mois suivant. Second fait : les rendements attendus sont
élevés en récession et après les krachs, c'est-à-dire précisément quand la volatilité est haute.
Réduire le risque quand la volatilité monte revient donc à sortir quand la prime est censée être la
plus grosse. L'article mesure lequel des deux effets l'emporte.

## L'intuition économique

Le rendement existe parce que la volatilité est bien plus prévisible que le rendement attendu, à
l'horizon d'un mois. Le rapport rendement sur variance, ce que l'investisseur moyenne-variance
cherche à maximiser, se dégrade donc quand la variance monte, faute d'une hausse compensatrice de la
moyenne. La stratégie ne fait qu'exploiter cette dégradation.

Les auteurs le formalisent en une proportionnalité qui est le cœur de l'article :

\[ \alpha \propto -\mathrm{cov}\!\left(\frac{\mu_t}{\sigma^2_t},\ \sigma^2_t\right) \]

L'alpha est positif si et seulement si le prix du risque, le rapport \(\mu_t/\sigma^2_t\), baisse
quand la variance monte. Ce n'est pas une friction ni un biais de comportement : c'est une propriété
de la dynamique conjointe de la prime et de la variance, et elle contredit les modèles structurels.
Dans Campbell et Cochrane (1999) comme dans Bansal et Yaron (2004), l'aversion effective au risque
monte dans les mauvais états, donc \(\mu_t/\sigma^2_t\) monte avec la variance, et l'alpha simulé est
nul ou négatif. Les auteurs simulent quatre modèles, aux calibrations de leurs auteurs d'origine.
L'habitude de Campbell et Cochrane (1999), les catastrophes rares de Wachter (2013), le risque de
long terme de Bansal et Yaron (2004), les intermédiaires de He et Krishnamurthy (2012). Le meilleur
des quatre est celui de Bansal et Yaron. Il produit un alpha aussi élevé que celui des données dans
0,2 % des échantillons simulés, et les trois autres font pire.

Ce qui ferait disparaître le rendement. Trois extinctions, dans l'ordre de vraisemblance. Un, la
volatilité cesse d'être moins persistante que la prime. Les auteurs montrent par un vecteur
autorégressif qu'après un choc de variance, la variance monte d'abord bien plus que le rendement
attendu, puis retombe plus vite. L'investisseur moyenne-variance réduit son exposition d'environ
50 % après un choc d'un écart type. C'est cette différence de persistance qui fait tout, et les
alphas décroissent d'ailleurs quand on allonge la période de rééquilibrage. Deux, les coûts de
transaction montent avec la volatilité au point d'annuler le gain, ce que l'article teste et rejette
sous ses hypothèses. Trois, la relation risque-rendement s'inverse, hypothèse pour laquelle la
figure 1 ne donne aucun appui : la volatilité passée y prédit fortement la volatilité courante et
presque pas le rendement moyen.

## Les données

Uniquement des facteurs déjà construits et publics, aucune donnée de titre individuel.

| Facteur | Origine | Échantillon (version NBER) |
|---|---|---|
| Marché, taille, valeur | site de Kenneth French, Fama et French (1993) | 1926-2015 |
| Momentum | site de Kenneth French | 1926-2015 |
| Rentabilité, investissement | site de Kenneth French, modèle à cinq facteurs de Fama et French (2015) | 1963-2015 |
| Rentabilité sur fonds propres, investissement | Hou, Xue et Zhang, modèle q | 1967-2015 |
| Portage de change | Lustig, Roussanov et Verdelhan (2011), fourni par Adrien Verdelhan | 1983-2015 |

Le point qui décide de la reproductibilité : la variance conditionnelle est estimée sur les
**rendements quotidiens** de chaque facteur, alors que la stratégie est mensuelle. Les séries
quotidiennes de Kenneth French couvrent le marché, la taille, la valeur et le momentum. Pour le
portage de change, les auteurs déclarent construire la mesure de volatilité sur les variations
quotidiennes de taux de change des portefeuilles haut et bas. La série de rendements, elle, reste
mensuelle.

Cederburg, O'Doherty, Wang et Yan (2020) refont neuf facteurs qui ne sont pas tout à fait les mêmes.
Ils écartent le portage de change et lui substituent le facteur « parier contre le bêta » de Frazzini
et Pedersen (2014). Leurs échantillons débutent en août 1926 pour le marché, la taille et la valeur,
en janvier 1927 pour le momentum, en février 1931 pour « parier contre le bêta ». Ils débutent en
août 1963 pour la rentabilité et l'investissement de Fama et French, en février 1967 pour ceux de
Hou, Xue et Zhang. Tous se terminent en décembre 2016.

## L'univers

Neuf facteurs pris un par un dans le tableau 1, puis sept portefeuilles moyenne-variance efficients
dans le tableau 2. Aucun titre individuel, aucune sélection transversale : la stratégie ne modifie
jamais les poids relatifs à l'intérieur d'un facteur, elle ne fait varier que le bêta conditionnel
sur ce facteur.

L'annexe étend le résultat à 20 indices boursiers de pays de l'OCDE, sans que le document de travail
consulté en donne le détail chiffré dans le corps du texte.

## La méthodologie

Une seule formule, appliquée à chaque facteur, sans estimation de paramètre. Le portefeuille géré en
volatilité multiplie le facteur par l'inverse de sa variance réalisée du mois précédent, puis
normalise l'ensemble.

La normalisation est le détail qui a fait toute la controverse. La constante \(c\) est choisie pour
que le portefeuille géré ait **exactement le même écart type inconditionnel que le portefeuille
d'origine sur l'échantillon complet**. Les auteurs justifient ce choix par la lisibilité et
soulignent en note 5 que \(c\) n'affecte pas le ratio de Sharpe de la stratégie. C'est exact pour le
Sharpe, et c'est le point sur lequel les critiques reviendront pour tout le reste.

Le test est ensuite une régression de couverture, ce que la littérature appelle une régression
d'engendrement : le facteur géré est régressé sur le facteur d'origine, et l'intercepte est lu comme
un alpha. Un alpha positif signifie que l'ensemble des deux titres, géré et non géré, étend la
frontière moyenne-variance.

Quatre contrôles sont rapportés.

- Ajout des trois facteurs de Fama et French dans chaque régression, panneau B du tableau 1.
- Interaction avec un témoin de récession du NBER, tableau 3.
- Coûts de transaction à 1 point de base d'après Fleming, Kirby et Ostdiek (2003), puis à 10 points
  de base d'après Frazzini, Israel et Moskowitz (2015).
- Ajout de 4 points de base pour la hausse des coûts quand la volatilité implicite passe de 20 % à
  40 %, son 98e centile, tableau 4.

## Les équations qui comptent

Le portefeuille géré, équation (1) :

\[ f^{\sigma}_{t+1} = \frac{c}{\hat{\sigma}^2_t(f)}\, f_{t+1} \]

La variance réalisée du mois précédent, équation (2), somme sur les 22 jours de bourse du mois :

\[ \hat{\sigma}^2_t(f) = RV^2_t(f) = \sum_{d=1/22}^{1} \left( f_{t+d} - \frac{\sum_{d=1/22}^{1} f_{t+d}}{22} \right)^2 \]

La régression d'engendrement, équation (3) :

\[ f^{\sigma}_{t+1} = \alpha + \beta f_{t+1} + \epsilon_{t+1} \]

Le ratio d'appréciation, ou ratio de Sharpe additionnel, est \(\alpha / \sigma_\epsilon\), avec
\(\sigma_\epsilon\) l'écart type résiduel de cette régression. Le nouveau ratio de Sharpe atteignable
en combinant les deux titres :

\[ SR_{new} = \sqrt{SR_{old}^2 + \left(\frac{\alpha}{\sigma_\epsilon}\right)^2} \]

Le gain d'utilité pour un investisseur moyenne-variance, équation (4) :

\[ \Delta U_{MV}(\%) = \frac{SR^2_{new} - SR^2_{old}}{SR^2_{old}} \]

Enfin la proportionnalité qui donne le sens économique de l'alpha, déjà citée plus haut :
\(\alpha \propto -\mathrm{cov}(\mu_t/\sigma^2_t, \sigma^2_t)\).

## Les résultats originaux

**Alpha annualisé du marché : 4,86 % par an.** L'écart type vaut 1,56, le bêta 0,61 et l'erreur
quadratique moyenne 51,39 (tableau 1, colonne 1, document de travail NBER, échantillon 1926-2015). L'introduction du même document arrondit à 4,9 %. Cederburg et al. (2020)
réestiment la même régression sur août 1926 à décembre 2016 et trouvent 4,63 % ; c'est leur propre
estimation, pas la reprise d'un chiffre de la version publiée.

**Tableau 1, panneau A.** Alphas annualisés en pourcentage par an, écarts types entre parenthèses,
avec le bêta sur le facteur d'origine.

| Facteur | Bêta | Alpha | Écart type | N | R² | Erreur quadratique |
|---|---|---|---|---|---|---|
| Marché | 0,61 | **4,86** | (1,56) | 1 065 | 0,37 | 51,39 |
| Taille | 0,62 | **-0,58** | (0,91) | 1 065 | 0,38 | 30,44 |
| Valeur | 0,57 | 1,97 | (1,02) | 1 065 | 0,32 | 34,92 |
| Momentum | 0,47 | **12,51** | (1,71) | 1 060 | 0,22 | 50,37 |
| Rentabilité (RMW) | 0,62 | 2,44 | (0,83) | 621 | 0,38 | 20,16 |
| Investissement (CMA) | 0,68 | 0,38 | (0,67) | 621 | 0,46 | 17,55 |
| Portage de change | 0,71 | 2,78 | (1,49) | 360 | 0,33 | 25,34 |
| Rentabilité sur fonds propres (ROE) | 0,63 | 5,48 | (0,97) | 575 | 0,40 | 23,69 |
| Investissement (IA) | 0,68 | 1,55 | (0,67) | 575 | 0,47 | 16,58 |

Le facteur de taille est le seul dont l'alpha est négatif, et il n'est pas significatif. Trois autres
n'atteignent pas deux écarts types. Contrôle **mesuré** ce jour, en divisant chaque alpha par son
écart type : la valeur ressort à 1,93, le portage de change à 1,87 et l'investissement de Fama et
French à 0,57. Quatre colonnes sur neuf ne franchissent donc pas ce seuil. Le corps du texte annonce
pourtant des interceptes positifs et significatifs dans la plupart des cas.

**Ratios d'appréciation annualisés** cités page 8 du document de travail : marché 0,34, valeur 0,20,
rentabilité 0,41, portage de change 0,44, rentabilité sur fonds propres 0,80, investissement 0,32,
momentum 0,875.

Contrôle arithmétique **mesuré** ce jour depuis les valeurs du tableau 1 : avec \(\alpha = 4{,}86\)
et une erreur quadratique de 51,39, le ratio d'appréciation annualisé vaut
\(\sqrt{12} \times 4{,}86 / 51{,}39 = 0{,}328\), donc 0,33 et non 0,34. C'est bien la valeur 0,33 que
porte le tableau 2, et c'est aussi celle qu'annonce l'introduction du document de travail. Le 0,34
de la page 8 est donc isolé dans son propre texte.

Le cas du momentum ne se referme pas de la même façon. La page 8 pose le calcul en toutes lettres,
\(\sqrt{12} \times 12{,}5 / 50 = 0{,}875\). Or ce produit vaut 0,866, et les valeurs exactes du
tableau 1 donnent \(\sqrt{12} \times 12{,}51 / 50{,}37 = 0{,}860\). Ni l'arrondi ni les valeurs
exactes ne rendent le 0,875 imprimé. L'écart vaut neuf millièmes contre le calcul arrondi de
l'article et quinze contre les valeurs exactes. C'est sans effet sur la conclusion, mais une
réplication qui viserait 0,875 se croirait fausse.

**Tableau 2, panneau A.** Portefeuilles moyenne-variance efficients, alphas annualisés et ratios
d'appréciation.

| Ensemble de facteurs | Alpha | Écart type | Sharpe d'origine | Ratio d'appréciation |
|---|---|---|---|---|
| Marché seul | 4,86 | (1,56) | 0,42 | 0,33 |
| Fama-French 3 | 4,99 | (1,00) | 0,69 | 0,50 |
| Fama-French 3 + momentum | 4,04 | (0,57) | 1,09 | 0,69 |
| Fama-French 5 | 1,34 | (0,32) | 1,20 | 0,56 |
| Fama-French 5 + momentum | 2,01 | (0,39) | 1,42 | 0,77 |
| Hou-Xue-Zhang | 2,32 | (0,38) | 1,69 | 0,91 |
| Hou-Xue-Zhang + momentum | 2,51 | (0,44) | 1,73 | 0,91 |

**Tableau 2, panneau B, sous-périodes de trente ans.** Alpha du marché : 8,11 (3,09) sur 1926-1955,
2,06 (2,82) sur 1956-1985, 4,22 (1,66) sur 1986-2015. Le creux du milieu est reconnu par les auteurs
et attribué à une volatilité elle-même peu variable pendant ces trente années. Tous les points
estimés restent positifs, dans tous les ensembles de facteurs et toutes les sous-périodes.

**Gain d'utilité : 65 % de l'utilité à vie** pour un investisseur moyenne-variance qui n'a accès
qu'au marché, contre 35 % pour la synchronisation des rendements attendus chez Campbell et Thompson
(2008). Contrôle **mesuré** ce jour : l'équation (4) avec un Sharpe d'origine de 0,42 et un ratio
d'appréciation de 0,33 rend 61,7 %, et il faut 0,34 pour obtenir 65,5 %. Les 65 % annoncés
correspondent donc au 0,34 du texte, pas au 0,33 du tableau 2. L'écart est mineur et il est déclaré
ici parce qu'une réplication tombera dessus.

**Tableau 3, bêtas de récession.** Le bêta hors récession du marché géré vaut 0,83 et le coefficient
d'interaction avec le témoin de récession du NBER vaut -0,51. Le bêta conditionnel en récession
tombe donc à 0,32. Le signe est le même pour les huit facteurs testés.

**Cumul, figure 3.** Un dollar placé en 1926 vaut environ 20 000 $ en 2015 pour la stratégie gérée
en volatilité, contre environ 4 000 $ pour l'achat-conservation. Chiffres lus par les auteurs sur un
graphique à échelle logarithmique, donc à prendre comme ordre de grandeur.

**Prolongement des mêmes auteurs.** Moreira et Muir (2019), *Should Long-Term Investors Time
Volatility?*, Journal of Financial Economics, 131(3), 507-527. Un investisseur de long terme qui
ignore la variation de volatilité abandonne l'équivalent de **2,4 % de richesse par an**.

## Les critiques connues

Deux réfutations publiées visent nommément cet article, et une troisième publication leur répond en
défendant une version corrigée de la stratégie. La plus complète des deux réfutations conclut que le
gain disparaît en temps réel.

**Cederburg, O'Doherty, Wang et Yan (2020)**, *On the Performance of Volatility-Managed Portfolios*,
Journal of Financial Economics, 138(1), 95-117. Trois attaques, dans l'ordre où les auteurs les
posent.

*Un, la comparaison directe ne montre rien de systématique.* Neuf facteurs sont repris, sur des
échantillons prolongés jusqu'en décembre 2016, le portage de change cédant sa place à « parier
contre le bêta ». Écarts de ratio de Sharpe entre
version gérée et version d'origine, valeurs p des tests de Jobson et Korkie (1981) entre crochets.

| Facteur | Écart de Sharpe | Valeur p |
|---|---|---|
| Marché | +0,09 | [0,30] |
| Taille | -0,15 | [0,09] |
| Valeur | -0,02 | [0,86] |
| Momentum | **+0,50** | [0,00] |
| Rentabilité (RMW) | +0,13 | [0,29] |
| Investissement (CMA) | -0,13 | [0,23] |
| Rentabilité sur fonds propres (ROE) | **+0,32** | [0,01] |
| Investissement (IA) | -0,05 | [0,68] |
| Parier contre le bêta (BAB) | **+0,24** | [0,01] |

Trois gains significatifs sur neuf. Élargi à 103 stratégies actions, 53 écarts sont positifs et 50 négatifs,
dont 8 significativement positifs et 4 significativement négatifs à 5 %. La majorité des gains
significatifs vient des neuf stratégies de momentum, où la gestion en volatilité améliore les neuf.

*Deux, l'alpha de régression n'est pas exploitable en temps réel.* Le résultat de Moreira et Muir
est confirmé sur l'échantillon élargi : les alphas d'engendrement restent significativement
positifs. Mais l'alpha mesure la performance d'une combinaison des deux titres à poids
optimaux ex post, au sens de Gibbons, Ross et Shanken (1989). Ces poids ne sont pas connus avant la
fin de l'échantillon. Reconstruite hors échantillon avec une fenêtre d'apprentissage, la
combinaison marché géré plus marché d'origine rend un ratio de Sharpe annualisé de **0,42 contre
0,46** pour le seul marché non géré. Son équivalent certain est plus bas également. Sur les
103 stratégies, la combinaison en temps réel rend un équivalent certain plus faible dans **72 cas sur
103**. Aucune des variantes testées ne renverse le classement : fenêtres minimales différentes,
fenêtre glissante contre fenêtre croissante, aversions au risque différentes, contraintes d'effet de
levier différentes, ajout des trois facteurs de Fama et French.

*Trois, la cause est une instabilité structurelle.* Les paramètres des régressions d'engendrement
des portefeuilles gérés en volatilité changent de régime plus souvent que ceux des stratégies
d'anomalie ordinaires. Ce que l'investisseur estime sur le passé n'indique donc pas de façon fiable
la performance future du portefeuille géré relativement au portefeuille non géré.

Deux mesures accessoires de cet article méritent d'être retenues pour une réplication. La
corrélation entre version gérée et version d'origine va de 0,48 à 0,70 selon le facteur. Et le 99e
centile du poids exigé dépasse 400 % pour les neuf facteurs, et atteint **864 %** pour le momentum,
alors que le poids médian est d'environ 1. La stratégie demande donc un effet de levier extrême
quelques mois sur cent.

L'annexe internet de Cederburg et al. décompose l'alpha annualisé du marché, 4,63 % dans leur
échantillon, en deux parts. La relation entre volatilité retardée et rendement contribue pour
-0,24 %. La relation entre volatilité retardée et volatilité courante contribue pour +4,87 %. Autrement dit,
la persistance de la volatilité fait tout, et la prévision de rendement rien.

**Liu, Tang et Zhou (2019)**, *Volatility-Managed Portfolio: Does It Really Work?*, The Journal of
Portfolio Management, 46(1), 38-51. La constante \(c\) de l'équation (1) est calibrée sur l'écart
type de plein échantillon, donc sur une information indisponible à la date des transactions : c'est
un regard en avant. Une fois cette constante estimée en temps réel, la stratégie devient très
difficile à tenir, son pire recul cumulé atteignant **68 % à 93 %** dans presque tous les cas. Elle ne
bat le marché que pendant la crise financière. Trois définitions alternatives de la synchronisation
sur volatilité sont testées et aucune ne bat le marché non plus. Résumé lu le 2026-09-01 sur la page
de publication de la Washington University in St. Louis, la page SSRN renvoyant une erreur 403 ; le
texte complet n'a pas été consulté.

**Xu (2024)**, *Improving Volatility-Managed Portfolios in Real Time*, Critical Finance Review, à
paraître. C'est la contre-critique, et elle concède le point avant de le corriger. Xu reprend
explicitement le diagnostic de Liu et al. (2019) et de Cederburg et al. (2020) sur le regard en
avant de la constante de normalisation. Le texte propose une formation modifiée, avec
redimensionnement effectif du risque, rendement attendu conditionnel et intercepte tiré d'un
arbitrage risque-rendement conditionnel. Sur 197 facteurs et portefeuilles d'anomalies, il rapporte
**148 hausses de ratio de Sharpe et 165 rendements anormaux positifs** en temps réel, tenant sous
contraintes d'effet de levier et coûts de transaction. Chiffres lus le 2026-09-01 dans le résumé du
manuscrit du 30 mars 2024 déposé chez l'éditeur de la revue.

**Où en est le débat.** Les deux camps s'accordent sur les alphas en échantillon : personne ne
conteste le tableau 1 de Moreira et Muir. Le désaccord porte entièrement sur le passage de l'alpha à
un gain pour un investisseur qui n'aurait connu que le passé. Sur ce point, un fait n'est contesté
par personne : la gestion en volatilité du momentum fonctionne, dans les trois articles. C'était
déjà le résultat de Barroso et Santa-Clara (2015) et de Daniel et Moskowitz (2016).

## Les problèmes de réplication connus

1. **Le regard en avant de la constante \(c\)** est le problème central, et il est documenté par deux
   articles publiés. Les auteurs le savaient et l'ont écarté par un argument exact mais partiel : la
   constante n'affecte pas le ratio de Sharpe de la stratégie seule. Elle affecte tout le reste, à
   commencer par l'alpha, le bêta et les poids de portefeuille.
2. **La série quotidienne du portage de change** n'est pas publique. Les données de rendement de
   change viennent de Lustig, Roussanov et Verdelhan (2011) et les remerciements nomment Adrien
   Verdelhan parmi les fournisseurs. Sans cette série, la colonne du portage de change n'est pas
   reproductible.
3. **Les facteurs de Hou, Xue et Zhang** ne sont pas librement téléchargeables comme ceux de Kenneth
   French. Les remerciements citent Alexi Savov, Adrien Verdelhan et Lu Zhang comme fournisseurs de
   données, sans dire qui a fourni quoi.
4. **Le compte de jours dans l'équation (2)** est écrit comme une somme de \(d = 1/22\) à 1, avec 22
   au dénominateur de la moyenne. Or le nombre de jours de bourse d'un mois n'est pas constant. Le
   manuscrit consulté ne dit pas si le diviseur reste 22 ou suit le nombre réel de jours. Non trouvé
   dans le texte consulté.
5. **Le traitement des mois incomplets** au début de chaque échantillon n'est pas décrit.
6. **Le chiffre à viser n'est pas établi.** L'alpha du marché vaut 4,86 dans le document de travail
   de 2016, sur 1926-2015. Il vaut 4,63 dans la réestimation de Cederburg et al. sur août 1926 à décembre
   2016. Celui de la version publiée au Journal of Finance reste **non trouvé** au 2026-09-01. Une
   réplication doit choisir sa cible parmi les deux chiffres connus et le dire.

## Les biais possibles

**Regard en avant sur la normalisation.** Traité ci-dessus. C'est le biais principal, il est reconnu
et quantifié par la littérature critique.

**Alpha en échantillon lu comme un gain réalisable.** L'alpha de la régression (3) est
mathématiquement le gain d'une combinaison à poids optimaux, et ces poids se calculent sur tout
l'échantillon. Cederburg et al. montrent que la traduction en gain hors échantillon échoue dans 72
cas sur 103. Ce n'est pas un défaut de calcul de Moreira et Muir, c'est un défaut d'interprétation
de leur mesure.

**Effet de levier implicite non contraint.** Le 99e centile du poids dépasse 400 % pour les neuf
facteurs et atteint 864 % pour le momentum. L'article teste un plafonnement à 1 et à 1,5 dans son
tableau 4 sur les coûts de transaction, mais les alphas principaux du tableau 1 sont calculés sans
plafond.

**Facteurs sélectionnés après coup.** Les neuf facteurs retenus sont ceux que la littérature avait
déjà validés en 2016. L'élargissement à 103 stratégies par Cederburg et al. fait tomber la
proportion de succès à peu près à une sur deux, ce qui est la signature d'une sélection.

**Aucune correction pour tests multiples** dans l'article d'origine, ni sur les neuf facteurs, ni sur
les sept combinaisons du tableau 2, ni sur les trois sous-périodes.

**Estimation de la variance en échantillon.** L'annexe A.1 du document de travail annonce que des
modèles de prévision de variance plus élaborés améliorent le résultat. Un tel choix, fait après avoir
vu les résultats de la variance réalisée simple, est un degré de liberté supplémentaire.

## Nos décisions d'implémentation

non commencé au 2026-09-01

## Nos écarts avec l'article

non commencé au 2026-09-01

## Nos résultats

non commencé au 2026-09-01

## Notre contrôle de robustesse

non commencé au 2026-09-01

## Références

- Moreira, A. et Muir, T. (2017). Volatility-Managed Portfolios. *The Journal of Finance*, 72(4),
  1611-1644. DOI 10.1111/jofi.12513
- Moreira, A. et Muir, T. (2016). Volatility Managed Portfolios. *NBER Working Paper* 22208.
  <https://www.nber.org/papers/w22208>
- Moreira, A. et Muir, T. (2019). Should Long-Term Investors Time Volatility? *Journal of Financial
  Economics*, 131(3), 507-527.
- Cederburg, S., O'Doherty, M. S., Wang, F. et Yan, X. S. (2020). On the Performance of
  Volatility-Managed Portfolios. *Journal of Financial Economics*, 138(1), 95-117. DOI
  10.1016/j.jfineco.2020.04.015. Version accessible : <https://www.lehigh.edu/~xuy219/research/COWY.pdf>
- Liu, F., Tang, X. et Zhou, G. (2019). Volatility-Managed Portfolio: Does It Really Work? *The
  Journal of Portfolio Management*, 46(1), 38-51.
- Xu, X. (2024). Improving Volatility-Managed Portfolios in Real Time. *Critical Finance Review*, à
  paraître. <https://cfr.ivo-welch.org/forthcoming/papers/xu2024improving.pdf>
- Barroso, P. et Santa-Clara, P. (2015). Momentum Has Its Moments. *Journal of Financial Economics*,
  116(1), 111-120.
- Daniel, K. et Moskowitz, T. J. (2016). Momentum Crashes. *Journal of Financial Economics*, 122(2),
  221-247.
- Jobson, J. D. et Korkie, B. M. (1981). Performance Hypothesis Testing with the Sharpe and Treynor
  Measures. *The Journal of Finance*, 36, 889-908. Test de l'égalité de deux ratios de Sharpe,
  utilisé par Cederburg et al.
- Gibbons, M. R., Ross, S. A. et Shanken, J. (1989). A Test of the Efficiency of a Given Portfolio.
  *Econometrica*, 57(5), 1121-1152. Base de l'argument des poids optimaux ex post. La bibliographie
  de Cederburg et al. imprime « 87 » pour le volume, ce qui est une coquille.
- Campbell, J. Y. et Thompson, S. B. (2008). Predicting Excess Stock Returns Out of Sample: Can
  Anything Beat the Historical Average? *Review of Financial Studies*, 21(4), 1509-1531. Repère du
  gain d'utilité de 35 %, cité par Moreira et Muir.
- Fleming, J., Kirby, C. et Ostdiek, B. (2003). The Economic Value of Volatility Timing Using
  Realized Volatility. *Journal of Financial Economics*, 67(3), 473-509. Source du coût de
  transaction d'un point de base du tableau 4.
- Frazzini, A., Israel, R. et Moskowitz, T. (2015). Trading Costs of Asset Pricing Anomalies.
  Document de travail. Source des dix points de base et de la pente du coût sur le VIX.
- Lustig, H., Roussanov, N. et Verdelhan, A. (2011). Common Risk Factors in Currency Markets.
  *Review of Financial Studies*. Source du facteur de portage de change. Volume et pagination **non
  trouvés** : le document de travail cite l'article avant sa pagination définitive, sous la forme
  « page hhr068 ».

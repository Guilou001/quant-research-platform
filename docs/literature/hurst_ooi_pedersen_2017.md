# A Century of Evidence on Trend-Following Investing

| | |
|---|---|
| **Auteurs** | Brian Hurst, Yao Hua Ooi, Lasse Heje Pedersen |
| **Année** | 2017 |
| **Revue ou source** | The Journal of Portfolio Management, vol. 44, n° 1, p. 15-29 (DOI 10.3905/jpm.2017.44.1.015) |
| **Lien** | Manuscrit accepté, portant la mention « Electronic copy available at: https://ssrn.com/abstract=2993026 », consulté le 2026-09-01 à l'adresse [static.twentyoverten.com](https://static.twentyoverten.com/593e8a9e7299b471eaecf644/SkLoGL67M/A-Century-of-Evidence-on-Trend-Following-Investing.pdf). Version blanche AQR d'automne 2014, échantillon 1880-2013, consultée à l'adresse [trendfollowing.com](https://www.trendfollowing.com/whitepaper/Century_Evidence_Trend_Following.pdf) |
| **Statut de réplication** | non commencé |

## La question de recherche

La rentabilité du suivi de tendance depuis 1985 est-elle un accident d'échantillon ?
Moskowitz, Ooi et Pedersen (2012) avaient documenté le momentum de série temporelle,
c'est-à-dire l'achat de ce qui a monté et la vente de ce qui a baissé, sur des données
commençant en 1985. Trois décennies suffisent à produire un résultat par hasard quand
des centaines de règles sont testées. Les auteurs remontent donc à 1880, ce qui ajoute
dix décennies entièrement hors échantillon par rapport à la littérature existante.

La question secondaire, et celle qui intéresse un praticien : que reste-t-il après les
coûts de transaction et les honoraires réellement facturés par les gérants de contrats à
terme ?

## L'intuition économique

Le suivi de tendance devrait rapporter parce que les prix intègrent l'information
lentement, et parce qu'une partie des ordres qui circulent ne cherche pas le profit.
Les auteurs nomment deux mécanismes, et n'en testent aucun.

Le premier est comportemental : ancrage et grégarisme, c'est-à-dire l'attachement à un
prix de référence et l'imitation des autres opérateurs, retardent l'ajustement du prix à
une nouvelle. Le prix bouge alors par étapes, ce qui crée la tendance. Les auteurs
renvoient à Barberis, Shleifer et Vishny (1998), à Daniel, Hirshleifer et
Subrahmanyam (1998) et à De Long et al. (1990). Ils renvoient aussi à Hong et
Stein (1999) et à Frazzini (2006), sans les tester (p. 6 du manuscrit).

Le second est institutionnel, et c'est le plus concret : des participants qui ne
cherchent pas le profit interviennent sur les prix. Une banque centrale qui achète sa
devise pour amortir sa volatilité ralentit l'incorporation de l'information dans le
prix, donc fabrique une tendance dont un tiers peut tirer un rendement. Un programme de
couverture d'entreprise fait de même sur les matières premières. Le rendement du suivi
de tendance est alors le prix payé par ces intervenants pour un service qu'ils
achètent, la stabilité ou l'assurance.

Ce qui ferait disparaître ce rendement est mesuré dans l'article, et ce n'est pas ce
qu'on attend. Ce n'est pas la concurrence : les auteurs testent la performance par
régime et trouvent que la variable qui compte le plus est la corrélation moyenne entre
marchés. Quand cette corrélation est dans son quintile le plus bas, le ratio de Sharpe
vaut 1,54, brut d'honoraires et net de coûts ; dans le quintile le plus haut, 0,67. Avec l'indicateur retardé
d'un mois, donc utilisable en pratique, la relation est monotone d'un bout à l'autre :
1,61, 1,29, 0,93, 0,69, 0,57 (exhibit 10, rapporté). L'explication des auteurs est
mécanique. La cible de volatilité de portefeuille étant fixe, une corrélation élevée
force à réduire toutes les positions, donc à parier moins. Autrement dit, quand tout
bouge ensemble, il y a moins de tendances réellement distinctes sur lesquelles miser.

Reste l'objection la plus forte, et elle est de méthode. Le mécanisme ci-dessus explique
pourquoi la stratégie gagne, mais l'article ne teste jamais le mécanisme lui-même. Il
teste la performance d'une règle. Un rendement positif sur 137 ans est compatible avec
le mécanisme annoncé et avec plusieurs autres, dont la prime de risque payée pour porter
des positions qu'il faut liquider aux pires moments.

## Les données

L'apport propre de l'article est une base de prix quotidiens de contrats à terme sur
matières premières, transcrite à la main. La source est le « Annual Report of the Trade
and Commerce of the Chicago Board of Trade », et elle remonte jusqu'à 1877. La
transcription s'arrête en 1951, où les bases électroniques prennent le relais (p. 3 du
manuscrit).

Trois règles de construction gouvernent le reste.

- Les rendements de contrats à terme sont simulés en détenant puis en roulant l'un des
  contrats les plus liquides. Le roulement enregistre les deux prix, celui du contrat
  vendu et celui du contrat acheté.
- Les prix de clôture sont utilisés quand ils existent. Sur la partie ancienne de
  l'échantillon, seuls les plus hauts et les plus bas sont disponibles, et les auteurs
  prennent leur moyenne.
- Hors matières premières, avant l'existence des contrats à terme, les auteurs
  substituent les rendements d'indices au comptant financés au taux court local de
  chaque pays.

L'échantillon travaille en fréquence mensuelle, sur des prix et rendements de fin de
mois. La stratégie exige trois ans d'historique pour estimer les volatilités, donc les
rendements simulés commencent en 1880 alors que les prix commencent en 1877.

Les auteurs déclarent ne pas prétendre que la stratégie aurait été implémentable telle
quelle dans les années 1880. Ni les marchés de financement modernes, ni les contrats à
terme sur indices actions et sur obligations n'existaient alors. Ces derniers sont
simulés, et la note 6 du manuscrit le dit.

## L'univers

67 marchés, répartis en quatre classes d'actifs : 29 matières premières, 11 indices
actions, 15 marchés obligataires et 12 paires de devises (p. 3 du manuscrit).

Tous les 67 ne sont pas disponibles à chaque date. La stratégie est construite sur
l'ensemble des actifs dont les données existent à l'instant considéré, ce qui fait varier
le nombre de positions au cours du temps. L'annexe A de l'article donne la disponibilité
et la source de chaque marché par période ; elle n'a pas été dépouillée marché par marché
au 2026-09-01.

Le nombre de marchés est identique dans la version d'automne 2014 et dans la version
publiée en 2017, y compris la ventilation en 29, 11, 15 et 12.

## La méthodologie

**Le signal.** Combinaison à poids égaux de trois momentums de série temporelle, à
un mois, trois mois et douze mois. Pour chaque horizon, un rendement excédentaire passé
positif donne une position longue, un rendement négatif une position courte. Chaque
sous-stratégie est donc toujours investie, longue ou courte, dans chaque marché. Il n'y
a pas de position neutre.

**Le dimensionnement.** Chaque position vise le même montant de volatilité, pour
diversifier et pour borner la contribution d'un marché unique. Les positions des trois
horizons sont agrégées chaque mois, puis mises à l'échelle pour que le portefeuille
combiné vise une volatilité annualisée ex ante de 10 %. La matrice de covariance
utilisée pour cette mise à l'échelle est estimée sur trois ans glissants de rendements
mensuels, à poids égaux (note 7 du manuscrit).

**Le rééquilibrage** est mensuel.

**Les coûts.** Les coûts de transaction sont soustraits, puis les honoraires. Le détail
figure ci-dessous, section « Les résultats originaux ».

**Ce que la méthodologie ne dit pas.** La constante qui fixe la volatilité visée par
marché n'est pas publiée dans cet article. Les auteurs renvoient à Moskowitz, Ooi et
Pedersen (2012) et à Hurst, Ooi et Pedersen (2013) pour la méthodologie. Valeur non
trouvée dans les deux versions consultées au 2026-09-01.

## Les équations qui comptent

L'article ne contient aucune équation numérotée. La règle est énoncée en prose. Ce qui
suit est une transcription, à vérifier contre Moskowitz, Ooi et Pedersen (2012) avant
toute implémentation.

Le signal de l'horizon \(h\), pour le marché \(i\) à la fin du mois \(t\), est le signe du
rendement excédentaire cumulé sur les \(h\) derniers mois :

\[
s^{h}_{i,t} = \operatorname{signe}\!\left( r^{e}_{i,t-h+1 \to t} \right), \qquad h \in \{1, 3, 12\}
\]

La position agrégée pondère les trois horizons également et vise une volatilité égale par
marché, d'où une division par la volatilité estimée \(\hat{\sigma}_{i,t}\) :

\[
w_{i,t} \;\propto\; \frac{1}{3}\sum_{h \in \{1,3,12\}} s^{h}_{i,t} \cdot \frac{1}{\hat{\sigma}_{i,t}}
\]

Le portefeuille entier est ensuite multiplié par un scalaire \(k_t\) qui amène sa
volatilité ex ante à la cible de 10 % :

\[
k_t = \frac{0{,}10}{\sqrt{\mathbf{w}_t^{\top}\,\hat{\Sigma}_t\,\mathbf{w}_t}}
\]

où \(\hat{\Sigma}_t\) est la matrice de covariance des trois dernières années de
rendements mensuels, à poids égaux. C'est ce scalaire qui fait que la stratégie parie
moins quand les corrélations montent, et donc c'est lui qui produit le résultat par
quintile de corrélation cité plus haut.

## Les résultats originaux

Tous les chiffres de cette section sont **rapportés**, lus dans le manuscrit accepté
consulté le 2026-09-01. Aucun n'a été recalculé.

### La période, les rendements et le ratio de Sharpe

Période exacte : de janvier 1880 à décembre 2016, soit 137 ans. Les rendements de
l'exhibit 1 sont des rendements excédentaires, c'est-à-dire nets du taux sans risque.

| Grandeur, plein échantillon 01/1880 à 12/2016 | Valeur |
|---|---|
| Rendement excédentaire annualisé, brut d'honoraires et brut de coûts | 18,0 % |
| Rendement excédentaire annualisé, brut d'honoraires et net de coûts | 11,0 % |
| Rendement excédentaire annualisé, net des honoraires 2 et 20 et net de coûts | 7,3 % |
| Volatilité réalisée annualisée | 9,7 % |
| Ratio de Sharpe, net d'honoraires et de coûts | 0,76 |
| Corrélation au marché actions américain | -0,01 |
| Corrélation aux obligations américaines à dix ans | -0,03 |

Le ratio de Sharpe brut n'est pas donné directement dans l'exhibit 1. Le rapport 18,0 sur
9,7 donne 1,86, et 11,0 sur 9,7 donne 1,13. Ces deux quotients sont **modélisés** à partir
des colonnes publiées, la volatilité publiée étant celle de la série nette.

Le texte donne un second chiffre, marché par marché. La stratégie a un rendement moyen
positif dans chacun des 67 marchés pris isolément. Le ratio de Sharpe moyen y vaut
environ 0,4, brut d'honoraires et brut de coûts (p. 7 du manuscrit, exhibit 3).

### Décennie par décennie

Le résultat central de l'article est qu'aucune décennie n'est perdante.

| Décennie | Brut de tout | Net de coûts | Net de 2 et 20 et de coûts | Volatilité | Sharpe net | Corr. actions | Corr. obligations |
|---|---|---|---|---|---|---|---|
| 1880-1889 | 12,1 % | 5,2 % | 2,6 % | 9,5 % | 0,27 | -0,11 | -0,04 |
| 1890-1899 | 17,4 % | 10,0 % | 6,5 % | 8,9 % | 0,73 | -0,02 | -0,15 |
| 1900-1909 | 15,3 % | 6,0 % | 3,3 % | 9,5 % | 0,34 | 0,02 | -0,35 |
| 1910-1919 | 12,5 % | 4,1 % | 1,6 % | 12,6 % | 0,13 | 0,12 | -0,01 |
| 1920-1929 | 20,8 % | 13,3 % | 9,2 % | 8,5 % | 1,09 | 0,15 | 0,06 |
| 1930-1939 | 15,4 % | 9,8 % | 6,3 % | 8,6 % | 0,74 | -0,11 | 0,20 |
| 1940-1949 | 23,8 % | 14,8 % | 10,4 % | 10,6 % | 0,99 | 0,33 | 0,31 |
| 1950-1959 | 26,7 % | 17,6 % | 13,1 % | 9,1 % | 1,45 | 0,23 | -0,19 |
| 1960-1969 | 21,0 % | 9,5 % | 6,0 % | 10,9 % | 0,56 | -0,09 | -0,37 |
| 1970-1979 | 27,4 % | 20,5 % | 15,1 % | 8,9 % | 1,70 | -0,24 | -0,25 |
| 1980-1989 | 20,1 % | 13,3 % | 9,1 % | 9,4 % | 0,96 | 0,18 | -0,16 |
| 1990-1999 | 16,8 % | 12,3 % | 8,3 % | 8,4 % | 0,98 | 0,01 | 0,21 |
| 2000-2009 | 11,6 % | 9,9 % | 6,3 % | 10,3 % | 0,61 | -0,34 | 0,27 |
| 2010-2016 | 7,6 % | 6,2 % | 3,3 % | 8,1 % | 0,41 | -0,15 | 0,28 |

La meilleure décennie est celle des années 1970, avec un Sharpe net de 1,70, ce qui
contredit l'idée que la stratégie aurait vécu de la baisse séculaire des taux. La pire
est celle des années 1910, à 0,13. La dernière période, incomplète, arrive au quatrième
rang le plus bas des quatorze, à 0,41, derrière 0,13, 0,27 et 0,34.

### La structure de coûts supposée

Deux couches se soustraient, et il faut les tenir séparées.

**Couche 1, les coûts de transaction.** Estimations propriétaires d'AQR faites en 2012,
incluant l'impact de marché et les commissions, exprimées en pourcentage du notionnel
échangé, à sens unique. Les coûts sont supposés deux fois plus élevés de 1993 à 2002 et
six fois plus élevés de 1880 à 1992, en s'appuyant sur Jones (2002).

| Classe d'actif | 1880-1992 | 1993-2002 | 2003-2016 |
|---|---|---|---|
| Actions | 0,34 % | 0,11 % | 0,06 % |
| Obligations | 0,06 % | 0,02 % | 0,01 % |
| Matières premières | 0,58 % | 0,19 % | 0,10 % |
| Devises | 0,18 % | 0,06 % | 0,03 % |

Les auteurs écrivent que ces coûts sont estimés avec une incertitude significative et
qu'ils n'incluent pas d'autres coûts possibles, notamment le coût de roulement des
contrats à terme (annexe B).

**Couche 2, les honoraires.** 2 % de frais de gestion annuels et 20 % de commission de
performance, cette dernière calculée et provisionnée mensuellement mais soumise à un
seuil de haute mer annuel. Concrètement, la commission de performance n'est prélevée une
année donnée que si la valeur liquidative de fin d'année dépasse toutes les valeurs
liquidatives de fin d'année antérieures.

Le poids de chaque couche se lit dans le tableau du plein échantillon. Les coûts de
transaction retirent 7,0 points de rendement annualisé, de 18,0 % à 11,0 %. Les
honoraires en retirent 3,7 de plus, de 11,0 % à 7,3 %. Les coûts pèsent donc près de
deux fois les honoraires, et ils sont les moins bien connus des deux.

### Le retard d'un mois, le contrôle qui fait mal

L'exhibit 2 donne le ratio de Sharpe brut de coûts et d'honoraires par horizon de signal,
puis le même signal appliqué avec un mois de retard.

| Horizon | Sans retard | Avec un mois de retard |
|---|---|---|
| 1 mois | 1,38 | 0,45 |
| 3 mois | 1,19 | 0,64 |
| 12 mois | 1,32 | 1,04 |

Le signal à un mois perd les deux tiers de son ratio de Sharpe quand on attend un mois
pour l'exécuter. Le signal à douze mois n'en perd que le cinquième. Toute réplication qui
introduit un décalage d'exécution doit donc s'attendre à un résultat très différent selon
l'horizon. Le poids d'un tiers accordé au signal à un mois est le point le plus fragile
de la construction.

### Le comportement en crise

La stratégie est positive dans 8 des 10 plus fortes baisses pic à creux d'un portefeuille
60/40 américain sur 1880-2016. L'explication avancée est de durée. La baisse moyenne pic
à creux de ces dix épisodes dure environ 15 mois. Le suiveur de tendance a donc le temps
de se retourner à la vente après le premier décrochage. Les auteurs notent
l'exception symétrique, un krach très rapide comme celui de 1987, où la stratégie n'a pas
le temps de se positionner.

Allocation de 20 % d'un portefeuille 60/40 vers la stratégie, exhibit 7 :

| Portefeuille | Rendement excédentaire annualisé | Volatilité annualisée | Pire baisse | Ratio de Sharpe |
|---|---|---|---|---|
| 60/40 | 4,1 % | 10,7 % | -62,3 % | 0,39 |
| 80 % de 60/40 et 20 % de suivi de tendance | 4,8 % | 8,7 % | -50,2 % | 0,55 |

Le 60/40 est pris brut d'honoraires et de coûts, la part de suivi de tendance nette des
deux, ce qui rend la comparaison conservatrice.

### Les pires baisses de la stratégie elle-même

L'exhibit 8, calculé brut d'honoraires et net de coûts, donne une pire baisse de -24,7 %,
d'août 1947 à décembre 1948, récupérée en février 1951. La septième du classement,
-16,1 % de mars 2015 à mai 2016, n'était pas récupérée à la fin de l'échantillon. La
stratégie perd donc jusqu'à un quart de sa valeur, sur des périodes qui se comptent en
années.

## Les critiques connues

**Le momentum de série temporelle n'est peut-être pas là.** Huang, Li, Wang et Zhou,
« Time series momentum: is it there? », Journal of Financial Economics, vol. 135, n° 3,
2020, p. 774-794, DOI 10.1016/j.jfineco.2019.08.004, régressent actif par actif et ne
trouvent presque rien, en échantillon comme hors échantillon. Le t de Student de la
régression groupée paraît grand mais reste sous les valeurs critiques de rééchantillonnages
paramétrique et non paramétrique. Leur conclusion sur le volet investissement est la plus
gênante pour l'article de Hurst. La stratégie reste rentable, mais sa performance est
pratiquement identique à celle d'une stratégie fondée sur la simple moyenne historique de
l'échantillon. Ces trois affirmations viennent du résumé publié, lu le 2026-09-01 ;
métadonnées confirmées par Crossref, texte intégral non consulté.

**La performance vient de la mise à l'échelle par la volatilité, pas du signe.** Kim, Tse
et Wald, « Time series momentum and volatility scaling », Journal of Financial Markets,
vol. 30, 2016, p. 103-124, DOI 10.1016/j.finmar.2016.05.003. Ces auteurs montrent que les
alphas de Moskowitz, Ooi et Pedersen (2012) tiennent surtout à la division par la volatilité. Sans cette division, le momentum de série temporelle et un simple achat et
conservation donnent des rendements cumulés voisins, et leurs alphas ne diffèrent pas
significativement. Cette critique porte directement sur la construction de Hurst, Ooi et
Pedersen, qui utilise la même mise à l'échelle. Affirmations lues dans le résumé publié
le 2026-09-01 ; métadonnées confirmées par Crossref, texte intégral non consulté.

**La stratégie de série temporelle n'est pas neutre au marché, et c'est là que naît son
avantage apparent.** Goyal et Jegadeesh, « Cross-sectional and time-series tests of return
predictability: what is the difference? », The Review of Financial Studies, vol. 31, n° 5,
2018, p. 1784-1824, DOI 10.1093/rfs/hhx131, opposent les deux familles de tests. Une
stratégie transversale est à investissement net nul, alors qu'une stratégie de série
temporelle porte une position nette longue variable en actifs risqués. Sur actions
individuelles, l'écart de performance entre les deux vient surtout de cette position nette
longue. La stratégie de Hurst, Ooi et Pedersen est de série temporelle et porte donc la
même position nette variable. Affirmations lues dans le résumé publié le 2026-09-01 ;
métadonnées confirmées par Crossref, texte intégral non consulté.

**Le choix des estimateurs de volatilité et des règles de négociation change le
résultat.** Baltas et Kosowski, « Demystifying time-series momentum strategies:
volatility estimators, trading rules and pairwise correlations ». Repris en 2020 comme
chapitre 3 de l'ouvrage « Market Momentum », p. 30-67, DOI 10.1002/9781119599364.ch3.
Référence vérifiée par Crossref ; chapitre non consulté. Elle est citée par Hurst, Ooi et
Pedersen eux-mêmes dans leur bibliographie.

**Le pêchage de données dans le suivi de tendance en général.** Zakamulin (2014) vise les
règles de temporisation de marché, moyennes mobiles et momentum de série temporelle. Leur
performance publiée porte selon lui un biais de pêchage de données considérable et ignore
des frictions de marché. Ses propres tests hors échantillon, coûts de transaction compris,
la trouvent surestimée. Ses travaux ne visent pas cet article. Métadonnées confirmées par
Crossref le 2026-09-01, conclusion lue dans le résumé publié, texte intégral non consulté.

**Aucune réfutation publiée visant nommément cet article n'a été trouvée au 2026-09-01.**
Les cinq critiques ci-dessus visent la famille de résultats, pas le papier. La recherche
a porté sur les moteurs de recherche généralistes et sur Crossref, pas sur une base
bibliographique payante.

**La critique interne la plus solide est dans l'article même.** Sa dernière période,
2010-2016, affiche 0,41 de ratio de Sharpe net, quatrième valeur la plus basse des
quatorze, et son signal à un mois y tombe à 0,06 brut. Les auteurs signalent le fait sans en tirer de
conclusion sur la disparition de l'effet.

## Les problèmes de réplication connus

**Les données de la partie ancienne n'existent nulle part ailleurs.** La base de prix de
contrats à terme sur matières premières transcrite à la main depuis les rapports annuels
du Chicago Board of Trade est la contribution propre des auteurs. Elle n'est pas
diffusée. Reconstruire 1877-1951 exigerait de refaire la transcription depuis des
documents d'archive. C'est le blocage principal, et il est absolu pour la période
d'avant-guerre.

**Les coûts de transaction sont propriétaires.** L'exhibit B1 donne les niveaux, ce qui
suffit à reproduire l'ordre de grandeur, mais leur origine est une estimation interne
d'AQR de 2012, non auditable. Les multiplicateurs historiques de deux et de six viennent
de Jones (2002), qui porte sur les actions américaines, et sont appliqués aux quatre
classes d'actifs.

**Les deux versions publiques ne donnent pas les mêmes nombres.** La version d'automne
2014, sur 1880-2013, affiche 14,9 % brut d'honoraires, 11,2 % net de 2 et 20, une
volatilité de 9,7 % et un Sharpe net de 0,77. La version publiée en 2017, sur 1880-2016,
affiche 11,0 % brut d'honoraires et net de coûts, puis 7,3 % net de tout. La volatilité
y est la même, 9,7 %, et le Sharpe net vaut 0,76. Sur le plein échantillon, l'écart entre
les deux versions vaut 3,9 points sur les deux lignes de rendement. C'est cohérent avec un
passage des rendements totaux aux rendements excédentaires du taux sans risque. Deux
mesures le corroborent, calculées ici en confrontant les deux tables publiées. D'abord,
l'écart n'est pas constant d'une décennie à l'autre : 0,6 point sur les années 1930 et
1940, 8,7 points sur les années 1980, donc il suit le niveau du taux court. Ensuite, les
ratios de Sharpe nets sont identiques dans les deux versions pour les douze décennies
comparables. Cela n'est possible que si la version de 2014 calculait déjà son ratio sur des
rendements excédentaires tout en affichant des rendements totaux. La version 2017
précise « excess returns », la version 2014 ne le précise pas, et aucun des deux textes
n'énonce la différence. Une réplication qui viserait 14,9 % en croyant viser la même
grandeur que 11,0 % se tromperait de convention.

**Les valeurs de la table des pires baisses diffèrent aussi entre les deux versions.** La
version 2014 donne -26,3 % pour la première, calculée sur rendements nets d'honoraires ;
la version 2017 donne -24,7 %, calculée brut d'honoraires et net de coûts. Le classement
lui-même change de rang. Toute cible de réplication doit nommer sa version.

**La section sur la capacité n'existe que dans la version 2014.** Celle-ci cite une
estimation BarclayHedge des actifs gérés en suivi de tendance systématique, de
22 milliards de dollars en 1999 à plus de 280 milliards en 2014. Elle donne aussi la part
des marchés sous-jacents occupée par ces gérants : 0,2 % en actions, 2,3 % en obligations,
5,8 % en matières premières, 0,4 % en devises. Rien de tout cela n'est dans le manuscrit
accepté de 2017. Le terme « BarclayHedge » n'y apparaît pas, vérifié par recherche
textuelle le 2026-09-01.

**Ce qui est reproductible sans données propriétaires.** La partie moderne, à partir des
années 1980, repose sur des contrats à terme dont les prix sont disponibles chez des
fournisseurs commerciaux courants. Une réplication honnête consisterait à refaire
1985-2026 et à comparer aux décennies publiées, en déclarant que 1880-1984 est hors
d'atteinte.

## Les biais possibles

**Simulation d'instruments qui n'existaient pas.** Les contrats à terme sur indices
actions et sur obligations sont simulés sur toute la partie ancienne, à partir d'indices
au comptant financés au taux court. Les auteurs le déclarent (note 6). Cela veut dire que
les rendements d'avant les années 1980 sur deux des quatre classes ne portent aucune
information sur la liquidité réelle, l'écart acheteur-vendeur ou la possibilité de vendre
à découvert. Or la stratégie est courte la moitié du temps.

**Prix moyens plutôt que prix de clôture.** Sur la partie ancienne, faute de clôtures,
les auteurs utilisent la moyenne du plus haut et du plus bas. Une moyenne haut-bas lisse
la série par rapport à une clôture, et une série lissée porte mécaniquement plus
d'autocorrélation, donc plus de tendance apparente. Les auteurs ne mesurent pas cet
effet, et il travaille dans le sens de leur résultat.

**Coûts d'aujourd'hui projetés vers hier par un facteur unique.** Multiplier par six les
coûts de 2012 pour couvrir 1880-1992 est une hypothèse forte sur 113 ans, calibrée sur
une étude d'actions américaines. Si le vrai facteur ancien était de douze, la rentabilité
des premières décennies s'effondrerait. L'article ne publie pas de sensibilité à ce
paramètre.

**Le coût de roulement est absent.** Les auteurs l'écrivent. Sur 29 matières premières
roulées chaque mois pendant 137 ans, ce coût n'est pas un détail.

**Univers rétrospectif.** Les 67 marchés sont ceux qui existent et sont négociables
aujourd'hui. Les marchés à terme disparus, ou ceux dont l'histoire est trop lacunaire
pour entrer dans l'échantillon, ne sont pas là. Ce biais de sélection des instruments
n'est pas traité dans l'article.

**Conflit d'intérêts déclaré.** Les trois auteurs sont à AQR, qui commercialise des
stratégies de suivi de tendance. La performance présentée est déclarée hypothétique et
simulée à chaque exhibit. Le fait est déclaré, il n'invalide rien, il indique où chercher
les contrôles manquants.

## Nos décisions d'implémentation

Non commencé au 2026-09-01.

## Nos écarts avec l'article

Non commencé au 2026-09-01.

## Nos résultats

Non commencé au 2026-09-01.

## Notre contrôle de robustesse

Non commencé au 2026-09-01.

## Références

Sources consultées de première main le 2026-09-01 :

- Hurst, B., Ooi, Y. H. et Pedersen, L. H. (2017). « A Century of Evidence on
  Trend-Following Investing ». The Journal of Portfolio Management, 44(1), 15-29.
  DOI 10.3905/jpm.2017.44.1.015. Manuscrit accepté lu à l'adresse
  <https://static.twentyoverten.com/593e8a9e7299b471eaecf644/SkLoGL67M/A-Century-of-Evidence-on-Trend-Following-Investing.pdf>,
  portant la mention SSRN 2993026.
- Hurst, B., Ooi, Y. H. et Pedersen, L. H. (2014). « A Century of Evidence on
  Trend-Following Investing ». Note blanche AQR, automne 2014, échantillon 1880-2013.
  Lue à l'adresse
  <https://www.trendfollowing.com/whitepaper/Century_Evidence_Trend_Following.pdf>.
- Page de l'article chez l'éditeur :
  <https://www.pm-research.com/content/iijpormgmt/44/1/15>. Métadonnées seules ; le texte
  est derrière un péage.
- Page SSRN <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2993026> : réponse HTTP
  403 depuis cet environnement, non consultée.

Références citées par métadonnées vérifiées mais non consultées au fond :

- Huang, D., Li, J., Wang, L. et Zhou, G. (2020). « Time series momentum: is it there? ».
  Journal of Financial Economics, 135(3), 774-794. DOI 10.1016/j.jfineco.2019.08.004.
  Résumé lu, texte intégral non consulté.
- Kim, A. Y., Tse, Y. et Wald, J. K. (2016). « Time series momentum and volatility
  scaling ». Journal of Financial Markets, 30, 103-124. DOI 10.1016/j.finmar.2016.05.003.
  Résumé lu, texte intégral non consulté.
- Goyal, A. et Jegadeesh, N. (2018). « Cross-sectional and time-series tests of return
  predictability: what is the difference? ». The Review of Financial Studies, 31(5),
  1784-1824. DOI 10.1093/rfs/hhx131. Résumé lu, texte intégral non consulté.
- Zakamulin, V. (2014). « The real-life performance of market timing with moving average
  and time-series momentum rules ». Journal of Asset Management, 15(4), 261-278.
  DOI 10.1057/jam.2014.25. Résumé lu, texte intégral non consulté.
- Baltas, N. et Kosowski, R. (2020). « Demystifying time-series momentum strategies:
  volatility estimators, trading rules and pairwise correlations ». Market Momentum,
  30-67. DOI 10.1002/9781119599364.ch3.
- Moskowitz, T. J., Ooi, Y. H. et Pedersen, L. H. (2012). « Time series momentum ».
  Journal of Financial Economics, 104(2), 228-250. DOI 10.1016/j.jfineco.2011.11.003.
  Fiche de ce dépôt : [moskowitz_ooi_pedersen_2012.md](moskowitz_ooi_pedersen_2012.md).

Références internes à l'article, citées telles qu'elles y figurent :

- Jones, C. (2002), source des multiplicateurs historiques de coûts de transaction.
- Barberis, N., Shleifer, A. et Vishny, R. (1998) ; Daniel, K., Hirshleifer, D. et
  Subrahmanyam, A. (1998) ; De Long, J. B. et al. (1990) ; Hong, H. et Stein, J. (1999) ;
  Frazzini, A. (2006), pour les biais comportementaux invoqués.
- Asness, C., Moskowitz, T. et Pedersen, L. H. (2013). « Value and Momentum Everywhere ».
  The Journal of Finance, 68(3), 929-985. Fiche jumelle de ce dépôt :
  [asness_moskowitz_pedersen_2013.md](asness_moskowitz_pedersen_2013.md).

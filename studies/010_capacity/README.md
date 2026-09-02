# Étude 010 : à quelle taille les deux stratégies chiffrables cessent-elles de rapporter ?

**Verdict : `REJECTED`.** Aucune des deux stratégies ne garde un ratio de
Sharpe net de 0,5 à cent millions de dollars. Le momentum de série temporelle
sur fonds cotés est borné par la participation avant de l'être par l'impact :
à un million de dollars, un rééquilibrage sur quatre demande déjà plus de dix
pour cent du volume quotidien d'un fonds de devises. L'arbitrage statistique a
une capacité nulle avant tout impact, parce que son brut ne couvre pas les cinq
points de base de demi-écart de l'article sur 1996-2026. Tout chiffre de cette
étude porte le statut **modélisé** : le coefficient d'impact est déclaré, pas
mesuré.

## La question de recherche

Une stratégie se publie avec un ratio de Sharpe et sans taille. Un allocateur
pose la question inverse : à combien de dollars ce ratio tient-il encore ? Les
huit études précédentes ont mesuré des rendements par dollar, comme si le
dollar suivant coûtait le même prix que le premier. Cette étude rejoue les
poids de deux d'entre elles à neuf tailles de capital, du million à dix
milliards, avec un coût d'impact qui croît avec la part du volume qu'un ordre
représente.

Deux stratégies seulement sont chiffrables. Les six autres du laboratoire
tournent sur des portefeuilles de facteurs publiés par Kenneth French ou AQR,
sans poids par titre ni volume ; leur capacité est **non calculable** avec des
données gratuites, et c'est écrit tel quel.

## L'article

Trois sources, aucune n'étant répliquée au sens des études 001 à 008. Almgren,
Thum, Hauptmann et Li (2005), *Direct estimation of equity market impact*,
Risk 18, estiment sur des ordres institutionnels réels une loi d'impact en
puissance de la participation, d'exposant proche de 0,6. Gatheral (2010),
*No-dynamic-arbitrage and market impact*, Quantitative Finance 10, montre que la
racine carrée est la forme compatible avec l'absence d'arbitrage sous une
décroissance exponentielle de l'impact. Frazzini, Israel et Moskowitz (2018),
*Trading Costs*, SSRN 3229719, mesurent la capacité des facteurs sur les
exécutions d'AQR ; **non consulté** dans cette étude, cité comme la référence
de ce qu'une mesure sur données réelles donnerait.

## L'intuition économique

Un ordre déplace le prix contre celui qui le passe, et le déplacement croît
avec la taille de l'ordre rapportée à ce que le marché échange d'habitude.
Passer deux fois plus de volume ne coûte pas deux fois plus, parce que le
carnet se reconstitue pendant l'exécution : la racine carrée est la forme
empirique retenue. Comme le capital multiplie chaque ordre, l'impact croît
comme la racine du capital, et il finit par manger l'alpha. La taille où il
l'a mangé entièrement est la capacité.

## La définition mathématique

Le coût d'un rééquilibrage au capital \( A \), pour une variation de poids
\( \delta_i \) sur l'actif \( i \), un demi-écart \( c_s \), une exécution sur
\( k \) séances :

\[
C_t = c_s \sum_i |\delta_{i,t}|
    + \kappa \sum_i |\delta_{i,t}|\, \sigma_{i,t}
      \sqrt{\frac{|\delta_{i,t}|\, A}{k \cdot ADV_{i,t}}}
\]

Le rendement net moyen est une droite en \( \sqrt{A} \), et le capital
d'annulation a une forme fermée :

\[
\bar r^{net}(A) = g - s - \sqrt{A}\,K
\qquad\Longrightarrow\qquad
A^{\ast} = \left(\frac{g - s}{K}\right)^{2}
\]

où \( g \) est le brut moyen par période, \( s \) le demi-écart moyen payé et
\( K \) la charge d'impact moyenne mesurée au capital unité. Les formules
vivent dans `quantlab.execution.capacity`, avec leurs dix points de
documentation, et l'[ADR-012](../../docs/architecture/adr/adr-012-capacite-par-forme-fermee.md)
dit pourquoi le moteur de backtest n'a pas été modifié.

## Les données

Les mêmes que les études 001 et 007, retéléchargées le 2026-09-02 par les mêmes
fournisseurs, avec deux champs de plus : le prix de clôture non ajusté et le
volume en titres, dont le produit est le volume en dollars.

| Stratégie | Source | Univers | Fenêtre évaluée | Périodes |
|---|---|---|---|---:|
| Momentum de série temporelle (001) | Yahoo, Kenneth French pour le taux sans risque | 28 fonds négociés en bourse, quatre classes d'actifs | 2007-01 à 2026-06 | 234 mois |
| Arbitrage statistique (007) | Yahoo | grandes capitalisations américaines, biais de survie déclaré | 1996-01 à 2026-06 | 7 672 séances |

Deux entrées de l'impact sont calculées sans regarder l'avenir. Le volume
quotidien moyen est la médiane de vingt et une séances de volume en dollars,
décalée d'une séance. La volatilité est l'écart type de vingt et une séances de
rendements quotidiens, décalé de même. Quinze séances valides suffisent, pour
qu'un titre qui sort de la cote garde un volume lisible jusqu'à sa vente.

## La méthodologie originale

Almgren et ses coauteurs régressent l'impact réalisé de quelque 700 000 ordres
sur la participation et la volatilité, et estiment l'exposant et le
coefficient. Frazzini, Israel et Moskowitz font de même sur les exécutions
d'AQR et en déduisent, pour chaque facteur, la taille à laquelle son alpha net
s'annule. Dans les deux cas le coefficient est **mesuré** sur des exécutions
réelles.

## Notre implémentation

Un modèle de coût, `ImpactAtScale`, porte le capital, le volume quotidien moyen
et la volatilité de chaque actif, et enrichit le contexte que le moteur lui
passe avant de déléguer le calcul aux modèles de coût existants. La courbe de
capacité rejoue les mêmes poids à chaque taille d'une grille géométrique de
neuf points. Deux passages au capital unité isolent \( g \), \( s \) et
\( K \), la forme fermée rend \( A^{\ast} \), et un dernier passage du moteur à
ce capital vérifie que le net moyen y vaut zéro à la précision machine.

Le plafond de participation, dix pour cent du volume quotidien, borne la
crédibilité du modèle. Au-delà, le coût est écrêté et déclaré minorant. Quand la
plus grosse transaction de l'historique dépasse ce plafond avant \( A^{\ast} \),
la capacité retenue est le capital où le plafond est atteint, déduit de la
participation au capital unité par une règle de trois.

Les poids sont rebâtis avec les fonctions de `quantlab.strategies` et les
paramètres des études 001 et 007, lus dans leurs propres `config.yaml`. Le
demi-écart est la somme des postes proportionnels de chaque étude, 4 points de
base pour la première, 5 pour la seconde.

## Nos écarts avec l'article

| Point | Almgren et coauteurs (2005) | Cette étude |
|---|---|---|
| Exposant de la participation | 0,6, estimé | 0,5, fixé |
| Coefficient | estimé sur des ordres réels | déclaré à 1, sensibilité à 0,5 et 2 |
| Impact temporaire et permanent | séparés | confondus, entièrement payé |
| Horizon d'exécution | variable | une séance, sensibilité à cinq |
| Capital | celui des ordres observés | constant sur tout l'historique |

## Les résultats

Tous les chiffres : `results/tables/summary.csv`, `capacity_tsmom.csv`,
`capacity_statarb.csv`, `sensitivity.csv` et `metrics.json`. Statut modélisé,
net de demi-écart et d'impact, brut de frais de gestion et de financement.

**Momentum de série temporelle sur 28 fonds cotés, 2007-2026, 234 mois.**

| Grandeur | Valeur |
|---|---:|
| Ratio de Sharpe à taille nulle, demi-écart payé | 0,335 |
| Rendement annualisé à taille nulle | 5,76 % |
| Ratio net à 1 M$ / 10 M$ / 100 M$ / 1 G$ | 0,293 / 0,252 / 0,209 / 0,177 |
| Part des rééquilibrages où un fonds dépasse 10 % de son volume, à 1 M$ / 10 M$ / 100 M$ | 24,5 % / 78,5 % / 99,1 % |
| Capital d'annulation, forme fermée | 44,0 M$ |
| Net moyen rendu par le moteur à ce capital, attendu zéro | +0,32 % par mois, donc **écrêté et optimiste** |
| Capital où le plafond de participation est atteint | **84 940 $** |
| Fonds qui bornent | FXF, FXA, FXB, FXY, SHY |
| Capacité retenue | **84 940 $** |

La lecture n'est pas que la stratégie meurt d'impact : c'est que le modèle
d'impact ne s'applique plus au-delà de cent mille dollars. La cible de 40 % de
volatilité par position, celle de l'article, fait porter plusieurs fois le
capital sur un fonds de devises qui bouge de 8 % par an, et ce fonds s'échange
quelques millions de dollars par séance. Les contrats à terme de l'article
n'ont pas ce défaut, leurs substituts cotés l'ont. La courbe tracée dans
`results/figures/capacity_tsmom.png` reste positive jusqu'à dix milliards, et
chaque point y est creux : le coût y est écrêté, donc le net est optimiste.

**Arbitrage statistique sur grandes capitalisations, 1996-2026, 7 672 séances.**

| Grandeur | Valeur |
|---|---:|
| Ratio de Sharpe à taille nulle, demi-écart payé | -0,306 |
| Rendement annualisé à taille nulle | -3,73 % |
| Demi-écart payé par an, à 5 points de base | 1 721 points de base, soit 344 fois le capital négocié |
| Impact à 1 M$ / 10 M$ / 100 M$ | 926 / 2 924 / 8 043 points de base par an |
| Ratio net à 1 M$ / 10 M$ / 100 M$ | -1,07 / -2,71 / -6,75 |
| Capital d'annulation | **0 $**, le net est déjà négatif à taille nulle |
| Capital où le plafond est atteint | 3,26 M$, titres PKG, GPC, ES, SJM, KIM |
| Dernier volume connu prêté à un titre sorti de la cote | 0,55 % des rééquilibrages |

La capacité est nulle par construction, et l'étude 007 l'annonçait : le coût
de seuil de rentabilité y vaut 3,92 points de base, sous les 5 de l'article.
L'apport de cette étude est l'ordre de grandeur de ce que l'impact ajouterait
si le brut couvrait le demi-écart : neuf pour cent par an au premier million,
parce que la stratégie tourne 344 fois son capital par an.

## La robustesse

Les huit essais déclarés. Le coefficient et la durée d'exécution ne changent pas
la conclusion, et la forme fermée se comporte exactement comme la loi le
prévoit : diviser le coefficient par deux multiplie le capital d'annulation par
quatre, étaler sur cinq séances le multiplie par cinq.

| Stratégie | Cas | Capital d'annulation | Capacité retenue | Ratio net à 100 M$ |
|---|---|---:|---:|---:|
| TSMOM | base, coefficient 1, une séance | 44,0 M$ | 84 940 $ | 0,209 |
| TSMOM | coefficient 0,5 | 176,0 M$ | 84 940 $ | 0,272 |
| TSMOM | coefficient 2 | 11,0 M$ | 84 940 $ | 0,081 |
| TSMOM | exécution sur cinq séances | 220,0 M$ | 424 702 $ | 0,238 |
| Arbitrage statistique | base | 0 $ | 0 $ | -6,75 |
| Arbitrage statistique | coefficient 0,5 | 0 $ | 0 $ | -3,61 |
| Arbitrage statistique | coefficient 2 | 0 $ | 0 $ | -11,77 |
| Arbitrage statistique | exécution sur cinq séances | 0 $ | 0 $ | -3,65 |

La borne par le plafond est un maximum sur tous les rééquilibrages, donc
fragile à une seule transaction : passer de vingt et une à quinze séances
valides dans les fenêtres l'a déplacée de 424 702 à 84 940 dollars. La colonne
« part des rééquilibrages écrêtés » de la table de capacité ne l'est pas, et
c'est elle qui porte la conclusion.

## Les coûts

Le demi-écart est proportionnel et ne dépend pas de la taille ; l'impact est le
seul terme convexe. Ni le financement de l'exposition au-delà du capital, ni
l'emprunt de titre ne sont facturés ici, parce qu'ils ne dépendent pas de la
taille et que les études 001 et 007 les traitent déjà. Le coefficient d'impact
n'est calibré sur aucune exécution réelle, et la capacité lui est
proportionnelle à la puissance moins deux.

## Le hors échantillon

Sans objet au sens des études 001 à 008 : aucun paramètre n'est ajusté ici,
et les poids sont ceux que les deux études ont déjà validés. La fenêtre
d'évaluation est l'historique entier de chaque stratégie, holdout compris,
parce que la capacité d'une stratégie ne se mesure pas sur ses seules bonnes
années.

## Les limites

| Limite | Statut |
|---|---|
| Coefficient d'impact déclaré, non mesuré | modélisé, sensibilité publiée à 0,5 et 2 |
| Exposant fixé à un demi quand Almgren estime 0,6 | reconnu, forme empruntée |
| Capital constant sur tout l'historique | reconnu, surestime la participation des débuts |
| Volume consolidé de fin de journée, sans distinction de séance | mesuré, c'est ce que Yahoo publie |
| Fonds de devises comme substituts de contrats à terme | reconnu, c'est ce qui borne le momentum |
| Sortie de cote à cotations fantômes, dernier volume connu prêté | déclaré, 0,55 % des rééquilibrages |
| Six stratégies sur huit non chiffrables | non calculable, faute de poids par titre |
| Fenêtre entière pour l'arbitrage statistique, dont vingt ans hors article | reconnu, la capacité sur 1997-2007 reste à mesurer |
| Yahoo révise ses volumes récents : deux exécutions à une heure d'intervalle diffèrent à la quatrième décimale, 84 941 puis 84 940 $ | mesuré le 2026-09-02, les chiffres publiés sont ceux de la dernière exécution |

## Le verdict

`REJECTED`. Le critère écrit avant le premier chiffre exigeait, à cent
millions de dollars, la moitié du ratio de Sharpe de taille nulle et un ratio
net d'au moins 0,5. Le momentum garde 62 % de son ratio, mais ce ratio vaut
0,209, et il est optimiste puisque le coût y est écrêté sur 99 % des
rééquilibrages. L'arbitrage statistique rend -6,75. Aucune des deux ne
franchit le seuil, et la phase 6 conclut ce que la phase 4 laissait entendre :
les stratégies du laboratoire n'ont pas de capacité à démontrer, elles ont
d'abord un alpha net à trouver.

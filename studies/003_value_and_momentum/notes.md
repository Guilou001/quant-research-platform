# Journal de l'étude 003

Ce fichier porte ce que le README ne porte pas : les essais qui n'ont rien donné, les fausses pistes,
et les surprises. Le compte des essais qui entre dans le ratio de Sharpe dégonflé est celui de
`results/tables/trials.csv`, soit **207**.

## Ce qui était connu avant d'écrire `config.yaml`, et pourquoi cela compte

Un seuil écrit après avoir vu le résultat n'est plus un seuil. Voici donc, exactement, ce qui avait
été mesuré au moment où `config.yaml` a été figé.

**Les quatre nombres de l'ancre du laboratoire.** Le fichier `/private/tmp/claude-501/ancres/mesures_2026-09-02.md`
donnait la corrélation de la paire EVERYWHERE sur l'échantillon complet, -0,577, et les trois ratios
de Sharpe qui l'accompagnent, 0,412, 0,593 et 1,096. La consigne de l'étude demandait de les
reproduire, ce qui est fait, à la décimale.

**Le tableau de la fenêtre de l'article, mesuré pendant la conception.** Avant d'écrire
`config.yaml`, les onze corrélations et les onze ratios de Sharpe de la fenêtre 1972-2011 ont été
mesurés une première fois, pour vérifier que les données étaient lisibles. L'écart des obligations
d'État était donc CONNU quand la règle de tolérance a été écrite.

**Pourquoi la règle reste défendable.** La tolérance n'est pas un nombre choisi, c'est une formule :
deux erreurs types d'échantillonnage d'un coefficient de corrélation, soit
\(2 (1 - \rho^2)/\sqrt{n}\). Elle se calcule depuis la valeur PUBLIÉE et le nombre de mois, jamais
depuis notre mesure. Elle vaut 0,095 pour les obligations d'État et 0,053 pour les actions
américaines, sans qu'aucun de ces deux nombres n'ait été touché. Le seuil de deux écarts types est
celui de 5 %, et il aurait été le même sur n'importe quel jeu.

**Ce qui n'était pas connu.** Le ratio de Sharpe hors échantillon, la rotation, le comportement en
période de tension, la décomposition du panneau, et la composition des dix-sept derniers mois. Les
sept autres seuils du verdict sont ceux du laboratoire, repris tels quels de l'étude 006.

## Le compte des essais, famille par famille

| Famille | Essais | Ce qu'elle couvre |
|---|---:|---|
| `replication_A` | 11 | Un mélange par paire, fenêtre de l'article |
| `balanced_panel` | 3 | Les trois agrégats restreints aux mois à huit classes |
| `pairs_A_ew` | 11 | Un mélange à parts égales par paire d'AQR |
| `pairs_A_rp` | 11 | Un mélange à risque égal par paire d'AQR |
| `pairs_B_ew` | 4 | Les quatre paires de Kenneth French, parts égales |
| `pairs_B_rp` | 4 | Les mêmes, à risque égal |
| `paper_window_rp` | 15 | Un mélange à risque égal par paire, fenêtre de l'article |
| `paper_window_B_ew` | 4 | Les quatre paires de Kenneth French, fenêtre de l'article |
| `holdout_window` | 2 | Les deux sous-fenêtres du hors échantillon |
| `weight_grid` | 121 | Onze paires par onze poids |
| `rp_window` | 4 | Quatre fenêtres du poids à risque égal |
| `rebalance` | 4 | Quatre pas de rééquilibrage |
| `lag` | 3 | Trois délais d'exécution |
| `costs` | 4 | Quatre taux de coût |
| `cost_multiple` | 6 | Six multiples de coût strictement positifs |
| **Total** | **207** | |

Le balayage compte pour autant d'essais qu'il a de cellules, règle 8. Les 121 cellules recouvrent en
partie les 15 mélanges à parts égales, puisque la colonne de poids 0,5 est le même objet. Ce double
compte est volontaire et conservateur : il durcit le ratio de Sharpe dégonflé.

**Trois familles restent hors du compte, et elles sont nommées.** Les trois longueurs de corrélation
glissante, les douze cellules de corrélation en période de tension, et les onze contrôles de
réplication de la table I. Aucune ne rend un rendement détenable ni ne peut être choisie comme
résultat. Restent dehors aussi les décompositions d'une série déjà comptée, les trois sous-périodes
et les quatre lignes du risque de queue.

**Le compte est passé de 183 à 207 après recomptage.** La première version comptait toutes les
grilles et oubliait quatre familles publiées hors grille. Les voici, et leur ajout ne change aucun
verdict : le ratio dégonflé descend de 0,005 à 0,000012, alors que le seuil est de 0,95, et la
statistique t de Holm valait déjà zéro. Le maximum attendu sous l'hypothèse nulle monte de 0,777 à
0,884, et le t de Bonferroni de 3,639 à 3,671.

## La fausse piste principale, et ce qu'elle a appris

**Ce qui a été essayé d'abord.** Les trois agrégats d'AQR rendent des ratios de Sharpe de mélange
nettement inférieurs aux publiés, 1,245 contre 1,59 pour le mondial. L'hypothèse de travail était que
la note 11 de l'article, la pondération par l'inverse de l'écart type d'échantillon, n'était plus
celle d'AQR.

**La reconstruction essayée, et son échec.** Les huit jambes individuelles ont été agrégées à la main
par l'inverse de leur écart type de plein échantillon, puis comparées à la colonne publiée. Trois nombres,
mesurés hors de `results/` le 2026-09-02. La corrélation de la reconstruction avec la colonne VAL vaut
0,968. Son écart type est 1,158 fois trop petit. Et la corrélation avec MOM ne vaut que 0,882.
La reconstruction ne redonne donc pas la colonne d'AQR, et sa pondération exacte reste **non
trouvée**. La piste est abandonnée, elle n'est pas comptée dans les essais parce qu'elle ne rend
aucune stratégie candidate.

**Ce qui a fermé la question, à moitié.** Le panneau est déséquilibré : les huit classes ne coexistent
qu'à partir de janvier 1983. Restreindre l'agrégat à ces 343 mois porte son ratio de Sharpe de 1,245
à 1,466, soit 64 % du chemin vers 1,59, et l'agrégat hors actions gagne davantage encore.
`results/tables/balanced_panel.csv` porte les six cellules. Le reste, 0,124, est déclaré non
attribuable : le classeur d'AQR écrit lui-même que ses sources et sa méthode peuvent différer de
l'article.

## La surprise trouvée tard, et qui a failli passer

**Les dix-sept derniers mois ne portent pas les mêmes actifs.** Les colonnes hors actions du classeur
d'AQR s'arrêtent au 31 janvier 2025, alors que la colonne agrégée court jusqu'au 30 juin 2026. Rien
dans le fichier ne le signale. Le défaut a été trouvé en lisant le tableau de couverture, où cinq
paires finissent en janvier 2025 et six en juin 2026.

**Ce que cela change.** Le ratio de Sharpe hors échantillon passe de 0,604 sur 179 mois à 0,246 sur
les 162 mois où les huit classes existent. Les dix-sept mois restants rendent 2,471, sur une série
qui n'est plus le même portefeuille. Le critère du verdict, fixé à 0,50, est donc franchi par une
fenêtre dont la composition change.

**Ce qui n'a PAS été fait, et pourquoi.** La définition du hors échantillon n'a pas été changée. Elle
est écrite dans `config.yaml` avant les résultats, et la modifier après avoir vu les deux nombres
serait déplacer la cible. Le tableau `holdout_composition.csv` a été ajouté pour publier la lecture
prudente, et le README dit en toutes lettres que ce critère passe pour une raison qu'il faut
connaître.

## Deux contrôles qui ne mesurent rien, et le disent

**La validation croisée combinatoire.** Les sept chemins rendent exactement le même ratio de Sharpe,
à écart type nul. La raison a été cherchée dans le code avant d'être trouvée dans les données : sur
les 56 sélections effectuées, le poids retenu est TOUJOURS 0,5. Un processus de sélection qui ne varie
jamais reconstruit toujours la même série, et la distribution s'effondre en un point. Le compte de
sélections distinctes est maintenant écrit dans `cpcv_distribution.csv` pour que cela se voie.

**La probabilité de surapprentissage.** Elle vaut zéro, pour exactement la même raison. La
configuration qui gagne en échantillon gagne aussi hors échantillon, parce que c'est toujours la même.
Ce n'est pas une preuve de robustesse, c'est un constat de dégénérescence.

**La leçon.** Ces deux contrôles jugent un PROCESSUS de sélection. Quand la stratégie n'en a pas, ils
n'ont rien à juger, et un lecteur pressé lirait « PBO nulle » comme une bonne nouvelle. C'est le même
piège que l'étude 006 avait rencontré sous une autre forme, celle d'une série figée.

## Le ratio de Sharpe dégonflé dépend du compte, et pas du résultat

C'est le constat le plus inconfortable de l'étude. Source :
`results/tables/deflation_sensitivity.csv`.

Avec 15 essais, le ratio dégonflé vaut 0,9998 et le critère passe largement. Avec 121, il vaut 0,537.
Avec les 207 essais du registre, il vaut 0,000012 et le critère échoue. Le ratio de Sharpe observé, lui,
ne bouge pas : 0,604.

**Ce que cela ne justifie pas.** Rien ici ne permet de choisir la convention la plus douce après coup.
La règle 8 du laboratoire dit que toutes les cellules de toutes les grilles comptent, et la référence
reste 207. La table de sensibilité est publiée pour que le lecteur voie le mécanisme, pas pour offrir
un autre chiffre.

**Ce que cela justifie.** Une réserve écrite dans les limites : les 207 essais ne sont pas
indépendants, 121 d'entre eux étant onze poids voisins sur les mêmes onze paires. Le maximum attendu
de 0,884 sous l'hypothèse nulle est donc un majorant, et le critère est conservateur.

## Ce qui a été essayé et n'a rien donné

**Le poids à risque égal estimé sur le passé.** Il devait battre le poids fixe de la moitié, puisqu'il
égalise les contributions au risque plutôt que les dollars. Il ne le bat sur aucune des quatre
fenêtres, et il perd de 0,001 à 0,006 de ratio de Sharpe. La raison est visible dans la colonne du
poids médian : elle vaut 0,492 à 0,502, donc l'estimation reconstruit à grands frais un nombre déjà
connu. C'est le meilleur argument pour la convention de l'article, et il n'était pas attendu.

**Le rééquilibrage plus lent.** Il devait coûter, en laissant le poids dériver. Il rapporte 0,009 de
ratio de Sharpe net à six mois, et ne coûte qu'à douze mois, 0,016. La rotation étant minuscule, le
gain de coût ne compense presque rien et le résultat vient du hasard de la dérive.

**Le rabais de Harvey et Liu.** Il est calculable ici, le ratio de Sharpe hors échantillon étant
positif, mais il rend une statistique t ajustée de exactement zéro. Avec 207 tests, la correction de
Holm porte la valeur p à un. Le critère échoue donc par une borne et non par une mesure fine, et la
colonne `haircut_status` de `deflated_sharpe.csv` dit que le calcul a bien eu lieu.

**La corrélation en période de tension.** Elle devait se dégrader partout, comme le veut le récit
courant sur la diversification qui disparaît quand elle sert. Elle se dégrade sur les actions, de
-0,671 à -0,429 aux États-Unis, mais elle se RENFORCE sur la paire toutes classes d'actifs aux deux
seuils les plus serrés, de -0,553 à -0,785. Le signe s'inverse au quantile de 0,20, donc aucune des
trois lignes ne se lit seule et le résultat est publié comme dépendant du seuil.

## Les trois frictions rencontrées dans l'infrastructure

Aucune n'est un défaut du laboratoire, et les trois ont coûté une exécution chacune.

**`cost_multiplier_analysis` refuse un multiple nul.** La grille de `config.yaml` porte le zéro, qui
sert de repère brut. Le multiple nul est maintenant filtré à l'appel, et le rendement brut est publié
par la ligne à zéro point de base du tableau des coûts.

**`bootstrap_statistic` ne connaît pas la méthode « block ».** Les quatre noms sont `iid`,
`moving_block`, `circular_block` et `stationary`. Le bloc circulaire est retenu, et il est déclaré
dans le tableau.

**`AlphaMetadata` refuse le mécanisme « risque de financement ».** Les quatre mécanismes admis sont le
biais comportemental, la contrainte institutionnelle, la friction et la prime de risque. Le risque de
financement de l'article est une contrainte institutionnelle, et la fiche d'alpha le déclare ainsi.

## Le contrôle par mutation des tests

Quatre défauts ont été réintroduits à la main dans `value_momentum.py`, puis les cinquante tests
relancés. Le compte de tests en échec est mesuré, pas supposé.

| Mutation | Tests en échec |
|---|---:|
| Retirer le décalage d'un mois du poids en expansion | 1 |
| Remplacer \(2 + 2\rho\) par \(1 + \rho\) dans la forme fermée | 5 |
| Mettre la dérivée à la puissance un demi au lieu de trois demis | 2 |
| Retirer la constante de mise à l'échelle des poids de rang | 5 |

La première mutation n'attrape qu'un test, et c'est peu. Le test en question est celui qui perturbe un
mois du milieu et exige que le poids de CE mois ne bouge pas. Une première version perturbait le
dernier mois, et elle passait avec ou sans le défaut, donc elle ne testait rien. Le test de
troncature, lui, ne bouge pas sous cette mutation parce que la troncature retire aussi le mois fautif.

## La contre-vérification des chiffres du README

Un script indépendant a confronté chaque cellule numérique des quinze tableaux du README au fichier de
`results/` qui la porte, plus sept nombres cités en prose. **Onze écarts ont été trouvés et corrigés.**

Six étaient des arrondis au dernier chiffre, tous dans le même sens que l'erreur humaine habituelle.
Ce sont 0,09 au lieu de 0,08 pour les sigmas du Japon, puis -0,611 au lieu de -0,610 et 0,005 au lieu
de 0,004. Ce sont enfin 0,121 au lieu de 0,120, 3,532 au lieu de 3,531, et -5,32 % au lieu de
-5,31 %.

**Cinq étaient des affirmations fausses en prose, et elles sont plus graves.** La première disait que
« le pire poids intérieur reste au-dessus de la meilleure jambe seule dans neuf paires sur onze ».
Elle était FAUSSE. Le pire poids intérieur est au-dessous de la meilleure jambe dans les onze paires,
et il est au-dessus de la plus faible dans les onze. La phrase a été refaite. Trois autres portaient
un compte ou une moyenne inexacts. Il y a sept corrélations sous une erreur type et non six, et
l'écart moyen des marchés individuels vaut 0,036 et non 0,09. La plage de corrélations de la jambe A
était aussi mal bornée. La cinquième attribuait à l'article un coût de dix points de base qu'il
n'écrit pas.

**La leçon.** Les six arrondis se voient à la machine. Les cinq affirmations ne se voient qu'en
recalculant la phrase, et c'est celle qui compare deux colonnes qui a failli passer.

## La passe de contradiction du 2026-09-02, et ses cinq corrections

Une seconde lecture, menée pour mettre l'étude en défaut, a effacé `results/` et relancé l'étude. Les
trente tableaux se sont reproduits au fichier près. Cinq défauts ont été trouvés, tous corrigés, et
aucun ne change le verdict.

**Le compte des essais était sous-déclaré, 183 au lieu de 207.** C'est le défaut le plus lourd, parce
qu'un compte trop petit rend le ratio de Sharpe dégonflé trop flatteur. Quatre familles publiées
vivaient hors du compte, et le README affirmait au contraire que le compte couvrait toutes les
évaluations de performance. Le détail est dans la section du compte des essais.

**Le titre de la carte de chaleur annonçait 1972-2026.** Ses données s'arrêtent en janvier 2025,
l'agrégat hors actions y finissant, et l'intersection des deux agrégats ne va donc pas plus loin. Le
titre se déduit maintenant des dates du tableau tracé, ce qui interdit à l'écart de revenir.

**Deux figures affichaient le point décimal anglais.** Les deux qui sont bâties à la main dans
`run.py`, la corrélation glissante et le nuage du Sharpe contre la corrélation, n'appliquaient pas le
formateur d'axe français que les fabriques de `quantlab.analytics.visualization` posent
elles-mêmes. Elles le posent désormais.

**Une phrase disait « les mêmes 475 mois » pour deux séries qui n'ont pas les mêmes mois.** La jambe
américaine d'AQR commence en février 1972 et porte 474 mois dans la fenêtre de l'article ; la paire
de Kenneth French en porte 475. La comparaison reste valide, le mois d'écart ne pesant rien, mais la
phrase était fausse et elle est corrigée.

**Deux arrondis.** L'écart du poids à risque égal contre le poids fixe vaut au plus 0,0063, donc
0,006 et non 0,007. Et la racine de 0,845 vaut 0,919, non 0,920, dans l'exemple déroulé à la main.

**Ce que la passe n'a pas trouvé.** Aucune information future. Le mélange à parts égales n'estime
rien, et le poids à risque égal en expansion est décalé d'un mois, ce que deux tests prouvent.
L'ordre des colonnes des vingt-cinq portefeuilles de Kenneth French a été vérifié contre le fichier
réel : la taille varie le plus lentement, donc la moyenne se prend bien sur la taille. Aucun seuil du
verdict n'a bougé. Les neuf instantanés de configuration écrits par les neuf exécutions portent tous
les mêmes huit seuils, les mêmes grilles et les mêmes bornes d'échantillon. Seule la phrase
d'hypothèse diffère, coupée en deux, comme l'étude le déclarait.

## Ce qui n'a pas été fait

**Le modèle à trois facteurs et ses 48 actifs de test**, tables V et VI de l'article. Ils exigent les
portefeuilles par tiers de chaque marché, que le classeur d'AQR ne publie pas. Report assumé, et non
oubli.

**La jambe de valeur américaine au prix courant**, sur l'univers de Kenneth French. Elle isolerait la
date du prix des deux autres différences entre la jambe A et la jambe B, et elle transformerait la
borne publiée en attribution. Les capitalisations mensuelles sont disponibles dans le tableau
`average_market_cap` des vingt-cinq portefeuilles. C'est la prochaine décision, et elle est écrite
dans le README.

**Les corrélations croisées entre marchés**, table II de l'article. Elles demandent des rendements
trimestriels et une moyenne des corrélations d'un marché avec tous les autres, marché lui-même exclu.
La figure des quatre agrégats en donne une version réduite, qui n'est pas le tableau.

**Les erreurs types de Newey-West.** Les statistiques t publiées sont celles de Lo, robustes à
l'autocorrélation, telles que `sharpe_tstat` les rend par défaut. La variante i.i.d. n'a pas été
essayée, donc elle ne figure pas dans le compte des essais.

**Le coût de financement du levier et le coût d'emprunt des titres vendus.** Les deux jambes sont
longues et courtes, donc un investisseur réel paierait pour emprunter. L'omission joue en faveur de la
stratégie, et elle est déclarée dans les limites.

## Un détail de numérotation

Le fichier `studies/README.md` n'a pas été modifié, ce fichier n'étant pas dans le périmètre
d'écriture de l'étude.

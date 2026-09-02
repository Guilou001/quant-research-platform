# Journal de l'étude 007

Ce fichier porte ce que le README ne porte pas : les essais qui n'ont rien donné, les fausses
pistes, et les surprises. Le compte des essais qui entre dans le ratio de Sharpe dégonflé est celui
de `results/tables/trials.csv`, soit **49**.

## Le compte des essais, famille par famille

| Famille | Essais | Ce qu'elle couvre |
|---|---:|---|
| `grid` | 16 | Quatre nombres de facteurs par quatre fenêtres d'estimation |
| `rules` | 3 | Les trois variantes de seuils, hors règle de l'article |
| `n_components` | 2 | Un seul portefeuille propre, puis trente |
| `variance_share` | 4 | Les quatre coupures de variance expliquée |
| `correlation_window` | 2 | Six mois et deux ans, hors le cas de référence |
| `reestimation` | 2 | Décider tous les cinq jours, puis tous les vingt et un |
| `characteristic_days` | 3 | Filtre serré, relâché, et retiré |
| `s_score` | 2 | Sans centrage transversal, puis s-score modifié par la dérive |
| `hedge` | 1 | Couverture recalculée chaque séance |
| `convention` | 2 | Le livre de l'article, avec puis sans couverture par le fonds indiciel |
| `costs` | 6 | Six taux de coût sur le cas de référence |
| `cost_multiple` | 6 | Six multiples du coût supposé |
| **Total** | **49** | |

La grille compte pour autant d'essais qu'elle a de cellules, règle 8. Cinq cellules répètent le cas
de référence sous un autre angle, la fenêtre de corrélation de 252 séances par exemple, et elles
sont comptées quand même. Le sur-compte durcit le ratio de Sharpe dégonflé au lieu de le flatter,
donc il est conservé.

## La décision qui devait tout changer, et qui ne change presque rien

**L'hypothèse de départ.** L'article dit que ses positions sont tout ou rien, sans ajustement
continu. Il dit aussi que la couverture consiste à vendre les montants de facteurs correspondants
au moment d'entrer. Deux lectures existent donc : la couverture se fige au jour de l'entrée, ou
elle se recalcule chaque séance avec les bêtas du jour.

**Ce qui était attendu.** Recalculer chaque jour devait faire exploser la rotation, puisque toute
la jambe de facteurs se retournerait à chaque séance. La couverture figée devait donc être la
seule lecture compatible avec les cinq points de base par transaction que l'article retient.

**Ce qui est mesuré.** La rotation annuelle passe de 344,0 à 370,2 en somme entière, soit 7,6 %
de plus seulement, et le coût de seuil de rentabilité de 3,92 à 3,86 points de base. Sources :
`results/tables/costs.csv` et la ligne `quotidienne` de `results/tables/variants.csv`. Le choix
ne décide de rien.

**Pourquoi.** La rotation ne vient pas de la couverture, elle vient du renouvellement des
positions. Les 344,0 unités négociées par an sur une exposition brute de 4 valent 43 allers-retours
du livre entier, donc une position tient 5,9 séances en moyenne
(`results/tables/costs.csv`). Le temps de retour à la moyenne médian vaut 7,56 séances
(`results/tables/ou_diagnostics.csv`). La règle ferme avant le retour complet, ce qui explique
l'écart. La couverture figée retire ce que sa réestimation quotidienne ajoutait, et ce n'était pas
grand-chose.

**Ce que cela oblige à écrire.** Le README ne peut pas attribuer l'écart avec le ratio net publié à
cette convention. Il reste donc un désaccord non résolu, et c'est écrit tel quel.

## La rotation ne dépend pas du nombre de positions ouvertes

C'était le second contrôle de la même question, et il tranche. Les quatre règles de seuils tiennent
en moyenne 22,5, 66,3, 72,6 et 124,1 positions ouvertes, soit un rapport de 5,5 entre la plus
concentrée et la plus large. Leur rotation annuelle vaut 341,5, 384,5, 344,0 et 321,3, soit un
rapport de 1,2 (`results/tables/trading_rules.csv`).

La rotation est donc à peu près invariante au nombre de positions. Le mécanisme est simple : ouvrir
deux fois plus de positions les rend deux fois plus petites, et le montant négocié par position
baisse d'autant. Cette invariance compte pour la comparaison avec l'article. Son univers de 1 417
titres porte beaucoup plus de positions que nos 224, soit les 225 identifiants demandés moins le
repère de marché. L'invariance interdit donc d'expliquer son coût plus faible par cette taille.

Cette invariance est propre à notre normalisation, qui vise une exposition brute constante chaque
séance. Dans le livre de l'article, où chaque position ouverte porte un montant fixe, la rotation
croît avec le nombre de positions. Le tableau `results/tables/conventions.csv` le montre : 8 339,0
unités négociées pour une exposition brute médiane de 73,0, soit 114 par unité d'exposition, contre
344,0 sur 4, soit 86, chez nous.

## Le désaccord sur le ratio de Sharpe net, et pourquoi il n'est pas résolu

**Le fait.** Le ratio de Sharpe BRUT sur la fenêtre de l'article vaut 1,460 contre 1,44 publié, ce
qui est un écart de 1,4 %. Le ratio NET des cinq points de base que l'article retient vaut 0,181.
Source : `results/tables/decay.csv`.

**L'arithmétique, statut modélisé.** Le rendement brut annuel vaut 13,50 % et la rotation annuelle
344,0 en somme entière. Cinq points de base par unité négociée coûtent donc
344,0 fois 0,0005, soit 17,20 points de rendement par an. Aucun des essais menés à exposition brute
4 n'atteint ce niveau de rendement brut : le plus élevé, celui du cas à un seul portefeuille propre,
vaut 18,0 % par an (`results/tables/variants.csv`). Les deux livres de
`results/tables/conventions.csv` en sortent, mais leur exposition brute vaut 80,5 et 73,0, donc leur
rendement n'est pas comparable à celui-là.

**Quatre lectures ont été essayées, et une seule referme une part de l'écart.** La première est
la couverture figée, mesurée ci-dessus et sans effet. La deuxième, un levier plus faible, est écartée
par un argument et non par une mesure. La normalisation à exposition brute constante rend le
rendement proportionnel au levier, donc le coût aussi, donc le ratio de Sharpe est invariant. La
troisième est un glissement prélevé sur la seule jambe d'actions, que l'équation de compte de
résultat de la page 771 n'écrit pas. La quatrième est la bonne, et elle est décrite juste après.
Cesser de négocier la jambe de facteurs porte le ratio net de la fenêtre de l'article de 0,181 à
0,471 (`results/tables/conventions.csv`), soit 23 % de la distance jusqu'aux 1,44 publiés. Le reste
est **déclaré non résolu**.

## La couverture que nous négocions, et celle que l'article ne négocie pas

**Le fait, trouvé en relisant l'article et non en relisant le code.** Notre chaîne replie les
portefeuilles propres sur les titres, donc chacune de nos positions porte une jambe d'actions et une
jambe de facteurs, et les deux se paient. L'article ne négocie pas la seconde dès que les facteurs ne
sont pas des instruments cotés. Sa section 5.1 l'écrit : les fonds synthétiques n'étant pas
négociables, les auteurs négocient les seules actions du signal et achètent ou vendent le fonds
indiciel du marché pour annuler le bêta d'ensemble. Sa section 5.3 renvoie à cette phrase pour la
variante à quinze composantes principales. Son équation de compte de résultat, page 771, ne porte
d'ailleurs aucune position autre qu'une action.

**Pourquoi la première rédaction ne l'a pas vu.** Elle a lu la section 4, qui décrit l'entrée en
position comme l'achat d'un dollar d'action et la vente des montants de facteurs correspondants.
Cette phrase vaut pour les fonds sectoriels réels, qui se négocient. Les sections 5.1 et 5.3 la
corrigent pour les fonds synthétiques et pour les composantes principales, et c'est cette correction
qui avait été manquée.

**Ce qui est mesuré.** Le coût de seuil de rentabilité passe de 3,92 à 4,24 points de base dans la
lecture de l'article, et à 4,95 sans aucune couverture. Le ratio net de la fenêtre de l'article passe
de 0,181 à 0,471 puis à 0,725. La statistique t d'après publication passe de -4,20 à -3,79 puis à
-1,28. Source : `results/tables/conventions.csv` et `results/tables/decay.csv`.

**Ce que cela change au verdict, et ce que cela ne change pas.** Rien au verdict : le ratio de Sharpe
net d'après publication reste négatif dans les trois livres, donc le critère de signe rejette dans
les trois. Beaucoup à la phrase qui ouvre le README : le multiple de coût auquel la stratégie meurt
va de 0,78 à 0,99 selon la lecture, et non de 0,784 tout court. La conclusion tient, sa précision
affichée non.

**Ce qui reste à faire.** Le livre de l'article n'est pas seulement moins coûteux, il garde une
exposition sectorielle que notre couverture retire. Comparer les deux ratios bruts n'est donc pas
comparer deux coûts, c'est comparer deux stratégies. Une étude suivante devrait refaire la
réplication entière dans la convention de l'article, plutôt que de la mesurer en robustesse.

## Les essais qui n'ont rien donné

**Le s-score modifié par la dérive.** L'article le définit à l'équation (17) et ne le rétroteste
pas, jugeant son effet négligeable devant les seuils. Mesuré, il n'est pas négligeable et il est
nuisible : le ratio de Sharpe brut tombe de 1,107 à 0,447 et le rendement brut de 13,50 à 5,08 %
par an (`results/tables/variants.csv`). La dérive annualisée médiane vaut 78,4 points de base sur la fenêtre de l'article
(`results/tables/ou_diagnostics.csv`), contre les 15 points de base annoncés page 771. L'unité de ce
15 n'est pas donnée, et l'exemple numérique de la même page, 0,15 fois 7 divisé par 300 annoncé égal
à 0,3, ne se referme qu'en lisant 300 points de base comme 3. La comparaison est donc **déclarée
incertaine** faute d'unité publiée.

**Le filtre de vitesse de rappel.** Le retirer entièrement ne change presque rien : le ratio de
Sharpe net passe de -0,304 à -0,246 et la rotation de 344,0 à 330,2. La raison est dans
`results/tables/ou_diagnostics.csv` : 99,0 % des titres passent déjà le filtre, parce que le temps
de retour médian vaut 7,6 séances contre un seuil à 30. Le filtre que l'article présente comme un
garde-fou ne mord pas sur notre univers.

**Le centrage transversal du s-score.** Le retirer laisse le ratio de Sharpe net à -0,249 contre
-0,304, donc l'équation (A2) et sa version non centrée se valent. C'est un résultat rassurant sur
la robustesse de la formule, et non un résultat sur la stratégie.

**Décider moins souvent.** Rééquilibrer tous les vingt et un jours divise la rotation par quatre,
de 344,0 à 85,9, mais divise aussi le rendement brut par deux et demi, de 13,50 à 5,67 % par an. Le
ratio de Sharpe net remonte de -0,304 à 0,190 et le coût de seuil de rentabilité de 3,92 à 6,58
points de base, donc la stratégie s'améliore sans devenir viable. C'est le seul levier qui déplace
vraiment le coût de seuil.

## Le plafond de facteurs, un garde-fou qui n'a jamais servi

Le module borne le nombre de facteurs à la fenêtre d'estimation moins deux, pour éviter qu'une
coupure de variance haute demande plus de facteurs que la régression n'a de points. Sur les 7 673
décisions du cas de référence, il n'a mordu **aucune fois**
(`results/tables/pipeline_diagnostics.csv`). La coupure la plus haute, 75 % de variance, retient
37 facteurs en médiane pour une fenêtre de 60 séances, donc elle reste sous le plafond de 58. Le
garde-fou est conservé parce qu'un univers plus large le franchirait.

## La convention de rotation, décidée avant de mesurer

Le moteur de backtest rend la rotation en demi-somme, celle qui divise par deux parce qu'un
aller-retour se paie une fois. Le coût de seuil de rentabilité doit se comparer à un demi-écart
acheteur-vendeur payé par côté, donc il se calcule sur la rotation en somme entière, et le facteur
de conversion vaut exactement deux. Publier le coût de seuil sur la demi-somme le doublerait, de
3,92 à 7,84 points de base, et renverserait la conclusion face aux cinq points de base de l'article.
La rotation est donc recalculée par `turnover_series` en convention `full_sum` pour chacune des 47
configurations, et le modèle de coût linéaire du paquet emploie déjà la même convention.

## Les trois défauts trouvés dans notre propre chaîne

**Une grille de multiples de coût contenant zéro.** `cost_multiplier_analysis` refuse un multiple
nul, ce qui est correct : un multiple nul n'est pas un coût, c'est l'absence de coût. La
configuration en portait un, et l'exécution s'est arrêtée à l'étape des coûts. La valeur nulle a été
retirée de la grille des multiples, le taux nul restant dans la grille des taux.

**Les axes de la carte de chaleur étaient triés comme du texte.** La première version convertissait
le nombre de facteurs et la fenêtre en chaînes, ce qui rangeait les colonnes dans l'ordre 120, 30,
60, 90 et les lignes dans l'ordre 10, 15, 20, 5. La carte se lisait donc dans le désordre sans
qu'aucune erreur ne le signale, et le défaut s'est vu à l'oeil sur la figure produite. Les deux axes
portent maintenant les colonnes numériques.

**L'axe de richesse annonçait la mauvaise devise.** La fabrique de figures porte une devise par
défaut qui n'est pas celle de cette étude, si bien que l'axe annonçait des dollars canadiens sous un
titre qui annonçait des dollars des États-Unis. L'argument `currency` est maintenant passé.

Un quatrième point a été corrigé avant qu'aucun résultat n'existe, donc il ne compte pas comme un
défaut mesuré. La première rédaction repérait la première séance négociée par
`executed_weights.dropna(how="all")`, qui ne retire rien : le moteur remplit les lignes d'avant la
première décision par des poids nuls et non par des valeurs manquantes. La première séance négociée
se déduit maintenant de la première ligne de poids non manquante, décalée d'une séance.

## Le contrôle par mutation des tests

Quatre défauts ont été réintroduits volontairement, un à la fois, pour vérifier que les tests les
attrapent.

| Mutation | Tests qui échouent |
|---|---:|
| La fenêtre d'estimation avance d'une séance, donc elle lit le lendemain | 3 |
| Le s-score change de signe | 3 |
| Le poids du portefeuille propre ne divise plus par la volatilité | 1 |
| La couverture s'ajoute au lieu de se retrancher | 2 |

La première mutation est celle qui compte, parce qu'aucune erreur ne la signalerait. Elle est
attrapée par les deux tests de troncature et par le test de sortie d'univers. Le test de troncature
exige que la chaîne rebâtie sur un échantillon coupé rende exactement les mêmes poids sur les dates
communes, ce qu'un simple décalage ne garantit pas.

Un contrôle inverse accompagne le test de perturbation : perturber les rendements à partir de la
date de coupure, et non après elle, doit changer les poids de cette date. Sans lui, une fonction qui
rendrait toujours zéro passerait le test de causalité.

## Ce qui n'a pas été fait

**Les fonds sectoriels négociés en bourse**, variante des tables 5 et 9 de l'article. Elle demande
une affectation sectorielle par titre à la date passée, que l'article ne publie pas et que nous
n'avons pas reconstruite. Report assumé.

**Les fonds sectoriels synthétiques**, tables 4 de l'article. Même raison, aggravée : l'article dit
seulement qu'ils sont pondérés par la capitalisation, sans publier l'affectation.

**Les signaux en temps de transaction**, table 9, qui donnent le meilleur résultat de l'article
après 2002. La normalisation exacte du facteur de volume n'est décrite qu'en une phrase, et la
reconstruire aurait été une invention plutôt qu'une réplication.

**Le seuil de capitalisation d'un milliard de dollars à la date de négociation.** Aucune série de
capitalisation en temps réel n'est accessible gratuitement, et le substitut retenu est un seuil de
liquidité. L'écart est déclaré dans le README.

**La théorie des matrices aléatoires** pour nettoyer le spectre de la corrélation. L'article la cite
et ne l'applique pas ; nous ne l'appliquons pas non plus. Avec 224 titres et 252 séances, notre
matrice est de rang plein, ce qui n'était pas le cas de la leur.

## Quatre traces d'exécution partielles restent au registre

Le registre `artifacts/experiments.jsonl` porte plusieurs lignes au nom de cette étude. Deux portent un
verdict vide et se sont arrêtées à l'étape des coûts, sur le refus du multiple nul. Deux autres
portent 19 et 20 essais : ce sont des exécutions de mise au point menées sur un univers réduit à 61
titres et sur 2002-2012, pour vérifier la chaîne sans attendre seize minutes. Les deux dernières
sont les exécutions complètes, à 47 essais. Aucune n'est effacée, règle 8, et seule la dernière
alimente `results/`.

## Un détail de numérotation

Le fichier `studies/README.md` n'a pas été modifié, ce fichier n'étant pas dans le périmètre
d'écriture de l'étude.

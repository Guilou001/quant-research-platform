# Journal de l'étude 004, qualité moins camelote

Ce journal porte les essais ratés, les décisions et leurs raisons. Il se lit dans l'ordre
du temps. Les chiffres cités viennent tous d'un fichier de `results/`, sauf mention
contraire.

## Le 2026-09-02, l'ordre des travaux

L'étude a deux jambes, et elles ne coûtent pas la même chose. La jambe A rejoue le facteur
publié par AQR, ce qui demande un appel réseau et une heure de travail. La jambe B
reconstruit le score de qualité depuis les fondamentaux point-in-time, ce qui demande cinq
gigaoctets de données et la totalité du reste. L'ordre retenu a été de sécuriser la jambe A
d'abord, puis de laisser la jambe B tourner en tâche de fond.

## Le premier essai raté, et le plus dangereux

Le filtre de lecture des jeux de la SEC a rendu **zéro ligne sur les soixante-neuf
trimestres**, sans lever la moindre erreur.

La cause tient en une ligne. Les colonnes `segments` et `coreg` de `num.txt` valent la
chaîne vide, non la valeur manquante, quand la valeur décrit le groupe consolidé. Le filtre
écrit `num["segments"].isna()` gardait donc zéro ligne, et le programme continuait avec des
tableaux vides. Le compte des dépôts, lui, restait correct, ce qui rendait la sortie
plausible à la lecture rapide : `sub=7376 num=0` pour le quatrième trimestre 2011.

Deux enseignements. Un, une lecture qui rend zéro ligne doit être traitée comme une erreur,
pas comme un résultat. Deux, ce défaut ne se voit ni au type, ni à la forme, ni au nombre de
colonnes, donc aucun test de schéma ne l'attrape. Le test qui l'attrape est
`test_le_vide_n_est_pas_le_manquant`, qui construit une archive à la main et exige que
quatre lignes survivent au filtre.

## Le deuxième essai raté, les prix ajustés

Les prix quotidiens ont été téléchargés une première fois avec `auto_adjust=True`, puis
jetés et retéléchargés.

La raison est arithmétique. Le prix ajusté est corrigé rétroactivement des dividendes et des
divisions, alors que le nombre d'actions lu dans un dépôt est celui de la date du dépôt.
Leur produit n'est donc pas une capitalisation boursière : il sous-estime les sociétés qui
distribuent depuis longtemps, et l'erreur croît avec la profondeur de l'historique. Or la
capitalisation sert à quatre choses dans cette étude, la pondération des jambes, la coupure
de taille, la cote Z d'Altman et la cote O d'Ohlson.

Le second téléchargement demande `auto_adjust=False`, garde le prix de clôture BRUT pour la
capitalisation et le prix AJUSTÉ pour les rendements. C'est la seule combinaison qui rende
les deux grandeurs justes en même temps.

## Le troisième essai raté, la première écriture de l'agrégation

La première version de `component_scores` travaillait sur un tableau long, empilait les
panneaux standardisés, regroupait par niveau d'index, puis remettait le résultat à plat par
une suite de `stack` et de `reindex`. Elle passait les tests, et elle était illisible.

Elle a été réécrite sur des panneaux de dates et de sociétés, avec une pile NumPy à trois
dimensions. Le compte des variables renseignées devient une somme le long du premier axe, et
la moyenne se lit en une ligne. Le test qui garde la propriété importante est
`test_la_moyenne_et_la_somme_donnent_la_meme_composante` : sur une ligne complète, moyenne
et somme ne diffèrent que d'un facteur constant, que la standardisation qui suit efface.

## Le quatrième piège, un nom de colonne

`PITFrame.panel` nomme sa colonne de décision `as_of_date`, et le module de l'étude emploie
`as_of`. Le contrôle anti-fuite appelé avec `"as_of"` cherchait donc une DATE portant ce
nom, et levait une erreur d'analyse de date au lieu de dire que la colonne manquait. Le
correctif est explicite : l'étude passe `as_of_col="as_of"` à `panel`.

## Le cinquième essai raté, et il change les résultats

Les huit variantes à pondération égale du balayage rendaient entre moins 0,4 et
moins 1,8 pour cent PAR MOIS, alors que les douze variantes pondérées par la valeur
rendaient toutes du positif. Un écart de cette taille entre deux pondérations du même
signal n'est pas un résultat, c'est un symptôme.

**La cause, trouvée en regardant trois séries de prix.** Le tableau
`results/tables/return_quality.csv` annonçait un rendement mensuel maximal de 309,9,
soit trente mille neuf cent quatre-vingt-dix pour cent. Trois séries ont été ouvertes,
et elles portent trois défauts DIFFÉRENTS du même fournisseur.

| Société | Ce que la série montre | Ce que c'est |
|---|---|---|
| Chord Energy, ex-Oasis Petroleum | le cours passe de 0,11 à 34,20 dollars entre octobre et novembre 2020 | la sortie de faillite avec regroupement d'actions, raccordée sans ajustement |
| CODQL | le prix ajusté vaut moins 0,1177 en mars et avril 2022 | un prix ajusté négatif, arithmétiquement impossible |
| Diversified Energy | le prix ajusté vaut exactement zéro pendant onze mois de cotation | un ajustement manquant |

**Pourquoi la pondération égale explose et pas l'autre.** Une jambe de deux cent
soixante titres à poids égaux donne à chacun un poids de 0,385 pour cent. Un rendement
de 309,9 y apporte donc 119 points de rendement de portefeuille en un seul mois, soit
0,90 point par mois répartis sur les cent trente-deux mois de l'étude. C'est exactement
l'ordre de grandeur de l'écart observé. La pondération par la valeur donne à ces titres
un poids proche de zéro, donc elle ne le voyait pas.

**Le correctif, et son statut.** Deux filtres vivent maintenant dans le module.
`usable_prices` retire les prix nuls ou négatifs, ce qui attrape les deux derniers cas.
`drop_return_outliers` retire les rendements hors des bornes déclarées dans
`config.yaml`, ce qui attrape le premier. **Ces deux bornes ont été écrites APRÈS avoir vu
les données**, et la règle du laboratoire veut que ce soit dit. Ce n'est pas un paramètre de
stratégie choisi sur un résultat, c'est un garde-fou de qualité de données posé après trois
inspections nommées. Les comptes retirés sont publiés dans
`results/tables/return_quality.csv`.

## Les décisions de construction, et ce qu'elles coûtent

**Quatre composantes, pas trois.** La consigne offrait un repli sur les portefeuilles triés
de Kenneth French, qui couvrent la rentabilité, l'investissement et le bêta depuis 1963 mais
ignorent la distribution. Les jeux de la SEC portent les vingt et une variables des quatre
composantes, donc la construction complète a été menée. Le repli à trois composantes est
tout de même publié, parce qu'il apporte ce que la construction complète ne peut pas
apporter : soixante-trois années sans biais du survivant.

**Onze années, et c'est la donnée qui l'impose.** Les jeux trimestriels de la SEC commencent
au deuxième trimestre 2009. Six des vingt et une variables demandent cinq exercices
d'historique, donc la première formation possible tombe à la mi-2015. La restriction est
déclarée dans `config.yaml` sous `construction_start`, et elle est la limite principale de
l'étude.

**L'univers survit par construction, et c'est mesuré.** La carte des symboles de la SEC est
celle d'aujourd'hui. Les sociétés radiées depuis 2015 n'y figurent plus, et le tableau
`results/tables/universe_coverage.csv` chiffre la perte. Le sens du biais est connu : la
jambe courte, celle de la camelote, perd ses pires membres, donc le facteur est
sous-estimé. Ce biais-là n'est pas réparable avec ces données ; celui du crible de taille
l'était, et la section suivante dit comment.

**La moyenne remplace la somme dans l'agrégation.** L'article somme les cotes de rang d'une
composante. Une banque ne déclare ni coût des ventes ni profit brut, donc sa cote de
rentabilité serait manquante et elle sortirait de l'univers. La composante se calcule donc
sur la moyenne des cotes renseignées, avec un plancher de variables écrit dans
`config.yaml`. L'écart est déclaré, et il est nul sur une ligne complète.

**L'indice des prix de la cote O vaut un.** Il entre par un logarithme commun à toutes les
sociétés d'une même date, donc il déplace toutes les cotes du même montant et ne change
aucun rang. Le test `test_l_indice_des_prix_ne_deplace_aucun_rang` le prouve plutôt que de
l'affirmer.

## Ce qui n'a pas été fait

**L'article publié n'a pas été lu.** Springer renvoie une page de protection anti-robot, et
les quatre autres voies essayées échouent. Toutes les définitions viennent de la version de
travail du 19 juin 2014. Novy-Marx et Medhat (2025) décrivent la version publiée avec TROIS
composantes, sans la distribution, ce qui contredit la version de travail et la page de
données d'AQR. La contradiction est déclarée et non tranchée.

**L'échantillon mondial n'est pas reconstruit.** Compustat Global exige un abonnement. La
jambe B ne couvre que les États-Unis, et la jambe A porte les vingt-quatre pays du facteur
publié.

**Aucun rendement de radiation n'est appliqué.** L'article impose moins trente pour cent aux
disparitions liées à la performance, à la manière de Shumway. Yahoo ne publie ni date ni
motif de radiation, donc la règle n'est pas reproductible et une société sans rendement sort
simplement de sa jambe.

## La contradiction du 2026-09-02, et les deux défauts qu'elle trouve

L'étude a été reprise de zéro par un second passage, dont la consigne était de la mettre en
défaut. Elle se reproduit à l'octet près : les vingt-neuf tableaux, les dix figures et
toutes les métriques sont identiques d'une exécution à l'autre, seul l'identifiant
d'expérience change. Deux défauts de fond ont pourtant été trouvés, et les deux sont
corrigés ici.

### Le premier, une fuite d'univers

**Le crible de taille ne s'appliquait pas à la section transversale.** Il servait à borner
la liste des symboles téléchargés, et cette liste est la RÉUNION des douze cribles annuels.
Le panneau gardait donc, dès juin 2015, les sociétés qui n'ont franchi le seuil de taille
qu'en 2020 ou en 2024.

**Le compte, mesuré.** En juin 2015, 257 des 1 159 sociétés du panneau, soit 22,2 pour
cent, n'appartenaient pas au crible de ce jour-là. La part tombe à 11,3 pour cent en 2026,
parce que la fenêtre de croissance restante se raccourcit. Sur toutes les dates, le crible
du jour retire 30 716 lignes sur 178 005.

**Ce que la fuite payait.** La comparaison est publiée dans
`results/tables/universe_screen_variant.csv` et comptée comme un essai. Sélectionner sur la
réunion des cribles rend 0,140 pour cent par mois et 0,161 de ratio de Sharpe, contre 0,130
et 0,152 pour le crible du jour. L'information future valait donc 7,5 pour cent du
rendement publié. Le sens est celui qu'on attend : une société entrée par un crible
postérieur est une société qui a grossi, donc une société dont la composante de croissance
devait payer.

**Le correctif.** Trois fonctions montent dans le module, `size_screens`, `screen_in_force`
et `apply_size_screen`. Le crible s'applique AVANT le passage par les rangs, sans quoi la
cote d'une société dépendrait de sociétés hors univers. Le test qui attrape le défaut est
`test_la_reunion_des_cribles_ferait_entrer_le_futur`. Il construit un registre de deux
sociétés dont l'une ne grossit qu'en 2016. Il exige ensuite que la réunion garde quatre
lignes là où le crible du jour n'en garde que deux.

### Le second, une convention de rotation

**La rotation se comptait en demi-somme.** Le module en fait son défaut, et cette lecture
convient à un coût facturé d'un seul côté. Le facteur, lui, achète d'un côté et vend de
l'autre, et chaque côté paie son écart.

**L'écart est exactement d'un facteur deux.** La rotation annualisée passe de 2,466 à
4,928, et le coût qui annule le rendement brut de 57,1 à 25,9 points de base. Le multiple
de coût survécu tombe de 5,706 à 2,590, contre un minimum exigé de 2,00 : le critère passe
encore, de peu.

**Pourquoi c'était un défaut et pas un choix.** Les études 003, 005, 006 et 008 passent
toutes `convention="full_sum"` sur des facteurs longs-courts. Celle-ci était la seule à
laisser le défaut du module, et rien dans son texte ne le disait.

### Les trois écarts de README trouvés au passage

Un, le balayage annonçait « douze cases pondérées par la valeur » et « huit à pondération
égale ». La grille en compte dix et dix, et le même README écrivait vingt lignes plus bas
« les dix cases pondérées par la valeur ». Deux, le R² ajusté de la régression à quatre
facteurs d'après publication était arrondi à 0,416 pour une valeur de 0,4155. Trois, le
tableau des coûts ne disait pas qu'il porte sur 131 mois et non 132, la rotation n'étant
pas définie au premier mois.

## Le cache, et ce qu'il change

Le premier lancement télécharge soixante-neuf archives de la SEC et les prix de mille cinq
cent quatre-vingt-trois titres. Les deux sont écrits sous `data/raw`, jamais commités, et
les lancements suivants n'y retouchent pas. Le programme reste déterministe : la graine vit
dans `config.yaml`, et le seul tirage aléatoire de l'étude, le rééchantillonnage par blocs,
passe par le générateur qu'elle construit.

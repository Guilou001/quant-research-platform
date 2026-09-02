# Journal de l'étude 001

Ce fichier porte ce que le README ne porte pas : les décisions prises en route, les
essais qui n'ont rien donné, et les trois choses qui ont surpris. Il est tenu dans
l'ordre des travaux, pas dans l'ordre du rapport.

## Ce qui a été décidé avant de coder

**Le plan en trois jambes vient d'une mesure, pas d'une préférence.** L'univers de fonds
négociés en bourse n'est complet qu'au 2007-04-11, date de la première cotation de HYG,
et l'échantillon de l'article s'arrête au 2009-12-31. Le chevauchement fait 36 mois. Une
réplication en échantillon est donc impossible, et une étude qui reconstruirait seulement
la stratégie ne saurait pas distinguer un défaut de code d'un affaiblissement du
phénomène. D'où la jambe A, qui mesure la série des auteurs, et la validation de la
jambe B contre elle.

**Les seuils du verdict ont été écrits dans `config.yaml` avant le premier
téléchargement.** Ils sont ceux du laboratoire, sans exception ni assouplissement.

| Seuil | Valeur |
|---|---:|
| Tolérance de réplication | 10 % |
| Sharpe hors échantillon minimal | 0,50 |
| t minimal après essais multiples | 3,00 |
| Ratio de Sharpe dégonflé minimal | 0,95 |
| Probabilité de surapprentissage maximale | 0,50 |
| Part de sous-périodes positives minimale | 0,60 |
| Multiple de coûts minimal | 2,00 |

## Les essais comptés, et pourquoi ce nombre

Le ratio de Sharpe dégonflé reçoit **73 essais**. Le compte se décompose ainsi.

| Origine | Nombre | Détail |
|---|---:|---|
| Grille formation contre détention | 64 | 8 formations par 8 détentions, tableau 2 de l'article |
| Variantes de volatilité | 5 | centres de masse de 20, 40, 60, 90 et 120 jours |
| Variantes de plafond de position | 2 | 3 fois et 5 fois le capital |
| Variante sans normalisation | 1 | la construction de Kim, Tse et Wald (2016) |
| Essai manuel | 1 | voir « L'essai manuel déclaré » ci-dessous |

Le centre de masse de 60 jours apparaît deux fois, une fois comme cellule de grille et
une fois comme variante. Le doublon est **gardé** dans le compte : sous-déclarer les
essais gonfle le ratio de Sharpe dégonflé, et c'est exactement le test que ce compte
sert à rendre honnête.

**L'essai manuel déclaré.** La configuration principale, formation de douze mois et
détention d'un mois, a été évaluée une fois avant que la date de fin ne soit fixée au
2026-06-30. Cette exécution portait un mois de juillet 2026 réduit à une seule séance,
et un ratio de Sharpe brut de 0,372 au lieu de 0,377. Elle compte comme un essai.

## Ce qui a échoué en route

**Un, la volatilité du paquet ne convenait pas.** `features.transforms.ewma_volatility`
existe et fait presque le bon calcul. Elle prend la moyenne exponentielle des carrés,
donc sans retrancher la moyenne pondérée, elle annualise par 252 et elle ne décale pas
d'un jour. L'article fait les trois autrement. La fonction a donc été écrite dans
`quantlab.strategies.time_series_momentum`, avec les trois écarts nommés dans sa
docstring. Ce n'est pas une seconde implémentation d'une même grandeur, c'est un autre
estimateur.

**Deux, la validation croisée combinatoire purgée était vide de sens à sa première
écriture.** La fonction recevait la série mensuelle nette figée, et mesurait son ratio de
Sharpe sur chaque chemin. Or les huit plis d'un chemin recouvrent l'échantillon entier,
donc les sept chemins rendaient sept fois le même nombre, 0,2120, à 3e-17 près. La
mesure a été refaite : à chaque segment, la cellule de grille est CHOISIE sur les plis
d'entraînement purgés, puis mesurée sur le pli de test. Le résultat devient une
distribution réelle, de médiane 0,166 et d'écart type 0,128, dont 28,6 % des chemins sont
négatifs. Une validation croisée qui rend sept fois le même nombre ne valide rien.

**Trois, les multiples de coûts partaient de zéro.** `cost_multiplier_analysis` refuse un
multiple nul, ce qui est juste : un multiple de zéro n'est pas un scénario de coût, c'est
le rendement brut, déjà publié ailleurs. La grille commence donc à 0,25.

**Quatre, une variante d'univers a été écartée avant de tourner.** Ajouter des fonds de
matières premières supplémentaires aurait rapproché le compte des 24 contrats de
l'article, mais aucun ne cote avant 2006 sans chevaucher DBC ou DBA. L'univers a été
laissé à 28, et l'écart avec les 58 contrats est déclaré dans « Les limites » du README.

## Le défaut qui n'aurait été vu par aucun test de forme

**Trente pour cent des mois disparaissaient en silence de chaque régression.**

L'index mensuel de la reconstruction était bâti sur la DERNIÈRE SÉANCE de chaque mois, ce
qui donne le 2013-01-31 pour janvier 2013 mais le 2015-01-30 pour janvier 2015. Le
facteur d'AQR et les facteurs de Kenneth French portent, eux, des fins de mois CIVILES.
Un `reindex` entre les deux ne lève aucune erreur : il rend des valeurs manquantes, que
le `dropna` de la régression retire ensuite.

Le tableau avait le bon nombre de colonnes, les bons noms, et des chiffres plausibles.
Seul le compte d'observations trahissait le défaut : 164 mois au lieu de 234, et 163
mois communs avec AQR au lieu de 233. Il a été trouvé en lisant la colonne `n_mois` du
tableau d'attribution, pas par un test.

Ce que le défaut changeait, mesuré en réexécutant l'étude avant et après la correction :

| Grandeur | Avant correction | Après correction |
|---|---:|---:|
| Mois retenus dans l'attribution | 164 | 234 |
| Mois communs avec le facteur d'AQR | 163 | 233 |
| Corrélation avec le facteur d'AQR | 0,747 | 0,760 |
| Bêta sur le facteur d'AQR | 1,007 | 0,983 |
| Cellules de grille à t positif | 11 | 25 ou 26 |
| t maximal de la grille | 1,555 | 2,496 |

La correction tient en une ligne : l'index mensuel est ramené à la fin de mois civile par
`to_period("M").to_timestamp("M")`, et la volatilité est prélevée à la dernière séance
puis réétiquetée. La leçon est celle de l'audit du 2026-08-31 : **un compte
d'observations se lit à chaque tableau, parce que c'est le seul chiffre qui trahit un
alignement muet.**

## Les trois choses qui ont surpris

**Un, le plafond de position améliore la performance nette.** L'article ne borne pas la
taille des positions, ce qui est sans conséquence sur des contrats à terme. Sur des fonds
cotés, la volatilité ex ante médiane de SHY vaut 1,09 %. La cible de 40 % y donne donc
une position de vingt-six fois les fonds propres. Plafonner à trois fois fait tomber le Sharpe
brut de 0,377 à 0,346 et **monter** le Sharpe net de 0,217 à 0,270. La raison est la
rotation annuelle, qui tombe de 9,15 à 4,22. C'est le seul réglage de l'étude qui améliore le
net, et il n'est pas dans l'article.

**Deux, la normalisation par la volatilité vaut plus que le signal.** Retirer la
normalisation, en gardant le même signe et la même équipondération, fait tomber le
ratio de Sharpe brut de 0,377 à 0,159. Le gain est donc divisé par 2,4 par une décision
de dimensionnement, alors que le signal ne change pas. C'est la thèse de Kim, Tse et
Wald (2016), mesurée ici sur notre univers.

**Trois, la structure de corrélation de l'article se retrouve intacte.** Les quatre
jambes de classe d'actif du facteur d'AQR sont faiblement corrélées entre elles, de -0,03
entre actions et taux à 0,39 entre devises et matières premières. Elles sont toutes plus
fortement corrélées à notre reconstruction, de 0,44 à 0,59. La matrice est écrite dans
`results/tables/correlations_classes_actifs.csv`. C'est
exactement le résultat que l'article qualifie de plus dérangeant : il existe une
composante commune aux stratégies de tendance qui n'existe pas dans les actifs
eux-mêmes.

## Ce que l'étude n'a pas fait, et pourquoi

**Les régressions groupées du premier étage.** Elles ne sont pas reproduites. L'objection
de Huang, Li, Wang et Zhou (2020) porte précisément sur leurs valeurs critiques, qu'ils
mesurent à 12,53 par amorçage paramétrique sauvage et à 4,83 par amorçage non
paramétrique, contre un t observé de 4,34. Reproduire une statistique dont on sait qu'on
ne peut pas la lire n'apprend rien. La jambe B mesure directement ce que la stratégie
rapporte, et la section « Chaque instrument, pris seul » du README mesure ce que les
régressions par actif diraient.

**Le jeu de données d'origine d'AQR sur 1985-2009.** AQR publie deux fichiers, celui de
l'article et la version prolongée. Le fournisseur du laboratoire ne connaît que le
second. Ajouter le premier demanderait d'écrire dans
`quantlab.data.providers.aqr`, hors du périmètre de cette étude. L'écart entre les deux
jeux reste donc **non mesuré**.

**La décomposition en autocovariance et carré de la moyenne.** L'article la publie, à
0,54 % et 0,29 % par mois. Elle n'a pas été reproduite, faute d'entrer dans l'une des
trois questions du plan.

## Le déterminisme, et la surprise qu'il a réservée

La graine vaut 20260902, elle est déclarée dans `config.yaml` et propagée par
`quantlab.core.determinism.make_generator`. Le code est déterministe : deux appels au
chargement des données dans le MÊME processus rendent des tableaux identiques au bit
près, sur les 8 411 lignes et les 28 colonnes.

**Trois exécutions complètes ne rendent pourtant pas les mêmes 38 métriques**, et il a
fallu chercher pourquoi. La cause n'est pas dans le code. Deux téléchargements du même
univers, sur les mêmes dates, à quelques minutes d'intervalle, rendent **115 150
cellules différentes sur 235 508**, avec un écart maximal de 1,8e-4 sur des prix de
l'ordre de cent. Les écarts sont des puissances de deux : les prix ajustés arrivent
quantifiés en simple précision, et l'arrondi n'est pas le même d'une requête à l'autre.

Ce que cela déplace, mesuré sur trois exécutions.

| Grandeur | Valeur |
|---|---|
| Métriques identiques au dernier chiffre | 13 sur 38 |
| Écart relatif médian des vingt-cinq autres | 1,0e-5 |
| Métriques dont l'écart relatif dépasse 1 % | 4 |

Les quatre sont des basculements sur une quasi-égalité, pas des dérives. Le compte de
cellules de grille à t positif vaut 25 ou 26, parce que la cellule (1, 48) porte un t de
quelques millièmes. Les trois autres sont l'écart type, le minimum et la médiane de la
validation croisée, dont la sélection de configuration change quand deux cellules sont à
égalité sur un segment d'entraînement.

**Ce qui a été décidé.** Ne pas figer la source. Un instantané commité rendrait l'étude
reproductible au bit près et non régénérable, ce qui est le contraire de l'objectif du
laboratoire. La fourchette est publiée à la place, et les quatre métriques concernées
sont nommées dans le README.

**La leçon, écrite pour les études suivantes.** Un test de déterminisme qui ne compare
que deux appels dans le même processus ne prouve rien sur la reproductibilité d'une
étude. Il faut comparer deux exécutions complètes, et quand elles diffèrent, chercher la
cause en amont du code avant d'accuser le code.

Le contrôle de causalité de `features.transforms.assert_causal` tourne à chaque
exécution sur la volatilité ex ante, avant toute mesure de performance. Un échec
arrêterait l'étude avant qu'un seul chiffre ne soit écrit.

## La contre-vérification du 2026-09-02

Un second agent a repris l'étude pour la mettre en défaut. Ce qu'il a trouvé, et ce qui
a été corrigé.

**Un, quatorze chiffres du README ne venaient pas de `results/`.** Le tableau de
performance de la jambe B portait des rendements annualisés et des pires replis d'une
exécution antérieure : 5,04 % au lieu de 5,13 % sur la fenêtre entière, -31,84 % au lieu
de -31,71 %, -36,01 % au lieu de -35,86 %. Le README se contredisait lui-même, sa section
des sous-périodes annonçant déjà -35,86 % comme pire repli de l'étude. Sept autres écarts
du même genre suivaient. Les deux Sharpe d'avant publication de la section « Le hors
échantillon ». La variance des Sharpe des essais. Le Sharpe de la cellule (12, 1) en
marche en avant. Le Sharpe net de la position plafonnée à cinq fois. Et la part de
l'exposition brute portée par SHY. Tous refaits depuis les fichiers.

**Deux, une plage de corrélations était fausse par omission.** Le README et ce journal
annonçaient des corrélations de classes « de 0,07 à 0,39 ». La plus basse des six paires
est celle des actions et des taux, à -0,03, et elle est NÉGATIVE. La matrice n'était
écrite dans aucun fichier, donc rien ne pouvait contredire le texte : `run.py` écrit
désormais `correlations_classes_actifs.csv`.

**Trois, la promesse de reproductibilité était trop large.** Le README affirmait que tout
chiffre donné à trois décimales se reproduit. Mesuré sur deux exécutions complètes, 13
des 64 statistiques t de la grille changent à la deuxième décimale et 16 à la troisième,
l'écart le plus grand valant 0,021. Le score de plateau et l'isolement bougent de la
même façon. La cause n'est pas un arrondi : c'est le signe d'un cumul qui frôle zéro, et
qui renverse une position entière pour un écart de prix de 2e-6. La promesse est
restreinte aux 38 métriques de `metrics.json`, et la grille est déclarée reproductible à
la première décimale.

**Quatre, deux écarts n'étaient pas déclarés.** L'univers est composé de survivants et il
est choisi en 2026 : un fonds fermé entre 2007 et aujourd'hui ne pouvait pas y entrer, et
le biais joue en faveur de la reconstruction. Le ratio de Sharpe dégonflé, lui, mélange
un Sharpe observé NET sur 169 mois et une variance entre essais mesurée sur des Sharpe
BRUTS sur 234 mois. Les deux sont désormais écrits, le premier comme huitième écart, le
second comme dixième limite.

**Cinq, le compte des lectures du holdout était faux.** Le README annonçait une seule
lecture. Chaque exécution de `run.py` mesure le holdout, donc il a été lu une douzaine de
fois. Ce qui vaut protection n'est pas le compte mais l'absence d'ajustement, et c'est ce
que le texte dit maintenant.

**Ce qui a résisté.** Le verdict `EXPERIMENTAL` et ses dix-sept raisons se reproduisent à
l'identique. Les 38 métriques de `metrics.json` se reproduisent, 13 au dernier chiffre et
les autres à 1,7e-5 en médiane, avec les quatre exceptions déjà nommées. Le compte de 73
essais a été refait poste par poste et il tient. Le ratio de Sharpe dégonflé vaut 0,309 à
64 essais et 0,262 à 145, donc aucun recomptage plausible ne le rapproche du seuil de
0,95. La chasse à la fuite n'a rien donné. Le décalage d'exécution vaut un partout, la
volatilité est décalée d'un jour de plus, et aucune statistique de normalisation n'est
calculée sur l'échantillon entier. Le test qui garde ce décalage échoue bien quand on
retire le décalage, vérifié en le retirant.

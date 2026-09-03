# Journal de l'étude 008, le portage

Ce fichier tient la trace de ce qui a été essayé, dans l'ordre, y compris ce qui
a échoué. Les essais de performance sont comptés dans
`results/tables/trials.csv` ; ce journal porte le reste, les impasses de données
et les défauts d'implémentation.

## 1. Le repérage des données, avant toute mesure de performance

**Ce que FRED donne pour le change.** Dix séries quotidiennes répondent, toutes
depuis le 4 janvier 1971 sauf l'euro qui part du 4 janvier 1999. Le sens de
cotation change d'une série à l'autre, et c'est le premier piège de l'étude.
`DEXUSUK`, `DEXUSAL`, `DEXUSNZ` et `DEXUSEU` cotent des dollars par unité
étrangère. `DEXJPUS`, `DEXCAUS`, `DEXSZUS`, `DEXNOUS`, `DEXSDUS` et `DEXDNUS`
cotent l'inverse.

**Ce que FRED donne pour les taux courts.** La famille `IR3TIB01` de l'OCDE
couvre les onze zones, mais pas sur les mêmes périodes. Mesuré le 2026-09-02 :
Canada depuis 1956-01, Royaume-Uni 1957-01, États-Unis 1964-06, Australie
1968-01, Nouvelle-Zélande 1973-12, Norvège 1979-01, Suède 1982-01, Danemark
1987-01, zone euro 1994-01, Suisse 1999-07 et Japon 2002-04.

**Le problème que cela pose.** Le yen et le franc suisse sont les deux monnaies
de financement classiques du portage, et ce sont les deux dernières à entrer.

**Quatre identifiants essayés et refusés par FRED**, tous en 404 :
`IR3TBB01JPM156N`, `JPNIR3TIB01STSAM`, `IR3TIB01JPM156Q` et `IR3TIB01CHM156Q`.

**Trois séries japonaises trouvées et écartées du cas de référence.**
`INTGSTJPM193N` s'arrête en 2017-06. `IRSTCB01JPM156N` s'arrête en 2023-12.
`IRSTCI01JPM156N` part de 1985-07 et suit l'argent au jour le jour, pas le trois
mois. La seule série longue et proche est `IR3TCD01JPM156N`, les certificats de
dépôt, de 1979-05 à 2022-03.

**La décision, et pourquoi.** Le cas de référence garde UNE famille
d'instruments pour les onze zones, quitte à ce que le yen n'entre qu'en 2002.
Une variante déclarée rallonge le yen et le franc suisse par un autre
instrument, uniquement AVANT le premier point de la série de référence. La
variante mesure ce que le choix coûte, et le résultat est publié dans
`results/tables/rate_source_variant.csv`.

## 2. Les trois classes d'actifs cherchées et non trouvées

Recherche menée le 2026-09-02, résultat consigné dans
`results/tables/asset_classes_not_reproducible.csv`.

**Matières premières.** Quatre pistes suivies. Les séries de `turtletrader.com`
sont gratuites et remontent aux années 1970, mais ce sont des contrats continus
ajustés, donc une seule échéance par date. La base des prix de la Banque
mondiale publie des prix au comptant mensuels depuis 1960 et aucun prix à terme.
Le Cboe ne diffuse l'historique que de ses propres contrats. La base `CHRIS` de
Nasdaq Data Link, celle qui donnait les contrats continus numérotés, n'est plus
accessible librement depuis la reprise de Quandl par Nasdaq.

**Indices actions.** Le portage exige le dividende ATTENDU sur le mois à venir.
Les indices `^DVS` et `^DIVD` de Yahoo Finance donnent le dividende VERSÉ, et
seulement pour le S&P 500. Les contrats sur dividendes du CME existent, mais
leur historique libre ne remonte pas à 1988 et ne couvre pas treize marchés.

**Options.** OptionMetrics est la source nommée par l'article, et elle est
vendue sous licence. Aucun équivalent gratuit ne remonte à 1996 avec les deux
groupes de delta exigés.

**Ce qui a été refusé.** Approcher le portage des matières premières par l'écart
entre deux contrats continus de rangs différents. Cet écart existe chez certains
fournisseurs, mais son mode de report est inconnu, donc le nombre obtenu ne
serait pas le portage de l'article. La consigne était de documenter le manque
plutôt que d'en fabriquer une approximation.

## 3. Ce qui a été écrit avant de voir un seul résultat

`config.yaml` a été écrit et validé par `ExperimentConfig` avant toute mesure de
performance. Il portait déjà les huit seuils du verdict, les cinq fenêtres de
crise nommées, les trois coupures de sous-période et la tolérance de réplication
à 0,50 avec sa justification.

La seule information connue à ce moment était la couverture des séries FRED,
relevée le même jour, et les valeurs publiées par l'article.

## 4. Les défauts d'implémentation trouvés en route

**Un masque manquant, et c'est le défaut le plus grave.** La première version
construisait le portage dès que les deux taux existaient, sans vérifier que le
change était coté. Conséquence mesurée : le portefeuille commençait en février
1968, trois ans avant la première cotation de change, et cinq devises recevaient
un poids sans rendement possible. L'euro aurait reçu un poids dès janvier 1994,
cinq ans avant sa première cotation. Le signal est désormais masqué par la
disponibilité du change à la date de formation, et l'échantillon passe de 700 à
664 mois.

**Une identité brisée de 1,08e-3, attrapée parce qu'elle était PUBLIÉE.** La
première version de `dollar_decomposition` calculait le panier de devises par
une moyenne qui saute les valeurs manquantes, tandis que la jambe neutre
comblait ces mêmes valeurs par zéro. La somme des deux jambes ne redonnait donc
plus le rendement total, l'écart valant 1,08e-3 sur trois cellules du panel. Le
défaut n'apparaissait sur AUCUN test, les données de test n'ayant pas de valeur
manquante. Il a été vu parce que la colonne `identity_max_error` est écrite dans
`results/tables/dollar_legs.csv`. Un test a été ajouté avec un rendement
manquant, et vérifié en réintroduisant le défaut : il rend 1,0e-3 au lieu de
1,4e-17.

**Deux définitions de la rotation dans la même étude.** La première version
calculait le coût net par `LinearCostModel` sur les poids décalés, sans dérive,
et le seuil de rentabilité par `turnover_series` avec dérive. Les deux chiffres
étaient donc légèrement incohérents. Une seule définition subsiste, la rotation
dérivée en somme entière, décalée du délai d'exécution, et elle alimente les
deux.

**Trois pièges d'interface, sans conséquence sur les chiffres.** Une condition
booléenne de forme `(n, 1)` passée à `DataFrame.where` lève au lieu de se
diffuser, et la multiplication par une série booléenne la remplace. La colonne
des profondeurs de `drawdown_table` s'appelle `depth` et non `drawdown`.
`cost_multiplier_analysis` refuse un multiple nul, qu'il faut filtrer avant
l'appel.

## 5. Les cinq mutations rejouées

Chaque contrôle qui garde une propriété a été validé en réintroduisant le défaut
qu'il prétend attraper.

| Mutation | Test qui tombe |
|---|---|
| `shift(execution_lag)` remplacé par `shift(0)` | perturbation du futur |
| Les deux branches de `to_usd_per_unit` échangées | signe du rendement d'une devise qui s'apprécie |
| Le portage écrit `local - étranger` | valeur exacte de l'équation (7) |
| La correction d'échantillon fini retirée de l'erreur type groupée | couverture du coefficient contre un |
| Le panier calculé par une moyenne qui saute les manquants | identité des deux jambes |

## 6. Les essais non retenus, et pourquoi

**Le facteur mondial de portage n'a pas été construit.** Il exige les neuf
classes de l'article, et il pondère chaque classe par sa volatilité de PLEIN
échantillon, ce qui est un regard en avant.

**Aucune erreur type de Newey-West n'a été calculée sur le portefeuille.**
L'article emploie des écarts types groupés par date dans son panel, et c'est ce
que nous employons. La correction d'autocorrélation du ratio de Sharpe est
disponible par l'erreur type de Lo, publiée dans
`results/tables/subperiods.csv`.

**Aucun tableau de marche en avant n'a été produit.** La validation croisée
combinatoire purgée et la probabilité de surapprentissage couvrent la même
question, et elles jugent le processus de sélection plutôt qu'une série figée.

**Le repère passif n'était pas un contrôle de réplication.** Son ratio de Sharpe
tombe à 0,391 contre 0,36 publié, mesuré sur la fenêtre de l'article, et le
chiffre n'a été regardé qu'après coup. Il ne compte donc pas dans le verdict, et
il est publié dans `results/tables/replication_table2.csv`.

## 7. Le compte des essais

Trente-trois essais. Neuf cellules de balayage, cinq taux de coût, six
multiples, quatre spécifications de panel, trois délais et deux jambes. Puis une
variante de taux, une variante de numéraire, un comparateur de momentum et une
substitution obligataire. Le compte est vérifié à l'exécution contre celui
déduit des grilles, et un écart lève une erreur de configuration.

Vingt-neuf de ces trente-trois portent un ratio de Sharpe, et ce sont les seuls
qui entrent dans la variance du ratio de Sharpe dégonflé. Les quatre autres sont
les spécifications de panel, dont la mesure est une statistique t.

## 8. La reproduction

Deux exécutions consécutives ont été comparées le 2026-09-02, répertoire par
répertoire. Les 25 tableaux de `results/tables` sont identiques au fichier près,
et `results/metrics.json` ne diffère que par l'identifiant d'expérience.

## 9. Ce que l'audit contradictoire du 2026-09-02 a trouvé

Une étude rendue a été relancée de zéro, ses tableaux confrontés un à un au
texte, et sa causalité éprouvée par troncature. Quatre constats, dans l'ordre de
gravité.

**Un, le dollar était classé comme un actif, et l'écart n'était pas déclaré.**
L'article classe des contrats de change, tous libellés contre le dollar, donc le
dollar n'y est pas classable. Notre panel lui donnait une colonne de portage nul,
qui lui valait un rang et un poids. Trois conséquences mesurées et publiées dans
`results/tables/numeraire_variant.csv`. L'asymétrie de l'échantillon complet passe
de -0,570 à **+0,253** quand la colonne sort, donc elle change de SIGNE pour un
ratio de Sharpe inchangé, 0,525 contre 0,532. Le coefficient de panel de la
fenêtre de l'article tombe de 1,084 à 0,897 et son t de 2,159 à 1,700, donc la
parité non couverte n'y est plus rejetée à 5 %. Et la série perd 35 mois, le
dollar comptant dans le plancher de quatre actifs. Trois tests neufs gardent la
propriété, tous validés en retirant le numéraire du classement.

**Deux, la variance des essais mélangeait deux échelles.** Les quatre
spécifications de panel étaient enregistrées avec leur statistique t là où le
registre attend un ratio de Sharpe. La variance des essais valait donc 0,7347 au
lieu de 0,0118, soit 62 fois trop, et le ratio de Sharpe dégonflé sortait à
6,8e-91 au lieu de **0,121**. Aucun test de forme ne pouvait le voir, les deux
grandeurs étant des flottants finis. Le registre est désormais dédoublé, l'un
pour le compte, l'autre pour la variance.

**Trois, le rééchantillonnage par blocs tronquait ses blocs.** Un bloc tiré près
de la fin rendait moins de douze mois, si bien que 46 % des tirages étaient plus
courts que les 164 mois d'origine et que le premier mois pesait 8,3 % de la
moyenne. Les blocs sont maintenant circulaires, et l'intervalle passe de
[-1,17 % ; +2,80 %] à [-1,28 % ; +2,75 %].

**Quatre, les sept chemins de validation croisée n'en sont que trois.** Le
processus de sélection retient le tri par rang sur signal brut dans presque tous
les blocs, donc les chemins se répètent à l'identique. Le nombre de valeurs
distinctes est désormais publié à côté de l'écart type.

**Ce que l'audit n'a PAS trouvé.** Aucune fuite. La chaîne complète a été
tronquée à quatre dates, 1995-12, 2005-12, 2012-09 et 2020-12, et le passé commun
est identique au bit près, écart maximal 0,000e+00. Perturber le signal après
janvier 2000 laisse le passé inchangé, écart 0,000e+00. Les 704 jetons numériques
du texte se retrouvent dans `results/` ou dans `config.yaml`, à deux exceptions
nommées, un fragment de DOI et une différence calculée dans la phrase même. Les
dix sens de cotation sont vérifiés contre
un fait extérieur, le yen valant 0,006251 dollar et la livre 1,3555 dollar au
2026-08-31. Deux exécutions consécutives rendent des tableaux identiques au
fichier près.

## Défaut trouvé le 2026-09-02, corrigé le 2026-09-03

La série `fx_carry_gross` n'a pas d'avril 2020. Cause mesurée : le taux
interbancaire américain à trois mois de la FRED, `IR3TIB01USM156N`, est
manquant pour 2020-04, et le portage de chaque devise se calcule contre ce
taux de base, donc les onze signaux sont manquants ce mois-là. Corrigé le
2026-09-03 : un trou d'au plus un mois est comblé par le taux du mois
précédent, `max_gap_fill_months: 1` dans la configuration, chaque report étant
publié. Deux reports en tout, avril 2020 et le rendement obligataire
néo-zélandais de septembre 1979. Vingt métriques ont bougé à la deuxième ou
troisième décimale, le ratio de Sharpe net hors échantillon passant de 0,144 à
0,132 et le Sharpe dégonflé de 0,149 à 0,121 ; le verdict est inchangé.

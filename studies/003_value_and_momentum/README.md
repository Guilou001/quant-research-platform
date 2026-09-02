# Valeur et momentum, partout

## La question de recherche

Le mélange de la valeur et du momentum doit-il son ratio de Sharpe à ses deux jambes, ou à la
corrélation négative qui les sépare ?

**La réponse, en trois phrases.** La corrélation fait presque tout, et elle se chiffre exactement.
Sur les 654 mois de la paire toutes classes d'actifs, la valeur rend un ratio de Sharpe de **0,412**
et le momentum de **0,593**. Leur mélange à parts égales rend **1,096**, soit 0,503 de plus que la
meilleure des deux jambes. Une corrélation de **-0,577** multiplie par **1,538** ce qu'un mélange
de deux jambes indépendantes aurait rendu, et cette prédiction coïncide avec la mesure à
**5,6e-16** près.

Ces chiffres viennent de `results/tables/pairs_full_sample.csv` et de
`results/tables/formula_check.csv`. Échantillon `VALIDATION`, brut de frais, janvier 1972 à juin 2026,
facteurs publiés par AQR.

**La réponse à la question du laboratoire.** Une unité de corrélation négative vaut **1,293** de ratio
de Sharpe au point mesuré, et la relation n'est pas linéaire. Le gain s'accélère quand la corrélation
descend, si bien que passer de -0,3 à -0,4 rapporte moins que passer de -0,7 à -0,8. La formule est
écrite plus bas et sa dérivée est vérifiée par différence finie.

**Ce que l'étude trouve et que l'article ne dit pas.** Notre jambe B, bâtie sur les portefeuilles
triés de Kenneth French, rend une corrélation de **-0,168** sur les 475 mois de la fenêtre de
l'article, là où celle d'AQR rend **-0,623** sur les 474 mois qu'elle couvre dans cette même fenêtre
(`results/tables/mechanical_correlation.csv`). Les deux séries ne commencent pas le même mois, la
jambe américaine d'AQR débutant en février 1972. Le ratio comptable de Kenneth French
emploie une capitalisation de décembre de l'année précédente. Le gain de diversification tient donc
en grande partie à la date du prix employé dans le signal de valeur.

**Le verdict est `EXPERIMENTAL`**, et non plus haut. Deux raisons, toutes deux publiées ci-dessous :
un contrôle de réplication sur onze échoue, celui des obligations d'État, et le résultat hors
échantillon ne survit pas au compte de 207 essais.

## L'article

Asness, C. S., Moskowitz, T. J. et Pedersen, L. H. (2013), « Value and Momentum Everywhere »,
*The Journal of Finance* 68(3), 929-985, DOI 10.1111/jofi.12021.

La version publiée a été lue le 2026-09-01 à l'adresse
`w4.stern.nyu.edu/facdir/lpederse/papers/ValMomEverywhere.pdf`. Les chiffres cibles sont recopiés dans
`docs/literature/asness_moskowitz_pedersen_2013.md`. Statut de ces chiffres : **rapportés**.

Trois travaux encadrent la lecture, et l'étude les prend au sérieux.

| Auteurs | Revue | Ce qu'ils opposent |
|---|---|---|
| Les auteurs eux-mêmes, page 950 | *Journal of Finance* | Retarder d'un an le prix du ratio comptable fait passer la corrélation de -0,53 à -0,28. |
| Dobrynskaya (2018) | *Finance Research Letters* 25 | Le modèle à trois facteurs n'apporte rien à l'intérieur d'une classe d'actif. |
| Daniel et Moskowitz (2016) | *Journal of Financial Economics* 122 | Le momentum s'effondre par crises, dans les états de panique. |

## L'intuition économique

Le gain du mélange vient de ce que les deux signaux prennent des positions opposées sur la même
information de prix, tout en étant tous deux rémunérés.

Le momentum achète ce que tout le monde vient d'acheter, donc il tient les positions les plus
encombrées. Quand un choc de financement force des ventes, la pression de prix frappe d'abord ces
positions, parce que tous sortent par la même porte au même moment. La valeur est contrarienne, donc
moins encombrée, et elle gagne là où le momentum perd. Les auteurs mesurent ce chargement de signe
opposé aux pages 958 à 964.

**Ce qui ferait disparaître le gain.** Trois extinctions, dans l'ordre de vraisemblance. La première
est arithmétique et les auteurs la nomment : le ratio comptable porte le prix courant au dénominateur
et le momentum le porte au numérateur, si bien qu'un titre qui monte devient simultanément cher et
gagnant. La deuxième est la disparition de la prime d'une des deux jambes. La troisième est le coût de
rotation. L'étude mesure la première et chiffre la troisième.

## La définition mathématique

Le poids du titre \(i\) pour le signal \(S\), équation (1) de la page 938 :

\[ w^{S}_{it} = c_t \left( \operatorname{rang}(S_{it}) - \frac{\sum_i \operatorname{rang}(S_{it})}{N} \right) \]

La constante \(c_t\) met le portefeuille à un dollar acheté et un dollar vendu. Le mélange à parts
égales est la moyenne simple des deux jambes :

\[ r^{mix}_t = 0{,}5\, r^{val}_t + 0{,}5\, r^{mom}_t \]

Le ratio de Sharpe d'un mélange à deux jambes se lit en forme fermée :

\[ S_{mix} = \frac{w \sigma_1 S_1 + (1-w) \sigma_2 S_2}{\sqrt{w^2 \sigma_1^2 + (1-w)^2 \sigma_2^2 + 2 w (1-w) \rho \sigma_1 \sigma_2}} \]

**Le cas qui porte l'étude.** Quand le poids égalise les deux contributions au risque, c'est-à-dire
quand \(w = \sigma_2 / (\sigma_1 + \sigma_2)\), les volatilités se simplifient et il reste :

\[ S_{mix} = \frac{S_1 + S_2}{\sqrt{2 + 2\rho}} \]

Trois nombres suffisent alors. Le multiplicateur de diversification, le rapport de ce ratio à ce
qu'il vaudrait si les deux jambes étaient indépendantes, vaut \(1/\sqrt{1+\rho}\). Sa dérivée par
rapport à la corrélation, la réponse à la question du laboratoire, vaut :

\[ \frac{\partial S_{mix}}{\partial \rho} = -\frac{S_1 + S_2}{(2 + 2\rho)^{3/2}} = -\frac{S_{mix}}{2(1+\rho)} \]

La dérivée est négative, donc rendre la corrélation plus négative augmente le ratio de Sharpe. Sa
valeur absolue croît quand la corrélation descend, ce qui rend le gain non linéaire.

## Les données

Deux sources, toutes deux gratuites, aucune reconstruction possible du côté d'AQR. Source :
`results/tables/data_sources.csv`.

| Source | Fichier | Table | Première date | Dernière date | Lignes |
|---|---|---|---|---|---:|
| AQR | Value-and-Momentum-Everywhere-Factors-Monthly | VME Factors | 1972-01-31 | 2026-06-30 | 654 |
| Kenneth French | F-F_Research_Data_Factors | mensuel | 1926-07-31 | 2026-06-30 | 1 200 |
| Kenneth French | F-F_Momentum_Factor | mensuel | 1927-01-31 | 2026-06-30 | 1 194 |
| Kenneth French | 25_Portfolios_5x5 | rendements pondérés | 1926-07-31 | 2026-06-30 | 1 200 |
| Kenneth French | 25_Portfolios_ME_Prior_12_2 | rendements pondérés | 1927-01-31 | 2026-06-30 | 1 194 |
| Kenneth French | 10_Portfolios_Prior_12_2 | rendements pondérés | 1927-01-31 | 2026-06-30 | 1 194 |

**Comment lire ce tableau, en trois constats.** Un, le classeur d'AQR porte les facteurs de l'article
eux-mêmes, reconstruits et prolongés jusqu'en juin 2026, alors que l'article s'arrête en juillet 2011.
Deux, la bibliothèque de Kenneth French remonte à 1926 et permet de bâtir une paire indépendante sur
un demi-siècle de plus. Trois, aucune des huit bases d'origine de l'article n'est gratuite, donc la
jambe A vérifie les facteurs publiés sans pouvoir les reconstruire.

**Ce que ces données ne sont pas.** Elles ne sont pas point-in-time. AQR écrit dans son propre
classeur qu'il reconstruit toute l'histoire à chaque mise à jour, et Kenneth French révise ses séries
à chaque millésime de CRSP. Les portefeuilles de Kenneth French sont en revanche bâtis sur l'univers
CRSP complet, radiations comprises, donc sans biais du survivant. La règle d'univers d'AQR n'est pas
publiée et son manifeste laisse le champ indéterminé plutôt que flatteur.

**Un défaut de la source, mesuré, que le fichier ne signale pas.** Les colonnes hors actions du
classeur d'AQR s'arrêtent au 31 janvier 2025, alors que la colonne agrégée « EVERYWHERE » court
jusqu'au 30 juin 2026. Les dix-sept derniers mois de cette colonne ne portent donc que les quatre
marchés d'actions. La composition de la série change sans avertissement, et la section « Le hors
échantillon » chiffre ce que cela coûte.

Couverture par paire, mesurée dans `results/tables/pair_coverage.csv`.

| Paire | Mois | Début | Fin | Mois dans la fenêtre de l'article |
|---|---:|---|---|---:|
| Toutes classes d'actifs | 654 | 1972-01-31 | 2026-06-30 | 475 |
| Actions, agrégat | 653 | 1972-02-29 | 2026-06-30 | 474 |
| Hors actions, agrégat | 637 | 1972-01-31 | 2025-01-31 | 475 |
| Actions américaines | 653 | 1972-02-29 | 2026-06-30 | 474 |
| Actions britanniques | 540 | 1981-07-31 | 2026-06-30 | 361 |
| Actions européennes | 540 | 1981-07-31 | 2026-06-30 | 361 |
| Actions japonaises | 540 | 1981-07-31 | 2026-06-30 | 361 |
| Indices actions par pays | 575 | 1977-03-31 | 2025-01-31 | 413 |
| Devises | 553 | 1979-01-31 | 2025-01-31 | 391 |
| Obligations d'État | 505 | 1983-01-31 | 2025-01-31 | 343 |
| Matières premières | 637 | 1972-01-31 | 2025-01-31 | 475 |
| Les quatre paires de la jambe B | 1 194 | 1927-01-31 | 2026-06-30 | 475 |

**Comment lire ce tableau, en trois constats.** Un, les huit marchés commencent entre 1972 et 1983, ce
qui interdit de lire l'agrégat mondial comme un panneau équilibré avant janvier 1983. Deux, les trois
marchés d'actions hors États-Unis ne commencent qu'en juillet 1981 pour leur jambe de valeur, alors
que l'article annonce 1972 et 1974. Trois, la jambe B porte 1 194 mois, soit deux fois et demie la
fenêtre de l'article, ce qui donne un échantillon indépendant de sa période.

## La méthodologie originale

L'article classe des titres, coupe en trois groupes égaux, et publie deux constructions.

Le momentum est identique dans les huit marchés, le rendement cumulé des douze derniers mois en
sautant le mois le plus récent. La valeur reçoit une définition par classe d'actif, cinq en tout, et
c'est le ratio de la valeur comptable sur la valeur de marché pour les actions. La valeur comptable
est retardée de six mois pour garantir sa disponibilité, la valeur de marché est prise à la date
courante.

Les portefeuilles sont pondérés par la capitalisation pour les actions et à poids égaux ailleurs. Les
auteurs rapportent l'écart entre le groupe haut et le groupe bas, puis un portefeuille pondéré par le
rang, qu'ils appellent facteur. Les moyennes mondiales pondèrent chaque marché par l'inverse de son
écart type d'échantillon, note 11 page 945.

Aucune performance de l'article n'est nette de coûts de transaction, et les auteurs l'écrivent page
976.

## Notre implémentation

La logique vit dans `src/quantlab/strategies/value_momentum.py`, et `run.py` ne fait qu'orchestrer. Le
module sépare quatre objets que la lecture courante mélange.

**La construction d'une jambe.** `rank_weighted_factor` applique l'équation (1) à des portefeuilles
déjà triés, les poids étant alors constants dans le temps. `high_minus_low` rend l'écart entre le
groupe le mieux classé et le moins bien classé. Les deux constructions coïncident exactement sur deux
groupes, et un test le vérifie.

**Le mélange.** `blend_returns` porte un poids fixe ou une série de poids. `risk_parity_weights` rend
le poids qui égalise les deux contributions au risque, dans deux versions déclarées. La version de
plein échantillon emploie l'écart type de toute la période, elle sert de repère théorique et elle
n'est pas tenable. La version en expansion calcule les deux écarts types sur les mois 1 à \(t-1\) puis
décale d'un mois.

**Le diagnostic.** `pair_diagnostics` rend une ligne complète par paire, et il ne calcule aucune
métrique lui-même. Le ratio de Sharpe vient de `quantlab.analytics.ratios`, la volatilité de
`quantlab.analytics.risk`, la rotation de `quantlab.analytics.turnover`.

**La théorie.** `two_asset_sharpe`, `equal_risk_sharpe`, `diversification_multiplier` et
`sharpe_sensitivity_to_correlation` portent les quatre formules de la section précédente. La dérivée
est vérifiée contre la différence finie centrée à 1e-6.

**L'absence d'information future se prouve par troncature.** Le mélange à parts égales n'estime rien,
donc il ne peut pas regarder en avant. Le mélange à risque égal estime deux écarts types, et deux
tests portent sa causalité. Le premier perturbe un mois du milieu et exige que le poids de CE mois ne
bouge pas. Le second retire la fin de l'échantillon et exige que tous les poids passés restent
identiques, avec son contrôle inverse qui exige que le poids de plein échantillon, lui, se déplace.

**Le contrôle par mutation.** Quatre défauts ont été réintroduits à la main dans le module, puis les
cinquante tests relancés. Retirer le décalage d'un mois fait échouer un test, remplacer
\(2 + 2\rho\) par \(1 + \rho\) en fait échouer cinq, mettre la dérivée à la puissance un demi au lieu
de trois demis en fait échouer deux, et retirer la constante de mise à l'échelle des poids de rang en
fait échouer cinq.

Aucun paramètre ne vit dans le code. Le fichier `config.yaml` porte les 11 poids de mélange, les 4
fenêtres de risque égal et les 3 fenêtres de corrélation glissante. Il porte aussi les 3 quantiles de
tension, les 4 pas de rééquilibrage et les 3 délais d'exécution. Il porte enfin les 4 taux de coût,
les 7 multiples de coût et les 8 seuils du verdict.

## Nos écarts avec l'article

**Nous employons les facteurs publiés d'AQR et non ceux de l'article.** Le classeur écrit lui-même que
la construction suit l'article mais que les sources et la méthode peuvent différer. Il reconstruit
aussi toute l'histoire à chaque mise à jour. L'écart sur les obligations d'État, chiffré plus bas,
peut venir de là, et nous ne savons pas le séparer d'une différence de définition de la valeur
obligataire.

**Notre échantillon va jusqu'en juin 2026 et non jusqu'en juillet 2011.** Toute comparaison directe
avec la table I est donc faite sur la fenêtre restreinte, et le tableau de réplication le déclare
ligne par ligne.

**Notre jambe B n'est pas la construction de l'article.** Trois différences la séparent de la jambe A.
L'univers est CRSP entier plutôt que les titres qui cumulent 90 % de la capitalisation. Le prix du
ratio comptable est celui de décembre de l'année précédente plutôt que celui du mois courant. Les
portefeuilles sont ceux de Kenneth French, en 2 fois 3 ou en 5 fois 5, plutôt qu'un tri en trois
groupes égaux. L'étude n'isole aucune de ces trois différences, et la section des résultats le dit.

**Nous n'employons pas la moyenne pondérée par l'inverse de la volatilité pour agréger les marchés.**
Nous lisons les trois colonnes agrégées d'AQR telles qu'elles sont publiées. La note 11 de l'article
décrit sa pondération, et nous ne pouvons pas vérifier qu'AQR l'a gardée.

**Nous ne reproduisons ni la table VI ni le modèle à trois facteurs.** Les 48 actifs de test exigent
les portefeuilles par tiers de chaque marché, qu'AQR ne publie pas. Report assumé, et non oubli.

**Nous corrigeons pour les tests multiples**, ce que l'article ne fait pas, et nous comptons 207
essais dans le ratio de Sharpe dégonflé.

**Le biais de survie de la jambe A est déclaré et non mesuré.** AQR ne publie pas sa règle d'entrée et
de sortie d'univers, et son onglet de sources nomme des bases commerciales sans décrire le traitement
des radiations. Statut : **non trouvé**.

## Les résultats

### La corrélation négative se réplique dans dix marchés sur onze

Source : `results/tables/replication_table1.csv` et `results/tables/replication_checks.csv`. Échantillon
`IS`, brut de frais, janvier 1972 à juillet 2011, univers des facteurs publiés par AQR.

| Marché | N | Corrélation | Publiée | Écart en sigmas | Sharpe valeur | Publié | Sharpe momentum | Publié | Sharpe mélange | Publié |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Toutes classes d'actifs | 475 | **-0,586** | -0,60 | 0,48 | 0,500 | 0,72 | 0,632 | 0,74 | 1,245 | 1,59 |
| Actions, agrégat | 474 | -0,598 | -0,60 | 0,05 | 0,471 | 0,51 | 0,590 | 0,59 | 1,181 | 1,28 |
| Hors actions, agrégat | 475 | -0,538 | -0,49 | -1,37 | 0,318 | 0,55 | 0,433 | 0,62 | 0,781 | 1,14 |
| Actions américaines | 474 | -0,623 | -0,65 | 1,01 | 0,268 | 0,26 | 0,462 | 0,45 | 0,844 | 0,86 |
| Actions britanniques | 361 | -0,639 | -0,62 | -0,59 | 0,339 | 0,38 | 0,558 | 0,48 | 1,062 | 1,07 |
| Actions européennes | 361 | -0,510 | -0,55 | 1,08 | 0,468 | 0,54 | 0,554 | 0,75 | 1,017 | 1,20 |
| Actions japonaises | 361 | -0,637 | -0,64 | 0,08 | 0,712 | 0,77 | 0,109 | 0,13 | 0,883 | 0,88 |
| Indices actions par pays | 413 | -0,389 | -0,37 | -0,45 | 0,507 | 0,60 | 0,580 | 0,63 | 0,978 | 1,00 |
| Devises | 391 | -0,434 | -0,43 | -0,09 | 0,411 | 0,44 | 0,330 | 0,32 | 0,690 | 0,69 |
| Obligations d'État | 343 | **-0,224** | -0,35 | **2,65** | 0,160 | 0,07 | 0,138 | 0,17 | 0,240 | 0,20 |
| Matières premières | 475 | -0,471 | -0,46 | -0,32 | 0,259 | 0,31 | 0,520 | 0,51 | 0,750 | 0,77 |

**Comment lire ce tableau, en trois constats.** Un, dix corrélations sur onze tombent à moins de deux
erreurs types d'échantillonnage de la valeur publiée, et sept à moins d'une. La règle de tolérance est
écrite dans `config.yaml` sous `correlation_tolerance_sigmas`, avant la mesure. Deux, les obligations
d'État échouent à 2,65 erreurs types, et c'est le seul contrôle en échec. L'article prévient lui-même
que la valeur obligataire change de signe selon sa définition, son panneau C donnant +0,22 pour la
mesure par l'écart de terme. Trois, les huit ratios de Sharpe de mélange des marchés
individuels se retrouvent à 0,036 près en moyenne. Les trois agrégats, eux, manquent de 0,099, 0,345
et 0,359.

### Le déséquilibre du panneau explique la moitié de l'écart sur les agrégats

Source : `results/tables/balanced_panel.csv`. Échantillon `IS`, brut de frais, fenêtre de l'article.

| Agrégat | Panneau | N | Début | Corrélation | Sharpe valeur | Sharpe momentum | Sharpe mélange | Publié |
|---|---|---:|---|---:|---:|---:|---:|---:|
| Toutes classes d'actifs | déséquilibré | 475 | 1972-01 | -0,586 | 0,500 | 0,632 | 1,245 | 1,59 |
| Toutes classes d'actifs | équilibré | 343 | 1983-01 | -0,639 | 0,642 | 0,636 | **1,466** | 1,59 |
| Actions, agrégat | déséquilibré | 474 | 1972-02 | -0,598 | 0,471 | 0,590 | 1,181 | 1,28 |
| Actions, agrégat | équilibré | 343 | 1983-01 | -0,665 | 0,504 | 0,490 | 1,201 | 1,28 |
| Hors actions, agrégat | déséquilibré | 475 | 1972-01 | -0,538 | 0,318 | 0,433 | 0,781 | 1,14 |
| Hors actions, agrégat | équilibré | 343 | 1983-01 | -0,463 | 0,488 | 0,625 | **1,077** | 1,14 |

**Comment lire ce tableau, en trois constats.** Un, restreindre l'agrégat mondial aux 343 mois où les
huit classes existent porte son ratio de Sharpe de 1,245 à 1,466, soit 64 % du chemin vers le 1,59
publié. Deux, l'agrégat hors actions gagne davantage encore, de 0,781 à 1,077 contre 1,14
publié, parce que ses trois classes les plus tardives commencent en 1977, 1979 et 1983. Trois,
l'agrégat d'actions ne gagne presque rien, de 1,181 à 1,201, ce qui est cohérent puisque ses quatre
marchés sont disponibles bien plus tôt.

**Ce que cela n'explique pas.** Le reste de l'écart, 0,124 sur l'agrégat mondial, n'est pas attribué.
Le classeur d'AQR déclare que ses sources et sa méthode peuvent différer de l'article, et nous n'avons
pas les entrées qui permettraient de trancher. Statut : **non trouvé**.

### Les trois grandeurs du facteur combiné mondial

Source : `results/tables/paper_combination.csv`. Échantillon `IS`, brut de frais, 475 mois de janvier
1972 à juillet 2011.

| Grandeur | Publiée | Mesurée | Écart relatif |
|---|---:|---:|---:|
| Rendement moyen annualisé du mélange, % | 6,8 | 5,58 | 0,180 |
| Écart type annualisé du mélange, % | 4,3 | 4,48 | 0,042 |
| Statistique t du mélange | 9,83 | 8,37 | 0,148 |

**Comment lire ce tableau, en trois constats.** Un, l'écart type se retrouve à 4 % près, ce qui
confirme que nous tenons bien le même objet. Deux, le rendement moyen manque de 18 %, et c'est lui qui
porte l'écart de ratio de Sharpe. Trois, la statistique t reste à 8,37, donc la conclusion de l'article
sur la significativité du mélange ne dépend pas de cet écart.

### Le tableau principal, quinze paires, échantillon complet

Source : `results/tables/pairs_full_sample.csv`. Échantillon `VALIDATION`, brut de frais, chaque paire
sur sa propre couverture, univers des facteurs publiés pour la jambe A et univers CRSP pour la jambe B.

| Jambe | Paire | N | Corrélation | Sharpe valeur | Sharpe momentum | Sharpe mélange | Gain sur la meilleure jambe | Multiplicateur |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| A | Toutes classes d'actifs | 654 | **-0,577** | 0,412 | 0,593 | **1,096** | **0,503** | 1,538 |
| A | Actions, agrégat | 653 | -0,590 | 0,333 | 0,571 | 0,996 | 0,425 | 1,563 |
| A | Hors actions, agrégat | 637 | -0,538 | 0,293 | 0,358 | 0,677 | 0,319 | 1,471 |
| A | Actions américaines | 653 | -0,610 | 0,154 | 0,459 | 0,701 | 0,241 | 1,601 |
| A | Actions britanniques | 540 | -0,605 | 0,210 | 0,555 | 0,874 | 0,319 | 1,590 |
| A | Actions européennes | 540 | -0,517 | 0,260 | 0,562 | 0,853 | 0,291 | 1,439 |
| A | Actions japonaises | 540 | -0,621 | 0,562 | 0,110 | 0,728 | 0,166 | 1,625 |
| A | Indices actions par pays | 575 | -0,414 | 0,310 | 0,465 | 0,722 | 0,257 | 1,306 |
| A | Devises | 553 | -0,437 | 0,319 | 0,221 | 0,503 | 0,184 | 1,332 |
| A | Obligations d'État | 505 | -0,248 | 0,106 | 0,128 | 0,189 | 0,061 | 1,153 |
| A | Matières premières | 637 | -0,504 | 0,316 | 0,376 | 0,694 | 0,318 | 1,420 |
| B | HML contre momentum de Carhart | 1 194 | -0,408 | 0,346 | 0,464 | 0,743 | 0,279 | 1,300 |
| B | Rang sur quintiles, taille neutralisée | 1 194 | -0,361 | 0,398 | 0,495 | 0,783 | 0,287 | 1,251 |
| B | Haut moins bas sur quintiles | 1 194 | -0,353 | 0,403 | 0,518 | 0,805 | 0,286 | 1,244 |
| B | HML contre déciles 12-2 | 1 194 | -0,398 | 0,346 | 0,417 | 0,680 | 0,263 | 1,288 |

**Comment lire ce tableau, en trois constats.** Un, les quinze corrélations sont négatives et les
quinze mélanges battent leur meilleure jambe, sans exception. C'est ce double fait qui alimente le
critère de signe économique du verdict. Deux, le cas japonais est celui que l'article met en avant :
le momentum n'y rend que 0,110, et pourtant lui donner la moitié du portefeuille porte le ratio de
Sharpe de 0,562 à 0,728. Trois, la jambe B, sur 1 194 mois, porte des corrélations de -0,353 à -0,408. Elles
sont nettement moins négatives que celles des quatre marchés d'actions de la jambe A, qui vont de
-0,517 à -0,621, et son multiplicateur va de 1,244 à 1,300 contre 1,538 sur la paire de référence.

### La formule prédit la mesure à la précision machine

Source : `results/tables/formula_check.csv`. C'est le contrôle central de l'étude. Échantillon
`VALIDATION`, brut de frais.

| Paire | Corrélation | Mélange à risque égal, mesuré | Mélange à risque égal, formule | Si les jambes étaient indépendantes | Apporté par la corrélation | Sharpe par unité de corrélation |
|---|---:|---:|---:|---:|---:|---:|
| Toutes classes d'actifs | -0,577 | 1,0933 | 1,0933 | 0,7108 | **0,383** | **-1,293** |
| Actions, agrégat | -0,590 | 0,9993 | 0,9993 | 0,6396 | 0,360 | -1,220 |
| Hors actions, agrégat | -0,538 | 0,6770 | 0,6770 | 0,4602 | 0,217 | -0,732 |
| Actions américaines | -0,610 | 0,6950 | 0,6950 | 0,4341 | 0,261 | -0,891 |
| Actions britanniques | -0,605 | 0,8605 | 0,8605 | 0,5411 | 0,319 | -1,088 |
| Actions européennes | -0,517 | 0,8363 | 0,8363 | 0,5812 | 0,255 | -0,866 |
| Actions japonaises | -0,621 | 0,7718 | 0,7718 | 0,4751 | 0,297 | -1,018 |
| Indices actions par pays | -0,414 | 0,7158 | 0,7158 | 0,5481 | 0,168 | -0,610 |
| Devises | -0,437 | 0,5086 | 0,5086 | 0,3818 | 0,127 | -0,451 |
| Obligations d'État | -0,248 | 0,1905 | 0,1905 | 0,1652 | 0,025 | -0,127 |
| Matières premières | -0,504 | 0,6948 | 0,6948 | 0,4892 | 0,206 | -0,701 |
| HML contre momentum de Carhart | -0,408 | 0,7442 | 0,7442 | 0,5724 | 0,172 | -0,629 |
| Rang sur quintiles | -0,361 | 0,7901 | 0,7901 | 0,6315 | 0,159 | -0,618 |
| Haut moins bas sur quintiles | -0,353 | 0,8100 | 0,8100 | 0,6514 | 0,159 | -0,626 |
| HML contre déciles 12-2 | -0,398 | 0,6949 | 0,6949 | 0,5394 | 0,156 | -0,577 |

**Comment lire ce tableau, en trois constats.** Un, l'écart maximal entre la mesure et la formule vaut
**5,6e-16** sur les quinze paires, donc l'identité tient à la précision machine. Ce n'est pas un
résultat empirique, c'est une vérification que les deux objets sont bien le même. Deux, la colonne
« apporté par la corrélation » se lit directement : sur la paire de référence, 0,383 des 1,093 de
ratio de Sharpe viennent de la seule corrélation négative, soit 35 %. Trois, la sensibilité varie d'un
facteur dix entre les obligations d'État, à -0,127, et la paire de référence, à -1,293. Elle dépend en
effet à la fois de la somme des deux Sharpe et du niveau de la corrélation.

**Un exemple déroulé, à la main.** Sur la paire de référence, la valeur rend 0,412 et le momentum
0,593, donc leur somme vaut 1,005. Deux jambes indépendantes rendraient 1,005 divisé par racine de
deux, soit 0,711. À une corrélation de -0,577, le dénominateur devient racine de 2 moins 1,155, soit
racine de 0,845, donc 0,919. Le ratio de Sharpe du mélange vaut ainsi 1,005 divisé par 0,919, soit
1,093, ce que la colonne mesurée confirme.

### La corrélation de la jambe B est deux fois moins négative que celle de la jambe A

Source : `results/tables/mechanical_correlation.csv` et `results/tables/pairs_paper_window.csv`.
Échantillon `IS`, brut de frais, 474 et 475 mois de la fenêtre de l'article.

| Construction | Prix du signal de valeur | N | Corrélation | Référence publiée |
|---|---|---:|---:|---:|
| AQR, actions américaines | courant | 474 | **-0,623** | -0,53 |
| Kenneth French, HML contre momentum de Carhart | décembre de l'année précédente | 475 | **-0,168** | -0,28 |

Les quatre paires de la jambe B, sur ces mêmes 475 mois, portent des corrélations de -0,118 à -0,168 et
des multiplicateurs de 1,065 à 1,096.

| Paire de la jambe B | N | Corrélation | Sharpe valeur | Sharpe momentum | Sharpe mélange | Gain | Multiplicateur |
|---|---:|---:|---:|---:|---:|---:|---:|
| HML contre momentum de Carhart | 475 | -0,168 | 0,482 | 0,561 | 0,798 | 0,236 | 1,096 |
| Rang sur quintiles, taille neutralisée | 475 | -0,141 | 0,472 | 0,604 | 0,821 | 0,218 | 1,079 |
| Haut moins bas sur quintiles | 475 | -0,152 | 0,511 | 0,628 | 0,871 | 0,244 | 1,086 |
| HML contre déciles 12-2 | 475 | -0,118 | 0,482 | 0,487 | 0,705 | 0,219 | 1,065 |

**Comment lire ces deux tableaux, en trois constats.** Un, la corrélation passe de -0,623 à -0,168
entre les deux constructions, et le multiplicateur de diversification de 1,60 à 1,10. Le gain tient
donc en grande partie à la définition de la valeur employée. Deux, la direction est celle que
l'article annonce lui-même page 950, où retarder le prix d'un an fait passer la corrélation de -0,53 à
-0,28. Notre mesure va plus loin que la sienne, à -0,168, avec un retard de prix de six à dix-huit
mois. Trois, les quatre constructions de la jambe B se tiennent dans un intervalle de 0,050. Cela
écarte la pondération par le rang et le nombre de groupes comme explication.

**L'objection la plus forte, et pourquoi elle ne renverse pas le constat.** Trois différences
séparent les deux constructions, pas une seule : l'univers, la date du prix, et le nombre de groupes
du tri. Le troisième est écarté par les quatre variantes de la jambe B, qui donnent le même résultat
en rang comme en écart extrême. Les deux premiers ne sont pas séparés par cette étude, et le contrôle
de l'article suggère que le prix en explique environ la moitié. Le constat publié est donc une borne
et non une attribution, et c'est écrit tel quel.

### La figure de richesse cumulée

`results/figures/equity_everywhere.png`. **Mode d'emploi.** L'axe vertical est une échelle
logarithmique en dollars des États-Unis, base un dollar au 31 janvier 1972. Trois courbes, la jambe de
valeur, la jambe de momentum, et leur mélange à parts égales, toutes brutes de frais. Regarder d'abord
la régularité du mélange plutôt que son niveau final : c'est la platitude de sa pente qui porte le
résultat, et non sa hauteur.

`results/figures/sharpe_versus_correlation.png`. **Mode d'emploi.** Chaque point est une paire, les
ronds pour la jambe A et les carrés pour la jambe B. L'axe horizontal porte la corrélation mesurée,
l'axe vertical le ratio de Sharpe du mélange à risque égal. La courbe est la formule fermée évaluée
aux ratios de Sharpe médians des jambes. Un point au-dessus de la courbe a des jambes meilleures que
la médiane, un point en dessous des jambes plus faibles ; l'écart vertical ne se lit donc pas comme
une erreur.

`results/figures/correlation_heatmap.png`. **Mode d'emploi.** Quatre séries, la valeur et le momentum
des actions puis des autres classes, et leurs six corrélations croisées. La figure s'arrête en
janvier 2025, l'agrégat hors actions y finissant, et son titre porte cette borne. Regarder d'abord les deux
cases valeur contre momentum à l'intérieur d'un même groupe, puis les deux cases croisées entre
groupes, qui mesurent ce que la diversification géographique ajoute à la diversification par signal.

## La robustesse

### Le poids de la moitié est optimal ou presque dans les onze paires

Source : `results/tables/weight_optimum.csv` et `results/tables/weight_sweep.csv`. Onze paires par
onze poids, 121 cellules, échantillon `VALIDATION`, brut de frais.

| Paire | Meilleur poids de valeur | Sharpe au meilleur poids | Sharpe à la moitié | Coût de tenir la moitié | Pire poids intérieur | Sharpe au pire poids |
|---|---:|---:|---:|---:|---:|---:|
| Toutes classes d'actifs | 0,5 | 1,096 | 1,096 | 0,000 | 0,9 | 0,512 |
| Actions, agrégat | 0,5 | 0,996 | 0,996 | 0,000 | 0,9 | 0,420 |
| Hors actions, agrégat | 0,5 | 0,677 | 0,677 | 0,000 | 0,9 | 0,353 |
| Actions américaines | 0,4 | 0,705 | 0,701 | 0,004 | 0,9 | 0,222 |
| Actions britanniques | 0,5 | 0,874 | 0,874 | 0,000 | 0,9 | 0,297 |
| Actions européennes | 0,5 | 0,853 | 0,853 | 0,000 | 0,9 | 0,357 |
| Actions japonaises | 0,6 | 0,811 | 0,728 | **0,083** | 0,1 | 0,174 |
| Indices actions par pays | 0,5 | 0,722 | 0,722 | 0,000 | 0,9 | 0,387 |
| Devises | 0,6 | 0,508 | 0,503 | 0,004 | 0,1 | 0,264 |
| Obligations d'État | 0,4 | 0,190 | 0,189 | 0,002 | 0,9 | 0,120 |
| Matières premières | 0,5 | 0,694 | 0,694 | 0,000 | 0,9 | 0,375 |

**Comment lire ce tableau, en trois constats.** Un, le poids de la moitié est exactement optimal dans
sept paires sur onze, et le plus cher des quatre écarts vaut 0,083 de ratio de Sharpe, sur les actions
japonaises. Deux, le pire poids intérieur reste au-dessus de la plus faible des deux jambes dans les onze
paires, sans exception. Un poids mal choisi entre 0,1 et 0,9 vaut donc toujours mieux que de tenir
seule la jambe la moins bonne, mais il peut faire pire que de tenir seule la meilleure. Trois, le poids optimal ne s'éloigne jamais de la moitié de plus d'un dixième, donc le
résultat ne demande aucune optimisation.

`results/figures/weight_heatmap.png`. **Mode d'emploi.** Une ligne par paire, une colonne par poids de
la jambe de valeur, une couleur par ratio de Sharpe. Chercher une plage claire large plutôt qu'une
case isolée : le résultat vaut par la largeur du plateau au centre, pas par la valeur d'une cellule.

### La corrélation est négative dans toutes les fenêtres glissantes

Source : `results/tables/rolling_correlation.csv`. Paire de référence, échantillon `VALIDATION`.

| Fenêtre | Nombre de fenêtres | Minimum | Médiane | Maximum | Part négative | Date du maximum |
|---|---:|---:|---:|---:|---:|---|
| 36 mois | 619 | -0,943 | -0,590 | **-0,099** | 1,000 | 1991-01-31 |
| 60 mois | 595 | -0,906 | -0,620 | -0,276 | 1,000 | 1985-12-31 |
| 120 mois | 535 | -0,844 | -0,643 | -0,350 | 1,000 | 1990-09-30 |

**Comment lire ce tableau, en trois constats.** Un, la corrélation n'est jamais positive, dans aucune
des 1 749 fenêtres des trois longueurs. C'est le contrôle le plus fort de la stabilité du résultat.
Deux, la fenêtre la moins négative de toutes vaut -0,099 et se termine en janvier 1991, donc même le
pire épisode laisse une corrélation négative. Trois, la médiane se resserre quand la fenêtre
s'allonge, de -0,590 à -0,643, ce qui indique que la variation à trois ans est du bruit
d'échantillonnage plus qu'un changement de régime.

`results/figures/rolling_correlation.png`. **Mode d'emploi.** Trois courbes, une par longueur de
fenêtre, et une ligne horizontale à zéro. Regarder d'abord si une courbe touche la ligne, puis
l'amplitude de la courbe à 36 mois par rapport à celle à 120 mois, qui mesure le bruit
d'échantillonnage.

### En période de tension, la diversification des actions faiblit

Source : `results/tables/stress_correlation.csv`. Le mois est dit tendu quand le rendement du facteur
de marché de Kenneth French tombe sous son quantile. Échantillon `VALIDATION`, brut de frais.

| Paire | Quantile | Seuil de marché | Mois tendus | Corrélation en tension | Corrélation hors tension | Écart |
|---|---:|---:|---:|---:|---:|---:|
| Toutes classes d'actifs | 0,05 | -7,37 % | 33 | **-0,785** | -0,553 | -0,232 |
| Actions, agrégat | 0,05 | -7,38 % | 33 | -0,513 | -0,611 | +0,098 |
| Actions américaines | 0,05 | -7,38 % | 33 | -0,416 | -0,639 | +0,223 |
| HML contre momentum de Carhart | 0,05 | -7,91 % | 60 | -0,162 | -0,429 | +0,267 |
| Toutes classes d'actifs | 0,10 | -4,91 % | 66 | -0,640 | -0,567 | -0,073 |
| Actions, agrégat | 0,10 | -4,92 % | 66 | -0,529 | -0,629 | +0,100 |
| Actions américaines | 0,10 | -4,92 % | 66 | -0,429 | -0,671 | +0,242 |
| HML contre momentum de Carhart | 0,10 | -5,31 % | 120 | -0,169 | -0,452 | +0,284 |
| Toutes classes d'actifs | 0,20 | -2,57 % | 131 | -0,467 | -0,627 | +0,160 |
| Actions, agrégat | 0,20 | -2,58 % | 131 | -0,560 | -0,617 | +0,057 |
| Actions américaines | 0,20 | -2,58 % | 131 | -0,484 | -0,670 | +0,185 |
| HML contre momentum de Carhart | 0,20 | -2,70 % | 239 | -0,206 | -0,462 | +0,256 |

**Comment lire ce tableau, en trois constats.** Un, sur les actions américaines la corrélation remonte
de -0,671 à -0,429 dans le décile des pires mois de marché, donc la diversification faiblit
précisément quand elle sert. Le même mouvement se voit sur la jambe B, de -0,452 à -0,169. Deux, la
paire toutes classes d'actifs fait l'inverse aux deux seuils les plus serrés, sa corrélation passant
de -0,553 à -0,785 dans les 33 pires mois. La diversification entre classes d'actifs tient donc là où
celle des seules actions cède. Trois, le signe de l'écart s'inverse pour cette paire au quantile de
0,20, ce qui signale que le résultat dépend du seuil et qu'aucune des trois lignes ne se lit seule.

### Le rééquilibrage, la fenêtre du poids et le délai d'exécution ne décident de rien

Trois sources, `results/tables/rebalance.csv`, `results/tables/risk_parity_window.csv` et
`results/tables/execution_lag.csv`. Paire de référence, net de dix points de base pour la première.

| Pas de rééquilibrage | Rotation annuelle | Sharpe brut | Sharpe net | Poids maximal | Poids minimal |
|---|---:|---:|---:|---:|---:|
| 1 mois | 0,176 | 1,096 | 1,092 | 0,500 | 0,500 |
| 3 mois | 0,265 | 1,107 | 1,100 | 0,586 | 0,399 |
| 6 mois | 0,277 | 1,108 | 1,101 | 0,670 | 0,378 |
| 12 mois | 0,268 | 1,082 | 1,076 | 0,703 | 0,345 |

| Fenêtre du poids à risque égal | N | Début | Poids médian | Sharpe en temps réel | Sharpe à parts égales |
|---|---:|---|---:|---:|---:|
| 36 mois | 618 | 1975-01 | 0,492 | 1,181 | 1,188 |
| 60 mois | 594 | 1977-01 | 0,493 | 1,253 | 1,254 |
| 120 mois | 534 | 1982-01 | 0,498 | 1,166 | 1,171 |
| 240 mois | 414 | 1992-01 | 0,502 | 1,018 | 1,023 |

| Délai d'exécution | N | Sharpe | Poids médian |
|---|---:|---:|---:|
| 1 mois, cas de référence | 594 | 1,253 | 0,4932 |
| 2 mois | 593 | 1,246 | 0,4932 |
| 3 mois | 592 | 1,238 | 0,4932 |

**Comment lire ces trois tableaux, en trois constats.** Un, rééquilibrer tous les six mois plutôt que
tous les mois change le ratio de Sharpe net de 0,009, et le pas de douze mois est le seul qui coûte
quelque chose, 0,016. Le poids dérive alors jusqu'à 0,703, ce qui suffit à entamer la diversification.
Deux, le poids à risque égal estimé sur le seul passé ne bat JAMAIS le poids fixe de la moitié, quelle
que soit la fenêtre, et l'écart va de 0,001 à 0,006 en sa défaveur. Estimer coûte donc un peu et ne
rapporte rien, ce qui est le meilleur argument pour le poids fixe de l'article. Trois, retarder
l'exécution de deux mois de plus retire 0,015 de ratio de Sharpe, parce que le poids ne bouge presque
pas d'un mois à l'autre.

### Les trois sous-périodes sont positives, la dernière deux fois moins

Source : `results/tables/subperiods.csv`. Mélange de référence, net de dix points de base, échantillon
`VALIDATION` pour les deux premières et `OOS` pour la troisième.

| Sous-période | N | Rendement composé annuel | Volatilité | Sharpe | t | Pire repli | Part de mois positifs |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1972-01 à 1991-11 | 239 | 7,20 % | 5,54 % | **1,285** | 6,44 | -6,49 % | 0,695 |
| 1991-12 à 2011-06 | 235 | 4,05 % | 2,99 % | **1,343** | 5,59 | -6,76 % | 0,694 |
| 2011-07 à 2026-06 | 180 | 1,72 % | 2,96 % | **0,590** | 2,00 | -11,56 % | 0,550 |

**Comment lire ce tableau, en trois constats.** Un, les trois sous-périodes sont positives, ce qui
donne la part de 1,000 comparée au seuil de 0,60 dans le verdict. Deux, le ratio de Sharpe est stable
sur les quarante premières années, 1,285 puis 1,343, et il tombe de moitié sur la période qui suit la
publication. Trois, la troisième sous-période est aussi la seule dont le pire repli dépasse dix points
de pourcentage, et sa part de mois positifs tombe de 0,69 à 0,55.

Le découpage vient de `subperiod_breakpoints` dans `config.yaml`, et il reprend les deux périodes de
la table VII de l'article, 1972-1991 et 1992-2011, plus ce qui suit sa publication. La borne du 31
juillet 2011 appartient à la troisième sous-période, qui compte donc 180 mois là où le hors
échantillon de la section suivante en compte 179.

`results/figures/subperiod_bars.png`. **Mode d'emploi.** Une barre par sous-période, la moustache
étant l'intervalle à 95 % construit sur l'erreur type de Lo. Vérifier qu'une moustache ne traverse pas
zéro avant de commenter la hauteur d'une barre.

### Le risque de queue du mélange

Source : `results/tables/tail_risk.csv`. Échantillon `VALIDATION`, 654 mois, brut de frais sauf la
dernière ligne.

| Série | Rendement annuel | Volatilité annuelle | Asymétrie | Kurtosis en excès | Pire repli | Sharpe |
|---|---:|---:|---:|---:|---:|---:|
| Valeur, toutes classes d'actifs | 3,66 % | 8,88 % | -0,227 | 11,79 | -31,96 % | 0,412 |
| Momentum, toutes classes d'actifs | 5,43 % | 9,16 % | +0,477 | 7,15 | -31,35 % | 0,593 |
| Mélange à parts égales, brut | 4,55 % | **4,15 %** | **+1,225** | 8,76 | **-11,51 %** | 1,096 |
| Mélange à parts égales, net à dix points de base | 4,53 % | 4,15 % | +1,221 | 8,74 | -11,56 % | 1,092 |

**Comment lire ce tableau, en trois constats.** Un, le mélange divise la volatilité par plus de deux,
de 8,88 % et 9,16 % à 4,15 %, alors que son rendement est la moyenne des deux. C'est la traduction en
dollars du multiplicateur de 1,538. Deux, le pire repli passe de 32 % à 11,5 %, soit un tiers, ce qui
est un gain plus grand encore que celui de la volatilité. Trois, l'asymétrie du mélange est positive,
+1,225, alors que sa jambe de valeur est négative. Le mélange n'achète donc pas son ratio de Sharpe en
vendant des queues, ce qu'une lecture soupçonneuse d'un Sharpe élevé suggérerait.

`results/figures/underwater_blend.png` et `results/figures/return_histogram.png`. **Mode d'emploi.**
La première montre la distance au sommet précédent, en points de pourcentage, et sert à juger la durée
d'un repli autant que sa profondeur. La seconde superpose la loi normale de même moyenne et de même
écart type, et l'écart à droite est ce que l'asymétrie de +1,225 chiffre.

## Les coûts

La rotation du mélange est petite, et le coût qui l'annulerait est donc énorme. Source :
`results/tables/costs.csv`. Rotation mesurée en convention de somme entière sur les deux jambes,
poids dérivés par la valeur liquidative.

| Taux | Brut par an | Net par an | Rotation annuelle | Sharpe net | Coût qui annule | Rotation qui annule |
|---|---:|---:|---:|---:|---:|---:|
| 0 point de base | 4,545 % | 4,545 % | 0,176 | 1,096 | 2 581 pb | sans objet |
| 1 point de base | 4,545 % | 4,544 % | 0,176 | 1,095 | 2 581 pb | 454,5 par an |
| 10 points de base | 4,545 % | 4,528 % | 0,176 | 1,092 | 2 581 pb | 45,5 par an |
| 20 points de base | 4,545 % | 4,510 % | 0,176 | 1,087 | 2 581 pb | 22,7 par an |

**Comment lire ce tableau, en trois constats.** Un, le coût de dix points de base retire 0,004 de
ratio de Sharpe, parce que le rééquilibrage mensuel ne fait tourner que 17,6 % du portefeuille par an.
Deux, le coût qui annulerait le rendement brut vaut 2 581 points de base par unité de rotation, soit
258 fois le coût de référence de dix points de base déclaré dans `config.yaml`. Trois, la
dernière colonne dit ce qui compte vraiment. À dix points de base, il faudrait 45,5 unités de rotation
par an pour effacer les 4,545 %. C'est le seuil que la rotation INTERNE des deux jambes devrait
franchir.

**Ce que ce tableau ne mesure pas, et c'est l'objection la plus forte.** La rotation de 0,176 est
celle du seul rééquilibrage entre les deux jambes. Elle ne contient pas la rotation interne de chaque
jambe, celle de la reconstruction mensuelle des positions de valeur et de momentum, qui est la
rotation coûteuse. AQR publie des rendements et non des positions, donc cette rotation n'est pas
calculable ici. Statut : **non trouvé**. La colonne « rotation qui annule » est la façon honnête de
publier la contrainte. Le résultat tient tant que les deux jambes ne dépassent pas ensemble 45,5
unités de rotation annuelle à dix points de base.

Le multiple de coût survécu vaut **10**, le plus grand de la grille
(`results/tables/cost_multiples.csv`). Le ratio de Sharpe hors échantillon passe de 0,607 à 0,561
entre le demi et le décuple du coût de référence. Cette conclusion est entièrement conditionnée à la
limite ci-dessus.

`results/figures/cost_sensitivity.png`. **Mode d'emploi.** L'axe horizontal porte le multiple appliqué
aux dix points de base, l'axe vertical le ratio de Sharpe net hors échantillon, et la ligne
horizontale marque zéro. La courbe ne croise pas zéro, et sa PENTE est ce qu'il faut lire : elle
mesure le coût du seul rééquilibrage, non celui des jambes.

## Le hors échantillon

### Le mélange rend 0,604 après la publication, et dix-sept mois portent l'essentiel

Source : `results/tables/holdout_composition.csv`. Mélange de référence, net de dix points de base,
échantillon `OOS`.

| Fenêtre | Début | Fin | N | Classes d'actifs présentes | Sharpe net |
|---|---|---|---:|---|---:|
| Hors échantillon complet | 2011-08-31 | 2026-06-30 | 179 | huit puis quatre | **0,604** |
| Hors échantillon, huit classes présentes | 2011-08-31 | 2025-01-31 | 162 | huit | **0,246** |
| Hors échantillon, actions seules | 2025-02-28 | 2026-06-30 | 17 | quatre | **2,471** |

**Comment lire ce tableau, en trois constats.** Un, le ratio de Sharpe hors échantillon de 0,604, celui
qui porte le verdict, tombe à 0,246 dès qu'on retire les dix-sept derniers mois. Deux, ces dix-sept
mois rendent un ratio de Sharpe de 2,471, mais ils ne décrivent pas le même portefeuille. Les colonnes
hors actions du classeur d'AQR s'y arrêtent, donc la série n'y porte plus que les quatre marchés
d'actions. Trois, le critère de ratio de Sharpe hors échantillon du verdict, fixé à 0,50, est
donc franchi grâce à une fenêtre dont la composition change sans que la source le signale.

**Pourquoi le chiffre de référence reste 0,604.** La définition du hors échantillon est écrite dans
`config.yaml` sous `paper_end`, avant que les résultats existent, et elle dit « tout ce qui suit
juillet 2011 ». La changer après avoir vu les deux nombres serait déplacer la cible. Le tableau
ci-dessus est publié pour que le lecteur fasse lui-même la lecture prudente, et la section du verdict
la reprend.

### Le rééchantillonnage par blocs

Source : `results/tables/bootstrap.csv`. Blocs circulaires de douze mois, 2 000 tirages, graine 20260902
propagée par `child_generators`, échantillon `OOS`, net de dix points de base.

| Grandeur | Observée | Erreur type | Centile 5 | Centile 95 | Part de tirages positifs |
|---|---:|---:|---:|---:|---:|
| Rendement annualisé du mélange | 1,79 % | 1,16 % | -0,04 % | 3,75 % | 0,947 |

**Comment lire ce tableau, en trois constats.** Un, le rendement hors échantillon vaut 1,79 % par an,
soit moins de la moitié des 4,55 % de l'échantillon complet. Deux, l'intervalle à 90 % touche zéro par
le bas, à -0,04 %, donc le résultat hors échantillon n'est pas distinguable de zéro à ce seuil. Trois,
94,7 % des tirages restent positifs, ce qui est le même message dit dans l'autre sens.

### Les contrôles de surapprentissage

| Contrôle | Valeur mesurée | Fichier |
|---|---:|---|
| Nombre d'essais comptés | **207** | `trials.csv` |
| Ratio de Sharpe hors échantillon, net | 0,604 | `deflated_sharpe.csv` |
| Statistique t hors échantillon | 2,059 | `deflated_sharpe.csv` |
| Maximum attendu sous l'hypothèse nulle | **0,884** | `deflated_sharpe.csv` |
| Ratio de Sharpe dégonflé | **0,000012** | `deflated_sharpe.csv` |
| t exigé par Bonferroni sur 207 essais | 3,671 | `deflated_sharpe.csv` |
| t après rabais de Holm | **0,000** | `deflated_sharpe.csv` |
| Probabilité de surapprentissage | 0,000 | `metrics.json` |
| Sharpe moyen des 7 chemins de validation croisée | 1,092 | `cpcv_distribution.csv` |

**Comment lire ce tableau, en trois constats.** Un, le maximum attendu sous l'hypothèse nulle vaut
0,884 avec 207 essais, donc il dépasse le 0,604 observé et le ratio dégonflé tombe à 0,000012. Deux,
le rabais de Holm sur 207 tests porte la valeur p à un et la statistique t ajustée à zéro, ce qui fait
échouer le critère de 3,00. Trois, ces deux échecs viennent du COMPTE d'essais autant que du résultat,
et le tableau suivant le chiffre plutôt que de l'affirmer.

**La sensibilité au compte d'essais, publiée plutôt qu'écartée.** Source :
`results/tables/deflation_sensitivity.csv`.

| Convention de comptage | Essais | Variance des Sharpe | Maximum attendu sous l'hypothèse nulle | Sharpe dégonflé | t exigé par Bonferroni |
|---|---:|---:|---:|---:|---:|
| Les 15 mélanges à parts égales, un par paire | 15 | 0,0429 | 0,367 | **0,9998** | 2,935 |
| Les 121 cellules du balayage des poids | 121 | 0,0530 | 0,598 | 0,537 | 3,531 |
| Tous les essais comptés, référence | 207 | 0,1013 | 0,884 | **0,000012** | 3,671 |

**Comment lire ce tableau, en trois constats.** Un, le ratio de Sharpe dégonflé passe de 0,9998 à 0,000012
selon la convention de comptage, donc ce critère est entièrement déterminé par le nombre d'essais
déclaré et non par la performance. Deux, la convention de référence est la plus sévère, et c'est celle
que la règle 8 du laboratoire impose : toutes les cellules de toutes les grilles comptent. Trois, les
207 essais ne sont pas indépendants, 121 d'entre eux étant onze poids voisins sur les mêmes onze
paires, si bien que le maximum attendu de 0,884 est un majorant. Le critère est donc conservateur, et
le dire ne le relâche pas.

**La validation croisée combinatoire ne dit rien ici, et c'est mesuré.** Les sept chemins rendent tous
exactement 1,0916, à écart type nul. La raison est dans le fichier : sur les 56 sélections effectuées,
**un seul poids distinct** a jamais été retenu, la moitié (`cpcv_distribution.csv`). Le processus de
sélection ne varie donc pas, ce qui explique aussi une probabilité de surapprentissage de zéro. Ces
deux contrôles constatent la stabilité du choix, ils ne valident pas la stratégie.

### Les quinze paires après correction pour tests multiples

Source : `results/tables/multiple_testing.csv`, correction de Holm sur les quinze statistiques t des
mélanges à parts égales, échantillon `VALIDATION`, brut de frais.

| Paire | N | Sharpe du mélange | t | Valeur p ajustée | Rejetée à 5 % |
|---|---:|---:|---:|---:|---|
| Toutes classes d'actifs | 654 | 1,096 | 8,38 | <1e-5 | oui |
| Actions, agrégat | 653 | 0,996 | 6,79 | <1e-5 | oui |
| Haut moins bas sur quintiles | 1 194 | 0,805 | 6,30 | <1e-5 | oui |
| Rang sur quintiles | 1 194 | 0,783 | 6,15 | <1e-5 | oui |
| HML contre momentum de Carhart | 1 194 | 0,743 | 6,01 | <1e-5 | oui |
| HML contre déciles 12-2 | 1 194 | 0,680 | 5,73 | <1e-5 | oui |
| Actions britanniques | 540 | 0,874 | 5,42 | <1e-5 | oui |
| Actions américaines | 653 | 0,701 | 5,40 | <1e-5 | oui |
| Hors actions, agrégat | 637 | 0,677 | 5,36 | <1e-5 | oui |
| Indices actions par pays | 575 | 0,722 | 5,34 | <1e-5 | oui |
| Actions européennes | 540 | 0,853 | 5,17 | <1e-5 | oui |
| Matières premières | 637 | 0,694 | 4,90 | <1e-5 | oui |
| Actions japonaises | 540 | 0,728 | 4,55 | 0,00002 | oui |
| Devises | 553 | 0,503 | 3,66 | 0,00050 | oui |
| Obligations d'État | 505 | 0,189 | 1,49 | **0,137** | non |

**Comment lire ce tableau, en trois constats.** Un, quatorze paires sur quinze survivent à la
correction de Holm, ce qui est un résultat inhabituellement fort pour ce laboratoire. Deux, la seule
paire qui ne survit pas est celle des obligations d'État, qui est aussi la seule dont le contrôle de
réplication échoue. Deux diagnostics indépendants désignent le même objet. Trois, cette correction
porte sur l'échantillon complet et non sur le hors échantillon, où le mélange de référence rend un t
de 2,06 contre 3,67 exigé par Bonferroni sur 207 essais.

## Les limites

**Un contrôle de réplication sur onze échoue.** La corrélation des obligations d'État vaut -0,224
contre -0,350 publié, soit 2,65 erreurs types d'échantillonnage. La cause n'est pas isolée. L'article publie trois mesures de valeur
obligataire dont la corrélation en écart haut moins bas va de -0,17 à +0,22, et AQR ne dit pas
laquelle il emploie aujourd'hui. Statut : **non trouvé**.

**Le ratio de Sharpe hors échantillon repose sur une série dont la composition change.** Les dix-sept
derniers mois ne portent que les actions, et sans eux le chiffre tombe de 0,604 à 0,246. Le tableau de
composition est publié, et la section du verdict le reprend explicitement.

**La rotation interne des deux jambes n'est pas mesurable.** AQR publie des rendements et non des
positions. Le seuil de 45,5 unités de rotation annuelle est la borne publiée, et le résultat de coût
tient uniquement sous cette borne.

**La jambe B ne sépare pas trois différences.** L'univers, la date du prix et le nombre de groupes du
tri changent tous les trois entre les deux jambes. Le troisième est écarté par les quatre variantes,
les deux premiers ne le sont pas. Le constat sur la corrélation mécanique est une borne, pas une
attribution.

**Le panneau est déséquilibré avant janvier 1983.** L'agrégat mondial des dix premières années ne
porte pas les huit classes, et l'article n'en dit rien. Le tableau du panneau équilibré chiffre ce que
cela vaut, et il ne referme pas tout l'écart.

**Aucun coût de financement ni aucune contrainte de vente à découvert n'est appliqué.** Les deux
jambes sont des portefeuilles longs et courts, et un investisseur réel paierait pour emprunter les
titres vendus. L'omission joue en faveur de la stratégie.

**La validation croisée combinatoire et la probabilité de surapprentissage ne disent rien ici.** Le
processus de sélection ne retient jamais qu'un seul poids, et les deux contrôles le constatent au lieu
de le tester. Le compte de sélections distinctes est publié pour que cela se voie.

**Le compte de 207 essais couvre toutes les évaluations de performance publiées.** Il a été porté de
183 à 207 après recomptage, quatre familles ayant d'abord été omises. Deux portent sur la fenêtre de
l'article : les quatre mélanges de la jambe B, puis les quinze mélanges à risque égal de cette même
fenêtre. Les deux autres sont les trois agrégats du panneau équilibré et les deux sous-fenêtres du
hors échantillon. Le tableau `trials.csv` les porte désormais, famille par famille.

**Trois familles de diagnostics restent hors du compte, et elles sont nommées.** Ce sont les trois
longueurs de corrélation glissante, les douze cellules de corrélation en période de tension, et les
onze contrôles de réplication de la table I. Les derniers comparent à un chiffre publié plutôt que de
sélectionner une stratégie. Aucune ne rend un rendement détenable. Restent aussi dehors les
décompositions d'une série déjà comptée, les trois sous-périodes et les quatre lignes du risque de
queue, qui découpent le mélange de référence sans proposer d'autre stratégie.

**Aucun résultat ne porte sur l'avenir.** Tous les chiffres sont mesurés sur des périodes nommées.

## Le verdict

**`EXPERIMENTAL`**, déduit par `quantlab.reporting.study.decide_verdict` depuis les seuils écrits dans
`config.yaml` avant que les résultats existent. Voici les critères, avec la valeur mesurée en face du
seuil.

| Critère | Mesuré | Seuil | Résultat |
|---|---:|---:|---|
| Signe économique attendu | 15 corrélations négatives et 15 mélanges gagnants | les deux exigés | RÉUSSI |
| Signe du Sharpe hors échantillon | 0,604 | rejet à 0 ou moins | RÉUSSI |
| Réplication, 11 contrôles de corrélation | **10 sur 11 dans la tolérance** | tous exigés | **ÉCHOUÉ** |
| Sharpe hors échantillon | 0,604 | minimum 0,50 | RÉUSSI |
| t après correction pour essais multiples | **0,000** | minimum 3,00 | **ÉCHOUÉ** |
| Ratio de Sharpe dégonflé | **0,000012** | minimum 0,95 | **ÉCHOUÉ** |
| Probabilité de surapprentissage | 0,000 | maximum 0,50 | RÉUSSI |
| Part de sous-périodes positives | 1,000 | minimum 0,60 | RÉUSSI |
| Multiple de coûts survécu | 10,000 | minimum 2,00 | RÉUSSI |
| Corrélation absolue avec le portefeuille détenu | 0,159, soit -0,159 signée | maximum 0,60 | RÉUSSI |

**Comment lire ce tableau, en trois constats.** Un, le verdict est `EXPERIMENTAL` et non `REPLICATED`
parce que l'échelle du laboratoire exige que TOUS les contrôles de réplication passent, et celui des
obligations d'État échoue. Les trois critères de robustesse qui échouent ensuite ne sont donc même pas
atteints par la progression. Deux, la corrélation avec le portefeuille détenu vaut -0,159, ce qui est
la propriété la plus attirante du mélange pour un gérant d'actions. Trois, les deux critères de
significativité échouent par le compte d'essais autant que par le résultat, et la table de sensibilité
le montre chiffre en main.

**Un critère passe pour une raison qu'il faut connaître.** Le ratio de Sharpe hors échantillon de
0,604 franchit le seuil de 0,50 uniquement grâce aux dix-sept mois où la série ne porte plus que les
actions. Sur les 162 mois où les huit classes existent, il vaut 0,246 et ce critère échouerait aussi.
La règle déclarée d'avance a été respectée, et cette phrase est le prix à payer pour ne pas l'avoir
changée.

**Ce que l'étude établit, en trois phrases.** La corrélation négative entre la valeur et le momentum
se réplique dans dix marchés sur onze, et le mélange bat sa meilleure jambe dans les quinze paires
mesurées. Le gain se calcule exactement par la formule du ratio de Sharpe à deux actifs, à 5,6e-16
près, et il vaut 0,383 des 1,093 de la paire de référence, soit 35 %. Ce gain se réduit de moitié dès
que la valeur est bâtie sur un prix retardé, ce que la jambe B mesure à -0,168 contre -0,623.

**La prochaine décision.** La jambe qui reste à construire est une valeur américaine au prix courant,
sur l'univers de Kenneth French, pour isoler la date du prix des deux autres différences. Elle demande
les capitalisations mensuelles, disponibles dans le fichier `average_market_cap` des vingt-cinq
portefeuilles, et elle trancherait la borne publiée ici en attribution.

## Reproduire

```bash
export QUANTLAB_USER_AGENT="votre nom votre courriel"
uv run python studies/003_value_and_momentum/run.py
uv run pytest tests/unit/test_strategies_value_momentum.py -o addopts="" -q
```

L'exécution télécharge un classeur d'AQR et cinq archives de la bibliothèque de Kenneth French, met
les fichiers en cache dans la couche `raw` du lac, et réécrit l'ensemble de `results/`. Deux
exécutions consécutives rendent des tableaux identiques au fichier près, seul l'identifiant
d'expérience changeant dans `metrics.json`. La vérification a été faite par comparaison des
répertoires le 2026-09-02.

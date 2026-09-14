# Tableau de bord du laboratoire

Engendré le 2026-09-04 par `quant dashboard build`, commit `ad1f741`. Chaque chiffre
vient d'un fichier du dépôt, nommé sous chaque tableau. Rien ici n'est un conseil en
investissement.

## L'état en quatre nombres

- **21 études** menées, verdicts : 7 `EXPERIMENTAL`, 13 `REJECTED`, 1 `REPLICATED`.
- **866 essais déclarés** dans les configurations, qui entrent dans le ratio de Sharpe dégonflé.
- **149 expériences** au registre, 866 essais sur les dernières exécutions.
- **2489 fonctions de test**, dont les gardiens d'architecture et de style.

Les résumés ont été relus le 13 septembre 2026. Les séries chiffrées conservent leur date de calcul indiquée ci-dessus.
Le [parcours pédagogique](../guide/index.md) et les [présentations des études](../etudes/index.md) expliquent les résultats et leurs limites.

## Les verdicts

Source : `studies/*/config.yaml` et `studies/*/results/metrics.json` ; la phrase de résultat vient
de `studies/README.md`.

| Étude | Essais | Verdict | Ce qui a été mesuré |
|---|---:|---|---|
| 001 Momentum de série temporelle | 73 | `EXPERIMENTAL` | Le Sharpe du facteur publié passe de 1,411 sur 1985-2009 à 0,337 après juin 2012, avant frais. La comparaison n'isole pas la publication comme cause. |
| 002 Momentum transversal | 53 | `EXPERIMENTAL` | L'écart gagnant moins perdant reste positif, à 0,768 % par mois sur 1994-2026 avant frais, mais son incertitude limite la conclusion. |
| 003 Valeur et momentum, partout | 207 | `EXPERIMENTAL` | Sur janvier 1972 à juin 2026, la corrélation vaut -0,577 et le mélange présente un Sharpe brut de 1,096. La date du prix employé dans le signal compte. |
| 004 Qualité moins camelote | 67 | `EXPERIMENTAL` | La construction sur rapports SEC présente une corrélation de 0,098 avec AQR sur juin 2015 à mai 2026. Les écarts de données ne permettent pas d'isoler une cause unique. |
| 005 Parier contre le bêta | 144 | `REJECTED` | Sur janvier 2001 à juin 2026, la réduction du bêta vers sa référence fait passer le Sharpe reconstruit de 0,394 à -0,001, avant la grille de coûts. |
| 006 Portefeuilles gérés en volatilité | 89 | `REJECTED` | L'alpha descriptif sur la fenêtre du papier se retrouve à 4,743 % par an, avant frais. La position calculable avec les informations passées ne satisfait pas les critères nets. |
| 007 Arbitrage statistique | 49 | `REJECTED` | Le seuil de coût de la reconstruction vaut 3,916 points de base par unité négociée. Il reste inférieur aux cinq points de base retenus dans l'article. |
| 008 Portage | 33 | `REPLICATED` | Le coefficient de portage vaut 1,084 sur novembre 1983 à septembre 2012. La comparaison est sensible à l'inclusion du dollar dans le classement. |
| 009 Huit sources d'alpha, un portefeuille | 20 | `REJECTED` | La référence ne dépasse pas sa meilleure composante. Son Sharpe dans la fenêtre finale de janvier 2020 à juin 2026 vaut 0,214, sur des composantes brutes. |
| 010 La capacité des deux stratégies chiffrables | 8 | `REJECTED` | Le capital compatible avec le plafond de participation du suivi de tendance vaut environ 84 940 dollars dans le modèle. Ce n'est pas une capacité commerciale observée. |
| 011 Arbres contre régression, après coûts | 17 | `REJECTED` | Les méthodes réduisent l'erreur face à zéro, mais les classements moyens restent négatifs. L'avantage prédictif des arbres sur la régression n'est pas suffisamment établi. |
| 012 Le portefeuille 009 sur séries nettes | 20 | `REJECTED` | Après les frais des composantes, la référence présente un Sharpe de -0,396 sur janvier 2020 à juin 2026. La diversification ne suffit pas à satisfaire les critères. |
| 013 Arbres contre régression sur quarante ans de survivants | 17 | `REJECTED` | Les prévisions semblent meilleures sur l'historique long, mais le panel ne restitue pas les entreprises disparues. L'effet pur de cette sélection n'est pas isolé. |
| 014 Ce que la publication laisse, huit stratégies ensemble | 12 | `EXPERIMENTAL` | Les huit stratégies montrent une baisse du rendement moyen après publication. La moyenne des baisses relatives vaut 72,7 %, avant frais et avec des fenêtres différentes. |
| 015 Ce que le forfait gratuit de Polygon donne pour un univers sans biais de survie | 3 | `REJECTED` | L'accès testé début septembre 2026 fournit 6 425 radiations datées, sans les prix anciens suffisants pour l'univers demandé. Le constat porte sur cet accès daté. |
| 016 Ce que la publication laisse, 212 portefeuilles sans biais de survie | 9 | `EXPERIMENTAL` | Sur 208 comparaisons brutes, 82,7 % montrent une baisse après publication. La médiane conserve 41,9 % du rendement antérieur. L'interprétation reste descriptive. |
| 017 Viser devant la cible, forme simple | 10 | `REJECTED` | Le rééquilibrage partiel réduit la rotation, mais son Sharpe net vaut 0,162 contre 0,176 après publication, jusqu'en juin 2026. |
| 018 La nuit contre la journée | 6 | `EXPERIMENTAL` | La décomposition sur janvier 2007 à juin 2026 situe les gains du momentum temporel la nuit. Elle ne calcule pas une règle nocturne après exécution et coûts. |
| 019 Marché, taille et momentum sur les cryptomonnaies | 10 | `REJECTED` | Le momentum présente un Sharpe net de -0,600 sur 213 semaines après publication. Le coût de base vaut 50 points de base par unité négociée et l'univers reste incomplet. |
| 020 Les meilleures idées des gestionnaires concentrés, lues à leur date de dépôt | 6 | `REJECTED` | La série composée des écarts mensuels au marché rapporte -0,05 % par an après les coûts modélisés, sur 157 mois. 28,9 % des idées formées n'ont pas de prix. |
| 021 Le portefeuille de primes pré-inscrit | 13 | `REJECTED` | Le portefeuille présente un Sharpe net de 0,629, contre 0,696 pour sa meilleure composante sur les mêmes 187 mois. Il manque le critère de supériorité retenu. |

## Les séries, et ce qu'elles valent

Une série de tête par étude, nette de coûts quand une version nette existe, plus les
portefeuilles construits dessus. Mensuel, brut de frais de gestion. Source :
`studies/*/results/series/`, mesures de `quantlab.analytics`. Les figures de richesse
cumulée partent de la première date commune à toutes les séries tracées, donc de la plus
courte d'entre elles.

| Série | Début | Fin | Années | Rendement composé (%) | Volatilité (%) | Sharpe | Pire repli (%) |
|---|---|---|---:|---:|---:|---:|---:|
| Momentum temporel, fonds cotés, net | 2007-01-31 | 2026-06-30 | 19,5 | 2,27 | 17,20 | 0,217 | -35,9 |
| Momentum transversal, survivants, net | 1991-01-31 | 2026-08-31 | 35,7 | -2,36 | 13,74 | -0,103 | -84,4 |
| Valeur et momentum, mélange, net | 1972-01-31 | 2026-06-30 | 54,5 | 4,53 | 4,15 | 1,092 | -11,6 |
| Qualité, notre construction, brut | 2015-06-30 | 2026-05-31 | 11,0 | 1,04 | 10,29 | 0,152 | -25,1 |
| Bêta défensif, déciles, net | 1966-07-31 | 2026-06-30 | 60,0 | 0,37 | 11,06 | 0,090 | -49,1 |
| Gestion de volatilité, temps réel, brut | 1946-08-31 | 2026-06-30 | 79,9 | -1,63 | 16,27 | -0,020 | -91,7 |
| Arbitrage statistique, net | 1996-01-31 | 2026-06-30 | 30,5 | -4,36 | 11,70 | -0,323 | -90,0 |
| Portage de change, net | 1971-02-28 | 2026-06-30 | 55,4 | 3,54 | 7,32 | 0,513 | -27,9 |
| Portefeuille 009, parité de risque, net | 2009-12-31 | 2026-06-30 | 16,6 | 2,28 | 3,59 | 0,646 | -7,7 |
| Portefeuille 009, parité hiérarchique, net, vue après coup | 2009-12-31 | 2026-06-30 | 16,6 | 2,70 | 2,96 | 0,916 | -4,3 |
| Portefeuille 012, parité de risque sur séries nettes | 2009-12-31 | 2026-06-30 | 16,6 | -0,49 | 3,37 | -0,128 | -18,7 |
| Étude 011, arbres, décile long moins court, net | 2020-07-31 | 2026-06-30 | 6,0 | 10,23 | 16,83 | 0,663 | -18,4 |
| Étude 011, régression, décile long moins court, net | 2020-07-31 | 2026-06-30 | 6,0 | 3,69 | 20,48 | 0,277 | -27,7 |
| Étude 013, arbres sur survivants, décile net, biais de survie | 1996-02-29 | 2026-06-30 | 30,4 | 20,54 | 25,87 | 0,849 | -48,8 |
| Étude 017, momentum temporel à rapprochement partiel, net | 2007-01-31 | 2026-06-30 | 19,5 | 2,19 | 15,86 | 0,216 | -32,1 |

## Les trajectoires

![richesse_cumulee_tetes](figures/richesse_cumulee_tetes.png)

![rendement_cumule_tetes](figures/rendement_cumule_tetes.png)

![rendements_annuels_tetes](figures/rendements_annuels_tetes.png)

![correlations_tetes](figures/correlations_tetes.png)

![richesse_cumulee_portefeuilles](figures/richesse_cumulee_portefeuilles.png)

![fonds_fermes_rendements_annuels](figures/fonds_fermes_rendements_annuels.png)

![fonds_fermes_correlations](figures/fonds_fermes_correlations.png)

## Les comparaisons aux fonds réels

### Facteurs publiés contre fonds cotés, mensuel

Source : `benchmarks/results/facteurs_publies_contre_fonds_reels_2026-09-02.csv`.

| strategy | fund | n_periods | correlation | beta | r_squared | drawdown_overlap | reading |
|---|---|---|---:|---:|---:|---:|---|
| TSMOM (AQR) | AQMIX | 197 | 0,755 | 0,575 | 0,570 | 0,679 | même phénomène |
| TSMOM (AQR) | DBMF | 85 | 0,603 | 0,496 | 0,363 | 0,485 | apparenté, à une autre échelle |
| TSMOM (AQR) | KMLM | 66 | 0,669 | 0,667 | 0,447 | 0,725 | apparenté |
| BAB USA (AQR) | BTAL | 178 | 0,484 | 0,829 | 0,234 | 0,240 | apparenté |
| BAB USA (AQR) | USMV | 177 | 0,192 | 0,248 | 0,037 | 0,271 | distinct |
| QMJ USA (AQR) | QUAL | 156 | -0,372 | -0,555 | 0,138 | 0,122 | distinct |
| Momentum US (VME) | MTUM | 159 | 0,249 | 0,332 | 0,062 | 0,273 | distinct |
| Décile gagnant 12-2 (KF) | MTUM | 159 | 0,887 | 0,658 | 0,787 | 0,571 | même phénomène |
| Valeur US (VME) | VLUE | 159 | 0,159 | 0,225 | 0,025 | 0,375 | distinct |
| TSMOM (AQR) | QSPIX | 152 | 0,133 | 0,125 | 0,018 | 0,451 | distinct |
| BAB USA (AQR) | QMNIX | 141 | 0,167 | 0,178 | 0,028 | 0,191 | distinct |


### Portefeuille 009 contre grands fonds fermés, annuel

Source : `benchmarks/results/fonds_fermes_contre_portefeuille_009_2026-09-02.csv`.

| fund_label | n_years | correlation | corr_lo | corr_hi | mean_fund | mean_strategy | mean_strategy_at_10pct_vol | reading |
|---|---|---:|---:|---:|---:|---:|---:|---|
| Medallion (Renaissance Technologies) | 9 | 0,381 | -0,379 | 0,834 | 0,376 | 0,035 | 0,100 | aucun co-mouvement établi |
| Wellington (Citadel) | 8 | 0,514 | -0,299 | 0,895 | 0,197 | 0,005 | 0,015 | aucun co-mouvement établi |
| Composite (D.E. Shaw) | 7 | 0,457 | -0,451 | 0,900 | 0,171 | 0,003 | 0,009 | aucun co-mouvement établi |
| Oculus (D.E. Shaw) | 4 | n.d. | n.d. | n.d. | 0,254 | -0,013 | -0,037 | trop peu d'années communes (4) |
| Millennium International (Millennium Management) | 4 | n.d. | n.d. | n.d. | 0,119 | 0,010 | 0,029 | trop peu d'années communes (4) |
| Pure Alpha (Bridgewater Associates) | 5 | 0,146 | -0,845 | 0,911 | 0,106 | -0,001 | -0,005 | aucun co-mouvement établi |
| Apex (AQR Capital Management) | 2 | n.d. | n.d. | n.d. | 0,173 | -0,006 | -0,018 | trop peu d'années communes (2) |
| TCI Master Fund (TCI Fund Management) | 7 | -0,415 | -0,890 | 0,492 | 0,201 | 0,009 | 0,026 | aucun co-mouvement établi |
| Elliott Associates (Elliott Investment Management) | 2 | n.d. | n.d. | n.d. | 0,053 | 0,027 | 0,076 | trop peu d'années communes (2) |
| Point72 (Point72 Asset Management) | 5 | -0,293 | -0,934 | 0,795 | 0,145 | -0,013 | -0,038 | aucun co-mouvement établi |
| Atlas Enhanced (Balyasny Asset Management) | 4 | n.d. | n.d. | n.d. | 0,107 | 0,010 | 0,029 | trop peu d'années communes (4) |


## Les dernières expériences du registre

Source : `artifacts/experiments.jsonl`, non suivi par git, régénéré par chaque exécution.

| Expérience | Terminée | Verdict | Essais | Commit |
|---|---|---|---:|---|
| portefeuille_de_primes_021-69102ec468 | 2026-09-05T00:38:23 | REJECTED | 13 | ad1f741 |
| portefeuille_de_primes_021-647aed02d0 | 2026-09-05T00:35:34 | REJECTED | 12 | ad1f741 |
| portefeuille_de_primes_021-697ff3c888 | 2026-09-05T00:26:36 | REJECTED | 12 | ad1f741 |
| meilleures_idees_13f_020-deb95ed444 | 2026-09-04T23:26:22 | REJECTED | 6 | 3e0ad4d |
| meilleures_idees_13f_020-c4a4e54440 | 2026-09-04T23:17:48 | REJECTED | 6 | 3e0ad4d |
| meilleures_idees_13f_020-2414d79a75 | 2026-09-04T22:55:08 | EXPERIMENTAL | 4 | 3e0ad4d |
| facteurs_crypto_019-47e871b885 | 2026-09-04T22:40:01 | REJECTED | 10 | 3e0ad4d |
| univers_polygon_015-da2a56dc17 | 2026-09-04T22:27:50 | REJECTED | 3 | 3e0ad4d |
| viser_devant_la_cible_017-4fc5bcdc6c | 2026-09-04T22:19:51 | REJECTED | 10 | 3e0ad4d |
| nuit_contre_journee_018-3a2bb7dc89 | 2026-09-04T22:19:20 | EXPERIMENTAL | 6 | 3e0ad4d |
| publication_decay_212_016-2634c31f9b | 2026-09-04T22:13:34 | EXPERIMENTAL | 9 | 3e0ad4d |
| publication_decay_212_016-74bf31ebcf | 2026-09-04T22:10:53 | EXPERIMENTAL | 9 | 3e0ad4d |

## Comment lire ce tableau

Aucune étude n'atteint `ROBUST`, et c'est le résultat du laboratoire, pas son échec : les
facteurs publiés se répliquent dans leur fenêtre et ne survivent pas à la publication, aux
coûts ou à la taille. Le parcours qui l'établit est décrit dans
[la méthodologie](../methodology/gauntlet.md), et chaque verdict dans le README de son étude.

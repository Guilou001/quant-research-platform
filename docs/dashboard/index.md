# Tableau de bord du laboratoire

Engendré le 2026-09-03 par `quant dashboard build`, commit `a85ff62`. Chaque chiffre
vient d'un fichier du dépôt, nommé sous chaque tableau. Rien ici n'est un conseil en
investissement.

## L'état en quatre nombres

- **11 études** menées, verdicts : 4 `EXPERIMENTAL`, 6 `REJECTED`, 1 `REPLICATED`.
- **760 essais déclarés** dans les configurations, qui entrent dans le ratio de Sharpe dégonflé.
- **128 expériences** au registre, 760 essais sur les dernières exécutions.
- **2413 fonctions de test**, dont les gardiens d'architecture et de style.

## Les verdicts

Source : `studies/*/config.yaml` et `studies/*/results/metrics.json` ; la phrase de résultat vient
de `studies/README.md`.

| Étude | Essais | Verdict | Ce qui a été mesuré |
|---|---:|---|---|
| 001 Momentum de série temporelle | 73 | `EXPERIMENTAL` | Sur la série des auteurs eux-mêmes, le ratio de Sharpe passe de 1,411 dans leur fenêtre à 0,337 après publication, et la chute est distinguable du hasard, z = 3,239. |
| 002 Momentum transversal | 53 | `EXPERIMENTAL` | Le t de l'écart gagnant moins perdant tombe de 5,12 à 1,746, et le biais de survie RETIRE 2,04 à 4,34 points de pourcentage par an au lieu d'en ajouter. |
| 003 Valeur et momentum, partout | 207 | `EXPERIMENTAL` | La corrélation valeur contre momentum vaut -0,577, le mélange à parts égales porte un Sharpe de 1,096 contre 0,593 pour la meilleure jambe, et 35 % de ce gain vient de la seule corrélation. |
| 004 Qualité moins camelote | 67 | `EXPERIMENTAL` | Le facteur publié se réplique, notre construction sur les fondamentaux point-in-time de la SEC ne le reproduit pas, corrélation 0,106, et la cause est identifiée : notre univers de grandes capitalisations perd la charge de taille qui porte le facteur. |
| 005 Parier contre le bêta | 144 | `REJECTED` | Le facteur ne s'affaiblit pas après publication, p = 0,960, mais le rétrécissement de 0,6 vers un décide de tout : il fait passer le Sharpe reconstruit de 0,394 à -0,001. |
| 006 Portefeuilles gérés en volatilité | 89 | `REJECTED` | L'alpha se réplique sur huit contrôles sur huit, et la version négociable rapporte -1,30 %/an net avec un Sharpe hors échantillon de -0,362. |
| 007 Arbitrage statistique | 49 | `REJECTED` | Le Sharpe brut se réplique, 1,460 contre 1,44, et le coût de seuil de rentabilité vaut 3,92 points de base contre les 5 que l'article lui-même suppose. |
| 008 Portage | 33 | `REPLICATED` | Le coefficient du test central se retrouve à 0,5 % près, 1,084 contre 1,09, et il tombe à 0,303 avec un t de 0,294 après la fin de l'échantillon. |
| 009 Huit sources d'alpha, un portefeuille | 20 | `REJECTED` | Huit stratégies valent 5,4 paris indépendants. Quatre allocations sur six battent la meilleure stratégie seule, mais pas la parité de risque désignée à l'avance, et la parité hiérarchique qui domine tout ne peut pas être retenue après coup. |
| 010 La capacité des deux stratégies chiffrables | 8 | `REJECTED` | Le momentum sur fonds cotés est borné par la participation avant de l'être par l'impact : à un million de dollars, un rééquilibrage sur quatre demande plus de dix pour cent du volume d'un fonds de devises. L'arbitrage statistique a une capacité nulle, son brut ne couvrant pas les cinq points de base de l'article sur 1996-2026. Statut modélisé. |
| 011 Arbres contre régression, après coûts | 17 | `REJECTED` | Six méthodes sur 1 526 grandes capitalisations et onze ans : R² mensuel hors échantillon de 0,35 % à 0,48 %, dans la plage de l'article, mais corrélation de rang négative pour les six. Les arbres amplifiés rendent un décile net à 0,663 contre 0,277 pour la régression, sans la battre au test de Diebold et Mariano, p 0,65 ; le linéaire est gardé. |

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
| Portage de change, net | 1971-02-28 | 2026-06-30 | 55,3 | 3,57 | 7,33 | 0,516 | -27,9 |
| Portefeuille 009, parité de risque, net | 2009-12-31 | 2026-06-30 | 16,5 | 2,34 | 3,65 | 0,652 | -7,3 |
| Portefeuille 009, parité hiérarchique, net, vue après coup | 2009-12-31 | 2026-06-30 | 16,5 | 2,68 | 2,99 | 0,900 | -4,3 |
| Étude 011, arbres, décile long moins court, net | 2020-07-31 | 2026-06-30 | 6,0 | 10,23 | 16,83 | 0,663 | -18,4 |
| Étude 011, régression, décile long moins court, net | 2020-07-31 | 2026-06-30 | 6,0 | 3,69 | 20,48 | 0,277 | -27,7 |

## Les trajectoires

![richesse_cumulee_tetes](figures/richesse_cumulee_tetes.png)

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
| Medallion (Renaissance Technologies) | 9 | 0,381 | -0,379 | 0,834 | 0,376 | 0,035 | 0,098 | aucun co-mouvement établi |
| Wellington (Citadel) | 7 | 0,792 | 0,096 | 0,968 | 0,190 | 0,013 | 0,034 | co-mouvement établi |
| Composite (D.E. Shaw) | 6 | 0,757 | -0,142 | 0,972 | 0,167 | 0,012 | 0,031 | aucun co-mouvement établi |
| Oculus (D.E. Shaw) | 3 | n.d. | n.d. | n.d. | 0,253 | 0,001 | -0,000 | trop peu d'années communes (3) |
| Millennium International (Millennium Management) | 4 | n.d. | n.d. | n.d. | 0,119 | 0,009 | 0,024 | trop peu d'années communes (4) |
| Pure Alpha (Bridgewater Associates) | 5 | 0,244 | -0,813 | 0,927 | 0,106 | -0,002 | -0,010 | aucun co-mouvement établi |
| Apex (AQR Capital Management) | 2 | n.d. | n.d. | n.d. | 0,173 | -0,005 | -0,016 | trop peu d'années communes (2) |
| TCI Master Fund (TCI Fund Management) | 6 | -0,623 | -0,953 | 0,381 | 0,212 | 0,018 | 0,050 | aucun co-mouvement établi |
| Elliott Associates (Elliott Investment Management) | 2 | n.d. | n.d. | n.d. | 0,053 | 0,023 | 0,064 | trop peu d'années communes (2) |
| Point72 (Point72 Asset Management) | 4 | n.d. | n.d. | n.d. | 0,141 | -0,005 | -0,018 | trop peu d'années communes (4) |
| Atlas Enhanced (Balyasny Asset Management) | 4 | n.d. | n.d. | n.d. | 0,107 | 0,009 | 0,024 | trop peu d'années communes (4) |


## Les dernières expériences du registre

Source : `artifacts/experiments.jsonl`, non suivi par git, régénéré par chaque exécution.

| Expérience | Terminée | Verdict | Essais | Commit |
|---|---|---|---:|---|
| cross_sectional_ml_011-2528fedf66 | 2026-09-02T23:23:31 | REJECTED | 17 | 54c17e0 |
| capacity_010-bec3cf46ac | 2026-09-02T22:38:43 | REJECTED | 8 | f2c4e60 |
| multi_strategy_009-2f1046ec7f | 2026-09-02T21:15:17 | REJECTED | 20 | 5b77898 |
| multi_strategy_009-df2c355fdf | 2026-09-02T21:14:31 | REJECTED | 15 | 5b77898 |
| 005_betting_against_beta-b21f54089f | 2026-09-02T21:13:18 | REJECTED | 144 | 5b77898 |
| 008_carry-f9c8c75b19 | 2026-09-02T21:10:53 | REPLICATED | 33 | 5b77898 |
| 007_statistical_arbitrage-413ede5568 | 2026-09-02T21:10:49 | REJECTED | 49 | 5b77898 |
| 005_betting_against_beta-0a707f3062 | 2026-09-02T21:10:39 | REJECTED | 144 | 5b77898 |
| 008_carry-452800285a | 2026-09-02T21:07:03 | REPLICATED | 33 | 5b77898 |
| 002_cross_sectional_momentum-48b737b531 | 2026-09-02T21:06:29 | EXPERIMENTAL | 53 | 5b77898 |
| 006_volatility_managed-6084d59b46 | 2026-09-02T20:54:45 | REJECTED | 89 | 5b77898 |
| 005_betting_against_beta-fd8db8b3be | 2026-09-02T20:54:32 | REJECTED | 144 | 5b77898 |

## Comment lire ce tableau

Aucune étude n'atteint `ROBUST`, et c'est le résultat du laboratoire, pas son échec : les
facteurs publiés se répliquent dans leur fenêtre et ne survivent pas à la publication, aux
coûts ou à la taille. Le parcours qui l'établit est décrit dans
[la méthodologie](../methodology/gauntlet.md), et chaque verdict dans le README de son étude.

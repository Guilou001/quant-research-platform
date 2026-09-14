# Les études

Chaque étude présente une question, un exemple fictif et les résultats enregistrés.
Les méthodes et commandes restent dans une annexe technique voisine.
Le [cours en huit chapitres](../docs/guide/index.md) explique les notions communes.

## Les expériences et leurs références

| Numéro | Étude | Article | Essais | Verdict |
|---|---|---|---:|---|
| 001 | [Momentum de série temporelle](001_time_series_momentum/) | Moskowitz, Ooi et Pedersen (2012) | 73 | `EXPERIMENTAL` |
| 002 | [Momentum transversal](002_cross_sectional_momentum/) | Jegadeesh et Titman (1993) | 53 | `EXPERIMENTAL` |
| 003 | [Valeur et momentum, partout](003_value_and_momentum/) | Asness, Moskowitz et Pedersen (2013) | 207 | `EXPERIMENTAL` |
| 004 | [Qualité moins camelote](004_quality_minus_junk/) | Asness, Frazzini et Pedersen (2019) | 67 | `EXPERIMENTAL` |
| 005 | [Parier contre le bêta](005_betting_against_beta/) | Frazzini et Pedersen (2014) | 144 | `REJECTED` |
| 006 | [Portefeuilles gérés en volatilité](006_volatility_managed/) | Moreira et Muir (2017) | 89 | `REJECTED` |
| 007 | [Arbitrage statistique](007_statistical_arbitrage/) | Avellaneda et Lee (2010) | 49 | `REJECTED` |
| 008 | [Portage](008_carry/) | Koijen, Moskowitz, Pedersen et Vrugt (2018) | 33 | `REPLICATED` |
| 009 | [Huit sources d'alpha, un portefeuille](009_multi_strategy/) | Grinold (1989), DeMiguel et coauteurs (2009) | 20 | `REJECTED` |
| 010 | [La capacité des deux stratégies chiffrables](010_capacity/) | Almgren et coauteurs (2005), Gatheral (2010) | 8 | `REJECTED` |
| 011 | [Arbres contre régression, après coûts](011_cross_sectional_ml/) | Gu, Kelly et Xiu (2020) | 17 | `REJECTED` |
| 012 | [Le portefeuille 009 sur séries nettes](012_multi_strategy_net/) | Grinold (1989), DeMiguel et coauteurs (2009) | 20 | `REJECTED` |
| 013 | [Arbres contre régression sur quarante ans de survivants](013_cross_sectional_ml_long/) | Gu, Kelly et Xiu (2020) | 17 | `REJECTED` |
| 014 | [Ce que la publication laisse, huit stratégies ensemble](014_publication_decay/) | McLean et Pontiff (2016) | 12 | `EXPERIMENTAL` |
| 015 | [Ce que le forfait gratuit de Polygon donne pour un univers sans biais de survie](015_univers_polygon/) | spécification 001, documentation de Polygon | 3 | `REJECTED` |
| 016 | [Ce que la publication laisse, 212 portefeuilles sans biais de survie](016_publication_decay_212/) | McLean et Pontiff (2016), Chen et Zimmermann (2022) | 9 | `EXPERIMENTAL` |
| 017 | [Viser devant la cible, forme simple](017_viser_devant_la_cible/) | Gârleanu et Pedersen (2013) | 10 | `REJECTED` |
| 018 | [La nuit contre la journée](018_nuit_contre_journee/) | Lou, Polk et Skouras (2019) | 6 | `EXPERIMENTAL` |
| 019 | [Marché, taille et momentum sur les cryptomonnaies](019_facteurs_crypto/) | Liu, Tsyvinski et Wu (2022) | 10 | `REJECTED` |
| 020 | [Les meilleures idées des gestionnaires concentrés, lues à leur date de dépôt](020_meilleures_idees_13f/) | Cohen, Polk et Silli (2010) | 6 | `REJECTED` |
| 021 | [Le portefeuille de primes pré-inscrit](021_portefeuille_de_primes/) | Hurst, Ooi et Pedersen (2017) ; Asness, Moskowitz et Pedersen (2013) ; Cboe et Wilshire (2019) | 13 | `REJECTED` |

Les verdicts décrivent les critères du laboratoire, dans le périmètre de chaque étude.
Ils ne remplacent pas les fenêtres, les coûts et les limites des données.
Les articles consultés en version de travail ou seulement par résumé restent signalés.

## Ce que chaque étude a mesuré
**001.** Le Sharpe du facteur publié passe de 1,411 sur 1985-2009 à 0,337 après juin 2012, avant frais. La comparaison n'isole pas la publication comme cause.

**002.** L'écart gagnant moins perdant reste positif, à 0,768 % par mois sur 1994-2026 avant frais, mais son incertitude limite la conclusion.

**003.** Sur janvier 1972 à juin 2026, la corrélation vaut -0,577 et le mélange présente un Sharpe brut de 1,096. La date du prix employé dans le signal compte.

**004.** La construction sur rapports SEC présente une corrélation de 0,098 avec AQR sur juin 2015 à mai 2026. Les écarts de données ne permettent pas d'isoler une cause unique.

**005.** Sur janvier 2001 à juin 2026, la réduction du bêta vers sa référence fait passer le Sharpe reconstruit de 0,394 à -0,001, avant la grille de coûts.

**006.** L'alpha descriptif sur la fenêtre du papier se retrouve à 4,743 % par an, avant frais. La position calculable avec les informations passées ne satisfait pas les critères nets.

**007.** Le seuil de coût de la reconstruction vaut 3,916 points de base par unité négociée. Il reste inférieur aux cinq points de base retenus dans l'article.

**008.** Le coefficient de portage vaut 1,084 sur novembre 1983 à septembre 2012. La comparaison est sensible à l'inclusion du dollar dans le classement.

**009.** La référence ne dépasse pas sa meilleure composante. Son Sharpe dans la fenêtre finale de janvier 2020 à juin 2026 vaut 0,214, sur des composantes brutes.

**010.** Le capital compatible avec le plafond de participation du suivi de tendance vaut environ 84 940 dollars dans le modèle. Ce n'est pas une capacité commerciale observée.

**011.** Les méthodes réduisent l'erreur face à zéro, mais les classements moyens restent négatifs. L'avantage prédictif des arbres sur la régression n'est pas suffisamment établi.

**012.** Après les frais des composantes, la référence présente un Sharpe de -0,396 sur janvier 2020 à juin 2026. La diversification ne suffit pas à satisfaire les critères.

**013.** Les prévisions semblent meilleures sur l'historique long, mais le panel ne restitue pas les entreprises disparues. L'effet pur de cette sélection n'est pas isolé.

**014.** Les huit stratégies montrent une baisse du rendement moyen après publication. La moyenne des baisses relatives vaut 72,7 %, avant frais et avec des fenêtres différentes.

**015.** L'accès testé début septembre 2026 fournit 6 425 radiations datées, sans les prix anciens suffisants pour l'univers demandé. Le constat porte sur cet accès daté.

**016.** Sur 208 comparaisons brutes, 82,7 % montrent une baisse après publication. La médiane conserve 41,9 % du rendement antérieur. L'interprétation reste descriptive.

**017.** Le rééquilibrage partiel réduit la rotation, mais son Sharpe net vaut 0,162 contre 0,176 après publication, jusqu'en juin 2026.

**018.** La décomposition sur janvier 2007 à juin 2026 situe les gains du momentum temporel la nuit. Elle ne calcule pas une règle nocturne après exécution et coûts.

**019.** Le momentum présente un Sharpe net de -0,600 sur 213 semaines après publication. Le coût de base vaut 50 points de base par unité négociée et l'univers reste incomplet.

**020.** La série composée des écarts mensuels au marché rapporte -0,05 % par an après les coûts modélisés, sur 157 mois. 28,9 % des idées formées n'ont pas de prix.

**021.** Le portefeuille présente un Sharpe net de 0,629, contre 0,696 pour sa meilleure composante sur les mêmes 187 mois. Il manque le critère de supériorité retenu.

## Refaire et documenter

Chaque dossier contient un README guidé, une ANNEXE_TECHNIQUE et un script run.py.
Les paramètres et les sorties gardent leur emplacement dans l'étude.
Les textes éditoriaux communs se modifient dans documentation, puis se régénèrent avec make learn.

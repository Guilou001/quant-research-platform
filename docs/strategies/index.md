# Les stratégies

**Huit réplications menées, aucune candidate au portefeuille.** C'est le
résultat de la phase 4, et il est plus instructif qu'une réussite.

| Étude | Article | Verdict | Ce qui décide |
|---|---|---|---|
| 001 Momentum de série temporelle | Moskowitz, Ooi et Pedersen (2012) | `EXPERIMENTAL` | Sharpe 1,411 puis 0,337, z = 3,239 |
| 002 Momentum transversal | Jegadeesh et Titman (1993) | `EXPERIMENTAL` | t de 5,12 puis 1,746 |
| 003 Valeur et momentum | Asness, Moskowitz et Pedersen (2013) | `EXPERIMENTAL` | corrélation -0,577, mélange 1,096 |
| 004 Qualité moins camelote | Asness, Frazzini et Pedersen (2019) | `EXPERIMENTAL` | notre construction corrèle 0,106 avec le facteur publié |
| 005 Parier contre le bêta | Frazzini et Pedersen (2014) | `REJECTED` | le rétrécissement de 0,6 fait passer le Sharpe de 0,394 à -0,001 |
| 006 Portefeuilles gérés en volatilité | Moreira et Muir (2017) | `REJECTED` | version négociable à -1,30 %/an net |
| 007 Arbitrage statistique | Avellaneda et Lee (2010) | `REJECTED` | seuil de rentabilité 3,92 points de base |
| 008 Portage | Koijen et coauteurs (2018) | `REPLICATED` | coefficient 1,084 contre 1,09, puis 0,303 hors échantillon |

Comment lire ce tableau, en trois constats. Le premier est que sept articles sur
huit se répliquent correctement dans leur propre fenêtre, donc ce n'est pas la
réplication qui échoue. Le deuxième est que ce qui échoue est la survie, tantôt à
la publication, tantôt aux coûts, tantôt à une hypothèse de construction que
l'article ne discute pas. Le troisième est que le seul verdict `REPLICATED` est
aussi celui dont trois classes d'actifs sur quatre n'ont pas pu être testées.

## Ce que la phase a appris, au-delà des verdicts

**Un article peut se répliquer parfaitement et rester inutilisable.** L'étude 006
retrouve les huit chiffres publiés de Moreira et Muir, dont l'erreur type de
l'alpha au centième. Sa version réellement négociable perd de l'argent. La
réplication et l'investissabilité sont deux questions différentes, et confondre
les deux est la faute que ce laboratoire existe pour éviter.

**Une hypothèse de construction non discutée peut porter tout le résultat.**
L'étude 005 mesure que le rétrécissement du bêta de 0,6 vers un, présenté par
Frazzini et Pedersen comme un détail d'estimation, fait passer le ratio de
Sharpe du facteur reconstruit de 0,394 à -0,001. Le classement des titres est
pourtant identique dans les deux cas.

**Le biais de survie ne va pas toujours dans le sens qu'on croit.** L'étude 002
mesure qu'il RETIRE 2,04 à 4,34 points de pourcentage par an au momentum, parce
qu'un décile perdant reconstitué sur un indice actuel se remplit de titres tombés
puis remontés.

**Une source publiée peut porter un défaut silencieux.** L'étude 003 relève que
les colonnes hors actions du classeur d'AQR s'arrêtent au 2025-01-31 alors que la
colonne agrégée court jusqu'au 2026-06-30, sans que le fichier le signale. Le
ratio de Sharpe hors échantillon passe de 0,604 à 0,246 selon la colonne lue.

## L'ordre de lecture

Les études se lisent dans l'ordre des numéros, qui est celui de la difficulté
croissante des données. Chacune vit dans `studies/NNN_nom/` avec son README, sa
configuration, son point d'entrée et ses résultats régénérables.

Le parcours de validation qu'elles traversent toutes est décrit dans
[Le parcours d'une stratégie](../methodology/gauntlet.md).

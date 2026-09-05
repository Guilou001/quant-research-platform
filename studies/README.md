# Les études

Une étude est une réplication académique autonome à la lecture et dépendante au
calcul. Elle se lit sans connaître les autres, et elle appelle le ratio de
Sharpe du paquet partagé plutôt que le sien.

## Ce que les études ont trouvé

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

Comment lire ce tableau, en quatre constats. Le premier est qu'**aucune étude
n'atteint `ROBUST` ni `PORTFOLIO_CANDIDATE`**, donc aucune ne mérite du capital
en l'état, et c'est le résultat le plus important de la phase. Le deuxième est
que sept des huit articles se répliquent correctement dans leur propre fenêtre :
ce n'est pas la réplication qui échoue, c'est la survie. Le troisième est que la
colonne des essais entre dans le ratio de Sharpe dégonflé, et que les 207 essais
de l'étude 003 le ramènent à 0,000012. Le quatrième est que le seul
`REPLICATED` est aussi celui dont trois classes d'actifs sur quatre n'ont pas pu
être testées faute de données.

## Ce que chaque étude a mesuré, en une ligne

**001.** Sur la série des auteurs eux-mêmes, le ratio de Sharpe passe de 1,411
dans leur fenêtre à 0,337 après publication, et la chute est distinguable du
hasard, z = 3,239.

**002.** Le t de l'écart gagnant moins perdant tombe de 5,12 à 1,746, et le
biais de survie RETIRE 2,04 à 4,34 points de pourcentage par an au lieu d'en
ajouter.

**003.** La corrélation valeur contre momentum vaut -0,577, le mélange à parts
égales porte un Sharpe de 1,096 contre 0,593 pour la meilleure jambe, et 35 % de
ce gain vient de la seule corrélation.

**004.** Le facteur publié se réplique, notre construction sur les fondamentaux
point-in-time de la SEC ne le reproduit pas, corrélation 0,106, et la cause est
identifiée : notre univers de grandes capitalisations perd la charge de taille
qui porte le facteur.

**005.** Le facteur ne s'affaiblit pas après publication, p = 0,960, mais le
rétrécissement de 0,6 vers un décide de tout : il fait passer le Sharpe reconstruit
de 0,394 à -0,001.

**006.** L'alpha se réplique sur huit contrôles sur huit, et la version
négociable rapporte -1,30 %/an net avec un Sharpe hors échantillon de -0,362.

**007.** Le Sharpe brut se réplique, 1,460 contre 1,44, et le coût de seuil de
rentabilité vaut 3,92 points de base contre les 5 que l'article lui-même suppose.

**008.** Le coefficient du test central se retrouve à 0,5 % près, 1,084 contre
1,09, et il tombe à 0,303 avec un t de 0,294 après la fin de l'échantillon.

**009.** Huit stratégies valent 5,4 paris indépendants. Trois allocations sur
six battent la meilleure stratégie seule, mais pas la parité de risque désignée
à l'avance, et la parité hiérarchique qui domine tout ne peut pas être retenue
après coup.

**010.** Le momentum sur fonds cotés est borné par la participation avant de
l'être par l'impact : à un million de dollars, un rééquilibrage sur quatre
demande plus de dix pour cent du volume d'un fonds de devises. L'arbitrage
statistique a une capacité nulle, son brut ne couvrant pas les cinq points de
base de l'article sur 1996-2026. Statut modélisé.

**011.** Six méthodes sur 1 526 grandes capitalisations et onze ans : R²
mensuel hors échantillon de 0,35 % à 0,48 %, dans la plage de l'article, mais
corrélation de rang négative pour les six. Les arbres amplifiés rendent un
décile net à 0,663 contre 0,277 pour la régression, sans la battre au test de
Diebold et Mariano, p 0,65 ; le linéaire est gardé.

**012.** Le portefeuille de l'étude 009 sur les séries nettes de chaque
stratégie rend -0,128 de Sharpe contre 0,535 pour la meilleure jambe seule.
Les corrélations n'ont pas bougé, les signes si : l'arbitrage statistique net,
à -0,932, retire 0,379 de Sharpe là où sa version brute en apportait 0,250.

**013.** Sur 502 survivants du S&P 500 rejoués depuis 1986, tout est positif,
R² de 1,6 % et déciles nets de 0,60 à 0,85, et c'est le signe du biais de
survie plutôt qu'un mérite : les arbres ne battent toujours pas la régression
au test de Diebold et Mariano, p 0,58, et un titre encore dans l'indice a
remonté par construction.

**014.** Les huit stratégies perdent après la publication de leur article, 73 % du
rendement mensuel moyen par la moyenne des rapports et 67 % par la régression,
contre 58 % chez McLean et Pontiff. Entre la fin de l'échantillon et la
publication, elles ne perdent presque rien contre 26 %, parce que ce sont celles
que leurs années suivantes n'ont pas démenties.

**015.** Le forfait gratuit de Polygon rend deux ans de prix et refuse 2008, mais son
référentiel des radiations est entier depuis 2004 : des actions ordinaires cotées
en 2014, la moitié ont disparu, mesuré sur 6 425 radiations datées.

**016.** Sur 208 portefeuilles de Chen et Zimmermann, construits sur CRSP donc sans
biais de survie, le rendement après publication vaut en moyenne 53 % de celui de
la fenêtre de l'article et 42 % en médiane, 83 % des prédicteurs baissent, et la
part perdue ne dépend pas de la force du prédicteur ; ceux publiés depuis 2010
ont perdu 94 % de leur rendement.

**017.** Ne parcourir que la moitié du chemin vers la cible, taux choisi avant
publication, réduit la rotation du momentum de série temporelle de 9,15 à 5,75
fois le capital par an et rend pourtant un Sharpe net de 0,162 contre 0,176 au
rééquilibrage complet ; la rotation n'est pas le levier, le signal l'est.

**018.** Le momentum de série temporelle gagne tout son rendement la nuit, 10,2 %
par an de la clôture à l'ouverture avec un t de 3,8, et perd 3,0 % par an le
jour ; MTUM gagne 99 % de son rendement la nuit, USMV 34 %, et le marché lui-même
62 %.

**019.** Les trois facteurs des cryptomonnaies se retrouvent dans la fenêtre de
l'article, momentum à 2,65 % par semaine, et perdent les cinq sixièmes de leur
rendement après sa parution ; le momentum négocie deux fois le capital par
semaine et rend -0,60 de Sharpe net de cinquante points de base.

**020.** La plus grosse position de chaque gestionnaire 13F concentré, formée le
quarante-sixième jour après le trimestre, rapporte 14,29 % par an contre 14,18 %
pour SPY, écart +0,27 %, t 0,26, bêta 1,08 : c'est l'indice des survivants, et
28,9 % des idées n'ont aucun prix, 50 % en 2013. La valeur des jeux 13F est en
milliers de dollars jusqu'en 2022, lue déclaration par déclaration.

**021.** Le portefeuille de primes déclaré avant tout calcul, tendance, valeur et
momentum, vente de puts, en inverse de volatilité et empilé à 1,5, rend 0,629 de
Sharpe net sur 2010-2026 et 0,88 en holdout, quatre sous-périodes positives ; il
est rejeté parce que la vente de puts seule fait 0,696, que le t vaut 2,30 et que
la tendance sur fonds cotés lui coûte 0,25, ce que la pré-inscription interdit de
corriger après coup.

## L'arborescence d'une étude

```
studies/NNN_nom_de_l_etude/
├── README.md            la fiche complète, quatorze sections
├── config.yaml          paramètres et seuils du verdict, écrits AVANT les résultats
├── run.py               le point d'entrée, sans logique réutilisable
├── notes.md             le journal, essais ratés compris
└── results/             les sorties régénérables : metrics.json, tables/, figures/
```

Toute logique réutilisable monte dans `src/quantlab/strategies/`, parce qu'une
métrique implémentée dans une étude finit par diverger de la même métrique
implémentée dans la suivante.

## Le gabarit du README d'étude

Quatorze sections, dans cet ordre : la question de recherche, l'article,
l'intuition économique, la définition mathématique, les données, la méthodologie
originale, notre implémentation, nos écarts avec l'article, les résultats, la
robustesse, les coûts, le hors échantillon, les limites, le verdict.

La section « Les résultats » porte chaque chiffre avec ses cinq mentions
obligatoires : échantillon, brut ou net, hypothèses de coût, période, univers.
Tout nombre publié vient d'un fichier de `results/`, et le README dit lequel.

## Comment ces études ont été contrôlées

Chaque étude a été menée, puis **contredite** par un second passage chargé de la
mettre en défaut : relance depuis zéro, confrontation de chaque nombre du README
aux fichiers de résultats, chasse à la fuite temporelle, recomptage des essais et
recalcul du verdict.

Ce contrôle a trouvé, sur les huit études, 34 chiffres de README qui ne
correspondaient pas aux résultats, 30 nombres publiés sans source, un compte
d'essais sous-déclaré de 183 à 207 qui rendait le ratio de Sharpe dégonflé trop
flatteur, et un univers de survivants qui n'était pas déclaré.

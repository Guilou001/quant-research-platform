# Journal de l'étude 005, parier contre le bêta

Ce journal porte les décisions, les essais ratés et les mesures qui n'entrent pas dans le README.
Il se lit dans l'ordre du travail, du 2026-09-02.

## 1. Ce que la fiche de littérature a réglé avant la première ligne de code

**La consigne de mission et la fiche ne disaient pas la même chose.** La consigne annonçait une
corrélation estimée sur trois ans de rendements HEBDOMADAIRES recouvrants. La fiche
`docs/literature/frazzini_pedersen_2014_bab.md` écrit cinq ans de rendements recouvrants de TROIS
JOURS, avec au moins 750 séances, et cite la page 17 de la version de travail. La consigne demandait
elle-même de vérifier dans la fiche avant de coder. C'est donc la fiche qui a été suivie, et l'écart
est déclaré ici plutôt que résolu en silence.

**Le sens du rétrécissement a été relu deux fois.** La fiche avertit que l'extraction textuelle du
PDF perd les symboles et fait lire les coefficients à l'envers. Le poids de 0,6 porte sur
l'estimation temporelle et 0,4 sur la valeur un. Un test le fige : un bêta de 2 doit devenir 1,6 et
non 1,4. La mutation qui inverse les deux poids fait tomber trois tests sur trente-trois.

**La fenêtre recouvrante de l'article regarde en avant.** Son écriture somme les rendements de
`t` à `t+2`, donc l'observation datée `t` contient deux séances futures. Le cas de référence de
l'étude somme `t-2` à `t`. Les deux alignements sont implémentés, et un test exige que celui de
l'article ÉCHOUE au contrôle `assert_causal` tandis que le nôtre le passe. L'écart de performance
entre les deux vaut 0,003 point de ratio de Sharpe, mesuré dans `results/tables/overlap_sweep.csv`.

## 2. Les essais ratés, dans l'ordre

**Le poids de rétrécissement nul a fait tomber le premier lancement.** La grille de robustesse
écrite dans `config.yaml` contenait la valeur 0,0. Elle rend tous les bêtas égaux à un, donc aucun
classement n'existe, `leg_weights` lève `DataQualityError` à chaque date, et `bab_portfolio` termine
sur `InsufficientDataError`. La valeur a été remplacée par 0,8, ce qui garde quatre points de grille
et couvre l'intervalle utile. Le remplacement est un correctif technique, pas un déplacement de
seuil, et le commentaire de `config.yaml` le dit.

**Le minimum d'observations fixe a fait tomber le deuxième lancement.** La grille de fenêtres de
volatilité descend à 63 séances alors que le minimum de l'article vaut 120, ce qui est impossible à
remplir. Le minimum suit désormais la fenêtre dans la proportion de l'article, 120 sur 252 pour la
volatilité et 750 sur 1 250 pour la corrélation. La règle vit dans `_scaled_minimum` de `run.py` et
elle est documentée.

**Le troisième lancement a buté sur un nom d'attribut.** `CostAnalysis` expose
`breakeven_multiplier` et `status`, et non `surviving_multiplier`. La logique de l'étude 006 a été
reprise telle quelle, qui rend le multiple de rupture s'il existe, le plus grand multiple testé si la
stratégie survit à tout, et zéro sinon.

**Une figure a été refaite parce qu'elle exposait un nom de clé interne.** La première version du
graphique par marché employait `subperiod_bars`, dont l'axe horizontal s'intitule « Sous-période » et
dont l'axe vertical reprenait le nom de colonne `sharpe_full`. Vingt-quatre marchés ne sont pas des
sous-périodes. Le graphique est devenu une carte de chaleur à deux lignes, avant et après avril 2012,
qui dit en plus quelque chose que la version en barres ne disait pas.

**Une carte de chaleur triait ses colonnes en texte.** Les écarts de financement s'affichaient dans
l'ordre 0, 100, 150, 200, 25, 300, 50, 500. Les étiquettes sont désormais complétées par des zéros,
ce qui remet l'ordre numérique. Le défaut ne levait aucune erreur et se voyait seulement à l'oeil.

**Une figure annonçait des dollars canadiens.** `equity_curve` porte une devise par défaut, et le
titre parlait de dollars des États-Unis pendant que l'axe parlait de dollars canadiens. L'argument
`currency` est maintenant passé explicitement.

## 3. Ce qui a été mesuré avant d'écrire un seuil, et ce qui ne l'a pas été

**Le seuil de 0,15 sur le bêta réalisé a été fixé APRÈS un prototype.** Le prototype du 2026-09-02,
lancé avant l'écriture du contrôle de réplication, rendait déjà un bêta réalisé de -0,18 sur les
déciles. Le seuil de 0,15 a donc été écrit en sachant qu'il échouerait. Il est conservé tel quel
parce qu'il est la lecture large de « proche de zéro », l'article annonçant un bêta ex ante de 0,00 et
un bêta réalisé de -0,06. L'alternative aurait été de l'élargir à 0,25 pour le faire passer, ce que
la règle du laboratoire interdit.

**Les sept autres seuils de verdict n'ont jamais bougé.** Ils sont ceux du laboratoire, identiques à
ceux de l'étude 006, et ils ont été écrits dans `config.yaml` avant le premier lancement.

**Une tolérance absolue est nécessaire pour ce contrôle.** `decide_verdict` refuse toute tolérance
dont l'équivalent relatif dépasse la tolérance déclarée de l'étude. Une valeur publiée nulle n'a pas
d'équivalent relatif, donc le contrôle est jugé sur sa seule tolérance absolue. Poser la cible à
-0,06, le bêta réalisé de l'article, aurait exigé une tolérance absolue de 0,015 pour rester sous
0,25 en relatif, ce qui n'a aucun sens économique.

## 4. Ce que le prototype a trouvé et que le README publie

Le prototype a mesuré, sur les déciles de Kenneth French, que le bêta réalisé du facteur passe de
+0,08 sans rétrécissement à -0,18 au rétrécissement de l'article. Ce constat a décidé de la forme de
l'étude : le poids de rétrécissement est devenu l'axe principal de tous les balayages, et la grille
des fenêtres d'estimation est passée au second plan. Le balayage complet a confirmé le prototype sur
trente-six cellules de la jambe B2.

Le sens de l'effet est arithmétique, et il est vérifié à la main dans le README. Le rétrécissement ne
change ni le classement ni la composition des jambes, seulement les diviseurs. Sur la jambe B2 sans
rétrécissement, les diviseurs valent 0,577 et 1,498 pour des bêtas réalisés de 0,590 et 1,510, donc
la neutralisation est presque exacte. Au rétrécissement de 0,6 les diviseurs deviennent 0,747 et
1,299, et l'exposition résiduelle vaut -0,40.

## 5. Les choix que l'étude n'a pas faits, et pourquoi

**L'univers CRSP complet n'a pas été cherché.** Il n'est pas public, et sa reconstruction dépasse le
cadre. La conséquence est nommée dans les limites : la critique de concentration sur les petites
capitalisations n'est mesurable qu'à l'échelle des déciles.

**Les portefeuilles quotidiens de Kenneth French n'ont pas été employés comme troisième univers.**
Les fichiers `25_Portfolios_5x5_Daily` et `10_Portfolios_Prior_12_2_Daily` sont déclarés dans
`quantlab.data.providers.french` et donneraient un univers quotidien sans biais de survie remontant à
1926. La recette exacte de l'article y serait applicable. Le choix a été écarté pour tenir la
consigne, qui nomme deux univers et demande de les comparer. C'est un report assumé, pas un oubli.

**Les alphas par marché ne sont pas calculés.** Le tableau V de l'article régresse chaque marché sur
des facteurs locaux, que Kenneth French publie pour les régions développées mais pas marché par
marché dans les jeux déclarés du dépôt. Régresser le pari contre le bêta japonais sur les facteurs
américains n'aurait aucun sens. Seuls les ratios de Sharpe et leurs erreurs types de Lo sont publiés
par marché.

**Le coût d'emprunt de titre n'est pas modélisé.** `config.yaml` porte `borrow_bps_annual` à zéro.
La jambe courte de nos deux constructions porte des portefeuilles agrégés ou des grandes
capitalisations, donc bon marché à emprunter, mais l'omission est déclarée dans les limites.

**La correction de Newey-West n'a pas été employée dans les régressions d'attribution.** L'article
publie des moindres carrés ordinaires, et changer d'estimateur de covariance aurait rendu les alphas
non comparables aux siens. L'argument existe dans `factor_regression` et n'a pas été activé.

## 6. Le compte des essais

Cent quarante-quatre essais sont enregistrés, familles comprises, et le détail vit dans
`results/tables/trials.csv`. Le compte attendu est calculé dans `run.py` avant l'ouverture du
registre, à partir des seules longueurs de grilles, et un écart avec le compte réel lève une
`RuntimeError`. Le contrôle a servi : il a attrapé le passage de seize à trente-deux essais de
financement quand la grille est passée d'une série à deux.

Trois familles portent la série publiée par AQR plutôt qu'une stratégie candidate, les quatre
fenêtres et les vingt-quatre marchés. Elles sont comptées quand même, ce qui durcit le ratio de
Sharpe dégonflé plutôt que de le flatter.

## 7. Les contrôles par mutation

La règle 10 du laboratoire exige qu'un test attrape un défaut plutôt que de le verrouiller. Trois
mutations ont été introduites puis retirées, le 2026-09-02.

| Mutation introduite | Tests qui tombent |
|---|---:|
| Le rétrécissement pèse 0,4 sur l'estimation et 0,6 sur un | 3 |
| Le décalage entre formation et détention est supprimé | 2 |
| La fenêtre recouvrante accepte une somme incomplète | 1 |

Les trente-trois tests passent une fois les mutations retirées. Un test tombe sur la première
mutation sans porter sur le rétrécissement : celui qui exige un bêta de deux pour un titre construit
à deux fois le marché. Il mesure donc la chaîne entière.

## 8. Ce qui reste à vérifier

La lecture selon laquelle le poids de 0,6 est calibré pour un univers plus bruité que le nôtre est
**modélisée**, et non mesurée. La vérifier demande de refaire l'exercice sur l'univers CRSP complet,
en comparant le bêta ex ante brut au bêta réalisé par tranche de capitalisation. Tant que ce n'est
pas fait, l'étude affirme seulement que le rétrécissement de 0,6 biaise l'estimation sur les deux
univers publics testés.

Le désaccord avec Novy-Marx et Velikov sur la dispersion transversale des bêtas n'est pas résolu. Ils
mesurent que la volatilité de marché en explique 58 %, nous mesurons 0,3 % avec une valeur p de
0,376. Deux différences de protocole sont candidates, l'univers et la période, et aucune n'a été
isolée.

## 9. Ce que la contre-vérification du 2026-09-02 a trouvé

L'étude a été rejouée de zéro et confrontée ligne par ligne à ses propres fichiers. La reproduction
est exacte : les vingt-neuf tableaux du premier lot sont revenus identiques octet pour octet, et
`metrics.json` ne différait que par son identifiant d'expérience. Les dix configurations archivées
sous `reports/` sont elles aussi identiques entre elles, donc aucun seuil n'a bougé entre le premier
lancement enregistré et le dernier.

**Le défaut de fond : l'alpha du financement était brut de frais de rotation.** `_alpha_at_spread`
appelait `_net_returns` avec un coût de rotation nul, alors que `financing.csv`, la carte de chaleur
et toute la chaîne du verdict facturent dix points de base. L'écart annoncé qui annule l'alpha de la
série de référence, 110 points de base, supposait donc la rotation gratuite. Facturée, l'alpha de
départ tombe de 0,036 à 0,0075 % par mois et l'écart qui l'annule tombe à **22,8 points de base**,
soit près de cinq fois moins. Les colonnes `alpha_4f_at_zero_net_pct`, `alpha_zero_spread_net_bps` et
`breakeven_spread_net_bps` sont ajoutées, et la métrique
`ecart_de_financement_qui_annule_lalpha_net_bps` est publiée avec son étiquette de coût. Le titre de
la section et la synthèse du README sont refaits. Le verdict ne bouge pas : ce critère n'entre pas
dans `decide_verdict`.

**Trois défauts de figure.** Le titre imposé de `equity_bab` annonçait « base 1 dollar au
1966-07-31 ». L'axe, lui, était déduit des données et annonçait « au départ de chaque courbe », la
courbe des titres commençant en 2001. La carte `parameter_heatmap` triait ses lignes en TEXTE, donc
« corrélation 750 j » se plaçait après « corrélation 2500 j ». Ses étiquettes de colonne portaient en
outre un point décimal quand ses cases portaient une virgule. La carte `financing_heatmap` affichait
« base net » et « base gross », les clés du code, à un lecteur français. Les trois sont corrigés.

**Trois défauts de rédaction.** L'étendue maximale d'une ligne du balayage vaut 0,632 point de ratio
de Sharpe et non 0,61. Le multiple de coût survécu de 3,876 était attribué à
`cost_multiples.csv`, qui ne le contient pas : il vit dans `metrics.json`, et le tableau n'en donne
que les deux bornes. Le classement des couvertures était annoncé comme reproduisant celui de
Novy-Marx et Velikov alors que seule sa moitié le reproduit, leur version pondérée par la
capitalisation arrivant dernière chez eux et deuxième chez nous.

**Une figure orpheline.** `return_histogram.png` était produite sans mode d'emploi dans le README,
contrairement à la règle du gabarit. Le mode d'emploi est ajouté.

**Un piège de lecture laissé en place et désormais nommé.** `cumulative_wealth` fait porter au
premier point tracé le rendement du premier mois, donc aucune courbe ne part de 1,00. Sur les deux
séries qui commencent en 1966 le décalage est invisible ; sur celle des titres il vaut 30,5 %,
mesuré, et la courbe part visiblement à 0,70. La convention vit dans `quantlab.analytics.returns` et
n'a pas été touchée, elle est expliquée dans le mode d'emploi de la figure.

**Une objection qui manquait, et qui est ajoutée.** L'étude concluait que le bêta brut est
« remarquablement juste ». Sur les déciles il ne l'est pas pour la jambe courte : 1,468 ex ante
contre 1,371 réalisé, soit 7,0 % de trop. C'est exactement la compression des bêtas que la
proposition 4 de l'article décrit. Un rétrécissement a donc bien lieu d'être. Ce que l'étude
établit est que le poids 0,6 sur-corrige, et non qu'il faut renoncer à rétrécir.

**Une objection examinée et écartée.** Le contrôle de réplication qui échoue compare notre bêta
réalisé à 0,00, le bêta EX ANTE de l'article, alors que `config.yaml` porte aussi son bêta RÉALISÉ de
-0,06, jamais employé. Viser -0,06 ne sauverait pas le contrôle. `decide_verdict` convertit toute
tolérance absolue en son équivalent relatif et refuse celles qui dépassent la tolérance déclarée de
0,25 ; la tolérance recevable serait donc de 0,015 pour un écart mesuré de 0,122. Le contrôle échoue
dans les deux lectures. La section 3 de ce journal l'avait déjà écrit.

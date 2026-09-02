# Parier contre le bêta

## La question de recherche

Le pari contre le bêta rapporte-t-il parce que les investisseurs ne peuvent pas emprunter, ou parce
que sa construction repose sur trois choix non standard que rien n'oblige à faire ?

**La réponse, en trois phrases.** Le facteur publié se réplique de près : 0,676 % par mois contre
0,70 publié, ratio de Sharpe 0,703 contre 0,78. Il ne s'affaiblit pas après l'article, l'écart de
ratio de Sharpe entre l'avant et l'après avril 2012 valant 0,015 pour une valeur p de 0,96. Notre reconstruction, elle,
tient tout entière à un seul réglage, le rétrécissement du bêta de poids 0,6 vers un. Ce réglage
précis fait passer le bêta réalisé de notre facteur de +0,08 à -0,18 sur les déciles. Sur les titres,
il le fait passer de +0,07 à -0,40, et il ramène le rendement à zéro. Le verdict déduit est `REJECTED`, parce que
le ratio de Sharpe hors échantillon de la série de référence vaut **-0,002**.

Ces trois phrases ne se contredisent pas. La première porte sur la série que les auteurs publient, la
deuxième sur la recette qu'ils décrivent, et l'écart entre les deux est le résultat de l'étude.
Chaque chiffre ci-dessous vient d'un fichier de `results/`, et le fichier est nommé.

## L'article

Frazzini, A. et Pedersen, L. H. (2014), « Betting against beta », *Journal of Financial Economics*
111(1), 1-25, DOI 10.1016/j.jfineco.2013.10.005.

La version publiée n'a pas été obtenue, ScienceDirect étant payant. Les chiffres cibles viennent de
la **version de travail du 10 mai 2013**, dont les tableaux III et V sont recopiés dans
`docs/literature/frazzini_pedersen_2014_bab.md`. Statut de ces chiffres : **rapportés**.

Trois publications répondent à l'article, et l'étude les prend au sérieux.

| Auteurs | Revue | Ce qu'ils opposent |
|---|---|---|
| Novy-Marx et Velikov (2022) | *Journal of Financial Economics* 143(1) | Trois procédures non standard. La pondération par les rangs, la couverture par le levier, et un estimateur de bêta qui mélange bêta de marché et volatilité. |
| Bali, Brown, Murray et Tang (2017) | *Journal of Financial and Quantitative Analysis* 52(6) | L'anomalie disparaît quand on neutralise la demande de loterie. Explication concurrente, pas réfutation des chiffres. |
| Asness, Frazzini, Gormsen et Pedersen (2020) | *Journal of Financial Economics* 135(3) | Réponse des auteurs. Seule la part de corrélation du bêta serait liée aux contraintes de levier. |

## L'intuition économique

Le rendement viendrait d'une contrainte institutionnelle, et non d'une prime de risque.

Le modèle d'évaluation des actifs financiers suppose que chacun détient le portefeuille au meilleur
rapport rendement sur risque, puis ajuste son levier. Or beaucoup d'investisseurs ne peuvent pas
emprunter. Celui qui veut du rendement sans levier achète donc directement les titres à bêta élevé,
le bêta étant la sensibilité du rendement d'un titre à celui du marché. Sa demande fait monter le
prix de ces titres, donc baisser leur rendement futur.

L'article écrit l'alpha d'équilibre d'un titre comme le produit de la tension de financement par un
moins son bêta. L'alpha décroît donc mécaniquement dans le bêta, et la droite de marché des titres
s'aplatit. Qui peut emprunter fait l'inverse du contraint : il achète du bêta faible et l'amplifie.

**Ce qui ferait disparaître le rendement est nommable.** La contrainte devrait cesser de mordre, ce
qui rendrait la droite de marché à sa pente théorique. Deux autres extinctions sont plus proches. Le
prix du levier peut manger le gain, puisque la stratégie emprunte. Et l'estimateur de bêta peut
cesser de neutraliser le marché, ce qui est le cas mesuré ici.

## La définition mathématique

**Le bêta ex ante**, équation (16) de l'article, n'est pas un bêta de régression :

\[ \hat{\beta}^{TS}_{i,t} = \hat{\rho}_{i,t} \, \frac{\hat{\sigma}_{i,t}}{\hat{\sigma}_{m,t}} \]

Les deux morceaux ne se mesurent pas sur le même horizon. Les volatilités emploient un an de
rendements logarithmiques quotidiens, avec au moins 120 séances. La corrélation emploie cinq ans de
rendements logarithmiques recouvrants de trois jours, avec au moins 750 séances.

**Le rétrécissement**, page 17, tire l'estimation vers la valeur un :

\[ \hat{\beta}_{i,t} = w \, \hat{\beta}^{TS}_{i,t} + (1 - w) \, \beta^{XS}, \qquad w = 0{,}6, \quad \beta^{XS} = 1 \]

**Les poids**, équation (17). Soit \(z\) le vecteur des rangs de bêta et \(\bar{z}\) leur moyenne :

\[ w_H = k (z - \bar{z})^{+}, \qquad w_L = k (z - \bar{z})^{-}, \qquad k = \frac{2}{\mathbf{1}'_n \lvert z - \bar{z} \rvert} \]

**Le facteur**, équation (18), divise chaque jambe par son bêta ex ante :

\[ r^{BAB}_{t+1} = \frac{1}{\beta^{L}_{t}}\left(r^{L}_{t+1} - r^{f}\right) - \frac{1}{\beta^{H}_{t}}\left(r^{H}_{t+1} - r^{f}\right) \]

Le bêta ex ante du facteur vaut donc exactement zéro par construction, puisque chaque jambe est
ramenée à un bêta de un. C'est une identité, et non un résultat.

## Les données

Cinq jeux, tous publics, mesurés le 2026-09-02. Source : `results/tables/data_sources.csv`.

| Source | Jeu | Première date | Dernière date | Lignes | Colonnes |
|---|---|---|---|---:|---:|
| AQR | `Betting-Against-Beta-Equity-Factors-Monthly.xlsx` | 1930-12-31 | 2026-06-30 | 1 147 | 29 |
| Kenneth French | `Portfolios_Formed_on_BETA` | 1963-07-31 | 2026-06-30 | 756 | 15 |
| Kenneth French | `F-F_Research_Data_Factors` | 1926-07-31 | 2026-06-30 | 1 200 | 4 |
| Kenneth French | `F-F_Research_Data_Factors_daily` | 1926-07-01 | 2026-06-30 | 26 274 | 4 |
| Yahoo | membres du S&P 500 relevés le 2026-09-02 | 1998-01-02 | 2026-06-30 | 7 166 | 503 |

**Comment lire ce tableau, en trois constats.** Un, le classeur d'AQR porte 29 colonnes, soit 24
marchés d'actions et cinq agrégats régionaux, et la colonne des États-Unis est la seule renseignée
avant 1984. Deux, les portefeuilles triés par bêta ne sont publiés qu'en fréquence **mensuelle**, ce
qui interdit d'y appliquer la recette quotidienne de l'article. Trois, les 503 titres de Yahoo sont
les membres d'AUJOURD'HUI de l'indice, donc cet univers porte un biais de survie, déclaré et non
corrigé.

**Ce que ces données ne sont pas.** Les 55 600 titres et 20 pays de l'article viennent de CRSP et de
XpressFeed Global, qui ne sont pas accessibles. Les blocs obligations d'État, crédit et contrats à
terme reposent sur trois sources privées, dont la base Bond.Hub de Barclays et un indice de détresse
fourni par Credit Suisse. Ils sont **non reconstructibles** et ne sont pas tentés.

## La méthodologie originale

L'article construit le facteur en quatre pas, chacun décidé et aucun standard.

Le bêta est estimé pour chaque titre à la fin de chaque mois, par la formule ci-dessus. Les titres
sont ensuite classés par bêta, et coupés à la médiane de leur classe d'actifs. Chaque titre reçoit
un poids proportionnel à la distance de son rang au rang moyen. La capitalisation n'entre donc nulle
part. Chaque jambe est enfin divisée par son bêta ex ante, ce qui amplifie la jambe longue et réduit
la jambe courte.

Aux États-Unis, ce montage achète en moyenne 1,40 dollar d'actions à bêta faible et vend à découvert
0,70 dollar d'actions à bêta élevé, page 19. Le rééquilibrage est mensuel, et le levier est supposé
obtenu au taux sans risque.

## Notre implémentation

La stratégie vit dans `src/quantlab/strategies/betting_against_beta.py`, et `run.py` ne fait
qu'orchestrer. Le module sépare trois objets que la formule mélange.

**L'estimateur** vit dans `frazzini_pedersen_beta`, qui rend aussi ses trois morceaux, corrélation,
volatilité du titre et volatilité du marché. Garder les morceaux permet de vérifier l'identité de
Novy-Marx et Velikov, ce que fait `beta_identity_terms`.

**La pondération** vit dans `leg_weights`, qui rend les rangs de l'article, l'équipondération, ou la
capitalisation. Les trois rendent deux séries positives qui somment à un, ce que la constante \(k\)
de l'équation (17) impose et qu'un test vérifie à 1e-12.

**Le portefeuille** vit dans `bab_portfolio`. Le décalage entre la formation et la détention s'y fait
en un seul endroit, par l'argument `execution_lag`, qui vaut un au cas de référence.

**Trois contrôles de causalité tiennent la chaîne.** Le bêta ex ante passe `assert_causal` de
`quantlab.features.transforms`. Un test perturbe le dernier mois de rendements et exige que rien
d'antérieur ne bouge dans le facteur. Un troisième test exige que l'écriture de l'article, dont la
fenêtre recouvrante regarde en AVANT, ÉCHOUE au même contrôle. Le contrôle par mutation confirme les
trois : inverser le rétrécissement fait tomber trois tests, supprimer le décalage en fait tomber
deux, et relâcher la fenêtre recouvrante en fait tomber un.

**Deux jambes construites, deux univers.** La jambe B1 emploie les dix déciles triés par bêta de
Kenneth French, sans biais de survie, en fréquence mensuelle. La jambe B2 emploie les 503 titres de
Yahoo, avec biais de survie déclaré, en fréquence quotidienne. Seule la seconde permet la recette
exacte de l'article.

Aucun paramètre ne vit dans le code. Le fichier `config.yaml` porte les 3 pondérations, les 2
pondérations internes et les 4 poids de rétrécissement. Il porte aussi les 3 fenêtres de volatilité,
les 3 fenêtres de corrélation, les 8 écarts de financement et les 8 seuils du verdict.

## Nos écarts avec l'article

**Nous répliquons la série publique d'AQR, qui n'est pas celle de l'article.** AQR diffuse un jeu
« original paper dataset » arrêté en mars 2012 et un facteur tenu à jour. Novy-Marx et Velikov
mesurent une corrélation de 96,2 % entre les deux après 1967, et un ratio de Sharpe significativement
plus élevé pour l'ancien. Notre colonne des États-Unis commence en décembre 1930 et non en janvier
1926, donc notre échantillon compte 976 mois là où l'article en compte 1 035.

**Notre univers de titres est celui d'aujourd'hui.** Les 503 membres du S&P 500 relevés le 2026-09-02
excluent par construction les sociétés disparues, ce qui flatte les deux jambes de façon inconnue. Le
biais est déclaré, jamais corrigé, et c'est la raison pour laquelle la jambe B1 existe.

**Notre bêta de la jambe B1 est estimé en fréquence mensuelle.** La bibliothèque de Kenneth French ne
publie aucun fichier quotidien pour les portefeuilles triés par bêta, vérifié le 2026-09-02 :
l'adresse `Portfolios_Formed_on_BETA_Daily_CSV.zip` répond 404 quand `Portfolios_Formed_on_BETA_CSV.zip`
répond 200. Nous employons donc douze mois pour les volatilités et soixante pour la corrélation, ce
qui suit les minima de douze et trente-six observations que l'article fixe pour les données
mensuelles. La correction de négociation non synchrone n'a pas de sens à cette fréquence, donc elle
est retirée de cette jambe.

**Notre fenêtre recouvrante regarde en arrière.** L'article écrit la somme de trois jours à partir de
la date courante, donc elle contient deux séances postérieures. Notre cas de référence somme les
trois séances qui se terminent à la date courante. L'écart est mesuré et vaut 0,003 point de ratio de
Sharpe, section « La robustesse ».

**Nous n'employons ni les obligations d'État, ni le crédit, ni les contrats à terme.** Trois sources
sont privées, et les remplacer par des séries de complaisance donnerait un résultat qui ne
répliquerait rien.

**Nous ajoutons trois objets que l'article n'a pas.** Un balayage du poids de rétrécissement, qui est
l'objet de l'étude. Un coût de financement du levier, que l'article suppose nul. Et une correction
pour tests multiples, que l'article ne fait pas.

**Nous écartons le poids de rétrécissement nul de la grille.** Il rend tous les bêtas égaux à un,
donc aucun classement n'existe et les deux jambes ne peuvent pas se former. Le défaut a été trouvé au
premier lancement, et le remplacement par 0,8 est déclaré dans `notes.md`.

## Les résultats

### Le facteur publié se réplique, et il ne s'affaiblit pas après l'article

Source : `results/tables/legA_windows.csv`. Colonne USA du classeur d'AQR, brut de frais, univers des
auteurs.

| Fenêtre | Échantillon | N | %/mois | Vol. %/an | Sharpe | t de la moyenne | Bêta réalisé |
|---|---|---:|---:|---:|---:|---:|---:|
| Complet, 1930-12 à 2026-06 | VALIDATION | 1 147 | 0,649 | 11,14 | 0,698 | 6,83 | -0,085 |
| Jusqu'à mars 2012 | IS | 976 | **0,676** | 11,54 | **0,703** | 6,34 | -0,088 |
| Depuis avril 2012 | OOS | 171 | 0,491 | 8,55 | **0,689** | 2,60 | -0,057 |
| Depuis janvier 2014 | OOS | 150 | 0,392 | 8,86 | 0,531 | 1,88 | -0,066 |

**Comment lire ce tableau, en trois constats.** Un, l'échantillon de l'article rend 0,676 % par mois
contre 0,70 publié et un ratio de Sharpe de 0,703 contre 0,78, sur 976 mois contre 1 035 puisque la
série publique commence en décembre 1930. Deux, le ratio de Sharpe postérieur à l'article vaut 0,689,
soit 0,015 de moins que dans l'échantillon. Le test de différence rend z égal à 0,050 et une valeur p
de 0,960 (`results/tables/legA_sharpe_difference.csv`), donc rien ne distingue les deux fenêtres.
Trois, la fenêtre postérieure à la publication de 2014 est moins bonne, 0,531, mais elle ne compte que
150 mois et son erreur type de Lo vaut 0,260.

Cette stabilité contraste avec le momentum de série temporelle, dont le ratio de Sharpe passe de
1,411 à 0,402 entre l'échantillon de son article et la suite, mesuré par l'étude 001.

### Les vingt-quatre marchés sont positifs, l'article en annonçait dix-huit sur dix-neuf

Source : `results/tables/legA_countries.csv`, brut de frais, échantillon complet de chaque marché.

| Grandeur mesurée | Valeur |
|---|---:|
| Marchés retenus, au moins 120 mois | 24 |
| Marchés au ratio de Sharpe positif | **24** |
| Marchés dont la statistique t dépasse 1,96 | 20 |
| Ratio de Sharpe médian | 0,526 |
| Marchés dont le Sharpe baisse après avril 2012 | 15 |
| Marchés dont l'écart est significatif à 5 % | **1** |

**Comment lire ce tableau, en trois constats.** Un, la prédiction internationale de l'article tient
et se renforce : il annonçait 18 marchés positifs sur 19, nous en mesurons 24 sur 24, l'Autriche qui
était sa seule exception ressortant à 0,213. Deux, quinze marchés sur vingt-quatre font moins bien
après avril 2012, ce qui ressemble à un affaiblissement, mais un seul écart est significatif, la
Finlande à z égal 1,963 et p égal 0,050. Trois, avec vingt-quatre tests menés, une seule valeur p à
0,050 est ce que le hasard produit, donc l'affaiblissement international n'est pas établi.

`results/figures/country_heatmap.png`. **Mode d'emploi.** Une colonne par marché, deux lignes pour
les deux fenêtres, une couleur par ratio de Sharpe. Comparer les deux lignes d'une même colonne
plutôt que deux colonnes entre elles, la longueur d'échantillon variant d'un marché à l'autre.

### L'alpha du facteur publié survit à quatre facteurs et tombe à six

Source : `results/tables/legA_attribution.csv`, moindres carrés ordinaires, alpha en pour cent par
mois, échantillon `IS` de décembre 1930 à mars 2012.

| Modèle | N | Alpha %/mois | t | Alpha publié | R² |
|---|---:|---:|---:|---:|---:|
| Un facteur | 976 | 0,733 | 6,89 | 0,73 | 0,021 |
| Trois facteurs | 976 | **0,741** | 6,93 | 0,73 | 0,021 |
| Quatre facteurs | 976 | **0,541** | 5,11 | 0,55 | 0,089 |
| Six facteurs | 585 | **0,190** | 1,51 | non publié | 0,319 |

**Comment lire ce tableau, en trois constats.** Un, les trois alphas que l'article publie se
retrouvent au centième de point, 0,741 contre 0,73 et 0,541 contre 0,55, ce qui atteste que nous
régressons la même série sur les mêmes facteurs. Deux, la ligne à six facteurs n'est pas dans
l'article. Ajouter la rentabilité et l'investissement de Fama et French fait tomber l'alpha à 0,190
avec un t de 1,51, donc il cesse d'être distinguable de zéro. Trois, les deux chargements
responsables valent 0,592 sur la rentabilité et 0,467 sur l'investissement, ce qui reproduit par une
implémentation indépendante les 0,45 et 0,50 que Novy-Marx et Velikov rapportent.

### Notre reconstruction retrouve le levier de l'article

Source : `results/tables/legB_leverage.csv`, moyenne sur toute la fenêtre de chaque jambe.

| Jambe | Publié | Déciles, rangs | Titres, rangs | Titres, sans rétrécissement |
|---|---:|---:|---:|---:|
| Longue, bêta faible | 1,40 | 1,188 | **1,367** | 1,975 |
| Courte, bêta élevé | 0,70 | 0,789 | **0,776** | 0,678 |

**Comment lire ce tableau, en trois constats.** Un, la jambe B2 au réglage de l'article achète 1,367
dollar et vend 0,776 dollar, contre 1,40 et 0,70 publiés, soit 2,4 % et 10,9 % d'écart. Deux, la
jambe B1 sur déciles achète moins, 1,188 dollar. Dix portefeuilles pondérés par la capitalisation ont
en effet des bêtas moins dispersés que 55 600 titres. Trois, sans rétrécissement la jambe
longue monte à 1,975 dollar, ce qui montre que le rétrécissement est le principal déterminant du
levier appliqué.

### Le rétrécissement de 0,6 décide de tout, et c'est le résultat de l'étude

Source : `results/tables/legB_realized_beta.csv`, jambe B1, rangs, rendements de décile pondérés par
la capitalisation, échantillon `VALIDATION` de juillet 1966 à juin 2026, 720 mois.

| Poids du rétrécissement | Bêta ex ante, jambe longue | Bêta réalisé, jambe longue | Bêta ex ante, jambe courte | Bêta réalisé, jambe courte | Bêta réalisé du facteur |
|---:|---:|---:|---:|---:|---:|
| 0,3 | 0,925 | 0,776 | 1,140 | 1,371 | **-0,377** |
| 0,6, celui de l'article | 0,850 | 0,776 | 1,281 | 1,371 | **-0,182** |
| 0,8 | 0,800 | 0,776 | 1,374 | 1,371 | -0,054 |
| 1,0, sans rétrécissement | 0,750 | 0,776 | 1,468 | 1,371 | **+0,081** |

**Comment lire ce tableau, en trois constats.** Un, les colonnes de bêta réalisé ne bougent pas avec
le rétrécissement, 0,776 et 1,371 partout. C'est normal : le rétrécissement est affine et croissant,
donc il ne change ni le classement ni la composition des jambes, seulement les diviseurs.
Deux, sans rétrécissement le bêta ex ante de la jambe longue vaut 0,750 contre 0,776 réalisé, soit
3,4 % d'écart, et le facteur ressort à un bêta réalisé de +0,081, donc à peu près neutre. Trois, au
réglage de l'article le bêta ex ante de la jambe longue monte à 0,850 alors que le réalisé reste à
0,776. Le levier de 1,188 ne suffit plus à neutraliser, et le facteur garde -0,182 de marché.

**L'objection la plus forte contre cette lecture, et ce qu'elle change.** Le rétrécissement n'est pas
gratuit : sans lui, la colonne de gauche du tableau surestime la jambe COURTE, 1,468 ex ante contre
1,371 réalisé, soit 7,0 % de trop. C'est exactement la compression des bêtas que la proposition 4 de
l'article décrit et que la note 14 invoque pour justifier de rétrécir. Un rétrécissement existe donc
bien à faire ici, et l'étude ne montre pas qu'il faut renoncer à rétrécir. Elle montre que le poids
0,6 SUR-CORRIGE : il déplace la jambe longue de 0,750 à 0,850 pour un réalisé de 0,776, alors que la
correction utile portait sur l'autre jambe. Le poids 0,8, seul point de grille intermédiaire, laisse
un bêta réalisé de -0,054, le plus proche de zéro des quatre. La grille ne dit pas où se trouve le
poids qui annulerait exactement le bêta, et l'étude ne l'a pas cherché.

Le même mécanisme est plus violent au niveau du titre. Source : `results/tables/legB_stocks.csv`,
échantillon `VALIDATION` de janvier 2001 à juin 2026, 306 mois, univers des 503 membres actuels du
S&P 500, brut de frais.

| Poids du rétrécissement | %/mois | Vol. %/an | Sharpe | t | Bêta réalisé | Bêta ex ante long | Bêta réalisé long |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0,3 | -0,330 | 16,48 | -0,240 | -1,37 | -0,663 | 0,873 | 0,590 |
| 0,6, celui de l'article | **-0,001** | 14,91 | **-0,001** | -0,01 | **-0,401** | 0,747 | 0,590 |
| 0,8 | 0,258 | 15,20 | 0,204 | 1,07 | -0,199 | 0,662 | 0,590 |
| 1,0, sans rétrécissement | **0,619** | 18,84 | **0,394** | 1,87 | **+0,073** | 0,577 | 0,590 |

**Comment lire ce tableau, en trois constats.** Un, sans rétrécissement le bêta ex ante de la jambe
longue vaut 0,577 contre 0,590 réalisé, soit 2,1 % d'écart. Celui de la jambe courte vaut 1,498
contre 1,510, soit 0,8 %, donc le bêta brut de l'article est juste à 2 % près sur cet univers. Deux, le
rétrécissement de 0,6 porte l'estimation de la jambe longue à 0,747, soit 26,5 % au-dessus du bêta
réalisé, et le facteur perd sa neutralité comme son rendement. Trois, entre 0,394 et -0,001 de ratio
de Sharpe, il n'y a que ce seul réglage, et le classement des titres est identique dans les deux cas.

**L'explication, et sa limite.** Le poids de 0,6 vient de la note 14 de l'article, qui rapporte une
moyenne empirique de 0,61 pour le facteur de Vasicek sur l'ensemble des actions américaines. Ce
facteur vaut un moins le rapport de la variance d'estimation à la variance totale, donc il est
d'autant plus bas que le bêta est mal estimé. Sur 55 600 titres dont beaucoup sont minuscules et peu
négociés, 0,6 se justifie. Sur 503 grandes capitalisations mesurées avec cinq ans de séances, le bêta
brut est déjà juste, et rétrécir devient un biais. Cette lecture est **modélisée**, et l'étude ne
peut pas la vérifier faute d'accès à l'univers CRSP complet.

### La critique de pondération de Novy-Marx et Velikov, mesurée

Source : `results/tables/legB_weighting.csv`, jambe B1, échantillon `VALIDATION` de juillet 1966 à
juin 2026, 720 mois, brut de frais. Ratio de Sharpe annualisé.

| Pondération dans le décile | Rangs, celle de l'article | Équipondérée | Capitalisation |
|---|---:|---:|---:|
| Capitalisation, rétrécissement 0,6 | **0,121** | 0,121 | 0,111 |
| Équipondérée, rétrécissement 0,6 | **0,291** | 0,287 | 0,262 |
| Capitalisation, sans rétrécissement | 0,286 | 0,280 | 0,253 |
| Équipondérée, sans rétrécissement | **0,639** | 0,624 | 0,593 |

**Comment lire ce tableau, en trois constats.** Un, la pondération par les rangs et
l'équipondération sont indiscernables, 0,121 contre 0,121 et 0,639 contre 0,624, ce qui confirme la
première moitié de la critique : les rangs ne font rien d'autre qu'équipondérer. Deux, passer à la
capitalisation coûte entre 7 % et 12 % du ratio de Sharpe, ce qui est réel mais modeste. C'est bien
moins que les deux tiers que Novy-Marx et Velikov mesurent au niveau du titre. Trois, le vrai levier
est ailleurs : la pondération À L'INTÉRIEUR des déciles fait plus que doubler le résultat, 0,291 contre 0,121, et
c'est l'équipondération interne qui donne du poids aux petites capitalisations.

**Pourquoi notre test de la critique est plus faible que le leur.** Les portefeuilles de Kenneth
French agrègent déjà les titres, donc la concentration sur le dernier centile de capitalisation
qu'ils mesurent, 1,05 dollar par dollar investi, n'est pas observable ici. Ce que nous mesurons est
la trace de cet effet à l'échelle des déciles, et elle va dans le même sens.

### La couverture par le marché bat la couverture par le levier

Source : `results/tables/nmv_hedge.csv`, jambe B1, rangs, échantillon commun de 660 mois, brut de
frais.

| Couverture | %/an | Vol. %/an | Sharpe | t | Bêta réalisé |
|---|---:|---:|---:|---:|---:|
| Par le levier, celle de l'article | 1,49 | 11,18 | **0,133** | 0,96 | -0,180 |
| Par le marché pondéré par la capitalisation | 2,36 | 11,73 | **0,201** | 1,43 | -0,072 |
| Par le marché équipondéré | 3,15 | 10,69 | **0,294** | 2,02 | -0,072 |

**Comment lire ce tableau, en trois constats.** Un, les trois séries couvrent les mêmes 660 mois, les
deux versions couvertes par un marché exigeant soixante mois d'estimation avant de commencer. Deux,
nous retrouvons la moitié de leur classement : la couverture par le marché équipondéré l'emporte sur
celle par le levier, 0,294 contre 0,133, et eux mesurent 1,26 contre 1,08. Trois, l'autre moitié est
INVERSÉE. Chez eux la couverture par le marché pondéré par la capitalisation arrive dernière, à 0,80
contre 1,08 pour le levier ; chez nous elle passe devant le levier, 0,201 contre 0,133. Notre
couverture par le levier est donc plus pénalisée que la leur, et l'explication est la même que plus
haut, un bêta ex ante trop rétréci qui laisse -0,180 d'exposition résiduelle.

### L'identité de Novy-Marx et Velikov tient à la précision machine

Source : `results/tables/nmv_identity.csv`. Ils établissent que le bêta de l'article se réécrit comme
le bêta de régression à cinq ans, corrigé par un rapport de rapports de volatilités. L'écart maximal
entre les deux membres vaut **1,78e-15** sur 2 712 162 cellules, donc l'identité est vérifiée et
notre estimateur est bien le leur.

Source : `results/tables/nmv_beta_artifact.csv`, 307 mois de janvier 2001 à juin 2026, bêtas non
rétrécis des 503 titres.

| Grandeur transversale | Moyenne | Écart type | Pente sur la volatilité de marché | R² | Valeur p |
|---|---:|---:|---:|---:|---:|
| Moyenne des bêtas | 1,003 | 0,163 | **-18,34** | **0,300** | 2,0e-25 |
| Dispersion des bêtas | 0,424 | 0,090 | -0,94 | 0,003 | 0,376 |

**Comment lire ce tableau, en trois constats.** Un, la moyenne transversale des bêtas devrait valoir
un en permanence et vaut 1,003 en moyenne, mais elle oscille d'un écart type de 0,163, donc elle
bouge. Deux, la volatilité de marché explique 30 % de cette oscillation, avec une valeur p de 2,0e-25.
C'est bien l'artefact que Novy-Marx et Velikov décrivent, eux qui mesurent 47 % sur le portefeuille
de marché CRSP. Trois, la dispersion transversale des bêtas, elle, n'est pas liée à la volatilité de
marché, R² de 0,003 et valeur p de 0,376. Ce résultat NE reproduit PAS leurs 58 %, et il est déclaré
tel quel.

## La robustesse

### Trente-six réglages de l'estimateur, et un seul axe qui compte

Source : `results/tables/parameter_sweep.csv`. Jambe B2, échantillon `VALIDATION` de janvier 2001 à
juin 2026, net de dix points de base, ratio de Sharpe annualisé.

| Fenêtres d'estimation | Rétrécissement 0,3 | 0,6 | 0,8 | 1,0 |
|---|---:|---:|---:|---:|
| Volatilité 63 j, corrélation 750 j | -0,271 | -0,022 | 0,173 | 0,328 |
| Volatilité 63 j, corrélation 1250 j | -0,245 | 0,003 | 0,203 | 0,353 |
| Volatilité 63 j, corrélation 2500 j | -0,213 | **0,058** | 0,264 | **0,400** |
| Volatilité 126 j, corrélation 750 j | -0,271 | -0,028 | 0,162 | 0,320 |
| Volatilité 126 j, corrélation 1250 j | -0,247 | -0,007 | 0,190 | 0,353 |
| Volatilité 126 j, corrélation 2500 j | -0,227 | 0,022 | 0,220 | 0,388 |
| Volatilité 252 j, corrélation 750 j | **-0,278** | -0,039 | 0,155 | 0,332 |
| Volatilité 252 j, corrélation 1250 j | -0,253 | -0,016 | 0,188 | 0,380 |
| Volatilité 252 j, corrélation 2500 j | -0,243 | -0,003 | 0,194 | 0,382 |

**Comment lire ce tableau, en trois constats.** Un, les neuf lignes se ressemblent, l'écart entre la
meilleure et la pire ligne d'une même colonne valant 0,11 point au plus : les fenêtres d'estimation
ne décident de rien. Deux, les quatre colonnes sont ordonnées et l'écart entre les extrêmes d'une même ligne vaut
jusqu'à 0,632 point de ratio de Sharpe : le rétrécissement décide de tout. Trois, la colonne de l'article, 0,6,
est celle qui traverse zéro, six cellules sur neuf y étant négatives.

`results/figures/parameter_heatmap.png` porte les mêmes trente-six cellules. **Mode d'emploi.** Une
ligne par couple de fenêtres, une colonne par poids de rétrécissement, une couleur par ratio de
Sharpe net. Lire les colonnes de gauche à droite plutôt que les lignes : c'est là que le gradient est.

### La fenêtre recouvrante ne change presque rien

Source : `results/tables/overlap_sweep.csv`, jambe B2, réglage de l'article, brut de frais.

| Fenêtre recouvrante | Alignement | Sharpe | Bêta réalisé |
|---|---|---:|---:|
| 1 séance, aucune correction | arrière | **0,0067** | -0,404 |
| 3 séances, celle de l'article | arrière | -0,0010 | -0,401 |
| 5 séances | arrière | -0,0009 | -0,393 |
| 3 séances | avant, celui de l'article | -0,0037 | -0,403 |

**Comment lire ce tableau, en trois constats.** Un, l'écart entre notre alignement arrière et
l'écriture de l'article vaut 0,003 point de ratio de Sharpe, donc le choix ne change pas les
conclusions. Notre alignement est en outre celui qui ne lit rien du futur. Deux, retirer entièrement la
correction de négociation non synchrone déplace le résultat de 0,008 point. Sur un univers de grandes
capitalisations, cette correction ne sert à rien, ce qui est cohérent avec sa raison d'être.
Trois, les quatre bêtas réalisés tiennent dans une plage de 0,011, donc la correction ne répare pas
le défaut de neutralité.

### Retarder l'exécution ne détruit rien

Source : `results/tables/execution_delay.csv`, jambe B1, rangs, brut de frais.

| Délai | N | %/an | Sharpe | Bêta réalisé |
|---|---:|---:|---:|---:|
| 1 mois, cas de référence | 720 | 1,337 | 0,121 | -0,182 |
| 2 mois | 719 | 1,610 | 0,145 | -0,184 |
| 3 mois | 718 | 1,790 | **0,164** | -0,194 |

**Comment lire ce tableau, en trois constats.** Un, retarder l'exécution AMÉLIORE le résultat, de
0,121 à 0,164, ce qui est l'inverse de ce qu'un signal à décroissance rapide donnerait. Deux, ce
profil dit que le bêta ex ante est une caractéristique lente, ce qui est cohérent avec une corrélation
estimée sur cinq ans. Trois, la stratégie n'est donc pas sensible au délai d'exécution, contrairement
au momentum intrajournalier ou à la gestion en volatilité.

### Les sous-périodes

Source : `results/tables/subperiods.csv`, série de référence, nette de dix points de base.

| Sous-période | N | Sharpe | t | Pire repli |
|---|---:|---:|---:|---:|
| 1966-07 à 1990-11 | 293 | **0,309** | 1,42 | -42,2 % |
| 1990-12 à 2012-02 | 255 | -0,048 | -0,22 | -46,6 % |
| 2012-03 à 2026-06 | 172 | 0,008 | 0,03 | -46,1 % |

**Comment lire ce tableau, en trois constats.** Un, deux sous-périodes sur trois sont positives, ce
qui donne la part de 0,667 comparée au seuil de 0,60 du verdict. Deux, aucune statistique t n'atteint
1,5 en valeur absolue, donc aucune sous-période ne dit rien à elle seule. Trois, le pire repli est le
même dans les trois tranches, autour de 45 %. La volatilité annuelle, elle, vaut 9,3 % dans la
première tranche, 12,2 % dans la deuxième et 12,0 % dans la troisième.

`results/figures/subperiod_bars.png`. **Mode d'emploi.** Une barre par sous-période, la moustache
étant l'intervalle à 95 % construit sur l'erreur type de Lo. Vérifier que chaque moustache traverse
zéro avant de commenter la hauteur d'une barre.

## Les coûts

### La rotation

Source : `results/tables/costs.csv`. Rotation en convention de somme entière sur les positions
nettes, coût de dix points de base par unité de rotation.

| Version | Rotation/an | Brut %/an | Net %/an | Sharpe net | Coût qui annule |
|---|---:|---:|---:|---:|---:|
| Déciles, rangs, capitalisation | 3,46 | 1,337 | 0,992 | 0,090 | **38,5 pb** |
| Titres, rangs, réglage de l'article | 2,20 | -0,015 | -0,235 | -0,016 | 29,9 pb |
| Titres, rangs, sans rétrécissement | 2,80 | **7,430** | **7,151** | **0,380** | **309,4 pb** |

**Comment lire ce tableau, en trois constats.** Un, la rotation est faible, entre 2,2 et 3,5 fois par
an, parce que le bêta ex ante bouge lentement : la stratégie n'est pas fragile aux frais. Deux, la
version sans rétrécissement supporte 309 points de base par unité de rotation avant de rendre zéro,
soit trente et une fois les dix points de base retenus. Trois, la version au réglage de l'article ne
supporte que 29,9 points de base, non parce qu'elle coûte plus cher, mais parce que son rendement
brut est déjà nul.

Le multiple de coût survécu de la série de référence vaut **3,876** (`results/metrics.json`, clé
`multiple_de_couts_survecu`), donc elle passe le seuil de 2,0 du verdict. Ce nombre ne figure pas
dans `results/tables/cost_multiples.csv` : ce tableau porte les six multiples testés, et 3,876 est
l'abscisse où la droite qui joint 2,0 et 5,0 croise zéro. Le tableau donne les deux bornes de cette
droite, 0,058 à deux fois dix points de base et -0,035 à cinq fois.

`results/figures/cost_sensitivity.png`. **Mode d'emploi.** L'axe horizontal porte le multiple appliqué
aux dix points de base, l'axe vertical le ratio de Sharpe net, et la ligne horizontale marque zéro.
Chercher l'abscisse où la courbe croise zéro, ici entre deux et cinq.

### Le prix du levier annule l'alpha à 23 points de base, une fois la rotation payée

C'est ce que l'article ne modélise pas, et son hypothèse de levier au taux sans risque est exactement
celle que sa propre théorie conteste. Source : `results/tables/financing_breakeven.csv`. La base
« nette » facture l'écart sur le capital emprunté net, la jambe longue moins le produit de la vente à
découvert. La base « brute » suppose que ce produit ne rapporte rien.

Attention à ne pas confondre deux emplois du mot « net ». La colonne « Base » nomme la base de
FACTURATION DU LEVIER. Les deux dernières colonnes, elles, nomment la base de COÛT DE ROTATION de
l'alpha : brut de frais de rotation, ou net des dix points de base facturés partout ailleurs dans
l'étude.

| Série | Base | Emprunté moyen | Alpha brut de rotation, %/mois | Écart qui l'annule | Alpha net de rotation, %/mois | Écart qui l'annule |
|---|---|---:|---:|---:|---:|---:|
| Déciles, rangs | nette | 0,399 | 0,036 | 110 pb | **0,0075** | **23 pb** |
| Déciles, rangs | brute | 1,188 | 0,036 | 37 pb | **0,0075** | **8 pb** |
| Titres, sans rétrécissement | nette | 1,296 | 0,315 | 289 pb | 0,292 | **267 pb** |
| Titres, sans rétrécissement | brute | 1,975 | 0,315 | 190 pb | 0,292 | **176 pb** |

**Comment lire ce tableau, en trois constats.** Un, la base de coût décide de tout pour la série de
référence. Son alpha à quatre facteurs vaut 0,036 % par mois sans frais de rotation et 0,0075 % une
fois payés les dix points de base. L'écart qui l'annule passe donc de 110 à 23 points de base. Deux,
le même changement de base ne coûte que 21 points de base à la version sans rétrécissement, 289
contre 267, parce que son alpha part cinq fois plus haut. Trois, la série de référence n'a donc pas
d'alpha à défendre : 23 points de base d'écart de financement, et 8 en base brute, sont moins que ce
que paie n'importe quel emprunteur.

L'écart qui annule le RENDEMENT, et non l'alpha, tient bien mieux, parce qu'il ne retranche pas les
quatre facteurs. Il vaut 335 points de base en base nette et 113 en base brute, brut de rotation
(`breakeven_spread_bps`), contre 249 et 84 net de rotation (`breakeven_spread_net_bps`).

Le calcul est exact et non interpolé. Le coût entre linéairement dans le rendement, donc l'alpha est
une fonction affine de l'écart, et deux points suffisent à résoudre le point d'annulation.

`results/figures/financing_heatmap.png`. **Mode d'emploi.** Une colonne par écart de financement, une
ligne par couple de série et de base de facturation, une couleur par ratio de Sharpe net. Comparer
les deux lignes d'une même série pour voir ce que coûte l'hypothèse sur le produit du découvert.

## Le hors échantillon

### La série de référence ne rapporte rien après l'article

La série qui porte le verdict est notre reconstruction sur les déciles triés par bêta. Elle est
pondérée par les rangs, ses rendements de décile sont pondérés par la capitalisation, elle emploie le
rétrécissement de l'article, et elle est nette de dix points de base. Sur l'échantillon `OOS` d'avril 2012 à juin 2026, 171 mois, son ratio de
Sharpe vaut **-0,002** (`results/metrics.json`, clé `sharpe_hors_echantillon_net`).

Le rééchantillonnage par blocs de douze mois, 2 000 tirages, graine 20260902, place le rendement
annualisé hors échantillon à **0,05 %**. Son intervalle va de -6,04 % à +5,89 %, et 51,5 % des
tirages sont positifs (`results/tables/bootstrap.csv`). Autrement dit, la série est indiscernable de
zéro dans les deux sens.

### Le processus de sélection, lui, aurait fonctionné

C'est le résultat le plus inattendu de l'étude, et il ne va pas dans le sens du verdict. Source :
`results/tables/cpcv_distribution.csv` et `results/tables/cpcv_paths.csv`.

| Contrôle | Valeur mesurée | Fichier |
|---|---:|---|
| Nombre d'essais comptés | 144 | `trials.csv` |
| Probabilité de surapprentissage | **0,000** | `metrics.json` |
| Sharpe moyen des 7 chemins de validation croisée | **0,631** | `cpcv_distribution.csv` |
| Sharpe minimal des 7 chemins | 0,572 | `cpcv_paths.csv` |
| Part de chemins négatifs | 0,000 | `cpcv_distribution.csv` |
| Ratio de Sharpe dégonflé | 1,2e-24, arrondi à 0,000 | `deflated_sharpe.csv` |
| t exigé par Bonferroni sur 144 essais | 3,58 | `deflated_sharpe.csv` |
| t observé hors échantillon | -0,007 | `deflated_sharpe.csv` |

**Comment lire ce tableau, en trois constats.** Un, la validation croisée combinatoire purgée juge
ici le PROCESSUS de sélection. Sur chaque bloc d'apprentissage, la meilleure des vingt-quatre
configurations de la jambe B1 est retenue, puis évaluée sur le bloc de test suivant. Deux, les sept
chemins ainsi reconstruits sont tous positifs et serrés, de 0,572 à 0,655, donc choisir la meilleure
configuration sur le passé aurait toujours donné un résultat positif ensuite. Trois, ce constat ne
sauve pas la configuration de l'article, il dit seulement que ce n'est pas elle que le passé aurait
désignée.

**L'objection la plus forte contre ce constat.** Les vingt-quatre configurations diffèrent surtout
par le poids de rétrécissement, et ce poids a un effet quasi monotone et stable dans le temps. Une
sélection sur le passé retrouve donc toujours le même gagnant, ce qui rend l'exercice moins exigeant
qu'il n'y paraît. Le ratio de Sharpe dégonflé, lui, reste à 1,2e-24 parce qu'il porte sur la série de
référence, dont le ratio hors échantillon est négatif.

### La correction pour tests multiples ne laisse passer que trois configurations

Source : `results/tables/multiple_testing.csv`, correction de Holm sur les vingt-quatre statistiques t
de la jambe B1.

| Dans le décile | Entre les déciles | Rétrécissement | Sharpe | t | Valeur p ajustée | Rejeté à 5 % |
|---|---|---:|---:|---:|---:|---|
| Équipondérée | Rangs | 1,0 | **0,639** | 3,43 | 0,0146 | **oui** |
| Équipondérée | Équipondérée | 1,0 | 0,624 | 3,34 | 0,0191 | **oui** |
| Équipondérée | Capitalisation | 1,0 | 0,593 | 3,20 | 0,0297 | **oui** |
| Équipondérée | Rangs | 0,8 | 0,469 | 2,68 | 0,1557 | non |
| Capitalisation | Rangs | 1,0 | 0,286 | 2,05 | 0,7201 | non |
| Capitalisation | Rangs | 0,6, celle de l'article | 0,121 | 0,91 | 1,0000 | non |

**Comment lire ce tableau, en trois constats.** Un, trois configurations sur vingt-quatre survivent à
la correction, et les trois emploient l'équipondération DANS le décile sans aucun rétrécissement.
Deux, la configuration exacte de l'article rend une valeur p ajustée de 1,000, donc elle ne dit rien.
Trois, la pondération entre les déciles ne sépare pas les trois survivantes de leurs voisines, ce qui
confirme une fois de plus que ce n'est pas l'axe qui compte.

`results/figures/rolling_sharpe.png` et `results/figures/underwater_bab.png`. **Mode d'emploi.** La
première trace le ratio de Sharpe de la série de référence sur fenêtre glissante de 120 mois.
Chercher si la courbe passe durablement au-dessus de zéro plutôt que de commenter un pic. La seconde montre la
distance au sommet précédent, en points de pourcentage, et sert à juger la durée d'un repli autant que
sa profondeur.

`results/figures/equity_bab.png`. **Mode d'emploi.** L'axe vertical est une échelle logarithmique en
dollars des États-Unis, base 1 dollar au départ de chaque courbe, la courbe des titres ne commençant
qu'en janvier 2001. Comparer les pentes plutôt que les niveaux, les trois séries ne partant pas de la
même date. Attention à un piège de lecture : le premier point tracé porte DÉJÀ le rendement du
premier mois, il ne vaut donc pas 1,00. La courbe des titres part à 0,70 parce que janvier 2001 lui
coûte 30,5 %, et non parce qu'elle aurait perdu de l'argent avant de commencer.

`results/figures/correlation_heatmap.png`. **Mode d'emploi.** Corrélations de Pearson sur les mois
communs aux cinq séries, soit janvier 2001 à juin 2026, la série des titres bornant l'échantillon.
Regarder d'abord la colonne du marché, qui dit ce qu'il reste d'exposition dans chaque version. La
case des déciles y vaut -0,29 sur ces mois communs, contre -0,259 sur les 720 mois du verdict.

`results/figures/return_histogram.png`. **Mode d'emploi.** Distribution mensuelle du facteur publié
par AQR, colonne des États-Unis, avec la loi normale de même moyenne et de même écart type. Regarder
les queues plutôt que le sommet : elles portent l'asymétrie de -0,67 et l'aplatissement excédentaire
de 7,02 mesurés sur l'échantillon COMPLET du classeur, celui que trace la figure
(`results/tables/legA_windows.csv`, première ligne).

## Les limites

**Notre univers de titres est celui d'aujourd'hui.** Les 503 membres du S&P 500 relevés le 2026-09-02
excluent les sociétés disparues. Le sens du biais n'est pas connu a priori : il flatte la jambe longue
si les faillites frappent surtout les titres à bêta élevé, et l'inverse sinon. Statut : **déclaré non
mesuré**.

**Les portefeuilles triés par bêta ne sont publiés qu'en mensuel.** La recette exacte de l'article,
qui demande des rendements quotidiens, n'est donc applicable que sur l'univers biaisé. Les deux jambes
ne se recouvrent pas parfaitement, et leur accord sur le rôle du rétrécissement est ce qui donne
confiance dans le résultat.

**Le coût d'emprunt de titre de la jambe courte n'est pas modélisé.** Seule la rotation est facturée.
La jambe courte porte 0,78 dollar par dollar investi, et ces titres seraient chers à emprunter s'ils
étaient petits, ce qui n'est pas le cas ici puisque les déciles sont agrégés.

**Le coût de transaction de dix points de base est une hypothèse.** Novy-Marx et Velikov mesurent
60 points de base par mois de rendement sur 1968-2017 au niveau du titre, ce qui n'est pas la même
unité que la nôtre. Le multiple de coût est balayé jusqu'à dix fois, et la conclusion ne bascule
qu'entre deux et cinq.

**Le seuil de 0,15 sur le bêta réalisé a été fixé après un prototype.** Le prototype du 2026-09-02
rendait déjà -0,18, donc le seuil est écrit en sachant qu'il échouerait. Il est conservé tel quel, et
le contrôle échoue, ce que `notes.md` déclare.

**Le compte de 144 essais couvre les évaluations de performance.** Les quatre fenêtres de la jambe A
et les vingt-quatre marchés portent la série publiée et non une stratégie candidate, mais ils sont
comptés quand même. Porter le compte de 144 à 300 laisse le ratio dégonflé indiscernable de zéro et le seuil de
Bonferroni à 3,76 contre un t observé de -0,007, donc aucun critère ne bascule.

**Le désaccord avec Novy-Marx et Velikov sur la dispersion des bêtas n'est pas résolu.** Ils mesurent
que la volatilité de marché explique 58 % de la dispersion transversale, nous mesurons 0,3 % avec une
valeur p de 0,376. Deux différences de protocole sont déclarées, l'univers et la période, et aucune
n'a été isolée.

**Les régressions emploient des erreurs types ordinaires**, comme l'article. Une correction de
Newey-West est disponible dans `factor_regression` par l'argument `cov_type` et n'a pas été retenue
pour rester comparable aux tableaux publiés.

**Aucun résultat ne porte sur l'avenir.** Tous les chiffres sont mesurés sur des périodes nommées.

## Le verdict

**`REJECTED`**, déduit par `quantlab.reporting.study.decide_verdict` depuis les seuils écrits dans
`config.yaml` avant que les résultats existent. Voici les critères, avec la valeur mesurée en face du
seuil.

| Critère | Mesuré | Seuil | Résultat |
|---|---:|---:|---|
| Signe économique attendu | rendement en échantillon positif | positif | RÉUSSI |
| Signe du Sharpe hors échantillon | **-0,002** | rejet à 0 ou moins | **ÉCHOUÉ** |
| Réplication, 9 contrôles chiffrés | **8 sur 9** dans la tolérance | tous exigés | **ÉCHOUÉ** |
| Sharpe hors échantillon | -0,002 | minimum 0,50 | ÉCHOUÉ |
| t après correction pour essais multiples | -0,007 | minimum 3,00 | ÉCHOUÉ |
| Ratio de Sharpe dégonflé | 0,000 | minimum 0,95 | ÉCHOUÉ |
| Probabilité de surapprentissage | 0,000 | maximum 0,50 | RÉUSSI |
| Part de sous-périodes positives | 0,667 | minimum 0,60 | RÉUSSI |
| Multiple de coûts survécu | 3,876 | minimum 2,00 | RÉUSSI |
| Corrélation absolue avec le portefeuille détenu | 0,259, soit -0,259 signée | maximum 0,60 | RÉUSSI |

**Comment lire ce tableau, en trois constats.** Un, le verdict est `REJECTED` parce que l'échelle du
laboratoire fait du signe du ratio de Sharpe hors échantillon un critère de rejet, qui précède tous
les autres, et ce ratio vaut -0,002. Deux, la décision se joue donc au troisième décimal, ce que le
rééchantillonnage confirme : 51,5 % des tirages sont positifs. Trois, huit contrôles de réplication
sur neuf passent, donc le rejet ne porte pas sur notre fidélité à l'article mais sur ce que sa recette
rapporte à qui la suit.

Le neuvième contrôle est le plus parlant. Source : `results/tables/replication_checks.csv`.

| Grandeur | Publié | Nous | Écart relatif | Verdict |
|---|---:|---:|---:|---|
| Rendement excédentaire mensuel, % | 0,700 | 0,676 | 0,034 | répliqué |
| Statistique t du rendement excédentaire | 7,120 | 6,343 | 0,109 | répliqué |
| Volatilité annualisée, % | 10,700 | 11,538 | 0,078 | répliqué |
| Ratio de Sharpe annualisé | 0,780 | 0,703 | 0,098 | répliqué |
| Alpha à trois facteurs, %/mois | 0,730 | 0,741 | 0,015 | répliqué |
| Alpha à quatre facteurs, %/mois | 0,550 | 0,541 | 0,016 | répliqué |
| Part de marchés au Sharpe positif | 0,947 | 1,000 | 0,056 | répliqué |
| Levier de la jambe longue, dollars | 1,400 | 1,367 | 0,024 | répliqué |
| Bêta réalisé de notre facteur | 0,000 | **-0,182** | tolérance absolue 0,15 | **écart** |

**Comment lire ce tableau, en trois constats.** Un, les huit contrôles portant sur la série publiée
passent tous, et sept d'entre eux à moins de 10 % d'écart relatif. Deux, le neuvième porte sur NOTRE
construction et il échoue : le bêta ex ante vaut zéro par identité, mais le bêta réalisé vaut -0,182
là où l'article annonce -0,06. Trois, ce même contrôle passerait à +0,081 sans le rétrécissement,
donc l'échec nomme précisément le pas de la recette qui ne se transporte pas.

**Ce que l'étude établit, en trois phrases.** Le facteur que publie AQR se réplique sur huit
grandeurs et ne s'affaiblit pas après l'article, l'écart de ratio de Sharpe entre avant et après
avril 2012 valant 0,015 pour une valeur p de 0,960. La recette décrite dans l'article, appliquée à
deux univers publics, ne rend un facteur neutre au marché que si l'on retire son rétrécissement de
0,6. Ce rétrécissement fait passer le bêta réalisé de +0,08 à -0,18 sur les déciles, et de +0,07 à
-0,40 sur les titres. Le prix du levier, que l'article suppose nul, annule l'alpha de la série de
référence à 23 points de base d'écart de financement, une fois payés ses dix points de base de
rotation.

**La prochaine décision.** Les trois seules configurations qui survivent à la correction de Holm
emploient l'équipondération à l'intérieur des déciles, donc elles chargent les petites
capitalisations. C'est exactement ce que Novy-Marx et Velikov reprochent au facteur, et le mesurer au
niveau du titre demande une base sans biais de survie. La prochaine étape est donc l'accès à un
univers CRSP complet, faute de quoi ce point restera mesuré à l'échelle des déciles seulement.

## Reproduire

```bash
export QUANTLAB_USER_AGENT="votre nom votre courriel"
uv run python studies/005_betting_against_beta/run.py
uv run pytest tests/unit/test_strategies_betting_against_beta.py -o addopts="" -q
```

L'exécution télécharge un classeur d'AQR et quatre fichiers de la bibliothèque de Kenneth French,
puis met ces archives en cache dans la couche `raw` du lac. Elle télécharge ensuite les prix
quotidiens de 503 titres et les écrit dans la couche `bronze`. Elle réécrit enfin `results/`. La première exécution prend
plusieurs minutes à cause du téléchargement, les suivantes environ une minute.

Deux exécutions consécutives rendent des tableaux identiques au fichier près, seul l'identifiant
d'expérience changeant. La vérification a été faite le 2026-09-02 par comparaison des répertoires :
les vingt-neuf fichiers CSV sont revenus octet pour octet.

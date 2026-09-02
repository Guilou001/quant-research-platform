# Momentum de série temporelle

**La question, en une phrase : le momentum de série temporelle survit-il à sa propre
publication ?**

**La réponse : non, pas au sens où l'article l'entendait.** Le facteur construit par les
auteurs eux-mêmes passe d'un ratio de Sharpe de 1,411 sur 1985-2009 à 0,337 après juin
2012. Cette chute n'est pas un accident d'échantillonnage : la statistique z de l'écart
vaut 3,24 pour une valeur p de 0,0012. Le mécanisme, lui, n'a pas disparu. Notre
reconstruction indépendante sur vingt-huit fonds négociés en bourse suit le facteur des
auteurs avec une corrélation de 0,760 et un bêta de 0,983, sans alpha. Ce qui reste est
un signal de Sharpe brut 0,377 sur 2007-2026. Quatre points de base de coûts par unité
de rotation le ramènent à 0,217, et le compte de 73 essais le réduit à un ratio de
Sharpe dégonflé de 0,301.

Tous les chiffres de cette fiche viennent de `results/`, et chaque tableau dit de quel
fichier. Ils se régénèrent par :

```bash
export QUANTLAB_USER_AGENT="prénom nom courriel"
uv run python studies/001_time_series_momentum/run.py
```

## La question de recherche

Le rendement passé d'un instrument prédit-il son propre rendement futur, sans aucune
comparaison avec les autres instruments ? Moskowitz, Ooi et Pedersen (2012) répondent
oui, sur 58 contrats à terme de quatre classes d'actifs, de 1965 à 2009.

La question de cette étude est la suivante. Quatorze années après la publication,
qu'est-il resté de ce résultat, et qu'est-ce qui, dans ce qui reste, tient à un
mécanisme économique plutôt qu'à la façon dont l'article a été mesuré ?

## L'article

Moskowitz, T. J., Ooi, Y. H. et Pedersen, L. H. (2012). Time series momentum. *Journal
of Financial Economics*, 104(2), 228-250.
[doi:10.1016/j.jfineco.2011.11.003](https://doi.org/10.1016/j.jfineco.2011.11.003)

La fiche complète du laboratoire est
[`docs/literature/moskowitz_ooi_pedersen_2012.md`](../../docs/literature/moskowitz_ooi_pedersen_2012.md).
Elle porte les 64 cellules du tableau 2, les régressions du tableau 3, les critiques
publiées et les problèmes de réplication connus.

Trois critiques comptent pour la lecture des résultats ci-dessous. Huang, Li, Wang et
Zhou (2020), dans la même revue et sur le jeu de données des auteurs, montrent que 47
des 55 actifs ont un t inférieur à 1,65 pris isolément. Kim, Tse et Wald (2016)
attribuent l'essentiel du gain à la normalisation par la volatilité et non à une
prévisibilité. Goyal et Jegadeesh (2018) l'attribuent à la position longue nette que
porte toute stratégie de série temporelle.

## L'intuition économique

Deux mécanismes sont invoqués, et ils ne prédisent pas la même chose.

Le premier est comportemental. Le prix sous-réagit d'abord à une information nouvelle,
puis surréagit avec retard quand les suiveurs de tendance entrent à leur tour. La
signature de ce mécanisme est le renversement : ce qui a été poussé trop loin revient
en arrière, et l'article le mesure au-delà de douze mois.

Le second est une contrainte institutionnelle, la pression de couverture. Un producteur
de matières premières est structurellement vendeur de contrats à terme pour fixer son
prix de vente. Quelqu'un doit prendre l'autre côté, et ce quelqu'un demande à être
payé.

Ces deux mécanismes prédisent des choses différentes après publication. Un biais
comportemental s'arbitre une fois qu'il est connu, donc il doit s'affaiblir. Une prime
payée pour fournir de la liquidité ne disparaît que si la contrainte disparaît. La
section « Le hors échantillon » revient sur ce qui est mesuré.

## La définition mathématique

**La volatilité ex ante**, qui gouverne tout le dimensionnement :

\[ \sigma_t^2 = 261 \sum_{i=0}^{\infty} (1-\delta)\,\delta^{\,i}\,\left(r_{t-1-i} - \bar{r}_t\right)^2 \]

Le facteur d'annualisation est 261 et non 252. Les poids \((1-\delta)\delta^i\) somment
à un, et \(\bar{r}_t\) est la moyenne pondérée des mêmes poids. Le paramètre
\(\delta\) n'est jamais imprimé dans l'article, qui publie seulement la condition sur le
centre de masse, \(\delta/(1-\delta) = 60\) jours. Il vaut donc 60/61, soit environ
0,983607 : statut **modélisé**, calculé depuis la condition publiée.

**Le rendement d'un instrument**, l'équation à recopier exactement :

\[ r^{\text{TSMOM},s}_{t,t+1} = \operatorname{sign}\left(r^s_{t-12,t}\right) \frac{40\,\%}{\sigma^s_t}\, r^s_{t,t+1} \]

L'indice de \(\sigma\) est bien \(t\) alors que le rendement porte sur \(t\) à \(t+1\).
La volatilité est celle connue à la date de décision. Écrire \(\sigma^s_{t+1}\) par
symétrie introduirait une fuite d'information.

**Le portefeuille diversifié**, sur les \(S_t\) instruments disponibles à la date t :

\[ r^{\text{TSMOM}}_{t,t+1} = \frac{1}{S_t} \sum_{s=1}^{S_t} \operatorname{sign}\left(r^s_{t-12,t}\right) \frac{40\,\%}{\sigma^s_t}\, r^s_{t,t+1} \]

La volatilité cible de 40 % multiplie tous les rendements par une constante. Elle ne
change donc pas le ratio de Sharpe, et c'est elle qui produit les 12 % de volatilité
annualisée que l'article annonce pour le portefeuille diversifié.

## Les données

**Trois sources, toutes gratuites, toutes téléchargées par script.**

| Source | Ce qu'elle donne | Période obtenue | Statut |
|---|---|---|---|
| AQR, *Time Series Momentum Factors, Monthly* | le facteur des auteurs et ses quatre jambes de classe d'actif | 1985-01 à 2026-05, 497 mois | mesuré |
| Kenneth French | marché, taille, valeur, momentum et taux sans risque, quotidiens et mensuels | 1926-07 à 2026-06 | mesuré |
| Yahoo Finance | prix ajustés quotidiens de 28 fonds négociés en bourse | 1993-01 à 2026-06 | mesuré |

**La contrainte qui décide du plan de l'étude.** L'article travaille sur 58 contrats à
terme de 1965 à 2009. Nous n'avons pas de contrats à terme. Mesuré sur nos 28 fonds, le
dernier de l'univers, HYG, ne cote qu'à partir du 2007-04-11, et il faut ensuite douze
mois de rendements pour former un signal. Une réplication en échantillon est donc
**impossible**, et le prétendre serait malhonnête.

Le tableau `results/tables/jambe_b_profondeur_univers.csv` donne, pour chacun des 28
fonds, la date de son premier prix et la date de sa première estimation de volatilité.
Les six premières séries de l'échantillon commencent en 1993 et 1996 ; la dernière
volatilité utilisable arrive en 2008.

**L'univers, et sa déclaration.** Dix fonds d'actions : SPY, QQQ, IWM, EFA, EEM, EWJ,
EWG, EWU, EWA, EWC. Sept d'obligations : TLT, IEF, SHY, LQD, HYG, TIP, AGG. Cinq de
matières premières : GLD, SLV, USO, DBC, DBA. Six de devises : FXE, FXY, FXB, FXA,
FXF, UUP. Ce sont des **substituts déclarés** des contrats à terme, et non des
équivalents. Un fonds coté ne porte ni le rendement de portage d'une courbe de contrats,
ni le coût de renouvellement, ni la marge. Il porte en revanche des frais de gestion,
que le contrat n'a pas.

## La méthodologie originale

Trois étages, du plus général au plus précis.

**Premier étage, les régressions groupées.** Le rendement mensuel de chaque instrument
est régressé sur son propre rendement retardé de h mois, les deux divisés par la
volatilité ex ante. Les retards vont de 1 à 60 mois.

**Deuxième étage, la grille de stratégies.** Pour chaque instrument et chaque mois, la
position est longue si le rendement excédentaire des k derniers mois est positif, et
elle est tenue h mois. Les valeurs de k et de h sont 1, 3, 6, 9, 12, 24, 36 et 48 mois,
soit 64 cellules. Les observations ne se chevauchent pas : une unique série mensuelle
est construite, dont le rendement du mois t est la moyenne des rendements de tous les
portefeuilles encore actifs.

**Troisième étage, le facteur.** Une seule cellule est retenue pour l'analyse détaillée,
k égale 12 et h égale 1. Chaque position porte 40 % de volatilité annualisée ex ante, et
le portefeuille est la moyenne équipondérée des instruments disponibles.

## Notre implémentation

Le module [`quantlab.strategies.time_series_momentum`](../../src/quantlab/strategies/time_series_momentum.py)
porte les quatre équations et rien d'autre. Aucune métrique de performance n'y vit : le
ratio de Sharpe vient de `quantlab.analytics.ratios`, le rendement du portefeuille de
`quantlab.backtest.engine.run_backtest`, et le signe du rendement cumulé de
`quantlab.features.transforms.time_series_momentum_signal`.

**Les six conventions tranchées, toutes déclarées.**

Un, la somme infinie de la volatilité est tronquée à l'échantillon et ses poids sont
renormalisés.

Deux, l'indice \(t-1-i\) de l'équation est pris au pied de la lettre. La volatilité
datée du jour t n'utilise aucun rendement du jour t. Un test le vérifie en changeant le
rendement du dernier jour et en constatant que l'estimation ne bouge pas.

Trois, la volatilité retenue à la date de décision mensuelle est celle du dernier jour
de bourse du mois.

Quatre, un instrument dont la volatilité ou le signal manque est absent du portefeuille,
et le diviseur \(S_t\) ne le compte pas.

Cinq, pour une détention de h mois, la position agrégée est la moyenne des positions des
cohortes actives, chacune gardant le signe ET la volatilité de sa date de formation.

Six, la division par \(S_t\) intervient après la moyenne des cohortes.

**Le décalage d'exécution vaut un mois**, sans exception. Les poids décidés à la fin du
mois t sont détenus pendant le mois t+1. Le moteur refuse un décalage nul sans
autorisation explicite.

**Les rendements sont excédentaires**, ceux des fonds comme ceux du facteur d'AQR. Le
taux sans risque de Kenneth French est retranché au niveau quotidien pour la volatilité
et au niveau mensuel pour les rendements. La position à levier est ainsi financée au
taux sans risque par construction, et l'écart de financement facturé par un courtier
est ajouté séparément.

**Le plan en trois jambes.** Chacune répond à une question différente, et les trois sont
nécessaires parce qu'aucune ne suffit.

| Jambe | Ce qu'elle mesure | Risque d'implémentation |
|---|---|---|
| A | ce que devient le facteur publié par les auteurs après leur échantillon | aucun, la série est la leur |
| B | ce que notre reconstruction indépendante produit sur des fonds cotés | entier, et c'est pourquoi elle est validée contre A |
| C | si le profil de la grille 8 sur 8 se retrouve | entier, hérité de B |

## Nos écarts avec l'article

Huit écarts, et chacun est une décision, pas un oubli.

**Un, l'univers.** Vingt-huit fonds négociés en bourse contre 58 contrats à terme.
L'article travaille sur des contrats liquides, sans frais de gestion, avec une marge de
5 à 20 %. Nos fonds portent des frais et n'ont pas de courbe de contrats.

**Deux, la période.** 2007-01 à 2026-06 contre 1985-2009. Le chevauchement avec
l'échantillon de l'article ne fait que 36 mois, et la fenêtre principale de cette étude
est postérieure à la publication.

**Trois, les repères de la grille.** L'article régresse sur MSCI World, l'indice
obligataire Barclays, le S&P GSCI, SMB, HML et UMD. Nous employons le marché américain
de Kenneth French, SMB, HML, MOM, plus le fonds AGG comme repère obligataire et le fonds
DBC comme repère de matières premières. Les deux derniers sont dans notre univers, ce
qui est aussi le cas des repères de l'article.

**Quatre, la duration obligataire.** L'article normalise la duration de ses contrats
obligataires. Un fonds coté ne se normalise pas : sa duration est celle de son
portefeuille. L'écart est déclaré, et non corrigé.

**Cinq, les coûts.** L'article n'en charge aucun, et le mot n'apparaît dans son texte
que dans une citation de la littérature. Nous en chargeons, donc les chiffres nets ne
sont pas comparables aux siens. Les chiffres bruts le sont.

**Six, la source du facteur de la jambe A.** AQR publie deux jeux, celui de l'article
d'origine sur 1985-2009 et la version prolongée. Le fournisseur du laboratoire ne
connaît que la seconde, et c'est elle qui est employée. Les deux ne portent pas le même
univers d'instruments au fil du temps.

**Sept, les régressions groupées du premier étage.** Elles ne sont pas reproduites.
L'objection de Huang, Li, Wang et Zhou (2020) porte précisément sur l'inférence de ces
régressions. Reproduire une statistique dont les valeurs critiques sont contestées
n'apprendrait rien de plus que ce que la jambe B mesure directement.

**Huit, l'univers est composé de survivants, et il est choisi en 2026.** Les 28 fonds
cotent tous aujourd'hui. Un fonds lancé en 2006 et fermé en 2015 ne pouvait pas entrer
dans cette liste, alors qu'un investisseur de 2007 aurait pu le détenir. L'article ne
rencontre pas ce problème : un contrat à terme sur le maïs ne ferme pas. Le biais est
donc dans le sens qui FLATTE notre reconstruction, et son ampleur n'est pas chiffrée,
faute d'une liste datée des fonds radiés : **non trouvé**. Ce qui le borne est la nature
de l'univers, fait de fonds indiciels larges dont aucun n'a été radié depuis 2007, et non
de fonds thématiques.

## Les résultats

### Jambe A, le facteur des auteurs perd les deux tiers de son ratio de Sharpe

Source : `results/tables/jambe_a_fenetres.csv` et
`results/tables/jambe_a_test_de_difference.csv`. Univers : les 58 instruments des
auteurs. Base : **brute** de tous frais, comme dans l'article. Fréquence mensuelle.

| Fenêtre | Échantillon | Mois | Rendement/an | Volatilité | Sharpe | Erreur type de Lo | IC à 95 % | Pire repli |
|---|---|---:|---:|---:|---:|---:|---|---:|
| 1985-01 à 2009-12 | `IS` | 300 | 17,39 % | 11,93 % | **1,411** | 0,193 | [1,034 ; 1,789] | -15,15 % |
| 2010-01 à 2026-05 | `OOS` | 197 | 4,50 % | 13,06 % | 0,402 | 0,237 | [-0,062 ; 0,867] | -27,91 % |
| 2012-06 à 2026-05 | `FINAL_HOLDOUT` | 168 | 3,60 % | 13,02 % | **0,337** | 0,270 | [-0,193 ; 0,866] | -27,91 % |

Comment lire ce tableau, en trois constats. **Un**, le ratio de Sharpe est divisé par
plus de quatre, et l'intervalle de confiance de la fenêtre postérieure à la publication
contient zéro. **Deux**, la volatilité, elle, ne bouge presque pas, de 11,93 % à
13,02 %, ce qui montre que la perte vient du numérateur et non du dénominateur.
**Trois**, le pire repli passe de 15,15 % à 27,91 % : la stratégie n'est pas seulement
moins rémunératrice, elle est plus douloureuse.

**L'écart est-il distinguable du hasard ?** Oui. Les deux fenêtres ne se recouvrent pas,
donc les deux estimateurs sont indépendants et la variance de leur écart est la somme
des variances.

| Grandeur | Valeur |
|---|---:|
| Écart des ratios de Sharpe | 1,0747 |
| Erreur type de Lo, 1985-2009 | 0,1925 |
| Erreur type de Lo, après publication | 0,2702 |
| Erreur type de l'écart | 0,3318 |
| Statistique z | **3,239** |
| Valeur p bilatérale | **0,0012** |

Comment lire ce tableau, en trois constats. **Un**, la statistique z de 3,24 franchit
même le seuil de 3,0 que Harvey, Liu et Zhu (2016) recommandent après correction pour
essais multiples. **Deux**, l'erreur type de Lo, robuste à l'autocorrélation, est ici
plus petite que l'erreur type i.i.d. sur la première fenêtre et plus grande sur la
seconde, ce qui a été vérifié dans le fichier source. **Trois**, le test suppose la
normalité asymptotique des deux estimateurs, hypothèse d'autant plus acceptable que les
deux fenêtres comptent respectivement 300 et 168 mois.

**Par classe d'actif.** Source : `results/tables/jambe_a_classes_actifs.csv`.

| Classe | Sharpe 1985-2009 | Sharpe après publication | z | p |
|---|---:|---:|---:|---:|
| Matières premières | 1,012 | 0,171 | 2,587 | 0,010 |
| Actions | 0,830 | 0,156 | 1,854 | 0,064 |
| Taux | 0,705 | 0,291 | 1,197 | 0,231 |
| Devises | 0,784 | 0,189 | 1,856 | 0,063 |

Comment lire ce tableau, en trois constats. **Un**, les quatre classes baissent, sans
exception, ce qui écarte l'explication par un accident propre à un marché. **Deux**,
une seule baisse est significative à 5 % prise isolément, celle des matières premières,
et deux autres le sont à 10 %. **Trois**, la classe qui résiste le mieux est celle des
taux, dont la baisse n'est pas distinguable du hasard, avec une valeur p de 0,231.

**L'attribution factorielle.** Source : `results/tables/jambe_a_attribution.csv`.
Régression du facteur sur le marché américain, SMB, HML et MOM de Kenneth French, avec
erreurs types de Newey et West.

| Fenêtre | Mois | Alpha/an | Alpha/mois | t de l'alpha | R² | Bêta MOM | t de MOM |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1985-2009 | 300 | 14,68 % | 1,223 % | **6,438** | 0,144 | 0,264 | 6,04 |
| 2010-2026 | 197 | 3,58 % | 0,298 % | 1,222 | 0,251 | 0,513 | 7,58 |
| après publication | 168 | 3,59 % | 0,299 % | **1,090** | 0,259 | 0,480 | 6,82 |

Comment lire ce tableau, en trois constats. **Un**, l'alpha mensuel de 1,223 % sur
1985-2009 est du même ordre que le 1,58 % publié, sans le retrouver à 10 % près.
L'écart relatif vaut 0,226, donc le contrôle de réplication échoue. **Deux**, après
publication, l'alpha n'est plus distinguable de zéro, avec un t de 1,09. **Trois**, la
charge sur le momentum transversal **double**, de 0,264 à 0,480, et le R² passe de 0,144
à 0,259. Ce qui reste du facteur ressemble donc de plus en plus à du momentum d'actions
déjà connu.

**Le pire repli, et sa durée.** Source : `results/tables/jambe_a_dix_pires_replis.csv`.
Le repli de 27,91 % commence le 2016-03-31, touche son creux le 2021-11-30 et n'est
effacé que le 2022-09-30. Il dure **78 mois**, dont 69 de descente. Il commence près de
quatre ans après la publication.

### Jambe B, notre reconstruction reproduit le facteur sans lui ajouter d'alpha

Source : `results/tables/jambe_b_performance.csv`. Univers : 28 fonds négociés en
bourse. Coûts : 1 point de base de commission, 2 de demi-écart, 1 de glissement, plus
50 points de base par an de financement au-delà d'une exposition brute de un. Statut de
ces quatre hypothèses : **modélisé**, aucune n'est mesurée sur des exécutions réelles.

| Fenêtre | Échantillon | Mois | Base | Rendement/an | Volatilité | Sharpe | Pire repli |
|---|---|---:|---|---:|---:|---:|---:|
| 2007-01 à 2009-12 | `IS` | 36 | brute | 5,07 % | 15,71 % | 0,391 | -20,51 % |
| 2007-01 à 2009-12 | `IS` | 36 | nette | 3,15 % | 15,71 % | 0,274 | -20,82 % |
| 2007-01 à 2012-05 | `OOS` | 65 | brute | 6,23 % | 17,38 % | 0,434 | -25,98 % |
| 2007-01 à 2012-05 | `OOS` | 65 | nette | 4,18 % | 17,38 % | 0,321 | -27,21 % |
| 2012-06 à 2026-06 | `FINAL_HOLDOUT` | 169 | brute | 4,71 % | 17,20 % | 0,354 | -31,71 % |
| 2012-06 à 2026-06 | `FINAL_HOLDOUT` | 169 | nette | 1,55 % | 17,17 % | **0,176** | -35,86 % |
| 2007-01 à 2026-06 | `OOS` | 234 | brute | 5,13 % | 17,22 % | 0,377 | -31,71 % |
| 2007-01 à 2026-06 | `OOS` | 234 | nette | 2,27 % | 17,20 % | **0,217** | -35,86 % |

Comment lire ce tableau, en trois constats. **Un**, le ratio de Sharpe brut de notre
reconstruction sur la fenêtre postérieure à la publication, 0,354, encadre celui du
facteur des auteurs sur la même période, 0,337. **Deux**, les coûts retirent 0,160 point
de Sharpe, soit 42 % du brut, et cette part est le vrai sujet de la section « Les
coûts ». **Trois**, la volatilité de 17,22 % dépasse de 43 % les 12 % de l'article, ce qui
vient de nos 28 instruments, moins nombreux et moins diversifiés que ses 58.

**La validation contre le facteur des auteurs**, qui est le contrôle décisif de cette
jambe. Source : `results/tables/jambe_b_validation_contre_aqr.csv`. Régression de notre
série brute sur le facteur d'AQR, 233 mois communs de 2007-01 à 2026-05.

| Grandeur | Valeur |
|---|---:|
| Corrélation | **0,760** |
| Bêta | **0,983** |
| t du bêta | 13,945 |
| Alpha annualisé | +0,89 % |
| t de l'alpha | 0,393 |
| R² | 0,578 |

Comment lire ce tableau, en trois constats. **Un**, un bêta de 0,983 avec un t de 13,9
signifie que notre série se comporte comme une unité du facteur des auteurs. Cela
atteste la méthodologie plus sûrement que n'importe quelle comparaison de moyennes.
**Deux**, l'alpha de 0,89 % par an avec un t de 0,39 dit que nous n'ajoutons rien, ce
qui est exactement le résultat souhaité pour une réplication. **Trois**, le R² de 0,578
laisse 42 % de variance inexpliquée, et c'est l'écart d'univers : 28 fonds cotés contre
58 contrats à terme.

**Chaque instrument, pris seul.** Source :
`results/tables/jambe_b_instruments_isoles.csv`. L'article annonce que les 58 contrats
affichent un ratio de Sharpe positif et que 52 sont significatifs à 5 %.

| Grandeur | Article | Nous |
|---|---:|---:|
| Part d'instruments à Sharpe positif | 100 % (58 sur 58) | **82,1 %** (23 sur 28) |
| Instruments significatifs à 5 % | 52 sur 58, soit 89,7 % | **4 sur 28**, soit 14,3 % |

Comment lire ce tableau, en trois constats. **Un**, cinq instruments ont un Sharpe
négatif chez nous : EWA, TIP, FXB, FXF et UUP. **Deux**, quatre seulement dépassent 1,96
en valeur absolue, SHY à 3,29, QQQ à 3,11, SPY à 2,34 et FXY à 2,28. **Trois**, ce
résultat va dans le sens de Huang, Li, Wang et Zhou (2020), qui trouvent 47 actifs sur
55 sous le seuil de 1,65 avec les données mêmes des auteurs.

**Où va le levier.** Source : `results/tables/jambe_b_expositions_par_instrument.csv`.
L'exposition brute moyenne du portefeuille vaut **5,06 fois** le capital, avec un
maximum de 9,12. Le fonds SHY, dont la volatilité ex ante médiane est de 1,09 %, porte à
lui seul un poids absolu moyen de 1,44, soit 28,6 % de l'exposition brute. C'est la
conséquence mécanique de la cible de 40 % appliquée sans plafond. L'article ne rencontre
pas ce problème, un contrat à terme sur bon du Trésor à deux ans se finançant à la
marge.

### Jambe C, le profil de la grille se retrouve, son niveau ne se retrouve pas

Source : `results/tables/jambe_c_grille_t_de_l_alpha.csv`,
`results/tables/jambe_c_grille_sharpe.csv` et `results/tables/jambe_c_profil.csv`.
Formation en ligne, détention en colonne, en mois. Statistique t de la constante d'une
régression à six facteurs. Échantillon `OOS`, base **brute**, 234 mois de 2007-01 à
2026-06, univers des 28 fonds. Coûts : aucun, la base étant brute.

| Formation \ Détention | 1 | 3 | 6 | 9 | 12 | 24 | 36 | 48 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0,93 | 1,38 | 1,57 | 1,54 | 1,18 | 0,26 | -0,53 | 0,00 |
| 3 | 2,31 | 1,28 | 1,50 | 0,96 | 0,57 | -0,19 | -1,31 | -0,58 |
| 6 | **2,50** | 1,51 | 1,35 | 0,48 | 0,13 | -1,03 | -1,81 | -0,76 |
| 9 | 2,23 | 1,16 | 0,29 | -0,06 | -0,08 | -1,47 | -1,84 | -0,92 |
| 12 | 1,39 | 0,45 | 0,45 | 0,30 | -0,06 | -1,63 | -1,67 | -0,80 |
| 24 | 0,62 | -0,52 | -1,68 | -2,16 | -2,37 | -2,24 | -1,89 | -1,61 |
| 36 | -0,62 | -0,88 | -1,25 | -1,35 | -1,34 | -1,20 | -1,18 | -1,20 |
| 48 | 0,52 | -0,30 | -0,70 | -0,89 | -0,90 | -1,02 | -1,26 | -1,00 |

Comment lire ce tableau, en trois constats. **Un**, le quart supérieur gauche, celui des
formations de 1 à 12 mois et des détentions courtes, est positif partout sauf une
cellule, exactement comme dans l'article. **Deux**, le renversement au-delà de 24 mois
de formation apparaît bien, et il est le plus marqué sur la ligne 24, dont six cellules
sur huit sont sous -1,6. **Trois**, aucune cellule n'atteint le seuil usuel de 1,96 sauf
trois, et le maximum vaut 2,50 contre 6,61 dans l'article. La cellule (1, 48) porte un t
dont la valeur absolue reste sous huit millièmes sur les trois exécutions mesurées, et
dont le signe change de l'une à l'autre. La section « La reproductibilité » chiffre ce
que la source déplace, ici et sur le reste de la grille.

**La comparaison de profil, chiffrée.**

| Grandeur | Article, 1985-2009 | Nous, 2007-2026 |
|---|---:|---:|
| Cellules à t positif | 62 sur 64 | **25 ou 26 sur 64** |
| Cellules à Sharpe positif | non publié | 60 sur 64 |
| t maximal | 6,61 en (12, 1) | **2,50** en (6, 1) |
| Sharpe médian, formations 1 à 12 mois | non publié | **0,347** |
| Sharpe médian, formations 24 à 48 mois | non publié | **0,214** |
| Corrélation de rang de Spearman avec la grille publiée | | **0,799** |

Comment lire ce tableau, en trois constats. **Un**, la corrélation de rang de 0,799
entre les 64 cellules publiées et les nôtres dit que la FORME de la grille se retrouve.
Le nombre de cellules positives dit, lui, que le NIVEAU ne se retrouve pas. **Deux**,
la cellule la plus forte se déplace de (12, 1) à (6, 1), déplacement d'une seule case
sur une grille dont les valeurs voisines sont proches. **Trois**, le Sharpe médian des
formations courtes dépasse celui des formations longues de 0,133, ce qui est le sens
prédit, mais l'écart est petit devant l'erreur type d'un Sharpe sur 234 mois, environ
0,20.

**Le compte des essais.** Une grille de 8 sur 8 vaut 64 essais. Ajoutés aux huit
variantes de robustesse et à l'essai manuel déclaré dans `notes.md`, cela fait **73
essais**, et ce nombre entre tel quel dans le ratio de Sharpe dégonflé.

## La robustesse

**Le plateau, plutôt que le pic.** Source : `results/tables/robustesse_plateau.csv` et
`results/tables/robustesse_meilleur_plateau.csv`. Échantillon `OOS`, base **brute**, 234
mois de 2007-01 à 2026-06, univers des 28 fonds. Le meilleur plateau de la grille est la
cellule (6, 3), dont le ratio de Sharpe vaut **0,4087** et le score de plateau 0,4081.
Son isolement, l'écart entre sa propre valeur et la médiane de son voisinage complet de
neuf cellules, vaut 0,0006. Une cellule isolée aurait un isolement élevé ; celle-ci est
au centre d'une zone plate, donc son résultat ne tient pas à un réglage. Le score et
l'isolement sont eux-mêmes instables, de 0,4052 à 0,4081 et de 0,0006 à 0,0035 sur trois
exécutions. La médiane d'un voisinage y bascule entre deux cellules presque égales. Le
Sharpe de la cellule, lui, ne bouge pas au quatrième chiffre.

**Les variantes de construction.** Source : `results/tables/robustesse_variantes.csv`.
Échantillon `OOS`, 234 mois de 2007-01 à 2026-06, univers des 28 fonds. Les colonnes
brute et nette portent la base de coût ; les hypothèses de coût sont celles de la jambe
B, statut **modélisé**.

| Variante | Sharpe brut | Sharpe net | Rotation/an | Exposition brute |
|---|---:|---:|---:|---:|
| Centre de masse 20 jours | 0,360 | 0,182 | 12,09 | 5,50 |
| Centre de masse 40 jours | 0,370 | 0,204 | 10,05 | 5,22 |
| Centre de masse 60 jours, l'article | 0,377 | 0,217 | 9,15 | 5,06 |
| Centre de masse 90 jours | 0,379 | 0,224 | 8,40 | 4,90 |
| Centre de masse 120 jours | 0,375 | 0,225 | 7,96 | 4,78 |
| Position plafonnée à 3 fois | 0,346 | **0,270** | 4,22 | 2,47 |
| Position plafonnée à 5 fois | 0,358 | 0,260 | 5,65 | 3,20 |
| Sans normalisation par la volatilité | **0,159** | 0,142 | 1,61 | 1,00 |

Comment lire ce tableau, en trois constats. **Un**, le centre de masse de la volatilité
ne décide de rien : le Sharpe brut varie de 0,360 à 0,379 sur un facteur six du
paramètre. **Deux**, plafonner la position à trois fois **améliore** le Sharpe net, de
0,217 à 0,270, parce que la rotation tombe de 9,15 à 4,22. Le choix de l'article, qui ne
plafonne rien, coûte donc de l'argent dès qu'on facture les transactions. **Trois**,
retirer la normalisation par la volatilité fait tomber le Sharpe brut de 0,377 à 0,159,
soit une division par 2,4. Le résultat va dans le sens de Kim, Tse et Wald (2016) : une
part majeure du gain vient de l'allocation à risque égal et non d'une prévisibilité.

**La marche en avant.** Source : `results/tables/walk_forward.csv`. Fenêtre
d'entraînement ancrée de 72 mois au minimum, bloc de test de 12 mois, purge de 12 mois
et embargo d'un mois. À chaque pli, la cellule de grille au meilleur Sharpe
d'entraînement est retenue, puis mesurée sur le bloc de test.

| Grandeur | Valeur |
|---|---:|
| Nombre de plis | 13 |
| Cellule retenue le plus souvent | (6, 1), dans 12 plis sur 13 |
| Sharpe de la série assemblée, brute | **0,379** |
| Sharpe de la cellule (12, 1) sur les mêmes blocs | **0,360** |

Comment lire ce tableau, en trois constats. **Un**, la sélection est stable, la même
cellule sortant douze fois sur treize. **Deux**, elle n'apporte presque rien : 0,379
contre 0,360 pour la cellule que l'article avait fixée d'avance, soit 0,019 point de
Sharpe pour treize sélections. **Trois**, cinq des treize blocs de test sont négatifs, y
compris les trois derniers, 2023, 2024 et 2025.

**La validation croisée combinatoire purgée.** Source : `results/tables/cpcv_chemins.csv`
et `results/tables/cpcv_configurations_retenues.csv`. Huit plis, deux plis en test par
combinaison, purge de 12 mois, embargo d'un mois, ce qui donne 28 combinaisons et sept
chemins. À chaque segment, la cellule est **choisie** sur les plis d'entraînement purgés
puis mesurée sur le pli de test, sans quoi les sept chemins rendraient sept fois le même
nombre.

| Grandeur | Valeur |
|---|---:|
| Chemins | 7 |
| Sharpe médian, brut | **0,162 à 0,166** |
| Sharpe moyen | 0,098 à 0,101 |
| Écart type entre chemins | 0,123 à 0,128 |
| Sharpe minimal | -0,071 à -0,091 |
| Part de chemins négatifs | **28,6 %** |

Ces quatre grandeurs portent une fourchette parce qu'elles basculent sur des
quasi-égalités : « La reproductibilité » explique pourquoi, et `results/` porte la valeur
de la dernière exécution.

Comment lire ce tableau, en trois constats. **Un**, le Sharpe médian d'environ 0,164
obtenu en choisissant la cellule sur les seuls plis d'entraînement est nettement sous les
0,377 de la cellule fixée d'avance sur l'échantillon entier. **Deux**, deux chemins sur sept sont
négatifs, ce qui donne la fréquence à laquelle une sélection honnête aurait perdu de
l'argent. **Trois**, la configuration retenue varie beaucoup selon le segment, dix des
56 sélections tombant sur (12, 48) et seize sur (6, 1).

**La probabilité de surapprentissage.** Source : `results/tables/pbo_logits.csv`. La
validation croisée combinatoirement symétrique sur les 64 séries de la grille rend une
probabilité de **0,814**. Au-delà de 0,5, la configuration retenue en échantillon fait
pire hors échantillon que la médiane du tirage au sort. Le seuil déclaré avant les
résultats était 0,5, et il est franchi de loin.

**Les essais multiples.** Source : `results/tables/essais_multiples.csv`.

| Grandeur | Valeur |
|---|---:|
| Essais comptés | **73** |
| Variance des ratios de Sharpe mensuels des essais | 0,00142 |
| Sharpe mensuel de la fenêtre postérieure à la publication, net | 0,0507 |
| Ratio de Sharpe dégonflé | **0,301** |
| t observé | 0,659 |
| t exigé, Bonferroni à 5 % sur 73 essais | **3,396** |
| Valeur p corrigée par la méthode de Holm | 1,000 |
| Ratio de Sharpe rasé | 0,000 |

Comment lire ce tableau, en trois constats. **Un**, le ratio de Sharpe dégonflé de 0,301
est très en dessous du seuil de publication de 0,95 retenu par Bailey et López de Prado
(2014). **Deux**, la correction de Holm sur 73 essais porte la valeur p à 1,000 et rase
la totalité du ratio de Sharpe. **Trois**, ces deux résultats disent la même chose de
deux façons : un Sharpe net de 0,176 sur 169 mois ne survit à aucune correction pour
essais multiples, quelle qu'elle soit.

**Les sous-périodes.** Source : `results/tables/sous_periodes.csv`, série nette.

| Sous-période | Mois | Rendement/an | Sharpe | Pire repli |
|---|---:|---:|---:|---:|
| 2007-01 à 2009-12 | 36 | 3,15 % | 0,274 | -20,82 % |
| 2010-01 à 2012-12 | 36 | 2,01 % | 0,198 | -21,99 % |
| 2013-01 à 2015-12 | 36 | 8,34 % | 0,568 | -22,29 % |
| 2016-01 à 2018-12 | 36 | -5,24 % | **-0,270** | -22,64 % |
| 2019-01 à 2021-12 | 36 | 3,60 % | 0,284 | -12,77 % |
| 2022-01 à 2026-06 | 54 | 2,26 % | 0,212 | **-35,86 %** |

Comment lire ce tableau, en trois constats. **Un**, cinq des six sous-périodes sont
positives, soit 83,3 %, ce qui franchit le seuil de 60 % déclaré avant les résultats.
**Deux**, la seule sous-période négative, 2016 à 2018, est aussi celle où le facteur des
auteurs entamait son repli de 78 mois. **Trois**, la dernière sous-période porte le pire
repli de toute l'étude, 35,86 %, pour un rendement annuel de 2,26 % seulement.

**L'attribution factorielle de notre reconstruction.** Source :
`results/tables/attribution_facteurs.csv`. Six facteurs, 234 mois.

| Série | Alpha/an | t de l'alpha | R² | Bêta MOM | t de MOM | Bêta marché |
|---|---:|---:|---:|---:|---:|---:|
| brute | 4,86 % | 1,392 | 0,170 | 0,456 | **4,939** | 0,086 |
| nette | 2,13 % | 0,603 | 0,168 | 0,453 | 4,849 | 0,083 |

Comment lire ce tableau, en trois constats. **Un**, l'alpha brut de 4,86 % par an n'est
pas significatif, avec un t de 1,39, et l'alpha net l'est encore moins. **Deux**, la
seule charge significative est celle du momentum transversal, à 0,456 avec un t de 4,94,
ce qui reproduit le résultat de l'article sur son propre échantillon. **Trois**, le bêta
de marché de 0,086 avec un t de 0,95 confirme que la stratégie n'est pas une exposition
actions déguisée.

**Le risque de queue.** Source : `results/tables/risque_de_queue.csv`, valeurs à
horizon mensuel.

| Série | Asymétrie | Aplatissement excédentaire | VaR historique à 5 % | Perte attendue à 5 % | Pire mois |
|---|---:|---:|---:|---:|---:|
| Notre reconstruction, brute | -0,100 | 0,555 | 7,90 % | 10,94 % | -14,35 % |
| Notre reconstruction, nette | -0,096 | 0,558 | 8,19 % | 11,15 % | -14,44 % |
| Facteur d'AQR | **+0,197** | 0,486 | 5,63 % | 7,19 % | -11,47 % |

Comment lire ce tableau, en trois constats. **Un**, le facteur des auteurs a une
asymétrie POSITIVE, ce qui est la signature du stellage que décrit l'article, alors que
notre reconstruction a une asymétrie légèrement négative. **Deux**, notre perte attendue
à 5 % dépasse de 55 % celle du facteur, 11,15 % contre 7,19 %. **Trois**, l'aplatissement excédentaire reste modeste dans les
deux cas, autour de 0,5, donc les queues ne sont pas le principal problème de cette
stratégie.

### La reproductibilité, mesurée sur trois exécutions

**Treize des 38 métriques sont identiques au dernier chiffre sur trois exécutions
successives, et l'écart relatif médian des vingt-cinq autres vaut 1,0e-5.** La cause
n'est pas dans le code : elle est dans la source.

Mesuré le 2026-09-02, deux téléchargements du même univers, sur les mêmes dates,
rendent 8 411 lignes et 28 colonnes identiques en forme. Mais **115 150 cellules sur
235 508 diffèrent**, de 1,8e-4 au plus sur des prix de l'ordre de cent. Les écarts sont
des puissances de deux : le fournisseur quantifie ses prix ajustés en simple précision,
et l'arrondi change d'une requête à l'autre. La comparaison de deux appels dans le MÊME
processus rend zéro écart, donc le bruit vient bien de la requête.

| Grandeur | Trois exécutions |
|---|---|
| Métriques identiques au dernier chiffre | 13 sur 38 |
| Écart relatif médian des autres | 1,0e-5 à 1,7e-5 |
| Métriques dont l'écart relatif dépasse 1 % | 4 |

Les quatre exceptions sont toutes des basculements de signe ou d'`argmax` sur une
quasi-égalité. Le compte de cellules de grille à t positif vaut 25 ou 26, parce que la
cellule (1, 48) porte un t de quelques millièmes. Les trois autres sont l'écart type, le
minimum et la médiane de la validation croisée, dont la sélection de configuration bascule
sur des segments où deux cellules sont à égalité. Leurs fourchettes mesurées valent 0,123
à 0,128 pour l'écart type, -0,071 à -0,091 pour le minimum, et 0,162 à 0,166 pour la
médiane.

**Le mécanisme n'est pas un arrondi, c'est un signe.** Le signal est le signe d'un
rendement cumulé. Quand ce cumul frôle zéro, un écart de prix de 2e-6 renverse une
position entière pour un instrument et un mois. La grille en porte la trace : entre deux
exécutions, 13 des 64 statistiques t changent à la deuxième décimale et 16 à la
troisième, l'écart le plus grand valant 0,021. Les formations courtes sont les plus
touchées, parce qu'un cumul sur un mois passe par zéro plus souvent qu'un cumul sur
douze.

**Conséquence pratique, et la restriction qu'elle impose.** Les métriques publiées dans
`metrics.json` sont reproductibles à trois décimales, sauf les quatre nommées ci-dessus.
Les 64 cellules de la grille et les deux scores de plateau, eux, ne le sont qu'à la
première décimale : ils sont donnés ici tels que la dernière exécution les rend, et la
lecture porte sur leur profil, jamais sur leur dernier chiffre. Le laboratoire ne fige
pas la source : un instantané commité rendrait l'étude reproductible et non régénérable,
ce qui est le contraire du but.

## Les coûts

**Le coût annuel mesuré vaut 2,76 % de la valeur liquidative.** Source :
`results/tables/couts_composantes.csv`. Il retire 0,16 point de ratio de Sharpe, soit
42 % du brut. Ce n'est pas un détail de comptabilité : c'est le premier facteur qui
décide si la stratégie est exécutable.

**Le seuil de rentabilité vaut 70,94 points de base** par unité de rotation. Source :
`metrics.json`, clé `cout_de_seuil_de_rentabilite_bps`. Autrement dit, il faudrait payer
près de dix-huit fois nos 4 points de base supposés pour que le rendement brut soit
entièrement mangé. Le chiffre paraît confortable, et la section suivante montre
pourquoi il ne l'est pas.

**La sensibilité au multiple des coûts.** Source :
`results/tables/couts_multiplicateur.csv`. Chaque multiple s'applique à la fois aux
frais de transaction et à l'écart de financement.

| Multiple des coûts supposés | Sharpe net | Survit |
|---:|---:|---|
| 0,25 | 0,337 | oui |
| 0,50 | 0,297 | oui |
| 1,00 | 0,217 | oui |
| 2,00 | 0,056 | oui |
| **2,35** | 0,000 | seuil interpolé |
| 3,00 | -0,105 | non |
| 5,00 | -0,426 | non |
| 10,00 | -1,221 | non |

Comment lire ce tableau, en trois constats. **Un**, le multiple survécu vaut 2,35, donc
la stratégie passe le seuil de 2,0 déclaré avant les résultats, mais de peu. **Deux**,
l'écart entre le seuil de rentabilité de 70,94 points de base et ce multiple de 2,35
vient du financement. Ce dernier se paie sur une exposition brute de 5,06 même quand
rien ne s'échange. **Trois**, à trois fois les coûts supposés, soit 12 points de base
par unité de rotation et 150 points de base de financement, la stratégie perd de
l'argent.

**Ce que le plafond de position change.** Plafonner chaque position à trois fois le
capital ramène la rotation annuelle de 9,15 à 4,22 et l'exposition brute de 5,06 à 2,47.
Le Sharpe brut baisse de 0,377 à 0,346, et le Sharpe **net monte** de 0,217 à 0,270.
C'est le seul réglage de toute l'étude qui améliore la performance nette, et il n'est
pas dans l'article.

## Le hors échantillon

**Tout, dans cette étude, est hors échantillon, et c'est la contrainte de départ.**
L'échantillon de l'article s'arrête en 2009 et notre univers ne devient complet qu'en
2008. Le chevauchement fait 36 mois sur 234, soit 15 %.

**Trois découpages, et ce que chacun mesure.**

| Découpage | Fenêtre | Ce qu'il mesure |
|---|---|---|
| `IS` | 2007-01 à 2009-12 | le chevauchement avec l'échantillon de l'article, 36 mois |
| `OOS` | 2010-01 à 2012-05 | après l'échantillon, avant la publication |
| `FINAL_HOLDOUT` | 2012-06 à 2026-06 | après la publication dans le *Journal of Financial Economics* |

**Aucun paramètre n'a été choisi sur le holdout final**, et son compte de lectures est
publié plutôt que minimisé. Chaque exécution de `run.py` mesure le holdout, donc il a été
lu autant de fois que l'étude a tourné, une douzaine de fois pendant le développement.
Ce qui protège le résultat n'est pas le nombre de lectures, c'est que rien ne s'y
ajuste. Les paramètres de la cellule principale, formation de douze mois et détention
d'un mois, viennent de l'article. Les seuils du verdict sont écrits dans `config.yaml`
avant le premier téléchargement. La grille de 64 cellules est publiée en entier plutôt
que filtrée sur sa meilleure case. L'unique essai où une décision a changé après lecture, la
date de fin ramenée au 2026-06-30, est déclaré dans `notes.md` et compté comme essai.

**Le résultat, mis côte à côte.**

Source : `results/tables/jambe_a_fenetres.csv` et
`results/tables/jambe_b_performance.csv`.

| Série | Avant publication | Après publication | Écart |
|---|---:|---:|---:|
| Facteur d'AQR, brut | 1,411 sur 1985-2009 | 0,337 | -1,075 |
| Notre reconstruction, brute | 0,434 sur 2007 à mai 2012 | 0,354 | -0,080 |
| Notre reconstruction, nette | 0,321 sur 2007 à mai 2012 | 0,176 | -0,146 |

Comment lire ce tableau, en trois constats. **Un**, la chute du facteur des auteurs est
treize fois plus grande que celle de notre reconstruction, mais elle part de beaucoup
plus haut et couvre 25 années contre cinq. **Deux**, notre fenêtre d'avant publication
ne fait que 65 mois, donc son erreur type de Sharpe vaut 0,423 et l'écart de 0,080 n'est
pas interprétable. **Trois**, la seule comparaison qui porte est celle du facteur des
auteurs, parce qu'elle repose sur 300 mois contre 168 et sur une série sans risque
d'implémentation.

## Les limites

**Un, l'univers n'est pas celui de l'article, et il ne peut pas l'être.** Vingt-huit
fonds cotés ne sont pas 58 contrats à terme. Le portage, le renouvellement de contrat et
la marge sont absents de nos données, et les frais de gestion des fonds sont présents
dans les leurs. L'écart est déclaré, non corrigé, et non chiffré : **non trouvé**, faute
d'une série de rendements de contrats à terme gratuite.

**Deux, le levier de la construction n'est pas exécutable tel quel.** Une exposition
brute moyenne de 5,06 fois le capital, avec un maximum de 9,12, suppose un courtier qui
prête à 50 points de base au-dessus du taux sans risque sur des fonds obligataires. La
variante plafonnée à trois fois, publiée plus haut, montre ce que le plafond change.

**Trois, les hypothèses de coût sont modélisées et non mesurées.** Quatre points de base
par unité de rotation est un ordre de grandeur pour un panier de fonds dont les plus
étroits s'échangent sous le point de base et les plus larges autour de cinq. Aucune
exécution réelle n'a été observée.

**Quatre, la jambe A repose sur la série prolongée d'AQR et non sur celle de l'article
d'origine.** AQR publie les deux, et le fournisseur du laboratoire ne connaît que la
première. L'écart entre les deux jeux n'a pas été mesuré : **non trouvé**.

**Cinq, deux contrôles de réplication échouent pour une raison identifiée et non
corrigée.** L'alpha mensuel de 1,223 % et son t de 6,438 sont mesurés contre le marché
américain de Kenneth French, quand l'article emploie MSCI World, l'indice obligataire
Barclays et le S&P GSCI. Deux de ces trois repères n'existent pas dans une source
gratuite avant 2003 : **non trouvé**.

**Six, le t de Student de la grille n'est pas comparable case par case à celui de
l'article.** Les fenêtres diffèrent, 234 mois contre 300, et les repères de régression
diffèrent. C'est pourquoi la comparaison porte sur le PROFIL, mesuré par une corrélation
de rang, et non sur les valeurs.

**Sept, le test de différence des deux ratios de Sharpe suppose la normalité
asymptotique** des deux estimateurs et l'indépendance des deux fenêtres. La seconde
hypothèse tient par construction, les fenêtres ne se recouvrant pas. La première repose
sur 300 et 168 observations, et l'asymétrie mesurée des deux séries reste sous 0,21 en
valeur absolue.

**Huit, les régressions groupées du premier étage de l'article ne sont pas
reproduites**, ce qui est une décision et non un oubli. Elle est justifiée dans « Nos
écarts avec l'article ».

**Neuf, la source de prix n'est pas stable au bit près d'une requête à l'autre.** La
section « La reproductibilité » chiffre ce que cela déplace. Quatre métriques sur 38
portent une fourchette au lieu d'une valeur, et elles sont nommées. Les 64 cellules de la
grille ne sont, elles, reproductibles qu'à la première décimale.

**Dix, le ratio de Sharpe dégonflé mélange deux bases et deux fenêtres.** Le Sharpe
observé est celui de la série NETTE sur les 169 mois postérieurs à la publication. La
variance entre essais qui le dégonfle est mesurée, elle, sur les Sharpe BRUTS des 72
essais et sur les 234 mois entiers. C'est le choix le plus défavorable disponible, une
variance entre essais mesurée sur la fenêtre longue étant plus grande que sur le seul
holdout, mais ce n'est pas une grandeur homogène. Le verdict n'en dépend pas : à 64
essais le ratio dégonflé vaut 0,309, à 73 il vaut 0,301, et il faudrait 145 essais pour
descendre à 0,262, toutes valeurs très loin du seuil de 0,95. Statut **modélisé**.

**Onze, l'univers ne compte que des survivants**, ce que « Nos écarts avec l'article »
détaille en huitième point. Le biais joue en faveur de notre reconstruction et n'est pas
chiffré : **non trouvé**.

## Le verdict

**`EXPERIMENTAL`.** Le verdict n'est pas choisi : il est déduit par
`quantlab.reporting.study.decide_verdict` depuis les seuils écrits dans `config.yaml`
avant que les résultats existent. Les dix-sept lignes de raisons sont dans
`results/tables/verdict_raisons.csv`, et les voici en entier, sans la ligne de synthèse ni celle du verdict.

| Critère | Mesuré | Seuil | État |
|---|---:|---:|---|
| Hypothèse économique, signe attendu | retrouvé | le signe décide du rejet | RÉUSSI |
| Signe du Sharpe hors échantillon | 0,176 | rejet à 0 ou moins | RÉUSSI |
| Réplication, volatilité du facteur 1985-2009 | 0,119 contre 0,120 | écart relatif 0,006 | RÉUSSI |
| Réplication, charge sur le momentum transversal | 0,264 contre 0,280 | écart relatif 0,056 | RÉUSSI |
| Réplication, alpha mensuel 1985-2009 | 0,0122 contre 0,0158 | écart relatif 0,226 | ÉCHOUÉ |
| Réplication, t de l'alpha mensuel | 6,438 contre 7,990 | écart relatif 0,194 | ÉCHOUÉ |
| Réplication, part d'instruments à Sharpe positif | 0,821 contre 1,000 | écart relatif 0,179 | ÉCHOUÉ |
| Réplication, cellules de grille à t positif | 25 ou 26 contre 62 | écart relatif 0,58 à 0,60 | ÉCHOUÉ |
| Sharpe hors échantillon | 0,176 | minimum 0,500 | ÉCHOUÉ |
| t après correction pour essais multiples | 0,659 | minimum 3,000 | ÉCHOUÉ |
| Ratio de Sharpe dégonflé | 0,301 | minimum 0,950 | ÉCHOUÉ |
| Probabilité de surapprentissage | 0,814 | maximum 0,500 | ÉCHOUÉ |
| Part de sous-périodes positives | 0,833 | minimum 0,600 | RÉUSSI |
| Multiple de coûts survécu | 2,349 | minimum 2,000 | RÉUSSI |
| Corrélation absolue au portefeuille existant | 0,096 | maximum 0,600 | RÉUSSI |

Comment lire ce tableau, en trois constats. **Un**, l'étude n'est pas rejetée : le signe
économique attendu est retrouvé et le Sharpe hors échantillon reste positif. **Deux**,
elle ne monte pas au niveau `REPLICATED` : quatre contrôles de réplication sur six
sortent de la tolérance de 10 % déclarée d'avance. Les raisons sont identifiées, et
écrites dans « Les limites ». **Trois**, même si tous les contrôles de réplication
passaient, quatre des six critères de robustesse échoueraient, et le plus lourd est la
probabilité de surapprentissage de 0,814.

**La réponse à la question de tête, en trois phrases.** Le momentum de série temporelle
ne survit pas à sa propre publication au sens de l'article, puisque le facteur de ses
auteurs perd 1,07 point de ratio de Sharpe avec une valeur p de 0,0012. Il survit en
tant que phénomène : notre reconstruction indépendante le retrouve avec un bêta de 0,983
et une corrélation de 0,760. Le profil de sa grille se retrouve aussi, à une corrélation
de rang de 0,799. Ce qui survit ne suffit pas à investir : un Sharpe net de
0,176 sur 169 mois, un ratio de Sharpe dégonflé de 0,301 sur 73 essais, et une
probabilité de surapprentissage de 0,814.

**Ce que l'étude ne dit pas, et l'objection la plus forte contre elle.** L'objection est
que notre reconstruction pourrait échouer parce qu'elle est mauvaise, et non parce que
le phénomène a faibli. Elle est traitée, et c'est la raison d'être de la jambe A. Le
facteur mesuré dans cette jambe est celui des auteurs, construit par eux, sur leur
univers de 58 contrats. Sa chute de 1,411 à 0,337 ne doit rien à notre code.

## Les fichiers

| Fichier | Contenu |
|---|---|
| `config.yaml` | tous les paramètres, les grilles d'essais et les seuils du verdict |
| `run.py` | l'enchaînement complet, déterministe, graine 20260902 |
| `notes.md` | le journal de l'étude, les essais ratés et les surprises |
| `results/metrics.json` | les 38 métriques publiées, le verdict et ses raisons |
| `results/tables/` | 34 tableaux, un par contrôle |
| `results/figures/` | 11 figures, en PNG et en PDF vectoriel |

**Les figures, et leur mode d'emploi.**

`richesse_facteur_aqr` montre la richesse cumulée du facteur des auteurs de 1985 à 2026,
en échelle logarithmique. Regarder la pente, et non le niveau : elle est constante
jusque vers 2015 et plate ensuite.

`richesse_reconstruction` superpose notre série brute, notre série nette et le facteur
d'AQR sur la seule fenêtre commune, en échelle ordinaire. Regarder l'écart croissant
entre la courbe brute et la courbe nette : c'est le coût, année après année.

`repli_facteur_aqr` trace le repli du facteur depuis son sommet. Regarder la longueur du
creux de 2016 à 2022, et non sa profondeur : soixante-dix-huit mois.

`sharpe_glissant_aqr` donne le ratio de Sharpe du facteur sur soixante mois glissants.
Regarder le moment où la courbe passe durablement sous un, vers 2010.

`grille_t_mesuree` et `grille_t_publiee` sont la même grille, la nôtre et celle de
l'article. Les regarder l'une après l'autre : la géographie des couleurs se ressemble,
l'échelle des couleurs ne se ressemble pas.

`sensibilite_aux_couts` trace le Sharpe net contre le multiple des coûts supposés.
Regarder où la courbe croise zéro, entre 2 et 3.

`sous_periodes` donne le Sharpe net par sous-période, avec son intervalle de confiance.
Regarder la largeur des barres d'erreur : chaque sous-période fait 36 mois, donc aucune
n'est concluante seule.

`correlations` croise les quatre jambes de classe d'actif du facteur et notre
reconstruction, sur la fenêtre commune 2007 à 2026. La matrice dessinée est aussi écrite
dans `results/tables/correlations_classes_actifs.csv`. Regarder le contraste entre les
corrélations faibles des classes entre elles, de -0,03 entre actions et taux à 0,39 entre
devises et matières premières, et leurs corrélations avec notre série, de 0,44 à 0,59.

`histogramme_des_rendements` et `quantiles_contre_la_normale` décrivent la distribution
mensuelle nette. Regarder la queue gauche du second graphique : les pires mois sont plus
mauvais que ne le prévoit la loi normale.

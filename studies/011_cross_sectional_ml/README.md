# Étude 011 : un ensemble d'arbres ordonne-t-il les rendements mieux qu'une régression, après coûts ?

**Verdict : `REJECTED`.** Les arbres amplifiés, désignés modèle complexe avant
tout résultat, ne prévoient pas mieux que la régression pénalisée désignée
modèle simple : le test de Diebold et Mariano rend une statistique de -0,45,
valeur p 0,65. Leur portefeuille décile rapporte pourtant un ratio de Sharpe
net de 0,663 contre 0,277, mais ce ratio porte un t de 1,99, un Sharpe
dégonflé de 0,82 pour dix-sept essais, et il tient sur six années. Le R²
mensuel hors échantillon des six méthodes se situe entre 0,35 % et 0,48 %, la
plage que Gu, Kelly et Xiu (2020) publient, et la corrélation de rang moyenne
est NÉGATIVE pour les six : les modèles prévoient le niveau du mois, pas
l'ordre des titres.

## La question de recherche

Gu, Kelly et Xiu (2020) montrent que des méthodes non linéaires, arbres et
réseaux, doublent le pouvoir prédictif d'une régression sur les rendements
mensuels d'actions, et que ce gain se transforme en portefeuilles à ratio de
Sharpe élevé. La question de cette étude est plus étroite et plus dure : sur un
panneau point-in-time de grandes capitalisations, avec vingt-sept
caractéristiques et onze ans de données, un ensemble d'arbres bat-il une
régression pénalisée hors échantillon, une fois les coûts payés ?

## L'article

Gu, S., Kelly, B. et Xiu, D. (2020), *Empirical Asset Pricing via Machine
Learning*, Review of Financial Studies 33(5), 2223-2273. Fiche :
[docs/literature/gu_kelly_xiu_2020.md](../../docs/literature/gu_kelly_xiu_2020.md).
Les chiffres cibles sont rapportés de la table 1 du document de travail NBER.

## L'intuition économique

Le rendement attendu d'un titre est une fonction inconnue de ses
caractéristiques. Une régression suppose cette fonction linéaire et
additive ; un arbre la découpe en régions et autorise des interactions, par
exemple un momentum qui ne paie que sur les titres liquides. Si les
interactions existent, les arbres gagnent ; si le signal est faible et le bruit
énorme, la souplesse des arbres n'attrape que le bruit, et la régression, plus
rigide, résiste mieux.

## La définition mathématique

Le modèle de l'article, additivement séparable entre prime et bruit :

\[
r_{i,t+1} = g^{\star}(z_{i,t}) + \epsilon_{i,t+1}
\]

Le critère, dont le dénominateur ne centre pas, de sorte que prévoir zéro rend
zéro :

\[
R^2_{oos} = 1 - \frac{\sum_{i,t}(r_{i,t+1} - \hat r_{i,t+1})^2}{\sum_{i,t} r_{i,t+1}^2}
\]

Les caractéristiques sont rangées à chaque date dans l'intervalle de moins un
à plus un, un manquant valant zéro. Les formules vivent dans
`quantlab.models`, chacune avec ses dix points de documentation.

## Les données

| Source | Contenu | Mesure |
|---|---|---|
| Cache de l'étude 004, `data/raw/qmj_features/0ff289aa1b4e1bcb` | 21 variables comptables et de risque point-in-time, capitalisation, rendements mensuels par société | 1 526 sociétés, 133 mois de 2015-06 à 2026-06 |
| Kenneth French | taux sans risque mensuel | même fenêtre |

Six caractéristiques de prix s'ajoutent, calculées depuis les rendements
mensuels : momentum de douze mois sautant le dernier, renversement à un mois,
renversement de 36 à 13 mois, volatilité de douze mois, rendement mensuel le
plus élevé sur douze mois, logarithme de la capitalisation. Panneau final :
178 005 lignes, 173 934 étiquetées, 27 caractéristiques, 1 338 sociétés par
mois en moyenne. Source : `results/metrics.json`, clé `coverage`.

**Le biais.** L'univers de l'étude 004 survit par construction, puisqu'il
vient de la carte des symboles d'aujourd'hui, et il est filtré par la taille.
Les deux sont déclarés dans l'étude 004 et hérités ici.

## La méthodologie originale

Treize méthodes sur 30 000 titres et 60 ans, 94 caractéristiques par titre
croisées avec 8 variables macroéconomiques. Dix-huit ans d'entraînement, douze
de validation, un test glissant d'un an réajusté chaque année. Perte de Huber
pour les linéaires, cinq moyens de régularisation pour les réseaux. R² hors
échantillon sans centrage, test de Diebold et Mariano entre méthodes,
portefeuilles déciles sans coût.

## Notre implémentation

Six méthodes, treize configurations : moindres carrés, régression pénalisée en
carré, en valeur absolue, filet élastique, arbres amplifiés par gradient, forêt
aléatoire. Analyse glissante ancrée, cinq ans d'entraînement puis un an de
test, purge d'un mois, six plis de 2020-06 à 2026-05. La configuration se
choisit sur les vingt-quatre derniers mois de l'entraînement, puis le modèle
se réajuste sur tout l'entraînement. Le modèle simple à battre, la régression
pénalisée en carré, et le modèle complexe, les arbres amplifiés, sont écrits
dans `config.yaml` avant tout résultat. Le portefeuille est le décile long
moins court des prévisions, un dollar acheté et un dollar vendu, décalé d'un
mois, à 10 points de base par unité négociée.

## Nos écarts avec l'article

| Point | Article | Cette étude |
|---|---|---|
| Univers et fenêtre | tout le CRSP, 1957-2016 | 1 526 grandes capitalisations, 2015-2026 |
| Caractéristiques | 94, plus 8 macroéconomiques croisées | 27, aucune macroéconomique |
| Entraînement et validation | 18 et 12 ans | 5 ans, dont 2 de validation à la fin |
| Après validation | modèle validé conservé | réajusté sur tout l'entraînement |
| Réseaux de neurones | cinq | aucun |
| Perte des linéaires | Huber | quadratique |
| Coûts | aucun | 10 points de base, modélisé |

## Les résultats

Tous les chiffres : `results/tables/evaluation.csv`, `diebold_mariano.csv`,
`portfolios.csv`, `folds.csv`, `metrics.json`. Hors échantillon, 72 mois de
2020-07 à 2026-06, brut de frais de gestion.

| Méthode | R² mensuel hors échantillon | Corrélation de rang moyenne, t | Sharpe net du décile long moins court | Sharpe brut | Rotation annuelle |
|---|---:|---:|---:|---:|---:|
| Moindres carrés | 0,41 % | -0,022, t -1,59 | 0,277 | 0,377 | 10,1 |
| Pénalisée en carré, référence | 0,41 % | -0,022, t -1,59 | 0,277 | 0,377 | 10,1 |
| Pénalisée en valeur absolue | 0,45 % | -0,020, t -1,26 | 0,386 | 0,469 | 8,7 |
| Filet élastique | 0,44 % | -0,070, t -2,29 | 0,435 | 0,472 | 3,2 |
| Arbres amplifiés, modèle complexe | 0,35 % | -0,016, t -1,33 | **0,663** | 0,767 | 8,5 |
| Forêt aléatoire | **0,48 %** | -0,019, t -1,36 | 0,572 | 0,631 | 6,6 |

Comment lire ce tableau, en trois constats. Le premier est que le R² est dans
la plage publiée par l'article, entre 0,3 % et 0,7 %, et que la forêt est en
tête comme chez eux ; mais l'écart entre nos 0,48 % et leurs 0,63 % vaut
23 % en relatif, au-delà des 10 % que le laboratoire exige. Le deuxième est
que la corrélation de rang est négative pour les six méthodes : le R² vient
de la prévision du NIVEAU moyen du mois, que la volatilité passée porte, pas
de l'ordre des titres à l'intérieur du mois. Le troisième est que les
portefeuilles déciles gagnent quand même, les arbres à 0,663 net, parce que
les deux déciles extrêmes se comportent autrement que la masse du classement.

**Le test qui décide.** Diebold et Mariano contre la référence, sur 72 mois et
trois retards : arbres amplifiés -0,45 (p 0,65), forêt +0,35 (p 0,72),
pénalisée en valeur absolue +0,46 (p 0,65), filet +0,31 (p 0,76), moindres
carrés -2,58 (p 0,01). Aucune méthode ne prévoit mieux que la référence à
un niveau qu'on puisse distinguer du hasard, et les moindres carrés font
pire, ce qui est l'observation centrale de l'article.

**Les plis.** Le R² des arbres par bloc de test : +3,4 %, -6,8 %, +1,1 %,
+0,0 %, +0,2 %, +1,3 %. Le bloc de 2021-06 à 2022-05 est négatif pour les six
méthodes : les modèles appris de 2015 à 2021 prévoyaient la suite du
rebond de 2020, et 2022 a fait l'inverse.

**Ce qui porte les arbres.** L'importance par permutation sur le dernier
bloc de test : volatilité de douze mois 0,13 point de R², endettement 0,06,
score de solidité 0,02, rendement le plus élevé 0,01. Le modèle complexe est
d'abord un tri par la volatilité et la solidité financière, ce que les
facteurs de l'étude 004 faisaient déjà.

## La robustesse

Dix-sept essais déclarés, treize configurations et quatre multiples de coûts.
Le Sharpe dégonflé du modèle complexe vaut 0,823 pour ce compte, la
probabilité de surapprentissage entre les six portefeuilles 0,371, et les trois
sous-périodes de deux ans sont positives, ratios de 0,29, 0,70 et 1,06,
croissants. La corrélation mensuelle avec la parité de risque de l'étude 009
vaut -0,445 : ce que les arbres captent ne ressemble pas au panier de
facteurs, ce qui vaudrait quelque chose si le signal existait.

## Les coûts

À 10 points de base par unité négociée et 8,5 rotations par an, les coûts
retirent 0,10 de Sharpe aux arbres, 0,767 brut contre 0,663 net. Le décile
survit à cinq fois ce coût, 0,249, et meurt à dix fois, -0,257. Statut
modélisé ; aucun impact de marché, la phase 6 ayant montré ce qu'il ferait sur
un tel univers.

## Le hors échantillon

Tout ce qui précède est hors échantillon au sens de l'analyse glissante : les
72 mois évalués n'ont servi ni à ajuster ni à régler. Il n'y a pas de holdout
final séparé, l'historique de onze ans ne le permettant pas, et c'est écrit
plutôt que contourné.

## Les limites

| Limite | Statut |
|---|---|
| Univers de survivants filtré par la taille | reconnu, hérité de l'étude 004 |
| Onze ans de données, six plis de test | mesuré, un t de 1,99 sur 72 mois ne prouve rien |
| 27 caractéristiques contre 94, aucune macroéconomique | reconnu |
| Réajustement après validation, perte quadratique | déclaré, écart avec l'article |
| R² dominé par le niveau du mois, corrélation de rang négative | mesuré, c'est le résultat |
| Tolérance de réplication : le demi-point absolu écrit dans la configuration n'est pas la règle du laboratoire, qui applique 10 % en relatif | reconnu, la règle du laboratoire a décidé |
| Coûts proportionnels seulement | modélisé |

## Le verdict

`REJECTED`, sur quatre critères écrits avant le premier chiffre. L'hypothèse
exigeait que le modèle complexe batte le simple au test de Diebold et Mariano
et en Sharpe net ; il gagne le second et perd le premier. Le t après essais
multiples vaut 1,99 contre 3 exigés, le Sharpe dégonflé 0,82 contre 0,95, et
la réplication du R² s'écarte de 23 %. Ce que l'étude établit : sur des
grandes capitalisations et onze ans, la non-linéarité ne prévoit pas mieux que
le linéaire, et un R² de l'ordre de celui de l'article peut coexister avec un
classement des titres qui ne vaut rien.

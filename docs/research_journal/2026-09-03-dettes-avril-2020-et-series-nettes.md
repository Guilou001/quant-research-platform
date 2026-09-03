# 2026-09-03 : un mois de taux manquant, et ce que le net change au portefeuille

## Question

Deux dettes consignées la veille. La série de portage de change de l'étude 008
n'avait pas d'avril 2020, parce que le taux interbancaire américain de la FRED
manque ce mois-là. L'étude 009 et la comparaison aux fonds fermés en
héritaient. Et l'étude 009 combinait des séries BRUTES, alors que la question
d'un allocateur porte sur des séries nettes. Corriger la première et répondre à
la seconde changent-ils ce qui a été publié ?

## Hypothèse

Écrite avant de relancer. Le report d'un mois de taux déplace les chiffres de
l'étude 008 à la troisième décimale sans changer son verdict. Et sur les séries
nettes, la diversification de l'étude 009 tient encore, au moins pour la parité
hiérarchique.

## Expérience

Dans l'étude 008, un trou d'au plus un mois dans une série de taux est comblé
par le taux du mois précédent, `max_gap_fill_months: 1`, chaque report étant
publié dans `results/tables/rate_gaps_filled.csv`. Relance des études 008 et
009 et de la comparaison aux fonds fermés. Puis l'étude 012 : le script de
l'étude 009, la même référence déclarée, vingt essais, et huit séries nettes
quand une version nette existe.

## Résultat

La première moitié de l'hypothèse est vraie, la seconde est fausse.

| Mesure | Avant | Après |
|---|---:|---:|
| Étude 008, Sharpe net hors échantillon | 0,144 | 0,132 |
| Étude 008, Sharpe dégonflé | 0,149 | 0,121 |
| Étude 009, meilleure jambe seule, brut | 0,693 | 0,721 |
| Étude 009, parité de risque, net de rééquilibrage | 0,652 | 0,646 |
| Étude 009, allocations au-dessus de la meilleure jambe | 4 sur 6 | 3 sur 6 |
| Portefeuille 009 contre Wellington, corrélation annuelle | 0,79 sur 7 ans | 0,51 sur 8 ans |
| Étude 012, parité de risque sur séries nettes | | **-0,128** |
| Étude 012, meilleure jambe seule, nette | | 0,535 |

Statut : mesuré, coûts modélisés. Deux reports de taux en tout, avril 2020 et
le rendement obligataire néo-zélandais de septembre 1979. Vingt métriques de
l'étude 008 bougent à la deuxième ou troisième décimale, trente-six sur
quarante-deux de l'étude 009, et le verdict des deux est inchangé. L'année
2020 revenue est la plus mauvaise du portefeuille, -5,3 %, et elle suffit à
défaire le seul co-mouvement établi avec un grand fonds : sept points faisaient
un indice, huit le défont.

Sur les séries nettes, les corrélations n'ont pas bougé, 0,093 contre 0,095,
mais trois séries sur huit sont négatives, et l'arbitrage statistique passe du
premier apport, +0,250, au premier fardeau, -0,379. Aucune des six allocations
ne bat la meilleure jambe, et le holdout est négatif pour quatre d'entre elles.

## Décision

Les chiffres publiés des études 008 et 009 et de la comparaison aux fonds
fermés sont ceux des relances. L'étude 012 porte le verdict `REJECTED` et
devient la lecture de référence du portefeuille : ce que l'étude 009 mesurait
était une diversification réelle de paris dont la moitié perd une fois leurs
coûts payés.

## Question suivante

La dette 4 : l'étude 011 sur quarante ans de survivants, pour savoir si c'est
l'historique qui manquait aux arbres ou le signal.

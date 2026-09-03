# 2026-09-02 : à quelle taille les stratégies chiffrables cessent-elles de rapporter ?

## Question

Les huit études rendent un rendement par dollar. Un allocateur demande à
combien de dollars ce rendement tient encore. La tension est entre deux faits
vrais : le modèle d'impact en racine carrée existait depuis la phase 6 des
coûts, et rien ne le reliait au moteur, qui raisonne en poids sans capital.

## Hypothèse

Écrite dans `config.yaml` avant le premier chiffre. Les deux stratégies dont
les instruments ont un volume mesurable sont le momentum de série temporelle
sur fonds cotés et l'arbitrage statistique sur actions. Chacune garde au moins
la moitié de son ratio de Sharpe de référence à cent millions de dollars, sous
un impact au coefficient un et une exécution en une séance.

## Expérience

Un module, `quantlab.execution.capacity`, et une étude, la 010. Le module rejoue
les mêmes poids à neuf tailles de capital avec un modèle de coût qui connaît le
capital et lit les volumes à la date du moteur. Deux passages au capital unité
isolent le brut moyen, le demi-écart moyen et la charge d'impact moyenne, et la
loi en racine carrée donne le capital d'annulation en forme fermée. Le moteur
est relancé à ce capital pour vérifier que le net moyen y vaut zéro, et ce
contrôle est publié. Huit essais : deux stratégies, un cas de base, deux
coefficients, une durée d'exécution.

En parallèle, un registre de dix grands fonds fermés, `benchmarks/hedge_funds.yaml`,
avec 81 rendements annuels rapportés, leur source et leur degré de
vérification, et la comparaison annuelle du portefeuille de l'étude 009 à ces
fonds.

## Résultat

L'hypothèse est fausse pour les deux stratégies, et pour deux raisons
différentes.

| Mesure | Momentum, 28 fonds cotés | Arbitrage statistique |
|---|---:|---:|
| Ratio de Sharpe à taille nulle, demi-écart payé | 0,335 | -0,306 |
| Ratio net à 100 M$ | 0,209, écrêté sur 99 % des mois | -6,75 |
| Capital d'annulation, forme fermée | 44,0 M$ | 0 $ |
| Capital où le plafond de participation est atteint | 84 940 $ | 3,26 M$ |
| Capacité retenue | 84 940 $ | 0 $ |

Statut : modélisé. Le momentum n'est pas borné par l'impact mais par la
participation. À un million de dollars, un rééquilibrage sur quatre demande
plus de dix pour cent du volume quotidien d'un fonds de devises. La cause est
la cible de 40 % de volatilité par position, sur des fonds qui s'échangent
quelques millions par séance. L'arbitrage statistique ne couvre pas son
demi-écart de cinq points de base sur 1996-2026, ce que l'étude 007 disait déjà
par son coût de seuil de 3,92 points de base. L'impact ajouterait 9,3 % par an
au premier million.

Côté fonds fermés : sur les années communes, le seul co-mouvement dont
l'intervalle exclut zéro est celui avec le Wellington de Citadel, 0,79 sur sept
années, borne basse 0,10. Le portefeuille à 10 % de volatilité rendrait 7,1 %
par an, modélisé, contre 37,6 % net pour Medallion sur 2010-2018, rapporté.

## Décision

La phase 6 est close. Le module de capacité reste tel quel, avec sa forme
fermée et son contrôle. Deux défauts de données sont déclarés et non corrigés
aujourd'hui ; le premier l'a été le 2026-09-03, voir l'entrée de ce jour. La série de portage de change de l'étude 008 n'a pas d'avril
2020. Cause mesurée le 2026-09-02 : le taux interbancaire américain à trois
mois de la FRED, `IR3TIB01USM156N`, manque ce mois-là, et le taux de base
absent annule les onze portages. Cela retire un mois à l'étude 009 et une
année à la comparaison annuelle. Et Yahoo garde des cotations fantômes à volume nul après une sortie
de cote, ce que le modèle traite par le dernier volume connu, compté.

## Question suivante

La capacité de l'arbitrage statistique sur la seule fenêtre de l'article,
1997-2007, où le brut couvrait les coûts. Et, pour le momentum, la même mesure
sur des contrats à terme dès qu'une source gratuite de volumes existe, ce qui
n'est pas le cas au 2026-09-02.

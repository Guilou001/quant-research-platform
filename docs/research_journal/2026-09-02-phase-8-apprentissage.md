# 2026-09-02 : la non-linéarité prévoit-elle mieux que le linéaire, après coûts ?

## Question

Gu, Kelly et Xiu (2020) publient qu'arbres et réseaux doublent le pouvoir
prédictif d'une régression sur les rendements mensuels. Le laboratoire a un
panneau point-in-time de 1 526 grandes capitalisations sur onze ans, avec
vingt-sept caractéristiques. Il a aussi une règle : un modèle complexe doit
battre un modèle simple après coûts et hors échantillon, sinon on garde le
simple. Les deux faits se confrontent.

## Hypothèse

Écrite dans `config.yaml` avant le premier chiffre : un ensemble d'arbres
appris sur vingt-sept caractéristiques ordonne les rendements du mois suivant
mieux qu'une régression pénalisée, et l'écart survit aux coûts de transaction
hors échantillon.

## Expérience

Trois modules, `quantlab.models.panel`, `cross_sectional` et `evaluation`, et
l'étude 011. Rangs transversaux dans l'intervalle de moins un à plus un,
étiquette du mois suivant par un décalage explicite, six méthodes de
`scikit-learn` derrière le protocole `AlphaModel` (ADR-013). Analyse glissante
ancrée, cinq ans d'entraînement, un an de test, purge d'un mois, configuration
choisie sur les vingt-quatre derniers mois de l'entraînement. Dix-sept essais
déclarés.

## Résultat

L'hypothèse est fausse.

| Mesure | Régression pénalisée, référence | Arbres amplifiés, modèle complexe |
|---|---:|---:|
| R² mensuel hors échantillon | 0,41 % | 0,35 % |
| Corrélation de rang moyenne | -0,022 | -0,016 |
| Sharpe net du décile long moins court, 72 mois | 0,277 | 0,663 |
| Diebold et Mariano contre la référence | | -0,45, p 0,65 |
| t du Sharpe, Sharpe dégonflé | | 1,99, 0,82 |

Statut : mesuré sur 2020-07 à 2026-06, coûts modélisés à 10 points de base.
Le R² des six méthodes tient dans la plage de l'article, 0,35 % à 0,48 %,
mais la corrélation de rang est négative pour les six. Le R² sans centrage
récompense la prévision du niveau du mois, que la volatilité passée porte ; il
ne dit rien de l'ordre des titres, qui est nul. Le portefeuille des arbres
gagne sur les déciles extrêmes, avec un t de 1,99 sur six ans.

## Décision

Verdict `REJECTED`, et la règle 9 tient : on garde le linéaire. Les modules
restent, avec leurs contrôles. La phase 8 est close.

## Question suivante

La même étude sur le panneau quotidien de survivants de l'étude 002, trente
ans au lieu de onze, pour savoir si c'est la longueur de l'historique qui
manque aux arbres ou le signal lui-même.

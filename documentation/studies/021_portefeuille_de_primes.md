# 021 Pourquoi refuser un portefeuille qui gagne de l'argent ?

Le portefeuille étudié obtient un Sharpe net de {{s021_sharpe}}, mais ne remplit pas tous les critères fixés pour le retenir.
Son meilleur composant seul obtient {{s021_single}} sur la même période.
Le refus porte sur une règle de décision et une hypothèse précises. Il ne signifie pas que tous les rendements observés sont négatifs.

## Trois sources de rendement dans un même portefeuille

Une première composante suit les tendances. Une deuxième combine la valeur et le momentum.
La troisième vend des options de vente, qui obligent leur vendeur à acheter à un prix convenu si leur détenteur exerce ce droit.
La prime reçue rémunère une exposition aux pertes, parfois importantes, lorsque les prix baissent fortement.

Ces composantes peuvent perdre à des moments différents.
Les mélanger cherche à rendre le risque plus régulier, mais ne garantit pas de battre chaque composante sur toute mesure.
Une protection utile dans une crise peut avoir un coût pendant le reste de l'historique.

## Un exemple de diversification qui coûte quelque chose

L'exemple est fictif et comporte deux périodes.
Le placement A gagne 10 % puis perd 10 %. Le placement B perd 2 % puis gagne 8 %.
À parts égales rééquilibrées avant chaque période, leur mélange gagne 4 % puis perd 1 %.

| Placement | Première période | Deuxième période | Gain composé |
|---|---:|---:|---:|
| A | +10 % | -10 % | -1 % |
| B | -2 % | +8 % | +5,84 % |
| Mélange à parts égales | +4 % | -1 % | +2,96 % |

Le mélange évite les variations extrêmes de A, mais gagne moins que B sur cet exemple.
Le qualifier de meilleur demande donc de préciser le critère retenu.
Le rendement final, la perte maximale et la régularité ne répondent pas à la même question.

## Comment les articles conduisent à la question locale

Les travaux sur la tendance, la valeur et le momentum motivent les composantes.
Les indices du Cboe fournissent une référence pour la vente d'options.
Les recherches sur la diversification et le contrôle de volatilité motivent la règle de combinaison.
Il s'agit d'une construction inspirée de plusieurs travaux, avec des substituts de données et des coûts modélisés.

Les références sont [Hurst, Ooi et Pedersen](repo:docs/literature/hurst_ooi_pedersen_2017.md),
[Asness, Moskowitz et Pedersen](repo:docs/literature/asness_moskowitz_pedersen_2013.md)
et [Moreira et Muir](repo:docs/literature/moreira_muir_2017.md).
La [spécification initiale](repo:docs/specs/007-indices-cboe-et-empilement.md) décrit les choix écrits avant les calculs de cette étude.

## La règle retenue avant de regarder

Les composantes les moins volatiles reçoivent davantage de poids.
La **volatilité** mesure la dispersion des rendements, pas toutes les formes de risque.
L'allocation vise une volatilité annuelle de 10 %, mais l'exposition totale est plafonnée à 1,5 fois le capital.

Dépasser une fois le capital exige un financement. Le coût supposé dépasse le taux court de 0,50 point de pourcentage annuel.
Ce choix est une hypothèse de l'expérience, et non un tarif garanti pour un investisseur.
Les autres coûts portent sur les transactions et le renouvellement des options.

Le test couvre {{s021_n}} mois, de décembre 2010 à juin 2026.
Les {{s021_future_n}} derniers mois constituent la période finale réservée dans le protocole local.
Cette réservation locale ne rend pas l'histoire économique inconnue du chercheur et n'efface pas les études déjà consultées.

## Comparer le résultat aux critères

| Mesure | Résultat enregistré | Lecture |
|---|---:|---|
| Sharpe du portefeuille net | {{s021_sharpe}} | Rendement excédentaire rapporté à sa dispersion |
| Sharpe du meilleur composant seul | {{s021_single}} | Le portefeuille ne le dépasse pas sur ce critère |
| Sharpe dans la période finale | {{s021_future}} | Résultat positif dans la fenêtre réservée |
| Statistique t dans la période finale | {{s021_t}} | Sous le seuil de 3 fixé dans le protocole |
| Pire repli depuis un sommet | {{s021_dd}} % | Perte historique maximale de la courbe retenue |

Les deux Sharpes du début sont calculés sur la même fenêtre.
La comparaison ne suffit pas à prouver que leur différence est statistiquement distincte de zéro.
Le critère initial demandait toutefois que le portefeuille dépasse son meilleur composant. La valeur observée n'y satisfait pas.
Source dans les [résultats de référence](repo:studies/021_portefeuille_de_primes/results/metrics.json).

![Les critères de décision du portefeuille](repo:docs/guide/figures/verdict_portefeuille.png)

Le graphique distingue la comparaison des Sharpes et le seuil statistique.
Les axes sont séparés, car un Sharpe et une statistique t n'ont pas la même signification.
Un résultat positif peut rester sous la barre de décision choisie.

## Le libellé automatique demande une traduction

Le [fichier de verdict](repo:studies/021_portefeuille_de_primes/results/tables/verdict_reasons.csv) appelle « réplication » la comparaison avec le meilleur composant.
Dans ce cas, la référence est une autre sortie du laboratoire, pas un chiffre reproduit depuis un article.
La corrélation avec un portefeuille existant y est aussi indiquée comme non mesurée.
Elle constitue une preuve manquante, et non une corrélation défavorable observée.

Cette lecture distingue un critère échoué d'un contrôle absent.
Elle empêche le mot `REJECTED` de masquer la nature du problème.
Les seuils de 3 ou de 0,95 sont des choix du protocole, pas des lois universelles de l'investissement.

## Pourquoi ne pas retirer immédiatement la composante décevante

L'analyse détaillée montre qu'enlever la tendance améliorerait le Sharpe dans cet historique.
Ce diagnostic peut motiver une nouvelle hypothèse. Il ne peut pas être utilisé pour annoncer que la règle initiale avait réussi.
La nouvelle règle demanderait une nouvelle évaluation et une déclaration du nombre d'essais supplémentaires.

L'[annexe technique](repo:studies/021_portefeuille_de_primes/ANNEXE_TECHNIQUE.md) conserve les variantes, les retraits de composantes et les coûts.
Le [chapitre sur le verdict](repo:docs/guide/08_conclusion.md) donne une grille pour lire les autres études avec la même distinction.

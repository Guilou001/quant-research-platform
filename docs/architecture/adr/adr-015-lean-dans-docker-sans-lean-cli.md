# ADR-015 : LEAN tourne dans son image publique, sans lean-cli, sur des barres exportées par le laboratoire

**Statut** : acceptée le 2026-09-03, phase 9.

## Contexte

L'ADR-008 a réservé LEAN à la réimplémentation indépendante des stratégies
retenues. Aucune ne l'a été, et le moteur du laboratoire n'avait jamais été
confronté à un moteur écrit par d'autres. L'outil officiel, `lean-cli`, exige
à l'initialisation un identifiant et un jeton d'API QuantConnect, mesuré le
2026-09-03 : la commande `lean init` s'interrompt sur cette demande. Le
laboratoire ne dépend d'aucun compte tiers pour se reproduire.

## Décision

LEAN tourne directement dans l'image publique `quantconnect/lean`, épinglée
par son empreinte, lancée par un script shell qui monte trois dossiers :
l'algorithme, les données, les résultats. Les deux bases de référence du moteur, les heures de marché et les
propriétés des symboles, sont copiées depuis l'image elle-même.

Les données de LEAN sont écrites par le laboratoire depuis les mêmes prix que
ceux qu'il utilise, par `quantlab.backtest.lean_bridge`. Trois conventions
sont fixées et testées. Dans le premier jeu de données, l'ouverture du jour est
la clôture de la veille, pour que l'exécution à l'ouverture suivante de LEAN
désigne le prix que le moteur du laboratoire suppose. C'est ce qui vérifie
l'arithmétique. Un second jeu porte l'ouverture réelle de Yahoo, ajustée par
le facteur de la clôture, pour mesurer ce que cette convention vaut. Les prix sont déjà ajustés et LEAN les lit en mode
`Raw`, sans fichier de correspondance ni de facteurs. Le taux sans risque est
fourni en CSV, et l'algorithme n'en lit jamais une valeur future.

L'algorithme de contrôle n'importe rien de `quantlab`, et un test le vérifie
sur le texte du fichier. Il ne recopie pas non plus l'univers ni les
paramètres : l'export les écrit dans `custom/params.json` depuis la
configuration de l'étude, et l'algorithme les lit là.

La réconciliation compare trois choses, et chacune est une table publiée. Les
rendements mensuels après retrait du financement, les poids à chaque date de
décision, et le prix de chaque exécution contre les clôtures voisines. Un
écart mensuel au-delà de 1e-4 est un écart à expliquer, seuil déclaré avant la
première lecture.

## Conséquences

Le moteur du laboratoire est contrôlé sur l'étude 001 à 5e-6 par mois. Deux
coûts que le moteur mensuel ne peut pas voir sont mesurés : l'ouverture
réelle du lendemain, 25 points de base par an, et une séance de retard, 71.
L'audit du 2026-09-03 a demandé le second jeu de données, l'épinglage de
l'image et la lecture des paramètres, tous trois absents de la première
version. Le prix est une image de 19,4 Go et Docker en marche. Le passage à une
stratégie retenue, si une l'est un jour, ne demande qu'un nouvel algorithme
dans `lean/algorithm/` et un nouvel export.

Les prix encodés en dix-millièmes de dollar bornent la précision : l'effet a
été mesuré, 0,05 % sur la volatilité du seul instrument à 0,45 % de volatilité,
et il est déclaré plutôt que corrigé.

## Options écartées

**`lean-cli`.** Rejeté parce que son initialisation exige un compte, ce qui
rendrait la reproduction dépendante d'un tiers.

**Un second moteur écrit dans le dépôt.** Rejeté par l'ADR-008 : un moteur
écrit par la même personne partage les angles morts du premier.

**Des barres à ouverture réelle de Yahoo.** Rejeté : l'ouverture de Yahoo
n'est pas ajustée de la même façon que la clôture ajustée, et la comparaison
ne porterait plus sur la même série de prix. La convention retenue est
déclarée et mesurée sur toutes les exécutions.

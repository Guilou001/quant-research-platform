# 003 Pourquoi associer valeur et momentum ?

La valeur cherche des actifs peu chers relativement à une mesure économique.
Le momentum cherche des actifs dont le prix a monté.
Ces deux règles peuvent prendre des positions différentes au même moment.

## Un exemple fictif

Le bénéfice d'une entreprise reste inchangé pendant que son prix passe de 100 à 120 dollars.
Elle devient plus chère relativement à ce bénéfice.
La hausse peut attirer une règle de momentum et éloigner une règle de valeur.

Cet exemple explique pourquoi les signaux peuvent s'opposer.
Il ne prouve pas que leur opposition suffit à produire un rendement.

## Le lien avec l'article

Asness, Moskowitz et Pedersen étudient la valeur et le momentum dans plusieurs classes d'actifs.
La [fiche de littérature](repo:docs/literature/asness_moskowitz_pedersen_2013.md) précise les définitions et les comparaisons.
Le laboratoire utilise leurs facteurs AQR, puis une construction alternative fondée sur Kenneth French.

L'exercice distingue le rendement de chaque composante et le gain associé à leurs mouvements communs.

## Le résultat sur les facteurs publiés

| Mesure | Janvier 1972 à juin 2026 |
|---|---:|
| Corrélation valeur et momentum | {{s003_corr}} |
| Sharpe du momentum seul | {{s003_single}} |
| Sharpe du mélange à parts égales | {{s003_mix}} |

Ces chiffres portent sur 654 mois et sont bruts de frais.
Le mélange présente un meilleur rapport entre rendement moyen et dispersion dans cet échantillon.
Cela ne constitue pas une promesse de domination future.

Une identité de variance vérifie le rôle arithmétique de la corrélation.
Elle n'identifie pas, à elle seule, la cause économique de cette corrélation.

## Pourquoi la date du signal compte

Un prix actuel et un prix retardé dans le ratio de valeur ne produisent pas les mêmes positions.
La construction alternative montre une corrélation différente.
Les conventions de mesure font donc partie du résultat, plutôt que d'un simple détail technique.

L'[étude 012](repo:docs/etudes/012_multi_strategy_net.md) poursuit la question après les coûts.

## Vérifier le résultat

Les [mesures enregistrées](repo:studies/003_value_and_momentum/results/metrics.json) donnent les nombres et leurs fenêtres.
L'[annexe technique](repo:studies/003_value_and_momentum/ANNEXE_TECHNIQUE.md) conserve les tableaux, les hypothèses, les limites et les commandes de calcul.
Le [script de l'étude](repo:studies/003_value_and_momentum/run.py) relie ces choix aux fonctions du laboratoire.

# Comprendre avant de comparer

Ce parcours explique comment passer d'une idée de placement à une conclusion que l'on peut vérifier.
Aucune connaissance de programmation n'est nécessaire pour lire les exemples.
Les calculs et les sources restent accessibles pour approfondir.

## Huit chapitres, dans l'ordre

| Chapitre | Ce que vous saurez expliquer |
|---|---|
| [01 La question économique](01_question.md) | Pourquoi une stratégie pourrait être rémunérée et ce qui pourrait la faire échouer |
| [02 L'information disponible](02_donnees.md) | Pourquoi la date d'un chiffre et les entreprises absentes comptent |
| [03 Le calendrier du test](03_calendrier.md) | Comment séparer l'apprentissage, le choix des paramètres et l'évaluation |
| [04 Le hasard et l'incertitude](04_hasard.md) | Pourquoi le meilleur résultat parmi beaucoup d'essais demande une vérification supplémentaire |
| [05 Prévoir, classer, investir](05_prevoir.md) | Pourquoi une bonne prévision ne garantit pas un bon portefeuille |
| [06 Ce que coûtent les positions](06_couts.md) | Comment les échanges, les emprunts et la taille réduisent le rendement |
| [07 Associer plusieurs stratégies](07_portefeuille.md) | Ce que la diversification améliore et ce qu'elle ne répare pas |
| [08 Lire une conclusion](08_conclusion.md) | Comment distinguer une mesure, une explication possible et une preuve manquante |

## Cinq enquêtes pour mettre les idées à l'épreuve

Commencez par [les prévisions des actions](../etudes/011_cross_sectional_ml.md).
Poursuivez avec [les entreprises oubliées](../etudes/013_cross_sectional_ml_long.md), puis [l'affaiblissement après publication](../etudes/016_publication_decay_212.md).
Terminez par [la nuit et la journée](../etudes/018_nuit_contre_journee.md) et [le portefeuille de primes](../etudes/021_portefeuille_de_primes.md).

Les [vingt et une études](../etudes/index.md) proposent ensuite d'autres applications.
Le [manuel PDF](https://github.com/Guilou001/quant-research-platform/blob/main/rapport/manuel.pdf) réunit les chapitres et leurs présentations.
Le [registre numérique](https://github.com/Guilou001/quant-research-platform/blob/main/documentation/publication_values.json) donne la source exacte des résultats insérés dans ces textes.

## Refaire les exemples

Les exemples portant la mention « fictif » servent à comprendre un calcul.
Ils ne sont pas des rendements de marché.

~~~bash
uv sync --locked --all-extras --dev
uv run python scripts/build_learning.py --check
uv run pytest tests/unit/test_reporting_education.py
~~~

Ces commandes fonctionnent hors réseau après installation des dépendances.
Les études historiques disposent de commandes séparées dans leurs annexes.

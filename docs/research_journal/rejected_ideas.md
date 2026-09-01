# Les idées rejetées

Cette page est aussi importante que les résultats. Une stratégie qui échoue est
une information ; la taire produit le biais de publication qui rend la
littérature financière si difficile à répliquer.

Elle sert aussi à quelque chose de très concret. Le ratio de Sharpe dégonflé a
besoin du nombre d'essais menés. Chaque ligne ici est un essai, et l'oublier
gonfle mécaniquement tous les résultats gardés.

## Le gabarit

| Champ | Ce qu'il porte |
|---|---|
| Date | quand l'essai a été mené |
| Idée | ce qui a été testé, en une phrase |
| Hypothèse économique | pourquoi cela aurait dû fonctionner |
| Ce qui a été mesuré | les chiffres, avec leur échantillon et leurs coûts |
| Pourquoi c'est rejeté | l'étape du parcours qui a échoué |
| Ce que cela apprend | ce qui reste utile de l'essai |

## Les rejets

Aucun au 2026-09-01. Les phases 0 à 3 construisent l'infrastructure ; aucune
stratégie n'a encore été testée, donc aucune n'a encore été rejetée.

Cette ligne se remplira à partir de la phase 4, et son absence de remplissage
serait un signal d'alarme : un laboratoire qui ne rejette rien ne teste rien.

## Le décompte des essais

| Famille de stratégies | Essais menés | Retenus | Rejetés |
|---|---|---|---|
| Momentum temporel | 0 | 0 | 0 |
| Momentum transversal | 0 | 0 | 0 |
| Valeur | 0 | 0 | 0 |
| Qualité | 0 | 0 | 0 |
| Bêta défensif | 0 | 0 | 0 |
| Gestion de la volatilité | 0 | 0 | 0 |
| Arbitrage statistique | 0 | 0 | 0 |
| Portage | 0 | 0 | 0 |

Ce tableau alimente directement `quantlab.validation.dsr`. Il se met à jour à
chaque expérience, y compris celles qui ne mènent nulle part.

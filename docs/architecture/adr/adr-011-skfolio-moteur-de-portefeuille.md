# ADR-011 : skfolio est le moteur d'optimisation, derrière nos protocoles

**Statut** : acceptée le 2026-09-02, phase 5.

## Contexte

La phase 5 demande une dizaine d'optimiseurs (équipondéré, inverse de
volatilité, variance minimale, parité de risque, diversification maximale,
hiérarchique, CVaR) et autant d'estimateurs de covariance (empirique,
exponentiel, rétréci, factoriel, débruité). Les écrire tous soi-même prendrait
des semaines et produirait des bogues que `skfolio` a déjà corrigés.

`skfolio` 1.0.3, installé et inspecté le 2026-09-02, expose exactement ce
catalogue. Côté moments : `EmpiricalCovariance`, `EWCovariance`, `LedoitWolf`,
`ShrunkCovariance`, `DenoiseCovariance`, `DetoneCovariance`. Côté
optimisation : `EqualWeighted`, `InverseVolatility`, `MeanRisk`,
`RiskBudgeting`, `HierarchicalRiskParity`, `HierarchicalEqualRiskContribution`,
`NestedClustersOptimization`, `MaximumDiversification`,
`DistributionallyRobustCVaR`, avec coûts de transaction, frais et poids
précédents en arguments.

Le plan du projet interdit pourtant de faire d'une bibliothèque une dépendance
architecturale impossible à remplacer.

## Décision

`skfolio` est le moteur de calcul, et il reste invisible depuis les stratégies.

- `quantlab.portfolio.covariance` expose des classes qui satisfont le protocole
  `quantlab.core.protocols.RiskModel`. Certaines enveloppent `skfolio`, d'autres
  sont écrites ici quand la pédagogie l'exige, par exemple la moyenne mobile
  exponentielle dont la formule tient en une ligne.
- `quantlab.portfolio.optimizers` expose des classes qui satisfont
  `PortfolioOptimizer`. Elles enveloppent `skfolio` et lui passent covariance,
  alpha, contraintes et coûts.
- Chaque enveloppe porte la documentation en dix points de la méthode qu'elle
  appelle, et un **contrôle indépendant** de son résultat. La parité de risque
  se vérifie par `quantlab.analytics.contributions`, contributions égales à
  1e-8. La variance minimale se vérifie par les conditions de premier ordre, et
  l'inverse de volatilité par la formule fermée.
- Rien dans `strategies/`, `signals/` ou `backtest/` n'importe `skfolio`. Un
  test mécanique l'ajoute à la liste des imports interdits.

## Conséquences

Un optimiseur de `skfolio` se remplace par une implémentation maison ou par
`Riskfolio-Lib` sans toucher à une stratégie, ce qui est le but. Le prix est une
couche d'enveloppe à maintenir, et la version de `skfolio` verrouillée dans
`uv.lock`.

Le contrôle indépendant de chaque résultat n'est pas de la redondance : c'est ce
qui transforme une bibliothèque tierce, dont on ne relit pas le code, en un
résultat qu'on peut défendre.

## Options écartées

**Tout écrire soi-même.** Rejetée pour le délai et le risque d'erreur, sauf là
où la formule est courte et où l'écrire enseigne quelque chose.

**Appeler `skfolio` directement depuis les études.** Rejetée parce que le jour
où une API change ou qu'un second moteur doit servir de contrôle, chaque étude
serait à réécrire.

**Riskfolio-Lib comme moteur principal.** Rejetée pour l'interface : `skfolio`
suit l'API de `scikit-learn`, ce qui rend ses estimateurs composables avec la
validation croisée déjà en place. `Riskfolio-Lib` reste le second moteur de
contrôle prévu par le plan.

# 012 Que reste-t-il du mélange après les frais de chaque stratégie ?

L'étude 009 combinait principalement des rendements bruts.
Cette étude remplace les composantes par leurs séries après les coûts retenus dans chaque expérience.
Elle pose une question simple, la diversification reste-t-elle avantageuse lorsque les positions doivent être négociées ?

## Un exemple fictif

Une stratégie gagne 8 % avant frais et coûte 1 % du capital.
Une autre gagne également 8 %, mais coûte 10 %.
Leurs rendements nets simplifiés deviennent 7 % et moins 2 %.

Le mélange à parts égales donne alors 2,5 % dans cette unique période, avant d'autres frais.
Combiner la seconde stratégie réduit ici la moyenne.
Une éventuelle réduction du risque doit être évaluée séparément.

## Le lien avec les travaux sur les portefeuilles

La comparaison reprend les références de l'[étude 009](../../docs/etudes/009_multi_strategy.md).
Les coûts modifient les rendements à allouer.
Ils peuvent aussi modifier leur dispersion et leurs corrélations lorsqu'ils varient dans le temps.

Il serait donc incorrect de supposer que le passage au net laisse toutes les corrélations inchangées.

## Le résultat sur la période finale

Le Sharpe de la référence en parité de risque vaut -0,396 sur janvier 2020 à juin 2026.
Le signe négatif indique un rendement excédentaire moyen négatif relativement à sa dispersion.
Il ne signifie pas que toutes les allocations possibles sont mauvaises.

Sur la fenêtre d'allocation plus large, la référence ne dépasse pas non plus la meilleure composante selon le critère déclaré.
L'arbitrage statistique, qui contribuait fortement au mélange brut, apporte une série nette beaucoup moins favorable.

## Ce que la comparaison autorise

Le rejet concerne ces huit composantes, ces hypothèses de coût et cette règle de sélection.
Les coûts sont des hypothèses publiées, pas un relevé de transactions réelles.
Les données des composantes conservent également des qualités différentes.

Le [chapitre sur la diversification](../../docs/guide/07_portefeuille.md) explique pourquoi réduire le risque et améliorer le rendement moyen sont deux objectifs distincts.

## Vérifier le résultat

Les [mesures enregistrées](results/metrics.json) donnent les nombres et leurs fenêtres.
L'[annexe technique](ANNEXE_TECHNIQUE.md) conserve les tableaux, les hypothèses, les limites et les commandes de calcul.
Le [script de l'étude](run.py) relie ces choix aux fonctions du laboratoire.

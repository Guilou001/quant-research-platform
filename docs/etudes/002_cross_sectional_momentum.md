# 002 Acheter les actions qui ont le plus monté

Le momentum transversal compare les actions entre elles.
Il achète les gagnantes passées et vend les perdantes passées.
Il diffère du suivi de tendance, qui examine chaque actif par rapport à son propre passé.

## Un exemple fictif

A a gagné 15 %, B a gagné 5 % et C a perdu 10 %.
Une règle simplifiée achète A et vend C.
Si A gagne ensuite 2 % et C gagne 6 %, l'écart de rendement vaut moins quatre points de pourcentage.

Le marché peut donc monter pendant que la stratégie perd.
Son résultat dépend de la différence entre les groupes, pas uniquement de la direction générale des actions.

## La question posée à la littérature

Jegadeesh et Titman documentent cette stratégie en 1993.
La [fiche de l'article](../literature/jegadeesh_titman_1993.md) précise les périodes de formation, de détention et le délai entre les deux.
Un décalage d'une semaine et un décalage d'un mois ne définissent pas le même test.

L'étude utilise notamment les portefeuilles triés de Kenneth French pour prolonger la comparaison.
Elle distingue cette série de la reconstruction sur les entreprises encore présentes aujourd'hui.

## Le résultat utile

L'écart gagnant moins perdant passe de 1,630 % par mois sur la fenêtre originale à 0,768 % sur 1994-2026, avant frais.
La moyenne reste positive, mais son incertitude augmente relativement au gain mesuré.
L'absence de significativité au seuil retenu ne signifie pas que le rendement véritable est exactement nul.

Dans la reconstruction sur survivants, le biais ne relève pas automatiquement la performance.
La sélection modifie aussi le groupe vendu.
Cet exemple réel justifie la prudence du [chapitre sur les données](../guide/02_donnees.md).

## La limite de la conclusion

Comparer deux périodes montre une évolution du résultat.
Cela ne suffit pas à isoler la concurrence créée par la publication.
Les changements de risque, de composition et de coûts restent des explications à examiner.

## Vérifier le résultat

Les [mesures enregistrées](https://github.com/Guilou001/quant-research-platform/blob/main/studies/002_cross_sectional_momentum/results/metrics.json) donnent les nombres et leurs fenêtres.
L'[annexe technique](https://github.com/Guilou001/quant-research-platform/blob/main/studies/002_cross_sectional_momentum/ANNEXE_TECHNIQUE.md) conserve les tableaux, les hypothèses, les limites et les commandes de calcul.
Le [script de l'étude](https://github.com/Guilou001/quant-research-platform/blob/main/studies/002_cross_sectional_momentum/run.py) relie ces choix aux fonctions du laboratoire.

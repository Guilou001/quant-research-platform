# 004 Peut-on reconstruire un placement fondé sur la qualité ?

Une entreprise rentable, stable et capable de financer son activité peut sembler de meilleure qualité.
Cela ne suffit pas à en faire un bon placement.
Le prix payé pour cette qualité compte aussi.

L'étude distingue deux questions.
Retrouvons-nous les propriétés du facteur publié par AQR ?
Pouvons-nous reconstruire un facteur comparable depuis les rapports publics des entreprises ?

## Un exemple fictif

Deux entreprises produisent chacune dix dollars de bénéfice annuel.
La première coûte 100 dollars et la seconde 250 dollars.
Même si la seconde est plus stable, son bénéfice représente une part plus faible du prix payé.

L'exemple ne fournit pas une méthode de valorisation complète.
Il explique seulement pourquoi qualité de l'entreprise et rendement attendu du placement ne se confondent pas.

## Ce qui est repris de la littérature

La [fiche Quality Minus Junk](repo:docs/literature/asness_frazzini_pedersen_2019_qmj.md) présente les composantes du score et les versions de l'article.
Le laboratoire s'appuie sur la version de travail obtenue.
La version publiée n'a pas été lue intégralement, et une différence sur le nombre de composantes reste déclarée.

Les données comptables de la SEC sont datées selon leur disponibilité.
Cette précaution n'élargit pas automatiquement le panel aux entreprises disparues.

## Le résultat de la reconstruction

La corrélation avec le facteur publié vaut {{s004_corr}} sur 132 mois communs, de juin 2015 à mai 2026.
Elle reste sous le seuil de comparaison fixé à 0,50.
Le Sharpe de notre construction vaut {{s004_ours}}, avant les coûts d'une mise en œuvre complète.

Retrouver les statistiques d'une série fournie par ses auteurs est plus limité que reconstruire ses positions.
L'étude réussit certaines comparaisons sur la série publiée, mais sa construction indépendante ne reproduit pas suffisamment ses mouvements.

## Ce que l'écart apprend

L'univers, les variables disponibles et la version du score diffèrent.
Ces écarts proposent des pistes explicatives, sans isoler une cause unique.
Le [registre des données](repo:docs/data/index.md) aide à retrouver leurs limites.

## Vérifier le résultat

Les [mesures enregistrées](repo:studies/004_quality_minus_junk/results/metrics.json) donnent les nombres et leurs fenêtres.
L'[annexe technique](repo:studies/004_quality_minus_junk/ANNEXE_TECHNIQUE.md) conserve les tableaux, les hypothèses, les limites et les commandes de calcul.
Le [script de l'étude](repo:studies/004_quality_minus_junk/run.py) relie ces choix aux fonctions du laboratoire.

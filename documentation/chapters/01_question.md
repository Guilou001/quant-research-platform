# 01 Partir d'une question économique

Une stratégie est une règle qui transforme une information en positions.
Avant de mesurer son rendement, il faut expliquer pourquoi quelqu'un pourrait être payé pour la suivre.
Cette explication donne aussi une raison de chercher où la règle échoue.

Le momentum est un exemple. Il consiste à suivre une hausse ou une baisse passée.
La question est de savoir si cette tendance renseigne encore sur les prochains rendements.
Dire que « le prix monte parce qu'il montait » décrit la règle, sans expliquer le mécanisme.

## Trois explications à départager

Une prime de risque rémunère une perte possible que d'autres investisseurs souhaitent éviter.
Une erreur de prix peut venir d'une réaction lente ou excessive à une information.
Une contrainte peut empêcher certains investisseurs de prendre une position, même si elle leur paraît intéressante.

Ces explications peuvent coexister. Une baisse après publication ne suffit pas à choisir entre elles.
Les risques, les coûts, la concurrence et les conditions économiques ont aussi pu changer.

## Un exemple fictif

Un contrat verse régulièrement un petit revenu, mais impose une grosse perte lors d'une crise.
Un autre exploite une information mal comprise et cesse de rapporter quand elle devient connue.

Les deux peuvent afficher le même rendement moyen sur une période courte.
Le premier rémunère éventuellement un risque rare. Le second dépend éventuellement d'une erreur qui peut disparaître.
Pour les distinguer, il faut examiner les pertes, les dates et les expositions.

Le rendement moyen répond donc à une seule question, combien le placement a rapporté en moyenne dans cet échantillon.
Il ne dit pas pourquoi, ni si la rémunération compense les risques.

## Comment le laboratoire pose sa question

L'[étude 001](repo:docs/etudes/001_time_series_momentum.md) examine le suivi de tendance après publication.
L'[étude 008](repo:docs/etudes/008_carry.md) s'intéresse au portage de devises.
L'[étude 021](repo:docs/etudes/021_portefeuille_de_primes.md) combine plusieurs sources de rendement et étudie leurs risques communs.

Les articles proposent des mécanismes et des mesures.
Le laboratoire distingue leurs résultats rapportés des calculs reproduits et des adaptations nécessaires aux données disponibles.
Une ressemblance de chiffre ne suffit pas à reproduire tout un article.

## La question à garder pour la suite

Avant un test, écrivez la règle, le mécanisme envisagé et le résultat qui vous ferait douter.
Indiquez aussi le placement de comparaison.
Une stratégie qui monte de 8 % lorsque son repère monte de 12 % n'a pas montré une supériorité par son seul rendement positif.

La [fiche de Moskowitz, Ooi et Pedersen](repo:docs/literature/moskowitz_ooi_pedersen_2012.md) illustre ce travail préparatoire.
Le [chapitre suivant](repo:docs/guide/02_donnees.md) examine ce que les données permettent réellement de tester.

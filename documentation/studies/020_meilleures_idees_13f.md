# 020 Copier les plus grosses positions des gestionnaires aide-t-il ?

Les déclarations 13F indiquent certaines positions détenues par de grands gestionnaires.
Elles décrivent une fin de trimestre, mais deviennent publiques plus tard.
Le laboratoire choisit des positions seulement après le délai de formation déclaré.

## Un exemple fictif

Un gestionnaire possède 20 % de son portefeuille dans A au 31 mars.
Il dépose sa déclaration le 12 mai.
Un investisseur qui lit ce dépôt ne peut pas prétendre avoir copié cette information le 1er avril.

La position peut aussi avoir changé entre mars et mai.
La déclaration révèle une détention passée, pas nécessairement la conviction actuelle du gestionnaire.

## La question inspirée de la littérature

Le document de Cohen, Polk et Silli motive l'idée de regarder les positions les plus importantes.
Le texte intégral n'a pas été lu dans l'expérience initiale.
La [fiche de littérature](repo:docs/literature/cohen_polk_silli_2010.md) déclare cette limite.

Notre règle sélectionne la plus grosse position de gestionnaires répondant à des seuils de concentration.
Elle forme le portefeuille au quarante-sixième jour après la fin du trimestre, avec les dépôts alors reçus.

## Le résultat et son unité

Sur 157 mois, de 2013 à août 2026, la série des écarts mensuels au marché produit un rendement composé annualisé de {{s020_gross}} % avant frais.
Il devient {{s020_net}} % après dix points de base par unité négociée selon la convention de l'étude.

Composer les différences mensuelles ne revient pas à soustraire les rendements annualisés des deux placements.
L'annexe publie aussi ces rendements séparés et la régression contre le marché.
La supériorité n'est pas suffisamment établie dans les tests retenus.

## La limite qui pèse sur l'interprétation

{{s020_missing}} % des idées formées n'ont pas de prix dans la source utilisée.
Dater correctement les dépôts ne restitue pas ces observations manquantes.
La plus grosse position peut également refléter une hausse passée, des contraintes ou un mandat, plutôt qu'une information privée.

Le [chapitre sur les données](repo:docs/guide/02_donnees.md) distingue ces problèmes.

## Vérifier le résultat

Les [mesures enregistrées](repo:studies/020_meilleures_idees_13f/results/metrics.json) donnent les nombres et leurs fenêtres.
L'[annexe technique](repo:studies/020_meilleures_idees_13f/ANNEXE_TECHNIQUE.md) conserve les tableaux, les hypothèses, les limites et les commandes de calcul.
Le [script de l'étude](repo:studies/020_meilleures_idees_13f/run.py) relie ces choix aux fonctions du laboratoire.

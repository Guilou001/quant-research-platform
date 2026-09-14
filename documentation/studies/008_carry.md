# 008 Un taux plus élevé paie-t-il le risque de change ?

Le **portage** est le revenu associé au maintien d'une position si certaines conditions de prix restent inchangées.
Sur les devises, un écart de taux peut inciter à emprunter dans la monnaie au taux faible pour placer dans celle au taux élevé.
La variation du change peut effacer cet écart.

## Un exemple fictif

Le placement rapporte 5 % dans une monnaie et son financement coûte 2 % dans l'autre.
Sans variation du change, l'écart est voisin de trois points de pourcentage avant frais.
Si la monnaie du placement perd 8 %, le placement converti rapporte environ moins 3,4 %, avant le coût du financement.

Le taux affiché n'est donc pas le rendement garanti dans la monnaie de l'investisseur.
Il faut convertir le capital final et tenir compte du financement.

## Ce que l'article examine

Koijen et ses coauteurs étudient le portage dans plusieurs classes d'actifs.
Notre expérience porte sur les devises accessibles.
La [fiche de littérature](repo:docs/literature/koijen_moskowitz_pedersen_vrugt_2018.md) explique pourquoi les autres classes ne sont pas reconstruites ici.

## Le résultat et sa sensibilité

Sur novembre 1983 à septembre 2012, la régression donne un coefficient de {{s008_coefficient}} et une statistique t de {{s008_t}}.
Le coefficient mesure une association entre le portage et le rendement futur, dans les unités et la spécification du modèle.
La statistique t compare l'estimation à son erreur type.

La comparaison est proche du chiffre publié dans la convention principale.
Retirer le dollar du classement modifie toutefois le coefficient et l'asymétrie des rendements.
Le statut de comparaison réussie doit donc rester attaché à cette convention précise.

## Ce qui reste après la fenêtre originale

Le pouvoir prédictif estimé devient plus faible et plus incertain sur octobre 2012 à juin 2026.
Cela ne permet pas d'affirmer que tous les portages sont devenus nuls.
L'étude souligne surtout la dépendance au numéraire, c'est-à-dire à la monnaie servant de référence.

## Vérifier le résultat

Les [mesures enregistrées](repo:studies/008_carry/results/metrics.json) donnent les nombres et leurs fenêtres.
L'[annexe technique](repo:studies/008_carry/ANNEXE_TECHNIQUE.md) conserve les tableaux, les hypothèses, les limites et les commandes de calcul.
Le [script de l'étude](repo:studies/008_carry/run.py) relie ces choix aux fonctions du laboratoire.

# 06 Passer du rendement théorique au rendement après frais

Un test peut supposer que les positions s'échangent au prix affiché.
Un ordre réel doit trouver une contrepartie.
Les commissions, l'écart acheteur-vendeur et l'effet de l'ordre sur le prix peuvent réduire le rendement.

La **rotation** mesure la quantité de positions échangées relativement au capital.
Il faut lire sa convention, car certaines mesures divisent la somme des achats et des ventes par deux.

## Un exemple fictif de rotation

Un portefeuille de 1 000 dollars vend 200 dollars d'une action et achète 200 dollars d'une autre.
Il échange 400 dollars.
Avec un coût de dix points de base sur chaque montant négocié, il paie 0,40 dollar.

Dix points de base valent 0,10 %.
Le coût représente donc 0,04 % du portefeuille dans cet exemple.
Si une table appelle « rotation » les seuls 200 dollars remplacés, son coefficient de coût doit tenir compte des deux passages.

## Un coût petit peut devenir important

Un aller-retour coûtant quatre points de base représente 0,04 % du montant échangé.
Répété 250 fois sur un montant constant égal au capital initial, il coûte 10 % de ce capital.
Cet exemple additionne les coûts sur un montant fixe et ignore la composition des rendements.

L'[étude 018](repo:docs/etudes/018_nuit_contre_journee.md) explique pourquoi on ne peut pas appliquer ce calcul sans vérifier les positions réellement négociées.
L'[étude 007](repo:docs/etudes/007_statistical_arbitrage.md) mesure le seuil de coût qui annule son propre rendement brut.

## Le coût dépend aussi de la taille

Acheter pour 1 000 dollars et acheter pour 100 millions ne mobilise pas la même quantité de liquidité.
L'**impact de marché** représente la variation de prix liée à l'exécution de l'ordre.
Un coefficient supposé produit une estimation modélisée, pas un coût observé.

La **capacité** est le capital compatible avec les contraintes retenues.
L'[étude 010](repo:docs/etudes/010_capacity.md) examine cette question sur deux stratégies dont les positions et les volumes sont disponibles.
Un facteur publié sans détail des titres ne permet pas le même calcul.

## Les frais que le mot net ne suffit pas à préciser

Une position vendue à découvert peut demander un emprunt de titres.
Le levier peut nécessiter un financement.
Les impôts et les frais de gestion constituent encore d'autres postes.

Chaque résultat net doit donc nommer les coûts inclus.
Le [moteur analytique](repo:docs/analytics/index.md) décrit les conventions, et les annexes donnent les coefficients propres aux études.

L'[étude 017](repo:docs/etudes/017_viser_devant_la_cible.md) pose ensuite une question pratique.
Peut-on réduire les échanges sans perdre trop vite l'information du signal ?

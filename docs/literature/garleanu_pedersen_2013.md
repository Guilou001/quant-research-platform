# Dynamic trading with predictable returns and transaction costs

| | |
|---|---|
| **Auteurs** | Nicolae Gârleanu, Lasse Heje Pedersen |
| **Année** | 2013 |
| **Revue ou source** | The Journal of Finance, vol. 68, no 6, p. 2309-2340, DOI 10.1111/jofi.12080 |
| **Lien** | Résumé lu le 2026-09-03 ; document de travail NBER 15205 ; l'article n'a pas été lu en entier |
| **Statut de réplication** | forme simple dans l'étude 017 ; la forme fermée n'est pas répliquée |

Ce que cette fiche porte vient du résumé de l'article, statut **rapporté**.

## La question de recherche

Comment négocier quand chaque transaction coûte et que les signaux qui
prédisent les rendements s'éteignent à des vitesses différentes ?

En mots simples : si chaque pas coûte, faut-il courir vers la cible ou
marcher vers là où elle sera ?

## L'intuition économique

Deux principes. Viser devant la cible : le portefeuille visé n'est pas le portefeuille
optimal sans coût. C'est une moyenne où chaque signal pèse moins s'il
s'éteint vite, parce qu'un signal bref ne vaut pas le coût de le suivre.
Puis ne parcourir qu'une partie du chemin vers ce portefeuille visé, à chaque
période, une fraction fixe.

## Les données

Contrats à terme sur matières premières, dans l'application empirique de
l'article. Non consulté au-delà du résumé.

## L'univers

Voir les données.

## La méthodologie

Une forme fermée de la politique optimale sous coûts de transaction
quadratiques et signaux autorégressifs, puis son application à des contrats à
terme, comparée à des références naïves.

## Les équations qui comptent

Le portefeuille détenu se rapproche du portefeuille visé d'une fraction
constante à chaque période, et le portefeuille visé pondère chaque signal par
un facteur décroissant avec sa vitesse d'extinction. La forme exacte n'est pas
reproduite ici, l'article n'ayant pas été lu.

## Les résultats originaux

Rapportés, résumé : la stratégie optimale rend un rendement net supérieur aux
références naïves, avec un ratio de Sharpe brut plus bas et des replis moins
profonds.

## Les critiques connues

Non consultées.

## Les problèmes de réplication connus

La forme fermée suppose des coûts quadratiques et un signal par actif à
vitesse d'extinction connue, deux objets qu'une série de stratégie ne porte
pas.

## Les biais possibles

Non consultés.

## Nos décisions d'implémentation

`quantlab.execution.rebalancing.partial_rebalance` : la seule fraction
constante, sans l'escompte des signaux par leur vitesse.

## Nos écarts avec l'article

La forme simple à taux constant, choisie sur la fenêtre d'avant publication,
appliquée au momentum de série temporelle sur fonds cotés.

## Nos résultats

Étude 017 : le taux choisi avant publication, 0,5, rend après publication un
ratio de Sharpe net de 0,162 contre 0,176 pour le rééquilibrage complet ;
verdict `REJECTED`.

## Notre contrôle de robustesse

La grille entière des taux est publiée pour les deux fenêtres.

## Références

Gârleanu, N. et Pedersen, L. H. (2013). Dynamic Trading with Predictable
Returns and Transaction Costs. The Journal of Finance, 68(6), 2309-2340.

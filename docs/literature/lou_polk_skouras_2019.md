# A tug of war: overnight versus intraday expected returns

| | |
|---|---|
| **Auteurs** | Dong Lou, Christopher Polk, Spyros Skouras |
| **Année** | 2019 |
| **Revue ou source** | Journal of Financial Economics, vol. 134, no 1, p. 192-213 |
| **Lien** | Résumé lu le 2026-09-03 ; version d'auteur sur le site de la London School of Economics ; l'article n'a pas été lu en entier |
| **Statut de réplication** | lecture reprise dans l'étude 018, sur fonds cotés |

Ce que cette fiche porte vient du résumé de l'article, statut **rapporté**.

## La question de recherche

Le rendement d'une stratégie se gagne-t-il pendant que le marché est ouvert,
ou pendant qu'il est fermé ?

En mots simples : gagne-t-on la nuit ou le jour ?

## L'intuition économique

Des investisseurs différents négocient à l'ouverture et pendant la séance, et
leurs demandes tirent les prix dans des sens opposés. Le rendement de
clôture à clôture mélange les deux, et une stratégie qui gagne en moyenne peut
gagner la nuit et perdre le jour.

## Les données

Actions américaines, ouvertures et clôtures quotidiennes. Non consulté au-delà.

## L'univers

Voir les données.

## La méthodologie

Le rendement de clôture à clôture est coupé en une part de nuit, de la
clôture à l'ouverture suivante, et une part de journée, de l'ouverture à la
clôture. Quatorze stratégies sont mesurées sur chaque part.

## Les équations qui comptent

Les deux parts se composent en le rendement total, voir
`quantlab.analytics.returns.overnight_intraday_split`.

## Les résultats originaux

Rapportés, résumé. Sur quatorze stratégies, le profit se gagne soit
entièrement la nuit, renversement et momentum, soit entièrement le jour,
valeur, rentabilité et investissement. Les signes sont opposés d'une période
à l'autre. Au niveau du titre, la part de nuit et la part de journée se
continuent chacune, et un renversement croisé dure des années.

## Les critiques connues

Non consultées.

## Les problèmes de réplication connus

L'ouverture officielle est le prix de l'enchère d'ouverture, et sa qualité
varie avec l'époque et la place ; l'ouverture d'un fonds coté n'est pas celle
de ses titres.

## Les biais possibles

Non consultés.

## Nos décisions d'implémentation

Ouverture ajustée par le facteur de la clôture, parts composées, fonds cotés
au lieu d'actions.

## Nos écarts avec l'article

Fonds cotés, une stratégie de laboratoire et cinq fonds de facteurs au lieu
de quatorze stratégies sur actions.

## Nos résultats

Étude 018.

## Notre contrôle de robustesse

Étude 018.

## Références

Lou, D., Polk, C. et Skouras, S. (2019). A Tug of War: Overnight versus
Intraday Expected Returns. Journal of Financial Economics, 134(1), 192-213.

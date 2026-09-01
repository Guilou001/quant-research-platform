# 2026-09-01 : ce que le point-in-time change, mesuré sur un vrai déposant

## Question

De combien la donnée fondamentale d'aujourd'hui diffère-t-elle de celle qui
était connaissable à l'époque ?

La règle point-in-time coûte cher. Elle oblige à garder toutes les déclarations
d'une même période, à porter quatre dates par observation, et à retarder l'entrée
de l'information. La question est de savoir si ce coût achète quelque chose de
mesurable, ou s'il protège contre un risque théorique.

## Hypothèse

Les corrections de comptes sont rares et petites, donc le point-in-time change
peu de chose sur un grand déposant suivi de près.

## Expérience

Le module `quantlab.data.providers.sec` a été lancé sur les données XBRL réelles
d'Apple (CIK 0000320193), balise `Assets`, taxonomie `us-gaap`, unité USD, le
2026-09-01. Le fichier `companyfacts` reçu pèse 4 195 471 caractères. La
conversion en point-in-time rend 146 lignes couvrant 70 fins de période.

Pour chaque période, l'écart a été calculé entre la PREMIÈRE valeur déclarée et
la DERNIÈRE, avec leurs dates de disponibilité respectives.

## Résultat

L'hypothèse est fausse sur son second membre. Les corrections sont bien rares,
mais elles ne sont pas petites.

| Fin de période | Première valeur | Disponible le | Dernière valeur | Disponible le | Écart |
|---|---:|---|---:|---|---:|
| 2009-09-26 | 53,851 G$ | 2009-10-27 | 47,501 G$ | 2011-10-26 | **-11,79 %** |
| 2008-09-27 | 39,572 G$ | 2009-07-22 | 36,171 G$ | 2010-10-27 | **-8,59 %** |
| 2015-09-26 | 290,479 G$ | 2015-10-28 | 290,345 G$ | 2016-10-26 | -0,05 % |

Comment lire ce tableau, en trois constats. Le premier est que trois périodes
sur soixante-dix portent une valeur révisée, soit 4 % des périodes. Le deuxième
est que les deux plus grandes révisions dépassent huit points de pourcentage,
ce qui n'est pas un arrondi mais un changement de nature de la donnée. Le
troisième est que le délai est long : la valeur du 2009-09-26 a été corrigée
deux ans plus tard, le 2011-10-26.

Dix-huit périodes sur soixante-dix sont déclarées plusieurs fois sans que la
valeur change, ce qui est le cas ordinaire d'un chiffre repris d'un trimestre à
l'autre dans un dépôt ultérieur.

Le comportement de `PITFrame.as_of` a été vérifié sur ce cas :

| Date de décision | Actifs du 2008-09-27 rendus |
|---|---:|
| 2009-09-30 | 39,572 G$ |
| 2010-06-30 | 36,171 G$ |
| 2015-06-30 | 36,171 G$ |

Tous ces chiffres sont **mesurés** le 2026-09-01.

## Décision

La règle point-in-time est conservée telle quelle, et le coût de conserver
toutes les déclarations est justifié par ces trois lignes.

Le chiffre à retenir est celui-ci. Prenons une stratégie qui trie les entreprises sur leur actif au premier
trimestre 2010. Nourrie des données d'aujourd'hui, elle travaille sur Apple avec
un actif inférieur de 11,8 % à celui que le marché voyait alors. L'écart n'est pas du bruit ; il va dans un
seul sens et il concerne l'exercice qui suit une crise, c'est-à-dire le moment
où un tri sur le bilan compte le plus.

La cause n'a pas été cherchée dans les dépôts eux-mêmes et n'est donc **pas
établie ici**. Le calendrier des deux révisions, entre 2010 et 2011, coïncide
avec la période d'adoption rétrospective des règles de comptabilisation du
chiffre d'affaires par plusieurs déposants du secteur, mais ce lien reste **non
vérifié**.

## Question suivante

Sur plusieurs centaines de déposants plutôt qu'un seul, quelle part des
périodes porte une révision de plus de cinq points de pourcentage ? Et cette
part est-elle plus forte pour les entreprises en difficulté, c'est-à-dire
précisément celles qu'un tri sur la valeur achète ?

# Notes de l'étude 010

## Ce qui a été décidé avant de voir un chiffre

Le capital de référence est cent millions de dollars. Le coefficient d'impact
vaut un, le plafond de participation dix pour cent du volume quotidien, les
fenêtres de volume et de volatilité vingt et une séances. L'hypothèse tient si,
au capital de référence, le ratio de Sharpe net garde la moitié de sa valeur à
taille nulle ET reste au-dessus de 0,5. Huit essais sont déclarés : un cas de
base, deux coefficients et une durée d'exécution, pour deux stratégies.

## Ce qui a surpris

Le momentum de série temporelle sur fonds cotés n'a pas de capacité au sens du
modèle, et ce n'est pas l'impact qui le dit, c'est la participation. À un
million de dollars, un rééquilibrage sur quatre demande déjà plus de dix pour
cent du volume quotidien d'un fonds ; à cent millions, 99 sur 100. Les fonds
qui bornent sont les fonds de devises, FXF, FXA, FXB et FXY, et l'obligataire
court SHY. La cause est double : la cible de 40 % de volatilité par position
fait porter plusieurs fois le capital sur un fonds de devises qui bouge de 8 %
par an, et ces fonds s'échangent quelques millions de dollars par séance. Les
contrats à terme de l'article n'ont pas ce défaut ; les substituts cotés l'ont.

L'arbitrage statistique a une capacité nulle avant tout impact. Sur 1996-2026,
le brut moyen ne couvre pas les cinq points de base de demi-écart que l'article
suppose, ce que l'étude 007 avait déjà mesuré par son coût de seuil de 3,92
points de base. L'impact n'a plus rien à tuer. À un million de dollars il
retire quand même 9,3 % par an, parce que la stratégie tourne 344 fois son
capital par an.

## Les essais ratés

Une première version inversait le sens de l'écrêtage : elle affirmait que le
capital d'annulation de forme fermée était un majorant de la capacité quand la
participation dépasse le plafond. C'est le contraire. Écrêter minore le coût,
donc le net que le moteur rend au capital d'annulation est POSITIF, pas
négatif, et le test écrit avant le code l'a attrapé. La capacité retenue est
désormais le capital où le plafond est atteint.

La première exécution sur l'arbitrage statistique a levé une erreur de données
au 2018-12-12 sur Aetna. Le titre est sorti de la cote fin novembre 2018, Yahoo
lui garde des cotations fantômes à volume nul pendant deux semaines, et la
stratégie solde encore sa position. Deux corrections déclarées : les fenêtres
de volume et de volatilité exigent quinze séances valides sur vingt et une, et
un titre sans volume à la date de sa vente emprunte son dernier volume connu.
Cet emprunt a servi sur 0,55 % des rééquilibrages, et le nombre est publié.

La borne par le plafond est un maximum sur tous les rééquilibrages, donc une
seule transaction extrême la fixe. Passer de vingt et une à quinze séances
valides a déplacé la borne du momentum de 424 702 à 84 940 dollars, parce
qu'un volume des premières semaines d'un fonds nouvellement coté devient
lisible. La colonne « part des rééquilibrages écrêtés » de la table de capacité
est la lecture robuste, et c'est elle que le README met en avant.

## Ce qui reste ouvert

Refaire l'arbitrage statistique sur la seule fenêtre de l'article, 1997-2007,
où le brut couvrait les coûts, pour mesurer une capacité qui n'est pas nulle
par construction. Et remplacer les fonds de devises par des contrats à terme
dès qu'une source gratuite de volumes existe, ce qui n'est pas le cas.

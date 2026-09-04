# 2026-09-04 : la porte de Polygon, ouverte sur le référentiel, fermée sur les prix

## Question

La feuille de route mettait en premier l'univers sans biais de survie, et la
spécification 001 exigeait de mesurer le forfait avant d'écrire une ligne. Que
rend la clé gratuite de Guillaume ?

## Hypothèse

Écrite dans la configuration de l'étude 015 : le forfait gratuit donne les
prix quotidiens depuis 1996, sociétés radiées comprises.

## Expérience

Le fournisseur `quantlab.data.providers.polygon`, clé lue hors du code et
jamais écrite au cache, deux sondes de prix, le référentiel en 36 pages à
treize secondes chacune.

## Résultat

| Mesure | Valeur |
|---|---:|
| Première barre quotidienne d'AAPL sur le forfait gratuit | 2024-09-04 |
| Lehman Brothers en 2008 | 403, « plan doesn't include this data timeframe » |
| Actions ordinaires radiées datées dans le référentiel | 6 425 depuis 2004 |
| Part des actions ordinaires de 2014 encore cotées en 2026 | 51 % |

Statut mesuré le 2026-09-04. Verdict `REJECTED` pour l'hypothèse, et un
sous-produit qui vaut l'étude : le référentiel chiffre le biais de survie sur
le marché entier, ce qu'aucune source libre du dépôt ne faisait.

## Décision

Le fournisseur reste, parce que le référentiel sert et parce que deux ans de
prix sans biais de survie suffisent à des tests courts. Les prix anciens des
titres radiés sont la première dépense de données qui aurait un sens, et la
feuille de route le dit.

## Question suivante

Les chantiers 5 et 6, qui n'ont pas cette dépendance.

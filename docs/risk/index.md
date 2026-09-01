# Le moteur de risque

**Non implémenté au 2026-09-01.** C'est la phase 5 de la feuille de route.

La variance n'épuise pas le risque, et la phase 5 le prend au sérieux.

Le moteur portera la covariance et ses estimateurs concurrents, les
contributions au risque par actif, facteur, secteur et stratégie, le risque de
queue, les corrélations en régime de tension, et les limites d'exposition.

Deux briques existent déjà et servent de fondation :
`quantlab.analytics.contributions` pour la décomposition exacte par le théorème
d'Euler, et `quantlab.analytics.risk` pour la valeur à risque, la perte espérée
et la correction d'annualisation de Lo (2002).

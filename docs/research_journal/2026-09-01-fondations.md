# 2026-09-01 : le socle technique et l'état réel des sources

## Question

Quelles versions et quelles sources de données sont réellement disponibles
aujourd'hui, plutôt que celles qu'on suppose disponibles ?

La tension est la suivante. Une pile technique se choisit sur des API dont on
croit connaître la forme, et ces API changent. Une source de données se choisit
sur une réputation, et son accès varie d'un jour à l'autre depuis un réseau
donné. Les deux erreurs coûtent cher plus tard, quand le code est écrit.

## Hypothèse

Le socle prévu (Python 3.12, Polars, DuckDB, pandas 3, skfolio, VectorBT) tient
sans conflit, et les sources gratuites prévues répondent.

## Expérience

Deux mesures, faites avant d'écrire une ligne de code métier.

D'abord, interrogation de l'API JSON de PyPI pour trente-neuf paquets, puis
installation réelle dans un environnement neuf et introspection des signatures
par `inspect.signature`.

Ensuite, requêtes HTTP sur sept sources de données avec un en-tête
d'identification.

## Résultat

**Un conflit dur, mesuré.** `import vectorbt` échoue avec Plotly 7.0.0 :
VectorBT 1.1.0 enregistre un gabarit contenant une trace `scattermapbox` que
Plotly 7 a retirée. La borne haute a été cherchée en installant quatre versions
successives, et non supposée : Plotly 5.24.1, 6.0.1, 6.3.1 et 6.5.0 passent,
7.0.0 échoue. Décision consignée en
[ADR-006](../architecture/adr/adr-006-plotly-borne.md).

**Les signatures utiles, vérifiées.** `skfolio` 1.0.3 expose bien
`CombinatorialPurgedCV(n_folds=10, n_test_folds=8, purged_size=0, embargo_size=0)`
et `WalkForward(test_size, train_size, ..., purged_size=0)`, plus
`optimal_folds_number`. Mesuré, non supposé.

**La SEC répond.** Le 2026-08-29, tout le domaine `sec.gov` renvoyait 403
« Request Rate Threshold Exceeded » depuis cet environnement, sur sept relances
en vingt minutes. Le 2026-09-01, trois points d'entrée testés répondent 200 avec
le même en-tête : `companyconcept`, `submissions` et l'index complet des dépôts.
Le blocage était un débit, pas une politique.

**Les six autres sources répondent.** Ken French (fichier quotidien des trois
facteurs, 177 852 octets), FRED en CSV sans clé (première observation de DGS10 :
1962-01-02 à 4,06), ALFRED avec millésime, AQR, et le dépôt Open Source Asset
Pricing.

**Le calendrier, mesuré.** La Bourse de New York a ouvert 2 516 fois entre le
1er janvier 2010 et le 31 décembre 2019, soit 251,703 séances par an sur
9,996 année. L'écart avec la convention de 252 déplace une volatilité annualisée
de 0,059 % en valeur relative.

Tous ces chiffres sont **mesurés** le 2026-09-01.

## Décision

Le socle est retenu tel quel, avec Plotly borné sous la version 7 et la
condition de levée écrite. La SEC entre dans les sources prévues, ce qui rend
possible la construction de fondamentaux point-in-time.

La conclusion de méthode dépasse ce cas. Un blocage réseau constaté un jour ne
se conclut pas en indisponibilité permanente d'une source. Il vaut la peine de
reprendre la mesure avant d'abandonner une fiche.

## Question suivante

Combien de temps prend la construction du panel point-in-time des fondamentaux
SEC à l'échelle de plusieurs centaines d'entreprises, et la limite de dix
requêtes par seconde est-elle le goulot ?

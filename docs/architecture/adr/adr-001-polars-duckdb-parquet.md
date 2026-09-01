# ADR-001 : le lac parle Parquet, DuckDB et Polars, l'analytique parle pandas

**Statut** : acceptée le 2026-09-01.

## Contexte

Deux besoins tirent dans des directions opposées. Le stockage veut un format
colonnaire compressé, typé, lisible sans tout charger en mémoire, et
interrogeable en SQL. Le calcul financier veut un objet indexé par le temps que
`statsmodels`, `arch`, `scipy` et `skfolio` acceptent directement, c'est-à-dire
du pandas.

Choisir une seule technologie oblige à payer l'autre besoin. Tout en pandas
donne un lac lent et lourd ; tout en Polars oblige à convertir avant chaque
régression, et une conversion par appel dans une boucle de backtest coûte plus
que le calcul lui-même.

## Décision

La frontière est posée à la sortie de la couche *gold*, et elle est unique.

- En amont de cette frontière, le lac stocke en **Parquet**, interroge en
  **DuckDB** et transforme en **Polars**.
- En aval, tout est du **pandas indexé par un `DatetimeIndex`**.
- Une seule fonction traverse la frontière, `quantlab.data.lake.to_analytics`.
  Elle trie l'index, refuse les doublons et fixe le fuseau.

Aucun module d'analytique n'importe Polars. Aucun module de lac ne rend du
pandas hors de cette fonction.

## Conséquences

Le coût de conversion est payé une fois par jeu de données et non une fois par
calcul. Le test qui garde cette règle est simple à écrire : aucun module sous
`quantlab/analytics/` ne doit importer `polars`.

En contrepartie, un jeu qui ne tient pas en mémoire ne peut pas franchir la
frontière. Les traitements sur des données plus grosses que la mémoire vive
restent en SQL DuckDB, en amont, et c'est une contrainte assumée. Les études
prévues à ce jour tiennent largement dans quelques gigaoctets.

## Options écartées

**Tout en pandas.** Rejetée pour la lecture : DuckDB lit une colonne d'un
Parquet de plusieurs gigaoctets sans charger le reste, ce que pandas ne sait pas
faire sans lecture partielle explicite. Le lac deviendrait le goulot.

**Tout en Polars.** Rejetée pour l'écosystème : `statsmodels`, `arch` et
`skfolio` prennent du pandas, et les convertir à chaque appel annule le gain.
Cette contrainte est mesurée, non supposée : les trois bibliothèques ont été
installées et leurs signatures inspectées le 2026-09-01.

**Une couche d'abstraction sur les deux.** Rejetée pour le coût : écrire un
tableau générique qui cache pandas et Polars revient à réécrire les deux, et la
fuite d'abstraction arrive au premier appel avancé.

# 2026-09-03 : rendre visible ce qui existe, sans rien retaper

## Question

Le laboratoire porte onze verdicts, trente-neuf séries et deux comparaisons
aux fonds réels, tous dans des fichiers séparés. Un lecteur extérieur, un
recruteur par exemple, ne peut pas en prendre connaissance en moins d'une
heure. Et un résumé écrit à la main divergerait des fichiers à la prochaine
exécution, ce que les audits du portefeuille ont mesuré ailleurs.

## Hypothèse

Une page et un PDF entièrement engendrés depuis les fichiers du dépôt, sans
un seul chiffre retapé, suffisent à présenter le laboratoire d'un seul écran,
et leur construction tient en une commande.

## Expérience

Le module `quantlab.reporting.dashboard` et la configuration
`configs/dashboard.yaml` (ADR-014). La commande `quant dashboard build` lit
les configurations, les métriques, les séries, les comparaisons et le
registre, écrit `docs/dashboard/index.md` et huit figures. La commande
`quant report` compile la même page en `rapport/rapport.pdf` par le
générateur de `gv-fintools`. Les commandes `backtest` et `portfolio` de la
ligne de commande, coquilles depuis la phase 0, sont écrites. Un CSV de poids
et un CSV de rendements donnent un résumé ; un CSV de rendements et un
optimiseur donnent des poids.

## Résultat

Mesuré le 2026-09-03 sur le dépôt : 11 études, 760 essais déclarés, 128
expériences au registre, 2 413 fonctions de test, 12 séries sur le tableau
de risque, 8 figures. La page passe les gardiens de style, le site se
construit en mode strict, et le PDF fait 1,0 Mo.

Deux défauts trouvés par la construction elle-même. Le compte d'essais de
l'étude 002 n'est pas au premier niveau de sa configuration, il vit sous une
section. La page l'a lu à zéro jusqu'à ce que la table de `studies/README.md`
serve de repli. Et le titre des études 010 et 011 lu dans
leur README est une question de plus de dix mots ; la table des études porte
un titre court, et c'est lui qui est repris.

## Décision

La phase 10 est close. Le tableau se régénère après chaque étude, par la
commande, et jamais à la main.

## Question suivante

Les dettes 1 et 2 : reporter le taux FRED absent d'avril 2020 et relancer les
études 008 et 009, puis refaire le portefeuille sur les séries nettes.

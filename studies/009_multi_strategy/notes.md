# Notes de l'étude 009

## Ce qui a été décidé avant de voir un chiffre

La référence est la parité de risque. Le holdout commence au 2020-01-31. Les
seuils du verdict sont ceux de `config.yaml`, écrits le 2026-09-02 avant le
premier chargement. Vingt essais sont déclarés.

## Ce qui a surpris

La parité hiérarchique domine tout, Sharpe 0,916 contre 0,646 pour la
référence, repli de -4,3 % contre -7,7 %, holdout 0,611 contre 0,214. La
tentation de la retenir est forte, et c'est précisément le geste interdit : six
allocations ont été essayées, et prendre la meilleure après coup revient à
sélectionner sur le résultat. Le Sharpe dégonflé à vingt essais, 0,410, dit ce
que vaut cette sélection.

Deux stratégies retirent du Sharpe au portefeuille, la gestion de volatilité
pour -0,175 et le bêta défensif pour -0,060. Les deux sont `REJECTED` dans leur
propre étude, et le portefeuille le confirme par un autre chemin.

## Les essais ratés

Une première exécution a échoué sur une clé `name` dans un `extra` de journal,
réservée par `logging.LogRecord`. Le bogue était latent dans
`quantlab.experiments.registry` depuis la phase 0 et n'avait jamais été
déclenché, les études précédentes tournant sous un autre niveau de journal. Il
est corrigé dans tout le paquet.

La première version ne mesurait pas le multiple de coûts survécu, ce qui
comptait un critère comme échoué faute de mesure. Cinq multiples ont été
ajoutés, de un à vingt, et le compte d'essais est passé de quinze à vingt.

## Ce qui reste ouvert

Refaire l'étude avec les séries NETTES de chaque stratégie, ce qui exige que
les huit études enregistrent une version nette comparable. Et refaire la
comparaison à QSPIX avec la parité hiérarchique, non pour changer la référence,
mais pour savoir si le fonds d'AQR lui ressemble davantage.

## Relance du 2026-09-03

La série de portage de change de l'étude 008 a retrouvé son avril 2020, et
l'étude a été relancée sans autre changement : 234 mois communs au lieu de
233, 199 mois hors échantillon au lieu de 198. Trente-six métriques sur
quarante-deux ont bougé, dont la meilleure jambe seule, 0,721 au lieu de
0,693, et la référence, 0,646 au lieu de 0,652. Trois allocations sur six
battent désormais la meilleure jambe au lieu de quatre, et le verdict est
inchangé. Les chiffres du README sont ceux de cette relance.

# ADR-014 : le tableau de bord et le rapport se génèrent depuis les fichiers, jamais à la main

**Statut** : acceptée le 2026-09-03, phase 10.

## Contexte

Onze études, trente-neuf séries enregistrées, deux registres de comparaison et
un registre d'expériences vivent dans des fichiers séparés. Un lecteur qui
arrive ne peut pas voir d'un seul écran ce que le laboratoire a établi. Le
portefeuille a déjà mesuré, lors de ses audits, que les chiffres retapés dans
un README divergent des fichiers de résultats dès la relance suivante. Un
seul contrôle sur les autres dépôts a trouvé 87 écarts.

## Décision

La page `docs/dashboard/index.md`, ses figures et le PDF `rapport/rapport.pdf`
ne s'écrivent jamais à la main. La commande `quant dashboard build` les
engendre depuis quatre sources : les configurations et les métriques des
études, les séries enregistrées par `quantlab.reporting.series`, les fichiers
de comparaison de `benchmarks/results/` et le registre `artifacts/experiments.jsonl`.
La page nomme sa source sous chaque tableau. `quant report` compile la même
page en PDF par le générateur de rapport de `gv-fintools`, avec le gabarit
commun du portefeuille.

Ce que le tableau montre se déclare dans `configs/dashboard.yaml` : une série
de tête par étude, les portefeuilles, la fenêtre commune des figures, les
fichiers de comparaison repris. Changer ce qui est montré est un changement de
configuration, versionné, pas une édition de page.

Les phrases de résultat d'une ligne viennent de `studies/README.md`, seul
endroit où elles sont écrites. Les titres et les comptes d'essais viennent de
la même table, avec la configuration de chaque étude qui prime quand elle les
porte.

## Conséquences

La page se régénère après chaque étude, et elle ne peut pas contredire les
fichiers. Le prix est une page dont la prose est fixée dans le code du module,
donc courte. Elle ne porte aucune interprétation nouvelle : l'interprétation
vit dans les README des études et dans le journal.

Les figures et la page sont suivies par git, parce qu'elles sont le produit
visible du dépôt ; le registre d'expériences ne l'est pas, et la page le dit.

## Options écartées

**Un tableau de bord interactif servi par une application.** Rejeté : un
serveur à maintenir, des dépendances de plus, et rien qu'une page statique ne
montre pas déjà pour onze études.

**Écrire la page à la main et la relire.** Rejeté par la mesure citée en
contexte.

**Un rapport PDF distinct de la page.** Rejeté : une seule source, deux formes,
aucune divergence possible, la règle déjà appliquée aux vingt-quatre autres
dépôts du portefeuille.

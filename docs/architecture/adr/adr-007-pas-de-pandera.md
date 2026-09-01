# ADR-007 : les contrats de données sont écrits à la main, sans Pandera

**Statut** : acceptée le 2026-09-01.

## Contexte

Les données doivent être contrôlées avant usage : colonnes attendues, types,
bornes, absence de doublon, cohérence des barres de prix. Pandera est la
bibliothèque de référence pour déclarer ces contrats en Python.

Trois faits pèsent contre son adoption ici. Le premier est que la moitié de nos
contrôles ne sont pas des contraintes de schéma mais des contrôles financiers.
Détecter une division non ajustée, comparer les dates présentes aux séances
réelles d'un calendrier d'échange, repérer un prix figé plusieurs séances. Rien
de cela ne s'exprime naturellement dans un schéma déclaratif.

Le deuxième est que nous manipulons pandas ET Polars, et qu'un contrat écrit
pour l'un ne vaut pas pour l'autre.

Le troisième est la dépendance elle-même. Pandera 0.33.1 suit pandas de près, et
pandas 3.0 est récent.

## Décision

Les contrôles vivent dans `quantlab.data.quality.checks`, écrits comme des
fonctions pures rendant un `CheckResult` gelé, avec un nom, un verdict, une
gravité, le nombre de violations, un échantillon des lignes fautives et un
message en français.

`run_checks` les agrège en un `QualityReport`, et `raise_if_failed` lève
`DataQualityError` au niveau de gravité choisi.

Chaque contrôle documente ce qu'il attrape **et ce qu'il laisse passer**. Un
contrôle dont on croit qu'il attrape plus qu'il n'attrape est pire que pas de
contrôle du tout.

## Conséquences

Le code de contrôle est à écrire et à tester nous-mêmes, ce qui coûte quelques
centaines de lignes. En échange, un contrôle financier s'ajoute sans se battre
contre un cadre déclaratif, et le rapport est le nôtre.

La décision se révise sans douleur : un `CheckResult` peut être produit par
Pandera aussi bien que par notre code, l'interface étant la seule chose que le
reste du projet connaît.

## Options écartées

**Pandera pour le schéma, notre code pour le reste.** Rejetée pour la double
mécanique : deux façons de déclarer un contrôle, deux formats de rapport, et un
lecteur qui doit connaître les deux.

**Aucun contrôle, confiance dans la source.** Rejetée : Yahoo rend des prix
ajustés recalculés à chaque dividende, et une division non traitée produit un
rendement de plusieurs centaines de pour cent qui traverse tout le pipeline sans
bruit.

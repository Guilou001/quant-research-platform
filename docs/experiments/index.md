# Le registre des expériences

**Implémenté.**

Le registre existe déjà et tourne : `quantlab.experiments.registry`.

Il écrit un répertoire par expérience sous `artifacts/`, plus un index en JSON
par ligne que DuckDB lit comme une table. Chaque expérience porte l'empreinte du
commit, la configuration, la graine et les versions des dépendances. Puis les
empreintes des jeux de données, la période, l'univers, les hypothèses de coût,
les métriques avec leur étiquette d'échantillon, et le verdict.

Deux champs servent directement au calcul plutôt qu'à la mémoire.
`n_trials` alimente le ratio de Sharpe dégonflé, qui a besoin de savoir combien
d'essais ont été menés. `holdout_reads` compte les consultations du holdout
final, et ce nombre se publie à côté du résultat : après lecture, le holdout
n'est plus hors échantillon.

```bash
uv run quant experiments list
uv run quant experiments show <identifiant>
uv run quant experiments trials tsmom
```

Le raisonnement derrière le choix d'un fichier plutôt que d'un serveur vit dans
[ADR-009](../architecture/adr/adr-009-registre-experiences.md).

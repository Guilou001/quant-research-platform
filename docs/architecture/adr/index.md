# Les décisions d'architecture

Une décision d'architecture est une décision qu'on ne prendra pas deux fois, et
dont le coût de retour arrière croît avec le temps. Elle s'écrit donc au moment
où elle est prise, avec ce qu'on savait alors, et non reconstituée après coup.

Chaque fiche suit le même gabarit : le contexte, la décision, le statut, les
conséquences acceptées, et les options écartées avec la raison de leur rejet.
Une décision sans option écartée n'est pas une décision, c'est une habitude.

| Numéro | Décision | Statut | Date |
|---|---|---|---|
| [ADR-001](adr-001-polars-duckdb-parquet.md) | Le lac parle Parquet, DuckDB et Polars, l'analytique parle pandas | Acceptée | 2026-09-01 |
| [ADR-002](adr-002-monorepo.md) | Un dépôt unique, des études autonomes à l'intérieur | Acceptée | 2026-09-01 |
| [ADR-003](adr-003-protocoles.md) | Les briques se parlent par protocoles structurels, jamais par imports concrets | Acceptée | 2026-09-01 |
| [ADR-004](adr-004-point-in-time.md) | Quatre dates par observation fondamentale, et une seule gouverne l'accès | Acceptée | 2026-09-01 |
| [ADR-005](adr-005-quatre-etages-du-lac.md) | Quatre étages de données, chacun avec une règle qui ne se négocie pas | Acceptée | 2026-09-01 |
| [ADR-006](adr-006-plotly-borne.md) | Plotly borné sous la version 7 tant que VectorBT ne suit pas | Acceptée | 2026-09-01 |
| [ADR-007](adr-007-pas-de-pandera.md) | Les contrats de données sont écrits à la main, sans Pandera | Acceptée | 2026-09-01 |
| [ADR-008](adr-008-deux-moteurs-de-backtest.md) | Deux moteurs de backtest indépendants, et la réconciliation est un livrable | Acceptée | 2026-09-01 |
| [ADR-009](adr-009-registre-experiences.md) | Le registre d'expériences est un fichier, pas un serveur | Acceptée | 2026-09-01 |
| [ADR-010](adr-010-francais-code-anglais.md) | La prose est en français, le code en anglais | Acceptée | 2026-09-01 |
| [ADR-011](adr-011-skfolio-moteur-de-portefeuille.md) | skfolio est le moteur d'optimisation, derrière nos protocoles | Acceptée | 2026-09-02 |
| [ADR-012](adr-012-capacite-par-forme-fermee.md) | La capacité se mesure en rejouant les poids à plusieurs tailles, et une forme fermée contrôle le moteur | Acceptée | 2026-09-02 |
| [ADR-013](adr-013-scikit-learn-derriere-les-modeles.md) | scikit-learn est le moteur d'apprentissage, derrière le protocole AlphaModel | Acceptée | 2026-09-02 |
| [ADR-014](adr-014-tableau-de-bord-engendre.md) | Le tableau de bord et le rapport se génèrent depuis les fichiers, jamais à la main | Acceptée | 2026-09-03 |

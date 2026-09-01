# quant-research-platform, règles du laboratoire

Ce fichier gouverne toute contribution, humaine ou assistée. Il l'emporte sur les
habitudes ; en cas de conflit avec un fichier de plus haut niveau, la règle la
plus stricte gagne. Les quinze règles ci-dessous ne sont pas des préférences de
style : chacune ferme une porte par laquelle un résultat faux est déjà entré
dans un laboratoire quantitatif.

## Les quinze règles

**Règle 1. Aucune information future dans une donnée historique.**
Un rapport accepté par la SEC le 15 mai n'est pas connaissable le 31 mars, même
s'il décrit le trimestre clos le 31 mars. Toute donnée fondamentale porte
`period_end`, `filing_date`, `accepted_timestamp` et `available_from`, et seul
le dernier gouverne l'accès. La violation lève `LookAheadError` et arrête le
pipeline.

**Règle 2. Aucune définition mathématique ne change en silence.**
Modifier la convention d'un turnover, d'un rendement ou d'une annualisation
exige de modifier la docstring, le test, et le journal de recherche dans le même
commit.

**Règle 3. Toute formule importante est documentée.**
Problème, intuition, formule, définition de chaque variable, hypothèses,
provenance académique, limites, alternatives, raison du choix, façon de vérifier
que l'implémentation est correcte. Dix points, pas neuf.

**Règle 4. Toute stratégie cite son origine.**
Auteurs, année, source. Une stratégie sans provenance est une stratégie qu'on ne
peut pas contredire.

**Règle 5. Tout chiffre de performance porte son étiquette.**
Échantillon (`IS` / `VALIDATION` / `OOS` / `FINAL_HOLDOUT`), brut ou net,
hypothèses de coût, période, univers. Un ratio de Sharpe sans ces cinq mentions
ne se publie pas.

**Règle 6. Aucun paramètre ne s'optimise sur le holdout final.**
Le nombre de consultations du holdout est compté et publié. Après lecture, il
n'est plus hors échantillon, et le registre le dit.

**Règle 7. Un bon backtest ne prouve rien sur l'avenir.**
Le vocabulaire suit : « mesuré sur telle période », jamais « la stratégie
rapporte ».

**Règle 8. Aucune expérience ratée n'est cachée.**
`docs/research_journal/rejected_ideas.md` reçoit les échecs. Le nombre d'essais
entre dans le calcul du ratio de Sharpe dégonflé ; les cacher fausse le test
qui sert précisément à détecter le surapprentissage.

**Règle 9. Un modèle complexe doit battre un modèle simple après coûts et hors
échantillon.** Sinon, on garde le simple. La complexité est un coût.

**Règle 10. Les tests tournent après chaque implémentation qui compte.**
Un test dont la valeur attendue vient de la sortie du code verrouille le bogue
au lieu de l'attraper. La valeur attendue vient donc d'une source indépendante,
d'un calcul à la main, ou d'une propriété mathématique.

**Règle 11. Aucun carnet ne porte de logique métier.**
Un carnet importe depuis `src/`, explique et trace. Il n'implémente pas.

**Règle 12. Aucune métrique financière n'est implémentée deux fois.**
Le ratio de Sharpe vit dans `quantlab.analytics.ratios` et nulle part ailleurs.

**Règle 13. Aucune constante magique.**
Un nombre qui décide de quelque chose vit dans une configuration validée.

**Règle 14. Le calcul est déterministe.**
Une graine par expérience, propagée explicitement. Les graines dérivées passent
par `SeedSequence.spawn`, jamais par `seed + i`.

**Règle 15. Toute décision d'architecture est écrite.**
Un ADR dans `docs/architecture/adr/`, numéroté, daté, avec ses conséquences.

## Conventions d'écriture

- **Français d'abord**, résumé anglais dans le README principal. Le code, les
  noms de modules, de fonctions et de variables sont en anglais ; les
  docstrings, les commentaires et la documentation sont en français.
- Le style suit `METHODE.md` du portefeuille : la réponse d'abord, pas de tiret
  cadratin, pas de ternaire fabriqué, aucune information absente comblée par une
  supposition. Une information non trouvée s'écrit « non trouvé ».
- Le statut de chaque chiffre se déclare : **mesuré**, **rapporté**,
  **précepte**, **modélisé**, **non trouvé**.

## Commandes

```bash
make install     # uv sync --all-extras --dev
make lint        # ruff format --check + ruff check
make test        # pytest hors réseau
make cov         # avec couverture
make docs        # mkdocs build --strict
```

## Ce qui existe, et ce qui n'existe pas

L'arborescence de `src/quantlab/` montre l'architecture entière. Les
sous-paquets non implémentés portent une docstring qui le dit et nomme leur
phase. Ne rien y écrire sans avoir lu `quantlab.core.protocols` : une brique qui
ne respecte pas son protocole n'est plus remplaçable, et c'est exactement ce que
l'architecture cherche à éviter.

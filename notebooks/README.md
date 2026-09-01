# Les carnets

Un carnet sert à trois choses : explorer, expliquer, montrer une figure. Il ne
porte aucune logique réutilisable.

La règle est mécanique. Si un bout de code d'un carnet mérite d'être appelé une
seconde fois, il monte dans `src/quantlab/` et le carnet l'importe :

```python
from quantlab.analytics.ratios import sharpe_ratio
from quantlab.validation.dsr import deflated_sharpe_ratio
```

et non huit cents lignes de logique cachée dans des cellules.

La raison est la reproductibilité. Un carnet s'exécute dans un ordre que rien ne
garantit, son état survit entre deux exécutions, et son résultat dépend de ce
qui a été lancé avant. Un module, lui, se teste.

`nbstripout` tourne en crochet de pré-commit et retire les sorties avant chaque
commit : un carnet versionné avec ses sorties rend le diff illisible et gonfle
le dépôt.

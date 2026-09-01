# Faire tourner sa première mesure

Cette page montre la chaîne complète sur le plus petit exemple possible :
charger des rendements, les mesurer, et vérifier que le chiffre obtenu est
défendable.

## Charger

```python
from quantlab.data.providers.french import FrenchProvider

provider = FrenchProvider()
factors = provider.benchmark_factors(frequency="monthly")
market = factors["Mkt-RF"]
rf = factors["RF"]
```

Le fournisseur écrit la réponse brute dans `data/raw/`, calcule son empreinte et
range le manifeste dans `metadata/manifests/`. La question « quelle donnée
exacte a produit ce résultat ? » a désormais une réponse.

## Mesurer

```python
from quantlab.analytics.ratios import sharpe_ratio, sharpe_standard_error
from quantlab.analytics.drawdown import max_drawdown
from quantlab.core.types import Frequency

sr = sharpe_ratio(market, frequency=Frequency.MONTHLY)
se = sharpe_standard_error(market, frequency=Frequency.MONTHLY)
dd = max_drawdown(market)
```

## Lire le résultat correctement

Trois réflexes, dans cet ordre.

**Le ratio de Sharpe seul ne dit rien.** Comparez-le à son erreur type. Un
Sharpe de 0,4 avec une erreur type de 0,3 est indiscernable de zéro, et
l'afficher sans son incertitude induit le lecteur en erreur.

**Le nombre d'essais compte.** Si ce chiffre est le meilleur de vingt variantes
essayées, il est biaisé vers le haut par construction. Le module
`quantlab.validation.dsr` dégonfle le ratio en conséquence, et il a besoin de
savoir combien d'essais ont eu lieu.

**L'échantillon et les coûts se déclarent.** Un chiffre du laboratoire porte
toujours son étiquette : `IS`, `VALIDATION`, `OOS` ou `FINAL_HOLDOUT`, et
`GROSS` ou `NET`. C'est la règle 5 du `CLAUDE.md`, et elle n'a pas d'exception.

## L'étape suivante

Une mesure n'est pas une étude. Une étude porte une hypothèse économique, une
réplication, des contrôles de robustesse et un verdict. Le parcours complet est
décrit dans [Le parcours d'une stratégie](../methodology/gauntlet.md).

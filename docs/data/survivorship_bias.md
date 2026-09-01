# Le biais de survie

Backtester une stratégie sur les membres actuels du S&P 500 utilise de
l'information future, et l'ampleur de l'erreur n'est pas marginale.

## Le mécanisme

Les entreprises qui composent l'indice aujourd'hui sont celles qui n'ont ni fait
faillite, ni été radiées, ni été absorbées après une chute. Les sélectionner
pour un test qui commence en 1990 revient à choisir les gagnants à l'avance.

Le biais frappe deux fois. Il gonfle le rendement moyen, parce que les pires
sorties manquent. Il réduit le risque mesuré, parce que les pires trajectoires
manquent aussi. Un ratio de Sharpe est donc surestimé à son numérateur et à son
dénominateur en même temps.

Il frappe plus fort sur certaines stratégies que sur d'autres. Une stratégie de
valeur achète les titres les moins chers, c'est-à-dire précisément la population
où les faillites se concentrent. Le biais de survie lui retire ses pires
positions.

## Ce que nous pouvons faire, et ce que nous ne pouvons pas

Les données gratuites ne portent pas d'univers point-in-time complet. Yahoo ne
rend pas les titres radiés ; l'appartenance historique aux indices n'est pas
publiée librement sous une forme exploitable.

Trois réponses, dans l'ordre de préférence.

**Un univers point-in-time quand il existe.** Les portefeuilles triés de Ken
French sont construits sur CRSP et incluent les titres radiés. Les facteurs de
Ken French sont donc exempts de biais de survie, et leur manifeste porte
`survivorship_free=True`.

**Un univers de fonds négociés en bourse.** Un FNB existe ou n'existe pas ; il
ne disparaît pas silencieusement de son propre historique. Les études
multi-actifs du laboratoire partent de là.

**Un marquage explicite.** Quand aucune des deux réponses ne s'applique, le
backtest porte le drapeau :

```
SURVIVORSHIP_BIAS_RISK = True
```

Les résultats concernés ne sont jamais présentés comme institutionnellement
propres. Ils ne peuvent pas atteindre le verdict `ROBUST`.

## Le champ à trois valeurs

Le manifeste porte `survivorship_free` avec trois valeurs possibles et non deux.

| Valeur | Ce qu'elle dit |
|---|---|
| `True` | vérifié, l'univers inclut les titres disparus |
| `False` | vérifié, l'univers ne les inclut pas |
| `None` | **non vérifié** |

`None` ne signifie pas « probablement bon ». Il signifie que personne n'a
regardé, et c'est une information que le lecteur d'un résultat doit avoir.

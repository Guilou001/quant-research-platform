# Le moteur d'analytique

Une métrique financière vit à un seul endroit dans ce dépôt. La règle vient
d'une expérience : quand le ratio de Sharpe existe en quatre exemplaires, il
finit par exister en quatre versions, et personne ne sait laquelle a produit le
chiffre publié.

## Ce que porte le moteur

| Module | Ce qu'il calcule |
|---|---|
| `returns` | rendements simples et logarithmiques, composition, rééchantillonnage, richesse cumulée, CAGR, rendements excédentaires |
| `risk` | volatilité, écart baissier, asymétrie, aplatissement, VaR, perte espérée, correction d'annualisation de Lo |
| `drawdown` | série de perte depuis le sommet, perte maximale, durée, temps de recouvrement, indice d'ulcère, CDaR |
| `ratios` | Sharpe et son erreur type, Sortino, Calmar, ratio d'information, Sharpe ajusté de l'asymétrie |
| `regression` | régression factorielle avec erreurs types HAC, bêta, bêta rétréci, résidualisation |
| `ic` | coefficient d'information, rendements par quantile, loi fondamentale et largeur effective |
| `turnover` | rotation avec poids dérivés, convention déclarée |
| `contributions` | volatilité du portefeuille, contribution marginale et contribution au risque |

## Trois conventions qui décident de tout

**Le signe de la perte.** La valeur à risque et la perte espérée s'expriment en
**perte positive**. Le drawdown s'exprime en valeurs **négatives**. Ces deux
conventions sont opposées, elles sont déclarées, et les tests les vérifient.

**L'annualisation.** Le numérateur d'un ratio s'annualise en \(N\), le
dénominateur en \(\sqrt{N}\). Le taux sans risque se soustrait **avant**
l'annualisation. Le facteur \(N\) vaut 252 par convention, et
`quantlab.core.calendars.sessions_per_year` sait le mesurer : la Bourse de New
York a ouvert 2 516 fois entre le 1er janvier 2010 et le 31 décembre 2019, soit
251,703 séances par an, mesuré le 2026-09-01.

**La rotation.** \(Turnover_t = \frac{1}{2}\sum_i |w_{i,t} - w_{i,t}^{\text{dérivé}}|\).
Les poids dérivés sont ceux vers lesquels le marché a fait glisser le
portefeuille. Comparer aux poids cibles au lieu des poids dérivés fait payer des
frais sur des transactions qui n'ont pas eu lieu.

## Pourquoi le ratio de Sharpe trompe

Cinq raisons, toutes documentées dans la docstring de `sharpe_ratio`.

1. **Il suppose l'indépendance temporelle.** Une autocorrélation positive,
   fréquente sur les actifs peu liquides, fait sous-estimer la volatilité
   annuelle et donc surestimer le ratio (Lo, 2002).
2. **Il ignore la forme de la distribution.** Deux séries de même moyenne et
   même écart type ont le même Sharpe, que l'une perde régulièrement un peu et
   l'autre rarement beaucoup.
3. **Il est biaisé vers le haut quand il est sélectionné.** Le meilleur de
   \(N\) essais dépasse mécaniquement sa vraie valeur, et l'écart croît avec
   \(N\).
4. **Il dépend du taux sans risque retenu**, et donc de la période.
5. **Il ne dit rien de la capacité.** Un Sharpe de 3 sur un million de dollars
   peut valoir 0,2 sur cent millions.

Le laboratoire rend donc toujours le ratio de Sharpe avec son erreur type, et
renvoie vers `quantlab.validation.dsr` dès qu'il y a eu sélection.

r"""Ne négocier qu'une partie du chemin vers la cible, la forme simple de Gârleanu et Pedersen.

**Le problème.** Un moteur qui saute à la cible à chaque rééquilibrage paie
toute la rotation que la cible demande. Une partie de cette rotation ne fait
que suivre le bruit du signal. L'étude
007 a mesuré qu'un arbitrage statistique meurt à 3,92 points de base. La
phase 9 a mesuré qu'une séance de retard coûte 71 points de base par an au
momentum. La rotation est le premier coût.

**L'intuition.** Gârleanu et Pedersen (2013) montrent qu'avec des coûts de
transaction quadratiques, la position optimale se rapproche de la cible d'une
fraction constante à chaque période au lieu de la rejoindre. On négocie moins,
on est en retard sur la cible, et l'échange vaut la peine quand le signal
persiste plus longtemps que le coût ne met à se rembourser.

**La formule.** Avec :math:`b_t` les poids dérivés à l'entrée de la période,
c'est-à-dire les poids détenus la veille poussés par les rendements de la
période, :math:`w^*_t` la cible et :math:`\theta` le taux de rapprochement,

.. math::

    h_t = b_t + \theta \left( w^*_t - b_t \right), \qquad 0 \le \theta \le 1

**Les variables.** :math:`h_t` les poids décidés, :math:`b_t` les poids dérivés
rendus par :func:`quantlab.analytics.turnover.drifted_weights`, :math:`w^*_t`
la cible de la stratégie, :math:`\theta` le taux, un à chaque période pour le
moteur ordinaire.

**Les hypothèses.** La dérive est celle du moteur de backtest, à la même base,
si bien que les poids décidés ici, passés au moteur avec le même décalage,
produisent une rotation égale à :math:`\theta \sum_i |w^*_{i,t} - b_{i,t}|`.
Le taux est constant, ce qui est la forme simple de l'article : la forme
complète le déduit du coût, de l'aversion au risque et de la vitesse
d'extinction du signal.

**La provenance.** Gârleanu, N. et Pedersen, L. H. (2013). Dynamic Trading
with Predictable Returns and Transaction Costs. Journal of Finance, 68(6),
2309-2340. Rapportée, résumé lu le 2026-09-03.

**Les limites.** Un taux constant ignore que des signaux différents
s'éteignent à des vitesses différentes. L'article pondère la cible par ces
vitesses, ce qui n'est pas fait ici et est déclaré dans la spécification 003.

**Les alternatives écartées.** Une bande de non-négociation autour de la
cible, qui produit une rotation nulle puis totale. La forme fermée complète,
qui exige un coût quadratique par actif que les études ne portent pas.

**Comment vérifier.** À taux un, la fonction rend la cible, et à taux nul les
poids dérivent sans jamais être négociés. À taux un demi sur deux actifs et
trois périodes, le calcul à la main du test de ce module se retrouve.
"""

from __future__ import annotations

import pandas as pd

from quantlab.analytics.turnover import drifted_weights
from quantlab.core.errors import ConfigError, DataQualityError

__all__ = ["partial_rebalance"]


def partial_rebalance(targets: pd.DataFrame, returns: pd.DataFrame, rate: float) -> pd.DataFrame:
    """Rend les poids décidés en ne parcourant qu'une fraction du chemin vers la cible.

    Args:
        targets: les poids cibles, une ligne par date de décision, une colonne
            par actif, sans valeur manquante.
        returns: les rendements simples de période aux mêmes dates et colonnes.
            La ligne datée *t* porte le rendement réalisé entre *t-1* et *t*,
            celui qui fait dériver les poids détenus avant la décision de *t*.
        rate: la fraction du chemin parcourue à chaque décision, entre zéro
            et un inclus.

    Returns:
        Les poids décidés, mêmes dates et colonnes que ``targets``.

    Raises:
        ConfigError: le taux est hors de l'intervalle fermé zéro un.
        DataQualityError: une cible manque, ou les rendements ne couvrent pas
            les dates ou les colonnes des cibles.
    """
    if not 0.0 <= rate <= 1.0:
        raise ConfigError(f"le taux doit être entre 0 et 1 inclus, reçu {rate}.")
    if targets.empty:
        raise DataQualityError("aucune cible à rapprocher.")
    if targets.isna().any().any():
        raise DataQualityError("une cible est manquante ; la stratégie doit rendre zéro, pas une absence.")
    manquantes = targets.index.difference(returns.index)
    if len(manquantes) > 0:
        raise DataQualityError(
            f"{len(manquantes)} date(s) de cible sans rendement, la première au {manquantes[0]}."
        )
    colonnes = targets.columns.difference(returns.columns)
    if len(colonnes) > 0:
        raise DataQualityError(f"colonnes sans rendement : {list(colonnes)}.")
    rendements = returns.reindex(index=targets.index, columns=targets.columns).fillna(0.0)
    decides = pd.DataFrame(0.0, index=targets.index, columns=targets.columns)
    detenus = pd.Series(0.0, index=targets.columns)
    for date in targets.index:
        derives = drifted_weights(detenus, rendements.loc[date]) if detenus.abs().sum() > 0 else detenus
        detenus = derives + rate * (targets.loc[date] - derives)
        decides.loc[date] = detenus
    return decides

"""Contrôles de ``quantlab.backtest.engine``.

Aucune valeur attendue de ce fichier ne vient de la sortie du code. Chacune
porte sa source en commentaire : (a) calcul à la main, (b) identité
mathématique, (c) valeur publiée, (d) implémentation indépendante.

Le test qui compte le plus est ``test_fuite_le_decalage_change_tout``. Il
mesure ce qu'un décalage nul invente, et c'est la seule preuve que le décalage
fonctionne.
"""

from __future__ import annotations

import math

import hypothesis.strategies as st
import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings

from quantlab.analytics.returns import compound
from quantlab.analytics.risk import volatility
from quantlab.backtest.engine import (
    DEFAULT_EXECUTION_LAG,
    BacktestResult,
    apply_execution_lag,
    equity_curve,
    rebalance_dates,
    run_backtest,
    volatility_target,
)
from quantlab.core.errors import (
    ConfigError,
    DataQualityError,
    InsufficientDataError,
    LookAheadError,
)
from quantlab.core.types import Frequency

ASSETS = ["A", "B"]


def _dates(n: int, start: str = "2020-01-01") -> pd.DatetimeIndex:
    """Rend ``n`` jours ouvrés consécutifs à partir de ``start``."""
    return pd.bdate_range(start, periods=n)


def _frame(values: dict[str, list[float]], index: pd.DatetimeIndex) -> pd.DataFrame:
    """Rend un tableau daté à partir de colonnes nommées."""
    return pd.DataFrame(values, index=index, dtype=float)


def _proportional_cost(rate: float):
    """Rend un modèle de coût proportionnel à la rotation, au taux donné.

    Le modèle est volontairement trivial : le fichier teste le moteur, pas le
    modèle de coût, qui a ses propres contrôles.
    """

    def cost(*, previous: pd.Series, target: pd.Series, context: pd.DataFrame) -> float:
        return rate * float(context.attrs["turnover"])

    return cost


# --------------------------------------------------------------------------
# (1) Le test anti-fuite : ce que le décalage empêche
# --------------------------------------------------------------------------


def test_fuite_le_decalage_change_tout(rng: np.random.Generator) -> None:
    """(b) Identité, puis (b) ordre de grandeur modélisé.

    Le portefeuille détient le SIGNE du rendement de la période même. Avec un
    décalage nul, le rendement de chaque période vaut donc exactement
    ``sign(r_t) * r_t = |r_t|``, qui est positif sans exception : c'est une
    identité, pas une statistique.

    Les deux chiffres attendus, modélisés sous deux hypothèses déclarées,
    252 séances et des rendements normaux centrés d'écart type 1 % :

    - décalage nul : la moyenne de ``|r|`` vaut ``0,01 * sqrt(2/pi) = 0,798 %``,
      et 252 périodes composées à ce rythme multiplient la mise par
      ``1,00798 ** 252 = 7,41``. ``compound`` rend le rendement total, soit
      cette richesse moins un, donc +641 % pour un signal sans information ;
    - décalage de un : le rendement devient ``sign(r_{t-1}) * r_t``, d'espérance
      nulle par indépendance, d'écart type ``0,01 * sqrt(252) = 15,9 %``.

    Les bornes des assertions sont larges au regard de ces deux nombres :
    4,0 contre 6,41 modélisé d'un côté, 0,75 contre 0,159 d'écart type de
    l'autre, soit 4,7 écarts types.
    """
    index = _dates(252)
    daily = pd.Series(rng.normal(0.0, 0.01, size=len(index)), index=index)
    returns = pd.DataFrame({"A": daily})
    signals = pd.DataFrame({"A": np.sign(daily.to_numpy())}, index=index)

    fuite = run_backtest(
        weights=signals,
        returns=returns,
        frequency=Frequency.DAILY,
        execution_lag=0,
        allow_same_bar_execution=True,
    )
    propre = run_backtest(
        weights=signals,
        returns=returns,
        frequency=Frequency.DAILY,
        execution_lag=1,
    )

    assert (fuite.gross_returns.to_numpy() >= -1e-15).all()
    assert float(compound(fuite.gross_returns)) > 4.0
    assert abs(float(compound(propre.gross_returns))) < 0.75
    assert (propre.gross_returns.to_numpy() < 0.0).any()


def test_decalage_par_defaut_vaut_un() -> None:
    """(a) La constante déclarée du module, et le refus du décalage nul."""
    assert DEFAULT_EXECUTION_LAG == 1

    index = _dates(4)
    returns = _frame({"A": [0.01, 0.02, -0.01, 0.03]}, index)
    weights = _frame({"A": [1.0, 1.0, 1.0, 1.0]}, index)
    with pytest.raises(LookAheadError, match="allow_same_bar_execution"):
        run_backtest(weights=weights, returns=returns, frequency=Frequency.DAILY, execution_lag=0)


# --------------------------------------------------------------------------
# (2) Le backtest calculé entièrement à la main
# --------------------------------------------------------------------------


def test_backtest_deux_actifs_trois_periodes_a_la_main() -> None:
    """(a) Calcul à la main, deux actifs, trois périodes, coût de 10 points de base.

    Rendements. Période 1 : A et B à 0 %. Période 2 : A +10 %, B -5 %.
    Période 3 : A 0 %, B +20 %.

    Cibles décidées. Date 1 : 60 % et 40 %. Date 2 : 50 % et 50 %.
    Le décalage vaut un, donc la cible de la date 1 est détenue en période 2.

    Période 1. Aucune cible n'est encore exécutable, le portefeuille est plat,
    rotation nulle et rendement nul.

    Période 2. Construction depuis l'encaisse vers 60 % et 40 %.
    Rotation = 0,5 x (0,60 + 0,40) = 0,50. Coût = 0,0010 x 0,50 = 0,0005.
    Rendement brut = 0,60 x 0,10 + 0,40 x (-0,05) = 0,06 - 0,02 = 0,04.
    Rendement net = 0,04 - 0,0005 = 0,0395.

    Dérive de fin de période 2. Valeurs 0,60 x 1,10 = 0,66 et
    0,40 x 0,95 = 0,38, total 1,04, donc poids dérivés 66/104 = 33/52 et
    38/104 = 19/52, soit 0,634615 et 0,365385.

    Période 3. Cible 50 % et 50 % contre ces poids dérivés.
    Écarts |26/52 - 33/52| = 7/52 et |26/52 - 19/52| = 7/52, somme 14/52,
    rotation 7/52 = 0,134615. Coût = 0,0010 x 7/52 = 0,000134615.
    Rendement brut = 0,50 x 0,00 + 0,50 x 0,20 = 0,10.
    Rendement net = 0,10 - 0,000134615 = 0,099865385.

    Richesse finale = 1 x 1,0395 x 1,099865385 = 1,143310067.
    """
    index = _dates(3)
    returns = _frame({"A": [0.0, 0.10, 0.0], "B": [0.0, -0.05, 0.20]}, index)
    weights = _frame({"A": [0.6, 0.5, 0.5], "B": [0.4, 0.5, 0.5]}, index)

    result = run_backtest(
        weights=weights,
        returns=returns,
        cost_model=_proportional_cost(0.0010),
        frequency=Frequency.DAILY,
        execution_lag=1,
    )

    assert result.turnover.tolist() == pytest.approx([0.0, 0.5, 7 / 52], abs=1e-15)
    assert result.costs.tolist() == pytest.approx([0.0, 0.0005, 0.0010 * 7 / 52], abs=1e-18)
    assert result.gross_returns.tolist() == pytest.approx([0.0, 0.04, 0.10], abs=1e-15)
    assert result.net_returns.tolist() == pytest.approx([0.0, 0.0395, 0.10 - 0.0010 * 7 / 52], abs=1e-15)
    assert result.drifted_weights.loc[index[2], "A"] == pytest.approx(33 / 52, abs=1e-15)
    assert result.drifted_weights.loc[index[2], "B"] == pytest.approx(19 / 52, abs=1e-15)
    assert result.executed_weights.loc[index[1]].tolist() == pytest.approx([0.6, 0.4], abs=1e-15)
    assert result.executed_weights.loc[index[2]].tolist() == pytest.approx([0.5, 0.5], abs=1e-15)
    assert float(equity_curve(result).iloc[-1]) == pytest.approx(1.143310067, abs=1e-9)


def test_capital_initial_met_la_courbe_a_l_echelle() -> None:
    """(b) Identité : la richesse est proportionnelle au capital de départ.

    Le même backtest lancé avec 10 000 dollars rend une courbe exactement
    10 000 fois celle du backtest à un dollar, les rendements étant inchangés.
    """
    index = _dates(3)
    returns = _frame({"A": [0.0, 0.10, 0.0], "B": [0.0, -0.05, 0.20]}, index)
    weights = _frame({"A": [0.6, 0.5, 0.5], "B": [0.4, 0.5, 0.5]}, index)
    commun = {"weights": weights, "returns": returns, "frequency": Frequency.DAILY}

    un = run_backtest(**commun, initial_capital=1.0)
    dix_mille = run_backtest(**commun, initial_capital=10_000.0)

    assert equity_curve(dix_mille).to_numpy() == pytest.approx(
        10_000.0 * equity_curve(un).to_numpy(), rel=1e-15
    )
    assert dix_mille.net_returns.to_numpy() == pytest.approx(un.net_returns.to_numpy(), abs=0.0)


# --------------------------------------------------------------------------
# (3) L'identité net = brut - coûts
# --------------------------------------------------------------------------


def test_identite_net_egale_brut_moins_couts(rng: np.random.Generator) -> None:
    """(b) Identité comptable, vérifiée à 1e-12 sur des données aléatoires.

    Le modèle de coût rend deux composantes, cinq points de base de commission
    et trois de fourchette. La somme des colonnes de la ventilation doit
    redonner la série de coûts, sans quoi la ventilation ment.
    """
    index = _dates(120)
    returns = _frame(
        {
            "A": rng.normal(0.0005, 0.01, size=120).tolist(),
            "B": rng.normal(0.0002, 0.008, size=120).tolist(),
        },
        index,
    )
    tirages = rng.uniform(0.0, 1.0, size=120)
    weights = _frame({"A": tirages.tolist(), "B": (1.0 - tirages).tolist()}, index)

    def cost(*, previous: pd.Series, target: pd.Series, context: pd.DataFrame) -> dict[str, float]:
        rotation = float(context.attrs["turnover"])
        return {"commission": 0.0005 * rotation, "spread": 0.0003 * rotation}

    result = run_backtest(
        weights=weights,
        returns=returns,
        cost_model=cost,
        frequency=Frequency.DAILY,
    )

    ecart = (result.net_returns - (result.gross_returns - result.costs)).abs().max()
    assert float(ecart) < 1e-12
    somme = result.cost_breakdown.sum(axis=1)
    assert float((somme - result.costs).abs().max()) < 1e-15
    assert list(result.cost_breakdown.columns) == ["commission", "spread"]
    assert float(result.costs.min()) >= 0.0


def test_sans_modele_de_cout_le_net_egale_le_brut() -> None:
    """(b) Identité : un coût absent vaut zéro, et non un coût implicite."""
    index = _dates(10)
    returns = _frame({"A": [0.01] * 10, "B": [-0.005] * 10}, index)
    weights = _frame({"A": [0.5] * 10, "B": [0.5] * 10}, index)

    result = run_backtest(weights=weights, returns=returns, frequency=Frequency.DAILY)

    assert float(result.costs.abs().max()) == 0.0
    assert result.net_returns.to_numpy() == pytest.approx(result.gross_returns.to_numpy(), abs=0.0)
    assert result.metadata["cost_model"] == "aucun"


# --------------------------------------------------------------------------
# (4) La convention de rotation : contre les poids dérivés, jamais contre les cibles
# --------------------------------------------------------------------------


def test_rotation_mesuree_contre_les_poids_derives() -> None:
    """(a) Calcul en forme fermée : un portefeuille laissé dériver ne négocie pas.

    Deux actifs aux rendements constants, +2 % et -1 % par période, partis de
    moitié-moitié. Les poids dérivés après ``k`` périodes valent

        w_A(k) = 1,02**k / (1,02**k + 0,99**k),   w_B(k) = 1 - w_A(k),

    puisque la dérive d'une période transforme 1,02**k en 1,02**(k+1) au
    numérateur comme au dénominateur.

    Les cibles fournies au moteur SONT cette suite. Le portefeuille ne négocie
    donc jamais après sa construction, et la rotation mesurée contre les poids
    dérivés vaut zéro à chaque période.

    Mesurée contre la cible précédente, la même suite affiche une rotation
    positive à chaque période. Comme w_A croît, la somme des demi-sommes des
    écarts se télescope et vaut w_A(23) - w_A(0). Avec
    (1,02/0,99)**23 = 1,98695, cela fait 1,98695 / 2,98695 - 0,50 = 0,16521,
    soit 16,5 points de rotation facturés pour zéro transaction.

    La construction initiale reste comptée, à 0,5 x (0,5 + 0,5) = 0,50 : passer
    de l'encaisse au portefeuille coûte, et l'oublier est l'erreur symétrique.
    """
    n = 25
    index = _dates(n)
    returns = _frame({"A": [0.02] * n, "B": [-0.01] * n}, index)
    a_values = [1.02**k / (1.02**k + 0.99**k) for k in range(n)]
    weights = _frame({"A": a_values, "B": [1.0 - a for a in a_values]}, index)

    result = run_backtest(
        weights=weights,
        returns=returns,
        frequency=Frequency.DAILY,
        execution_lag=1,
    )

    assert float(result.turnover.iloc[0]) == 0.0
    assert float(result.turnover.iloc[1]) == pytest.approx(0.5, abs=1e-15)
    assert float(result.turnover.iloc[2:].abs().max()) < 1e-12

    naive = sum(abs(a_values[k] - a_values[k - 1]) for k in range(1, n - 1))
    assert naive == pytest.approx(a_values[n - 2] - a_values[0], abs=1e-12)
    assert naive == pytest.approx(0.16521, abs=1e-5)


def test_rebalancement_mensuel_ne_negocie_qu_aux_fins_de_mois() -> None:
    """(a) Comptage à la main : trois mois de séances, trois rééquilibrages.

    Les cibles sont constantes et fournies chaque jour. Avec un rééquilibrage
    mensuel, seules les dernières séances de janvier, février et mars 2021
    portent une rotation non nulle.
    """
    index = pd.bdate_range("2021-01-01", "2021-03-31")
    returns = _frame({"A": [0.001] * len(index), "B": [-0.002] * len(index)}, index)
    weights = _frame({"A": [0.5] * len(index), "B": [0.5] * len(index)}, index)

    result = run_backtest(
        weights=weights,
        returns=returns,
        frequency=Frequency.DAILY,
        rebalance=Frequency.MONTHLY,
    )

    negociations = result.turnover[result.turnover > 0.0]
    assert len(negociations) == 3
    assert list(negociations.index) == [
        pd.Timestamp("2021-01-29"),
        pd.Timestamp("2021-02-26"),
        pd.Timestamp("2021-03-31"),
    ]


def test_entre_deux_rebalancements_le_livre_derive_et_continue_de_gagner() -> None:
    """(a) Calcul à la main : hors date de négociation, le portefeuille dérive.

    Quatre périodes, deux actifs, cibles constantes à moitié-moitié, décalage
    de un. Le rendement de A vaut 0 %, +10 %, +20 % puis +10 %, celui de B est
    nul partout. La seule date négociable est la deuxième.

    Période 2. La cible de la date 1 s'exécute : 50 % et 50 %.
    Rendement brut = 0,5 x 0,10 = 0,05, rotation 0,5 x (0,5 + 0,5) = 0,50.
    Valeurs de fin 0,55 et 0,50, valeur liquidative 1,05, donc poids dérivés
    0,55 / 1,05 = 11/21 et 0,50 / 1,05 = 10/21.

    Période 3. Aucune négociation. Poids détenus 11/21 et 10/21, rendement brut
    (11/21) x 0,20 = 11/105 = 0,104761905. Valeurs de fin 13,2/21 et 10/21,
    valeur liquidative 23,2/21, donc poids dérivés 33/58 et 25/58.

    Période 4. Aucune négociation non plus. Rendement brut
    (33/58) x 0,10 = 33/580 = 0,056896552.

    Ces deux nombres séparent quatre conventions. Un livre soldé hors date de
    rééquilibrage rendrait 0. Un livre figé sur la cible rendrait 0,100 puis
    0,050. Une dérive calculée sur le rendement de la période en cours, donc
    sur une information future, rendrait 0,109090909 en période 3.
    """
    index = _dates(4)
    returns = _frame({"A": [0.0, 0.10, 0.20, 0.10], "B": [0.0, 0.0, 0.0, 0.0]}, index)
    weights = _frame({"A": [0.5] * 4, "B": [0.5] * 4}, index)

    result = run_backtest(
        weights=weights,
        returns=returns,
        frequency=Frequency.DAILY,
        execution_lag=1,
        rebalance=pd.DatetimeIndex([index[1]]),
    )

    assert result.turnover.tolist() == pytest.approx([0.0, 0.5, 0.0, 0.0], abs=1e-15)
    assert result.executed_weights.loc[index[2]].tolist() == pytest.approx([11 / 21, 10 / 21], abs=1e-15)
    assert result.executed_weights.loc[index[3]].tolist() == pytest.approx([33 / 58, 25 / 58], abs=1e-15)
    assert result.gross_returns.tolist() == pytest.approx([0.0, 0.05, 11 / 105, 33 / 580], abs=1e-15)


def test_le_levier_porte_se_distingue_de_l_exposition_brute() -> None:
    """(a) Calcul à la main : un livre 130/30 dont une jambe gagne 10 %.

    Les poids détenus valent +1,3 et -0,3, donc une exposition brute de 1,6 à
    l'entrée de chaque période. En période 2, A gagne 10 % et B ne bouge pas.

    Valeurs de fin : 1,3 x 1,1 = 1,43 et -0,3. Croissance de la valeur
    liquidative : 1 + 1,3 x 0,10 = 1,13. Poids dérivés 1,43/1,13 et -0,30/1,13,
    donc une exposition brute de fin de (1,43 + 0,30) / 1,13 = 173/113.

    Le levier porté est la moyenne des deux, soit (8/5 + 173/113) / 2 =
    1769/1130 = 1,565486726. Il diffère de l'exposition brute, qui reste 1,6 :
    sans cette assertion, remplacer le levier par l'exposition brute passerait
    inaperçu.
    """
    index = _dates(2)
    returns = _frame({"A": [0.0, 0.10], "B": [0.0, 0.0]}, index)
    weights = _frame({"A": [1.3, 1.3], "B": [-0.3, -0.3]}, index)

    result = run_backtest(
        weights=weights,
        returns=returns,
        frequency=Frequency.DAILY,
        execution_lag=0,
        allow_same_bar_execution=True,
    )

    assert result.gross_exposure.tolist() == pytest.approx([1.6, 1.6], abs=1e-15)
    assert float(result.leverage.iloc[1]) == pytest.approx(1769 / 1130, abs=1e-15)
    assert float(result.leverage.iloc[1]) != pytest.approx(1.6, abs=1e-6)


def test_le_modele_de_cout_ne_voit_aucun_rendement_futur() -> None:
    """(a) Le contexte porte le rendement de la période PRÉCÉDENTE, jamais celui de la période.

    La transaction a lieu au début de la période. Le rendement de cette
    période, réalisé à sa fin, n'est donc pas connaissable à cet instant. Un
    modèle de coût qui le recevrait pourrait facturer moins cher les jours de
    hausse, et le backtest gagnerait sans rien avoir prédit.

    Les rendements valent 1 %, 2 %, 3 % puis 4 %, tous distincts. Le contexte
    reçu à la date d'indice ``k`` doit porter le rendement d'indice ``k - 1``.
    """
    index = _dates(4)
    valeurs = [0.01, 0.02, 0.03, 0.04]
    returns = _frame({"A": valeurs}, index)
    weights = _frame({"A": [1.0] * 4}, index)
    vus: dict[pd.Timestamp, float] = {}

    def cost(*, previous: pd.Series, target: pd.Series, context: pd.DataFrame) -> float:
        assert "period_return" not in context.columns
        vus[context.attrs["date"]] = float(context["previous_return"].iloc[0])
        return 0.0

    run_backtest(
        weights=weights,
        returns=returns,
        cost_model=cost,
        frequency=Frequency.DAILY,
        execution_lag=1,
    )

    assert list(vus) == list(index[1:])
    for position in range(1, 4):
        assert vus[index[position]] == pytest.approx(valeurs[position - 1], abs=0.0)


# --------------------------------------------------------------------------
# Les dates de rééquilibrage
# --------------------------------------------------------------------------


def test_rebalance_dates_mensuel_et_trimestriel() -> None:
    """(a) Dernières séances des mois et des trimestres de 2021, lues au calendrier.

    Janvier 2021 finit le vendredi 29, février le vendredi 26, mars le
    mercredi 31. Les fins de trimestre de 2021 tombent les 31 mars, 30 juin,
    30 septembre et 31 décembre, tous jours ouvrés.
    """
    index = pd.bdate_range("2021-01-01", "2021-12-31")

    mensuel = rebalance_dates(index, Frequency.MONTHLY)
    trimestriel = rebalance_dates(index, Frequency.QUARTERLY)

    assert len(mensuel) == 12
    assert list(mensuel[:3]) == [
        pd.Timestamp("2021-01-29"),
        pd.Timestamp("2021-02-26"),
        pd.Timestamp("2021-03-31"),
    ]
    assert list(trimestriel) == [
        pd.Timestamp("2021-03-31"),
        pd.Timestamp("2021-06-30"),
        pd.Timestamp("2021-09-30"),
        pd.Timestamp("2021-12-31"),
    ]
    assert trimestriel.isin(mensuel).all()


def test_rebalance_dates_quotidien_rend_l_index_entier() -> None:
    """(b) Identité : « à chaque période » ne retire aucune date."""
    index = _dates(37)
    assert rebalance_dates(index, Frequency.DAILY).equals(index)


def test_rebalance_dates_refuse_un_index_non_date() -> None:
    """(b) Un mois n'existe pas sur un index entier : la fonction le dit."""
    index = pd.Index([0, 1, 2, 3])
    assert rebalance_dates(index, Frequency.DAILY).equals(index)
    with pytest.raises(ConfigError, match="DatetimeIndex"):
        rebalance_dates(index, Frequency.MONTHLY)


def test_rebalance_dates_cas_limites() -> None:
    """(b) Index vide, doublons et désordre sont refusés, pas devinés."""
    with pytest.raises(InsufficientDataError):
        rebalance_dates(pd.DatetimeIndex([]), Frequency.MONTHLY)
    doublons = pd.DatetimeIndex(["2021-01-04", "2021-01-04"])
    with pytest.raises(DataQualityError, match="double"):
        rebalance_dates(doublons, Frequency.MONTHLY)
    desordre = pd.DatetimeIndex(["2021-02-01", "2021-01-04"])
    with pytest.raises(DataQualityError, match="trié"):
        rebalance_dates(desordre, Frequency.MONTHLY)


# --------------------------------------------------------------------------
# Le décalage d'exécution, isolé
# --------------------------------------------------------------------------


def test_apply_execution_lag_deplace_les_lignes() -> None:
    """(a) Trois dates, décalage de un : la ligne 2 porte la valeur de la ligne 1."""
    index = _dates(3)
    weights = _frame({"A": [0.1, 0.2, 0.3]}, index)

    decale = apply_execution_lag(weights, 1)

    assert math.isnan(decale.loc[index[0], "A"])
    assert decale.loc[index[1], "A"] == pytest.approx(0.1, abs=1e-15)
    assert decale.loc[index[2], "A"] == pytest.approx(0.2, abs=1e-15)
    assert apply_execution_lag(weights, 0).equals(weights)


def test_apply_execution_lag_refuse_le_negatif() -> None:
    """(b) Un décalage négatif est la définition de la fuite : il lève."""
    weights = _frame({"A": [0.1, 0.2]}, _dates(2))
    with pytest.raises(LookAheadError, match="négatif"):
        apply_execution_lag(weights, -1)
    with pytest.raises(TypeError):
        apply_execution_lag(weights["A"], 1)


@given(
    lag=st.integers(min_value=0, max_value=5),
    valeurs=st.lists(
        st.floats(min_value=-2.0, max_value=2.0, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=30,
    ),
)
@settings(max_examples=50, deadline=None)
def test_propriete_le_decalage_recopie_la_ligne_anterieure(lag: int, valeurs: list[float]) -> None:
    """(b) Propriété : la ligne k du résultat vaut la ligne k - lag de l'entrée.

    La comparaison se fait sur les listes, sans repasser par le code testé.
    """
    index = _dates(len(valeurs))
    weights = _frame({"A": valeurs}, index)

    decale = apply_execution_lag(weights, lag)

    for position in range(len(valeurs)):
        obtenu = decale.iloc[position, 0]
        if position < lag:
            assert math.isnan(obtenu)
        else:
            assert obtenu == pytest.approx(valeurs[position - lag], abs=0.0)


# --------------------------------------------------------------------------
# (5) La cible de volatilité
# --------------------------------------------------------------------------


def test_volatility_target_valeur_exacte() -> None:
    """(a) Calcul à la main : une prévision au double de la cible rend 0,5.

    Une volatilité prévue de 0,20 / sqrt(252) par séance s'annualise à 0,20.
    Pour une cible de 0,10, le levier vaut 0,10 / 0,20 = 0,50 exactement.
    """
    index = _dates(5)
    quotidienne = 0.20 / math.sqrt(252.0)
    forecast = pd.Series([quotidienne] * 5, index=index)

    levier = volatility_target(forecast, 0.10, Frequency.DAILY, leverage_cap=5.0)

    assert levier.to_numpy() == pytest.approx([0.5] * 5, abs=1e-14)
    assert levier.name == "leverage"


def test_volatility_target_plafonne_quand_la_volatilite_tend_vers_zero() -> None:
    """(a) Sans plafond, le levier explose : 0,1 % de volatilité contre 10 % de cible.

    Une volatilité prévue de 0,001 annualisée contre une cible de 0,10 demande
    un levier de 100. Le plafond fixé à 3,0 le ramène à 3,0. Une prévision
    exactement nulle demanderait un levier infini, et rend le plafond elle
    aussi, jamais ``inf`` ni ``NaN``.
    """
    index = _dates(3)
    minuscule = 0.001 / math.sqrt(252.0)
    forecast = pd.Series([minuscule, 0.0, 1e-300], index=index)

    levier = volatility_target(forecast, 0.10, Frequency.DAILY, leverage_cap=3.0)

    assert levier.to_numpy() == pytest.approx([3.0, 3.0, 3.0], abs=0.0)
    assert np.isfinite(levier.to_numpy()).all()


def test_volatility_target_atteint_la_cible_sur_une_serie_a_volatilite_connue(
    rng: np.random.Generator,
) -> None:
    """(b) Identité de construction, tolérance justifiée par l'erreur d'estimation.

    Les rendements sont tirés normaux centrés d'écart type quotidien 1 %, soit
    15,87 % annualisés. La prévision est l'écart type des 60 séances
    précédentes, décalé d'une séance pour interdire toute fuite. La stratégie
    levée doit afficher une volatilité réalisée proche de la cible de 10 %,
    parce que le levier est exactement le rapport de la cible au risque prévu.

    Deux écarts connus subsistent, et la tolérance les couvre. Le premier est
    l'erreur d'échantillonnage de la volatilité réalisée sur 4 940 points,
    d'ordre 1 / sqrt(2 x 4940) = 1,0 %. Le second est le biais de Jensen de
    l'inverse d'un écart type estimé sur 60 points, d'ordre 3 / (4 x 59) =
    1,3 %. Leur somme reste sous 2,5 %, et la tolérance retenue de 10 %
    relatifs vaut quatre fois cette somme.
    """
    n = 5000
    index = _dates(n)
    rendements = pd.Series(rng.normal(0.0, 0.01, size=n), index=index)
    prevision = rendements.rolling(window=60).std().shift(1)

    levier = volatility_target(prevision, 0.10, Frequency.DAILY, leverage_cap=10.0)
    levee = (levier * rendements).dropna()

    assert volatility(levee, Frequency.DAILY) == pytest.approx(0.10, rel=0.10)


def test_volatility_target_lissage_et_bornes() -> None:
    """(b) Identité : une moyenne de valeurs bornées reste dans les mêmes bornes.

    Le lissage s'applique après écrêtage. Comme la moyenne mobile d'une suite
    à valeurs dans [plancher, plafond] reste dans cet intervalle, le lissage ne
    peut pas ramener un levier au-dessus du plafond.
    """
    index = _dates(6)
    forecast = pd.Series([0.001, 0.05, 0.001, 0.05, 0.001, 0.05], index=index)

    brut = volatility_target(forecast, 0.10, Frequency.DAILY, leverage_cap=2.0, leverage_floor=0.25)
    lisse = volatility_target(
        forecast, 0.10, Frequency.DAILY, leverage_cap=2.0, leverage_floor=0.25, smoothing=3
    )

    assert float(brut.max()) <= 2.0
    assert float(brut.min()) >= 0.25
    assert float(lisse.max()) <= 2.0
    assert float(lisse.min()) >= 0.25
    # (a) Moyenne à la main des deux premiers leviers, tous deux écrêtés au
    # plafond de 2,0 pour le premier et calculés pour le second :
    # 0,05 x sqrt(252) = 0,7937, donc 0,10 / 0,7937 = 0,12599, écrêté au
    # plancher de 0,25. La moyenne des deux vaut (2,0 + 0,25) / 2 = 1,125.
    assert float(lisse.iloc[1]) == pytest.approx(1.125, abs=1e-14)


def test_volatility_target_refuse_les_configurations_absurdes() -> None:
    """(b) Le plafond est obligatoire, et les entrées incohérentes lèvent."""
    index = _dates(3)
    forecast = pd.Series([0.01, 0.01, 0.01], index=index)

    with pytest.raises(ConfigError, match="leverage_cap"):
        volatility_target(forecast, 0.10, Frequency.DAILY, leverage_cap=0.0)
    with pytest.raises(ConfigError, match="leverage_floor"):
        volatility_target(forecast, 0.10, Frequency.DAILY, leverage_cap=1.0, leverage_floor=2.0)
    with pytest.raises(ConfigError, match="target_annual"):
        volatility_target(forecast, -0.10, Frequency.DAILY, leverage_cap=1.0)
    with pytest.raises(ConfigError, match="smoothing"):
        volatility_target(forecast, 0.10, Frequency.DAILY, leverage_cap=1.0, smoothing=0)
    with pytest.raises(TypeError):
        volatility_target(forecast.to_frame(), 0.10, Frequency.DAILY, leverage_cap=1.0)


def test_volatility_target_cas_limites_de_la_prevision() -> None:
    """(b) Série vide, série toute manquante, trou au milieu, valeur négative.

    Les valeurs manquantes du DÉBUT sont admises : une fenêtre glissante de
    soixante séances n'a rien à dire avant la soixantième. Celles du MILIEU
    sont refusées, parce qu'elles dimensionneraient une position au hasard.
    """
    index = _dates(4)
    with pytest.raises(InsufficientDataError):
        volatility_target(pd.Series(dtype=float), 0.10, Frequency.DAILY, leverage_cap=1.0)
    with pytest.raises(InsufficientDataError):
        volatility_target(pd.Series([np.nan] * 4, index=index), 0.10, Frequency.DAILY, leverage_cap=1.0)
    with pytest.raises(DataQualityError, match="trou"):
        volatility_target(
            pd.Series([0.01, np.nan, 0.01, 0.01], index=index),
            0.10,
            Frequency.DAILY,
            leverage_cap=1.0,
        )
    with pytest.raises(DataQualityError, match="négative"):
        volatility_target(
            pd.Series([0.01, -0.01, 0.01, 0.01], index=index),
            0.10,
            Frequency.DAILY,
            leverage_cap=1.0,
        )

    debut_manquant = pd.Series([np.nan, np.nan, 0.01, 0.01], index=index)
    levier = volatility_target(debut_manquant, 0.10, Frequency.DAILY, leverage_cap=5.0)
    assert bool(levier.iloc[:2].isna().all())
    assert bool(levier.iloc[2:].notna().all())


@given(
    valeurs=st.lists(
        st.floats(min_value=0.0, max_value=0.5, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=40,
    ),
    plafond=st.floats(min_value=0.1, max_value=8.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=60, deadline=None)
def test_propriete_le_levier_reste_dans_ses_bornes(valeurs: list[float], plafond: float) -> None:
    """(b) Propriété : le levier rendu tient toujours entre le plancher et le plafond.

    C'est la raison d'être du plafond, et elle doit tenir pour toute prévision
    positive, y compris nulle.
    """
    index = _dates(len(valeurs))
    forecast = pd.Series(valeurs, index=index)

    levier = volatility_target(forecast, 0.10, Frequency.DAILY, leverage_cap=plafond, leverage_floor=0.05)

    assert float(levier.max()) <= plafond + 1e-12
    assert float(levier.min()) >= 0.05 - 1e-12


# --------------------------------------------------------------------------
# (6) La propriété centrale du moteur
# --------------------------------------------------------------------------


@given(
    rendements_a=st.lists(
        st.floats(min_value=-0.2, max_value=0.2, allow_nan=False, allow_infinity=False),
        min_size=2,
        max_size=20,
    ),
    poids_a=st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    poids_b=st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=60, deadline=None)
def test_propriete_poids_constants_sans_frais_ni_decalage(
    rendements_a: list[float], poids_a: float, poids_b: float
) -> None:
    """(b) Propriété : le moteur rend exactement le rendement pondéré du panier.

    Sans frais, sans décalage et avec des poids constants rééquilibrés à chaque
    période, le rendement de période vaut par définition la somme des poids
    multipliés par les rendements. La valeur attendue est ce produit scalaire,
    calculé ici par NumPy, donc en dehors du code testé.
    """
    n = len(rendements_a)
    index = _dates(n)
    rendements_b = [-0.5 * r for r in rendements_a]
    returns = _frame({"A": rendements_a, "B": rendements_b}, index)
    weights = _frame({"A": [poids_a] * n, "B": [poids_b] * n}, index)

    result = run_backtest(
        weights=weights,
        returns=returns,
        frequency=Frequency.DAILY,
        execution_lag=0,
        allow_same_bar_execution=True,
    )

    attendu = np.array([poids_a, poids_b]) @ returns.to_numpy().T
    assert result.gross_returns.to_numpy() == pytest.approx(attendu, abs=1e-12)
    assert result.net_returns.to_numpy() == pytest.approx(attendu, abs=1e-12)


# --------------------------------------------------------------------------
# Le résultat, ses expositions et son résumé
# --------------------------------------------------------------------------


def test_expositions_et_levier_dun_livre_long_short() -> None:
    """(a) Calcul à la main sur un livre 130/30, deux périodes.

    Les poids détenus valent +1,3 et -0,3. L'exposition brute vaut
    1,3 + 0,3 = 1,6 et l'exposition nette 1,3 - 0,3 = 1,0.

    Le levier rendu est la moyenne des expositions brutes du début et de la fin
    de période. Avec des rendements nuls, la dérive ne change rien, donc le
    levier vaut aussi 1,6. C'est ce qui le distingue de l'exposition brute, qui
    ne regarde que le début.
    """
    index = _dates(2)
    returns = _frame({"A": [0.0, 0.0], "B": [0.0, 0.0]}, index)
    weights = _frame({"A": [1.3, 1.3], "B": [-0.3, -0.3]}, index)

    result = run_backtest(
        weights=weights,
        returns=returns,
        frequency=Frequency.DAILY,
        execution_lag=0,
        allow_same_bar_execution=True,
    )

    assert result.gross_exposure.tolist() == pytest.approx([1.6, 1.6], abs=1e-15)
    assert result.net_exposure.tolist() == pytest.approx([1.0, 1.0], abs=1e-15)
    assert result.leverage.tolist() == pytest.approx([1.6, 1.6], abs=1e-15)


def test_summary_et_to_frame(rng: np.random.Generator) -> None:
    """(b) Le résumé délègue tout à ``analytics``, et les identités le montrent.

    Deux contrôles indépendants du moteur. Le rendement total net du résumé
    doit valoir la composition de la série nette, calculée ici par
    ``analytics.returns.compound``. Sans frais, l'écart des deux taux annuels
    composés doit être exactement nul.
    """
    index = _dates(300)
    returns = _frame(
        {
            "A": rng.normal(0.0004, 0.011, size=300).tolist(),
            "B": rng.normal(0.0003, 0.009, size=300).tolist(),
        },
        index,
    )
    weights = _frame({"A": [0.6] * 300, "B": [0.4] * 300}, index)

    result = run_backtest(weights=weights, returns=returns, frequency=Frequency.DAILY)
    resume = result.summary()

    assert resume["total_return_net"] == pytest.approx(float(compound(result.net_returns)), abs=1e-15)
    assert resume["cost_drag_annual"] == pytest.approx(0.0, abs=1e-15)
    assert resume["n_periods"] == 300
    assert resume["cost_basis"] == "net"
    assert resume["volatility_annual"] == pytest.approx(
        volatility(result.net_returns, Frequency.DAILY), abs=0.0
    )

    table = result.to_frame()
    assert list(table.columns) == [
        "gross_return",
        "net_return",
        "cost",
        "turnover",
        "gross_exposure",
        "net_exposure",
        "leverage",
    ]
    assert table.index.equals(index)


def test_summary_refuse_une_seule_periode() -> None:
    """(b) Deux points ne font pas une volatilité : le résumé lève."""
    index = _dates(1)
    returns = _frame({"A": [0.01]}, index)
    weights = _frame({"A": [1.0]}, index)

    result = run_backtest(weights=weights, returns=returns, frequency=Frequency.DAILY)

    assert isinstance(result, BacktestResult)
    with pytest.raises(InsufficientDataError):
        result.summary()


def test_metadonnees_portent_les_hypotheses() -> None:
    """(b) Une performance sans échantillon ni base de coût est un chiffre nu."""
    index = _dates(5)
    returns = _frame({"A": [0.01] * 5}, index)
    weights = _frame({"A": [1.0] * 5}, index)

    result = run_backtest(
        weights=weights,
        returns=returns,
        frequency=Frequency.MONTHLY,
        execution_lag=2,
        cost_model=_proportional_cost(0.001),
    )

    meta = result.metadata
    assert meta["execution_lag"] == 2
    assert meta["same_bar_execution"] is False
    assert meta["start"] == index[0]
    assert meta["end"] == index[-1]
    assert meta["n_periods"] == 5
    assert meta["frequency"] is Frequency.MONTHLY
    assert meta["turnover_convention"] == "half_sum"
    assert str(meta["sample"]) == "IS"
    assert str(meta["cost_basis"]) == "net"


# --------------------------------------------------------------------------
# Les refus du moteur
# --------------------------------------------------------------------------


def test_moteur_refuse_les_entrees_incoherentes() -> None:
    """(b) Actif inconnu, date inconnue, capital nul, tableau vide."""
    index = _dates(4)
    returns = _frame({"A": [0.01] * 4}, index)
    weights = _frame({"A": [1.0] * 4}, index)

    with pytest.raises(ConfigError, match="absents de returns"):
        run_backtest(
            weights=_frame({"A": [1.0] * 4, "Z": [0.0] * 4}, index),
            returns=returns,
            frequency=Frequency.DAILY,
        )
    autre = _frame({"A": [1.0] * 4}, _dates(4, start="2030-01-01"))
    with pytest.raises(ConfigError, match="absentes de returns"):
        run_backtest(weights=autre, returns=returns, frequency=Frequency.DAILY)
    with pytest.raises(ConfigError, match="initial_capital"):
        run_backtest(weights=weights, returns=returns, frequency=Frequency.DAILY, initial_capital=0.0)
    with pytest.raises(InsufficientDataError):
        run_backtest(
            weights=pd.DataFrame(columns=["A"], dtype=float),
            returns=returns,
            frequency=Frequency.DAILY,
        )
    with pytest.raises(ConfigError, match="cost_model"):
        run_backtest(weights=weights, returns=returns, frequency=Frequency.DAILY, cost_model="dix pour cent")


def test_moteur_refuse_un_rendement_manquant_sur_un_actif_detenu() -> None:
    """(b) Un trou ne se remplace pas par zéro en silence."""
    index = _dates(4)
    returns = _frame({"A": [0.01, np.nan, 0.02, 0.0]}, index)
    weights = _frame({"A": [1.0] * 4}, index)

    with pytest.raises(DataQualityError, match="manquant"):
        run_backtest(weights=weights, returns=returns, frequency=Frequency.DAILY)


def test_moteur_refuse_une_ligne_de_poids_a_moitie_manquante() -> None:
    """(b) Un actif sans cible n'est pas un actif à poids nul."""
    index = _dates(4)
    returns = _frame({"A": [0.01] * 4, "B": [0.0] * 4}, index)
    weights = _frame({"A": [0.5, 0.5, 0.5, 0.5], "B": [0.5, np.nan, 0.5, 0.5]}, index)

    with pytest.raises(DataQualityError, match="partiellement manquante"):
        run_backtest(weights=weights, returns=returns, frequency=Frequency.DAILY)


def test_moteur_refuse_une_date_de_rebalancement_inconnue() -> None:
    """(b) Une date sans rendement ne se négocie pas."""
    index = _dates(4)
    returns = _frame({"A": [0.01] * 4}, index)
    weights = _frame({"A": [1.0] * 4}, index)

    with pytest.raises(ConfigError, match="absentes de l'index"):
        run_backtest(
            weights=weights,
            returns=returns,
            frequency=Frequency.DAILY,
            rebalance=pd.DatetimeIndex(["2030-06-03"]),
        )


def test_moteur_accepte_un_objet_portant_une_methode_cost() -> None:
    """(a) Le protocole ``CostModel`` du dépôt passe sans adaptateur.

    Le modèle facture vingt points de base la rotation. La construction initiale
    d'un portefeuille pleinement investi vaut une rotation de 0,50, donc un coût
    de 0,0010 exactement.
    """

    class Fixe:
        """Modèle de coût proportionnel, écrit comme le protocole l'exige."""

        def cost(self, *, previous: pd.Series, target: pd.Series, context: pd.DataFrame) -> float:
            """Rend vingt points de base multipliés par la rotation de la période."""
            return 0.0020 * float(context.attrs["turnover"])

    index = _dates(3)
    returns = _frame({"A": [0.0, 0.0, 0.0], "B": [0.0, 0.0, 0.0]}, index)
    weights = _frame({"A": [0.5] * 3, "B": [0.5] * 3}, index)

    result = run_backtest(
        weights=weights,
        returns=returns,
        cost_model=Fixe(),
        frequency=Frequency.DAILY,
        execution_lag=1,
    )

    assert float(result.costs.iloc[1]) == pytest.approx(0.0010, abs=1e-15)
    assert float(result.costs.iloc[2]) == pytest.approx(0.0, abs=1e-15)
    assert result.metadata["cost_model"] == "Fixe"

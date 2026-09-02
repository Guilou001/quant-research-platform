"""Contrôles de ``quantlab.execution.capacity``.

Aucune valeur attendue ne vient de la sortie du code. Chacune porte sa source
en commentaire : (a) calcul à la main, (b) identité mathématique, (c) propriété
de construction des données.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from quantlab.analytics.visualization.figures import capacity_plot
from quantlab.backtest.engine import run_backtest
from quantlab.core.determinism import make_generator
from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.protocols import CostModel
from quantlab.core.types import Frequency
from quantlab.execution.capacity import (
    IMPACT_COMPONENT,
    SPREAD_COMPONENT,
    ImpactAtScale,
    average_daily_dollar_volume,
    breakeven_aum,
    capacity_curve,
    interpolate_crossing,
    realized_daily_volatility,
)

MONTHLY = Frequency.MONTHLY
MONTH_ENDS = pd.DatetimeIndex(["2020-01-31", "2020-02-29", "2020-03-31"])
DAYS = pd.bdate_range("2019-12-02", "2020-04-30")


def _constant_frames(
    adv: float = 1e7, vol: float = 0.02, assets: tuple[str, ...] = ("X", "Y")
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rend un volume et une volatilité constants sur les séances de 2020."""
    adv_frame = pd.DataFrame(adv, index=DAYS, columns=list(assets))
    vol_frame = pd.DataFrame(vol, index=DAYS, columns=list(assets))
    return adv_frame, vol_frame


def _single_trade_weights() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Un seul achat de 20 % sur X, tenu ensuite, sur des rendements nuls."""
    weights = pd.DataFrame({"X": [0.2, 0.2, 0.2], "Y": [0.0, 0.0, 0.0]}, index=MONTH_ENDS)
    returns = pd.DataFrame(0.0, index=MONTH_ENDS, columns=["X", "Y"])
    return weights, returns


def _context(date: str, columns: dict[str, pd.Series] | None = None) -> pd.DataFrame:
    """Rend un contexte minimal portant la date, comme le moteur le fait."""
    frame = pd.DataFrame(columns or {}, index=pd.Index(["X", "Y"]))
    frame.attrs["date"] = pd.Timestamp(date)
    return frame


# ---------------------------------------------------------------------------
# Le modèle de coût à une taille donnée
# ---------------------------------------------------------------------------


def test_impact_d_un_achat_de_vingt_pour_cent_a_la_main() -> None:
    """Source (a). Participation 0,2 M$ sur 10 M$ = 0,02, racine 0,141421.

    Impact unitaire 0,5 × 0,02 × 0,141421 = 0,00141421 ; coût 0,2 × cela =
    0,000282843, soit 2,82843 points de base. Payé une seule fois, à la
    période où la cible est détenue pour la première fois.
    """
    adv, vol = _constant_frames()
    weights, returns = _single_trade_weights()
    model = ImpactAtScale(aum=1e6, adv_dollars=adv, volatility=vol, coefficient=0.5)
    result = run_backtest(
        weights=weights, returns=returns, cost_model=model, execution_lag=1, frequency=MONTHLY
    )
    impact = result.cost_breakdown[IMPACT_COMPONENT]
    assert impact.loc["2020-02-29"] == pytest.approx(0.5 * 0.02 * 0.2 * math.sqrt(0.02), rel=1e-12)
    assert impact.loc["2020-02-29"] == pytest.approx(2.828427e-4, rel=1e-6)
    assert impact.loc["2020-01-31"] == 0.0
    assert impact.loc["2020-03-31"] == 0.0
    assert (
        SPREAD_COMPONENT not in result.cost_breakdown.columns
        or (result.cost_breakdown[SPREAD_COMPONENT] == 0).all()
    )


def test_le_demi_ecart_se_paie_sur_les_deux_cotes_et_ne_depend_pas_du_capital() -> None:
    """Source (a). 5 pb sur une rotation en somme entière de 0,2 = 1e-4 du capital."""
    adv, vol = _constant_frames()
    weights, returns = _single_trade_weights()
    for aum in (1e6, 1e9):
        model = ImpactAtScale(aum=aum, adv_dollars=adv, volatility=vol, coefficient=0.5, spread_bps=5.0)
        result = run_backtest(
            weights=weights, returns=returns, cost_model=model, execution_lag=1, frequency=MONTHLY
        )
        assert result.cost_breakdown[SPREAD_COMPONENT].loc["2020-02-29"] == pytest.approx(1e-4, rel=1e-12)
        assert result.costs.loc["2020-02-29"] == pytest.approx(
            1e-4 + result.cost_breakdown[IMPACT_COMPONENT].loc["2020-02-29"], rel=1e-12
        )


def _impact_bps(**kwargs: object) -> float:
    """Rend l'impact en points de base d'un achat de 20 % sur X, hors moteur."""
    adv, vol = _constant_frames(adv=float(kwargs.pop("adv", 1e7)))
    model = ImpactAtScale(adv_dollars=adv, volatility=vol, coefficient=1.0, **kwargs)  # type: ignore[arg-type]
    previous = pd.Series({"X": 0.0, "Y": 0.0})
    target = pd.Series({"X": 0.2, "Y": 0.0})
    return model.breakdown(previous=previous, target=target, context=_context("2020-02-14")).impact_bps


def test_quatre_fois_le_capital_double_l_impact() -> None:
    """Source (b) : l'impact croît en racine carrée du capital."""
    assert _impact_bps(aum=4e6) == pytest.approx(2.0 * _impact_bps(aum=1e6), rel=1e-12)


def test_etaler_sur_quatre_seances_divise_l_impact_par_deux() -> None:
    """Source (b) : la participation quotidienne est divisée par quatre, sa racine par deux."""
    assert _impact_bps(aum=1e6, execution_days=4) == pytest.approx(0.5 * _impact_bps(aum=1e6), rel=1e-12)


def test_doubler_le_volume_divise_l_impact_par_racine_de_deux() -> None:
    """Source (b)."""
    assert _impact_bps(aum=1e6, adv=2e7) == pytest.approx(_impact_bps(aum=1e6) / math.sqrt(2.0), rel=1e-12)


def test_le_modele_respecte_le_protocole_et_rend_deux_composantes() -> None:
    """Le moteur lit ``cost`` ; il rend un dictionnaire dont la somme est le total."""
    adv, vol = _constant_frames()
    model = ImpactAtScale(aum=1e6, adv_dollars=adv, volatility=vol, coefficient=0.5, spread_bps=5.0)
    assert isinstance(model, CostModel)
    previous = pd.Series({"X": 0.0, "Y": 0.0})
    target = pd.Series({"X": 0.2, "Y": 0.0})
    parts = model.cost(previous=previous, target=target, context=_context("2020-02-14"))
    detail = model.breakdown(previous=previous, target=target, context=_context("2020-02-14"))
    assert set(parts) == {SPREAD_COMPONENT, IMPACT_COMPONENT}
    assert sum(parts.values()) == pytest.approx(detail.total_fraction, rel=1e-12)
    assert parts[SPREAD_COMPONENT] == pytest.approx(5.0 * 0.2 / 10_000.0, rel=1e-12)


def test_sans_date_le_modele_refuse() -> None:
    """Un contexte sans date ne permet pas de lire le volume : erreur, pas zéro."""
    adv, vol = _constant_frames()
    model = ImpactAtScale(aum=1e6, adv_dollars=adv, volatility=vol)
    with pytest.raises(ConfigError, match="date"):
        model.breakdown(previous=pd.Series({"X": 0.0}), target=pd.Series({"X": 0.1}), context=None)


def test_avant_le_premier_volume_connu_le_modele_refuse() -> None:
    """Une date antérieure à tout volume connu lève ``InsufficientDataError``."""
    adv, vol = _constant_frames()
    model = ImpactAtScale(aum=1e6, adv_dollars=adv, volatility=vol)
    with pytest.raises(InsufficientDataError):
        model.breakdown(
            previous=pd.Series({"X": 0.0}), target=pd.Series({"X": 0.1}), context=_context("2010-01-04")
        )


def test_un_actif_negocie_sans_volume_leve() -> None:
    """Un volume manquant sur un actif négocié ne se chiffre pas à zéro en silence."""
    adv, vol = _constant_frames()
    adv.loc[:, "X"] = np.nan
    model = ImpactAtScale(aum=1e6, adv_dollars=adv, volatility=vol)
    with pytest.raises(DataQualityError):
        model.breakdown(
            previous=pd.Series({"X": 0.0}), target=pd.Series({"X": 0.1}), context=_context("2020-02-14")
        )


def test_une_sortie_de_cote_emprunte_le_dernier_volume_connu_si_demande() -> None:
    """Source (a). Le volume de X tombe à zéro puis manque ; le coût vaut celui du dernier volume positif.

    Au 2020-02-14 le dernier volume strictement positif de X est celui du
    2020-02-07, 5 M$ : participation 0,2 M$ sur 5 M$ = 0,04, racine 0,2, impact
    unitaire 0,5 × 0,02 × 0,2 = 0,002, coût 0,2 × 0,002 = 4 points de base.
    """
    adv, vol = _constant_frames()
    adv.loc["2020-02-03":"2020-02-07", "X"] = 5e6
    adv.loc["2020-02-10":"2020-02-12", "X"] = 0.0
    adv.loc["2020-02-13":, "X"] = np.nan
    strict = ImpactAtScale(aum=1e6, adv_dollars=adv, volatility=vol, coefficient=0.5)
    with pytest.raises(DataQualityError, match="X"):
        strict.breakdown(
            previous=pd.Series({"X": 0.0}), target=pd.Series({"X": 0.2}), context=_context("2020-02-14")
        )
    lenient = ImpactAtScale(
        aum=1e6, adv_dollars=adv, volatility=vol, coefficient=0.5, on_missing_liquidity="last_known"
    )
    parts = lenient.breakdown(
        previous=pd.Series({"X": 0.0}), target=pd.Series({"X": 0.2}), context=_context("2020-02-14")
    )
    assert parts.impact_bps == pytest.approx(4.0, rel=1e-12)
    assert lenient.participation_log[0]["n_last_known"] == 1
    assert lenient.last_known_share() == 1.0
    with pytest.raises(ConfigError):
        ImpactAtScale(aum=1e6, adv_dollars=adv, volatility=vol, on_missing_liquidity="ignore")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "bad", [{"aum": 0.0}, {"aum": -1.0}, {"aum": math.inf}, {"aum": 1e6, "execution_days": 0}]
)
def test_parametres_hors_domaine(bad: dict[str, float]) -> None:
    """Capital nul, négatif, infini, ou aucune séance d'exécution : refusés."""
    adv, vol = _constant_frames()
    with pytest.raises(ConfigError):
        ImpactAtScale(adv_dollars=adv, volatility=vol, **bad)  # type: ignore[arg-type]


def test_le_journal_de_participation_compte_les_ecretages() -> None:
    """Source (a). 0,2 × 1e9 / 1e7 = 20 de participation, au-dessus du plafond de 0,1."""
    adv, vol = _constant_frames()
    model = ImpactAtScale(aum=1e9, adv_dollars=adv, volatility=vol)
    model.breakdown(
        previous=pd.Series({"X": 0.0}), target=pd.Series({"X": 0.2}), context=_context("2020-02-14")
    )
    assert model.max_participation() == pytest.approx(20.0, rel=1e-12)
    assert model.clipped_share() == 1.0
    assert model.participation_log[0]["n_clipped"] == 1
    assert model.participation_log[0]["asset_max"] == "X"
    assert model.binding_assets() == [("X", pytest.approx(20.0))]


# ---------------------------------------------------------------------------
# Les deux entrées, sans regard sur l'avenir
# ---------------------------------------------------------------------------


def test_le_volume_moyen_ne_voit_pas_la_seance_du_jour() -> None:
    """Source (c). Un volume aberrant à la date t ne change la valeur qu'à partir de t+1."""
    index = pd.bdate_range("2020-01-01", periods=60)
    prices = pd.DataFrame(10.0, index=index, columns=["X"])
    volumes = pd.DataFrame(1e6, index=index, columns=["X"])
    calm = average_daily_dollar_volume(prices, volumes, window=21)
    spiked_volumes = volumes.copy()
    spiked_volumes.iloc[30, 0] = 1e9
    spiked = average_daily_dollar_volume(prices, spiked_volumes, window=21)
    assert calm.iloc[30, 0] == spiked.iloc[30, 0] == pytest.approx(1e7)
    assert spiked.iloc[31, 0] == calm.iloc[31, 0]  # la médiane absorbe une seule séance
    assert calm.iloc[:21, 0].isna().all()
    assert calm.iloc[21, 0] == pytest.approx(1e7)


def test_la_mediane_absorbe_une_seance_mais_pas_onze() -> None:
    """Source (c). Onze séances aberrantes sur vingt et une déplacent la médiane."""
    index = pd.bdate_range("2020-01-01", periods=60)
    prices = pd.DataFrame(10.0, index=index, columns=["X"])
    volumes = pd.DataFrame(1e6, index=index, columns=["X"])
    volumes.iloc[30:41, 0] = 1e9
    adv = average_daily_dollar_volume(prices, volumes, window=21)
    assert adv.iloc[41, 0] == pytest.approx(1e10)
    assert adv.iloc[30, 0] == pytest.approx(1e7)


def test_la_volatilite_alternee_vaut_x_racine_de_w_sur_w_moins_un() -> None:
    """Source (a). Sur ±x en alternance et une fenêtre paire, l'écart type vaut x √(w/(w-1))."""
    index = pd.bdate_range("2020-01-01", periods=60)
    x = 0.01
    returns = pd.DataFrame({"X": [x if i % 2 == 0 else -x for i in range(60)]}, index=index)
    vol = realized_daily_volatility(returns, window=20)
    assert vol.iloc[:20, 0].isna().all()
    assert vol.iloc[25, 0] == pytest.approx(x * math.sqrt(20 / 19), rel=1e-12)


def test_la_volatilite_constante_vaut_zero_et_ne_voit_pas_le_jour() -> None:
    """Source (c). Un choc à t n'entre dans la volatilité qu'à t+1."""
    index = pd.bdate_range("2020-01-01", periods=60)
    returns = pd.DataFrame(0.001, index=index, columns=["X"])
    returns.iloc[40, 0] = 0.2
    vol = realized_daily_volatility(returns, window=21)
    assert vol.iloc[40, 0] == pytest.approx(0.0, abs=1e-15)
    assert vol.iloc[41, 0] > 0.01


def test_prices_et_volumes_doivent_partager_leurs_actifs() -> None:
    """Deux tableaux d'actifs différents ne se multiplient pas en silence."""
    index = pd.bdate_range("2020-01-01", periods=30)
    with pytest.raises(ConfigError):
        average_daily_dollar_volume(
            pd.DataFrame(1.0, index=index, columns=["X"]), pd.DataFrame(1.0, index=index, columns=["Y"])
        )


# ---------------------------------------------------------------------------
# La forme fermée et l'interpolation
# ---------------------------------------------------------------------------


def test_forme_fermee_a_la_main() -> None:
    """Source (a). (0,002 - 0,0005) / 1e-6 = 1 500 ; au carré, 2,25 millions."""
    assert breakeven_aum(0.002, 0.0005, 1e-6) == pytest.approx(2.25e6, rel=1e-12)
    assert breakeven_aum(0.0004, 0.0005, 1e-6) == 0.0
    assert breakeven_aum(0.002, 0.0, 0.0) is None
    with pytest.raises(ConfigError):
        breakeven_aum(0.002, -0.1, 1e-6)
    with pytest.raises(ConfigError):
        breakeven_aum(math.nan, 0.0, 1e-6)


def test_interpolation_en_logarithme_a_la_main() -> None:
    """Source (a). Entre un million à +1 et cent millions à -1, zéro est à dix millions."""
    assert interpolate_crossing([1e6, 1e8], [1.0, -1.0]) == pytest.approx(1e7, rel=1e-12)
    assert interpolate_crossing([1e6, 1e8], [1.0, 0.5]) is None
    assert interpolate_crossing([1e6, 1e8], [-1.0, -2.0]) == 1e6
    assert interpolate_crossing([1e6, 1e7, 1e8], [3.0, 1.0, -1.0], threshold=0.0) == pytest.approx(
        math.sqrt(1e7 * 1e8)
    )
    with pytest.raises(ConfigError):
        interpolate_crossing([1e8, 1e6], [1.0, -1.0])


# ---------------------------------------------------------------------------
# La courbe entière, contrôlée par la forme fermée
# ---------------------------------------------------------------------------


def _random_case(
    seed: int, *, mean: float, n_months: int = 36
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Trois actifs, poids positifs qui bougent, rendements de moyenne déclarée."""
    g = make_generator(seed)
    months = pd.date_range("2018-01-31", periods=n_months, freq="ME")
    days = pd.bdate_range("2017-11-01", months[-1] + pd.Timedelta(days=5))
    assets = ["A", "B", "C"]
    weights = pd.DataFrame(g.uniform(0.1, 0.5, size=(n_months, 3)), index=months, columns=assets)
    returns = pd.DataFrame(g.normal(mean, 0.03, size=(n_months, 3)), index=months, columns=assets)
    adv = pd.DataFrame(g.uniform(5e7, 2e8, size=(len(days), 3)), index=days, columns=assets)
    vol = pd.DataFrame(g.uniform(0.01, 0.03, size=(len(days), 3)), index=days, columns=assets)
    return weights, returns, adv, vol


def test_le_moteur_retrouve_la_forme_fermee_quand_rien_n_est_ecrete() -> None:
    """Source (b). Net moyen = g - s - √A K, à la précision machine, et zéro au capital d'annulation.

    Le plafond de participation est relevé à 1 pour que rien ne soit écrêté,
    ce qui est la condition de validité de la forme fermée.
    """
    weights, returns, adv, vol = _random_case(1, mean=0.004)
    curve = capacity_curve(
        weights,
        returns,
        adv_dollars=adv,
        volatility=vol,
        frequency=MONTHLY,
        aum_grid=(1e5, 1e6, 1e7),
        coefficient=1.0,
        spread_bps=5.0,
        participation_cap=1.0,
    )
    for aum, row in curve.table.iterrows():
        closed = curve.gross_mean - curve.spread_mean - math.sqrt(float(aum)) * curve.impact_load_mean
        assert row["return_net_annual"] / 12.0 == pytest.approx(closed, abs=1e-14)
        assert row["status"] == "exact"
    assert curve.breakeven_aum is not None and curve.breakeven_aum > 0.0
    assert curve.breakeven_check == pytest.approx(0.0, abs=1e-12)
    assert curve.breakeven_clipped is False
    assert curve.capacity_aum == min(curve.breakeven_aum, curve.participation_cap_aum)
    assert curve.n_periods == 36


def test_le_sharpe_net_decroit_avec_la_taille() -> None:
    """Source (b). Un coût croissant en √A fait décroître le ratio de Sharpe net."""
    weights, returns, adv, vol = _random_case(2, mean=0.004)
    curve = capacity_curve(
        weights, returns, adv_dollars=adv, volatility=vol, frequency=MONTHLY, aum_grid=(1e5, 1e6, 1e7, 1e8)
    )
    sharpes = curve.table["sharpe_net"].to_numpy()
    assert (np.diff(sharpes) < 0).all()
    assert curve.sharpe_reference > sharpes[0]


def test_au_dela_du_plafond_le_moteur_est_optimiste_et_le_plafond_borne() -> None:
    """Source (b). Écrêter la participation minore le coût, donc le net du moteur au capital A* est positif.

    Un alpha élevé place A* là où la participation dépasse le plafond par
    défaut. Le contrôle ressort positif, et la capacité retenue est le capital
    où la plus grosse transaction atteint le plafond, qui se déduit de la
    participation au capital unité par une règle de trois : à ce capital, le
    moteur mesure une participation maximale égale au plafond, sans écrêtage.
    """
    weights, returns, adv, vol = _random_case(3, mean=0.02)
    curve = capacity_curve(
        weights, returns, adv_dollars=adv, volatility=vol, frequency=MONTHLY, aum_grid=(1e6, 1e8)
    )
    assert curve.breakeven_clipped is True
    assert curve.breakeven_check is not None and curve.breakeven_check > 0.0
    assert curve.participation_cap_aum is not None and curve.breakeven_aum is not None
    assert curve.participation_cap_aum < curve.breakeven_aum
    assert curve.capacity_aum == curve.participation_cap_aum
    assert any("plafond" in note for note in curve.notes)
    assert curve.binding_assets and curve.binding_assets[0][0] in {"A", "B", "C"}
    at_cap = ImpactAtScale(aum=curve.participation_cap_aum, adv_dollars=adv, volatility=vol)
    run_backtest(weights=weights, returns=returns, cost_model=at_cap, execution_lag=1, frequency=MONTHLY)
    assert at_cap.max_participation() == pytest.approx(curve.participation_cap, rel=1e-9)
    assert at_cap.clipped_share() == 0.0


def test_sans_transaction_la_capacite_n_est_pas_bornee() -> None:
    """Des poids nuls ne portent aucun impact : capacité ``None`` et note explicite."""
    weights, returns, adv, vol = _random_case(4, mean=0.004)
    zeros = weights * 0.0
    curve = capacity_curve(
        zeros, returns, adv_dollars=adv, volatility=vol, frequency=MONTHLY, aum_grid=(1e6, 1e7)
    )
    assert curve.breakeven_aum is None
    assert curve.capacity_aum is None
    assert curve.impact_load_mean == 0.0
    assert math.isnan(curve.sharpe_reference)
    assert any("bornée" in note for note in curve.notes)


def test_alpha_deja_negatif_donne_une_capacite_nulle() -> None:
    """Un brut négatif en moyenne ne se sauve à aucune taille : capacité zéro."""
    weights, returns, adv, vol = _random_case(5, mean=-0.01)
    curve = capacity_curve(
        weights, returns, adv_dollars=adv, volatility=vol, frequency=MONTHLY, aum_grid=(1e6, 1e7)
    )
    assert curve.breakeven_aum == 0.0
    assert curve.breakeven_check is None
    assert curve.half_sharpe_aum is None


def test_grille_invalide_refusee() -> None:
    """Une grille vide, décroissante ou négative est refusée avant tout calcul."""
    weights, returns, adv, vol = _random_case(6, mean=0.004)
    for grid in ((), (1e7, 1e6), (-1.0, 1e6)):
        with pytest.raises(ConfigError):
            capacity_curve(
                weights, returns, adv_dollars=adv, volatility=vol, frequency=MONTHLY, aum_grid=grid
            )


def test_le_resume_est_serialisable_et_declare_le_statut() -> None:
    """Le résumé porte le statut modélisé et les notes en liste."""
    weights, returns, adv, vol = _random_case(7, mean=0.004)
    curve = capacity_curve(
        weights, returns, adv_dollars=adv, volatility=vol, frequency=MONTHLY, aum_grid=(1e6, 1e7)
    )
    summary = curve.summary()
    assert summary["status"] == "modélisé"
    assert isinstance(summary["notes"], list)
    assert summary["frequency"] == "monthly"


def test_la_figure_de_capacite_rend_la_table_tracee() -> None:
    """La figure rend la table qu'elle dessine et déduit son titre des données."""
    weights, returns, adv, vol = _random_case(8, mean=0.004)
    curve = capacity_curve(
        weights, returns, adv_dollars=adv, volatility=vol, frequency=MONTHLY, aum_grid=(1e5, 1e6, 1e7, 1e8)
    )
    fig, drawn = capacity_plot(
        curve.table,
        breakeven_aum=curve.breakeven_aum,
        half_sharpe_aum=curve.half_sharpe_aum,
        capacity_aum=curve.capacity_aum,
    )
    assert list(drawn.index) == list(curve.table.index)
    assert {"return_net_annual", "sharpe_net"} <= set(drawn.columns)
    assert "Capacité" in fig.axes[0].get_title()

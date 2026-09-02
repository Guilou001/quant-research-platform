"""Contrôles de ``quantlab.models``.

Aucune valeur attendue ne vient de la sortie du code. Chacune porte sa source
en commentaire : (a) calcul à la main, (b) identité mathématique, (c) propriété
de construction des données, (d) bibliothèque indépendante.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm

from quantlab.core.determinism import make_generator
from quantlab.core.errors import ConfigError, InsufficientDataError
from quantlab.core.protocols import AlphaModel
from quantlab.models.cross_sectional import (
    FittedModel,
    fit_model,
    permutation_importance,
    select_config,
    spec_from_config,
    walk_forward_predict,
)
from quantlab.models.evaluation import (
    diebold_mariano,
    oos_r2,
    predictions_to_wide,
    r2_by_date,
    squared_errors,
)
from quantlab.models.panel import (
    LABEL_NAME,
    Panel,
    make_panel,
    price_features,
    rank_features,
    to_long,
    to_wide,
)
from quantlab.validation.splits import ExpandingSplit

SEED = 20260902


def _long_index(n_dates: int, n_entities: int) -> pd.MultiIndex:
    dates = pd.date_range("2015-01-31", periods=n_dates, freq="ME")
    entities = [f"E{k:03d}" for k in range(n_entities)]
    return pd.MultiIndex.from_product([dates, entities], names=["date", "entity"])


def _linear_world(seed: int, n_dates: int = 100, n_entities: int = 30, noise: float = 0.02):
    """Trois caractéristiques normales, une étiquette linéaire dans les deux premières."""
    g = make_generator(seed)
    index = _long_index(n_dates, n_entities)
    x = pd.DataFrame(g.normal(size=(len(index), 3)), index=index, columns=["x1", "x2", "x3"])
    returns_next = 0.05 * x["x1"] - 0.03 * x["x2"] + g.normal(0.0, noise, len(index))
    # le rendement de t+1 est l'étiquette de t : on le range dans le tableau large à t+1
    wide_next = to_wide(returns_next.rename("r"))
    returns = wide_next.shift(1)
    return x, returns


# ---------------------------------------------------------------------------
# Le panneau
# ---------------------------------------------------------------------------


def test_le_rang_transversal_a_la_main() -> None:
    """Source (a). 10, 20, 30 rendent -1, 0, 1 ; un manquant rend 0 ; deux égaux partagent le rang."""
    index = _long_index(1, 4)
    features = pd.DataFrame({"a": [10.0, 20.0, 30.0, np.nan], "b": [5.0, 5.0, 1.0, 9.0]}, index=index)
    ranked = rank_features(features)
    assert ranked["a"].tolist() == pytest.approx([-1.0, 0.0, 1.0, 0.0])
    # b : rangs moyens 2,5 / 2,5 / 1 / 4 sur n = 4 -> 2(r-1)/3 - 1
    assert ranked["b"].tolist() == pytest.approx([0.0, 0.0, -1.0, 1.0])
    assert not ranked.isna().any().any()


def test_le_rang_ne_lit_pas_les_autres_dates() -> None:
    """Source (c). Changer une date ne change aucune autre date."""
    x, _ = _linear_world(1, n_dates=6, n_entities=10)
    before = rank_features(x)
    x2 = x.copy()
    x2.loc[(x2.index.get_level_values("date")[-1], slice(None)), :] *= 100.0
    after = rank_features(x2)
    dates = before.index.get_level_values("date")
    last = dates.max()
    pd.testing.assert_frame_equal(before[dates < last], after[dates < last])


def test_l_etiquette_est_le_rendement_du_mois_suivant() -> None:
    """Source (a). Sur un tableau connu, l'étiquette de t vaut le rendement de t+1 ; la dernière date n'en a pas."""
    dates = pd.date_range("2020-01-31", periods=3, freq="ME")
    returns = pd.DataFrame({"A": [0.01, 0.02, 0.03], "B": [-0.01, -0.02, -0.03]}, index=dates)
    features = to_long(returns, "f").to_frame()
    panel = make_panel(features, returns)
    assert panel.label.loc[(dates[0], "A")] == pytest.approx(0.02)
    assert panel.label.loc[(dates[1], "B")] == pytest.approx(-0.03)
    assert np.isnan(panel.label.loc[(dates[2], "A")])
    assert panel.label.name == LABEL_NAME
    assert len(panel.observed().label) == 4
    with pytest.raises(ConfigError):
        make_panel(features, returns, horizon=0)


def test_le_panneau_refuse_un_index_desaligne() -> None:
    """Caractéristiques et étiquette doivent partager le même index."""
    index = _long_index(2, 2)
    features = pd.DataFrame({"f": 0.0}, index=index)
    label = pd.Series(0.0, index=index[:-1], name=LABEL_NAME)
    with pytest.raises(ConfigError):
        Panel(features, label)


def test_les_caracteristiques_de_prix_a_la_main_et_sans_fuite() -> None:
    """Source (a) et (c). Sur 1 % par mois, mom_12_1 vaut 1,01^11 - 1 ; perturber l'avenir ne change pas le passé."""
    dates = pd.date_range("2015-01-31", periods=40, freq="ME")
    returns = pd.DataFrame({"A": 0.01, "B": 0.02}, index=dates)
    feats = price_features(returns)
    row = feats.loc[(dates[20], "A")]
    assert row["mom_12_1"] == pytest.approx(1.01**11 - 1.0, rel=1e-12)
    assert row["rev_1"] == pytest.approx(0.01)
    assert row["vol_12"] == pytest.approx(0.0, abs=1e-15)
    assert row["max_12"] == pytest.approx(0.01)
    assert np.isnan(feats.loc[(dates[5], "A"), "mom_36_13"])
    g = make_generator(3)
    noisy = pd.DataFrame(g.normal(0.0, 0.05, size=(40, 2)), index=dates, columns=["A", "B"])
    base = price_features(noisy)
    shocked = noisy.copy()
    shocked.iloc[25:] += 0.5
    after = price_features(shocked)
    cut = dates[24]
    d = base.index.get_level_values("date")
    pd.testing.assert_frame_equal(base[d <= cut], after[d <= cut])


def test_la_taille_est_le_log_de_la_capitalisation() -> None:
    """Source (a). log(1e9) = 20,723."""
    dates = pd.date_range("2015-01-31", periods=3, freq="ME")
    returns = pd.DataFrame({"A": 0.0}, index=dates)
    equity = pd.DataFrame({"A": [1e9, 1e9, 0.0]}, index=dates)
    feats = price_features(returns, equity)
    assert feats.loc[(dates[0], "A"), "size"] == pytest.approx(math.log(1e9))
    assert np.isnan(feats.loc[(dates[2], "A"), "size"])


# ---------------------------------------------------------------------------
# L'évaluation
# ---------------------------------------------------------------------------


def test_r2_hors_echantillon_a_la_main() -> None:
    """Source (a). Exact rend 1, zéro rend 0, r + 1 sur (1, 2, 3) rend 1 - 3/14."""
    y = pd.Series([1.0, 2.0, 3.0], index=pd.RangeIndex(3))
    assert oos_r2(y, y) == pytest.approx(1.0)
    assert oos_r2(y, y * 0.0) == pytest.approx(0.0)
    assert oos_r2(y, y + 1.0) == pytest.approx(1.0 - 3.0 / 14.0)
    assert oos_r2(y, y + 1.0, center=2.0) == pytest.approx(1.0 - 3.0 / 2.0)
    with pytest.raises(InsufficientDataError):
        oos_r2(y * 0.0, y)


def test_r2_par_date_et_erreurs_carrees() -> None:
    """Source (a). Deux dates, l'une prévue exactement, l'autre prévue à zéro."""
    index = _long_index(2, 2)
    y = pd.Series([0.1, -0.1, 0.2, 0.1], index=index)
    p = pd.Series([0.1, -0.1, 0.0, 0.0], index=index)
    by_date = r2_by_date(y, p)
    assert by_date.iloc[0] == pytest.approx(1.0)
    assert by_date.iloc[1] == pytest.approx(0.0)
    assert squared_errors(y, p).sum() == pytest.approx(0.05)
    wide = predictions_to_wide(p)
    assert wide.shape == (2, 2)


def test_diebold_mariano_egal_au_t_hac_de_statsmodels() -> None:
    """Source (d). La statistique égale le t d'une régression de d sur une constante, HAC de Bartlett."""
    g = make_generator(5)
    n = 120
    d = np.zeros(n)
    for t in range(1, n):
        d[t] = 0.5 * d[t - 1] + g.normal(0.0, 1.0)
    d += 0.3
    dates = pd.date_range("2010-01-31", periods=n, freq="ME")
    loss_a = pd.Series(d + 1.0, index=dates)
    loss_b = pd.Series(1.0, index=dates)
    lags = 4
    ours = diebold_mariano(loss_a, loss_b, lags=lags)
    fit = sm.OLS(d, np.ones((n, 1))).fit(cov_type="HAC", cov_kwds={"maxlags": lags, "use_correction": False})
    assert ours.statistic == pytest.approx(float(fit.tvalues[0]), rel=1e-9)
    assert ours.mean_difference == pytest.approx(d.mean())
    assert ours.n_periods == n and ours.lags == lags


def test_diebold_mariano_pertes_identiques_et_panneau() -> None:
    """Des pertes identiques rendent zéro et p = 1 ; un panneau (date, titre) est moyenné par date."""
    index = _long_index(12, 5)
    g = make_generator(6)
    loss = pd.Series(g.uniform(0.0, 1.0, len(index)), index=index)
    same = diebold_mariano(loss, loss.copy())
    assert same.statistic == 0.0 and same.pvalue == 1.0
    worse = diebold_mariano(loss + 0.5, loss)
    assert worse.statistic > 3.0 and worse.mean_difference == pytest.approx(0.5)
    with pytest.raises(InsufficientDataError):
        diebold_mariano(loss.iloc[:20], loss.iloc[:20] * 2)


# ---------------------------------------------------------------------------
# Les modèles et l'analyse glissante
# ---------------------------------------------------------------------------


def test_le_modele_ajuste_satisfait_le_protocole() -> None:
    """Un modèle ajusté porte un nom et une méthode predict ; une colonne absente est refusée."""
    x, returns = _linear_world(7, n_dates=12, n_entities=10)
    panel = make_panel(x, returns).observed()
    spec = spec_from_config("ridge", [{"alpha": 1.0}], seed=SEED)
    model = fit_model(spec, spec.grid[0], panel.features, panel.label)
    assert isinstance(model, FittedModel)
    assert isinstance(model, AlphaModel)
    assert model.predict(panel.features).shape[0] == len(panel.label)
    with pytest.raises(ConfigError):
        model.predict(panel.features.drop(columns=["x3"]))
    with pytest.raises(ConfigError):
        spec_from_config("inconnu", None, seed=SEED)


def test_la_selection_ne_retient_jamais_la_penalite_absurde() -> None:
    """Source (c). Une pénalité de 1e9 annule la prévision ; la validation choisit l'autre."""
    x, returns = _linear_world(8, n_dates=60, n_entities=20)
    panel = make_panel(x, returns).observed()
    spec = spec_from_config("ridge", [{"alpha": 1e9}, {"alpha": 1e-3}], seed=SEED)
    choice = select_config(spec, panel, panel.dates, validation_periods=12, purge=1)
    assert choice.chosen_index == 1
    assert choice.validation_r2[1] > choice.validation_r2[0]
    assert choice.n_validation_dates == 12
    with pytest.raises(InsufficientDataError):
        select_config(spec, panel, panel.dates[:10], validation_periods=12, purge=1)


def test_l_analyse_glissante_retrouve_une_relation_lineaire_hors_echantillon() -> None:
    """Source (c). R² hors échantillon élevé sur une étiquette linéaire, plis strictement chronologiques."""
    x, returns = _linear_world(9, n_dates=100, n_entities=30)
    panel = make_panel(x, returns)
    spec = spec_from_config("ridge", [{"alpha": 1e-3}, {"alpha": 1.0}], seed=SEED)
    split = ExpandingSplit(train_size=48, test_size=12, purge=1)
    out = walk_forward_predict(panel, spec, split, validation_periods=12)
    assert len(out.folds) == 4
    for f in out.folds:
        assert f.train_end < f.test_start
        assert f.test_r2 > 0.3
    realized = panel.label.reindex(out.predictions.index)
    assert oos_r2(realized, out.predictions) > 0.3
    assert set(out.predictions.index.get_level_values("date")) <= set(panel.dates[48:])
    assert out.last_model.name == "ridge"
    report = out.report()
    assert list(report.columns)[:2] == ["train_start", "train_end"]


def test_les_arbres_captent_une_relation_que_le_lineaire_ne_voit_pas() -> None:
    """Source (c). Étiquette en x1², sans corrélation linéaire : ridge près de zéro, arbres nettement positifs."""
    g = make_generator(10)
    index = _long_index(80, 40)
    x = pd.DataFrame(g.normal(size=(len(index), 2)), index=index, columns=["x1", "x2"])
    ranked_x1 = rank_features(x)["x1"]
    label_next = 0.05 * (ranked_x1**2 - 1.0 / 3.0) + g.normal(0.0, 0.01, len(index))
    returns = to_wide(label_next.rename("r")).shift(1)
    panel = make_panel(x, returns)
    split = ExpandingSplit(train_size=40, test_size=20, purge=1)
    ridge = walk_forward_predict(
        panel, spec_from_config("ridge", [{"alpha": 1.0}], seed=SEED), split, validation_periods=6
    )
    trees = walk_forward_predict(
        panel,
        spec_from_config("gbrt", [{"max_depth": 3, "max_iter": 100, "learning_rate": 0.1}], seed=SEED),
        split,
        validation_periods=6,
    )
    realized = panel.label
    r2_ridge = oos_r2(realized.reindex(ridge.predictions.index), ridge.predictions)
    r2_trees = oos_r2(realized.reindex(trees.predictions.index), trees.predictions)
    assert abs(r2_ridge) < 0.15
    assert r2_trees > 0.5
    assert trees.family == "tree" and trees.n_configs == 1
    last = trees.folds[-1]
    last_rows = panel.rows_at(panel.dates[(panel.dates >= last.test_start) & (panel.dates <= last.test_end)])
    importance = permutation_importance(
        trees.last_model, panel.features.iloc[last_rows], panel.label.iloc[last_rows], seed=SEED, n_repeats=3
    )
    assert importance.index[0] == "x1"
    assert importance.loc["x1", "importance"] > 5.0 * abs(importance.loc["x2", "importance"])

"""Les tests du portage, et la convention de cotation qu'ils gardent.

Trois familles de tests. La première garde le SENS de cotation, celui qui
inverse le signe du portage quand on se trompe, et elle le garde jusque dans le
fichier de configuration de l'étude 008. La deuxième garde la causalité, un
décalage d'exécution d'une période et pas zéro. La troisième vérifie la
régression de panel contre une régression à variables muettes calculée
autrement, et ses erreurs types groupées contre statsmodels.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm
import yaml

from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.features.transforms import assert_causal
from quantlab.strategies.carry import (
    bond_slope_carry,
    carry_portfolio,
    carry_signal,
    currency_excess_return,
    dollar_decomposition,
    modified_duration,
    momentum_signal,
    month_end_sample,
    panel_carry_regression,
    portfolio_carry,
    rank_weights,
    sign_weights,
    smoothed_signal,
    tercile_weights,
    to_usd_per_unit,
    weights_from_signal,
)

RACINE = Path(__file__).resolve().parents[2]
CONFIG_008 = RACINE / "studies" / "008_carry" / "config.yaml"


def _mois(n: int, debut: str = "2000-01-31") -> pd.DatetimeIndex:
    """Rend un index de n fins de mois."""
    return pd.date_range(debut, periods=n, freq="ME")


def _panel(n_mois: int = 60, n_actifs: int = 5, graine: int = 7) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rend un couple signal et rendement où le portage passe entièrement au prix."""
    generateur = np.random.default_rng(graine)
    index = _mois(n_mois)
    noms = [f"A{i}" for i in range(n_actifs)]
    signal = pd.DataFrame(generateur.normal(0.0, 0.003, size=(n_mois, n_actifs)), index=index, columns=noms)
    bruit = pd.DataFrame(generateur.normal(0.0, 0.02, size=(n_mois, n_actifs)), index=index, columns=noms)
    rendement = signal.shift(1) + bruit
    return signal, rendement


# --------------------------------------------------------------------------- #
# 1. La convention de cotation
# --------------------------------------------------------------------------- #


def test_cotation_directe_est_rendue_telle_quelle() -> None:
    """Une série déjà cotée en dollars par unité n'est pas touchée."""
    serie = pd.Series([1.30, 1.25], index=_mois(2))
    pd.testing.assert_series_equal(to_usd_per_unit(serie, "usd_per_unit"), serie)


def test_cotation_inverse_est_retournee() -> None:
    """Une série cotée en unités par dollar est retournée, et une seule fois."""
    serie = pd.Series([100.0, 125.0], index=_mois(2))
    obtenu = to_usd_per_unit(serie, "unit_per_usd")
    assert obtenu.tolist() == pytest.approx([0.01, 0.008])


def test_cotation_inconnue_leve() -> None:
    """Un sens de cotation non déclaré lève, il ne se devine pas."""
    serie = pd.Series([1.0], index=_mois(1))
    with pytest.raises(ConfigError, match="sens de cotation"):
        to_usd_per_unit(serie, "par_hasard")  # type: ignore[arg-type]


def test_cotation_negative_leve() -> None:
    """Une cotation nulle ou négative interdit l'inversion et lève."""
    serie = pd.Series([1.0, 0.0], index=_mois(2))
    with pytest.raises(DataQualityError):
        to_usd_per_unit(serie, "unit_per_usd")


def test_le_sens_declare_dans_la_configuration_suit_le_nom_fred() -> None:
    """Le sens déclaré dans l'étude 008 suit la règle de nommage de FRED.

    C'est le test qui garde la convention. Une série ``DEXUS??`` cote des
    dollars par unité étrangère, une série ``DEX??US`` cote l'inverse. Une
    inversion de ce tableau retournerait le signe du portage sans casser aucun
    autre test.
    """
    config = yaml.safe_load(CONFIG_008.read_text(encoding="utf-8"))
    fautifs: list[str] = []
    for devise, bloc in config["params"]["spot_series"].items():
        nom = str(bloc["series"])
        attendu = "usd_per_unit" if nom.startswith("DEXUS") else "unit_per_usd"
        if bloc["quote"] != attendu:
            fautifs.append(f"{devise} : {nom} déclaré {bloc['quote']} au lieu de {attendu}")
    assert not fautifs, "sens de cotation faux :\n" + "\n".join(fautifs)


def test_le_portage_monte_avec_le_taux_etranger() -> None:
    """Un taux étranger au-dessus du taux local rend un portage positif."""
    index = _mois(1)
    haut = pd.Series([0.05], index=index)
    bas = pd.Series([0.02], index=index)
    assert float(carry_signal(haut, bas).iloc[0]) > 0.0
    assert float(carry_signal(bas, haut).iloc[0]) < 0.0


def test_la_formule_du_portage_est_celle_de_l_equation_sept() -> None:
    """Le portage vaut l'écart mensuel divisé par un plus le taux local mensuel."""
    index = _mois(1)
    obtenu = float(carry_signal(pd.Series([0.05], index=index), pd.Series([0.02], index=index)).iloc[0])
    attendu = (0.05 - 0.02) / 12.0 / (1.0 + 0.02 / 12.0)
    assert obtenu == pytest.approx(attendu, rel=1e-12)


# --------------------------------------------------------------------------- #
# 2. Le rendement de change
# --------------------------------------------------------------------------- #


def test_le_rendement_vaut_le_portage_quand_le_change_ne_bouge_pas() -> None:
    """À change constant, le rendement en excès se réduit à l'écart de taux."""
    index = _mois(3)
    spot = pd.Series([1.0, 1.0, 1.0], index=index)
    etranger = pd.Series([0.05] * 3, index=index)
    local = pd.Series([0.02] * 3, index=index)
    obtenu = currency_excess_return(spot, etranger, local)
    assert obtenu.iloc[1] == pytest.approx((0.05 - 0.02) / 12.0, rel=1e-12)


def test_une_appreciation_de_la_devise_ajoute_au_rendement() -> None:
    """Une devise qui s'apprécie en dollars ajoute sa variation au rendement."""
    index = _mois(2)
    taux = pd.Series([0.0, 0.0], index=index)
    monte = currency_excess_return(pd.Series([1.0, 1.1], index=index), taux, taux)
    baisse = currency_excess_return(pd.Series([1.0, 0.9], index=index), taux, taux)
    assert float(monte.iloc[-1]) == pytest.approx(0.1, rel=1e-12)
    assert float(baisse.iloc[-1]) == pytest.approx(-0.1, rel=1e-12)


def test_inverser_la_cotation_inverse_le_signe_du_rendement() -> None:
    """Se tromper de sens de cotation retourne le signe de la variation de change.

    C'est la démonstration de ce que garde le test de configuration. La série
    brute et la série inversée donnent des rendements de signes opposés.
    """
    index = _mois(2)
    taux = pd.Series([0.0, 0.0], index=index)
    brut = pd.Series([100.0, 110.0], index=index)
    juste = currency_excess_return(to_usd_per_unit(brut, "unit_per_usd"), taux, taux)
    faux = currency_excess_return(to_usd_per_unit(brut, "usd_per_unit"), taux, taux)
    assert float(juste.iloc[-1]) < 0.0
    assert float(faux.iloc[-1]) > 0.0


def test_le_mois_retient_la_derniere_seance() -> None:
    """L'échantillonnage mensuel retient la dernière séance connue du mois."""
    index = pd.to_datetime(["2020-01-02", "2020-01-31", "2020-02-03", "2020-02-27"])
    serie = pd.Series([1.0, 2.0, 3.0, 4.0], index=index)
    obtenu = month_end_sample(serie)
    assert obtenu.tolist() == [2.0, 4.0]
    assert obtenu.index.tolist() == pd.to_datetime(["2020-01-31", "2020-02-29"]).tolist()


def test_le_mois_refuse_une_serie_vide() -> None:
    """Une série sans observation valide lève au lieu de rendre un vide."""
    serie = pd.Series([np.nan, np.nan], index=_mois(2))
    with pytest.raises(InsufficientDataError):
        month_end_sample(serie)


# --------------------------------------------------------------------------- #
# 3. Les poids
# --------------------------------------------------------------------------- #


def test_les_poids_par_rang_somment_a_zero_et_pesent_deux() -> None:
    """Le tri par rang est à somme nulle et d'exposition brute imposée."""
    signal, _ = _panel()
    poids = rank_weights(signal, gross=2.0)
    assert poids.sum(axis=1).abs().max() == pytest.approx(0.0, abs=1e-12)
    assert poids.abs().sum(axis=1).min() == pytest.approx(2.0, rel=1e-12)


def test_l_exposition_brute_ne_depend_pas_du_nombre_d_actifs() -> None:
    """Retirer un actif ne change pas l'exposition brute totale."""
    signal, _ = _panel(n_actifs=6)
    complet = rank_weights(signal, gross=2.0).abs().sum(axis=1)
    ampute = rank_weights(signal.drop(columns=["A5"]), gross=2.0).abs().sum(axis=1)
    assert complet.max() == pytest.approx(2.0, rel=1e-12)
    assert ampute.max() == pytest.approx(2.0, rel=1e-12)


def test_le_plus_fort_portage_est_long_et_le_plus_faible_court() -> None:
    """Le tri place le portage le plus haut du côté long."""
    index = _mois(1)
    signal = pd.DataFrame([[0.001, 0.005, -0.002]], index=index, columns=["a", "b", "c"])
    poids = rank_weights(signal, gross=2.0)
    assert float(poids.loc[index[0], "b"]) > 0.0
    assert float(poids.loc[index[0], "c"]) < 0.0


def test_une_date_trop_maigre_rend_des_poids_nuls() -> None:
    """Une date où trop peu d'actifs cotent ne prend aucune position."""
    index = _mois(2)
    signal = pd.DataFrame(
        [[0.001, np.nan, np.nan], [0.001, 0.002, 0.003]], index=index, columns=["a", "b", "c"]
    )
    poids = rank_weights(signal, gross=2.0, min_assets=2)
    assert poids.loc[index[0]].abs().sum() == pytest.approx(0.0)
    assert poids.loc[index[1]].abs().sum() == pytest.approx(2.0)


def test_les_poids_de_calendrier_sont_de_signe_constant() -> None:
    """La stratégie de calendrier ne prend que des positions unitaires."""
    signal, _ = _panel()
    poids = sign_weights(signal, gross=2.0)
    non_nuls = poids.to_numpy()[np.abs(poids.to_numpy()) > 1e-12]
    assert np.allclose(np.abs(non_nuls), np.abs(non_nuls).max())


def test_le_tri_par_tiers_concentre_les_positions() -> None:
    """Le tri par tiers laisse des actifs à poids nul, le tri par rang non."""
    index = _mois(1)
    signal = pd.DataFrame([[1.0, 2.0, 3.0, 4.0, 5.0, 6.0]], index=index, columns=list("abcdef"))
    tiers = tercile_weights(signal, gross=2.0)
    rang = rank_weights(signal, gross=2.0)
    assert int((tiers.loc[index[0]].abs() < 1e-12).sum()) == 2
    assert int((rang.loc[index[0]].abs() < 1e-12).sum()) == 0


def test_le_schema_inconnu_leve() -> None:
    """Un schéma de pondération non prévu lève au lieu de retomber sur un défaut."""
    signal, _ = _panel()
    with pytest.raises(ConfigError, match="schéma"):
        weights_from_signal(signal, scheme="au_pif")  # type: ignore[arg-type]


def test_le_portage_du_portefeuille_est_positif() -> None:
    """Le portage du portefeuille trié par portage est positif, équation (22)."""
    signal, _ = _panel()
    poids = rank_weights(signal, gross=2.0)
    assert float(portfolio_carry(poids, signal).min()) > 0.0


# --------------------------------------------------------------------------- #
# 4. La causalité
# --------------------------------------------------------------------------- #


def test_le_decalage_nul_est_refuse() -> None:
    """Un décalage d'exécution nul lève, il ne se négocie pas."""
    signal, rendement = _panel()
    with pytest.raises(ConfigError, match="execution_lag"):
        carry_portfolio(signal, rendement, execution_lag=0)


def test_perturber_le_futur_ne_change_pas_le_passe() -> None:
    """Modifier le signal après une date laisse les rendements antérieurs intacts."""
    signal, rendement = _panel()
    coupure = signal.index[40]
    reference = carry_portfolio(signal, rendement).returns
    perturbe = signal.copy()
    perturbe.loc[perturbe.index > coupure] += 0.05
    obtenu = carry_portfolio(perturbe, rendement).returns
    pd.testing.assert_series_equal(
        reference.loc[reference.index <= coupure], obtenu.loc[obtenu.index <= coupure]
    )


def test_retirer_le_futur_ne_change_pas_le_passe() -> None:
    """Tronquer l'échantillon laisse les rendements passés identiques."""
    signal, rendement = _panel()
    coupure = signal.index[40]
    reference = carry_portfolio(signal, rendement).returns
    court = carry_portfolio(
        signal.loc[signal.index <= coupure], rendement.loc[rendement.index <= coupure]
    ).returns
    pd.testing.assert_series_equal(reference.loc[court.index], court)


def test_le_poids_applique_est_celui_du_mois_precedent() -> None:
    """Le poids qui multiplie le rendement du mois est formé le mois d'avant."""
    signal, rendement = _panel()
    resultat = carry_portfolio(signal, rendement, execution_lag=1)
    date = resultat.weights.index[10]
    precedente = signal.index[signal.index.get_loc(date) - 1]
    pd.testing.assert_series_equal(
        resultat.weights.loc[date], resultat.raw_weights.loc[precedente], check_names=False
    )


def test_le_momentum_ne_lit_pas_le_futur() -> None:
    """Le signal de momentum passe le contrôle de causalité par troncature."""
    _, rendement = _panel(n_mois=80)
    assert_causal(
        lambda x: momentum_signal(x, lookback=12),
        rendement,
        name="momentum_signal",
    )


def test_le_saut_de_la_variante_carry_deux_treize_decale_bien() -> None:
    """La variante qui saute un mois n'emploie aucune valeur du mois courant."""
    index = _mois(15)
    signal = pd.DataFrame({"a": np.arange(15, dtype=float)}, index=index)
    sans_saut = smoothed_signal(signal, window=12, skip=0)
    avec_saut = smoothed_signal(signal, window=12, skip=1)
    assert float(sans_saut.iloc[11, 0]) == pytest.approx(np.mean(np.arange(12)))
    assert float(avec_saut.iloc[12, 0]) == pytest.approx(np.mean(np.arange(12)))


def test_la_fenetre_de_lissage_doit_etre_positive() -> None:
    """Une fenêtre nulle lève au lieu de rendre une moyenne vide."""
    signal, _ = _panel()
    with pytest.raises(ConfigError):
        smoothed_signal(signal, window=0)


# --------------------------------------------------------------------------- #
# 5. La régression de panel
# --------------------------------------------------------------------------- #


def _lsdv(signal: pd.DataFrame, rendement: pd.DataFrame) -> sm.regression.linear_model.RegressionResults:
    """Ajuste la même régression avec des variables muettes explicites."""
    decale = signal.shift(1)
    long_x = decale.melt(ignore_index=False, var_name="entity", value_name="x")
    long_y = rendement.melt(ignore_index=False, var_name="entity", value_name="y")
    panel = pd.concat(
        [long_y.set_index("entity", append=True), long_x.set_index("entity", append=True)], axis=1
    ).dropna()
    panel = panel.reset_index()
    panel.columns = ["period", "entity", "y", "x"]
    muettes_entite = pd.get_dummies(panel["entity"], prefix="e", drop_first=False, dtype=float)
    muettes_date = pd.get_dummies(panel["period"], prefix="d", drop_first=True, dtype=float)
    design = pd.concat([panel[["x"]], muettes_entite, muettes_date], axis=1)
    return sm.OLS(panel["y"].to_numpy(), design.to_numpy()).fit(
        cov_type="cluster", cov_kwds={"groups": panel["period"].to_numpy()}
    )


def test_le_coefficient_egale_celui_des_variables_muettes() -> None:
    """L'estimateur intra-groupe rend exactement le coefficient à variables muettes."""
    signal, rendement = _panel(n_mois=48, n_actifs=4)
    obtenu = panel_carry_regression(signal, rendement)
    attendu = _lsdv(signal, rendement)
    assert obtenu.coefficient == pytest.approx(float(attendu.params[0]), rel=1e-8)


def test_l_erreur_type_groupee_egale_celle_de_statsmodels() -> None:
    """L'erreur type groupée par date se retrouve à la sixième décimale."""
    signal, rendement = _panel(n_mois=48, n_actifs=4)
    obtenu = panel_carry_regression(signal, rendement, cluster="time")
    attendu = _lsdv(signal, rendement)
    assert obtenu.stderr == pytest.approx(float(attendu.bse[0]), rel=1e-6)


def test_un_portage_entierement_repris_rend_un_coefficient_de_un() -> None:
    """Quand le rendement vaut le portage plus un bruit, le coefficient vaut un."""
    generateur = np.random.default_rng(11)
    index = _mois(400)
    noms = [f"A{i}" for i in range(6)]
    signal = pd.DataFrame(generateur.normal(0.0, 0.01, size=(400, 6)), index=index, columns=noms)
    bruit = pd.DataFrame(generateur.normal(0.0, 0.005, size=(400, 6)), index=index, columns=noms)
    rendement = signal.shift(1) + bruit
    resultat = panel_carry_regression(signal, rendement)
    assert resultat.coefficient == pytest.approx(1.0, abs=0.05)
    assert abs(resultat.tstat_vs_one) < 2.0


def test_un_portage_entierement_annule_rend_un_coefficient_nul() -> None:
    """Quand la variation de change annule le portage, le coefficient vaut zéro."""
    generateur = np.random.default_rng(12)
    index = _mois(400)
    noms = [f"A{i}" for i in range(6)]
    signal = pd.DataFrame(generateur.normal(0.0, 0.01, size=(400, 6)), index=index, columns=noms)
    bruit = pd.DataFrame(generateur.normal(0.0, 0.005, size=(400, 6)), index=index, columns=noms)
    rendement = bruit
    resultat = panel_carry_regression(signal, rendement)
    assert resultat.coefficient == pytest.approx(0.0, abs=0.05)


def test_le_panel_refuse_un_decalage_nul() -> None:
    """La régression de panel refuse elle aussi un décalage nul."""
    signal, rendement = _panel()
    with pytest.raises(ConfigError):
        panel_carry_regression(signal, rendement, execution_lag=0)


def test_le_panel_leve_si_le_portage_ne_varie_plus() -> None:
    """Un portage identique pour tous et à toute date ne peut rien identifier."""
    index = _mois(24)
    signal = pd.DataFrame(1.0, index=index, columns=["a", "b"])
    rendement = pd.DataFrame(0.01, index=index, columns=["a", "b"])
    with pytest.raises(InsufficientDataError):
        panel_carry_regression(signal, rendement)


def test_les_effets_fixes_de_date_retirent_le_mouvement_commun() -> None:
    """Ajouter un choc commun à toutes les devises ne bouge pas le coefficient."""
    signal, rendement = _panel(n_mois=120, n_actifs=5)
    sans = panel_carry_regression(signal, rendement, time_fixed_effects=True)
    generateur = np.random.default_rng(3)
    choc = pd.Series(generateur.normal(0.0, 0.05, size=len(rendement)), index=rendement.index)
    avec = panel_carry_regression(signal, rendement.add(choc, axis=0), time_fixed_effects=True)
    assert avec.coefficient == pytest.approx(sans.coefficient, rel=1e-8)


# --------------------------------------------------------------------------- #
# 6. La substitution obligataire
# --------------------------------------------------------------------------- #


def test_la_duration_modifiee_suit_sa_formule_fermee() -> None:
    """La duration modifiée d'une obligation au pair suit la formule annoncée."""
    taux = pd.Series([0.05], index=_mois(1))
    attendu = (1.0 - (1.05) ** (-10.0)) / 0.05
    assert float(modified_duration(taux, maturity_years=10.0).iloc[0]) == pytest.approx(attendu, rel=1e-12)


def test_la_duration_a_taux_nul_vaut_l_echeance() -> None:
    """À taux nul, la duration modifiée se réduit à l'échéance."""
    taux = pd.Series([0.0], index=_mois(1))
    assert float(modified_duration(taux, maturity_years=7.0).iloc[0]) == pytest.approx(7.0)


def test_le_portage_obligataire_vaut_la_pente_mensuelle() -> None:
    """Le portage approché vaut la pente de la courbe ramenée au mois."""
    index = _mois(2)
    long = pd.Series([0.04, 0.04], index=index)
    court = pd.Series([0.01, 0.01], index=index)
    tableau = bond_slope_carry(long, court, maturity_years=10.0)
    assert float(tableau["carry"].iloc[0]) == pytest.approx(0.03 / 12.0, rel=1e-12)
    assert float(tableau["excess_return"].iloc[1]) == pytest.approx(0.03 / 12.0, rel=1e-12)


def test_une_hausse_de_taux_fait_perdre_l_obligation() -> None:
    """Une hausse du taux long retire au rendement l'effet de duration."""
    index = _mois(2)
    long = pd.Series([0.04, 0.05], index=index)
    court = pd.Series([0.04, 0.04], index=index)
    tableau = bond_slope_carry(long, court, maturity_years=10.0)
    duree = float(modified_duration(long, maturity_years=10.0).iloc[0])
    assert float(tableau["excess_return"].iloc[1]) == pytest.approx(-duree * 0.01, rel=1e-12)


# --------------------------------------------------------------------------- #
# 7. Les contrôles d'entrée
# --------------------------------------------------------------------------- #


def test_un_index_non_trie_leve() -> None:
    """Un index dans le désordre lève plutôt que de produire un décalage faux."""
    index = pd.to_datetime(["2020-02-29", "2020-01-31"])
    signal = pd.DataFrame({"a": [1.0, 2.0]}, index=index)
    with pytest.raises(DataQualityError):
        rank_weights(signal)


def test_une_date_en_double_leve() -> None:
    """Deux lignes à la même date lèvent, le décalage n'aurait plus de sens."""
    index = pd.to_datetime(["2020-01-31", "2020-01-31"])
    signal = pd.DataFrame({"a": [1.0, 2.0]}, index=index)
    with pytest.raises(DataQualityError):
        rank_weights(signal)


def test_aucune_colonne_commune_leve() -> None:
    """Un signal et des rendements sans actif commun lèvent."""
    index = _mois(12)
    signal = pd.DataFrame({"a": np.arange(12.0)}, index=index)
    rendement = pd.DataFrame({"b": np.arange(12.0)}, index=index)
    with pytest.raises(InsufficientDataError):
        carry_portfolio(signal, rendement)


# --------------------------------------------------------------------------- #
# 8. La décomposition en jambe neutre au dollar et jambe de dollar
# --------------------------------------------------------------------------- #


def test_les_deux_jambes_redonnent_le_rendement_total() -> None:
    """La somme des deux jambes vaut le rendement total, à la précision machine."""
    signal, rendement = _panel(n_mois=60, n_actifs=5)
    signal["USD"] = 0.0
    rendement["USD"] = 0.0
    resultat = carry_portfolio(signal, rendement, min_assets=3)
    disponible = signal.notna().shift(1).fillna(value=False)
    parts = dollar_decomposition(resultat.weights, rendement, disponible)
    ecart = (parts["dollar_neutral"] + parts["dollar"] - parts["total"]).abs().max()
    assert float(ecart) < 1e-12


def test_la_jambe_neutre_ne_porte_aucun_pari_sur_le_dollar() -> None:
    """Les poids de la jambe neutre somment à zéro sur les devises étrangères."""
    index = _mois(3)
    poids = pd.DataFrame(
        [[0.5, -0.3, 0.2, -0.4], [0.1, 0.1, -0.1, -0.1], [0.6, -0.2, -0.1, -0.3]],
        index=index,
        columns=["a", "b", "c", "USD"],
    )
    rendement = pd.DataFrame(
        [[0.01, 0.02, -0.01, 0.0], [0.0, 0.01, 0.02, 0.0], [-0.02, 0.01, 0.0, 0.0]],
        index=index,
        columns=["a", "b", "c", "USD"],
    )
    disponible = pd.DataFrame(True, index=index, columns=["a", "b", "c", "USD"])
    parts = dollar_decomposition(poids, rendement, disponible)
    net = poids[["a", "b", "c"]].sum(axis=1)
    panier = rendement[["a", "b", "c"]].mean(axis=1)
    pd.testing.assert_series_equal(parts["dollar"], (net * panier).rename("dollar"))


def test_un_portefeuille_sans_exposition_nette_a_une_jambe_de_dollar_nulle() -> None:
    """Quand les poids étrangers somment déjà à zéro, la jambe de dollar disparaît."""
    index = _mois(2)
    poids = pd.DataFrame([[0.5, -0.5, 0.0], [0.25, -0.25, 0.0]], index=index, columns=["a", "b", "USD"])
    rendement = pd.DataFrame([[0.01, -0.02, 0.0], [0.03, 0.01, 0.0]], index=index, columns=["a", "b", "USD"])
    disponible = pd.DataFrame(True, index=index, columns=["a", "b", "USD"])
    parts = dollar_decomposition(poids, rendement, disponible)
    assert parts["dollar"].abs().max() == pytest.approx(0.0, abs=1e-15)


def test_la_colonne_du_numeraire_est_exigee() -> None:
    """Une décomposition sans colonne de numéraire lève au lieu de deviner."""
    index = _mois(2)
    poids = pd.DataFrame([[0.5, -0.5], [0.25, -0.25]], index=index, columns=["a", "b"])
    rendement = pd.DataFrame([[0.01, -0.02], [0.03, 0.01]], index=index, columns=["a", "b"])
    disponible = pd.DataFrame(True, index=index, columns=["a", "b"])
    with pytest.raises(ConfigError, match="numéraire"):
        dollar_decomposition(poids, rendement, disponible)


def test_l_identite_tient_meme_avec_un_rendement_manquant() -> None:
    """Un rendement manquant sur une devise négociable ne brise pas l'identité.

    Le contrôle est nécessaire, un panier calculé en ignorant le manquant et une
    jambe neutre le comblant à zéro ne se compensant plus.
    """
    index = _mois(2)
    poids = pd.DataFrame([[0.5, -0.3, -0.2], [0.4, -0.1, -0.3]], index=index, columns=["a", "b", "USD"])
    rendement = pd.DataFrame([[0.01, np.nan, 0.0], [0.02, 0.01, 0.0]], index=index, columns=["a", "b", "USD"])
    disponible = pd.DataFrame(True, index=index, columns=["a", "b", "USD"])
    parts = dollar_decomposition(poids, rendement, disponible)
    ecart = (parts["dollar_neutral"] + parts["dollar"] - parts["total"]).abs().max()
    assert float(ecart) < 1e-15


def test_le_numeraire_classe_laisse_une_exposition_nette_aux_autres() -> None:
    """Classer le numéraire avec les autres actifs ouvre un pari sur lui.

    L'article classe des contrats de change, tous libellés contre le dollar, et
    le dollar n'y est donc pas classable. Lui donner une colonne de portage nul
    lui vaut un rang, donc un poids, donc une exposition nette sur les autres
    devises. Ce test mesure cette exposition plutôt que de la supposer nulle.
    """
    index = _mois(3)
    etrangeres = pd.DataFrame(
        [[0.004, 0.001, -0.003], [0.005, 0.002, -0.002], [0.006, 0.002, -0.001]],
        index=index,
        columns=["a", "b", "c"],
    )
    avec = etrangeres.assign(USD=0.0)
    poids_avec = rank_weights(avec, gross=2.0, min_assets=2)
    poids_sans = rank_weights(etrangeres, gross=2.0, min_assets=2)
    net_avec = poids_avec[["a", "b", "c"]].sum(axis=1)
    net_sans = poids_sans.sum(axis=1)
    assert float(net_sans.abs().max()) < 1e-15
    assert float(net_avec.abs().min()) > 0.05
    assert float((net_avec + poids_avec["USD"]).abs().max()) < 1e-15


def test_le_numeraire_compte_dans_le_plancher_d_actifs() -> None:
    """Le numéraire fait passer le plancher, donc il crée des mois investis.

    Une date qui ne porte que trois devises étrangères est trop maigre pour un
    plancher de quatre. La colonne du numéraire la fait passer, et le
    portefeuille commence alors plus tôt qu'un univers de contrats seuls.
    """
    index = _mois(2)
    etrangeres = pd.DataFrame(
        [[0.004, 0.001, -0.003], [0.005, 0.000, -0.002]], index=index, columns=["a", "b", "c"]
    )
    avec = etrangeres.assign(USD=0.0)
    assert float(rank_weights(etrangeres, gross=2.0, min_assets=4).abs().to_numpy().sum()) == 0.0
    assert float(rank_weights(avec, gross=2.0, min_assets=4).abs().to_numpy().sum()) > 0.0


def test_retirer_le_numeraire_change_le_portefeuille_de_l_etude() -> None:
    """Les deux univers ne rendent pas la même série, et l'écart se mesure.

    Le contrôle garde le constat publié dans ``numeraire_variant.csv`` : la
    série à onze actifs et la série à dix actifs diffèrent, donc le choix du
    numéraire est un écart avec l'article et non une convention d'écriture.
    """
    signal, rendement = _panel(n_mois=90, n_actifs=4, graine=11)
    avec = signal.assign(USD=0.0)
    rendement_avec = rendement.assign(USD=0.0)
    onze = carry_portfolio(avec, rendement_avec, scheme="rank", gross=2.0, min_assets=2).returns.dropna()
    dix = carry_portfolio(signal, rendement, scheme="rank", gross=2.0, min_assets=2).returns.dropna()
    commun = onze.index.intersection(dix.index)
    assert float((onze.loc[commun] - dix.loc[commun]).abs().max()) > 1e-6

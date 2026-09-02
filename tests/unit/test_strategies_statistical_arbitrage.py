"""Les contrôles du module d'arbitrage statistique.

Chaque valeur attendue vient d'un calcul à la main, d'une propriété
mathématique, ou d'une implémentation indépendante de NumPy. Aucune ne vient de
la sortie du code, ce qui verrouillerait le défaut au lieu de l'attraper.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from quantlab.core.determinism import make_generator
from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.strategies.statistical_arbitrage import (
    PAPER_CHARACTERISTIC_DAYS,
    PAPER_RULE,
    SURVIVORSHIP_BIAS_RISK,
    TRADING_DAYS_PER_YEAR,
    OrnsteinUhlenbeckFit,
    TradingRule,
    characteristic_time_days,
    eigen_portfolios,
    hedged_dollar_weights,
    market_hedged_book,
    mean_reversion_half_life,
    ornstein_uhlenbeck_fit,
    residual_regression,
    s_scores,
    statistical_arbitrage_weights,
    update_positions,
)


def _panel(n_dates: int, n_assets: int, seed: int) -> pd.DataFrame:
    """Fabrique un panneau de rendements à structure factorielle connue."""
    generator = make_generator(seed)
    common = generator.normal(0.0, 0.01, size=(n_dates, 3))
    loadings = generator.normal(1.0, 0.3, size=(3, n_assets))
    noise = generator.normal(0.0, 0.008, size=(n_dates, n_assets))
    values = common @ loadings + noise
    index = pd.bdate_range("2000-01-03", periods=n_dates)
    columns = [f"A{i:03d}" for i in range(n_assets)]
    return pd.DataFrame(values, index=index, columns=columns)


# --------------------------------------------------------------------------- #
# Le drapeau de biais du survivant
# --------------------------------------------------------------------------- #


def test_le_biais_du_survivant_est_declare() -> None:
    """Le module affiche le risque au lieu de le taire."""
    assert SURVIVORSHIP_BIAS_RISK is True


# --------------------------------------------------------------------------- #
# Les deux temps de retour à la moyenne
# --------------------------------------------------------------------------- #


def test_demi_vie_dune_annee() -> None:
    """Une vitesse égale au logarithme de deux rend une demi-vie d'un an."""
    assert mean_reversion_half_life(math.log(2.0)) == pytest.approx(252.0)


def test_demi_vie_de_vingt_et_un_jours() -> None:
    """La demi-vie se divise quand la vitesse se multiplie."""
    kappa = math.log(2.0) * 252.0 / 21.0
    assert mean_reversion_half_life(kappa) == pytest.approx(21.0)


def test_seuil_de_larticle_en_seances() -> None:
    """Le seuil publié, 252 sur 30, vaut exactement trente séances."""
    assert characteristic_time_days(252.0 / 30.0) == pytest.approx(PAPER_CHARACTERISTIC_DAYS)


def test_temps_caracteristique_negatif_absent() -> None:
    """Une vitesse nulle ou négative ne définit aucun temps de retour."""
    out = characteristic_time_days(np.array([-1.0, 0.0, 252.0]))
    assert np.isnan(out[0]) and np.isnan(out[1])
    assert out[2] == pytest.approx(1.0)


def test_demi_vie_vaut_ln_deux_fois_le_temps_caracteristique() -> None:
    """Les deux mesures diffèrent exactement du facteur logarithme de deux."""
    kappa = np.array([4.0, 8.4, 30.0])
    ratio = mean_reversion_half_life(kappa) / characteristic_time_days(kappa)
    assert ratio == pytest.approx(np.full(3, math.log(2.0)))


# --------------------------------------------------------------------------- #
# Les portefeuilles propres
# --------------------------------------------------------------------------- #


def test_valeurs_propres_de_deux_titres() -> None:
    """Sur deux titres, les valeurs propres valent un plus et un moins la corrélation.

    La corrélation de référence vient de ``numpy.corrcoef``, implémentation
    indépendante de celle du module.
    """
    generator = make_generator(11)
    data = generator.normal(0.0, 0.01, size=(400, 2))
    rho = float(np.corrcoef(data, rowvar=False)[0, 1])
    decomposition = eigen_portfolios(data, n_components=2)
    assert decomposition.eigenvalues[0] == pytest.approx(1.0 + abs(rho))
    assert decomposition.eigenvalues[1] == pytest.approx(1.0 - abs(rho))


def test_poids_du_portefeuille_propre_divise_par_la_volatilite() -> None:
    """Le poids vaut le coefficient du vecteur propre divisé par l'écart type."""
    generator = make_generator(12)
    data = generator.normal(0.0, 0.01, size=(300, 4))
    decomposition = eigen_portfolios(data, n_components=2)
    volatilities = data.std(axis=0, ddof=1)
    attendu = (decomposition.eigenvectors / volatilities[:, None]).T
    assert decomposition.weights == pytest.approx(attendu)


def test_part_de_variance_expliquee() -> None:
    """La part retenue est la somme des valeurs propres sur leur trace.

    La trace d'une matrice de corrélation vaut le nombre de titres, ce qui donne
    un dénominateur connu sans passer par le code.
    """
    generator = make_generator(13)
    data = generator.normal(0.0, 0.01, size=(300, 5))
    decomposition = eigen_portfolios(data, n_components=2)
    assert decomposition.variance_share == pytest.approx(decomposition.eigenvalues.sum() / 5.0)


def test_nombre_variable_de_facteurs() -> None:
    """Le critère de variance retient le plus petit nombre qui atteint la cible."""
    generator = make_generator(14)
    common = generator.normal(0.0, 0.02, size=(300, 1))
    data = common @ np.ones((1, 6)) + generator.normal(0.0, 0.002, size=(300, 6))
    decomposition = eigen_portfolios(data, variance_share=0.55)
    assert decomposition.n_components == 1
    assert decomposition.variance_share >= 0.55


def test_deux_criteres_refuses() -> None:
    """Donner les deux critères, ou aucun, lève."""
    data = make_generator(15).normal(0.0, 0.01, size=(50, 3))
    with pytest.raises(ConfigError):
        eigen_portfolios(data, n_components=2, variance_share=0.5)
    with pytest.raises(ConfigError):
        eigen_portfolios(data)


def test_fenetre_trouee_refusee() -> None:
    """Une valeur manquante dans la fenêtre lève au lieu d'être comblée."""
    data = make_generator(16).normal(0.0, 0.01, size=(50, 3))
    data[10, 1] = np.nan
    with pytest.raises(DataQualityError):
        eigen_portfolios(data, n_components=2)


def test_titre_de_volatilite_nulle_refuse() -> None:
    """Un titre constant n'a pas de corrélation, et le module le dit."""
    data = make_generator(17).normal(0.0, 0.01, size=(50, 3))
    data[:, 2] = 0.0
    with pytest.raises(DataQualityError):
        eigen_portfolios(data, n_components=2)


def test_univers_trop_petit_refuse() -> None:
    """Un seul titre ne porte aucune matrice de corrélation."""
    with pytest.raises(InsufficientDataError):
        eigen_portfolios(np.zeros((50, 1)), n_components=1)


# --------------------------------------------------------------------------- #
# La régression résiduelle
# --------------------------------------------------------------------------- #


def test_residu_nul_sur_une_combinaison_exacte() -> None:
    """Un titre qui est exactement une combinaison des facteurs n'a pas de résidu."""
    generator = make_generator(21)
    factors = generator.normal(0.0, 0.01, size=(60, 3))
    returns = factors @ np.array([[1.0, 0.5], [-0.2, 0.3], [0.7, -0.1]])
    _, _, cumulative = residual_regression(returns, factors)
    assert np.abs(cumulative).max() < 1e-12


def test_derive_annualisee_retrouvee() -> None:
    """L'ordonnée à l'origine se retrouve multipliée par 252."""
    generator = make_generator(22)
    factors = generator.normal(0.0, 0.01, size=(60, 2))
    returns = 0.0004 + factors @ np.array([[1.0], [0.5]])
    _, drift, _ = residual_regression(returns, factors)
    assert drift[0] == pytest.approx(0.0004 * TRADING_DAYS_PER_YEAR)


def test_residu_cumule_finit_a_zero() -> None:
    """La régression force la somme des résidus à zéro, artefact déclaré."""
    generator = make_generator(23)
    factors = generator.normal(0.0, 0.01, size=(60, 3))
    returns = generator.normal(0.0, 0.01, size=(60, 5))
    _, _, cumulative = residual_regression(returns, factors)
    assert np.abs(cumulative[-1]).max() < 1e-12


def test_longueurs_incompatibles_refusees() -> None:
    """Des fenêtres de longueurs différentes lèvent."""
    with pytest.raises(ConfigError):
        residual_regression(np.zeros((60, 2)), np.zeros((30, 2)))


# --------------------------------------------------------------------------- #
# L'estimation du processus de retour à la moyenne
# --------------------------------------------------------------------------- #


def test_autoregression_exacte_sans_bruit() -> None:
    """Une trajectoire sans bruit rend exactement ses deux coefficients.

    La suite est construite à la main par la récurrence de paramètres 0,2 et
    0,5. Le bruit étant nul, la variance résiduelle l'est aussi, donc le titre
    est déclaré non stationnaire par le plancher de variance.
    """
    serie = [0.0]
    for _ in range(30):
        serie.append(0.2 + 0.5 * serie[-1])
    fit = ornstein_uhlenbeck_fit(np.array(serie)[:, None])
    assert fit.intercept[0] == pytest.approx(0.2)
    assert fit.ar1_slope[0] == pytest.approx(0.5)
    assert not bool(fit.stationary[0])


def test_coefficients_confrontes_a_polyfit() -> None:
    """Les coefficients coïncident avec ceux de ``numpy.polyfit``."""
    generator = make_generator(31)
    serie = np.zeros(200)
    bruit = generator.normal(0.0, 0.01, size=200)
    for k in range(1, 200):
        serie[k] = 0.05 + 0.8 * serie[k - 1] + bruit[k]
    fit = ornstein_uhlenbeck_fit(serie[:, None])
    pente, ordonnee = np.polyfit(serie[:-1], serie[1:], 1)
    assert fit.ar1_slope[0] == pytest.approx(pente)
    assert fit.intercept[0] == pytest.approx(ordonnee)


def test_identites_du_processus() -> None:
    """Les quatre identités de l'annexe A tiennent sur les valeurs rendues."""
    generator = make_generator(32)
    serie = np.zeros((300, 2))
    for k in range(1, 300):
        serie[k] = 0.02 + 0.7 * serie[k - 1] + generator.normal(0.0, 0.01, size=2)
    fit = ornstein_uhlenbeck_fit(serie)
    b = fit.ar1_slope
    assert fit.kappa == pytest.approx(-np.log(b) * TRADING_DAYS_PER_YEAR)
    assert fit.equilibrium == pytest.approx(fit.intercept / (1.0 - b))
    assert fit.sigma_eq == pytest.approx(np.sqrt(fit.residual_variance / (1.0 - b**2)))
    assert fit.sigma == pytest.approx(fit.sigma_eq * np.sqrt(2.0 * fit.kappa))


def test_vitesse_retrouvee_sur_un_processus_simule() -> None:
    """Sur un long échantillon, la vitesse estimée approche la vitesse vraie.

    La suite est simulée avec une pente de 0,9, donc une vitesse vraie de moins
    le logarithme de 0,9 fois 252, soit 26,6 par an.
    """
    generator = make_generator(33)
    serie = np.zeros(20000)
    for k in range(1, 20000):
        serie[k] = 0.9 * serie[k - 1] + generator.normal(0.0, 0.01)
    fit = ornstein_uhlenbeck_fit(serie[:, None])
    attendu = -math.log(0.9) * TRADING_DAYS_PER_YEAR
    assert fit.kappa[0] == pytest.approx(attendu, rel=0.05)


def test_pente_hors_intervalle_declaree_non_stationnaire() -> None:
    """Une pente négative ou supérieure à un ne définit aucun retour à la moyenne."""
    marche = np.cumsum(np.ones(50))[:, None]
    fit = ornstein_uhlenbeck_fit(marche)
    assert not bool(fit.stationary[0])
    assert np.isnan(fit.kappa[0])


def test_fenetre_trop_courte_refusee() -> None:
    """Trois points ne suffisent pas à estimer une pente et une variance."""
    with pytest.raises(InsufficientDataError):
        ornstein_uhlenbeck_fit(np.zeros((3, 2)))


# --------------------------------------------------------------------------- #
# Le s-score
# --------------------------------------------------------------------------- #


def _fit_construit(equilibres: list[float], sigmas: list[float], kappas: list[float]) -> OrnsteinUhlenbeckFit:
    """Fabrique un ajustement à la main, pour tester la seule formule du s-score."""
    n = len(equilibres)
    return OrnsteinUhlenbeckFit(
        intercept=np.zeros(n),
        ar1_slope=np.full(n, 0.5),
        kappa=np.array(kappas, dtype=float),
        equilibrium=np.array(equilibres, dtype=float),
        sigma=np.ones(n),
        sigma_eq=np.array(sigmas, dtype=float),
        residual_variance=np.ones(n),
        stationary=np.ones(n, dtype=bool),
    )


def test_s_score_centre_calcule_a_la_main() -> None:
    """Deux titres d'équilibres 1 et 3 et d'écarts types 1 et 2 rendent 1 et -0,5."""
    fit = _fit_construit([1.0, 3.0], [1.0, 2.0], [10.0, 10.0])
    assert s_scores(fit) == pytest.approx(np.array([1.0, -0.5]))


def test_s_score_sans_centrage() -> None:
    """Sans centrage, le s-score vaut l'opposé de l'équilibre réduit."""
    fit = _fit_construit([1.0, 3.0], [1.0, 2.0], [10.0, 10.0])
    assert s_scores(fit, centre_across_names=False) == pytest.approx(np.array([-1.0, -1.5]))


def test_s_score_modifie_retire_la_derive() -> None:
    """Le s-score modifié retranche la dérive divisée par vitesse et écart type."""
    fit = _fit_construit([1.0, 3.0], [1.0, 2.0], [10.0, 5.0])
    derive = np.array([0.5, 1.0])
    attendu = np.array([1.0 - 0.5 / (10.0 * 1.0), -0.5 - 1.0 / (5.0 * 2.0)])
    assert s_scores(fit, drift=derive) == pytest.approx(attendu)


def test_titre_non_stationnaire_sans_s_score() -> None:
    """Un titre rejeté par la stationnarité ne porte aucun score."""
    fit = _fit_construit([1.0, 3.0], [1.0, 2.0], [10.0, 10.0])
    fit = OrnsteinUhlenbeckFit(**{**fit.__dict__, "stationary": np.array([True, False])})
    scores = s_scores(fit)
    assert np.isnan(scores[1])
    assert scores[0] == pytest.approx(0.0)


# --------------------------------------------------------------------------- #
# La règle tout ou rien
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("avant", "score", "attendu"),
    [
        (0.0, -1.30, 1.0),
        (0.0, -1.25, 0.0),
        (0.0, -1.20, 0.0),
        (1.0, -1.00, 1.0),
        (1.0, -0.51, 1.0),
        (1.0, -0.40, 0.0),
        (0.0, 1.30, -1.0),
        (0.0, 1.25, 0.0),
        (-1.0, 0.90, -1.0),
        (-1.0, 0.76, -1.0),
        (-1.0, 0.70, 0.0),
    ],
)
def test_table_de_la_regle(avant: float, score: float, attendu: float) -> None:
    """La table de l'équation (16) se déroule à la main, cas par cas."""
    sortie = update_positions(np.array([avant]), np.array([score]), np.array([True]), PAPER_RULE)
    assert sortie[0] == pytest.approx(attendu)


def test_titre_hors_filtre_ferme_sa_position() -> None:
    """Le modèle rejeté ferme la position, comme l'écrit la page 771."""
    sortie = update_positions(np.array([1.0]), np.array([-2.0]), np.array([False]), PAPER_RULE)
    assert sortie[0] == 0.0


def test_score_absent_ferme_la_position() -> None:
    """Un s-score manquant ne laisse pas la position ouverte par défaut."""
    sortie = update_positions(np.array([-1.0]), np.array([np.nan]), np.array([True]), PAPER_RULE)
    assert sortie[0] == 0.0


def test_position_ne_souvre_pas_et_se_ferme_le_meme_jour() -> None:
    """Une règle dont la sortie dépasse l'entrée est refusée à la construction."""
    with pytest.raises(ConfigError):
        TradingRule(name="absurde", open_long=1.0, close_long=1.5)
    with pytest.raises(ConfigError):
        TradingRule(name="absurde", open_short=1.0, close_short=1.5)


def test_regle_sans_nom_refusee() -> None:
    """Une règle anonyme ne peut pas nommer sa colonne dans un tableau."""
    with pytest.raises(ConfigError):
        TradingRule(name="  ")


# --------------------------------------------------------------------------- #
# La couverture par les facteurs
# --------------------------------------------------------------------------- #


def test_couverture_parfaite_annule_le_poids() -> None:
    """Un titre couvert par lui-même à bêta un laisse un poids exactement nul."""
    poids = hedged_dollar_weights(np.array([1.0]), np.array([[1.0]]), np.array([[1.0]]), gross_leverage=4.0)
    assert poids == pytest.approx(np.zeros(1))


def test_couverture_calculee_a_la_main() -> None:
    """Deux titres, un facteur équipondéré, bêtas de 0,5 : le poids vaut deux et moins deux."""
    poids = hedged_dollar_weights(
        np.array([1.0, 0.0]),
        np.array([[0.5], [0.5]]),
        np.array([[1.0, 1.0]]),
        gross_leverage=4.0,
    )
    assert poids == pytest.approx(np.array([2.0, -2.0]))


def test_exposition_brute_atteinte() -> None:
    """La normalisation rend exactement l'exposition brute demandée."""
    generator = make_generator(41)
    positions = np.sign(generator.normal(size=20))
    betas = generator.normal(0.0, 0.5, size=(20, 3))
    factors = generator.normal(0.0, 1.0, size=(3, 20))
    poids = hedged_dollar_weights(positions, betas, factors, gross_leverage=4.0)
    assert float(np.abs(poids).sum()) == pytest.approx(4.0)


def test_aucune_position_rend_des_poids_nuls() -> None:
    """Un jour sans position ouverte ne porte aucun poids."""
    poids = hedged_dollar_weights(np.zeros(5), np.zeros((5, 2)), np.zeros((2, 5)), gross_leverage=4.0)
    assert poids == pytest.approx(np.zeros(5))


def test_levier_negatif_refuse() -> None:
    """Une exposition brute nulle ou négative n'a pas de sens."""
    with pytest.raises(ConfigError):
        hedged_dollar_weights(np.zeros(2), np.zeros((2, 1)), np.zeros((1, 2)), gross_leverage=0.0)


def test_dimensions_incompatibles_refusees() -> None:
    """Un bêta par titre de plus que de positions lève."""
    with pytest.raises(ConfigError):
        hedged_dollar_weights(np.zeros(2), np.zeros((3, 1)), np.zeros((1, 2)), gross_leverage=1.0)
    with pytest.raises(ConfigError):
        hedged_dollar_weights(np.zeros(2), np.zeros((2, 2)), np.zeros((1, 2)), gross_leverage=1.0)


# --------------------------------------------------------------------------- #
# La chaîne complète, et son absence d'information future
# --------------------------------------------------------------------------- #


def _chaine(returns: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
    """Déroule la chaîne avec les réglages courts des tests et rend les poids."""
    parametres: dict[str, object] = {
        "rules": [PAPER_RULE],
        "correlation_window": 60,
        "estimation_window": 20,
        "n_components": 3,
        "min_names": 8,
    }
    parametres.update(kwargs)
    return statistical_arbitrage_weights(returns, **parametres).weights[PAPER_RULE.name]  # type: ignore[arg-type]


def test_troncature_ne_change_rien_au_passe() -> None:
    """La chaîne rebâtie sur un échantillon tronqué rend les mêmes poids.

    C'est la preuve d'absence d'information future qu'aucun décalage ne donne :
    une statistique de fin d'échantillon changerait les valeurs passées.
    """
    panneau = _panel(240, 12, seed=51)
    complet = _chaine(panneau)
    tronque = _chaine(panneau.iloc[:200])
    commun = tronque.index
    assert np.nanmax(np.abs((complet.loc[commun] - tronque).to_numpy())) == pytest.approx(0.0, abs=1e-15)


def test_perturber_lavenir_ne_change_pas_le_present() -> None:
    """Modifier les rendements postérieurs à une date laisse ses poids intacts."""
    panneau = _panel(240, 12, seed=52)
    reference = _chaine(panneau)
    coupure = panneau.index[180]
    perturbe = panneau.copy()
    perturbe.loc[perturbe.index > coupure] += 0.05
    obtenu = _chaine(perturbe)
    ecart = (reference.loc[:coupure] - obtenu.loc[:coupure]).abs().to_numpy()
    assert np.nanmax(ecart) == pytest.approx(0.0, abs=1e-15)


def test_perturber_le_present_change_le_present() -> None:
    """Contrôle inverse : sans lui, une fonction constante passerait le test précédent."""
    panneau = _panel(240, 12, seed=53)
    reference = _chaine(panneau)
    coupure = panneau.index[180]
    perturbe = panneau.copy()
    perturbe.loc[perturbe.index >= coupure] += 0.05
    obtenu = _chaine(perturbe)
    ecart = (reference.loc[coupure] - obtenu.loc[coupure]).abs()
    assert float(np.nanmax(ecart.to_numpy())) > 1e-9


def test_exposition_brute_des_jours_negocies() -> None:
    """Tout jour portant une position ouverte porte l'exposition brute visée."""
    panneau = _panel(200, 12, seed=54)
    resultat = statistical_arbitrage_weights(
        panneau,
        rules=[PAPER_RULE],
        correlation_window=60,
        estimation_window=20,
        n_components=3,
        min_names=8,
        gross_leverage=4.0,
    )
    poids = resultat.weights[PAPER_RULE.name]
    ouverts = resultat.n_positions[PAPER_RULE.name] > 0
    brut = poids.abs().sum(axis=1)
    assert brut[ouverts].to_numpy() == pytest.approx(np.full(int(ouverts.sum()), 4.0))


def test_jours_sans_decision_sont_manquants() -> None:
    """Une réestimation tous les cinq jours laisse quatre lignes vides sur cinq."""
    panneau = _panel(200, 12, seed=55)
    poids = _chaine(panneau, reestimation_days=5)
    decides = poids.notna().any(axis=1)
    positions_decidees = np.flatnonzero(decides.to_numpy())
    assert np.all(np.diff(positions_decidees) == 5)


def test_sortie_dunivers_ferme_la_position() -> None:
    """Un titre qui cesse de coter quitte l'univers dès la séance suivante."""
    panneau = _panel(200, 12, seed=56)
    panneau.iloc[150:, 0] = np.nan
    resultat = statistical_arbitrage_weights(
        panneau,
        rules=[PAPER_RULE],
        correlation_window=60,
        estimation_window=20,
        n_components=3,
        min_names=8,
    )
    appartenance = resultat.membership["A000"]
    assert not bool(appartenance.iloc[150:].any())
    assert bool(appartenance.iloc[100:150].all())


def test_masque_de_liquidite_retire_le_titre() -> None:
    """Un masque supplémentaire retire le titre de l'univers sans autre effet."""
    panneau = _panel(200, 12, seed=57)
    masque = pd.DataFrame(True, index=panneau.index, columns=panneau.columns)
    masque["A001"] = False
    resultat = statistical_arbitrage_weights(
        panneau,
        rules=[PAPER_RULE],
        correlation_window=60,
        estimation_window=20,
        n_components=3,
        min_names=8,
        tradable=masque,
    )
    assert not bool(resultat.membership["A001"].any())
    assert float(resultat.weights[PAPER_RULE.name]["A001"].abs().sum()) == 0.0


def test_filtre_de_vitesse_retire_les_lents() -> None:
    """Serrer le filtre ne peut que réduire le nombre de titres éligibles."""
    panneau = _panel(200, 12, seed=58)
    large = statistical_arbitrage_weights(
        panneau,
        rules=[PAPER_RULE],
        correlation_window=60,
        estimation_window=20,
        n_components=3,
        min_names=8,
        max_characteristic_days=None,
    )
    serre = statistical_arbitrage_weights(
        panneau,
        rules=[PAPER_RULE],
        correlation_window=60,
        estimation_window=20,
        n_components=3,
        min_names=8,
        max_characteristic_days=10.0,
    )
    assert int(serre.eligible.to_numpy().sum()) <= int(large.eligible.to_numpy().sum())


def test_deux_regles_partagent_les_memes_signaux() -> None:
    """Deux règles déroulées ensemble lisent le même s-score et diffèrent des positions."""
    panneau = _panel(200, 12, seed=59)
    laxiste = TradingRule(name="laxiste", open_long=0.75, open_short=0.75)
    resultat = statistical_arbitrage_weights(
        panneau,
        rules=[PAPER_RULE, laxiste],
        correlation_window=60,
        estimation_window=20,
        n_components=3,
        min_names=8,
    )
    assert set(resultat.weights) == {PAPER_RULE.name, "laxiste"}
    assert resultat.n_positions["laxiste"].sum() >= resultat.n_positions[PAPER_RULE.name].sum()


def test_nombre_de_facteurs_publie() -> None:
    """Le nombre de facteurs retenus est celui qui a été demandé."""
    panneau = _panel(200, 12, seed=60)
    resultat = statistical_arbitrage_weights(
        panneau,
        rules=[PAPER_RULE],
        correlation_window=60,
        estimation_window=20,
        n_components=3,
        min_names=8,
    )
    observes = resultat.n_factors.dropna().unique()
    assert observes.tolist() == [3.0]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"correlation_window": 10, "estimation_window": 20},
        {"estimation_window": 5},
        {"reestimation_days": 0},
        {"rules": []},
    ],
)
def test_reglages_incoherents_refuses(kwargs: dict[str, object]) -> None:
    """Une fenêtre courte, une réestimation nulle ou une règle absente lèvent."""
    panneau = _panel(120, 12, seed=61)
    with pytest.raises(ConfigError):
        _chaine(panneau, **kwargs)


def test_deux_regles_de_meme_nom_refusees() -> None:
    """Deux colonnes de même nom rendraient le tableau de poids illisible."""
    panneau = _panel(120, 12, seed=62)
    with pytest.raises(ConfigError):
        _chaine(panneau, rules=[PAPER_RULE, TradingRule(name=PAPER_RULE.name)])


def test_echantillon_plus_court_que_la_fenetre_refuse() -> None:
    """Moins de séances que la fenêtre de corrélation lève au lieu de rendre vide."""
    panneau = _panel(40, 12, seed=63)
    with pytest.raises(InsufficientDataError):
        _chaine(panneau)


def test_index_non_trie_refuse() -> None:
    """Un index dans le désordre fabriquerait des fenêtres fausses en silence."""
    panneau = _panel(120, 12, seed=64).iloc[::-1]
    with pytest.raises(DataQualityError):
        _chaine(panneau)


def test_ecart_type_dequilibre_publie() -> None:
    """L'écart type d'équilibre est rendu, et il est strictement positif."""
    panneau = _panel(200, 12, seed=65)
    resultat = statistical_arbitrage_weights(
        panneau,
        rules=[PAPER_RULE],
        correlation_window=60,
        estimation_window=20,
        n_components=3,
        min_names=8,
    )
    valeurs = resultat.equilibrium_volatility.to_numpy()
    observees = valeurs[np.isfinite(valeurs)]
    assert observees.size > 0
    assert float(observees.min()) > 0.0


def test_s_score_se_reconstruit_depuis_lecart_type() -> None:
    """Le s-score multiplié par l'écart type rend un écart d'équilibre borné.

    Le produit vaut la moyenne des équilibres moins celui du titre, donc sa
    moyenne en travers des titres est nulle à chaque date.
    """
    panneau = _panel(200, 12, seed=66)
    resultat = statistical_arbitrage_weights(
        panneau,
        rules=[PAPER_RULE],
        correlation_window=60,
        estimation_window=20,
        n_components=3,
        min_names=8,
    )
    produit = resultat.s_score * resultat.equilibrium_volatility
    lignes = produit.dropna(how="all")
    assert float(np.nanmax(np.abs(lignes.mean(axis=1).to_numpy()))) < 1e-12


def test_plafond_de_facteurs_mord_et_se_declare() -> None:
    """Une coupure de variance haute demande plus de facteurs que de points."""
    panneau = _panel(200, 30, seed=67)
    resultat = statistical_arbitrage_weights(
        panneau,
        rules=[PAPER_RULE],
        correlation_window=60,
        estimation_window=20,
        n_components=None,
        variance_share=0.99,
        min_names=8,
    )
    assert resultat.diagnostics["factor_cap"] == 18.0
    assert resultat.diagnostics["n_capped_windows"] > 0.0
    assert float(resultat.n_factors.max()) <= 18.0


def test_couverture_figee_ne_bouge_pas_a_positions_constantes() -> None:
    """Deux séances de mêmes positions rendent les mêmes poids, couverture figée.

    C'est la propriété qui définit le choix : la jambe de facteurs se fixe au
    jour de l'entrée, donc rien ne se négocie tant que rien ne s'ouvre ni ne se
    ferme.
    """
    panneau = _panel(200, 12, seed=68)
    resultat = statistical_arbitrage_weights(
        panneau,
        rules=[PAPER_RULE],
        correlation_window=60,
        estimation_window=20,
        n_components=3,
        min_names=8,
        hedge_at_entry=True,
    )
    poids = resultat.weights[PAPER_RULE.name].dropna(how="all")
    positions = resultat.n_positions[PAPER_RULE.name].reindex(poids.index)
    inchangees = positions.diff() == 0.0
    ecart = poids.diff().abs().sum(axis=1)
    stables = ecart[inchangees.fillna(value=False)]
    assert len(stables) > 10
    assert float(stables.min()) == pytest.approx(0.0, abs=1e-12)


def test_couverture_quotidienne_negocie_tous_les_jours() -> None:
    """Recalculée chaque séance, la couverture déplace les poids sans cesse."""
    panneau = _panel(200, 12, seed=69)
    figee = statistical_arbitrage_weights(
        panneau,
        rules=[PAPER_RULE],
        correlation_window=60,
        estimation_window=20,
        n_components=3,
        min_names=8,
        hedge_at_entry=True,
    ).weights[PAPER_RULE.name]
    quotidienne = statistical_arbitrage_weights(
        panneau,
        rules=[PAPER_RULE],
        correlation_window=60,
        estimation_window=20,
        n_components=3,
        min_names=8,
        hedge_at_entry=False,
    ).weights[PAPER_RULE.name]
    assert float(quotidienne.diff().abs().sum().sum()) > float(figee.diff().abs().sum().sum())


def test_couverture_quotidienne_reste_causale() -> None:
    """La couverture recalculée chaque jour garde la stabilité par troncature.

    Le cas de référence, couverture figée, est déjà couvert par les deux tests
    de troncature qui emploient les réglages par défaut.
    """
    panneau = _panel(240, 12, seed=70)
    complet = _chaine(panneau, hedge_at_entry=False)
    tronque = _chaine(panneau.iloc[:200], hedge_at_entry=False)
    ecart = (complet.loc[tronque.index] - tronque).abs().to_numpy()
    assert np.nanmax(ecart) == pytest.approx(0.0, abs=1e-15)


# --------------------------------------------------------------------------- #
# Le livre de l'article : actions tout ou rien, couverture par le seul repère
# --------------------------------------------------------------------------- #


def _livre_simple() -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """Rend un panneau minuscule dont le bêta au repère vaut exactement un."""
    index = pd.bdate_range("2000-01-03", periods=8)
    marche = pd.Series([0.01, -0.02, 0.015, -0.005, 0.02, -0.01, 0.005, 0.01], index=index)
    rendements = pd.DataFrame({"AAA": marche.to_numpy(), "BBB": marche.to_numpy() * 2.0}, index=index)
    positions = pd.DataFrame(0.0, index=index, columns=["AAA", "BBB"])
    positions.iloc[-3:, 0] = 1.0
    return positions, rendements, marche


def test_livre_de_larticle_couvre_un_beta_unitaire() -> None:
    """Un titre de bêta un, acheté seul, rend une jambe de repère de moins un."""
    positions, rendements, marche = _livre_simple()
    livre = market_hedged_book(positions, rendements, marche, window=4, benchmark="SPY")
    assert livre["SPY"].iloc[-1] == pytest.approx(-1.0, abs=1e-12)
    assert livre["AAA"].iloc[-1] == pytest.approx(1.0, abs=1e-12)


def test_livre_de_larticle_additionne_les_betas() -> None:
    """Deux titres de bêtas un et deux, achetés ensemble, donnent moins trois."""
    positions, rendements, marche = _livre_simple()
    positions.iloc[-3:, 1] = 1.0
    livre = market_hedged_book(positions, rendements, marche, window=4, benchmark="SPY")
    assert livre["SPY"].iloc[-1] == pytest.approx(-3.0, abs=1e-12)


def test_livre_de_larticle_refuse_un_repere_deja_present() -> None:
    """Le repère ne peut pas écraser une colonne de titre existante."""
    positions, rendements, marche = _livre_simple()
    with pytest.raises(ConfigError):
        market_hedged_book(positions, rendements, marche, window=4, benchmark="AAA")


def test_livre_de_larticle_refuse_des_colonnes_qui_diffèrent() -> None:
    """Les positions et les rendements portent les mêmes titres, dans le même ordre."""
    positions, rendements, marche = _livre_simple()
    with pytest.raises(ConfigError):
        market_hedged_book(positions, rendements[["BBB", "AAA"]], marche, window=4, benchmark="SPY")


def test_livre_de_larticle_refuse_un_beta_manquant() -> None:
    """Une position ouverte sans bêta estimable est une erreur, pas un zéro."""
    positions, rendements, marche = _livre_simple()
    positions.iloc[0, 0] = 1.0
    with pytest.raises(DataQualityError):
        market_hedged_book(positions, rendements, marche, window=4, benchmark="SPY")


def test_livre_de_larticle_garde_les_jours_sans_decision() -> None:
    """Un jour sans décision reste entièrement manquant, jambe de repère comprise."""
    positions, rendements, marche = _livre_simple()
    positions.iloc[3] = np.nan
    livre = market_hedged_book(positions, rendements, marche, window=4, benchmark="SPY")
    assert bool(livre.iloc[3].isna().all())


# --------------------------------------------------------------------------- #
# Le panneau de positions publié par la chaîne
# --------------------------------------------------------------------------- #


def test_le_panneau_de_positions_redonne_son_propre_compte() -> None:
    """La somme des positions en valeur absolue est le nombre de positions publié."""
    panneau = _panel(200, 12, seed=71)
    resultat = statistical_arbitrage_weights(
        panneau,
        rules=[PAPER_RULE],
        correlation_window=60,
        estimation_window=20,
        n_components=3,
        min_names=8,
    )
    positions = resultat.positions[PAPER_RULE.name]
    compte = positions.abs().sum(axis=1)
    attendu = resultat.n_positions[PAPER_RULE.name]
    assert float((compte - attendu).abs().max()) == pytest.approx(0.0, abs=1e-12)


def test_le_panneau_de_positions_ne_prend_que_trois_valeurs() -> None:
    """La règle est tout ou rien, donc aucune position intermédiaire n'existe."""
    panneau = _panel(200, 12, seed=72)
    resultat = statistical_arbitrage_weights(
        panneau,
        rules=[PAPER_RULE],
        correlation_window=60,
        estimation_window=20,
        n_components=3,
        min_names=8,
    )
    valeurs = resultat.positions[PAPER_RULE.name].to_numpy()
    valeurs = valeurs[np.isfinite(valeurs)]
    assert set(np.unique(valeurs)).issubset({-1.0, 0.0, 1.0})


def test_le_panneau_de_positions_partage_lindex_des_poids() -> None:
    """Un jour sans poids est un jour sans position, et réciproquement."""
    panneau = _panel(200, 12, seed=73)
    resultat = statistical_arbitrage_weights(
        panneau,
        rules=[PAPER_RULE],
        correlation_window=60,
        estimation_window=20,
        n_components=3,
        min_names=8,
    )
    poids = resultat.weights[PAPER_RULE.name]
    positions = resultat.positions[PAPER_RULE.name]
    assert list(poids.index) == list(positions.index)
    assert list(poids.columns) == list(positions.columns)
    assert (poids.notna().any(axis=1) == positions.notna().any(axis=1)).all()

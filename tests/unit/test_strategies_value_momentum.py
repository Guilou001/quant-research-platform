"""Les contrôles du module de la valeur et du momentum.

Chaque valeur attendue vient d'un calcul à la main, d'une propriété
mathématique, ou d'un chiffre publié. Aucune ne vient de la sortie du code, ce
qui verrouillerait le défaut au lieu de l'attraper.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.types import Frequency
from quantlab.strategies.value_momentum import (
    align_pair,
    blend_returns,
    correlation_standard_error,
    diversification_multiplier,
    equal_risk_sharpe,
    grid_average_over_size,
    high_minus_low,
    pair_diagnostics,
    rank_weighted_factor,
    rank_weights,
    rebalanced_blend,
    risk_parity_weights,
    rolling_correlation,
    sharpe_sensitivity_to_correlation,
    stress_correlation,
    two_asset_sharpe,
)


def _monthly(start: str, values: list[float] | np.ndarray) -> pd.Series:
    """Fabrique une série mensuelle indexée par fin de mois."""
    index = pd.period_range(start, periods=len(values), freq="M").to_timestamp(how="end").normalize()
    return pd.Series(list(values), index=pd.DatetimeIndex(index, name="date"), dtype=float)


def _pair(seed: int, n: int = 360, rho: float = -0.5) -> tuple[pd.Series, pd.Series]:
    """Fabrique deux jambes corrélées, de volatilités différentes."""
    rng = np.random.default_rng(seed)
    z1 = rng.standard_normal(n)
    z2 = rho * z1 + math.sqrt(1.0 - rho**2) * rng.standard_normal(n)
    value = _monthly("1972-01", 0.004 + 0.02 * z1)
    momentum = _monthly("1972-01", 0.006 + 0.035 * z2)
    return value, momentum


# --------------------------------------------------------------------------- #
# Les poids de rang, équation (1) de l'article
# --------------------------------------------------------------------------- #


def test_poids_de_rang_a_la_main_sur_cinq_groupes() -> None:
    """Cinq groupes rendent des écarts -2, -1, 0, 1, 2 divisés par trois.

    La somme des écarts positifs vaut 1 + 2 = 3, donc les poids valent
    -2/3, -1/3, 0, 1/3, 2/3. Calcul à la main, aucune sortie du code.
    """
    attendu = np.array([-2.0, -1.0, 0.0, 1.0, 2.0]) / 3.0
    np.testing.assert_allclose(rank_weights(5), attendu, rtol=0.0, atol=1e-15)


def test_poids_de_rang_a_la_main_sur_dix_groupes() -> None:
    """Dix groupes rendent des écarts -4,5 à 4,5 divisés par 12,5.

    La somme des écarts positifs vaut 0,5 + 1,5 + 2,5 + 3,5 + 4,5 = 12,5.
    Le poids du dixième décile vaut donc 4,5 / 12,5 = 0,36.
    """
    poids = rank_weights(10)
    assert poids[-1] == pytest.approx(0.36, abs=1e-15)
    assert poids[0] == pytest.approx(-0.36, abs=1e-15)


def test_poids_de_rang_somment_a_zero_et_un_dollar() -> None:
    """La somme des poids est nulle et la partie positive vaut un dollar."""
    for n in (2, 3, 5, 10, 25):
        poids = rank_weights(n)
        assert poids.sum() == pytest.approx(0.0, abs=1e-14)
        assert poids[poids > 0.0].sum() == pytest.approx(1.0, abs=1e-14)
        assert poids[poids < 0.0].sum() == pytest.approx(-1.0, abs=1e-14)


def test_poids_de_rang_refuse_un_seul_groupe() -> None:
    """Un classement d'un seul élément n'a pas de rang moyen utile."""
    with pytest.raises(ConfigError, match="au moins 2"):
        rank_weights(1)


# --------------------------------------------------------------------------- #
# Les deux constructions de facteur
# --------------------------------------------------------------------------- #


def test_facteur_de_rang_coincide_avec_l_ecart_sur_deux_groupes() -> None:
    """Sur deux groupes, les poids valent -1 et +1, donc les deux formules se rejoignent.

    C'est une propriété algébrique : l'écart au rang moyen vaut -0,5 et +0,5,
    et la constante de mise à l'échelle vaut deux.
    """
    frame = pd.DataFrame(
        {"bas": [0.01, -0.02, 0.03], "haut": [0.04, 0.01, -0.01]},
        index=pd.period_range("2000-01", periods=3, freq="M").to_timestamp(how="end").normalize(),
    )
    pd.testing.assert_series_equal(rank_weighted_factor(frame).rename("x"), high_minus_low(frame).rename("x"))


def test_facteur_de_rang_a_la_main_sur_trois_groupes() -> None:
    """Trois groupes rendent -1, 0, +1, donc le facteur vaut le troisième moins le premier.

    Les écarts au rang moyen valent -1, 0, 1 et la somme des positifs vaut un,
    si bien que le poids du milieu est nul.
    """
    frame = pd.DataFrame(
        {"a": [0.10], "b": [0.50], "c": [0.07]},
        index=pd.DatetimeIndex(["2000-01-31"], name="date"),
    )
    assert float(rank_weighted_factor(frame).iloc[0]) == pytest.approx(-0.03, abs=1e-15)


def test_ecart_haut_moins_bas_a_la_main() -> None:
    """Le haut moins le bas se lit directement sur les deux colonnes extrêmes."""
    frame = pd.DataFrame(
        {"a": [0.02, 0.01], "b": [0.00, 0.00], "c": [0.05, -0.03]},
        index=pd.period_range("2000-01", periods=2, freq="M").to_timestamp(how="end").normalize(),
    )
    np.testing.assert_allclose(high_minus_low(frame).to_numpy(), [0.03, -0.04], atol=1e-15)


def test_facteur_refuse_une_seule_colonne() -> None:
    """Un tri à une seule case n'est pas un tri."""
    frame = pd.DataFrame({"a": [0.01]}, index=pd.DatetimeIndex(["2000-01-31"], name="date"))
    with pytest.raises(InsufficientDataError):
        rank_weighted_factor(frame)


# --------------------------------------------------------------------------- #
# La moyenne du tableau croisé sur la dimension de taille
# --------------------------------------------------------------------------- #


def test_moyenne_sur_la_taille_a_la_main() -> None:
    """Deux tailles et trois groupes de signal rendent la moyenne des deux lignes.

    Les colonnes sont lues taille par taille : ME1 S1, ME1 S2, ME1 S3, puis
    ME2 S1, ME2 S2, ME2 S3. La première colonne du résultat vaut donc la
    moyenne de la première et de la quatrième.
    """
    frame = pd.DataFrame(
        [[0.01, 0.02, 0.03, 0.05, 0.06, 0.07]],
        index=pd.DatetimeIndex(["2000-01-31"], name="date"),
        columns=["a", "b", "c", "d", "e", "f"],
    )
    out = grid_average_over_size(frame, n_size=2, n_signal=3)
    assert list(out.columns) == ["q1", "q2", "q3"]
    np.testing.assert_allclose(out.to_numpy(), [[0.03, 0.04, 0.05]], atol=1e-15)


def test_moyenne_sur_la_taille_refuse_une_forme_incoherente() -> None:
    """Six colonnes ne se rangent pas en cinq fois cinq."""
    frame = pd.DataFrame(
        [[0.01] * 6],
        index=pd.DatetimeIndex(["2000-01-31"], name="date"),
        columns=list("abcdef"),
    )
    with pytest.raises(ConfigError, match="colonnes"):
        grid_average_over_size(frame, n_size=5, n_signal=5)


# --------------------------------------------------------------------------- #
# L'alignement et le mélange
# --------------------------------------------------------------------------- #


def test_alignement_garde_les_seuls_mois_communs_et_complets() -> None:
    """Un trou dans une jambe retire le mois des deux."""
    value = _monthly("2000-01", [0.01, float("nan"), 0.03, 0.04])
    momentum = _monthly("2000-02", [0.02, 0.03, 0.04])
    frame = align_pair(value, momentum)
    assert list(frame.index.strftime("%Y-%m")) == ["2000-03", "2000-04"]


def test_alignement_refuse_un_seul_mois_commun() -> None:
    """Une corrélation sur un point n'existe pas."""
    value = _monthly("2000-01", [0.01, 0.02])
    momentum = _monthly("2000-02", [0.03])
    with pytest.raises(InsufficientDataError):
        align_pair(value, momentum)


def test_melange_a_parts_egales_a_la_main() -> None:
    """La moitié de 2 % et la moitié de 4 % font 3 %."""
    value = _monthly("2000-01", [0.02, -0.02])
    momentum = _monthly("2000-01", [0.04, 0.06])
    blend = blend_returns(value, momentum, value_weight=0.5)
    np.testing.assert_allclose(blend.to_numpy(), [0.03, 0.02], atol=1e-15)


def test_melange_a_poids_un_rend_la_premiere_jambe() -> None:
    """Un poids de un sur la valeur rend exactement la jambe de valeur."""
    value, momentum = _pair(seed=1, n=48)
    blend = blend_returns(value, momentum, value_weight=1.0)
    np.testing.assert_allclose(blend.to_numpy(), value.to_numpy(), atol=1e-15)


# --------------------------------------------------------------------------- #
# Le mélange à risque égal, et sa causalité
# --------------------------------------------------------------------------- #


def test_poids_a_risque_egal_de_plein_echantillon_a_la_main() -> None:
    """Deux jambes d'écarts types 1 et 3 donnent un poids de 0,75 à la première.

    Le poids de la première jambe vaut sigma2 / (sigma1 + sigma2), soit
    3 / 4 = 0,75. Les deux séries sont construites pour porter exactement ces
    deux écarts types.
    """
    value = _monthly("2000-01", [-1.0, 1.0, -1.0, 1.0])
    momentum = _monthly("2000-01", [-3.0, 3.0, -3.0, 3.0])
    poids = risk_parity_weights(value, momentum)
    assert float(poids.iloc[0]) == pytest.approx(0.75, abs=1e-14)


def test_poids_a_risque_egal_en_expansion_n_emploie_pas_le_mois_courant() -> None:
    """Modifier un mois du milieu ne change pas le poids porté par CE mois.

    Le poids du mois t se calcule sur les mois 1 à t-1. Perturber le mois t
    doit donc laisser son propre poids intact, et ne bouger que la suite. Le
    contrôle a été validé par mutation : retirer le décalage d'un mois le fait
    échouer.
    """
    value, momentum = _pair(seed=7, n=120)
    poids = risk_parity_weights(value, momentum, min_periods=24)
    perturbee = value.copy()
    position = 60
    perturbee.iloc[position] = perturbee.iloc[position] + 5.0
    poids_perturbe = risk_parity_weights(perturbee, momentum, min_periods=24)
    pd.testing.assert_series_equal(poids.iloc[: position + 1], poids_perturbe.iloc[: position + 1])
    assert poids.iloc[position + 1] != pytest.approx(poids_perturbe.iloc[position + 1])


def test_poids_a_risque_egal_en_expansion_stable_par_troncature() -> None:
    """Retirer la fin de l'échantillon ne change aucun poids passé.

    C'est la preuve d'absence d'information future qui ne repose pas sur la
    lecture du code : une chaîne tenable rend les mêmes valeurs passées quand
    on lui retire l'avenir.
    """
    value, momentum = _pair(seed=11, n=200)
    complet = risk_parity_weights(value, momentum, min_periods=36)
    tronque = risk_parity_weights(value.iloc[:150], momentum.iloc[:150], min_periods=36)
    pd.testing.assert_series_equal(complet.iloc[:150], tronque)


def test_poids_a_risque_egal_de_plein_echantillon_bouge_par_troncature() -> None:
    """Le contrôle inverse : le poids de plein échantillon, lui, dépend de l'avenir.

    Sans ce test, le précédent passerait aussi sur une version fautive qui
    emploierait l'écart type de tout l'échantillon.
    """
    value, momentum = _pair(seed=11, n=200)
    complet = float(risk_parity_weights(value, momentum).iloc[0])
    tronque = float(risk_parity_weights(value.iloc[:150], momentum.iloc[:150]).iloc[0])
    assert complet != pytest.approx(tronque, abs=1e-6)


def test_poids_a_risque_egal_refuse_une_fenetre_d_un_mois() -> None:
    """Un écart type sur un seul mois n'existe pas."""
    value, momentum = _pair(seed=3, n=24)
    with pytest.raises(ConfigError, match="au moins 2"):
        risk_parity_weights(value, momentum, min_periods=1)


def test_poids_a_risque_egal_refuse_une_jambe_constante() -> None:
    """Une jambe d'écart type nul rendrait un poids infini."""
    value = _monthly("2000-01", [0.02, 0.02, 0.02, 0.02])
    momentum = _monthly("2000-01", [0.01, -0.01, 0.02, -0.02])
    with pytest.raises(DataQualityError):
        risk_parity_weights(value, momentum)


# --------------------------------------------------------------------------- #
# Le rééquilibrage
# --------------------------------------------------------------------------- #


def test_reequilibrage_mensuel_coincide_avec_le_melange_a_poids_fixe() -> None:
    """Rééquilibrer tous les mois revient à tenir le poids cible chaque mois."""
    value, momentum = _pair(seed=5, n=60)
    attendu = blend_returns(value, momentum, value_weight=0.5)
    obtenu = rebalanced_blend(value, momentum, value_weight=0.5, rebalance_months=1)
    np.testing.assert_allclose(obtenu["blend"].to_numpy(), attendu.to_numpy(), atol=1e-15)
    np.testing.assert_allclose(obtenu["value_weight"].to_numpy(), 0.5, atol=1e-15)


def test_derive_du_poids_a_la_main_sur_deux_mois() -> None:
    """Après un mois à +10 % contre 0 %, le poids passe de 0,5 à 11/21.

    Le mélange rapporte 5 %, la jambe de valeur vaut 1,10 fois sa mise et le
    mélange 1,05 fois la sienne. Le poids dérivé vaut 0,5 x 1,10 / 1,05, soit
    0,55 / 1,05 = 11 / 21 = 0,523810.
    """
    value = _monthly("2000-01", [0.10, 0.00])
    momentum = _monthly("2000-01", [0.00, 0.00])
    out = rebalanced_blend(value, momentum, value_weight=0.5, rebalance_months=12)
    assert float(out["value_weight"].iloc[1]) == pytest.approx(11.0 / 21.0, abs=1e-14)


def test_reequilibrage_refuse_une_periode_nulle() -> None:
    """Rééquilibrer tous les zéro mois n'a pas de sens."""
    value, momentum = _pair(seed=5, n=24)
    with pytest.raises(ConfigError, match="au moins 1"):
        rebalanced_blend(value, momentum, rebalance_months=0)


def test_reequilibrage_refuse_une_ruine_totale() -> None:
    """Un mélange qui perd tout ne porte plus de poids dérivé défini."""
    value = _monthly("2000-01", [-1.0, 0.0])
    momentum = _monthly("2000-01", [-1.0, 0.0])
    with pytest.raises(DataQualityError):
        rebalanced_blend(value, momentum, rebalance_months=12)


# --------------------------------------------------------------------------- #
# La formule du Sharpe à deux actifs
# --------------------------------------------------------------------------- #


def test_sharpe_a_deux_actifs_avec_un_poids_de_un() -> None:
    """Un poids de un rend le ratio de Sharpe de la première jambe, quel que soit rho."""
    for rho in (-0.9, -0.3, 0.0, 0.5, 1.0):
        obtenu = two_asset_sharpe(
            0.42,
            0.61,
            volatility_value=0.11,
            volatility_momentum=0.19,
            correlation=rho,
            value_weight=1.0,
        )
        assert obtenu == pytest.approx(0.42, abs=1e-12)


def test_sharpe_a_deux_actifs_cas_symetrique_a_la_main() -> None:
    """Deux jambes identiques mélangées à parts égales rendent S fois racine de 2/(1+rho).

    Avec sigma1 = sigma2 et S1 = S2 = S, le numérateur vaut S sigma et le
    dénominateur sigma racine((1 + rho) / 2). Le rapport vaut donc
    S racine(2 / (1 + rho)), formule dérivée à la main.
    """
    for rho in (-0.75, -0.5, 0.0, 0.5, 1.0):
        attendu = 0.4 * math.sqrt(2.0 / (1.0 + rho))
        obtenu = two_asset_sharpe(
            0.4,
            0.4,
            volatility_value=0.15,
            volatility_momentum=0.15,
            correlation=rho,
            value_weight=0.5,
        )
        assert obtenu == pytest.approx(attendu, rel=1e-12)


def test_sharpe_a_deux_actifs_refuse_une_volatilite_nulle() -> None:
    """Une jambe sans risque n'a pas de place dans cette formule."""
    with pytest.raises(ConfigError):
        two_asset_sharpe(
            0.4,
            0.4,
            volatility_value=0.0,
            volatility_momentum=0.15,
            correlation=0.0,
            value_weight=0.5,
        )


def test_sharpe_a_deux_actifs_refuse_une_correlation_hors_bornes() -> None:
    """Une corrélation de 1,5 n'existe pas."""
    with pytest.raises(ConfigError, match=r"\[-1, 1\]"):
        two_asset_sharpe(
            0.4,
            0.4,
            volatility_value=0.1,
            volatility_momentum=0.1,
            correlation=1.5,
            value_weight=0.5,
        )


def test_le_melange_parfaitement_oppose_leve() -> None:
    """Deux jambes de corrélation -1 et de même volatilité s'annulent exactement."""
    with pytest.raises(DataQualityError):
        two_asset_sharpe(
            0.4,
            0.4,
            volatility_value=0.15,
            volatility_momentum=0.15,
            correlation=-1.0,
            value_weight=0.5,
        )


# --------------------------------------------------------------------------- #
# La forme fermée du mélange à risque égal
# --------------------------------------------------------------------------- #


def test_forme_fermee_a_risque_egal_a_la_main() -> None:
    """Deux Sharpe de 0,5 sans corrélation rendent 1 / racine de 2.

    La formule donne (0,5 + 0,5) / racine(2 + 0) = 0,7071068.
    """
    assert equal_risk_sharpe(0.5, 0.5, 0.0) == pytest.approx(1.0 / math.sqrt(2.0), rel=1e-14)


def test_forme_fermee_egale_la_formule_generale_au_poids_a_risque_egal() -> None:
    """Les deux formules coïncident quand le poids égalise les contributions au risque.

    Le poids qui égalise vaut sigma2 / (sigma1 + sigma2). C'est une identité
    algébrique, donc l'égalité doit tenir à la précision machine pour toute
    combinaison de volatilités.
    """
    for sigma_v, sigma_m, rho in ((0.10, 0.30, -0.577), (0.25, 0.25, 0.4), (0.07, 0.19, -0.9)):
        poids = sigma_m / (sigma_v + sigma_m)
        general = two_asset_sharpe(
            0.41,
            0.59,
            volatility_value=sigma_v,
            volatility_momentum=sigma_m,
            correlation=rho,
            value_weight=poids,
        )
        assert general == pytest.approx(equal_risk_sharpe(0.41, 0.59, rho), rel=1e-12)


def test_forme_fermee_refuse_la_correlation_moins_un() -> None:
    """À corrélation -1, le mélange à risque égal est sans risque et sans ratio."""
    with pytest.raises(ConfigError):
        equal_risk_sharpe(0.5, 0.5, -1.0)


# --------------------------------------------------------------------------- #
# Le multiplicateur et la sensibilité
# --------------------------------------------------------------------------- #


def test_multiplicateur_vaut_un_a_correlation_nulle() -> None:
    """Deux jambes indépendantes sont la référence, donc le multiplicateur vaut un."""
    assert diversification_multiplier(0.0) == pytest.approx(1.0, abs=1e-15)


def test_multiplicateur_est_le_rapport_des_deux_formes_fermees() -> None:
    """Le multiplicateur doit reproduire le rapport du Sharpe à rho sur celui à zéro."""
    for rho in (-0.9, -0.577, -0.2, 0.3, 1.0):
        attendu = equal_risk_sharpe(0.4, 0.6, rho) / equal_risk_sharpe(0.4, 0.6, 0.0)
        assert diversification_multiplier(rho) == pytest.approx(attendu, rel=1e-13)


def test_multiplicateur_a_la_main_pour_deux_valeurs_publiables() -> None:
    """À rho = -0,75 le multiplicateur vaut deux, et à rho = 3/4 il vaut 2 / racine(7).

    Les deux valeurs se calculent à la main : 1 / racine(0,25) = 2, et
    1 / racine(1,75) = 0,755929.
    """
    assert diversification_multiplier(-0.75) == pytest.approx(2.0, rel=1e-14)
    assert diversification_multiplier(0.75) == pytest.approx(1.0 / math.sqrt(1.75), rel=1e-14)


def test_sensibilite_est_la_derivee_de_la_forme_fermee() -> None:
    """La dérivée analytique doit coïncider avec la différence finie centrée.

    C'est le contrôle qui attraperait un facteur deux oublié dans la dérivation.
    """
    for rho in (-0.8, -0.577, -0.1, 0.4):
        pas = 1e-6
        finie = (equal_risk_sharpe(0.4, 0.6, rho + pas) - equal_risk_sharpe(0.4, 0.6, rho - pas)) / (
            2.0 * pas
        )
        assert sharpe_sensitivity_to_correlation(0.4, 0.6, rho) == pytest.approx(finie, rel=1e-6)


def test_sensibilite_est_negative_et_croit_en_valeur_absolue() -> None:
    """Le gain n'est pas linéaire : les derniers dixièmes rapportent le plus."""
    valeurs = [abs(sharpe_sensitivity_to_correlation(0.4, 0.6, r)) for r in (-0.8, -0.5, 0.0, 0.5)]
    assert valeurs == sorted(valeurs, reverse=True)
    assert sharpe_sensitivity_to_correlation(0.4, 0.6, -0.5) < 0.0


# --------------------------------------------------------------------------- #
# L'erreur type de la corrélation
# --------------------------------------------------------------------------- #


def test_erreur_type_de_correlation_a_la_main() -> None:
    """À rho nul et cent observations, l'erreur type vaut un dixième.

    La formule (1 - rho^2) / racine(n) donne 1 / 10 = 0,1.
    """
    assert correlation_standard_error(0.0, 100) == pytest.approx(0.1, abs=1e-15)


def test_erreur_type_de_correlation_s_annule_aux_bornes() -> None:
    """Une corrélation parfaite n'a plus d'incertitude asymptotique."""
    assert correlation_standard_error(1.0, 50) == pytest.approx(0.0, abs=1e-15)
    assert correlation_standard_error(-1.0, 50) == pytest.approx(0.0, abs=1e-15)


def test_erreur_type_refuse_une_correlation_impossible() -> None:
    """Une corrélation de -2 n'existe pas."""
    with pytest.raises(ConfigError):
        correlation_standard_error(-2.0, 100)


# --------------------------------------------------------------------------- #
# La corrélation glissante et la corrélation de tension
# --------------------------------------------------------------------------- #


def test_correlation_glissante_vaut_un_sur_deux_jambes_proportionnelles() -> None:
    """Deux jambes proportionnelles ont une corrélation de un dans toute fenêtre."""
    value, _ = _pair(seed=13, n=90)
    proportionnelle = value * 3.0
    roulante = rolling_correlation(value, proportionnelle, window=24).dropna()
    np.testing.assert_allclose(roulante.to_numpy(), 1.0, atol=1e-10)


def test_correlation_glissante_laisse_la_fenetre_incomplete_manquante() -> None:
    """Les premiers mois n'ont pas assez d'observations, et cela se voit."""
    value, momentum = _pair(seed=17, n=60)
    roulante = rolling_correlation(value, momentum, window=24)
    assert roulante.iloc[:23].isna().all()
    assert roulante.iloc[23:].notna().all()


def test_correlation_glissante_refuse_une_fenetre_de_deux_mois() -> None:
    """Une corrélation sur deux points vaut toujours plus ou moins un."""
    value, momentum = _pair(seed=19, n=48)
    with pytest.raises(ConfigError, match="au moins 3"):
        rolling_correlation(value, momentum, window=2)


def test_correlation_de_tension_separe_deux_regimes_construits() -> None:
    """Une paire construite pour être opposée en tension et alignée hors tension le montre.

    Les vingt premiers mois portent une corrélation de +1 et un marché en
    hausse, les vingt suivants une corrélation de -1 et un marché en baisse.
    Le seuil du quantile 0,5 sépare exactement les deux blocs.
    """
    rng = np.random.default_rng(23)
    calme = rng.standard_normal(20)
    tendu = rng.standard_normal(20)
    value = _monthly("2000-01", np.concatenate([calme, tendu]) * 0.02)
    momentum = _monthly("2000-01", np.concatenate([calme, -tendu]) * 0.02)
    marche = _monthly("2000-01", np.concatenate([np.full(20, 0.05), np.full(20, -0.05)]))
    out = stress_correlation(value, momentum, marche, quantile=0.5)
    assert out["correlation_stress"] == pytest.approx(-1.0, abs=1e-10)
    assert out["correlation_calm"] == pytest.approx(1.0, abs=1e-10)
    assert out["n_stress"] == 20.0


def test_correlation_de_tension_refuse_un_quantile_hors_bornes() -> None:
    """Un quantile de 1,5 ne coupe rien."""
    value, momentum = _pair(seed=29, n=60)
    with pytest.raises(ConfigError):
        stress_correlation(value, momentum, value, quantile=1.5)


def test_correlation_de_tension_refuse_un_bloc_trop_court() -> None:
    """Deux mois de tension ne donnent pas une corrélation lisible."""
    value, momentum = _pair(seed=31, n=60)
    with pytest.raises(InsufficientDataError):
        stress_correlation(value, momentum, value, quantile=0.02)


# --------------------------------------------------------------------------- #
# Le diagnostic d'une paire, et l'identité qui porte l'étude
# --------------------------------------------------------------------------- #


def test_le_melange_a_risque_egal_mesure_egale_sa_forme_fermee() -> None:
    """La mesure et la formule doivent coïncider à la précision machine.

    C'est une identité algébrique : le mélange à risque égal de plein
    échantillon a des contributions au risque identiques, donc les volatilités
    se simplifient. L'égalité est le contrôle central de l'étude, et elle
    échouerait si la formule portait un facteur faux.
    """
    for seed in (2, 4, 8):
        value, momentum = _pair(seed=seed, n=480, rho=-0.6)
        diag = pair_diagnostics(value, momentum, label="test", frequency=Frequency.MONTHLY)
        assert diag.sharpe_risk_parity == pytest.approx(diag.sharpe_risk_parity_formula, rel=1e-11)


def test_le_diagnostic_retrouve_le_sharpe_a_parts_egales_par_la_formule_generale() -> None:
    """Le mélange à parts égales doit suivre la formule générale à deux actifs.

    Les quatre moments du diagnostic suffisent à reconstruire le ratio de
    Sharpe du mélange, ce qui vérifie que les volatilités publiées sont bien
    celles qui entrent dans la formule.
    """
    value, momentum = _pair(seed=6, n=360, rho=-0.4)
    diag = pair_diagnostics(value, momentum, label="test")
    reconstruit = two_asset_sharpe(
        diag.sharpe_value,
        diag.sharpe_momentum,
        volatility_value=diag.volatility_value,
        volatility_momentum=diag.volatility_momentum,
        correlation=diag.correlation,
        value_weight=0.5,
    )
    assert reconstruit == pytest.approx(diag.sharpe_equal_weight, rel=1e-11)


def test_le_diagnostic_porte_ses_bornes_et_son_compte() -> None:
    """Le nombre de mois et les deux dates sont ceux de l'intersection."""
    value, momentum = _pair(seed=10, n=120)
    diag = pair_diagnostics(value, momentum, label="EVERYWHERE")
    assert diag.label == "EVERYWHERE"
    assert diag.n_months == 120
    assert diag.start == "1972-01-31"
    assert diag.end == "1981-12-31"


def test_le_gain_est_nul_quand_les_deux_jambes_sont_identiques() -> None:
    """Mélanger une jambe avec elle-même ne diversifie rien.

    La corrélation vaut un, le multiplicateur vaut 1 / racine(2), et le
    mélange rend exactement le ratio de Sharpe de la jambe.
    """
    value, _ = _pair(seed=12, n=240)
    diag = pair_diagnostics(value, value.copy(), label="identique")
    assert diag.correlation == pytest.approx(1.0, abs=1e-12)
    assert diag.gain_over_best_leg == pytest.approx(0.0, abs=1e-12)
    assert diag.multiplier == pytest.approx(1.0 / math.sqrt(2.0), rel=1e-13)

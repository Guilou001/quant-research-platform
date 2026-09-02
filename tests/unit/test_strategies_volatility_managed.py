"""Les contrôles du module des portefeuilles gérés en volatilité.

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
from quantlab.strategies.volatility_managed import (
    appraisal_ratio,
    combined_sharpe,
    ewma_variance,
    expanding_constant,
    full_sample_constant,
    hedged_spread,
    leverage_series,
    managed_weights,
    monthly_variance,
    real_time_combination,
    realized_variance,
    spanning_regression,
    utility_gain,
    volatility_managed_returns,
)


def _daily(values: dict[str, list[float]]) -> pd.Series:
    """Fabrique une série quotidienne depuis un dictionnaire de mois."""
    dates: list[pd.Timestamp] = []
    numbers: list[float] = []
    for month, block in values.items():
        days = pd.bdate_range(f"{month}-01", periods=len(block))
        dates.extend(days)
        numbers.extend(block)
    return pd.Series(numbers, index=pd.DatetimeIndex(dates, name="date"), dtype=float)


def _monthly(start: str, values: list[float]) -> pd.Series:
    """Fabrique une série mensuelle indexée par fin de mois."""
    index = pd.period_range(start, periods=len(values), freq="M").to_timestamp(how="end").normalize()
    return pd.Series(values, index=pd.DatetimeIndex(index, name="date"), dtype=float)


# --------------------------------------------------------------------------- #
# La variance réalisée
# --------------------------------------------------------------------------- #


def test_variance_realisee_somme_des_carres_a_la_main() -> None:
    """Quatre séances à un centième rendent quatre fois un dix-millième.

    Le calcul se fait à la main : 0,01 au carré vaut 0,0001, et quatre séances
    en somment 0,0004.
    """
    serie = _daily({"2020-01": [0.01, -0.01, 0.01, -0.01]})
    frame = realized_variance(serie)
    assert frame["variance"].iloc[0] == pytest.approx(0.0004, abs=1e-15)
    assert int(frame["n_observations"].iloc[0]) == 4


def test_variance_realisee_centree_retire_la_moyenne() -> None:
    """Trois séances à +2 %, +2 % et -1 % centrées rendent 0,0006.

    La moyenne vaut 0,01. Les écarts valent 0,01, 0,01 et -0,02, dont les
    carrés somment 0,0001 plus 0,0001 plus 0,0004, soit 0,0006.
    """
    serie = _daily({"2020-03": [0.02, 0.02, -0.01]})
    frame = realized_variance(serie, demean=True)
    assert frame["variance"].iloc[0] == pytest.approx(0.0006, abs=1e-15)


def test_variance_realisee_indexee_en_fin_de_mois() -> None:
    """La variance de janvier 2020 porte la date du 31 janvier 2020."""
    serie = _daily({"2020-01": [0.01, 0.02], "2020-02": [0.01, 0.01]})
    frame = realized_variance(serie)
    assert list(frame.index) == [pd.Timestamp("2020-01-31"), pd.Timestamp("2020-02-29")]


def test_variance_realisee_filtre_les_mois_courts() -> None:
    """Un mois de deux séances disparaît quand le minimum en exige trois."""
    serie = _daily({"2020-01": [0.01, 0.02], "2020-02": [0.01, 0.01, 0.01]})
    frame = realized_variance(serie, min_observations=3)
    assert math.isnan(frame["variance"].iloc[0])
    assert frame["variance"].iloc[1] == pytest.approx(0.0003, abs=1e-15)
    assert int(frame["n_observations"].iloc[0]) == 2


def test_variance_nulle_devient_manquante() -> None:
    """Un mois entièrement plat ne rend pas un poids infini."""
    serie = _daily({"2020-01": [0.0, 0.0, 0.0], "2020-02": [0.01, 0.01]})
    frame = realized_variance(serie)
    assert math.isnan(frame["variance"].iloc[0])


def test_variance_realisee_refuse_un_minimum_nul() -> None:
    """Un minimum de zéro séance n'a pas de sens et lève."""
    with pytest.raises(ConfigError):
        realized_variance(_daily({"2020-01": [0.01]}), min_observations=0)


def test_variance_realisee_refuse_une_serie_vide() -> None:
    """Une série sans aucune séance ne définit aucune variance."""
    vide = pd.Series(dtype=float, index=pd.DatetimeIndex([], name="date"))
    with pytest.raises(InsufficientDataError):
        realized_variance(vide)


def test_serie_non_triee_est_refusee() -> None:
    """Une série datée à l'envers fausserait tous les décalages."""
    index = pd.DatetimeIndex(["2020-01-03", "2020-01-02"], name="date")
    with pytest.raises(DataQualityError):
        realized_variance(pd.Series([0.01, 0.02], index=index))


# --------------------------------------------------------------------------- #
# Les deux autres mesures de variance
# --------------------------------------------------------------------------- #


def test_ewma_sur_une_serie_constante_egale_le_carre() -> None:
    """Sur des rendements constants, le lissage rend exactement leur carré.

    La récurrence part de la première observation, donc :math:`h_d` vaut
    :math:`f^2` à chaque pas si tous les carrés sont égaux. La variance
    mensuelle vaut alors le nombre de séances multiplié par ce carré.
    """
    serie = _daily({"2020-01": [0.01] * 20})
    frame = ewma_variance(serie, halflife_days=5.0)
    assert frame["variance"].iloc[0] == pytest.approx(20 * 0.0001, rel=1e-12)


def test_ewma_refuse_une_demi_vie_negative() -> None:
    """Une demi-vie nulle ou négative n'a pas de sens."""
    with pytest.raises(ConfigError):
        ewma_variance(_daily({"2020-01": [0.01, 0.02]}), halflife_days=0.0)


def test_mesure_de_variance_inconnue_leve() -> None:
    """Un nom de mesure mal orthographié lève au lieu de choisir par défaut."""
    with pytest.raises(ConfigError):
        monthly_variance(_daily({"2020-01": [0.01, 0.02]}), method="garsh")  # type: ignore[arg-type]


def test_mesure_realisee_par_le_repartiteur() -> None:
    """Le répartiteur rend le même tableau que l'appel direct."""
    serie = _daily({"2020-01": [0.01, -0.02, 0.03]})
    direct = realized_variance(serie)
    par_nom = monthly_variance(serie, method="realized")
    pd.testing.assert_frame_equal(direct, par_nom)


# --------------------------------------------------------------------------- #
# Les poids, et la causalité
# --------------------------------------------------------------------------- #


def test_le_poids_du_mois_emploie_la_variance_du_mois_precedent() -> None:
    """Le poids de février vaut l'inverse de la variance de janvier.

    Avec des variances de 0,01 puis 0,04, le poids de février vaut 100 et celui
    de mars 25. Le poids de janvier est manquant, aucun mois ne le précédant.
    """
    variance = _monthly("2020-01", [0.01, 0.04, 0.02])
    poids = managed_weights(variance, constant=1.0)
    assert math.isnan(poids.iloc[0])
    assert poids.iloc[1] == pytest.approx(100.0)
    assert poids.iloc[2] == pytest.approx(25.0)


def test_le_plafond_de_levier_borne_le_poids() -> None:
    """Un plafond de dix ramène un poids de cent à dix, et laisse les autres."""
    variance = _monthly("2020-01", [0.01, 0.5, 0.5])
    poids = managed_weights(variance, constant=1.0, leverage_cap=10.0)
    assert poids.iloc[1] == pytest.approx(10.0)
    assert poids.iloc[2] == pytest.approx(2.0)


def test_le_plafond_negatif_est_refuse() -> None:
    """Un plafond nul rendrait tous les poids nuls sans le dire."""
    with pytest.raises(ConfigError):
        managed_weights(_monthly("2020-01", [0.01, 0.02]), constant=1.0, leverage_cap=0.0)


def test_l_inverse_de_la_variance_n_est_pas_decale() -> None:
    """La série d'inverse garde l'index de sa variance, sans décalage.

    Le décalage appartient à :func:`managed_weights`, et le vérifier ici
    empêche qu'un second décalage s'ajoute au premier.
    """
    variance = _monthly("2020-01", [0.01, 0.04])
    inverse = leverage_series(variance)
    assert inverse.iloc[0] == pytest.approx(100.0)
    assert inverse.iloc[1] == pytest.approx(25.0)


def test_le_plafond_s_applique_au_poids_final() -> None:
    """Le plafond borne la constante divisée par la variance, pas l'inverse seul.

    Avec une constante de deux et une variance de 0,5, le poids vaut quatre
    avant plafond, donc un plafond de trois le ramène à trois. Un plafond posé
    sur le seul inverse aurait laissé passer quatre.
    """
    variance = _monthly("2020-01", [0.5, 0.5])
    poids = managed_weights(variance, constant=2.0, leverage_cap=3.0)
    assert poids.iloc[1] == pytest.approx(3.0)


def test_le_poids_ne_depend_pas_de_la_variance_du_mois_meme() -> None:
    """Perturber la variance d'un mois laisse le poids de ce mois inchangé.

    C'est le contrôle de causalité de la règle 1, et il est plus exigeant que le
    contrôle du dernier mois. Le poids porté par le troisième mois emploie la
    variance du deuxième, donc la variance du troisième ne doit rien y changer.
    """
    variance = _monthly("2020-01", [0.01, 0.02, 0.03, 0.04])
    avant = managed_weights(variance, constant=1.0)
    perturbee = variance.copy()
    perturbee.iloc[2] = perturbee.iloc[2] * 1000.0
    apres = managed_weights(perturbee, constant=1.0)
    pd.testing.assert_series_equal(avant.iloc[:3], apres.iloc[:3])
    assert apres.iloc[3] != pytest.approx(avant.iloc[3])


# --------------------------------------------------------------------------- #
# Les deux constantes
# --------------------------------------------------------------------------- #


def test_la_constante_de_plein_echantillon_egalise_les_ecarts_types() -> None:
    """La série gérée a exactement l'écart type de la série d'origine.

    C'est la propriété qui définit la constante, donc le contrôle le plus
    direct de son implémentation.
    """
    generateur = np.random.default_rng(7)
    facteur = _monthly("1990-01", list(generateur.normal(0.005, 0.04, 240)))
    variance = _monthly("1990-01", list(generateur.uniform(0.001, 0.01, 240)))
    resultat = volatility_managed_returns(facteur, variance)
    assert resultat.returns.std(ddof=1) == pytest.approx(resultat.base.std(ddof=1), rel=1e-12)


def test_la_constante_de_plein_echantillon_vaut_le_rapport_des_ecarts_types() -> None:
    """La constante vaut l'écart type du facteur divisé par celui du quotient."""
    facteur = _monthly("2000-01", [0.01, -0.02, 0.03, 0.00])
    quotient = _monthly("2000-01", [0.5, -1.0, 1.5, 0.0])
    attendu = float(np.std([0.01, -0.02, 0.03, 0.0], ddof=1)) / float(np.std([0.5, -1.0, 1.5, 0.0], ddof=1))
    assert full_sample_constant(facteur, quotient) == pytest.approx(attendu, rel=1e-12)


def test_la_constante_en_expansion_est_decalee_d_un_mois() -> None:
    """La constante du mois quatre est calculée sur les mois un à trois.

    Avec un minimum de trois mois, la première valeur non manquante apparaît au
    quatrième mois, et elle égale le rapport des écarts types des trois
    premiers.
    """
    facteur = _monthly("2000-01", [0.01, -0.02, 0.03, 0.05, -0.01])
    quotient = _monthly("2000-01", [0.5, -1.0, 1.5, 2.0, -0.5])
    constante = expanding_constant(facteur, quotient, min_periods=3)
    assert constante.iloc[:3].isna().all()
    attendu = float(np.std([0.01, -0.02, 0.03], ddof=1)) / float(np.std([0.5, -1.0, 1.5], ddof=1))
    assert constante.iloc[3] == pytest.approx(attendu, rel=1e-12)


def test_la_constante_en_expansion_ignore_le_mois_courant() -> None:
    """Perturber un mois laisse la constante de ce mois inchangée.

    La constante portée par le mois quatre emploie les mois un à trois, donc
    une perturbation du mois quatre ne doit toucher que les mois suivants.
    """
    facteur = _monthly("2000-01", [0.01, -0.02, 0.03, 0.05, -0.01, 0.02])
    quotient = _monthly("2000-01", [0.5, -1.0, 1.5, 2.0, -0.5, 1.0])
    avant = expanding_constant(facteur, quotient, min_periods=3)
    facteur_perturbe = facteur.copy()
    facteur_perturbe.iloc[3] = 10.0
    apres = expanding_constant(facteur_perturbe, quotient, min_periods=3)
    pd.testing.assert_series_equal(avant.iloc[:4], apres.iloc[:4])
    assert apres.iloc[4] != pytest.approx(avant.iloc[4])


def test_la_constante_en_expansion_refuse_un_minimum_d_un_mois() -> None:
    """Un écart type sur un seul mois n'existe pas."""
    facteur = _monthly("2000-01", [0.01, 0.02])
    with pytest.raises(ConfigError):
        expanding_constant(facteur, facteur, min_periods=1)


def test_constante_inconnue_leve() -> None:
    """Un mot de constante non reconnu lève au lieu de choisir par défaut."""
    facteur = _monthly("2000-01", [0.01, 0.02, 0.03])
    variance = _monthly("2000-01", [0.01, 0.02, 0.03])
    with pytest.raises(ConfigError):
        volatility_managed_returns(facteur, variance, constant="retrospective")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# La régression d'engendrement
# --------------------------------------------------------------------------- #


def test_un_multiple_exact_du_facteur_rend_un_alpha_nul() -> None:
    """Deux fois le facteur rend un bêta de deux et un alpha nul.

    Les trois valeurs attendues viennent de l'algèbre de la régression, pas du
    code : une relation exacte sans bruit a un coefficient de détermination de
    un et un résidu nul.
    """
    generateur = np.random.default_rng(11)
    base = _monthly("1990-01", list(generateur.normal(0.005, 0.04, 120)))
    resultat = spanning_regression(2.0 * base, base)
    assert resultat.beta == pytest.approx(2.0, rel=1e-10)
    assert resultat.alpha_annual == pytest.approx(0.0, abs=1e-10)
    assert resultat.r_squared == pytest.approx(1.0, rel=1e-10)


def test_un_alpha_mensuel_impose_se_retrouve_annualise() -> None:
    """Un décalage mensuel de 0,5 % rend un alpha annualisé de 6 %.

    L'annualisation retenue par le paquet multiplie l'alpha mensuel par douze,
    donc 0,005 fois douze font 0,06.
    """
    generateur = np.random.default_rng(13)
    base = _monthly("1990-01", list(generateur.normal(0.005, 0.04, 240)))
    gere = 0.5 * base + 0.005
    resultat = spanning_regression(gere, base)
    assert resultat.alpha_annual == pytest.approx(0.06, rel=1e-8)
    assert resultat.beta == pytest.approx(0.5, rel=1e-8)


def test_le_ratio_d_appreciation_ne_bouge_pas_avec_l_echelle() -> None:
    """Multiplier la série gérée par trois laisse le ratio d'appréciation.

    L'alpha et la volatilité résiduelle sont tous deux multipliés par trois,
    donc leur rapport ne change pas.
    """
    generateur = np.random.default_rng(17)
    base = _monthly("1990-01", list(generateur.normal(0.005, 0.04, 240)))
    gere = 0.6 * base + pd.Series(generateur.normal(0.002, 0.03, 240), index=base.index)
    simple = spanning_regression(gere, base)
    triple = spanning_regression(3.0 * gere, base)
    assert triple.appraisal_ratio == pytest.approx(simple.appraisal_ratio, rel=1e-10)
    assert triple.beta == pytest.approx(3.0 * simple.beta, rel=1e-10)


def test_la_colonne_rmse_de_l_article_vaut_racine_de_douze_fois_la_volatilite() -> None:
    """La colonne « RMSE » se déduit de la volatilité résiduelle annualisée.

    L'article imprime 51,39 pour le marché et un ratio d'appréciation de 0,33
    avec un alpha de 4,86. La seule lecture cohérente des deux nombres est
    celle codée ici, et ce test vérifie la conversion.
    """
    generateur = np.random.default_rng(19)
    base = _monthly("1990-01", list(generateur.normal(0.005, 0.04, 240)))
    gere = 0.6 * base + pd.Series(generateur.normal(0.002, 0.03, 240), index=base.index)
    resultat = spanning_regression(gere, base)
    attendu = resultat.residual_vol_annual * 100.0 * math.sqrt(12.0)
    assert resultat.paper_rmse == pytest.approx(attendu, rel=1e-12)
    assert resultat.appraisal_ratio == pytest.approx(
        math.sqrt(12.0) * resultat.alpha_annual * 100.0 / resultat.paper_rmse, rel=1e-12
    )


def test_la_regression_refuse_un_echantillon_de_deux_mois() -> None:
    """Deux points définissent une droite exacte, sans résidu ni erreur type."""
    base = _monthly("2000-01", [0.01, 0.02])
    with pytest.raises(InsufficientDataError):
        spanning_regression(base, base)


# --------------------------------------------------------------------------- #
# Les grandeurs dérivées de l'article
# --------------------------------------------------------------------------- #


def test_le_ratio_d_appreciation_du_marche_de_l_article() -> None:
    """L'alpha de 4,86 et la RMSE de 51,39 rendent 0,328, valeur de l'article.

    Le calcul est celui de la fiche de littérature, fait à la main : racine de
    douze fois 4,86 divisé par 51,39.
    """
    volatilite_residuelle = 51.39 / (100.0 * math.sqrt(12.0))
    assert appraisal_ratio(0.0486, volatilite_residuelle) == pytest.approx(0.3276, abs=5e-4)


def test_le_gain_d_utilite_de_l_article() -> None:
    """Un Sharpe de 0,42 et un ratio de 0,33 rendent 61,7 %.

    Le calcul vient de la fiche de littérature : 0,33 au carré divisé par 0,42
    au carré vaut 0,6173.
    """
    assert utility_gain(0.42, 0.33) == pytest.approx(0.6173, abs=5e-4)


def test_le_sharpe_combine_suit_pythagore() -> None:
    """Un Sharpe de 0,3 et un ratio de 0,4 rendent exactement 0,5."""
    assert combined_sharpe(0.3, 0.4) == pytest.approx(0.5, rel=1e-12)


def test_un_sharpe_nul_rend_le_gain_indefini() -> None:
    """Le gain relatif n'existe pas quand le repère vaut zéro."""
    with pytest.raises(ConfigError):
        utility_gain(0.0, 0.3)


def test_ratio_d_appreciation_sans_residu() -> None:
    """Une volatilité résiduelle nulle rend une valeur manquante, pas l'infini."""
    assert math.isnan(appraisal_ratio(0.05, 0.0))


# --------------------------------------------------------------------------- #
# Les deux constructions en temps réel
# --------------------------------------------------------------------------- #


def test_l_ecart_couvert_emploie_un_beta_du_passe() -> None:
    """Le bêta du mois est estimé sur les mois antérieurs, jamais sur le mois.

    Sur une relation exacte sans bruit, le bêta passé vaut le bêta vrai, donc
    l'écart couvert est nul à la précision machine.
    """
    generateur = np.random.default_rng(23)
    base = _monthly("1990-01", list(generateur.normal(0.005, 0.04, 120)))
    gere = 0.7 * base
    ecart = hedged_spread(gere, base, min_periods=12)
    assert float(np.max(np.abs(ecart.to_numpy()))) < 1e-12


def test_le_beta_de_couverture_ignore_le_mois_courant() -> None:
    """Perturber le rendement géré d'un mois ne change que ce mois et la suite.

    Le bêta employé au mois vingt est estimé sur les mois antérieurs. Une
    perturbation du mois vingt déplace donc l'écart du mois vingt par son seul
    rendement, et laisse intacts les écarts des mois un à dix-neuf.
    """
    generateur = np.random.default_rng(29)
    base = _monthly("1990-01", list(generateur.normal(0.005, 0.04, 60)))
    gere = 0.7 * base + pd.Series(generateur.normal(0.0, 0.02, 60), index=base.index)
    avant = hedged_spread(gere, base, min_periods=12)
    gere_perturbe = gere.copy()
    gere_perturbe.iloc[20] = 5.0
    apres = hedged_spread(gere_perturbe, base, min_periods=12)
    position = int(avant.index.get_loc(gere.index[20]))
    pd.testing.assert_series_equal(avant.iloc[:position], apres.iloc[:position])
    ecart_attendu = 5.0 - float(gere.iloc[20])
    assert apres.iloc[position] - avant.iloc[position] == pytest.approx(ecart_attendu, rel=1e-10)


def test_la_combinaison_en_temps_reel_commence_apres_le_minimum() -> None:
    """Avec 60 mois d'historique exigés sur 120 mois, il reste 60 décisions."""
    generateur = np.random.default_rng(31)
    base = _monthly("1990-01", list(generateur.normal(0.005, 0.04, 120)))
    gere = pd.Series(generateur.normal(0.004, 0.05, 120), index=base.index)
    table = real_time_combination(base, gere, min_periods=60, risk_aversion=3.0)
    assert len(table) == 60
    assert list(table.columns) == ["combination", "base_only", "weight_base", "weight_managed"]


def test_le_poids_du_facteur_seul_suit_la_formule_de_merton() -> None:
    """Le poids du titre unique vaut la moyenne sur aversion fois variance.

    La formule est celle de Merton, écrite à la main : le premier poids
    employé porte sur les 60 premiers mois d'historique.
    """
    generateur = np.random.default_rng(37)
    base = _monthly("1990-01", list(generateur.normal(0.005, 0.04, 120)))
    gere = pd.Series(generateur.normal(0.004, 0.05, 120), index=base.index)
    table = real_time_combination(base, gere, min_periods=60, risk_aversion=3.0)
    historique = base.iloc[:60]
    attendu = float(historique.mean()) / (3.0 * float(historique.var(ddof=1)))
    realise = float(base.iloc[60])
    assert table["base_only"].iloc[0] == pytest.approx(attendu * realise, rel=1e-10)


def test_la_combinaison_refuse_une_aversion_nulle() -> None:
    """Une aversion nulle rendrait des poids infinis."""
    base = _monthly("1990-01", [0.01] * 30)
    with pytest.raises(ConfigError):
        real_time_combination(base, base, min_periods=10, risk_aversion=0.0)


def test_la_combinaison_refuse_un_historique_trop_court() -> None:
    """Un minimum plus long que l'échantillon ne laisse aucune décision."""
    base = _monthly("1990-01", [0.01, 0.02, 0.03])
    with pytest.raises(InsufficientDataError):
        real_time_combination(base, base, min_periods=10, risk_aversion=3.0)


# --------------------------------------------------------------------------- #
# Le portefeuille complet
# --------------------------------------------------------------------------- #


def test_le_portefeuille_gere_perd_son_premier_mois() -> None:
    """Le premier mois ne peut pas être géré, aucune variance ne le précède."""
    facteur = _monthly("2000-01", [0.01, -0.02, 0.03, 0.04])
    variance = _monthly("2000-01", [0.01, 0.02, 0.04, 0.01])
    resultat = volatility_managed_returns(facteur, variance)
    assert resultat.n_observations == 3
    assert resultat.returns.index[0] == pd.Timestamp("2000-02-29")


def test_le_poids_du_portefeuille_gere_est_la_constante_sur_la_variance() -> None:
    """Le poids de février vaut la constante divisée par la variance de janvier."""
    facteur = _monthly("2000-01", [0.01, -0.02, 0.03, 0.04])
    variance = _monthly("2000-01", [0.01, 0.02, 0.04, 0.01])
    resultat = volatility_managed_returns(facteur, variance)
    constante = float(resultat.constant)
    assert resultat.weights.iloc[0] == pytest.approx(constante / 0.01, rel=1e-12)
    assert resultat.returns.iloc[0] == pytest.approx(resultat.weights.iloc[0] * (-0.02), rel=1e-12)


def test_la_frequence_annuelle_change_l_annualisation() -> None:
    """Un alpha annuel imposé se retrouve tel quel en fréquence annuelle."""
    generateur = np.random.default_rng(41)
    index = pd.DatetimeIndex(pd.date_range("1990-12-31", periods=40, freq="YE"), name="date")
    base = pd.Series(generateur.normal(0.06, 0.18, 40), index=index)
    gere = 0.5 * base + 0.02
    resultat = spanning_regression(gere, base, frequency=Frequency.ANNUAL)
    assert resultat.alpha_annual == pytest.approx(0.02, rel=1e-8)


# --------------------------------------------------------------------------- #
# La preuve d'absence d'information future, par troncature
# --------------------------------------------------------------------------- #


def _chaine_tenable(facteur: pd.Series, variance: pd.Series, minimum: int) -> pd.Series:
    """Rend l'écart couvert en temps réel, constante et bêta estimés sur le passé."""
    gere = volatility_managed_returns(facteur, variance, constant="expanding", min_periods=minimum)
    return hedged_spread(gere.returns, gere.base, min_periods=minimum)


def test_la_chaine_tenable_ne_bouge_pas_quand_on_coupe_le_futur() -> None:
    """Couper les derniers mois ne change aucune valeur des mois précédents.

    C'est la propriété qui définit l'absence d'information future, et elle se
    vérifie sans connaître le code : une série calculée sur 1990-2010 doit
    coïncider avec la même série calculée sur 1990-2000, sur les mois communs.
    Un seul écart non nul prouverait qu'une statistique de fin d'échantillon
    remonte le temps.
    """
    generateur = np.random.default_rng(7)
    index = pd.DatetimeIndex(pd.date_range("1990-01-31", periods=300, freq="ME"), name="date")
    facteur = pd.Series(generateur.normal(0.006, 0.045, 300), index=index, name="facteur")
    variance = pd.Series(generateur.gamma(2.0, 0.001, 300), index=index, name="variance")

    complet = _chaine_tenable(facteur, variance, 60)
    for coupure in (180, 220, 270):
        tronque = _chaine_tenable(facteur.iloc[:coupure], variance.iloc[:coupure], 60)
        commun = tronque.index.intersection(complet.index)
        assert len(commun) > 50
        assert float((tronque.loc[commun] - complet.loc[commun]).abs().max()) == 0.0


def test_la_constante_de_plein_echantillon_bouge_quand_on_coupe_le_futur() -> None:
    """Le contrôle inverse : la version de l'article, elle, dépend de la fin.

    Sans ce second test, le premier ne prouverait rien : il pourrait passer sur
    une chaîne insensible à tout. La constante de plein échantillon est un
    regard en avant assumé, donc tronquer l'échantillon DOIT déplacer ses
    valeurs passées.
    """
    generateur = np.random.default_rng(11)
    index = pd.DatetimeIndex(pd.date_range("1990-01-31", periods=300, freq="ME"), name="date")
    facteur = pd.Series(generateur.normal(0.006, 0.045, 300), index=index, name="facteur")
    variance = pd.Series(generateur.gamma(2.0, 0.001, 300), index=index, name="variance")

    complet = volatility_managed_returns(facteur, variance).returns
    tronque = volatility_managed_returns(facteur.iloc[:150], variance.iloc[:150]).returns
    commun = tronque.index.intersection(complet.index)
    assert float((tronque.loc[commun] - complet.loc[commun]).abs().max()) > 1e-6

"""Les tests du momentum de série temporelle, dont chaque attendu vient d'ailleurs.

Aucune valeur attendue de ce fichier ne sort du code testé. Elles viennent
d'une somme géométrique calculée à la main, d'une propriété mathématique
invariante, d'un calcul indépendant écrit en NumPy pur, ou d'un chiffre publié
par Moskowitz, Ooi et Pedersen (2012).
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from quantlab.core.errors import ConfigError, InsufficientDataError
from quantlab.features.transforms import assert_causal
from quantlab.strategies.time_series_momentum import (
    DEFAULT_ANNUALIZATION_DAYS,
    DEFAULT_TARGET_VOLATILITY,
    PAPER_GRID,
    cohort_positions,
    diversified_weights,
    ex_ante_volatility,
    formation_signal,
    grid_weights,
    position_sizes,
    smoothing_from_center_of_mass,
    tsmom_weights,
)


def _dates(n: int, freq: str = "B") -> pd.DatetimeIndex:
    """Rend un index de dates, ouvrables ou mensuelles, pour les fixtures."""
    return pd.date_range("2000-01-31", periods=n, freq=freq)


# --------------------------------------------------------------------------- #
# Le lissage déduit du centre de masse
# --------------------------------------------------------------------------- #


def test_lissage_egale_soixante_soixante_et_unieme() -> None:
    """Le centre de masse de 60 jours de l'article donne 60/61, calculé à la main."""
    assert smoothing_from_center_of_mass(60.0) == pytest.approx(60.0 / 61.0, abs=1e-15)


def test_lissage_retrouve_le_centre_de_masse_par_sommation() -> None:
    r"""La somme :math:`\sum_i (1-\delta)\delta^i i` redonne le centre de masse.

    C'est la condition publiée par l'article. Elle est ici évaluée par sommation
    explicite jusqu'à un rang élevé, donc sans réutiliser la forme fermée que la
    fonction applique.
    """
    for centre in (5.0, 20.0, 60.0, 250.0):
        delta = smoothing_from_center_of_mass(centre)
        i = np.arange(0, 400_000)
        poids = (1.0 - delta) * delta**i
        assert float((poids * i).sum()) == pytest.approx(centre, rel=1e-6)
        assert float(poids.sum()) == pytest.approx(1.0, rel=1e-9)


def test_lissage_refuse_un_centre_de_masse_negatif() -> None:
    """Un centre de masse nul ou négatif n'a pas de lissage."""
    with pytest.raises(ConfigError):
        smoothing_from_center_of_mass(0.0)


# --------------------------------------------------------------------------- #
# La volatilité ex ante
# --------------------------------------------------------------------------- #


def test_l_annualisation_par_defaut_vaut_les_261_jours_de_l_article() -> None:
    """L'article écrit 261, pas les 252 usuels, et ce défaut ne doit pas glisser.

    La valeur attendue est celle imprimée dans l'équation de la volatilité
    ex ante, page 234 du fac-similé. Statut : rapporté.
    """
    assert DEFAULT_ANNUALIZATION_DAYS == 261.0
    assert DEFAULT_TARGET_VOLATILITY == 0.40


def test_volatilite_nulle_sur_des_rendements_constants() -> None:
    """Des rendements constants n'ont aucune dispersion, donc aucune volatilité.

    La propriété est mathématique : tous les écarts à la moyenne pondérée sont
    exactement nuls, quel que soit le lissage.
    """
    idx = _dates(400)
    r = pd.DataFrame({"A": np.full(400, 0.001)}, index=idx)
    vol = ex_ante_volatility(r, min_periods=60)
    assert vol["A"].dropna().abs().max() == pytest.approx(0.0, abs=1e-12)


def test_volatilite_d_une_serie_alternee_tend_vers_la_racine_de_kappa() -> None:
    r"""Sur :math:`+c, -c, +c, \ldots`, la volatilité tend vers :math:`|c|\sqrt{\kappa}`.

    La moyenne pondérée d'une série alternée tend vers zéro quand le lissage est
    proche de un, donc la variance pondérée tend vers :math:`c^2` et la
    volatilité annualisée vers :math:`|c|\sqrt{261}`.
    """
    idx = _dates(3000)
    c = 0.01
    valeurs = np.where(np.arange(3000) % 2 == 0, c, -c)
    r = pd.DataFrame({"A": valeurs}, index=idx)
    vol = ex_ante_volatility(r, min_periods=60)
    attendu = c * math.sqrt(261.0)
    assert float(vol["A"].iloc[-1]) == pytest.approx(attendu, rel=1e-3)


def test_volatilite_reproduit_une_somme_ponderee_ecrite_a_la_main() -> None:
    r"""La valeur du dernier jour égale la somme pondérée écrite en NumPy pur.

    L'attendu est calculé ici par la double somme de l'article, sur les poids
    tronqués et renormalisés, sans appeler ``ewm``.
    """
    rng = np.random.default_rng(20260902)
    n = 500
    idx = _dates(n)
    x = rng.normal(0.0, 0.012, size=n)
    r = pd.DataFrame({"A": x}, index=idx)

    delta = 60.0 / 61.0
    # L'équation somme les rendements jusqu'à t-1, donc le dernier jour est exclu.
    passe = x[:-1][::-1]
    poids = (1.0 - delta) * delta ** np.arange(passe.size)
    poids = poids / poids.sum()
    moyenne = float((poids * passe).sum())
    variance = float((poids * (passe - moyenne) ** 2).sum())
    attendu = math.sqrt(261.0 * variance)

    obtenu = float(ex_ante_volatility(r, min_periods=60)["A"].iloc[-1])
    assert obtenu == pytest.approx(attendu, rel=1e-12)


def test_volatilite_ignore_le_rendement_du_jour() -> None:
    """Changer le rendement du jour t laisse la volatilité du jour t inchangée.

    C'est la traduction directe de l'indice ``t-1-i`` de l'équation. Sans le
    décalage, cette égalité échoue.
    """
    rng = np.random.default_rng(7)
    idx = _dates(400)
    x = rng.normal(0.0, 0.01, size=400)
    base = pd.DataFrame({"A": x}, index=idx)
    trafique = base.copy()
    trafique.iloc[-1, 0] = 0.5

    v1 = ex_ante_volatility(base, min_periods=60)["A"].iloc[-1]
    v2 = ex_ante_volatility(trafique, min_periods=60)["A"].iloc[-1]
    assert float(v1) == pytest.approx(float(v2), abs=1e-15)


def test_volatilite_passe_le_controle_de_causalite() -> None:
    """Le contrôle générique de causalité du laboratoire accepte la fonction."""
    rng = np.random.default_rng(11)
    idx = _dates(600)
    source = pd.DataFrame({"A": rng.normal(0.0, 0.01, size=600)}, index=idx)
    assert_causal(
        lambda s: ex_ante_volatility(s, min_periods=60),
        source,
        name="ex_ante_volatility",
    )


def test_volatilite_refuse_un_tableau_vide() -> None:
    """Un tableau sans ligne ne donne aucune estimation."""
    with pytest.raises(InsufficientDataError):
        ex_ante_volatility(pd.DataFrame({"A": pd.Series(dtype=float)}), min_periods=60)


def test_volatilite_refuse_une_annualisation_negative() -> None:
    """Un facteur d'annualisation négatif rendrait une racine imaginaire."""
    idx = _dates(100)
    r = pd.DataFrame({"A": np.full(100, 0.001)}, index=idx)
    with pytest.raises(ConfigError):
        ex_ante_volatility(r, annualization_days=-1.0, min_periods=60)


def test_volatilite_du_papier_depasse_celle_a_252_de_1_77_pour_cent() -> None:
    """L'écart entre 261 et 252 vaut la racine de leur rapport, moins un.

    La fiche de littérature l'annonce à 1,77 %. Le contrôle mesure l'écart sur
    une série réelle et le compare à ce chiffre publié.
    """
    rng = np.random.default_rng(3)
    idx = _dates(800)
    r = pd.DataFrame({"A": rng.normal(0.0, 0.01, size=800)}, index=idx)
    a = ex_ante_volatility(r, annualization_days=261.0, min_periods=60)["A"].iloc[-1]
    b = ex_ante_volatility(r, annualization_days=252.0, min_periods=60)["A"].iloc[-1]
    assert float(a / b - 1.0) == pytest.approx(0.0177, abs=5e-5)


# --------------------------------------------------------------------------- #
# Le signal de formation
# --------------------------------------------------------------------------- #


def test_signal_positif_apres_douze_mois_de_hausse() -> None:
    """Douze mois positifs rendent un signal long, et la fenêtre courte rien."""
    idx = _dates(24, freq="ME")
    r = pd.DataFrame({"A": np.full(24, 0.01)}, index=idx)
    s = formation_signal(r, 12)
    assert bool(s["A"].iloc[:11].isna().all())
    assert float(s["A"].iloc[11]) == 1.0
    assert float(s["A"].iloc[-1]) == 1.0


def test_signal_negatif_apres_douze_mois_de_baisse() -> None:
    """Douze mois négatifs rendent un signal court."""
    idx = _dates(24, freq="ME")
    r = pd.DataFrame({"A": np.full(24, -0.01)}, index=idx)
    assert float(formation_signal(r, 12)["A"].iloc[-1]) == -1.0


# --------------------------------------------------------------------------- #
# Le dimensionnement des positions
# --------------------------------------------------------------------------- #


def test_position_vaut_deux_fois_le_signal_a_vingt_pour_cent_de_volatilite() -> None:
    """À 40 % visés et 20 % estimés, la position vaut exactement deux.

    Le calcul est celui de la docstring : 0,40 divisé par 0,20.
    """
    idx = _dates(3, freq="ME")
    s = pd.DataFrame({"A": [1.0, -1.0, 0.0]}, index=idx)
    v = pd.DataFrame({"A": [0.20, 0.20, 0.20]}, index=idx)
    p = position_sizes(s, v)
    assert list(p["A"]) == [2.0, -2.0, 0.0]


def test_position_vaut_le_signal_a_la_volatilite_cible() -> None:
    """À volatilité estimée égale à la cible, la position vaut le signal."""
    idx = _dates(2, freq="ME")
    s = pd.DataFrame({"A": [1.0, -1.0]}, index=idx)
    v = pd.DataFrame({"A": [DEFAULT_TARGET_VOLATILITY] * 2}, index=idx)
    assert list(position_sizes(s, v)["A"]) == [1.0, -1.0]


def test_position_respecte_le_plafond_declare() -> None:
    """Un plafond de trois borne la position d'un actif à 1 % de volatilité."""
    idx = _dates(1, freq="ME")
    s = pd.DataFrame({"A": [1.0]}, index=idx)
    v = pd.DataFrame({"A": [0.01]}, index=idx)
    assert float(position_sizes(s, v)["A"].iloc[0]) == pytest.approx(40.0)
    assert float(position_sizes(s, v, max_position=3.0)["A"].iloc[0]) == pytest.approx(3.0)


def test_position_manque_la_ou_le_signal_manque() -> None:
    """Un signal manquant rend une position manquante, jamais un zéro."""
    idx = _dates(2, freq="ME")
    s = pd.DataFrame({"A": [np.nan, 1.0]}, index=idx)
    v = pd.DataFrame({"A": [0.20, 0.20]}, index=idx)
    p = position_sizes(s, v)
    assert bool(np.isnan(p["A"].iloc[0]))
    assert float(p["A"].iloc[1]) == pytest.approx(2.0)


def test_position_refuse_des_colonnes_discordantes() -> None:
    """Deux tableaux aux colonnes différentes ne s'apparient pas en silence."""
    idx = _dates(2, freq="ME")
    s = pd.DataFrame({"A": [1.0, 1.0]}, index=idx)
    v = pd.DataFrame({"B": [0.2, 0.2]}, index=idx)
    with pytest.raises(ConfigError):
        position_sizes(s, v)


# --------------------------------------------------------------------------- #
# Les cohortes
# --------------------------------------------------------------------------- #


def test_cohortes_a_un_mois_rendent_l_entree() -> None:
    """Une détention d'un mois ne moyenne rien."""
    idx = _dates(4, freq="ME")
    p = pd.DataFrame({"A": [1.0, 2.0, 4.0, 8.0]}, index=idx)
    pd.testing.assert_frame_equal(cohort_positions(p, 1), p)


def test_cohortes_a_trois_mois_moyennent_les_trois_dernieres() -> None:
    """Sur 1, 2 et 4, la troisième ligne vaut 7/3, calculé à la main."""
    idx = _dates(3, freq="ME")
    p = pd.DataFrame({"A": [1.0, 2.0, 4.0]}, index=idx)
    c = cohort_positions(p, 3)
    assert float(c["A"].iloc[0]) == pytest.approx(1.0)
    assert float(c["A"].iloc[1]) == pytest.approx(1.5)
    assert float(c["A"].iloc[2]) == pytest.approx(7.0 / 3.0)


def test_cohortes_ne_comptent_que_les_dates_ou_l_instrument_existait() -> None:
    """Un instrument entré au deuxième mois ne se dilue pas par son absence."""
    idx = _dates(3, freq="ME")
    p = pd.DataFrame({"A": [np.nan, 2.0, 4.0]}, index=idx)
    c = cohort_positions(p, 3)
    assert bool(np.isnan(c["A"].iloc[0]))
    assert float(c["A"].iloc[1]) == pytest.approx(2.0)
    assert float(c["A"].iloc[2]) == pytest.approx(3.0)


def test_cohortes_se_ferment_a_la_sortie_d_univers() -> None:
    """Un instrument sans position courante n'est plus détenu, malgré ses cohortes."""
    idx = _dates(3, freq="ME")
    p = pd.DataFrame({"A": [1.0, 2.0, np.nan]}, index=idx)
    assert bool(np.isnan(cohort_positions(p, 3)["A"].iloc[2]))


def test_cohortes_refusent_une_detention_nulle() -> None:
    """Une détention de zéro mois n'a pas de sens."""
    idx = _dates(2, freq="ME")
    with pytest.raises(ConfigError):
        cohort_positions(pd.DataFrame({"A": [1.0, 1.0]}, index=idx), 0)


# --------------------------------------------------------------------------- #
# L'équipondération
# --------------------------------------------------------------------------- #


def test_equiponderation_divise_par_le_nombre_d_instruments_presents() -> None:
    """Trois colonnes dont une manquante donnent un diviseur de deux."""
    idx = _dates(1, freq="ME")
    p = pd.DataFrame({"A": [3.0], "B": [6.0], "C": [np.nan]}, index=idx)
    w = diversified_weights(p)
    assert float(w["A"].iloc[0]) == pytest.approx(1.5)
    assert float(w["B"].iloc[0]) == pytest.approx(3.0)
    assert float(w["C"].iloc[0]) == pytest.approx(0.0)


def test_equiponderation_ne_laisse_aucune_valeur_manquante() -> None:
    """Le moteur de backtest refuse une ligne de poids trouée."""
    idx = _dates(3, freq="ME")
    p = pd.DataFrame({"A": [np.nan, 1.0, 2.0], "B": [1.0, np.nan, 2.0]}, index=idx)
    assert not bool(diversified_weights(p).isna().to_numpy().any())


def test_equiponderation_refuse_un_univers_toujours_vide() -> None:
    """Aucun instrument nulle part rend une erreur, pas un tableau de zéros."""
    idx = _dates(2, freq="ME")
    p = pd.DataFrame({"A": [np.nan, np.nan]}, index=idx)
    with pytest.raises(InsufficientDataError):
        diversified_weights(p)


# --------------------------------------------------------------------------- #
# L'enchaînement complet, et la grille
# --------------------------------------------------------------------------- #


def test_enchainement_reproduit_l_equation_du_portefeuille() -> None:
    r"""Les poids égalent :math:`S_t \lambda / (\sigma_t S)`, recalculé en NumPy pur.

    Le contrôle recopie l'équation du portefeuille diversifié de l'article et la
    compare à l'enchaînement des quatre fonctions.
    """
    idx = _dates(20, freq="ME")
    rng = np.random.default_rng(5)
    r = pd.DataFrame(rng.normal(0.005, 0.03, size=(20, 3)), index=idx, columns=["A", "B", "C"])
    v = pd.DataFrame(np.tile(np.array([0.10, 0.20, 0.40]), (20, 1)), index=idx, columns=["A", "B", "C"])
    w = tsmom_weights(r, v, lookback=12, holding=1)

    cumul = (1.0 + r).rolling(12).apply(np.prod, raw=True) - 1.0
    signe = np.sign(cumul.to_numpy())
    attendu = signe * DEFAULT_TARGET_VOLATILITY / v.to_numpy() / 3.0
    obtenu = w.to_numpy()
    valides = ~np.isnan(attendu)
    assert np.allclose(obtenu[valides], attendu[valides], atol=1e-12)


def test_grille_porte_les_soixante_quatre_cellules_du_tableau_2() -> None:
    """La grille de l'article compte huit formations et huit détentions."""
    idx = _dates(80, freq="ME")
    rng = np.random.default_rng(9)
    r = pd.DataFrame(rng.normal(0.004, 0.03, size=(80, 2)), index=idx, columns=["A", "B"])
    v = pd.DataFrame(np.full((80, 2), 0.20), index=idx, columns=["A", "B"])
    cellules = grid_weights(r, v)
    assert len(cellules) == 64
    assert len(PAPER_GRID) == 8
    assert set(cellules) == {(k, h) for k in PAPER_GRID for h in PAPER_GRID}


def test_grille_retrouve_l_enchainement_cellule_par_cellule() -> None:
    """La cellule (12, 1) de la grille égale l'enchaînement appelé seul."""
    idx = _dates(40, freq="ME")
    rng = np.random.default_rng(13)
    r = pd.DataFrame(rng.normal(0.004, 0.03, size=(40, 2)), index=idx, columns=["A", "B"])
    v = pd.DataFrame(np.full((40, 2), 0.25), index=idx, columns=["A", "B"])
    cellules = grid_weights(r, v, formations=(12,), holdings=(1, 3))
    pd.testing.assert_frame_equal(cellules[12, 1], tsmom_weights(r, v, lookback=12, holding=1))
    pd.testing.assert_frame_equal(cellules[12, 3], tsmom_weights(r, v, lookback=12, holding=3))


def test_la_volatilite_cible_ne_change_pas_le_signe_des_poids() -> None:
    """Multiplier la cible multiplie tous les poids par la même constante.

    C'est la propriété que l'article invoque pour dire que le choix de 40 % est
    sans conséquence sur le ratio de Sharpe.
    """
    idx = _dates(30, freq="ME")
    rng = np.random.default_rng(17)
    r = pd.DataFrame(rng.normal(0.004, 0.03, size=(30, 3)), index=idx, columns=["A", "B", "C"])
    v = pd.DataFrame(rng.uniform(0.05, 0.5, size=(30, 3)), index=idx, columns=["A", "B", "C"])
    w1 = tsmom_weights(r, v, target_volatility=0.40)
    w2 = tsmom_weights(r, v, target_volatility=0.10)
    assert np.allclose(w1.to_numpy(), 4.0 * w2.to_numpy(), atol=1e-12)

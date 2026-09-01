"""Tests de ``quantlab.analytics.risk``.

Règle appliquée à chaque assertion : la valeur attendue ne vient JAMAIS de la
sortie du code testé. Chaque test dit dans son commentaire laquelle des quatre
sources il emploie.

(a) calcul à la main, chiffres visibles dans le commentaire ;
(b) forme fermée ou identité mathématique ;
(c) valeur publiée, citée ;
(d) implémentation indépendante (scipy, statsmodels) sur le même intrant.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from scipy import integrate, stats
from statsmodels.tsa.stattools import acf

from quantlab.analytics.risk import (
    annualization_bias,
    cornish_fisher_quantile,
    downside_deviation,
    expected_shortfall,
    expected_shortfall_factor,
    gain_to_pain,
    hit_rate,
    kurtosis,
    lo_annualization_factor,
    sample_autocorrelation,
    semi_variance,
    skewness,
    tail_ratio,
    upside_deviation,
    value_at_risk,
    volatility,
)
from quantlab.core.determinism import make_generator
from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.types import Frequency

# Série de vingt rendements réguliers, de -10 % à +9 % par pas de 1 %.
# Elle sert de support aux tests de quantile parce que son quantile linéaire
# se calcule à la main sans ambiguïté.
LADDER = np.arange(-10, 10, dtype=float) / 100.0


@pytest.fixture
def normal_sample() -> np.ndarray:
    """Vingt mille rendements normaux indépendants, graine fixée à 20260901."""
    return make_generator(20260901).normal(loc=0.0004, scale=0.011, size=20_000)


# --------------------------------------------------------------------------- #
# Volatilité
# --------------------------------------------------------------------------- #


def test_volatility_calcul_a_la_main() -> None:
    """(a) Sur -1 %, +1 %, -1 %, +1 % la moyenne vaut 0, la somme des carrés 0,0004.

    Avec ddof = 1 : variance = 0,0004 / 3 = 1,333333e-4, écart type = 0,01154700538.
    """
    r = [-0.01, 0.01, -0.01, 0.01]
    assert volatility(r, annualize=False) == pytest.approx(math.sqrt(0.0004 / 3.0), rel=1e-12)
    assert volatility(r, annualize=False) == pytest.approx(0.011547005383792515, rel=1e-12)


def test_volatility_annualisation_racine_252() -> None:
    """(b) Identité : la version annualisée vaut la version de période fois racine de 252."""
    r = [-0.01, 0.01, -0.01, 0.01, 0.02, -0.03]
    per_period = volatility(r, Frequency.DAILY, annualize=False)
    annualised = volatility(r, Frequency.DAILY, annualize=True)
    assert annualised == pytest.approx(per_period * math.sqrt(252.0), rel=1e-12)


def test_volatility_contre_numpy(normal_sample: np.ndarray) -> None:
    """(d) Implémentation indépendante : ``numpy.std`` sur le même intrant et le même ddof."""
    assert volatility(normal_sample, annualize=False, ddof=1) == pytest.approx(
        float(np.std(normal_sample, ddof=1)), rel=1e-14
    )


def test_volatility_serie_constante_vaut_zero() -> None:
    """(b) Une série sans dispersion a un écart type nul.

    La tolérance absolue n'est pas cosmétique : 0,02 n'est pas représentable en
    binaire, la moyenne de dix copies vaut 0,019999999999999997, et l'écart type
    calculé sort à 3,66e-18 au lieu de zéro. Le seuil de 1e-15 est cent fois
    au-dessus de ce bruit et cent mille milliards de fois sous un écart type
    réaliste de rendement quotidien.
    """
    assert volatility([0.02] * 10, annualize=False) == pytest.approx(0.0, abs=1e-15)


def test_volatility_ignore_les_valeurs_manquantes() -> None:
    """(b) Retirer un NaN doit rendre le même chiffre que la série sans ce NaN."""
    avec = pd.Series([-0.01, np.nan, 0.01, -0.01, 0.01])
    sans = pd.Series([-0.01, 0.01, -0.01, 0.01])
    assert volatility(avec, annualize=False) == pytest.approx(volatility(sans, annualize=False), rel=1e-15)


def test_volatility_serie_vide_et_point_unique() -> None:
    """(b) Un écart type à ddof = 1 exige deux observations : une seule ne suffit pas."""
    with pytest.raises(InsufficientDataError):
        volatility([])
    with pytest.raises(InsufficientDataError):
        volatility([0.01])


def test_volatility_rendement_de_moins_cent_pourcent() -> None:
    """(a) Sur -100 % et +100 %, la moyenne vaut 0 et la somme des carrés 2.

    Avec ddof = 1, variance = 2 / 1 = 2 et écart type = racine de 2 = 1,4142135624.
    """
    assert volatility([-1.0, 1.0], annualize=False) == pytest.approx(math.sqrt(2.0), rel=1e-14)


# --------------------------------------------------------------------------- #
# Déviations à la baisse et à la hausse
# --------------------------------------------------------------------------- #


def test_downside_deviation_deux_conventions_a_la_main() -> None:
    """(a) Sur +2 %, -1 %, +3 %, -3 %, +1 % au seuil nul.

    Écarts défavorables : -0,01 et -0,03. Somme des carrés = 0,0001 + 0,0009 = 0,001.
    Convention « total » : 0,001 / 5 = 0,0002, racine = 0,0141421356.
    Convention « below » : 0,001 / 2 = 0,0005, racine = 0,0223606798.
    """
    r = [0.02, -0.01, 0.03, -0.03, 0.01]
    assert downside_deviation(r, annualize=False) == pytest.approx(math.sqrt(0.0002), rel=1e-12)
    assert downside_deviation(r, annualize=False, denominator="below") == pytest.approx(
        math.sqrt(0.0005), rel=1e-12
    )


def test_downside_deviation_seuil_non_nul_a_la_main() -> None:
    """(a) Mêmes rendements, seuil 1 %.

    Écarts au seuil : +0,01, -0,02, +0,02, -0,04, 0,00. Défavorables : -0,02 et -0,04.
    Somme des carrés = 0,0004 + 0,0016 = 0,002. Convention « total » : 0,002 / 5 = 0,0004,
    racine = 0,02.
    """
    r = [0.02, -0.01, 0.03, -0.03, 0.01]
    assert downside_deviation(r, 0.01, annualize=False) == pytest.approx(0.02, rel=1e-12)


def test_downside_deviation_sans_perte_vaut_zero() -> None:
    """(b) Aucun écart défavorable : la convention « total » rend zéro, « below » n'est pas définie."""
    r = [0.01, 0.02, 0.03]
    assert downside_deviation(r, annualize=False) == 0.0
    with pytest.raises(InsufficientDataError):
        downside_deviation(r, annualize=False, denominator="below")


def test_downside_deviation_convention_inconnue() -> None:
    """(b) Le paramètre de convention est fermé : toute autre valeur est refusée."""
    with pytest.raises(ConfigError):
        downside_deviation([0.01, -0.01], denominator="moyenne")  # type: ignore[arg-type]


def test_semi_variance_est_le_carre_de_la_deviation() -> None:
    """(b) Identité de définition : SV = DD au carré, à convention et seuil égaux."""
    r = [0.02, -0.01, 0.03, -0.03, 0.01, -0.005]
    dd = downside_deviation(r, 0.002, annualize=False)
    sv = semi_variance(r, 0.002)
    assert sv == pytest.approx(dd**2, rel=1e-14)


def test_semi_variances_somment_a_la_moyenne_des_carres() -> None:
    """(b) Identité : min(x,0)^2 + max(x,0)^2 = x^2, donc les deux semi-variances somment.

    Sous la convention « total », SV_bas + SV_haut = moyenne des (r - tau)^2.
    """
    rng = make_generator(7)
    r = rng.normal(0.0, 0.02, size=500)
    tau = 0.001
    bas = downside_deviation(r, tau, annualize=False) ** 2
    haut = upside_deviation(r, tau, annualize=False) ** 2
    attendu = float(np.mean((r - tau) ** 2))
    assert bas + haut == pytest.approx(attendu, rel=1e-14)


def test_semi_variance_annualise_lineairement() -> None:
    """(a) Une variance s'annualise en multipliant par N, jamais par racine de N.

    Sur +2 %, -1 %, +3 %, -3 %, +1 % au seuil nul, la somme des carrés
    défavorables vaut 0,001 et la semi-variance de période 0,001 / 5 = 0,0002.
    Annualisée en quotidien : 0,0002 x 252 = 0,0504. En mensuel : 0,0002 x 12 = 0,0024.
    Le test vérifie aussi que le facteur n'est PAS racine de 252, qui donnerait
    0,003175, un chiffre seize fois plus petit.
    """
    r = [0.02, -0.01, 0.03, -0.03, 0.01]
    assert semi_variance(r, annualize=True) == pytest.approx(0.0504, rel=1e-12)
    assert semi_variance(r, frequency=Frequency.MONTHLY, annualize=True) == pytest.approx(0.0024, rel=1e-12)
    assert semi_variance(r, annualize=True) != pytest.approx(0.0002 * math.sqrt(252.0), rel=1e-3)


def test_upside_deviation_convention_below_a_la_main() -> None:
    """(a) Convention « below » à la hausse : le dénominateur compte les seules
    observations STRICTEMENT au-dessus du seuil.

    Sur +2 %, -1 %, +3 %, -3 %, +1 % au seuil de 1 %, les écarts favorables valent
    +0,01 et +0,02, le rendement de +1 % étant exactement au seuil et donc exclu.
    Somme des carrés = 0,0001 + 0,0004 = 0,0005, divisée par 2, racine = 0,0158113883.
    Compter le point à égalité donnerait 0,0005 / 3, soit 0,0129, chiffre différent.
    """
    r = [0.02, -0.01, 0.03, -0.03, 0.01]
    assert upside_deviation(r, 0.01, annualize=False, denominator="below") == pytest.approx(
        math.sqrt(0.0005 / 2.0), rel=1e-12
    )
    assert upside_deviation(r, 0.01, annualize=False, denominator="below") != pytest.approx(
        math.sqrt(0.0005 / 3.0), rel=1e-3
    )


def test_upside_deviation_sans_gain_leve_en_convention_below() -> None:
    """(b) Sans aucune observation au-dessus du seuil, la convention « below » n'est pas définie."""
    with pytest.raises(InsufficientDataError):
        upside_deviation([-0.01, -0.02], annualize=False, denominator="below")
    with pytest.raises(ConfigError):
        upside_deviation([0.01, -0.01], denominator="moyenne")  # type: ignore[arg-type]


def test_upside_deviation_est_le_miroir_de_la_baisse() -> None:
    """(b) Symétrie : UD(r, tau) = DD(-r, -tau) en convention « total »."""
    r = np.array([0.02, -0.01, 0.03, -0.03, 0.01])
    assert upside_deviation(r, 0.005, annualize=False) == pytest.approx(
        downside_deviation(-r, -0.005, annualize=False), rel=1e-14
    )


# --------------------------------------------------------------------------- #
# Asymétrie et aplatissement
# --------------------------------------------------------------------------- #


def test_skewness_contre_scipy(normal_sample: np.ndarray) -> None:
    """(d) Implémentation indépendante : ``scipy.stats.skew`` sur le même intrant."""
    assert skewness(normal_sample) == pytest.approx(float(stats.skew(normal_sample, bias=False)), rel=1e-14)
    assert skewness(normal_sample, bias=True) == pytest.approx(
        float(stats.skew(normal_sample, bias=True)), rel=1e-14
    )


def test_kurtosis_contre_scipy(normal_sample: np.ndarray) -> None:
    """(d) Implémentation indépendante : ``scipy.stats.kurtosis``, les deux conventions."""
    assert kurtosis(normal_sample) == pytest.approx(
        float(stats.kurtosis(normal_sample, fisher=True, bias=False)), rel=1e-14
    )
    assert kurtosis(normal_sample, excess=False) == pytest.approx(
        float(stats.kurtosis(normal_sample, fisher=False, bias=False)), rel=1e-14
    )


def test_kurtosis_excedentaire_vaut_le_brut_moins_trois(normal_sample: np.ndarray) -> None:
    """(b) Identité de définition entre les deux conventions."""
    assert kurtosis(normal_sample, excess=False) - kurtosis(normal_sample) == pytest.approx(3.0, abs=1e-10)


def test_skewness_nulle_sur_serie_symetrique() -> None:
    """(b) Une série symétrique autour de sa moyenne a une asymétrie nulle."""
    assert skewness([-0.03, -0.01, 0.01, 0.03]) == pytest.approx(0.0, abs=1e-15)


def test_moments_exigent_assez_de_points() -> None:
    """(b) G1 exige trois observations, G2 en exige quatre."""
    with pytest.raises(InsufficientDataError):
        skewness([0.01, 0.02])
    with pytest.raises(InsufficientDataError):
        kurtosis([0.01, 0.02, 0.03])


# --------------------------------------------------------------------------- #
# Cornish-Fisher
# --------------------------------------------------------------------------- #


def test_cornish_fisher_sans_correction_rend_z() -> None:
    """(b) Avec S = K = 0 tous les termes correctifs s'annulent, il reste z."""
    for z in (-2.5, -1.0, 0.0, 1.0, 2.5):
        assert cornish_fisher_quantile(z, 0.0, 0.0) == pytest.approx(z, rel=1e-15, abs=1e-15)


def test_cornish_fisher_en_z_egal_un_a_la_main() -> None:
    """(a) En z = 1 : z^2 - 1 = 0, z^3 - 3z = -2, 2z^3 - 5z = -3.

    Donc z_CF = 1 + 0 - 2K/24 + 3S^2/36 = 1 - K/12 + S^2/12.
    Avec S = 0,6 et K = 2,4 : 1 - 0,2 + 0,03 = 0,83.
    """
    assert cornish_fisher_quantile(1.0, 0.6, 2.4) == pytest.approx(0.83, rel=1e-14)


def test_cornish_fisher_en_z_nul_a_la_main() -> None:
    """(a) En z = 0 : z_CF = (0 - 1) S / 6 = -S/6. Avec S = 1,2 : -0,2."""
    assert cornish_fisher_quantile(0.0, 1.2, 5.0) == pytest.approx(-0.2, rel=1e-14)


# --------------------------------------------------------------------------- #
# Valeur à risque
# --------------------------------------------------------------------------- #


def test_var_historique_sur_serie_construite_a_la_main() -> None:
    """(a) Vingt valeurs de -0,10 à +0,09 par pas de 0,01, triées par construction.

    Le quantile linéaire à alpha = 5 % se place à la position (n-1) x alpha = 19 x 0,05 = 0,95,
    donc entre x[0] = -0,10 et x[1] = -0,09 : q = -0,10 + 0,95 x 0,01 = -0,0905.
    La valeur à risque, en perte positive, vaut donc 0,0905.
    """
    assert value_at_risk(LADDER, 0.05) == pytest.approx(0.0905, abs=1e-12)


def test_var_historique_a_dix_pour_cent_a_la_main() -> None:
    """(a) Même série, alpha = 10 % : position 19 x 0,10 = 1,90, entre x[1] et x[2].

    q = -0,09 + 0,90 x 0,01 = -0,081. Valeur à risque = 0,081.
    """
    assert value_at_risk(LADDER, 0.10) == pytest.approx(0.081, abs=1e-12)


def test_var_est_une_perte_positive_et_peut_etre_negative() -> None:
    """(b) Convention déclarée : la sortie est une perte.

    Sur les cinq rendements 1 %, 2 %, 3 %, 4 %, 5 %, le quantile linéaire à 5 %
    se place en position 4 x 0,05 = 0,20, soit 0,01 + 0,20 x 0,01 = 0,012. La
    valeur à risque vaut donc -0,012 : la « pire » perte est un gain de 1,2 %,
    et aucun repliement à zéro n'est appliqué.

    Le miroir se lit ensuite par l'identité de quantile
    q_alpha(-r) = -q_{1-alpha}(r), donc VaR_alpha(-r) = -VaR_{1-alpha}(r). Sur
    la même série, le quantile à 95 % vaut 0,04 + 0,80 x 0,01 = 0,048, donc la
    valeur à risque de la série retournée vaut 0,048.
    """
    positifs = np.array([0.01, 0.02, 0.03, 0.04, 0.05])
    assert value_at_risk(positifs, 0.05) == pytest.approx(-0.012, abs=1e-14)
    assert value_at_risk(-positifs, 0.05) == pytest.approx(0.048, abs=1e-14)
    assert value_at_risk(-positifs, 0.05) == pytest.approx(-value_at_risk(positifs, 0.95), rel=1e-14)


def test_var_gaussienne_contre_scipy(normal_sample: np.ndarray) -> None:
    """(d) Implémentation indépendante : ``scipy.stats.norm.ppf`` appliqué à mu et sigma.

    VaR = -(mu + sigma * z_alpha), avec sigma à ddof = 1.
    """
    mu = float(np.mean(normal_sample))
    sigma = float(np.std(normal_sample, ddof=1))
    attendu = -(mu + sigma * float(stats.norm.ppf(0.05)))
    assert value_at_risk(normal_sample, 0.05, method="gaussian") == pytest.approx(attendu, rel=1e-13)


def test_var_cornish_fisher_sur_serie_symetrique() -> None:
    """(a) et (d) Sur une série symétrique, l'asymétrie est nulle et il ne reste
    du développement que le terme d'aplatissement.

    La valeur attendue est écrite ici en toutes lettres, sans appeler la fonction
    testée : z_CF = z + (z^3 - 3z) K / 24, avec z = -1,6448536270 le quantile
    normal à 5 % et K l'aplatissement excédentaire non biaisé rendu par scipy.
    La valeur à risque vaut ensuite -(mu + sigma z_CF), sigma à ddof = 1.
    """
    symetrique = np.array([-0.03, -0.02, -0.01, 0.0, 0.0, 0.01, 0.02, 0.03])
    assert skewness(symetrique) == pytest.approx(0.0, abs=1e-15)
    z = float(stats.norm.ppf(0.05))
    k = float(stats.kurtosis(symetrique, fisher=True, bias=False))
    z_cf = z + (z**3 - 3.0 * z) * k / 24.0
    mu = float(np.mean(symetrique))
    sigma = float(np.std(symetrique, ddof=1))
    assert value_at_risk(symetrique, 0.05, method="cornish_fisher") == pytest.approx(
        -(mu + sigma * z_cf), rel=1e-13
    )


def test_var_cornish_fisher_sur_serie_asymetrique() -> None:
    """(a) et (d) Série franchement asymétrique : le terme en S doit peser.

    Le développement complet est réécrit ici, sans appeler la fonction testée :
    z_CF = z + (z^2 - 1) S / 6 + (z^3 - 3z) K / 24 - (2z^3 - 5z) S^2 / 36.
    S et K viennent de scipy, estimateurs non biaisés, sur le même intrant.
    Le test vérifie en outre que la correction déplace réellement le chiffre,
    de plus d'un point de base par rapport à la version gaussienne, sans quoi
    l'égalité serait obtenue même en ignorant l'asymétrie.
    """
    asymetrique = np.array([-0.18, -0.02, -0.015, -0.01, -0.005, 0.0, 0.005, 0.01, 0.012, 0.02])
    s_hat = float(stats.skew(asymetrique, bias=False))
    k_hat = float(stats.kurtosis(asymetrique, fisher=True, bias=False))
    assert s_hat < -1.0
    z = float(stats.norm.ppf(0.05))
    z_cf = (
        z
        + (z**2 - 1.0) * s_hat / 6.0
        + (z**3 - 3.0 * z) * k_hat / 24.0
        - (2.0 * z**3 - 5.0 * z) * s_hat**2 / 36.0
    )
    mu = float(np.mean(asymetrique))
    sigma = float(np.std(asymetrique, ddof=1))
    obtenu = value_at_risk(asymetrique, 0.05, method="cornish_fisher")
    assert obtenu == pytest.approx(-(mu + sigma * z_cf), rel=1e-13)
    assert abs(obtenu - value_at_risk(asymetrique, 0.05, method="gaussian")) > 1e-4


def test_es_cornish_fisher_sur_serie_asymetrique() -> None:
    """(d) Implémentation indépendante : la quadrature du quantile corrigé, réécrite ici.

    ES = sigma * f - mu, avec f = -(1/alpha) fois l'intégrale de z_CF(p) sur
    [0, alpha]. L'intégrale est calculée par ``scipy.integrate.quad`` sur le
    développement réécrit dans ce test, donc sans passer par le module.
    """
    asymetrique = np.array([-0.18, -0.02, -0.015, -0.01, -0.005, 0.0, 0.005, 0.01, 0.012, 0.02])
    alpha = 0.05
    s_hat = float(stats.skew(asymetrique, bias=False))
    k_hat = float(stats.kurtosis(asymetrique, fisher=True, bias=False))

    def z_cf(p: float) -> float:
        z = float(stats.norm.ppf(p))
        return (
            z
            + (z**2 - 1.0) * s_hat / 6.0
            + (z**3 - 3.0 * z) * k_hat / 24.0
            - (2.0 * z**3 - 5.0 * z) * s_hat**2 / 36.0
        )

    integrale, _ = integrate.quad(z_cf, 0.0, alpha, limit=200)
    mu = float(np.mean(asymetrique))
    sigma = float(np.std(asymetrique, ddof=1))
    attendu = sigma * (-integrale / alpha) - mu
    obtenu = expected_shortfall(asymetrique, alpha, method="cornish_fisher")
    assert obtenu == pytest.approx(attendu, rel=1e-8)
    assert abs(obtenu - expected_shortfall(asymetrique, alpha, method="gaussian")) > 1e-4


def test_var_decroit_avec_alpha(normal_sample: np.ndarray) -> None:
    """(b) Monotonie : une queue plus étroite donne une perte de seuil plus grande."""
    assert value_at_risk(normal_sample, 0.01) > value_at_risk(normal_sample, 0.05)
    assert value_at_risk(normal_sample, 0.05) > value_at_risk(normal_sample, 0.10)


def test_var_alpha_et_methode_invalides() -> None:
    """(b) Les deux paramètres fermés refusent ce qui n'est pas dans leur domaine."""
    with pytest.raises(ConfigError):
        value_at_risk(LADDER, 0.0)
    with pytest.raises(ConfigError):
        value_at_risk(LADDER, 1.0)
    with pytest.raises(ConfigError):
        value_at_risk(LADDER, 0.05, method="montecarlo")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Perte attendue au-delà
# --------------------------------------------------------------------------- #


def test_es_historique_sur_serie_construite_a_la_main() -> None:
    """(a) Même échelle de vingt valeurs, alpha = 5 %.

    Le quantile vaut -0,0905 (voir le test de valeur à risque). Une seule
    observation lui est inférieure ou égale, -0,10. La moyenne de cette queue vaut
    -0,10, donc la perte attendue au-delà vaut 0,10 exactement.
    """
    assert expected_shortfall(LADDER, 0.05) == pytest.approx(0.10, abs=1e-12)


def test_es_historique_a_vingt_pour_cent_a_la_main() -> None:
    """(a) Même série, alpha = 20 % : position 19 x 0,20 = 3,80, entre x[3] = -0,07
    et x[4] = -0,06, donc q = -0,07 + 0,80 x 0,01 = -0,062.

    Les observations inférieures ou égales à -0,062 sont -0,10, -0,09, -0,08, -0,07,
    dont la moyenne vaut -0,34 / 4 = -0,085. La perte attendue au-delà vaut 0,085.
    """
    assert expected_shortfall(LADDER, 0.20) == pytest.approx(0.085, abs=1e-12)


def test_es_gaussienne_contre_normale_tronquee(normal_sample: np.ndarray) -> None:
    """(d) Implémentation indépendante : l'espérance d'une normale tronquée de scipy.

    ES = -(mu + sigma * E[Z | Z < z_alpha]), et ``scipy.stats.truncnorm(-inf, z).mean()``
    rend cette espérance conditionnelle sans passer par la formule testée.
    """
    alpha = 0.05
    z_alpha = float(stats.norm.ppf(alpha))
    mu = float(np.mean(normal_sample))
    sigma = float(np.std(normal_sample, ddof=1))
    esperance_tronquee = float(stats.truncnorm(-np.inf, z_alpha).mean())
    attendu = -(mu + sigma * esperance_tronquee)
    assert expected_shortfall(normal_sample, alpha, method="gaussian") == pytest.approx(attendu, rel=1e-10)


def test_es_gaussienne_contre_forme_fermee(normal_sample: np.ndarray) -> None:
    """(c) Forme fermée publiée : ES = sigma * phi(z_alpha)/alpha - mu.

    McNeil, Frey et Embrechts (2015), « Quantitative Risk Management », 2e édition,
    chapitre 2, exemple 2.14.
    """
    alpha = 0.05
    z_alpha = float(stats.norm.ppf(alpha))
    mu = float(np.mean(normal_sample))
    sigma = float(np.std(normal_sample, ddof=1))
    attendu = sigma * float(stats.norm.pdf(z_alpha)) / alpha - mu
    assert expected_shortfall(normal_sample, alpha, method="gaussian") == pytest.approx(attendu, rel=1e-13)


def test_es_factor_gaussien_vaut_la_valeur_publiee() -> None:
    """(c) Valeur publiée : à alpha = 5 %, phi(1,644854)/0,05 = 2,062713.

    Chiffre courant des manuels de gestion des risques, par exemple McNeil, Frey et
    Embrechts (2015), chapitre 2. La vérification indépendante suit en (b) au test
    suivant.
    """
    assert expected_shortfall_factor(0.05) == pytest.approx(2.062713, rel=1e-6)


def test_es_factor_cornish_fisher_retrouve_le_gaussien() -> None:
    """(b) Identité : sans asymétrie ni excès d'aplatissement, l'intégrale du quantile
    de Cornish-Fisher est celle du quantile normal.

    La voie de quadrature est forcée en injectant un excès d'aplatissement infime
    (1e-13) plutôt que zéro, ce qui évite le raccourci en forme fermée et prouve
    que la quadrature est correcte.
    """
    ferme = expected_shortfall_factor(0.05)
    quadrature = expected_shortfall_factor(0.05, 0.0, 1e-13)
    assert quadrature == pytest.approx(ferme, rel=1e-8)


def test_es_factor_par_integration_independante() -> None:
    """(d) Implémentation indépendante : intégration de x * phi(x) sur (-inf, z_alpha).

    E[Z | Z < z] = (1/alpha) * integrale de x phi(x), et le facteur vaut son opposé.
    """
    alpha = 0.05
    z_alpha = float(stats.norm.ppf(alpha))
    integrale, _ = integrate.quad(lambda x: x * float(stats.norm.pdf(x)), -np.inf, z_alpha)
    assert expected_shortfall_factor(alpha) == pytest.approx(-integrale / alpha, rel=1e-10)


def test_es_depasse_var_sur_donnees_reelles(normal_sample: np.ndarray) -> None:
    """(b) Inégalité structurelle : la moyenne de la queue dépasse son seuil."""
    for method in ("historical", "gaussian", "cornish_fisher"):
        var = value_at_risk(normal_sample, 0.05, method=method)  # type: ignore[arg-type]
        es = expected_shortfall(normal_sample, 0.05, method=method)  # type: ignore[arg-type]
        assert es >= var


def test_es_methode_invalide() -> None:
    """(b) Le paramètre de méthode est fermé."""
    with pytest.raises(ConfigError):
        expected_shortfall(LADDER, 0.05, method="evt")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Autocorrélation et facteur de Lo
# --------------------------------------------------------------------------- #


def test_autocorrelation_contre_statsmodels(normal_sample: np.ndarray) -> None:
    """(d) Implémentation indépendante : ``statsmodels.tsa.stattools.acf`` non ajusté."""
    attendu = acf(normal_sample, nlags=6, adjusted=False, fft=False)[1:]
    obtenu = sample_autocorrelation(normal_sample, 6)
    assert obtenu == pytest.approx(np.asarray(attendu), rel=1e-12, abs=1e-14)


def test_autocorrelation_serie_constante() -> None:
    """(b) Sans variance, l'autocorrélation n'est pas définie."""
    with pytest.raises(DataQualityError):
        sample_autocorrelation([0.01] * 20, 3)


def test_autocorrelation_retards_invalides() -> None:
    """(b) Le retard 0 n'est pas une autocorrélation : c'est la variance, toujours 1."""
    with pytest.raises(ConfigError):
        sample_autocorrelation(LADDER, 0)


def test_lo_factor_vaut_exactement_racine_de_n_sans_autocorrelation() -> None:
    """(b) Forme fermée : avec tous les rho nuls, la somme disparaît et il reste sqrt(N).

    Testé exactement, sans tolérance de simulation, pour 252, 52, 12 et 4 périodes.
    """
    for n_periods in (252.0, 52.0, 12.0, 4.0):
        rho_nuls = np.zeros(int(n_periods) - 1)
        assert lo_annualization_factor(rho_nuls, n_periods) == pytest.approx(math.sqrt(n_periods), rel=1e-15)
        assert lo_annualization_factor([], n_periods) == pytest.approx(math.sqrt(n_periods), rel=1e-15)


def test_lo_factor_cas_a_la_main() -> None:
    """(a) Avec N = 2 et rho_1 = 0,5 : 2 + 2 x (2-1) x 0,5 = 3, racine = 1,7320508076.

    Avec N = 3, rho = (0,2 ; 0,1) : 3 + 2 x (2 x 0,2 + 1 x 0,1) = 3 + 1,0 = 4, racine = 2.
    """
    assert lo_annualization_factor([0.5], 2.0) == pytest.approx(math.sqrt(3.0), rel=1e-15)
    assert lo_annualization_factor([0.2, 0.1], 3.0) == pytest.approx(2.0, rel=1e-15)


def test_lo_factor_refuse_une_variance_negative() -> None:
    """(a) Avec N = 3 et rho = (-0,9 ; -0,9) : 3 + 2 x (2 x (-0,9) + (-0,9)) = 3 - 5,4 = -2,4.

    La racine n'existe pas, donc la fonction lève au lieu de rendre un NaN.
    """
    with pytest.raises(DataQualityError):
        lo_annualization_factor([-0.9, -0.9], 3.0)


def test_lo_factor_refuse_trop_de_retards() -> None:
    """(b) La formule de Lo ne définit que les retards 1 à N-1."""
    with pytest.raises(ConfigError):
        lo_annualization_factor([0.1, 0.1, 0.1], 3.0)


def test_annualization_bias_vaut_un_sur_serie_independante(normal_sample: np.ndarray) -> None:
    """(b) et tolérance dérivée : sur des rendements indépendants, le rapport vaut 1.

    Tolérance déclarée, calculée et non copiée. Sous indépendance, chaque rho_k a un
    écart type d'environ 1/racine(n). Le facteur de variance vaut N + 2 * somme des
    (N-k) rho_k, donc son écart type vaut 2 * racine(somme des (N-k)^2 / n).
    Avec N = 252, cinq retards et n = 20 000, la somme des (N-k)^2 vaut
    251^2 + 250^2 + 249^2 + 248^2 + 247^2 = 310 015. Divisée par 20 000 elle donne
    15,50, dont la racine vaut 3,937, et le double 7,874 sur une base de 252.
    Soit 3,1 % sur la variance, donc environ 1,56 % sur le rapport qui en est la
    racine. Trois écarts types font 4,7 %, d'où la tolérance retenue de 5 %.
    """
    ratio = annualization_bias(normal_sample, Frequency.DAILY, max_lags=5)
    assert ratio == pytest.approx(1.0, abs=0.05)


def test_annualization_bias_retrouve_la_valeur_theorique_d_un_ar1() -> None:
    """(a) La valeur attendue est calculée à la main depuis le coefficient du processus.

    Un AR(1) de coefficient 0,30 a pour autocorrélation theorique rho_k = 0,30^k.
    L'équation (7) de Lo donne alors, avec N = 252 et cinq retards :
    2 x (251 x 0,3 + 250 x 0,09 + 249 x 0,027 + 248 x 0,0081 + 247 x 0,00243)
    = 2 x (75,300 + 22,500 + 6,723 + 2,0088 + 0,60021) = 214,264.
    Le facteur de variance vaut 252 + 214,264 = 466,264 et le rapport
    racine(466,264 / 252) = 1,360240.

    Tolérance dérivée, non copiée : l'écart type d'un rho estimé sur 20 000 points
    vaut environ 1 / racine(20 000) = 0,0071. Les cinq rho sont fortement corrélés
    entre eux, donc leurs erreurs s'additionnent au pire. Cela donne
    2 x (251 + 250 + 249 + 248 + 247) x 0,0071 = 17,7 sur un facteur de 466.
    Soit 3,8 % sur la variance et 1,9 % sur le rapport. Trois pour cent est retenu.
    """
    phi = 0.30
    n_periods = 252.0
    attendu = math.sqrt((n_periods + 2.0 * sum((n_periods - k) * phi**k for k in range(1, 6))) / n_periods)
    assert attendu == pytest.approx(1.360240, rel=1e-6)
    rng = make_generator(20260902)
    n = 20_000
    bruit = rng.normal(0.0, 0.01, size=n)
    serie = np.empty(n)
    serie[0] = bruit[0]
    for t in range(1, n):
        serie[t] = phi * serie[t - 1] + bruit[t]
    assert annualization_bias(serie, Frequency.DAILY, max_lags=5) == pytest.approx(attendu, rel=0.03)


def test_annualization_bias_retards_par_defaut_suivent_newey_west() -> None:
    """(a) Le nombre de retards par défaut est calculé à la main, puis imposé.

    La règle de Newey et West (1994) est m = partie entière de 4 (n/100)^(2/9).
    Sur 20 000 observations : (200)^(2/9) = exp(0,22222 x 5,29832) = 3,2461,
    fois 4 = 12,984, partie entière 12. Le test impose ce 12 et exige l'égalité
    EXACTE avec l'appel par défaut. Un nombre de retards différent, 4 par exemple,
    doit donner un chiffre différent, sans quoi le test ne verrouillerait rien.
    """
    rng = make_generator(4242)
    serie = rng.normal(0.0004, 0.011, size=20_000)
    assert annualization_bias(serie, Frequency.DAILY) == annualization_bias(
        serie, Frequency.DAILY, max_lags=12
    )
    assert annualization_bias(serie, Frequency.DAILY, max_lags=4) != pytest.approx(
        annualization_bias(serie, Frequency.DAILY), rel=1e-6
    )


def test_annualization_bias_retards_bornes_par_le_quart_de_l_echantillon() -> None:
    """(a) Le tout est calculé à la main, retards compris, sur sept points.

    Série de sept rendements en rampe, de 0,1 % à 0,7 % par pas de 0,1 %. Les écarts
    à la moyenne valent -3, -2, -1, 0, 1, 2, 3 millièmes de pour cent, leur somme
    des carrés 28. Le produit croisé au retard 1 vaut 6 + 2 + 0 + 0 + 2 + 6 = 16,
    donc rho_1 = 16 / 28 = 4/7.

    La règle de Newey et West donnerait ici 4 x (0,07)^(2/9) = 2,28, soit 2 retards,
    mais le quart de l'échantillon n'en autorise qu'un. Avec un seul retard, le
    facteur de Lo vaut racine(252 + 2 x 251 x 4/7) = racine(538,857) = 23,2133 et
    le rapport 23,2133 / racine(252) = 1,462300. Le test l'exige, et exige en
    outre que deux retards donnent un chiffre différent.
    """
    rampe = np.arange(1, 8, dtype=float) / 1000.0
    rho_1 = 4.0 / 7.0
    attendu = math.sqrt((252.0 + 2.0 * 251.0 * rho_1) / 252.0)
    assert attendu == pytest.approx(1.462300, rel=1e-6)
    assert sample_autocorrelation(rampe, 1)[0] == pytest.approx(rho_1, rel=1e-14)
    assert annualization_bias(rampe, Frequency.DAILY) == pytest.approx(attendu, rel=1e-12)
    assert annualization_bias(rampe, Frequency.DAILY, max_lags=2) != pytest.approx(attendu, rel=1e-3)


def test_annualization_bias_garde_au_moins_un_retard() -> None:
    """(a) Sur trois points, la règle automatique tomberait à zéro retard, et le plancher tient.

    Sur 0,1 %, 0,2 %, 0,3 %, le quart de l'échantillon vaut 0, donc sans plancher le
    calcul demanderait zéro autocorrélation et lèverait. Avec le plancher d'un
    retard, les écarts à la moyenne valent -1, 0, +1 millième, le produit croisé au
    retard 1 vaut 0 x (-1) + 1 x 0 = 0, donc rho_1 = 0 exactement. Le facteur de Lo
    vaut alors racine de 252 et le rapport 1 exactement.
    """
    rampe = np.array([0.001, 0.002, 0.003])
    assert sample_autocorrelation(rampe, 1)[0] == 0.0
    assert annualization_bias(rampe, Frequency.DAILY) == pytest.approx(1.0, rel=1e-15)


def test_annualization_bias_serie_annuelle_vaut_un() -> None:
    """(b) Une série déjà annuelle n'est pas annualisée : le rapport vaut 1 exactement."""
    rng = make_generator(3)
    assert annualization_bias(rng.normal(0.05, 0.15, size=40), Frequency.ANNUAL) == 1.0


def test_annualization_bias_retards_invalides() -> None:
    """(b) Un nombre de retards nul ou négatif n'a pas de sens."""
    rng = make_generator(4)
    with pytest.raises(ConfigError):
        annualization_bias(rng.normal(0.0, 0.01, size=100), Frequency.DAILY, max_lags=0)


# --------------------------------------------------------------------------- #
# Rapport de queue, taux de réussite, gain sur peine
# --------------------------------------------------------------------------- #


def test_tail_ratio_a_la_main() -> None:
    """(a) Sur l'échelle de vingt valeurs, quantile à 95 % : position 19 x 0,95 = 18,05,
    entre x[18] = 0,08 et x[19] = 0,09, soit 0,08 + 0,05 x 0,01 = 0,0805.

    Le quantile à 5 % vaut -0,0905 (déjà calculé). Le rapport vaut donc
    0,0805 / 0,0905 = 0,88950276.
    """
    assert tail_ratio(LADDER) == pytest.approx(0.0805 / 0.0905, rel=1e-12)


def test_tail_ratio_vaut_un_sur_serie_symetrique() -> None:
    """(b) Une série symétrique autour de zéro a deux queues de même taille."""
    symetrique = np.array([-0.05, -0.02, -0.01, 0.0, 0.01, 0.02, 0.05])
    assert tail_ratio(symetrique) == pytest.approx(1.0, rel=1e-14)


def test_tail_ratio_quantile_nul() -> None:
    """(b) Un quantile inférieur nul rend le rapport indéfini, donc la fonction lève."""
    with pytest.raises(DataQualityError):
        tail_ratio(np.array([0.0, 0.0, 0.0, 0.01, 0.02]))


def test_tail_ratio_bornes_incoherentes() -> None:
    """(b) Le quantile inférieur doit être sous le supérieur."""
    with pytest.raises(ConfigError):
        tail_ratio(LADDER, upper=0.05, lower=0.95)


def test_hit_rate_a_la_main() -> None:
    """(a) Sur dix rendements dont six strictement positifs, le taux vaut 6 / 10 = 0,6."""
    r = [0.01, 0.02, -0.01, 0.03, -0.02, 0.01, 0.04, -0.05, 0.02, -0.01]
    assert hit_rate(r) == pytest.approx(0.6, rel=1e-15)


def test_hit_rate_egalite_stricte() -> None:
    """(b) Convention déclarée : un rendement égal au seuil ne compte pas.

    Sur quatre valeurs dont deux nulles et deux positives, le taux vaut 2 / 4 = 0,5.
    """
    assert hit_rate([0.0, 0.0, 0.01, 0.02]) == pytest.approx(0.5, rel=1e-15)


def test_hit_rate_seuil_non_nul_a_la_main() -> None:
    """(a) Seuil à 1 % sur +0,5 %, +1 %, +1,5 %, +2 % : deux valeurs le dépassent, donc 0,5."""
    assert hit_rate([0.005, 0.01, 0.015, 0.02], 0.01) == pytest.approx(0.5, rel=1e-15)


def test_gain_to_pain_a_la_main() -> None:
    """(a) Sur +3 %, -1 %, +2 %, -1 % : somme = 0,03, peine = 0,02, rapport = 1,5."""
    assert gain_to_pain([0.03, -0.01, 0.02, -0.01]) == pytest.approx(1.5, rel=1e-12)


def test_gain_to_pain_sans_perte() -> None:
    """(b) Sans aucun rendement négatif, le dénominateur est nul et le rapport indéfini."""
    with pytest.raises(InsufficientDataError):
        gain_to_pain([0.01, 0.02, 0.03])


def test_series_vides_partout() -> None:
    """(b) Aucune de ces mesures n'est définie sur une série sans observation."""
    for fonction in (downside_deviation, upside_deviation, hit_rate, gain_to_pain, tail_ratio):
        with pytest.raises(InsufficientDataError):
            fonction([])
    with pytest.raises(InsufficientDataError):
        value_at_risk([])


# --------------------------------------------------------------------------- #
# Propriétés (hypothesis)
# --------------------------------------------------------------------------- #

FINITE_RETURNS = st.lists(
    st.floats(min_value=-0.9, max_value=0.9, allow_nan=False, allow_infinity=False),
    min_size=5,
    max_size=200,
)
POSITIVE_SCALE = st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False)


@given(returns=FINITE_RETURNS, scale=POSITIVE_SCALE)
@settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_propriete_volatilite_homogene_degre_un(returns: list[float], scale: float) -> None:
    """(b) Invariance d'échelle : vol(c r) = c vol(r) pour tout c > 0."""
    r = np.asarray(returns, dtype=float)
    assert volatility(scale * r, annualize=False) == pytest.approx(
        scale * volatility(r, annualize=False), rel=1e-9, abs=1e-15
    )


@given(returns=FINITE_RETURNS, scale=POSITIVE_SCALE)
@settings(max_examples=200)
def test_propriete_var_historique_homogene(returns: list[float], scale: float) -> None:
    """(b) Invariance d'échelle de la valeur à risque historique : VaR(c r) = c VaR(r)."""
    r = np.asarray(returns, dtype=float)
    assert value_at_risk(scale * r, 0.05) == pytest.approx(
        scale * value_at_risk(r, 0.05), rel=1e-9, abs=1e-15
    )


@given(
    returns=FINITE_RETURNS,
    alpha=st.floats(min_value=0.01, max_value=0.40, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=300)
def test_propriete_es_superieure_ou_egale_a_var(returns: list[float], alpha: float) -> None:
    """(b) Inégalité toujours vraie : la moyenne d'une queue dépasse le seuil de cette queue.

    Vérifiée pour la version historique et la version gaussienne. La tolérance
    absolue de 1e-12 absorbe l'arrondi des flottants, sans quoi l'égalité stricte du
    cas dégénéré (série constante) échouerait pour des raisons de représentation.
    """
    r = np.asarray(returns, dtype=float)
    for method in ("historical", "gaussian"):
        var = value_at_risk(r, alpha, method=method)  # type: ignore[arg-type]
        es = expected_shortfall(r, alpha, method=method)  # type: ignore[arg-type]
        assert es >= var - 1e-12


@given(returns=FINITE_RETURNS)
@settings(max_examples=200)
def test_propriete_identite_des_semi_variances(returns: list[float]) -> None:
    """(b) Identité algébrique : min(x,0)^2 + max(x,0)^2 = x^2, sommée sur l'échantillon."""
    r = np.asarray(returns, dtype=float)
    bas = downside_deviation(r, annualize=False) ** 2
    haut = upside_deviation(r, annualize=False) ** 2
    assert bas + haut == pytest.approx(float(np.mean(r**2)), rel=1e-9, abs=1e-15)


@given(returns=FINITE_RETURNS)
@settings(max_examples=200)
def test_propriete_deviation_baisse_bornee_par_ecart_type(returns: list[float]) -> None:
    """(b) Borne : au seuil égal à la moyenne, la semi-variance ne dépasse pas la variance.

    La somme des carrés des seuls écarts défavorables ne peut pas dépasser celle de
    tous les écarts, et les deux partagent le même dénominateur en convention
    « total ». La variance de comparaison est donc prise à ddof = 0.
    """
    r = np.asarray(returns, dtype=float)
    moyenne = float(np.mean(r))
    bas = downside_deviation(r, moyenne, annualize=False) ** 2
    variance = float(np.mean((r - moyenne) ** 2))
    assert bas <= variance + 1e-15

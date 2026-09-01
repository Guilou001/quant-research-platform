"""Tests du module des corrections pour tests multiples.

Aucune valeur attendue de ce fichier ne vient de la sortie du code testé.
Chaque assertion cite sa source : ``statsmodels`` comme implémentation
indépendante, une valeur publiée par Harvey, Liu et Zhu (2016), une identité
mathématique, ou un calcul à la main écrit en commentaire.
"""

from __future__ import annotations

import itertools
import math

import numpy as np
import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from scipy import stats
from statsmodels.stats.multitest import multipletests

from quantlab.core.determinism import child_generators, make_generator
from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.types import Frequency
from quantlab.validation.multiple_testing import (
    HLZ_2012_FACTOR_COUNT,
    HLZ_2012_THRESHOLDS,
    TrialCounter,
    _politis_romano_variance,
    adjust_pvalues,
    benjamini_hochberg,
    benjamini_yekutieli,
    benjamini_yekutieli_constant,
    bonferroni,
    haircut_sharpe,
    hansen_spa,
    holm,
    required_tstat,
    whites_reality_check,
)

# Graine unique de ce fichier. Toute graine dérivée passe par
# ``child_generators``, jamais par « graine + i ».
GRAINE = 20260901

# Graine distincte, et non une graine dérivée par addition : la règle 14 du
# CLAUDE.md l'interdit. Celle-ci sert au test du ballast, qui exige le MÊME flux
# de tirages sur quatre appels, donc un générateur reconstruit quatre fois
# depuis la même valeur.
GRAINE_BALLAST = 20260902

#: Correspondance entre les procédures du module et les noms de statsmodels.
PROCEDURES = {
    "bonferroni": (bonferroni, "bonferroni"),
    "holm": (holm, "holm"),
    "benjamini_hochberg": (benjamini_hochberg, "fdr_bh"),
    "benjamini_yekutieli": (benjamini_yekutieli, "fdr_by"),
}


def _reference_long_run_variance(x: np.ndarray, q: float) -> float:
    r"""Recopie la variance de long terme de Hansen (2005), en boucles explicites.

    Cette fonction est un DOUBLE DE TEST, écrit depuis l'article et non depuis le
    code testé. Le module calcule les autocovariances par transformée de Fourier
    et les pondère par tableaux ; cette transcription les calcule terme à terme.
    Deux chemins de calcul indépendants pour une même formule.

    La formule, telle que Hansen (2005) l'écrit en section 3 :

    .. math::

        \hat{\omega}^2 = \hat{\gamma}_0
        + 2 \sum_{i=1}^{n-1} \kappa(n,i)\, \hat{\gamma}_i,
        \qquad
        \kappa(n,i) = \frac{n-i}{n}(1-q)^i + \frac{i}{n}(1-q)^{n-i}

    .. math::

        \hat{\gamma}_i = \frac{1}{n} \sum_{j=1}^{n-i}
        (x_j - \bar{x})(x_{j+i} - \bar{x})

    Args:
        x: la série, de longueur ``n``.
        q: la probabilité de redémarrer un bloc.

    Returns:
        La variance de long terme, sans plancher.
    """
    n = x.size
    moyenne = float(x.mean())
    gamma = [sum((x[j] - moyenne) * (x[j + i] - moyenne) for j in range(n - i)) / n for i in range(n)]
    total = gamma[0]
    for i in range(1, n):
        noyau = (n - i) / n * (1.0 - q) ** i + i / n * (1.0 - q) ** (n - i)
        total += 2.0 * noyau * gamma[i]
    return float(total)


def _serie_ar1(phi: float, sigma: float, n: int, generateur: np.random.Generator) -> np.ndarray:
    """Tire une série autorégressive d'ordre un, rodée sur 200 périodes jetées."""
    rodage = 200
    bruit = generateur.normal(0.0, sigma, size=n + rodage)
    x = np.empty(n + rodage)
    x[0] = bruit[0]
    for t in range(1, n + rodage):
        x[t] = phi * x[t - 1] + bruit[t]
    return x[rodage:]


def _reference_stationary_bootstrap(
    n_observations: int,
    *,
    n_resamples: int,
    block_size: float,
    generator: np.random.Generator,
) -> np.ndarray:
    """Tire des indices par le bootstrap stationnaire de Politis et Romano (1994).

    Cette fonction est un DOUBLE DE TEST. Elle recopie la récurrence telle que
    Hansen (2005) l'écrit en section 3, et sert tant que
    ``quantlab.validation.bootstrap`` n'est pas dans l'arbre. Le module de
    production, lui, délègue au paquet du laboratoire.

    La récurrence de Hansen : le premier indice est tiré uniformément, puis avec
    probabilité ``q`` l'indice suivant est tiré uniformément, sinon il suit le
    précédent, en revenant au début après la dernière observation.

    Args:
        n_observations: la longueur de la série d'origine.
        n_resamples: le nombre de rééchantillons.
        block_size: la longueur moyenne des blocs, dont l'inverse donne ``q``.
        generator: le générateur aléatoire.

    Returns:
        La matrice d'indices, de forme ``(n_resamples, n_observations)``.
    """
    q = 1.0 / block_size
    departs = generator.integers(0, n_observations, size=(n_resamples, n_observations))
    redemarre = generator.random((n_resamples, n_observations)) < q
    redemarre[:, 0] = True
    positions = np.arange(n_observations)
    dernier = np.maximum.accumulate(np.where(redemarre, positions, -1), axis=1)
    base = np.take_along_axis(departs, dernier, axis=1)
    return (base + (positions - dernier)) % n_observations


def _cadre(matrice: np.ndarray, prefixe: str = "s") -> pd.DataFrame:
    """Met une matrice de rendements en tableau indexé par des dates ouvrables."""
    index = pd.date_range("2000-01-03", periods=matrice.shape[0], freq="B")
    colonnes = [f"{prefixe}{k}" for k in range(matrice.shape[1])]
    return pd.DataFrame(matrice, index=index, columns=colonnes)


# --------------------------------------------------------------------------
# Les quatre procédures, contre statsmodels
# --------------------------------------------------------------------------


@pytest.mark.parametrize("nom", sorted(PROCEDURES))
def test_les_quatre_procedures_retrouvent_statsmodels(nom: str) -> None:
    """Chaque procédure redonne ``multipletests`` à 1e-12 sur le même vecteur.

    Source de la valeur attendue : ``statsmodels.stats.multitest.multipletests``,
    implémentation indépendante et éprouvée. C'est le contrôle qui valide la
    transcription des formules de Harvey, Liu et Zhu (2016).
    """
    generateur = make_generator(GRAINE)
    # Un mélange de valeurs p très petites, moyennes et grandes, plus des
    # doublons exacts, qui sont le cas où un tri instable ferait diverger.
    valeurs = np.concatenate(
        [
            generateur.uniform(0.0, 1.0, size=40),
            np.array([0.0, 1.0, 0.05, 0.05, 0.05, 1e-12, 0.999999]),
        ]
    )
    alpha = 0.05
    fonction, methode_sm = PROCEDURES[nom]

    obtenu = fonction(valeurs, alpha)
    rejets_sm, p_ajustees_sm, _, _ = multipletests(valeurs, alpha=alpha, method=methode_sm)

    np.testing.assert_allclose(obtenu.adjusted_pvalues, p_ajustees_sm, rtol=1e-12, atol=1e-12)
    np.testing.assert_array_equal(obtenu.rejected, rejets_sm)
    assert obtenu.n_tests == valeurs.size


@pytest.mark.parametrize("nom", sorted(PROCEDURES))
def test_les_quatre_procedures_sur_un_vecteur_de_dix(nom: str) -> None:
    """Le contrôle tient aussi sur le petit vecteur de l'exemple de l'article.

    Les dix valeurs p sont celles du tableau 4 de Harvey, Liu et Zhu (2016),
    section 4.4, exprimées en fraction. Statut RAPPORTÉ, lues dans la version
    NBER w20592. La valeur attendue reste celle de ``statsmodels``.
    """
    valeurs = np.array([0.0000, 0.0000, 0.0005, 0.0060, 0.0084, 0.0085, 0.0128, 0.0271, 0.0300, 0.0466])
    fonction, methode_sm = PROCEDURES[nom]
    obtenu = fonction(valeurs, 0.05)
    rejets_sm, p_ajustees_sm, _, _ = multipletests(valeurs, alpha=0.05, method=methode_sm)
    np.testing.assert_allclose(obtenu.adjusted_pvalues, p_ajustees_sm, rtol=1e-12, atol=1e-12)
    np.testing.assert_array_equal(obtenu.rejected, rejets_sm)


def test_l_exemple_publie_donne_trois_quatre_et_six_decouvertes() -> None:
    """Les comptes de découvertes de l'exemple de l'article sont retrouvés.

    Valeurs attendues RAPPORTÉES, exemples 4.4.1 à 4.4.3 de Harvey, Liu et Zhu
    (2016) : Bonferroni retient trois facteurs, Holm quatre, et la variante sous
    dépendance arbitraire six. Les seuils sont ceux de l'article, 5 % pour les
    deux premières et 5 % pour la troisième.
    """
    valeurs = np.array([0.0000, 0.0000, 0.0005, 0.0060, 0.0084, 0.0085, 0.0128, 0.0271, 0.0300, 0.0466])
    assert bonferroni(valeurs, 0.05).n_rejected == 3
    assert holm(valeurs, 0.05).n_rejected == 4
    assert benjamini_yekutieli(valeurs, 0.05).n_rejected == 6


def test_les_seuils_effectifs_sont_ceux_imprimes_par_l_article() -> None:
    """Les trois seuils effectifs de l'exemple publié sont retrouvés.

    Valeurs attendues RAPPORTÉES, légende du tableau 4 de Harvey, Liu et Zhu
    (2016), version NBER w20592 : « The threshold t-ratio for Bonferroni is
    0.05%, for Holm 0.60% and for BHY 0.85% ». Ces trois nombres sont des seuils
    sur les valeurs p BRUTES, et non sur les valeurs p ajustées. Ce sont donc
    exactement ce que rend ``effective_threshold``.

    L'article étiquette ces seuils « t-ratio » dans sa légende alors qu'ils sont
    en pourcentage de valeur p, ce que ses propres tableaux confirment.
    """
    valeurs = np.array([0.0000, 0.0000, 0.0005, 0.0060, 0.0084, 0.0085, 0.0128, 0.0271, 0.0300, 0.0466])
    assert bonferroni(valeurs, 0.05).effective_threshold == pytest.approx(0.0005, rel=1e-12)
    assert holm(valeurs, 0.05).effective_threshold == pytest.approx(0.0060, rel=1e-12)
    assert benjamini_yekutieli(valeurs, 0.05).effective_threshold == pytest.approx(0.0085, rel=1e-12)


def test_bonferroni_rejette_alpha_fois_sous_l_hypothese_nulle() -> None:
    """Sous l'hypothèse nulle, Bonferroni rejette en moyenne alpha fois par famille.

    Valeur attendue par identité, pas par exécution. Sous l'hypothèse nulle une
    valeur p est uniforme sur l'intervalle unité. Bonferroni rejette au seuil
    alpha sur M, donc le nombre de rejets d'une famille de M tests suit une loi
    binomiale de paramètres M et alpha sur M. Son espérance vaut exactement
    alpha, quel que soit M.

    Sur R familles indépendantes, le total suit une binomiale de paramètres
    R fois M et alpha sur M. Avec R = 400, M = 1000 et alpha = 0,05 :
    espérance 400 x 0,05 = 20, variance 20 x (1 - 0,00005) = 19,999, donc
    écart type 4,472. La tolérance retenue est de quatre écarts types, soit
    l'intervalle [2,1 ; 37,9], que le vrai total quitte avec une probabilité
    inférieure à 1 sur 10 000.
    """
    n_familles, n_tests, alpha = 400, 1000, 0.05
    generateurs = child_generators(GRAINE, n_familles)
    total = sum(bonferroni(g.uniform(0.0, 1.0, size=n_tests), alpha).n_rejected for g in generateurs)

    espérance = n_familles * alpha
    ecart_type = math.sqrt(n_familles * n_tests * (alpha / n_tests) * (1 - alpha / n_tests))
    assert abs(total - espérance) <= 4.0 * ecart_type, (
        f"{total} rejets, attendu {espérance} plus ou moins {4.0 * ecart_type:.1f}"
    )


def test_le_facteur_de_dependance_est_le_nombre_harmonique() -> None:
    """Le facteur c(M) vaut la somme des inverses des entiers.

    Valeurs attendues par calcul à la main. Pour M = 1, la somme vaut 1. Pour
    M = 4, elle vaut 1 + 0,5 + 1/3 + 0,25 = 25/12 = 2,0833333. Pour M = 10, la
    somme des dix premiers inverses vaut 7381/2520 = 2,9289683.
    """
    assert benjamini_yekutieli_constant(1) == pytest.approx(1.0, rel=1e-15)
    assert benjamini_yekutieli_constant(4) == pytest.approx(25.0 / 12.0, rel=1e-15)
    assert benjamini_yekutieli_constant(10) == pytest.approx(7381.0 / 2520.0, rel=1e-15)


def test_le_seuil_effectif_est_la_plus_grande_valeur_p_retenue() -> None:
    """Le seuil effectif encadre exactement ce que la procédure a retenu.

    Propriété de définition : toute valeur p rejetée est inférieure ou égale au
    seuil effectif, et aucune valeur p conservée ne lui est inférieure.
    """
    valeurs = np.array([0.001, 0.004, 0.02, 0.2, 0.5])
    resultat = benjamini_hochberg(valeurs, 0.05)
    assert resultat.n_rejected >= 1
    assert valeurs[resultat.rejected].max() == pytest.approx(resultat.effective_threshold)
    assert valeurs[~resultat.rejected].min() > resultat.effective_threshold


def test_sans_aucun_rejet_le_seuil_effectif_est_celui_du_premier_rang() -> None:
    """Sans rejet, le seuil rendu est celui qu'aurait dû franchir le meilleur essai.

    Valeur attendue par identité : le seuil de Bonferroni au premier rang vaut
    alpha sur M, soit 0,05 / 4 = 0,0125.
    """
    resultat = bonferroni(np.array([0.4, 0.5, 0.6, 0.7]), 0.05)
    assert resultat.n_rejected == 0
    assert resultat.effective_threshold == pytest.approx(0.0125, rel=1e-15)


# --------------------------------------------------------------------------
# Propriétés, par hypothesis
# --------------------------------------------------------------------------


@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    st.lists(
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=40,
    )
)
def test_ordre_des_quatre_procedures(valeurs: list[float]) -> None:
    """Les quatre procédures s'ordonnent, et l'ordre se démontre.

    Trois inégalités, toutes établies à la main sur les formules.

    Bonferroni domine Holm parce que M est supérieur ou égal à M - j + 1 pour
    tout rang j.

    Holm domine Benjamini-Hochberg parce que (M - j + 1) x j - M vaut
    (j - 1)(M - j), qui est positif ou nul sur tout rang. Donc M / j est
    inférieur ou égal à M - j + 1 rang par rang.

    Benjamini-Yekutieli domine Benjamini-Hochberg parce que c(M) est supérieur
    ou égal à 1.

    Enfin toute valeur p ajustée est comprise entre la valeur p brute et 1.
    """
    p = np.asarray(valeurs, dtype=float)
    alpha = 0.05
    p_bonf = bonferroni(p, alpha).adjusted_pvalues
    p_holm = holm(p, alpha).adjusted_pvalues
    p_bh = benjamini_hochberg(p, alpha).adjusted_pvalues
    p_by = benjamini_yekutieli(p, alpha).adjusted_pvalues

    tolerance = 1e-12
    assert np.all(p_bonf >= p_holm - tolerance)
    assert np.all(p_holm >= p_bh - tolerance)
    assert np.all(p_by >= p_bh - tolerance)
    for ajustee in (p_bonf, p_holm, p_bh, p_by):
        assert np.all(ajustee >= p - tolerance)
        assert np.all(ajustee <= 1.0 + tolerance)


@settings(max_examples=100, deadline=None)
@given(
    st.lists(
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=30,
    )
)
def test_holm_rejette_tout_ce_que_rejette_bonferroni(valeurs: list[float]) -> None:
    """Holm domine uniformément Bonferroni en nombre de découvertes.

    Propriété démontrée par Harvey, Liu et Zhu (2016), section 4.4.2 : tout test
    rejeté sous Bonferroni l'est sous Holm, jamais l'inverse.
    """
    p = np.asarray(valeurs, dtype=float)
    rejets_bonf = bonferroni(p, 0.05).rejected
    rejets_holm = holm(p, 0.05).rejected
    assert np.all(rejets_holm | ~rejets_bonf)


# --------------------------------------------------------------------------
# Le seuil de t exigé
# --------------------------------------------------------------------------


def test_le_seuil_de_t_a_un_seul_essai_est_le_seuil_usuel() -> None:
    """Sans essai concurrent, le seuil retombe sur 1,959964.

    Valeur attendue par forme fermée : le quantile à 97,5 % de la loi normale
    centrée réduite vaut 1,9599639845, nombre tabulé de longue date.
    """
    assert required_tstat(1, 0.05) == pytest.approx(1.9599639845400545, rel=1e-12)


def test_le_seuil_de_t_retrouve_la_valeur_publiee_de_bonferroni() -> None:
    """À 316 facteurs et 5 %, Bonferroni exige 3,78, comme l'article le publie.

    Valeur attendue RAPPORTÉE : Harvey, Liu et Zhu (2016), section 4.6, écrivent
    que le seuil de Bonferroni passe de 1,96 à 3,78 en 2012, avec 316 facteurs
    recensés. La valeur p correspondante qu'ils annoncent, 0,02 %, est retrouvée
    elle aussi.
    """
    seuil = required_tstat(HLZ_2012_FACTOR_COUNT, 0.05, method="bonferroni")
    assert seuil == pytest.approx(HLZ_2012_THRESHOLDS["bonferroni"], abs=0.005)
    valeur_p = 2.0 * stats.norm.sf(HLZ_2012_THRESHOLDS["bonferroni"])
    assert valeur_p == pytest.approx(0.0002, abs=0.00005)


def test_le_seuil_de_t_croit_avec_le_nombre_d_essais() -> None:
    """Plus d'essais exige un t plus grand, pour les quatre procédures.

    Propriété de monotonie : le seuil de valeur p décroît en 1 sur M, donc le
    quantile normal correspondant croît. Le contrôle porte sur une suite
    strictement croissante d'effectifs d'essais.
    """
    effectifs = [1, 2, 5, 10, 50, 100, 316, 1000, 5000]
    for methode in ("bonferroni", "holm", "benjamini_hochberg", "benjamini_yekutieli"):
        seuils = [required_tstat(m, 0.05, method=methode) for m in effectifs]
        assert all(a < b for a, b in itertools.pairwise(seuils)), f"{methode} n'est pas croissant : {seuils}"


def test_benjamini_yekutieli_exige_plus_que_les_trois_autres() -> None:
    """Le facteur de dépendance arbitraire durcit le seuil, et les trois autres coïncident.

    Propriété par identité. Au premier rang, le seuil de Holm vaut
    alpha / (M + 1 - 1), celui de Benjamini-Hochberg vaut 1 x alpha / M, et
    celui de Bonferroni vaut alpha / M. Les trois sont le même nombre. Seul
    Benjamini-Yekutieli divise en plus par c(M), qui dépasse 1 dès M = 2.
    """
    for n_tests in (2, 10, 316):
        seuils = {
            m: required_tstat(n_tests, 0.05, method=m)
            for m in ("bonferroni", "holm", "benjamini_hochberg", "benjamini_yekutieli")
        }
        assert seuils["bonferroni"] == pytest.approx(seuils["holm"], rel=1e-15)
        assert seuils["bonferroni"] == pytest.approx(seuils["benjamini_hochberg"], rel=1e-15)
        assert seuils["benjamini_yekutieli"] > seuils["bonferroni"]


def test_le_seuil_de_t_refuse_les_arguments_hors_domaine() -> None:
    """Un effectif nul, un alpha hors bornes ou une procédure inconnue lèvent."""
    with pytest.raises(ConfigError):
        required_tstat(0, 0.05)
    with pytest.raises(ConfigError):
        required_tstat(10, 0.0)
    with pytest.raises(ConfigError):
        required_tstat(10, 1.0)
    with pytest.raises(ConfigError):
        required_tstat(10, 0.05, method="tukey")


# --------------------------------------------------------------------------
# Le rabais de ratio de Sharpe
# --------------------------------------------------------------------------


def test_le_rabais_suit_le_calcul_a_la_main() -> None:
    """Le rabais d'un Sharpe de 1,0 sur dix ans mensuels après dix essais est vérifié pas à pas.

    Calcul à la main, chaîne complète, avec les quantiles de la loi normale
    centrée réduite.

    Ratio de Sharpe périodique : 1,0 / racine de 12 = 0,28867513.
    Statistique t : 0,28867513 x racine de 120 = 3,16227766, qui est exactement
    la racine de 10, puisque le t vaut le ratio annualisé multiplié par la
    racine du nombre d'ANNÉES.
    Valeur p bilatérale : 2 x (1 - Phi(3,1622776602)) = 0,0015654022580.
    Valeur p ajustée par Bonferroni sur dix essais : 0,0156540225800.
    Statistique t ajustée : Phi moins un de (1 - 0,0078270112900) = 2,4168835894.
    Ratio de Sharpe rabattu annualisé :
    2,4168835894 / racine de 120 x racine de 12 = 0,7642856982.
    Rabais : (1,0 - 0,7642856982) / 1,0 = 0,2357143018.
    """
    resultat = haircut_sharpe(
        1.0,
        n_tests=10,
        n_obs=120,
        frequency=Frequency.MONTHLY,
        method="bonferroni",
    )
    assert resultat.observed_tstat == pytest.approx(math.sqrt(10.0), rel=1e-12)
    assert resultat.single_pvalue == pytest.approx(0.0015654022580, rel=1e-11)
    assert resultat.adjusted_pvalue == pytest.approx(0.0156540225800, rel=1e-11)
    assert resultat.adjusted_tstat == pytest.approx(2.4168835894, rel=1e-10)
    assert resultat.haircut_sr == pytest.approx(0.7642856982, rel=1e-10)
    assert resultat.haircut_fraction == pytest.approx(0.2357143018, rel=1e-10)


def test_le_rabais_est_nul_a_un_seul_essai() -> None:
    """Un essai unique ne se rabat pas, quelle que soit la procédure.

    Propriété par identité : avec M = 1 la valeur p ajustée vaut la valeur p
    brute, et c(1) vaut 1, donc l'aller-retour est l'identité.
    """
    for methode in ("bonferroni", "holm", "benjamini_hochberg", "bhy"):
        resultat = haircut_sharpe(1.4, n_tests=1, n_obs=252 * 5, frequency=Frequency.DAILY, method=methode)
        assert resultat.haircut_fraction == pytest.approx(0.0, abs=1e-9)
        assert resultat.haircut_sr == pytest.approx(1.4, rel=1e-9)


def test_le_rabais_croit_avec_le_nombre_d_essais() -> None:
    """Plus d'essais rabat davantage, strictement.

    Propriété de monotonie : la valeur p ajustée croît en M, donc le t ajusté
    décroît, donc le ratio rabattu décroît.
    """
    rabais = [
        haircut_sharpe(
            1.0, n_tests=m, n_obs=120, frequency=Frequency.MONTHLY, method="bonferroni"
        ).haircut_fraction
        for m in (1, 2, 10, 50, 200)
    ]
    assert all(a < b for a, b in itertools.pairwise(rabais)), rabais


def test_connaitre_les_autres_essais_adoucit_benjamini_yekutieli() -> None:
    """Fournir les valeurs p des autres essais rend la correction moins dure.

    Propriété par définition. Sans le vecteur des autres essais, la valeur p
    ajustée rendue est la borne supérieure M x c(M) x p. Avec un vecteur où
    plusieurs essais sont eux aussi significatifs, la récurrence de
    Benjamini-Yekutieli prend le minimum avec les rangs suivants, donc rend au
    plus la même chose.
    """
    autres = np.full(19, 0.001)
    borne = haircut_sharpe(1.0, n_tests=20, n_obs=120, frequency=Frequency.MONTHLY, method="bhy")
    exact = haircut_sharpe(
        1.0,
        n_tests=20,
        n_obs=120,
        frequency=Frequency.MONTHLY,
        method="bhy",
        other_pvalues=autres,
    )
    assert exact.adjusted_pvalue <= borne.adjusted_pvalue
    assert exact.haircut_fraction < borne.haircut_fraction


def test_sans_les_autres_essais_holm_est_exact_et_benjamini_hochberg_est_une_borne() -> None:
    """La valeur p ajustée du meilleur essai est exacte pour Holm, majorée pour BH.

    Contre-exemple chiffré, contrôlé par ``statsmodels`` comme implémentation
    indépendante. Avec dix essais dont les deux meilleurs valent 0,004 et 0,005,
    la valeur p ajustée du premier vaut 0,04 sous Holm et 0,025 sous
    Benjamini-Hochberg. Sans le vecteur des autres essais, le rabais rend 0,04
    dans les deux cas.

    L'écart va toujours dans le même sens : la valeur rendue MAJORE la valeur
    exacte, donc le rabais annoncé est trop dur et jamais trop doux. C'est la
    seule direction acceptable pour un contrôle de fouille de données.
    """
    autres = np.array([0.005, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9])
    vecteur = np.concatenate(([0.004], autres))
    exactes = {
        nom: multipletests(vecteur, alpha=0.05, method=methode_sm)[1][0]
        for nom, (_, methode_sm) in PROCEDURES.items()
    }
    assert exactes["holm"] == pytest.approx(0.04, rel=1e-12)
    assert exactes["benjamini_hochberg"] == pytest.approx(0.025, rel=1e-12)

    # Le rabais se calcule sur une valeur p, pas sur un ratio de Sharpe donné.
    # On remonte donc au ratio qui produit exactement p = 0,004 sur 120 mois.
    tstat = float(stats.norm.isf(0.004 / 2.0))
    sharpe_annuel = tstat / math.sqrt(120.0) * math.sqrt(12.0)

    for methode in ("holm", "benjamini_hochberg"):
        borne = haircut_sharpe(
            sharpe_annuel, n_tests=10, n_obs=120, frequency=Frequency.MONTHLY, method=methode
        )
        assert borne.single_pvalue == pytest.approx(0.004, rel=1e-9)
        assert borne.adjusted_pvalue == pytest.approx(0.04, rel=1e-9)
        assert borne.adjusted_pvalue >= exactes[methode] - 1e-12

        exact = haircut_sharpe(
            sharpe_annuel,
            n_tests=10,
            n_obs=120,
            frequency=Frequency.MONTHLY,
            method=methode,
            other_pvalues=autres,
        )
        assert exact.adjusted_pvalue == pytest.approx(exactes[methode], rel=1e-9)

    # Holm coïncide, Benjamini-Hochberg non : c'est le contre-exemple.
    sans_autres = haircut_sharpe(
        sharpe_annuel, n_tests=10, n_obs=120, frequency=Frequency.MONTHLY, method="bh"
    )
    avec_autres = haircut_sharpe(
        sharpe_annuel,
        n_tests=10,
        n_obs=120,
        frequency=Frequency.MONTHLY,
        method="bh",
        other_pvalues=autres,
    )
    assert avec_autres.haircut_fraction < sans_autres.haircut_fraction


def test_le_rabais_est_invariant_a_l_echelle_d_annualisation() -> None:
    """Le rabais en pourcentage ne dépend pas de l'unité du ratio de Sharpe.

    Propriété par identité. Le rabais est un rapport de deux ratios exprimés
    dans la même unité. Le passage de l'un à l'autre multiplie les deux par la
    même racine du nombre de périodes par an.
    """
    annualise = haircut_sharpe(1.0, n_tests=25, n_obs=120, frequency=Frequency.MONTHLY)
    periodique = haircut_sharpe(
        1.0 / math.sqrt(12.0),
        n_tests=25,
        n_obs=120,
        frequency=Frequency.MONTHLY,
        annualized=False,
    )
    assert annualise.haircut_fraction == pytest.approx(periodique.haircut_fraction, rel=1e-12)
    assert annualise.haircut_sr == pytest.approx(periodique.haircut_sr * math.sqrt(12.0), rel=1e-12)


def test_le_rabais_refuse_un_sharpe_non_positif() -> None:
    """Rabattre un ratio de Sharpe négatif n'a pas de sens, et lève."""
    with pytest.raises(ConfigError):
        haircut_sharpe(-0.3, n_tests=10, n_obs=120, frequency=Frequency.MONTHLY)
    with pytest.raises(ConfigError):
        haircut_sharpe(0.0, n_tests=10, n_obs=120, frequency=Frequency.MONTHLY)


# --------------------------------------------------------------------------
# Le contrôle de réalité de White
# --------------------------------------------------------------------------


def test_white_ne_rejette_pas_quand_tout_est_du_bruit() -> None:
    """Sous bruit pur, le taux de rejet reste au niveau nominal ou en dessous.

    Valeur attendue par identité binomiale. Sous l'hypothèse nulle prise dans sa
    configuration la moins favorable, toutes les moyennes valant zéro, la valeur
    p du contrôle de réalité est asymptotiquement uniforme. Le nombre de rejets
    sur R = 40 jeux indépendants suit donc une binomiale de paramètres 40 et
    0,05 : espérance 2, écart type racine de 40 x 0,05 x 0,95 = 1,378.

    Le test est unilatéral, parce que le contrôle de réalité est CONSERVATEUR
    par construction, comme Hansen (2005) le montre. Zéro rejet est un résultat
    acceptable ; un taux très au-dessus du nominal ne l'est pas. La borne
    retenue est l'espérance plus quatre écarts types, soit 7,5, donc au plus
    sept rejets.
    """
    n_jeux, n_dates, n_strategies, n_bootstrap = 40, 250, 8, 200
    generateurs = child_generators(GRAINE, 2 * n_jeux)
    rejets = 0
    for i in range(n_jeux):
        donnees = generateurs[2 * i].normal(0.0, 0.01, size=(n_dates, n_strategies))
        cadre = _cadre(donnees)
        repere = pd.Series(0.0, index=cadre.index)
        resultat = whites_reality_check(
            cadre,
            repere,
            n_bootstrap=n_bootstrap,
            generator=generateurs[2 * i + 1],
            block_size=4.0,
        )
        rejets += int(resultat.pvalue <= 0.05)
    assert rejets <= 7, f"{rejets} rejets sur {n_jeux} jeux de bruit pur, attendu au plus 7"


def test_white_rejette_quand_une_strategie_a_un_vrai_avantage() -> None:
    """Un avantage de six erreurs types fait s'effondrer la valeur p.

    Valeur attendue par calcul à la main. La stratégie 0 a une surperformance
    moyenne de 0,003 par période et un écart type de 0,01, sur 400 périodes.
    Sa statistique t vaut donc 0,003 / 0,01 x racine de 400 = 6,0. Sous
    l'hypothèse nulle, le maximum de huit variables normales centrées réduites
    dépasse 6,0 avec une probabilité de 8 x (1 - Phi(6)) = 7,9e-9, MODÉLISÉ.
    Une valeur p de bootstrap au-dessus de 0,01 serait donc un défaut du code.
    """
    generateurs = child_generators(GRAINE, 2)
    donnees = generateurs[0].normal(0.0, 0.01, size=(400, 8))
    donnees[:, 0] += 0.003
    cadre = _cadre(donnees)
    repere = pd.Series(0.0, index=cadre.index)
    resultat = whites_reality_check(
        cadre,
        repere,
        n_bootstrap=500,
        generator=generateurs[1],
        block_size=4.0,
    )
    assert resultat.pvalue <= 0.01
    assert resultat.best_strategy == "s0"
    assert resultat.n_observations == 400


def test_white_refuse_une_matrice_vide_ou_trop_courte() -> None:
    """Les cas limites lèvent une erreur nommée plutôt que de rendre un nombre."""
    generateur = make_generator(GRAINE)
    index = pd.date_range("2000-01-03", periods=2, freq="B")
    vide = pd.DataFrame(index=index)
    with pytest.raises(InsufficientDataError):
        whites_reality_check(
            vide,
            pd.Series(0.0, index=index),
            generator=generateur,
            block_size=1.0,
        )
    court = pd.DataFrame({"a": [0.01, 0.02]}, index=index)
    with pytest.raises(InsufficientDataError):
        whites_reality_check(
            court,
            pd.Series(0.0, index=index),
            generator=generateur,
            block_size=1.0,
        )


def test_white_refuse_un_bloc_hors_domaine() -> None:
    """Une longueur de bloc sous 1 ou au-delà de la série lève une erreur de configuration."""
    generateur = make_generator(GRAINE)
    cadre = _cadre(make_generator(GRAINE).normal(0.0, 0.01, size=(50, 3)))
    repere = pd.Series(0.0, index=cadre.index)
    with pytest.raises(ConfigError):
        whites_reality_check(
            cadre,
            repere,
            generator=generateur,
            block_size=0.5,
        )
    with pytest.raises(ConfigError):
        whites_reality_check(
            cadre,
            repere,
            generator=generateur,
            block_size=500.0,
        )


def test_un_tireur_injecte_donne_le_meme_verdict_que_celui_du_laboratoire() -> None:
    """Le contrat ``IndexResampler`` est respecté, et le verdict ne dépend pas du tireur.

    Deux tirages de blocs différents, celui du laboratoire et la récurrence de
    Hansen recopiée dans ce fichier, doivent conclure la même chose sur un jeu
    où une stratégie surperforme de six erreurs types. Un verdict qui dépendrait
    du tireur signalerait un défaut de la statistique, pas du bootstrap.
    """
    generateurs = child_generators(GRAINE, 3)
    donnees = generateurs[0].normal(0.0, 0.01, size=(400, 8))
    donnees[:, 0] += 0.003
    cadre = _cadre(donnees)
    repere = pd.Series(0.0, index=cadre.index)

    du_laboratoire = whites_reality_check(
        cadre, repere, n_bootstrap=300, generator=generateurs[1], block_size=4.0
    )
    injecte = whites_reality_check(
        cadre,
        repere,
        n_bootstrap=300,
        generator=generateurs[2],
        block_size=4.0,
        resampler=_reference_stationary_bootstrap,
    )
    assert du_laboratoire.pvalue <= 0.01
    assert injecte.pvalue <= 0.01
    assert du_laboratoire.statistic == pytest.approx(injecte.statistic, rel=1e-15)


def test_un_tireur_de_mauvaise_forme_est_refuse() -> None:
    """Un tireur qui rend une matrice de mauvaise forme lève, plutôt que de calculer faux."""

    def tireur_fautif(
        n_observations: int,
        *,
        n_resamples: int,
        block_size: float,
        generator: np.random.Generator,
    ) -> np.ndarray:
        """Rend volontairement une matrice trop courte."""
        return generator.integers(0, n_observations, size=(n_resamples, n_observations - 1))

    cadre = _cadre(make_generator(GRAINE).normal(0.0, 0.01, size=(60, 3)))
    with pytest.raises(ConfigError):
        whites_reality_check(
            cadre,
            pd.Series(0.0, index=cadre.index),
            n_bootstrap=10,
            generator=make_generator(GRAINE),
            block_size=4.0,
            resampler=tireur_fautif,
        )


# --------------------------------------------------------------------------
# Le test SPA de Hansen
# --------------------------------------------------------------------------


def _jeu_avec_ballast(n_dates: int, n_ballast: int, generateur: np.random.Generator) -> pd.DataFrame:
    """Construit une stratégie honnête, deux neutres, puis des stratégies désastreuses."""
    utiles = generateur.normal(0.0, 0.01, size=(n_dates, 3))
    utiles[:, 0] += 0.001
    if n_ballast == 0:
        return _cadre(utiles)
    ballast = generateur.normal(-0.01, 0.01, size=(n_dates, n_ballast))
    return _cadre(np.hstack([utiles, ballast]))


def test_hansen_ordonne_ses_trois_valeurs_p() -> None:
    """La borne inférieure est sous la cohérente, elle-même sous la supérieure.

    Propriété démontrée par Hansen (2005), section 2.4. Le recentrage inférieur
    ramène toute moyenne négative à zéro, donc décale la loi de bootstrap vers
    le bas et rend un test LIBÉRAL. Le recentrage supérieur laisse toutes les
    moyennes, donc rend le test le plus CONSERVATEUR des trois, celui de la
    configuration la moins favorable.
    """
    generateurs = child_generators(GRAINE, 2)
    cadre = _jeu_avec_ballast(400, 12, generateurs[0])
    repere = pd.Series(0.0, index=cadre.index)
    resultat = hansen_spa(
        cadre,
        repere,
        n_bootstrap=400,
        generator=generateurs[1],
        block_size=4.0,
    )
    assert resultat.pvalue_lower <= resultat.pvalue_consistent <= resultat.pvalue_upper
    # Les douze stratégies de ballast sont mauvaises par construction. Les DEUX
    # stratégies neutres peuvent l'être aussi par tirage, d'où l'inégalité. La
    # stratégie honnête, elle, gagne 0,001 par période pour un seuil à moins
    # 0,00095, donc elle ne peut pas être comptée : la borne haute est 14 sur
    # quinze stratégies, et non quinze.
    assert 12 <= resultat.n_poor_alternatives <= 14


def test_le_ballast_dilue_white_et_laisse_hansen_intact() -> None:
    """Ajouter douze stratégies désastreuses gonfle White et ne touche pas Hansen.

    C'est le résultat central de Hansen (2005) : le contrôle de réalité peut
    être manipulé par l'ajout de mauvaises alternatives, et le recentrage
    cohérent l'en protège.

    Valeur attendue par démonstration, pas par exécution. Une stratégie de
    surperformance moyenne très négative est classée mauvaise par le seuil en
    racine de deux fois le logarithme itéré, donc recentrée sur sa propre
    moyenne. Sa statistique de bootstrap reste alors loin sous le maximum, à
    toutes les répétitions. La valeur p cohérente doit donc être EXACTEMENT
    identique, aux mêmes indices de bootstrap, avec ou sans ballast.

    Le contrôle de réalité, lui, recentre tout le monde sur zéro. Le maximum de
    quinze écarts de bootstrap dépasse celui de trois bien plus souvent, et sa
    valeur p monte.
    """
    generateur_donnees = make_generator(GRAINE)
    sans = _jeu_avec_ballast(400, 0, generateur_donnees)
    avec = _jeu_avec_ballast(400, 12, make_generator(GRAINE))
    np.testing.assert_allclose(avec.to_numpy()[:, :3], sans.to_numpy(), rtol=0, atol=0)
    repere = pd.Series(0.0, index=sans.index)

    arguments = {"n_bootstrap": 600, "block_size": 4.0}
    spa_sans = hansen_spa(sans, repere, generator=make_generator(GRAINE_BALLAST), **arguments)
    spa_avec = hansen_spa(avec, repere, generator=make_generator(GRAINE_BALLAST), **arguments)
    rc_sans = whites_reality_check(sans, repere, generator=make_generator(GRAINE_BALLAST), **arguments)
    rc_avec = whites_reality_check(avec, repere, generator=make_generator(GRAINE_BALLAST), **arguments)

    assert spa_avec.pvalue_consistent == spa_sans.pvalue_consistent
    assert rc_avec.pvalue > rc_sans.pvalue + 0.02, (
        f"White passe de {rc_sans.pvalue} à {rc_avec.pvalue}, dilution attendue plus forte"
    )


def test_hansen_rejette_un_vrai_avantage() -> None:
    """Une surperformance de six erreurs types fait s'effondrer les trois valeurs p.

    Même calcul à la main que pour le contrôle de réalité. La stratégie 0
    surperforme de 0,003 par période pour un écart type de 0,01, sur 400
    périodes, soit une statistique studentisée de 6,0. Sous l'hypothèse nulle,
    huit normales centrées réduites dépassent 6,0 avec une probabilité de
    7,9e-9, MODÉLISÉ.
    """
    generateurs = child_generators(GRAINE, 2)
    donnees = generateurs[0].normal(0.0, 0.01, size=(400, 8))
    donnees[:, 0] += 0.003
    cadre = _cadre(donnees)
    repere = pd.Series(0.0, index=cadre.index)
    resultat = hansen_spa(
        cadre,
        repere,
        n_bootstrap=500,
        generator=generateurs[1],
        block_size=4.0,
    )
    assert resultat.pvalue_upper <= 0.01
    assert resultat.best_strategy == "s0"
    assert resultat.statistic > 4.0


def test_la_variance_de_long_terme_suit_la_formule_de_hansen_terme_a_terme() -> None:
    """La variance de long terme redonne la formule publiée, à la précision machine.

    Source de la valeur attendue : ``_reference_long_run_variance``, transcription
    littérale en boucles de la formule de Hansen (2005), section 3. Le module
    passe par une transformée de Fourier et des tableaux pondérés ; le double de
    test somme terme à terme. Deux chemins indépendants pour une même formule.

    Le contrôle porte sur des séries AUTOCORRÉLÉES, et c'est le point. Sur une
    série sans mémoire, toutes les autocovariances d'ordre supérieur à zéro sont
    nulles, donc le noyau de pondération ne pèse sur rien et une erreur de noyau
    passe inaperçue. Un processus autorégressif de coefficient 0,6 donne au
    contraire une variance de long terme voisine du triple de la variance
    simple.

    Les longueurs 40, 60 et 120 sont choisies courtes exprès. Le second terme du
    noyau, en :math:`(i/n)(1-q)^{n-i}`, ne pèse qu'aux grands décalages, et son
    poids relatif s'efface quand n grandit.
    """
    generateurs = child_generators(GRAINE, 3)
    q = 1.0 / 5.0
    for longueur, generateur in zip((40, 60, 120), generateurs, strict=True):
        serie = _serie_ar1(0.6, 0.01, longueur, generateur)
        attendu = _reference_long_run_variance(serie, q)
        obtenu = _politis_romano_variance(serie.reshape(-1, 1), q, 1e-16)[0]
        assert obtenu == pytest.approx(attendu, rel=1e-12), (
            f"longueur {longueur} : {obtenu} contre {attendu} par la formule"
        )
        # Contrôle de direction, pas de valeur : une autocorrélation POSITIVE
        # gonfle la variance de long terme au-dessus de la variance simple.
        assert obtenu > serie.var(ddof=0)


def test_la_variance_de_long_terme_retrouve_la_forme_fermee_autoregressive() -> None:
    """Sur un processus autorégressif, l'estimateur retrouve sa valeur théorique.

    Valeur attendue par forme fermée. Pour un processus autorégressif d'ordre un
    de coefficient phi et de bruit d'écart type sigma, la variance vaut
    sigma^2 / (1 - phi^2) et l'autocovariance d'ordre i vaut cette variance fois
    phi puissance i. Portées dans le noyau de Hansen, ces autocovariances
    THÉORIQUES donnent la cible, sans jamais passer par l'échantillon.

    Avec phi = 0,6 et q = 0,2, la cible vaut 2,844 fois la variance simple.

    Tolérance MESURÉE, non choisie. Sur 300 séries indépendantes de 2 000 points,
    l'écart relatif entre l'estimateur et cette cible a un écart type de 8,8 %,
    mesuré le 2026-09-01. La tolérance retenue est de quatre écarts types, soit
    35 %, franchie par 3 séries sur 1 000 dans cette mesure.
    """
    phi, sigma, n, q = 0.6, 0.01, 2000, 0.2
    generateur = child_generators(GRAINE, 1)[0]

    lags = np.arange(1, n, dtype=float)
    noyau = (n - lags) / n * (1.0 - q) ** lags + lags / n * (1.0 - q) ** (n - lags)
    gamma_zero = sigma**2 / (1.0 - phi**2)
    cible = gamma_zero * (1.0 + 2.0 * float(np.sum(noyau * phi**lags)))
    assert cible / gamma_zero == pytest.approx(2.844, abs=0.001)

    serie = _serie_ar1(phi, sigma, n, generateur)
    obtenu = _politis_romano_variance(serie.reshape(-1, 1), q, 1e-16)[0]
    assert obtenu == pytest.approx(cible, rel=0.35), f"{obtenu} contre une cible de {cible}"


def test_hansen_retrouve_la_variance_de_long_terme_sur_une_serie_sans_memoire() -> None:
    """Sans autocorrélation, la variance de long terme retombe sur la variance simple.

    Valeur attendue par forme fermée. La somme pondérée d'autocovariances de
    Hansen (2005) se réduit à l'autocovariance d'ordre zéro quand toutes les
    autres sont nulles. Or l'autocovariance d'ordre zéro, estimée à n degrés de
    liberté, vaut la variance de population de l'échantillon.

    Tolérance MESURÉE, non choisie pour faire passer le test. Les
    autocovariances d'ordre supérieur à zéro ne sont pas nulles en échantillon
    fini, seulement centrées sur zéro, et leur somme pondérée reste bruitée. Sur
    200 séries indépendantes de 4 000 points, l'écart relatif à la variance
    simple a un écart type de 4,1 %, mesuré le 2026-09-01. Une tolérance de 5 %
    serait donc franchie par une série sur cinq. La tolérance retenue est de
    quatre écarts types, soit 17 %.
    """
    generateurs = child_generators(GRAINE, 2)
    donnees = generateurs[0].normal(0.0, 0.02, size=(4000, 2))
    cadre = _cadre(donnees)
    repere = pd.Series(0.0, index=cadre.index)
    resultat = hansen_spa(
        cadre,
        repere,
        n_bootstrap=20,
        generator=generateurs[1],
        block_size=5.0,
    )
    variance_simple = donnees.var(axis=0, ddof=0)
    np.testing.assert_allclose(resultat.long_run_variances, variance_simple, rtol=0.17)


def test_le_seuil_des_mauvaises_strategies_est_negatif() -> None:
    """Le seuil qui écarte une stratégie du recentrage cohérent est NÉGATIF.

    Propriété par identité, et le signe décide de tout. Hansen (2005) écrit
    g_c(x) = x si x est supérieur ou égal à moins A, et zéro sinon, avec
    A = racine de (omega au carré sur n) fois deux fois le logarithme itéré.
    Une stratégie n'est écartée que si sa surperformance moyenne est FRANCHEMENT
    négative. Un seuil positif écarterait au contraire toutes les stratégies
    médiocrement bonnes, ce qui rendrait le recentrage cohérent plus libéral que
    le recentrage inférieur.

    Deux contrôles. D'abord l'identité, sur un jeu mêlant bonnes et mauvaises
    stratégies : le compte rendu égale le compte des moyennes sous moins A,
    A étant recalculé dans le test depuis la variance de long terme rendue.

    Ensuite un contrôle de signe. Six stratégies de surperformance moyenne
    +0,0002 par période, pour un écart type de 0,01 sur 400 périodes, ont un A
    voisin de 0,00095. Aucune n'est donc mauvaise. Avec un seuil de signe
    inversé, les six le seraient.
    """
    generateurs = child_generators(GRAINE, 4)

    melange = _jeu_avec_ballast(400, 12, generateurs[0])
    resultat = hansen_spa(
        melange,
        pd.Series(0.0, index=melange.index),
        n_bootstrap=50,
        generator=generateurs[1],
        block_size=4.0,
    )
    n = resultat.n_observations
    seuil = -np.sqrt(resultat.long_run_variances / n * 2.0 * math.log(math.log(n)))
    assert np.all(seuil < 0.0)
    attendu = int(np.count_nonzero(melange.to_numpy().mean(axis=0) < seuil))
    assert resultat.n_poor_alternatives == attendu

    faiblement_positives = generateurs[2].normal(0.0, 0.01, size=(400, 6))
    faiblement_positives -= faiblement_positives.mean(axis=0, keepdims=True)
    faiblement_positives += 0.0002
    cadre = _cadre(faiblement_positives)
    resultat_positif = hansen_spa(
        cadre,
        pd.Series(0.0, index=cadre.index),
        n_bootstrap=50,
        generator=generateurs[3],
        block_size=4.0,
    )
    ampleur = math.sqrt(0.0001 / 400 * 2.0 * math.log(math.log(400)))
    assert ampleur == pytest.approx(0.000946, abs=0.00001)
    assert resultat_positif.n_poor_alternatives == 0


def test_la_statistique_de_hansen_est_bornee_a_zero() -> None:
    """Quand toutes les stratégies perdent, la statistique vaut exactement zéro.

    Propriété par définition. Hansen (2005) définit sa statistique comme le
    maximum entre le plus grand des rapports studentisés et zéro. Sans cette
    borne, une famille où tout le monde perd rendrait une statistique négative,
    et la valeur p perdrait son sens.

    Six stratégies perdant 0,003 par période pour un écart type de 0,01 sur 400
    périodes ont chacune un rapport studentisé voisin de moins 6. Le maximum est
    donc négatif avant la borne, et nul après.
    """
    generateurs = child_generators(GRAINE, 2)
    donnees = generateurs[0].normal(0.0, 0.01, size=(400, 6)) - 0.003
    cadre = _cadre(donnees)
    resultat = hansen_spa(
        cadre,
        pd.Series(0.0, index=cadre.index),
        n_bootstrap=200,
        generator=generateurs[1],
        block_size=4.0,
    )
    assert np.all(resultat.studentized_means < -4.0)
    assert resultat.statistic == 0.0
    # Toute statistique de bootstrap est elle aussi bornée à zéro, donc jamais
    # STRICTEMENT au-dessus de zéro par la seule borne. La valeur p mesure alors
    # la part des rééchantillons réellement positifs.
    assert 0.0 <= resultat.pvalue_consistent <= 1.0
    assert resultat.pvalue_lower <= resultat.pvalue_consistent <= resultat.pvalue_upper


def test_hansen_refuse_un_plancher_de_variance_non_positif() -> None:
    """Un plancher nul ou négatif lève une erreur de configuration."""
    cadre = _cadre(make_generator(GRAINE).normal(0.0, 0.01, size=(60, 3)))
    with pytest.raises(ConfigError):
        hansen_spa(
            cadre,
            pd.Series(0.0, index=cadre.index),
            generator=make_generator(GRAINE),
            block_size=4.0,
            variance_floor=0.0,
        )


# --------------------------------------------------------------------------
# Le registre des essais
# --------------------------------------------------------------------------


def test_le_registre_compte_par_famille_et_en_tout() -> None:
    """Les comptes par famille et le compte total sont exacts.

    Valeur attendue par dénombrement à la main : trois essais en momentum, deux
    en portage, donc cinq au total.
    """
    registre = TrialCounter()
    for nom, sharpe in [("a", 0.4), ("b", 0.9), ("c", -0.2)]:
        registre = registre.record("momentum", nom, sharpe)
    for nom, sharpe in [("d", 0.1), ("e", 0.5)]:
        registre = registre.record("portage", nom, sharpe)

    assert registre.n_trials("momentum") == 3
    assert registre.n_trials("portage") == 2
    assert registre.n_trials() == 5
    assert registre.families() == ("momentum", "portage")


def test_le_registre_est_gele_et_ne_change_pas_sous_les_pieds() -> None:
    """Enregistrer un essai rend un registre neuf sans modifier l'ancien."""
    vide = TrialCounter()
    un = vide.record("momentum", "a", 0.4)
    deux = un.record("momentum", "b", 0.9)
    assert vide.n_trials() == 0
    assert un.n_trials() == 1
    assert deux.n_trials() == 2


def test_le_registre_refuse_un_doublon_et_un_sharpe_non_fini() -> None:
    """Un essai déjà enregistré ou un ratio non fini lève une erreur de configuration."""
    registre = TrialCounter().record("momentum", "a", 0.4)
    with pytest.raises(ConfigError):
        registre.record("momentum", "a", 0.7)
    with pytest.raises(ConfigError):
        registre.record("momentum", "b", float("nan"))
    assert registre.record("portage", "a", 0.7).n_trials() == 2


def test_la_variance_des_essais_est_celle_de_numpy() -> None:
    """La variance rendue est la variance sans biais, contrôlée par NumPy.

    Source de la valeur attendue : ``numpy.var(ddof=1)``, implémentation
    indépendante. Le contrôle porte aussi sur un calcul à la main, la variance
    sans biais de (0 ; 1 ; 2) valant ((0-1)^2 + 0 + (2-1)^2) / 2 = 1.
    """
    valeurs = [0.0, 1.0, 2.0]
    registre = TrialCounter()
    for i, s in enumerate(valeurs):
        registre = registre.record("momentum", f"e{i}", s)
    assert registre.sharpe_variance("momentum") == pytest.approx(1.0, rel=1e-15)
    assert registre.mean_sharpe("momentum") == pytest.approx(1.0, rel=1e-15)

    generateur = make_generator(GRAINE)
    tirages = generateur.normal(0.3, 0.7, size=60)
    grand = TrialCounter()
    for i, s in enumerate(tirages):
        grand = grand.record("carry", f"e{i}", float(s))
    assert grand.sharpe_variance("carry") == pytest.approx(float(np.var(tirages, ddof=1)), rel=1e-12)


def test_le_registre_rend_les_intrants_du_sharpe_degonfle() -> None:
    """Le nombre d'essais indépendants suit l'équation (9) de Bailey et López de Prado.

    Calcul à la main. Avec M = 20 essais et une corrélation moyenne déclarée de
    0,6, la formule N = rho + (1 - rho) M donne 0,6 + 0,4 x 20 = 8,6. À
    corrélation nulle elle rend 20, et à corrélation 1 elle rend 1.
    """
    registre = TrialCounter()
    for i in range(20):
        registre = registre.record("momentum", f"e{i}", 0.1 * i)

    intrants = registre.deflation_inputs("momentum", average_correlation=0.6)
    assert intrants.n_trials == 20
    assert intrants.n_independent_trials == pytest.approx(8.6, rel=1e-12)
    assert intrants.best_sharpe == pytest.approx(1.9, rel=1e-12)
    assert intrants.family == "momentum"

    assert registre.deflation_inputs("momentum").n_independent_trials == pytest.approx(20.0)
    assert registre.deflation_inputs(
        "momentum", average_correlation=1.0
    ).n_independent_trials == pytest.approx(1.0)


def test_le_registre_refuse_une_correlation_hors_bornes() -> None:
    """Une corrélation moyenne hors de l'intervalle unité lève."""
    registre = TrialCounter().record("m", "a", 0.1).record("m", "b", 0.2)
    with pytest.raises(ConfigError):
        registre.deflation_inputs("m", average_correlation=1.5)
    with pytest.raises(ConfigError):
        registre.deflation_inputs("m", average_correlation=-0.1)


def test_le_registre_refuse_une_variance_sur_un_seul_essai() -> None:
    """Une variance exige au moins deux essais, et le dit."""
    registre = TrialCounter().record("m", "a", 0.1)
    with pytest.raises(InsufficientDataError):
        registre.sharpe_variance("m")
    with pytest.raises(InsufficientDataError):
        TrialCounter().mean_sharpe()


# --------------------------------------------------------------------------
# Validation des entrées
# --------------------------------------------------------------------------


def test_les_valeurs_p_hors_domaine_sont_refusees() -> None:
    """Un vecteur vide, une valeur manquante ou hors bornes lève l'erreur nommée."""
    with pytest.raises(InsufficientDataError):
        bonferroni([])
    with pytest.raises(DataQualityError):
        bonferroni([0.1, np.nan])
    with pytest.raises(DataQualityError):
        bonferroni([0.1, 1.5])
    with pytest.raises(DataQualityError):
        bonferroni([0.1, -0.01])
    with pytest.raises(ConfigError):
        bonferroni([0.1, 0.2], alpha=0.0)


def test_adjust_pvalues_accepte_les_alias_et_refuse_l_inconnu() -> None:
    """Les alias « bh », « by » et « bhy » mènent aux bonnes procédures."""
    valeurs = [0.001, 0.02, 0.3]
    assert adjust_pvalues(valeurs, method="bh").method == "benjamini_hochberg"
    assert adjust_pvalues(valeurs, method="by").method == "benjamini_yekutieli"
    assert adjust_pvalues(valeurs, method="BHY").method == "benjamini_yekutieli"
    assert adjust_pvalues(valeurs, method="Holm").method == "holm"
    with pytest.raises(ConfigError):
        adjust_pvalues(valeurs, method="sidak")


def test_les_procedures_declarent_ce_qu_elles_controlent() -> None:
    """Bonferroni et Holm contrôlent l'erreur familiale, les deux autres le taux de fausses découvertes."""
    valeurs = [0.001, 0.02, 0.3]
    assert bonferroni(valeurs).controls == "FWER"
    assert holm(valeurs).controls == "FWER"
    assert benjamini_hochberg(valeurs).controls == "FDR"
    assert benjamini_yekutieli(valeurs).controls == "FDR"


def test_une_serie_pandas_est_acceptee_comme_vecteur_de_valeurs_p() -> None:
    """Une série pandas donne le même résultat qu'un tableau NumPy."""
    valeurs = [0.001, 0.02, 0.3, 0.7]
    serie = pd.Series(valeurs, index=["a", "b", "c", "d"])
    np.testing.assert_allclose(
        holm(serie).adjusted_pvalues, holm(np.asarray(valeurs)).adjusted_pvalues, rtol=1e-15
    )

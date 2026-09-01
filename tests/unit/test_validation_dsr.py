"""Les tests du Sharpe probabiliste et du Sharpe dégonflé.

**D'où viennent les valeurs attendues.** Aucune ne sort de l'exécution du code.
Elles proviennent de quatre sources, nommées à chaque test.

Les valeurs PUBLIÉES viennent des deux articles sources, dont les exemples
chiffrés sont reproduits ici. Côté 2014 : le DSR de 0,9505 pour 46 essais et de
0,95 pour 88 essais sous rendements normaux. Côté 2012 : la longueur minimale de
59,895 mois, les 2,73 années de l'exemple quotidien, et les quatre longueurs
minimales de la figure 16.

Les IDENTITÉS sont exactes et testées à 1e-12. Le PSR d'un Sharpe égal à son
repère vaut 0,5. L'aller-retour entre longueur minimale et PSR redonne le niveau
de confiance. Et la variance de Bailey égale celle de Mertens.

Les SIMULATIONS servent de vérité indépendante là où aucune forme fermée
n'existe : le maximum de N tirages normaux, et la calibration du PSR sous
l'hypothèse nulle. Les tolérances y sont exprimées en erreurs types de la
moyenne simulée, et justifiées sur place.

La QUADRATURE donne l'espérance exacte du maximum de N normales, ce qui permet
de mesurer l'erreur de l'approximation plutôt que de la supposer.
"""

from __future__ import annotations

import math
from itertools import pairwise

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from scipy.integrate import quad
from scipy.stats import kurtosis as scipy_kurtosis
from scipy.stats import norm
from scipy.stats import skew as scipy_skew

from quantlab.core.determinism import child_generators
from quantlab.core.errors import DataQualityError, InsufficientDataError
from quantlab.validation.dsr import (
    DEFAULT_CONFIDENCE,
    EULER_MASCHERONI,
    MIN_OBSERVATIONS,
    DeflatedSharpeResult,
    deflated_sharpe_ratio,
    expected_maximum_sharpe,
    haircut,
    minimum_track_record_length,
    probabilistic_sharpe_ratio,
    sharpe_variance_term,
)

# Graine unique de ce fichier. Toutes les graines dérivées passent par
# child_generators, jamais par « graine + i » (règle 14 du CLAUDE.md).
SEED = 20260901

# Les paramètres de l'exemple chiffré de Bailey et López de Prado (2014),
# section « A numerical example » : Sharpe annuel de 2,5 sur cinq ans de données
# quotidiennes à 250 séances par an, cent essais indépendants, variance des
# essais de 0,002, asymétrie -3 et aplatissement 10.
PAPER_SESSIONS_PER_YEAR = 250.0
PAPER_SR = 2.5 / math.sqrt(PAPER_SESSIONS_PER_YEAR)
PAPER_N_OBS = 1250.0
PAPER_SKEW = -3.0
PAPER_KURTOSIS = 10.0
PAPER_TRIAL_VARIANCE = 0.002


def _exact_expected_maximum(n_trials: int) -> float:
    """Rend l'espérance EXACTE du maximum de n tirages normaux centrés réduits.

    La densité du maximum de n variables indépendantes de même loi vaut
    n F(x)^{n-1} f(x). L'intégrale se calcule par quadrature adaptative, donc
    sans tirage aléatoire et sans lien avec la formule testée. Elle sert de
    vérité indépendante pour mesurer l'erreur de l'approximation.

    Args:
        n_trials: le nombre de tirages.

    Returns:
        L'espérance du maximum, en unités d'écart type.
    """

    def integrand(x: float) -> float:
        return x * n_trials * norm.cdf(x) ** (n_trials - 1) * norm.pdf(x)

    value, _ = quad(integrand, -12.0, 12.0, limit=400)
    return float(value)


# --------------------------------------------------------------------------
# 1. Les valeurs publiées
# --------------------------------------------------------------------------


def test_exemple_publie_du_dsr_quarante_six_essais() -> None:
    """Le DSR vaut 0,9505 pour 46 essais, chiffre IMPRIMÉ dans l'article.

    Source : Bailey et López de Prado (2014), section « A numerical example ».
    L'article écrit que le DSR « aurait valu 0,9505, au-dessus du seuil de
    confiance de 95 % », si le chercheur n'avait conduit que 46 essais.
    """
    valeur = deflated_sharpe_ratio(
        PAPER_SR, PAPER_TRIAL_VARIANCE, 46, PAPER_N_OBS, PAPER_SKEW, PAPER_KURTOSIS
    )
    assert valeur == pytest.approx(0.9505, abs=5e-5)


def test_exemple_publie_du_dsr_cent_essais() -> None:
    """Le DSR vaut environ 0,90 pour 100 essais, chiffre annoncé dans l'article.

    Source : même section. L'article conclut qu'« il n'y a que 90 % de chances
    que le vrai Sharpe de cette stratégie dépasse zéro ». La tolérance de 5e-3
    reflète la précision à laquelle l'article publie ce chiffre, deux décimales.
    """
    valeur = deflated_sharpe_ratio(
        PAPER_SR, PAPER_TRIAL_VARIANCE, 100, PAPER_N_OBS, PAPER_SKEW, PAPER_KURTOSIS
    )
    assert valeur == pytest.approx(0.90, abs=5e-3)


def test_exemple_publie_du_dsr_sous_rendements_normaux() -> None:
    """Sous des rendements normaux, le DSR vaut 0,95 après 88 essais.

    Source : même section. « Si la stratégie avait montré des rendements
    normaux, le DSR aurait valu 0,95 après N = 88 essais indépendants. »

    Ce test est le PLUS important du fichier pour la convention d'aplatissement.
    L'article écrit que les rendements normaux correspondent à une asymétrie
    nulle et à un aplatissement de 3, et non de 0. C'est donc l'aplatissement
    NON EXCÉDENTAIRE qui entre dans la formule.

    Passer 0 à la place de 3 ne rend aucun nombre : le module lève une
    DataQualityError, puisque aucune loi n'a un aplatissement non excédentaire
    sous 1. Le cas où la mauvaise convention passerait inaperçue, un
    aplatissement de 7 pour 10, est traité par le test suivant.
    """
    valeur = deflated_sharpe_ratio(PAPER_SR, PAPER_TRIAL_VARIANCE, 88, PAPER_N_OBS, 0.0, 3.0)
    assert valeur == pytest.approx(0.95, abs=1e-3)


def test_convention_daplatissement_le_choix_zero_donne_un_autre_nombre() -> None:
    """Passer l'aplatissement excédentaire change le résultat, donc le test mord.

    Ce test protège le test précédent contre l'illusion d'une tolérance trop
    lâche. Il vérifie que la convention EXCÉDENTAIRE, aplatissement 0 sous la
    normale, donne un nombre différent du bon. Le cas retenu est celui où
    l'écart est visible : l'exemple publié à asymétrie -3 et aplatissement 10.
    """
    bon = deflated_sharpe_ratio(PAPER_SR, PAPER_TRIAL_VARIANCE, 100, PAPER_N_OBS, PAPER_SKEW, PAPER_KURTOSIS)
    mauvais = deflated_sharpe_ratio(
        PAPER_SR, PAPER_TRIAL_VARIANCE, 100, PAPER_N_OBS, PAPER_SKEW, PAPER_KURTOSIS - 3.0
    )
    assert abs(bon - mauvais) > 1e-3


def test_exemple_publie_de_la_longueur_minimale_en_mois() -> None:
    """La longueur minimale vaut 59,895 mois, chiffre IMPRIMÉ dans l'article.

    Source : Bailey et López de Prado (2012), annexe A.3. Le code de l'annexe
    fixe ``stats=[2, 12**0.5, -0.72, 5.78]`` et ``sr_ref=1/12**0.5``, donc un
    Sharpe mensuel de 2/racine(12), un repère mensuel de 1/racine(12), une
    asymétrie de -0,72 et un aplatissement de 5,78. Le texte annonce
    « MinTRL = 59,895 mois, soit environ 4,99 années ».
    """
    sr = 2.0 / math.sqrt(12.0)
    repere = 1.0 / math.sqrt(12.0)
    longueur = minimum_track_record_length(sr, repere, -0.72, 5.78, DEFAULT_CONFIDENCE)
    assert longueur == pytest.approx(59.895, abs=0.01)
    assert longueur / 12.0 == pytest.approx(4.99, abs=0.005)


def test_exemple_publie_de_la_longueur_minimale_quotidienne() -> None:
    """Un Sharpe annuel de 2 face à un repère de 1 exige 2,73 années de données.

    Source : Bailey et López de Prado (2012), section 5, commentaire de la
    figure 8. Le texte y écrit qu'« une durée de 2,73 années est nécessaire pour
    qu'un Sharpe annualisé de 2 soit considéré supérieur à 1 à un niveau de
    confiance de 95 % ». L'hypothèse est celle de rendements quotidiens
    indépendants et normaux.

    Le résultat vaut 2,731 années que l'on compte 250 ou 252 séances par an, la
    conversion se simplifiant presque entièrement.
    """
    for seances in (250.0, 252.0):
        sr = 2.0 / math.sqrt(seances)
        repere = 1.0 / math.sqrt(seances)
        longueur = minimum_track_record_length(sr, repere, 0.0, 3.0, DEFAULT_CONFIDENCE)
        assert longueur / seances == pytest.approx(2.73, abs=0.005)


@pytest.mark.parametrize(
    ("nom", "sr", "asymetrie", "aplatissement", "ecart_type_publie", "trl_zero", "trl_demi"),
    [
        ("PSR maximal", 0.7079, -0.2250, 2.9570, 0.1028, 0.7152, 1.0804),
        ("Sharpe maximal", 0.8183, -1.4455, 7.0497, 0.1550, 1.1593, 1.6695),
    ],
)
def test_exemple_publie_de_la_figure_seize(
    nom: str,
    sr: float,
    asymetrie: float,
    aplatissement: float,
    ecart_type_publie: float,
    trl_zero: float,
    trl_demi: float,
) -> None:
    """Les quatre longueurs minimales de la figure 16 se retrouvent à la décimale.

    Source : Bailey et López de Prado (2012), figure 16 du prétirage, « Stats of
    Max PSR and Max SR portfolios ». Elle compare le portefeuille de PSR maximal
    au portefeuille de Sharpe maximal, sur 134 observations mensuelles. Le
    tableau publie l'écart type du Sharpe, puis les longueurs minimales en
    ANNÉES contre un repère nul et contre un repère annualisé de 0,5.

    La figure 11 du même prétirage porte un tout autre contenu, la table des
    longueurs minimales à asymétrie -0,72 et aplatissement 5,78.

    Deux conventions se lisent dans ces chiffres. L'écart type publié vaut la
    racine du facteur de variance divisée par racine(T-1), ce qui confirme le
    T-1. Et le repère de 0,5 est ANNUALISÉ, donc divisé par racine(12) avant
    d'entrer dans la formule mensuelle.
    """
    observations = 134.0
    facteur = sharpe_variance_term(sr, asymetrie, aplatissement)
    assert math.sqrt(facteur / (observations - 1.0)) == pytest.approx(ecart_type_publie, abs=5e-5)

    sans_repere = minimum_track_record_length(sr, 0.0, asymetrie, aplatissement, DEFAULT_CONFIDENCE)
    assert sans_repere / 12.0 == pytest.approx(trl_zero, abs=5e-4), nom

    repere_annuel = 0.5 / math.sqrt(12.0)
    avec_repere = minimum_track_record_length(sr, repere_annuel, asymetrie, aplatissement, DEFAULT_CONFIDENCE)
    assert avec_repere / 12.0 == pytest.approx(trl_demi, abs=5e-4), nom


def test_exemple_publie_du_psr_de_la_figure_seize() -> None:
    """Le PSR contre un repère annualisé de 0,5 vaut 0,99999 pour le Sharpe maximal.

    Source : Bailey et López de Prado (2012), figure 16 du prétirage, ligne
    PSR(0.5), colonne du portefeuille de Sharpe maximal. La même ligne donne
    1,00000 au portefeuille de PSR maximal, valeur trop arrondie pour contraindre
    quoi que ce soit, donc non reprise ici.
    """
    valeur = probabilistic_sharpe_ratio(0.8183, 0.5 / math.sqrt(12.0), 134.0, -1.4455, 7.0497)
    assert valeur == pytest.approx(0.99999, abs=1e-5)


def test_le_seuil_se_deduit_du_dsr_publie_a_quarante_six_essais() -> None:
    """Le seuil de sélection à 46 essais vaut 0,100363, déduit du DSR imprimé.

    **D'où vient la valeur attendue.** Elle N'EST PAS une sortie du code. Le
    seul chiffre du seuil que l'article imprime en clair est le DSR de 0,9505 à
    46 essais. On l'inverse à la main pour en tirer le repère qui le produit,
    puis on compare ce repère à ce que rend la formule du maximum attendu.

    L'article de 2014 n'imprime que « 90 % » pour ses cent essais, donc deux
    décimales. Inverser ce 0,90 ne contraindrait le seuil qu'à 5e-4 près, et
    toute valeur plus précise ne pourrait venir que du code lui-même. Le 0,9505
    à quatre décimales est le seul point d'appui honnête.

    **La tolérance.** Le DSR publié est arrondi à quatre décimales, soit une
    incertitude de 5e-5 sur la probabilité. Convertie en seuil, elle vaut
    5e-5 / phi(1,6497) x 1,237171 / racine(1249), soit 1,7e-5. La tolérance de
    2e-5 la couvre sans la dépasser.
    """
    # Calcul à la main, à partir du DSR PUBLIÉ de 0,9505 à N = 46 :
    #   z = Phi^{-1}(0,9505) = 1,6497211
    #   dénominateur = racine(1 + 3 x 0,1581139 + (10-1)/4 x 0,1581139^2) = 1,2371708
    #   SR_0 = 0,1581139 - 1,6497211 x 1,2371708 / racine(1249) = 0,1003630
    seuil_attendu = 0.1003630
    assert expected_maximum_sharpe(46, PAPER_TRIAL_VARIANCE) == pytest.approx(seuil_attendu, abs=2e-5)
    assert haircut(PAPER_SR, 46, PAPER_TRIAL_VARIANCE) == pytest.approx(seuil_attendu / PAPER_SR, abs=2e-4)


def test_le_rasage_est_le_seuil_rapporte_au_sharpe_observe() -> None:
    """Le rasage vaut le seuil divisé par le Sharpe observé, sur trois cas.

    Identité de définition, vérifiée sans passer par un chiffre publié : la
    fonction de rasage ne doit rien faire d'autre que ce quotient. Le seuil
    entre ici par la fonction qui le calcule, dont la justesse est établie
    ailleurs par les chiffres publiés et par la quadrature.
    """
    for essais in (2, 46, 1000):
        attendu = expected_maximum_sharpe(essais, PAPER_TRIAL_VARIANCE) / PAPER_SR
        assert haircut(PAPER_SR, essais, PAPER_TRIAL_VARIANCE) == pytest.approx(attendu, abs=1e-15)


# --------------------------------------------------------------------------
# 2. Les identités exactes
# --------------------------------------------------------------------------


@pytest.mark.parametrize("observations", [2.0, 10.0, 250.0, 5000.0, 1_000_000.0])
@pytest.mark.parametrize("sr", [-0.5, 0.0, 0.05, 1.2])
def test_le_psr_dun_sharpe_egal_au_repere_vaut_un_demi(observations: float, sr: float) -> None:
    """Un Sharpe égal à son repère rend exactement 0,5, quelle que soit la taille.

    Identité exacte : le numérateur du z est nul, et la fonction de répartition
    normale vaut 0,5 en zéro. Le résultat ne dépend ni de T, ni des moments.
    """
    valeur = probabilistic_sharpe_ratio(sr, sr, observations, -0.4, 6.0)
    assert valeur == pytest.approx(0.5, abs=1e-12)


@pytest.mark.parametrize("confiance", [0.5, 0.75, 0.90, 0.95, 0.99, 0.999])
def test_aller_retour_entre_longueur_minimale_et_psr(confiance: float) -> None:
    """Le PSR évalué à la longueur minimale redonne exactement le niveau demandé.

    Identité algébrique. En posant T = MinTRL, le facteur racine(T-1) vaut
    racine(V) x z / (SR - SR*), et le z du PSR se réduit à z tout court. Le
    résultat est donc Phi(z), soit le niveau de confiance, à la précision
    machine.
    """
    sr, repere, asymetrie, aplatissement = 0.18, 0.05, -0.6, 7.2
    longueur = minimum_track_record_length(sr, repere, asymetrie, aplatissement, confiance)
    retour = probabilistic_sharpe_ratio(sr, repere, longueur, asymetrie, aplatissement)
    assert retour == pytest.approx(confiance, abs=1e-12)


@pytest.mark.parametrize("sr", [0.0, 0.05, 0.2, 0.9, 2.0])
def test_le_facteur_de_variance_redonne_la_forme_de_lo_sous_la_normale(sr: float) -> None:
    """Sous la normale, le facteur vaut 1 + SR au carré sur 2, forme de Lo (2002).

    Identité fermée. Avec une asymétrie nulle et un aplatissement NON
    excédentaire de 3, le terme (gamma_4 - 1)/4 vaut exactement 1/2. C'est le
    résultat de Lo (2002), « The Statistics of Sharpe Ratios », Financial
    Analysts Journal 58(4), pour des rendements indépendants et normaux.
    """
    assert sharpe_variance_term(sr, 0.0, 3.0) == pytest.approx(1.0 + sr**2 / 2.0, abs=1e-14)


@pytest.mark.parametrize("sr", [-1.0, 0.0, 0.13, 0.75])
@pytest.mark.parametrize(("asymetrie", "aplatissement"), [(0.0, 3.0), (-1.2, 8.0), (0.9, 4.5)])
def test_lecriture_de_bailey_egale_celle_de_mertens(
    sr: float, asymetrie: float, aplatissement: float
) -> None:
    """Les deux écritures publiées de la variance du Sharpe coïncident exactement.

    Mertens (2002) écrit la variance asymptotique du Sharpe sous la forme
    1 + SR carré sur 2, moins asymétrie fois SR, plus (aplatissement - 3)/4 fois
    SR carré. Bailey et López de Prado la condensent en 1, moins asymétrie fois
    SR, plus (aplatissement - 1)/4 fois SR carré. Le développement montre que
    1/2 + (K-3)/4 vaut (K-1)/4, donc les deux sont la même quantité.

    Ce test attrape la faute de transcription la plus probable du module : un 3
    écrit à la place du 1 dans le terme d'aplatissement.
    """
    mertens = 1.0 + sr**2 / 2.0 - asymetrie * sr + (aplatissement - 3.0) / 4.0 * sr**2
    assert sharpe_variance_term(sr, asymetrie, aplatissement) == pytest.approx(mertens, abs=1e-14)


def test_un_seul_essai_ne_deforme_rien() -> None:
    """Avec un seul essai, le seuil vaut la moyenne des essais et le rasage est nul.

    Identité exacte : l'espérance du maximum d'un unique tirage est ce tirage.
    Aucune sélection n'a eu lieu, donc le DSR se confond avec le PSR contre la
    moyenne des essais, nulle par défaut.
    """
    assert expected_maximum_sharpe(1, 0.05) == 0.0
    assert expected_maximum_sharpe(1, 0.05, mean_of_trials=0.3) == 0.3
    assert haircut(0.2, 1, 0.05) == 0.0
    dsr = deflated_sharpe_ratio(0.12, 0.05, 1, 500.0, -0.3, 5.0)
    psr = probabilistic_sharpe_ratio(0.12, 0.0, 500.0, -0.3, 5.0)
    assert dsr == pytest.approx(psr, abs=1e-14)


# --------------------------------------------------------------------------
# 3. Les monotonies
# --------------------------------------------------------------------------


def test_le_psr_croit_avec_la_longueur_de_lechantillon() -> None:
    """Plus l'historique est long, plus la conclusion est assurée.

    Propriété mathématique : le z du PSR est proportionnel à racine(T-1), donc
    strictement croissant en T dès que le Sharpe dépasse son repère.
    """
    valeurs = [
        probabilistic_sharpe_ratio(0.15, 0.02, observations, -0.5, 6.0)
        for observations in (30.0, 60.0, 125.0, 250.0, 1000.0, 4000.0)
    ]
    assert all(a < b for a, b in pairwise(valeurs))


def test_le_psr_decroit_quand_lasymetrie_devient_negative() -> None:
    """Une asymétrie négative rend le Sharpe moins crédible, pas plus.

    Propriété mathématique : le terme -asymétrie x SR grandit quand l'asymétrie
    baisse, donc le dénominateur grandit et le z rétrécit. Économiquement, une
    stratégie qui gagne petit souvent et perd gros rarement a un Sharpe dont
    l'incertitude est sous-estimée par la formule usuelle.
    """
    valeurs = [
        probabilistic_sharpe_ratio(0.15, 0.02, 500.0, asymetrie, 8.0)
        for asymetrie in (-2.0, -1.0, -0.25, 0.0, 0.25, 1.0)
    ]
    assert all(a < b for a, b in pairwise(valeurs))


def test_le_psr_decroit_quand_laplatissement_monte() -> None:
    """Des queues plus épaisses abaissent le PSR, tout le reste égal.

    Propriété mathématique : le terme (aplatissement - 1)/4 fois SR carré est
    strictement croissant en aplatissement dès que le Sharpe n'est pas nul.
    """
    valeurs = [
        probabilistic_sharpe_ratio(0.15, 0.02, 500.0, 0.0, aplatissement)
        for aplatissement in (3.0, 5.0, 9.0, 15.0, 30.0)
    ]
    assert all(a > b for a, b in pairwise(valeurs))


def test_le_dsr_decroit_strictement_avec_le_nombre_dessais() -> None:
    """Chaque essai supplémentaire relève le seuil, donc abaisse le DSR.

    Propriété mathématique : le quantile normal d'ordre 1 - 1/N est strictement
    croissant en N, donc le seuil de sélection l'est aussi, donc le DSR est
    strictement décroissant. C'est la traduction chiffrée de la règle 8 : cacher
    des essais est le seul moyen de faire remonter ce nombre.
    """
    valeurs = [
        deflated_sharpe_ratio(PAPER_SR, PAPER_TRIAL_VARIANCE, essais, PAPER_N_OBS, -1.0, 6.0)
        for essais in (2, 5, 10, 50, 100, 500, 2000, 10_000)
    ]
    assert all(a > b for a, b in pairwise(valeurs))


def test_le_rasage_croit_avec_le_nombre_dessais_et_la_dispersion() -> None:
    """La part imputable à la chance grandit avec les essais et avec leur dispersion."""
    par_essais = [haircut(PAPER_SR, essais, PAPER_TRIAL_VARIANCE) for essais in (2, 10, 100, 1000)]
    assert all(a < b for a, b in pairwise(par_essais))
    par_variance = [haircut(PAPER_SR, 100, variance) for variance in (0.0005, 0.001, 0.002, 0.01)]
    assert all(a < b for a, b in pairwise(par_variance))


def test_un_sharpe_sous_le_seuil_de_selection_tombe_sous_un_demi() -> None:
    """Un Sharpe inférieur au maximum attendu de N essais rend un DSR sous 0,5.

    Le cas est construit pour être sans ambiguïté : mille essais de variance
    0,01 portent le seuil à 0,3106, très au-dessus du Sharpe observé de 0,10.
    Le numérateur du z est donc négatif, et la fonction de répartition normale
    rend moins de 0,5. C'est la situation du chercheur qui a essayé mille
    variantes et retenu la meilleure.
    """
    seuil = expected_maximum_sharpe(1000, 0.01)
    observe = 0.10
    assert observe < seuil
    valeur = deflated_sharpe_ratio(observe, 0.01, 1000, 2000.0, 0.0, 3.0)
    assert valeur < 0.5
    assert haircut(observe, 1000, 0.01) > 1.0
    # Le PSR contre zéro, lui, reste très élevé : c'est exactement l'illusion
    # que le DSR sert à dissiper.
    assert probabilistic_sharpe_ratio(observe, 0.0, 2000.0, 0.0, 3.0) > 0.99


# --------------------------------------------------------------------------
# 4. Les simulations
# --------------------------------------------------------------------------


@pytest.mark.parametrize("n_trials", [10, 50, 1000])
def test_le_maximum_attendu_contre_une_simulation(n_trials: int) -> None:
    """La formule du maximum attendu se vérifie sur deux mille tirages simulés.

    C'est le test qui prouve la formule. Le protocole est celui de l'annexe 2 de
    l'article de 2014. Tirer N Sharpe normaux de variance connue, prendre le
    maximum, recommencer deux mille fois. Puis comparer la moyenne des maxima à
    la valeur analytique.

    **La tolérance, et sa justification.** Elle est la somme de deux termes,
    parce que deux sources d'écart existent et qu'elles sont de nature
    différente. Le premier est l'erreur d'échantillonnage de la moyenne simulée,
    bornée par quatre erreurs types, soit une probabilité de dépassement de
    6 pour 100 000 sous normalité. Le second est l'erreur de l'approximation
    elle-même, qui n'est PAS nulle : elle est calculée ici par quadrature
    exacte, donc mesurée et non supposée.

    Aucune des deux ne vient de l'exécution du code testé. La quadrature intègre
    la densité du maximum, n F(x)^{n-1} f(x), et la simulation tire des normales
    avec numpy.
    """
    variance = 0.25
    repetitions = 2000
    generateurs = child_generators(SEED, repetitions)
    maxima = np.array([g.normal(0.0, math.sqrt(variance), n_trials).max() for g in generateurs], dtype=float)
    moyenne_simulee = float(maxima.mean())
    erreur_type = float(maxima.std(ddof=1)) / math.sqrt(repetitions)

    formule = expected_maximum_sharpe(n_trials, variance)
    exact = _exact_expected_maximum(n_trials) * math.sqrt(variance)
    biais_approximation = abs(formule - exact)
    tolerance = biais_approximation + 4.0 * erreur_type

    assert abs(formule - moyenne_simulee) < tolerance
    # La simulation, elle, doit coller à la valeur exacte à quatre erreurs types
    # près, sans aucune allocation pour un biais d'approximation.
    assert abs(moyenne_simulee - exact) < 4.0 * erreur_type


@pytest.mark.parametrize("n_trials", [10, 50, 100, 1000])
def test_lapproximation_du_maximum_est_prudente_et_bornee(n_trials: int) -> None:
    """L'approximation surestime le seuil exact, de moins de 0,05 écart type.

    Vérité indépendante : la quadrature de la densité du maximum. Le budget de
    0,05 est déclaré ici, et il est deux fois plus large que l'erreur observée à
    N = 10, la pire des quatre. Le SENS de l'erreur est ce qui compte pour
    l'usage : un seuil trop haut rend le DSR prudent, jamais complaisant.

    Ce test discrimine une faute plausible, l'échange des poids 1 - gamma et
    gamma entre les deux quantiles. Cet échange rend une erreur NÉGATIVE, donc
    la première assertion échoue.
    """
    formule = expected_maximum_sharpe(n_trials, 1.0)
    exact = _exact_expected_maximum(n_trials)
    assert formule > exact
    assert formule - exact < 0.05


def test_calibration_du_psr_sous_lhypothese_nulle() -> None:
    """Sous l'hypothèse nulle, le PSR moyen vaut 0,5 et sa queue à 5 % pèse 5 %.

    **Le protocole.** Deux mille échantillons de 750 rendements indépendants et
    normaux, de vrai Sharpe périodique 0,10. Sur chacun, on mesure le Sharpe, son
    asymétrie et son aplatissement, puis on calcule le PSR contre le VRAI Sharpe.
    Le repère étant exactement la valeur à estimer, le PSR doit se comporter
    comme une valeur p : uniforme sur zéro un.

    **La tolérance, et sa justification.** L'écart type d'une loi uniforme vaut
    1/racine(12), soit 0,2887, donc l'erreur type de la moyenne sur deux mille
    tirages vaut 0,0065. Quatre erreurs types donnent 0,026, seuil retenu. La
    part au-delà de 0,95 doit valoir 5 %, avec une erreur type binomiale de
    racine(0,05 x 0,95 / 2000), soit 0,0049 ; quatre erreurs types donnent 0,020.

    **Ce que ce test prouve et ce qu'il ne prouve pas.** Il prouve que la
    statistique est calibrée, donc que l'ÉCHELLE du z est la bonne. Un facteur
    de racine de T retiré ou divisé par deux fait sortir la queue de sa
    tolérance, MESURÉ à 0,4765 et 0,0005 contre 0,05 attendu.

    Il ne prouve NI le T-1, ni la convention d'aplatissement. Remplacer
    racine(T-1) par racine(T) laisse la moyenne et la queue inchangées à cinq
    décimales à 750 observations, MESURÉ. Et à un Sharpe périodique de 0,10, le
    terme en Sharpe au carré pèse moins d'un pour cent. Ce sont les exemples
    publiés qui tiennent ces deux conventions, en particulier le DSR de 0,9505
    dont la reproduction à 5e-5 exclut racine(T), qui rend 0,95057.
    """
    vrai_sharpe = 0.10
    observations = 750
    repetitions = 2000
    generateurs = child_generators(SEED + 1, repetitions)
    valeurs = np.empty(repetitions, dtype=float)
    for indice, generateur in enumerate(generateurs):
        echantillon = generateur.normal(vrai_sharpe, 1.0, observations)
        sharpe = float(echantillon.mean() / echantillon.std(ddof=1))
        valeurs[indice] = probabilistic_sharpe_ratio(
            sharpe,
            vrai_sharpe,
            float(observations),
            float(scipy_skew(echantillon)),
            float(scipy_kurtosis(echantillon, fisher=False)),
        )
    assert abs(float(valeurs.mean()) - 0.5) < 0.026
    assert abs(float((valeurs > 0.95).mean()) - 0.05) < 0.020


# --------------------------------------------------------------------------
# 5. Les cas limites et les refus
# --------------------------------------------------------------------------


@pytest.mark.parametrize("observations", [0.0, 0.5, 0.9999, -10.0])
def test_le_psr_refuse_un_echantillon_trop_court(observations: float) -> None:
    """Sous une observation, la racine de T-1 n'est pas réelle et le module refuse."""
    with pytest.raises(InsufficientDataError, match="observation"):
        probabilistic_sharpe_ratio(0.1, 0.0, observations, 0.0, 3.0)


@pytest.mark.parametrize("sr", [-1.0, 0.0, 0.3, 2.0])
def test_une_seule_observation_ne_dit_rien_et_rend_un_demi(sr: float) -> None:
    """À une seule observation, le PSR vaut exactement 0,5 pour tout Sharpe.

    Identité exacte : la racine de T-1 s'annule, donc le z aussi, donc la
    fonction de répartition rend 0,5. C'est la bonne réponse d'un échantillon
    sans information, et c'est aussi la borne basse de la longueur minimale, que
    le niveau de confiance de 0,5 atteint exactement.
    """
    assert probabilistic_sharpe_ratio(sr, 0.0, 1.0, 0.0, 3.0) == pytest.approx(0.5, abs=1e-14)
    assert minimum_track_record_length(0.3, 0.1, 0.0, 3.0, 0.5) == pytest.approx(1.0, abs=1e-14)


@pytest.mark.parametrize("aplatissement", [0.0, -1.0, 0.9999])
def test_le_module_refuse_un_aplatissement_excedentaire(aplatissement: float) -> None:
    """Un aplatissement sous 1 trahit la mauvaise convention, et lève.

    Aucune loi de probabilité n'a un aplatissement non excédentaire inférieur à
    1, cette borne étant atteinte par la loi de Bernoulli symétrique. Une valeur
    plus basse signale presque toujours un aplatissement EXCÉDENTAIRE passé par
    erreur, la faute que la documentation du module désigne comme la plus
    fréquente.
    """
    with pytest.raises(DataQualityError, match="NON excédentaire"):
        sharpe_variance_term(0.1, 0.0, aplatissement)


def test_le_module_refuse_un_couple_de_moments_impossible() -> None:
    """Un aplatissement sous le carré de l'asymétrie plus un mène à une variance nulle.

    Toute loi vérifie que l'aplatissement non excédentaire dépasse le carré de
    l'asymétrie plus un. Quand cette inégalité est violée, le facteur de
    variance peut s'annuler ou devenir négatif, et le PSR n'a plus de sens. Le
    cas construit ici, asymétrie 4 et aplatissement 5, viole l'inégalité, et le
    Sharpe choisi annule exactement le facteur.
    """
    asymetrie, aplatissement = 4.0, 5.0
    assert aplatissement < asymetrie**2 + 1.0
    # Le facteur 1 - 4 x SR + SR^2 s'annule pour SR = 2 - racine(3) = 0,267949.
    sr_racine = 2.0 - math.sqrt(3.0)
    with pytest.raises(DataQualityError, match="non positif"):
        sharpe_variance_term(sr_racine, asymetrie, aplatissement)


@pytest.mark.parametrize("moment", [math.nan, math.inf, -math.inf])
def test_le_module_refuse_un_moment_non_fini(moment: float) -> None:
    """Un moment non fini se refuse, plutôt que de produire un NaN silencieux."""
    with pytest.raises(DataQualityError):
        sharpe_variance_term(0.1, moment, 5.0)
    with pytest.raises(DataQualityError):
        sharpe_variance_term(0.1, 0.0, moment)


@pytest.mark.parametrize("confiance", [0.0, 1.0, -0.1, 1.5])
def test_la_longueur_minimale_refuse_un_niveau_de_confiance_hors_bornes(confiance: float) -> None:
    """Un niveau de confiance hors de l'intervalle ouvert n'a pas de quantile fini."""
    with pytest.raises(ValueError, match="niveau de confiance"):
        minimum_track_record_length(0.2, 0.05, 0.0, 3.0, confiance)


@pytest.mark.parametrize(("sr", "repere"), [(0.05, 0.05), (0.02, 0.10), (-0.3, 0.0)])
def test_la_longueur_minimale_refuse_un_sharpe_sous_le_repere(sr: float, repere: float) -> None:
    """Quand le Sharpe ne dépasse pas le repère, aucun historique ne suffit.

    Le module lève plutôt que de rendre un nombre. Rendre une longueur positive
    par le carré du dénominateur ferait croire qu'il suffit d'attendre, alors
    que la conclusion serait de signe opposé.
    """
    with pytest.raises(ValueError, match="ne dépasse pas le repère"):
        minimum_track_record_length(sr, repere, 0.0, 3.0, DEFAULT_CONFIDENCE)


@pytest.mark.parametrize("essais", [0, -1, -100])
def test_le_seuil_refuse_un_nombre_dessais_nul_ou_negatif(essais: int) -> None:
    """Zéro essai n'a pas de maximum, et le module le dit."""
    with pytest.raises(ValueError, match="nombre d'essais"):
        expected_maximum_sharpe(essais, 0.01)


@pytest.mark.parametrize("variance", [-1e-9, -0.5, math.nan])
def test_le_seuil_refuse_une_variance_dessai_impossible(variance: float) -> None:
    """Une variance négative ou non finie se refuse avant tout calcul."""
    with pytest.raises(DataQualityError, match="variance"):
        expected_maximum_sharpe(10, variance)


@pytest.mark.parametrize("sr", [0.0, -0.2])
def test_le_rasage_refuse_un_sharpe_non_positif(sr: float) -> None:
    """Une fraction du Sharpe observé n'a pas de sens si celui-ci n'est pas positif."""
    with pytest.raises(ValueError, match="strictement positif"):
        haircut(sr, 10, 0.01)


def test_une_variance_dessai_nulle_ramene_le_dsr_au_psr() -> None:
    """Sans dispersion entre essais, le seuil vaut la moyenne et rien n'est dégonflé.

    Cas limite exact : la racine de zéro annule le terme de sélection, quel que
    soit le nombre d'essais. Le DSR se confond alors avec le PSR contre la
    moyenne des essais.
    """
    dsr = deflated_sharpe_ratio(0.15, 0.0, 5000, 800.0, -0.4, 6.0)
    psr = probabilistic_sharpe_ratio(0.15, 0.0, 800.0, -0.4, 6.0)
    assert dsr == pytest.approx(psr, abs=1e-14)


@pytest.mark.parametrize("valeur", [math.nan, math.inf, -math.inf])
def test_le_psr_refuse_un_sharpe_ou_un_repere_non_fini(valeur: float) -> None:
    """Un Sharpe non fini se refuse, au lieu de traverser le module en NaN.

    Le danger est asymétrique. Un NaN ressort en NaN, et une comparaison au
    seuil de 0,95 le rejette, donc l'erreur va du bon côté. Un infini, lui,
    ressort en 1,0, soit une découverte certaine tirée d'une entrée vide.
    """
    with pytest.raises(DataQualityError, match="pas finie"):
        probabilistic_sharpe_ratio(valeur, 0.0, 500.0, 0.0, 3.0)
    with pytest.raises(DataQualityError, match="pas finie"):
        probabilistic_sharpe_ratio(0.1, valeur, 500.0, 0.0, 3.0)


@pytest.mark.parametrize("valeur", [math.nan, math.inf])
def test_le_psr_refuse_un_nombre_dobservations_non_fini(valeur: float) -> None:
    """Un nombre d'observations infini rendrait un PSR de 1, donc il se refuse.

    Vérité par forme fermée : la fonction de répartition normale tend vers 1 en
    l'infini. Sans ce refus, un appel dont la longueur d'échantillon est mal
    calculée publierait une certitude.
    """
    with pytest.raises(InsufficientDataError, match="observation"):
        probabilistic_sharpe_ratio(0.1, 0.0, valeur, 0.0, 3.0)


@pytest.mark.parametrize("valeur", [math.nan, math.inf, -math.inf])
def test_la_longueur_minimale_refuse_un_sharpe_non_fini(valeur: float) -> None:
    """Un NaN passe toutes les comparaisons, donc il se refuse avant elles.

    Le garde « le Sharpe observé dépasse-t-il le repère » est une comparaison,
    et toute comparaison à un NaN rend faux. Le NaN franchirait donc ce garde
    sans bruit et ressortirait en longueur non finie.
    """
    with pytest.raises(DataQualityError, match="pas finie"):
        minimum_track_record_length(valeur, 0.0, 0.0, 3.0, DEFAULT_CONFIDENCE)
    with pytest.raises(DataQualityError, match="pas finie"):
        minimum_track_record_length(0.2, valeur, 0.0, 3.0, DEFAULT_CONFIDENCE)


@pytest.mark.parametrize("valeur", [math.nan, math.inf])
def test_le_seuil_refuse_une_ponderation_ou_une_moyenne_non_finie(valeur: float) -> None:
    """La constante de pondération et la moyenne des essais doivent être finies."""
    with pytest.raises(DataQualityError, match="pas finie"):
        expected_maximum_sharpe(10, 0.01, gamma=valeur)
    with pytest.raises(DataQualityError, match="pas finie"):
        expected_maximum_sharpe(10, 0.01, mean_of_trials=valeur)


# --------------------------------------------------------------------------
# 6. Le résultat gelé
# --------------------------------------------------------------------------


def test_le_resultat_porte_ses_intrants_et_ne_bouge_plus() -> None:
    """La classe de résultat reproduit les quatre sorties et refuse toute retouche.

    Les quatre champs calculés sont comparés aux fonctions libres, appelées
    séparément. Le gel est vérifié par une tentative d'écriture.
    """
    resultat = DeflatedSharpeResult.from_inputs(
        PAPER_SR, PAPER_TRIAL_VARIANCE, 100, PAPER_N_OBS, PAPER_SKEW, PAPER_KURTOSIS
    )
    assert resultat.observed_sr == PAPER_SR
    assert resultat.n_trials == 100
    assert resultat.gamma == EULER_MASCHERONI
    assert resultat.expected_maximum_sr == expected_maximum_sharpe(100, PAPER_TRIAL_VARIANCE)
    assert resultat.deflated_sharpe == deflated_sharpe_ratio(
        PAPER_SR, PAPER_TRIAL_VARIANCE, 100, PAPER_N_OBS, PAPER_SKEW, PAPER_KURTOSIS
    )
    assert resultat.probabilistic_sharpe_vs_zero == probabilistic_sharpe_ratio(
        PAPER_SR, 0.0, PAPER_N_OBS, PAPER_SKEW, PAPER_KURTOSIS
    )
    assert resultat.haircut_fraction == haircut(PAPER_SR, 100, PAPER_TRIAL_VARIANCE)
    assert resultat.deflated_sharpe < resultat.probabilistic_sharpe_vs_zero
    with pytest.raises(AttributeError):
        resultat.deflated_sharpe = 0.99  # type: ignore[misc]


# --------------------------------------------------------------------------
# 7. Les propriétés, par hypothesis
# --------------------------------------------------------------------------

_sharpes = st.floats(min_value=-3.0, max_value=3.0, allow_nan=False, allow_infinity=False)
_asymetries = st.floats(min_value=-3.0, max_value=3.0, allow_nan=False, allow_infinity=False)
_marges = st.floats(min_value=0.1, max_value=20.0, allow_nan=False, allow_infinity=False)
_observations = st.floats(min_value=1.0, max_value=1e6, allow_nan=False, allow_infinity=False)


@given(sr=_sharpes, repere=_sharpes, asymetrie=_asymetries, marge=_marges, observations=_observations)
@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
def test_propriete_le_psr_est_une_probabilite(
    sr: float, repere: float, asymetrie: float, marge: float, observations: float
) -> None:
    """Le PSR reste dans zéro un et suit le signe de l'écart au repère.

    Propriété mathématique : la fonction de répartition normale est à valeurs
    dans zéro un et strictement croissante. L'aplatissement est construit
    au-dessus de la borne du carré de l'asymétrie plus un, ce qui garantit un
    facteur de variance strictement positif.
    """
    aplatissement = asymetrie**2 + 1.0 + marge
    valeur = probabilistic_sharpe_ratio(sr, repere, observations, asymetrie, aplatissement)
    assert 0.0 <= valeur <= 1.0
    if sr > repere:
        assert valeur >= 0.5
    elif sr < repere:
        assert valeur <= 0.5
    else:
        assert valeur == pytest.approx(0.5, abs=1e-12)


@given(sr=_sharpes, asymetrie=_asymetries, marge=_marges)
@settings(max_examples=200)
def test_propriete_le_facteur_de_variance_est_positif_sous_la_borne(
    sr: float, asymetrie: float, marge: float
) -> None:
    """Le facteur de variance reste positif dès que les moments sont possibles.

    Propriété mathématique : le discriminant du polynôme en Sharpe vaut
    asymétrie au carré moins aplatissement plus un. Il est négatif ou nul dès
    que l'aplatissement dépasse le carré de l'asymétrie plus un, donc le
    polynôme, de coefficient dominant positif, ne s'annule jamais.
    """
    aplatissement = asymetrie**2 + 1.0 + marge
    assert sharpe_variance_term(sr, asymetrie, aplatissement) > 0.0


@given(
    essais=st.integers(min_value=2, max_value=100_000),
    supplement=st.integers(min_value=1, max_value=50_000),
    variance=st.floats(min_value=1e-6, max_value=4.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=200)
def test_propriete_le_seuil_croit_strictement_avec_les_essais(
    essais: int, supplement: int, variance: float
) -> None:
    """Le seuil de sélection croît strictement avec le nombre d'essais.

    Propriété mathématique : les deux quantiles normaux qui composent le seuil
    sont strictement croissants en N, et leurs poids sont positifs et somment
    à 1.
    """
    petit = expected_maximum_sharpe(essais, variance)
    grand = expected_maximum_sharpe(essais + supplement, variance)
    assert grand > petit


@given(
    sr=st.floats(min_value=0.02, max_value=2.0, allow_nan=False, allow_infinity=False),
    ecart=st.floats(min_value=0.01, max_value=1.0, allow_nan=False, allow_infinity=False),
    asymetrie=_asymetries,
    marge=_marges,
    confiance=st.floats(min_value=0.51, max_value=0.999, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=300)
def test_propriete_laller_retour_est_exact_partout(
    sr: float, ecart: float, asymetrie: float, marge: float, confiance: float
) -> None:
    """L'aller-retour longueur minimale puis PSR redonne le niveau de confiance.

    Identité algébrique exacte, vérifiée sur trois cents cas tirés. La tolérance
    relative de 1e-10 couvre le seul arrondi de la double précision.
    """
    aplatissement = asymetrie**2 + 1.0 + marge
    longueur = minimum_track_record_length(sr, sr - ecart, asymetrie, aplatissement, confiance)
    assert longueur > MIN_OBSERVATIONS
    retour = probabilistic_sharpe_ratio(sr, sr - ecart, longueur, asymetrie, aplatissement)
    assert retour == pytest.approx(confiance, rel=1e-10)

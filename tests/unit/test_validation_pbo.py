"""Contrôles du module ``quantlab.validation.pbo``.

Chaque valeur attendue vient d'une source déclarée en commentaire, jamais de la
sortie du code. Les quatre sources admises sont le calcul à la main, l'identité
mathématique, la valeur publiée et l'implémentation indépendante.
"""

from __future__ import annotations

import math

import hypothesis.strategies as st
import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from scipy.stats import pearsonr

from quantlab.core.determinism import child_generators
from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.types import Frequency
from quantlab.validation.pbo import (
    CSCVResult,
    combinatorially_symmetric_cv,
    logits,
    number_of_partitions,
    performance_degradation,
    probability_of_backtest_overfitting,
    sharpe_performance,
    stochastic_dominance,
)


def _mean_performance(block: pd.DataFrame) -> np.ndarray:
    """Note un bloc par la moyenne arithmétique de chaque colonne.

    Cette mesure sert partout où un test s'appuie sur une identité exacte. La
    moyenne est additive, donc la performance d'une moitié et celle de son
    complément somment à deux fois la performance plein échantillon, ce qui
    donne des valeurs attendues en forme fermée.
    """
    return block.to_numpy().mean(axis=0)


def _hand_matrix() -> pd.DataFrame:
    """Rend le tableau de quatre périodes et trois configurations calculé à la main.

    Les valeurs sont choisies pour que les six partitions ne produisent aucun ex
    aequo, ni dans l'échantillon ni dehors.
    """
    return pd.DataFrame(
        {
            "A": [8.0, 0.0, 1.0, 2.0],
            "B": [1.0, 5.0, 0.0, 8.0],
            "C": [0.0, 2.0, 7.0, 3.0],
        }
    )


def _noise_matrix(generator: np.random.Generator, n_periods: int, n_configurations: int) -> pd.DataFrame:
    """Rend un tableau de gains purement aléatoires, sans aucune configuration meilleure."""
    values = generator.normal(0.0, 0.01, size=(n_periods, n_configurations))
    return pd.DataFrame(values, columns=[f"config_{i:02d}" for i in range(n_configurations)])


# ---------------------------------------------------------------------------
# Le nombre de partitions et les gardes
# ---------------------------------------------------------------------------


def test_le_nombre_de_partitions_vaut_le_coefficient_binomial() -> None:
    """C(S, S/2) pour S = 4, 6 et 8, calculé à la main.

    Source : calcul à la main. C(4,2) = (4 x 3) / (2 x 1) = 6.
    C(6,3) = (6 x 5 x 4) / (3 x 2 x 1) = 20.
    C(8,4) = (8 x 7 x 6 x 5) / (4 x 3 x 2 x 1) = 1680 / 24 = 70.
    """
    assert number_of_partitions(4) == 6
    assert number_of_partitions(6) == 20
    assert number_of_partitions(8) == 70


def test_le_choix_de_larticle_donne_douze_mille_huit_cent_soixante_dix() -> None:
    """S = 16 donne 12 870 partitions, et non les 12 780 imprimés dans le manuscrit.

    Source : implémentation indépendante, ``math.comb`` de la bibliothèque
    standard. Le manuscrit déposé sur davidhbailey.com écrit 12 780, ce qui est
    une transposition de chiffres.
    """
    assert number_of_partitions(16) == math.comb(16, 8)
    assert number_of_partitions(16) == 12870


def test_le_nombre_de_partitions_egale_le_nombre_dessais_produits() -> None:
    """La procédure produit exactement C(S, S/2) essais.

    Source : identité mathématique, la même que le test précédent, vérifiée ici
    sur le tableau réellement rendu plutôt que sur la formule seule.
    """
    generator = child_generators(20260901, 1)[0]
    matrix = _noise_matrix(generator, n_periods=240, n_configurations=6)
    for n_splits in (4, 6, 8):
        result = combinatorially_symmetric_cv(matrix, n_splits, performance=_mean_performance)
        assert result.n_partitions == number_of_partitions(n_splits)
        assert len(result.trials) == number_of_partitions(n_splits)


@pytest.mark.parametrize("n_splits", [3, 5, 7, 15])
def test_un_nombre_impair_de_blocs_leve_une_erreur(n_splits: int) -> None:
    """Deux moitiés de taille égale exigent un nombre pair de blocs.

    Source : identité mathématique, S/2 n'est pas entier quand S est impair.
    """
    with pytest.raises(ConfigError, match="PAIR"):
        number_of_partitions(n_splits)
    generator = child_generators(20260901, 1)[0]
    matrix = _noise_matrix(generator, n_periods=120, n_configurations=4)
    with pytest.raises(ConfigError, match="PAIR"):
        combinatorially_symmetric_cv(matrix, n_splits, performance=_mean_performance)


@pytest.mark.parametrize("n_splits", [0, 1, -2])
def test_moins_de_deux_blocs_leve_une_erreur(n_splits: int) -> None:
    """Une partition en deux moitiés exige au moins deux blocs.

    Source : calcul à la main, un seul bloc ne se coupe pas en deux moitiés.
    """
    with pytest.raises(ConfigError, match="au moins 2"):
        number_of_partitions(n_splits)


# ---------------------------------------------------------------------------
# La procédure elle-même, contre un calcul à la main
# ---------------------------------------------------------------------------


def test_la_procedure_reproduit_le_calcul_a_la_main() -> None:
    """Les six partitions du tableau à la main, une par une.

    Source : calcul à la main. Les quatre blocs valent une période chacun, donc
    la moyenne d'une moitié est la demi-somme de ses deux périodes.
    Configuration A : 8, 0, 1, 2. Configuration B : 1, 5, 0, 8.
    Configuration C : 0, 2, 7, 3.
    Moitié (0,1) : A = 4,0 ; B = 3,0 ; C = 1,0.
    Moitié (0,2) : A = 4,5 ; B = 0,5 ; C = 3,5.
    Moitié (0,3) : A = 5,0 ; B = 4,5 ; C = 1,5.
    Moitié (1,2) : A = 0,5 ; B = 2,5 ; C = 4,5.
    Moitié (1,3) : A = 1,0 ; B = 6,5 ; C = 2,5.
    Moitié (2,3) : A = 1,5 ; B = 4,0 ; C = 5,0.
    """
    result = combinatorially_symmetric_cv(
        _hand_matrix(), 4, performance=_mean_performance, min_rows_per_split=1
    )
    attendu = pd.DataFrame(
        [
            [4.0, 3.0, 1.0],
            [4.5, 0.5, 3.5],
            [5.0, 4.5, 1.5],
            [0.5, 2.5, 4.5],
            [1.0, 6.5, 2.5],
            [1.5, 4.0, 5.0],
        ],
        columns=["A", "B", "C"],
    )
    np.testing.assert_allclose(result.in_sample_performance.to_numpy(), attendu.to_numpy())
    # Les compléments : (0,1) va avec (2,3), (0,2) avec (1,3), (0,3) avec (1,2).
    ordre_complementaire = [5, 4, 3, 2, 1, 0]
    np.testing.assert_allclose(
        result.out_of_sample_performance.to_numpy(),
        attendu.to_numpy()[ordre_complementaire],
    )
    assert list(result.trials["selected"]) == ["A", "A", "A", "C", "B", "C"]


def test_la_moitie_de_test_est_lechantillon_de_la_partition_complementaire() -> None:
    """La symétrie de la procédure, vérifiée sur toutes les partitions.

    Source : identité mathématique. Chaque moitié sert une fois d'entraînement
    et une fois de test, donc l'ensemble des performances hors échantillon est
    une permutation de l'ensemble des performances dans l'échantillon.
    """
    generator = child_generators(20260901, 1)[0]
    matrix = _noise_matrix(generator, n_periods=180, n_configurations=5)
    result = combinatorially_symmetric_cv(matrix, 6, performance=_mean_performance)
    dans = np.sort(result.in_sample_performance.to_numpy(), axis=0)
    dehors = np.sort(result.out_of_sample_performance.to_numpy(), axis=0)
    np.testing.assert_allclose(dans, dehors)


def test_les_logits_du_calcul_a_la_main_valent_moins_logarithme_de_trois() -> None:
    """Les six partitions du tableau à la main placent toutes la retenue au dernier rang.

    Source : calcul à la main. Avec N = 3, le rang 1 donne un rang relatif de
    1 / (3 + 1) = 0,25, dont le logit vaut ln(0,25 / 0,75) = -ln 3.
    """
    resultat = probability_of_backtest_overfitting(
        _hand_matrix(), 4, performance=_mean_performance, min_rows_per_split=1
    )
    np.testing.assert_allclose(resultat.logits.to_numpy(), -math.log(3.0))
    assert resultat.pbo == 1.0
    assert resultat.median_rank == 1.0
    assert resultat.median_relative_rank == 0.25
    assert resultat.n_partitions == 6


def test_la_convention_d_egalite_compte_le_logit_nul_comme_un_surapprentissage() -> None:
    """L'intégrale de l'article est fermée en zéro, et le cas d'égalité le prouve.

    Source : calcul à la main. Deux colonnes portent exactement les mêmes
    valeurs. Dans chaque partition, les deux performances sont égales, donc les
    rangs ex aequo valent tous deux (1 + 2) / 2 = 1,5. Le rang relatif vaut
    1,5 / (2 + 1) = 0,5 et le logit ln(1) = 0 exactement.

    Ce que le test verrouille. L'article définit la probabilité par
    l'intégrale de moins l'infini à zéro, borne comprise, donc les six logits
    nuls comptent et la probabilité vaut 1. Une comparaison stricte rendrait 0.
    Les deux verdicts sont opposés, et aucun autre test du fichier ne les
    sépare : la vérification a été faite en réintroduisant le défaut.
    """
    matrice = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0], "b": [1.0, 2.0, 3.0, 4.0]})
    resultat = probability_of_backtest_overfitting(
        matrice, 4, performance=_mean_performance, min_rows_per_split=1
    )
    np.testing.assert_allclose(resultat.logits.to_numpy(), 0.0, atol=0.0)
    assert resultat.median_rank == 1.5
    assert resultat.median_relative_rank == 0.5
    assert resultat.pbo == 1.0


def test_la_regression_du_calcul_a_la_main_rend_moins_trente_six_sur_quatre_vingt_neuf() -> None:
    """La pente, la constante et le R2 des six paires retenues.

    Source : calcul à la main sur les six paires du tableau précédent.
    Dans l'échantillon : 4,0 ; 4,5 ; 5,0 ; 4,5 ; 6,5 ; 5,0, de moyenne 59/12.
    Dehors : 1,5 ; 1,0 ; 0,5 ; 1,5 ; 0,5 ; 1,0, de moyenne 1.
    Somme des produits centrés = -3/2. Somme des carrés centrés = 534/144.
    Pente = (-3/2) x (144/534) = -216/534 = -36/89.
    Constante = 1 + (36/89) x (59/12) = 1 + 177/89 = 266/89.
    Somme des carrés centrés de la sortie = 1, donc R2 = (3/2)^2 / (534/144) = 54/89.
    """
    degradation = performance_degradation(
        _hand_matrix(), 4, performance=_mean_performance, min_rows_per_split=1
    )
    assert degradation.slope == pytest.approx(-36 / 89, rel=1e-12)
    assert degradation.intercept == pytest.approx(266 / 89, rel=1e-12)
    assert degradation.r_squared == pytest.approx(54 / 89, rel=1e-12)
    assert degradation.n_pairs == 6
    assert degradation.probability_of_loss == 0.0


# ---------------------------------------------------------------------------
# Le test sous l'hypothèse nulle
# ---------------------------------------------------------------------------


def test_sous_lhypothese_nulle_la_probabilite_vaut_un_demi() -> None:
    """Un tableau de bruit pur rend une probabilité de 0,5.

    Source : identité mathématique. Sous l'hypothèse nulle, les N colonnes sont
    indépendantes et de même loi. Les deux moitiés d'une partition portent des
    lignes disjointes, donc le classement hors échantillon est indépendant du
    classement dans l'échantillon. Le rang hors échantillon de la configuration
    retenue est donc uniforme sur 1, ..., N. Avec N pair, la part des rangs
    situés au plus à (N + 1) / 2, soit au plus N / 2, vaut exactement 1/2.

    Tolérance. La valeur attendue est 0,5 exactement. La moyenne des essais
    porte une erreur type estimée sur les essais eux-mêmes, et la borne retenue
    est de quatre erreurs types. Sous une approximation normale, cette borne
    laisse un risque de fausse alarme sous 1 pour 10 000. La graine est fixée,
    donc le test est déterministe et ce risque ne se réalise qu'une fois pour
    toutes.
    """
    n_essais = 120
    n_configurations = 12  # pair, donc aucun rang ne tombe pile sur la médiane
    generateurs = child_generators(20260901, n_essais)
    valeurs = np.array(
        [
            probability_of_backtest_overfitting(
                _noise_matrix(g, n_periods=240, n_configurations=n_configurations),
                8,
                performance=_mean_performance,
            ).pbo
            for g in generateurs
        ]
    )
    moyenne = valeurs.mean()
    erreur_type = valeurs.std(ddof=1) / math.sqrt(n_essais)
    assert abs(moyenne - 0.5) <= 4.0 * erreur_type, f"moyenne {moyenne:.4f}, erreur type {erreur_type:.4f}"


def test_sous_lhypothese_nulle_le_rang_relatif_median_vaut_un_demi() -> None:
    """Le rang relatif médian tourne autour de 0,5 sous l'hypothèse nulle.

    Source : identité mathématique, la même uniformité des rangs que le test
    précédent. La médiane d'une loi uniforme sur 1, ..., N divisée par N + 1
    vaut (N + 1) / 2 divisé par N + 1, soit 0,5. Tolérance de quatre erreurs
    types, estimées sur les essais.
    """
    n_essais = 60
    generateurs = child_generators(20260902, n_essais)
    valeurs = np.array(
        [
            probability_of_backtest_overfitting(
                _noise_matrix(g, n_periods=240, n_configurations=12),
                8,
                performance=_mean_performance,
            ).median_relative_rank
            for g in generateurs
        ]
    )
    erreur_type = valeurs.std(ddof=1) / math.sqrt(n_essais)
    assert abs(valeurs.mean() - 0.5) <= 4.0 * erreur_type


# ---------------------------------------------------------------------------
# Le test sous une alternative claire
# ---------------------------------------------------------------------------


def test_une_configuration_qui_domine_partout_rend_une_probabilite_nulle() -> None:
    """Une configuration meilleure dans chaque période rend une probabilité de zéro.

    Source : calcul à la main. La configuration dominante gagne dans les deux
    moitiés de chaque partition, puisque sa dérive dépasse l'amplitude du bruit
    sur n'importe quel bloc. Son rang hors échantillon vaut donc N, son rang
    relatif N / (N + 1), et son logit ln N, strictement positif. Aucune
    partition ne compte, donc la probabilité vaut zéro exactement.
    """
    generateur = child_generators(20260903, 1)[0]
    n_configurations = 10
    matrice = _noise_matrix(generateur, n_periods=240, n_configurations=n_configurations)
    matrice.iloc[:, 0] = matrice.iloc[:, 0] + 1.0  # cent fois l'écart type du bruit
    resultat = probability_of_backtest_overfitting(matrice, 8, performance=_mean_performance)
    assert resultat.pbo == 0.0
    assert resultat.median_rank == float(n_configurations)
    np.testing.assert_allclose(resultat.logits.to_numpy(), math.log(n_configurations))


def test_une_configuration_qui_domine_partout_domine_aussi_stochastiquement() -> None:
    """La sélection bat le tirage au sort aux deux ordres quand elle trie vraiment.

    Source : identité mathématique. La configuration retenue est la meilleure
    des N dans chaque partition, donc sa performance dépasse la moyenne des N
    de la même partition, partition par partition. La répartition de la
    première est donc partout à droite de celle de la seconde. La dominance au
    premier ordre entraîne celle au second.
    """
    generateur = child_generators(20260904, 1)[0]
    matrice = _noise_matrix(generateur, n_periods=240, n_configurations=10)
    matrice.iloc[:, 0] = matrice.iloc[:, 0] + 1.0
    dominance = stochastic_dominance(matrice, 8, performance=_mean_performance)
    assert dominance.first_order is True
    assert dominance.second_order is True
    assert dominance.max_cdf_gap > 0.0


def test_les_repartitions_empiriques_reproduisent_le_calcul_a_la_main() -> None:
    """Les deux fonctions de répartition du tableau à la main, point par point.

    Source : calcul à la main, sur les six partitions déjà énumérées.
    La configuration retenue rapporte hors échantillon 1,5 ; 1,0 ; 0,5 ; 1,5 ;
    0,5 et 1,0. Le repère est la moyenne des trois colonnes de la même moitié
    de test, soit 10,5/3 ; 10/3 ; 7,5/3 ; 11/3 ; 8,5/3 et 8/3.
    La grille est la réunion triée des douze valeurs, sans doublon.

    Les deux répartitions se comptent à la main. Celle de la sélection vaut
    2/6 en 0,5, puis 4/6 en 1,0, puis 1 à partir de 1,5. Celle du repère reste
    nulle jusqu'à 2,5, puis monte d'un sixième à chacune de ses six valeurs.

    Le verdict qui suit est un verdict de direction. La sélection est partout
    sous le repère, donc l'écart des répartitions est négatif et aucune
    dominance ne tient. Une inversion du signe de cet écart rendrait au
    contraire les deux verdicts vrais, ce qui a été vérifié en réintroduisant
    le défaut.
    """
    dominance = stochastic_dominance(_hand_matrix(), 4, performance=_mean_performance, min_rows_per_split=1)
    grille_attendue = np.array([0.5, 1.0, 1.5, 2.5, 8 / 3, 17 / 6, 10 / 3, 3.5, 11 / 3])
    np.testing.assert_allclose(dominance.grid, grille_attendue)
    np.testing.assert_allclose(
        dominance.selected_cdf * 6.0, np.array([2.0, 4.0, 6.0, 6.0, 6.0, 6.0, 6.0, 6.0, 6.0])
    )
    np.testing.assert_allclose(
        dominance.benchmark_cdf * 6.0, np.array([0.0, 0.0, 0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    )
    assert dominance.first_order is False
    assert dominance.second_order is False
    assert dominance.max_cdf_gap == 0.0
    assert dominance.n_partitions == 6
    # La courbe du second ordre part de zéro et ne remonte jamais au-dessus.
    assert dominance.second_order_curve[0] == 0.0
    assert dominance.second_order_curve[-1] < 0.0


def test_la_dominance_au_premier_ordre_entraine_celle_au_second() -> None:
    """Le lien logique entre les deux ordres tient sur du bruit comme sur du signal.

    Source : identité mathématique. Si la différence des deux répartitions est
    positive partout, son intégrale de la borne inférieure jusqu'à un point
    quelconque l'est aussi.
    """
    for graine, decalage in ((20260905, 0.0), (20260906, 1.0)):
        generateur = child_generators(graine, 1)[0]
        matrice = _noise_matrix(generateur, n_periods=240, n_configurations=8)
        matrice.iloc[:, 0] = matrice.iloc[:, 0] + decalage
        dominance = stochastic_dominance(matrice, 8, performance=_mean_performance)
        if dominance.first_order:
            assert dominance.second_order


# ---------------------------------------------------------------------------
# La pente de dégradation
# ---------------------------------------------------------------------------


def test_la_pente_vaut_moins_un_quand_une_seule_configuration_est_retenue() -> None:
    """Le mécanisme de bascule, isolé par une identité exacte.

    Source : identité mathématique. Les deux moitiés sont de même taille et la
    mesure est la moyenne arithmétique, donc x + y = 2 m pour la configuration
    retenue, où m est sa moyenne plein échantillon. Quand la même configuration
    gagne dans toutes les partitions, m est une constante et la relation
    y = 2 m - x est une droite de pente -1 exactement, de R2 égal à 1.
    """
    generateur = child_generators(20260907, 1)[0]
    matrice = _noise_matrix(generateur, n_periods=240, n_configurations=6)
    matrice.iloc[:, 0] = matrice.iloc[:, 0] + 1.0
    degradation = performance_degradation(matrice, 8, performance=_mean_performance)
    assert degradation.slope == pytest.approx(-1.0, abs=1e-9)
    assert degradation.r_squared == pytest.approx(1.0, abs=1e-9)


def test_la_pente_sur_toutes_les_configurations_est_positive_sous_la_persistance() -> None:
    """La pente qui sépare les deux régimes, contre sa forme fermée.

    Source : forme fermée. On note x et y les moyennes des deux moitiés d'une
    configuration, puis u = (x + y) / 2 et e = (x - y) / 2. L'identité
    Cov(x, y) = Var(u) - Var(e) est algébrique.

    Les deux variances se calculent sur l'ensemble des paires configuration par
    partition. Var(u) est la variance des moyennes plein échantillon des N
    configurations. Son espérance vaut ((N-1)/N) (tau^2 + sigma^2/T), le
    facteur (N-1)/N venant du diviseur N de la variance de population.
    Var(e) est la variance d'une moitié autour de cette moyenne, d'espérance
    sigma^2/T. La pente attendue vaut donc
    ((N-1)/N (tau^2 + sigma^2/T) - sigma^2/T) divisé par
    ((N-1)/N (tau^2 + sigma^2/T) + sigma^2/T).

    Tolérance. Elle est déclarée en valeur absolue et non en erreurs types.
    L'estimateur des moindres carrés est un rapport de deux moments
    d'échantillon, et l'espérance d'un rapport n'est pas le rapport des
    espérances. Ce biais ne diminue pas avec le nombre d'essais, contrairement
    à l'erreur type. Mesuré le 2026-09-01 sur ce plan exact, il vaut -0,00102,
    pour une erreur type de la moyenne de 0,00034. La borne de 0,003 couvre
    donc le biais plus quatre erreurs types, qui font ensemble 0,00238.

    Ce que la borne ne sépare pas, et c'est déclaré. Le facteur (N-1)/N ne
    déplace la valeur attendue que de 0,0002 dans ce régime, donc ce test ne
    l'atteste pas. Il est atteint par le test d'identité des variances, qui
    est exact.
    """
    n_essais = 20
    n_configurations = 12
    n_periodes = 240
    sigma = 0.01
    tau = 0.02
    generateurs = child_generators(20260908, n_essais)
    pentes = []
    for generateur in generateurs:
        qualite = generateur.normal(0.0, tau, size=n_configurations)
        matrice = _noise_matrix(generateur, n_periodes, n_configurations) + qualite
        pentes.append(
            performance_degradation(matrice, 8, performance=_mean_performance).all_configurations_slope
        )
    part = (n_configurations - 1) / n_configurations
    variance_entre = part * (tau**2 + sigma**2 / n_periodes)
    variance_dedans = sigma**2 / n_periodes
    attendu = (variance_entre - variance_dedans) / (variance_entre + variance_dedans)
    assert np.mean(pentes) == pytest.approx(attendu, abs=0.003)
    assert min(pentes) > 0.0


def test_la_pente_est_negative_quand_la_performance_est_purement_bruitee() -> None:
    """Sous le bruit pur, les deux pentes sont négatives EN MOYENNE.

    Source : identité mathématique et mesure. La sélection par le maximum
    achète de la performance dans l'échantillon au prix de la moitié
    complémentaire, ce que l'article nomme l'effet de compensation (section
    3.2). L'identité Cov(x, y) = Var(u) - Var(e) donne alors une covariance
    négative, puisque la sélection gonfle Var(e) sans rien ajouter à Var(u).
    La borne retenue est de trois erreurs types de la moyenne des essais, et
    la graine est fixée.

    Le test porte sur la moyenne, et pas sur chaque tirage. Mesuré le
    2026-09-01 sur ce plan exact, la pente de l'article est positive dans 3,3 %
    des 120 tirages, son maximum vaut +0,57 et son minimum -1,67. Une
    assertion tirage par tirage serait donc fausse.
    """
    n_essais = 120
    generateurs = child_generators(20260909, n_essais)
    retenues = []
    toutes = []
    for generateur in generateurs:
        matrice = _noise_matrix(generateur, n_periods=240, n_configurations=12)
        degradation = performance_degradation(matrice, 8, performance=_mean_performance)
        retenues.append(degradation.slope)
        toutes.append(degradation.all_configurations_slope)
    for serie in (np.array(retenues), np.array(toutes)):
        erreur_type = serie.std(ddof=1) / math.sqrt(n_essais)
        assert serie.mean() + 3.0 * erreur_type < 0.0


def test_la_pente_suit_lidentite_des_variances() -> None:
    """La pente rendue est exactement celle qu'impose la décomposition.

    Source : identité mathématique. On pose u = (x + y) / 2 et e = (x - y) / 2,
    donc x = u + e et y = u - e. Il vient Cov(x, y) = Var(u) - Var(e), et la
    pente des moindres carrés vaut (Var(u) - Var(e)) / Var(x). L'identité est
    algébrique et ne suppose ni modèle ni loi. Elle est vérifiée ici sur les
    seules colonnes du tableau d'essais, sans repasser par la régression.

    Elle donne aussi la condition exacte du seuil de moins un :
    pente + 1 = 2 Cov(u, x) / Var(x). La pente descend donc sous moins un
    quand la sélection par le maximum rend Cov(u, x) négative, ce qui arrive
    sous le bruit pur. Mesuré le 2026-09-01 sur ce plan, la plus basse des 120
    pentes vaut -1,67.
    """
    generateur = child_generators(20260918, 1)[0]
    matrice = _noise_matrix(generateur, n_periods=240, n_configurations=12)
    result = combinatorially_symmetric_cv(matrice, 8, performance=_mean_performance)
    dans = result.trials["in_sample_performance"].to_numpy()
    dehors = result.trials["out_of_sample_performance"].to_numpy()
    milieu = (dans + dehors) / 2.0
    ecart = (dans - dehors) / 2.0
    attendu = (milieu.var() - ecart.var()) / dans.var()
    pente = performance_degradation(result).slope
    assert pente == pytest.approx(attendu, rel=1e-12)
    assert pente + 1.0 == pytest.approx(2.0 * np.cov(milieu, dans, bias=True)[0, 1] / dans.var(), rel=1e-9)


def test_la_pente_sur_toutes_les_configurations_est_une_correlation() -> None:
    """La pente ajoutée par le module est exactement une corrélation de Pearson.

    Source : identité mathématique, puis implémentation indépendante.

    L'identité d'abord. La symétrie de la procédure fait que l'ensemble des
    performances hors échantillon est une permutation de l'ensemble des
    performances dans l'échantillon. Les deux colonnes mises en commun ont donc
    la MÊME variance, au bit près. La pente des moindres carrés, qui vaut
    Cov(x, y) / Var(x), se confond alors avec Cov(x, y) divisé par la racine du
    produit des deux variances, c'est-à-dire avec la corrélation.

    L'implémentation indépendante ensuite. La valeur attendue vient de
    ``scipy.stats.pearsonr``, qui ne partage aucune ligne avec le module.

    Trois conséquences, toutes vérifiées ici. La pente groupée est bornée entre
    moins un et un, ce que la pente de l'article n'est pas. Elle ne dépend pas
    du sens de la régression, donc inverser l'échantillon et le hors
    échantillon ne la change pas. Et elle diffère de la pente de l'article sur
    le même tableau, puisque celle-ci ne garde que les paires retenues.
    """
    generateur = child_generators(20260919, 1)[0]
    qualite = generateur.normal(0.0, 0.02, size=8)
    matrice = _noise_matrix(generateur, n_periods=240, n_configurations=8) + qualite
    result = combinatorially_symmetric_cv(matrice, 6, performance=_mean_performance)
    dans = result.in_sample_performance.to_numpy().ravel()
    dehors = result.out_of_sample_performance.to_numpy().ravel()
    # La permutation, donc l'égalité des variances, est vérifiée avant de s'en servir.
    np.testing.assert_allclose(np.sort(dans), np.sort(dehors), rtol=0.0, atol=0.0)
    assert dans.var() == dehors.var()

    attendu = pearsonr(dans, dehors).statistic
    degradation = performance_degradation(result)
    assert degradation.all_configurations_slope == pytest.approx(attendu, rel=1e-12)
    assert abs(degradation.all_configurations_slope) <= 1.0
    assert degradation.all_configurations_slope != pytest.approx(degradation.slope, rel=1e-3)


# ---------------------------------------------------------------------------
# Le logit
# ---------------------------------------------------------------------------


def test_le_logit_du_rang_median_est_nul() -> None:
    """Le point neutre de la transformation.

    Source : calcul à la main. Avec N = 9, le rang médian vaut 5, donc le rang
    relatif 5 / 10 = 0,5 et le logit ln(1) = 0.
    """
    assert logits([5.0], 9)[0] == pytest.approx(0.0, abs=1e-15)


def test_le_logit_des_rangs_extremes_est_symetrique() -> None:
    """Le premier et le dernier rang donnent des logits opposés.

    Source : calcul à la main. Avec N = 4, le rang 1 donne 1/5 et le rang 4
    donne 4/5, dont les logits valent ln(1/4) = -ln 4 et ln 4.
    """
    valeurs = logits([1.0, 4.0], 4)
    assert valeurs[0] == pytest.approx(-math.log(4.0))
    assert valeurs[1] == pytest.approx(math.log(4.0))


def test_le_logit_refuse_un_rang_relatif_hors_de_lintervalle_ouvert() -> None:
    """Sans nombre de configurations, l'entrée doit être un rang relatif."""
    with pytest.raises(ConfigError, match="strictement entre 0 et 1"):
        logits([0.0, 0.5])
    with pytest.raises(ConfigError, match="strictement entre 0 et 1"):
        logits([0.5, 1.0])


def test_le_logit_refuse_un_rang_absolu_hors_bornes() -> None:
    """Avec un nombre de configurations, l'entrée doit être un rang entre 1 et N."""
    with pytest.raises(ConfigError, match="entre 1 et 5"):
        logits([0.0, 3.0], 5)
    with pytest.raises(ConfigError, match="entre 1 et 5"):
        logits([6.0], 5)


def test_le_logit_refuse_une_entree_vide_ou_une_seule_configuration() -> None:
    """Les deux cas dégénérés de la transformation."""
    with pytest.raises(ConfigError, match="vide"):
        logits([])
    with pytest.raises(ConfigError, match="au moins 2"):
        logits([1.0], 1)


def test_le_logit_refuse_une_valeur_non_finie() -> None:
    """Un rang manquant n'a pas de logit."""
    with pytest.raises(DataQualityError, match="non finie"):
        logits([0.5, np.nan])


@settings(max_examples=200, deadline=None)
@given(
    rang=st.integers(min_value=1, max_value=50),
    n_configurations=st.integers(min_value=2, max_value=50),
)
def test_propriete_le_logit_est_antisymetrique(rang: int, n_configurations: int) -> None:
    """Le logit du rang miroir est l'opposé du logit du rang.

    Source : identité mathématique. Le rang r a pour rang relatif
    r / (N + 1) et le rang miroir N + 1 - r a pour rang relatif
    1 - r / (N + 1). Or ln(w / (1 - w)) change de signe quand w devient 1 - w.
    """
    rang = min(rang, n_configurations)
    miroir = n_configurations + 1 - rang
    direct = logits([float(rang)], n_configurations)[0]
    inverse = logits([float(miroir)], n_configurations)[0]
    assert direct == pytest.approx(-inverse, abs=1e-12)


@settings(max_examples=200, deadline=None)
@given(rangs=st.lists(st.floats(min_value=0.001, max_value=0.999), min_size=2, max_size=30, unique=True))
def test_propriete_le_logit_est_strictement_croissant(rangs: list[float]) -> None:
    """Le logit conserve l'ordre des rangs relatifs.

    Source : identité mathématique. La dérivée de ln(w / (1 - w)) vaut
    1 / (w (1 - w)), strictement positive sur l'intervalle ouvert de 0 à 1.
    """
    tries = np.sort(np.array(rangs))
    valeurs = logits(tries)
    assert np.all(np.diff(valeurs) > 0.0)


# ---------------------------------------------------------------------------
# Les gardes du tableau d'entrée
# ---------------------------------------------------------------------------


def test_un_tableau_qui_nest_pas_un_dataframe_est_refuse() -> None:
    """Le contrat d'entrée est explicite plutôt que deviné."""
    generateur = child_generators(20260910, 1)[0]
    with pytest.raises(ConfigError, match="DataFrame"):
        combinatorially_symmetric_cv(generateur.normal(size=(80, 4)), 4)


def test_une_seule_configuration_est_refusee() -> None:
    """Classer une colonne unique n'a pas de sens : la sélection est vide de contenu."""
    matrice = pd.DataFrame({"seule": np.arange(80, dtype=float)})
    with pytest.raises(ConfigError, match="au moins 2 configurations"):
        combinatorially_symmetric_cv(matrice, 4, performance=_mean_performance)


def test_une_valeur_manquante_est_refusee() -> None:
    """Un trou dans le tableau se signale au lieu de se propager en silence."""
    generateur = child_generators(20260911, 1)[0]
    matrice = _noise_matrix(generateur, n_periods=80, n_configurations=3)
    matrice.iloc[3, 1] = np.nan
    with pytest.raises(DataQualityError, match="manquante"):
        combinatorially_symmetric_cv(matrice, 4, performance=_mean_performance)


def test_des_colonnes_en_double_sont_refusees() -> None:
    """Deux configurations de même nom ne se distinguent plus dans le classement."""
    valeurs = np.arange(24, dtype=float).reshape(8, 3)
    matrice = pd.DataFrame(valeurs, columns=["a", "a", "b"])
    with pytest.raises(ConfigError, match="uniques"):
        combinatorially_symmetric_cv(matrice, 4, performance=_mean_performance)


def test_trop_peu_de_lignes_par_bloc_leve_une_erreur() -> None:
    """Un bloc trop court ne porte pas la mesure demandée."""
    generateur = child_generators(20260912, 1)[0]
    matrice = _noise_matrix(generateur, n_periods=6, n_configurations=3)
    with pytest.raises(InsufficientDataError, match="minimum"):
        combinatorially_symmetric_cv(matrice, 8, performance=_mean_performance)


def test_les_lignes_de_queue_sont_ecartees_et_comptees() -> None:
    """Les blocs sont de dimensions égales, donc le reste de la division part.

    Source : calcul à la main. 250 lignes découpées en 8 blocs donnent 31
    lignes par bloc, soit 248 lignes utilisées et 2 écartées.
    """
    generateur = child_generators(20260913, 1)[0]
    matrice = _noise_matrix(generateur, n_periods=250, n_configurations=4)
    result = combinatorially_symmetric_cv(matrice, 8, performance=_mean_performance)
    assert result.rows_per_split == 31
    assert result.n_observations == 248
    assert result.n_dropped_rows == 2


def test_une_fonction_de_performance_de_mauvaise_forme_est_refusee() -> None:
    """La fonction doit rendre une valeur par configuration, pas une de plus."""
    generateur = child_generators(20260914, 1)[0]
    matrice = _noise_matrix(generateur, n_periods=80, n_configurations=3)
    with pytest.raises(ConfigError, match="3 valeurs"):
        combinatorially_symmetric_cv(matrice, 4, performance=lambda block: np.zeros(2))


# ---------------------------------------------------------------------------
# La réutilisation d'un résultat déjà calculé
# ---------------------------------------------------------------------------


def test_un_resultat_deja_calcule_est_reutilise_tel_quel() -> None:
    """Les quatre statistiques lisent le même passage, sans le recalculer.

    Source : identité mathématique. Les statistiques sont des fonctions
    déterministes du résultat, donc les passer par le tableau ou par le
    résultat doit rendre exactement les mêmes nombres.
    """
    generateur = child_generators(20260915, 1)[0]
    matrice = _noise_matrix(generateur, n_periods=240, n_configurations=6)
    result = combinatorially_symmetric_cv(matrice, 6, performance=_mean_performance)
    assert isinstance(result, CSCVResult)
    direct = probability_of_backtest_overfitting(matrice, 6, performance=_mean_performance)
    reutilise = probability_of_backtest_overfitting(result)
    assert direct.pbo == reutilise.pbo
    assert (
        performance_degradation(matrice, 6, performance=_mean_performance).slope
        == performance_degradation(result).slope
    )
    assert (
        stochastic_dominance(matrice, 6, performance=_mean_performance).first_order
        == stochastic_dominance(result).first_order
    )


# ---------------------------------------------------------------------------
# La mesure de performance par défaut
# ---------------------------------------------------------------------------


def test_la_mesure_par_defaut_est_le_ratio_de_sharpe_du_laboratoire() -> None:
    """La fonction par défaut rend le ratio de Sharpe, et la formule le confirme.

    Source : deux sources indépendantes l'une de l'autre. La première est la
    forme fermée, moyenne divisée par écart type d'échantillon à ddof = 1, le
    tout multiplié par la racine de 252. Elle ne passe par aucun code du
    laboratoire. La seconde est la fonction publique
    ``quantlab.analytics.ratios.sharpe_ratio``, seule implémentation du ratio
    dans le dépôt, appelée colonne par colonne.

    Pourquoi les deux. La forme fermée atteste que la grandeur rendue est bien
    un ratio de Sharpe annualisé, ce qu'une comparaison au seul appel du
    laboratoire ne prouverait pas. L'égalité au bit près avec la fonction
    publique atteste, elle, que le module ne réimplémente rien.
    """
    from quantlab.analytics.ratios import sharpe_ratio

    generateur = child_generators(20260916, 1)[0]
    matrice = _noise_matrix(generateur, n_periods=60, n_configurations=4)
    obtenu = sharpe_performance(matrice, frequency=Frequency.DAILY)

    facteur = math.sqrt(Frequency.DAILY.periods_per_year)
    ferme = np.array(
        [matrice[c].mean() / matrice[c].std(ddof=1) * facteur for c in matrice.columns],
        dtype=float,
    )
    np.testing.assert_allclose(obtenu, ferme, rtol=1e-12, atol=0.0)

    laboratoire = [sharpe_ratio(matrice[c], frequency=Frequency.DAILY) for c in matrice.columns]
    np.testing.assert_allclose(obtenu, laboratoire, rtol=0.0, atol=0.0)

    # Le degré de liberté compte : ddof = 0 gonfle le ratio de sqrt(n / (n - 1)).
    brut = sharpe_performance(matrice, frequency=Frequency.DAILY, ddof=0)
    np.testing.assert_allclose(brut, obtenu * math.sqrt(60 / 59), rtol=1e-12)


def test_lannualisation_ne_change_aucun_classement() -> None:
    """Multiplier par une constante positive laisse les rangs, donc la probabilité.

    Source : identité mathématique. L'annualisation multiplie chaque ratio par
    la racine du nombre de périodes par an, la même pour toutes les colonnes.
    """
    generateur = child_generators(20260917, 1)[0]
    matrice = _noise_matrix(generateur, n_periods=240, n_configurations=6)
    annualise = probability_of_backtest_overfitting(matrice, 6, frequency=Frequency.DAILY)
    brut = probability_of_backtest_overfitting(
        matrice,
        6,
        performance=lambda block: sharpe_performance(block, frequency=Frequency.DAILY, annualize=False),
    )
    assert annualise.pbo == brut.pbo
    np.testing.assert_allclose(annualise.logits.to_numpy(), brut.logits.to_numpy())

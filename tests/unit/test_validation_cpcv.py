"""Contrôles de ``quantlab.validation.cpcv``.

Aucune valeur attendue de ce fichier ne vient de la sortie du code. Chacune
porte sa source en commentaire : (a) calcul à la main, (b) identité
mathématique, (c) valeur publiée, (d) implémentation indépendante.

La fonction ``test_paths`` du module est importée sous un autre nom. Sans cela,
pytest la ramasserait comme un test et réclamerait deux fixtures qui n'existent
pas.
"""

from __future__ import annotations

import math
from collections.abc import Callable

import hypothesis.strategies as st
import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings

from quantlab.analytics.ratios import sharpe_ratio
from quantlab.core.config import ValidationConfig
from quantlab.core.determinism import child_generators
from quantlab.core.errors import ConfigError, InsufficientDataError
from quantlab.core.types import Frequency
from quantlab.validation.cpcv import (
    CONVENTION_DIFFERENCES,
    CombinatorialPurgedCV,
    PerformanceDistribution,
    TestPath,
    compare_with_skfolio,
    cpcv_performance_distribution,
    optimal_folds,
    skfolio_cpcv,
)
from quantlab.validation.cpcv import test_paths as build_test_paths

SEED = 20260901


def _matrix(n_samples: int, n_features: int = 1) -> np.ndarray:
    """Rend un intrant de la bonne longueur, dont le contenu n'importe pas."""
    return np.arange(float(n_samples * n_features)).reshape(n_samples, n_features)


def _config(**overrides: object) -> ValidationConfig:
    """Rend une configuration de validation valide, surchargeable."""
    base: dict[str, object] = {
        "train_end": "2015-12-31",
        "validation_end": "2019-12-31",
        "n_folds": 6,
        "n_test_folds": 2,
        "purge_periods": 3,
        "embargo_periods": 2,
    }
    base.update(overrides)
    return ValidationConfig(**base)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# Le décompte des combinaisons et des chemins
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("n_folds", "n_test_folds", "n_splits", "n_paths"),
    [
        # (a) Calculs à la main, un par ligne.
        # N=6, k=2 : C(6,2) = (6x5)/2 = 15 combinaisons ; chemins = 15 x 2 / 6 = 5.
        (6, 2, 15, 5),
        # N=10, k=2 : C(10,2) = (10x9)/2 = 45 ; chemins = 45 x 2 / 10 = 9.
        (10, 2, 45, 9),
        # N=5, k=3 : C(5,3) = (5x4x3)/6 = 10 ; chemins = 10 x 3 / 5 = 6.
        (5, 3, 10, 6),
        # N=4, k=2 : C(4,2) = 6 ; chemins = 6 x 2 / 4 = 3.
        (4, 2, 6, 3),
        # N=10, k=8 : C(10,8) = C(10,2) = 45 ; chemins = 45 x 8 / 10 = 36.
        (10, 8, 45, 36),
        # N=3, k=1 : C(3,1) = 3 ; chemins = 3 x 1 / 3 = 1, le cas dégénéré.
        (3, 1, 3, 1),
    ],
)
def test_decompte_des_combinaisons_et_des_chemins(
    n_folds: int, n_test_folds: int, n_splits: int, n_paths: int
) -> None:
    """(a) Calculs à la main, portés dans le tableau de paramètres."""
    cv = CombinatorialPurgedCV(n_folds=n_folds, n_test_folds=n_test_folds)
    assert cv.n_splits == n_splits
    assert cv.n_paths == n_paths
    assert cv.get_n_splits() == n_splits
    assert len(cv.test_fold_combinations()) == n_splits


@pytest.mark.parametrize(("n_folds", "n_test_folds"), [(6, 2), (10, 3), (12, 5), (7, 6), (4, 1)])
def test_les_deux_ecritures_du_nombre_de_chemins_coincident(n_folds: int, n_test_folds: int) -> None:
    """(b) Identité mathématique : k/N x C(N,k) = C(N-1, k-1).

    La preuve tient en une ligne d'algèbre. En développant les factorielles,
    (k/N) x N! / (k!(N-k)!) vaut (N-1)! / ((k-1)!(N-k)!), qui est C(N-1, k-1).
    Le test impose au passage que la division tombe juste.
    """
    cv = CombinatorialPurgedCV(n_folds=n_folds, n_test_folds=n_test_folds)
    assert cv.n_paths == math.comb(n_folds - 1, n_test_folds - 1)
    assert cv.n_splits * n_test_folds % n_folds == 0


def test_chaque_pli_est_teste_dans_autant_de_combinaisons_que_de_chemins() -> None:
    """(b) Chaque pli occupe exactement une place de test par chemin.

    Avec N=6 et k=2, chaque pli apparaît dans C(5,1) = 5 combinaisons, et il y a
    5 chemins. La matrice d'affectation est donc de forme (6, 5).
    """
    cv = CombinatorialPurgedCV(n_folds=6, n_test_folds=2)
    assignment = cv.path_assignment()
    assert assignment.shape == (6, 5)
    for fold in range(6):
        occurrences = sum(1 for combo in cv.test_fold_combinations() if fold in combo)
        assert occurrences == 5  # (a) C(5,1) = 5
    assert sorted(assignment.flatten().tolist()) == sorted(
        [split for split, combo in enumerate(cv.test_fold_combinations()) for _ in combo]
    )


def test_chaque_observation_est_testee_le_bon_nombre_de_fois() -> None:
    """(a) Sur les 15 combinaisons, chaque observation est en test 5 fois.

    Le compte vient du calcul à la main : une observation appartient à un pli,
    et ce pli est en test dans C(5,1) = 5 des 15 combinaisons.
    """
    cv = CombinatorialPurgedCV(n_folds=6, n_test_folds=2)
    X = _matrix(60)
    compte = np.zeros(60, dtype=int)
    for _, test_index in cv.split(X):
        compte[test_index] += 1
    assert compte.tolist() == [5] * 60


def test_chaque_chemin_couvre_l_echantillon_une_fois() -> None:
    """(b) Un chemin recouvre l'échantillon exactement une fois, sans trou.

    C'est la définition même d'un chemin : une place de test par pli, et les
    plis partitionnent l'échantillon.
    """
    cv = CombinatorialPurgedCV(n_folds=6, n_test_folds=2)
    X = _matrix(60)
    paths = build_test_paths(cv, X)
    assert len(paths) == 5  # (a) 15 x 2 / 6 = 5
    for path in paths:
        assert path.test_index.tolist() == list(range(60))
        assert path.n_observations == 60
        assert len(path.segments) == 6
        assert [segment.fold for segment in path.segments] == list(range(6))


def test_les_chemins_emploient_des_combinaisons_differentes() -> None:
    """(a) Les cinq chemins ne recyclent pas les mêmes combinaisons.

    Chaque combinaison sert exactement k = 2 fois au total, une fois par pli
    qu'elle teste. Les 5 chemins x 6 plis font 30 places, pour 15 combinaisons.
    """
    cv = CombinatorialPurgedCV(n_folds=6, n_test_folds=2)
    paths = build_test_paths(cv, _matrix(60))
    places = [split for path in paths for split in path.split_ids]
    assert len(places) == 30  # (a) 5 chemins x 6 plis
    assert sorted(set(places)) == list(range(15))
    assert all(places.count(split) == 2 for split in range(15))


# --------------------------------------------------------------------------
# Le découpage en plis
# --------------------------------------------------------------------------


def test_tailles_de_plis_le_reste_va_aux_premiers() -> None:
    """(a) Treize observations en cinq plis donnent 3, 3, 3, 2, 2.

    Treize divisé par cinq fait deux, reste trois. Les trois premiers plis
    reçoivent donc une observation de plus. C'est la convention de
    ``sklearn.model_selection.KFold``.
    """
    cv = CombinatorialPurgedCV(n_folds=5, n_test_folds=2)
    bounds = cv.fold_boundaries(13)
    assert bounds.tolist() == [0, 3, 6, 9, 11, 13]
    assert np.diff(bounds).tolist() == [3, 3, 3, 2, 2]


def test_les_plis_partitionnent_l_echantillon() -> None:
    """(b) Les plis sont contigus, disjoints et couvrants, quelle que soit la taille."""
    for n_samples in (17, 20, 23, 100):
        cv = CombinatorialPurgedCV(n_folds=7, n_test_folds=2)
        bounds = cv.fold_boundaries(n_samples)
        assert bounds[0] == 0
        assert bounds[-1] == n_samples
        assert np.all(np.diff(bounds) > 0)


def test_moins_d_observations_que_de_plis_leve() -> None:
    """(a) Cinq observations en six plis laisseraient un pli vide."""
    cv = CombinatorialPurgedCV(n_folds=6, n_test_folds=2)
    with pytest.raises(InsufficientDataError, match="un pli au moins serait vide"):
        cv.fold_boundaries(5)
    with pytest.raises(InsufficientDataError):
        list(cv.split(_matrix(5)))


# --------------------------------------------------------------------------
# La purge et l'embargo, sur douze observations comptées à la main
# --------------------------------------------------------------------------
#
# Douze observations en six plis donnent six plis de deux :
# pli 0 = [0, 1], pli 1 = [2, 3], pli 2 = [4, 5], pli 3 = [6, 7],
# pli 4 = [8, 9], pli 5 = [10, 11].


def _split_of(
    cv: CombinatorialPurgedCV, X: np.ndarray, combination: tuple[int, ...]
) -> tuple[list[int], list[int]]:
    """Rend l'entraînement et le test de la combinaison demandée, en listes.

    Le parcours s'arrête à la combinaison voulue plutôt que de dérouler les
    autres, qui ne sont pas l'objet du contrôle.
    """
    position = cv.test_fold_combinations().index(combination)
    for index, (train, test) in enumerate(cv.split(X)):
        if index == position:
            return train.tolist(), test.tolist()
    raise AssertionError(f"combinaison {combination} introuvable")


def test_ordre_lexicographique_des_combinaisons() -> None:
    """(a) Les combinaisons se lisent dans l'ordre d'``itertools.combinations``.

    Pour N=6 et k=2, la septième combinaison, d'indice 6, est le couple (1, 3).
    L'ordre importe : c'est celui de ``skfolio``, donc celui qui rend les deux
    implémentations comparables une à une.
    """
    cv = CombinatorialPurgedCV(n_folds=6, n_test_folds=2)
    combinations = cv.test_fold_combinations()
    assert combinations[0] == (0, 1)
    assert combinations[6] == (1, 3)
    assert combinations[-1] == (4, 5)


def test_sans_purge_l_entrainement_est_le_complement_du_test() -> None:
    """(a) Purge et embargo nuls : les plis 1 et 3 en test laissent tout le reste.

    Test = [2, 3, 6, 7]. Entraînement = [0, 1, 4, 5, 8, 9, 10, 11].
    """
    cv = CombinatorialPurgedCV(n_folds=6, n_test_folds=2)
    train, test = _split_of(cv, _matrix(12), (1, 3))
    assert test == [2, 3, 6, 7]
    assert train == [0, 1, 4, 5, 8, 9, 10, 11]


def test_la_purge_agit_aux_deux_frontieres_de_chaque_bloc() -> None:
    """(a) Purge de 1, plis 1 et 3 en test, quatre observations retirées.

    Bloc [2, 3] : la purge retire 1 à gauche et 4 à droite.
    Bloc [6, 7] : la purge retire 5 à gauche et 8 à droite.
    Entraînement attendu : [0, 9, 10, 11].
    """
    cv = CombinatorialPurgedCV(n_folds=6, n_test_folds=2, purge=1)
    train, test = _split_of(cv, _matrix(12), (1, 3))
    assert test == [2, 3, 6, 7]
    assert train == [0, 9, 10, 11]


def test_l_embargo_n_agit_qu_a_droite() -> None:
    """(a) Embargo de 1 sans purge, plis 1 et 3 en test.

    Rien n'est retiré à gauche des blocs. À droite, 4 et 8 partent.
    Entraînement attendu : [0, 1, 5, 9, 10, 11].
    """
    cv = CombinatorialPurgedCV(n_folds=6, n_test_folds=2, embargo=1)
    train, _ = _split_of(cv, _matrix(12), (1, 3))
    assert train == [0, 1, 5, 9, 10, 11]


def test_purge_et_embargo_se_cumulent_a_droite() -> None:
    """(a) Purge 1 et embargo 2, plis 2 et 3 en test, donc un bloc unique.

    Les deux plis sont voisins : le test vaut [4, 5, 6, 7], d'un seul tenant.
    À gauche, la purge retire 3. À droite, purge plus embargo font trois
    observations, soit 8, 9 et 10. Entraînement attendu : [0, 1, 2, 11].
    """
    cv = CombinatorialPurgedCV(n_folds=6, n_test_folds=2, purge=1, embargo=2)
    train, test = _split_of(cv, _matrix(12), (2, 3))
    assert test == [4, 5, 6, 7]
    assert train == [0, 1, 2, 11]


def test_la_purge_ne_deborde_pas_au_debut_de_l_echantillon() -> None:
    """(a) Vingt-quatre observations en six plis de quatre, purge de 2.

    Les plis 0 et 1 en test donnent le bloc [0, ..., 7]. Il n'y a rien à retirer
    avant l'observation 0, et la purge ne repart pas de la fin du tableau.
    À droite partent 8 et 9. Entraînement attendu : [10, ..., 23].
    """
    cv = CombinatorialPurgedCV(n_folds=6, n_test_folds=2, purge=2)
    train, test = _split_of(cv, _matrix(24), (0, 1))
    assert test == list(range(8))
    assert train == list(range(10, 24))


def test_la_purge_ne_deborde_pas_a_la_fin_de_l_echantillon() -> None:
    """(a) Mêmes données, purge de 1, plis 4 et 5 en test.

    Le bloc de test vaut [16, ..., 23]. Il n'y a rien à retirer après
    l'observation 23. À gauche part 15. Entraînement attendu : [0, ..., 14].
    """
    cv = CombinatorialPurgedCV(n_folds=6, n_test_folds=2, purge=1)
    train, test = _split_of(cv, _matrix(24), (4, 5))
    assert test == list(range(16, 24))
    assert train == list(range(15))


@pytest.mark.parametrize(
    ("purge", "embargo", "entrainements"),
    [
        # (c) Valeurs publiées : les trois exemples exécutés de la docstring de
        # ``skfolio.model_selection.CombinatorialPurgedCV``, version 1.0.3, sur
        # douze observations en trois plis de quatre pris deux à deux. Elles sont
        # recopiées du texte de la classe, pas obtenues en exécutant quoi que ce
        # soit, ni le nôtre ni le sien.
        (0, 0, [[8, 9, 10, 11], [4, 5, 6, 7], [0, 1, 2, 3]]),
        (1, 0, [[9, 10, 11], [5, 6], [0, 1, 2]]),
        (0, 1, [[9, 10, 11], [5, 6, 7], [0, 1, 2, 3]]),
    ],
)
def test_les_entrainements_publies_par_skfolio_sont_retrouves(
    purge: int, embargo: int, entrainements: list[list[int]]
) -> None:
    """(c) Les trois exemples publiés dans la documentation de ``skfolio`` 1.0.3.

    Ces valeurs sont une vérité extérieure aux deux implémentations. Un test qui
    confronte notre code au code de ``skfolio`` prouve seulement que les deux
    font la même chose. Celui-ci prouve en plus qu'elles font ce que la
    documentation annonce, purge et embargo compris.
    """
    cv = CombinatorialPurgedCV(n_folds=3, n_test_folds=2, purge=purge, embargo=embargo)
    obtenus = [train.tolist() for train, _ in cv.split(_matrix(12))]
    assert obtenus == entrainements


def test_purge_et_test_ne_se_recouvrent_jamais() -> None:
    """(b) Entraînement et test restent disjoints sur toutes les combinaisons."""
    cv = CombinatorialPurgedCV(n_folds=8, n_test_folds=3, purge=2, embargo=1)
    X = _matrix(80)
    for train, test in cv.split(X):
        assert set(train).isdisjoint(set(test))
        assert np.all(np.diff(train) > 0)
        assert np.all(np.diff(test) > 0)


def test_un_entrainement_vide_leve_plutot_que_de_rendre_un_tableau_nul() -> None:
    """(a) Six plis de deux, cinq en test, purge 1 et embargo 1.

    Le seul pli d'entraînement fait deux observations. Quand il est encadré par
    deux blocs de test, il perd deux observations à gauche, purge plus embargo,
    et une à droite. Il ne reste rien, et le découpage doit le dire.
    """
    cv = CombinatorialPurgedCV(n_folds=6, n_test_folds=5, purge=1, embargo=1)
    with pytest.raises(InsufficientDataError, match="entraînement vide"):
        list(cv.split(_matrix(12)))


# --------------------------------------------------------------------------
# La distribution de performance
# --------------------------------------------------------------------------


def test_resume_de_distribution_calcule_a_la_main() -> None:
    """(a) Cinq chemins portant -2, -1, 0, 1 et 2.

    Moyenne 0, médiane 0. Somme des carrés 4+1+0+1+4 = 10, divisée par 4 pour
    l'écart type d'échantillon, soit 2,5 dont la racine vaut 1,5811388300841898.
    Quantile 5 % par interpolation linéaire : la position vaut 0,05 x 4 = 0,2,
    donc -2 + 0,2 x 1 = -1,8. Quantile 95 % : position 3,8, donc 1 + 0,8 = 1,8.
    Part de chemins négatifs : 2 sur 5, soit 0,4.
    """
    cv = CombinatorialPurgedCV(n_folds=6, n_test_folds=2)
    distribution = cpcv_performance_distribution(
        cv, _matrix(60), lambda path: float(path.path_id) - 2.0, metric_name="sharpe"
    )
    assert isinstance(distribution, PerformanceDistribution)
    assert distribution.metrics.tolist() == [-2.0, -1.0, 0.0, 1.0, 2.0]
    assert distribution.metrics.name == "sharpe"
    assert distribution.metrics.index.name == "path"
    resume = distribution.summary
    assert resume["count"] == 5.0
    assert resume["mean"] == pytest.approx(0.0, abs=1e-15)
    assert resume["median"] == pytest.approx(0.0, abs=1e-15)
    assert resume["std"] == pytest.approx(math.sqrt(2.5), abs=1e-15)
    assert resume["min"] == -2.0
    assert resume["max"] == 2.0
    assert resume["quantile_low"] == pytest.approx(-1.8, abs=1e-15)
    assert resume["quantile_high"] == pytest.approx(1.8, abs=1e-15)
    assert resume["quantile_low_level"] == 0.05
    assert resume["quantile_high_level"] == 0.95
    assert distribution.negative_share == pytest.approx(0.4, abs=1e-15)


def test_les_niveaux_de_quantile_sont_des_arguments() -> None:
    """(a) Avec les niveaux 10 % et 90 %, les positions valent 0,4 et 3,6.

    Quantile 10 % : -2 + 0,4 x 1 = -1,6. Quantile 90 % : 1 + 0,6 x 1 = 1,6.
    """
    cv = CombinatorialPurgedCV(n_folds=6, n_test_folds=2)
    distribution = cpcv_performance_distribution(
        cv,
        _matrix(60),
        lambda path: float(path.path_id) - 2.0,
        lower_quantile=0.10,
        upper_quantile=0.90,
    )
    assert distribution.summary["quantile_low"] == pytest.approx(-1.6, abs=1e-15)
    assert distribution.summary["quantile_high"] == pytest.approx(1.6, abs=1e-15)


@pytest.mark.parametrize(("bas", "haut"), [(0.0, 0.95), (0.05, 1.0), (0.95, 0.05)])
def test_niveaux_de_quantile_hors_domaine(bas: float, haut: float) -> None:
    """(a) Les niveaux doivent vérifier 0 < bas < haut < 1, sans exception."""
    cv = CombinatorialPurgedCV(n_folds=4, n_test_folds=2)
    with pytest.raises(ConfigError, match="niveaux de quantile"):
        cpcv_performance_distribution(
            cv, _matrix(40), lambda path: 1.0, lower_quantile=bas, upper_quantile=haut
        )


# --------------------------------------------------------------------------
# Simulation : ce que la distribution montre quand il n'y a rien à trouver
# --------------------------------------------------------------------------


def _momentum_backtest(returns: pd.Series) -> Callable[[TestPath], float]:
    """Rend une fonction de backtest dont la position dépend de l'entraînement.

    La position d'un morceau vaut la moyenne des rendements d'entraînement
    divisée par leur écart type. Sous l'hypothèse nulle, entraînement et test
    sont indépendants, donc l'espérance du produit est nulle.
    """
    values = returns.to_numpy()

    def backtest(path: TestPath) -> float:
        """Rend le ratio de Sharpe annualisé du chemin, morceau par morceau."""
        pieces = []
        for segment in path.segments:
            train = values[segment.train_index]
            weight = float(train.mean() / train.std(ddof=1))
            pieces.append(weight * values[segment.test_index])
        out_of_sample = pd.Series(np.concatenate(pieces), index=returns.index)
        return sharpe_ratio(out_of_sample, frequency=Frequency.DAILY)

    return backtest


def test_simulation_sous_l_hypothese_nulle_la_moyenne_des_chemins_reste_nulle() -> None:
    """(b) Vérité connue : des rendements indépendants ne portent aucun signal.

    Les données sont simulées, donc la réponse est connue avant le calcul :
    l'espérance du ratio de Sharpe hors échantillon vaut zéro. La tolérance
    s'écrit en erreurs types plutôt qu'en valeur absolue. Sous l'hypothèse
    nulle, un ratio de Sharpe annualisé estimé sur n observations a un écart
    type d'environ la racine de 252 sur n, soit 0,447 pour 1 260 séances. Les
    cinq chemins étant corrélés, l'écart type de leur moyenne ne dépasse pas
    celui d'un chemin. Le seuil retenu est de trois erreurs types.
    """
    generator = child_generators(SEED, 1)[0]
    n_samples = 1260
    returns = pd.Series(generator.normal(0.0, 0.01, n_samples))
    cv = CombinatorialPurgedCV(n_folds=6, n_test_folds=2, purge=5, embargo=2)

    distribution = cpcv_performance_distribution(
        cv, returns.to_frame(), _momentum_backtest(returns), metric_name="sharpe"
    )

    erreur_type = math.sqrt(252.0 / n_samples)
    assert abs(distribution.summary["mean"]) < 3.0 * erreur_type
    assert distribution.metrics.size == 5


def test_simulation_la_tolerance_separe_un_sharpe_nul_d_un_sharpe_de_trois() -> None:
    """(b) Vérité connue à deux valeurs, pour montrer que la tolérance refuse.

    Une tolérance ne vaut que si elle refuse quelque chose. Sans ce contrôle,
    le test précédent passerait avec n'importe quelle borne assez large. Celle
    retenue vaut trois erreurs types, soit 3 x racine(252 / 1 260) = 1,342.
    Elle sépare bien zéro de trois, puisque 3 dépasse 2 x 1,342, qui vaut
    2,683. Les deux mondes admissibles ne se recouvrent donc pas.

    Le monde à signal tire des rendements indépendants de moyenne mu et d'écart
    type sigma, avec mu / sigma x racine(252) fixé à 3. La position vaut la
    moyenne d'entraînement divisée par son écart type, donc elle est positive
    presque sûrement. Sa statistique de Student vaut 0,189 x racine(840) = 5,5
    sur un entraînement moyen de 840 observations. Le ratio de Sharpe étant
    invariant par changement d'échelle positif, la performance hors échantillon
    reproduit celle des rendements eux-mêmes.
    """
    bruit, signal = child_generators(SEED, 2)
    n_samples = 1260
    sigma = 0.01
    sharpe_vise = 3.0
    mu = sigma * sharpe_vise / math.sqrt(252.0)
    erreur_type = math.sqrt(252.0 / n_samples)
    cv = CombinatorialPurgedCV(n_folds=6, n_test_folds=2, purge=5, embargo=2)

    # (a) La borne de séparation, calculée à la main : 2 x 3 x 0,4472 = 2,683 < 3.
    assert sharpe_vise > 2.0 * 3.0 * erreur_type

    sans = pd.Series(bruit.normal(0.0, sigma, n_samples))
    avec = pd.Series(signal.normal(mu, sigma, n_samples))
    sans_signal = cpcv_performance_distribution(cv, sans.to_frame(), _momentum_backtest(sans))
    avec_signal = cpcv_performance_distribution(cv, avec.to_frame(), _momentum_backtest(avec))

    assert abs(sans_signal.summary["mean"]) < 3.0 * erreur_type
    assert abs(avec_signal.summary["mean"] - sharpe_vise) < 3.0 * erreur_type
    # Un chemin négatif serait à plus de six erreurs types de la vérité posée.
    assert avec_signal.negative_share == 0.0
    assert sans_signal.summary["mean"] < avec_signal.summary["mean"]


def test_un_seul_chemin_donne_un_ecart_type_indefini() -> None:
    """(b) L'écart type d'échantillon d'un point unique n'existe pas.

    Avec N = 3 et k = 1, il y a C(3,1) = 3 combinaisons et 3 x 1 / 3 = 1 chemin.
    L'écart type d'échantillon divise par n - 1, qui vaut zéro ici, donc il rend
    NaN. Un zéro à sa place serait un mensonge : il ferait lire une dispersion
    nulle là où la dispersion n'est pas définie.
    """
    cv = CombinatorialPurgedCV(n_folds=3, n_test_folds=1)
    distribution = cpcv_performance_distribution(cv, _matrix(30), lambda path: -1.5)

    assert distribution.metrics.size == 1  # (a) 3 x 1 / 3 = 1
    assert math.isnan(distribution.summary["std"])
    assert distribution.summary["mean"] == -1.5
    assert distribution.summary["quantile_low"] == -1.5
    assert distribution.negative_share == 1.0


def test_la_dispersion_ne_nait_que_de_la_dependance_a_l_entrainement() -> None:
    """(b) Deux backtests sur les mêmes données, l'un aveugle à l'entraînement.

    Un backtest qui ignore l'entraînement rend le même nombre sur les cinq
    chemins, puisque les cinq couvrent le même échantillon. Son écart type est
    donc nul, exactement. Dès que la position dépend de l'entraînement, les
    chemins se séparent. C'est ce que la distribution mesure, et c'est la raison
    d'être de la méthode.
    """
    generator = child_generators(SEED, 1)[0]
    returns = pd.Series(generator.normal(0.0, 0.01, 1260))
    cv = CombinatorialPurgedCV(n_folds=6, n_test_folds=2, purge=5, embargo=2)

    aveugle = cpcv_performance_distribution(
        cv,
        returns.to_frame(),
        lambda path: sharpe_ratio(returns.iloc[path.test_index], frequency=Frequency.DAILY),
    )
    informe = cpcv_performance_distribution(cv, returns.to_frame(), _momentum_backtest(returns))

    assert aveugle.metrics.std(ddof=1) == 0.0
    assert informe.metrics.std(ddof=1) > 0.0
    # (b) Identité : le chemin couvrant arange(n) dans l'ordre, le backtest
    # aveugle rend exactement le ratio de Sharpe de la série entière.
    entier = sharpe_ratio(returns, frequency=Frequency.DAILY)
    assert aveugle.metrics.iloc[0] == pytest.approx(entier, abs=1e-12)


# --------------------------------------------------------------------------
# Propriétés, sur des paramétrages tirés au hasard
# --------------------------------------------------------------------------


@settings(max_examples=40, deadline=None)
@given(
    n_folds=st.integers(min_value=2, max_value=7),
    decalage=st.integers(min_value=0, max_value=6),
    surplus=st.integers(min_value=0, max_value=20),
)
def test_propriete_decompte_couverture_et_disjonction(n_folds: int, decalage: int, surplus: int) -> None:
    """(b) Trois identités qui tiennent quel que soit le paramétrage.

    Le nombre de combinaisons vaut le coefficient binomial. Le produit du
    nombre de chemins par le nombre de plis vaut celui du nombre de
    combinaisons par le nombre de plis de test. Enfin, chaque chemin recouvre
    l'échantillon une fois et une seule.
    """
    n_test_folds = 1 + decalage % (n_folds - 1)
    n_samples = n_folds + surplus
    cv = CombinatorialPurgedCV(n_folds=n_folds, n_test_folds=n_test_folds)

    assert cv.n_splits == math.comb(n_folds, n_test_folds)
    assert cv.n_paths * n_folds == cv.n_splits * n_test_folds

    X = _matrix(n_samples)
    for train, test in cv.split(X):
        assert set(train).isdisjoint(set(test))
    paths = build_test_paths(cv, X)
    assert len(paths) == cv.n_paths
    for path in paths:
        assert path.test_index.tolist() == list(range(n_samples))


# --------------------------------------------------------------------------
# Confrontation avec skfolio 1.0.3
# --------------------------------------------------------------------------


@pytest.mark.parametrize(("n_folds", "n_test_folds"), [(6, 2), (10, 2), (5, 3), (10, 8), (8, 4), (4, 2)])
def test_les_decomptes_coincident_avec_skfolio(n_folds: int, n_test_folds: int) -> None:
    """(d) Implémentation indépendante : ``skfolio`` 1.0.3.

    Le nombre de combinaisons et le nombre de chemins ne dépendent que de N et
    de k. Un écart signalerait une faute de formule d'un côté ou de l'autre.
    Les 120 observations sont divisibles par chacun des nombres de plis
    éprouvés, si bien que les deux découpes coïncident aussi.
    """
    cv = CombinatorialPurgedCV(n_folds=n_folds, n_test_folds=n_test_folds)
    comparison = compare_with_skfolio(cv, _matrix(120))

    assert comparison.n_splits_skfolio == math.comb(n_folds, n_test_folds)
    assert comparison.splits_gap == 0
    assert comparison.paths_gap == 0
    assert comparison.counts_agree
    assert comparison.same_test_sets is True
    assert comparison.fold_sizes_quantlab == comparison.fold_sizes_skfolio
    assert comparison.notes[: len(CONVENTION_DIFFERENCES)] == CONVENTION_DIFFERENCES


def test_les_index_purges_coincident_avec_skfolio() -> None:
    """(d) La purge et l'embargo se comparent index par index à ``skfolio``.

    Le contrôle porte sur les 15 combinaisons de six plis pris deux à deux, avec
    une purge de 3 et un embargo de 2. Les 120 observations se divisent en six
    plis de 20, donc les deux découpes partent du même point et tout écart
    viendrait de la purge.
    """
    from skfolio.model_selection import CombinatorialPurgedCV as SkfolioCPCV

    cv = CombinatorialPurgedCV(n_folds=6, n_test_folds=2, purge=3, embargo=2)
    sk = SkfolioCPCV(n_folds=6, n_test_folds=2, purged_size=3, embargo_size=2)
    X = _matrix(120)

    ours = list(cv.split(X))
    theirs = list(sk.split(X))
    assert len(ours) == len(theirs) == 15

    for (train, test), (sk_train, sk_test) in zip(ours, theirs, strict=True):
        assert train.tolist() == sk_train.tolist()
        assert test.tolist() == np.sort(np.concatenate(sk_test)).tolist()


def test_l_affectation_des_chemins_coincide_avec_skfolio() -> None:
    """(d) La matrice qui range les combinaisons en chemins est celle de ``skfolio``."""
    from skfolio.model_selection import CombinatorialPurgedCV as SkfolioCPCV

    cv = CombinatorialPurgedCV(n_folds=6, n_test_folds=2)
    sk = SkfolioCPCV(n_folds=6, n_test_folds=2)
    assert cv.path_assignment().tolist() == sk.recombined_paths.tolist()


def test_la_convention_de_reste_diverge_de_skfolio_et_le_dit() -> None:
    """(a) et (d) Treize observations en cinq plis : les découpes diffèrent.

    Notre convention verse le reste sur les premiers plis, donc 3, 3, 3, 2, 2,
    et les treize observations sont couvertes. ``skfolio`` 1.0.3 attribue à
    l'observation numéro t le pli t divisé par 2 en division entière, puis
    ramène le seul identifiant égal à 5 sur le pli 4. L'observation 12 reçoit
    l'identifiant 6, que rien ne ramène dans les cinq plis. Elle n'appartient
    donc à aucun pli de test, et les plis mesurent 2, 2, 2, 2 et 4, soit douze
    observations sur treize. Ce constat est mesuré sur ``skfolio`` 1.0.3 le
    2026-09-01, et le test le fige pour qu'une mise à jour le signale.
    """
    cv = CombinatorialPurgedCV(n_folds=5, n_test_folds=2)
    comparison = compare_with_skfolio(cv, _matrix(13))

    assert comparison.counts_agree
    assert comparison.fold_sizes_quantlab == (3, 3, 3, 2, 2)
    assert sum(comparison.fold_sizes_quantlab) == 13
    assert comparison.fold_sizes_skfolio == (2, 2, 2, 2, 4)
    assert sum(comparison.fold_sizes_skfolio) == 12
    assert comparison.same_test_sets is False


def test_quand_skfolio_refuse_de_decouper_la_comparaison_le_dit() -> None:
    """(d) La garde de purge de ``skfolio`` 1.0.3 est plus stricte que la nôtre.

    ``skfolio`` refuse dès que purge plus embargo atteint la taille d'un pli
    moins un. Soixante observations en six plis de dix : il refuse donc à partir
    de neuf. Notre découpage tient encore à neuf, chaque combinaison gardant au
    moins onze observations d'entraînement. La comparaison doit alors rendre les
    décomptes sans prétendre avoir confronté les index.
    """
    cv = CombinatorialPurgedCV(n_folds=6, n_test_folds=2, purge=9)
    comparison = compare_with_skfolio(cv, _matrix(60))

    assert comparison.counts_agree
    assert comparison.same_test_sets is None
    assert comparison.fold_sizes_skfolio == ()
    assert comparison.fold_sizes_quantlab == (10, 10, 10, 10, 10, 10)
    assert any("n'a pas pu découper" in note for note in comparison.notes)
    # Notre découpage, lui, produit bien les 15 combinaisons. (a) C(6,2) = 15.
    assert len(list(cv.split(_matrix(60)))) == 15


def test_skfolio_cpcv_reprend_la_configuration_de_validation() -> None:
    """(a) La correspondance des quatre noms, vérifiée dans les deux sens."""
    config = _config()
    sk = skfolio_cpcv(config)
    ours = CombinatorialPurgedCV.from_config(config)

    assert (sk.n_folds, sk.n_test_folds, sk.purged_size, sk.embargo_size) == (6, 2, 3, 2)
    assert (ours.n_folds, ours.n_test_folds, ours.purge, ours.embargo) == (6, 2, 3, 2)
    assert ours.n_splits == sk.n_splits
    assert ours.n_paths == sk.n_test_paths


def test_le_domaine_de_skfolio_est_plus_etroit_et_le_refus_est_explicite() -> None:
    """(a) Un seul pli de test est licite chez nous, refusé par ``skfolio``.

    Le cas dégénère en validation croisée purgée ordinaire : C(6,1) = 6
    combinaisons et 6 x 1 / 6 = 1 chemin. La fabrique doit dire pourquoi
    ``skfolio`` refuse plutôt que de laisser remonter son message brut.
    """
    config = _config(n_test_folds=1)
    ours = CombinatorialPurgedCV.from_config(config)
    assert (ours.n_splits, ours.n_paths) == (6, 1)
    with pytest.raises(ConfigError, match="skfolio refuse"):
        skfolio_cpcv(config)


def test_optimal_folds_minimise_le_cout_publie() -> None:
    """(b) et (d) Le couple rendu bat les autres sous la fonction de coût.

    Le coût est la somme des deux distances relatives aux cibles, pondérées à
    un. La taille moyenne d'entraînement vaut n fois (N - k) sur N. Les cibles
    sont 1 000 observations, un entraînement de 800 et dix chemins. Le couple
    (11, 2) donne alors C(10,1) = 10 chemins et 1 000 x 9 / 11 = 818,18
    observations d'entraînement, donc un coût de 0,0227. Les cinq autres couples
    éprouvés sont plus chers, et le test le vérifie sans lire la sortie du code.
    """

    def cout(n_folds: int, n_test_folds: int) -> float:
        """Rend le coût publié par ``skfolio``, réécrit ici depuis sa formule."""
        chemins = math.comb(n_folds, n_test_folds) * n_test_folds // n_folds
        taille = 1000.0 / n_folds * (n_folds - n_test_folds)
        return abs(chemins - 10) / 10 + abs(taille - 800.0) / 800.0

    n_folds, n_test_folds = optimal_folds(n_observations=1000, target_train_size=800, target_n_test_paths=10)

    assert n_folds >= 3
    assert 2 <= n_test_folds < n_folds
    for candidat in [(6, 2), (12, 2), (21, 2), (11, 3), (30, 2)]:
        assert cout(n_folds, n_test_folds) <= cout(*candidat)


# --------------------------------------------------------------------------
# Le domaine des paramètres
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kwargs", "motif"),
    [
        ({"n_folds": 1, "n_test_folds": 1}, "n_folds doit valoir au moins 2"),
        ({"n_folds": 6, "n_test_folds": 0}, "n_test_folds doit valoir au moins 1"),
        ({"n_folds": 6, "n_test_folds": 6}, "strictement inférieur"),
        ({"n_folds": 6, "n_test_folds": 7}, "strictement inférieur"),
        ({"n_folds": 6, "n_test_folds": 2, "purge": -1}, "purge ne peut pas être négative"),
        ({"n_folds": 6, "n_test_folds": 2, "embargo": -1}, "embargo ne peut pas être négatif"),
    ],
)
def test_parametres_hors_domaine(kwargs: dict[str, int], motif: str) -> None:
    """(a) Chaque borne du domaine est refusée par une erreur nommée."""
    with pytest.raises(ConfigError, match=motif):
        CombinatorialPurgedCV(**kwargs)


def test_le_plafond_de_combinaisons_est_un_argument() -> None:
    """(a) C(20,10) vaut 184 756, au-delà du plafond posé à dix.

    Le plafond est un argument documenté, jamais une constante cachée. Le même
    paramétrage passe dès qu'on le relève.
    """
    with pytest.raises(ConfigError, match="au-delà du plafond"):
        CombinatorialPurgedCV(n_folds=20, n_test_folds=10, max_splits=10)
    cv = CombinatorialPurgedCV(n_folds=20, n_test_folds=10, max_splits=200_000)
    assert cv.n_splits == 184_756  # (a) C(20,10), valeur classique du triangle de Pascal


def test_un_intrant_sans_longueur_est_refuse() -> None:
    """(a) Un entier n'est pas un tableau, et le message doit le dire."""
    cv = CombinatorialPurgedCV(n_folds=4, n_test_folds=2)
    with pytest.raises(ConfigError, match="ni attribut"):
        list(cv.split(42))


def test_l_intrant_peut_etre_un_dataframe_ou_une_liste() -> None:
    """(a) Seule la longueur de l'intrant est lue, jamais son contenu.

    Douze observations en quatre plis donnent des plis de trois, quelle que soit
    la forme du tableau.
    """
    cv = CombinatorialPurgedCV(n_folds=4, n_test_folds=2)
    attendu = [(train.tolist(), test.tolist()) for train, test in cv.split(_matrix(12))]
    frame = pd.DataFrame({"a": range(12), "b": range(12)})
    depuis_frame = [(train.tolist(), test.tolist()) for train, test in cv.split(frame)]
    depuis_liste = [(train.tolist(), test.tolist()) for train, test in cv.split(list(range(12)))]
    assert depuis_frame == attendu
    assert depuis_liste == attendu
    assert attendu[0][1] == [0, 1, 2, 3, 4, 5]

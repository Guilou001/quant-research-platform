"""Contrôles du module ``quantlab.validation.bootstrap``.

Chaque valeur attendue vient d'une source déclarée en commentaire, jamais de la
sortie du code. Les quatre sources admises sont le calcul à la main (a), la forme
fermée ou l'identité mathématique (b), la valeur publiée et citée (c), et
l'implémentation indépendante (d).
"""

from __future__ import annotations

import math

import hypothesis.strategies as st
import numpy as np
import pandas as pd
import pytest
import scipy.stats as sps
from arch.bootstrap import optimal_block_length
from hypothesis import given, settings

from quantlab.analytics.ratios import sharpe_ratio
from quantlab.core.determinism import child_generators, make_generator
from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.types import Frequency
from quantlab.validation.bootstrap import (
    BootstrapDistribution,
    BootstrapMethod,
    _flat_top_weight,
    block_bootstrap,
    bootstrap_confidence_interval,
    bootstrap_indices,
    bootstrap_pvalue,
    bootstrap_statistic,
    geometric_block_lengths,
    iid_bootstrap,
    optimal_block_size,
    politis_white_block_sizes,
    stationary_bootstrap,
)

SEED = 20260901


def _ar1(n: int, rho: float, generator: np.random.Generator, *, burn: int = 500) -> np.ndarray:
    """Simule un processus autorégressif d'ordre un, innovations normales réduites.

    Le rodage de ``burn`` observations est jeté pour que la série rendue soit
    stationnaire, et non partie de zéro.
    """
    total = n + burn
    innovations = generator.standard_normal(total)
    series = np.empty(total)
    series[0] = innovations[0] / math.sqrt(1.0 - rho**2)
    for t in range(1, total):
        series[t] = rho * series[t - 1] + innovations[t]
    return series[burn:]


def _ar1_variance_of_mean(n: int, rho: float) -> float:
    r"""Rend la variance exacte de la moyenne d'un AR(1) de variance d'innovation 1.

    Source (b) : forme fermée. Pour un processus stationnaire,

    .. math::

        \operatorname{Var}(\bar{x}) = \frac{1}{n^2}
        \left[n\gamma_0 + 2\sum_{k=1}^{n-1}(n-k)\gamma_k\right],
        \qquad \gamma_k = \frac{\rho^{|k|}}{1 - \rho^2}
    """
    gamma0 = 1.0 / (1.0 - rho**2)
    lags = np.arange(1, n)
    cross = float(np.sum((n - lags) * gamma0 * rho**lags))
    return (n * gamma0 + 2.0 * cross) / n**2


# --------------------------------------------------------------------------- #
# Forme et appartenance des rééchantillons
# --------------------------------------------------------------------------- #


def test_iid_bootstrap_shape_and_membership() -> None:
    """Source (b) : un tirage avec remise ne peut rendre que des valeurs de l'échantillon."""
    sample = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    generator = make_generator(SEED)
    resamples = iid_bootstrap(sample, 50, generator)
    assert resamples.shape == (50, 5)
    assert np.isin(resamples, sample).all()


def test_iid_bootstrap_accepts_a_frame_and_keeps_columns_together() -> None:
    """Source (b) : rééchantillonner des lignes garde chaque ligne intacte.

    La ligne ``[10, 20]`` ne peut jamais devenir ``[10, 40]`` : c'est la
    propriété qui permet de rééchantillonner un signal et son rendement futur
    sans détruire le lien entre les deux.
    """
    frame = pd.DataFrame({"a": [10.0, 30.0, 50.0], "b": [20.0, 40.0, 60.0]})
    generator = make_generator(SEED)
    resamples = iid_bootstrap(frame, 20, generator)
    assert resamples.shape == (20, 3, 2)
    # Chaque ligne rééchantillonnée vérifie b = a + 10, relation vraie ligne à ligne.
    assert np.allclose(resamples[..., 1], resamples[..., 0] + 10.0)


def test_circular_block_resample_has_exactly_the_original_length() -> None:
    """Source (b) : la longueur voulue vaut celle des données, quel que soit le bloc.

    Sept ne divise ni 3 ni 4 ni 5, donc le dernier bloc est tronqué dans les
    trois cas. La longueur rendue reste 7.
    """
    sample = np.arange(7.0)
    for block in (3, 4, 5):
        generator = make_generator(SEED)
        resamples = block_bootstrap(sample, block, 30, generator, circular=True)
        assert resamples.shape == (30, 7)
        assert np.isin(resamples, sample).all()


def test_circular_block_of_size_one_is_the_iid_bootstrap() -> None:
    """Source (b) : identité. Un bloc de longueur 1 tire un départ par position.

    Les deux constructions consomment alors exactement le même tirage uniforme,
    donc elles rendent la même matrice à partir du même générateur.
    """
    sample = np.arange(12.0)
    circular = block_bootstrap(sample, 1, 25, make_generator(11), circular=True)
    naive = iid_bootstrap(sample, 25, make_generator(11))
    assert np.array_equal(circular, naive)


def test_moving_block_bootstrap_never_wraps_around() -> None:
    """Source (a) : calcul à la main des départs admissibles.

    Avec 10 observations et des blocs de 4, un départ vaut au plus l'indice 6,
    puisque 6 + 4 = 10. Un bloc non circulaire est donc toujours croissant de 1
    en 1 sur ses 4 positions, sans retour à zéro. La longueur demandée est fixée
    à 8, soit exactement deux blocs, pour qu'aucun bloc ne soit tronqué.
    """
    sample = np.arange(10.0)
    generator = make_generator(SEED)
    resamples = block_bootstrap(sample, 4, 200, generator, circular=False, size=8)
    blocks = resamples.reshape(200, 2, 4)
    steps = np.diff(blocks, axis=2)
    assert np.all(steps == 1.0)
    assert blocks[:, :, 0].max() <= 6.0


def test_moving_block_refuses_a_block_longer_than_the_sample() -> None:
    """Un bloc non circulaire plus long que la série n'a aucun départ admissible."""
    with pytest.raises(ConfigError, match="dépasse les 5 observations"):
        block_bootstrap(np.arange(5.0), 6, 10, make_generator(SEED), circular=False)


def test_circular_blocks_wrap_around_the_ring_exactly() -> None:
    """Source (a) : le repli modulo est la définition même du bootstrap circulaire.

    Politis et Romano (1992) recollent la série en anneau. La position i d'un
    bloc parti de s vaut donc (s + i) modulo n, sans exception. Avec 10
    observations et des blocs de 4, les départs 7, 8 et 9 franchissent le bord,
    et le test vérifie qu'ils y sont bien passés.

    Le contrôle est exact et ne dépend d'aucune tolérance : sans le repli, une
    autre construction plausible saturerait sur la dernière observation, ce que
    l'égalité ci-dessous refuse.
    """
    n, block, n_resamples = 10, 4, 500
    resamples = block_bootstrap(
        np.arange(float(n)), block, n_resamples, make_generator(SEED), circular=True, size=8
    )
    blocks = resamples.astype(int).reshape(n_resamples, 2, block)
    for offset in range(block):
        assert np.array_equal(blocks[:, :, offset], (blocks[:, :, 0] + offset) % n)
    # Le contrôle serait vide si aucun bloc ne franchissait le bord.
    assert bool(np.any(blocks[:, :, 0] > n - block))


@pytest.mark.parametrize("method", [BootstrapMethod.CIRCULAR_BLOCK, BootstrapMethod.STATIONARY])
def test_every_observation_is_drawn_with_the_same_probability(method: BootstrapMethod) -> None:
    """Source (b) : sur l'anneau, chaque date a la probabilité 1/n d'occuper une position.

    C'est la raison d'être du repli. Sans lui, les premières et les dernières
    observations seraient sous-représentées, et une série dont les extrémités
    portent une crise verrait cette crise s'effacer du rééchantillonnage.

    Valeur attendue : 20 000 × 10 / 10 = 20 000 apparitions par indice.

    Tolérance : les positions d'un même bloc sont parfaitement liées, si bien que
    le nombre de tirages indépendants est celui des blocs, soit environ 60 000
    pour des blocs de 4. L'écart type du compte d'un indice vaut alors de l'ordre
    de racine(60 000 × 0,4 × 0,6) = 120, soit 0,6 % de 20 000. La borne retenue
    est de 3 %, soit cinq fois cet écart type.
    """
    n, n_resamples = 10, 20_000
    sample = np.arange(float(n))
    generator = make_generator(SEED)
    if method is BootstrapMethod.STATIONARY:
        resamples = stationary_bootstrap(sample, 4.0, n_resamples, generator)
    else:
        resamples = block_bootstrap(sample, 4, n_resamples, generator, circular=True)
    counts = np.bincount(resamples.astype(int).ravel(), minlength=n)
    expected = n_resamples * n / n
    assert counts.shape == (n,)
    assert np.allclose(counts, expected, rtol=0.03)


def test_stationary_bootstrap_shape_and_membership() -> None:
    """Source (b) : le rééchantillon stationnaire garde la longueur et l'échantillon."""
    sample = np.arange(20.0)
    generator = make_generator(SEED)
    resamples = stationary_bootstrap(sample, 5.0, 40, generator)
    assert resamples.shape == (40, 20)
    assert np.isin(resamples, sample).all()


# --------------------------------------------------------------------------- #
# La loi géométrique des longueurs de bloc
# --------------------------------------------------------------------------- #


def test_geometric_block_lengths_follow_the_published_law() -> None:
    """Sources (b) et (d) : moments en forme fermée et fonction de répartition de scipy.

    Politis et Romano (1994) posent P(L = m) = (1-p)^(m-1) p, de moyenne 1/p et
    d'écart type racine(1-p)/p. Pour une moyenne de 10, donc p = 0,1, l'écart
    type vaut racine(0,9)/0,1 = 9,4868.

    Tolérance : sur 200 000 tirages indépendants, l'erreur type de la moyenne
    vaut 9,4868 / racine(200 000) = 0,0212. La borne retenue est quatre erreurs
    types, soit 0,0849, arrondie à 0,09.
    """
    mean_block = 10.0
    n_draws = 200_000
    lengths = geometric_block_lengths(n_draws, mean_block, make_generator(SEED))

    assert lengths.min() >= 1
    assert lengths.mean() == pytest.approx(mean_block, abs=0.09)

    # Écart type : racine(1 - p) / p avec p = 0,1.
    expected_std = math.sqrt(1.0 - 0.1) / 0.1
    assert lengths.std(ddof=1) == pytest.approx(expected_std, rel=0.02)

    # Source (d) : la fonction de répartition de scipy.stats.geom, même paramétrage.
    reference = sps.geom(0.1)
    for cutoff in (1, 3, 7, 15, 30):
        empirical = float(np.mean(lengths <= cutoff))
        assert empirical == pytest.approx(reference.cdf(cutoff), abs=0.005)


def test_geometric_block_lengths_refuse_a_mean_of_one() -> None:
    """Une moyenne de 1 rend p = 1, donc des blocs d'une seule observation."""
    with pytest.raises(ConfigError, match="doit dépasser 1"):
        geometric_block_lengths(10, 1.0, make_generator(SEED))


def test_stationary_bootstrap_restarts_at_the_geometric_rate() -> None:
    """Source (b) : par absence de mémoire, chaque position redémarre avec probabilité p.

    Sur des données valant leur propre indice, le rééchantillon EST la matrice
    d'indices. Une position continue son bloc quand son indice vaut le précédent
    plus un, modulo la longueur de la série. La proportion de ruptures estime
    donc p = 1 / longueur moyenne.

    Correction déclarée : une rupture passe inaperçue quand le nouveau départ
    tombe exactement sur la position suivante, ce qui arrive avec probabilité
    1/n. Le taux attendu vaut donc p(1 - 1/n) = 0,1 × (1 - 1/2000) = 0,09995.

    Tolérance : les indicateurs de rupture sont i.i.d. de Bernoulli, ce que
    l'absence de mémoire garantit. Sur 100 × 1999 = 199 900 positions, l'erreur
    type vaut racine(0,1 × 0,9 / 199 900) = 0,00067. La borne retenue est quatre
    erreurs types, soit 0,0027, arrondie à 0,003.
    """
    n = 2000
    mean_block = 10.0
    sample = np.arange(float(n))
    indices = stationary_bootstrap(sample, mean_block, 100, make_generator(SEED)).astype(int)

    continuation = indices[:, 1:] == (indices[:, :-1] + 1) % n
    restart_rate = float(np.mean(~continuation))
    expected = (1.0 / mean_block) * (1.0 - 1.0 / n)
    assert restart_rate == pytest.approx(expected, abs=0.003)


def test_stationary_bootstrap_blocks_are_consecutive_on_the_ring() -> None:
    """Source (a) : par construction, une position qui n'est pas une rupture suit la précédente.

    Le test vérifie qu'il n'existe aucun autre motif : chaque écart entre deux
    positions voisines vaut soit 1 modulo n, soit un saut de rupture.
    """
    n = 50
    indices = stationary_bootstrap(np.arange(float(n)), 8.0, 30, make_generator(3)).astype(int)
    steps = (indices[:, 1:] - indices[:, :-1]) % n
    # Toute valeur est licite, mais la part des pas égaux à 1 doit dominer
    # largement : avec une moyenne de 8, sept pas sur huit continuent un bloc.
    assert float(np.mean(steps == 1)) > 0.75


def test_stationary_resample_block_lengths_follow_the_geometric_law() -> None:
    """Sources (b) et (d) : la loi des blocs RÉELLEMENT posés dans le rééchantillon.

    Le contrôle précédent porte sur ``geometric_block_lengths``, pris à part, et
    sur le TAUX moyen de rupture. Ni l'un ni l'autre ne prouve que le
    rééchantillonneur pose des blocs de longueur aléatoire. Des blocs de longueur
    FIXE égale à la moyenne rendent exactement le même taux de rupture, et le
    bootstrap stationnaire redevient alors celui de Künsch sans que rien ne le
    signale. Ce test lit les longueurs dans la matrice d'indices produite.

    Sur des données valant leur propre indice, une rupture est une position dont
    l'indice ne vaut pas le précédent plus un, modulo la longueur. L'écart entre
    deux ruptures consécutives EST la longueur d'un bloc complet, les blocs de
    bord étant écartés parce qu'ils sont tronqués.

    Valeurs attendues, source (b). Deux blocs voisins se soudent quand le nouveau
    départ tombe sur la position suivante, ce qui arrive avec probabilité 1/n. Un
    bloc observé réunit donc un nombre géométrique de blocs vrais, de moyenne
    1/(1 - 1/n), et sa longueur moyenne vaut (1/p)/(1 - 1/n) = 10,005. Son écart
    type vaut racine(1 - p)/p = 9,4868 à la correction en 1/n près.

    Tolérances, source (b). Le tirage donne 100 lignes de 2 000 positions, soit
    20 000 ruptures, dont deux blocs tronqués par ligne, ce qui laisse environ
    19 800 blocs complets. L'erreur type d'une fréquence y vaut au plus
    0,5/racine(19 800) = 0,00355, et la borne retenue est quatre erreurs types,
    soit 0,0142, arrondie à 0,015. L'erreur type de la moyenne vaut
    9,4868/racine(19 800) = 0,0674, et la borne retenue est quatre fois cela,
    soit 0,27. L'aplatissement de la loi géométrique vaut 9 + p²/(1-p) = 9,011.
    L'erreur type relative de l'écart type vaut donc
    racine(8,011/(4 × 19 800)) = 1,01 %, et la borne retenue est cinq fois cela,
    soit 5 %. La déformation due
    aux soudures est d'ordre 1/n = 0,0005, donc trente fois sous la borne des
    fréquences.
    """
    n, mean_block, n_rows = 2000, 10.0, 100
    probability = 1.0 / mean_block
    indices = stationary_bootstrap(np.arange(float(n)), mean_block, n_rows, make_generator(SEED)).astype(int)

    breaks = indices[:, 1:] != (indices[:, :-1] + 1) % n
    complete_lengths = np.concatenate(
        [np.diff(np.flatnonzero(row) + 1) for row in breaks if np.flatnonzero(row).size >= 2]
    )
    assert complete_lengths.size > 19_000
    assert complete_lengths.min() >= 1

    expected_mean = (1.0 / probability) / (1.0 - 1.0 / n)
    assert expected_mean == pytest.approx(10.005, abs=1e-3)
    assert complete_lengths.mean() == pytest.approx(expected_mean, abs=0.27)

    expected_std = math.sqrt(1.0 - probability) / probability
    assert complete_lengths.std(ddof=1) == pytest.approx(expected_std, rel=0.05)

    # Source (d) : la fonction de répartition de scipy.stats.geom, même paramètre.
    reference = sps.geom(probability)
    for cutoff in (1, 3, 7, 15, 30):
        empirical = float(np.mean(complete_lengths <= cutoff))
        assert empirical == pytest.approx(reference.cdf(cutoff), abs=0.015)


@pytest.mark.slow
def test_stationary_bootstrap_recovers_the_ar1_variance_of_the_mean() -> None:
    r"""Test de simulation : le bootstrap stationnaire retrouve une variance connue.

    Sans ce contrôle, rien ne relie la matrice d'indices au résultat statistique.
    Un rééchantillonneur qui tirerait un seul départ par rééchantillon garderait
    des longueurs de bloc géométriques, un taux de rupture juste et des indices
    uniformes, tout en rendant une variance vingt-cinq fois trop grande.

    Vérité, source (b) : la variance exacte de la moyenne d'un AR(1), calculée
    par ``_ar1_variance_of_mean``. Pour rho = 0,5 et n = 800 elle vaut 0,0049917,
    et le détail du calcul est écrit dans le test du bootstrap par blocs.

    Tolérance, source (b). Le bootstrap stationnaire estime la variance de long
    terme en pondérant l'autocovariance de retard k par (1 - p)^k, avec
    p = 1/15. Sur un AR(1) de coefficient 0,5, le facteur pondéré vaut
    1 + 2 × 0,466667/0,533333 = 2,75, contre 3 pour le facteur vrai. Le biais à
    la baisse est donc de 8,3 %, et la formule elle-même l'impose. L'autocovariance
    empirique en ajoute un second, également à la baisse et d'ordre 1/n. La borne
    retenue est 20 %, plus du double du biais calculé, et c'est celle du test
    jumeau sur le bootstrap par blocs.
    """
    rho, n, n_paths, n_resamples, mean_block = 0.5, 800, 60, 250, 15.0
    true_variance = _ar1_variance_of_mean(n, rho)
    assert true_variance == pytest.approx(0.0049917, abs=1e-6)

    generators = child_generators(SEED + 2, 2 * n_paths)
    variances = np.empty(n_paths)
    for path in range(n_paths):
        series = _ar1(n, rho, generators[2 * path])
        resamples = stationary_bootstrap(series, mean_block, n_resamples, generators[2 * path + 1])
        variances[path] = np.var(resamples.mean(axis=1), ddof=1)

    assert variances.mean() == pytest.approx(true_variance, rel=0.20)


# --------------------------------------------------------------------------- #
# Longueur de bloc optimale, règle de Politis et White
# --------------------------------------------------------------------------- #


def test_flat_top_weight_matches_hand_values() -> None:
    """Source (a) : calcul à la main de la fenêtre lambda(s) = min(1, 2(1 - |s|)).

    Avec M = 10, le retard 3 donne s = 0,3, donc un poids de 1. Le retard 5
    donne s = 0,5, donc un poids de 1 encore, la fenêtre étant plate jusque-là.
    Le retard 8 donne s = 0,8, donc 2 × (1 - 0,8) = 0,4. Le retard 10 donne 0, et
    tout retard au-delà aussi.
    """
    assert _flat_top_weight(3, 10) == pytest.approx(1.0)
    assert _flat_top_weight(5, 10) == pytest.approx(1.0)
    assert _flat_top_weight(8, 10) == pytest.approx(0.4)
    assert _flat_top_weight(10, 10) == pytest.approx(0.0)
    assert _flat_top_weight(14, 10) == pytest.approx(0.0)


def test_optimal_block_size_matches_arch_implementation() -> None:
    """Source (d) : ``arch.bootstrap.optimal_block_length``, version 8.

    Le contrôle porte sur la TRANSCRIPTION de la règle, non sur la règle
    elle-même. Notre code reprend les écarts que ``arch`` déclare vis-à-vis du
    programme MATLAB de Patton, à savoir la longueur d'échantillon maximale et la
    normalisation du corrélogramme. Le contrôle indépendant de la règle est celui
    de la valeur de population, plus bas.

    L'échantillon compte 1 500 observations, donc bien moins de 100 000, seuil au
    delà duquel la définition de K_N employée par ``arch`` cesserait de coïncider
    avec celle du papier.
    """
    series = _ar1(1500, 0.6, make_generator(SEED))
    selection = politis_white_block_sizes(series)
    reference = optimal_block_length(series)
    assert selection.stationary == pytest.approx(float(reference.iloc[0, 0]), rel=1e-10)
    assert selection.circular == pytest.approx(float(reference.iloc[0, 1]), rel=1e-10)


def test_optimal_block_sizes_differ_by_the_cube_root_of_three_halves() -> None:
    """Source (b) : identité, vraie sur toute série dont le plafond ne mord pas.

    Les deux longueurs ne diffèrent que par la constante c_i, valant 2 pour le
    bootstrap stationnaire et 4/3 pour le circulaire. Le rapport des deux vaut
    donc (2 / (4/3))^(1/3) = (3/2)^(1/3) = 1,144714.
    """
    series = _ar1(1200, 0.5, make_generator(7))
    selection = politis_white_block_sizes(series)
    assert not selection.truncated
    assert selection.circular / selection.stationary == pytest.approx(1.5 ** (1 / 3), rel=1e-12)


def test_optimal_block_size_approaches_the_ar1_population_value() -> None:
    r"""Source (b) : forme fermée de la règle sur un AR(1) de population.

    Les autocovariances de population valent gamma(k) = gamma(0) rho^|k|. La
    fenêtre à sommet plat tendant vers 1, les deux grandeurs du papier valent

        g(0) = gamma(0) (1 + rho) / (1 - rho)
        G    = 2 gamma(0) rho / (1 - rho)^2

    de sorte que G / g(0) = 2 rho / (1 - rho^2). La longueur optimale du
    bootstrap stationnaire vaut alors n^(1/3) × (G / g(0))^(2/3). Pour rho = 0,5
    et n = 4 000 : 2 × 0,5 / 0,75 = 1,33333, puis 1,33333^(2/3) = 1,21141, et
    4 000^(1/3) = 15,8740, soit 19,229.

    Tolérance : la règle converge à vitesse cubique et son estimateur est bruité
    à taille finie. La borne retenue est un facteur 1,5 dans les deux sens, soit
    l'intervalle allant de 12,8 à 28,8. C'est un contrôle d'ordre de grandeur,
    déclaré comme tel, et non un contrôle de précision.
    """
    rho, n = 0.5, 4000
    series = _ar1(n, rho, make_generator(123))
    population = n ** (1 / 3) * (2 * rho / (1 - rho**2)) ** (2 / 3)
    assert population == pytest.approx(19.229, abs=0.01)
    measured = optimal_block_size(series, bootstrap=BootstrapMethod.STATIONARY)
    assert population / 1.5 <= measured <= population * 1.5


def test_optimal_block_size_falls_to_the_floor_on_white_noise() -> None:
    """Source (b) : sur du bruit blanc, la grandeur G tend vers zéro, donc la longueur aussi.

    Aucun bloc n'est utile quand il n'y a rien à préserver. Le plancher déclaré
    ramène alors la longueur à 1, c'est-à-dire au bootstrap i.i.d.
    """
    noise = make_generator(99).standard_normal(3000)
    selection = politis_white_block_sizes(noise)
    assert selection.stationary < 2.0
    assert optimal_block_size(noise) == pytest.approx(1.0)


def test_optimal_block_size_grows_with_persistence() -> None:
    """Source (b) : la longueur de population croît en 2 rho / (1 - rho²), donc en rho.

    Le contrôle est monotone et n'exige aucune tolérance chiffrée : plus la série
    est persistante, plus le bloc doit être long pour emporter la dépendance.
    """
    generators = child_generators(SEED, 3)
    sizes = [
        optimal_block_size(_ar1(3000, rho, generator))
        for rho, generator in zip((0.1, 0.5, 0.8), generators, strict=True)
    ]
    assert sizes[0] < sizes[1] < sizes[2]


def test_optimal_block_size_rejects_an_unknown_rule() -> None:
    """Une règle non implémentée lève au lieu de retomber sur un défaut silencieux."""
    with pytest.raises(ConfigError, match="règle de sélection inconnue"):
        optimal_block_size(np.arange(40.0), method="hall_horowitz_jing")  # type: ignore[arg-type]


def test_optimal_block_size_rejects_the_iid_method() -> None:
    """Le bootstrap i.i.d. n'a pas de longueur de bloc, et le dire vaut mieux que rendre 1."""
    series = _ar1(200, 0.3, make_generator(5))
    with pytest.raises(ConfigError, match="n'a pas de longueur de bloc"):
        optimal_block_size(series, bootstrap=BootstrapMethod.IID)


def test_politis_white_refuses_a_two_dimensional_input() -> None:
    """La règle vaut par série ; l'appliquer à un tableau demanderait une agrégation inventée."""
    with pytest.raises(ConfigError, match="colonne par colonne"):
        politis_white_block_sizes(np.zeros((40, 2)) + np.arange(40.0)[:, None])


def test_politis_white_refuses_a_short_series() -> None:
    """Sous seize observations, les sommes d'autocovariances de la règle sont vides."""
    with pytest.raises(InsufficientDataError, match="au moins 16 observations"):
        politis_white_block_sizes(np.arange(12.0))


# --------------------------------------------------------------------------- #
# Distribution bootstrap d'une statistique
# --------------------------------------------------------------------------- #


def test_iid_bootstrap_variance_of_the_mean_matches_its_closed_form() -> None:
    r"""Source (b) : la variance bootstrap de la moyenne se calcule exactement.

    Sous le bootstrap i.i.d., la moyenne d'un rééchantillon a pour variance
    conditionnelle sigma_n^2 / n, où sigma_n^2 est la variance empirique de
    dénominateur n. Ce n'est pas une approximation : c'est la variance d'une
    moyenne de n tirages i.i.d. dans la loi empirique.

    Tolérance : l'erreur de Monte-Carlo sur une variance estimée à partir de B
    répliques a une erreur type relative de racine(2 / (B - 1)). Avec B = 4 000,
    cela vaut 2,24 %. La borne retenue est trois fois cela, soit 6,7 %, arrondie
    à 7 %.
    """
    sample = make_generator(31).standard_normal(120)
    distribution = bootstrap_statistic(sample, np.mean, BootstrapMethod.IID, 4000, make_generator(SEED))
    expected_variance = float(np.var(sample, ddof=0)) / sample.size
    assert distribution.standard_error**2 == pytest.approx(expected_variance, rel=0.07)
    assert distribution.observed == pytest.approx(float(np.mean(sample)), abs=1e-15)


def test_standard_error_and_bias_use_the_published_denominators() -> None:
    """Source (a) : calcul à la main sur cinq répliques choisies.

    Répliques 1, 2, 3, 4 et 5. Leur moyenne vaut 3, et la somme des carrés des
    écarts vaut 4 + 1 + 0 + 1 + 4 = 10. L'erreur type bootstrap emploie le
    dénominateur d'échantillon B - 1 = 4, donc la variance vaut 2,5 et l'erreur
    type racine(2,5) = 1,5811388. Avec un observé de 2,5, le biais vaut
    3 - 2,5 = 0,5, et la médiane des répliques vaut 3.

    Le contrôle est exact parce qu'aucune tolérance de Monte-Carlo ne sépare le
    dénominateur B du dénominateur B - 1 : leur écart relatif est de 1/(2B).
    """
    distribution = BootstrapDistribution(
        observed=2.5,
        replicates=np.array([1.0, 2.0, 3.0, 4.0, 5.0]),
        method=BootstrapMethod.IID,
        n_resamples=5,
        n_observations=20,
        block_size=None,
    )
    assert distribution.standard_error == pytest.approx(math.sqrt(2.5), abs=1e-12)
    assert distribution.standard_error == pytest.approx(1.5811388, abs=1e-7)
    assert distribution.bias == pytest.approx(0.5, abs=1e-12)
    assert distribution.quantile(0.5) == pytest.approx(3.0, abs=1e-12)


def test_bootstrap_bias_of_the_mean_is_zero() -> None:
    """Source (b) : l'espérance de la moyenne rééchantillonnée EST la moyenne observée.

    Le biais bootstrap de la moyenne est donc nul en espérance, et ce qui reste
    est du bruit de Monte-Carlo.

    Tolérance : l'erreur type du biais vaut sigma_n / racine(n × B). Avec les
    valeurs du test, la borne retenue est quatre fois cette quantité, calculée
    ci-dessous plutôt que posée en dur.
    """
    sample = make_generator(17).standard_normal(150)
    n_resamples = 3000
    distribution = bootstrap_statistic(
        sample, np.mean, BootstrapMethod.IID, n_resamples, make_generator(SEED)
    )
    standard_error_of_bias = float(np.std(sample, ddof=0)) / math.sqrt(sample.size * n_resamples)
    assert abs(distribution.bias) < 4.0 * standard_error_of_bias


def test_bootstrap_statistic_reuses_the_laboratory_sharpe_ratio() -> None:
    """La statistique passée est appelée telle quelle, ratio de Sharpe compris.

    Source (b) : la statistique observée doit valoir exactement ce que rend
    ``quantlab.analytics.ratios.sharpe_ratio`` sur les données d'origine. Le
    ratio n'est réimplémenté nulle part, conformément à la règle 12.
    """
    returns = make_generator(41).normal(0.0005, 0.01, size=400)

    def annual_sharpe(values: np.ndarray) -> float:
        return sharpe_ratio(pd.Series(values), frequency=Frequency.DAILY)

    distribution = bootstrap_statistic(
        returns, annual_sharpe, BootstrapMethod.STATIONARY, 200, make_generator(SEED), mean_block_size=5.0
    )
    assert distribution.observed == pytest.approx(annual_sharpe(returns), abs=1e-15)
    assert distribution.replicates.shape == (200,)
    assert distribution.block_size == pytest.approx(5.0)
    assert distribution.method is BootstrapMethod.STATIONARY


def test_block_bootstrap_recovers_the_dependence_the_iid_bootstrap_loses() -> None:
    r"""Test de simulation : la vérité est connue en forme fermée sur un AR(1).

    Source (b), deux formes fermées.

    D'abord la variance vraie de la moyenne d'un AR(1), calculée exactement par
    ``_ar1_variance_of_mean``.

    Ensuite l'espérance de la variance bootstrap i.i.d. Pour tout processus
    stationnaire, E[(1/n) somme (x_i - moyenne)^2] = gamma(0) - Var(moyenne). La
    variance bootstrap i.i.d. de la moyenne valant sigma_n^2 / n, son espérance
    vaut donc exactement (gamma(0) - Var(moyenne)) / n.

    Pour rho = 0,5 et n = 800, la somme des autocovariances se calcule à la main.
    gamma(0) = 1 / 0,75 = 1,33333. La double somme vaut n fois la somme des rho^k,
    soit 800, moins la somme des k rho^k, soit 2, donc 798. La variance vraie de
    la moyenne vaut (800 × 1,33333 + 2 × 1,33333 × 798) / 800^2 = 3194,67 / 640 000
    = 0,0049917. L'espérance de la variance i.i.d. vaut alors
    (1,33333 - 0,0049917) / 800 = 0,00166043. Le bootstrap i.i.d. annonce donc une
    variance 3,01 fois trop petite, soit une erreur type 42,3 % trop petite.

    Le bloc de 15 est un choix déclaré, du même ordre que ce que rend la règle de
    Politis et White sur ces trajectoires, et il n'est pas issu d'un réglage.

    Tolérances déclarées. Sur 60 trajectoires indépendantes, la dispersion de la
    variance i.i.d. moyenne est dominée par celle de sigma_n^2, dont l'erreur
    type relative vaut racine(2 / n_eff) avec n_eff de l'ordre de n(1-rho)/(1+rho)
    = 267, soit 8,7 % par trajectoire et 1,1 % sur soixante. La borne retenue est
    5 %, soit plus de quatre fois cela. Pour le bootstrap circulaire, la borne est
    de 20 %. Son estimateur est celui de Bartlett, dont le biais à la baisse est
    d'ordre 1/b, soit environ 7 % pour un bloc de 15. Le bruit d'estimation
    s'ajoute à ce biais.
    """
    rho, n, n_paths, n_resamples = 0.5, 800, 60, 250
    gamma0 = 1.0 / (1.0 - rho**2)
    true_variance = _ar1_variance_of_mean(n, rho)
    assert true_variance == pytest.approx(0.0049917, abs=1e-6)
    expected_iid_variance = (gamma0 - true_variance) / n
    assert expected_iid_variance == pytest.approx(0.00166043, abs=1e-7)

    block = 15
    generators = child_generators(SEED, 2 * n_paths)
    iid_variances = np.empty(n_paths)
    block_variances = np.empty(n_paths)
    for path in range(n_paths):
        series = _ar1(n, rho, generators[2 * path])
        draw = generators[2 * path + 1]
        iid_variances[path] = np.var(iid_bootstrap(series, n_resamples, draw).mean(axis=1), ddof=1)
        block_variances[path] = np.var(
            block_bootstrap(series, block, n_resamples, draw, circular=True).mean(axis=1), ddof=1
        )

    assert iid_variances.mean() == pytest.approx(expected_iid_variance, rel=0.05)
    assert block_variances.mean() == pytest.approx(true_variance, rel=0.20)
    # L'erreur relative du bootstrap par blocs est strictement plus petite.
    assert abs(block_variances.mean() / true_variance - 1.0) < abs(iid_variances.mean() / true_variance - 1.0)


# --------------------------------------------------------------------------- #
# Intervalles de confiance
# --------------------------------------------------------------------------- #


def test_percentile_interval_reads_the_quantiles_of_the_replicates() -> None:
    """Source (b) : par définition, les bornes SONT les quantiles empiriques."""
    sample = make_generator(13).standard_normal(80)
    distribution = bootstrap_statistic(sample, np.mean, BootstrapMethod.IID, 500, make_generator(2))
    interval = bootstrap_confidence_interval(distribution, 0.90, "percentile")
    assert interval.low == pytest.approx(float(np.quantile(distribution.replicates, 0.05)))
    assert interval.high == pytest.approx(float(np.quantile(distribution.replicates, 0.95)))
    assert interval.width == pytest.approx(interval.high - interval.low)


def test_basic_interval_is_the_percentile_interval_reflected() -> None:
    """Source (b) : identité. La somme des bornes opposées vaut deux fois l'observé.

    L'intervalle basique valant [2 theta - q_haut, 2 theta - q_bas], sa borne
    basse et la borne haute du percentile somment à 2 theta, et réciproquement.
    """
    sample = make_generator(23).standard_normal(90)
    distribution = bootstrap_statistic(sample, np.mean, BootstrapMethod.IID, 600, make_generator(4))
    percentile = bootstrap_confidence_interval(distribution, 0.95, "percentile")
    basic = bootstrap_confidence_interval(distribution, 0.95, "basic")
    two_theta = 2.0 * distribution.observed
    assert basic.low + percentile.high == pytest.approx(two_theta, abs=1e-12)
    assert basic.high + percentile.low == pytest.approx(two_theta, abs=1e-12)
    assert basic.width == pytest.approx(percentile.width, abs=1e-12)


@pytest.mark.slow
@pytest.mark.parametrize("method", ["percentile", "basic"])
def test_interval_covers_the_true_mean_about_ninety_five_percent_of_the_time(method: str) -> None:
    """Test de couverture sur des données SIMULÉES indépendantes, vérité connue.

    Les données sont normales de moyenne 0,5 et d'écart type 2, tirées i.i.d.,
    donc le bootstrap naïf est légitime et la vraie moyenne vaut 0,5 par
    construction.

    Valeur attendue, source (b). La couverture visée est 0,95. À taille finie
    l'intervalle par percentile est légèrement trop étroit, la variance bootstrap
    divisant par n au lieu de n - 1. À n = 200, sa demi-largeur vaut
    1,96 × racine(199/200) / t(0,975 ; 199) = 1,96 × 0,997494 / 1,971957 = 0,99146
    fois celle de l'intervalle de Student. Le manque de couverture qui en résulte
    est de 0,2 point, soit une couverture attendue de 0,948.

    Tolérance, source (b). Le nombre de succès sur 200 répétitions suit une loi
    binomiale d'erreur type racine(0,95 × 0,05 / 200) = 0,0154. La borne retenue
    est trois erreurs types, soit 0,046, ce qui laisse l'intervalle allant de
    0,904 à 0,996. La couverture attendue de 0,948 y est très largement.
    """
    true_mean, true_std = 0.5, 2.0
    n_observations, n_repetitions, n_resamples = 200, 200, 399
    generators = child_generators(SEED, 2 * n_repetitions)
    covered = 0
    for repetition in range(n_repetitions):
        sample = generators[2 * repetition].normal(true_mean, true_std, size=n_observations)
        distribution = bootstrap_statistic(
            sample, np.mean, BootstrapMethod.IID, n_resamples, generators[2 * repetition + 1]
        )
        interval = bootstrap_confidence_interval(distribution, 0.95, method)  # type: ignore[arg-type]
        covered += int(interval.contains(true_mean))
    coverage = covered / n_repetitions
    assert coverage == pytest.approx(0.95, abs=0.046)


def test_interval_rejects_an_impossible_confidence_level() -> None:
    """Un niveau de 1 demanderait un intervalle infini, et un niveau de 0 un point."""
    sample = np.arange(20.0)
    distribution = bootstrap_statistic(sample, np.mean, BootstrapMethod.IID, 50, make_generator(1))
    with pytest.raises(ConfigError, match="strictement entre 0 et 1"):
        bootstrap_confidence_interval(distribution, 1.0)
    with pytest.raises(ConfigError, match="méthode d'intervalle inconnue"):
        bootstrap_confidence_interval(distribution, 0.95, "bca")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Valeur p
# --------------------------------------------------------------------------- #


def test_pvalue_is_one_when_the_null_equals_the_observed_statistic() -> None:
    """Source (b) : identité. Un écart observé nul est atteint ou dépassé par toutes les répliques.

    La valeur p vaut alors (1 + B) / (B + 1) = 1 exactement, quelle que soit la
    distribution bootstrap.
    """
    sample = make_generator(19).standard_normal(100)
    distribution = bootstrap_statistic(sample, np.mean, BootstrapMethod.IID, 250, make_generator(6))
    assert bootstrap_pvalue(distribution, distribution.observed) == pytest.approx(1.0, abs=1e-15)


def test_pvalue_counts_the_ties_as_exceedances() -> None:
    """Source (a) : calcul à la main, avec des égalités posées exprès.

    Davison et Hinkley (1997) comptent les répliques dont l'écart ATTEINT ou
    dépasse l'écart observé. Le cas d'égalité décide du niveau du test sur une
    statistique discrète, un taux de réussite par exemple, où les égalités sont
    fréquentes. Compter au sens strict rend une valeur p trop petite, donc un
    test qui rejette trop souvent.

    Le calcul. L'observé vaut 1 et la valeur nulle 0, donc l'écart observé vaut
    1. Les répliques 0, 2, 1,5, 1 et 3 donnent les écarts 1, 1, 0,5, 0 et 2.
    Trois de ces écarts atteignent ou dépassent 1, à savoir 1, 1 et 2. La valeur
    p vaut donc (1 + 3) / (5 + 1) = 4/6 = 0,6666667. Au sens strict elle vaudrait
    2/6, soit la moitié.
    """
    distribution = BootstrapDistribution(
        observed=1.0,
        replicates=np.array([0.0, 2.0, 1.5, 1.0, 3.0]),
        method=BootstrapMethod.IID,
        n_resamples=5,
        n_observations=30,
        block_size=None,
    )
    assert bootstrap_pvalue(distribution, 0.0) == pytest.approx(4.0 / 6.0, abs=1e-15)


def test_pvalue_reaches_its_floor_on_an_overwhelming_effect() -> None:
    """Source (b) : la valeur p ne peut pas descendre sous 1 / (B + 1).

    Avec 499 répliques, le plancher vaut 1/500 = 0,002. Une moyenne de 5 sur des
    données d'écart type 1 et de taille 200 est à 70 erreurs types de zéro, donc
    aucune réplique ne s'en écarte autant.
    """
    sample = make_generator(29).normal(5.0, 1.0, size=200)
    distribution = bootstrap_statistic(sample, np.mean, BootstrapMethod.IID, 499, make_generator(8))
    assert bootstrap_pvalue(distribution, 0.0) == pytest.approx(1.0 / 500.0, abs=1e-15)


def test_pvalue_counts_the_recentred_deviations() -> None:
    """Source (a) : recomptage à la main de la formule de Davison et Hinkley.

    Le test refait le comptage à partir des répliques, sans réutiliser la
    fonction. On compte les répliques dont l'écart à l'observé atteint l'écart
    entre l'observé et la valeur nulle. On ajoute un, puis on divise par B plus
    un.
    """
    sample = make_generator(37).normal(0.15, 1.0, size=150)
    distribution = bootstrap_statistic(sample, np.mean, BootstrapMethod.IID, 300, make_generator(9))
    null_value = 0.0
    deviations = np.abs(distribution.replicates - distribution.observed)
    hand_count = int(np.sum(deviations >= abs(distribution.observed - null_value)))
    expected = (1 + hand_count) / (300 + 1)
    assert bootstrap_pvalue(distribution, null_value) == pytest.approx(expected, abs=1e-15)


@pytest.mark.slow
def test_pvalue_is_approximately_uniform_under_a_true_null() -> None:
    """Test de simulation sous l'hypothèse nulle vraie, données i.i.d. de moyenne nulle.

    Valeur attendue, source (b) : une valeur p bien calibrée est uniforme sous
    l'hypothèse nulle, donc la part des répétitions sous 0,05 vaut 0,05.

    Tolérance : sur 300 répétitions, l'erreur type binomiale vaut
    racine(0,05 × 0,95 / 300) = 0,0126. La borne retenue est trois erreurs types,
    soit 0,038. Le bootstrap par percentile étant légèrement trop étroit à
    n = 100, le taux de rejet attendu est un peu au-dessus de 0,05, ce que la
    borne absorbe.
    """
    n_repetitions, n_resamples = 300, 199
    generators = child_generators(SEED + 1, 2 * n_repetitions)
    rejections = 0
    for repetition in range(n_repetitions):
        sample = generators[2 * repetition].standard_normal(100)
        distribution = bootstrap_statistic(
            sample, np.mean, BootstrapMethod.IID, n_resamples, generators[2 * repetition + 1]
        )
        rejections += int(bootstrap_pvalue(distribution, 0.0) < 0.05)
    assert rejections / n_repetitions == pytest.approx(0.05, abs=0.038)


# --------------------------------------------------------------------------- #
# Contrôles d'entrée
# --------------------------------------------------------------------------- #


def test_missing_values_are_refused_rather_than_dropped() -> None:
    """Retirer une ligne souderait deux dates non voisines, ce que le module refuse."""
    with pytest.raises(DataQualityError, match="valeurs manquantes"):
        iid_bootstrap([1.0, np.nan, 3.0], 10, make_generator(SEED))


def test_a_single_observation_is_refused() -> None:
    """Un échantillon d'une observation rend toujours le même rééchantillon."""
    with pytest.raises(InsufficientDataError, match="au moins 2 observations"):
        iid_bootstrap([1.0], 10, make_generator(SEED))


def test_a_three_dimensional_input_is_refused() -> None:
    """Le module range les observations en lignes ; un cube n'a pas d'axe du temps déclaré."""
    with pytest.raises(ConfigError, match="dimension reçue 3"):
        iid_bootstrap(np.zeros((3, 4, 5)), 10, make_generator(SEED))


def test_a_legacy_random_state_is_refused() -> None:
    """Un ``RandomState`` casserait la garantie de reproductibilité sans rien signaler."""
    with pytest.raises(ConfigError, match=r"numpy\.random\.Generator"):
        iid_bootstrap(np.arange(10.0), 5, np.random.RandomState(0))  # type: ignore[arg-type]


def test_a_block_method_without_a_block_size_is_refused() -> None:
    """Aucun défaut silencieux : la longueur de bloc est un choix, pas une convention."""
    with pytest.raises(ConfigError, match="exige block_size"):
        bootstrap_indices(50, BootstrapMethod.CIRCULAR_BLOCK, 10, make_generator(SEED))
    with pytest.raises(ConfigError, match="exige mean_block_size"):
        bootstrap_indices(50, BootstrapMethod.STATIONARY, 10, make_generator(SEED))


def test_a_non_finite_null_value_is_refused() -> None:
    """Une hypothèse nulle infinie rendrait une valeur p au plancher sans signification."""
    distribution = bootstrap_statistic(
        np.arange(20.0), np.mean, BootstrapMethod.IID, 50, make_generator(SEED)
    )
    with pytest.raises(ConfigError, match="null_value doit être fini"):
        bootstrap_pvalue(distribution, math.inf)


def test_a_statistic_that_is_not_finite_is_refused() -> None:
    """Une réplique infinie signale une statistique indéfinie, pas un résultat."""
    with pytest.raises(DataQualityError, match="nombre fini"):
        bootstrap_statistic(
            np.arange(20.0),
            lambda values: math.inf if values[0] == 0.0 else 1.0,
            BootstrapMethod.IID,
            200,
            make_generator(SEED),
        )


def test_quantile_refuses_a_probability_outside_zero_one() -> None:
    """Un quantile d'ordre 1,5 n'existe pas."""
    distribution = bootstrap_statistic(
        np.arange(20.0), np.mean, BootstrapMethod.IID, 30, make_generator(SEED)
    )
    with pytest.raises(ConfigError, match="entre 0 et 1"):
        distribution.quantile(1.5)


# --------------------------------------------------------------------------- #
# Propriétés (hypothesis)
# --------------------------------------------------------------------------- #

FINITE_VALUES = st.lists(
    st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False, width=64),
    min_size=2,
    max_size=40,
)


@given(
    values=FINITE_VALUES,
    n_resamples=st.integers(min_value=1, max_value=5),
    method=st.sampled_from(list(BootstrapMethod)),
    block=st.integers(min_value=1, max_value=6),
)
@settings(max_examples=300, deadline=None)
def test_every_resampled_value_comes_from_the_sample(
    values: list[float], n_resamples: int, method: BootstrapMethod, block: int
) -> None:
    """Propriété : un rééchantillonnage ne crée aucune valeur nouvelle.

    Source (b) : le bootstrap indexe l'échantillon, donc l'ensemble des valeurs
    rendues est inclus dans celui des valeurs de départ. La propriété tient pour
    les quatre méthodes et pour toute longueur de bloc.
    """
    sample = np.asarray(values, dtype=float)
    generator = make_generator(SEED)
    if method is BootstrapMethod.IID:
        resamples = iid_bootstrap(sample, n_resamples, generator)
    elif method is BootstrapMethod.STATIONARY:
        resamples = stationary_bootstrap(sample, float(block) + 1.0, n_resamples, generator)
    else:
        circular = method is BootstrapMethod.CIRCULAR_BLOCK
        usable = block if circular else min(block, sample.size)
        resamples = block_bootstrap(sample, usable, n_resamples, generator, circular=circular)
    assert resamples.shape == (n_resamples, sample.size)
    assert np.isin(resamples, sample).all()


@given(
    size=st.integers(min_value=2, max_value=60),
    block=st.integers(min_value=1, max_value=25),
    n_resamples=st.integers(min_value=1, max_value=4),
)
@settings(max_examples=200, deadline=None)
def test_circular_resamples_keep_the_requested_length(size: int, block: int, n_resamples: int) -> None:
    """Propriété : la version circulaire rend toujours la longueur demandée.

    Source (b) : les blocs sont concaténés puis tronqués, et le repli sur
    l'anneau rend tout départ admissible. Aucune combinaison de longueurs ne peut
    donc raccourcir le résultat, y compris quand le bloc dépasse la série.
    """
    sample = np.arange(float(size))
    resamples = block_bootstrap(sample, block, n_resamples, make_generator(SEED), circular=True)
    assert resamples.shape == (n_resamples, size)


@given(
    size=st.integers(min_value=2, max_value=50),
    mean_block=st.floats(min_value=1.5, max_value=20.0),
)
@settings(max_examples=200, deadline=None)
def test_stationary_indices_stay_in_range(size: int, mean_block: float) -> None:
    """Propriété : les indices du bootstrap stationnaire restent dans la série.

    Source (b) : le repli modulo la longueur borne les indices, même quand un
    bloc géométrique fait plusieurs fois le tour de l'anneau.
    """
    indices = bootstrap_indices(
        size, BootstrapMethod.STATIONARY, 3, make_generator(SEED), mean_block_size=mean_block
    )
    assert indices.shape == (3, size)
    assert indices.min() >= 0
    assert indices.max() < size

"""Contrôles de ``quantlab.signals.standardize``.

Aucune valeur attendue de ce fichier ne vient de la sortie du code. Chacune
porte sa source en commentaire : (a) calcul à la main, (b) identité
mathématique, (c) valeur publiée, (d) bibliothèque indépendante.

Le panel de référence porte dix actifs et trois dates, et les z-scores comme les
rangs de sa première ligne sont calculés à la main dans les commentaires.
"""

from __future__ import annotations

import math
from collections.abc import Callable

import hypothesis.strategies as st
import numpy as np
import pandas as pd
import pytest
from hypothesis import assume, given, settings
from scipy.stats import norm

from quantlab.core.errors import (
    ConfigError,
    DataQualityError,
    InsufficientDataError,
    LookAheadError,
)
from quantlab.signals.standardize import (
    MAD_SCALE,
    WeightingMethod,
    cross_sectional_rank,
    cross_sectional_zscore,
    demean_by_group,
    neutralize_to_zero_net,
    robust_zscore,
    scale_to_gross,
    scale_to_net,
    signal_to_weights,
    winsorize,
)

ASSETS = list("ABCDEFGHIJ")
DATES = pd.to_datetime(["2020-01-31", "2020-02-29", "2020-03-31"])

#: Le panel de référence, construit à la main.
#: Ligne 1 : les entiers de 1 à 10, un par actif, sans ex aequo.
#: Ligne 2 : la valeur 3 partout, donc une coupe constante.
#: Ligne 3 : quatre actifs renseignés seulement, sous le plancher de cinq.
PANEL = pd.DataFrame(
    [
        [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
        [3.0] * 10,
        [1.0, 2.0, 3.0, 4.0, *([float("nan")] * 6)],
    ],
    index=DATES,
    columns=ASSETS,
)

# (a) Calcul à la main sur la première ligne du panel.
# Moyenne : (1 + 2 + ... + 10) / 10 = 55 / 10 = 5,5.
# Somme des carrés des écarts : 2 x (4,5^2 + 3,5^2 + 2,5^2 + 1,5^2 + 0,5^2)
#   = 2 x (20,25 + 12,25 + 6,25 + 2,25 + 0,25) = 2 x 41,25 = 82,5.
# Variance d'échantillon : 82,5 / 9. Écart type : racine de ce nombre.
ECART_TYPE_LIGNE_1 = math.sqrt(82.5 / 9.0)

# (a) Rangs de la première ligne : 1 à 10, ramenés à [-1, 1] par
# -1 + (r - 1) x 2 / 9, ce qui donne les neuvièmes impairs.
RANGS_LIGNE_1 = np.array([-1.0, -7 / 9, -5 / 9, -3 / 9, -1 / 9, 1 / 9, 3 / 9, 5 / 9, 7 / 9, 1.0])


# --------------------------------------------------------------------------
# Le z-score transversal
# --------------------------------------------------------------------------


def test_zscore_premiere_ligne_calculee_a_la_main() -> None:
    """(a) Calcul à la main : (x - 5,5) / racine(82,5 / 9)."""
    resultat = cross_sectional_zscore(PANEL)
    ligne = resultat.iloc[0]
    assert ligne["A"] == pytest.approx(-4.5 / ECART_TYPE_LIGNE_1, abs=1e-15)
    assert ligne["E"] == pytest.approx(-0.5 / ECART_TYPE_LIGNE_1, abs=1e-15)
    assert ligne["J"] == pytest.approx(4.5 / ECART_TYPE_LIGNE_1, abs=1e-15)


def test_zscore_moyenne_nulle_et_ecart_type_unitaire() -> None:
    """(b) Identité : une coupe centrée réduite a pour moments 0 et 1."""
    ligne = cross_sectional_zscore(PANEL).iloc[0]
    assert float(ligne.mean()) == pytest.approx(0.0, abs=1e-15)
    assert float(ligne.std(ddof=1)) == pytest.approx(1.0, abs=1e-15)


def test_zscore_ligne_constante_rend_nan() -> None:
    """(b) Identité : la dispersion d'une coupe constante est nulle, la division n'existe pas."""
    assert bool(cross_sectional_zscore(PANEL).iloc[1].isna().all())


def test_zscore_ligne_trop_mince_rend_nan_et_le_seuil_en_est_la_cause() -> None:
    """(a) La troisième ligne porte quatre actifs, sous le plancher de cinq.

    Le second volet prouve que le ``NaN`` vient du plancher et non d'un autre
    défaut : abaisser le seuil à quatre rend le z-score calculé à la main.
    Moyenne des quatre valeurs : (1 + 2 + 3 + 4) / 4 = 2,5.
    Somme des carrés des écarts : 2 x (1,5^2 + 0,5^2) = 2 x 2,5 = 5.
    Variance d'échantillon : 5 / 3.
    """
    assert bool(cross_sectional_zscore(PANEL).iloc[2].isna().all())
    permissif = cross_sectional_zscore(PANEL, min_names=4).iloc[2]
    assert permissif["A"] == pytest.approx(-1.5 / math.sqrt(5.0 / 3.0), abs=1e-15)
    assert bool(permissif[["E", "F", "G", "H", "I", "J"]].isna().all())


def test_zscore_invariant_par_transformation_affine_croissante() -> None:
    """(b) Identité : le z-score de a x + b vaut celui de x pour tout a strictement positif."""
    attendu = cross_sectional_zscore(PANEL)
    obtenu = cross_sectional_zscore(PANEL * 7.0 + 13.0)
    pd.testing.assert_frame_equal(obtenu, attendu, atol=1e-14, rtol=1e-14)


def test_zscore_ddof_change_le_denominateur_dans_le_rapport_connu() -> None:
    """(b) Identité : s(ddof=0) = s(ddof=1) x racine((n-1)/n), donc z est multiplié par l'inverse."""
    avec_un = cross_sectional_zscore(PANEL).iloc[0]
    avec_zero = cross_sectional_zscore(PANEL, ddof=0).iloc[0]
    rapport = math.sqrt(10.0 / 9.0)
    np.testing.assert_allclose(avec_zero.to_numpy(), avec_un.to_numpy() * rapport, atol=1e-14)


def test_zscore_refuse_un_ddof_negatif() -> None:
    """(b) Un degré de liberté négatif n'a pas de sens."""
    with pytest.raises(ConfigError, match="ddof"):
        cross_sectional_zscore(PANEL, ddof=-1)


def test_zscore_refuse_un_plancher_sous_deux() -> None:
    """(b) Une dispersion d'échantillon exige au moins deux points."""
    with pytest.raises(ConfigError, match="min_names"):
        cross_sectional_zscore(PANEL, min_names=1)


@given(
    valeurs=st.lists(
        st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
        min_size=5,
        max_size=20,
    )
)
@settings(deadline=None, max_examples=200)
def test_zscore_propriete_des_deux_premiers_moments(valeurs: list[float]) -> None:
    """(b) Propriété : sur toute coupe non dégénérée, moyenne nulle et écart type unitaire."""
    tableau = np.asarray(valeurs, dtype=float)
    echelle = max(1.0, float(np.abs(tableau).max()))
    assume(float(tableau.std(ddof=1)) > 1e-6 * echelle)
    ligne = cross_sectional_zscore(pd.DataFrame([tableau])).iloc[0].to_numpy()
    assert float(ligne.mean()) == pytest.approx(0.0, abs=1e-8)
    assert float(ligne.std(ddof=1)) == pytest.approx(1.0, rel=1e-8)


# --------------------------------------------------------------------------
# Le rang transversal
# --------------------------------------------------------------------------


def test_rang_premiere_ligne_calcule_a_la_main() -> None:
    """(a) Calcul à la main : -1 + (r - 1) x 2 / 9 sur les rangs 1 à 10."""
    np.testing.assert_allclose(cross_sectional_rank(PANEL).iloc[0].to_numpy(), RANGS_LIGNE_1, atol=1e-15)


def test_rang_ligne_constante_rend_le_milieu_de_l_intervalle() -> None:
    """(a) Tous les rangs moyens valent (n + 1) / 2 = 5,5, donc -1 + 4,5 x 2 / 9 = 0."""
    np.testing.assert_array_equal(cross_sectional_rank(PANEL).iloc[1].to_numpy(), np.zeros(10))


def test_rang_ligne_trop_mince_rend_nan() -> None:
    """(a) Quatre actifs renseignés sous un plancher de cinq."""
    assert bool(cross_sectional_rank(PANEL).iloc[2].isna().all())
    permissif = cross_sectional_rank(PANEL, min_names=4).iloc[2]
    # (a) Quatre noms, rangs 1 à 4, donc -1 + (r - 1) x 2 / 3.
    np.testing.assert_allclose(
        permissif[["A", "B", "C", "D"]].to_numpy(), np.array([-1.0, -1 / 3, 1 / 3, 1.0]), atol=1e-15
    )


def test_rang_ex_aequo_moyennes_calcules_a_la_main() -> None:
    """(a) Deux ex aequo au bas du classement reçoivent le rang 1,5.

    Rang normalisé : -1 + (1,5 - 1) x 2 / 9 = -1 + 1/9 = -8/9.
    """
    panel = PANEL.copy()
    panel.iloc[0, 1] = 1.0
    obtenu = cross_sectional_rank(panel).iloc[0]
    assert obtenu["A"] == pytest.approx(-8 / 9, abs=1e-15)
    assert obtenu["B"] == pytest.approx(-8 / 9, abs=1e-15)


def test_rang_echelle_personnalisee() -> None:
    """(b) Identité : sur une coupe sans ex aequo, le minimum atteint a et le maximum b."""
    obtenu = cross_sectional_rank(PANEL, scale=(0.0, 1.0)).iloc[0]
    assert float(obtenu.min()) == pytest.approx(0.0, abs=1e-15)
    assert float(obtenu.max()) == pytest.approx(1.0, abs=1e-15)
    # (a) Le troisième actif porte le rang 3, donc (3 - 1) / 9 = 2/9.
    assert obtenu["C"] == pytest.approx(2 / 9, abs=1e-15)


def test_rang_refuse_une_methode_inconnue_et_une_echelle_inversee() -> None:
    """(b) La méthode ``dense`` ne remplit pas l'intervalle, elle est refusée."""
    with pytest.raises(ConfigError, match="method"):
        cross_sectional_rank(PANEL, method="dense")  # type: ignore[arg-type]
    with pytest.raises(ConfigError, match="scale"):
        cross_sectional_rank(PANEL, scale=(1.0, -1.0))


@given(valeurs=st.lists(st.integers(min_value=-1000, max_value=1000), unique=True, min_size=5, max_size=15))
@settings(deadline=None, max_examples=200)
def test_rang_invariant_par_transformation_strictement_croissante(valeurs: list[int]) -> None:
    """(b) Propriété : le rang de Spearman ne dépend que de l'ordre.

    Les deux transformations employées sont strictement croissantes sur les
    réels. Les entrées sont des entiers distincts sous mille en valeur absolue,
    si bien que 2 x + 7 et x^3 restent exacts en virgule flottante et ne peuvent
    créer aucun ex aequo.
    """
    panel = pd.DataFrame([np.asarray(valeurs, dtype=float)])
    attendu = cross_sectional_rank(panel)
    pd.testing.assert_frame_equal(cross_sectional_rank(panel * 2.0 + 7.0), attendu)
    pd.testing.assert_frame_equal(cross_sectional_rank(panel**3), attendu)


# --------------------------------------------------------------------------
# L'écrêtage
# --------------------------------------------------------------------------


def test_winsorize_bornes_calculees_a_la_main() -> None:
    """(a) Calcul à la main, interpolation linéaire sur dix valeurs ordonnées.

    Le quantile de niveau p se lit à la position p x (n - 1) du vecteur trié.
    Pour p = 0,1 et n = 10 : position 0,9, entre 1 et 2, donc 1 + 0,9 = 1,9.
    Pour p = 0,9 : position 8,1, entre 9 et 10, donc 9 + 0,1 = 9,1.
    """
    obtenu = winsorize(PANEL, lower=0.1, upper=0.9).iloc[0]
    assert obtenu["A"] == pytest.approx(1.9, abs=1e-15)
    assert obtenu["J"] == pytest.approx(9.1, abs=1e-15)
    np.testing.assert_array_equal(obtenu[list("BCDEFGHI")].to_numpy(), PANEL.iloc[0][list("BCDEFGHI")])


def _quantile_par_statistiques_d_ordre(valeurs: list[float], niveau: float) -> float:
    """Rend le quantile par la définition, sans passer par ``numpy``.

    La position vaut ``niveau x (n - 1)`` dans le vecteur trié, et la valeur
    s'interpole linéairement entre les deux statistiques d'ordre qui l'encadrent.
    C'est la convention ``linear``, celle que suit l'implémentation.

    Args:
        valeurs: les observations, sans valeur manquante.
        niveau: le niveau demandé, entre zéro et un.

    Returns:
        Le quantile interpolé.
    """
    trie = sorted(valeurs)
    position = niveau * (len(trie) - 1)
    bas = math.floor(position)
    haut = min(bas + 1, len(trie) - 1)
    return trie[bas] + (position - bas) * (trie[haut] - trie[bas])


def test_winsorize_bornes_contre_les_statistiques_d_ordre() -> None:
    """(a) Calcul indépendant : le quantile relu depuis sa définition, sans ``numpy``.

    Le contrôle précédent comparait ``numpy.nanquantile`` à lui-même, puisque
    l'implémentation appelle cette fonction. Il ne prouvait donc que la
    transmission des niveaux. La borne est ici recalculée à part, en Python pur.
    Sur les quatre valeurs 1, 2, 3 et 4 : la position du quantile à 25 % vaut
    0,75, donc la borne basse vaut 1 + 0,75 = 1,75 ; celle du quantile à 75 %
    vaut 2,25, donc la borne haute vaut 3 + 0,25 = 3,25.
    """
    presentes = [1.0, 2.0, 3.0, 4.0]
    basse = _quantile_par_statistiques_d_ordre(presentes, 0.25)
    haute = _quantile_par_statistiques_d_ordre(presentes, 0.75)
    assert basse == pytest.approx(1.75, abs=1e-15)
    assert haute == pytest.approx(3.25, abs=1e-15)
    obtenu = winsorize(PANEL, lower=0.25, upper=0.75).iloc[2]
    np.testing.assert_allclose(
        obtenu[["A", "B", "C", "D"]].to_numpy(), np.array([1.75, 2.0, 3.0, 3.25]), atol=1e-15
    )
    assert bool(obtenu[["E", "F", "G", "H", "I", "J"]].isna().all())


def test_winsorize_ne_supprime_aucune_observation() -> None:
    """(b) L'écrêtage borne, la troncature supprime : le compte des actifs ne bouge pas."""
    obtenu = winsorize(PANEL, lower=0.2, upper=0.8)
    assert obtenu.shape == PANEL.shape
    np.testing.assert_array_equal(obtenu.notna().to_numpy(), PANEL.notna().to_numpy())


def test_winsorize_bornes_extremes_laissent_le_panel_intact() -> None:
    """(b) Identité : le quantile 0 est le minimum et le quantile 1 le maximum."""
    pd.testing.assert_frame_equal(winsorize(PANEL, lower=0.0, upper=1.0), PANEL)


def test_winsorize_sur_l_axe_du_temps() -> None:
    """(a) Sur la colonne A, les trois valeurs 1, 3 et 1 donnent des quantiles connus.

    Vecteur trié : 1, 1, 3. Pour p = 0,5 et n = 3, la position vaut 1, donc la
    médiane vaut 1. Pour p = 1, la borne haute vaut 3. Aucun écrêtage ne peut
    donc laisser la valeur 3 en place sur cette colonne.
    """
    obtenu = winsorize(PANEL, lower=0.0, upper=0.5, axis="time", allow_lookahead=True)
    np.testing.assert_array_equal(obtenu["A"].to_numpy(), np.array([1.0, 1.0, 1.0]))


def test_winsorize_axe_du_temps_refuse_sans_aveu_de_fuite() -> None:
    """(b) La règle 1 du laboratoire : une lecture du futur lève ``LookAheadError``."""
    with pytest.raises(LookAheadError, match="time"):
        winsorize(PANEL, axis="time")


def test_winsorize_axe_du_temps_laisse_le_futur_entrer_dans_le_passe() -> None:
    """(a) Contre-exemple chiffré de la fuite que l'aveu autorise.

    Panel de deux dates et cinq actifs. La colonne du dernier actif porte 5 à la
    première date et 50 à la seconde. Le quantile bas à 10 % de la paire ordonnée
    5 puis 50 se lit à la position 0,1 x (2 - 1) = 0,1, donc il vaut
    5 + 0,1 x 45 = 9,5. La première date sort donc à 9,5 au lieu de 5.

    Remplacer la SEULE valeur de la seconde date par un million déplace ce même
    quantile à 5 + 0,1 x (1 000 000 - 5) = 100 004,5, et la première date le suit.
    Une donnée du futur décide donc de ce qui est publié pour le passé.
    """
    base = pd.DataFrame([[1.0, 2.0, 3.0, 4.0, 5.0], [10.0, 20.0, 30.0, 40.0, 50.0]])
    futur = base.copy()
    futur.iloc[1, 4] = 1e6
    avant = winsorize(base, lower=0.1, upper=0.9, axis="time", allow_lookahead=True)
    apres = winsorize(futur, lower=0.1, upper=0.9, axis="time", allow_lookahead=True)
    assert float(avant.iloc[0, 4]) == pytest.approx(9.5, abs=1e-12)
    assert float(apres.iloc[0, 4]) == pytest.approx(100004.5, abs=1e-9)


def test_winsorize_refuse_des_niveaux_mal_ordonnes_et_un_axe_inconnu() -> None:
    """(b) Les niveaux doivent vérifier 0 <= lower < upper <= 1."""
    with pytest.raises(ConfigError, match="lower"):
        winsorize(PANEL, lower=0.9, upper=0.1)
    with pytest.raises(ConfigError, match="axis"):
        winsorize(PANEL, axis="colonnes")  # type: ignore[arg-type]


@given(
    valeurs=st.lists(
        st.floats(min_value=-1e4, max_value=1e4, allow_nan=False, allow_infinity=False),
        min_size=5,
        max_size=20,
    )
)
@settings(deadline=None, max_examples=100)
def test_winsorize_propriete_de_monotonie(valeurs: list[float]) -> None:
    """(b) Propriété : l'écrêtage est une fonction croissante, il ne réordonne rien."""
    panel = pd.DataFrame([np.asarray(valeurs, dtype=float)])
    ecrete = winsorize(panel, lower=0.1, upper=0.9).iloc[0].to_numpy()
    ordre = np.argsort(panel.iloc[0].to_numpy(), kind="stable")
    assert np.all(np.diff(ecrete[ordre]) >= -1e-12)


# --------------------------------------------------------------------------
# Le z-score robuste
# --------------------------------------------------------------------------


def test_facteur_de_coherence_contre_scipy() -> None:
    """(d) Bibliothèque indépendante : le facteur vaut 1 / Phi^{-1}(0,75)."""
    assert pytest.approx(1.0 / float(norm.ppf(0.75)), rel=1e-15) == MAD_SCALE
    assert round(MAD_SCALE, 5) == 1.4826


def test_robust_zscore_exemple_calcule_a_la_main() -> None:
    """(a) Calcul à la main sur cinq valeurs 1, 2, 3, 4 et 5.

    Médiane : 3. Écarts absolus : 2, 1, 0, 1, 2, dont la médiane vaut 1.
    Le z-score robuste du 5 vaut donc 2 / 1,4826022 = 1,34898.
    """
    panel = pd.DataFrame([[1.0, 2.0, 3.0, 4.0, 5.0]], columns=list("abcde"))
    obtenu = robust_zscore(panel).iloc[0]
    assert obtenu["e"] == pytest.approx(2.0 / MAD_SCALE, abs=1e-15)
    assert obtenu["c"] == pytest.approx(0.0, abs=1e-15)
    assert obtenu["e"] == pytest.approx(1.34898, abs=5e-6)


def test_robust_zscore_ne_bouge_pas_quand_une_valeur_extreme_explose() -> None:
    """(a) La médiane et l'écart absolu médian sont inchangés, donc les autres z aussi.

    Sur 1 à 10, la médiane vaut 5,5 et les écarts absolus triés sont
    0,5 0,5 1,5 1,5 2,5 2,5 3,5 3,5 4,5 4,5, de médiane 2,5. En remplaçant le 10
    par un million, la médiane reste 5,5 et les écarts triés deviennent
    0,5 0,5 1,5 1,5 2,5 2,5 3,5 3,5 4,5 999994,5, de médiane 2,5 encore.
    Les neuf premiers z-scores robustes sont donc identiques au bit près, alors
    que le z-score ordinaire, lui, s'effondre.
    """
    pollue = PANEL.copy()
    pollue.iloc[0, 9] = 1e6
    robuste_avant = robust_zscore(PANEL).iloc[0].to_numpy()[:9]
    robuste_apres = robust_zscore(pollue).iloc[0].to_numpy()[:9]
    np.testing.assert_array_equal(robuste_apres, robuste_avant)
    ordinaire_apres = cross_sectional_zscore(pollue).iloc[0].to_numpy()[:9]
    assert float(np.abs(ordinaire_apres).max()) < 0.5


def test_robust_zscore_rend_nan_quand_l_ecart_absolu_median_est_nul() -> None:
    """(a) Six valeurs identiques sur dix rendent une médiane des écarts nulle.

    Écarts absolus à la médiane 1 : six zéros, puis 1, 2, 3 et 4. Le sixième et
    le cinquième éléments triés valent zéro, donc leur moyenne aussi.
    """
    panel = pd.DataFrame([[1.0] * 6 + [2.0, 3.0, 4.0, 5.0]], columns=ASSETS)
    assert bool(robust_zscore(panel).iloc[0].isna().all())


def test_robust_zscore_ligne_trop_mince_rend_nan() -> None:
    """(a) Quatre actifs renseignés sous un plancher de cinq."""
    assert bool(robust_zscore(PANEL).iloc[2].isna().all())


# --------------------------------------------------------------------------
# Le retrait de la moyenne par groupe
# --------------------------------------------------------------------------

GROUPES = {actif: ("X" if actif < "F" else "Y") for actif in ASSETS}


def test_demean_par_groupe_calcule_a_la_main() -> None:
    """(a) Groupe X : 1 à 5, de moyenne 3. Groupe Y : 6 à 10, de moyenne 8."""
    obtenu = demean_by_group(PANEL, GROUPES).iloc[0]
    attendu = np.array([-2.0, -1.0, 0.0, 1.0, 2.0, -2.0, -1.0, 0.0, 1.0, 2.0])
    np.testing.assert_allclose(obtenu.to_numpy(), attendu, atol=1e-15)


def test_demean_par_groupe_annule_la_moyenne_de_chaque_groupe() -> None:
    """(b) Identité : retirer la moyenne d'un bloc rend un bloc de moyenne nulle."""
    obtenu = demean_by_group(PANEL, GROUPES)
    for etiquette in ("X", "Y"):
        colonnes = [actif for actif in ASSETS if GROUPES[actif] == etiquette]
        moyennes = obtenu[colonnes].mean(axis=1).dropna().to_numpy()
        np.testing.assert_allclose(moyennes, np.zeros(moyennes.size), atol=1e-15)


def test_demean_par_groupe_singleton_rend_zero_puis_nan_sous_le_seuil() -> None:
    """(a) Un actif seul dans son groupe est comparé à lui-même, donc son signal vaut zéro."""
    groupes = dict(GROUPES) | {"J": "Z"}
    obtenu = demean_by_group(PANEL, groupes)
    assert obtenu.iloc[0]["J"] == pytest.approx(0.0, abs=1e-15)
    exigeant = demean_by_group(PANEL, groupes, min_names=2)
    assert bool(exigeant.iloc[0][["J"]].isna().all())


def test_demean_par_groupe_refuse_un_actif_sans_groupe() -> None:
    """(b) Combler un groupe manquant serait une décision cachée."""
    incomplet = {actif: "X" for actif in ASSETS if actif != "J"}
    with pytest.raises(ConfigError, match="groupe"):
        demean_by_group(PANEL, incomplet)


def test_demean_par_groupe_accepte_une_series() -> None:
    """(b) Un dictionnaire et une Series portant la même table donnent le même résultat."""
    par_dictionnaire = demean_by_group(PANEL, GROUPES)
    par_series = demean_by_group(PANEL, pd.Series(GROUPES))
    pd.testing.assert_frame_equal(par_series, par_dictionnaire)


# --------------------------------------------------------------------------
# Les mises à l'échelle d'un vecteur de poids
# --------------------------------------------------------------------------


def _poids(*valeurs: float) -> pd.Series:
    return pd.Series(list(valeurs), index=ASSETS[: len(valeurs)], dtype=float)


def test_scale_to_gross_exemple_calcule_a_la_main() -> None:
    """(a) Poids 0,2 -0,6 et 0,4 : exposition brute 1,2, facteur 1 / 1,2 = 5/6."""
    obtenu = scale_to_gross(_poids(0.2, -0.6, 0.4))
    np.testing.assert_allclose(obtenu.to_numpy(), np.array([1 / 6, -0.5, 1 / 3]), atol=1e-15)
    assert float(obtenu.abs().sum()) == pytest.approx(1.0, abs=1e-15)


def test_scale_to_gross_conserve_les_rapports() -> None:
    """(b) Identité : une multiplication par un scalaire laisse tout rapport inchangé."""
    depart = _poids(0.2, -0.6, 0.4)
    obtenu = scale_to_gross(depart, target_gross=2.5)
    assert float(obtenu.abs().sum()) == pytest.approx(2.5, abs=1e-15)
    assert float(obtenu.iloc[0] / obtenu.iloc[1]) == pytest.approx(float(depart.iloc[0] / depart.iloc[1]))


def test_scale_to_gross_refuse_un_vecteur_nul_et_une_cible_negative() -> None:
    """(b) Aucun facteur ne porte un vecteur nul à une exposition strictement positive."""
    with pytest.raises(DataQualityError, match="brute"):
        scale_to_gross(_poids(0.0, 0.0, 0.0))
    with pytest.raises(ConfigError, match="target_gross"):
        scale_to_gross(_poids(0.2, -0.6, 0.4), target_gross=-1.0)


def test_scale_to_gross_cible_nulle_rend_des_zeros() -> None:
    """(b) Identité : une exposition brute nulle n'est atteinte que par le vecteur nul."""
    obtenu = scale_to_gross(_poids(0.2, -0.6, 0.4), target_gross=0.0)
    np.testing.assert_array_equal(obtenu.to_numpy(), np.zeros(3))


def test_scale_to_gross_refuse_un_poids_manquant_et_un_vecteur_vide() -> None:
    """(b) Un poids inconnu n'est pas un poids, et un portefeuille vide n'a pas d'exposition."""
    with pytest.raises(DataQualityError, match="manquant"):
        scale_to_gross(_poids(0.2, float("nan"), 0.4))
    with pytest.raises(InsufficientDataError, match="vide"):
        scale_to_gross(pd.Series(dtype=float))


def test_scale_to_net_exemple_calcule_a_la_main() -> None:
    """(a) Poids 0,2 -0,6 et 0,4 : somme 0, cible 1, décalage (1 - 0) / 3 = 1/3."""
    obtenu = scale_to_net(_poids(0.2, -0.6, 0.4), target_net=1.0)
    np.testing.assert_allclose(
        obtenu.to_numpy(), np.array([0.2 + 1 / 3, -0.6 + 1 / 3, 0.4 + 1 / 3]), atol=1e-15
    )
    assert float(obtenu.sum()) == pytest.approx(1.0, abs=1e-15)


def test_scale_to_net_conserve_tous_les_ecarts() -> None:
    """(b) Identité : une translation laisse toute différence de poids inchangée."""
    depart = _poids(0.5, -0.2, 0.9, 0.1)
    obtenu = scale_to_net(depart, target_net=0.3)
    np.testing.assert_allclose(np.diff(obtenu.to_numpy()), np.diff(depart.to_numpy()), atol=1e-15)


def test_neutralize_to_zero_net_annule_la_somme() -> None:
    """(a) Poids 0,5 -0,2 0,9 et 0,1 : somme 1,3, moyenne 0,325, retirée à chacun."""
    depart = _poids(0.5, -0.2, 0.9, 0.1)
    obtenu = neutralize_to_zero_net(depart)
    assert float(obtenu.sum()) == pytest.approx(0.0, abs=1e-15)
    assert obtenu.iloc[0] == pytest.approx(0.5 - 0.325, abs=1e-15)


def test_neutralize_puis_scale_to_gross_tient_les_deux_cibles() -> None:
    """(b) Identité : multiplier une somme nulle par un scalaire la laisse nulle."""
    obtenu = scale_to_gross(neutralize_to_zero_net(_poids(0.5, -0.2, 0.9, 0.1)), target_gross=1.6)
    assert float(obtenu.sum()) == pytest.approx(0.0, abs=1e-15)
    assert float(obtenu.abs().sum()) == pytest.approx(1.6, abs=1e-15)


# --------------------------------------------------------------------------
# Du signal aux poids
# --------------------------------------------------------------------------

#: Un signal non linéaire, pour que le rang et le z-score ne coïncident pas.
SIGNAL = pd.DataFrame(
    [
        [-8.0, -1.0, -0.5, -0.25, 0.0, 0.25, 0.5, 1.0, 2.0, 12.0],
        [3.0] * 10,
        [1.0, 2.0, 3.0, 4.0, *([float("nan")] * 6)],
    ],
    index=DATES,
    columns=ASSETS,
)


@pytest.mark.parametrize("methode", ["rank", "zscore", "equal_long_short"])
def test_signal_to_weights_long_short_somme_nulle_et_brut_a_la_cible(methode: str) -> None:
    """(b) Identité : la construction long-short recentre puis normalise l'exposition brute."""
    quantiles = 5 if methode == "equal_long_short" else None
    obtenu = signal_to_weights(SIGNAL, method=methode, n_quantiles=quantiles, target_gross=1.6)
    ligne = obtenu.iloc[0]
    assert float(ligne.sum()) == pytest.approx(0.0, abs=1e-12)
    assert float(ligne.abs().sum()) == pytest.approx(1.6, abs=1e-12)


def test_signal_to_weights_rang_calcule_a_la_main() -> None:
    """(a) Rangs 1 à 10 ramenés à [-1, 1], soit les neuvièmes impairs de -1 à 1.

    Somme des valeurs absolues : 2 x (1 + 7/9 + 5/9 + 3/9 + 1/9) = 2 x 25/9,
    soit 50/9. Chaque poids vaut donc son rang normalisé multiplié par 9/50,
    l'exposition brute visée étant l'unité. Le premier actif reçoit
    -1 x 9 / 50 = -0,18 et le troisième -5/9 x 9/50 = -0,10.
    """
    obtenu = signal_to_weights(SIGNAL, method="rank").iloc[0]
    np.testing.assert_allclose(obtenu.to_numpy(), RANGS_LIGNE_1 * 9.0 / 50.0, atol=1e-15)
    assert obtenu["A"] == pytest.approx(-0.18, abs=1e-15)
    assert obtenu["C"] == pytest.approx(-0.10, abs=1e-15)


def test_signal_to_weights_paquets_extremes_calcules_a_la_main() -> None:
    """(a) Dix actifs en cinq paquets : deux par paquet, donc 0,25 par position.

    Le paquet bas porte les deux plus faibles signaux et le paquet haut les deux
    plus forts. Les six actifs du milieu reçoivent exactement zéro.
    """
    obtenu = signal_to_weights(SIGNAL, method="equal_long_short", n_quantiles=5).iloc[0]
    attendu = np.array([-0.25, -0.25, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.25, 0.25])
    np.testing.assert_allclose(obtenu.to_numpy(), attendu, atol=1e-15)


@pytest.mark.parametrize("methode", ["rank", "zscore", "equal_long_short"])
def test_signal_to_weights_long_only_reste_positif_et_somme_a_la_cible(methode: str) -> None:
    """(b) Identité : sans jambe vendeuse, l'exposition nette égale l'exposition brute."""
    quantiles = 5 if methode == "equal_long_short" else None
    ligne = signal_to_weights(
        SIGNAL, method=methode, n_quantiles=quantiles, long_only=True, target_gross=1.0
    ).iloc[0]
    assert bool((ligne >= -1e-15).all())
    assert float(ligne.sum()) == pytest.approx(1.0, abs=1e-12)


def test_signal_to_weights_long_only_par_rang_laisse_le_dernier_a_zero() -> None:
    """(a) Le rang normalisé sur [0, 1] vaut zéro pour le plus faible signal."""
    ligne = signal_to_weights(SIGNAL, method="rank", long_only=True).iloc[0]
    assert ligne["A"] == pytest.approx(0.0, abs=1e-15)
    # (a) Les rangs 1 à 10 donnent des scores 0 à 1 par neuvièmes, de somme 5,
    # donc le deuxième actif reçoit (1/9) / 5 = 1/45.
    assert ligne["B"] == pytest.approx(1 / 45, abs=1e-15)


def test_signal_to_weights_coupe_constante_rend_nan_pour_les_trois_methodes() -> None:
    """(b) Une coupe sans dispersion n'ordonne rien, donc ne rend aucun portefeuille."""
    for methode, quantiles in (("rank", None), ("zscore", None), ("equal_long_short", 5)):
        obtenu = signal_to_weights(SIGNAL, method=methode, n_quantiles=quantiles)
        assert bool(obtenu.iloc[1].isna().all())


def test_signal_to_weights_date_trop_mince_rend_nan() -> None:
    """(a) La troisième date porte quatre actifs, sous le plancher de cinq."""
    obtenu = signal_to_weights(SIGNAL, method="rank")
    assert bool(obtenu.iloc[2].isna().all())
    permissif = signal_to_weights(SIGNAL, method="rank", min_names=4).iloc[2]
    # (a) Quatre rangs sur [-1, 1] : -1, -1/3, 1/3 et 1, de somme absolue 8/3.
    np.testing.assert_allclose(
        permissif[["A", "B", "C", "D"]].to_numpy(),
        np.array([-1.0, -1 / 3, 1 / 3, 1.0]) / (8 / 3),
        atol=1e-15,
    )
    np.testing.assert_array_equal(permissif[["E", "J"]].to_numpy(), np.zeros(2))


def test_signal_to_weights_accepte_une_coupe_indexee_par_actif() -> None:
    """(b) Identité : la coupe d'une date donne la ligne du panel correspondant."""
    coupe = SIGNAL.iloc[0]
    obtenu = signal_to_weights(coupe, method="rank")
    assert isinstance(obtenu, pd.Series)
    np.testing.assert_allclose(
        obtenu.to_numpy(), signal_to_weights(SIGNAL, method="rank").iloc[0].to_numpy(), atol=1e-15
    )


def test_signal_to_weights_refuse_les_incoherences_de_configuration() -> None:
    """(b) Un argument ignoré en silence cacherait une intention de l'appelant."""
    with pytest.raises(ConfigError, match="n_quantiles"):
        signal_to_weights(SIGNAL, method="rank", n_quantiles=5)
    with pytest.raises(ConfigError, match="n_quantiles"):
        signal_to_weights(SIGNAL, method="equal_long_short")
    with pytest.raises(ConfigError, match="n_quantiles"):
        signal_to_weights(SIGNAL, method="equal_long_short", n_quantiles=1)
    with pytest.raises(ConfigError, match="target_gross"):
        signal_to_weights(SIGNAL, method="rank", target_gross=0.0)
    with pytest.raises(ValueError, match="quantile"):
        signal_to_weights(SIGNAL, method="quantile")


def test_signal_to_weights_paquets_non_separes_rendent_nan() -> None:
    """(a) Huit actifs sur dix portent le même signal : les paquets extrêmes se touchent.

    Avec cinq paquets, le paquet bas et le paquet haut portent alors le même
    signal, et leur séparation ne viendrait que de l'ordre des colonnes.
    """
    panel = pd.DataFrame([[0.0] + [1.0] * 8 + [2.0]], columns=ASSETS)
    assert bool(signal_to_weights(panel, method="equal_long_short", n_quantiles=5).iloc[0].isna().all())


def test_signal_to_weights_accepte_l_enumeration() -> None:
    """(b) L'énumération et sa valeur textuelle désignent la même règle."""
    par_texte = signal_to_weights(SIGNAL, method="zscore")
    par_enum = signal_to_weights(SIGNAL, method=WeightingMethod.ZSCORE)
    pd.testing.assert_frame_equal(par_enum, par_texte)


@given(
    valeurs=st.lists(st.integers(min_value=-1000, max_value=1000), unique=True, min_size=5, max_size=15),
    cible=st.floats(min_value=0.1, max_value=5.0),
)
@settings(deadline=None, max_examples=100)
def test_signal_to_weights_propriete_long_short(valeurs: list[int], cible: float) -> None:
    """(b) Propriété : somme nulle et somme des valeurs absolues égale à la cible."""
    panel = pd.DataFrame([np.asarray(valeurs, dtype=float)])
    ligne = signal_to_weights(panel, method="rank", target_gross=cible).iloc[0]
    assert float(ligne.sum()) == pytest.approx(0.0, abs=1e-12)
    assert float(ligne.abs().sum()) == pytest.approx(cible, rel=1e-12)


# --------------------------------------------------------------------------
# Les cas limites et les refus de contrat
# --------------------------------------------------------------------------

#: Les quatre transformations de panel, soumises aux mêmes refus de contrat.
type Transformation = Callable[..., pd.DataFrame]
TRANSFORMATIONS: tuple[Transformation, ...] = (
    cross_sectional_zscore,
    cross_sectional_rank,
    robust_zscore,
    winsorize,
)


@pytest.mark.parametrize("transformation", TRANSFORMATIONS, ids=lambda f: f.__name__)
def test_panel_vide_rend_un_panel_vide(transformation: Transformation) -> None:
    """(b) Un panel sans donnée n'a aucune statistique, et aucune erreur à lever."""
    vide = pd.DataFrame(dtype=float)
    obtenu = transformation(vide)
    assert obtenu.shape == (0, 0)


@pytest.mark.parametrize("transformation", TRANSFORMATIONS, ids=lambda f: f.__name__)
def test_panel_a_un_seul_actif(transformation: Transformation) -> None:
    """(a) Un actif seul est sous le plancher de cinq, sauf pour l'écrêtage.

    L'écrêtage ne compare pas les actifs entre eux au sens d'une dispersion : sur
    un seul point, tous les quantiles valent cette valeur, et l'écrêtage la rend
    inchangée.
    """
    unique = pd.DataFrame([[1.0], [2.0], [3.0]], index=DATES, columns=["A"])
    obtenu = transformation(unique)
    if transformation is winsorize:
        np.testing.assert_array_equal(obtenu.to_numpy(), unique.to_numpy())
    else:
        assert bool(obtenu.isna().all().all())


@pytest.mark.parametrize("transformation", TRANSFORMATIONS, ids=lambda f: f.__name__)
def test_refus_des_valeurs_infinies_et_des_doublons(transformation: Transformation) -> None:
    """(b) Une valeur infinie contamine toute statistique de la coupe."""
    infini = PANEL.copy()
    infini.iloc[0, 0] = float("inf")
    with pytest.raises(DataQualityError, match="infinies"):
        transformation(infini)
    double = pd.concat([PANEL, PANEL[["A"]]], axis=1)
    with pytest.raises(DataQualityError, match="double"):
        transformation(double)


@pytest.mark.parametrize("transformation", TRANSFORMATIONS, ids=lambda f: f.__name__)
def test_refus_d_un_objet_qui_n_est_pas_un_panel(transformation: Transformation) -> None:
    """(b) Une Series n'est pas un panel : l'axe transversal ne serait pas défini."""
    with pytest.raises(ConfigError, match="DataFrame"):
        transformation(PANEL.iloc[0])


@pytest.mark.parametrize("transformation", TRANSFORMATIONS, ids=lambda f: f.__name__)
def test_les_valeurs_manquantes_ressortent_manquantes(transformation: Transformation) -> None:
    """(b) Un actif hors univers le reste : aucune transformation ne comble un trou."""
    obtenu = transformation(PANEL, **({} if transformation is winsorize else {"min_names": 2}))
    manquants = PANEL.isna().to_numpy()
    assert bool(np.isnan(obtenu.to_numpy()[manquants]).all())


# --------------------------------------------------------------------------
# L'unité du signal ne décide de rien
# --------------------------------------------------------------------------

#: Les treize ordres de grandeur balayés par les contrôles d'invariance
#: d'échelle. Le facteur 1e-13 est celui qui prenait en défaut le plancher de
#: dispersion absolu de la version précédente.
FACTEURS_D_ECHELLE = (1e6, 1.0, 1e-6, 1e-12, 1e-13, 1e-14)


@pytest.mark.parametrize("facteur", FACTEURS_D_ECHELLE)
def test_zscore_invariant_par_changement_d_unite(facteur: float) -> None:
    """(b) Identité : le z-score de a x vaut celui de x pour tout a strictement positif.

    Le point n'est pas la tolérance mais le domaine. Un plancher de dispersion
    absolu rend ``NaN`` dès que l'écart type de la coupe tombe sous ce plancher,
    ce qui arrive pour a = 1e-13 sur les entiers de 1 à 10. Le portefeuille
    dépendrait alors du choix de l'unité, ce qu'aucune formule ne dit.
    """
    attendu = cross_sectional_zscore(PANEL).iloc[0].to_numpy()
    obtenu = cross_sectional_zscore(PANEL * facteur).iloc[0].to_numpy()
    assert not bool(np.isnan(obtenu).any())
    np.testing.assert_allclose(obtenu, attendu, rtol=1e-12)


@pytest.mark.parametrize("facteur", FACTEURS_D_ECHELLE)
def test_robust_zscore_invariant_par_changement_d_unite(facteur: float) -> None:
    """(b) Identité : la médiane et l'écart absolu médian sont homogènes de degré un."""
    attendu = robust_zscore(PANEL).iloc[0].to_numpy()
    obtenu = robust_zscore(PANEL * facteur).iloc[0].to_numpy()
    assert not bool(np.isnan(obtenu).any())
    np.testing.assert_allclose(obtenu, attendu, rtol=1e-12)


@pytest.mark.parametrize("facteur", FACTEURS_D_ECHELLE)
@pytest.mark.parametrize("methode", ["rank", "zscore", "equal_long_short"])
def test_signal_to_weights_invariant_par_changement_d_unite(methode: str, facteur: float) -> None:
    """(b) Identité : les trois règles ne lisent que l'ordre ou des écarts normalisés."""
    quantiles = 5 if methode == "equal_long_short" else None
    attendu = signal_to_weights(SIGNAL, method=methode, n_quantiles=quantiles).iloc[0].to_numpy()
    obtenu = signal_to_weights(SIGNAL * facteur, method=methode, n_quantiles=quantiles).iloc[0].to_numpy()
    assert not bool(np.isnan(obtenu).any())
    np.testing.assert_allclose(obtenu, attendu, atol=1e-14)


def test_zscore_ligne_vraiment_constante_rend_nan_a_toute_echelle() -> None:
    """(b) Identité : une coupe constante a une dispersion nulle, quelle que soit son unité.

    Le plancher relatif ne doit pas rendre acceptable ce que le plancher absolu
    refusait. Une coupe constante à un milliard reste une coupe constante.
    """
    for niveau in (1e-13, 1.0, 1e9):
        panel = pd.DataFrame([[niveau] * 10], columns=ASSETS)
        assert bool(cross_sectional_zscore(panel).iloc[0].isna().all())
        assert bool(robust_zscore(panel).iloc[0].isna().all())


def test_scale_to_gross_porte_des_poids_minuscules_a_la_cible() -> None:
    """(a) Calcul à la main : poids 1e-13 et -3e-13, exposition brute 4e-13.

    Le facteur vaut 1 / 4e-13, donc les poids deviennent 0,25 et -0,75. Un seuil
    absolu sur l'exposition brute de départ levait ici une erreur, alors que la
    mise à l'échelle est parfaitement définie : la somme des valeurs absolues ne
    s'annule que si tous les poids sont nuls.
    """
    obtenu = scale_to_gross(pd.Series([1e-13, -3e-13], index=["A", "B"]))
    np.testing.assert_allclose(obtenu.to_numpy(), np.array([0.25, -0.75]), rtol=1e-12)


# --------------------------------------------------------------------------
# Aucune date n'influence une autre
# --------------------------------------------------------------------------

#: Deux dates et cinq actifs. Les contrôles de fuite modifient la SECONDE date
#: et vérifient que la première ne bouge pas d'un bit.
PANEL_DEUX_DATES = pd.DataFrame(
    [[1.0, 2.0, 3.0, 4.0, 5.0], [10.0, 20.0, 30.0, 40.0, 50.0]],
    index=DATES[:2],
    columns=ASSETS[:5],
)


def _panel_au_futur_modifie() -> pd.DataFrame:
    """Rend le même panel dont la seule dernière date porte une valeur extrême."""
    futur = PANEL_DEUX_DATES.copy()
    futur.iloc[1, 4] = 1e6
    return futur


@pytest.mark.parametrize(
    ("nom", "appel"),
    [
        ("zscore", lambda p: cross_sectional_zscore(p)),
        ("rang", lambda p: cross_sectional_rank(p)),
        ("robuste", lambda p: robust_zscore(p)),
        ("ecretage", lambda p: winsorize(p, lower=0.1, upper=0.9)),
        ("groupes", lambda p: demean_by_group(p, dict.fromkeys(ASSETS[:5], "X"))),
        ("poids_rang", lambda p: signal_to_weights(p, method="rank")),
        ("poids_zscore", lambda p: signal_to_weights(p, method="zscore")),
        ("poids_paquets", lambda p: signal_to_weights(p, method="equal_long_short", n_quantiles=5)),
    ],
)
def test_aucune_date_posterieure_n_influence_une_date_anterieure(
    nom: str, appel: Callable[[pd.DataFrame], pd.DataFrame]
) -> None:
    """(b) Propriété : une transformation transversale est une fonction de sa seule ligne.

    C'est la garantie que le module revendique dans sa docstring de tête, et
    c'est le seul chemin par lequel une fuite temporelle pourrait entrer ici. Le
    contrôle remplace la dernière valeur de la DERNIÈRE date par un million et
    exige que la première date ressorte identique au bit près.
    """
    avant = appel(PANEL_DEUX_DATES).iloc[0].to_numpy()
    apres = appel(_panel_au_futur_modifie()).iloc[0].to_numpy()
    np.testing.assert_array_equal(apres, avant)


# --------------------------------------------------------------------------
# Le recentrage des scores, et le refus des coupes constantes
# --------------------------------------------------------------------------

#: Une coupe à trois ex aequo au bas du classement, puis deux valeurs
#: distinctes. Elle sépare les quatre règles de départage.
COUPE_EX_AEQUO = pd.DataFrame([[1.0, 1.0, 1.0, 2.0, 3.0]], columns=ASSETS[:5])


def test_signal_to_weights_rang_minimum_recentre_calcule_a_la_main() -> None:
    """(a) Calcul à la main : les rangs ``min`` laissent une exposition nette à corriger.

    Rangs par la règle ``min`` sur 1, 1, 1, 2 et 3 : 1, 1, 1, 4 et 5.
    Scores avant recentrage, par 2 (r - 1) / 4 - 1 : -1, -1, -1, 0,5 et 1.
    Leur moyenne vaut (-3 + 1,5) / 5 = -0,3, donc le portefeuille serait vendeur
    net sans rien qui le décide. Après retrait de cette moyenne : -0,7, -0,7,
    -0,7, 0,8 et 1,3, de somme nulle et d'exposition brute 4,2.
    Les poids valent donc -0,7/4,2 = -1/6, puis 0,8/4,2 = 4/21 et 1,3/4,2 = 13/42.
    """
    obtenu = signal_to_weights(COUPE_EX_AEQUO, method="rank", rank_method="min").iloc[0]
    attendu = np.array([-1 / 6, -1 / 6, -1 / 6, 4 / 21, 13 / 42])
    np.testing.assert_allclose(obtenu.to_numpy(), attendu, atol=1e-15)
    assert float(obtenu.sum()) == pytest.approx(0.0, abs=1e-15)


def test_signal_to_weights_rang_maximum_recentre_calcule_a_la_main() -> None:
    """(a) Calcul à la main : les rangs ``max`` penchent dans l'autre sens.

    Rangs par la règle ``max`` : 3, 3, 3, 4 et 5. Scores avant recentrage :
    0, 0, 0, 0,5 et 1, de moyenne 1,5 / 5 = 0,3. Après retrait : -0,3, -0,3,
    -0,3, 0,2 et 0,7, d'exposition brute 1,8. Les poids valent -1/6 trois fois,
    puis 0,2/1,8 = 1/9 et 0,7/1,8 = 7/18.
    """
    obtenu = signal_to_weights(COUPE_EX_AEQUO, method="rank", rank_method="max").iloc[0]
    attendu = np.array([-1 / 6, -1 / 6, -1 / 6, 1 / 9, 7 / 18])
    np.testing.assert_allclose(obtenu.to_numpy(), attendu, atol=1e-15)
    assert float(obtenu.sum()) == pytest.approx(0.0, abs=1e-15)


@pytest.mark.parametrize("departage", ["average", "min", "max", "first"])
def test_signal_to_weights_coupe_constante_rend_nan_quel_que_soit_le_departage(departage: str) -> None:
    """(a) Le refus de la coupe constante porte sur les quatre règles de départage.

    La règle ``average`` donne le même rang à tout le monde, donc des scores
    nuls, et l'absence de portefeuille s'obtiendrait sans garde explicite. La
    règle ``first``, elle, numérote les colonnes de 1 à 5 : sans la garde, les
    poids sortiraient à -1/3, -1/6, 0, 1/6 et 1/3, soit un portefeuille entier
    tiré de l'ordre des colonnes et d'aucune donnée.
    """
    constante = pd.DataFrame([[3.0] * 5], columns=ASSETS[:5])
    obtenu = signal_to_weights(constante, method="rank", rank_method=departage).iloc[0]
    assert bool(obtenu.isna().all())


def test_signal_to_weights_zscore_calcule_a_la_main() -> None:
    """(a) Calcul à la main sur les signaux 0, 1, 2, 3 et 10.

    Moyenne : 16 / 5 = 3,2. Écarts au centre : -3,2, -2,2, -1,2, -0,2 et 6,8.
    Le z-score divise ces écarts par l'écart type, et la mise à l'échelle brute
    les divise par la somme de leurs valeurs absolues divisée par le même écart
    type. L'écart type se simplifie donc entièrement, et le poids d'un actif
    vaut son écart au centre divisé par 13,6.
    Le premier reçoit -3,2 / 13,6 = -4/17 et le dernier 6,8 / 13,6 = 1/2.
    """
    coupe = pd.DataFrame([[0.0, 1.0, 2.0, 3.0, 10.0]], columns=ASSETS[:5])
    obtenu = signal_to_weights(coupe, method="zscore").iloc[0]
    ecarts = np.array([-3.2, -2.2, -1.2, -0.2, 6.8])
    np.testing.assert_allclose(obtenu.to_numpy(), ecarts / 13.6, atol=1e-15)
    assert obtenu.iloc[0] == pytest.approx(-4 / 17, abs=1e-15)
    assert obtenu.iloc[4] == pytest.approx(0.5, abs=1e-15)


@given(
    valeurs=st.lists(st.integers(min_value=-1000, max_value=1000), unique=True, min_size=5, max_size=12),
    exposant=st.integers(min_value=-14, max_value=6),
)
@settings(deadline=None, max_examples=150)
def test_signal_to_weights_propriete_d_invariance_d_echelle(valeurs: list[int], exposant: int) -> None:
    """(b) Propriété : multiplier le signal par une puissance de dix ne change aucun poids.

    Le rang ne lit que l'ordre, qu'une multiplication par un facteur positif
    laisse intact. Les entiers sont distincts, donc aucune multiplication ne
    crée d'ex aequo.
    """
    panel = pd.DataFrame([np.asarray(valeurs, dtype=float)])
    attendu = signal_to_weights(panel, method="rank").iloc[0].to_numpy()
    obtenu = signal_to_weights(panel * (10.0**exposant), method="rank").iloc[0].to_numpy()
    np.testing.assert_allclose(obtenu, attendu, atol=1e-15)

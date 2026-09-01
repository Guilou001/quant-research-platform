"""Contrôles du module ``quantlab.validation.robustness``.

Règle 10 du laboratoire, appliquée sans exception : aucune valeur attendue ne
vient de la sortie du code. Chaque test dit d'où sort la sienne, parmi quatre
sources.

(a) un calcul à la main, écrit dans le commentaire, chiffres visibles ;
(b) une forme fermée ou une identité mathématique ;
(c) une valeur publiée, citée ;
(d) une implémentation indépendante, ``numpy`` ou ``itertools`` sur le même intrant.

La grille synthétique de ce fichier est le cœur du dossier. Elle est écrite à la
main, cellule par cellule, et l'on sait donc où est le plateau et où est le pic
isolé avant de faire tourner quoi que ce soit.
"""

from __future__ import annotations

import itertools
import math

import numpy as np
import pandas as pd
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from scipy.stats import norm

from conftest import TEST_SEED
from quantlab.core.determinism import child_generators
from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.types import CostBasis, Frequency, SampleTag
from quantlab.validation import robustness
from quantlab.validation.robustness import (
    RobustnessReport,
    best_plateau,
    cost_multiplier_analysis,
    execution_delay_analysis,
    parameter_sweep,
    plateau_score,
    sensitivity_analysis,
    subperiod_performance,
)

# --------------------------------------------------------------------------- #
# La grille synthétique, écrite à la main
# --------------------------------------------------------------------------- #

#: Les deux axes de la grille. Cinq valeurs chacun, donc 25 combinaisons.
FAST = (5, 10, 20, 40, 80)
SLOW = (50, 100, 150, 200, 250)

#: La métrique, posée cellule par cellule. Lignes = ``FAST``, colonnes = ``SLOW``.
#:
#: Le bloc supérieur gauche de neuf cases tourne autour de 1,00 : c'est le
#: PLATEAU, et son centre est la case (10, 100). La case (40, 200) vaut 3,00
#: alors que ses huit voisines valent 0,10 : c'est le PIC ISOLÉ. Il est placé à
#: l'intérieur de la grille, et non sur un bord, pour qu'il soit éligible et
#: que le test mesure bien le score de plateau plutôt qu'un filtrage de bord.
GRID_VALUES = (
    (0.98, 1.02, 0.99, 0.10, 0.10),
    (1.01, 1.05, 1.00, 0.10, 0.10),
    (0.97, 1.03, 0.96, 0.10, 0.10),
    (0.10, 0.10, 0.10, 3.00, 0.10),
    (0.10, 0.10, 0.10, 0.10, 0.10),
)

#: Dictionnaire de consultation de la grille, pour la fonction d'évaluation.
GRID_LOOKUP = {(FAST[i], SLOW[j]): GRID_VALUES[i][j] for i in range(len(FAST)) for j in range(len(SLOW))}


def _grid_metric(fast: int, slow: int) -> float:
    """Rend la métrique posée à la main pour cette combinaison."""
    return GRID_LOOKUP[(fast, slow)]


@pytest.fixture
def synthetic_sweep() -> pd.DataFrame:
    """Rend le balayage de la grille synthétique, 25 lignes."""
    return parameter_sweep({"fast": FAST, "slow": SLOW}, _grid_metric)


# --------------------------------------------------------------------------- #
# parameter_sweep
# --------------------------------------------------------------------------- #


def test_le_balayage_couvre_le_produit_cartesien(synthetic_sweep: pd.DataFrame) -> None:
    """La hauteur du tableau vaut le produit des longueurs des axes.

    Source (b) et (d) : la forme fermée ``5 x 5 = 25``, et l'ensemble des
    combinaisons attendu construit par ``itertools.product``, indépendant du
    code testé.
    """
    assert len(synthetic_sweep) == 5 * 5
    attendues = set(itertools.product(FAST, SLOW))
    obtenues = set(
        zip(
            synthetic_sweep["fast"].tolist(),
            synthetic_sweep["slow"].tolist(),
            strict=True,
        )
    )
    assert obtenues == attendues


def test_le_balayage_conserve_les_mauvaises_combinaisons(synthetic_sweep: pd.DataFrame) -> None:
    """Les combinaisons à 0,10 sont présentes, et elles sont majoritaires.

    Source (a) : la grille écrite à la main porte quinze cases à 0,10, comptées
    directement dans ``GRID_VALUES``.
    """
    attendu = sum(1 for ligne in GRID_VALUES for valeur in ligne if valeur == 0.10)
    assert attendu == 15
    assert int((synthetic_sweep["metric"] == 0.10).sum()) == attendu


def test_le_balayage_rend_les_metriques_posees(synthetic_sweep: pd.DataFrame) -> None:
    """Chaque ligne porte la valeur écrite à la main pour sa combinaison."""
    for ligne in synthetic_sweep.itertuples():
        assert ligne.metric == GRID_LOOKUP[(ligne.fast, ligne.slow)]


def test_le_balayage_accepte_plusieurs_metriques() -> None:
    """Une fonction qui rend un dictionnaire donne une colonne par métrique.

    Source (a) : ``sharpe`` vaut ``x / 2`` et ``turnover`` vaut ``x + 1``, donc
    pour ``x = 4`` on attend 2,0 et 5,0.
    """
    sweep = parameter_sweep({"x": (2, 4)}, lambda x: {"sharpe": x / 2, "turnover": x + 1})
    assert list(sweep.columns) == ["trial", "x", "sharpe", "turnover", "error"]
    ligne = sweep.loc[sweep["x"] == 4].iloc[0]
    assert ligne["sharpe"] == 2.0
    assert ligne["turnover"] == 5.0


def test_le_balayage_leve_par_defaut_quand_une_evaluation_echoue() -> None:
    """Sans consigne contraire, une évaluation qui échoue arrête le balayage."""

    def evaluer(x: int) -> float:
        if x == 2:
            raise ValueError("évaluation impossible")
        return float(x)

    with pytest.raises(ValueError, match="évaluation impossible"):
        parameter_sweep({"x": (1, 2, 3)}, evaluer)


def test_le_balayage_enregistre_les_echecs_quand_on_le_demande() -> None:
    """Avec ``on_error='record'``, l'échec devient une ligne à métrique absente."""

    def evaluer(x: int) -> float:
        if x == 2:
            raise ValueError("évaluation impossible")
        return float(x)

    sweep = parameter_sweep({"x": (1, 2, 3)}, evaluer, on_error="record")
    assert len(sweep) == 3
    rate = sweep.loc[sweep["x"] == 2].iloc[0]
    assert math.isnan(rate["metric"])
    assert "évaluation impossible" in rate["error"]
    assert (sweep.loc[sweep["x"] != 2, "error"] == "").all()


def test_le_balayage_ne_depend_pas_du_parallelisme() -> None:
    """Le tableau rendu est identique avec un fil et avec quatre.

    Source (b) : identité exigée par la règle 14, le déterminisme. Le
    parallélisme change la vitesse, jamais l'ordre ni les valeurs.
    """
    seq = parameter_sweep({"fast": FAST, "slow": SLOW}, _grid_metric, n_jobs=1)
    par = parameter_sweep({"fast": FAST, "slow": SLOW}, _grid_metric, n_jobs=4)
    pd.testing.assert_frame_equal(seq, par)


@pytest.mark.parametrize(
    ("grille", "motif"),
    [
        ({}, "vide"),
        ({"x": ()}, "aucune valeur"),
        ({"x": (1, 1)}, "deux fois la même valeur"),
        ({"trial": (1, 2)}, "réservé"),
    ],
)
def test_le_balayage_refuse_une_grille_mal_formee(grille: dict, motif: str) -> None:
    """Une grille mal formée lève avant tout calcul."""
    with pytest.raises(ConfigError, match=motif):
        parameter_sweep(grille, lambda **_: 0.0)


def test_le_balayage_refuse_un_nombre_de_fils_nul() -> None:
    """``n_jobs`` inférieur à 1 n'a pas de sens et lève."""
    with pytest.raises(ConfigError, match="n_jobs"):
        parameter_sweep({"x": (1, 2)}, lambda x: float(x), n_jobs=0)


# --------------------------------------------------------------------------- #
# plateau_score
# --------------------------------------------------------------------------- #


def test_le_rayon_nul_rend_la_metrique_elle_meme(synthetic_sweep: pd.DataFrame) -> None:
    """Avec un rayon nul, chaque point est son seul voisin.

    Source (b) : identité annoncée au point (10) de la docstring. Le score vaut
    la métrique et l'isolement vaut zéro, partout.
    """
    note = plateau_score(synthetic_sweep, ["fast", "slow"], "metric", 0)
    assert note["plateau_score"].to_numpy() == pytest.approx(note["metric"].to_numpy())
    assert note["isolation"].to_numpy() == pytest.approx(0.0, abs=1e-15)
    assert (note["neighborhood_size"] == 1).all()


def test_une_grille_constante_a_un_isolement_nul_partout() -> None:
    """Sur une métrique constante, le score vaut la constante et l'isolement zéro.

    Source (b) : la médiane d'un ensemble de valeurs toutes égales à 0,42 vaut
    0,42, quel que soit le voisinage retenu.
    """
    sweep = parameter_sweep({"a": (1, 2, 3), "b": (10, 20, 30)}, lambda a, b: 0.42)
    note = plateau_score(sweep, ["a", "b"], "metric")
    assert note["plateau_score"].to_numpy() == pytest.approx(0.42)
    assert note["isolation"].to_numpy() == pytest.approx(0.0, abs=1e-15)


def test_les_scores_de_plateau_valent_les_medianes_calculees_a_la_main(
    synthetic_sweep: pd.DataFrame,
) -> None:
    """Trois cases sont vérifiées contre une médiane posée à la main.

    Source (a). Les trois voisinages, rayon 1, point compris.

    Centre du plateau, la case (10, 100), neuf voisins :
    0,98 1,02 0,99 1,01 1,05 1,00 0,97 1,03 0,96. Triés :
    0,96 0,97 0,98 0,99 1,00 1,01 1,02 1,03 1,05. La cinquième vaut 1,00.

    Le pic isolé, la case (40, 200), neuf voisins :
    0,96 0,10 0,10 0,10 3,00 0,10 0,10 0,10 0,10. Triés : sept fois 0,10, puis
    0,96 puis 3,00. La cinquième vaut 0,10, et l'isolement vaut 3,00 moins 0,10.

    Le coin (5, 50), quatre voisins seulement, la grille s'arrêtant :
    0,98 1,02 1,01 1,05. Médiane paire, donc (1,01 + 1,02) / 2 = 1,015.
    """
    note = plateau_score(synthetic_sweep, ["fast", "slow"], "metric").set_index(["fast", "slow"])

    assert note.loc[(10, 100), "plateau_score"] == pytest.approx(1.00)
    assert note.loc[(10, 100), "isolation"] == pytest.approx(1.05 - 1.00)
    assert note.loc[(10, 100), "neighborhood_size"] == 9
    assert bool(note.loc[(10, 100), "neighborhood_complete"]) is True

    assert note.loc[(40, 200), "plateau_score"] == pytest.approx(0.10)
    assert note.loc[(40, 200), "isolation"] == pytest.approx(2.90)

    assert note.loc[(5, 50), "plateau_score"] == pytest.approx(1.015)
    assert note.loc[(5, 50), "neighborhood_size"] == 4
    assert bool(note.loc[(5, 50), "neighborhood_complete"]) is False


def test_l_agregateur_minimum_lit_le_pire_voisin(synthetic_sweep: pd.DataFrame) -> None:
    """En lecture du pire cas, le centre du plateau tombe à son plus mauvais voisin.

    Source (a) : le voisinage de (10, 100) porte 0,96 comme plus petite valeur,
    lue directement dans la grille écrite à la main.
    """
    note = plateau_score(synthetic_sweep, ["fast", "slow"], "metric", aggregator="min").set_index(
        ["fast", "slow"]
    )
    assert note.loc[(10, 100), "plateau_score"] == pytest.approx(0.96)


def test_la_fraction_de_plateau_compte_les_voisins_au_dessus_du_seuil(
    synthetic_sweep: pd.DataFrame,
) -> None:
    """Au seuil 0,90, huit voisins sur neuf passent autour du centre du plateau.

    Source (a) : le voisinage de (10, 100) porte 0,98 1,02 0,99 1,01 1,05 1,00
    0,97 1,03 0,96, tous supérieurs ou égaux à 0,90, donc neuf sur neuf. Celui
    de (10, 150) porte en plus trois cases à 0,10, donc six sur neuf.
    """
    note = plateau_score(synthetic_sweep, ["fast", "slow"], "metric", threshold=0.90).set_index(
        ["fast", "slow"]
    )
    assert note.loc[(10, 100), "plateau_fraction"] == pytest.approx(1.0)
    assert note.loc[(10, 150), "plateau_fraction"] == pytest.approx(6 / 9)


def test_le_score_compte_les_trous_d_une_grille_incomplete() -> None:
    """Une combinaison absente du balayage réduit le voisinage sans le fausser.

    Source (a) : sur une grille 3 par 3 dont on retire le coin (3, 30), le
    centre (2, 20) n'a plus que huit voisins et son voisinage n'est plus plein.
    """
    sweep = parameter_sweep({"a": (1, 2, 3), "b": (10, 20, 30)}, lambda a, b: 1.0)
    partiel = sweep.loc[~((sweep["a"] == 3) & (sweep["b"] == 30))]
    note = plateau_score(partiel, ["a", "b"], "metric").set_index(["a", "b"])
    assert note.loc[(2, 20), "neighborhood_size"] == 8
    assert bool(note.loc[(2, 20), "neighborhood_complete"]) is False
    assert note.loc[(2, 20), "neighborhood_missing"] == 0


def test_une_metrique_manquante_est_comptee_comme_un_trou() -> None:
    """Une évaluation en échec ne compte pas dans la médiane, et se compte à part.

    Source (a) : sur une grille de trois valeurs toutes à 1,0 dont la deuxième
    échoue, le voisinage du centre porte deux valeurs valides et un trou.
    """

    def evaluer(x: int) -> float:
        if x == 2:
            raise ValueError("échec")
        return 1.0

    sweep = parameter_sweep({"x": (1, 2, 3)}, evaluer, on_error="record")
    note = plateau_score(sweep, ["x"], "metric").set_index("x")
    assert note.loc[2, "neighborhood_size"] == 2
    assert note.loc[2, "neighborhood_missing"] == 1
    assert note.loc[2, "plateau_score"] == pytest.approx(1.0)


def test_le_score_refuse_une_combinaison_en_double() -> None:
    """Deux lignes de mêmes paramètres rendent le voisinage ambigu."""
    double = pd.DataFrame({"x": [1, 1, 2], "metric": [0.5, 0.6, 0.7]})
    with pytest.raises(DataQualityError, match="même combinaison"):
        plateau_score(double, ["x"], "metric")


def test_le_score_refuse_une_colonne_absente(synthetic_sweep: pd.DataFrame) -> None:
    """Une colonne de métrique inconnue lève avant tout calcul."""
    with pytest.raises(ConfigError, match="absente"):
        plateau_score(synthetic_sweep, ["fast", "slow"], "sharpe")


def test_le_score_refuse_un_rayon_negatif(synthetic_sweep: pd.DataFrame) -> None:
    """Un rayon négatif n'a pas de sens géométrique."""
    with pytest.raises(ConfigError, match="neighborhood"):
        plateau_score(synthetic_sweep, ["fast", "slow"], "metric", -1)


# --------------------------------------------------------------------------- #
# best_plateau, le test qui porte le module
# --------------------------------------------------------------------------- #


def test_le_maximum_brut_choisit_le_pic_isole(synthetic_sweep: pd.DataFrame) -> None:
    """Le maximum de la métrique retient la case à 3,00, celle qui est isolée.

    Source (a) : la grille écrite à la main ne porte qu'une case à 3,00, en
    position (40, 200). C'est la moitié attendue du contraste, l'autre moitié
    étant le test qui suit.
    """
    gagnant = synthetic_sweep.loc[synthetic_sweep["metric"].idxmax()]
    assert (int(gagnant["fast"]), int(gagnant["slow"])) == (40, 200)
    assert gagnant["metric"] == pytest.approx(3.00)


def test_le_meilleur_plateau_choisit_le_plateau_et_pas_le_pic(
    synthetic_sweep: pd.DataFrame,
) -> None:
    """Le point retenu est le centre du bloc, dont la métrique est trois fois plus petite.

    Source (a) pour les deux scores, calculés dans le test précédent des
    médianes : 1,00 au centre du plateau, 0,10 au pic isolé. Le classement par
    score de plateau retient donc le centre, dont la métrique brute vaut 1,05
    contre 3,00 au pic. C'est l'écart que la docstring de ``best_plateau``
    annonce, et il est mesuré ici.
    """
    gagnant = best_plateau(synthetic_sweep, ["fast", "slow"], "metric")
    assert (int(gagnant["fast"]), int(gagnant["slow"])) == (10, 100)
    assert gagnant["metric"] == pytest.approx(1.05)
    assert gagnant["plateau_score"] == pytest.approx(1.00)
    assert gagnant["isolation"] == pytest.approx(0.05)

    brut = synthetic_sweep.loc[synthetic_sweep["metric"].idxmax()]
    assert gagnant["metric"] < brut["metric"]


def test_le_meilleur_plateau_ecarte_les_bords_par_defaut(
    synthetic_sweep: pd.DataFrame,
) -> None:
    """Sans exigence de voisinage plein, un bord l'emporte pour une mauvaise raison.

    Source (a) : le coin (5, 50) et le bord (10, 50) ont tous deux une médiane
    de 1,015, calculée sur quatre et six voisins seulement. Cette valeur dépasse
    le 1,00 du centre du plateau, non parce que le bord est meilleur mais parce
    que sa moitié manquante n'a jamais été évaluée. Le départage par la métrique
    brute donne alors (10, 50), dont la métrique vaut 1,01 contre 0,98.

    Le test fixe cette limite déclarée plutôt que de la taire.
    """
    bord = best_plateau(synthetic_sweep, ["fast", "slow"], "metric", require_full_neighborhood=False)
    assert (int(bord["fast"]), int(bord["slow"])) == (10, 50)
    assert bord["plateau_score"] == pytest.approx(1.015)
    assert bord["plateau_score"] > 1.00


def test_le_meilleur_plateau_leve_quand_aucun_voisinage_n_est_plein() -> None:
    """Une grille plus étroite que le voisinage ne permet aucune conclusion.

    Source (b) : sur deux points en une dimension et un rayon de 1, le cube
    plein compte trois cases, donc aucun point ne l'a.
    """
    sweep = parameter_sweep({"x": (1, 2)}, lambda x: float(x))
    with pytest.raises(InsufficientDataError, match="voisinage plein"):
        best_plateau(sweep, ["x"], "metric")


def test_le_departage_se_fait_par_la_metrique_puis_par_l_ordre() -> None:
    """À score égal, la métrique brute départage, puis l'ordre du balayage.

    Source (a) : six points en ligne, de métriques 1,0 3,0 1,0 1,0 3,0 1,0. Les
    quatre points intérieurs ont pour voisinages (1,0 3,0 1,0), (3,0 1,0 1,0),
    (1,0 1,0 3,0) et (1,0 3,0 1,0). Les quatre médianes valent 1,0. Le premier
    départage retient les deux points de métrique 3,0, en x = 2 et x = 5. Le
    second départage retient le premier des deux dans l'ordre du balayage.
    """
    metriques = {1: 1.0, 2: 3.0, 3: 1.0, 4: 1.0, 5: 3.0, 6: 1.0}
    plat = parameter_sweep({"x": tuple(metriques)}, lambda x: metriques[x])
    note = plateau_score(plat, ["x"], "metric")
    interieurs = note.loc[note["neighborhood_complete"].to_numpy(dtype=bool)]
    assert interieurs["plateau_score"].to_numpy() == pytest.approx(1.0)

    gagnant = best_plateau(plat, ["x"], "metric")
    assert int(gagnant["x"]) == 2
    assert gagnant["metric"] == pytest.approx(3.0)
    assert gagnant["plateau_score"] == pytest.approx(1.0)


@settings(deadline=None, max_examples=100)
@given(
    valeurs=st.lists(
        st.floats(min_value=-5.0, max_value=5.0, allow_nan=False, allow_infinity=False),
        min_size=3,
        max_size=15,
    )
)
def test_propriete_le_rayon_nul_est_l_identite(valeurs: list[float]) -> None:
    """Propriété : à rayon nul, le score est la métrique et l'isolement est nul.

    Source (b) : identité mathématique, le voisinage se réduisant au point.
    """
    frame = pd.DataFrame({"p": range(len(valeurs)), "metric": valeurs})
    note = plateau_score(frame, ["p"], "metric", 0)
    assert note["plateau_score"].to_numpy() == pytest.approx(np.asarray(valeurs))
    assert note["isolation"].to_numpy() == pytest.approx(0.0, abs=1e-12)


@settings(deadline=None, max_examples=100)
@given(
    valeurs=st.lists(
        st.floats(min_value=-5.0, max_value=5.0, allow_nan=False, allow_infinity=False),
        min_size=4,
        max_size=15,
    )
)
def test_propriete_le_score_reste_dans_l_enveloppe_du_voisinage(valeurs: list[float]) -> None:
    """Propriété : la médiane d'un voisinage est bornée par son minimum et son maximum.

    Source (b) : propriété élémentaire de la médiane. Elle vaut pour tout
    voisinage non vide, donc pour toute grille en une dimension.
    """
    frame = pd.DataFrame({"p": range(len(valeurs)), "metric": valeurs})
    note = plateau_score(frame, ["p"], "metric", 1)
    tableau = np.asarray(valeurs)
    for position in range(len(valeurs)):
        debut = max(0, position - 1)
        fin = min(len(valeurs), position + 2)
        fenetre = tableau[debut:fin]
        assert note.loc[position, "plateau_score"] >= fenetre.min() - 1e-12
        assert note.loc[position, "plateau_score"] <= fenetre.max() + 1e-12


def test_simulation_le_plateau_bat_le_maximum_brut_sous_bruit() -> None:
    """Sur des données SIMULÉES à vérité connue, le plateau vise mieux que le pic.

    Le montage. La vraie métrique est un dôme quadratique centré sur la case
    (3, 3) d'une grille 7 par 7, valant 1,00 au centre et décroissant de 0,02
    par unité de distance au carré. On y ajoute un bruit gaussien indépendant
    d'écart type 0,10. La vérité est donc CONNUE par construction, et les deux
    règles de sélection se comparent sur la même réalisation.

    Les deux règles sont restreintes aux 25 cases intérieures, pour que le
    filtrage des bords ne soit pas ce qui décide. Ce qui les sépare est donc le
    lissage par le voisinage, et lui seul.

    La tolérance est déclarée en erreurs types, jamais en valeur absolue. On
    mesure la distance au carré entre la case retenue et la vraie case optimale,
    sur 200 tirages indépendants obtenus par ``child_generators``. La
    statistique de test est la moyenne des écarts appariés divisée par son
    erreur type, et le seuil retenu est 3, soit trois erreurs types.

    Source (b) : sous le montage, le maximum brut d'un champ bruité est un
    estimateur biaisé de l'argmax, le bruit maximal se cumulant au signal. La
    médiane de neuf cases divise l'écart type du bruit par environ 2,4, donc
    l'ordre attendu est connu avant la simulation.
    """
    cote = 7
    lignes, colonnes = np.meshgrid(np.arange(cote), np.arange(cote), indexing="ij")
    signal = 1.0 - 0.02 * ((lignes - 3) ** 2 + (colonnes - 3) ** 2)
    n_tirages = 200
    ecarts = np.empty(n_tirages, dtype="float64")

    for essai, generateur in enumerate(child_generators(TEST_SEED, n_tirages)):
        observe = signal + generateur.normal(0.0, 0.10, size=(cote, cote))
        frame = pd.DataFrame({"a": lignes.ravel(), "b": colonnes.ravel(), "metric": observe.ravel()})
        note = plateau_score(frame, ["a", "b"], "metric")
        interieur = note.loc[note["neighborhood_complete"].to_numpy(dtype=bool)]
        par_brut = interieur.loc[interieur["metric"].idxmax()]
        par_plateau = interieur.loc[interieur["plateau_score"].idxmax()]
        d_brut = (par_brut["a"] - 3) ** 2 + (par_brut["b"] - 3) ** 2
        d_plateau = (par_plateau["a"] - 3) ** 2 + (par_plateau["b"] - 3) ** 2
        ecarts[essai] = float(d_brut - d_plateau)

    moyenne = float(ecarts.mean())
    erreur_type = float(ecarts.std(ddof=1) / math.sqrt(n_tirages))
    assert moyenne > 0.0
    assert moyenne / erreur_type > 3.0


# --------------------------------------------------------------------------- #
# sensitivity_analysis
# --------------------------------------------------------------------------- #


def test_l_elasticite_d_une_droite_vaut_un() -> None:
    """Sur une fonction proportionnelle, l'élasticité vaut exactement 1.

    Source (b) : pour ``m(x) = c x``, la variation relative de la métrique est
    celle du paramètre, quel que soit ``c`` non nul et quelle que soit
    l'amplitude de la perturbation.
    """
    table = sensitivity_analysis({"x": 4.0}, lambda x: 3.0 * x, {"x": [1.0, 8.0, 40.0]})
    assert table["elasticity"].to_numpy() == pytest.approx(1.0)


def test_l_elasticite_du_carre_vaut_deux_et_demi_de_deux_vers_trois() -> None:
    """Sur ``m(x) = x^2``, de 2 vers 3, la version en point vaut 2,5.

    Source (a) : la métrique passe de 4 à 9, soit +5/4 = +125 %. Le paramètre
    passe de 2 à 3, soit +1/2 = +50 %. Le rapport vaut 1,25 / 0,5 = 2,5.
    """
    table = sensitivity_analysis({"x": 2.0}, lambda x: x**2, {"x": [3.0]})
    assert table["metric"].iloc[0] == pytest.approx(9.0)
    assert table["relative_metric_change"].iloc[0] == pytest.approx(1.25)
    assert table["relative_param_change"].iloc[0] == pytest.approx(0.5)
    assert table["elasticity"].iloc[0] == pytest.approx(2.5)


def test_l_elasticite_en_arc_du_carre_vaut_vingt_cinq_treiziemes() -> None:
    """La version en arc du même cas vaut exactement 25/13.

    Source (a) : la métrique varie de 5 pour une moyenne de 6,5, soit 10/13. Le
    paramètre varie de 1 pour une moyenne de 2,5, soit 2/5. Le rapport vaut
    (10/13) / (2/5) = 50/26 = 25/13, soit 1,923076...
    """
    table = sensitivity_analysis({"x": 2.0}, lambda x: x**2, {"x": [3.0]}, method="arc")
    assert table["elasticity"].iloc[0] == pytest.approx(25 / 13)


def test_l_elasticite_est_indefinie_quand_la_base_est_nulle() -> None:
    """Un paramètre de base nul rend l'élasticité en point indéfinie.

    Source (b) : le dénominateur ``(x' - x) / x`` n'existe pas en ``x = 0``. La
    fonction rend une valeur manquante plutôt qu'un très grand nombre.
    """
    table = sensitivity_analysis({"x": 0.0}, lambda x: 1.0 + x, {"x": [1.0]})
    assert math.isnan(table["elasticity"].iloc[0])
    assert table["metric"].iloc[0] == pytest.approx(2.0)


def test_la_sensibilite_ne_bouge_qu_un_parametre_a_la_fois() -> None:
    """Les autres paramètres gardent leur valeur de base pendant la perturbation.

    Source (a) : avec ``m(x, y) = 10 y + x``, une perturbation de ``x`` de 1 à 3
    doit rendre 20 + 3 = 23 si ``y`` reste à 2.
    """
    table = sensitivity_analysis({"x": 1.0, "y": 2.0}, lambda x, y: 10.0 * y + x, {"x": [3.0]})
    assert table["metric"].iloc[0] == pytest.approx(23.0)


def test_la_sensibilite_refuse_un_parametre_absent_de_la_base() -> None:
    """Perturber un paramètre qui n'existe pas dans la base lève."""
    with pytest.raises(ConfigError, match="absents"):
        sensitivity_analysis({"x": 1.0}, lambda x: x, {"z": [2.0]})


# --------------------------------------------------------------------------- #
# subperiod_performance
# --------------------------------------------------------------------------- #

#: Les paramètres de la série à Sharpe connu par construction. Chaque moitié
#: alterne deux valeurs symétriques autour de sa moyenne, ce qui fixe la
#: moyenne d'échantillon à ``m`` et l'écart type à ``s * sqrt(n / (n - 1))``.
HALF_LENGTH = 252
MEAN_UP, MEAN_DOWN = 0.0005, -0.0002
DEVIATION = 0.01


def _alternating(mean: float, deviation: float, length: int) -> np.ndarray:
    """Rend une suite alternant ``mean + deviation`` et ``mean - deviation``."""
    signes = np.where(np.arange(length) % 2 == 0, 1.0, -1.0)
    return mean + deviation * signes


@pytest.fixture
def two_halves() -> pd.Series:
    """Rend une série de 504 jours dont chaque moitié a un Sharpe en forme fermée."""
    index = pd.bdate_range("2015-01-01", periods=2 * HALF_LENGTH)
    valeurs = np.concatenate(
        [
            _alternating(MEAN_UP, DEVIATION, HALF_LENGTH),
            _alternating(MEAN_DOWN, DEVIATION, HALF_LENGTH),
        ]
    )
    return pd.Series(valeurs, index=index, name="strategy")


def _closed_form_sharpe(mean: float, deviation: float, length: int) -> float:
    """Rend le Sharpe annualisé attendu d'une moitié alternante.

    La moyenne d'échantillon vaut ``mean``. La somme des carrés des écarts vaut
    ``length * deviation^2``, donc l'écart type à ``ddof=1`` vaut
    ``deviation * sqrt(length / (length - 1))``. Le Sharpe périodique vaut donc
    ``(mean / deviation) * sqrt((length - 1) / length)``. En annualisant sur 252
    séances avec ``length = 252``, les deux racines se simplifient et il reste
    ``(mean / deviation) * sqrt(length - 1)``.
    """
    return (mean / deviation) * math.sqrt(length - 1)


def test_les_deux_moities_ont_leur_sharpe_de_forme_fermee(two_halves: pd.Series) -> None:
    """Le Sharpe de chaque moitié vaut sa forme fermée, au millième de milliardième.

    Source (b) : la forme fermée est démontrée dans ``_closed_form_sharpe``. Avec
    ``m / s = 0,05`` sur la première moitié, elle donne 0,05 fois racine de 251,
    soit 0,792149 ; sur la seconde, ``m / s = -0,02`` donne -0,316860.
    """
    index = two_halves.index
    table = subperiod_performance(two_halves, breakpoints=[index[HALF_LENGTH]], frequency=Frequency.DAILY)
    assert len(table) == 2
    assert table["n_observations"].tolist() == [HALF_LENGTH, HALF_LENGTH]
    assert table["sharpe"].iloc[0] == pytest.approx(
        _closed_form_sharpe(MEAN_UP, DEVIATION, HALF_LENGTH), rel=1e-12
    )
    assert table["sharpe"].iloc[1] == pytest.approx(
        _closed_form_sharpe(MEAN_DOWN, DEVIATION, HALF_LENGTH), rel=1e-12
    )
    assert table["label"].tolist() == ["P1", "P2"]


def test_l_erreur_type_iid_suit_sa_forme_fermee(two_halves: pd.Series) -> None:
    """L'erreur type i.i.d. annualisée vaut la racine de un plus la moitié du carré.

    Source (b) et (c). Jobson et Korkie (1981) corrigés par Memmel (2003)
    donnent une erreur type périodique de racine de ``(1 + SR_p^2 / 2) / T``.
    Avec ``T = 252`` observations et une annualisation en racine de 252, le
    facteur ``sqrt(252)`` annule le ``sqrt(T)`` et il reste
    ``sqrt(1 + SR_p^2 / 2)``, où ``SR_p`` est le Sharpe périodique.
    """
    index = two_halves.index
    table = subperiod_performance(two_halves, breakpoints=[index[HALF_LENGTH]], frequency=Frequency.DAILY)
    sr_periodique = _closed_form_sharpe(MEAN_UP, DEVIATION, HALF_LENGTH) / math.sqrt(252.0)
    attendu = math.sqrt(1.0 + sr_periodique**2 / 2.0)
    assert table["sharpe_se_iid"].iloc[0] == pytest.approx(attendu, rel=1e-12)


def test_le_rendement_total_d_une_moitie_suit_sa_forme_fermee(two_halves: pd.Series) -> None:
    """Le rendement composé d'une moitié alternante a une forme fermée.

    Source (b) : chaque paire de périodes multiplie la richesse par
    ``(1 + m + s)(1 + m - s) = (1 + m)^2 - s^2``. Sur 126 paires, le facteur
    total est cette quantité à la puissance 126.
    """
    index = two_halves.index
    table = subperiod_performance(two_halves, breakpoints=[index[HALF_LENGTH]], frequency=Frequency.DAILY)
    facteur_paire = (1.0 + MEAN_UP) ** 2 - DEVIATION**2
    attendu = facteur_paire ** (HALF_LENGTH / 2) - 1.0
    assert table["total_return"].iloc[0] == pytest.approx(attendu, rel=1e-12)


def test_le_taux_annuel_egale_le_rendement_total_sur_une_annee(two_halves: pd.Series) -> None:
    """Sur exactement 252 séances, le taux annuel composé égale le rendement total.

    Source (b) : la durée en années vaut 252 / 252 = 1, donc la racine unième du
    facteur de croissance est le facteur lui-même.
    """
    index = two_halves.index
    table = subperiod_performance(two_halves, breakpoints=[index[HALF_LENGTH]], frequency=Frequency.DAILY)
    assert table["cagr"].iloc[0] == pytest.approx(table["total_return"].iloc[0], rel=1e-12)


def test_le_taux_de_reussite_d_une_moitie_vaut_un_demi(two_halves: pd.Series) -> None:
    """Une moitié alternante a exactement une période gagnante sur deux.

    Source (a) : les deux valeurs valent 0,0105 et -0,0095 sur la première
    moitié, donc une positive sur deux exactement.
    """
    index = two_halves.index
    table = subperiod_performance(two_halves, breakpoints=[index[HALF_LENGTH]], frequency=Frequency.DAILY)
    assert table["hit_rate"].iloc[0] == pytest.approx(0.5)


def test_un_decoupage_en_deux_egale_la_coupure_a_mi_chemin(two_halves: pd.Series) -> None:
    """``n_periods=2`` et la coupure explicite au milieu donnent le même tableau.

    Source (b) : sur 504 observations, ``numpy.array_split`` en deux tranches
    rend deux blocs de 252, donc la même frontière que l'étiquette du 253e jour.
    """
    index = two_halves.index
    par_coupure = subperiod_performance(
        two_halves, breakpoints=[index[HALF_LENGTH]], frequency=Frequency.DAILY
    )
    par_nombre = subperiod_performance(two_halves, n_periods=2, frequency=Frequency.DAILY)
    pd.testing.assert_frame_equal(par_coupure, par_nombre)


def test_les_etiquettes_fournies_sont_reprises(two_halves: pd.Series) -> None:
    """Les noms de tranches donnés par l'appelant remplacent la numérotation."""
    table = subperiod_performance(
        two_halves, n_periods=2, frequency=Frequency.DAILY, labels=["avant", "après"]
    )
    assert table["label"].tolist() == ["avant", "après"]


def test_le_decoupage_refuse_les_deux_arguments(two_halves: pd.Series) -> None:
    """Donner à la fois des coupures et un nombre de tranches est ambigu."""
    with pytest.raises(ConfigError, match="exactement un argument"):
        subperiod_performance(
            two_halves, breakpoints=[two_halves.index[10]], n_periods=2, frequency=Frequency.DAILY
        )


def test_le_decoupage_refuse_de_n_avoir_aucun_argument(two_halves: pd.Series) -> None:
    """Sans découpage, la fonction n'a rien à faire et le dit."""
    with pytest.raises(ConfigError, match="exactement un argument"):
        subperiod_performance(two_halves, frequency=Frequency.DAILY)


def test_le_decoupage_leve_sur_une_tranche_trop_courte(two_halves: pd.Series) -> None:
    """Une tranche de moins de quatre observations ne porte pas d'erreur type.

    Source (b) : l'erreur type de Lo (2002) estime un moment d'ordre quatre, qui
    exige au moins quatre observations.
    """
    with pytest.raises(InsufficientDataError, match="exigées"):
        subperiod_performance(two_halves, breakpoints=[two_halves.index[2]], frequency=Frequency.DAILY)


def test_le_decoupage_refuse_un_index_decroissant(two_halves: pd.Series) -> None:
    """Un index non croissant rend toute coupure temporelle fausse."""
    with pytest.raises(ConfigError, match="croissant"):
        subperiod_performance(two_halves.iloc[::-1], n_periods=2, frequency=Frequency.DAILY)


# --------------------------------------------------------------------------- #
# cost_multiplier_analysis
# --------------------------------------------------------------------------- #


def test_le_multiple_de_rupture_vaut_le_point_mort_analytique() -> None:
    """Sur une droite décroissante, le multiple rendu est le point mort exact.

    Source (a) et (b). La métrique vaut ``0,90 - 0,12 * m``, donc elle atteint
    zéro en ``m = 0,90 / 0,12 = 7,5``. Aux multiples testés, elle vaut 0,78 puis
    0,66 puis 0,54 puis 0,30 puis -0,30. Le point mort est encadré par 5 et 10,
    et l'interpolation linéaire rend
    ``5 + 5 * 0,30 / (0,30 + 0,30) = 5 + 2,5 = 7,5``, exactement, une
    interpolation linéaire étant exacte sur une droite.
    """
    analyse = cost_multiplier_analysis(lambda m: 0.90 - 0.12 * m)
    assert analyse.status == "bracketed"
    assert analyse.monotone is True
    assert analyse.breakeven_multiplier == pytest.approx(7.5, rel=1e-12)
    assert analyse.table["metric"].tolist() == pytest.approx([0.78, 0.66, 0.54, 0.30, -0.30])
    assert analyse.table["survives"].tolist() == [True, True, True, True, False]


def test_le_seuil_de_survie_deplace_le_point_mort() -> None:
    """Avec un seuil de 0,30, la même droite meurt exactement au multiple 5.

    Source (a) : ``0,90 - 0,12 m = 0,30`` donne ``m = 0,60 / 0,12 = 5``. La
    comparaison de survie étant STRICTE, le multiple 5 est déjà mort, et le
    point mort encadré par 3 et 5 vaut
    ``3 + 2 * (0,54 - 0,30) / (0,54 - 0,30) = 5``.
    """
    analyse = cost_multiplier_analysis(lambda m: 0.90 - 0.12 * m, threshold=0.30)
    assert analyse.breakeven_multiplier == pytest.approx(5.0, rel=1e-9)


def test_une_strategie_qui_tient_partout_n_a_pas_de_point_mort() -> None:
    """Quand la métrique reste positive au multiple 10, aucun point mort n'existe.

    Source (a) : ``1,0 - 0,01 * 10 = 0,90``, strictement positif.
    """
    analyse = cost_multiplier_analysis(lambda m: 1.0 - 0.01 * m)
    assert analyse.status == "survives_all"
    assert analyse.breakeven_multiplier is None


def test_une_strategie_deja_morte_au_multiple_un_est_signalee() -> None:
    """Une métrique négative dès le multiple 1 ne s'interpole pas vers le bas.

    Source (a) : ``0,05 - 0,20 * 1 = -0,15``, déjà sous zéro.
    """
    analyse = cost_multiplier_analysis(lambda m: 0.05 - 0.20 * m)
    assert analyse.status == "dead_at_first"
    assert analyse.breakeven_multiplier is None


def test_l_analyse_de_couts_signale_une_courbe_non_monotone() -> None:
    """Une métrique qui remonte avec les coûts est signalée, non corrigée.

    Source (a) : la suite 0,5 0,4 0,6 0,3 0,1 monte entre le deuxième et le
    troisième multiple, donc la courbe n'est pas décroissante.
    """
    valeurs = {1.0: 0.5, 2.0: 0.4, 3.0: 0.6, 5.0: 0.3, 10.0: -0.1}
    analyse = cost_multiplier_analysis(lambda m: valeurs[m])
    assert analyse.monotone is False


@pytest.mark.parametrize(
    ("multiples", "motif"),
    [
        ((1.0,), "au moins deux"),
        ((2.0, 1.0), "croissants"),
        ((0.0, 1.0), "positifs"),
    ],
)
def test_l_analyse_de_couts_refuse_des_multiples_mal_formes(multiples: tuple[float, ...], motif: str) -> None:
    """Des multiples mal formés lèvent avant toute évaluation."""
    with pytest.raises(ConfigError, match=motif):
        cost_multiplier_analysis(lambda m: 1.0 - 0.1 * m, multiples)


@settings(deadline=None, max_examples=200)
@given(
    pente=st.floats(min_value=0.01, max_value=2.0, allow_nan=False, allow_infinity=False),
    ordonnee=st.floats(min_value=0.02, max_value=8.0, allow_nan=False, allow_infinity=False),
)
def test_propriete_la_courbe_de_couts_decroit_et_son_point_mort_est_analytique(
    pente: float, ordonnee: float
) -> None:
    """Propriété : sur ``b - a m`` avec ``a > 0``, la métrique décroît strictement.

    Source (b) : le point mort analytique vaut ``b / a``, racine de l'affine.
    Quand il tombe entre le premier et le dernier multiple, l'interpolation
    linéaire le retrouve exactement ; sinon le statut rendu dit de quel côté il
    tombe, et le test le vérifie contre la même racine.
    """
    multiples = (1.0, 2.0, 3.0, 5.0, 10.0)
    racine = ordonnee / pente
    assume(abs(racine - multiples[0]) > 1e-6)
    assume(abs(racine - multiples[-1]) > 1e-6)

    analyse = cost_multiplier_analysis(lambda m: ordonnee - pente * m, multiples)
    metriques = analyse.table["metric"].to_numpy()
    assert bool(np.all(np.diff(metriques) < 0.0))
    assert analyse.monotone is True

    if analyse.status == "bracketed":
        assert analyse.breakeven_multiplier == pytest.approx(racine, rel=1e-9)
    elif analyse.status == "survives_all":
        assert racine > multiples[-1]
    else:
        assert racine < multiples[0]


@settings(deadline=None, max_examples=100)
@given(
    pente=st.floats(min_value=0.05, max_value=1.0, allow_nan=False, allow_infinity=False),
    ordonnee=st.floats(min_value=1.0, max_value=5.0, allow_nan=False, allow_infinity=False),
    seuil_bas=st.floats(min_value=-1.0, max_value=0.0, allow_nan=False, allow_infinity=False),
    ecart=st.floats(min_value=0.05, max_value=0.5, allow_nan=False, allow_infinity=False),
)
def test_propriete_un_seuil_plus_haut_avance_la_mort(
    pente: float, ordonnee: float, seuil_bas: float, ecart: float
) -> None:
    """Propriété : exiger davantage ne peut pas retarder le point mort.

    Source (b) : sur une fonction décroissante, la solution de
    ``f(m) = tau`` décroît quand ``tau`` croît. C'est la monotonie que le test
    de la spécification demande, vue du côté du seuil.
    """
    multiples = (1.0, 2.0, 3.0, 5.0, 10.0)
    seuil_haut = seuil_bas + ecart
    bas = cost_multiplier_analysis(lambda m: ordonnee - pente * m, multiples, threshold=seuil_bas)
    haut = cost_multiplier_analysis(lambda m: ordonnee - pente * m, multiples, threshold=seuil_haut)
    if bas.breakeven_multiplier is not None and haut.breakeven_multiplier is not None:
        assert haut.breakeven_multiplier <= bas.breakeven_multiplier + 1e-9


# --------------------------------------------------------------------------- #
# execution_delay_analysis
# --------------------------------------------------------------------------- #


def test_la_retention_suit_la_decroissance_geometrique_posee() -> None:
    """Sur ``m(h) = m0 * rho^h``, la rétention rendue vaut ``rho^h``.

    Source (b) : identité annoncée au point (10) de la docstring. Avec
    ``m0 = 1,4`` et ``rho = 0,5``, la rétention vaut 1, 0,5, 0,25 puis 0,03125,
    cette dernière étant ``0,5^5``.
    """
    table = execution_delay_analysis(lambda h: 1.4 * 0.5**h)
    assert table["delay"].tolist() == [0, 1, 2, 5]
    assert table["retention"].to_numpy() == pytest.approx([1.0, 0.5, 0.25, 0.5**5])
    assert table["decay"].to_numpy() == pytest.approx([0.0, -0.7, -1.05, 1.4 * 0.5**5 - 1.4])


def test_le_seuil_de_retention_decide_de_la_survie() -> None:
    """Au seuil de moitié, seuls les décalages 0 et 1 survivent à ``rho = 0,5``.

    Source (a) : la comparaison est un supérieur ou égal, donc 0,5 passe et 0,25
    ne passe pas.
    """
    table = execution_delay_analysis(lambda h: 1.4 * 0.5**h, retention_threshold=0.5)
    assert table["survives"].tolist() == [True, True, False, False]


def test_une_reference_non_positive_rend_la_retention_indefinie() -> None:
    """Quand le décalage nul ne rapporte rien, la rétention n'a pas de sens.

    Source (b) : diviser par une référence nulle ou négative rendrait un rapport
    ininterprétable, la perte absolue restant lisible.
    """
    table = execution_delay_analysis(lambda h: -0.2 - 0.1 * h)
    assert bool(table["retention"].isna().all())
    assert table["decay"].to_numpy() == pytest.approx([0.0, -0.1, -0.2, -0.5])


@pytest.mark.parametrize(
    ("horizons", "motif"),
    [
        ((), "aucun décalage"),
        ((2, 1), "croissants"),
        ((-1, 0), "positifs"),
    ],
)
def test_l_analyse_de_delai_refuse_des_horizons_mal_formes(horizons: tuple[int, ...], motif: str) -> None:
    """Des décalages mal formés lèvent avant toute évaluation."""
    with pytest.raises(ConfigError, match=motif):
        execution_delay_analysis(lambda h: 1.0, horizons)


# --------------------------------------------------------------------------- #
# RobustnessReport
# --------------------------------------------------------------------------- #


def test_le_rapport_compte_les_essais(synthetic_sweep: pd.DataFrame) -> None:
    """Le nombre d'essais est la hauteur du balayage, intrant du Sharpe dégonflé.

    Source (b) : 5 fois 5 fait 25.
    """
    rapport = RobustnessReport(sample=SampleTag.IN_SAMPLE, cost_basis=CostBasis.NET, sweep=synthetic_sweep)
    assert rapport.n_trials == 25


def test_un_rapport_vide_porte_quand_meme_son_etiquette() -> None:
    """Sans aucune pièce, le tableau garde la ligne d'échantillon.

    C'est la règle 5 : aucun chiffre de performance ne se publie sans son
    étiquette d'échantillon et sa base de coût.
    """
    rapport = RobustnessReport(sample=SampleTag.OUT_OF_SAMPLE, cost_basis=CostBasis.GROSS)
    table = rapport.to_frame()
    assert len(table) == 1
    assert table.loc[0, "detail"] == "OOS, gross"
    assert rapport.n_trials == 0


def test_le_rapport_reunit_les_six_pieces(synthetic_sweep: pd.DataFrame, two_halves: pd.Series) -> None:
    """Le tableau lisible porte une ligne par grandeur qui décide.

    Source (a) pour chaque valeur vérifiée : 25 essais, un maximum brut de 3,00,
    un score de plateau de 1,00 et un multiple de rupture de 7,5, tous établis
    par les tests précédents à partir de la grille écrite à la main.
    """
    rapport = RobustnessReport(
        sample=SampleTag.VALIDATION,
        cost_basis=CostBasis.NET,
        metric_col="metric",
        sweep=synthetic_sweep,
        plateau=best_plateau(synthetic_sweep, ["fast", "slow"], "metric"),
        sensitivity=sensitivity_analysis({"x": 2.0}, lambda x: x**2, {"x": [3.0]}),
        subperiods=subperiod_performance(two_halves, n_periods=2, frequency=Frequency.DAILY),
        costs=cost_multiplier_analysis(lambda m: 0.90 - 0.12 * m),
        delays=execution_delay_analysis(lambda h: 1.4 * 0.5**h),
    )
    table = rapport.to_frame().set_index("quantity")

    assert set(table["section"]) == {
        "échantillon",
        "balayage",
        "plateau",
        "sensibilité",
        "sous-périodes",
        "coûts",
        "délai",
    }
    assert table.loc["combinaisons évaluées", "value"] == pytest.approx(25.0)
    assert table.loc["meilleure métrique brute", "value"] == pytest.approx(3.00)
    assert table.loc["score de plateau", "value"] == pytest.approx(1.00)
    assert table.loc["métrique du point retenu", "value"] == pytest.approx(1.05)
    assert table.loc["élasticité la plus forte", "value"] == pytest.approx(2.5)
    assert table.loc["multiple de rupture", "value"] == pytest.approx(7.5)
    assert table.loc["rétention au plus grand décalage", "value"] == pytest.approx(0.5**5)
    assert table.loc["part de sous-périodes positives", "value"] == pytest.approx(0.5)
    assert table.loc["pire ratio de Sharpe", "value"] == pytest.approx(
        _closed_form_sharpe(MEAN_DOWN, DEVIATION, HALF_LENGTH), rel=1e-12
    )


# --------------------------------------------------------------------------- #
# La docstring du module, dont les nombres se vérifient comme le reste
# --------------------------------------------------------------------------- #

#: La constante d'Euler-Mascheroni. Elle place le second terme de l'espérance du
#: maximum, et l'omettre est l'erreur que ce test surveille.
EULER_MASCHERONI = 0.5772156649015329


def _expected_maximum(n_trials: int) -> float:
    """Rend l'espérance du maximum de ``n_trials`` normales centrées réduites.

    C'est la forme de Bailey et López de Prado (2014), recalculée ici avec
    ``scipy.stats.norm`` seul. Elle ne passe par aucun code du laboratoire, ni
    par ``quantlab.validation.dsr``, ce qui en fait une source (d).
    """
    gauche = norm.ppf(1.0 - 1.0 / n_trials)
    droite = norm.ppf(1.0 - 1.0 / (n_trials * math.e))
    return float((1.0 - EULER_MASCHERONI) * gauche + EULER_MASCHERONI * droite)


def test_les_nombres_d_esperance_du_maximum_de_la_docstring_sont_exacts() -> None:
    """Les quatre nombres cités en tête du module se recalculent à l'identique.

    Source (d) pour l'espérance du maximum, ``scipy.stats.norm`` appliqué à la
    forme de Bailey et López de Prado (2014). Source (b) pour la borne
    asymptotique, racine de deux fois le logarithme du nombre d'essais.

    Ce test existe pour une raison précise. La première rédaction du module
    publiait la borne :math:`\\sqrt{2 \\ln N}` comme si elle était
    l'espérance du maximum. Elle la surestime de 40 % à dix essais, 2,15 contre
    1,57, et surtout elle écrase le rapport entre mille et dix essais à 1,73 au
    lieu de 2,07. Le chiffre qui décide, celui du prix de la recherche
    multiple, était donc faux dans le sens rassurant.
    """
    assert round(_expected_maximum(10), 2) == 1.57
    assert round(_expected_maximum(1000), 2) == 3.26
    assert round(_expected_maximum(1000) / _expected_maximum(10), 2) == 2.07

    assert round(math.sqrt(2.0 * math.log(10)), 2) == 2.15
    assert round(math.sqrt(2.0 * math.log(1000)) / math.sqrt(2.0 * math.log(10)), 2) == 1.73

    # Chaque nombre est épinglé à SA phrase, et non cherché n'importe où dans
    # la docstring. Un simple « 2,07 in doc » laissait passer le retour à
    # l'ancien 1,7, ce chiffre restant présent dans une autre phrase.
    doc = " ".join((robustness.__doc__ or "").split())
    revendications = (
        r"cette espérance de :math:`1{,}57\,\sigma` à :math:`3{,}26\,\sigma`",
        "soit une exigence multipliée par 2,07 pour la même absence de signal",
        "Elle le surestime de 40 % à dix essais, 2,15 contre 1,57",
        "elle écrase le rapport entre 1000 et 10 essais à 1,73 au lieu de 2,07",
    )
    for phrase in revendications:
        assert phrase in doc, f"la docstring ne porte plus la revendication : {phrase}"


def test_l_esperance_du_maximum_de_la_docstring_egale_celle_du_module_dsr() -> None:
    """La forme recalculée ici rend ce que rend le module qui l'emploie.

    Source (d) : deux implémentations séparées du même objet, celle de ce
    fichier et celle de ``quantlab.validation.dsr``, doivent coïncider. Le
    renvoi de la docstring vers ``dsr`` est ainsi vérifié plutôt qu'affirmé.
    """
    from quantlab.validation.dsr import expected_maximum_sharpe

    for essais in (10, 100, 1000):
        attendu = _expected_maximum(essais)
        obtenu = expected_maximum_sharpe(essais, variance_of_trials=1.0)
        assert obtenu == pytest.approx(attendu, rel=1e-12)

"""Tests du module ``quantlab.analytics.drawdown``.

Chaque valeur attendue porte sa source, et aucune ne vient de la sortie du code.
Quatre sources sont admises : (a) un calcul à la main écrit dans le commentaire,
(b) une identité mathématique, (c) une valeur publiée et citée, (d) une
implémentation indépendante appliquée au même intrant.
"""

from __future__ import annotations

import itertools
import math

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from quantlab.analytics.drawdown import (
    average_drawdown,
    conditional_drawdown_at_risk,
    drawdown_series,
    drawdown_table,
    max_drawdown,
    max_drawdown_duration,
    pain_index,
    pain_ratio,
    time_to_recovery,
    ulcer_index,
)
from quantlab.core.determinism import make_generator
from quantlab.core.errors import DataQualityError, InsufficientDataError

# La série de référence du module, construite à la main.
#
#   richesse      100     120      90      110     150
#   sommet        100     120     120      120     150
#   drawdown        0       0   -0,25    -1/12       0
#
# Détail des deux valeurs non nulles :
#   (90 - 120) / 120  = -30/120  = -0,25
#   (110 - 120) / 120 = -10/120  = -1/12 = -0,0833333...
HAND_WEALTH = pd.Series([100.0, 120.0, 90.0, 110.0, 150.0])
HAND_DRAWDOWN = [0.0, 0.0, -0.25, -1.0 / 12.0, 0.0]

# Seconde série de référence, construite pour SÉPARER ce que la première
# confond. Le sommet reste à 100 du début à la fin, donc chaque drawdown est la
# richesse divisée par 100, moins un.
#
#   richesse    100      90      80     100      95      96      97     100
#   drawdown      0   -0,10   -0,20       0   -0,05   -0,04   -0,03       0
#
# Deux épisodes, et ils se contredisent sur tous les points qui comptent :
#   épisode 1, positions 1 et 2 : début 1, creux 2, fin 3, profondeur -0,20,
#              deux périodes sous l'eau, un seul pas du creux au retour ;
#   épisode 2, positions 4 à 6  : début 4, creux 4, fin 7, profondeur -0,05,
#              trois périodes sous l'eau, trois pas du creux au retour.
# Le PLUS PROFOND est donc le plus court, et le PLUS LONG est le moins
# profond. Sans cette opposition, un tri inversé passe inaperçu.
CONTRAST_WEALTH = pd.Series([100.0, 90.0, 80.0, 100.0, 95.0, 96.0, 97.0, 100.0])
CONTRAST_DRAWDOWN = [0.0, -0.10, -0.20, 0.0, -0.05, -0.04, -0.03, 0.0]

RETURN_STRATEGY = st.lists(
    st.floats(min_value=-0.95, max_value=1.0, allow_nan=False, allow_infinity=False),
    min_size=1,
    max_size=60,
)


def _brute_force_max_drawdown(wealth: np.ndarray) -> float:
    """Rend le drawdown maximal par recherche exhaustive sur toutes les paires.

    Implémentation INDÉPENDANTE de celle du module, source (d) des tests. Elle
    ne tient aucun maximum courant : elle regarde les couples de positions
    ``i <= j`` un par un, en :math:`O(n^2)`, et garde le pire rapport. Les deux
    algorithmes ne partagent que la définition, pas le chemin de calcul.
    """
    worst = 0.0
    for i in range(len(wealth)):
        for j in range(i, len(wealth)):
            worst = min(worst, wealth[j] / wealth[i] - 1.0)
    return worst


# --------------------------------------------------------------------------
# Le calcul à la main
# --------------------------------------------------------------------------


def test_drawdown_series_reproduit_le_calcul_a_la_main() -> None:
    """Source (a) : les cinq valeurs sont posées en tête de fichier."""
    result = drawdown_series(HAND_WEALTH, is_wealth=True)
    np.testing.assert_allclose(result.to_numpy(), HAND_DRAWDOWN, atol=1e-15)
    assert result.index.equals(HAND_WEALTH.index)


def test_drawdown_depuis_les_rendements_egale_celui_de_la_richesse() -> None:
    """Source (b) : le drawdown est invariant au niveau de la richesse.

    Les quatre rendements se déduisent de la même série de richesse. La courbe
    reconstruite vaut donc la richesse divisée par 100, et le drawdown, qui est
    un rapport, ne change pas. Le premier point disparaît, un rendement de moins
    qu'un prix.
    """
    returns = HAND_WEALTH.pct_change().dropna().reset_index(drop=True)
    result = drawdown_series(returns, is_wealth=False)
    np.testing.assert_allclose(result.to_numpy(), HAND_DRAWDOWN[1:], atol=1e-15)


def test_le_capital_initial_compte_comme_un_sommet() -> None:
    """Source (a) : un premier rendement de -5 % rend -5 %, pas 0 %.

    Convention déclarée dans la docstring : la richesse part de 1, et 1 est un
    sommet. Avec 1 x 0,95 = 0,95, le drawdown vaut 0,95 / 1 - 1 = -0,05.
    """
    result = drawdown_series(pd.Series([-0.05]), is_wealth=False)
    assert result.iloc[0] == pytest.approx(-0.05, abs=1e-15)


def test_max_drawdown_vaut_un_quart() -> None:
    """Source (a) : le minimum des cinq valeurs posées en tête de fichier."""
    assert max_drawdown(HAND_WEALTH, is_wealth=True) == pytest.approx(-0.25, abs=1e-15)


def test_max_drawdown_egale_la_recherche_exhaustive() -> None:
    """Source (d) : comparaison avec une recherche en O(n²) sur toutes les paires."""
    rng = make_generator(20260901)
    wealth = pd.Series(100.0 * np.exp(np.cumsum(rng.normal(0.0002, 0.01, size=300))))
    expected = _brute_force_max_drawdown(wealth.to_numpy())
    assert max_drawdown(wealth, is_wealth=True) == pytest.approx(expected, rel=1e-12)


# --------------------------------------------------------------------------
# Le tableau des épisodes
# --------------------------------------------------------------------------


def test_table_un_seul_episode_recouvre() -> None:
    """Source (a) : lecture directe des positions de la série de référence.

    L'unique épisode commence en position 2, première période sous l'eau, touche
    son creux à la même position, et se referme en position 4, premier retour au
    sommet. Deux périodes sont sous l'eau, les positions 2 et 3.
    """
    table = drawdown_table(HAND_WEALTH, is_wealth=True)
    assert len(table) == 1
    row = table.iloc[0]
    assert int(row["start"]) == 2
    assert int(row["trough"]) == 2
    assert int(row["end"]) == 4
    assert row["depth"] == pytest.approx(-0.25, abs=1e-15)
    assert int(row["length"]) == 2
    assert int(row["time_to_trough"]) == 1
    assert int(row["recovery"]) == 2
    assert bool(row["recovered"]) is True


def test_table_marque_un_episode_non_recouvre() -> None:
    """Source (a) : la série s'arrête sous l'eau, donc rien à recouvrer.

    Richesse (100, 120, 90) : le sommet vaut 120 et la dernière observation est
    à -25 % de ce sommet. L'épisode reste ouvert, une seule période sous l'eau.
    """
    table = drawdown_table(pd.Series([100.0, 120.0, 90.0]), is_wealth=True)
    assert len(table) == 1
    row = table.iloc[0]
    assert bool(row["recovered"]) is False
    assert pd.isna(row["end"])
    assert pd.isna(row["recovery"])
    assert int(row["length"]) == 1
    assert int(row["time_to_trough"]) == 1
    assert row["depth"] == pytest.approx(-0.25, abs=1e-15)


def test_table_deux_episodes_dans_l_ordre_chronologique() -> None:
    """Source (a) : deux creux séparés par un retour au sommet.

    Richesse (100, 120, 90, 120, 114, 120) : le sommet reste à 120 dès la
    position 1. Drawdowns : 0, 0, -0,25, 0, -0,05, 0, puisque 114 / 120 = 0,95.
    Deux épisodes d'une période chacun, aux positions 2 et 4.
    """
    wealth = pd.Series([100.0, 120.0, 90.0, 120.0, 114.0, 120.0])
    table = drawdown_table(wealth, is_wealth=True)
    assert len(table) == 2
    np.testing.assert_allclose(table["depth"].to_numpy(), [-0.25, -0.05], atol=1e-15)
    np.testing.assert_array_equal(table["start"].to_numpy(), [2, 4])
    np.testing.assert_array_equal(table["end"].to_numpy(), [3, 5])
    assert table["recovered"].all()


def test_table_separe_le_debut_du_creux_sur_deux_episodes_contrastes() -> None:
    """Source (a) : les huit drawdowns sont posés en tête de fichier, sommet à 100.

    Le premier épisode a son creux UNE période après son début, ce que la série
    de référence principale ne montre pas, ses deux positions coïncidant. Une
    colonne ``start`` qui rendrait en fait le creux passerait donc inaperçue
    ailleurs et échoue ici.
    """
    table = drawdown_table(CONTRAST_WEALTH, is_wealth=True)
    assert len(table) == 2
    np.testing.assert_allclose(
        drawdown_series(CONTRAST_WEALTH, is_wealth=True).to_numpy(),
        CONTRAST_DRAWDOWN,
        atol=1e-15,
    )
    np.testing.assert_array_equal(table["start"].to_numpy(), [1, 4])
    np.testing.assert_array_equal(table["trough"].to_numpy(), [2, 4])
    np.testing.assert_array_equal(table["end"].to_numpy(), [3, 7])
    np.testing.assert_allclose(table["depth"].to_numpy(), [-0.20, -0.05], atol=1e-15)
    np.testing.assert_array_equal(table["length"].to_numpy(), [2, 3])
    np.testing.assert_array_equal(table["time_to_trough"].to_numpy(), [2, 1])
    np.testing.assert_array_equal(table["recovery"].to_numpy(), [1, 3])
    assert table["recovered"].all()


def test_trough_prend_la_premiere_position_en_cas_d_egalite() -> None:
    """Source (a) : la docstring promet la première position, deux creux égaux la testent.

    Richesse (100, 90, 90, 100) : le sommet vaut 100 et les positions 1 et 2
    partagent le drawdown -0,10. Le creux annoncé est la position 1.
    """
    table = drawdown_table(pd.Series([100.0, 90.0, 90.0, 100.0]), is_wealth=True)
    assert len(table) == 1
    assert int(table.loc[0, "trough"]) == 1
    assert int(table.loc[0, "time_to_trough"]) == 1
    assert int(table.loc[0, "recovery"]) == 2


def test_table_vide_quand_la_serie_ne_descend_jamais() -> None:
    """Source (b) : sans période négative, il n'y a aucun épisode à décrire."""
    table = drawdown_table(pd.Series([1.0, 2.0, 3.0]), is_wealth=True)
    assert table.empty
    assert list(table.columns) == [
        "start",
        "trough",
        "end",
        "depth",
        "length",
        "time_to_trough",
        "recovery",
        "recovered",
    ]


def test_table_conserve_les_etiquettes_de_dates() -> None:
    """Source (a) : les colonnes portent les dates de l'index, pas des positions."""
    index = pd.date_range("2024-01-31", periods=5, freq="ME")
    table = drawdown_table(pd.Series(HAND_WEALTH.to_numpy(), index=index), is_wealth=True)
    assert table.loc[0, "start"] == pd.Timestamp("2024-03-31")
    assert table.loc[0, "end"] == pd.Timestamp("2024-05-31")


def test_table_date_manquante_quand_l_episode_reste_ouvert() -> None:
    """Source (a) : sur index de dates, une fin absente vaut NaT et non la dernière date."""
    index = pd.date_range("2024-01-31", periods=3, freq="ME")
    table = drawdown_table(pd.Series([100.0, 120.0, 90.0], index=index), is_wealth=True)
    assert table["end"].isna().all()


# --------------------------------------------------------------------------
# Les durées
# --------------------------------------------------------------------------


def test_max_drawdown_duration_compte_les_periodes_sous_l_eau() -> None:
    """Source (a) : positions 2 et 3 sous l'eau, donc deux périodes."""
    assert max_drawdown_duration(HAND_WEALTH, is_wealth=True) == 2


def test_time_to_recovery_du_pire_creux() -> None:
    """Source (a) : du creux en position 2 au retour au sommet en position 4."""
    assert time_to_recovery(HAND_WEALTH, is_wealth=True) == 2


def test_time_to_recovery_vaut_none_si_non_recouvre() -> None:
    """Source (b) : une durée inconnue s'écrit comme absente, jamais comme un nombre."""
    assert time_to_recovery(pd.Series([100.0, 120.0, 90.0]), is_wealth=True) is None


def test_max_drawdown_duration_suit_l_episode_le_plus_long_et_non_le_plus_profond() -> None:
    """Source (a) : trois périodes sous l'eau aux positions 4, 5 et 6.

    Le pire épisode de la série contrastée ne dure que deux périodes, le second
    en dure trois. La fonction rend la plus LONGUE durée, donc 3. Une
    implémentation qui prendrait le minimum, ou qui suivrait l'épisode le plus
    profond, rendrait 2 et échoue ici. Mesuré le 2026-09-01, ce défaut passait
    les quarante-sept tests précédents, tous portés par des séries à un seul
    épisode.
    """
    assert max_drawdown_duration(CONTRAST_WEALTH, is_wealth=True) == 3
    # Contrôle croisé : le pire épisode, lui, ne dure que deux périodes.
    table = drawdown_table(CONTRAST_WEALTH, is_wealth=True)
    assert int(table.loc[table["depth"].idxmin(), "length"]) == 2


def test_time_to_recovery_suit_le_creux_le_plus_profond_et_non_le_plus_long() -> None:
    """Source (a) : du creux en position 2 au retour en position 3, donc une période.

    Le pire creux de la série contrastée vaut -0,20 en position 2 et se referme
    en position 3. Le second épisode, plus long et moins profond, demande trois
    périodes. La fonction suit la PROFONDEUR, donc elle rend 1. Une
    implémentation qui trierait dans l'autre sens rendrait 3, et ce défaut
    passait les quarante-sept tests précédents.
    """
    assert time_to_recovery(CONTRAST_WEALTH, is_wealth=True) == 1
    # Contrôle croisé : l'épisode le plus long, lui, demande trois périodes.
    table = drawdown_table(CONTRAST_WEALTH, is_wealth=True)
    assert int(table.loc[table["length"].idxmax(), "recovery"]) == 3


def test_durees_nulles_sans_drawdown() -> None:
    """Source (b) : une série croissante n'a ni épisode, ni durée."""
    wealth = pd.Series([1.0, 1.5, 2.0])
    assert max_drawdown_duration(wealth, is_wealth=True) == 0
    assert time_to_recovery(wealth, is_wealth=True) == 0


# --------------------------------------------------------------------------
# Moyenne des épisodes
# --------------------------------------------------------------------------


def test_average_drawdown_moyenne_les_profondeurs() -> None:
    """Source (a) : deux épisodes de -0,25 et -0,05, moyenne (-0,25 - 0,05) / 2 = -0,15."""
    wealth = pd.Series([100.0, 120.0, 90.0, 120.0, 114.0, 120.0])
    assert average_drawdown(wealth, is_wealth=True) == pytest.approx(-0.15, abs=1e-15)


def test_average_drawdown_sur_deux_episodes_de_profondeurs_inegales() -> None:
    """Source (a) : (-0,20 - 0,05) / 2 = -0,125 sur la série contrastée."""
    assert average_drawdown(CONTRAST_WEALTH, is_wealth=True) == pytest.approx(-0.125, abs=1e-15)
    # top=2 reprend les deux seuls épisodes, donc la même moyenne.
    assert average_drawdown(CONTRAST_WEALTH, is_wealth=True, top=2) == pytest.approx(-0.125, abs=1e-15)


def test_average_drawdown_nulle_sans_episode() -> None:
    """Source (b) : sans épisode il n'y a rien à moyenner, la fonction rend zéro."""
    assert average_drawdown(pd.Series([1.0, 2.0, 3.0]), is_wealth=True) == 0.0


def test_average_drawdown_top_un_egale_le_maximum() -> None:
    """Source (b) : la moyenne du seul pire épisode est le drawdown maximal."""
    wealth = pd.Series([100.0, 120.0, 90.0, 120.0, 114.0, 120.0])
    assert average_drawdown(wealth, is_wealth=True, top=1) == pytest.approx(
        max_drawdown(wealth, is_wealth=True), abs=1e-15
    )


def test_average_drawdown_refuse_un_top_nul() -> None:
    with pytest.raises(ValueError, match="top"):
        average_drawdown(HAND_WEALTH, is_wealth=True, top=0)


# --------------------------------------------------------------------------
# Indice d'ulcère et indice de peine
# --------------------------------------------------------------------------


def test_ulcer_index_calcul_a_la_main() -> None:
    """Source (a) : forme fermée exacte sur la série de référence.

    Somme des carrés : 0,25² + (1/12)² = 1/16 + 1/144 = 9/144 + 1/144 = 10/144.
    Divisée par les cinq périodes : 10/720 = 1/72.
    Racine : 1 / (6 racine de 2) = 0,117851130197758.
    """
    expected = 1.0 / (6.0 * math.sqrt(2.0))
    assert ulcer_index(HAND_WEALTH, is_wealth=True) == pytest.approx(expected, rel=1e-14)


def test_ulcer_index_nul_sur_une_serie_strictement_croissante() -> None:
    """Source (b) : tous les drawdowns sont nuls, donc leur racine des carrés aussi."""
    assert ulcer_index(pd.Series([1.0, 2.0, 3.0, 4.0]), is_wealth=True) == 0.0
    assert ulcer_index(pd.Series([0.01, 0.02, 0.03]), is_wealth=False) == 0.0


def test_pain_index_calcul_a_la_main() -> None:
    """Source (a) : (0,25 + 1/12) / 5 = (1/3) / 5 = 1/15 = 0,0666666666666667."""
    assert pain_index(HAND_WEALTH, is_wealth=True) == pytest.approx(1.0 / 15.0, rel=1e-14)


def test_pain_index_inferieur_ou_egal_a_l_ulcer_index() -> None:
    """Source (b) : inégalité des normes, la moyenne quadratique majore la moyenne."""
    rng = make_generator(7)
    wealth = pd.Series(np.exp(np.cumsum(rng.normal(0.0, 0.01, size=500))))
    assert pain_index(wealth, is_wealth=True) <= ulcer_index(wealth, is_wealth=True) + 1e-15


def test_pain_ratio_calcul_a_la_main() -> None:
    """Source (a) : 0,10 divisé par 1/15 vaut 1,5 exactement."""
    ratio = pain_ratio(HAND_WEALTH, annualized_excess_return=0.10, is_wealth=True)
    assert ratio == pytest.approx(1.5, rel=1e-14)


def test_pain_ratio_refuse_une_serie_sans_drawdown() -> None:
    """Source (b) : un dénominateur nul ne se remplace pas par un infini."""
    with pytest.raises(InsufficientDataError):
        pain_ratio(pd.Series([1.0, 2.0]), annualized_excess_return=0.1, is_wealth=True)


# --------------------------------------------------------------------------
# Drawdown conditionnel
# --------------------------------------------------------------------------


def test_cdar_calcul_a_la_main() -> None:
    """Source (a) : avec alpha = 0,4 sur cinq périodes, la queue pèse deux observations.

    Pertes classées décroissantes : 0,25 ; 1/12 ; 0 ; 0 ; 0.
    alpha x T = 0,4 x 5 = 2, entier, donc moyenne des deux pires :
    (0,25 + 0,0833333) / 2 = 0,3333333 / 2 = 0,1666667, rendue négative.
    """
    result = conditional_drawdown_at_risk(HAND_WEALTH, alpha=0.4, is_wealth=True)
    assert result == pytest.approx(-1.0 / 6.0, rel=1e-14)


def test_cdar_poids_fractionnaire() -> None:
    """Source (a) : avec alpha = 0,3 sur cinq périodes, la queue pèse 1,5 observation.

    alpha x T = 1,5, donc m = 1 : le poids est de 1 sur la perte 0,25 et de 0,5
    sur la perte 1/12. Total = 0,25 + 0,5 x 0,0833333 = 0,2916667, divisé par
    1,5 = 0,1944444, rendu négatif.
    """
    result = conditional_drawdown_at_risk(HAND_WEALTH, alpha=0.3, is_wealth=True)
    expected = -(0.25 + 0.5 * (1.0 / 12.0)) / 1.5
    assert result == pytest.approx(expected, rel=1e-14)


def test_cdar_tend_vers_le_max_drawdown_quand_alpha_est_petit() -> None:
    """Source (b) : quand alpha x T est inférieur ou égal à 1, la queue est le pire point."""
    wealth = HAND_WEALTH
    assert conditional_drawdown_at_risk(wealth, alpha=0.1, is_wealth=True) == pytest.approx(
        max_drawdown(wealth, is_wealth=True), rel=1e-14
    )


def test_cdar_a_alpha_un_egale_l_oppose_de_l_indice_de_peine() -> None:
    """Source (b) : moyenner toute la queue revient à moyenner toute la série."""
    rng = make_generator(11)
    wealth = pd.Series(np.exp(np.cumsum(rng.normal(0.0, 0.01, size=200))))
    assert conditional_drawdown_at_risk(wealth, alpha=1.0, is_wealth=True) == pytest.approx(
        -pain_index(wealth, is_wealth=True), rel=1e-14
    )


def test_cdar_decroit_quand_alpha_diminue() -> None:
    """Source (b) : une queue plus étroite ne peut contenir que des pertes plus grandes."""
    rng = make_generator(13)
    wealth = pd.Series(np.exp(np.cumsum(rng.normal(0.0, 0.01, size=400))))
    valeurs = [conditional_drawdown_at_risk(wealth, alpha=a, is_wealth=True) for a in (1.0, 0.5, 0.2, 0.05)]
    assert all(earlier >= later - 1e-15 for earlier, later in itertools.pairwise(valeurs))


@pytest.mark.parametrize("alpha", [0.0, -0.1, 1.5])
def test_cdar_refuse_un_alpha_hors_bornes(alpha: float) -> None:
    with pytest.raises(ValueError, match="alpha"):
        conditional_drawdown_at_risk(HAND_WEALTH, alpha=alpha, is_wealth=True)


# --------------------------------------------------------------------------
# Cas limites et qualité des données
# --------------------------------------------------------------------------


def test_serie_vide_leve_insufficient_data() -> None:
    with pytest.raises(InsufficientDataError):
        drawdown_series(pd.Series([], dtype="float64"))


def test_serie_d_un_seul_point() -> None:
    """Source (a) : un seul rendement de -10 % donne un seul drawdown de -10 %."""
    assert drawdown_series(pd.Series([-0.10])).tolist() == [pytest.approx(-0.10, abs=1e-15)]
    assert drawdown_series(pd.Series([50.0]), is_wealth=True).tolist() == [0.0]


def test_serie_constante_n_a_aucun_drawdown() -> None:
    """Source (b) : sans variation, la richesse est toujours à son sommet."""
    flat = pd.Series([0.0, 0.0, 0.0, 0.0])
    assert max_drawdown(flat) == 0.0
    assert ulcer_index(flat) == 0.0
    assert drawdown_table(flat).empty


def test_valeurs_manquantes_levent_data_quality() -> None:
    with pytest.raises(DataQualityError, match="manquantes"):
        drawdown_series(pd.Series([0.01, np.nan, 0.02]))


def test_index_non_croissant_leve_data_quality() -> None:
    index = pd.to_datetime(["2024-01-31", "2024-03-31", "2024-02-29"])
    with pytest.raises(DataQualityError, match="croissant"):
        drawdown_series(pd.Series([1.0, 2.0, 3.0], index=index), is_wealth=True)


def test_index_avec_doublons_leve_data_quality() -> None:
    index = pd.to_datetime(["2024-01-31", "2024-01-31"])
    with pytest.raises(DataQualityError, match="double"):
        drawdown_series(pd.Series([1.0, 2.0], index=index), is_wealth=True)


def test_rendement_de_moins_cent_pourcent() -> None:
    """Source (a) : après une perte totale, la richesse vaut 0 et le drawdown -1.

    Rendements (0,10 ; -1,00 ; 0,00) : la richesse passe de 1 à 1,10 puis à 0,
    et y reste. Le sommet est 1,10, donc le drawdown vaut (0 - 1,10) / 1,10 = -1
    aux deux dernières périodes.
    """
    result = drawdown_series(pd.Series([0.10, -1.0, 0.0]))
    np.testing.assert_allclose(result.to_numpy(), [0.0, -1.0, -1.0], atol=1e-15)
    assert max_drawdown(pd.Series([0.10, -1.0, 0.0])) == pytest.approx(-1.0, abs=1e-15)


def test_rendement_inferieur_a_moins_cent_pourcent_est_refuse() -> None:
    with pytest.raises(DataQualityError, match="-100"):
        drawdown_series(pd.Series([0.10, -1.5]))


def test_richesse_negative_est_refusee() -> None:
    with pytest.raises(DataQualityError, match="négative"):
        drawdown_series(pd.Series([100.0, -5.0]), is_wealth=True)


# --------------------------------------------------------------------------
# Propriétés (hypothesis)
# --------------------------------------------------------------------------


@given(returns=RETURN_STRATEGY)
@settings(max_examples=200, deadline=None)
def test_propriete_drawdown_negatif_ou_nul(returns: list[float]) -> None:
    """Propriété : le drawdown ne dépasse jamais zéro, par définition du sommet.

    Cette propriété a été VIDE jusqu'au 2026-09-01, la fonction plafonnant son
    résultat à zéro avant de le rendre. Mesuré ce jour-là : avec un sommet
    remplacé par une moyenne courante, donc faux, le test passait quand même. Le
    plafonnement a été retiré du module, et la même injection le fait maintenant
    échouer.
    """
    result = drawdown_series(pd.Series(returns))
    assert (result <= 0.0).all()


@given(returns=RETURN_STRATEGY)
@settings(max_examples=200, deadline=None)
def test_propriete_max_drawdown_borne_par_moins_un(returns: list[float]) -> None:
    """Propriété : avec des rendements strictement au-dessus de -100 %, la richesse

    reste positive, donc le drawdown reste au-dessus de -1.
    """
    value = max_drawdown(pd.Series(returns))
    assert -1.0 <= value <= 0.0


@given(
    returns=RETURN_STRATEGY,
    facteur=st.floats(min_value=1e-3, max_value=1e3, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100, deadline=None)
def test_propriete_invariance_d_echelle(returns: list[float], facteur: float) -> None:
    """Propriété : multiplier la richesse par une constante ne change pas le drawdown.

    Le drawdown est un rapport, donc homogène de degré zéro en la richesse.
    """
    wealth = pd.Series(returns).add(1.0).cumprod()
    base = drawdown_series(wealth, is_wealth=True)
    mise_a_l_echelle = drawdown_series(wealth * facteur, is_wealth=True)
    np.testing.assert_allclose(mise_a_l_echelle.to_numpy(), base.to_numpy(), atol=1e-12)


@given(returns=RETURN_STRATEGY)
@settings(max_examples=200, deadline=None)
def test_propriete_identite_des_durees_du_tableau(returns: list[float]) -> None:
    """Propriété : ``length == time_to_trough + recovery - 1`` sur tout épisode recouvré.

    Les deux comptes se recouvrent d'exactement une période, celle du creux.
    """
    table = drawdown_table(pd.Series(returns))
    recouvres = table[table["recovered"]]
    if recouvres.empty:
        return
    attendu = recouvres["time_to_trough"] + recouvres["recovery"] - 1
    assert (recouvres["length"] == attendu).all()


@given(returns=RETURN_STRATEGY)
@settings(max_examples=200, deadline=None)
def test_propriete_le_pire_episode_porte_le_max_drawdown(returns: list[float]) -> None:
    """Propriété : la profondeur minimale du tableau est le drawdown maximal."""
    serie = pd.Series(returns)
    table = drawdown_table(serie)
    value = max_drawdown(serie)
    if table.empty:
        assert value == 0.0
    else:
        assert float(table["depth"].min()) == pytest.approx(value, abs=1e-15)


# --------------------------------------------------------------------------
# La croissance du drawdown maximal avec la longueur de l'échantillon
# --------------------------------------------------------------------------


def test_max_drawdown_croit_en_racine_du_temps() -> None:
    """Source (c) : E[MDD] = racine(pi / 2) x sigma x racine(T) pour une marche sans dérive.

    Résultat de Magdon-Ismail, Atiya, Pratap et Abu-Mostafa (2004), « On the
    maximum drawdown of a Brownian motion », Journal of Applied Probability,
    41(1), 147-161. Il vaut pour un mouvement brownien observé en continu, et la
    simulation ci-dessous n'observe que T points. L'observation discrète
    sous-estime chaque extremum d'environ 0,5826 fois sigma, constante RAPPORTÉE
    par Broadie, Glasserman et Kou (1997), « A continuity correction for discrete
    barrier options », Mathematical Finance, 7(4), 325-349. Un drawdown en
    comporte deux, le sommet et le creux, donc le biais MODÉLISÉ vaut
    2 x 0,5826 x 0,25 / 1000 = 0,000291, soit 2,9 % du niveau attendu à 1 008 pas
    et 5,9 % à 252 pas.

    L'écart MESURÉ le 2026-09-01, sur les 1 500 trajectoires de graine 20260901,
    va dans ce sens et de cette taille : -3,7 % à 1 008 pas (-0,009575 contre
    -0,009948 attendu) et -6,1 % à 252 pas (-0,004672 contre -0,004974). Le
    rapport des deux horizons ressort à 2,0496, le biais frappant plus fort
    l'horizon court. La tolérance de 8 % laisse donc un facteur deux de marge sur
    le biais connu, tout en attrapant une erreur de facteur.

    La richesse simulée part de 1 000 avec des pas de 0,25, donc un écart type
    terminal de 7,9 sur 1 008 pas. Le drawdown relatif est alors très proche du
    drawdown absolu divisé par 1 000, à un demi pour cent près.
    """
    sigma, base, paths = 0.25, 1000.0, 1500
    rng = make_generator(20260901)

    def moyenne_mdd(horizon: int) -> float:
        pas = np.hstack([np.zeros((paths, 1)), rng.normal(0.0, sigma, size=(paths, horizon))])
        richesse = base + np.cumsum(pas, axis=1)
        return float(np.mean([max_drawdown(pd.Series(chemin), is_wealth=True) for chemin in richesse]))

    court, long = 252, 1008
    mdd_court = moyenne_mdd(court)
    mdd_long = moyenne_mdd(long)

    attendu_long = -math.sqrt(math.pi / 2.0) * sigma * math.sqrt(long) / base
    assert mdd_long == pytest.approx(attendu_long, rel=0.08)
    # La loi en racine du temps : quadrupler l'horizon double le drawdown attendu.
    assert mdd_long / mdd_court == pytest.approx(2.0, rel=0.08)

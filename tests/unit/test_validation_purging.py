"""Contrôles du module ``quantlab.validation.purging``.

Chaque valeur attendue vient d'une source déclarée en commentaire, jamais de la
sortie du code. Les quatre sources admises sont le calcul à la main, l'identité
mathématique, la valeur publiée et l'implémentation indépendante.

Le cas de référence de tout le fichier est celui du schéma de la docstring de
``purge`` : quatorze observations quotidiennes, un horizon de deux périodes, un
test aux positions 6 à 9. Il est reconstruit à la main dans ``_hand_case`` et
les observations que la purge doit retirer y sont énumérées.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from quantlab.core.determinism import child_generators
from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.validation.purging import (
    DEFAULT_EMBARGO_FRACTION,
    LeakageReport,
    embargo,
    embargo_size_from_fraction,
    label_spans,
    leakage_report,
    make_label_endtimes,
    overlap_fraction,
    purge,
    purged_embargoed_split,
)

N_HAND = 14
HAND_INDEX = pd.date_range("2020-01-01", periods=N_HAND, freq="D")
HAND_TEST = np.arange(6, 10)
HAND_TRAIN = np.array([p for p in range(N_HAND) if p not in set(HAND_TEST.tolist())])


def _hand_case() -> tuple[pd.DatetimeIndex, pd.Series, np.ndarray, np.ndarray]:
    """Rend l'index, les fins d'étiquette, l'entraînement et le test du cas à la main.

    Les fins d'étiquette sont écrites en clair, sans passer par le code testé :
    l'observation ``i`` finit en ``min(i + 2, 13)``.
    """
    fins = [min(i + 2, N_HAND - 1) for i in range(N_HAND)]
    ends = pd.Series(HAND_INDEX[fins], index=HAND_INDEX, name="label_end")
    return HAND_INDEX, ends, HAND_TRAIN, HAND_TEST


# --------------------------------------------------------------------------- #
# label_spans et make_label_endtimes
# --------------------------------------------------------------------------- #


def test_fins_etiquettes_decalees_de_l_horizon() -> None:
    """Source (b) : identité de définition, la fin de ``i`` est la date de ``i + h``."""
    index = pd.date_range("2021-03-01", periods=10, freq="D")
    ends = make_label_endtimes(index, 3)
    # Pour i de 0 à 6, fin(i) = index[i + 3]. Vérifié terme à terme.
    for i in range(7):
        assert ends.iloc[i] == index[i + 3]


def test_fins_etiquettes_plafonnees_en_queue() -> None:
    """Source (a) : calcul à la main, les trois dernières fins valent la dernière date."""
    index = pd.date_range("2021-03-01", periods=10, freq="D")
    ends = make_label_endtimes(index, 3)
    # i = 7, 8, 9 pointent au-delà de la position 9, donc se plafonnent en index[9].
    assert list(ends.iloc[7:]) == [index[9]] * 3


def test_fins_etiquettes_sans_plafond_valent_nat() -> None:
    """Source (a) : calcul à la main, trois observations sans étiquette observable."""
    index = pd.date_range("2021-03-01", periods=10, freq="D")
    ends = make_label_endtimes(index, 3, clip_tail=False)
    assert ends.iloc[:7].notna().all()
    assert ends.iloc[7:].isna().all()


def test_horizon_nul_donne_une_etiquette_instantanee() -> None:
    """Source (b) : identité, un horizon nul laisse la fin égale au début."""
    index = pd.date_range("2021-03-01", periods=8, freq="D")
    ends = make_label_endtimes(index, 0)
    assert ends.equals(pd.Series(index, index=index, name="label_end"))


def test_label_spans_accepte_une_duree() -> None:
    """Source (a) : calcul à la main, cinq jours de calendrier sur un index quotidien."""
    index = pd.date_range("2021-03-01", periods=10, freq="D")
    spans = label_spans(index, pd.Timedelta(days=5))
    # index[0] + 5 jours = 2021-03-06, qui est index[5].
    assert spans["end"].iloc[0] == pd.Timestamp("2021-03-06")
    # index[9] + 5 jours dépasse la fin, donc se plafonne en index[9].
    assert spans["end"].iloc[9] == index[9]
    assert list(spans.columns) == ["start", "end"]


def test_label_spans_refuse_un_horizon_negatif() -> None:
    """Un horizon négatif ferait remonter le temps à une étiquette."""
    index = pd.date_range("2021-03-01", periods=5, freq="D")
    with pytest.raises(ConfigError, match="positif"):
        label_spans(index, -1)
    with pytest.raises(ConfigError, match="positif"):
        label_spans(index, pd.Timedelta(days=-3))


def test_label_spans_refuse_un_index_non_croissant() -> None:
    """Les positions encodent l'ordre du temps, donc l'index doit être trié."""
    index = pd.DatetimeIndex(["2021-03-03", "2021-03-01", "2021-03-02"])
    with pytest.raises(DataQualityError, match="croissant"):
        label_spans(index, 1)


def test_label_spans_refuse_un_index_avec_doublons() -> None:
    """Une date en double rendrait la position ambiguë."""
    index = pd.DatetimeIndex(["2021-03-01", "2021-03-01", "2021-03-02"])
    with pytest.raises(DataQualityError, match="double"):
        label_spans(index, 1)


# --------------------------------------------------------------------------- #
# purge : le cas construit à la main
# --------------------------------------------------------------------------- #


def test_purge_du_cas_a_la_main() -> None:
    """Source (a) : calcul à la main, énuméré observation par observation.

    Test aux positions 6 à 9, horizon 2. La portée du test va de la date 6
    (début de l'étiquette de l'observation 6) à la date 11 (fin de l'étiquette
    de l'observation 9).

    Observation 0, étiquette [0, 2] : 2 < 6, elle survit.
    Observation 1, étiquette [1, 3] : 3 < 6, elle survit.
    Observation 2, étiquette [2, 4] : 4 < 6, elle survit.
    Observation 3, étiquette [3, 5] : 5 < 6, elle survit.
    Observation 4, étiquette [4, 6] : 6 est dans [6, 11], PURGÉE.
    Observation 5, étiquette [5, 7] : 7 est dans [6, 11], PURGÉE.
    Observation 10, étiquette [10, 12] : 10 est dans [6, 11], PURGÉE.
    Observation 11, étiquette [11, 13] : 11 est dans [6, 11], PURGÉE.
    Observation 12, étiquette [12, 13] : 12 > 11, elle survit.
    Observation 13, étiquette [13, 13] : 13 > 11, elle survit.

    Compte : 4 purgées sur 10, il reste exactement {0, 1, 2, 3, 12, 13}.
    """
    index, ends, train, test = _hand_case()
    kept = purge(train, test, ends, index)
    assert kept.tolist() == [0, 1, 2, 3, 12, 13]
    assert len(kept) == len(train) - 4


def test_purge_ne_retire_rien_avec_un_horizon_nul() -> None:
    """Source (b) : identité, deux points distincts ne s'intersectent jamais.

    Avec un horizon nul, l'étiquette de l'observation i est le singleton
    {date i}. Entraînement et test étant disjoints, aucune intersection n'existe.
    """
    index, _, train, test = _hand_case()
    ends = make_label_endtimes(index, 0)
    kept = purge(train, test, ends, index)
    assert kept.tolist() == train.tolist()


def test_purge_est_un_sous_ensemble_de_l_entrainement() -> None:
    """Source (b) : identité, un filtre ne peut qu'enlever."""
    index, ends, train, test = _hand_case()
    kept = purge(train, test, ends, index)
    assert set(kept.tolist()) <= set(train.tolist())


def test_purge_avec_un_test_non_contigu() -> None:
    """Source (a) : calcul à la main sur deux blocs de test disjoints.

    Index de 14 dates, horizon 1, test aux positions {3, 4} et {9, 10}.
    Portées du test : [3, 5] et [9, 11].
    Observation 2, étiquette [2, 3] : 3 est dans [3, 5], PURGÉE.
    Observation 5, étiquette [5, 6] : 5 est dans [3, 5], PURGÉE.
    Observation 6, étiquette [6, 7] : hors des deux portées, elle survit.
    Observation 8, étiquette [8, 9] : 9 est dans [9, 11], PURGÉE.
    Observation 11, étiquette [11, 12] : 11 est dans [9, 11], PURGÉE.
    Observation 12, étiquette [12, 13] : 12 > 11, elle survit.
    Observation 13, étiquette [13, 13] : 13 > 11, elle survit.
    Compte : 4 purgées sur 10, il reste {0, 1, 6, 7, 12, 13}.
    """
    index = pd.date_range("2020-01-01", periods=14, freq="D")
    ends = make_label_endtimes(index, 1)
    test = np.array([3, 4, 9, 10])
    train = np.array([0, 1, 2, 5, 6, 7, 8, 11, 12, 13])
    kept = purge(train, test, ends, index)
    assert kept.tolist() == [0, 1, 6, 7, 12, 13]


def test_purge_avec_un_horizon_variable_et_une_etiquette_emboitee() -> None:
    """Source (a) : calcul à la main, une étiquette de test en contient une autre.

    Le module accepte un horizon variable, celui de la méthode des trois
    barrières, où une étiquette se ferme dès qu'un seuil est touché. Deux
    étiquettes de test peuvent alors s'emboîter, la seconde finissant avant la
    première. La portée du test reste celle de la plus longue.

    Douze dates, test aux positions 3 et 4. L'étiquette de 3 court jusqu'à la
    date 9, celle de 4 s'arrête dès la date 5. La portée du test est donc
    [3, 9], et non [3, 5] : c'est le maximum des deux fins qui compte, pas la
    dernière lue. Les autres observations gardent un horizon de 2.

    Observation 0, étiquette [0, 2] : 2 < 3, elle survit.
    Observation 1, étiquette [1, 3] : 3 est dans [3, 9], PURGÉE.
    Observation 2, étiquette [2, 4] : PURGÉE.
    Observations 5, 6, 7, 8, étiquettes [5, 7] à [8, 10] : toutes PURGÉES.
    Observation 9, étiquette [9, 11] : 9 est dans [3, 9], PURGÉE.
    Observation 10, étiquette [10, 11] : 10 > 9, elle survit.
    Observation 11, étiquette [11, 11] : elle survit.

    Il reste exactement {0, 10, 11}. Retenir la fin de la dernière étiquette lue
    au lieu du maximum laisserait passer 6, 7, 8 et 9.
    """
    index = pd.date_range("2020-01-01", periods=12, freq="D")
    fins = [min(i + 2, 11) for i in range(12)]
    fins[3] = 9
    fins[4] = 5
    ends = pd.Series(index[fins], index=index, name="label_end")
    test = np.array([3, 4])
    train = np.array([0, 1, 2, 5, 6, 7, 8, 9, 10, 11])
    kept = purge(train, test, ends, index)
    assert kept.tolist() == [0, 10, 11]
    assert leakage_report(train, test, ends, index).test_span_end == index[9]


def test_purge_avec_un_test_vide_ne_retire_rien() -> None:
    """Sans test, rien ne peut fuir vers lui."""
    index, ends, train, _ = _hand_case()
    kept = purge(train, np.array([], dtype=np.int64), ends, index)
    assert kept.tolist() == train.tolist()


def test_purge_refuse_une_position_hors_bornes() -> None:
    """Une position au-delà de l'index n'a pas de date."""
    index, ends, train, test = _hand_case()
    with pytest.raises(ConfigError, match="bornes"):
        purge(np.append(train, 99), test, ends, index)


def test_purge_refuse_des_positions_en_double() -> None:
    """Un doublon fausserait tous les comptes du rapport de fuite."""
    index, ends, train, test = _hand_case()
    with pytest.raises(ConfigError, match="double"):
        purge(np.append(train, train[0]), test, ends, index)


def test_purge_refuse_une_serie_mal_alignee() -> None:
    """La série de fins doit porter exactement l'index des observations."""
    index, ends, train, test = _hand_case()
    decale = ends.iloc[1:]
    with pytest.raises(ConfigError, match="indexée"):
        purge(train, test, decale, index)


def test_purge_refuse_une_fin_manquante_dans_le_decoupage() -> None:
    """Une étiquette sans fin connue arrête le calcul plutôt que de passer."""
    index, _, train, test = _hand_case()
    ends = make_label_endtimes(index, 2, clip_tail=False)
    with pytest.raises(DataQualityError, match="fin connue"):
        purge(train, test, ends, index)


def test_purge_refuse_une_etiquette_qui_remonte_le_temps() -> None:
    """Une fin antérieure au début est une donnée fausse, pas un cas limite."""
    index, ends, train, test = _hand_case()
    casse = ends.copy()
    casse.iloc[4] = index[0]
    with pytest.raises(DataQualityError, match="avant de commencer"):
        purge(train, test, casse, index)


# --------------------------------------------------------------------------- #
# embargo
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("taille", [1, 2, 3, 4])
def test_embargo_retire_exactement_le_nombre_demande(taille: int) -> None:
    """Source (a) : calcul à la main, le test finit en 9 et quatre positions suivent.

    Le test occupe 6 à 9. Les positions d'entraînement postérieures sont 10, 11,
    12 et 13. Un embargo de taille m retire donc les m premières d'entre elles,
    tant que m ne dépasse pas 4.
    """
    _, _, train, test = _hand_case()
    kept = embargo(train, test, taille)
    assert len(train) - len(kept) == taille
    retirees = sorted(set(train.tolist()) - set(kept.tolist()))
    assert retirees == list(range(10, 10 + taille))


def test_embargo_nul_ne_retire_rien() -> None:
    """Source (b) : identité, l'intervalle (e, e] est vide."""
    _, _, train, test = _hand_case()
    assert embargo(train, test, 0).tolist() == train.tolist()


def test_embargo_ne_retire_rien_avant_le_test() -> None:
    """L'embargo est unilatéral : rien de ce qui précède le test ne part."""
    _, _, train, test = _hand_case()
    kept = set(embargo(train, test, 3).tolist())
    assert {0, 1, 2, 3, 4, 5} <= kept


def test_embargo_sature_a_la_fin_de_l_echantillon() -> None:
    """Un embargo plus long que la queue disponible retire seulement la queue."""
    _, _, train, test = _hand_case()
    kept = embargo(train, test, 50)
    assert kept.tolist() == [0, 1, 2, 3, 4, 5]


def test_embargo_par_bloc_sur_un_test_non_contigu() -> None:
    """Source (a) : calcul à la main, un embargo de 2 après chacun des deux blocs.

    Test aux positions {3, 4} et {9, 10}. Les blocs finissent en 4 et en 10.
    Un embargo de 2 retire {5, 6} puis {11, 12}, soit quatre observations.
    """
    test = np.array([3, 4, 9, 10])
    train = np.array([0, 1, 2, 5, 6, 7, 8, 11, 12, 13])
    kept = embargo(train, test, 2)
    assert kept.tolist() == [0, 1, 2, 7, 8, 13]


def test_embargo_refuse_une_taille_negative() -> None:
    """Un embargo négatif ajouterait des observations au lieu d'en retirer."""
    _, _, train, test = _hand_case()
    with pytest.raises(ConfigError, match="positif"):
        embargo(train, test, -1)


def test_embargo_refuse_une_taille_non_entiere() -> None:
    """La taille se compte en périodes de l'index, donc en entier."""
    _, _, train, test = _hand_case()
    with pytest.raises(ConfigError, match="entier"):
        embargo(train, test, 1.5)


# --------------------------------------------------------------------------- #
# embargo_size_from_fraction
# --------------------------------------------------------------------------- #


def test_taille_d_embargo_depuis_la_fraction() -> None:
    """Source (c) : valeur publiée, López de Prado (2018) extrait 7.2, 1 % tronqué.

    Avec 1 000 observations et la fraction par défaut de 0,01, la règle donne
    floor(0,01 x 1000) = 10 périodes.
    """
    assert embargo_size_from_fraction(1000) == 10
    assert DEFAULT_EMBARGO_FRACTION == 0.01


def test_taille_d_embargo_tronque_vers_le_bas() -> None:
    """Source (a) : calcul à la main, floor(0,01 x 250) = floor(2,5) = 2."""
    assert embargo_size_from_fraction(250, 0.01) == 2


@pytest.mark.parametrize("fraction", [-0.01, 1.5])
def test_taille_d_embargo_refuse_une_fraction_hors_bornes(fraction: float) -> None:
    """Une fraction hors de l'intervalle de 0 à 1 n'a pas de sens."""
    with pytest.raises(ConfigError, match="fraction"):
        embargo_size_from_fraction(1000, fraction)


# --------------------------------------------------------------------------- #
# purged_embargoed_split
# --------------------------------------------------------------------------- #


def test_decoupage_purge_et_embargoue_du_cas_a_la_main() -> None:
    """Source (a) : calcul à la main, l'embargo commence où la purge s'arrête.

    La purge laisse {0, 1, 2, 3, 12, 13}. La portée du test s'arrête à la date
    11, donc l'embargo s'ancre en 11 et non en 9. Un embargo de 1 retire la
    position 12, la première que la purge n'a pas prise. Il reste
    {0, 1, 2, 3, 13}.

    Un embargo de 3 viserait 12, 13 et 14 ; la position 14 n'existe pas, donc il
    retire 12 et 13, et il reste {0, 1, 2, 3}.
    """
    index, ends, train, test = _hand_case()
    assert purged_embargoed_split(train, test, ends, index, embargo_size=1).tolist() == [0, 1, 2, 3, 13]
    assert purged_embargoed_split(train, test, ends, index, embargo_size=3).tolist() == [0, 1, 2, 3]


def test_l_embargo_ancre_sur_le_test_seul_serait_absorbe_par_la_purge() -> None:
    """Source (a) : calcul à la main, la faute que l'ancre corrige.

    Ancré sur la dernière observation du test, en 9, un embargo de 2 viserait
    les positions 10 et 11. La purge les a déjà retirées, donc il n'ajouterait
    RIEN. Ancré sur la fin de la portée, en 11, il retire 12 et 13.

    Le contrôle compare les deux ensembles : ils doivent différer de deux
    observations, sans quoi l'embargo est inopérant sous l'horizon.
    """
    index, ends, train, test = _hand_case()
    purge_seule = purge(train, test, ends, index)
    ancre_naive = embargo(purge_seule, test, 2)
    assert ancre_naive.tolist() == purge_seule.tolist()

    correct = purged_embargoed_split(train, test, ends, index, embargo_size=2)
    assert correct.tolist() == [0, 1, 2, 3]
    assert len(purge_seule) - len(correct) == 2


def test_decoupage_sans_embargo_egale_la_purge_seule() -> None:
    """Source (b) : identité, un embargo nul est le filtre neutre."""
    index, ends, train, test = _hand_case()
    a = purged_embargoed_split(train, test, ends, index, embargo_size=0)
    b = purge(train, test, ends, index)
    assert a.tolist() == b.tolist()


def test_l_ordre_des_deux_filtres_est_indifferent() -> None:
    """Source (b) : identité, l'intersection de deux filtres est commutative."""
    index, ends, train, test = _hand_case()
    purge_puis_embargo = embargo(purge(train, test, ends, index), test, 3)
    embargo_puis_purge = purge(embargo(train, test, 3), test, ends, index)
    assert purge_puis_embargo.tolist() == embargo_puis_purge.tolist()


# --------------------------------------------------------------------------- #
# leakage_report et overlap_fraction
# --------------------------------------------------------------------------- #


def test_rapport_de_fuite_du_cas_a_la_main() -> None:
    """Source (a) : calcul à la main sur le cas de référence.

    Quatre observations d'entraînement sur dix recouvrent le test, soit 0,4.
    La portée du test couvre les six dates 6 à 11.
    Le pire recouvrement est celui de l'observation 10 : son étiquette [10, 12]
    contient les dates 10 et 11 de la portée, soit 2 périodes. L'observation 11
    n'en contient qu'une, la date 11. L'observation 5, d'étiquette [5, 7],
    contient les dates 6 et 7, soit 2 périodes également. Le maximum vaut 2.
    """
    index, ends, train, test = _hand_case()
    rapport = leakage_report(train, test, ends, index)
    assert isinstance(rapport, LeakageReport)
    assert rapport.n_train == 10
    assert rapport.n_test == 4
    assert rapport.n_overlapping == 4
    assert rapport.overlap_fraction == pytest.approx(0.4, abs=1e-15)
    assert rapport.max_overlap_periods == 2
    assert rapport.test_span_start == index[6]
    assert rapport.test_span_end == index[11]
    assert rapport.n_test_blocks == 1


def test_rapport_de_fuite_nul_apres_purge() -> None:
    """Source (b) : identité, la purge est définie comme le retrait de la fuite."""
    index, ends, train, test = _hand_case()
    kept = purge(train, test, ends, index)
    rapport = leakage_report(kept, test, ends, index)
    assert rapport.n_overlapping == 0
    assert rapport.overlap_fraction == 0.0
    assert rapport.max_overlap_periods == 0


def test_rapport_de_fuite_compte_les_blocs_de_test() -> None:
    """Source (a) : calcul à la main, deux blocs de test séparés par la position 6.

    Test aux positions {3, 4} et {9, 10}, horizon 1. Les portées sont [3, 5] et
    [9, 11]. Elles ne se touchent pas, donc le rapport compte deux blocs.
    """
    index = pd.date_range("2020-01-01", periods=14, freq="D")
    ends = make_label_endtimes(index, 1)
    test = np.array([3, 4, 9, 10])
    train = np.array([0, 1, 2, 5, 6, 7, 8, 11, 12, 13])
    rapport = leakage_report(train, test, ends, index)
    assert rapport.n_test_blocks == 2
    assert rapport.test_span_start == index[3]
    assert rapport.test_span_end == index[11]


def test_rapport_de_fuite_sans_test() -> None:
    """Sans test, la fuite est nulle et la portée n'existe pas."""
    index, ends, train, _ = _hand_case()
    rapport = leakage_report(train, np.array([], dtype=np.int64), ends, index)
    assert rapport.n_test == 0
    assert rapport.n_overlapping == 0
    assert rapport.test_span_start is None


def test_rapport_de_fuite_refuse_un_entrainement_vide() -> None:
    """Une part sur un ensemble vide n'est pas définie, donc le calcul s'arrête."""
    index, ends, _, test = _hand_case()
    with pytest.raises(InsufficientDataError):
        leakage_report(np.array([], dtype=np.int64), test, ends, index)


def test_rapport_de_fuite_compte_la_derniere_date_de_l_etiquette() -> None:
    """Source (a) : calcul à la main, l'intervalle d'étiquette est FERMÉ à droite.

    Index de huit dates, horizon 2, test réduit à la position 5. La portée du
    test couvre les dates 5, 6 et 7. L'entraînement est réduit à la seule
    observation 3, dont l'étiquette [3, 5] ne touche cette portée que par sa
    dernière date, la date 5.

    Cette date compte, l'intervalle étant fermé aux deux bouts, donc le
    recouvrement vaut 1 période et non 0. Le contrôle est là pour cette
    différence-là : une borne droite ouverte rendrait zéro et laisserait la
    fuite invisible dans le rapport.
    """
    index = pd.date_range("2020-01-01", periods=8, freq="D")
    ends = make_label_endtimes(index, 2)
    rapport = leakage_report(np.array([3]), np.array([5]), ends, index)
    assert rapport.n_overlapping == 1
    assert rapport.max_overlap_periods == 1


def test_le_rapport_se_serialise() -> None:
    """Le rapport rend un dictionnaire, prêt pour un tableau de résultats."""
    index, ends, train, test = _hand_case()
    brut = leakage_report(train, test, ends, index).as_dict()
    assert brut["n_overlapping"] == 4
    assert set(brut) == {
        "n_train",
        "n_test",
        "n_overlapping",
        "overlap_fraction",
        "max_overlap_periods",
        "test_span_start",
        "test_span_end",
        "n_test_blocks",
    }


def test_la_part_contaminee_egale_le_compte_de_la_purge() -> None:
    """Source (b) : identité, les deux fonctions partagent le même prédicat."""
    index, ends, train, test = _hand_case()
    kept = purge(train, test, ends, index)
    attendu = (len(train) - len(kept)) / len(train)
    assert overlap_fraction(train, test, ends, index) == pytest.approx(attendu, abs=1e-15)


def test_la_part_contaminee_est_nulle_avec_un_horizon_nul() -> None:
    """Source (b) : identité, un horizon nul ne crée aucun recouvrement."""
    index, _, train, test = _hand_case()
    ends = make_label_endtimes(index, 0)
    assert overlap_fraction(train, test, ends, index) == 0.0


# --------------------------------------------------------------------------- #
# Le coût de la purge, vérifié sur l'exemple chiffré de la documentation
# --------------------------------------------------------------------------- #


def test_cout_modelise_de_la_documentation() -> None:
    """Source (a) : le calcul à la main de la docstring du module, refait en grand.

    Mille observations quotidiennes, horizon de 20 jours, dix plis. Le pli
    central occupe les positions 500 à 599. Une observation p avant le test a
    son étiquette qui finit en p + 20, donc elle touche le test dès p >= 480,
    ce qui fait 20 observations, de 480 à 499.

    Après le test, une observation p touche encore la portée tant que
    p <= 619, la fin de l'étiquette de l'observation 599. Cela fait 20
    observations de plus, de 600 à 619, et c'est la raison pour laquelle
    l'embargo ne commence à mordre qu'au-delà.

    Total attendu : 40 observations purgées sur 900, soit 4,4 % de
    l'entraînement. La docstring annonce 20 par FRONTIÈRE, et il y a deux
    frontières autour d'un pli central. Vingt sur mille font bien 2,0 % de
    l'échantillon par frontière.
    """
    index = pd.date_range("2018-01-01", periods=1000, freq="D")
    ends = make_label_endtimes(index, 20)
    test = np.arange(500, 600)
    train = np.array([p for p in range(1000) if not 500 <= p < 600])
    kept = purge(train, test, ends, index)
    retirees = sorted(set(train.tolist()) - set(kept.tolist()))
    assert retirees == list(range(480, 500)) + list(range(600, 620))
    assert len(retirees) == 40
    assert len(retirees) / len(train) == pytest.approx(40 / 900, abs=1e-15)
    # Vingt observations à la frontière qui précède le test, soit 2,0 % des
    # mille observations de l'échantillon, comme l'annonce la docstring du module.
    frontiere_avant = [p for p in retirees if p < 500]
    assert len(frontiere_avant) == 20
    assert len(frontiere_avant) / 1000 == pytest.approx(0.02, abs=1e-15)


def test_cout_croit_avec_l_horizon() -> None:
    """Source (a) : calcul à la main, un horizon de 250 purge 250 observations par côté.

    Avec le même découpage et un horizon d'un an de calendrier, soit 250
    périodes, la purge retire les positions 250 à 499 puis 600 à 849. Cela fait
    500 observations sur 900, soit 55,6 % de l'entraînement, et non les 27,8 %
    que donnerait une seule frontière.
    """
    index = pd.date_range("2018-01-01", periods=1000, freq="D")
    ends = make_label_endtimes(index, 250)
    test = np.arange(500, 600)
    train = np.array([p for p in range(1000) if not 500 <= p < 600])
    part = overlap_fraction(train, test, ends, index)
    assert part == pytest.approx(500 / 900, abs=1e-12)


# --------------------------------------------------------------------------- #
# Confrontation à une implémentation indépendante
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(("purge_taille", "embargo_taille"), [(3, 0), (0, 2), (3, 2), (1, 4)])
def test_le_decoupage_complet_egale_celui_de_skfolio(purge_taille: int, embargo_taille: int) -> None:
    """Source (d) : implémentation indépendante, ``skfolio.CombinatorialPurgedCV``.

    ``skfolio`` retire ``purged_size`` observations avant chaque bloc de test et
    ``purged_size + embargo_size`` après. Le module obtient le même résultat
    autrement : la purge par recouvrement d'étiquettes avec un horizon égal à
    ``purged_size``, puis l'embargo ancré sur la fin de la portée du test.

    L'égalité doit tenir sur les quinze découpages de la validation croisée
    combinatoire, blocs de test non contigus compris. Aucune tolérance, les deux
    résultats sont des ensembles de positions entières.

    Le contrôle est celui qui attrape l'ancre fautive : avec un embargo ancré sur
    la dernière observation du test, les cas où ``embargo_size`` est inférieur à
    ``purged_size`` rendent trop d'observations d'entraînement.
    """
    from skfolio.model_selection import CombinatorialPurgedCV

    n, n_folds = 120, 6
    index = pd.date_range("2019-01-01", periods=n, freq="B")
    ends = make_label_endtimes(index, purge_taille)
    donnees = np.zeros((n, 1))

    cv = CombinatorialPurgedCV(
        n_folds=n_folds,
        n_test_folds=2,
        purged_size=purge_taille,
        embargo_size=embargo_taille,
    )
    n_decoupages = 0
    for train_skfolio, blocs in cv.split(donnees):
        test = np.sort(np.concatenate(blocs))
        train = np.array([p for p in range(n) if p not in set(test.tolist())])
        kept = purged_embargoed_split(train, test, ends, index, embargo_size=embargo_taille)
        assert kept.tolist() == np.asarray(train_skfolio).tolist()
        n_decoupages += 1
    # C(6, 2) = 15 découpages, la valeur vient du coefficient binomial, pas du code.
    assert n_decoupages == 15


# --------------------------------------------------------------------------- #
# Propriétés
# --------------------------------------------------------------------------- #

_SPLIT = st.builds(
    lambda n, debut, longueur, horizon: (n, debut % max(n - longueur, 1), longueur, horizon),
    n=st.integers(min_value=6, max_value=60),
    debut=st.integers(min_value=0, max_value=59),
    longueur=st.integers(min_value=1, max_value=5),
    horizon=st.integers(min_value=0, max_value=8),
)


@given(cas=_SPLIT)
@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_propriete_aucune_etiquette_ne_deborde_apres_purge(cas: tuple[int, int, int, int]) -> None:
    """Source (b) : identité, après purge aucune étiquette ne finit après le début du test.

    La propriété demandée est celle-ci : une observation d'entraînement conservée
    et antérieure au test a son étiquette qui se termine strictement avant la
    première date du test. C'est la définition même de la purge, vérifiée ici
    sur des découpages tirés au hasard plutôt que sur un seul cas.
    """
    n, debut, longueur, horizon = cas
    longueur = min(longueur, n - 1)
    debut = min(debut, n - longueur - 1)
    index = pd.date_range("2020-01-01", periods=n, freq="D")
    ends = make_label_endtimes(index, horizon)
    test = np.arange(debut, debut + longueur)
    train = np.array([p for p in range(n) if not debut <= p < debut + longueur])
    kept = purge(train, test, ends, index)

    debut_du_test = index[debut]
    for p in kept.tolist():
        if index[p] < debut_du_test:
            assert ends.iloc[p] < debut_du_test


@given(cas=_SPLIT)
@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_propriete_purge_monotone_en_horizon(cas: tuple[int, int, int, int]) -> None:
    """Source (b) : identité, un horizon plus long ne peut que purger davantage.

    Allonger l'étiquette agrandit chaque intervalle d'entraînement et chaque
    intervalle de test. Un recouvrement déjà présent ne peut donc pas disparaître.
    """
    n, debut, longueur, horizon = cas
    longueur = min(longueur, n - 1)
    debut = min(debut, n - longueur - 1)
    index = pd.date_range("2020-01-01", periods=n, freq="D")
    test = np.arange(debut, debut + longueur)
    train = np.array([p for p in range(n) if not debut <= p < debut + longueur])

    court = purge(train, test, make_label_endtimes(index, horizon), index)
    long = purge(train, test, make_label_endtimes(index, horizon + 1), index)
    assert set(long.tolist()) <= set(court.tolist())


@given(cas=_SPLIT, taille=st.integers(min_value=0, max_value=10))
@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_propriete_le_decoupage_complet_est_inclus_dans_la_purge(
    cas: tuple[int, int, int, int], taille: int
) -> None:
    """Source (b) : identité, ajouter un filtre ne peut qu'enlever."""
    n, debut, longueur, horizon = cas
    longueur = min(longueur, n - 1)
    debut = min(debut, n - longueur - 1)
    index = pd.date_range("2020-01-01", periods=n, freq="D")
    ends = make_label_endtimes(index, horizon)
    test = np.arange(debut, debut + longueur)
    train = np.array([p for p in range(n) if not debut <= p < debut + longueur])

    complet = purged_embargoed_split(train, test, ends, index, embargo_size=taille)
    purge_seule = purge(train, test, ends, index)
    assert set(complet.tolist()) <= set(purge_seule.tolist())
    assert set(purge_seule.tolist()) <= set(train.tolist())


# --------------------------------------------------------------------------- #
# Simulation à vérité connue
# --------------------------------------------------------------------------- #


def test_simulation_la_purge_efface_la_fuite_construite() -> None:
    """Source (a) : vérité connue par construction, comparée à un compte exact.

    **Le montage.** Le trait de l'observation ``p`` est la somme des rendements
    des dates ``p + 1`` à ``p + 10``, et rien d'autre. Deux observations
    partagent donc de l'information si et seulement si leurs fenêtres de
    rendements se recoupent. La fuite devient un fait d'ensembles, vérifiable
    sans statistique.

    **La vérité connue.** Le test occupe les positions 200 à 249, donc ses
    étiquettes consomment les rendements des dates 201 à 259. Une observation
    d'entraînement ``p`` fuit si ``[p + 1, p + 10]`` recoupe ``[201, 259]``,
    c'est-à-dire si ``p + 10 >= 201`` et ``p + 1 <= 259``. Cela donne les
    positions 191 à 199 avant le test et 250 à 258 après, soit 18 observations.

    **Ce que la purge retire, et pourquoi c'est deux de plus.** Elle raisonne sur
    des intervalles FERMÉS de dates, donc elle retire 190 à 199 et 250 à 259,
    soit 20 observations. Les deux extra, 190 et 259, touchent la portée du test
    par une date commune sans partager le moindre rendement. La purge est donc
    prudente d'une observation à chaque frontière, et le test le chiffre plutôt
    que de le supposer.

    Aucune tolérance : les deux ensembles sont comparés terme à terme.
    """
    rng = child_generators(20260901, 1)[0]
    n, horizon = 400, 10
    index = pd.date_range("2019-01-01", periods=n, freq="B")
    rendements = rng.normal(0.0, 0.01, size=n)
    ends = make_label_endtimes(index, horizon)

    debut, fin = 200, 249
    test = np.arange(debut, fin + 1)
    train = np.array([p for p in range(n) if not debut <= p <= fin])

    # Les rendements que consomme le test : de debut + 1 à fin + horizon.
    rendements_du_test = set(range(debut + 1, fin + horizon + 1))
    assert rendements_du_test == set(range(201, 260))

    def fenetre(p: int) -> set[int]:
        """Les indices de rendement qui entrent dans le trait de ``p``."""
        return set(range(p + 1, p + horizon + 1))

    fuient = sorted(p for p in train.tolist() if fenetre(p) & rendements_du_test)
    assert fuient == list(range(191, 200)) + list(range(250, 259))
    assert len(fuient) == 18

    kept = purge(train, test, ends, index)
    retirees = sorted(set(train.tolist()) - set(kept.tolist()))
    assert retirees == list(range(190, 200)) + list(range(250, 260))
    assert len(retirees) - len(fuient) == 2
    assert sorted(set(retirees) - set(fuient)) == [190, 259]

    # Aucune observation conservée ne partage un rendement avec le test.
    for p in kept.tolist():
        assert not fenetre(p) & rendements_du_test
    assert leakage_report(kept, test, ends, index).n_overlapping == 0
    # Le trait existe et n'est pas dégénéré : sans cela le contrôle ci-dessus
    # serait vrai pour de mauvaises raisons.
    assert rendements.std() > 0.0


def test_simulation_correlation_de_fuite_contre_sa_forme_fermee() -> None:
    """Source (b) : forme fermée de la corrélation, tolérance en erreurs types.

    **La grandeur mesurée.** Les rendements sont indépendants et de même
    variance. Le trait de ``p`` est la somme de dix d'entre eux, la cible du
    test la somme des cinquante-neuf rendements des dates 201 à 259. La
    corrélation entre les deux ne dépend donc que du nombre de rendements
    communs :

        rho = k / sqrt(10 x 59), où k est ce nombre.

    Pour l'observation 195, le trait couvre les rendements 196 à 205, donc
    k = 5 et rho = 5 / sqrt(590) = 0,2058. Pour l'observation 189, le trait
    couvre 190 à 199, donc k = 0 et rho = 0 exactement.

    **La tolérance.** L'écart type d'une corrélation d'échantillon vaut environ
    (1 - rho^2) / sqrt(R) sur R tirages indépendants. Avec R = 4 000, cela fait
    0,0151 pour l'observation 195 et 0,0158 pour l'observation 189. Le seuil
    retenu est de quatre erreurs types, soit une probabilité de fausse alarme de
    l'ordre de 6 sur 100 000 sous la loi normale. La graine est fixée, donc le
    résultat est reproductible.

    **Le lien avec la purge.** L'observation 195 est celle que la purge retire,
    l'observation 189 celle qu'elle garde. Le test vérifie les deux décisions et
    les deux corrélations, pour que la mesure et la règle se répondent.
    """
    rng = child_generators(20260901, 3)[2]
    n, horizon, n_tirages = 280, 10, 4000
    index = pd.date_range("2019-01-01", periods=n, freq="B")
    ends = make_label_endtimes(index, horizon)
    debut, fin = 200, 249
    test = np.arange(debut, fin + 1)
    train = np.array([p for p in range(n) if not debut <= p <= fin])

    kept = set(purge(train, test, ends, index).tolist())
    assert 195 not in kept
    assert 189 in kept

    tirages = rng.normal(0.0, 0.01, size=(n_tirages, n))
    cumul = np.concatenate([np.zeros((n_tirages, 1)), tirages.cumsum(axis=1)], axis=1)

    def somme(a: int, b: int) -> np.ndarray:
        """La somme des rendements des dates ``a`` à ``b``, bornes comprises."""
        return cumul[:, b + 1] - cumul[:, a]

    cible = somme(debut + 1, fin + horizon)
    assert cible.size == n_tirages

    # Forme fermée, écrite ici et non lue dans la sortie du code.
    n_cible = fin + horizon - debut  # 59 rendements
    rho_attendu = {195: 5 / np.sqrt(horizon * n_cible), 189: 0.0}
    for p, rho in rho_attendu.items():
        trait = somme(p + 1, p + horizon)
        mesure = float(np.corrcoef(trait, cible)[0, 1])
        erreur_type = (1.0 - rho**2) / np.sqrt(n_tirages)
        assert abs(mesure - rho) < 4.0 * erreur_type


def test_simulation_la_part_contaminee_suit_la_formule() -> None:
    """Source (a) : forme fermée du nombre d'observations purgées, sur cent tirages.

    Pour un pli de test contigu [d, f] et un horizon h, la purge retire les
    observations de d - h à d - 1 avant le test. Après le test, elle retire
    celles de f + 1 à f + h, dès que ces positions existent.
    Le compte attendu se calcule donc en forme
    fermée, et le test le compare au compte réalisé sur cent découpages tirés au
    hasard. Aucune tolérance : les deux nombres sont entiers et doivent coïncider.
    """
    rng = child_generators(20260901, 2)[1]
    n = 300
    index = pd.date_range("2019-01-01", periods=n, freq="B")
    for _ in range(100):
        horizon = int(rng.integers(0, 25))
        longueur = int(rng.integers(5, 60))
        debut = int(rng.integers(0, n - longueur))
        fin = debut + longueur - 1
        ends = make_label_endtimes(index, horizon)
        test = np.arange(debut, fin + 1)
        train = np.array([p for p in range(n) if not debut <= p <= fin])

        avant = len([p for p in range(max(debut - horizon, 0), debut)])
        apres = len([p for p in range(fin + 1, min(fin + horizon + 1, n))])
        attendu = avant + apres

        kept = purge(train, test, ends, index)
        assert len(train) - len(kept) == attendu

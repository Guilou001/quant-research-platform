"""Contrôles de ``quantlab.validation.splits``.

Aucune valeur attendue de ce fichier ne vient de la sortie du code. Chacune
porte sa source en commentaire : (a) calcul à la main, (b) identité ou forme
fermée, (c) valeur publiée et citée, (d) implémentation indépendante.
"""

from __future__ import annotations

import hypothesis.strategies as st
import numpy as np
import pandas as pd
import pytest
from hypothesis import assume, given, settings

from quantlab.core.determinism import child_generators
from quantlab.core.errors import (
    ConfigError,
    DataQualityError,
    InsufficientDataError,
    LookAheadError,
)
from quantlab.core.types import SampleTag
from quantlab.validation.splits import (
    ExpandingSplit,
    RollingSplit,
    TimeSplit,
    WalkForward,
    assert_chronological,
    chronological_split,
    split_report,
    train_test_split_forbidden,
)

# Cent jours calendaires à partir du 1er janvier 2020. Le 100e est le 9 avril
# 2020 : 31 jours en janvier, 29 en février (année bissextile), 31 en mars,
# soit 91 jours, plus 9 en avril.
DATES = pd.date_range("2020-01-01", periods=100, freq="D")


# --------------------------------------------------------------------------
# Le découpage fixe, borné à la main
# --------------------------------------------------------------------------


def test_chronological_split_bornes_a_la_main() -> None:
    """(a) Comptage à la main sur les cent dates quotidiennes de 2020.

    Entraînement jusqu'au 1er février inclus : les 31 jours de janvier plus le
    1er février font 32 dates.
    Réglage du 2 février au 1er mars inclus : du 2 au 29 février font 28 dates
    (2020 est bissextile), plus le 1er mars, soit 29 dates.
    Test : ce qui reste, 100 - 32 - 29 = 39 dates, du 2 mars au 9 avril.
    """
    split = chronological_split(DATES, "2020-02-01", "2020-03-01")

    assert len(split.train) == 32
    assert len(split.validation) == 29
    assert len(split.test) == 39
    assert len(split.final_holdout) == 0
    assert split.train[0] == pd.Timestamp("2020-01-01")
    assert split.train[-1] == pd.Timestamp("2020-02-01")
    assert split.validation[0] == pd.Timestamp("2020-02-02")
    assert split.validation[-1] == pd.Timestamp("2020-03-01")
    assert split.test[0] == pd.Timestamp("2020-03-02")
    assert split.test[-1] == pd.Timestamp("2020-04-09")


def test_chronological_split_avec_segment_scelle_a_la_main() -> None:
    """(a) Comptage à la main, segment scellé à partir du 1er avril 2020.

    Avril 2020 est représenté du 1er au 9, soit 9 dates scellées.
    Le test perd ces 9 dates : 39 - 9 = 30, du 2 mars au 31 mars.
    La somme redonne 32 + 29 + 30 + 9 = 100.
    """
    split = chronological_split(DATES, "2020-02-01", "2020-03-01", "2020-04-01")

    assert len(split.train) == 32
    assert len(split.validation) == 29
    assert len(split.test) == 30
    assert len(split.final_holdout) == 9
    assert split.test[-1] == pd.Timestamp("2020-03-31")
    assert split.final_holdout[0] == pd.Timestamp("2020-04-01")
    assert split.n_observations == 100


def test_chronological_split_partition_exacte() -> None:
    """(b) Identité de partition : la concaténation des segments redonne l'index."""
    split = chronological_split(DATES, "2020-02-01", "2020-03-01", "2020-04-01")
    reconstitue = split.train.append(split.validation).append(split.test).append(split.final_holdout)
    assert reconstitue.equals(DATES)


def test_chronological_split_etiquettes_d_echantillon() -> None:
    """(b) Chaque segment porte l'étiquette prévue par ``quantlab.core.types``."""
    assert TimeSplit.tag_of("train") is SampleTag.IN_SAMPLE
    assert TimeSplit.tag_of("validation") is SampleTag.VALIDATION
    assert TimeSplit.tag_of("test") is SampleTag.OUT_OF_SAMPLE
    assert TimeSplit.tag_of("final_holdout") is SampleTag.FINAL_HOLDOUT
    with pytest.raises(ConfigError, match="segment inconnu"):
        TimeSplit.tag_of("oos")


def test_chronological_split_refuse_des_bornes_inversees() -> None:
    """(b) La borne de réglage doit suivre strictement celle d'entraînement."""
    with pytest.raises(ConfigError, match="train_end"):
        chronological_split(DATES, "2020-03-01", "2020-02-01")


def test_chronological_split_refuse_un_holdout_trop_tot() -> None:
    """(b) Un segment scellé qui commence avant la fin du réglage vide le test."""
    with pytest.raises(ConfigError, match="final_holdout_start"):
        chronological_split(DATES, "2020-02-01", "2020-03-01", "2020-02-15")


def test_chronological_split_refuse_un_segment_vide() -> None:
    """(b) Deux bornes trop rapprochées ne laissent aucune date de réglage.

    Entre le 1er février exclu et le 2 février inclus, l'index quotidien ne
    porte que le 2 février. En prenant deux bornes qui se suivent sans date
    intermédiaire sur un index mensuel, le segment est vide.
    """
    mensuel = pd.date_range("2020-01-31", periods=12, freq="ME")
    with pytest.raises(InsufficientDataError, match="vides"):
        chronological_split(mensuel, "2020-03-31", "2020-04-15")


def test_chronological_split_refuse_un_index_non_trie() -> None:
    """(b) Un index décroissant rend l'ordre du temps ininterprétable."""
    with pytest.raises(DataQualityError, match="croissant"):
        chronological_split(DATES[::-1], "2020-02-01", "2020-03-01")


def test_chronological_split_refuse_des_dates_en_double() -> None:
    """(b) Deux observations à la même date rendent la partition ambiguë."""
    doublon = DATES.append(pd.DatetimeIndex([DATES[10]])).sort_values()
    with pytest.raises(DataQualityError, match="double"):
        chronological_split(doublon, "2020-02-01", "2020-03-01")


def test_chronological_split_refuse_un_index_vide() -> None:
    """(b) Un index vide n'a rien à partager, et l'erreur reste une erreur du paquet.

    Sans ce contrôle, la construction du message d'erreur lit ``index[0]`` sur
    un index de longueur nulle et lève un ``IndexError`` de numpy. L'appelant
    qui intercepte ``QuantLabError`` ne le verrait pas passer.
    """
    with pytest.raises(InsufficientDataError, match="vide"):
        chronological_split(pd.DatetimeIndex([]), "2020-02-01", "2020-03-01")


def test_time_split_refuse_le_recouvrement() -> None:
    """(a) Deux segments qui partagent une date sont refusés à la construction.

    L'entraînement va du 1er au 10 janvier, le réglage du 10 au 20. Le 10
    janvier appartient aux deux, donc les segments se recouvrent.
    """
    train = pd.date_range("2020-01-01", "2020-01-10", freq="D")
    validation = pd.date_range("2020-01-10", "2020-01-20", freq="D")
    with pytest.raises(DataQualityError, match="recouvrent"):
        TimeSplit(
            train=train,
            validation=validation,
            test=pd.date_range("2020-01-21", "2020-01-25", freq="D"),
            final_holdout=pd.DatetimeIndex([]),
        )


# --------------------------------------------------------------------------
# Le garde-fou chronologique
# --------------------------------------------------------------------------


def test_assert_chronological_accepte_un_pli_correct() -> None:
    """(a) Entraînement 0 à 2, test 3 à 4 : le maximum 2 précède le minimum 3."""
    assert_chronological(np.array([0, 1, 2]), np.array([3, 4]))


def test_assert_chronological_leve_sur_un_recouvrement() -> None:
    """(a) Cas construit : une seule position d'entraînement dépasse.

    Entraînement 0, 1, 2, 5. Test 3, 4, 5, 6. Le maximum d'entraînement vaut 5
    et le minimum de test vaut 3, donc l'inégalité 5 < 3 est fausse.
    Une seule position d'entraînement atteint ou dépasse 3, la position 5 :
    0, 1 et 2 restent sous 3. Le message doit donc annoncer une observation.
    """
    with pytest.raises(LookAheadError, match="1 observation"):
        assert_chronological(np.array([0, 1, 2, 5]), np.array([3, 4, 5, 6]))


def test_assert_chronological_leve_sur_l_egalite() -> None:
    """(a) L'inégalité est stricte : la position 3 partagée est déjà une fuite."""
    with pytest.raises(LookAheadError):
        assert_chronological(np.array([0, 3]), np.array([3, 4]))


def test_assert_chronological_leve_sur_un_ensemble_vide() -> None:
    """(b) Un pli dont un côté est vide ne rend aucune mesure."""
    with pytest.raises(InsufficientDataError):
        assert_chronological(np.array([], dtype=int), np.array([1, 2]))


def test_assert_chronological_marche_sur_des_dates() -> None:
    """(a) Le garde-fou compare aussi bien des dates que des positions."""
    with pytest.raises(LookAheadError):
        assert_chronological(DATES[:60], DATES[50:])


# --------------------------------------------------------------------------
# Le mélange interdit
# --------------------------------------------------------------------------


def test_train_test_split_forbidden_leve_toujours() -> None:
    """(b) La fonction lève quels que soient ses arguments."""
    with pytest.raises(LookAheadError):
        train_test_split_forbidden()
    with pytest.raises(LookAheadError):
        train_test_split_forbidden(np.arange(10), test_size=0.2, shuffle=True)


def test_train_test_split_forbidden_explique_le_mecanisme() -> None:
    """(b) Le message nomme le mécanisme et la sortie de secours."""
    with pytest.raises(LookAheadError) as excinfo:
        train_test_split_forbidden()
    message = str(excinfo.value)
    assert "2020" in message and "2015" in message
    assert "chronological_split" in message
    assert "WalkForward" in message


# --------------------------------------------------------------------------
# Le nombre de plis, calculé à la main
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("n", "train_size", "test_size", "step", "attendu"),
    [
        # (a) Calculs à la main par K = (n - L_tr - L_te) // s + 1.
        # 100 dates, 50 d'entraînement, 10 de test, pas 10 : (100-60)//10+1 = 5.
        (100, 50, 10, None, 5),
        # Pas de 7 : (100-60)//7+1 = 40//7+1 = 5+1 = 6. Derniers blocs de test
        # à 50, 57, 64, 71, 78, 85 ; le sixième finit en 95, donc il tient.
        (100, 50, 10, 7, 6),
        # Pas de 5 avec 60 et 20 : (100-80)//5+1 = 4+1 = 5.
        (100, 60, 20, 5, 5),
        # Juste de quoi faire un seul pli : (60-60)//10+1 = 1.
        (60, 50, 10, None, 1),
        # Pas plus grand que le bloc de test : (100-60)//25+1 = 1+1 = 2.
        (100, 50, 10, 25, 2),
    ],
)
def test_nombre_de_plis_calcule_a_la_main(
    n: int, train_size: int, test_size: int, step: int | None, attendu: int
) -> None:
    """(a) Le nombre de plis suit la formule du module, ancré comme glissant."""
    for anchored in (False, True):
        cv = WalkForward(train_size=train_size, test_size=test_size, step=step, anchored=anchored)
        assert cv.get_n_splits(n) == attendu
        assert len(list(cv.split(n))) == attendu


def test_bornes_des_plis_glissants_a_la_main() -> None:
    """(a) Cinq plis sur cent positions, fenêtre glissante de 50, test de 10.

    Les blocs de test occupent 50 à 59, 60 à 69, 70 à 79, 80 à 89, 90 à 99.
    Les fenêtres d'entraînement partent de 0, 10, 20, 30 et 40, et gardent
    toutes 50 positions.
    """
    folds = list(RollingSplit(train_size=50, test_size=10).split(100))

    assert [len(train) for train, _ in folds] == [50, 50, 50, 50, 50]
    assert [int(train[0]) for train, _ in folds] == [0, 10, 20, 30, 40]
    assert [int(test[0]) for _, test in folds] == [50, 60, 70, 80, 90]
    assert [int(test[-1]) for _, test in folds] == [59, 69, 79, 89, 99]


def test_bornes_des_plis_ancres_a_la_main() -> None:
    """(a) Mêmes blocs de test, mais la fenêtre d'entraînement part toujours de 0.

    Elle porte donc 50, 60, 70, 80 puis 90 positions.
    """
    folds = list(ExpandingSplit(train_size=50, test_size=10).split(100))

    assert [len(train) for train, _ in folds] == [50, 60, 70, 80, 90]
    assert [int(train[0]) for train, _ in folds] == [0, 0, 0, 0, 0]
    assert [int(test[0]) for _, test in folds] == [50, 60, 70, 80, 90]


def test_les_alias_valent_leur_reglage_explicite() -> None:
    """(b) Les alias ne font rien de plus que fixer ``anchored``."""
    for alias, anchored in ((ExpandingSplit, True), (RollingSplit, False)):
        reference = WalkForward(train_size=30, test_size=5, step=5, anchored=anchored, purge=2)
        essai = alias(train_size=30, test_size=5, step=5, purge=2)
        assert essai.anchored is anchored
        for (t1, s1), (t2, s2) in zip(reference.split(100), essai.split(100), strict=True):
            assert np.array_equal(t1, t2)
            assert np.array_equal(s1, s2)


# --------------------------------------------------------------------------
# Purge et embargo
# --------------------------------------------------------------------------


def test_la_purge_raccourcit_la_fenetre_glissante_a_la_main() -> None:
    """(a) Purge de 5 sur une fenêtre glissante de 50 : il reste 45 positions.

    Le premier bloc de test commence en 50, donc l'entraînement s'arrête en 44
    inclus au lieu de 49. Il part toujours de 0, donc 45 positions.
    """
    train, test = next(iter(RollingSplit(train_size=50, test_size=10, purge=5).split(100)))

    assert len(train) == 45
    assert int(train[0]) == 0
    assert int(train[-1]) == 44
    assert int(test[0]) == 50


def test_la_purge_raccourcit_la_fenetre_ancree_a_la_main() -> None:
    """(a) Purge de 5, variante ancrée : le deuxième pli porte 55 positions.

    Son bloc de test commence en 60, l'entraînement s'arrête donc en 54 inclus,
    et il part de 0.
    """
    folds = list(ExpandingSplit(train_size=50, test_size=10, purge=5).split(100))
    train, test = folds[1]

    assert len(train) == 55
    assert int(train[-1]) == 54
    assert int(test[0]) == 60


@pytest.mark.parametrize(
    ("anchored", "attendu"),
    [
        # (a) Calcul à la main. Blocs de test en 50-59, 60-69, 70-79, 80-89,
        # 90-99, donc zones d'embargo en 60-64, 70-74, 80-84, 90-94.
        # Ancré : fenêtres [0,50), [0,60), [0,70), [0,80), [0,90), dont on
        # retire les zones antérieures, soit 50, 60, 70-5, 80-10, 90-15.
        (True, [50, 60, 65, 70, 75]),
        # Glissant : fenêtres [0,50), [10,60), [20,70), [30,80), [40,90),
        # soit 50, 50, 50-5, 50-10, 50-15.
        (False, [50, 50, 45, 40, 35]),
    ],
)
def test_l_embargo_mord_a_partir_du_deuxieme_pli_suivant(anchored: bool, attendu: list[int]) -> None:
    """(a) La zone d'embargo du pli j n'atteint la fenêtre du pli k qu'à partir de k = j + 2.

    La condition du module s'écrit (k - j) fois le pas strictement supérieur au
    bloc de test augmenté de la purge. Avec un pas de 10, un bloc de 10 et une
    purge nulle, elle se lit k au moins égal à j + 2. Le pli 1 ne perd donc rien
    et les suivants perdent 5 positions par bloc de test antérieur.
    """
    folds = list(WalkForward(train_size=50, test_size=10, anchored=anchored, embargo=5).split(100))
    assert [len(train) for train, _ in folds] == attendu
    # Le pli 2 perd exactement les positions 60 à 64, et garde 59 et 65.
    train_deux = set(folds[2][0].tolist())
    assert set(range(60, 65)).isdisjoint(train_deux)
    assert {59, 65}.issubset(train_deux)


def test_l_embargo_ne_mord_pas_sur_le_pli_immediatement_suivant() -> None:
    """(a) Le pli 1 est identique avec et sans embargo, la condition n'étant pas remplie.

    Sa fenêtre ancrée s'arrête en 59 inclus et la zone d'embargo du pli 0
    commence en 60.
    """
    sans = list(WalkForward(train_size=50, test_size=10, anchored=True).split(100))
    avec = list(WalkForward(train_size=50, test_size=10, anchored=True, embargo=5).split(100))

    for k in (0, 1):
        assert np.array_equal(sans[k][0], avec[k][0])
        assert np.array_equal(sans[k][1], avec[k][1])
    assert not np.array_equal(sans[2][0], avec[2][0])


def test_l_embargo_mord_quand_les_blocs_de_test_sont_espaces() -> None:
    """(a) Calcul à la main, pas 20, bloc de test 10, embargo 5, variante ancrée.

    Le pli 0 teste sur 50 à 59, le pli 1 sur 70 à 79. La fenêtre ancrée du pli 1
    couvre 0 à 69, soit 70 positions. L'embargo du pli 0 retire 60 à 64, soit 5
    positions, et il en reste 65.
    """
    folds = list(WalkForward(train_size=50, test_size=10, step=20, anchored=True, embargo=5).split(100))
    train, test = folds[1]

    assert int(test[0]) == 70
    assert len(train) == 65
    assert 59 in set(train.tolist())
    assert set(range(60, 65)).isdisjoint(set(train.tolist()))
    assert 65 in set(train.tolist())


def test_l_embargo_qui_vide_une_fenetre_leve_au_lieu_de_rendre_moins_de_plis() -> None:
    """(a) Calcul à la main : quatre positions, fenêtre 1, test 1, embargo 1.

    La formule donne (4 - 2) // 1 + 1 = 3 plis. Les blocs de test occupent la
    position 1, puis 2, puis 3. Les zones d'embargo couvrent donc 2, puis 3,
    puis la position 4 qui tombe au-delà des données. La fenêtre glissante du
    pli 2 est la seule position 2, mise sous embargo par le pli 0, donc vide.

    Le module lève plutôt que de rendre deux plis là où ``get_n_splits`` en
    annonce trois. Un compte silencieusement plus court fausserait toute erreur
    type calculée sur les plis.
    """
    cv = WalkForward(train_size=1, test_size=1, embargo=1)
    assert cv.get_n_splits(4) == 3
    with pytest.raises(InsufficientDataError, match="pli 2"):
        list(cv.split(4))


def test_reglages_hors_domaine_refuses() -> None:
    """(b) Les cinq contrôles de domaine lèvent ``ConfigError``."""
    with pytest.raises(ConfigError, match="train_size"):
        WalkForward(train_size=0, test_size=10)
    with pytest.raises(ConfigError, match="test_size"):
        WalkForward(train_size=10, test_size=0)
    with pytest.raises(ConfigError, match="purge"):
        WalkForward(train_size=10, test_size=5, purge=-1)
    with pytest.raises(ConfigError, match="embargo"):
        WalkForward(train_size=10, test_size=5, embargo=-1)
    with pytest.raises(ConfigError, match="step"):
        WalkForward(train_size=10, test_size=5, step=0)
    with pytest.raises(ConfigError, match="sous train_size"):
        WalkForward(train_size=10, test_size=5, purge=10)


def test_donnees_trop_courtes_refusees() -> None:
    """(b) Moins de ``train_size + test_size`` observations ne fait aucun pli."""
    cv = WalkForward(train_size=50, test_size=10)
    with pytest.raises(InsufficientDataError, match="60"):
        cv.get_n_splits(59)
    with pytest.raises(InsufficientDataError):
        list(cv.split(59))


def test_donnees_absentes_refusees() -> None:
    """(b) Le nombre de plis dépend de la longueur, il ne se devine pas."""
    with pytest.raises(ConfigError):
        WalkForward(train_size=50, test_size=10).get_n_splits()


# --------------------------------------------------------------------------
# Le tableau de découpage
# --------------------------------------------------------------------------


def test_split_report_d_un_decoupage_fixe() -> None:
    """(a) Les parts valent 32, 29, 30 et 9 centièmes, et somment à un."""
    split = chronological_split(DATES, "2020-02-01", "2020-03-01", "2020-04-01")
    report = split_report(split, DATES)

    assert list(report["segment"]) == ["train", "validation", "test", "final_holdout"]
    assert list(report["n_obs"]) == [32, 29, 30, 9]
    assert report["share"].sum() == pytest.approx(1.0, abs=1e-15)
    assert report.loc[0, "share"] == pytest.approx(0.32, abs=1e-15)
    assert report.loc[3, "start"] == pd.Timestamp("2020-04-01")


def test_split_report_d_une_analyse_glissante() -> None:
    """(a) Cinq plis, deux lignes chacun, donc dix lignes.

    La part d'un bloc de test vaut 10 sur 100, soit un dixième.
    """
    report = split_report(RollingSplit(train_size=50, test_size=10), DATES)

    assert len(report) == 10
    assert list(report["fold"]) == [0, 0, 1, 1, 2, 2, 3, 3, 4, 4]
    assert set(report["part"]) == {"train", "test"}
    tests = report[report["part"] == "test"]
    assert list(tests["n_obs"]) == [10, 10, 10, 10, 10]
    assert tests["share"].to_numpy() == pytest.approx(np.full(5, 0.10), abs=1e-15)
    assert tests.iloc[0]["start"] == DATES[50]
    assert tests.iloc[-1]["end"] == DATES[99]


def test_split_report_refuse_un_index_de_mauvaise_longueur() -> None:
    """(b) Un index plus court que le découpage rendrait des parts fausses."""
    split = chronological_split(DATES, "2020-02-01", "2020-03-01")
    with pytest.raises(DataQualityError, match="couvre"):
        split_report(split, DATES[:50])


def test_split_report_refuse_un_objet_etranger() -> None:
    """(b) Le tableau ne se construit que sur les deux types du module."""
    with pytest.raises(TypeError, match="TimeSplit"):
        split_report(object(), DATES)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# Propriétés hypothesis
# --------------------------------------------------------------------------


@given(
    n=st.integers(min_value=2, max_value=250),
    train_size=st.integers(min_value=1, max_value=80),
    test_size=st.integers(min_value=1, max_value=40),
    step=st.integers(min_value=1, max_value=30),
    purge=st.integers(min_value=0, max_value=12),
    embargo=st.integers(min_value=0, max_value=12),
    anchored=st.booleans(),
)
@settings(max_examples=400, deadline=None)
def test_propriete_l_entrainement_precede_toujours_le_test(
    n: int,
    train_size: int,
    test_size: int,
    step: int,
    purge: int,
    embargo: int,
    anchored: bool,
) -> None:
    """(b) Propriété : pour tout pli, max(train) < min(test), avec la purge en prime.

    La vérification est indépendante du garde-fou interne : elle recalcule
    l'inégalité, l'intersection des deux ensembles et l'écart minimal imposé
    par la purge, qui vaut au moins ``purge + 1`` positions.
    """
    assume(purge < train_size)
    assume(n >= train_size + test_size)
    cv = WalkForward(
        train_size=train_size,
        test_size=test_size,
        step=step,
        anchored=anchored,
        purge=purge,
        embargo=embargo,
    )
    try:
        folds = list(cv.split(n))
    except InsufficientDataError:
        return

    assert len(folds) == cv.get_n_splits(n)
    for train_idx, test_idx in folds:
        assert train_idx.size > 0
        assert test_idx.size == test_size
        assert int(train_idx.max()) < int(test_idx.min())
        assert int(test_idx.min()) - int(train_idx.max()) >= purge + 1
        assert np.intersect1d(train_idx, test_idx).size == 0
        assert int(test_idx.max()) < n
        assert np.array_equal(np.sort(train_idx), train_idx)


@given(
    debut=st.integers(min_value=5, max_value=40),
    milieu=st.integers(min_value=1, max_value=30),
    fin=st.integers(min_value=1, max_value=20),
)
@settings(max_examples=200, deadline=None)
def test_propriete_la_partition_couvre_l_index(debut: int, milieu: int, fin: int) -> None:
    """(b) Propriété de partition : les quatre segments redonnent l'index exact.

    Les trois bornes sont tirées comme des positions, ce qui garantit qu'aucun
    segment n'est vide.
    """
    assume(debut + milieu + fin < len(DATES))
    split = chronological_split(
        DATES,
        DATES[debut - 1],
        DATES[debut + milieu - 1],
        DATES[debut + milieu + fin],
    )
    reconstitue = split.train.append(split.validation).append(split.test).append(split.final_holdout)
    assert reconstitue.equals(DATES)
    assert len(split.train) == debut
    assert len(split.validation) == milieu


# --------------------------------------------------------------------------
# Simulation : ce que le mélange coûte, mesuré sur une vérité connue
# --------------------------------------------------------------------------

#: Longueur de la marche aléatoire simulée.
SIM_N = 1000
#: Longueur de la fenêtre d'entraînement de l'analyse glissante simulée.
SIM_TRAIN = 500
#: Longueur du bloc de test simulé.
SIM_TEST = 10
#: Nombre de blocs de la validation croisée mélangée simulée.
SIM_FOLDS = 5
#: Nombre de graines indépendantes, obtenues par ``child_generators``.
SIM_SEEDS = 6
#: Graine de l'expérience.
SIM_SEED = 20260901


def _one_nn_mse(y: np.ndarray, train_idx: np.ndarray, test_idx: np.ndarray) -> float:
    """Erreur quadratique moyenne du plus proche voisin dans le temps.

    Le modèle prédit la valeur de la position d'entraînement la plus proche en
    temps. Sur une marche aléatoire, l'erreur d'un tel modèle vaut exactement la
    distance qui sépare le point à prévoir de son voisin, en variance.
    """
    ordonnes = np.sort(train_idx)
    pos = np.searchsorted(ordonnes, test_idx)
    gauche = ordonnes[np.clip(pos - 1, 0, ordonnes.size - 1)]
    droite = ordonnes[np.clip(pos, 0, ordonnes.size - 1)]
    choix = np.where(np.abs(gauche - test_idx) <= np.abs(droite - test_idx), gauche, droite)
    return float(np.mean((y[test_idx] - y[choix]) ** 2))


def test_le_melange_gonfle_la_mesure_hors_echantillon() -> None:
    """(b) Simulation à vérité connue : les deux erreurs ont une forme fermée.

    La cible est une marche aléatoire à incréments normaux centrés réduits, donc
    la variance d'un écart de d pas vaut exactement d.

    Sous mélange en cinq blocs, le voisin d'entraînement le plus proche est à un
    pas sauf si les deux voisins immédiats sont eux aussi en test. Cela arrive
    avec une probabilité de (1/5) au carré. L'espérance de la distance vaut donc
    1 + (1/5)^2 + (1/5)^4 + ..., soit 1,0417 à quatre décimales, et l'erreur
    quadratique attendue vaut ce même nombre.

    Sous analyse glissante, le voisin est toujours la dernière position
    d'entraînement, et le j-ième point du bloc de test en est à j pas. La
    moyenne sur j = 1 à 10 vaut (10 + 1) / 2 = 5,5.

    Tolérances déclarées en erreurs types, et non choisies pour que le test
    passe. Pour l'analyse glissante, la variance de la moyenne d'un pli vaut 2
    fois la somme des min(j,k) au carré divisée par 100. Cette somme vaut
    21 x 385 - 2 x 3025 = 2035, donc la variance vaut 40,7 et l'écart type d'un
    pli 6,38. Les blocs de test étant disjoints, les 50 plis sont indépendants,
    et sur 6 graines l'erreur type de la moyenne vaut 6,38 / racine(300) = 0,37.
    La bande retenue, plus ou moins 1,2, fait 3,3 erreurs types.

    Pour le mélange, l'erreur d'un point vaut d fois un khi-deux à un degré de
    liberté, de variance 2 d au carré. Avec E[d] = 1,042 et E[d au carré] = 1,13,
    la variance d'un point vaut environ 2,3. Les 6 000 points traités comme
    indépendants donnent une erreur type de 0,020, majorant l'erreur type de
    0,011 mesurée entre les six graines. La bande de plus ou moins 0,08 fait
    donc au moins quatre erreurs types.
    """
    melange: list[float] = []
    glissant: list[float] = []
    cv = RollingSplit(train_size=SIM_TRAIN, test_size=SIM_TEST)

    for rng in child_generators(SIM_SEED, SIM_SEEDS):
        y = np.cumsum(rng.standard_normal(SIM_N))

        blocs = np.array_split(rng.permutation(SIM_N), SIM_FOLDS)
        erreurs = [
            _one_nn_mse(
                y,
                np.concatenate([b for j, b in enumerate(blocs) if j != i]),
                blocs[i],
            )
            for i in range(SIM_FOLDS)
        ]
        melange.append(float(np.mean(erreurs)))

        glissant.append(float(np.mean([_one_nn_mse(y, tr, te) for tr, te in cv.split(SIM_N)])))

    mse_melange = float(np.mean(melange))
    mse_glissant = float(np.mean(glissant))

    assert mse_melange == pytest.approx(1.0417, abs=0.08)
    assert mse_glissant == pytest.approx(5.5, abs=1.2)
    # Le rapport attendu vaut 5,5 / 1,0417 = 5,28. Le seuil de 3 laisse une
    # marge confortable et rend le test insensible au bruit de simulation.
    assert mse_glissant / mse_melange > 3.0

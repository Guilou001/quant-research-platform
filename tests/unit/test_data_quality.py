"""Tests de ``quantlab.data.quality.checks``.

Aucune valeur attendue de ce fichier ne vient de la sortie du code. Chaque test
dit dans son commentaire de quelle source elle vient, parmi les quatre
suivantes :

- (a) un calcul écrit à la main, chiffres visibles dans le commentaire ;
- (b) une identité ou une propriété mathématique, par exemple
  « le nombre de lignes en trop vaut la longueur moins le nombre de valeurs
  distinctes » ;
- (c) une valeur publiée, ici le calendrier des jours fériés de la Bourse de
  New York pour 2023, et le règlement du contrat de pétrole WTI de mai 2020 ;
- (d) une implémentation indépendante appliquée au même intrant, ici une
  boucle Python écrite dans le test, ``pandas.bdate_range`` privé des jours
  fériés publiés, et ``exchange_calendars`` par l'intermédiaire de
  :func:`quantlab.core.calendars.sessions`.

Aucun test ne sort sur le réseau. ``exchange_calendars`` porte ses jours fériés
dans le paquet installé.
"""

from __future__ import annotations

from functools import partial

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from quantlab.core.determinism import child_generators
from quantlab.core.errors import DataQualityError
from quantlab.data.quality.checks import (
    DEFAULT_VOLUME_TOLERANCE,
    CheckResult,
    QualityReport,
    Severity,
    check_column_schema,
    check_extreme_returns,
    check_missing_sessions,
    check_monotonic_index,
    check_no_duplicate_timestamps,
    check_ohlc_consistency,
    check_positive_prices,
    check_split_anomaly,
    check_stale_prices,
    check_timezone,
    run_checks,
)

# ---------------------------------------------------------------------------
# Fabriques de données construites à la main
# ---------------------------------------------------------------------------

#: Les jours fériés PUBLIÉS de la Bourse de New York tombant entre le
#: 2023-07-03 et le 2023-11-24 : fête de l'Indépendance, fête du Travail et
#: Action de grâce. Source (c) : calendrier des jours fériés du NYSE pour 2023.
FERIES_NYSE_2023 = ("2023-07-04", "2023-09-04", "2023-11-23")

#: La fenêtre de contrôle du calendrier, choisie pour contenir les deux
#: fermetures que la spécification exige, le 4 juillet et l'Action de grâce.
FENETRE_DEBUT = "2023-07-03"
FENETRE_FIN = "2023-11-24"


def barres(closes: list[float], volumes: list[float] | None = None) -> pd.DataFrame:
    """Rend un tableau de barres cohérentes autour des clôtures données.

    L'ouverture vaut la clôture, le plus bas vaut 0,9 fois la clôture et le plus
    haut 1,1 fois. Les trois inégalités de :func:`check_ohlc_consistency` sont
    donc satisfaites par construction, ce qui isole le contrôle testé.
    """
    n = len(closes)
    index = pd.date_range("2023-01-03", periods=n, freq="B")
    serie = pd.Series(closes, dtype="float64")
    return pd.DataFrame(
        {
            "open": serie.to_numpy(),
            "high": (serie * 1.1).to_numpy(),
            "low": (serie * 0.9).to_numpy(),
            "close": serie.to_numpy(),
            "volume": np.asarray(volumes if volumes is not None else [1_000_000.0] * n),
        },
        index=index,
    )


def marche_simulee(gen: np.random.Generator, n: int, loi: str) -> pd.DataFrame:
    """Rend une série sans aucune division, pour mesurer une fausse alarme.

    Args:
        gen: le générateur, issu de ``child_generators`` pour l'indépendance.
        n: le nombre de séances.
        loi: ``"normal"`` ou ``"student"``. Dans les deux cas l'écart type des
            rendements logarithmiques vaut 2 % par séance.
    """
    # La loi de Student à trois degrés de liberté a un écart type de racine de 3,
    # donc la division par cette racine ramène les deux lois au même écart type.
    r = gen.normal(0.0, 0.02, n) if loi == "normal" else 0.02 * gen.standard_t(3, n) / np.sqrt(3.0)
    prix = 100.0 * np.exp(np.cumsum(r))
    volume = 1_000_000.0 * np.exp(gen.normal(0.0, 0.4, n))
    return pd.DataFrame(
        {"close": prix, "volume": volume},
        index=pd.date_range("1990-01-01", periods=n, freq="D"),
    )


# ---------------------------------------------------------------------------
# Severity
# ---------------------------------------------------------------------------


def test_severity_rang_croissant_contrairement_a_l_ordre_alphabetique() -> None:
    """Le rang ordonne INFO < WARNING < ERROR, ce que les chaînes ne font pas.

    Source (b) : identité d'ordre. « ERROR » précède « INFO » puis « WARNING »
    dans l'ordre alphabétique, donc comparer les membres par leur chaîne rend
    l'inverse de l'ordre voulu sur la première paire.
    """
    assert Severity.INFO.rank < Severity.WARNING.rank < Severity.ERROR.rank
    assert Severity.ERROR.value < Severity.INFO.value


# ---------------------------------------------------------------------------
# check_no_duplicate_timestamps
# ---------------------------------------------------------------------------


def test_doublons_index_propre() -> None:
    """Un index sans répétition passe. Source (a) : trois dates distinctes."""
    res = check_no_duplicate_timestamps(barres([10.0, 11.0, 12.0]))
    assert res.passed
    assert res.n_violations == 0
    assert res.sample.empty


def test_doublons_index_fautif() -> None:
    """Deux fois le 3 et trois fois le 5 font 1 + 2 = 3 lignes en trop.

    Source (a) : la clé « 2023-01-03 » porte 2 lignes, soit une en trop, et la
    clé « 2023-01-05 » en porte 3, soit deux en trop. Total 3, sur 6 lignes
    fautives réparties sur 2 clés.
    """
    index = pd.DatetimeIndex(
        [
            "2023-01-03",
            "2023-01-03",
            "2023-01-04",
            "2023-01-05",
            "2023-01-05",
            "2023-01-05",
        ]
    )
    df = pd.DataFrame({"close": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]}, index=index)
    res = check_no_duplicate_timestamps(df)
    assert not res.passed
    assert res.n_violations == 3
    assert len(res.sample) == 5  # les 2 + 3 lignes dupliquées
    assert "2 clé(s)" in res.message


def test_doublons_sur_colonnes_cles() -> None:
    """Sur un panel, la clé est le couple date-ticker. Source (a).

    Le couple (2023-01-03, AAA) apparaît deux fois, donc une ligne en trop. Le
    couple (2023-01-03, BBB) n'apparaît qu'une fois et ne compte pas.
    """
    df = pd.DataFrame(
        {
            "date": ["2023-01-03", "2023-01-03", "2023-01-03"],
            "ticker": ["AAA", "AAA", "BBB"],
            "close": [1.0, 1.0, 2.0],
        }
    )
    res = check_no_duplicate_timestamps(df, keys=["date", "ticker"])
    assert not res.passed
    assert res.n_violations == 1
    assert check_no_duplicate_timestamps(df, keys=["ticker"]).n_violations == 1


def test_doublons_colonne_cle_absente() -> None:
    """Une clé absente fait ÉCHOUER le contrôle, elle ne le fait pas passer."""
    res = check_no_duplicate_timestamps(barres([1.0, 2.0]), keys=["ticker"])
    assert not res.passed
    assert res.n_violations == 1
    assert "absente" in res.message


@given(valeurs=st.lists(st.integers(min_value=0, max_value=5), max_size=20))
@settings(max_examples=100, deadline=None)
def test_doublons_identite_longueur_moins_distincts(valeurs: list[int]) -> None:
    """Propriété : lignes en trop = longueur moins nombre de valeurs distinctes.

    Source (b) : identité algébrique. La somme sur les clés dupliquées de
    (effectif - 1) vaut la somme sur toutes les clés de (effectif - 1), les
    clés uniques y contribuant zéro, et cette somme vaut bien
    ``len(valeurs) - len(set(valeurs))``.
    """
    df = pd.DataFrame({"x": range(len(valeurs))}, index=pd.Index(valeurs))
    res = check_no_duplicate_timestamps(df)
    assert res.n_violations == len(valeurs) - len(set(valeurs))
    assert res.passed == (res.n_violations == 0)


# ---------------------------------------------------------------------------
# check_monotonic_index
# ---------------------------------------------------------------------------


def test_index_croissant_passe() -> None:
    """Source (a) : l'index [1, 2, 3] ne porte aucune inversion."""
    res = check_monotonic_index(pd.DataFrame({"x": [0, 0, 0]}, index=[1, 2, 3]))
    assert res.passed
    assert res.n_violations == 0


def test_index_desordonne_une_rupture() -> None:
    """Sur [1, 3, 2] la seule position fautive est la troisième. Source (a).

    La position 1 compare 3 à 1, croissant. La position 2 compare 2 à 3, donc
    une rupture. Total : une violation, à la position 2 en numérotation partant
    de zéro.
    """
    df = pd.DataFrame({"x": [10, 30, 20]}, index=[1, 3, 2])
    res = check_monotonic_index(df)
    assert not res.passed
    assert res.n_violations == 1
    assert res.sample.index.tolist() == [2]


def test_index_doublon_adjacent_selon_le_mode() -> None:
    """Un doublon adjacent est fautif en mode strict et toléré sinon.

    Source (a) : sur [1, 2, 2, 3], la position 2 compare 2 à 2. La comparaison
    « suivant <= précédent » la retient, « suivant < précédent » non.
    """
    df = pd.DataFrame({"x": [0, 0, 0, 0]}, index=[1, 2, 2, 3])
    assert check_monotonic_index(df, strict=True).n_violations == 1
    assert check_monotonic_index(df, strict=False).passed


@pytest.mark.parametrize("n", [0, 1])
def test_index_trop_court_passe(n: int) -> None:
    """Zéro ou une observation : l'ordre est trivialement respecté. Source (b)."""
    df = pd.DataFrame({"x": [1.0] * n}, index=pd.DatetimeIndex(["2023-01-03"][:n]))
    res = check_monotonic_index(df)
    assert res.passed
    assert res.n_violations == 0


@given(n=st.integers(min_value=2, max_value=30))
@settings(max_examples=30, deadline=None)
def test_index_decroissant_donne_n_moins_un(n: int) -> None:
    """Propriété : un index strictement décroissant rend n - 1 ruptures.

    Source (b) : chacune des n - 1 positions à partir de la deuxième compare une
    valeur à une valeur strictement plus grande, donc chacune est fautive.
    """
    df = pd.DataFrame({"x": range(n)}, index=list(range(n, 0, -1)))
    assert check_monotonic_index(df).n_violations == n - 1


# ---------------------------------------------------------------------------
# check_ohlc_consistency
# ---------------------------------------------------------------------------


def test_ohlc_barres_coherentes_passent() -> None:
    """Source (a) : bas = 0,9 c, haut = 1,1 c, ouverture = clôture = c."""
    res = check_ohlc_consistency(barres([10.0, 11.0, 12.0]))
    assert res.passed
    assert res.n_violations == 0


def test_ohlc_barre_plate_passe() -> None:
    """Quatre prix égaux passent : les inégalités sont larges. Source (b).

    Avec o = h = l = c = 10, on a 10 <= min(10 ; 10) et max(10 ; 10) <= 10.
    """
    df = pd.DataFrame(
        {"open": [10.0], "high": [10.0], "low": [10.0], "close": [10.0], "volume": [0.0]},
        index=pd.DatetimeIndex(["2023-01-03"]),
    )
    assert check_ohlc_consistency(df).passed


def test_ohlc_trois_violations_une_par_barre() -> None:
    """Trois barres fautives, chacune pour une raison, comptent pour trois.

    Source (a), barre par barre.
    Barre 1 : o = 10, h = 9, l = 8, c = 8,5. max(10 ; 8,5) = 10 dépasse h = 9.
    Barre 2 : o = 10, h = 12, l = 11, c = 10,5. l = 11 dépasse min(10 ; 10,5) = 10.
    Barre 3 : volume = -1, la troisième inégalité est violée.
    Une quatrième barre est cohérente et ne compte pas.
    """
    df = pd.DataFrame(
        {
            "open": [10.0, 10.0, 10.0, 10.0],
            "high": [9.0, 12.0, 11.0, 11.0],
            "low": [8.0, 11.0, 9.0, 9.0],
            "close": [8.5, 10.5, 10.0, 10.0],
            "volume": [1.0, 1.0, -1.0, 1.0],
        },
        index=pd.date_range("2023-01-03", periods=4, freq="B"),
    )
    res = check_ohlc_consistency(df)
    assert not res.passed
    assert res.n_violations == 3
    assert len(res.sample) == 3


def test_ohlc_colonne_absente_fait_echouer() -> None:
    """Sans la colonne « volume », le contrôle échoue au lieu de passer."""
    df = barres([10.0]).drop(columns=["volume"])
    res = check_ohlc_consistency(df)
    assert not res.passed
    assert "volume" in res.message
    # Le même tableau passe quand on déclare qu'il n'y a pas de volume.
    assert check_ohlc_consistency(df, volume_column=None).passed


def test_ohlc_ne_voit_pas_une_barre_entierement_fausse() -> None:
    """Multiplier les quatre prix par deux ne crée aucune violation. Source (b).

    C'est la limite documentée du contrôle : l'invariance d'échelle des deux
    inégalités rend une division non ajustée invisible ici, et c'est
    :func:`check_split_anomaly` qui s'en charge.
    """
    df = barres([10.0, 11.0])
    double = df.copy()
    double[["open", "high", "low", "close"]] *= 2.0
    assert check_ohlc_consistency(df).passed
    assert check_ohlc_consistency(double).passed


@given(
    ouverture=st.floats(1.0, 100.0),
    haut=st.floats(1.0, 100.0),
    bas=st.floats(1.0, 100.0),
    cloture=st.floats(1.0, 100.0),
)
@settings(max_examples=200, deadline=None)
def test_ohlc_contre_implementation_independante(
    ouverture: float, haut: float, bas: float, cloture: float
) -> None:
    """Le verdict coïncide avec une boucle Python écrite ici. Source (d)."""
    df = pd.DataFrame(
        {
            "open": [ouverture],
            "high": [haut],
            "low": [bas],
            "close": [cloture],
            "volume": [1.0],
        },
        index=pd.DatetimeIndex(["2023-01-03"]),
    )
    attendu = bas <= min(ouverture, cloture) and max(ouverture, cloture) <= haut
    assert check_ohlc_consistency(df).passed is attendu


# ---------------------------------------------------------------------------
# check_missing_sessions
# ---------------------------------------------------------------------------


def seances_publiees() -> pd.DatetimeIndex:
    """Rend les séances attendues, calculées sans le module contrôlé.

    Source (c) et (d) : la grille des jours ouvrés de ``pandas.bdate_range``,
    privée des trois jours fériés PUBLIÉS du NYSE tombant dans la fenêtre.
    """
    grille = pd.bdate_range(FENETRE_DEBUT, FENETRE_FIN)
    return grille.difference(pd.DatetimeIndex(FERIES_NYSE_2023))


def test_seances_manquantes_serie_complete_passe() -> None:
    """Une série bâtie sur les séances publiées ne signale rien.

    Source (c) : 105 jours ouvrés entre le 2023-07-03 et le 2023-11-24, moins
    les trois fériés du NYSE, soit 102 séances.
    """
    attendues = seances_publiees()
    assert len(pd.bdate_range(FENETRE_DEBUT, FENETRE_FIN)) == 105
    assert len(attendues) == 102
    df = pd.DataFrame({"close": np.arange(len(attendues), dtype="float64")}, index=attendues)
    res = check_missing_sessions(df, "XNYS", FENETRE_DEBUT, FENETRE_FIN)
    assert res.passed
    assert res.n_violations == 0


def test_seances_manquantes_grille_de_jours_ouvres_signale_les_feries() -> None:
    """Une grille de jours ouvrés contient les trois fériés, et le contrôle le dit.

    Source (c) : le 4 juillet 2023, le 4 septembre 2023 et le 23 novembre 2023,
    jour de l'Action de grâce, sont fériés au NYSE. Un contrôle qui comparerait
    à ``pandas.bdate_range`` au lieu du calendrier d'échange ne verrait aucun
    de ces trois cas, ce qui est la raison d'être de ce contrôle.
    """
    grille = pd.bdate_range(FENETRE_DEBUT, FENETRE_FIN)
    df = pd.DataFrame({"close": np.arange(len(grille), dtype="float64")}, index=grille)
    res = check_missing_sessions(df, "XNYS", FENETRE_DEBUT, FENETRE_FIN)
    assert not res.passed
    assert res.n_violations == 3
    assert set(res.sample["kind"]) == {"date hors séance"}
    assert sorted(str(d.date()) for d in res.sample["date"]) == list(FERIES_NYSE_2023)


def test_seances_manquantes_trou_reel() -> None:
    """Retirer deux séances en rend exactement deux absentes. Source (a).

    Le 2023-07-05 et le 2023-11-24 sont des séances du NYSE, le premier étant
    le lendemain de la fête de l'Indépendance et le second le lendemain de
    l'Action de grâce. Les enlever laisse 100 lignes sur 102.
    """
    attendues = seances_publiees()
    tronquee = attendues.difference(pd.DatetimeIndex(["2023-07-05", "2023-11-24"]))
    assert len(tronquee) == 100
    df = pd.DataFrame({"close": np.arange(100, dtype="float64")}, index=tronquee)
    res = check_missing_sessions(df, "XNYS", FENETRE_DEBUT, FENETRE_FIN)
    assert not res.passed
    assert res.n_violations == 2
    assert set(res.sample["kind"]) == {"séance absente"}


def test_seances_manquantes_index_intrajournalier() -> None:
    """Un index horodaté à 9 h 30 se compare aux séances, pas à des instants.

    Source (c) et (d) : les mêmes 102 séances publiées, portées à l'ouverture
    de la Bourse de New York. Sans ramener l'horodatage à minuit, aucune des
    102 dates ne coïncide avec une séance du calendrier, et le contrôle
    rendrait 204 violations, 102 séances absentes plus 102 dates hors séance.
    """
    attendues = seances_publiees()
    intraday = attendues + pd.Timedelta(hours=9, minutes=30)
    df = pd.DataFrame({"close": np.arange(len(intraday), dtype="float64")}, index=intraday)
    res = check_missing_sessions(df, "XNYS", FENETRE_DEBUT, FENETRE_FIN)
    assert res.passed
    assert res.n_violations == 0


def test_seances_manquantes_desactivation_des_dates_hors_seance() -> None:
    """``flag_non_sessions=False`` ne compte plus que les séances absentes."""
    grille = pd.bdate_range(FENETRE_DEBUT, FENETRE_FIN)
    df = pd.DataFrame({"close": np.arange(len(grille), dtype="float64")}, index=grille)
    res = check_missing_sessions(df, "XNYS", FENETRE_DEBUT, FENETRE_FIN, flag_non_sessions=False)
    assert res.passed


def test_seances_manquantes_tableau_vide_et_index_non_temporel() -> None:
    """Un tableau vide passe ; un index non temporel lève une erreur de qualité."""
    vide = pd.DataFrame({"close": pd.Series(dtype="float64")}, index=pd.DatetimeIndex([]))
    assert check_missing_sessions(vide).passed
    with pytest.raises(DataQualityError, match="DatetimeIndex"):
        check_missing_sessions(pd.DataFrame({"close": [1.0]}, index=[0]))


# ---------------------------------------------------------------------------
# check_extreme_returns
# ---------------------------------------------------------------------------


def test_rendements_extremes_serie_calme_passe() -> None:
    """Source (a) : 100 -> 101 -> 102 donne 1,0 % puis 0,990 %, sous 50 %."""
    res = check_extreme_returns(barres([100.0, 101.0, 102.0]))
    assert res.passed
    assert res.n_violations == 0


def test_rendements_extremes_chute_de_soixante_pour_cent() -> None:
    """Une chute de 100 à 40 vaut -60 % et dépasse le seuil. Source (a).

    40 / 100 - 1 = -0,6, dont la valeur absolue 0,6 dépasse 0,5. La remontée
    suivante, 100 / 40 - 1 = +1,5, dépasse aussi le seuil. Deux violations.
    """
    res = check_extreme_returns(barres([100.0, 40.0, 100.0]))
    assert not res.passed
    assert res.n_violations == 2
    assert res.sample["return"].iloc[0] == pytest.approx(-0.6)
    assert res.sample["return"].iloc[1] == pytest.approx(1.5)


def test_rendements_extremes_division_deux_pour_une_pas_vue_au_seuil_par_defaut() -> None:
    """La limite documentée : -50 % pile n'est pas strictement au delà de 0,5.

    Source (a) : 50 / 100 - 1 = -0,5 exactement, et la comparaison est stricte.
    Le contrôle passe donc, et il faut descendre le seuil à 0,45 pour l'attraper.
    """
    df = barres([100.0, 50.0])
    assert check_extreme_returns(df, threshold=0.5).passed
    assert check_extreme_returns(df, threshold=0.45).n_violations == 1


def test_rendements_extremes_perte_totale_et_valeurs_manquantes() -> None:
    """Un rendement de -100 % est signalé, une valeur manquante ne l'est pas.

    Source (a) : 0 / 100 - 1 = -1, signalé. Le rendement suivant divise par
    zéro et ne donne pas de nombre fini comparable, donc il ne compte pas. Les
    deux dernières lignes portent une valeur manquante et restent muettes.
    """
    df = barres([100.0, 0.0, np.nan, np.nan])
    res = check_extreme_returns(df)
    assert res.n_violations == 1
    assert res.sample["return"].iloc[0] == pytest.approx(-1.0)


def test_rendements_extremes_serie_vide_ou_dun_point() -> None:
    """Zéro ou une observation ne peut porter aucun rendement. Source (b)."""
    assert check_extreme_returns(barres([])).passed
    assert check_extreme_returns(barres([100.0])).passed


def test_rendements_extremes_deja_des_rendements() -> None:
    """Avec ``already_returns``, la colonne est lue telle quelle. Source (a).

    La série [0,1 ; -0,7 ; 0,2] porte un seul élément au delà de 0,5, le -0,7.
    """
    df = pd.DataFrame({"r": [0.1, -0.7, 0.2]}, index=pd.date_range("2023-01-03", periods=3, freq="B"))
    res = check_extreme_returns(df, column="r", already_returns=True)
    assert res.n_violations == 1


def test_rendements_extremes_seuil_invalide() -> None:
    """Un seuil nul ou négatif n'a pas de sens et lève ``ValueError``."""
    with pytest.raises(ValueError, match="threshold"):
        check_extreme_returns(barres([1.0, 2.0]), threshold=0.0)


def test_rendements_extremes_colonne_absente_fait_echouer() -> None:
    """Une colonne absente fait échouer le contrôle, elle ne le fait pas passer."""
    res = check_extreme_returns(barres([1.0, 2.0]), column="adj_close")
    assert not res.passed
    assert "adj_close" in res.message


@given(facteur=st.floats(min_value=0.01, max_value=100.0))
@settings(max_examples=50, deadline=None)
def test_rendements_extremes_invariance_d_echelle(facteur: float) -> None:
    """Propriété : multiplier tous les prix par une constante ne change rien.

    Source (b) : le rendement simple est invariant par changement d'unité,
    (k P_t) / (k P_{t-1}) - 1 = P_t / P_{t-1} - 1. Un contrôle sur les
    rendements doit donc rendre le même verdict en dollars et en cents.
    """
    df = barres([100.0, 40.0, 45.0, 44.0])
    echelle = df.copy()
    echelle[["open", "high", "low", "close"]] *= facteur
    assert check_extreme_returns(echelle).n_violations == check_extreme_returns(df).n_violations


def test_rendements_extremes_fausse_alarme_bornee() -> None:
    """Le taux de fausse alarme reste sous 0,01 % sur des séries sans anomalie.

    Source (b), borne modélisée. Sous des rendements logarithmiques normaux
    d'écart type 2 % par séance, franchir 50 % en une séance demande plus de
    vingt écarts types, donc zéro alarme attendue. Sous une loi de Student à
    trois degrés de liberté de même écart type, la docstring du contrôle publie
    un taux modélisé de 0,00278 %, mesuré sur dix fois plus de tirages. La
    borne testée ici, 0,01 %, est plus de trois fois supérieure, ce qui rend
    l'assertion insensible au bruit d'échantillonnage.
    """
    n_par_lot, n_lots = 2_520, 100
    total = n_par_lot * n_lots
    for loi, plafond in (("normal", 0.0), ("student", 1e-4)):
        signalees = sum(
            check_extreme_returns(marche_simulee(g, n_par_lot, loi)).n_violations
            for g in child_generators(20260901, n_lots)
        )
        assert signalees / total <= plafond, f"{loi} : {signalees} sur {total}"


# ---------------------------------------------------------------------------
# check_split_anomaly
# ---------------------------------------------------------------------------


def test_division_non_ajustee_volume_plat_est_signalee() -> None:
    """Prix divisé par deux, volume inchangé : la ligne est signalée. Source (a).

    Le rapport de prix vaut 100 / 50 = 2, exactement le candidat 2, donc l'écart
    de prix est nul et passe la tolérance de 2 %. La médiane glissante du volume
    vaut 1 000 000, le volume attendu vaut 2 000 000, et le volume observé de
    1 000 000 donne |1 / 2 - 1| = 0,50, au delà de la tolérance de 0,30.
    """
    df = barres([100.0] * 5 + [50.0, 50.0])
    res = check_split_anomaly(df)
    assert not res.passed
    assert res.n_violations == 1
    assert res.sample["price_ratio"].iloc[0] == pytest.approx(2.0)
    assert res.sample["matched_ratio"].iloc[0] == pytest.approx(2.0)
    assert res.sample["volume_factor"].iloc[0] == pytest.approx(1.0)


def test_division_coherente_avec_le_volume_nest_pas_signalee() -> None:
    """Le même saut de prix avec un volume doublé est jugé cohérent. Source (a).

    Volume observé 2 100 000 contre 2 000 000 attendus, soit |2,1 / 2 - 1| =
    0,05, sous la tolérance de 0,30. La bande corroborante va de 1 400 000 à
    2 600 000.
    """
    volumes = [1_000_000.0] * 5 + [2_100_000.0, 2_000_000.0]
    assert check_split_anomaly(barres([100.0] * 5 + [50.0, 50.0], volumes)).passed


def test_regroupement_un_pour_dix_volume_plat_est_signale() -> None:
    """Un regroupement multiplie le prix par dix et divise le volume par dix.

    Source (a) : le rapport de prix vaut 100 / 1 000 = 0,1, exactement le
    candidat 0,1. Le volume attendu vaut 0,1 x 1 000 000 = 100 000 et le volume
    observé reste à 1 000 000, soit |1 000 000 / 100 000 - 1| = 9, très au delà
    de 0,30.
    """
    res = check_split_anomaly(barres([100.0] * 5 + [1_000.0, 1_000.0]))
    assert res.n_violations == 1
    assert res.sample["matched_ratio"].iloc[0] == pytest.approx(0.1)


def test_serie_sans_saut_ne_declenche_rien() -> None:
    """Une série qui monte de 1 % par séance ne signale rien. Source (a).

    Le rapport de prix vaut 1 / 1,01 = 0,990, dont l'écart au candidat le plus
    proche, 1,5, vaut 34 %, très au delà de la tolérance de 2 %.
    """
    prix = [100.0 * 1.01**k for k in range(30)]
    assert check_split_anomaly(barres(prix)).passed


def test_division_mediane_des_volumes_precedents() -> None:
    """La référence est la MÉDIANE des ``volume_window`` volumes PRÉCÉDENTS.

    Source (a), calcul à la main sur des volumes volontairement asymétriques,
    en millions d'actions : 1, 2, 4, 12, puis la séance de division. Avec une
    fenêtre de trois, la référence vaut la médiane de 2, 4 et 12, soit 4. Le
    volume attendu vaut donc 4 x 2 = 8 et le rapport de volume observé vaut
    12 / 4 = 3.

    Le tableau est bâti pour que quatre défauts plausibles se voient. La
    moyenne des trois volumes vaut 6 et non 4, la médiane non décalée vaut 12,
    la médiane décalée de deux séances vaut 2, et la médiane sur toute
    l'histoire vaut 3. Aucune ne rend 4, donc aucune ne rend un rapport de
    volume de 3.
    """
    millions = [1e6, 2e6, 4e6, 12e6]
    prix = [100.0] * 4 + [50.0]

    # Volume observé de 12 millions contre 8 attendus : |12 / 8 - 1| = 0,50,
    # au delà de la tolérance de 0,30, donc la ligne est signalée.
    res = check_split_anomaly(barres(prix, [*millions, 12e6]), volume_window=3)
    assert res.n_violations == 1
    assert res.sample["volume_factor"].iloc[0] == pytest.approx(3.0)
    assert res.sample["matched_ratio"].iloc[0] == pytest.approx(2.0)

    # Volume observé de 8 millions, exactement l'attendu : la division est
    # jugée cohérente et rien n'est signalé.
    assert check_split_anomaly(barres(prix, [*millions, 8e6]), volume_window=3).passed


def test_division_colonne_de_volume_absente_fait_echouer() -> None:
    """Sans volume, le recoupement est impossible et le contrôle échoue."""
    df = barres([100.0, 50.0]).drop(columns=["volume"])
    res = check_split_anomaly(df)
    assert not res.passed
    assert "volume" in res.message


def test_division_arguments_invalides() -> None:
    """Les tolérances négatives, la fenêtre nulle et la liste vide sont refusées."""
    df = barres([100.0, 50.0])
    with pytest.raises(ValueError, match="tolérances"):
        check_split_anomaly(df, ratio_tolerance=-0.1)
    with pytest.raises(ValueError, match="volume_window"):
        check_split_anomaly(df, volume_window=0)
    with pytest.raises(ValueError, match="ratios"):
        check_split_anomaly(df, ratios=[])


def test_division_tolerance_de_volume_par_defaut_sous_un_tiers() -> None:
    """La valeur par défaut garantit qu'un volume plat est toujours signalé.

    Source (b) : la bande corroborante est [r(1 - d), r(1 + d)]. Pour que le
    facteur 1 en soit exclu quel que soit le rapport candidat, il faut
    r(1 - d) > 1 au plus petit rapport supérieur à 1, soit 1,5, donc d < 1/3.
    """
    assert DEFAULT_VOLUME_TOLERANCE < 1.0 / 3.0
    assert 1.5 * (1.0 - DEFAULT_VOLUME_TOLERANCE) > 1.0


def test_split_anomaly_fausse_alarme_bornee() -> None:
    """Le taux de fausse alarme reste sous 0,01 % sur des séries sans division.

    Source (b), borne modélisée sous les hypothèses de la docstring du contrôle,
    rendements et volumes logarithmiques normaux, puis rendements de Student à
    trois degrés de liberté. Le taux publié pour la seconde loi vaut 0,00119 %,
    mesuré sur dix fois plus de tirages, et la borne testée est huit fois
    au dessus.
    """
    n_par_lot, n_lots = 2_520, 100
    total = n_par_lot * n_lots
    for loi, plafond in (("normal", 0.0), ("student", 1e-4)):
        signalees = sum(
            check_split_anomaly(marche_simulee(g, n_par_lot, loi)).n_violations
            for g in child_generators(20260901, n_lots)
        )
        assert signalees / total <= plafond, f"{loi} : {signalees} sur {total}"


# ---------------------------------------------------------------------------
# check_stale_prices
# ---------------------------------------------------------------------------


def test_prix_figes_plage_de_trois() -> None:
    """Sur [10 ; 11 ; 11 ; 11 ; 12] avec max_repeats = 2, trois lignes fautives.

    Source (a) : la plage des trois onze a une longueur de 3, strictement
    supérieure à 2, et elle porte trois lignes. Les deux autres plages ont une
    longueur de 1.
    """
    res = check_stale_prices(barres([10.0, 11.0, 11.0, 11.0, 12.0]), max_repeats=2)
    assert not res.passed
    assert res.n_violations == 3
    assert "1 plage(s)" in res.message


def test_prix_figes_longueur_exactement_toleree_passe() -> None:
    """La même plage de trois passe quand max_repeats vaut 3. Source (a).

    La comparaison est stricte : 3 > 3 est faux.
    """
    assert check_stale_prices(barres([10.0, 11.0, 11.0, 11.0, 12.0]), max_repeats=3).passed


def test_prix_figes_serie_variable_passe() -> None:
    """Une série qui bouge à chaque séance ne porte aucune plage. Source (a)."""
    assert check_stale_prices(barres([10.0, 11.0, 12.0, 13.0]), max_repeats=1).passed


def test_prix_figes_valeurs_manquantes_ne_comptent_pas() -> None:
    """Deux valeurs manquantes consécutives ne forment pas une plage stagnante.

    Source (a) : la série [10 ; nan ; nan ; nan ; 12] ne porte aucune valeur
    RENSEIGNÉE répétée, et le contrôle passe même avec max_repeats = 1.
    """
    assert check_stale_prices(barres([10.0, np.nan, np.nan, np.nan, 12.0]), max_repeats=1).passed


def test_prix_figes_colonne_a_valeurs_absentes_nullable() -> None:
    """Une colonne ``Float64`` portant des ``pd.NA`` se contrôle sans lever.

    Source (a) : sur la série [10 ; NA ; NA ; 10 ; 10] avec max_repeats = 1,
    les deux valeurs absentes coupent les plages. Seules les deux dernières
    valeurs identiques en forment une, de longueur 2, strictement supérieure à
    1. Le contrôle rend donc deux violations.

    Le type ``Float64`` est celui d'un chargement Parquet à colonnes
    nullables. Sur ce type, comparer deux ``pd.NA`` rend ``pd.NA`` et non
    ``True``, si bien qu'un découpage de plages fondé sur la seule comparaison
    lève ``ValueError`` au lieu de rendre un verdict.
    """
    index = pd.date_range("2023-01-03", periods=5, freq="B")
    serie = pd.Series([10.0, pd.NA, pd.NA, 10.0, 10.0], dtype="Float64", index=index)
    df = pd.DataFrame({"close": serie})
    assert str(df["close"].dtype) == "Float64"
    assert int(df["close"].isna().sum()) == 2
    res = check_stale_prices(df, max_repeats=1)
    assert not res.passed
    assert res.n_violations == 2
    # Le même contenu en float64 rend le même verdict : le type de colonne ne
    # doit pas changer le nombre de plages.
    assert check_stale_prices(df.astype("float64"), max_repeats=1).n_violations == 2


def test_prix_figes_argument_invalide() -> None:
    """``max_repeats`` inférieur à 1 est refusé."""
    with pytest.raises(ValueError, match="max_repeats"):
        check_stale_prices(barres([1.0, 1.0]), max_repeats=0)


@given(n=st.integers(min_value=2, max_value=25), tolerance=st.integers(min_value=1, max_value=25))
@settings(max_examples=100, deadline=None)
def test_prix_figes_serie_constante(n: int, tolerance: int) -> None:
    """Propriété : une série constante de longueur n rend n violations ou zéro.

    Source (b) : la série constante forme une plage unique de longueur n. Elle
    est fautive si et seulement si n dépasse strictement la tolérance, et elle
    porte alors ses n lignes.
    """
    res = check_stale_prices(barres([7.0] * n), max_repeats=tolerance)
    assert res.n_violations == (n if n > tolerance else 0)


# ---------------------------------------------------------------------------
# check_timezone
# ---------------------------------------------------------------------------


def test_fuseau_naif_attendu_naif() -> None:
    """Un index naïf est conforme quand ``expected`` vaut ``None``."""
    res = check_timezone(barres([1.0, 2.0]), None)
    assert res.passed
    assert res.n_violations == 0


def test_fuseau_naif_alors_qu_un_fuseau_etait_attendu() -> None:
    """Un index naïf viole une attente de fuseau, une fois. Source (a)."""
    res = check_timezone(barres([1.0, 2.0]), "America/New_York")
    assert not res.passed
    assert res.n_violations == 1
    assert "naïf" in res.message


def test_fuseau_averti_conforme_et_non_conforme() -> None:
    """New York attendu : conforme en heure de New York, fautif en UTC."""
    df = barres([1.0, 2.0])
    ny = df.tz_localize("America/New_York")
    utc = df.tz_localize("UTC")
    assert check_timezone(ny, "America/New_York").passed
    assert check_timezone(utc, "America/New_York").n_violations == 1
    assert check_timezone(utc, "UTC").passed


def test_fuseau_melange_naif_et_averti() -> None:
    """Un index d'objets mêlant les deux natures compte le camp minoritaire.

    Source (a) : trois horodatages naïfs et un averti donnent min(3 ; 1) = 1
    horodatage à corriger.
    """
    index = pd.Index(
        [
            pd.Timestamp("2023-01-03"),
            pd.Timestamp("2023-01-04"),
            pd.Timestamp("2023-01-05"),
            pd.Timestamp("2023-01-06", tz="UTC"),
        ]
    )
    df = pd.DataFrame({"close": [1.0, 2.0, 3.0, 4.0]}, index=index)
    res = check_timezone(df, None)
    assert not res.passed
    assert res.n_violations == 1
    assert "mélange" in res.message


def test_fuseau_index_non_temporel() -> None:
    """Un index d'entiers ne permet aucune vérification, et le contrôle le dit."""
    res = check_timezone(pd.DataFrame({"close": [1.0]}, index=[0]), "UTC")
    assert not res.passed
    assert "horodatages" in res.message


# ---------------------------------------------------------------------------
# check_positive_prices
# ---------------------------------------------------------------------------


def test_prix_positifs_serie_propre() -> None:
    """Source (a) : les quatre colonnes de 10 et 11 sont strictement positives."""
    assert check_positive_prices(barres([10.0, 11.0])).passed


def test_prix_positifs_un_zero_compte_une_ligne() -> None:
    """Une ligne dont deux colonnes sont fautives compte pour une. Source (a).

    La deuxième barre porte low = 0 et close = -1. Elle viole deux fois la
    règle et rend une seule violation, l'unité étant la ligne.
    """
    df = barres([10.0, 11.0, 12.0])
    df.loc[df.index[1], "low"] = 0.0
    df.loc[df.index[1], "close"] = -1.0
    res = check_positive_prices(df)
    assert not res.passed
    assert res.n_violations == 1
    assert len(res.sample) == 1


def test_prix_positifs_zero_seul_est_refuse_par_defaut() -> None:
    """Un zéro seul, sans aucune valeur négative, est fautif par défaut.

    Source (a) : la règle par défaut exige un prix STRICTEMENT positif, et 0 la
    viole. Le test existe parce qu'un contrôle qui ne refuserait que le négatif
    laisserait passer le zéro de remplissage, qui est le cas le plus fréquent
    des deux.
    """
    df = barres([10.0, 11.0])
    df.loc[df.index[0], "low"] = 0.0
    res = check_positive_prices(df)
    assert not res.passed
    assert res.n_violations == 1
    assert res.sample["low"].iloc[0] == 0.0


def test_prix_positifs_zero_tolere_sur_demande() -> None:
    """``allow_zero`` accepte le zéro et continue de refuser le négatif."""
    df = barres([10.0, 11.0])
    df.loc[df.index[0], "low"] = 0.0
    assert check_positive_prices(df, allow_zero=True).passed
    df.loc[df.index[1], "low"] = -0.01
    assert check_positive_prices(df, allow_zero=True).n_violations == 1


def test_prix_positifs_signale_a_tort_un_prix_negatif_legitime() -> None:
    """Le contrôle signale le règlement négatif du WTI, et c'est sa limite.

    Source (c) : le contrat à terme de pétrole WTI d'échéance mai 2020 s'est
    réglé à -37,63 dollars le 20 avril 2020, valeur rapportée par le CME Group.
    Le contrôle rend une violation sur cette ligne, ce qui est correct au sens
    de sa règle et faux au sens économique. Ce test fige la limite documentée.
    """
    df = barres([20.0, -37.63, 10.0])
    res = check_positive_prices(df, columns=["close"])
    assert res.n_violations == 1


def test_prix_positifs_valeur_manquante_nest_pas_signalee() -> None:
    """Une valeur absente n'est PAS signalée, et c'est une limite documentée.

    Source (b) : la comparaison d'un ``NaN`` à zéro rend ``False`` en pandas
    comme en NumPy, pour les deux sens de l'inégalité. Un prix manquant passe
    donc les deux modes du contrôle. Le test fige ce comportement pour qu'un
    lecteur ne prenne pas ce contrôle pour un contrôle de complétude.
    """
    df = barres([10.0, 11.0])
    df.loc[df.index[1], "low"] = np.nan
    assert np.isnan(df.loc[df.index[1], "low"])
    assert check_positive_prices(df).passed
    assert check_positive_prices(df, allow_zero=True).passed


def test_prix_positifs_colonnes_absentes_et_texte() -> None:
    """Sans colonne de prix le contrôle échoue ; une colonne de texte lève."""
    res = check_positive_prices(pd.DataFrame({"autre": [1.0]}))
    assert not res.passed
    with pytest.raises(DataQualityError, match="texte"):
        check_positive_prices(pd.DataFrame({"close": ["10"]}), columns=["close"])


# ---------------------------------------------------------------------------
# check_column_schema
# ---------------------------------------------------------------------------


def test_schema_conforme() -> None:
    """Source (a) : les cinq colonnes de la fabrique sont toutes en float64."""
    schema = dict.fromkeys(("open", "high", "low", "close", "volume"), "float64")
    res = check_column_schema(barres([1.0, 2.0]), schema)
    assert res.passed
    assert res.n_violations == 0


def test_schema_colonne_absente_et_type_faux() -> None:
    """Une colonne absente et un type inattendu font deux violations. Source (a).

    Le type observé est rapporté tel que pandas le nomme. Le test le relit sur
    le tableau lui même plutôt que de le figer, car pandas 3 nomme « str » ce
    que pandas 2 nommait « object ». Cette valeur exacte ne fait pas partie du
    contrat du contrôle. Source (b) pour cette seconde assertion.
    """
    df = pd.DataFrame({"close": ["10", "11"]})
    res = check_column_schema(df, {"close": "float64", "volume": "float64"})
    assert not res.passed
    assert res.n_violations == 2
    lignes = res.sample.set_index("column")
    assert lignes.loc["close", "observed"] == str(df["close"].dtype)
    assert lignes.loc["close", "observed"] != "float64"
    assert lignes.loc["volume", "observed"] == "absente"


def test_schema_presence_seule() -> None:
    """Un type ``None`` n'exige que la présence de la colonne. Source (a)."""
    df = pd.DataFrame({"close": ["10"]})
    assert check_column_schema(df, {"close": None}).passed


def test_schema_colonnes_surnumeraires() -> None:
    """``allow_extra=False`` compte les colonnes non déclarées. Source (a).

    La fabrique rend cinq colonnes ; en déclarer une seule en laisse quatre
    surnuméraires.
    """
    df = barres([1.0, 2.0])
    assert check_column_schema(df, {"close": "float64"}).passed
    res = check_column_schema(df, {"close": "float64"}, allow_extra=False)
    assert res.n_violations == 4


def test_schema_compare_le_nom_exact_du_type() -> None:
    """La limite documentée : float32 ne satisfait pas float64. Source (a)."""
    df = pd.DataFrame({"close": np.asarray([1.0], dtype="float32")})
    assert not check_column_schema(df, {"close": "float64"}).passed
    assert check_column_schema(df, {"close": "float32"}).passed


# ---------------------------------------------------------------------------
# run_checks et QualityReport
# ---------------------------------------------------------------------------


def test_run_checks_agrege_dans_l_ordre() -> None:
    """Le rapport porte un résultat par contrôle, dans l'ordre d'exécution."""
    df = barres([10.0, 11.0, 12.0])
    rapport = run_checks(df, [check_monotonic_index, check_ohlc_consistency, check_positive_prices])
    assert isinstance(rapport, QualityReport)
    assert len(rapport) == 3
    assert [r.name for r in rapport] == [
        "monotonic_index",
        "ohlc_consistency",
        "positive_prices",
    ]
    assert rapport.passed
    assert list(rapport.to_frame().columns) == [
        "name",
        "passed",
        "severity",
        "n_violations",
        "message",
    ]


def test_run_checks_leve_au_bon_niveau_de_gravite() -> None:
    """Un avertissement ne bloque pas au seuil ERROR, et bloque au seuil WARNING.

    Source (a) : le tableau porte une chute de 100 à 40, soit -60 %, signalée
    par un contrôle de gravité WARNING. Les deux autres contrôles passent.
    """
    df = barres([100.0, 40.0, 45.0])
    rapport = run_checks(
        df,
        [
            check_monotonic_index,
            check_ohlc_consistency,
            partial(check_extreme_returns, threshold=0.5),
        ],
    )
    assert not rapport.passed
    assert len(rapport.failures()) == 1
    assert rapport.failures(Severity.ERROR) == ()
    rapport.raise_if_failed(Severity.ERROR)  # ne lève pas
    with pytest.raises(DataQualityError, match="extreme_returns"):
        rapport.raise_if_failed(Severity.WARNING)


def test_run_checks_leve_sur_une_erreur_et_liste_tous_les_echecs() -> None:
    """Le message porte tous les échecs du seuil, pas seulement le premier."""
    index = pd.DatetimeIndex(["2023-01-04", "2023-01-03", "2023-01-03"])
    df = pd.DataFrame({"close": [1.0, 2.0, 3.0]}, index=index)
    rapport = run_checks(df, [check_monotonic_index, check_no_duplicate_timestamps])
    with pytest.raises(DataQualityError) as excinfo:
        rapport.raise_if_failed()
    message = str(excinfo.value)
    assert "monotonic_index" in message
    assert "no_duplicate_timestamps" in message
    assert "2 contrôle(s)" in message


def test_run_checks_ne_masque_pas_une_exception_de_controle() -> None:
    """Une exception levée par un contrôle remonte, elle ne devient pas un rouge.

    Source (b) : un contrôle qui lève est bogué. Le transformer en résultat
    échoué produirait un rapport d'apparence complète, ce que ce module existe
    précisément pour éviter.
    """

    def controle_bogue(df: pd.DataFrame) -> CheckResult:
        raise RuntimeError("bogue du contrôle")

    with pytest.raises(RuntimeError, match="bogue du contrôle"):
        run_checks(barres([1.0]), [controle_bogue])


def test_run_checks_sans_controle() -> None:
    """Une suite vide passe et ne lève rien. Source (b) : « tous » sur le vide."""
    rapport = run_checks(barres([1.0]), [])
    assert rapport.passed
    assert len(rapport) == 0
    rapport.raise_if_failed()


def test_check_result_est_gele_et_lisible() -> None:
    """Le résultat est immuable et son texte porte gravité, état et compte."""
    res = check_monotonic_index(barres([1.0, 2.0]))
    with pytest.raises(Exception, match=r"frozen|immutable|cannot assign"):
        res.passed = False  # type: ignore[misc]
    assert "monotonic_index" in str(res)
    assert "OK" in str(res)

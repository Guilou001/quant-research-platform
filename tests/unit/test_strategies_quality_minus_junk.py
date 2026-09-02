"""Les contrôles du module de la qualité moins la camelote.

Chaque valeur attendue vient d'un calcul à la main, d'une propriété
mathématique, ou d'une identité algébrique. Aucune ne vient de la sortie du
code, ce qui verrouillerait le défaut au lieu de l'attraper.
"""

from __future__ import annotations

import io
import math
import zipfile

import numpy as np
import pandas as pd
import pytest

from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError, LookAheadError
from quantlab.data.point_in_time import PITFrame, assert_no_lookahead
from quantlab.strategies.quality_minus_junk import (
    COMPONENT_VARIABLES,
    accounting_items,
    altman_z_score,
    annual_records,
    apply_size_screen,
    component_scores,
    dera_quarter_url,
    dera_quarters,
    drop_return_outliers,
    frazzini_pedersen_beta,
    growth_variables,
    idiosyncratic_volatility,
    lagged_records,
    latest_records,
    ohlson_o_score,
    parse_dera_archive,
    payout_variables,
    profitability_variables,
    quality_minus_junk,
    quality_score,
    quarterly_roe_volatility,
    rank_zscore,
    safety_variables,
    screen_in_force,
    size_screens,
    three_component_proxy,
    usable_prices,
    variable_panels,
)

# --------------------------------------------------------------------------- #
# Les fabriques d'échantillons
# --------------------------------------------------------------------------- #


SUB_HEADER = "adsh\tcik\tname\tsic\tform\tperiod\tfy\tfp\tfiled\taccepted"
NUM_HEADER = "adsh\ttag\tversion\tddate\tqtrs\tuom\tsegments\tcoreg\tvalue\tfootnote"


def _archive(sub_rows: list[str], num_rows: list[str]) -> bytes:
    """Fabrique une archive DERA minimale, au format tabulé de la SEC."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("sub.txt", "\n".join([SUB_HEADER, *sub_rows]) + "\n")
        archive.writestr("num.txt", "\n".join([NUM_HEADER, *num_rows]) + "\n")
    return buffer.getvalue()


def _sub(adsh: str, cik: int, form: str = "10-K", filed: int = 20150331) -> str:
    """Rend une ligne de dépôt."""
    return f"{adsh}\t{cik}\tSOCIETE {cik}\t3711\t{form}\t20141231\t2014\tFY\t{filed}\t2015-03-31 16:00:00.0"


def _num(
    adsh: str,
    tag: str,
    ddate: int,
    qtrs: int,
    value: float,
    *,
    version: str = "us-gaap/2014",
    segments: str = "",
    coreg: str = "",
    uom: str = "USD",
) -> str:
    """Rend une ligne de valeur numérique."""
    return f"{adsh}\t{tag}\t{version}\t{ddate}\t{qtrs}\t{uom}\t{segments}\t{coreg}\t{value}\t"


def _full_year(adsh: str, ddate: int, *, assets: float, income: float, revenue: float) -> list[str]:
    """Rend les lignes minimales d'un exercice complet."""
    return [
        _num(adsh, "Assets", ddate, 0, assets),
        _num(adsh, "StockholdersEquity", ddate, 0, assets / 2.0),
        _num(adsh, "Revenues", ddate, 4, revenue),
        _num(adsh, "NetIncomeLoss", ddate, 4, income),
    ]


# --------------------------------------------------------------------------- #
# Les adresses et les trimestres
# --------------------------------------------------------------------------- #


def test_adresse_du_trimestre() -> None:
    """L'adresse suit le gabarit publié par la SEC, année puis trimestre."""
    assert dera_quarter_url("https://sec/x/", 2015, 2) == "https://sec/x/2015q2.zip"


def test_adresse_refuse_un_trimestre_hors_bornes() -> None:
    """Un cinquième trimestre n'existe pas et se refuse à la construction."""
    with pytest.raises(ConfigError, match="trimestre invalide"):
        dera_quarter_url("https://sec/x", 2015, 5)


def test_suite_des_trimestres_franchit_l_annee() -> None:
    """La suite passe de décembre à janvier sans sauter ni répéter."""
    assert dera_quarters(2015, 3, 2016, 1) == ((2015, 3), (2015, 4), (2016, 1))


def test_suite_refuse_un_ordre_inverse() -> None:
    """Une borne haute antérieure à la borne basse est une erreur de configuration."""
    with pytest.raises(ConfigError, match="suit"):
        dera_quarters(2016, 1, 2015, 3)


# --------------------------------------------------------------------------- #
# La lecture des archives
# --------------------------------------------------------------------------- #


def test_le_vide_n_est_pas_le_manquant() -> None:
    """Une colonne de segment vide garde la ligne, et c'est le piège du module.

    Les fichiers de la SEC écrivent une chaîne vide, non une valeur manquante.
    Un filtre écrit avec ``isna`` ne garderait aucune ligne, sans lever. Ce test
    fige le comportement correct sur une archive construite à la main.
    """
    payload = _archive([_sub("A", 1)], _full_year("A", 20141231, assets=100.0, income=10.0, revenue=50.0))
    submissions, numbers = parse_dera_archive(payload)
    assert len(submissions) == 1
    assert len(numbers) == 4


def test_les_lignes_sectorielles_sont_retirees() -> None:
    """Une valeur portant un segment décrit une division, pas le groupe."""
    rows = [
        _num("A", "Assets", 20141231, 0, 100.0),
        _num("A", "Assets", 20141231, 0, 40.0, segments="Region=US;"),
        _num("A", "Assets", 20141231, 0, 30.0, coreg="FILIALE"),
        _num("A", "Assets", 20141231, 0, 20.0, version="maison/2014"),
        _num("A", "AutreBalise", 20141231, 0, 7.0),
    ]
    _, numbers = parse_dera_archive(_archive([_sub("A", 1)], rows))
    assert len(numbers) == 1
    assert float(numbers["value"].iloc[0]) == 100.0


def test_archive_incomplete_leve() -> None:
    """Une archive sans ``num.txt`` ne se lit pas, et le dit."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("sub.txt", SUB_HEADER + "\n")
    with pytest.raises(DataQualityError, match="incomplète"):
        parse_dera_archive(buffer.getvalue())


# --------------------------------------------------------------------------- #
# Le recollement des postes
# --------------------------------------------------------------------------- #


def test_recollement_prend_la_premiere_balise_renseignee() -> None:
    """Le chiffre d'affaires se lit dans la première balise disponible.

    Vérité connue : la première ligne porte ``Revenues`` à 90, la seconde ne
    porte que la balise de rechange à 70. Le recollement doit donc rendre 90
    puis 70.
    """
    pivoted = pd.DataFrame(
        {
            "Revenues": [90.0, np.nan],
            "SalesRevenueNet": [np.nan, 70.0],
            "Assets": [200.0, 200.0],
        }
    )
    items = accounting_items(pivoted)
    assert items["REVT"].tolist() == [90.0, 70.0]


def test_postes_deduits_a_la_main() -> None:
    """Les fonds propres, le profit brut, le fonds de roulement et la dette sont vérifiés.

    Vérité connue, calculée à la main : capitaux propres 500 moins privilégiées
    20 font 480 de fonds propres. Ventes 300 moins coût 180 font 120 de profit
    brut. Actif courant 200 moins passif courant 90 moins encaisse 40 plus dette
    courante 10 plus impôts 5 font 85 de fonds de roulement. La dette totale
    vaut 150 plus 10 plus 30 plus 20, soit 210.
    """
    pivoted = pd.DataFrame(
        {
            "StockholdersEquity": [500.0],
            "PreferredStockValue": [20.0],
            "Revenues": [300.0],
            "CostOfRevenue": [180.0],
            "AssetsCurrent": [200.0],
            "LiabilitiesCurrent": [90.0],
            "CashAndCashEquivalentsAtCarryingValue": [40.0],
            "LongTermDebtCurrent": [10.0],
            "AccruedIncomeTaxesCurrent": [5.0],
            "LongTermDebtNoncurrent": [150.0],
            "MinorityInterest": [30.0],
        }
    )
    items = accounting_items(pivoted)
    assert float(items["BE"].iloc[0]) == pytest.approx(480.0)
    assert float(items["GP"].iloc[0]) == pytest.approx(120.0)
    assert float(items["WC"].iloc[0]) == pytest.approx(85.0)
    assert float(items["TOTD"].iloc[0]) == pytest.approx(210.0)


def test_les_fonds_propres_passent_par_la_solution_de_rechange() -> None:
    """Sans capitaux propres déclarés, on retire les minoritaires du total.

    Vérité connue : 700 incluant 120 de minoritaires font 580, moins 30 de
    privilégiées, soit 550 de fonds propres comptables.
    """
    pivoted = pd.DataFrame(
        {
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest": [700.0],
            "MinorityInterest": [120.0],
            "PreferredStockValue": [30.0],
        }
    )
    assert float(accounting_items(pivoted)["BE"].iloc[0]) == pytest.approx(550.0)


# --------------------------------------------------------------------------- #
# Les exercices annuels et leur disponibilité
# --------------------------------------------------------------------------- #


def test_un_exercice_porte_sa_date_de_depot() -> None:
    """L'exercice clos fin 2014 devient connaissable le jour du dépôt, pas avant."""
    payload = _archive(
        [_sub("A", 1, filed=20150331)],
        _full_year("A", 20141231, assets=100.0, income=10.0, revenue=50.0),
    )
    submissions, numbers = parse_dera_archive(payload)
    records = annual_records(submissions, numbers)
    assert len(records) == 1
    assert records["period_end"].iloc[0] == pd.Timestamp("2014-12-31")
    assert records["available_from"].iloc[0] == pd.Timestamp("2015-03-31")


def test_un_depot_anterieur_a_sa_periode_est_refuse() -> None:
    """Un dépôt daté avant la fin de la période qu'il décrit est impossible."""
    payload = _archive(
        [_sub("A", 1, filed=20141101)],
        _full_year("A", 20141231, assets=100.0, income=10.0, revenue=50.0),
    )
    submissions, numbers = parse_dera_archive(payload)
    assert annual_records(submissions, numbers).empty


def test_sans_bilan_aucun_exercice() -> None:
    """Un compte de résultat sans bilan à la même date ne fait pas un exercice."""
    rows = [_num("A", "Revenues", 20141231, 4, 50.0), _num("A", "NetIncomeLoss", 20141231, 4, 10.0)]
    submissions, numbers = parse_dera_archive(_archive([_sub("A", 1)], rows))
    with pytest.raises(InsufficientDataError):
        annual_records(submissions, numbers)


def test_anti_fuite_canonique_du_registre() -> None:
    """Le rapport déposé le 31 mars 2015 reste invisible le 31 décembre 2014.

    C'est le contrôle canonique de la règle 1 du ``CLAUDE.md``, appliqué à la
    chaîne réelle du module : lecture de l'archive, assemblage des exercices,
    puis registre point-in-time.
    """
    payload = _archive(
        [_sub("A", 1, filed=20150331)],
        _full_year("A", 20141231, assets=100.0, income=10.0, revenue=50.0),
    )
    records = annual_records(*parse_dera_archive(payload))
    registre = PITFrame(records)
    assert len(registre.as_of("2014-12-31")) == 0
    assert len(registre.as_of("2015-03-30")) == 0
    assert len(registre.as_of("2015-03-31")) == 1


def test_le_panneau_ne_porte_aucune_fuite() -> None:
    """Toute ligne rendue à une date de décision était publique à cette date."""
    payload = _archive(
        [_sub("A", 1, filed=20150331), _sub("B", 2, filed=20150515)],
        _full_year("A", 20141231, assets=100.0, income=10.0, revenue=50.0)
        + _full_year("B", 20141231, assets=200.0, income=20.0, revenue=90.0),
    )
    records = annual_records(*parse_dera_archive(payload))
    dates = pd.date_range("2015-01-31", "2015-12-31", freq="ME")
    panneau = PITFrame(records).panel(dates, as_of_col="as_of")
    rapport = assert_no_lookahead(panneau, "as_of")
    assert rapport.clean
    assert set(panneau.loc[panneau["as_of"] == pd.Timestamp("2015-04-30"), "entity_id"]) == {1}


def test_une_fuite_fabriquee_est_bien_attrapee() -> None:
    """Le contrôle anti-fuite échoue quand on avance la date de disponibilité.

    Ce contrôle inverse prouve que le test précédent teste quelque chose. Sans
    lui, un ``assert_no_lookahead`` qui ne regarderait rien passerait aussi.
    """
    frame = pd.DataFrame(
        {
            "entity_id": [1],
            "period_end": [pd.Timestamp("2014-12-31")],
            "available_from": [pd.Timestamp("2015-03-31")],
            "AT": [100.0],
        }
    )
    with pytest.raises(LookAheadError):
        assert_no_lookahead(PITFrame(frame), "2015-01-31")


# --------------------------------------------------------------------------- #
# La sélection des exercices
# --------------------------------------------------------------------------- #


def _panel_deux_exercices() -> pd.DataFrame:
    """Rend un panneau à deux exercices pour une société, à une date de décision."""
    return pd.DataFrame(
        {
            "as_of": [pd.Timestamp("2015-06-30")] * 3,
            "entity_id": [1, 1, 1],
            "period_end": [
                pd.Timestamp("2009-12-31"),
                pd.Timestamp("2013-12-31"),
                pd.Timestamp("2014-12-31"),
            ],
            "AT": [50.0, 90.0, 100.0],
        }
    )


# --------------------------------------------------------------------------- #
# Le crible d'univers, point-in-time
# --------------------------------------------------------------------------- #


def _registre_deux_societes() -> pd.DataFrame:
    """Une petite qui grossit après 2015, une grosse qui l'est déjà."""
    return pd.DataFrame(
        {
            "entity_id": [1, 1, 2, 2],
            "available_from": pd.to_datetime(["2015-02-01", "2016-02-01", "2015-02-01", "2016-02-01"]),
            "period_end": pd.to_datetime(["2014-12-31", "2015-12-31", "2014-12-31", "2015-12-31"]),
            "AT": [100.0, 120.0, 1.0, 900.0],
            "REVT": [50.0, 60.0, 0.5, 400.0],
        }
    )


def test_le_crible_ignore_la_croissance_a_venir() -> None:
    """La société 2 n'entre qu'en 2016, l'exercice qui la fait grossir n'existant pas avant."""
    screens = size_screens(
        _registre_deux_societes(),
        [pd.Timestamp("2015-06-30"), pd.Timestamp("2016-06-30")],
        max_names=1,
    )
    assert screens[pd.Timestamp("2015-06-30")] == frozenset({1})
    assert screens[pd.Timestamp("2016-06-30")] == frozenset({2})


def test_le_crible_refuse_un_nombre_de_noms_nul() -> None:
    """Un crible qui ne garde personne n'est pas un crible."""
    with pytest.raises(ConfigError):
        size_screens(_registre_deux_societes(), [pd.Timestamp("2015-06-30")], max_names=0)


def test_le_crible_refuse_un_registre_incomplet() -> None:
    """Sans le chiffre d'affaires, le second classement ne se calcule pas."""
    registre = _registre_deux_societes().drop(columns=["REVT"])
    with pytest.raises(ConfigError):
        size_screens(registre, [pd.Timestamp("2015-06-30")], max_names=1)


def test_un_exercice_trop_ancien_ne_qualifie_plus() -> None:
    """Une société qui a cessé de déposer sort du crible passé le regard en arrière."""
    registre = _registre_deux_societes()
    registre = registre[registre["available_from"] == pd.Timestamp("2015-02-01")]
    screens = size_screens(registre, [pd.Timestamp("2020-06-30")], max_names=5, lookback_years=2)
    assert screens[pd.Timestamp("2020-06-30")] == frozenset()


def test_le_crible_en_vigueur_est_le_dernier_anterieur() -> None:
    """Entre deux juins, c'est le juin précédent qui gouverne, jamais le suivant."""
    screens = {
        pd.Timestamp("2015-06-30"): frozenset({1}),
        pd.Timestamp("2016-06-30"): frozenset({1, 2}),
    }
    assert screen_in_force(screens, pd.Timestamp("2015-12-31")) == frozenset({1})
    assert screen_in_force(screens, pd.Timestamp("2016-06-30")) == frozenset({1, 2})
    assert screen_in_force(screens, pd.Timestamp("2014-01-31")) == frozenset({1})


def test_le_crible_vide_est_refuse() -> None:
    """Aucun crible ne veut dire aucune règle, donc une erreur plutôt qu'un défaut muet."""
    with pytest.raises(ConfigError):
        screen_in_force({}, pd.Timestamp("2015-06-30"))


def test_la_reunion_des_cribles_ferait_entrer_le_futur() -> None:
    """Le contrôle qui attrape la fuite : la réunion garde une ligne que le crible du jour refuse."""
    screens = size_screens(
        _registre_deux_societes(),
        [pd.Timestamp("2015-06-30"), pd.Timestamp("2016-06-30")],
        max_names=1,
    )
    variables = pd.DataFrame(
        {
            "as_of": pd.to_datetime(["2015-06-30", "2015-06-30", "2016-06-30", "2016-06-30"]),
            "entity_id": [1, 2, 1, 2],
            "roa": [0.1, 0.2, 0.3, 0.4],
        }
    )
    reunion = frozenset().union(*screens.values())
    naive = variables[variables["entity_id"].isin(reunion)]
    filtre = apply_size_screen(variables, screens)
    assert len(naive) == 4
    assert len(filtre) == 2
    admis_en_2015 = filtre[filtre["as_of"] == pd.Timestamp("2015-06-30")]["entity_id"].tolist()
    assert admis_en_2015 == [1]


def test_le_filtre_refuse_une_colonne_absente() -> None:
    """Sans colonne de date de décision, le filtre ne sait pas quel crible appliquer."""
    variables = pd.DataFrame({"entity_id": [1], "roa": [0.1]})
    with pytest.raises(ConfigError):
        apply_size_screen(variables, {pd.Timestamp("2015-06-30"): frozenset({1})})


def test_le_dernier_exercice_est_le_plus_recent() -> None:
    """La sélection garde l'exercice clos le plus tard, et lui seul."""
    chosen = latest_records(_panel_deux_exercices(), max_staleness_days=548)
    assert len(chosen) == 1
    assert chosen["period_end"].iloc[0] == pd.Timestamp("2014-12-31")


def test_un_exercice_perime_sort_de_l_univers() -> None:
    """Un exercice vieux de plus de la limite ne sert plus, même s'il est le dernier."""
    panel = _panel_deux_exercices()
    panel = panel[panel["period_end"] == pd.Timestamp("2009-12-31")]
    assert latest_records(panel, max_staleness_days=548).empty


def test_l_exercice_retarde_vise_cinq_ans_en_arriere() -> None:
    """Le décalage de cinq ans choisit 2009 quand l'exercice courant finit en 2014."""
    panel = _panel_deux_exercices()
    current = latest_records(panel, max_staleness_days=548)
    lagged = lagged_records(panel, current, years=5, tolerance_days=200)
    assert len(lagged) == 1
    assert lagged["lag_period_end"].iloc[0] == pd.Timestamp("2009-12-31")
    assert float(lagged["lag_AT"].iloc[0]) == pytest.approx(50.0)


def test_une_tolerance_serree_perd_l_exercice_retarde() -> None:
    """Sous une tolérance de dix jours, l'écart de 2009 à la cible reste trop grand."""
    panel = _panel_deux_exercices()
    panel.loc[panel["period_end"] == pd.Timestamp("2009-12-31"), "period_end"] = pd.Timestamp("2009-06-30")
    current = latest_records(panel, max_staleness_days=548)
    assert lagged_records(panel, current, years=5, tolerance_days=10).empty


# --------------------------------------------------------------------------- #
# Les vingt et une variables
# --------------------------------------------------------------------------- #


def _un_exercice() -> pd.DataFrame:
    """Rend une société aux postes ronds, pour les calculs à la main."""
    return pd.DataFrame(
        {
            "AT": [1000.0],
            "BE": [400.0],
            "GP": [300.0],
            "SALE": [800.0],
            "IB": [60.0],
            "DP": [50.0],
            "CAPX": [40.0],
            "DELTA_WC": [30.0],
        }
    )


def test_rentabilite_calculee_a_la_main() -> None:
    """Les six variables de rentabilité sont vérifiées une à une.

    Vérité connue : profit brut sur actif 300/1000 = 0,30. Résultat sur fonds
    propres 60/400 = 0,15. Résultat sur actif 60/1000 = 0,06. Flux de trésorerie
    60 + 50 - 30 - 40 = 40, sur 1000, soit 0,04. Marge brute 300/800 = 0,375.
    Régularisations -(30 - 50)/1000 = 0,02.
    """
    out = profitability_variables(_un_exercice()).iloc[0]
    assert out["gpoa"] == pytest.approx(0.30)
    assert out["roe"] == pytest.approx(0.15)
    assert out["roa"] == pytest.approx(0.06)
    assert out["cfoa"] == pytest.approx(0.04)
    assert out["gmar"] == pytest.approx(0.375)
    assert out["acc"] == pytest.approx(0.02)


def test_un_denominateur_negatif_rend_manquant() -> None:
    """Des fonds propres négatifs ne produisent pas un rendement sur fonds propres."""
    frame = _un_exercice()
    frame["BE"] = [-100.0]
    assert math.isnan(float(profitability_variables(frame)["roe"].iloc[0]))


def test_la_croissance_de_la_marge_se_divise_par_les_ventes() -> None:
    """Le dénominateur de la croissance de marge est les ventes, pas l'actif.

    C'est le piège nommé dans l'annexe A1. L'échantillon écarte volontairement
    les ventes retardées de l'actif retardé, de sorte qu'une confusion des deux
    change le résultat. Vérité connue : le profit brut passe de 100 à 300, la
    variation vaut 200, et 200 divisé par 500 de ventes retardées fait 0,40. La
    même variation sur 2000 d'actif retardé ferait 0,10.
    """
    frame = _un_exercice()
    frame["lag_AT"] = [2000.0]
    frame["lag_BE"] = [800.0]
    frame["lag_GP"] = [100.0]
    frame["lag_SALE"] = [500.0]
    frame["lag_IB"] = [20.0]
    frame["lag_DP"] = [10.0]
    frame["lag_CAPX"] = [5.0]
    frame["lag_DELTA_WC"] = [15.0]
    out = growth_variables(frame).iloc[0]
    assert out["d_gmar"] == pytest.approx(0.40)
    assert out["d_gpoa"] == pytest.approx(0.10)
    assert out["d_roe"] == pytest.approx(40.0 / 800.0)
    assert out["d_roa"] == pytest.approx(40.0 / 2000.0)


def test_la_croissance_du_flux_de_tresorerie_se_calcule_a_la_main() -> None:
    """Vérité connue : le flux passe de 10 à 40, soit 30 sur 2000 d'actif retardé.

    Le flux retardé vaut 20 plus 10 moins 15 moins 5, soit 10. Le flux courant
    vaut 40, calculé au test précédent. La variation vaut donc 30.
    """
    frame = _un_exercice()
    frame["lag_AT"] = [2000.0]
    frame["lag_BE"] = [800.0]
    frame["lag_GP"] = [100.0]
    frame["lag_SALE"] = [500.0]
    frame["lag_IB"] = [20.0]
    frame["lag_DP"] = [10.0]
    frame["lag_CAPX"] = [5.0]
    frame["lag_DELTA_WC"] = [15.0]
    assert float(growth_variables(frame)["d_cfoa"].iloc[0]) == pytest.approx(30.0 / 2000.0)


def test_la_cote_de_altman_se_calcule_a_la_main() -> None:
    """Vérité connue, calculée terme par terme.

    Avec un fonds de roulement de 100, des bénéfices non répartis de 200, un
    résultat d'exploitation de 50, une valeur boursière de 600 et des ventes de
    800, le numérateur vaut 120 plus 280 plus 165 plus 360 plus 800, soit 1725.
    Divisé par 1000 d'actif, la cote vaut 1,725.
    """
    frame = pd.DataFrame(
        {"WC": [100.0], "RE": [200.0], "EBIT": [50.0], "ME": [600.0], "SALE": [800.0], "AT": [1000.0]}
    )
    assert float(altman_z_score(frame).iloc[0]) == pytest.approx(1.725)


def _pour_ohlson() -> pd.DataFrame:
    """Rend deux sociétés dont les postes servent à la cote d'Ohlson."""
    return pd.DataFrame(
        {
            "AT": [1000.0, 2000.0],
            "ME": [600.0, 900.0],
            "BE": [400.0, 700.0],
            "DLC": [50.0, 100.0],
            "DLTT": [150.0, 400.0],
            "ACT": [300.0, 500.0],
            "LCT": [200.0, 250.0],
            "LT": [600.0, 1300.0],
            "IB": [60.0, -20.0],
            "PT": [80.0, -25.0],
            "IB_previous": [40.0, -10.0],
        }
    )


def test_la_cote_d_ohlson_se_calcule_a_la_main() -> None:
    """Vérité connue, calculée terme par terme sur la première société.

    L'actif ajusté vaut 1000 plus un dixième de 200, soit 1020. Les huit termes
    suivants se lisent dans l'annexe A1, et leur somme avec la constante donne
    la valeur attendue ci-dessous.
    """
    frame = _pour_ohlson()
    adj = 1000.0 + 0.1 * (600.0 - 400.0)
    attendu = (
        -1.32
        - 0.407 * math.log(adj)
        + 6.03 * (50.0 + 150.0) / adj
        - 1.43 * (300.0 - 200.0) / adj
        + 0.076 * (200.0 / 300.0)
        - 1.72 * 0.0
        - 2.37 * (60.0 / 1000.0)
        - 1.83 * (80.0 / 600.0)
        + 0.285 * 0.0
        - 0.521 * (60.0 - 40.0) / (60.0 + 40.0)
    )
    assert float(ohlson_o_score(frame).iloc[0]) == pytest.approx(attendu)


def test_le_temoin_de_deux_pertes_s_allume() -> None:
    """La seconde société perd deux exercices de suite, donc le témoin vaut un.

    La différence des deux cotes calculées avec et sans ce terme doit valoir
    exactement le coefficient de l'annexe, 0,285.
    """
    frame = _pour_ohlson()
    avec = float(ohlson_o_score(frame).iloc[1])
    sans = frame.copy()
    sans.loc[1, "IB_previous"] = 10.0
    chin_avec = (-20.0 - (-10.0)) / (20.0 + 10.0)
    chin_sans = (-20.0 - 10.0) / (20.0 + 10.0)
    attendu = 0.285 * (1.0 - 0.0) - 0.521 * (chin_avec - chin_sans)
    assert avec - float(ohlson_o_score(sans).iloc[1]) == pytest.approx(attendu)


def test_l_indice_des_prix_ne_deplace_aucun_rang() -> None:
    """Changer l'indice des prix décale toutes les cotes du même montant.

    C'est une propriété mathématique : l'indice entre par un logarithme commun à
    toutes les sociétés de la date. Le score final passant par les rangs, la
    valeur retenue pour l'indice ne peut pas changer le classement.
    """
    frame = _pour_ohlson()
    un = ohlson_o_score(frame, cpi=1.0)
    cent = ohlson_o_score(frame, cpi=100.0)
    ecarts = (un - cent).to_numpy()
    assert ecarts[0] == pytest.approx(ecarts[1])
    assert un.rank().tolist() == cent.rank().tolist()


def test_un_indice_des_prix_negatif_est_refuse() -> None:
    """Un indice nul ou négatif n'a pas de logarithme, et se refuse à l'entrée."""
    with pytest.raises(ConfigError, match="strictement positif"):
        ohlson_o_score(_pour_ohlson(), cpi=0.0)


def test_les_signes_de_la_surete() -> None:
    """Quatre des six variables de sûreté sont prises en négatif.

    Vérité connue : un bêta de 1,3 donne -1,3, une volatilité résiduelle de 0,25
    donne -0,25, un levier de 200 sur 1000 donne -0,20, et une volatilité des
    bénéfices de 0,08 donne -0,08.
    """
    frame = _pour_ohlson()
    frame["TOTD"] = [200.0, 500.0]
    frame["WC"] = [100.0, 250.0]
    frame["RE"] = [200.0, 100.0]
    frame["EBIT"] = [50.0, -30.0]
    frame["SALE"] = [800.0, 1200.0]
    frame["beta"] = [1.3, 0.7]
    frame["ivol_raw"] = [0.25, 0.40]
    frame["evol_raw"] = [0.08, 0.15]
    out = safety_variables(frame)
    assert float(out["bab"].iloc[0]) == pytest.approx(-1.3)
    assert float(out["ivol"].iloc[0]) == pytest.approx(-0.25)
    assert float(out["lev"].iloc[0]) == pytest.approx(-0.20)
    assert float(out["evol"].iloc[0]) == pytest.approx(-0.08)
    assert float(out["o_score"].iloc[0]) == pytest.approx(-float(ohlson_o_score(frame).iloc[0]))


def test_la_distribution_se_calcule_a_la_main() -> None:
    """Vérité connue : émettre des actions abaisse la note, en racheter la relève.

    Le nombre d'actions passe de 100 à 110, donc l'émission vaut moins le
    logarithme de 1,1. La dette passe de 200 à 180, donc la variable vaut moins
    le logarithme de 0,9, un nombre positif. Le taux de distribution vaut 150
    divisé par 600, soit 0,25.
    """
    frame = pd.DataFrame(
        {
            "SHROUT": [110.0],
            "lag1_SHROUT": [100.0],
            "TOTD": [180.0],
            "lag1_TOTD": [200.0],
            "NPOP_NUMERATOR": [150.0],
            "NPOP_DENOMINATOR": [600.0],
        }
    )
    out = payout_variables(frame).iloc[0]
    assert out["eiss"] == pytest.approx(-math.log(1.1))
    assert out["diss"] == pytest.approx(-math.log(0.9))
    assert out["npop"] == pytest.approx(0.25)


# --------------------------------------------------------------------------- #
# Le nettoyage des prix
# --------------------------------------------------------------------------- #


def test_un_prix_nul_fabrique_un_rendement_infini() -> None:
    """Sans nettoyage, un prix nul rend un rendement infini, et le nettoyage l'empêche.

    Vérité connue par l'arithmétique : passer de zéro à dix donne un rapport
    infini, et passer de dix à moins cinq donne moins cent cinquante pour cent.
    Le nettoyage retire les deux prix fautifs, donc les rendements qui les
    touchent valent manquant au lieu de valoir l'impossible.
    """
    prix = pd.DataFrame({"A": [10.0, 0.0, 10.0, -5.0, 20.0]})
    assert np.isinf(prix.pct_change().to_numpy()).any()
    nettoye, retires = usable_prices(prix)
    assert retires == 2
    assert not np.isinf(nettoye.pct_change().to_numpy()[~np.isnan(nettoye.pct_change().to_numpy())]).any()
    assert nettoye["A"].isna().tolist() == [False, True, False, True, False]


def test_un_rendement_de_trois_cents_fois_est_retire() -> None:
    """Le raccord de deux titres sous un symbole fabrique un rendement impossible.

    Vérité connue par le cas mesuré de Chord Energy : le cours passe de onze
    cents à 34,20 dollars entre octobre et novembre 2020, soit un rendement de
    30 990 pour cent. Le filtre le retire et laisse les rendements ordinaires
    intacts.
    """
    rendements = pd.DataFrame({"A": [0.05, 309.9, -0.20], "B": [0.01, 0.02, 0.03]})
    nettoye, retires = drop_return_outliers(rendements, max_return=3.0, min_return=-0.99)
    assert len(retires) == 1
    assert float(retires["value"].iloc[0]) == pytest.approx(309.9)
    assert bool(nettoye["A"].isna().tolist()[1])
    assert nettoye["B"].notna().all()


def test_les_bornes_de_rendement_se_verifient() -> None:
    """Un rendement ne descend pas sous moins un, et les bornes s'ordonnent."""
    rendements = pd.DataFrame({"A": [0.0]})
    with pytest.raises(ConfigError, match="moins un"):
        drop_return_outliers(rendements, max_return=3.0, min_return=-2.0)
    with pytest.raises(ConfigError, match="non ordonnées"):
        drop_return_outliers(rendements, max_return=-0.5, min_return=-0.5)


def test_le_nettoyage_ne_compte_pas_les_valeurs_deja_manquantes() -> None:
    """Une case déjà manquante n'est pas une case retirée par le nettoyage."""
    prix = pd.DataFrame({"A": [10.0, np.nan, 12.0], "B": [1.0, 2.0, 0.0]})
    nettoye, retires = usable_prices(prix)
    assert retires == 1
    assert int(nettoye.isna().to_numpy().sum()) == 2


# --------------------------------------------------------------------------- #
# Les variables de marché
# --------------------------------------------------------------------------- #


def _marche_et_titres(n: int = 1400) -> tuple[pd.DataFrame, pd.Series]:
    """Rend un marché et trois titres dont deux ont un bêta connu d'avance."""
    generator = np.random.default_rng(4)
    dates = pd.bdate_range("2010-01-01", periods=n)
    market = pd.Series(generator.normal(0.0004, 0.01, n), index=dates, name="MKT")
    frame = pd.DataFrame(
        {
            "DEUX": 2.0 * market.to_numpy(),
            "UN": market.to_numpy(),
            "BRUIT": generator.normal(0.0, 0.01, n),
        },
        index=dates,
    )
    return frame, market


def test_le_beta_d_un_titre_deux_fois_le_marche_est_connu() -> None:
    """Vérité connue par construction : bêta brut de deux, rétréci à 1,6.

    Le titre vaut exactement deux fois le marché, donc la corrélation vaut un et
    le rapport des écarts types vaut deux, aux effets du logarithme près. Le
    rétrécissement à 0,6 sur une cible de un donne 1,6.
    """
    frame, market = _marche_et_titres()
    dates = [frame.index[-1]]
    betas = frazzini_pedersen_beta(frame, market, dates)
    assert float(betas.loc[dates[0], "DEUX"]) == pytest.approx(1.6, abs=0.02)
    assert float(betas.loc[dates[0], "UN"]) == pytest.approx(1.0, abs=0.02)


def test_le_beta_ne_lit_pas_l_avenir() -> None:
    """Perturber les séances postérieures à la date ne change pas le bêta calculé.

    C'est le contrôle de causalité, appliqué directement à la fonction. Une
    fenêtre mal bornée le ferait échouer, et rien d'autre ne le signalerait.
    """
    frame, market = _marche_et_titres()
    coupure = frame.index[1000]
    reference = frazzini_pedersen_beta(frame, market, [coupure])
    trouble = frame.copy()
    trouble.iloc[1001:] = trouble.iloc[1001:] + 0.5
    perturbe = frazzini_pedersen_beta(trouble, market, [coupure])
    pd.testing.assert_frame_equal(reference, perturbe)


def test_le_beta_refuse_une_fenetre_nulle() -> None:
    """Une fenêtre d'un jour ne définit aucun écart type, et se refuse."""
    frame, market = _marche_et_titres(400)
    with pytest.raises(ConfigError, match="strictement positifs"):
        frazzini_pedersen_beta(frame, market, [frame.index[-1]], volatility_window=1)


def test_la_volatilite_residuelle_d_un_titre_colineaire_est_nulle() -> None:
    """Vérité connue : un titre qui vaut deux fois le marché n'a aucun résidu.

    Avec un bêta imposé de deux, le résidu vaut identiquement zéro, donc son
    écart type aussi. Un signe inversé dans la soustraction donnerait quatre
    fois la volatilité du marché.
    """
    frame, market = _marche_et_titres(400)
    date = frame.index[-1]
    betas = pd.DataFrame({"DEUX": [2.0], "UN": [1.0], "BRUIT": [0.0]}, index=[date])
    sigma = idiosyncratic_volatility(frame, market, betas, [date])
    assert float(sigma.loc[date, "DEUX"]) == pytest.approx(0.0, abs=1e-12)
    assert float(sigma.loc[date, "BRUIT"]) == pytest.approx(
        float(frame["BRUIT"].iloc[-252:-1].std()), rel=1e-6
    )


def test_la_volatilite_des_benefices_se_calcule_a_la_main() -> None:
    """Vérité connue : douze trimestres alternant deux valeurs.

    Le rendement trimestriel des fonds propres vaut 0,02 puis 0,04, en
    alternance sur douze trimestres. L'écart type d'échantillon de six valeurs à
    0,02 et six à 0,04 vaut 0,01 multiplié par la racine de douze sur onze.
    """
    sub_rows: list[str] = []
    num_rows: list[str] = []
    dates = pd.date_range("2012-03-31", periods=12, freq="QE")
    for index, moment in enumerate(dates):
        adsh = f"Q{index:02d}"
        ddate = int(moment.strftime("%Y%m%d"))
        filed = int((moment + pd.Timedelta(days=30)).strftime("%Y%m%d"))
        sub_rows.append(_sub(adsh, 1, form="10-Q", filed=filed))
        income = 2.0 if index % 2 == 0 else 4.0
        num_rows.append(_num(adsh, "NetIncomeLoss", ddate, 1, income))
        num_rows.append(_num(adsh, "StockholdersEquity", ddate, 0, 100.0))
    submissions, numbers = parse_dera_archive(_archive(sub_rows, num_rows))
    out = quarterly_roe_volatility(submissions, numbers, [pd.Timestamp("2015-06-30")])
    attendu = 0.01 * math.sqrt(12.0 / 11.0)
    assert len(out) == 1
    assert float(out["evol_raw"].iloc[0]) == pytest.approx(attendu)
    assert int(out["evol_count"].iloc[0]) == 12


def test_onze_trimestres_ne_suffisent_pas() -> None:
    """Le seuil de douze observations écarte une société trop jeune."""
    sub_rows: list[str] = []
    num_rows: list[str] = []
    for index, moment in enumerate(pd.date_range("2012-03-31", periods=11, freq="QE")):
        adsh = f"Q{index:02d}"
        ddate = int(moment.strftime("%Y%m%d"))
        filed = int((moment + pd.Timedelta(days=30)).strftime("%Y%m%d"))
        sub_rows.append(_sub(adsh, 1, form="10-Q", filed=filed))
        num_rows.append(_num(adsh, "NetIncomeLoss", ddate, 1, 2.0 + index))
        num_rows.append(_num(adsh, "StockholdersEquity", ddate, 0, 100.0))
    submissions, numbers = parse_dera_archive(_archive(sub_rows, num_rows))
    assert quarterly_roe_volatility(submissions, numbers, [pd.Timestamp("2015-06-30")]).empty


# --------------------------------------------------------------------------- #
# Les rangs, les composantes et le score
# --------------------------------------------------------------------------- #


def _panneau(n_dates: int = 4, n_names: int = 12) -> pd.DataFrame:
    """Rend un panneau de valeurs strictement croissantes par colonne."""
    dates = pd.date_range("2015-01-31", periods=n_dates, freq="ME")
    names = [f"S{i:02d}" for i in range(n_names)]
    values = np.arange(n_names, dtype="float64")[None, :] + np.arange(n_dates)[:, None]
    return pd.DataFrame(values, index=dates, columns=names)


def test_la_cote_de_rang_est_centree_et_reduite() -> None:
    """Propriété mathématique : la cote a pour moyenne zéro et pour écart type un."""
    out = rank_zscore(_panneau(), min_names=5)
    assert out.mean(axis=1).abs().max() == pytest.approx(0.0, abs=1e-12)
    assert out.std(axis=1, ddof=1).sub(1.0).abs().max() == pytest.approx(0.0, abs=1e-12)


def test_la_cote_de_rang_ignore_toute_transformation_croissante() -> None:
    """Propriété mathématique : élever au cube ne change aucun rang, donc aucune cote.

    C'est ce qui distingue le rang de la cote de niveau. Une implémentation qui
    standardiserait les niveaux au lieu des rangs échouerait ici.
    """
    panel = _panneau()
    pd.testing.assert_frame_equal(rank_zscore(panel, min_names=5), rank_zscore(panel**3, min_names=5))


def _variables_completes() -> pd.DataFrame:
    """Rend un tableau long portant les vingt et une variables, sans trou."""
    generator = np.random.default_rng(11)
    dates = pd.date_range("2015-01-31", periods=3, freq="ME")
    names = list(range(30))
    rows = []
    for moment in dates:
        for name in names:
            row = {"as_of": moment, "entity_id": name}
            for names_of_component in COMPONENT_VARIABLES.values():
                for variable in names_of_component:
                    row[variable] = float(generator.normal())
            rows.append(row)
    return pd.DataFrame(rows)


def test_la_moyenne_et_la_somme_donnent_la_meme_composante() -> None:
    """Identité algébrique : sur une ligne complète, moyenne et somme coïncident.

    La composante est la cote de la moyenne des cotes de ses variables. La règle
    de l'article standardise la somme. Les deux ne diffèrent que d'un facteur
    constant, que la standardisation efface. Le test le vérifie en reconstruisant
    la somme à la main depuis les panneaux de variables.
    """
    variables = _variables_completes()
    scores, counts = component_scores(variables, min_names=5)
    panels = variable_panels(variables, min_names=5)
    for component, names in COMPONENT_VARIABLES.items():
        somme = sum(panels[name] for name in names)
        centre = somme.sub(somme.mean(axis=1), axis=0).div(somme.std(axis=1, ddof=1), axis=0)
        pd.testing.assert_frame_equal(scores[component], centre, check_names=False)
        assert int(counts[component].to_numpy().min()) == len(names)


def test_une_composante_trop_creuse_est_effacee() -> None:
    """Sous le seuil de variables renseignées, la composante vaut manquant."""
    variables = _variables_completes()
    variables.loc[variables["entity_id"] == 0, ["roe", "roa", "cfoa", "gmar", "acc"]] = np.nan
    scores, _ = component_scores(variables, min_variables={"profitability": 3}, min_names=5)
    assert scores["profitability"][0].isna().all()


def test_le_score_exige_assez_de_composantes() -> None:
    """Une société à deux composantes seulement sort du score quand trois sont exigées."""
    variables = _variables_completes()
    scores, _ = component_scores(variables, min_names=5)
    scores["growth"].loc[:, 0] = np.nan
    scores["safety"].loc[:, 0] = np.nan
    quality = quality_score(scores, min_components=3, min_names=5)
    assert quality[0].isna().all()
    assert quality.drop(columns=[0]).notna().all().all()


def test_le_score_est_centre_et_reduit() -> None:
    """Propriété mathématique : le score final est une cote transversale."""
    variables = _variables_completes()
    scores, _ = component_scores(variables, min_names=5)
    quality = quality_score(scores, min_names=5)
    assert quality.mean(axis=1).abs().max() == pytest.approx(0.0, abs=1e-12)
    assert quality.std(axis=1, ddof=1).sub(1.0).abs().max() == pytest.approx(0.0, abs=1e-12)


def test_le_score_refuse_un_dictionnaire_vide() -> None:
    """Sans composante, il n'y a pas de score, et la fonction le dit."""
    with pytest.raises(ConfigError, match="aucune composante"):
        quality_score({})


# --------------------------------------------------------------------------- #
# Le facteur
# --------------------------------------------------------------------------- #


def _univers(n_dates: int = 6, n_names: int = 100) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Rend un univers dont la qualité décide du rendement, à valeur connue.

    Les sociétés de score élevé rendent dix pour cent, celles de score bas en
    perdent dix, les autres rien. La capitalisation alterne pour que les deux
    moitiés de taille se remplissent également.
    """
    dates = pd.date_range("2015-01-31", periods=n_dates, freq="ME")
    names = [f"S{i:03d}" for i in range(n_names)]
    scores = pd.DataFrame(np.tile(np.linspace(-1.0, 1.0, n_names), (n_dates, 1)), index=dates, columns=names)
    equity = pd.DataFrame(
        np.tile(np.where(np.arange(n_names) % 2 == 0, 1.0, 3.0), (n_dates, 1)),
        index=dates,
        columns=names,
    )
    forward = pd.DataFrame(0.0, index=dates, columns=names)
    forward.loc[:, names[-30:]] = 0.10
    forward.loc[:, names[:30]] = -0.10
    return scores, equity, forward


def test_le_facteur_retrouve_l_ecart_impose() -> None:
    """Vérité connue par construction : vingt points d'écart entre les deux jambes.

    Les trente meilleurs scores gagnent dix pour cent, les trente pires en
    perdent autant, et le tri à trente pour cent les sélectionne exactement. Le
    facteur vaut donc 0,20 à chaque date, quelle que soit la pondération.
    """
    scores, equity, forward = _univers()
    factor = quality_minus_junk(scores, equity, forward, min_names_per_leg=5)
    assert factor.returns.round(10).unique().tolist() == [0.20]
    assert set(factor.counts.columns) == {"small_quality", "big_quality", "small_junk", "big_junk"}


def test_le_facteur_est_neutre_en_taille_par_construction() -> None:
    """La somme des poids des grandes égale celle des petites, au signe près.

    Chaque moitié de taille pèse un demi à l'achat et un demi à la vente. La
    somme algébrique des poids d'une moitié vaut donc zéro, ce qui est ce que
    veut dire « neutre en taille » dans l'article.
    """
    scores, equity, forward = _univers()
    factor = quality_minus_junk(scores, equity, forward, min_names_per_leg=5)
    date = factor.weights.index[0]
    poids = factor.weights.loc[date]
    petites = poids[[c for c in poids.index if int(c[1:]) % 2 == 0]]
    assert float(petites.sum()) == pytest.approx(0.0, abs=1e-12)
    assert float(poids.abs().sum()) == pytest.approx(2.0)


def test_le_facteur_ne_lit_pas_l_avenir() -> None:
    """Perturber les rendements postérieurs à une date ne change rien avant elle.

    La fonction ne décale rien elle-même : elle consomme un tableau de
    rendements déjà avancé d'un mois par l'appelant. Le contrôle porte donc sur
    l'absence de tout regard au-delà de la ligne courante.
    """
    scores, equity, forward = _univers()
    reference = quality_minus_junk(scores, equity, forward, min_names_per_leg=5).returns
    trouble = forward.copy()
    trouble.iloc[3:] = trouble.iloc[3:] + 1.0
    perturbe = quality_minus_junk(scores, equity, trouble, min_names_per_leg=5).returns
    pd.testing.assert_series_equal(reference.iloc[:3], perturbe.iloc[:3])


def test_une_societe_sans_rendement_sort_de_sa_jambe() -> None:
    """Un rendement manquant retire la société et renormalise les poids restants.

    Vérité connue : en pondération égale sur trente sociétés, retirer l'une
    d'elles porte chaque poids restant de un trentième à un vingt-neuvième, donc
    la moitié de jambe pèse toujours un demi.
    """
    scores, equity, forward = _univers()
    forward.iloc[:, -1] = np.nan
    factor = quality_minus_junk(scores, equity, forward, weighting="equal", min_names_per_leg=5)
    assert int(factor.counts["big_quality"].iloc[0] + factor.counts["small_quality"].iloc[0]) == 29
    assert float(factor.weights.iloc[0].abs().sum()) == pytest.approx(2.0)


def test_le_facteur_refuse_une_part_impossible() -> None:
    """Une part de sept dixièmes ferait se recouvrir les deux extrémités."""
    scores, equity, forward = _univers()
    with pytest.raises(ConfigError, match="quality_quantile"):
        quality_minus_junk(scores, equity, forward, quality_quantile=0.7)


def test_le_facteur_refuse_une_ponderation_inconnue() -> None:
    """Seules la pondération par la valeur et la pondération égale existent."""
    scores, equity, forward = _univers()
    with pytest.raises(ConfigError, match="pondération inconnue"):
        quality_minus_junk(scores, equity, forward, weighting="racine")


def test_un_univers_trop_petit_ne_produit_aucune_date() -> None:
    """Sans assez de sociétés pour remplir les quatre coins, la fonction lève."""
    scores, equity, forward = _univers(n_names=20)
    with pytest.raises(InsufficientDataError, match="quatre coins"):
        quality_minus_junk(scores, equity, forward, min_names_per_leg=40)


# --------------------------------------------------------------------------- #
# Le repli à trois composantes
# --------------------------------------------------------------------------- #


def test_l_approximation_moyenne_ses_trois_ecarts() -> None:
    """Vérité connue : trois écarts de 2, 4 et 6 points ont pour moyenne 4 points."""
    index = pd.date_range("2015-01-31", periods=2, freq="ME")
    legs = {
        "profitability": (pd.Series([0.05, 0.05], index=index), pd.Series([0.03, 0.03], index=index)),
        "growth": (pd.Series([0.06, 0.06], index=index), pd.Series([0.02, 0.02], index=index)),
        "safety": (pd.Series([0.07, 0.07], index=index), pd.Series([0.01, 0.01], index=index)),
    }
    out = three_component_proxy(legs)
    assert out["profitability"].tolist() == pytest.approx([0.02, 0.02])
    assert out["proxy"].tolist() == pytest.approx([0.04, 0.04])


def test_l_approximation_refuse_un_dictionnaire_vide() -> None:
    """Sans composante, il n'y a rien à moyenner."""
    with pytest.raises(ConfigError, match="aucune composante"):
        three_component_proxy({})

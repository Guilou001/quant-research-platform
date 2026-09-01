"""Contrôles du registre point-in-time.

Aucune valeur attendue de ce fichier ne vient de la sortie du code. Chaque test
dit en commentaire d'où vient son attendu, parmi quatre sources. (a) Un calcul à
la main écrit dans le test, chiffres visibles. (b) Une identité ou une propriété
mathématique. (c) Une valeur publiée et citée. (d) Une implémentation
indépendante écrite dans le test.

Le calendrier de référence, écrit une fois et réutilisé partout. Il vient des
délais de dépôt de la SEC, valeur RAPPORTÉE, règle finale 33-8644 de 2005 :
un 10-Q de grand déposant accéléré part au plus tard 40 jours après la clôture.

    clôture du trimestre     2015-03-31
    dépôt du 10-Q            2015-05-15   soit 45 jours plus tard
    correction du 10-Q       2015-11-09
    clôture du trimestre     2015-06-30
    dépôt du 10-Q            2015-08-14   soit 45 jours plus tard

Les 45 jours se comptent à la main : du 31 mars au 30 avril il y a 30 jours,
du 30 avril au 15 mai il y en a 15, soit 45. Du 30 juin au 31 juillet il y a
31 jours, du 31 juillet au 14 août il y en a 14, soit 45 également.
"""

from __future__ import annotations

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from quantlab.core.errors import ConfigError, DataQualityError, LookAheadError
from quantlab.data.point_in_time import (
    AS_OF_COLUMN,
    LookAheadReport,
    PITFrame,
    asof_join,
    assert_no_lookahead,
    lookahead_report,
)

# --------------------------------------------------------------------------- #
# Jeux d'essai, écrits à la main                                               #
# --------------------------------------------------------------------------- #

#: Le cas canonique : deux trimestres d'une même société, chacun déposé 45 jours après sa clôture.
CANONICAL = pd.DataFrame(
    {
        "entity_id": ["AAA", "AAA"],
        "period_end": ["2015-03-31", "2015-06-30"],
        "available_from": ["2015-05-15", "2015-08-14"],
        "eps": [1.10, 1.25],
    }
)

#: Le premier trimestre 2015, publié le 15 mai à 1,10 puis corrigé le 9 novembre à 0,85.
RESTATEMENT = pd.DataFrame(
    {
        "entity_id": ["BBB", "BBB"],
        "period_end": ["2015-03-31", "2015-03-31"],
        "available_from": ["2015-05-15", "2015-11-09"],
        "eps": [1.10, 0.85],
    }
)


def build(records: list[tuple[str, str, str, float]]) -> pd.DataFrame:
    """Rend un tableau brut depuis une liste de quadruplets écrits à la main."""
    return pd.DataFrame(
        {
            "entity_id": [row[0] for row in records],
            "period_end": [row[1] for row in records],
            "available_from": [row[2] for row in records],
            "eps": [row[3] for row in records],
        }
    )


# --------------------------------------------------------------------------- #
# Le cas canonique : le dépôt du 15 mai n'existe pas le 31 mars                #
# --------------------------------------------------------------------------- #


def test_le_depot_du_15_mai_est_refuse_au_31_mars() -> None:
    """Source (a) : au 31 mars 2015 le 10-Q n'est pas déposé, donc zéro ligne."""
    pit = PITFrame(CANONICAL)
    assert len(pit.as_of("2015-03-31")) == 0
    # La veille du dépôt non plus : la règle est stricte, pas approximative.
    assert len(pit.as_of("2015-05-14")) == 0


def test_le_depot_devient_lisible_le_jour_meme() -> None:
    """Source (a) : le 15 mai, une seule ligne, celle du trimestre clos le 31 mars, eps 1,10."""
    visible = PITFrame(CANONICAL).as_of("2015-05-15")
    assert len(visible) == 1
    assert visible["period_end"].iloc[0] == pd.Timestamp("2015-03-31")
    assert visible["eps"].iloc[0] == pytest.approx(1.10)


def test_les_deux_trimestres_sont_lisibles_apres_le_second_depot() -> None:
    """Source (a) : au 14 août, les deux dépôts sont faits, donc deux lignes et 2,35 de somme."""
    visible = PITFrame(CANONICAL).as_of("2015-08-14")
    assert len(visible) == 2
    # 1,10 + 1,25 = 2,35, addition écrite à la main.
    assert visible["eps"].sum() == pytest.approx(2.35)


def test_as_of_avant_toute_disponibilite_rend_un_tableau_vide() -> None:
    """Source (a) : au 1er janvier 2015 rien n'est déposé, et l'absence n'est pas une erreur."""
    visible = PITFrame(CANONICAL).as_of("2015-01-01")
    assert isinstance(visible, pd.DataFrame)
    assert len(visible) == 0
    # Les colonnes survivent : un tableau vide reste consommable par la suite du pipeline.
    assert list(visible.columns) == ["entity_id", "period_end", "available_from", "eps"]


# --------------------------------------------------------------------------- #
# La correction : la version en vigueur, pas la meilleure version connue       #
# --------------------------------------------------------------------------- #


def test_restatement_rend_l_ancienne_valeur_avant_la_correction() -> None:
    """Source (a) : le 1er août 2015, seule la publication du 15 mai existe, donc 1,10."""
    visible = PITFrame(RESTATEMENT).as_of("2015-08-01")
    assert len(visible) == 1
    assert visible["eps"].iloc[0] == pytest.approx(1.10)


def test_restatement_rend_la_nouvelle_valeur_le_jour_de_la_correction() -> None:
    """Source (a) : le 9 novembre 2015, la correction est publiée, donc 0,85 et une seule ligne."""
    visible = PITFrame(RESTATEMENT).as_of("2015-11-09")
    assert len(visible) == 1
    assert visible["eps"].iloc[0] == pytest.approx(0.85)


def test_restatement_keep_first_rend_la_publication_d_origine() -> None:
    """Source (a) : « first » garde la version d'origine, 1,10, même après la correction."""
    visible = PITFrame(RESTATEMENT).as_of("2015-11-09", keep="first")
    assert visible["eps"].iloc[0] == pytest.approx(1.10)


def test_restatement_keep_all_rend_les_deux_versions() -> None:
    """Source (a) : « all » ne déduplique pas, donc deux lignes après le 9 novembre."""
    visible = PITFrame(RESTATEMENT).as_of("2015-11-09", keep="all")
    assert len(visible) == 2
    assert visible["eps"].tolist() == [1.10, 0.85]


def test_keep_inconnu_refuse() -> None:
    """Source (a) : « latest » n'est pas une règle du module, il n'est pas deviné."""
    with pytest.raises(ConfigError, match="keep"):
        PITFrame(RESTATEMENT).as_of("2015-11-09", keep="latest")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# La validation du constructeur                                                #
# --------------------------------------------------------------------------- #


def test_disponibilite_anterieure_a_la_periode_leve_lookahead() -> None:
    """Source (a) : un dépôt daté du 1er mars pour un trimestre clos le 31 mars est impossible."""
    poison = build([("AAA", "2015-03-31", "2015-03-01", 1.10)])
    with pytest.raises(LookAheadError) as excinfo:
        PITFrame(poison)
    message = str(excinfo.value)
    # L'entité et l'écart doivent apparaître : un message sans détail n'aide personne.
    assert "AAA" in message
    # Du 1er au 31 mars il y a 30 jours, compté à la main.
    assert "30.00" in message


def test_le_message_de_lookahead_compte_les_lignes_fautives() -> None:
    """Source (a) : deux lignes fautives sur trois, écrites à la main."""
    poison = build(
        [
            ("AAA", "2015-03-31", "2015-05-15", 1.10),
            ("BBB", "2015-03-31", "2015-03-30", 1.20),
            ("CCC", "2015-03-31", "2015-03-29", 1.30),
        ]
    )
    with pytest.raises(LookAheadError, match="2 ligne"):
        PITFrame(poison)


def test_colonne_obligatoire_absente_refusee() -> None:
    """Source (a) : sans « available_from », le registre ne peut rien garantir."""
    incomplete = CANONICAL.drop(columns=["available_from"])
    with pytest.raises(DataQualityError, match="available_from"):
        PITFrame(incomplete)


def test_date_manquante_refusee() -> None:
    """Source (a) : une comparaison contre NaT rend False, ce qui masquerait la fuite."""
    holed = build([("AAA", "2015-03-31", "2015-05-15", 1.10)])
    holed.loc[0, "available_from"] = None
    with pytest.raises(DataQualityError, match="manquante"):
        PITFrame(holed)


def test_colonne_de_periode_numerique_refusee() -> None:
    """Source (a) : 20150331 lu comme des nanosecondes donnerait une date de 1970."""
    numeric = build([("AAA", "2015-03-31", "2015-05-15", 1.10)])
    numeric["period_end"] = [20150331]
    with pytest.raises(DataQualityError, match="nombres"):
        PITFrame(numeric)


def test_entite_manquante_refusee() -> None:
    """Source (a) : une ligne sans entité ne peut être appariée à aucun titre."""
    anonymous = build([("AAA", "2015-03-31", "2015-05-15", 1.10)])
    anonymous.loc[0, "entity_id"] = None
    with pytest.raises(DataQualityError, match="entité"):
        PITFrame(anonymous)


def test_registre_vide_est_licite() -> None:
    """Source (a) : un registre sans ligne est un état légitime, pas une erreur."""
    empty = pd.DataFrame({"entity_id": [], "period_end": [], "available_from": [], "eps": []})
    pit = PITFrame(empty)
    assert len(pit) == 0
    assert len(pit.as_of("2015-05-15")) == 0
    assert pit.entities == ()


def test_registre_d_une_seule_ligne() -> None:
    """Source (a) : une ligne unique se comporte comme le cas général."""
    pit = PITFrame(build([("AAA", "2015-03-31", "2015-05-15", 1.10)]))
    assert len(pit.as_of("2015-05-14")) == 0
    assert len(pit.as_of("2015-05-15")) == 1


def test_fuseau_discordant_refuse() -> None:
    """Source (a) : comparer une date naïve à une date localisée est refusé, pas arbitré."""
    mixed = build([("AAA", "2015-03-31", "2015-05-15", 1.10)])
    mixed["available_from"] = pd.to_datetime(mixed["available_from"]).dt.tz_localize("UTC")
    with pytest.raises(DataQualityError, match="fuseau"):
        PITFrame(mixed)


def test_date_de_decision_localisee_sur_registre_naif_refusee() -> None:
    """Source (a) : la date de décision doit avoir le même caractère que la colonne."""
    pit = PITFrame(CANONICAL)
    with pytest.raises(ConfigError, match="fuseau"):
        pit.as_of(pd.Timestamp("2015-05-15", tz="UTC"))


def test_colonnes_utiles_et_entites() -> None:
    """Source (a) : trois colonnes de clé, donc « eps » seul reste comme valeur."""
    pit = PITFrame(CANONICAL)
    assert pit.value_columns == ("eps",)
    assert pit.entities == ("AAA",)
    assert len(pit) == 2


# --------------------------------------------------------------------------- #
# latest_as_of et panel                                                        #
# --------------------------------------------------------------------------- #


def test_latest_as_of_rend_une_ligne_par_entite() -> None:
    """Source (a) : au 1er septembre, AAA a deux trimestres publiés, le plus récent est celui de juin."""
    both = pd.concat([CANONICAL, build([("BBB", "2015-03-31", "2015-05-15", 2.00)])], ignore_index=True)
    latest = PITFrame(both).latest_as_of("2015-09-01")
    assert len(latest) == 2
    aaa = latest[latest["entity_id"] == "AAA"]
    assert aaa["period_end"].iloc[0] == pd.Timestamp("2015-06-30")
    assert aaa["eps"].iloc[0] == pytest.approx(1.25)


def test_latest_as_of_recule_avec_la_date() -> None:
    """Source (a) : au 1er juin, seul le trimestre de mars est publié, donc eps 1,10."""
    latest = PITFrame(CANONICAL).latest_as_of("2015-06-01")
    assert len(latest) == 1
    assert latest["period_end"].iloc[0] == pd.Timestamp("2015-03-31")


def test_latest_as_of_vide_avant_tout_depot() -> None:
    """Source (a) : rien n'est publié le 1er janvier, donc aucune ligne."""
    assert len(PITFrame(CANONICAL).latest_as_of("2015-01-01")) == 0


def test_panel_empile_les_etats_connaissables() -> None:
    """Source (a) : trois dates de rééquilibrage, 0 + 1 + 2 = 3 lignes, addition à la main."""
    panel = PITFrame(CANONICAL).panel(["2015-05-14", "2015-05-15", "2015-08-14"])
    assert len(panel) == 3
    assert next(iter(panel.columns)) == AS_OF_COLUMN
    counts = panel.groupby(AS_OF_COLUMN).size()
    assert counts.loc[pd.Timestamp("2015-05-15")] == 1
    assert counts.loc[pd.Timestamp("2015-08-14")] == 2


def test_panel_sans_date_rend_un_tableau_vide_type() -> None:
    """Source (a) : aucune date de décision, donc aucune ligne, et les colonnes restent."""
    panel = PITFrame(CANONICAL).panel([])
    assert len(panel) == 0
    assert AS_OF_COLUMN in panel.columns


def test_panel_refuse_une_date_repetee() -> None:
    """Source (a) : deux fois la même date dupliquerait chaque ligne du panneau."""
    with pytest.raises(ConfigError, match="répétée"):
        PITFrame(CANONICAL).panel(["2015-05-15", "2015-05-15"])


def test_panel_refuse_une_collision_de_colonne() -> None:
    """Source (a) : écraser « eps » par la date de décision perdrait la valeur."""
    with pytest.raises(ConfigError, match="eps"):
        PITFrame(CANONICAL).panel(["2015-05-15"], as_of_col="eps")


# --------------------------------------------------------------------------- #
# Implémentation indépendante                                                  #
# --------------------------------------------------------------------------- #


def naive_as_of(records: list[tuple[str, str, str, float]], date: str) -> set[tuple[str, str, float]]:
    """Rend l'état connaissable par une boucle Python, sans pandas.

    Source (d) de la valeur attendue : cette fonction est une seconde
    implémentation, écrite dans un autre style, de la même règle. Elle parcourt
    les lignes dans leur ordre d'arrivée et garde, pour chaque couple entité et
    fin de période, celle dont la disponibilité est la plus tardive.
    """
    best: dict[tuple[str, str], tuple[str, int, float]] = {}
    for position, (entity, period, available, value) in enumerate(records):
        if available > date:
            continue
        key = (entity, period)
        candidate = (available, position, value)
        current = best.get(key)
        if current is None or candidate[:2] >= current[:2]:
            best[key] = candidate
    return {(entity, period, value) for (entity, period), (_, _, value) in best.items()}


#: Huit lignes écrites à la main : trois sociétés, des dépôts en retard, deux corrections.
MIXED: list[tuple[str, str, str, float]] = [
    ("AAA", "2015-03-31", "2015-05-15", 1.10),
    ("AAA", "2015-03-31", "2015-11-09", 0.85),
    ("AAA", "2015-06-30", "2015-08-14", 1.25),
    ("BBB", "2015-03-31", "2015-06-30", 2.00),
    ("BBB", "2015-06-30", "2015-09-30", 2.10),
    ("CCC", "2015-03-31", "2015-05-15", 3.00),
    ("CCC", "2015-03-31", "2015-05-15", 3.05),
    ("CCC", "2015-12-31", "2016-03-15", 3.20),
]


@pytest.mark.parametrize(
    "date",
    ["2015-01-01", "2015-05-15", "2015-06-30", "2015-08-14", "2015-11-09", "2016-03-15", "2020-01-01"],
)
def test_as_of_egale_une_implementation_independante(date: str) -> None:
    """Source (d) : la boucle Python de :func:`naive_as_of` sur les mêmes huit lignes."""
    obtained = PITFrame(build(MIXED)).as_of(date)
    got = {(row.entity_id, row.period_end.strftime("%Y-%m-%d"), row.eps) for row in obtained.itertuples()}
    assert got == naive_as_of(MIXED, date)


# --------------------------------------------------------------------------- #
# Le contrôle anti-fuite                                                       #
# --------------------------------------------------------------------------- #


def test_le_rapport_compte_quarante_cinq_jours() -> None:
    """Source (a) : du 31 mars au 15 mai 2015 il y a 30 + 15 = 45 jours."""
    report = lookahead_report(PITFrame(CANONICAL), "2015-03-31")
    assert report.n_violations == 2
    assert report.n_rows == 2
    assert report.entities == ("AAA",)
    # Le pire écart est celui du dépôt du 14 août : du 31 mars au 14 août,
    # 30 (avril) + 31 (mai) + 30 (juin) + 31 (juillet) + 14 = 136 jours.
    assert report.max_gap_days == pytest.approx(136.0)
    assert not report.clean


def test_la_tolerance_a_sa_frontiere() -> None:
    """Source (a) : à 45 jours de tolérance le dépôt du 15 mai passe, à 44 il échoue."""
    one = PITFrame(build([("AAA", "2015-03-31", "2015-05-15", 1.10)]))
    assert lookahead_report(one, "2015-03-31", tolerance_days=45).clean
    assert lookahead_report(one, "2015-03-31", tolerance_days=44).n_violations == 1


def test_tolerance_negative_refusee() -> None:
    """Source (a) : une tolérance négative n'a pas de sens, elle refuserait le présent."""
    with pytest.raises(ConfigError, match="tolerance_days"):
        lookahead_report(PITFrame(CANONICAL), "2015-06-30", tolerance_days=-1)


def test_assert_no_lookahead_passe_sur_un_panneau() -> None:
    """Source (b) : un panneau construit par as_of ne peut pas fuir, c'est l'invariant du module."""
    panel = PITFrame(CANONICAL).panel(["2015-05-15", "2015-08-14", "2015-12-31"])
    report = assert_no_lookahead(panel, AS_OF_COLUMN)
    assert isinstance(report, LookAheadReport)
    assert report.clean
    # 1 + 2 + 2 = 5 lignes, addition à la main.
    assert report.n_rows == 5


def test_assert_no_lookahead_leve_sur_un_panneau_empoisonne() -> None:
    """Source (a) : décision au 31 mars sur un dépôt du 15 mai, soit 45 jours d'avance."""
    with pytest.raises(LookAheadError, match=r"45\.00"):
        assert_no_lookahead(PITFrame(build([("AAA", "2015-03-31", "2015-05-15", 1.10)])), "2015-03-31")


def test_assert_no_lookahead_accepte_une_suite_alignee() -> None:
    """Source (a) : deux dates pour deux lignes, la première fuit, la seconde non."""
    frame = PITFrame(CANONICAL).data
    report = lookahead_report(frame, ["2015-03-31", "2015-12-31"])
    assert report.n_violations == 1


def test_assert_no_lookahead_refuse_une_longueur_discordante() -> None:
    """Source (a) : trois dates pour deux lignes, l'appariement serait deviné."""
    with pytest.raises(ConfigError, match="3 date"):
        lookahead_report(PITFrame(CANONICAL), ["2015-03-31", "2015-06-30", "2015-09-30"])


def test_lookahead_report_refuse_un_tableau_sans_disponibilite() -> None:
    """Source (a) : sans colonne de disponibilité, il n'y a rien à contrôler."""
    with pytest.raises(DataQualityError, match="available_from"):
        lookahead_report(pd.DataFrame({"entity_id": ["AAA"]}), "2015-03-31")


def test_describe_dit_ce_qui_a_ete_controle() -> None:
    """Source (a) : un rapport propre de dix lignes se décrit sans mentionner de fuite."""
    report = LookAheadReport(n_rows=10, n_violations=0, entities=(), max_gap_days=0.0, tolerance_days=0.0)
    assert "10 ligne(s)" in report.describe()
    assert "aucune fuite" in report.describe()


# --------------------------------------------------------------------------- #
# La jointure temporelle                                                       #
# --------------------------------------------------------------------------- #

#: Deux décisions de portefeuille, au 30 juin et au 30 septembre 2015.
DECISIONS = pd.DataFrame(
    {
        "entity_id": ["AAA", "AAA"],
        "decision_date": pd.to_datetime(["2015-06-30", "2015-09-30"]),
    }
)


def test_asof_join_apparie_le_dernier_depot_connu() -> None:
    """Source (a) : au 30 juin seul le dépôt du 15 mai existe (1,10) ; au 30 septembre celui du 14 août (1,25)."""
    right = PITFrame(CANONICAL).data.sort_values("available_from")
    joint = asof_join(DECISIONS, right, "entity_id", "decision_date", "available_from")
    assert joint["eps"].tolist() == [1.10, 1.25]


def test_asof_join_forward_refuse_sans_aveu() -> None:
    """Source (a) : la direction avant apparie chaque décision au dépôt SUIVANT, c'est la fuite parfaite."""
    right = PITFrame(CANONICAL).data.sort_values("available_from")
    with pytest.raises(LookAheadError, match="forward"):
        asof_join(DECISIONS, right, "entity_id", "decision_date", "available_from", direction="forward")


def test_asof_join_forward_autorise_explicitement() -> None:
    """Source (a) : avec l'aveu, la décision du 30 juin reçoit le dépôt du 14 août, eps 1,25."""
    right = PITFrame(CANONICAL).data.sort_values("available_from")
    joint = asof_join(
        DECISIONS,
        right,
        "entity_id",
        "decision_date",
        "available_from",
        direction="forward",
        allow_lookahead=True,
    )
    assert joint["eps"].iloc[0] == pytest.approx(1.25)


def test_asof_join_refuse_un_tableau_non_trie() -> None:
    """Source (a) : merge_asof exige un tri croissant global, et le silence coûterait un résultat faux."""
    right = PITFrame(CANONICAL).data.sort_values("available_from", ascending=False)
    with pytest.raises(DataQualityError, match="trié"):
        asof_join(DECISIONS, right, "entity_id", "decision_date", "available_from")


def test_asof_join_refuse_une_colonne_de_temps_textuelle() -> None:
    """Source (a) : comparer « 2015-05-15 » à « 2015-06-30 » comme du texte marche par accident, pas par droit."""
    right = PITFrame(CANONICAL).data.sort_values("available_from").copy()
    right["available_from"] = right["available_from"].dt.strftime("%Y-%m-%d")
    with pytest.raises(DataQualityError, match="type"):
        asof_join(DECISIONS, right, "entity_id", "decision_date", "available_from")


def test_asof_join_refuse_une_cle_de_groupe_absente() -> None:
    """Source (a) : sans clé commune, la jointure apparierait des sociétés entre elles."""
    right = PITFrame(CANONICAL).data.sort_values("available_from").drop(columns=["entity_id"])
    with pytest.raises(DataQualityError, match="entity_id"):
        asof_join(DECISIONS, right, "entity_id", "decision_date", "available_from")


def test_asof_join_exclut_l_appariement_exact_si_demande() -> None:
    """Source (a) : la décision du 15 mai n'apparie plus le dépôt du 15 mai, donc valeur manquante."""
    decisions = pd.DataFrame({"entity_id": ["AAA"], "decision_date": pd.to_datetime(["2015-05-15"])})
    right = PITFrame(CANONICAL).data.sort_values("available_from")
    joint = asof_join(
        decisions, right, "entity_id", "decision_date", "available_from", allow_exact_matches=False
    )
    assert joint["eps"].isna().all()


def test_asof_join_aligne_deux_resolutions() -> None:
    """Source (a) : une colonne en secondes et une en nanosecondes décrivent les mêmes instants."""
    decisions = DECISIONS.copy()
    decisions["decision_date"] = decisions["decision_date"].astype("datetime64[s]")
    right = PITFrame(CANONICAL).data.sort_values("available_from")
    joint = asof_join(decisions, right, "entity_id", "decision_date", "available_from")
    assert joint["eps"].tolist() == [1.10, 1.25]


def test_asof_join_direction_inconnue_refusee() -> None:
    """Source (a) : « sideways » n'est pas une direction de merge_asof."""
    right = PITFrame(CANONICAL).data.sort_values("available_from")
    with pytest.raises(ConfigError, match="direction"):
        asof_join(DECISIONS, right, "entity_id", "decision_date", "available_from", direction="sideways")  # type: ignore[arg-type]


def test_le_join_naif_sur_la_periode_donne_quarante_cinq_jours_d_avance() -> None:
    """Source (a) : c'est la démonstration du biais, chiffrée sur le cas canonique.

    Un appariement sur ``period_end`` donne au portefeuille du 31 mars le
    bénéfice publié le 15 mai, soit 45 jours d'information gratuite. Le contrôle
    du module le détecte, la jointure naïve ne le voit pas.
    """
    naif = DECISIONS.assign(decision_date=pd.to_datetime(["2015-03-31", "2015-06-30"])).merge(
        PITFrame(CANONICAL).data, left_on=["entity_id", "decision_date"], right_on=["entity_id", "period_end"]
    )
    # Deux lignes appariées alors qu'aucune n'était connaissable, comptées à la main.
    assert len(naif) == 2
    report = lookahead_report(naif, "decision_date")
    assert report.n_violations == 2
    assert report.max_gap_days == pytest.approx(45.0)


# --------------------------------------------------------------------------- #
# Propriétés                                                                   #
# --------------------------------------------------------------------------- #

BASE = pd.Timestamp("2015-01-01")

pit_records = st.lists(
    st.tuples(
        st.sampled_from(["AAA", "BBB", "CCC"]),
        st.integers(min_value=0, max_value=400),
        st.integers(min_value=0, max_value=200),
        st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False),
    ),
    min_size=0,
    max_size=25,
)


def frame_from(records: list[tuple[str, int, int, float]]) -> pd.DataFrame:
    """Rend un registre valide depuis des décalages en jours, disponibilité toujours postérieure."""
    periods = [BASE + pd.Timedelta(days=offset) for _, offset, _, _ in records]
    available = [
        period + pd.Timedelta(days=lag) for period, (_, _, lag, _) in zip(periods, records, strict=True)
    ]
    return pd.DataFrame(
        {
            "entity_id": pd.Series([row[0] for row in records], dtype="object"),
            "period_end": pd.Series(periods, dtype="datetime64[ns]"),
            "available_from": pd.Series(available, dtype="datetime64[ns]"),
            "eps": pd.Series([row[3] for row in records], dtype="float64"),
        }
    )


@given(records=pit_records, query=st.integers(min_value=-50, max_value=700))
@settings(max_examples=200, deadline=None)
def test_propriete_toute_ligne_rendue_etait_disponible(
    records: list[tuple[str, int, int, float]], query: int
) -> None:
    """Source (b) : l'invariant du module, ``available_from <= d`` pour toute ligne rendue.

    La propriété se vérifie sur toute date, y compris antérieure au registre, et
    sur tout registre, y compris vide. Elle entraîne un corollaire testé ici
    aussi : la fin de période est elle aussi antérieure à la date de décision,
    puisque le constructeur garantit ``period_end <= available_from``.
    """
    date = BASE + pd.Timedelta(days=query)
    visible = PITFrame(frame_from(records)).as_of(date)
    assert (visible["available_from"] <= date).all()
    assert (visible["period_end"] <= date).all()


@given(
    records=pit_records,
    first=st.integers(min_value=-50, max_value=700),
    gap=st.integers(min_value=0, max_value=400),
)
@settings(max_examples=100, deadline=None)
def test_propriete_la_visibilite_ne_recule_jamais(
    records: list[tuple[str, int, int, float]], first: int, gap: int
) -> None:
    """Source (b) : l'ensemble des couples entité et période visibles croît avec la date.

    Une information connaissable un jour le reste toujours. La correction d'un
    chiffre change sa valeur, jamais l'existence de la période dans le registre.
    """
    pit = PITFrame(frame_from(records))
    early = pit.as_of(BASE + pd.Timedelta(days=first))
    late = pit.as_of(BASE + pd.Timedelta(days=first + gap))
    keys_early = set(zip(early["entity_id"], early["period_end"], strict=True))
    keys_late = set(zip(late["entity_id"], late["period_end"], strict=True))
    assert keys_early <= keys_late


@given(records=pit_records, query=st.integers(min_value=-50, max_value=700))
@settings(max_examples=100, deadline=None)
def test_propriete_une_ligne_par_couple_entite_periode(
    records: list[tuple[str, int, int, float]], query: int
) -> None:
    """Source (b) : identité de comptage, ``as_of`` rend exactement un état par couple visible."""
    date = BASE + pd.Timedelta(days=query)
    frame = frame_from(records)
    visible = PITFrame(frame).as_of(date)
    expected_keys = {
        (row.entity_id, row.period_end) for row in frame.itertuples() if row.available_from <= date
    }
    assert len(visible) == len(expected_keys)


@given(
    records=st.lists(
        st.tuples(
            st.sampled_from(["AAA", "BBB"]),
            st.integers(min_value=0, max_value=100),
            st.integers(min_value=-30, max_value=30),
        ),
        min_size=1,
        max_size=10,
    )
)
@settings(max_examples=200, deadline=None)
def test_propriete_le_constructeur_refuse_exactement_les_lags_negatifs(
    records: list[tuple[str, int, int]],
) -> None:
    """Source (b) : équivalence logique, le constructeur lève si et seulement si un décalage est négatif."""
    quadruples = [(entity, offset, lag, 0.0) for entity, offset, lag in records]
    frame = frame_from(quadruples)  # type: ignore[arg-type]
    has_negative = any(lag < 0 for _, _, lag in records)
    if has_negative:
        with pytest.raises(LookAheadError):
            PITFrame(frame)
    else:
        assert len(PITFrame(frame)) == len(records)


@given(records=pit_records, query=st.integers(min_value=-50, max_value=700))
@settings(max_examples=100, deadline=None)
def test_propriete_le_panneau_ne_fuit_jamais(records: list[tuple[str, int, int, float]], query: int) -> None:
    """Source (b) : par construction, un panneau passe toujours le contrôle anti-fuite."""
    dates = [BASE + pd.Timedelta(days=query), BASE + pd.Timedelta(days=query + 90)]
    panel = PITFrame(frame_from(records)).panel(dates)
    assert assert_no_lookahead(panel, AS_OF_COLUMN).clean


# --------------------------------------------------------------------------- #
# Les trous trouvés par la vérification adversariale du 2026-09-01             #
# --------------------------------------------------------------------------- #


def test_colonne_de_dates_entiere_en_dtype_object_refusee() -> None:
    """Source (a) : 20150331 lu en nanosecondes donne 1970-01-01, calculé à la main.

    Le contrôle du dtype seul laissait passer une colonne ``object`` remplie
    d'entiers. Le calcul que faisait alors ``pd.to_datetime`` est écrit ici :
    20 150 331 nanosecondes après le 1er janvier 1970 tombent le 1er janvier
    1970 à 0,020150331 seconde. Les deux dates gardaient leur ordre, le registre
    était accepté, et tout devenait visible à toute date.
    """
    poison = build([("AAA", "2015-03-31", "2015-05-15", 1.10)])
    poison["period_end"] = pd.Series([20150331], dtype="object")
    poison["available_from"] = pd.Series([20150515], dtype="object")
    with pytest.raises(DataQualityError, match="nombres"):
        PITFrame(poison)


def test_colonne_de_dates_flottante_en_dtype_object_refusee() -> None:
    """Source (a) : 1,4e18 nanosecondes valent 1,4e9 secondes, soit mai 2014, pas mars 2015."""
    poison = build([("AAA", "2015-03-31", "2015-05-15", 1.10)])
    poison["period_end"] = pd.Series([1.4e18], dtype="object")
    poison["available_from"] = pd.Series([1.5e18], dtype="object")
    with pytest.raises(DataQualityError, match="nombres"):
        PITFrame(poison)


def test_colonne_de_dates_mixte_refusee() -> None:
    """Source (a) : une colonne moitié entiers moitié chaînes lirait une moitié en nanosecondes."""
    poison = build([("AAA", "2015-03-31", "2015-05-15", 1.10), ("AAA", "2015-06-30", "2015-08-14", 1.25)])
    poison["available_from"] = pd.Series([20150515, "2015-08-14"], dtype="object")
    with pytest.raises(DataQualityError, match="nombres"):
        PITFrame(poison)


def test_les_dates_ecrites_en_chaine_restent_acceptees() -> None:
    """Source (a) : le durcissement ne doit pas refuser une colonne de chaînes ISO, cas normal."""
    pit = PITFrame(build([("AAA", "2015-03-31", "2015-05-15", 1.10)]))
    assert len(pit.as_of("2015-05-15")) == 1


def test_as_of_et_lookahead_report_s_accordent_sur_deux_fuseaux_explicites() -> None:
    """Source (b) : identité entre deux entrées du module sur le même registre et le même instant.

    Le dépôt est daté du 15 mai 2015 à midi UTC. La décision est prise le
    15 mai 2015 à 8 h à New York, soit 12 h UTC, donc le MÊME instant. Les deux
    entrées doivent donc conclure la même chose, ``as_of`` en rendant la ligne
    et ``lookahead_report`` en ne comptant aucune fuite. Un désaccord signale
    que l'une des deux compare autre chose que des instants absolus.
    """
    aware = pd.DataFrame(
        {
            "entity_id": ["AAA"],
            "period_end": pd.to_datetime(["2015-03-31 12:00"]).tz_localize("UTC"),
            "available_from": pd.to_datetime(["2015-05-15 12:00"]).tz_localize("UTC"),
            "eps": [1.10],
        }
    )
    decision = pd.Timestamp("2015-05-15 08:00", tz="America/New_York")
    pit = PITFrame(aware)
    assert len(pit.as_of(decision)) == 1
    assert lookahead_report(pit, decision).clean


def test_le_melange_naif_et_localise_reste_refuse_par_le_rapport() -> None:
    """Source (a) : sans fuseau déclaré, la comparaison exigerait d'en supposer un."""
    aware = pd.DataFrame(
        {
            "entity_id": ["AAA"],
            "period_end": pd.to_datetime(["2015-03-31"]).tz_localize("UTC"),
            "available_from": pd.to_datetime(["2015-05-15"]).tz_localize("UTC"),
        }
    )
    with pytest.raises(DataQualityError, match="naïve"):
        lookahead_report(aware, pd.Series(pd.to_datetime(["2015-06-30"]), index=aware.index))


def test_la_frontiere_de_as_of_est_large_et_c_est_ecrit() -> None:
    """Source (a) : la règle documentée est ``available_from <= date``, testée aux deux bords.

    Le dépôt du 15 mai à 16 h 30 n'est pas lisible par une décision datée du
    15 mai à minuit, puisque 16 h 30 suit minuit. Le même dépôt tronqué au jour
    l'est, puisque minuit égale minuit. C'est le coin d'ombre décrit dans la
    docstring de ``as_of``, et il est épinglé ici pour qu'aucune modification ne
    le déplace en silence.
    """
    intraday = pd.DataFrame(
        {
            "entity_id": ["AAA"],
            "period_end": ["2015-03-31"],
            "available_from": ["2015-05-15 16:30:00"],
            "eps": [1.10],
        }
    )
    assert len(PITFrame(intraday).as_of("2015-05-15")) == 0
    assert len(PITFrame(intraday).as_of("2015-05-15 16:30:00")) == 1
    tronque = build([("AAA", "2015-03-31", "2015-05-15", 1.10)])
    assert len(PITFrame(tronque).as_of("2015-05-15")) == 1
    # La veille reste refusée dans les deux cas : la règle n'est large qu'à l'égalité.
    assert len(PITFrame(tronque).as_of("2015-05-14")) == 0

"""Le test canonique de fuite temporelle, et ses variantes.

**Le cas de référence.** Un rapport financier accepté par la SEC le 15 mai 2015
décrit le trimestre clos le 31 mars 2015. Une décision de portefeuille prise le
31 mars 2015 ne peut pas s'en servir. Le pipeline doit refuser l'accès, et non
rendre la donnée avec un avertissement.

**Pourquoi ce test est particulier.** Une fuite ne provoque aucune erreur. Le
code tourne, les colonnes sont justes, le ratio de Sharpe est excellent, et le
résultat est faux. Aucun test de valeur ne l'attrape ; seul un test de propriété
sur les dates y parvient.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from quantlab.core.errors import LookAheadError
from quantlab.data.point_in_time import (
    AS_OF_COLUMN,
    AVAILABLE_FROM_COLUMN,
    PITFrame,
    asof_join,
    assert_no_lookahead,
    lookahead_report,
)

#: La date de dépôt du cas canonique.
DEPOT = dt.date(2015, 5, 15)
#: La date de décision du cas canonique, antérieure au dépôt.
DECISION = dt.date(2015, 3, 31)


def _cas_canonique() -> pd.DataFrame:
    """Rend le tableau du cas de référence, avec sa correction de comptes.

    Trois lignes, dont deux décrivent le même trimestre. La seconde corrige la
    première le 2015-08-20, ce qui permet de vérifier que ``as_of`` rend
    l'ancienne valeur avant la correction et la nouvelle après.
    """
    return pd.DataFrame(
        {
            "entity_id": ["ACME", "ACME", "ACME"],
            "period_end": pd.to_datetime(["2015-03-31", "2015-03-31", "2015-06-30"]),
            "filing_date": pd.to_datetime(["2015-05-15", "2015-08-20", "2015-08-05"]),
            "available_from": pd.to_datetime(["2015-05-15", "2015-08-20", "2015-08-05"]),
            "assets": [100.0, 95.0, 110.0],
        }
    )


def test_le_depot_du_15_mai_est_inaccessible_le_31_mars() -> None:
    """Le cas canonique. Ce test ne se désactive jamais.

    La donnée du trimestre clos le 31 mars est déposée le 15 mai. Au 31 mars,
    ``as_of`` doit rendre un tableau VIDE, et non la ligne avec un
    avertissement : un avertissement se lit après coup, une ligne absente
    s'impose au calcul.
    """
    frame = PITFrame(_cas_canonique())
    vue = frame.as_of(DECISION)
    assert vue.empty, f"de l'information future a été rendue : le dépôt du {DEPOT} est visible au {DECISION}"


def test_la_correction_de_comptes_n_est_pas_connue_avant_sa_date() -> None:
    """Avant le 2015-08-20, le premier trimestre vaut 100 et non 95.

    Un module qui ne garderait que la dernière valeur connue rendrait 95 dès le
    1er juin, donc ferait connaître une correction trois mois avant qu'elle
    existe. Ce test est ce qui l'interdit.
    """
    frame = PITFrame(_cas_canonique())

    avant = frame.as_of("2015-06-01")
    assert len(avant) == 1
    assert float(avant["assets"].iloc[0]) == 100.0

    apres = frame.as_of("2015-09-01")
    ligne_q1 = apres[apres["period_end"] == pd.Timestamp("2015-03-31")]
    assert float(ligne_q1["assets"].iloc[0]) == 95.0


def test_une_disponibilite_anterieure_a_la_periode_est_refusee() -> None:
    """Une donnée connaissable avant la fin de la période qu'elle décrit est un bogue.

    Le cas se produit pour de vrai lorsqu'un chargeur confond ``period_end`` et
    ``filing_date``. Le constructeur doit lever, pas corriger en silence.
    """
    fautif = _cas_canonique()
    fautif.loc[0, "available_from"] = pd.Timestamp("2015-01-15")
    with pytest.raises(LookAheadError):
        PITFrame(fautif)


def test_le_panel_de_rebalancement_ne_fuit_sur_aucune_date() -> None:
    """Un panel empilé sur douze dates de rééquilibrage ne fuit sur aucune.

    C'est la forme sous laquelle les caractéristiques entrent réellement dans
    une étude : une ligne par entité et par date de décision. Le test vérifie
    la propriété sur toutes les dates à la fois.
    """
    frame = PITFrame(_cas_canonique())
    dates = pd.date_range("2015-01-31", periods=12, freq="ME")
    panel = frame.panel(dates)
    if panel.empty:
        pytest.skip("le panel est vide sur cette fenêtre, rien à vérifier")
    fuites = panel[panel[AVAILABLE_FROM_COLUMN] > panel[AS_OF_COLUMN]]
    assert fuites.empty, f"{len(fuites)} lignes connues avant leur disponibilité"


def test_la_garde_compte_les_violations_au_lieu_de_les_taire() -> None:
    """La garde chiffre la fuite avant de lever, et lève bien quand il y en a une.

    Deux comportements sont vérifiés. Sur le tableau complet vu au 31 mars 2015,
    les trois lignes sont dans le futur, donc ``assert_no_lookahead`` lève et
    ``lookahead_report`` compte trois violations avec un écart maximal de
    142 jours, calculé à la main : du 31 mars au 20 août 2015, il y a bien
    142 jours. Vu au 31 décembre 2015, tout est disponible et le rapport est
    propre.
    """
    frame = PITFrame(_cas_canonique())

    rapport = lookahead_report(frame, DECISION)
    assert rapport.n_violations == 3
    assert rapport.max_gap_days == pytest.approx(142.0)
    with pytest.raises(LookAheadError):
        assert_no_lookahead(frame, decision_dates=DECISION)

    propre = assert_no_lookahead(frame, decision_dates="2015-12-31")
    assert propre.n_violations == 0


def test_la_jointure_temporelle_refuse_de_regarder_devant() -> None:
    """``asof_join`` en direction « forward » exige un consentement explicite.

    Une jointure vers l'avant est parfois légitime, par exemple pour attacher à
    chaque dépôt le rendement qui a suivi. Elle n'est jamais légitime par
    défaut, et l'argument ``allow_lookahead`` oblige à l'écrire.
    """
    gauche = pd.DataFrame(
        {
            "entity_id": ["ACME"],
            "decision_date": pd.to_datetime(["2015-03-31"]),
        }
    )
    droite = _cas_canonique()
    with pytest.raises((LookAheadError, ValueError)):
        asof_join(
            gauche,
            droite,
            on="entity_id",
            left_time="decision_date",
            right_time="available_from",
            direction="forward",
        )


@settings(max_examples=100, deadline=None)
@given(
    decalage_jours=st.integers(min_value=-400, max_value=400),
)
def test_propriete_aucune_ligne_rendue_n_etait_indisponible(decalage_jours: int) -> None:
    """Pour toute date de décision, toute ligne rendue était déjà disponible.

    C'est la propriété qui définit le point-in-time, et elle vaut pour toute
    date, pas seulement pour celles auxquelles on a pensé. Hypothesis balaie
    plus de huit cents jours autour du cas canonique.
    """
    frame = PITFrame(_cas_canonique())
    date = pd.Timestamp("2015-05-15") + pd.Timedelta(days=decalage_jours)
    vue = frame.as_of(date)
    if vue.empty:
        return
    assert (vue["available_from"] <= date).all(), (
        f"au {date.date()}, une ligne disponible plus tard a été rendue"
    )

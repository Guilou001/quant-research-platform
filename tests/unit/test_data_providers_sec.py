"""Tests du fournisseur SEC, tous hors réseau sauf deux, marqués « network ».

Règle tenue ici : aucune valeur attendue ne vient de la sortie du code. Chaque
assertion porte en commentaire la source de sa valeur, parmi
(a) un calcul à la main, chiffres visibles,
(b) une identité mathématique,
(c) une valeur publiée par la source elle-même, citée avec sa date de mesure,
(d) une implémentation indépendante.

Les extraits JSON et texte recopiés plus bas sont des octets réels de la SEC,
relevés le 2026-09-01 sur les trois adresses citées en tête du module testé.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

import pandas as pd
import pytest
from hypothesis import given
from hypothesis import settings as hyp_settings
from hypothesis import strategies as st

from quantlab.core.calendars import get_calendar
from quantlab.core.config import Settings
from quantlab.core.errors import ConfigError, DataQualityError, LookAheadError
from quantlab.core.protocols import DataProvider, PointInTimeDataset
from quantlab.data.providers.base import HttpClient
from quantlab.data.providers.sec import (
    AVAILABILITY_RULE,
    KNOWN_LIMITATIONS,
    MAX_REQUESTS_PER_SECOND,
    MIN_REQUEST_DELAY_S,
    PIT_SCHEMA,
    PointInTimeFundamentals,
    SecProvider,
    as_of,
    assert_no_lookahead,
    company_concept_url,
    company_facts_url,
    empty_pit_frame,
    full_index_url,
    normalize_cik,
    parse_acceptance,
    parse_company_tickers,
    parse_master_index,
    polite_delay_s,
    submissions_url,
    to_point_in_time,
)

# ---------------------------------------------------------------------------
# Données de référence, recopiées de la SEC le 2026-09-01. Source (c).
# ---------------------------------------------------------------------------

#: Les quatre déclarations de « us-gaap:Assets » d'Apple pour la période close le
#: 27 septembre 2008, recopiées telles quelles depuis
#: https://data.sec.gov/api/xbrl/companyconcept/CIK0000320193/us-gaap/Assets.json
#: mesurée en réponse 200 le 2026-09-01. Deux valeurs distinctes s'y succèdent,
#: 39 572 000 000 dollars puis 36 171 000 000 après le 10-K/A. Source (c).
APPLE_2008_RECORDS: list[dict[str, Any]] = [
    {
        "end": "2008-09-27",
        "val": 39572000000,
        "accn": "0001193125-09-153165",
        "fy": 2009,
        "fp": "Q3",
        "form": "10-Q",
        "filed": "2009-07-22",
    },
    {
        "end": "2008-09-27",
        "val": 39572000000,
        "accn": "0001193125-09-214859",
        "fy": 2009,
        "fp": "FY",
        "form": "10-K",
        "filed": "2009-10-27",
    },
    {
        "end": "2008-09-27",
        "val": 36171000000,
        "accn": "0001193125-10-012091",
        "fy": 2009,
        "fp": "FY",
        "form": "10-K/A",
        "filed": "2010-01-25",
    },
    {
        "end": "2008-09-27",
        "val": 36171000000,
        "accn": "0001193125-10-238044",
        "fy": 2010,
        "fp": "FY",
        "form": "10-K",
        "filed": "2010-10-27",
        "frame": "CY2008Q3I",
    },
]

#: Le cas canonique de fuite du laboratoire, écrit à la main : un trimestre clos
#: le 31 mars 2015, déposé le 15 mai 2015, redéclaré le 6 novembre 2015 avec une
#: valeur plus basse. Source (a).
LEAK_RECORDS: list[dict[str, Any]] = [
    {
        "end": "2015-03-31",
        "val": 1000.0,
        "accn": "0000000000-15-000001",
        "fy": 2015,
        "fp": "Q1",
        "form": "10-Q",
        "filed": "2015-05-15",
    },
    {
        "end": "2015-03-31",
        "val": 900.0,
        "accn": "0000000000-15-000002",
        "fy": 2015,
        "fp": "Q3",
        "form": "10-Q/A",
        "filed": "2015-11-06",
    },
]

#: Un extrait de https://www.sec.gov/Archives/edgar/full-index/2015/QTR2/master.idx
#: mesuré en réponse 200 le 2026-09-01, en-tête compris. Source (c).
MASTER_INDEX_EXTRACT = """Description:           Master Index of EDGAR Dissemination Feed
Last Data Received:    June 30, 2015
Comments:              webmaster@sec.gov
Anonymous FTP:         ftp://ftp.sec.gov/edgar/
Cloud HTTP:            https://www.sec.gov/Archives/




CIK|Company Name|Form Type|Date Filed|Filename
--------------------------------------------------------------------------------
1000032|BINCH JAMES G|4|2015-06-02|edgar/data/1000032/0001209191-15-049043.txt
1000045|NICHOLAS FINANCIAL INC|10-K|2015-06-15|edgar/data/1000045/0001193125-15-223218.txt
1000045|NICHOLAS FINANCIAL INC|4/A|2015-05-14|edgar/data/1000045/0001140361-15-019826.txt
"""

#: Les quatre premières entrées de https://www.sec.gov/files/company_tickers.json
#: mesurées le 2026-09-01. Source (c).
COMPANY_TICKERS_EXTRACT: dict[str, Any] = {
    "0": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA CORP"},
    "1": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "2": {"cik_str": 1652044, "ticker": "GOOGL", "title": "Alphabet Inc."},
    "3": {"cik_str": 789019, "ticker": "MSFT", "title": "MICROSOFT CORP"},
}

#: Un extrait de https://data.sec.gov/submissions/CIK0000320193.json mesuré le
#: 2026-09-01, réduit à deux dépôts. Source (c).
SUBMISSIONS_EXTRACT: dict[str, Any] = {
    "cik": "320193",
    "name": "Apple Inc.",
    "filings": {
        "recent": {
            "accessionNumber": ["0001140361-26-034741", "0001140361-26-033928"],
            "filingDate": ["2026-08-27", "2026-08-20"],
            "acceptanceDateTime": ["2026-08-27T22:30:30.000Z", "2026-08-20T22:30:16.000Z"],
            "form": ["4", "4"],
        },
        "files": [],
    },
}

#: L'identification exigée par la SEC, sans adresse personnelle.
GOOD_AGENT = "quantlab research (chercheur@exemple.ca)"


# ---------------------------------------------------------------------------
# Fabriques et doublures
# ---------------------------------------------------------------------------


def concept_payload(records: list[dict[str, Any]], *, tag: str = "Assets") -> dict[str, Any]:
    """Rend un JSON de la forme « companyconcept » autour des enregistrements."""
    return {
        "cik": 320193,
        "taxonomy": "us-gaap",
        "tag": tag,
        "label": tag,
        "entityName": "Apple Inc.",
        "units": {"USD": list(records)},
    }


def facts_payload(records: list[dict[str, Any]], *, tag: str = "Assets") -> dict[str, Any]:
    """Rend un JSON de la forme « companyfacts » autour des enregistrements."""
    return {
        "cik": 320193,
        "entityName": "Apple Inc.",
        "facts": {"us-gaap": {tag: {"label": tag, "units": {"USD": list(records)}}}},
    }


class FakeResponse:
    """La forme minimale qu'un client HTTP attend d'une réponse."""

    def __init__(self, content: bytes, url: str = "https://data.sec.gov/x") -> None:
        self.status_code = 200
        self.content = content
        self.headers: dict[str, str] = {}
        self.url = url


class FakeSession:
    """Session factice : rend les réponses données, la dernière se répétant."""

    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, *, params: Any = None, headers: Any = None, timeout: Any = None) -> Any:
        self.calls.append({"url": url, "headers": headers})
        return self._responses.pop(0) if len(self._responses) > 1 else self._responses[0]

    def close(self) -> None:
        return None


def make_provider(payloads: list[Any], tmp_path: Any, **kwargs: Any) -> tuple[SecProvider, FakeSession]:
    """Rend un fournisseur branché sur une session factice et un cache temporaire."""
    responses = [FakeResponse(p if isinstance(p, bytes) else json.dumps(p).encode("utf-8")) for p in payloads]
    session = FakeSession(responses)
    settings = Settings(user_agent=GOOD_AGENT, request_delay_s=0.0, max_retries=1, log_level="INFO")
    client = HttpClient(settings=settings, session=session, require_email_contact=True)
    return SecProvider(client=client, raw_root=tmp_path, **kwargs), session


# ---------------------------------------------------------------------------
# Identifiants et adresses
# ---------------------------------------------------------------------------


def test_normalize_cik_rend_dix_chiffres() -> None:
    """Les trois écritures du même déposant se rejoignent. Source (a)."""
    # Apple porte l'identifiant 320193 ; complété à dix chiffres, cela fait
    # 0000320193, soit quatre zéros puis les six chiffres. Calcul à la main.
    assert normalize_cik(320193) == "0000320193"
    assert normalize_cik("320193") == "0000320193"
    assert normalize_cik("CIK0000320193") == "0000320193"
    assert normalize_cik("0000320193") == "0000320193"


def test_normalize_cik_refuse_le_vide_et_le_trop_long() -> None:
    """Une entrée sans chiffre ou de onze chiffres lève. Source (a)."""
    with pytest.raises(ValueError, match="aucun chiffre"):
        normalize_cik("APPLE")
    # 12345678901 porte onze chiffres, un de plus que la largeur de la SEC.
    with pytest.raises(ValueError, match="10 chiffres"):
        normalize_cik("12345678901")


def test_normalize_cik_ne_fabrique_pas_un_autre_deposant_depuis_un_flottant() -> None:
    """Un flottant entier vaut l'entier, un flottant décimal lève. Source (a)."""
    # Calcul à la main : pandas rend une colonne d'entiers en float64 dès qu'elle
    # porte une valeur manquante, donc 320193 arrive écrit « 320193.0 ». Récolter
    # ses chiffres donne 3201930, soit sept chiffres et donc l'identifiant
    # 0003201930, qui n'est pas celui d'Apple. La valeur attendue est celle de
    # l'entier, 0000320193, quatre zéros puis les six chiffres.
    assert normalize_cik(320193.0) == "0000320193"
    assert normalize_cik(320193.0) == normalize_cik(320193)
    # Un flottant à partie décimale n'est aucun identifiant, il lève.
    with pytest.raises(ValueError, match="flottant"):
        normalize_cik(320193.5)
    # L'écriture décimale d'un flottant est refusée aussi, plutôt que récoltée.
    with pytest.raises(ValueError, match="ne s'écrit pas"):
        normalize_cik("320193.0")
    # Un identifiant est positif : -320193 ne vaut pas 0000320193.
    with pytest.raises(ValueError, match="positif"):
        normalize_cik(-320193)


def test_les_adresses_sont_celles_mesurees_le_2026_09_01() -> None:
    """Les trois adresses qui répondent 200 sont reconstruites. Source (c)."""
    assert (
        company_concept_url(320193, "us-gaap", "Assets")
        == "https://data.sec.gov/api/xbrl/companyconcept/CIK0000320193/us-gaap/Assets.json"
    )
    assert submissions_url(320193) == "https://data.sec.gov/submissions/CIK0000320193.json"
    assert full_index_url(2015, 2) == "https://www.sec.gov/Archives/edgar/full-index/2015/QTR2/master.idx"
    assert (
        company_facts_url("CIK0000320193") == "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json"
    )


def test_full_index_url_refuse_un_trimestre_et_une_annee_impossibles() -> None:
    """Le trimestre 5 et l'année 1992 lèvent. Source (a)."""
    with pytest.raises(ValueError, match="trimestre"):
        full_index_url(2015, 5)
    with pytest.raises(ValueError, match="1993"):
        full_index_url(1992, 1)


def test_polite_delay_s_tient_la_limite_annoncee_par_la_sec() -> None:
    """Dix requêtes par seconde font un dixième de seconde de pause. Source (a) et (c)."""
    # La SEC annonce 10 requêtes par seconde. 1 / 10 = 0,1 seconde, calcul à la main.
    plancher = MIN_REQUEST_DELAY_S
    assert plancher == pytest.approx(1.0 / MAX_REQUESTS_PER_SECOND)
    assert plancher == pytest.approx(0.1)
    # Une configuration à zéro est relevée au plancher, une plus lente est gardée.
    assert polite_delay_s(0.0) == pytest.approx(0.1)
    assert polite_delay_s(0.05) == pytest.approx(0.1)
    assert polite_delay_s(0.5) == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Le cœur : la table point-in-time
# ---------------------------------------------------------------------------


def test_deux_declarations_du_meme_trimestre_sont_toutes_les_deux_gardees() -> None:
    """Le tableau garde les deux dépôts du même trimestre. Source (c)."""
    pit = to_point_in_time(concept_payload(APPLE_2008_RECORDS[:2]))
    # Les deux enregistrements portent la même période, 2008-09-27, et deux dates
    # de dépôt, 2009-07-22 et 2009-10-27. Le tableau doit donc porter deux lignes.
    assert len(pit) == 2
    assert set(pit["period_end"]) == {pd.Timestamp("2008-09-27")}
    assert sorted(pit["filing_date"].dt.date.astype(str)) == ["2009-07-22", "2009-10-27"]
    # Une seule des deux est la déclaration d'origine, l'autre est une redéclaration.
    assert list(pit["is_restatement"]) == [False, True]


def test_available_from_vaut_la_date_de_depot_et_jamais_la_fin_de_periode() -> None:
    """La règle d'utilisabilité tient sur toutes les lignes. Source (b)."""
    pit = to_point_in_time(concept_payload(APPLE_2008_RECORDS))
    # Identité de construction avec un décalage nul : available_from = filing_date.
    assert (pit["available_from"] == pit["filing_date"]).all()
    # Et jamais la fin de période, qui précède strictement le dépôt ici.
    assert (pit["available_from"] != pit["period_end"]).all()
    assert (pit["available_from"] > pit["period_end"]).all()
    assert "period_end" in AVAILABILITY_RULE  # la règle documentée dit le « jamais »


def test_as_of_avant_le_depot_ne_rend_rien() -> None:
    """Une date antérieure à tout dépôt rend un tableau vide. Source (a)."""
    pit = to_point_in_time(concept_payload(APPLE_2008_RECORDS[:2]))
    # Le premier dépôt date du 2009-07-22. La veille, rien n'est public.
    assert as_of(pit, "2009-07-21").empty
    # Le jour même, la première déclaration l'est.
    assert len(as_of(pit, "2009-07-22")) == 1


def test_as_of_choisit_la_derniere_declaration_connue() -> None:
    """La valeur rendue change quand la redéclaration devient publique. Source (c)."""
    pit = to_point_in_time(concept_payload(APPLE_2008_RECORDS))
    # Au 2009-12-31, seuls les dépôts du 22 juillet et du 27 octobre 2009 sont
    # publics, et tous deux annoncent 39 572 000 000 dollars.
    connu = as_of(pit, "2009-12-31")
    assert list(connu["value"]) == [39572000000.0]
    # Au 2010-06-30, le 10-K/A du 25 janvier 2010 a corrigé le chiffre à
    # 36 171 000 000 dollars. L'écart vaut 3 401 000 000 dollars.
    corrige = as_of(pit, "2010-06-30")
    assert list(corrige["value"]) == [36171000000.0]
    assert connu.loc[0, "value"] - corrige.loc[0, "value"] == pytest.approx(3.401e9)


def test_garde_toutes_les_revisions_deja_publiques_sur_demande() -> None:
    """Le mode « toutes révisions » rend une ligne par dépôt déjà public. Source (a)."""
    pit = to_point_in_time(concept_payload(APPLE_2008_RECORDS))
    # Au 2010-06-30, trois des quatre dépôts sont publics : 2009-07-22,
    # 2009-10-27 et 2010-01-25. Le quatrième est du 2010-10-27.
    toutes = as_of(pit, "2010-06-30", keep_all_revisions=True)
    assert len(toutes) == 3


def test_fuite_canonique_le_depot_de_mai_est_invisible_en_mars() -> None:
    """Le contrôle anti-fuite du laboratoire : mai n'est pas connaissable en mars. Source (a)."""
    pit = to_point_in_time(concept_payload(LEAK_RECORDS))
    # Le dépôt est du 2015-05-15, la date de portefeuille du 2015-03-31, soit
    # 45 jours avant. Rien ne doit sortir.
    assert as_of(pit, "2015-03-31").empty
    assert as_of(pit, dt.date(2015, 3, 31)).empty
    # La veille du dépôt non plus.
    assert as_of(pit, "2015-05-14").empty
    # Le jour du dépôt, la valeur d'origine sort, et elle seule.
    assert list(as_of(pit, "2015-05-15")["value"]) == [1000.0]
    # Après la correction du 2015-11-06, c'est la valeur corrigée.
    assert list(as_of(pit, "2015-12-31")["value"]) == [900.0]


def test_le_decalage_dun_jour_ouvre_pousse_au_lundi_suivant() -> None:
    """Un dépôt du vendredi devient utilisable le lundi. Source (a) et (d)."""
    pit = to_point_in_time(concept_payload(LEAK_RECORDS), availability_lag_business_days=1)
    # Le 2015-05-15 est un vendredi ; la séance suivante de la Bourse de New York
    # est le lundi 2015-05-18, le seul jour férié de mai 2015 étant le Memorial
    # Day du 25 mai. Le calendrier vient de exchange_calendars, source (d).
    premier = pit.loc[pit["filing_date"] == pd.Timestamp("2015-05-15")]
    assert list(premier["available_from"]) == [pd.Timestamp("2015-05-18")]
    # Conséquence directe : le vendredi du dépôt, l'information n'est plus utilisable.
    assert as_of(pit, "2015-05-15").empty
    assert list(as_of(pit, "2015-05-18")["value"]) == [1000.0]


def test_le_decalage_marche_aussi_quand_le_depot_tombe_hors_seance() -> None:
    """EDGAR reçoit hors séance, et le décalage doit quand même aboutir. Source (a) et (d)."""
    # Mesuré le 2026-09-01 sur l'index réel du deuxième trimestre 2015 : 3 542 des
    # 260 019 dépôts tombent un jour sans séance, le Vendredi saint du 2015-04-03
    # et le samedi 2015-04-25. Les deux cas doivent aboutir, pas lever.
    #
    # Calcul à la main. Le 2015-04-03 est un Vendredi saint, la Bourse de New York
    # est fermée ; la séance suivante est le lundi 2015-04-06. Le 2015-04-25 est un
    # samedi ; la séance suivante est le lundi 2015-04-27.
    attendus = {"2015-04-03": pd.Timestamp("2015-04-06"), "2015-04-25": pd.Timestamp("2015-04-27")}
    for depot, attendu in attendus.items():
        payload = concept_payload(
            [{"end": "2014-12-31", "val": 1.0, "accn": "x", "form": "10-K", "filed": depot}]
        )
        pit = to_point_in_time(payload, availability_lag_business_days=1)
        assert pit.loc[0, "available_from"] == attendu
    # Source (d) : le calendrier de exchange_calendars confirme que ces deux jours
    # ne sont pas des séances, et que les deux lundis en sont.
    calendrier = get_calendar("XNYS")
    seances = set(calendrier.sessions)
    assert pd.Timestamp("2015-04-03") not in seances
    assert pd.Timestamp("2015-04-25") not in seances
    assert {pd.Timestamp("2015-04-06"), pd.Timestamp("2015-04-27")} <= seances


def test_le_decalage_de_deux_seances_saute_le_ferie() -> None:
    """Deux séances après un vendredi de veille de férié tombent le mardi. Source (a) et (d)."""
    # Calcul à la main. Le 2015-05-22 est un vendredi, et le lundi 2015-05-25 est
    # le Memorial Day, jour où la Bourse est fermée. La première séance suivante
    # est donc le mardi 2015-05-26, et la deuxième le mercredi 2015-05-27.
    payload = concept_payload(
        [{"end": "2015-03-31", "val": 1.0, "accn": "x", "form": "10-Q", "filed": "2015-05-22"}]
    )
    pit = to_point_in_time(payload, availability_lag_business_days=2)
    assert pit.loc[0, "available_from"] == pd.Timestamp("2015-05-27")
    # Source (d) : la même date obtenue en composant deux fois « next_session ».
    calendrier = get_calendar("XNYS")
    independant = calendrier.next_session(calendrier.next_session(pd.Timestamp("2015-05-22")))
    assert pit.loc[0, "available_from"] == pd.Timestamp(independant)


def test_le_decalage_refuse_un_depot_anterieur_au_calendrier() -> None:
    """Hors des bornes du calendrier, la date se refuse au lieu de se tromper. Source (a)."""
    # La première séance chargée par exchange_calendars fixe la borne. Un dépôt
    # antérieur n'a pas de « séance suivante » connue : rendre la première séance
    # du calendrier serait faux en silence, donc le module lève.
    premiere = pd.Timestamp(get_calendar("XNYS").sessions[0])
    trop_vieux = (premiere - pd.Timedelta(days=30)).date().isoformat()
    payload = concept_payload(
        [{"end": "1900-01-01", "val": 1.0, "accn": "x", "form": "10-K", "filed": trop_vieux}]
    )
    with pytest.raises(DataQualityError, match="commence le"):
        to_point_in_time(payload, availability_lag_business_days=1)


def test_le_decalage_negatif_est_refuse() -> None:
    """Avancer la disponibilité est la fuite même, donc refusé. Source (a)."""
    with pytest.raises(ValueError, match="négatif"):
        to_point_in_time(concept_payload(LEAK_RECORDS), availability_lag_business_days=-1)


def test_les_faits_instantanes_nont_pas_de_debut_de_periode() -> None:
    """Un poste de bilan est instantané, un poste de résultat ne l'est pas. Source (c)."""
    # « Assets » est un solde à une date, ses enregistrements n'ont pas de « start ».
    instant = to_point_in_time(concept_payload(APPLE_2008_RECORDS[:1]))
    assert bool(instant.loc[0, "is_instant"]) is True
    assert pd.isna(instant.loc[0, "period_start"])
    # Un flux porte « start » et « end », ici un trimestre de 90 jours.
    flux = concept_payload(
        [
            {
                "start": "2015-01-01",
                "end": "2015-03-31",
                "val": 500.0,
                "accn": "0000000000-15-000003",
                "fy": 2015,
                "fp": "Q1",
                "form": "10-Q",
                "filed": "2015-05-15",
            }
        ],
        tag="Revenues",
    )
    frame = to_point_in_time(flux)
    assert bool(frame.loc[0, "is_instant"]) is False
    assert frame.loc[0, "period_start"] == pd.Timestamp("2015-01-01")


def test_le_filtre_par_balise_et_par_unite() -> None:
    """Les filtres écartent ce qui n'est pas demandé. Source (a)."""
    payload = facts_payload(APPLE_2008_RECORDS)
    payload["facts"]["us-gaap"]["Liabilities"] = {
        "label": "Liabilities",
        "units": {"USD": list(LEAK_RECORDS)},
    }
    # Sans filtre : 4 déclarations d'Assets plus 2 de Liabilities font 6 lignes.
    assert len(to_point_in_time(payload)) == 6
    # Filtré sur Assets : 4 lignes.
    assert len(to_point_in_time(payload, tags=("Assets",))) == 4
    # Une unité absente rend un tableau vide, aux colonnes du schéma.
    vide = to_point_in_time(payload, units=("CAD",))
    assert vide.empty
    assert list(vide.columns) == list(PIT_SCHEMA)


def test_le_meme_json_lu_par_les_deux_interfaces_donne_le_meme_tableau() -> None:
    """companyfacts et companyconcept mènent au même résultat. Source (b)."""
    par_concept = to_point_in_time(concept_payload(APPLE_2008_RECORDS))
    par_facts = to_point_in_time(facts_payload(APPLE_2008_RECORDS))
    # Identité : les deux formes portent les mêmes enregistrements, donc les
    # mêmes valeurs et les mêmes dates. Seul « entity_name » vient d'ailleurs.
    assert list(par_concept["value"]) == list(par_facts["value"])
    assert list(par_concept["filing_date"]) == list(par_facts["filing_date"])
    assert list(par_concept["accession"]) == list(par_facts["accession"])


def test_le_schema_et_les_types_sont_ceux_annonces() -> None:
    """Le tableau porte les quatre dates exigées et rien d'autre. Source (a)."""
    pit = to_point_in_time(concept_payload(APPLE_2008_RECORDS))
    assert list(pit.columns) == list(PIT_SCHEMA)
    for name in ("period_end", "filing_date", "accepted_timestamp", "available_from"):
        assert name in pit.columns
    assert str(pit["accepted_timestamp"].dtype) == "datetime64[ns, UTC]"
    assert str(pit["value"].dtype) == "float64"


def test_horodatage_dacceptation_absent_sauf_apport_des_soumissions() -> None:
    """Sans les soumissions, l'acceptation est « non trouvé » et non zéro. Source (a)."""
    sans = to_point_in_time(concept_payload(APPLE_2008_RECORDS[:1]))
    assert sans["accepted_timestamp"].isna().all()
    # Avec la correspondance, l'instant se remplit pour le dépôt reconnu.
    acceptation = {"0001193125-09-153165": pd.Timestamp("2009-07-22T20:31:00Z")}
    avec = to_point_in_time(concept_payload(APPLE_2008_RECORDS[:1]), acceptance=acceptation)
    assert avec.loc[0, "accepted_timestamp"] == pd.Timestamp("2009-07-22T20:31:00Z")


# ---------------------------------------------------------------------------
# Cas limites
# ---------------------------------------------------------------------------


def test_payload_sans_aucun_fait() -> None:
    """Un JSON sans enregistrement rend un tableau vide et typé. Source (a)."""
    vide = to_point_in_time({"cik": 320193, "facts": {}})
    assert vide.empty
    assert list(vide.columns) == list(PIT_SCHEMA)
    # Et « as_of » sur ce tableau ne lève pas, il rend le vide aussi.
    assert as_of(vide, "2020-01-01").empty
    assert as_of(empty_pit_frame(), "2020-01-01").empty


def test_payload_dun_seul_enregistrement() -> None:
    """Une seule déclaration n'est jamais une redéclaration. Source (b)."""
    pit = to_point_in_time(concept_payload(APPLE_2008_RECORDS[:1]))
    assert len(pit) == 1
    assert bool(pit.loc[0, "is_restatement"]) is False


def test_deux_declarations_de_valeur_identique_restent_deux_lignes() -> None:
    """Une redéclaration qui ne change rien reste une redéclaration. Source (a)."""
    # Les deux premiers dépôts d'Apple annoncent tous deux 39 572 000 000 dollars.
    pit = to_point_in_time(concept_payload(APPLE_2008_RECORDS[:2]))
    assert set(pit["value"]) == {39572000000.0}
    assert len(pit) == 2
    assert int(pit["is_restatement"].sum()) == 1


def test_valeur_nulle_acceptee_et_valeur_non_numerique_refusee() -> None:
    """Zéro est une valeur, « n/a » n'en est pas une. Source (a)."""
    zero = concept_payload(
        [{"end": "2015-03-31", "val": 0, "accn": "a", "form": "10-Q", "filed": "2015-05-15"}]
    )
    assert to_point_in_time(zero).loc[0, "value"] == 0.0
    mauvais = concept_payload(
        [{"end": "2015-03-31", "val": None, "accn": "a", "form": "10-Q", "filed": "2015-05-15"}]
    )
    with pytest.raises(DataQualityError, match="non numérique"):
        to_point_in_time(mauvais)


def test_enregistrement_sans_date_de_depot_refuse() -> None:
    """Un fait sans « filed » n'a pas de date d'utilisabilité, donc il lève. Source (a)."""
    incomplet = concept_payload([{"end": "2015-03-31", "val": 1.0, "accn": "a", "form": "10-Q"}])
    with pytest.raises(DataQualityError, match="filed"):
        to_point_in_time(incomplet)


def test_date_de_depot_vide_refusee_au_lieu_de_disparaitre() -> None:
    """Une date vide se lit « NaT » et rendrait la ligne invisible, donc elle lève. Source (a)."""
    # Calcul à la main du chemin qu'une telle ligne suivrait sans ce refus.
    # « filed » vide donne filing_date = NaT, donc available_from = NaT.
    # « as_of » écarte les dates manquantes, donc la déclaration ne sort jamais,
    # à aucune date. Le tableau annoncerait une ligne et le panel n'en aurait
    # aucune, sans un mot. Refuser à la lecture est la seule issue honnête.
    vide = concept_payload([{"end": "2015-03-31", "val": 1.0, "accn": "a", "form": "10-Q", "filed": ""}])
    with pytest.raises(DataQualityError, match="illisible ou vide"):
        to_point_in_time(vide)
    sans_fin = concept_payload([{"end": "", "val": 1.0, "accn": "a", "form": "10-Q", "filed": "2015-05-15"}])
    with pytest.raises(DataQualityError, match="illisible ou vide"):
        to_point_in_time(sans_fin)


def test_json_qui_nest_ni_facts_ni_concept_refuse() -> None:
    """Un JSON étranger lève plutôt que de rendre un tableau vide. Source (a)."""
    with pytest.raises(DataQualityError, match="companyfacts"):
        to_point_in_time({"cik": 320193, "resultat": []})


def test_as_of_sur_un_tableau_sans_les_colonnes_leve() -> None:
    """Un tableau étranger est refusé nommément. Source (a)."""
    with pytest.raises(DataQualityError, match="colonnes absentes"):
        as_of(pd.DataFrame({"valeur": [1.0]}), "2020-01-01")


# ---------------------------------------------------------------------------
# Le garde anti-fuite
# ---------------------------------------------------------------------------


def test_assert_no_lookahead_passe_sur_un_tableau_sain() -> None:
    """Le tableau construit par le module passe son propre contrôle. Source (b)."""
    pit = to_point_in_time(concept_payload(APPLE_2008_RECORDS))
    assert_no_lookahead(pit)  # ne lève pas


def test_assert_no_lookahead_attrape_la_fuite_canonique() -> None:
    """Un tableau qui daterait l'information de la fin de période échoue. Source (a)."""
    pit = to_point_in_time(concept_payload(LEAK_RECORDS))
    truque = pit.copy()
    # La fuite classique : available_from posé à period_end, soit le 2015-03-31
    # au lieu du 2015-05-15, ce qui avance l'information de 45 jours.
    truque["available_from"] = truque["period_end"]
    with pytest.raises(LookAheadError, match="2015-03-31"):
        assert_no_lookahead(truque)


def test_assert_no_lookahead_attrape_un_depot_le_jour_de_la_cloture() -> None:
    """Un fait déposé le jour même de la clôture est déjà une fuite. Source (a)."""
    # Le second contrôle se distingue du premier ici. available_from vaut bien la
    # date de dépôt, donc l'invariant de construction tient. Mais dépôt et fin de
    # période tombent tous deux le 2015-03-31, ce qu'aucune information publiée ne
    # peut faire.
    meme_jour = concept_payload(
        [
            {
                "end": "2015-03-31",
                "val": 1000.0,
                "accn": "0000000000-15-000009",
                "form": "8-K",
                "filed": "2015-03-31",
            }
        ]
    )
    pit = to_point_in_time(meme_jour)
    assert pit.loc[0, "available_from"] == pit.loc[0, "filing_date"]
    with pytest.raises(LookAheadError, match="avant la fin de la période"):
        assert_no_lookahead(pit)


def test_assert_no_lookahead_attrape_une_disponibilite_anterieure_au_depot() -> None:
    """Une date d'utilisabilité antérieure au dépôt échoue aussi. Source (a)."""
    pit = to_point_in_time(concept_payload(LEAK_RECORDS))
    truque = pit.copy()
    # Un jour avant le dépôt du 2015-05-15, soit le 2015-05-14.
    truque["available_from"] = truque["filing_date"] - pd.Timedelta(days=1)
    with pytest.raises(LookAheadError, match="précède la date de dépôt"):
        assert_no_lookahead(truque)


def test_assert_no_lookahead_refuse_une_date_manquante_au_lieu_de_la_laisser_passer() -> None:
    """Une date absente échappe aux deux inégalités, donc elle est refusée. Source (b)."""
    pit = to_point_in_time(concept_payload(LEAK_RECORDS))
    truque = pit.copy()
    truque.loc[0, "available_from"] = pd.NaT
    # Identité de l'arithmétique des dates : « NaT < x » et « NaT <= x » sont tous
    # deux faux. Les deux contrôles rendraient donc un tableau vide de fautifs et
    # déclareraient ce panel sain. La ligne doit être refusée en amont.
    assert not (pd.NaT < pd.Timestamp("2015-05-15"))
    assert not (pd.NaT <= pd.Timestamp("2015-03-31"))
    with pytest.raises(LookAheadError, match="date manquante"):
        assert_no_lookahead(truque)


def test_assert_no_lookahead_nomme_les_colonnes_absentes() -> None:
    """Un tableau sans les trois colonnes est refusé nommément. Source (a)."""
    with pytest.raises(DataQualityError, match="colonnes absentes"):
        assert_no_lookahead(pd.DataFrame({"valeur": [1.0]}))


def test_point_in_time_fundamentals_tient_le_protocole_et_valide() -> None:
    """La classe rend « as_of » et refuse un panel fautif. Source (a)."""
    pit = to_point_in_time(concept_payload(LEAK_RECORDS))
    panel = PointInTimeFundamentals(pit)
    assert isinstance(panel, PointInTimeDataset)
    assert len(panel) == 2
    assert panel.as_of("2015-03-31").empty
    assert list(panel.as_of("2015-05-15")["value"]) == [1000.0]
    truque = pit.copy()
    truque["available_from"] = truque["period_end"]
    with pytest.raises(LookAheadError):
        PointInTimeFundamentals(truque)


# ---------------------------------------------------------------------------
# Propriétés
# ---------------------------------------------------------------------------

_records = st.lists(
    st.tuples(
        st.integers(min_value=0, max_value=2000),  # jours écoulés depuis le 2010-01-01
        st.floats(min_value=-1e9, max_value=1e9, allow_nan=False, allow_infinity=False),
    ),
    min_size=1,
    max_size=25,
)


def _payload_from(pairs: list[tuple[int, float]]) -> dict[str, Any]:
    """Rend un JSON de concept où chaque couple donne un dépôt du même trimestre."""
    records = [
        {
            "end": "2009-12-31",
            "val": value,
            "accn": f"0000000000-10-{index:06d}",
            "form": "10-Q",
            "filed": (dt.date(2010, 1, 1) + dt.timedelta(days=offset)).isoformat(),
        }
        for index, (offset, value) in enumerate(pairs)
    ]
    return concept_payload(records)


@hyp_settings(deadline=None, max_examples=60)
@given(pairs=_records, jour=st.integers(min_value=-10, max_value=2100))
def test_propriete_as_of_ne_rend_jamais_un_depot_futur(pairs: list[tuple[int, float]], jour: int) -> None:
    """Invariant : aucune ligne rendue n'a été déposée après la date demandée. Source (b)."""
    pit = to_point_in_time(_payload_from(pairs))
    date = pd.Timestamp(dt.date(2010, 1, 1) + dt.timedelta(days=jour))
    visible = as_of(pit, date, keep_all_revisions=True)
    assert (visible["filing_date"] <= date).all()
    assert (visible["available_from"] <= date).all()


@hyp_settings(deadline=None, max_examples=60)
@given(pairs=_records, a=st.integers(min_value=0, max_value=2100), ecart=st.integers(0, 500))
def test_propriete_la_connaissance_ne_decroit_jamais(
    pairs: list[tuple[int, float]], a: int, ecart: int
) -> None:
    """Monotonie : ce qui est connu à une date reste connu plus tard. Source (b)."""
    pit = to_point_in_time(_payload_from(pairs))
    tot = pd.Timestamp(dt.date(2010, 1, 1) + dt.timedelta(days=a))
    tard = tot + pd.Timedelta(days=ecart)
    connus_tot = set(as_of(pit, tot, keep_all_revisions=True)["accession"])
    connus_tard = set(as_of(pit, tard, keep_all_revisions=True)["accession"])
    assert connus_tot <= connus_tard


@hyp_settings(deadline=None, max_examples=60)
@given(pairs=_records)
def test_propriete_une_declaration_dorigine_par_periode(pairs: list[tuple[int, float]]) -> None:
    """Identité de comptage : les non-redéclarations comptent les périodes. Source (b)."""
    pit = to_point_in_time(_payload_from(pairs))
    periodes = pit[["cik", "taxonomy", "tag", "unit", "period_end"]].drop_duplicates()
    assert int((~pit["is_restatement"]).sum()) == len(periodes)


@hyp_settings(deadline=None, max_examples=60)
@given(pairs=_records)
def test_propriete_une_ligne_par_periode_apres_selection(pairs: list[tuple[int, float]]) -> None:
    """Identité : « as_of » rend au plus une ligne par période. Source (b)."""
    pit = to_point_in_time(_payload_from(pairs))
    selection = as_of(pit, "2020-01-01")
    assert len(selection) == selection["period_end"].nunique()
    assert len(selection) <= 1  # les couples engendrés partagent tous la même période


# ---------------------------------------------------------------------------
# Les autres formats
# ---------------------------------------------------------------------------


def test_parse_master_index_sur_lextrait_reel() -> None:
    """Les trois lignes de l'extrait sont lues avec leurs champs. Source (c)."""
    frame = parse_master_index(MASTER_INDEX_EXTRACT)
    assert len(frame) == 3
    # Première ligne : 1000032, complété à dix chiffres, fait 0001000032.
    assert frame.loc[0, "cik"] == "0001000032"
    assert frame.loc[0, "company_name"] == "BINCH JAMES G"
    assert frame.loc[0, "form_type"] == "4"
    assert frame.loc[0, "date_filed"] == pd.Timestamp("2015-06-02")
    assert frame.loc[1, "url"] == ("https://www.sec.gov/Archives/edgar/data/1000045/0001193125-15-223218.txt")
    # L'en-tête de cinq lignes et la ligne de tirets ne produisent aucune ligne.
    assert "Description" not in set(frame["cik"])


def test_parse_master_index_sur_un_texte_sans_index() -> None:
    """Un contenu qui n'est pas un master.idx lève. Source (a)."""
    with pytest.raises(DataQualityError, match="aucune ligne de dépôt"):
        parse_master_index("404 Not Found")


def test_parse_company_tickers_sur_lextrait_reel() -> None:
    """Les quatre symboles se convertissent en identifiants. Source (c)."""
    frame = parse_company_tickers(COMPANY_TICKERS_EXTRACT)
    assert len(frame) == 4
    # 1045810 complété à dix chiffres fait 0001045810 ; 320193 fait 0000320193.
    mapping = dict(zip(frame["ticker"], frame["cik"], strict=True))
    assert mapping["NVDA"] == "0001045810"
    assert mapping["AAPL"] == "0000320193"
    assert mapping["MSFT"] == "0000789019"


def test_parse_company_tickers_accepte_la_forme_fields_data() -> None:
    """La seconde forme publiée par la SEC est lue aussi. Source (c)."""
    autre = {"fields": ["cik", "ticker", "title"], "data": [[320193, "AAPL", "Apple Inc."]]}
    frame = parse_company_tickers(autre)
    assert list(frame["cik"]) == ["0000320193"]


def test_parse_acceptance_sur_lextrait_reel() -> None:
    """Les horodatages d'acceptation sont lus en temps universel. Source (c)."""
    stamps = parse_acceptance(SUBMISSIONS_EXTRACT)
    # Le dépôt 0001140361-26-034741 a été accepté le 2026-08-27 à 22 h 30 min 30 s UTC.
    assert stamps["0001140361-26-034741"] == pd.Timestamp("2026-08-27T22:30:30Z")
    assert len(stamps) == 2


def test_parse_acceptance_refuse_un_bloc_incomplet() -> None:
    """Un bloc sans les deux colonnes lève. Source (a)."""
    with pytest.raises(DataQualityError, match="acceptanceDateTime"):
        parse_acceptance({"filings": {"recent": {"accessionNumber": ["a"]}}})


# ---------------------------------------------------------------------------
# Le fournisseur, hors réseau
# ---------------------------------------------------------------------------


def test_le_fournisseur_tient_le_protocole_data_provider(tmp_path: Any) -> None:
    """La classe porte « name », « fetch » et « manifest ». Source (a)."""
    provider, _ = make_provider([{"cik": 320193, "facts": {}}], tmp_path)
    assert isinstance(provider, DataProvider)
    assert provider.name == "sec"


def test_company_concept_appelle_ladresse_attendue(tmp_path: Any) -> None:
    """L'appel part vers l'adresse mesurée, avec le JSON rendu tel quel. Source (c)."""
    payload = concept_payload(APPLE_2008_RECORDS)
    provider, session = make_provider([payload], tmp_path)
    recu = provider.company_concept(320193, "us-gaap", "Assets")
    assert session.calls[0]["url"] == (
        "https://data.sec.gov/api/xbrl/companyconcept/CIK0000320193/us-gaap/Assets.json"
    )
    assert recu["units"]["USD"][0]["val"] == 39572000000
    # L'en-tête d'identification part avec la requête, la SEC l'exige.
    assert "@" in session.calls[0]["headers"]["User-Agent"]


def test_ticker_to_cik_hors_reseau(tmp_path: Any) -> None:
    """La correspondance symbole vers déposant se construit sans réseau. Source (c)."""
    provider, _ = make_provider([COMPANY_TICKERS_EXTRACT], tmp_path)
    mapping = provider.ticker_to_cik()
    assert mapping["AAPL"] == "0000320193"
    assert mapping["NVDA"] == "0001045810"
    assert len(mapping) == 4


def test_full_index_hors_reseau(tmp_path: Any) -> None:
    """L'index d'un trimestre se lit depuis les octets d'un master.idx. Source (c)."""
    provider, session = make_provider([MASTER_INDEX_EXTRACT.encode("latin-1")], tmp_path)
    frame = provider.full_index(2015, 2)
    assert session.calls[0]["url"] == ("https://www.sec.gov/Archives/edgar/full-index/2015/QTR2/master.idx")
    assert len(frame) == 3


def test_submissions_et_horodatages_hors_reseau(tmp_path: Any) -> None:
    """Les soumissions rendent les instants d'acceptation. Source (c)."""
    provider, _ = make_provider([SUBMISSIONS_EXTRACT], tmp_path)
    stamps = provider.acceptance_timestamps(320193)
    assert stamps["0001140361-26-033928"] == pd.Timestamp("2026-08-20T22:30:16Z")


def test_fundamentals_panel_hors_reseau(tmp_path: Any) -> None:
    """Le panel garde les redéclarations de la fenêtre demandée. Source (c)."""
    provider, _ = make_provider([facts_payload(APPLE_2008_RECORDS)], tmp_path)
    panel = provider.fundamentals_panel(ciks=[320193], tags=["Assets"], start="2008-01-01", end="2008-12-31")
    # Les quatre déclarations portent toutes la période close le 2008-09-27, qui
    # tombe dans la fenêtre. Aucune n'est écartée.
    assert len(panel) == 4
    assert set(panel["period_end"]) == {pd.Timestamp("2008-09-27")}
    assert list(panel.columns) == list(PIT_SCHEMA)


def test_fundamentals_panel_filtre_sur_la_fenetre(tmp_path: Any) -> None:
    """Une fenêtre qui exclut la période rend un panel vide. Source (a)."""
    provider, _ = make_provider([facts_payload(APPLE_2008_RECORDS)], tmp_path)
    # La seule période du jeu se clôt le 2008-09-27, hors de l'année 2012.
    panel = provider.fundamentals_panel(ciks=[320193], tags=["Assets"], start="2012-01-01", end="2012-12-31")
    assert panel.empty
    # Filtrée sur la disponibilité, la fenêtre 2010 attrape les deux dépôts de 2010.
    par_disponibilite = provider.fundamentals_panel(
        ciks=[320193],
        tags=["Assets"],
        start="2010-01-01",
        end="2010-12-31",
        filter_on="available_from",
    )
    assert len(par_disponibilite) == 2


def test_fundamentals_panel_refuse_une_colonne_et_une_fenetre_impossibles(tmp_path: Any) -> None:
    """Un filtre inconnu et une fenêtre inversée lèvent. Source (a)."""
    provider, _ = make_provider([facts_payload(APPLE_2008_RECORDS)], tmp_path)
    with pytest.raises(ValueError, match="filter_on"):
        provider.fundamentals_panel(
            ciks=[320193], tags=["Assets"], start="2008-01-01", end="2008-12-31", filter_on="period_start"
        )
    with pytest.raises(ValueError, match="inversée"):
        provider.fundamentals_panel(ciks=[320193], tags=["Assets"], start="2012-01-01", end="2008-12-31")


def test_fetch_exige_ciks_et_tags(tmp_path: Any) -> None:
    """La signature du protocole exige les deux arguments nommés. Source (a)."""
    provider, _ = make_provider([facts_payload(APPLE_2008_RECORDS)], tmp_path)
    with pytest.raises(ValueError, match="ciks"):
        provider.fetch(start=dt.date(2008, 1, 1), end=dt.date(2008, 12, 31))
    frame = provider.fetch(
        start=dt.date(2008, 1, 1), end=dt.date(2008, 12, 31), ciks=[320193], tags=["Assets"]
    )
    assert len(frame) == 4


def test_le_decalage_negatif_est_refuse_a_la_construction(tmp_path: Any) -> None:
    """Le fournisseur refuse un décalage négatif dès sa construction. Source (a)."""
    with pytest.raises(ConfigError, match="négatif"):
        make_provider([{"cik": 320193, "facts": {}}], tmp_path, availability_lag_business_days=-1)


def test_le_manifeste_declare_le_point_in_time(tmp_path: Any) -> None:
    """La provenance dit vrai sur les trois champs qui comptent. Source (a)."""
    provider, _ = make_provider([facts_payload(APPLE_2008_RECORDS)], tmp_path)
    provider.fundamentals_panel(ciks=[320193], tags=["Assets"], start="2008-01-01", end="2008-12-31")
    manifeste = provider.manifest()
    assert manifeste.point_in_time is True
    assert manifeste.adjusted is False
    assert manifeste.survivorship_free is None  # réponse honnête, ni vrai ni faux
    assert manifeste.currency == "USD"
    assert manifeste.n_rows == 4
    assert manifeste.n_columns == len(PIT_SCHEMA)
    assert "filing_date" in manifeste.notes
    # Identité, source (b) : la note annonce un nombre de limites, et ce nombre
    # est celui de la constante. Compter les entrées de la constante et exiger
    # ce même compte serait comparer le code à lui-même, donc ne rien tester ;
    # c'est l'accord entre les deux qui a du contenu.
    assert f"Limites connues : {len(KNOWN_LIMITATIONS)}" in manifeste.notes
    assert all(limite.strip() for limite in KNOWN_LIMITATIONS)


def test_le_manifeste_exige_une_fenetre(tmp_path: Any) -> None:
    """Sans panel et sans dates, le manifeste refuse d'inventer. Source (a)."""
    provider, _ = make_provider([{"cik": 320193, "facts": {}}], tmp_path)
    with pytest.raises(ConfigError, match="start et end"):
        provider.manifest()
    with pytest.raises(ValueError, match="inconnues"):
        provider.manifest(start=dt.date(2020, 1, 1), end=dt.date(2020, 12, 31), inconnu=1)


def test_le_cache_brut_ecrit_avant_toute_interpretation(tmp_path: Any) -> None:
    """La réponse est écrite sur disque, et relue sans nouvelle requête. Source (a)."""
    provider, session = make_provider([concept_payload(APPLE_2008_RECORDS)], tmp_path)
    provider.company_concept(320193, "us-gaap", "Assets")
    assert len(session.calls) == 1
    assert list(tmp_path.rglob("*.bin"))
    provider.company_concept(320193, "us-gaap", "Assets")
    # Le second appel vient du cache : aucune requête de plus.
    assert len(session.calls) == 1


# ---------------------------------------------------------------------------
# Réseau, exclu de l'intégration continue
# ---------------------------------------------------------------------------


@pytest.mark.network
def test_reseau_companyfacts_reel_porte_les_quatre_dates(tmp_path: Any) -> None:
    """Le vrai companyfacts d'Apple donne les quatre colonnes de dates. Source (c)."""
    provider = SecProvider(raw_root=tmp_path)
    facts = provider.company_facts(320193)
    pit = to_point_in_time(facts, taxonomies=("us-gaap",), tags=("Assets",))
    for name in ("period_end", "filing_date", "accepted_timestamp", "available_from"):
        assert name in pit.columns
    assert not pit.empty
    assert_no_lookahead(pit)
    # La période close le 2008-09-27 est déclarée plusieurs fois, et la valeur
    # connue au 2009-12-31 diffère de celle connue au 2010-06-30. Source (c).
    avant = as_of(pit, "2009-12-31")
    apres = as_of(pit, "2010-06-30")
    cible = pd.Timestamp("2008-09-27")
    assert list(avant.loc[avant["period_end"] == cible, "value"]) == [39572000000.0]
    assert list(apres.loc[apres["period_end"] == cible, "value"]) == [36171000000.0]


@pytest.mark.network
def test_reseau_index_complet_2015_qtr2(tmp_path: Any) -> None:
    """L'index du deuxième trimestre 2015 se télécharge et se lit. Source (c)."""
    provider = SecProvider(raw_root=tmp_path)
    frame = provider.full_index(2015, 2)
    assert len(frame) > 100_000  # mesuré le 2026-09-01 : 260 019 lignes de dépôt
    assert frame["date_filed"].min() >= pd.Timestamp("2015-01-01")
    # Les trois premières lignes de l'extrait recopié plus haut sont celles du
    # fichier vivant, dans le même ordre. Source (c).
    attendu = parse_master_index(MASTER_INDEX_EXTRACT)
    assert list(frame.loc[:2, "cik"]) == list(attendu["cik"])
    assert list(frame.loc[:2, "company_name"]) == list(attendu["company_name"])
    assert list(frame.loc[:2, "date_filed"]) == list(attendu["date_filed"])
    # Mesuré le 2026-09-01 : 3 542 dépôts, soit 1,36 %, tombent hors séance, le
    # Vendredi saint du 2015-04-03 et le samedi 2015-04-25. Source (c).
    seances = set(get_calendar("XNYS").sessions)
    hors_seance = frame.loc[~frame["date_filed"].isin(seances)]
    assert sorted(set(hors_seance["date_filed"])) == [
        pd.Timestamp("2015-04-03"),
        pd.Timestamp("2015-04-25"),
    ]

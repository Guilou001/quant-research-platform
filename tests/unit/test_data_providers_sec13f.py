"""Le fournisseur des jeux 13F sur un fichier compressé écrit à la main, sans réseau."""

from __future__ import annotations

import datetime as dt
import io
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from quantlab.core.errors import LookAheadError
from quantlab.data.providers.base import RawResponse
from quantlab.data.providers.sec13f import (
    SecForm13FProvider,
    normalize_value_units,
    parse_index,
    parse_quarter,
)

SUBMISSION = "ACCESSION_NUMBER\tFILING_DATE\tSUBMISSIONTYPE\tCIK\tPERIODOFREPORT\n0001-23-000005\t31-OCT-2023\t13F-HR\t0000051762\t30-SEP-2023\n"
COVERPAGE = "ACCESSION_NUMBER\tREPORTCALENDARORQUARTER\tISAMENDMENT\tFILINGMANAGER_NAME\tREPORTTYPE\n0001-23-000005\t30-SEP-2023\t\tRNC CAPITAL MANAGEMENT LLC\t13F HOLDINGS REPORT\n"
INFOTABLE = (
    "ACCESSION_NUMBER\tINFOTABLE_SK\tNAMEOFISSUER\tTITLEOFCLASS\tCUSIP\tFIGI\tVALUE\tSSHPRNAMT\tSSHPRNAMTTYPE\tPUTCALL\tINVESTMENTDISCRETION\n"
    "0001-23-000005\t1\tABBOTT LABORATORIES\tCOM\t002824100\tBBG00KTDT9Q6\t1515058\t15643\tSH\t\tSOLE\n"
    "0001-23-000005\t2\tAPPLE INC\tCOM\t037833100\t\t2000000\t10000\tSH\tPut\tSOLE\n"
)


def _zip(submission: str = SUBMISSION, prefix: str = "") -> bytes:
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as z:
        z.writestr(f"{prefix}SUBMISSION.tsv", submission)
        z.writestr(f"{prefix}COVERPAGE.tsv", COVERPAGE)
        z.writestr(f"{prefix}INFOTABLE.tsv", INFOTABLE)
    return tampon.getvalue()


def test_les_tables_dans_un_dossier_en_majuscules_sont_trouvees() -> None:
    """Les fichiers par fenêtre de trois mois rangent leurs tables dans un dossier, mesuré."""
    tables = parse_quarter(_zip(prefix="01JUN2025-31AUG2025_form13f/"))
    assert len(tables["holdings"]) == 2


class FakeClient:
    def __init__(self, bodies: dict[str, bytes]) -> None:
        self.bodies = bodies
        self.calls: list[str] = []

    def get(
        self, url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None
    ) -> RawResponse:
        self.calls.append(url)
        for cle, corps in self.bodies.items():
            if cle in url:
                return RawResponse(
                    content=corps, url=url, fetched_at=dt.datetime(2026, 9, 4, tzinfo=dt.UTC), status_code=200
                )
        raise AssertionError(url)


def test_le_trimestre_rend_ses_trois_tables_typees() -> None:
    tables = parse_quarter(_zip())
    assert tables["submissions"].loc[0, "filing_date"] == pd.Timestamp("2023-10-31")
    assert tables["submissions"].loc[0, "period_end"] == pd.Timestamp("2023-09-30")
    assert tables["coverpages"].loc[0, "manager_name"] == "RNC CAPITAL MANAGEMENT LLC"
    positions = tables["holdings"]
    assert positions.loc[0, "cusip"] == "002824100" and positions.loc[0, "figi"] == "BBG00KTDT9Q6"
    assert positions.loc[0, "value_usd"] == 1515058 and positions.loc[0, "shares"] == 15643
    assert positions.loc[1, "put_call"] == "Put"


def test_un_depot_anterieur_a_sa_periode_est_une_fuite() -> None:
    faux = "ACCESSION_NUMBER\tFILING_DATE\tSUBMISSIONTYPE\tCIK\tPERIODOFREPORT\n0001-23-000005\t15-SEP-2023\t13F-HR\t0000051762\t30-SEP-2023\n"
    with pytest.raises(LookAheadError):
        parse_quarter(_zip(faux))


def test_l_index_rend_les_adresses_completes() -> None:
    html = (
        '<a href="/files/structureddata/data/form-13f-data-sets/2023q4_form13f.zip">x</a>'
        '<a href="/files/structureddata/data/form-13f-data-sets/2013q2_form13f.zip">y</a>'
    )
    liens = parse_index(html)
    assert liens == [
        "https://www.sec.gov/files/structureddata/data/form-13f-data-sets/2013q2_form13f.zip",
        "https://www.sec.gov/files/structureddata/data/form-13f-data-sets/2023q4_form13f.zip",
    ]


def test_le_fournisseur_lit_le_cache_et_declare_le_point_in_time(tmp_path: Path) -> None:
    client = FakeClient({"2023q4_form13f.zip": _zip()})
    fournisseur = SecForm13FProvider(client=client, raw_root=tmp_path / "sec13f")
    url = "https://www.sec.gov/files/structureddata/data/form-13f-data-sets/2023q4_form13f.zip"
    tables = fournisseur.quarter(url)
    assert len(tables["holdings"]) == 2
    manifeste = fournisseur.manifest()
    assert manifeste.point_in_time is True
    assert manifeste.data_end == dt.date(2023, 10, 31)
    fournisseur.quarter(url)
    assert len(client.calls) == 1


def test_une_declaration_en_milliers_est_ramenee_en_dollars() -> None:
    """Apple à 150 $ : 10 000 titres valent 1 500 000 $, donc 1 500 en milliers.

    La déclaration 0001 vaut 0,15 $ par titre lue en dollars, sous le seuil ;
    la déclaration 0002 vaut 150 $ par titre et reste telle quelle.
    """
    positions = pd.DataFrame(
        {
            "accession": ["0001", "0001", "0002", "0002"],
            "value_usd": [1500.0, 800.0, 1500000.0, 800000.0],
            "shares": [10000.0, 4000.0, 10000.0, 4000.0],
        }
    )
    resultat = normalize_value_units(positions)
    assert resultat["value_usd"].tolist() == [1500000.0, 800000.0, 1500000.0, 800000.0]
    assert resultat["value_unit"].tolist() == ["thousands", "thousands", "dollars", "dollars"]


def test_une_ligne_sans_titres_suit_sa_declaration() -> None:
    """Le diagnostic vient de la médiane des lignes qui ont un nombre de titres."""
    positions = pd.DataFrame(
        {
            "accession": ["0001", "0001", "0001"],
            "value_usd": [1500.0, 800.0, 50.0],
            "shares": [10000.0, 4000.0, 0.0],
        }
    )
    resultat = normalize_value_units(positions)
    assert resultat["value_usd"].tolist() == [1500000.0, 800000.0, 50000.0]


def test_une_valeur_cent_fois_trop_grande_est_suspecte_et_non_corrigee() -> None:
    """22 574 $ par titre n'est ni des dollars ni des milliers : la déclaration est marquée."""
    positions = pd.DataFrame(
        {
            "accession": ["0003", "0003"],
            "value_usd": [225740000.0, 120000000.0],
            "shares": [10000.0, 4000.0],
        }
    )
    resultat = normalize_value_units(positions)
    assert resultat["value_usd"].tolist() == [225740000.0, 120000000.0]
    assert resultat["value_unit"].tolist() == ["suspect", "suspect"]

"""La correspondance OpenFIGI sur des réponses écrites à la main, sans réseau."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from quantlab.core.errors import DataQualityError
from quantlab.data.providers.openfigi import OpenFigiMapper, parse_mapping_response

REPONSE = [
    {
        "data": [
            {
                "ticker": "AAPL",
                "exchCode": "US",
                "compositeFIGI": "BBG000B9XRY4",
                "securityType": "Common Stock",
                "name": "APPLE INC",
            }
        ]
    },
    {"error": "No identifier found."},
    {
        "data": [
            {"ticker": "ABT", "exchCode": "UA", "compositeFIGI": "X"},
            {"ticker": "ABT", "exchCode": "US", "compositeFIGI": "BBG000B9ZXB4"},
        ]
    },
]


class FakeResponse:
    def __init__(self, payload: list[dict[str, Any]], status: int = 200) -> None:
        self._payload = payload
        self.status_code = status

    def json(self) -> list[dict[str, Any]]:
        return self._payload


class FakeSession:
    def __init__(self) -> None:
        self.posts: list[list[dict[str, str]]] = []

    def post(
        self, url: str, *, json: list[dict[str, str]], headers: dict[str, str], timeout: int
    ) -> FakeResponse:
        self.posts.append(json)
        par_cusip = {"037833100": REPONSE[0], "524908100": REPONSE[1], "002824100": REPONSE[2]}
        return FakeResponse([par_cusip[j["idValue"]] for j in json])


def test_la_reponse_retient_le_titre_americain_et_marque_l_absence() -> None:
    tableau = parse_mapping_response(["037833100", "524908100", "002824100"], REPONSE)
    assert tableau.loc[0, "ticker"] == "AAPL" and bool(tableau.loc[0, "found"])
    assert not bool(tableau.loc[1, "found"]) and pd.isna(tableau.loc[1, "ticker"])
    assert tableau.loc[2, "composite_figi"] == "BBG000B9ZXB4"


def test_une_reponse_de_mauvaise_longueur_est_refusee() -> None:
    with pytest.raises(DataQualityError):
        parse_mapping_response(["a", "b"], REPONSE)


def test_le_cache_evite_la_seconde_requete(tmp_path: Path) -> None:
    session = FakeSession()
    pauses: list[float] = []
    mapper = OpenFigiMapper(tmp_path / "figi.json", session=session, sleeper=pauses.append)
    premier = mapper.map(["037833100", "524908100", "002824100"])
    assert len(premier) == 3 and len(session.posts) == 1 and pauses == [2.5]
    second = OpenFigiMapper(tmp_path / "figi.json", session=session, sleeper=pauses.append).map(["037833100"])
    assert second.loc[0, "ticker"] == "AAPL" and len(session.posts) == 1

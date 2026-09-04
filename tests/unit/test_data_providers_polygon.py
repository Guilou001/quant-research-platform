"""Le fournisseur Polygon sur des réponses écrites à la main, sans réseau ni clé."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from quantlab.core.errors import ConfigError
from quantlab.data.providers.base import RawResponse
from quantlab.data.providers.polygon import PolygonProvider, parse_daily_bars, parse_reference_page

PAGE_1 = json.dumps(
    {
        "results": [
            {
                "ticker": "AAB.WS",
                "name": "LEHMAN BROTHERS WTS",
                "active": False,
                "delisted_utc": "2008-02-11T05:00:00Z",
                "type": "WARRANT",
                "primary_exchange": "XASE",
            },
            {
                "ticker": "LEH",
                "name": "LEHMAN BROTHERS HOLDINGS",
                "active": False,
                "delisted_utc": "2008-09-17T04:00:00Z",
                "type": "CS",
                "primary_exchange": "XNYS",
                "cik": "0000806085",
            },
        ],
        "next_url": "https://api.polygon.io/v3/reference/tickers?cursor=abc",
    }
)
PAGE_2 = json.dumps({"results": [{"ticker": "WCOM", "name": "WORLDCOM", "active": False, "type": "CS"}]})
BARS = json.dumps(
    {
        "ticker": "AAPL",
        "resultsCount": 2,
        # 1725422400000 ms = 2024-09-04 04:00 UTC = 2024-09-04 00:00 New York.
        "results": [
            {
                "t": 1725422400000,
                "o": 228.55,
                "h": 232.0,
                "l": 226.5,
                "c": 220.85,
                "v": 43840200,
                "vw": 229.1,
                "n": 100,
            },
            {
                "t": 1725508800000,
                "o": 221.0,
                "h": 225.0,
                "l": 220.0,
                "c": 222.38,
                "v": 36615400,
                "vw": 222.5,
                "n": 90,
            },
        ],
    }
)


class FakeClient:
    def __init__(self, bodies: dict[str, str]) -> None:
        self.bodies = bodies
        self.calls: list[dict[str, Any]] = []

    def get(
        self, url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None
    ) -> RawResponse:
        self.calls.append({"url": url, "params": dict(params or {}), "headers": dict(headers or {})})
        for cle, corps in self.bodies.items():
            if cle in url:
                return RawResponse(
                    content=corps.encode(), url=url, fetched_at=dt.datetime.now(dt.UTC), status_code=200
                )
        raise AssertionError(f"réponse non prévue pour {url}")


def test_une_page_du_referentiel_rend_ses_lignes_et_la_suivante() -> None:
    frame, suivant = parse_reference_page(PAGE_1)
    assert list(frame["ticker"]) == ["AAB.WS", "LEH"]
    assert frame.loc[1, "delisted_utc"] == pd.Timestamp("2008-09-17T04:00:00Z")
    assert suivant is not None and "cursor=abc" in suivant
    frame2, suivant2 = parse_reference_page(PAGE_2)
    assert suivant2 is None and pd.isna(frame2.loc[0, "delisted_utc"])


def test_les_barres_sont_datees_au_jour_de_new_york() -> None:
    """L'horodatage en millisecondes de 4 h UTC tombe le 2024-09-04 à New York."""
    frame = parse_daily_bars(BARS, "AAPL")
    assert frame.loc[0, "date"] == pd.Timestamp("2024-09-04")
    assert frame.loc[0, "close"] == pytest.approx(220.85)
    assert list(frame.columns) == [
        "date",
        "ticker",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "vwap",
        "transactions",
    ]


def test_le_fournisseur_pagine_avec_la_pause_et_sans_cle_dans_le_cache(tmp_path: Path) -> None:
    client = FakeClient({"cursor=abc": PAGE_2, "/v3/reference/tickers": PAGE_1})
    pauses: list[float] = []
    fournisseur = PolygonProvider(
        api_key="secret", pause_s=13.0, sleeper=pauses.append, client=client, raw_root=tmp_path / "polygon"
    )
    tableau = fournisseur.reference_tickers(active=False)
    assert list(tableau["ticker"]) == ["AAB.WS", "LEH", "WCOM"]
    assert len(client.calls) == 2
    assert all("secret" not in json.dumps(c["params"]) for c in client.calls)
    assert all(c["headers"]["Authorization"] == "Bearer secret" for c in client.calls)
    assert pauses == [13.0, 13.0]
    assert fournisseur.manifest().survivorship_free is True
    # Aucune clé écrite dans le cache brut.
    for fichier in (tmp_path / "polygon").rglob("*"):
        if fichier.is_file():
            assert b"secret" not in fichier.read_bytes()


def test_sans_cle_le_fournisseur_refuse(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("POLYGON_API_KEY", raising=False)
    monkeypatch.setattr(
        "quantlab.data.providers.polygon.read_api_key",
        lambda: (_ for _ in ()).throw(ConfigError("aucune clé")),
    )
    fournisseur = PolygonProvider(
        client=FakeClient({}), raw_root=tmp_path / "polygon", sleeper=lambda s: None
    )
    with pytest.raises(ConfigError):
        fournisseur.daily_bars("AAPL", start="2024-09-01", end="2024-09-10")

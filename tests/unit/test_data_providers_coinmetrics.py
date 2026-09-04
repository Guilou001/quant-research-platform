"""Le fournisseur Coin Metrics sur des fichiers écrits à la main, sans réseau."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from quantlab.core.errors import ConfigError, DataQualityError
from quantlab.data.providers.base import RawResponse
from quantlab.data.providers.coinmetrics import CoinMetricsProvider, parse_asset_csv, parse_asset_list

TREE = json.dumps(
    {"truncated": False, "tree": [{"path": "csv/btc.csv"}, {"path": "csv/luna.csv"}, {"path": "README.md"}]}
)
BTC = "time,AdrActCnt,CapMrktCurUSD,PriceUSD\n2017-12-16,1,320000000000,19100.0\n2017-12-17,1,330000000000,19500.0\n2017-12-18,1,,18900.0\n"


class FakeClient:
    def __init__(self, bodies: dict[str, str]) -> None:
        self.bodies = bodies
        self.calls: list[str] = []

    def get(
        self, url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None
    ) -> RawResponse:
        self.calls.append(url)
        for cle, corps in self.bodies.items():
            if cle in url:
                return RawResponse(
                    content=corps.encode(),
                    url=url,
                    fetched_at=dt.datetime(2026, 9, 4, tzinfo=dt.UTC),
                    status_code=200,
                )
        raise AssertionError(url)


def test_l_arbre_rend_les_actifs_et_refuse_la_troncature() -> None:
    assert parse_asset_list(TREE) == ["btc", "luna"]
    with pytest.raises(DataQualityError):
        parse_asset_list(json.dumps({"truncated": True, "tree": []}))


def test_le_csv_rend_prix_et_capitalisation_dates() -> None:
    frame = parse_asset_csv(BTC, "btc")
    assert frame.loc[1, "date"] == pd.Timestamp("2017-12-17")
    assert frame.loc[1, "price_usd"] == pytest.approx(19500.0)
    assert frame.loc[1, "market_cap_usd"] == pytest.approx(3.3e11)
    assert pd.isna(frame.loc[2, "market_cap_usd"])
    assert list(frame.columns) == ["date", "asset", "price_usd", "market_cap_usd"]


def test_le_fournisseur_lit_le_cache_et_declare_la_licence(tmp_path: Path) -> None:
    client = FakeClient({"git/trees": TREE, "csv/btc.csv": BTC})
    fournisseur = CoinMetricsProvider(client=client, raw_root=tmp_path / "cm")
    assert fournisseur.assets() == ["btc", "luna"]
    frame = fournisseur.asset_history("btc")
    assert len(frame) == 3
    manifeste = fournisseur.manifest()
    assert "NonCommercial" in manifeste.license
    assert manifeste.survivorship_free is True
    fournisseur.asset_history("btc")
    assert len(client.calls) == 2


def test_un_nom_d_actif_en_majuscules_est_refuse(tmp_path: Path) -> None:
    fournisseur = CoinMetricsProvider(client=FakeClient({}), raw_root=tmp_path / "cm")
    with pytest.raises(ConfigError):
        fournisseur.asset_history("BTC")

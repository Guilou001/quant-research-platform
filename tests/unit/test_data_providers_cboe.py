"""Le fournisseur des indices du Cboe : lecture, refus, manifeste, sur des extraits écrits à la main."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from quantlab.core.errors import ConfigError, DataQualityError
from quantlab.data.providers.base import RawResponse
from quantlab.data.providers.cboe import CboeIndexProvider, daily_segment, parse_history_csv

PUT_CSV = (
    "DATE,PUT\n03/04/1991,153.500000\n03/05/1991,154.100000\n03/06/1991,153.900000\n03/07/1991,155.200000\n"
)
VIX_CSV = "DATE,OPEN,HIGH,LOW,CLOSE\n01/02/1990,17.24,17.24,17.24,17.24\n01/03/1990,18.19,18.19,18.19,18.19\n"


def test_l_extrait_de_quatre_lignes_rend_des_dates_triees_et_des_niveaux() -> None:
    table = parse_history_csv(PUT_CSV, "PUT")
    assert list(table.columns) == ["date", "level"]
    assert table["date"].tolist()[0] == pd.Timestamp("1991-03-04")
    assert table["level"].tolist() == [153.5, 154.1, 153.9, 155.2]


def test_le_vix_se_lit_a_la_cloture() -> None:
    table = parse_history_csv(VIX_CSV, "VIX")
    assert table["level"].tolist() == [17.24, 18.19]


def test_une_colonne_manquante_est_refusee() -> None:
    with pytest.raises(DataQualityError):
        parse_history_csv("DATE,BXM\n03/04/1991,100.0\n", "PUT")


def test_une_date_repetee_est_refusee() -> None:
    with pytest.raises(DataQualityError):
        parse_history_csv("DATE,PUT\n03/04/1991,100.0\n03/04/1991,101.0\n", "PUT")


def test_un_niveau_nul_est_refuse() -> None:
    with pytest.raises(DataQualityError):
        parse_history_csv("DATE,PUT\n03/04/1991,0.0\n", "PUT")


def test_un_indice_inconnu_est_refuse() -> None:
    with pytest.raises(ConfigError):
        parse_history_csv(PUT_CSV, "SPX")


def test_le_segment_quotidien_ecarte_les_points_isoles_du_debut() -> None:
    """Trois points espacés d'années, puis quatre séances : seules les quatre séances restent."""
    texte = (
        "DATE,PUT\n03/04/1991,153.5\n09/27/1994,220.0\n01/03/2007,700.0\n01/04/2007,701.0\n"
        "01/05/2007,702.0\n01/08/2007,703.0\n"
    )
    table = daily_segment(parse_history_csv(texte, "PUT"))
    assert table["date"].iloc[0] == pd.Timestamp("2007-01-03")
    assert len(table) == 4


def test_un_historique_continu_est_rendu_entier() -> None:
    table = daily_segment(parse_history_csv(PUT_CSV, "PUT"))
    assert len(table) == 4


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
        raise AssertionError(f"adresse inattendue : {url}")


def test_le_fournisseur_lit_le_cache_et_declare_la_licence(tmp_path: Path) -> None:
    client = FakeClient({"PUT_History.csv": PUT_CSV.encode()})
    fournisseur = CboeIndexProvider(client=client, raw_root=tmp_path / "cboe")
    table = fournisseur.history("PUT")
    assert len(table) == 4
    manifeste = fournisseur.manifest()
    assert "non commercial" in manifeste.license
    assert manifeste.data_start == dt.date(1991, 3, 4)
    assert manifeste.data_end == dt.date(1991, 3, 7)
    assert manifeste.point_in_time is False
    fournisseur.history("PUT")
    assert len(client.calls) == 1


@pytest.mark.network
def test_reseau_la_volatilite_mensuelle_de_put_1991_2018_est_celle_publiee() -> None:
    """Critère 3 de la spécification 007 : autour des 9,9 % de Cboe et Wilshire (2019) pour 1986-2018.

    Le fichier n'est quotidien que depuis le 2007-01-03, mesuré ; la fenêtre
    2007-2018 contient 2008, donc la tolérance monte à trois points au-dessus.
    """
    from quantlab.analytics.returns import resample_returns, to_returns
    from quantlab.core.types import Frequency, ReturnKind

    table = daily_segment(CboeIndexProvider().history("PUT"))
    assert table["date"].iloc[0] == pd.Timestamp("2007-01-03")
    quotidien = to_returns(pd.Series(table["level"].to_numpy(), index=table["date"]), kind=ReturnKind.SIMPLE)
    mensuel = resample_returns(quotidien, Frequency.MONTHLY, ReturnKind.SIMPLE).loc["2007":"2018"]
    volatilite = float(mensuel.std(ddof=1) * (12**0.5))
    assert 0.09 <= volatilite <= 0.13, volatilite

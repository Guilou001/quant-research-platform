"""Le fournisseur Open Source Asset Pricing, sur un extrait écrit à la main, sans réseau."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from quantlab.core.errors import DataQualityError
from quantlab.data.providers.base import RawResponse
from quantlab.data.providers.osap import OsapProvider, parse_long_short_csv, parse_signal_doc

RETURNS = "date,AM,Accruals\n2024-10-31,-1.745,0.5\n2024-11-29,2.286,-0.25\n2024-12-31,1.801,NA\n"
DOC = (
    "Acronym,Cat.Signal,Predictability in OP,Signal Rep Quality,Authors,Year,LongDescription,Journal,"
    "Cat.Form,Cat.Data,Cat.Economic,SampleStartYear,SampleEndYear,Acronym2,Evidence Summary,"
    "Key Table in OP,Test in OP,Sign,Return,T-Stat\n"
    "AM,Predictor,1_clear,1_good,Fama and French,1992,Assets to market,JF,continuous,Accounting,"
    "value,1963,1990,AM,t,,,1,,5.69\n"
    "Accruals,Predictor,1_clear,1_good,Sloan,1996,Accruals,AR,continuous,Accounting,accruals,"
    "1962,1991,Accruals,t,,,-1,0.866666667,4.71\n"
    "Placebo1,Placebo,3_not,1_good,Someone,2000,A placebo,JF,continuous,Accounting,x,1980,1995,P,,,,1,,1.0\n"
)


class FakeClient:
    def __init__(self, bodies: dict[str, str]) -> None:
        self.bodies = bodies
        self.calls: list[dict[str, Any]] = []

    def get(
        self, url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None
    ) -> RawResponse:
        sent = dict(params or {})
        self.calls.append({"url": url, "params": sent})
        return RawResponse(
            content=self.bodies[sent["id"]].encode("utf-8"),
            url=url,
            fetched_at=dt.datetime(2026, 9, 4, 12, 0, tzinfo=dt.UTC),
            status_code=200,
        )


def test_les_rendements_passent_du_pourcentage_a_la_fraction() -> None:
    """1,801 % en décembre 2024 devient 0,01801, et la date est la fin de mois civile."""
    frame = parse_long_short_csv(RETURNS)
    assert frame.loc[pd.Timestamp("2024-12-31"), "AM"] == pytest.approx(0.01801)
    assert frame.loc[pd.Timestamp("2024-11-30"), "AM"] == pytest.approx(0.02286)
    assert pd.isna(frame.loc[pd.Timestamp("2024-12-31"), "Accruals"])
    assert list(frame.columns) == ["AM", "Accruals"]


def test_la_fiche_ne_garde_que_les_predicteurs_avec_leurs_annees() -> None:
    doc = parse_signal_doc(DOC)
    assert list(doc.index) == ["AM", "Accruals"]
    assert doc.loc["Accruals", "publication_year"] == 1996
    assert doc.loc["Accruals", "sample_end_year"] == 1991
    assert doc.loc["AM", "op_tstat"] == pytest.approx(5.69)


def test_une_colonne_absente_est_refusee() -> None:
    with pytest.raises(DataQualityError):
        parse_long_short_csv("AM,Accruals\n1.0,2.0\n")
    with pytest.raises(DataQualityError):
        parse_signal_doc("Acronym,Cat.Signal\nAM,Predictor\n")


def test_le_fournisseur_lit_le_cache_et_declare_l_univers_sans_biais(tmp_path: Path) -> None:
    client = FakeClient(
        {"10sOryk_ddjkXagaajTKUk1nwJs2ZLRiI": RETURNS, "1Sev9s6cPFUGgxp1pFiej0lGzpsMqJCI2": DOC}
    )
    fournisseur = OsapProvider(client=client, raw_root=tmp_path / "osap")
    rendements = fournisseur.long_short_returns()
    assert rendements.shape == (3, 2)
    manifeste = fournisseur.manifest()
    assert manifeste.survivorship_free is True
    assert manifeste.point_in_time is False
    assert "Chen et Zimmermann" in manifeste.license
    assert manifeste.n_rows == 3
    # Une seconde lecture vient du cache brut : aucun nouvel appel.
    fournisseur.long_short_returns()
    assert len(client.calls) == 1
    fiche = fournisseur.signal_documentation()
    assert len(fiche) == 2
    assert len(client.calls) == 2

"""Le pont vers LEAN : format des barres, relecture du journal, réconciliation.

Chaque valeur attendue est calculée à la main dans le test, jamais copiée de la
sortie du code. Le dernier test vérifie que l'algorithme de contrôle n'importe
rien du laboratoire, ce qui est la condition de son indépendance.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from quantlab.backtest.lean_bridge import (
    format_lean_daily,
    lean_daily_bars,
    monthly_returns_from_values,
    parse_portfolio_value_log,
    reconcile_monthly,
    write_lean_daily_zip,
)
from quantlab.core.errors import DataQualityError

RACINE = Path(__file__).resolve().parents[2]


def _prix() -> pd.Series:
    dates = pd.to_datetime(["2020-01-30", "2020-01-31", "2020-02-03", "2020-02-04"])
    return pd.Series([100.0, 102.0, 101.0, 103.5], index=dates)


def test_l_ouverture_est_la_cloture_de_la_veille() -> None:
    """La barre du 31 janvier ouvre à 100, la clôture du 30 ; la première ouvre sur elle-même."""
    barres = lean_daily_bars(_prix())
    assert barres["open"].tolist() == [100.0, 100.0, 102.0, 101.0]
    assert barres["close"].tolist() == [100.0, 102.0, 101.0, 103.5]
    # Le haut et le bas encadrent toujours l'ouverture et la clôture.
    assert (barres["high"] >= barres[["open", "close"]].max(axis=1)).all()
    assert (barres["low"] <= barres[["open", "close"]].min(axis=1)).all()
    assert barres["volume"].tolist() == [0, 0, 0, 0]


def test_le_format_encode_en_dix_milliemes_de_dollar() -> None:
    """102 $ s'écrit 1020000, et la date s'écrit AAAAMMJJ suivie de 00:00."""
    texte = format_lean_daily(lean_daily_bars(_prix()))
    lignes = texte.strip().splitlines()
    assert lignes[1] == "20200131 00:00,1000000,1020000,1000000,1020000,0"
    assert lignes[3] == "20200204 00:00,1010000,1035000,1010000,1035000,0"


def test_l_archive_porte_le_csv_du_symbole_en_minuscules(tmp_path: Path) -> None:
    chemin = write_lean_daily_zip(tmp_path, "SPY", _prix())
    assert chemin == tmp_path / "equity" / "usa" / "daily" / "spy.zip"
    with zipfile.ZipFile(chemin) as archive:
        assert archive.namelist() == ["spy.csv"]
        contenu = archive.read("spy.csv").decode()
    assert contenu.startswith("20200130 00:00,1000000,1000000,1000000,1000000,0")


def test_un_prix_manquant_apres_le_premier_est_refuse() -> None:
    """Un trou intérieur serait lu en un jour par LEAN et en deux valeurs absentes par le laboratoire."""
    serie = _prix()
    serie.iloc[2] = np.nan
    with pytest.raises(DataQualityError, match="2020-02-03"):
        lean_daily_bars(serie)


def test_les_valeurs_manquantes_avant_le_premier_prix_sont_ignorees() -> None:
    serie = pd.concat([pd.Series([np.nan], index=pd.to_datetime(["2020-01-29"])), _prix()])
    barres = lean_daily_bars(serie)
    assert len(barres) == 4
    assert barres["open"].iloc[0] == 100.0


def test_une_ouverture_reelle_remplace_la_convention() -> None:
    """Avec des ouvertures fournies, la barre du 31 janvier ouvre à 101 et non à 100."""
    serie = _prix()
    ouvertures = pd.Series([99.0, 101.0, 102.5, 100.5], index=serie.index)
    barres = lean_daily_bars(serie, opens=ouvertures)
    assert barres["open"].tolist() == [99.0, 101.0, 102.5, 100.5]
    # Le 3 février ouvre à 102,5 et clôt à 101 : le haut est l'ouverture, le bas la clôture.
    assert barres.loc["2020-02-03", "high"] == 102.5
    assert barres.loc["2020-02-03", "low"] == 101.0


def test_une_ouverture_reelle_manquante_est_refusee() -> None:
    serie = _prix()
    ouvertures = pd.Series([99.0, np.nan, 102.5, 100.5], index=serie.index)
    with pytest.raises(DataQualityError):
        lean_daily_bars(serie, opens=ouvertures)


def test_un_prix_negatif_est_refuse() -> None:
    serie = _prix()
    serie.iloc[1] = -1.0
    with pytest.raises(DataQualityError):
        lean_daily_bars(serie)


def test_le_journal_est_relu_malgre_le_prefixe_de_lean() -> None:
    """LEAN préfixe chaque ligne ; seules les lignes PV comptent, triées par date."""
    journal = (
        "20260903 21:44:03 TRACE:: Debug: PV,2007-02-01,100000000.0\n"
        "20260903 21:44:03 TRACE:: Debug: DECISION,2007-01-31,3,SPY:0.5\n"
        "20260903 21:44:04 TRACE:: Debug: PV,2007-01-31,100000000.0\n"
        "20260903 21:44:04 TRACE:: Debug: PV,2007-02-02,101000000.0\n"
    )
    serie = parse_portfolio_value_log(journal)
    assert serie.index.tolist() == list(pd.to_datetime(["2007-01-31", "2007-02-01", "2007-02-02"]))
    assert serie.tolist() == [100000000.0, 100000000.0, 101000000.0]


def test_deux_valeurs_differentes_pour_une_date_sont_refusees() -> None:
    with pytest.raises(DataQualityError):
        parse_portfolio_value_log("PV,2007-01-31,1.0\nPV,2007-01-31,2.0\n")


def test_les_rendements_mensuels_prennent_la_derniere_valeur_du_mois() -> None:
    """De 100 fin janvier à 110 fin février puis 99 fin mars : +10 % puis -10 %."""
    dates = pd.to_datetime(["2020-01-30", "2020-01-31", "2020-02-14", "2020-02-28", "2020-03-31"])
    valeurs = pd.Series([95.0, 100.0, 120.0, 110.0, 99.0], index=dates)
    mensuel = monthly_returns_from_values(valeurs)
    assert mensuel.index.tolist() == list(pd.to_datetime(["2020-02-29", "2020-03-31"]))
    assert mensuel.tolist() == pytest.approx([0.10, -0.10])


def test_un_financement_absent_sur_un_mois_commun_est_refuse() -> None:
    """Un financement manquant absorbé à zéro passerait pour un écart de moteur de r_f x somme des poids."""
    index = pd.to_datetime(["2020-02-29", "2020-03-31"])
    lab = pd.Series([0.009, -0.020], index=index)
    lean = pd.Series([0.015, -0.019], index=index)
    financement = pd.Series([0.005], index=index[:1])
    with pytest.raises(DataQualityError, match="2020-03-31"):
        reconcile_monthly(lab, lean, financement)


def test_la_reconciliation_retranche_le_financement() -> None:
    """LEAN à 1,5 % total avec 0,5 % de financement vaut 1,0 % excédentaire, l'écart au lab est 0,1 %."""
    index = pd.to_datetime(["2020-02-29", "2020-03-31"])
    lab = pd.Series([0.009, -0.020], index=index)
    lean = pd.Series([0.015, -0.019], index=index)
    financement = pd.Series([0.005, 0.001], index=index)
    tableau = reconcile_monthly(lab, lean, financement)
    assert tableau["lean_excess"].tolist() == pytest.approx([0.010, -0.020])
    assert tableau["difference"].tolist() == pytest.approx([0.001, 0.0])


def test_aucun_mois_commun_est_une_erreur() -> None:
    a = pd.Series([0.01], index=pd.to_datetime(["2020-01-31"]))
    b = pd.Series([0.01], index=pd.to_datetime(["2021-01-31"]))
    with pytest.raises(DataQualityError):
        reconcile_monthly(a, b, b)


def test_l_algorithme_lean_n_importe_rien_du_laboratoire() -> None:
    """L'indépendance exigée par l'ADR-008 se vérifie mécaniquement."""
    source = (RACINE / "lean" / "algorithm" / "main.py").read_text(encoding="utf-8")
    assert "quantlab" not in source
    assert "from AlgorithmImports import" in source

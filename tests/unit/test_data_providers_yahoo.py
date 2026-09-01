"""Les tests du fournisseur Yahoo, tous hors réseau sauf un, marqué comme tel.

La réponse de yfinance est enregistrée en dur dans ce fichier, telle qu'elle a
été mesurée le 2026-09-01 avec yfinance 1.7.0. Deux formes sont conservées, la
réponse ordinaire à deux titres valides et celle qui contient un titre
introuvable. La seconde porte une bizarrerie que personne n'inventerait : le
titre en échec reçoit une colonne « Adj Close » vide, alors que les titres
valides n'en ont aucune.

Aucune valeur attendue de ce fichier ne vient de la sortie du code testé. Chaque
test dit d'où vient la sienne, entre le tableau enregistré, un calcul écrit à la
main, une identité mathématique, et la documentation de yfinance.
"""

from __future__ import annotations

import datetime as dt
import sys
from typing import Any

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.paths import Layer
from quantlab.core.protocols import DataProvider
from quantlab.core.types import Frequency
from quantlab.data.manifest import DatasetManifest, sha256_frame
from quantlab.data.providers.yahoo import (
    DTYPES,
    KNOWN_LIMITATIONS,
    LICENSE,
    SCHEMA,
    SOURCE_NAME,
    YahooProvider,
    normalize,
    to_wide,
)

# --------------------------------------------------------------------------------------
# La réponse enregistrée, mesurée le 2026-09-01 (yfinance 1.7.0, auto_adjust=False).
# yf.download(["AAPL", "MSFT"], start="2024-01-02", end="2024-01-05", interval="1d",
#             auto_adjust=False, group_by="column", progress=False, threads=False)
# --------------------------------------------------------------------------------------

RECORDED_DATES = ("2024-01-02", "2024-01-03", "2024-01-04")

RECORDED: dict[tuple[str, str], list[float]] = {
    ("Adj Close", "AAPL"): [183.403976, 182.030762, 179.718948],
    ("Adj Close", "MSFT"): [363.117950, 362.853546, 360.249146],
    ("Close", "AAPL"): [185.639999, 184.250000, 181.910004],
    ("Close", "MSFT"): [370.869995, 370.600006, 367.940002],
    ("High", "AAPL"): [188.440002, 185.880005, 183.089996],
    ("High", "MSFT"): [375.899994, 373.260010, 373.100006],
    ("Low", "AAPL"): [183.889999, 183.429993, 180.880005],
    ("Low", "MSFT"): [366.769989, 368.510010, 367.170013],
    ("Open", "AAPL"): [187.149994, 184.220001, 182.149994],
    ("Open", "MSFT"): [373.859985, 369.010010, 370.670013],
    ("Volume", "AAPL"): [82488700.0, 58414500.0, 71983600.0],
    ("Volume", "MSFT"): [25258600.0, 23083500.0, 20901500.0],
}


def recorded_frame() -> pd.DataFrame:
    """Rend la réponse enregistrée, colonnes à deux niveaux « Price » puis « Ticker »."""
    index = pd.DatetimeIndex(pd.to_datetime(list(RECORDED_DATES)), name="Date")
    columns = pd.MultiIndex.from_tuples(list(RECORDED), names=["Price", "Ticker"])
    return pd.DataFrame(RECORDED, index=index)[columns]


def recorded_frame_grouped_by_ticker() -> pd.DataFrame:
    """Rend la même réponse dans l'ordre de niveaux de ``group_by="ticker"``."""
    frame = recorded_frame()
    frame.columns = pd.MultiIndex.from_tuples(
        [(ticker, price) for price, ticker in frame.columns], names=["Ticker", "Price"]
    )
    return frame.sort_index(axis=1)


def recorded_frame_flat_single() -> pd.DataFrame:
    """Rend la forme ``multi_level_index=False`` d'un seul titre, sans « Adj Close ».

    Mesuré le 2026-09-01 : avec ``auto_adjust=True``, yfinance rend cinq colonnes
    plates, « Close », « High », « Low », « Open » et « Volume », et aucune
    colonne ajustée séparée.
    """
    index = pd.DatetimeIndex(pd.to_datetime(list(RECORDED_DATES)), name="Date")
    return pd.DataFrame(
        {
            "Close": RECORDED[("Close", "AAPL")],
            "High": RECORDED[("High", "AAPL")],
            "Low": RECORDED[("Low", "AAPL")],
            "Open": RECORDED[("Open", "AAPL")],
            "Volume": RECORDED[("Volume", "AAPL")],
        },
        index=index,
    )


def recorded_frame_with_failed_ticker() -> pd.DataFrame:
    """Rend la forme mesurée quand un identifiant n'existe pas chez Yahoo.

    Mesuré le 2026-09-01 avec ``["AAPL", "ZZZZINVALIDTICKER"]`` et
    ``auto_adjust=True`` : le titre en échec porte six colonnes entièrement
    absentes, dont une « Adj Close » que le titre valide n'a pas.
    """
    index = pd.DatetimeIndex(pd.to_datetime(list(RECORDED_DATES)), name="Date")
    absent = [float("nan")] * len(RECORDED_DATES)
    data = {
        ("Adj Close", "ZZZZINVALIDTICKER"): absent,
        ("Close", "AAPL"): RECORDED[("Adj Close", "AAPL")],
        ("Close", "ZZZZINVALIDTICKER"): absent,
        ("High", "AAPL"): RECORDED[("High", "AAPL")],
        ("High", "ZZZZINVALIDTICKER"): absent,
        ("Low", "AAPL"): RECORDED[("Low", "AAPL")],
        ("Low", "ZZZZINVALIDTICKER"): absent,
        ("Open", "AAPL"): RECORDED[("Open", "AAPL")],
        ("Open", "ZZZZINVALIDTICKER"): absent,
        ("Volume", "AAPL"): RECORDED[("Volume", "AAPL")],
        ("Volume", "ZZZZINVALIDTICKER"): absent,
    }
    columns = pd.MultiIndex.from_tuples(list(data), names=["Price", "Ticker"])
    return pd.DataFrame(data, index=index)[columns]


def synthetic_long(
    *,
    dates: list[str],
    symbols: list[str],
    closes: dict[str, list[float]],
) -> pd.DataFrame:
    """Rend un tableau long au schéma, construit à la main pour tester :func:`to_wide`."""
    rows = [
        {
            "date": pd.Timestamp(date),
            "symbol": symbol,
            "open": closes[symbol][i],
            "high": closes[symbol][i],
            "low": closes[symbol][i],
            "close": closes[symbol][i],
            "adj_close": closes[symbol][i],
            "volume": 1.0,
        }
        for symbol in symbols
        for i, date in enumerate(dates)
    ]
    return pd.DataFrame(rows)[list(SCHEMA)].astype(DTYPES)


# --------------------------------------------------------------------------------------
# Normalisation
# --------------------------------------------------------------------------------------


def test_normalise_la_reponse_a_deux_niveaux() -> None:
    """Trois séances et deux titres donnent six lignes, au schéma exact.

    Source des valeurs attendues : (a) le tableau enregistré ci-dessus, dont les
    nombres sont recopiés à la main dans les assertions. Trois dates fois deux
    titres font six lignes, et l'ordre attendu est la date croissante puis le
    symbole par ordre alphabétique, donc la première ligne est AAPL au 2 janvier.
    """
    out = normalize(recorded_frame(), tickers=["AAPL", "MSFT"])

    assert list(out.columns) == list(SCHEMA)
    assert len(out) == 6
    assert list(out["symbol"]) == ["AAPL", "MSFT", "AAPL", "MSFT", "AAPL", "MSFT"]
    assert out.loc[0, "date"] == pd.Timestamp("2024-01-02")
    assert out.loc[0, "symbol"] == "AAPL"
    assert out.loc[0, "open"] == pytest.approx(187.149994)
    assert out.loc[0, "high"] == pytest.approx(188.440002)
    assert out.loc[0, "low"] == pytest.approx(183.889999)
    assert out.loc[0, "close"] == pytest.approx(185.639999)
    assert out.loc[0, "adj_close"] == pytest.approx(183.403976)
    assert out.loc[0, "volume"] == pytest.approx(82488700.0)
    # La dernière ligne est MSFT au 4 janvier.
    assert out.loc[5, "symbol"] == "MSFT"
    assert out.loc[5, "adj_close"] == pytest.approx(360.249146)


#: Les types attendus, réécrits ici à la main plutôt que lus dans le module.
#: Comparer la sortie du code à la table du code ne prouve rien : mesuré le
#: 2026-09-01, passer « volume » de float64 à int64 dans le module laissait les
#: trente-cinq tests au vert, alors que ce type ne sait pas porter une valeur
#: absente et lève IntCastingNaNError sur un volume manquant.
TYPES_ATTENDUS: dict[str, str] = {
    "date": "datetime64[ns]",
    "symbol": "str",
    "open": "float64",
    "high": "float64",
    "low": "float64",
    "close": "float64",
    "adj_close": "float64",
    "volume": "float64",
}


def test_les_types_de_colonnes_sont_ceux_du_schema() -> None:
    """Chaque colonne porte le type attendu, et le volume est en flottant.

    Source : (a) la table :data:`TYPES_ATTENDUS`, écrite à la main dans ce
    fichier. La table :data:`DTYPES` du module est comparée à la même référence,
    pour qu'une déclaration fausse se voie au lieu de se confirmer elle-même.
    """
    out = normalize(recorded_frame(), tickers=["AAPL", "MSFT"])
    assert {name: str(dtype) for name, dtype in out.dtypes.items()} == TYPES_ATTENDUS
    assert DTYPES == TYPES_ATTENDUS
    assert set(TYPES_ATTENDUS) == set(SCHEMA)


def test_un_volume_absent_survit_a_la_mise_en_forme() -> None:
    """Un volume manquant traverse la normalisation sans faire tomber la barre.

    Source : (b) la raison même du type flottant. Un entier ne sait pas porter
    une valeur absente : mesuré le 2026-09-01, ``pd.Series([1.0, nan]).astype(
    "int64")`` lève ``IntCastingNaNError``. Yahoo laisse le volume vide sur les
    titres peu échangés, donc la barre doit rester, prix compris, avec son seul
    volume absent.
    """
    raw = recorded_frame()
    raw.loc[pd.Timestamp("2024-01-03"), ("Volume", "MSFT")] = float("nan")
    out = normalize(raw, tickers=["AAPL", "MSFT"])

    # (a) Trois dates fois deux titres font toujours six lignes : rien n'est perdu.
    assert len(out) == 6
    ligne = out[(out["symbol"] == "MSFT") & (out["date"] == pd.Timestamp("2024-01-03"))]
    assert len(ligne) == 1
    assert np.isnan(ligne["volume"].to_numpy()[0])
    # (a) Le close de MSFT au 3 janvier vaut 370.600006 dans le tableau enregistré.
    assert ligne["close"].to_numpy()[0] == pytest.approx(370.600006)


def test_l_orientation_des_niveaux_ne_change_rien() -> None:
    """Le résultat est le même que les niveaux soient champ puis titre ou l'inverse.

    Source : (b) une identité. ``group_by="column"`` et ``group_by="ticker"``
    décrivent la même donnée, donc la normalisation doit rendre le même tableau
    à la ligne près.
    """
    par_colonne = normalize(recorded_frame(), tickers=["AAPL", "MSFT"])
    par_titre = normalize(recorded_frame_grouped_by_ticker(), tickers=["AAPL", "MSFT"])
    pd.testing.assert_frame_equal(par_colonne, par_titre)


def test_colonnes_plates_et_prix_deja_ajustes() -> None:
    """Sans colonne ajustée, ``adj_close`` recopie ``close``, valeur par valeur.

    Source : (b) une identité. ``auto_adjust=True`` fait rendre à Yahoo des prix
    déjà corrigés, donc la colonne ajustée du schéma est le close lui-même. La
    vérification porte sur l'égalité exacte, sans tolérance.
    """
    out = normalize(recorded_frame_flat_single(), tickers="AAPL")
    assert len(out) == 3
    assert set(out["symbol"]) == {"AAPL"}
    assert (out["adj_close"].to_numpy() == out["close"].to_numpy()).all()
    # (a) Le close du 2 janvier vaut 185.639999 dans le tableau enregistré.
    assert out.loc[0, "close"] == pytest.approx(185.639999)


def test_colonnes_plates_sans_identifiant_levent() -> None:
    """Un tableau plat sans identifiant unique ne dit pas de quel titre il parle."""
    with pytest.raises(DataQualityError, match="colonnes plates"):
        normalize(recorded_frame_flat_single(), tickers=["AAPL", "MSFT"])


def test_titre_introuvable_leve_par_defaut() -> None:
    """Un titre demandé sans aucune barre arrête la normalisation.

    Source : (a) la forme enregistrée avec ``ZZZZINVALIDTICKER``, dont les six
    colonnes sont vides. La politique par défaut lève, parce qu'un univers
    amputé en silence fausse toute comparaison transversale.
    """
    with pytest.raises(DataQualityError, match="ZZZZINVALIDTICKER"):
        normalize(recorded_frame_with_failed_ticker(), tickers=["AAPL", "ZZZZINVALIDTICKER"])


def test_titre_introuvable_retire_sur_demande() -> None:
    """Avec « drop », le titre vide disparaît et les trois barres valides restent.

    Source : (a) le tableau enregistré. AAPL porte trois séances, le titre en
    échec aucune, donc trois lignes et un seul symbole.
    """
    out = normalize(
        recorded_frame_with_failed_ticker(),
        tickers=["AAPL", "ZZZZINVALIDTICKER"],
        on_missing="drop",
    )
    assert len(out) == 3
    assert set(out["symbol"]) == {"AAPL"}


def test_politique_de_manquant_inconnue_leve() -> None:
    """Une politique mal orthographiée est une erreur, pas un réglage par défaut."""
    with pytest.raises(ValueError, match="on_missing"):
        normalize(recorded_frame(), tickers=["AAPL", "MSFT"], on_missing="ignore")  # type: ignore[arg-type]


def test_date_en_double_leve() -> None:
    """Deux barres du même titre à la même date sont refusées.

    Source : (b) le couple date et titre est la clé du schéma. Le tableau est
    fabriqué en répétant la première séance, donc deux couples identiques.
    """
    raw = recorded_frame()
    doublon = pd.concat([raw, raw.iloc[[0]]])
    with pytest.raises(DataQualityError, match="déjà vu"):
        normalize(doublon, tickers=["AAPL", "MSFT"])


def test_plus_haut_sous_plus_bas_leve() -> None:
    """Une barre dont le haut passe sous le bas est une donnée fausse.

    Source : (b) une contrainte d'ordre. Le plus haut d'une séance domine son
    plus bas par définition. Le test abaisse le haut d'AAPL au 3 janvier à
    100,0, sous son bas de 183,429993.
    """
    raw = recorded_frame()
    raw.loc[pd.Timestamp("2024-01-03"), ("High", "AAPL")] = 100.0
    with pytest.raises(DataQualityError, match="plus haut sous leur plus bas"):
        normalize(raw, tickers=["AAPL", "MSFT"])

    # Le même tableau passe quand le contrôle est désactivé, et rend six lignes.
    assert len(normalize(raw, tickers=["AAPL", "MSFT"], check_ohlc=False)) == 6


def test_tableau_vide_leve() -> None:
    """Une réponse vide de Yahoo lève plutôt que de rendre un tableau vide."""
    with pytest.raises(InsufficientDataError):
        normalize(pd.DataFrame(), tickers=["AAPL"])


def test_une_seule_seance() -> None:
    """Une seule séance et un seul titre donnent exactement une ligne.

    Source : (a) la première ligne du tableau enregistré, isolée.
    """
    raw = recorded_frame().iloc[[0]]
    out = normalize(raw, tickers=["AAPL", "MSFT"])
    assert len(out) == 2
    assert out.loc[0, "close"] == pytest.approx(185.639999)


def test_barre_absente_retiree_sans_toucher_aux_autres() -> None:
    """Une séance absente pour un titre retire sa ligne, pas celle du voisin.

    Source : (a) le tableau enregistré, dont on efface les six champs d'AAPL au
    3 janvier. Il reste trois lignes MSFT et deux lignes AAPL, donc cinq.
    """
    raw = recorded_frame()
    for champ in ("Adj Close", "Close", "High", "Low", "Open", "Volume"):
        raw.loc[pd.Timestamp("2024-01-03"), (champ, "AAPL")] = float("nan")
    out = normalize(raw, tickers=["AAPL", "MSFT"])
    assert len(out) == 5
    assert (out["symbol"] == "AAPL").sum() == 2
    assert (out["symbol"] == "MSFT").sum() == 3


def test_prix_tombe_a_zero() -> None:
    """Un prix nul est une donnée valide, et rend un rendement de -100 %.

    Source : (a) un calcul à la main. Avec des closes de 100, 50 puis 0, les
    rendements simples valent 50 / 100 - 1 = -0,5 puis 0 / 50 - 1 = -1,0. Le
    module ne doit ni retirer la ligne à zéro, ni la traiter comme absente.
    """
    long = synthetic_long(
        dates=["2024-01-02", "2024-01-03", "2024-01-04"],
        symbols=["AAA"],
        closes={"AAA": [100.0, 50.0, 0.0]},
    )
    wide = to_wide(long, field="close")
    rendements = wide["AAA"].pct_change().dropna().to_numpy()
    assert rendements[0] == pytest.approx(-0.5)
    assert rendements[1] == pytest.approx(-1.0)


# --------------------------------------------------------------------------------------
# Passage au format large
# --------------------------------------------------------------------------------------


def test_to_wide_rend_un_index_temporel_trie() -> None:
    """L'index est un ``DatetimeIndex`` croissant et les colonnes sont alphabétiques.

    Source : (a) un tableau long construit à la main dans le désordre, dates
    mélangées et symboles en ordre inverse. La sortie attendue est écrite ici,
    trois dates croissantes et deux colonnes de A puis B.
    """
    long = synthetic_long(
        dates=["2024-01-04", "2024-01-02", "2024-01-03"],
        symbols=["BBB", "AAA"],
        closes={"AAA": [3.0, 1.0, 2.0], "BBB": [30.0, 10.0, 20.0]},
    )
    long = long.sample(frac=1.0, random_state=7).reset_index(drop=True)
    wide = to_wide(long, field="adj_close")

    assert isinstance(wide.index, pd.DatetimeIndex)
    assert wide.index.is_monotonic_increasing
    assert wide.index.name == "date"
    assert list(wide.columns) == ["AAA", "BBB"]
    assert wide.columns.name == "symbol"
    assert list(wide.index) == [pd.Timestamp(d) for d in ("2024-01-02", "2024-01-03", "2024-01-04")]
    assert list(wide["AAA"]) == [1.0, 2.0, 3.0]
    assert list(wide["BBB"]) == [10.0, 20.0, 30.0]


def test_to_wide_aligne_sans_decaler_les_calendriers() -> None:
    """Un titre qui n'a pas coté reçoit une valeur absente, pas la valeur du voisin.

    Source : (b) l'alignement par la date. AAA cote trois séances, BBB seulement
    la première et la troisième, donc la case du 3 janvier est absente et celle
    du 4 janvier vaut 30,0.
    """
    long = synthetic_long(
        dates=["2024-01-02", "2024-01-03", "2024-01-04"],
        symbols=["AAA"],
        closes={"AAA": [1.0, 2.0, 3.0]},
    )
    manquant = synthetic_long(
        dates=["2024-01-02", "2024-01-04"],
        symbols=["BBB"],
        closes={"BBB": [10.0, 30.0]},
    )
    wide = to_wide(pd.concat([long, manquant], ignore_index=True), field="close")

    assert len(wide) == 3
    assert np.isnan(wide.loc[pd.Timestamp("2024-01-03"), "BBB"])
    assert wide.loc[pd.Timestamp("2024-01-04"), "BBB"] == 30.0


def test_to_wide_champ_inconnu_leve() -> None:
    """Demander une colonne qui n'est pas un champ de valeur est une erreur."""
    long = synthetic_long(dates=["2024-01-02"], symbols=["AAA"], closes={"AAA": [1.0]})
    with pytest.raises(ValueError, match="champ de valeur"):
        to_wide(long, field="symbol")


def test_to_wide_doublon_leve() -> None:
    """Un couple date et titre répété écraserait une valeur, donc il lève."""
    long = synthetic_long(dates=["2024-01-02"], symbols=["AAA"], closes={"AAA": [1.0]})
    with pytest.raises(DataQualityError, match="déjà vu"):
        to_wide(pd.concat([long, long], ignore_index=True))


def test_to_wide_tableau_vide_leve() -> None:
    """Un tableau long vide ne produit pas une matrice vide, il lève."""
    vide = synthetic_long(dates=["2024-01-02"], symbols=["AAA"], closes={"AAA": [1.0]}).iloc[:0]
    with pytest.raises(InsufficientDataError):
        to_wide(vide)


# --------------------------------------------------------------------------------------
# Propriétés
# --------------------------------------------------------------------------------------


@settings(max_examples=40, deadline=None)
@given(
    n_dates=st.integers(min_value=1, max_value=6),
    n_symbols=st.integers(min_value=1, max_value=4),
    prix=st.lists(
        st.floats(min_value=1.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False),
        min_size=24,
        max_size=24,
    ),
)
def test_propriete_aller_retour_long_puis_large(n_dates: int, n_symbols: int, prix: list[float]) -> None:
    """Chaque cellule du tableau large redonne la valeur de sa ligne longue.

    Source : (b) une identité algébrique. Le passage long vers large est une
    bijection sur les couples présents, donc ``wide.loc[date, symbol]`` égale la
    valeur de la ligne correspondante, à l'identique et sans tolérance.

    La propriété testée en même temps est le compte : sans barre absente, le
    nombre de lignes longues vaut le nombre de dates multiplié par le nombre de
    titres.
    """
    dates = pd.DatetimeIndex(pd.date_range("2024-01-02", periods=n_dates, freq="D"), name="Date")
    symbols = [f"SYM{i}" for i in range(n_symbols)]
    data: dict[tuple[str, str], list[float]] = {}
    for j, symbol in enumerate(symbols):
        base = [prix[(j * 6 + i) % len(prix)] for i in range(n_dates)]
        data[("Open", symbol)] = base
        data[("High", symbol)] = [v * 1.01 for v in base]
        data[("Low", symbol)] = [v * 0.99 for v in base]
        data[("Close", symbol)] = base
        data[("Adj Close", symbol)] = [v * 0.5 for v in base]
        data[("Volume", symbol)] = [1000.0] * n_dates
    columns = pd.MultiIndex.from_tuples(list(data), names=["Price", "Ticker"])
    raw = pd.DataFrame(data, index=dates)[columns]

    long = normalize(raw, tickers=symbols)
    assert len(long) == n_dates * n_symbols

    wide = to_wide(long, field="adj_close")
    assert list(wide.columns) == sorted(symbols)
    for row in long.itertuples(index=False):
        assert wide.loc[row.date, row.symbol] == row.adj_close


@settings(max_examples=25, deadline=None)
@given(graine=st.integers(min_value=0, max_value=10_000))
def test_propriete_invariance_a_l_ordre_des_lignes(graine: int) -> None:
    """L'ordre des lignes reçues ne change pas le tableau rendu.

    Source : (b) une invariance. La normalisation trie par date puis par titre,
    donc mélanger les lignes de la réponse de Yahoo doit rendre exactement le
    même tableau.
    """
    raw = recorded_frame()
    melange = raw.sample(frac=1.0, random_state=graine)
    pd.testing.assert_frame_equal(
        normalize(raw, tickers=["AAPL", "MSFT"]),
        normalize(melange, tickers=["AAPL", "MSFT"]),
    )


@settings(max_examples=25, deadline=None)
@given(facteur=st.floats(min_value=0.001, max_value=1000.0, allow_nan=False, allow_infinity=False))
def test_propriete_invariance_d_echelle(facteur: float) -> None:
    """Multiplier tous les prix par un facteur multiplie la sortie par ce facteur.

    Source : (b) l'homogénéité de degré un. La mise en forme ne fait aucune
    arithmétique, donc elle commute avec la multiplication par un scalaire.
    """
    raw = recorded_frame()
    mis_a_l_echelle = raw.copy()
    for colonne in raw.columns:
        if colonne[0] != "Volume":
            mis_a_l_echelle[colonne] = raw[colonne] * facteur

    attendu = normalize(raw, tickers=["AAPL", "MSFT"])
    obtenu = normalize(mis_a_l_echelle, tickers=["AAPL", "MSFT"])
    for champ in ("open", "high", "low", "close", "adj_close"):
        np.testing.assert_allclose(obtenu[champ].to_numpy(), attendu[champ].to_numpy() * facteur, rtol=1e-12)


# --------------------------------------------------------------------------------------
# Manifeste et limites déclarées
# --------------------------------------------------------------------------------------


def test_le_manifeste_declare_le_biais_de_survie() -> None:
    """Le manifeste dit faux là où la source ne garantit rien.

    Source : (c) la spécification du fournisseur et les limites publiées de
    Yahoo. Les trois champs de garantie sont écrits en dur dans le module, et ce
    test vérifie qu'ils ne peuvent pas devenir vrais par accident.
    """
    manifeste = YahooProvider().manifest(
        symbols=["AAPL", "MSFT"],
        start="2024-01-02",
        end="2024-01-04",
        interval="1d",
        rows=6,
    )
    assert isinstance(manifeste, DatasetManifest)
    assert manifeste.survivorship_free is False
    assert manifeste.point_in_time is False
    assert manifeste.adjusted is True
    assert manifeste.provider == "yahoo"
    assert manifeste.source == SOURCE_NAME == "Yahoo Finance"
    assert manifeste.license == LICENSE == "Yahoo, usage personnel"
    assert "recalculés à chaque dividende" in manifeste.revision_policy
    assert manifeste.data_start == dt.date(2024, 1, 2)
    assert manifeste.data_end == dt.date(2024, 1, 4)
    assert manifeste.frequency is Frequency.DAILY
    assert manifeste.layer is Layer.BRONZE
    assert manifeste.n_rows == 6
    assert manifeste.columns == SCHEMA
    assert manifeste.n_columns == len(SCHEMA) == 8
    assert manifeste.dataset_id == "yahoo-2titres-1d-2024-01-02-2024-01-04"
    assert manifeste.download_timestamp.tzinfo is not None
    # Les limites connues voyagent dans le manifeste, pour le lecteur du fichier
    # de métadonnées qui n'ouvrira jamais le code source.
    assert "Biais de survie" in manifeste.notes


def test_le_manifeste_nomme_le_titre_quand_il_est_seul() -> None:
    """Un univers d'un seul titre donne un identifiant qui le nomme.

    Source : (a) la règle écrite dans le module, appliquée à la main. Un seul
    titre, « SPY », donne « yahoo-spy-1d-2024-01-02-2024-01-04 ».
    """
    manifeste = YahooProvider().manifest(symbols="SPY", start="2024-01-02", end="2024-01-04")
    assert manifeste.dataset_id == "yahoo-spy-1d-2024-01-02-2024-01-04"


def test_le_manifeste_nettoie_les_tickers_d_indice() -> None:
    """L'accent circonflexe d'un indice ne se retrouve pas dans un nom de fichier.

    Source : (a) la règle de nettoyage, appliquée à la main. « ^GSPC » devient
    « gspc », les caractères hors alphanumériques étant remplacés puis élagués.
    """
    manifeste = YahooProvider().manifest(symbols="^GSPC", start="2024-01-02", end="2024-01-04")
    assert manifeste.dataset_id == "yahoo-gspc-1d-2024-01-02-2024-01-04"


def test_le_manifeste_dit_ce_que_les_ajustements_ont_fait() -> None:
    """Le champ des actions de société distingue les deux modes de Yahoo.

    Source : (d) le comportement mesuré de yfinance 1.7.0 le 2026-09-01. Avec
    ``auto_adjust=True`` la réponse ne porte aucune colonne « Adj Close » et son
    close est déjà corrigé, avec ``auto_adjust=False`` les deux colonnes
    coexistent.
    """
    commun = {"symbols": "SPY", "start": "2024-01-02", "end": "2024-01-04"}
    assert (
        "adj_close recopie ce close" in YahooProvider().manifest(auto_adjust=True, **commun).corporate_actions
    )
    assert "close brut" in YahooProvider().manifest(auto_adjust=False, **commun).corporate_actions


def test_le_manifeste_laisse_vide_ce_qui_n_est_pas_mesure() -> None:
    """La devise et l'adresse de licence restent vides plutôt que devinées.

    Source : (c) la règle du laboratoire sur le statut des chiffres. Une
    information absente s'écrit absente. La réponse de ``yfinance.download`` ne
    nomme aucune devise, mesuré le 2026-09-01, et l'adresse des conditions
    d'utilisation de Yahoo n'a pas été vérifiée.
    """
    manifeste = YahooProvider().manifest(symbols="SPY", start="2024-01-02", end="2024-01-04")
    assert manifeste.currency == ""
    assert manifeste.license_url is None
    assert "currency" in manifeste.missing_for_gold()


def test_le_manifeste_refuse_un_intervalle_intrajournalier() -> None:
    """Un pas plus fin que la séance n'a pas de fréquence, donc il lève.

    Source : (b) l'énumération ``Frequency``, dont la plus fine valeur est la
    séance quotidienne. Rien dans le laboratoire ne sait annualiser un pas de
    cinq minutes, donc le manifeste refuse de l'écrire.
    """
    with pytest.raises(ConfigError, match=r"n.a pas d.équivalent dans Frequency"):
        YahooProvider().manifest(symbols="SPY", start="2024-01-02", end="2024-01-04", interval="5m")


def test_le_manifeste_se_serialise() -> None:
    """Le manifeste rend un dictionnaire dont les dates sont des textes ISO.

    Source : (a) les dates passées à la main, 2024-01-02 et 2024-01-04.
    """
    payload = (
        YahooProvider()
        .manifest(symbols="SPY", start="2024-01-02", end="2024-01-04", rows=2)
        .model_dump(mode="json")
    )
    assert payload["data_start"] == "2024-01-02"
    assert payload["data_end"] == "2024-01-04"
    assert payload["survivorship_free"] is False
    assert payload["layer"] == "bronze"


def test_le_manifeste_sans_telechargement_leve() -> None:
    """Sans téléchargement ni description explicite, il n'y a rien à déclarer."""
    with pytest.raises(ConfigError, match="téléchargement préalable"):
        YahooProvider().manifest()


def test_le_manifeste_refuse_une_cle_inconnue() -> None:
    """Une clé mal orthographiée est refusée, pas ignorée."""
    with pytest.raises(ValueError, match="inconnues"):
        YahooProvider().manifest(symbols="SPY", start="2024-01-02", end="2024-01-04", lignes=2)


def test_les_limites_connues_sont_ecrites() -> None:
    """Les quatre limites de la source sont nommées, aucune n'est vague.

    Source : (c) la spécification du module. Quatre limites sont exigées, le
    biais de survie, l'absence de calendrier point-in-time des indices, les
    ajustements rétroactifs et l'absence de carnet d'ordres.
    """
    assert len(KNOWN_LIMITATIONS) == 4
    texte = " ".join(KNOWN_LIMITATIONS).lower()
    for mot in ("survie", "point-in-time", "rétroactif", "carnet d'ordres"):
        assert mot in texte
    assert all(len(limite) > 60 for limite in KNOWN_LIMITATIONS)


def test_le_fournisseur_satisfait_le_protocole() -> None:
    """Le fournisseur porte ``name``, ``fetch`` et ``manifest``, donc il est branchable.

    Source : (b) le protocole structurel ``DataProvider``, déclaré
    ``runtime_checkable`` dans ``quantlab.core.protocols``.
    """
    assert isinstance(YahooProvider(), DataProvider)
    assert YahooProvider().name == "yahoo"


def test_fetch_refuse_une_periode_a_l_envers() -> None:
    """Une fin qui précède le début est refusée avant toute requête réseau."""
    with pytest.raises(ValueError, match="doit précéder"):
        YahooProvider().fetch("SPY", start="2024-02-01", end="2024-01-01")


def test_fetch_refuse_un_univers_vide() -> None:
    """Une liste d'identifiants vide est refusée avant toute requête réseau."""
    with pytest.raises(ValueError, match="aucun identifiant"):
        YahooProvider().fetch([], start="2024-01-02", end="2024-01-04")


# --------------------------------------------------------------------------------------
# Le téléchargement, joué hors réseau contre un faux yfinance
#
# Sans ces tests, la totalité de fetch() ne serait vérifiée que par le test réseau,
# que l'intégration continue exclut. Mesuré le 2026-09-01 en réintroduisant quatre
# bogues dans fetch() : la borne haute non corrigée, le mode d'ajustement inversé,
# l'empreinte vidée et les colonnes retournées, aucun des trente-cinq tests hors
# réseau ne bronchait, et trois des quatre passaient même le test réseau.
# --------------------------------------------------------------------------------------


class FauxYfinance:
    """Rend la réponse enregistrée et retient les arguments reçus.

    L'objet remplace le module ``yfinance`` dans ``sys.modules``, que
    :meth:`YahooProvider.fetch` importe localement. Il compte ses appels et
    peut échouer les ``echecs`` premiers, ce qui rend la relance observable.
    """

    def __init__(self, *, echecs: int = 0, frame: pd.DataFrame | None = None) -> None:
        self.appels: list[dict[str, Any]] = []
        self.echecs = echecs
        self.frame = recorded_frame() if frame is None else frame

    def download(self, **kwargs: Any) -> pd.DataFrame:
        self.appels.append(kwargs)
        if len(self.appels) <= self.echecs:
            raise ConnectionError("panne simulée")
        return self.frame.copy()


@pytest.fixture
def faux_yahoo(monkeypatch: pytest.MonkeyPatch) -> FauxYfinance:
    """Installe le faux module et le rend au test."""
    faux = FauxYfinance()
    monkeypatch.setitem(sys.modules, "yfinance", faux)
    return faux


def test_fetch_corrige_la_borne_haute_exclusive(faux_yahoo: FauxYfinance) -> None:
    """La fin demandée est incluse, donc la requête part un jour plus loin.

    Source : (a) un calcul à la main. Yahoo exclut sa borne haute, mesuré le
    2026-09-01. Pour que le 2024-01-04 soit rendu, la requête doit porter
    2024-01-04 + 1 jour = 2024-01-05. Le début, lui, ne bouge pas.

    Le test lit l'argument reçu par le faux module, et non la sortie du code :
    c'est la requête envoyée à Yahoo qui décide de ce qui manque.
    """
    frame = YahooProvider().fetch(["AAPL", "MSFT"], start="2024-01-02", end="2024-01-04")

    assert len(faux_yahoo.appels) == 1
    envoye = faux_yahoo.appels[0]
    assert envoye["start"] == "2024-01-02"
    assert envoye["end"] == "2024-01-05"
    assert envoye["interval"] == "1d"
    assert envoye["tickers"] == ["AAPL", "MSFT"]
    # (b) Le contrat du module : la sortie porte le schéma, dans l'ordre du schéma.
    assert list(frame.columns) == list(SCHEMA)
    # (a) Trois dates fois deux titres font six lignes.
    assert len(frame) == 6


def test_fetch_sans_borne_incluse_ne_deplace_pas_la_fin(faux_yahoo: FauxYfinance) -> None:
    """Avec ``end_inclusive=False``, la date part telle quelle.

    Source : (a) la date passée à la main, 2024-01-04, qui doit se retrouver
    inchangée dans l'appel.
    """
    YahooProvider().fetch(["AAPL", "MSFT"], start="2024-01-02", end="2024-01-04", end_inclusive=False)
    assert faux_yahoo.appels[0]["end"] == "2024-01-04"


@pytest.mark.parametrize("mode", [True, False])
def test_fetch_transmet_le_mode_d_ajustement(faux_yahoo: FauxYfinance, mode: bool) -> None:
    """Le mode d'ajustement demandé arrive intact chez Yahoo, et dans le manifeste.

    Source : (b) une identité de transmission. Un mode inversé en route rendrait
    des prix bruts sous un manifeste qui annonce des prix ajustés, faute qu'aucun
    contrôle en aval ne peut voir.
    """
    YahooProvider().fetch(["AAPL", "MSFT"], start="2024-01-02", end="2024-01-04", auto_adjust=mode)
    assert faux_yahoo.appels[0]["auto_adjust"] is mode

    actions = (
        YahooProvider()
        .manifest(symbols=["AAPL"], start="2024-01-02", end="2024-01-04", auto_adjust=mode)
        .corporate_actions
    )
    assert ("adj_close recopie ce close" in actions) is mode
    assert ("close brut" in actions) is not mode


def test_le_manifeste_apres_telechargement_porte_l_empreinte(faux_yahoo: FauxYfinance) -> None:
    """Le manifeste rattache le tableau rendu par son empreinte SHA-256.

    Source : (d) une implémentation indépendante. L'empreinte attendue est
    recalculée ici par ``sha256_frame`` appliqué au tableau rendu, sans passer
    par le fournisseur. Une empreinte vide, ou celle d'un autre tableau, casse
    le lien entre le manifeste et la donnée qu'il décrit.
    """
    provider = YahooProvider()
    frame = provider.fetch(["AAPL", "MSFT"], start="2024-01-02", end="2024-01-04")
    manifeste = provider.manifest()

    assert manifeste.checksum_sha256 == sha256_frame(frame)
    assert len(manifeste.checksum_sha256) == 64  # (c) SHA-256 s'écrit sur 64 chiffres hexadécimaux.
    # (a) Six lignes comptées à la main, et les bornes demandées telles quelles.
    assert manifeste.n_rows == 6
    assert manifeste.data_start == dt.date(2024, 1, 2)
    assert manifeste.data_end == dt.date(2024, 1, 4)
    assert manifeste.dataset_id == "yahoo-2titres-1d-2024-01-02-2024-01-04"


def test_fetch_relance_puis_reussit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deux pannes suivies d'une réponse donnent trois appels et un tableau.

    Source : (a) un calcul à la main. Deux échecs plus une réussite font trois
    appels, ce que compte le faux module.
    """
    faux = FauxYfinance(echecs=2)
    monkeypatch.setitem(sys.modules, "yfinance", faux)
    frame = YahooProvider(max_retries=3, retry_delay_s=0.0).fetch(
        ["AAPL", "MSFT"], start="2024-01-02", end="2024-01-04"
    )
    assert len(faux.appels) == 3
    assert len(frame) == 6


def test_fetch_abandonne_apres_ses_tentatives(monkeypatch: pytest.MonkeyPatch) -> None:
    """Une source muette lève, après exactement le nombre de tentatives demandé.

    Source : (a) le compte demandé, deux tentatives, retrouvé dans le compteur du
    faux module et dans le message.
    """
    faux = FauxYfinance(echecs=99)
    monkeypatch.setitem(sys.modules, "yfinance", faux)
    with pytest.raises(DataQualityError, match="2 tentatives"):
        YahooProvider(max_retries=2, retry_delay_s=0.0).fetch("AAPL", start="2024-01-02", end="2024-01-04")
    assert len(faux.appels) == 2


def test_fetch_interroge_yahoo_meme_avec_zero_tentative(faux_yahoo: FauxYfinance) -> None:
    """Un nombre de tentatives nul est ramené à une, pas à aucune.

    Source : (b) le contrat du module. Sortir de la boucle sans avoir appelé la
    source produirait une erreur qui parle d'une source muette alors que
    personne ne l'a interrogée. Le plancher vaut une tentative.
    """
    frame = YahooProvider(max_retries=0).fetch(["AAPL", "MSFT"], start="2024-01-02", end="2024-01-04")
    assert len(faux_yahoo.appels) == 1
    assert len(frame) == 6


def test_le_manifeste_refuse_le_pas_de_cinq_seances() -> None:
    """« 5d » n'a pas de fréquence nommée, et le message ne prétend pas l'inverse.

    Source : (b) l'énumération ``Frequency``, qui nomme la séance, la semaine, le
    mois, le trimestre et l'année, et rien entre la séance et la semaine. Le
    message ne doit pas expliquer ce refus par un pas trop fin : cinq séances
    sont plus grossières qu'une, pas plus fines.
    """
    with pytest.raises(ConfigError) as capture:
        YahooProvider().manifest(symbols="SPY", start="2024-01-02", end="2024-01-04", interval="5d")
    message = str(capture.value)
    assert "5d" in message
    assert "ne descend pas sous la séance" not in message


# --------------------------------------------------------------------------------------
# Le seul test qui sort sur le réseau
# --------------------------------------------------------------------------------------


@pytest.mark.network
def test_telechargement_reel_dun_titre() -> None:
    """Une vraie requête sur un titre rend le schéma et des dates dans la fenêtre.

    Le contenu n'est pas comparé à des valeurs fixes : les prix ajustés de Yahoo
    changent à chaque dividende, donc un test de valeur serait faux dès le
    prochain détachement. Seule la forme est vérifiée.
    """
    frame = YahooProvider().fetch("SPY", start="2024-01-02", end="2024-01-31")

    assert list(frame.columns) == list(SCHEMA)
    assert set(frame["symbol"]) == {"SPY"}
    assert len(frame) >= 15
    assert frame["date"].min() >= pd.Timestamp("2024-01-02")
    assert frame["date"].max() <= pd.Timestamp("2024-01-31")
    assert frame.duplicated(subset=["date", "symbol"]).sum() == 0
    assert (frame["high"] >= frame["low"]).all()

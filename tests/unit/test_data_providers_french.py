"""Tests du lecteur de la bibliothèque de Kenneth French.

Aucune valeur attendue de ce fichier ne vient de la sortie du code. Chacune est
annoncée dans le commentaire du test avec sa source, parmi les quatre suivantes :

(a) un calcul à la main, chiffres visibles dans le commentaire ;
(b) une identité mathématique ou une propriété structurelle ;
(c) une valeur publiée, ici les lignes littérales des fichiers
    « F-F_Research_Data_Factors.CSV », téléchargé le 2026-09-01, et
    « 10_Portfolios_Prior_12_2.CSV », « 10_Portfolios_Prior_1_0.CSV »,
    « Portfolios_Formed_on_OP.CSV » et « 25_Portfolios_ME_Prior_12_2.CSV »,
    téléchargés le 2026-09-02. Tous sont du millésime CRSP 202606 de la
    bibliothèque de Kenneth R. French ;
(d) une implémentation indépendante.

L'analyse syntaxique se teste entièrement hors réseau : l'extrait ci-dessous est
recopié tel quel du fichier réel, à un saut près entre décembre 1926 et
septembre 1936, marqué dans le commentaire.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import io
import zipfile

import numpy as np
import pandas as pd
import pytest
from hypothesis import HealthCheck, given
from hypothesis import settings as hyp_settings
from hypothesis import strategies as st

from quantlab.core.config import Settings
from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.protocols import DataProvider
from quantlab.core.types import Frequency
from quantlab.data.providers.base import HttpClient, RawResponse, cache_key
from quantlab.data.providers.french import (
    BENCHMARK_COLUMNS,
    LOSER_DECILE,
    MISSING_CODES,
    MOMENTUM_DECILE_COLUMNS,
    PERIOD_MARKER,
    SPREAD_NAME,
    WINNER_DECILE,
    FrenchProvider,
    available_datasets,
    combine_benchmark_factors,
    decile_spread,
    parse_french_csv,
    select_return_block,
    slice_period,
)

# --------------------------------------------------------------------------- #
# Source (c) : lignes littérales de « F-F_Research_Data_Factors.CSV », millésime
# 202606. Les lignes 1 à 11 sont les onze premières du fichier. La ligne
# « 193609 » est la ligne 128 du même fichier, insérée ici parce qu'elle porte la
# valeur 0,97 qui sert au test de conversion. Les six dernières lignes sont
# celles du tableau annuel, à partir de sa ligne de titre.
# --------------------------------------------------------------------------- #
EXTRAIT_TROIS_FACTEURS = """This file was created using the 202606 CRSP database.
The 1-month TBill rate data until 202405 are from Ibbotson Associates. Starting from 202406, the 1-month TBill rate is from ICE BofA US 1-Month Treasury Bill Index. 
The annual TBill return is compounded from the monthly T-bill rates from January to December. 

,Mkt-RF,SMB,HML,RF
192607,   2.89,  -2.55,  -2.39,   0.22
192608,   2.64,  -1.14,   3.81,   0.25
192609,   0.38,  -1.36,   0.05,   0.23
192610,  -3.27,  -0.14,   0.82,   0.32
192611,   2.54,  -0.11,  -0.61,   0.31
192612,   2.62,  -0.07,   0.06,   0.28
193609,   0.97,   3.12,   0.94,   0.01

 Annual Factors: January-December 
,Mkt-RF,SMB,HML,RF
  1927,  29.44,  -2.20,  -4.58,   3.12
  1928,  35.56,   3.73,  -5.26,   3.56
  1929, -19.58, -30.68,  11.86,   4.75
  1930, -31.14,  -5.53, -11.76,   2.41

Copyright 2026 Eugene F. Fama and Kenneth R. French
"""

# Extrait FABRIQUÉ, au format du fichier réel, portant les deux codes de
# manquant que l'en-tête des fichiers de portefeuilles déclare : « Missing data
# are indicated by -99.99 or -999. » Le rendement de -100,00 est le cas limite
# de la perte totale, qui doit rester une valeur et non un manquant.
EXTRAIT_MANQUANTS = """Fichier fabriqué pour le test, format identique au fichier réel.

,Mkt-RF,SMB,HML,RF
193301, -99.99,   1.00,   2.00,   0.02
193302,   1.00,-999.00,   2.00,   0.02
193303,-100.00,    -999,   2.00,   0.02
"""

# Extrait FABRIQUÉ reprenant deux titres littéraux du fichier
# « 25_Portfolios_5x5.CSV » : un tableau de rendements et un tableau de comptes.
# Le second ne doit PAS être divisé par 100.
EXTRAIT_DEUX_NATURES = """This file was created using the 202606 CRSP database.

  Average Value Weighted Returns -- Monthly
,SMALL LoBM,BIG HiBM
192607,   1.0866,   2.0068
192608,   0.7831,   5.6834

  Number of Firms in Portfolios
,SMALL LoBM,BIG HiBM
192607,      7,     35
192608,      7,     35
"""


def _parse_extrait() -> object:
    """Analyse l'extrait littéral une fois, pour les tests qui le partagent."""
    return parse_french_csv(EXTRAIT_TROIS_FACTEURS)


# --------------------------------------------------------------------------- #
# Découpage et datation
# --------------------------------------------------------------------------- #
def test_le_fichier_porte_deux_tableaux() -> None:
    """Source (c) : le fichier réel empile un tableau mensuel et un annuel."""
    parsed = _parse_extrait()
    assert len(parsed) == 2
    assert parsed.names == ("monthly", "annual_factors_january_december")
    assert parsed.blocks[0].frequency is Frequency.MONTHLY
    assert parsed.blocks[1].frequency is Frequency.ANNUAL
    # Source (c) : le titre est écrit ligne 1207 du fichier réel, son en-tête de
    # colonnes ligne 1208 et sa première observation ligne 1209.
    assert parsed.blocks[1].title == "Annual Factors: January-December"


def test_les_dates_mensuelles_sont_portees_a_la_fin_du_mois() -> None:
    """Source (a) : 192607 est juillet 1926, dont le dernier jour est le 31."""
    mensuel = _parse_extrait()["monthly"]
    assert mensuel.index[0] == pd.Timestamp("1926-07-31")
    assert mensuel.index[5] == pd.Timestamp("1926-12-31")
    # Septembre 1936 compte 30 jours, donc le 30 et non le 31.
    assert mensuel.index[6] == pd.Timestamp("1936-09-30")
    assert mensuel.index.name == "date"


def test_les_dates_annuelles_sont_portees_au_31_decembre() -> None:
    """Source (a) : 1927 est l'année 1927, dont le dernier jour est le 31 décembre."""
    annuel = _parse_extrait()["annual_factors_january_december"]
    assert list(annuel.index) == [
        pd.Timestamp("1927-12-31"),
        pd.Timestamp("1928-12-31"),
        pd.Timestamp("1929-12-31"),
        pd.Timestamp("1930-12-31"),
    ]


def test_la_position_de_date_au_debut_est_disponible() -> None:
    """Source (a) : en position « start », juillet 1926 commence le 1er."""
    mensuel = parse_french_csv(EXTRAIT_TROIS_FACTEURS, date_position="start")["monthly"]
    assert mensuel.index[0] == pd.Timestamp("1926-07-01")


def test_le_preambule_et_la_mention_de_droit_dauteur_sont_conserves() -> None:
    """Source (c) : première et dernière lignes de texte du fichier réel."""
    parsed = _parse_extrait()
    assert parsed.preamble.startswith("This file was created using the 202606 CRSP database.")
    assert parsed.trailer == "Copyright 2026 Eugene F. Fama and Kenneth R. French"
    # Le préambule ne doit nommer aucun tableau.
    assert "this_file_was_created" not in parsed.names


# --------------------------------------------------------------------------- #
# Conversion de pourcentage
# --------------------------------------------------------------------------- #
def test_conversion_du_pourcentage_en_decimales() -> None:
    """Source (a) : 0,97 % vaut 0,97 / 100 = 0,0097, et 2,89 % vaut 0,0289."""
    mensuel = _parse_extrait()["monthly"]
    assert float(mensuel.loc["1936-09-30", "MKT-RF"]) == pytest.approx(0.0097, rel=1e-12)
    assert float(mensuel.loc["1926-07-31", "MKT-RF"]) == pytest.approx(0.0289, rel=1e-12)
    # -2,55 % vaut -0,0255, le signe étant conservé.
    assert float(mensuel.loc["1926-07-31", "SMB"]) == pytest.approx(-0.0255, rel=1e-12)
    # Le taux sans risque suit la même règle : 0,22 % par mois vaut 0,0022.
    assert float(mensuel.loc["1926-07-31", "RF"]) == pytest.approx(0.0022, rel=1e-12)


def test_conversion_du_tableau_annuel() -> None:
    """Source (a) : 29,44 % vaut 0,2944 et -19,58 % vaut -0,1958."""
    annuel = _parse_extrait()["annual_factors_january_december"]
    assert float(annuel.loc["1927-12-31", "MKT-RF"]) == pytest.approx(0.2944, rel=1e-12)
    assert float(annuel.loc["1929-12-31", "MKT-RF"]) == pytest.approx(-0.1958, rel=1e-12)


def _lecture_independante(lignes: list[str], format_date: str, fin_de_periode) -> pd.DataFrame:
    """Relit un tableau avec ``pandas.read_csv``, sans passer par le module."""
    frame = pd.read_csv(io.StringIO("\n".join(lignes)), index_col=0)
    frame.index = pd.to_datetime(frame.index.astype(str).str.strip(), format=format_date) + fin_de_periode
    frame.columns = [str(nom).strip().upper() for nom in frame.columns]
    return frame / 100.0


def test_la_lecture_redonne_ce_que_pandas_lit_sur_les_memes_lignes() -> None:
    """Source (d) : implémentation indépendante, ``pandas.read_csv`` par tranches.

    Le découpage automatique doit rendre exactement ce qu'un lecteur obtiendrait
    en donnant à ``pandas`` les bornes de chaque tableau à la main. Les tranches
    sont comptées sur l'extrait : l'en-tête mensuel est la cinquième ligne et
    porte sept observations, l'en-tête annuel la quinzième et en porte quatre.
    """
    lignes = EXTRAIT_TROIS_FACTEURS.split("\n")
    parsed = _parse_extrait()
    attendus = {
        "monthly": _lecture_independante(lignes[4:12], "%Y%m", pd.offsets.MonthEnd(0)),
        "annual_factors_january_december": _lecture_independante(lignes[14:19], "%Y", pd.offsets.YearEnd(0)),
    }
    for nom, attendu in attendus.items():
        obtenu = parsed[nom]
        assert list(obtenu.columns) == list(attendu.columns)
        assert list(obtenu.index) == list(attendu.index)
        np.testing.assert_allclose(obtenu.to_numpy(), attendu.to_numpy(), rtol=0.0, atol=1e-15)


def test_les_colonnes_sont_mises_en_majuscules() -> None:
    """Source (b) : « Mkt-RF » et « MKT-RF » doivent désigner la même colonne."""
    assert list(_parse_extrait()["monthly"].columns) == ["MKT-RF", "SMB", "HML", "RF"]
    brut = parse_french_csv(EXTRAIT_TROIS_FACTEURS, uppercase_columns=False)["monthly"]
    assert list(brut.columns) == ["Mkt-RF", "SMB", "HML", "RF"]


def test_un_tableau_qui_nest_pas_en_pourcentage_nest_pas_divise() -> None:
    """Source (a) : sept sociétés restent sept, et 1,0866 % devient 0,010866."""
    parsed = parse_french_csv(EXTRAIT_DEUX_NATURES)
    assert parsed.names == (
        "average_value_weighted_returns_monthly",
        "number_of_firms_in_portfolios",
    )
    rendements = parsed["average_value_weighted_returns_monthly"]
    comptes = parsed["number_of_firms_in_portfolios"]
    assert float(rendements.loc["1926-07-31", "SMALL LOBM"]) == pytest.approx(0.010866, rel=1e-12)
    assert float(comptes.loc["1926-07-31", "SMALL LOBM"]) == 7.0
    assert float(comptes.loc["1926-07-31", "BIG HIBM"]) == 35.0
    assert parsed.blocks[0].in_percent is True
    assert parsed.blocks[1].in_percent is False


# --------------------------------------------------------------------------- #
# Codes de manquant
# --------------------------------------------------------------------------- #
def test_les_codes_de_manquant_deviennent_des_nan() -> None:
    """Source (c) : « Missing data are indicated by -99.99 or -999. »

    Le piège est l'ordre des opérations. Divisé avant d'être reconnu, -99,99
    donnerait -0,9999, soit une perte de 99,99 %, parfaitement plausible.
    """
    frame = parse_french_csv(EXTRAIT_MANQUANTS)["monthly"]
    assert np.isnan(frame.loc["1933-01-31", "MKT-RF"])
    assert np.isnan(frame.loc["1933-02-28", "SMB"])
    # « -999 » sans décimale est le même code.
    assert np.isnan(frame.loc["1933-03-31", "SMB"])
    # Aucune valeur du tableau ne vaut -0,9999 : ce serait le code divisé.
    assert not np.isclose(frame.to_numpy(), -0.9999, atol=1e-9).any()


def test_une_perte_totale_reste_une_valeur() -> None:
    """Source (a) : -100,00 % vaut -1,0, et ce n'est pas un manquant."""
    frame = parse_french_csv(EXTRAIT_MANQUANTS)["monthly"]
    assert float(frame.loc["1933-03-31", "MKT-RF"]) == pytest.approx(-1.0, rel=1e-12)


def test_les_valeurs_ordinaires_survivent_aux_manquants_voisins() -> None:
    """Source (a) : 1,00 % vaut 0,01, même sur une ligne qui porte un code."""
    frame = parse_french_csv(EXTRAIT_MANQUANTS)["monthly"]
    assert float(frame.loc["1933-01-31", "SMB"]) == pytest.approx(0.01, rel=1e-12)
    assert float(frame.loc["1933-02-28", "MKT-RF"]) == pytest.approx(0.01, rel=1e-12)


# --------------------------------------------------------------------------- #
# Cas limites
# --------------------------------------------------------------------------- #
def test_texte_vide() -> None:
    """Source (b) : un fichier sans tableau ne porte aucun tableau."""
    parsed = parse_french_csv("")
    assert len(parsed) == 0
    with pytest.raises(InsufficientDataError):
        _ = parsed.primary


def test_texte_sans_tableau() -> None:
    """Source (b) : un fichier de prose seule ne porte aucun tableau."""
    parsed = parse_french_csv("This file was created using the 202606 CRSP database.\n")
    assert len(parsed) == 0
    assert parsed.preamble.startswith("This file")


def test_tableau_dune_seule_ligne() -> None:
    """Source (a) : une seule observation reste une observation."""
    parsed = parse_french_csv(",Mkt-RF\n19260701,    0.09\n")
    frame = parsed.primary
    assert frame.shape == (1, 1)
    assert frame.index[0] == pd.Timestamp("1926-07-01")
    assert float(frame.iloc[0, 0]) == pytest.approx(0.0009, rel=1e-12)
    assert parsed.blocks[0].frequency is Frequency.DAILY


def test_la_frequence_se_deduit_de_lecart_median_entre_dates() -> None:
    """Source (a) : un écart médian de 1 jour est quotidien, de 7 hebdomadaire.

    Du 19260201 au 19260205, les quatre écarts valent 1 jour, donc la médiane
    vaut 1, sous le seuil de 4 jours. Du 19260101 au 19260122 de sept en sept,
    les trois écarts valent 7 jours, donc la médiane vaut 7, au-dessus du seuil.
    Aucun fichier ne déclare sa fréquence : elle se lit sur les dates seules.
    """
    quotidien = ",Mkt-RF\n" + "".join(f"1926020{j},   1.00\n" for j in range(1, 6))
    hebdomadaire = ",Mkt-RF\n" + "".join(f"192601{j:02d},   1.00\n" for j in (1, 8, 15, 22))
    assert parse_french_csv(quotidien).blocks[0].frequency is Frequency.DAILY
    assert parse_french_csv(hebdomadaire).blocks[0].frequency is Frequency.WEEKLY
    # Le seuil est un argument, pas une constante cachée : au-dessus de 7 jours,
    # le tableau hebdomadaire repasse du côté quotidien.
    deplace = parse_french_csv(hebdomadaire, weekly_gap_threshold_days=8.0)
    assert deplace.blocks[0].frequency is Frequency.DAILY


def test_tableau_constant() -> None:
    """Source (b) : une série constante garde sa constante, sans variance."""
    texte = ",Mkt-RF\n192601,   1.00\n192602,   1.00\n192603,   1.00\n"
    frame = parse_french_csv(texte).primary
    assert float(frame["MKT-RF"].std(ddof=1)) == pytest.approx(0.0, abs=1e-15)
    np.testing.assert_allclose(frame["MKT-RF"].to_numpy(), 0.01, rtol=0.0, atol=1e-15)


def test_champ_vide_devient_nan() -> None:
    """Source (b) : un champ vide est une valeur absente, pas un zéro."""
    frame = parse_french_csv(",Mkt-RF,SMB\n192601,   1.00,\n").primary
    assert np.isnan(frame.loc["1926-01-31", "SMB"])


def test_lignes_de_largeurs_inegales_sont_refusees() -> None:
    """Source (b) : trois champs dans un tableau à deux colonnes est une faute."""
    texte = ",Mkt-RF,SMB\n192601,   1.00,   2.00\n192602,   1.00,   2.00,   3.00\n"
    with pytest.raises(DataQualityError, match="champs attendus"):
        parse_french_csv(texte)


def test_dates_de_longueurs_melees_sont_refusees() -> None:
    """Source (b) : un tableau mêlant AAAAMM et AAAAMMJJ n'a pas de fréquence."""
    texte = ",Mkt-RF\n192601,   1.00\n19260102,   1.00\n"
    with pytest.raises(DataQualityError, match="longueurs mêlées"):
        parse_french_csv(texte)


def test_valeur_non_numerique_est_refusee() -> None:
    """Source (b) : « n/a » n'est pas un nombre, et le silence serait pire."""
    texte = ",Mkt-RF\n192601,    n/a\n"
    with pytest.raises(DataQualityError, match="n'est pas un nombre"):
        parse_french_csv(texte)


def test_fins_de_ligne_crlf_et_retour_chariot_isole() -> None:
    """Source (c) : le fichier réel mêle CRLF et retour chariot isolé.

    Mesuré le 2026-09-01 dans « 6_Portfolios_2x3.CSV » : quinze retours chariot
    isolés, répartis sur les lignes 2527, 5037, 6241, 7445 et 8205. Celui de la
    ligne 2527 précède l'en-tête du quatrième tableau.
    """
    texte = "Preambule\r\n\r\n  Average Value Weighted Returns -- Monthly\r\n\r,Mkt-RF\r\n192601,   1.00\r\n"
    parsed = parse_french_csv(texte)
    assert parsed.names == ("average_value_weighted_returns_monthly",)
    assert float(parsed.primary.iloc[0, 0]) == pytest.approx(0.01, rel=1e-12)


def test_noms_en_collision_recoivent_un_suffixe() -> None:
    """Source (b) : deux tableaux ne peuvent pas porter la même clé."""
    texte = (
        "  For portfolios formed in June of year t\n"
        ",A\n192601,   1.00\n\n"
        "  For portfolios formed in June of year t\n"
        ",A\n192601,   2.00\n"
    )
    parsed = parse_french_csv(texte)
    assert parsed.names == (
        "for_portfolios_formed_in_june_of_year_t",
        "for_portfolios_formed_in_june_of_year_t_2",
    )


def test_tableau_sans_en_tete_recoit_des_noms_generes() -> None:
    """Source (b) : sans en-tête, les colonnes se nomment par leur position."""
    parsed = parse_french_csv("192601,   1.00,   2.00\n")
    assert list(parsed.primary.columns) == ["V1", "V2"]


# --------------------------------------------------------------------------- #
# Propriétés
# --------------------------------------------------------------------------- #
@given(
    valeurs=st.lists(
        st.integers(min_value=-5_000, max_value=5_000)
        .map(lambda n: n / 100.0)
        .filter(lambda v: not any(abs(v - code) < 1e-9 for code in MISSING_CODES)),
        min_size=1,
        # Douze au plus : les dates fabriquées sont les douze mois de 1926.
        max_size=12,
    )
)
@hyp_settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_propriete_la_conversion_est_exactement_une_division_par_cent(valeurs: list[float]) -> None:
    """Source (b) : identité algébrique, parse(v) x 100 = v pour tout v publié.

    La conversion est linéaire, donc réversible. Si le multiplicateur inverse ne
    rend pas la valeur écrite, c'est que le lecteur a fait autre chose qu'une
    division.
    """
    lignes = "".join(f"1926{mois + 1:02d},{valeur:8.2f}\n" for mois, valeur in enumerate(valeurs))
    frame = parse_french_csv(",Mkt-RF\n" + lignes).primary
    retrouve = frame["MKT-RF"].to_numpy() * 100.0
    np.testing.assert_allclose(retrouve, np.array(valeurs), rtol=0.0, atol=1e-9)


@given(
    positions=st.lists(st.booleans(), min_size=1, max_size=12),
    code=st.sampled_from(MISSING_CODES),
)
@hyp_settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_propriete_un_code_de_manquant_donne_toujours_un_nan(positions: list[bool], code: float) -> None:
    """Source (b) : le nombre de NaN égale le nombre de codes écrits."""
    lignes = "".join(
        f"1926{mois + 1:02d},{code if manquant else 1.25:8.2f}\n" for mois, manquant in enumerate(positions)
    )
    frame = parse_french_csv(",Mkt-RF\n" + lignes).primary
    assert int(frame["MKT-RF"].isna().sum()) == sum(positions)
    valides = frame["MKT-RF"].dropna().to_numpy()
    np.testing.assert_allclose(valides, 0.0125, rtol=0.0, atol=1e-12)


@given(
    titre=st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=122), max_size=60),
    max_mots=st.integers(min_value=1, max_value=8),
)
def test_propriete_un_nom_de_tableau_est_toujours_un_identifiant_sobre(titre: str, max_mots: int) -> None:
    """Source (b) : un nom court ne porte que des minuscules, chiffres et soulignés."""
    from quantlab.data.providers.french import _slugify

    nom = _slugify(titre, max_mots)
    assert set(nom) <= set("abcdefghijklmnopqrstuvwxyz0123456789_")
    if nom:
        assert len(nom.split("_")) <= max_mots


# --------------------------------------------------------------------------- #
# Bornage
# --------------------------------------------------------------------------- #
def test_le_bornage_inclut_les_deux_bornes() -> None:
    """Source (a) : de 1926-08-01 à 1926-11-30, il reste quatre mois.

    Les dates étant portées à la fin du mois, une borne gauche au 1er août garde
    le mois d'août, daté du 31. La borne droite tombe exactement sur le
    30 novembre, donc novembre est gardé lui aussi : quatre mois d'août à
    novembre.
    """
    mensuel = _parse_extrait()["monthly"]
    coupe = slice_period(mensuel, "1926-08-01", "1926-11-30")
    assert list(coupe.index) == [
        pd.Timestamp("1926-08-31"),
        pd.Timestamp("1926-09-30"),
        pd.Timestamp("1926-10-31"),
        pd.Timestamp("1926-11-30"),
    ]


def test_le_bornage_garde_la_ligne_posee_sur_la_borne_de_gauche() -> None:
    """Source (a) : la borne gauche est INCLUSE, donc sa propre ligne survit.

    Le test précédent ne le prouve pas : sa borne gauche, le 1er août, ne porte
    aucune observation, si bien qu'une borne rendue exclusive donnerait la même
    réponse. Ici la borne tombe sur le 30 septembre 1926, qui est une ligne du
    tableau. De septembre à décembre 1926 il reste donc quatre mois, et le
    premier est septembre.
    """
    mensuel = _parse_extrait()["monthly"]
    coupe = slice_period(mensuel, "1926-09-30", "1926-12-31")
    assert list(coupe.index) == [
        pd.Timestamp("1926-09-30"),
        pd.Timestamp("1926-10-31"),
        pd.Timestamp("1926-11-30"),
        pd.Timestamp("1926-12-31"),
    ]
    # Une seule borne, posée sur une ligne, garde cette ligne aux deux bouts.
    assert list(slice_period(mensuel, "1936-09-30").index) == [pd.Timestamp("1936-09-30")]
    assert slice_period(mensuel, None, "1926-07-31").index[-1] == pd.Timestamp("1926-07-31")


def test_le_bornage_sans_borne_ne_coupe_rien() -> None:
    """Source (b) : sans borne, le tableau est rendu entier."""
    mensuel = _parse_extrait()["monthly"]
    assert len(slice_period(mensuel)) == len(mensuel)


# --------------------------------------------------------------------------- #
# Facteurs de référence
# --------------------------------------------------------------------------- #
def _cinq_facteurs() -> pd.DataFrame:
    """Deux mois de cinq facteurs, fabriqués à la main."""
    index = pd.DatetimeIndex(["1963-07-31", "1963-08-31"], name="date")
    return pd.DataFrame(
        {
            "MKT-RF": [-0.0039, 0.0508],
            "SMB": [-0.0048, -0.0080],
            "HML": [-0.0081, 0.0170],
            "RMW": [0.0064, 0.0040],
            "CMA": [-0.0115, -0.0038],
            "RF": [0.0027, 0.0025],
        },
        index=index,
    )


def test_les_facteurs_de_reference_sont_dans_lordre_declare() -> None:
    """Source (b) : les sept colonnes sortent dans l'ordre de BENCHMARK_COLUMNS."""
    momentum = pd.DataFrame(
        {"MOM": [0.0101, 0.0100]},
        index=pd.DatetimeIndex(["1963-07-31", "1963-08-31"], name="date"),
    )
    combine = combine_benchmark_factors(_cinq_facteurs(), momentum)
    assert list(combine.columns) == list(BENCHMARK_COLUMNS)
    assert float(combine.loc["1963-07-31", "MOM"]) == pytest.approx(0.0101, rel=1e-12)
    assert float(combine.loc["1963-08-31", "MKT-RF"]) == pytest.approx(0.0508, rel=1e-12)


def test_un_momentum_plus_court_laisse_un_nan_visible() -> None:
    """Source (a) : deux mois de facteurs et un seul de momentum font un NaN."""
    momentum = pd.DataFrame({"MOM": [0.0101]}, index=pd.DatetimeIndex(["1963-07-31"], name="date"))
    combine = combine_benchmark_factors(_cinq_facteurs(), momentum)
    assert len(combine) == 2
    assert int(combine["MOM"].isna().sum()) == 1
    assert np.isnan(combine.loc["1963-08-31", "MOM"])


def test_une_colonne_absente_est_refusee() -> None:
    """Source (b) : sans RMW, ce ne sont pas les cinq facteurs."""
    tronque = _cinq_facteurs().drop(columns=["RMW"])
    momentum = pd.DataFrame({"MOM": [0.01]}, index=pd.DatetimeIndex(["1963-07-31"], name="date"))
    with pytest.raises(DataQualityError, match="RMW"):
        combine_benchmark_factors(tronque, momentum)
    with pytest.raises(DataQualityError, match="momentum"):
        combine_benchmark_factors(_cinq_facteurs(), pd.DataFrame({"AUTRE": [0.01]}))


def test_des_index_disjoints_sont_refuses() -> None:
    """Source (b) : deux séries sans date commune ne s'alignent pas."""
    momentum = pd.DataFrame({"MOM": [0.01]}, index=pd.DatetimeIndex(["2020-01-31"], name="date"))
    with pytest.raises(InsufficientDataError):
        combine_benchmark_factors(_cinq_facteurs(), momentum)


# --------------------------------------------------------------------------- #
# Le fournisseur, hors réseau
# --------------------------------------------------------------------------- #
def _archive(texte: str, nom: str = "F-F_Research_Data_Factors.CSV") -> bytes:
    """Fabrique une archive ZIP au format de la bibliothèque."""
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(nom, texte)
    return tampon.getvalue()


class _ClientFaux:
    """Client HTTP de test : il rend une réponse préparée, sans réseau.

    Le socle des fournisseurs ne connaît de son client qu'une méthode ``get``
    rendant une :class:`RawResponse`, si bien que ce double suffit et que rien
    ne sort de la machine.
    """

    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.calls: list[str] = []

    def get(self, url: str, *, params=None, headers=None) -> RawResponse:
        self.calls.append(url)
        return RawResponse(content=self.payload, url=url)


def _provider(tmp_path, client: _ClientFaux) -> FrenchProvider:
    """Un fournisseur branché sur un cache jetable et un client de test."""
    return FrenchProvider(client=client, raw_root=tmp_path / "french")


def test_ladresse_de_larchive_est_celle_de_la_bibliotheque() -> None:
    """Source (c) : adresse vérifiée le 2026-09-01, réponse 200."""
    provider = FrenchProvider()
    assert provider.archive_url("F-F_Research_Data_Factors_daily") == (
        "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_daily_CSV.zip"
    )
    with pytest.raises(ConfigError):
        provider.archive_url("  ")


def test_le_fournisseur_satisfait_le_protocole() -> None:
    """Source (b) : le protocole est structurel, l'instance doit le remplir."""
    assert isinstance(FrenchProvider(), DataProvider)
    assert FrenchProvider.name == "french"


def test_fetch_rend_le_tableau_principal(tmp_path) -> None:
    """Source (a) : le tableau principal est le mensuel, sept lignes ici."""
    provider = _provider(tmp_path, _ClientFaux(_archive(EXTRAIT_TROIS_FACTEURS)))
    frame = provider.fetch("F-F_Research_Data_Factors")
    assert frame.shape == (7, 4)
    assert float(frame.loc["1936-09-30", "MKT-RF"]) == pytest.approx(0.0097, rel=1e-12)


def test_fetch_sait_designer_le_second_tableau(tmp_path) -> None:
    """Source (a) : le tableau annuel de l'extrait porte quatre années."""
    provider = _provider(tmp_path, _ClientFaux(_archive(EXTRAIT_TROIS_FACTEURS)))
    frame = provider.fetch("F-F_Research_Data_Factors", table="annual_factors_january_december")
    assert len(frame) == 4
    with pytest.raises(KeyError):
        provider.fetch("F-F_Research_Data_Factors", table="inexistant")


def test_fetch_tables_rend_les_deux_tableaux_bornes(tmp_path) -> None:
    """Source (a) : bornée à 1926, la partie mensuelle garde six mois."""
    provider = _provider(tmp_path, _ClientFaux(_archive(EXTRAIT_TROIS_FACTEURS)))
    tables = provider.fetch_tables("F-F_Research_Data_Factors", "1926-01-01", "1926-12-31")
    assert set(tables) == {"monthly", "annual_factors_january_december"}
    assert len(tables["monthly"]) == 6
    assert len(tables["annual_factors_january_december"]) == 0


def test_larchive_est_mise_en_cache_et_relue_sans_reseau(tmp_path) -> None:
    """Source (b) : le second appel ne doit toucher aucun client."""
    client = _ClientFaux(_archive(EXTRAIT_TROIS_FACTEURS))
    provider = _provider(tmp_path, client)
    provider.fetch("F-F_Research_Data_Factors")
    assert len(client.calls) == 1
    provider.fetch("F-F_Research_Data_Factors")
    assert len(client.calls) == 1
    cle = cache_key(provider.archive_url("F-F_Research_Data_Factors"), None, "F-F_Research_Data_Factors")
    assert len(provider.cached_paths(cle)) == 1


def test_une_reponse_qui_nest_pas_une_archive_est_refusee(tmp_path) -> None:
    """Source (b) : une page HTML ne commence pas par la signature « PK »."""
    provider = _provider(tmp_path, _ClientFaux(b"<html>Not found</html>"))
    with pytest.raises(DataQualityError, match="archive ZIP"):
        provider.fetch("F-F_Research_Data_Factors")


def test_une_archive_sans_csv_est_refusee(tmp_path) -> None:
    """Source (b) : une archive sans fichier CSV ne porte pas de données."""
    provider = _provider(tmp_path, _ClientFaux(_archive("rien", nom="lisez-moi.txt")))
    with pytest.raises(DataQualityError, match="aucun fichier CSV"):
        provider.fetch("F-F_Research_Data_Factors")


def test_le_manifeste_declare_ce_qui_decide_dun_backtest(tmp_path) -> None:
    """Source (c) : les facteurs sont bâtis sur CRSP et révisés à chaque millésime."""
    provider = _provider(tmp_path, _ClientFaux(_archive(EXTRAIT_TROIS_FACTEURS)))
    frame = provider.fetch("F-F_Research_Data_Factors")
    manifeste = provider.manifest("F-F_Research_Data_Factors", frame=frame)
    assert manifeste.survivorship_free is True
    assert manifeste.point_in_time is False
    assert "citation" in manifeste.license
    assert manifeste.url.endswith("F-F_Research_Data_Factors_CSV.zip")
    assert manifeste.provider == "french"
    assert manifeste.n_rows == 7
    assert manifeste.columns == ("MKT-RF", "SMB", "HML", "RF")
    assert manifeste.n_columns == 4
    # Source (a) : la couverture est celle de l'extrait, de juillet 1926 à
    # septembre 1936, dates de fin de mois.
    assert manifeste.data_start == dt.date(1926, 7, 31)
    assert manifeste.data_end == dt.date(1936, 9, 30)
    # Source (d) : l'empreinte est celle que hashlib calcule sur les mêmes octets.
    attendu = hashlib.sha256(provider.download("F-F_Research_Data_Factors")).hexdigest()
    assert manifeste.checksum_sha256 == attendu
    assert isinstance(manifeste.download_timestamp, dt.datetime)


def test_le_manifeste_declare_la_frequence_du_tableau_decrit(tmp_path) -> None:
    """Source (a) : quatre dates séparées d'un an font un tableau annuel.

    Le fichier empile deux tableaux de fréquences différentes. Déclarer celle du
    FICHIER pour le tableau annuel serait une erreur qui ne se voit pas : la
    fréquence gouverne l'annualisation, et ``Frequency.MONTHLY.periods_per_year``
    vaut 12 contre 1 pour ``Frequency.ANNUAL``. Une moyenne serait annualisée
    douze fois trop haut, une volatilité d'un facteur racine de douze.
    """
    provider = _provider(tmp_path, _ClientFaux(_archive(EXTRAIT_TROIS_FACTEURS)))
    annuel = provider.manifest("F-F_Research_Data_Factors", table="annual_factors_january_december")
    assert annuel.frequency is Frequency.ANNUAL
    assert annuel.n_rows == 4
    assert annuel.data_start == dt.date(1927, 12, 31)
    assert annuel.data_end == dt.date(1930, 12, 31)
    # Source (b) : le tableau principal du même fichier reste mensuel.
    assert provider.manifest("F-F_Research_Data_Factors").frequency is Frequency.MONTHLY
    # Un tableau borné garde la fréquence de son tableau d'origine.
    borne = provider.fetch("F-F_Research_Data_Factors", table="annual_factors_january_december")
    assert (
        provider.manifest(
            "F-F_Research_Data_Factors",
            table="annual_factors_january_december",
            frame=borne,
        ).frequency
        is Frequency.ANNUAL
    )


def test_le_manifeste_refuse_de_nommer_un_tableau_absent(tmp_path) -> None:
    """Source (b) : un tableau qu'on ne trouve pas ne se décrit pas au jugé."""
    provider = _provider(tmp_path, _ClientFaux(_archive(EXTRAIT_TROIS_FACTEURS)))
    with pytest.raises(KeyError):
        provider.manifest("F-F_Research_Data_Factors", table="inexistant")


def test_le_manifeste_ne_manque_que_de_sa_lignee(tmp_path) -> None:
    """Source (b) : le contrôle du manifeste dit ce qui manque pour le gold.

    Un jeu téléchargé n'a pas de parent, donc « parent_datasets » est le seul
    champ que ce fournisseur ne peut pas remplir. Tout autre manque signalerait
    une provenance incomplète.
    """
    provider = _provider(tmp_path, _ClientFaux(_archive(EXTRAIT_TROIS_FACTEURS)))
    manifeste = provider.manifest("F-F_Research_Data_Factors")
    assert manifeste.missing_for_gold() == ("parent_datasets",)


def test_un_tableau_vide_na_pas_de_couverture(tmp_path) -> None:
    """Source (b) : sans ligne, la période couverte est indéterminée."""
    provider = _provider(tmp_path, _ClientFaux(_archive(EXTRAIT_TROIS_FACTEURS)))
    vide = provider.fetch("F-F_Research_Data_Factors", "2100-01-01", "2100-12-31")
    with pytest.raises(InsufficientDataError):
        provider.manifest("F-F_Research_Data_Factors", frame=vide)


def test_les_jeux_connus_couvrent_les_quatre_familles_demandees() -> None:
    """Source (c) : onze noms vérifiés le 2026-09-01, tous en réponse 200."""
    jeux = available_datasets()
    attendus = {
        "F-F_Research_Data_Factors",
        "F-F_Research_Data_Factors_daily",
        "F-F_Research_Data_5_Factors_2x3",
        "F-F_Research_Data_5_Factors_2x3_daily",
        "F-F_Momentum_Factor",
        "F-F_Momentum_Factor_daily",
        "25_Portfolios_5x5",
        "25_Portfolios_5x5_Daily",
        "6_Portfolios_2x3",
        "6_Portfolios_2x3_daily",
    }
    assert attendus <= set(jeux)
    assert jeux["F-F_Research_Data_Factors"].frequency is Frequency.MONTHLY
    assert jeux["F-F_Research_Data_Factors_daily"].frequency is Frequency.DAILY
    # Source (c) : taille mesurée le 2026-09-01, 177 852 octets.
    assert jeux["F-F_Research_Data_Factors_daily"].archive_bytes == 177_852
    assert FrenchProvider.available_datasets() is jeux


def test_une_frequence_sans_fichier_de_reference_est_refusee(tmp_path) -> None:
    """Source (b) : la bibliothèque ne publie pas de cinq facteurs trimestriels."""
    provider = _provider(tmp_path, _ClientFaux(b""))
    with pytest.raises(ConfigError, match="non publiée"):
        provider.benchmark_factors(Frequency.QUARTERLY)


# --------------------------------------------------------------------------- #
# Le réseau, facultatif
# --------------------------------------------------------------------------- #
def _client_reseau() -> HttpClient:
    """Un client identifié par un courriel, comme le socle l'exige."""
    # Settings lit QUANTLAB_USER_AGENT ; sans elle, le socle refuse la requête
    # avant de la faire, ce qui est exactement ce que le test doit vérifier.
    return HttpClient(settings=Settings())


@pytest.mark.network
def test_reseau_le_premier_jour_des_trois_facteurs_quotidiens(tmp_path) -> None:
    """Source (c) : la série quotidienne commence le 1er juillet 1926.

    C'est la date de début publiée par la bibliothèque pour les trois facteurs
    quotidiens, inchangée d'un millésime à l'autre puisqu'elle est celle du
    premier jour de cotation couvert par CRSP dans cette série.
    """
    provider = FrenchProvider(client=_client_reseau(), raw_root=tmp_path / "french")
    frame = provider.fetch("F-F_Research_Data_Factors_daily")
    assert frame.index[0] == pd.Timestamp("1926-07-01")
    assert list(frame.columns) == ["MKT-RF", "SMB", "HML", "RF"]
    # Les valeurs sont en décimales : un rendement quotidien de facteur ne
    # dépasse pas 100 % en valeur absolue sur cette série.
    assert float(np.nanmax(np.abs(frame.to_numpy()))) < 1.0


@pytest.mark.network
def test_reseau_le_taux_annuel_est_le_compose_des_taux_mensuels(tmp_path) -> None:
    """Source (c) : l'en-tête du fichier énonce l'identité, et (a) sa tolérance.

    Le fichier écrit « The annual TBill return is compounded from the monthly
    T-bill rates from January to December ». Le taux annuel publié doit donc
    valoir le produit des douze taux mensuels, moins un. L'identité met à
    l'épreuve d'un seul coup la division par cent, la datation de fin de période
    et le découpage en deux tableaux : un diviseur faux, un décalage d'un mois
    ou un mélange des deux tableaux la casseraient.

    La tolérance vient d'un calcul, non d'une observation. Les taux mensuels
    sont publiés arrondis au centième de point, soit 5e-5 en décimales, et douze
    arrondis de même signe donnent au pire 6e-4. Mesuré le 2026-09-01 sur les
    99 années complètes du millésime 202606, l'écart maximal vaut 3,0e-4.

    Contrôle en creux : MKT-RF est une DIFFÉRENCE de rendements, qui ne se
    compose pas. Son écart annuel atteint 2,4e-2, mesuré le même jour, donc le
    test verrait une colonne prise pour une autre.
    """
    provider = FrenchProvider(client=_client_reseau(), raw_root=tmp_path / "french")
    tables = provider.fetch_tables("F-F_Research_Data_Factors")
    mensuel = tables["monthly"]
    annuel = tables["annual_factors_january_december"]
    ecarts = []
    for horodate in annuel.index:
        mois = mensuel.loc[str(horodate.year), "RF"]
        if len(mois) != 12:
            continue
        ecarts.append(float(np.prod(1.0 + mois.to_numpy()) - 1.0 - annuel.loc[horodate, "RF"]))
    assert len(ecarts) >= 90
    assert max(abs(ecart) for ecart in ecarts) < 6e-4


@pytest.mark.network
def test_reseau_les_sept_facteurs_de_reference_sont_alignes(tmp_path) -> None:
    """Source (c) : les cinq facteurs commencent en juillet 1963."""
    provider = FrenchProvider(client=_client_reseau(), raw_root=tmp_path / "french")
    frame = provider.benchmark_factors(Frequency.MONTHLY)
    assert list(frame.columns) == list(BENCHMARK_COLUMNS)
    assert frame.index[0] == pd.Timestamp("1963-07-31")
    assert int(frame["MOM"].isna().sum()) == 0


# --------------------------------------------------------------------------- #
# Les fichiers de portefeuilles triés, ajoutés le 2026-09-02
#
# Source (c) : lignes littérales de « 10_Portfolios_Prior_12_2.CSV », millésime
# CRSP 202606. Les lignes 1 à 15 sont les quinze premières du fichier. La ligne
# « 202606 » est sa ligne 1205, la dernière du premier tableau, recopiée juste
# après le saut : le fichier porte 1 194 mois entre les deux, retirés ici. Les
# six autres tableaux suivent à partir de leur ligne de titre, tronqués à deux
# ou trois lignes de données chacun. Aucune valeur n'est retouchée.
# --------------------------------------------------------------------------- #
EXTRAIT_DECILES = """This file was created using the 202606 CRSP database.
It contains value- and equal-weighted returns for  10 prior-return portfolios.
The portfolios are constructed monthly. PRIOR_RET is from -12 to - 2.

Annual returns are from January to December.

Missing data are indicated by -99.99 or -999.


  Value Weight Returns -- Monthly
,Lo PRIOR,PRIOR 2,PRIOR 3,PRIOR 4,PRIOR 5,PRIOR 6,PRIOR 7,PRIOR 8,PRIOR 9,Hi PRIOR
192701,  -3.32,  -4.54,   2.67,  -0.29,  -0.41,   0.97,   0.29,   0.71,  -0.14,  -0.24
192702,   7.39,   6.01,   7.03,   7.46,   4.69,   3.72,   2.99,   3.20,   4.14,   7.04
192703,  -3.23,  -3.05,  -3.84,  -4.80,  -0.46,  -2.48,   1.94,   0.49,   0.86,   5.50
192704,   1.28,  -3.01,  -2.44,   1.02,   0.94,  -0.16,   2.03,  -0.51,   1.59,   5.49
202606,  -6.93,  -1.13,  -4.29,  -7.52,   1.06,   5.06,  -3.86,  -1.69,  -4.72,   8.35


  Average Equal Weighted Returns -- Monthly
,Lo PRIOR,PRIOR 2,PRIOR 3,PRIOR 4,PRIOR 5,PRIOR 6,PRIOR 7,PRIOR 8,PRIOR 9,Hi PRIOR
192701,  -0.47,   0.88,   4.10,   2.51,  -0.29,   3.08,   0.98,   0.98,  -0.39,   1.30
192702,   3.97,   4.06,   6.87,   7.53,   6.39,   4.85,   5.34,   4.09,   5.46,   5.63
192703,  -6.06,  -5.18,  -2.06,  -1.73,  -1.98,  -1.39,   0.37,  -1.34,   0.38,  -0.76
192704,   1.95,  -0.32,   0.11,  -0.75,  -0.27,   0.30,   1.20,  -0.44,   2.21,   4.42


  Average Value Weighted Returns -- Annual
,Lo PRIOR,PRIOR 2,PRIOR 3,PRIOR 4,PRIOR 5,PRIOR 6,PRIOR 7,PRIOR 8,PRIOR 9,Hi PRIOR
  1927,  13.05,   8.26,  18.79,  23.59,  33.27,  23.26,  36.19,  28.44,  39.55,  66.00
  1928,  16.96,  22.58,  26.85,  20.69,  28.03,  30.34,  40.98,  42.29,  49.90,  88.22
  1929, -59.11, -48.08, -36.05, -22.17,   0.44, -13.51,   5.51,   0.22,   0.08, -29.80


  Average Equal Weighted Returns -- Annual
,Lo PRIOR,PRIOR 2,PRIOR 3,PRIOR 4,PRIOR 5,PRIOR 6,PRIOR 7,PRIOR 8,PRIOR 9,Hi PRIOR
  1927,  16.89,  18.98,  24.31,  32.23,  29.95,  41.73,  36.77,  28.69,  39.26,  40.63
  1928,  34.88,  35.85,  38.90,  34.72,  31.32,  59.08,  43.51,  30.94,  44.23,  84.97
  1929, -56.59, -48.05, -36.69, -35.16, -24.80, -19.65, -19.73, -15.64, -18.10, -25.22


  Number of Firms in Portfolios
,Lo PRIOR,PRIOR 2,PRIOR 3,PRIOR 4,PRIOR 5,PRIOR 6,PRIOR 7,PRIOR 8,PRIOR 9,Hi PRIOR
192701,     47,     47,     48,     47,     47,     47,     47,     48,     47,     47
192702,     48,     47,     48,     47,     48,     48,     47,     48,     47,     48


  Average Firm Size
,Lo PRIOR,PRIOR 2,PRIOR 3,PRIOR 4,PRIOR 5,PRIOR 6,PRIOR 7,PRIOR 8,PRIOR 9,Hi PRIOR
192701,      7.27,     11.52,     23.23,     42.40,     45.90,     61.52,    109.02,    137.04,     67.57,     83.96
192702,      3.53,     16.45,     16.07,     23.25,     57.36,     70.55,     73.65,    149.21,     92.02,     86.43


  Value-Weighted Average of Prior Returns
,Lo PRIOR,PRIOR 2,PRIOR 3,PRIOR 4,PRIOR 5,PRIOR 6,PRIOR 7,PRIOR 8,PRIOR 9,Hi PRIOR
1927, -39.55, -19.07,  -7.79,   1.90,  12.68,  20.02,  26.24,  36.31,  52.31, 115.07
1928, -17.25,  -2.07,   5.87,  14.57,  23.98,  33.06,  48.26,  62.32,  82.31, 135.06

Copyright 2026 Eugene F. Fama and Kenneth R. French
"""

# Source (c) : lignes 10 à 13 de « 10_Portfolios_Prior_1_0.CSV ». Le titre porte
# « Aerage » au lieu de « Average », faute de frappe de la bibliothèque relevée
# le 2026-09-02 et recopiée telle quelle.
EXTRAIT_TITRE_FAUTIF = """This file was created using the 202606 CRSP database.

  Aerage Value Weighted Returns -- Monthly
,Lo PRIOR,PRIOR 2,PRIOR 3,PRIOR 4,PRIOR 5,PRIOR 6,PRIOR 7,PRIOR 8,PRIOR 9,Hi PRIOR
192602,  -7.81,  -5.01,  -3.97,  -3.74,  -4.75,  -1.32,  -1.86,  -1.40,  -2.70,  -5.38
192603, -17.26,  -9.53, -14.03,  -5.27,  -8.54,  -4.23,  -5.05,  -4.93,  -3.37,  -9.65
"""

# Source (c) : lignes 24 à 27 puis 1544 à 1547 de « Portfolios_Formed_on_OP.CSV ».
# Ce fichier écrit « Average Value Weight Returns », sans le « ed » de
# « Weighted », et son titre annuel nomme la période en entier. Ses colonnes de
# déciles s'appellent « 2-Dec » à « 9-Dec », le tableur ayant lu « Dec 2 » comme
# une date, ce que le fichier trié par bêta n'a pas subi.
EXTRAIT_TITRES_VARIANTS = """This file was created using the 202606 CRSP database.

  Average Value Weight Returns -- Monthly
,Lo 30,Med 40,Hi 30,Lo 20,Qnt 2,Qnt 3,Qnt 4,Hi 20,Lo 10,2-Dec,3-Dec,4-Dec,5-Dec,6-Dec,7-Dec,8-Dec,9-Dec,Hi 10
196307,   -0.87,    0.38,    0.03,   -0.40,    1.08,   -0.12,   -1.05,    0.52,   -1.37,    0.05,   -1.47,    2.17,   -0.87,    1.00,   -1.06,   -1.04,   -0.26,    0.94
196308,    5.47,    4.91,    5.83,    5.16,    4.37,    5.33,    5.46,    6.04,    5.57,    4.98,    5.87,    3.75,    5.44,    5.17,    5.58,    5.38,    6.00,    6.06


  Value Weight Returns -- Annual from January to December
,Lo 30,Med 40,Hi 30,Lo 20,Qnt 2,Qnt 3,Qnt 4,Hi 20,Lo 10,2-Dec,3-Dec,4-Dec,5-Dec,6-Dec,7-Dec,8-Dec,9-Dec,Hi 10
  1964,   21.86,   15.77,   15.95,   22.20,   21.50,   12.06,   14.58,   17.89,   13.55,   26.17,   21.42,   21.54,   11.68,   13.85,   17.78,   12.53,   18.85,   16.56
  1965,   19.47,    6.84,   20.54,   23.56,    1.22,   14.31,   14.70,   22.34,   28.85,   20.78,   16.48,   -4.82,   15.79,   13.43,   15.26,   14.33,   27.76,   20.12
"""

# Source (c) : lignes 11, 12 et 16 de « 25_Portfolios_ME_Prior_12_2.CSV ». La
# ligne d'avril 1927 porte un -99.99 dans la colonne « BIG LoPRIOR » : aucune
# grande société n'était alors dans le quintile de plus faible rendement passé.
EXTRAIT_CROISE_MANQUANT = """This file was created using the 202606 CRSP database.

  Average Value Weighted Returns -- Monthly
,SMALL LoPRIOR,ME1 PRIOR2,ME1 PRIOR3,ME1 PRIOR4,SMALL HiPRIOR,ME2 PRIOR1,ME2 PRIOR2,ME2 PRIOR3,ME2 PRIOR4,ME2 PRIOR5,ME3 PRIOR1,ME3 PRIOR2,ME3 PRIOR3,ME3 PRIOR4,ME3 PRIOR5,ME4 PRIOR1,ME4 PRIOR2,ME4 PRIOR3,ME4 PRIOR4,ME4 PRIOR5,BIG LoPRIOR,ME5 PRIOR2,ME5 PRIOR3,ME5 PRIOR4,BIG HiPRIOR
192704,   0.91,  -0.90,   0.39,   7.44,  -7.30,  -1.12,   1.04,  -1.82,   3.67,   7.35,  -7.68,  -0.28,   1.16,  -0.56,   3.42,  -1.61,  -2.44,   0.85,   0.15,   0.98, -99.99,  -0.68,   0.22,   0.58,   4.11
"""

#: Les noms de colonnes lus à la ligne 11 du fichier réel, avant la mise en
#: majuscules. Ils servent de valeur attendue indépendante de la constante du
#: module, qu'un copier-coller depuis le code aurait rendue circulaire.
COLONNES_DU_FICHIER = (
    "Lo PRIOR",
    "PRIOR 2",
    "PRIOR 3",
    "PRIOR 4",
    "PRIOR 5",
    "PRIOR 6",
    "PRIOR 7",
    "PRIOR 8",
    "PRIOR 9",
    "Hi PRIOR",
)


# --------------------------------------------------------------------------- #
# Le découpage des sept tableaux
# --------------------------------------------------------------------------- #
def test_le_fichier_des_deciles_porte_sept_tableaux() -> None:
    """Source (c) : sept titres lus dans le fichier réel le 2026-09-02.

    Le fichier empile quatre tableaux de rendements, deux tableaux de
    caractéristiques et un tableau de rendements passés moyens. Un lecteur qui
    s'arrêterait au premier saut de ligne en perdrait six.
    """
    parsed = parse_french_csv(EXTRAIT_DECILES)
    assert len(parsed) == 7
    assert parsed.names == (
        "value_weight_returns_monthly",
        "average_equal_weighted_returns_monthly",
        "average_value_weighted_returns_annual",
        "average_equal_weighted_returns_annual",
        "number_of_firms_in_portfolios",
        "average_firm_size",
        "value_weighted_average_of_prior_returns",
    )
    assert parsed.block("value_weight_returns_monthly").frequency is Frequency.MONTHLY
    assert parsed.block("average_value_weighted_returns_annual").frequency is Frequency.ANNUAL
    assert parsed.trailer.strip() == "Copyright 2026 Eugene F. Fama and Kenneth R. French"


def test_les_colonnes_sont_celles_du_fichier_en_majuscules() -> None:
    """Source (c) : l'en-tête écrit « Lo PRIOR » et « Hi PRIOR ».

    La constante du module doit être la mise en majuscules de cet en-tête, et
    rien d'autre. Le test compare donc la constante au texte du fichier, jamais
    à elle-même.
    """
    parsed = parse_french_csv(EXTRAIT_DECILES)
    attendues = [nom.upper() for nom in COLONNES_DU_FICHIER]
    for nom_du_tableau in parsed.names:
        assert list(parsed[nom_du_tableau].columns) == attendues
    assert list(MOMENTUM_DECILE_COLUMNS) == attendues
    assert LOSER_DECILE == "LO PRIOR"
    assert WINNER_DECILE == "HI PRIOR"


def test_conversion_du_pourcentage_sur_les_deciles() -> None:
    """Source (a) : -3,32 % s'écrit -0,0332 en décimales, soit -3,32 / 100."""
    frame = parse_french_csv(EXTRAIT_DECILES)["value_weight_returns_monthly"]
    assert float(frame.loc["1927-01-31", "LO PRIOR"]) == pytest.approx(-0.0332, rel=1e-12)
    assert float(frame.loc["1927-01-31", "HI PRIOR"]) == pytest.approx(-0.0024, rel=1e-12)
    # Le dernier mois du fichier, recopié après le saut : 8,35 / 100 = 0,0835.
    assert float(frame.loc["2026-06-30", "HI PRIOR"]) == pytest.approx(0.0835, rel=1e-12)


def test_les_deux_tableaux_de_caracteristiques_ne_sont_pas_divises() -> None:
    """Source (a) : 47 sociétés restent 47, et 7,27 M$ restent 7,27.

    Diviser par cent rendrait 0,47 société et une capitalisation moyenne de
    0,0727 million de dollars. Les deux titres ne portent ni « return » ni
    « factor », ce qui est la règle de :func:`_is_percent_block`.
    """
    parsed = parse_french_csv(EXTRAIT_DECILES)
    societes = parsed.block("number_of_firms_in_portfolios")
    taille = parsed.block("average_firm_size")
    assert societes.in_percent is False
    assert taille.in_percent is False
    assert float(societes.frame.loc["1927-01-31", "LO PRIOR"]) == 47.0
    assert float(taille.frame.loc["1927-01-31", "LO PRIOR"]) == pytest.approx(7.27, rel=1e-12)


def test_la_moyenne_des_rendements_passes_reste_un_pourcentage() -> None:
    """Source (a) : -39,55 devient -0,3955, car le titre porte « Returns ».

    Ce tableau donne le rendement passé moyen des sociétés de chaque décile à
    leur formation. C'est bien un pourcentage, et il est daté à l'année.
    """
    bloc = parse_french_csv(EXTRAIT_DECILES).block("value_weighted_average_of_prior_returns")
    assert bloc.in_percent is True
    assert bloc.frequency is Frequency.ANNUAL
    assert float(bloc.frame.loc["1927-12-31", "LO PRIOR"]) == pytest.approx(-0.3955, rel=1e-12)


# --------------------------------------------------------------------------- #
# Le choix du tableau de rendements
# --------------------------------------------------------------------------- #
def test_le_choix_ecarte_le_tableau_de_rendements_passes() -> None:
    """Source (b) : deux titres portent « value » et « returns », un seul compte.

    Le piège est nommé : « Value-Weighted Average of Prior Returns » contient
    les deux mots que cherche une recherche naïve. Il ne porte pas le marqueur
    de période, et c'est ce qui le distingue.
    """
    parsed = parse_french_csv(EXTRAIT_DECILES)
    bloc = select_return_block(parsed, weighting="value", frequency=Frequency.MONTHLY)
    assert bloc.title == "Value Weight Returns -- Monthly"
    assert bloc.name == "value_weight_returns_monthly"


def test_seuls_les_tableaux_de_rendements_portent_le_marqueur_de_periode() -> None:
    """Source (c) : quatre titres marqués sur sept, relevés le 2026-09-02.

    C'est la propriété sur laquelle repose :func:`select_return_block`, et ce
    test la vérifie seule, sans passer par la sélection. Les trois titres non
    marqués sont ceux des caractéristiques, dont le piège nommé
    « Value-Weighted Average of Prior Returns ».
    """
    parsed = parse_french_csv(EXTRAIT_DECILES)
    marques = [bloc for bloc in parsed.blocks if PERIOD_MARKER in bloc.title]
    non_marques = [bloc.title for bloc in parsed.blocks if PERIOD_MARKER not in bloc.title]
    assert len(marques) == 4
    assert all(bloc.in_percent for bloc in marques)
    assert non_marques == [
        "Number of Firms in Portfolios",
        "Average Firm Size",
        "Value-Weighted Average of Prior Returns",
    ]


def test_le_choix_distingue_les_deux_ponderations_et_les_deux_frequences() -> None:
    """Source (c) : les quatre titres marqués du fichier réel, un par couple."""
    parsed = parse_french_csv(EXTRAIT_DECILES)
    couples = {
        ("value", Frequency.MONTHLY): "Value Weight Returns -- Monthly",
        ("equal", Frequency.MONTHLY): "Average Equal Weighted Returns -- Monthly",
        ("value", Frequency.ANNUAL): "Average Value Weighted Returns -- Annual",
        ("equal", Frequency.ANNUAL): "Average Equal Weighted Returns -- Annual",
    }
    for (ponderation, frequence), titre in couples.items():
        bloc = select_return_block(parsed, weighting=ponderation, frequency=frequence)
        assert bloc.title == titre


def test_le_choix_survit_a_la_faute_de_frappe_de_la_source() -> None:
    """Source (c) : le fichier de renversement écrit « Aerage ».

    Un choix qui chercherait « Average Value Weighted Returns » ne trouverait
    rien ici. La règle ne regarde que le mot de pondération et le marqueur.
    """
    parsed = parse_french_csv(EXTRAIT_TITRE_FAUTIF)
    bloc = select_return_block(parsed, weighting="value", frequency=Frequency.MONTHLY)
    assert bloc.title == "Aerage Value Weighted Returns -- Monthly"
    assert float(bloc.frame.loc["1926-02-28", "LO PRIOR"]) == pytest.approx(-0.0781, rel=1e-12)


def test_le_choix_survit_aux_deux_autres_orthographes() -> None:
    """Source (c) : « Value Weight » sans « ed », et la période écrite en toutes lettres."""
    parsed = parse_french_csv(EXTRAIT_TITRES_VARIANTS)
    mensuel = select_return_block(parsed, weighting="value", frequency=Frequency.MONTHLY)
    annuel = select_return_block(parsed, weighting="value", frequency=Frequency.ANNUAL)
    assert mensuel.title == "Average Value Weight Returns -- Monthly"
    assert annuel.title == "Value Weight Returns -- Annual from January to December"
    # Source (c) : le tableur a lu « Dec 2 » comme une date et écrit « 2-Dec ».
    assert list(mensuel.frame.columns)[9] == "2-DEC"
    # Source (a) : 21,86 % pour le tiers le moins rentable en 1964, soit 0,2186.
    assert float(annuel.frame.loc["1964-12-31", "LO 30"]) == pytest.approx(0.2186, rel=1e-12)


def test_une_ponderation_inconnue_est_refusee() -> None:
    """Source (b) : la bibliothèque n'en publie que deux, la faute doit être dite."""
    parsed = parse_french_csv(EXTRAIT_DECILES)
    with pytest.raises(ConfigError, match="pondération"):
        select_return_block(parsed, weighting="capitalisation")


def test_une_frequence_absente_du_fichier_est_refusee() -> None:
    """Source (b) : le fichier mensuel ne porte aucun tableau quotidien."""
    parsed = parse_french_csv(EXTRAIT_DECILES)
    with pytest.raises(DataQualityError, match="aucun tableau de rendements"):
        select_return_block(parsed, weighting="value", frequency=Frequency.DAILY)


# --------------------------------------------------------------------------- #
# L'écart entre déciles extrêmes
# --------------------------------------------------------------------------- #
def test_lecart_est_le_gagnant_moins_le_perdant() -> None:
    """Source (a) : en janvier 1927, -0,24 moins -3,32 fait 3,08 points.

    En décimales, 3,08 / 100 vaut 0,0308. En 1927, l'année entière donne
    66,00 moins 13,05, soit 52,95 points, donc 0,5295.
    """
    parsed = parse_french_csv(EXTRAIT_DECILES)
    mensuel = decile_spread(parsed["value_weight_returns_monthly"])
    annuel = decile_spread(parsed["average_value_weighted_returns_annual"])
    assert mensuel.name == SPREAD_NAME
    assert float(mensuel.loc["1927-01-31"]) == pytest.approx(0.0308, rel=1e-9)
    assert float(annuel.loc["1927-12-31"]) == pytest.approx(0.5295, rel=1e-9)


def test_lecart_refuse_une_colonne_absente() -> None:
    """Source (b) : le fichier croisé n'a pas de colonne « HI PRIOR »."""
    parsed = parse_french_csv(EXTRAIT_CROISE_MANQUANT)
    with pytest.raises(DataQualityError, match="colonnes de déciles absentes"):
        decile_spread(parsed["average_value_weighted_returns_monthly"])


def test_un_manquant_du_fichier_se_propage_dans_lecart() -> None:
    """Source (c) : avril 1927 porte -99.99 dans « BIG LoPRIOR ».

    L'écart doit valoir ``NaN``, et non 4,11 moins -0,9999. Un code de manquant
    divisé par cent passerait pour une perte de 99,99 %, et l'écart calculé
    contre lui vaudrait plus de cent points de pourcentage.
    """
    frame = parse_french_csv(EXTRAIT_CROISE_MANQUANT)["average_value_weighted_returns_monthly"]
    assert bool(np.isnan(float(frame.loc["1927-04-30", "BIG LOPRIOR"])))
    ecart = decile_spread(frame, winner="BIG HIPRIOR", loser="BIG LOPRIOR")
    assert bool(np.isnan(float(ecart.loc["1927-04-30"])))
    # Source (c) : la colonne voisine est intacte, 4,11 / 100 = 0,0411.
    assert float(frame.loc["1927-04-30", "BIG HIPRIOR"]) == pytest.approx(0.0411, rel=1e-12)


@given(
    valeurs=st.lists(
        st.tuples(
            st.floats(min_value=-1.0, max_value=10.0, allow_nan=False),
            st.floats(min_value=-1.0, max_value=10.0, allow_nan=False),
        ),
        min_size=1,
        max_size=40,
    )
)
@hyp_settings(max_examples=60, suppress_health_check=[HealthCheck.too_slow])
def test_propriete_lecart_est_exactement_une_soustraction(valeurs: list[tuple[float, float]]) -> None:
    """Source (b) : identité, l'écart vaut colonne du gagnant moins celle du perdant."""
    index = pd.date_range("1990-01-31", periods=len(valeurs), freq="ME", name="date")
    frame = pd.DataFrame(
        {
            LOSER_DECILE: [bas for bas, _ in valeurs],
            WINNER_DECILE: [haut for _, haut in valeurs],
        },
        index=index,
    )
    ecart = decile_spread(frame)
    attendu = frame[WINNER_DECILE].to_numpy() - frame[LOSER_DECILE].to_numpy()
    assert np.allclose(ecart.to_numpy(), attendu, rtol=0.0, atol=0.0, equal_nan=True)
    assert list(ecart.index) == list(frame.index)


# --------------------------------------------------------------------------- #
# Le fournisseur, hors réseau
# --------------------------------------------------------------------------- #
def test_les_dix_fichiers_de_portefeuilles_tries_sont_declares() -> None:
    """Source (c) : dix noms et dix tailles mesurés le 2026-09-02, réponse 200."""
    jeux = available_datasets()
    tailles = {
        "10_Portfolios_Prior_12_2": 118_942,
        "10_Portfolios_Prior_12_2_Daily": 898_974,
        "25_Portfolios_ME_Prior_12_2": 426_118,
        "6_Portfolios_ME_Prior_12_2": 121_761,
        "10_Portfolios_Prior_1_0": 120_670,
        "10_Portfolios_Prior_60_13": 113_246,
        "Portfolios_Formed_on_BETA": 114_846,
        "Portfolios_Formed_on_OP": 134_980,
        "Portfolios_Formed_on_INV": 135_278,
        "49_Industry_Portfolios": 488_664,
    }
    for nom, octets in tailles.items():
        assert jeux[nom].archive_bytes == octets
    assert jeux["10_Portfolios_Prior_12_2"].frequency is Frequency.MONTHLY
    assert jeux["10_Portfolios_Prior_12_2_Daily"].frequency is Frequency.DAILY
    assert len(jeux) == 21


def test_momentum_deciles_rend_les_dix_colonnes_dans_lordre(tmp_path) -> None:
    """Source (c) : dix colonnes, de « LO PRIOR » à « HI PRIOR », ordre du fichier."""
    archive = _archive(EXTRAIT_DECILES, "10_Portfolios_Prior_12_2.CSV")
    provider = _provider(tmp_path, _ClientFaux(archive))
    frame = provider.momentum_deciles()
    assert list(frame.columns) == [nom.upper() for nom in COLONNES_DU_FICHIER]
    assert frame.index[0] == pd.Timestamp("1927-01-31")
    assert float(frame.loc["1927-01-31", "LO PRIOR"]) == pytest.approx(-0.0332, rel=1e-12)


def test_momentum_deciles_sait_prendre_lequiponderation(tmp_path) -> None:
    """Source (a) : le tableau équipondéré donne -0,47 % en janvier 1927."""
    archive = _archive(EXTRAIT_DECILES, "10_Portfolios_Prior_12_2.CSV")
    provider = _provider(tmp_path, _ClientFaux(archive))
    frame = provider.momentum_deciles(weighting="equal")
    assert float(frame.loc["1927-01-31", "LO PRIOR"]) == pytest.approx(-0.0047, rel=1e-12)


def test_momentum_deciles_borne_la_periode(tmp_path) -> None:
    """Source (a) : deux mois demandés sur les cinq de l'extrait, bornes incluses."""
    archive = _archive(EXTRAIT_DECILES, "10_Portfolios_Prior_12_2.CSV")
    provider = _provider(tmp_path, _ClientFaux(archive))
    frame = provider.momentum_deciles(Frequency.MONTHLY, "value", "1927-02-01", "1927-03-31")
    assert list(frame.index) == [pd.Timestamp("1927-02-28"), pd.Timestamp("1927-03-31")]


def test_momentum_spread_est_la_derniere_colonne_moins_la_premiere(tmp_path) -> None:
    """Source (b) : identité entre les deux méthodes, sur toutes les dates."""
    archive = _archive(EXTRAIT_DECILES, "10_Portfolios_Prior_12_2.CSV")
    provider = _provider(tmp_path, _ClientFaux(archive))
    deciles = provider.momentum_deciles()
    ecart = provider.momentum_spread()
    attendu = deciles.iloc[:, -1].to_numpy() - deciles.iloc[:, 0].to_numpy()
    assert np.allclose(ecart.to_numpy(), attendu, rtol=0.0, atol=0.0)
    assert ecart.name == SPREAD_NAME


def test_une_frequence_sans_fichier_de_deciles_est_refusee(tmp_path) -> None:
    """Source (b) : la bibliothèque ne publie pas de déciles hebdomadaires."""
    provider = _provider(tmp_path, _ClientFaux(b""))
    with pytest.raises(ConfigError, match="non publiée"):
        provider.momentum_deciles(Frequency.WEEKLY)


def test_un_fichier_aux_colonnes_changees_est_refuse(tmp_path) -> None:
    """Source (b) : un changement de format de la source doit lever, pas passer.

    L'extrait servi ici est celui du tri par rentabilité, dont les colonnes
    s'appellent « Lo 30 » et « Hi 10 ». Aucune des dix colonnes de déciles de
    momentum n'y figure.
    """
    archive = _archive(EXTRAIT_TITRES_VARIANTS, "10_Portfolios_Prior_12_2.CSV")
    provider = _provider(tmp_path, _ClientFaux(archive))
    with pytest.raises(DataQualityError, match="colonnes de déciles absentes"):
        provider.momentum_deciles()


def test_portfolio_returns_lit_un_fichier_de_tri_quelconque(tmp_path) -> None:
    """Source (a) : 5,47 % pour le tiers le moins rentable en août 1963."""
    archive = _archive(EXTRAIT_TITRES_VARIANTS, "Portfolios_Formed_on_OP.CSV")
    provider = _provider(tmp_path, _ClientFaux(archive))
    frame = provider.portfolio_returns("Portfolios_Formed_on_OP")
    assert float(frame.loc["1963-08-31", "LO 30"]) == pytest.approx(0.0547, rel=1e-12)
    assert len(frame.columns) == 18


def test_le_manifeste_des_deciles_declare_labsence_de_biais_du_survivant(tmp_path) -> None:
    """Source (b) : la construction sur CRSP est ce qui autorise la déclaration.

    L'univers de CRSP contient les sociétés radiées, si bien que le décile
    perdant garde celles qui ont disparu. Sans cette propriété, le tri de
    Jegadeesh et Titman serait irréplicable, puisque son décile perdant est
    justement celui qui perd des sociétés.
    """
    archive = _archive(EXTRAIT_DECILES, "10_Portfolios_Prior_12_2.CSV")
    provider = _provider(tmp_path, _ClientFaux(archive))
    manifeste = provider.manifest("10_Portfolios_Prior_12_2")
    assert manifeste.survivorship_free is True
    assert manifeste.point_in_time is False
    assert manifeste.frequency is Frequency.MONTHLY
    assert manifeste.data_start == dt.date(1927, 1, 31)
    assert manifeste.url.endswith("10_Portfolios_Prior_12_2_CSV.zip")
    assert "Jegadeesh" in (manifeste.notes or "")


# --------------------------------------------------------------------------- #
# Le réseau, facultatif
# --------------------------------------------------------------------------- #
# Source (c) : lignes 1 à 13 de « 10_Portfolios_Prior_12_2_Daily.CSV », millésime
# CRSP 202606, téléchargé le 2026-09-02. L'en-tête annonce « constructed daily »
# là où le fichier mensuel annonce « constructed monthly », et c'est ce que la
# docstring de :meth:`FrenchProvider.momentum_deciles` déclare.
EXTRAIT_DECILES_QUOTIDIENS = """This file was created using the 202606 CRSP database.
It contains value- and equally-weighted returns for  10 prior return portfolios.

The portfolios are constructed daily.  PRIOR_RET is from - 250 to - 21.

Missing data are indicated by -99.99 or -999.


  Average Value Weighted Returns -- Daily
,Lo PRIOR,PRIOR 2,PRIOR 3,PRIOR 4,PRIOR 5,PRIOR 6,PRIOR 7,PRIOR 8,PRIOR 9,Hi PRIOR
19261103,  -0.12,   0.61,  -0.07,   0.14,  -0.49,  -0.13,  -0.14,   0.46,   0.19,   1.26
19261104,   0.55,   1.47,   1.60,   0.61,   1.02,   0.59,   0.82,   0.45,   0.46,   0.40
19261105,  -0.92,  -0.72,  -0.27,  -0.36,   0.08,   0.20,  -0.15,   0.37,   0.25,   0.06
"""

# Source (c) : lignes 2612, 2613 et 3807 de « 10_Portfolios_Prior_12_2.CSV ». La
# dernière est la ligne de juin 2026 du tableau des effectifs, recopiée après un
# saut de 1 193 lignes.
EXTRAIT_EFFECTIFS = """This file was created using the 202606 CRSP database.

  Number of Firms in Portfolios
,Lo PRIOR,PRIOR 2,PRIOR 3,PRIOR 4,PRIOR 5,PRIOR 6,PRIOR 7,PRIOR 8,PRIOR 9,Hi PRIOR
202606,    614,    360,    243,    252,    239,    271,    253,    276,    273,    420
"""


def test_les_dix_deciles_nont_pas_le_meme_effectif() -> None:
    """Source (c) : la ligne de juin 2026 du tableau des effectifs du fichier.

    La docstring de :meth:`FrenchProvider.momentum_deciles` affirmait des groupes
    de même effectif. Le fichier dit le contraire, et c'est structurel : les
    bornes se calculent sur le seul NYSE puis s'appliquent au NYSE, à l'AMEX et
    au NASDAQ, si bien que les queues débordent.
    """
    effectifs = parse_french_csv(EXTRAIT_EFFECTIFS)["number_of_firms_in_portfolios"]
    juin = effectifs.loc["2026-06-30"]
    assert float(juin[LOSER_DECILE]) == 614.0
    assert float(juin[WINNER_DECILE]) == 420.0
    assert float(juin["PRIOR 5"]) == 239.0
    # Source (a) : 614 / 239 = 2,569..., donc les groupes ne sont pas égaux.
    assert float(juin.max() / juin.min()) == pytest.approx(614.0 / 239.0, rel=1e-12)
    assert float(juin.max() / juin.min()) > 2.0


def test_le_fichier_quotidien_annonce_une_construction_quotidienne() -> None:
    """Source (c) : « The portfolios are constructed daily », en-tête du fichier.

    C'est la phrase qui interdit d'écrire que les déciles quotidiens sont
    reformés chaque mois. Le préambule la conserve, et la sélection rend bien le
    tableau quotidien pondéré par la capitalisation.
    """
    parsed = parse_french_csv(EXTRAIT_DECILES_QUOTIDIENS)
    assert "The portfolios are constructed daily." in parsed.preamble
    assert "constructed monthly" not in parsed.preamble
    bloc = select_return_block(parsed, weighting="value", frequency=Frequency.DAILY)
    assert bloc.title == "Average Value Weighted Returns -- Daily"
    assert bloc.frequency is Frequency.DAILY
    # Source (a) : -0,12 / 100 = -0,0012, première séance du fichier.
    assert float(bloc.frame.loc["1926-11-03", "LO PRIOR"]) == pytest.approx(-0.0012, rel=1e-12)


def test_le_fichier_mensuel_annonce_une_construction_mensuelle() -> None:
    """Source (c) : « The portfolios are constructed monthly », en-tête du fichier.

    La contre-épreuve du test précédent. Les deux fichiers portent la même
    grammaire de titre et deux cadences de reformation différentes.
    """
    parsed = parse_french_csv(EXTRAIT_DECILES)
    assert "The portfolios are constructed monthly." in parsed.preamble


def test_le_choix_retient_le_premier_tableau_quand_deux_conviennent() -> None:
    """Source (b) : la docstring promet le premier dans l'ordre du fichier.

    Aucun millésime mesuré ne publie deux tableaux pour un même couple, mais la
    règle est écrite et doit tenir. Le fichier fabriqué ici en publie deux, et la
    fonction doit rendre celui qui vient en premier.
    """
    texte = (
        "En-tête fabriqué pour le test.\n"
        "\n"
        "  Value Weight Returns -- Monthly\n"
        ",Lo PRIOR,Hi PRIOR\n"
        "192701,  -3.32,  -0.24\n"
        "\n"
        "  Average Value Weighted Returns -- Monthly\n"
        ",Lo PRIOR,Hi PRIOR\n"
        "192701,  -1.00,   1.00\n"
    )
    parsed = parse_french_csv(texte)
    assert len(parsed) == 2
    bloc = select_return_block(parsed, weighting="value", frequency=Frequency.MONTHLY)
    assert bloc.title == "Value Weight Returns -- Monthly"
    assert bloc.first_line == parsed.blocks[0].first_line
    # Source (a) : -3,32 / 100, la valeur du PREMIER tableau et non du second.
    assert float(bloc.frame.loc["1927-01-31", "LO PRIOR"]) == pytest.approx(-0.0332, rel=1e-12)


@pytest.mark.network
def test_reseau_le_premier_mois_des_deciles_est_celui_du_fichier(tmp_path) -> None:
    """Source (c) : la première ligne de données du fichier porte « 192701 ».

    Le test lit la date DANS le texte téléchargé, puis la compare à l'index
    analysé. Il vérifie ainsi deux choses d'un coup. Aucune ligne n'a été sautée
    en tête de tableau, et la convention de date porte bien janvier 1927 au
    31 janvier et non au 1er.
    """
    provider = FrenchProvider(client=_client_reseau(), raw_root=tmp_path / "french")
    texte = provider.read_text("10_Portfolios_Prior_12_2")
    lignes = texte.replace("\r", "").split("\n")
    premieres = [ligne for ligne in lignes if ligne[:6].isdigit()]
    assert premieres[0].split(",")[0] == "192701"
    frame = provider.momentum_deciles()
    assert frame.index[0] == pd.Timestamp("1927-01-31")
    assert list(frame.columns) == [nom.upper() for nom in COLONNES_DU_FICHIER]
    # Source (a) : un rendement mensuel de décile reste sous 1000 % en décimales.
    assert float(np.nanmax(np.abs(frame.to_numpy()))) < 10.0


@pytest.mark.network
def test_reseau_le_facteur_de_momentum_se_rebatit_depuis_les_six_portefeuilles(tmp_path) -> None:
    """Source (c) : la définition publiée du facteur, et (a) sa tolérance.

    La bibliothèque définit le facteur de momentum comme la moyenne des deux
    portefeuilles gagnants moins la moyenne des deux perdants, du tri croisé
    taille sur momentum. Rejouer cette définition sur les six portefeuilles doit
    redonner le facteur publié.

    La tolérance vient d'un calcul. Les deux fichiers publient au centième de
    point, soit 5e-5 en décimales, et une moyenne de deux valeurs arrondies plus
    la différence de deux moyennes donnent au pire 1,0e-4.

    Ce test est la contre-épreuve de :func:`decile_spread` : l'écart des déciles
    extrêmes, lui, ne redonne PAS le facteur.
    """
    provider = FrenchProvider(client=_client_reseau(), raw_root=tmp_path / "french")
    six = provider.portfolio_returns("6_Portfolios_ME_Prior_12_2")
    momentum = provider.fetch("F-F_Momentum_Factor")["MOM"]
    gagnants = 0.5 * (six["SMALL HIPRIOR"] + six["BIG HIPRIOR"])
    perdants = 0.5 * (six["SMALL LOPRIOR"] + six["BIG LOPRIOR"])
    rebati = (gagnants - perdants).reindex(momentum.index).dropna()
    publie = momentum.reindex(rebati.index)
    assert len(rebati) > 1100
    assert float(np.max(np.abs(rebati.to_numpy() - publie.to_numpy()))) <= 1.05e-4
    # L'écart des déciles extrêmes est une AUTRE série, et l'écart le montre.
    ecart = provider.momentum_spread().reindex(rebati.index)
    assert float(np.max(np.abs(ecart.to_numpy() - publie.to_numpy()))) > 1e-2


@pytest.mark.network
def test_reseau_les_effectifs_des_deciles_sont_tres_inegaux(tmp_path) -> None:
    """Source (c) : le tableau des effectifs du fichier, sur ses 1 194 mois.

    Ce test ancre les deux chiffres que porte la docstring de
    :meth:`FrenchProvider.momentum_deciles`. Il lit le tableau publié, pas une
    sortie de calcul, et il échouerait si un millésime égalisait les effectifs.
    """
    provider = FrenchProvider(client=_client_reseau(), raw_root=tmp_path / "french")
    effectifs = provider.fetch("10_Portfolios_Prior_12_2", table="number_of_firms_in_portfolios")
    assert len(effectifs) == 1194
    juin = effectifs.loc[pd.Timestamp("2026-06-30")]
    assert float(juin[LOSER_DECILE]) == 614.0
    assert float(juin[WINNER_DECILE]) == 420.0
    assert float(juin["PRIOR 5"]) == 239.0
    rapport = (effectifs.max(axis=1) / effectifs.min(axis=1)).median()
    # Source (a) : la docstring annonce 2,11, arrondi au centième.
    assert float(rapport) == pytest.approx(2.11, abs=5e-3)

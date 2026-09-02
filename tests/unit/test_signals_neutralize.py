"""Contrôles du module ``quantlab.signals.neutralize``.

Chaque valeur attendue vient d'une source déclarée en commentaire, jamais de la
sortie du code. Les quatre sources admises sont le calcul à la main, l'identité
mathématique, la valeur publiée et l'implémentation indépendante.
"""

from __future__ import annotations

import hypothesis.strategies as st
import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm
from hypothesis import given, settings

from quantlab.analytics.regression import residualize
from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.signals.neutralize import (
    INTERCEPT_COLUMN,
    exposure_report,
    neutralize,
    neutralize_market_beta,
    neutralize_sector,
    neutralize_size,
    orthogonalize,
    sector_dummies,
)

ASSETS = list("abcdef")
DATES = pd.to_datetime(["2020-01-31", "2020-02-29", "2020-03-31"])

#: Le bêta de chaque actif. Il n'est pas une fonction affine de la taille, donc
#: le plan à deux expositions reste de rang plein.
BETA = pd.Series([0.8, 1.0, 1.2, 0.9, 1.1, 1.3], index=ASSETS, name="beta")

#: La taille de chaque actif, déjà en unités arbitraires.
SIZE = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], index=ASSETS, name="size")

#: Le secteur de chaque actif : trois modalités, deux membres chacune.
SECTORS = pd.Series(["tech", "energie", "sante", "tech", "energie", "sante"], index=ASSETS)


def _panel(rows: list[list[float]]) -> pd.DataFrame:
    """Rend un panier de signal aux dates et actifs de référence."""
    return pd.DataFrame(rows, index=DATES, columns=ASSETS, dtype=float)


def _spanned_panel() -> pd.DataFrame:
    """Rend un signal qui est EXACTEMENT une combinaison des deux expositions.

    Les trois dates portent des chargements différents, ce qui permet de tester
    aussi la moyenne et le t de :func:`exposure_report`.

    Date 1 : 0,1 plus 1,0 fois le bêta moins 0,5 fois la taille.
    Date 2 : 0,2 plus 1,5 fois le bêta moins 1,0 fois la taille.
    Date 3 : 0,3 plus 2,0 fois le bêta moins 1,5 fois la taille.
    """
    intercepts = [0.1, 0.2, 0.3]
    on_beta = [1.0, 1.5, 2.0]
    on_size = [-0.5, -1.0, -1.5]
    rows = [
        [a + b * beta + c * size for beta, size in zip(BETA, SIZE, strict=True)]
        for a, b, c in zip(intercepts, on_beta, on_size, strict=True)
    ]
    return _panel(rows)


# --------------------------------------------------------------------------- #
# neutralize : les deux cas qui bornent le comportement
# --------------------------------------------------------------------------- #


def test_signal_dans_lespace_des_expositions_donne_zero() -> None:
    """Source (b) : identité de projection.

    Un vecteur qui appartient à l'espace engendré par les colonnes du plan est
    son propre projeté. Le résidu est donc le vecteur nul, à la précision de la
    double précision près.
    """
    residual = neutralize(_spanned_panel(), {"beta": BETA, "size": SIZE})
    assert np.abs(residual.to_numpy()).max() == pytest.approx(0.0, abs=1e-12)


def test_signal_orthogonal_reste_inchange() -> None:
    """Source (a) : calcul à la main sur quatre actifs.

    Le plan porte la constante et l'exposition x. Le signal s vérifie deux
    orthogonalités, vérifiées ici à la main.
    La somme de s vaut 1 moins 1 moins 1 plus 1, soit zéro.
    Le produit de s par x vaut -1,5 plus 0,5 moins 0,5 plus 1,5, soit zéro.
    La projection est donc nulle et le résidu vaut s.
    """
    assets = list("wxyz")
    dates = DATES[:1]
    exposure = pd.Series([-1.5, -0.5, 0.5, 1.5], index=assets, name="x")
    signal = pd.DataFrame([[1.0, -1.0, -1.0, 1.0]], index=dates, columns=assets)

    residual = neutralize(signal, exposure, min_names=3)

    expected = np.array([1.0, -1.0, -1.0, 1.0])
    assert residual.to_numpy()[0] == pytest.approx(expected, abs=1e-12)


def test_accord_avec_residualize_du_module_de_regression() -> None:
    """Source (d) : implémentation indépendante, ``analytics.regression.residualize``.

    La coupe d'une seule date est un échantillon comme un autre. Le module de
    régression la traite par ``statsmodels`` ; ce module la traite par
    ``numpy.linalg.lstsq``. Les deux chemins doivent rendre le même résidu.
    """
    signal = _panel(
        [
            [0.03, -0.01, 0.05, 0.02, -0.04, 0.01],
            [0.00, 0.02, -0.03, 0.06, 0.01, -0.02],
            [0.04, 0.03, 0.00, -0.05, 0.02, 0.07],
        ]
    )
    factors = pd.DataFrame({"beta": BETA, "size": SIZE})

    mine = neutralize(signal, {"beta": BETA, "size": SIZE})

    for date in DATES:
        theirs = residualize(signal.loc[date], factors)
        assert mine.loc[date].to_numpy() == pytest.approx(theirs.to_numpy(), abs=1e-12)


def test_ponderation_accord_avec_les_moindres_carres_ponderes() -> None:
    """Source (d) : implémentation indépendante, ``statsmodels.api.WLS``."""
    signal = _panel(
        [
            [0.03, -0.01, 0.05, 0.02, -0.04, 0.01],
            [0.00, 0.02, -0.03, 0.06, 0.01, -0.02],
            [0.04, 0.03, 0.00, -0.05, 0.02, 0.07],
        ]
    )
    weights = pd.Series([1.0, 2.0, 3.0, 1.0, 4.0, 2.0], index=ASSETS)
    design = sm.add_constant(pd.DataFrame({"beta": BETA, "size": SIZE}))

    mine = neutralize(signal, {"beta": BETA, "size": SIZE}, weights=weights)

    for date in DATES:
        theirs = sm.WLS(signal.loc[date], design, weights=weights).fit().resid
        assert mine.loc[date].to_numpy() == pytest.approx(theirs.to_numpy(), abs=1e-12)


def test_poids_nul_exclut_de_lestimation_sans_priver_du_residu() -> None:
    """Source (a) : calcul à la main sur cinq actifs.

    Les quatre premiers actifs vérifient exactement y égale x, donc la droite
    pondérée passe par eux : la constante vaut zéro et la pente un. Le cinquième
    porte un poids nul, donc ne déplace pas la droite, et son résidu vaut
    100 moins 4, soit 96.
    """
    assets = list("vwxyz")
    exposure = pd.Series([0.0, 1.0, 2.0, 3.0, 4.0], index=assets, name="x")
    signal = pd.DataFrame([[0.0, 1.0, 2.0, 3.0, 100.0]], index=DATES[:1], columns=assets)
    weights = pd.Series([1.0, 1.0, 1.0, 1.0, 0.0], index=assets)

    residual = neutralize(signal, exposure, weights=weights, min_names=4)

    expected = np.array([0.0, 0.0, 0.0, 0.0, 96.0])
    assert residual.to_numpy()[0] == pytest.approx(expected, abs=1e-12)


def test_signal_constant_donne_un_residu_nul() -> None:
    """Source (b) : identité. Une constante appartient à l'espace de la constante."""
    signal = _panel([[2.5] * 6] * 3)
    residual = neutralize(signal, {"beta": BETA})
    assert np.abs(residual.to_numpy()).max() == pytest.approx(0.0, abs=1e-12)


def test_actif_sans_exposition_reste_manquant() -> None:
    """Source (b) : un actif sans régresseur n'entre pas dans la projection."""
    betas = BETA.copy()
    betas.loc["c"] = np.nan
    signal = _panel([[0.01, 0.02, 0.03, 0.04, 0.05, 0.06]] * 3)

    residual = neutralize(signal, {"beta": betas}, min_names=5)

    assert residual["c"].isna().all()
    assert residual.drop(columns=["c"]).notna().all().all()


def test_signal_manquant_reste_manquant() -> None:
    """Source (b) : un signal absent n'a pas de résidu."""
    signal = _panel([[0.01, 0.02, 0.03, 0.04, 0.05, 0.06]] * 3)
    signal.loc[DATES[1], "b"] = np.nan

    residual = neutralize(signal, {"beta": BETA}, min_names=5)

    assert bool(np.isnan(residual.loc[DATES[1], "b"]))
    assert residual.loc[DATES[0]].notna().all()


# --------------------------------------------------------------------------- #
# sector_dummies et la trappe de colinéarité
# --------------------------------------------------------------------------- #


def test_trois_modalites_donnent_deux_colonnes() -> None:
    """Source (a) : comptage à la main.

    Les trois modalités triées sont « energie », « sante » et « tech ». Le
    retrait de la première en laisse deux.
    """
    dummies = sector_dummies(SECTORS)
    assert dummies.columns.tolist() == ["sante", "tech"]
    assert dummies.shape == (6, 2)


def test_sans_retrait_les_trois_colonnes_sont_conservees() -> None:
    """Source (a) : comptage à la main, trois modalités et trois colonnes."""
    dummies = sector_dummies(SECTORS, drop_first=False)
    assert dummies.columns.tolist() == ["energie", "sante", "tech"]


def test_les_indicatrices_somment_a_un_hors_reference() -> None:
    """Source (a) : calcul à la main.

    L'actif « a » est technologique, donc sa ligne vaut zéro puis un. L'actif
    « b » appartient à la modalité de référence, donc sa ligne est nulle.
    """
    dummies = sector_dummies(SECTORS)
    assert dummies.loc["a"].tolist() == [0.0, 1.0]
    assert dummies.loc["b"].tolist() == [0.0, 0.0]
    assert dummies.loc["c"].tolist() == [1.0, 0.0]


def test_modalite_manquante_donne_une_ligne_manquante() -> None:
    """Source (b) : un actif sans classification n'appartient à aucun groupe."""
    sectors = SECTORS.copy()
    sectors.loc["d"] = np.nan
    dummies = sector_dummies(sectors)
    assert dummies.loc["d"].isna().all()
    assert dummies.drop(index=["d"]).notna().all().all()


def test_toutes_les_indicatrices_avec_une_constante_sont_refusees() -> None:
    """Source (b) : la somme des indicatrices reproduit la constante.

    C'est la trappe documentée dans :func:`sector_dummies`. Le plan est
    singulier, et le module refuse plutôt que de rendre une solution de norme
    minimale sans le dire.
    """
    dummies = sector_dummies(SECTORS, drop_first=False)
    exposures = {name: dummies[name] for name in dummies.columns}
    signal = _panel([[0.01, 0.02, 0.03, 0.04, 0.05, 0.06]] * 3)

    with pytest.raises(DataQualityError, match="rang déficient"):
        neutralize(signal, exposures, add_intercept=True)


def test_toutes_les_indicatrices_sans_constante_sont_acceptees() -> None:
    """Source (b) : sans constante, les trois indicatrices sont indépendantes.

    Le résidu vaut alors le signal moins la moyenne de son groupe, comme avec
    une constante et deux indicatrices.
    """
    dummies = sector_dummies(SECTORS, drop_first=False)
    exposures = {name: dummies[name] for name in dummies.columns}
    signal = _panel([[1.0, 3.0, 10.0, 5.0, 7.0, 20.0]] * 3)

    without = neutralize(signal, exposures, add_intercept=False)
    with_constant = neutralize_sector(signal, SECTORS)

    assert without.to_numpy() == pytest.approx(with_constant.to_numpy(), abs=1e-12)


def test_sans_constante_toutes_les_modalites_sont_conservees() -> None:
    """Source (a) : calcul à la main sur trois groupes de deux actifs.

    Sans constante, la première modalité ne doit PAS être retirée, sans quoi le
    groupe de référence n'aurait plus de moyenne à retirer et garderait son
    signal brut. Groupe « energie », les actifs b et e, valeurs 3 et 7, moyenne
    5, résidus -2 et 2. Groupe « sante », les actifs c et f, valeurs 10 et 20,
    moyenne 15, résidus -5 et 5. Groupe « tech », les actifs a et d, valeurs 1
    et 5, moyenne 3, résidus -2 et 2.
    """
    signal = _panel([[1.0, 3.0, 10.0, 5.0, 7.0, 20.0]] * 3)

    residual = neutralize_sector(signal, SECTORS, add_intercept=False)

    expected = np.array([-2.0, -2.0, -5.0, 2.0, 2.0, 5.0])
    assert residual.to_numpy()[0] == pytest.approx(expected, abs=1e-12)


# --------------------------------------------------------------------------- #
# Les trois raccourcis
# --------------------------------------------------------------------------- #


def test_neutraliser_le_secteur_retire_la_moyenne_du_groupe() -> None:
    """Source (a) : calcul à la main sur deux groupes de trois actifs.

    Groupe A, les actifs a, b et f, valeurs 1, 3 et 5, moyenne 3, résidus -2, 0
    et 2. Groupe B, les actifs c, d et e, valeurs 10, 20 et 30, moyenne 20,
    résidus -10, 0 et 10.
    """
    sectors = pd.Series(["A", "A", "B", "B", "B", "A"], index=ASSETS)
    signal = _panel([[1.0, 3.0, 10.0, 20.0, 30.0, 5.0]] * 3)

    residual = neutralize_sector(signal, sectors)

    expected = np.array([-2.0, 0.0, -10.0, 0.0, 10.0, 2.0])
    assert residual.to_numpy()[0] == pytest.approx(expected, abs=1e-12)


def test_secteur_absent_a_une_date_laisse_la_constante_seule() -> None:
    """Source (a) : calcul à la main sur une date où tous les actifs sont dans A.

    L'indicatrice de B est alors identiquement nulle, donc retirée. Le plan se
    réduit à la constante, et le résidu vaut le signal moins sa moyenne. La
    moyenne de 1, 2, 3, 4, 5 et 6 vaut 3,5, donc le premier résidu vaut -2,5.
    """
    sectors = pd.DataFrame(
        [
            ["A", "A", "A", "B", "B", "B"],
            ["A", "A", "A", "A", "B", "B"],
            ["A", "A", "A", "A", "A", "A"],
        ],
        index=DATES,
        columns=ASSETS,
    )
    signal = _panel([[1.0, 2.0, 3.0, 4.0, 5.0, 6.0]] * 3)

    residual = neutralize_sector(signal, sectors)

    expected = np.array([-2.5, -1.5, -0.5, 0.5, 1.5, 2.5])
    assert residual.loc[DATES[2]].to_numpy() == pytest.approx(expected, abs=1e-12)


def test_neutraliser_le_beta_annule_la_correlation_transversale() -> None:
    """Source (b) : identité des moindres carrés, le résidu est orthogonal au régresseur."""
    signal = _panel(
        [
            [0.03, -0.01, 0.05, 0.02, -0.04, 0.01],
            [0.00, 0.02, -0.03, 0.06, 0.01, -0.02],
            [0.04, 0.03, 0.00, -0.05, 0.02, 0.07],
        ]
    )
    residual = neutralize_market_beta(signal, BETA)
    for date in DATES:
        correlation = np.corrcoef(residual.loc[date].to_numpy(), BETA.to_numpy())[0, 1]
        assert correlation == pytest.approx(0.0, abs=1e-12)


def test_neutraliser_la_taille_passe_par_le_logarithme() -> None:
    """Source (b) : identité, la fonction applique le logarithme naturel elle-même."""
    caps = pd.Series([1e8, 5e8, 2e9, 1e10, 4e10, 3e11], index=ASSETS)
    signal = _panel([[0.03, -0.01, 0.05, 0.02, -0.04, 0.01]] * 3)

    automatique = neutralize_size(signal, caps, log=True)
    manuelle = neutralize(signal, {"size": np.log(caps)})

    assert automatique.to_numpy() == pytest.approx(manuelle.to_numpy(), abs=1e-12)


def test_neutraliser_la_taille_sans_logarithme_utilise_le_niveau() -> None:
    """Source (b) : identité, sans transformation le régresseur est la capitalisation."""
    caps = pd.Series([1e8, 5e8, 2e9, 1e10, 4e10, 3e11], index=ASSETS)
    signal = _panel([[0.03, -0.01, 0.05, 0.02, -0.04, 0.01]] * 3)

    brute = neutralize_size(signal, caps, log=False)
    attendue = neutralize(signal, {"size": caps})

    assert brute.to_numpy() == pytest.approx(attendue.to_numpy(), abs=1e-12)


def test_capitalisation_nulle_refusee_en_logarithme() -> None:
    """Source (b) : le logarithme de zéro n'existe pas."""
    caps = pd.Series([1e8, 0.0, 2e9, 1e10, 4e10, 3e11], index=ASSETS)
    signal = _panel([[0.03, -0.01, 0.05, 0.02, -0.04, 0.01]] * 3)

    with pytest.raises(DataQualityError, match="logarithme"):
        neutralize_size(signal, caps)


# --------------------------------------------------------------------------- #
# orthogonalize
# --------------------------------------------------------------------------- #


def test_somme_de_deux_signaux_existants_est_entierement_expliquee() -> None:
    """Source (b) : identité de projection, la somme est dans l'espace engendré."""
    first = _panel(
        [
            [0.03, -0.01, 0.05, 0.02, -0.04, 0.01],
            [0.00, 0.02, -0.03, 0.06, 0.01, -0.02],
            [0.04, 0.03, 0.00, -0.05, 0.02, 0.07],
        ]
    )
    second = _panel(
        [
            [0.01, 0.04, -0.02, 0.00, 0.03, -0.05],
            [0.02, -0.03, 0.01, 0.05, -0.01, 0.04],
            [-0.04, 0.01, 0.06, 0.02, 0.00, 0.03],
        ]
    )
    candidate = first + second

    residual = orthogonalize(candidate, {"a": first, "b": second})

    assert np.abs(residual.to_numpy()).max() == pytest.approx(0.0, abs=1e-14)


def test_un_signal_deja_orthogonal_survit_intact() -> None:
    """Source (a) : calcul à la main sur quatre actifs.

    Le signal existant vaut -1,5, -0,5, 0,5 et 1,5, de somme nulle. Le candidat
    vaut 1, -1, -1 et 1, de somme nulle. Leur produit terme à terme somme à
    -1,5 plus 0,5 moins 0,5 plus 1,5, soit zéro.
    """
    assets = list("wxyz")
    existing = pd.DataFrame([[-1.5, -0.5, 0.5, 1.5]], index=DATES[:1], columns=assets)
    candidate = pd.DataFrame([[1.0, -1.0, -1.0, 1.0]], index=DATES[:1], columns=assets)

    residual = orthogonalize(candidate, existing, min_names=3)

    assert residual.to_numpy()[0] == pytest.approx(np.array([1.0, -1.0, -1.0, 1.0]), abs=1e-12)


def test_suite_et_dictionnaire_donnent_le_meme_residu() -> None:
    """Source (b) : identité, le nom des colonnes ne change pas la projection."""
    first = _panel([[0.03, -0.01, 0.05, 0.02, -0.04, 0.01]] * 3)
    second = _panel([[0.01, 0.04, -0.02, 0.00, 0.03, -0.05]] * 3)
    candidate = _panel([[0.02, 0.01, 0.00, -0.03, 0.04, 0.05]] * 3)

    par_suite = orthogonalize(candidate, [first, second])
    par_dictionnaire = orthogonalize(candidate, {"un": first, "deux": second})

    assert par_suite.to_numpy() == pytest.approx(par_dictionnaire.to_numpy(), abs=1e-12)


def test_suite_vide_refusee() -> None:
    """Source (b) : sans signal existant, il n'y a rien à retirer."""
    candidate = _panel([[0.02, 0.01, 0.00, -0.03, 0.04, 0.05]] * 3)
    with pytest.raises(ConfigError, match="vide"):
        orthogonalize(candidate, [])


# --------------------------------------------------------------------------- #
# exposure_report
# --------------------------------------------------------------------------- #


def test_rapport_retrouve_les_chargements_construits() -> None:
    """Source (a) : calcul à la main sur les chargements imposés.

    Le signal est construit avec les chargements 1,0, 1,5 et 2,0 sur le bêta,
    de moyenne 1,5 et d'écart type d'échantillon 0,5. Le t vaut 1,5 divisé par
    0,5 sur racine de 3, soit 3 fois racine de 3.
    Les chargements de taille valent -0,5, -1,0 et -1,5, de moyenne -1,0 et de
    même écart type, donc un t de moins 2 fois racine de 3.
    Les constantes valent 0,1, 0,2 et 0,3, de moyenne 0,2 et d'écart type 0,1,
    donc un t de 2 fois racine de 3.
    """
    report = exposure_report(_spanned_panel(), {"beta": BETA, "size": SIZE})

    assert report.index.tolist() == [INTERCEPT_COLUMN, "beta", "size"]
    assert report.loc["beta", "loading_before"] == pytest.approx(1.5, abs=1e-12)
    assert report.loc["size", "loading_before"] == pytest.approx(-1.0, abs=1e-12)
    assert report.loc[INTERCEPT_COLUMN, "loading_before"] == pytest.approx(0.2, abs=1e-12)
    assert report.loc["beta", "tstat_before"] == pytest.approx(3.0 * np.sqrt(3.0), rel=1e-10)
    assert report.loc["size", "tstat_before"] == pytest.approx(-2.0 * np.sqrt(3.0), rel=1e-10)
    assert report.loc[INTERCEPT_COLUMN, "tstat_before"] == pytest.approx(2.0 * np.sqrt(3.0), rel=1e-10)
    assert report["n_periods"].tolist() == [3, 3, 3]


def test_rapport_montre_un_chargement_nul_apres_neutralisation() -> None:
    """Source (b) : identité, le résidu est orthogonal au plan qui l'a produit.

    Le t d'après neutralisation est rendu manquant : il serait le rapport de
    deux poussières d'arrondi, et un lecteur y lirait un chiffre.
    """
    report = exposure_report(_spanned_panel(), {"beta": BETA, "size": SIZE})

    assert np.abs(report["loading_after"].to_numpy()).max() == pytest.approx(0.0, abs=1e-10)
    assert report["tstat_after"].isna().all()


def test_rapport_sans_dispersion_ne_rend_pas_un_t_infini() -> None:
    """Source (b) : un écart type nul ne définit aucun t.

    Les trois dates portent le même chargement, donc la dispersion est nulle et
    le rapport de Fama et MacBeth n'existe pas.
    """
    rows = [[1.0 * beta for beta in BETA]] * 3
    report = exposure_report(_panel(rows), {"beta": BETA})

    assert report.loc["beta", "loading_before"] == pytest.approx(1.0, abs=1e-12)
    assert bool(np.isnan(report.loc["beta", "tstat_before"]))


# --------------------------------------------------------------------------- #
# Les refus
# --------------------------------------------------------------------------- #


def test_exposition_transposee_refusee() -> None:
    """Source (b) : un tableau d'actifs par modalités n'est pas un panier daté."""
    dummies = sector_dummies(SECTORS)
    signal = _panel([[0.01, 0.02, 0.03, 0.04, 0.05, 0.06]] * 3)
    with pytest.raises(ConfigError, match="transposée"):
        neutralize(signal, {"secteur": dummies})


def test_exposition_indexee_par_les_dates_refusee() -> None:
    """Source (b) : une exposition fixe est indexée par les actifs."""
    signal = _panel([[0.01, 0.02, 0.03, 0.04, 0.05, 0.06]] * 3)
    mauvaise = pd.Series([1.0, 2.0, 3.0], index=DATES)
    with pytest.raises(ConfigError, match="indexée par les dates"):
        neutralize(signal, {"beta": mauvaise})


def test_poids_negatif_refuse() -> None:
    """Source (b) : un poids négatif renverse le sens du critère minimisé."""
    signal = _panel([[0.01, 0.02, 0.03, 0.04, 0.05, 0.06]] * 3)
    weights = pd.Series([1.0, 1.0, -1.0, 1.0, 1.0, 1.0], index=ASSETS)
    with pytest.raises(DataQualityError, match="négatif"):
        neutralize(signal, {"beta": BETA}, weights=weights)


def test_dates_en_double_refusees() -> None:
    """Source (b) : une date en double rendrait l'appariement ambigu."""
    index = pd.to_datetime(["2020-01-31", "2020-01-31"])
    signal = pd.DataFrame([[0.01] * 6, [0.02] * 6], index=index, columns=ASSETS)
    with pytest.raises(DataQualityError, match="double"):
        neutralize(signal, {"beta": BETA})


def test_panier_vide_refuse() -> None:
    """Source (b) : aucune coupe transversale n'existe sur un tableau vide."""
    with pytest.raises(InsufficientDataError, match="vide"):
        neutralize(pd.DataFrame(), {"beta": BETA})


def test_plan_sans_colonne_refuse() -> None:
    """Source (b) : une classification entièrement absente ne donne aucune colonne.

    Sans constante non plus, il ne reste rien sur quoi projeter, et le module
    refuse plutôt que de rendre le signal intact sous le nom de résidu.
    """
    sectors = pd.Series([np.nan] * 6, index=ASSETS, dtype=object)
    signal = _panel([[0.01, 0.02, 0.03, 0.04, 0.05, 0.06]] * 3)
    with pytest.raises(ConfigError, match="plan de régression est vide"):
        neutralize(signal, {"secteur": sectors}, add_intercept=False)


def test_une_seule_modalite_laisse_la_constante_seule() -> None:
    """Source (a) : calcul à la main.

    L'unique modalité reproduit la constante, donc elle est retirée. Le résidu
    vaut le signal moins sa moyenne : la moyenne de 1 à 6 vaut 3,5, donc le
    premier résidu vaut -2,5.
    """
    sectors = pd.Series(["A"] * 6, index=ASSETS)
    signal = _panel([[1.0, 2.0, 3.0, 4.0, 5.0, 6.0]] * 3)

    residual = neutralize_sector(signal, sectors)

    expected = np.array([-2.5, -1.5, -0.5, 0.5, 1.5, 2.5])
    assert residual.to_numpy()[0] == pytest.approx(expected, abs=1e-12)


def test_dictionnaire_dexpositions_vide_refuse() -> None:
    """Source (b) : sans exposition, la neutralisation n'a pas d'objet."""
    signal = _panel([[0.01, 0.02, 0.03, 0.04, 0.05, 0.06]] * 3)
    with pytest.raises(ConfigError, match="vide"):
        neutralize(signal, {})


def test_min_names_incoherent_refuse() -> None:
    """Source (b) : une régression exige au moins deux points."""
    signal = _panel([[0.01, 0.02, 0.03, 0.04, 0.05, 0.06]] * 3)
    with pytest.raises(ConfigError, match="min_names"):
        neutralize(signal, {"beta": BETA}, min_names=1)


def test_date_trop_mince_est_sautee_sans_arreter_les_autres() -> None:
    """Source (b) : une date de deux actifs ne porte pas un plan de deux colonnes.

    La ligne concernée ressort entièrement manquante, et les deux autres sont
    calculées normalement.
    """
    signal = _panel([[0.01, 0.02, 0.03, 0.04, 0.05, 0.06]] * 3)
    signal.loc[DATES[1], ["c", "d", "e", "f"]] = np.nan

    residual = neutralize(signal, {"beta": BETA}, min_names=5)

    assert residual.loc[DATES[1]].isna().all()
    assert residual.loc[DATES[0]].notna().all()
    assert residual.loc[DATES[2]].notna().all()


def test_toutes_les_dates_trop_minces_levent() -> None:
    """Source (b) : sans aucune date exploitable, il n'y a rien à rendre."""
    signal = _panel([[0.01, 0.02, np.nan, np.nan, np.nan, np.nan]] * 3)
    with pytest.raises(InsufficientDataError, match="aucune des 3 dates"):
        neutralize(signal, {"beta": BETA}, min_names=5)


def test_exposition_dun_type_inattendu_refusee() -> None:
    """Source (b) : le module ne devine pas la forme d'un objet quelconque."""
    signal = _panel([[0.01, 0.02, 0.03, 0.04, 0.05, 0.06]] * 3)
    with pytest.raises(ConfigError, match="Series ou un DataFrame"):
        neutralize(signal, {"beta": [1.0, 2.0, 3.0]})


# --------------------------------------------------------------------------- #
# Propriétés
# --------------------------------------------------------------------------- #

_VALEURS = st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False)


@settings(deadline=None, max_examples=50)
@given(values=st.lists(_VALEURS, min_size=18, max_size=18))
def test_propriete_residu_orthogonal_au_plan(values: list[float]) -> None:
    """Source (b) : identité des équations normales, le produit du plan par le résidu est nul.

    C'est la définition même des moindres carrés ordinaires. La tolérance est
    relative à l'ampleur du signal, parce que l'annulation se fait en double
    précision.
    """
    signal = _panel([values[0:6], values[6:12], values[12:18]])
    residual = neutralize(signal, {"beta": BETA, "size": SIZE})

    echelle = max(1.0, float(np.abs(signal.to_numpy()).max()))
    for date in DATES:
        residus = residual.loc[date].to_numpy()
        assert abs(float(residus.sum())) <= 1e-9 * echelle
        assert abs(float(residus @ BETA.to_numpy())) <= 1e-9 * echelle
        assert abs(float(residus @ SIZE.to_numpy())) <= 1e-9 * echelle


@settings(deadline=None, max_examples=50)
@given(values=st.lists(_VALEURS, min_size=18, max_size=18))
def test_propriete_idempotence(values: list[float]) -> None:
    """Source (b) : identité, un projecteur orthogonal appliqué deux fois vaut une fois."""
    signal = _panel([values[0:6], values[6:12], values[12:18]])
    une_fois = neutralize(signal, {"beta": BETA, "size": SIZE})
    deux_fois = neutralize(une_fois, {"beta": BETA, "size": SIZE})

    echelle = max(1.0, float(np.abs(signal.to_numpy()).max()))
    ecart = float(np.abs(une_fois.to_numpy() - deux_fois.to_numpy()).max())
    assert ecart <= 1e-9 * echelle


# --------------------------------------------------------------------------- #
# Vérification adverse : la référence sectorielle absente à une date
# --------------------------------------------------------------------------- #


def _sectors_reference_absente() -> pd.DataFrame:
    """Rend un panier sectoriel dont la référence alphabétique manque à la date 3.

    Les modalités du panier entier sont « A », « B » et « C », donc « A » est la
    référence retirée. Aucun actif n'est classé « A » à la troisième date.
    """
    return pd.DataFrame(
        [
            ["A", "A", "B", "B", "C", "C"],
            ["A", "A", "B", "B", "C", "C"],
            ["B", "B", "B", "C", "C", "C"],
        ],
        index=DATES,
        columns=ASSETS,
    )


def test_reference_absente_a_une_date_donne_les_moyennes_de_groupe() -> None:
    """Source (a) : calcul à la main sur deux groupes de trois actifs.

    À la troisième date, le groupe « B » réunit les actifs a, b et c, de valeurs
    1, 2 et 3, donc de moyenne 2 et de résidus -1, 0 et 1. Le groupe « C »
    réunit d, e et f, de valeurs 4, 5 et 6, donc de moyenne 5 et de résidus
    -1, 0 et 1.
    """
    signal = _panel([[1.0, 2.0, 3.0, 4.0, 5.0, 6.0]] * 3)

    residual = neutralize_sector(signal, _sectors_reference_absente())

    expected = np.array([-1.0, 0.0, 1.0, -1.0, 0.0, 1.0])
    assert residual.loc[DATES[2]].to_numpy() == pytest.approx(expected, abs=1e-12)


def test_le_residu_ne_depend_pas_des_modalites_des_autres_dates() -> None:
    """Source (b) : identité, le résidu d'une coupe ne dépend que de cette coupe.

    Renommer « A » en « Z » ne change aucune classification de la troisième
    date, où « A » n'apparaît pas. Cela déplace en revanche la référence
    alphabétique globale. Les résidus de la troisième date doivent donc rester
    les mêmes, sans quoi une modalité observée ailleurs déciderait de cette
    coupe.
    """
    signal = _panel([[1.0, 2.0, 3.0, 4.0, 5.0, 6.0]] * 3)
    sectors = _sectors_reference_absente()

    avec_a = neutralize_sector(signal, sectors)
    avec_z = neutralize_sector(signal, sectors.replace("A", "Z"))

    assert avec_a.loc[DATES[2]].to_numpy() == pytest.approx(avec_z.loc[DATES[2]].to_numpy(), abs=1e-12)


def test_une_seule_modalite_non_reference_laisse_la_constante_seule() -> None:
    """Source (a) : calcul à la main sur une date entièrement classée « B ».

    L'unique indicatrice vivante vaut un partout, donc elle reproduit la
    constante et se retire. Le plan se réduit à la constante et le résidu vaut
    le signal moins sa moyenne. La moyenne de 1 à 6 vaut 3,5, donc le premier
    résidu vaut -2,5.
    """
    sectors = pd.DataFrame(
        [
            ["A", "A", "A", "B", "B", "B"],
            ["A", "A", "A", "B", "B", "B"],
            ["B", "B", "B", "B", "B", "B"],
        ],
        index=DATES,
        columns=ASSETS,
    )
    signal = _panel([[1.0, 2.0, 3.0, 4.0, 5.0, 6.0]] * 3)

    residual = neutralize_sector(signal, sectors)

    expected = np.array([-2.5, -1.5, -0.5, 0.5, 1.5, 2.5])
    assert residual.loc[DATES[2]].to_numpy() == pytest.approx(expected, abs=1e-12)


def test_reference_absente_sous_ponderation_reste_juste() -> None:
    """Source (d) : implémentation indépendante, ``statsmodels.api.WLS``.

    Le plan de la troisième date est écrit à la main, avec la modalité « B »
    pour référence locale et l'indicatrice de « C » pour seule colonne.
    """
    signal = _panel([[1.0, 2.0, 3.0, 4.0, 5.0, 6.0]] * 3)
    weights = pd.Series([1.0, 2.0, 3.0, 1.0, 4.0, 2.0], index=ASSETS)

    residual = neutralize_sector(signal, _sectors_reference_absente(), weights=weights)

    design = pd.DataFrame(
        {"const": 1.0, "c": [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]},
        index=ASSETS,
    )
    theirs = sm.WLS(signal.loc[DATES[2]], design, weights=weights).fit().resid
    assert residual.loc[DATES[2]].to_numpy() == pytest.approx(theirs.to_numpy(), abs=1e-12)


def test_chargement_numerique_survit_au_changement_de_reference() -> None:
    """Source (b) : identité, un coefficient ne dépend que de l'espace engendré.

    Le coefficient du bêta se lit sur la partie du bêta que les indicatrices et
    la constante n'expliquent pas. Cette partie ne change pas quand on change de
    modalité de référence, puisque l'espace engendré est le même. Le chargement
    du bêta doit donc être identique dans les deux étiquetages, alors que celui
    de la constante est déclaré manquant à la date rebasée.
    """
    signal = _panel(
        [
            [0.03, -0.01, 0.05, 0.02, -0.04, 0.01],
            [0.00, 0.02, -0.03, 0.06, 0.01, -0.02],
            [0.04, 0.03, 0.00, -0.05, 0.02, 0.07],
        ]
    )
    sectors = _sectors_reference_absente()

    rebase = exposure_report(signal, {"sector": sectors, "beta": BETA})
    intact = exposure_report(signal, {"sector": sectors.replace("A", "Z"), "beta": BETA})

    assert rebase.loc["beta", "loading_before"] == pytest.approx(
        intact.loc["beta", "loading_before"], abs=1e-12
    )
    assert rebase.loc["beta", "n_periods"] == 3
    # La constante et le bloc sectoriel perdent la date rebasée, la troisième.
    assert rebase.loc[INTERCEPT_COLUMN, "n_periods"] == 2
    assert intact.loc[INTERCEPT_COLUMN, "n_periods"] == 3


# --------------------------------------------------------------------------- #
# Vérification adverse : les collisions de noms de colonnes
# --------------------------------------------------------------------------- #


def test_colonne_produite_deux_fois_refusee() -> None:
    """Source (a) : calcul à la main sur un signal purement sectoriel.

    Le signal vaut 10 dans le secteur « x » et -10 dans « y », donc sa
    neutralisation sectorielle vaut exactement zéro. L'exposition « s »
    engendre la colonne « s_y », que l'exposition numérique du même nom
    écraserait dans le dictionnaire des blocs. Le signal ressortirait alors
    intact sous le nom de résidu, sans qu'aucun message ne le dise.
    """
    sectors = pd.Series(["x", "y", "x", "y", "x", "y"], index=ASSETS)
    signal = _panel([[10.0, -10.0, 10.0, -10.0, 10.0, -10.0]] * 3)

    seul = neutralize(signal, {"s": sectors})
    assert np.abs(seul.to_numpy()).max() == pytest.approx(0.0, abs=1e-12)

    with pytest.raises(ConfigError, match="déjà produite"):
        neutralize(signal, {"s": sectors, "s_y": BETA})
    with pytest.raises(ConfigError, match="déjà produite"):
        neutralize(signal, {"s_y": BETA, "s": sectors})


def test_exposition_nommee_intercept_refusee() -> None:
    """Source (b) : deux colonnes de même nom rendent le rapport illisible.

    Le plan porte déjà une colonne « intercept ». Une exposition du même nom
    donnerait deux colonnes homonymes dans le tableau des chargements, dont
    aucune lecture par étiquette ne pourrait plus être faite.
    """
    signal = _panel([[0.01, 0.02, 0.03, 0.04, 0.05, 0.06]] * 3)

    with pytest.raises(ConfigError, match="nom réservé"):
        neutralize(signal, {INTERCEPT_COLUMN: BETA})

    # Sans constante, le nom n'est plus réservé et l'exposition passe.
    sans_constante = neutralize(signal, {INTERCEPT_COLUMN: BETA}, add_intercept=False)
    assert sans_constante.notna().all().all()


# --------------------------------------------------------------------------- #
# Vérification adverse : aucune information future
# --------------------------------------------------------------------------- #


def test_une_date_ajoutee_apres_ne_bouge_aucun_residu_anterieur() -> None:
    """Source (b) : identité, chaque coupe est résolue seule.

    Une quatrième date ajoutée au panier ne peut rien changer aux trois
    premières. L'égalité est exigée AU BIT PRÈS, et non à une tolérance, parce
    que les mêmes opérations flottantes doivent être exécutées dans le même
    ordre. Une statistique calculée sur le panier entier, moyenne, écart type ou
    quantile, ferait échouer ce test.
    """
    signal = _panel(
        [
            [0.03, -0.01, 0.05, 0.02, -0.04, 0.01],
            [0.00, 0.02, -0.03, 0.06, 0.01, -0.02],
            [0.04, 0.03, 0.00, -0.05, 0.02, 0.07],
        ]
    )
    futur = pd.DataFrame(
        [[9.0, -9.0, 4.0, -4.0, 1.0, -1.0]],
        index=pd.to_datetime(["2020-04-30"]),
        columns=ASSETS,
    )
    allonge = pd.concat([signal, futur])

    court = neutralize(signal, {"beta": BETA, "size": SIZE})
    long = neutralize(allonge, {"beta": BETA, "size": SIZE})

    assert np.array_equal(court.to_numpy(), long.loc[DATES].to_numpy())


def test_un_secteur_apparu_plus_tard_ne_bouge_pas_les_residus_anterieurs() -> None:
    """Source (b) : identité, une modalité absente d'une coupe n'y pèse rien.

    Un quatrième secteur, qui n'existe qu'à une date postérieure, ajoute une
    colonne au plan. Cette colonne est nulle aux dates antérieures, donc elle en
    est retirée, et leurs résidus ne bougent pas d'un bit.
    """
    signal = _panel([[1.0, 2.0, 3.0, 4.0, 5.0, 6.0]] * 3)
    sectors = _sectors_reference_absente()
    court = neutralize_sector(signal, sectors)

    futur_signal = pd.concat(
        [signal, pd.DataFrame([[7.0] * 6], index=pd.to_datetime(["2020-04-30"]), columns=ASSETS)]
    )
    futur_sectors = pd.concat(
        [sectors, pd.DataFrame([["D"] * 3 + ["B"] * 3], index=pd.to_datetime(["2020-04-30"]), columns=ASSETS)]
    )
    long = neutralize_sector(futur_signal, futur_sectors)

    assert np.array_equal(court.to_numpy(), long.loc[DATES].to_numpy())


def test_poids_manquant_ecarte_lactif_de_la_date() -> None:
    """Source (b) : sans poids, l'actif n'a pas de place dans le critère pondéré.

    Le comportement diffère du poids nul, qui laisse le résidu. Il est décrit
    dans la documentation de :func:`neutralize`, et ce test le fige.
    """
    signal = _panel([[0.01, 0.02, 0.03, 0.04, 0.05, 0.06]] * 3)
    weights = pd.Series([1.0, 1.0, 1.0, 1.0, 1.0, np.nan], index=ASSETS)

    residual = neutralize(signal, {"beta": BETA}, weights=weights, min_names=3)

    assert residual["f"].isna().all()
    assert residual.drop(columns=["f"]).notna().all().all()


def test_reference_portee_par_un_seul_actif_de_poids_nul() -> None:
    """Source (a) : calcul à la main sur cinq actifs pondérés et un écarté.

    L'actif « a » est le seul classé « A », et son poids est nul, donc il ne
    pèse pas dans l'estimation. Les indicatrices « B » et « C » somment à un
    chez tous les actifs qui pèsent, donc la référence locale doit changer.
    La droite se fixe alors sur les cinq actifs pondérés : le groupe « B »
    réunit b et c, de valeurs 2 et 3, donc de moyenne 2,5 et de résidus -0,5 et
    0,5. Le groupe « C » réunit d, e et f, de valeurs 4, 5 et 6, donc de moyenne
    5 et de résidus -1, 0 et 1. L'actif « a » reçoit l'ajustement du groupe de
    référence, soit 2,5, et son résidu vaut 1 moins 2,5.
    """
    sectors = pd.DataFrame([["A", "B", "B", "C", "C", "C"]] * 3, index=DATES, columns=ASSETS)
    signal = _panel([[1.0, 2.0, 3.0, 4.0, 5.0, 6.0]] * 3)
    weights = pd.Series([0.0, 1.0, 1.0, 1.0, 1.0, 1.0], index=ASSETS)

    residual = neutralize_sector(signal, sectors, weights=weights, min_names=4)

    expected = np.array([-1.5, -0.5, 0.5, -1.0, 0.0, 1.0])
    assert residual.to_numpy()[0] == pytest.approx(expected, abs=1e-12)


def test_deux_blocs_qualitatifs_rebases_a_la_meme_date() -> None:
    """Source (d) : implémentation indépendante, ``statsmodels.api.OLS``.

    Les deux classifications perdent leur référence à la troisième date, donc
    chacune doit céder une modalité de plus. Le plan attendu est écrit à la
    main : la constante, l'indicatrice de « C » pour la première et celle de
    « R » pour la seconde.
    """
    first = pd.DataFrame(
        [
            ["A", "A", "B", "B", "C", "C"],
            ["A", "A", "B", "B", "C", "C"],
            ["B", "B", "B", "C", "C", "C"],
        ],
        index=DATES,
        columns=ASSETS,
    )
    second = pd.DataFrame(
        [
            ["P", "Q", "P", "Q", "P", "Q"],
            ["P", "Q", "P", "Q", "P", "Q"],
            ["Q", "Q", "R", "R", "Q", "R"],
        ],
        index=DATES,
        columns=ASSETS,
    )
    signal = _panel([[1.0, 2.0, 3.0, 4.0, 5.0, 6.0]] * 3)

    residual = neutralize(signal, {"s1": first, "s2": second}, min_names=4)

    design = pd.DataFrame(
        {
            "const": 1.0,
            "s1_C": [0.0, 0.0, 0.0, 1.0, 1.0, 1.0],
            "s2_R": [0.0, 0.0, 1.0, 1.0, 0.0, 1.0],
        },
        index=ASSETS,
    )
    theirs = sm.OLS(signal.loc[DATES[2]], design).fit().resid
    assert residual.loc[DATES[2]].to_numpy() == pytest.approx(theirs.to_numpy(), abs=1e-12)

"""Contrôles du module ``quantlab.analytics.regression``.

Règle du laboratoire tenue ici : aucune valeur attendue ne vient de la sortie du
code testé. Chaque test dit dans son commentaire d'où sort sa cible, parmi les
quatre sources admises, (a) calcul à la main, (b) identité mathématique,
(c) valeur publiée, (d) implémentation indépendante.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from quantlab.analytics.regression import (
    DEFAULT_BLUME_WEIGHT,
    INTERCEPT_NAME,
    attribution_table,
    beta,
    factor_regression,
    newey_west_lags,
    residualize,
    rolling_alpha,
    rolling_beta,
    shrunk_beta,
)
from quantlab.core.determinism import child_generators
from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.types import Frequency

# Graine de l'expérience, fixée une fois pour tout le fichier.
SEED = 20260901

# Les cinq couples de rendements du calcul à la main, en clair.
HAND_MARKET = [0.01, -0.02, 0.03, 0.00, -0.01]
HAND_ASSET = [0.02, -0.03, 0.05, 0.01, -0.02]
# Moyennes : marché 0,002 et actif 0,006.
# Écarts marché : 0,008 ; -0,022 ; 0,028 ; -0,002 ; -0,012.
# Écarts actif  : 0,014 ; -0,036 ; 0,044 ;  0,004 ; -0,026.
# Somme des produits : 0,000112 + 0,000792 + 0,001232 - 0,000008 + 0,000312 = 0,00244.
# Somme des carrés du marché : 0,000064 + 0,000484 + 0,000784 + 0,000004 + 0,000144 = 0,00148.
# Bêta = 0,00244 / 0,00148 = 244/148 = 61/37 = 1,6486486...
HAND_BETA = 61.0 / 37.0


def _index(n: int) -> pd.DatetimeIndex:
    """Rend un index mensuel de fin de mois, sans jour férié à gérer."""
    return pd.date_range("2000-01-31", periods=n, freq="ME")


def _simulated_panel(
    n: int = 3000,
    alpha_true: float = 0.0015,
    betas_true: tuple[float, float, float] = (1.20, -0.40, 0.60),
    sigma: float = 0.02,
) -> tuple[pd.Series, pd.DataFrame, float, tuple[float, float, float]]:
    """Rend un échantillon simulé dont les coefficients sont connus d'avance.

    Les deux flux aléatoires viennent de ``child_generators``, donc indépendants
    par construction : le premier tire les facteurs, le second le bruit.
    """
    gen_factors, gen_noise = child_generators(SEED, 2)
    idx = _index(n)
    factors = pd.DataFrame(
        {
            "mkt": gen_factors.normal(0.006, 0.045, n),
            "smb": gen_factors.normal(0.002, 0.030, n),
            "hml": gen_factors.normal(0.001, 0.028, n),
        },
        index=idx,
    )
    noise = gen_noise.normal(0.0, sigma, n)
    y = pd.Series(
        alpha_true
        + betas_true[0] * factors["mkt"]
        + betas_true[1] * factors["smb"]
        + betas_true[2] * factors["hml"]
        + noise,
        index=idx,
        name="strategy",
    )
    return y, factors, alpha_true, betas_true


# --------------------------------------------------------------------------- #
# newey_west_lags
# --------------------------------------------------------------------------- #


def test_newey_west_lags_calcules_a_la_main() -> None:
    """Source (a) : les deux formules recalculées à la main.

    T = 100. Newey-West : 4 * (100/100)^(2/9) = 4 * 1 = 4, partie entière 4.
    Stock-Watson : 0,75 * 100^(1/3) = 0,75 * 4,641588 = 3,481191, partie entière 3.

    T = 1000. Newey-West : 4 * 10^(2/9). ln 10 = 2,302585, fois 2/9 = 0,511685,
    exponentielle 1,668101, fois 4 = 6,672403, partie entière 6.
    Stock-Watson : 0,75 * 1000^(1/3) = 0,75 * 10 = 7,5, partie entière 7.
    """
    assert newey_west_lags(100, rule="newey_west") == 4
    assert newey_west_lags(100, rule="stock_watson") == 3
    assert newey_west_lags(1000, rule="newey_west") == 6
    assert newey_west_lags(1000, rule="stock_watson") == 7


def test_newey_west_lags_defaut_est_stock_watson() -> None:
    """Source (a) : la valeur par défaut documentée est la règle de Stock-Watson."""
    assert newey_west_lags(1000) == newey_west_lags(1000, rule="stock_watson") == 7


def test_newey_west_lags_regle_inconnue() -> None:
    """Source (b) : une règle non implémentée doit s'arrêter, pas se deviner."""
    with pytest.raises(ConfigError, match="règle de retards inconnue"):
        newey_west_lags(500, rule="andrews")  # type: ignore[arg-type]


def test_newey_west_lags_echantillon_vide() -> None:
    """Source (b) : zéro observation ne donne pas de retard, elle donne une erreur."""
    with pytest.raises(InsufficientDataError):
        newey_west_lags(0)


@given(st.integers(min_value=1, max_value=500_000), st.integers(min_value=0, max_value=500_000))
def test_newey_west_lags_croit_avec_la_taille(n: int, extra: int) -> None:
    """Source (b) : les deux formules sont croissantes en T, donc leur partie entière aussi."""
    for rule in ("newey_west", "stock_watson"):
        assert newey_west_lags(n + extra, rule=rule) >= newey_west_lags(n, rule=rule)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# beta
# --------------------------------------------------------------------------- #


def test_beta_calcul_a_la_main_sur_cinq_couples() -> None:
    """Source (a) : bêta = 0,00244 / 0,00148 = 61/37, calcul déroulé en tête de fichier."""
    idx = _index(5)
    market = pd.Series(HAND_MARKET, index=idx, name="mkt")
    asset = pd.Series(HAND_ASSET, index=idx, name="asset")
    assert beta(asset, market) == pytest.approx(HAND_BETA, rel=1e-12)


def test_beta_insensible_au_ddof() -> None:
    """Source (b) : le ddof divise numérateur et dénominateur, il s'annule dans le rapport."""
    idx = _index(5)
    market = pd.Series(HAND_MARKET, index=idx, name="mkt")
    asset = pd.Series(HAND_ASSET, index=idx, name="asset")
    assert beta(asset, market, ddof=0) == pytest.approx(beta(asset, market, ddof=1), rel=1e-14)


def test_beta_egale_la_pente_de_statsmodels() -> None:
    """Source (d) : ``statsmodels.OLS`` sur le même intrant rend la même pente."""
    y, factors, _, _ = _simulated_panel(n=400)
    market = factors["mkt"]
    design = sm.add_constant(market.to_frame())
    attendu = float(sm.OLS(y, design).fit().params["mkt"])
    assert beta(y, market) == pytest.approx(attendu, rel=1e-12)


def test_beta_marche_constant_leve_une_erreur() -> None:
    """Source (b) : une variance de marché nulle rend le rapport indéfini."""
    idx = _index(10)
    market = pd.Series(np.full(10, 0.01), index=idx, name="mkt")
    asset = pd.Series(np.linspace(-0.02, 0.02, 10), index=idx, name="asset")
    with pytest.raises(DataQualityError, match="constante"):
        beta(asset, market)


def test_beta_serie_vide_et_point_unique() -> None:
    """Source (b) : un bêta demande au moins deux points communs."""
    vide = pd.Series(dtype=float, index=pd.DatetimeIndex([]), name="asset")
    with pytest.raises(InsufficientDataError):
        beta(vide, vide.rename("mkt"))

    un = pd.Series([0.01], index=_index(1), name="asset")
    with pytest.raises(InsufficientDataError):
        beta(un, un.rename("mkt"))


def test_beta_supporte_un_rendement_de_moins_cent_pour_cent() -> None:
    """Source (a) : avec r = -1 la formule reste définie, elle ne divise pas par (1 + r).

    Marché (0,10 ; -0,05 ; 0,02 ; -0,20), actif (0,20 ; -0,10 ; 0,05 ; -1,00).
    Moyenne marché = -0,0325, moyenne actif = -0,2125.
    Écarts marché : 0,1325 ; -0,0175 ; 0,0525 ; -0,1675.
    Écarts actif  : 0,4125 ; 0,1125 ; 0,2625 ; -0,7875.
    Produits : 0,05465625 ; -0,00196875 ; 0,01378125 ; 0,13190625, somme 0,198375.
    Carrés du marché : 0,01755625 ; 0,00030625 ; 0,00275625 ; 0,02805625, somme 0,048675.
    Bêta = 0,198375 / 0,048675 = 4,0755008...
    """
    idx = _index(4)
    market = pd.Series([0.10, -0.05, 0.02, -0.20], index=idx, name="mkt")
    asset = pd.Series([0.20, -0.10, 0.05, -1.00], index=idx, name="asset")
    assert beta(asset, market) == pytest.approx(0.198375 / 0.048675, rel=1e-12)


@given(
    st.lists(
        st.floats(min_value=-0.5, max_value=0.5, allow_nan=False, allow_infinity=False),
        min_size=6,
        max_size=40,
    ),
    st.data(),
    st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_beta_invariance_d_echelle(marche: list[float], data: st.DataObject, facteur: float) -> None:
    """Source (b) : bêta(c·r, m) = c·bêta(r, m) et bêta(r, c·m) = bêta(r, m)/c."""
    n = len(marche)
    actif = data.draw(
        st.lists(
            st.floats(min_value=-0.5, max_value=0.5, allow_nan=False, allow_infinity=False),
            min_size=n,
            max_size=n,
        )
    )
    m = np.asarray(marche, dtype=float)
    assume(float(np.var(m)) > 1e-6)
    idx = _index(n)
    market = pd.Series(m, index=idx, name="mkt")
    asset = pd.Series(np.asarray(actif, dtype=float), index=idx, name="asset")

    base = beta(asset, market)
    assert beta(asset * facteur, market) == pytest.approx(facteur * base, rel=1e-8, abs=1e-12)
    assert beta(asset, market * facteur) == pytest.approx(base / facteur, rel=1e-8, abs=1e-12)


# --------------------------------------------------------------------------- #
# factor_regression
# --------------------------------------------------------------------------- #


def test_factor_regression_retrouve_les_coefficients_simules() -> None:
    """Source (a) : les coefficients sont ceux du processus générateur, écrits en clair.

    Tolérance déclarée en erreurs types, pas en valeur absolue : un écart de plus
    de trois erreurs types sur un coefficient vrai arrive avec une probabilité
    d'environ 0,3 % par coefficient sous normalité.
    """
    y, factors, alpha_true, betas_true = _simulated_panel(n=3000)
    res = factor_regression(y, factors, frequency=Frequency.MONTHLY, annualize_alpha=False)

    assert res.n_obs == 3000
    assert abs(res.alpha - alpha_true) < 3.0 * res.alpha_stderr
    for nom, vrai in zip(["mkt", "smb", "hml"], betas_true, strict=True):
        ecart = abs(float(res.betas[nom]) - vrai)
        assert ecart < 3.0 * float(res.beta_stderr[nom]), f"{nom} : {ecart} hors de trois erreurs types"


def test_factor_regression_egale_statsmodels_hac() -> None:
    """Source (d) : mêmes chiffres que ``statsmodels.OLS(...).fit(cov_type="HAC")``.

    Le module ne doit rien ajouter au calcul, il doit seulement l'emballer.
    """
    y, factors, _, _ = _simulated_panel(n=600)
    res = factor_regression(
        y, factors, cov_type="HAC", maxlags=6, annualize_alpha=False, frequency=Frequency.MONTHLY
    )

    design = sm.add_constant(factors)
    reference = sm.OLS(y, design).fit(cov_type="HAC", cov_kwds={"maxlags": 6, "use_correction": False})

    assert res.alpha == pytest.approx(float(reference.params["const"]), rel=1e-12, abs=1e-15)
    assert res.alpha_stderr == pytest.approx(float(reference.bse["const"]), rel=1e-12)
    assert res.alpha_tstat == pytest.approx(float(reference.tvalues["const"]), rel=1e-12)
    assert res.r_squared == pytest.approx(float(reference.rsquared), rel=1e-12)
    assert res.adj_r_squared == pytest.approx(float(reference.rsquared_adj), rel=1e-12)
    for nom in ("mkt", "smb", "hml"):
        assert float(res.betas[nom]) == pytest.approx(float(reference.params[nom]), rel=1e-12)
        assert float(res.beta_stderr[nom]) == pytest.approx(float(reference.bse[nom]), rel=1e-12)
        assert float(res.beta_tstats[nom]) == pytest.approx(float(reference.tvalues[nom]), rel=1e-12)


def test_factor_regression_retards_par_defaut_suivent_la_regle() -> None:
    """Source (a) : 600 observations, 0,75 * 600^(1/3) = 0,75 * 8,4343 = 6,3257, donc 6."""
    y, factors, _, _ = _simulated_panel(n=600)
    res = factor_regression(y, factors)
    assert res.maxlags == 6
    assert res.cov_type == "HAC"


def test_factor_regression_hac_change_le_t_mais_pas_les_coefficients() -> None:
    """Source (b) : HAC ne touche qu'à la variance estimée, jamais aux coefficients.

    C'est la propriété que la documentation annonce, et elle se vérifie en
    comparant deux ajustements qui ne diffèrent que par le type de covariance.
    """
    y, factors, _, _ = _simulated_panel(n=600)
    ordinaire = factor_regression(y, factors, cov_type="nonrobust")
    robuste = factor_regression(y, factors, cov_type="HAC", maxlags=6)

    assert ordinaire.alpha == pytest.approx(robuste.alpha, rel=1e-14)
    for nom in ("mkt", "smb", "hml"):
        assert float(ordinaire.betas[nom]) == pytest.approx(float(robuste.betas[nom]), rel=1e-14)
    assert ordinaire.maxlags is None
    assert robuste.maxlags == 6


def test_annualisation_multiplie_l_alpha_sans_toucher_au_t() -> None:
    """Source (b) : alpha et son erreur type sont multipliés par le même 12, le rapport ne bouge pas."""
    y, factors, _, _ = _simulated_panel(n=600)
    par_mois = factor_regression(y, factors, maxlags=6, annualize_alpha=False)
    par_an = factor_regression(y, factors, maxlags=6, annualize_alpha=True, frequency=Frequency.MONTHLY)

    assert par_an.alpha == pytest.approx(12.0 * par_mois.alpha, rel=1e-12)
    assert par_an.alpha_stderr == pytest.approx(12.0 * par_mois.alpha_stderr, rel=1e-12)
    assert par_an.alpha_tstat == pytest.approx(par_mois.alpha_tstat, rel=1e-12)
    assert par_an.annualization_factor == 12.0
    assert par_mois.annualization_factor == 1.0


def test_facteur_colineaire_leve_une_erreur_claire() -> None:
    """Source (b) : une colonne somme de deux autres rend la matrice de plan singulière.

    ``statsmodels`` ne lèverait rien et répartirait le chargement au hasard de la
    pseudo-inverse. Le module doit refuser, et nommer la colonne.
    """
    y, factors, _, _ = _simulated_panel(n=300)
    piege = factors.copy()
    piege["combo"] = piege["mkt"] + piege["smb"]

    with pytest.raises(DataQualityError, match="colinéaires"):
        factor_regression(y, piege)


def test_facteur_duplique_leve_une_erreur() -> None:
    """Source (b) : deux colonnes identiques sont le cas de colinéarité le plus simple."""
    y, factors, _, _ = _simulated_panel(n=300)
    piege = factors.copy()
    piege["copie"] = piege["hml"]
    with pytest.raises(DataQualityError, match="colinéaires"):
        factor_regression(y, piege)


def test_facteur_constant_avec_intercepte_leve_une_erreur() -> None:
    """Source (b) : une colonne constante reproduit la constante, le rang tombe."""
    y, factors, _, _ = _simulated_panel(n=300)
    piege = factors.copy()
    piege["cash"] = 0.001
    with pytest.raises(DataQualityError, match="colinéaires"):
        factor_regression(y, piege)


def test_taux_sans_risque_soustrait_du_rendement() -> None:
    """Source (b) : régresser r - rf revient à régresser la différence formée à la main."""
    y, factors, _, _ = _simulated_panel(n=400)
    rf = pd.Series(np.full(len(y), 0.002), index=y.index, name="rf")

    avec = factor_regression(y, factors, rf, maxlags=6, annualize_alpha=False)
    a_la_main = factor_regression(y - rf, factors, maxlags=6, annualize_alpha=False)

    assert avec.alpha == pytest.approx(a_la_main.alpha, rel=1e-12)
    assert avec.mean_excess_return == pytest.approx(float((y - rf).mean()), rel=1e-12)


def test_taux_sans_risque_scalaire_decale_l_alpha() -> None:
    """Source (a) : retirer 0,002 par mois abaisse la constante de 0,002 exactement.

    Les facteurs ne bougent pas, donc les bêtas ne bougent pas, et la constante
    absorbe toute la translation.
    """
    y, factors, _, _ = _simulated_panel(n=400)
    sans = factor_regression(y, factors, maxlags=6, annualize_alpha=False)
    avec = factor_regression(y, factors, 0.002, maxlags=6, annualize_alpha=False)
    assert avec.alpha == pytest.approx(sans.alpha - 0.002, rel=1e-10, abs=1e-15)


def test_nan_retires_et_resultat_egal_au_calcul_sur_donnees_propres() -> None:
    """Source (b) : les lignes incomplètes sont retirées, le reste est identique."""
    y, factors, _, _ = _simulated_panel(n=400)
    sale = y.copy()
    sale.iloc[[5, 50, 123]] = np.nan
    facteurs_sales = factors.copy()
    facteurs_sales.iloc[7, 1] = np.nan

    res = factor_regression(sale, facteurs_sales, maxlags=6, annualize_alpha=False)
    propre = pd.concat([sale.rename("y"), facteurs_sales], axis=1).dropna()
    attendu = factor_regression(propre["y"], propre[["mkt", "smb", "hml"]], maxlags=6, annualize_alpha=False)

    assert res.n_obs == 400 - 4
    assert res.alpha == pytest.approx(attendu.alpha, rel=1e-12)


def test_index_disjoints_leve_une_erreur() -> None:
    """Source (b) : sans date commune, il n'y a pas de régression à faire."""
    y, factors, _, _ = _simulated_panel(n=50)
    decale = factors.copy()
    decale.index = pd.date_range("2100-01-31", periods=50, freq="ME")
    with pytest.raises(InsufficientDataError, match="aucune date commune"):
        factor_regression(y, decale)


def test_trop_peu_d_observations() -> None:
    """Source (b) : quatre paramètres demandent au moins cinq observations."""
    y, factors, _, _ = _simulated_panel(n=4)
    with pytest.raises(InsufficientDataError, match="paramètres"):
        factor_regression(y, factors)


def test_index_duplique_refuse() -> None:
    """Source (b) : un index dupliqué rendrait l'appariement ambigu."""
    y, factors, _, _ = _simulated_panel(n=20)
    double = pd.concat([y, y.iloc[[0]]])
    with pytest.raises(DataQualityError, match="index dupliqué"):
        factor_regression(double, factors)


def test_type_de_covariance_inconnu() -> None:
    """Source (b) : un type non reconnu s'arrête au lieu de tomber sur un défaut silencieux."""
    y, factors, _, _ = _simulated_panel(n=100)
    with pytest.raises(ConfigError, match="type de covariance inconnu"):
        factor_regression(y, factors, cov_type="sandwich")  # type: ignore[arg-type]


def test_retards_negatifs_refuses() -> None:
    """Source (b) : un nombre de retards négatif n'a pas de sens."""
    y, factors, _, _ = _simulated_panel(n=100)
    with pytest.raises(ConfigError, match="négatif"):
        factor_regression(y, factors, maxlags=-1)


def test_facteur_nomme_comme_la_constante_refuse() -> None:
    """Source (b) : deux colonnes du même nom rendraient le tableau illisible."""
    y, factors, _, _ = _simulated_panel(n=100)
    piege = factors.rename(columns={"mkt": INTERCEPT_NAME})
    with pytest.raises(ConfigError, match="nom réservé"):
        factor_regression(y, piege)


def test_facteur_unique_en_series_accepte() -> None:
    """Source (d) : une Series unique donne la même pente que ``statsmodels``."""
    y, factors, _, _ = _simulated_panel(n=300)
    res = factor_regression(y, factors["mkt"], maxlags=5, annualize_alpha=False)
    design = sm.add_constant(factors[["mkt"]])
    reference = sm.OLS(y, design).fit(cov_type="HAC", cov_kwds={"maxlags": 5, "use_correction": False})
    assert float(res.betas["mkt"]) == pytest.approx(float(reference.params["mkt"]), rel=1e-12)
    assert res.factor_names == ["mkt"]


# --------------------------------------------------------------------------- #
# attribution_table
# --------------------------------------------------------------------------- #


def test_attribution_table_verifie_l_identite_des_moindres_carres() -> None:
    """Source (b) : moyenne du rendement = alpha + somme des bêtas fois moyennes des facteurs.

    C'est une identité exacte des moindres carrés avec constante, donc vérifiable
    à la précision machine et non à une tolérance choisie.
    """
    y, factors, _, _ = _simulated_panel(n=800)
    res = factor_regression(y, factors, maxlags=6, annualize_alpha=True, frequency=Frequency.MONTHLY)
    table = attribution_table(res)

    total = float(table.loc["total", "contribution"])
    assert total == pytest.approx(12.0 * res.mean_excess_return, rel=1e-12)

    lignes = table.drop(index="total")
    assert float(lignes["contribution"].sum()) == pytest.approx(total, rel=1e-12)
    assert list(lignes.index) == [INTERCEPT_NAME, "mkt", "smb", "hml"]


def test_attribution_table_par_periode() -> None:
    """Source (b) : sans annualisation, la même identité tient à l'échelle mensuelle."""
    y, factors, _, _ = _simulated_panel(n=800)
    res = factor_regression(y, factors, maxlags=6, annualize_alpha=False)
    table = attribution_table(res, with_total=False)
    assert float(table["contribution"].sum()) == pytest.approx(res.mean_excess_return, rel=1e-12)
    assert "total" not in table.index


# --------------------------------------------------------------------------- #
# residualize
# --------------------------------------------------------------------------- #


def test_residualize_orthogonal_aux_facteurs() -> None:
    """Source (b) : la projection des moindres carrés impose X'e = 0 et une moyenne nulle."""
    y, factors, _, _ = _simulated_panel(n=500)
    residus = residualize(y, factors)

    assert len(residus) == 500
    assert float(residus.mean()) == pytest.approx(0.0, abs=1e-15)
    produits = factors.to_numpy(dtype=float).T @ residus.to_numpy(dtype=float)
    echelle = float(np.abs(y.to_numpy(dtype=float)).sum())
    assert np.max(np.abs(produits)) < 1e-12 * echelle


def test_residualize_annule_le_beta_de_marche() -> None:
    """Source (b) : un résidu orthogonal au marché a un bêta de marché nul."""
    y, factors, _, _ = _simulated_panel(n=500)
    residus = residualize(y, factors["mkt"])
    assert beta(residus, factors["mkt"]) == pytest.approx(0.0, abs=1e-12)


def test_residualize_refuse_les_facteurs_colineaires() -> None:
    """Source (b) : même garde-fou que la régression, la projection est la même algèbre."""
    y, factors, _, _ = _simulated_panel(n=300)
    piege = factors.copy()
    piege["combo"] = piege["mkt"] - 2.0 * piege["hml"]
    with pytest.raises(DataQualityError, match="colinéaires"):
        residualize(y, piege)


# --------------------------------------------------------------------------- #
# rolling_beta et rolling_alpha
# --------------------------------------------------------------------------- #


def test_rolling_beta_sur_fenetre_pleine_egale_beta() -> None:
    """Source (b) : une fenêtre de la longueur de l'échantillon est le bêta plein."""
    y, factors, _, _ = _simulated_panel(n=200)
    serie = rolling_beta(y, factors["mkt"], window=200)
    assert float(serie.iloc[-1]) == pytest.approx(beta(y, factors["mkt"]), rel=1e-12)
    assert int(serie.notna().sum()) == 1


def test_rolling_beta_egale_statsmodels_sur_chaque_tranche() -> None:
    """Source (d) : la pente ``statsmodels`` de la tranche, sur trois dates tirées."""
    y, factors, _, _ = _simulated_panel(n=300)
    fenetre = 60
    serie = rolling_beta(y, factors["mkt"], window=fenetre)
    for fin in (59, 150, 299):
        tranche_y = y.iloc[fin - fenetre + 1 : fin + 1]
        tranche_m = factors["mkt"].iloc[fin - fenetre + 1 : fin + 1]
        attendu = float(sm.OLS(tranche_y, sm.add_constant(tranche_m.to_frame())).fit().params["mkt"])
        assert float(serie.iloc[fin]) == pytest.approx(attendu, rel=1e-10)


def test_rolling_beta_fenetre_trop_courte_ou_trop_longue() -> None:
    """Source (b) : une fenêtre d'un point ne définit pas de pente."""
    y, factors, _, _ = _simulated_panel(n=50)
    with pytest.raises(ConfigError, match="fenêtre"):
        rolling_beta(y, factors["mkt"], window=1)
    with pytest.raises(InsufficientDataError):
        rolling_beta(y, factors["mkt"], window=100)


def test_rolling_alpha_egale_la_constante_de_statsmodels() -> None:
    """Source (d) : la constante ``statsmodels`` de la tranche, annualisée à la main."""
    y, factors, _, _ = _simulated_panel(n=300)
    fenetre = 60
    serie = rolling_alpha(y, factors["mkt"], window=fenetre, frequency=Frequency.MONTHLY)
    for fin in (59, 200, 299):
        tranche_y = y.iloc[fin - fenetre + 1 : fin + 1]
        tranche_m = factors["mkt"].iloc[fin - fenetre + 1 : fin + 1]
        ajuste = sm.OLS(tranche_y, sm.add_constant(tranche_m.to_frame())).fit()
        attendu = 12.0 * float(ajuste.params["const"])
        assert float(serie.iloc[fin]) == pytest.approx(attendu, rel=1e-10)


def test_rolling_alpha_sans_annualisation() -> None:
    """Source (b) : l'annualisation est une multiplication par 12, rien d'autre."""
    y, factors, _, _ = _simulated_panel(n=200)
    par_an = rolling_alpha(y, factors["mkt"], window=60, annualize=True, frequency=Frequency.MONTHLY)
    par_mois = rolling_alpha(y, factors["mkt"], window=60, annualize=False)
    ecart = (par_an - 12.0 * par_mois).abs().max()
    assert float(ecart) < 1e-15


# --------------------------------------------------------------------------- #
# shrunk_beta
# --------------------------------------------------------------------------- #


def test_shrunk_beta_calcul_a_la_main() -> None:
    """Source (a) : (61/37 + 1) / 2 = (98/37) / 2 = 49/37 = 1,3243243..."""
    idx = _index(5)
    market = pd.Series(HAND_MARKET, index=idx, name="mkt")
    asset = pd.Series(HAND_ASSET, index=idx, name="asset")
    assert shrunk_beta(asset, market, prior=1.0, weight=0.5) == pytest.approx(49.0 / 37.0, rel=1e-12)


def test_shrunk_beta_bornes_du_poids() -> None:
    """Source (b) : poids 1 rend l'estimation brute, poids 0 rend la cible."""
    idx = _index(5)
    market = pd.Series(HAND_MARKET, index=idx, name="mkt")
    asset = pd.Series(HAND_ASSET, index=idx, name="asset")
    assert shrunk_beta(asset, market, weight=1.0) == pytest.approx(HAND_BETA, rel=1e-12)
    assert shrunk_beta(asset, market, prior=0.8, weight=0.0) == pytest.approx(0.8, rel=1e-14)


def test_shrunk_beta_poids_par_defaut_est_celui_de_blume() -> None:
    """Source (a) : deux tiers de 61/37 plus un tiers de 1 vaut 0,666667·1,648649 + 0,333333."""
    idx = _index(5)
    market = pd.Series(HAND_MARKET, index=idx, name="mkt")
    asset = pd.Series(HAND_ASSET, index=idx, name="asset")
    attendu = (2.0 / 3.0) * (61.0 / 37.0) + (1.0 / 3.0) * 1.0
    assert shrunk_beta(asset, market) == pytest.approx(attendu, rel=1e-12)
    assert pytest.approx(2.0 / 3.0, rel=1e-15) == DEFAULT_BLUME_WEIGHT


def test_shrunk_beta_vasicek_utilise_l_erreur_type_de_statsmodels() -> None:
    """Source (d) : l'erreur type vient de ``statsmodels``, le poids de la formule de Vasicek.

    w = sigma0² / (sigma0² + s²), avec sigma0² fixé à 0,09 et s l'erreur type de
    la pente rendue par une régression ordinaire indépendante.
    """
    y, factors, _, _ = _simulated_panel(n=400)
    market = factors["mkt"]
    ajuste = sm.OLS(y, sm.add_constant(market.to_frame())).fit()
    pente = float(ajuste.params["mkt"])
    erreur_type = float(ajuste.bse["mkt"])

    sigma0_carre = 0.09
    poids = sigma0_carre / (sigma0_carre + erreur_type**2)
    attendu = poids * pente + (1.0 - poids) * 1.0

    assert shrunk_beta(y, market, prior_variance=sigma0_carre) == pytest.approx(attendu, rel=1e-10)


def test_shrunk_beta_rétrécit_davantage_quand_l_estimation_est_imprécise() -> None:
    """Source (b) : le poids de Vasicek décroît quand la variance a priori tombe.

    Avec une loi a priori très serrée, la cible l'emporte ; avec une loi très
    large, l'estimation l'emporte. La monotonie est celle de w en sigma0².
    """
    y, factors, _, _ = _simulated_panel(n=400)
    market = factors["mkt"]
    brut = beta(y, market)
    serre = shrunk_beta(y, market, prior_variance=1e-8)
    large = shrunk_beta(y, market, prior_variance=1e4)
    assert abs(serre - 1.0) < abs(large - 1.0)
    assert large == pytest.approx(brut, rel=1e-3)


def test_shrunk_beta_poids_hors_bornes_refuse() -> None:
    """Source (b) : un poids hors de [0, 1] extrapole au lieu de rétrécir."""
    idx = _index(5)
    market = pd.Series(HAND_MARKET, index=idx, name="mkt")
    asset = pd.Series(HAND_ASSET, index=idx, name="asset")
    with pytest.raises(ConfigError, match=r"\[0, 1\]"):
        shrunk_beta(asset, market, weight=1.5)
    with pytest.raises(ConfigError, match="variance a priori"):
        shrunk_beta(asset, market, prior_variance=-1.0)


@given(
    st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    st.floats(min_value=-3.0, max_value=3.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=50, deadline=None)
def test_shrunk_beta_reste_entre_l_estimation_et_la_cible(poids: float, cible: float) -> None:
    """Source (b) : une combinaison convexe reste dans l'intervalle de ses deux termes."""
    idx = _index(5)
    market = pd.Series(HAND_MARKET, index=idx, name="mkt")
    asset = pd.Series(HAND_ASSET, index=idx, name="asset")
    valeur = shrunk_beta(asset, market, prior=cible, weight=poids)
    bas, haut = sorted([HAND_BETA, cible])
    assert bas - 1e-12 <= valeur <= haut + 1e-12


# --------------------------------------------------------------------------- #
# Contrôles ajoutés par la vérification adversariale du 2026-09-01
# --------------------------------------------------------------------------- #


def _hac_stderr_a_la_main(design: np.ndarray, y: np.ndarray, lags: int) -> np.ndarray:
    """Rend les erreurs types HAC, recodées depuis la formule de Newey et West (1987).

    Aucune ligne de ``statsmodels`` n'intervient ici. La matrice centrale est la
    somme des autocovariances des scores, pondérées par le noyau de Bartlett
    w(l) = 1 - l / (L + 1), et la matrice sandwich est (X'X)^-1 S (X'X)^-1.
    Sans correction de petit échantillon, ce qui est la formule de 1987.
    """
    xtx_inv = np.linalg.inv(design.T @ design)
    coefficients = xtx_inv @ (design.T @ y)
    resid = y - design @ coefficients
    scores = design * resid[:, None]
    central = scores.T @ scores
    for lag in range(1, lags + 1):
        weight = 1.0 - lag / (lags + 1.0)
        gamma = scores[lag:].T @ scores[:-lag]
        central = central + weight * (gamma + gamma.T)
    return np.sqrt(np.diag(xtx_inv @ central @ xtx_inv))


def test_hac_egale_le_calcul_de_newey_west_recode_a_la_main() -> None:
    """Source (d) : une implémentation indépendante de la formule de Newey-West.

    Le test précédent comparait le module à ``statsmodels``, c'est-à-dire à la
    bibliothèque qu'il appelle lui-même. Cela contrôle le câblage des arguments,
    pas la formule. Ici la matrice sandwich est recalculée à part, depuis la
    définition, et les quatre erreurs types doivent coïncider.
    """
    y, factors, _, _ = _simulated_panel(n=600)
    res = factor_regression(y, factors, cov_type="HAC", maxlags=6, annualize_alpha=False)

    design = np.column_stack([np.ones(len(y)), factors.to_numpy(dtype=float)])
    attendu = _hac_stderr_a_la_main(design, y.to_numpy(dtype=float), 6)

    obtenu = np.array([res.alpha_stderr] + [float(res.beta_stderr[c]) for c in factors.columns])
    assert obtenu == pytest.approx(attendu, rel=1e-10)


def test_hac_correction_de_petit_echantillon_vaut_racine_de_n_sur_n_moins_k() -> None:
    """Source (b) : la correction de petit échantillon multiplie la variance par n / (n - k).

    Sur l'erreur type, cela fait racine de n / (n - k). Avec 300 observations et
    quatre paramètres, le rapport attendu vaut racine de 300/296 = 1,0067341...
    Le calcul est écrit ici, il ne vient pas de la sortie du module.
    """
    y, factors, _, _ = _simulated_panel(n=300)
    sans = factor_regression(y, factors, maxlags=4, hac_use_correction=False, annualize_alpha=False)
    avec = factor_regression(y, factors, maxlags=4, hac_use_correction=True, annualize_alpha=False)

    attendu = float(np.sqrt(300.0 / (300.0 - 4.0)))
    assert avec.alpha_stderr / sans.alpha_stderr == pytest.approx(attendu, rel=1e-12)
    for nom in ("mkt", "smb", "hml"):
        rapport = float(avec.beta_stderr[nom]) / float(sans.beta_stderr[nom])
        assert rapport == pytest.approx(attendu, rel=1e-12)


@pytest.mark.parametrize("nom_piege", ["__y__", "__rf__"])
def test_facteur_nomme_comme_une_colonne_interne_ne_corrompt_pas_la_regression(nom_piege: str) -> None:
    """Source (d) : ``statsmodels`` sur le même intrant, facteur au nom piégé compris.

    L'alignement interne assemblait autrefois les colonnes par nom. Un facteur
    appelé ``__y__`` écrasait alors le rendement régressé, et la régression
    rendait un bêta de 1 sur ce facteur et de 0 sur les autres, sans message.
    """
    y, factors, _, _ = _simulated_panel(n=200)
    piege = factors.rename(columns={"smb": nom_piege})
    rf = pd.Series(np.linspace(0.001, 0.003, len(y)), index=y.index, name="rf")

    res = factor_regression(y, piege, rf, cov_type="nonrobust", annualize_alpha=False)
    reference = sm.OLS(y - rf, sm.add_constant(piege)).fit()

    assert res.alpha == pytest.approx(float(reference.params["const"]), rel=1e-12)
    for nom in piege.columns:
        assert float(res.betas[nom]) == pytest.approx(float(reference.params[nom]), rel=1e-12)


def test_attribution_table_refuse_un_facteur_nomme_total() -> None:
    """Source (b) : deux lignes du même nom rendraient ``table.loc["total"]`` ambigu.

    Sans ce refus, le tableau portait bien deux lignes « total », et la lecture
    de la contribution totale rendait une série de deux valeurs au lieu d'un
    nombre.
    """
    y, factors, _, _ = _simulated_panel(n=200)
    piege = factors.rename(columns={"hml": "total"})
    res = factor_regression(y, piege, maxlags=4)

    with pytest.raises(ConfigError, match="nom réservé de la ligne de somme"):
        attribution_table(res)

    sans_total = attribution_table(res, with_total=False)
    assert list(sans_total.index) == [INTERCEPT_NAME, "mkt", "smb", "total"]
    assert not sans_total.index.has_duplicates


def test_marche_a_plusieurs_colonnes_refuse() -> None:
    """Source (b) : prendre la première colonne en silence rendrait un bêta non demandé."""
    y, factors, _, _ = _simulated_panel(n=200)
    for fonction, kwargs in (
        (beta, {}),
        (rolling_beta, {"window": 60}),
        (rolling_alpha, {"window": 60}),
        (shrunk_beta, {}),
    ):
        with pytest.raises(ConfigError, match="une seule série"):
            fonction(y, factors, **kwargs)  # type: ignore[operator]

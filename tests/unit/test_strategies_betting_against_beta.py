"""Les contrôles du module « parier contre le bêta ».

Chaque valeur attendue vient d'un calcul à la main, d'une identité
mathématique, ou d'une propriété que la construction impose. Aucune ne vient de
la sortie du code, parce qu'un test ainsi rempli verrouille le défaut au lieu
de l'attraper.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from quantlab.core.errors import (
    ConfigError,
    DataQualityError,
    InsufficientDataError,
    LookAheadError,
)
from quantlab.features.transforms import assert_causal
from quantlab.strategies.betting_against_beta import (
    DEFAULT_SHRINKAGE_WEIGHT,
    bab_portfolio,
    beta_identity_terms,
    financing_cost,
    frazzini_pedersen_beta,
    leg_weights,
    market_capitalization,
    overlapping_log_returns,
    rolling_log_volatility,
    shrink_beta,
)

#: Les fenêtres employées par les tests, courtes pour rester lisibles.
VOL_WINDOW = 20
VOL_MIN = 10
CORR_WINDOW = 60
CORR_MIN = 40


def _jours(n: int, start: str = "2000-01-03") -> pd.DatetimeIndex:
    """Rend un index de n jours ouvrés consécutifs."""
    return pd.bdate_range(start, periods=n, name="date")


def _marche(n: int, seed: int) -> pd.Series:
    """Rend un marché simulé, rendements simples quotidiens."""
    generator = np.random.default_rng(seed)
    return pd.Series(generator.normal(0.0004, 0.01, n), index=_jours(n), name="market")


def _titre_de_beta(market: pd.Series, beta: float, bruit: float, seed: int) -> pd.Series:
    """Rend un titre dont le rendement LOGARITHMIQUE vaut bêta fois celui du marché."""
    generator = np.random.default_rng(seed)
    logs = beta * np.log1p(market.to_numpy()) + generator.normal(0.0, bruit, len(market))
    return pd.Series(np.expm1(logs), index=market.index, name=f"beta{beta}")


# --------------------------------------------------------------------------- #
# Les rendements recouvrants
# --------------------------------------------------------------------------- #
def test_somme_recouvrante_calculee_a_la_main() -> None:
    """Trois rendements de 1 % donnent trois fois le logarithme de 1,01."""
    serie = pd.Series([0.01] * 5, index=_jours(5))
    obtenu = overlapping_log_returns(serie, 3)
    assert obtenu.iloc[:2].isna().all()
    assert obtenu.iloc[2] == pytest.approx(3.0 * math.log(1.01), abs=1e-15)


def test_les_deux_alignements_sont_le_meme_calcul_decale() -> None:
    """L'alignement avant est l'alignement arrière déplacé de deux séances."""
    generator = np.random.default_rng(11)
    serie = pd.Series(generator.normal(0.0, 0.01, 40), index=_jours(40))
    arriere = overlapping_log_returns(serie, 3, alignment="backward")
    avant = overlapping_log_returns(serie, 3, alignment="forward")
    pd.testing.assert_series_equal(
        arriere.iloc[2:].reset_index(drop=True),
        avant.iloc[:-2].reset_index(drop=True),
        check_names=False,
    )


def test_lalignement_avant_lit_le_futur_et_larriere_non() -> None:
    """Le contrôle de causalité refuse l'écriture de l'article et accepte la nôtre."""
    generator = np.random.default_rng(12)
    source = pd.Series(generator.normal(0.0, 0.01, 60), index=_jours(60))
    assert_causal(lambda x: overlapping_log_returns(x, 3, alignment="backward"), source)
    with pytest.raises(LookAheadError):
        assert_causal(lambda x: overlapping_log_returns(x, 3, alignment="forward"), source)


def test_la_somme_recouvrante_refuse_un_horizon_nul() -> None:
    """Un horizon inférieur à un n'a pas de sens et lève."""
    serie = pd.Series([0.01] * 5, index=_jours(5))
    with pytest.raises(ConfigError):
        overlapping_log_returns(serie, 0)
    with pytest.raises(ConfigError):
        overlapping_log_returns(serie, 3, alignment="centered")  # type: ignore[arg-type]


def test_la_somme_recouvrante_refuse_une_perte_totale() -> None:
    """Un rendement de moins cent pour cent n'a pas de logarithme."""
    serie = pd.Series([0.01, -1.0, 0.01, 0.02], index=_jours(4))
    with pytest.raises(DataQualityError):
        overlapping_log_returns(serie, 3)


def test_la_volatilite_glissante_egale_lecart_type_des_logarithmes() -> None:
    """La fonction rend bien l'écart type sans biais des rendements logarithmiques."""
    generator = np.random.default_rng(13)
    serie = pd.Series(generator.normal(0.0, 0.02, 30), index=_jours(30))
    obtenu = rolling_log_volatility(serie, 10, 10)
    attendu = float(np.std(np.log1p(serie.to_numpy()[-10:]), ddof=1))
    assert obtenu.iloc[-1] == pytest.approx(attendu, rel=1e-12)


# --------------------------------------------------------------------------- #
# Le rétrécissement
# --------------------------------------------------------------------------- #
def test_le_retrecissement_va_dans_le_bon_sens() -> None:
    """Un bêta de 2 devient 1,6, et non 1,4 comme le sens inverse le donnerait."""
    valeur = pd.Series([2.0], index=pd.DatetimeIndex(["2020-01-31"]))
    assert float(shrink_beta(valeur).iloc[0]) == pytest.approx(1.6, abs=1e-15)
    assert DEFAULT_SHRINKAGE_WEIGHT == 0.6


def test_le_retrecissement_est_affine_et_borne() -> None:
    """Le poids un rend l'identité, le poids zéro rend la cible."""
    valeur = pd.Series([0.4, 2.5], index=pd.DatetimeIndex(["2020-01-31", "2020-02-29"]))
    pd.testing.assert_series_equal(shrink_beta(valeur, weight=1.0), valeur)
    assert (shrink_beta(valeur, weight=0.0) == 1.0).all()
    with pytest.raises(ConfigError):
        shrink_beta(valeur, weight=1.2)


def test_le_retrecissement_ne_change_pas_le_classement() -> None:
    """L'article l'affirme, et la propriété se vérifie sur les rangs."""
    valeur = pd.Series([0.3, 1.9, 0.8, 1.1], index=_jours(4))
    avant = valeur.rank()
    apres = shrink_beta(valeur, weight=DEFAULT_SHRINKAGE_WEIGHT).rank()
    pd.testing.assert_series_equal(avant, apres)


# --------------------------------------------------------------------------- #
# Le bêta ex ante
# --------------------------------------------------------------------------- #
def _beta_de(assets: pd.DataFrame, market: pd.Series, weight: float = 1.0) -> pd.DataFrame:
    """Rend le bêta ex ante aux fenêtres courtes des tests."""
    return frazzini_pedersen_beta(
        assets,
        market,
        volatility_window=VOL_WINDOW,
        volatility_min_periods=VOL_MIN,
        correlation_window=CORR_WINDOW,
        correlation_min_periods=CORR_MIN,
        shrinkage_weight=weight,
    ).beta


def test_le_beta_du_marche_contre_lui_meme_vaut_un() -> None:
    """La corrélation vaut un et les volatilités s'annulent, donc le bêta vaut un."""
    market = _marche(120, seed=1)
    obtenu = _beta_de(market.to_frame("market"), market).dropna()
    assert not obtenu.empty
    assert obtenu["market"].sub(1.0).abs().max() < 1e-12


def test_un_titre_deux_fois_le_marche_a_un_beta_de_deux() -> None:
    """Sans bruit, le rapport des volatilités vaut deux et la corrélation un."""
    market = _marche(120, seed=2)
    titre = _titre_de_beta(market, 2.0, bruit=0.0, seed=3)
    obtenu = _beta_de(titre.to_frame("titre"), market).dropna()
    assert obtenu["titre"].sub(2.0).abs().max() < 1e-10


def test_le_beta_ex_ante_ne_lit_pas_le_futur() -> None:
    """Perturber la fin de l'échantillon ne change rien avant la coupure."""
    market = _marche(200, seed=4)
    titre = _titre_de_beta(market, 1.3, bruit=0.004, seed=5)
    source = pd.concat({"titre": titre, "market": market}, axis=1)

    def caracteristique(frame: pd.DataFrame) -> pd.Series:
        """Rend le bêta ex ante du seul titre."""
        return _beta_de(frame[["titre"]], frame["market"], weight=DEFAULT_SHRINKAGE_WEIGHT)["titre"]

    assert_causal(caracteristique, source, name="beta_frazzini_pedersen")


def test_lidentite_de_novy_marx_et_velikov_tient() -> None:
    """Les deux membres coïncident, l'identité étant une conséquence algébrique."""
    market = _marche(200, seed=6)
    assets = pd.concat(
        {
            "bas": _titre_de_beta(market, 0.6, bruit=0.005, seed=7),
            "haut": _titre_de_beta(market, 1.7, bruit=0.008, seed=8),
        },
        axis=1,
    )
    termes = beta_identity_terms(
        assets,
        market,
        volatility_window=VOL_WINDOW,
        volatility_min_periods=VOL_MIN,
        correlation_window=CORR_WINDOW,
        correlation_min_periods=CORR_MIN,
    )
    ecart = (termes["beta_fp"] - termes["beta_identity"]).abs().max().max()
    assert float(ecart) < 1e-10


def test_le_beta_ex_ante_refuse_une_fenetre_incoherente() -> None:
    """Un minimum plus grand que la fenêtre lève avant tout calcul."""
    market = _marche(80, seed=9)
    with pytest.raises(ConfigError):
        frazzini_pedersen_beta(
            market.to_frame("market"),
            market,
            volatility_window=10,
            volatility_min_periods=20,
            correlation_window=CORR_WINDOW,
            correlation_min_periods=CORR_MIN,
        )


# --------------------------------------------------------------------------- #
# Les poids des jambes
# --------------------------------------------------------------------------- #
def test_les_poids_de_rang_valent_ceux_du_calcul_a_la_main() -> None:
    """Cinq bêtas distincts donnent k égal à un tiers, donc 2/3 et 1/3."""
    betas = pd.Series([0.5, 0.8, 1.0, 1.3, 1.7], index=list("abcde"))
    bas, haut = leg_weights(betas)
    assert bas.loc["a"] == pytest.approx(2.0 / 3.0, abs=1e-15)
    assert bas.loc["b"] == pytest.approx(1.0 / 3.0, abs=1e-15)
    assert bas.loc["c"] == pytest.approx(0.0, abs=1e-15)
    assert haut.loc["e"] == pytest.approx(2.0 / 3.0, abs=1e-15)


@pytest.mark.parametrize("methode", ["rank", "equal", "cap"])
def test_chaque_jambe_somme_a_un(methode: str) -> None:
    """La constante de l'article impose deux sommes égales à un."""
    betas = pd.Series([0.4, 0.7, 0.9, 1.1, 1.4, 1.9], index=list("abcdef"))
    caps = pd.Series([10.0, 200.0, 5.0, 300.0, 8.0, 40.0], index=list("abcdef"))
    bas, haut = leg_weights(betas, method=methode, capitalization=caps)  # type: ignore[arg-type]
    assert float(bas.sum()) == pytest.approx(1.0, abs=1e-12)
    assert float(haut.sum()) == pytest.approx(1.0, abs=1e-12)
    assert bool((bas >= 0.0).all()) and bool((haut >= 0.0).all())


def test_les_poids_de_capitalisation_sont_proportionnels_a_la_taille() -> None:
    """Dans la jambe basse, le rapport des poids égale le rapport des tailles."""
    betas = pd.Series([0.4, 0.7, 1.4, 1.9], index=list("abcd"))
    caps = pd.Series([10.0, 30.0, 5.0, 15.0], index=list("abcd"))
    bas, _ = leg_weights(betas, method="cap", capitalization=caps)
    assert bas.loc["b"] / bas.loc["a"] == pytest.approx(3.0, abs=1e-12)
    assert bas.loc["c"] == pytest.approx(0.0, abs=1e-15)


def test_lequiponderation_donne_le_meme_poids_a_chaque_titre_de_la_jambe() -> None:
    """Quatre titres coupés en deux moitiés donnent un demi à chacun."""
    betas = pd.Series([0.4, 0.7, 1.4, 1.9], index=list("abcd"))
    bas, haut = leg_weights(betas, method="equal")
    assert bas.loc["a"] == pytest.approx(0.5, abs=1e-15)
    assert haut.loc["d"] == pytest.approx(0.5, abs=1e-15)


def test_les_poids_refusent_les_cas_degeneres() -> None:
    """Une méthode inconnue, un bêta unique et des bêtas égaux lèvent."""
    betas = pd.Series([0.4, 0.7, 1.4], index=list("abc"))
    with pytest.raises(ConfigError):
        leg_weights(betas, method="taille")  # type: ignore[arg-type]
    with pytest.raises(ConfigError):
        leg_weights(betas, method="cap")
    with pytest.raises(InsufficientDataError):
        leg_weights(pd.Series([1.0], index=["a"]))
    with pytest.raises(DataQualityError):
        leg_weights(pd.Series([1.0, 1.0, 1.0], index=list("abc")))


def test_le_retrecissement_ne_change_pas_la_composition_des_jambes() -> None:
    """Il est affine croissant, donc il laisse les rangs et les poids intacts."""
    betas = pd.Series([0.4, 0.7, 0.9, 1.1, 1.4, 1.9], index=list("abcdef"))
    brut = leg_weights(betas)
    retreci = leg_weights(shrink_beta(betas))
    pd.testing.assert_series_equal(brut[0], retreci[0])
    pd.testing.assert_series_equal(brut[1], retreci[1])


# --------------------------------------------------------------------------- #
# Le portefeuille
# --------------------------------------------------------------------------- #
def _monde(n_mois: int = 60, n_titres: int = 8, seed: int = 21) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rend un couple de bêtas et de rendements excédentaires mensuels."""
    generator = np.random.default_rng(seed)
    index = pd.date_range("2000-01-31", periods=n_mois, freq="ME", name="date")
    noms = [f"A{i:02d}" for i in range(n_titres)]
    socle = np.linspace(0.5, 1.8, n_titres)
    betas = pd.DataFrame(
        socle + generator.normal(0.0, 0.05, (n_mois, n_titres)),
        index=index,
        columns=noms,
    )
    marche = generator.normal(0.005, 0.045, n_mois)
    bruit = generator.normal(0.0, 0.03, (n_mois, n_titres))
    rendements = pd.DataFrame(betas.to_numpy() * marche[:, None] + bruit, index=index, columns=noms)
    return betas, rendements


def test_le_beta_ex_ante_du_facteur_vaut_exactement_zero() -> None:
    """C'est l'identité que la mise à l'échelle impose, et elle tient à 1e-12."""
    betas, rendements = _monde()
    result = bab_portfolio(betas, rendements, min_names=4)
    expose = (result.positions * betas.loc[result.positions.index]).sum(axis=1)
    assert float(expose.abs().max()) < 1e-12


def test_chaque_jambe_porte_un_beta_de_un_apres_mise_a_lechelle() -> None:
    """La jambe longue et la jambe courte valent un, leur différence zéro."""
    betas, rendements = _monde()
    result = bab_portfolio(betas, rendements, min_names=4)
    assert float((result.beta_low * result.leverage_low - 1.0).abs().max()) < 1e-12
    assert float((result.beta_high * result.leverage_high - 1.0).abs().max()) < 1e-12


def test_le_facteur_est_decale_dune_periode() -> None:
    """Le rendement d'un mois emploie les bêtas du mois précédent."""
    betas, rendements = _monde()
    result = bab_portfolio(betas, rendements, min_names=4)
    assert result.returns.index[0] == betas.index[1]
    assert list(result.positions.index) == list(result.returns.index.shift(-1, freq="ME"))


def test_perturber_le_dernier_mois_ne_change_que_le_dernier_rendement() -> None:
    """Aucun rendement antérieur ne bouge, ce qui prouve l'absence de fuite."""
    betas, rendements = _monde()
    reference = bab_portfolio(betas, rendements, min_names=4).returns
    modifie = rendements.copy()
    modifie.iloc[-1] = modifie.iloc[-1] + 0.5
    obtenu = bab_portfolio(betas, modifie, min_names=4).returns
    pd.testing.assert_series_equal(reference.iloc[:-1], obtenu.iloc[:-1])
    assert abs(float(reference.iloc[-1] - obtenu.iloc[-1])) > 1e-6


def test_le_facteur_refuse_un_decalage_nul() -> None:
    """Un décalage nul ferait acheter au prix qu'on cherche à prévoir."""
    betas, rendements = _monde()
    with pytest.raises(ConfigError):
        bab_portfolio(betas, rendements, execution_lag=0)
    with pytest.raises(ConfigError):
        bab_portfolio(betas, rendements, min_names=1)


def test_le_facteur_gagne_quand_la_droite_de_marche_est_plate() -> None:
    """Un monde où l'alpha décroît dans le bêta doit rendre le facteur positif.

    L'alpha suit la proposition 1 de l'article, qui l'écrit proportionnel à un
    moins le bêta. La construction doit donc capter un rendement positif, et le
    signe est la seule prédiction que ce test vérifie.
    """
    generator = np.random.default_rng(31)
    n_mois, n_titres = 240, 12
    index = pd.date_range("2000-01-31", periods=n_mois, freq="ME", name="date")
    noms = [f"A{i:02d}" for i in range(n_titres)]
    socle = np.linspace(0.5, 1.8, n_titres)
    betas = pd.DataFrame(np.tile(socle, (n_mois, 1)), index=index, columns=noms)
    marche = generator.normal(0.005, 0.04, n_mois)
    alpha = 0.004 * (1.0 - socle)
    bruit = generator.normal(0.0, 0.02, (n_mois, n_titres))
    rendements = pd.DataFrame(
        alpha[None, :] + betas.to_numpy() * marche[:, None] + bruit, index=index, columns=noms
    )
    result = bab_portfolio(betas, rendements, min_names=4)
    assert float(result.returns.mean()) > 0.0


def test_le_nombre_de_rendements_manquants_est_compte() -> None:
    """Un rendement absent vaut zéro, et le compte est publié plutôt que caché."""
    betas, rendements = _monde()
    troue = rendements.copy()
    troue.iloc[5, 0] = np.nan
    troue.iloc[6, 1] = np.nan
    result = bab_portfolio(betas, troue, min_names=4)
    assert result.n_missing_returns == 2


def test_le_facteur_refuse_des_colonnes_disjointes() -> None:
    """Sans colonne commune, aucun classement n'est possible."""
    betas, rendements = _monde()
    with pytest.raises(InsufficientDataError):
        bab_portfolio(betas, rendements.rename(columns=lambda c: f"{c}_bis"))


# --------------------------------------------------------------------------- #
# Le levier et son prix
# --------------------------------------------------------------------------- #
def test_le_cout_de_financement_se_calcule_a_la_main() -> None:
    """Cent points de base sur 0,70 dollar font 5,83 points de base par mois."""
    index = pd.DatetimeIndex(["2020-01-31", "2020-02-29"], name="date")
    bas = pd.Series([1.40, 1.40], index=index)
    haut = pd.Series([0.70, 0.70], index=index)
    obtenu = financing_cost(bas, haut, spread_bps_annual=100.0)
    assert float(obtenu.iloc[0]) == pytest.approx(0.01 * 0.70 / 12.0, rel=1e-12)
    brut = financing_cost(bas, haut, spread_bps_annual=100.0, basis="gross")
    assert float(brut.iloc[0]) == pytest.approx(0.01 * 1.40 / 12.0, rel=1e-12)


def test_le_cout_de_financement_refuse_un_ecart_negatif() -> None:
    """Un écart négatif reviendrait à être payé pour emprunter."""
    index = pd.DatetimeIndex(["2020-01-31"], name="date")
    bas = pd.Series([1.4], index=index)
    haut = pd.Series([0.7], index=index)
    with pytest.raises(ConfigError):
        financing_cost(bas, haut, spread_bps_annual=-1.0)
    with pytest.raises(ConfigError):
        financing_cost(bas, haut, spread_bps_annual=10.0, basis="total")  # type: ignore[arg-type]


def test_la_capitalisation_est_le_produit_du_nombre_par_la_taille() -> None:
    """Cent sociétés de deux millions font deux cents millions."""
    index = pd.DatetimeIndex(["2020-01-31"], name="date")
    nombre = pd.DataFrame({"D1": [100.0], "D2": [0.0]}, index=index)
    taille = pd.DataFrame({"D1": [2.0], "D2": [3.0]}, index=index)
    obtenu = market_capitalization(nombre, taille)
    assert float(obtenu.loc[index[0], "D1"]) == pytest.approx(200.0, abs=1e-12)
    assert bool(obtenu.loc[index[0], "D2"] != obtenu.loc[index[0], "D2"])

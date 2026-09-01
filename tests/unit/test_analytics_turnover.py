"""Contrôles de ``quantlab.analytics.turnover``.

Aucune valeur attendue de ce fichier ne vient de la sortie du code. Chacune
porte sa source en commentaire : (a) calcul à la main, (b) identité
mathématique, (c) valeur publiée, (d) implémentation indépendante.
"""

from __future__ import annotations

import math

import hypothesis.strategies as st
import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from scipy.spatial.distance import cityblock

from quantlab.analytics.turnover import (
    annualized_turnover,
    drifted_weights,
    holding_period,
    trade_frame,
    turnover,
    turnover_series,
)
from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.types import Frequency

ASSETS = ["A", "B"]


def _weights(*values: float, index: list[str] | None = None) -> pd.Series:
    return pd.Series(list(values), index=index or ASSETS, dtype=float)


# --------------------------------------------------------------------------
# Exemples entièrement calculés à la main
# --------------------------------------------------------------------------


def test_drifted_weights_exemple_a_la_main() -> None:
    """(a) Calcul à la main, deux actifs.

    Poids de départ 0,60 et 0,40. Rendements +10 % et -5 %.
    Valeurs après la période : 0,60 x 1,10 = 0,66 et 0,40 x 0,95 = 0,38.
    Valeur totale : 0,66 + 0,38 = 1,04.
    Poids dérivés : 0,66 / 1,04 = 66/104 = 33/52 et 0,38 / 1,04 = 19/52.
    """
    drift = drifted_weights(_weights(0.6, 0.4), _weights(0.10, -0.05))
    assert drift["A"] == pytest.approx(33 / 52, abs=1e-15)
    assert drift["B"] == pytest.approx(19 / 52, abs=1e-15)


def test_turnover_avec_et_sans_derive_exemple_a_la_main() -> None:
    """(a) Calcul à la main, le même exemple, cible moitié-moitié.

    Avec dérive : |0,50 - 33/52| = |26/52 - 33/52| = 7/52 sur A,
    et |26/52 - 19/52| = 7/52 sur B. Somme 14/52, demi-somme 7/52 = 0,134615.
    Sans dérive : |0,50 - 0,60| + |0,50 - 0,40| = 0,20, demi-somme 0,10.
    L'écart entre les deux conventions vaut 3,46 points sur un seul mois.
    """
    previous = _weights(0.6, 0.4)
    target = _weights(0.5, 0.5)
    returns = _weights(0.10, -0.05)

    avec = turnover(previous, target, drifted=True, period_returns=returns)
    sans = turnover(previous, target, drifted=False)

    assert avec == pytest.approx(7 / 52, abs=1e-15)
    assert sans == pytest.approx(0.10, abs=1e-15)


def test_convention_somme_entiere_vaut_le_double() -> None:
    """(a) Même exemple : la somme entière vaut 14/52, soit deux fois 7/52."""
    previous = _weights(0.6, 0.4)
    target = _weights(0.5, 0.5)
    returns = _weights(0.10, -0.05)

    entiere = turnover(previous, target, period_returns=returns, convention="full_sum")
    assert entiere == pytest.approx(14 / 52, abs=1e-15)


def test_base_nav_et_base_invested_different_quand_du_cash_est_detenu() -> None:
    """(a) Calcul à la main, portefeuille investi à 80 % avec 20 % d'encaisse.

    Poids 0,60 sur A et 0,20 sur B, le reste en encaisse. A gagne 50 %.
    Valeurs : A vaut 0,90, B vaut 0,20, l'encaisse vaut 0,20.
    Valeur liquidative : 0,90 + 0,20 + 0,20 = 1,30.
    Base « nav » : 0,90 / 1,30 = 9/13 et 0,20 / 1,30 = 2/13, somme 11/13 investi.
    Base « invested » : 0,90 / 1,10 = 9/11 et 0,20 / 1,10 = 2/11, somme 1, ce qui
    prétend à tort que l'encaisse a disparu.
    """
    weights = _weights(0.6, 0.2)
    returns = _weights(0.5, 0.0)

    nav = drifted_weights(weights, returns, basis="nav")
    invested = drifted_weights(weights, returns, basis="invested")

    assert nav["A"] == pytest.approx(9 / 13, abs=1e-15)
    assert nav["B"] == pytest.approx(2 / 13, abs=1e-15)
    assert invested["A"] == pytest.approx(9 / 11, abs=1e-15)
    assert invested["B"] == pytest.approx(2 / 11, abs=1e-15)


def test_la_base_par_defaut_est_la_valeur_liquidative() -> None:
    """(a) Le défaut retenu se vérifie sur le seul cas où les deux bases diffèrent.

    Mêmes intrants que le test précédent, sans passer ``basis``. La valeur
    attendue est 0,90 / 1,30 = 9/13, celle de la base « nav ». La base
    « invested » rendrait 9/11, donc ce test échoue si le défaut change.
    """
    drift = drifted_weights(_weights(0.6, 0.2), _weights(0.5, 0.0))
    assert drift["A"] == pytest.approx(9 / 13, abs=1e-15)
    assert float(drift.sum()) == pytest.approx(11 / 13, abs=1e-15)


def test_perte_totale_dun_actif() -> None:
    """(a) Calcul à la main : A perd 100 %, B ne bouge pas.

    Poids 0,50 et 0,50. Valeurs après : 0,00 et 0,50.
    Valeur liquidative : 1 + 0,5 x (-1) = 0,50.
    Poids dérivés : 0,00 / 0,50 = 0 et 0,50 / 0,50 = 1.
    """
    drift = drifted_weights(_weights(0.5, 0.5), _weights(-1.0, 0.0))
    assert drift["A"] == pytest.approx(0.0, abs=1e-15)
    assert drift["B"] == pytest.approx(1.0, abs=1e-15)


def test_renversement_complet_dun_long_only_vaut_un() -> None:
    """(a) Borne maximale : tout vendre pour tout racheter ailleurs.

    De (1, 0) vers (0, 1) sans rendement : |0 - 1| + |1 - 0| = 2, demi-somme 1.
    C'est le maximum atteignable par un portefeuille long-only pleinement
    investi, puisque la somme des écarts absolus ne peut dépasser 2.
    """
    rotation = turnover(_weights(1.0, 0.0), _weights(0.0, 1.0), drifted=False)
    assert rotation == pytest.approx(1.0, abs=1e-15)


def test_rebalancement_identique_donne_zero() -> None:
    """(b) Identité : rééquilibrer vers les poids dérivés ne négocie rien."""
    previous = _weights(0.7, 0.3)
    returns = _weights(0.03, -0.11)
    drift = drifted_weights(previous, returns)

    assert turnover(previous, drift, period_returns=returns) == pytest.approx(0.0, abs=1e-15)
    assert turnover(previous, previous, drifted=False) == pytest.approx(0.0, abs=1e-15)


def test_frais_fantomes_dun_portefeuille_jamais_rebalance() -> None:
    """(a) Le défaut que la convention évite, calculé à la main.

    Portefeuille équipondéré jamais rééquilibré. A gagne 20 %, B ne bouge pas.
    Valeurs : 0,60 et 0,50, valeur liquidative 1,10, poids observés 6/11 et 5/11.
    Contre les poids dérivés, la rotation est exactement nulle : rien n'a été
    négocié. Contre les poids cibles précédents, elle vaut
    0,5 x (|6/11 - 1/2| + |5/11 - 1/2|) = 0,5 x (1/22 + 1/22) = 1/22 = 0,045455.
    Ce sont des frais facturés sur une transaction qui n'a jamais eu lieu.
    """
    dates = pd.to_datetime(["2020-01-31", "2020-02-29"])
    weights = pd.DataFrame(
        [[0.5, 0.5], [6 / 11, 5 / 11]],
        index=dates,
        columns=ASSETS,
        dtype=float,
    )
    returns = pd.DataFrame([[0.0, 0.0], [0.20, 0.0]], index=dates, columns=ASSETS, dtype=float)

    avec = turnover_series(weights, returns, drifted=True)
    sans = turnover_series(weights, drifted=False)

    assert avec.iloc[0] == pytest.approx(0.0, abs=1e-15)
    assert sans.iloc[0] == pytest.approx(1 / 22, abs=1e-15)


def test_turnover_series_sur_trois_dates() -> None:
    """(a) Calcul à la main, deux rééquilibrages.

    Poids : (0,60 ; 0,40) puis (0,50 ; 0,50) puis (0,50 ; 0,50).
    Rendements : néant, puis (+10 % ; -5 %), puis (0 ; 0).
    Première rotation : 7/52, celle de l'exemple travaillé plus haut.
    Seconde rotation : les rendements sont nuls, donc les poids dérivés valent
    (0,50 ; 0,50) et la cible ne bouge pas, donc zéro.
    """
    dates = pd.to_datetime(["2020-01-31", "2020-02-29", "2020-03-31"])
    weights = pd.DataFrame([[0.6, 0.4], [0.5, 0.5], [0.5, 0.5]], index=dates, columns=ASSETS, dtype=float)
    returns = pd.DataFrame([[0.0, 0.0], [0.10, -0.05], [0.0, 0.0]], index=dates, columns=ASSETS, dtype=float)

    serie = turnover_series(weights, returns)

    assert list(serie.index) == list(dates[1:])
    assert serie.iloc[0] == pytest.approx(7 / 52, abs=1e-15)
    assert serie.iloc[1] == pytest.approx(0.0, abs=1e-15)
    assert serie.name == "turnover"


def test_construction_initiale_comptee_a_part() -> None:
    """(a) Bâtir (0,60 ; 0,40) depuis l'encaisse : 0,5 x (0,60 + 0,40) = 0,50."""
    dates = pd.to_datetime(["2020-01-31", "2020-02-29"])
    weights = pd.DataFrame([[0.6, 0.4], [0.6, 0.4]], index=dates, columns=ASSETS, dtype=float)
    returns = pd.DataFrame([[0.0, 0.0], [0.0, 0.0]], index=dates, columns=ASSETS, dtype=float)

    serie = turnover_series(weights, returns, include_initial=True)

    assert len(serie) == 2
    assert serie.iloc[0] == pytest.approx(0.5, abs=1e-15)
    assert serie.iloc[1] == pytest.approx(0.0, abs=1e-15)


def test_trade_frame_signe_et_somme_nulle() -> None:
    """(a) et (b). Achats et ventes se compensent sur un portefeuille investi.

    De (0,60 ; 0,40) vers (0,50 ; 0,50) sans rendement : -0,10 sur A, +0,10 sur B.
    La somme d'une ligne vaut zéro, identité vraie pour tout rééquilibrage d'un
    portefeuille pleinement investi.
    """
    dates = pd.to_datetime(["2020-01-31", "2020-02-29"])
    weights = pd.DataFrame([[0.6, 0.4], [0.5, 0.5]], index=dates, columns=ASSETS, dtype=float)
    returns = pd.DataFrame([[0.0, 0.0], [0.0, 0.0]], index=dates, columns=ASSETS, dtype=float)

    trades = trade_frame(weights, returns)

    assert trades.loc[dates[1], "A"] == pytest.approx(-0.10, abs=1e-15)
    assert trades.loc[dates[1], "B"] == pytest.approx(+0.10, abs=1e-15)
    assert float(trades.sum(axis=1).iloc[0]) == pytest.approx(0.0, abs=1e-15)


def test_annualized_turnover_mensuel() -> None:
    """(a) Douze mois à 10 % de rotation font 1,2 par an."""
    serie = pd.Series([0.1, 0.1, 0.1], dtype=float)
    assert annualized_turnover(serie, Frequency.MONTHLY) == pytest.approx(1.2, abs=1e-15)


def test_annualized_turnover_ignore_les_manquants() -> None:
    """(a) La moyenne de 0,2 et 0,4 vaut 0,3, et 0,3 x 4 trimestres font 1,2."""
    serie = pd.Series([np.nan, 0.2, 0.4], dtype=float)
    assert annualized_turnover(serie, Frequency.QUARTERLY) == pytest.approx(1.2, abs=1e-15)


def test_holding_period() -> None:
    """(a) et (b). 1/1,2 vaut 0,8333 an, et le produit rotation x durée vaut un."""
    duree = holding_period(1.2)
    assert duree == pytest.approx(1 / 1.2, abs=1e-15)
    assert 1.2 * duree == pytest.approx(1.0, abs=1e-15)
    assert holding_period(0.0) == math.inf


# --------------------------------------------------------------------------
# Contrôle contre une implémentation indépendante
# --------------------------------------------------------------------------


def test_turnover_egale_la_moitie_de_la_distance_de_manhattan() -> None:
    """(d) ``scipy.spatial.distance.cityblock`` calcule la même somme absolue."""
    previous = _weights(0.25, 0.75)
    target = _weights(0.60, 0.40)
    attendu = 0.5 * cityblock(previous.to_numpy(), target.to_numpy())

    assert turnover(previous, target, drifted=False) == pytest.approx(attendu, abs=1e-15)


# --------------------------------------------------------------------------
# Propriétés
# --------------------------------------------------------------------------

_POIDS = st.lists(
    st.floats(min_value=-2.0, max_value=2.0, allow_nan=False, allow_infinity=False),
    min_size=1,
    max_size=6,
)
_SIMPLEXE = st.lists(
    st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    min_size=2,
    max_size=6,
).filter(lambda xs: sum(xs) > 1e-6)


@settings(deadline=None, max_examples=200)
@given(previous=_POIDS, target=_POIDS)
def test_propriete_turnover_positif(previous: list[float], target: list[float]) -> None:
    """(b) Une somme de valeurs absolues est positive ou nulle."""
    n = max(len(previous), len(target))
    noms = [f"A{i}" for i in range(n)]
    p = pd.Series(previous + [0.0] * (n - len(previous)), index=noms, dtype=float)
    t = pd.Series(target + [0.0] * (n - len(target)), index=noms, dtype=float)

    assert turnover(p, t, drifted=False) >= 0.0


@settings(deadline=None, max_examples=200)
@given(previous=_SIMPLEXE, target=_SIMPLEXE)
def test_propriete_borne_zero_un_sur_le_simplexe(previous: list[float], target: list[float]) -> None:
    """(b) Deux vecteurs positifs sommant à un distent d'au plus 2 en norme L1.

    La demi-somme est donc bornée par un, et c'est la borne atteinte par le
    renversement complet.
    """
    n = max(len(previous), len(target))
    noms = [f"A{i}" for i in range(n)]
    p = np.array(previous + [0.0] * (n - len(previous)))
    t = np.array(target + [0.0] * (n - len(target)))
    p = pd.Series(p / p.sum(), index=noms, dtype=float)
    t = pd.Series(t / t.sum(), index=noms, dtype=float)

    rotation = turnover(p, t, drifted=False)
    assert 0.0 <= rotation <= 1.0 + 1e-12


@settings(deadline=None, max_examples=100)
@given(
    poids=_SIMPLEXE,
    rendement=st.floats(min_value=-0.9, max_value=2.0, allow_nan=False, allow_infinity=False),
)
def test_propriete_rendement_uniforme_ne_deplace_pas_les_poids(poids: list[float], rendement: float) -> None:
    """(b) Identité : sur un portefeuille pleinement investi, un rendement commun à
    tous les actifs multiplie toutes les valeurs par le même nombre, donc laisse
    les poids relatifs inchangés.
    """
    noms = [f"A{i}" for i in range(len(poids))]
    brut = np.array(poids)
    w = pd.Series(brut / brut.sum(), index=noms, dtype=float)
    r = pd.Series(rendement, index=noms, dtype=float)

    drift = drifted_weights(w, r)
    np.testing.assert_allclose(drift.to_numpy(), w.to_numpy(), atol=1e-12)


@settings(deadline=None, max_examples=100)
@given(poids=_SIMPLEXE)
def test_propriete_les_poids_derives_somment_a_un(poids: list[float]) -> None:
    """(b) Un portefeuille pleinement investi le reste après la dérive."""
    noms = [f"A{i}" for i in range(len(poids))]
    brut = np.array(poids)
    w = pd.Series(brut / brut.sum(), index=noms, dtype=float)
    r = pd.Series(np.linspace(-0.5, 0.5, len(poids)), index=noms, dtype=float)

    assert float(drifted_weights(w, r).sum()) == pytest.approx(1.0, abs=1e-12)


@settings(deadline=None, max_examples=200)
@given(previous=_POIDS, target=_POIDS)
def test_propriete_invariance_par_permutation(previous: list[float], target: list[float]) -> None:
    """(b) La rotation est une somme, donc elle ne dépend pas de l'ordre des actifs.

    La tolérance est relative, et elle doit l'être. L'addition flottante n'est
    pas associative : réordonner les termes déplace le dernier bit du résultat.
    Sur six actifs de poids allant jusqu'à deux, la somme approche 12, dont
    l'unité au dernier rang vaut 1,78e-15. Une tolérance absolue de 1e-15 est
    donc sous le bruit d'arrondi, et elle échoue sur des intrants parfaitement
    licites. Contre-exemple mesuré le 2026-09-01 : la permutation rend
    5,381827413533854 là où l'ordre direct rend 5,381827413533852, deux unités
    au dernier rang d'écart. La propriété vraie est l'égalité à l'arrondi près,
    pas l'égalité bit à bit.
    """
    n = max(len(previous), len(target))
    noms = [f"A{i}" for i in range(n)]
    p = pd.Series(previous + [0.0] * (n - len(previous)), index=noms, dtype=float)
    t = pd.Series(target + [0.0] * (n - len(target)), index=noms, dtype=float)
    inverse = noms[::-1]

    direct = turnover(p, t, drifted=False)
    permute = turnover(p.reindex(inverse), t.reindex(inverse), drifted=False)
    assert direct == pytest.approx(permute, rel=1e-12, abs=1e-15)


@settings(deadline=None, max_examples=100)
@given(previous=_POIDS, target=_POIDS)
def test_propriete_somme_entiere_vaut_deux_demi_sommes(previous: list[float], target: list[float]) -> None:
    """(b) Les deux conventions diffèrent d'un facteur deux exactement."""
    n = max(len(previous), len(target))
    noms = [f"A{i}" for i in range(n)]
    p = pd.Series(previous + [0.0] * (n - len(previous)), index=noms, dtype=float)
    t = pd.Series(target + [0.0] * (n - len(target)), index=noms, dtype=float)

    demi = turnover(p, t, drifted=False, convention="half_sum")
    entiere = turnover(p, t, drifted=False, convention="full_sum")
    assert entiere == pytest.approx(2.0 * demi, abs=1e-15)


# --------------------------------------------------------------------------
# Cas limites et erreurs déclarées
# --------------------------------------------------------------------------


def test_serie_vide_leve() -> None:
    vide = pd.Series(dtype=float)
    with pytest.raises(InsufficientDataError):
        drifted_weights(vide, _weights(0.1, 0.2))
    with pytest.raises(InsufficientDataError):
        turnover(vide, vide, drifted=False)


def test_un_seul_actif_pleinement_investi_reste_a_un() -> None:
    """(b) Un portefeuille d'un seul actif investi à 100 % ne dérive pas."""
    solo = pd.Series([1.0], index=["A"], dtype=float)
    drift = drifted_weights(solo, pd.Series([0.37], index=["A"], dtype=float))
    assert drift["A"] == pytest.approx(1.0, abs=1e-15)
    assert turnover(solo, solo, period_returns=pd.Series([0.37], index=["A"], dtype=float)) == 0.0


def test_serie_constante_ne_negocie_rien() -> None:
    """(b) Poids constants et rendements identiques : aucune transaction."""
    dates = pd.to_datetime(["2020-01-31", "2020-02-29", "2020-03-31"])
    weights = pd.DataFrame(0.5, index=dates, columns=ASSETS, dtype=float)
    returns = pd.DataFrame(0.02, index=dates, columns=ASSETS, dtype=float)

    serie = turnover_series(weights, returns)
    np.testing.assert_allclose(serie.to_numpy(), np.zeros(2), atol=1e-15)


def test_valeur_manquante_leve() -> None:
    with pytest.raises(DataQualityError, match="valeurs manquantes"):
        drifted_weights(_weights(0.5, np.nan), _weights(0.1, 0.1))
    with pytest.raises(DataQualityError, match="valeurs manquantes"):
        turnover(_weights(0.5, 0.5), _weights(np.nan, 0.5), drifted=False)


def test_rendement_absent_leve() -> None:
    with pytest.raises(DataQualityError, match="rendement manquant"):
        drifted_weights(_weights(0.5, 0.5), pd.Series([0.1], index=["A"], dtype=float))


def test_index_en_double_leve() -> None:
    doublon = pd.Series([0.5, 0.5], index=["A", "A"], dtype=float)
    with pytest.raises(DataQualityError, match="double"):
        drifted_weights(doublon, _weights(0.1, 0.1))


def test_capital_detruit_leve() -> None:
    """(a) Les deux actifs perdent 100 % : la valeur liquidative tombe à zéro."""
    with pytest.raises(DataQualityError, match="dégénéré"):
        drifted_weights(_weights(0.5, 0.5), _weights(-1.0, -1.0))


def test_dollars_neutres_traitables_en_nav_et_refuses_en_invested() -> None:
    """(a) Livre à somme nulle, rendements nuls.

    Base « invested » : le dénominateur vaut 1 + (-1) = 0, donc la fonction lève.
    Base « nav » : le dénominateur vaut 1 + 0 = 1, donc les poids sont inchangés.
    """
    neutre = _weights(1.0, -1.0)
    nuls = _weights(0.0, 0.0)

    with pytest.raises(DataQualityError, match="dégénéré"):
        drifted_weights(neutre, nuls, basis="invested")

    drift = drifted_weights(neutre, nuls, basis="nav")
    np.testing.assert_allclose(drift.to_numpy(), np.array([1.0, -1.0]), atol=1e-15)


def test_convention_inconnue_leve() -> None:
    with pytest.raises(ConfigError, match="convention inconnue"):
        turnover(_weights(0.5, 0.5), _weights(0.5, 0.5), drifted=False, convention="moitie")


def test_base_inconnue_leve() -> None:
    with pytest.raises(ConfigError, match="base de dérive inconnue"):
        drifted_weights(_weights(0.5, 0.5), _weights(0.0, 0.0), basis="gross")


def test_derive_sans_rendements_leve() -> None:
    with pytest.raises(ConfigError, match="period_returns"):
        turnover(_weights(0.5, 0.5), _weights(0.4, 0.6), drifted=True)
    with pytest.raises(ConfigError, match="returns_frame"):
        trade_frame(pd.DataFrame([[0.5, 0.5], [0.4, 0.6]], columns=ASSETS, dtype=float))


def test_une_seule_date_leve() -> None:
    seule = pd.DataFrame([[0.5, 0.5]], index=pd.to_datetime(["2020-01-31"]), columns=ASSETS, dtype=float)
    with pytest.raises(InsufficientDataError, match="au moins deux"):
        turnover_series(seule, drifted=False)


def test_dates_non_triees_levent() -> None:
    dates = pd.to_datetime(["2020-02-29", "2020-01-31"])
    weights = pd.DataFrame([[0.5, 0.5], [0.4, 0.6]], index=dates, columns=ASSETS, dtype=float)
    with pytest.raises(DataQualityError, match="trié"):
        turnover_series(weights, drifted=False)


def test_rendement_absent_a_la_date_de_rebalancement_leve() -> None:
    dates = pd.to_datetime(["2020-01-31", "2020-02-29"])
    weights = pd.DataFrame([[0.5, 0.5], [0.4, 0.6]], index=dates, columns=ASSETS, dtype=float)
    returns = pd.DataFrame([[0.0, 0.0]], index=dates[:1], columns=ASSETS, dtype=float)
    with pytest.raises(DataQualityError, match="aucun rendement"):
        turnover_series(weights, returns)


def test_rotation_annuelle_negative_refusee() -> None:
    with pytest.raises(ValueError, match="négative"):
        holding_period(-0.1)


def test_annualized_turnover_sur_serie_vide_leve() -> None:
    with pytest.raises(InsufficientDataError):
        annualized_turnover(pd.Series(dtype=float), Frequency.MONTHLY)


def test_entree_et_sortie_dunivers() -> None:
    """(a) Un actif qui entre dans l'univers porte un poids de départ nul.

    De (A = 1,0) vers (B = 1,0), rendements nuls : |0 - 1| + |1 - 0| = 2,
    demi-somme 1.
    """
    previous = pd.Series([1.0], index=["A"], dtype=float)
    target = pd.Series([1.0], index=["B"], dtype=float)
    assert turnover(previous, target, drifted=False) == pytest.approx(1.0, abs=1e-15)


def test_le_defaut_de_frequence_est_mensuel() -> None:
    """(a) Le défaut de ``annualized_turnover`` se vérifie sans le passer.

    Une rotation de 10 % par période, annualisée sans nommer la fréquence, doit
    rendre 0,10 x 12 = 1,2. Le défaut quotidien rendrait 0,10 x 252 = 25,2.
    Test ajouté après un contrôle de mutation : passer le défaut de
    ``MONTHLY`` à ``DAILY`` ne faisait échouer aucun test, les deux appels
    existants nommant leur fréquence.
    """
    assert annualized_turnover(0.1) == pytest.approx(1.2, abs=1e-15)


def test_la_demi_somme_nest_pas_le_montant_dun_seul_cote_quand_lencaisse_finance() -> None:
    """(a) La limite de la demi-somme, calculée à la main.

    Portefeuille de 60 % en A, 20 % en B et 20 % d'encaisse. A gagne 50 %, donc
    la valeur liquidative vaut 1,30 et les poids dérivés 0,90/1,30 = 18/26 et
    0,20/1,30 = 4/26. La cible est moitié-moitié, soit 13/26 chacun.
    Variations : 13/26 - 18/26 = -5/26 sur A et 13/26 - 4/26 = +9/26 sur B.
    La demi-somme vaut donc 14/26 divisé par deux, soit 7/26 = 0,269231, alors
    que les achats font 9/26 = 0,346154 et les ventes 5/26 = 0,192308.
    La demi-somme n'est ni l'un ni l'autre : elle ne vaut le montant d'un seul
    côté que si le rééquilibrage s'autofinance.

    (b) Identité vérifiée en prime : la différence entre les achats et les
    ventes, 4/26 = 2/13, est exactement l'encaisse dérivée consommée.
    """
    previous = _weights(0.6, 0.2)
    target = _weights(0.5, 0.5)
    returns = _weights(0.5, 0.0)

    derives = drifted_weights(previous, returns)
    variations = target - derives
    achats = float(variations[variations > 0].sum())
    ventes = float(-variations[variations < 0].sum())
    encaisse_derivee = 1.0 - float(derives.sum())

    assert turnover(previous, target, period_returns=returns) == pytest.approx(7 / 26, abs=1e-15)
    assert achats == pytest.approx(9 / 26, abs=1e-15)
    assert ventes == pytest.approx(5 / 26, abs=1e-15)
    assert achats - ventes == pytest.approx(encaisse_derivee, abs=1e-15)


def test_un_rendement_manquant_hors_portefeuille_est_ignore() -> None:
    """(b) Contrat déclaré : les actifs en trop sont ignorés, NaN compris.

    Un tableau de rendements couvre l'univers entier, et un titre non détenu à
    cette date peut n'avoir aucune cote. Refuser la ligne entière pour ce motif
    rendrait la fonction inutilisable sur un univers large. Le rendement d'un
    actif DÉTENU reste exigé, et son absence fait toujours lever.
    """
    detenus = pd.Series([1.0], index=["A"], dtype=float)
    rendements = pd.Series([0.10, np.nan], index=["A", "C"], dtype=float)

    derive = drifted_weights(detenus, rendements)
    assert derive["A"] == pytest.approx(1.0, abs=1e-15)
    assert list(derive.index) == ["A"]

    with pytest.raises(DataQualityError, match="valeurs manquantes"):
        drifted_weights(_weights(0.5, 0.5), pd.Series([0.1, np.nan], index=ASSETS, dtype=float))


def test_cadre_de_poids_sans_aucune_date_leve() -> None:
    """(b) Contrat déclaré : aucune date négociable rend une erreur, pas un vide.

    Avant correction, ce cas rendait une série vide de type objet, donc une
    rotation nulle qui n'avait jamais été mesurée, et un type que pandas 3
    proscrit.
    """
    vide = pd.DataFrame(columns=ASSETS, index=pd.DatetimeIndex([]), dtype=float)
    with pytest.raises(InsufficientDataError):
        trade_frame(vide, drifted=False, include_initial=True)
    with pytest.raises(InsufficientDataError):
        turnover_series(vide, drifted=False, include_initial=True)


def test_poids_non_numeriques_levent_une_erreur_de_qualite() -> None:
    """(b) Contrat déclaré : ``DataQualityError``, pas un ``ValueError`` de pandas.

    Le contrat annoncé dans la section Raises doit être celui que la fonction
    tient, sans quoi l'appelant ne peut pas l'attraper.
    """
    dates = pd.to_datetime(["2020-01-31", "2020-02-29"])
    texte = pd.DataFrame([["a", "b"], ["c", "d"]], index=dates, columns=ASSETS)
    with pytest.raises(DataQualityError, match="numérique"):
        trade_frame(texte, drifted=False)


def test_la_rotation_dune_serie_est_toujours_en_flottants() -> None:
    """(b) Le type de sortie est fixé : pandas 3 proscrit l'inférence en objet."""
    dates = pd.to_datetime(["2020-01-31", "2020-02-29"])
    weights = pd.DataFrame([[0.6, 0.4], [0.5, 0.5]], index=dates, columns=ASSETS, dtype=float)
    returns = pd.DataFrame([[0.0, 0.0], [0.0, 0.0]], index=dates, columns=ASSETS, dtype=float)

    assert turnover_series(weights, returns).dtype == np.dtype("float64")
    assert set(trade_frame(weights, returns).dtypes) == {np.dtype("float64")}

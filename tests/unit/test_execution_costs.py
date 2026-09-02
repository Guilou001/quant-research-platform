"""Contrôles de ``quantlab.execution.costs``.

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

from quantlab.core.config import CostConfig
from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.protocols import CostModel
from quantlab.core.types import Frequency
from quantlab.execution.costs import (
    ADV_FRACTION_COLUMN,
    BPS_PER_UNIT,
    PERIOD_RETURN_COLUMN,
    VOLATILITY_COLUMN,
    BorrowCostModel,
    CompositeCostModel,
    CostBreakdown,
    FinancingCostModel,
    LinearCostModel,
    SqrtImpactModel,
    breakeven_cost_bps,
    from_config,
)

ASSETS = ["A", "B"]


def _weights(*values: float, index: list[str] | None = None) -> pd.Series:
    return pd.Series(list(values), index=index or ASSETS, dtype=float)


def _impact_context(
    volatilities: tuple[float, ...],
    adv_fractions: tuple[float, ...],
    index: list[str] | None = None,
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            VOLATILITY_COLUMN: list(volatilities),
            ADV_FRACTION_COLUMN: list(adv_fractions),
        },
        index=index or ASSETS,
    )


# --------------------------------------------------------------------------
# L'aller-retour à deux actifs, entièrement calculé à la main
# --------------------------------------------------------------------------

# (a) Calcul à la main, portefeuille long-short à deux actifs.
#
# Poids de départ  : A = +0,90, B = -0,30.
# Poids cibles     : A = +0,70, B = -0,50.
# Variations       : A = -0,20, B = -0,20.
# Rotation (somme entière, les deux côtés) : 0,20 + 0,20 = 0,40.
#
# 1. Coût linéaire. Commission 1,0 pb, demi-écart 2,5 pb, glissement 0,5 pb.
#    Commission : 1,0 x 0,40 = 0,40 pb
#    Demi-écart : 2,5 x 0,40 = 1,00 pb
#    Glissement : 0,5 x 0,40 = 0,20 pb
#    Sous-total : 1,60 pb
#
# 2. Impact en racine carrée. Coefficient 0,5.
#    Actif A : volatilité 0,02, volume quotidien moyen 5,0 fois le capital.
#      participation = 0,20 / 5,0 = 0,04, racine = 0,20
#      impact unitaire = 0,5 x 0,02 x 0,20 = 0,002
#      coût = 0,20 x 0,002 = 0,0004, soit 4 pb
#    Actif B : volatilité 0,03, volume quotidien moyen 20,0 fois le capital.
#      participation = 0,20 / 20,0 = 0,01, racine = 0,10
#      impact unitaire = 0,5 x 0,03 x 0,10 = 0,0015
#      coût = 0,20 x 0,0015 = 0,0003, soit 3 pb
#    Sous-total : 7 pb
#
# 3. Emprunt de titre. 300 pb par an, fréquence quotidienne, 252 séances.
#    Exposition vendeuse cible = 0,50.
#    coût = (300 / 252) x 0,50 = 150 / 252 = 25 / 42 pb, environ 0,595238 pb
#
# 4. Financement du levier. 100 pb par an au-dessus du taux sans risque.
#    Exposition brute cible = 0,70 + 0,50 = 1,20, part financée = 0,20.
#    coût = (100 / 252) x 0,20 = 20 / 252 = 5 / 63 pb, environ 0,079365 pb
#
# Total = 1,60 + 7 + 25/42 + 5/63 = 8,60 + 85/126 pb, environ 9,274603 pb.

PREVIOUS_ALLER_RETOUR = _weights(0.90, -0.30)
TARGET_ALLER_RETOUR = _weights(0.70, -0.50)
CONTEXT_ALLER_RETOUR = _impact_context((0.02, 0.03), (5.0, 20.0))

ATTENDU_LINEAIRE_BPS = 1.60
ATTENDU_IMPACT_BPS = 7.0
ATTENDU_EMPRUNT_BPS = 25 / 42
ATTENDU_FINANCEMENT_BPS = 5 / 63
ATTENDU_TOTAL_BPS = 8.60 + 85 / 126


def _modele_aller_retour() -> CompositeCostModel:
    return CompositeCostModel(
        [
            LinearCostModel(commission_bps=1.0, spread_bps=2.5, slippage_bps=0.5),
            SqrtImpactModel(coefficient=0.5),
            BorrowCostModel(annual_bps=300.0, frequency=Frequency.DAILY),
            FinancingCostModel(spread_over_rf_bps=100.0, frequency=Frequency.DAILY),
        ]
    )


def test_aller_retour_deux_actifs_chaque_composante() -> None:
    """(a) Chaque composante du calcul à la main ci-dessus, une par une."""
    detail = _modele_aller_retour().breakdown(
        previous=PREVIOUS_ALLER_RETOUR,
        target=TARGET_ALLER_RETOUR,
        context=CONTEXT_ALLER_RETOUR,
    )

    assert detail.traded_fraction == pytest.approx(0.40, abs=1e-15)
    assert detail.commission_bps == pytest.approx(0.40, abs=1e-14)
    assert detail.spread_bps == pytest.approx(1.00, abs=1e-14)
    assert detail.slippage_bps == pytest.approx(0.20, abs=1e-14)
    assert detail.impact_bps == pytest.approx(ATTENDU_IMPACT_BPS, abs=1e-13)
    assert detail.borrow_bps == pytest.approx(ATTENDU_EMPRUNT_BPS, abs=1e-14)
    assert detail.financing_bps == pytest.approx(ATTENDU_FINANCEMENT_BPS, abs=1e-14)


def test_aller_retour_total_et_fraction() -> None:
    """(a) Le total du même calcul, et sa conversion en fraction du capital."""
    detail = _modele_aller_retour().breakdown(
        previous=PREVIOUS_ALLER_RETOUR,
        target=TARGET_ALLER_RETOUR,
        context=CONTEXT_ALLER_RETOUR,
    )
    assert detail.total_bps == pytest.approx(ATTENDU_TOTAL_BPS, abs=1e-13)
    assert detail.total_fraction == pytest.approx(ATTENDU_TOTAL_BPS / 1e4, abs=1e-17)


def test_cost_rend_la_meme_chose_que_le_total_du_detail() -> None:
    """(b) Identité : ``cost`` est le total du détail divisé par dix mille."""
    modele = _modele_aller_retour()
    detail = modele.breakdown(
        previous=PREVIOUS_ALLER_RETOUR,
        target=TARGET_ALLER_RETOUR,
        context=CONTEXT_ALLER_RETOUR,
    )
    cout = modele.cost(
        previous=PREVIOUS_ALLER_RETOUR,
        target=TARGET_ALLER_RETOUR,
        context=CONTEXT_ALLER_RETOUR,
    )
    assert cout == pytest.approx(detail.total_bps / BPS_PER_UNIT, abs=0.0, rel=0.0)


def test_la_somme_des_composantes_vaut_la_somme_des_modeles_pris_seuls() -> None:
    """(b) Identité : composer puis chiffrer vaut chiffrer puis additionner."""
    seuls = [
        LinearCostModel(commission_bps=1.0, spread_bps=2.5, slippage_bps=0.5),
        SqrtImpactModel(coefficient=0.5),
        BorrowCostModel(annual_bps=300.0, frequency=Frequency.DAILY),
        FinancingCostModel(spread_over_rf_bps=100.0, frequency=Frequency.DAILY),
    ]
    total_separe = sum(
        m.breakdown(
            previous=PREVIOUS_ALLER_RETOUR,
            target=TARGET_ALLER_RETOUR,
            context=CONTEXT_ALLER_RETOUR,
        ).total_bps
        for m in seuls
    )
    compose = _modele_aller_retour().breakdown(
        previous=PREVIOUS_ALLER_RETOUR,
        target=TARGET_ALLER_RETOUR,
        context=CONTEXT_ALLER_RETOUR,
    )
    assert compose.total_bps == pytest.approx(total_separe, abs=1e-13)


# --------------------------------------------------------------------------
# La rotation, contrôlée par une implémentation indépendante
# --------------------------------------------------------------------------


def test_rotation_en_somme_entiere_egale_la_distance_de_manhattan() -> None:
    """(d) ``scipy.spatial.distance.cityblock`` calcule la même somme."""
    detail = LinearCostModel(commission_bps=1.0).breakdown(
        previous=PREVIOUS_ALLER_RETOUR, target=TARGET_ALLER_RETOUR
    )
    attendu = cityblock(
        PREVIOUS_ALLER_RETOUR.to_numpy(),
        TARGET_ALLER_RETOUR.to_numpy(),
    )
    assert detail.traded_fraction == pytest.approx(attendu, abs=1e-15)


def test_la_derive_change_la_rotation_facturee() -> None:
    """(a) Calcul à la main : poids 0,60 et 0,40, rendements +10 % et -5 %.

    Valeurs après la période : 0,66 et 0,38, valeur liquidative 1,04.
    Poids dérivés : 33/52 et 19/52. Cible moitié-moitié, soit 26/52.
    Variations : -7/52 sur A et +7/52 sur B, somme entière 14/52.
    À 10 points de base de commission, le coût vaut 140/52 point de base.
    """
    contexte = pd.DataFrame({PERIOD_RETURN_COLUMN: [0.10, -0.05]}, index=ASSETS)
    detail = LinearCostModel(commission_bps=10.0).breakdown(
        previous=_weights(0.60, 0.40),
        target=_weights(0.50, 0.50),
        context=contexte,
    )
    assert detail.traded_fraction == pytest.approx(14 / 52, abs=1e-15)
    assert detail.commission_bps == pytest.approx(140 / 52, abs=1e-14)


def test_la_derive_divise_par_la_croissance_de_la_valeur_liquidative() -> None:
    """(a) Calcul à la main sur un portefeuille qui garde de l'encaisse.

    C'est le cas où les deux dénominateurs possibles de la dérive cessent de
    coïncider. Les poids valent 0,60 sur A et 0,20 sur B, donc 0,20 d'encaisse.
    A gagne 50 %, B ne bouge pas. La valeur liquidative passe à 1,30, et les
    poids dérivés valent 9/13 et 2/13. Vers une cible moitié-moitié, les écarts
    valent 5/26 et 9/26, de somme entière 14/26 = 7/13. À 13 points de base de
    commission, le coût vaut exactement 7 points de base.

    Diviser plutôt par la seule valeur investie, 1,10, donnerait des poids de
    9/11 et 2/11, une rotation de 7/11 et un coût de 8,27 points de base.
    """
    contexte = pd.DataFrame({PERIOD_RETURN_COLUMN: [0.50, 0.0]}, index=ASSETS)
    detail = LinearCostModel(commission_bps=13.0).breakdown(
        previous=_weights(0.60, 0.20),
        target=_weights(0.50, 0.50),
        context=contexte,
    )
    assert detail.traded_fraction == pytest.approx(7 / 13, abs=1e-15)
    assert detail.commission_bps == pytest.approx(7.0, abs=1e-13)


# --------------------------------------------------------------------------
# Le modèle linéaire, et la convention du demi-écart
# --------------------------------------------------------------------------


def test_aller_retour_complet_paie_l_ecart_entier() -> None:
    """(a) La convention du demi-écart, vérifiée sur un aller-retour complet.

    Un titre coté 99,95 contre 100,05 a un écart entier de 10 points de base du
    milieu, donc un demi-écart de 5 points. Acheter tout le portefeuille depuis
    l'encaisse puis tout revendre fait une rotation de 1,0 puis de 1,0, soit
    2,0 en tout. Le coût vaut 2,0 x 5 = 10 points de base, soit l'écart entier
    payé une fois sur l'aller-retour.
    """
    modele = LinearCostModel(spread_bps=5.0)
    encaisse = _weights(0.0, 0.0)
    investi = _weights(0.50, 0.50)

    aller = modele.breakdown(previous=encaisse, target=investi)
    retour = modele.breakdown(previous=investi, target=encaisse)

    assert aller.traded_fraction == pytest.approx(1.0, abs=1e-15)
    assert aller.spread_bps + retour.spread_bps == pytest.approx(10.0, abs=1e-14)


def test_le_taux_est_la_somme_des_trois_postes() -> None:
    """(b) Identité : le taux unitaire est la somme des trois taux déclarés."""
    modele = LinearCostModel(commission_bps=1.5, spread_bps=2.0, slippage_bps=0.25)
    assert modele.rate_bps == pytest.approx(3.75, abs=1e-15)


def test_doubler_la_rotation_double_le_cout_lineaire() -> None:
    """(b) Identité : le coût linéaire est proportionnel à la rotation."""
    modele = LinearCostModel(commission_bps=2.0, spread_bps=1.0)
    depart = _weights(0.0, 0.0)
    simple = modele.cost(previous=depart, target=_weights(0.10, 0.10))
    double = modele.cost(previous=depart, target=_weights(0.20, 0.20))
    assert double == pytest.approx(2.0 * simple, abs=1e-18)


@pytest.mark.parametrize(
    ("nom", "valeur"),
    [("commission_bps", -1.0), ("spread_bps", -0.5), ("slippage_bps", -3.0)],
)
def test_taux_negatif_refuse(nom: str, valeur: float) -> None:
    """Un coût négatif est un revenu, et ce module n'en distribue pas."""
    with pytest.raises(ConfigError):
        LinearCostModel(**{nom: valeur})


def test_taux_non_fini_refuse() -> None:
    """Un taux infini rendrait un coût infini sans jamais lever."""
    with pytest.raises(ConfigError):
        LinearCostModel(commission_bps=math.inf)


# --------------------------------------------------------------------------
# L'impact en racine carrée
# --------------------------------------------------------------------------


def test_impact_quadrupler_le_montant_multiplie_le_cout_par_huit() -> None:
    """(b) Identité : le coût d'impact croît comme la puissance trois demis.

    L'impact unitaire vaut une constante fois la racine du montant négocié,
    donc quadrupler le montant le double. Le coût, produit du montant par
    l'impact unitaire, est alors multiplié par quatre fois deux, soit huit.
    """
    modele = SqrtImpactModel(coefficient=0.5)
    contexte = _impact_context((0.02,), (10.0,), index=["A"])
    depart = pd.Series([0.0], index=["A"], dtype=float)

    petit = modele.breakdown(
        previous=depart, target=pd.Series([0.10], index=["A"], dtype=float), context=contexte
    )
    grand = modele.breakdown(
        previous=depart, target=pd.Series([0.40], index=["A"], dtype=float), context=contexte
    )
    assert grand.impact_bps == pytest.approx(8.0 * petit.impact_bps, abs=1e-12)


def test_impact_doubler_le_volume_divise_par_racine_de_deux() -> None:
    """(b) Identité : l'impact varie comme l'inverse de la racine du volume."""
    modele = SqrtImpactModel(coefficient=0.5)
    depart = pd.Series([0.0], index=["A"], dtype=float)
    cible = pd.Series([0.10], index=["A"], dtype=float)

    mince = modele.breakdown(
        previous=depart, target=cible, context=_impact_context((0.02,), (10.0,), index=["A"])
    )
    epais = modele.breakdown(
        previous=depart, target=cible, context=_impact_context((0.02,), (20.0,), index=["A"])
    )
    assert epais.impact_bps == pytest.approx(mince.impact_bps / math.sqrt(2.0), abs=1e-14)


def test_impact_valeur_a_la_main_sur_un_actif() -> None:
    """(a) Calcul à la main : 0,5 x 0,02 x racine(0,04) = 0,002, fois 0,20.

    La participation vaut 0,20 / 5,0 = 0,04 et sa racine 0,20. L'impact
    unitaire vaut 0,002 et le coût 0,20 x 0,002 = 0,0004, soit 4 points de base.
    """
    detail = SqrtImpactModel(coefficient=0.5).breakdown(
        previous=pd.Series([0.0], index=["A"], dtype=float),
        target=pd.Series([0.20], index=["A"], dtype=float),
        context=_impact_context((0.02,), (5.0,), index=["A"]),
    )
    assert detail.impact_bps == pytest.approx(4.0, abs=1e-13)


def test_impact_ecrete_au_plafond_de_participation() -> None:
    """(a) Calcul à la main : participation 0,50 écrêtée à 0,10.

    Le montant négocié vaut 0,50 pour un volume quotidien moyen égal au
    capital, donc une participation de 0,50. Le plafond la ramène à 0,10, dont
    la racine vaut environ 0,3162278. L'impact unitaire vaut alors
    1,0 x 0,02 x racine(0,10) et le coût 0,50 fois ce nombre, soit
    0,01 x racine(0,10) en fraction, donc 100 x racine(0,10) points de base.
    """
    detail = SqrtImpactModel(coefficient=1.0, participation_cap=0.10).breakdown(
        previous=pd.Series([0.0], index=["A"], dtype=float),
        target=pd.Series([0.50], index=["A"], dtype=float),
        context=_impact_context((0.02,), (1.0,), index=["A"]),
    )
    assert detail.impact_bps == pytest.approx(100.0 * math.sqrt(0.10), abs=1e-12)


def test_impact_sans_contexte_leve() -> None:
    """Un impact sans volatilité ni volume ne se chiffre pas à zéro en silence."""
    with pytest.raises(ConfigError):
        SqrtImpactModel().breakdown(previous=_weights(0.0, 0.0), target=_weights(0.5, 0.5))


def test_impact_actif_negocie_absent_du_contexte_leve() -> None:
    """Un actif négocié qui manque au contexte fait lever, il ne coûte pas zéro."""
    contexte = _impact_context((0.02,), (5.0,), index=["A"])
    with pytest.raises(DataQualityError):
        SqrtImpactModel().breakdown(previous=_weights(0.0, 0.0), target=_weights(0.1, 0.1), context=contexte)


def test_impact_volume_nul_leve() -> None:
    """Un titre qui n'échange pas ne se négocie pas non plus dans le modèle."""
    contexte = _impact_context((0.02,), (0.0,), index=["A"])
    with pytest.raises(DataQualityError):
        SqrtImpactModel().breakdown(
            previous=pd.Series([0.0], index=["A"], dtype=float),
            target=pd.Series([0.1], index=["A"], dtype=float),
            context=contexte,
        )


def test_plafond_de_participation_non_positif_refuse() -> None:
    """Un plafond nul rendrait tout impact nul, ce qui est un coût inventé."""
    with pytest.raises(ConfigError):
        SqrtImpactModel(coefficient=1.0, participation_cap=0.0)


# --------------------------------------------------------------------------
# Emprunt de titre et financement
# --------------------------------------------------------------------------


def test_emprunt_nul_sur_un_portefeuille_long_only() -> None:
    """(b) Identité : sans poids négatif, l'exposition vendeuse est nulle."""
    modele = BorrowCostModel(annual_bps=500.0, frequency=Frequency.DAILY)
    detail = modele.breakdown(previous=_weights(0.30, 0.70), target=_weights(0.60, 0.40))
    assert detail.borrow_bps == 0.0
    assert detail.total_bps == 0.0


def test_emprunt_douze_mois_cumulent_le_taux_annuel() -> None:
    """(b) Identité : douze périodes mensuelles rendent le taux annuel entier.

    Sur une exposition vendeuse de 100 % du capital, chaque mois coûte le
    douzième de 300 points de base, soit 25 points. Douze mois font 300.
    """
    modele = BorrowCostModel(annual_bps=300.0, frequency=Frequency.MONTHLY)
    court = _weights(0.0, -1.0)
    detail = modele.breakdown(previous=court, target=court)
    assert detail.borrow_bps == pytest.approx(25.0, abs=1e-13)
    assert 12.0 * detail.borrow_bps == pytest.approx(300.0, abs=1e-12)


def test_emprunt_facture_la_position_cible_et_non_la_precedente() -> None:
    """(a) Calcul à la main : la vente de 0,40 est facturée, pas celle de 0,10.

    Le loyer court sur la position détenue après le rééquilibrage. Avec un taux
    mensuel de 120/12 = 10 points de base, une exposition vendeuse cible de 0,40
    coûte 4 points de base.
    """
    modele = BorrowCostModel(annual_bps=120.0, frequency=Frequency.MONTHLY)
    detail = modele.breakdown(previous=_weights(0.5, -0.10), target=_weights(0.5, -0.40))
    assert detail.borrow_bps == pytest.approx(4.0, abs=1e-13)


def test_emprunt_additionne_toutes_les_positions_vendeuses() -> None:
    """(a) Calcul à la main : deux ventes à découvert, 0,30 et 0,20.

    L'exposition vendeuse est la SOMME des poids négatifs en valeur absolue,
    soit 0,50, et non le plus gros d'entre eux, qui vaut 0,30. Le taux mensuel
    vaut 240/12 = 20 points de base, donc le loyer vaut 20 x 0,50 = 10 points de
    base. Retenir le plus gros short rendrait 6 points.
    """
    trois = ["A", "B", "C"]
    fige = pd.Series([0.50, -0.30, -0.20], index=trois, dtype=float)
    detail = BorrowCostModel(annual_bps=240.0, frequency=Frequency.MONTHLY).breakdown(
        previous=fige, target=fige
    )
    assert detail.borrow_bps == pytest.approx(10.0, abs=1e-13)


def test_financement_additionne_les_trois_jambes_en_valeur_absolue() -> None:
    """(a) Calcul à la main : deux achats et une vente, exposition brute 2,00.

    Les poids valent 0,80, 0,70 et -0,50. Leur somme SIGNÉE vaut 1,00, qui ne
    financerait rien, alors que la somme de leurs valeurs absolues vaut 2,00,
    donc une part financée de 1,00. Au taux mensuel de 120/12 = 10 points de
    base, le coût vaut 10 points de base.
    """
    trois = ["A", "B", "C"]
    fige = pd.Series([0.80, 0.70, -0.50], index=trois, dtype=float)
    detail = FinancingCostModel(spread_over_rf_bps=120.0, frequency=Frequency.MONTHLY).breakdown(
        previous=fige, target=fige
    )
    assert detail.financing_bps == pytest.approx(10.0, abs=1e-13)


def test_financement_facture_l_exposition_cible_et_non_la_precedente() -> None:
    """(a) Calcul à la main : le levier facturé est celui d'après rééquilibrage.

    Les poids de départ valent 0,90 et -0,90, donc une exposition brute de 1,80
    et une part financée de 0,80. Les poids cibles valent 0,60 et -0,60, donc
    une exposition brute de 1,20 et une part financée de 0,20. Au taux mensuel
    de 120/12 = 10 points de base, la cible coûte 2 points et la position de
    départ en coûterait 8.
    """
    detail = FinancingCostModel(spread_over_rf_bps=120.0, frequency=Frequency.MONTHLY).breakdown(
        previous=_weights(0.90, -0.90), target=_weights(0.60, -0.60)
    )
    assert detail.financing_bps == pytest.approx(2.0, abs=1e-13)
    assert detail.traded_fraction == pytest.approx(0.60, abs=1e-15)


def test_financement_nul_a_levier_un() -> None:
    """(b) Identité : une exposition brute de un ne finance rien."""
    modele = FinancingCostModel(spread_over_rf_bps=200.0, frequency=Frequency.DAILY)
    detail = modele.breakdown(previous=_weights(0.20, 0.80), target=_weights(0.60, 0.40))
    assert detail.financing_bps == 0.0
    assert detail.total_bps == 0.0


def test_financement_nul_sous_le_levier_un() -> None:
    """(b) Identité : une exposition brute inférieure à un ne finance rien."""
    modele = FinancingCostModel(spread_over_rf_bps=200.0, frequency=Frequency.DAILY)
    detail = modele.breakdown(previous=_weights(0.10, 0.10), target=_weights(0.25, 0.25))
    assert detail.financing_bps == 0.0


def test_financement_douze_mois_a_levier_deux_cumulent_l_ecart_annuel() -> None:
    """(b) Identité : à levier deux, une unité est financée toute l'année.

    L'exposition brute vaut 2,0, la part financée 1,0. Chaque mois coûte le
    douzième de 100 points de base, et douze mois font 100.
    """
    modele = FinancingCostModel(spread_over_rf_bps=100.0, frequency=Frequency.MONTHLY)
    levier = _weights(1.20, -0.80)
    detail = modele.breakdown(previous=levier, target=levier)
    assert detail.financing_bps == pytest.approx(100.0 / 12.0, abs=1e-13)
    assert 12.0 * detail.financing_bps == pytest.approx(100.0, abs=1e-12)


def test_le_portage_court_meme_quand_rien_ne_bouge() -> None:
    """(b) Identité : le loyer dépend du temps, pas de la rotation.

    Un portefeuille inchangé a une rotation nulle et paie quand même son
    emprunt de titre. Confondre les deux ferait disparaître le coût d'une
    position tenue longtemps sans rééquilibrage.
    """
    fige = _weights(0.60, -0.40)
    detail = BorrowCostModel(annual_bps=252.0, frequency=Frequency.DAILY).breakdown(
        previous=fige, target=fige
    )
    assert detail.traded_fraction == 0.0
    assert detail.borrow_bps == pytest.approx(0.40, abs=1e-14)


# --------------------------------------------------------------------------
# La composition et la configuration
# --------------------------------------------------------------------------


def test_composition_vide_rend_un_cout_nul_et_la_rotation() -> None:
    """(b) Identité : une somme vide vaut zéro, et la rotation reste mesurée."""
    detail = CompositeCostModel().breakdown(previous=PREVIOUS_ALLER_RETOUR, target=TARGET_ALLER_RETOUR)
    assert detail.total_bps == 0.0
    assert detail.traded_fraction == pytest.approx(0.40, abs=1e-15)
    assert len(CompositeCostModel()) == 0


def test_composition_refuse_un_objet_sans_breakdown() -> None:
    """Un objet qui ne sait pas chiffrer un coût n'entre pas dans la somme."""
    with pytest.raises(ConfigError):
        CompositeCostModel([object()])  # type: ignore[list-item]


def test_addition_de_deux_decompositions_de_rotations_differentes_leve() -> None:
    """Deux rééquilibrages différents ne s'additionnent pas par accident."""
    un = CostBreakdown(commission_bps=1.0, traded_fraction=0.40)
    deux = CostBreakdown(commission_bps=1.0, traded_fraction=0.80)
    with pytest.raises(ConfigError):
        _ = un + deux


def test_from_config_active_les_composantes_declarees() -> None:
    """(a) Trois composantes déclarées, trois modèles construits.

    La configuration porte une commission, un demi-écart, un impact en racine
    carrée et un emprunt annuel. Le financement reste à zéro, donc son modèle
    n'est pas instancié.
    """
    config = CostConfig(
        commission_bps=1.0,
        spread_bps=2.5,
        impact_model="sqrt",
        impact_coefficient=0.5,
        borrow_bps_annual=300.0,
    )
    modele = from_config(config, frequency=Frequency.DAILY)
    types = [type(m).__name__ for m in modele.models]
    assert types == ["LinearCostModel", "SqrtImpactModel", "BorrowCostModel"]


def test_from_config_sans_cout_rend_une_composition_vide() -> None:
    """Une étude brute de frais le dit explicitement, par une somme vide."""
    assert len(from_config(CostConfig())) == 0


def test_from_config_refuse_un_modele_d_impact_inconnu() -> None:
    """Le seul nom d'impact reconnu est « sqrt »."""
    with pytest.raises(ConfigError):
        from_config(CostConfig(impact_model="lineaire"))


def test_from_config_retrouve_le_calcul_a_la_main() -> None:
    """(a) La configuration équivalente rend les 9,274603 points de base."""
    config = CostConfig(
        commission_bps=1.0,
        spread_bps=2.5,
        slippage_bps=0.5,
        impact_model="sqrt",
        impact_coefficient=0.5,
        borrow_bps_annual=300.0,
        financing_spread_bps_annual=100.0,
    )
    detail = from_config(config, frequency=Frequency.DAILY).breakdown(
        previous=PREVIOUS_ALLER_RETOUR,
        target=TARGET_ALLER_RETOUR,
        context=CONTEXT_ALLER_RETOUR,
    )
    assert detail.total_bps == pytest.approx(ATTENDU_TOTAL_BPS, abs=1e-13)


def test_les_modeles_satisfont_le_protocole_du_laboratoire() -> None:
    """Chaque modèle porte la méthode exigée par ``core.protocols.CostModel``."""
    for modele in (
        LinearCostModel(commission_bps=1.0),
        SqrtImpactModel(),
        BorrowCostModel(annual_bps=10.0),
        FinancingCostModel(spread_over_rf_bps=10.0),
        CompositeCostModel(),
    ):
        assert isinstance(modele, CostModel)


def test_as_dict_porte_le_total() -> None:
    """(b) Identité : le dictionnaire de rapport contient la même somme."""
    detail = CostBreakdown(commission_bps=1.0, spread_bps=2.0, traded_fraction=0.5)
    rendu = detail.as_dict()
    assert rendu["total_bps"] == pytest.approx(3.0, abs=1e-15)
    assert rendu["traded_fraction"] == 0.5


# --------------------------------------------------------------------------
# Le seuil de rentabilité
# --------------------------------------------------------------------------


def _serie_de_test(valeurs: list[float]) -> pd.Series:
    index = pd.bdate_range("2020-01-01", periods=len(valeurs))
    return pd.Series(valeurs, index=index, dtype=float)


def test_seuil_de_rentabilite_valeur_a_la_main() -> None:
    """(a) Calcul à la main : moyenne brute 0,0002, rotation moyenne 0,40.

    Les rendements bruts alternent 0,0003 et 0,0001, de moyenne 0,0002. Les
    rotations alternent 0,50 et 0,30, de moyenne 0,40. Le seuil vaut
    0,0002 / 0,40 = 0,0005, soit 5 points de base par unité négociée.
    """
    bruts = _serie_de_test([0.0003, 0.0001] * 12)
    rotations = _serie_de_test([0.50, 0.30] * 12)
    assert breakeven_cost_bps(bruts, rotations, Frequency.DAILY) == pytest.approx(5.0, abs=1e-12)


def test_le_cout_du_seuil_annule_l_alpha_net() -> None:
    """(b) Identité : appliquer le seuil trouvé annule la moyenne du net.

    C'est la définition même du seuil, et c'est le contrôle qui prouve que la
    conversion en points de base ne s'est pas trompée de facteur.
    """
    rng = np.random.default_rng(20260901)
    bruts = _serie_de_test(list(rng.normal(0.0004, 0.01, size=250)))
    rotations = _serie_de_test(list(rng.uniform(0.05, 0.90, size=250)))

    seuil_bps = breakeven_cost_bps(bruts, rotations, Frequency.DAILY)
    nets = bruts - (seuil_bps / BPS_PER_UNIT) * rotations
    assert float(nets.mean()) == pytest.approx(0.0, abs=1e-12)


def test_doubler_l_alpha_brut_double_le_seuil() -> None:
    """(b) Identité : le seuil est linéaire dans les rendements bruts."""
    bruts = _serie_de_test([0.0003, 0.0001, 0.0005] * 8)
    rotations = _serie_de_test([0.50, 0.30, 0.20] * 8)
    simple = breakeven_cost_bps(bruts, rotations, Frequency.DAILY)
    double = breakeven_cost_bps(2.0 * bruts, rotations, Frequency.DAILY)
    assert double == pytest.approx(2.0 * simple, abs=1e-12)


def test_le_seuil_ne_depend_pas_de_la_frequence_declaree() -> None:
    """(b) Identité : le facteur d'annualisation se simplifie dans le rapport."""
    bruts = _serie_de_test([0.0003, 0.0001] * 12)
    rotations = _serie_de_test([0.50, 0.30] * 12)
    quotidien = breakeven_cost_bps(bruts, rotations, Frequency.DAILY)
    mensuel = breakeven_cost_bps(bruts, rotations, Frequency.MONTHLY)
    assert quotidien == pytest.approx(mensuel, abs=0.0, rel=0.0)


def test_un_alpha_brut_negatif_rend_un_seuil_negatif() -> None:
    """(b) Identité : le signe du seuil est celui de la moyenne brute."""
    bruts = _serie_de_test([-0.0002] * 24)
    rotations = _serie_de_test([0.40] * 24)
    assert breakeven_cost_bps(bruts, rotations, Frequency.DAILY) < 0.0


def test_seuil_refuse_une_serie_trop_courte() -> None:
    """Un rapport de deux moyennes sur trois points n'est pas interprétable."""
    with pytest.raises(InsufficientDataError):
        breakeven_cost_bps(_serie_de_test([0.01, 0.02, 0.03]), _serie_de_test([0.1, 0.2, 0.3]))


def test_seuil_refuse_une_rotation_moyenne_nulle() -> None:
    """Une stratégie qui ne négocie jamais n'a pas de seuil de rentabilité."""
    with pytest.raises(DataQualityError):
        breakeven_cost_bps(_serie_de_test([0.001] * 24), _serie_de_test([0.0] * 24))


def test_seuil_refuse_une_rotation_negative() -> None:
    """Une rotation est une somme de valeurs absolues, jamais un nombre négatif."""
    rotations = _serie_de_test([0.4] * 23 + [-0.1])
    with pytest.raises(DataQualityError):
        breakeven_cost_bps(_serie_de_test([0.001] * 24), rotations)


def test_seuil_refuse_une_valeur_manquante() -> None:
    """Une période sans rotation connue se retire en amont, pas ici."""
    rotations = _serie_de_test([0.4] * 23 + [float("nan")])
    with pytest.raises(DataQualityError):
        breakeven_cost_bps(_serie_de_test([0.001] * 24), rotations)


def test_seuil_refuse_un_index_duplique() -> None:
    """(a) Calcul à la main : quatre dates dupliquées franchiraient le plancher.

    Quatre dates présentes deux fois dans les rendements et trois fois dans les
    rotations donnent 4 x 2 x 3 = 24 lignes après appariement, donc deux fois le
    plancher de douze observations, alors que l'étude ne porte que sur quatre
    périodes réelles. Le doublon se refuse avant l'alignement.
    """
    quatre = list(pd.bdate_range("2020-01-01", periods=4))
    bruts = pd.Series([0.001] * 8, index=quatre * 2, dtype=float)
    rotations = pd.Series([0.4] * 12, index=quatre * 3, dtype=float)
    with pytest.raises(DataQualityError):
        breakeven_cost_bps(bruts, rotations)


def test_seuil_refuse_une_intersection_maigre() -> None:
    """(a) Calcul à la main : 24 périodes communes sur 240 font 90 % de perte.

    Les rendements couvrent 240 séances et les rotations les 24 premières. La
    jointure en retient 24, soit 90 % de perte du côté des rendements, très
    au-dessus du dixième toléré. Sans ce garde-fou, le seuil rendu décrirait un
    mois choisi par personne.
    """
    longues = pd.bdate_range("2020-01-01", periods=240)
    bruts = pd.Series(np.linspace(-0.01, 0.01, 240), index=longues, dtype=float)
    rotations = pd.Series([0.4] * 24, index=longues[:24], dtype=float)
    with pytest.raises(DataQualityError):
        breakeven_cost_bps(bruts, rotations)


def test_seuil_tolere_un_decalage_de_bord() -> None:
    """(a) Calcul à la main : perdre 2 périodes sur 24 fait 8,3 %, sous le seuil.

    Les rotations manquent les deux premières séances, ce qui arrive dès qu'un
    signal a besoin d'une fenêtre pour démarrer. La perte vaut 2/24, soit 8,3 %,
    donc sous le dixième toléré, et le calcul aboutit. Sur des séries constantes
    de 0,0002 et 0,40, le seuil vaut 5 points de base.
    """
    dates = pd.bdate_range("2020-01-01", periods=24)
    bruts = pd.Series([0.0002] * 24, index=dates, dtype=float)
    rotations = pd.Series([0.40] * 22, index=dates[2:], dtype=float)
    assert breakeven_cost_bps(bruts, rotations, min_observations=12) == pytest.approx(5.0, abs=1e-12)


def test_seuil_refuse_une_tolerance_hors_bornes() -> None:
    """Une part perdue se déclare entre zéro et un, jamais au-delà."""
    bruts = _serie_de_test([0.0002] * 24)
    rotations = _serie_de_test([0.40] * 24)
    with pytest.raises(ConfigError):
        breakeven_cost_bps(bruts, rotations, max_dropped_fraction=1.5)


def test_seuil_refuse_autre_chose_qu_une_serie() -> None:
    """Une liste n'a pas d'index, donc aucun alignement n'est possible."""
    with pytest.raises(TypeError):
        breakeven_cost_bps([0.01] * 24, _serie_de_test([0.4] * 24))  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# Les cas limites des vecteurs de poids
# --------------------------------------------------------------------------


def test_poids_vides_levent() -> None:
    """Deux vecteurs vides ne décrivent aucun rééquilibrage."""
    vide = pd.Series(dtype=float)
    with pytest.raises(InsufficientDataError):
        LinearCostModel(commission_bps=1.0).breakdown(previous=vide, target=vide)


def test_un_seul_actif_se_chiffre() -> None:
    """(a) Calcul à la main : un actif, rotation 0,25, taux 4 points de base.

    Le coût vaut 4,0 x 0,25 = 1,0 point de base.
    """
    detail = LinearCostModel(commission_bps=4.0).breakdown(
        previous=pd.Series([0.25], index=["A"], dtype=float),
        target=pd.Series([0.50], index=["A"], dtype=float),
    )
    assert detail.commission_bps == pytest.approx(1.0, abs=1e-14)


def test_poids_tous_nuls_rendent_un_cout_nul() -> None:
    """(b) Identité : un portefeuille vide ne négocie ni ne porte rien."""
    zero = _weights(0.0, 0.0)
    modele = CompositeCostModel(
        [
            LinearCostModel(commission_bps=5.0),
            BorrowCostModel(annual_bps=500.0),
            FinancingCostModel(spread_over_rf_bps=500.0),
        ]
    )
    assert modele.cost(previous=zero, target=zero) == 0.0


def test_poids_manquant_leve() -> None:
    """Un poids inconnu ne se remplace pas par zéro en silence."""
    with pytest.raises(DataQualityError):
        LinearCostModel(commission_bps=1.0).breakdown(
            previous=_weights(float("nan"), 0.5), target=_weights(0.5, 0.5)
        )


def test_index_en_double_leve() -> None:
    """Un actif présent deux fois rendrait la rotation ambiguë."""
    double = pd.Series([0.5, 0.5], index=["A", "A"], dtype=float)
    with pytest.raises(DataQualityError):
        LinearCostModel(commission_bps=1.0).breakdown(previous=double, target=double)


def test_entree_qui_n_est_pas_une_serie_leve() -> None:
    """Un dictionnaire n'a pas d'index aligné, donc pas de rotation définie."""
    with pytest.raises(TypeError):
        LinearCostModel(commission_bps=1.0).breakdown(
            previous={"A": 0.5},  # type: ignore[arg-type]
            target=_weights(0.5, 0.5),
        )


def test_univers_disjoints_comptent_les_entrees_et_les_sorties() -> None:
    """(a) Calcul à la main : sortir de A à 0,60 et entrer sur C à 0,60.

    L'union des deux univers porte A et C. La variation vaut -0,60 sur A et
    +0,60 sur C, donc une rotation de 1,20 en somme entière. À 2 points de base,
    le coût vaut 2,4 points de base.
    """
    detail = LinearCostModel(commission_bps=2.0).breakdown(
        previous=pd.Series([0.60], index=["A"], dtype=float),
        target=pd.Series([0.60], index=["C"], dtype=float),
    )
    assert detail.traded_fraction == pytest.approx(1.20, abs=1e-15)
    assert detail.commission_bps == pytest.approx(2.4, abs=1e-14)


# --------------------------------------------------------------------------
# Propriétés hypothesis
# --------------------------------------------------------------------------

_POIDS = st.floats(min_value=-2.0, max_value=2.0, allow_nan=False, allow_infinity=False, width=32)


@given(paires=st.lists(st.tuples(_POIDS, _POIDS), min_size=1, max_size=6))
@settings(max_examples=200, deadline=None)
def test_propriete_le_cout_croit_avec_la_rotation(paires: list[tuple[float, float]]) -> None:
    """(b) Identité : doubler le déplacement des poids ne peut pas coûter moins.

    Le coût linéaire vaut le taux multiplié par la somme des variations en
    valeur absolue. Multiplier chaque variation par deux double cette somme,
    donc double le coût.
    """
    index = [f"A{i}" for i in range(len(paires))]
    depart = pd.Series([p[0] for p in paires], index=index, dtype=float)
    pas = pd.Series([p[1] for p in paires], index=index, dtype=float)
    modele = LinearCostModel(commission_bps=1.0, spread_bps=2.0, slippage_bps=0.5)

    petit = modele.cost(previous=depart, target=depart + pas)
    grand = modele.cost(previous=depart, target=depart + 2.0 * pas)
    assert grand >= petit - 1e-15


@given(paires=st.lists(st.tuples(_POIDS, _POIDS), min_size=1, max_size=6))
@settings(max_examples=200, deadline=None)
def test_propriete_l_impact_croit_avec_la_rotation(paires: list[tuple[float, float]]) -> None:
    """(b) Identité : l'impact est croissant en montant négocié, actif par actif."""
    index = [f"A{i}" for i in range(len(paires))]
    depart = pd.Series([p[0] for p in paires], index=index, dtype=float)
    pas = pd.Series([p[1] for p in paires], index=index, dtype=float)
    contexte = pd.DataFrame(
        {VOLATILITY_COLUMN: [0.02] * len(paires), ADV_FRACTION_COLUMN: [100.0] * len(paires)},
        index=index,
    )
    modele = SqrtImpactModel(coefficient=1.0)

    petit = modele.cost(previous=depart, target=depart + pas, context=contexte)
    grand = modele.cost(previous=depart, target=depart + 2.0 * pas, context=contexte)
    assert grand >= petit - 1e-15


@given(valeurs=st.lists(_POIDS, min_size=1, max_size=8))
@settings(max_examples=200, deadline=None)
def test_propriete_le_cout_de_transaction_est_nul_quand_rien_ne_bouge(valeurs: list[float]) -> None:
    """(b) Identité : une cible égale à la position rend une rotation nulle.

    Le contrôle porte sur les seules composantes de transaction. Les coûts de
    portage, eux, courent avec le temps et restent dus, ce que vérifie
    ``test_le_portage_court_meme_quand_rien_ne_bouge``.
    """
    index = [f"A{i}" for i in range(len(valeurs))]
    poids = pd.Series(valeurs, index=index, dtype=float)
    contexte = pd.DataFrame(
        {VOLATILITY_COLUMN: [0.02] * len(valeurs), ADV_FRACTION_COLUMN: [50.0] * len(valeurs)},
        index=index,
    )
    modele = CompositeCostModel(
        [LinearCostModel(commission_bps=3.0, spread_bps=2.0), SqrtImpactModel(coefficient=1.0)]
    )
    detail = modele.breakdown(previous=poids, target=poids.copy(), context=contexte)

    assert detail.traded_fraction == 0.0
    assert detail.total_bps == 0.0


@given(shorts=st.lists(st.floats(min_value=0.0, max_value=1.0, width=32), min_size=1, max_size=6))
@settings(max_examples=200, deadline=None)
def test_propriete_le_loyer_est_additif_sur_les_positions_vendeuses(shorts: list[float]) -> None:
    """(b) Identité : le loyer d'un panier de ventes vaut la somme des loyers.

    L'exposition vendeuse est une somme, pas un maximum. Facturer le panier
    entier doit donc rendre exactement ce que rend la somme des positions prises
    une à une, à la précision machine près.
    """
    index = [f"S{i}" for i in range(len(shorts))]
    panier = pd.Series([-abs(v) for v in shorts], index=index, dtype=float)
    modele = BorrowCostModel(annual_bps=360.0, frequency=Frequency.MONTHLY)

    ensemble = modele.breakdown(previous=panier, target=panier).borrow_bps
    un_a_un = sum(
        modele.breakdown(
            previous=pd.Series([panier[nom]], index=[nom], dtype=float),
            target=pd.Series([panier[nom]], index=[nom], dtype=float),
        ).borrow_bps
        for nom in index
    )
    assert ensemble == pytest.approx(un_a_un, abs=1e-12)


@given(
    moyenne=st.floats(min_value=1e-6, max_value=1e-2, allow_nan=False, allow_infinity=False),
    rotation=st.floats(min_value=1e-3, max_value=3.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100, deadline=None)
def test_propriete_le_seuil_est_le_rapport_des_deux_moyennes(moyenne: float, rotation: float) -> None:
    """(b) Identité : sur des séries constantes, le seuil vaut le rapport exact."""
    bruts = _serie_de_test([moyenne] * 24)
    rotations = _serie_de_test([rotation] * 24)
    attendu = BPS_PER_UNIT * moyenne / rotation
    assert breakeven_cost_bps(bruts, rotations) == pytest.approx(attendu, rel=1e-12)

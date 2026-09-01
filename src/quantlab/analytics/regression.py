r"""La régression factorielle, et pourquoi ses erreurs types par défaut sont fausses.

**Le problème.** Une régression d'un rendement sur des facteurs rend deux
choses : des chargements et une mesure de leur précision. Les chargements sont
sans biais sous des hypothèses faibles ; la mesure de précision, elle, est
fausse presque toujours sur des rendements financiers. Un alpha déclaré
significatif à 2,5 erreurs types peut tomber sous 1,5 dès que la formule de
variance tient compte de ce que les rendements font vraiment.

**Deux violations, et une seule conséquence.** Les moindres carrés ordinaires
supposent des résidus de variance constante et non corrélés entre eux. Les
rendements violent les deux. La variance se regroupe en paquets, phénomène
documenté par Mandelbrot (1963) puis modélisé par Engle (1982) : les grosses
variations suivent les grosses variations. Et les rendements de portefeuilles
construits sur des signaux lents restent corrélés d'une période à la suivante,
d'autant plus que les positions se recouvrent. Dans les deux cas les
coefficients restent sans biais, et c'est leur variance estimée qui est trop
petite. Le t rendu par la formule ordinaire est donc trop grand, et il ment
dans le sens qui flatte le chercheur.

**Ce que corrige HAC, et ce qu'il ne corrige pas.** L'estimateur de Newey et
West (1987) remplace la matrice centrale de la variance par une somme pondérée
des autocovariances des scores. La somme s'arrête à un nombre de retards
choisi. Il corrige
l'hétéroscédasticité et l'autocorrélation dans la VARIANCE ESTIMÉE des
coefficients. Il ne corrige RIEN d'autre. En particulier il ne déplace pas
les coefficients d'un millième. Il ne répare ni un biais de variable omise, ni
une erreur de mesure sur un facteur. Il ne rend pas non plus valide une
régression dont le régresseur est endogène. Un alpha faux reste faux avec HAC,
seulement mieux entouré.

**Le compromis du nombre de retards.** Trop peu de retards laisse de
l'autocorrélation dans la variance estimée, donc un t encore trop grand. Trop
de retards fait estimer beaucoup d'autocovariances sur peu de données, ce qui
rend la variance elle-même bruitée et la statistique instable en petit
échantillon. Les deux règles empiriques implémentées ici sortent de cette
tension. Voir :func:`newey_west_lags`.

**Pourquoi un alpha survit à trois facteurs et meurt contre cinq.** L'alpha
d'une régression est la part du rendement moyen que les facteurs inclus
n'expliquent pas. Ajouter un facteur corrélé à la stratégie transfère du
rendement moyen de l'alpha vers le nouveau chargement, par simple algèbre des
moindres carrés. Fama et French (2015) ajoutent la rentabilité et
l'investissement aux trois facteurs de 1993 ; les stratégies de qualité et de
faible risque, très chargées sur ces deux dimensions, y perdent l'essentiel de
leur alpha. La leçon pratique tient en une phrase : un alpha n'est jamais un
fait, c'est un reste, et ce reste dépend de la liste des facteurs.

**Frontière de types.** Ce module parle pandas, indexé par le temps. Les séries
sont alignées sur l'intersection de leurs index, triées, puis les lignes
incomplètes sont retirées. L'ordre chronologique compte : l'estimateur HAC lit
les résidus dans l'ordre où ils arrivent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.linalg import qr

from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.logging import get_logger
from quantlab.core.types import Frequency

__all__ = [
    "DEFAULT_BLUME_WEIGHT",
    "DEFAULT_COLLINEARITY_TOL",
    "DEFAULT_ZERO_VARIANCE_TOL",
    "INTERCEPT_NAME",
    "TOTAL_ROW_NAME",
    "FactorRegressionResult",
    "attribution_table",
    "beta",
    "factor_regression",
    "newey_west_lags",
    "residualize",
    "rolling_alpha",
    "rolling_beta",
    "shrunk_beta",
]

log = get_logger(__name__)

#: Nom donné à la constante de régression dans les tableaux rendus.
INTERCEPT_NAME = "alpha"

#: Nom de la ligne de somme ajoutée par :func:`attribution_table`. Un facteur qui
#: porterait ce nom rendrait l'index ambigu, et ``table.loc["total"]`` rendrait
#: alors deux lignes au lieu d'une. Le nom est donc refusé, pas toléré.
TOTAL_ROW_NAME = "total"

#: Poids par défaut du rétrécissement de bêta, deux tiers sur l'estimation et un
#: tiers sur la cible. C'est la convention dite « bêta ajusté » popularisée par
#: les terminaux de marché, elle-même issue de Blume (1975). Rapporté, non mesuré
#: sur les données du laboratoire.
DEFAULT_BLUME_WEIGHT = 2.0 / 3.0

#: Seuil de détection de la colinéarité, exprimé en rapport de valeurs
#: singulières sur la matrice de plan aux colonnes normalisées. Une valeur
#: singulière sous ``tol`` fois la plus grande signale une colonne redondante.
DEFAULT_COLLINEARITY_TOL = 1e-8

#: Seuil relatif en deçà duquel une série est déclarée constante. Il se compare à
#: la somme des carrés centrés rapportée à la somme des carrés bruts. Une série
#: vraiment constante rend un rapport non nul, à cause de l'erreur d'arrondi sur
#: la moyenne. Mesuré sur dix valeurs égales à 0,01 : le rapport vaut 3,0e-32,
#: donc seize ordres de grandeur sous le seuil retenu, qui le détecte.
DEFAULT_ZERO_VARIANCE_TOL = 1e-16

#: Nombre de degrés de liberté perdus par une régression simple, la constante et
#: la pente.
_SIMPLE_REGRESSION_PARAMS = 2

LagRule = Literal["newey_west", "stock_watson"]
CovType = Literal["nonrobust", "HC0", "HC1", "HC2", "HC3", "HAC"]

_COV_TYPES: frozenset[str] = frozenset({"nonrobust", "HC0", "HC1", "HC2", "HC3", "HAC"})


# --------------------------------------------------------------------------- #
# Le résultat
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, eq=False, slots=True)
class FactorRegressionResult:
    """Le résultat gelé d'une régression factorielle, chiffres et convention.

    Chaque champ porte sa convention avec lui, parce qu'un alpha sans son échelle
    et un t sans son type de covariance sont des nombres qu'on ne peut pas
    relire. L'objet est immuable : un résultat de recherche ne se modifie pas
    après coup.

    Attributes:
        alpha: la constante de la régression, annualisée si ``alpha_annualized``.
        alpha_stderr: son erreur type, à la même échelle que ``alpha``.
        alpha_tstat: le rapport de l'alpha à son erreur type, invariant à
            l'annualisation puisque les deux sont multipliés par le même nombre.
        alpha_pvalue: la valeur p bilatérale associée.
        alpha_annualized: vrai si ``alpha`` est exprimé par an, faux s'il est
            exprimé par période d'observation.
        betas: les chargements factoriels, indexés par nom de facteur.
        beta_stderr: leurs erreurs types.
        beta_tstats: leurs statistiques t.
        beta_pvalues: leurs valeurs p bilatérales.
        r_squared: la part de variance du rendement expliquée par les facteurs.
        adj_r_squared: la même, pénalisée par le nombre de régresseurs.
        n_obs: le nombre d'observations réellement utilisées, après alignement et
            retrait des lignes incomplètes.
        cov_type: le type de matrice de covariance des coefficients.
        maxlags: le nombre de retards de l'estimateur HAC, ``None`` sinon.
        frequency: la fréquence d'observation déclarée des séries.
        factor_means: la moyenne de chaque facteur sur l'échantillon utilisé, par
            période et non annualisée.
        mean_excess_return: la moyenne du rendement régressé sur ce même
            échantillon, par période.
        residuals: les résidus, indexés comme l'échantillon utilisé.
        fitted: la partie expliquée, indexée de même.

    Note:
        L'identité des moindres carrés avec constante impose
        ``mean_excess_return = alpha_par_période + somme(betas * factor_means)``.
        :func:`attribution_table` s'appuie dessus, et un test la vérifie à
        1e-12.
    """

    alpha: float
    alpha_stderr: float
    alpha_tstat: float
    alpha_pvalue: float
    alpha_annualized: bool
    betas: pd.Series
    beta_stderr: pd.Series
    beta_tstats: pd.Series
    beta_pvalues: pd.Series
    r_squared: float
    adj_r_squared: float
    n_obs: int
    cov_type: str
    maxlags: int | None
    frequency: Frequency
    factor_means: pd.Series
    mean_excess_return: float
    residuals: pd.Series
    fitted: pd.Series

    @property
    def annualization_factor(self) -> float:
        """Le nombre par lequel l'alpha par période a été multiplié.

        Returns:
            Le nombre de périodes par an si l'alpha est annualisé, 1,0 sinon.
        """
        return self.frequency.periods_per_year if self.alpha_annualized else 1.0

    @property
    def factor_names(self) -> list[str]:
        """La liste des facteurs, dans l'ordre où ils ont été régressés."""
        return [str(name) for name in self.betas.index]


# --------------------------------------------------------------------------- #
# Préparation des données
# --------------------------------------------------------------------------- #


def _as_frame(factors: pd.Series | pd.DataFrame) -> pd.DataFrame:
    """Rend les facteurs sous forme de tableau, une colonne par facteur."""
    if isinstance(factors, pd.Series):
        name = "factor" if factors.name is None else str(factors.name)
        return factors.rename(name).to_frame()
    if isinstance(factors, pd.DataFrame):
        return factors
    raise ConfigError("les facteurs doivent être une Series ou un DataFrame pandas")


def _check_index(obj: pd.Series | pd.DataFrame, label: str) -> None:
    """Refuse un index dupliqué, qui ferait apparier deux fois la même date."""
    if obj.index.has_duplicates:
        raise DataQualityError(f"index dupliqué dans {label} : l'appariement serait ambigu")


def _align(
    returns: pd.Series,
    factors: pd.Series | pd.DataFrame,
    risk_free: pd.Series | float | None = None,
) -> tuple[pd.Series, pd.DataFrame]:
    """Aligne le rendement et les facteurs, retire les lignes incomplètes, trie.

    Args:
        returns: la série régressée, brute ou déjà en excès.
        factors: un ou plusieurs facteurs. Ils sont supposés déjà en excès du
            taux sans risque, comme le sont ceux de la bibliothèque de Kenneth
            French.
        risk_free: le taux sans risque de la même fréquence, à retirer du
            rendement régressé. Un nombre le fixe constant sur tout
            l'échantillon.

    Returns:
        Le couple (rendement en excès, tableau des facteurs), même index trié.

    Raises:
        DataQualityError: si un index porte des doublons.
        InsufficientDataError: si l'intersection est vide.

    Note:
        L'assemblage se fait par position, jamais par nom de colonne. Un facteur
        peut donc porter n'importe quel nom sans écraser le rendement régressé ni
        le taux sans risque.
    """
    y = pd.Series(returns).astype(float)
    x = _as_frame(factors).astype(float)
    _check_index(y, "les rendements")
    _check_index(x, "les facteurs")
    if x.columns.has_duplicates:
        raise ConfigError("deux facteurs portent le même nom, le tableau serait illisible")

    parts: list[pd.Series] = [y]
    parts.extend(x[column] for column in x.columns)
    if isinstance(risk_free, pd.Series):
        _check_index(risk_free, "le taux sans risque")
        parts.append(risk_free.astype(float))

    # Les colonnes sont renumérotées par position avant toute lecture. Un
    # appariement par nom laisserait un facteur appelé comme une colonne interne
    # écraser le rendement régressé, sans message et sans trace.
    joined = pd.concat(parts, axis=1, join="inner").set_axis(pd.RangeIndex(len(parts)), axis="columns")
    joined = joined.dropna(how="any").sort_index()
    if joined.empty:
        raise InsufficientDataError("aucune date commune entre le rendement et les facteurs")

    excess = joined.iloc[:, 0]
    if isinstance(risk_free, pd.Series):
        excess = excess - joined.iloc[:, len(parts) - 1]
    elif risk_free is not None:
        excess = excess - float(risk_free)

    aligned_factors = joined.iloc[:, 1 : 1 + x.shape[1]].set_axis(
        [str(column) for column in x.columns], axis="columns"
    )
    return excess.rename(y.name if y.name is not None else "asset"), aligned_factors


def _single_market(aligned: pd.DataFrame) -> pd.Series:
    """Rend l'unique colonne de marché, et refuse un tableau qui en porte plusieurs.

    Les fonctions à un seul facteur prennent la première colonne de ce qu'on leur
    passe. Devant un tableau de trois facteurs, prendre la première en silence
    rendrait un bêta calculé sur une série que l'appelant n'a pas choisie.

    Args:
        aligned: le tableau des régresseurs, déjà aligné.

    Returns:
        La colonne unique, en série.

    Raises:
        ConfigError: si le tableau ne porte pas exactement une colonne.
    """
    if aligned.shape[1] != 1:
        raise ConfigError(
            f"le marché doit être une seule série, {aligned.shape[1]} colonnes reçues : "
            "choisissez la colonne avant d'appeler."
        )
    return aligned.iloc[:, 0]


def _assert_full_rank(design: pd.DataFrame, tol: float) -> None:
    """Refuse une matrice de plan de rang déficient, en nommant les coupables.

    **Pourquoi ce garde-fou.** ``statsmodels`` résout les moindres carrés par
    pseudo-inverse. Devant deux colonnes identiques il ne lève rien : il rend une
    solution de norme minimale, qui répartit arbitrairement le chargement entre
    les colonnes liées. Les erreurs types deviennent alors ininterprétables sans
    qu'aucun message ne le signale. Le laboratoire préfère l'arrêt net.

    **Méthode.** Les colonnes sont normalisées, pour que le seuil ne dépende pas
    des unités, puis une décomposition QR avec pivotage de colonnes classe les
    régresseurs par information ajoutée. Un terme diagonal sous ``tol`` fois le
    premier signale une colonne que les précédentes reproduisent déjà.

    Args:
        design: la matrice de plan, constante comprise.
        tol: le seuil relatif de détection.

    Raises:
        DataQualityError: si une colonne est nulle ou reproductible par les
            autres.
    """
    values = design.to_numpy(dtype=float)
    norms = np.linalg.norm(values, axis=0)
    empty = [str(c) for c, n in zip(design.columns, norms, strict=True) if n == 0.0]
    if empty:
        raise DataQualityError(f"régresseurs identiquement nuls : {', '.join(empty)}")

    _, upper, pivots = qr(values / norms, mode="economic", pivoting=True)
    diagonal = np.abs(np.diag(upper))
    weak = diagonal <= tol * diagonal[0]
    if bool(weak.any()):
        culprits = [str(design.columns[p]) for p, is_weak in zip(pivots, weak, strict=True) if is_weak]
        raise DataQualityError(
            "régresseurs colinéaires : "
            f"{', '.join(culprits)} se déduisent des autres colonnes "
            f"(seuil relatif {tol:g}). Retirez-les ou combinez-les avant de régresser."
        )


# --------------------------------------------------------------------------- #
# Choix du nombre de retards
# --------------------------------------------------------------------------- #


def newey_west_lags(n_obs: int, rule: LagRule = "stock_watson") -> int:
    r"""Rend le nombre de retards de l'estimateur HAC, par règle empirique.

    **Le problème.** L'estimateur de Newey et West somme les autocovariances des
    scores jusqu'à un retard :math:`L`. Ce nombre n'est pas donné par les
    données : il faut le choisir, et le choix change la statistique t.

    **L'intuition.** :math:`L` fixe jusqu'où on croit que la mémoire de la série
    porte. Le prendre trop court revient à ignorer une autocorrélation réelle,
    donc à garder un t trop grand. Le prendre trop long revient à estimer
    beaucoup d'autocovariances avec peu de couples d'observations, donc à rendre
    la variance estimée bruitée. Les deux règles ci-dessous font croître
    :math:`L` avec la taille d'échantillon, lentement.

    .. math::

        L_{NW} = \left\lfloor 4 \left(\frac{T}{100}\right)^{2/9} \right\rfloor
        \qquad
        L_{SW} = \left\lfloor 0{,}75 \; T^{1/3} \right\rfloor

    Args:
        n_obs: :math:`T`, le nombre d'observations de la régression.
        rule: ``"newey_west"`` pour la première formule, ``"stock_watson"`` pour
            la seconde.

    Returns:
        Le nombre entier de retards, toujours positif ou nul.

    Raises:
        InsufficientDataError: si ``n_obs`` est inférieur à 1.
        ConfigError: si la règle est inconnue.

    Example:
        Pour :math:`T = 1000`, la règle de Newey et West donne
        :math:`4 \times 10^{2/9} = 4 \times 1{,}6681 = 6{,}672`, donc 6 retards.
        Celle de Stock et Watson donne :math:`0{,}75 \times 10 = 7{,}5`, donc 7.
        Calculs à la main, vérifiés dans les tests.

    Note:
        Variables. :math:`T` est le nombre d'observations, :math:`L` le nombre de
        retards retenu, et :math:`\lfloor \cdot \rfloor` la partie entière par
        défaut.

        Hypothèses. Les deux règles supposent une autocorrélation qui décroît
        assez vite pour qu'un nombre de retards croissant en :math:`T^{1/3}` ou
        :math:`T^{2/9}` suffise. Elles ne valent pas sous mémoire longue.

        Provenance. La première vient de Newey et West (1994), « Automatic Lag
        Selection in Covariance Matrix Estimation », Review of Economic Studies
        61(4), et sert de défaut à plusieurs paquets économétriques. La seconde
        vient du manuel de Stock et Watson, « Introduction to Econometrics »,
        chapitre sur les séries temporelles.

        Limites. Ce sont des règles, pas des estimations. Aucune ne regarde la
        série. La procédure automatique d'Andrews (1991) choisit :math:`L` à
        partir de l'autocorrélation estimée, au prix d'une étape de plus et d'une
        sensibilité au modèle auxiliaire retenu.

        Alternatives. Andrews (1991), le noyau quadratique spectral, ou le choix
        d'un :math:`L` fixe justifié par la structure de la stratégie, par
        exemple la durée de recouvrement des positions.

        Choix du laboratoire. Stock et Watson par défaut, parce qu'elle se
        recalcule de tête et qu'elle est la règle du manuel que la plupart des
        lecteurs ont eu en main. Elle ne donne PAS systématiquement plus de
        retards que Newey et West, contrairement à ce qu'on lit souvent. Mesuré
        sur :math:`T` de 2 à 3000, elle en donne moins pour 128 valeurs de
        :math:`T`, toutes en deçà de 297, et davantage seulement à partir de
        :math:`T = 513`. Deux repères mesurés : à :math:`T = 100`, un peu plus de huit ans
        de données mensuelles, elle rend 3 retards contre 4 ;
        à :math:`T = 1000` elle en rend 7 contre 6. Un échantillon mensuel court
        reçoit donc un t un peu MOINS prudent qu'avec la règle de Newey et West,
        et le passage explicite de ``maxlags`` reste la façon de trancher.

        Vérification. Les deux formules se recalculent à la main en une ligne, et
        le test du module le fait sur :math:`T = 100` et :math:`T = 1000`.
    """
    if n_obs < 1:
        raise InsufficientDataError("le nombre de retards demande au moins une observation")
    if rule == "newey_west":
        raw = 4.0 * (n_obs / 100.0) ** (2.0 / 9.0)
    elif rule == "stock_watson":
        raw = 0.75 * n_obs ** (1.0 / 3.0)
    else:
        raise ConfigError(f"règle de retards inconnue : {rule!r}, attendu newey_west ou stock_watson")
    return int(np.floor(raw))


# --------------------------------------------------------------------------- #
# La régression factorielle
# --------------------------------------------------------------------------- #


def factor_regression(
    returns: pd.Series,
    factors: pd.Series | pd.DataFrame,
    risk_free: pd.Series | float | None = None,
    *,
    cov_type: CovType = "HAC",
    maxlags: int | None = None,
    lag_rule: LagRule = "stock_watson",
    annualize_alpha: bool = True,
    frequency: Frequency = Frequency.MONTHLY,
    collinearity_tol: float = DEFAULT_COLLINEARITY_TOL,
    hac_use_correction: bool = False,
) -> FactorRegressionResult:
    r"""Régresse un rendement sur des facteurs et rend alpha, bêtas et leurs t.

    **Le problème.** Une stratégie affiche un rendement moyen. La question
    utile n'est pas ce rendement, mais ce qu'il en reste une fois payé ce que
    des expositions connues auraient rapporté toutes seules.

    **L'intuition.** La régression sépare le rendement en deux parts : ce que
    les facteurs expliquent, et le reste. Le reste, mesuré par la constante, est
    l'alpha. Un alpha positif dit que la stratégie a rendu plus que son
    exposition ne le justifiait sur cet échantillon.

    .. math::

        r_{t} - r^{f}_{t}
        = \alpha + \sum_{k=1}^{K} \beta_{k} f_{k,t} + \varepsilon_{t}

    Args:
        returns: la série régressée, à la fréquence déclarée par ``frequency``.
        factors: un facteur ou un tableau de facteurs, supposés déjà en excès du
            taux sans risque.
        risk_free: le taux sans risque à retirer du rendement régressé. Sans
            valeur, ``returns`` est pris comme déjà en excès.
        cov_type: ``"HAC"`` pour Newey-West, ``"HC0"`` à ``"HC3"`` pour White,
            ``"nonrobust"`` pour la formule des moindres carrés ordinaires.
        maxlags: le nombre de retards HAC. Sans valeur, il vient de
            :func:`newey_west_lags` appliqué au nombre d'observations retenues.
        lag_rule: la règle de choix des retards quand ``maxlags`` est absent.
        annualize_alpha: multiplie l'alpha et son erreur type par le nombre de
            périodes par an. La statistique t ne bouge pas.
        frequency: la fréquence d'observation, qui fixe le facteur
            d'annualisation.
        collinearity_tol: le seuil de refus de colinéarité, voir
            :func:`_assert_full_rank`.
        hac_use_correction: applique la correction de petit échantillon de
            ``statsmodels`` à la matrice HAC. Faux par défaut, ce qui reproduit
            la formule de Newey et West (1987).

    Returns:
        Un :class:`FactorRegressionResult` gelé.

    Raises:
        ConfigError: type de covariance inconnu, retards négatifs, ou facteur
            portant le nom réservé de la constante.
        DataQualityError: régresseurs colinéaires ou index dupliqué.
        InsufficientDataError: moins d'observations que de paramètres à estimer.

    Example:
        Sur des données simulées à bêta connu de 1,2, la régression retrouve
        1,2 à moins de trois erreurs types. Le test du module le vérifie avec une
        graine fixée.

    Note:
        Variables. :math:`r_t` est le rendement de la stratégie, :math:`r^f_t` le
        taux sans risque, :math:`f_{k,t}` le rendement du facteur :math:`k`,
        :math:`\beta_k` son chargement, :math:`\alpha` la constante, et
        :math:`\varepsilon_t` le résidu.

        Hypothèses. Les moindres carrés donnent un estimateur sans biais si les
        facteurs sont exogènes et si la relation est linéaire. Ils ne demandent
        ni normalité ni variance constante pour cela. La variance estimée des
        coefficients, elle, demande beaucoup plus, d'où le recours à HAC.

        Provenance. Jensen (1968) pour l'alpha comme constante d'une régression
        de marché, Fama et French (1993) pour le modèle à trois facteurs. Puis
        Carhart (1997) pour le momentum et Fama et French (2015) pour les cinq
        facteurs. Newey et West (1987) pour la matrice de covariance.

        Limites. Trois, et aucune n'est réparable par le choix de la covariance.
        Le chargement est supposé constant sur tout l'échantillon, ce que
        contredit toute stratégie qui change d'exposition. Un facteur omis
        corrélé à la stratégie gonfle l'alpha. Et l'alpha se lit sur
        l'échantillon d'estimation, donc dans l'échantillon, ce qui n'annonce
        rien du suivant.

        Alternatives. Une régression par fenêtre glissante pour laisser bouger
        les chargements, voir :func:`rolling_beta`. Un modèle à changement de
        régime pour les faire dépendre d'un état. Une régression pondérée par
        l'inverse de la variance conditionnelle quand un modèle GARCH est déjà
        estimé.

        Choix du laboratoire. HAC par défaut, parce que les rendements de
        stratégies sont autocorrélés et hétéroscédastiques, et que la formule
        ordinaire se trompe alors toujours dans le sens qui flatte. Le coût est
        une perte de puissance quand il n'y a rien à corriger, ce qui est le bon
        sens de l'erreur.

        Vérification. Les coefficients et les t se comparent directement à
        ``statsmodels.OLS(...).fit(cov_type="HAC")``, et les tests du module le
        font sur les mêmes intrants.
    """
    if cov_type not in _COV_TYPES:
        raise ConfigError(f"type de covariance inconnu : {cov_type!r}, attendu l'un de {sorted(_COV_TYPES)}")
    if maxlags is not None and maxlags < 0:
        raise ConfigError("le nombre de retards ne peut pas être négatif")

    excess, aligned = _align(returns, factors, risk_free)
    if INTERCEPT_NAME in aligned.columns:
        raise ConfigError(f"un facteur porte le nom réservé de la constante : {INTERCEPT_NAME!r}")

    n_obs = len(excess)
    n_params = aligned.shape[1] + 1
    if n_obs < n_params + 1:
        raise InsufficientDataError(
            f"{n_obs} observations pour {n_params} paramètres : il en faut au moins {n_params + 1}"
        )

    design = aligned.copy()
    design.insert(0, INTERCEPT_NAME, 1.0)
    _assert_full_rank(design, collinearity_tol)

    lags: int | None = None
    fit_kwargs: dict[str, object] = {"cov_type": cov_type}
    if cov_type == "HAC":
        lags = maxlags if maxlags is not None else newey_west_lags(n_obs, lag_rule)
        fit_kwargs["cov_kwds"] = {"maxlags": lags, "use_correction": hac_use_correction}

    fitted_model = sm.OLS(excess, design).fit(**fit_kwargs)
    log.debug(
        "régression factorielle ajustée",
        extra={"n_obs": n_obs, "cov_type": cov_type, "maxlags": lags, "n_factors": aligned.shape[1]},
    )

    scale = frequency.periods_per_year if annualize_alpha else 1.0
    params = fitted_model.params
    stderr = fitted_model.bse
    tvalues = fitted_model.tvalues
    pvalues = fitted_model.pvalues
    names = [str(c) for c in aligned.columns]

    return FactorRegressionResult(
        alpha=float(params[INTERCEPT_NAME]) * scale,
        alpha_stderr=float(stderr[INTERCEPT_NAME]) * scale,
        alpha_tstat=float(tvalues[INTERCEPT_NAME]),
        alpha_pvalue=float(pvalues[INTERCEPT_NAME]),
        alpha_annualized=annualize_alpha,
        betas=params[names].astype(float).rename("beta"),
        beta_stderr=stderr[names].astype(float).rename("std_error"),
        beta_tstats=tvalues[names].astype(float).rename("t_stat"),
        beta_pvalues=pvalues[names].astype(float).rename("p_value"),
        r_squared=float(fitted_model.rsquared),
        adj_r_squared=float(fitted_model.rsquared_adj),
        n_obs=n_obs,
        cov_type=cov_type,
        maxlags=lags,
        frequency=frequency,
        factor_means=aligned.mean().astype(float).rename("factor_mean"),
        mean_excess_return=float(excess.mean()),
        residuals=fitted_model.resid.rename("residual"),
        fitted=fitted_model.fittedvalues.rename("fitted"),
    )


def attribution_table(result: FactorRegressionResult, *, with_total: bool = True) -> pd.DataFrame:
    r"""Rend le tableau des chargements et de ce que chacun a rapporté.

    **Le problème.** Un objet de résultat porte huit vecteurs. Un lecteur veut
    une page : quel chargement, avec quelle précision, et combien il a rapporté
    sur la période.

    **L'intuition.** La régression avec constante impose une identité comptable
    sur les moyennes. Le rendement moyen se décompose exactement en la somme des
    chargements multipliés par les moyennes de facteurs, plus l'alpha. Le
    tableau affiche cette décomposition.

    .. math::

        \bar{r} = \alpha + \sum_{k=1}^{K} \beta_{k} \bar{f}_{k}

    Args:
        result: le résultat rendu par :func:`factor_regression`.
        with_total: ajoute une ligne « total » qui somme la colonne des
            contributions. Un facteur portant ce nom est alors refusé.

    Returns:
        Un tableau indexé par ``alpha`` puis par facteur, aux colonnes
        ``loading``, ``std_error``, ``t_stat``, ``p_value``, ``factor_mean`` et
        ``contribution``. Les colonnes ``factor_mean`` et ``contribution`` sont à
        la même échelle que l'alpha du résultat, annualisée ou par période. Les
        chargements et leurs erreurs types ne sont jamais annualisés.

    Raises:
        ConfigError: si un facteur porte le nom de la ligne de total et que
            ``with_total`` est vrai.

    Example:
        Un alpha annualisé de 2,4 % et deux facteurs contribuant 5,1 % et
        -0,7 % donnent un total de 6,8 %, qui est le rendement moyen annualisé
        de la stratégie sur l'échantillon.

    Note:
        Variables. :math:`\bar{r}` est le rendement moyen en excès,
        :math:`\bar{f}_k` la moyenne du facteur :math:`k` sur le même
        échantillon.

        Hypothèses. L'identité tient exactement pour les moindres carrés avec
        constante, sur l'échantillon d'estimation, quelle que soit la matrice de
        covariance choisie. Elle ne tient plus si la constante est retirée.

        Provenance. Décomposition standard des moindres carrés. La présentation
        par contributions vient de l'attribution de performance factorielle,
        exposée notamment par Grinold et Kahn (2000).

        Limites. Une contribution mesure ce que le chargement a rapporté sur
        cette période, pas ce qu'il rapportera. Un facteur au rendement moyen
        négatif sur l'échantillon rend une contribution négative même si le
        chargement est délibéré et rémunéré à long terme. Le tableau n'attribue
        rien aux résidus, par construction : leur moyenne est nulle.

        Alternatives. Une attribution de Brinson pour un portefeuille décomposé
        par secteur, une attribution par période plutôt que par moyenne.

        Choix du laboratoire. Le tableau reste additif, sans pondération
        géométrique, parce que l'additivité est ce qui le rend contrôlable.
        L'annualisation multiplie chaque ligne par le même nombre, donc ne casse
        pas l'identité.

        Vérification. La somme de la colonne ``contribution`` est égale au
        rendement moyen en excès multiplié par le facteur d'annualisation, à la
        précision machine. Un test du module le vérifie à 1e-12.
    """
    scale = result.annualization_factor
    if with_total and TOTAL_ROW_NAME in result.factor_names:
        raise ConfigError(
            f"un facteur porte le nom réservé de la ligne de somme : {TOTAL_ROW_NAME!r}. "
            "Renommez-le, ou demandez le tableau sans total."
        )
    rows: dict[str, dict[str, float]] = {
        INTERCEPT_NAME: {
            "loading": result.alpha,
            "std_error": result.alpha_stderr,
            "t_stat": result.alpha_tstat,
            "p_value": result.alpha_pvalue,
            "factor_mean": float("nan"),
            "contribution": result.alpha,
        }
    }
    for name in result.factor_names:
        mean_k = float(result.factor_means[name]) * scale
        loading = float(result.betas[name])
        rows[name] = {
            "loading": loading,
            "std_error": float(result.beta_stderr[name]),
            "t_stat": float(result.beta_tstats[name]),
            "p_value": float(result.beta_pvalues[name]),
            "factor_mean": mean_k,
            "contribution": loading * mean_k,
        }

    table = pd.DataFrame.from_dict(rows, orient="index")
    table.index.name = "term"
    if with_total:
        total = pd.DataFrame(
            {
                "loading": [float("nan")],
                "std_error": [float("nan")],
                "t_stat": [float("nan")],
                "p_value": [float("nan")],
                "factor_mean": [float("nan")],
                "contribution": [float(table["contribution"].sum())],
            },
            index=pd.Index([TOTAL_ROW_NAME], name="term"),
        )
        table = pd.concat([table, total])
    return table


def residualize(
    returns: pd.Series,
    factors: pd.Series | pd.DataFrame,
    *,
    risk_free: pd.Series | float | None = None,
    add_intercept: bool = True,
    collinearity_tol: float = DEFAULT_COLLINEARITY_TOL,
) -> pd.Series:
    r"""Rend la part du rendement que les facteurs n'expliquent pas.

    **Le problème.** Une étude sur un signal veut souvent savoir ce qu'il
    apporte au-delà d'expositions déjà connues. Comparer directement le signal
    au marché mélange les deux.

    **L'intuition.** Projeter le rendement sur les facteurs, puis garder ce qui
    dépasse. Ce reste est par construction sans corrélation avec les facteurs
    inclus, sur l'échantillon d'estimation.

    .. math::

        e = y - X (X^{\top} X)^{-1} X^{\top} y = (I - P_X) \, y

    Args:
        returns: la série à neutraliser.
        factors: le ou les facteurs à retirer.
        risk_free: le taux sans risque à retirer du rendement avant projection.
        add_intercept: ajoute une constante, ce qui centre les résidus.
        collinearity_tol: le seuil de refus de colinéarité.

    Returns:
        Les résidus, indexés comme l'échantillon aligné.

    Raises:
        DataQualityError: régresseurs colinéaires.
        InsufficientDataError: moins d'observations que de paramètres.

    Example:
        Neutraliser un portefeuille de momentum du marché rend une série dont le
        bêta de marché est nul à la précision machine sur l'échantillon.

    Note:
        Variables. :math:`y` est le vecteur des rendements, :math:`X` la matrice
        des facteurs, :math:`P_X` le projecteur orthogonal sur son espace
        engendré, et :math:`e` le résidu.

        Hypothèses. Aucune au-delà du rang plein de :math:`X`. La neutralisation
        est une projection géométrique, elle ne suppose ni normalité ni
        stationnarité.

        Provenance. Le théorème de Frisch et Waugh (1933), complété par Lovell
        (1963), établit que régresser sur un sous-ensemble de régresseurs après
        avoir neutralisé les autres rend les mêmes coefficients que la régression
        complète. C'est ce résultat qui rend la neutralisation légitime comme
        diagnostic.

        Limites. L'orthogonalité vaut dans l'échantillon, et seulement lui. Un
        résidu neutre au marché sur 2010-2020 peut porter un bêta de 0,3 sur
        2021-2026. La neutralisation retire aussi le rendement rémunéré des
        facteurs, donc rend une série de rendement moyen plus faible.

        Alternatives. Neutraliser par construction du portefeuille, en imposant
        un bêta nul dans l'optimiseur, plutôt qu'après coup sur les rendements.
        Ce n'est pas la même chose : la seconde ne se négocie pas.

        Choix du laboratoire. La projection après coup sert au diagnostic, pas à
        la construction. Elle répond à la question « le signal apporte-t-il
        autre chose que ces facteurs ? » sans engager de position.

        Vérification. Le produit :math:`X^{\top} e` vaut zéro à la précision
        machine, et la moyenne des résidus vaut zéro quand la constante est
        incluse. Deux tests du module le vérifient.
    """
    excess, aligned = _align(returns, factors, risk_free)
    n_params = aligned.shape[1] + (1 if add_intercept else 0)
    if len(excess) < n_params + 1:
        raise InsufficientDataError(
            f"{len(excess)} observations pour {n_params} paramètres : projection impossible"
        )

    design = aligned.copy()
    if add_intercept:
        design.insert(0, INTERCEPT_NAME, 1.0)
    _assert_full_rank(design, collinearity_tol)
    residual = sm.OLS(excess, design).fit().resid
    return residual.rename(f"{excess.name}_residual")


# --------------------------------------------------------------------------- #
# Bêta, bêta glissant, bêta rétréci
# --------------------------------------------------------------------------- #


def _centered_sum_of_squares(values: np.ndarray, tol: float = DEFAULT_ZERO_VARIANCE_TOL) -> float:
    """Rend la somme des carrés centrés, et refuse une série constante.

    Le test est relatif, parce qu'une série constante ne rend pas zéro en double
    précision. La moyenne de dix valeurs égales à 0,01 s'écarte du dernier bit.
    La somme des carrés centrés ressort alors à 3,0e-35 au lieu de 0, mesuré, pour
    une somme brute de 1e-3. Comparer à zéro laisserait passer une division par du
    bruit d'arrondi.

    Args:
        values: la série, non centrée.
        tol: le seuil, rapporté à la somme des carrés bruts.

    Raises:
        DataQualityError: si la série est constante au sens de ce seuil.
    """
    centered = values - values.mean()
    sum_sq = float(centered @ centered)
    raw = float(values @ values)
    if raw == 0.0 or sum_sq <= tol * raw:
        raise DataQualityError(
            "la série de marché est constante : sa variance est nulle, le bêta n'est pas défini"
        )
    return sum_sq


def _beta_stderr(excess: pd.Series, market: pd.Series) -> float:
    r"""Rend l'erreur type ordinaire du bêta, sur deux séries déjà alignées.

    Elle suit la formule des moindres carrés simples, avec un dénominateur de
    :math:`T - 2` pour la variance résiduelle : la constante et la pente coûtent
    chacune un degré de liberté.

    .. math::

        s^{2}_{\hat\beta}
        = \frac{\sum_t \hat\varepsilon_t^{2} / (T - 2)}
               {\sum_t (r_{m,t} - \bar{r}_m)^{2}}

    Raises:
        DataQualityError: si le marché est constant.
        InsufficientDataError: moins de trois observations.
    """
    m = market.to_numpy(dtype=float)
    y = excess.to_numpy(dtype=float)
    centered_m = m - m.mean()
    sum_sq_m = _centered_sum_of_squares(m)
    slope = float((centered_m @ (y - y.mean())) / sum_sq_m)
    intercept = float(y.mean() - slope * m.mean())
    residual = y - intercept - slope * m
    dof = y.size - _SIMPLE_REGRESSION_PARAMS
    if dof <= 0:
        raise InsufficientDataError("l'erreur type du bêta demande au moins trois observations")
    sigma2 = float(residual @ residual) / dof
    return float(np.sqrt(sigma2 / sum_sq_m))


def beta(returns: pd.Series, market: pd.Series, *, ddof: int = 1) -> float:
    r"""Rend le bêta de marché, covariance sur variance.

    **Le problème.** Mesurer de combien un actif bouge quand le marché bouge
    d'un pour cent.

    **L'intuition.** C'est la pente de la droite des moindres carrés du
    rendement de l'actif sur celui du marché. La covariance dit comment les deux
    bougent ensemble, la variance du marché sert d'unité.

    .. math::

        \beta_i = \frac{\operatorname{Cov}(r_i, r_m)}{\operatorname{Var}(r_m)}
        = \frac{\sum_t (r_{i,t} - \bar{r}_i)(r_{m,t} - \bar{r}_m)}
               {\sum_t (r_{m,t} - \bar{r}_m)^2}

    Args:
        returns: le rendement de l'actif ou de la stratégie.
        market: le rendement du marché de référence.
        ddof: les degrés de liberté retirés dans la covariance et la variance.
            Ils s'annulent dans le rapport, la valeur rendue est donc la même
            pour ``ddof = 0`` et ``ddof = 1``. L'argument existe pour que la
            convention soit écrite, pas cachée.

    Returns:
        Le bêta, sans unité.

    Raises:
        ConfigError: si ``market`` porte plus d'une colonne.
        DataQualityError: si le marché est constant sur l'échantillon.
        InsufficientDataError: moins de deux observations communes.

    Example:
        Marché (1 %, -2 %, 3 %, 0 %, -1 %) et actif
        (2 %, -3 %, 5 %, 1 %, -2 %). La somme des produits centrés vaut 0,00244,
        la somme des carrés centrés du marché 0,00148. Le bêta vaut donc 61/37,
        soit 1,6486. Calcul refait à la main dans le test du module.

    Note:
        Variables. :math:`r_i` est le rendement de l'actif, :math:`r_m` celui du
        marché, et les barres notent les moyennes d'échantillon.

        Hypothèses. Une relation linéaire et un bêta constant sur la fenêtre. Le
        bêta n'a pas besoin de rendements normaux pour être défini, seulement
        d'une variance de marché finie et non nulle.

        Provenance. Sharpe (1964) et Lintner (1965) pour le modèle d'évaluation
        des actifs financiers, où le bêta est l'unique mesure de risque
        rémunérée.

        Limites. Le bêta mesuré sur données quotidiennes d'un titre peu liquide
        est biaisé vers le bas, parce que son prix réagit avec retard. Scholes et
        Williams (1977) puis Dimson (1979) corrigent ce biais en ajoutant des
        rendements de marché décalés.

        Alternatives. Le bêta de Dimson pour l'illiquidité, un bêta glissant pour
        laisser bouger l'exposition, un bêta rétréci pour la prévision, voir
        :func:`shrunk_beta`.

        Choix du laboratoire. La formule brute sert de référence contrôlable. Les
        corrections se demandent explicitement, jamais par défaut.

        Vérification. La valeur est la pente d'une régression simple, donc
        comparable à ``statsmodels.OLS``. Deux tests du module le font, l'un à la
        main, l'autre contre ``statsmodels``.
    """
    excess, aligned = _align(returns, market)
    market_column = _single_market(aligned)
    if len(excess) < _SIMPLE_REGRESSION_PARAMS:
        raise InsufficientDataError(
            f"{len(excess)} observation commune : le bêta en demande au moins {_SIMPLE_REGRESSION_PARAMS}"
        )
    m = market_column.to_numpy(dtype=float)
    y = excess.to_numpy(dtype=float)
    divisor = max(len(m) - ddof, 1)
    denominator = _centered_sum_of_squares(m) / divisor
    numerator = float((m - m.mean()) @ (y - y.mean())) / divisor
    return numerator / denominator


def rolling_beta(
    returns: pd.Series,
    market: pd.Series,
    window: int,
    *,
    min_periods: int | None = None,
    ddof: int = 1,
) -> pd.Series:
    r"""Rend le bêta estimé sur une fenêtre glissante de longueur fixe.

    **Le problème.** Un bêta unique sur vingt ans suppose une exposition qui n'a
    pas bougé. Peu de stratégies tiennent cette promesse.

    **L'intuition.** Recalculer la même formule sur les ``window`` dernières
    observations, à chaque date. La série obtenue montre quand l'exposition a
    changé.

    .. math::

        \beta_t(w) = \frac{\operatorname{Cov}_{[t-w+1,\,t]}(r_i, r_m)}
                          {\operatorname{Var}_{[t-w+1,\,t]}(r_m)}

    Args:
        returns: le rendement de l'actif.
        market: le rendement du marché.
        window: la longueur de la fenêtre, en nombre d'observations.
        min_periods: le nombre minimal d'observations valides pour rendre une
            valeur. Vaut ``window`` par défaut, donc aucune valeur partielle.
        ddof: degrés de liberté de la covariance et de la variance, qui
            s'annulent dans le rapport.

    Returns:
        La série des bêtas, de même index que l'échantillon aligné, avec des
        valeurs manquantes sur les premières dates.

    Raises:
        ConfigError: fenêtre inférieure à deux, ou marché à plusieurs colonnes.
        InsufficientDataError: échantillon plus court que la fenêtre.

    Example:
        Une fenêtre égale à la longueur de l'échantillon rend, à sa dernière
        date, exactement la valeur de :func:`beta`. Un test du module le
        vérifie.

    Note:
        Variables. :math:`w` est la longueur de fenêtre, :math:`t` la date
        d'observation.

        Hypothèses. Le bêta est supposé constant à l'intérieur de la fenêtre, et
        libre de bouger d'une fenêtre à l'autre. C'est une approximation par
        morceaux d'un paramètre qui varie.

        Provenance. Pratique courante depuis Fama et MacBeth (1973), qui
        estiment les bêtas sur une fenêtre antérieure avant de les utiliser.

        Limites. Le choix de la fenêtre décide du résultat. Une fenêtre courte
        rend un bêta bruité, une fenêtre longue rend un bêta en retard sur le
        changement réel. La fenêtre rectangulaire donne en plus le même poids à
        l'observation d'il y a un jour et à celle d'il y a trois ans.

        Alternatives. Une pondération exponentielle, un filtre de Kalman à bêta
        variable dans le temps, ou une régression sur variable d'état.

        Choix du laboratoire. La fenêtre rectangulaire est le repère, parce
        qu'elle se recalcule à la main sur n'importe quelle tranche. Les
        méthodes pondérées se comparent à elle.

        Vérification. Sur la fenêtre pleine, la valeur coïncide avec
        :func:`beta`. Sur une fenêtre quelconque, elle coïncide avec la pente
        d'une régression ``statsmodels`` sur la même tranche.
    """
    if window < _SIMPLE_REGRESSION_PARAMS:
        raise ConfigError(f"la fenêtre doit valoir au moins {_SIMPLE_REGRESSION_PARAMS} observations")
    excess, aligned = _align(returns, market)
    market_column = _single_market(aligned)
    if len(excess) < window:
        raise InsufficientDataError(f"{len(excess)} observations pour une fenêtre de {window}")
    periods = window if min_periods is None else min_periods
    covariance = excess.rolling(window, min_periods=periods).cov(market_column, ddof=ddof)
    variance = market_column.rolling(window, min_periods=periods).var(ddof=ddof)
    return (covariance / variance).rename("rolling_beta")


def rolling_alpha(
    returns: pd.Series,
    market: pd.Series,
    window: int,
    *,
    risk_free: pd.Series | float | None = None,
    min_periods: int | None = None,
    ddof: int = 1,
    annualize: bool = True,
    frequency: Frequency = Frequency.MONTHLY,
) -> pd.Series:
    r"""Rend l'alpha estimé sur une fenêtre glissante, à un seul facteur.

    **Le problème.** Savoir quand une stratégie a créé de la valeur au-delà de
    son exposition au marché, plutôt que sur toute la période d'un bloc.

    **L'intuition.** Sur chaque fenêtre, l'alpha est ce que la moyenne du
    rendement dépasse du bêta multiplié par la moyenne du marché. C'est
    exactement la constante d'une régression simple, écrite sans matrice.

    .. math::

        \alpha_t(w) = \bar{r}_{i,[t-w+1,\,t]}
        - \beta_t(w) \, \bar{r}_{m,[t-w+1,\,t]}

    Args:
        returns: le rendement de l'actif.
        market: le rendement du marché.
        window: la longueur de la fenêtre, en nombre d'observations.
        risk_free: le taux sans risque à retirer du rendement de l'actif.
        min_periods: le nombre minimal d'observations valides.
        ddof: degrés de liberté du bêta, sans effet sur sa valeur.
        annualize: multiplie l'alpha par le nombre de périodes par an.
        frequency: la fréquence d'observation, qui fixe ce nombre.

    Returns:
        La série des alphas, de même index que l'échantillon aligné.

    Raises:
        ConfigError: fenêtre inférieure à deux, ou marché à plusieurs colonnes.
        InsufficientDataError: échantillon plus court que la fenêtre.

    Example:
        Sur la dernière fenêtre, la valeur coïncide avec la constante d'une
        régression ``statsmodels`` sur la même tranche. Un test du module le
        vérifie.

    Note:
        Variables. Mêmes notations que :func:`rolling_beta`, la barre notant la
        moyenne sur la fenêtre.

        Hypothèses. Celles de la régression simple, sur chaque fenêtre. Aucune
        erreur type n'est rendue, parce qu'une erreur type sur fenêtres
        recouvrantes est presque toujours mal lue : les valeurs voisines
        partagent leurs observations et ne sont pas indépendantes.

        Provenance. Jensen (1968) pour la définition de l'alpha, appliquée par
        fenêtre.

        Limites. L'annualisation multiplie l'alpha par le nombre de périodes,
        ce qui suppose une composition arithmétique. Sur des rendements
        mensuels, l'écart avec la composition géométrique reste au second ordre
        et se creuse quand l'alpha est grand.

        Alternatives. La régression glissante multifactorielle, plus coûteuse et
        plus informative, obtenue en appelant :func:`factor_regression` sur
        chaque tranche.

        Choix du laboratoire. La forme fermée est retenue pour le coût : elle
        évite d'ajuster un modèle par date. Sa valeur est identique à celle de
        la régression, ce qu'un test vérifie.

        Vérification. Comparaison à ``statsmodels`` sur une tranche.
    """
    excess, aligned = _align(returns, market, risk_free)
    market_column = _single_market(aligned)
    betas = rolling_beta(excess, market_column, window, min_periods=min_periods, ddof=ddof)
    periods = window if min_periods is None else min_periods
    mean_asset = excess.rolling(window, min_periods=periods).mean()
    mean_market = market_column.rolling(window, min_periods=periods).mean()
    scale = frequency.periods_per_year if annualize else 1.0
    return ((mean_asset - betas * mean_market) * scale).rename("rolling_alpha")


def shrunk_beta(
    returns: pd.Series,
    market: pd.Series,
    *,
    prior: float = 1.0,
    weight: float | None = None,
    prior_variance: float | None = None,
    ddof: int = 1,
) -> float:
    r"""Rend le bêta rétréci vers une cible, à la Vasicek ou à la Blume.

    **Le problème.** Le bêta estimé sur un échantillon est bruité. Employé tel
    quel pour prévoir le bêta de la période suivante, il se trompe d'autant plus
    qu'il est extrême, parce qu'une valeur extrême doit une part de son extrémité
    au hasard de l'estimation.

    **L'intuition.** Tirer l'estimation vers une valeur centrale. Le bêta moyen
    d'un marché vaut un par construction, puisque le marché est la somme
    pondérée de ses titres. Un bêta estimé à 1,8 est donc plus probablement un
    bêta de 1,4 mal mesuré qu'un vrai 1,8, et le rétrécissement fait ce pari.

    .. math::

        \hat{\beta}^{\,shrunk} = w \, \hat{\beta} + (1 - w) \, \beta_{0}
        \qquad
        w_{Vasicek} = \frac{\sigma^{2}_{0}}
                           {\sigma^{2}_{0} + s^{2}_{\hat{\beta}}}

    Args:
        returns: le rendement de l'actif.
        market: le rendement du marché.
        prior: la cible :math:`\beta_0` du rétrécissement, un par défaut.
        weight: le poids :math:`w` accordé à l'estimation, entre 0 et 1. Donné,
            il l'emporte sur tout le reste.
        prior_variance: la variance :math:`\sigma^2_0` de la loi a priori des
            bêtas. Donnée sans ``weight``, elle déclenche la formule de Vasicek.
        ddof: degrés de liberté du bêta brut, sans effet sur sa valeur.

    Returns:
        Le bêta rétréci.

    Raises:
        ConfigError: poids hors de [0, 1], variance a priori négative, ou marché
            à plusieurs colonnes.

    Example:
        Un bêta brut de 61/37, soit 1,6486, rétréci vers 1 avec un poids de 0,5,
        donne (1,6486 + 1) / 2 = 1,3243. Calcul refait à la main dans le test du
        module.

    Note:
        Variables. :math:`\hat{\beta}` est le bêta estimé, :math:`\beta_0` la
        cible, :math:`s^2_{\hat\beta}` la variance d'échantillonnage de
        l'estimation, et :math:`\sigma^2_0` la variance des vrais bêtas dans la
        population.

        Hypothèses. Vasicek suppose une loi a priori normale sur les bêtas et une
        erreur d'estimation normale indépendante. Le poids qui en sort est la
        moyenne a posteriori exacte sous ces deux hypothèses.

        Provenance. Vasicek (1973), « A Note on Using Cross-Sectional
        Information in Bayesian Estimation of Security Betas », Journal of
        Finance 28(5). Blume (1975), « Betas and Their Regression Tendencies »,
        Journal of Finance 30(3), qui mesure sur données américaines que les
        bêtas extrêmes reviennent vers un d'une période à la suivante.

        Pourquoi cela prévoit mieux. L'estimation brute minimise l'erreur dans
        l'échantillon, pas hors échantillon. Une erreur quadratique de prévision
        se décompose en biais au carré plus variance. Rétrécir ajoute un peu de
        biais et retire beaucoup de variance, si bien que la somme baisse tant
        que l'estimation est bruitée. Le gain est donc d'autant plus grand que la
        fenêtre est courte, le titre volatil, ou le bêta extrême. Blume (1975) le
        mesure sur des portefeuilles américains de 1926 à 1968 ; le laboratoire
        ne l'a pas encore mesuré sur données canadiennes, et ce chiffre est donc
        non trouvé ici.

        Limites. La cible de un vaut pour un titre d'actions face à son propre
        marché. Elle ne vaut pas pour une stratégie neutre au marché, dont le
        vrai bêta est proche de zéro, et le rétrécissement vers un y ferait plus
        de mal que de bien. Le poids par défaut est une convention, pas une
        mesure.

        Alternatives. Le rétrécissement vers la moyenne du secteur plutôt que
        vers un, ou l'estimation hiérarchique complète. Une troisième voie est le
        bêta ajusté par régression des bêtas d'une période sur ceux de la
        précédente, qui est la forme originale de Blume.

        Choix du laboratoire. Le poids de Vasicek quand une variance a priori est
        disponible, parce qu'il rétrécit davantage les estimations les moins
        précises. À défaut, deux tiers, valeur déclarée et rapportée.

        Vérification. Avec ``weight = 1`` la fonction rend exactement le bêta
        brut, avec ``weight = 0`` exactement la cible, et le résultat reste
        toujours entre les deux. Trois tests du module le vérifient, dont un test
        de propriété.
    """
    if weight is not None and not (0.0 <= weight <= 1.0):
        raise ConfigError(f"le poids du rétrécissement doit être dans [0, 1], reçu {weight}")
    if prior_variance is not None and prior_variance < 0.0:
        raise ConfigError("la variance a priori ne peut pas être négative")

    excess, aligned = _align(returns, market)
    market_column = _single_market(aligned)
    raw = beta(excess, market_column, ddof=ddof)
    stderr = _beta_stderr(excess, market_column)

    if weight is not None:
        used = float(weight)
    elif prior_variance is not None:
        denominator = prior_variance + stderr**2
        used = 1.0 if denominator == 0.0 else float(prior_variance / denominator)
    else:
        used = DEFAULT_BLUME_WEIGHT
    return used * raw + (1.0 - used) * float(prior)

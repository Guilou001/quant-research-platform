r"""Les rendements : les convertir, les agréger dans le temps, les annualiser.

Ce module est la fondation de l'analytique. Tout ce qui suit dans le laboratoire,
volatilité, ratio de Sharpe, attribution, backtest, consomme une série produite
ici. Une erreur de convention à cet étage se propage partout, sans jamais lever
d'exception, et ressort sous la forme d'un ratio de Sharpe faux de dix pour cent.

**Deux conventions, et chacune est additive dans une seule dimension.**

Le rendement simple, la variation relative du prix d'une période à l'autre,
s'agrège dans la dimension des ACTIFS. Le rendement d'un portefeuille est la
moyenne pondérée des rendements simples de ses lignes, exactement :

.. math::

    r^{p}_t = \sum_{i=1}^{N} w_{i} \, r_{i,t}.

Cette égalité est fausse en rendement logarithmique. Le logarithme d'une somme
pondérée n'est pas la somme pondérée des logarithmes, et l'écart se chiffre.
Sur un portefeuille équipondéré de deux actifs à +50 % et -30 %, le rendement
simple du portefeuille vaut +10 %. La moyenne des logarithmes, elle, rend
:math:`\exp(0{,}5 \times (0{,}4055 - 0{,}3567)) - 1 = +2{,}47 \%`.

Le rendement logarithmique, le logarithme du rapport des prix, s'agrège dans la
dimension du TEMPS. La somme des rendements logarithmiques d'une suite de
périodes est le rendement logarithmique de la période entière, exactement :

.. math::

    r^{\log}_{1 \to T} = \sum_{t=1}^{T} r^{\log}_t
    = \ln\!\left(\frac{P_T}{P_0}\right).

Cette égalité est fausse en rendement simple, où la composition est un produit
et non une somme. C'est la raison pour laquelle
:func:`resample_returns` SOMME les rendements logarithmiques et COMPOSE les
rendements simples, et ne moyenne jamais ni les uns ni les autres. Moyenner des
rendements pour changer de fréquence est l'erreur la plus fréquente de tout ce
module, et elle est silencieuse.

**L'exemple à retenir, +10 % puis -10 %.**

Un placement de 100 $ qui gagne 10 % puis en perd 10 % vaut
:math:`100 \times 1{,}10 \times 0{,}90 = 99` dollars. La perte est de 1 %, alors
que la moyenne arithmétique des deux rendements simples vaut exactement zéro.

En logarithme, :math:`\ln(1{,}10) = +0{,}09531` et :math:`\ln(0{,}90) = -0{,}10536`
somment à :math:`-0{,}01005`, dont l'exponentielle rend 0,99, soit la richesse
finale au cent près. La somme des logarithmes ne se trompe pas ; la moyenne des
rendements simples, si.

**Pourquoi la moyenne arithmétique dépasse toujours la géométrique.**

L'inégalité arithmético-géométrique dit que, pour des facteurs de croissance
:math:`1 + r_t` tous positifs, la moyenne arithmétique domine la moyenne
géométrique, avec égalité si et seulement si tous les rendements sont égaux.
L'écart n'est pas un détail de présentation : il croît avec la dispersion.

Un développement au second ordre de :math:`\ln(1 + r)` autour de la moyenne donne
l'approximation classique :

.. math::

    \mu_{g} \approx \mu_{a} - \frac{\sigma^{2}}{2}.

où :math:`\mu_a` est la moyenne arithmétique des rendements simples,
:math:`\mu_g` leur moyenne géométrique et :math:`\sigma^2` leur variance, les
trois mesurés à la MÊME fréquence. Concrètement, une stratégie de 8 % de moyenne
arithmétique annuelle et de 20 % de volatilité ne compose qu'à environ
:math:`8 - 0{,}20^2 / 2 = 6` pour cent par an. Les deux points d'écart ne sont
pas un coût, ce sont deux façons de résumer la même série.

Conséquence opérationnelle. La moyenne arithmétique est l'estimateur du rendement
espéré d'UNE période, celui qui entre dans une optimisation moyenne-variance. La
moyenne géométrique est le taux de croissance réellement encaissé par un
investisseur qui ne retire rien. Publier l'une en appelant l'autre flatte la
stratégie d'environ :math:`\sigma^2 / 2`, et ce module oblige à choisir.

**Pourquoi le CAGR d'un backtest court est fragile.**

Le taux de croissance annuel composé ne dépend que de deux nombres, la richesse
de départ et la richesse d'arrivée, et il ignore tout ce qui se passe entre les
deux. Trois défauts en découlent.

D'abord, sa sensibilité aux bornes. Déplacer la date de fin d'un seul mois
baissier sur un backtest de trois ans change le CAGR de plusieurs points, alors
que la stratégie n'a pas changé.

Ensuite, son incertitude statistique. L'erreur type d'un rendement moyen annuel
décroît comme :math:`\sigma / \sqrt{T}` avec :math:`T` en années. À 20 % de
volatilité annuelle sur trois ans, elle vaut :math:`0{,}20 / \sqrt{3} = 11{,}5`
points de pourcentage. Un CAGR mesuré à 12 % sur trois ans n'est donc pas
distinguable de zéro : l'intervalle à 95 %, soit 12 plus ou moins 1,96 fois
11,5, couvre de -10,6 % à +34,6 %.

Enfin, sa dépendance à l'ordre inverse de celle qu'on croit : le CAGR est
invariant à la permutation des rendements, si bien que deux stratégies de risques
opposés peuvent le partager. C'est pourquoi aucun verdict du laboratoire ne
repose sur un CAGR seul.

Note:
    Statut des chiffres cités dans ce module : les exemples numériques sont
    MODÉLISÉS, calculés depuis les formules ci-dessus. Les valeurs 0,09531 et
    -0,10536 sont recopiées de la docstring de
    :class:`quantlab.core.types.ReturnKind`.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd

from quantlab.core.errors import DataQualityError, InsufficientDataError
from quantlab.core.logging import get_logger
from quantlab.core.types import Frequency, ReturnKind

__all__ = [
    "align_returns",
    "arithmetic_mean_return",
    "cagr",
    "compound",
    "cumulative_wealth",
    "excess_returns",
    "geometric_mean_return",
    "log_to_simple",
    "overnight_intraday_split",
    "resample_returns",
    "simple_to_log",
    "to_prices",
    "to_returns",
]

_LOG = get_logger(__name__)

#: Le paramètre de type des fonctions qui conservent la forme de leur entrée.
#: Une ``Series`` rend une ``Series``, un ``DataFrame`` rend un ``DataFrame``,
#: et la signature le dit au lieu de le laisser deviner.
type PandasObj = pd.Series | pd.DataFrame

#: Nombre de jours de l'année julienne moyenne, utilisé pour comparer un pas
#: d'observation mesuré à la durée d'une période cible.
DAYS_PER_YEAR = 365.25

#: Tolérance par défaut du garde-fou de rééchantillonnage. Un pas médian
#: supérieur à 1,5 fois la durée de la période cible signale un passage vers une
#: fréquence PLUS FINE, que ce module refuse.
DEFAULT_UPSAMPLE_TOLERANCE = 1.5


def _validate[T: (pd.Series, pd.DataFrame)](data: T, *, name: str, minimum: int = 1) -> None:
    """Refuse une entrée qui rendrait le calcul aval faux en silence.

    Args:
        data: la série ou le tableau à contrôler.
        name: le nom de l'argument, pour le message d'erreur.
        minimum: nombre d'observations exigé.

    Raises:
        TypeError: si l'objet n'est ni une ``Series`` ni un ``DataFrame``.
        InsufficientDataError: si l'objet porte moins de ``minimum`` lignes.
        DataQualityError: si l'index porte des doublons ou n'est pas croissant.

    Note:
        Un index non trié fait cumuler les rendements dans le désordre, ce qui
        laisse la richesse finale correcte mais toute mesure de creux fausse. Le
        portefeuille a déjà rencontré ce défaut sur des horodatages mal lus.
    """
    if not isinstance(data, pd.Series | pd.DataFrame):
        raise TypeError(f"{name} doit être une Series ou un DataFrame pandas, reçu {type(data)!r}")
    if len(data) < minimum:
        raise InsufficientDataError(f"{name} porte {len(data)} observation(s), il en faut au moins {minimum}")
    index = data.index
    if index.has_duplicates:
        raise DataQualityError(f"l'index de {name} porte des horodatages en double")
    if len(index) > 1 and not index.is_monotonic_increasing:
        raise DataQualityError(f"l'index de {name} n'est pas croissant")


def _periods_per_year(frequency: Frequency, periods_per_year: float | None) -> float:
    """Rend le facteur d'annualisation retenu, injecté ou conventionnel.

    Args:
        frequency: la fréquence d'observation de la série.
        periods_per_year: facteur MESURÉ à utiliser à la place de la convention,
            typiquement celui de
            :func:`quantlab.core.calendars.annualization_factor`.

    Returns:
        Le nombre de périodes par an.

    Raises:
        ValueError: si le facteur injecté n'est pas strictement positif.
    """
    if periods_per_year is None:
        return frequency.periods_per_year
    if periods_per_year <= 0:
        raise ValueError("periods_per_year doit être strictement positif")
    return float(periods_per_year)


def to_returns[T: (pd.Series, pd.DataFrame)](
    prices: T,
    kind: ReturnKind = ReturnKind.SIMPLE,
    *,
    dropna: bool = True,
) -> T:
    r"""Rend les rendements d'une série de prix, simples ou logarithmiques.

    **Le problème.** Un prix n'est pas comparable d'un actif à l'autre ni d'une
    époque à l'autre. Le rendement l'est, parce qu'il est sans dimension.

    **L'intuition.** On divise le prix d'aujourd'hui par celui d'hier. Le
    quotient dit combien vaut un dollar investi la veille ; on lui retire 1 pour
    obtenir la variation, ou on en prend le logarithme pour la rendre additive.

    .. math::

        r_t = \frac{P_t}{P_{t-1}} - 1
        \qquad\text{ou}\qquad
        r^{\log}_t = \ln\!\left(\frac{P_t}{P_{t-1}}\right) = \ln(1 + r_t).

    où :math:`P_t` est le prix observé en fin de période :math:`t`, et
    :math:`r_t` le rendement de la période allant de :math:`t-1` à :math:`t`.

    **Hypothèses.** Les prix sont déjà ajustés des actions de société, division
    et dividende compris. Un prix non ajusté fabrique un faux rendement de -50 %
    le jour d'une division par deux. Les prix sont strictement positifs, ce qui
    est vérifié. L'index est trié et sans doublon, ce qui est vérifié.

    **Provenance.** Convention universelle, exposée par exemple dans Campbell,
    Lo et MacKinlay, « The Econometrics of Financial Markets » (1997),
    chapitre 1, qui pose les deux définitions et la propriété d'additivité
    temporelle du rendement continûment composé.

    **Limites.** Le premier rendement est indéfini, et cette fonction le retire
    par défaut : la série rendue est plus courte d'une observation que celle des
    prix. Un trou intérieur dans les prix fabrique deux rendements manquants,
    et ``dropna`` les supprimerait sans le dire ; nettoyer les prix en amont
    reste la bonne réponse.

    **Alternatives.** ``pandas.Series.pct_change`` fait le calcul simple, avec
    une gestion des manquants qui a changé de comportement par défaut entre
    versions. Le quotient explicite retenu ici ne dépend d'aucune de ces
    valeurs par défaut.

    **Pourquoi cette méthode.** Une seule fonction rend les deux conventions,
    déclarées par un ``ReturnKind``, ce qui rend impossible d'oublier laquelle
    circule dans la suite du calcul.

    **Comment vérifier.** L'identité :math:`r^{\log} = \ln(1 + r)` doit tenir à
    la précision machine sur les deux sorties, et
    ``to_prices(to_returns(p), initial=p.iloc[0])`` doit reproduire ``p`` privé
    de sa première ligne.

    Args:
        prices: série ou tableau de prix, indexé par le temps, colonnes = actifs.
        kind: convention de rendement voulue.
        dropna: retire les lignes entièrement manquantes, dont la première.

    Returns:
        Les rendements, du même type que l'entrée.

    Raises:
        InsufficientDataError: si moins de deux prix sont fournis.
        DataQualityError: si un prix est nul ou négatif, ou si l'index est
            invalide.

    Example:
        >>> import pandas as pd
        >>> p = pd.Series([100.0, 110.0, 99.0], index=pd.date_range("2020-01-31", periods=3, freq="ME"))
        >>> to_returns(p).round(4).tolist()
        [0.1, -0.1]
    """
    _validate(prices, name="prices", minimum=2)
    non_positive = np.asarray(prices <= 0)
    if non_positive.any():
        raise DataQualityError(
            "les prix doivent être strictement positifs ; "
            f"{int(non_positive.sum())} valeur(s) nulle(s) ou négative(s) trouvée(s)"
        )
    ratio = prices / prices.shift(1)
    out = np.log(ratio) if kind is ReturnKind.LOG else ratio - 1.0
    if dropna:
        out = out.dropna() if isinstance(out, pd.Series) else out.dropna(how="all")
    return out


def to_prices[T: (pd.Series, pd.DataFrame)](
    returns: T,
    initial: float = 1.0,
    kind: ReturnKind = ReturnKind.SIMPLE,
) -> T:
    r"""Rend l'indice de richesse cumulée engendré par une série de rendements.

    **Le problème.** Une suite de rendements ne se lit pas. La richesse d'un
    dollar investi au départ se lit, et c'est elle qui porte les creux, les
    sommets et la durée de récupération.

    **L'intuition.** On empile les facteurs de croissance. Chaque période
    multiplie la richesse par :math:`1 + r_t`, donc la richesse finale est le
    produit de ces facteurs, ou l'exponentielle de la somme des logarithmes.

    .. math::

        V_t = V_0 \prod_{s=1}^{t} (1 + r_s)
        \qquad\text{ou}\qquad
        V_t = V_0 \exp\!\left(\sum_{s=1}^{t} r^{\log}_s\right).

    où :math:`V_0` est la richesse de départ et :math:`r_s` le rendement de la
    période :math:`s`, exprimé dans la convention ``kind``.

    **Hypothèses.** Aucun apport ni retrait en cours de route. Les rendements
    sont nets de ce qu'on veut voir déduit, ce module n'ajoutant aucun coût.

    **Provenance.** Définition de l'indice de richesse, standard depuis Fisher
    et Lorie (1964), « Rates of Return on Investments in Common Stocks »,
    Journal of Business.

    **Limites.** L'indice ne dit rien de la trajectoire à l'intérieur d'une
    période. Un creux intrajournalier de 30 % est invisible sur un indice
    quotidien, et le creux mesuré sur des données mensuelles sous-estime
    toujours le creux réel.

    **Alternatives.** ``(1 + r).cumprod()`` fait la même chose en une ligne. La
    fonction ajoute la gestion de la convention logarithmique, la richesse de
    départ et le contrôle d'index.

    **Pourquoi cette méthode.** Le produit cumulé traite la faillite sans rien
    signaler d'anormal : un rendement de -100 % annule la richesse et l'y
    maintient. Mesuré le 2026-09-01, la route équivalente par
    ``exp(log1p(r).cumsum())`` rend la même richesse nulle, mais émet un
    avertissement ``divide by zero encountered in log1p``, qui devient une
    erreur dès qu'un pipeline promeut les avertissements. Le produit n'en émet
    aucun.

    **Comment vérifier.** La dernière valeur doit égaler
    ``initial * (1 + compound(returns))`` à la précision machine, y compris sur
    une série entièrement manquante, où les deux rendent ``NaN``.

    Args:
        returns: série ou tableau de rendements.
        initial: richesse de départ, 1,0 par défaut, soit un indice base 1.
        kind: convention des rendements fournis.

    Returns:
        L'indice de richesse, indexé comme ``returns``. La date de départ n'est
        PAS ajoutée : la première valeur rendue est déjà la richesse après le
        premier rendement.

    Raises:
        InsufficientDataError: si la série est vide.
        DataQualityError: si l'index est invalide.

    Example:
        >>> import pandas as pd
        >>> r = pd.Series([0.10, -0.10], index=pd.date_range("2020-01-31", periods=2, freq="ME"))
        >>> to_prices(r, initial=100.0).round(2).tolist()
        [110.0, 99.0]
    """
    _validate(returns, name="returns", minimum=1)
    if kind is ReturnKind.LOG:
        return initial * np.exp(returns.cumsum())
    return initial * (1.0 + returns).cumprod()


def simple_to_log(r: PandasObj | float) -> PandasObj | float:
    r"""Convertit un rendement simple en rendement logarithmique.

    .. math::

        r^{\log} = \ln(1 + r), \qquad r > -1.

    La garde :math:`r > -1` n'est pas une précaution de programmation, c'est le
    domaine de définition. Un rendement de -100 % détruit la totalité du capital,
    et le logarithme du facteur de croissance nul vaut moins l'infini. La
    faillite se représente en rendement simple, jamais en logarithme.

    Args:
        r: rendement simple, scalaire, série ou tableau.

    Returns:
        Le rendement logarithmique, du même type que l'entrée.

    Raises:
        DataQualityError: si un rendement vaut -1 ou moins.

    Note:
        Le calcul passe par ``numpy.log1p``, qui garde sa précision pour les
        petits rendements là où ``log(1 + r)`` la perd. Sur un rendement de
        1e-9, l'écart relatif entre les deux écritures atteint l'ordre de 1e-8.

    Example:
        >>> round(float(simple_to_log(0.10)), 5)
        0.09531
    """
    values = np.asarray(r, dtype=float)
    if np.any(values <= -1.0):
        raise DataQualityError(
            "un rendement simple de -100 % ou moins n'a pas de logarithme ; "
            "garder la convention simple pour représenter une faillite"
        )
    out = np.log1p(values)
    if isinstance(r, pd.Series):
        return pd.Series(out, index=r.index, name=r.name)
    if isinstance(r, pd.DataFrame):
        return pd.DataFrame(out, index=r.index, columns=r.columns)
    return float(out)


def log_to_simple(r: PandasObj | float) -> PandasObj | float:
    r"""Convertit un rendement logarithmique en rendement simple.

    .. math::

        r = \exp(r^{\log}) - 1.

    Args:
        r: rendement logarithmique, scalaire, série ou tableau.

    Returns:
        Le rendement simple, du même type que l'entrée.

    Note:
        Le calcul passe par ``numpy.expm1``, réciproque exacte de ``log1p``, ce
        qui rend l'aller-retour stable jusqu'à la précision machine. Aucune
        garde n'est nécessaire ici : l'image de :math:`\exp` est strictement
        positive, donc le rendement simple rendu est toujours supérieur à -1.

    Example:
        >>> round(float(log_to_simple(0.09531017980432486)), 10)
        0.1
    """
    out = np.expm1(np.asarray(r, dtype=float))
    if isinstance(r, pd.Series):
        return pd.Series(out, index=r.index, name=r.name)
    if isinstance(r, pd.DataFrame):
        return pd.DataFrame(out, index=r.index, columns=r.columns)
    return float(out)


def compound(
    returns: pd.Series | pd.DataFrame,
    kind: ReturnKind = ReturnKind.SIMPLE,
    *,
    skipna: bool = True,
) -> float | pd.Series:
    r"""Rend le rendement total de la période entière, dans la convention donnée.

    **Le problème.** Additionner des rendements simples pour résumer une période
    est faux, et l'erreur croît avec la longueur de la période. Sur douze mois à
    +5 %, la somme annonce +60 % là où la composition rend +79,6 %.

    **L'intuition.** Composer, c'est empiler des facteurs multiplicatifs. On
    multiplie les :math:`1 + r_t` et on retire 1 à la fin.

    .. math::

        R_{1 \to T} = \prod_{t=1}^{T} (1 + r_t) - 1
        \qquad\text{ou}\qquad
        R^{\log}_{1 \to T} = \sum_{t=1}^{T} r^{\log}_t.

    où :math:`T` est le nombre de périodes et :math:`r_t` le rendement de la
    période :math:`t`.

    **Hypothèses.** Les rendements sont consécutifs et sans recouvrement. Les
    manquants sont traités comme des périodes à rendement nul quand
    ``skipna`` vaut ``True``, ce qui est un choix et non une neutralité. Une
    série ENTIÈREMENT manquante fait exception et rend ``NaN``. Elle ne porte
    aucune observation, donc aucun rendement d'ensemble. Sans cette exception,
    le produit vide vaudrait 1 et la fonction annoncerait 0 %, là où
    :func:`to_prices` rend ``NaN`` sur la même entrée.

    **Provenance.** Définition du rendement composé, présente dans toute la
    littérature de mesure de performance, notamment Bacon, « Practical
    Portfolio Performance Measurement and Attribution » (2019), chapitre 2.

    **Limites.** Le résultat est un scalaire par colonne, donc il perd toute
    information de trajectoire. Deux séries de creux très différents partagent
    le même rendement composé.

    **Alternatives.** Passer par la somme des logarithmes puis exponentier donne
    le même nombre. Sur un rendement de -100 %, mesuré le 2026-09-01, cette
    route rend bien -1 mais émet un avertissement de division par zéro, là où le
    produit reste silencieux.

    **Pourquoi cette méthode.** Le produit couvre tout le domaine, faillite
    comprise, sans avertissement, et il rend la même valeur que la richesse
    finale de :func:`to_prices` par construction.

    **Comment vérifier.** ``1 + compound(r)`` doit égaler
    ``to_prices(r).iloc[-1]`` avec ``initial=1``, et pour des rendements
    logarithmiques la somme doit égaler ``log(prix_final / prix_initial)``.

    Args:
        returns: série ou tableau de rendements.
        kind: convention des rendements fournis. La sortie est dans la MÊME
            convention : un total simple pour des entrées simples, un total
            logarithmique pour des entrées logarithmiques.
        skipna: ignore les manquants. Sinon un seul manquant rend ``NaN``.

    Returns:
        Un flottant pour une série, une ``Series`` indexée par colonne pour un
        tableau. ``NaN`` pour une série ou une colonne sans aucune observation
        valide, quelle que soit la valeur de ``skipna``.

    Raises:
        InsufficientDataError: si la série est vide.

    Example:
        >>> import pandas as pd
        >>> r = pd.Series([0.10, -0.10], index=pd.date_range("2020-01-31", periods=2, freq="ME"))
        >>> round(float(compound(r)), 10)
        -0.01
    """
    _validate(returns, name="returns", minimum=1)
    if kind is ReturnKind.LOG:
        total = returns.sum(skipna=skipna, min_count=1)
    else:
        total = (1.0 + returns).prod(skipna=skipna, min_count=1) - 1.0
    return float(total) if isinstance(returns, pd.Series) else total


def _guard_downsampling(
    index: pd.Index,
    to_frequency: Frequency,
    *,
    periods_per_year: float,
    upsample_tolerance: float,
) -> None:
    """Refuse un rééchantillonnage vers une fréquence plus fine que la source.

    Args:
        index: l'index temporel de la série.
        to_frequency: la fréquence visée, pour le message d'erreur.
        periods_per_year: le nombre de périodes par an de la fréquence visée.
        upsample_tolerance: multiple du pas cible au-delà duquel le pas mesuré
            est déclaré trop grossier.

    Raises:
        InsufficientDataError: si le pas médian observé dépasse la durée de la
            période cible multipliée par la tolérance.

    Note:
        Passer de mensuel à quotidien fabriquerait un rendement par mois et des
        manquants partout ailleurs, sans lever d'erreur. Le contrôle mesure le
        pas médian réel plutôt que de faire confiance à une fréquence déclarée.

        Un index à fuseau horaire est d'abord ramené en temps universel puis
        privé de son fuseau. Sans cette étape, numpy émet « no explicit
        representation of timezones available for np.datetime64 », mesuré le
        2026-09-01, ce qui casse tout appelant qui promeut les avertissements
        en erreurs. Le passage par le temps universel garde les durées réelles,
        y compris au travers d'un changement d'heure.
    """
    if len(index) < 2:
        return
    naive = index.tz_convert("UTC").tz_localize(None) if getattr(index, "tz", None) is not None else index
    spacings = np.diff(naive.to_numpy().astype("datetime64[s]").astype("float64")) / 86400.0
    observed = float(np.median(spacings))
    target = DAYS_PER_YEAR / periods_per_year
    if observed > target * upsample_tolerance:
        raise InsufficientDataError(
            f"pas médian observé de {observed:.2f} jour(s) contre {target:.2f} pour "
            f"{to_frequency.value} : agréger vers une fréquence plus fine est refusé"
        )


def resample_returns[T: (pd.Series, pd.DataFrame)](
    returns: T,
    to_frequency: Frequency,
    kind: ReturnKind = ReturnKind.SIMPLE,
    *,
    upsample_tolerance: float = DEFAULT_UPSAMPLE_TOLERANCE,
    periods_per_year: float | None = None,
) -> T:
    r"""Agrège des rendements vers une fréquence plus grossière, sans moyenner.

    **Le problème.** Comparer une stratégie quotidienne à un indice mensuel
    demande de ramener les deux à la même fréquence. La tentation est de
    moyenner les rendements du mois, et c'est faux : la moyenne de +10 % et
    -10 % vaut zéro alors que le mois a perdu 1 %.

    **L'intuition.** Agréger dans le temps, c'est composer. En logarithme la
    composition est une somme, en simple c'est un produit de facteurs.

    .. math::

        R^{simple}_{mois} = \prod_{t \in mois} (1 + r_t) - 1
        \qquad
        R^{\log}_{mois} = \sum_{t \in mois} r^{\log}_t.

    où :math:`t` parcourt les périodes fines contenues dans la période
    grossière.

    **Hypothèses.** Les bornes de période sont celles de pandas, fin de mois
    calendaire pour ``ME``, vendredi pour ``W-FRI``. Une période partielle en
    début ou en fin d'échantillon est agrégée telle quelle, donc le premier et
    le dernier point peuvent couvrir moins de jours que les autres.

    **Provenance.** Convention d'agrégation temporelle des rendements, Campbell,
    Lo et MacKinlay (1997), chapitre 1, section 1.4.

    **Limites.** L'agrégation détruit l'information de fréquence fine, donc la
    volatilité mensuelle mesurée ainsi n'égale pas la volatilité quotidienne
    annualisée dès que les rendements sont autocorrélés. C'est d'ailleurs le
    test le plus simple de l'hypothèse de racine unitaire, et il échoue souvent.

    **Alternatives.** ``resample().last()`` sur les PRIX puis conversion en
    rendements donne le même résultat quand la série de prix est disponible, et
    reste préférable dans ce cas parce qu'elle ne dépend d'aucune convention de
    manquants.

    **Pourquoi cette méthode.** L'entrée du laboratoire est souvent une série de
    rendements déjà nette de coûts, dont les prix n'existent plus.

    **Comment vérifier.** Composer les rendements mensuels rendus doit redonner
    exactement le rendement composé de la série quotidienne d'origine, à la
    précision machine, dès lors que les périodes couvrent tout l'échantillon.

    Args:
        returns: série ou tableau de rendements, indexé par un ``DatetimeIndex``.
        to_frequency: la fréquence visée, plus grossière que celle de l'entrée.
        kind: convention des rendements fournis, conservée en sortie.
        upsample_tolerance: multiple du pas cible au-delà duquel l'agrégation
            est refusée. Valeur par défaut 1,5, soit un pas observé une fois et
            demie plus long que la période visée.
        periods_per_year: facteur mesuré remplaçant la convention, utilisé par
            le seul garde-fou.

    Returns:
        Les rendements agrégés, indexés en fin de période.

    Raises:
        DataQualityError: si l'index n'est pas un ``DatetimeIndex``.
        InsufficientDataError: si la série est vide ou si la fréquence visée est
            plus fine que celle de l'entrée.

    Example:
        >>> import pandas as pd
        >>> idx = pd.date_range("2020-01-31", periods=12, freq="ME")
        >>> r = pd.Series([0.01] * 12, index=idx)
        >>> round(float(resample_returns(r, Frequency.ANNUAL).iloc[0]), 10)
        0.1268250301
    """
    _validate(returns, name="returns", minimum=1)
    if not isinstance(returns.index, pd.DatetimeIndex):
        raise DataQualityError("le rééchantillonnage exige un index de type DatetimeIndex")
    factor = _periods_per_year(to_frequency, periods_per_year)
    _guard_downsampling(
        returns.index,
        to_frequency,
        periods_per_year=factor,
        upsample_tolerance=upsample_tolerance,
    )
    grouped = returns.resample(to_frequency.pandas_alias)
    if kind is ReturnKind.LOG:
        return grouped.sum(min_count=1)
    return grouped.apply(lambda block: (1.0 + block).prod(min_count=1) - 1.0)


def cumulative_wealth[T: (pd.Series, pd.DataFrame)](
    returns: T,
    initial: float = 1.0,
    kind: ReturnKind = ReturnKind.SIMPLE,
) -> T:
    """Rend la richesse cumulée, synonyme lisible de :func:`to_prices`.

    Le nom existe parce que les deux lectures d'un même objet ne servent pas au
    même usage. ``to_prices`` reconstruit une série de prix à partir de
    rendements ; ``cumulative_wealth`` répond à la question « combien vaut un
    dollar investi au départ ». Le calcul est le même.

    Args:
        returns: série ou tableau de rendements.
        initial: richesse de départ, 1,0 par défaut.
        kind: convention des rendements fournis.

    Returns:
        L'indice de richesse, indexé comme ``returns``.

    Example:
        >>> import pandas as pd
        >>> r = pd.Series([0.10, -1.00], index=pd.date_range("2020-01-31", periods=2, freq="ME"))
        >>> cumulative_wealth(r).tolist()
        [1.1, 0.0]
    """
    return to_prices(returns, initial=initial, kind=kind)


def cagr(
    returns: pd.Series | pd.DataFrame,
    frequency: Frequency,
    periods: int | None = None,
    kind: ReturnKind = ReturnKind.SIMPLE,
    *,
    periods_per_year: float | None = None,
) -> float | pd.Series:
    r"""Rend le taux de croissance annuel composé de la série.

    **Le problème.** Un rendement total de 33,1 % ne dit pas s'il a été obtenu
    en trois ans ou en trois mois. Le ramener à un rythme annuel le rend
    comparable.

    **L'intuition.** On cherche le taux constant qui, appliqué chaque année,
    mène de la richesse de départ à la richesse d'arrivée dans le même temps.

    .. math::

        CAGR = \left(\frac{V_T}{V_0}\right)^{1/T} - 1,
        \qquad T = \frac{n}{N}.

    où :math:`V_T / V_0` est le facteur de croissance total, :math:`n` le nombre
    de périodes observées et :math:`N` le nombre de périodes par an, si bien que
    :math:`T` est une durée en ANNÉES.

    **Hypothèses.** Les périodes sont régulières, ce qui rend :math:`n / N`
    correct. Sur une série trouée, passer ``periods`` explicitement ou mesurer
    la durée calendaire est la seule voie juste.

    **Provenance.** Définition du taux de croissance annuel composé, identique à
    celle du GIPS pour un rendement annualisé sur plus d'un an.

    **Limites.** Fragilité aux bornes, incertitude statistique large sur les
    échantillons courts, invariance à l'ordre des rendements. Le préambule du
    module chiffre les trois. Une série de moins d'un an ne s'annualise pas
    honnêtement, et le GIPS interdit d'ailleurs de le faire. La durée retenue
    est ``len(returns) / N``, qui compte les lignes MANQUANTES comme des
    périodes écoulées, à la différence de
    :func:`arithmetic_mean_return`, dont le dénominateur est le nombre
    d'observations valides. Sur une série trouée, les deux ne divisent donc pas
    par le même nombre, et ``periods`` sert à trancher.

    **Alternatives.** La moyenne géométrique annualisée donne le MÊME nombre,
    par construction. La moyenne arithmétique annualisée en donne un autre,
    supérieur d'environ :math:`\sigma^2 / 2`, et ne doit pas porter ce nom.

    **Pourquoi cette méthode.** Elle ne dépend que de la richesse finale, donc
    elle est cohérente avec :func:`to_prices` sans hypothèse supplémentaire.

    **Comment vérifier.** Trois rendements annuels de 10 % mènent une richesse
    de 1 à 1,331, dont la racine cubique vaut exactement 1,10, donc un CAGR de
    10 %. Le test du module refait ce calcul à la main.

    Args:
        returns: série ou tableau de rendements.
        frequency: fréquence d'observation, qui fixe le nombre de périodes/an.
        periods: nombre de périodes à retenir pour la durée. Sans valeur, la
            longueur de la série est utilisée.
        kind: convention des rendements fournis.
        periods_per_year: facteur mesuré remplaçant la convention.

    Returns:
        Le taux annuel composé, en rendement SIMPLE quelle que soit la
        convention d'entrée. Un facteur de croissance nul ou négatif, donc une
        faillite, rend -1,0 plutôt qu'un ``NaN``. Un facteur INCONNU, faute
        d'observation valide, rend ``NaN`` : la faillite et l'absence de mesure
        sont deux états différents, et les confondre annonce -100 %/an sur une
        série qui n'a rien mesuré.

    Raises:
        InsufficientDataError: si la série est vide ou si la durée est nulle.

    Example:
        >>> import pandas as pd
        >>> r = pd.Series([0.10] * 3, index=pd.date_range("2020-12-31", periods=3, freq="YE"))
        >>> round(float(cagr(r, Frequency.ANNUAL)), 12)
        0.1
    """
    _validate(returns, name="returns", minimum=1)
    factor = _periods_per_year(frequency, periods_per_year)
    n = len(returns) if periods is None else periods
    years = n / factor
    if years <= 0:
        raise InsufficientDataError("la durée en années doit être strictement positive")
    total = np.asarray(compound(returns, kind=kind), dtype=float)
    growth = np.exp(total) if kind is ReturnKind.LOG else 1.0 + total
    known = ~np.isnan(growth)
    alive = known & (growth > 0.0)
    safe = np.where(alive, growth, 1.0)
    out = np.where(alive, np.power(safe, 1.0 / years) - 1.0, np.where(known, -1.0, np.nan))
    if isinstance(returns, pd.DataFrame):
        return pd.Series(out, index=returns.columns)
    return float(out)


def arithmetic_mean_return(
    returns: pd.Series | pd.DataFrame,
    frequency: Frequency,
    annualize: bool = True,
    kind: ReturnKind = ReturnKind.SIMPLE,
    *,
    periods_per_year: float | None = None,
) -> float | pd.Series:
    r"""Rend la moyenne arithmétique des rendements, annualisée par défaut.

    **Le problème.** Une optimisation moyenne-variance demande le rendement
    ESPÉRÉ d'une période, pas le taux de croissance encaissé. Les deux nombres
    diffèrent, et le second est toujours le plus petit.

    **L'intuition.** On fait la moyenne simple des rendements de période, puis
    on la multiplie par le nombre de périodes dans l'année.

    .. math::

        \mu_a = \frac{1}{n}\sum_{t=1}^{n} r_t,
        \qquad
        \mu_a^{ann} = N \, \mu_a.

    où :math:`n` est le nombre d'observations et :math:`N` le nombre de
    périodes par an.

    **Hypothèses.** Les rendements sont identiquement distribués et
    indépendants. L'annualisation retenue est LINÉAIRE et non composée, comme
    dans la littérature des facteurs. Elle garde la cohérence avec la
    volatilité annualisée en :math:`\sqrt{N}`. Le ratio de Sharpe annualisé
    vaut donc bien :math:`\sqrt{N}` fois celui de la période.

    **Provenance.** Convention de Fama et French, dont les moments publiés sur
    les portefeuilles de facteurs sont des moyennes mensuelles multipliées par
    douze.

    **Limites.** La moyenne arithmétique n'est pas encaissable. Un investisseur
    qui subit +100 % puis -50 % touche zéro pour cent par an alors que la
    moyenne arithmétique annonce +25 % par période.

    **Alternatives.** L'annualisation composée :math:`(1 + \mu_a)^N - 1` donne
    un nombre plus grand, et n'est cohérente ni avec la volatilité en racine ni
    avec la moyenne géométrique. Elle n'est pas retenue.

    **Pourquoi cette méthode.** Elle sert d'entrée aux optimiseurs et de
    numérateur au ratio de Sharpe, deux usages qui exigent tous deux la
    convention linéaire.

    **Comment vérifier.** Sur des rendements constants égaux à :math:`c`, la
    moyenne vaut :math:`c` et sa version annualisée :math:`N c`, exactement.

    Args:
        returns: série ou tableau de rendements.
        frequency: fréquence d'observation.
        annualize: multiplie par le nombre de périodes par an.
        kind: convention des rendements. En logarithme, la moyenne rendue est
            celle des logarithmes, et elle coïncide avec la moyenne géométrique.
        periods_per_year: facteur mesuré remplaçant la convention.

    Returns:
        La moyenne, scalaire pour une série, ``Series`` par colonne pour un
        tableau.

    Raises:
        InsufficientDataError: si la série est vide.

    Example:
        >>> import pandas as pd
        >>> r = pd.Series([0.01] * 12, index=pd.date_range("2020-01-31", periods=12, freq="ME"))
        >>> round(float(arithmetic_mean_return(r, Frequency.MONTHLY)), 10)
        0.12
    """
    _validate(returns, name="returns", minimum=1)
    factor = _periods_per_year(frequency, periods_per_year) if annualize else 1.0
    mean = returns.mean() * factor
    return float(mean) if isinstance(returns, pd.Series) else mean


def geometric_mean_return(
    returns: pd.Series | pd.DataFrame,
    frequency: Frequency,
    annualize: bool = True,
    kind: ReturnKind = ReturnKind.SIMPLE,
    *,
    periods_per_year: float | None = None,
) -> float | pd.Series:
    r"""Rend la moyenne géométrique des rendements, annualisée par défaut.

    **Le problème.** Le taux réellement encaissé par un investisseur qui ne
    retire rien n'est pas la moyenne des rendements, c'est le taux constant qui
    aurait produit la même richesse finale.

    **L'intuition.** On prend la racine :math:`n`-ième du facteur de croissance
    total, puis on compose sur une année.

    .. math::

        \mu_g = \left(\prod_{t=1}^{n} (1 + r_t)\right)^{1/n} - 1,
        \qquad
        \mu_g^{ann} = (1 + \mu_g)^{N} - 1.

    où :math:`n` est le nombre d'observations et :math:`N` le nombre de périodes
    par an.

    **Hypothèses.** Aucune, au-delà de facteurs de croissance positifs. La
    moyenne géométrique est une identité comptable sur la série observée, pas
    une estimation.

    **Provenance.** Inégalité arithmético-géométrique et définition du taux
    équivalent, présentes dans Bacon (2019), chapitre 2.

    **Limites.** Elle ignore la trajectoire et se dégrade vite quand un seul
    rendement approche -100 %, ce qui est correct comptablement mais rend
    l'estimateur très sensible à un point aberrant. La racine est prise sur
    ``len(returns)``, donc les lignes manquantes comptent comme des périodes
    à rendement nul, là où :func:`arithmetic_mean_return` les exclut de son
    dénominateur. Le choix garde l'identité avec :func:`cagr`.

    **Alternatives.** ``scipy.stats.gmean`` sur les facteurs de croissance donne
    exactement le même nombre, et le test du module s'en sert comme
    implémentation indépendante.

    **Pourquoi cette méthode.** Annualisée, elle égale le CAGR par
    construction, ce qui donne une identité vérifiable plutôt qu'une
    concordance approximative.

    **Comment vérifier.** ``geometric_mean_return(r, f)`` doit égaler
    ``cagr(r, f)`` à la précision machine, et rester inférieure ou égale à
    ``arithmetic_mean_return(r, f, annualize=False)`` sur toute série.

    Args:
        returns: série ou tableau de rendements.
        frequency: fréquence d'observation.
        annualize: compose sur le nombre de périodes par an.
        kind: convention des rendements. En logarithme, la composition est une
            somme, donc la moyenne géométrique EST la moyenne arithmétique des
            logarithmes, et l'annualisation redevient linéaire.
        periods_per_year: facteur mesuré remplaçant la convention.

    Returns:
        La moyenne géométrique, en rendement SIMPLE si l'entrée est simple, en
        logarithme si l'entrée est logarithmique. Une faillite rend -1,0, une
        série sans aucune observation valide rend ``NaN``.

    Raises:
        InsufficientDataError: si la série est vide.

    Example:
        La moyenne géométrique de +10 % puis -10 % vaut sqrt(1,10 x 0,90) - 1,
        soit sqrt(0,99) - 1 = -0,005012562893.

        >>> import pandas as pd
        >>> r = pd.Series([0.10, -0.10], index=pd.date_range("2020-12-31", periods=2, freq="YE"))
        >>> round(float(geometric_mean_return(r, Frequency.ANNUAL)), 10)
        -0.0050125629
    """
    _validate(returns, name="returns", minimum=1)
    factor = _periods_per_year(frequency, periods_per_year) if annualize else 1.0
    n = len(returns)
    if kind is ReturnKind.LOG:
        mean = returns.mean() * factor
        return float(mean) if isinstance(returns, pd.Series) else mean
    growth = 1.0 + np.asarray(compound(returns, kind=kind), dtype=float)
    known = ~np.isnan(growth)
    alive = known & (growth > 0.0)
    per_period = np.power(np.where(alive, growth, 1.0), 1.0 / n)
    out = np.where(alive, np.power(per_period, factor) - 1.0, np.where(known, -1.0, np.nan))
    if isinstance(returns, pd.DataFrame):
        return pd.Series(out, index=returns.columns)
    return float(out)


def excess_returns[T: (pd.Series, pd.DataFrame)](
    returns: T,
    risk_free: float | pd.Series,
    frequency: Frequency,
    *,
    method: Literal["arithmetic", "geometric"] = "arithmetic",
    kind: ReturnKind = ReturnKind.SIMPLE,
    annualized_rate: bool = True,
    deannualize: Literal["compound", "linear"] = "compound",
    periods_per_year: float | None = None,
) -> T:
    r"""Rend les rendements en excès du taux sans risque, deux conventions au choix.

    **Le problème.** Un taux sans risque est coté en ANNUEL, la série de
    rendements est observée en quotidien ou en mensuel, et les soustraire tels
    quels surestime l'excès d'un facteur allant jusqu'à 252.

    **L'intuition.** On ramène d'abord le taux annuel à la fréquence de la
    série, puis on retire le placement sans risque du placement risqué. Deux
    façons de retirer coexistent, et elles ne donnent pas le même nombre.

    .. math::

        \text{arithmétique :} \quad e_t = r_t - r^{f}_t
        \qquad
        \text{géométrique :} \quad e_t = \frac{1 + r_t}{1 + r^{f}_t} - 1.

    où :math:`r^{f}_t` est le taux sans risque converti à la fréquence de la
    série. Les deux écritures sont liées par une identité exacte :

    .. math::

        \frac{1 + r_t}{1 + r^{f}_t} - 1 = \frac{r_t - r^{f}_t}{1 + r^{f}_t}.

    donc la version géométrique est la version arithmétique DÉFLATÉE par le
    facteur sans risque. À 4 % de taux annuel et 10 % de rendement annuel,
    l'arithmétique rend 6,00 % et la géométrique 5,769 %, soit un écart de
    23 points de base. En quotidien, cet écart tombe sous le point de base et
    devient invisible.

    **Hypothèses.** Le taux fourni est annuel quand ``annualized_rate`` vaut
    ``True``. La conversion par défaut est COMPOSÉE, :math:`(1 + r^f)^{1/N} - 1`,
    ce qui est exact pour un taux à composition annuelle. La conversion linéaire
    :math:`r^f / N` est la convention du marché monétaire, disponible par
    ``deannualize="linear"``.

    **Provenance.** Ken French soustrait son taux sans risque
    ARITHMÉTIQUEMENT dans la construction de ses facteurs, et son fichier de
    facteurs porte un taux déjà mensuel. C'est pourquoi ``"arithmetic"`` est le
    défaut ici : un excès calculé autrement ne serait plus comparable à la
    littérature des facteurs. La version géométrique est celle que Bacon (2019)
    recommande pour la mesure de performance, parce qu'elle se compose
    proprement dans le temps.

    **Limites.** La série des taux courts est elle-même une prévision imparfaite
    du rendement d'un bon du Trésor détenu sur la période, et un taux emprunté
    diffère d'un taux prêté. Le laboratoire ignore cet écart, et le déclare.

    **Alternatives.** Ne rien soustraire du tout et publier un rendement brut
    est défendable si l'étiquette le dit. Ce module ne le fait pas parce que le
    ratio de Sharpe l'exige.

    **Pourquoi cette méthode.** Les deux conventions sont implémentées et
    nommées, plutôt qu'une seule choisie en silence, parce que l'écart entre
    elles apparaît dans les comparaisons à basse fréquence.

    **Comment vérifier.** Sur un rendement annuel de 10 % et un taux annuel de
    4 %, les deux sorties doivent valoir 0,06 et 0,06/1,04. En convention
    logarithmique, les deux méthodes doivent rendre exactement la même série.

    Args:
        returns: série ou tableau de rendements.
        risk_free: taux sans risque, scalaire ou série indexée par le temps.
        frequency: fréquence d'observation des rendements.
        method: ``"arithmetic"`` pour la soustraction simple, ``"geometric"``
            pour la déflation par le facteur sans risque.
        kind: convention des rendements. En logarithme, les deux méthodes
            coïncident et rendent :math:`r^{\log}_t - \ln(1 + r^f_t)`.
        annualized_rate: le taux fourni est annuel. Le mettre à ``False`` pour
            un taux déjà exprimé à la fréquence de la série, comme celui des
            fichiers de facteurs de Ken French.
        deannualize: ``"compound"`` ou ``"linear"``, la façon de ramener le taux
            annuel à la fréquence de la série.
        periods_per_year: facteur mesuré remplaçant la convention.

    Returns:
        Les rendements en excès, alignés sur l'intersection des index quand le
        taux est une série.

    Raises:
        ValueError: si ``method`` ou ``deannualize`` porte une valeur inconnue.
        InsufficientDataError: si l'intersection des index est vide.

    Example:
        >>> import pandas as pd
        >>> r = pd.Series([0.10], index=pd.DatetimeIndex(["2020-12-31"]))
        >>> round(float(excess_returns(r, 0.04, Frequency.ANNUAL).iloc[0]), 10)
        0.06
    """
    if method not in {"arithmetic", "geometric"}:
        raise ValueError(f"method inconnue : {method!r}")
    if deannualize not in {"compound", "linear"}:
        raise ValueError(f"deannualize inconnue : {deannualize!r}")
    _validate(returns, name="returns", minimum=1)
    factor = _periods_per_year(frequency, periods_per_year)

    if isinstance(risk_free, pd.Series):
        _validate(risk_free, name="risk_free", minimum=1)
        returns, rate = align_returns(returns, risk_free)
    else:
        rate = float(risk_free)

    if annualized_rate:
        rate = (1.0 + rate) ** (1.0 / factor) - 1.0 if deannualize == "compound" else rate / factor

    if kind is ReturnKind.LOG:
        rate_log = np.log1p(rate)
        return returns.sub(rate_log, axis=0) if isinstance(rate, pd.Series) else returns - rate_log

    if method == "arithmetic":
        return returns.sub(rate, axis=0) if isinstance(rate, pd.Series) else returns - rate
    if isinstance(rate, pd.Series):
        return (1.0 + returns).div(1.0 + rate, axis=0) - 1.0
    return (1.0 + returns) / (1.0 + rate) - 1.0


def align_returns(*series: pd.Series | pd.DataFrame) -> tuple[pd.Series | pd.DataFrame, ...]:
    """Rend les mêmes objets restreints à l'intersection de leurs index.

    **Le problème.** Deux séries de longueurs différentes se soustraient sans
    protester en pandas, qui aligne et remplit de manquants. Le calcul aval
    rend alors un ratio de Sharpe estimé sur trois observations communes, sans
    que rien ne le signale.

    **L'intuition.** On ne garde que les dates présentes partout, et on refuse
    de continuer si cet ensemble est vide.

    Args:
        *series: au moins deux objets pandas indexés par le temps.

    Returns:
        Un tuple des objets réindexés sur l'intersection, dans l'ordre reçu.

    Raises:
        ValueError: si moins de deux objets sont fournis.
        InsufficientDataError: si l'intersection est vide.
        DataQualityError: si un index porte des doublons ou n'est pas croissant.

    Note:
        L'alignement porte sur l'index seul. Les manquants intérieurs sont
        conservés tels quels : les retirer est une décision d'étude, pas
        d'infrastructure.

    Example:
        >>> import pandas as pd
        >>> a = pd.Series([1.0, 2.0, 3.0], index=pd.date_range("2020-01-01", periods=3))
        >>> b = pd.Series([9.0, 9.0], index=pd.date_range("2020-01-02", periods=2))
        >>> [len(x) for x in align_returns(a, b)]
        [2, 2]
    """
    if len(series) < 2:
        raise ValueError("align_returns demande au moins deux objets")
    for position, obj in enumerate(series):
        _validate(obj, name=f"série {position}", minimum=0)
    common = series[0].index
    for obj in series[1:]:
        common = common.intersection(obj.index)
    if len(common) == 0:
        raise InsufficientDataError("le recouvrement des index est vide")
    _LOG.debug(
        "alignement effectué",
        extra={"n_series": len(series), "n_common": len(common)},
    )
    return tuple(obj.loc[common] for obj in series)


def overnight_intraday_split(
    open_: pd.DataFrame, close: pd.DataFrame, adj_close: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    r"""Décompose le rendement de clôture à clôture en sa part de nuit et sa part de journée.

    **Le problème.** Une stratégie qui gagne « en moyenne » peut gagner la nuit
    et perdre le jour, ou l'inverse, et la différence décide où placer
    l'exécution. Lou, Polk et Skouras (2019) mesurent que le momentum gagne la
    nuit et la valeur le jour ; le laboratoire doit pouvoir le refaire sur ses
    propres séries.

    **L'intuition.** L'ouverture brute n'est pas ajustée des dividendes et des
    divisions alors que la clôture ajustée l'est. On ajuste l'ouverture par le
    même facteur que la clôture, puis on coupe le chemin de la veille à
    aujourd'hui en deux morceaux qui se composent.

    **La formule.**

    .. math::

        \tilde O_t = O_t \frac{\tilde C_t}{C_t}, \qquad
        r^{\text{nuit}}_t = \frac{\tilde O_t}{\tilde C_{t-1}} - 1, \qquad
        r^{\text{jour}}_t = \frac{\tilde C_t}{\tilde O_t} - 1,
        \qquad (1 + r^{\text{nuit}}_t)(1 + r^{\text{jour}}_t) = \frac{\tilde C_t}{\tilde C_{t-1}}

    **Les variables.** :math:`O_t` et :math:`C_t` l'ouverture et la clôture
    brutes, :math:`\tilde C_t` la clôture ajustée, :math:`\tilde O_t`
    l'ouverture ajustée.

    **Les hypothèses.** Le facteur d'ajustement d'une séance s'applique à son
    ouverture comme à sa clôture. C'est exact pour une division, et une
    approximation pour un dividende détaché entre la clôture de la veille et
    l'ouverture. Une séance sans ouverture, ou sans clôture de veille, rend une
    valeur absente pour ses deux parts.

    **La provenance.** Lou, D., Polk, C. et Skouras, S. (2019). A Tug of War:
    Overnight versus Intraday Expected Returns. Journal of Financial Economics,
    134(1), 192-213. Rapportée, résumé lu le 2026-09-03.

    **Les limites.** La nuit contient tout ce qui se passe hors séance, y
    compris les enchères d'ouverture ; la décomposition est celle des prix
    officiels, pas des heures de négociation.

    **Les alternatives écartées.** Additionner les deux parts, ce qui casse
    l'identité ; utiliser l'ouverture brute, ce qui invente un rendement à
    chaque dividende.

    **Comment vérifier.** Sur trois jours écrits à la main, la composition des
    deux parts redonne le rendement de clôture à clôture à 1e-12, ce que le
    test de ce module vérifie.

    Args:
        open_: les ouvertures brutes, une colonne par titre.
        close: les clôtures brutes, mêmes colonnes et dates.
        adj_close: les clôtures ajustées, mêmes colonnes et dates.

    Returns:
        Le couple ``(nuit, jour)`` de tableaux de rendements simples, mêmes
        dates et colonnes, la première séance absente.

    Raises:
        DataQualityError: les trois tableaux n'ont pas les mêmes dates et
            colonnes, ou un prix n'est pas strictement positif.
    """
    for nom, tableau in (("open", open_), ("close", close), ("adj_close", adj_close)):
        if not tableau.index.equals(adj_close.index) or not tableau.columns.equals(adj_close.columns):
            raise DataQualityError(f"« {nom} » n'a pas les dates et colonnes de « adj_close ».")
        if (tableau <= 0).any().any():
            raise DataQualityError(f"« {nom} » porte un prix nul ou négatif.")
    ouverture_ajustee = open_ * adj_close / close
    nuit = ouverture_ajustee / adj_close.shift(1) - 1.0
    jour = adj_close / ouverture_ajustee - 1.0
    return nuit, jour

r"""Le Sharpe probabiliste et le Sharpe dégonflé : ce qui reste après la chance.

**Le problème.** Un ratio de Sharpe élevé ne prouve rien à lui seul. Il est
gonflé par deux mécanismes distincts, et les deux agissent en même temps.

Le premier est la longueur de l'échantillon. Le ratio de Sharpe est une
statistique estimée, donc bruitée, et son erreur type décroît en
:math:`1/\sqrt{T}`. Sur trois ans de données mensuelles, un Sharpe de 1,0 est
compatible avec un vrai Sharpe nul. Le second mécanisme est la sélection. Qui
essaie mille stratégies sans aucun talent obtiendra quand même une meilleure
stratégie, et son Sharpe sera d'autant plus élevé que les essais sont nombreux.

**Pourquoi mille essais aléatoires produisent mécaniquement un excellent
Sharpe.** Le maximum de :math:`N` tirages indépendants d'une loi centrée n'est
pas centré : il croît comme :math:`\sqrt{2\ln N}`. Avec des essais dont les
Sharpe annuels ont un écart type de 0,5, le meilleur de cent essais atteint 1,27
en moyenne alors qu'aucun n'a la moindre valeur (MODÉLISÉ, par la formule de
:func:`expected_maximum_sharpe`). Publier ce 1,27 comme une découverte, c'est
publier une propriété de la loi normale.

**Le remède.** Deux corrections successives, dues à Bailey et López de Prado.
Le ratio de Sharpe probabiliste (PSR) transforme le Sharpe en une probabilité
que le vrai Sharpe dépasse un repère, en tenant compte de la longueur de
l'échantillon et des deux moments supérieurs. Le ratio de Sharpe dégonflé (DSR)
est ce même PSR, calculé contre un repère qui n'est plus zéro mais le Sharpe
qu'on aurait obtenu par pure chance après :math:`N` essais.

**Ce que le DSR exige, et ce qui le rend inopérant.** Le DSR ne se calcule pas
sans :math:`N`, le nombre d'essais indépendants réellement conduits. Ce nombre
n'est mesurable par aucun contrôle automatique : lui seul sait combien de
variantes il a regardées. Sous-déclarer :math:`N` abaisse le seuil, donc gonfle
le DSR, et le test cesse de tester quoi que ce soit. Un chercheur qui annonce
:math:`N = 5` après en avoir essayé trois cents obtient un DSR flatteur et faux.
C'est la raison de la règle 8 du ``CLAUDE.md`` : les expériences ratées
s'écrivent dans ``docs/research_journal/rejected_ideas.md`` au moment où elles
échouent. Le compteur d'essais n'est pas une formalité comptable, c'est
l'intrant qui décide du verdict.

**Convention d'échelle, à lire avant tout appel.** Toutes les fonctions de ce
module travaillent sur des grandeurs NON ANNUALISÉES, à la fréquence
d'observation de l'échantillon. Un Sharpe annuel de 2,5 mesuré sur des données
quotidiennes s'y passe sous la forme :math:`2{,}5/\sqrt{250}`, et la variance
des Sharpe d'essai suit la même échelle. Mélanger les deux échelles fausse le
terme en :math:`\widehat{SR}^2` d'un facteur égal au nombre de périodes par an.

Provenance. Bailey, D. et López de Prado, M. (2012), « The Sharpe Ratio
Efficient Frontier », Journal of Risk 15(2), pages 3 à 44, pour le PSR et la
longueur minimale d'historique. Bailey, D. et López de Prado, M. (2014), « The
Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and
Non-Normality », Journal of Portfolio Management 40(5), pages 94 à 107, pour le
DSR et l'espérance du maximum.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from scipy.stats import norm

from quantlab.core.errors import DataQualityError, InsufficientDataError

#: La constante d'Euler-Mascheroni, en double précision. L'annexe 2 de Bailey et
#: López de Prado (2014) la tronque à ``0.5772156649`` dans son code ; l'écart
#: sur le seuil est inférieur à 1e-10, donc invisible sur tout verdict publié.
EULER_MASCHERONI: Final[float] = 0.5772156649015329

#: Le nombre minimal d'observations d'un échantillon. C'est la borne du
#: DOMAINE de la formule, pas un seuil de validité statistique : le PSR fait
#: intervenir :math:`\sqrt{T-1}`, qui n'est réel qu'à partir d'une observation.
#: À exactement une observation, le PSR vaut 0,5 pour tout Sharpe, ce qui est la
#: bonne réponse d'un échantillon sans information. La borne de validité, elle,
#: est bien plus haute : les auteurs rappellent la règle usuelle de trente
#: observations pour que le théorème central limite s'applique.
MIN_OBSERVATIONS: Final[float] = 1.0

#: L'aplatissement NON EXCÉDENTAIRE minimal d'une loi de probabilité. Aucune
#: distribution n'a un aplatissement non excédentaire sous 1, cette borne étant
#: atteinte par la loi de Bernoulli symétrique. Une valeur inférieure signale
#: presque toujours un aplatissement EXCÉDENTAIRE passé par erreur.
MIN_KURTOSIS: Final[float] = 1.0

#: Le niveau de confiance retenu par défaut pour la longueur minimale
#: d'historique. C'est celui des exemples chiffrés des deux articles sources.
DEFAULT_CONFIDENCE: Final[float] = 0.95

__all__ = [
    "DEFAULT_CONFIDENCE",
    "EULER_MASCHERONI",
    "MIN_KURTOSIS",
    "MIN_OBSERVATIONS",
    "DeflatedSharpeResult",
    "deflated_sharpe_ratio",
    "expected_maximum_sharpe",
    "haircut",
    "minimum_track_record_length",
    "probabilistic_sharpe_ratio",
    "sharpe_variance_term",
]


def _check_finite(**values: float) -> None:
    """Refuse toute entrée non finie, plutôt que de rendre un verdict silencieux.

    **Pourquoi ce garde existe.** La fonction de répartition normale rend 1 en
    l'infini et NaN sur un NaN. Sans ce refus, un Sharpe manquant traverse tout
    le module et ressort en verdict. Le cas le plus dangereux est un nombre
    d'observations infini, qui rendrait un PSR de 1 : une découverte certaine
    tirée d'une entrée vide.

    Args:
        **values: les entrées à contrôler, nommées par leur paramètre.

    Raises:
        DataQualityError: l'une des valeurs n'est ni finie ni définie.
    """
    for nom, valeur in values.items():
        if not math.isfinite(valeur):
            raise DataQualityError(
                f"l'entrée « {nom} » vaut {valeur} et n'est pas finie : le calcul rendrait "
                "un verdict faux en silence plutôt qu'une erreur"
            )


def _check_moments(skew: float, kurtosis: float) -> None:
    """Refuse un aplatissement impossible, qui trahit la mauvaise convention.

    Args:
        skew: l'asymétrie d'échantillon.
        kurtosis: l'aplatissement NON excédentaire, valant 3 sous la normale.

    Raises:
        DataQualityError: l'aplatissement est sous 1, donc hors du domaine de
            toute loi de probabilité.
    """
    if not math.isfinite(skew):
        raise DataQualityError(f"asymétrie non finie : {skew}")
    if not math.isfinite(kurtosis):
        raise DataQualityError(f"aplatissement non fini : {kurtosis}")
    if kurtosis < MIN_KURTOSIS:
        raise DataQualityError(
            f"aplatissement {kurtosis} sous la borne {MIN_KURTOSIS} : ce module attend "
            "l'aplatissement NON excédentaire, qui vaut 3 sous la loi normale et jamais 0"
        )


def sharpe_variance_term(observed_sr: float, skew: float, kurtosis: float) -> float:
    r"""Rend le facteur qui gonfle l'incertitude du Sharpe quand la loi n'est pas normale.

    **(1) Le problème.** L'erreur type usuelle du ratio de Sharpe suppose des
    rendements normaux. Une stratégie à queue gauche épaisse, comme la vente
    d'options, a un Sharpe bien plus incertain que cette formule ne le dit.

    **(2) L'intuition.** Le Sharpe est un rapport de deux moments estimés. Sa
    variance dépend donc de la variance de ces deux estimateurs et de leur
    covariance, lesquelles font intervenir les moments d'ordre trois et quatre.

    **(3) La formule.**

    .. math::

        V(\widehat{SR}) = 1 - \hat{\gamma}_3 \widehat{SR}
        + \frac{\hat{\gamma}_4 - 1}{4}\widehat{SR}^2

    **(4) Les variables.** :math:`\widehat{SR}` le Sharpe observé, non annualisé.
    :math:`\hat{\gamma}_3` l'asymétrie d'échantillon. :math:`\hat{\gamma}_4`
    l'aplatissement d'échantillon NON EXCÉDENTAIRE, qui vaut 3 sous la loi
    normale. La variance de l'estimateur du Sharpe vaut ensuite
    :math:`V(\widehat{SR})/(T-1)`.

    **La convention d'aplatissement, et pourquoi elle décide de tout.** Le terme
    s'écrit :math:`(\hat{\gamma}_4 - 1)/4`. Sous la loi normale il rend
    :math:`(3-1)/4 = 1/2`, donc :math:`V = 1 + \widehat{SR}^2/2`, qui est
    exactement le résultat de Lo (2002). Passer l'aplatissement EXCÉDENTAIRE,
    nul sous la normale, rendrait :math:`-1/4` au lieu de :math:`+1/2` et
    inverserait le signe de la correction. Ce module attend donc l'aplatissement
    non excédentaire, et :func:`_check_moments` refuse toute valeur sous 1.

    **(5) Les hypothèses.** Rendements stationnaires et ergodiques, non
    nécessairement indépendants ni normaux. Le résultat est asymptotique, donc
    valable en grand échantillon.

    **(6) La provenance.** Mertens (2002), « Comments on Variance of the IID
    Estimator in Lo (2002) », pour la variance asymptotique. Bailey et López de
    Prado (2012) pour cette écriture, équation (8) de leur article.

    **(7) Les limites.** L'asymétrie et l'aplatissement d'échantillon sont très
    mal estimés en petit échantillon. Leur erreur type sous normalité vaut
    :math:`\sqrt{6/T}` et :math:`\sqrt{24/T}`, soit 0,24 et 0,49 pour cent
    observations, MODÉLISÉ. La correction hérite de ce bruit.

    **(8) Les alternatives.** L'erreur type de Lo (2002) corrigée de
    l'autocorrélation, disponible dans
    ``quantlab.analytics.ratios.sharpe_standard_error``, qui traite un défaut
    différent, la dépendance temporelle plutôt que la non-normalité.

    **(9) Pourquoi celle-ci.** C'est l'expression exacte que les deux articles
    sources utilisent. La reprendre telle quelle rend le PSR et le DSR de ce
    module comparables aux chiffres publiés, à la décimale près.

    **(10) Comment vérifier.** Deux identités indépendantes. Sous la normale,
    asymétrie nulle et aplatissement 3, le résultat vaut exactement
    :math:`1 + \widehat{SR}^2/2`. Et l'écriture de Mertens,
    :math:`1 + \widehat{SR}^2/2 - \hat{\gamma}_3\widehat{SR}
    + (\hat{\gamma}_4-3)\widehat{SR}^2/4`, est algébriquement la même. Les deux
    sont testées.

    Args:
        observed_sr: le ratio de Sharpe observé, à la fréquence de l'échantillon.
        skew: l'asymétrie d'échantillon des rendements.
        kurtosis: l'aplatissement d'échantillon NON excédentaire, 3 sous la normale.

    Returns:
        Le facteur de variance, sans unité, valant 1 pour un Sharpe nul.

    Raises:
        DataQualityError: le Sharpe observé ou un moment n'est pas fini, ou
            l'aplatissement est sous 1, ou le facteur obtenu n'est pas
            strictement positif.
    """
    _check_finite(observed_sr=observed_sr)
    _check_moments(skew, kurtosis)
    term = 1.0 - skew * observed_sr + (kurtosis - 1.0) / 4.0 * observed_sr**2
    if term <= 0.0:
        raise DataQualityError(
            f"facteur de variance non positif ({term}) pour SR={observed_sr}, "
            f"asymétrie={skew}, aplatissement={kurtosis} : ce couple de moments est impossible, "
            "toute loi vérifiant l'aplatissement au moins égal au carré de l'asymétrie plus un"
        )
    return term


def probabilistic_sharpe_ratio(
    observed_sr: float,
    benchmark_sr: float,
    n_obs: float,
    skew: float,
    kurtosis: float,
) -> float:
    r"""Rend la probabilité que le vrai ratio de Sharpe dépasse un repère.

    **(1) Le problème.** Deux stratégies affichant le même Sharpe de 1,0 ne
    valent pas la même chose. L'une a dix ans d'historique, l'autre six mois. Ou
    bien l'une perd rarement beaucoup, et l'autre pas. Le Sharpe seul ne porte
    aucune information sur sa propre précision.

    **(2) L'intuition.** L'estimateur du Sharpe est asymptotiquement normal
    autour du vrai Sharpe. Connaissant son erreur type, on répond directement à
    la question qui intéresse l'investisseur : quelle est la probabilité que le
    vrai Sharpe dépasse le seuil qui m'intéresse ?

    **(3) La formule.**

    .. math::

        \widehat{PSR}(SR^*) = \Phi\!\left[
        \frac{(\widehat{SR} - SR^*)\sqrt{T-1}}
        {\sqrt{1 - \hat{\gamma}_3 \widehat{SR}
        + \frac{\hat{\gamma}_4 - 1}{4}\widehat{SR}^2}}\right]

    **(4) Les variables.** :math:`\widehat{SR}` le Sharpe observé non annualisé,
    :math:`SR^*` le repère à la même échelle, :math:`T` le nombre
    d'observations, :math:`\hat{\gamma}_3` l'asymétrie, :math:`\hat{\gamma}_4`
    l'aplatissement NON EXCÉDENTAIRE, et :math:`\Phi` la fonction de répartition
    de la loi normale centrée réduite.

    **La lecture du résultat.** Un PSR de 0,95 se lit : la probabilité que le
    vrai Sharpe dépasse le repère vaut 95 %. Ce n'est pas un ratio de Sharpe
    corrigé, c'est une probabilité, donc toujours entre 0 et 1.

    **(5) Les hypothèses.** Rendements stationnaires et ergodiques, moments
    d'ordre trois et quatre finis, échantillon assez grand pour que le théorème
    central limite s'applique. Les auteurs rappellent la règle usuelle de trente
    observations au minimum, en précisant qu'elle vaut pour l'estimation des
    moments, pas pour la conclusion.

    **(6) La provenance.** Bailey et López de Prado (2012), équation (11).

    **(7) Les limites.** Trois. Le résultat est asymptotique, donc optimiste sur
    un échantillon court. Les moments d'ordre supérieur sont mal estimés, et
    leur bruit se propage. Enfin, et c'est le point important, le PSR ne corrige
    RIEN de la sélection : il traite un essai unique. C'est précisément ce trou
    que le DSR ferme.

    **(8) Les alternatives.** Le Sharpe ajusté de Pezier et White (2006),
    disponible dans ``quantlab.analytics.ratios.adjusted_sharpe_ratio``, qui
    rend un point corrigé plutôt qu'une probabilité. L'intervalle de confiance
    de Lo (2002), qui corrige l'autocorrélation mais suppose la normalité.

    **(9) Pourquoi celui-ci.** Il rend une probabilité, donc une grandeur
    comparable d'une stratégie à l'autre et d'une fréquence à l'autre. Et il
    sert de brique au DSR, dont il est le calcul sous-jacent.

    **(10) Comment vérifier.** Quatre contrôles indépendants, tous testés. Un
    Sharpe égal au repère rend exactement 0,5, quel que soit :math:`T`. Sous la
    normale, le dénominateur se réduit à :math:`\sqrt{1+\widehat{SR}^2/2}`, la
    forme de Lo (2002). Le résultat croît avec :math:`T` et avec l'asymétrie, et
    décroît avec l'aplatissement. Enfin, évalué au nombre d'observations rendu
    par :func:`minimum_track_record_length`, il redonne exactement le niveau de
    confiance demandé.

    Args:
        observed_sr: le Sharpe observé, à la fréquence de l'échantillon.
        benchmark_sr: le repère à battre, à la même échelle. Zéro pose la
            question « la stratégie gagne-t-elle quelque chose ».
        n_obs: le nombre d'observations. Un réel est accepté, ce qui permet
            l'aller-retour exact avec la longueur minimale d'historique, dont le
            résultat n'est pas entier et peut descendre sous deux.
        skew: l'asymétrie d'échantillon des rendements.
        kurtosis: l'aplatissement d'échantillon NON excédentaire, 3 sous la normale.

    Returns:
        La probabilité que le vrai Sharpe dépasse le repère, entre 0 et 1.

    Raises:
        InsufficientDataError: moins d'une observation, ou un nombre
            d'observations infini.
        DataQualityError: les moments passés sont hors du domaine possible, ou
            un Sharpe passé n'est pas fini.
    """
    if not math.isfinite(n_obs) or n_obs < MIN_OBSERVATIONS:
        raise InsufficientDataError(
            f"le PSR exige au moins {MIN_OBSERVATIONS:.0f} observation, en nombre fini, "
            f"et {n_obs} a été reçue"
        )
    _check_finite(benchmark_sr=benchmark_sr)
    variance_term = sharpe_variance_term(observed_sr, skew, kurtosis)
    statistic = (observed_sr - benchmark_sr) * math.sqrt(n_obs - 1.0) / math.sqrt(variance_term)
    return float(norm.cdf(statistic))


def minimum_track_record_length(
    observed_sr: float,
    benchmark_sr: float,
    skew: float,
    kurtosis: float,
    confidence: float = DEFAULT_CONFIDENCE,
) -> float:
    r"""Rend le nombre d'observations minimal pour conclure au niveau demandé.

    **(1) Le problème.** Un gérant affiche un Sharpe de 1,5 sur dix-huit mois.
    Faut-il lui confier de l'argent ? La question pratique n'est pas « le Sharpe
    est-il élevé » mais « l'historique est-il assez long pour que ce Sharpe
    signifie quelque chose ».

    **(2) L'intuition.** On renverse le PSR. Plutôt que de demander la
    probabilité à un :math:`T` donné, on demande le :math:`T` qui porterait
    cette probabilité au niveau voulu. La relation s'inverse en forme fermée,
    puisque :math:`T` n'entre dans le PSR que par :math:`\sqrt{T-1}`.

    **(3) La formule.**

    .. math::

        \widehat{MinTRL} = 1 + \left[1 - \hat{\gamma}_3 \widehat{SR}
        + \frac{\hat{\gamma}_4 - 1}{4}\widehat{SR}^2\right]
        \left(\frac{Z_{1-\alpha}}{\widehat{SR} - SR^*}\right)^2

    **(4) Les variables.** :math:`Z_{1-\alpha}` le quantile normal du niveau de
    confiance, soit 1,6449 à 95 %. Les autres symboles sont ceux du PSR. Le
    résultat s'exprime en NOMBRE D'OBSERVATIONS à la fréquence de l'échantillon,
    jamais en années : diviser par 12 pour du mensuel, par le nombre de séances
    pour du quotidien.

    **(5) Les hypothèses.** Celles du PSR, plus une de plus, souvent oubliée.
    Les moments qui entrent dans la formule sont supposés connus, donc mesurés
    sur une série déjà longue. Les auteurs le disent explicitement : une
    longueur minimale de trente observations ne dispense pas d'en avoir
    davantage pour estimer les moments eux-mêmes.

    **(6) La provenance.** Bailey et López de Prado (2012), équation (13).

    **(7) Les limites.** Le résultat explose quand le Sharpe observé approche le
    repère, en :math:`1/(\widehat{SR}-SR^*)^2`. Et il n'existe pas du tout quand
    le Sharpe observé est sous le repère : aucun historique, si long soit-il, ne
    permet de conclure dans le bon sens. La fonction lève plutôt que de rendre
    un nombre négatif.

    **(8) Les alternatives.** Une puissance de test classique sur le
    :math:`t` de Student des rendements, qui ignore les moments supérieurs et
    sous-estime donc la longueur requise sur les stratégies à queue épaisse.

    **(9) Pourquoi celle-ci.** Elle répond dans l'unité de la décision, un
    nombre de mois ou de séances, et elle chiffre le prix de la non-normalité.
    L'exemple de l'article le montre : un Sharpe annuel de 2 face à un repère de
    1 exige 682,8 séances en normale, contre 59,9 mois quand l'asymétrie vaut
    -0,72 et l'aplatissement 5,78.

    **(10) Comment vérifier.** Par l'aller-retour, qui est une identité exacte.
    Le PSR évalué au :math:`T` rendu ici vaut exactement le niveau de confiance
    demandé, à la précision machine. Le test le vérifie à 1e-12.

    Args:
        observed_sr: le Sharpe observé, à la fréquence de l'échantillon.
        benchmark_sr: le repère à battre, à la même échelle.
        skew: l'asymétrie d'échantillon des rendements.
        kurtosis: l'aplatissement d'échantillon NON excédentaire, 3 sous la normale.
        confidence: le niveau de confiance voulu, strictement entre 0 et 1.

    Returns:
        Le nombre d'observations minimal, réel et non arrondi, à la fréquence
        de l'échantillon.

    Raises:
        ValueError: le niveau de confiance sort de l'intervalle ouvert, ou le
            Sharpe observé ne dépasse pas le repère.
        DataQualityError: les moments ou les Sharpe passés sont hors du domaine
            possible. Un Sharpe non fini est refusé ici plutôt que comparé : le
            NaN rend toute comparaison fausse, donc franchirait le garde suivant.
    """
    if not 0.0 < confidence < 1.0:
        raise ValueError(f"le niveau de confiance doit être strictement entre 0 et 1, reçu {confidence}")
    _check_finite(observed_sr=observed_sr, benchmark_sr=benchmark_sr)
    if observed_sr <= benchmark_sr:
        raise ValueError(
            f"le Sharpe observé ({observed_sr}) ne dépasse pas le repère ({benchmark_sr}) : "
            "aucune longueur d'historique ne permet de conclure dans le sens demandé"
        )
    variance_term = sharpe_variance_term(observed_sr, skew, kurtosis)
    quantile = float(norm.ppf(confidence))
    return 1.0 + variance_term * (quantile / (observed_sr - benchmark_sr)) ** 2


def expected_maximum_sharpe(
    n_trials: int,
    variance_of_trials: float,
    gamma: float = EULER_MASCHERONI,
    mean_of_trials: float = 0.0,
) -> float:
    r"""Rend le Sharpe attendu du meilleur de N essais sans aucun talent.

    **(1) Le problème.** C'est le seuil que le DSR oppose au Sharpe observé.
    Sans lui, la comparaison se fait contre zéro, ce qui revient à supposer que
    le chercheur n'a essayé qu'une chose.

    **(2) L'intuition.** Si l'on tire :math:`N` Sharpe indépendants d'une même
    loi centrée, leur maximum n'est pas centré. Il croît avec :math:`N`, comme
    la taille du plus grand de :math:`N` individus croît avec la taille du
    groupe, sans que personne ne grandisse. La théorie des valeurs extrêmes
    donne le rythme de cette croissance.

    **(3) La formule.**

    .. math::

        E[\max\{\widehat{SR}_n\}] \approx E[\{\widehat{SR}_n\}]
        + \sqrt{V[\{\widehat{SR}_n\}]}\left[(1-\gamma)\,
        \Phi^{-1}\!\left(1 - \frac{1}{N}\right)
        + \gamma\, \Phi^{-1}\!\left(1 - \frac{1}{N e}\right)\right]

    **(4) Les variables.** :math:`N` le nombre d'essais INDÉPENDANTS,
    :math:`V[\{\widehat{SR}_n\}]` la variance des Sharpe obtenus au fil des
    essais, :math:`E[\{\widehat{SR}_n\}]` leur moyenne, nulle sous l'hypothèse
    d'absence de talent. :math:`\gamma` est la constante d'Euler-Mascheroni,
    environ 0,5772. :math:`e` est le nombre d'Euler et :math:`\Phi^{-1}` le
    quantile normal.

    **Le cas d'un seul essai.** Pour :math:`N = 1`, l'expression diverge, le
    quantile de zéro valant moins l'infini. La fonction rend alors la moyenne
    des essais, ce qui est la valeur EXACTE : le maximum d'un seul tirage est ce
    tirage. Aucune sélection n'a eu lieu, donc rien n'est à dégonfler.

    **(5) Les hypothèses.** Essais indépendants, Sharpe d'essai normalement
    distribués, :math:`N` grand. L'indépendance est la plus fragile : cent
    variantes d'une même idée ne font pas cent essais indépendants. L'annexe 3
    de l'article de 2014 traite ce cas.

    **(6) La provenance.** Bailey et López de Prado (2014), équations (1) et
    (6), l'approximation du maximum étant démontrée dans leur annexe 1. Le code
    de leur annexe 2 s'écrit
    ``maxZ=(1-emc)*norm.ppf(1-1./N)+emc*norm.ppf(1-1./(N*e))``.

    **(7) Les limites.** C'est une approximation, et son erreur est mesurable.
    Comparée à la valeur exacte obtenue par quadrature, elle SURESTIME le seuil.
    L'écart va de 0,036 à 0,014 en unités de Sharpe réduit quand :math:`N` passe
    de 10 à 1 000 (MESURÉ par intégration numérique dans le test du module). Le
    sens de l'erreur est le bon pour l'usage visé : un seuil trop haut rend le
    DSR prudent plutôt que complaisant.

    **(8) Les alternatives.** Le seuil de Harvey et Liu (2014), fondé sur le
    contrôle du taux de fausses découvertes de Benjamini et Hochberg. Les
    auteurs de 2014 le citent comme complémentaire et invitent à calculer le DSR
    contre les deux seuils.

    **(9) Pourquoi celle-ci.** Elle est en forme fermée, donc sans tirage ni
    graine, et elle ne demande que deux nombres que le chercheur connaît, le
    compte de ses essais et la dispersion de leurs résultats.

    **(10) Comment vérifier.** Par simulation. Tirer :math:`N` Sharpe normaux de
    variance connue, prendre le maximum, recommencer deux mille fois, et
    comparer la moyenne des maxima à la formule. Le test du module le fait, et
    borne l'écart par la somme de l'erreur d'approximation, calculée exactement
    par quadrature, et de quatre erreurs types de la moyenne simulée.

    Args:
        n_trials: le nombre d'essais indépendants conduits, au moins 1.
        variance_of_trials: la variance des Sharpe obtenus au fil des essais, à
            la fréquence de l'échantillon et non annualisée.
        gamma: la constante d'Euler-Mascheroni. Exposée en argument pour que le
            chiffre publié reste reproductible si la constante change de
            précision.
        mean_of_trials: la moyenne des Sharpe d'essai. Zéro par défaut, ce qui
            est l'hypothèse nulle d'absence totale de talent dans la classe de
            stratégies étudiée.

    Returns:
        Le Sharpe attendu du meilleur essai, à la fréquence de l'échantillon.

    Raises:
        ValueError: moins d'un essai.
        DataQualityError: la variance des essais est négative ou non finie, ou
            la constante de pondération ou la moyenne des essais n'est pas finie.
    """
    if n_trials < 1:
        raise ValueError(f"le nombre d'essais doit valoir au moins 1, reçu {n_trials}")
    _check_finite(gamma=gamma, mean_of_trials=mean_of_trials)
    if not math.isfinite(variance_of_trials) or variance_of_trials < 0.0:
        raise DataQualityError(
            f"la variance des Sharpe d'essai doit être finie et positive, reçue {variance_of_trials}"
        )
    if n_trials == 1:
        return mean_of_trials
    upper = float(norm.ppf(1.0 - 1.0 / n_trials))
    upper_scaled = float(norm.ppf(1.0 - 1.0 / (n_trials * math.e)))
    return mean_of_trials + math.sqrt(variance_of_trials) * ((1.0 - gamma) * upper + gamma * upper_scaled)


def deflated_sharpe_ratio(
    observed_sr: float,
    sharpe_variance_across_trials: float,
    n_trials: int,
    n_obs: float,
    skew: float,
    kurtosis: float,
    gamma: float = EULER_MASCHERONI,
    mean_sharpe_across_trials: float = 0.0,
) -> float:
    r"""Rend la probabilité que le Sharpe survive à la sélection et à la non-normalité.

    **(1) Le problème.** Le PSR répond à « ce Sharpe est-il assez précis », pas
    à « ce Sharpe est-il le meilleur de trois cents essais ». Les deux sources
    de gonflement agissent ensemble, et corriger l'une seule laisse passer des
    découvertes fausses.

    **(2) L'intuition.** On garde le PSR, on déplace son repère. Le repère n'est
    plus zéro mais le Sharpe qu'un chercheur sans talent aurait obtenu en
    gardant le meilleur de ses :math:`N` essais. Battre zéro ne prouve rien ;
    battre son propre maximum de chance prouve quelque chose.

    **(3) La formule.**

    .. math::

        \widehat{DSR} = \widehat{PSR}(\widehat{SR_0}) = \Phi\!\left[
        \frac{(\widehat{SR} - \widehat{SR_0})\sqrt{T-1}}
        {\sqrt{1 - \hat{\gamma}_3 \widehat{SR}
        + \frac{\hat{\gamma}_4 - 1}{4}\widehat{SR}^2}}\right]

    avec le seuil

    .. math::

        \widehat{SR_0} = \sqrt{V[\{\widehat{SR}_n\}]}\left[(1-\gamma)\,
        \Phi^{-1}\!\left(1 - \frac{1}{N}\right)
        + \gamma\, \Phi^{-1}\!\left(1 - \frac{1}{N e}\right)\right]

    **(4) Les variables.** Celles du PSR, plus :math:`N` le nombre d'essais
    indépendants et :math:`V[\{\widehat{SR}_n\}]` la variance des Sharpe
    obtenus au fil de ces essais. Toutes les grandeurs sont à la fréquence de
    l'échantillon.

    **(5) Les hypothèses.** Celles du PSR, plus celles du seuil : essais
    indépendants, Sharpe d'essai normaux, absence de talent sous l'hypothèse
    nulle. Une hypothèse implicite mérite d'être nommée : le chercheur DÉCLARE
    honnêtement :math:`N`.

    **(6) La provenance.** Bailey et López de Prado (2014), équation (2). Leur
    exemple chiffré est reproduit dans le test du module. Il part d'un Sharpe
    annuel de 2,5 sur 1 250 jours, avec :math:`N = 100` et une variance d'essai
    de 0,002. L'asymétrie vaut -3, l'aplatissement 10, et le DSR sort à 0,90.

    **(7) Les limites.** Deux, et la première est décisive. Le DSR n'est pas
    plus fiable que le :math:`N` qu'on lui donne, et ce nombre n'est vérifiable
    par aucun contrôle automatique. Sous-déclarer les essais abaisse le seuil et
    gonfle le DSR, ce qui vide le test de sa fonction. La seconde limite est
    l'indépendance : compter trois cents variantes d'une même idée comme trois
    cents essais indépendants surestime le seuil dans l'autre sens.

    **(8) Les alternatives.** Le Sharpe rasé de Harvey et Liu (2015), qui rend
    un Sharpe corrigé plutôt qu'une probabilité, et la longueur minimale de
    backtest des mêmes auteurs de 2014. Le contrôle par validation croisée
    combinatoire purgée traite le même mal par un autre chemin, en mesurant
    directement la probabilité de surapprentissage.

    **(9) Pourquoi celui-ci.** Il agrège en un seul nombre les cinq intrants qui
    décident réellement de la crédibilité d'un backtest : longueur, asymétrie,
    aplatissement, dispersion des essais et nombre d'essais. Et il conserve la
    lecture probabiliste du PSR.

    **(10) Comment vérifier.** Sur l'exemple publié de l'article, dont trois
    valeurs sont reproduites par le test du module : 0,9505 pour
    :math:`N = 46`, environ 0,90 pour :math:`N = 100`, et 0,95 pour
    :math:`N = 88` sous des rendements normaux. Deux propriétés sont testées en
    plus, la décroissance stricte en :math:`N` et le passage sous 0,5 dès que le
    Sharpe observé tombe sous le seuil.

    Args:
        observed_sr: le Sharpe observé de la stratégie retenue, non annualisé.
        sharpe_variance_across_trials: la variance des Sharpe obtenus au fil des
            essais, à la même échelle.
        n_trials: le nombre d'essais indépendants conduits.
        n_obs: le nombre d'observations de l'échantillon retenu.
        skew: l'asymétrie d'échantillon des rendements de la stratégie retenue.
        kurtosis: l'aplatissement d'échantillon NON excédentaire, 3 sous la normale.
        gamma: la constante d'Euler-Mascheroni.
        mean_sharpe_across_trials: la moyenne des Sharpe d'essai, nulle sous
            l'hypothèse d'absence de talent.

    Returns:
        La probabilité que le vrai Sharpe dépasse le seuil de sélection, entre
        0 et 1. Un DSR sous 0,95 ne se publie pas comme une découverte.

    Raises:
        InsufficientDataError: moins d'une observation.
        DataQualityError: les moments ou la variance des essais sont impossibles.
        ValueError: moins d'un essai.
    """
    threshold = expected_maximum_sharpe(
        n_trials,
        sharpe_variance_across_trials,
        gamma=gamma,
        mean_of_trials=mean_sharpe_across_trials,
    )
    return probabilistic_sharpe_ratio(observed_sr, threshold, n_obs, skew, kurtosis)


def haircut(
    observed_sr: float,
    n_trials: int,
    sharpe_variance_across_trials: float,
    gamma: float = EULER_MASCHERONI,
    mean_sharpe_across_trials: float = 0.0,
) -> float:
    r"""Rend la part du Sharpe observé que la seule chance explique.

    **(1) Le problème.** Le DSR rend une probabilité, qui répond par oui ou par
    non. Le gérant veut aussi savoir de combien son chiffre est amputé, dans
    l'unité qu'il connaît. « Votre Sharpe de 2,5 vaut 0,90 de probabilité » ne
    dit pas ce que la sélection a coûté.

    **(2) L'intuition.** Le seuil du DSR est le Sharpe qu'on aurait obtenu sans
    aucun talent après :math:`N` essais. Rapporté au Sharpe observé, il donne
    directement la fraction de celui-ci qui n'est que le résultat de la
    sélection.

    **(3) La formule.**

    .. math::

        H = \frac{\widehat{SR_0}}{\widehat{SR}}
        = 1 - \frac{\widehat{SR} - \widehat{SR_0}}{\widehat{SR}}

    **(4) Les variables.** :math:`\widehat{SR}` le Sharpe observé, strictement
    positif, et :math:`\widehat{SR_0}` le seuil de
    :func:`expected_maximum_sharpe`. Le résultat est une FRACTION, à multiplier
    par cent pour l'exprimer en pourcentage.

    **La lecture, avec un cas chiffré.** Sur l'exemple de l'article de 2014, le
    Sharpe non annualisé vaut 0,1581 et le seuil 0,1132 après cent essais. La
    fraction rendue est 0,716, donc 71,6 % du Sharpe affiché s'explique par la
    sélection seule, et 28,4 % restent à la stratégie (MODÉLISÉ, depuis les trois
    intrants publiés de l'article).

    **(5) Les hypothèses.** Celles de :func:`expected_maximum_sharpe`, et une de
    plus : le Sharpe observé est strictement positif, sans quoi la fraction n'a
    pas de sens.

    **(6) La provenance.** La notion de Sharpe rasé vient de Harvey et Liu
    (2015), « Backtesting », Journal of Portfolio Management 42(1). La
    définition retenue ici est celle du cadre de Bailey et López de Prado, dont
    le seuil sert de numérateur.

    **(7) Les limites.** La fraction peut dépasser 1, ce qui signifie que le
    Sharpe observé est entièrement sous le seuil de chance. La fonction ne
    tronque pas : un dépassement est une information, pas une anomalie
    d'affichage.

    **(8) Les alternatives.** Le rasage de Harvey et Liu passe par la valeur p
    ajustée du test multiple, puis reconvertit cette valeur p en Sharpe. Il rend
    des nombres différents, parce qu'il corrige le taux de fausses découvertes
    plutôt que l'espérance du maximum.

    **(9) Pourquoi celle-ci.** Elle est en forme fermée, elle se lit sans
    formation statistique, et elle est cohérente avec le DSR publié à côté
    d'elle : les deux reposent sur le même seuil.

    **(10) Comment vérifier.** La fraction vaut zéro pour un seul essai, puisque
    le seuil vaut alors la moyenne des essais, nulle par défaut. Elle croît
    strictement avec le nombre d'essais et avec la dispersion de leurs
    résultats. Les trois propriétés sont testées.

    Args:
        observed_sr: le Sharpe observé, strictement positif, non annualisé.
        n_trials: le nombre d'essais indépendants conduits.
        sharpe_variance_across_trials: la variance des Sharpe d'essai.
        gamma: la constante d'Euler-Mascheroni.
        mean_sharpe_across_trials: la moyenne des Sharpe d'essai.

    Returns:
        La fraction du Sharpe observé imputable à la sélection, sans unité.

    Raises:
        ValueError: le Sharpe observé n'est pas strictement positif, ou moins
            d'un essai.
        DataQualityError: la variance des essais est impossible.
    """
    if observed_sr <= 0.0:
        raise ValueError(
            f"le Sharpe observé doit être strictement positif pour un rasage relatif, reçu {observed_sr}"
        )
    threshold = expected_maximum_sharpe(
        n_trials,
        sharpe_variance_across_trials,
        gamma=gamma,
        mean_of_trials=mean_sharpe_across_trials,
    )
    return threshold / observed_sr


@dataclass(frozen=True, slots=True)
class DeflatedSharpeResult:
    """Le verdict du Sharpe dégonflé, avec tous ses intrants.

    **Pourquoi porter les intrants.** Un DSR de 0,93 ne veut rien dire seul. Le
    même chiffre découle de vingt combinaisons d'essais, de longueurs et de
    moments, et il se relit six mois plus tard sans ambiguïté seulement si les
    six intrants voyagent avec lui. Cette classe est gelée pour que le chiffre
    publié ne puisse plus bouger après coup.

    **La règle 8, dans un attribut.** Le champ ``n_trials`` est celui que
    personne ne peut vérifier à la place du chercheur. Le porter dans le
    résultat le rend citable, donc opposable.

    Attributes:
        observed_sr: le Sharpe observé, non annualisé.
        n_obs: le nombre d'observations de l'échantillon.
        skew: l'asymétrie d'échantillon des rendements.
        kurtosis: l'aplatissement NON excédentaire, 3 sous la loi normale.
        n_trials: le nombre d'essais indépendants DÉCLARÉ.
        sharpe_variance_across_trials: la variance des Sharpe d'essai.
        mean_sharpe_across_trials: la moyenne des Sharpe d'essai.
        gamma: la constante d'Euler-Mascheroni employée.
        expected_maximum_sr: le seuil de sélection, en unités de Sharpe.
        deflated_sharpe: le DSR, probabilité entre 0 et 1.
        probabilistic_sharpe_vs_zero: le PSR contre zéro, pour lire d'un coup
            d'œil ce que la seule correction de sélection a retiré.
        haircut_fraction: la part du Sharpe observé imputable à la sélection.
    """

    observed_sr: float
    n_obs: float
    skew: float
    kurtosis: float
    n_trials: int
    sharpe_variance_across_trials: float
    mean_sharpe_across_trials: float
    gamma: float
    expected_maximum_sr: float
    deflated_sharpe: float
    probabilistic_sharpe_vs_zero: float
    haircut_fraction: float

    @classmethod
    def from_inputs(
        cls,
        observed_sr: float,
        sharpe_variance_across_trials: float,
        n_trials: int,
        n_obs: float,
        skew: float,
        kurtosis: float,
        gamma: float = EULER_MASCHERONI,
        mean_sharpe_across_trials: float = 0.0,
    ) -> DeflatedSharpeResult:
        """Calcule le verdict complet et le fige avec ses intrants.

        Args:
            observed_sr: le Sharpe observé, non annualisé.
            sharpe_variance_across_trials: la variance des Sharpe d'essai.
            n_trials: le nombre d'essais indépendants conduits.
            n_obs: le nombre d'observations de l'échantillon.
            skew: l'asymétrie d'échantillon des rendements.
            kurtosis: l'aplatissement NON excédentaire, 3 sous la normale.
            gamma: la constante d'Euler-Mascheroni.
            mean_sharpe_across_trials: la moyenne des Sharpe d'essai.

        Returns:
            Le résultat gelé, prêt à être journalisé ou publié.

        Raises:
            InsufficientDataError: moins d'une observation.
            DataQualityError: les moments ou la variance des essais sont impossibles.
            ValueError: moins d'un essai, ou Sharpe observé non positif.
        """
        threshold = expected_maximum_sharpe(
            n_trials,
            sharpe_variance_across_trials,
            gamma=gamma,
            mean_of_trials=mean_sharpe_across_trials,
        )
        return cls(
            observed_sr=observed_sr,
            n_obs=n_obs,
            skew=skew,
            kurtosis=kurtosis,
            n_trials=n_trials,
            sharpe_variance_across_trials=sharpe_variance_across_trials,
            mean_sharpe_across_trials=mean_sharpe_across_trials,
            gamma=gamma,
            expected_maximum_sr=threshold,
            deflated_sharpe=probabilistic_sharpe_ratio(observed_sr, threshold, n_obs, skew, kurtosis),
            probabilistic_sharpe_vs_zero=probabilistic_sharpe_ratio(observed_sr, 0.0, n_obs, skew, kurtosis),
            haircut_fraction=haircut(
                observed_sr,
                n_trials,
                sharpe_variance_across_trials,
                gamma=gamma,
                mean_sharpe_across_trials=mean_sharpe_across_trials,
            ),
        )

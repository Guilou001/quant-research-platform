r"""Les figures des rapports d'étude, en Matplotlib, pour le PDF et le PNG.

**Le problème.** Une figure peut être vraie et ne rien montrer. Elle peut aussi
montrer un chiffre faux sans que rien ne le signale, parce qu'une image ne se
teste pas. Tant qu'une fabrique ne rend que des pixels, aucun test ne peut la
contredire, et la figure devient le seul endroit du dépôt où un nombre circule
sans preuve.

**La règle du module.** Chaque fabrique rend un couple ``(figure, données)``.
Les données sont les nombres effectivement dessinés, dans un objet pandas ou
une petite classe de données. Le test porte sur ces nombres, comparés à un
calcul indépendant, et le dessin n'est plus qu'une mise en forme de ce qui a
déjà été vérifié. C'est la règle du paquet ``gvf.figures`` du portefeuille,
reprise ici parce qu'elle a déjà servi.

**La feuille de style.** Elle n'est pas réécrite. ``gvf.style`` porte la palette
d'Okabe et Ito, lisible sous les trois formes courantes de daltonisme, et la
virgule décimale des axes, sans laquelle un axe français affiche « 12.5 ».
Mesuré le 2026-09-02 dans cet environnement : ``gvf`` version 0.4.0 est
importable, donc aucune feuille locale de repli n'est écrite.

**Les réglages ne fuient pas.** ``gvf.style.appliquer`` modifie les ``rcParams``
de Matplotlib pour tout le processus. Une bibliothèque n'a pas à faire cela au
dos de son appelant. Les réglages sont donc capturés une fois, puis posés dans
un contexte qui les retire à la sortie, ce que :func:`portfolio_style` fournit.

**Les conventions d'axe du portefeuille**, tenues ici sans exception. On écrit
« points de pourcentage », jamais « pt » ni « points de % ». On écrit « échelle
logarithmique » en toutes lettres. Tout axe de richesse cumulée porte sa devise
et sa date de base. Aucun nom de clé interne n'atteint le lecteur, les fabriques
qui reçoivent des noms de colonnes acceptant une étiquette lisible. Enfin chaque
titre par défaut est déduit des données dessinées, jamais écrit d'avance.

**Statut des nombres.** Ce module ne produit aucune estimation. Il met en forme
ce que ``quantlab.analytics`` et ``quantlab.validation`` ont mesuré, et il ne
réimplémente aucune métrique, règle 12 du ``CLAUDE.md``. Le ratio de Sharpe vient
de ``analytics.ratios``, le repli de ``analytics.drawdown``, le point de rupture
des coûts de ``validation.robustness``.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import matplotlib as mpl
import numpy as np
import pandas as pd
from gvf import style as gvf_style
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from pandas.api.types import is_numeric_dtype
from scipy import stats

from quantlab.analytics.drawdown import drawdown_series, max_drawdown
from quantlab.analytics.ratios import sharpe_ratio
from quantlab.analytics.regression import rolling_beta
from quantlab.analytics.returns import cumulative_wealth, resample_returns
from quantlab.analytics.risk import kurtosis, volatility
from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.types import Frequency, ReturnFrame, ReturnSeries
from quantlab.validation.robustness import CostAnalysis, cost_multiplier_analysis

__all__ = [
    "BASE_FONT_SIZE",
    "CONSTANT_SAMPLE_TOLERANCE",
    "DEFAULT_BENCHMARK_LABEL",
    "DEFAULT_CURRENCY",
    "DEFAULT_FIGSIZE",
    "DEFAULT_HISTOGRAM_BINS",
    "DEFAULT_IC_WINDOW",
    "DEFAULT_ROLLING_WINDOW",
    "HistogramData",
    "QuantileBars",
    "RollingMetric",
    "correlation_heatmap",
    "cost_sensitivity",
    "equity_curve",
    "ic_timeseries",
    "monthly_returns_heatmap",
    "parameter_heatmap",
    "portfolio_style",
    "qq_plot",
    "quantile_bars",
    "return_histogram",
    "rolling_metric",
    "save_figure",
    "subperiod_bars",
    "underwater",
]

#: La taille de police de base, en points typographiques. Onze points est le
#: réglage par défaut de ``gvf.style.appliquer``, retenu tel quel pour que les
#: figures de ce dépôt et celles du reste du portefeuille se ressemblent.
BASE_FONT_SIZE = 11.0

#: La taille par défaut d'une figure, en pouces. Le rapport 16 sur 9 tient dans
#: la largeur d'une page A4 avec ses marges, et dans une colonne de README.
DEFAULT_FIGSIZE: tuple[float, float] = (8.0, 4.5)

#: La devise par défaut des axes de richesse. Le laboratoire travaille sur des
#: portefeuilles canadiens, et un axe sans devise ne veut rien dire.
DEFAULT_CURRENCY = "$ CA"

#: Le nom donné au repère quand l'appelant n'en fournit pas par ``Series.name``.
DEFAULT_BENCHMARK_LABEL = "Repère"

#: La fenêtre glissante par défaut, en observations. 252 est le nombre de
#: séances d'une année sous la convention de ``Frequency.DAILY``.
DEFAULT_ROLLING_WINDOW = 252

#: La fenêtre par défaut de la moyenne mobile du coefficient d'information, en
#: dates. Douze correspond à une année de dates mensuelles, la fréquence usuelle
#: d'un signal transversal.
DEFAULT_IC_WINDOW = 12

#: Le nombre de classes par défaut de l'histogramme des rendements.
DEFAULT_HISTOGRAM_BINS = 50

#: La part de l'intervalle entre deux dates qu'occupe une barre. Le reste sépare
#: les barres. Mesuré le 2026-09-02 : une largeur fixe de 0,8 sur un index
#: mensuel, dont le pas vaut 28 à 31 jours, dessinait des barres couvrant 2,9
#: pour cent de leur intervalle, donc invisibles à la résolution d'un README.
BAR_WIDTH_FRACTION = 0.8

#: Le nombre de points de la courbe normale superposée à l'histogramme. Assez
#: pour que la courbe paraisse lisse à la résolution d'impression.
NORMAL_CURVE_POINTS = 512

#: Les couleurs des cartes de chaleur divergentes, du négatif au positif. Rouge
#: et bleu restent distinguables sous les deux formes les plus fréquentes de
#: daltonisme, ce que le vert et le rouge ne font pas. Cette échelle ne convient
#: qu'à une grandeur qui change de signe, le blanc du centre marquant le zéro.
DIVERGING_COLORMAP = "RdBu"

#: Les couleurs des cartes de chaleur d'une grandeur qui garde son signe. Une
#: échelle divergente centrée sur zéro n'utiliserait alors qu'une moitié de sa
#: rampe. Mesuré le 2026-09-02 sur un balayage dont le ratio net va de 0,80 à
#: 1,04 : la rampe symétrique n'en couvrait que 11,5 pour cent, et les
#: vingt-cinq cases se ressemblaient toutes. « viridis » est perceptuellement
#: uniforme et lisible sous les trois formes courantes de daltonisme.
SEQUENTIAL_COLORMAP = "viridis"

#: L'opacité des aires remplies. Assez basse pour laisser voir la grille.
FILL_ALPHA = 0.35

#: Le seuil au-dessous duquel une carte de chaleur cesse d'être annotée. Au delà
#: de deux cents cases, les nombres se chevauchent et masquent la couleur.
MAX_ANNOTATED_CELLS = 200

#: Le seuil relatif au-dessous duquel un écart type est tenu pour nul. Une série
#: constante ne rend pas zéro exactement, sa moyenne n'étant pas représentable en
#: binaire, et son écart type mesuré vaut quelques 1e-18. Le seuil est relatif à
#: l'échelle des données, comme dans ``analytics.ratios``.
CONSTANT_SAMPLE_TOLERANCE = 1e-12

#: Les métriques que :func:`rolling_metric` sait tracer.
RollingMetric = Literal["sharpe", "volatility", "beta"]

_RC_CACHE: dict[str, Any] = {}


def _rc_portefeuille() -> dict[str, Any]:
    """Rend les seuls ``rcParams`` que la feuille du portefeuille modifie.

    Les réglages sont posés par ``gvf.style.appliquer`` dans un contexte
    temporaire, puis comparés à l'état d'origine. Ne garder que les clés
    changées évite de réimposer le moteur graphique ou le dossier de polices de
    l'appelant, ce qu'un dictionnaire complet ferait.
    """
    if not _RC_CACHE:
        avant = mpl.rcParams.copy()
        with mpl.rc_context():
            gvf_style.appliquer(BASE_FONT_SIZE)
            for cle, valeur in mpl.rcParams.items():
                if cle in avant and repr(valeur) != repr(avant[cle]):
                    _RC_CACHE[cle] = valeur
    return dict(_RC_CACHE)


@contextlib.contextmanager
def portfolio_style() -> Iterator[None]:
    """La feuille de style du portefeuille, posée le temps d'un bloc.

    Toute figure de ce module est construite à l'intérieur de ce contexte, et
    :func:`save_figure` s'y replace pour l'écriture. La raison tient à deux
    réglages qui ne sont lus qu'au moment d'enregistrer, la résolution et le
    type de police du PDF.

    Yields:
        Rien. Le contexte ne sert qu'à poser puis retirer les réglages.

    Example:
        >>> with portfolio_style():
        ...     import matplotlib as mpl
        ...     mpl.rcParams["legend.frameon"]
        False
    """
    with mpl.rc_context(rc=_rc_portefeuille()):
        yield


def _nouvelle_figure(figsize: tuple[float, float]) -> tuple[Figure, Axes]:
    """Crée une figure et son unique repère, sans passer par ``pyplot``.

    ``pyplot`` tient un registre global des figures ouvertes, qui fuit dès qu'un
    appelant oublie de fermer. La construction directe n'a pas ce défaut.
    """
    fig = Figure(figsize=figsize)
    ax = fig.add_subplot(1, 1, 1)
    return fig, ax


def _est_constant(valeurs: np.ndarray, ecart_type: float) -> bool:
    """Dit si un échantillon est constant à la précision machine près.

    Le seuil est relatif à l'échelle des données. Une comparaison à zéro strict
    laisserait passer une série constante, dont l'écart type mesuré vaut
    quelques 1e-18 plutôt que zéro.
    """
    echelle = float(np.max(np.abs(valeurs))) if valeurs.size else 0.0
    return ecart_type <= CONSTANT_SAMPLE_TOLERANCE * max(echelle, 1.0)


def _humaniser(nom: str) -> str:
    """Rend une étiquette lisible à partir d'un nom de colonne.

    Le souligné devient une espace et la première lettre passe en capitale. La
    convention du portefeuille interdit d'exposer une clé interne au lecteur, et
    cette fonction est le repli quand l'appelant n'a pas fourni d'étiquette.
    """
    propre = nom.replace("_", " ").strip()
    return propre[:1].upper() + propre[1:] if propre else nom


def _serie_propre(returns: ReturnSeries, *, nom: str, minimum: int = 1) -> pd.Series:
    """Rend la série sans valeur manquante, après contrôle de sa taille."""
    if not isinstance(returns, pd.Series):
        raise ConfigError(f"{nom} doit être une série pandas, reçu {type(returns).__name__}")
    propre = returns.dropna().astype("float64")
    if len(propre) < minimum:
        raise InsufficientDataError(f"{nom} porte {len(propre)} observations, {minimum} exigées")
    return propre


def _largeur_de_barre(index: pd.Index) -> float:
    """Rend la largeur d'une barre dans les unités de l'axe des abscisses.

    Matplotlib compte les abscisses d'un index de dates en JOURS. Une largeur
    fixe de 0,8 convient donc à un pas quotidien et disparaît à tout pas plus
    grossier. La largeur se déduit du pas médian de l'index, ce qui vaut pour le
    mensuel comme pour l'hebdomadaire.

    Args:
        index: l'index des dates tracées.

    Returns:
        La largeur, en jours pour un index de dates et sans unité sinon.
    """
    if not isinstance(index, pd.DatetimeIndex) or len(index) < 2:
        return BAR_WIDTH_FRACTION
    pas = np.median(np.diff(index.to_numpy()).astype("timedelta64[s]").astype("float64"))
    jours = pas / 86_400.0
    return BAR_WIDTH_FRACTION * jours if jours > 0.0 else BAR_WIDTH_FRACTION


def _bornes_de_dates(index: pd.Index) -> tuple[str, str]:
    """Rend la première et la dernière étiquette de l'index, en texte.

    Les dates sont écrites en année, mois et jour, format non ambigu qui se lit
    de la même façon des deux côtés de la frontière.
    """
    debut, fin = index[0], index[-1]
    if isinstance(index, pd.DatetimeIndex):
        return debut.strftime("%Y-%m-%d"), fin.strftime("%Y-%m-%d")
    return str(debut), str(fin)


def _formateur_points_de_pourcentage(decimales: int = 1) -> Any:
    """Rend le formateur d'axe qui affiche une fraction en points de pourcentage.

    Les données restent des fractions, et seul l'affichage est multiplié par
    cent. Une fraction convertie dans les données se retrouverait tôt ou tard
    additionnée à une autre restée en fraction.
    """
    return gvf_style.formateur(decimales, "", 100.0)


def _echelle_de_couleur(valeurs: np.ndarray) -> tuple[float, float, str]:
    """Choisit les bornes et la rampe de couleur d'une carte de chaleur.

    Le critère est le signe des données. Une grandeur qui change de signe garde
    une rampe divergente bornée symétriquement, si bien que le blanc du centre
    marque le zéro. Une grandeur qui garde son signe reçoit une rampe séquentielle
    bornée par ses propres extrêmes, faute de quoi elle n'occuperait qu'une
    moitié de la rampe et toutes ses cases se ressembleraient.

    Args:
        valeurs: les cases de la table, valeurs manquantes comprises.

    Returns:
        La borne basse, la borne haute, et le nom de la rampe.
    """
    minimum = float(np.nanmin(valeurs))
    maximum = float(np.nanmax(valeurs))
    if minimum < 0.0 < maximum:
        amplitude = max(abs(minimum), abs(maximum))
        return -amplitude, amplitude, DIVERGING_COLORMAP
    if maximum == minimum:
        # Une table constante n'a pas d'étendue : on l'ouvre d'une unité pour que
        # ``imshow`` reçoive des bornes distinctes.
        return minimum - 0.5, maximum + 0.5, SEQUENTIAL_COLORMAP
    return minimum, maximum, SEQUENTIAL_COLORMAP


#: Le seuil de luminance au-dessous duquel une case est tenue pour sombre, donc
#: annotée en blanc. La luminance perçue est calculée par la pondération de la
#: recommandation UIT-R BT.601, 0,299 pour le rouge, 0,587 pour le vert et 0,114
#: pour le bleu. Le seuil de 0,5 est un précepte, non une mesure.
DARK_CELL_LUMINANCE = 0.5


def _carte_de_chaleur(
    ax: Axes,
    table: pd.DataFrame,
    *,
    vmin: float,
    vmax: float,
    colormap: str,
    annoter: bool,
    decimales: int,
    facteur: float,
) -> Any:
    """Dessine une table en carte de chaleur, avec ou sans annotation des cases.

    La couleur de l'annotation se déduit de la luminance de la case, et non du
    signe de la valeur. Un seuil sur le signe ne vaudrait que pour une rampe
    divergente, et écrirait du noir sur du bleu nuit dès qu'une rampe
    séquentielle est employée.

    Args:
        ax: le repère à remplir.
        table: les valeurs, lignes et colonnes déjà ordonnées.
        vmin: la borne basse de l'échelle de couleur.
        vmax: la borne haute.
        colormap: le nom de la rampe de couleur.
        annoter: vrai pour écrire la valeur dans chaque case.
        decimales: le nombre de décimales des annotations.
        facteur: le facteur appliqué aux annotations, cent pour des points de
            pourcentage.

    Returns:
        L'image Matplotlib, à passer à ``colorbar``.
    """
    valeurs = table.to_numpy(dtype="float64")
    image = ax.imshow(valeurs, cmap=colormap, vmin=vmin, vmax=vmax, aspect="auto")
    ax.set_xticks(range(table.shape[1]))
    ax.set_xticklabels([str(c) for c in table.columns], rotation=0)
    ax.set_yticks(range(table.shape[0]))
    ax.set_yticklabels([str(i) for i in table.index])
    ax.grid(visible=False)
    if annoter:
        for i in range(table.shape[0]):
            for j in range(table.shape[1]):
                v = valeurs[i, j]
                if not np.isfinite(v):
                    continue
                rouge, vert, bleu, _ = image.cmap(image.norm(v))
                luminance = 0.299 * rouge + 0.587 * vert + 0.114 * bleu
                couleur = "white" if luminance < DARK_CELL_LUMINANCE else "black"
                ax.text(
                    j,
                    i,
                    gvf_style.fr(v * facteur, decimales),
                    ha="center",
                    va="center",
                    fontsize=BASE_FONT_SIZE - 3.0,
                    color=couleur,
                )
    return image


def equity_curve(
    returns_by_name: Mapping[str, ReturnSeries],
    *,
    log_scale: bool = True,
    benchmark: ReturnSeries | None = None,
    benchmark_label: str | None = None,
    initial: float = 1.0,
    currency: str = DEFAULT_CURRENCY,
    title: str | None = None,
    figsize: tuple[float, float] = DEFAULT_FIGSIZE,
) -> tuple[Figure, pd.DataFrame]:
    r"""Trace la richesse cumulée de plusieurs séries, et rend les courbes tracées.

    **Le problème.** Comparer des stratégies par leur rendement annuel cache la
    trajectoire. Deux séries au même rendement composé peuvent avoir passé des
    années à des niveaux très différents, et c'est la trajectoire que le lecteur
    doit voir.

    **L'intuition.** On place la même somme dans chaque série à la même date,
    puis on suit ce que cette somme devient. L'échelle logarithmique s'impose
    dès que le rapport entre le début et la fin dépasse un ordre de grandeur,
    car sur une échelle linéaire les premières années deviennent illisibles.

    .. math::

        W_t = W_0 \prod_{s \le t} (1 + r_s)

    **Les variables.** :math:`r_s` est le rendement SIMPLE de la période
    :math:`s`. :math:`W_0` est la mise de départ, l'argument ``initial``.
    :math:`W_t` est la richesse à la fin de la période :math:`t`, dans la devise
    ``currency``.

    **Les hypothèses.** Les rendements sont simples, nets de ce que l'appelant a
    voulu retirer, et les séries partagent la même devise. Aucune conversion de
    change n'est faite ici. Les séries sont réunies par leurs dates, sans
    remplissage : une série plus courte laisse un trou dans sa colonne.

    **La date de base.** Chaque courbe reçoit la mise ``initial`` à sa PREMIÈRE
    date observée. Quand les séries ne commencent pas le même jour, l'axe l'écrit
    et le titre le répète, car deux courbes de bases différentes ne se comparent
    pas. Une série qui démarre deux mois plus tard peut finir plus haut sans
    avoir mieux travaillé.

    **La provenance.** La courbe de richesse composée est la convention du GIPS
    Handbook, troisième édition, 2020, chapitre sur la présentation des
    performances. Le calcul lui-même vient de
    :func:`quantlab.analytics.returns.cumulative_wealth`.

    **Les limites.** La lecture d'une échelle logarithmique se trompe souvent de
    question : deux segments de même pente y portent le même RENDEMENT, non le
    même gain en dollars. La date de base est écrite sur l'axe pour cette
    raison, car la comparaison ne vaut qu'à mise égale.

    **Les alternatives.** Le rendement cumulé en points de pourcentage évite la
    devise, mais il perd le montant, donc l'ordre de grandeur des pertes. La
    richesse rapportée à celle du repère montre l'écart et cache le niveau.

    **Pourquoi cette forme ici.** Le laboratoire publie des verdicts hors
    échantillon, et un verdict se lit sur une trajectoire complète.

    **Comment vérifier.** La dernière valeur d'une colonne vaut
    ``initial * prod(1 + r)``, ce qu'un test recalcule avec ``numpy.cumprod``.

    Args:
        returns_by_name: les séries de rendements, une par nom de courbe.
        log_scale: vrai pour l'échelle logarithmique, écrite en toutes lettres
            dans la légende de l'axe.
        benchmark: un repère facultatif, tracé en noir et en trait tireté.
        benchmark_label: le nom du repère. Vaut le nom de la série, sinon
            ``DEFAULT_BENCHMARK_LABEL``.
        initial: la mise de départ, exprimée dans ``currency``.
        currency: la devise, portée par l'axe des ordonnées.
        title: un titre imposé. Sans lui, le titre est déduit des données.
        figsize: la taille de la figure, en pouces.

    Returns:
        La figure, et le tableau des richesses, une colonne par courbe et une
        ligne par date de l'union des index.

    Raises:
        ConfigError: si aucune série n'est fournie, si ``initial`` est nul ou
            négatif, ou si le nom du repère est déjà celui d'une stratégie.
        InsufficientDataError: si une série est vide après retrait des valeurs
            manquantes.
    """
    if not returns_by_name:
        raise ConfigError("equity_curve demande au moins une série")
    if initial <= 0.0:
        raise ConfigError(f"initial vaut {initial}, il doit être strictement positif")

    colonnes: dict[str, pd.Series] = {}
    for nom, serie in returns_by_name.items():
        colonnes[nom] = cumulative_wealth(_serie_propre(serie, nom=nom), initial=initial)
    etiquette_repere: str | None = None
    if benchmark is not None:
        etiquette_repere = benchmark_label or str(benchmark.name or DEFAULT_BENCHMARK_LABEL)
        if etiquette_repere in colonnes:
            # Sans cette garde, l'affectation qui suit écraserait la stratégie et le
            # lecteur verrait la courbe du repère sous le nom de la stratégie.
            raise ConfigError(
                f"le repère porte le nom {etiquette_repere!r}, déjà pris par une stratégie ; "
                f"passer benchmark_label pour le distinguer"
            )
        colonnes[etiquette_repere] = cumulative_wealth(
            _serie_propre(benchmark, nom=etiquette_repere), initial=initial
        )

    richesse = pd.concat(colonnes, axis=1).sort_index()
    debut, fin = _bornes_de_dates(richesse.index)
    # Chaque colonne est basée à sa PREMIÈRE date observée, non à la première date
    # de l'union. Écrire une date de base commune serait faux dès qu'une série
    # commence plus tard, et la comparaison des courbes ne serait plus à mise égale.
    premieres = {nom: richesse[nom].first_valid_index() for nom in richesse.columns}
    bases_communes = len(set(premieres.values())) == 1

    with portfolio_style():
        fig, ax = _nouvelle_figure(figsize)
        for nom in richesse.columns:
            if nom == etiquette_repere:
                ax.plot(
                    richesse.index,
                    richesse[nom],
                    label=nom,
                    color=gvf_style.GRIS,
                    linestyle="--",
                    linewidth=1.3,
                )
            else:
                ax.plot(richesse.index, richesse[nom], label=nom)
        if log_scale:
            ax.set_yscale("log")
        ax.yaxis.set_major_formatter(gvf_style.formateur(2))
        echelle = ", échelle logarithmique" if log_scale else ""
        mise = f"{gvf_style.fr(initial, 2)} {currency}"
        base = f"base {mise} au {debut}" if bases_communes else f"base {mise} au départ de chaque courbe"
        ax.set_ylabel(f"Richesse cumulée en {currency}\n{base}{echelle}")
        ax.set_xlabel("Date de fin de période")
        finales = richesse.ffill().iloc[-1]
        meilleure = str(finales.idxmax())
        avertissement = "" if bases_communes else ", dates de base différentes"
        ax.set_title(
            title
            or f"Richesse cumulée du {debut} au {fin}, {meilleure} finit à "
            f"{gvf_style.fr(float(finales.max()), 2)} {currency}{avertissement}"
        )
        ax.legend(loc="best")
    return fig, richesse


def underwater(
    returns: ReturnSeries,
    *,
    is_wealth: bool = False,
    title: str | None = None,
    figsize: tuple[float, float] = DEFAULT_FIGSIZE,
) -> tuple[Figure, pd.Series]:
    r"""Trace le repli depuis le sommet en aire, et rend la série tracée.

    **Le problème.** La volatilité compte les hausses comme les baisses, alors
    qu'un investisseur ne vit pas les deux de la même façon. Le repli depuis le
    sommet ne regarde que ce qui a été perdu par rapport au meilleur moment déjà
    vécu, et c'est ce chiffre qui décide d'un rachat.

    **L'intuition.** La courbe reste collée à zéro tant que la stratégie bat son
    record, et s'enfonce dès qu'elle décroche. La largeur d'un creux compte
    autant que sa profondeur, car elle mesure le temps passé sous l'eau.

    .. math::

        DD_t = \frac{W_t - \max_{s \le t} W_s}{\max_{s \le t} W_s}

    **Les variables.** :math:`W_t` est la richesse cumulée en fin de période
    :math:`t`, et :math:`DD_t` le repli, négatif ou nul, exprimé en fraction du
    sommet.

    **Les hypothèses.** Les observations sont ordonnées et sans trou de
    numéraire. La richesse est mesurée en fin de période, si bien qu'un creux
    survenu à l'intérieur d'une période n'est pas vu.

    **La provenance.** Chekhlov, Uryasev et Zabarankin (2005), « Drawdown
    measure in portfolio optimization », *International Journal of Theoretical
    and Applied Finance*, 8(1), 13-58. Le calcul vient de
    :func:`quantlab.analytics.drawdown.drawdown_series`.

    **Les limites.** Le repli maximal est une statistique d'ordre, donc très
    bruitée, et il croît avec la longueur de l'échantillon même sans changement
    de comportement.

    **Les alternatives.** L'indice d'Ulcer résume la même courbe en un nombre,
    et la table de ``drawdown_table`` en donne les épisodes datés.

    **Pourquoi cette forme ici.** L'aire montre d'un coup la durée passée sous
    l'eau, que ni le maximum ni l'indice d'Ulcer ne donnent.

    **Comment vérifier.** La valeur minimale de la série rendue vaut exactement
    ``max_drawdown`` du même intrant, ce qu'un test compare.

    Args:
        returns: les rendements simples, ou la richesse si ``is_wealth``.
        is_wealth: vrai quand l'entrée est déjà une courbe de richesse.
        title: un titre imposé. Sans lui, le titre est déduit des données.
        figsize: la taille de la figure, en pouces.

    Returns:
        La figure, et la série des replis, négative ou nulle, en fraction.

    Raises:
        InsufficientDataError: si la série est vide après retrait des valeurs
            manquantes.
    """
    propre = _serie_propre(returns, nom="returns")
    repli = drawdown_series(propre, is_wealth=is_wealth)
    pire = max_drawdown(propre, is_wealth=is_wealth)
    debut, fin = _bornes_de_dates(repli.index)

    with portfolio_style():
        fig, ax = _nouvelle_figure(figsize)
        ax.fill_between(repli.index, repli.to_numpy(), 0.0, color=gvf_style.OKABE_ITO[3], alpha=FILL_ALPHA)
        ax.plot(repli.index, repli, color=gvf_style.OKABE_ITO[3], linewidth=1.2)
        ax.axhline(0.0, color=gvf_style.GRIS, linewidth=0.8)
        ax.yaxis.set_major_formatter(_formateur_points_de_pourcentage(0))
        ax.set_ylabel("Repli depuis le sommet, en points de pourcentage")
        ax.set_xlabel("Date de fin de période")
        ax.set_title(
            title
            or f"Repli maximal de {gvf_style.fr(abs(pire) * 100.0, 1)} points de pourcentage, "
            f"du {debut} au {fin}"
        )
    return fig, repli


def _sharpe_glissant(serie: pd.Series, window: int, frequency: Frequency, risk_free: float) -> pd.Series:
    """Rend le ratio de Sharpe recalculé sur chaque fenêtre fermée.

    La boucle explicite remplace ``rolling.apply`` pour une raison de justesse :
    ``sharpe_ratio`` reçoit ainsi une série pandas complète, avec sa fréquence
    et son taux sans risque, et non un tableau nu privé de son contexte.

    La fenêtre est fermée à droite : la valeur écrite à la date ``t`` ne lit que
    les ``window`` observations qui finissent en ``t``, jamais la suivante.

    Une fenêtre sans dispersion, celle d'un fonds suspendu par exemple, n'a pas
    de ratio de Sharpe. ``sharpe_ratio`` lève alors, et la valeur manquante est
    écrite à sa place. Interrompre le tracé entier pour une fenêtre dégénérée
    priverait le lecteur des cinq mille autres.
    """
    valeurs = np.full(len(serie), np.nan)
    for fin in range(window, len(serie) + 1):
        tranche = serie.iloc[fin - window : fin]
        try:
            valeurs[fin - 1] = sharpe_ratio(tranche, frequency=frequency, risk_free=risk_free, annualize=True)
        except InsufficientDataError:
            valeurs[fin - 1] = np.nan
    return pd.Series(valeurs, index=serie.index, name="sharpe")


def _volatilite_glissante(serie: pd.Series, window: int, frequency: Frequency) -> pd.Series:
    """Rend la volatilité annualisée recalculée sur chaque fenêtre fermée.

    La fenêtre est fermée à droite : la valeur écrite à la date ``t`` ne lit que
    les ``window`` observations qui finissent en ``t``, jamais la suivante.
    """
    valeurs = np.full(len(serie), np.nan)
    for fin in range(window, len(serie) + 1):
        valeurs[fin - 1] = volatility(serie.iloc[fin - window : fin], frequency, annualize=True)
    return pd.Series(valeurs, index=serie.index, name="volatility")


def rolling_metric(
    returns: ReturnSeries,
    metric: RollingMetric = "sharpe",
    window: int = DEFAULT_ROLLING_WINDOW,
    *,
    frequency: Frequency = Frequency.DAILY,
    benchmark: ReturnSeries | None = None,
    risk_free: float = 0.0,
    title: str | None = None,
    figsize: tuple[float, float] = DEFAULT_FIGSIZE,
) -> tuple[Figure, pd.Series]:
    r"""Trace une métrique recalculée sur fenêtre glissante, et rend la série.

    **Le problème.** Un ratio de Sharpe unique sur vingt ans suppose que rien
    n'a bougé. Peu de stratégies tiennent cette promesse, et le chiffre
    d'ensemble cache aussi bien une dérive lente qu'un unique bon trimestre.

    **L'intuition.** On refait le même calcul sur les ``window`` dernières
    observations, à chaque date. La courbe obtenue montre quand la performance a
    changé, et l'ampleur de ses oscillations dit combien le chiffre d'ensemble
    est fragile.

    .. math::

        \widehat{SR}_t(w) = \frac{\bar{r}_{[t-w+1,\,t]} - r_f}
                                 {\hat{\sigma}_{[t-w+1,\,t]}} \sqrt{N}

    **Les variables.** :math:`w` est la fenêtre en observations, :math:`N` le
    nombre de périodes par an de ``frequency``, :math:`r_f` le taux sans risque.
    Le bêta glissant remplace ce rapport par celui de la covariance à la
    variance du repère.

    **Les hypothèses.** La fenêtre est fermée à droite, donc aucune valeur n'est
    rendue avant la ``window``-ième observation, et la valeur de la date ``t`` ne
    lit rien après ``t``. Les rendements sont simples et de fréquence constante,
    sinon l'annualisation est fausse. Une fenêtre sans dispersion rend une valeur
    manquante plutôt que d'interrompre le tracé.

    **Les valeurs manquantes sont retirées avant le calcul.** La fenêtre compte
    donc des OBSERVATIONS et non des jours de calendrier. Sur une série trouée,
    une fenêtre de 252 couvre plus d'une année civile, et l'annualisation par
    252 sous-estime alors la durée réellement parcourue.

    **La provenance.** Le ratio vient de Sharpe (1966), « Mutual fund
    performance », *Journal of Business*, 39(1), 119-138. Le bêta glissant vient
    de :func:`quantlab.analytics.regression.rolling_beta`.

    **Les limites.** Une fenêtre glissante est un filtre : elle produit des
    oscillations lentes même sur du bruit indépendant, et l'oeil y voit des
    régimes qui n'existent pas. La fenêtre choisie décide de ce qu'on voit.

    **Les alternatives.** Le découpage en sous-périodes fixes de
    ``validation.robustness.subperiod_performance`` publie une erreur type à
    côté de chaque point, ce qu'une courbe glissante ne fait pas.

    **Pourquoi cette forme ici.** Elle situe dans le temps les épisodes que le
    découpage en tranches agrège.

    **Comment vérifier.** À la dernière date d'une série de longueur ``window``,
    la valeur rendue égale la métrique calculée sur l'échantillon entier. Et
    remplacer toutes les observations postérieures à une date par n'importe quoi
    laisse la courbe inchangée jusqu'à cette date, ce qu'un test mesure.

    Args:
        returns: les rendements simples de la stratégie.
        metric: ``"sharpe"``, ``"volatility"`` ou ``"beta"``.
        window: la longueur de la fenêtre, en observations.
        frequency: la fréquence des rendements, pour l'annualisation.
        benchmark: le repère, exigé par ``"beta"`` et ignoré sinon.
        risk_free: le taux sans risque annuel, utilisé par ``"sharpe"``.
        title: un titre imposé. Sans lui, le titre est déduit des données.
        figsize: la taille de la figure, en pouces.

    Returns:
        La figure, et la série de la métrique, valeurs manquantes comprises sur
        les premières dates.

    Raises:
        ConfigError: métrique inconnue, fenêtre inférieure à deux, ou ``"beta"``
            demandé sans repère.
        InsufficientDataError: si la série est plus courte que la fenêtre.
    """
    if window < 2:
        raise ConfigError(f"window vaut {window}, il en faut au moins deux")
    propre = _serie_propre(returns, nom="returns", minimum=window)

    if metric == "sharpe":
        serie = _sharpe_glissant(propre, window, frequency, risk_free)
        etiquette = "Ratio de Sharpe annualisé"
        formateur = gvf_style.formateur(2)
    elif metric == "volatility":
        serie = _volatilite_glissante(propre, window, frequency)
        etiquette = "Volatilité annualisée, en points de pourcentage"
        formateur = _formateur_points_de_pourcentage(0)
    elif metric == "beta":
        if benchmark is None:
            raise ConfigError("le bêta glissant demande un repère")
        serie = rolling_beta(propre, _serie_propre(benchmark, nom="benchmark"), window)
        serie.name = "beta"
        etiquette = "Bêta contre le repère"
        formateur = gvf_style.formateur(2)
    else:
        raise ConfigError(f"métrique inconnue : {metric!r}")

    valides = serie.dropna()
    debut, fin = _bornes_de_dates(serie.index)

    with portfolio_style():
        fig, ax = _nouvelle_figure(figsize)
        ax.plot(serie.index, serie, color=gvf_style.OKABE_ITO[0])
        if len(valides) > 0:
            mediane = float(valides.median())
            ax.axhline(mediane, color=gvf_style.GRIS, linewidth=0.9, linestyle=":")
            resume = f"médiane {gvf_style.fr(mediane, 2)}"
        else:
            resume = "aucune valeur calculable"
        ax.yaxis.set_major_formatter(formateur)
        ax.set_ylabel(etiquette)
        ax.set_xlabel("Date de fin de fenêtre")
        ax.set_title(
            title
            or f"{etiquette.split(',')[0]} sur {window} observations glissantes, {resume}, "
            f"du {debut} au {fin}"
        )
    return fig, serie


def monthly_returns_heatmap(
    returns: ReturnSeries,
    *,
    already_monthly: bool = False,
    title: str | None = None,
    figsize: tuple[float, float] = DEFAULT_FIGSIZE,
) -> tuple[Figure, pd.DataFrame]:
    r"""Trace la grille des rendements mensuels, années en lignes, et la rend.

    **Le problème.** Une courbe de richesse montre la tendance et cache la
    saisonnalité, les mois catastrophiques et les longues séries plates. La
    grille montre les trois d'un coup.

    **L'intuition.** Chaque case porte le rendement composé d'un mois. La
    couleur donne le signe et l'ampleur, le nombre donne la valeur exacte, et
    l'oeil parcourt une ligne pour lire une année.

    .. math::

        R_{a,m} = \prod_{t \in (a,m)} (1 + r_t) - 1

    **Les variables.** :math:`a` est l'année, :math:`m` le mois, :math:`r_t` le
    rendement simple d'une période fine contenue dans ce mois.

    **Les hypothèses.** Les bornes de mois sont celles du calendrier, comme dans
    pandas. Un mois incomplet en début ou en fin d'échantillon est agrégé tel
    quel, donc sa case couvre moins de jours que les autres.

    **La provenance.** L'agrégation temporelle vient de
    :func:`quantlab.analytics.returns.resample_returns`, elle-même conforme à
    Campbell, Lo et MacKinlay (1997), *The Econometrics of Financial Markets*.

    **Les limites.** La grille donne autant de place à un mois de crise qu'à un
    mois ordinaire, ce qui exagère les épisodes courts. Elle ne dit rien de la
    composition dans le temps, qu'un lecteur pressé additionne à tort.

    **Les alternatives.** Un histogramme des rendements mensuels donne la
    distribution et perd la date. La grille garde la date et perd la forme.

    **Pourquoi cette forme ici.** Les verdicts du laboratoire portent souvent
    sur une poignée de mois, et la grille les rend repérables.

    **Comment vérifier.** Le produit des cases d'une année, augmentées de un,
    égale le rendement composé de cette année.

    Args:
        returns: les rendements simples, de fréquence quelconque.
        already_monthly: vrai si la série est déjà mensuelle, ce qui évite une
            agrégation sans effet.
        title: un titre imposé. Sans lui, le titre est déduit des données.
        figsize: la taille de la figure, en pouces.

    Returns:
        La figure, et le tableau des rendements en fraction, années en index et
        numéros de mois en colonnes, de 1 à 12.

    Raises:
        DataQualityError: si l'index n'est pas un index de dates, ou si deux
            observations tombent dans le même mois.
        InsufficientDataError: si la série est vide.
    """
    propre = _serie_propre(returns, nom="returns")
    if not isinstance(propre.index, pd.DatetimeIndex):
        raise DataQualityError("monthly_returns_heatmap demande un index de dates")
    mensuel = propre if already_monthly else resample_returns(propre, Frequency.MONTHLY)

    grille = pd.DataFrame(
        {
            "year": mensuel.index.year,
            "month": mensuel.index.month,
            "value": mensuel.to_numpy(dtype="float64"),
        }
    )
    if grille.duplicated(subset=["year", "month"]).any():
        # Le cas se produit quand `already_monthly` est posé à tort sur une série
        # plus fine. Sans cette garde, pandas lève un ValueError nu, que l'appelant
        # ne peut pas rattacher à sa cause.
        raise DataQualityError(
            "deux observations tombent dans le même mois : la série n'est pas mensuelle, "
            "et already_monthly ne doit pas être posé"
        )
    # `pivot` et non `pivot_table` : le second agrège en silence quand un couple se répète,
    # ce qui masquerait un index de dates portant deux fois le même mois.
    table = grille.pivot(index="year", columns="month", values="value")  # noqa: PD010
    table = table.reindex(columns=range(1, 13))
    table.index.name = None
    table.columns.name = None

    fini = table.to_numpy(dtype="float64")
    amplitude = float(np.nanmax(np.abs(fini))) if np.isfinite(fini).any() else 1.0
    amplitude = amplitude if amplitude > 0.0 else 1.0
    meilleur = float(np.nanmax(fini)) if np.isfinite(fini).any() else float("nan")
    pire = float(np.nanmin(fini)) if np.isfinite(fini).any() else float("nan")

    with portfolio_style():
        fig, ax = _nouvelle_figure(figsize)
        image = _carte_de_chaleur(
            ax,
            table,
            vmin=-amplitude,
            vmax=amplitude,
            colormap=DIVERGING_COLORMAP,
            annoter=table.size <= MAX_ANNOTATED_CELLS,
            decimales=1,
            facteur=100.0,
        )
        barre = fig.colorbar(image, ax=ax)
        barre.ax.yaxis.set_major_formatter(_formateur_points_de_pourcentage(0))
        barre.set_label("Rendement du mois, en points de pourcentage")
        ax.set_xlabel("Mois")
        ax.set_ylabel("Année")
        ax.set_title(
            title
            or f"Rendements mensuels de {table.index[0]} à {table.index[-1]}, "
            f"du meilleur mois à {gvf_style.fr(meilleur * 100.0, 1)} au pire à "
            f"{gvf_style.fr(pire * 100.0, 1)} points de pourcentage"
        )
    return fig, table


@dataclass(frozen=True)
class HistogramData:
    """Les nombres dessinés par :func:`return_histogram`.

    Attributes:
        counts: l'effectif de chaque classe, entier.
        edges: les bornes des classes, de longueur ``len(counts) + 1``.
        density: l'effectif ramené à une densité, effectif divisé par le produit
            du nombre d'observations et de la largeur de classe.
        mean: la moyenne de l'échantillon.
        std: l'écart type de l'échantillon, à un degré de liberté près.
        normal_curve: la densité normale de mêmes moyenne et écart type, indexée
            par la grille où elle a été évaluée. Vaut ``None`` sans superposition.
    """

    counts: np.ndarray
    edges: np.ndarray
    density: np.ndarray
    mean: float
    std: float
    normal_curve: pd.Series | None


def return_histogram(
    returns: ReturnSeries,
    bins: int = DEFAULT_HISTOGRAM_BINS,
    *,
    overlay_normal: bool = True,
    title: str | None = None,
    figsize: tuple[float, float] = DEFAULT_FIGSIZE,
) -> tuple[Figure, HistogramData]:
    r"""Trace la distribution des rendements, et rend les effectifs dessinés.

    **Le problème.** Le ratio de Sharpe résume une distribution par ses deux
    premiers moments. Si la distribution a une queue gauche épaisse, ce résumé
    ment, et l'histogramme est le moyen le plus direct de le voir.

    **L'intuition.** On compte combien d'observations tombent dans chaque
    tranche de rendement, puis on superpose la loi normale de mêmes moyenne et
    écart type. L'écart entre les barres et la courbe est exactement ce que le
    ratio de Sharpe ignore.

    .. math::

        f(x) = \frac{1}{\hat{\sigma}\sqrt{2\pi}}
               \exp\left(-\frac{(x - \bar{r})^2}{2\hat{\sigma}^2}\right)

    **Les variables.** :math:`\bar{r}` est la moyenne de l'échantillon,
    :math:`\hat{\sigma}` son écart type à un degré de liberté près, et
    :math:`f` la densité tracée par dessus les barres.

    **Les hypothèses.** Les barres sont des densités, non des effectifs, faute
    de quoi la courbe normale ne serait pas à la même échelle. Les classes sont
    de largeur égale, entre le minimum et le maximum observés.

    **La provenance.** La superposition d'une normale ajustée est la pratique
    courante depuis Mandelbrot (1963), « The variation of certain speculative
    prices », *Journal of Business*, 36(4), 394-419. Il en tire le rejet de la
    normalité des rendements.

    **Les limites.** Le nombre de classes change ce que l'oeil voit, et aucune
    règle ne le fixe. Un histogramme ne teste rien : le rejet de la normalité se
    prononce par un test, pas par un dessin.

    **Les alternatives.** Le graphique quantile contre quantile de
    :func:`qq_plot` montre les queues bien mieux, l'histogramme les écrasant.

    **Pourquoi cette forme ici.** Elle donne le centre et le mode, que le
    graphique des quantiles rend illisibles.

    **Comment vérifier.** La somme des effectifs égale le nombre d'observations,
    et la densité au point moyen vaut l'inverse du produit de l'écart type par
    la racine de deux fois pi.

    Args:
        returns: les rendements simples.
        bins: le nombre de classes.
        overlay_normal: vrai pour superposer la densité normale ajustée.
        title: un titre imposé. Sans lui, le titre est déduit des données.
        figsize: la taille de la figure, en pouces.

    Returns:
        La figure, et les nombres dessinés dans un :class:`HistogramData`.

    Raises:
        ConfigError: si ``bins`` est inférieur à un.
        InsufficientDataError: si la série porte moins de deux observations.
    """
    if bins < 1:
        raise ConfigError(f"bins vaut {bins}, il en faut au moins une")
    propre = _serie_propre(returns, nom="returns", minimum=2)
    valeurs = propre.to_numpy(dtype="float64")

    effectifs, bornes = np.histogram(valeurs, bins=bins)
    largeurs = np.diff(bornes)
    densite = effectifs / (len(valeurs) * largeurs)
    moyenne = float(np.mean(valeurs))
    ecart_type = float(np.std(valeurs, ddof=1))

    courbe: pd.Series | None = None
    if overlay_normal and not _est_constant(valeurs, ecart_type):
        grille = np.linspace(bornes[0], bornes[-1], NORMAL_CURVE_POINTS)
        courbe = pd.Series(stats.norm.pdf(grille, loc=moyenne, scale=ecart_type), index=grille)

    aplatissement = kurtosis(propre, excess=True)

    with portfolio_style():
        fig, ax = _nouvelle_figure(figsize)
        ax.bar(
            bornes[:-1],
            densite,
            width=largeurs,
            align="edge",
            color=gvf_style.OKABE_ITO[0],
            alpha=0.8,
        )
        if courbe is not None:
            ax.plot(
                courbe.index, courbe.to_numpy(), color=gvf_style.OKABE_ITO[3], label="Loi normale ajustée"
            )
            ax.legend(loc="best")
        ax.xaxis.set_major_formatter(_formateur_points_de_pourcentage(1))
        ax.set_xlabel("Rendement de la période, en points de pourcentage")
        ax.set_ylabel("Densité")
        ax.set_title(
            title
            or f"Distribution de {len(valeurs)} rendements, aplatissement excédentaire "
            f"{gvf_style.fr(aplatissement, 2)}"
        )
    return fig, HistogramData(
        counts=effectifs,
        edges=bornes,
        density=densite,
        mean=moyenne,
        std=ecart_type,
        normal_curve=courbe,
    )


def qq_plot(
    returns: ReturnSeries,
    *,
    title: str | None = None,
    figsize: tuple[float, float] = DEFAULT_FIGSIZE,
) -> tuple[Figure, pd.DataFrame]:
    r"""Trace les quantiles observés contre les quantiles normaux, et les rend.

    **Le problème.** L'histogramme écrase les queues, là où se joue le risque de
    ruine. Il faut une représentation qui donne autant de place à la centième
    observation qu'à la médiane.

    **L'intuition.** On trie les rendements, on les compare au quantile que la
    loi normale aurait donné au même rang, et on regarde si les points suivent
    la première bissectrice. Un point qui s'en écarte vers le bas à gauche
    signale une queue gauche plus épaisse que la normale.

    .. math::

        q_i = \Phi^{-1}\!\left(\frac{i - 0{,}5}{n}\right),
        \qquad
        z_{(i)} = \frac{r_{(i)} - \bar{r}}{\hat{\sigma}}

    **Les variables.** :math:`\Phi^{-1}` est la fonction quantile de la loi
    normale centrée réduite, :math:`r_{(i)}` la :math:`i`-ième valeur triée, et
    :math:`z_{(i)}` la même valeur centrée réduite.

    **Les hypothèses.** La position de tracé retenue est :math:`(i - 0,5)/n`,
    dite de Hazen. Les données sont centrées et réduites, si bien que la droite
    de référence est la première bissectrice et non une droite ajustée.

    **La provenance.** Wilk et Gnanadesikan (1968), « Probability plotting
    methods for the analysis of data », *Biometrika*, 55(1), 1-17. La position
    retenue est celle de Hazen (1914). Mesuré le 2026-09-02 :
    ``scipy.stats.probplot`` emploie une autre position, celle de Filliben, et
    ses quantiles s'écartent des nôtres de 0,106 sur deux cents points.
    ``statsmodels.graphics.gofplots.ProbPlot`` avec ``a=0,5`` donne la position
    de Hazen, et sert de contrôle indépendant dans les tests.

    **Les limites.** Les points extrêmes sont eux-mêmes très bruités : le
    dernier point bouge beaucoup d'un échantillon à l'autre, même sous
    normalité. Le graphique suggère, il ne conclut pas.

    **Les alternatives.** Le test de Jarque et Bera donne une valeur p et perd
    la forme de l'écart, qui dit de quel côté la queue est épaisse.

    **Pourquoi cette forme ici.** Le laboratoire mesure des queues avant de
    poser une valeur à risque, et la forme de l'écart oriente le choix.

    **Comment vérifier.** Les quantiles théoriques rendus égalent ceux de
    ``statsmodels.graphics.gofplots.ProbPlot`` réglé sur la position de Hazen.

    Args:
        returns: les rendements simples.
        title: un titre imposé. Sans lui, le titre est déduit des données.
        figsize: la taille de la figure, en pouces.

    Returns:
        La figure, et un tableau à deux colonnes, ``theoretical`` et ``sample``,
        trié par quantile croissant.

    Raises:
        InsufficientDataError: si la série porte moins de deux observations.
        DataQualityError: si l'échantillon est constant, donc sans écart type.
    """
    propre = _serie_propre(returns, nom="returns", minimum=2)
    valeurs = np.sort(propre.to_numpy(dtype="float64"))
    n = len(valeurs)
    ecart_type = float(np.std(valeurs, ddof=1))
    if _est_constant(valeurs, ecart_type):
        raise DataQualityError("qq_plot demande un échantillon non constant")

    positions = (np.arange(1, n + 1) - 0.5) / n
    theoriques = stats.norm.ppf(positions)
    reduites = (valeurs - float(np.mean(valeurs))) / ecart_type
    table = pd.DataFrame({"theoretical": theoriques, "sample": reduites})
    aplatissement = kurtosis(propre, excess=True)

    with portfolio_style():
        fig, ax = _nouvelle_figure(figsize)
        ax.scatter(theoriques, reduites, s=12.0, color=gvf_style.OKABE_ITO[0])
        borne = float(max(abs(theoriques[0]), abs(theoriques[-1]), abs(reduites).max()))
        ax.plot([-borne, borne], [-borne, borne], color=gvf_style.GRIS, linewidth=1.0, linestyle="--")
        ax.set_xlabel("Quantile de la loi normale centrée réduite")
        ax.set_ylabel("Quantile observé, centré et réduit")
        ax.set_title(
            title
            or f"Quantiles observés contre normaux, {n} observations, aplatissement excédentaire "
            f"{gvf_style.fr(aplatissement, 2)}"
        )
    return fig, table


@dataclass(frozen=True)
class QuantileBars:
    """Les nombres dessinés par :func:`quantile_bars`.

    Attributes:
        means: le rendement moyen par période de chaque quantile, indexé par le
            nom de colonne du tri.
        spread_mean: le rendement moyen de la colonne d'écart, quand elle
            existe, sinon ``None``.
        monotone: vrai si les moyennes croissent faiblement du premier au
            dernier quantile, ce qu'un signal utile fait.
    """

    means: pd.Series
    spread_mean: float | None
    monotone: bool


def quantile_bars(
    quantile_returns: ReturnFrame,
    *,
    spread_column: str = "spread",
    title: str | None = None,
    figsize: tuple[float, float] = DEFAULT_FIGSIZE,
) -> tuple[Figure, QuantileBars]:
    r"""Trace le rendement moyen par quantile de signal, et rend ces moyennes.

    **Le problème.** Le coefficient d'information dit que l'ordre est bon, il ne
    dit pas combien un gérant encaisse, ni si le gain vient des meilleurs
    signaux ou seulement des pires. Le tri par quantiles répond aux deux.

    **L'intuition.** On achète le paquet des meilleurs signaux, on vend celui
    des pires, et on regarde ce que rapporte chaque paquet. Une progression
    régulière du premier au dernier quantile vaut mieux qu'un écart porté par
    une seule extrémité, car elle survit plus souvent hors échantillon.

    .. math::

        \bar{r}^{(q)} = \frac{1}{T} \sum_{t=1}^{T} r^{(q)}_t

    **Les variables.** :math:`r^{(q)}_t` est le rendement du quantile :math:`q`
    à la date :math:`t`, :math:`T` le nombre de dates.

    **Les hypothèses.** Le tableau reçu vient de
    :func:`quantlab.analytics.ic.quantile_returns`, ses colonnes sont ordonnées
    du premier au dernier quantile, et la colonne d'écart vient en dernier. La
    moyenne est arithmétique, non composée, donc elle ne se lit pas comme un
    rendement encaissé sur toute la période.

    **La provenance.** Le tri par quantiles est la méthode de Fama et French
    (1992), « The cross-section of expected stock returns », *Journal of
    Finance*, 47(2), 427-465.

    **Les limites.** Le tri jette l'information sur l'ampleur du signal à
    l'intérieur d'un paquet, et le nombre de quantiles change le résultat. Une
    moyenne simple ne dit rien de la dispersion, que la barre ne montre pas.

    **Les alternatives.** Le coefficient d'information garde l'ampleur du signal
    et perd le rendement en dollars.

    **Pourquoi cette forme ici.** La monotonie se lit d'un coup d'oeil sur des
    barres, et c'est elle qui distingue un signal d'un artefact d'extrémité.

    **Comment vérifier.** Chaque barre égale la moyenne arithmétique de sa
    colonne, ce qu'un test recalcule à la main sur un petit tableau.

    Args:
        quantile_returns: le tableau des rendements par quantile, dates en
            lignes et quantiles en colonnes.
        spread_column: le nom de la colonne d'écart, exclue des barres.
        title: un titre imposé. Sans lui, le titre est déduit des données.
        figsize: la taille de la figure, en pouces.

    Returns:
        La figure, et les moyennes dans un :class:`QuantileBars`.

    Raises:
        ConfigError: si le tableau ne porte aucune colonne de quantile.
        DataQualityError: si un quantile n'a pas de moyenne finie.
        InsufficientDataError: si le tableau est vide.
    """
    if not isinstance(quantile_returns, pd.DataFrame):
        raise ConfigError("quantile_returns doit être un tableau pandas")
    if len(quantile_returns) == 0:
        raise InsufficientDataError("quantile_returns est vide")
    colonnes = [c for c in quantile_returns.columns if c != spread_column]
    if not colonnes:
        raise ConfigError("aucune colonne de quantile en dehors de la colonne d'écart")

    moyennes = quantile_returns[colonnes].mean()
    valeurs = moyennes.to_numpy(dtype="float64")
    if not np.all(np.isfinite(valeurs)):
        # Une comparaison à une valeur manquante rend faux, donc un quantile vide
        # faisait écrire « progression irrégulière » au titre. Le dessin aurait
        # affirmé quelque chose du signal à partir d'un trou dans les données.
        vides = [str(c) for c, v in zip(colonnes, valeurs, strict=True) if not np.isfinite(v)]
        raise DataQualityError(f"quantiles sans moyenne finie : {vides}")
    ecart = float(quantile_returns[spread_column].mean()) if spread_column in quantile_returns else None
    monotone = bool(np.all(np.diff(valeurs) >= 0.0))

    with portfolio_style():
        fig, ax = _nouvelle_figure(figsize)
        couleurs = [gvf_style.OKABE_ITO[2] if v >= 0.0 else gvf_style.OKABE_ITO[3] for v in valeurs]
        ax.bar([str(c) for c in colonnes], valeurs, color=couleurs, width=0.62)
        ax.axhline(0.0, color=gvf_style.GRIS, linewidth=0.8)
        ax.yaxis.set_major_formatter(_formateur_points_de_pourcentage(2))
        ax.set_ylabel("Rendement moyen par période, en points de pourcentage")
        ax.set_xlabel("Quantile de signal, du plus faible au plus fort")
        mention = "progression régulière" if monotone else "progression irrégulière"
        if ecart is None:
            fin_titre = mention
        else:
            fin_titre = f"écart de {gvf_style.fr(ecart * 100.0, 2)} points de pourcentage, {mention}"
        ax.set_title(title or f"Rendement moyen par quantile sur {len(quantile_returns)} dates, {fin_titre}")
    return fig, QuantileBars(means=moyennes, spread_mean=ecart, monotone=monotone)


def ic_timeseries(
    ic: pd.Series,
    *,
    window: int = DEFAULT_IC_WINDOW,
    title: str | None = None,
    figsize: tuple[float, float] = DEFAULT_FIGSIZE,
) -> tuple[Figure, pd.DataFrame]:
    r"""Trace le coefficient d'information dans le temps, et rend les deux séries.

    **Le problème.** Un coefficient d'information moyen de 0,03 se lit comme une
    petite information stable. Il peut aussi bien recouvrir deux années fortes
    et huit années nulles, ce que la moyenne ne dit jamais.

    **L'intuition.** On trace la valeur de chaque date, puis sa moyenne mobile.
    Les barres donnent le bruit, la ligne donne la tendance, et la ligne
    horizontale donne la moyenne d'ensemble à laquelle tout se compare.

    .. math::

        \overline{IC}_t(w) = \frac{1}{w} \sum_{s=t-w+1}^{t} IC_s

    **Les variables.** :math:`IC_s` est le coefficient de la date :math:`s`,
    :math:`w` la fenêtre en dates.

    **Les hypothèses.** Les dates sont ordonnées et régulièrement espacées, sans
    quoi la fenêtre en nombre de dates ne correspond à aucune durée. Les valeurs
    manquantes, aux dates où l'univers est trop mince, sont laissées telles
    quelles et interrompent la moyenne mobile.

    **La provenance.** Grinold et Kahn (1999), *Active Portfolio Management*,
    deuxième édition, chapitre 6. La série vient de
    :func:`quantlab.analytics.ic.ic_series`.

    **Les limites.** La moyenne mobile lisse aussi du bruit indépendant et
    fabrique des régimes apparents. La moyenne d'ensemble est elle-même bruitée,
    et son erreur type se lit dans ``ic_summary``, pas ici.

    **Les alternatives.** ``rolling_ic`` rend la même série lissée avec son
    erreur type, à préférer dès qu'il faut conclure.

    **Pourquoi cette forme ici.** Elle situe dans le temps ce que le résumé
    agrège, avant toute conclusion.

    **Comment vérifier.** La moyenne mobile à la dernière date égale la moyenne
    arithmétique des ``window`` dernières valeurs.

    Args:
        ic: la série des coefficients d'information, une valeur par date.
        window: la fenêtre de la moyenne mobile, en dates.
        title: un titre imposé. Sans lui, le titre est déduit des données.
        figsize: la taille de la figure, en pouces.

    Returns:
        La figure, et un tableau à deux colonnes, ``ic`` et ``rolling_mean``.

    Raises:
        ConfigError: si la fenêtre est inférieure à deux.
        InsufficientDataError: si la série est vide après retrait des valeurs
            manquantes.
    """
    if window < 2:
        raise ConfigError(f"window vaut {window}, il en faut au moins deux")
    if not isinstance(ic, pd.Series):
        raise ConfigError("ic doit être une série pandas")
    if len(ic.dropna()) == 0:
        raise InsufficientDataError("la série de coefficients est vide")

    serie = ic.astype("float64")
    lissee = serie.rolling(window=window, min_periods=window).mean()
    table = pd.DataFrame({"ic": serie, "rolling_mean": lissee})
    moyenne = float(serie.mean())
    part_positive = float((serie.dropna() > 0.0).mean())
    debut, fin = _bornes_de_dates(serie.index)

    with portfolio_style():
        fig, ax = _nouvelle_figure(figsize)
        couleurs = [
            gvf_style.OKABE_ITO[2] if v >= 0.0 else gvf_style.OKABE_ITO[3]
            for v in serie.fillna(0.0).to_numpy(dtype="float64")
        ]
        ax.bar(
            serie.index,
            serie.to_numpy(dtype="float64"),
            color=couleurs,
            width=_largeur_de_barre(serie.index),
        )
        ax.plot(
            table.index,
            table["rolling_mean"],
            color=gvf_style.OKABE_ITO[0],
            label=f"Moyenne mobile sur {window} dates",
        )
        ax.axhline(moyenne, color=gvf_style.GRIS, linewidth=0.9, linestyle=":")
        ax.axhline(0.0, color=gvf_style.GRIS, linewidth=0.8)
        ax.yaxis.set_major_formatter(gvf_style.formateur(2))
        ax.set_ylabel("Coefficient d'information, sans unité")
        ax.set_xlabel("Date du signal")
        ax.legend(loc="best")
        ax.set_title(
            title
            or f"Coefficient d'information du {debut} au {fin}, moyenne "
            f"{gvf_style.fr(moyenne, 3)} et {gvf_style.fr(part_positive * 100.0, 0)} pour cent "
            f"de dates positives"
        )
    return fig, table


def parameter_heatmap(
    sweep_df: pd.DataFrame,
    x: str,
    y: str,
    metric: str,
    *,
    x_label: str | None = None,
    y_label: str | None = None,
    metric_label: str | None = None,
    title: str | None = None,
    figsize: tuple[float, float] = DEFAULT_FIGSIZE,
) -> tuple[Figure, pd.DataFrame]:
    r"""Trace la carte de robustesse d'un balayage, et rend la table pivotée.

    **Le problème.** Une étude qui publie sa meilleure configuration ne dit pas
    si le voisinage de cette configuration tient. Un maximum isolé décrit le
    bruit de l'échantillon, un plateau décrit peut-être un mécanisme, et les
    deux portent le même chiffre.

    **L'intuition.** On étale la grille en deux dimensions et on colore la
    métrique. Une tache large et continue est un plateau, une case brillante
    entourée de cases sombres est un pic, et l'oeil fait la différence plus vite
    que n'importe quel résumé.

    .. math::

        M(i, j) = m\big(\theta_x = g_i,\ \theta_y = h_j\big)

    **Les variables.** :math:`g_i` et :math:`h_j` sont les valeurs balayées des
    deux paramètres, :math:`m` la métrique évaluée par le balayage.

    **Les hypothèses.** Chaque couple de valeurs apparaît une fois et une seule
    dans le tableau. Si le balayage porte sur plus de deux paramètres, les
    autres axes doivent être filtrés avant l'appel, sinon le couple se répète.

    **La provenance.** La lecture par plateau vient de Bailey, Borwein, Lopez de
    Prado et Zhu (2014), « Pseudo-mathematics and financial charlatanism »,
    *Notices of the AMS*, 61(5), 458-471. Le balayage vient de
    :func:`quantlab.validation.robustness.parameter_sweep`, et
    ``plateau_score`` note ce que la carte montre.

    **L'échelle de couleur.** Elle se déduit des données. Une métrique qui change
    de signe reçoit une rampe divergente centrée sur zéro, une métrique d'un seul
    signe reçoit une rampe séquentielle bornée par ses extrêmes. Mesuré le
    2026-09-02 : sur un balayage dont le ratio net va de 0,80 à 1,04, la rampe
    symétrique n'occupait que 11,5 pour cent de sa plage, et les vingt-cinq cases
    paraissaient identiques.

    **Les limites.** La carte ne corrige rien : elle montre le nombre d'essais
    sans le déduire du ratio publié, ce que fait le ratio de Sharpe dégonflé.
    L'échelle de couleur choisie change fortement l'impression de plateau.

    **Les alternatives.** ``plateau_score`` rend un nombre par point, donc un
    classement défendable, là où la carte rend une impression.

    **Pourquoi cette forme ici.** Elle sert de contrôle visuel avant le calcul,
    et elle attrape les grilles mal construites que le score ne signale pas.

    **Comment vérifier.** Chaque case de la table rendue égale la ligne du
    balayage qui porte le même couple de paramètres, et le titre ne compte que
    les cases effectivement mesurées.

    Args:
        sweep_df: le tableau du balayage, une ligne par combinaison.
        x: le nom de la colonne portée par l'axe des abscisses.
        y: le nom de la colonne portée par l'axe des ordonnées.
        metric: le nom de la colonne de la métrique.
        x_label: l'étiquette lisible de l'axe des abscisses. Sans elle, le nom
            de colonne est rendu lisible en retirant les soulignés.
        y_label: l'étiquette lisible de l'axe des ordonnées.
        metric_label: l'étiquette lisible de la métrique.
        title: un titre imposé. Sans lui, le titre est déduit des données.
        figsize: la taille de la figure, en pouces.

    Returns:
        La figure, et la table pivotée, valeurs de ``y`` en index et valeurs de
        ``x`` en colonnes.

    Raises:
        ConfigError: si une colonne demandée manque.
        DataQualityError: si un couple de paramètres apparaît deux fois.
        InsufficientDataError: si le tableau est vide.
    """
    manquantes = [c for c in (x, y, metric) if c not in sweep_df.columns]
    if manquantes:
        raise ConfigError(f"colonnes absentes du balayage : {manquantes}")
    if len(sweep_df) == 0:
        raise InsufficientDataError("le balayage est vide")
    if sweep_df.duplicated(subset=[x, y]).any():
        raise DataQualityError(f"un couple ({x}, {y}) apparaît plusieurs fois dans le balayage")

    # `pivot` et non `pivot_table` : les doublons sont refusés au-dessus plutôt
    # que moyennés en silence, ce qui rendrait une case fausse sans le dire.
    table = sweep_df.pivot(index=y, columns=x, values=metric).sort_index()  # noqa: PD010
    table = table.reindex(columns=sorted(table.columns))
    valeurs = table.to_numpy(dtype="float64")
    if not np.isfinite(valeurs).any():
        raise DataQualityError("la métrique ne porte aucune valeur finie")
    maximum = float(np.nanmax(valeurs))
    mediane = float(np.nanmedian(valeurs))
    # Le nombre de cases de la table n'est PAS le nombre de combinaisons mesurées :
    # une grille incomplète laisse des cases vides, que le titre comptait à tort.
    mesurees = int(np.isfinite(valeurs).sum())
    basse, haute, rampe = _echelle_de_couleur(valeurs)

    nom_metrique = metric_label or _humaniser(metric)

    with portfolio_style():
        fig, ax = _nouvelle_figure(figsize)
        image = _carte_de_chaleur(
            ax,
            table,
            vmin=basse,
            vmax=haute,
            colormap=rampe,
            annoter=table.size <= MAX_ANNOTATED_CELLS,
            decimales=2,
            facteur=1.0,
        )
        barre = fig.colorbar(image, ax=ax)
        barre.set_label(nom_metrique)
        ax.set_xlabel(x_label or _humaniser(x))
        ax.set_ylabel(y_label or _humaniser(y))
        ax.set_title(
            title
            or f"{nom_metrique} sur {mesurees} combinaisons mesurées, maximum "
            f"{gvf_style.fr(maximum, 2)} contre une médiane de {gvf_style.fr(mediane, 2)}"
        )
    return fig, table


def cost_sensitivity(
    multipliers: Sequence[float],
    net_sharpe: Sequence[float],
    *,
    threshold: float = 0.0,
    metric_label: str = "Ratio de Sharpe net",
    title: str | None = None,
    figsize: tuple[float, float] = DEFAULT_FIGSIZE,
) -> tuple[Figure, CostAnalysis]:
    r"""Trace la métrique nette contre le multiple de coûts, et rend l'analyse.

    **Le problème.** Un backtest net de frais suppose un coût unitaire, et ce
    coût est une hypothèse, presque toujours optimiste. La question utile n'est
    pas combien la stratégie rapporte, mais à partir de quel coût elle ne
    rapporte plus.

    **L'intuition.** On multiplie le coût supposé par un facteur croissant et on
    regarde où la métrique traverse le seuil de survie. Une stratégie qui meurt
    à 1,3 fois ses coûts supposés est une stratégie morte, l'incertitude sur un
    coût de transaction dépassant largement trente pour cent.

    .. math::

        \lambda^{\ast} = \lambda_k + (\lambda_{k+1} - \lambda_k)
                         \frac{m(\lambda_k) - \tau}{m(\lambda_k) - m(\lambda_{k+1})}

    **Les variables.** :math:`\lambda` est le multiple appliqué au coût supposé,
    :math:`m(\lambda)` la métrique nette à ce multiple, :math:`\tau` le seuil de
    survie, et :math:`\lambda^{\ast}` le point de rupture interpolé entre les
    deux multiples qui l'encadrent.

    **Les hypothèses.** Les multiples sont strictement croissants et strictement
    positifs. L'interpolation est linéaire entre deux points mesurés, ce qui
    suppose la métrique presque affine sur cet intervalle.

    **La provenance.** Novy-Marx et Velikov (2016), « A taxonomy of anomalies
    and their trading costs », *Review of Financial Studies*, 29(1), 104-147.
    Le calcul vient de
    :func:`quantlab.validation.robustness.cost_multiplier_analysis`, appelée ici
    sur une table déjà mesurée plutôt que sur une fonction à évaluer.

    **Les limites.** Le coût réel ne croît pas proportionnellement à la taille,
    ni linéairement avec le multiple, donc le point de rupture est un ordre de
    grandeur et non une frontière. Un multiple ne dit rien de l'impact de
    marché, qui dépend du volume échangé.

    **Les alternatives.** Le seuil de glissement exprimé en cents par action
    parle davantage à un exécutant, et se déduit du même balayage.

    **Pourquoi cette forme ici.** La pente près du multiple unité montre la
    fragilité aussi bien que le point de rupture lui-même.

    **Comment vérifier.** Sur deux points qui encadrent le seuil, le point de
    rupture rendu égale l'interpolation linéaire calculée à la main.

    Args:
        multipliers: les multiples de coûts testés, strictement croissants.
        net_sharpe: la métrique nette mesurée à chaque multiple, dans le même
            ordre.
        threshold: le seuil de survie, zéro par défaut.
        metric_label: l'étiquette lisible de l'axe des ordonnées.
        title: un titre imposé. Sans lui, le titre est déduit des données.
        figsize: la taille de la figure, en pouces.

    Returns:
        La figure, et l'analyse de coûts, qui porte la table, le point de
        rupture, le statut et la monotonie.

    Raises:
        ConfigError: si les deux suites n'ont pas la même longueur, ou si les
            multiples sont mal ordonnés.
        DataQualityError: si une métrique n'est pas finie.
    """
    lambdas = [float(m) for m in multipliers]
    metriques = [float(v) for v in net_sharpe]
    if len(lambdas) != len(metriques):
        raise ConfigError(f"{len(lambdas)} multiples pour {len(metriques)} valeurs de métrique")
    table_lue = dict(zip(lambdas, metriques, strict=True))
    analyse = cost_multiplier_analysis(lambda lam: table_lue[float(lam)], lambdas, threshold=threshold)

    rupture = analyse.breakeven_multiplier
    with portfolio_style():
        fig, ax = _nouvelle_figure(figsize)
        ax.plot(
            analyse.table["multiplier"],
            analyse.table["metric"],
            marker="o",
            color=gvf_style.OKABE_ITO[0],
        )
        ax.axhline(threshold, color=gvf_style.GRIS, linewidth=0.9, linestyle=":")
        if rupture is not None:
            ax.axvline(rupture, color=gvf_style.OKABE_ITO[3], linewidth=1.1, linestyle="--")
        ax.xaxis.set_major_formatter(gvf_style.formateur(1))
        ax.yaxis.set_major_formatter(gvf_style.formateur(2))
        ax.set_xlabel("Multiple appliqué aux coûts supposés")
        ax.set_ylabel(metric_label)
        if rupture is None:
            verdict = (
                "elle survit à tous les multiples testés"
                if analyse.status == "survives_all"
                else "elle est déjà morte au premier multiple"
            )
        else:
            verdict = f"elle meurt à {gvf_style.fr(rupture, 2)} fois les coûts supposés"
        ax.set_title(title or f"Sensibilité aux coûts sur {len(lambdas)} multiples, {verdict}")
    return fig, analyse


def subperiod_bars(
    subperiod_df: pd.DataFrame,
    *,
    metric_column: str = "sharpe",
    error_column: str | None = "sharpe_se_lo",
    label_column: str = "label",
    confidence: float = 0.95,
    metric_label: str | None = None,
    title: str | None = None,
    figsize: tuple[float, float] = DEFAULT_FIGSIZE,
) -> tuple[Figure, pd.DataFrame]:
    r"""Trace la performance par sous-période avec son intervalle, et la rend.

    **Le problème.** Une stratégie dont le ratio de Sharpe vaut 1,2 sur trente
    ans peut n'avoir gagné que pendant trois d'entre elles. Le chiffre
    d'ensemble ne le dit pas, et une barre sans intervalle de confiance laisse
    croire que chaque tranche est un résultat.

    **L'intuition.** On recalcule tout sur chaque tranche et on dessine
    l'incertitude à côté du point. Une tranche de deux ans porte un intervalle
    qui recouvre presque toujours zéro, et le voir empêche de conclure sur du
    vide.

    .. math::

        IC_{1-\alpha} = \widehat{SR} \pm z_{1 - \alpha/2}\, \widehat{SE}

    **Les variables.** :math:`\widehat{SR}` est le ratio de la tranche,
    :math:`\widehat{SE}` son erreur type, et :math:`z_{1-\alpha/2}` le quantile
    normal correspondant au niveau ``confidence``.

    **Les hypothèses.** L'erreur type retenue par défaut est celle de Lo, qui
    corrige l'autocorrélation. L'intervalle est symétrique et normal, ce qui est
    une approximation grossière sur une tranche courte.

    **La provenance.** Lo (2002), « The statistics of Sharpe ratios »,
    *Financial Analysts Journal*, 58(4), 36-52. Le tableau vient de
    :func:`quantlab.validation.robustness.subperiod_performance`.

    **Les limites.** Les bornes de tranches sont choisies, et un découpage
    différent donne un dessin différent. Les intervalles ne sont pas corrigés
    pour la multiplicité des tranches examinées.

    **Les alternatives.** La courbe glissante de :func:`rolling_metric` ne fixe
    aucune borne et perd l'erreur type.

    **Pourquoi cette forme ici.** Les tranches nommées se citent dans un
    rapport, ce qu'une courbe continue ne permet pas.

    **Comment vérifier.** Les bornes rendues valent la métrique plus ou moins le
    quantile normal multiplié par l'erreur type, ce qu'un test recalcule.

    Args:
        subperiod_df: le tableau des sous-périodes.
        metric_column: la colonne de la métrique tracée.
        error_column: la colonne de l'erreur type, ou ``None`` pour tracer des
            barres nues.
        label_column: la colonne des étiquettes de tranche.
        confidence: le niveau de confiance de l'intervalle, entre zéro et un.
        metric_label: l'étiquette lisible de l'axe des ordonnées.
        title: un titre imposé. Sans lui, le titre est déduit des données.
        figsize: la taille de la figure, en pouces.

    Returns:
        La figure, et un tableau à quatre colonnes, ``label``, ``metric``,
        ``ci_low`` et ``ci_high``.

    Raises:
        ConfigError: si une colonne demandée manque, ou si le niveau de
            confiance sort de l'intervalle ouvert entre zéro et un.
        DataQualityError: si une erreur type est négative ou non finie.
        InsufficientDataError: si le tableau est vide.
    """
    if not 0.0 < confidence < 1.0:
        raise ConfigError(f"confidence vaut {confidence}, il faut un niveau strictement entre 0 et 1")
    if len(subperiod_df) == 0:
        raise InsufficientDataError("le tableau des sous-périodes est vide")
    attendues = [label_column, metric_column] + ([error_column] if error_column else [])
    manquantes = [c for c in attendues if c not in subperiod_df.columns]
    if manquantes:
        raise ConfigError(f"colonnes absentes du tableau des sous-périodes : {manquantes}")

    valeurs = subperiod_df[metric_column].to_numpy(dtype="float64")
    if error_column is None:
        demi = np.zeros(len(valeurs))
    else:
        erreurs = subperiod_df[error_column].to_numpy(dtype="float64")
        if not np.all(np.isfinite(erreurs)):
            # Une erreur type manquante donnait des bornes manquantes, et la barre
            # d'incertitude disparaissait sans que rien ne le dise au lecteur.
            raise DataQualityError(f"la colonne {error_column!r} porte une erreur type non finie")
        if np.any(erreurs < 0.0):
            # Une erreur type négative renversait l'intervalle, ci_low passant
            # au-dessus de ci_high, et Matplotlib levait un ValueError nu.
            raise DataQualityError(f"la colonne {error_column!r} porte une erreur type négative")
        quantile = float(stats.norm.ppf(0.5 + confidence / 2.0))
        demi = quantile * erreurs
    table = pd.DataFrame(
        {
            "label": subperiod_df[label_column].astype("string").to_numpy(),
            "metric": valeurs,
            "ci_low": valeurs - demi,
            "ci_high": valeurs + demi,
        }
    )
    positives = int((valeurs > 0.0).sum())
    nom_metrique = metric_label or _humaniser(metric_column)

    with portfolio_style():
        fig, ax = _nouvelle_figure(figsize)
        couleurs = [gvf_style.OKABE_ITO[2] if v >= 0.0 else gvf_style.OKABE_ITO[3] for v in valeurs]
        ax.bar(table["label"].tolist(), valeurs, color=couleurs, width=0.62)
        if error_column is not None:
            ax.errorbar(
                table["label"].tolist(),
                valeurs,
                yerr=demi,
                fmt="none",
                ecolor=gvf_style.GRIS,
                capsize=3.0,
                linewidth=1.0,
            )
        ax.axhline(0.0, color=gvf_style.GRIS, linewidth=0.8)
        ax.yaxis.set_major_formatter(gvf_style.formateur(2))
        ax.set_ylabel(f"{nom_metrique}, intervalle à {gvf_style.fr(confidence * 100.0, 0)} pour cent")
        ax.set_xlabel("Sous-période")
        ax.set_title(
            title or f"{nom_metrique} sur {len(valeurs)} sous-périodes, {positives} au-dessus de zéro"
        )
    return fig, table


def correlation_heatmap(
    frame: pd.DataFrame,
    *,
    method: Literal["pearson", "spearman", "kendall"] = "pearson",
    labels: Sequence[str] | None = None,
    title: str | None = None,
    figsize: tuple[float, float] = DEFAULT_FIGSIZE,
) -> tuple[Figure, pd.DataFrame]:
    r"""Trace la matrice des corrélations, et rend cette matrice.

    **Le problème.** Un portefeuille de dix stratégies dont les corrélations
    valent 0,9 est une seule stratégie payée dix fois. La liste des ratios de
    Sharpe ne le montre pas, la matrice le montre.

    **L'intuition.** Chaque case porte la corrélation d'une paire, et l'échelle
    de couleur va de moins un à plus un en passant par zéro au centre. Un bloc
    uniformément foncé signale un groupe redondant.

    .. math::

        \rho_{ij} = \frac{\operatorname{Cov}(x_i, x_j)}
                         {\sqrt{\operatorname{Var}(x_i)\operatorname{Var}(x_j)}}

    **Les variables.** :math:`x_i` et :math:`x_j` sont deux colonnes du tableau,
    et :math:`\rho_{ij}` leur corrélation sur les dates communes.

    **Les hypothèses.** Les paires sont formées date par date, les valeurs
    manquantes étant écartées paire par paire, ce qui est la convention de
    pandas. La corrélation de Pearson ne voit que la dépendance linéaire.

    **La provenance.** La convention d'affichage vient de la pratique courante
    de l'allocation. Ledoit et Wolf (2004), « Honey, I shrunk the sample
    covariance matrix », *Journal of Portfolio Management*, 30(4), 110-119,
    montrent combien cette matrice est mal estimée.

    **Les limites.** Une corrélation estimée sur peu de points est très bruitée,
    et la matrice échantillonnale est presque toujours trop optimiste sur la
    diversification. La corrélation de Pearson rate les dépendances de queue.

    **Les alternatives.** ``analytics.contributions.effective_number_of_bets``
    résume la même information en un nombre, sans montrer quelle paire pose
    problème.

    **Pourquoi cette forme ici.** Le laboratoire compare des stratégies entre
    elles avant de les additionner, et la redondance se voit par blocs.

    **Comment vérifier.** La diagonale vaut un, la matrice est symétrique, et
    une paire parfaitement affine rend exactement un.

    Args:
        frame: le tableau des séries, dates en lignes et séries en colonnes.
        method: la méthode de corrélation passée à pandas.
        labels: les étiquettes lisibles des séries, dans l'ordre des colonnes.
            Sans elles, les noms de colonnes sont rendus lisibles.
        title: un titre imposé. Sans lui, le titre est déduit des données.
        figsize: la taille de la figure, en pouces.

    Returns:
        La figure, et la matrice des corrélations.

    Raises:
        ConfigError: si le nombre d'étiquettes ne correspond pas au nombre de
            colonnes.
        DataQualityError: si une colonne n'est pas numérique, ou si elle est
            constante, donc sans corrélation définie.
        InsufficientDataError: si le tableau porte moins de deux colonnes ou
            moins de deux lignes.
    """
    if not isinstance(frame, pd.DataFrame):
        raise ConfigError("frame doit être un tableau pandas")
    if frame.shape[1] < 2 or frame.shape[0] < 2:
        raise InsufficientDataError(
            f"correlation_heatmap demande au moins deux colonnes et deux lignes, "
            f"reçu {frame.shape[0]} par {frame.shape[1]}"
        )
    if labels is not None and len(labels) != frame.shape[1]:
        raise ConfigError(f"{len(labels)} étiquettes pour {frame.shape[1]} colonnes")
    non_numeriques = [str(c) for c in frame.columns if not is_numeric_dtype(frame[c])]
    if non_numeriques:
        # Sans cette garde, pandas lève un ValueError nu de conversion en flottant.
        raise DataQualityError(f"colonnes non numériques, sans corrélation : {non_numeriques}")
    constantes = [
        str(c)
        for c in frame.columns
        if _est_constant(
            frame[c].dropna().to_numpy(dtype="float64"),
            float(frame[c].std(ddof=1)) if frame[c].notna().sum() > 1 else 0.0,
        )
    ]
    if constantes:
        # Une colonne sans dispersion rend une ligne et une colonne entièrement
        # manquantes. Le titre publiait alors « moyenne hors diagonale nan », et
        # numpy émettait deux avertissements que l'appelant ne voyait pas.
        raise DataQualityError(f"colonnes sans dispersion, donc sans corrélation : {constantes}")

    matrice = frame.corr(method=method)
    lisibles = list(labels) if labels is not None else [_humaniser(str(c)) for c in matrice.columns]
    affichee = matrice.copy()
    affichee.index = pd.Index(lisibles)
    affichee.columns = pd.Index(lisibles)

    valeurs = matrice.to_numpy(dtype="float64")
    hors_diagonale = valeurs[~np.eye(len(valeurs), dtype=bool)]
    moyenne = float(np.nanmean(hors_diagonale))
    maximum = float(np.nanmax(hors_diagonale))

    with portfolio_style():
        fig, ax = _nouvelle_figure(figsize)
        image = _carte_de_chaleur(
            ax,
            affichee,
            vmin=-1.0,
            vmax=1.0,
            colormap=DIVERGING_COLORMAP,
            annoter=affichee.size <= MAX_ANNOTATED_CELLS,
            decimales=2,
            facteur=1.0,
        )
        ax.set_xticklabels(lisibles, rotation=30, ha="right")
        barre = fig.colorbar(image, ax=ax)
        barre.set_label("Corrélation, sans unité")
        ax.set_title(
            title
            or f"Corrélations de {len(lisibles)} séries, moyenne hors diagonale "
            f"{gvf_style.fr(moyenne, 2)} et maximum {gvf_style.fr(maximum, 2)}"
        )
    return fig, affichee


def save_figure(fig: Figure, path: Path | str, *, vector: bool = True) -> list[Path]:
    """Écrit la figure en PNG et, par défaut, en PDF vectoriel.

    **Le problème.** Le PNG sert au README lu sur GitHub, le PDF au rapport
    imprimé. Mesuré dans le portefeuille le 2026-08-30 : treize appels
    d'enregistrement sur vingt n'écrivaient que du PNG, donc la moitié des
    figures se pixelisait dans les rapports.

    **La solution retenue.** L'écriture est déléguée à ``gvf.style.enregistrer``,
    qui crée le dossier et écrit les deux formes. L'appel est placé dans la
    feuille de style du portefeuille, car deux réglages ne sont lus qu'au moment
    d'enregistrer, la résolution et le type de police du PDF.

    Args:
        fig: la figure à écrire.
        path: le chemin de destination. Une extension éventuelle est retirée,
            les deux formes étant écrites côte à côte sous le même nom.
        vector: faux pour n'écrire que le PNG.

    Returns:
        Les chemins écrits, le PNG d'abord.

    Raises:
        ConfigError: si le chemin ne porte aucun nom de fichier.

    Example:
        >>> import tempfile
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> fig, _ = underwater(pd.Series([0.01, -0.02, 0.005]))
        >>> with tempfile.TemporaryDirectory() as dossier:
        ...     ecrits = save_figure(fig, Path(dossier) / "repli")
        ...     [c.suffix for c in ecrits]
        ['.png', '.pdf']
    """
    chemin = Path(path)
    nom = chemin.stem if chemin.suffix in {".png", ".pdf"} else chemin.name
    if not nom:
        raise ConfigError(f"le chemin {path!r} ne porte aucun nom de fichier")
    with portfolio_style():
        return list(gvf_style.enregistrer(fig, chemin.parent, nom, vectoriel=vector))


def capacity_plot(
    table: pd.DataFrame,
    *,
    breakeven_aum: float | None = None,
    half_sharpe_aum: float | None = None,
    capacity_aum: float | None = None,
    currency: str = "$ US",
    title: str | None = None,
    figsize: tuple[float, float] = (8.0, 6.5),
) -> tuple[Figure, pd.DataFrame]:
    r"""Trace le rendement net et le ratio de Sharpe net contre la taille du capital.

    **Le problème.** Une stratégie se publie avec un ratio de Sharpe et sans
    taille. La figure montre à quelle taille ce ratio tient encore, et à
    laquelle il s'annule.

    **L'intuition.** Deux panneaux sur le même axe logarithmique du capital.
    Le rendement net annualisé en haut, le ratio de Sharpe net en bas. Une
    ligne verticale marque le capital d'annulation de la forme fermée, une
    autre celui où le ratio tombe à la moitié de sa référence.

    .. math::

        \bar{r}^{net}(A) = g - s - \sqrt{A}\, K

    **Les variables.** :math:`A` le capital, :math:`g` le brut moyen,
    :math:`s` le demi-écart moyen, :math:`K` la charge d'impact au capital
    unité. Voir :mod:`quantlab.execution.capacity`.

    **Les hypothèses.** La table vient de
    :func:`quantlab.execution.capacity.capacity_curve` : une ligne par
    taille, indexée par le capital en dollars, avec ``return_net_annual`` en
    fraction, ``sharpe_net``, et facultativement ``status`` valant ``exact``
    ou ``minorant``.

    **La provenance.** La courbe rendement contre capital est la lecture
    usuelle de la capacité, sans article de référence ; statut précepte.

    **Les limites.** Tout ce qui est dessiné est MODÉLISÉ, et le titre le
    dit. Un point au statut ``minorant`` est dessiné creux : le coût réel y
    est plus grand que le coût tracé.

    **Les alternatives.** Une seule courbe du coût annualisé en points de
    base, plus parlante pour un exécutant.

    **Pourquoi cette forme ici.** Le rendement et le ratio ne s'annulent pas
    au même endroit que la moitié du ratio, et l'allocateur a besoin des deux.

    **Comment vérifier.** La table rendue est celle qui a été tracée, ligne
    pour ligne.

    Args:
        table: la table de capacité, indexée par le capital en dollars.
        breakeven_aum: le capital d'annulation à marquer, ou ``None``.
        half_sharpe_aum: le capital de demi-ratio à marquer, ou ``None``.
        capacity_aum: la capacité retenue à marquer d'un trait plein, quand
            elle diffère du capital d'annulation, ou ``None``.
        currency: la devise affichée sur l'axe.
        title: un titre imposé. Sans lui, le titre est déduit des données.
        figsize: la taille de la figure, en pouces.

    Returns:
        La figure, et la table tracée.

    Raises:
        ConfigError: la table ne porte pas les deux colonnes exigées, ou son
            index n'est pas strictement positif.
    """
    exigees = {"return_net_annual", "sharpe_net"}
    if not exigees <= set(table.columns):
        raise ConfigError(f"la table de capacité doit porter {sorted(exigees)}, reçu {list(table.columns)}")
    aums = np.asarray(table.index, dtype=float)
    if aums.size == 0 or bool((aums <= 0.0).any()):
        raise ConfigError("l'index de la table de capacité doit être un capital strictement positif")
    tracee = table.copy()
    statuts = (
        tracee["status"].astype(str) if "status" in tracee.columns else pd.Series("exact", index=tracee.index)
    )
    creux = (statuts == "minorant").to_numpy()

    def _millions(valeur: float, _position: float) -> str:
        """Écrit un capital en millions, en typographie française."""
        return gvf_style.fr(valeur / 1e6, 0)

    with portfolio_style():
        fig = Figure(figsize=figsize)
        haut = fig.add_subplot(2, 1, 1)
        bas = fig.add_subplot(2, 1, 2, sharex=haut)
        for ax, colonne, facteur, etiquette in (
            (haut, "return_net_annual", 100.0, "Rendement net annualisé (%)"),
            (bas, "sharpe_net", 1.0, "Ratio de Sharpe net"),
        ):
            valeurs = tracee[colonne].to_numpy(dtype=float) * facteur
            ax.plot(aums, valeurs, color=gvf_style.OKABE_ITO[0], linewidth=1.4)
            ax.plot(aums[~creux], valeurs[~creux], "o", color=gvf_style.OKABE_ITO[0])
            if creux.any():
                ax.plot(
                    aums[creux],
                    valeurs[creux],
                    "o",
                    markerfacecolor="white",
                    markeredgecolor=gvf_style.OKABE_ITO[0],
                    label="coût écrêté, minorant",
                )
            ax.axhline(0.0, color=gvf_style.GRIS, linewidth=0.9, linestyle=":")
            if breakeven_aum is not None and breakeven_aum > 0.0:
                ax.axvline(breakeven_aum, color=gvf_style.OKABE_ITO[3], linewidth=1.1, linestyle="--")
            if half_sharpe_aum is not None:
                ax.axvline(half_sharpe_aum, color=gvf_style.OKABE_ITO[2], linewidth=1.0, linestyle="-.")
            if capacity_aum is not None and capacity_aum > 0.0 and capacity_aum != breakeven_aum:
                ax.axvline(capacity_aum, color="black", linewidth=1.2, linestyle="-")
            ax.set_xscale("log")
            ax.xaxis.set_major_formatter(mpl.ticker.FuncFormatter(_millions))
            ax.yaxis.set_major_formatter(gvf_style.formateur(2 if colonne == "sharpe_net" else 1))
            ax.set_ylabel(etiquette)
        if creux.any():
            haut.legend(loc="upper right", frameon=False)
        bas.set_xlabel(f"Capital géré (millions de {currency}, échelle logarithmique)")
        if title is None:
            if breakeven_aum is None:
                lecture = "le rendement net reste positif sur toute la grille"
            elif breakeven_aum <= 0.0:
                lecture = "le rendement net est déjà négatif à taille nulle"
            else:
                lecture = f"le rendement net s'annule vers {gvf_style.fr(breakeven_aum / 1e6, 0)} M{currency}"
            title = f"Capacité modélisée sur {len(aums)} tailles, {lecture}"
            if capacity_aum is not None and capacity_aum > 0.0 and capacity_aum != breakeven_aum:
                title += f", capacité retenue {gvf_style.fr(capacity_aum / 1e6, 2)} M{currency}"
        haut.set_title(title)
    return fig, tracee


def _annees(frame: pd.DataFrame) -> np.ndarray:
    """Rend l'index d'un tableau annuel en entiers, ou lève ``ConfigError``."""
    try:
        return np.asarray(frame.index, dtype=int)
    except (TypeError, ValueError) as exc:
        raise ConfigError("un tableau de rendements annuels est indexé par année entière") from exc


def annual_returns_lines(
    frame: pd.DataFrame,
    *,
    highlight: str,
    title: str | None = None,
    figsize: tuple[float, float] = (10.0, 5.5),
) -> tuple[Figure, pd.DataFrame]:
    r"""Trace les rendements annuels de plusieurs fonds, l'un d'eux mis en avant.

    **Le problème.** Les grands fonds fermés ne publient qu'un chiffre par an.
    Une stratégie de laboratoire doit se lire à côté d'eux, sans que la figure
    fasse croire à une série mensuelle qui n'existe pas.

    **L'intuition.** Une ligne par fonds, un point par année rapportée, et la
    série mise en avant en noir épais. Les trous des fonds restent des trous.

    .. math::

        R_{a} = \prod_{t \in a} (1 + r_t) - 1

    **Les variables.** :math:`R_a` le rendement de l'année civile :math:`a`,
    en fraction dans le tableau et en pour cent sur l'axe.

    **Les hypothèses.** Le tableau est indexé par année entière, une colonne
    par fonds, les manquants marquant les années non trouvées.

    **La provenance.** Aucune ; c'est la lecture directe d'un tableau annuel.

    **Les limites.** Une ligne relie deux années rapportées même si celles
    d'entre elles manquent, et le lecteur doit le savoir ; le titre le dit.

    **Les alternatives.** La carte de chaleur d':func:`annual_returns_heatmap`,
    qui ne relie rien.

    **Pourquoi cette forme ici.** C'est la figure qu'un lecteur demande en
    premier, et elle montre d'un coup l'échelle des rendements de chacun.

    **Comment vérifier.** Le tableau rendu est celui qui a été tracé.

    Args:
        frame: les rendements annuels en fraction, indexés par année.
        highlight: la colonne mise en avant.
        title: un titre imposé. Sans lui, le titre est déduit des données.
        figsize: la taille de la figure, en pouces.

    Returns:
        La figure, et le tableau tracé.

    Raises:
        ConfigError: la colonne mise en avant n'existe pas, ou l'index n'est
            pas une année entière.
    """
    if highlight not in frame.columns:
        raise ConfigError(f"la colonne mise en avant {highlight!r} n'est pas dans le tableau")
    frame = frame.sort_index()
    annees = _annees(frame)
    with portfolio_style():
        fig, ax = _nouvelle_figure(figsize)
        rang = 0
        for nom in frame.columns:
            serie = frame[nom].to_numpy(dtype=float) * 100.0
            if nom == highlight:
                ax.plot(annees, serie, color="black", linewidth=2.6, marker="o", label=str(nom), zorder=5)
            else:
                couleur = gvf_style.OKABE_ITO[rang % len(gvf_style.OKABE_ITO)]
                style = "-" if rang < len(gvf_style.OKABE_ITO) else "--"
                ax.plot(
                    annees, serie, color=couleur, linewidth=1.1, linestyle=style, marker=".", label=str(nom)
                )
                rang += 1
        ax.axhline(0.0, color=gvf_style.GRIS, linewidth=0.9, linestyle=":")
        ax.yaxis.set_major_formatter(gvf_style.formateur(0))
        ax.set_ylabel("Rendement annuel net (%)")
        ax.set_xlabel("Année civile")
        ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), frameon=False, fontsize=BASE_FONT_SIZE - 2.0)
        if title is None:
            autres = len(frame.columns) - 1
            title = (
                f"Rendements annuels de {highlight} et de {autres} fonds, "
                f"{int(annees.min())}-{int(annees.max())}, chiffres des fonds rapportés"
            )
        ax.set_title(title)
    return fig, frame.copy()


def annual_returns_heatmap(
    frame: pd.DataFrame,
    *,
    highlight: str,
    title: str | None = None,
    figsize: tuple[float, float] = (9.0, 8.0),
) -> tuple[Figure, pd.DataFrame]:
    r"""Dessine les rendements annuels en carte de chaleur, années en lignes, fonds en colonnes.

    **Le problème.** Dix fonds sur trente ans font trois cents cases, et une
    figure à lignes n'en montre plus rien. La carte garde chaque case lisible,
    et une année non trouvée y reste blanche.

    **L'intuition.** Une rampe divergente centrée sur zéro, bornée au
    quatre-vingt-quinzième centile des valeurs absolues pour qu'une seule
    année extrême n'efface pas les autres ; chaque case porte son chiffre
    exact.

    .. math::

        v_{\max} = Q_{0{,}95}\left(|R_{a,f}|\right)

    **Les variables.** :math:`R_{a,f}` le rendement de l'année :math:`a` du
    fonds :math:`f`, en fraction.

    **Les hypothèses.** Le tableau est indexé par année entière ; la colonne
    mise en avant est placée en premier.

    **La provenance.** Aucune ; convention de lecture.

    **Les limites.** La couleur sature au-delà de la borne, et seule
    l'annotation dit la vraie valeur de la case.

    **Les alternatives.** La figure à lignes d':func:`annual_returns_lines`.

    **Pourquoi cette forme ici.** Elle montre les trous, et c'est ce que le
    registre des fonds fermés a de plus honnête à montrer.

    **Comment vérifier.** Le tableau rendu est celui qui a été tracé, la
    colonne mise en avant en tête.

    Args:
        frame: les rendements annuels en fraction, indexés par année.
        highlight: la colonne placée en premier.
        title: un titre imposé. Sans lui, le titre est déduit des données.
        figsize: la taille de la figure, en pouces.

    Returns:
        La figure, et le tableau tracé, colonnes réordonnées.

    Raises:
        ConfigError: la colonne mise en avant n'existe pas, ou l'index n'est
            pas une année entière.
    """
    if highlight not in frame.columns:
        raise ConfigError(f"la colonne mise en avant {highlight!r} n'est pas dans le tableau")
    frame = frame.sort_index()
    annees = _annees(frame)
    ordre = [highlight, *[c for c in frame.columns if c != highlight]]
    table = frame.loc[:, ordre].copy()
    table.index = pd.Index(annees, name="year")
    absolues = np.abs(table.to_numpy(dtype=float))
    finies = absolues[np.isfinite(absolues)]
    borne = float(np.percentile(finies, 95)) if finies.size else 1.0
    borne = max(borne, 1e-6)
    with portfolio_style():
        fig, ax = _nouvelle_figure(figsize)
        image = _carte_de_chaleur(
            ax,
            table,
            vmin=-borne,
            vmax=borne,
            colormap=DIVERGING_COLORMAP,
            annoter=True,
            decimales=0,
            facteur=100.0,
        )
        ax.set_xticklabels([str(c) for c in table.columns], rotation=45, ha="right")
        barre = fig.colorbar(image, ax=ax, fraction=0.04, pad=0.02)
        barre.set_label("Rendement annuel net (%), couleur bornée au 95e centile")
        barre.formatter = mpl.ticker.FuncFormatter(lambda v, _p: gvf_style.fr(v * 100.0, 0))
        barre.update_ticks()
        if title is None:
            title = (
                f"Rendements annuels, {len(table.columns)} colonnes, "
                f"{int(annees.min())}-{int(annees.max())}, case blanche = année non trouvée"
            )
        ax.set_title(title)
    return fig, table


def correlation_bars(
    table: pd.DataFrame,
    *,
    value_col: str = "correlation",
    lo_col: str = "corr_lo",
    hi_col: str = "corr_hi",
    label_col: str = "fund",
    n_col: str = "n_years",
    title: str | None = None,
    figsize: tuple[float, float] = (8.0, 5.0),
) -> tuple[Figure, pd.DataFrame]:
    r"""Trace des corrélations en barres horizontales, avec leur intervalle de confiance.

    **Le problème.** Une corrélation sur huit années porte une incertitude
    énorme, et la publier sans son intervalle fait lire du bruit comme un
    lien.

    **L'intuition.** Une barre par fonds, triée, et un trait qui va de la borne
    basse à la borne haute de l'intervalle de Fisher. Une barre dont le trait
    traverse zéro ne prouve rien, et cela se voit.

    .. math::

        \left[\tanh(z - q/\sqrt{n-3}),\ \tanh(z + q/\sqrt{n-3})\right]

    **Les variables.** :math:`z` la corrélation transformée, :math:`n` le
    nombre d'années communes, :math:`q` le quantile normal.

    **Les hypothèses.** Le tableau vient de
    :func:`quantlab.analytics.comparison.annual_comparison_table`.

    **La provenance.** Fisher (1915) pour l'intervalle ; convention de lecture
    pour la figure.

    **Les limites.** Un fonds sans corrélation calculable, faute d'années,
    est dessiné sans barre, avec son nombre d'années dans l'étiquette.

    **Les alternatives.** Un nuage de points par fonds, plus fidèle et moins
    lisible à dix fonds.

    **Pourquoi cette forme ici.** L'intervalle est la figure ; la barre
    n'est que son centre.

    **Comment vérifier.** Le tableau rendu est le tableau trié qui a été
    tracé.

    Args:
        table: une ligne par fonds, avec la corrélation, ses bornes, son
            étiquette et son nombre d'années.
        value_col: la colonne de la corrélation.
        lo_col: la colonne de la borne basse.
        hi_col: la colonne de la borne haute.
        label_col: la colonne de l'étiquette.
        n_col: la colonne du nombre d'années.
        title: un titre imposé. Sans lui, le titre est déduit des données.
        figsize: la taille de la figure, en pouces.

    Returns:
        La figure, et le tableau trié tracé.

    Raises:
        ConfigError: une colonne exigée manque.
    """
    exigees = {value_col, lo_col, hi_col, label_col, n_col}
    if not exigees <= set(table.columns):
        raise ConfigError(f"le tableau doit porter {sorted(exigees)}, reçu {list(table.columns)}")
    triee = table.sort_values(value_col, na_position="first").reset_index(drop=True)
    valeurs = triee[value_col].to_numpy(dtype=float)
    bas = triee[lo_col].to_numpy(dtype=float)
    haut = triee[hi_col].to_numpy(dtype=float)
    etiquettes = [f"{lab} ({int(n)} années)" for lab, n in zip(triee[label_col], triee[n_col], strict=True)]
    with portfolio_style():
        fig, ax = _nouvelle_figure(figsize)
        positions = np.arange(len(triee))
        finies = np.isfinite(valeurs)
        ax.barh(positions[finies], valeurs[finies], color=gvf_style.OKABE_ITO[0], height=0.6)
        for i in positions[finies]:
            if np.isfinite(bas[i]) and np.isfinite(haut[i]):
                ax.plot([bas[i], haut[i]], [i, i], color="black", linewidth=1.2)
        ax.axvline(0.0, color=gvf_style.GRIS, linewidth=0.9, linestyle=":")
        ax.set_yticks(positions)
        ax.set_yticklabels(etiquettes)
        ax.set_xlim(-1.0, 1.0)
        ax.xaxis.set_major_formatter(gvf_style.formateur(1))
        ax.set_xlabel("Corrélation des rendements annuels, trait = intervalle de Fisher à 95 %")
        if title is None:
            etablies = int(np.sum(np.isfinite(bas) & (bas > 0.0)))
            title = f"Corrélations annuelles avec {len(triee)} fonds, {etablies} co-mouvement(s) établi(s)"
        ax.set_title(title)
    return fig, triee

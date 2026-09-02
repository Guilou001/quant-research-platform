r"""La neutralisation factorielle : retirer d'un signal ce qui n'est pas de l'alpha.

**Le problème.** Une stratégie qui n'est que longue technologie n'a pas d'alpha,
elle a une exposition sectorielle. Son rendement se lit alors sans rien savoir
d'elle, en regardant le secteur monter. Le modèle sous-jacent est le suivant :

.. math::

    r_i = \beta_{march\acute{e}} F_{march\acute{e}} + \beta_{secteur} F_{secteur}
          + \cdots + \epsilon_i

et c'est :math:`\epsilon_i` qui nous intéresse quand nous cherchons de l'alpha
idiosyncratique. Neutraliser un signal, c'est le projeter sur les expositions
connues à chaque date, puis ne garder que le reste.

**La convention de forme, qui décide de tout.** Un panier se lit ici comme le
module :mod:`quantlab.analytics.ic` le lit : les dates en lignes, les actifs en
colonnes. Une exposition prend deux formes. Un ``DataFrame`` est TOUJOURS un
panier de la même forme, jamais une matrice d'actifs par expositions. Une
``Series`` indexée par les actifs est une exposition fixe, répétée à chaque date.
Plusieurs expositions se passent dans un dictionnaire qui les nomme.

**Pourquoi la régression n'est pas déléguée à ``analytics.regression``.** La
fonction :func:`quantlab.analytics.regression.residualize` projette elle aussi,
et sur un échantillon unique elle rendrait le même résidu. Trois raisons la
rendent inutilisable dans la boucle transversale. Elle ne pondère pas les
observations, alors qu'une neutralisation de gérant se fait souvent en racine de
capitalisation. Elle lève une erreur dès que les observations manquent, alors
qu'une date trop mince doit être sautée sans arrêter les mille autres. Elle
porte enfin un taux sans risque et un vocabulaire de série temporelle qui n'ont
aucun sens sur une coupe à une date. La logique HAC de ce module voisin n'est
pas davantage transposable : elle corrige une autocorrélation dans le temps, et
une coupe transversale n'a pas de temps. Un test vérifie que les deux chemins
rendent le même résidu au dix-millième de milliardième, ce qui interdit toute
divergence silencieuse.

**Provenance.** La régression transversale date par date est celle de Fama et
MacBeth (1973). Le résultat qui légitime le résidu comme diagnostic est le
théorème de Frisch et Waugh (1933), complété par Lovell (1963). La pratique de
neutraliser un signal sur un modèle de risque vient de Rosenberg (1974) et de la
famille de modèles Barra qui en descend. Voir aussi Grinold et Kahn (1999),
*Active Portfolio Management*, chapitre 3.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd

from quantlab.analytics.ic import DEFAULT_MIN_NAMES
from quantlab.analytics.regression import DEFAULT_COLLINEARITY_TOL
from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.logging import get_logger

__all__ = [
    "INTERCEPT_COLUMN",
    "RESIDUAL_LOADING_TOL",
    "exposure_report",
    "neutralize",
    "neutralize_market_beta",
    "neutralize_sector",
    "neutralize_size",
    "orthogonalize",
    "sector_dummies",
]

log = get_logger(__name__)

#: Nom de la colonne constante de la coupe transversale. Le module voisin
#: ``analytics.regression`` appelle la sienne « alpha », parce qu'une constante
#: de série temporelle EST l'alpha. Ici la constante est la moyenne transversale
#: du signal à une date, ce qui n'est pas un alpha, donc le nom diffère.
INTERCEPT_COLUMN = "intercept"

#: Seuil relatif sous lequel un chargement résiduel est déclaré numériquement
#: nul par :func:`exposure_report`. Après neutralisation le chargement vaut zéro
#: en arithmétique exacte, et une poussière d'arrondi en double précision. Le
#: rapport entre cette poussière et le chargement d'origine tombe sous 1e-14 sur
#: les cas testés, donc le seuil retenu laisse deux ordres de grandeur de marge.
RESIDUAL_LOADING_TOL = 1e-10

#: Nombre minimal de périodes exigé pour former un t de Fama et MacBeth. Avec une
#: seule date l'écart type d'échantillon n'existe pas.
_MIN_PERIODS_FOR_TSTAT = 2

#: Écart maximal toléré entre un et la somme des indicatrices d'un bloc quand on
#: teste si ce bloc reproduit la constante. Les indicatrices valent exactement
#: 0,0 et 1,0, donc leur somme est exacte en double précision et le seuil ne sert
#: qu'à protéger d'une entrée déjà entachée d'arrondi.
_INDICATOR_SUM_TOL = 1e-12

#: Forme acceptée pour une exposition : un panier daté, ou une valeur fixe par actif.
ExposureLike = pd.DataFrame | pd.Series

#: Forme acceptée pour un jeu d'expositions : une seule, ou un dictionnaire nommé.
ExposureSet = ExposureLike | Mapping[str, ExposureLike]


# --------------------------------------------------------------------------- #
# Vérifications de forme
# --------------------------------------------------------------------------- #


def _check_frame(frame: pd.DataFrame, label: str) -> None:
    """Refuse une date ou un actif en double, qui rendrait l'appariement ambigu."""
    if frame.index.has_duplicates:
        raise DataQualityError(f"{label} porte des dates en double")
    if frame.columns.has_duplicates:
        raise DataQualityError(f"{label} porte des actifs en double")


def _overlap(left: pd.Index, right: pd.Index) -> int:
    """Compte les étiquettes communes à deux index, sans passer par pandas.

    L'intersection de pandas entre un index de dates et un index de chaînes
    dépend du dtype et peut avertir. Le comptage par ensembles Python ne dépend
    de rien.
    """
    return len(set(left) & set(right))


def _check_panel_orientation(frame: pd.DataFrame, panel: pd.DataFrame, name: str) -> None:
    """Refuse un tableau transposé, dont les lignes seraient des actifs.

    Sans ce garde-fou, un tableau d'actifs par expositions serait réindexé sur
    les dates, rendrait un panier entièrement vide, et la neutralisation
    échouerait plus loin sur un message qui ne nomme pas la cause.
    """
    if _overlap(frame.index, panel.index) == 0 and _overlap(frame.index, panel.columns) > 0:
        raise ConfigError(
            f"l'exposition « {name} » semble transposée : ses lignes sont des actifs. "
            "Un tableau d'exposition porte les dates en lignes. Pour plusieurs expositions "
            "fixes, passez un dictionnaire d'une Series par exposition."
        )


def _check_static_orientation(values: pd.Series, panel: pd.DataFrame, name: str) -> None:
    """Refuse une exposition fixe indexée par les dates au lieu des actifs."""
    if _overlap(values.index, panel.columns) == 0 and _overlap(values.index, panel.index) > 0:
        raise ConfigError(
            f"l'exposition « {name} » est indexée par les dates. Une Series d'exposition "
            "est indexée par les actifs ; un panier daté se passe en DataFrame."
        )


def _as_panel(value: ExposureLike, panel: pd.DataFrame, name: str) -> tuple[pd.DataFrame, bool]:
    """Met une exposition à la forme du panier, et dit si elle est numérique.

    Args:
        value: l'exposition, panier daté ou valeur fixe par actif.
        panel: le panier du signal, qui donne les dates et les actifs cibles.
        name: le nom de l'exposition, pour les messages d'erreur.

    Returns:
        Le couple (panier réindexé, exposition numérique ou non).

    Raises:
        ConfigError: si le type est inattendu, ou l'orientation renversée.
        DataQualityError: si un actif ou une date apparaît deux fois.
    """
    if isinstance(value, pd.Series):
        if value.index.has_duplicates:
            raise DataQualityError(f"l'exposition « {name} » porte un actif en double")
        _check_static_orientation(value, panel, name)
        numeric = bool(pd.api.types.is_numeric_dtype(value))
        row = value.reindex(panel.columns)
        repeated = np.tile(row.to_numpy(), (len(panel.index), 1))
        return pd.DataFrame(repeated, index=panel.index, columns=panel.columns), numeric
    if isinstance(value, pd.DataFrame):
        _check_frame(value, f"l'exposition « {name} »")
        _check_panel_orientation(value, panel, name)
        numeric = all(bool(pd.api.types.is_numeric_dtype(value[column])) for column in value.columns)
        return value.reindex(index=panel.index, columns=panel.columns), numeric
    raise ConfigError(f"l'exposition « {name} » doit être une Series ou un DataFrame pandas")


def _as_mapping(exposures: ExposureSet) -> dict[str, ExposureLike]:
    """Rend le jeu d'expositions sous forme de dictionnaire nommé."""
    if isinstance(exposures, pd.Series | pd.DataFrame):
        name = "exposure"
        if isinstance(exposures, pd.Series) and exposures.name is not None:
            name = str(exposures.name)
        return {name: exposures}
    if isinstance(exposures, Mapping):
        if not exposures:
            raise ConfigError("le dictionnaire d'expositions est vide")
        return {str(key): value for key, value in exposures.items()}
    raise ConfigError("les expositions doivent être une Series, un DataFrame ou un dictionnaire")


# --------------------------------------------------------------------------- #
# Codage en indicatrices
# --------------------------------------------------------------------------- #


def sector_dummies(sectors: pd.Series, *, drop_first: bool = True, prefix: str = "") -> pd.DataFrame:
    r"""Code une variable qualitative en colonnes d'indicatrices, une par modalité.

    **Le problème.** Un secteur n'est pas un nombre. Écrire « technologie = 1,
    énergie = 2, santé = 3 » imposerait que la santé soit trois fois la
    technologie, ce qui n'a aucun sens. Une régression a besoin de colonnes
    numériques dont l'échelle veut dire quelque chose.

    **L'intuition.** Une colonne par modalité, qui vaut un quand l'actif y
    appartient et zéro sinon. Le coefficient de cette colonne se lit alors comme
    l'écart moyen du signal dans ce secteur.

    .. math::

        D_{i,k} = \mathbb{1}\{ s_i = m_k \}, \qquad k = 1, \ldots, K

    Définition de chaque variable :

    - :math:`s_i` la modalité de l'actif :math:`i`, une chaîne ;
    - :math:`m_k` la :math:`k` ième modalité de la liste triée ;
    - :math:`D` la matrice des indicatrices, :math:`n` lignes et :math:`K`
      colonnes avant retrait.

    **La trappe de colinéarité, qui est la raison d'être de ``drop_first``.**
    Les :math:`K` indicatrices se somment à un actif par actif. Elles
    reproduisent donc exactement la colonne constante. Garder les :math:`K`
    colonnes ET une constante rend la matrice de plan singulière, et la
    régression n'a plus de solution unique. Le remède standard est d'en retirer
    une, qui devient la modalité de référence : les coefficients restants se
    lisent en écart à elle. L'autre remède, aussi valable, est de garder les
    :math:`K` colonnes et de retirer la constante.

    Args:
        sectors: la modalité de chaque actif, index des actifs. Une valeur
            manquante rend une ligne entièrement manquante, donc un actif que la
            régression écartera à cette date.
        drop_first: retire la première modalité de la liste triée. À laisser vrai
            dès que le plan porte une constante.
        prefix: préfixe des noms de colonnes, utile quand plusieurs variables
            qualitatives coexistent dans le même plan.

    Returns:
        Un tableau indexé par les actifs, une colonne par modalité conservée,
        valeurs 0,0 et 1,0 en flottant.

    Raises:
        DataQualityError: si un actif apparaît deux fois.

    Example:
        >>> import pandas as pd
        >>> secteurs = pd.Series(["tech", "energie", "sante", "tech"], index=list("abcd"))
        >>> sector_dummies(secteurs).columns.tolist()
        ['sante', 'tech']

    Note:
        Hypothèses. Les modalités sont exhaustives et exclusives : un actif
        appartient à un secteur et un seul. Un actif à cheval sur deux secteurs
        exige des poids d'appartenance, que ce codage ne représente pas.

        Provenance. Le codage remonte à Suits (1957), « Use of dummy variables in
        regression equations », *Journal of the American Statistical Association*
        52(280), 548-551, qui décrit déjà la trappe de colinéarité.

        Limites. Le tri des modalités est alphabétique, donc la référence retirée
        dépend des noms et non de l'économie. Une référence choisie exprès se
        passe en renommant, ou en retirant la colonne voulue après coup.

        Alternatives. Le codage par écart à la moyenne, dit « effets », rend des
        coefficients qui somment à zéro plutôt qu'en écart à une référence. Il
        change la lecture des coefficients, jamais les résidus.

        Choix du laboratoire. La neutralisation ne lit pas les coefficients de
        secteur un par un, elle ne garde que le résidu. Le résidu est identique
        pour les deux codages, puisque l'espace engendré est le même.

        Vérification. La somme des colonnes conservées vaut un pour tout actif
        hors modalité de référence, et zéro pour les actifs de référence. Un test
        du module le vérifie sur trois modalités.
    """
    if sectors.index.has_duplicates:
        raise DataQualityError("la variable qualitative porte un actif en double")

    missing = sectors.isna()
    labels = sectors.astype(str).where(~missing)
    modalities = sorted(labels.dropna().unique().tolist())
    kept = modalities[1:] if drop_first else modalities

    frame = pd.DataFrame(
        {f"{prefix}{modality}": (labels == modality).astype(float) for modality in kept},
        index=sectors.index,
        columns=[f"{prefix}{modality}" for modality in kept],
        dtype=float,
    )
    frame.loc[missing.to_numpy(), :] = np.nan
    return frame


def _expand_categorical(frame: pd.DataFrame, name: str, drop_first: bool) -> dict[str, np.ndarray]:
    """Développe un panier de modalités en un bloc d'indicatrices par modalité.

    La liste des modalités est calculée sur TOUT le panier, pas date par date.
    Sans cela, une date où un secteur est absent n'aurait pas les mêmes colonnes
    que ses voisines, et les chargements ne seraient plus comparables dans le
    temps. Une colonne vide à une date est retirée plus tard, au moment de
    résoudre.

    Args:
        frame: le panier des modalités, dates en lignes, actifs en colonnes.
        name: le nom de l'exposition, qui préfixe les colonnes rendues.
        drop_first: retire la première modalité, voir :func:`sector_dummies`.

    Returns:
        Un dictionnaire du nom de colonne vers un tableau de dates par actifs.
    """
    missing = frame.isna()
    labels = frame.astype(str).where(~missing)
    flat = pd.Series(labels.to_numpy().ravel())
    modalities = sorted(flat.dropna().unique().tolist())
    kept = modalities[1:] if drop_first else modalities

    blocks: dict[str, np.ndarray] = {}
    for modality in kept:
        indicator = (labels == modality).astype(float).where(~missing)
        blocks[f"{name}_{modality}"] = indicator.to_numpy(dtype=float)
    return blocks


# --------------------------------------------------------------------------- #
# Le moteur transversal
# --------------------------------------------------------------------------- #


def _assert_identified(design: np.ndarray, columns: list[str], date: object, tol: float) -> None:
    """Refuse un plan de rang déficient, en nommant la date fautive.

    **Méthode.** Les colonnes sont normalisées, pour que le seuil ne dépende pas
    des unités, puis les valeurs singulières sont comparées entre elles. Une
    dernière valeur singulière sous ``tol`` fois la première signale une colonne
    que les autres reproduisent déjà.

    Args:
        design: la matrice de plan, déjà pondérée et sans colonne nulle.
        columns: les noms des colonnes, pour le message.
        date: la date de la coupe, pour le message.
        tol: le seuil relatif de détection.

    Raises:
        DataQualityError: si le plan est de rang déficient.
    """
    norms = np.linalg.norm(design, axis=0)
    singular = np.linalg.svd(design / norms, compute_uv=False)
    if singular[-1] <= tol * singular[0]:
        raise DataQualityError(
            f"plan de rang déficient au {date} sur les colonnes {columns} "
            f"(seuil relatif {tol:g}). Cause la plus fréquente : toutes les indicatrices "
            "conservées en présence d'une constante, qu'elles reproduisent par leur somme."
        )


def _rebase_block(
    design: np.ndarray,
    alive: np.ndarray,
    positions: list[int],
    active: np.ndarray,
) -> list[int]:
    """Retire une indicatrice quand le bloc reproduit la constante à cette date.

    **Le problème.** La modalité de référence est choisie une fois pour tout le
    panier, sur la liste alphabétique globale. Une date où cette modalité
    n'apparaît chez aucun actif garde donc toutes ses indicatrices vivantes. Leur
    somme vaut alors un chez chaque actif, donc elles reproduisent la constante.
    Le plan devient singulier, et la coupe se refuse alors qu'elle est
    parfaitement posée. Le refus dépend ainsi des modalités présentes aux AUTRES
    dates, ce qu'aucune lecture du résultat ne laisserait deviner.

    **L'intuition.** Il suffit d'écarter une indicatrice de plus à cette date. La
    modalité écartée devient la référence locale, l'espace engendré ne change
    pas, et le résidu est celui qu'on attendait.

    Args:
        design: le plan non pondéré restreint aux actifs exploitables.
        alive: le masque des colonnes retenues, modifié sur place.
        positions: les indices des colonnes du bloc qualitatif.
        active: le masque des lignes qui portent un poids strictement positif.

    Returns:
        Les indices des colonnes du bloc qui étaient vivantes avant le retrait,
        vide si aucun retrait n'a eu lieu. Le lecteur s'en sert pour déclarer
        manquants des chargements dont la référence a changé.

    Note:
        Vérification. Le test compare la somme du bloc à un chez les seuls actifs
        pondérés. Elle vaut zéro dès que la référence globale est présente, donc
        le retrait ne se déclenche que dans le cas pathologique.
    """
    live = [j for j in positions if alive[j]]
    if not live:
        return []
    total = design[np.ix_(active, live)].sum(axis=1)
    if total.size == 0 or float(np.max(np.abs(total - 1.0))) > _INDICATOR_SUM_TOL:
        return []
    alive[live[0]] = False
    return live


def _solve(y: np.ndarray, design: np.ndarray, weight: np.ndarray | None) -> np.ndarray:
    r"""Résout les moindres carrés, pondérés ou non, et rend les coefficients.

    La pondération se traite en multipliant chaque ligne par la racine de son
    poids, ce qui ramène le problème pondéré à un problème ordinaire :

    .. math::

        \hat{b} = \arg\min_b \sum_i w_i (y_i - x_i^{\top} b)^2
                = \arg\min_b \| \sqrt{w} \odot (y - X b) \|^2

    Args:
        y: le signal de la coupe.
        design: la matrice de plan.
        weight: les poids, ou rien pour des poids égaux.

    Returns:
        Le vecteur des coefficients.
    """
    if weight is None:
        coefficients, *_ = np.linalg.lstsq(design, y, rcond=None)
        return coefficients
    root = np.sqrt(weight)
    coefficients, *_ = np.linalg.lstsq(design * root[:, None], y * root, rcond=None)
    return coefficients


def _engine(
    panel: pd.DataFrame,
    exposures: ExposureSet,
    *,
    add_intercept: bool,
    weights: ExposureLike | None,
    min_names: int,
    collinearity_tol: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Régresse le signal sur les expositions date par date, et rend tout.

    Args:
        panel: le signal, dates en lignes, actifs en colonnes.
        exposures: les expositions, voir :func:`neutralize`.
        add_intercept: ajoute la colonne constante.
        weights: les poids de régression, ou rien.
        min_names: le nombre minimal d'actifs exploitables à une date.
        collinearity_tol: le seuil de refus de colinéarité.

    Returns:
        Le couple (panier des résidus, tableau des chargements par date).

    Raises:
        ConfigError: plan vide, ou seuil incohérent.
        DataQualityError: doublon, poids négatif, ou plan singulier.
        InsufficientDataError: aucune date exploitable.
    """
    if not isinstance(panel, pd.DataFrame):
        raise ConfigError("le panier de signal doit être un DataFrame pandas")
    _check_frame(panel, "le panier de signal")
    if min_names < 2:
        raise ConfigError("min_names doit valoir au moins 2, une régression exigeant deux points")
    if panel.empty:
        raise InsufficientDataError("le panier de signal est vide")

    named = _as_mapping(exposures)
    blocks: dict[str, np.ndarray] = {}
    categorical: dict[str, list[str]] = {}
    for name, value in named.items():
        frame, numeric = _as_panel(value, panel, name)
        if numeric:
            produced = {name: frame.to_numpy(dtype=float)}
        else:
            produced = _expand_categorical(frame, name, drop_first=add_intercept)
            categorical[name] = list(produced)
        clash = sorted(set(produced) & set(blocks))
        if clash:
            raise ConfigError(
                f"l'exposition « {name} » produit la colonne {clash}, déjà produite par une "
                "autre exposition. La garder écraserait la première en silence, et le signal "
                "ressortirait non neutralisé sans que rien ne le dise. Renommez l'une des deux."
            )
        blocks.update(produced)

    if add_intercept and INTERCEPT_COLUMN in blocks:
        raise ConfigError(
            f"une exposition porte le nom réservé « {INTERCEPT_COLUMN} », qui est celui de la "
            "colonne constante. Renommez-la, ou posez add_intercept à faux."
        )

    columns = list(blocks)
    if add_intercept:
        columns.insert(0, INTERCEPT_COLUMN)
    if not columns:
        raise ConfigError("le plan de régression est vide : aucune exposition à retirer et aucune constante")
    position_of = {column: index for index, column in enumerate(columns)}
    blocks_by_exposure = {name: [position_of[c] for c in cols] for name, cols in categorical.items()}

    n_dates, n_assets = panel.shape
    tensor = np.empty((n_dates, n_assets, len(columns)), dtype=float)
    offset = 0
    if add_intercept:
        tensor[:, :, 0] = 1.0
        offset = 1
    for position, name in enumerate(blocks, start=offset):
        tensor[:, :, position] = blocks[name]

    signal = panel.to_numpy(dtype=float)
    weight_values: np.ndarray | None = None
    if weights is not None:
        weight_frame, numeric = _as_panel(weights, panel, "weights")
        if not numeric:
            raise ConfigError("les poids doivent être numériques")
        weight_values = weight_frame.to_numpy(dtype=float)
        if bool(np.any(weight_values[np.isfinite(weight_values)] < 0.0)):
            raise DataQualityError("un poids est négatif : la pondération n'a plus de sens")

    residuals = np.full((n_dates, n_assets), np.nan)
    loadings = np.full((n_dates, len(columns)), np.nan)
    n_skipped = 0

    for i, date in enumerate(panel.index):
        y = signal[i]
        x = tensor[i]
        valid = np.isfinite(y) & np.all(np.isfinite(x), axis=1)
        weight_row: np.ndarray | None = None
        if weight_values is not None:
            weight_row = weight_values[i]
            valid &= np.isfinite(weight_row)
        used = int(valid.sum())
        effective = used if weight_row is None else int(np.sum(weight_row[valid] > 0.0))
        if used < max(min_names, len(columns) + 1) or effective < len(columns) + 1:
            n_skipped += 1
            continue

        sub_design = x[valid]
        sub_weight = None if weight_row is None else weight_row[valid]
        scaled = sub_design if sub_weight is None else sub_design * np.sqrt(sub_weight)[:, None]
        alive = np.linalg.norm(scaled, axis=0) > 0.0
        if not bool(alive.any()):
            n_skipped += 1
            continue

        rebased: list[int] = []
        if add_intercept:
            active = np.ones(used, dtype=bool) if sub_weight is None else sub_weight > 0.0
            for positions in blocks_by_exposure.values():
                rebased.extend(_rebase_block(sub_design, alive, positions, active))
        if not bool(alive.any()):
            n_skipped += 1
            continue

        kept_columns = [columns[j] for j in range(len(columns)) if alive[j]]
        _assert_identified(scaled[:, alive], kept_columns, date, collinearity_tol)
        coefficients = _solve(y[valid], sub_design[:, alive], sub_weight)
        residuals[i, valid] = y[valid] - sub_design[:, alive] @ coefficients
        loadings[i, alive] = coefficients
        if rebased:
            # La référence de ce bloc a changé à cette date, donc son chargement et
            # celui de la constante ne se comparent plus à ceux des autres dates.
            # Les déclarer manquants vaut mieux que les moyenner avec les autres.
            loadings[i, rebased] = np.nan
            loadings[i, 0] = np.nan

    if n_skipped == n_dates:
        raise InsufficientDataError(
            f"aucune des {n_dates} dates ne porte assez d'actifs exploitables "
            f"pour un plan de {len(columns)} colonnes"
        )

    log.debug(
        "neutralisation transversale terminée",
        extra={"n_dates": n_dates, "n_skipped": n_skipped, "n_columns": len(columns)},
    )
    residual_frame = pd.DataFrame(residuals, index=panel.index, columns=panel.columns)
    loading_frame = pd.DataFrame(loadings, index=panel.index, columns=columns)
    return residual_frame, loading_frame


# --------------------------------------------------------------------------- #
# L'interface publique
# --------------------------------------------------------------------------- #


def neutralize(
    panel: pd.DataFrame,
    exposures: ExposureSet,
    *,
    add_intercept: bool = True,
    weights: ExposureLike | None = None,
    min_names: int = DEFAULT_MIN_NAMES,
    collinearity_tol: float = DEFAULT_COLLINEARITY_TOL,
) -> pd.DataFrame:
    r"""Retire d'un signal la part que des expositions connues expliquent.

    **Le problème.** Un signal transversal se compare à des rendements futurs, et
    son coefficient d'information sert de verdict. Ce verdict ment si le signal
    n'est qu'un secteur déguisé. La question à laquelle ce module répond est
    donc : que reste-t-il du signal une fois les expositions connues retirées ?

    **L'intuition.** À chaque date, régresser le signal sur les expositions et ne
    garder que ce que la régression n'explique pas. Le reste est sans corrélation
    avec les expositions, à cette date, par construction géométrique.

    .. math::

        e_t = s_t - X_t (X_t^{\top} W_t X_t)^{-1} X_t^{\top} W_t s_t

    Définition de chaque variable :

    - :math:`s_t` le vecteur du signal à la date :math:`t`, un nombre par actif ;
    - :math:`X_t` la matrice des expositions, actifs en lignes, constante
      comprise si ``add_intercept`` ;
    - :math:`W_t` la matrice diagonale des poids, l'identité par défaut ;
    - :math:`e_t` le signal neutralisé, de même longueur que :math:`s_t`.

    Args:
        panel: le signal, dates en lignes, actifs en colonnes.
        exposures: une exposition ou un dictionnaire d'expositions. Un
            ``DataFrame`` est un panier daté ; une ``Series`` indexée par les
            actifs est une exposition fixe. Une exposition non numérique est
            codée en indicatrices, et la première modalité est retirée dès que le
            plan porte une constante. Deux expositions qui produiraient la même
            colonne sont refusées, l'une écrasant l'autre en silence.
        add_intercept: ajoute la colonne constante, ce qui centre le signal
            neutralisé à chaque date. Le nom ``intercept`` devient alors réservé.
        weights: les poids de la régression, même forme qu'une exposition. Un
            poids nul écarte l'actif de l'estimation, sans lui retirer son
            résidu. Un poids manquant écarte l'actif de la date, résidu compris,
            parce qu'aucune valeur de remplacement ne serait défendable.
        min_names: le nombre minimal d'actifs exploitables sous lequel la date
            est sautée plutôt que calculée.
        collinearity_tol: le seuil relatif de refus d'un plan singulier.

    Returns:
        Un tableau de la forme de ``panel``, portant le signal neutralisé, et
        ``nan`` aux dates sautées comme aux actifs sans exposition.

    Raises:
        ConfigError: plan vide, orientation renversée, seuil incohérent, nom de
            colonne produit deux fois, ou exposition nommée ``intercept``.
        DataQualityError: doublon d'index, poids négatif, ou plan singulier.
        InsufficientDataError: panier vide, ou aucune date exploitable.

    Example:
        Un signal égal à deux fois la taille moins trois fois le bêta se
        neutralise en exactement zéro, à la précision machine, sur ces deux
        expositions.

    Note:
        Hypothèses. La relation entre signal et expositions est linéaire à
        chaque date. Les expositions sont connues à la date où elles servent, ce
        que ce module ne vérifie pas : un bêta calculé sur l'année entière
        contient de l'information future, et le résidu en hérite.

        Provenance. Régression transversale de Fama et MacBeth (1973), résidu
        légitimé par Frisch et Waugh (1933) et Lovell (1963), pratique de
        neutralisation issue de Rosenberg (1974).

        Limites. Neutraliser sur des expositions ESTIMÉES fait entrer l'erreur
        d'estimation dans le résidu. Un bêta bruité laisse passer une part de
        l'exposition qu'on croyait retirée, donc la neutralisation est partielle.
        L'ordre de grandeur est chiffré dans :func:`neutralize_market_beta`.
        L'orthogonalité vaut par ailleurs dans l'échantillon, et seulement lui.
        La liste des modalités d'une exposition qualitative est enfin dressée sur
        le panier entier, dates futures comprises. Elle décide du nom des
        colonnes, jamais du résidu d'une date : un contrôle du module vérifie
        qu'ajouter une date au panier laisse les résidus des dates antérieures
        inchangés au bit près.

        Alternatives. Contraindre l'exposition à zéro dans l'optimiseur de
        portefeuille, plutôt que de corriger le signal après coup. La contrainte
        agit sur des positions négociables, la projection non. Autre voie, tenir
        les expositions comme des variables de contrôle dans une seule régression
        de panel, ce qui suppose des chargements constants dans le temps.

        Choix du laboratoire. La projection date par date ne suppose rien sur la
        stabilité des chargements, et elle rend un signal de même forme que
        l'entrée, donc utilisable partout où l'original l'était.

        Vérification. Le produit :math:`X_t^{\top} W_t e_t` vaut zéro à la
        précision machine à chaque date. Un signal déjà orthogonal aux
        expositions ressort inchangé. Deux tests du module le vérifient.
    """
    residual, _ = _engine(
        panel,
        exposures,
        add_intercept=add_intercept,
        weights=weights,
        min_names=min_names,
        collinearity_tol=collinearity_tol,
    )
    return residual


def neutralize_market_beta(
    panel: pd.DataFrame,
    betas: ExposureLike,
    *,
    add_intercept: bool = True,
    weights: ExposureLike | None = None,
    min_names: int = DEFAULT_MIN_NAMES,
) -> pd.DataFrame:
    r"""Retire du signal sa part expliquée par le bêta de marché.

    **Le problème.** Un signal qui trie les actifs par bêta produit un
    portefeuille long les titres agressifs et court les défensifs. Son rendement
    suit alors le marché, et se trouve rémunéré même sans la moindre information.

    **L'intuition.** Le bêta est une exposition numérique comme une autre. La
    régression transversale du signal sur le bêta, à chaque date, isole la part
    du classement qui ne vient pas du bêta.

    .. math::

        e_{i,t} = s_{i,t} - a_t - b_t \, \beta_{i,t}

    Args:
        panel: le signal, dates en lignes, actifs en colonnes.
        betas: le bêta de chaque actif, panier daté ou valeur fixe par actif.
        add_intercept: ajoute la constante transversale.
        weights: les poids de la régression, voir :func:`neutralize`.
        min_names: le nombre minimal d'actifs exploitables à une date.

    Returns:
        Le signal neutralisé du bêta, de la forme de ``panel``.

    Raises:
        ConfigError: si l'orientation du bêta est renversée.
        InsufficientDataError: si aucune date n'est exploitable.

    Note:
        Variables. :math:`s_{i,t}` est le signal, :math:`\beta_{i,t}` le bêta,
        :math:`a_t` la constante transversale, :math:`b_t` le chargement de la
        date, et :math:`e_{i,t}` le résidu.

        Hypothèses. Le bêta passé approche le bêta de la période où le signal
        sera détenu. Rosenberg et Guy (1976) montrent que cette approximation se
        dégrade vite sur un titre isolé, et tient mieux sur un panier.

        Provenance. Le bêta vient de Sharpe (1964) et Lintner (1965). Sa
        stabilité et son rétrécissement sont traités par Blume (1975), déjà
        implémenté dans :func:`quantlab.analytics.regression.shrunk_beta`.

        Limites, chiffrées. L'erreur type d'un bêta de moindres carrés vaut
        :math:`\sigma_{\epsilon} / (\sigma_m \sqrt{T})`. Avec soixante mois, une
        volatilité de marché de 4,5 % par mois et une volatilité
        idiosyncratique de 4 % à 6 %, elle ressort entre 0,115 et 0,172. Le
        calcul : 0,04 divisé par 0,045 fois 7,746 donne 0,115, et 0,06 au
        numérateur donne 0,172. Statut MODÉLISÉ, hypothèses déclarées ci-dessus.
        Une exposition résiduelle de cet ordre survit donc à la neutralisation.

        Alternatives. Neutraliser sur un bêta rétréci, moins bruité mais biaisé
        vers un. Ou imposer un bêta nul au portefeuille, ce qui déplace le
        problème vers l'optimiseur sans le supprimer.

        Choix du laboratoire. Le bêta brut est retenu par défaut, parce que le
        rétrécissement mélange deux décisions dans un seul chiffre. Le
        rétrécissement se demande explicitement, en passant un bêta déjà rétréci.

        Vérification. La corrélation transversale entre le résidu et le bêta vaut
        zéro à la précision machine à chaque date. Un test du module le vérifie.
    """
    return neutralize(
        panel,
        {"beta": betas},
        add_intercept=add_intercept,
        weights=weights,
        min_names=min_names,
    )


def neutralize_sector(
    panel: pd.DataFrame,
    sectors: ExposureLike,
    *,
    add_intercept: bool = True,
    weights: ExposureLike | None = None,
    min_names: int = DEFAULT_MIN_NAMES,
) -> pd.DataFrame:
    r"""Retire du signal sa part expliquée par l'appartenance sectorielle.

    **Le problème.** Un signal calculé sur des ratios comptables classe souvent
    les secteurs entre eux plutôt que les titres à l'intérieur d'un secteur. Une
    banque et un éditeur de logiciels n'ont pas le même rapport de valeur
    comptable au cours, et rien de cet écart ne dit lequel des deux est bon
    marché.

    **L'intuition.** Retirer, à chaque date, la moyenne du signal dans le secteur
    de chaque actif. La régression sur les indicatrices fait exactement cela
    quand aucune autre exposition n'est présente.

    .. math::

        e_{i,t} = s_{i,t} - \bar{s}_{g(i),t}

    Args:
        panel: le signal, dates en lignes, actifs en colonnes.
        sectors: le secteur de chaque actif, panier daté de modalités ou
            ``Series`` fixe indexée par les actifs.
        add_intercept: ajoute la constante. La première modalité est alors
            retirée, sans quoi le plan serait singulier.
        weights: les poids de la régression, voir :func:`neutralize`.
        min_names: le nombre minimal d'actifs exploitables à une date.

    Returns:
        Le signal neutralisé du secteur, de la forme de ``panel``.

    Raises:
        DataQualityError: si le plan reste singulier malgré les deux retraits.
        InsufficientDataError: si aucune date n'est exploitable.

    Note:
        Variables. :math:`g(i)` désigne le secteur de l'actif :math:`i`, et
        :math:`\bar{s}_{g,t}` la moyenne du signal dans ce secteur à la date
        :math:`t`. L'égalité écrite ci-dessus vaut sans pondération et sans autre
        exposition dans le plan.

        Hypothèses. Un actif appartient à un secteur et un seul, et la
        classification est stable sur la période. Une révision de nomenclature
        change les moyennes de groupe sans prévenir.

        La référence, et ce qui arrive quand elle manque. La modalité retirée est
        la première de la liste alphabétique du panier entier, ce qui rend les
        chargements comparables d'une date à l'autre. Une date où cette modalité
        n'apparaît chez aucun actif verrait ses indicatrices restantes sommer à
        un, donc reproduire la constante. Le module y retire alors une seconde
        modalité, qui sert de référence à cette date seule. Le résidu est celui
        qu'on attend, et les chargements du bloc comme celui de la constante sont
        rendus MANQUANTS à cette date, leur base n'étant plus celle des autres.
        Les chargements des expositions numériques du même plan, eux, restent
        valides : ils ne dépendent que de l'espace engendré, que le changement de
        référence laisse intact.

        Provenance. La neutralisation par groupe est la pratique courante des
        modèles de risque à facteurs industriels, décrite par Rosenberg (1974) et
        reprise dans Grinold et Kahn (1999), chapitre 3.

        Limites. Neutraliser sur un secteur retire aussi le rendement que la
        rotation sectorielle rapportait, quand elle rapportait quelque chose. Un
        secteur à trois membres rend par ailleurs une moyenne de groupe très
        bruitée, et le résidu de ces trois titres devient presque mécanique.

        Alternatives. Retirer la médiane du groupe plutôt que sa moyenne, ce qui
        résiste aux valeurs extrêmes mais n'est plus une projection linéaire. Ou
        classer sur les rangs à l'intérieur de chaque groupe.

        Choix du laboratoire. La régression garde une seule mécanique pour toutes
        les expositions, donc un seul chemin de code à vérifier, et elle accepte
        de mêler secteur et expositions numériques dans le même plan.

        Vérification. Sans pondération ni autre exposition, la moyenne du résidu
        vaut zéro dans chaque secteur, à chaque date. Un test du module le
        vérifie.
    """
    return neutralize(
        panel,
        {"sector": sectors},
        add_intercept=add_intercept,
        weights=weights,
        min_names=min_names,
    )


def neutralize_size(
    panel: pd.DataFrame,
    market_caps: ExposureLike,
    *,
    log: bool = True,
    add_intercept: bool = True,
    weights: ExposureLike | None = None,
    min_names: int = DEFAULT_MIN_NAMES,
) -> pd.DataFrame:
    r"""Retire du signal sa part expliquée par la taille des sociétés.

    **Le problème.** Beaucoup de signaux sont plus forts sur les petites
    sociétés, où l'information circule moins bien. Un signal qui trie par taille
    ramasse donc une prime connue, celle de Banz (1981), et non de l'alpha.

    **L'intuition.** La capitalisation s'étale sur quatre ordres de grandeur, si
    bien qu'une régression en niveau serait dictée par les trois plus grosses
    sociétés. Son logarithme la ramène à une échelle où l'écart entre deux titres
    se lit en pourcentage.

    .. math::

        e_{i,t} = s_{i,t} - a_t - c_t \ln(\mathrm{cap}_{i,t})

    Args:
        panel: le signal, dates en lignes, actifs en colonnes.
        market_caps: la capitalisation de chaque actif, panier daté ou valeur
            fixe par actif.
        log: prend le logarithme naturel de la capitalisation avant de régresser.
        add_intercept: ajoute la constante transversale.
        weights: les poids de la régression, voir :func:`neutralize`.
        min_names: le nombre minimal d'actifs exploitables à une date.

    Returns:
        Le signal neutralisé de la taille, de la forme de ``panel``.

    Raises:
        ConfigError: si l'orientation de la capitalisation est renversée.
        DataQualityError: si une capitalisation est négative ou nulle alors que
            son logarithme est demandé.
        InsufficientDataError: si aucune date n'est exploitable.

    Note:
        Variables. :math:`\mathrm{cap}_{i,t}` est la capitalisation boursière,
        :math:`c_t` le chargement de taille de la date, et :math:`e_{i,t}` le
        résidu.

        Hypothèses. Le lien entre signal et taille est linéaire dans le
        logarithme. C'est une hypothèse forte : Fama et French (2008) montrent
        que plusieurs anomalies se concentrent dans le plus petit décile, donc
        que la relation est en marche d'escalier plutôt qu'en droite.

        Provenance. L'effet taille est mesuré par Banz (1981), « The relationship
        between return and market value of common stocks », *Journal of Financial
        Economics* 9(1), 3-18. Le facteur SMB de Fama et French (1993) le
        formalise en portefeuille.

        Limites. Le logarithme d'une capitalisation nulle n'existe pas, et une
        capitalisation manquante écarte l'actif de la date. La linéarité
        résiduelle laisse par ailleurs passer l'effet de décile extrême.

        Alternatives. Régresser sur le rang de taille, qui ne suppose plus la
        linéarité, ou neutraliser à l'intérieur de tranches de taille, ce qui
        revient au codage en indicatrices.

        Choix du laboratoire. Le logarithme est retenu par défaut parce qu'il est
        la convention de tous les modèles de risque cités, ce qui rend les
        chargements comparables à ceux de la littérature.

        Vérification. Sur une capitalisation fixe dans le temps, le résidu est
        identique à celui obtenu en passant le logarithme à la main. Un test du
        module le vérifie.
    """
    exposure = market_caps
    if log:
        frame, numeric = _as_panel(market_caps, _reference_panel(panel), "market_cap")
        if not numeric:
            raise ConfigError("la capitalisation doit être numérique")
        values = frame.to_numpy(dtype=float)
        finite = np.isfinite(values)
        if bool(np.any(values[finite] <= 0.0)):
            raise DataQualityError("une capitalisation est nulle ou négative : son logarithme n'existe pas")
        exposure = pd.DataFrame(np.log(values), index=frame.index, columns=frame.columns)
    return neutralize(
        panel,
        {"size": exposure},
        add_intercept=add_intercept,
        weights=weights,
        min_names=min_names,
    )


def _reference_panel(panel: pd.DataFrame) -> pd.DataFrame:
    """Rend le panier après contrôle de forme, pour les fonctions qui prétraitent.

    Args:
        panel: le panier de signal à contrôler.

    Returns:
        Le panier lui-même, une fois ses doublons refusés.

    Raises:
        ConfigError: si l'objet n'est pas un tableau pandas.
        DataQualityError: si une date ou un actif apparaît deux fois.
    """
    if not isinstance(panel, pd.DataFrame):
        raise ConfigError("le panier de signal doit être un DataFrame pandas")
    _check_frame(panel, "le panier de signal")
    return panel


def orthogonalize(
    signal: pd.DataFrame,
    other_signals: pd.DataFrame | Mapping[str, pd.DataFrame] | Sequence[pd.DataFrame],
    *,
    add_intercept: bool = True,
    weights: ExposureLike | None = None,
    min_names: int = DEFAULT_MIN_NAMES,
) -> pd.DataFrame:
    r"""Rend la part d'un signal que d'autres signaux n'expliquent pas.

    **Le problème.** Un laboratoire accumule des signaux, et chaque nouveau
    candidat ressemble aux précédents. La question qui décide de le garder ou non
    n'est pas « prédit-il ? » mais « prédit-il ce que les autres ne prédisent
    pas ? ». Un signal corrélé à 0,9 avec un signal déjà en production
    n'apporte presque rien, quel que soit son coefficient d'information.

    **L'intuition.** Projeter le candidat sur les signaux existants, à chaque
    date, et mesurer le résidu. Si le résidu ne prédit plus rien, le candidat
    était une reformulation.

    .. math::

        e_t = s_t - S_t (S_t^{\top} S_t)^{-1} S_t^{\top} s_t

    Args:
        signal: le signal candidat, dates en lignes, actifs en colonnes.
        other_signals: les signaux déjà connus. Un ``DataFrame`` seul, un
            dictionnaire qui les nomme, ou une suite de tableaux nommés
            ``other_1``, ``other_2`` et ainsi de suite.
        add_intercept: ajoute la constante transversale.
        weights: les poids de la régression, voir :func:`neutralize`.
        min_names: le nombre minimal d'actifs exploitables à une date.

    Returns:
        La part du candidat orthogonale aux autres, de la forme de ``signal``.

    Raises:
        ConfigError: si ``other_signals`` est vide ou d'un type inattendu.
        DataQualityError: si deux signaux existants sont identiques, donc
            colinéaires.
        InsufficientDataError: si aucune date n'est exploitable.

    Example:
        Un candidat égal à la somme de deux signaux existants se réduit
        exactement à zéro.

    Note:
        Variables. :math:`s_t` est le candidat à la date :math:`t`, :math:`S_t`
        la matrice des signaux existants, et :math:`e_t` la part neuve.

        Hypothèses. La redondance est linéaire. Deux signaux peuvent porter la
        même information sous une forme non linéaire, et ressortir orthogonaux
        alors qu'ils disent la même chose.

        Provenance. L'idée de juger un facteur candidat par ce qu'il ajoute à un
        modèle existant est celle de Barillas et Shanken (2017), « Which alpha ? »,
        *Review of Financial Studies* 30(4), 1316-1338. Voir aussi Fama et French
        (2015) sur l'absorption d'un facteur par cinq autres.

        Limites. L'ordre de projection compte pour l'interprétation, jamais pour
        le résidu. Deux signaux fortement corrélés rendent un résidu de faible
        variance, donc bruité, et son coefficient d'information devient difficile
        à distinguer de zéro.

        Alternatives. Comparer les alphas de deux régressions emboîtées, ce qui
        teste la même chose sur les rendements du portefeuille et non sur le
        signal lui-même. Ou mesurer la corrélation transversale moyenne, plus
        simple mais muette dès qu'il y a plus de deux signaux.

        Choix du laboratoire. Le résidu se mesure ensuite avec les mêmes outils
        que le signal d'origine, ce qui rend les deux verdicts comparables.

        Vérification. Le résidu d'un candidat déjà orthogonal est le candidat
        lui-même. Un test du module le vérifie.
    """
    if isinstance(other_signals, pd.DataFrame):
        named: dict[str, ExposureLike] = {"other": other_signals}
    elif isinstance(other_signals, Mapping):
        if not other_signals:
            raise ConfigError("le dictionnaire de signaux existants est vide")
        named = {str(key): value for key, value in other_signals.items()}
    elif isinstance(other_signals, Sequence):
        if not other_signals:
            raise ConfigError("la suite de signaux existants est vide")
        named = {f"other_{position}": frame for position, frame in enumerate(other_signals, start=1)}
    else:
        raise ConfigError("other_signals doit être un DataFrame, un dictionnaire ou une suite")

    return neutralize(
        signal,
        named,
        add_intercept=add_intercept,
        weights=weights,
        min_names=min_names,
    )


def _fama_macbeth_tstat(loadings: pd.Series) -> float:
    r"""Rend le t de Fama et MacBeth d'une série de chargements datés.

    .. math::

        t = \frac{\bar{b}}{\hat{\sigma}_b / \sqrt{T}}

    Args:
        loadings: les chargements, un par date, valeurs manquantes admises.

    Returns:
        Le t, ou ``nan`` si moins de deux dates sont disponibles, ou si la
        dispersion est nulle. Une dispersion nulle rendrait un t infini, qui
        décrit la coïncidence de l'échantillon et non une régularité.
    """
    clean = loadings.dropna()
    n = len(clean)
    if n < _MIN_PERIODS_FOR_TSTAT:
        return float("nan")
    dispersion = float(clean.std(ddof=1))
    if not np.isfinite(dispersion) or dispersion <= 0.0:
        return float("nan")
    return float(clean.mean()) / (dispersion / np.sqrt(n))


def exposure_report(
    panel: pd.DataFrame,
    exposures: ExposureSet,
    *,
    add_intercept: bool = True,
    weights: ExposureLike | None = None,
    min_names: int = DEFAULT_MIN_NAMES,
    collinearity_tol: float = DEFAULT_COLLINEARITY_TOL,
) -> pd.DataFrame:
    r"""Compare les chargements du signal avant et après neutralisation.

    **Le problème.** Une neutralisation est une opération silencieuse : elle rend
    un tableau de même forme, et rien ne dit si elle a fait son travail. Un
    rapport d'étude qui annonce un signal neutre au secteur sans le montrer
    demande au lecteur de le croire sur parole.

    **L'intuition.** Le chargement transversal du signal sur chaque exposition se
    calcule avant et après. Avant, il vaut ce qu'il vaut ; après, il vaut zéro.
    La moyenne des chargements sur les dates, et leur t, résument les deux états
    en une ligne par exposition.

    .. math::

        \bar{b}_k = \frac{1}{T} \sum_{t=1}^{T} b_{k,t},
        \qquad
        t_k = \frac{\bar{b}_k}{\hat{\sigma}_{b_k} / \sqrt{T}}

    Définition de chaque variable :

    - :math:`b_{k,t}` le chargement de l'exposition :math:`k` à la date
      :math:`t`, issu de la régression transversale ;
    - :math:`T` le nombre de dates où ce chargement est défini ;
    - :math:`\hat{\sigma}_{b_k}` l'écart type d'échantillon des chargements.

    Args:
        panel: le signal, dates en lignes, actifs en colonnes.
        exposures: les expositions, voir :func:`neutralize`.
        add_intercept: ajoute la constante transversale.
        weights: les poids de la régression, voir :func:`neutralize`.
        min_names: le nombre minimal d'actifs exploitables à une date.
        collinearity_tol: le seuil relatif de refus d'un plan singulier.

    Returns:
        Un tableau indexé par les colonnes du plan, portant ``loading_before``,
        ``tstat_before``, ``loading_after``, ``tstat_after`` et ``n_periods``.

    Raises:
        DataQualityError: si le plan est singulier à une date.
        InsufficientDataError: si aucune date n'est exploitable.

    Note:
        Hypothèses. Le t de Fama et MacBeth suppose les chargements
        indépendants d'une date à l'autre. Sur des expositions lentes, comme la
        taille ou le secteur, cette indépendance est fausse et le t est trop
        grand. Le corriger demande un estimateur HAC sur la série des
        chargements, que :func:`quantlab.analytics.ic.ic_summary` sait faire.

        Provenance. La procédure en deux temps, régression transversale puis
        moyenne dans le temps, est celle de Fama et MacBeth (1973), « Risk,
        return, and equilibrium: empirical tests », *Journal of Political
        Economy* 81(3), 607-636.

        Limites. Le chargement d'après neutralisation vaut zéro en arithmétique
        exacte, donc son t est un rapport de deux poussières d'arrondi. Il est
        rendu manquant dès que le chargement résiduel tombe sous
        ``RESIDUAL_LOADING_TOL`` fois son ampleur d'origine. Publier un t de 0,7
        sur du bruit d'arrondi tromperait le lecteur. Une date où la référence
        d'un bloc qualitatif a dû changer est par ailleurs écartée du bloc et de
        la constante. Leurs chargements y sont déclarés manquants, donc ils
        n'entrent ni dans la moyenne ni dans ``n_periods``.

        Alternatives. Montrer la corrélation transversale moyenne entre signal et
        exposition, plus intuitive, mais qui ne se lit plus dès que les
        expositions sont corrélées entre elles.

        Choix du laboratoire. Les deux colonnes se lisent ensemble : la première
        dit ce que le signal contenait, la seconde prouve que la neutralisation
        l'a retiré. C'est cette preuve que le rapport d'étude doit porter.

        Vérification. Sur un signal construit avec des chargements connus, la
        colonne d'avant retrouve ces chargements à la précision machine. Un test
        du module le vérifie.
    """
    residual, before = _engine(
        panel,
        exposures,
        add_intercept=add_intercept,
        weights=weights,
        min_names=min_names,
        collinearity_tol=collinearity_tol,
    )
    _, after = _engine(
        residual,
        exposures,
        add_intercept=add_intercept,
        weights=weights,
        min_names=min_names,
        collinearity_tol=collinearity_tol,
    )

    rows: dict[str, list[float]] = {
        "loading_before": [],
        "tstat_before": [],
        "loading_after": [],
        "tstat_after": [],
        "n_periods": [],
    }
    for column in before.columns:
        left = before[column]
        right = after[column]
        scale = float(left.abs().max())
        if not np.isfinite(scale) or scale == 0.0:
            scale = 1.0
        residual_scale = float(right.abs().max())
        negligible = np.isfinite(residual_scale) and residual_scale <= RESIDUAL_LOADING_TOL * scale
        rows["loading_before"].append(float(left.mean()))
        rows["tstat_before"].append(_fama_macbeth_tstat(left))
        rows["loading_after"].append(float(right.mean()))
        rows["tstat_after"].append(float("nan") if negligible else _fama_macbeth_tstat(right))
        rows["n_periods"].append(float(left.notna().sum()))

    report = pd.DataFrame(rows, index=pd.Index(before.columns, name="exposure"))
    return report.astype({"n_periods": int})

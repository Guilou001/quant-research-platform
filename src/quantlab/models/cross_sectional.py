"""Les modèles transversaux, du linéaire aux arbres, derrière le protocole AlphaModel.

**Le problème.** Gu, Kelly et Xiu (2020) comparent treize méthodes sur le même
découpage et le même jeu de variables. Ce qui compte n'est pas la méthode mais
la discipline. Même panneau, même ordre des dates, même réglage des
hyperparamètres sur une fenêtre de validation qui précède le test, et jamais
sur le test.

**Ce que le module fait.** Il enveloppe des estimateurs de ``scikit-learn``
derrière une spécification nommée et une grille d'hyperparamètres déclarée.
Une analyse glissante choisit la configuration sur les dernières dates de
l'entraînement, réajuste, puis prévoit le bloc de test. Chaque modèle
ajusté satisfait :class:`quantlab.core.protocols.AlphaModel` : un nom, et une
méthode ``predict`` qui rend un score par titre.

**Ce qu'il ne fait pas.** Il ne convertit rien en poids, ne facture aucun
coût, et n'importe aucun fournisseur de données. ``scikit-learn`` reste
invisible depuis les stratégies, comme ``skfolio`` l'est depuis
:mod:`quantlab.portfolio` (ADR-013).
"""

from __future__ import annotations

import functools
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import ElasticNet, HuberRegressor, Lasso, LinearRegression, Ridge
from sklearn.neural_network import MLPRegressor

from quantlab.core.errors import ConfigError, InsufficientDataError, LookAheadError
from quantlab.core.logging import get_logger
from quantlab.models.evaluation import oos_r2
from quantlab.models.panel import Panel
from quantlab.validation.splits import WalkForward

__all__ = [
    "FACTORIES",
    "FAMILIES",
    "ConfigChoice",
    "FittedModel",
    "FoldResult",
    "ModelSpec",
    "WalkForwardPredictions",
    "fit_model",
    "permutation_importance",
    "select_config",
    "spec_from_config",
    "walk_forward_predict",
]

_LOG = get_logger(__name__)

#: Les trois familles de l'article : linéaire, arbres, réseaux.
FAMILIES: tuple[str, ...] = ("linear", "tree", "network")

#: Le nombre maximal d'itérations des solveurs à coordonnées, déclaré.
MAX_ITER_LINEAR: int = 5_000


def _ols(seed: int, **kw: Any) -> BaseEstimator:
    """Les moindres carrés ordinaires, sans hyperparamètre."""
    del seed
    return LinearRegression(**kw)


def _huber(seed: int, **kw: Any) -> BaseEstimator:
    """La régression robuste à perte de Huber, celle de l'article pour le linéaire."""
    del seed
    return HuberRegressor(max_iter=MAX_ITER_LINEAR, **kw)


def _ridge(seed: int, **kw: Any) -> BaseEstimator:
    """La régression à pénalité quadratique."""
    del seed
    return Ridge(**kw)


def _lasso(seed: int, **kw: Any) -> BaseEstimator:
    """La régression à pénalité en valeur absolue."""
    del seed
    return Lasso(max_iter=MAX_ITER_LINEAR, **kw)


def _elastic_net(seed: int, **kw: Any) -> BaseEstimator:
    """Le filet élastique, mélange des deux pénalités."""
    del seed
    return ElasticNet(max_iter=MAX_ITER_LINEAR, **kw)


def _gbrt(seed: int, **kw: Any) -> BaseEstimator:
    """Les arbres de régression amplifiés par gradient, à histogrammes."""
    return HistGradientBoostingRegressor(random_state=seed, **kw)


def _random_forest(seed: int, **kw: Any) -> BaseEstimator:
    """La forêt aléatoire."""
    return RandomForestRegressor(random_state=seed, **kw)


def _mlp(seed: int, **kw: Any) -> BaseEstimator:
    """Le perceptron multicouche, avec arrêt anticipé."""
    return MLPRegressor(random_state=seed, early_stopping=True, **kw)


#: Les fabriques nommées, chacune avec sa famille.
FACTORIES: Mapping[str, tuple[str, Callable[..., BaseEstimator]]] = {
    "ols": ("linear", _ols),
    "huber": ("linear", _huber),
    "ridge": ("linear", _ridge),
    "lasso": ("linear", _lasso),
    "elastic_net": ("linear", _elastic_net),
    "gbrt": ("tree", _gbrt),
    "random_forest": ("tree", _random_forest),
    "mlp": ("network", _mlp),
}


@dataclass(frozen=True)
class ModelSpec:
    """Une méthode nommée, sa famille, sa fabrique et sa grille d'hyperparamètres.

    Attributes:
        name: le nom court employé dans les tableaux.
        family: ``linear``, ``tree`` ou ``network``.
        factory: la fonction qui rend un estimateur neuf pour une configuration.
        grid: les configurations candidates, au moins une ; chacune est un
            essai au sens du compte des essais.
    """

    name: str
    family: str
    factory: Callable[..., BaseEstimator]
    grid: tuple[dict[str, Any], ...]

    def __post_init__(self) -> None:
        if self.family not in FAMILIES:
            raise ConfigError(f"family doit être dans {FAMILIES}, reçu {self.family!r}.")
        if not self.grid:
            raise ConfigError(f"{self.name} : la grille doit porter au moins une configuration.")

    @property
    def n_configs(self) -> int:
        """Le nombre de configurations, donc d'essais que la méthode déclare."""
        return len(self.grid)


def spec_from_config(name: str, grid: Sequence[Mapping[str, Any]] | None, *, seed: int) -> ModelSpec:
    """Construit une spécification depuis un nom de fabrique et une grille déclarée.

    Args:
        name: une clé de :data:`FACTORIES`.
        grid: les configurations, ou ``None`` pour la configuration par défaut.
        seed: la graine passée aux estimateurs qui en prennent une.

    Returns:
        La spécification.

    Raises:
        ConfigError: le nom est inconnu.
    """
    if name not in FACTORIES:
        raise ConfigError(f"méthode inconnue {name!r} ; connues : {sorted(FACTORIES)}.")
    family, factory = FACTORIES[name]
    configs = tuple(dict(g) for g in grid) if grid else ({},)
    return ModelSpec(name=name, family=family, factory=functools.partial(factory, int(seed)), grid=configs)


@dataclass(frozen=True)
class FittedModel:
    """Un modèle ajusté, qui satisfait le protocole ``AlphaModel``.

    Attributes:
        name: le nom de la méthode.
        estimator: l'estimateur ajusté.
        feature_names: les colonnes attendues, dans l'ordre d'ajustement.
        config: la configuration retenue.
    """

    name: str
    estimator: BaseEstimator
    feature_names: tuple[str, ...]
    config: dict[str, Any]

    def predict(self, features: pd.DataFrame) -> pd.Series:
        """Rend un score par ligne du panneau, dans l'ordre de ses lignes.

        Args:
            features: un panneau portant au moins les colonnes d'ajustement.

        Returns:
            Les prévisions, indexées comme ``features``, nommées par la méthode.

        Raises:
            ConfigError: une colonne d'ajustement manque.
        """
        missing = [c for c in self.feature_names if c not in features.columns]
        if missing:
            raise ConfigError(f"colonnes absentes du panneau : {missing}")
        values = self.estimator.predict(features.loc[:, list(self.feature_names)].to_numpy(dtype=float))
        return pd.Series(np.asarray(values, dtype=float), index=features.index, name=self.name)


def fit_model(
    spec: ModelSpec, config: Mapping[str, Any], features: pd.DataFrame, label: pd.Series
) -> FittedModel:
    """Ajuste une configuration sur un panneau étiqueté.

    Args:
        spec: la méthode.
        config: la configuration d'hyperparamètres.
        features: les caractéristiques, sans manquant.
        label: l'étiquette, sans manquant, même index.

    Returns:
        Le modèle ajusté.

    Raises:
        InsufficientDataError: moins de deux observations.
    """
    if len(features) < 2:
        raise InsufficientDataError("au moins deux observations sont nécessaires pour ajuster.")
    estimator = spec.factory(**dict(config))
    estimator.fit(features.to_numpy(dtype=float), label.to_numpy(dtype=float))
    return FittedModel(spec.name, estimator, tuple(str(c) for c in features.columns), dict(config))


@dataclass(frozen=True)
class ConfigChoice:
    """Le choix d'une configuration sur la fenêtre de validation.

    Attributes:
        config: la configuration retenue.
        chosen_index: sa position dans la grille.
        validation_r2: le R² de validation de chaque configuration, dans
            l'ordre de la grille ; NaN quand la grille n'a qu'une entrée.
        n_validation_dates: le nombre de dates de validation employées.
    """

    config: dict[str, Any]
    chosen_index: int
    validation_r2: tuple[float, ...]
    n_validation_dates: int


def select_config(
    spec: ModelSpec,
    panel: Panel,
    train_dates: pd.DatetimeIndex,
    *,
    validation_periods: int,
    purge: int,
) -> ConfigChoice:
    r"""Choisit la configuration par le R² sur les dernières dates de l'entraînement.

    **Le problème.** Un hyperparamètre réglé sur le bloc de test transforme
    une mesure hors échantillon en mesure dans l'échantillon, sans qu'aucune
    erreur ne le signale.

    **L'intuition.** L'entraînement se coupe en deux, chronologiquement. La
    première partie ajuste chaque configuration, la seconde, la validation,
    les départage. Une purge sépare les deux, comme entre entraînement et
    test. Le test n'est jamais consulté.

    **La formule.** La configuration retenue est
    :math:`\arg\max_j R^2_{oos}(\text{validation} \mid j)`, avec la première
    en cas d'égalité.

    **Les variables.** :math:`j` parcourt la grille ; le R² est celui de
    :func:`quantlab.models.evaluation.oos_r2`.

    **Les hypothèses.** Les dernières dates de l'entraînement ressemblent au
    test davantage que les premières, ce qui justifie de valider à la fin.

    **La provenance.** Gu, Kelly et Xiu (2020), section 1.3 : échantillon
    d'entraînement, de validation et de test, dans cet ordre, sans mélange.

    **Les limites.** La validation est courte, donc bruitée, et un modèle
    peut être choisi pour une bonne année. Le compte des configurations entre
    dans les essais déclarés.

    **Les alternatives.** Une validation croisée purgée à l'intérieur de
    l'entraînement, plus stable et plus coûteuse.

    **Pourquoi cette méthode ici.** C'est celle de l'article, et elle
    conserve l'ordre du temps.

    **Comment vérifier.** Une grille où une configuration est absurde, par
    exemple une pénalité de :math:`10^9`, ne la retient jamais.

    Args:
        spec: la méthode et sa grille.
        panel: le panneau, étiquettes observées seulement.
        train_dates: les dates d'entraînement, croissantes.
        validation_periods: le nombre de dates finales réservées à la validation.
        purge: le nombre de dates retirées entre ajustement et validation.

    Returns:
        Le choix, avec le R² de validation de chaque configuration.

    Raises:
        InsufficientDataError: l'entraînement est trop court pour être coupé.
    """
    if spec.n_configs == 1:
        return ConfigChoice(dict(spec.grid[0]), 0, (math.nan,), 0)
    n_fit = len(train_dates) - int(validation_periods) - int(purge)
    if n_fit < 2:
        raise InsufficientDataError(
            f"{len(train_dates)} dates d'entraînement ne laissent pas de place à "
            f"{validation_periods} dates de validation et {purge} de purge."
        )
    fit_dates = train_dates[:n_fit]
    validation_dates = train_dates[len(train_dates) - int(validation_periods) :]
    fit_rows = panel.rows_at(fit_dates)
    validation_rows = panel.rows_at(validation_dates)
    x_fit, y_fit = panel.features.iloc[fit_rows], panel.label.iloc[fit_rows]
    x_val, y_val = panel.features.iloc[validation_rows], panel.label.iloc[validation_rows]
    scores: list[float] = []
    for config in spec.grid:
        model = fit_model(spec, config, x_fit, y_fit)
        scores.append(oos_r2(y_val, model.predict(x_val)))
    ranked = [(-s if math.isfinite(s) else math.inf, j) for j, s in enumerate(scores)]
    best = min(ranked)[1]
    return ConfigChoice(dict(spec.grid[best]), best, tuple(scores), len(validation_dates))


@dataclass(frozen=True)
class FoldResult:
    """Ce qu'un pli de l'analyse glissante a fait et mesuré.

    Attributes:
        fold: le numéro du pli, à partir de zéro.
        train_start: la première date d'entraînement.
        train_end: la dernière date d'entraînement, purge comprise.
        test_start: la première date de test.
        test_end: la dernière date de test.
        n_train: le nombre d'observations étiquetées d'entraînement.
        n_test: le nombre d'observations prévues.
        config: la configuration retenue.
        validation_r2: le R² de validation de cette configuration.
        test_r2: le R² hors échantillon du pli.
    """

    fold: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    n_train: int
    n_test: int
    config: dict[str, Any]
    validation_r2: float
    test_r2: float


@dataclass(frozen=True)
class WalkForwardPredictions:
    """Les prévisions hors échantillon d'une méthode, pli après pli.

    Attributes:
        name: le nom de la méthode.
        family: sa famille.
        predictions: les prévisions, indexées par (date, titre), dates de test
            seulement.
        folds: le compte rendu de chaque pli.
        n_configs: le nombre de configurations de la grille.
        last_model: le modèle ajusté du dernier pli, pour l'importance des
            variables et l'inspection.
    """

    name: str
    family: str
    predictions: pd.Series
    folds: tuple[FoldResult, ...]
    n_configs: int
    last_model: FittedModel

    def report(self) -> pd.DataFrame:
        """Rend le compte rendu des plis en tableau."""
        rows = [
            {
                "fold": f.fold,
                "train_start": f.train_start,
                "train_end": f.train_end,
                "test_start": f.test_start,
                "test_end": f.test_end,
                "n_train": f.n_train,
                "n_test": f.n_test,
                "config": str(f.config),
                "validation_r2": f.validation_r2,
                "test_r2": f.test_r2,
            }
            for f in self.folds
        ]
        return pd.DataFrame(rows).set_index("fold")


def walk_forward_predict(
    panel: Panel,
    spec: ModelSpec,
    split: WalkForward,
    *,
    validation_periods: int,
) -> WalkForwardPredictions:
    r"""Prévoit chaque bloc de test avec un modèle ajusté sur le seul passé purgé.

    **Le problème.** La seule prévision qui vaut est celle faite avec
    l'information d'alors. Un modèle ajusté une fois sur tout l'historique
    et évalué sur une partie de lui prévoit ce qu'il a déjà vu.

    **L'intuition.** Refaire le geste du gérant. À chaque pli, les dates
    d'entraînement précèdent les dates de test, et une purge d'au moins
    l'horizon de l'étiquette les sépare. La configuration se choisit sur la
    fin de l'entraînement. Le modèle se réajuste ensuite sur tout
    l'entraînement, puis prévoit le bloc.

    **La formule.** Pour le pli :math:`k`, entraînement sur
    :math:`\{t \le T_k - p\}`, test sur :math:`\{T_k < t \le T_k + s\}`,
    avec :math:`p` la purge et :math:`s` la taille du bloc.

    **Les variables.** Celles de
    :class:`quantlab.validation.splits.WalkForward`, qui porte le découpage.

    **Les hypothèses.** Les lignes non étiquetées servent à prévoir, jamais à
    ajuster. Le bloc de test n'est jamais lu avant la prévision, ce qu'une
    vérification d'ordre des dates fait respecter.

    **La provenance.** Gu, Kelly et Xiu (2020), section 1.3 ; López de Prado
    (2018), chapitre 7, pour la purge.

    **Les limites.** Le réajustement sur tout l'entraînement s'écarte de
    l'article, qui garde le modèle validé ; c'est déclaré dans l'étude.

    **Les alternatives.** La validation croisée combinatoire purgée, qui rend
    plusieurs chemins et sert à la probabilité de surapprentissage.

    **Pourquoi cette méthode ici.** Elle reproduit l'ordre réel des décisions,
    et c'est cet ordre que le laboratoire mesure.

    **Comment vérifier.** Sur un panneau où l'étiquette est une fonction
    linéaire connue des caractéristiques, la régression retrouve un R² hors
    échantillon élevé ; et chaque pli a ``train_end`` strictement avant
    ``test_start``.

    Args:
        panel: le panneau entier, étiquettes manquantes admises.
        spec: la méthode et sa grille.
        split: le découpage glissant, appliqué aux dates uniques du panneau.
        validation_periods: les dates finales de l'entraînement réservées au
            choix de la configuration.

    Returns:
        Les prévisions des blocs de test, et le compte rendu des plis.

    Raises:
        LookAheadError: un pli place une date de test avant la fin de
            l'entraînement, ce qui ne doit jamais arriver.
        InsufficientDataError: aucun pli ne tient dans l'historique.
    """
    dates = panel.dates
    observed = panel.observed()
    folds: list[FoldResult] = []
    pieces: list[pd.Series] = []
    for k, (train_idx, test_idx) in enumerate(split.split(np.arange(len(dates)))):
        train_dates = dates[np.asarray(train_idx)]
        test_dates = dates[np.asarray(test_idx)]
        if train_dates.max() >= test_dates.min():
            raise LookAheadError(
                f"pli {k} : l'entraînement finit le {train_dates.max().date()} et le test "
                f"commence le {test_dates.min().date()}."
            )
        choice = select_config(
            spec, observed, train_dates, validation_periods=validation_periods, purge=int(split.purge)
        )
        train_rows = observed.rows_at(train_dates)
        model = fit_model(
            spec, choice.config, observed.features.iloc[train_rows], observed.label.iloc[train_rows]
        )
        test_rows = panel.rows_at(test_dates)
        predicted = model.predict(panel.features.iloc[test_rows])
        pieces.append(predicted)
        realized = panel.label.iloc[test_rows]
        test_r2 = oos_r2(realized, predicted) if realized.notna().sum() > 1 else math.nan
        folds.append(
            FoldResult(
                fold=k,
                train_start=pd.Timestamp(train_dates.min()),
                train_end=pd.Timestamp(train_dates.max()),
                test_start=pd.Timestamp(test_dates.min()),
                test_end=pd.Timestamp(test_dates.max()),
                n_train=len(train_rows),
                n_test=len(test_rows),
                config=choice.config,
                validation_r2=float(choice.validation_r2[choice.chosen_index]),
                test_r2=float(test_r2),
            )
        )
        _LOG.info(
            "pli prévu",
            extra={
                "model": spec.name,
                "fold": k,
                "test_start": str(test_dates.min().date()),
                "test_r2": test_r2,
            },
        )
    if not folds:
        raise InsufficientDataError("aucun pli : l'historique est plus court que train_size + test_size.")
    predictions = pd.concat(pieces).rename(spec.name)
    return WalkForwardPredictions(spec.name, spec.family, predictions, tuple(folds), spec.n_configs, model)


def permutation_importance(
    model: FittedModel,
    features: pd.DataFrame,
    label: pd.Series,
    *,
    seed: int,
    n_repeats: int = 5,
) -> pd.DataFrame:
    r"""Rend l'importance de chaque caractéristique par permutation, mesurée hors échantillon.

    **Le problème.** Un arbre ne rend pas de coefficient, et un coefficient
    linéaire sur des rangs ne dit pas ce que le modèle perdrait sans la
    variable.

    **L'intuition.** Mélanger une colonne entre les lignes, prévoir à nouveau,
    et mesurer de combien le R² tombe. Une variable dont la permutation ne
    change rien ne servait à rien.

    .. math::

        I_j = R^2_{oos} - \frac{1}{K}\sum_{k=1}^{K} R^2_{oos}\left(X^{(j,k)}\right)

    **Les variables.** :math:`X^{(j,k)}` le panneau dont la colonne :math:`j`
    est permutée une :math:`k`-ième fois.

    **Les hypothèses.** Les permutations cassent aussi les dépendances entre
    variables, donc deux variables redondantes se partagent une importance
    faible chacune.

    **La provenance.** Breiman (2001), Random forests, Machine Learning 45,
    rapporté. Gu, Kelly et Xiu (2020) mesurent plutôt la baisse du R² en
    fixant la variable à zéro, ce qui est proche sur des rangs centrés.

    **Les limites.** Mesurée sur un seul bloc de test, elle est bruitée, et
    elle ne dit pas le signe de l'effet.

    **Les alternatives.** Les valeurs de Shapley, plus coûteuses.

    **Pourquoi cette méthode ici.** Elle vaut pour tout modèle, linéaire ou
    non, avec la même définition.

    **Comment vérifier.** Sur une étiquette qui ne dépend que de la première
    colonne, c'est elle qui porte l'importance et les autres sont proches de
    zéro.

    Args:
        model: le modèle ajusté.
        features: le panneau de test, sans manquant.
        label: l'étiquette observée, même index.
        seed: la graine des permutations.
        n_repeats: le nombre de permutations par colonne.

    Returns:
        Un tableau indexé par caractéristique, colonnes ``importance`` et
        ``importance_std``, trié par importance décroissante.
    """
    keep = label.notna().to_numpy()
    if int(keep.sum()) < 2:
        raise InsufficientDataError("l'importance par permutation exige au moins deux étiquettes observées.")
    x = features.loc[:, list(model.feature_names)].iloc[keep]
    y = label.iloc[keep]
    base = oos_r2(y, model.predict(x))
    rng = np.random.default_rng(int(seed))
    rows = []
    for column in model.feature_names:
        drops = []
        for _ in range(int(n_repeats)):
            shuffled = x.copy()
            shuffled[column] = rng.permutation(shuffled[column].to_numpy())
            drops.append(base - oos_r2(y, model.predict(shuffled)))
        rows.append(
            {"feature": column, "importance": float(np.mean(drops)), "importance_std": float(np.std(drops))}
        )
    return pd.DataFrame(rows).set_index("feature").sort_values("importance", ascending=False)

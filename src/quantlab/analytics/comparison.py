r"""Comparer la trajectoire d'une stratégie à celle d'un fonds réel.

**Le problème.** Un backtest rend une courbe. Un fonds coté en rend une autre,
construite par des gens qui paient des frais, subissent des flux et négocient
pour de vrai. Si les deux courbes se ressemblent, notre reconstruction capte le
même phénomène que le marché vend ; si elles divergent, l'écart est une
information, et il faut savoir de quel côté il penche.

**Ce que « se ressembler » veut dire ici, et ce que cela ne veut pas dire.**
Deux trajectoires se ressemblent à trois conditions. Leurs rendements
PÉRIODIQUES sont corrélés. La pente de l'une sur l'autre est proche de un. Leurs
replis tombent aux mêmes dates. Deux courbes de richesse cumulée qui finissent
au même niveau ne se ressemblent pas pour autant : une hausse régulière et un
krach suivi d'un rebond arrivent au même point par des chemins opposés. C'est
pourquoi la comparaison porte sur les rendements, jamais sur les niveaux.

**Le modèle.** La régression du fonds sur la stratégie,

.. math::

    r^{fonds}_t = \alpha + \beta \, r^{strat}_t + \epsilon_t

rend trois quantités lisibles. :math:`\beta` dit si le fonds amplifie ou
atténue la stratégie. :math:`\alpha` dit ce que le fonds gagne ou perd en plus,
frais compris. :math:`R^2` dit quelle part de la trajectoire du fonds la
stratégie explique. L'erreur de suivi, l'écart type annualisé de
:math:`\epsilon_t`, chiffre ce qui reste.

**Les limites, celle qui décide d'abord.** Un fonds ne publie ni son levier, ni
son univers exact, ni sa règle de rééquilibrage. Une corrélation de 0,8 avec
une stratégie prouve que le fonds fait QUELQUE CHOSE de proche, pas qu'il fait
la MÊME chose. Ensuite, les fonds cotés sont récents : la plupart des fonds de
facteurs datent de 2013, si bien que la comparaison porte sur une dizaine
d'années, toujours après la publication de l'article. Enfin, le fonds est NET
de frais et la stratégie reconstruite est le plus souvent BRUTE : l'alpha
mesuré ici porte donc les frais avec le signe moins, et il faut le lire ainsi.

**La provenance.** La régression d'un fonds sur ses facteurs est l'analyse de
style de Sharpe (1992), « Asset Allocation: Management Style and Performance
Measurement », Journal of Portfolio Management. Le recouvrement des replis est
un critère de ce laboratoire, précepte sans mesure publiée derrière. Il est
retenu parce qu'il attrape ce que la corrélation moyenne cache : deux séries
corrélées à 0,6 en moyenne peuvent perdre à des dates différentes.

**Comment vérifier.** Une stratégie comparée à elle-même rend une corrélation
de un, un bêta de un, un alpha nul et un recouvrement des replis de un. Une
stratégie comparée à son opposé rend une corrélation de moins un. Les tests du
module le vérifient, et ils vérifient la régression contre ``statsmodels``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
import yaml
from pydantic import Field, field_validator
from scipy import stats

from quantlab.analytics.drawdown import drawdown_series, max_drawdown
from quantlab.analytics.ratios import sharpe_ratio
from quantlab.analytics.regression import factor_regression
from quantlab.analytics.returns import align_returns, cumulative_wealth, resample_returns, to_returns
from quantlab.core.config import StrictModel
from quantlab.core.errors import InsufficientDataError
from quantlab.core.logging import get_logger
from quantlab.core.types import Frequency, ReturnKind

__all__ = [
    "DEFAULT_DRAWDOWN_THRESHOLD",
    "DEFAULT_MIN_PERIODS",
    "DEFAULT_ROLLING_WINDOW",
    "FundProxy",
    "TrajectoryComparison",
    "compare_trajectories",
    "comparison_table",
    "drawdown_overlap",
    "fund_returns_from_prices",
    "load_fund_registry",
    "similarity_reading",
]

_log = get_logger(__name__)

#: Fenêtre de la corrélation glissante, en périodes. Trente-six mois est le
#: choix usuel de l'analyse de style, assez long pour estimer une corrélation,
#: assez court pour voir un changement de régime.
DEFAULT_ROLLING_WINDOW = 36

#: Nombre minimal de périodes communes pour qu'une comparaison ait un sens. Sous
#: vingt-quatre mois, l'erreur type d'une corrélation dépasse 0,2 et le chiffre
#: ne tranche rien.
DEFAULT_MIN_PERIODS = 24

#: Un repli compte comme tel au-delà de ce seuil, en fraction. Cinq pour cent
#: sépare une respiration d'une perte, et c'est un précepte déclaré, non une
#: mesure.
DEFAULT_DRAWDOWN_THRESHOLD = 0.05


class FundProxy(StrictModel):
    """Un fonds réel qui vend au public ce qu'une stratégie du laboratoire reconstruit.

    Le registre des fonds vit dans ``benchmarks/funds.yaml``. Chaque fiche dit
    quelle famille de stratégie le fonds prétend suivre, depuis quand il cote,
    et ce qu'il faut savoir avant de le comparer.
    """

    ticker: str
    name: str
    family: str
    strategy_hint: str
    inception: str
    expense_ratio_bps: float | None = None
    notes: str = ""


@dataclass(frozen=True)
class TrajectoryComparison:
    """Le résultat d'une comparaison entre une stratégie et un fonds.

    Tous les chiffres sont mesurés sur la période COMMUNE, et cette période est
    écrite dans l'objet, parce qu'une corrélation sans sa fenêtre ne veut rien
    dire.
    """

    strategy: str
    fund: str
    start: pd.Timestamp
    end: pd.Timestamp
    n_periods: int
    frequency: Frequency
    correlation: float
    beta: float
    beta_tstat: float
    alpha_annual: float
    alpha_tstat: float
    r_squared: float
    tracking_error_annual: float
    sharpe_strategy: float
    sharpe_fund: float
    wealth_strategy: float
    wealth_fund: float
    max_drawdown_strategy: float
    max_drawdown_fund: float
    drawdown_overlap: float
    rolling_correlation_min: float
    rolling_correlation_median: float
    rolling_window: int

    def as_row(self) -> dict[str, Any]:
        """Rend la comparaison en une ligne de tableau."""
        return {
            "strategy": self.strategy,
            "fund": self.fund,
            "start": self.start.date(),
            "end": self.end.date(),
            "n_periods": self.n_periods,
            "correlation": self.correlation,
            "beta": self.beta,
            "beta_tstat": self.beta_tstat,
            "alpha_annual": self.alpha_annual,
            "alpha_tstat": self.alpha_tstat,
            "r_squared": self.r_squared,
            "tracking_error_annual": self.tracking_error_annual,
            "sharpe_strategy": self.sharpe_strategy,
            "sharpe_fund": self.sharpe_fund,
            "wealth_strategy": self.wealth_strategy,
            "wealth_fund": self.wealth_fund,
            "max_drawdown_strategy": self.max_drawdown_strategy,
            "max_drawdown_fund": self.max_drawdown_fund,
            "drawdown_overlap": self.drawdown_overlap,
            "rolling_correlation_min": self.rolling_correlation_min,
            "rolling_correlation_median": self.rolling_correlation_median,
            "reading": similarity_reading(self),
        }


def fund_returns_from_prices(
    prices: pd.DataFrame,
    *,
    frequency: Frequency = Frequency.MONTHLY,
) -> pd.DataFrame:
    """Rend les rendements d'un tableau de prix, à la fréquence demandée.

    Args:
        prices: prix ajustés, dates en lignes, fonds en colonnes.
        frequency: la fréquence de sortie. Le passage du quotidien au mensuel
            se fait en composant les rendements quotidiens, jamais en les
            moyennant.

    Returns:
        Les rendements simples, une colonne par fonds, les périodes sans prix
        laissées manquantes plutôt que remplies.
    """
    daily = to_returns(prices, ReturnKind.SIMPLE, dropna=False)
    if frequency is Frequency.DAILY:
        return daily
    out = {}
    for col in daily.columns:
        s = daily[col].dropna()
        if s.empty:
            continue
        out[col] = resample_returns(s, frequency, ReturnKind.SIMPLE)
    return pd.DataFrame(out)


def drawdown_overlap(
    a: pd.Series,
    b: pd.Series,
    *,
    threshold: float = DEFAULT_DRAWDOWN_THRESHOLD,
) -> float:
    r"""Rend la part des périodes de repli qui sont communes aux deux séries.

    **Le problème.** Deux séries corrélées à 0,6 en moyenne peuvent perdre à
    des dates différentes, et la corrélation ne le voit pas. Un investisseur,
    lui, le voit : ce qui compte est de savoir si les deux tombent ensemble.

    **La définition.** Une période est « en repli » quand la perte depuis le
    sommet dépasse le seuil. Le recouvrement est le rapport de Jaccard des deux
    ensembles de périodes en repli :

    .. math::

        J = \frac{|A \cap B|}{|A \cup B|}

    où :math:`A` et :math:`B` sont les ensembles de périodes en repli de chaque
    série. Il vaut un si les deux tombent toujours ensemble, zéro si jamais.

    Args:
        a: rendements de la première série.
        b: rendements de la seconde, sur le même index.
        threshold: la profondeur à partir de laquelle un repli compte.

    Returns:
        Le rapport de Jaccard, entre zéro et un. Vaut ``nan`` si aucune des
        deux séries n'a connu de repli au-delà du seuil, cas où la question ne
        se pose pas.
    """
    a, b = align_returns(a, b)
    in_a = drawdown_series(a) <= -threshold
    in_b = drawdown_series(b) <= -threshold
    union = int((in_a | in_b).sum())
    if union == 0:
        return float("nan")
    return float((in_a & in_b).sum() / union)


def compare_trajectories(
    strategy: pd.Series,
    fund: pd.Series,
    *,
    frequency: Frequency = Frequency.MONTHLY,
    rolling_window: int = DEFAULT_ROLLING_WINDOW,
    min_periods: int = DEFAULT_MIN_PERIODS,
    drawdown_threshold: float = DEFAULT_DRAWDOWN_THRESHOLD,
    strategy_name: str | None = None,
    fund_name: str | None = None,
) -> TrajectoryComparison:
    """Compare une stratégie reconstruite à un fonds réel sur leur période commune.

    Args:
        strategy: rendements de la stratégie, indexés par date.
        fund: rendements du fonds, même fréquence.
        frequency: la fréquence des deux séries.
        rolling_window: la fenêtre de la corrélation glissante.
        min_periods: le nombre minimal de périodes communes exigé.
        drawdown_threshold: la profondeur qui définit un repli.
        strategy_name: le nom affiché, sinon celui de la série.
        fund_name: le nom affiché, sinon celui de la série.

    Returns:
        La comparaison, tous chiffres mesurés sur la période commune.

    Raises:
        InsufficientDataError: si le recouvrement est plus court que
            ``min_periods``.

    Note:
        La régression est celle du FONDS sur la STRATÉGIE, pas l'inverse. Le
        bêta se lit donc « le fonds bouge de bêta pour un de la stratégie », et
        l'alpha est ce que le fonds ajoute ou retire, frais compris.
    """
    s, f = align_returns(strategy.dropna(), fund.dropna())
    if len(s) < min_periods:
        raise InsufficientDataError(
            f"{len(s)} périodes communes, il en faut au moins {min_periods} pour comparer"
        )
    s_name = strategy_name or str(strategy.name or "strategy")
    f_name = fund_name or str(fund.name or "fund")

    reg = factor_regression(f, s.rename(s_name), frequency=frequency)
    beta = float(reg.betas.iloc[0])
    beta_t = float(reg.beta_tstats.iloc[0])

    rolling = s.rolling(rolling_window, min_periods=rolling_window).corr(f).dropna()
    result = TrajectoryComparison(
        strategy=s_name,
        fund=f_name,
        start=pd.Timestamp(s.index.min()),
        end=pd.Timestamp(s.index.max()),
        n_periods=len(s),
        frequency=frequency,
        correlation=float(s.corr(f)),
        beta=beta,
        beta_tstat=beta_t,
        alpha_annual=float(reg.alpha),
        alpha_tstat=float(reg.alpha_tstat),
        r_squared=float(reg.r_squared),
        tracking_error_annual=float(reg.residuals.std(ddof=1) * np.sqrt(frequency.periods_per_year)),
        sharpe_strategy=float(sharpe_ratio(s, frequency=frequency)),
        sharpe_fund=float(sharpe_ratio(f, frequency=frequency)),
        wealth_strategy=float(cumulative_wealth(s).iloc[-1]),
        wealth_fund=float(cumulative_wealth(f).iloc[-1]),
        max_drawdown_strategy=float(max_drawdown(s)),
        max_drawdown_fund=float(max_drawdown(f)),
        drawdown_overlap=drawdown_overlap(s, f, threshold=drawdown_threshold),
        rolling_correlation_min=float(rolling.min()) if len(rolling) else float("nan"),
        rolling_correlation_median=float(rolling.median()) if len(rolling) else float("nan"),
        rolling_window=rolling_window,
    )
    _log.info(
        "trajectoires comparées",
        extra={
            "strategy": s_name,
            "fund": f_name,
            "n": result.n_periods,
            "corr": round(result.correlation, 3),
            "beta": round(result.beta, 3),
        },
    )
    return result


def similarity_reading(c: TrajectoryComparison) -> str:
    """Rend la lecture en mots d'une comparaison, selon des seuils déclarés.

    Les seuils sont des préceptes de ce laboratoire, écrits ici et nulle part
    ailleurs. « Même phénomène » exige une corrélation au-dessus de 0,7 et un
    recouvrement des replis au-dessus de 0,5. « Apparenté » couvre une
    corrélation entre 0,4 et 0,7, et « distinct » tout ce qui est en dessous. Un
    bêta hors de l'intervalle 0,5 à 2 ajoute « à une autre échelle », parce que
    le fonds amplifie ou dilue alors nettement la stratégie.
    """
    if np.isnan(c.correlation):
        return "non mesurable"
    if c.correlation >= 0.7 and (np.isnan(c.drawdown_overlap) or c.drawdown_overlap >= 0.5):
        base = "même phénomène"
    elif c.correlation >= 0.4:
        base = "apparenté"
    elif c.correlation <= -0.4:
        base = "opposé"
    else:
        base = "distinct"
    if base in {"même phénomène", "apparenté"} and not (0.5 <= c.beta <= 2.0):
        base += ", à une autre échelle"
    return base


def comparison_table(
    strategies: dict[str, pd.Series],
    funds: dict[str, pd.Series],
    *,
    pairs: list[tuple[str, str]] | None = None,
    frequency: Frequency = Frequency.MONTHLY,
    **kwargs: Any,
) -> pd.DataFrame:
    """Compare plusieurs stratégies à plusieurs fonds et rend le tableau.

    Args:
        strategies: les séries de rendements des stratégies, par nom.
        funds: les séries de rendements des fonds, par symbole.
        pairs: les couples à comparer. Sans valeur, toutes les combinaisons.
        frequency: la fréquence commune.
        **kwargs: transmis à :func:`compare_trajectories`.

    Returns:
        Une ligne par couple, les couples au recouvrement trop court omis et
        journalisés plutôt que remplis.
    """
    if pairs is None:
        pairs = [(s, f) for s in strategies for f in funds]
    rows = []
    for s_name, f_name in pairs:
        try:
            c = compare_trajectories(
                strategies[s_name],
                funds[f_name],
                frequency=frequency,
                strategy_name=s_name,
                fund_name=f_name,
                **kwargs,
            )
        except InsufficientDataError as exc:
            _log.warning("couple omis", extra={"strategy": s_name, "fund": f_name, "reason": str(exc)})
            continue
        rows.append(c.as_row())
    return pd.DataFrame(rows)


def load_fund_registry(path: str | Path) -> list[FundProxy]:
    """Lit le registre des fonds réels depuis son YAML."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return [FundProxy.model_validate(item) for item in raw.get("funds", [])]


# ---------------------------------------------------------------------------
# Les grands fonds fermés : comparaison sur rendements ANNUELS rapportés
# ---------------------------------------------------------------------------

#: Le nombre minimal d'années communes pour publier une corrélation annuelle.
MIN_ANNUAL_YEARS = 5

#: Le nombre minimal d'années pour que l'intervalle de Fisher soit défini.
FISHER_MIN_YEARS = 4

#: Le niveau de confiance de l'intervalle sur la corrélation.
DEFAULT_CONFIDENCE = 0.95

#: Le nombre de périodes exigé pour qu'une année soit complète, par fréquence.
COMPLETE_YEAR_PERIODS: dict[Frequency, int] = {Frequency.MONTHLY: 12, Frequency.DAILY: 240}

#: La borne appliquée à la corrélation avant la transformation de Fisher.
FISHER_CLIP = 1.0 - 1e-12


class HedgeFundRecord(StrictModel):
    """Un grand fonds fermé, connu par ses seuls rendements annuels rapportés.

    Le registre vit dans ``benchmarks/hedge_funds.yaml``. Chaque valeur porte
    le degré de vérification atteint. ``page`` signifie qu'elle a été lue à la
    source, ``titre`` que seul le titre d'un article la porte, ``resume``
    qu'elle vient d'un résumé de moteur de recherche. Une année absente est une
    année non trouvée.
    """

    key: str
    name: str
    manager: str
    style: str
    net_of_fees: bool = True
    annual_returns_pct: dict[int, float]
    gross_returns_pct: dict[int, float] = Field(default_factory=dict)
    verification: dict[str, str] = Field(default_factory=dict)
    sources: list[dict[str, str]] = Field(default_factory=list)
    notes: str = ""

    @field_validator("verification", mode="before")
    @classmethod
    def _keys_as_text(cls, value: object) -> object:
        """Écrit les clés d'années en texte, qu'elles soient un entier ou une plage."""
        if isinstance(value, dict):
            return {str(k): str(v) for k, v in value.items()}
        return value

    def verification_of(self, year: int) -> str:
        """Rend le degré de vérification d'une année, ou « non déclaré »."""
        for key, level in self.verification.items():
            if "-" in key:
                first, last = key.split("-", 1)
                if int(first) <= year <= int(last):
                    return level
            elif int(key) == year:
                return level
        return "non déclaré"


def load_hedge_fund_registry(path: str | Path) -> list[HedgeFundRecord]:
    """Lit le registre des grands fonds fermés depuis son YAML."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return [HedgeFundRecord.model_validate(item) for item in raw.get("funds", [])]


def hedge_fund_table(
    records: Sequence[HedgeFundRecord],
    *,
    basis: Literal["net", "gross"] = "net",
) -> pd.DataFrame:
    """Rend les rendements annuels en FRACTION, une colonne par fonds, une ligne par année.

    Args:
        records: les fiches du registre.
        basis: ``net`` pour les rendements nets de frais, ``gross`` pour les
            bruts, que seul Medallion publie.

    Returns:
        Un tableau indexé par année civile, manquant là où rien n'est rapporté.
    """
    columns: dict[str, pd.Series] = {}
    for record in records:
        source = record.annual_returns_pct if basis == "net" else record.gross_returns_pct
        if not source:
            continue
        columns[record.key] = pd.Series({int(y): float(v) / 100.0 for y, v in source.items()})
    if not columns:
        return pd.DataFrame()
    table = pd.DataFrame(columns).sort_index()
    table.index.name = "year"
    return table


def annual_returns(
    returns: pd.Series,
    *,
    frequency: Frequency = Frequency.MONTHLY,
    require_complete: bool = True,
) -> pd.Series:
    r"""Compose les rendements d'une série en rendements par année civile.

    **Le problème.** Les grands fonds ne publient qu'un chiffre par an. Pour
    les comparer à une stratégie mensuelle, il faut la ramener à l'année, et
    une année incomplète comparée à une année pleine fausse le niveau.

    **L'intuition.** Le rendement d'une année est le produit des facteurs de
    croissance de ses périodes, moins un. Une année qui n'a pas toutes ses
    périodes est écartée plutôt que complétée.

    **La formule.**

    .. math::

        R_{a} = \prod_{t \in a} (1 + r_t) - 1

    **Les variables.** :math:`r_t` le rendement simple d'une période,
    :math:`a` l'année civile.

    **Les hypothèses.** Les rendements sont simples, non logarithmiques. Une
    année est complète avec 12 mois en mensuel et 240 séances en quotidien.

    **La provenance.** Composition ordinaire ; aucune référence externe.

    **Les limites.** Une année de rendement composé masque la volatilité
    intra-annuelle, qui est précisément ce que les fonds fermés ne publient
    pas non plus.

    **Les alternatives.** Une somme de rendements logarithmiques, identique en
    exponentielle.

    **Pourquoi cette méthode ici.** C'est la seule échelle commune avec des
    fonds qui ne publient qu'un chiffre par an.

    **Comment vérifier.** Douze mois à 1 % donnent :math:`1{,}01^{12} - 1`,
    soit 12,6825 %.

    Args:
        returns: la série de rendements simples, indexée par date.
        frequency: sa fréquence, qui fixe le nombre de périodes d'une année
            complète.
        require_complete: écarter les années incomplètes.

    Returns:
        Une série indexée par année civile entière.

    Raises:
        InsufficientDataError: aucune année complète n'existe.
    """
    if not isinstance(returns.index, pd.DatetimeIndex):
        raise InsufficientDataError("annual_returns exige un index temporel.")
    clean = returns.dropna().astype(float)
    grouped = clean.groupby(clean.index.year)
    compounded = grouped.apply(lambda s: float(np.prod(1.0 + s.to_numpy()) - 1.0))
    if require_complete:
        needed = COMPLETE_YEAR_PERIODS.get(frequency)
        if needed is None:
            raise InsufficientDataError(f"aucune règle d'année complète pour la fréquence {frequency}.")
        counts = grouped.size()
        compounded = compounded[counts >= needed]
    if compounded.empty:
        raise InsufficientDataError("aucune année complète dans la série.")
    compounded.index = compounded.index.astype(int)
    compounded.index.name = "year"
    return compounded.rename(returns.name)


def fisher_interval(
    correlation: float, n: int, confidence: float = DEFAULT_CONFIDENCE
) -> tuple[float, float]:
    r"""Rend l'intervalle de confiance d'une corrélation par la transformation de Fisher.

    **Le problème.** Dix années communes donnent une corrélation dont l'erreur
    type vaut un tiers. La publier sans intervalle laisse croire à une
    précision qu'elle n'a pas.

    **L'intuition.** La corrélation transformée par la tangente hyperbolique
    inverse est à peu près normale, d'écart type :math:`1/\sqrt{n-3}`.

    **La formule.**

    .. math::

        z = \operatorname{artanh}(r), \qquad
        \left[\tanh\!\left(z - q\,\tfrac{1}{\sqrt{n-3}}\right),\
        \tanh\!\left(z + q\,\tfrac{1}{\sqrt{n-3}}\right)\right]

    **Les variables.** :math:`r` la corrélation estimée, :math:`n` le nombre
    d'observations, :math:`q` le quantile normal du niveau demandé.

    **Les hypothèses.** Les paires sont indépendantes et à peu près
    normales. Des rendements annuels le sont mieux que des mensuels.

    **La provenance.** Fisher (1915), Frequency distribution of the values of
    the correlation coefficient, Biometrika 10 ; précepte de manuel.

    **Les limites.** Sous quatre observations, l'intervalle n'est pas défini.
    Une corrélation de un exactement donne une transformée infinie, bornée
    ici par une constante.

    **Les alternatives.** Un bootstrap sur les paires, plus honnête quand
    :math:`n` est petit, mais bruité pour la même raison.

    **Pourquoi cette méthode ici.** Un seul paramètre et une forme fermée que
    le lecteur recalcule.

    **Comment vérifier.** Pour :math:`r = 0{,}5` et :math:`n = 12`, à 95 %,
    l'intervalle vaut environ :math:`[-0{,}104,\ 0{,}834]`.

    Args:
        correlation: la corrélation estimée.
        n: le nombre de paires.
        confidence: le niveau de confiance, entre zéro et un exclus.

    Returns:
        Les bornes basse et haute ; NaN toutes deux sous quatre paires ou pour
        une corrélation non finie.
    """
    if n < FISHER_MIN_YEARS or not np.isfinite(correlation):
        return (float("nan"), float("nan"))
    r = float(np.clip(correlation, -FISHER_CLIP, FISHER_CLIP))
    z = float(np.arctanh(r))
    q = float(stats.norm.ppf(0.5 + confidence / 2.0))
    half_width = q / math.sqrt(n - 3)
    return (float(np.tanh(z - half_width)), float(np.tanh(z + half_width)))


def annual_reading(n_years: int, corr_lo: float, corr_hi: float, *, min_years: int = MIN_ANNUAL_YEARS) -> str:
    """Rend la lecture en mots d'une corrélation annuelle et de son intervalle.

    Les seuils sont des préceptes du laboratoire. Une corrélation n'est
    « établie » que si son intervalle exclut zéro, et rien ne se dit sous le
    nombre minimal d'années.
    """
    if n_years < min_years:
        return f"trop peu d'années communes ({n_years})"
    if np.isnan(corr_lo) or np.isnan(corr_hi):
        return "non mesurable"
    if corr_lo > 0.0:
        return "co-mouvement établi"
    if corr_hi < 0.0:
        return "mouvements opposés"
    return "aucun co-mouvement établi"


@dataclass(frozen=True)
class AnnualComparison:
    """La comparaison d'une stratégie à un fonds fermé, sur leurs années communes.

    Tous les chiffres sont en fraction et portent sur les années COMMUNES,
    écrites dans l'objet. La stratégie est nette de coûts de transaction mais
    brute de frais de gestion ; le fonds est net de tout.
    """

    strategy: str
    fund: str
    n_years: int
    first_year: int
    last_year: int
    correlation: float
    corr_lo: float
    corr_hi: float
    mean_strategy: float
    mean_fund: float
    vol_strategy: float
    vol_fund: float
    worst_strategy: float
    worst_fund: float
    hit_rate: float
    both_negative: int
    reading: str

    def as_row(self) -> dict[str, Any]:
        """Rend la comparaison en une ligne de tableau."""
        return {
            "strategy": self.strategy,
            "fund": self.fund,
            "n_years": self.n_years,
            "first_year": self.first_year,
            "last_year": self.last_year,
            "correlation": self.correlation,
            "corr_lo": self.corr_lo,
            "corr_hi": self.corr_hi,
            "mean_strategy": self.mean_strategy,
            "mean_fund": self.mean_fund,
            "vol_strategy": self.vol_strategy,
            "vol_fund": self.vol_fund,
            "worst_strategy": self.worst_strategy,
            "worst_fund": self.worst_fund,
            "hit_rate": self.hit_rate,
            "both_negative": self.both_negative,
            "reading": self.reading,
        }


def compare_annual(
    strategy: pd.Series,
    fund: pd.Series,
    *,
    strategy_name: str = "stratégie",
    fund_name: str = "fonds",
    min_years: int = MIN_ANNUAL_YEARS,
    confidence: float = DEFAULT_CONFIDENCE,
) -> AnnualComparison:
    """Compare deux séries de rendements annuels sur leurs années communes.

    Args:
        strategy: les rendements annuels de la stratégie, indexés par année.
        fund: les rendements annuels rapportés du fonds, indexés par année.
        strategy_name: le nom de la stratégie dans les tableaux.
        fund_name: le nom du fonds dans les tableaux.
        min_years: le nombre d'années communes sous lequel la corrélation
            n'est pas publiée.
        confidence: le niveau de l'intervalle de Fisher.

    Returns:
        La comparaison, avec sa lecture en mots.

    Raises:
        InsufficientDataError: aucune année commune.
    """
    common = pd.concat([strategy.rename("s"), fund.rename("f")], axis=1, join="inner").dropna()
    if common.empty:
        raise InsufficientDataError(f"aucune année commune entre {strategy_name} et {fund_name}.")
    s, f = common["s"].astype(float), common["f"].astype(float)
    n = len(common)
    if n >= min_years and n >= 2 and s.std(ddof=1) > 0.0 and f.std(ddof=1) > 0.0:
        corr = float(s.corr(f))
    else:
        corr = float("nan")
    lo, hi = fisher_interval(corr, n, confidence)
    return AnnualComparison(
        strategy=strategy_name,
        fund=fund_name,
        n_years=n,
        first_year=int(common.index.min()),
        last_year=int(common.index.max()),
        correlation=corr,
        corr_lo=lo,
        corr_hi=hi,
        mean_strategy=float(s.mean()),
        mean_fund=float(f.mean()),
        vol_strategy=float(s.std(ddof=1)) if n > 1 else float("nan"),
        vol_fund=float(f.std(ddof=1)) if n > 1 else float("nan"),
        worst_strategy=float(s.min()),
        worst_fund=float(f.min()),
        hit_rate=float((s > f).mean()),
        both_negative=int(((s < 0.0) & (f < 0.0)).sum()),
        reading=annual_reading(n, lo, hi, min_years=min_years),
    )


def annual_comparison_table(
    strategy: pd.Series,
    funds: pd.DataFrame,
    *,
    strategy_name: str = "stratégie",
    min_years: int = MIN_ANNUAL_YEARS,
) -> pd.DataFrame:
    """Compare une stratégie à chaque colonne d'un tableau de fonds, une ligne par fonds.

    Les fonds sans année commune sont écrits avec zéro année plutôt qu'omis,
    parce qu'une absence de comparaison est une information.
    """
    rows: list[dict[str, Any]] = []
    for name in funds.columns:
        try:
            rows.append(
                compare_annual(
                    strategy,
                    funds[name].dropna(),
                    strategy_name=strategy_name,
                    fund_name=str(name),
                    min_years=min_years,
                ).as_row()
            )
        except InsufficientDataError:
            rows.append(
                {
                    "strategy": strategy_name,
                    "fund": str(name),
                    "n_years": 0,
                    "reading": "aucune année commune",
                }
            )
    return pd.DataFrame(rows)


def scale_to_volatility(
    returns: pd.Series,
    target_volatility_annual: float,
    *,
    frequency: Frequency,
) -> pd.Series:
    r"""Met une série à une volatilité annualisée cible par un facteur constant, statut MODÉLISÉ.

    **Le problème.** Une stratégie à 5 % de volatilité et un fonds à 20 % ne
    se comparent pas en niveau de rendement : le fonds porte quatre fois le
    risque. Ramener les deux à la même volatilité rend les niveaux lisibles.

    **L'intuition.** Multiplier chaque rendement par le rapport de la cible à
    la volatilité réalisée revient à porter la stratégie avec une exposition
    constante. Le ratio de Sharpe est inchangé, le niveau est mis à l'échelle.

    **La formule.**

    .. math::

        \tilde r_t = r_t \, \frac{\sigma^{\ast}}{\hat\sigma}

    **Les variables.** :math:`\sigma^{\ast}` la cible annualisée,
    :math:`\hat\sigma` l'écart type annualisé de la série entière.

    **Les hypothèses.** L'exposition est constante et connue d'avance, ce qui
    est faux : la volatilité de la série entière n'est connue qu'à la fin.
    Le financement de l'exposition au-delà de un n'est pas facturé.

    **La provenance.** Usage courant des comparaisons de fonds à volatilité
    égale ; précepte.

    **Les limites.** C'est une mise à l'échelle avec le recul, pas une
    stratégie négociable. Le chiffre qui en sort est MODÉLISÉ, et il ne
    remplace jamais le chiffre à l'exposition réelle.

    **Les alternatives.** Un ciblage de volatilité en marche avant, que le
    moteur de backtest sait faire, et qui change la trajectoire.

    **Pourquoi cette méthode ici.** Pour lire côte à côte un rendement annuel
    de laboratoire et celui d'un fonds à levier, sans prétendre à plus.

    **Comment vérifier.** La série rendue a exactement la volatilité cible, et
    son ratio de Sharpe est celui de la série d'origine.

    Args:
        returns: la série de rendements simples.
        target_volatility_annual: la volatilité annualisée visée, en fraction.
        frequency: la fréquence de la série.

    Returns:
        La série mise à l'échelle.

    Raises:
        InsufficientDataError: la série n'a aucune dispersion.
    """
    sigma = float(returns.std(ddof=1)) * math.sqrt(frequency.periods_per_year)
    if not np.isfinite(sigma) or sigma <= 0.0:
        raise InsufficientDataError("la série n'a aucune dispersion, elle ne se met pas à l'échelle.")
    return returns * (float(target_volatility_annual) / sigma)

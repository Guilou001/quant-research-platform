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

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

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

"""Le momentum de série temporelle de Moskowitz, Ooi et Pedersen (2012), pour LEAN.

Cet algorithme est la réimplémentation indépendante exigée par l'ADR-008. Il
n'importe rien du laboratoire, et il refait les quatre équations de l'article
depuis leur énoncé : la volatilité ex ante à pondération exponentielle, centrée
sur soixante séances et annualisée par 261 ; le signe du rendement excédentaire
des douze derniers mois ; la position à 40 % de volatilité cible ; la moyenne
sur les instruments disponibles. Les rendements excédentaires retranchent le
taux sans risque de Kenneth French, lu dans deux fichiers CSV montés avec les
données.

Les ordres sont passés sur la barre du dernier jour de séance du mois, et LEAN
les remplit à l'ouverture de la barre suivante. L'export a écrit cette
ouverture comme la clôture de la veille, si bien que le prix d'exécution est la
clôture de la décision, la convention du moteur du laboratoire. La variable
d'environnement ``TSMOM_DELAY_DAYS`` retarde les ordres d'autant de séances.
"""

import math
import os
from collections import defaultdict
from datetime import date, datetime

import pandas as pd
from AlgorithmImports import (
    ConstantFeeModel,
    DataNormalizationMode,
    ImmediateFillModel,
    NullSlippageModel,
    QCAlgorithm,
    Resolution,
)

UNIVERSE = [
    "SPY", "QQQ", "IWM", "EFA", "EEM", "EWJ", "EWG", "EWU", "EWA", "EWC",
    "TLT", "IEF", "SHY", "LQD", "HYG", "TIP", "AGG",
    "GLD", "SLV", "USO", "DBC", "DBA",
    "FXE", "FXY", "FXB", "FXA", "FXF", "UUP",
]  # fmt: skip

LOOKBACK_MONTHS = 12
TARGET_VOLATILITY = 0.40
CENTER_OF_MASS_DAYS = 60.0
ANNUALIZATION_DAYS = 261.0
MIN_VOL_OBSERVATIONS = 252
MIN_TRADING_DAYS_PER_MONTH = 15
FIRST_TRADE_DATE = date(2007, 1, 1)
START = datetime(1993, 1, 4)
END = datetime(2026, 6, 30)
INITIAL_CASH = 100_000_000.0
DATA_FOLDER = "/Data"


class TsmomControl(QCAlgorithm):
    """L'algorithme de contrôle, écrit sans regarder le code du laboratoire."""

    def Initialize(self) -> None:
        self.SetStartDate(START.year, START.month, START.day)
        self.SetEndDate(END.year, END.month, END.day)
        self.SetCash(INITIAL_CASH)
        self.Settings.FreePortfolioValuePercentage = 0.0
        self.Settings.MinimumOrderMarginPortfolioPercentage = 0.0
        self.delay_days = int(os.environ.get("TSMOM_DELAY_DAYS", "0"))
        self.decay = CENTER_OF_MASS_DAYS / (CENTER_OF_MASS_DAYS + 1.0)

        self.SetSecurityInitializer(self._prepare_security)
        self.symbols = {}
        for ticker in UNIVERSE:
            equity = self.AddEquity(ticker, Resolution.Daily, dataNormalizationMode=DataNormalizationMode.Raw)
            self.symbols[ticker] = equity.Symbol

        rf_daily = pd.read_csv(f"{DATA_FOLDER}/custom/rf_daily.csv", parse_dates=["date"])
        rf_monthly = pd.read_csv(f"{DATA_FOLDER}/custom/rf_monthly.csv", parse_dates=["date"])
        self.rf_daily = {d.date(): float(v) for d, v in zip(rf_daily["date"], rf_daily["rf"], strict=True)}
        self.rf_monthly = {
            (d.year, d.month): float(v) for d, v in zip(rf_monthly["date"], rf_monthly["rf"], strict=True)
        }

        # Un historique par instrument : clôtures datées, rendements excédentaires
        # quotidiens datés, rendements bruts par mois civil.
        self.last_close = {}
        self.last_close_date = {}
        self.daily_excess = defaultdict(list)
        self.monthly_gross = defaultdict(lambda: defaultdict(list))
        self.pending_orders = None
        self.pending_countdown = 0
        self.decisions = 0

    def _prepare_security(self, security) -> None:
        security.SetLeverage(100.0)
        security.SetFeeModel(ConstantFeeModel(0.0))
        security.SetSlippageModel(NullSlippageModel())
        security.SetFillModel(ImmediateFillModel())

    # ------------------------------------------------------------------ #
    # L'arrivée des barres
    # ------------------------------------------------------------------ #
    def OnData(self, data) -> None:
        bar_date = None
        for ticker, symbol in self.symbols.items():
            if symbol not in data.Bars:
                continue
            bar = data.Bars[symbol]
            bar_date = bar.EndTime.date() if bar_date is None else bar_date
            close = float(bar.Close)
            previous = self.last_close.get(ticker)
            if previous is not None:
                gross = close / previous - 1.0
                rf = self.rf_daily.get(self._bar_day(bar), 0.0)
                self.daily_excess[ticker].append(gross - rf)
                month_key = (self._bar_day(bar).year, self._bar_day(bar).month)
                self.monthly_gross[ticker][month_key].append(gross)
            self.last_close[ticker] = close
            self.last_close_date[ticker] = self._bar_day(bar)

        if bar_date is None:
            return
        current_day = self._first_bar_day(data)

        if self.pending_orders is not None:
            self.pending_countdown -= 1
            if self.pending_countdown <= 0:
                self._execute(self.pending_orders)
                self.pending_orders = None

        self.Log(f"PV,{current_day.isoformat()},{float(self.Portfolio.TotalPortfolioValue)!r}")

        if current_day < FIRST_TRADE_DATE or not self._is_month_end(current_day):
            return
        weights = self._decide(current_day)
        self.decisions += 1
        if self.delay_days <= 0:
            self._execute(weights)
        else:
            self.pending_orders = weights
            self.pending_countdown = self.delay_days

    @staticmethod
    def _bar_day(bar) -> date:
        # Une barre quotidienne finit à minuit ou à seize heures selon le
        # réglage de LEAN ; dans les deux cas, EndTime moins une minute tombe
        # le jour de séance de la barre.
        return (bar.EndTime - pd.Timedelta(minutes=1)).date()

    def _first_bar_day(self, data) -> date:
        for symbol in self.symbols.values():
            if symbol in data.Bars:
                return self._bar_day(data.Bars[symbol])
        raise RuntimeError("aucune barre dans la tranche")

    def _is_month_end(self, day: date) -> bool:
        hours = self.Securities[self.symbols["SPY"]].Exchange.Hours
        next_day = hours.GetNextTradingDay(datetime(day.year, day.month, day.day))
        return next_day.month != day.month

    # ------------------------------------------------------------------ #
    # Les quatre équations
    # ------------------------------------------------------------------ #
    def _volatility(self, ticker: str) -> float | None:
        """La volatilité ex ante annualisée, sans le rendement du jour de décision."""
        history = self.daily_excess[ticker][:-1]
        if len(history) < MIN_VOL_OBSERVATIONS:
            return None
        delta = self.decay
        total_weight = 0.0
        mean = 0.0
        square = 0.0
        weight = 1.0
        for value in reversed(history):
            total_weight += weight
            mean += weight * value
            square += weight * value * value
            weight *= delta
            if weight < 1e-18:
                break
        mean /= total_weight
        variance = square / total_weight - mean * mean
        if variance <= 0.0:
            return None
        return math.sqrt(ANNUALIZATION_DAYS * variance)

    def _monthly_excess(self, ticker: str, year: int, month: int) -> float | None:
        days = self.monthly_gross[ticker].get((year, month))
        if days is None or len(days) < MIN_TRADING_DAYS_PER_MONTH:
            return None
        gross = 1.0
        for r in days:
            gross *= 1.0 + r
        rf = self.rf_monthly.get((year, month))
        if rf is None:
            return None
        return gross - 1.0 - rf

    def _signal(self, ticker: str, day: date) -> float | None:
        """Le signe du rendement excédentaire composé des douze derniers mois."""
        year, month = day.year, day.month
        compounded = 1.0
        for _ in range(LOOKBACK_MONTHS):
            excess = self._monthly_excess(ticker, year, month)
            if excess is None:
                return None
            compounded *= 1.0 + excess
            month -= 1
            if month == 0:
                month = 12
                year -= 1
        value = compounded - 1.0
        if value > 0.0:
            return 1.0
        if value < 0.0:
            return -1.0
        return 0.0

    def _decide(self, day: date) -> dict:
        positions = {}
        for ticker in UNIVERSE:
            if self.last_close_date.get(ticker) != day:
                continue
            sigma = self._volatility(ticker)
            sign = self._signal(ticker, day)
            if sigma is None or sign is None:
                continue
            positions[ticker] = sign * TARGET_VOLATILITY / sigma
        count = len(positions)
        weights = {t: p / count for t, p in positions.items()} if count else {}
        detail = ";".join(f"{t}:{w!r}" for t, w in sorted(weights.items()))
        self.Log(f"DECISION,{day.isoformat()},{count},{detail}")
        return weights

    def _execute(self, weights: dict) -> None:
        for ticker, symbol in self.symbols.items():
            target = weights.get(ticker, 0.0)
            if target == 0.0:
                if self.Portfolio[symbol].Invested:
                    self.Liquidate(symbol)
                continue
            self.SetHoldings(symbol, target)

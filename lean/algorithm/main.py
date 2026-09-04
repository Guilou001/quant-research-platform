"""Le momentum de série temporelle de Moskowitz, Ooi et Pedersen (2012), pour LEAN.

Cet algorithme est la réimplémentation indépendante exigée par l'ADR-008. Il
n'importe rien du laboratoire, et il refait les quatre équations de l'article
depuis leur énoncé : la volatilité ex ante à pondération exponentielle, le
signe du rendement excédentaire des douze derniers mois, la position à
volatilité cible, la moyenne sur les instruments disponibles. Les rendements
excédentaires retranchent le taux sans risque de Kenneth French, lu dans deux
fichiers CSV montés avec les données. L'univers, les dates et les paramètres
de la stratégie sont lus dans ``custom/params.json``, écrit par l'export du
laboratoire depuis la configuration de l'étude 001 : rien n'est recopié ici.

Les ordres sont passés sur la barre du dernier jour de séance du mois, et LEAN
les remplit à l'ouverture de la barre suivante. Selon le jeu de données monté,
cette ouverture est la clôture de la veille, la convention du moteur du
laboratoire, ou l'ouverture réelle du lendemain. La variable d'environnement
``TSMOM_DELAY_DAYS`` retarde les ordres d'autant de séances.
"""

import json
import math
import os
from collections import defaultdict
from datetime import date, datetime, timedelta

from AlgorithmImports import (
    ConstantFeeModel,
    DataNormalizationMode,
    Globals,
    ImmediateFillModel,
    NullSlippageModel,
    QCAlgorithm,
    Resolution,
)

INITIAL_CASH = 100_000_000.0
ONE_MINUTE = timedelta(minutes=1)
WEIGHT_FLOOR = 1e-18


def _data_folder() -> str:
    """Le dossier de données que LEAN a reçu, ou le point de montage par défaut."""
    try:
        dossier = str(Globals.DataFolder)
    except Exception:
        dossier = ""
    return dossier.rstrip("/") if dossier else "/Data"


def _read_rates(path: str) -> list[tuple[date, float]]:
    """Lit un CSV date,rf et rend la liste triée des couples."""
    couples = []
    with open(path) as fichier:
        next(fichier)
        for ligne in fichier:
            jour, valeur = ligne.strip().split(",")
            couples.append((date.fromisoformat(jour), float(valeur)))
    couples.sort()
    return couples


class TsmomControl(QCAlgorithm):
    """L'algorithme de contrôle, écrit sans regarder le code du laboratoire."""

    def Initialize(self) -> None:
        dossier = _data_folder()
        with open(f"{dossier}/custom/params.json") as fichier:
            params = json.load(fichier)
        self.tickers = list(params["universe"])
        self.first_trade_date = date.fromisoformat(params["first_trade_date"])
        self.lookback_months = int(params["lookback_months"])
        self.target_volatility = float(params["target_volatility"])
        self.annualization_days = float(params["volatility_annualization_days"])
        self.min_vol_observations = int(params["volatility_min_periods_days"])
        self.min_trading_days = int(params["min_trading_days_per_month"])
        centre = float(params["volatility_center_of_mass_days"])
        self.decay = centre / (centre + 1.0)
        debut = date.fromisoformat(params["start"])
        fin = date.fromisoformat(params["end"])

        self.SetStartDate(debut.year, debut.month, debut.day)
        self.SetEndDate(fin.year, fin.month, fin.day)
        self.SetCash(INITIAL_CASH)
        self.Settings.FreePortfolioValuePercentage = 0.0
        self.Settings.MinimumOrderMarginPortfolioPercentage = 0.0
        self.delay_days = int(os.environ.get("TSMOM_DELAY_DAYS", "0"))

        self.SetSecurityInitializer(self._prepare_security)
        self.symbols = {}
        for ticker in self.tickers:
            equity = self.AddEquity(ticker, Resolution.Daily, dataNormalizationMode=DataNormalizationMode.Raw)
            self.symbols[ticker] = equity.Symbol

        # Les deux taux : quotidien reporté vers l'avant quand une séance manque,
        # mensuel reporté de même, comme le laboratoire le fait.
        self.rf_daily = _read_rates(f"{dossier}/custom/rf_daily.csv")
        self.rf_daily_index = 0
        self.rf_daily_last = 0.0
        self.rf_monthly = {}
        for jour, valeur in _read_rates(f"{dossier}/custom/rf_monthly.csv"):
            self.rf_monthly[(jour.year, jour.month)] = valeur
        self.rf_monthly_last_key = None

        self.last_close = {}
        self.last_close_date = {}
        self.daily_excess = defaultdict(list)
        self.monthly_gross = defaultdict(lambda: defaultdict(list))
        self.pending_orders = None
        self.pending_countdown = 0

    def _prepare_security(self, security) -> None:
        security.SetLeverage(100.0)
        security.SetFeeModel(ConstantFeeModel(0.0))
        security.SetSlippageModel(NullSlippageModel())
        security.SetFillModel(ImmediateFillModel())

    # ------------------------------------------------------------------ #
    # Les taux
    # ------------------------------------------------------------------ #
    def _daily_rate(self, day: date) -> float:
        """Le taux quotidien du jour, ou le dernier connu avant lui."""
        while self.rf_daily_index < len(self.rf_daily) and self.rf_daily[self.rf_daily_index][0] <= day:
            self.rf_daily_last = self.rf_daily[self.rf_daily_index][1]
            self.rf_daily_index += 1
        return self.rf_daily_last

    def _monthly_rate(self, year: int, month: int):
        """Le taux mensuel du mois, ou le dernier connu avant lui, ou None s'il n'y en a aucun."""
        valeur = self.rf_monthly.get((year, month))
        if valeur is not None:
            return valeur
        anterieurs = [cle for cle in self.rf_monthly if cle <= (year, month)]
        if not anterieurs:
            return None
        cle = max(anterieurs)
        if cle != self.rf_monthly_last_key:
            self.rf_monthly_last_key = cle
            self.Log(f"RF_MONTHLY_FFILL,{year}-{month:02d},{cle[0]}-{cle[1]:02d}")
        return self.rf_monthly[cle]

    # ------------------------------------------------------------------ #
    # L'arrivée des barres
    # ------------------------------------------------------------------ #
    def OnData(self, data) -> None:
        current_day = None
        for ticker, symbol in self.symbols.items():
            if symbol not in data.Bars:
                continue
            bar = data.Bars[symbol]
            # Une barre quotidienne finit à minuit ou à seize heures selon le
            # réglage de LEAN ; dans les deux cas, EndTime moins une minute tombe
            # le jour de séance de la barre.
            day = (bar.EndTime - ONE_MINUTE).date()
            current_day = current_day or day
            close = float(bar.Close)
            previous = self.last_close.get(ticker)
            if previous is not None:
                gross = close / previous - 1.0
                self.daily_excess[ticker].append(gross - self._daily_rate(day))
                self.monthly_gross[ticker][(day.year, day.month)].append(gross)
            self.last_close[ticker] = close
            self.last_close_date[ticker] = day
        if current_day is None:
            return

        if self.pending_orders is not None:
            self.pending_countdown -= 1
            if self.pending_countdown <= 0:
                self._execute(self.pending_orders)
                self.pending_orders = None

        self.Log(f"PV,{current_day.isoformat()},{float(self.Portfolio.TotalPortfolioValue)!r}")

        if current_day < self.first_trade_date or not self._is_month_end(current_day):
            return
        weights = self._decide(current_day)
        if self.delay_days <= 0:
            self._execute(weights)
        else:
            self.pending_orders = weights
            self.pending_countdown = self.delay_days

    def _is_month_end(self, day: date) -> bool:
        hours = self.Securities[self.symbols[self.tickers[0]]].Exchange.Hours
        next_day = hours.GetNextTradingDay(datetime(day.year, day.month, day.day))
        return next_day.month != day.month

    # ------------------------------------------------------------------ #
    # Les quatre équations
    # ------------------------------------------------------------------ #
    def _volatility(self, ticker: str):
        """La volatilité ex ante annualisée, sans le rendement du jour de décision."""
        history = self.daily_excess[ticker]
        n = len(history) - 1
        if n < self.min_vol_observations:
            return None
        delta = self.decay
        total_weight = 0.0
        mean = 0.0
        square = 0.0
        weight = 1.0
        for i in range(n - 1, -1, -1):
            value = history[i]
            total_weight += weight
            mean += weight * value
            square += weight * value * value
            weight *= delta
            if weight < WEIGHT_FLOOR:
                break
        mean /= total_weight
        variance = square / total_weight - mean * mean
        if variance <= 0.0:
            return None
        return math.sqrt(self.annualization_days * variance)

    def _monthly_excess(self, ticker: str, year: int, month: int):
        days = self.monthly_gross[ticker].get((year, month))
        if days is None or len(days) < self.min_trading_days:
            return None
        gross = 1.0
        for r in days:
            gross *= 1.0 + r
        rf = self._monthly_rate(year, month)
        if rf is None:
            return None
        return gross - 1.0 - rf

    def _signal(self, ticker: str, day: date):
        """Le signe du rendement excédentaire composé des douze derniers mois."""
        year, month = day.year, day.month
        compounded = 1.0
        for _ in range(self.lookback_months):
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
        for ticker in self.tickers:
            if self.last_close_date.get(ticker) != day:
                continue
            sigma = self._volatility(ticker)
            sign = self._signal(ticker, day)
            if sigma is None or sign is None:
                continue
            positions[ticker] = sign * self.target_volatility / sigma
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

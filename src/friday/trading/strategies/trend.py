"""Stratégies de tendance : croisement de moyennes, cassure de range (Donchian). Toutes deux
dans le sens de l'EMA journalière ; stop d'au moins N ATR, objectif en R (règles du plan)."""

from friday.trading.backtest.series import ema_series
from friday.trading.strategies.base import Entry, State, Strategy

FAST, SLOW = 20, 50  # EMA 1 h du croisement
RANGE = 20  # bougies 1 h du range à casser


class CrossoverStrategy(Strategy):
    name = "croisement"
    label = "le croisement de moyennes"
    summary = (f"l'EMA{FAST} 1 h croise l'EMA{SLOW} 1 h, dans le sens de la tendance "
               "journalière")  # fmt: skip

    def add_series(self, state: State) -> None:
        state.extra["fast"] = ema_series(state.closes, FAST)
        state.extra["slow"] = ema_series(state.closes, SLOW)

    def entry(self, state: State, i: int, day: int) -> Entry | None:
        fast, slow = state.extra["fast"], state.extra["slow"]
        if i == 0 or None in (fast[i], slow[i], fast[i - 1], slow[i - 1]):
            return None
        above_now, above_before = fast[i] > slow[i], fast[i - 1] > slow[i - 1]
        if above_now == above_before:
            return None  # pas de croisement sur cette bougie
        side = "achat" if above_now else "vente"
        return self.by_risk(state, i, side) if side in self.sides(state, i, day) else None


class BreakoutStrategy(Strategy):
    name = "cassure"
    label = "la cassure de range"
    summary = (f"clôture au-delà du plus haut ou du plus bas des {RANGE} dernières heures, dans "
               "le sens de la tendance journalière")  # fmt: skip

    def entry(self, state: State, i: int, day: int) -> Entry | None:
        if i < RANGE:
            return None
        before = state.hourly[i - RANGE : i]
        close = state.closes[i]
        if close > max(c.high for c in before):
            side = "achat"
        elif close < min(c.low for c in before):
            side = "vente"
        else:
            return None
        return self.by_risk(state, i, side) if side in self.sides(state, i, day) else None

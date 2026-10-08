"""« Le repli sur moyenne (modèle) » : repli vers l'EMA 1 h, RSI dans la zone et qui repart,
dans le sens de l'EMA journalière ; stop sous le dernier creux (au moins N ATR). C'était le
plan de départ ; ses chiffres se règlent dans Réglages → Trading (modèle « repli »). Le plan
écrit de l'utilisateur, lui, est une autre stratégie (custom.py)."""

from friday.trading.backtest.series import ema_series
from friday.trading.plan_rules import PlanRules
from friday.trading.strategies.base import Entry, State, Strategy

SWING = 10  # « dernier creux / sommet » : extrême des 10 dernières bougies 1 h


def setup_ok(side: str, i: int, close: float, pull, rsi, width: float, rules: PlanRules) -> bool:
    if pull is not None and (pull[i] is None or abs(close - pull[i]) > rules.pullback_atr * width):
        return False
    buy = side == "achat"
    low, high = (rules.rsi_low, rules.rsi_high) if buy else (100 - rules.rsi_high,
                                                             100 - rules.rsi_low)  # fmt: skip
    if not low <= rsi[i] <= high:
        return False
    return not rules.rsi_turning or (rsi[i] > rsi[i - 1] if buy else rsi[i] < rsi[i - 1])


class PlanStrategy(Strategy):
    name = "repli"
    label = "le repli sur moyenne (modèle)"
    summary = "repli vers l'EMA 1 h avec un RSI qui repart, dans le sens de la tendance"

    def add_series(self, state: State) -> None:
        period = state.rules.pullback_ema
        state.extra["pull"] = ema_series(state.closes, period) if period else None

    def entry(self, state: State, i: int, day: int) -> Entry | None:
        rsi, width = state.rsi, state.atr[i]
        if width is None or rsi[i] is None or i == 0 or rsi[i - 1] is None:
            return None
        for side in self.sides(state, i, day):
            if setup_ok(side, i, state.closes[i], state.extra["pull"], rsi, width, state.rules):
                recent = state.hourly[max(0, i - SWING + 1) : i + 1]
                swing = min(c.low for c in recent) if side == "achat" else max(
                    c.high for c in recent)  # fmt: skip
                return self.by_risk(state, i, side, stop=swing)
        return None

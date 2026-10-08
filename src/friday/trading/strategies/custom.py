"""« Ton plan écrit » : la stratégie qui exécute les règles traduites de ton plan (spec.py).
Chaque condition est évaluée à la clôture de la bougie 1 h `i`, sur des séries calculées une
fois ; « plus haut / plus bas des bougies précédentes » exclut la bougie `i` (pas de futur)."""

from datetime import timedelta

from friday.trading.backtest.series import atr_series, ema_series, rsi_series
from friday.trading.calendar import PARIS
from friday.trading.strategies.base import Entry, State, Strategy
from friday.trading.strategies.spec import describe


def _sma(values: list[float], period: int) -> list:
    out, total = [None] * len(values), 0.0
    for i, v in enumerate(values):
        total += v - (values[i - period] if i >= period else 0.0)
        if i >= period - 1:
            out[i] = total / period
    return out


def _bands(values: list[float], period: int, k: float, sign: int) -> list:
    mean, out = _sma(values, period), [None] * len(values)
    for i in range(period - 1, len(values)):
        window = values[i - period + 1 : i + 1]
        std = (sum((x - mean[i]) ** 2 for x in window) / period) ** 0.5
        out[i] = mean[i] + sign * k * std
    return out


def _extreme(values: list[float], period: int, pick) -> list:
    """Extrême des `period` bougies AVANT i (exclue)."""
    return [pick(values[i - period : i]) if i >= period else None for i in range(len(values))]


class CustomStrategy(Strategy):
    name = "mon_plan"
    label = "ton plan écrit"

    def __init__(self, spec: dict) -> None:
        self.spec = spec
        self.summary = spec.get("resume") or "; ".join(describe(spec)[:2])
        self.trend_filter = spec.get("tendance") is not None

    def add_series(self, state: State) -> None:
        if self.trend_filter:
            period = self.spec["tendance"]["ema"]
            state.trend = ema_series([d.close for d in state.daily], period)
        else:
            state.trend = None

    def series(self, state: State, o: dict) -> list:
        key = (o["indicateur"], o.get("periode"), o.get("ecarts"))
        if key not in state.extra:
            h, closes, p = state.hourly, state.closes, o.get("periode")
            make = {
                "cours": lambda: closes, "ouverture": lambda: [c.open for c in h],
                "haut": lambda: [c.high for c in h], "bas": lambda: [c.low for c in h],
                "ema": lambda: ema_series(closes, p), "sma": lambda: _sma(closes, p),
                "rsi": lambda: rsi_series(closes, p), "atr": lambda: atr_series(h, p),
                "bollinger_haute": lambda: _bands(closes, p, o.get("ecarts", 2), 1),
                "bollinger_basse": lambda: _bands(closes, p, o.get("ecarts", 2), -1),
                "plus_haut": lambda: _extreme([c.high for c in h], p, max),
                "plus_bas": lambda: _extreme([c.low for c in h], p, min),
            }  # fmt: skip
            state.extra[key] = make[o["indicateur"]]()
        return state.extra[key]

    def value(self, state: State, o: dict, i: int) -> float | None:
        if "valeur" in o:
            return o["valeur"]
        j = i - o.get("decalage", 0)
        return self.series(state, o)[j] if j >= 0 else None

    def holds(self, state: State, c: dict, i: int) -> bool:
        op, left = c["op"], self.value(state, c["gauche"], i)
        if op in ("monte", "baisse"):
            before = self.value(state, c["gauche"], i - 1) if i else None
            return None not in (left, before) and (
                left > before if op == "monte" else left < before
            )
        right = self.value(state, c["droite"], i)
        if left is None or right is None:
            return False
        if op in ("croise_au_dessus", "croise_en_dessous"):
            if i == 0:
                return False
            l0, r0 = self.value(state, c["gauche"], i - 1), self.value(state, c["droite"], i - 1)
            if l0 is None or r0 is None:
                return False
            return l0 <= r0 and left > right if op == "croise_au_dessus" else (
                l0 >= r0 and left < right)  # fmt: skip
        if op == "proche":
            width = state.atr[i]
            return width is not None and abs(left - right) <= c.get("k", 1.0) * width
        return {">": left > right, "<": left < right, ">=": left >= right,
                "<=": left <= right}[op]  # fmt: skip

    def entry(self, state: State, i: int, day: int) -> Entry | None:
        hours = self.spec.get("heures")
        if hours:
            closing = (state.hourly[i].time + timedelta(hours=1)).astimezone(PARIS).hour
            if not hours[0] <= closing <= hours[1]:  # « entre 9 h et 17 h » : 17 h compris
                return None
        for side in self.sides(state, i, day):
            conditions = self.spec[side]
            if conditions and all(self.holds(state, c, i) for c in conditions):
                return self._trade(state, i, side)
        return None

    def _trade(self, state: State, i: int, side: str) -> Entry | None:
        close, sign, width = state.closes[i], 1 if side == "achat" else -1, state.atr[i]
        stop_rule, target_rule = self.spec["stop"], self.spec["objectif"]
        if not width:
            return None
        if stop_rule["type"] == "creux":
            recent = state.hourly[max(0, i - stop_rule["bougies"] + 1) : i + 1]
            stop = min(c.low for c in recent) if sign > 0 else max(c.high for c in recent)
        else:
            stop = close - sign * stop_rule["multiple"] * width
        entry = self.by_risk(state, i, side, stop=stop)  # au moins le stop minimal du risque
        if entry is None:
            return None
        if target_rule["type"] == "r":
            entry.target = close + sign * target_rule["valeur"] * abs(close - entry.stop)
            return entry
        level = self.value(state, target_rule["indicateur"], i)
        if level is None or (level - close) * sign <= 0:
            return None  # objectif déjà dépassé : pas de trade
        entry.target = level
        return entry

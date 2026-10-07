"""Backtest du plan : les règles de la check-list (plan_rules.py) rejouées bougie 1 h après
bougie 1 h sur l'historique, sans rien voir du futur.

- Signal à la CLÔTURE d'une bougie 1 h : tendance par l'EMA journalière (de la dernière
  journée terminée), cours près de l'EMA 1 h, RSI 14 dans la zone (et qui repart) ; entrée au
  cours de clôture.
- Stop « sous le dernier creux » (extrême des SWING dernières bougies), à au moins
  `stop_atr` ATR ; objectif à `min_rr` R (2 R si la règle est désactivée).
- Sortie : stop ou objectif touché ; les deux dans la même bougie → le stop (prudent) ; une
  ouverture au-delà (week-end, annonce) sort au cours d'ouverture, pire que le stop.
- Un trade à la fois ; le spread est retiré de chaque trade (en R).
- Non rejouables : les annonces (pas d'historique du calendrier) et le risque en % (tout est
  en R).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from friday.trading.backtest.series import atr_series, ema_series, rsi_series
from friday.trading.market import Candle
from friday.trading.plan_rules import PlanRules

SWING = 10  # « dernier creux / sommet » : extrême des 10 dernières bougies 1 h


@dataclass
class Trade:
    opened: datetime
    direction: str  # « achat » ou « vente »
    entry: float
    stop: float
    target: float
    closed: datetime | None = None
    result_r: float | None = None


def simulate(hourly: list[Candle], daily: list[Candle], rules: PlanRules,
             spread: float = 0.0) -> list[Trade]:  # fmt: skip
    """Les trades fermés que le plan aurait pris (`spread` en unités de prix)."""
    closes = [c.close for c in hourly]
    trend = ema_series([d.close for d in daily], rules.trend_ema) if rules.trend_ema else None
    pull = ema_series(closes, rules.pullback_ema) if rules.pullback_ema else None
    rsi, atr = rsi_series(closes), atr_series(hourly)
    trades: list[Trade] = []
    current: Trade | None = None
    day = -1  # dernière journée terminée
    for i, bar in enumerate(hourly):
        while day + 1 < len(daily) and daily[day + 1].time + timedelta(days=1) <= bar.time:
            day += 1
        if current is not None:
            if _exit(current, bar, spread):
                trades.append(current)
                current = None
            continue
        if atr[i] is None or rsi[i] is None or i == 0 or rsi[i - 1] is None:
            continue
        sides = ("achat", "vente")
        if trend is not None:
            line = trend[day] if day >= 0 else None
            if line is None:
                continue
            sides = ("achat",) if bar.close > line else ("vente",)
        for side in sides:
            if _setup(side, i, bar.close, pull, rsi, atr[i], rules):
                current = _open(side, i, hourly, atr[i], rules)
                break
    return trades


def _setup(side: str, i: int, close: float, pull, rsi, width: float, rules: PlanRules) -> bool:
    if pull is not None and (pull[i] is None or abs(close - pull[i]) > rules.pullback_atr * width):
        return False
    buy = side == "achat"
    low, high = (rules.rsi_low, rules.rsi_high) if buy else (100 - rules.rsi_high,
                                                             100 - rules.rsi_low)  # fmt: skip
    if not low <= rsi[i] <= high:
        return False
    return not rules.rsi_turning or (rsi[i] > rsi[i - 1] if buy else rsi[i] < rsi[i - 1])


def _open(side: str, i: int, hourly: list[Candle], width: float, rules: PlanRules) -> Trade:
    bar, recent = hourly[i], hourly[max(0, i - SWING + 1) : i + 1]
    floor = rules.stop_atr * width
    if side == "achat":
        stop = min(min(c.low for c in recent), bar.close - floor)
    else:
        stop = max(max(c.high for c in recent), bar.close + floor)
    if stop == bar.close:  # bougie sans amplitude et règle du stop désactivée
        stop += -width if side == "achat" else width
    risk = abs(bar.close - stop)
    reward = (rules.min_rr or 2.0) * risk
    target = bar.close + reward if side == "achat" else bar.close - reward
    return Trade(bar.time, side, bar.close, stop, target)


def _exit(trade: Trade, bar: Candle, spread: float) -> bool:
    """Le trade se termine-t-il dans cette bougie ? (résultat en R, spread déduit)"""
    buy = trade.direction == "achat"
    sign = 1 if buy else -1
    risk = abs(trade.entry - trade.stop)
    if (bar.open - trade.stop) * sign <= 0 or (bar.open - trade.target) * sign >= 0:
        price = bar.open  # ouverture au-delà du stop ou de l'objectif (trou de cotation)
    elif (bar.low if buy else bar.high) * sign <= trade.stop * sign:
        price = trade.stop
    elif (bar.high if buy else bar.low) * sign >= trade.target * sign:
        price = trade.target
    else:
        return False
    trade.closed = bar.time
    trade.result_r = (price - trade.entry) * sign / risk - spread / risk
    return True

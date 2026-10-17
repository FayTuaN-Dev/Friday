"""Backtest : une stratégie (strategies/, par défaut le plan) rejouée bougie 1 h après
bougie 1 h sur l'historique, sans rien voir du futur.

- La stratégie décide à la CLÔTURE d'une bougie 1 h (tendance : dernière journée terminée) ;
  entrée au cours de clôture, avec son stop (au moins `stop_atr` ATR) et son objectif.
- Sortie : stop ou objectif touché ; les deux dans la même bougie → le stop (prudent) ; une
  ouverture au-delà (week-end, annonce) sort au cours d'ouverture, pire que le stop.
- Sortie suiveuse (Turtles) : à l'achat, le plus bas des N bougies précédentes, qui monte avec
  le prix et ne descend jamais sous le stop ; sans objectif, c'est elle qui fait sortir.
- Un trade à la fois ; le spread est retiré de chaque trade (en R).
- Non rejouables : les annonces (pas d'historique du calendrier) et le risque en % (tout est
  en R).
"""

from dataclasses import dataclass
from datetime import datetime

from friday.trading.backtest.series import extreme_series
from friday.trading.market import Candle
from friday.trading.plan_rules import PlanRules
from friday.trading.strategies import Strategy, finished_day
from friday.trading.strategies.plan import PlanStrategy


@dataclass
class Trade:
    opened: datetime
    direction: str  # « achat » ou « vente »
    entry: float
    stop: float  # le stop initial : il fixe le risque (1 R)
    target: float | None  # None : pas d'objectif (sortie suiveuse)
    trail: int | None = None  # sortie suiveuse : N bougies
    closed: datetime | None = None
    result_r: float | None = None


def simulate(hourly: list[Candle], daily: list[Candle], rules: PlanRules, spread: float = 0.0,
             strategy: Strategy | None = None) -> list[Trade]:  # fmt: skip
    """Les trades fermés que la stratégie (par défaut : le plan) aurait pris, `spread` en
    unités de prix. Un trade à la fois ; la stratégie ne voit que le passé."""
    strategy = strategy or PlanStrategy()
    state = strategy.prepare(hourly, daily, rules)
    trades: list[Trade] = []
    current: Trade | None = None
    channels: dict[tuple[int, bool], list] = {}  # (N, plus haut ?) → série, calculée une fois
    day = -1  # dernière journée terminée
    for i, bar in enumerate(hourly):
        day = finished_day(daily, bar.time, day)
        if current is not None:
            if _exit(current, bar, spread, _trail_level(current, hourly, i, channels)):
                trades.append(current)
                current = None
            continue
        entry = strategy.entry(state, i, day)
        if entry is not None:
            current = Trade(bar.time, entry.side, bar.close, entry.stop, entry.target,
                            entry.trail)  # fmt: skip
    return trades


def _trail_level(trade: Trade, hourly: list[Candle], i: int, channels: dict) -> float | None:
    """Où la sortie suiveuse attend le prix pendant la bougie `i` (bougies d'avant seulement)."""
    if not trade.trail:
        return None
    key = (trade.trail, trade.direction == "vente")  # en vente : le plus haut
    if key not in channels:
        values = [c.high for c in hourly] if key[1] else [c.low for c in hourly]
        channels[key] = extreme_series(values, trade.trail, highest=key[1])
    return channels[key][i]


def _exit(trade: Trade, bar: Candle, spread: float, trail: float | None = None) -> bool:
    """Le trade se termine-t-il dans cette bougie ? (résultat en R, spread déduit)"""
    buy = trade.direction == "achat"
    sign = 1 if buy else -1
    risk = abs(trade.entry - trade.stop)
    stop = trade.stop  # la sortie suiveuse remplace le stop dès qu'elle est plus près du prix
    if trail is not None and (trail - stop) * sign > 0:
        stop = trail
    target = trade.target
    if (bar.open - stop) * sign <= 0 or (target is not None and (bar.open - target) * sign >= 0):
        price = bar.open  # ouverture au-delà du stop ou de l'objectif (trou de cotation)
    elif (bar.low if buy else bar.high) * sign <= stop * sign:
        price = stop
    elif target is not None and (bar.high if buy else bar.low) * sign >= target * sign:
        price = target
    else:
        return False
    trade.closed = bar.time
    trade.result_r = (price - trade.entry) * sign / risk - spread / risk
    return True

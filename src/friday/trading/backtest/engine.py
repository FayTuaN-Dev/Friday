"""Backtest : une stratégie (strategies/, par défaut le plan) rejouée bougie 1 h après
bougie 1 h sur l'historique, sans rien voir du futur.

- La stratégie décide à la CLÔTURE d'une bougie 1 h (tendance : dernière journée terminée) ;
  entrée au cours de clôture, avec son stop (au moins `stop_atr` ATR) et son objectif.
- Sortie : stop ou objectif touché ; les deux dans la même bougie → le stop (prudent) ; une
  ouverture au-delà (week-end, annonce) sort au cours d'ouverture, pire que le stop.
- Un trade à la fois ; le spread est retiré de chaque trade (en R).
- Non rejouables : les annonces (pas d'historique du calendrier) et le risque en % (tout est
  en R).
"""

from dataclasses import dataclass
from datetime import datetime

from friday.trading.market import Candle
from friday.trading.plan_rules import PlanRules
from friday.trading.strategies import Strategy, finished_day
from friday.trading.strategies.plan import PlanStrategy


@dataclass
class Trade:
    opened: datetime
    direction: str  # « achat » ou « vente »
    entry: float
    stop: float
    target: float
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
    day = -1  # dernière journée terminée
    for i, bar in enumerate(hourly):
        day = finished_day(daily, bar.time, day)
        if current is not None:
            if _exit(current, bar, spread):
                trades.append(current)
                current = None
            continue
        entry = strategy.entry(state, i, day)
        if entry is not None:
            current = Trade(bar.time, entry.side, bar.close, entry.stop, entry.target)
    return trades


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

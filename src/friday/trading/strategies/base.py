"""Ce qu'est une stratégie pour Friday : une règle d'ENTRÉE sur la clôture d'une bougie 1 h,
avec son stop et son objectif. Tout le reste est commun et ne dépend pas d'elle : le moteur
de backtest (sorties, spread, un trade à la fois), la gestion du risque (stop d'au moins
N ATR, objectif en R : plan_rules.py), les alertes et la check-list.

Règle d'or : `entry(state, i, day)` ne regarde QUE les bougies jusqu'à `i` (incluse) et les
journées terminées jusqu'à `day` — jamais le futur (testé).
"""

from dataclasses import dataclass, field
from datetime import timedelta

from friday.trading.backtest.series import atr_series, ema_series, rsi_series
from friday.trading.market import Candle
from friday.trading.plan_rules import PlanRules


@dataclass
class Entry:
    side: str  # « achat » ou « vente »
    stop: float
    target: float


@dataclass
class State:
    """Les séries calculées une fois pour toutes (un seul passage), lues bougie par bougie."""

    hourly: list[Candle]
    daily: list[Candle]
    rules: PlanRules
    closes: list[float]
    atr: list
    rsi: list
    trend: list | None  # EMA journalière de tendance, ou None (règle désactivée)
    extra: dict = field(default_factory=dict)  # séries propres à une stratégie


def finished_day(daily: list[Candle], moment, start: int = -1) -> int:
    """Indice de la dernière journée terminée avant `moment` (-1 : aucune)."""
    day = start
    while day + 1 < len(daily) and daily[day + 1].time + timedelta(days=1) <= moment:
        day += 1
    return day


class Strategy:
    name = ""  # identifiant (fichier de choix, outils)
    label = ""  # pour parler : « la cassure de range »
    summary = ""  # en une phrase
    trend_filter = True  # ne trade que dans le sens de l'EMA journalière (si la règle existe)

    def prepare(self, hourly: list[Candle], daily: list[Candle], rules: PlanRules) -> State:
        closes = [c.close for c in hourly]
        trend = ema_series([d.close for d in daily], rules.trend_ema) if rules.trend_ema else None
        state = State(hourly, daily, rules, closes, atr_series(hourly), rsi_series(closes), trend)
        self.add_series(state)
        return state

    def add_series(self, state: State) -> None:
        """Les séries propres à la stratégie (moyennes, bandes…)."""

    def entry(self, state: State, i: int, day: int) -> Entry | None:
        raise NotImplementedError

    # --- outils communs -----------------------------------------------------------------------

    def sides(self, state: State, i: int, day: int) -> tuple[str, ...]:
        """Les sens permis : celui de la tendance journalière, ou les deux."""
        if not self.trend_filter or state.trend is None:
            return ("achat", "vente")
        line = state.trend[day] if day >= 0 else None
        if line is None:
            return ()
        return ("achat",) if state.closes[i] > line else ("vente",)

    def by_risk(self, state: State, i: int, side: str, stop: float | None = None,
                target: float | None = None) -> Entry | None:  # fmt: skip
        """Entrée au cours de clôture ; stop d'au moins `stop_atr` ATR (ou celui donné s'il
        est plus loin) ; objectif à `min_rr` R (ou celui donné)."""
        width = state.atr[i]
        if not width:
            return None
        close, sign = state.closes[i], 1 if side == "achat" else -1
        floor = close - sign * state.rules.stop_atr * width
        stop = floor if stop is None else (min(stop, floor) if sign > 0 else max(stop, floor))
        if stop == close:
            stop = close - sign * width
        risk = abs(close - stop)
        if target is None:
            target = close + sign * (state.rules.min_rr or 2.0) * risk
        if (target - close) * sign <= 0:
            return None  # objectif déjà dépassé : pas de trade
        return Entry(side, stop, target)

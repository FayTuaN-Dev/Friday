"""Check-list d'une stratégie autre que le plan : sa règle d'entrée a-t-elle donné un signal
dans le sens de l'idée, sur les dernières bougies 1 h fermées ? (Les règles de gestion du
risque — stop, objectif, risque, annonce, trades ouverts — restent celles du plan.)"""

from datetime import datetime, timedelta

from friday.trading.checklist import KO, OK, UNKNOWN, Check, Idea, Market
from friday.trading.plan_rules import PlanRules
from friday.trading.strategies import Strategy, finished_day
from friday.trading.strategies.base import closed_days

RECENT = 3  # un signal de moins de 3 h compte encore


def signal(idea: Idea, market: Market, now: datetime, rules: PlanRules,
           strategy: Strategy) -> Check:  # fmt: skip
    name = f"Signal de ta stratégie ({strategy.label})"
    hourly = [c for c in market.hourly if c.time + timedelta(hours=1) <= now]  # fermées
    in_days = strategy.unit == "jour"
    if in_days:  # stratégie journalière (Turtles) : les journées fermées
        hourly = closed_days(market.daily, now)
    if len(hourly) < 2:
        return Check(name, UNKNOWN, "pas assez d'historique")
    state = strategy.prepare(hourly, market.daily, rules)
    for age in range(RECENT):
        i = len(hourly) - 1 - age
        entry = strategy.entry(state, i, finished_day(market.daily, hourly[i].time))
        if entry is not None and entry.side == idea.direction:
            when = (
                ("sur la dernière journée" if age == 0 else f"il y a {age + 1} jours")
                if in_days
                else ("sur la dernière bougie 1 h" if age == 0 else f"il y a {age + 1} h")
            )
            return Check(name, OK, f"signal d'{'achat' if idea.buy else 'vente'} {when}")
    span = "dernières journées" if in_days else "dernières bougies 1 h"
    return Check(name, KO, f"aucun signal d'{'achat' if idea.buy else 'vente'} sur les "
                           f"{RECENT} {span} ({strategy.summary})")  # fmt: skip

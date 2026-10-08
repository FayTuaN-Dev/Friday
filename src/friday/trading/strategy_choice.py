"""Quelle stratégie suivre (data/trading_strategies.json) : celle choisie pour un instrument,
sinon celle par défaut (Réglages → Trading → Ma stratégie), sinon le premier plan écrit
traduit, sinon le modèle « repli ». C'est elle que suivent alertes, check-list, briefing,
backtest, et le plan joint aux analyses de Claude.

Les plans écrits sont dans le carnet (plan_book.py) ; une stratégie de plan s'appelle
« plan:<id> ». « mon_plan » (choix d'avant le carnet) désigne le premier plan traduit."""

import json
import logging
from pathlib import Path

from friday.trading.plan_book import PREFIX, PlanBook
from friday.trading.strategies import BY_NAME, STRATEGIES, Strategy
from friday.trading.strategies.plan import PlanStrategy

log = logging.getLogger(__name__)
DEFAULT = "_defaut"  # clé du choix par défaut dans le fichier
MINE = "mon_plan"  # le premier plan écrit traduit


class StrategyChoice:
    def __init__(self, path: Path | None, book: PlanBook | None = None) -> None:
        self.path, self.book = path, book or PlanBook(None)

    def available(self) -> tuple[Strategy, ...]:
        return (*self.book.strategies(), *STRATEGIES)

    def first_plan(self) -> Strategy | None:
        found = self.book.strategies()
        return found[0] if found else None

    def chosen(self) -> dict[str, str]:
        if self.path is None or not self.path.is_file():
            return {}
        try:
            data = json.loads(self.path.read_text("utf-8"))
            return {k: v for k, v in data.items() if isinstance(v, str)}
        except (OSError, ValueError, AttributeError):
            log.warning("Choix des stratégies illisible (%s) : choix par défaut", self.path)
            return {}

    def default(self) -> Strategy:
        return self.named(self.chosen().get(DEFAULT, MINE))

    def get(self, symbol: str) -> Strategy:
        name = self.chosen().get(symbol)
        return self.named(name) if name else self.default()

    def set(self, symbol: str, name: str) -> None:
        """`symbol` = DEFAULT : le choix pour tous les instruments sans choix propre."""
        data = self.chosen()
        data[symbol] = name
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, indent=2), "utf-8")

    def named(self, name: str) -> Strategy:
        """Une stratégie par son nom ; un plan supprimé ou pas encore traduit : le modèle."""
        if name == MINE:
            return self.first_plan() or PlanStrategy()
        if name.startswith(PREFIX):
            plan = self.book.get(name[len(PREFIX) :])
            return self.book.strategy(plan) if plan and plan["spec"] else PlanStrategy()
        return BY_NAME.get(name, PlanStrategy())

    def plan_text(self, symbol: str) -> str:
        """Ce que Claude doit connaître de la stratégie suivie : le texte du plan écrit, ou la
        description de la stratégie de base."""
        strategy = self.get(symbol)
        if strategy.name.startswith(PREFIX):
            plan = self.book.get(strategy.name[len(PREFIX) :])
            if plan:
                return f"Plan « {plan['nom']} » :\n{plan['texte']}"
        return f"Stratégie suivie : {strategy.label} ({strategy.summary})."

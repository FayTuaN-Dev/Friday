"""La stratégie choisie pour chaque instrument (data/trading_strategies.json) : celle des
alertes, de la check-list et du briefing. Par défaut : le plan."""

import json
import logging
from pathlib import Path

from friday.trading.strategies import BY_NAME, Strategy
from friday.trading.strategies.plan import PlanStrategy

log = logging.getLogger(__name__)


class StrategyChoice:
    def __init__(self, path: Path | None) -> None:
        self.path = path

    def chosen(self) -> dict[str, str]:
        if self.path is None or not self.path.is_file():
            return {}
        try:
            data = json.loads(self.path.read_text("utf-8"))
            return {k: v for k, v in data.items() if v in BY_NAME}
        except (OSError, ValueError, AttributeError):
            log.warning("Choix des stratégies illisible (%s) : le plan partout", self.path)
            return {}

    def get(self, symbol: str) -> Strategy:
        return BY_NAME.get(self.chosen().get(symbol, "plan"), PlanStrategy())

    def set(self, symbol: str, name: str) -> None:
        data = self.chosen()
        if name == "plan":
            data.pop(symbol, None)  # le plan est le choix par défaut
        else:
            data[symbol] = name
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, indent=2), "utf-8")

"""Outils du mode trading : la surveillance de plusieurs marchés (P2). « Surveille tous les
marchés avec Turtle » : chaque marché que la stratégie suit (ses familles cochées) devient
surveillé, avec elle comme stratégie ; chaque setup est noté au carnet et annoncé.
« Mes derniers setups » : le carnet. « Arrête de surveiller les marchés » : fin, les alertes
de prix restent. Tout sur le PC (cours publics Yahoo)."""

from datetime import datetime

from friday.tools.base import Display, Tool, ToolResult
from friday.tools.strategies_markets import asked_strategy
from friday.trading.alerts.watcher import AlertWatcher
from friday.trading.backtest.portfolio import UNIVERSE
from friday.trading.instruments import FAMILIES, by_symbol, family
from friday.trading.sessions import PARIS

SHOWN = 10  # setups listés


class WatchMarketsTool(Tool):
    name = "watch_markets"
    description = (
        "Surveille tous les marchés que suit une stratégie (« surveille tous les marchés avec "
        "Turtle », « surveille les marchés de mon plan ») et annonce chaque setup ; ou arrête "
        "(« arrête de surveiller les marchés »)."
    )
    parameters = {
        "strategy": {"type": "string", "description": "La stratégie nommée, s'il en nomme une"},
        "stop": {"type": "boolean", "description": "true : arrêter la surveillance"},
        "request": {"type": "string", "description": "La phrase de l'utilisateur"},
    }

    def __init__(self, watcher: AlertWatcher, choice) -> None:
        self.watcher, self.choice = watcher, choice

    def label(self, args: dict) -> str:
        return "🔔 Surveillance des marchés" + (" : arrêt" if args.get("stop") else "")

    def run(self, strategy: str = "", stop: bool = False, request: str = "") -> ToolResult:
        store = self.watcher.store
        if stop:
            count = store.remove_setups()
            return ToolResult(f"Dis EXACTEMENT : « Surveillance arrêtée sur {count} marché(s). "
                              "Tes alertes de prix restent. »")  # fmt: skip
        name = asked_strategy(self.choice, strategy, request)
        chosen = self.choice.named(name) if name else self.choice.default()
        markets = [m for m in map(by_symbol, UNIVERSE) if chosen.covers(m)]
        for market in markets:
            self.choice.set(market.symbol, chosen.name)
            store.add_setup(market.symbol)
        families = sorted({family(m) for m in markets}, key=list(FAMILIES).index)
        kinds = ", ".join(FAMILIES[f].lower() for f in families)
        when = (
            "à la clôture de chaque journée, lue à toute heure ; annoncés entre "
            if chosen.unit == "jour"
            else "à la clôture des bougies 1 h, entre "
        )
        start, end = self.watcher.hours
        spoken = (f"Je surveille {len(markets)} marchés ({kinds}) avec {chosen.label} : setups "
                  f"vus {when}{start} h et {end} h en semaine, et tous notés au carnet. Dis « mes "
                  "derniers setups » pour le voir. Ce ne sont pas des ordres : vérifie avec la "
                  "check-list.")  # fmt: skip
        return ToolResult(f"Dis EXACTEMENT : « {spoken} »")


class RecentSetupsTool(Tool):
    name = "recent_setups"
    description = "Le carnet des setups vus par la surveillance (« mes derniers setups »)."
    parameters = {}

    def __init__(self, watcher: AlertWatcher) -> None:
        self.watcher = watcher

    def label(self, args: dict) -> str:
        return "📒 Carnet des setups"

    def run(self) -> ToolResult:
        found = self.watcher.setups.all()[-SHOWN:][::-1]
        if not found:
            return ToolResult("Dis EXACTEMENT : « Aucun setup noté pour le moment. »")
        items = [{"text": f"{_name(e)} · {e['side']} · {_when(e)}", "meta": e["text"]}
                 for e in found]  # fmt: skip
        spoken = "Derniers setups : " + " ; ".join(
            f"{e['side']} sur {_name(e)} ({_when(e)})" for e in found[:5]) + "."  # fmt: skip
        return ToolResult(
            f"Dis EXACTEMENT : « {spoken} » Le carnet est affiché.",
            Display("items", "Carnet des setups", {"icon": "📒", "items": items}),
        )


def _name(entry: dict) -> str:
    market = by_symbol(entry["symbol"])
    return market.name if market else entry["symbol"]


def _when(entry: dict) -> str:
    bar = datetime.fromisoformat(entry["bar"])
    if entry["unit"] == "jour":
        return f"journée du {bar:%d/%m}"
    return f"{bar.astimezone(PARIS):%d/%m à %H h}"

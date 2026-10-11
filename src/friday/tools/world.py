"""Outils de la veille monde (J9) : « quoi de neuf dans le monde ? » et « qu'est-ce qui peut
bouger les marchés ? ». Phrases construites par le code (world/digest.py) ; le détail
s'affiche à l'écran."""

from collections.abc import Callable

from friday.tools.base import Display, Tool, ToolResult
from friday.trading.instruments import Instrument, by_symbol, detect
from friday.voice.wake import normalize
from friday.world.digest import World
from friday.world.sources import WorldUnavailable

DEFAULT = ("EURUSD", "XAUUSD", "USOIL")  # sans trading configuré : les marchés courants
MOVERS = ("bouger les marches", "bouge les marches", "bougent les marches", "bouger mes marches",
          "faire bouger", "fait bouger", "font bouger")  # fmt: skip
ABOUT = ("quoi de neuf pour", "quoi de neuf sur", "quoi de neuf cote", "l actualite de",
         "l actu de", "les nouvelles de")  # + un instrument  # fmt: skip


# MONTRER le monde (J9b) : le globe plein écran
SHOW = ("montre moi le monde", "montre le monde", "affiche le monde", "montre moi le globe",
        "affiche le globe", "carte du monde", "montre moi ce qui se passe dans le monde",
        "fais moi voir le monde", "montre moi la situation dans le monde")  # fmt: skip
WORLD = ("quoi de neuf dans le monde", "se passe dans le monde", "nouvelles du monde",
         "actualite internationale", "actualites internationales", "infos internationales",
         "info internationale", "actu internationale", "point sur le monde")  # fmt: skip


def world_request(text: str) -> tuple[str, dict] | None:
    """Les demandes de la veille monde, reconnues par le code : « montre-moi le monde » →
    show_world ; « qu'est-ce qui peut bouger les marchés ? », « quoi de neuf pour l'or ? » →
    market_movers, avec l'instrument (constaté : qwen inventait EUR/USD, ou donnait le cours
    de l'or) ; « quoi de neuf dans le monde ? » → world_news."""
    padded = f" {normalize(text)} "
    if any(f" {w}" in padded for w in SHOW):
        return ("show_world", {})
    found = detect(text)
    if any(f" {w}" in padded for w in MOVERS) or (found and any(f" {w}" in padded for w in ABOUT)):
        return ("market_movers", {"instrument": found.name if found else ""})
    if any(f" {w}" in padded for w in WORLD):  # « quoi de neuf dans le monde ? »
        return ("world_news", {})
    return None


def my_instruments(trading) -> list[Instrument]:
    """Ceux du briefing trading (réglages), puis ceux des alertes ; sinon DEFAULT."""
    briefing = getattr(trading, "briefing", None)
    alerts = getattr(trading, "alerts", None)
    found = [detect(n) or by_symbol(n) for n in getattr(briefing, "configured", ())]
    found += [by_symbol(a.symbol) for a in alerts.store.all()] if alerts is not None else []
    found = [i for n, i in enumerate(found) if i is not None and i not in found[:n]]
    return found or [by_symbol(s) for s in DEFAULT]


class WorldNewsTool(Tool):
    name = "world_news"
    description = (
        "Le point sur l'actualité internationale et les catastrophes en cours (« quoi de neuf "
        "dans le monde ? », « les infos internationales », « il y a eu un séisme ? »)."
    )
    parameters = {}

    def __init__(self, world: World) -> None:
        self.world = world

    def label(self, args: dict) -> str:
        return "🌍 Le monde"

    def run(self) -> ToolResult:
        try:
            spoken, items = self.world.overview()
        except WorldUnavailable as error:
            return ToolResult(f"Dis EXACTEMENT : « {error} »")
        display = Display("items", "Dans le monde", {"icon": "🌍", "items": items})
        return ToolResult(spoken, display if items else None)


class MarketMoversTool(Tool):
    name = "market_movers"
    description = (
        "Ce qui, dans l'actualité internationale, peut faire bouger les marchés de "
        "l'utilisateur (« qu'est-ce qui peut bouger les marchés ? », « quoi de neuf pour "
        "l'or ? »). Pas pour un cours : market_quote."
    )
    parameters = {
        "instrument": {"type": "string", "description": "« or », « EUR/USD »… s'il en nomme un"}
    }

    def __init__(self, world: World,
                 mine: Callable[[], list[Instrument]] | None = None) -> None:  # fmt: skip
        """`mine()` : les instruments de l'utilisateur (briefing trading, alertes…)."""
        self.world = world
        self.mine = mine or (lambda: my_instruments(None))

    def label(self, args: dict) -> str:
        return "🌍 Ce qui peut bouger les marchés"

    def run(self, instrument: str = "") -> ToolResult:
        found = detect(instrument) or by_symbol(instrument) if instrument else None
        instruments = [found] if found else [i for i in self.mine() if i is not None]
        try:
            return ToolResult(self.world.movers(instruments or None, named=found is not None))
        except WorldUnavailable as error:
            return ToolResult(f"Dis EXACTEMENT : « {error} »")


class ShowWorldTool(Tool):
    name = "show_world"
    description = (
        "MONTRER le monde sur un globe plein écran : thèmes de l'actualité et catastrophes en "
        "cours (« montre-moi ce qui se passe dans le monde », « affiche le globe »)."
    )
    parameters = {}

    def __init__(self, world: World,
                 mine: Callable[[], list[Instrument]] | None = None) -> None:  # fmt: skip
        self.world = world
        self.mine = mine or (lambda: my_instruments(None))

    def label(self, args: dict) -> str:
        return "🌍 Globe"

    def run(self) -> ToolResult:
        from friday.world.globe import globe

        try:
            spoken, data = globe(self.world, [i for i in self.mine() if i is not None])
        except WorldUnavailable as error:
            return ToolResult(f"Dis EXACTEMENT : « {error} »")
        return ToolResult(spoken, Display("world", "Le monde en ce moment", data))

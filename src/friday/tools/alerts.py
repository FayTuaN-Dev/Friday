"""Outils du mode trading : les alertes (« préviens-moi si l'or passe 4 150 », « surveille
l'or », « mes alertes », « annule l'alerte 2 »). Surveillées sur le PC (trading/alerts)."""

from friday.tools.base import Display, Tool, ToolResult
from friday.tools.trading import INSTRUMENT
from friday.trading import risk_calc
from friday.trading.alerts.store import Alert
from friday.trading.alerts.watcher import AlertWatcher
from friday.trading.instruments import by_symbol
from friday.trading.market import MarketUnavailable, _digits


def _price(instrument, value: float) -> str:
    return f"{value:,.{_digits(instrument)}f}".replace(",", " ").replace(".", ",")


def describe(alert: Alert) -> str:
    instrument = by_symbol(alert.symbol)
    name = instrument.name if instrument else alert.symbol
    if alert.kind == "setup":
        return f"n°{alert.id} : setup du plan sur {name} (bougies 1 h, heures de trading)"
    way = "au-dessus de" if alert.above else "sous"
    level = _price(instrument, alert.level) if instrument else f"{alert.level:g}"
    return f"n°{alert.id} : {name} {way} {level}"


class _AlertTool(Tool):
    def __init__(self, watcher: AlertWatcher) -> None:
        self.watcher = watcher


class PriceAlertTool(_AlertTool):
    name = "set_price_alert"
    description = (
        "Alerte de prix : prévient à la voix quand un instrument atteint un niveau (« préviens-"
        "moi si l'or passe 4 150 », « alerte sur l'EUR/USD à 1,1550 »)."
    )
    parameters = {"instrument": INSTRUMENT,
                  "level": {"type": "number", "description": "Le niveau de prix"}}  # fmt: skip
    required = ("instrument", "level")

    def label(self, args: dict) -> str:
        return f"🔔 Alerte : {args.get('instrument', '')} à {args.get('level', '')}"

    def run(self, instrument: str, level: float) -> ToolResult:
        try:
            item = risk_calc.resolve(instrument)
            price, seen = self.watcher.price(item)
        except (ValueError, MarketUnavailable) as error:
            return ToolResult(f"Alerte impossible : {error} Dis-le simplement.")
        alert = self.watcher.store.add_level(item.symbol, level, above=level > price)
        source = ""
        if not seen and item.note:  # contrat à terme sans graphique : le dire
            known = item.symbol in self.watcher.store.offsets
            source = (" Graphique TradingView non affiché : cours du contrat à terme, "
                      + ("recalé sur le dernier écart vu avec ton graphique." if known
                         else "ouvre le graphique pour l'aligner."))  # fmt: skip
        spoken = (f"C'est noté, alerte {describe(alert)} ; le cours est à "
                  f"{_price(item, price)}. Je te préviens dès qu'il y est.{source}")  # fmt: skip
        return ToolResult(f"Dis EXACTEMENT : « {spoken} »")


class WatchSetupTool(_AlertTool):
    name = "watch_setup"
    description = (
        "Surveille un instrument et prévient à la voix quand le setup du plan de trading se forme "
        "(« surveille l'or », « préviens-moi quand mon setup se forme sur l'EUR/USD »)."
    )
    parameters = {"instrument": INSTRUMENT}
    required = ("instrument",)

    def label(self, args: dict) -> str:
        return f"🔔 Surveillance du setup : {args.get('instrument', '')}"

    def run(self, instrument: str) -> ToolResult:
        try:
            item = risk_calc.resolve(instrument)
        except ValueError as error:
            return ToolResult(f"Surveillance impossible : {error}")
        self.watcher.store.add_setup(item.symbol)
        start, end = self.watcher.hours
        spoken = (f"Je surveille {item.name} : je te préviens quand le setup de ton plan se "
                  f"forme, à la clôture des bougies 1 h, entre {start} h et {end} h en "
                  "semaine.")  # fmt: skip
        return ToolResult(f"Dis EXACTEMENT : « {spoken} »")


class ListAlertsTool(_AlertTool):
    name = "list_alerts"
    description = "Liste les alertes de trading en cours (« mes alertes »)."
    parameters = {}

    def run(self) -> ToolResult:
        alerts = self.watcher.store.all()
        if not alerts:
            return ToolResult("Dis EXACTEMENT : « Aucune alerte en cours. »")
        items = [{"text": describe(a), "meta": f"créée le {a.created}"} for a in alerts]
        lines = "\n".join(f"- {describe(a)}" for a in alerts)
        return ToolResult(
            f"Alertes en cours (affichées) :\n{lines}\nRésume-les en une phrase.",
            Display("items", "Alertes de trading", {"icon": "🔔", "items": items}),
        )


class CancelAlertTool(_AlertTool):
    name = "cancel_alert"
    description = "Annule une alerte de trading par son numéro, ou toutes (« annule l'alerte 2 »)."
    parameters = {
        "alert_id": {"type": "integer", "description": "Numéro de l'alerte"},
        "all": {"type": "boolean", "description": "true pour annuler toutes les alertes"},
    }

    def run(self, alert_id: int | None = None, all: bool = False) -> ToolResult:  # noqa: A002
        store = self.watcher.store
        if all:
            return ToolResult(f"Dis EXACTEMENT : « {store.clear()} alerte(s) annulée(s). »")
        if alert_id is None:
            return ToolResult("Quelle alerte ? Demande son numéro (ou « toutes »).")
        if store.remove(int(alert_id)):
            return ToolResult(f"Dis EXACTEMENT : « Alerte n°{alert_id} annulée. »")
        return ToolResult(f"Pas d'alerte n°{alert_id}. Propose de lister les alertes.")

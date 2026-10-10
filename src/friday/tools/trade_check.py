"""Outil du mode trading : la check-list avant trade (« je veux acheter l'or à 4 160, stop
4 140 »). Les règles du plan sont vérifiées par le code (trading/plan_checks.py) ; seuls des
cours publics sont lus en ligne (Yahoo, ForexFactory). Rien ne part chez Claude."""

import logging
from collections.abc import Callable
from datetime import UTC, datetime

from friday.tools.base import Display, Tool, ToolResult
from friday.tools.trading import INSTRUMENT, Prices, value_per_lot
from friday.trading import Trading, risk_calc
from friday.trading.calendar import SourceUnavailable
from friday.trading.checklist import ICONS, Context, Idea, Market
from friday.trading.instruments import Instrument, chart_price, same_scale
from friday.trading.market import MarketUnavailable, fetch
from friday.trading.plan_checks import evaluate
from friday.trading.plan_rules import load_rules

log = logging.getLogger(__name__)


def load_market(instrument: Instrument, chart: float | None) -> Market:
    """Cours, bougies de 1 h (1 mois) et journalières (2 ans, pour l'EMA200). Contrat à terme
    (l'or…) : les niveaux sont recalés sur le cours du graphique TradingView s'il est visible."""
    quote, hourly = fetch(instrument.yahoo, "1h", "1mo")
    _, daily = fetch(instrument.yahoo, "1d", "2y")
    if not instrument.note:
        return Market(quote.price, daily, hourly)
    if chart is None:
        return Market(quote.price, daily, hourly, shift_known=False)
    return Market(quote.price, daily, hourly, shift=quote.price - chart)


class TradeCheckTool(Tool):
    name = "trade_check"
    description = (
        "Check-list avant trade : vérifie une idée de trade (sens, entrée, stop, objectif) "
        "règle par règle par rapport au plan de l'utilisateur (« je veux acheter l'or à 4 160, "
        "stop 4 140 », « mon trade respecte-t-il mon plan ? »). Feu vert / orange / rouge."
    )
    parameters = {
        "instrument": INSTRUMENT,
        "direction": {"type": "string", "enum": ["achat", "vente"]},
        "entry": {"type": "number", "description": "Prix d'entrée"},
        "stop": {"type": "number", "description": "Stop loss (prix)"},
        "target": {"type": "number", "description": "Objectif (prix), s'il est donné"},
        "risk_percent": {"type": "number", "description": "Risque en %, s'il est donné"},
        "lots": {"type": "number", "description": "Taille en lots, si elle est donnée"},
    }
    required = ("direction", "entry", "stop")

    def __init__(
        self, trading: Trading, prices: Prices | None = None, market=load_market,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:  # fmt: skip
        self.trading, self.prices, self.market, self.now = trading, prices or Prices(), market, now

    def label(self, args: dict) -> str:
        return f"🚦 Check-list : {args.get('direction', '')} {args.get('instrument', '')}".strip()

    def run(self, direction: str, entry: float, stop: float, instrument: str = "",
            target: float | None = None, risk_percent: float | None = None,
            lots: float | None = None) -> ToolResult:  # fmt: skip
        trading = self.trading
        try:
            item = risk_calc.resolve(instrument) if instrument else trading.instrument_for("")
            if item is None:
                return ToolResult("Quel instrument ? Demande-le.")
            market = self._market(item)
            if market is not None:  # virgule perdue par le modèle : remise à l'échelle
                entry, stop = same_scale(entry, market.price), same_scale(stop, market.price)
                target = same_scale(target, market.price) if target else target
            idea = Idea(item, direction, entry, stop, target, risk_percent, lots)
            idea.check_sides()
        except ValueError as error:
            return ToolResult(f"Vérification impossible : {error} Dis-le simplement.")
        choice = getattr(self.trading, "choice", None)
        strategy = choice.get(item.symbol) if choice is not None else None
        verdict = evaluate(idea, market, self._context(item, entry), self._rules(),
                           strategy)  # fmt: skip
        title = f"{direction.capitalize()} {item.name} à {entry:g}, stop {stop:g}"
        items = [{"text": verdict.text().split("\n")[0], "meta": "Calculé sur le PC, sans Claude"}]
        items += [{"text": f"{ICONS[c.status]} {c.rule}", "meta": c.detail} for c in verdict.checks]
        return ToolResult(
            "Check-list faite sur le PC à partir du plan (le détail de chaque règle est affiché). "
            "Dis EXACTEMENT cette phrase, sans rien ajouter sur les règles : "
            f"« {verdict.spoken()} » Puis, en quelques mots, que ce n'est ni un signal ni "
            "un conseil.",
            Display("items", f"Check-list : {title}", {"icon": "🚦", "items": items}),
        )  # fmt: skip

    def _rules(self):
        return load_rules(self.trading.rules_path)

    def _market(self, item: Instrument) -> Market | None:
        capture = self.trading.capture
        title = capture.window_title() if capture is not None else None
        try:
            return self.market(item, chart_price(title, item) if title else None)
        except MarketUnavailable as error:
            log.info("Check-list sans données de marché : %s", error)
            return None

    def _context(self, item: Instrument, entry: float) -> Context:
        account = self.trading.account_currency
        open_trades = sum(1 for t in self.trading.journal.all_trades() if t.exit is None)
        try:
            per_lot = value_per_lot(item, account, entry, self.prices)[0]
        except ValueError:  # MissingRate compris : le risque sera « à vérifier »
            per_lot = None
        return Context(self.now(), self._events(), open_trades, per_lot, account)

    def _events(self):
        source = getattr(self.trading.builder.context, "events", None)
        if source is None:
            return None
        try:
            events = source()
        except SourceUnavailable:
            return None
        return events[0] if isinstance(events, tuple) else events

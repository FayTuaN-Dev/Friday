"""Mode trading de Friday : analyses par Claude (isolé, après aperçu et validation), calculs de
risque déterministes et journal local. Voir docs/ARCHITECTURE.md."""

from dataclasses import dataclass, field
from pathlib import Path

from friday.tools.claude_code import ClaudeCodeJob
from friday.trading.context_builder import ContextBuilder
from friday.trading.instruments import Instrument, by_symbol, detect, from_chart_title
from friday.trading.journal import TradeJournal
from friday.trading.mode import TradingMode


@dataclass
class Trading:
    mode: TradingMode
    journal: TradeJournal
    builder: ContextBuilder
    job: ClaudeCodeJob  # Claude isolé (analyst.py)
    account_currency: str = "EUR"
    capture: object = None  # ChartCapture (fenêtre du graphique), ou None
    current: Instrument | None = field(default_factory=lambda: by_symbol("EURUSD"))
    rules_path: Path | None = None  # règles chiffrées de la check-list (plan_rules.py)
    alerts: object = None  # AlertWatcher (alerts/watcher.py), ou None

    def chart_shows(self, instrument: Instrument | None) -> bool:
        """Le graphique TradingView affiché est-il celui de cet instrument ?"""
        if instrument is None or self.capture is None:
            return False
        title = self.capture.window_title()
        shown = from_chart_title(title) if title else None
        return shown is not None and shown.symbol == instrument.symbol

    def instrument_for(self, question: str) -> Instrument | None:
        """L'instrument de la question ; sinon celui du graphique TradingView affiché ; sinon
        le dernier utilisé. Il devient l'instrument courant (« et sur l'or ? » change)."""
        found = detect(question)
        if found is None and self.capture is not None:
            title = self.capture.window_title()
            found = from_chart_title(title) if title else None
        if found is not None:
            self.current = found
        return self.current

"""Mode trading de Friday : analyses par Claude (isolé, après aperçu et validation), calculs de
risque déterministes et journal local. Voir docs/ARCHITECTURE.md."""

from dataclasses import dataclass

from friday.tools.claude_code import ClaudeCodeJob
from friday.trading.context_builder import ContextBuilder
from friday.trading.journal import TradeJournal
from friday.trading.mode import TradingMode


@dataclass
class Trading:
    mode: TradingMode
    journal: TradeJournal
    builder: ContextBuilder
    job: ClaudeCodeJob  # Claude isolé (analyst.py)
    account_currency: str = "EUR"

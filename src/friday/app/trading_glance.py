"""Le coup d'œil trading des cartes de côté (W3), la partie réseau : le cours des marchés
suivis (Yahoo, variation du jour) et les prochaines annonces à fort impact de leurs devises
(ForexFactory, gardé une heure sur le disque). Lu hors du fil de l'interface, toutes les
minutes, seulement quand la carte est affichée. Journal et carnet, eux, sont lus sur place."""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from friday.trading import calendar
from friday.trading.instruments import Instrument
from friday.trading.market import MarketUnavailable, Quote, fetch

log = logging.getLogger(__name__)
MAX_MARKETS, MAX_EVENTS = 5, 2


@dataclass(frozen=True)
class Glance:
    quotes: list[tuple[Instrument, Quote | None]] = field(default_factory=list)
    events: list[calendar.Event] = field(default_factory=list)


def quote_of(instrument: Instrument) -> Quote | None:
    try:
        return fetch(instrument.yahoo, "1d", "5d")[0]
    except MarketUnavailable as error:
        log.debug("Cours de %s indisponible : %s", instrument.symbol, error)
        return None


def next_events(events: list[calendar.Event], currencies: set[str], now: datetime,
                count: int = MAX_EVENTS) -> list[calendar.Event]:  # fmt: skip
    """Les prochaines annonces à FORT impact de ces devises (ou de toutes), à venir."""
    found = [e for e in events if e.impact == "High" and e.time > now
             and (e.currency in currencies or e.currency == "All")]  # fmt: skip
    return sorted(found, key=lambda e: e.time)[:count]


class TradingGlance:
    def __init__(self, instruments: Callable[[], list[Instrument]], cache_dir=None,
                 quote: Callable = quote_of, events: Callable | None = None,
                 now: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:  # fmt: skip
        """`instruments()` : ceux du briefing (réglés, surveillés, ou l'instrument courant)."""
        self.instruments, self.quote, self.now = instruments, quote, now
        path = cache_dir / "ff_calendar.json" if cache_dir else None
        self.events = events or (lambda: calendar.load(path)[0])

    def read(self) -> Glance:
        chosen = self.instruments()[:MAX_MARKETS]
        quotes = [(i, self.quote(i)) for i in chosen]
        try:
            events = next_events(self.events(), {c for i in chosen for c in i.currencies},
                                 self.now())  # fmt: skip
        except calendar.SourceUnavailable as error:
            log.debug("Calendrier indisponible : %s", error)
            events = []
        return Glance(quotes, events)


def from_trading(trading) -> TradingGlance | None:
    briefing = getattr(trading, "briefing", None)
    if briefing is None:
        return None
    from friday.core.config import DATA_DIR

    return TradingGlance(briefing.instruments, DATA_DIR / "cache")

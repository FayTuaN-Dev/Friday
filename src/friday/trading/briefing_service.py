"""Le briefing trading au bon moment : en semaine, une fois par jour, dès que la plage de
trading commence (ou au démarrage de Friday s'il arrive pendant la plage). Le jour du dernier
briefing est gardé (data/trading_briefing.json) : pas de doublon après un redémarrage."""

import json
import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from friday.trading.alerts.watcher import yahoo_history
from friday.trading.briefing import TradingBriefing, build
from friday.trading.calendar import PARIS, SourceUnavailable
from friday.trading.instruments import Instrument, by_symbol, detect
from friday.trading.plan_rules import load_rules

log = logging.getLogger(__name__)


class BriefingService:
    def __init__(
        self, trading, state_path: Path | None, hours: tuple[int, int] = (9, 18),
        instruments: tuple[str, ...] = (), auto: bool = True, history=yahoo_history,
        now: Callable[[], datetime] = lambda: datetime.now(UTC), interval: float = 60,
    ) -> None:  # fmt: skip
        """`trading` : l'objet Trading (journal, alertes, sources du calendrier, instrument)."""
        self.trading, self.state_path, self.hours = trading, state_path, hours
        self.configured, self.auto, self.history = instruments, auto, history
        self.now, self.interval = now, interval
        self._stop = threading.Event()

    def instruments(self) -> list[Instrument]:
        """Ceux des réglages ; sinon ceux qu'on surveille ; sinon l'instrument courant."""
        found = [detect(name) or by_symbol(name) for name in self.configured]
        if not found and getattr(self.trading, "alerts", None) is not None:
            found = [by_symbol(a.symbol) for a in self.trading.alerts.store.all()
                     if a.kind == "setup"]  # fmt: skip
        if not found and self.trading.current is not None:
            found = [self.trading.current]
        return [i for n, i in enumerate(found) if i is not None and i not in found[:n]]

    def build(self, instruments: list[Instrument] | None = None) -> TradingBriefing:
        alerts = getattr(self.trading, "alerts", None)
        return build(
            instruments or self.instruments(), self.history, self._events(),
            load_rules(self.trading.rules_path), self.now(), self.hours,
            alerts.store.offsets if alerts is not None else {},
            sum(1 for t in self.trading.journal.all_trades() if t.exit is None),
            len(alerts.store.all()) if alerts is not None else 0,
        )  # fmt: skip

    def due(self) -> bool:
        local = self.now().astimezone(PARIS)
        return (self.auto and local.weekday() < 5 and self.hours[0] <= local.hour < self.hours[1]
                and self._last() != local.date().isoformat())  # fmt: skip

    def mark_done(self) -> None:
        if self.state_path is not None:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            day = self.now().astimezone(PARIS).date().isoformat()
            self.state_path.write_text(json.dumps({"last_run": day}), "utf-8")

    def start(self, on_ready: Callable[[TradingBriefing], None]) -> None:
        threading.Thread(target=self._loop, args=(on_ready,), daemon=True,
                         name="trading-briefing").start()  # fmt: skip

    def stop(self) -> None:
        self._stop.set()

    def check(self, on_ready: Callable[[TradingBriefing], None]) -> None:
        if self.due():
            self.mark_done()  # même en cas d'échec : pas de nouvel essai chaque minute
            on_ready(self.build())

    def _loop(self, on_ready) -> None:
        while not self._stop.wait(self.interval):
            try:
                self.check(on_ready)
            except Exception:
                log.exception("Briefing trading impossible")

    def _last(self) -> str | None:
        try:
            return json.loads(self.state_path.read_text("utf-8")).get("last_run")
        except (AttributeError, OSError, ValueError):
            return None

    def _events(self):
        source = getattr(getattr(self.trading.builder, "context", None), "events", None)
        if source is None:
            return None
        try:
            events = source()
        except SourceUnavailable:
            return None
        return events[0] if isinstance(events, tuple) else events

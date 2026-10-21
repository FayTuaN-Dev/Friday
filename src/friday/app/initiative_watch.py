"""Le veilleur des initiatives : chaque minute, il regarde si Friday a quelque chose d'utile à
dire d'elle-même (I1 : l'heure de départ pour un rendez-vous) et, si le garde-fou est d'accord,
le passe à l'assistant, qui l'annonce À VOIX HAUTE (en mode jeu : gardé pour le retour)."""

import logging
import threading
from collections.abc import Callable
from datetime import datetime, timedelta

from friday.core.config import DATA_DIR
from friday.google.calendar import Event, GoogleCalendar
from friday.initiative.departure import Trip, departure_text, key
from friday.initiative.guard import Guard, quiet_hours
from friday.initiative.travel import Travel
from friday.tools.base import ToolResult

log = logging.getLogger(__name__)

TASK = "initiative"
CHECK_EVERY = 60  # secondes
AGENDA_EVERY = timedelta(minutes=10)  # l'agenda Google n'est relu que toutes les 10 min
AHEAD = timedelta(hours=4)  # un rendez-vous plus lointain attendra le tour suivant


class InitiativeWatch:
    def __init__(self, guard: Guard, on_initiative: Callable[[str, ToolResult], None],
                 calendar: GoogleCalendar | None = None, travel: Travel | None = None,
                 ) -> None:  # fmt: skip
        self.guard, self.on_initiative = guard, on_initiative
        self.calendar, self.travel = calendar, travel
        self._events: list[Event] = []
        self._read_at: datetime | None = None
        self._stop = threading.Event()

    def events(self, now: datetime) -> list[Event]:
        """Les événements des 4 prochaines heures (demain matin compris, tard le soir), relus
        toutes les 10 min ; agenda injoignable : la dernière liste connue."""
        if self._read_at is None or now - self._read_at >= AGENDA_EVERY:
            try:
                self._events = self.calendar.between(now.date(), (now + AHEAD).date())
                self._read_at = now
            except Exception as error:  # compte déconnecté, réseau…
                log.info("Initiatives : agenda illisible (%s)", error)
        return self._events

    def departures(self, now: datetime) -> list[str]:
        if self.calendar is None or self.travel is None:
            return []
        said = []
        for event in self.events(now):
            if (event.all_day or not event.location.strip() or self.guard.said(key(event))
                    or not now < event.start <= now + AHEAD):  # fmt: skip
                continue
            seconds = self.travel.seconds(event.location)
            if seconds is None:
                continue
            trip = Trip(event, seconds)
            if trip.due(now) and self.guard.allow(key(event), now):
                said.append(departure_text(trip, now))
        return said

    def check(self, now: datetime | None = None) -> int:
        now = now or datetime.now()
        texts = self.departures(now)
        for text in texts:
            log.info("Initiative : %s", text)
            self.on_initiative(TASK, ToolResult(text))
        return len(texts)

    def start(self) -> None:
        def loop() -> None:
            while not self._stop.wait(CHECK_EVERY):
                try:
                    self.check()
                except Exception:
                    log.exception("Initiatives : vérification impossible")

        threading.Thread(target=loop, daemon=True, name="initiatives").start()

    def stop(self) -> None:
        self._stop.set()


def start_initiatives(settings, google, on_initiative: Callable[[str, ToolResult], None],
                      ) -> InitiativeWatch:  # fmt: skip
    """Le veilleur, branché sur ce qui est disponible : sans compte Google ou sans ville par
    défaut, pas d'heure de départ."""
    guard = Guard(DATA_DIR / "initiative_vu.json", quiet_hours(settings.initiative_quiet),
                  max(1, settings.initiative_per_hour))  # fmt: skip
    calendar = travel = None
    if settings.initiative_departure and google is not None and settings.home_city.strip():
        calendar = GoogleCalendar(lambda: google.service("calendar", "v3"))
        travel = Travel(settings.home_city.strip())
    watch = InitiativeWatch(guard, on_initiative, calendar, travel)
    watch.start()
    return watch

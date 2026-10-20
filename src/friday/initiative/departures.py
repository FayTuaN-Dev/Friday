"""La source « heure de départ » (I1) : l'agenda Google relu toutes les 10 min, le trajet de
chaque rendez-vous qui a une adresse, et la phrase quand il est temps de prévenir."""

import logging
from collections.abc import Callable
from datetime import datetime, timedelta

from friday.google.calendar import Event, GoogleCalendar
from friday.initiative.departure import Trip, departure_text, key
from friday.initiative.source import Candidate
from friday.initiative.travel import Travel

log = logging.getLogger(__name__)

AGENDA_EVERY = timedelta(minutes=10)  # l'agenda Google n'est relu que toutes les 10 min
AHEAD = timedelta(hours=4)  # un rendez-vous plus lointain attendra le tour suivant


class Departures:
    def __init__(self, calendar: GoogleCalendar, travel: Travel) -> None:
        self.calendar, self.travel = calendar, travel
        self._events: list[Event] = []
        self._read_at: datetime | None = None

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

    def candidates(self, now: datetime, said: Callable[[str], bool]) -> list[Candidate]:
        found = []
        for event in self.events(now):
            if (event.all_day or not event.location.strip() or said(key(event))
                    or not now < event.start <= now + AHEAD):  # fmt: skip
                continue
            seconds = self.travel.seconds(event.location)
            if seconds is None:
                continue
            trip = Trip(event, seconds)
            if trip.due(now):
                found.append(Candidate((key(event),), departure_text(trip, now)))
        return found

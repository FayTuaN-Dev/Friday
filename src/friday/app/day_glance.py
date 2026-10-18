"""Le coup d'œil « Aujourd'hui » des cartes de côté (W4), la partie Google : les prochains
rendez-vous de l'agenda (aujourd'hui et demain) et les mails non lus (le nombre, et les
derniers expéditeurs). Lu hors du fil de l'interface, toutes les 5 minutes, seulement quand
la carte est affichée et le compte connecté. Les rappels, eux, sont lus sur place (local)."""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from friday.google.calendar import Event, GoogleCalendar
from friday.google.gmail import Gmail

log = logging.getLogger(__name__)
MAX_EVENTS, MAX_SENDERS = 3, 2


@dataclass(frozen=True)
class Day:
    events: list[Event] = field(default_factory=list)
    unread: int | None = None  # None : inconnu
    senders: list[str] = field(default_factory=list)
    connected: bool = False


def upcoming(events: list[Event], now: datetime, count: int = MAX_EVENTS) -> list[Event]:
    """Ceux qui ne sont pas finis (les journées entières d'aujourd'hui comprises)."""
    return [e for e in events if e.end > now or (e.all_day and e.start.date() >= now.date())
            ][:count]  # fmt: skip


class DayGlance:
    def __init__(self, account, now: Callable[[], datetime] = datetime.now) -> None:
        self.account, self.now = account, now
        self.calendar = GoogleCalendar(lambda: account.service("calendar", "v3"))
        self.gmail = Gmail(lambda: account.service("gmail", "v1"))

    def read(self) -> Day:
        if not self.account.connected:
            return Day()
        now = self.now()
        try:
            today: date = now.date()
            events = upcoming(self.calendar.between(today, today + timedelta(days=1)), now)
        except Exception as error:  # réseau, droits : la carte reste sur l'agenda vide
            log.debug("Agenda Google illisible : %s", error)
            events = []
        try:
            senders = [m.sender_name for m in self.gmail.unread(limit=MAX_SENDERS)]
        except Exception as error:
            log.debug("Mails non lus illisibles : %s", error)
            senders = []
        return Day(events, self.gmail.unread_total(), senders, True)

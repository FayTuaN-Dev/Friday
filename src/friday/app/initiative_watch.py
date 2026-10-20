"""Le veilleur des initiatives : chaque minute, il demande à chaque source (I1 : l'heure de
départ d'un rendez-vous, I2 : les mails importants) si Friday a quelque chose d'utile à dire
d'elle-même et, si le garde-fou est d'accord, le passe à l'assistant, qui l'annonce À VOIX
HAUTE (en mode jeu : gardé pour le retour)."""

import logging
import threading
from collections.abc import Callable
from datetime import datetime

from friday.core.config import DATA_DIR
from friday.initiative.guard import Guard, quiet_hours
from friday.initiative.source import Source
from friday.tools.base import ToolResult

log = logging.getLogger(__name__)

TASK = "initiative"
CHECK_EVERY = 60  # secondes


class InitiativeWatch:
    def __init__(self, guard: Guard, on_initiative: Callable[[str, ToolResult], None],
                 sources: list[Source]) -> None:  # fmt: skip
        self.guard, self.on_initiative, self.sources = guard, on_initiative, sources
        self._stop = threading.Event()

    def check(self, now: datetime | None = None) -> int:
        """Annonce ce qui doit l'être ; renvoie combien. Une source en panne n'arrête pas les
        autres."""
        now = now or datetime.now()
        count = 0
        for source in self.sources:
            try:
                found = source.candidates(now, self.guard.said)
            except Exception:
                log.exception("Initiatives : %s en panne", type(source).__name__)
                continue
            for candidate in found:
                if self.guard.allow(candidate.keys, now):
                    log.info("Initiative : %s", candidate.text)
                    self.on_initiative(TASK, ToolResult(candidate.text))
                    count += 1
        return count

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


def sources(settings, google) -> list[Source]:
    """Les initiatives allumées et possibles : sans compte Google, aucune ; sans ville par
    défaut, pas d'heure de départ."""
    if google is None:
        return []
    found: list[Source] = []
    if settings.initiative_departure and settings.home_city.strip():
        from friday.google.calendar import GoogleCalendar
        from friday.initiative.departures import Departures
        from friday.initiative.travel import Travel
        from friday.initiative.weather import TripWeather

        calendar = GoogleCalendar(lambda: google.service("calendar", "v3"))
        weather = TripWeather() if settings.initiative_weather else None
        found.append(Departures(calendar, Travel(settings.home_city.strip()), weather))
    if settings.initiative_mails:
        from friday.google.gmail import Gmail
        from friday.initiative.mails import ImportantMails, entries

        gmail = Gmail(lambda: google.service("gmail", "v1"))
        found.append(ImportantMails(gmail, entries(settings.initiative_mail_senders),
                                    entries(settings.initiative_mail_words)))  # fmt: skip
    return found


def start_initiatives(settings, google, on_initiative: Callable[[str, ToolResult], None],
                      ) -> InitiativeWatch:  # fmt: skip
    guard = Guard(DATA_DIR / "initiative_vu.json", quiet_hours(settings.initiative_quiet),
                  max(1, settings.initiative_per_hour))  # fmt: skip
    watch = InitiativeWatch(guard, on_initiative, sources(settings, google))
    watch.start()
    return watch

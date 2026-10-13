"""Le coup d'œil de l'écran d'accueil (U2) : une ligne sur la journée, tirée de ce que Friday
sait déjà (rappels du jour, agenda Google, mails non lus). Chaque source est facultative :
une source absente, déconnectée ou en panne est simplement omise, jamais bloquante."""

import logging
from collections.abc import Callable
from datetime import date, datetime

log = logging.getLogger(__name__)


def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'s' if count > 1 else ''}"


def reminders_today(agenda, today: date) -> str:
    count = sum(1 for r in agenda.pending() if r.due_at.date() == today)
    return _plural(count, "rappel") + " aujourd'hui" if count else ""


def events_today(google, today: date) -> str:
    from friday.google.calendar import GoogleCalendar

    events = GoogleCalendar(lambda: google.service("calendar", "v3")).between(today, today)
    if not events:
        return "agenda libre aujourd'hui"
    first = events[0]
    return f"{len(events)} rendez-vous aujourd'hui (le premier : {first.when()}, {first.title})"


def unread_mails(google) -> str:
    from friday.google.gmail import Gmail

    count = Gmail(lambda: google.service("gmail", "v1")).unread_total()
    if count is None:
        return ""
    if not count:
        return "aucun mail non lu"
    return _plural(count, "mail") + (" non lus" if count > 1 else " non lu")


def glance(components, now: datetime | None = None) -> str:
    """« 2 rendez-vous aujourd'hui… · 20 mails non lus · 1 rappel aujourd'hui »."""
    today = (now or datetime.now()).date()
    google = getattr(components, "google", None)
    if google is not None and not _safe(lambda: google.connected):
        google = None  # jamais d'ouverture du navigateur depuis l'accueil
    parts: list[Callable[[], str]] = []
    if google is not None:
        parts += [lambda: events_today(google, today), lambda: unread_mails(google)]
    agenda = getattr(components, "agenda", None)
    if agenda is not None:
        parts.append(lambda: reminders_today(agenda, today))
    return " · ".join(text for text in map(_safe, parts) if text)


def _safe(part: Callable):
    try:
        return part()
    except Exception as error:  # réseau, jeton expiré… : la ligne se passe de cette source
        log.info("Accueil : une source est indisponible (%s)", error)
        return ""

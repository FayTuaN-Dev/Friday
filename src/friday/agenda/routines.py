"""Routines planifiées (J5) : « tous les jours à 7 h, fais-moi mon briefing », « le lundi à
8 h, trie mes mails ». Une routine = une demande, une heure, des jours. Rangées dans
data/routines.json. Les jours et l'heure sont lus par le CODE (le modèle recopie ce que
l'utilisateur a dit). Une routine manquée (PC éteint) est rattrapée si le retard est de moins
de 3 h, une seule fois."""

import json
import logging
import re
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from friday.agenda.times import parse_time
from friday.brain.prompts import JOURS
from friday.voice.wake import normalize

log = logging.getLogger(__name__)

ALL_DAYS = (0, 1, 2, 3, 4, 5, 6)
WEEKDAYS, WEEKEND = (0, 1, 2, 3, 4), (5, 6)
CATCH_UP = timedelta(hours=3)


@dataclass
class Routine:
    id: int
    request: str  # ce que Friday fera, avec les mots de l'utilisateur
    time: str  # « 07:30 »
    days: list[int] = field(default_factory=lambda: list(ALL_DAYS))  # 0 = lundi
    enabled: bool = True
    created: str = ""  # ISO : une routine ne rattrape rien d'avant sa création
    last_run: str = ""  # ISO du dernier créneau exécuté


def parse_days(text: str) -> list[int]:
    """« tous les jours », « en semaine », « le week-end », « lundi et jeudi », « du lundi au
    vendredi », « les mardis » → jours (0 = lundi). Rien de reconnu : tous les jours."""
    words = f" {normalize(text)} "
    if " semaine " in words and " week " not in words and not _named(words):
        return list(WEEKDAYS)
    if (" week end " in words or " weekend " in words) and not _named(words):
        return list(WEEKEND)
    if span := re.search(rf" du ({'|'.join(JOURS)})s? au ({'|'.join(JOURS)})s? ", words):
        start, end = JOURS.index(span.group(1)), JOURS.index(span.group(2))
        return [(start + n) % 7 for n in range((end - start) % 7 + 1)]
    return _named(words) or list(ALL_DAYS)


def _named(words: str) -> list[int]:
    return [n for n, day in enumerate(JOURS) if f" {day} " in words or f" {day}s " in words]


def describe_days(days: list[int]) -> str:
    days = sorted(set(days))
    if days == list(ALL_DAYS):
        return "tous les jours"
    if days == list(WEEKDAYS):
        return "en semaine"
    if days == list(WEEKEND):
        return "le week-end"
    names = [f"le {JOURS[d]}" for d in days]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " et " + names[-1]


def spoken_time(hhmm: str) -> str:
    """« 07:30 » → « 7 h 30 » ; « 08:00 » → « 8 h »."""
    hour, minute = map(int, hhmm.split(":"))
    return f"{hour} h {minute:02d}" if minute else f"{hour} h"


def describe(routine: Routine) -> str:
    return f"{describe_days(routine.days)} à {spoken_time(routine.time)} : « {routine.request} »"


def last_slot(routine: Routine, now: datetime) -> datetime | None:
    """Le dernier créneau prévu (jour + heure) au plus tard maintenant, sur 7 jours."""
    hour, minute = map(int, routine.time.split(":"))
    for back in range(8):
        day = now - timedelta(days=back)
        slot = day.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if slot.weekday() in routine.days and slot <= now:
            return slot
    return None


def is_due(routine: Routine, now: datetime) -> datetime | None:
    """Le créneau à exécuter maintenant, ou None (déjà fait, trop vieux, désactivée…)."""
    slot = last_slot(routine, now)
    if not routine.enabled or slot is None or now - slot > CATCH_UP:
        return None
    if routine.created and slot.isoformat() < routine.created:
        return None
    if routine.last_run and slot.isoformat() <= routine.last_run:
        return None
    return slot


class RoutineStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def all(self) -> list[Routine]:
        try:
            raw = json.loads(self.path.read_text("utf-8"))
            return [Routine(**item) for item in raw]
        except FileNotFoundError:
            return []
        except (OSError, ValueError, TypeError) as error:
            log.warning("Routines illisibles : %s", error)
            return []

    def _save(self, routines: list[Routine]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = [asdict(r) for r in routines]
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")

    def add(self, request: str, time: str, days: list[int], now: datetime) -> Routine:
        hour, minute = parse_time(time)
        with self._lock:
            routines = self.all()
            routine = Routine(max((r.id for r in routines), default=0) + 1,
                              " ".join(request.split()).strip(" .«»\"'"),
                              f"{hour:02d}:{minute:02d}", sorted(set(days)),
                              created=now.isoformat(timespec="seconds"))  # fmt: skip
            self._save([*routines, routine])
        return routine

    def remove(self, routine_id: int) -> Routine | None:
        with self._lock:
            routines = self.all()
            gone = next((r for r in routines if r.id == routine_id), None)
            if gone:
                self._save([r for r in routines if r.id != routine_id])
        return gone

    def mark_run(self, routine_id: int, slot: datetime) -> None:
        with self._lock:
            routines = self.all()
            for routine in routines:
                if routine.id == routine_id:
                    routine.last_run = slot.isoformat()
            self._save(routines)

    def due(self, now: datetime) -> list[tuple[Routine, datetime]]:
        return [(r, slot) for r in self.all() if (slot := is_due(r, now)) is not None]

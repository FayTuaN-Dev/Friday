"""Calcul des dates de rappel. Le LLM donne « 18:00 » et « demain », Friday calcule la date
(le LLM se trompe trop souvent en faisant lui-même ce calcul)."""

import re
from datetime import datetime, timedelta

from friday.agenda.durations import parse_duration
from friday.brain.prompts import JOURS, french_date
from friday.voice.wake import normalize

RELATIVE_DAYS = {"aujourd hui": 0, "ce soir": 0, "demain": 1, "apres demain": 2}
TIME_PATTERN = re.compile(r"^(\d{1,2})\s*(?:h|:|heures?)?\s*(\d{2})?$")


def parse_time(text: str) -> tuple[int, int]:
    """« 18:00 », « 18h », « 18h30 », « 9 » → (heure, minute)."""
    match = TIME_PATTERN.match(text.strip().lower().replace(" ", ""))
    if not match:
        raise ValueError(f"heure illisible : « {text} »")
    hour, minute = int(match.group(1)), int(match.group(2) or 0)
    if hour > 23 or minute > 59:
        raise ValueError(f"heure impossible : « {text} »")
    return hour, minute


def resolve(
    now: datetime,
    delay: str | float | None = None,
    time: str | None = None,
    day: str | None = None,
) -> datetime:
    """Quand déclencher : après un délai (« 2 minutes », tel que dit), ou à une heure
    (aujourd'hui, demain, un jour nommé)."""
    if delay not in (None, "", 0):
        return now + parse_duration(str(delay))
    if not time:
        raise ValueError("il faut un délai ou une heure")
    hour, minute = parse_time(time)
    at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    wanted = normalize(day or "")
    if wanted in RELATIVE_DAYS:
        return at + timedelta(days=RELATIVE_DAYS[wanted])
    if wanted in JOURS:
        ahead = (JOURS.index(wanted) - now.weekday()) % 7
        at += timedelta(days=ahead)
        return at if at > now else at + timedelta(days=7)
    if wanted:
        raise ValueError(f"jour non compris : « {day} »")
    return at if at > now else at + timedelta(days=1)  # heure passée : c'est pour demain


def describe(when: datetime, now: datetime) -> str:
    """« aujourd'hui à 18:00 », « demain à 09:00 », « samedi 10 octobre à 18:00 »."""
    delta = (when.date() - now.date()).days
    day = {0: "aujourd'hui", 1: "demain"}.get(delta, french_date(when))
    return f"{day} à {when:%H:%M}"

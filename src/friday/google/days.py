"""Jours et périodes dits en français → dates. Le LLM recopie ce que l'utilisateur a dit
(« jeudi », « le 12 novembre », « cette semaine ») et Friday calcule : il se trompe trop
souvent en faisant lui-même ce calcul."""

import re
from datetime import date, timedelta

from friday.brain.prompts import JOURS, MOIS
from friday.voice.wake import normalize

RELATIVE = {"aujourd hui": 0, "ce soir": 0, "ce matin": 0, "demain": 1, "apres demain": 2}
MONTHS = {normalize(m): i for i, m in enumerate(MOIS, 1)}
FILLERS = {"le", "la", "ce", "cette", "prochain", "prochaine", "matin", "soir", "apres", "midi"}


def parse_day(text: str, today: date) -> date:
    """« demain », « jeudi », « jeudi prochain », « le 12 », « 12 novembre », « 12/11 »,
    « 2026-11-12 » → date (jamais dans le passé pour un jour de semaine ou une date sans année)."""
    words = normalize(text)
    if not words:
        return today
    for phrase, offset in sorted(RELATIVE.items(), key=lambda p: -len(p[0])):
        if words.startswith(phrase):
            return today + timedelta(days=offset)
    if iso := re.fullmatch(r"(\d{4}) (\d{1,2}) (\d{1,2})", words):
        return date(*map(int, iso.groups()))
    tokens = [w for w in words.split() if w not in FILLERS]
    for token in tokens:
        if token in JOURS:
            ahead = (JOURS.index(token) - today.weekday()) % 7
            return today + timedelta(days=ahead)
    numbers = [int(t) for t in tokens if t.isdigit()]
    month = next((MONTHS[t] for t in tokens if t in MONTHS), None)
    if numbers and month is None and len(numbers) >= 2:  # « 12/11 » ou « 12/11/2026 »
        day, month, *year = numbers
        return _future(day, month, year[0] if year else None, today)
    if numbers:
        day = numbers[0]
        year = numbers[1] if len(numbers) > 1 and numbers[1] > 31 else None
        if month is None:  # « le 12 » : ce mois-ci, ou le mois prochain si c'est passé
            candidate = _safe_date(today.year, today.month, day)
            if candidate >= today:
                return candidate
            month = today.month % 12 + 1
            year = today.year + (today.month == 12)
        return _future(day, month, year, today)
    raise ValueError(f"jour non compris : « {text} »")


def parse_period(text: str, today: date) -> tuple[date, date]:
    """Période à afficher → (premier jour, dernier jour inclus)."""
    words = normalize(text or "aujourd'hui")
    monday = today - timedelta(days=today.weekday())
    if "semaine prochaine" in words:
        return monday + timedelta(days=7), monday + timedelta(days=13)
    if "semaine" in words:
        return today, monday + timedelta(days=6)
    if "week end" in words or "weekend" in words:
        saturday = today + timedelta(days=(5 - today.weekday()) % 7)
        return saturday, saturday + timedelta(days=1)
    if "mois" in words:
        return today, today + timedelta(days=30)
    day = parse_day(text, today)
    return day, day


def _safe_date(year: int, month: int, day: int) -> date:
    try:
        return date(year, month, day)
    except ValueError as error:
        raise ValueError(f"date impossible : {day}/{month}/{year}") from error


def _future(day: int, month: int, year: int | None, today: date) -> date:
    if year is not None:
        return _safe_date(year if year > 100 else 2000 + year, month, day)
    candidate = _safe_date(today.year, month, day)
    return candidate if candidate >= today else _safe_date(today.year + 1, month, day)

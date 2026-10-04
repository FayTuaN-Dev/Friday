"""Durées dites à l'oral → timedelta. Le LLM transmet « 2 minutes » tel quel : il avait
converti « dans deux minutes » en 120 minutes."""

import re
from datetime import timedelta

from jarvis.voice.wake import normalize

NUMBERS = {
    "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7,
    "huit": 8, "neuf": 9, "dix": 10, "onze": 11, "douze": 12, "treize": 13, "quatorze": 14,
    "quinze": 15, "seize": 16, "vingt": 20, "trente": 30, "quarante": 40, "cinquante": 50,
    "soixante": 60,
}  # fmt: skip
UNITS = {
    "h": 3600, "heure": 3600, "heures": 3600, "hr": 3600,
    "min": 60, "mn": 60, "minute": 60, "minutes": 60,
    "s": 1, "sec": 1, "seconde": 1, "secondes": 1,
}  # fmt: skip
# Expressions toutes faites, remplacées avant l'analyse
IDIOMS = [
    (r"\b(trois )?quarts? d heure\b", lambda m: "45 minutes" if m.group(1) else "15 minutes"),
    (r"\b(une )?demi heure\b", lambda m: "30 minutes"),
    (r"\bun 15 minutes\b", lambda m: "15 minutes"),
]


def _tokens(text: str) -> list[str]:
    text = normalize(text)
    text = re.sub(r"(\d)([a-z])", r"\1 \2", text)
    text = re.sub(r"([a-z])(\d)", r"\1 \2", text)
    for pattern, replace in IDIOMS:
        text = re.sub(pattern, replace, text)
    tokens: list[str] = []
    for word in text.split():
        value = str(NUMBERS[word]) if word in NUMBERS else word
        if value.isdigit() and tokens and tokens[-1].isdigit():  # « vingt cinq » → 25
            tokens[-1] = str(int(tokens[-1]) + int(value))
        else:
            tokens.append(value)
    return tokens


def parse_duration(text: str) -> timedelta:
    """« 2 minutes », « deux minutes », « 1h30 », « une heure et demie », « un quart d'heure »,
    « 90 secondes », « 10 » (= minutes)."""
    tokens = _tokens(text)
    seconds, pending, last_unit = 0.0, None, None
    for i, token in enumerate(tokens):
        if token.isdigit():
            pending = int(token)
        elif token in UNITS and pending is not None:
            seconds += pending * UNITS[token]
            last_unit, pending = UNITS[token], None
        elif token in ("demi", "demie") and last_unit and i >= 1 and tokens[i - 1] == "et":
            seconds += last_unit / 2  # « une heure et demie »
        elif token == "quart" and last_unit == 3600 and tokens[i - 1] == "et":
            seconds += 900  # « une heure et quart »
    if pending is not None:  # nombre final sans unité : « 1 h 30 » → minutes, « 10 » → minutes
        seconds += pending * 60
    if seconds <= 0:
        raise ValueError(f"durée non comprise : « {text} »")
    return timedelta(seconds=seconds)

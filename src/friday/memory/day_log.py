"""Mémoire de la journée (F5) : chaque échange (ce que l'utilisateur a dit, le début de la
réponse) est gardé sur ce PC, dans data/journee.db, 90 jours. « De quoi on a parlé hier ? » :
le CODE trouve le jour et relit ses échanges ; le modèle n'a plus qu'à les résumer."""

import re
import sqlite3
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

from friday.brain.prompts import JOURS, MOIS
from friday.voice.wake import normalize

KEEP_DAYS = 90
SAID_CHARS, REPLY_CHARS = 300, 300  # gardés ; relus plus courts (tools/day_memory.py)

# « De quoi on a parlé hier ? » : reconnu par le code
ASKS = ("de quoi on a parle", "de quoi avons nous parle", "on a parle de quoi",
        "qu est ce qu on s est dit", "qu est ce qu on a dit", "qu est ce que je t ai demande",
        "que t ai je demande", "nos conversations", "notre conversation d", "nos echanges",
        "resume notre journee", "resume de notre journee", "resume nos echanges")  # fmt: skip


class DayLog:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS echanges (quand TEXT NOT NULL, "
                         "dit TEXT NOT NULL, reponse TEXT NOT NULL)")  # fmt: skip
        self._db.execute("CREATE INDEX IF NOT EXISTS par_jour ON echanges (quand)")
        self.prune()

    def add(self, said: str, reply: str, when: datetime | None = None) -> None:
        said, reply = " ".join(said.split()), " ".join(reply.split())
        if not said:
            return
        when = (when or datetime.now()).isoformat(timespec="seconds")
        with self._lock:
            self._db.execute("INSERT INTO echanges VALUES (?, ?, ?)",
                             (when, said[:SAID_CHARS], reply[:REPLY_CHARS]))  # fmt: skip
            self._db.commit()

    def day(self, day: date) -> list[tuple[datetime, str, str]]:
        start, end = day.isoformat(), (day + timedelta(days=1)).isoformat()
        with self._lock:
            rows = self._db.execute(
                "SELECT quand, dit, reponse FROM echanges WHERE quand >= ? AND quand < ? "
                "ORDER BY quand", (start, end)).fetchall()  # fmt: skip
        return [(datetime.fromisoformat(when), said, reply) for when, said, reply in rows]

    def prune(self, today: date | None = None) -> None:
        limit = ((today or date.today()) - timedelta(days=KEEP_DAYS)).isoformat()
        with self._lock:
            self._db.execute("DELETE FROM echanges WHERE quand < ?", (limit,))
            self._db.commit()

    def close(self) -> None:
        self._db.close()


def asks_day(text: str) -> bool:
    padded = f" {normalize(text)} "
    return any(f" {words}" in padded for words in ASKS)


def past_day(text: str, today: date) -> date:
    """Le jour PASSÉ dont on parle : « hier », « avant-hier », « lundi » (le dernier lundi),
    « il y a 3 jours », « le 4 octobre » ; aujourd'hui sinon."""
    words = f" {normalize(text)} "
    if " avant hier " in words:
        return today - timedelta(days=2)
    if " hier " in words:
        return today - timedelta(days=1)
    if ago := re.search(r" il y a (\d+) jours? ", words):
        return today - timedelta(days=int(ago.group(1)))
    if " semaine derniere " in words or " il y a une semaine " in words:
        return today - timedelta(days=7)
    for n, name in enumerate(JOURS):
        if f" {name} " in words:
            back = (today.weekday() - n) % 7
            return today - timedelta(days=back or 7)
    for n, month in enumerate(MOIS, 1):
        if found := re.search(rf" (\d{{1,2}}) {normalize(month)} ", words):
            day = date(today.year, n, int(found.group(1)))
            return day if day <= today else day.replace(year=today.year - 1)
    return today


def day_name(day: date, today: date) -> str:
    """« aujourd'hui », « hier », « avant-hier », sinon « jeudi 9 octobre »."""
    gap = (today - day).days
    if gap in (0, 1, 2):
        return ("aujourd'hui", "hier", "avant-hier")[gap]
    return f"{JOURS[day.weekday()]} {day.day} {MOIS[day.month - 1]}"

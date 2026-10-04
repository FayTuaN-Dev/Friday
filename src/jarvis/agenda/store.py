"""Rappels et notes, dans une base SQLite locale (data/agenda.db)."""

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY,
    text TEXT NOT NULL,
    due_at TEXT NOT NULL,       -- date ISO locale
    done INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY,
    list TEXT NOT NULL,         -- « notes », « courses », « tâches »…
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


@dataclass
class Reminder:
    id: int
    text: str
    due_at: datetime


@dataclass
class Note:
    id: int
    list: str
    text: str


class AgendaStore:
    def __init__(self, path: Path | str) -> None:
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._db.executescript(SCHEMA)
            self._db.commit()

    def _run(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cursor = self._db.execute(sql, params)
            self._db.commit()
            return cursor

    # --- Rappels ---

    def add_reminder(self, text: str, due_at: datetime) -> Reminder:
        cursor = self._run(
            "INSERT INTO reminders (text, due_at) VALUES (?, ?)",
            (text, due_at.isoformat(timespec="seconds")),
        )
        return Reminder(cursor.lastrowid, text, due_at)

    def pending(self) -> list[Reminder]:
        rows = self._run(
            "SELECT id, text, due_at FROM reminders WHERE done = 0 ORDER BY due_at"
        ).fetchall()
        return [Reminder(i, t, datetime.fromisoformat(d)) for i, t, d in rows]

    def due(self, now: datetime) -> list[Reminder]:
        return [r for r in self.pending() if r.due_at <= now]

    def mark_done(self, reminder_id: int) -> bool:
        return self._run("UPDATE reminders SET done = 1 WHERE id = ? AND done = 0",
                         (reminder_id,)).rowcount > 0  # fmt: skip

    # --- Notes et listes ---

    def add_note(self, list_name: str, text: str) -> Note:
        cursor = self._run(
            "INSERT INTO notes (list, text, created_at) VALUES (?, ?, ?)",
            (list_name, text, datetime.now().isoformat(timespec="seconds")),
        )
        return Note(cursor.lastrowid, list_name, text)

    def notes(self, list_name: str | None = None) -> list[Note]:
        if list_name:
            rows = self._run("SELECT id, list, text FROM notes WHERE list = ? ORDER BY id",
                             (list_name,)).fetchall()  # fmt: skip
        else:
            rows = self._run("SELECT id, list, text FROM notes ORDER BY list, id").fetchall()
        return [Note(*row) for row in rows]

    def lists(self) -> list[str]:
        return [r[0] for r in self._run("SELECT DISTINCT list FROM notes ORDER BY list")]

    def remove_note(self, note_id: int) -> Note | None:
        row = self._run("SELECT id, list, text FROM notes WHERE id = ?", (note_id,)).fetchone()
        if row:
            self._run("DELETE FROM notes WHERE id = ?", (note_id,))
        return Note(*row) if row else None

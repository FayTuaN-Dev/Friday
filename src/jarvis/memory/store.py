"""Stockage des souvenirs dans une base SQLite locale (data/memory.db)."""

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY,
    text TEXT NOT NULL,
    source TEXT NOT NULL,          -- « explicit » (demandé) ou « auto » (déduit)
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    embedding BLOB NOT NULL        -- vecteur float32 normalisé
)
"""


@dataclass
class Memory:
    id: int
    text: str
    source: str
    updated_at: str


class MemoryStore:
    def __init__(self, path: Path | str) -> None:
        # Utilisée depuis plusieurs threads (assistant, mémorisation en arrière-plan).
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._db.execute(SCHEMA)
            self._db.commit()

    def add(self, text: str, source: str, embedding: np.ndarray) -> Memory:
        now = _now()
        with self._lock:
            cursor = self._db.execute(
                "INSERT INTO memories (text, source, created_at, updated_at, embedding) "
                "VALUES (?, ?, ?, ?, ?)",
                (text, source, now, now, embedding.astype(np.float32).tobytes()),
            )
            self._db.commit()
        return Memory(cursor.lastrowid, text, source, now)

    def update(self, memory_id: int, text: str, embedding: np.ndarray) -> Memory | None:
        now = _now()
        with self._lock:
            cursor = self._db.execute(
                "UPDATE memories SET text = ?, updated_at = ?, embedding = ? WHERE id = ?",
                (text, now, embedding.astype(np.float32).tobytes(), memory_id),
            )
            self._db.commit()
        return self.get(memory_id) if cursor.rowcount else None

    def delete(self, memory_id: int) -> Memory | None:
        memory = self.get(memory_id)
        if memory:
            with self._lock:
                self._db.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
                self._db.commit()
        return memory

    def get(self, memory_id: int) -> Memory | None:
        with self._lock:
            row = self._db.execute(
                "SELECT id, text, source, updated_at FROM memories WHERE id = ?", (memory_id,)
            ).fetchone()
        return Memory(*row) if row else None

    def all(self) -> list[Memory]:
        with self._lock:
            rows = self._db.execute(
                "SELECT id, text, source, updated_at FROM memories ORDER BY id"
            ).fetchall()
        return [Memory(*row) for row in rows]

    def count(self) -> int:
        with self._lock:
            return self._db.execute("SELECT COUNT(*) FROM memories").fetchone()[0]

    def nearest(self, vector: np.ndarray, k: int = 1) -> list[tuple[Memory, float]]:
        """Les `k` souvenirs les plus proches par le sens, avec leur score (0 à 1)."""
        with self._lock:
            rows = self._db.execute(
                "SELECT id, text, source, updated_at, embedding FROM memories"
            ).fetchall()
        if not rows:
            return []
        matrix = np.stack([np.frombuffer(r[4], dtype=np.float32) for r in rows])
        scores = matrix @ vector
        best = np.argsort(-scores)[:k]
        return [(Memory(*rows[i][:4]), float(scores[i])) for i in best]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")

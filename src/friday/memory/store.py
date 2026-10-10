"""Stockage des souvenirs dans une base SQLite locale (data/memory.db). Mémoire « vivante » :
un souvenir répété est RENFORCÉ (confirmations, confiance) au lieu d'être recopié ; un
souvenir corrigé est REMPLACÉ mais gardé dans l'historique (statut « replaced »), jamais
effacé en silence. Seul « oublie que… » efface vraiment (avec ses anciennes versions)."""

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
# Colonnes ajoutées par la mémoire vivante (J1) : migration douce des bases existantes
COLUMNS = {
    "status": "TEXT NOT NULL DEFAULT 'active'",  # « active » ou « replaced »
    "category": "TEXT NOT NULL DEFAULT ''",
    "confirmations": "INTEGER NOT NULL DEFAULT 1",  # fois où le fait a été dit
    "confidence": "REAL NOT NULL DEFAULT 0.75",
    "said": "TEXT NOT NULL DEFAULT ''",  # la phrase de l'utilisateur d'où il vient
    "replaced_by": "INTEGER",
}
FIELDS = ("id, text, source, updated_at, category, confirmations, confidence, said, "
          "created_at, status, replaced_by")  # fmt: skip
CONFIDENCE = {"explicit": 0.9, "auto": 0.75}
CONFIRM_STEP, CONFIDENCE_MAX = 0.05, 0.99


@dataclass
class Memory:
    id: int
    text: str
    source: str
    updated_at: str
    category: str = ""
    confirmations: int = 1
    confidence: float = 0.75
    said: str = ""
    created_at: str = ""
    status: str = "active"
    replaced_by: int | None = None


class MemoryStore:
    def __init__(self, path: Path | str) -> None:
        # Utilisée depuis plusieurs threads (assistant, mémorisation en arrière-plan).
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._db.execute(SCHEMA)
            known = {row[1] for row in self._db.execute("PRAGMA table_info(memories)")}
            for name, kind in COLUMNS.items():
                if name not in known:
                    self._db.execute(f"ALTER TABLE memories ADD COLUMN {name} {kind}")
            self._db.commit()

    def add(self, text: str, source: str, embedding: np.ndarray, category: str = "",
            said: str = "") -> Memory:  # fmt: skip
        now = _now()
        with self._lock:
            cursor = self._db.execute(
                "INSERT INTO memories (text, source, created_at, updated_at, embedding, "
                "category, confidence, said) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (text, source, now, now, _blob(embedding), category,
                 CONFIDENCE.get(source, 0.75), said),
            )  # fmt: skip
            self._db.commit()
        return self.get(cursor.lastrowid)

    def confirm(self, memory_id: int, text: str, embedding: np.ndarray) -> Memory | None:
        """Le fait est redit : reformulé, une confirmation de plus, confiance en hausse."""
        with self._lock:
            cursor = self._db.execute(
                "UPDATE memories SET text = ?, updated_at = ?, embedding = ?, "
                "confirmations = confirmations + 1, confidence = MIN(?, confidence + ?) "
                "WHERE id = ?",
                (text, _now(), _blob(embedding), CONFIDENCE_MAX, CONFIRM_STEP, memory_id),
            )  # fmt: skip
            self._db.commit()
        return self.get(memory_id) if cursor.rowcount else None

    def replace(self, old_id: int, new_id: int) -> None:
        """L'ancien fait reste dans l'historique, marqué remplacé par le nouveau."""
        with self._lock:
            self._db.execute("UPDATE memories SET status = 'replaced', replaced_by = ?, "
                             "updated_at = ? WHERE id = ?", (new_id, _now(), old_id))  # fmt: skip
            self._db.commit()

    def set_category(self, memory_id: int, category: str) -> None:
        with self._lock:
            self._db.execute("UPDATE memories SET category = ? WHERE id = ?",
                             (category, memory_id))  # fmt: skip
            self._db.commit()

    def delete(self, memory_id: int) -> Memory | None:
        """Efface le souvenir ET ses anciennes versions : « oublie » veut dire oublier."""
        memory = self.get(memory_id)
        if memory:
            doomed = [memory_id] + [m.id for m in self.history(memory_id)]
            with self._lock:
                self._db.executemany("DELETE FROM memories WHERE id = ?", [(i,) for i in doomed])
                self._db.commit()
        return memory

    def get(self, memory_id: int) -> Memory | None:
        rows = self._select("WHERE id = ?", (memory_id,))
        return rows[0] if rows else None

    def all(self) -> list[Memory]:
        """Les souvenirs actifs (sans les anciennes versions)."""
        return self._select("WHERE status = 'active' ORDER BY id")

    def history(self, memory_id: int) -> list[Memory]:
        """Les versions remplacées de ce souvenir, de la plus récente à la plus ancienne."""
        found, current = [], memory_id
        while previous := self._select("WHERE replaced_by = ?", (current,)):
            found.append(previous[0])
            current = previous[0].id
        return found

    def count(self) -> int:
        with self._lock:
            return self._db.execute(
                "SELECT COUNT(*) FROM memories WHERE status = 'active'").fetchone()[0]  # fmt: skip

    def nearest(self, vector: np.ndarray, k: int = 1) -> list[tuple[Memory, float]]:
        """Les `k` souvenirs actifs les plus proches par le sens, avec leur score (0 à 1)."""
        with self._lock:
            query = f"SELECT {FIELDS}, embedding FROM memories WHERE status = 'active'"
            rows = self._db.execute(query).fetchall()
        if not rows:
            return []
        matrix = np.stack([np.frombuffer(r[-1], dtype=np.float32) for r in rows])
        scores = matrix @ vector
        best = np.argsort(-scores)[:k]
        return [(Memory(*rows[i][:-1]), float(scores[i])) for i in best]

    def _select(self, where: str, args: tuple = ()) -> list[Memory]:
        with self._lock:
            rows = self._db.execute(f"SELECT {FIELDS} FROM memories {where}", args).fetchall()
        return [Memory(*row) for row in rows]

    def close(self) -> None:
        self._db.close()


def _blob(embedding: np.ndarray) -> bytes:
    return embedding.astype(np.float32).tobytes()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")

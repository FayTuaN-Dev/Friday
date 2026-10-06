"""Index de la bibliothèque (data/library.db) : documents, passages, vecteurs de sens, et un
index plein texte (FTS5) pour les mots exacts (« pip », « EUR/USD », un nom propre)."""

import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from friday.library.chunker import Passage
from friday.voice.wake import normalize

# Mots trop courants pour aider une recherche par mots (« qu'est-ce qu'un pip » → « pip »).
STOPWORDS = set(
    """
a à au aux avec ce ces cet cette c ça d de des du dans donc elle elles en est et etre être
fait faire il ils j je l la le les leur leurs lui m ma me mes moi mon n ne nous on ou où par
pas pour qu que quel quelle quelles quels qui quoi s sa se ses si son sur t ta te tes toi ton
tu un une vos votre vous y comment pourquoi combien quand dit dire selon parle explique
livre livres document documents bibliotheque cours
""".split()
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    mtime REAL NOT NULL,           -- pour réindexer un fichier modifié
    pages INTEGER,
    passages INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS passages (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page INTEGER,
    text TEXT NOT NULL,
    embedding BLOB NOT NULL        -- vecteur float32 normalisé
);
CREATE VIRTUAL TABLE IF NOT EXISTS passages_fts USING fts5(
    text, content='passages', content_rowid='id', tokenize='unicode61 remove_diacritics 2'
);
"""


@dataclass
class LibraryDocument:
    id: int
    path: str
    name: str
    mtime: float
    pages: int | None
    passages: int


@dataclass
class Hit:
    passage_id: int
    document: str  # nom du fichier
    path: str
    page: int | None
    text: str


class LibraryStore:
    def __init__(self, path: Path | str) -> None:
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.execute("PRAGMA foreign_keys = ON")
        self._lock = threading.Lock()
        self._vectors: tuple[np.ndarray, np.ndarray] | None = None  # (ids, matrice), en cache
        with self._lock:
            self._db.executescript(SCHEMA)
            self._db.commit()

    def documents(self) -> list[LibraryDocument]:
        with self._lock:
            rows = self._db.execute(
                "SELECT id, path, name, mtime, pages, passages FROM documents ORDER BY name"
            ).fetchall()
        return [LibraryDocument(*row) for row in rows]

    def add(
        self, path: Path, mtime: float, pages: int | None,
        passages: list[Passage], vectors: np.ndarray,
    ) -> None:  # fmt: skip
        """Ajoute (ou remplace) un document et ses passages."""
        self.remove(str(path))
        with self._lock:
            cursor = self._db.execute(
                "INSERT INTO documents (path, name, mtime, pages, passages) VALUES (?, ?, ?, ?, ?)",
                (str(path), path.name, mtime, pages, len(passages)),
            )
            document_id = cursor.lastrowid
            for passage, vector in zip(passages, vectors, strict=True):
                row = self._db.execute(
                    "INSERT INTO passages (document_id, page, text, embedding) VALUES (?, ?, ?, ?)",
                    (document_id, passage.page, passage.text, vector.astype(np.float32).tobytes()),
                )
                self._db.execute(
                    "INSERT INTO passages_fts (rowid, text) VALUES (?, ?)",
                    (row.lastrowid, passage.text),
                )
            self._db.commit()
            self._vectors = None

    def remove(self, path: str) -> bool:
        with self._lock:
            row = self._db.execute("SELECT id FROM documents WHERE path = ?", (path,)).fetchone()
            if row is None:
                return False
            for passage_id, text in self._db.execute(
                "SELECT id, text FROM passages WHERE document_id = ?", (row[0],)
            ).fetchall():
                self._db.execute(
                    "INSERT INTO passages_fts (passages_fts, rowid, text) VALUES ('delete', ?, ?)",
                    (passage_id, text),
                )
            self._db.execute("DELETE FROM passages WHERE document_id = ?", (row[0],))
            self._db.execute("DELETE FROM documents WHERE id = ?", (row[0],))
            self._db.commit()
            self._vectors = None
        return True

    def by_meaning(self, query: np.ndarray, limit: int) -> list[tuple[int, float]]:
        """(identifiant, ressemblance) des passages les plus proches par le sens."""
        ids, matrix = self._load_vectors()
        if not len(ids):
            return []
        scores = matrix @ query
        return [(int(ids[i]), float(scores[i])) for i in np.argsort(-scores)[:limit]]

    def by_words(self, query: str, limit: int, every_word: bool = False) -> list[int]:
        """Identifiants des passages qui contiennent les mots importants (classement BM25) :
        l'un d'eux, ou tous (`every_word`)."""
        words = [w for w in normalize(query).split() if len(w) > 1 and w not in STOPWORDS]
        if not words:
            return []
        match = (" AND " if every_word else " OR ").join(f'"{w}"' for w in words)
        with self._lock:
            rows = self._db.execute(
                "SELECT rowid FROM passages_fts WHERE passages_fts MATCH ? ORDER BY rank LIMIT ?",
                (match, limit),
            ).fetchall()
        return [row[0] for row in rows]

    def hits(self, passage_ids: list[int]) -> list[Hit]:
        if not passage_ids:
            return []
        marks = ",".join("?" * len(passage_ids))
        with self._lock:
            rows = self._db.execute(
                "SELECT p.id, d.name, d.path, p.page, p.text FROM passages p "
                f"JOIN documents d ON d.id = p.document_id WHERE p.id IN ({marks})",
                passage_ids,
            ).fetchall()
        found = {row[0]: Hit(*row) for row in rows}
        return [found[i] for i in passage_ids if i in found]

    def _load_vectors(self) -> tuple[np.ndarray, np.ndarray]:
        with self._lock:
            if self._vectors is None:
                rows = self._db.execute("SELECT id, embedding FROM passages").fetchall()
                ids = np.array([r[0] for r in rows], dtype=np.int64)
                matrix = (
                    np.stack([np.frombuffer(r[1], dtype=np.float32) for r in rows])
                    if rows else np.zeros((0, 1), dtype=np.float32)
                )  # fmt: skip
                self._vectors = (ids, matrix)
            return self._vectors

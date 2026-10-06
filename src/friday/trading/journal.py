"""Journal de trading local (data/trading.db) : les trades, et la trace de chaque envoi à
Claude (ce qui est parti, quand, empreinte des images). Rien de ce fichier ne part en ligne ;
seul un résumé anonyme (`summary`) peut être joint à une analyse, via l'aperçu."""

import hashlib
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from friday.trading.risk_calc import result_in_r

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY,
    opened_at TEXT NOT NULL,
    pair TEXT NOT NULL,
    direction TEXT NOT NULL,       -- « achat » ou « vente »
    entry REAL NOT NULL,
    stop REAL NOT NULL,
    target REAL,
    lots REAL,
    reason TEXT NOT NULL DEFAULT '',
    capture TEXT,                  -- chemin local d'une capture (jamais envoyé)
    exit REAL,
    closed_at TEXT,
    result_r REAL                  -- résultat en multiples du risque initial
);
CREATE TABLE IF NOT EXISTS sent (
    id INTEGER PRIMARY KEY,
    sent_at TEXT NOT NULL,
    question TEXT NOT NULL,
    content TEXT NOT NULL,         -- le texte exact envoyé (déjà masqué)
    chars INTEGER NOT NULL,
    images TEXT NOT NULL DEFAULT '', -- empreintes SHA-256 des images envoyées
    answer TEXT
);
"""


@dataclass
class Trade:
    id: int
    opened_at: str
    pair: str
    direction: str
    entry: float
    stop: float
    target: float | None
    lots: float | None
    reason: str
    exit: float | None
    result_r: float | None


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class TradeJournal:
    def __init__(self, path: Path | str) -> None:
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._db.executescript(SCHEMA)
            self._db.commit()

    def open_trade(
        self, pair: str, direction: str, entry: float, stop: float,
        target: float | None = None, lots: float | None = None, reason: str = "",
    ) -> Trade:  # fmt: skip
        with self._lock:
            cursor = self._db.execute(
                "INSERT INTO trades (opened_at, pair, direction, entry, stop, target, lots, reason)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (_now(), pair.upper(), direction, entry, stop, target, lots, reason),
            )
            self._db.commit()
        return self.get(cursor.lastrowid)

    def close_trade(self, trade_id: int, exit_price: float) -> Trade | None:
        trade = self.get(trade_id)
        if trade is None or trade.exit is not None:
            return None
        r = result_in_r(trade.entry, trade.stop, exit_price)
        with self._lock:
            self._db.execute(
                "UPDATE trades SET exit = ?, closed_at = ?, result_r = ? WHERE id = ?",
                (exit_price, _now(), r, trade_id),
            )
            self._db.commit()
        return self.get(trade_id)

    def get(self, trade_id: int) -> Trade | None:
        rows = self._trades("WHERE id = ?", (trade_id,))
        return rows[0] if rows else None

    def recent(self, limit: int = 10) -> list[Trade]:
        return self._trades("ORDER BY id DESC LIMIT ?", (limit,))

    def _trades(self, where: str, params: tuple) -> list[Trade]:
        with self._lock:
            rows = self._db.execute(
                "SELECT id, opened_at, pair, direction, entry, stop, target, lots, reason, exit,"
                f" result_r FROM trades {where}",
                params,
            ).fetchall()
        return [Trade(*row) for row in rows]

    def summary(self) -> str:
        """Bilan anonyme : nombre de trades, réussite, moyenne et total en R (aucun montant)."""
        with self._lock:
            results = [r for (r,) in self._db.execute(
                "SELECT result_r FROM trades WHERE result_r IS NOT NULL").fetchall()]  # fmt: skip
            open_count = self._db.execute(
                "SELECT COUNT(*) FROM trades WHERE result_r IS NULL"
            ).fetchone()[0]
        if not results:
            return f"Aucun trade clôturé ({open_count} en cours)."
        wins = sum(1 for r in results if r > 0)
        return (
            f"{len(results)} trades clôturés ({open_count} en cours) : {wins / len(results):.0%} "
            f"gagnants, moyenne {sum(results) / len(results):+.2f} R, total {sum(results):+.1f} R."
        )

    def log_sent(self, question: str, content: str, images: list[bytes] = ()) -> int:
        hashes = ",".join(hashlib.sha256(image).hexdigest() for image in images)
        with self._lock:
            cursor = self._db.execute(
                "INSERT INTO sent (sent_at, question, content, chars, images)"
                " VALUES (?, ?, ?, ?, ?)",
                (_now(), question, content, len(content), hashes),
            )
            self._db.commit()
        return cursor.lastrowid

    def log_answer(self, sent_id: int, answer: str) -> None:
        with self._lock:
            self._db.execute("UPDATE sent SET answer = ? WHERE id = ?", (answer, sent_id))
            self._db.commit()

    def sent_count(self) -> int:
        with self._lock:
            return self._db.execute("SELECT COUNT(*) FROM sent").fetchone()[0]

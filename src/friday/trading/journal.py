"""Journal de trading local (data/trading.db) : les trades, et la trace de chaque envoi à
Claude (ce qui est parti, quand, empreinte des images). Rien de ce fichier ne part en ligne ;
seul un résumé anonyme (`summary`) peut être joint à une analyse, via l'aperçu."""

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from friday.trading.risk_calc import result_in_r
from friday.trading.sent_log import SentLog

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
    result_r REAL,                 -- résultat en multiples du risque initial
    setup TEXT NOT NULL DEFAULT '', -- le setup utilisé (« repli EMA50 »…)
    plan_ok INTEGER,               -- plan respecté ? 1 / 0 / NULL (non dit)
    mood TEXT NOT NULL DEFAULT ''  -- état d'esprit à l'entrée
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
    setup: str = ""
    plan_ok: bool | None = None
    mood: str = ""
    capture: str | None = None
    closed_at: str | None = None


@dataclass
class Stats:
    closed: int
    open: int
    wins: int
    average_r: float | None
    total_r: float

    @property
    def win_rate(self) -> float | None:
        return self.wins / self.closed if self.closed else None


# Colonnes ajoutées après coup : un journal plus ancien les reçoit à l'ouverture
ADDED = {"setup": "TEXT NOT NULL DEFAULT ''", "plan_ok": "INTEGER",
         "mood": "TEXT NOT NULL DEFAULT ''"}  # fmt: skip
FIELDS = (
    "id, opened_at, pair, direction, entry, stop, target, lots, reason, exit, result_r, "
    "setup, plan_ok, mood, capture, closed_at"
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class TradeJournal(SentLog):
    def __init__(self, path: Path | str) -> None:
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._lock = threading.Lock()
        self.version = 0  # augmente à chaque changement : l'écran du journal se rafraîchit
        with self._lock:
            self._db.executescript(SCHEMA)
            known = {row[1] for row in self._db.execute("PRAGMA table_info(trades)")}
            for column, kind in ADDED.items():
                if column not in known:
                    self._db.execute(f"ALTER TABLE trades ADD COLUMN {column} {kind}")
            self._db.commit()

    def open_trade(
        self, pair: str, direction: str, entry: float, stop: float,
        target: float | None = None, lots: float | None = None, reason: str = "",
        setup: str = "", plan_ok: bool | None = None, mood: str = "",
    ) -> Trade:  # fmt: skip
        with self._lock:
            cursor = self._db.execute(
                "INSERT INTO trades (opened_at, pair, direction, entry, stop, target, lots, reason,"
                " setup, plan_ok, mood) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (_now(), pair.upper(), direction, entry, stop, target, lots, reason,
                 setup.strip(), plan_ok, mood.strip()),
            )  # fmt: skip
            self._db.commit()
            self.version += 1
        return self.get(cursor.lastrowid)

    def annotate(self, trade_id: int, **fields) -> Trade | None:
        """Complète un trade après coup : setup, plan_ok, mood, capture (chemin local)."""
        allowed = {k: v for k, v in fields.items()
                   if k in ("setup", "plan_ok", "mood", "capture") and v is not None}  # fmt: skip
        if not allowed or self.get(trade_id) is None:
            return self.get(trade_id)
        for key in ("setup", "mood"):
            if key in allowed:
                allowed[key] = str(allowed[key]).strip()
        with self._lock:
            self._db.execute(f"UPDATE trades SET {', '.join(f'{k} = ?' for k in allowed)}"
                             " WHERE id = ?", (*allowed.values(), trade_id))  # fmt: skip
            self._db.commit()
            self.version += 1
        return self.get(trade_id)

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
            self.version += 1
        return self.get(trade_id)

    def delete_trade(self, trade_id: int) -> bool:
        with self._lock:
            cursor = self._db.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
            self._db.commit()
            self.version += 1
        return cursor.rowcount > 0

    def all_trades(self) -> list[Trade]:
        """Tous les trades, les plus récents d'abord."""
        return self._trades("ORDER BY id DESC", ())

    def equity(self) -> list[tuple[int, str, float, float]]:
        """La courbe des résultats : (n°, instrument, résultat, cumul) de chaque trade clôturé,
        dans l'ordre de clôture."""
        with self._lock:
            rows = self._db.execute(
                "SELECT id, pair, result_r FROM trades WHERE result_r IS NOT NULL"
                " ORDER BY closed_at, id"
            ).fetchall()
        total, points = 0.0, []
        for trade_id, pair, result in rows:
            total += result
            points.append((trade_id, pair, result, total))
        return points

    def stats(self) -> Stats:
        with self._lock:
            results = [r for (r,) in self._db.execute(
                "SELECT result_r FROM trades WHERE result_r IS NOT NULL").fetchall()]  # fmt: skip
            open_count = self._db.execute(
                "SELECT COUNT(*) FROM trades WHERE result_r IS NULL"
            ).fetchone()[0]
        wins = sum(1 for r in results if r > 0)
        average = sum(results) / len(results) if results else None
        return Stats(len(results), open_count, wins, average, sum(results))

    def export_csv(self, path: Path) -> int:
        """Tous les trades en CSV pour Excel (journal_export.py) ; renvoie leur nombre."""
        from friday.trading.journal_export import export_csv

        return export_csv(list(reversed(self.all_trades())), path)

    def get(self, trade_id: int) -> Trade | None:
        rows = self._trades("WHERE id = ?", (trade_id,))
        return rows[0] if rows else None

    def recent(self, limit: int = 10) -> list[Trade]:
        return self._trades("ORDER BY id DESC LIMIT ?", (limit,))

    def _trades(self, where: str, params: tuple) -> list[Trade]:
        with self._lock:
            rows = self._db.execute(f"SELECT {FIELDS} FROM trades {where}", params).fetchall()
        trades = [Trade(*row) for row in rows]
        for trade in trades:
            trade.plan_ok = None if trade.plan_ok is None else bool(trade.plan_ok)
        return trades

    def review(self, now: datetime | None = None) -> str:
        """Bilan ANONYME détaillé : semaine, statistiques par catégorie, constats."""
        from friday.trading.journal_stats import review_text

        return review_text(self.all_trades(), self.summary(), now or datetime.now())

    def summary(self) -> str:
        """Bilan anonyme : nombre de trades, réussite, moyenne et total en R (aucun montant)."""
        s = self.stats()
        if not s.closed:
            return f"Aucun trade clôturé ({s.open} en cours)."
        return (
            f"{s.closed} trades clôturés ({s.open} en cours) : {s.win_rate:.0%} gagnants, "
            f"moyenne {s.average_r:+.2f} R, total {s.total_r:+.1f} R."
        )

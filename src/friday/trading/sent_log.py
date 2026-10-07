"""La trace de chaque envoi à Claude (table « sent » du journal) : le texte exact parti (déjà
masqué), quand, l'empreinte des images, et la réponse. Mêlée à TradeJournal (même base)."""

import hashlib
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Analysis:
    id: int
    sent_at: str
    question: str
    answer: str
    instrument: str | None
    price: float | None


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class SentLog:
    """Attend `self._db` (sqlite3) et `self._lock`, fournis par TradeJournal."""

    def log_sent(self, question: str, content: str, images: list[bytes] = (),
                 instrument: str | None = None, price: float | None = None) -> int:  # fmt: skip
        """`instrument`, `price` : de quoi parlait l'analyse, et le cours à ce moment (pour
        la comparer plus tard avec ce que le marché a fait)."""
        hashes = ",".join(hashlib.sha256(image).hexdigest() for image in images)
        with self._lock:
            cursor = self._db.execute(
                "INSERT INTO sent (sent_at, question, content, chars, images, instrument, price)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (_now(), question, content, len(content), hashes, instrument, price),
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

    def backfill_instruments(self) -> int:
        """Analyses d'avant la mémoire (sans instrument) : l'instrument est retrouvé dans la
        question (« l'or », « EUR/USD ») ; le cours d'alors reste inconnu. Une seule fois."""
        from friday.trading.instruments import detect

        with self._lock:
            rows = self._db.execute(
                "SELECT id, question FROM sent WHERE instrument IS NULL").fetchall()  # fmt: skip
            found = [(i.symbol, row_id) for row_id, question in rows if (i := detect(question))]
            self._db.executemany("UPDATE sent SET instrument = ? WHERE id = ?", found)
            self._db.execute("UPDATE sent SET instrument = '' WHERE instrument IS NULL")
            self._db.commit()
        return len(found)

    def analyses(self, symbol: str | None = None, limit: int = 5) -> list[Analysis]:
        """Les analyses de Claude (avec réponse), les plus récentes d'abord."""
        where, params = ("AND instrument = ?", (symbol,)) if symbol else ("", ())
        with self._lock:
            rows = self._db.execute(
                "SELECT id, sent_at, question, answer, instrument, price FROM sent"
                f" WHERE answer IS NOT NULL AND answer != '' {where} ORDER BY id DESC LIMIT ?",
                (*params, limit),
            ).fetchall()
        return [Analysis(*row) for row in rows]

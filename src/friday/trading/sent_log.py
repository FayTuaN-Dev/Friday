"""La trace de chaque envoi à Claude (table « sent » du journal) : le texte exact parti (déjà
masqué), quand, l'empreinte des images, et la réponse. Mêlée à TradeJournal (même base)."""

import hashlib
from datetime import datetime


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class SentLog:
    """Attend `self._db` (sqlite3) et `self._lock`, fournis par TradeJournal."""

    def log_sent(self, question: str, content: str, images: list[bytes] = ()) -> int:
        hashes = ",".join(hashlib.sha256(image).hexdigest() for image in images)
        with self._lock:
            cursor = self._db.execute(
                "INSERT INTO sent (sent_at, question, content, chars, images)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    datetime.now().isoformat(timespec="seconds"),
                    question,
                    content,
                    len(content),
                    hashes,
                ),
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

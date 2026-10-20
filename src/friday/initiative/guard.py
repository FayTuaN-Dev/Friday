"""Le garde-fou des initiatives : Friday ne parle d'elle-même ni pendant les heures calmes, ni
trop souvent, ni deux fois du même sujet (les sujets dits sont gardés dans un fichier, pour
qu'un redémarrage ne les fasse pas répéter)."""

import json
import logging
import re
import threading
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger(__name__)

FORGET_AFTER = timedelta(days=3)  # un sujet plus ancien ne reviendra plus : on l'oublie


def quiet_hours(value: str) -> tuple[int, int]:
    """« 23-7 », « 23 h - 7 h » → (23, 7) ; vide ou illisible : (23, 7). (0, 0) : jamais calme."""
    found = [int(n) for n in re.findall(r"\d{1,2}", value or "")]
    if len(found) >= 2 and all(0 <= n <= 24 for n in found[:2]):
        return found[0] % 24, found[1] % 24
    return 23, 7


def is_quiet(hours: tuple[int, int], now: datetime) -> bool:
    start, end = hours
    if start == end:
        return False
    if start < end:  # « 13-14 »
        return start <= now.hour < end
    return now.hour >= start or now.hour < end  # « 23-7 » : passe minuit


class Guard:
    def __init__(self, state: Path, quiet: tuple[int, int] = (23, 7), per_hour: int = 4) -> None:
        self.state, self.quiet, self.per_hour = state, quiet, per_hour
        self._lock = threading.Lock()
        self._said = self._load()
        self._spoken: list[datetime] = []  # quand Friday a pris la parole (limite par heure)

    def _load(self) -> dict[str, datetime]:
        try:
            raw = json.loads(self.state.read_text("utf-8"))
            return {key: datetime.fromisoformat(when) for key, when in raw.items()}
        except (OSError, ValueError, TypeError, AttributeError):
            return {}

    def _save(self) -> None:
        try:
            self.state.parent.mkdir(parents=True, exist_ok=True)
            data = {key: when.isoformat() for key, when in self._said.items()}
            self.state.write_text(json.dumps(data, ensure_ascii=False), "utf-8")
        except OSError:
            log.exception("Initiatives : sujets dits non enregistrés")

    def said(self, key: str) -> bool:
        return key in self._said

    def allow(self, keys: str | tuple[str, ...], now: datetime) -> bool:
        """Friday peut-elle parler de ce(s) sujet(s) maintenant ? Si oui, ils comptent comme
        dits (plusieurs sujets : plusieurs mails réunis dans une phrase)."""
        keys = (keys,) if isinstance(keys, str) else keys
        with self._lock:
            if any(k in self._said for k in keys) or is_quiet(self.quiet, now):
                return False
            self._spoken = [w for w in self._spoken if now - w < timedelta(hours=1)]
            recent = len(self._spoken)
            if recent >= self.per_hour:
                log.info("Initiative « %s » retenue : déjà %d cette heure", keys[0], recent)
                return False
            self._said = {k: w for k, w in self._said.items() if now - w < FORGET_AFTER}
            self._said.update(dict.fromkeys(keys, now))
            self._spoken.append(now)
            self._save()
            return True

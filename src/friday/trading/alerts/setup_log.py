"""Le carnet des setups (data/trading_setups.json) : chaque setup vu par la surveillance des
marchés, noté une seule fois (marché, sens, bougie), avec ses niveaux et l'annonce faite.
Un setup trouvé hors des heures de trading (ou PC éteint : la clôture d'une journée déjà
passée) attend d'être annoncé au retour, s'il est encore récent. C'est sur ce carnet que
Claude dira oui ou non (P3), et qu'on verra ce que chaque setup aurait donné."""

import json
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger(__name__)
KEEP = 500  # setups gardés au plus (les plus anciens partent)
STALE = timedelta(days=3)  # plus vieux, un setup n'est plus annoncé (le prix a bougé)
PENDING = "attente"  # l'avis de Claude est demandé
VERDICT_WAIT = timedelta(minutes=15)  # au-delà, le setup est annoncé sans son avis


class SetupLog:
    def __init__(self, path: Path | None) -> None:
        self.path, self._lock = path, threading.Lock()
        self._entries: list[dict] = self._load()

    def all(self) -> list[dict]:
        with self._lock:
            return [dict(e) for e in self._entries]

    def add(self, symbol: str, setup, text: str, seen: datetime) -> dict | None:
        """Le setup noté ; None s'il l'était déjà (même marché, même sens, même bougie)."""
        strategy = setup.strategy
        entry = {
            "symbol": symbol, "side": setup.side, "bar": setup.bar.time.isoformat(),
            "close": setup.bar.close, "stop": setup.stop, "target": setup.target,
            "trail": setup.trail, "strategy": getattr(strategy, "name", ""),
            "label": getattr(strategy, "label", ""), "unit": getattr(strategy, "unit", "heure"),
            "text": text, "seen": seen.isoformat(), "announced": False,
            "avis": None, "raison": "", "closed": None, "result_r": None,
        }  # fmt: skip
        with self._lock:
            if any(e["symbol"] == symbol and e["side"] == setup.side and e["bar"] == entry["bar"]
                   for e in self._entries):  # fmt: skip
                return None
            entry["id"] = max((e["id"] for e in self._entries), default=0) + 1
            self._entries = [*self._entries, entry][-KEEP:]
        self._save()
        return dict(entry)

    def waiting(self, now: datetime) -> list[dict]:
        """Les setups pas encore annoncés et encore récents ; ceux dont l'avis de Claude est
        attendu patientent (VERDICT_WAIT au plus)."""
        return [e for e in self.all() if not e["announced"]
                and now - datetime.fromisoformat(e["seen"]) <= STALE
                and (e.get("avis") != PENDING
                     or now - datetime.fromisoformat(e["seen"]) > VERDICT_WAIT)]  # fmt: skip

    def update(self, entry_id: int, **fields) -> None:
        with self._lock:
            for entry in self._entries:
                if entry["id"] == entry_id:
                    entry.update(fields)
        self._save()

    def mark_announced(self, ids: list[int]) -> None:
        with self._lock:
            for entry in self._entries:
                if entry["id"] in ids:
                    entry["announced"] = True
        self._save()

    def _load(self) -> list[dict]:
        if self.path is None or not self.path.is_file():
            return []
        try:
            data = json.loads(self.path.read_text("utf-8"))
            return [e for e in data if isinstance(e, dict) and "id" in e]
        except (OSError, ValueError):
            log.warning("Carnet des setups illisible (%s) : on repart de zéro", self.path)
            return []

    def _save(self) -> None:
        if self.path is None:
            return
        with self._lock:
            text = json.dumps(self._entries, indent=1, ensure_ascii=False)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(text, "utf-8")

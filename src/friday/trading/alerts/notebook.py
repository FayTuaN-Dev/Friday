"""Ce que la surveillance fait de chaque setup trouvé : le noter au carnet (setup_log.py),
demander l'avis de Claude s'il est activé (setup_verdict.py, un à la fois, hors du fil de la
surveillance), suivre ce que le trade aurait donné (outcome.py), et préparer l'annonce."""

import logging
import queue
import threading
from collections.abc import Callable
from datetime import datetime

from friday.trading.alerts.outcome import follow
from friday.trading.alerts.setup_log import PENDING, SetupLog
from friday.trading.backtest.spread import spread_of
from friday.trading.instruments import Instrument

log = logging.getLogger(__name__)


class Notebook:
    def __init__(self, setups: SetupLog, now: Callable[[], datetime]) -> None:
        self.setups, self.now = setups, now
        self.judge = None  # SetupJudge : l'avis de Claude (s'il est activé)
        self._queue: queue.Queue = queue.Queue()

    def note(self, instrument: Instrument, found, text: str, now: datetime) -> None:
        """Le setup au carnet ; avec l'avis de Claude demandé s'il est activé."""
        entry = self.setups.add(instrument.symbol, found, text, now)
        if entry is not None and self.judge is not None and self.judge.reserve(now):
            self.setups.update(entry["id"], avis=PENDING)
            self._queue.put((entry, instrument))

    def judge_one(self, entry: dict, instrument: Instrument) -> None:
        found = self.judge.judge(entry, instrument, self.now())
        avis, raison = found if found else (None, "")
        self.setups.update(entry["id"], avis=avis, raison=raison)

    def run(self, stop: threading.Event) -> None:
        """Les avis demandés, un par un (fil « setup-avis »)."""
        while not stop.is_set():
            entry, instrument = self._queue.get()
            try:
                self.judge_one(entry, instrument)
            except Exception:
                log.exception("Avis de Claude sur un setup impossible")
                self.setups.update(entry["id"], avis=None)

    def follow(self, instrument: Instrument, bars, unit: str) -> None:
        """Ce que les setups encore ouverts de ce marché auraient donné, sur ces bougies."""
        if not bars:
            return
        spread = spread_of(instrument, bars[-1].close)
        for entry in self.setups.all():
            if (entry["symbol"] == instrument.symbol and entry["unit"] == unit
                    and entry["result_r"] is None):  # fmt: skip
                done = follow(entry, bars, spread)
                if done is not None:
                    self.setups.update(entry["id"], closed=done[0], result_r=done[1])

    def announcement(self) -> str | None:
        """Les setups pas encore annoncés, en une seule annonce (puis marqués annoncés)."""
        waiting = self.setups.waiting(self.now())
        if not waiting:
            return None
        texts = [e["text"] + verdict_text(e) for e in waiting]
        head = f"{len(texts)} setups depuis ma dernière annonce. " if len(texts) > 1 else ""
        self.setups.mark_announced([e["id"] for e in waiting])
        return head + " ".join(texts)


def verdict_text(entry: dict) -> str:
    """L'avis de Claude ajouté à l'annonce (s'il a été demandé)."""
    if entry.get("avis") in ("oui", "non"):
        word = "OUI" if entry["avis"] == "oui" else "NON"
        return f" Avis de Claude : {word}. {entry.get('raison', '')}".rstrip()
    if entry.get("avis") == PENDING:
        return " L'avis de Claude n'est pas encore arrivé."
    return ""

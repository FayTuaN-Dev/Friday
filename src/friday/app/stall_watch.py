"""Détecteur de blocage : si une demande attend trop longtemps d'être traitée, l'état de tous
les fils d'exécution est écrit dans logs/blocage-<heure>.txt (la ligne exacte où Friday est
coincée), pour corriger la vraie cause au lieu de la deviner."""

import faulthandler
import logging
import threading
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

WAIT_LIMIT = 30.0  # secondes qu'une demande peut attendre avant qu'on enquête


class StallWatch:
    def __init__(self, waiting_since: Callable[[], float | None], folder: Path,
                 limit: float = WAIT_LIMIT, every: float = 5.0) -> None:  # fmt: skip
        """`waiting_since` : depuis quand la plus ancienne demande attend (None : aucune)."""
        self.waiting_since = waiting_since
        self.folder = folder
        self.limit = limit
        self.every = every
        self._reported: float | None = None  # demande déjà signalée (une fois suffit)
        self.reports: list[Path] = []
        threading.Thread(target=self._loop, daemon=True, name="stall-watch").start()

    def _loop(self) -> None:
        while True:
            time.sleep(self.every)
            self.check()

    def check(self) -> Path | None:
        since = self.waiting_since()
        if since is None or time.monotonic() - since < self.limit or since == self._reported:
            return None
        self._reported = since
        self.folder.mkdir(parents=True, exist_ok=True)
        path = self.folder / f"blocage-{datetime.now():%Y%m%d-%H%M%S}.txt"
        with path.open("w", encoding="utf-8") as file:
            file.write(f"Une demande attend depuis {time.monotonic() - since:.0f} s.\n\n")
            file.flush()
            faulthandler.dump_traceback(file, all_threads=True)
        log.warning("Friday semble bloquée : état des fils écrit dans %s", path)
        self.reports.append(path)
        return path

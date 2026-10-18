"""Lit les performances du PC hors du fil de l'interface, seulement quand on le lui demande :
les cartes le demandent toutes les 2 s tant qu'elles sont affichées. Fenêtre cachée, réduite
ou mode jeu : plus aucune lecture (rien ne vole de puissance aux jeux)."""

import atexit
import logging
import threading
import weakref

from PySide6.QtCore import QObject, Signal

from friday.app.pc_stats import PcStats

log = logging.getLogger(__name__)
_SAMPLERS: "weakref.WeakSet[Sampler]" = weakref.WeakSet()


@atexit.register
def _stop_all() -> None:
    """Comme now_playing.py : un fil qui émet pendant que Qt se ferme fait planter Python."""
    for sampler in list(_SAMPLERS):
        sampler.stop()


class Sampler(QObject):
    read = Signal(object)  # Snapshot

    def __init__(self, stats: PcStats | None = None) -> None:
        super().__init__()
        self.stats = stats
        self._wanted, self._stop = threading.Event(), threading.Event()
        _SAMPLERS.add(self)
        self._thread = threading.Thread(target=self._loop, daemon=True, name="pc-stats")
        self._thread.start()

    def request(self) -> None:
        """Une lecture, dès que possible (une seule à la fois : les demandes se fondent)."""
        self._wanted.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._wanted.wait()
            self._wanted.clear()
            if self._stop.is_set():
                return
            try:
                self.stats = self.stats or PcStats()
                snapshot = self.stats.read()
            except Exception:
                log.exception("Lecture des performances du PC impossible")
                continue
            try:
                self.read.emit(snapshot)
            except RuntimeError:  # la carte n'est plus là
                return

    def stop(self) -> None:
        self._stop.set()
        self._wanted.set()

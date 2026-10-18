"""Lit hors du fil de l'interface, seulement quand on le lui demande : les cartes le demandent
à intervalle régulier tant qu'elles sont affichées. Fenêtre cachée, réduite ou mode jeu : plus
aucune lecture (rien ne vole de puissance aux jeux). Par défaut : les performances du PC."""

import atexit
import logging
import threading
import weakref
from collections.abc import Callable

from PySide6.QtCore import QObject, Signal

log = logging.getLogger(__name__)
_SAMPLERS: "weakref.WeakSet[Sampler]" = weakref.WeakSet()


@atexit.register
def _stop_all() -> None:
    """Comme now_playing.py : un fil qui émet pendant que Qt se ferme fait planter Python."""
    for sampler in list(_SAMPLERS):
        sampler.stop()


def pc_reader() -> Callable[[], object]:
    from friday.app.pc_stats import PcStats

    return PcStats().read


class Sampler(QObject):
    read = Signal(object)  # ce que le lecteur a lu (Snapshot du PC, Status de Friday…)

    def __init__(self, make: Callable[[], Callable[[], object]] = pc_reader,
                 name: str = "pc-stats") -> None:  # fmt: skip
        """`make()` donne le lecteur : appelé dans le fil, à la 1re lecture (rien au démarrage)."""
        super().__init__()
        self._make, self._reader = make, None
        self._wanted, self._stop = threading.Event(), threading.Event()
        self._name, self._thread = name, None
        _SAMPLERS.add(self)

    def request(self) -> None:
        """Une lecture, dès que possible (une seule à la fois : les demandes se fondent). Le
        fil ne démarre qu'à la 1re demande : jamais en fenêtre normale (cartes cachées)."""
        if self._stop.is_set():
            return
        if self._thread is None:
            self._thread = threading.Thread(target=self._loop, daemon=True, name=self._name)
            self._thread.start()
        self._wanted.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._wanted.wait()
            self._wanted.clear()
            if self._stop.is_set():
                return
            try:
                self._reader = self._reader or self._make()
                found = self._reader()
            except Exception:
                log.exception("Lecture pour les cartes de côté impossible")
                continue
            try:
                self.read.emit(found)
            except RuntimeError:  # la carte n'est plus là
                return

    def stop(self) -> None:
        self._stop.set()
        self._wanted.set()

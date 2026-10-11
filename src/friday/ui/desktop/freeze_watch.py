"""Guetteur d'à-coups : un minuteur qui devrait sonner toutes les 100 ms ; s'il sonne bien
plus tard, l'interface était figée (création d'une scène, du moteur web…) : on le note dans
le journal, avec l'heure, pour relier un à-coup ressenti à sa cause."""

import logging
import time

from PySide6.QtCore import QObject, QTimer

log = logging.getLogger(__name__)

EVERY_MS = 100
FROZEN_MS = 250  # au-delà : à-coup visible


class FreezeWatch(QObject):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.worst = 0.0  # le plus long gel vu (ms), pour le diagnostic
        self._last = time.monotonic()
        self._timer = QTimer(self, interval=EVERY_MS, timeout=self._tick)
        self._timer.start()

    def _tick(self) -> None:
        now = time.monotonic()
        late = (now - self._last) * 1000 - EVERY_MS
        self._last = now
        if late > FROZEN_MS:
            self.worst = max(self.worst, late)
            log.warning("Interface figée %.0f ms", late)

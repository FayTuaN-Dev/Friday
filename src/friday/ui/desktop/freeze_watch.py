"""Guetteur d'à-coups : un minuteur qui devrait sonner toutes les 100 ms ; s'il sonne bien
plus tard, l'interface était figée : on le note dans le journal. Pendant le gel, un petit fil
de surveillance photographie où en est le fil de l'interface (fichier, fonction, ligne) :
le journal dit QUOI figeait Friday, pas seulement combien de temps.

Le fil de surveillance ne touche qu'un « pouls » en Python pur, jamais l'objet Qt : s'il en
tenait la dernière référence, Python le détruirait depuis ce fil (constaté : Qt plante). La
pile est lue par faulthandler (fait pour ça, sans toucher aux objets Python) : la lire avec
sys._current_frames depuis ce fil faisait planter Qt (constaté, Python 3.12)."""

import faulthandler
import logging
import re
import tempfile
import threading
import time
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, QTimer

log = logging.getLogger(__name__)

EVERY_MS = 100
FROZEN_MS = 250  # au-delà : à-coup visible
LOOK_EVERY = 0.05  # le fil de surveillance regarde toutes les 50 ms
FRAMES = 6  # étapes de la pile notées (les plus proches du blocage)


THREAD = re.compile(r"^(?:Current thread|Thread) (0x[0-9a-fA-F]+)", re.M)
STEP = re.compile(r'File "([^"]+)", line (\d+) in (\S+)')


def where(gui: int) -> str:
    """« friday/tools/x.py:42 run ← … » : où en est le fil de l'interface (les étapes du code
    de Friday d'abord), lu par faulthandler."""
    with tempfile.TemporaryFile("w+", encoding="utf-8") as dump:
        faulthandler.dump_traceback(dump, all_threads=True)
        dump.seek(0)
        text = dump.read()
    marks = list(THREAD.finditer(text))
    for n, mark in enumerate(marks):
        if int(mark.group(1), 16) != gui:
            continue
        block = text[mark.end() : marks[n + 1].start() if n + 1 < len(marks) else len(text)]
        steps = STEP.findall(block)  # du plus récent au plus ancien
        ours = [s for s in steps if "/friday/" in s[0].replace("\\", "/").lower()] or steps
        return " ← ".join(f"{path.replace(chr(92), '/').split('/src/')[-1]}:{line} {name}"
                          for path, line, name in ours[:FRAMES])  # fmt: skip
    return "(fil de l'interface introuvable)"


@dataclass
class Pulse:
    """Ce que partagent l'interface (elle bat) et le fil de surveillance (il regarde)."""

    gui: int  # identifiant du fil de l'interface
    last: float = field(default_factory=time.monotonic)
    stop: threading.Event = field(default_factory=threading.Event)
    culprits: list[str] = field(default_factory=list)  # où l'interface était figée


def _look(pulse: Pulse) -> None:
    """Dans un autre fil : si l'interface ne bat plus, d'où ne revient-elle pas ?"""
    seen = 0.0  # le gel déjà photographié (son début)
    while not pulse.stop.wait(LOOK_EVERY):
        started = pulse.last
        if (time.monotonic() - started) * 1000 < EVERY_MS + FROZEN_MS or started == seen:
            continue
        seen = started
        culprit = where(pulse.gui)
        pulse.culprits[:] = (pulse.culprits + [culprit])[-20:]
        log.warning("Gel en cours, l'interface est dans : %s", culprit)


class FreezeWatch(QObject):
    def __init__(self, parent: QObject | None = None, sample: bool = True) -> None:
        super().__init__(parent)
        self.worst = 0.0  # le plus long gel vu (ms), pour le diagnostic
        self.pulse = Pulse(threading.get_ident())
        self._timer = QTimer(self, interval=EVERY_MS, timeout=self._tick)
        self._timer.start()
        if sample:
            threading.Thread(target=_look, args=(self.pulse,), daemon=True,
                             name="freeze-watch").start()  # fmt: skip
            self.destroyed.connect(self.pulse.stop.set)

    @property
    def culprits(self) -> list[str]:
        return self.pulse.culprits

    def _tick(self) -> None:
        now = time.monotonic()
        late = (now - self.pulse.last) * 1000 - EVERY_MS
        self.pulse.last = now
        if late > FROZEN_MS:
            self.worst = max(self.worst, late)
            log.warning("Interface figée %.0f ms", late)

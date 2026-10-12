"""Guetteur d'à-coups : un minuteur qui devrait sonner toutes les 100 ms ; s'il sonne bien
plus tard, l'interface était figée : on le note dans le journal, avec ce que faisaient TOUS
les fils pendant le gel.

La photo est prise par faulthandler.dump_traceback_later, une minuterie écrite en C, réarmée à
chaque battement de l'interface : si l'interface ne revient pas à temps, elle écrit la pile
de tous les fils SANS avoir besoin du verrou de Python. Constaté : un mouchard en Python ne
pouvait pas tourner pendant qu'un autre fil gardait ce verrou, et photographiait trop tard
(il désignait des innocents)."""

import faulthandler
import logging
import re
import tempfile
import threading
import time

from PySide6.QtCore import QObject, QTimer

log = logging.getLogger(__name__)

EVERY_MS = 100
FROZEN_MS = 250  # au-delà : à-coup visible
PHOTO_AFTER = 0.35  # secondes sans battement : la minuterie photographie tous les fils
FRAMES = 4  # étapes notées par fil
THREAD = re.compile(r"^(?:Current thread|Thread) (0x[0-9a-fA-F]+)", re.M)
STEP = re.compile(r'File "([^"]+)", line (\d+) in (\S+)')
# Un fil qui attend (file, minuterie, réseau…) n'est pas un coupable
IDLE = {"wait", "get", "sleep", "select", "_poll", "accept", "recv", "readinto", "read", "join",
        "_wait_for_tstate_lock", "run_forever", "_run_once", "poll", "wait_for"}  # fmt: skip


def _short(path: str, line: str, name: str) -> str:
    path = path.replace(chr(92), "/").split("/src/")[-1].split("site-packages/")[-1]
    return f"{path}:{line} {name}"


def threads_in(text: str) -> dict[int, list[tuple[str, str, str]]]:
    """La photo de faulthandler → {fil : étapes, de la plus récente à la plus ancienne}."""
    marks = list(THREAD.finditer(text))
    found = {}
    for n, mark in enumerate(marks):
        block = text[mark.end() : marks[n + 1].start() if n + 1 < len(marks) else len(text)]
        found[int(mark.group(1), 16)] = STEP.findall(block)
    return found


def describe(steps: list[tuple[str, str, str]]) -> str:
    """L'étape en cours, puis les étapes du code de Friday qui y mènent."""
    if not steps:
        return ""
    ours = [s for s in steps[1:] if "/friday/" in s[0].replace(chr(92), "/").lower()]
    return " ← ".join(_short(*s) for s in [steps[0], *ours][:FRAMES])


def summary(text: str, gui: int, names: dict[int, str]) -> tuple[str, list[str]]:
    """(où était l'interface, ce que faisaient les autres fils qui ne dormaient pas)."""
    threads = threads_in(text)
    interface = describe(threads.get(gui, [])) or "(introuvable)"
    busy = [f"{names.get(ident, hex(ident))} : {describe(steps)}"
            for ident, steps in threads.items()
            if ident != gui and steps and steps[0][2] not in IDLE]  # fmt: skip
    return interface, busy


class FreezeWatch(QObject):
    def __init__(self, parent: QObject | None = None, sample: bool = True) -> None:
        super().__init__(parent)
        self.worst = 0.0  # le plus long gel vu (ms), pour le diagnostic
        self.culprits: list[str] = []  # ce que faisaient les fils pendant les derniers gels
        self._last = time.monotonic()
        self._gui = threading.get_ident()
        self._photos = tempfile.TemporaryFile("w+", encoding="utf-8") if sample else None
        self._read = 0  # ce qui a déjà été lu dans les photos
        self._timer = QTimer(self, interval=EVERY_MS, timeout=self._tick)
        self._timer.start()
        self._arm()
        self.destroyed.connect(faulthandler.cancel_dump_traceback_later)

    def _arm(self) -> None:
        if self._photos is not None:
            faulthandler.dump_traceback_later(PHOTO_AFTER, file=self._photos)

    def _tick(self) -> None:
        now = time.monotonic()
        late = (now - self._last) * 1000 - EVERY_MS
        self._last = now
        if late > FROZEN_MS:
            self.worst = max(self.worst, late)
            log.warning("Interface figée %.0f ms", late)
        self._read_photo()
        self._arm()  # réarmée : elle ne se déclenche que si l'interface ne revient pas

    def _read_photo(self) -> None:
        if self._photos is None:
            return
        self._photos.flush()
        self._photos.seek(self._read)
        text = self._photos.read()
        self._read = self._photos.tell()
        if not text.strip():
            return
        names = {t.ident: t.name for t in threading.enumerate()}
        interface, busy = summary(text, self._gui, names)
        self.culprits = (self.culprits + [interface, *busy])[-30:]
        log.warning("Gel : l'interface était dans %s", interface)
        for line in busy:
            log.warning("   pendant ce temps, %s", line)

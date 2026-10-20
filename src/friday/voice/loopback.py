"""Le son du PC (ce que jouent les haut-parleurs ou le casque), capté en « loopback » WASAPI
avec la bibliothèque soundcard : une vidéo, un appel… Pour l'interprète (D2).
Rien n'est enregistré sur le disque : l'audio passe directement à la détection de parole."""

import logging
import threading
from collections.abc import Callable

import numpy as np

from friday.voice.recorder import resample

log = logging.getLogger(__name__)

RATE = 48_000
BLOCK = RATE // 10  # 100 ms


def pick_speaker(speakers: list, wanted: str, default):
    """La sortie demandée (son nom, ou son début : les noms MME sont coupés à 31 caractères),
    sinon celle de Windows."""
    wanted = wanted.strip().lower()
    if wanted:
        for speaker in speakers:
            name = speaker.name.lower()
            if name.startswith(wanted) or wanted in name:
                return speaker
        log.warning("Sortie audio « %s » introuvable : celle de Windows", wanted)
    return default


class Loopback:
    def __init__(self, on_audio: Callable[[np.ndarray], None], device: str = "") -> None:
        self.on_audio = on_audio  # audio 16 kHz mono, par blocs de 100 ms
        self.device = device
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="son du PC")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        import ctypes
        import sys

        try:
            # soundcard prépare COM au premier import, dans le fil qui l'importe ; un autre fil
            # doit le faire lui-même (le faire avant l'import le fait échouer : constaté)
            imported = "soundcard" in sys.modules
            import soundcard as sc

            if imported:
                ctypes.windll.ole32.CoInitializeEx(None, 0)

            speaker = pick_speaker(sc.all_speakers(), self.device, sc.default_speaker())
            source = sc.get_microphone(speaker.id, include_loopback=True)
            log.info("Interprète : écoute de « %s »", speaker.name)
            with source.recorder(samplerate=RATE, channels=1, blocksize=BLOCK) as recorder:
                while not self._stop.is_set():
                    block = recorder.record(numframes=BLOCK)
                    self.on_audio(resample(np.asarray(block)[:, 0], RATE))
        except Exception:
            log.exception("Son du PC impossible à capter")

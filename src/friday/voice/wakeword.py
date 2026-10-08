"""Mot d'activation dédié (openWakeWord) : un petit modèle « Friday » (data/models/friday.onnx,
entraîné une fois : docs/mot-activation.md) écoute en continu sur le processeur. Whisper ne
transcrit plus que les phrases où il a entendu « Friday » (ou une relance attendue) : moins
de faux déclenchements, moins de calcul. Sans le fichier, l'écoute reste celle d'avant.

Tout est local : seuls les petits modèles audio publics d'openWakeWord sont téléchargés une
fois s'ils manquent."""

import logging
import queue
import threading
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

FRAME = 1280  # 80 ms à 16 kHz : ce qu'attend openWakeWord
THRESHOLD = 0.5


def load_model(path: Path):
    from openwakeword.model import Model

    try:
        return Model(wakeword_models=[str(path)], inference_framework="onnx")
    except Exception:  # modèles audio communs absents : téléchargés une fois (publics)
        from openwakeword.utils import download_models

        download_models()
        return Model(wakeword_models=[str(path)], inference_framework="onnx")


class WakeWordDetector:
    def __init__(
        self, model, threshold: float = THRESHOLD,
        clock: Callable[[], float] = time.monotonic, background: bool = True,
    ) -> None:  # fmt: skip
        """`model` : un Model openWakeWord (ou un double : predict(trame) → {nom: score})."""
        self.model, self.threshold, self.clock = model, threshold, clock
        self.last = float("-inf")  # moment de la dernière détection
        self.best = 0.0  # meilleur score récent (diagnostic)
        self._buffer = np.zeros(0, dtype=np.int16)
        self._queue: queue.Queue[np.ndarray | None] | None = None
        if background:
            self._queue = queue.Queue(maxsize=200)
            threading.Thread(target=self._loop, daemon=True, name="wake-word").start()

    def feed(self, audio: np.ndarray) -> None:
        """Audio 16 kHz en flottants (-1…1), depuis le flux du micro."""
        pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
        if self._queue is None:
            self._process(pcm)
            return
        try:
            self._queue.put_nowait(pcm)
        except queue.Full:  # le processeur est saturé : on saute un bout plutôt que bloquer
            pass

    def heard_since(self, moment: float) -> bool:
        return self.last >= moment

    def _process(self, pcm: np.ndarray) -> None:
        self._buffer = np.concatenate([self._buffer, pcm])
        while len(self._buffer) >= FRAME:
            frame, self._buffer = self._buffer[:FRAME], self._buffer[FRAME:]
            score = max(self.model.predict(frame).values(), default=0.0)
            self.best = max(self.best * 0.99, score)
            if score >= self.threshold:
                if self.clock() - self.last > 1.0:
                    log.info("Mot d'activation entendu (score %.2f)", score)
                self.last = self.clock()

    def _loop(self) -> None:
        while (pcm := self._queue.get()) is not None:
            try:
                self._process(pcm)
            except Exception:
                log.exception("Erreur du mot d'activation")

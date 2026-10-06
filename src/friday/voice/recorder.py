"""Enregistrement du micro entre start() et stop()."""

import logging
import threading
from collections.abc import Callable

import numpy as np
import sounddevice as sd

from friday.voice.devices import resolve_device

log = logging.getLogger(__name__)

WHISPER_RATE = 16_000


def resample(audio: np.ndarray, src_rate: int, dst_rate: int = WHISPER_RATE) -> np.ndarray:
    if src_rate == dst_rate or audio.size == 0:
        return audio.astype(np.float32)
    n = int(audio.size * dst_rate / src_rate)
    positions = np.linspace(0, audio.size - 1, n)
    return np.interp(positions, np.arange(audio.size), audio).astype(np.float32)


class Recorder:
    def __init__(
        self, device: int | str | None = None, on_level: Callable[[float], None] | None = None
    ) -> None:
        self.device = resolve_device(device, "input")  # un seul micro, même nom en triple
        self._on_level = on_level  # niveau sonore (0 à 1) toutes les ~20 ms, pour l'animation
        # On enregistre à la fréquence native du micro puis on convertit en 16 kHz pour Whisper.
        self.sample_rate = int(sd.query_devices(self.device, kind="input")["default_samplerate"])
        self._frames: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._stream: sd.InputStream | None = None

    def start(self) -> None:
        self._frames = []
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            device=self.device,
            channels=1,
            dtype="float32",
            blocksize=self.sample_rate // 50,
            callback=self._on_audio,
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        """Arrête l'enregistrement et renvoie l'audio en 16 kHz mono."""
        if self._stream is None:
            return np.zeros(0, dtype=np.float32)
        self._stream.stop()
        self._stream.close()
        self._stream = None
        with self._lock:
            audio = np.concatenate(self._frames)[:, 0] if self._frames else np.zeros(0)
        return resample(audio, self.sample_rate)

    def _on_audio(self, data: np.ndarray, frames: int, time, status) -> None:
        if status:
            log.debug("Micro : %s", status)
        with self._lock:
            self._frames.append(data.copy())
        if self._on_level:
            rms = float(np.sqrt(np.mean(data**2)))
            self._on_level(min(1.0, rms * 8))

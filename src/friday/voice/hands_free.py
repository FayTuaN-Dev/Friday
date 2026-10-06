"""Écoute en continu (mains libres) : micro → phrases (VAD) → texte (Whisper) → rappel."""

import logging
import queue
import threading
from collections.abc import Callable

import numpy as np
import sounddevice as sd

from friday.voice.devices import resolve_device
from friday.voice.recorder import WHISPER_RATE, resample
from friday.voice.vad import SpeechSegmenter, StreamingVAD

log = logging.getLogger(__name__)


class HandsFreeListener:
    def __init__(
        self,
        transcribe: Callable[[np.ndarray], str],
        on_heard: Callable[[str, float], None],  # (texte, moment où la phrase a commencé)
        device: int | str | None = None,
        silence_ms: int = 700,
        heard_log=None,  # HeardLog : diagnostic, garde l'audio des phrases entendues
    ) -> None:
        self._transcribe = transcribe
        self._heard_log = heard_log
        self._on_heard = on_heard
        self.device = resolve_device(device, "input")  # un seul micro, même nom en triple
        self.sample_rate = int(sd.query_devices(self.device, kind="input")["default_samplerate"])
        self.segmenter = SpeechSegmenter(StreamingVAD(), self._segments_put, silence_ms=silence_ms)
        self._segments: queue.Queue[tuple[np.ndarray, float] | None] = queue.Queue()
        self._paused = threading.Event()
        self._stream: sd.InputStream | None = None

    def start(self) -> None:
        threading.Thread(target=self._transcribe_loop, daemon=True, name="hands-free").start()
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            device=self.device,
            channels=1,
            dtype="float32",
            blocksize=self.sample_rate // 50,  # blocs de 20 ms
            callback=self._on_audio,
        )
        self._stream.start()
        log.info("Écoute mains libres active")

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self._segments.put(None)

    def pause(self) -> None:
        """Pendant le push-to-talk, l'écoute continue s'efface."""
        self._paused.set()

    def resume(self) -> None:
        self.segmenter.reset()
        self._paused.clear()

    # --- Threads ---

    def _on_audio(self, data: np.ndarray, frames: int, time, status) -> None:
        if self._paused.is_set():
            return
        try:
            self.segmenter.feed(resample(data[:, 0], self.sample_rate, WHISPER_RATE))
        except Exception:
            log.exception("Erreur de détection de parole")

    def _segments_put(self, segment: np.ndarray) -> None:
        self._segments.put((segment, self.segmenter.started_at))

    def _transcribe_loop(self) -> None:
        while (item := self._segments.get()) is not None:
            segment, started_at = item
            try:
                text = self._transcribe(segment)
                if self._heard_log:
                    self._heard_log.save(segment, text)
                if text:
                    log.info("Entendu : %s", text)
                    self._on_heard(text, started_at)
            except Exception:
                log.exception("Erreur de transcription en continu")

"""Détection de parole en continu (VAD) : découpe le flux du micro en phrases."""

import time
from collections import deque
from collections.abc import Callable

import numpy as np

FRAME = 512  # échantillons par trame à 16 kHz (32 ms), taille attendue par Silero
FRAME_MS = 32
CONTEXT = 64


class StreamingVAD:
    """Silero VAD (modèle fourni avec faster-whisper), avec sa mémoire conservée entre trames."""

    def __init__(self) -> None:
        from faster_whisper.vad import get_vad_model

        self._session = get_vad_model().session
        self.reset()

    def reset(self) -> None:
        self._h = np.zeros((1, 1, 128), dtype=np.float32)
        self._c = np.zeros((1, 1, 128), dtype=np.float32)
        self._context = np.zeros(CONTEXT, dtype=np.float32)

    def __call__(self, frame: np.ndarray) -> float:
        """Probabilité (0 à 1) que la trame contienne de la parole."""
        x = np.concatenate([self._context, frame])[None, :]
        out, self._h, self._c = self._session.run(None, {"input": x, "h": self._h, "c": self._c})
        self._context = frame[-CONTEXT:]
        return float(out.ravel()[0])


class SpeechSegmenter:
    """Machine à états : silence → parole (après quelques trames) → silence prolongé = fin."""

    def __init__(
        self,
        vad: Callable[[np.ndarray], float],
        on_segment: Callable[[np.ndarray], None],
        threshold: float = 0.5,
        silence_ms: int = 700,
        min_speech_ms: int = 250,
        preroll_ms: int = 500,  # le « J » de Friday est détecté avec un temps de retard
        max_ms: int = 45_000,  # une demande peut enchaîner plusieurs choses
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.vad = vad
        self.clock = clock
        self.on_segment = on_segment
        self.threshold = threshold
        self._silence_frames = silence_ms // FRAME_MS
        self._min_frames = min_speech_ms // FRAME_MS
        self._max_frames = max_ms // FRAME_MS
        # On garde un peu d'audio d'avant le début détecté, pour ne pas couper le 1er mot.
        self._preroll: deque[np.ndarray] = deque(maxlen=preroll_ms // FRAME_MS)
        self._pending = np.zeros(0, dtype=np.float32)
        self._frames: list[np.ndarray] = []
        self._speech = 0
        self._silence = 0
        self.started_at = 0.0  # moment où la phrase en cours (ou la dernière) a commencé

    @property
    def in_speech(self) -> bool:
        return bool(self._frames)

    def feed(self, audio: np.ndarray) -> None:
        self._pending = np.concatenate([self._pending, audio])
        while self._pending.size >= FRAME:
            frame, self._pending = self._pending[:FRAME], self._pending[FRAME:]
            self._process(frame, self.vad(frame) >= self.threshold)

    def reset(self) -> None:
        self._pending = np.zeros(0, dtype=np.float32)
        self._frames, self._speech, self._silence = [], 0, 0
        self._preroll.clear()

    def _process(self, frame: np.ndarray, is_speech: bool) -> None:
        if not self._frames:
            if is_speech:
                self.started_at = self.clock()
                self._frames = [*self._preroll, frame]
                self._speech, self._silence = 1, 0
            else:
                self._preroll.append(frame)
            return

        self._frames.append(frame)
        if is_speech:
            self._speech += 1
            self._silence = 0
        else:
            self._silence += 1

        ended = self._silence >= self._silence_frames
        if ended or len(self._frames) >= self._max_frames:
            frames, enough = self._frames, self._speech >= self._min_frames
            self._frames, self._speech, self._silence = [], 0, 0
            self._preroll.clear()
            if enough:  # un claquement ou un toussotement ne fait pas une phrase
                self.on_segment(np.concatenate(frames))

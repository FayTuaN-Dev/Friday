"""Diagnostic (désactivé par défaut) : garde les dernières phrases entendues en .wav, avec ce
que Whisper en a compris, pour comprendre pourquoi une demande n'a pas été reconnue."""

import logging
import re
import wave
from datetime import datetime
from pathlib import Path

import numpy as np

from friday.voice.recorder import WHISPER_RATE

log = logging.getLogger(__name__)

KEEP = 100  # au-delà, les plus anciens sont effacés


class HeardLog:
    def __init__(self, folder: Path) -> None:
        self.folder = folder
        folder.mkdir(parents=True, exist_ok=True)
        log.info("Enregistrement des phrases entendues dans %s", folder)

    def save(self, audio: np.ndarray, text: str) -> Path:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]
        slug = re.sub(r"[^\w]+", "_", text.lower())[:60].strip("_") or "vide"
        path = self.folder / f"{stamp}_{slug}.wav"
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(WHISPER_RATE)
            wav.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())
        path.with_suffix(".txt").write_text(text, encoding="utf-8")
        self._prune()
        return path

    def _prune(self) -> None:
        recordings = sorted(self.folder.glob("*.wav"))
        for old in recordings[:-KEEP]:
            old.unlink(missing_ok=True)
            old.with_suffix(".txt").unlink(missing_ok=True)

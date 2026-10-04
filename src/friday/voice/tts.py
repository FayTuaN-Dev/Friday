"""Synthèse vocale locale avec Piper."""

import logging
from pathlib import Path

import numpy as np
from piper import PiperVoice, SynthesisConfig
from piper.download_voices import download_voice

log = logging.getLogger(__name__)


class PiperTTS:
    def __init__(
        self, voice: str, voices_dir: Path, speed: float = 1.0, speaker: int | None = None
    ) -> None:
        model = voices_dir / f"{voice}.onnx"
        if not model.exists():
            log.info("Téléchargement de la voix %s…", voice)
            voices_dir.mkdir(parents=True, exist_ok=True)
            download_voice(voice, voices_dir)

        self.voice = PiperVoice.load(model)
        self.sample_rate = self.voice.config.sample_rate
        # Piper raisonne en « durée des phonèmes » : 0.8 = plus rapide, donc on inverse.
        self.config = SynthesisConfig(length_scale=1 / speed, speaker_id=speaker)
        log.info("Voix %s chargée (%d Hz)", voice, self.sample_rate)

    def synthesize(self, text: str) -> np.ndarray:
        """Renvoie l'audio (float32 mono entre -1 et 1)."""
        chunks = [c.audio_float_array for c in self.voice.synthesize(text, self.config)]
        if not chunks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(chunks)

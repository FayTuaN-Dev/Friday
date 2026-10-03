"""Transcription de la voix avec faster-whisper (GPU si possible, sinon CPU)."""

import logging
import os
from pathlib import Path

import numpy as np

from jarvis.voice.cuda import register_cuda_dlls
from jarvis.voice.recorder import WHISPER_RATE

log = logging.getLogger(__name__)

MIN_SECONDS = 0.4
# Phrases que Whisper invente parfois sur du silence (il a été entraîné sur des sous-titres).
HALLUCINATIONS = ("sous-titr", "amara.org", "merci d'avoir regardé", "abonnez-vous")


def clean_transcript(text: str) -> str:
    text = text.strip()
    if any(h in text.lower() for h in HALLUCINATIONS):
        return ""
    return text


class WhisperSTT:
    def __init__(self, model: str, device: str, models_dir: Path) -> None:
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        register_cuda_dlls()
        from faster_whisper import WhisperModel

        try:
            self.model = WhisperModel(
                model, device=device, compute_type="int8_float16", download_root=str(models_dir)
            )
            self._warmup()
        except (RuntimeError, ValueError) as e:
            if device == "cpu":
                raise
            # Les erreurs CUDA (DLL manquante, mémoire vidéo pleine) n'apparaissent qu'à l'usage.
            log.warning("Whisper sur GPU impossible (%s), bascule sur CPU", e)
            self.model = WhisperModel(
                model, device="cpu", compute_type="int8", download_root=str(models_dir)
            )
            self._warmup()
        log.info("Whisper %s prêt (%s)", model, self.model.model.device)

    def _warmup(self) -> None:
        list(self.model.transcribe(np.zeros(WHISPER_RATE, dtype=np.float32), language="fr")[0])

    def transcribe(self, audio: np.ndarray) -> str:
        if audio.size < MIN_SECONDS * WHISPER_RATE:
            return ""
        segments, _ = self.model.transcribe(
            audio,
            language="fr",
            beam_size=5,
            vad_filter=True,  # ignore les silences avant/après la parole
            condition_on_previous_text=False,
            initial_prompt="Jarvis,",  # aide Whisper à bien écrire le nom
        )
        return clean_transcript(" ".join(s.text for s in segments))

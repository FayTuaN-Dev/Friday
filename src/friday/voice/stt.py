"""Transcription de la voix avec faster-whisper (GPU si possible, sinon CPU)."""

import logging
import os
import threading
from pathlib import Path

import numpy as np

from friday.voice.cuda import register_cuda_dlls
from friday.voice.rate import WHISPER_RATE

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
    def __init__(self, model: str, device: str, models_dir: Path, hotword: str = "Friday") -> None:
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        self.hotword = hotword  # le nom de l'assistante, que Whisper doit bien écrire
        # Push-to-talk et écoute continue transcrivent depuis deux threads : un à la fois.
        self._lock = threading.Lock()
        self._settings = (model, device, models_dir)
        self._load()

    def _load(self) -> None:
        model, device, models_dir = self._settings
        register_cuda_dlls()
        from faster_whisper import WhisperModel

        try:
            # int8_float16 n'existe que sur carte graphique : sur processeur, int8.
            compute_type = "int8" if device == "cpu" else "int8_float16"
            self.model = WhisperModel(
                model, device=device, compute_type=compute_type, download_root=str(models_dir)
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

    @property
    def loaded(self) -> bool:
        return self.model is not None

    def unload(self) -> None:
        """Mode jeu : le modèle quitte la carte graphique (rechargé par `reload`)."""
        import gc

        with self._lock:
            self.model = None
            gc.collect()
        log.info("Whisper déchargé")

    def reload(self) -> None:
        with self._lock:
            if self.model is None:
                self._load()

    def _warmup(self) -> None:
        list(self.model.transcribe(np.zeros(WHISPER_RATE, dtype=np.float32), language="fr")[0])

    def transcribe(self, audio: np.ndarray) -> str:
        if audio.size < MIN_SECONDS * WHISPER_RATE:
            return ""
        with self._lock:
            if self.model is None:  # déchargé (mode jeu) : rien à transcrire
                return ""
            return self._transcribe(audio)

    def _transcribe(self, audio: np.ndarray) -> str:
        segments, _ = self.model.transcribe(
            audio,
            language="fr",
            beam_size=5,
            vad_filter=True,  # ignore les silences avant/après la parole
            condition_on_previous_text=False,
            # Oriente Whisper vers le nom. (Un initial_prompt="Jarvis," faisait l'inverse : Whisper
            # croyait le nom déjà dit et le sautait — 12 réveils sur 20 contre 18 ici.)
            hotwords=self.hotword,
        )
        return clean_transcript(" ".join(s.text for s in segments))

    def transcribe_head(self, audio: np.ndarray, language: str, seconds: float = 1.3) -> str:
        """Retranscrit seulement le début de la voix, dans une autre langue : un nom anglais
        (« Friday ») au début d'une phrase française est souvent sauté par Whisper en français.
        Sur un extrait plus long, Whisper repasse au français : il faut rester court."""
        start = voice_start(audio)
        with self._lock:
            if self.model is None:
                return ""
            segments, _ = self.model.transcribe(
                audio[start : start + int(seconds * WHISPER_RATE)],
                language=language,
                beam_size=5,
                temperature=0.0,  # pas de nouvel essai « au hasard » : résultat reproductible
                vad_filter=False,
                condition_on_previous_text=False,
                # Pas d'indice ici : en anglais, il fait entendre « Friday » dans « Frida »,
                # « Fred »… (mesuré : 6 faux réveils sur 36 avec, 1 sans).
            )
        return " ".join(s.text for s in segments).strip()


def voice_start(audio: np.ndarray, frame: int = 320) -> int:
    """Indice où la voix commence (le segment contient ~0,5 s d'avant, gardé par le VAD)."""
    n = audio.size // frame
    if n == 0:
        return 0
    rms = np.sqrt(np.mean(audio[: n * frame].reshape(n, frame) ** 2, axis=1))
    loud = np.flatnonzero(rms > max(0.01, rms.max() * 0.1))
    return max(0, (int(loud[0]) - 5) * frame) if loud.size else 0  # 0,1 s de marge

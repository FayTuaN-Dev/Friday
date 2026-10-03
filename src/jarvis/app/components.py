"""Chargement des briques lourdes (modèles), chacune pouvant échouer sans bloquer Jarvis."""

import logging
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from jarvis.brain.llm import Brain
from jarvis.core.config import MODELS_DIR, VOICES_DIR, Settings
from jarvis.tools import default_toolbox
from jarvis.voice.speaker import Speaker

log = logging.getLogger(__name__)


@dataclass
class Components:
    brain: Brain
    speaker: Speaker | None = None
    stt: object | None = None  # WhisperSTT
    recorder: object | None = None  # Recorder


def load_components(
    settings: Settings,
    on_mic_level: Callable[[float], None],
    on_speech_audio: Callable[[np.ndarray, int], None],
) -> Components:
    brain = Brain(settings, toolbox=default_toolbox(settings))
    brain.warmup()
    components = Components(brain=brain)

    if settings.tts_enabled:
        try:
            from jarvis.voice.tts import PiperTTS

            tts = PiperTTS(settings.tts_voice, VOICES_DIR, settings.tts_speed, settings.tts_speaker)
            components.speaker = Speaker(tts, on_play=on_speech_audio)
        except Exception:
            log.exception("Voix indisponible, Jarvis continue en mode texte")

    if settings.stt_enabled:
        try:
            from jarvis.voice.recorder import Recorder
            from jarvis.voice.stt import WhisperSTT

            components.recorder = Recorder(settings.mic_device, on_level=on_mic_level)
            components.stt = WhisperSTT(settings.stt_model, settings.stt_device, MODELS_DIR)
        except Exception:
            log.exception("Écoute indisponible, Jarvis continue au clavier")
            components.recorder = components.stt = None

    return components


def describe(settings: Settings, components: Components, inputs: list[str]) -> str:
    """Résumé affiché sous le cercle : « Cerveau : … · Voix : … · Dites « Jarvis » »."""
    parts = [f"Cerveau : {settings.ollama_model}"]
    parts.append(f"Voix : {settings.tts_voice}" if components.speaker else "Voix : désactivée")
    parts += inputs or ["Écoute : désactivée"]
    return " · ".join(parts)

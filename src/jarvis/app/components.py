"""Chargement des briques lourdes (modèles), chacune pouvant échouer sans bloquer Jarvis."""

import logging
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import ollama

from jarvis.app.memory_keeper import MemoryKeeper
from jarvis.brain.llm import Brain
from jarvis.core.config import DATA_DIR, MODELS_DIR, VOICES_DIR, Settings
from jarvis.memory.service import MemoryService, format_memories
from jarvis.tools import default_toolbox
from jarvis.voice.speaker import Speaker

log = logging.getLogger(__name__)


@dataclass
class Components:
    brain: Brain
    speaker: Speaker | None = None
    stt: object | None = None  # WhisperSTT
    recorder: object | None = None  # Recorder
    memory: MemoryService | None = None
    keeper: MemoryKeeper | None = None  # mémorisation automatique


def load_components(
    settings: Settings,
    on_mic_level: Callable[[float], None],
    on_speech_audio: Callable[[np.ndarray, int], None],
    on_memory: Callable[[str], None] = lambda text: None,
) -> Components:
    client = ollama.Client(host=settings.ollama_host)
    memory = load_memory(settings, client)
    brain = Brain(
        settings,
        client=client,
        toolbox=default_toolbox(settings, memory),
        recall=(lambda question: format_memories(memory.relevant(question))) if memory else None,
    )
    brain.warmup()
    components = Components(brain=brain, memory=memory)

    if memory and settings.memory_auto:
        from jarvis.memory.extractor import FactExtractor

        extractor = FactExtractor(client, settings.ollama_model, settings.ollama_num_ctx)
        components.keeper = MemoryKeeper(memory, extractor, on_memory)

    if settings.tts_enabled:
        try:
            from jarvis.voice.player import AudioPlayer
            from jarvis.voice.tts import PiperTTS

            tts = PiperTTS(settings.tts_voice, VOICES_DIR, settings.tts_speed, settings.tts_speaker)
            player = AudioPlayer(tts.sample_rate, settings.output_device)
            components.speaker = Speaker(
                tts, play=player.play, stop_playback=player.stop, on_play=on_speech_audio
            )
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


def load_memory(settings: Settings, client: ollama.Client) -> MemoryService | None:
    if not settings.memory_enabled:
        return None
    try:
        from jarvis.memory.embedder import Embedder
        from jarvis.memory.store import MemoryStore

        DATA_DIR.mkdir(exist_ok=True)
        embedder = Embedder(settings.embed_model, client)
        embedder.query("test")  # vérifie que le modèle est installé (et le charge)
        memory = MemoryService(MemoryStore(DATA_DIR / "memory.db"), embedder)
        log.info("Mémoire chargée : %d souvenirs", memory.store.count())
        return memory
    except Exception:
        log.exception(
            "Mémoire indisponible (modèle manquant ? « ollama pull %s »)", settings.embed_model
        )
        return None


def describe(settings: Settings, components: Components, inputs: list[str]) -> str:
    """Résumé affiché sous le cercle : « Cerveau : … · Voix : … · Dites « Jarvis » »."""
    parts = [f"Cerveau : {settings.ollama_model}"]
    parts.append(f"Voix : {settings.tts_voice}" if components.speaker else "Voix : désactivée")
    if components.memory:
        parts.append(f"Mémoire : {components.memory.store.count()} souvenirs")
    parts += inputs or ["Écoute : désactivée"]
    return " · ".join(parts)

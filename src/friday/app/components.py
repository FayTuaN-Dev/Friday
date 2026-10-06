"""Chargement des briques lourdes (modèles), chacune pouvant échouer sans bloquer Friday."""

import logging
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import ollama

from friday.app.extras import load_briefing, load_google
from friday.app.gpu_check import warn_if_spilling
from friday.app.memory_keeper import MemoryKeeper
from friday.brain.llm import Brain
from friday.core.config import DATA_DIR, MODELS_DIR, VOICES_DIR, Settings
from friday.memory.service import MemoryService, format_memories
from friday.tools import ToolResult, default_toolbox
from friday.tools.research import ResearchLog
from friday.voice.speaker import Speaker

log = logging.getLogger(__name__)


@dataclass
class Components:
    brain: Brain
    speaker: Speaker | None = None
    stt: object | None = None  # WhisperSTT
    recorder: object | None = None  # Recorder
    memory: MemoryService | None = None
    keeper: MemoryKeeper | None = None  # mémorisation automatique
    agenda: object | None = None  # AgendaStore (rappels, notes)
    briefing: object | None = None  # Briefing (briefing du matin)
    google: object | None = None  # GoogleAccount (agenda et mails)


def load_components(
    settings: Settings,
    on_mic_level: Callable[[float], None],
    on_speech_audio: Callable[[np.ndarray, int], None],
    on_memory: Callable[[str], None] = lambda text: None,
    on_background: Callable[[str, ToolResult], None] | None = None,
) -> Components:
    client = ollama.Client(host=settings.ollama_host)
    memory = load_memory(settings, client)
    agenda = None
    if settings.agenda_enabled:
        from friday.agenda.store import AgendaStore

        DATA_DIR.mkdir(exist_ok=True)
        agenda = AgendaStore(DATA_DIR / "agenda.db")
    google = load_google(settings)
    briefing = load_briefing(settings, agenda, google)
    research = ResearchLog()
    contexts = {"web": research.summary}
    if briefing:
        contexts["briefing"] = briefing.summary
    brain = Brain(
        settings,
        client=client,
        toolbox=default_toolbox(
            settings, memory, on_background, agenda, briefing, google, research
        ),
        recall=(lambda question: format_memories(memory.relevant(question))) if memory else None,
        router=load_router(memory),
        skill_contexts=contexts,
    )
    brain.warmup()
    warn_if_spilling(client, settings.ollama_model, settings.ollama_num_ctx)
    components = Components(
        brain=brain, memory=memory, agenda=agenda, briefing=briefing, google=google
    )

    if memory and settings.memory_auto:
        from friday.memory.extractor import FactExtractor

        extractor = FactExtractor(client, settings.ollama_model, settings.ollama_num_ctx)
        components.keeper = MemoryKeeper(memory, extractor, on_memory)

    if settings.tts_enabled:
        try:
            from friday.voice.player import AudioPlayer
            from friday.voice.tts import PiperTTS

            tts = PiperTTS(settings.tts_voice, VOICES_DIR, settings.tts_speed, settings.tts_speaker)
            player = AudioPlayer(tts.sample_rate, settings.output_device)
            name = settings.wake_words[0]
            components.speaker = Speaker(
                tts,
                play=player.play,
                stop_playback=player.stop,
                on_play=on_speech_audio,
                pronunciations={name: settings.tts_name_pronunciation}
                if settings.tts_name_pronunciation
                else None,
            )
        except Exception:
            log.exception("Voix indisponible, Friday continue en mode texte")

    if settings.stt_enabled:
        try:
            from friday.voice.recorder import Recorder
            from friday.voice.stt import WhisperSTT

            components.recorder = Recorder(settings.mic_device, on_level=on_mic_level)
            components.stt = WhisperSTT(
                settings.stt_model,
                settings.stt_device,
                MODELS_DIR,
                settings.wake_words[0].capitalize(),
            )
        except Exception:
            log.exception("Écoute indisponible, Friday continue au clavier")
            components.recorder = components.stt = None

    if agenda is not None and on_background is not None:
        from friday.app.reminders import start_reminders

        start_reminders(agenda, lambda: components.speaker, on_background)

    return components


def load_router(memory: MemoryService | None):
    """Aiguillage des compétences : mots-clés, et le sens des phrases si les embeddings de la
    mémoire sont disponibles."""
    from friday.brain.router import SkillRouter
    from friday.brain.skills import SKILLS

    if memory is None:
        return SkillRouter(SKILLS)
    return SkillRouter(SKILLS, memory.embedder.query, memory.embedder.documents)


def load_memory(settings: Settings, client: ollama.Client) -> MemoryService | None:
    if not settings.memory_enabled:
        return None
    try:
        from friday.memory.embedder import Embedder
        from friday.memory.store import MemoryStore

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
    """Résumé affiché sous le cercle : « Cerveau : … · Voix : … · Dites « Friday » »."""
    parts = [f"Cerveau : {settings.ollama_model}"]
    parts.append(f"Voix : {settings.tts_voice}" if components.speaker else "Voix : désactivée")
    if components.memory:
        parts.append(f"Mémoire : {components.memory.store.count()} souvenirs")
    if components.google:
        connected = components.google.connected
        parts.append("Google : connecté" if connected else "Google : à autoriser (navigateur)")
    parts += inputs or ["Écoute : désactivée"]
    return " · ".join(parts)

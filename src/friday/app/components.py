"""Chargement des briques lourdes (modèles), chacune pouvant échouer sans bloquer Friday."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import ollama

from friday.app.extras import (
    load_briefing,
    load_google,
    load_library,
    load_trading,
    load_world,
)
from friday.app.gpu_check import warn_if_spilling
from friday.app.memory_keeper import MemoryKeeper
from friday.app.prefetch import hints, prefetcher
from friday.brain.gpu_gate import GatedClient
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
    library: object | None = None  # Library (bibliothèque de documents)
    trading: object | None = None  # Trading (mode trading)
    backup: object | None = None  # DailyBackup (sauvegarde quotidienne de data/)
    day_log: object | None = None  # DayLog (mémoire de la journée)


def load_components(
    settings: Settings,
    on_mic_level: Callable[[float], None],
    on_speech_audio: Callable[[np.ndarray, int], None],
    on_memory: Callable[[str], None] = lambda text: None,
    on_background: Callable[[str, ToolResult], None] | None = None,
) -> Components:
    client = GatedClient(host=settings.ollama_host)
    memory = load_memory(settings, client)
    day_log = None
    if settings.day_memory:
        from friday.memory.day_log import DayLog

        day_log = DayLog(DATA_DIR / "journee.db")
    agenda = None
    if settings.agenda_enabled:
        from friday.agenda.store import AgendaStore

        DATA_DIR.mkdir(exist_ok=True)
        agenda = AgendaStore(DATA_DIR / "agenda.db")
    google = load_google(settings)
    briefing = load_briefing(settings, agenda, google)
    research = ResearchLog()
    library = load_library(settings, memory)
    trading = load_trading(settings, library)
    world = load_world(settings, trading)
    contexts = {"web": research.summary}
    if briefing:
        contexts["briefing"] = briefing.summary
    toolbox = default_toolbox(
        settings,
        memory,
        on_background,
        agenda,
        briefing,
        google,
        research,
        library,
        trading,
        day_log,
        world,
    )
    if (categories := toolbox.find("category_mails")) is not None:
        from friday.tools.mail_sorting import categories_context

        contexts["mail"] = lambda: categories_context(categories.mailbox)
    brain = Brain(
        settings,
        client=client,
        toolbox=toolbox,
        recall=(lambda question: format_memories(memory.relevant(question))) if memory else None,
        router=load_router(memory),
        skill_contexts=contexts,
        skill_hints=hints(library, trading),
        # Outils de trading : toujours là ; l'analyse par Claude : en mode trading seulement
        skill_gates={"analyse_trading": lambda: bool(trading and trading.mode.enabled)},
    )
    brain.prefetch = prefetcher(library, trading, brain.toolset.router,
                                mail=categories is not None, days=day_log is not None,
                                memory=memory is not None, world=world is not None,
                                music=toolbox.find("play_music") is not None,
                                web=toolbox.find("read_webpage") is not None)  # fmt: skip
    brain.warmup()
    warn_if_spilling(client, settings.ollama_model, settings.ollama_num_ctx)
    components = Components(
        brain=brain,
        memory=memory,
        agenda=agenda,
        briefing=briefing,
        google=google,
        library=library,
        trading=trading,
        day_log=day_log,
    )

    if memory and settings.memory_auto:
        from friday.memory.extractor import FactExtractor

        extractor = FactExtractor(client, settings.ollama_model, settings.ollama_num_ctx)
        components.keeper = MemoryKeeper(memory, extractor, on_memory)
        components.keeper.sort_unthemed(client, settings.ollama_model)

    if settings.tts_enabled:
        try:
            from friday.voice.player import AudioPlayer
            from friday.voice.tts import PiperTTS

            tts = PiperTTS(settings.tts_voice, VOICES_DIR, settings.tts_speed, settings.tts_speaker)
            tts.synthesize("Bonjour.")  # échauffement : la 1re phrase figeait la fenêtre
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
        from friday.agenda.routines import RoutineStore
        from friday.app.routines import RoutineRunner

        RoutineRunner(RoutineStore(DATA_DIR / "routines.json"), on_background).start()
    if trading is not None and trading.alerts is not None and on_background is not None:
        from friday.app.trading_alerts import start_alerts

        start_alerts(trading.alerts, lambda: components.speaker, on_background)
    if world is not None and settings.world_alerts and on_background is not None:
        from friday.app.world_watch import WorldWatch

        WorldWatch(world, DATA_DIR / "monde_vu.json", on_background).start()
    from friday.app.backup import DailyBackup

    components.backup = DailyBackup(DATA_DIR, Path(settings.backup_dir) if settings.backup_dir
                                    else None)  # fmt: skip
    components.backup.start()  # au démarrage si la dernière a plus de 24 h, puis chaque jour
    if settings.night_dream and memory is not None and day_log is not None:
        from friday.app.night_dream import NightDream
        from friday.core.config import LOGS_DIR
        from friday.memory.dream import Dreamer

        dreamer = Dreamer(client, settings.ollama_model, settings.ollama_num_ctx)
        NightDream(memory, day_log, dreamer, DATA_DIR / "reve", LOGS_DIR / "friday.log",
                   on_background).start()  # fmt: skip
    if trading is not None and trading.prepare is not None:
        from friday.trading.warm import start_warming

        start_warming(trading, trading.prepare)  # aperçu des analyses instantané
    if trading is not None and trading.briefing is not None and on_background is not None:
        from friday.app.trading_briefing import start_trading_briefing

        start_trading_briefing(trading.briefing, lambda: components.speaker, on_background)

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
        memory = MemoryService(MemoryStore(DATA_DIR / "memory.db"), embedder,
                               mirror=DATA_DIR / "memoire.md")  # fmt: skip
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

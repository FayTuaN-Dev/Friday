"""Configuration de Friday, chargée depuis le fichier .env à la racine du projet."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT_DIR / "data"
LOGS_DIR = ROOT_DIR / "logs"
VOICES_DIR = DATA_DIR / "voices"
MODELS_DIR = DATA_DIR / "models"


@dataclass(frozen=True)
class TradingSettings:
    """Mode trading (voir trading/) : désactivé par défaut dans les tests."""

    enabled: bool = False
    passages: int = 10  # extraits de la bibliothèque joints à une analyse
    max_chars: int = 12_000  # taille maximale du paquet envoyé
    account_currency: str = "EUR"
    blocklist: tuple[str, ...] = ()  # mots toujours masqués (nom, n° de client…)
    capture_window: str = "TradingView"  # titre de la fenêtre du graphique
    model: str = ""  # vide : celui de Claude Code
    hours: tuple[int, int] = (9, 18)  # plage de trading de l'utilisateur (heure de Paris)
    fred_key: str = ""  # clé gratuite FRED : résultats publiés des annonces américaines
    briefing: bool = True  # briefing trading automatique à l'ouverture de la plage de trading
    briefing_instruments: tuple[str, ...] = ()  # vide : les instruments surveillés


@dataclass(frozen=True)
class Settings:
    user_name: str
    ollama_host: str
    ollama_model: str
    ollama_num_ctx: int
    claude_model: str
    claude_enabled: bool
    claude_workspace: Path
    claude_timeout: float
    tts_enabled: bool
    tts_voice: str
    tts_speaker: int | None
    tts_speed: float
    stt_enabled: bool
    stt_model: str
    stt_device: str
    mic_device: int | str | None
    output_device: int | str | None
    ptt_key: str
    hands_free: bool
    wake_words: list[str]
    follow_up_seconds: float
    vad_silence_ms: int
    hands_free_record: bool
    wake_language: str
    tts_name_pronunciation: str
    tools_enabled: bool
    search_region: str
    search_backend: str
    home_city: str
    pc_control: bool
    files_access: bool
    vision_enabled: bool
    vision_model: str
    google_enabled: bool
    agenda_enabled: bool
    memory_enabled: bool
    memory_auto: bool
    library_enabled: bool
    embed_model: str
    log_level: str
    interface_color: str = "Or"  # couleur de base de l'interface (palette ou #rrggbb)
    backup_dir: str = ""  # copie des sauvegardes quotidiennes (clé USB, OneDrive…), facultatif
    notifications: bool = True  # notification Windows quand une tâche de fond se termine
    day_memory: bool = True  # mémoire de la journée : les échanges gardés 90 jours (F5)
    night_dream: bool = True  # rêve nocturne : relire la journée, rapport de ménage (J2)
    clap_wake: bool = True  # double clap = « Friday » (J3), avec l'écoute mains libres
    clap_sensitivity: str = "moyenne"  # « faible », « moyenne » ou « forte »
    scenes: bool = True  # météo en scène plein écran plutôt qu'en fenêtre (J7)
    world: bool = True  # veille monde : actualité internationale, catastrophes (J9)
    world_alerts: bool = True  # notification discrète pour un événement majeur (J9)
    trading: TradingSettings = TradingSettings()


def _hours(value: str) -> tuple[int, int]:
    """« 9-18 », « 9h-18h » → (9, 18) ; valeur illisible : (9, 18)."""
    import re

    found = re.findall(r"\d{1,2}", value)
    if len(found) >= 2 and 0 <= int(found[0]) < int(found[1]) <= 24:  # « 8 h - 17 h 30 »
        return int(found[0]), int(found[1])
    return 9, 18


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if not value:
        return default
    return value.strip().lower() in ("1", "true", "oui", "yes")


def _device(value: str | None) -> int | str | None:
    """Périphérique audio : numéro, morceau de nom, ou vide pour celui de Windows."""
    if not value:
        return None
    return int(value) if value.isdigit() else value


def load_settings() -> Settings:
    load_dotenv(ROOT_DIR / ".env")
    return Settings(
        # JARVIS_USER_NAME : ancien nom du réglage, toujours accepté
        user_name=os.getenv("FRIDAY_USER_NAME") or os.getenv("JARVIS_USER_NAME") or "Monsieur",
        ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen3:8b"),
        ollama_num_ctx=int(os.getenv("OLLAMA_NUM_CTX", "8192")),
        claude_model=os.getenv("CLAUDE_MODEL", "sonnet"),
        claude_enabled=_bool("CLAUDE_ENABLED", True),
        claude_workspace=Path(
            os.getenv("CLAUDE_WORKSPACE") or Path.home() / "Documents" / "Dev" / "Friday-Workspace"
        ),
        claude_timeout=float(os.getenv("CLAUDE_TIMEOUT", "900")),
        tts_enabled=_bool("TTS_ENABLED", True),
        tts_voice=os.getenv("TTS_VOICE", "fr_FR-siwis-medium"),
        tts_speaker=int(v) if (v := os.getenv("TTS_SPEAKER")) else None,
        tts_speed=float(os.getenv("TTS_SPEED", "1.0")),
        stt_enabled=_bool("STT_ENABLED", True),
        stt_model=os.getenv("STT_MODEL", "large-v3-turbo"),
        stt_device=os.getenv("STT_DEVICE", "cuda"),
        mic_device=_device(os.getenv("MIC_DEVICE")),
        output_device=_device(os.getenv("OUTPUT_DEVICE")),
        ptt_key=os.getenv("PTT_KEY", "home"),
        hands_free=_bool("HANDS_FREE", True),
        wake_words=[
            w.strip().lower() for w in os.getenv("WAKE_WORDS", "friday").split(",") if w.strip()
        ],
        follow_up_seconds=float(os.getenv("FOLLOW_UP_SECONDS", "8")),
        vad_silence_ms=int(os.getenv("VAD_SILENCE_MS", "700")),
        hands_free_record=_bool("HANDS_FREE_RECORD", False),
        wake_language=os.getenv("WAKE_LANGUAGE", "en"),
        tts_name_pronunciation=os.getenv("TTS_NAME_PRONUNCIATION", "Fraille dé"),
        tools_enabled=_bool("TOOLS_ENABLED", True),
        search_region=os.getenv("SEARCH_REGION", "fr-fr"),
        search_backend=os.getenv("SEARCH_BACKEND", "auto"),
        home_city=os.getenv("HOME_CITY", ""),
        pc_control=_bool("PC_CONTROL", True),
        files_access=_bool("FILES_ACCESS", True),
        vision_enabled=_bool("VISION_ENABLED", True),
        vision_model=os.getenv("VISION_MODEL", "qwen3-vl:4b-instruct"),
        google_enabled=_bool("GOOGLE_ENABLED", True),
        agenda_enabled=_bool("AGENDA_ENABLED", True),
        memory_enabled=_bool("MEMORY_ENABLED", True),
        memory_auto=_bool("MEMORY_AUTO", True),
        library_enabled=_bool("LIBRARY_ENABLED", True),
        embed_model=os.getenv("EMBED_MODEL", "embeddinggemma"),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        interface_color=os.getenv("FRIDAY_COLOR", "Or"),
        backup_dir=os.getenv("BACKUP_DIR", "").strip(),
        notifications=_bool("NOTIFICATIONS", True),
        day_memory=_bool("DAY_MEMORY", True),
        night_dream=_bool("NIGHT_DREAM", True),
        clap_wake=_bool("CLAP_WAKE", True),
        clap_sensitivity=os.getenv("CLAP_SENSITIVITY", "moyenne").strip().lower(),
        scenes=_bool("SCENES", True),
        world=_bool("WORLD", True),
        world_alerts=_bool("WORLD_ALERTS", True),
        trading=TradingSettings(
            enabled=_bool("TRADING_ENABLED", True),
            passages=max(1, min(15, int(os.getenv("TRADING_PASSAGES", "10")))),
            max_chars=int(os.getenv("TRADING_MAX_CHARS", "12000")),
            account_currency=os.getenv("TRADING_ACCOUNT_CURRENCY", "EUR").upper(),
            blocklist=tuple(
                w.strip() for w in os.getenv("TRADING_BLOCKLIST", "").split(",") if w.strip()
            ),
            capture_window=os.getenv("TRADING_CAPTURE_WINDOW", "TradingView"),
            model=os.getenv("TRADING_MODEL", ""),
            hours=_hours(os.getenv("TRADING_HOURS", "9-18")),
            briefing=_bool("TRADING_BRIEFING", True),
            briefing_instruments=tuple(
                w.strip()
                for w in os.getenv("TRADING_BRIEFING_INSTRUMENTS", "").split(",")
                if w.strip()
            ),
            fred_key=os.getenv("FRED_API_KEY", "").strip(),
        ),
    )

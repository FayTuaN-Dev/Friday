"""Configuration de Jarvis, chargée depuis le fichier .env à la racine du projet."""

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
class Settings:
    user_name: str
    ollama_host: str
    ollama_model: str
    ollama_num_ctx: int
    claude_model: str
    tts_enabled: bool
    tts_voice: str
    tts_speaker: int | None
    tts_speed: float
    stt_enabled: bool
    stt_model: str
    stt_device: str
    mic_device: int | str | None
    ptt_key: str
    tools_enabled: bool
    search_region: str
    log_level: str


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
        user_name=os.getenv("JARVIS_USER_NAME", "Monsieur"),
        ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen3:8b"),
        ollama_num_ctx=int(os.getenv("OLLAMA_NUM_CTX", "8192")),
        claude_model=os.getenv("CLAUDE_MODEL", "sonnet"),
        tts_enabled=_bool("TTS_ENABLED", True),
        tts_voice=os.getenv("TTS_VOICE", "fr_FR-siwis-medium"),
        tts_speaker=int(v) if (v := os.getenv("TTS_SPEAKER")) else None,
        tts_speed=float(os.getenv("TTS_SPEED", "1.0")),
        stt_enabled=_bool("STT_ENABLED", True),
        stt_model=os.getenv("STT_MODEL", "large-v3-turbo"),
        stt_device=os.getenv("STT_DEVICE", "cuda"),
        mic_device=_device(os.getenv("MIC_DEVICE")),
        ptt_key=os.getenv("PTT_KEY", "home"),
        tools_enabled=_bool("TOOLS_ENABLED", True),
        search_region=os.getenv("SEARCH_REGION", "fr-fr"),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )

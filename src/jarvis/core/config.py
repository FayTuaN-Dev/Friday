"""Configuration de Jarvis, chargée depuis le fichier .env à la racine du projet."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT_DIR / "data"
LOGS_DIR = ROOT_DIR / "logs"
VOICES_DIR = DATA_DIR / "voices"


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
    log_level: str


def load_settings() -> Settings:
    load_dotenv(ROOT_DIR / ".env")
    return Settings(
        user_name=os.getenv("JARVIS_USER_NAME", "Monsieur"),
        ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen3:8b"),
        ollama_num_ctx=int(os.getenv("OLLAMA_NUM_CTX", "8192")),
        claude_model=os.getenv("CLAUDE_MODEL", "sonnet"),
        tts_enabled=os.getenv("TTS_ENABLED", "true").lower() in ("1", "true", "oui", "yes"),
        tts_voice=os.getenv("TTS_VOICE", "fr_FR-tom-medium"),
        tts_speaker=int(v) if (v := os.getenv("TTS_SPEAKER")) else None,
        tts_speed=float(os.getenv("TTS_SPEED", "1.0")),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )

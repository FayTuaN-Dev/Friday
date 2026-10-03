"""Configuration de Jarvis, chargée depuis le fichier .env à la racine du projet."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT_DIR / "data"
LOGS_DIR = ROOT_DIR / "logs"


@dataclass(frozen=True)
class Settings:
    user_name: str
    ollama_host: str
    ollama_model: str
    ollama_num_ctx: int
    claude_model: str
    log_level: str


def load_settings() -> Settings:
    load_dotenv(ROOT_DIR / ".env")
    return Settings(
        user_name=os.getenv("JARVIS_USER_NAME", "Monsieur"),
        ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen3:8b"),
        ollama_num_ctx=int(os.getenv("OLLAMA_NUM_CTX", "8192")),
        claude_model=os.getenv("CLAUDE_MODEL", "sonnet"),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )

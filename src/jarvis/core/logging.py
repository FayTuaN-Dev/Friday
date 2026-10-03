"""Journalisation : console + fichier tournant dans logs/."""

import logging
from logging.handlers import RotatingFileHandler

from jarvis.core.config import LOGS_DIR


def setup_logging(level: str = "INFO") -> None:
    LOGS_DIR.mkdir(exist_ok=True)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%H:%M:%S")

    console = logging.StreamHandler()
    console.setFormatter(fmt)

    file = RotatingFileHandler(
        LOGS_DIR / "jarvis.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [console, file]
    # Bibliothèques trop bavardes (une ligne par requête HTTP)
    for noisy in ("httpx", "primp", "faster_whisper"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

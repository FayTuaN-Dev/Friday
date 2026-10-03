"""Jarvis — assistant personnel vocal."""

import logging
import sys

from jarvis.core.config import load_settings
from jarvis.core.logging import setup_logging


def main() -> None:
    # La console Windows n'est pas en UTF-8 par défaut : sans ça, les accents sont illisibles.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    settings = load_settings()
    setup_logging(settings.log_level)
    log = logging.getLogger("jarvis")
    log.info("Jarvis démarre (modèle : %s)", settings.ollama_model)
    print(f"Bonjour {settings.user_name}, Jarvis est prêt.")

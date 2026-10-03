"""Jarvis — assistant personnel vocal."""

import logging
import sys

from jarvis.core.config import load_settings
from jarvis.core.logging import setup_logging


def main() -> None:
    # La console Windows n'est pas en UTF-8 par défaut : sans ça, les accents sont illisibles.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")
    settings = load_settings()
    setup_logging(settings.log_level)
    logging.getLogger("jarvis").info("Jarvis démarre (modèle : %s)", settings.ollama_model)

    from jarvis.cli import TerminalApp

    TerminalApp(settings).run()

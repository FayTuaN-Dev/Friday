"""Jarvis — assistant personnel vocal."""

import argparse
import logging
import sys

from jarvis.core.config import load_settings
from jarvis.core.logging import setup_logging


def main() -> None:
    parser = argparse.ArgumentParser(prog="jarvis", description="Assistant personnel vocal")
    parser.add_argument("--cli", action="store_true", help="interface terminal (sans fenêtre)")
    args = parser.parse_args()

    # La console Windows n'est pas en UTF-8 par défaut : sans ça, les accents sont illisibles.
    for stream in (sys.stdout, sys.stderr, sys.stdin):
        if stream:
            stream.reconfigure(encoding="utf-8")
    settings = load_settings()
    setup_logging(settings.log_level)
    logging.getLogger("jarvis").info("Jarvis démarre (modèle : %s)", settings.ollama_model)

    if args.cli:
        from jarvis.ui.terminal import run
    else:
        from jarvis.ui.desktop.app import run
    run(settings)

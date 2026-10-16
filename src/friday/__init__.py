"""Friday — assistant personnel vocal."""

import argparse
import logging
import sys

from friday.core.config import load_settings
from friday.core.logging import setup_logging


def main() -> None:
    parser = argparse.ArgumentParser(prog="friday", description="Assistant personnel vocal")
    parser.add_argument("--cli", action="store_true", help="interface terminal (sans fenêtre)")
    hint = "démarrer cachée près de l'horloge (lancement avec Windows)"
    parser.add_argument("--tray", action="store_true", help=hint)
    hint = "Friday léger sans fenêtre, à l'écoute du réseau (sur le Raspberry Pi)"
    parser.add_argument("--serveur", action="store_true", help=hint)
    parser.add_argument("--parle-au-pi", metavar="TEXTE", help="une question au Friday du Pi")
    args = parser.parse_args()

    # La console Windows n'est pas en UTF-8 par défaut : sans ça, les accents sont illisibles.
    for stream in (sys.stdout, sys.stderr, sys.stdin):
        if stream:
            stream.reconfigure(encoding="utf-8")
    settings = load_settings()
    setup_logging(settings.log_level)
    logging.getLogger("friday").info("Friday démarre (modèle : %s)", settings.ollama_model)

    if args.parle_au_pi:
        from friday.server.client import talk
        from friday.server.settings import load_server_settings

        talk(load_server_settings(), args.parle_au_pi)
    elif args.serveur:
        from friday.server.client import run_server

        run_server(settings)
    elif args.cli:
        from friday.ui.terminal import run

        run(settings)
    else:
        from friday.ui.desktop.app import run

        run(settings, tray=args.tray)

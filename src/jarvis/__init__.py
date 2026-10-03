"""Jarvis — assistant personnel vocal."""

import logging
import sys

from jarvis.brain.llm import Brain, BrainError
from jarvis.core.config import load_settings
from jarvis.core.logging import setup_logging

HELP = "Commandes : /reset (nouvelle conversation), /quit (quitter)"


def main() -> None:
    # La console Windows n'est pas en UTF-8 par défaut : sans ça, les accents sont illisibles.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")
    settings = load_settings()
    setup_logging(settings.log_level)
    log = logging.getLogger("jarvis")
    log.info("Jarvis démarre (modèle : %s)", settings.ollama_model)

    brain = Brain(settings)
    print(f"Jarvis est prêt, {settings.user_name}. {HELP}\n")

    while True:
        try:
            text = input("Vous  > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            continue
        if text == "/quit":
            break
        if text == "/reset":
            brain.reset()
            print("(Nouvelle conversation)\n")
            continue

        print("Jarvis> ", end="", flush=True)
        try:
            for chunk in brain.reply(text):
                print(chunk, end="", flush=True)
        except BrainError:
            print(f"\n[Impossible de joindre Ollama sur {settings.ollama_host}. Est-il lancé ?]")
        except KeyboardInterrupt:
            print(" [interrompu]")
        print("\n")

    print(f"À bientôt, {settings.user_name}.")

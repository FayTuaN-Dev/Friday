"""Jarvis — assistant personnel vocal."""

import logging
import sys

from jarvis.brain.llm import Brain, BrainError
from jarvis.core.config import VOICES_DIR, Settings, load_settings
from jarvis.core.logging import setup_logging
from jarvis.voice.speaker import Speaker
from jarvis.voice.text import SentenceSplitter

HELP = "Commandes : /voix (activer/couper la voix), /reset (nouvelle conversation), /quit"

log = logging.getLogger("jarvis")


def create_speaker(settings: Settings) -> Speaker | None:
    if not settings.tts_enabled:
        return None
    try:
        from jarvis.voice.tts import PiperTTS

        tts = PiperTTS(settings.tts_voice, VOICES_DIR, settings.tts_speed, settings.tts_speaker)
        return Speaker(tts)
    except Exception:
        log.exception("Voix indisponible, Jarvis continue en mode texte")
        return None


def main() -> None:
    # La console Windows n'est pas en UTF-8 par défaut : sans ça, les accents sont illisibles.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")
    settings = load_settings()
    setup_logging(settings.log_level)
    log.info("Jarvis démarre (modèle : %s)", settings.ollama_model)

    brain = Brain(settings)
    brain.warmup()
    speaker = create_speaker(settings)
    voice_on = speaker is not None
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
        if text == "/voix":
            if speaker is None:
                print("(Voix indisponible : voir les logs)\n")
            else:
                voice_on = not voice_on
                print(f"(Voix {'activée' if voice_on else 'coupée'})\n")
            continue

        splitter = SentenceSplitter()
        print("Jarvis> ", end="", flush=True)
        try:
            for chunk in brain.reply(text):
                print(chunk, end="", flush=True)
                if voice_on:
                    for sentence in splitter.feed(chunk):
                        speaker.say(sentence)
            if voice_on:
                for sentence in splitter.flush():
                    speaker.say(sentence)
                speaker.wait()
        except BrainError:
            print(f"\n[Impossible de joindre Ollama sur {settings.ollama_host}. Est-il lancé ?]")
        except KeyboardInterrupt:
            if speaker:
                speaker.stop()
            print(" [interrompu]")
        print("\n")

    print(f"À bientôt, {settings.user_name}.")

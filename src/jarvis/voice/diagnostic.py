"""Diagnostic audio : rejoue la même phrase sous différentes charges pour trouver d'où viennent
des grésillements.

Usage : uv run python -m jarvis.voice.diagnostic
Écouter chaque étape et noter celles où la voix grésille.
"""

import sys
import threading
import time

import numpy as np
import sounddevice as sd

from jarvis.core.config import MODELS_DIR, VOICES_DIR, load_settings
from jarvis.voice.player import AudioPlayer
from jarvis.voice.recorder import resample

SENTENCE = (
    "Le cours du nickel a fortement progressé ces dernières semaines, porté par la demande "
    "en batteries et par des tensions sur l'offre en Indonésie."
)


def play_and_count(player, audio: np.ndarray) -> int:
    """Joue l'audio avec le lecteur de Jarvis et compte les coupures de la carte son."""
    before = player.underflows
    player.play(audio)
    return player.underflows - before


def busy_gpu_llm(settings, stop: threading.Event) -> None:
    from jarvis.brain.llm import Brain, BrainError

    brain = Brain(settings)
    try:
        while not stop.is_set():
            for _ in brain.reply("Raconte l'histoire du nickel en vingt phrases détaillées."):
                if stop.is_set():
                    return
            brain.reset()
    except BrainError:
        print("   ⚠ Ollama ne répond pas : lance-le pour que cette étape ait du sens.")


def busy_cpu_piper(tts, stop: threading.Event) -> None:
    while not stop.is_set():
        tts.synthesize(SENTENCE)


def busy_gpu_whisper(stt, audio16k: np.ndarray, stop: threading.Event) -> None:
    while not stop.is_set():
        stt.transcribe(audio16k)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    from jarvis.voice.stt import WhisperSTT
    from jarvis.voice.tts import PiperTTS

    settings = load_settings()
    print("Chargement des modèles…")
    tts = PiperTTS(settings.tts_voice, VOICES_DIR, settings.tts_speed, settings.tts_speaker)
    stt = WhisperSTT(settings.stt_model, settings.stt_device, MODELS_DIR)
    audio = tts.synthesize(SENTENCE)
    audio16k = resample(audio, tts.sample_rate)
    player = AudioPlayer(tts.sample_rate, settings.output_device)
    print(f"Sortie audio : {sd.query_devices(player._stream.device)['name']}\n")

    steps = [
        ("1. Au repos (rien d'autre ne tourne)", []),
        ("2. Carte graphique occupée par le LLM (Ollama)", [lambda s: busy_gpu_llm(settings, s)]),
        ("3. Processeur occupé par la synthèse Piper", [lambda s: busy_cpu_piper(tts, s)]),
        ("4. Carte graphique occupée par Whisper", [lambda s: busy_gpu_whisper(stt, audio16k, s)]),
        (
            "5. Tout en même temps (comme pendant une longue réponse)",
            [
                lambda s: busy_gpu_llm(settings, s),
                lambda s: busy_cpu_piper(tts, s),
                lambda s: busy_gpu_whisper(stt, audio16k, s),
            ],
        ),
    ]
    for title, loads in steps:
        print(title)
        stop = threading.Event()
        for load in loads:
            threading.Thread(target=load, args=(stop,), daemon=True).start()
        time.sleep(2 if loads else 0.5)  # laisse la charge démarrer
        underflows = play_and_count(player, audio)
        stop.set()
        print(f"   → coupures détectées par la carte son : {underflows}\n")
        time.sleep(1.5)

    player.close()
    print("Terminé. Note les étapes où tu as entendu des grésillements.")


if __name__ == "__main__":
    main()

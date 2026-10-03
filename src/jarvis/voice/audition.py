"""Écoute les voix françaises téléchargées pour choisir celle de Jarvis.

Usage : uv run python -m jarvis.voice.audition
"""

import sys
import time

import sounddevice as sd

from jarvis.core.config import VOICES_DIR
from jarvis.voice.tts import PiperTTS

SAMPLE = (
    "Bonjour Monsieur. Tous les systèmes sont opérationnels. "
    "Il est quinze heures trente, et vous avez trois rendez-vous cet après-midi."
)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    candidates = [(v.stem, None) for v in sorted(VOICES_DIR.glob("*.onnx"))]
    # upmc contient deux locuteurs
    candidates = [
        c
        for name, _ in candidates
        for c in ([(name, 0), (name, 1)] if "upmc" in name else [(name, None)])
    ]
    if not candidates:
        print(f"Aucune voix dans {VOICES_DIR}. Lance d'abord Jarvis une fois.")
        return

    for name, speaker in candidates:
        label = name + (f" (TTS_SPEAKER={speaker})" if speaker is not None else "")
        tts = PiperTTS(name, VOICES_DIR, speaker=speaker)
        start = time.perf_counter()
        audio = tts.synthesize(SAMPLE)
        took = time.perf_counter() - start
        print(f"▶ {label}  — synthèse en {took:.2f} s")
        sd.play(audio, tts.sample_rate, blocking=True)
        time.sleep(0.5)


if __name__ == "__main__":
    main()

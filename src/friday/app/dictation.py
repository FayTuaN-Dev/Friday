"""Dictée partout : maintenir la touche de dictée, parler, relâcher. Le texte s'écrit dans la
fenêtre active (Discord, navigateur, Word…), là où est le curseur. Whisper seulement : ni le
modèle de langue ni Internet, le texte arrive en une à deux secondes.

« à la ligne » et « nouveau paragraphe » dits pendant la dictée deviennent des retours à la
ligne. Les dictées successives se suivent avec une espace.
"""

import logging
import re
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from friday.app.assistant import Assistant

log = logging.getLogger(__name__)

# Whisper ponctue tout seul ; il reste les retours à la ligne, dits à voix haute
COMMANDS = (
    (re.compile(r"[,.]?\s*\bnouveau paragraphe\b[,.]?\s*", re.IGNORECASE), "\n\n"),
    (re.compile(r"[,.]?\s*\bpoint,? à la ligne\b[,.]?\s*", re.IGNORECASE), ".\n"),
    (re.compile(r"[,.]?\s*\bà la ligne\b[,.]?\s*", re.IGNORECASE), "\n"),
)


def dictated(text: str) -> str:
    """Le texte à écrire : commandes remplacées, majuscule après un retour à la ligne, et une
    espace finale pour enchaîner la dictée suivante."""
    text = text.strip()
    for pattern, replacement in COMMANDS:
        text = pattern.sub(replacement, text)
    text = re.sub(r"\n(\w)", lambda m: "\n" + m.group(1).upper(), text)
    if not text.strip():
        return text
    return text if text.endswith("\n") else text + " "


def type_text(text: str) -> None:
    """Tape le texte dans la fenêtre active (caractères Unicode : accents compris)."""
    import keyboard

    keyboard.write(text, delay=0)


class Dictation:
    def __init__(self, assistant: "Assistant", write: Callable[[str], None] = type_text) -> None:
        self.assistant = assistant
        self.write = write
        self.recording = False

    def press(self) -> None:
        a, inputs = self.assistant, self.assistant.inputs
        if self.recording or inputs.listening or a.game.paused or not a.can_listen:
            return
        self.recording = True
        inputs.pause()  # l'écoute mains libres n'entend pas la dictée
        a.components.recorder.start()
        log.info("Dictée : enregistrement")

    def other_key(self) -> None:
        """Une autre touche pendant la dictée : c'était un raccourci (Ctrl+C…), on annule."""
        if not self.recording:
            return
        self.recording = False
        self.assistant.components.recorder.stop()
        self.assistant.inputs.resume()
        log.info("Dictée annulée (raccourci clavier)")

    def release(self) -> None:
        if not self.recording:
            return
        self.recording = False
        audio = self.assistant.components.recorder.stop()
        self.assistant.inputs.resume()
        threading.Thread(target=self._finish, args=(audio,), daemon=True,
                         name="dictee").start()  # fmt: skip

    def _finish(self, audio) -> None:
        try:
            text = dictated(self.assistant.components.stt.transcribe(audio))
            if text.strip():
                self.write(text)
                log.info("Dictée : %d caractères écrits", len(text))
        except Exception:
            log.exception("Dictée impossible")

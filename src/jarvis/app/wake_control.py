"""Décide quoi faire d'une phrase entendue en continu (mains libres)."""

import logging
import time
from collections.abc import Callable
from typing import Protocol

from jarvis.voice.wake import is_stop, is_stop_request, similarity, split_wake_word, wake_pattern

log = logging.getLogger(__name__)

# Au-delà de cette part de mots communs avec ce que Jarvis vient de dire, c'est son écho.
ECHO_SIMILARITY = 0.6


class WakeTarget(Protocol):
    last_reply_text: str
    busy: bool  # en train de réfléchir ou de parler

    def interrupt(self) -> None: ...
    def acknowledge(self) -> None: ...
    def submit_heard(self, text: str) -> None: ...


class WakeControl:
    """Règles :
    - « Jarvis, <demande> » : coupe Jarvis s'il parle, puis traite la demande ;
    - « Jarvis » seul : il répond « Oui ? » et écoute la phrase suivante sans le nom ;
    - « Jarvis, stop » : coupe la parole, sans nouvelle demande ; pendant qu'il parle,
      « stop » seul suffit ;
    - juste après une réponse, une relance sans le nom est acceptée quelques secondes ;
    - ce qui ressemble à ce que Jarvis vient de dire (son propre écho) est ignoré.
    """

    def __init__(
        self,
        target: WakeTarget,
        wake_words: list[str],
        follow_up_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.target = target
        self.pattern = wake_pattern(wake_words)
        self.follow_up_seconds = follow_up_seconds
        self._clock = clock
        self._follow_up_until = 0.0

    def open_follow_up(self) -> None:
        self._follow_up_until = self._clock() + self.follow_up_seconds

    def on_heard(self, text: str) -> None:
        if self._is_echo(text):
            log.debug("Écho de Jarvis ignoré : %s", text)
            return

        # Pendant qu'il parle, « stop » suffit (même si Whisper a mal compris le nom).
        if self.target.busy and is_stop_request(text):
            self.target.interrupt()
            return

        command = split_wake_word(text, self.pattern)
        if command is None:
            if self._clock() > self._follow_up_until:
                return  # conversation autour de l'ordinateur, pas pour Jarvis
            command = text
        self._follow_up_until = 0.0

        if is_stop(command):
            self.target.interrupt()
        elif not command:
            self.target.interrupt()
            self.target.acknowledge()
        else:
            self.target.interrupt()
            self.target.submit_heard(command)

    def _is_echo(self, text: str) -> bool:
        said = self.target.last_reply_text
        return bool(said) and similarity(text, said) >= ECHO_SIMILARITY

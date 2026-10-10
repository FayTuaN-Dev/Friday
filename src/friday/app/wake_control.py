"""Décide quoi faire d'une phrase entendue en continu (mains libres)."""

import logging
import time
from collections.abc import Callable
from typing import Protocol

from friday.voice.wake import is_stop, is_stop_request, similarity, split_wake_word, wake_pattern

log = logging.getLogger(__name__)

# Au-delà de cette part de mots communs avec ce que Friday vient de dire, c'est son écho…
ECHO_SIMILARITY = 0.6
# … mais seulement pendant qu'elle parle ou juste après : l'utilisateur qui lui répond
# reprend forcément ses mots (« retire l'agenda du briefing » après la liste des rubriques).
ECHO_TAIL = 2.0
# Une phrase qui commence par son nom n'est un écho que si elle répète presque tout.
NAMED_ECHO_SIMILARITY = 0.85
# Une phrase sans le nom, entendue peu après la fin d'une fenêtre de relance, est signalée.
RECENT_SECONDS = 20.0


class WakeTarget(Protocol):
    last_reply_text: str
    busy: bool  # en train de réfléchir ou de parler
    awaiting_confirmation: bool  # « Je lance ? » posé, réponse attendue

    def spoke_recently(self, at: float) -> bool: ...  # parlait à cet instant, ou juste avant

    def interrupt(self) -> None: ...
    def acknowledge(self) -> None: ...
    def submit_heard(self, text: str) -> None: ...
    def on_ignored(self, text: str) -> None: ...


class WakeControl:
    """Règles :
    - « Friday, <demande> » : coupe Friday s'il parle, puis traite la demande ;
    - « Friday » seul : il répond « Oui ? » et écoute la phrase suivante sans le nom ;
    - « Friday, stop » : coupe la parole, sans nouvelle demande ; pendant qu'il parle,
      « stop » seul suffit ;
    - juste après une réponse, une relance sans le nom est acceptée quelques secondes ;
    - « Je lance ? » en attente : « oui » / « non » suffit, sans le nom ;
    - ce qui ressemble à ce que Friday vient de dire (son propre écho) est ignoré.
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
        # Au démarrage, aucune fenêtre récente : rien n'est signalé.
        self._follow_up_until = float("-inf")

    def open_follow_up(self) -> None:
        self._follow_up_until = self._clock() + self.follow_up_seconds

    def on_heard(self, text: str, spoken_at: float | None = None) -> None:
        """`spoken_at` : quand la phrase a COMMENCÉ (une longue phrase commencée dans la
        fenêtre de relance compte, même si sa transcription se termine après)."""
        spoken_at = self._clock() if spoken_at is None else spoken_at
        if self._is_echo(text, spoken_at):
            log.info("Ignoré (écho de la voix de Friday) : %s", text)
            return

        # « Je lance ? » en attente : la réponse n'a pas besoin du nom.
        if self.target.awaiting_confirmation:
            command = split_wake_word(text, self.pattern)
            self.target.submit_heard(command or text)
            return

        # Pendant qu'il parle, « stop » suffit (même si Whisper a mal compris le nom).
        if self.target.busy and is_stop_request(text):
            self.target.interrupt()
            return

        command = split_wake_word(text, self.pattern)
        if command is None:
            if spoken_at > self._follow_up_until:
                # Juste après un échange, c'était sans doute pour lui : on le signale.
                if spoken_at - self._follow_up_until < RECENT_SECONDS:
                    self.target.on_ignored(text)
                log.info("Ignoré (pas de « Friday » au début) : %s", text)
                return  # sinon : conversation autour de l'ordinateur, pas pour Friday
            command = text
        self._follow_up_until = float("-inf")  # la fenêtre ne sert qu'une fois

        if is_stop(command):
            self.target.interrupt()
        elif not command:
            self.target.interrupt()
            self.target.acknowledge()
        else:
            self.target.interrupt()
            self.target.submit_heard(command)

    def on_clap(self) -> None:
        """Double clap : comme « Friday » dit seul (« Oui ? », puis la demande sans le nom).
        Ignoré si une confirmation attend sa réponse : un clap n'est ni oui ni non."""
        if self.target.awaiting_confirmation:
            log.info("Double clap ignoré : une confirmation attend sa réponse")
            return
        log.info("Double clap : Friday écoute")
        self.target.interrupt()
        self.target.acknowledge()

    def _is_echo(self, text: str, spoken_at: float) -> bool:
        said = self.target.last_reply_text
        if not said or not self.target.spoke_recently(spoken_at):
            return False
        named = split_wake_word(text, self.pattern) is not None
        return similarity(text, said) >= (NAMED_ECHO_SIMILARITY if named else ECHO_SIMILARITY)

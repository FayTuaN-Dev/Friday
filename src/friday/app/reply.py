"""Déroulé d'une réponse : texte vers l'interface, phrases vers la voix, outils, pop-ups."""

import random
import threading
from collections.abc import Callable, Iterable, Iterator

from friday.app.events import AssistantListener
from friday.brain.events import BrainEvent, ConfirmationRequest, ToolFinished, ToolStarted
from friday.voice.speaker import Speaker
from friday.voice.text import SentenceSplitter

# Dit pendant qu'un outil travaille, pour ne pas laisser de blanc
FILLERS = ("Je regarde ça.", "Un instant.", "Je vérifie.", "Je m'en occupe.")


class Reply:
    def __init__(
        self,
        listener: AssistantListener,
        speaker: Speaker | None,
        interrupted: threading.Event,
        on_confirm: Callable[[ConfirmationRequest], None] = lambda request: request.answer(False),
    ) -> None:
        self.listener = listener
        self.on_confirm = on_confirm  # enregistre la question en attente de « oui » / « non »
        self.speaker = speaker
        self.interrupted = interrupted
        self._splitter = SentenceSplitter()
        self.spoken = ""  # tout ce qui a été envoyé à la voix
        self.tools_used: list[str] = []

    def run(self, events: Iterator[BrainEvent]) -> bool:
        """Joue la réponse jusqu'au bout. Renvoie True si elle a été interrompue."""
        for event in events:
            if self.interrupted.is_set():
                return True
            if isinstance(event, str):
                self.listener.on_reply_chunk(event)
                self._say(self._splitter.feed(event))
            elif isinstance(event, ToolStarted):
                self.tools_used.append(event.name)
                self._say(self._splitter.flush())  # ce qui a été dit avant l'outil
                if not self.spoken:
                    self._say([random.choice(FILLERS)])
                self.listener.on_tool(event.label)
            elif isinstance(event, ConfirmationRequest):
                self._say(self._splitter.flush())
                self._say([event.question])
                self.on_confirm(event)
            elif isinstance(event, ToolFinished) and event.result.display:
                self.listener.on_display(event.result.display)

        self._say(self._splitter.flush())
        if self.speaker:
            self.speaker.wait()
        return self.interrupted.is_set()

    def _say(self, sentences: Iterable[str]) -> None:
        if not self.speaker:
            return
        for sentence in sentences:
            self.speaker.say(sentence)
            self.spoken += f" {sentence}"

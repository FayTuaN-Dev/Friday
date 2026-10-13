"""Déroulé d'une réponse : texte vers l'interface, phrases vers la voix, outils, pop-ups."""

import random
import threading
from collections.abc import Callable, Iterable, Iterator

from friday.app.events import AssistantListener
from friday.app.scene_gate import SceneGate
from friday.brain.events import (
    BrainEvent,
    ConfirmationRequest,
    ThinkingStarted,
    ToolFinished,
    ToolStarted,
)
from friday.voice.speaker import Speaker
from friday.voice.text import SentenceSplitter

# Dit pendant qu'un outil travaille, pour ne pas laisser de blanc
FILLERS = ("Je regarde ça.", "Un instant.", "Je vérifie.", "Je m'en occupe.")
THINKING = (
    "Laissez-moi réfléchir un instant.",
    "Je réfléchis, un instant.",
    "Voyons cela de près.",
)


class Reply:
    def __init__(
        self,
        listener: AssistantListener,
        speaker: Speaker | None,
        interrupted: threading.Event,
        on_confirm: Callable[[ConfirmationRequest], None] = lambda request: request.answer(False),
        scene_gate: SceneGate | None = None,
    ) -> None:
        self.listener = listener
        self.scene_gate = scene_gate  # la voix attend que la scène soit affichée (U8)
        self.on_confirm = on_confirm  # enregistre la question en attente de « oui » / « non »
        self.speaker = speaker
        self.interrupted = interrupted
        self._splitter = SentenceSplitter()
        self.spoken = ""  # tout ce qui a été envoyé à la voix
        self.text = ""  # tout le texte de la réponse (pour le journal)
        self.tools_used: list[str] = []
        self._thinking = False  # pastille « Réflexion approfondie » en cours (U3)

    def run(self, events: Iterator[BrainEvent]) -> bool:
        """Joue la réponse jusqu'au bout. Renvoie True si elle a été interrompue."""
        for event in events:
            if self.interrupted.is_set():
                return True
            if self._thinking and isinstance(event, str | ToolStarted):
                self._thinking = False  # la réflexion est finie : sa pastille passe à ✓
                self.listener.on_tool_done(True)
            if isinstance(event, str):
                self.text += event
                self.listener.on_reply_chunk(event)
                self._say(self._splitter.feed(event))
            elif isinstance(event, ThinkingStarted):  # 10 à 25 s de réflexion : on le dit
                self._say([random.choice(THINKING)])
                self.listener.on_tool("🧠 Réflexion approfondie")
                self._thinking = True
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
            elif isinstance(event, ToolFinished):
                self.listener.on_tool_done(event.result.ok)
                if not event.result.display:
                    continue
                if self.scene_gate is not None:
                    self.scene_gate.expect(event.result.display)
                self.listener.on_display(event.result.display)

        self._say(self._splitter.flush())
        if self.speaker:
            self.speaker.wait()
        return self.interrupted.is_set()

    def _say(self, sentences: Iterable[str]) -> None:
        if not self.speaker:
            return
        for sentence in sentences:
            if self.scene_gate is not None:
                self.scene_gate.wait()  # immédiat, sauf pendant qu'une scène se met en place
            self.speaker.say(sentence)
            self.spoken += f" {sentence}"

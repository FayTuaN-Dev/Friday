"""Ce que le cerveau produit pendant une réponse, en plus du texte."""

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from friday.tools.base import ToolResult


@dataclass
class ToolStarted:
    name: str
    args: dict[str, Any]
    label: str  # ex. « 🔎 Recherche : météo Lyon »


@dataclass
class ToolFinished:
    name: str
    result: ToolResult


@dataclass
class ConfirmationRequest:
    """Un outil sensible attend le feu vert de l'utilisateur (« Je lance ? »).

    Le cerveau attend la réponse dans le thread de l'assistant ; elle arrive d'un autre
    thread (clic dans la fenêtre, « oui » à la voix ou au clavier).
    """

    name: str
    args: dict[str, Any]
    question: str
    approved: bool = False
    _answered: threading.Event = field(default_factory=threading.Event, repr=False)

    @property
    def answered(self) -> bool:
        return self._answered.is_set()

    def answer(self, approved: bool) -> None:
        if not self.answered:
            self.approved = approved
            self._answered.set()

    def wait(self, timeout: float, cancelled: Callable[[], bool] = lambda: False) -> bool:
        """True si l'utilisateur a accepté. Pas de réponse à temps ou interruption : refus."""
        deadline = time.monotonic() + timeout
        while not self._answered.wait(0.1):
            if cancelled() or time.monotonic() > deadline:
                self.answer(False)
        return self.approved


# Une réponse est un flux de morceaux de texte (str) entrecoupés d'événements d'outils.
@dataclass
class ThinkingStarted:
    """Le modèle va réfléchir avant de répondre (calcul, « réfléchis ») : 10 à 25 s."""


BrainEvent = str | ToolStarted | ToolFinished | ConfirmationRequest | ThinkingStarted

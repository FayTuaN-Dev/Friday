"""Confirmation des actions sensibles : Friday demande « Je lance ? » et attend la réponse."""

import logging
import threading

from friday.app.events import AssistantListener
from friday.brain.events import ConfirmationRequest
from friday.tools.base import Display
from friday.voice.wake import normalize

log = logging.getLogger(__name__)

YES = {
    "oui", "ouais", "ok", "okay", "d accord", "vas y", "go", "lance", "lance le", "lance la",
    "c est parti", "confirme", "je confirme", "bien sur", "parfait", "yes", "allez",
    # constaté : pris pour de nouvelles questions (et envoyés à Claude comme telles)
    "valide", "je valide", "envoie", "envoie le", "envoie la", "envoyer", "tu peux envoyer",
    "tu peux y aller", "c est bon", "envoie a claude", "ok envoie", "oui envoie",
}  # fmt: skip
NO = {
    "non", "annule", "annuler", "stop", "laisse tomber", "pas maintenant", "non merci",
    "surtout pas", "attends", "no", "n envoie pas", "ne l envoie pas", "annule l envoi",
    "pas d envoi", "n envoie rien",
}  # fmt: skip


def classify(text: str) -> str:
    """« yes », « no », ou « other » (une autre demande) selon le début de la réponse."""
    words = normalize(text).split()
    for size in (3, 2, 1):
        start = " ".join(words[:size])
        if start in YES:
            return "yes"
        if start in NO:
            return "no"
    return "other"


class ConfirmationGate:
    def __init__(self, listener: AssistantListener) -> None:
        self.listener = listener
        self._pending: ConfirmationRequest | None = None
        self._lock = threading.Lock()

    @property
    def waiting(self) -> bool:
        return self._pending is not None and not self._pending.answered

    def ask(self, request: ConfirmationRequest) -> None:
        with self._lock:
            self._pending = request
        if request.preview is not None:  # montrer EXACTEMENT ce qui partira
            self.listener.on_display(Display(
                "send_preview", "Aperçu de l'envoi",
                {"packet": request.preview, "request": request, "answer": self.answer},
            ))  # fmt: skip
        self.listener.on_confirmation(request.question)

    def answer(self, approved: bool) -> None:
        with self._lock:
            request, self._pending = self._pending, None
        if request and not request.answered:
            request.answer(approved)
            self.listener.on_notice("✅ C'est parti." if approved else "Annulé.")

    def route(self, text: str) -> bool:
        """Si une confirmation est attendue, `text` y répond : renvoie True s'il est
        « consommé » (oui / non). Une autre demande annule et suit son cours (False)."""
        if not self.waiting:
            return False
        verdict = classify(text)
        self.answer(verdict == "yes")
        return verdict != "other"

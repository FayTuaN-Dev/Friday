"""Mémorisation automatique en arrière-plan : après chaque échange, retient ce qui compte."""

import logging
import queue
import threading
from collections.abc import Callable

from friday.memory.extractor import FactExtractor
from friday.memory.service import MemoryService

log = logging.getLogger(__name__)


class MemoryKeeper:
    def __init__(
        self,
        memory: MemoryService,
        extractor: FactExtractor,
        on_saved: Callable[[str], None],
    ) -> None:
        self.memory = memory
        self.extractor = extractor
        self.on_saved = on_saved
        self._queue: queue.Queue[tuple[str, str]] = queue.Queue()
        threading.Thread(target=self._loop, daemon=True, name="memory").start()

    def observe(self, user_text: str, context: str = "") -> None:
        """Appelé après chaque réponse ; le travail se fait sans bloquer la conversation.
        `context` : ce que Friday venait de dire (pour comprendre une réponse courte)."""
        self._queue.put((user_text, context))

    def wait_idle(self) -> None:
        """Pour les tests : attend la fin du travail en cours."""
        self._queue.join()

    def _loop(self) -> None:
        while True:
            text, context = self._queue.get()
            try:
                for fact in self.extractor.extract(text, self.memory.relevant(text), context):
                    memory = self.memory.remember(fact.text, "auto", fact.replaces)
                    self.on_saved(memory.text)
            except Exception:
                log.exception("Échec de la mémorisation automatique")
            finally:
                self._queue.task_done()

"""Déclenche les rappels à l'heure, y compris ceux manqués pendant que Jarvis était fermé."""

import logging
import threading
from collections.abc import Callable
from datetime import datetime

from jarvis.agenda.store import AgendaStore, Reminder

log = logging.getLogger(__name__)


class ReminderScheduler:
    def __init__(
        self,
        store: AgendaStore,
        on_due: Callable[[Reminder, bool], None],  # (rappel, en retard ?)
        clock: Callable[[], datetime] = datetime.now,
        interval: float = 1.0,
    ) -> None:
        self.store = store
        self.on_due = on_due
        self.clock = clock
        self.interval = interval
        self._stop = threading.Event()

    def start(self) -> None:
        # Manqués pendant que Jarvis était fermé : annoncés tout de suite, « en retard ».
        for reminder in self.store.due(self.clock()):
            self._fire(reminder, late=True)
        threading.Thread(target=self._loop, daemon=True, name="reminders").start()

    def stop(self) -> None:
        self._stop.set()

    def check(self) -> None:
        for reminder in self.store.due(self.clock()):
            self._fire(reminder, late=False)

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                self.check()
            except Exception:
                log.exception("Erreur dans le planificateur de rappels")

    def _fire(self, reminder: Reminder, late: bool) -> None:
        if self.store.mark_done(reminder.id):  # une seule fois, même si deux threads passent
            log.info("Rappel n°%d : %s", reminder.id, reminder.text)
            self.on_due(reminder, late)

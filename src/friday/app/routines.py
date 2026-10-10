"""Déclenche les routines à l'heure (J5), et au démarrage celles manquées depuis moins de 3 h.
Une routine due est passée à Friday comme une tâche de fond finie : elle l'annonce (bulle
Windows si elle n'est pas devant) puis fait la demande, avec ses outils."""

import logging
import threading
from collections.abc import Callable
from datetime import datetime

from friday.agenda.routines import RoutineStore, describe_days, spoken_time
from friday.tools.base import ToolResult

log = logging.getLogger(__name__)

TASK = "routine"
CHECK_EVERY = 30  # secondes


def instruction(request: str, name: str) -> str:
    """Ce que Friday reçoit à l'heure dite : faire la demande, pas en parler."""
    return (f"C'est l'heure d'une routine que l'utilisateur a programmée ({name}). Fais "
            f"maintenant ce qu'il a demandé, comme s'il venait de le dire, avec tes outils si "
            f"besoin : « {request} »")  # fmt: skip


class RoutineRunner:
    def __init__(self, store: RoutineStore, on_due: Callable[[str, ToolResult], None],
                 clock: Callable[[], datetime] = datetime.now) -> None:  # fmt: skip
        self.store, self.on_due, self.clock = store, on_due, clock
        self._stop = threading.Event()

    def check(self) -> int:
        """Lance les routines dues ; renvoie combien."""
        now = self.clock()
        due = self.store.due(now)
        for routine, slot in due:
            self.store.mark_run(routine.id, slot)  # avant : jamais deux fois le même créneau
            name = f"{describe_days(routine.days)} à {spoken_time(routine.time)}"
            log.info("Routine %d (%s) : %s", routine.id, name, routine.request)
            self.on_due(TASK, ToolResult(instruction(routine.request, name)))
        return len(due)

    def start(self) -> None:
        def loop() -> None:
            while True:
                try:
                    self.check()
                except Exception:
                    log.exception("Routines : vérification impossible")
                if self._stop.wait(CHECK_EVERY):
                    return

        threading.Thread(target=loop, daemon=True, name="routines").start()

    def stop(self) -> None:
        self._stop.set()

"""Alerte monde (J9) : toutes les 15 min, un événement majeur (alerte rouge GDACS, séisme de
magnitude 7 ou plus) pas encore signalé → une notification DISCRÈTE (Friday ne parle pas :
voir app/notification.py). Les événements signalés sont gardés (data/monde_vu.json)."""

import json
import logging
import threading
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

from friday.tools.base import ToolResult
from friday.world.digest import World, describe
from friday.world.sources import WorldUnavailable
from friday.world.themes import disaster_theme

log = logging.getLogger(__name__)

TASK = "monde"  # tâche de fond silencieuse
CHECK_EVERY = 900  # secondes
WITHIN = timedelta(hours=12)  # plus ancien : déjà connu, on ne le signale plus
KEEP = 200  # identifiants gardés


def alert_text(disaster) -> str:
    theme = disaster_theme(disaster)
    market = f" Ça peut faire bouger {theme.moves}." if theme else ""
    return f"Dis EXACTEMENT : « Alerte monde : {describe(disaster)}.{market} »"


class WorldWatch:
    def __init__(self, world: World, state: Path, on_alert: Callable[[str, ToolResult], None],
                 ) -> None:  # fmt: skip
        self.world, self.state, self.on_alert = world, state, on_alert
        self._stop = threading.Event()

    def seen(self) -> list[str]:
        try:
            return list(json.loads(self.state.read_text("utf-8")))
        except (OSError, ValueError, TypeError):
            return []

    def check(self) -> int:
        """Signale les nouveaux événements majeurs ; renvoie combien."""
        seen = self.seen()
        try:
            new = self.world.new_major(set(seen), WITHIN)
        except WorldUnavailable as error:
            log.info("Alerte monde : %s", error)
            return 0
        if not new:
            return 0
        self.state.parent.mkdir(parents=True, exist_ok=True)
        self.state.write_text(json.dumps((seen + [d.id for d in new])[-KEEP:]), "utf-8")
        for disaster in new:
            log.info("Alerte monde : %s", describe(disaster))
            self.on_alert(TASK, ToolResult(alert_text(disaster)))
        return len(new)

    def start(self) -> None:
        def loop() -> None:
            while True:
                try:
                    self.check()
                except Exception:
                    log.exception("Alerte monde impossible")
                if self._stop.wait(CHECK_EVERY):
                    return

        threading.Thread(target=loop, daemon=True, name="alerte-monde").start()

    def stop(self) -> None:
        self._stop.set()

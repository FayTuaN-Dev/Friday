"""Les limites Claude lues par Friday (data/claude_limits.json, écrit par le relais
claude_status.py à chaque rafraîchissement de la ligne d'état de Claude Code) : ce qu'il
reste de la session (5 h) et de la semaine. Une fenêtre dont l'heure de remise à zéro est
passée repart à 100 % ; des chiffres anciens sont signalés comme tels."""

import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from friday.trading.sessions import DAYS

OLD = 3600  # au-delà d'une heure sans nouvelle, l'âge des chiffres est affiché


@dataclass
class Window:
    label: str
    left: float  # % restant
    resets_at: float | None  # epoch (s)

    def reset_text(self, now: float) -> str:
        if not self.resets_at:
            return ""
        seconds = self.resets_at - now
        when = datetime.fromtimestamp(self.resets_at)
        if seconds < 24 * 3600:
            hours, minutes = int(seconds // 3600), int(seconds % 3600 // 60)
            return f"remise à zéro dans {hours} h {minutes:02d}" if hours else (
                f"remise à zéro dans {minutes} min")  # fmt: skip
        return f"remise à zéro {DAYS[when.weekday()]} à {when:%H:%M}"


@dataclass
class Limits:
    windows: list[Window]
    updated: float

    def age_text(self, now: float) -> str:
        minutes = int((now - self.updated) // 60)
        if now - self.updated < OLD:
            return ""
        return f"chiffres d'il y a {minutes // 60} h {minutes % 60:02d} (mis à jour quand " \
               "Claude Code est utilisé)"  # fmt: skip


def read(path: Path, now: float | None = None) -> Limits | None:
    now = now or time.time()
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    windows = []
    for key, label in (("five_hour", "Session Claude"), ("seven_day", "Semaine Claude")):
        window = data.get(key)
        if not isinstance(window, dict):
            continue
        resets_at = window.get("resets_at")
        expired = isinstance(resets_at, int | float) and resets_at <= now
        left = 100.0 if expired else max(0.0, 100.0 - float(window.get("used", 0)))
        windows.append(Window(label, left, None if expired else resets_at))
    return Limits(windows, float(data.get("updated", now))) if windows else None

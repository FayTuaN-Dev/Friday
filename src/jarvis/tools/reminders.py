"""Outils : minuteurs et rappels."""

from collections.abc import Callable
from datetime import datetime

from jarvis.agenda.store import AgendaStore
from jarvis.agenda.times import describe, resolve
from jarvis.tools.base import Display, Tool, ToolResult

DAY_HELP = "aujourd'hui, demain, après-demain, ou un jour de la semaine (lundi…)"


class SetTimerTool(Tool):
    name = "set_timer"
    description = (
        "Lance un minuteur (compte à rebours). Donne la durée EXACTEMENT comme l'utilisateur "
        "l'a dite (« 10 minutes », « une heure et demie »), sans la convertir."
    )
    parameters = {
        "duration": {"type": "string", "description": "La durée telle que dite : « 10 minutes »"},
        "label": {"type": "string", "description": "Nom facultatif (« pâtes », « lessive »…)"},
    }
    required = ("duration",)

    def __init__(self, store: AgendaStore, clock: Callable[[], datetime] = datetime.now):
        self.store, self.clock = store, clock

    def label(self, args: dict) -> str:
        return f"⏲️ Minuteur : {args.get('duration', '')}"

    def run(self, duration: str, label: str = "") -> ToolResult:
        now = self.clock()
        try:
            due = resolve(now, delay=duration)
        except ValueError as e:
            return ToolResult(f"Minuteur non lancé : {e}. Demande la durée.")
        if label.strip().lower() in ("minuteur", "timer", "compte à rebours"):
            label = ""  # « Minuteur Minuteur terminé » sinon
        text = f"Minuteur {label or f'de {duration}'} terminé"
        self.store.add_reminder(text, due)
        return ToolResult(f"Minuteur de {duration} lancé, il sonnera à {due:%H:%M:%S}.")


class SetReminderTool(Tool):
    name = "set_reminder"
    description = (
        "Programme un rappel. Donne SOIT « delay », le délai EXACTEMENT comme l'utilisateur "
        "l'a dit (« 2 minutes », « une heure »), SOIT « time » (« 18:00 ») avec éventuellement "
        f"« day » ({DAY_HELP}). Ne convertis et ne calcule rien toi-même."
    )
    parameters = {
        "text": {"type": "string", "description": "Ce qu'il faut rappeler (« appeler maman »)"},
        "delay": {"type": "string", "description": "Délai tel que dit : « 2 minutes »"},
        "time": {"type": "string", "description": "Heure, format HH:MM"},
        "day": {"type": "string", "description": DAY_HELP},
    }
    required = ("text",)

    def __init__(self, store: AgendaStore, clock: Callable[[], datetime] = datetime.now):
        self.store, self.clock = store, clock

    def label(self, args: dict) -> str:
        return f"⏰ Rappel : {args.get('text', '')}"

    def run(self, text: str, delay: str | None = None, time: str | None = None,
            day: str | None = None) -> ToolResult:  # fmt: skip
        now = self.clock()
        try:
            due = resolve(now, delay, time, day)
        except ValueError as e:
            return ToolResult(f"Rappel non programmé : {e}. Demande une précision.")
        reminder = self.store.add_reminder(text, due)
        return ToolResult(f"Rappel n°{reminder.id} programmé {describe(due, now)} : {text}.")


class ListRemindersTool(Tool):
    name = "list_reminders"
    description = "Affiche les rappels et minuteurs à venir."
    parameters = {}

    def __init__(self, store: AgendaStore, clock: Callable[[], datetime] = datetime.now):
        self.store, self.clock = store, clock

    def label(self, args: dict) -> str:
        return "⏰ Rappels"

    def run(self) -> ToolResult:
        pending, now = self.store.pending(), self.clock()
        if not pending:
            return ToolResult("Aucun rappel à venir.")
        lines = [f"[{r.id}] {describe(r.due_at, now)} : {r.text}" for r in pending]
        items = [{"text": r.text, "meta": f"n°{r.id} · {describe(r.due_at, now)}"}
                 for r in pending]  # fmt: skip
        return ToolResult(
            "Rappels à venir (affichés à l'écran) :\n" + "\n".join(lines),
            Display("items", "Rappels à venir", {"icon": "⏰", "items": items}),
        )


class CancelReminderTool(Tool):
    name = "cancel_reminder"
    description = "Annule un rappel ou un minuteur, par son numéro (voir list_reminders)."
    parameters = {"reminder_id": {"type": "integer", "description": "Numéro du rappel"}}
    required = ("reminder_id",)

    def __init__(self, store: AgendaStore) -> None:
        self.store = store

    def label(self, args: dict) -> str:
        return f"⏰ Annulation du rappel n°{args.get('reminder_id')}"

    def run(self, reminder_id: int) -> ToolResult:
        if self.store.mark_done(int(reminder_id)):
            return ToolResult(f"Rappel n°{reminder_id} annulé.")
        return ToolResult(f"Pas de rappel en attente n°{reminder_id}.")

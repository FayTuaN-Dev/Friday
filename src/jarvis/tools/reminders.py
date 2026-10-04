"""Outils : minuteurs et rappels."""

from collections.abc import Callable
from datetime import datetime

from jarvis.agenda.store import AgendaStore
from jarvis.agenda.times import describe, resolve
from jarvis.tools.base import Display, Tool, ToolResult

DAY_HELP = "aujourd'hui, demain, après-demain, ou un jour de la semaine (lundi…)"


class SetTimerTool(Tool):
    name = "set_timer"
    description = "Lance un minuteur (compte à rebours). Exemple : « minuteur de 10 minutes »."
    parameters = {
        "minutes": {"type": "number", "description": "Durée en minutes (0.5 = 30 secondes)"},
        "label": {"type": "string", "description": "Nom facultatif (« pâtes », « lessive »…)"},
    }
    required = ("minutes",)

    def __init__(self, store: AgendaStore, clock: Callable[[], datetime] = datetime.now):
        self.store, self.clock = store, clock

    def label(self, args: dict) -> str:
        return f"⏲️ Minuteur : {args.get('minutes')} min"

    def run(self, minutes: float, label: str = "") -> ToolResult:
        if float(minutes) <= 0:
            return ToolResult("Durée invalide.")
        now = self.clock()
        text = f"Minuteur {label or f'de {minutes:g} minutes'} terminé"
        reminder = self.store.add_reminder(text, resolve(now, delay_minutes=minutes))
        return ToolResult(f"Minuteur lancé, il sonnera à {reminder.due_at:%H:%M:%S}.")


class SetReminderTool(Tool):
    name = "set_reminder"
    description = (
        "Programme un rappel. Donne SOIT « delay_minutes » (« dans 2 heures » = 120), SOIT "
        f"« time » (« 18:00 ») avec éventuellement « day » ({DAY_HELP}). Ne calcule jamais "
        "de date toi-même."
    )
    parameters = {
        "text": {"type": "string", "description": "Ce qu'il faut rappeler (« appeler maman »)"},
        "delay_minutes": {"type": "number", "description": "Dans combien de minutes"},
        "time": {"type": "string", "description": "Heure, format HH:MM"},
        "day": {"type": "string", "description": DAY_HELP},
    }
    required = ("text",)

    def __init__(self, store: AgendaStore, clock: Callable[[], datetime] = datetime.now):
        self.store, self.clock = store, clock

    def label(self, args: dict) -> str:
        return f"⏰ Rappel : {args.get('text', '')}"

    def run(self, text: str, delay_minutes: float | None = None, time: str | None = None,
            day: str | None = None) -> ToolResult:  # fmt: skip
        now = self.clock()
        try:
            due = resolve(now, delay_minutes, time, day)
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

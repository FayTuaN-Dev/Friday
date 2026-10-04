"""Quand un rappel arrive à échéance : carillon, puis Friday l'annonce de lui-même."""

from collections.abc import Callable

from friday.agenda.scheduler import ReminderScheduler
from friday.agenda.store import AgendaStore, Reminder
from friday.tools.base import ToolResult
from friday.voice.speaker import Speaker


def announcement(reminder: Reminder, late: bool) -> str:
    """Consigne pour le LLM (passée par la file de l'assistant, comme une fin de tâche)."""
    when = (
        f" Il était prévu à {reminder.due_at:%H:%M} le {reminder.due_at:%d/%m}, pendant que "
        "Friday était fermé : signale le retard."
        if late
        else ""
    )
    return (
        f"RAPPEL : {reminder.text}.{when} Annonce-le maintenant à l'utilisateur en une "
        "phrase courte, qui commence par « Rappel »."
    )


def start_reminders(
    store: AgendaStore,
    speaker: Callable[[], Speaker | None],
    on_background: Callable[[str, ToolResult], None],
) -> ReminderScheduler:
    def on_due(reminder: Reminder, late: bool) -> None:
        if (voice := speaker()) is not None:
            voice.chime()
        on_background("rappel", ToolResult(announcement(reminder, late)))

    scheduler = ReminderScheduler(store, on_due)
    scheduler.start()
    return scheduler

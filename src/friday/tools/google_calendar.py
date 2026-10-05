"""Outils : agenda Google (voir, ajouter, déplacer et supprimer avec confirmation)."""

from datetime import datetime

from friday.agenda.times import parse_time
from friday.brain.prompts import french_date
from friday.google.calendar import Event, GoogleCalendar
from friday.google.days import parse_day, parse_period
from friday.tools.base import Display, Tool, ToolResult
from friday.tools.google_base import guarded


def event_line(event: Event, with_day: bool) -> str:
    day = f"{french_date(event.start)}, " if with_day else ""
    where = f" ({event.location})" if event.location else ""
    return f"{day}{event.when()} : {event.title}{where}"


def at(day: str, time: str | None, now: datetime) -> datetime:
    hour, minute = parse_time(time) if time else (0, 0)
    return datetime.combine(
        parse_day(day or "aujourd'hui", now.date()), datetime.min.time()
    ).replace(hour=hour, minute=minute)


class ListEventsTool(Tool):
    name = "list_events"
    description = (
        "Montre l'agenda Google : « qu'est-ce que j'ai aujourd'hui / demain / jeudi / cette "
        "semaine ? ». Donne aussi l'identifiant des événements, nécessaire pour les déplacer "
        "ou les supprimer."
    )
    parameters = {
        "period": {
            "type": "string",
            "description": "Tel que dit : aujourd'hui, demain, jeudi, le 12 novembre, cette "
            "semaine, la semaine prochaine, ce week-end",
        }
    }

    def __init__(self, calendar: GoogleCalendar) -> None:
        self.calendar = calendar

    def label(self, args: dict) -> str:
        return f"📅 Agenda : {args.get('period') or 'aujourd’hui'}"

    def run(self, period: str = "aujourd'hui") -> ToolResult:
        return guarded(lambda: self._list(period))

    def _list(self, period: str) -> ToolResult:
        first, last = parse_period(period, datetime.now().date())
        events = self.calendar.between(first, last)
        span = (
            french_date(first)
            if first == last
            else f"du {french_date(first)} au {french_date(last)}"
        )
        if not events:
            return ToolResult(f"Rien de prévu dans l'agenda ({span}).")
        several_days = first != last
        lines = [f"- {event_line(e, several_days)} [id : {e.id}]" for e in events]
        items = [{"text": e.title, "meta": event_line(e, True).rsplit(" : ", 1)[0]} for e in events]
        return ToolResult(
            f"Agenda ({span}), affiché à l'écran :\n"
            + "\n".join(lines)
            + "\nNe lis pas les identifiants à voix haute.",
            Display("items", f"Agenda : {period}", {"icon": "📅", "items": items}),
        )


class AddEventTool(Tool):
    name = "add_event"
    description = (
        "Ajoute un événement à l'agenda Google (« ajoute dentiste jeudi à 14 h »). Sans heure, "
        "l'événement dure toute la journée. Recopie le jour et l'heure tels que dits."
    )
    parameters = {
        "title": {"type": "string", "description": "Titre de l'événement"},
        "day": {
            "type": "string",
            "description": "Jour tel que dit (demain, jeudi, le 12 novembre)",
        },
        "time": {"type": "string", "description": "Heure (14:00), vide = toute la journée"},
        "duration_minutes": {"type": "integer", "description": "Durée (60 par défaut)"},
        "location": {"type": "string", "description": "Lieu, si précisé"},
    }
    required = ("title", "day")

    def __init__(self, calendar: GoogleCalendar) -> None:
        self.calendar = calendar

    def label(self, args: dict) -> str:
        return f"📅 Ajout : {args.get('title', '')}"

    def run(self, title: str, day: str, time: str = "", duration_minutes: int | None = None,
            location: str = "") -> ToolResult:  # fmt: skip
        def add() -> ToolResult:
            start = at(day, time, datetime.now())
            event = self.calendar.add(title, start, duration_minutes, location, all_day=not time)
            return ToolResult(f"Ajouté à l'agenda : {event_line(event, True)}.")

        return guarded(add)


class MoveEventTool(Tool):
    name = "move_event"
    description = "Déplace un événement de l'agenda (id donné par list_events), durée conservée."
    parameters = {
        "event_id": {"type": "string", "description": "Identifiant (voir list_events)"},
        "day": {"type": "string", "description": "Nouveau jour, tel que dit"},
        "time": {"type": "string", "description": "Nouvelle heure (14:00)"},
    }
    required = ("event_id", "time")
    needs_confirmation = True

    def __init__(self, calendar: GoogleCalendar) -> None:
        self.calendar = calendar

    def label(self, args: dict) -> str:
        return "📅 Déplacement d'un événement"

    def confirmation(self, args: dict) -> str:
        try:
            event = self.calendar.get(args.get("event_id", ""))
            new = at(args.get("day") or "", args.get("time"), datetime.now())
        except Exception:
            return "Je déplace cet événement ?"
        return f"Je déplace « {event.title} » au {french_date(new)} à {new:%H:%M} ?"

    def run(self, event_id: str, time: str, day: str = "") -> ToolResult:
        def move() -> ToolResult:
            event = self.calendar.move(self.calendar.get(event_id), at(day, time, datetime.now()))
            return ToolResult(f"Déplacé : {event_line(event, True)}.")

        return guarded(move)


class DeleteEventTool(Tool):
    name = "delete_event"
    description = "Supprime un événement de l'agenda (id donné par list_events)."
    parameters = {"event_id": {"type": "string", "description": "Identifiant (voir list_events)"}}
    required = ("event_id",)
    needs_confirmation = True

    def __init__(self, calendar: GoogleCalendar) -> None:
        self.calendar = calendar

    def label(self, args: dict) -> str:
        return "📅 Suppression d'un événement"

    def confirmation(self, args: dict) -> str:
        try:
            event = self.calendar.get(args.get("event_id", ""))
        except Exception:
            return "Je supprime cet événement de l'agenda ?"
        return f"Je supprime « {event.title} » ({event_line(event, True).rsplit(' : ', 1)[0]}) ?"

    def run(self, event_id: str) -> ToolResult:
        def delete() -> ToolResult:
            self.calendar.delete(event_id)
            return ToolResult("Événement supprimé de l'agenda.")

        return guarded(delete)

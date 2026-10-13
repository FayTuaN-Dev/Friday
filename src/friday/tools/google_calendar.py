"""Outils : agenda Google (voir, ajouter, déplacer et supprimer avec confirmation)."""

from datetime import datetime

from friday.agenda.times import parse_time
from friday.brain.prompts import french_date
from friday.google.calendar import Event, GoogleCalendar
from friday.google.days import parse_day, parse_period
from friday.google.event_ref import EventNotFound, RecentEvents, find_event
from friday.tools.base import Display, Tool, ToolResult
from friday.tools.google_base import guarded

CALENDAR_DAY = "https://calendar.google.com/calendar/r/day/"  # + AAAA/MM/JJ


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
        "semaine ? ». Les événements sont numérotés : « déplace le 2 » ou « supprime le 1 » "
        "font référence à cette liste."
    )
    parameters = {
        "period": {
            "type": "string",
            "description": "Tel que dit : aujourd'hui, demain, jeudi, le 12 novembre, cette "
            "semaine, la semaine prochaine, ce week-end",
        }
    }

    def __init__(self, calendar: GoogleCalendar, recent: RecentEvents) -> None:
        self.calendar = calendar
        self.recent = recent

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
        self.recent.remember(events)
        lines = [f"[{i}] {event_line(e, several_days)}" for i, e in enumerate(events, 1)]
        items = [{"text": e.title, "meta": event_line(e, True).rsplit(" : ", 1)[0],
                  "url": f"{CALENDAR_DAY}{e.start:%Y/%m/%d}"} for e in events]  # fmt: skip
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

    def __init__(self, calendar: GoogleCalendar, recent: RecentEvents) -> None:
        self.calendar = calendar
        self.recent = recent

    def label(self, args: dict) -> str:
        return f"📅 Ajout : {args.get('title', '')}"

    def run(self, title: str, day: str, time: str = "", duration_minutes: int | None = None,
            location: str = "") -> ToolResult:  # fmt: skip
        def add() -> ToolResult:
            start = at(day, time, datetime.now())
            event = self.calendar.add(title, start, duration_minutes, location, all_day=not time)
            self.recent.remember([event])  # « supprime-le » juste après
            return ToolResult(f"Ajouté à l'agenda : {event_line(event, True)}.")

        return guarded(add)


EVENT_REF = {
    "type": "string",
    "description": "L'événement : son numéro dans la dernière liste, ou quelques mots de son "
    "titre (« banque »), ou vide pour celui dont on vient de parler",
}


class _ChangeEventTool(Tool):
    """Déplacer / supprimer : l'utilisateur confirme, et seul l'événement exact nommé dans la
    question est touché. Introuvable : pas de question, run() explique pourquoi."""

    needs_confirmation = True

    def __init__(self, calendar: GoogleCalendar, recent: RecentEvents) -> None:
        self.calendar = calendar
        self.recent = recent
        self._pending: tuple | None = None  # (référence, événement) confirmés

    def _find(self, ref: str) -> Event:
        return find_event(ref, self.recent, self.calendar, datetime.now().date())

    def _prepare(self, args: dict) -> str | None:
        try:
            event = self._find(args.get("event", ""))
        except Exception:
            self._pending = None
            return None
        self._pending = (args.get("event", ""), event)
        return self.question(event, args)

    def confirmation(self, args: dict) -> str | None:
        return self._prepare(args)

    def _confirmed(self, ref: str) -> Event:
        pending, self._pending = self._pending, None
        if pending is None or pending[0] != ref:
            self._find(ref)  # lève EventNotFound avec la raison
            raise EventNotFound("rien n'a été confirmé pour cet événement")
        return pending[1]

    def question(self, event: Event, args: dict) -> str:
        raise NotImplementedError


class MoveEventTool(_ChangeEventTool):
    name = "move_event"
    description = "Déplace un événement de l'agenda (durée conservée), après confirmation."
    parameters = {
        "event": EVENT_REF,
        "day": {"type": "string", "description": "Nouveau jour, tel que dit"},
        "time": {"type": "string", "description": "Nouvelle heure (14:00)"},
    }
    required = ("time",)

    def label(self, args: dict) -> str:
        return "📅 Déplacement d'un événement"

    def question(self, event: Event, args: dict) -> str:
        new = at(args.get("day") or "", args.get("time"), datetime.now())
        return f"Je déplace « {event.title} » au {french_date(new)} à {new:%H:%M} ?"

    def run(self, time: str, event: str = "", day: str = "") -> ToolResult:
        def move() -> ToolResult:
            moved = self.calendar.move(self._confirmed(event), at(day, time, datetime.now()))
            self.recent.remember([moved])
            return ToolResult(f"Déplacé : {event_line(moved, True)}.")

        return guarded(move)


class DeleteEventTool(_ChangeEventTool):
    name = "delete_event"
    description = "Supprime un événement de l'agenda Google (jamais un mail), après confirmation."
    parameters = {"event": EVENT_REF}

    def label(self, args: dict) -> str:
        return "📅 Suppression d'un événement"

    def question(self, event: Event, args: dict) -> str:
        return f"Je supprime « {event.title} » ({event_line(event, True).rsplit(' : ', 1)[0]}) ?"

    def run(self, event: str = "") -> ToolResult:
        def delete() -> ToolResult:
            try:
                target = self._confirmed(event)
            except EventNotFound as error:  # souvent : il parlait de mails, pas d'agenda
                return ToolResult(
                    f"Rien supprimé : aucun événement de l'agenda ne correspond ({error}). Si "
                    "l'utilisateur parlait de MAILS, c'est l'outil trash_mails qu'il fallait "
                    "utiliser : appelle-le ; sinon, demande-lui de préciser l'événement."
                )
            self.calendar.delete(target.id)
            self.recent.remember([])
            return ToolResult(f"« {target.title} » supprimé de l'agenda.")

        return guarded(delete)

"""Agenda Google (calendrier principal) : lire, ajouter, déplacer, supprimer des événements."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta


@dataclass
class Event:
    id: str
    title: str
    start: datetime  # heure locale (minuit pour un événement « toute la journée »)
    end: datetime
    all_day: bool = False
    location: str = ""

    def when(self) -> str:
        if self.all_day:
            return "toute la journée"
        return f"{self.start:%H:%M}–{self.end:%H:%M}"


def _local(moment: datetime) -> datetime:
    return moment.astimezone().replace(tzinfo=None) if moment.tzinfo else moment


def _aware(moment: datetime) -> str:
    return moment.astimezone().isoformat()  # heure locale avec son fuseau, pour Google


def parse_event(item: dict) -> Event:
    start, end = item.get("start", {}), item.get("end", {})
    all_day = "date" in start
    if all_day:
        begin = datetime.combine(date.fromisoformat(start["date"]), time())
        finish = datetime.combine(date.fromisoformat(end.get("date", start["date"])), time())
    else:
        begin = _local(datetime.fromisoformat(start["dateTime"]))
        finish = _local(datetime.fromisoformat(end.get("dateTime", start["dateTime"])))
    return Event(item["id"], item.get("summary") or "(sans titre)", begin, finish, all_day,
                 item.get("location", ""))  # fmt: skip


class GoogleCalendar:
    def __init__(self, service: Callable[[], object]) -> None:
        self._service = service  # appelé à chaque fois : le compte peut se connecter en route

    def _events(self):
        return self._service().events()

    def between(self, first: date, last: date) -> list[Event]:
        """Événements du premier au dernier jour inclus, dans l'ordre."""
        begin = datetime.combine(first, time())
        end = datetime.combine(last + timedelta(days=1), time())
        response = self._events().list(
            calendarId="primary", timeMin=_aware(begin), timeMax=_aware(end),
            singleEvents=True, orderBy="startTime", maxResults=50,
        ).execute()  # fmt: skip
        return [parse_event(item) for item in response.get("items", [])]

    def add(self, title: str, start: datetime, minutes: int | None, location: str = "",
            all_day: bool = False) -> Event:  # fmt: skip
        body: dict = {"summary": title}
        if location:
            body["location"] = location
        if all_day:
            body["start"] = {"date": start.date().isoformat()}
            body["end"] = {"date": (start.date() + timedelta(days=1)).isoformat()}
        else:
            body["start"] = {"dateTime": _aware(start)}
            body["end"] = {"dateTime": _aware(start + timedelta(minutes=minutes or 60))}
        return parse_event(self._events().insert(calendarId="primary", body=body).execute())

    def move(self, event: Event, start: datetime) -> Event:
        """Déplace en gardant la durée."""
        duration = event.end - event.start
        body = {"start": {"dateTime": _aware(start)}, "end": {"dateTime": _aware(start + duration)}}
        return parse_event(
            self._events().patch(calendarId="primary", eventId=event.id, body=body).execute()
        )

    def delete(self, event_id: str) -> None:
        self._events().delete(calendarId="primary", eventId=event_id).execute()

    def get(self, event_id: str) -> Event:
        return parse_event(self._events().get(calendarId="primary", eventId=event_id).execute())

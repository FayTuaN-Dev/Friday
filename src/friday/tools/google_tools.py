"""Outils du compte Google : agenda et Gmail."""

from friday.google.calendar import GoogleCalendar
from friday.google.event_ref import RecentEvents
from friday.google.gmail import Gmail
from friday.tools.base import Tool


def google_tools(account) -> list[Tool]:
    from friday.tools.gmail import CheckMailTool, ReadMailTool, SearchMailTool, SendMailTool
    from friday.tools.google_calendar import (
        AddEventTool,
        DeleteEventTool,
        ListEventsTool,
        MoveEventTool,
    )

    calendar = GoogleCalendar(lambda: account.service("calendar", "v3"))
    recent = RecentEvents()  # partagé : « supprime le 2 » renvoie à la dernière liste
    gmail = Gmail(lambda: account.service("gmail", "v1"))
    return [
        ListEventsTool(calendar, recent), AddEventTool(calendar, recent),
        MoveEventTool(calendar, recent), DeleteEventTool(calendar, recent),
        CheckMailTool(gmail), SearchMailTool(gmail), ReadMailTool(gmail), SendMailTool(gmail),
    ]  # fmt: skip

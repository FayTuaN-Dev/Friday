"""Outils du compte Google : agenda et Gmail."""

from friday.google.calendar import GoogleCalendar
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
    gmail = Gmail(lambda: account.service("gmail", "v1"))
    return [
        ListEventsTool(calendar), AddEventTool(calendar), MoveEventTool(calendar),
        DeleteEventTool(calendar), CheckMailTool(gmail), SearchMailTool(gmail),
        ReadMailTool(gmail), SendMailTool(gmail),
    ]  # fmt: skip

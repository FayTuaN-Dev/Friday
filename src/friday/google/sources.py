"""Ce que le briefing du matin tire du compte Google (agenda du jour, mails non lus)."""

from datetime import date

from friday.google.calendar import GoogleCalendar
from friday.google.gmail import Gmail


def calendar_lines(account, day: date) -> list[str]:
    events = GoogleCalendar(lambda: account.service("calendar", "v3")).between(day, day)
    return [f"{e.when()} : {e.title}" + (f" ({e.location})" if e.location else "") for e in events]


def unread_lines(account) -> list[str]:
    mails = Gmail(lambda: account.service("gmail", "v1")).unread(limit=5)
    return [f"{m.sender_name} : « {m.subject} »" for m in mails]

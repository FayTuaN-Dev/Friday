"""Outils du compte Google : agenda et Gmail."""

from friday.google.calendar import GoogleCalendar
from friday.google.event_ref import RecentEvents
from friday.google.gmail import Gmail
from friday.tools.base import Tool


def google_tools(account, settings, on_background=None) -> list[Tool]:
    import ollama

    from friday.google.mailbox import Mailbox
    from friday.google.sorter import Classifier, MailSorter
    from friday.tools.gmail import CheckMailTool, ReadMailTool, SearchMailTool, SendMailTool
    from friday.tools.google_calendar import (
        AddEventTool,
        DeleteEventTool,
        ListEventsTool,
        MoveEventTool,
    )
    from friday.tools.mail_sorting import CategoryMailsTool, SortMailsTool
    from friday.tools.mail_trash import TrashMailsTool

    calendar = GoogleCalendar(lambda: account.service("calendar", "v3"))
    mailbox = Mailbox(lambda: account.service("gmail", "v1"))
    classify = Classifier(ollama.Client(host=settings.ollama_host), settings.ollama_model,
                          settings.ollama_num_ctx)  # fmt: skip
    recent = RecentEvents()  # partagé : « supprime le 2 » renvoie à la dernière liste
    gmail = Gmail(lambda: account.service("gmail", "v1"))
    return [
        ListEventsTool(calendar, recent), AddEventTool(calendar, recent),
        MoveEventTool(calendar, recent), DeleteEventTool(calendar, recent),
        CheckMailTool(gmail), SearchMailTool(gmail), ReadMailTool(gmail), SendMailTool(gmail),
        SortMailsTool(MailSorter(mailbox, classify), on_background), CategoryMailsTool(mailbox),
        TrashMailsTool(mailbox),
    ]  # fmt: skip

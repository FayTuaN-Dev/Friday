import base64
from datetime import date, datetime, timedelta

import pytest

from friday.google.calendar import GoogleCalendar, parse_event
from friday.google.days import parse_day, parse_period
from friday.google.event_ref import RecentEvents
from friday.google.gmail import Gmail, extract_body, html_to_text
from friday.tools.gmail import CheckMailTool, SendMailTool
from friday.tools.google_calendar import (
    AddEventTool,
    DeleteEventTool,
    ListEventsTool,
    MoveEventTool,
)

TODAY = date(2026, 10, 6)  # un mardi


def local(*moment) -> str:
    """Heure locale de la machine, au format Google (la CI tourne en UTC, pas à Paris)."""
    return datetime(*moment).astimezone().isoformat()


@pytest.mark.parametrize(
    ("said", "expected"),
    [
        ("aujourd'hui", date(2026, 10, 6)),
        ("demain matin", date(2026, 10, 7)),
        ("jeudi", date(2026, 10, 8)),
        ("jeudi prochain", date(2026, 10, 8)),
        ("lundi", date(2026, 10, 12)),
        ("le 12 novembre", date(2026, 11, 12)),
        ("12 mars", date(2027, 3, 12)),  # déjà passé cette année : l'an prochain
        ("le 20", date(2026, 10, 20)),
        ("le 2", date(2026, 11, 2)),  # passé ce mois-ci : le mois prochain
        ("12/11", date(2026, 11, 12)),
        ("2026-12-24", date(2026, 12, 24)),
        ("1er décembre", date(2026, 12, 1)),
    ],
)
def test_parse_day(said, expected):
    assert parse_day(said.replace("1er", "1"), TODAY) == expected


def test_parse_period_and_bad_days():
    assert parse_period("cette semaine", TODAY) == (TODAY, date(2026, 10, 11))
    assert parse_period("la semaine prochaine", TODAY) == (date(2026, 10, 12), date(2026, 10, 18))
    assert parse_period("ce week-end", TODAY) == (date(2026, 10, 10), date(2026, 10, 11))
    assert parse_period("demain", TODAY) == (date(2026, 10, 7),) * 2
    with pytest.raises(ValueError):
        parse_day("un jour peut-être", TODAY)
    with pytest.raises(ValueError):
        parse_day("31 février", TODAY)


class Call:
    """Imite googleapiclient : resource.method(**kwargs).execute()."""

    def __init__(self, log, name, result):
        self.log, self.name, self.result = log, name, result

    def __call__(self, **kwargs):
        self.log.append((self.name, kwargs))
        return self

    def execute(self):
        return self.result(self.log[-1][1]) if callable(self.result) else self.result


class FakeEvents:
    def __init__(self, items):
        self.items, self.log = items, []

    def __getattr__(self, name):
        results = {
            "list": {"items": self.items},
            "insert": lambda kw: {"id": "new", **kw["body"]},
            "get": lambda kw: next(i for i in self.items if i["id"] == kw["eventId"]),
            "delete": {},
            "patch": lambda kw: {**self.items[0], **kw["body"]},
        }
        return Call(self.log, name, results[name])


def calendar_with(items):
    events = FakeEvents(items)
    service = type("S", (), {"events": lambda self: events})()
    return GoogleCalendar(lambda: service), events


DENTIST = {"id": "e1", "summary": "Dentiste", "location": "Bordeaux",
           "start": {"dateTime": local(2026, 10, 8, 14)},
           "end": {"dateTime": local(2026, 10, 8, 15)}}  # fmt: skip
HOLIDAY = {"id": "e2", "summary": "Férié", "start": {"date": "2026-11-11"},
           "end": {"date": "2026-11-12"}}  # fmt: skip


def test_parse_events():
    event = parse_event(DENTIST)
    assert (event.title, event.when(), event.location) == ("Dentiste", "14:00–15:00", "Bordeaux")
    assert parse_event(HOLIDAY).all_day and parse_event(HOLIDAY).when() == "toute la journée"


def test_list_events_tool():
    calendar, events = calendar_with([DENTIST, HOLIDAY])
    result = ListEventsTool(calendar, RecentEvents()).run("cette semaine")
    assert "[1] jeudi 8 octobre 2026, 14:00–15:00 : Dentiste (Bordeaux)" in result.text
    assert result.display.data["items"][0]["text"] == "Dentiste"
    assert events.log[0][1]["singleEvents"] is True
    empty, _ = calendar_with([])
    assert "Rien de prévu" in ListEventsTool(empty, RecentEvents()).run("demain").text
    assert "pas compris" in ListEventsTool(empty, RecentEvents()).run("un jour peut-être").text


def test_add_event_timed_and_all_day():
    calendar, events = calendar_with([])
    AddEventTool(calendar, RecentEvents()).run("Dentiste", "demain", "14h30", 30)
    body = events.log[-1][1]["body"]
    start = datetime.fromisoformat(body["start"]["dateTime"])
    end = datetime.fromisoformat(body["end"]["dateTime"])
    assert (start.hour, start.minute, end - start) == (14, 30, timedelta(minutes=30))
    assert start.date() == date.today() + timedelta(days=1)
    AddEventTool(calendar, RecentEvents()).run("Anniversaire de Léa", "le 12 novembre")
    assert "date" in events.log[-1][1]["body"]["start"]  # sans heure : toute la journée


BANK = {"id": "e3", "summary": "Rendez-vous à la banque",
        "start": {"dateTime": local(2026, 10, 9, 11)},
        "end": {"dateTime": local(2026, 10, 9, 12)}}  # fmt: skip


def deleted(events):
    return [kw["eventId"] for name, kw in events.log if name == "delete"]


def test_delete_by_number_from_the_last_list():
    calendar, events = calendar_with([DENTIST, BANK])
    recent = RecentEvents()
    ListEventsTool(calendar, recent).run("cette semaine")
    tool = DeleteEventTool(calendar, recent)
    assert tool.needs_confirmation
    assert "« Rendez-vous à la banque »" in tool.confirmation({"event": "2"})
    assert "supprimé" in tool.run("2").text and deleted(events) == ["e3"]


def test_delete_it_right_after_adding():
    calendar, events = calendar_with([])
    recent = RecentEvents()
    AddEventTool(calendar, recent).run("Coiffeur", "samedi", "10:00")
    tool = DeleteEventTool(calendar, recent)
    assert "« Coiffeur »" in tool.confirmation({"event": ""})  # « supprime-le »
    tool.run("")
    assert deleted(events) == ["new"]


def test_find_by_title_words_ambiguous_or_missing():
    calendar, events = calendar_with([DENTIST, BANK, {**BANK, "id": "e4"}])
    tool = DeleteEventTool(calendar, RecentEvents())
    assert tool.confirmation({"event": "dentiste"}).startswith("Je supprime « Dentiste »")
    tool.run("dentiste")
    assert deleted(events) == ["e1"]
    for ref in ("banque", "piscine", "1"):  # deux banques ; rien ; pas de liste récente
        assert tool.confirmation({"event": ref}) is None  # pas de question inutile
        assert "pas compris" in tool.run(ref).text
    assert deleted(events) == ["e1"]  # rien d'autre n'a été supprimé


def test_move_only_the_confirmed_event():
    calendar, events = calendar_with([DENTIST])
    tool = MoveEventTool(calendar, RecentEvents())
    assert "« Dentiste »" in tool.confirmation({"event": "dentiste", "day": "vendredi",
                                                 "time": "16:00"})  # fmt: skip
    assert "Déplacé" in tool.run("16:00", "dentiste", "vendredi").text
    assert "pas compris" in tool.run("17:00", "dentiste", "samedi").text  # sans confirmation
    assert [name for name, _ in events.log].count("patch") == 1


def b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def test_mail_bodies():
    assert html_to_text("<p>Bonjour&nbsp;Val</p><script>x()</script><br>À bientôt") == (
        "Bonjour\xa0Val\n\nÀ bientôt"
    )
    multipart = {"mimeType": "multipart/alternative", "parts": [
        {"mimeType": "text/html", "body": {"data": b64("<b>HTML</b>")}},
        {"mimeType": "text/plain", "body": {"data": b64("Texte brut")}}]}  # fmt: skip
    assert extract_body(multipart) == "Texte brut"
    assert extract_body({"mimeType": "text/html", "body": {"data": b64("<i>seul</i>")}}) == "seul"


class FakeMessages:
    def __init__(self):
        self.log = []
        self.store = {
            "m1": {"id": "m1", "threadId": "t1", "snippet": "On se voit jeudi ?",
                   "labelIds": ["INBOX", "UNREAD"], "payload": {
                "headers": [{"name": "From", "value": "Julie Martin <julie@exemple.fr>"},
                            {"name": "Subject", "value": "Jeudi"},
                            {"name": "Date", "value": "Mon, 05 Oct 2026 18:00:00 +0200"},
                            {"name": "Message-ID", "value": "<abc@mail>"}],
                "mimeType": "text/plain", "body": {"data": b64("On se voit jeudi ?")}}},
        }  # fmt: skip

    def __getattr__(self, name):
        results = {
            "list": lambda kw: {"messages": [{"id": i} for i in self.store]},
            "get": lambda kw: self.store[kw["id"]],
            "send": {"id": "sent"},
        }
        return Call(self.log, name, results[name])


def gmail_with():
    messages = FakeMessages()
    users = type("U", (), {"messages": lambda self: messages})()
    service = type("S", (), {"users": lambda self: users})()
    return Gmail(lambda: service), messages


def test_check_mail_and_find_address():
    gmail, _ = gmail_with()
    result = CheckMailTool(gmail).run(count=5)
    assert "(non lu) — Julie Martin : « Jeudi »" in result.text and "05/10" in result.text
    assert "Derniers mails reçus" in result.text
    assert gmail.find_address("julie") == "julie@exemple.fr"


def test_send_mail_only_sends_the_confirmed_draft():
    gmail, messages = gmail_with()
    tool = SendMailTool(gmail)
    args = {"body": "Oui, jeudi 18 h c'est parfait.", "reply_to_id": "m1"}
    question = tool.confirmation(args)
    assert "julie@exemple.fr" in question and "Re: Jeudi" in question
    assert "Mail envoyé" in tool.run(**args).text
    sent = messages.log[-1]
    assert sent[0] == "send" and sent[1]["body"]["threadId"] == "t1"
    raw = base64.urlsafe_b64decode(sent[1]["body"]["raw"]).decode()
    assert "In-Reply-To: <abc@mail>" in raw and "Subject: Re: Jeudi" in raw

    # Sans confirmation préalable (ou brouillon modifié) : rien n'est envoyé
    count = len(messages.log)
    assert "NON envoyé" in tool.run(body="autre chose", to="julie@exemple.fr").text
    assert len(messages.log) == count


def test_unknown_recipient_never_sends():
    gmail, messages = gmail_with()
    messages.__dict__["store"] = {}
    tool = SendMailTool(gmail)
    gmail.search = lambda query, limit=8: []  # aucun contact de ce nom
    args = {"to": "Bernard", "body": "Salut"}
    assert tool.confirmation(args) is None  # pas de question inutile
    assert "NON envoyé" in tool.run(**args).text
    assert not any(name == "send" for name, _ in messages.log)


def test_latest_mails_skip_promotions():
    gmail, messages = gmail_with()
    promo = {**messages.store["m1"], "id": "p1", "labelIds": ["INBOX", "CATEGORY_PROMOTIONS"]}
    messages.store = {"p1": promo, **messages.store}  # la promo est la plus récente
    assert [m.id for m in gmail.latest(5)] == ["m1"]
    assert gmail.latest(5)[0].unread

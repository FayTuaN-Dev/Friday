from datetime import date, datetime
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication
from test_desktop import make_window

from friday.app import glance as glance_module
from friday.app.events import AssistantState
from friday.app.glance import glance
from friday.ui.desktop.widgets.welcome import greeting, moment, today

app = QApplication.instance() or QApplication([])
NOW = datetime(2026, 10, 13, 9, 30)


def test_greeting_and_date_follow_the_time_of_day():
    assert greeting(NOW, "Monsieur") == "Bonjour, Monsieur."
    assert greeting(datetime(2026, 10, 13, 21), "Tony") == "Bonsoir, Tony."
    assert moment(datetime(2026, 10, 13, 2)) == "soir"  # en pleine nuit : pas « journée »
    assert today(NOW) == "Mardi 13 octobre"


def test_a_suggestion_is_sent_as_if_typed_once_friday_is_ready():
    w = make_window()
    welcome = w.chat.welcome
    assert not welcome.isEnabled()  # les modèles chargent encore
    w.bridge.on_ready("Cerveau : qwen3:8b")
    w.bridge.on_state(AssistantState.IDLE)
    app.processEvents()
    assert welcome.isEnabled()
    welcome.refresh(NOW)
    welcome.suggestions[0].click()
    assert w.assistant.sent == ["Fais-moi le briefing du matin"]


def test_the_welcome_leaves_with_the_first_message_and_returns_on_reset():
    w = make_window()
    w.show()
    w.bridge.on_user_message("Bonjour", False)
    app.processEvents()
    assert w.chat.welcome.isHidden()
    w.chat.clear()
    assert not w.chat.welcome.isHidden()
    assert w.chat.welcome.parent() is not None  # l'accueil survit à la remise à zéro


class Reminders:
    def pending(self):
        return [SimpleNamespace(due_at=datetime(2026, 10, 13, 18)),
                SimpleNamespace(due_at=datetime(2026, 10, 14, 9))]  # fmt: skip


def test_glance_sums_up_the_day_and_skips_missing_sources(monkeypatch):
    google = SimpleNamespace(connected=True)
    monkeypatch.setattr(glance_module, "events_today", lambda g, d: "agenda libre aujourd'hui")
    monkeypatch.setattr(glance_module, "unread_mails", lambda g: "20 mails non lus")
    line = glance(SimpleNamespace(google=google, agenda=Reminders()), NOW)
    assert line == "agenda libre aujourd'hui · 20 mails non lus · 1 rappel aujourd'hui"
    assert glance(SimpleNamespace(google=None, agenda=None), NOW) == ""
    assert glance(None, NOW) == ""


def test_glance_never_opens_google_when_disconnected_and_survives_errors(monkeypatch):
    def broken(*_):
        raise ConnectionError("pas de réseau")

    monkeypatch.setattr(glance_module, "events_today", broken)
    monkeypatch.setattr(glance_module, "unread_mails", lambda g: "3 mails non lus")
    connected = SimpleNamespace(google=SimpleNamespace(connected=True), agenda=None)
    assert glance(connected, NOW) == "3 mails non lus"  # l'agenda en panne est omis
    offline = SimpleNamespace(google=SimpleNamespace(connected=False), agenda=None)
    assert glance(offline, NOW) == ""


def test_reminders_line_counts_only_today():
    assert glance_module.reminders_today(Reminders(), date(2026, 10, 15)) == ""

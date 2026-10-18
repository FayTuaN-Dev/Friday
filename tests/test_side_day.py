"""Les cartes « Aujourd'hui » et « Concentration » des colonnes de côté (W4)."""

from datetime import datetime, timedelta
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication

from friday.agenda.store import AgendaStore, Reminder
from friday.app.day_glance import Day, DayGlance, upcoming
from friday.google.calendar import Event
from friday.ui.desktop.side.day_cards import BREAK, WORK, DayCard, FocusCard

app = QApplication.instance() or QApplication([])
NOW = datetime(2026, 10, 19, 14, 0)


def event(hours, title, length=1, all_day=False):
    start = NOW + timedelta(hours=hours)
    return Event(title, title, start, start + timedelta(hours=length), all_day)


def test_upcoming_drops_finished_events_but_keeps_today_all_day():
    day = NOW.replace(hour=0)
    events = [Event("a", "Congé", day, day + timedelta(days=1), True), event(-3, "Fini"),
              event(-0.5, "En cours"), event(2, "Dentiste"), event(20, "Réunion")]  # fmt: skip
    assert [e.title for e in upcoming(events, NOW)] == ["Congé", "En cours", "Dentiste"]


def test_day_glance_reads_google_only_when_connected():
    assert DayGlance(SimpleNamespace(connected=False)).read() == Day()

    def service(name, version):
        raise ConnectionError("pas de réseau")

    glance = DayGlance(SimpleNamespace(connected=True, service=service), now=lambda: NOW)
    glance.gmail.unread_total = lambda: 3
    assert glance.read() == Day([], 3, [], True)  # agenda et expéditeurs illisibles : vides


def test_day_card_lines(tmp_path):
    card = DayCard()
    card.show_day(Day(), NOW)
    assert "non connecté" in card.agenda.text()
    card.show_day(Day([event(2, "Dentiste"), event(20, "Réunion")], 2, ["Julie", "Banque"],
                      True), NOW)  # fmt: skip
    assert card.agenda.text() == "16:00 · Dentiste\ndemain 10:00 · Réunion"
    assert card.mails.text() == "2 non lus · Julie, Banque"
    card.show_day(Day([], 0, [], True), NOW)
    assert card.agenda.text() == "Rien de prévu d'ici demain soir."
    assert card.mails.text() == "Aucun mail non lu."
    reminders = [Reminder(1, "Appeler maman", NOW + timedelta(minutes=12)),
                 Reminder(2, "Payer le loyer", NOW + timedelta(days=3)),
                 Reminder(3, "Sortir", NOW - timedelta(minutes=1)), Reminder(4, "x", NOW),
                 Reminder(5, "y", NOW)]  # fmt: skip
    card.show_reminders(reminders, NOW)
    assert card.reminders.text().splitlines() == [
        "Appeler maman · dans 12 min", "Payer le loyer · 22/10 à 14:00", "Sortir · maintenant",
        "… et 2 autres"]  # fmt: skip
    store = AgendaStore(tmp_path / "agenda.db")
    card.show_reminders(store.pending(), NOW)
    assert card.reminders.text() == "Aucun rappel."


def test_focus_timer_work_then_break_then_ready():
    rung = []
    card = FocusCard(rung.append)
    assert card.meter.value.text() == "25:00" and card.start.isVisibleTo(card)
    card.begin("travail")
    card.timer.stop()  # le test fait avancer le temps lui-même
    for _ in range(60):
        card.tick()
    assert card.meter.value.text() == "24:00" and card.stop.isVisibleTo(card)
    for _ in range(WORK - 60):
        card.tick()
    assert card.phase == "pause" and "Pause de 5 minutes" in rung[0]
    assert card.message.isVisibleTo(card)
    card.timer.stop()
    for _ in range(BREAK):
        card.tick()
    assert card.phase == "" and len(rung) == 2 and card.start.isVisibleTo(card)
    card.begin("travail")
    card.end()
    assert card.phase == "" and not card.timer.isActive()


def test_day_card_appears_with_friday_loaded(tmp_path):
    from PySide6.QtWidgets import QFrame, QHBoxLayout, QWidget
    from test_side_widgets import FakeSampler

    from friday.ui.desktop.side.columns import SidePanels

    playing, limits = QFrame(), QFrame()
    playing.has_track = False
    side = SidePanels(playing, limits, {}, FakeSampler())
    window = QWidget()
    row = QHBoxLayout(window)
    row.addWidget(side.left)
    row.addWidget(side.right)
    window.show()
    side.place(True)
    assert not side.cards["day"].isVisible() and side.cards["focus"].isVisible()
    store = AgendaStore(tmp_path / "agenda.db")
    store.add_reminder("Appeler maman", datetime.now() + timedelta(hours=2))
    day = FakeSampler()
    side.set_day(store, SimpleNamespace(configured=True, connected=True), day)
    assert side.cards["day"].isVisible() and day.requests == 1
    assert side.cards["day"].reminders.text().startswith("Appeler maman · dans 1 h 5")
    window.close()

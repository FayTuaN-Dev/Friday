from datetime import datetime

import numpy as np
import pytest

from jarvis.agenda.scheduler import ReminderScheduler
from jarvis.agenda.store import AgendaStore
from jarvis.agenda.times import describe, parse_time, resolve
from jarvis.app.reminders import announcement
from jarvis.tools.notes import AddNoteTool, ListNotesTool, RemoveNoteTool, list_key
from jarvis.tools.reminders import (
    CancelReminderTool,
    ListRemindersTool,
    SetReminderTool,
    SetTimerTool,
)
from jarvis.voice.sounds import chime

NOW = datetime(2026, 10, 4, 14, 30)  # un dimanche, 14 h 30


# --- Calcul des dates ---


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"delay": "2 heures"}, datetime(2026, 10, 4, 16, 30)),
        ({"delay": "deux minutes"}, datetime(2026, 10, 4, 14, 32)),
        ({"delay": "30 secondes"}, datetime(2026, 10, 4, 14, 30, 30)),
        ({"delay": "une heure et demie"}, datetime(2026, 10, 4, 16, 0)),
        ({"time": "18:00"}, datetime(2026, 10, 4, 18, 0)),
        ({"time": "9h"}, datetime(2026, 10, 5, 9, 0)),  # déjà passé → demain
        ({"time": "18h30", "day": "demain"}, datetime(2026, 10, 5, 18, 30)),
        ({"time": "8:15", "day": "après-demain"}, datetime(2026, 10, 6, 8, 15)),
        ({"time": "10:00", "day": "lundi"}, datetime(2026, 10, 5, 10, 0)),
        ({"time": "10:00", "day": "Samedi"}, datetime(2026, 10, 10, 10, 0)),
        ({"time": "10:00", "day": "dimanche"}, datetime(2026, 10, 11, 10, 0)),  # passé → +7 j
        ({"time": "20:00", "day": "dimanche"}, datetime(2026, 10, 4, 20, 0)),  # plus tard ce jour
        ({"time": "21:00", "day": "ce soir"}, datetime(2026, 10, 4, 21, 0)),
    ],
)
def test_resolve(kwargs, expected):
    assert resolve(NOW, **kwargs) == expected


@pytest.mark.parametrize(
    "kwargs", [{}, {"time": "25:00"}, {"time": "midi et quart"}, {"time": "9:00", "day": "bientôt"}]
)
def test_resolve_rejects_what_it_cannot_understand(kwargs):
    with pytest.raises(ValueError):
        resolve(NOW, **kwargs)


def test_parse_and_describe():
    assert parse_time("18 h 05") == (18, 5)
    assert describe(datetime(2026, 10, 4, 18, 0), NOW) == "aujourd'hui à 18:00"
    assert describe(datetime(2026, 10, 5, 9, 0), NOW) == "demain à 09:00"
    assert describe(datetime(2026, 10, 10, 9, 0), NOW) == "samedi 10 octobre 2026 à 09:00"


# --- Stockage et planificateur ---


@pytest.fixture
def store(tmp_path):
    return AgendaStore(tmp_path / "agenda.db")


def test_reminders_persist_and_fire_once(tmp_path):
    first = AgendaStore(tmp_path / "a.db")
    first.add_reminder("Appeler maman", datetime(2026, 10, 4, 15, 0))
    store = AgendaStore(tmp_path / "a.db")  # Jarvis redémarré
    fired = []
    clock = iter([datetime(2026, 10, 4, 14, 59), datetime(2026, 10, 4, 15, 0, 1)])
    scheduler = ReminderScheduler(store, lambda r, late: fired.append((r.text, late)),
                                  clock=lambda: next(clock))  # fmt: skip
    scheduler.check()
    assert fired == []
    scheduler.check()
    assert fired == [("Appeler maman", False)]
    assert store.pending() == [] and not store.mark_done(1)  # plus jamais redéclenché


def test_missed_reminders_are_announced_late_at_startup(store):
    store.add_reminder("Sortir les poubelles", datetime(2026, 10, 3, 20, 0))
    fired = []
    scheduler = ReminderScheduler(store, lambda r, late: fired.append(late), clock=lambda: NOW)
    scheduler.start()
    scheduler.stop()
    assert fired == [True]


def test_notes_lists(store):
    store.add_note("courses", "lait")
    store.add_note("courses", "œufs")
    store.add_note("tâches", "payer le loyer")
    assert [n.text for n in store.notes("courses")] == ["lait", "œufs"]
    assert store.lists() == ["courses", "tâches"]
    assert store.remove_note(1).text == "lait" and store.remove_note(1) is None


# --- Outils ---


def test_timer_and_reminder_tools(store):
    assert "14:40:00" in SetTimerTool(store, clock=lambda: NOW).run("10 minutes").text
    assert "non lancé" in SetTimerTool(store, clock=lambda: NOW).run("bientôt").text
    result = SetReminderTool(store, clock=lambda: NOW).run("appeler maman", time="18:00")
    assert "aujourd'hui à 18:00" in result.text
    bad = SetReminderTool(store, clock=lambda: NOW).run("x", time="midi moins le quart")
    assert "non programmé" in bad.text
    listing = ListRemindersTool(store, clock=lambda: NOW).run()
    assert listing.display.kind == "items" and len(listing.display.data["items"]) == 2
    assert "annulé" in CancelReminderTool(store).run(1).text
    assert "Pas de rappel" in CancelReminderTool(store).run(1).text
    assert [r.text for r in store.pending()] == ["appeler maman"]


def test_note_tools(store):
    assert list_key("Ma liste de courses") == "courses" and list_key(None) == "notes"
    AddNoteTool(store).run("lait", list="liste de courses")
    AddNoteTool(store).run("idée de cadeau pour Clara")
    courses = ListNotesTool(store).run("courses")
    assert "lait" in courses.text and courses.display.data["items"][0]["text"] == "lait"
    assert "vide" in ListNotesTool(store).run("tâches").text
    assert "Retiré" in RemoveNoteTool(store).run(1).text


def test_announcement_and_chime():
    from jarvis.agenda.store import Reminder

    reminder = Reminder(1, "Appeler maman", datetime(2026, 10, 3, 20, 0))
    assert "RAPPEL : Appeler maman" in announcement(reminder, late=False)
    assert "retard" in announcement(reminder, late=True)
    sound = chime(22050)
    assert sound.dtype == np.float32 and 0 < np.abs(sound).max() <= 1


@pytest.mark.parametrize(
    ("spoken", "seconds"),
    [
        ("2 minutes", 120), ("deux minutes", 120), ("dans deux minutes", 120),
        ("1h30", 5400), ("une heure et demie", 5400), ("une heure et quart", 4500),
        ("un quart d'heure", 900), ("trois quarts d'heure", 2700), ("une demi-heure", 1800),
        ("90 secondes", 90), ("vingt-cinq minutes", 1500), ("10", 600),
    ],
)  # fmt: skip
def test_spoken_durations(spoken, seconds):
    from jarvis.agenda.durations import parse_duration

    assert parse_duration(spoken).total_seconds() == seconds


def test_timer_label_is_not_repeated(store):
    SetTimerTool(store, clock=lambda: NOW).run("3 minutes", label="Minuteur")
    assert store.pending()[0].text == "Minuteur de 3 minutes terminé"

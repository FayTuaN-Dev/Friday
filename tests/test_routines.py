"""Routines planifiées (J5) : jours et heure lus par le code, exécution à l'heure, une seule
fois par créneau, rattrapage de moins de 3 h (PC éteint), rien avant la création."""

from datetime import datetime

from friday.agenda.routines import (
    Routine,
    RoutineStore,
    describe,
    describe_days,
    is_due,
    parse_days,
    spoken_time,
)
from friday.app.notification import TITLES
from friday.app.routines import TASK, RoutineRunner
from friday.tools.routines import AddRoutineTool, ListRoutinesTool, RemoveRoutineTool

MONDAY_7 = datetime(2026, 10, 12, 7, 0)  # un lundi


def test_days_are_read_by_the_code():
    assert parse_days("tous les jours") == [0, 1, 2, 3, 4, 5, 6] == parse_days("")
    assert parse_days("en semaine") == [0, 1, 2, 3, 4]
    assert parse_days("le week-end") == [5, 6]
    assert parse_days("tous les lundis") == [0]
    assert parse_days("lundi et jeudi") == [0, 3]
    assert parse_days("du lundi au vendredi") == [0, 1, 2, 3, 4]
    assert parse_days("du samedi au lundi") == [5, 6, 0]
    assert describe_days([0, 1, 2, 3, 4]) == "en semaine"
    assert describe_days([0, 3]) == "le lundi et le jeudi"
    assert (spoken_time("07:30"), spoken_time("08:00")) == ("7 h 30", "8 h")


def routine(**changes) -> Routine:
    values = {"id": 1, "request": "trie mes mails", "time": "08:00", "days": [0],
              "created": "2026-10-01T10:00:00"}  # fmt: skip
    return Routine(**{**values, **changes})


def test_when_a_routine_is_due():
    r = routine()
    assert is_due(r, datetime(2026, 10, 12, 7, 59)) is None  # pas encore
    assert is_due(r, datetime(2026, 10, 12, 8, 0)) == datetime(2026, 10, 12, 8, 0)
    assert is_due(r, datetime(2026, 10, 12, 10, 30)) is not None  # PC allumé à 10 h 30
    assert is_due(r, datetime(2026, 10, 12, 11, 30)) is None  # plus de 3 h : trop tard
    assert is_due(r, datetime(2026, 10, 13, 8, 30)) is None  # mardi : pas prévu
    done = routine(last_run="2026-10-12T08:00:00")
    assert is_due(done, datetime(2026, 10, 12, 9, 0)) is None  # déjà fait
    new = routine(created="2026-10-12T09:00:00")
    assert is_due(new, datetime(2026, 10, 12, 9, 5)) is None  # créée après le créneau
    assert is_due(routine(enabled=False), datetime(2026, 10, 12, 8, 1)) is None


def test_the_runner_hands_the_request_to_friday_once(tmp_path):
    store = RoutineStore(tmp_path / "routines.json")
    store.add("fais-moi mon briefing", "7h", [0, 1, 2, 3, 4], datetime(2026, 10, 10, 12))
    calls, clock = [], [MONDAY_7]
    runner = RoutineRunner(store, lambda task, result: calls.append((task, result.text)),
                           clock=lambda: clock[0])  # fmt: skip
    assert runner.check() == 1 and runner.check() == 0  # une seule fois
    task, text = calls[0]
    assert task == TASK and TITLES[TASK] == "🔁 Routine"
    assert "Fais maintenant ce qu'il a demandé" in text and "« fais-moi mon briefing »" in text
    clock[0] = datetime(2026, 10, 13, 7, 1)
    assert runner.check() == 1  # le lendemain


def test_routine_tools(tmp_path):
    store = RoutineStore(tmp_path / "routines.json")
    add = AddRoutineTool(store, clock=lambda: MONDAY_7)
    assert add.run("trie mes mails", "8h", "tous les lundis").text == (
        "Dis EXACTEMENT : « C'est programmé : le lundi à 8 h : « trie mes mails ». »")  # fmt: skip
    add.run("fais-moi mon briefing", "07:30", "en semaine")
    assert "heure illisible" in add.run("lance la musique", "midi et demi").text
    listing = ListRoutinesTool(store).run().text
    assert listing == ("Dis EXACTEMENT : « Tes routines : 1) le lundi à 8 h : « trie mes "
                       "mails » ; 2) en semaine à 7 h 30 : « fais-moi mon briefing ». »"
                       )  # fmt: skip
    remove = RemoveRoutineTool(store)
    assert remove.run(about="celle des mails").text.startswith(
        "Dis EXACTEMENT : « Routine supprimée : le lundi à 8 h")  # fmt: skip
    assert [describe(r) for r in store.all()] == ["en semaine à 7 h 30 : « fais-moi mon briefing »"]
    assert remove.run(about="la musique").text.startswith("Rien supprimé")
    assert remove.run(number=1).text.startswith("Dis EXACTEMENT : « Routine supprimée")
    assert ListRoutinesTool(store).run().text == "Dis EXACTEMENT : « Aucune routine programmée. »"

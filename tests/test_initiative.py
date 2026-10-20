from dataclasses import replace
from datetime import date, datetime, timedelta

import httpx
from fakes import SETTINGS

from friday.app.initiative_watch import InitiativeWatch, sources
from friday.google.calendar import Event
from friday.initiative.departure import Trip, departure_text, place_name, spoken_time
from friday.initiative.departures import Departures
from friday.initiative.guard import Guard, is_quiet, quiet_hours
from friday.initiative.travel import Route, Travel

NOW = datetime(2026, 10, 21, 15, 30)


def event(start=datetime(2026, 10, 21, 16, 0), location="Les Herbiers", **kw) -> Event:
    return Event(kw.get("id", "e1"), kw.get("title", "Dentiste"), start,
                 start + timedelta(hours=1), kw.get("all_day", False), location)  # fmt: skip


class FakeCalendar:
    def __init__(self, events, fail=False):
        self.events, self.fail, self.reads = events, fail, 0

    def between(self, first: date, last: date):
        self.reads += 1
        if self.fail:
            raise RuntimeError("déconnecté")
        return self.events


class FakeTravel:
    def __init__(self, seconds=600.0):
        self.value = seconds

    def route(self, place):
        return None if self.value is None else Route(self.value, 46.7, -1.3)


def watch(tmp_path, events, seconds=600.0, **guard):
    said = []
    w = InitiativeWatch(Guard(tmp_path / "vu.json", **guard),
                        lambda task, result: said.append((task, result.text)),
                        [Departures(FakeCalendar(events), FakeTravel(seconds))])  # fmt: skip
    return w, said


# Le garde-fou


def test_quiet_hours_are_read_and_can_cross_midnight():
    assert quiet_hours("23-7") == (23, 7)
    assert quiet_hours("22 h - 6 h 30") == (22, 6)
    assert quiet_hours("") == (23, 7)
    assert quiet_hours("0-0") == (0, 0)
    assert is_quiet((23, 7), datetime(2026, 1, 1, 23, 30))
    assert is_quiet((23, 7), datetime(2026, 1, 1, 6, 59))
    assert not is_quiet((23, 7), datetime(2026, 1, 1, 7, 0))
    assert is_quiet((13, 14), datetime(2026, 1, 1, 13, 10))
    assert not is_quiet((0, 0), datetime(2026, 1, 1, 3, 0))


def test_the_guard_never_repeats_a_subject_even_after_a_restart(tmp_path):
    guard = Guard(tmp_path / "vu.json")
    assert guard.allow("depart:e1", NOW)
    assert not guard.allow("depart:e1", NOW + timedelta(minutes=5))
    assert not Guard(tmp_path / "vu.json").allow("depart:e1", NOW + timedelta(hours=2))


def test_the_guard_limits_initiatives_per_hour_and_stays_silent_at_night(tmp_path):
    guard = Guard(tmp_path / "vu.json", per_hour=2)
    assert guard.allow("a", NOW) and guard.allow("b", NOW)
    assert not guard.allow("c", NOW + timedelta(minutes=30))
    assert guard.allow("c", NOW + timedelta(minutes=61))
    assert not guard.allow("d", datetime(2026, 10, 21, 23, 15))


def test_a_broken_state_file_is_ignored(tmp_path):
    (tmp_path / "vu.json").write_text("pas du json", "utf-8")
    assert Guard(tmp_path / "vu.json").allow("a", NOW)


# L'heure de départ


def test_spoken_times_and_place_names():
    assert spoken_time(datetime(2026, 1, 1, 16, 0)) == "16 h"
    assert spoken_time(datetime(2026, 1, 1, 9, 5)) == "9 h 05"
    assert place_name("12 rue des Lilas, 85500 Les Herbiers, France") == "Les Herbiers"
    assert place_name("Cabinet du Dr Martin, Montaigu") == "Cabinet du Dr Martin"


def test_departure_is_due_a_quarter_of_an_hour_before_leaving():
    trip = Trip(event(), 600)  # 10 min de route → 11,5 min avec la marge, + 5 → partir à 15 h 43
    assert trip.leave_at == datetime(2026, 10, 21, 15, 43, 30)
    assert not trip.due(datetime(2026, 10, 21, 15, 28))
    assert trip.due(datetime(2026, 10, 21, 15, 29))
    assert not trip.due(datetime(2026, 10, 21, 16, 0))  # commencé
    assert not Trip(event(), 120).due(NOW)  # à côté
    assert not Trip(event(all_day=True), 600).due(NOW)


def test_departure_sentence():
    text = departure_text(Trip(event(), 600), NOW)
    assert text == ("Dis EXACTEMENT : « Dentiste à 16 h, à Les Herbiers : environ 12 min de "
                    "route, il faudrait partir vers 15 h 43, dans 14 minutes. »")  # fmt: skip
    late = departure_text(Trip(event(), 600), datetime(2026, 10, 21, 15, 50))
    assert "il faudrait déjà être parti" in late


# Le veilleur


def test_the_watch_announces_a_departure_once(tmp_path):
    w, said = watch(tmp_path, [event()])
    assert w.check(NOW) == 1
    assert said[0][0] == "initiative" and "Dentiste à 16 h" in said[0][1]
    assert w.check(NOW + timedelta(minutes=1)) == 0


def test_the_watch_ignores_events_without_address_or_too_far(tmp_path):
    w, said = watch(tmp_path, [event(location=""), event(id="e2", start=NOW + timedelta(hours=6))])
    assert w.check(NOW) == 0


def test_the_watch_rereads_the_agenda_only_every_ten_minutes(tmp_path):
    w, _ = watch(tmp_path, [])
    for minute in range(12):
        w.check(NOW + timedelta(minutes=minute))
    assert w.sources[0].calendar.reads == 2


def test_an_unreachable_agenda_or_unknown_place_says_nothing(tmp_path):
    w, said = watch(tmp_path, [event()], seconds=None)
    assert w.check(NOW) == 0
    w = InitiativeWatch(Guard(tmp_path / "x.json"), lambda *a: said.append(a),
                        [Departures(FakeCalendar([], fail=True), FakeTravel())])  # fmt: skip
    assert w.check(NOW) == 0 and not said


class FakeGoogle:
    def service(self, name, version):
        raise AssertionError("pas d'appel réseau à la création")


def test_sources_follow_the_settings():
    on = replace(SETTINGS, home_city="Bazoges-en-Paillers")
    assert sources(on, None) == []  # sans compte Google : rien
    kinds = [type(s).__name__ for s in sources(on, FakeGoogle())]
    assert kinds == ["Departures", "ImportantMails"]
    no_town = [type(s).__name__ for s in sources(replace(on, home_city=" "), FakeGoogle())]
    assert no_town == ["ImportantMails"]
    off = replace(on, initiative_departure=False, initiative_mails=False)
    assert sources(off, FakeGoogle()) == []


class BrokenSource:
    def candidates(self, now, said):
        raise RuntimeError("panne")


def test_a_broken_source_does_not_stop_the_others(tmp_path):
    said = []
    departures = Departures(FakeCalendar([event()]), FakeTravel())
    w = InitiativeWatch(Guard(tmp_path / "vu.json"), lambda *a: said.append(a),
                        [BrokenSource(), departures])  # fmt: skip
    assert w.check(NOW) == 1


# Le trajet (OpenStreetMap)


def fake_osm(calls):
    def handler(request):
        calls.append(request.url.host)
        if request.url.host == "nominatim.openstreetmap.org":
            q = request.url.params["q"]
            return httpx.Response(
                200, json=[] if q == "Nulle part" else [{"lat": "46.9", "lon": "-1.0"}]
            )
        return httpx.Response(200, json={"code": "Ok", "routes": [{"duration": 840.0}]})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_travel_time_is_asked_once_per_place():
    calls = []
    travel = Travel("Bazoges-en-Paillers", fake_osm(calls))
    assert travel.seconds("Les Herbiers") == 840.0
    assert travel.seconds("  les   herbiers ") == 840.0
    assert calls.count("routing.openstreetmap.de") == 1
    assert travel.seconds("Nulle part") is None


def test_travel_survives_a_network_error():
    def broken(request):
        raise httpx.ConnectError("hors ligne")

    travel = Travel("Bazoges", httpx.Client(transport=httpx.MockTransport(broken)))
    assert travel.seconds("Les Herbiers") is None

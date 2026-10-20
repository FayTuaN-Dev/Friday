from datetime import datetime, timedelta

import httpx

from friday.google.calendar import Event
from friday.initiative.departures import Departures
from friday.initiative.travel import Route
from friday.initiative.weather import Hour, TripWeather, advice, risks

DAY = datetime(2026, 10, 21)
OUT = (datetime(2026, 10, 21, 15, 43), datetime(2026, 10, 21, 16, 0))
BACK = (datetime(2026, 10, 21, 17, 0), datetime(2026, 10, 21, 17, 17))


def hour(h, rain=0.0, chance=0, gusts=20, temp=12) -> Hour:
    return Hour(DAY.replace(hour=h), rain, chance, gusts, temp)


def dry_day(*bad: Hour) -> list[Hour]:
    worse = {b.at.hour: b for b in bad}
    return [worse.get(h, hour(h)) for h in range(24)]


def test_risks_for_a_motorbike():
    assert risks(hour(9)) == []
    assert risks(hour(9, rain=0.5)) == ["pluie"]
    assert risks(hour(9, chance=70)) == ["pluie"]
    assert risks(hour(9, gusts=72.4)) == ["rafales à 72 km/h"]
    assert risks(hour(9, temp=0.5)) == ["risque de verglas"]


def test_dry_trip_says_the_bike_is_fine():
    assert advice(dry_day(), OUT, BACK) == " Temps sec sur le trajet : la moto passe."


def test_rain_on_the_way_out_or_back():
    out = advice(dry_day(hour(15, rain=1.2)), OUT, BACK)
    assert out == " Attention, pluie à l'aller : la voiture plutôt que la moto."
    back = advice(dry_day(hour(17, chance=80, gusts=65)), OUT, BACK)
    assert back == (" Attention, pluie et rafales à 65 km/h au retour, vers 17 h : la voiture "
                    "plutôt que la moto.")  # fmt: skip


def test_rain_outside_the_trip_does_not_count():
    assert "moto passe" in advice(dry_day(hour(13, rain=3.0)), OUT, BACK)


def test_unknown_forecast_says_nothing():
    assert advice([], OUT, BACK) == ""


def test_forecast_is_asked_once_and_kept():
    calls = []

    def handler(request):
        calls.append(request.url.params["hourly"])
        return httpx.Response(200, json={"hourly": {
            "time": ["2026-10-21T15:00", "2026-10-21T16:00"], "precipitation": [0.0, None],
            "precipitation_probability": [10, 90], "wind_gusts_10m": [20, 30],
            "temperature_2m": [12, None]}})  # fmt: skip

    weather = TripWeather(httpx.Client(transport=httpx.MockTransport(handler)))
    hours = weather.hours(46.67, -1.43)
    assert hours[1] == Hour(datetime(2026, 10, 21, 16), 0, 90, 30, 10)
    weather.hours(46.671, -1.432)
    assert len(calls) == 1


def test_forecast_unreachable_gives_nothing():
    def broken(request):
        raise httpx.ConnectError("hors ligne")

    assert TripWeather(httpx.Client(transport=httpx.MockTransport(broken))).hours(1, 2) == []


class FakeCalendar:
    def between(self, first, last):
        start = datetime(2026, 10, 21, 16)
        return [Event("e1", "Dentiste", start, start + timedelta(hours=1), False, "Montaigu")]


class FakeTravel:
    def route(self, place):
        return Route(600, 46.97, -1.31)


class FakeWeather:
    def __init__(self, hours):
        self.value, self.asked = hours, []

    def hours(self, lat, lon):
        self.asked.append((lat, lon))
        return self.value


def test_the_departure_announcement_carries_the_trip_weather():
    weather = FakeWeather(dry_day(hour(17, rain=2.0)))
    found = Departures(FakeCalendar(), FakeTravel(), weather).candidates(
        datetime(2026, 10, 21, 15, 30), lambda key: False
    )
    assert found[0].text.endswith(
        "dans 14 minutes. Attention, pluie au retour, vers 17 h : la voiture plutôt que la "
        "moto. »")  # fmt: skip
    assert weather.asked == [(46.97, -1.31)]  # au lieu du rendez-vous


def test_without_trip_weather_the_announcement_is_unchanged():
    found = Departures(FakeCalendar(), FakeTravel()).candidates(
        datetime(2026, 10, 21, 15, 30), lambda key: False
    )
    assert found[0].text.endswith("dans 14 minutes. »")

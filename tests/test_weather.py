from datetime import date

import httpx

from friday.tools.weather import WeatherTool, day_name
from friday.tools.weather_codes import describe_weather

FORECAST = {
    "current": {
        "temperature_2m": 18.4,
        "apparent_temperature": 19.6,
        "weather_code": 3,
        "wind_speed_10m": 7.1,
        "relative_humidity_2m": 88,
    },
    "daily": {
        "time": ["2026-10-05", "2026-10-06", "2026-10-07"],
        "weather_code": [61, 0, 95],
        "temperature_2m_max": [23.5, 26.4, 19.0],
        "temperature_2m_min": [12.2, 14.0, 11.6],
        "precipitation_probability_max": [70, 0, None],
    },
}


def fake_open_meteo(found=True):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        if "geocoding" in request.url.host:
            results = [{"name": "Bordeaux", "country": "France", "latitude": 44.8,
                        "longitude": -0.58}] if found else []  # fmt: skip
            return httpx.Response(200, json={"results": results} if found else {})
        return httpx.Response(200, json=FORECAST)

    return httpx.Client(transport=httpx.MockTransport(handler)), seen


def test_weather_for_a_city():
    client, seen = fake_open_meteo()
    result = WeatherTool(client=client).run("Bordeaux")

    assert "Bordeaux (France)" in result.text
    assert "18 °C (ressenti 20 °C), couvert" in result.text
    assert "Aujourd'hui : pluie faible, de 12 à 24 °C, risque de pluie 70 %" in result.text
    assert result.display.kind == "weather"
    days = result.display.data["days"]
    assert [d["day"] for d in days] == ["Aujourd'hui", "Demain", "Mercredi"]
    assert days[2]["rain"] == 0 and days[2]["icon"] == "⛈️"  # donnée manquante → 0
    assert seen[1].params["timezone"] == "auto"


def test_home_city_is_used_when_none_given():
    client, seen = fake_open_meteo()
    WeatherTool("Lyon", client=client).run()
    assert seen[0].params["name"] == "Lyon"


def test_no_city_and_unknown_city():
    assert "Aucune ville" in WeatherTool().run().text
    client, _ = fake_open_meteo(found=False)
    assert "ne trouve pas" in WeatherTool(client=client).run("Xyzzyville").text


def test_codes_and_day_names():
    assert describe_weather(0) == ("ciel dégagé", "☀️")
    assert describe_weather(1234)[0] == "temps inconnu"
    assert day_name("2026-10-09", date(2026, 10, 5)) == "Vendredi"

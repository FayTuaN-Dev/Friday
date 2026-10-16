import httpx

from friday.tools.weather_map import (
    REGIONS,
    ShowWeatherMapTool,
    grid,
    region_box,
    side,
    wind_summary,
    wind_vector,
)

FRANCE = REGIONS["france"][1]


def fake_meteo(calls, status=200):
    def handler(request):
        calls.append(request.url.host)
        if request.url.host == "nominatim.openstreetmap.org":
            return httpx.Response(
                200,
                json=[
                    {
                        "lat": "48.2",
                        "lon": "-2.9",
                        "name": "Bretagne",
                        "display_name": "Bretagne, France",
                        "boundingbox": ["47.2", "48.9", "-5.2", "-1.0"],
                    }
                ],
            )
        if status != 200:
            return httpx.Response(status, json={"reason": "trop de demandes"})
        lats = request.url.params["latitude"].split(",")
        rows = []
        for k, lat in enumerate(lats):  # plus chaud au sud ; vent d'ouest, plus fort au nord
            north = float(lat) > 49
            rows.append(
                {
                    "current": {
                        "temperature_2m": 30 - float(lat) / 3,
                        "wind_speed_10m": 50 if north and k % 7 == 0 else 20,
                        "wind_direction_10m": 270,
                    }
                }
            )
        return httpx.Response(200, json=rows)  # fmt: skip

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_known_regions_and_places_give_a_usable_box():
    client = fake_meteo([])
    assert region_box(client, "") == REGIONS["france"]  # rien de dit : la France
    assert region_box(client, "en Europe")[0] == "l'Europe"
    name, (south, north, west, east) = region_box(client, "Bretagne")
    assert name == "Bretagne" and south < 48.2 < north and west < -2.9 < east
    assert 4 <= north - south <= 30  # une région, pas une rue ni la planète


def test_where_and_which_way():
    assert side(FRANCE, 51, 2) == "au nord" and side(FRANCE, 42, -4) == "au sud-ouest"
    assert side(FRANCE, 46.2, 2.2) == "au centre"
    u, v = wind_vector(20, 270)  # vent d'ouest : il souffle vers l'est
    assert round(u) == 20 and round(v) == 0
    assert wind_summary([u] * 3, [v] * 3, [20, 20, 30]) == "vent d'ouest, 20 km/h en général"
    assert wind_summary([0.5], [0.5], [2]).startswith("vent faible")
    points = grid(FRANCE, 12, 12)
    assert len(points) == 144 and points[0] == (41.0, -5.5) and points[-1] == (51.5, 10.0)


def test_the_map_shows_wind_and_temperatures_and_says_the_essentials():
    calls = []
    tool = ShowWeatherMapTool(fake_meteo(calls))
    result = tool.run("les deux", "France")
    assert result.display.kind == "weather_map"
    assert result.display.title == "Vent et températures · France"
    data = result.display.data
    assert data["layers"] == ["wind", "temp"] and len(data["temp"]) == data["nx"] * data["ny"]
    assert data["fit"] == list(FRANCE) and data["bbox"][0] < 41 < 51.5 < data["bbox"][1]
    assert " °C (au sud" in result.text and "vent d'ouest" in result.text  # chaud au sud
    assert "jusqu'à 50 km/h (au nord" in result.text
    tool.run("vent", "France")  # « et le vent ? » juste après : pas de nouvelle demande
    assert calls.count("api.open-meteo.com") == 1
    wind_only = tool.run("vent", "France")
    assert wind_only.display.data["layers"] == ["wind"] and "températures" not in wind_only.text


def test_a_freshly_started_pc_still_asks_for_measures(monkeypatch):
    from friday.tools import weather_map

    monkeypatch.setattr(weather_map.time, "monotonic", lambda: 30.0)  # allumé il y a 30 s
    calls = []
    result = ShowWeatherMapTool(fake_meteo(calls)).run("vent", "France")
    assert calls.count("api.open-meteo.com") == 1 and result.display is not None


def test_a_saturated_or_silent_service_is_said_plainly():
    result = ShowWeatherMapTool(fake_meteo([], status=429)).run("vent", "France")
    assert "saturé" in result.text and result.display is None

    def silent(request):
        raise httpx.ReadTimeout("muet", request=request)

    tool = ShowWeatherMapTool(httpx.Client(transport=httpx.MockTransport(silent)))
    assert "ne répond pas" in tool.run("vent", "France").text


def test_the_map_page_carries_the_weather_script():
    from friday.ui.desktop.scenes.layer import SHOWN_ON_MAP
    from friday.ui.desktop.scenes.map_page import page

    assert "window.fridayWeather" in page() and SHOWN_ON_MAP["weather_map"] == "weather"

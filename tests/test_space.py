from datetime import UTC, datetime

import httpx
import pytest

from friday.tools import space, space_data
from friday.tools.orbits import Pass, passes, satellite, track, where
from friday.tools.space import NextLaunchesTool, ShowSpaceTool, launch_date, pass_text
from friday.tools.space_data import ocean

# Les éléments d'orbite de l'ISS chez CelesTrak, le 15 octobre 2026
ISS = {"OBJECT_NAME": "ISS (ZARYA)", "OBJECT_ID": "1998-067A",
       "EPOCH": "2026-10-15T19:43:34.186944",
       "MEAN_MOTION": 15.48879905, "ECCENTRICITY": 0.00067551, "INCLINATION": 51.6317,
       "RA_OF_ASC_NODE": 63.1136, "ARG_OF_PERICENTER": 265.8514, "MEAN_ANOMALY": 94.1703,
       "EPHEMERIS_TYPE": 0, "CLASSIFICATION_TYPE": "U", "NORAD_CAT_ID": 25544,
       "ELEMENT_SET_NO": 999, "REV_AT_EPOCH": 59045, "BSTAR": 0.00010980148,
       "MEAN_MOTION_DOT": 5.58e-5, "MEAN_MOTION_DDOT": 0}  # fmt: skip
CHECKED = datetime(2026, 10, 16, 11, 34, 49, tzinfo=UTC)  # position relevée par un autre service
LAUNCH = {"name": "Falcon 9 | Starlink", "net": "2026-10-19T10:30:00Z", "status": {"abbrev": "Go"},
          "net_precision": {"name": "Minute"}, "rocket": {"configuration": {"name": "Falcon 9"}},
          "launch_service_provider": {"name": "SpaceX"}, "mission": {"name": "Starlink 15-15"},
          "pad": {"latitude": "28.56", "longitude": "-80.57",
                  "location": {"name": "Cape Canaveral SFS, FL, USA"}}}  # fmt: skip
DONE = LAUNCH | {"name": "déjà parti", "status": {"name": "Launch Successful"}}
LATER = LAUNCH | {"net": "2026-12-01T00:00:00Z", "status": {"abbrev": "TBD"},
                  "net_precision": {"name": "Month"}, "rocket": {"configuration": {
                      "name": "Ariane 62"}}, "launch_service_provider": {"name": "Arianespace"},
                  "mission": {"name": "Metop"}, "pad": {}}  # fmt: skip


@pytest.fixture(autouse=True)
def forget(monkeypatch):  # chaque test redemande ses données
    monkeypatch.setattr(space_data, "_orbits", {})
    monkeypatch.setattr(space_data, "_launches", {})
    monkeypatch.setattr(space, "now", lambda: CHECKED)


def fake_space(calls, status=200):
    def handler(request):
        calls.append(request.url)
        host = request.url.host
        if status != 200:
            return httpx.Response(status)
        if host == "celestrak.org":
            return httpx.Response(
                200, json=[ISS | {"NORAD_CAT_ID": int(request.url.params["CATNR"])}]
            )
        if host == "ll.thespacedevs.com":
            return httpx.Response(200, json={"results": [DONE, LAUNCH, LATER]})
        if "reverse" in request.url.path:
            return httpx.Response(200, json={"address": {"country": "Canada"}})
        return httpx.Response(200, json=[{"lat": "46.87", "lon": "-1.01", "name": "Les Herbiers",
                                          "display_name": "Les Herbiers, France"}])  # fmt: skip

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_the_orbit_lands_where_the_station_really_was():
    lat, lon, alt, kmh = where(satellite(ISS), CHECKED)
    assert abs(lat - 51.6) < 0.3 and abs(lon - -55.48) < 0.3  # relevé : 51,6° N, 55,48° O
    assert 400 < alt < 450 and 27000 < kmh < 28000
    line = track(satellite(ISS), CHECKED, 95)
    assert len(line) == 96 and all(
        abs(b[0] - a[0]) < 30 for a, b in zip(line, line[1:], strict=False)
    )


def test_visible_passes_are_at_night_only():
    found = passes(satellite(ISS), 46.87, -1.01, CHECKED, 72)
    assert found and all(p.start.astimezone().hour < 8 or p.start.astimezone().hour > 18
                         for p in found)  # fmt: skip
    today = datetime(2026, 10, 16, 12, 0).astimezone()
    seen = Pass(datetime(2026, 10, 17, 4, 28, tzinfo=UTC), 4, 21, "sud", "est")
    assert pass_text(seen, today).startswith("demain à ")
    assert pass_text(seen, today).endswith("21° au-dessus de l'horizon, du sud vers l'est")
    assert ocean(-20, 80) == "l'océan Indien" and ocean(40, 10) == "la Méditerranée"


def test_the_station_is_shown_with_its_neighbours_and_its_passes():
    calls = []
    result = ShowSpaceTool("Les Herbiers", fake_space(calls)).run("ISS")
    assert "l'ISS survole en ce moment : Canada" in result.text
    assert "Prochains passages visibles à l'œil nu depuis Les Herbiers" in result.text
    data = result.display.data
    assert result.display.kind == "space" and data["home"] == [-1.01, 46.87]
    assert [s["label"] for s in data["sats"] if s["focus"]] == ["ISS"] and len(data["sats"]) == 3
    ShowSpaceTool("", fake_space(calls)).run("Hubble")  # orbites gardées 2 h : pas redemandées
    assert sum(u.host == "celestrak.org" for u in calls) == 3


def test_next_launches_skip_the_past_and_vague_dates_have_no_fake_hour():
    result = NextLaunchesTool(fake_space([])).run("SpaceX")
    assert (
        "déjà parti" not in result.text
        and "Falcon 9 de SpaceX, mission Starlink 15-15" in result.text
    )
    assert "en décembre 2026 (date à confirmer) : Ariane 62" in result.text
    assert result.display.data["pads"] == [
        {"where": [-80.57, 28.56], "label": "Falcon 9 · 19 octobre"}
    ]
    today = datetime(2026, 10, 16, 12, 0).astimezone()
    end = datetime(2026, 12, 31, tzinfo=UTC)  # une date floue : la fin de la période
    assert launch_date(end, "Quarter 4", today) == "au 4e trimestre 2026 (date à confirmer)"
    assert launch_date(end, "Year", today) == "en 2026 (date à confirmer)"
    assert launch_date(datetime(2026, 11, 23, tzinfo=UTC), "Day", today).startswith("vers le 23")


def test_a_busy_service_is_said_plainly():
    assert "saturé" in ShowSpaceTool("", fake_space([], status=429)).run("ISS").text
    assert "saturé" in NextLaunchesTool(fake_space([], status=429)).run("").text


def test_the_map_page_carries_the_space_script():
    from friday.ui.desktop.scenes.layer import SHOWN_ON_MAP
    from friday.ui.desktop.scenes.map_page import page

    assert "window.fridaySpace" in page() and SHOWN_ON_MAP["space"] == "space"

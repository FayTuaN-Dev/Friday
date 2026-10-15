import httpx

from friday.tools.planes import PlaneOverheadTool, ShowPlanesTool, around
from friday.tools.planes_data import bearing, distance_km, parse

# Un « état » OpenSky : identifiant, indicatif, pays, 2 dates, lon, lat, altitude (m), au sol,
# vitesse (m/s), cap
NANTES_PALMA = ["4ca9e1", "VOE77PD ", "Spain", 0, 0, -1.21, 46.85, 4694.0, False, 175.0, 139.0]
HIGH = ["39de4c", "AFR1234 ", "France", 0, 0, 2.3, 48.9, 11000.0, False, 230.0, 320.0]
RYANAIR = ["4ca123", "RYR67RD ", "Ireland", 0, 0, 1.0, 45.0, 10000.0, False, 220.0, 10.0]
GROUND = ["3c0001", "AFR9    ", "France", 0, 0, -1.6, 47.15, 0.0, True, 0.0, 0.0]


def fake_sky(calls, states=None, status=200):
    states = [NANTES_PALMA, HIGH, RYANAIR, GROUND] if states is None else states

    def handler(request):
        calls.append(request.url)
        host = request.url.host
        if host == "nominatim.openstreetmap.org":
            return httpx.Response(
                200,
                json=[
                    {
                        "lat": "46.87",
                        "lon": "-1.01",
                        "name": "Les Herbiers",
                        "display_name": "Les Herbiers, France",
                        "boundingbox": ["46.8", "46.9", "-1.1", "-0.9"],
                    }
                ],
            )
        if host == "opensky-network.org":
            if status != 200:
                return httpx.Response(status)
            return httpx.Response(200, json={"states": states})
        if "callsign" in request.url.path:
            return httpx.Response(
                200,
                json={
                    "response": {
                        "flightroute": {
                            "airline": {"name": "Volotea"},
                            "origin": {
                                "municipality": "Nantes",
                                "latitude": 47.15,
                                "longitude": -1.61,
                            },
                            "destination": {
                                "municipality": "Palma De Mallorca",
                                "latitude": 39.55,
                                "longitude": 2.74,
                            },
                        }
                    }
                },
            )
        return httpx.Response(200, json={"response": {"aircraft": {
            "type": "A319 111", "manufacturer": "Airbus SAS"}}})  # fmt: skip

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_only_flying_planes_are_kept():
    assert parse(GROUND) is None
    plane = parse(NANTES_PALMA)
    assert plane.callsign == "VOE77PD" and plane.kmh == 630 and plane.meters == 4694
    assert plane.airline == "Volotea"
    assert parse(["x", "FGOPV", "", 0, 0, 1, 1, 500.0, False, 50.0, 0.0]).airline == ""


def test_the_map_of_planes_counts_airlines():
    calls = []
    result = ShowPlanesTool(fake_sky(calls)).run("")
    assert result.display.kind == "planes" and result.display.title == "Avions · France · 3"
    assert "3 avions en vol" in result.text and "Volotea (1)" in result.text
    params = calls[-1].params
    assert params["lamin"] == "41.0" and params["lomax"] == "10.0"  # la zone, en une demande
    assert ShowPlanesTool(fake_sky([], status=429)).run("").text.count("saturé") == 1


def test_the_plane_overhead_is_described_with_its_flight():
    result = PlaneOverheadTool("Les Herbiers", fake_sky([])).run("")
    text = result.text
    assert "Airbus A319 de Volotea, vol VOE77PD, de Nantes vers Palma De Mallorca" in text
    assert "4700 m d'altitude et 630 km/h, à 15 km à l'ouest de Les Herbiers" in text
    data = result.display.data
    assert data["home"] == [-1.01, 46.87]
    assert [p[5] for p in data["planes"] if p[7]] == ["VOE77PD"]  # mis en valeur
    assert data["path"][0] == [-1.61, 47.15] and data["path"][2] == [2.74, 39.55]


def test_nobody_overhead_or_no_home():
    empty = PlaneOverheadTool("Les Herbiers", fake_sky([], states=[GROUND])).run("")
    assert "Aucun avion capté au-dessus de Les Herbiers" in empty.text
    assert "demande-lui" in PlaneOverheadTool("", fake_sky([])).run("").text


def test_geometry_helpers():
    assert round(distance_km(46.87, -1.01, 47.22, -1.55)) == 56  # Les Herbiers → Nantes
    assert 300 < bearing(46.87, -1.01, 47.22, -1.55) < 330  # vers le nord-ouest
    south, north, west, east = around(46.87, -1.01, 75)
    assert round(north - south, 2) == 1.35 and east - west > north - south


def test_the_map_page_carries_the_planes_script():
    from friday.ui.desktop.scenes.layer import SHOWN_ON_MAP
    from friday.ui.desktop.scenes.map_page import page

    assert "window.fridayPlanes" in page() and SHOWN_ON_MAP["planes"] == "planes"

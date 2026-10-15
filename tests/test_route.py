import httpx

from friday.tools.route import (
    ShowRouteTool,
    distance_text,
    duration_text,
    latin,
    thin,
    travel_mode,
)

PLACES = {
    "Les Herbiers": {"lat": "46.87", "lon": "-1.01", "name": "Les Herbiers",
                     "display_name": "Les Herbiers, Vendée, France"},
    "Paris": {"lat": "48.85", "lon": "2.35", "name": "Paris", "display_name": "Paris, France"},
    "Marseille": {"lat": "43.29", "lon": "5.37", "name": "Marseille",
                  "display_name": "Marseille, France"},
}  # fmt: skip


def fake_osm(seen, code="Ok"):
    def handler(request):
        seen.append(request.url)
        if request.url.host == "nominatim.openstreetmap.org":
            found = PLACES.get(request.url.params["q"])
            return httpx.Response(200, json=[found] if found else [])
        if code != "Ok":
            return httpx.Response(400, json={"code": code})
        route = {"distance": 773_400, "duration": 29_700,
                 "geometry": {"coordinates": [[2.35, 48.85], [4.8, 45.7], [5.37, 43.29]]},
                 "legs": [{"summary": "Autoroute du Soleil, Autoroute du Soleil"}]}  # fmt: skip
        return httpx.Response(200, json={"code": "Ok", "routes": [route]})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_a_route_is_traced_with_distance_duration_and_roads():
    seen = []
    result = ShowRouteTool("Les Herbiers", fake_osm(seen)).run("Marseille", "Paris")
    assert "Paris → Marseille en voiture, 773 km, environ 8 h 15 sans les bouchons" in result.text
    assert result.text.count("Autoroute du Soleil") == 1  # doublon retiré
    assert result.display.kind == "route"
    assert result.display.data["coords"][0] == [2.35, 48.85]
    assert "routed-car" in str(seen[-1])


def test_home_is_the_default_start():
    seen = []
    ShowRouteTool("Les Herbiers", fake_osm(seen)).run("Paris", "chez moi", "à vélo")
    assert seen[0].params["q"] == "Les Herbiers"
    assert "routed-bike" in str(seen[-1])
    no_home = ShowRouteTool("", fake_osm([])).run("Paris")
    assert "d'où il part" in no_home.text and no_home.display is None


def test_unknown_place_or_no_road_is_said_plainly():
    assert "Je ne trouve pas « Atlantide »" in ShowRouteTool(
        "Les Herbiers", fake_osm([])).run("Atlantide").text  # fmt: skip
    text = ShowRouteTool("Les Herbiers", fake_osm([], code="NoRoute")).run("Paris", "", "pied").text
    assert "Je ne trouve pas de route à pied" in text


def test_small_helpers():
    assert [travel_mode(m) for m in ("", "Vélo", "en marchant", "voiture")] == [
        "voiture", "velo", "a pied", "voiture"]  # fmt: skip
    assert [duration_text(s) for s in (30, 3000, 3600, 29_700, 554_000)] == [
        "1 min", "50 min", "1 h", "8 h 15", "6 j 10 h"]  # fmt: skip
    assert distance_text(12_080_400) == "12 080 km" and distance_text(3_240) == "3,2 km"
    assert latin("A 87") and latin("Autoroute du Soleil") and not latin("连霍高速")
    points = [[i / 1e6, i / 1e6] for i in range(10_001)]
    kept = thin(points, 1000)
    assert len(kept) <= 1001 and kept[0] == [0, 0] and kept[-1] == [0.01, 0.01]


def test_the_map_page_carries_the_route_script():
    from friday.ui.desktop.scenes.map_page import page

    assert "window.fridayRoute" in page()

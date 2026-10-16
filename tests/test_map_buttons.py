import json

import httpx

from friday.tools.planes import planes_here
from friday.ui.desktop.scenes.links_page import request_of
from friday.ui.desktop.scenes.map_bridge import MapBridge

PLANE = ["4ca9e1", "VOE77PD ", "Spain", 0, 0, -1.21, 46.85, 4694.0, False, 175.0, 139.0]


def sky(calls, status=200):
    def handler(request):
        calls.append(request.url)
        if status != 200:
            return httpx.Response(status)
        return httpx.Response(200, json={"states": [PLANE]})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_only_friday_requests_are_read_from_the_page_console():
    assert request_of('friday:{"ask": "planes", "box": [41, 51, -5, 10]}')["ask"] == "planes"
    for message in ("Erreur de tuile", "friday:pas du json", 'friday:{"box": 1}', "friday:[1]"):
        assert request_of(message) is None, message


def test_planes_of_the_view_stop_at_the_date_line():
    calls = []
    assert planes_here(sky(calls), [40, 52, -200, -170])[0][5] == "VOE77PD"
    assert calls[-1].params["lomin"] == "-180.0"  # OpenSky ne passe pas ±180°
    planes_here(sky(calls), [-80, 80, -300, 300])  # tout le tour du monde : une seule demande
    assert "lomin" not in calls[-1].params


def test_the_bridge_answers_the_page_with_planes_or_a_plain_message():
    answers = []
    bridge = MapBridge("#f0a83c", sky([]))
    bridge.reply.connect(answers.append)
    bridge.planes([41, 51.5, -5.5, 10], 3)
    data = json.loads(answers[-1].split("fridayPlanesHere(")[1].rsplit(", ", 1)[0])
    assert data["id"] == 3 and data["planes"][0][5] == "VOE77PD"
    busy = MapBridge("#f0a83c", sky([], status=429))
    busy.reply.connect(answers.append)
    busy.planes([41, 51.5, -5.5, 10], 4)
    assert "limite du jour" in answers[-1] and '"id": 4' in answers[-1]


def test_the_map_page_carries_the_buttons():
    from friday.ui.desktop.scenes.map_page import page

    html = page()
    assert 'id = "friday-layers"' in html and "window.fridayPlanesHere" in html
    assert "__ACCENT__" not in html and "#friday-layers button" in html

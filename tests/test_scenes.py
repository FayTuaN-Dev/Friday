"""Scènes plein écran (J7) : ciel météo selon le temps, lieu trouvé par le code avec le bon
zoom, calque qui s'ouvre sur la météo ou un lieu et se ferme sur « ferme » ou Échap."""

from types import SimpleNamespace

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from test_desktop import app, make_window  # noqa: F401  (QApplication)

from friday.tools.base import Display
from friday.tools.place import ShowPlaceTool, zoom_for
from friday.tools.popups import CLOSE
from friday.ui.desktop.scenes.map_scene import page
from friday.ui.desktop.scenes.weather_scene import WeatherScene, sky_kind

WEATHER = {"current": {"temperature": 14, "feels_like": 12, "label": "pluie faible",
                       "icon": "🌧️", "wind": 18, "humidity": 80, "code": 61, "is_day": False},
           "days": [{"day": "demain", "label": "beau", "icon": "☀️", "min": 8, "max": 17,
                     "rain": 0}]}  # fmt: skip


def test_the_sky_follows_the_weather():
    assert [sky_kind(c) for c in (0, 2, 3, 45, 61, 81, 73, 95, None)] == [
        "clair", "nuageux", "couvert", "brouillard", "pluie", "pluie", "neige", "orage",
        "couvert"]  # fmt: skip
    scene = WeatherScene(WEATHER, "Les Herbiers (France)")
    assert scene.kind == "pluie" and not scene.day and len(scene.drops) == 260
    scene.resize(600, 400)
    for _ in range(5):
        scene._tick()
    assert not scene.grab().isNull()


class Response:
    def __init__(self, found):
        self.found = found

    def raise_for_status(self):
        pass

    def json(self):
        return self.found


def test_the_place_is_found_by_the_code():
    assert zoom_for(["48.8574", "48.8590", "2.2933", "2.2956"]) == 16.3  # un monument
    assert zoom_for(["24.2", "35.9", "135.8", "154.0"], "city") == 10.5  # Tokyo et ses îles
    assert zoom_for(["24.0", "45.7", "122.9", "153.9"]) < 5  # un pays
    eiffel = {"lat": "48.8582", "lon": "2.2945", "name": "Tour Eiffel",
              "display_name": "Tour Eiffel, 5, Avenue Anatole France, Paris, 75007, France",
              "boundingbox": ["48.8574", "48.8590", "2.2933", "2.2956"],
              "addresstype": "tourism"}  # fmt: skip
    calls = []
    client = SimpleNamespace(get=lambda url, params: calls.append(params) or Response([eiffel]))
    result = ShowPlaceTool(client).run("la tour Eiffel")
    assert calls[0]["q"] == "la tour Eiffel" and calls[0]["accept-language"] == "fr"
    assert result.display.kind == "place" and result.display.title == "Tour Eiffel — 75007, France"
    assert result.display.data == {"lat": 48.8582, "lon": 2.2945, "zoom": 16.3,
                                   "name": "Tour Eiffel"}  # fmt: skip
    nothing = SimpleNamespace(get=lambda url, params: Response([]))
    assert "Je ne trouve pas « Atlantide »" in ShowPlaceTool(nothing).run("Atlantide").text
    html = page(48.8582, 2.2945, 16.3, "#f0a83c")
    assert '"lat": 48.8582' in html and "tiles.openfreemap.org" in html and "#f0a83c" in html


def test_scenes_open_and_close(tmp_path):
    window = make_window(tmp_path)
    window.resize(1000, 700)
    window._on_display(Display("weather", "Les Herbiers (France)", WEATHER))
    layer = window.scene_layer
    assert layer.showing and isinstance(layer.scene, WeatherScene)
    assert layer.title.text() == ""  # la scène écrit déjà le lieu
    layer.start_subtitle()
    layer.add_subtitle("Il pleut un peu ")
    layer.add_subtitle("aux Herbiers.")
    assert layer.subtitle.text() == "Il pleut un peu aux Herbiers."
    window._on_display(Display(CLOSE, "", {"which": "all"}))  # « ferme », « reviens »
    assert not layer.showing
    window._on_display(Display("weather", "Les Herbiers (France)", WEATHER))
    window.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))
    assert not layer.showing
    window.settings = SimpleNamespace(**{**vars(window.settings), "scenes": False})
    window._on_display(Display("weather", "Les Herbiers (France)", WEATHER))
    assert not layer.showing  # scènes coupées : la météo reste en petite fenêtre

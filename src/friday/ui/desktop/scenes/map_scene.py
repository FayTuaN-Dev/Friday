"""Scène carte 3D plein écran (J7) : « montre-moi la tour Eiffel » → la carte vole jusqu'au
lieu, inclinée, bâtiments en volume, et tourne lentement autour. MapLibre GL (libre) et les
cartes OpenFreeMap (gratuites, sans compte ni clé) dans une page web intégrée à Friday."""

import json

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QVBoxLayout, QWidget

MAPLIBRE = "https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl"
STYLE = "https://tiles.openfreemap.org/styles/dark"  # sombre, comme Friday

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<link href="{maplibre}.css" rel="stylesheet"><script src="{maplibre}.js"></script>
<style>html,body,#map{{margin:0;height:100%;background:#0b0d12}}
.maplibregl-ctrl-attrib{{opacity:.55;font-size:10px}}</style></head>
<body><div id="map"></div><script>
const place = {place};
const map = new maplibregl.Map({{container: "map", style: "{style}", center: [2.35, 46.6],
  zoom: 4, pitch: 0, bearing: 0, attributionControl: {{compact: true}}}});
map.on("load", () => {{
  if (!map.getLayer("friday-3d")) {{
    map.addLayer({{id: "friday-3d", type: "fill-extrusion", source: "openmaptiles",
      "source-layer": "building", minzoom: 14, paint: {{
        "fill-extrusion-color": "{accent}",
        "fill-extrusion-height": ["coalesce", ["get", "render_height"], 8],
        "fill-extrusion-base": ["coalesce", ["get", "render_min_height"], 0],
        "fill-extrusion-opacity": 0.6}}}});
  }}
  new maplibregl.Marker({{color: "{accent}"}}).setLngLat([place.lon, place.lat]).addTo(map);
  map.flyTo({{center: [place.lon, place.lat], zoom: place.zoom, pitch: place.zoom > 13 ? 62 : 35,
    bearing: -20, duration: 6000, essential: true}});
  map.once("moveend", () => {{
    let bearing = map.getBearing();
    setInterval(() => {{ bearing += 0.08; map.setBearing(bearing); }}, 40);
  }});
}});
</script></body></html>"""


def page(lat: float, lon: float, zoom: float, accent: str = "#f0a83c") -> str:
    place = json.dumps({"lat": lat, "lon": lon, "zoom": zoom})
    return PAGE.format(maplibre=MAPLIBRE, style=STYLE, place=place, accent=accent)


class MapScene(QWidget):
    def __init__(self, data: dict, accent: str = "#f0a83c", parent=None) -> None:
        super().__init__(parent)
        from PySide6.QtWebEngineWidgets import QWebEngineView

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = QWebEngineView(self)
        self.view.setHtml(page(data["lat"], data["lon"], data["zoom"], accent),
                          QUrl("https://friday.local/"))  # fmt: skip
        layout.addWidget(self.view)

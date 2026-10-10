"""Scène carte 3D plein écran (J7) : « montre-moi la tour Eiffel » → la carte se place sur le
lieu, inclinée, bâtiments en volume ; une fois que Friday a fini de parler, elle s'envole un
peu et tourne lentement autour. MapLibre GL (libre) et les cartes OpenFreeMap (gratuites,
sans compte ni clé) dans une page web intégrée à Friday. La même page montre aussi le globe de
la veille monde (J9b) : thèmes et catastrophes en points, détail au clic, globe qui tourne.

La page est créée UNE fois, peu après le démarrage, puis réutilisée : créer le moteur web
bloque la fenêtre un instant, ce qui hachait la voix quand c'était fait pendant qu'elle
parlait. Pour la même raison, rien ne s'anime tant que Friday parle."""

import json

from PySide6.QtCore import QUrl
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QVBoxLayout, QWidget

MAPLIBRE = "https://unpkg.com/maplibre-gl@5.8.0/dist/maplibre-gl"  # 5 : le globe
STYLE = "https://tiles.openfreemap.org/styles/dark"  # sombre, comme Friday
BACKGROUND = "#0b0d12"

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<link href="{maplibre}.css" rel="stylesheet"><script src="{maplibre}.js"></script>
<style>html,body,#map{{margin:0;height:100%;background:{background}}}
.maplibregl-ctrl-attrib{{opacity:.55;font-size:10px}}</style></head>
<body><div id="map"></div><script>
// Rendu à la résolution de base (pas ×1,5 sur un écran agrandi) : moitié moins de calcul
const map = new maplibregl.Map({{container: "map", style: "{style}", center: [2.35, 46.6],
  zoom: 4, pixelRatio: 1, fadeDuration: 0, attributionControl: {{compact: true}}}});
map.addControl(new maplibregl.NavigationControl({{visualizePitch: true}}), "bottom-right");
let spin = null, marker = null, place = null, stopTimer = null, mode = "place", ready = false;
const later = [];  // en attente du style (chargé après la page)
const whenReady = (fn) => {{ if (ready) fn(); else later.push(fn); }};
const COLORS = ["match", ["get", "kind"], "mine", "{accent}", "theme", "#7aa2c8",
  "red", "#ff3b3b", "#ff7aa8"];  // catastrophes : rouge (alerte rouge), rose (orange)
const geojson = (points) => ({{type: "FeatureCollection", features: points.map((p) => ({{
  type: "Feature", geometry: {{type: "Point", coordinates: [p.lon, p.lat]}}, properties: p}}))}});
const stopSpin = () => {{ if (spin) {{ clearInterval(spin); spin = null; }} }};
// L'utilisateur prend la main : la rotation automatique s'arrête (sinon elle annule ses gestes)
for (const name of ["mousedown", "wheel", "touchstart", "dragstart"]) map.on(name, stopSpin);
map.on("load", () => {{
  map.addLayer({{id: "friday-3d", type: "fill-extrusion", source: "openmaptiles",
    "source-layer": "building", minzoom: 14, paint: {{
      "fill-extrusion-color": "{accent}",
      "fill-extrusion-height": ["coalesce", ["get", "render_height"], 8],
      "fill-extrusion-base": ["coalesce", ["get", "render_min_height"], 0],
      "fill-extrusion-opacity": 0.6}}}});
  map.addSource("world", {{type: "geojson", data: geojson([])}});
  map.addLayer({{id: "world-halo", type: "circle", source: "world", paint: {{
    "circle-radius": ["*", 2.2, ["get", "size"]], "circle-color": COLORS,
    "circle-opacity": 0.18, "circle-blur": 0.6}}}});
  map.addLayer({{id: "world-dots", type: "circle", source: "world", paint: {{
    "circle-radius": ["*", 0.7, ["get", "size"]], "circle-color": COLORS,
    "circle-stroke-color": "#ffffff", "circle-stroke-width": 1, "circle-stroke-opacity": 0.6}}}});
  map.addLayer({{id: "world-labels", type: "symbol", source: "world", layout: {{
    "text-field": ["get", "label"], "text-font": ["Noto Sans Regular"], "text-size": 12,
    "text-offset": [0, 1.3], "text-anchor": "top"}}, paint: {{"text-color": "#e8eef7",
    "text-halo-color": "#000000", "text-halo-width": 1.2}}}});
  map.on("click", "world-dots", (e) => {{
    const p = e.features[0].properties;
    new maplibregl.Popup({{closeButton: false}}).setLngLat(e.lngLat)
      .setText(p.label + " — " + p.detail).addTo(map);
  }});
  ready = true;
  later.splice(0).forEach((fn) => fn());
}});
// Se placer sur le lieu, d'un coup (pendant que Friday parle : une seule image à calculer)
window.fridayGo = (lat, lon, zoom, accent) => whenReady(() => {{
  stopSpin();
  mode = "place";
  map.setProjection({{type: "mercator"}});
  map.getSource("world").setData(geojson([]));
  place = {{lat, lon, zoom}};
  if (marker) marker.remove();
  marker = new maplibregl.Marker({{color: accent}}).setLngLat([lon, lat]).addTo(map);
  map.jumpTo({{center: [lon, lat], zoom: zoom - 1.2, pitch: zoom > 13 ? 55 : 30, bearing: 0}});
}});
// Le globe de la veille monde : les points, vus de loin
window.fridayWorld = (points) => whenReady(() => {{
  stopSpin();
  mode = "world";
  place = null;
  if (marker) {{ marker.remove(); marker = null; }}
  map.setProjection({{type: "globe"}});
  map.getSource("world").setData(geojson(points));
  // Le globe occupe 80 % de la hauteur (à zoom 1,6, il mesure environ 460 px)
  const zoom = 1.6 + Math.log2(map.getContainer().clientHeight * 0.8 / 460);
  map.jumpTo({{center: [20, 30], zoom: Math.max(1, zoom), pitch: 0, bearing: 0}});
}});
// Friday a fini de parler : petit vol vers le lieu, puis lente rotation (40 s au plus)
window.fridayMove = () => {{
  if (spin) return;
  if (mode === "world") {{  // le globe tourne lentement sur lui-même (60 s au plus)
    const turn = () => {{ const c = map.getCenter(); map.setCenter([c.lng + 0.12, c.lat]); }};
    spin = setInterval(turn, 60);
    clearTimeout(stopTimer);
    stopTimer = setTimeout(stopSpin, 60000);
    return;
  }}
  if (!place) return;
  map.flyTo({{center: [place.lon, place.lat], zoom: place.zoom,
    pitch: place.zoom > 13 ? 62 : 35, bearing: -20, duration: 3500, essential: true}});
  map.once("moveend", () => {{
    let bearing = map.getBearing();
    spin = setInterval(() => {{ bearing += 0.12; map.setBearing(bearing); }}, 60);
    clearTimeout(stopTimer);
    stopTimer = setTimeout(stopSpin, 40000);
  }});
}};
window.fridayStop = stopSpin;
</script></body></html>"""


def page(accent: str = "#f0a83c") -> str:
    return PAGE.format(maplibre=MAPLIBRE, style=STYLE, accent=accent, background=BACKGROUND)


def world_script(data: dict) -> str:
    """Le JavaScript qui montre le globe et ses points."""
    return f"window.fridayWorld && window.fridayWorld({json.dumps(data['points'])});"


def go_script(data: dict, accent: str) -> str:
    """Le JavaScript qui place la carte sur un lieu."""
    args = ", ".join(json.dumps(v) for v in (data["lat"], data["lon"], data["zoom"], accent))
    return f"window.fridayGo && window.fridayGo({args});"


class MapScene(QWidget):
    keep = True  # gardée entre deux affichages (le calque la cache au lieu de la détruire)

    def __init__(self, accent: str = "#f0a83c", parent=None) -> None:
        super().__init__(parent)
        from PySide6.QtWebEngineWidgets import QWebEngineView

        self.accent = accent
        self.ready = False
        self._pending: str | None = None  # le dernier script, joué une fois la page prête
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = QWebEngineView(self)
        self.view.page().setBackgroundColor(QColor(BACKGROUND))  # pas de flash blanc
        self.view.loadFinished.connect(self._loaded)
        self.view.setHtml(page(accent), QUrl("https://friday.local/"))
        layout.addWidget(self.view)

    def _loaded(self, ok: bool) -> None:
        self.ready = ok
        if ok and self._pending is not None:
            self._run(self._pending)

    def _run(self, script: str) -> None:
        self._pending = script
        if self.ready:
            self.view.page().runJavaScript(script)

    def go(self, data: dict) -> None:
        """Se place sur le lieu (sans animation : Friday va en parler)."""
        self._run(go_script(data, self.accent))

    def world(self, data: dict) -> None:
        """Le globe de la veille monde (J9b)."""
        self._run(world_script(data))

    def animate(self) -> None:
        """Friday a fini de parler : vol et rotation."""
        if self.ready:
            self.view.page().runJavaScript("window.fridayMove && window.fridayMove();")

    def still(self) -> None:
        if self.ready:
            self.view.page().runJavaScript("window.fridayStop && window.fridayStop();")

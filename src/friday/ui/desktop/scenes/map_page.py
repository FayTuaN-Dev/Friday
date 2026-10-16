"""La page web de la scène carte : MapLibre GL (libre) et les cartes OpenFreeMap (gratuites,
sans compte ni clé). La carte des lieux (J7) est ici ; le globe de la veille monde (J9b)
est dans globe_js.py, les itinéraires (M1) dans route_js.py, la météo (M2) dans
weather_js.py, les avions (M3) dans planes_js.py, l'espace (M4) dans space_js.py.
page() assemble le tout."""

from friday.ui.desktop.scenes.globe_js import GLOBE_CSS, GLOBE_JS
from friday.ui.desktop.scenes.layers_js import LAYERS_CSS, LAYERS_JS
from friday.ui.desktop.scenes.planes_js import PLANES_JS
from friday.ui.desktop.scenes.route_js import ROUTE_JS
from friday.ui.desktop.scenes.space_js import SPACE_CSS, SPACE_JS
from friday.ui.desktop.scenes.weather_follow_js import WEATHER_FOLLOW_JS
from friday.ui.desktop.scenes.weather_js import WEATHER_JS

MAPLIBRE = "https://unpkg.com/maplibre-gl@5.8.0/dist/maplibre-gl"  # 5 : le globe
STYLE = "https://tiles.openfreemap.org/styles/dark"  # sombre, comme Friday
BACKGROUND = "#0b0d12"

HEAD = """<!doctype html><html><head><meta charset="utf-8">
<link href="__MAPLIBRE__.css" rel="stylesheet"><script src="__MAPLIBRE__.js"></script>
<style>html,body{margin:0;height:100%;background:__BACKGROUND__;overflow:hidden}
#stars,#map,#leaders,#callouts{position:absolute;inset:0;width:100%;height:100%}
#map{background:transparent}
.maplibregl-ctrl-attrib{opacity:.55;font-size:10px}
.maplibregl-ctrl-top-right{top:96px}
__GLOBE_CSS____SPACE_CSS____LAYERS_CSS__</style></head>
<body><canvas id="stars"></canvas><div id="map"></div><svg id="leaders"></svg>
<div id="callouts"></div><script>
"""

PLACE_JS = """
// Rendu à la résolution de base (pas ×1,5 sur un écran agrandi) : moitié moins de calcul
const map = new maplibregl.Map({container: "map", style: "__STYLE__", center: [2.35, 46.6],
  zoom: 4, pixelRatio: 1, fadeDuration: 0, attributionControl: {compact: true}});
map.addControl(new maplibregl.NavigationControl({visualizePitch: true}), "top-right");
// U8 : la conversation de Friday couvre le bas de la carte ; on centre au-dessus
window.fridayPad = (top, bottom) => map.setPadding({top: top, bottom: bottom, left: 0, right: 0});
let spin = null, marker = null, place = null, stopTimer = null, mode = "place", ready = false;
const later = [];  // en attente du style (chargé après la page)
const whenReady = (fn) => { if (ready) fn(); else later.push(fn); };
const stopSpin = () => { if (spin) { spin.stop(); spin = null; } };
// Animation fluide : à chaque image de l'écran, on avance selon le temps écoulé (et non par
// sauts toutes les 50 ms, qui donnaient 20 pas par seconde, donc des à-coups)
function animate(step) {
  stopSpin();
  let last = performance.now(), id = 0;
  const frame = (now) => {
    step(Math.min(now - last, 100) / 1000, now);  // secondes ; pas de bond après une pause
    last = now;
    id = requestAnimationFrame(frame);
  };
  id = requestAnimationFrame(frame);
  spin = {stop: () => cancelAnimationFrame(id)};
}
// L'utilisateur prend la main : la rotation automatique s'arrête (sinon elle annule ses gestes)
for (const name of ["mousedown", "wheel", "touchstart", "dragstart"]) map.on(name, stopSpin);
map.on("load", () => {
  map.addLayer({id: "friday-3d", type: "fill-extrusion", source: "openmaptiles",
    "source-layer": "building", minzoom: 14, paint: {
      "fill-extrusion-color": "__ACCENT__",
      "fill-extrusion-height": ["coalesce", ["get", "render_height"], 8],
      "fill-extrusion-base": ["coalesce", ["get", "render_min_height"], 0],
      "fill-extrusion-opacity": 0.6}});
  addWorldLayers();
  ready = true;
  later.splice(0).forEach((fn) => fn());
});
// Se placer sur le lieu, d'un coup (pendant que Friday parle : une seule image à calculer)
window.fridayGo = (lat, lon, zoom, accent) => whenReady(() => {
  stopSpin();
  leaveWorld();
  place = {lat, lon, zoom};
  if (marker) marker.remove();
  marker = new maplibregl.Marker({color: accent}).setLngLat([lon, lat]).addTo(map);
  map.jumpTo({center: [lon, lat], zoom: zoom - 1.2, pitch: zoom > 13 ? 55 : 30, bearing: 0});
});
// Friday a fini de parler : petit vol vers le lieu, puis lente rotation (40 s au plus)
window.fridayMove = () => {
  if (spin) return;
  if (mode === "world") { spinGlobe(); return; }  // reprend, s'il lui reste du temps
  if (!place) return;
  map.flyTo({center: [place.lon, place.lat], zoom: place.zoom,
    pitch: place.zoom > 13 ? 62 : 35, bearing: -20, duration: 3500, essential: true});
  map.once("moveend", () => {
    let bearing = map.getBearing();
    animate((dt) => { bearing += 2 * dt; map.setBearing(bearing); });  // 2° par seconde
    clearTimeout(stopTimer);
    stopTimer = setTimeout(stopSpin, 40000);
  });
};
window.fridayStop = stopSpin;
"""

TAIL = "</script></body></html>"


def page(accent: str = "#f0a83c") -> str:
    scripts = (PLACE_JS, GLOBE_JS, ROUTE_JS, WEATHER_JS, WEATHER_FOLLOW_JS, PLANES_JS, SPACE_JS,
               LAYERS_JS)  # fmt: skip
    html = HEAD + "".join(scripts) + TAIL
    for key, value in (("__GLOBE_CSS__", GLOBE_CSS), ("__SPACE_CSS__", SPACE_CSS),
                       ("__LAYERS_CSS__", LAYERS_CSS),
                       ("__MAPLIBRE__", MAPLIBRE),
                       ("__STYLE__", STYLE), ("__BACKGROUND__", BACKGROUND),
                       ("__ACCENT__", accent)):  # fmt: skip
        html = html.replace(key, value)
    return html

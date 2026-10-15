"""Les itinéraires (M1), dans la page de la scène carte (map_page.py) : la route tracée de
part en part (elle se dessine en 1,5 s), un point blanc au départ, la couleur de Friday à
l'arrivée, et la carte cadrée sur tout le trajet."""

ROUTE_JS = """
let routeMarkers = [];
const noRoute = {type: "FeatureCollection", features: []};
function clearRoute() {
  if (map.getSource("route")) map.getSource("route").setData(noRoute);
  routeMarkers.forEach((m) => m.remove());
  routeMarkers = [];
}
// Un lieu ou le globe remplace l'itinéraire
for (const name of ["fridayGo", "fridayWorld"]) {
  const shown = window[name];
  window[name] = (...args) => { clearRoute(); shown(...args); };
}
// Le dégradé de ligne veut une expression sur line-progress, même pour une seule couleur
const plain = (color) => ["step", ["line-progress"], color, 1, color];
function drawRoute(accent) {  // la ligne avance du départ à l'arrivée
  const start = performance.now();
  const frame = (now) => {
    const t = Math.min((now - start) / 1500, 1);
    map.setPaintProperty("route-line", "line-gradient", t >= 1 ? plain(accent) :
      ["step", ["line-progress"], accent, Math.max(t, 0.001), "rgba(0,0,0,0)"]);
    if (t < 1) requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
}
window.fridayRoute = (route, accent) => whenReady(() => {
  stopSpin();
  leaveWorld();
  place = null;
  if (marker) { marker.remove(); marker = null; }
  clearRoute();
  const line = {type: "Feature", properties: {},
    geometry: {type: "LineString", coordinates: route.coords}};
  if (!map.getSource("route")) {
    map.addSource("route", {type: "geojson", data: line, lineMetrics: true});
    const layout = {"line-join": "round", "line-cap": "round"};
    map.addLayer({id: "route-casing", type: "line", source: "route", layout,
      paint: {"line-color": "#000000", "line-width": 9, "line-opacity": 0.5}});
    map.addLayer({id: "route-line", type: "line", source: "route", layout,
      paint: {"line-width": 5, "line-gradient": plain(accent)}});
  } else {
    map.getSource("route").setData(line);
  }
  routeMarkers = [
    new maplibregl.Marker({color: "#ffffff", scale: 0.75})
      .setLngLat([route.start.lon, route.start.lat]).addTo(map),
    new maplibregl.Marker({color: accent}).setLngLat([route.end.lon, route.end.lat]).addTo(map),
  ];
  const bounds = new maplibregl.LngLatBounds();
  route.coords.forEach((c) => bounds.extend(c));
  map.jumpTo({pitch: 0, bearing: 0});
  map.fitBounds(bounds, {padding: {top: 40, bottom: 40, left: 70, right: 70}, duration: 0,
    maxZoom: 15});
  drawRoute(accent);
});
"""

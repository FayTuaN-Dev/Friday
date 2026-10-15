"""Les avions sur la carte (M3), dans la page de la scène carte (map_page.py) : chaque avion
est une petite silhouette tournée vers son cap, qui avance d'elle-même à sa vitesse (les
positions datent de la demande ; on les fait vivre au lieu de redemander sans cesse). Un clic
sur un avion montre son vol ; l'avion « au-dessus de chez moi » est mis en valeur, avec son
trajet en pointillés."""

PLANES_JS = """
let planes = null, planesAnim = null, planesMarker = null, planesClick = false;
const noPlanes = {type: "FeatureCollection", features: []};
function planeIcon() {  // une silhouette blanche, nez vers le haut (le nord) ; teintée par la carte
  const size = 48, c = document.createElement("canvas");
  c.width = c.height = size;
  const g = c.getContext("2d");
  g.fillStyle = "#ffffff";
  g.beginPath();
  g.moveTo(24, 2); g.lineTo(28, 16); g.lineTo(46, 28); g.lineTo(46, 32); g.lineTo(28, 26);
  g.lineTo(27, 38); g.lineTo(33, 43); g.lineTo(33, 46); g.lineTo(24, 43); g.lineTo(15, 46);
  g.lineTo(15, 43); g.lineTo(21, 38); g.lineTo(20, 26); g.lineTo(2, 32); g.lineTo(2, 28);
  g.lineTo(20, 16); g.closePath(); g.fill();
  return g.getImageData(0, 0, size, size);
}
function planeFeatures() {
  return {type: "FeatureCollection", features: planes.list.map((p) => ({type: "Feature",
    properties: {track: p[2], alt: p[3], kmh: p[4], cs: p[5], label: p[6], focus: p[7]},
    geometry: {type: "Point", coordinates: [p[0], p[1]]}}))};
}
function stopPlanes() { if (planesAnim) { clearInterval(planesAnim); planesAnim = null; } }
function flyPlanes() {  // 4 fois par seconde, chaque avion avance selon son cap et sa vitesse
  stopPlanes();
  let last = performance.now();
  planesAnim = setInterval(() => {
    const now = performance.now(), hours = (now - last) / 3600000;
    last = now;
    if (now - planes.since > 300000) { stopPlanes(); return; }  // 5 min : trop vieux
    for (const p of planes.list) {
      const km = p[4] * hours, rad = p[2] * Math.PI / 180;
      p[1] += km * Math.cos(rad) / 111;
      p[0] += km * Math.sin(rad) / (111 * Math.max(Math.cos(p[1] * Math.PI / 180), 0.2));
    }
    if (map.getSource("planes")) map.getSource("planes").setData(planeFeatures());
  }, 250);
}
function clearPlanes() {
  stopPlanes();
  if (map.getSource("planes")) map.getSource("planes").setData(noPlanes);
  if (map.getSource("planes-path")) map.getSource("planes-path").setData(noPlanes);
  if (planesMarker) { planesMarker.remove(); planesMarker = null; }
  planes = null;
}
function planeLayers(accent) {
  if (!map.hasImage("plane")) map.addImage("plane", planeIcon(), {sdf: true});
  if (map.getSource("planes")) return;
  map.addSource("planes-path", {type: "geojson", data: noPlanes});
  map.addLayer({id: "planes-path", type: "line", source: "planes-path", paint: {
    "line-color": accent, "line-width": 2, "line-dasharray": [2, 2], "line-opacity": 0.8}});
  map.addSource("planes", {type: "geojson", data: noPlanes});
  map.addLayer({id: "planes", type: "symbol", source: "planes", layout: {
    "icon-image": "plane", "icon-rotate": ["get", "track"], "icon-rotation-alignment": "map",
    "icon-allow-overlap": true, "icon-ignore-placement": true,
    "icon-size": ["interpolate", ["linear"], ["zoom"], 3, 0.22, 6, 0.38, 10, 0.6],
    "text-field": ["case", ["get", "focus"], ["get", "cs"], ""], "text-offset": [0, 1.6],
    "text-font": ["Noto Sans Regular"], "text-size": 13, "text-allow-overlap": true},
    paint: {"icon-color": ["case", ["get", "focus"], accent, "#dfe8f5"],
      "icon-opacity": ["case", ["get", "focus"], 1, 0.85],
      "text-color": "#ffffff", "text-halo-color": "rgba(0,0,0,0.8)", "text-halo-width": 1.4}});
  if (!planesClick) {  // un clic sur un avion : son vol, son altitude, sa vitesse
    planesClick = true;
    map.on("click", "planes", (e) => {
      const p = e.features[0].properties;
      const info = `<b>${p.label || p.cs || "Avion"}</b><br>${Math.round(p.alt / 100) * 100} m`
        + ` · ${p.kmh} km/h`;
      new maplibregl.Popup({closeButton: false}).setLngLat(e.lngLat).setHTML(info).addTo(map);
    });
    map.on("mouseenter", "planes", () => { map.getCanvas().style.cursor = "pointer"; });
    map.on("mouseleave", "planes", () => { map.getCanvas().style.cursor = ""; });
  }
}
// Un lieu, le globe, un itinéraire ou la météo remplace les avions ; Friday écoute : pause
for (const name of ["fridayGo", "fridayWorld", "fridayRoute", "fridayWeather"]) {
  const shown = window[name];
  window[name] = (...args) => { clearPlanes(); shown(...args); };
}
const planesStop = window.fridayStop, planesMove = window.fridayMove;
window.fridayStop = () => { stopPlanes(); planesStop(); };
window.fridayMove = () => { if (planes && !planesAnim) flyPlanes(); planesMove(); };
window.fridayPlanes = (data, accent) => whenReady(() => {
  stopSpin();
  leaveWorld();
  place = null;
  if (marker) { marker.remove(); marker = null; }
  clearRoute();
  clearWeather();
  clearPlanes();
  planeLayers(accent);
  planes = {list: data.planes, since: performance.now()};
  map.getSource("planes").setData(planeFeatures());
  map.jumpTo({pitch: 0, bearing: 0});
  const focus = data.planes.find((p) => p[7]);
  if (data.path) {
    map.getSource("planes-path").setData({type: "Feature", properties: {},
      geometry: {type: "LineString", coordinates: data.path}});
  }
  if (data.home) {
    planesMarker = new maplibregl.Marker({color: "#ffffff", scale: 0.75})
      .setLngLat(data.home).addTo(map);
  }
  if (focus && data.home) {  // chez moi et l'avion, bien cadrés
    const b = new maplibregl.LngLatBounds(data.home, data.home);
    b.extend([focus[0], focus[1]]);
    map.fitBounds(b, {padding: 140, duration: 0, maxZoom: 10});
  } else if (data.bbox) {
    const [s, n, w, e] = data.bbox;
    map.fitBounds([[w, s], [e, n]], {padding: 10, duration: 0});
  }
  flyPlanes();
});
"""

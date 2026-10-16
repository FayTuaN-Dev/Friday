"""Les avions sur la carte (M3), dans la page de la scène carte (map_page.py) : chaque avion
est une petite silhouette tournée vers son cap, qui avance d'elle-même à sa vitesse (les
positions datent de la demande ; on les fait vivre au lieu de redemander sans cesse). Un clic
sur un avion montre son vol ; l'avion « au-dessus de chez moi » est mis en valeur, avec son
trajet en pointillés.

Constaté : redonner 1 000 avions à la carte 4 fois par seconde la fait tout redécouper, et
les avions clignotent. Ils sont donc dessinés sur notre propre calque, à chaque image, comme
les particules de vent ; la carte ne garde que le trajet en pointillés."""

PLANES_JS = """
let planes = null, planesAnim = 0, planesMarker = null, planesCanvas = null, planesHooked = false;
const noPlanes = {type: "FeatureCollection", features: []};
function planeSprite(color) {  // une silhouette nez vers le haut (le nord), dans la couleur voulue
  const c = document.createElement("canvas");
  c.width = c.height = 48;
  const g = c.getContext("2d");
  g.fillStyle = color;
  g.beginPath();
  g.moveTo(24, 2); g.lineTo(28, 16); g.lineTo(46, 28); g.lineTo(46, 32); g.lineTo(28, 26);
  g.lineTo(27, 38); g.lineTo(33, 43); g.lineTo(33, 46); g.lineTo(24, 43); g.lineTo(15, 46);
  g.lineTo(15, 43); g.lineTo(21, 38); g.lineTo(20, 26); g.lineTo(2, 32); g.lineTo(2, 28);
  g.lineTo(20, 16); g.closePath(); g.fill();
  return c;
}
function planesLayer() {  // sous les repères et les bulles de la carte, au-dessus du fond
  if (!planesCanvas) {
    planesCanvas = document.createElement("canvas");
    planesCanvas.style.cssText = "position:absolute;left:0;top:0;pointer-events:none";
    map.getCanvas().after(planesCanvas);
    map.on("move", () => { if (planes && !planesAnim) drawPlanes(); });  // en pause : suivre
  }
  const m = map.getCanvas();
  if (planesCanvas.width !== m.clientWidth || planesCanvas.height !== m.clientHeight) {
    planesCanvas.width = m.clientWidth; planesCanvas.height = m.clientHeight;
    planesCanvas.style.width = m.clientWidth + "px";
    planesCanvas.style.height = m.clientHeight + "px";
  }
  return planesCanvas;
}
function planeAt(p, hours) {  // [lon, lat] maintenant, d'après le cap et la vitesse
  const km = p[4] * hours, rad = p[2] * Math.PI / 180, lat = p[1] + km * Math.cos(rad) / 111;
  return [p[0] + km * Math.sin(rad) / (111 * Math.max(Math.cos(lat * Math.PI / 180), 0.2)), lat];
}
function planeSize() {  // en pixels : petits vus de loin, plus gros quand on zoome
  const z = map.getZoom();
  return z <= 3 ? 10 : z <= 6 ? 10 + (z - 3) * 2.7 : Math.min(18 + (z - 6) * 2.8, 29);
}
function drawPlanes() {
  const c = planesLayer(), g = c.getContext("2d");
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.clearRect(0, 0, c.width, c.height);
  if (!planes) return;
  // Au-delà de 5 min, les positions estimées deviennent fausses : on arrête de les avancer
  const hours = Math.min(performance.now() - planes.since, 300000) / 3600000;
  const size = planeSize(), half = size / 2, turn = -map.getBearing() * Math.PI / 180;
  let focus = null;
  g.globalAlpha = 0.85;
  for (const p of planes.list) {
    const s = map.project(planeAt(p, hours));
    p.x = s.x; p.y = s.y;
    if (s.x < -size || s.y < -size || s.x > c.width + size || s.y > c.height + size) continue;
    if (p[7]) { focus = p; continue; }
    const r = p[2] * Math.PI / 180 + turn, cos = Math.cos(r), sin = Math.sin(r);
    g.setTransform(cos, sin, -sin, cos, s.x, s.y);
    g.drawImage(planes.sprite, -half, -half, size, size);
  }
  if (focus) {  // l'avion mis en valeur : par-dessus les autres, plus gros, avec son indicatif
    const big = size * 1.5, r = focus[2] * Math.PI / 180 + turn;
    g.globalAlpha = 1;
    g.setTransform(Math.cos(r), Math.sin(r), -Math.sin(r), Math.cos(r), focus.x, focus.y);
    g.drawImage(planes.focusSprite, -big / 2, -big / 2, big, big);
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.font = "13px sans-serif"; g.textAlign = "center"; g.lineWidth = 3;
    g.strokeStyle = "rgba(0,0,0,0.8)"; g.fillStyle = "#ffffff";
    g.strokeText(focus[5], focus.x, focus.y + big); g.fillText(focus[5], focus.x, focus.y + big);
  }
}
function nearestPlane(point) {  // l'avion sous la souris (à quelques pixels près)
  if (!planes) return null;
  let best = null, reach = Math.max(planeSize(), 12) ** 2;
  for (const p of planes.list) {
    const d = (p.x - point.x) ** 2 + (p.y - point.y) ** 2;
    if (d < reach) { reach = d; best = p; }
  }
  return best;
}
function stopPlanes() { if (planesAnim) { cancelAnimationFrame(planesAnim); planesAnim = 0; } }
function flyPlanes() {  // à chaque image, chaque avion avance selon son cap et sa vitesse
  stopPlanes();
  const frame = () => { drawPlanes(); planesAnim = requestAnimationFrame(frame); };
  planesAnim = requestAnimationFrame(frame);
}
function clearPlanes() {
  stopPlanes();
  planes = null;
  if (planesCanvas) drawPlanes();
  if (map.getSource("planes-path")) map.getSource("planes-path").setData(noPlanes);
  if (planesMarker) { planesMarker.remove(); planesMarker = null; }
}
function planeLayers() {
  if (!map.getSource("planes-path")) {
    map.addSource("planes-path", {type: "geojson", data: noPlanes});
    map.addLayer({id: "planes-path", type: "line", source: "planes-path", paint: {
      "line-color": planes.accent, "line-width": 2, "line-dasharray": [2, 2],
      "line-opacity": 0.8}});
  }
  map.setPaintProperty("planes-path", "line-color", planes.accent);
  if (planesHooked) return;
  planesHooked = true;  // un clic sur un avion : son vol, son altitude, sa vitesse
  map.on("click", (e) => {
    const p = nearestPlane(e.point);
    if (!p) return;
    const info = `<b>${p[6] || p[5] || "Avion"}</b><br>${Math.round(p[3] / 100) * 100} m`
      + ` · ${p[4]} km/h`;
    new maplibregl.Popup({closeButton: false}).setLngLat(map.unproject([p.x, p.y]))
      .setHTML(info).addTo(map);
  });
  map.on("mousemove", (e) => {
    if (planes) map.getCanvas().style.cursor = nearestPlane(e.point) ? "pointer" : "";
  });
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
  planes = {list: data.planes, since: performance.now(), accent: accent,
    sprite: planeSprite("#dfe8f5"), focusSprite: planeSprite(accent)};
  planeLayers();
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
  } else if (data.bbox) {  // cadré sur la région ; les avions autour remplissent la fenêtre
    const [s, n, w, e] = data.fit || data.bbox;
    map.fitBounds([[w, s], [e, n]], {padding: 10, duration: 0});
  }
  flyPlanes();
});
"""

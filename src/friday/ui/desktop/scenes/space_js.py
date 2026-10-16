"""L'espace sur le globe (M4), dans la page de la scène carte (map_page.py) : les stations
avancent le long de leur trajectoire (calculée par Friday pour un tour et demi, en temps
réel), la station demandée est mise en valeur ; les bases des prochains lancements sont
marquées. Le fond étoilé est celui du globe de la veille monde (globe_js.py)."""

SPACE_CSS = """
.space-tag{display:flex;align-items:center;gap:6px;font:600 12px sans-serif;color:#fff;
  text-shadow:0 0 3px #000,0 0 6px #000;pointer-events:none;white-space:nowrap}
.space-tag i{width:9px;height:9px;border-radius:50%;background:#dfe8f5;
  box-shadow:0 0 8px 2px rgba(223,232,245,.6)}
.space-tag.focus i{width:13px;height:13px;background:var(--accent);
  box-shadow:0 0 12px 4px var(--accent)}
.space-pad i{border-radius:2px;transform:rotate(45deg)}
"""

SPACE_JS = """
let space = null, spaceAnim = 0, spaceMarkers = [];
const noSpace = {type: "FeatureCollection", features: []};
function spaceTag(text, cls, accent) {  // un point lumineux et son nom
  const el = document.createElement("div");
  el.className = "space-tag " + cls;
  el.style.setProperty("--accent", accent);
  const dot = document.createElement("i"), name = document.createElement("span");
  name.textContent = text;
  el.append(dot, name);
  return el;
}
function satAt(sat, seconds) {  // [lon, lat] à cet instant, entre deux points de la trace
  const f = Math.min(Math.max((seconds - sat.t0) / sat.step, 0), sat.track.length - 1.001);
  const i = Math.floor(f), k = f - i, a = sat.track[i], b = sat.track[i + 1];
  return [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k];
}
function moveSats() {
  const seconds = (performance.now() - space.since) / 1000;
  space.sats.forEach((sat, n) => space.dots[n].setLngLat(satAt(sat, seconds)));
}
function stopSpace() { if (spaceAnim) { cancelAnimationFrame(spaceAnim); spaceAnim = 0; } }
function flySats() {  // à chaque image (une station parcourt 7,7 km par seconde)
  stopSpace();
  const frame = () => { moveSats(); spaceAnim = requestAnimationFrame(frame); };
  spaceAnim = requestAnimationFrame(frame);
}
function clearSpace() {
  stopSpace();
  spaceMarkers.forEach((m) => m.remove());
  spaceMarkers = [];
  for (const id of ["space-tracks", "space-focus"]) {
    if (map.getSource(id)) map.getSource(id).setData(noSpace);
  }
  space = null;
}
function spaceLayers() {
  if (map.getSource("space-tracks")) return;
  map.addSource("space-tracks", {type: "geojson", data: noSpace});
  map.addLayer({id: "space-tracks", type: "line", source: "space-tracks",
    layout: {"line-join": "round", "line-cap": "round"},
    paint: {"line-color": ["get", "color"], "line-width": ["get", "width"],
      "line-opacity": ["get", "opacity"]}});
  // La trace mise en valeur s'estompe (dégradé le long de la ligne : il faut ses mesures)
  map.addSource("space-focus", {type: "geojson", data: noSpace, lineMetrics: true});
  map.addLayer({id: "space-focus", type: "line", source: "space-focus",
    layout: {"line-join": "round", "line-cap": "round"}, paint: {"line-width": 2.5}});
}
function rgba(hex, alpha) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${alpha})`;
}
// Constaté : un tour et demi tracé à pleine couleur, la fin du tour suivant (décalée par la
// rotation de la Terre) s'arrêtait net au milieu de nulle part. Légère derrière la station,
// vive devant elle, puis elle s'efface.
function fadingTrack(sat, accent) {
  const here = Math.min(Math.max(-sat.t0 / sat.step / (sat.track.length - 1), 0.01), 0.9);
  map.getSource("space-focus").setData({type: "Feature", properties: {},
    geometry: {type: "LineString", coordinates: sat.track}});
  map.setPaintProperty("space-focus", "line-gradient", ["interpolate", ["linear"],
    ["line-progress"], 0, rgba(accent, 0.1), here, rgba(accent, 0.95),
    here + (1 - here) * 0.5, rgba(accent, 0.6), 1, rgba(accent, 0)]);
}
// Un lieu, le globe, un itinéraire, la météo ou les avions remplacent l'espace
for (const name of ["fridayGo", "fridayWorld", "fridayRoute", "fridayWeather", "fridayPlanes"]) {
  const shown = window[name];
  window[name] = (...args) => { clearSpace(); shown(...args); };
}
const spaceStop = window.fridayStop, spaceMove = window.fridayMove;
window.fridayStop = () => { stopSpace(); spaceStop(); };
window.fridayMove = () => { if (space && !spaceAnim) { flySats(); return; } spaceMove(); };
window.fridaySpace = (data, accent) => whenReady(() => {
  stopSpin();
  leaveWorld();
  place = null;
  if (marker) { marker.remove(); marker = null; }
  clearRoute();
  clearWeather();
  clearPlanes();
  clearSpace();
  mode = "space";
  map.setProjection({type: "globe"});
  sky(true);
  spaceLayers();
  space = {sats: data.sats, since: performance.now(), dots: []};
  const features = [];
  for (const sat of data.sats) {  // la trace : discrète, celle demandée bien visible
    if (sat.focus) fadingTrack(sat, accent);
    else features.push({type: "Feature", properties: {color: "#9fb3d1", width: 1.2,
      opacity: 0.45}, geometry: {type: "LineString", coordinates: sat.track}});
    const dot = new maplibregl.Marker({element: spaceTag(sat.label, sat.focus ? "focus" : "",
      accent)}).setLngLat(satAt(sat, 0)).addTo(map);
    space.dots.push(dot);
    spaceMarkers.push(dot);
  }
  map.getSource("space-tracks").setData({type: "FeatureCollection", features});
  for (const pad of data.pads) {  // les bases de lancement, avec la fusée et la date
    const el = spaceTag(pad.label, "focus space-pad", accent);
    spaceMarkers.push(new maplibregl.Marker({element: el}).setLngLat(pad.where).addTo(map));
  }
  if (data.home) {
    spaceMarkers.push(new maplibregl.Marker({color: "#ffffff", scale: 0.7})
      .setLngLat(data.home).addTo(map));
  }
  const focus = data.sats.find((s) => s.focus);
  const center = focus ? satAt(focus, 0) : data.pads.length ? data.pads[0].where : [0, 20];
  const zoom = 1.6 + Math.log2(map.getContainer().clientHeight * 0.75 / 460);
  map.jumpTo({center, zoom: Math.max(1, zoom), pitch: 0, bearing: 0});
  if (data.sats.length) flySats();
});
"""

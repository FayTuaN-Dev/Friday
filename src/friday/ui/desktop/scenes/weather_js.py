"""La météo sur la carte (M2), dans la page de la scène carte (map_page.py) : les
températures en couleur (une image lissée posée sur la carte, sous les noms de lieux, avec
quelques valeurs écrites) et le vent en particules qui filent dans son sens."""

WEATHER_JS = """
let wx = null, wxAnim = null, wxCanvas = null;
// Du froid au chaud (°C → couleur), comme les cartes de la télévision
const TEMP_SCALE = [[-20, [94, 60, 153]], [-5, [49, 54, 149]], [3, [69, 117, 180]],
  [10, [116, 173, 209]], [15, [171, 217, 233]], [19, [254, 224, 144]], [24, [253, 174, 97]],
  [29, [244, 109, 67]], [35, [215, 48, 39]], [42, [165, 0, 38]]];
function tempColor(t) {
  for (let i = 1; i < TEMP_SCALE.length; i++) {
    const [t1, c1] = TEMP_SCALE[i];
    if (t <= t1) {
      const [t0, c0] = TEMP_SCALE[i - 1];
      const k = Math.max(0, (t - t0) / (t1 - t0));
      return c0.map((v, j) => Math.round(v + (c1[j] - v) * k));
    }
  }
  return TEMP_SCALE[TEMP_SCALE.length - 1][1];
}
// Valeur d'un champ de la grille en un point (interpolation entre les 4 points voisins)
function sample(field, lon, lat) {
  const [s, n, w, e] = wx.bbox;
  const fx = Math.min(Math.max((lon - w) / (e - w) * (wx.nx - 1), 0), wx.nx - 1.001);
  const fy = Math.min(Math.max((lat - s) / (n - s) * (wx.ny - 1), 0), wx.ny - 1.001);
  const i = Math.floor(fx), j = Math.floor(fy), dx = fx - i, dy = fy - j;
  const at = (a, b) => field[b * wx.nx + a];
  return (at(i, j) * (1 - dx) + at(i + 1, j) * dx) * (1 - dy)
    + (at(i, j + 1) * (1 - dx) + at(i + 1, j + 1) * dx) * dy;
}
const mercY = (lat) =>
  Math.log(Math.tan(Math.PI / 4 + Math.max(-85, Math.min(85, lat)) * Math.PI / 360));
const latOfY = (y) => (2 * Math.atan(Math.exp(y)) - Math.PI / 2) * 180 / Math.PI;
// Les bords de l'image s'effacent : pas de cassure nette si l'on recule ou déplace la carte
const edgeFade = (f) => Math.min(1, Math.min(f, 1 - f) / 0.06);
function tempImage() {  // une image, ligne par ligne en projection de la carte (Mercator)
  const [s, n, w, e] = wx.bbox, W = 240, H = 240;
  const canvas = document.createElement("canvas");
  canvas.width = W; canvas.height = H;
  const ctx = canvas.getContext("2d"), img = ctx.createImageData(W, H);
  const top = mercY(n), bottom = mercY(s);
  for (let r = 0; r < H; r++) {
    const lat = latOfY(top - (top - bottom) * (r + 0.5) / H);
    for (let c = 0; c < W; c++) {
      const [R, G, B] = tempColor(sample(wx.temp, w + (e - w) * (c + 0.5) / W, lat));
      const o = (r * W + c) * 4, edge = edgeFade((r + 0.5) / H) * edgeFade((c + 0.5) / W);
      img.data[o] = R; img.data[o + 1] = G; img.data[o + 2] = B;
      img.data[o + 3] = Math.round(255 * edge);
    }
  }
  ctx.putImageData(img, 0, 0);
  return canvas.toDataURL();
}
function tempLabels() {  // une valeur sur deux, pour rester lisible
  const [s, n, w, e] = wx.bbox, features = [];
  for (let j = 1; j < wx.ny; j += 2) for (let i = 1; i < wx.nx; i += 2) {
    const lon = w + (e - w) * i / (wx.nx - 1), lat = s + (n - s) * j / (wx.ny - 1);
    features.push({type: "Feature", properties: {t: Math.round(wx.temp[j * wx.nx + i])},
      geometry: {type: "Point", coordinates: [lon, lat]}});
  }
  return {type: "FeatureCollection", features};
}
function windCanvas() {
  if (!wxCanvas) {
    wxCanvas = document.createElement("canvas");
    wxCanvas.style.cssText = "position:absolute;inset:0;width:100%;height:100%;pointer-events:none";
    document.getElementById("map").after(wxCanvas);
    const wipe = () => wxCanvas.getContext("2d").clearRect(0, 0, wxCanvas.width, wxCanvas.height);
    map.on("move", wipe);  // la carte bouge : les traînées repartent de zéro
  }
  wxCanvas.width = wxCanvas.clientWidth; wxCanvas.height = wxCanvas.clientHeight;
  return wxCanvas;
}
function stopWind() {
  if (wxAnim) { wxAnim.stop(); wxAnim = null; }
  if (wxCanvas) wxCanvas.getContext("2d").clearRect(0, 0, wxCanvas.width, wxCanvas.height);
}
function startWind() {  // des particules qui suivent le vent, avec une traînée qui s'efface
  stopWind();
  const c = windCanvas(), ctx = c.getContext("2d"), [s, n, w, e] = wx.bbox;
  const count = Math.round(Math.min(1800, c.width * c.height / 500));
  const spawn = (p) => { p.lon = w + Math.random() * (e - w); p.lat = s + Math.random() * (n - s);
    p.age = Math.floor(Math.random() * 80); return p; };
  const parts = Array.from({length: count}, () => spawn({}));
  const k = (e - w) / 30000;  // degrés par (km/h × image) : 30 km/h traversent en ~17 s
  let id = 0;
  const frame = () => {
    ctx.globalCompositeOperation = "destination-in";
    ctx.fillStyle = "rgba(0,0,0,0.92)";
    ctx.fillRect(0, 0, c.width, c.height);
    ctx.globalCompositeOperation = "source-over";
    ctx.lineWidth = 1.3; ctx.strokeStyle = "rgba(255,255,255,0.8)";
    ctx.beginPath();
    for (const p of parts) {
      const a = map.project([p.lon, p.lat]);
      p.lon += sample(wx.u, p.lon, p.lat) * k / Math.max(Math.cos(p.lat * Math.PI / 180), 0.2);
      p.lat += sample(wx.v, p.lon, p.lat) * k;
      if (++p.age > 80 || p.lon < w || p.lon > e || p.lat < s || p.lat > n) {
        spawn(p); p.age = 0; continue;  // trop vieille ou sortie : elle renaît ailleurs
      }
      const b = map.project([p.lon, p.lat]);
      ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y);
    }
    ctx.stroke();
    id = requestAnimationFrame(frame);
  };
  id = requestAnimationFrame(frame);
  wxAnim = {stop: () => cancelAnimationFrame(id)};
}
function clearWeather() {
  stopWind();
  for (const id of ["wx-labels", "wx-temp"]) if (map.getLayer(id)) map.removeLayer(id);
  for (const id of ["wx-labels", "wx-temp"]) if (map.getSource(id)) map.removeSource(id);
  wx = null;
}
// Un lieu, le globe ou un itinéraire remplace la météo ; Friday écoute : le vent se repose
for (const name of ["fridayGo", "fridayWorld", "fridayRoute"]) {
  const shown = window[name];
  window[name] = (...args) => { clearWeather(); shown(...args); };
}
const stopAll = window.fridayStop, moveOn = window.fridayMove;
window.fridayStop = () => { stopWind(); stopAll(); };
window.fridayMove = () => {
  if (wx && wx.layers.includes("wind") && !wxAnim) { startWind(); return; }
  moveOn();
};
// Dessine (ou redessine, quand la carte suit le regard : weather_follow_js.py) la météo de wx
function paintWeather(wind) {
  const [s, n, w, e] = wx.bbox, corners = [[w, n], [e, n], [e, s], [w, s]];
  if (wx.layers.includes("temp") && map.getSource("wx-temp")) {
    map.getSource("wx-temp").updateImage({url: tempImage(), coordinates: corners});
    map.getSource("wx-labels").setData(tempLabels());
  } else if (wx.layers.includes("temp")) {
    const below = (map.getStyle().layers.find((l) => l.type === "symbol") || {}).id;
    map.addSource("wx-temp", {type: "image", url: tempImage(), coordinates: corners});
    map.addLayer({id: "wx-temp", type: "raster", source: "wx-temp",
      paint: {"raster-opacity": 0.55, "raster-fade-duration": 0}}, below);
    map.addSource("wx-labels", {type: "geojson", data: tempLabels()});
    map.addLayer({id: "wx-labels", type: "symbol", source: "wx-labels", layout: {
      "text-field": ["concat", ["to-string", ["get", "t"]], "°"],
      "text-font": ["Noto Sans Regular"], "text-size": 13, "text-allow-overlap": false},
      paint: {"text-color": "#ffffff", "text-halo-color": "rgba(0,0,0,0.75)",
        "text-halo-width": 1.4}});
  }
  if (wind && wx.layers.includes("wind")) startWind();
}
window.fridayWeather = (data) => whenReady(() => {
  stopSpin();
  leaveWorld();
  place = null;
  if (marker) { marker.remove(); marker = null; }
  clearRoute();
  clearWeather();
  wx = data;
  const [fs, fn, fw, fe] = data.fit || data.bbox;
  map.jumpTo({pitch: 0, bearing: 0});  // cadré sur la région ; les mesures autour la débordent
  map.fitBounds([[fw, fs], [fe, fn]], {padding: 10, duration: 0});
  paintWeather(true);
});
"""

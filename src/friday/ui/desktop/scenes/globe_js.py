"""Le globe de la veille monde (J9b), dans la page de la scène carte (map_page.py) : fond
étoilé, atmosphère, points qui « respirent », et TOUTES les étiquettes ouvertes, rangées en
deux colonnes de part et d'autre du globe (jamais l'une sur l'autre), chacune reliée à son
point par un trait ; elles suivent la rotation et se cachent quand leur point passe derrière.
Le globe tourne tout seul dès qu'il s'affiche ; toucher la carte l'arrête."""

GLOBE_CSS = """
#leaders,#callouts{pointer-events:none}
#leaders polyline{fill:none;stroke-width:1.2;stroke-opacity:.75}
#leaders circle{stroke:none}
.callout{position:absolute;left:0;top:0;width:230px;height:58px;box-sizing:border-box;
  padding:6px 10px;
  background:rgba(9,13,22,.78);border:1px solid rgba(255,255,255,.07);
  border-left:3px solid var(--c);border-radius:8px;backdrop-filter:blur(6px);
  box-shadow:0 4px 18px rgba(0,0,0,.45),0 0 12px color-mix(in srgb,var(--c) 25%,transparent);
  font-family:"Segoe UI",sans-serif;transition:opacity .3s}
.callout b{display:block;font-size:11px;font-weight:600;letter-spacing:1.2px;
  text-transform:uppercase;color:var(--c);white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis}
.callout span{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;
  overflow:hidden;font-size:11px;line-height:1.3;color:#b8c2d1;margin-top:2px}
"""

GLOBE_JS = """
// --- Globe de la veille monde (J9b) ---
const KIND_COLORS = {mine: "__ACCENT__", theme: "#7aa2c8", red: "#ff3b3b", orange: "#ff7aa8"};
const COLORS = ["match", ["get", "kind"], "mine", KIND_COLORS.mine, "theme", KIND_COLORS.theme,
  "red", KIND_COLORS.red, KIND_COLORS.orange];
const SVG = "http://www.w3.org/2000/svg";
const callouts = document.getElementById("callouts"), leaders = document.getElementById("leaders");
const CARD_W = 230, GAP = 66, MARGIN = 14, RAD = Math.PI / 180;  // cartes de 58 px
let labelled = [];
const geojson = (points) => ({type: "FeatureCollection", features: points.map((p) => ({
  type: "Feature", geometry: {type: "Point", coordinates: [p.lon, p.lat]}, properties: p}))});

function drawStars() {  // un ciel étoilé, dessiné une fois (et à chaque redimensionnement)
  const c = document.getElementById("stars"), ctx = c.getContext("2d");
  c.width = innerWidth; c.height = innerHeight;
  const glow = ctx.createRadialGradient(c.width / 2, c.height / 2, 0, c.width / 2,
    c.height / 2, Math.max(c.width, c.height) * 0.7);
  glow.addColorStop(0, "#14223d"); glow.addColorStop(1, "__BACKGROUND__");
  ctx.fillStyle = glow; ctx.fillRect(0, 0, c.width, c.height);
  ctx.fillStyle = "#ffffff";
  for (let i = 0; i < 420; i++) {
    ctx.globalAlpha = Math.random() * 0.55 + 0.1;
    ctx.beginPath();
    ctx.arc(Math.random() * c.width, Math.random() * c.height, Math.random() * 1.1 + 0.2, 0,
      2 * Math.PI);
    ctx.fill();
  }
  ctx.globalAlpha = 1;
}
drawStars();
addEventListener("resize", () => { drawStars(); layoutCallouts(); });

function addWorldLayers() {
  map.addSource("world", {type: "geojson", data: geojson([])});
  map.addLayer({id: "world-halo", type: "circle", source: "world", paint: {
    "circle-radius": ["*", 2.2, ["get", "size"]], "circle-color": COLORS,
    "circle-opacity": 0.22, "circle-blur": 0.7}});
  map.addLayer({id: "world-dots", type: "circle", source: "world", paint: {
    "circle-radius": ["*", 0.6, ["get", "size"]], "circle-color": COLORS,
    "circle-stroke-color": "#ffffff", "circle-stroke-width": 1.2, "circle-stroke-opacity": 0.8}});
  map.on("move", layoutCallouts);
}

function sky(world) {  // l'atmosphère bleutée autour du globe ; rien pour la carte des lieux
  try {
    map.setSky(world ? {"sky-color": "#0d2a55", "horizon-color": "#3d76c4",
      "fog-color": "__BACKGROUND__", "sky-horizon-blend": 0.7, "horizon-fog-blend": 0.6,
      "fog-ground-blend": 0.4, "atmosphere-blend": ["interpolate", ["linear"], ["zoom"],
        0, 1, 5, 1, 7, 0]} : {"atmosphere-blend": 0});
  } catch (e) { /* sans atmosphère : pas grave */ }
}

function leaveWorld() {
  mode = "place";
  map.setProjection({type: "mercator"});
  map.getSource("world").setData(geojson([]));
  sky(false);
  callouts.replaceChildren(); leaders.replaceChildren(); labelled = [];
}

function setCallouts(points) {
  callouts.replaceChildren(); leaders.replaceChildren();
  labelled = points.map((p) => {
    const color = KIND_COLORS[p.kind] || "#ffffff";
    const card = document.createElement("div");
    card.className = "callout";
    card.style.setProperty("--c", color);
    const title = document.createElement("b"), text = document.createElement("span");
    title.textContent = p.label; text.textContent = p.detail;
    card.append(title, text);
    callouts.append(card);
    const line = document.createElementNS(SVG, "polyline");
    line.setAttribute("stroke", color);
    const end = document.createElementNS(SVG, "circle");  // petit rond au bout du trait
    end.setAttribute("r", 2.5); end.setAttribute("fill", color);
    leaders.append(line, end);
    return {p, card, line, end};
  });
  layoutCallouts();
}

function facing(p, c) {  // le point est-il sur la face visible du globe ?
  return Math.sin(p.lat * RAD) * Math.sin(c.lat * RAD) + Math.cos(p.lat * RAD)
    * Math.cos(c.lat * RAD) * Math.cos((p.lon - c.lng) * RAD) > 0.12;
}

function stack(items, top, bottom) {  // hauteurs des étiquettes, sans chevauchement
  items.sort((a, b) => a.y - b.y);
  let previous = top - GAP;
  for (const it of items) { it.top = Math.max(it.y - 14, previous + GAP); previous = it.top; }
  let limit = bottom;
  for (let i = items.length - 1; i >= 0; i--) {
    items[i].top = Math.min(items[i].top, limit - GAP); limit = items[i].top;
  }
}

function layoutCallouts() {
  if (mode !== "world" || !labelled.length) return;
  const w = callouts.clientWidth, h = callouts.clientHeight, c = map.getCenter();
  const mid = map.project(c), radius = 230 * Math.pow(2, map.getZoom() - 1.6);
  const left = [], right = [];
  for (const it of labelled) {
    const shown = facing(it.p, c);
    for (const el of [it.card, it.line, it.end]) el.style.display = shown ? "" : "none";
    if (!shown) continue;
    const xy = map.project([it.p.lon, it.p.lat]);
    it.x = xy.x; it.y = xy.y;
    (xy.x < mid.x ? left : right).push(it);
  }
  for (const [items, side] of [[left, -1], [right, 1]]) {
    stack(items, MARGIN, h - MARGIN - 24);
    const edge = side < 0 ? Math.max(MARGIN + CARD_W, mid.x - radius - 48)
      : Math.min(w - MARGIN - CARD_W, mid.x + radius + 48);
    for (const it of items) {
      it.card.style.transform = `translate(${side < 0 ? edge - CARD_W : edge}px, ${it.top}px)`;
      const y = it.top + 14, elbow = edge - side * 22;
      it.line.setAttribute("points", `${it.x},${it.y} ${elbow},${y} ${edge},${y}`);
      it.end.setAttribute("cx", it.x); it.end.setAttribute("cy", it.y);
    }
  }
}

function spinGlobe() {  // tourne sur lui-même, les halos « respirent »
  stopSpin();
  let t = 0;
  spin = setInterval(() => {
    const c = map.getCenter();
    map.setCenter([c.lng + 0.1, c.lat]);
    t += 0.05;
    map.setPaintProperty("world-halo", "circle-radius",
      ["*", 2.2 + 0.45 * Math.sin(t * 2), ["get", "size"]]);
  }, 50);
}

// Le globe : points, étiquettes, atmosphère, puis la rotation, tout de suite
window.fridayWorld = (points) => whenReady(() => {
  stopSpin();
  mode = "world";
  place = null;
  if (marker) { marker.remove(); marker = null; }
  map.setProjection({type: "globe"});
  sky(true);
  map.getSource("world").setData(geojson(points));
  // Le globe occupe 75 % de la hauteur (à zoom 1,6, il mesure environ 460 px)
  const zoom = 1.6 + Math.log2(map.getContainer().clientHeight * 0.75 / 460);
  map.jumpTo({center: [20, 30], zoom: Math.max(1, zoom), pitch: 0, bearing: 0});
  setCallouts(points);
  spinGlobe();
});
"""

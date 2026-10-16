"""Les boutons de la carte (demandés après M1–M4) : afficher ou masquer soi-même les
températures, le vent et les avions, et les combiner (les avions par-dessus la météo).
Sur la carte à plat seulement (pas sur le globe ni dans l'espace).

La météo, la page la demande elle-même (weather_follow_js.py). Les avions, OpenSky refuse
qu'une page web les demande : la page écrit sa demande dans la console (« friday:{…} »),
Friday la lit (links_page.py) et renvoie les avions par window.fridayPlanesHere."""

LAYERS_CSS = """
#friday-layers{position:absolute;left:12px;top:96px;display:none;flex-direction:column;gap:6px;
  z-index:5;font:600 12px sans-serif}
#friday-layers button{all:unset;cursor:pointer;padding:7px 12px;border-radius:14px;color:#dfe8f5;
  background:rgba(11,13,18,.72);border:1px solid rgba(223,232,245,.18);backdrop-filter:blur(6px)}
#friday-layers button:hover{border-color:rgba(223,232,245,.45)}
#friday-layers button.on{color:#0b0d12;background:var(--accent);border-color:var(--accent)}
#friday-layers button.busy{opacity:.6}
#friday-layers .note{color:#dfe8f5;max-width:150px;text-shadow:0 0 4px #000;font-weight:400}
"""

LAYERS_JS = """
const layersPanel = document.createElement("div");
layersPanel.id = "friday-layers";
layersPanel.style.setProperty("--accent", "__ACCENT__");
document.body.append(layersPanel);
const layerButtons = {}, layersNote = document.createElement("div");
layersNote.className = "note";
let planesWanted = 0;  // numéro de la dernière demande d'avions (une plus récente l'emporte)
function layerButton(key, text, action) {
  const b = document.createElement("button");
  b.textContent = text;
  b.addEventListener("click", action);
  layersPanel.append(b);
  layerButtons[key] = b;
}
function syncLayers() {  // l'état des boutons suit ce qui est affiché
  layersPanel.style.display = mode === "place" ? "flex" : "none";
  const shown = (name) => !!(wx && wx.layers.includes(name));
  layerButtons.temp.classList.toggle("on", shown("temp"));
  layerButtons.wind.classList.toggle("on", shown("wind"));
  layerButtons.planes.classList.toggle("on", !!planes);
  layerButtons.here.style.display = planes ? "" : "none";
}
function hideTemp() {
  for (const id of ["wx-labels", "wx-temp"]) if (map.getLayer(id)) map.removeLayer(id);
  for (const id of ["wx-labels", "wx-temp"]) if (map.getSource(id)) map.removeSource(id);
}
function toggleWeather(name) {
  layersNote.textContent = "";
  wxAsked++;  // une mesure en cours ne rouvrira pas ce qu'on vient de fermer
  if (wx && wx.layers.includes(name)) {  // masquer
    wx.layers = wx.layers.filter((l) => l !== name);
    if (name === "temp") hideTemp(); else stopWind();
    if (!wx.layers.length) clearWeather();
  } else if (wx) {  // ajouter à la météo déjà mesurée
    wx.layers = [...wx.layers, name];
    paintWeather(name === "wind");
  } else {  // rien encore : la météo de ce qui est à l'écran
    layerButtons[name].classList.add("busy");
    wxFollowing = true;
    wxFollow([name]).finally(() => { layerButtons[name].classList.remove("busy"); syncLayers(); });
  }
  syncLayers();
}
function askPlanes() {  // à Friday : les avions de ce qui est à l'écran
  layersNote.textContent = "";
  layerButtons.planes.classList.add("busy");
  planesWanted++;
  console.info("friday:" + JSON.stringify({ask: "planes", box: wxView(), id: planesWanted}));
}
layerButton("temp", "Températures", () => toggleWeather("temp"));
layerButton("wind", "Vent", () => toggleWeather("wind"));
layerButton("planes", "Avions", () => {
  if (planes) { clearPlanes(); syncLayers(); } else askPlanes();
});
layerButton("here", "↻ Avions ici", askPlanes);
layersPanel.append(layersNote);
// La réponse de Friday : les avions, sans toucher au reste ni bouger la carte
window.fridayPlanesHere = (data, accent) => whenReady(() => {
  layerButtons.planes.classList.remove("busy");
  if (data.id !== planesWanted || mode !== "place") return;  // dépassée, ou plus sur la carte
  if (data.error) { layersNote.textContent = data.error; return; }
  clearPlanes();
  planes = {list: data.planes, since: performance.now(), accent: accent,
    sprite: planeSprite("#dfe8f5"), focusSprite: planeSprite(accent)};
  planeLayers();
  flyPlanes();
  layersNote.textContent = data.planes.length ? "" : "Aucun avion capté ici.";
  syncLayers();
});
// Ce que Friday montre (à la voix) remet les boutons à jour ; une demande en cours est oubliée
for (const name of ["fridayGo", "fridayWorld", "fridayRoute", "fridayWeather", "fridayPlanes",
  "fridaySpace"]) {
  const shown = window[name];
  window[name] = (...args) => {
    wxAsked++; planesWanted++; layersNote.textContent = "";
    shown(...args);
    whenReady(syncLayers);
  };
}
whenReady(syncLayers);
"""

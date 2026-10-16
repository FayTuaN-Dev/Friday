"""La météo suit le regard (M2, demandé après essai) : on déplace la carte de la France vers
l'Angleterre, ou on l'agrandit en plein écran, et les températures et le vent de ce qui est
à l'écran arrivent, sans bord visible. La page demande elle-même à Open-Meteo (gratuit, il
l'autorise), une demi-seconde après le dernier geste ; les points sont pris sur une grille
fixe et gardés 10 min, pour que revenir en arrière ne redemande rien (Open-Meteo compte
chaque point : 600 par minute au plus)."""

WEATHER_FOLLOW_JS = """
const WX_URL = "https://api.open-meteo.com/v1/forecast", WX_KEEP = 600000;
const WX_STEPS = [0.25, 0.5, 1, 2, 3, 5, 8, 12, 20];  // écart entre deux points, en degrés
const wxCache = new Map();
let wxTimer = 0, wxAsked = 0, wxFollowing = false;
const wrapLon = (lon) => ((lon + 540) % 360) - 180;
const wxKey = (lat, lon) => `${lat.toFixed(2)},${wrapLon(lon).toFixed(2)}`;
function wxView() {  // ce que la fenêtre montre, en degrés (un tour du monde au plus)
  const b = map.getBounds();
  let w = b.getWest(), e = b.getEast();
  if (e - w > 360) { const mid = (w + e) / 2; w = mid - 180; e = mid + 180; }
  return [Math.max(b.getSouth(), -80), Math.min(b.getNorth(), 80), w, e];
}
function wxGrid([s, n, w, e]) {  // une maille de plus tout autour : aucun bord à l'écran
  const sp = WX_STEPS.find((d) => (e - w) / d <= 12 && (n - s) / d <= 16) || 30;
  const south = Math.max(Math.floor(s / sp) * sp - sp, -84);
  const north = Math.min(Math.ceil(n / sp) * sp + sp, 84);
  const west = Math.floor(w / sp) * sp - sp, east = Math.ceil(e / sp) * sp + sp;
  return {sp, bbox: [south, north, west, east], nx: Math.round((east - west) / sp) + 1,
    ny: Math.round((north - south) / sp) + 1};
}
const covers = (box, [s, n, w, e]) => box[0] <= s && box[1] >= n && box[2] <= w && box[3] >= e;
async function wxMeasure(points) {  // en paquets de 200 points ; gardés dans wxCache
  for (let k = 0; k < points.length; k += 200) {
    const part = points.slice(k, k + 200);
    const url = `${WX_URL}?latitude=${part.map((p) => p[0].toFixed(2)).join(",")}`
      + `&longitude=${part.map((p) => wrapLon(p[1]).toFixed(2)).join(",")}`
      + "&current=temperature_2m,wind_speed_10m,wind_direction_10m";
    const response = await fetch(url);
    if (!response.ok) throw new Error("météo " + response.status);
    const rows = await response.json(), list = Array.isArray(rows) ? rows : [rows];
    part.forEach(([lat, lon], i) => {
      const c = list[i].current, rad = c.wind_direction_10m * Math.PI / 180;
      wxCache.set(wxKey(lat, lon), {at: Date.now(), t: c.temperature_2m,
        u: -c.wind_speed_10m * Math.sin(rad), v: -c.wind_speed_10m * Math.cos(rad)});
    });
  }
}
// `fresh` : les couches voulues quand rien n'est encore affiché (un bouton de la carte)
async function wxFollow(fresh) {
  if (!(wx || fresh) || !wxFollowing) return;
  const view = wxView(), g = wxGrid(view);
  if (wx && wx.sp === g.sp && covers(wx.bbox, view)) return;  // déjà tout ce qu'il faut
  const id = ++wxAsked, points = [];
  for (let j = 0; j < g.ny; j++) for (let i = 0; i < g.nx; i++) {
    points.push([g.bbox[0] + j * g.sp, g.bbox[2] + i * g.sp]);
  }
  const old = (p) => !(wxCache.get(wxKey(...p))?.at > Date.now() - WX_KEEP);
  try { await wxMeasure(points.filter(old)); } catch (error) { return; }  // muet : on garde
  if (id !== wxAsked || !(wx || fresh)) return;  // un geste plus récent, ou la météo fermée
  const got = points.map((p) => wxCache.get(wxKey(...p)));
  wx = {...(wx || {layers: fresh}), ...g, temp: got.map((m) => m.t), u: got.map((m) => m.u),
    v: got.map((m) => m.v)};
  paintWeather(!!fresh || !!wxAnim);  // le vent repart s'il soufflait (en pause : l'écoute)
}
// Seuls les gestes de l'utilisateur comptent (pas le cadrage fait par Friday)
map.on("moveend", (e) => {
  if (!wx || !e.originalEvent) return;
  wxFollowing = true;
  clearTimeout(wxTimer);
  wxTimer = setTimeout(wxFollow, 500);
});
const wxShow = window.fridayWeather;
window.fridayWeather = (data) => { wxFollowing = false; wxAsked++; wxShow(data); };
"""

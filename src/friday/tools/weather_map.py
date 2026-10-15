"""Météo sur la carte (M2) : « montre-moi le vent », « les températures en France ». Une grille
de points (12 × 12, en une seule demande à Open-Meteo, gratuit et sans compte) : la carte
colore les températures et fait courir des particules dans le sens du vent."""

import math
import time

import httpx

from friday.tools.base import Display, Tool, ToolResult
from friday.tools.place import HEADERS, find_place
from friday.voice.wake import normalize

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
# Zones connues (sud, nord, ouest, est) : la boîte de « France » chez OpenStreetMap va
# jusqu'aux outre-mer, inutilisable pour une carte
REGIONS = {
    "france": ("la France", (41.0, 51.5, -5.5, 10.0)),
    "europe": ("l'Europe", (34.0, 71.0, -25.0, 45.0)),
    "monde": ("le monde", (-60.0, 75.0, -180.0, 180.0)),
}
# Open-Meteo compte chaque point comme une demande (600 par minute) : constaté, 4 cartes de
# 256 points d'affilée → « trop de demandes ». 144 points suffisent, lissés par la carte.
GRID = (12, 12)
WORLD_GRID = (20, 10)
KEEP_SECONDS = 600  # « montre le vent » puis « et les températures » : pas de nouvelle demande
LAYERS = {"vent": ("wind",), "temperatures": ("temp",), "les deux": ("wind", "temp")}
TITLES = {("wind",): "Vent", ("temp",): "Températures", ("wind", "temp"): "Vent et températures"}
WINDS = ("du nord", "du nord-est", "d'est", "du sud-est", "du sud", "du sud-ouest", "d'ouest",
         "du nord-ouest")  # fmt: skip
SIDES = ("au nord", "au nord-est", "à l'est", "au sud-est", "au sud", "au sud-ouest", "à l'ouest",
         "au nord-ouest")  # fmt: skip


def region_box(client: httpx.Client, region: str) -> tuple[str, tuple] | None:
    """(nom, (sud, nord, ouest, est)) ; une ville ou une région : environ 400 km autour."""
    plain = normalize(region or "") or "france"
    for key, known in REGIONS.items():
        if key in plain:
            return known
    found = find_place(client, region)
    if found is None:
        return None
    lat, lon = float(found["lat"]), float(found["lon"])
    south, north, west, east = (float(v) for v in found["boundingbox"])
    span = min(max(north - south, (east - west) * math.cos(math.radians(lat)), 4.0), 30.0)
    wide = span / max(math.cos(math.radians(lat)), 0.3)
    name = found.get("name") or found["display_name"].split(",")[0]
    return name, (lat - span / 2, lat + span / 2, lon - wide * 0.7, lon + wide * 0.7)


def without_article(name: str) -> str:
    """« la France » → « France » (pour le titre de la carte)."""
    for article in ("la ", "le ", "l'"):
        if name.startswith(article):
            return name[len(article) :]
    return name


def grid(box: tuple, nx: int, ny: int) -> list[tuple[float, float]]:
    """Points (lat, lon), ligne par ligne du sud au nord, d'ouest en est."""
    south, north, west, east = box
    return [(round(south + (north - south) * j / (ny - 1), 3),
             round(west + (east - west) * i / (nx - 1), 3))
            for j in range(ny) for i in range(nx)]  # fmt: skip


def side(box: tuple, lat: float, lon: float) -> str:
    """Où est ce point dans la zone : « au nord-est », « au centre »."""
    south, north, west, east = box
    dy = (lat - (south + north) / 2) / (north - south)
    dx = (lon - (west + east) / 2) / (east - west)
    if math.hypot(dx, dy) < 0.15:
        return "au centre"
    return SIDES[round(math.degrees(math.atan2(dx, dy)) / 45) % 8]


def wind_vector(speed: float, direction: float) -> tuple[float, float]:
    """Vent venant de `direction` (degrés) → (u vers l'est, v vers le nord), en km/h."""
    rad = math.radians(direction)
    return -speed * math.sin(rad), -speed * math.cos(rad)


def wind_summary(u: list[float], v: list[float], speeds: list[float]) -> str:
    mean_u, mean_v = sum(u) / len(u), sum(v) / len(v)
    typical = sorted(speeds)[len(speeds) // 2]
    if typical < 5:
        return f"vent faible ({round(typical)} km/h en général)"
    origin = math.degrees(math.atan2(-mean_u, -mean_v)) % 360
    return f"vent {WINDS[round(origin / 45) % 8]}, {round(typical)} km/h en général"


class ShowWeatherMapTool(Tool):
    name = "show_weather_map"
    description = (
        "MONTRE la météo sur une CARTE : le vent animé et/ou les températures en couleur, sur "
        "la France, l'Europe, le monde ou autour d'un lieu (« montre-moi le vent », « carte "
        "des températures en France », « le vent en Bretagne »). Pour la météo d'une ville en "
        "mots, c'est get_weather."
    )
    parameters = {
        "layers": {"type": "string", "enum": ["vent", "températures", "les deux"],
                   "description": "Ce qui est demandé (les deux si rien de précis)"},
        "region": {"type": "string",
                   "description": "France, Europe, monde, ou un lieu (vide = la France)"},
    }  # fmt: skip

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(timeout=20, headers=HEADERS)
        self._kept: dict[tuple, tuple[float, list]] = {}  # zone → (quand, mesures)

    def _measure(self, points: list[tuple[float, float]]) -> list[dict] | None:
        """Temps actuel de chaque point (None : service saturé)."""
        key = tuple(points)
        # Constaté (CI) : avec « 0 » comme date par défaut, un PC allumé depuis moins de 10 min
        # croyait avoir des mesures récentes… vides
        if key in self._kept and time.monotonic() - self._kept[key][0] < KEEP_SECONDS:
            return self._kept[key][1]
        response = self.client.get(FORECAST_URL, params={
            "latitude": ",".join(str(lat) for lat, _ in points),
            "longitude": ",".join(str(lon) for _, lon in points),
            "current": "temperature_2m,wind_speed_10m,wind_direction_10m",
        })  # fmt: skip
        if response.status_code == 429:
            return None
        response.raise_for_status()
        rows = response.json()
        current = [r["current"] for r in (rows if isinstance(rows, list) else [rows])]
        self._kept = {key: (time.monotonic(), current)}
        return current

    def label(self, args: dict) -> str:
        return f"🌬️ Carte météo : {args.get('region') or 'France'}"

    def run(self, layers: str = "les deux", region: str = "") -> ToolResult:
        found = region_box(self.client, region)
        if found is None:
            return ToolResult(f"Dis EXACTEMENT : « Je ne trouve pas « {region} » sur la carte. »")
        name, box = found
        nx, ny = WORLD_GRID if box[3] - box[2] > 90 else GRID
        points = grid(box, nx, ny)
        current = self._measure(points)
        if current is None:
            return ToolResult("Dis EXACTEMENT : « Le service météo est saturé, redemandez-moi "
                              "dans une minute. »")  # fmt: skip
        temps = [round(c["temperature_2m"], 1) for c in current]
        speeds = [c["wind_speed_10m"] for c in current]
        vectors = [wind_vector(c["wind_speed_10m"], c["wind_direction_10m"]) for c in current]
        u, v = [x for x, _ in vectors], [y for _, y in vectors]
        shown = LAYERS.get(normalize(layers or ""), LAYERS["les deux"])
        coldest, hottest = temps.index(min(temps)), temps.index(max(temps))
        windiest = speeds.index(max(speeds))
        facts = []
        if "temp" in shown:
            cold, hot = side(box, *points[coldest]), side(box, *points[hottest])
            facts.append(f"températures de {round(temps[coldest])} °C ({cold}) à "
                         f"{round(temps[hottest])} °C ({hot})")  # fmt: skip
        if "wind" in shown:
            facts.append(f"{wind_summary(u, v, speeds)}, jusqu'à {round(speeds[windiest])} km/h "
                         f"({side(box, *points[windiest])})")  # fmt: skip
        data = {"bbox": list(box), "nx": nx, "ny": ny, "layers": list(shown), "temp": temps,
                "u": [round(x, 1) for x in u], "v": [round(y, 1) for y in v]}  # fmt: skip
        return ToolResult(
            f"Carte affichée sur {name}, en ce moment, mesures de toute la zone affichée (elle "
            f"déborde sur la mer et les pays voisins) : {' ; '.join(facts)}. Dis-le en une ou "
            "deux phrases (« sur la carte »), sans rien inventer.",
            Display("weather_map", f"{TITLES[shown]} · {without_article(name)}", data),
        )

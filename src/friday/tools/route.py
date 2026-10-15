"""Itinéraires (M1) : « trace-moi la route des Herbiers à Nantes », « combien de temps pour
aller à la tour Eiffel ? ». Les lieux sont trouvés par OpenStreetMap (Nominatim), la route
calculée par le serveur OSRM d'OpenStreetMap (FOSSGIS, gratuit, sans compte), puis tracée
sur la carte de Friday. Durées sans les bouchons : un GPS avec le trafic serait payant."""

import httpx

from friday.tools.base import Display, Tool, ToolResult
from friday.tools.place import HEADERS, find_place
from friday.voice.wake import normalize

ROUTING_URL = "https://routing.openstreetmap.de/{profile}/route/v1/driving/{a};{b}"
PROFILES = {"voiture": "routed-car", "velo": "routed-bike", "a pied": "routed-foot"}
SAID = {"voiture": "en voiture", "velo": "à vélo", "a pied": "à pied"}
HOME = {"", "chez moi", "maison", "la maison", "ici", "ma position", "mon domicile", "moi"}
MAX_POINTS = 4000  # assez pour une belle ligne, sans alourdir la page de la carte


def travel_mode(mode: str) -> str:
    plain = normalize(mode or "")
    if "velo" in plain or "bicyclette" in plain:
        return "velo"
    if "pied" in plain or "marche" in plain or "marchant" in plain:
        return "a pied"
    return "voiture"


def duration_text(seconds: float) -> str:
    minutes = max(1, round(seconds / 60))
    if minutes < 60:
        return f"{minutes} min"
    hours, rest = divmod(minutes, 60)
    if hours >= 24:  # Les Herbiers → Tokyo : « 6 j 10 h », pas « 153 h 54 »
        days, hours = divmod(round(minutes / 60), 24)
        return f"{days} j {hours} h" if hours else f"{days} j"
    return f"{hours} h {rest:02d}" if rest else f"{hours} h"


def distance_text(meters: float) -> str:
    km = meters / 1000
    return f"{km:.1f} km".replace(".", ",") if km < 10 else f"{round(km):,} km".replace(",", " ")


def thin(points: list, limit: int = MAX_POINTS) -> list:
    """Garde un point sur n (le premier et le dernier toujours), arrondis à ~1 m."""
    step = max(1, -(-len(points) // limit))
    kept = points[::step] + ([points[-1]] if (len(points) - 1) % step else [])
    return [[round(lon, 5), round(lat, 5)] for lon, lat in kept]


def latin(name: str) -> bool:
    return bool(name.strip()) and all(ord(c) < 0x250 for c in name)


def short_name(found: dict) -> str:
    return found.get("name") or found["display_name"].split(",")[0]


class ShowRouteTool(Tool):
    name = "show_route"
    description = (
        "Calcule un ITINÉRAIRE et le trace sur la carte, avec distance et durée (« trace-moi la "
        "route de Nantes à Lyon », « combien de temps pour aller à la tour Eiffel ? », « c'est "
        "loin, Bordeaux ? », « à vélo jusqu'au lac de Grand-Lieu »)."
    )
    parameters = {
        "destination": {"type": "string", "description": "L'arrivée, telle que dite"},
        "origin": {"type": "string",
                   "description": "Le départ, tel que dit (vide = chez l'utilisateur)"},
        "mode": {"type": "string", "enum": ["voiture", "vélo", "à pied"],
                 "description": "Le moyen de transport (voiture si rien n'est dit)"},
    }  # fmt: skip
    required = ("destination",)

    def __init__(self, home_city: str = "", client: httpx.Client | None = None) -> None:
        self.home_city = home_city
        self.client = client or httpx.Client(timeout=15, headers=HEADERS)

    def label(self, args: dict) -> str:
        start = args.get("origin") or self.home_city or "?"
        return f"🧭 Itinéraire : {start} → {args.get('destination', '')}"

    def run(self, destination: str, origin: str = "", mode: str = "voiture") -> ToolResult:
        if normalize(origin) in HOME:
            origin = self.home_city
        if not origin:
            return ToolResult("Le départ manque et la ville de l'utilisateur n'est pas réglée. "
                              "Demande-lui d'où il part, en une phrase.")  # fmt: skip
        start, end = find_place(self.client, origin), find_place(self.client, destination)
        for wanted, found in ((origin, start), (destination, end)):
            if found is None:
                return ToolResult(f"Dis EXACTEMENT : « Je ne trouve pas « {wanted} » sur la "
                                  "carte. »")  # fmt: skip
        kind = travel_mode(mode)
        a, b = (f"{p['lon']},{p['lat']}" for p in (start, end))
        response = self.client.get(
            ROUTING_URL.format(profile=PROFILES[kind], a=a, b=b),
            params={"overview": "full", "geometries": "geojson", "steps": "true"},
        )
        if response.status_code != 400:  # 400 : OSRM répond « pas de route » (NoRoute…)
            response.raise_for_status()
        data = response.json()
        if data.get("code") != "Ok" or not data.get("routes"):
            return ToolResult(f"Dis EXACTEMENT : « Je ne trouve pas de route {SAID[kind]} entre "
                              f"{short_name(start)} et {short_name(end)}. »")  # fmt: skip
        route = data["routes"][0]
        summary = route["legs"][0].get("summary", "") if route.get("legs") else ""
        # Constaté : « Autoroute du Soleil, Autoroute du Soleil » pour Paris → Marseille
        # …et des noms chinois vers Tokyo : seuls les noms en alphabet latin sont gardés
        roads = ", ".join(dict.fromkeys(r.strip() for r in summary.split(",") if latin(r)))
        km, time = distance_text(route["distance"]), duration_text(route["duration"])
        names = (short_name(start), short_name(end))
        shown = {
            "coords": thin(route["geometry"]["coordinates"]),
            "start": {"name": names[0], "lat": float(start["lat"]), "lon": float(start["lon"])},
            "end": {"name": names[1], "lat": float(end["lat"]), "lon": float(end["lon"])},
            "distance": km, "duration": time, "mode": kind, "roads": roads,
        }  # fmt: skip
        by = f", par {roads}" if roads else ""
        traffic = " sans les bouchons" if kind == "voiture" else ""
        return ToolResult(
            f"Itinéraire tracé sur la carte : {names[0]} → {names[1]} {SAID[kind]}, {km}, "
            f"environ {time}{traffic}{by}. Dis-le en une phrase (distance, durée et grands axes "
            "seulement), sans rien inventer.",
            Display("route", f"{names[0]} → {names[1]} · {km} · {time}", shown),
        )

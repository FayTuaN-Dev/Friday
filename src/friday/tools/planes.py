"""Les avions sur la carte (M3) : « montre les avions au-dessus de la France », « c'est quoi
l'avion au-dessus de chez moi ? ». Données : planes_data.py (OpenSky, adsbdb)."""

import math
from collections import Counter

import httpx

from friday.tools.base import Display, Tool, ToolResult
from friday.tools.place import HEADERS, find_place
from friday.tools.planes_data import Busy, Plane, bearing, distance_km, flight, model, planes_in
from friday.tools.weather_map import SIDES, inside, region_box, view_box, without_article

NEAR_KM = 75  # « au-dessus de chez moi » : le plus proche dans ce rayon
BUSY = ("Dis EXACTEMENT : « Le service des avions ne répond plus pour aujourd'hui ou est "
        "saturé : redemandez-moi plus tard. »")  # fmt: skip


def row(plane: Plane, label: str = "", focus: bool = False) -> list:
    """Un avion pour la carte : position, cap, altitude, vitesse, indicatif, description."""
    label = label or " · ".join(x for x in (plane.callsign, plane.airline) if x)
    return [round(plane.lon, 4), round(plane.lat, 4), round(plane.track), plane.meters,
            plane.kmh, plane.callsign, label, focus]  # fmt: skip


def planes_here(client: httpx.Client, box: list[float]) -> list[list]:
    """Les avions de ce que la carte montre (bouton « Avions » de la carte). Peut lever Busy."""
    south, north, west, east = box
    if east - west >= 360:
        west, east = -180.0, 180.0  # tout le tour du monde : planes_in demande tout
    else:  # OpenSky ne passe pas la ligne de changement de date : on s'arrête à ±180°
        west, east = max(west, -180.0), min(east, 180.0)
    return [row(p) for p in planes_in(client, (max(south, -90.0), min(north, 90.0), west, east))]


def around(lat: float, lon: float, km: float) -> tuple:
    """La zone (sud, nord, ouest, est) d'environ `km` autour d'un point."""
    dlat = km / 111
    dlon = dlat / max(math.cos(math.radians(lat)), 0.2)
    return lat - dlat, lat + dlat, lon - dlon, lon + dlon


class ShowPlanesTool(Tool):
    name = "show_planes"
    description = (
        "MONTRE les avions en vol, en direct, sur une carte (« montre les avions au-dessus de "
        "la France », « les avions en Bretagne », « le trafic aérien en Europe »)."
    )
    parameters = {
        "region": {"type": "string", "description": "Pays, région ou ville (vide = la France)"}
    }

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(timeout=25, headers=HEADERS)

    def label(self, args: dict) -> str:
        return f"✈️ Avions : {args.get('region') or 'France'}"

    def run(self, region: str = "") -> ToolResult:
        found = region_box(self.client, region)
        if found is None:
            return ToolResult(f"Dis EXACTEMENT : « Je ne trouve pas « {region} » sur la carte. »")
        name, box = found
        try:  # toute la fenêtre a ses avions ; on ne compte que ceux de la région
            planes = planes_in(self.client, view_box(box))
        except Busy:
            return ToolResult(BUSY)
        mine = [p for p in planes if inside(box, p.lat, p.lon)]
        if not mine:
            return ToolResult(f"Dis EXACTEMENT : « Aucun avion capté sur {name} en ce moment. »")
        airlines = Counter(p.airline for p in mine if p.airline).most_common(2)
        mostly = " et ".join(f"{a} ({n})" for a, n in airlines)
        facts = f"{len(mine)} avions en vol sur {name}" + (f", surtout {mostly}" if mostly else "")
        data = {"planes": [row(p) for p in planes], "bbox": list(view_box(box)), "fit": list(box)}
        return ToolResult(
            f"Carte des avions affichée sur {name}, en direct : {facts}. Dis-le en une phrase, "
            "et qu'on peut cliquer sur un avion pour voir son vol. Rien d'autre.",
            Display("planes", f"Avions · {without_article(name)} · {len(mine)}", data),
        )


class PlaneOverheadTool(Tool):
    name = "plane_overhead"
    description = (
        "L'avion le plus proche au-dessus d'un lieu, avec son vol (« c'est quoi l'avion "
        "au-dessus de chez moi ? », « quel avion passe au-dessus de Nantes ? »)."
    )
    parameters = {"place": {"type": "string", "description": "Le lieu (vide = chez l'utilisateur)"}}

    def __init__(self, home_city: str = "", client: httpx.Client | None = None) -> None:
        self.home_city = home_city
        self.client = client or httpx.Client(timeout=25, headers=HEADERS)

    def label(self, args: dict) -> str:
        return f"✈️ Au-dessus de {args.get('place') or self.home_city or 'chez vous'}"

    def run(self, place: str = "") -> ToolResult:
        where = place or self.home_city
        if not where:
            return ToolResult("La ville de l'utilisateur n'est pas réglée : demande-lui de quel "
                              "lieu il parle, en une phrase.")  # fmt: skip
        found = find_place(self.client, where)
        if found is None:
            return ToolResult(f"Dis EXACTEMENT : « Je ne trouve pas « {where} » sur la carte. »")
        lat, lon = float(found["lat"]), float(found["lon"])
        name = found.get("name") or where
        try:
            near = planes_in(self.client, around(lat, lon, NEAR_KM))
        except Busy:
            return ToolResult(BUSY)
        if not near:
            return ToolResult(f"Dis EXACTEMENT : « Aucun avion capté au-dessus de {name} en ce "
                              "moment. »")  # fmt: skip
        plane = min(near, key=lambda p: distance_km(lat, lon, p.lat, p.lon))
        km = distance_km(lat, lon, plane.lat, plane.lon)
        side = SIDES[round(bearing(lat, lon, plane.lat, plane.lon) / 45) % 8]
        info, kind = flight(self.client, plane.callsign), model(self.client, plane.hex)
        airline = info.get("airline") or plane.airline
        trip = (f", de {info['origin']} vers {info['destination']}"
                if info.get("origin") and info.get("destination") else "")  # fmt: skip
        what = " ".join(x for x in (kind or "un avion", f"de {airline}" if airline else "") if x)
        facts = (f"{what}, vol {plane.callsign or 'sans indicatif'}{trip}, à "
                 f"{round(plane.meters, -2)} m d'altitude et {plane.kmh} km/h, à {round(km)} km "
                 f"{side} de {name}")  # fmt: skip
        label = " · ".join(x for x in (plane.callsign, kind, airline) if x)
        path = info.get("path") or []
        data = {
            "planes": [row(p, label if p is plane else "", p is plane) for p in near],
            "home": [lon, lat],
            "path": [path[0], [plane.lon, plane.lat], path[1]] if len(path) == 2 else None,
        }
        return ToolResult(
            f"Avion le plus proche (en direct) : {facts}. Dis-le en une ou deux phrases, sans "
            "rien inventer.",
            Display("planes", f"Au-dessus de {name} · {plane.callsign or kind}", data),
        )

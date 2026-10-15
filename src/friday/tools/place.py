"""« Montre-moi la tour Eiffel », « montre-moi Tokyo » (J7) : le lieu est trouvé par le CODE
(OpenStreetMap / Nominatim, gratuit) puis affiché en carte 3D plein écran. Le zoom suit la
taille du lieu : un monument de près, une ville, un pays de loin."""

import math

import httpx

from friday.tools.base import Display, Tool, ToolResult

SEARCH_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "Friday-assistant-personnel/1.0 (usage local)"}
# Une ville se montre de près, même si sa zone officielle va loin (Tokyo et ses îles)
TOWNS = {"city", "town", "village", "municipality", "city_district", "suburb", "province"}


def find_place(client: httpx.Client, place: str) -> dict | None:
    """Le lieu le plus probable (OpenStreetMap), ou None."""
    response = client.get(SEARCH_URL, params={"q": place, "format": "json", "limit": 1,
                                              "accept-language": "fr"})  # fmt: skip
    response.raise_for_status()
    found = response.json()
    return found[0] if found else None


def zoom_for(bbox: list[str], kind: str = "") -> float:
    """Boîte du lieu [sud, nord, ouest, est] → zoom de carte (17 : un bâtiment, 4 : un pays)."""
    south, north, west, east = (float(v) for v in bbox)
    span = max(north - south, (east - west) * math.cos(math.radians((north + south) / 2)), 1e-4)
    zoom = max(3.0, min(16.3, math.log2(360 / span) - 0.5))  # un monument et ses abords
    return round(max(zoom, 10.5) if kind in TOWNS else zoom, 1)


class ShowPlaceTool(Tool):
    name = "show_place"
    description = (
        "Montre un LIEU RÉEL sur Terre en carte 3D plein écran (« montre-moi la tour Eiffel », "
        "« où se trouve Tokyo ? », « fais-moi voir le mont Saint-Michel »). Pas pour une image "
        "ni pour la météo."
    )
    parameters = {"place": {"type": "string", "description": "Le lieu, tel que dit"}}
    required = ("place",)

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(timeout=8, headers=HEADERS)

    def label(self, args: dict) -> str:
        return f"🗺️ Carte : {args.get('place', '')}"

    def run(self, place: str) -> ToolResult:
        top = find_place(self.client, place)
        if top is None:
            return ToolResult(f"Dis EXACTEMENT : « Je ne trouve pas « {place} » sur la carte. »")
        name = top.get("name") or top["display_name"].split(",")[0]
        where = ", ".join(top["display_name"].split(", ")[-2:])
        zoom = zoom_for(top["boundingbox"], top.get("addresstype", ""))
        data = {"lat": float(top["lat"]), "lon": float(top["lon"]), "zoom": zoom, "name": name}
        return ToolResult(f"Carte affichée en plein écran : {top['display_name']}. Dis en une "
                          "phrase ce que c'est et où ça se trouve, sans inventer.",
                          Display("place", f"{name} — {where}", data))  # fmt: skip

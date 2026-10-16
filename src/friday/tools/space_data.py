"""Les données de l'espace (M4), gratuites et sans compte : les orbites chez CelesTrak (qui
demande de ne pas les retélécharger plus d'une fois toutes les 2 h), les lancements chez
Launch Library 2 (15 demandes par heure), et le pays ou l'océan survolé chez OpenStreetMap."""

import time

import httpx
from sgp4.api import Satrec

from friday.tools.orbits import satellite

ORBITS_URL = "https://celestrak.org/NORAD/elements/gp.php"
LAUNCHES_URL = "https://ll.thespacedevs.com/2.3.0/launches/upcoming/"
REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
ORBITS_KEEP, LAUNCHES_KEEP = 2 * 3600, 1800
# Ce qu'on sait montrer : clé → (numéro du catalogue, nom dans une phrase, étiquette)
SATELLITES = {
    "iss": (25544, "l'ISS", "ISS"),
    "tiangong": (48274, "la station chinoise Tiangong", "Tiangong"),
    "hubble": (20580, "le télescope Hubble", "Hubble"),
}
DONE = {"Launch Successful", "Launch Failure", "Launch was a Partial Failure"}


class Busy(Exception):
    """Le service refuse (trop de demandes)."""


_orbits: dict[int, tuple[float, Satrec]] = {}
_launches: dict[str, tuple[float, list[dict]]] = {}


def fresh(kept: tuple | None, keep: float) -> bool:
    return kept is not None and time.monotonic() - kept[0] < keep


def orbit(client: httpx.Client, number: int) -> Satrec:
    if not fresh(_orbits.get(number), ORBITS_KEEP):
        response = client.get(ORBITS_URL, params={"CATNR": number, "FORMAT": "json"})
        if response.status_code in (403, 429, 503):
            raise Busy
        response.raise_for_status()
        _orbits[number] = (time.monotonic(), satellite(response.json()[0]))
    return _orbits[number][1]


def launches(client: httpx.Client, search: str = "") -> list[dict]:
    """Les prochains lancements (pas ceux qui viennent d'avoir lieu), du plus proche au plus
    lointain : nom, date (UTC, ISO), fusée, opérateur, mission, base, position de la base."""
    if not fresh(_launches.get(search), LAUNCHES_KEEP):
        params = {"limit": 10, "mode": "normal"} | ({"search": search} if search else {})
        response = client.get(LAUNCHES_URL, params=params)
        if response.status_code in (429, 503):
            raise Busy
        response.raise_for_status()
        found = []
        for item in response.json().get("results", []):
            if (item.get("status") or {}).get("name") in DONE:
                continue
            pad = item.get("pad") or {}
            mission = item.get("mission") or {}
            found.append({
                "name": item.get("name", ""),
                "net": item.get("net", ""),
                "status": (item.get("status") or {}).get("abbrev", ""),
                "precision": (item.get("net_precision") or {}).get("name", "Hour"),
                "rocket": ((item.get("rocket") or {}).get("configuration") or {}).get("name", ""),
                "provider": (item.get("launch_service_provider") or {}).get("name", ""),
                "mission": mission.get("name", ""),
                "orbit": (mission.get("orbit") or {}).get("name", ""),
                "pad": (pad.get("location") or {}).get("name", "") or pad.get("name", ""),
                "where": [float(pad["longitude"]), float(pad["latitude"])]
                if pad.get("latitude") not in (None, "") else None,
            })  # fmt: skip
        _launches[search] = (time.monotonic(), found)
    return _launches[search][1]


def ocean(lat: float, lon: float) -> str:
    """Au large : quel océan, en gros (assez pour « l'ISS survole l'Atlantique »)."""
    if lat < -55:
        return "l'océan Austral"
    if lat > 66:
        return "l'océan Arctique"
    if 30 < lat < 46 and -6 < lon < 37:
        return "la Méditerranée"
    if -70 < lon < 20:
        return "l'océan Atlantique"
    if 20 <= lon < 120 and lat < 30:
        return "l'océan Indien"
    return "l'océan Pacifique"


def overflown(client: httpx.Client, lat: float, lon: float) -> str:
    """Le pays survolé (son nom seul : « Canada »), ou l'océan (« l'océan Indien »)."""
    try:
        params = {"lat": lat, "lon": lon, "zoom": 3, "format": "json", "accept-language": "fr"}
        response = client.get(REVERSE_URL, params=params)
        country = (response.json().get("address") or {}).get("country", "")
    except (httpx.HTTPError, ValueError):
        country = ""
    return country or ocean(lat, lon)

"""Les avions en direct (M3) : positions par OpenSky Network (gratuit, sans compte : une
zone rectangulaire en une demande, 0,3 s pour la France ; environ 400 « crédits » par jour,
3 à 4 par carte), vol et modèle d'avion par adsbdb. Essayé d'abord : adsb.lol, mais une
demande par cercle de 463 km et une toutes les 3 s : 42 s pour la France."""

import math
from dataclasses import dataclass

import httpx

STATES_URL = "https://opensky-network.org/api/states/all"
FLIGHT_URL = "https://api.adsbdb.com/v0/callsign/{callsign}"
AIRCRAFT_URL = "https://api.adsbdb.com/v0/aircraft/{hex}"
MAX_SHOWN = 3000  # au-delà, la carte rame (l'Europe en compte environ 5 000)

# Indicatif → compagnie (les trois lettres OACI du début : « AFR1234 » = Air France)
AIRLINES = {
    "AFR": "Air France", "HOP": "Air France Hop", "TVF": "Transavia France", "TRA": "Transavia",
    "EZY": "easyJet", "EJU": "easyJet", "EZS": "easyJet", "RYR": "Ryanair", "RUK": "Ryanair",
    "VOE": "Volotea", "VLG": "Vueling", "IBE": "Iberia", "AEA": "Air Europa", "DLH": "Lufthansa",
    "EWG": "Eurowings", "CFG": "Condor", "BAW": "British Airways", "EIN": "Aer Lingus",
    "KLM": "KLM", "BEL": "Brussels Airlines", "SWR": "Swiss", "AUA": "Austrian", "TAP": "TAP",
    "ITY": "ITA Airways", "SAS": "SAS", "FIN": "Finnair", "NOZ": "Norwegian", "NAX": "Norwegian",
    "LOT": "LOT", "WZZ": "Wizz Air", "AEE": "Aegean", "THY": "Turkish Airlines",
    "PGT": "Pegasus", "SXS": "SunExpress", "UAE": "Emirates", "QTR": "Qatar Airways",
    "ETD": "Etihad", "RAM": "Royal Air Maroc", "DAH": "Air Algérie", "TAR": "Tunisair",
    "DAL": "Delta", "UAL": "United", "AAL": "American Airlines", "ACA": "Air Canada",
    "FDX": "FedEx", "UPS": "UPS", "DHK": "DHL", "BCS": "DHL", "CRL": "Corsair",
    "FBU": "French Bee", "CCM": "Air Corsica", "ASL": "ASL Airlines", "NJE": "NetJets",
}  # fmt: skip


class Busy(Exception):
    """OpenSky refuse (crédits du jour épuisés, ou trop de demandes)."""


@dataclass
class Plane:
    hex: str
    callsign: str
    lat: float
    lon: float
    track: float  # cap, degrés
    meters: int  # altitude
    kmh: int

    @property
    def airline(self) -> str:
        return AIRLINES.get(self.callsign[:3], "") if self.callsign[3:4].isdigit() else ""


def parse(state: list) -> Plane | None:
    """Un « état » OpenSky → un avion EN VOL avec une position (None sinon)."""
    hex_, callsign, _, _, _, lon, lat, altitude, on_ground, speed, track = state[:11]
    if lat is None or lon is None or on_ground or not altitude or altitude <= 0:
        return None
    return Plane(hex=hex_, callsign=(callsign or "").strip(), lat=lat, lon=lon,
                 track=float(track or 0), meters=round(altitude),
                 kmh=round((speed or 0) * 3.6))  # fmt: skip


def planes_in(client: httpx.Client, box: tuple) -> list[Plane]:
    """Les avions en vol dans la zone (sud, nord, ouest, est)."""
    south, north, west, east = box
    params = {} if east - west >= 360 else {"lamin": south, "lamax": north, "lomin": west,
                                            "lomax": east}  # fmt: skip
    response = client.get(STATES_URL, params=params)
    if response.status_code in (429, 503):
        raise Busy()
    response.raise_for_status()
    planes = [p for p in map(parse, response.json().get("states") or []) if p is not None]
    step = max(1, math.ceil(len(planes) / MAX_SHOWN))
    return planes[::step]


def _adsbdb(client: httpx.Client, url: str, key: str) -> dict:
    try:
        response = client.get(url)
        if response.status_code != 200:
            return {}
        return response.json().get("response", {}).get(key) or {}
    except (httpx.HTTPError, ValueError):
        return {}


def flight(client: httpx.Client, callsign: str) -> dict:
    """Compagnie, départ et arrivée d'un vol (adsbdb) ; vide si inconnu."""
    route = _adsbdb(client, FLIGHT_URL.format(callsign=callsign), "flightroute") if callsign else {}
    if not route:
        return {}
    airport = lambda key: route.get(key) or {}  # noqa: E731
    return {
        "airline": (route.get("airline") or {}).get("name", ""),
        "origin": airport("origin").get("municipality", ""),
        "destination": airport("destination").get("municipality", ""),
        "path": [[airport(k).get("longitude"), airport(k).get("latitude")]
                 for k in ("origin", "destination") if airport(k).get("latitude") is not None],
    }  # fmt: skip


def model(client: httpx.Client, hex_: str) -> str:
    """« Airbus A321 » (adsbdb, par l'identifiant de l'avion) ; vide si inconnu."""
    aircraft = _adsbdb(client, AIRCRAFT_URL.format(hex=hex_), "aircraft")
    maker, kind = aircraft.get("manufacturer", ""), aircraft.get("type", "")
    words = kind.split()
    if len(words) > 1 and any(c.isdigit() for c in words[0]):
        kind = words[0]  # « A319 111 » → « A319 » (la variante n'intéresse personne)
    if kind and maker and maker.split()[0].lower() not in kind.lower():
        return f"{maker.split()[0]} {kind}"
    return kind


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


def bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Direction (degrés depuis le nord) du point 1 vers le point 2."""
    p1, p2, dl = math.radians(lat1), math.radians(lat2), math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return math.degrees(math.atan2(x, y)) % 360

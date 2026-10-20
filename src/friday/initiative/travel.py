"""Durée de trajet en voiture de la maison à un lieu de l'agenda (OpenStreetMap, comme les
itinéraires de la carte), avec la position de l'arrivée (pour la météo du trajet). Gardée en
mémoire : le même lieu n'est demandé qu'une fois."""

import logging
from dataclasses import dataclass

import httpx

from friday.tools.place import HEADERS, find_place
from friday.tools.route import PROFILES, ROUTING_URL

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Route:
    seconds: float  # de route, sans les bouchons
    lat: float  # l'arrivée
    lon: float


class Travel:
    def __init__(self, home: str, client: httpx.Client | None = None) -> None:
        self.home = home
        self.client = client or httpx.Client(timeout=15, headers=HEADERS)
        self._known: dict[str, Route | None] = {}

    def route(self, place: str) -> Route | None:
        """Le trajet depuis la maison, ou None : lieu introuvable, pas de route, ou serveur
        injoignable (redemandé la fois suivante)."""
        key = " ".join(place.lower().split())
        if key not in self._known:
            try:
                self._known[key] = self._ask(place)
            except httpx.HTTPError as error:
                log.info("Trajet vers « %s » impossible : %s", place, error)
                return None
        return self._known[key]

    def seconds(self, place: str) -> float | None:
        found = self.route(place)
        return found.seconds if found else None

    def _ask(self, place: str) -> Route | None:
        start, end = find_place(self.client, self.home), find_place(self.client, place)
        if start is None or end is None:
            log.info("Trajet : « %s » ou « %s » introuvable", self.home, place)
            return None
        a, b = (f"{p['lon']},{p['lat']}" for p in (start, end))
        response = self.client.get(ROUTING_URL.format(profile=PROFILES["voiture"], a=a, b=b),
                                   params={"overview": "false"})  # fmt: skip
        if response.status_code == 400:  # pas de route
            return None
        response.raise_for_status()
        data = response.json()
        if data.get("code") != "Ok" or not data.get("routes"):
            return None
        return Route(float(data["routes"][0]["duration"]), float(end["lat"]), float(end["lon"]))

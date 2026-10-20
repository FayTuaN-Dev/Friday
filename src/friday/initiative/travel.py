"""Durée de trajet en voiture de la maison à un lieu de l'agenda (OpenStreetMap, comme les
itinéraires de la carte). Gardée en mémoire : le même lieu n'est demandé qu'une fois."""

import logging

import httpx

from friday.tools.place import HEADERS, find_place
from friday.tools.route import PROFILES, ROUTING_URL

log = logging.getLogger(__name__)


class Travel:
    def __init__(self, home: str, client: httpx.Client | None = None) -> None:
        self.home = home
        self.client = client or httpx.Client(timeout=15, headers=HEADERS)
        self._known: dict[str, float | None] = {}

    def seconds(self, place: str) -> float | None:
        """Secondes de route depuis la maison (sans les bouchons), ou None : lieu introuvable,
        pas de route, ou serveur injoignable (redemandé la fois suivante)."""
        key = " ".join(place.lower().split())
        if key not in self._known:
            try:
                self._known[key] = self._ask(place)
            except httpx.HTTPError as error:
                log.info("Trajet vers « %s » impossible : %s", place, error)
                return None
        return self._known[key]

    def _ask(self, place: str) -> float | None:
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
        return float(data["routes"][0]["duration"])

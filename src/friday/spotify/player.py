"""Spotify par son API (compte Premium) : trouver une playlist, un album, un artiste ou un
titre, et le lancer sur l'appli Spotify du PC (ouverte si besoin)."""

import logging
import os
import time
from collections.abc import Callable

import httpx

from friday.spotify.auth import SpotifyAccount
from friday.spotify.matching import Choice, best, clean

log = logging.getLogger(__name__)

API = "https://api.spotify.com/v1"
PLAYLISTS_KEPT = 600  # secondes : les playlists de l'utilisateur, relues toutes les 10 min
DEVICE_WAIT = 12  # secondes pour que l'appli, tout juste ouverte, apparaisse


class SpotifyError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


class Spotify:
    def __init__(self, account: SpotifyAccount, client: httpx.Client | None = None,
                 launch: Callable[[], None] = lambda: os.startfile("spotify:"),
                 sleep: Callable[[float], None] = time.sleep) -> None:  # fmt: skip
        self.account, self.launch, self.sleep = account, launch, sleep
        self.client = client or httpx.Client(timeout=10)
        self._playlists: tuple[float, list[Choice]] | None = None

    def _call(self, method: str, path: str, **kwargs) -> dict:
        headers = {"Authorization": f"Bearer {self.account.access_token()}"}
        response = self.client.request(method, API + path, headers=headers, **kwargs)
        if response.status_code >= 400:
            try:
                message = response.json().get("error", {}).get("message", "")
            except ValueError:
                message = response.text[:120]
            raise SpotifyError(response.status_code, message or f"erreur {response.status_code}")
        return response.json() if response.content else {}

    def my_playlists(self) -> list[Choice]:
        if self._playlists and time.time() - self._playlists[0] < PLAYLISTS_KEPT:
            return self._playlists[1]
        found, path = [], "/me/playlists?limit=50"
        while path and len(found) < 200:
            page = self._call("GET", path.replace(API, ""))
            found += [Choice("playlist", p["name"], p["uri"],
                             (p.get("owner") or {}).get("display_name", ""), mine=True)
                      for p in page.get("items") or [] if p]  # fmt: skip
            path = page.get("next")
        self._playlists = (time.time(), found)
        return found

    def search(self, query: str) -> list[Choice]:
        page = self._call("GET", "/search", params={
            "q": query, "type": "playlist,album,artist,track", "limit": 5})  # fmt: skip
        found = []
        for kind in ("playlist", "artist", "album", "track"):
            for item in (page.get(f"{kind}s") or {}).get("items") or []:
                if not item:  # Spotify renvoie parfois des cases vides
                    continue
                by = (
                    ", ".join(a["name"] for a in item.get("artists", [])[:2])
                    if kind in ("album", "track")
                    else (item.get("owner") or {}).get("display_name", "")
                )
                found.append(Choice(kind, item["name"], item["uri"], by))
        return found

    def find(self, query: str) -> Choice | None:
        wanted, _ = clean(query)
        return best(query, self.my_playlists() + self.search(wanted))

    def device(self) -> str:
        """L'appli Spotify où jouer : celle qui joue, sinon celle du PC (ouverte si besoin)."""
        for attempt in range(DEVICE_WAIT + 1):
            devices = self._call("GET", "/me/player/devices").get("devices", [])
            active = [d for d in devices if d.get("is_active")]
            computer = [d for d in devices if d.get("type") == "Computer"]
            if found := (active or computer or devices):
                return found[0]["id"]
            if attempt == 0:
                self.launch()  # appli fermée : on l'ouvre et on attend qu'elle se présente
            self.sleep(1)
        raise SpotifyError(404, "l'appli Spotify ne répond pas")

    def play(self, choice: Choice) -> None:
        body = {"uris": [choice.uri]} if choice.kind == "track" else {"context_uri": choice.uri}
        self._call("PUT", "/me/player/play", params={"device_id": self.device()}, json=body)
        log.info("Spotify : lecture de %s (%s)", choice.name, choice.kind)

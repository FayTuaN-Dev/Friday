"""Volume par SteelSeries Sonar (le mixeur de SteelSeries GG), par son serveur local.

Constaté : Sonar verrouille le volume général de Windows ET remet à 100 % le volume de
chaque application ; Friday disait « réglé à 30 % » sans effet. Le réglage passe donc par
Sonar lui-même : le master (ce que l'on entend), ou la sortie d'une application (Gaming,
Chat, Media, Aux). En mode streamer, seule la mixette d'écoute (« monitoring ») est touchée :
le son envoyé au stream ne change pas.

Adresse : GG l'écrit dans coreProps.json ; GG donne celle de Sonar (/subApps).
"""

import json
import logging
import os
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

CORE_PROPS = (Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
              / "SteelSeries" / "SteelSeries Engine 3" / "coreProps.json")  # fmt: skip
# Nom de la sortie Windows (« SteelSeries Sonar - Media (…) ») → voie de Sonar
CHANNELS = {"gaming": "game", "chat": "chatRender", "media": "media", "aux": "aux"}
NAMES = {"game": "Gaming", "chatRender": "Chat", "media": "Media", "aux": "Aux"}


def channel_of(device: str) -> str | None:
    """« SteelSeries Sonar - Media (SteelSeries Sonar Virtual Audio Device) » → « media »."""
    if "sonar - " not in device.lower():
        return None
    word = device.lower().split("sonar - ", 1)[1].split(" ", 1)[0]
    return CHANNELS.get(word)


class SonarUnavailable(Exception):
    pass


class Sonar:
    def __init__(self, base: str, client: httpx.Client | None = None) -> None:
        self.base = base.rstrip("/")
        self.client = client or httpx.Client(timeout=3)

    @classmethod
    def find(cls, props: Path = CORE_PROPS, client: httpx.Client | None = None) -> "Sonar | None":
        """Sonar en marche sur ce PC, ou None (pas de GG, GG fermé, Sonar désactivé)."""
        try:
            gg = json.loads(props.read_text("utf-8"))["ggEncryptedAddress"]
            with httpx.Client(verify=False, timeout=2) as local:  # certificat local de GG
                sonar = local.get(f"https://{gg}/subApps").json()["subApps"]["sonar"]
            if not (sonar.get("isEnabled") and sonar.get("isRunning")):
                return None
            return cls(sonar["metadata"]["webServerAddress"], client)
        except (OSError, KeyError, ValueError, httpx.HTTPError) as error:
            log.debug("Sonar introuvable : %s", error)
            return None

    def _call(self, method: str, path: str):
        try:
            response = self.client.request(method, self.base + path)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise SonarUnavailable(f"Sonar ne répond pas ({error})") from error

    def _streamer(self) -> bool:
        return self._call("GET", "/mode/") == "stream"

    def _path(self, channel: str, what: str, value: str) -> str:
        if self._streamer():
            return f"/volumeSettings/streamer/monitoring/{channel}/{what}/{value}"
        return f"/volumeSettings/classic/{channel}/{what}/{value}"

    def get(self, channel: str = "master") -> int:
        streamer = self._streamer()
        settings = self._call("GET", f"/volumeSettings/{'streamer' if streamer else 'classic'}")
        slot = settings["masters"] if channel == "master" else settings["devices"][channel]
        values = slot["stream"]["monitoring"] if streamer else slot["classic"]
        return round(values["volume"] * 100)

    def set(self, level: int, channel: str = "master") -> None:
        self._call("PUT", self._path(channel, "Volume", f"{max(0, min(100, level)) / 100:g}"))

    def mute(self, muted: bool, channel: str = "master") -> None:
        self._call("PUT", self._path(channel, "Mute", "true" if muted else "false"))

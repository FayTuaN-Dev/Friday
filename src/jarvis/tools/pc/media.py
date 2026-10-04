"""Outils : volume du PC, touches multimédia (lecture, piste suivante…) et musique."""

import os
import webbrowser
from urllib.parse import quote

import keyboard

from jarvis.tools.base import Tool, ToolResult

MEDIA_KEYS = {
    "play_pause": "play/pause media",
    "next": "next track",
    "previous": "previous track",
}


class Volume:
    """Volume général de Windows (pycaw)."""

    def _endpoint(self):
        import comtypes
        from pycaw.pycaw import AudioUtilities

        comtypes.CoInitialize()  # chaque outil tourne dans son propre thread
        return AudioUtilities.GetSpeakers().EndpointVolume

    def get(self) -> int:
        return round(self._endpoint().GetMasterVolumeLevelScalar() * 100)

    def set(self, level: int) -> None:
        self._endpoint().SetMasterVolumeLevelScalar(max(0, min(100, level)) / 100, None)

    def mute(self, muted: bool) -> None:
        self._endpoint().SetMute(int(muted), None)


class VolumeTool(Tool):
    name = "set_volume"
    description = (
        "Règle le volume de l'ordinateur : un niveau précis (0 à 100), une variation "
        "(+10 pour monter, -10 pour baisser), ou couper / remettre le son."
    )
    parameters = {
        "level": {"type": "integer", "description": "Niveau voulu, de 0 à 100"},
        "change": {"type": "integer", "description": "Variation : +10, -20…"},
        "mute": {"type": "boolean", "description": "true = couper le son, false = le remettre"},
    }

    def __init__(self, volume=None) -> None:
        self.volume = volume or Volume()

    def label(self, args: dict) -> str:
        return "🔊 Volume"

    def run(self, level: int | None = None, change: int | None = None,
            mute: bool | None = None) -> ToolResult:  # fmt: skip
        if mute is not None:
            self.volume.mute(bool(mute))
            return ToolResult("Son coupé." if mute else "Son remis.")
        if level is None and change is None:
            return ToolResult(f"Le volume est à {self.volume.get()} %.")
        target = int(level) if level is not None else self.volume.get() + int(change)
        self.volume.set(target)
        self.volume.mute(False)
        return ToolResult(f"Volume réglé à {max(0, min(100, target))} %.")


class MediaTool(Tool):
    name = "media_control"
    description = (
        "Contrôle la musique ou la vidéo en cours (Spotify, YouTube…) : mettre en pause ou "
        "reprendre, piste suivante, piste précédente."
    )
    parameters = {"action": {"type": "string", "enum": list(MEDIA_KEYS), "description": "L'action"}}
    required = ("action",)

    def __init__(self, press=keyboard.send) -> None:
        self.press = press

    def label(self, args: dict) -> str:
        return {"play_pause": "⏯️ Lecture / pause", "next": "⏭️ Piste suivante",
                "previous": "⏮️ Piste précédente"}.get(args.get("action"), "🎵 Musique")  # fmt: skip

    def run(self, action: str) -> ToolResult:
        if action not in MEDIA_KEYS:
            return ToolResult(f"Action inconnue : {action}.")
        self.press(MEDIA_KEYS[action])
        return ToolResult("C'est fait.")


class PlayMusicTool(Tool):
    name = "play_music"
    description = (
        "Cherche une musique, un artiste ou une playlist dans Spotify (ou sur YouTube si "
        "Spotify n'est pas installé). La recherche s'ouvre ; il reste à lancer la lecture."
    )
    parameters = {"query": {"type": "string", "description": "Titre, artiste, style, playlist"}}
    required = ("query",)

    def __init__(self, has_spotify: bool, open_uri=os.startfile, open_url=webbrowser.open):
        self.has_spotify = has_spotify
        self.open_uri, self.open_url = open_uri, open_url

    def label(self, args: dict) -> str:
        return f"🎵 Musique : {args.get('query', '')}"

    def run(self, query: str) -> ToolResult:
        if self.has_spotify:
            self.open_uri(f"spotify:search:{quote(query)}")
            return ToolResult(f"Recherche « {query} » ouverte dans Spotify.")
        self.open_url(f"https://www.youtube.com/results?search_query={quote(query)}")
        return ToolResult(f"Recherche « {query} » ouverte sur YouTube.")

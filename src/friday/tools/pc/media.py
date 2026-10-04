"""Outils : touches multimédia (lecture, piste suivante…) et recherche de musique."""

import os
import webbrowser
from urllib.parse import quote

import keyboard

from friday.tools.base import Tool, ToolResult

MEDIA_KEYS = {
    "play_pause": "play/pause media",
    "next": "next track",
    "previous": "previous track",
}


class MediaTool(Tool):
    name = "media_control"
    description = (
        "Contrôle la musique ou la vidéo (Spotify, YouTube…) : lancer la lecture (de ce qui est "
        "affiché ou était en cours), mettre en pause, piste suivante, piste précédente. "
        "« Lance la musique », « change de musique », « suivante » : c'est cet outil."
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
            return ToolResult(
                f"Recherche « {query} » ouverte dans Spotify. Dis à l'utilisateur d'ouvrir le "
                "résultat voulu (playlist, album…) ; dès qu'il le demande, lance la lecture avec "
                "media_control (play_pause)."
            )
        self.open_url(f"https://www.youtube.com/results?search_query={quote(query)}")
        return ToolResult(f"Recherche « {query} » ouverte sur YouTube.")

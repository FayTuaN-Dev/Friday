"""Contrôle du PC (Windows) : applications, sites, volume, musique."""

import sys
import threading

from friday.tools.base import Tool


def spotify_player(settings):
    """Spotify par son API, si une application est réglée (SPOTIFY_CLIENT_ID) ; sinon None."""
    if settings is None or not getattr(settings, "spotify_client_id", ""):
        return None
    from friday.core.config import DATA_DIR
    from friday.spotify.auth import SpotifyAccount
    from friday.spotify.player import Spotify

    return Spotify(SpotifyAccount(settings.spotify_client_id, DATA_DIR / "spotify_token.json"))


def pc_tools(settings=None) -> list[Tool]:
    if sys.platform != "win32":
        return []
    from friday.tools.pc.apps import CloseAppTool, OpenAppTool
    from friday.tools.pc.apps_index import AppIndex
    from friday.tools.pc.media import MediaTool, PlayMusicTool
    from friday.tools.pc.volume import VolumeTool
    from friday.tools.pc.web import OpenWebsiteTool

    index = AppIndex()
    threading.Thread(target=lambda: index.apps, daemon=True, name="apps-index").start()

    class _LazySpotify:  # vérifié au moment de chercher (l'index se charge en arrière-plan)
        def __bool__(self) -> bool:
            return index.find("spotify") is not None

    return [
        OpenAppTool(index),
        CloseAppTool(index),
        OpenWebsiteTool(),
        VolumeTool(),
        MediaTool(),
        PlayMusicTool(_LazySpotify(), spotify_player(settings)),
    ]

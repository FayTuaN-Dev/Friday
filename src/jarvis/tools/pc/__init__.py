"""Contrôle du PC (Windows) : applications, sites, volume, musique."""

import sys
import threading

from jarvis.tools.base import Tool


def pc_tools() -> list[Tool]:
    if sys.platform != "win32":
        return []
    from jarvis.tools.pc.apps import CloseAppTool, OpenAppTool
    from jarvis.tools.pc.apps_index import AppIndex
    from jarvis.tools.pc.media import MediaTool, PlayMusicTool, VolumeTool
    from jarvis.tools.pc.web import OpenWebsiteTool

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
        PlayMusicTool(_LazySpotify()),
    ]

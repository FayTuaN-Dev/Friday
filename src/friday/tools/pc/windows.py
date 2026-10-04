"""Fermer proprement les fenêtres d'une application (comme un clic sur la croix).

On envoie WM_CLOSE aux fenêtres au lieu de tuer le processus : l'application peut ainsi
proposer d'enregistrer le travail en cours.
"""

import ctypes
import logging
from ctypes import wintypes

import psutil

from friday.voice.wake import normalize

log = logging.getLogger(__name__)

WM_CLOSE = 0x0010


def find_processes(app_name: str) -> list[psutil.Process]:
    """Processus dont le nom de programme ressemble à l'application (« spotify » → Spotify.exe)."""
    wanted = normalize(app_name).replace(" ", "")
    found = []
    for proc in psutil.process_iter(["name"]):
        exe = normalize((proc.info["name"] or "").removesuffix(".exe")).replace(" ", "")
        if exe and (exe == wanted or (len(wanted) >= 4 and wanted in exe)):
            found.append(proc)
    return found


def close_windows(pids: set[int]) -> int:
    """Demande la fermeture des fenêtres visibles de ces processus ; renvoie leur nombre."""
    if not pids:
        return 0
    user32 = ctypes.windll.user32
    closed = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def on_window(hwnd, _lparam):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and user32.IsWindowVisible(hwnd):
            user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
            closed.append(hwnd)
        return True

    user32.EnumWindows(on_window, 0)
    log.info("WM_CLOSE envoyé à %d fenêtre(s)", len(closed))
    return len(closed)

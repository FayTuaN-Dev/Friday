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


def visible_windows() -> list[tuple[int, int, str]]:
    """Fenêtres visibles : (poignée, processus, titre)."""
    user32 = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def on_window(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            title = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, title, 256)
            found.append((hwnd, pid.value, title.value))
        return True

    user32.EnumWindows(on_window, 0)
    return found


def windows_titled(app_name: str) -> set[int]:
    """Fenêtres dont le titre contient le nom : repli quand le programme porte un autre nom
    que l'application (LibreOffice tourne sous « soffice.bin », sa fenêtre s'appelle
    « ticket.pdf - LibreOffice Draw »)."""
    wanted = normalize(app_name).replace(" ", "")
    if len(wanted) < 4:
        return set()
    return {
        hwnd for hwnd, _pid, title in visible_windows()
        if title and wanted in normalize(title).replace(" ", "")
    }  # fmt: skip


def close_hwnds(hwnds: set[int]) -> int:
    for hwnd in hwnds:
        ctypes.windll.user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    log.info("WM_CLOSE envoyé à %d fenêtre(s)", len(hwnds))
    return len(hwnds)


def close_windows(pids: set[int]) -> int:
    """Demande la fermeture des fenêtres visibles de ces processus ; renvoie leur nombre."""
    if not pids:
        return 0
    return close_hwnds({hwnd for hwnd, pid, _title in visible_windows() if pid in pids})

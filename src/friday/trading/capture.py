"""Capture CIBLÉE du graphique : uniquement la fenêtre dont le titre contient « TradingView »
(réglable), recadrée sur la zone choisie par l'utilisateur. Jamais l'écran entier.

`PrintWindow` lit le contenu de LA fenêtre elle-même : même si une autre fenêtre est
par-dessus (Friday, une notification…), elle n'apparaît pas sur la capture. Si la fenêtre
est introuvable, réduite ou illisible : pas de capture du tout (aucun repli sur l'écran).
"""

import ctypes
import io
import json
import os
import re
import sys
from ctypes import wintypes
from dataclasses import asdict, dataclass
from pathlib import Path

MAX_WIDTH = 1600
PW_RENDERFULLCONTENT = 2  # contenu rendu par la carte graphique (navigateurs, Electron)
PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)
# TradingView ne met pas son nom dans le titre de l'onglet : « EURUSD 1,12585 ▲ +0.36% »
# (symbole, cours, variation). Constaté dans Chrome.
TICKER_TITLE = re.compile(r"^[A-Z0-9:._!/-]{2,}\s+\d[\d\s.,]*\s*[▲▼]?\s*[+\-−]?\d[\d.,]*\s?%")


class CaptureUnavailable(Exception):
    """Message destiné à l'utilisateur (montré dans l'aperçu)."""


@dataclass
class Zone:
    """Zone gardée, en fractions de la fenêtre (0 à 1) : suit la fenêtre redimensionnée."""

    left: float = 0.0
    top: float = 0.0
    right: float = 1.0
    bottom: float = 1.0

    def valid(self) -> bool:
        return 0 <= self.left < self.right <= 1 and 0 <= self.top < self.bottom <= 1

    def box(self, width: int, height: int) -> tuple[int, int, int, int]:
        return (round(self.left * width), round(self.top * height),
                round(self.right * width), round(self.bottom * height))  # fmt: skip


def load_zone(path: Path) -> Zone:
    try:
        zone = Zone(**json.loads(path.read_text("utf-8")).get("zone", {}))
        return zone if zone.valid() else Zone()
    except (OSError, ValueError, TypeError):
        return Zone()


def save_zone(path: Path, zone: Zone) -> None:
    data = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text("utf-8"))
        except ValueError:
            data = {}
    data["zone"] = asdict(zone)
    path.write_text(json.dumps(data, indent=2), "utf-8")


# --- Windows ---------------------------------------------------------------------------------


def _api():
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    # Poignées 64 bits : sans ces déclarations, ctypes les tronque.
    user32.GetWindowDC.restype = wintypes.HDC
    user32.GetWindowDC.argtypes = [wintypes.HWND]
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
    user32.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
    gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi32.DeleteDC.argtypes = [wintypes.HDC]
    gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
                                ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]  # fmt: skip
    return user32, gdi32


def is_chart_title(title: str, title_part: str) -> bool:
    """Le titre contient `title_part`, ou (réglage par défaut « TradingView ») c'est un titre de
    graphique TradingView : symbole, cours, variation en %."""
    if title_part.lower() in title.lower():
        return True
    return title_part.lower() == "tradingview" and bool(TICKER_TITLE.match(title))


def find_window(title_part: str) -> tuple[int, str] | None:
    """La plus grande fenêtre visible (non réduite) au titre de graphique, hors des fenêtres
    de Friday elle-même."""
    if sys.platform != "win32" or not title_part.strip():
        return None
    user32 = ctypes.windll.user32
    own_pid, found = os.getpid(), []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _):
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        title = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title, length + 1)
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if is_chart_title(title.value, title_part) and pid.value != own_pid:
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            area = (rect.right - rect.left) * (rect.bottom - rect.top)
            found.append((area, hwnd, title.value))
        return True

    user32.EnumWindows(visit, 0)
    if not found:
        return None
    _, hwnd, title = max(found)
    return hwnd, title


def window_image(hwnd: int):
    """Image (PIL) du contenu de la fenêtre, même cachée par d'autres fenêtres."""
    from PIL import Image

    user32, gdi32 = _api()
    previous = user32.SetThreadDpiAwarenessContext(PER_MONITOR_AWARE_V2)  # vraies dimensions
    try:
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        width, height = rect.right - rect.left, rect.bottom - rect.top
        if width <= 0 or height <= 0:
            raise CaptureUnavailable("La fenêtre du graphique a une taille nulle.")
        window_dc = user32.GetWindowDC(hwnd)
        memory_dc = gdi32.CreateCompatibleDC(window_dc)
        bitmap = gdi32.CreateCompatibleBitmap(window_dc, width, height)
        gdi32.SelectObject(memory_dc, bitmap)
        try:
            if not user32.PrintWindow(hwnd, memory_dc, PW_RENDERFULLCONTENT):
                raise CaptureUnavailable("Windows n'a pas pu lire la fenêtre du graphique.")
            header = (ctypes.c_uint32 * 10)(40, width, (-height) & 0xFFFFFFFF, 1 | (32 << 16))
            pixels = ctypes.create_string_buffer(width * height * 4)
            gdi32.GetDIBits(memory_dc, bitmap, 0, height, pixels, header, 0)
        finally:
            gdi32.DeleteObject(bitmap)
            gdi32.DeleteDC(memory_dc)
            user32.ReleaseDC(hwnd, window_dc)
    finally:
        if previous:
            user32.SetThreadDpiAwarenessContext(previous)
    image = Image.frombuffer("RGB", (width, height), pixels, "raw", "BGRX", 0, 1)
    if image.getextrema() in (((0, 0), (0, 0), (0, 0)),):
        raise CaptureUnavailable("La capture du graphique est vide (fenêtre non affichable).")
    return image


def to_png(image, zone: Zone, max_width: int = MAX_WIDTH) -> bytes:
    from PIL import Image

    image = image.crop(zone.box(*image.size))
    if image.width > max_width:
        image = image.resize((max_width, round(image.height * max_width / image.width)),
                             Image.LANCZOS)  # fmt: skip
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


class ChartCapture:
    def __init__(self, title_part: str, zone_path: Path) -> None:
        self.title_part, self.zone_path = title_part, zone_path

    def full_window(self):
        """Toute la fenêtre (pour choisir la zone dans les réglages)."""
        found = find_window(self.title_part)
        if found is None:
            raise CaptureUnavailable(
                f"Fenêtre « {self.title_part} » introuvable (ouverte et non réduite ?)."
            )
        return window_image(found[0])

    def window_title(self) -> str | None:
        """Titre de la fenêtre du graphique (« XAUUSD 4 192,7 ▲… » : le symbole affiché)."""
        found = find_window(self.title_part)
        return found[1] if found else None

    def capture(self) -> bytes:
        """PNG de la zone choisie de la fenêtre du graphique."""
        return to_png(self.full_window(), load_zone(self.zone_path))

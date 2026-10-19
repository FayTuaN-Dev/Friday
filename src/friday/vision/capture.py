"""Capture d'écran : l'écran où se trouve la souris (là où l'utilisateur travaille)."""

import ctypes
import io
import sys
from ctypes import wintypes

MAX_WIDTH = 1600  # au-delà, plus lent à analyser sans mieux lire


def cursor_position() -> tuple[int, int] | None:
    if sys.platform != "win32":
        return None
    point = wintypes.POINT()
    if not ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
        return None
    return point.x, point.y


def pick_monitor(monitors: list[dict], cursor: tuple[int, int] | None) -> dict:
    """`monitors` au format mss : [0] = tous les écrans, puis un par écran."""
    screens = monitors[1:] or monitors
    if cursor:
        x, y = cursor
        for m in screens:
            if m["left"] <= x < m["left"] + m["width"] and m["top"] <= y < m["top"] + m["height"]:
                return m
    return screens[0]  # écran principal


def capture_screen(max_width: int = MAX_WIDTH) -> bytes:
    """PNG de l'écran sous la souris, réduit à `max_width` pixels de large au plus."""
    import mss
    from PIL import Image

    with mss.MSS() as sct:
        shot = sct.grab(pick_monitor(sct.monitors, cursor_position()))
        image = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    if image.width > max_width:
        image = image.resize((max_width, round(image.height * max_width / image.width)),
                             Image.LANCZOS)  # fmt: skip
    buffer = io.BytesIO()
    image.save(buffer, "PNG", optimize=False)
    return buffer.getvalue()


def load_image(path, max_width: int = MAX_WIDTH) -> bytes:
    """PNG d'une image du disque (collée ou glissée dans la fenêtre), réduite comme l'écran."""
    from PIL import Image

    with Image.open(path) as opened:
        image = opened.convert("RGB")
    if image.width > max_width:
        image = image.resize((max_width, round(image.height * max_width / image.width)),
                             Image.LANCZOS)  # fmt: skip
    buffer = io.BytesIO()
    image.save(buffer, "PNG", optimize=False)
    return buffer.getvalue()

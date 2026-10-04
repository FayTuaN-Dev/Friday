"""Coins arrondis natifs de Windows 11 (DWM), pour une fenêtre sans bordure.

Une fenêtre transparente (l'autre façon d'avoir des coins arrondis avec Qt) clignote quand on
la redimensionne : sous Windows 11, on laisse donc Windows arrondir une fenêtre opaque (avec
son ombre et une fine bordure à la couleur de Friday). Ailleurs : repli sur la transparence.
"""

import ctypes
import logging
import sys

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget

log = logging.getLogger(__name__)

DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_BORDER_COLOR = 34
DWMWCP_ROUND = 2
WINDOWS_11_BUILD = 22000


def native_corners_available() -> bool:
    return sys.platform == "win32" and sys.getwindowsversion().build >= WINDOWS_11_BUILD


def _set_attribute(window: QWidget, attribute: int, value: int) -> bool:
    try:
        data = ctypes.c_int(value)
        result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            ctypes.c_void_p(int(window.winId())), attribute, ctypes.byref(data), ctypes.sizeof(data)
        )
        return result == 0
    except (AttributeError, OSError) as error:
        log.debug("DWM indisponible : %s", error)
        return False


def round_corners(window: QWidget) -> bool:
    return _set_attribute(window, DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND)


def set_border_color(window: QWidget, color: QColor) -> bool:
    colorref = color.red() | color.green() << 8 | color.blue() << 16  # format 0x00BBGGRR
    return _set_attribute(window, DWMWA_BORDER_COLOR, colorref)

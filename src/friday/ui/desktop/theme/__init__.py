"""Thème de l'interface : une couleur de base → palette → feuille de style.

`current()` donne la palette en cours ; `apply_theme()` la change à chaud (toute l'application
et les pop-ups se re-colorent).
"""

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from friday.ui.desktop.theme.palette import (
    DEFAULT,
    PRESETS,
    Palette,
    build_palette,
    parse_color,
    state_color,
)
from friday.ui.desktop.theme.stylesheet import FONT_HUD, FONT_UI, stylesheet

_current = build_palette(QColor(PRESETS[DEFAULT]))


def current() -> Palette:
    return _current


def apply_theme(app: QApplication, base: QColor, light: bool = False) -> Palette:
    """`light` : l'ambiance « verre » (claire) plutôt que la sombre."""
    global _current
    _current = build_palette(base, light)
    app.setStyleSheet(stylesheet(_current))
    links = app.palette()  # couleur des liens cliquables (non réglable par feuille de style)
    links.setColor(QPalette.Link, QColor(_current.accent))
    links.setColor(QPalette.LinkVisited, QColor(_current.muted))
    app.setPalette(links)
    return _current


__all__ = [
    "DEFAULT", "FONT_HUD", "FONT_UI", "PRESETS", "Palette", "apply_theme", "build_palette",
    "current", "parse_color", "state_color", "stylesheet",
]  # fmt: skip

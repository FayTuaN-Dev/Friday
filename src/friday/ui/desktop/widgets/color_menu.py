"""Menu des couleurs : palettes prêtes à l'emploi + « Autre couleur… » (sélecteur libre)."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QColorDialog, QMenu, QWidget

from friday.ui.desktop.theme import PRESETS


def swatch(color: QColor, size: int = 14) -> QIcon:
    """Pastille ronde de la couleur, devant le nom de la palette."""
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(color)
    painter.drawEllipse(2, 2, size * 2 - 4, size * 2 - 4)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)


class ColorMenu(QMenu):
    color_chosen = Signal(QColor)

    def __init__(self, current: QColor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.current = QColor(current)
        # Coins arrondis : la fenêtre du menu doit être transparente autour du panneau
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        for name, value in PRESETS.items():
            action = self.addAction(swatch(QColor(value)), name)
            action.triggered.connect(lambda _=False, v=value: self._choose(QColor(v)))
        self.addSeparator()
        self.addAction("Autre couleur…").triggered.connect(self._pick)

    def _pick(self) -> None:
        chosen = QColorDialog.getColor(self.current, self.window(), "Couleur de Friday")
        if chosen.isValid():
            self._choose(chosen)

    def _choose(self, color: QColor) -> None:
        self.current = color
        self.color_chosen.emit(color)

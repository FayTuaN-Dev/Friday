"""Pop-up « Ce que je vois » : la capture d'écran que Friday vient d'analyser."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel

from friday.tools.base import Display
from friday.ui.desktop.popups.base import Popup

WIDTH = 520


class ScreenPopup(Popup):
    def __init__(self, display: Display) -> None:
        super().__init__("👁️", display.title, (WIDTH + 30, 360))
        pixmap = QPixmap()
        pixmap.loadFromData(display.data["image"])
        picture = QLabel(objectName="ImageTile", alignment=Qt.AlignCenter)
        if not pixmap.isNull():
            pixmap = pixmap.scaledToWidth(WIDTH, Qt.SmoothTransformation)
            picture.setPixmap(pixmap)
            self.resize(WIDTH + 30, pixmap.height() + 80)
        self.body.addWidget(picture)

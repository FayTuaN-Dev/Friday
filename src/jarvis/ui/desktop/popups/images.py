"""Pop-up galerie d'images (cliquer sur une image ouvre sa page d'origine)."""

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import QGridLayout, QLabel, QWidget

from jarvis.tools.base import Display
from jarvis.ui.desktop.popups.base import Popup

COLUMNS = 3
THUMB = QSize(180, 140)


class ImageTile(QLabel):
    def __init__(self, pixmap: QPixmap, title: str, url: str) -> None:
        super().__init__(objectName="ImageTile", alignment=Qt.AlignCenter)
        self.setFixedSize(THUMB + QSize(8, 8))
        self.setPixmap(pixmap.scaled(THUMB, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.setToolTip(title)
        self.setCursor(Qt.PointingHandCursor)
        self.url = url

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            QDesktopServices.openUrl(QUrl(self.url))


class ImagesPopup(Popup):
    def __init__(self, display: Display) -> None:
        super().__init__("🖼️", display.title, (COLUMNS * 196 + 26, 400))
        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(6)
        grid.setContentsMargins(0, 0, 0, 0)

        tiles = 0
        for image in display.data["images"]:
            pixmap = QPixmap()
            if not pixmap.loadFromData(image["data"]):
                continue  # format non reconnu
            grid.addWidget(ImageTile(pixmap, image["title"], image["url"]), *divmod(tiles, COLUMNS))
            tiles += 1

        self.body.addWidget(grid_widget)
        self.body.addStretch()
        rows = max(1, -(-tiles // COLUMNS))
        self.resize(self.width(), 60 + rows * (THUMB.height() + 14))

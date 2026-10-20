"""Sous-titres de l'interprète (D2) : un bandeau par-dessus tout, en bas de l'écran où est la
souris (même sur une vidéo en plein écran dans le navigateur). Les clics le traversent. Il
s'efface seul quand plus rien n'est dit."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

HIDE_MS = 7000  # plus de phrase depuis 7 s : le bandeau s'efface
WIDTH = 0.7  # part de la largeur de l'écran
BOTTOM = 90  # pixels au-dessus du bas de l'écran (la barre de lecture reste visible)


class SubtitleBar(QWidget):
    def __init__(self) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)  # fmt: skip
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        box = QWidget(self, objectName="SubtitleBox")
        box.setStyleSheet("#SubtitleBox { background: rgba(0, 0, 0, 170); border-radius: 12px; }"
                          "QLabel { color: white; background: transparent; }")  # fmt: skip
        layout = QVBoxLayout(box)
        layout.setContentsMargins(22, 12, 22, 12)
        self.french = QLabel(wordWrap=True, alignment=Qt.AlignCenter)
        self.french.setStyleSheet("font-size: 24px; font-weight: 600;")
        self.heard = QLabel(wordWrap=True, alignment=Qt.AlignCenter)
        self.heard.setStyleSheet("font-size: 13px; color: rgba(255, 255, 255, 150);")
        layout.addWidget(self.french)
        layout.addWidget(self.heard)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(box)
        self._timer = QTimer(self, singleShot=True, interval=HIDE_MS, timeout=self.hide)

    def show_text(self, french: str, heard: str = "") -> None:
        self.french.setText(french)
        self.heard.setText(heard)
        self.heard.setVisible(bool(heard) and heard != french)
        self._place()
        self.show()
        self.raise_()
        self._timer.start()

    def _place(self) -> None:
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        area = screen.geometry()
        width = int(area.width() * WIDTH)
        self.setFixedWidth(width)
        self.adjustSize()
        self.move(area.x() + (area.width() - width) // 2,
                  area.y() + area.height() - self.height() - BOTTOM)  # fmt: skip

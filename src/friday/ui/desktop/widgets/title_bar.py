"""Barre de titre maison : couleur à gauche, nom au centre, réduire / agrandir / fermer à droite.
On déplace la fenêtre en l'attrapant ; un double-clic l'agrandit ou la restaure."""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from friday.ui.desktop.icons import icon
from friday.ui.desktop.theme import Palette
from friday.ui.desktop.widgets.color_menu import ColorMenu

TITLE = "F.R.I.D.A.Y."


class TitleBar(QWidget):
    def __init__(self, window: QWidget, base: QColor) -> None:
        super().__init__(objectName="TitleBar")
        self._window = window
        self.setFixedHeight(46)
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 8, 10, 0)
        row.setSpacing(2)

        self.color_button = self._button("Couleur de Friday", "TitleButton")
        self.settings_button = self._button("Réglages", "TitleButton")
        self.color_menu = ColorMenu(base, self)
        self.color_button.clicked.connect(self._open_color_menu)
        self.minimize = self._button("Réduire", "TitleButton", window.showMinimized)
        self.maximize = self._button("Agrandir", "TitleButton", self.toggle_maximized)
        self.close_button = self._button("Fermer", "CloseButton", window.close)

        title = QLabel(TITLE, objectName="Title", alignment=Qt.AlignCenter)
        self.title = title
        # Le titre reste centré : même largeur réservée à gauche et à droite
        left = QWidget()
        left_row = QHBoxLayout(left)
        left_row.setContentsMargins(0, 0, 0, 0)
        left_row.addWidget(self.color_button)
        left_row.addWidget(self.settings_button)
        left_row.addStretch()
        right = QWidget()
        right_row = QHBoxLayout(right)
        right_row.setContentsMargins(0, 0, 0, 0)
        right_row.setSpacing(2)
        right_row.addStretch()
        for button in (self.minimize, self.maximize, self.close_button):
            right_row.addWidget(button)
        left.setFixedWidth(100)
        right.setFixedWidth(100)
        row.addWidget(left)
        row.addWidget(title, 1)
        row.addWidget(right)

    def _button(self, tip: str, name: str, slot=None) -> QPushButton:
        button = QPushButton(objectName=name, toolTip=tip)
        button.setIconSize(QSize(15, 15))
        button.setFocusPolicy(Qt.NoFocus)
        button.setFixedSize(28, 28)
        if slot:
            button.clicked.connect(slot)
        return button

    def set_trading(self, on: bool) -> None:
        """Le mode trading se voit : le titre l'annonce tant qu'il est actif."""
        self.title.setText(f"{TITLE} · MODE TRADING" if on else TITLE)

    def refresh(self, palette: Palette) -> None:
        self.color_button.setIcon(icon("palette", palette.accent, 16))
        self.settings_button.setIcon(icon("settings", palette.accent, 16))
        self.minimize.setIcon(icon("minimize", palette.muted, 15))
        self.maximize.setIcon(icon("maximize", palette.muted, 15))
        self.close_button.setIcon(icon("close", palette.muted, 15))

    def _open_color_menu(self) -> None:
        self.color_menu.exec(self.color_button.mapToGlobal(self.color_button.rect().bottomLeft()))

    def toggle_maximized(self) -> None:
        if self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._window.windowHandle().startSystemMove()

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.toggle_maximized()

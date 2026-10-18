"""Barre de titre maison : menu des pages (☰), réglages et mode jeu à gauche, nom au centre,
réduire / agrandir / fermer à droite (la couleur se choisit dans les réglages), et dessous un
trait fin de la couleur d'accent qui s'efface vers les bords.
On déplace la fenêtre en l'attrapant ; un double-clic l'agrandit ou la restaure."""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from friday.ui.desktop.icons import icon
from friday.ui.desktop.theme import Palette

TITLE = "F.R.I.D.A.Y."


class TitleBar(QWidget):
    def __init__(self, window: QWidget, base: QColor) -> None:
        super().__init__(objectName="TitleBar")
        self._window = window
        self._line: QColor | None = None  # le trait sous la barre (refresh)
        self.setFixedHeight(46)
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 8, 10, 0)
        row.setSpacing(2)

        self.menu_button = self._button("Pages : Conversation, Trading", "TitleButton")
        self.settings_button = self._button("Réglages", "TitleButton")
        self.game_button = self._button("Mode jeu : libérer la carte graphique", "TitleButton")
        self.minimize = self._button("Réduire", "TitleButton", window.showMinimized)
        self.maximize = self._button("Agrandir", "TitleButton", self.toggle_maximized)
        self.close_button = self._button("Fermer", "CloseButton", window.close)

        title = QLabel(TITLE, objectName="Title", alignment=Qt.AlignCenter)
        self.title = title
        # Le titre reste centré : même largeur réservée à gauche et à droite
        left = QWidget()
        left_row = QHBoxLayout(left)
        left_row.setContentsMargins(0, 0, 0, 0)
        left_row.setSpacing(2)
        left_row.addWidget(self.menu_button)
        left_row.addWidget(self.settings_button)
        left_row.addWidget(self.game_button)
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
        # Espacement des lettres réduit en mode trading : le titre tient dans sa place.
        self.title.setText(f"{TITLE} · TRADING" if on else TITLE)
        self.title.setProperty("trading", on)
        self.title.style().unpolish(self.title)
        self.title.style().polish(self.title)

    def paintEvent(self, _event) -> None:
        if self._line is None:
            return
        y, width = self.height() - 1, self.width()
        fade = QLinearGradient(width * 0.2, 0, width * 0.8, 0)
        edge = QColor(self._line)
        edge.setAlpha(0)
        fade.setColorAt(0, edge)
        fade.setColorAt(0.5, self._line)
        fade.setColorAt(1, edge)
        QPainter(self).fillRect(int(width * 0.2), y, int(width * 0.6), 1, fade)

    def refresh(self, palette: Palette) -> None:
        self._line = QColor(palette.base)
        self._line.setAlpha(90)
        self.update()
        self.menu_button.setIcon(icon("menu", palette.accent, 16))
        self.settings_button.setIcon(icon("settings", palette.accent, 16))
        self.game_button.setIcon(icon("gamepad", palette.accent, 16))
        self.minimize.setIcon(icon("minimize", palette.muted, 15))
        self.maximize.setIcon(icon("maximize", palette.muted, 15))
        self.close_button.setIcon(icon("close", palette.muted, 15))

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

"""Barre du bas, en pilule : saisie au clavier, micro (maintenir), voix, nouvelle conversation."""

from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QWidget

from friday.ui.desktop.icons import icon
from friday.ui.desktop.theme import Palette


class InputBar(QWidget):
    submitted = Signal(str)
    mic_pressed = Signal()
    mic_released = Signal()
    voice_toggled = Signal()
    reset_clicked = Signal()

    def __init__(self, ptt_key: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("InputBar")
        self.setAttribute(Qt.WA_StyledBackground)
        self.setFixedHeight(52)  # arrondi = moitié de la hauteur : une vraie pilule
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 6, 8, 6)
        layout.setSpacing(2)

        self.edit = QLineEdit(placeholderText=f"Écrire à Friday… ou maintenir « {ptt_key} »")
        self.edit.returnPressed.connect(self._submit)
        self.edit.installEventFilter(self)  # la pilule s'allume pendant la saisie

        self.reset = self._button("Nouvelle conversation", self.reset_clicked)
        self.voice = self._button("Activer / couper la voix", self.voice_toggled)
        self.mic = self._button("Maintenir pour parler", None, "MicButton")
        self.mic.pressed.connect(self.mic_pressed)
        self.mic.released.connect(self.mic_released)
        self.send = self._button("Envoyer", self._submit, "SendButton")

        layout.addWidget(self.edit, 1)
        for button in (self.reset, self.voice, self.mic, self.send):
            layout.addWidget(button)
        self._voice_on = True
        self._palette: Palette | None = None

    def eventFilter(self, watched, event) -> bool:
        if event.type() in (QEvent.FocusIn, QEvent.FocusOut):
            self.setProperty("focused", event.type() == QEvent.FocusIn)
            self.style().unpolish(self)
            self.style().polish(self)
        return False

    def _button(self, tip: str, slot, name: str = "") -> QPushButton:
        button = QPushButton(objectName=name, toolTip=tip)
        button.setIconSize(QSize(19, 19))
        button.setFocusPolicy(Qt.NoFocus)
        if slot is not None:
            button.clicked.connect(slot)
        return button

    def refresh(self, palette: Palette) -> None:
        """Re-colore les icônes (appelé quand la couleur de l'interface change)."""
        self._palette = palette
        self.reset.setIcon(icon("reset", palette.muted))
        self.mic.setIcon(icon("mic", palette.accent))
        self.send.setIcon(icon("send", palette.accent))
        self.set_voice(self._voice_on)

    def set_voice(self, on: bool) -> None:
        self._voice_on = on
        if self._palette is not None:
            name, color = ("volume", self._palette.accent) if on else ("mute", self._palette.muted)
            self.voice.setIcon(icon(name, color))

    def _submit(self) -> None:
        text = self.edit.text().strip()
        if text:
            self.submitted.emit(text)
            self.edit.clear()

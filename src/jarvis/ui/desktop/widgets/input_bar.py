"""Barre du bas : saisie au clavier, bouton micro (maintenir), voix, nouvelle conversation."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QWidget


class InputBar(QWidget):
    submitted = Signal(str)
    mic_pressed = Signal()
    mic_released = Signal()
    voice_toggled = Signal()
    reset_clicked = Signal()

    def __init__(self, ptt_key: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("InputBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 5, 6, 5)
        layout.setSpacing(6)

        self.edit = QLineEdit(placeholderText=f"Écrivez à Jarvis… ou maintenez « {ptt_key} »")
        self.edit.returnPressed.connect(self._submit)

        self.mic = QPushButton("🎙", objectName="MicButton", toolTip="Maintenir pour parler")
        self.mic.pressed.connect(self.mic_pressed)
        self.mic.released.connect(self.mic_released)

        self.voice = QPushButton("🔊", toolTip="Activer / couper la voix", checkable=True)
        self.voice.clicked.connect(self.voice_toggled)

        reset = QPushButton("⟲", toolTip="Nouvelle conversation")
        reset.clicked.connect(self.reset_clicked)

        send = QPushButton("➤", toolTip="Envoyer")
        send.clicked.connect(self._submit)

        layout.addWidget(self.edit, 1)
        for button in (send, self.mic, self.voice, reset):
            layout.addWidget(button)

    def set_voice(self, on: bool) -> None:
        self.voice.setText("🔊" if on else "🔇")
        self.voice.setChecked(not on)

    def _submit(self) -> None:
        text = self.edit.text().strip()
        if text:
            self.submitted.emit(text)
            self.edit.clear()

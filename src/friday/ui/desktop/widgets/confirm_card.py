"""Carte « Je lance ? » dans le chat : [Lancer] / [Annuler] (on peut aussi répondre à la voix)."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class ConfirmCard(QFrame):
    answered = Signal(bool)

    def __init__(self, question: str) -> None:
        super().__init__(objectName="ConfirmCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.addWidget(QLabel(question, objectName="ConfirmQuestion", wordWrap=True))
        layout.addWidget(QLabel("Répondez « oui » / « non », ou :", objectName="Hint"))

        buttons = QHBoxLayout()
        self.yes = QPushButton("Lancer", objectName="ConfirmYes")
        self.no = QPushButton("Annuler", objectName="ConfirmNo")
        self.yes.clicked.connect(lambda: self._answer(True))
        self.no.clicked.connect(lambda: self._answer(False))
        buttons.addStretch()
        buttons.addWidget(self.no)
        buttons.addWidget(self.yes)
        layout.addLayout(buttons)

    def close_card(self) -> None:
        """La question est réglée (réponse, refus ou délai dépassé) : plus de clic possible."""
        self.yes.setEnabled(False)
        self.no.setEnabled(False)

    def _answer(self, approved: bool) -> None:
        self.close_card()
        self.answered.emit(approved)

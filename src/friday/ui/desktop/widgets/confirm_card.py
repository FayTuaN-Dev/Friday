"""Carte « Je lance ? » dans le fil (U4) : la question, [Annuler] et [Lancer] (bouton plein),
et une fine barre qui se vide pendant le temps laissé pour répondre. On peut aussi répondre
« oui » / « non » à la voix ou au clavier ; une fois réglée, la carte dit ce qui s'est passé."""

import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout

TICK_MS = 250


class ConfirmCard(QFrame):
    answered = Signal(bool)

    def __init__(self, question: str, seconds: float = 60.0) -> None:
        super().__init__(objectName="ConfirmCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 12)
        layout.setSpacing(10)
        layout.addWidget(QLabel(question, objectName="ConfirmQuestion", wordWrap=True))

        buttons = QHBoxLayout()
        self.hint = QLabel("ou dites « oui » / « non »", objectName="Hint")
        self.yes = QPushButton("Lancer", objectName="ConfirmYes", cursor=Qt.PointingHandCursor)
        self.no = QPushButton("Annuler", objectName="ConfirmNo", cursor=Qt.PointingHandCursor)
        self.yes.clicked.connect(lambda: self._answer(True))
        self.no.clicked.connect(lambda: self._answer(False))
        buttons.addWidget(self.hint)
        buttons.addStretch()
        buttons.addWidget(self.no)
        buttons.addWidget(self.yes)
        layout.addLayout(buttons)

        self.outcome = QLabel(objectName="ConfirmOutcome")  # « ✓ Lancé », « Annulé »…
        self.outcome.hide()
        layout.addWidget(self.outcome)
        self.bar = QProgressBar(objectName="ConfirmTime", textVisible=False, maximum=1000)
        self.bar.setFixedHeight(3)
        self.bar.setValue(1000)
        layout.addWidget(self.bar)
        self.seconds = max(1.0, seconds)
        self._start = time.monotonic()
        self._timer = QTimer(self, interval=TICK_MS, timeout=self._tick)
        self._timer.start()

    @property
    def closed(self) -> bool:
        return not self.yes.isEnabled()

    def _tick(self) -> None:
        left = 1 - (time.monotonic() - self._start) / self.seconds
        self.bar.setValue(int(1000 * max(0.0, left)))
        if left <= 0:  # le cerveau a renoncé de son côté : la carte le montre
            self.close_card("⏱ Délai dépassé : rien n'a été lancé")

    def close_card(self, outcome: str = "Question close") -> None:
        """La question est réglée (réponse, refus, délai ou fin de réponse) : plus de clic,
        et la carte dit ce qui s'est passé à la place des boutons."""
        if self.closed:
            return
        self._timer.stop()
        for widget in (self.yes, self.no, self.hint, self.bar):
            widget.setEnabled(False)
            widget.hide()
        self.outcome.setText(outcome)
        self.outcome.show()

    def _answer(self, approved: bool) -> None:
        self.close_card("✓ Lancé" if approved else "✗ Annulé")
        self.answered.emit(approved)

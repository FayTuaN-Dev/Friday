"""Pastille d'outil dans le fil (U3) : une roue tourne pendant que l'outil travaille, puis
✓ (ou ✗ s'il a échoué) avec sa durée : « 🔎 Recherche : météo Lyon  ✓ 1,2 s »."""

import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel

SPINNER = "◐◓◑◒"
SPIN_MS = 120


def duration(seconds: float) -> str:
    if seconds < 10:
        return f"{seconds:.1f} s".replace(".", ",")
    if seconds < 60:
        return f"{seconds:.0f} s"
    return f"{seconds // 60:.0f} min {seconds % 60:02.0f}"


class ToolChip(QFrame):
    def __init__(self, label: str) -> None:
        super().__init__(objectName="ToolChip")
        self.setProperty("state", "running")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 5, 12, 5)
        layout.setSpacing(8)
        self.label = QLabel(label, objectName="ToolChipLabel")
        self.mark = QLabel(SPINNER[0], objectName="ToolChipMark")
        self.time = QLabel("", objectName="ToolChipTime")
        layout.addWidget(self.mark)
        layout.addWidget(self.label)
        layout.addWidget(self.time)
        self.running = True
        self._start = time.monotonic()
        self._frame = 0
        self._timer = QTimer(self, interval=SPIN_MS, timeout=self._spin)
        self._timer.start()

    def _spin(self) -> None:
        self._frame = (self._frame + 1) % len(SPINNER)
        self.mark.setText(SPINNER[self._frame])
        elapsed = time.monotonic() - self._start
        if elapsed >= 3:  # au-delà de quelques secondes, le temps qui passe rassure
            self.time.setText(duration(elapsed))

    def finish(self, ok: bool = True, note: str = "") -> None:
        """Fin de l'outil : ✓ ou ✗, la durée (ou une note : « interrompu »)."""
        if not self.running:
            return
        self.running = False
        self._timer.stop()
        self.mark.setText("✓" if ok else "✗")
        self.time.setText(note or duration(time.monotonic() - self._start))
        self.setProperty("state", "ok" if ok else "failed")
        for widget in (self, self.mark, self.time):  # le style suit l'état
            widget.style().unpolish(widget)
            widget.style().polish(widget)


def chip_row(chip: ToolChip) -> QHBoxLayout:
    """Pastilles alignées à gauche, comme les réponses de Friday."""
    row = QHBoxLayout()
    row.addWidget(chip, 0, Qt.AlignLeft)
    row.addStretch()
    return row

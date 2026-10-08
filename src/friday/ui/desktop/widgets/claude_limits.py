"""Les limites Claude à l'écran (fenêtre agrandie) : une barre par fenêtre — session (5 h) et
semaine — avec le pourcentage RESTANT et l'heure de remise à zéro (app/claude_limits.py).
Vert, puis orange sous 50 %, rouge sous 20 %. Relu toutes les 30 s."""

import time

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFrame, QLabel, QProgressBar, QVBoxLayout

from friday.app.claude_limits import read
from friday.claude_status import LIMITS

COLORS = ((50, "#4cc38a"), (20, "#e5a54b"), (0, "#e5636b"))  # (au-dessus de, couleur)
HOW = ("Limites Claude : branchez Claude Code dans Réglages → Diagnostic, puis utilisez-le une "
       "fois.")  # fmt: skip


class ClaudeLimits(QFrame):
    def __init__(self, path=LIMITS, clock=time.time) -> None:
        super().__init__(objectName="ResultCard")
        self.path, self.clock = path, clock
        self.setFixedWidth(280)
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(14, 10, 14, 10)
        self.layout_.addWidget(QLabel("Limites Claude", objectName="SettingsLabel"))
        self.rows: list[tuple[QLabel, QProgressBar, QLabel]] = []
        for _ in range(2):
            title, bar, detail = QLabel(), QProgressBar(maximum=100), QLabel(objectName="Hint")
            bar.setTextVisible(False)
            bar.setFixedHeight(10)
            detail.setWordWrap(True)
            for widget in (title, bar, detail):
                self.layout_.addWidget(widget)
            self.rows.append((title, bar, detail))
        self.note = QLabel(objectName="Hint", wordWrap=True)
        self.layout_.addWidget(self.note)
        self._timer = QTimer(self, interval=30_000)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        self.refresh()

    def refresh(self) -> None:
        now = self.clock()
        limits = read(self.path, now)
        windows = limits.windows if limits else []
        for n, (title, bar, detail) in enumerate(self.rows):
            shown = n < len(windows)
            for widget in (title, bar, detail):
                widget.setVisible(shown)
            if not shown:
                continue
            window = windows[n]
            color = next(c for floor, c in COLORS if window.left >= floor)
            title.setText(f"{window.label} : {window.left:.0f} % restants")
            bar.setValue(round(window.left))
            bar.setStyleSheet(f"QProgressBar::chunk {{ background: {color}; }}")
            detail.setText(window.reset_text(now))
        self.note.setText(HOW if limits is None else limits.age_text(now))
        self.note.setVisible(bool(self.note.text()))

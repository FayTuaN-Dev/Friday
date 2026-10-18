"""Les limites Claude à l'écran (fenêtre agrandie), au style HUD de Friday : pour la session
(5 h) et la semaine, le pourcentage RESTANT en grand, une barre fine lumineuse à la couleur
d'accent du thème (rouge seulement sous 20 %) et l'heure de remise à zéro
(app/claude_limits.py). Relu toutes les 30 s ; suit la couleur choisie."""

import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout

from friday.app.claude_limits import read
from friday.claude_status import LIMITS
from friday.ui.desktop import theme
from friday.ui.desktop.theme.stylesheet import FONT_HUD

LOW = 20  # sous 20 % restants : couleur d'alerte
HOW = "Branchez Claude Code dans Réglages → Diagnostic, puis utilisez-le une fois."


def style(p) -> str:
    """Feuille de style du panneau pour la palette `p` du thème."""
    return f"""
    #Limits {{ background: {p.card}; border: 1px solid {p.card_border or p.accent_glow};
               border-radius: 14px; }}
    #Limits QLabel {{ background: transparent; }}
    #LimitsTitle {{ font-family: "{FONT_HUD}"; font-size: 11px; color: {p.accent};
                    letter-spacing: 4px; }}
    #LimitsName {{ font-family: "{FONT_HUD}"; font-size: 10px; color: {p.muted};
                   letter-spacing: 3px; }}
    #LimitsValue {{ font-family: "{FONT_HUD}"; font-size: 18px; color: {p.accent}; }}
    #LimitsValue[low="true"] {{ color: {p.error}; }}
    #LimitsDetail {{ font-size: 10px; color: {p.muted}; }}
    #LimitsBar {{ background: {p.accent_glow}; border: none; border-radius: 2px; }}
    #LimitsBar::chunk {{ border-radius: 2px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                         stop:0 {p.accent_soft}, stop:1 {p.accent}); }}
    #LimitsBar[low="true"]::chunk {{ background: {p.error}; }}
    """  # fmt: skip


class Row:
    def __init__(self, layout: QVBoxLayout) -> None:
        line = QHBoxLayout()
        self.name = QLabel(objectName="LimitsName")
        self.value = QLabel(objectName="LimitsValue", alignment=Qt.AlignRight | Qt.AlignVCenter)
        line.addWidget(self.name, 1, Qt.AlignBottom)
        line.addWidget(self.value)
        self.bar = QProgressBar(objectName="LimitsBar", maximum=100, textVisible=False)
        self.bar.setFixedHeight(4)
        self.detail = QLabel(objectName="LimitsDetail")
        layout.addLayout(line)
        layout.addWidget(self.bar)
        layout.addWidget(self.detail)
        layout.addSpacing(3)
        self.widgets = (self.name, self.value, self.bar, self.detail)

    def show(self, window, now: float) -> None:
        low = window.left < LOW
        self.name.setText(window.label.split()[0].upper())  # SESSION, SEMAINE
        self.value.setText(f"{window.left:.0f} %")
        self.bar.setValue(round(window.left))
        self.detail.setText(f"restants · {window.reset_text(now)}" if window.resets_at
                            else "restants")  # fmt: skip
        for widget in (self.value, self.bar):
            widget.setProperty("low", low)
            widget.style().unpolish(widget)
            widget.style().polish(widget)


class ClaudeLimits(QFrame):
    def __init__(self, path=LIMITS, clock=time.time) -> None:
        super().__init__(objectName="Limits")
        self.path, self.clock = path, clock
        self.setFixedWidth(250)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 8)
        layout.setSpacing(2)
        layout.addWidget(QLabel("CLAUDE", objectName="LimitsTitle"))
        layout.addSpacing(4)
        self.rows = [Row(layout), Row(layout)]
        self.note = QLabel(objectName="LimitsDetail", wordWrap=True)
        layout.addWidget(self.note)
        self._timer = QTimer(self, interval=30_000)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        self.refresh()

    def refresh(self) -> None:
        now = self.clock()
        limits = read(self.path, now)
        windows = limits.windows if limits else []
        css = style(theme.current())  # suit la couleur choisie (reposée : tout se redessine)
        if self.styleSheet() != css:
            self.setStyleSheet(css)
        for n, row in enumerate(self.rows):
            for widget in row.widgets:
                widget.setVisible(n < len(windows))
            if n < len(windows):
                row.show(windows[n], now)
        self.note.setText(HOW if limits is None else limits.age_text(now))
        self.note.setVisible(bool(self.note.text()))

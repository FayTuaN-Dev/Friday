"""Séquence de démarrage (J4) : en surimpression sur la sphère, l'auto-test défile ligne par
ligne en deux colonnes (« OLLAMA   OK »), puis « FRIDAY EN LIGNE » et tout s'efface. Ce qui
ne va pas reste affiché plus longtemps (app/boot_check.py)."""

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel

from friday.app.diagnostic import BAD, OK
from friday.ui.desktop import theme
from friday.ui.desktop.theme.stylesheet import FONT_HUD

STEP_MS = 140  # une ligne toutes les 140 ms
SHOWN_MS = 2500  # puis tout reste affiché…
TROUBLE_MS = 12000  # … plus longtemps si quelque chose ne va pas
WARN_COLOR = "#f0a83c"  # orange : « À VOIR »


def row(topic: str, state: str) -> tuple[str, str, str]:
    """(rubrique, verdict, couleur du verdict) : (« MICRO », « OK », accent)."""
    p = theme.current()
    word, color = {OK: ("OK", p.accent), BAD: ("ÉCHEC", p.error)}.get(state, ("À VOIR", WARN_COLOR))
    return topic.upper(), word, color


class BootLog(QLabel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setTextFormat(Qt.RichText)
        self.setAlignment(Qt.AlignLeft | Qt.AlignBottom)
        self._rows: list[tuple[str, str, str]] = []
        self._shown = 0
        self._effect = QGraphicsOpacityEffect(self, opacity=1.0)
        self.setGraphicsEffect(self._effect)
        self._fade = QPropertyAnimation(self._effect, b"opacity", self, duration=900,
                                        easingCurve=QEasingCurve.InOutQuad)  # fmt: skip
        self._fade.finished.connect(self.hide)
        self._timer = QTimer(self, interval=STEP_MS, timeout=self._step)
        self.hide()

    def start(self, lines) -> None:
        """`lines` : (rubrique, état, détail) de l'auto-test."""
        self._rows = [row(topic, state) for topic, state, _ in lines]
        self._rows.append(("FRIDAY EN LIGNE", "", theme.current().accent))
        self._trouble = any(state != OK for _, state, _ in lines)
        self._shown = 0
        self._effect.setOpacity(1.0)
        self.show()
        self._timer.start()

    def _step(self) -> None:
        self._shown += 1
        self._render()
        if self._shown >= len(self._rows):
            self._timer.stop()
            QTimer.singleShot(TROUBLE_MS if self._trouble else SHOWN_MS, self._fade_out)

    def _render(self) -> None:
        name_color = theme.current().muted
        cells = [f'<tr><td style="color:{name_color if word else color}; padding-right:18px">'
                 f'{name}</td><td style="color:{color}">{word}</td></tr>'
                 for name, word, color in self._rows[: self._shown]]  # fmt: skip
        css = f"font-family:'{FONT_HUD}'; font-size:10px; letter-spacing:2px"
        self.setText(f'<table style="{css}" cellspacing="0" cellpadding="2">{"".join(cells)}'
                     "</table>")  # fmt: skip

    def _fade_out(self) -> None:
        self._fade.setStartValue(1.0)
        self._fade.setEndValue(0.0)
        self._fade.start()

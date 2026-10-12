"""U7 : les réglages dans la fenêtre de Friday, plus dans une fenêtre à part. Un panneau
glisse depuis la droite (0,25 s) ; derrière, la conversation s'assombrit. On le ferme avec
✕, Échap ou un clic à côté. Fenêtre étroite : il prend toute la largeur."""

from PySide6.QtCore import QEasingCurve, QRect, QVariantAnimation
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from friday.ui.desktop import theme

PANEL_WIDTH = 820  # au plus ; moins si la fenêtre est étroite
FULL_BELOW = 700  # fenêtre plus étroite : le panneau prend toute la largeur
SLIDE_MS = 250
SCRIM = 170  # opacité du voile derrière le panneau


class SettingsOverlay(QWidget):
    def __init__(self, parent: QWidget, panel: QWidget) -> None:
        super().__init__(parent)
        self.panel = panel
        panel.setParent(self)
        self.progress = 0.0  # 0 : fermé, 1 : ouvert
        self._closing = False
        self._animation = QVariantAnimation(self, duration=SLIDE_MS,
                                            easingCurve=QEasingCurve.OutCubic)  # fmt: skip
        self._animation.valueChanged.connect(self._step)
        self._animation.finished.connect(self._finished)
        self.hide()

    @property
    def showing(self) -> bool:
        return not self.isHidden() and not self._closing

    def open(self, area: QRect) -> None:
        self.setGeometry(area)
        self._closing = False
        self.show()
        self.raise_()
        self.panel.show()
        self._run(1.0)

    def dismiss(self) -> None:
        """Le panneau repart vers la droite, puis tout est caché (gardé pour la suite)."""
        if self._closing:
            return
        self._closing = True
        self._run(0.0)

    def _run(self, end: float) -> None:
        self._animation.stop()
        self._animation.setStartValue(self.progress)
        self._animation.setEndValue(end)
        self._animation.start()

    def _step(self, value: float) -> None:
        self.progress = float(value)
        self._place()
        self.update()

    def _finished(self) -> None:
        if self._closing:
            self.hide()

    def _place(self) -> None:
        width = self.width() if self.width() < FULL_BELOW else min(PANEL_WIDTH, self.width() - 24)
        x = self.width() - width + int((1 - self.progress) * (width + 24))
        self.panel.setGeometry(x, 0, width, self.height())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._place()

    def paintEvent(self, _event) -> None:
        color = QColor(theme.current().bg)
        color.setAlpha(int(SCRIM * self.progress))
        painter = QPainter(self)
        painter.fillRect(self.rect(), color)
        painter.end()

    def mousePressEvent(self, event) -> None:
        if not self.panel.geometry().contains(event.position().toPoint()):
            self.dismiss()  # un clic à côté du panneau le ferme

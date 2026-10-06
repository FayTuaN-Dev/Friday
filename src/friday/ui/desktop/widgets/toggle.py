"""Interrupteur arrondi (on / off), aux couleurs du thème."""

from PySide6.QtCore import Property, QPropertyAnimation, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QAbstractButton

from friday.ui.desktop import theme


class Toggle(QAbstractButton):
    def __init__(self, checked: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.PointingHandCursor)
        self._offset = 1.0 if checked else 0.0
        self._slide = QPropertyAnimation(self, b"offset", self, duration=140)
        self.toggled.connect(self._animate)

    def sizeHint(self) -> QSize:
        return QSize(42, 24)

    def _animate(self, checked: bool) -> None:
        self._slide.setEndValue(1.0 if checked else 0.0)
        self._slide.start()

    def _get_offset(self) -> float:
        return self._offset

    def _set_offset(self, value: float) -> None:
        self._offset = value
        self.update()

    offset = Property(float, _get_offset, _set_offset)

    def paintEvent(self, _event) -> None:
        palette = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        track = QColor(palette.accent if self.isChecked() else palette.muted)
        track.setAlpha(230 if self.isChecked() else 90)
        if not self.isEnabled():
            track.setAlpha(50)
        rect = QRectF(1, 2, self.width() - 2, self.height() - 4)
        painter.setPen(Qt.NoPen)
        painter.setBrush(track)
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        knob = rect.height() - 6
        x = rect.left() + 3 + self._offset * (rect.width() - knob - 6)
        painter.setBrush(QColor(palette.bg if self.isChecked() else palette.text))
        painter.drawEllipse(QRectF(x, rect.top() + 3, knob, knob))
        painter.end()

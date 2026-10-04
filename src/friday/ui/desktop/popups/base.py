"""Fenêtre pop-up de base : sans bordure Windows, en-tête déplaçable, apparition en fondu."""

from PySide6.QtCore import QPoint, QPropertyAnimation, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class ElidedLabel(QLabel):
    """Libellé sur une ligne, tronqué avec « … » s'il est trop long (n'élargit pas la fenêtre)."""

    def __init__(self, text: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.full_text = text
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        metrics = self.fontMetrics()
        self.setText(metrics.elidedText(self.full_text, Qt.ElideRight, self.width()))


class Popup(QWidget):
    closed = Signal(object)

    def __init__(self, icon: str, title: str, size: tuple[int, int]) -> None:
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint)
        self.setObjectName("Popup")
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setAttribute(Qt.WA_StyledBackground)
        self.resize(*size)
        self._drag_from: QPoint | None = None

        header = QWidget(objectName="PopupHeader")
        row = QHBoxLayout(header)
        row.setContentsMargins(12, 6, 6, 6)
        title_label = ElidedLabel(f"{icon}  {title}", objectName="PopupTitle")
        title_label.setToolTip(title)
        close = QPushButton("✕", objectName="PopupClose", toolTip="Fermer")
        close.clicked.connect(self.close)
        row.addWidget(title_label, 1)
        row.addWidget(close)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        layout.addWidget(header)
        self.body = QVBoxLayout()
        self.body.setContentsMargins(12, 10, 12, 12)
        layout.addLayout(self.body, 1)

    def show_animated(self) -> None:
        self.setWindowOpacity(0.0)
        self.show()
        self._fade = QPropertyAnimation(self, b"windowOpacity", self, duration=250)
        self._fade.setEndValue(0.97)
        self._fade.start()

    # Déplacement en attrapant la fenêtre (elle n'a pas de barre de titre Windows)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_from = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_from is not None:
            self.move(event.globalPosition().toPoint() - self._drag_from)

    def mouseReleaseEvent(self, _event) -> None:
        self._drag_from = None

    def closeEvent(self, event) -> None:
        self.closed.emit(self)
        super().closeEvent(event)

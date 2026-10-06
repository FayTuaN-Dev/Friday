"""Choisir la zone du graphique : la fenêtre TradingView est capturée, l'utilisateur trace un
rectangle à la souris. Seule cette zone partira ensuite (après aperçu)."""

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRubberBand,
    QVBoxLayout,
    QWidget,
)

from friday.trading.capture import CaptureUnavailable, Zone, load_zone, save_zone

MAX_SIZE = QSize(860, 520)


class _Canvas(QLabel):
    """L'image de la fenêtre, sur laquelle on trace la zone."""

    traced = Signal()

    def __init__(self, pixmap: QPixmap) -> None:
        super().__init__()
        self.setPixmap(pixmap)
        self.setFixedSize(pixmap.size())
        self.setCursor(Qt.CrossCursor)
        self.band = QRubberBand(QRubberBand.Rectangle, self)
        self._origin = QPoint()

    def mousePressEvent(self, event) -> None:
        self._origin = event.position().toPoint()
        self.band.setGeometry(QRect(self._origin, QSize()))
        self.band.show()

    def mouseMoveEvent(self, event) -> None:
        self.band.setGeometry(QRect(self._origin, event.position().toPoint()).normalized())

    def mouseReleaseEvent(self, event) -> None:
        self.traced.emit()

    def zone(self) -> Zone | None:
        rect = self.band.geometry().intersected(self.rect())
        if rect.width() < 20 or rect.height() < 20:  # rien de tracé (ou un simple clic)
            return None
        w, h = self.width(), self.height()
        return Zone(rect.left() / w, rect.top() / h, (rect.right() + 1) / w,
                    (rect.bottom() + 1) / h)  # fmt: skip


class ZonePicker(QDialog):
    def __init__(self, image, zone_path, parent=None) -> None:
        """`image` : PIL de toute la fenêtre du graphique."""
        super().__init__(parent)
        self.setWindowTitle("Zone du graphique")
        self.zone_path = zone_path
        data = image.convert("RGB").tobytes()
        qimage = QImage(data, image.width, image.height, image.width * 3, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimage.copy()).scaled(MAX_SIZE, Qt.KeepAspectRatio,
                                                         Qt.SmoothTransformation)  # fmt: skip
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Tracez à la souris le rectangle du graphique. Seule cette zone sera envoyée "
            "(toujours après aperçu) : laissez dehors le solde, les positions et les comptes.",
            wordWrap=True))  # fmt: skip
        self.canvas = _Canvas(pixmap)
        layout.addWidget(self.canvas, 0, Qt.AlignCenter)
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Annuler", objectName="SettingsSmall")
        self.save_button = QPushButton("Enregistrer la zone", objectName="SettingsPrimary")
        self.save_button.setEnabled(False)
        self.canvas.traced.connect(
            lambda: self.save_button.setEnabled(self.canvas.zone() is not None)
        )
        cancel.clicked.connect(self.reject)
        self.save_button.clicked.connect(self._save)
        buttons.addWidget(cancel)
        buttons.addWidget(self.save_button)
        layout.addLayout(buttons)

    def _save(self) -> None:
        zone = self.canvas.zone()
        if zone is not None:
            save_zone(self.zone_path, zone)
            self.accept()


def describe(zone: Zone) -> str:
    if zone == Zone():
        return "Toute la fenêtre TradingView."
    return (f"Zone choisie : {zone.right - zone.left:.0%} de la largeur et "
            f"{zone.bottom - zone.top:.0%} de la hauteur de la fenêtre.")  # fmt: skip


class ChartZoneRow(QFrame):
    """Ligne des réglages Trading : la zone actuelle, « Choisir la zone… », « Toute la fenêtre »."""

    def __init__(self, capture) -> None:
        super().__init__(objectName="SettingsRow")
        self.capture = capture
        line = QHBoxLayout(self)
        line.setContentsMargins(14, 10, 14, 10)
        texts = QVBoxLayout()
        texts.addWidget(QLabel("Zone du graphique envoyée", objectName="SettingsLabel"))
        self.status = QLabel(objectName="Hint", wordWrap=True)
        texts.addWidget(self.status)
        line.addLayout(texts, 1)
        pick = QPushButton("Choisir la zone…", objectName="SettingsSmall")
        reset = QPushButton("Toute la fenêtre", objectName="SettingsSmall")
        pick.clicked.connect(self._pick)
        reset.clicked.connect(self._reset)
        for button in (pick, reset):
            button.setEnabled(capture is not None)
            line.addWidget(button)
        self.refresh()

    def refresh(self, message: str = "") -> None:
        if self.capture is None:
            self.status.setText("Mode trading désactivé.")
            return
        self.status.setText(message or describe(load_zone(self.capture.zone_path)))

    def _pick(self) -> None:
        try:
            image = self.capture.full_window()
        except CaptureUnavailable as error:
            self.refresh(str(error))
            return
        if ZonePicker(image, self.capture.zone_path, self.window()).exec():
            self.refresh()

    def _reset(self) -> None:
        save_zone(self.capture.zone_path, Zone())
        self.refresh()


def chart_zone_widget(capture) -> QWidget:
    return ChartZoneRow(capture)

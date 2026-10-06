"""Pop-up de base : sans bordure Windows, arrondi, en-tête déplaçable, apparition en fondu."""

from PySide6.QtCore import QPoint, QPropertyAnimation, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizeGrip,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from friday.ui.desktop import theme
from friday.ui.desktop.icons import icon


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

    def __init__(self, symbol: str, title: str, size: tuple[int, int]) -> None:
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint)
        self.setObjectName("Popup")
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.key = ""  # identité de la liste affichée (mises à jour sur place)
        self.setAttribute(Qt.WA_TranslucentBackground)  # coins arrondis
        self.resize(*size)
        self.setMinimumSize(300, 200)
        self._drag_from: QPoint | None = None

        header = QWidget(objectName="PopupHeader")
        row = QHBoxLayout(header)
        row.setContentsMargins(16, 10, 10, 4)
        title_label = ElidedLabel(f"{symbol}  {title}", objectName="PopupTitle")
        title_label.setToolTip(title)
        close = QPushButton(objectName="PopupClose", toolTip="Fermer")
        close.setIcon(icon("close", theme.current().muted, 13))
        close.setIconSize(QSize(13, 13))
        close.setFocusPolicy(Qt.NoFocus)
        close.clicked.connect(self.close)
        row.addWidget(title_label, 1)
        row.addWidget(close)

        shell = QWidget(objectName="PopupShell")
        shell.setAttribute(Qt.WA_StyledBackground)
        QVBoxLayout(self).setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(shell)
        layout = QVBoxLayout(shell)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)
        self.body = QVBoxLayout()
        self.body.setContentsMargins(14, 8, 14, 4)
        layout.addLayout(self.body, 1)
        # Poignée du coin bas-droit : la fenêtre s'agrandit (elle n'a pas de bord Windows)
        corner = QHBoxLayout()
        corner.setContentsMargins(0, 0, 4, 4)
        corner.addStretch()
        grip = QSizeGrip(self)
        grip.setToolTip("Agrandir")
        corner.addWidget(grip, 0, Qt.AlignBottom | Qt.AlignRight)
        layout.addLayout(corner)

    def fit_height(self, content: QWidget, extra: int = 150, screen_share: float = 0.9) -> None:
        """Hauteur ajustée au contenu, au plus `screen_share` de l'écran (puis défilement)."""
        screen = self.screen().availableGeometry() if self.screen() else None
        limit = int(screen.height() * screen_share) if screen else 900
        wanted = content.sizeHint().height() + extra
        self.resize(self.width(), max(self.minimumHeight(), min(wanted, limit)))

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

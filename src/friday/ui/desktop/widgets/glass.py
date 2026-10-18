"""Le fond de la fenêtre : le noir teinté du thème, une lueur douce de la couleur d'accent
derrière la sphère, et les bords qui s'assombrissent un peu (vignette), pour que les cartes
de côté, en verre sombre, se détachent. Dessiné une fois par taille, puis gardé en image ;
sous tout le reste (même sous les scènes), la souris passe au travers."""

from PySide6.QtCore import QEvent, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap, QRadialGradient
from PySide6.QtWidgets import QWidget

from friday.ui.desktop import theme

RADIUS = 22  # coins de la fenêtre (#Shell)


def paint_glass(painter: QPainter, width: int, height: int, radius: float = RADIUS) -> None:
    p = theme.current()
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, width, height), radius, radius)
    painter.setClipPath(path)
    painter.fillRect(0, 0, width, height, QColor(p.bg))
    glow = QRadialGradient(width / 2, height * 0.3, max(width, height) * 0.5)
    tint = QColor(p.base)
    for at, alpha in ((0, 34), (0.45, 12), (1, 0)):
        tint.setAlpha(alpha)
        glow.setColorAt(at, tint)
    painter.fillRect(0, 0, width, height, glow)
    shade = QRadialGradient(width / 2, height / 2, max(width, height) * 0.75)
    shade.setColorAt(0.55, QColor(0, 0, 0, 0))
    shade.setColorAt(1, QColor(0, 0, 0, 110))
    painter.fillRect(0, 0, width, height, shade)


class GlassBackdrop(QWidget):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._image: QPixmap | None = None
        self._key = None
        parent.installEventFilter(self)  # toujours à la taille de la fenêtre
        self.setGeometry(parent.rect())

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Resize:
            self.setGeometry(watched.rect())
            self.lower()
        return False

    def refresh(self) -> None:
        """Couleur changée : redessiner."""
        self._image = None
        self.update()

    def paintEvent(self, _event) -> None:
        native = self.parent().property("native") is True  # agrandie : sans coins arrondis
        key = (self.width(), self.height(), theme.current().accent, native)
        if self._image is None or self._key != key:
            self._key = key
            self._image = QPixmap(self.size())
            self._image.fill(Qt.transparent)
            painter = QPainter(self._image)
            painter.setRenderHint(QPainter.Antialiasing)
            paint_glass(painter, self.width(), self.height(), 0 if native else RADIUS)
            painter.end()
        QPainter(self).drawPixmap(0, 0, self._image)

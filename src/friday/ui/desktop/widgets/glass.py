"""Le fond de l'ambiance « verre » (claire) : un dégradé gris-bleu très clair, une lueur douce
de la couleur d'accent derrière la sphère, et de chaque côté une pile de plaques de verre
translucides en perspective, bord supérieur lumineux (d'après la maquette choisie par
l'utilisateur). Caché en ambiance sombre. Dessiné une fois par taille, puis gardé en image ;
sous tout le reste (même sous les scènes), la souris passe au travers.

`pool()` : sous la sphère, une flaque sombre — sa lumière s'ajoute (mode additif) et ne se
verrait pas sur un fond clair."""

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget

from friday.ui.desktop import theme

RADIUS = 22  # coins de la fenêtre (#Shell)
PLATES = 5  # plaques par pile


def pool(painter: QPainter, cx: float, cy: float, size: float, room: float) -> None:
    """La flaque sombre sous la sphère, en ambiance verre seulement ; `room` : le rayon
    disponible dans le widget (au-delà, la flaque serait coupée net)."""
    if not theme.current().light:
        return
    radius = min(size * 1.3, room)
    shade = QRadialGradient(cx, cy, radius)
    shade.setColorAt(0, QColor(14, 22, 34, 225))
    shade.setColorAt(0.6, QColor(14, 22, 34, 120))
    shade.setColorAt(1, QColor(14, 22, 34, 0))
    painter.save()
    painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
    painter.setPen(Qt.NoPen)
    painter.setBrush(shade)
    painter.drawEllipse(QPointF(cx, cy), radius, radius)
    painter.restore()


def _plate(x: float, y: float, w: float, depth: float, lean: float) -> QPolygonF:
    """Une plaque vue de biais : le bord du fond plus court, décalé de `lean`."""
    back = w * 0.78
    return QPolygonF([QPointF(x, y + depth), QPointF(x + w, y + depth),
                      QPointF(x + (w + back) / 2 + lean, y),
                      QPointF(x + (w - back) / 2 + lean, y)])  # fmt: skip


def paint_glass(painter: QPainter, width: int, height: int) -> None:
    p = theme.current()
    accent = QColor(p.accent)
    sky = QLinearGradient(0, 0, 0, height)
    sky.setColorAt(0, QColor(p.bg).lighter(106))
    sky.setColorAt(1, QColor(p.bg).darker(108))
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, width, height), RADIUS, RADIUS)
    painter.setClipPath(path)
    painter.fillRect(0, 0, width, height, sky)
    glow = QRadialGradient(width / 2, height * 0.3, max(width, height) * 0.45)
    tint = QColor(accent)
    tint.setAlpha(46)
    glow.setColorAt(0, tint)
    glow.setColorAt(1, QColor(tint.red(), tint.green(), tint.blue(), 0))
    painter.fillRect(0, 0, width, height, glow)
    # Les piles encadrent la sphère, entre les colonnes de cartes (bords) et le centre
    plate_w, depth = max(140.0, width * 0.13), max(22.0, height * 0.04)
    gap = height * 0.085
    for side in (-1, 1):
        x = width * 0.22 if side < 0 else width * 0.78 - plate_w
        for n in range(PLATES):
            y = height * 0.1 + n * gap
            shape = _plate(x, y, plate_w, depth, side * -plate_w * 0.06)
            fill = QLinearGradient(0, y, 0, y + depth)
            fill.setColorAt(0, QColor(255, 255, 255, 120))
            fill.setColorAt(1, QColor(255, 255, 255, 40))
            painter.setPen(QPen(QColor(255, 255, 255, 210), 1.2))
            painter.setBrush(fill)
            painter.drawPolygon(shape)
            edge = QColor(accent)
            edge.setAlpha(70 - n * 10)
            painter.setPen(QPen(edge, 1.0))
            painter.drawLine(shape[0], shape[1])  # le bord avant prend la couleur, discrète


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
        """Ambiance ou couleur changée : redessiner (et se montrer ou se cacher)."""
        self._image = None
        self.setVisible(theme.current().light)
        self.update()

    def paintEvent(self, _event) -> None:
        key = (self.width(), self.height(), theme.current().accent, theme.current().bg)
        if self._image is None or self._key != key:
            self._key = key
            self._image = QPixmap(self.size())
            self._image.fill(Qt.transparent)
            painter = QPainter(self._image)
            painter.setRenderHint(QPainter.Antialiasing)
            paint_glass(painter, self.width(), self.height())
            painter.end()
        QPainter(self).drawPixmap(0, 0, self._image)

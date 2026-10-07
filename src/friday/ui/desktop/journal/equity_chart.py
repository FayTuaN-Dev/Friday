"""Courbe des résultats du journal : le total en R après chaque trade clôturé (une seule série,
un seul axe, en partant de 0). Trait de 2 px à la couleur du thème, point final cerclé et sa
valeur, quadrillage en filets discrets, ligne du zéro ; au survol, un viseur et le détail du
trade le plus proche. Le tableau du journal en est l'équivalent lisible sans le graphique."""

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QToolTip, QWidget

from friday.ui.desktop import theme

MARGIN_LEFT, MARGIN_RIGHT, MARGIN_TOP, MARGIN_BOTTOM = 46, 64, 14, 26
Point = tuple[int, str, float, float]  # (n°, instrument, résultat, cumul)


def nice_ticks(low: float, high: float, count: int = 4) -> list[float]:
    """Graduations rondes (…, -1, 0, 1, 2…) couvrant [low, high], zéro compris."""
    low, high = min(low, 0.0), max(high, 0.0)
    if high - low < 1e-9:
        high = low + 1
    raw = (high - low) / count
    magnitude = 10 ** math.floor(math.log10(raw))
    step = next(m * magnitude for m in (1, 2, 2.5, 5, 10) if m * magnitude >= raw)
    value, ticks = math.floor(low / step) * step, []
    while True:  # jusqu'à couvrir le plus haut (sinon la courbe sortirait par le haut)
        ticks.append(round(value, 6))
        if value >= high - 1e-9:
            return ticks
        value += step


def fr(value: float, sign: bool = False) -> str:
    text = f"{value:+.2f}" if sign else f"{value:g}"
    return text.replace(".", ",")


class EquityChart(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.points: list[Point] = []
        self.setMouseTracking(True)
        self.setMinimumHeight(170)
        self._hover: int | None = None  # indice du point survolé

    def set_points(self, points: list[Point]) -> None:
        self.points = list(points)
        self._hover = None
        self.update()

    # --- géométrie ---------------------------------------------------------------------------

    def _plot(self) -> QRectF:
        return QRectF(MARGIN_LEFT, MARGIN_TOP, max(1, self.width() - MARGIN_LEFT - MARGIN_RIGHT),
                      max(1, self.height() - MARGIN_TOP - MARGIN_BOTTOM))  # fmt: skip

    def _scale(self) -> tuple[list[float], float, float]:
        values = [0.0] + [p[3] for p in self.points]
        ticks = nice_ticks(min(values), max(values))
        return ticks, ticks[0], ticks[-1]

    def _xy(self, index: int, value: float, low: float, high: float) -> QPointF:
        """Indice 0 = le départ (0 R) ; puis un trade clôturé par pas."""
        plot = self._plot()
        steps = max(1, len(self.points))
        x = plot.left() + plot.width() * index / steps
        y = plot.bottom() - plot.height() * (value - low) / (high - low)
        return QPointF(x, y)

    # --- dessin -------------------------------------------------------------------------------

    def paintEvent(self, _event) -> None:
        p = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if not self.points:
            painter.setPen(QColor(p.muted))
            painter.drawText(self.rect(), Qt.AlignCenter,
                             "La courbe apparaîtra après le premier trade clôturé.")  # fmt: skip
            return
        ticks, low, high = self._scale()
        plot = self._plot()
        grid = QPen(QColor(p.surface_hi), 1)
        for tick in ticks:  # quadrillage : filets pleins, discrets ; graduations rondes
            y = self._xy(0, tick, low, high).y()
            painter.setPen(QPen(QColor(p.muted), 1) if tick == 0 else grid)  # le zéro ressort
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            painter.setPen(QColor(p.muted))
            painter.drawText(QRectF(0, y - 9, MARGIN_LEFT - 8, 18), Qt.AlignRight | Qt.AlignVCenter,
                             f"{fr(tick)} R")  # fmt: skip
        painter.drawText(QRectF(plot.left(), plot.bottom() + 6, plot.width(), 18), Qt.AlignLeft,
                         "départ")  # fmt: skip
        painter.drawText(QRectF(plot.left(), plot.bottom() + 6, plot.width(), 18), Qt.AlignRight,
                         f"trade n°{self.points[-1][0]}")  # fmt: skip
        accent = QColor(p.accent)
        path = QPainterPath(self._xy(0, 0.0, low, high))
        for i, point in enumerate(self.points, 1):
            path.lineTo(self._xy(i, point[3], low, high))
        pen = QPen(accent, 2)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.drawPath(path)
        self._dot(painter, len(self.points), low, high, accent, QColor(p.surface))
        end = self._xy(len(self.points), self.points[-1][3], low, high)
        painter.setPen(QColor(p.text))  # la valeur en couleur de texte, jamais de la série
        label = f"{fr(self.points[-1][3], True)} R"
        painter.drawText(QRectF(end.x() + 10, end.y() - 10, MARGIN_RIGHT - 12, 20),
                         Qt.AlignLeft | Qt.AlignVCenter, label)  # fmt: skip
        if self._hover is not None:
            spot = self._xy(self._hover, self.points[self._hover - 1][3], low, high)
            painter.setPen(QPen(QColor(p.muted), 1))  # viseur
            painter.drawLine(QPointF(spot.x(), plot.top()), QPointF(spot.x(), plot.bottom()))
            self._dot(painter, self._hover, low, high, accent, QColor(p.surface))
        painter.end()

    def _dot(self, painter, index, low, high, color, ring) -> None:
        """Point de 8 px cerclé de 2 px de la couleur du fond (lisible sur la ligne)."""
        center = self._xy(index, self.points[index - 1][3], low, high)
        painter.setPen(QPen(ring, 2))
        painter.setBrush(color)
        painter.drawEllipse(center, 5, 5)
        painter.setBrush(Qt.NoBrush)

    # --- survol -------------------------------------------------------------------------------

    def mouseMoveEvent(self, event) -> None:
        if not self.points:
            return
        plot = self._plot()
        steps = len(self.points)
        index = round((event.position().x() - plot.left()) / plot.width() * steps)
        index = min(max(index, 1), steps)  # le trade le plus proche (la cible : toute la zone)
        if index != self._hover:
            self._hover = index
            self.update()
        number, pair, result, total = self.points[index - 1]
        QToolTip.showText(event.globalPosition().toPoint(),
                          f"Trade n°{number} · {pair} · {fr(result, True)} R · cumul "
                          f"{fr(total, True)} R", self)  # fmt: skip

    def leaveEvent(self, _event) -> None:
        self._hover = None
        QToolTip.hideText()
        self.update()

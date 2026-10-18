"""Courbes du bilan des setups (onglet « Setups ») : le total en R au fil des setups terminés,
pour tous les setups, ceux où Claude a dit OUI et ceux où il a dit NON, sur le même axe. Si la
courbe OUI monte plus vite que « tous », l'avis de Claude aide. Même dessin que la courbe du
journal (equity_chart.py) : légende en haut, valeur au bout de chaque courbe, viseur au survol."""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QToolTip, QWidget

from friday.trading.alerts.review import CURVES
from friday.trading.instruments import by_symbol
from friday.ui.desktop import theme
from friday.ui.desktop.journal.equity_chart import fr, nice_ticks
from friday.ui.desktop.journal.window import GAIN, LOSS

LEFT, RIGHT, TOP, BOTTOM = 46, 70, 30, 26
NAMES = ("Tous", "OUI de Claude", "NON de Claude")


class ReviewCurves(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.points: list[tuple[dict, list[float]]] = []  # review.curves()
        self.setMouseTracking(True)
        self.setMinimumHeight(190)
        self._hover: int | None = None

    def set_points(self, points) -> None:
        self.points = list(points)
        self._hover = None
        self.update()

    def colors(self) -> list[QColor]:
        return [QColor(theme.current().accent), GAIN, LOSS]

    def _plot(self) -> QRectF:
        return QRectF(LEFT, TOP, max(1, self.width() - LEFT - RIGHT),
                      max(1, self.height() - TOP - BOTTOM))  # fmt: skip

    def _xy(self, index: int, value: float, low: float, high: float) -> QPointF:
        plot = self._plot()
        x = plot.left() + plot.width() * index / max(1, len(self.points))
        return QPointF(x, plot.bottom() - plot.height() * (value - low) / (high - low))

    def paintEvent(self, _event) -> None:
        p = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if not self.points:
            painter.setPen(QColor(p.muted))
            empty = "Les courbes apparaîtront après le premier setup terminé."
            painter.drawText(self.rect(), Qt.AlignCenter, empty)
            return
        values = [0.0] + [v for _, totals in self.points for v in totals]
        ticks = nice_ticks(min(values), max(values))
        low, high = ticks[0], ticks[-1]
        plot = self._plot()
        for tick in ticks:
            y = self._xy(0, tick, low, high).y()
            painter.setPen(QPen(QColor(p.muted if tick == 0 else p.surface_hi), 1))
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            painter.setPen(QColor(p.muted))
            painter.drawText(QRectF(0, y - 9, LEFT - 8, 18), Qt.AlignRight | Qt.AlignVCenter,
                             f"{fr(tick)} R")  # fmt: skip
        painter.drawText(QRectF(plot.left(), plot.bottom() + 6, plot.width(), 18), Qt.AlignLeft,
                         "départ")  # fmt: skip
        painter.drawText(QRectF(plot.left(), plot.bottom() + 6, plot.width(), 18), Qt.AlignRight,
                         f"{len(self.points)} setups terminés")  # fmt: skip
        self._legend(painter)
        ends = []
        for k, color in enumerate(self.colors()):
            path = QPainterPath(self._xy(0, 0.0, low, high))
            for i, (_, totals) in enumerate(self.points, 1):
                path.lineTo(self._xy(i, totals[k], low, high))
            pen = QPen(color, 2.5 if k == 0 else 2)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawPath(path)
            ends.append((self._xy(len(self.points), self.points[-1][1][k], low, high).y(), k))
        self._end_labels(painter, ends)
        if self._hover is not None:
            x = self._xy(self._hover, 0.0, low, high).x()
            painter.setPen(QPen(QColor(p.muted), 1))
            painter.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
        painter.end()

    def _legend(self, painter: QPainter) -> None:
        x = LEFT
        for name, color in zip(NAMES, self.colors(), strict=True):
            painter.fillRect(QRectF(x, 10, 14, 3), color)
            painter.setPen(QColor(theme.current().text))
            painter.drawText(QRectF(x + 20, 2, 140, 18), Qt.AlignLeft | Qt.AlignVCenter, name)
            x += 28 + painter.fontMetrics().horizontalAdvance(name)

    def _end_labels(self, painter: QPainter, ends: list[tuple[float, int]]) -> None:
        """La valeur au bout de chaque courbe, écartées de 16 px au moins (sans se chevaucher)."""
        last, plot = None, self._plot()
        for y, k in sorted(ends):
            y = y if last is None else max(y, last + 16)
            last = y
            painter.setPen(self.colors()[k])
            painter.drawText(QRectF(plot.right() + 8, y - 9, RIGHT - 10, 18),
                             Qt.AlignLeft | Qt.AlignVCenter,
                             f"{fr(self.points[-1][1][k], True)} R")  # fmt: skip

    def mouseMoveEvent(self, event) -> None:
        if not self.points:
            return
        plot = self._plot()
        index = round((event.position().x() - plot.left()) / plot.width() * len(self.points))
        index = min(max(index, 1), len(self.points))
        if index != self._hover:
            self._hover = index
            self.update()
        entry, totals = self.points[index - 1]
        instrument = by_symbol(entry["symbol"])
        name = instrument.name if instrument else entry["symbol"]
        avis = {"oui": " · Claude : OUI", "non": " · Claude : NON"}.get(entry.get("avis"), "")
        result = fr(entry["result_r"], True)
        lines = [f"Setup {index} · {name} · {entry['side']}{avis} · {result} R"]
        for (label, _), total in zip(CURVES, totals, strict=True):
            lines.append(f"{label} : {fr(total, True)} R")
        QToolTip.showText(event.globalPosition().toPoint(), "\n".join(lines), self)

    def leaveEvent(self, _event) -> None:
        self._hover = None
        QToolTip.hideText()
        self.update()

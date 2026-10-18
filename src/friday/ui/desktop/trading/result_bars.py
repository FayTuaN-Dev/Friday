"""Barres du bilan des setups (onglet « Setups ») : le total en R des setups terminés, par
marché ou par stratégie, du meilleur au pire. Une barre par ligne, partant d'un même zéro :
vers la droite en vert (ça a rapporté), vers la gauche en rouge (ça a coûté)."""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from friday.ui.desktop import theme
from friday.ui.desktop.journal.equity_chart import fr
from friday.ui.desktop.journal.window import GAIN, LOSS

ROW, NAME, VALUE = 24, 130, 140  # hauteur d'une ligne, colonne du nom, colonne de la valeur


class ResultBars(QWidget):
    def __init__(self, title: str) -> None:
        super().__init__()
        self.title = title
        self.rows: list[tuple[str, int, float]] = []  # review.totals_by()
        self._fit()

    def set_rows(self, rows) -> None:
        self.rows = list(rows)
        self._fit()
        self.update()

    def _fit(self) -> None:
        self.setFixedHeight(ROW * (max(1, len(self.rows)) + 1) + 6)

    def paintEvent(self, _event) -> None:
        p = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QColor(p.text))
        painter.drawText(QRectF(0, 0, self.width(), ROW), Qt.AlignLeft | Qt.AlignVCenter,
                         self.title)  # fmt: skip
        if not self.rows:
            painter.setPen(QColor(p.muted))
            painter.drawText(QRectF(0, ROW, self.width(), ROW), Qt.AlignLeft | Qt.AlignVCenter,
                             "Aucun setup terminé.")  # fmt: skip
            return
        span = max(abs(total) for _, _, total in self.rows) or 1.0
        lows = any(total < 0 for _, _, total in self.rows)
        highs = any(total > 0 for _, _, total in self.rows)
        width = max(10.0, self.width() - NAME - VALUE)
        # le zéro : au milieu s'il y a gains et pertes, sinon au bord (toute la place)
        zero = NAME + (width / 2 if lows and highs else width if lows else 0)
        reach = width / 2 if lows and highs else width
        for i, (name, count, total) in enumerate(self.rows, 1):
            top = ROW * i
            painter.setPen(QColor(p.text))
            shown = painter.fontMetrics().elidedText(name, Qt.ElideRight, NAME - 8)
            painter.drawText(QRectF(0, top, NAME - 8, ROW), Qt.AlignLeft | Qt.AlignVCenter, shown)
            size = reach * abs(total) / span
            left = zero if total >= 0 else zero - size
            bar = QRectF(left, top + 6, max(size, 1.5), ROW - 12)
            painter.setPen(Qt.NoPen)
            painter.setBrush(GAIN if total > 0 else LOSS if total < 0 else QColor(p.muted))
            painter.drawRoundedRect(bar, 3, 3)
            painter.setPen(QColor(p.muted))
            value = f"{fr(total, True)} R · {count} setup{'s' if count > 1 else ''}"
            painter.drawText(QRectF(NAME + width + 8, top, VALUE - 8, ROW),
                             Qt.AlignLeft | Qt.AlignVCenter, value)  # fmt: skip
        painter.setPen(QPen(QColor(p.muted), 1))  # la ligne du zéro, par-dessus
        painter.drawLine(int(zero), ROW + 2, int(zero), ROW * (len(self.rows) + 1) - 2)
        painter.end()

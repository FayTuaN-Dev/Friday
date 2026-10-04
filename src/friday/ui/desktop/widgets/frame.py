"""Cadre d'une fenêtre sans bordure Windows : une fine marge autour du contenu arrondi,
qui sert de poignée pour redimensionner la fenêtre (curseur adapté sur les bords)."""

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QVBoxLayout, QWidget

MARGIN = 6  # largeur de la zone de redimensionnement, en pixels
CURSORS = {
    Qt.LeftEdge: Qt.SizeHorCursor,
    Qt.RightEdge: Qt.SizeHorCursor,
    Qt.TopEdge: Qt.SizeVerCursor,
    Qt.BottomEdge: Qt.SizeVerCursor,
    Qt.LeftEdge | Qt.TopEdge: Qt.SizeFDiagCursor,
    Qt.RightEdge | Qt.BottomEdge: Qt.SizeFDiagCursor,
    Qt.RightEdge | Qt.TopEdge: Qt.SizeBDiagCursor,
    Qt.LeftEdge | Qt.BottomEdge: Qt.SizeBDiagCursor,
}


class ResizableFrame(QWidget):
    """`shell` est le vrai contenu (le panneau arrondi) ; la marge autour reste transparente."""

    def __init__(self, shell: QWidget) -> None:
        super().__init__(objectName="Transparent")
        self.setMouseTracking(True)
        self._layout = QVBoxLayout(self)
        self._layout.addWidget(shell)
        self.set_maximized(False)

    def set_maximized(self, maximized: bool) -> None:
        self._layout.setContentsMargins(*(0 if maximized else MARGIN,) * 4)
        self._resizable = not maximized

    def edges_at(self, pos: QPoint) -> Qt.Edge:
        edges = Qt.Edges()
        if not self._resizable:
            return edges
        corner = MARGIN * 3  # coins un peu plus larges : plus faciles à attraper
        x, y, w, h = pos.x(), pos.y(), self.width(), self.height()
        if x < MARGIN or (x < corner and (y < MARGIN or y > h - MARGIN)):
            edges |= Qt.LeftEdge
        if x > w - MARGIN or (x > w - corner and (y < MARGIN or y > h - MARGIN)):
            edges |= Qt.RightEdge
        if y < MARGIN or (y < corner and (x < MARGIN or x > w - MARGIN)):
            edges |= Qt.TopEdge
        if y > h - MARGIN or (y > h - corner and (x < MARGIN or x > w - MARGIN)):
            edges |= Qt.BottomEdge
        return edges

    def mouseMoveEvent(self, event) -> None:
        cursor = CURSORS.get(self.edges_at(event.position().toPoint()))
        if cursor is None:
            self.unsetCursor()
        else:
            self.setCursor(cursor)

    def mousePressEvent(self, event) -> None:
        edges = self.edges_at(event.position().toPoint())
        if event.button() == Qt.LeftButton and edges:
            self.window().windowHandle().startSystemResize(edges)

    def paintEvent(self, _event) -> None:
        # Presque transparent mais pas tout à fait : sous Windows, les pixels totalement
        # transparents laissent passer les clics, et la marge ne servirait plus de poignée.
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 1))
        painter.end()

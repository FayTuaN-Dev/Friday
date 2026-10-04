"""Icônes fines au trait (SVG, dessin inspiré de Lucide, licence ISC), colorées par le thème."""

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

PATHS = {
    "send": '<path d="M22 2 11 13"/><path d="m22 2-7 20-4-9-9-4z"/>',
    "mic": '<rect x="9" y="2" width="6" height="12" rx="3"/>'
    '<path d="M19 10v1a7 7 0 0 1-14 0v-1"/><path d="M12 18v4"/>',
    "volume": '<path d="M11 5 6 9H2v6h4l5 4z"/>'
    '<path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M19 5a10 10 0 0 1 0 14"/>',
    "mute": '<path d="M11 5 6 9H2v6h4l5 4z"/><path d="m22 9-6 6"/><path d="m16 9 6 6"/>',
    "reset": '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/>',
    "palette": '<circle cx="13.5" cy="6.5" r="1"/><circle cx="17.5" cy="10.5" r="1"/>'
    '<circle cx="8.5" cy="7.5" r="1"/><circle cx="6.5" cy="12.5" r="1"/>'
    '<path d="M12 2a10 10 0 0 0 0 20c1 0 1.7-.8 1.7-1.7 0-.4-.2-.8-.4-1.1-.3-.3-.4-.7-.4-1.1'
    ' 0-.9.8-1.7 1.7-1.7H16a6 6 0 0 0 6-6c0-4.9-4.5-8.4-10-8.4z"/>',
    "minimize": '<path d="M5 12h14"/>',
    "maximize": '<rect x="5" y="5" width="14" height="14" rx="2"/>',
    "close": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
}


def icon(name: str, color: str, size: int = 20, stroke: float = 1.8) -> QIcon:
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" '
        f'stroke-linejoin="round">{PATHS[name]}</svg>'
    )
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    pixmap = QPixmap(size * 2, size * 2)  # double résolution : net sur les écrans haute densité
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter, QRectF(0, 0, size * 2, size * 2))
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)

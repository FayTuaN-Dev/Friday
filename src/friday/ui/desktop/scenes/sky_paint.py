"""Ce que la scène météo dessine UNE fois et garde en image (U8) : le ciel et son soleil ou
sa lune, chaque nuage, et les textes. Constaté : tout redessiner 30 fois par seconde coûtait
13 ms par image (les nuages surtout : ~180 ellipses en dégradé), et Python, occupé à
peindre, privait la voix de son fil (coupures). Une image se recopie en une fraction de ms.
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPixmap, QRadialGradient

from friday.ui.desktop.theme.stylesheet import FONT_HUD

SKIES = {  # (haut, bas) du dégradé : jour, nuit
    "clair": (("#2f6fbf", "#9fd0f5"), ("#05070f", "#16213d")),
    "nuageux": (("#45709e", "#a9c4dc"), ("#070a12", "#1b2335")),
    "couvert": (("#59677a", "#9aa6b4"), ("#0a0c11", "#1e232c")),
    "brouillard": (("#7d8690", "#c4c9ce"), ("#101215", "#2a2e33")),
    "pluie": (("#3b4756", "#7c8896"), ("#06080c", "#1a2029")),
    "neige": (("#8b9bb0", "#dfe7f0"), ("#0d1119", "#2c3442")),
    "orage": (("#232a36", "#4d5868"), ("#040507", "#141821")),
}
PUFFS = ((0, 0, 1.0), (-0.7, 0.18, 0.7), (0.75, 0.15, 0.75), (0.3, -0.3, 0.6))  # un nuage


def font(size: int, spacing: float = 0, family: str = FONT_HUD) -> QFont:
    f = QFont(family)
    f.setPixelSize(size)
    f.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
    return f


def _canvas(w: int, h: int) -> tuple[QPixmap, QPainter]:
    pixmap = QPixmap(max(1, int(w)), max(1, int(h)))
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    return pixmap, painter


def background(kind: str, day: bool, w: int, h: int) -> QPixmap:
    """Le dégradé du ciel, avec le soleil ou la lune par beau temps."""
    pixmap, p = _canvas(w, h)
    top, bottom = SKIES[kind][0 if day else 1]
    sky = QLinearGradient(0, 0, 0, h)
    sky.setColorAt(0, QColor(top))
    sky.setColorAt(1, QColor(bottom))
    p.fillRect(0, 0, w, h, sky)
    if kind in ("clair", "nuageux"):
        center, radius = QPointF(w * 0.78, h * 0.22), min(w, h) * (0.09 if day else 0.06)
        color = QColor(255, 236, 170) if day else QColor(220, 228, 255)
        glow = QRadialGradient(center, radius * 4)
        glow.setColorAt(0, QColor(color.red(), color.green(), color.blue(), 150))
        glow.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawEllipse(center, radius * 4, radius * 4)
        p.setBrush(color)
        p.drawEllipse(center, radius, radius)
    p.end()
    return pixmap


def cloud_sprite(kind: str, day: bool, r: float) -> QPixmap:
    """Un nuage de rayon `r` (quatre bouffées en dégradé), centré dans son image."""
    shade = {"orage": 70, "pluie": 120, "couvert": 170}.get(kind, 235)
    if not day:
        shade = int(shade * 0.35)
    alpha = 120 if kind == "brouillard" else 170
    pixmap, p = _canvas(r * 3.6, r * 2.6)
    cx, cy = r * 1.8, r * 1.3
    p.setPen(Qt.NoPen)
    for dx, dy, k in PUFFS:
        center = QPointF(cx + dx * r, cy + dy * r)
        g = QRadialGradient(center, r * k)
        g.setColorAt(0, QColor(shade, shade, shade + 8, alpha))
        g.setColorAt(1, QColor(shade, shade, shade + 8, 0))
        p.setBrush(g)
        p.drawEllipse(center, r * k, r * k * 0.75)
    p.end()
    return pixmap


def text_layer(data: dict, place: str, w: int, h: int, insets: tuple[int, int]) -> QPixmap:
    """Lieu, température, détails et prévisions, posés de haut en bas dans la partie visible
    (sous la barre de titre, au-dessus de la conversation de Friday)."""
    pixmap, p = _canvas(w, h)
    current, days = data.get("current", {}), data.get("days", [])
    light, soft = QColor(255, 255, 255, 235), QColor(255, 255, 255, 170)
    top, bottom = insets
    limit = h - bottom - 12
    p.setPen(soft)
    p.setFont(font(15, 4))
    p.drawText(QRectF(40, top + 24, w - 80, 30), Qt.AlignLeft, place.upper())
    size = max(70, min(170, (limit - top) * 0.3))
    p.setPen(light)
    p.setFont(font(int(min(w * 0.2, size * 0.85))))
    temperature = f"{current.get('temperature', '—')}°"
    p.drawText(QRectF(36, top + 58, w * 0.6, size), Qt.AlignLeft | Qt.AlignBottom, temperature)
    p.setFont(font(17, 1))
    p.setPen(soft)
    details = (f"{current.get('label', '')} · ressenti {current.get('feels_like', '—')}° · "
               f"vent {current.get('wind', '—')} km/h · humidité "
               f"{current.get('humidity', '—')} %")  # fmt: skip
    box = QRectF(42, top + 64 + size, w - 84, 60)
    used = p.boundingRect(box, Qt.AlignLeft | Qt.TextWordWrap, details)
    p.drawText(box, Qt.AlignLeft | Qt.TextWordWrap, details)
    if days and used.bottom() + 14 + 100 <= limit:  # sinon : la conversation le cacherait
        _forecast(p, w, used.bottom() + 14, days[:7])
    p.end()
    return pixmap


def _forecast(p: QPainter, w: int, y: float, days: list[dict]) -> None:
    band = QRectF(30, y, w - 60, 100)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(0, 0, 0, 70))
    p.drawRoundedRect(band, 14, 14)
    cell = band.width() / len(days)
    for n, day in enumerate(days):
        x = band.left() + n * cell
        p.setPen(QColor(255, 255, 255, 170))
        p.setFont(font(11, 2))
        p.drawText(QRectF(x, band.top() + 10, cell, 18), Qt.AlignCenter, day["day"].upper())
        p.setFont(font(24, family="Segoe UI Emoji"))
        p.drawText(QRectF(x, band.top() + 30, cell, 32), Qt.AlignCenter, day.get("icon", ""))
        p.setPen(QColor(255, 255, 255, 230))
        p.setFont(font(14))
        p.drawText(QRectF(x, band.top() + 66, cell, 22), Qt.AlignCenter,
                   f"{day['min']}° / {day['max']}°")  # fmt: skip

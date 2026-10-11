"""Scène météo plein écran (J7) : un ciel animé selon le temps qu'il fait (soleil, nuages,
pluie, neige, orage, brouillard ; jour ou nuit avec étoiles), la température en grand, le
ressenti, le vent, l'humidité et les prévisions des 7 jours. Données : l'outil météo
(Open-Meteo) ; tout est dessiné en Qt, sans page web."""

import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

from friday.ui.desktop.theme.stylesheet import FONT_HUD

FPS = 30


def font(size: int, spacing: float = 0, family: str = FONT_HUD) -> QFont:
    f = QFont(family)
    f.setPixelSize(size)
    f.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
    return f


def sky_kind(code: int | None) -> str:
    """Code météo (WMO) → « clair », « nuageux », « couvert », « brouillard », « pluie »,
    « neige » ou « orage »."""
    code = -1 if code is None else code
    if code in (0, 1):
        return "clair"
    if code == 2:
        return "nuageux"
    if code in (45, 48):
        return "brouillard"
    if code in (71, 73, 75, 77, 85, 86):
        return "neige"
    if code >= 95:
        return "orage"
    if 51 <= code <= 82:
        return "pluie"
    return "couvert"


SKIES = {  # (haut, bas) du dégradé : jour, nuit
    "clair": (("#2f6fbf", "#9fd0f5"), ("#05070f", "#16213d")),
    "nuageux": (("#45709e", "#a9c4dc"), ("#070a12", "#1b2335")),
    "couvert": (("#59677a", "#9aa6b4"), ("#0a0c11", "#1e232c")),
    "brouillard": (("#7d8690", "#c4c9ce"), ("#101215", "#2a2e33")),
    "pluie": (("#3b4756", "#7c8896"), ("#06080c", "#1a2029")),
    "neige": (("#8b9bb0", "#dfe7f0"), ("#0d1119", "#2c3442")),
    "orage": (("#232a36", "#4d5868"), ("#040507", "#141821")),
}
CLOUDS = {"clair": 2, "nuageux": 6, "couvert": 11, "brouillard": 9, "pluie": 10, "neige": 9,
          "orage": 12}  # fmt: skip


class WeatherScene(QWidget):
    draws_title = True  # le lieu est écrit dans la scène

    def __init__(self, data: dict, place: str, parent=None, seed: int = 4) -> None:
        super().__init__(parent)
        self.data, self.place = data, place
        current = data.get("current", {})
        self.kind = sky_kind(current.get("code"))
        self.day = bool(current.get("is_day", True))
        rng = self.rng = random.Random(seed)
        self.stars = [(rng.random(), rng.random() * 0.7, rng.uniform(0.5, 1.8)) for _ in range(140)]
        self.clouds = [[rng.uniform(-0.2, 1.1), rng.uniform(0.04, 0.45), rng.uniform(0.18, 0.4),
                        rng.uniform(0.006, 0.02)] for _ in range(CLOUDS[self.kind])]  # fmt: skip
        count = {"pluie": 260, "orage": 320, "neige": 180}.get(self.kind, 0)
        self.drops = [[rng.random(), rng.random(), rng.uniform(0.6, 1.0)] for _ in range(count)]
        self.time, self.flash = 0.0, 0.0
        self.insets = (0, 0)  # (haut, bas) cachés par Friday quand la scène est en fond (U8)
        self._timer = QTimer(self, interval=1000 // FPS, timeout=self._tick)
        self._timer.start()

    def set_insets(self, top: int, bottom: int) -> None:
        self.insets = (top, bottom)
        self.update()

    def _tick(self) -> None:
        dt = 1 / FPS
        self.time += dt
        for cloud in self.clouds:
            cloud[0] += cloud[3] * dt * 4
            if cloud[0] > 1.25:
                cloud[0] = -0.35
        fall = 0.18 if self.kind == "neige" else 1.4
        for drop in self.drops:
            drop[1] += fall * drop[2] * dt
            if self.kind == "neige":
                drop[0] += math.sin(self.time * 1.3 + drop[2] * 9) * 0.0008
            if drop[1] > 1:
                drop[0], drop[1] = self.rng.random(), -0.05
        if self.kind == "orage":
            self.flash = max(0.0, self.flash - dt * 2.5)
            if self.rng.random() < dt * 0.25:
                self.flash = 1.0
        if self.isVisible():
            self.update()

    # --- Dessin ---

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        top, bottom = SKIES[self.kind][0 if self.day else 1]
        sky = QLinearGradient(0, 0, 0, h)
        sky.setColorAt(0, QColor(top))
        sky.setColorAt(1, QColor(bottom))
        p.fillRect(self.rect(), sky)
        if not self.day:
            self._stars(p, w, h)
        if self.kind in ("clair", "nuageux"):
            self._sun_or_moon(p, w, h)
        self._clouds(p, w, h)
        self._precipitation(p, w, h)
        if self.flash > 0:
            p.fillRect(self.rect(), QColor(220, 230, 255, int(150 * self.flash**2)))
        self._texts(p, w, h)
        p.end()

    def _stars(self, p: QPainter, w: int, h: int) -> None:
        cover = {"clair": 1.0, "nuageux": 0.6}.get(self.kind, 0.15)
        for x, y, size in self.stars:
            twinkle = 0.55 + 0.45 * math.sin(self.time * 2 + x * 40)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 240, int(200 * twinkle * cover)))
            p.drawEllipse(QPointF(x * w, y * h), size, size)

    def _sun_or_moon(self, p: QPainter, w: int, h: int) -> None:
        center, radius = QPointF(w * 0.78, h * 0.22), min(w, h) * (0.09 if self.day else 0.06)
        glow = QRadialGradient(center, radius * 4)
        color = QColor(255, 236, 170) if self.day else QColor(220, 228, 255)
        pulse = 1 + 0.04 * math.sin(self.time * 1.2)
        glow.setColorAt(0, QColor(color.red(), color.green(), color.blue(), 150))
        glow.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawEllipse(center, radius * 4 * pulse, radius * 4 * pulse)
        p.setBrush(color)
        p.drawEllipse(center, radius, radius)

    def _clouds(self, p: QPainter, w: int, h: int) -> None:
        shade = {"orage": 70, "pluie": 120, "couvert": 170}.get(self.kind, 235)
        if not self.day:
            shade = int(shade * 0.35)
        alpha = 120 if self.kind == "brouillard" else 170
        p.setPen(Qt.NoPen)
        for x, y, size, _ in self.clouds:
            cx, cy, r = x * w, y * h, size * min(w, h)
            for dx, dy, k in ((0, 0, 1.0), (-0.7, 0.18, 0.7), (0.75, 0.15, 0.75), (0.3, -0.3, 0.6)):
                g = QRadialGradient(QPointF(cx + dx * r, cy + dy * r), r * k)
                g.setColorAt(0, QColor(shade, shade, shade + 8, alpha))
                g.setColorAt(1, QColor(shade, shade, shade + 8, 0))
                p.setBrush(g)
                p.drawEllipse(QPointF(cx + dx * r, cy + dy * r), r * k, r * k * 0.75)

    def _precipitation(self, p: QPainter, w: int, h: int) -> None:
        if self.kind == "neige":
            p.setPen(Qt.NoPen)
            for x, y, size in self.drops:
                p.setBrush(QColor(255, 255, 255, int(200 * size)))
                p.drawEllipse(QPointF(x * w, y * h), 2.2 * size, 2.2 * size)
        elif self.drops:
            for x, y, size in self.drops:
                p.setPen(QPen(QColor(190, 210, 235, int(150 * size)), 1.2))
                p.drawLine(QPointF(x * w, y * h), QPointF(x * w - 3, y * h + 16 * size))

    def _texts(self, p: QPainter, w: int, h: int) -> None:
        current, days = self.data.get("current", {}), self.data.get("days", [])
        light = QColor(255, 255, 255, 235)
        soft = QColor(255, 255, 255, 170)
        # Tout tient dans la partie visible (sous la barre de titre, au-dessus de Friday), posé
        # de haut en bas : lieu, température, détails, prévisions (s'il reste la place)
        top, bottom = self.insets
        limit = h - bottom - 12
        p.setPen(soft)
        p.setFont(font(15, 4))
        p.drawText(QRectF(40, top + 24, w - 80, 30), Qt.AlignLeft, self.place.upper())
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
        if used.bottom() + 14 + 100 <= limit:  # sinon : la conversation cacherait le bandeau
            self._forecast(p, w, used.bottom() + 14, days[:7])

    def _forecast(self, p: QPainter, w: int, y: float, days: list[dict]) -> None:
        """Le bandeau des jours suivants, à partir de la hauteur `y`."""
        if not days:
            return
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

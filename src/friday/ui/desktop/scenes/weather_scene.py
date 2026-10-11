"""Scène météo plein écran (J7) : un ciel animé selon le temps qu'il fait (soleil, nuages,
pluie, neige, orage, brouillard ; jour ou nuit avec étoiles), la température en grand, le
ressenti, le vent, l'humidité et les prévisions des 7 jours. Données : l'outil météo
(Open-Meteo) ; tout est dessiné en Qt, sans page web.

Léger à dessiner (U8) : le ciel, les nuages et les textes sont des images faites une fois
(sky_paint.py) ; à chaque image, on les recopie et l'on ajoute étoiles et pluie en quelques
appels groupés."""

import math
import random

from PySide6.QtCore import QLineF, QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from friday.ui.desktop.scenes.sky_paint import SKIES, background, cloud_sprite, font, text_layer

__all__ = ["SKIES", "WeatherScene", "font", "sky_kind"]

FPS = 30
BUCKETS = 4  # niveaux de transparence : les points d'un même niveau partent en un appel


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
        self._cache: tuple | None = None  # (taille, marges) → images faites une fois
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

    def _layers(self) -> tuple:
        w, h = self.width(), self.height()
        key = (w, h, self.insets)
        if self._cache is None or self._cache[0] != key:
            unit = min(w, h)
            sprites = [
                cloud_sprite(self.kind, self.day, size * unit) for _, _, size, _ in self.clouds
            ]
            self._cache = (key, background(self.kind, self.day, w, h), sprites,
                           text_layer(self.data, self.place, w, h, self.insets))  # fmt: skip
        return self._cache[1:]

    def paintEvent(self, _event) -> None:
        sky, sprites, texts = self._layers()
        w, h = self.width(), self.height()
        p = QPainter(self)
        p.drawPixmap(0, 0, sky)
        p.setRenderHint(QPainter.Antialiasing)
        if not self.day:
            self._stars(p, w, h)
        for (x, y, _, _), sprite in zip(self.clouds, sprites, strict=True):
            p.drawPixmap(QPointF(x * w - sprite.width() / 2, y * h - sprite.height() / 2), sprite)
        self._precipitation(p, w, h)
        if self.flash > 0:
            p.fillRect(self.rect(), QColor(220, 230, 255, int(150 * self.flash**2)))
        p.drawPixmap(0, 0, texts)
        p.end()

    def _stars(self, p: QPainter, w: int, h: int) -> None:
        cover = {"clair": 1.0, "nuageux": 0.6}.get(self.kind, 0.15)
        groups: dict[tuple[int, bool], list[QPointF]] = {}
        for x, y, size in self.stars:
            twinkle = 0.55 + 0.45 * math.sin(self.time * 2 + x * 40)
            level = min(BUCKETS - 1, int(twinkle * BUCKETS))
            groups.setdefault((level, size > 1.1), []).append(QPointF(x * w, y * h))
        for (level, big), points in groups.items():
            alpha = int(200 * (level + 0.5) / BUCKETS * cover)
            p.setPen(QPen(QColor(255, 255, 240, alpha), 3.0 if big else 1.6, Qt.SolidLine,
                          Qt.RoundCap))  # fmt: skip
            p.drawPoints(points)

    def _precipitation(self, p: QPainter, w: int, h: int) -> None:
        groups: dict[int, list] = {}
        snow = self.kind == "neige"
        for x, y, size in self.drops:
            level = min(BUCKETS - 1, int((size - 0.6) / 0.4 * BUCKETS))
            if snow:
                groups.setdefault(level, []).append(QPointF(x * w, y * h))
            else:
                groups.setdefault(level, []).append(
                    QLineF(x * w, y * h, x * w - 3, y * h + 16 * size)
                )
        for level, items in groups.items():
            size = 0.6 + 0.4 * (level + 0.5) / BUCKETS
            if snow:
                p.setPen(QPen(QColor(255, 255, 255, int(200 * size)), 4.4 * size, Qt.SolidLine,
                              Qt.RoundCap))  # fmt: skip
                p.drawPoints(items)
            else:
                p.setPen(QPen(QColor(190, 210, 235, int(150 * size)), 1.2))
                p.drawLines(items)

"""Couches de dessin du noyau, de l'arrière vers l'avant, toutes en lumière additive :
halo → particules floues → rayons → circuits → anneaux (+ étincelles) → noyau en « œil ».

Mixin utilisé par HoloOrb : il lit `scene`, `color`, `cx`, `cy`, `size`, `world`, `time`,
`turn`, `speed`, `level`, `sparks` sur le widget.
"""

import math

import numpy as np
from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap, QPolygonF, QRadialGradient

from friday.ui.desktop.widgets.holo.scene import GLYPHS, WIDTHS


def glow_sprite(color: tuple, size: int = 64) -> QPixmap:
    """Petite tache lumineuse, réutilisée pour les particules, les étincelles et le cœur."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    p = QPainter(pixmap)
    g = QRadialGradient(size / 2, size / 2, size / 2)
    g.setColorAt(0, QColor(255, 250, 235, 255))
    g.setColorAt(0.25, QColor(*color, 200))
    g.setColorAt(1, QColor(*color, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(g)
    p.drawEllipse(0, 0, size, size)
    p.end()
    return pixmap


# Anneaux du noyau : (rayon, épaisseur, sens et vitesse de rotation, longueur en degrés)
CORE_ARCS = ((0.1, 2.6, 1.0, 290), (0.14, 1.2, -0.7, 220), (0.19, 0.8, 0.4, 300),
             (0.25, 0.6, -0.25, 140))  # fmt: skip


class HoloLayers:
    _pens: dict
    _sprite: QPixmap
    _sprite_color: tuple | None = None

    def project(self, p: np.ndarray):
        q = p @ self.world.T
        persp = 2.8 / (2.8 - q[:, 2])
        x = self.cx + q[:, 0] * persp * self.size
        y = self.cy + q[:, 1] * persp * self.size
        return x, y, np.clip((q[:, 2] + 1.2) / 2.4, 0, 1)  # profondeur : 0 derrière, 1 devant

    def pen(self, alpha: float, width: float, whiten: float = 0.0) -> QPen:
        """Stylo mis en cache (en créer un par trait coûte cher) : alpha par paliers de 8."""
        key = (self.color, int(max(0, min(255, alpha))) // 8, round(width, 1), round(whiten, 1))
        pen = self._pens.get(key)
        if pen is None:
            c = tuple(int(v + (255 - v) * key[3]) for v in self.color)
            pen = QPen(QColor(*c, min(255, key[1] * 8 + 4)), key[2])
            pen.setCapStyle(Qt.RoundCap)
            if len(self._pens) > 4000:
                self._pens.clear()
            self._pens[key] = pen
        return pen

    def draw_layers(self, painter: QPainter, glow: float) -> None:
        if self._sprite_color != self.color:
            self._sprite, self._sprite_color = glow_sprite(self.color), self.color
        painter.setCompositionMode(QPainter.CompositionMode_Plus)
        self._draw_halo(painter, glow)
        self._draw_particles(painter, glow)
        self._draw_rays(painter, glow)
        self._draw_glyphs(painter, glow)
        self._draw_rings(painter, glow)
        self._draw_core(painter, glow)

    def _blob(self, painter, x: float, y: float, radius: float, opacity: float) -> None:
        painter.setOpacity(max(0.0, min(1.0, opacity)))
        painter.drawPixmap(QRectF(x - radius, y - radius, 2 * radius, 2 * radius), self._sprite,
                           QRectF(self._sprite.rect()))  # fmt: skip

    def _draw_halo(self, painter, glow):
        center, radius = QPointF(self.cx, self.cy), self.size * 1.8
        gradient = QRadialGradient(center, radius)
        gradient.setColorAt(0, QColor(*self.color, int(45 * glow)))
        gradient.setColorAt(0.55, QColor(*self.color, int(12 * glow)))
        gradient.setColorAt(1, QColor(*self.color, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(gradient)
        painter.drawEllipse(center, radius, radius)
        painter.setBrush(Qt.NoBrush)

    def _draw_particles(self, painter, glow):
        s = self.scene
        wobble = 1 + 0.04 * np.sin(self.time * 0.5 + np.arange(len(s.particles)))
        x, y, depth = self.project(s.particles * wobble[:, None])
        for i in range(len(s.particles)):
            self._blob(painter, x[i], y[i], s.particle_size[i] * (0.6 + depth[i]),
                       0.22 * glow * (0.3 + depth[i]))  # fmt: skip
        painter.setOpacity(1)

    def _draw_rays(self, painter, glow):
        groups: dict = {}  # dessinés par lots, un appel par niveau de luminosité
        for angle, start, end, bright in self.scene.rays:
            a = angle + self.turn * 0.072
            flicker = 0.55 + 0.45 * math.sin(self.time * 1.7 + angle * 5)
            reach = end * (1 + 0.15 * self.level)
            c, s = math.cos(a) * self.size, math.sin(a) * self.size
            line = QLineF(self.cx + c * start, self.cy + s * start,
                          self.cx + c * reach, self.cy + s * reach)  # fmt: skip
            groups.setdefault(int(85 * bright * flicker * glow) // 12, []).append(line)
        for level, lines in groups.items():
            painter.setPen(self.pen(level * 12, 0.8))
            painter.drawLines(lines)

    def _draw_glyphs(self, painter, glow):
        s = self.scene
        x, y, depth = self.project(s.glyph_points)
        on = 0.5 + 0.5 * np.sin(self.time * (1.5 + self.speed) + s.glyph_phases)
        for g in range(GLYPHS):
            if on[g] < 0.2:
                continue
            a, b = s.glyph_offsets[g], s.glyph_offsets[g + 1]
            painter.setPen(self.pen(190 * on[g] * glow * (0.25 + depth[a:b].mean()), 1.0))
            painter.drawPolyline(QPolygonF([QPointF(x[i], y[i]) for i in range(a, b)]))

    def _draw_rings(self, painter, glow):
        s = self.scene
        x, y, depth = self.project(s.ring_points(s.owners, s.thetas, self.turn))
        means = np.add.reduceat(depth, s.arc_starts) / s.arc_lengths
        alpha = 210 * s.arc_bright * glow * (0.15 + means)
        bucket = np.clip(alpha // 24, 0, 10).astype(int)  # 11 paliers de luminosité
        order = np.lexsort((s.arc_width_index, bucket))  # regroupés par stylo
        xy = np.stack([x, y], 1).tolist()
        polygons = [QPolygonF([QPointF(*pt) for pt in xy[a:b]]) for a, b in s.arc_bounds]

        # Lueur : traits fins sur une image au quart de la résolution, puis agrandie : le
        # flou d'agrandissement fait une lueur large et douce, pour très peu de calcul.
        w, h = max(4, self.width()), max(4, self.height())
        quarter = QImage(w // 4, h // 4, QImage.Format_ARGB32_Premultiplied)
        quarter.fill(Qt.transparent)
        glow_painter = QPainter(quarter)
        glow_painter.setRenderHint(QPainter.Antialiasing)
        glow_painter.setCompositionMode(QPainter.CompositionMode_Plus)
        glow_painter.scale(0.25, 0.25)
        self._draw_arcs(glow_painter, polygons, order, bucket, glow_pass=True)
        glow_painter.end()
        blurred = quarter.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        painter.drawImage(QRectF(0, 0, w, h), blurred)
        self._draw_arcs(painter, polygons, order, bucket)  # traits nets
        self._draw_sparks(painter)

    def _draw_arcs(self, painter, polygons, order, bucket, glow_pass=False):
        widths, current = self.scene.arc_width_index, None
        for i in order.tolist():
            key = (bucket[i], widths[i])
            if key != current:  # on ne change de stylo qu'entre deux groupes
                current = key
                width = WIDTHS[key[1]]
                if glow_pass:  # épaisseur en pixels de l'image de lueur
                    pen = QPen(self.pen(key[0] * 13, 1.0))
                    pen.setWidthF(0.8 + width * 0.6)
                    pen.setCosmetic(True)
                else:
                    pen = self.pen(key[0] * 24, width * 0.8, whiten=0.03 * key[0])
                painter.setPen(pen)
            painter.drawPolyline(polygons[i])

    def _draw_sparks(self, painter):
        if not self.sparks:
            return
        owners = np.array([s[0] for s in self.sparks])
        thetas = np.array([s[1] for s in self.sparks])
        x, y, depth = self.project(self.scene.ring_points(owners, thetas, self.turn))
        for i, spark in enumerate(self.sparks):
            self._blob(painter, x[i], y[i], 6 + 10 * spark[3], spark[3] * (0.4 + depth[i]))
        painter.setOpacity(1)

    def _draw_core(self, painter, glow):
        pulse = 1 + 0.35 * self.level
        self._blob(painter, self.cx, self.cy, self.size * 0.3 * pulse, 0.85 * glow)
        painter.setOpacity(1)
        for radius, width, turn, span in CORE_ARCS:
            r = radius * self.size * pulse
            painter.setPen(self.pen(230 * glow, width, whiten=0.35))
            start = int((self.turn * turn * 60) % 360 * 16)
            painter.drawArc(QRectF(self.cx - r, self.cy - r, 2 * r, 2 * r), start, span * 16)
        spiral = QPolygonF()  # l'« œil »
        for i in range(70):
            a = i * 0.24 + self.turn * 0.8
            r = self.size * 0.085 * pulse * (i / 70)
            spiral.append(QPointF(self.cx + math.cos(a) * r, self.cy + math.sin(a) * r))
        painter.setPen(self.pen(210 * glow, 1.3, whiten=0.5))
        painter.drawPolyline(spiral)

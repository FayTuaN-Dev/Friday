"""Sphère de particules (J4) : quelques milliers de points sur une sphère qui tourne et respire,
se déforme en vagues avec la voix (le micro quand Friday écoute, sa voix quand elle parle) et
tourbillonne quand elle réfléchit. Au démarrage, les particules sont un nuage diffus qui
converge en spirale vers la sphère quand Friday est prête. Même interface que HoloOrb :
les deux styles sont interchangeables (Réglages → Interface)."""

import math
import time

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

from friday.app.events import AssistantState
from friday.ui.desktop import theme
from friday.ui.desktop.widgets.fast_points import PointBuffer
from friday.ui.desktop.widgets.freeze import freeze
from friday.ui.desktop.widgets.glass import pool
from friday.ui.desktop.widgets.holo.orb import FPS, speech_envelope

POINTS = 2600
LAYERS = 5  # profondeurs dessinées de l'arrière vers l'avant
FULL_SIZE = 97  # rayon en pixels de la sphère en grand (cœur de 270 px de haut)
MIN_POINTS = 600  # en petit : assez de points pour rester une sphère
CONVERGE_SECONDS = 2.2
SPHERE_FPS = 30  # ~13 ms par image : 30 images/s suffisent et ménagent le processeur
# État → (vitesse de rotation, tourbillon, amplitude des vagues au repos)
MOTION = {
    AssistantState.LOADING: (0.05, 0.0, 0.0),
    AssistantState.IDLE: (0.12, 0.0, 0.015),
    AssistantState.LISTENING: (0.2, 0.0, 0.03),
    AssistantState.THINKING: (0.45, 1.0, 0.04),
    AssistantState.SPEAKING: (0.25, 0.0, 0.03),
    AssistantState.PAUSED: (0.03, 0.0, 0.0),
}
EASE = 0.05


def fibonacci_sphere(n: int) -> np.ndarray:
    """`n` points répartis régulièrement sur la sphère unité."""
    i = np.arange(n) + 0.5
    phi = np.arccos(1 - 2 * i / n)
    theta = math.pi * (1 + 5**0.5) * i
    return np.column_stack([np.cos(theta) * np.sin(phi), np.cos(phi), np.sin(theta) * np.sin(phi)])


def converge(progress: float, delays: np.ndarray) -> np.ndarray:
    """Avancement (0 → 1) de chaque particule : elles arrivent les unes après les autres
    (`delays` de 0 à 1), avec une courbe douce."""
    p = np.clip((progress * 1.6 - delays * 0.6), 0.0, 1.0)
    return p * p * p * (p * (p * 6 - 15) + 10)  # quintique : départ et arrivée en douceur


class ParticleSphere(QWidget):
    def __init__(self, parent: QWidget | None = None, seed: int = 5) -> None:
        super().__init__(parent)
        self.setMinimumSize(80, 80)  # réduit en conversation (U1)
        self._buffers = [PointBuffer() for _ in range(LAYERS)]  # points de chaque profondeur
        rng = np.random.default_rng(seed)
        self.targets = fibonacci_sphere(POINTS)
        self.spawn = rng.normal(0, 1.4, (POINTS, 3))  # le nuage du démarrage
        self.delays = (self.targets[:, 1] + 1) / 2  # du bas vers le haut
        self.state = AssistantState.LOADING
        self.base = theme.current().base
        self.color = self._target_color()
        self.speed, self.swirl, self.ripple = MOTION[self.state]
        self.level = 0.0
        self.time = self.turn = 0.0
        self.progress = 0.0  # convergence du démarrage (0 : nuage, 1 : sphère)
        self.converging = False
        self._mic_level = 0.0
        self._envelope = np.zeros(0)
        self._envelope_start = 0.0
        self._last_tick = time.perf_counter()
        self._timer = QTimer(self, interval=1000 // SPHERE_FPS, timeout=self._tick)
        self._timer.start()

    # --- Entrées (comme HoloOrb) ---

    def set_state(self, state: AssistantState) -> None:
        if self.state is AssistantState.LOADING and state is not AssistantState.LOADING:
            self.converging = True  # Friday est prête : le nuage devient sphère
        self.state = state
        freeze(self._timer, state)
        if state is not AssistantState.LISTENING:
            self._mic_level = 0.0

    def set_mic_level(self, level: float) -> None:
        self._mic_level = level

    def play_speech(self, audio: np.ndarray, sample_rate: int) -> None:
        self._envelope = speech_envelope(audio, sample_rate)
        self._envelope_start = time.monotonic()

    def set_base_color(self, base: QColor) -> None:
        self.base = QColor(base)

    # --- Animation ---

    def _target_color(self) -> tuple[int, int, int]:
        c = theme.state_color(self.base, self.state)
        return c.red(), c.green(), c.blue()

    def _target_level(self) -> float:
        if self.state is AssistantState.LISTENING:
            return self._mic_level
        if self.state is AssistantState.SPEAKING:
            i = int((time.monotonic() - self._envelope_start) * FPS)
            return float(self._envelope[i]) if i < self._envelope.size else 0.0
        return 0.0

    def _tick(self) -> None:
        now = time.perf_counter()
        dt, self._last_tick = min(now - self._last_tick, 0.05), now
        speed, swirl, ripple = MOTION[self.state]
        target = self._target_color()
        self.color = tuple(int(round(c + (n - c) * EASE))
                           for c, n in zip(self.color, target, strict=True))  # fmt: skip
        self.speed += (speed - self.speed) * EASE
        self.swirl += (swirl - self.swirl) * EASE
        self.ripple += (ripple - self.ripple) * EASE
        self.level += (self._target_level() - self.level) * 0.15
        if self.converging:
            self.progress = min(1.0, self.progress + dt / CONVERGE_SECONDS)
        self.time += dt
        self.turn += dt * self.speed
        if self.isVisible():
            self.update()

    def positions(self) -> np.ndarray:
        """Les points 3D de cette image : nuage → sphère, vagues de la voix, tourbillon."""
        t, pts = self.time, self.targets
        x, y, z = pts[:, 0], pts[:, 1], pts[:, 2]
        wave = (np.sin(3 * x * math.pi + t * 2.1) * np.cos(2 * y * math.pi - t * 1.7)
                + 0.6 * np.sin(4 * z * math.pi + t * 2.9))  # fmt: skip
        radius = 1 + (self.ripple + 0.11 * self.level) * wave
        sphere = pts * radius[:, None]
        if self.swirl > 0.01:  # réflexion : les latitudes tournent à des vitesses différentes
            a = self.swirl * np.sin(y * 3 + t * 2) * 0.6
            c, s = np.cos(a), np.sin(a)
            sphere = np.column_stack([sphere[:, 0] * c - sphere[:, 2] * s, sphere[:, 1],
                                      sphere[:, 0] * s + sphere[:, 2] * c])  # fmt: skip
        if self.progress >= 1:
            return sphere
        drift = self.spawn + 0.08 * np.sin(t * 0.5 + self.spawn[:, ::-1])
        k = converge(self.progress, self.delays)[:, None]
        spin = (1 - k[:, 0]) * 2.5  # la spirale se resserre en arrivant
        c, s = np.cos(spin), np.sin(spin)
        spiral = np.column_stack([drift[:, 0] * c - drift[:, 2] * s, drift[:, 1],
                                  drift[:, 0] * s + drift[:, 2] * c])  # fmt: skip
        return spiral * (1 - k) + sphere * k

    def paintEvent(self, _event) -> None:
        w, h = self.width(), self.height()
        cx, cy, size = w / 2, h / 2, min(w, h) * 0.36
        a = self.turn
        c, s = math.cos(a), math.sin(a)
        pts = self.positions()
        # Réduite (U1) : moins de points, pour garder la densité du grand format. Constaté :
        # tous les points serrés, leur lumière s'additionnait et la sphère éblouissait.
        # Toujours les mêmes points (tirés une fois) : rien ne clignote.
        scale = min(1.0, size / FULL_SIZE)
        if scale < 1.0:
            if getattr(self, "_order", None) is None or len(self._order) != len(pts):
                self._order = np.random.default_rng(7).permutation(len(pts))
            pts = pts[self._order[: max(MIN_POINTS, int(len(pts) * scale * scale))]]
        x = pts[:, 0] * c + pts[:, 2] * s  # rotation autour de l'axe vertical
        z = -pts[:, 0] * s + pts[:, 2] * c
        y = pts[:, 1] * 0.96 + z * 0.12  # légèrement penchée vers l'avant
        depth = np.clip((z + 1.4) / 2.8, 0, 1)  # 0 : au fond, 1 : devant
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pool(painter, cx, cy, size, min(w, h) / 2)  # verre : une flaque sombre sous la lumière
        painter.setCompositionMode(QPainter.CompositionMode_Plus)  # lumière additive
        r, g, b = self.color
        halo = QRadialGradient(cx, cy, size * 1.5)
        glow = int(28 + 40 * self.level) * min(1.0, self.progress + 0.3) * (0.5 + 0.5 * scale)
        halo.setColorAt(0, QColor(r, g, b, int(glow)))
        halo.setColorAt(1, QColor(r, g, b, 0))
        painter.fillRect(self.rect(), halo)
        fade = 0.35 + 0.65 * self.progress
        layer = np.minimum((depth * LAYERS).astype(int), LAYERS - 1)
        for n in range(LAYERS):
            mask = layer == n
            if not mask.any():
                continue
            near = (n + 0.5) / LAYERS
            alpha = int((40 + 190 * near) * fade * (0.85 + 0.3 * self.level) * (0.7 + 0.3 * scale))
            width = (1.0 + 1.6 * near) * (0.6 + 0.4 * scale)
            painter.setPen(QPen(QColor(r, g, b, min(255, alpha)), width,
                                Qt.SolidLine, Qt.RoundCap))  # fmt: skip
            xs, ys = cx + x[mask] * size, cy - y[mask] * size
            painter.drawPoints(self._buffers[n].fill(xs, ys))  # sans boucle Python
        painter.end()

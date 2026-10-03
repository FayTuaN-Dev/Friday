"""Cercle HUD animé : sa couleur suit l'état de Jarvis, sa taille suit la voix."""

import math
import time

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

from jarvis.app.events import AssistantState
from jarvis.ui.desktop import theme

FPS = 60
# Vitesse de rotation des anneaux (degrés par image) selon l'état
SPIN = {
    AssistantState.LOADING: 0.4,
    AssistantState.IDLE: 0.25,
    AssistantState.LISTENING: 0.8,
    AssistantState.THINKING: 2.5,
    AssistantState.SPEAKING: 0.9,
}


def speech_envelope(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    """Volume de la voix image par image (0 à 1), pour animer pendant la lecture."""
    frame = max(1, sample_rate // FPS)
    n = audio.size // frame
    if n == 0:
        return np.zeros(0)
    rms = np.sqrt(np.mean(audio[: n * frame].reshape(n, frame) ** 2, axis=1))
    return np.clip(rms * 5, 0, 1)


class HudOrb(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(220, 220)
        self.state = AssistantState.LOADING
        self._color = QColor(theme.STATE_COLORS[self.state])
        self._angle = 0.0
        self._level = 0.0  # niveau affiché (lissé)
        self._mic_level = 0.0
        self._envelope = np.zeros(0)
        self._envelope_start = 0.0
        self._timer = QTimer(self, interval=1000 // FPS, timeout=self._tick)
        self._timer.start()

    # --- Entrées ---

    def set_state(self, state: AssistantState) -> None:
        self.state = state
        if state is not AssistantState.LISTENING:
            self._mic_level = 0.0

    def set_mic_level(self, level: float) -> None:
        self._mic_level = level

    def play_speech(self, audio: np.ndarray, sample_rate: int) -> None:
        self._envelope = speech_envelope(audio, sample_rate)
        self._envelope_start = time.monotonic()

    # --- Animation ---

    def _target_level(self) -> float:
        if self.state is AssistantState.LISTENING:
            return self._mic_level
        if self.state is AssistantState.SPEAKING:
            i = int((time.monotonic() - self._envelope_start) * FPS)
            return float(self._envelope[i]) if i < self._envelope.size else 0.0
        if self.state is AssistantState.THINKING:
            return 0.15 + 0.1 * math.sin(time.monotonic() * 6)
        return 0.05 + 0.03 * math.sin(time.monotonic() * 1.5)  # respiration au repos

    def _tick(self) -> None:
        self._angle = (self._angle + SPIN[self.state]) % 360
        self._level += (self._target_level() - self._level) * 0.3
        # Transition douce de couleur entre les états
        target = QColor(theme.STATE_COLORS[self.state])
        c = self._color
        self._color = QColor(
            int(c.red() + (target.red() - c.red()) * 0.15),
            int(c.green() + (target.green() - c.green()) * 0.15),
            int(c.blue() + (target.blue() - c.blue()) * 0.15),
        )
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        center = QPointF(self.width() / 2, self.height() / 2)
        r = min(self.width(), self.height()) * 0.24
        level = self._level

        self._draw_glow(p, center, r * (1.9 + level * 0.6), level)
        self._draw_ticks(p, center, r * 1.75)
        self._draw_arcs(p, center, r * 1.45, self._angle, [(0, 70), (120, 50), (220, 90)], 3)
        self._draw_arcs(p, center, r * 1.25, -self._angle * 1.6, [(30, 140), (210, 140)], 1.5)
        self._draw_core(p, center, r * (0.85 + level * 0.35))
        p.end()

    def _with_alpha(self, alpha: int) -> QColor:
        c = QColor(self._color)
        c.setAlpha(max(0, min(255, alpha)))
        return c

    def _draw_glow(self, p: QPainter, center: QPointF, radius: float, level: float) -> None:
        g = QRadialGradient(center, radius)
        g.setColorAt(0.0, self._with_alpha(int(70 + level * 120)))
        g.setColorAt(0.5, self._with_alpha(int(20 + level * 40)))
        g.setColorAt(1.0, self._with_alpha(0))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(center, radius, radius)

    def _draw_ticks(self, p: QPainter, center: QPointF, radius: float) -> None:
        for i in range(72):
            a = math.radians(i * 5 + self._angle * 0.3)
            long = i % 6 == 0
            inner = radius - (8 if long else 4)
            p.setPen(QPen(self._with_alpha(160 if long else 70), 1.5 if long else 1))
            p.drawLine(
                QPointF(center.x() + inner * math.cos(a), center.y() + inner * math.sin(a)),
                QPointF(center.x() + radius * math.cos(a), center.y() + radius * math.sin(a)),
            )

    def _draw_arcs(self, p, center, radius, rotation, segments, width) -> None:
        rect = QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(self._with_alpha(220), width, Qt.SolidLine, Qt.RoundCap))
        for start, span in segments:
            p.drawArc(rect, int((start + rotation) * 16), int(span * 16))

    def _draw_core(self, p: QPainter, center: QPointF, radius: float) -> None:
        g = QRadialGradient(center, radius)
        g.setColorAt(0.0, QColor(255, 255, 255, 230))
        g.setColorAt(0.25, self._with_alpha(255))
        g.setColorAt(0.8, self._with_alpha(90))
        g.setColorAt(1.0, self._with_alpha(20))
        p.setPen(QPen(self._with_alpha(255), 2))
        p.setBrush(g)
        p.drawEllipse(center, radius, radius)

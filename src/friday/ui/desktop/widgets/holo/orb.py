"""Noyau holographique animé : couleur et vitesse suivent l'état de Friday, l'éclat suit la voix
(le micro quand elle écoute, sa propre voix quand elle parle)."""

import math
import random
import time

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from friday.app.events import AssistantState
from friday.ui.desktop import theme
from friday.ui.desktop.widgets.holo.painter import HoloPainter, PainterThread
from friday.ui.desktop.widgets.holo.scene import RINGS, HoloScene, rotation

FPS = 60  # valeurs de l'enveloppe de la voix par seconde
HOLO_FPS = 30  # images du noyau par seconde (60 doublait le travail sans gain visible)
# État → (vitesse, intensité, étincelles par seconde)
MOTION = {
    AssistantState.LOADING: (0.25, 0.4, 1),
    AssistantState.IDLE: (0.35, 0.65, 3),
    AssistantState.LISTENING: (0.6, 0.85, 8),
    AssistantState.THINKING: (1.4, 1.0, 30),
    AssistantState.SPEAKING: (0.8, 1.05, 12),
}
EASE = 0.05  # transitions douces entre états
TILT = rotation((1, 0, 0), 0.35)  # le noyau est légèrement penché vers l'avant


def speech_envelope(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    """Volume de la voix image par image (0 à 1), pour animer pendant la lecture."""
    frame = max(1, sample_rate // FPS)
    n = audio.size // frame
    if n == 0:
        return np.zeros(0)
    rms = np.sqrt(np.mean(audio[: n * frame].reshape(n, frame) ** 2, axis=1))
    return np.clip(rms * 5, 0, 1)


class HoloOrb(QWidget):
    """L'état et l'animation ; le dessin se fait dans le fil du peintre (painter.py)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(80, 80)  # réduit en conversation (U1)
        self.scene = HoloScene()
        self.rng = random.Random(3)
        self.state = AssistantState.LOADING
        self.base = theme.current().base
        self.color = self._target_color()
        self.speed, self.intensity, _ = MOTION[self.state]
        self.level = 0.0
        self.time = 0.0  # temps de l'animation
        self.turn = 0.0  # rotation accumulée (intégrée : pas de saut quand la vitesse change)
        self.sparks: list[list] = []  # [anneau, angle, vitesse, vie]
        self._painter = PainterThread(HoloPainter(self.scene))
        self.destroyed.connect(self._painter.close)  # le fil s'arrête avec le noyau
        self._shown = 0  # numéro de la dernière image affichée
        self._mic_level = 0.0
        self._envelope = np.zeros(0)
        self._envelope_start = 0.0
        self._last_tick = time.perf_counter()
        self._timer = QTimer(self, interval=1000 // HOLO_FPS, timeout=self._tick)
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

    def set_base_color(self, base: QColor) -> None:
        self.base = QColor(base)  # la transition de couleur se fait en douceur dans _tick

    # --- Animation ---

    def _target_color(self) -> tuple[int, int, int]:
        c = theme.state_color(self.base, self.state)
        return c.red(), c.green(), c.blue()

    def _target_level(self) -> float:
        t = self.time
        if self.state is AssistantState.LISTENING:
            return 0.2 + 0.8 * self._mic_level
        if self.state is AssistantState.SPEAKING:
            i = int((time.monotonic() - self._envelope_start) * FPS)
            voice = float(self._envelope[i]) if i < self._envelope.size else 0.0
            return 0.3 + 0.7 * voice
        if self.state is AssistantState.THINKING:
            return 0.5 + 0.1 * math.sin(t * 3)
        return 0.15 + 0.05 * math.sin(t * 0.9)  # respiration au repos

    def _tick(self) -> None:
        # Temps réel écoulé (une image peut prendre plus de 1/60 s), plafonné contre les sauts
        now = time.perf_counter()
        dt, self._last_tick = min(now - self._last_tick, 0.05), now
        speed, intensity, spark_rate = MOTION[self.state]
        target = self._target_color()
        self.color = tuple(
            int(round(c + (n - c) * EASE)) for c, n in zip(self.color, target, strict=True)
        )
        self.speed += (speed - self.speed) * EASE
        self.intensity += (intensity - self.intensity) * EASE
        self.level += (self._target_level() - self.level) * 0.1
        self.time += dt
        self.turn += dt * self.speed
        self._update_sparks(dt, spark_rate)
        if self.isVisible():
            self._painter.request(self._snapshot())  # dessiné dans le fil du peintre
            frame = self._painter.frame
            if frame is not None and frame[0] != self._shown:
                self.update()

    def _update_sparks(self, dt: float, rate: float) -> None:
        rng = self.rng
        if rng.random() < rate * dt:
            self.sparks.append([rng.randrange(RINGS), rng.uniform(0, 6.28),
                                rng.choice([-1, 1]) * rng.uniform(1.5, 3.5), 1.0])  # fmt: skip
        for spark in self.sparks:
            spark[1] += spark[2] * dt * (0.6 + self.speed)
            spark[3] -= dt * 0.7
        self.sparks = [s for s in self.sparks if s[3] > 0]

    def _snapshot(self) -> dict:
        """L'état du moment, copié pour le peintre (il ne lit jamais le widget)."""
        w, h = self.width(), self.height()
        return {
            "w": w, "h": h, "cx": w / 2, "cy": h / 2,
            "size": min(w, h) * 0.34 * (1 + 0.03 * self.level),
            "world": rotation((0.15, 1, 0.05), self.turn * 0.12) @ TILT,
            "color": self.color, "time": self.time, "turn": self.turn, "speed": self.speed,
            "level": self.level, "sparks": [list(s) for s in self.sparks],
            "glow": self.intensity * (0.75 + 0.6 * self.level),
        }  # fmt: skip

    def paintEvent(self, _event) -> None:
        frame = self._painter.frame
        if frame is None:
            return
        self._shown, image = frame
        painter = QPainter(self)
        painter.drawImage(self.rect(), image)  # une seule opération pour l'interface
        painter.end()

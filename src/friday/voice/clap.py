"""Double clap (J3) : deux claquements de mains rapprochés réveillent Friday, comme « Friday »
dit seul. Repéré sur le flux de l'écoute mains libres (blocs de 20 ms en 16 kHz), sans modèle
ni entraînement. Un clap, c'est :
- un BRUIT SOUDAIN : bien plus fort que le fond sonore des instants d'avant ;
- très BREF (moins de 120 ms au-dessus du seuil) : la parole et la musique durent plus.
Deux claps espacés de 0,15 à 0,8 s, puis une demi-seconde de calme (pas de troisième : un
rythme de musique ou des applaudissements ne réveillent pas). Le temps est compté en échantillons :
le détecteur est déterministe (testable sur des sons fabriqués)."""

from collections.abc import Callable

import numpy as np

RATE = 16_000
SENSITIVITY = {  # niveau de crête minimal (0–1) selon le réglage
    "faible": 0.45,
    "moyenne": 0.28,
    "forte": 0.16,
}
ONSET = 8.0  # la crête doit dépasser 8 fois le niveau moyen du fond sonore
MAX_CLAP = 0.12  # s au-dessus du seuil, au plus
GAP = (0.15, 0.8)  # s entre les deux claps
QUIET_AFTER = 0.5  # s sans bruit soudain après le second (sinon : rythme, applaudissements)
COOLDOWN = 2.0  # s entre deux réveils
BACKGROUND = 0.05  # vitesse d'adaptation au fond sonore


class ClapDetector:
    def __init__(self, on_double: Callable[[], None], sensitivity: str = "moyenne") -> None:
        self.on_double = on_double
        self.threshold = SENSITIVITY.get(sensitivity, SENSITIVITY["moyenne"])
        self.background = 0.01  # niveau moyen (RMS) du fond sonore
        self.now = 0.0  # s écoulées (comptées en échantillons)
        self._burst_start: float | None = None  # bruit soudain en cours depuis…
        self._claps: list[float] = []
        self._pending: float | None = None  # double clap à confirmer après un silence
        self._last_fire = float("-inf")

    def feed(self, block: np.ndarray) -> None:
        """Un bloc de son 16 kHz (20 ms environ)."""
        if block.size == 0:
            return
        start, self.now = self.now, self.now + block.size / RATE
        peak = float(np.abs(block).max())
        rms = float(np.sqrt(np.mean(block**2)))
        loud = peak >= self.threshold and peak >= ONSET * self.background
        if loud and self._burst_start is None:
            self._burst_start = start
        elif not loud:
            if self._burst_start is not None:
                self._burst_ended(self._burst_start, start)
                self._burst_start = None
            self.background += BACKGROUND * (rms - self.background)  # seulement hors bruit
        if self._burst_start is not None and self.now - self._burst_start > MAX_CLAP:
            self._claps.clear()  # un bruit qui dure : parole, musique… on oublie tout
            self._pending = None
        if self._pending is not None and self.now - self._pending >= QUIET_AFTER:
            self._pending = None
            self._claps.clear()
            if self.now - self._last_fire >= COOLDOWN:
                self._last_fire = self.now
                self.on_double()

    def _burst_ended(self, began: float, ended: float) -> None:
        if ended - began > MAX_CLAP:
            return
        if self._pending is not None:  # un troisième : ce n'était pas un double clap
            self._pending = None
            self._claps = [began]
            return
        self._claps = [t for t in self._claps if GAP[0] <= began - t <= GAP[1]] or []
        if self._claps:
            self._pending = began
        else:
            self._claps = [began]

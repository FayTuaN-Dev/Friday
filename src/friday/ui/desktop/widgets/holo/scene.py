"""Géométrie 3D du noyau holographique : anneaux, rayons, circuits, particules (numpy pur).

Tout est construit une seule fois, avec une graine fixe (le noyau a toujours la même forme),
et rangé dans de grands tableaux pour être projeté en un seul calcul à chaque image.
"""

import math
import random

import numpy as np

RINGS = 38
RAYS = 70
GLYPHS = 110
PARTICLES = 60
WIDTHS = (0.5, 0.7, 0.9, 1.3, 2.2)  # épaisseurs possibles des anneaux
ARC_LENGTHS = (0.02, 0.04, 0.08, 0.15, 0.35, 0.7, 1.2)  # radians ; les courts font « pointillés »


def rotation(axis, angle: float) -> np.ndarray:
    x, y, z = np.asarray(axis, dtype=float) / np.linalg.norm(axis)
    c, s, t = math.cos(angle), math.sin(angle), 1 - math.cos(angle)
    return np.array([
        [t * x * x + c, t * x * y - s * z, t * x * z + s * y],
        [t * x * y + s * z, t * y * y + c, t * y * z - s * x],
        [t * x * z - s * y, t * y * z + s * x, t * z * z + c],
    ])  # fmt: skip


def basis(normal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Deux vecteurs perpendiculaires entre eux et à `normal` (le plan d'un anneau)."""
    helper = np.array([1.0, 0, 0]) if abs(normal[0]) < 0.9 else np.array([0, 1.0, 0])
    u = np.cross(normal, helper)
    u /= np.linalg.norm(u)
    return u, np.cross(normal, u)


class HoloScene:
    def __init__(self, seed: int = 11) -> None:
        self.rng = random.Random(seed)
        self._build_rings()
        self._build_glyphs()
        rng = self.rng
        # rayon = (angle, début, fin, luminosité), en fraction de la taille du noyau
        self.rays = [(rng.uniform(0, 6.28), rng.uniform(0.12, 0.5), rng.uniform(0.85, 1.6),
                      rng.uniform(0.15, 1.0)) for _ in range(RAYS)]  # fmt: skip
        self.particles = np.array(
            [self.random_axis() * rng.uniform(0.2, 1.3) for _ in range(PARTICLES)]
        )
        self.particle_size = np.array([rng.uniform(3, 14) for _ in range(PARTICLES)])

    def random_axis(self) -> np.ndarray:
        v = np.array([self.rng.gauss(0, 1) for _ in range(3)])
        return v / np.linalg.norm(v)

    def _build_rings(self) -> None:
        """Chaque anneau = grand cercle découpé en arcs de longueurs variées."""
        rng = self.rng
        u_list, v_list, radius, speed, width, bright = [], [], [], [], [], []
        thetas, owners, arcs = [], [], []  # arcs = (début, fin, anneau) dans le tableau des points
        for ring in range(RINGS):
            u, v = basis(self.random_axis())
            u_list.append(u)
            v_list.append(v)
            radius.append(rng.uniform(0.75, 1.12))
            speed.append(rng.uniform(-0.5, 0.5))
            width.append(rng.randrange(len(WIDTHS)))  # indice dans WIDTHS
            bright.append(rng.uniform(0.35, 1.0))
            angle = rng.uniform(0, 6.28)
            end = angle + 6.28
            while angle < end:
                length = rng.choice(ARC_LENGTHS)
                n = max(2, int(length * 11))  # assez de points pour une courbe lisse
                start = len(thetas)
                thetas += list(np.linspace(angle, angle + length, n))
                owners += [ring] * n
                arcs.append((start, len(thetas), ring))
                angle += length + rng.uniform(0.03, 0.45)
        self.ring_u, self.ring_v = np.array(u_list), np.array(v_list)
        self.ring_radius, self.ring_speed = np.array(radius), np.array(speed)
        self.ring_bright, ring_width = np.array(bright), np.array(width)
        self.thetas, self.owners = np.array(thetas), np.array(owners)
        # Tableaux par arc, pour tout calculer d'un coup à chaque image
        self.arc_bounds = [(a, b) for a, b, _ in arcs]
        self.arc_starts = np.array([a for a, _, _ in arcs])
        self.arc_lengths = np.array([b - a for a, b, _ in arcs])
        rings = np.array([r for _, _, r in arcs])
        self.arc_bright = self.ring_bright[rings]
        self.arc_width_index = ring_width[rings]

    def _build_glyphs(self) -> None:
        """Fragments de circuits (traits à angle droit) posés sur la sphère."""
        paths, phases = [], []
        for _ in range(GLYPHS):
            center = self.random_axis() * self.rng.uniform(0.82, 1.06)
            a, b = basis(center / np.linalg.norm(center))
            point, path = center.copy(), [center.copy()]
            for _ in range(self.rng.randint(2, 6)):
                point = point + self.rng.choice([a, -a, b, -b]) * self.rng.uniform(0.03, 0.11)
                path.append(point.copy())
            paths.append(np.array(path))
            phases.append(self.rng.uniform(0, 6.28))
        self.glyph_offsets = np.cumsum([0] + [len(p) for p in paths])
        self.glyph_points = np.concatenate(paths)
        self.glyph_phases = np.array(phases)

    def ring_points(self, owners: np.ndarray, thetas: np.ndarray, turn: float) -> np.ndarray:
        """Points 3D des anneaux ; `turn` = avance de rotation propre à chaque anneau."""
        t = thetas + turn * self.ring_speed[owners]
        r = self.ring_radius[owners][:, None]
        u, v = self.ring_u[owners], self.ring_v[owners]
        return r * (np.cos(t)[:, None] * u + np.sin(t)[:, None] * v)

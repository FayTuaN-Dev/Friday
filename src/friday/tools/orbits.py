"""Où sont les satellites (M4) : à partir de leurs éléments d'orbite (CelesTrak), le modèle
SGP4 donne leur position à tout instant ; on en tire la latitude, la longitude, l'altitude, et
les passages visibles depuis un lieu (le satellite éclairé par le Soleil dans un ciel noir).
Précision : quelques kilomètres, bien assez pour une carte et une heure de passage."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import numpy as np
from sgp4 import omm
from sgp4.api import Satrec, jday
from sgp4.propagation import gstime

EARTH_KM = 6378.137
FLAT = 1 / 298.257223563
COMPASS = ("nord", "nord-est", "est", "sud-est", "sud", "sud-ouest", "ouest", "nord-ouest")
MIN_ELEVATION = 10  # degrés : plus bas, les arbres et les toits le cachent
DARK_SUN = -6  # degrés : le Soleil assez bas pour que le ciel soit noir


def satellite(fields: dict) -> Satrec:
    """Un satellite à partir de ses éléments au format OMM (le JSON de CelesTrak)."""
    sat = Satrec()
    omm.initialize(sat, fields)
    return sat


def _days(times: list[datetime]) -> tuple[np.ndarray, np.ndarray]:
    pairs = [jday(t.year, t.month, t.day, t.hour, t.minute, t.second + t.microsecond / 1e6)
             for t in times]  # fmt: skip
    return np.array([p[0] for p in pairs]), np.array([p[1] for p in pairs])


def _earth_fixed(sat: Satrec, times: list[datetime]) -> tuple[np.ndarray, np.ndarray]:
    """Positions (km) dans le repère de la Terre qui tourne, et vitesses (km/s)."""
    jd, fr = _days(times)
    _, r, v = sat.sgp4_array(jd, fr)
    theta = np.array([gstime(a + b) for a, b in zip(jd, fr, strict=True)])
    c, s = np.cos(theta), np.sin(theta)
    x, y = c * r[:, 0] + s * r[:, 1], -s * r[:, 0] + c * r[:, 1]
    return np.column_stack([x, y, r[:, 2]]), np.linalg.norm(v, axis=1)


def _geodetic(xyz: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(latitude, longitude en degrés, altitude en km) sur l'ellipsoïde terrestre."""
    x, y, z = xyz[:, 0], xyz[:, 1], xyz[:, 2]
    e2, p = FLAT * (2 - FLAT), np.hypot(x, y)
    lat = np.arctan2(z, p * (1 - e2))
    for _ in range(4):
        n = EARTH_KM / np.sqrt(1 - e2 * np.sin(lat) ** 2)
        lat = np.arctan2(z + e2 * n * np.sin(lat), p)
    n = EARTH_KM / np.sqrt(1 - e2 * np.sin(lat) ** 2)
    return np.degrees(lat), np.degrees(np.arctan2(y, x)), p / np.cos(lat) - n


def _site(lat: float, lon: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Un lieu au sol : sa position (km) et ses directions haut, est, nord."""
    la, lo = np.radians(lat), np.radians(lon)
    e2 = FLAT * (2 - FLAT)
    n = EARTH_KM / np.sqrt(1 - e2 * np.sin(la) ** 2)
    where = np.array([n * np.cos(la) * np.cos(lo), n * np.cos(la) * np.sin(lo),
                      n * (1 - e2) * np.sin(la)])  # fmt: skip
    up = np.array([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)])
    east = np.array([-np.sin(lo), np.cos(lo), 0.0])
    north = np.array([-np.sin(la) * np.cos(lo), -np.sin(la) * np.sin(lo), np.cos(la)])
    return where, up, east, north


def _sun(times: list[datetime]) -> np.ndarray:
    """Direction du Soleil (vecteur unité), dans le repère de la Terre qui tourne."""
    jd, fr = _days(times)
    n = jd + fr - 2451545.0
    g = np.radians(357.528 + 0.9856003 * n)
    lam = np.radians(280.460 + 0.9856474 * n + 1.915 * np.sin(g) + 0.020 * np.sin(2 * g))
    eps = np.radians(23.439 - 0.0000004 * n)
    sx, sy, sz = np.cos(lam), np.cos(eps) * np.sin(lam), np.sin(eps) * np.sin(lam)
    theta = np.array([gstime(a + b) for a, b in zip(jd, fr, strict=True)])
    c, s = np.cos(theta), np.sin(theta)
    return np.column_stack([c * sx + s * sy, -s * sx + c * sy, sz])


def track(sat: Satrec, start: datetime, minutes: int, step: int = 60) -> list[list[float]]:
    """[lon, lat] toutes les `step` secondes ; longitudes sans saut à ±180° (la carte trace
    alors la ligne d'un seul tenant)."""
    times = [start + timedelta(seconds=s) for s in range(0, minutes * 60 + 1, step)]
    lat, lon, _ = _geodetic(_earth_fixed(sat, times)[0])
    lon = np.degrees(np.unwrap(np.radians(lon)))
    return [[round(float(a), 3), round(float(b), 3)] for a, b in zip(lon, lat, strict=True)]


def where(sat: Satrec, when: datetime) -> tuple[float, float, float, float]:
    """(latitude, longitude, altitude en km, vitesse en km/h) à cet instant."""
    xyz, speed = _earth_fixed(sat, [when])
    lat, lon, alt = _geodetic(xyz)
    return float(lat[0]), float(lon[0]), float(alt[0]), float(speed[0] * 3600)


@dataclass
class Pass:
    start: datetime  # début de la partie visible (UTC)
    minutes: int
    highest: int  # hauteur maximale dans le ciel, en degrés
    rises: str  # direction d'où il arrive (« ouest »)
    sets: str  # direction où il disparaît


def passes(sat: Satrec, lat: float, lon: float, start: datetime, hours: int = 48,
           step: int = 20) -> list[Pass]:  # fmt: skip
    """Les passages VISIBLES à l'œil nu au-dessus du lieu, dans les `hours` prochaines heures."""
    times = [start + timedelta(seconds=s) for s in range(0, hours * 3600, step)]
    xyz, _ = _earth_fixed(sat, times)
    home, up, east, north = _site(lat, lon)
    d = xyz - home
    dist = np.linalg.norm(d, axis=1)
    elevation = np.degrees(np.arcsin(d @ up / dist))
    azimuth = np.degrees(np.arctan2(d @ east, d @ north)) % 360
    sun = _sun(times)
    dark = np.degrees(np.arcsin(sun @ up)) < DARK_SUN
    ahead = np.einsum("ij,ij->i", xyz, sun)  # côté jour, ou derrière la Terre (dans l'ombre)
    beside = np.linalg.norm(xyz - ahead[:, None] * sun, axis=1)
    lit = (ahead > 0) | (beside > EARTH_KM)
    seen = (elevation > MIN_ELEVATION) & dark & lit
    found, k = [], 0
    while k < len(times):
        if not seen[k]:
            k += 1
            continue
        end = k
        while end + 1 < len(times) and seen[end + 1]:
            end += 1
        found.append(Pass(
            times[k], max(1, round((end - k + 1) * step / 60)),
            round(float(elevation[k:end + 1].max())),
            COMPASS[round(azimuth[k] / 45) % 8], COMPASS[round(azimuth[end] / 45) % 8],
        ))  # fmt: skip
        k = end + 1
    return found


def now() -> datetime:
    return datetime.now(UTC)

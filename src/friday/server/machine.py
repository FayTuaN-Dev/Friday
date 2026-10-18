"""L'état de la machine du Friday léger (le Pi), pour la carte « Pi » de l'écran du PC :
température, mémoire, depuis quand il tourne, dernière question reçue. Lu dans /proc et /sys
(Linux, bibliothèque standard seulement) ; une valeur introuvable est simplement absente."""

import time
from pathlib import Path

THERMAL = Path("/sys/class/thermal/thermal_zone0/temp")
MEMINFO, UPTIME = Path("/proc/meminfo"), Path("/proc/uptime")


def _read(path: Path) -> str:
    try:
        return path.read_text()
    except OSError:
        return ""


def temperature(path: Path = THERMAL) -> float | None:
    text = _read(path).strip()
    return round(int(text) / 1000, 1) if text.isdigit() else None


def memory(path: Path = MEMINFO) -> tuple[float, float] | None:
    """(utilisée, totale) en Go."""
    values = {}
    for line in _read(path).splitlines():
        name, _, rest = line.partition(":")
        if rest.split():
            values[name] = int(rest.split()[0])  # en ko
    if "MemTotal" not in values or "MemAvailable" not in values:
        return None
    total, free = values["MemTotal"], values["MemAvailable"]
    return round((total - free) / 1024**2, 2), round(total / 1024**2, 2)


def uptime(path: Path = UPTIME) -> int | None:
    """Secondes depuis le démarrage."""
    parts = _read(path).split()
    try:
        return int(float(parts[0]))
    except (IndexError, ValueError):
        return None


class Machine:
    def __init__(self, clock=time.time) -> None:
        self.clock = clock
        self.last_message: float | None = None  # dernière question reçue (horodatage)

    def heard(self) -> None:
        self.last_message = self.clock()

    def status(self) -> dict:
        found = {"temperature": temperature(), "uptime": uptime(),
                 "last_message": self.last_message}  # fmt: skip
        mem = memory()
        if mem is not None:
            found["memory_used"], found["memory_total"] = mem
        return {k: v for k, v in found.items() if v is not None}

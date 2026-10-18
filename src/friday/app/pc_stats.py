"""Les performances du PC pour les widgets de l'écran : processeur, mémoire vive, carte
graphique (utilisation, température, mémoire vidéo) et place sur chaque disque. Tout est lu
sur le PC (psutil, nvidia-smi), rien ne sort. Une lecture prend quelques millisecondes,
nvidia-smi un peu plus : elle se fait hors du fil de l'interface (ui/desktop/side/sampler.py)."""

import logging
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field

import psutil

log = logging.getLogger(__name__)
GPU_QUERY = "name,utilization.gpu,temperature.gpu,memory.used,memory.total"
GB = 1024**3


@dataclass(frozen=True)
class Gpu:
    name: str
    load: float  # %
    temperature: int  # °C
    vram_used: int  # Mo
    vram_total: int  # Mo


@dataclass(frozen=True)
class Disk:
    name: str  # « C: »
    used: float  # Go
    total: float  # Go

    @property
    def free_share(self) -> float:
        return 1 - self.used / self.total if self.total else 0.0


@dataclass(frozen=True)
class Snapshot:
    cpu: float  # %
    ram_used: float  # Go
    ram_total: float  # Go
    gpu: Gpu | None = None
    disks: list[Disk] = field(default_factory=list)


def read_gpu(run: Callable = subprocess.run) -> Gpu | None:
    """La carte NVIDIA (la première), None sans nvidia-smi."""
    try:
        out = run(["nvidia-smi", f"--query-gpu={GPU_QUERY}", "--format=csv,noheader,nounits"],
                  capture_output=True, text=True, timeout=3,
                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout  # fmt: skip
        name, load, temp, used, total = [x.strip() for x in out.splitlines()[0].split(",")]
        return Gpu(name.removeprefix("NVIDIA ").removeprefix("GeForce "), float(load),
                   int(temp), int(used), int(total))  # fmt: skip
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None


def read_disks() -> list[Disk]:
    """Les disques fixes (ni lecteur optique ni clé USB)."""
    disks = []
    for part in psutil.disk_partitions(all=False):
        if "cdrom" in part.opts or "removable" in part.opts or not part.fstype:
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except OSError:
            continue
        disks.append(Disk(part.mountpoint.rstrip("\\/") or part.mountpoint, usage.used / GB,
                          usage.total / GB))  # fmt: skip
    return disks


class PcStats:
    """Lecteur réutilisable : après GIVE_UP échecs de suite, nvidia-smi n'est plus essayé."""

    GIVE_UP = 3

    def __init__(self, gpu: Callable[[], Gpu | None] = read_gpu,
                 disks: Callable[[], list[Disk]] = read_disks) -> None:  # fmt: skip
        self._gpu, self._disks = gpu, disks
        self._failures = 0
        psutil.cpu_percent(interval=None)  # la 1re mesure sert de point de départ

    def read(self) -> Snapshot:
        memory = psutil.virtual_memory()
        gpu = None
        if self._failures < self.GIVE_UP:
            gpu = self._gpu()
            self._failures = 0 if gpu is not None else self._failures + 1
            if self._failures == self.GIVE_UP:
                log.info("Pas de carte NVIDIA lisible (nvidia-smi) : widget carte graphique vide")
        return Snapshot(psutil.cpu_percent(interval=None), (memory.total - memory.available) / GB,
                        memory.total / GB, gpu, self._disks())  # fmt: skip

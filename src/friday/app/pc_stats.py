"""Les performances du PC pour les widgets de l'écran : processeur, mémoire vive, carte
graphique (utilisation, température, mémoire vidéo), place sur chaque disque, et le réseau
(octets envoyés et reçus, temps de réponse d'Internet). Tout est lu sur le PC (psutil,
nvidia-smi) ; seule la mesure du ping sort : une connexion ouverte puis refermée vers
1.1.1.1 (Cloudflare), sans rien envoyer, toutes les 10 s tant que la carte est affichée.
Une lecture prend quelques millisecondes, nvidia-smi un peu plus : elle se fait hors du fil
de l'interface (ui/desktop/side/sampler.py)."""

import logging
import socket
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import psutil

log = logging.getLogger(__name__)
GPU_QUERY = "name,utilization.gpu,temperature.gpu,memory.used,memory.total"
GB = 1024**3
PING_HOST, PING_EVERY = ("1.1.1.1", 443), 5  # une lecture sur 5 : toutes les 10 s


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
    sent: int = 0  # octets envoyés depuis le démarrage de Windows
    received: int = 0
    taken: float = 0.0  # instant de la lecture (time.monotonic), pour les débits
    ping: float | None = None  # ms ; None : Internet injoignable (ou pas encore mesuré)


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


def ping(host: tuple[str, int] = PING_HOST, timeout: float = 1.0) -> float | None:
    """Le temps d'ouverture d'une connexion (ms) : comme un ping, sans droits particuliers."""
    start = time.perf_counter()
    try:
        socket.create_connection(host, timeout=timeout).close()
    except OSError:
        return None
    return (time.perf_counter() - start) * 1000


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
                 disks: Callable[[], list[Disk]] = read_disks,
                 pinger: Callable[[], float | None] = ping) -> None:  # fmt: skip
        self._gpu, self._disks, self._ping = gpu, disks, pinger
        self._failures = self._reads = 0
        self._last_ping: float | None = None
        psutil.cpu_percent(interval=None)  # la 1re mesure sert de point de départ

    def read(self) -> Snapshot:
        memory = psutil.virtual_memory()
        gpu = None
        if self._failures < self.GIVE_UP:
            gpu = self._gpu()
            self._failures = 0 if gpu is not None else self._failures + 1
            if self._failures == self.GIVE_UP:
                log.info("Pas de carte NVIDIA lisible (nvidia-smi) : widget carte graphique vide")
        if self._reads % PING_EVERY == 0:
            self._last_ping = self._ping()
        self._reads += 1
        net = psutil.net_io_counters()
        return Snapshot(psutil.cpu_percent(interval=None), (memory.total - memory.available) / GB,
                        memory.total / GB, gpu, self._disks(), net.bytes_sent, net.bytes_recv,
                        time.monotonic(), self._last_ping)  # fmt: skip

"""Les cartes « PC » des colonnes de côté : processeur (avec sa courbe de la dernière minute)
et mémoire vive, carte graphique (utilisation, mémoire vidéo, température), disques (place
libre). Elles reçoivent une lecture (app/pc_stats.py) toutes les 2 s."""

from collections import deque

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QLabel, QWidget

from friday.app.pc_stats import Snapshot
from friday.ui.desktop import theme
from friday.ui.desktop.side.hud import HudCard, Meter

HISTORY = 30  # lectures gardées pour la courbe (une minute)
CPU_HIGH, RAM_HIGH, VRAM_HIGH, HOT, DISK_LOW = 90, 0.9, 0.95, 83, 0.10


def fr(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


class Sparkline(QWidget):
    """La courbe du processeur sur la dernière minute (0 à 100 %), sans axe."""

    def __init__(self) -> None:
        super().__init__()
        self.values: deque[float] = deque(maxlen=HISTORY)
        self.setFixedHeight(26)

    def add(self, value: float) -> None:
        self.values.append(value)
        self.update()

    def paintEvent(self, _event) -> None:
        if len(self.values) < 2:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height() - 2
        step = w / (HISTORY - 1)
        start = w - step * (len(self.values) - 1)
        points = [QPointF(start + i * step, 1 + h * (1 - v / 100))
                  for i, v in enumerate(self.values)]  # fmt: skip
        path = QPainterPath(points[0])
        for point in points[1:]:
            path.lineTo(point)
        accent = QColor(theme.current().accent)
        painter.setPen(QPen(accent, 1.5))
        painter.drawPath(path)
        path.lineTo(points[-1].x(), h + 1)
        path.lineTo(points[0].x(), h + 1)
        fill = QColor(accent)
        fill.setAlphaF(0.12)
        painter.fillPath(path, fill)
        painter.end()


class CpuCard(HudCard):
    def __init__(self) -> None:
        super().__init__("PC")
        self.cpu = Meter(self.body, "Processeur")
        self.curve = Sparkline()
        self.body.insertWidget(self.body.count() - 1, self.curve)  # sous la barre du processeur
        self.ram = Meter(self.body, "Mémoire")

    def show(self, s: Snapshot) -> None:
        self.cpu.show(f"{s.cpu:.0f} %", s.cpu / 100, alert=s.cpu >= CPU_HIGH)
        self.curve.add(s.cpu)
        share = s.ram_used / s.ram_total if s.ram_total else 0.0
        self.ram.show(f"{share:.0%}".replace("%", " %"), share,
                      f"{fr(s.ram_used)} / {s.ram_total:.0f} Go", share >= RAM_HIGH)  # fmt: skip


class GpuCard(HudCard):
    def __init__(self) -> None:
        super().__init__("CARTE GRAPHIQUE")
        self.load = Meter(self.body, "Utilisation")
        self.vram = Meter(self.body, "Mémoire vidéo")
        self.missing = QLabel("Aucune carte NVIDIA lisible (nvidia-smi).", objectName="HudDetail",
                              wordWrap=True)  # fmt: skip
        self.body.addWidget(self.missing)
        self.missing.hide()

    def show(self, s: Snapshot) -> None:
        gpu = s.gpu
        for meter in (self.load, self.vram):
            meter.set_visible(gpu is not None)
        self.missing.setVisible(gpu is None)
        if gpu is None:
            return
        self.load.show(f"{gpu.load:.0f} %", gpu.load / 100, f"{gpu.name} · {gpu.temperature} °C",
                       gpu.temperature >= HOT)  # fmt: skip
        share = gpu.vram_used / gpu.vram_total if gpu.vram_total else 0.0
        self.vram.show(f"{fr(gpu.vram_used / 1024)} Go", share,
                       f"sur {gpu.vram_total / 1024:.0f} Go", share >= VRAM_HIGH)  # fmt: skip


class DisksCard(HudCard):
    def __init__(self) -> None:
        super().__init__("DISQUES")
        self.meters: dict[str, Meter] = {}

    def show(self, s: Snapshot) -> None:
        for disk in s.disks:
            meter = self.meters.get(disk.name)
            if meter is None:
                meter = self.meters[disk.name] = Meter(self.body, disk.name)
            free = disk.total - disk.used
            meter.show(f"{free:.0f} Go", disk.used / disk.total if disk.total else 0.0,
                       f"libres sur {disk.total:.0f} Go", disk.free_share < DISK_LOW)  # fmt: skip
        for name, meter in self.meters.items():
            meter.set_visible(any(d.name == name for d in s.disks))

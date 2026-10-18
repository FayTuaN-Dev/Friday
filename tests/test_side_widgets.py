"""Les colonnes de côté (fenêtre agrandie) : cartes du PC, choix dans Réglages → Apparence."""

import json
import subprocess
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication

from friday.app.pc_stats import Disk, Gpu, PcStats, Snapshot, read_gpu
from friday.ui.desktop.side.columns import SidePanels
from friday.ui.desktop.side.pc_cards import CpuCard, DisksCard, GpuCard

app = QApplication.instance() or QApplication([])
GPU = Gpu("RTX 3070", 29.0, 85, 7900, 8192)
SNAP = Snapshot(42.0, 13.7, 31.9, GPU, [Disk("C:", 850.0, 931.4), Disk("D:", 362.0, 476.9)])


def test_read_gpu_parses_nvidia_smi_and_survives_its_absence():
    out = SimpleNamespace(stdout="NVIDIA GeForce RTX 3070, 29, 36, 558, 8192\n")
    assert read_gpu(lambda *a, **k: out) == Gpu("RTX 3070", 29.0, 36, 558, 8192)

    def missing(*a, **k):
        raise FileNotFoundError("nvidia-smi")

    assert read_gpu(missing) is None

    def slow(*a, **k):
        raise subprocess.TimeoutExpired("nvidia-smi", 3)

    assert read_gpu(slow) is None


def test_pc_stats_gives_up_on_gpu_after_three_failures():
    calls = []
    stats = PcStats(gpu=lambda: calls.append(1))
    stats.GIVE_UP = 3
    for _ in range(5):
        assert stats.read().gpu is None
    assert len(calls) == 3


def test_cards_show_values_and_alerts():
    cpu, gpu, disks = CpuCard(), GpuCard(), DisksCard()
    for card in (cpu, gpu, disks):
        card.show(SNAP)
    assert cpu.cpu.value.text() == "42 %" and cpu.ram.detail.text() == "13,7 / 32 Go"
    assert gpu.load.detail.text() == "RTX 3070 · 85 °C" and gpu.load.value.property("alert")
    assert gpu.vram.value.text() == "7,7 Go" and gpu.vram.bar.property("alert")  # 96 % pris
    assert disks.meters["C:"].value.text() == "81 Go" and disks.meters["C:"].bar.property("alert")
    assert not disks.meters["D:"].bar.property("alert")
    gpu.show(Snapshot(1.0, 1.0, 2.0))  # pas de carte NVIDIA
    assert gpu.missing.isVisibleTo(gpu) and not gpu.load.value.isVisibleTo(gpu)


class FakeSampler:
    def __init__(self):
        from PySide6.QtCore import QObject, Signal

        class Relay(QObject):
            read = Signal(object)

        self.relay = Relay()
        self.read = self.relay.read
        self.requests = 0

    def request(self):
        self.requests += 1

    def stop(self):
        pass


def test_panels_follow_the_appearance_toggles(tmp_path):
    from PySide6.QtWidgets import QFrame, QHBoxLayout, QWidget

    playing = QFrame()
    playing.has_track = False
    limits = QFrame()
    sampler = FakeSampler()
    side = SidePanels(playing, limits, {"gpu": False}, sampler)
    window = QWidget()
    row = QHBoxLayout(window)
    row.addWidget(side.left)
    row.addWidget(side.right)
    window.show()
    side.place(True)
    assert side.cards["pc"].isVisible() and not side.cards["gpu"].isVisible()
    assert limits.isVisible() and not playing.isVisible()
    assert sampler.requests == 1  # une lecture tout de suite
    sampler.read.emit(SNAP)
    assert side.cards["pc"].cpu.value.text() == "42 %"
    saved = {}
    side.set_enabled("claude", False, saved.update)
    assert not limits.isVisible() and saved["widgets"]["claude"] is False
    side.place(False)  # fenêtre plus agrandie : rien, et plus de lecture
    assert not side.cards["pc"].isVisible() and not side.wanted()
    window.close()


def test_appearance_page_toggles_save_the_choice(tmp_path):
    from PySide6.QtGui import QColor

    from friday.ui.desktop.settings.other_pages import AppearancePage
    from friday.ui.desktop.side.columns import WIDGETS

    chosen = []
    page = AppearancePage(QColor("#f0a83c"), lambda c: None, widgets={"disks": False},
                          set_widget=lambda k, on: chosen.append((k, on)))  # fmt: skip
    toggles = page.widgets.toggles
    assert set(toggles) == {key for key, _ in WIDGETS} and not toggles["disks"].isChecked()
    toggles["pc"].click()
    assert chosen == [("pc", False)]
    json.dumps(chosen)


def test_ping_every_fifth_read_and_offline_is_none():
    import socket

    from friday.app.pc_stats import ping

    calls = []
    stats = PcStats(pinger=lambda: calls.append(1) or 21.5)
    readings = [stats.read().ping for _ in range(6)]
    assert len(calls) == 2 and readings == [21.5] * 6  # le dernier ping, entre deux mesures
    closed = socket.socket()
    closed.bind(("127.0.0.1", 0))  # un port que personne n'écoute (sur le PC lui-même)
    port = closed.getsockname()[1]
    closed.close()
    assert ping(("127.0.0.1", port), timeout=0.5) is None


def test_net_card_shows_rates_and_slow_ping():
    from friday.ui.desktop.side.pc_cards import NetCard, rate

    assert rate(13_000_000) == "12,4 Mo/s" and rate(850_000) == "830 ko/s"
    card = NetCard()
    card.show(Snapshot(1, 1, 2, sent=1_000, received=5_000, taken=10.0, ping=18.0))
    assert card.down.value.text() == "0 ko/s"  # 1re lecture : pas encore de débit
    assert card.ping.value.text() == "18 ms" and not card.ping.value.property("alert")
    card.show(Snapshot(1, 1, 2, sent=205_800, received=26_219_400, taken=12.0, ping=210.0))
    assert card.down.value.text() == "12,5 Mo/s" and card.up.value.text() == "100 ko/s"
    assert card.ping.value.property("alert")  # lent
    card.show(Snapshot(1, 1, 2, sent=0, received=0, taken=14.0, ping=None))  # compteurs remis
    assert card.down.value.text() == "0 ko/s" and card.ping.value.text() == "—"
    assert card.ping.detail.text() == "Internet ne répond pas"

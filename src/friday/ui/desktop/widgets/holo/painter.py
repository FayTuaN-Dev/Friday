"""Le noyau holographique se dessine dans son propre fil, dans une image (QImage), et le fil de
l'interface ne fait plus qu'afficher la dernière image prête : un appel au lieu de ~1 800.

Constaté : chaque appel à Qt rend le verrou de Python, et le reprendre attend quand un autre
fil travaille (réponse de qwen, mails…) ; ~1 800 appels par image figeaient la fenêtre 300 à
750 ms. Si Friday est très occupée, c'est l'animation du noyau qui ralentit un peu, plus la
fenêtre.

Le fil du peintre ne connaît que lui-même et ses images, jamais le widget : s'il tenait la
dernière référence d'un objet Qt, Python le détruirait depuis ce fil (constaté : plantage).
"""

import threading

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter

from friday.ui.desktop.widgets.holo.layers import HoloLayers
from friday.ui.desktop.widgets.holo.scene import HoloScene


class HoloPainter(HoloLayers):
    """Dessine le noyau dans une image ; l'état du moment arrive en « instantané »."""

    def __init__(self, scene: HoloScene) -> None:
        self.scene = scene
        self._pens: dict = {}
        self.w = self.h = 0

    def render(self, snapshot: dict) -> QImage | None:
        self.__dict__.update(snapshot)  # couleur, centre, taille, rotation, éclat, étincelles…
        if self.w < 4 or self.h < 4:
            return None
        image = QImage(self.w, self.h, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        self.draw_layers(painter, snapshot["glow"])
        painter.end()
        return image


class PainterThread:
    """Le fil du peintre : il dessine le dernier instantané demandé, puis attend le suivant."""

    def __init__(self, painter: HoloPainter) -> None:
        self.painter = painter
        self.wanted: dict | None = None
        self.frame: tuple[int, QImage] | None = None  # (numéro, image)
        self.wake = threading.Event()
        self.stop = threading.Event()
        threading.Thread(target=_paint_loop, args=(self,), daemon=True, name="holo-paint").start()

    def request(self, snapshot: dict) -> None:
        self.wanted = snapshot
        self.wake.set()

    def close(self) -> None:
        self.stop.set()
        self.wake.set()


def _paint_loop(worker: PainterThread) -> None:
    number = 0
    while not worker.stop.is_set():
        worker.wake.wait(0.5)
        worker.wake.clear()
        snapshot, worker.wanted = worker.wanted, None
        if snapshot is None or worker.stop.is_set():
            continue
        try:
            image = worker.painter.render(snapshot)
        except Exception:  # une image ratée ne doit pas arrêter le noyau
            continue
        if image is not None:
            number += 1
            worker.frame = (number, image)

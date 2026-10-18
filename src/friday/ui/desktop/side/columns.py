"""Les colonnes de côté, fenêtre agrandie : à gauche les cartes du PC (processeur et mémoire,
carte graphique, disques) avec « En écoute » en bas ; à droite les limites Claude. Chaque
carte s'affiche ou non selon Réglages → Apparence (data/interface.json, « widgets »)."""

from collections.abc import Callable

from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtWidgets import QVBoxLayout, QWidget

from friday.ui.desktop.side.pc_cards import CpuCard, DisksCard, GpuCard
from friday.ui.desktop.side.sampler import Sampler

WIDGETS = (("pc", "Processeur et mémoire"), ("gpu", "Carte graphique"), ("disks", "Disques"),
           ("claude", "Limites Claude"), ("music", "En écoute (musique)"))  # fmt: skip
PC = ("pc", "gpu", "disks")
EVERY_MS = 2000


def _column() -> tuple[QWidget, QVBoxLayout]:
    column = QWidget()
    layout = QVBoxLayout(column)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)
    return column, layout


class SidePanels(QObject):
    def __init__(self, playing, limits, enabled: dict[str, bool] | None = None,
                 sampler: Sampler | None = None) -> None:  # fmt: skip
        super().__init__()
        self.playing, self.limits = playing, limits
        self.enabled = {key: True for key, _ in WIDGETS} | (enabled or {})
        self.cards = {"pc": CpuCard(), "gpu": GpuCard(), "disks": DisksCard()}
        self.left, left = _column()
        for key in PC:
            left.addWidget(self.cards[key], 0, Qt.AlignTop)
        left.addStretch(1)
        left.addWidget(playing, 0, Qt.AlignBottom)
        self.right, right = _column()
        right.addWidget(limits, 0, Qt.AlignTop)
        right.addStretch(1)
        self.wide = False
        self.sampler = sampler or Sampler()
        self.sampler.read.connect(self._show)
        self._timer = QTimer(self, interval=EVERY_MS)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self.place(False)

    def place(self, wide: bool) -> None:
        """Fenêtre agrandie (et pas de scène) : les cartes choisies ; sinon rien."""
        self.wide = wide
        for key, card in self.cards.items():
            card.setVisible(wide and self.enabled[key])
        self.limits.setVisible(wide and self.enabled["claude"])
        self.playing.setVisible(wide and self.enabled["music"] and self.playing.has_track)
        if self.wanted():
            self.sampler.request()  # tout de suite, sans attendre 2 s

    def set_enabled(self, key: str, on: bool, save: Callable[[dict], None] | None = None) -> None:
        self.enabled[key] = on
        self.place(self.wide)
        if save is not None:
            save({"widgets": dict(self.enabled)})

    def wanted(self) -> bool:
        """Une lecture du PC sert-elle ? (une carte du PC affichée, fenêtre ni réduite ni
        cachée)"""
        window = self.left.window()
        return (any(self.cards[k].isVisible() for k in PC) and window is not None
                and not window.isMinimized())  # fmt: skip

    def _tick(self) -> None:
        if self.wanted():
            self.sampler.request()

    def _show(self, snapshot) -> None:
        for card in self.cards.values():
            card.show(snapshot)

    def refresh_style(self) -> None:
        for card in self.cards.values():
            card.refresh_style()

    def close(self) -> None:
        self._timer.stop()
        self.sampler.stop()

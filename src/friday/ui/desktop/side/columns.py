"""Les colonnes de côté, fenêtre agrandie : à gauche les cartes du PC (processeur et mémoire,
carte graphique, disques) avec « En écoute » en bas ; à droite les limites Claude, Friday
(modèles chargés, mode jeu) et le Pi. Chaque carte s'affiche ou non selon Réglages →
Apparence (data/interface.json, « widgets ») ; celle du Pi seulement s'il est réglé."""

from collections.abc import Callable

from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtWidgets import QVBoxLayout, QWidget

from friday.ui.desktop.side.friday_cards import FridayCard, PiCard
from friday.ui.desktop.side.pc_cards import CpuCard, DisksCard, GpuCard
from friday.ui.desktop.side.sampler import Sampler

WIDGETS = (("pc", "Processeur et mémoire"), ("gpu", "Carte graphique"), ("disks", "Disques"),
           ("claude", "Limites Claude"), ("friday", "Friday (modèles chargés, mode jeu)"),
           ("pi", "Le Pi"), ("music", "En écoute (musique)"))  # fmt: skip
PC, STATUS = ("pc", "gpu", "disks"), ("friday", "pi")
EVERY_MS, STATUS_EVERY = 2000, 5  # le PC toutes les 2 s ; Friday et le Pi toutes les 10 s


def status_sampler(settings) -> Sampler:
    """L'état de Friday et du Pi, lu dans son propre fil."""

    def make():
        from friday.app.friday_status import from_settings

        return from_settings(settings).read

    return Sampler(make, "friday-status")


def whisper_text(settings) -> str:
    if not getattr(settings, "stt_enabled", False):
        return ""
    device = "carte graphique" if settings.stt_device == "cuda" else "processeur"
    return f"{settings.stt_model} ({device})"


def _column() -> tuple[QWidget, QVBoxLayout]:
    column = QWidget()
    layout = QVBoxLayout(column)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)
    return column, layout


class SidePanels(QObject):
    def __init__(self, playing, limits, enabled: dict[str, bool] | None = None,
                 sampler: Sampler | None = None, status: Sampler | None = None,
                 toggle_game: Callable[[], None] | None = None,
                 whisper: str = "") -> None:  # fmt: skip
        """`status` : lit l'état de Friday et du Pi (app/friday_status.py) ; sans lui, pas de
        cartes Friday ni Pi."""
        super().__init__()
        self.playing, self.limits = playing, limits
        self.enabled = {key: True for key, _ in WIDGETS} | (enabled or {})
        self.cards = {"pc": CpuCard(), "gpu": GpuCard(), "disks": DisksCard(),
                      "friday": FridayCard(toggle_game, whisper), "pi": PiCard()}  # fmt: skip
        self.pi_configured = False  # appris à la 1re lecture
        self.left, left = _column()
        for key in PC:
            left.addWidget(self.cards[key], 0, Qt.AlignTop)
        left.addStretch(1)
        left.addWidget(playing, 0, Qt.AlignBottom)
        self.right, right = _column()
        right.addWidget(limits, 0, Qt.AlignTop)
        for key in STATUS:
            right.addWidget(self.cards[key], 0, Qt.AlignTop)
        right.addStretch(1)
        self.wide, self._ticks = False, 0
        self.sampler = sampler or Sampler()
        self.sampler.read.connect(self._show)
        self.status = status
        if status is not None:
            status.read.connect(self._show_status)
        self._timer = QTimer(self, interval=EVERY_MS)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self.place(False)

    def place(self, wide: bool) -> None:
        """Fenêtre agrandie (et pas de scène) : les cartes choisies ; sinon rien."""
        self.wide = wide
        for key, card in self.cards.items():
            card.setVisible(wide and self.enabled[key] and self._available(key))
        self.limits.setVisible(wide and self.enabled["claude"])
        self.playing.setVisible(wide and self.enabled["music"] and self.playing.has_track)
        if self.wanted():
            self.sampler.request()  # tout de suite, sans attendre 2 s
        if self.wanted(STATUS):
            self.status.request()

    def _available(self, key: str) -> bool:
        if key == "pi":
            return self.status is not None and self.pi_configured
        return key != "friday" or self.status is not None

    def set_enabled(self, key: str, on: bool, save: Callable[[dict], None] | None = None) -> None:
        self.enabled[key] = on
        self.place(self.wide)
        if save is not None:
            save({"widgets": dict(self.enabled)})

    def wanted(self, keys=PC) -> bool:
        """Une lecture sert-elle ? (une de ces cartes affichée, fenêtre ni réduite ni cachée)
        Friday et le Pi : aussi tant que l'on ne sait pas si le Pi est réglé."""
        window = self.left.window()
        if window is None or window.isMinimized() or not self.wide:
            return False
        if keys == STATUS:
            return self.status is not None and (
                any(self.cards[k].isVisible() for k in keys)
                or (self.enabled["pi"] and not self.pi_configured))  # fmt: skip
        return any(self.cards[k].isVisible() for k in keys)

    def _tick(self) -> None:
        self._ticks += 1
        if self.wanted():
            self.sampler.request()
        if self._ticks % STATUS_EVERY == 0 and self.wanted(STATUS):
            self.status.request()

    def _show(self, snapshot) -> None:
        for key in PC:
            self.cards[key].show(snapshot)

    def _show_status(self, status) -> None:
        for key in STATUS:
            self.cards[key].show_status(status)
        if status.pi_configured != self.pi_configured:
            self.pi_configured = status.pi_configured
            self.place(self.wide)

    def set_state(self, state) -> None:
        self.cards["friday"].set_state(state)

    def refresh_style(self) -> None:
        for card in self.cards.values():
            card.refresh_style()

    def close(self) -> None:
        self._timer.stop()
        self.sampler.stop()
        if self.status is not None:
            self.status.stop()

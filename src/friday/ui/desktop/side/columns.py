"""Les colonnes de côté, fenêtre agrandie. À gauche : les cartes du PC (processeur et mémoire,
carte graphique, disques, réseau), puis Trading (cours, annonce, dernier setup, semaine), avec « En
écoute » en bas. À droite : les limites Claude, Friday (modèles chargés, mode jeu), le Pi,
Aujourd'hui (agenda, mails, rappels) et Concentration. Chaque carte s'affiche ou non selon
Réglages → Apparence (data/interface.json, « widgets ») ; celles qui dépendent de Friday
chargée (glances.py) ou du Pi réglé, seulement une fois qu'elles ont de quoi s'afficher."""

from collections.abc import Callable

from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtWidgets import QVBoxLayout, QWidget

from friday.ui.desktop.side.day_cards import DayCard, FocusCard
from friday.ui.desktop.side.friday_cards import FridayCard, PiCard
from friday.ui.desktop.side.glances import GlanceMixin
from friday.ui.desktop.side.pc_cards import CpuCard, DisksCard, GpuCard, NetCard
from friday.ui.desktop.side.sampler import Sampler
from friday.ui.desktop.side.trading_card import TradingCard

WIDGETS = (("pc", "Processeur et mémoire"), ("gpu", "Carte graphique"), ("disks", "Disques"),
           ("net", "Réseau (débits, ping)"),
           ("claude", "Limites Claude"), ("friday", "Friday (modèles chargés, mode jeu)"),
           ("pi", "Le Pi"), ("trading", "Trading (cours, annonce, setup, semaine)"),
           ("day", "Aujourd'hui (agenda, mails, rappels)"),
           ("focus", "Concentration (25 min, puis pause)"),
           ("music", "En écoute (musique)"))  # fmt: skip
PC, STATUS = ("pc", "gpu", "disks", "net"), ("friday", "pi")
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


class SidePanels(GlanceMixin, QObject):
    def __init__(self, playing, limits, enabled: dict[str, bool] | None = None,
                 sampler: Sampler | None = None, status: Sampler | None = None,
                 toggle_game: Callable[[], None] | None = None, whisper: str = "",
                 open_trading: Callable[[str], None] | None = None,
                 ring: Callable[[str], None] | None = None) -> None:  # fmt: skip
        """`status` : lit l'état de Friday et du Pi (app/friday_status.py) ; sans lui, pas de
        cartes Friday ni Pi. `ring(texte)` : la fin d'un tour de concentration."""
        super().__init__()
        self.playing, self.limits = playing, limits
        self.enabled = {key: True for key, _ in WIDGETS} | (enabled or {})
        self.cards = {"pc": CpuCard(), "gpu": GpuCard(), "disks": DisksCard(), "net": NetCard(),
                      "friday": FridayCard(toggle_game, whisper), "pi": PiCard(),
                      "trading": TradingCard(open_trading), "day": DayCard(),
                      "focus": FocusCard(ring)}  # fmt: skip
        self.pi_configured = False  # appris à la 1re lecture
        self.left, left = _column()
        for key in (*PC, "trading"):
            left.addWidget(self.cards[key], 0, Qt.AlignTop)
        left.addStretch(1)
        left.addWidget(playing, 0, Qt.AlignBottom)
        self.right, right = _column()
        right.addWidget(limits, 0, Qt.AlignTop)
        for key in (*STATUS, "day", "focus"):
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
        """Fenêtre agrandie (et pas de scène) : les cartes choisies ; sinon rien. Appelée
        souvent (« En écoute » prévient toutes les 1,5 s) : seules les cartes qui VIENNENT
        d'apparaître sont lues tout de suite ; les autres gardent leur rythme (constaté :
        Google et les cours relus toutes les 1,5 s, la carte « sautait »)."""
        was_wide, self.wide = self.wide, wide
        shown = {key for key, card in self.cards.items() if card.isVisible()}
        for key, card in self.cards.items():
            card.setVisible(wide and self.enabled[key] and self._available(key))
        self.limits.setVisible(wide and self.enabled["claude"])
        self.playing.setVisible(wide and self.enabled["music"] and self.playing.has_track)
        new = {key for key, card in self.cards.items() if card.isVisible()} - shown
        if new & set(PC) and self.wanted():
            self.sampler.request()  # tout de suite, sans attendre 2 s
        if (new & set(STATUS) or (wide and not was_wide)) and self.wanted(STATUS):
            self.status.request()
        self._glance_tick(new)

    def _available(self, key: str) -> bool:
        if key == "pi":
            return self.status is not None and self.pi_configured
        if key == "friday":
            return self.status is not None
        if key == "trading":
            return self.glance is not None
        if key == "day":
            return getattr(self, "_has_day", False)
        return True

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
        self._glance_tick(set(), self._ticks)

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
        self._stop_glances()

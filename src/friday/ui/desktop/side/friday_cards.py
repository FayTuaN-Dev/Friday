"""Les cartes « Friday » et « Pi » des colonnes de côté. Friday : son état, les modèles chargés
(mémoire vidéo prise, en rouge s'ils débordent sur le processeur), Whisper, et le bouton du
mode jeu. Pi : en ligne ou non, température, mémoire, depuis quand il tourne et la dernière
question reçue. Elles reçoivent un Status (app/friday_status.py) toutes les 5 s."""

import time
from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton

from friday.app.events import AssistantState
from friday.app.friday_status import Status
from friday.ui.desktop import theme
from friday.ui.desktop.side.hud import HudCard, Meter, _flag, tint
from friday.ui.desktop.side.pc_cards import fr, pct

PI_HOT, MAX_MODELS = 75, 3


def duration(seconds: float) -> str:
    """« 12 min », « 3 h 05 », « 2 j 4 h »."""
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{max(minutes, 1)} min"
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours} h {minutes:02d}"
    days, hours = divmod(hours, 24)
    return f"{days} j {hours} h"


def _line(card: HudCard, name: str) -> QLabel:
    row = QHBoxLayout()
    row.addWidget(QLabel(name, objectName="HudName"), 1, Qt.AlignBottom)
    value = QLabel(objectName="HudValue", alignment=Qt.AlignRight | Qt.AlignVCenter)
    row.addWidget(value)
    card.body.addLayout(row)
    card.body.addSpacing(5)
    return value


class FridayCard(HudCard):
    def __init__(self, toggle_game: Callable[[], None] | None = None, whisper: str = "") -> None:
        super().__init__("FRIDAY")
        self.state = _line(self, "ÉTAT")
        self.models = [Meter(self.body, "") for _ in range(MAX_MODELS)]
        self.note = QLabel(objectName="HudDetail", wordWrap=True)
        self.body.addWidget(self.note)
        self.whisper = whisper
        self.game = QPushButton("Mode jeu", objectName="SettingsSmall")
        self.game.setFocusPolicy(Qt.NoFocus)
        self.game.setToolTip("Rend la carte graphique au jeu (« Friday reviens » pour revenir)")
        if toggle_game is not None:
            self.game.clicked.connect(toggle_game)
        self.body.addSpacing(4)
        self.body.addWidget(self.game, 0, Qt.AlignLeft)
        self.show_status(Status([]))

    def set_state(self, state: AssistantState) -> None:
        self.state.setText(state.value)
        tint(self.state, f"color: {theme.current().states[state]};")
        self.game.setText("Revenir" if state is AssistantState.PAUSED else "Mode jeu")

    def show_status(self, status: Status) -> None:
        models = status.models or []
        for meter, model in zip(self.models, models, strict=False):
            meter.name.setText(model.name.upper())
            spill = model.on_gpu < 0.99
            detail = (f"{pct(1 - model.on_gpu)} sur le processeur : Friday ralentit" if spill
                      else "sur la carte graphique")  # fmt: skip
            meter.show(f"{fr(model.vram)} Go", model.on_gpu, detail, spill)
        for n, meter in enumerate(self.models):
            meter.set_visible(n < len(models))
        notes = []
        if status.models is None:
            notes.append("Ollama ne répond pas.")
        elif not models:
            notes.append("Aucun modèle chargé (libéré, ou mode jeu).")
        if self.whisper:
            notes.append(f"Écoute : Whisper {self.whisper}")
        self.note.setText("\n".join(notes))


class PiCard(HudCard):
    def __init__(self, clock=time.time) -> None:
        super().__init__("PI")
        self.clock = clock
        self.online = _line(self, "LIAISON")
        self.temperature = Meter(self.body, "Température")
        self.memory = Meter(self.body, "Mémoire")
        self.detail = QLabel(objectName="HudDetail", wordWrap=True)
        self.body.addWidget(self.detail)

    def show_status(self, status: Status) -> None:
        pi = status.pi
        self.online.setText("EN LIGNE" if pi is not None else "HORS LIGNE")
        _flag(self.online, pi is None)
        found = pi or {}
        temp, used, total = (found.get(k) for k in ("temperature", "memory_used", "memory_total"))
        self.temperature.set_visible(temp is not None)
        if temp is not None:
            self.temperature.show(f"{temp:.0f} °C", temp / 85, alert=temp >= PI_HOT)
        self.memory.set_visible(bool(used and total))
        if used and total:
            self.memory.show(pct(used / total), used / total,
                             f"{fr(used)} / {total:.0f} Go")  # fmt: skip
        self.detail.setText(self._detail(pi))

    def _detail(self, pi: dict | None) -> str:
        if pi is None:
            return "Le Pi ne répond pas (éteint, ou réseau coupé)."
        parts = []
        if pi.get("uptime"):
            parts.append(f"allumé depuis {duration(pi['uptime'])}")
        if pi.get("last_message"):
            parts.append(f"dernière question il y a {duration(self.clock() - pi['last_message'])}")
        else:
            parts.append("aucune question depuis son démarrage")
        return " · ".join(parts).capitalize()

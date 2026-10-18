"""Les cartes « Aujourd'hui » et « Concentration » des colonnes de côté (W4).

Aujourd'hui : les prochains rendez-vous (agenda Google), les mails non lus et leurs derniers
expéditeurs, les rappels à venir (dans combien de temps). Concentration : 25 min de travail
puis 5 min de pause ; à chaque fin, un carillon et une bulle Windows (`ring`)."""

from collections.abc import Callable
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton

from friday.app.day_glance import Day
from friday.ui.desktop.side.friday_cards import duration
from friday.ui.desktop.side.hud import HudCard, Meter

WORK, BREAK = 25 * 60, 5 * 60
MAX_REMINDERS = 3


def event_line(event, now: datetime) -> str:
    day = "" if event.start.date() == now.date() else "demain "
    when = "toute la journée" if event.all_day else f"{event.start:%H:%M}"
    return f"{day}{when} · {event.title}"


class DayCard(HudCard):
    def __init__(self) -> None:
        super().__init__("AUJOURD'HUI")
        self.agenda = self._section("AGENDA")
        self.mails = self._section("MAILS")
        self.reminders = self._section("RAPPELS")

    def _section(self, title: str) -> QLabel:
        head = QLabel(title, objectName="HudName")
        text = QLabel(objectName="HudDetail", wordWrap=True)
        self.body.addWidget(head)
        self.body.addWidget(text)
        self.body.addSpacing(4)
        return text

    def show_day(self, day: Day, now: datetime | None = None) -> None:
        now = now or datetime.now()
        if not day.connected:
            self.agenda.setText("Compte Google non connecté (Réglages → Comptes).")
            self.mails.setText("—")
            return
        self.agenda.setText("\n".join(event_line(e, now) for e in day.events)
                            or "Rien de prévu d'ici demain soir.")  # fmt: skip
        if day.unread is None:
            self.mails.setText("Nombre de non lus inconnu.")
        elif not day.unread:
            self.mails.setText("Aucun mail non lu.")
        else:
            senders = f" · {', '.join(day.senders)}" if day.senders else ""
            self.mails.setText(f"{day.unread} non lu{'s' if day.unread > 1 else ''}{senders}")

    def show_reminders(self, reminders, now: datetime | None = None) -> None:
        """Les rappels en attente (AgendaStore.pending), les plus proches d'abord."""
        now = now or datetime.now()
        lines = []
        for r in reminders[:MAX_REMINDERS]:
            wait = (r.due_at - now).total_seconds()
            when = (f"dans {duration(wait)}" if 0 < wait < 86400
                    else "maintenant" if wait <= 0 else f"{r.due_at:%d/%m à %H:%M}")  # fmt: skip
            lines.append(f"{r.text} · {when}")
        more = len(reminders) - MAX_REMINDERS
        if more > 0:
            lines.append(f"… et {more} autre{'s' if more > 1 else ''}")
        self.reminders.setText("\n".join(lines) or "Aucun rappel.")


class FocusCard(HudCard):
    def __init__(self, ring: Callable[[str], None] | None = None) -> None:
        super().__init__("CONCENTRATION")
        self.ring = ring
        self.meter = Meter(self.body, "Prêt")
        self.message = QLabel(objectName="HudDetail", wordWrap=True)
        self.body.addWidget(self.message)
        self.message.hide()
        self.left = 0  # secondes restantes
        self.phase = ""  # « travail », « pause » ou rien
        row = QHBoxLayout()
        self.start = QPushButton("Démarrer 25 min", objectName="SettingsSmall")
        self.stop = QPushButton("Arrêter", objectName="SettingsSmall")
        for button in (self.start, self.stop):
            button.setFocusPolicy(Qt.NoFocus)
            row.addWidget(button)
        row.addStretch(1)
        self.body.addLayout(row)
        self.start.clicked.connect(lambda: self.begin("travail"))
        self.stop.clicked.connect(self.end)
        self.timer = QTimer(self, interval=1000)
        self.timer.timeout.connect(self.tick)
        self._show()

    def begin(self, phase: str) -> None:
        if phase == "travail":
            self.message.hide()
        self.phase, self.left = phase, WORK if phase == "travail" else BREAK
        self.timer.start()
        self._show()

    def end(self) -> None:
        self.phase, self.left = "", 0
        self.timer.stop()
        self._show()

    def tick(self) -> None:
        self.left -= 1
        if self.left > 0:
            self._show()
            return
        if self.phase == "travail":
            self._ring("25 minutes de concentration : bravo ! Pause de 5 minutes.")
            self.begin("pause")
        else:
            self._ring("Fin de la pause : prêt pour un autre tour ?")
            self.end()

    def _ring(self, text: str) -> None:
        self.message.setText(text)
        self.message.show()
        if self.ring is not None:
            self.ring(text)

    def _show(self) -> None:
        total = WORK if self.phase == "travail" else BREAK
        minutes, seconds = divmod(max(self.left, 0), 60)
        name = {"travail": "Travail", "pause": "Pause"}.get(self.phase, "Prêt")
        self.meter.name.setText(name.upper())
        self.meter.show(f"{minutes:02d}:{seconds:02d}" if self.phase else "25:00",
                        1 - self.left / total if self.phase else 0.0)  # fmt: skip
        self.start.setVisible(not self.phase)
        self.stop.setVisible(bool(self.phase))

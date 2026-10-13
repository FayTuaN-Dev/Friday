"""Écran d'accueil (U2), dans le fil de discussion tant qu'il est vide : salutation selon
l'heure, date du jour, coup d'œil sur la journée, et des suggestions à cliquer (chacune est
envoyée comme si elle avait été tapée)."""

import threading
from collections.abc import Callable
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget

DAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
          "septembre", "octobre", "novembre", "décembre"]  # fmt: skip
# (texte du bouton, demande envoyée à Friday)
BRIEFING = ("☕  Briefing du matin", "Fais-moi le briefing du matin")
WEATHER = ("☀️  La météo", "Quel temps fait-il ?")
MAILS = ("✉️  Mes mails non lus", "Ai-je des mails non lus ?")
WORLD = ("🌍  Le monde en direct", "Montre-moi le monde")
MUSIC = ("🎵  Musique chill", "Mets de la musique chill")
TOMORROW = ("📅  Agenda de demain", "Qu'ai-je à l'agenda demain ?")
# Selon le moment de la journée : ce qu'on demande le plus souvent à cette heure-là
SUGGESTIONS = {
    "matin": [BRIEFING, WEATHER, MAILS, WORLD],
    "journée": [MAILS, WEATHER, WORLD, MUSIC],
    "soir": [TOMORROW, MUSIC, MAILS, WORLD],
}


def moment(now: datetime) -> str:
    return "matin" if 5 <= now.hour < 12 else "journée" if 12 <= now.hour < 18 else "soir"


def greeting(now: datetime, name: str) -> str:
    return f"{'Bonsoir' if moment(now) == 'soir' else 'Bonjour'}, {name}."


def today(now: datetime) -> str:
    return f"{DAYS[now.weekday()]} {now.day} {MONTHS[now.month - 1]}".capitalize()


class Welcome(QWidget):
    chosen = Signal(str)  # la suggestion cliquée, comme si elle avait été tapée

    def __init__(self, name: str = "Monsieur", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.name = name
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        self.greeting = QLabel(objectName="WelcomeGreeting", alignment=Qt.AlignCenter)
        self.date = QLabel(objectName="WelcomeDate", alignment=Qt.AlignCenter)
        self.glance = QLabel(objectName="WelcomeGlance", alignment=Qt.AlignCenter,
                             wordWrap=True)  # fmt: skip
        for label in (self.greeting, self.date, self.glance):
            layout.addWidget(label)
        layout.addSpacing(10)
        grid = QGridLayout()
        grid.setSpacing(8)
        layout.addLayout(grid)
        self.suggestions = []  # quatre boutons, dont le texte suit le moment de la journée
        for n in range(4):
            button = QPushButton(objectName="Suggestion", cursor=Qt.PointingHandCursor)
            button.clicked.connect(lambda _=False, b=button: self.chosen.emit(b.toolTip()))
            grid.addWidget(button, n // 2, n % 2)
            self.suggestions.append(button)
        self.set_glance("")
        self.refresh()

    def refresh(self, now: datetime | None = None) -> None:
        """Salutation, date et suggestions du moment (au démarrage et à chaque remise à zéro)."""
        now = now or datetime.now()
        self.greeting.setText(greeting(now, self.name))
        self.date.setText(today(now))
        for button, (text, request) in zip(self.suggestions, SUGGESTIONS[moment(now)],
                                           strict=True):  # fmt: skip
            button.setText(text)
            button.setToolTip(request)  # la demande exacte, montrée au survol

    def set_glance(self, text: str) -> None:
        self.glance.setText(text)
        self.glance.setVisible(bool(text))

    def load_glance(self, fetch: Callable[[], str]) -> None:
        """Le coup d'œil (agenda, mails : réseau) se prépare dans un fil ; une minuterie
        relève le résultat. Le fil ne tient jamais le widget (constaté avec le Diagnostic :
        un fil qui tenait la dernière référence détruisait la page hors de l'interface)."""
        box: list[str] = []

        def work() -> None:
            try:
                box.append(fetch())
            except Exception:
                box.append("")

        threading.Thread(target=work, daemon=True, name="welcome-glance").start()
        timer = QTimer(self, interval=200)

        def collect() -> None:
            if box:
                timer.stop()
                timer.deleteLater()
                self.set_glance(box[0])

        timer.timeout.connect(collect)
        timer.start()

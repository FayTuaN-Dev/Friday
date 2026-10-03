"""Lancement de l'application de bureau (uv run jarvis)."""

import sys

from PySide6.QtWidgets import QApplication

from jarvis.core.config import Settings
from jarvis.ui.desktop.main_window import MainWindow
from jarvis.ui.desktop.theme import stylesheet


def run(settings: Settings) -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Jarvis")
    app.setStyleSheet(stylesheet())
    window = MainWindow(settings)
    window.show()
    # Les modèles se chargent en arrière-plan : la fenêtre s'affiche tout de suite.
    window.assistant.start()
    sys.exit(app.exec())

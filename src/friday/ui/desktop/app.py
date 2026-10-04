"""Lancement de l'application de bureau (uv run friday)."""

import sys

from PySide6.QtWidgets import QApplication

from friday.core.config import Settings
from friday.ui.desktop.main_window import MainWindow


def run(settings: Settings) -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Friday")
    window = MainWindow(settings)  # applique aussi le thème (couleur choisie)
    window.show()
    # Les modèles se chargent en arrière-plan : la fenêtre s'affiche tout de suite.
    window.assistant.start()
    sys.exit(app.exec())

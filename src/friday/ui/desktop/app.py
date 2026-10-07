"""Lancement de l'application de bureau (uv run friday)."""

import logging
import sys

from PySide6.QtWidgets import QApplication

from friday.core.config import Settings
from friday.ui.desktop.main_window import MainWindow


def log_uncaught(kind, error, trace) -> None:
    """Une erreur dans l'interface (slot Qt) n'allait que dans la console : on la garde."""
    logging.getLogger("friday.ui").error("Erreur dans l'interface", exc_info=(kind, error, trace))


def run(settings: Settings) -> None:
    sys.excepthook = log_uncaught
    app = QApplication(sys.argv)
    app.setApplicationName("Friday")
    window = MainWindow(settings)  # applique aussi le thème (couleur choisie)
    window.show()
    # Les modèles se chargent en arrière-plan : la fenêtre s'affiche tout de suite.
    window.assistant.start()
    sys.exit(app.exec())

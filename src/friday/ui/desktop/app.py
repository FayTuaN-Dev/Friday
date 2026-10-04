"""Lancement de l'application de bureau (uv run friday)."""

import sys

from PySide6.QtWidgets import QApplication

from friday.core.config import Settings
from friday.ui.desktop.main_window import MainWindow
from friday.ui.desktop.theme import link_palette, stylesheet


def run(settings: Settings) -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Friday")
    app.setStyleSheet(stylesheet())
    link_palette(app)
    window = MainWindow(settings)
    window.show()
    # Les modèles se chargent en arrière-plan : la fenêtre s'affiche tout de suite.
    window.assistant.start()
    sys.exit(app.exec())

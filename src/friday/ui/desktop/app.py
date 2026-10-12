"""Lancement de l'application de bureau (uv run friday)."""

import logging
import sys

from PySide6.QtWidgets import QApplication

from friday.core.config import Settings
from friday.ui.desktop.main_window import MainWindow

# Toutes les 0,5 ms (au lieu de 5), Python passe la main d'un fil à l'autre. Constaté : à
# chaque appel à Qt, l'interface rend le verrou de Python et doit le reprendre ; si un autre
# fil travaille (réponse de qwen, mails, recherche…), chaque reprise coûtait jusqu'à 5 ms.
# Le noyau holographique (~2 000 appels à Qt par image) passait de 11 à 358 ms par image,
# d'où les gels ; à 0,5 ms : 30 ms. Sans effet mesurable sur les autres calculs.
SWITCH_INTERVAL = 0.0005


def keep_interface_responsive() -> None:
    sys.setswitchinterval(SWITCH_INTERVAL)


def log_uncaught(kind, error, trace) -> None:
    """Une erreur dans l'interface (slot Qt) n'allait que dans la console : on la garde."""
    logging.getLogger("friday.ui").error("Erreur dans l'interface", exc_info=(kind, error, trace))


def run(settings: Settings) -> None:
    sys.excepthook = log_uncaught
    keep_interface_responsive()
    app = QApplication(sys.argv)
    app.setApplicationName("Friday")
    window = MainWindow(settings)  # applique aussi le thème (couleur choisie)
    window.show()
    # Les modèles se chargent en arrière-plan : la fenêtre s'affiche tout de suite.
    window.assistant.start()
    sys.exit(app.exec())

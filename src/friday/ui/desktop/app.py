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


def preload_voice(settings: Settings) -> None:
    """Le travail lourd qui figeait la fenêtre (voix : ~2,3 s + 1,5 s pour sa 1re phrase) est
    fait AVANT de l'afficher (S2) : elle apparaît un peu plus tard, mais fluide."""
    if not settings.tts_enabled:
        return
    from friday.core.config import VOICES_DIR
    from friday.voice.tts import load_voice

    try:
        load_voice(settings.tts_voice, VOICES_DIR, settings.tts_speed, settings.tts_speaker)
    except Exception:  # elle sera réessayée (et signalée) pendant le chargement de Friday
        logging.getLogger("friday").exception("Voix non préchargée")


def log_uncaught(kind, error, trace) -> None:
    """Une erreur dans l'interface (slot Qt) n'allait que dans la console : on la garde."""
    logging.getLogger("friday.ui").error("Erreur dans l'interface", exc_info=(kind, error, trace))


def run(settings: Settings, tray: bool = False) -> None:
    """`tray` : lancée avec Windows, Friday démarre cachée dans l'icône près de l'horloge."""
    sys.excepthook = log_uncaught
    keep_interface_responsive()
    app = QApplication(sys.argv)
    app.setApplicationName("Friday")
    from friday.ui.desktop.single_instance import InstanceServer, wake_running

    if wake_running():  # déjà lancée (avec Windows) : elle se montre, celle-ci s'arrête
        logging.getLogger("friday").info("Friday tourne déjà : sa fenêtre est ramenée devant")
        return
    app.setQuitOnLastWindowClosed(False)  # la croix cache Friday, elle continue de tourner
    # Tout de suite : une 2e Friday lancée pendant la préparation la trouve déjà
    instances = InstanceServer()
    from friday.core import autostart

    autostart.sync(settings.start_with_windows)
    preload_voice(settings)
    window = MainWindow(settings)  # applique aussi le thème (couleur choisie)
    instances.setParent(window)
    instances.show_requested.connect(window.notifier.bring_back)
    window.scene_layer.warm_map()  # moteur web de la carte (~0,5 s)
    window.prepare_settings()  # panneau des réglages (~0,6 s)
    if not tray:
        window.show()
    # Les modèles (qwen, Whisper) se chargent ensuite en arrière-plan, fenêtre affichée.
    window.assistant.start()
    sys.exit(app.exec())

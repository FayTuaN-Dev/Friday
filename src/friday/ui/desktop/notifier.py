"""Notifications Windows : quand une tâche de fond se termine et que Friday n'est pas au
premier plan (réduite, derrière TradingView…), une bulle Windows apparaît. Un clic sur la
bulle (ou sur l'icône près de l'horloge) ramène Friday devant. Qt les affiche via une icône
de la zone de notification : elle reste visible tant que Friday tourne."""

from PySide6.QtWidgets import QSystemTrayIcon, QWidget

from friday.tools.base import Display

SHOWN_MS = 8000


class Notifier:
    def __init__(self, window: QWidget, icon) -> None:
        self.window = window
        self.tray = QSystemTrayIcon(icon, window) if QSystemTrayIcon.isSystemTrayAvailable() \
            else None  # fmt: skip
        if self.tray is not None:
            self.tray.setToolTip("Friday")
            self.tray.messageClicked.connect(self.bring_back)
            self.tray.activated.connect(lambda reason: self.bring_back())
            self.tray.show()
        self.sent: list[tuple[str, str]] = []  # (titre, texte), pour les tests

    def in_front(self) -> bool:
        return self.window.isActiveWindow() and not self.window.isMinimized()

    def notify(self, display: Display) -> bool:
        """Affiche la bulle si Friday n'est pas au premier plan ; renvoie True si affichée."""
        if self.in_front():
            return False
        text = display.data.get("text", "")
        self.sent.append((display.title, text))
        if self.tray is not None:
            self.tray.showMessage(display.title, text, QSystemTrayIcon.Information, SHOWN_MS)
        return True

    def bring_back(self) -> None:
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

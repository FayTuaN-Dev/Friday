"""Notifications Windows : quand une tâche de fond se termine et que Friday n'est pas au
premier plan (réduite, derrière TradingView…), une bulle Windows apparaît. Un clic sur la
bulle (ou sur l'icône près de l'horloge) ramène Friday devant. Qt les affiche via une icône
de la zone de notification : elle reste visible tant que Friday tourne."""

from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from friday.tools.base import Display

SHOWN_MS = 8000


class Notifier:
    def __init__(self, window: QWidget, icon, on_game=None, game_icon=None) -> None:
        """`on_game` : « Mode jeu » / « Reprendre » du menu (G3) ; `game_icon` : l'icône
        montrée pendant le mode jeu."""
        self.window = window
        self.icons = (icon, game_icon or icon)
        self.tray = QSystemTrayIcon(icon, window) if QSystemTrayIcon.isSystemTrayAvailable() \
            else None  # fmt: skip
        if self.tray is not None:
            self.tray.setToolTip("Friday")
            self.tray.messageClicked.connect(self.bring_back)
            self.tray.activated.connect(self._clicked)
            self.menu = QMenu(window)
            self.game_action = self.menu.addAction("🎮  Mode jeu", on_game or (lambda: None))
            self.menu.addAction("Ouvrir Friday", self.bring_back)
            self.menu.addSeparator()
            self.menu.addAction("Quitter Friday", window.close)
            self.tray.setContextMenu(self.menu)
            self.tray.show()
        self.sent: list[tuple[str, str]] = []  # (titre, texte), pour les tests

    def _clicked(self, reason) -> None:
        if reason != QSystemTrayIcon.Context:  # clic droit : le menu, pas la fenêtre
            self.bring_back()

    def set_game(self, on: bool) -> None:
        """Mode jeu (G3) : l'icône change, l'infobulle et le menu disent comment revenir."""
        if self.tray is None:
            return
        self.tray.setIcon(self.icons[on])
        self.tray.setToolTip("Friday · mode jeu (« Friday, reviens » ou double clap)" if on
                             else "Friday")  # fmt: skip
        self.game_action.setText("▶  Reprendre Friday" if on else "🎮  Mode jeu")

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

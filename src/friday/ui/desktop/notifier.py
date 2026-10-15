"""Notifications Windows : quand une tâche de fond se termine et que Friday n'est pas au
premier plan (réduite, derrière TradingView…), une bulle Windows apparaît. Un clic sur la
bulle (ou sur l'icône près de l'horloge) ramène Friday devant. Qt les affiche via une icône
de la zone de notification : elle reste visible tant que Friday tourne."""

from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from friday.tools.base import Display

SHOWN_MS = 8000


class Notifier:
    def __init__(self, window: QWidget, icon, on_game=None, game_icon=None,
                 on_globe=None) -> None:  # fmt: skip
        """`on_game` : « Mode jeu » / « Reprendre » du menu (G3) ; `game_icon` : l'icône
        montrée pendant le mode jeu ; `on_globe` : « Œil de Dieu » du menu."""
        self.window = window
        self.icons = (icon, game_icon or icon)
        self._game = self._loading = self._globe = False
        self.tray = QSystemTrayIcon(icon, window) if QSystemTrayIcon.isSystemTrayAvailable() \
            else None  # fmt: skip
        if self.tray is not None:
            self.tray.setToolTip("Friday")
            self.tray.messageClicked.connect(self.bring_back)
            self.tray.activated.connect(self._clicked)
            self.menu = QMenu(window)
            self.game_action = self.menu.addAction("🎮  Mode jeu", on_game or (lambda: None))
            self.globe_action = self.menu.addAction("🌍  Œil de Dieu", on_globe or (lambda: None))
            self.menu.addAction("Ouvrir Friday", self.bring_back)
            self.menu.addSeparator()
            self.menu.addAction("Quitter Friday", getattr(window, "quit_friday", window.close))
            self.tray.setContextMenu(self.menu)
            self.tray.show()
        self.sent: list[tuple[str, str]] = []  # (titre, texte), pour les tests
        self._told_hidden = False

    def _clicked(self, reason) -> None:
        if reason != QSystemTrayIcon.Context:  # clic droit : le menu, pas la fenêtre
            self.bring_back()

    def set_game(self, on: bool) -> None:
        """Mode jeu (G3) : l'icône change, l'infobulle et le menu disent comment revenir."""
        if self.tray is None:
            return
        self._game = on
        self.tray.setIcon(self.icons[on])
        self._tooltip()
        self.game_action.setText("▶  Reprendre Friday" if on else "🎮  Mode jeu")

    def set_loading(self, on: bool) -> None:
        """Démarrage (S3) : l'infobulle dit que Friday se prépare (elle attend Ollama…)."""
        self._loading = on
        self._tooltip()

    def set_globe(self, on: bool) -> None:
        """Œil de Dieu : l'infobulle rappelle que Friday tourne sur son petit cerveau."""
        self._globe = on
        if self.tray is not None:
            self.globe_action.setText("🌍  Fermer l'œil de Dieu" if on else "🌍  Œil de Dieu")
        self._tooltip()

    def _tooltip(self) -> None:
        if self.tray is None:
            return
        if self._game:
            text = "Friday · mode jeu (« Friday, reviens » ou double clap)"
        elif self._loading:
            text = "Friday · démarrage…"
        else:
            text = "Friday · œil de Dieu (petit cerveau)" if self._globe else "Friday"
        self.tray.setToolTip(text)

    def hidden_once(self) -> None:
        """La croix a caché Friday : on le dit une fois, pour qu'elle ne semble pas fermée."""
        if self._told_hidden or self.tray is None:
            return
        self._told_hidden = True
        self.tray.showMessage("Friday reste là",
                              "Elle vous écoute toujours. Clic sur l'icône pour la rouvrir ; "
                              "clic droit → « Quitter Friday » pour l'arrêter.",
                              QSystemTrayIcon.Information, SHOWN_MS)  # fmt: skip

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

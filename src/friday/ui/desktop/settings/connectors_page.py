"""Page « Connecteurs » : les serveurs MCP de data/mcp.json, leur état (branché, en panne…),
leurs outils, un interrupteur chacun. « Ajouter un connecteur » (tout prêt ou le sien),
« Outils » pour choisir ceux que qwen reçoit, « Supprimer » ; « Se connecter » quand un
serveur distant demande un compte. Le fichier reste ouvrable, pour les cas rares. Appliqué
tout de suite, sans redémarrer."""

import os

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from friday.connectors import config

HELP = ("Les connecteurs MCP donnent à Friday les outils d'autres services (Notion, "
        "TradingView…). Un outil qui peut modifier des données vous demande toujours « oui » "
        "avant. Un serveur en ligne peut demander un compte : « Se connecter » ouvre le "
        "navigateur, et le jeton reste sur ce PC.")  # fmt: skip


class ConnectorsPage(QWidget):
    changed = Signal()  # émis depuis le fil d'un connecteur : rafraîchit dans le fil de l'écran

    def __init__(self, connectors) -> None:
        super().__init__(objectName="SettingsPage")
        self.connectors = connectors
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(8)
        layout.addWidget(QLabel("Connecteurs", objectName="SettingsTitle"))
        if connectors is None:
            layout.addWidget(QLabel("Connecteurs indisponibles : Friday n'est pas encore chargé, "
                                    "ou la bibliothèque mcp manque.", objectName="Hint",
                                    wordWrap=True))  # fmt: skip
            layout.addStretch()
            return
        from friday.ui.desktop.settings.connector_form import ConnectorForm

        layout.addWidget(QLabel(HELP, objectName="Hint", wordWrap=True))
        buttons = QHBoxLayout()
        self.add_button = QPushButton("Ajouter un connecteur", objectName="SettingsPrimary")
        buttons.addWidget(self.add_button)
        for text, action in (("Rebrancher", connectors.reload),
                             ("Ouvrir le fichier", self._open_file)):  # fmt: skip
            button = QPushButton(text, objectName="SettingsSmall")
            button.clicked.connect(action)
            buttons.addWidget(button)
        buttons.addStretch()
        layout.addLayout(buttons)
        self.form = ConnectorForm(connectors)
        self.form.hide()
        self.add_button.clicked.connect(lambda: self.form.setVisible(not self.form.isVisible()))
        layout.addWidget(self.form)
        self.rows = QVBoxLayout()
        self.rows.setSpacing(6)
        layout.addLayout(self.rows)
        layout.addStretch()
        self.picking: str | None = None  # le serveur dont on choisit les outils
        self._removing: str | None = None  # « Supprimer » cliqué une fois : à confirmer
        self.changed.connect(self.refresh)
        self._listener = self._notify
        connectors.listeners.append(self._listener)
        self.destroyed.connect(self._closed)
        self.refresh()

    def _notify(self) -> None:
        try:
            self.changed.emit()
        except RuntimeError:  # page détruite entre-temps
            pass

    def _closed(self) -> None:
        if self._listener in self.connectors.listeners:
            self.connectors.listeners.remove(self._listener)

    def refresh(self) -> None:
        from friday.ui.desktop.settings.tool_picker import ToolPicker

        while self.rows.count():
            old = self.rows.takeAt(0).widget()
            old.hide()  # sinon visible par-dessus la page jusqu'à sa destruction
            old.deleteLater()
        problem = config.problem(self.connectors.path)
        if problem:
            self.rows.addWidget(QLabel(f"Le fichier mcp.json n'est pas compris ({problem}). "
                                       "Corrigez-le puis « Rebrancher ».",
                                       objectName="Warning", wordWrap=True))  # fmt: skip
        statuses = self.connectors.statuses()
        for status in statuses:
            self.rows.addWidget(self._row(status))
            if status.name == self.picking and status.state == "branché":
                self.picker = ToolPicker(self.connectors, status.name)
                self.picker.done.connect(self._picked)
                self.rows.addWidget(self.picker)
        if not statuses and not problem:
            self.rows.addWidget(QLabel("Aucun connecteur pour l'instant : « Ajouter un "
                                       "connecteur » en propose des tout prêts.",
                                       objectName="Hint", wordWrap=True))  # fmt: skip

    def _row(self, status) -> QFrame:
        from friday.ui.desktop.widgets.toggle import Toggle

        row = QFrame(objectName="SettingsRow")
        column = QVBoxLayout(row)
        column.setContentsMargins(14, 8, 10, 8)
        top = QHBoxLayout()
        toggle = Toggle(status.enabled)
        toggle.toggled.connect(lambda on, n=status.name: self.connectors.set_enabled(n, on))
        top.addWidget(toggle)
        text = QVBoxLayout()
        state = f"{status.state} · {status.detail}" if status.detail else status.state
        text.addWidget(QLabel(f"{status.name} — {state}", objectName="SettingsLabel",
                              wordWrap=True))  # fmt: skip
        shown = ", ".join(status.tools[:8]) + (" …" if len(status.tools) > 8 else "")
        text.addWidget(QLabel(shown or status.where, objectName="Hint", wordWrap=True))
        top.addLayout(text, 1)
        column.addLayout(top)
        actions = QHBoxLayout()
        actions.addStretch()
        row.toggle, row.account, row.tools = toggle, None, None
        if status.state == "à connecter" or status.signed_in:
            login = status.state == "à connecter"
            row.account = self._button(actions, "Se connecter" if login else "Se déconnecter",
                                       self.connectors.sign_in if login
                                       else self.connectors.sign_out, status.name)  # fmt: skip
        if status.state == "branché":
            row.tools = self._button(actions, "Fermer" if self.picking == status.name
                                     else "Outils", self._pick, status.name)  # fmt: skip
        confirm = self._removing == status.name
        row.remove = self._button(actions, "Confirmer la suppression" if confirm else "Supprimer",
                                  self._remove, status.name)  # fmt: skip
        column.addLayout(actions)
        return row

    @staticmethod
    def _button(line: QHBoxLayout, text: str, action, name: str) -> QPushButton:
        button = QPushButton(text, objectName="SettingsSmall")
        button.clicked.connect(lambda _=False: action(name))
        line.addWidget(button)
        return button

    def _pick(self, name: str) -> None:
        self.picking = None if self.picking == name else name
        self.refresh()

    def _picked(self) -> None:
        self.picking = None
        self.refresh()

    def _remove(self, name: str) -> None:
        if self._removing != name:  # premier clic : on demande de confirmer
            self._removing = name
            self.refresh()
            return
        self._removing = None
        if self.picking == name:
            self.picking = None
        self.connectors.remove(name)

    def _open_file(self) -> None:
        config.ensure(self.connectors.path)
        os.startfile(self.connectors.path)  # noqa: S606 (fichier de Friday)

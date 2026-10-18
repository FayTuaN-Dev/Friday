"""Page « Connecteurs » : les serveurs MCP de data/mcp.json, leur état (branché, en panne…),
leurs outils, un interrupteur chacun ; « Ouvrir le fichier » pour en ajouter, « Rebrancher »
pour relire le fichier. Appliqué tout de suite, sans redémarrer."""

import os

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from friday.connectors import config

HELP = ("Les connecteurs MCP donnent à Friday les outils d'autres services (TradingView, "
        "GitHub, Notion…). Ajoutez un serveur dans le fichier, puis « Rebrancher ». Un outil "
        "qui peut modifier des données vous demande toujours « oui » avant.")  # fmt: skip
EXAMPLE = ('Exemple : {"serveurs": {"notes": {"commande": "npx", "arguments": ["-y", '
           '"un-serveur-mcp"], "description": "mes notes", "mots_cles": ["note"]}}}')  # fmt: skip


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
        layout.addWidget(QLabel(HELP, objectName="Hint", wordWrap=True))
        buttons = QHBoxLayout()
        for text, action in (("Ouvrir le fichier", self._open_file),
                             ("Rebrancher", connectors.reload)):  # fmt: skip
            button = QPushButton(text, objectName="SettingsSmall")
            button.clicked.connect(action)
            buttons.addWidget(button)
        buttons.addStretch()
        layout.addLayout(buttons)
        self.rows = QVBoxLayout()
        self.rows.setSpacing(6)
        layout.addLayout(self.rows)
        layout.addStretch()
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
        while self.rows.count():
            self.rows.takeAt(0).widget().deleteLater()
        statuses = self.connectors.statuses()
        for status in statuses:
            self.rows.addWidget(self._row(status))
        if not statuses:
            self.rows.addWidget(QLabel("Aucun connecteur pour l'instant. " + EXAMPLE,
                                       objectName="Hint", wordWrap=True))  # fmt: skip

    def _row(self, status) -> QFrame:
        from friday.ui.desktop.widgets.toggle import Toggle

        row = QFrame(objectName="SettingsRow")
        line = QHBoxLayout(row)
        line.setContentsMargins(14, 8, 10, 8)
        toggle = Toggle(status.enabled)
        toggle.toggled.connect(lambda on, n=status.name: self.connectors.set_enabled(n, on))
        line.addWidget(toggle)
        text = QVBoxLayout()
        state = f"{status.state} · {status.detail}" if status.detail else status.state
        text.addWidget(QLabel(f"{status.name} — {state}", objectName="SettingsLabel",
                              wordWrap=True))  # fmt: skip
        shown = ", ".join(status.tools[:8]) + (" …" if len(status.tools) > 8 else "")
        text.addWidget(QLabel(shown or status.where, objectName="Hint", wordWrap=True))
        line.addLayout(text, 1)
        row.toggle = toggle
        return row

    def _open_file(self) -> None:
        config.ensure(self.connectors.path)
        os.startfile(self.connectors.path)  # noqa: S606 (fichier de Friday)

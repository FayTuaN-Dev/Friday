"""Réglages → Connecteurs → « Ajouter un connecteur » : un connecteur tout prêt (Notion,
Heure, TradingView…) ou le sien (une adresse en ligne, ou un programme sur ce PC et ses clés),
sans écrire data/mcp.json à la main."""

import shlex

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from friday.connectors.catalog import PRESETS

ONLINE, LOCAL = "En ligne (une adresse)", "Sur ce PC (un programme)"
OWN = "Le mien (personnalisé)"
OWN_NOTE = ("Une adresse en ligne (https://…/mcp) ou un programme lancé sur ce PC : voir la "
            "page du serveur MCP.")  # fmt: skip


def split_args(text: str) -> list[str]:
    """Les arguments tels qu'on les tape (« -y "mon dossier" ») ; les \\ des chemins restent."""
    try:
        parts = shlex.split(text, posix=False)
    except ValueError:  # guillemet non fermé
        parts = text.split()
    return [p[1:-1] if len(p) > 1 and p[0] == p[-1] and p[0] in "\"'" else p for p in parts]


def parse_keys(text: str) -> dict[str, str]:
    """« NOM=valeur », une par ligne ; les autres lignes sont ignorées."""
    pairs = (line.split("=", 1) for line in text.splitlines() if "=" in line)
    return {name.strip(): value.strip() for name, value in pairs if name.strip()}


class ConnectorForm(QFrame):
    added = Signal()

    def __init__(self, connectors) -> None:
        super().__init__(objectName="SettingsRow")
        self.connectors = connectors
        self._extra: dict = {}  # ce qu'un connecteur tout prêt règle en plus (ses outils)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.addWidget(QLabel("Ajouter un connecteur", objectName="SettingsLabel"))
        self.preset = QComboBox()
        self.preset.addItem(OWN, None)
        for preset in PRESETS:
            self.preset.addItem(preset.name.capitalize(), preset)
        self.preset.currentIndexChanged.connect(self._fill)
        layout.addWidget(self.preset)
        self.note = QLabel(objectName="Hint", wordWrap=True)
        layout.addWidget(self.note)
        self.name = QLineEdit(placeholderText="Nom (ex. notes)")
        self.kind = QComboBox()
        self.kind.addItems([ONLINE, LOCAL])
        self.kind.currentIndexChanged.connect(self._show_kind)
        self.url = QLineEdit(placeholderText="Adresse du serveur (https://…/mcp)")
        self.command = QLineEdit(placeholderText="Programme (ex. npx, uvx)")
        self.args = QLineEdit(placeholderText="Arguments (ex. -y un-serveur-mcp)")
        self.keys = QPlainTextEdit(placeholderText="Clés, une par ligne : NOM=valeur "
                                                   "(restent sur ce PC)")  # fmt: skip
        self.keys.setFixedHeight(64)
        self.description = QLineEdit(placeholderText="À quoi il sert, en une ligne "
                                                     "(aide Friday à le choisir)")  # fmt: skip
        self.keywords = QLineEdit(placeholderText="Mots-clés, séparés par des virgules "
                                                  "(ex. notion, mes pages)")  # fmt: skip
        for widget in (self.name, self.kind, self.url, self.command, self.args, self.keys,
                       self.description, self.keywords):  # fmt: skip
            layout.addWidget(widget)
        line = QHBoxLayout()
        self.status = QLabel(objectName="Warning", wordWrap=True)
        line.addWidget(self.status, 1)
        cancel = QPushButton("Annuler", objectName="SettingsSmall")
        cancel.clicked.connect(self.hide)
        self.add_button = QPushButton("Ajouter", objectName="SettingsPrimary")
        self.add_button.clicked.connect(self.submit)
        line.addWidget(cancel)
        line.addWidget(self.add_button)
        layout.addLayout(line)
        self._fill()

    def _show_kind(self) -> None:
        local = self.kind.currentText() == LOCAL
        self.url.setVisible(not local)
        for widget in (self.command, self.args, self.keys):
            widget.setVisible(local)

    def _fill(self) -> None:
        """Un connecteur tout prêt remplit le formulaire (qu'on peut encore retoucher)."""
        preset = self.preset.currentData()
        entry = preset.entry if preset else {}
        self.note.setText(preset.note if preset else OWN_NOTE)
        self.name.setText(preset.name if preset else "")
        self.kind.setCurrentText(LOCAL if entry.get("commande") else ONLINE)
        self.url.setText(entry.get("url", ""))
        self.command.setText(entry.get("commande", ""))
        self.args.setText(shlex.join(entry.get("arguments", [])))
        self.keys.setPlainText("")
        self.description.setText(entry.get("description", ""))
        self.keywords.setText(", ".join(entry.get("mots_cles", [])))
        self._extra = {"outils": entry["outils"]} if "outils" in entry else {}
        self.status.setText("")
        self._show_kind()

    def entry(self) -> dict:
        entry: dict = {"description": self.description.text().strip(),
                       "mots_cles": [k.strip() for k in self.keywords.text().split(",")
                                     if k.strip()], **self._extra}  # fmt: skip
        if self.kind.currentText() == LOCAL:
            entry["commande"] = self.command.text().strip()
            entry["arguments"] = split_args(self.args.text())
            keys = parse_keys(self.keys.toPlainText())
            if keys:
                entry["env"] = keys
        else:
            entry["url"] = self.url.text().strip()
        return entry

    def submit(self) -> bool:
        problem = self.connectors.add(self.name.text(), self.entry())
        self.status.setText(f"Pas ajouté : {problem}." if problem else "")
        if not problem:
            self.preset.setCurrentIndex(0)
            self._fill()
            self.hide()
            self.added.emit()
        return not problem

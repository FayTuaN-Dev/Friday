"""Réglages → Diagnostic : l'état d'Ollama, des modèles, de la carte graphique, de la voix et
de la dernière sauvegarde (app/diagnostic.py), avec « Sauvegarder maintenant » et « Recharger
le modèle »."""

import threading

from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from friday.app.diagnostic import collect
from friday.core.config import DATA_DIR


class DiagnosticPage(QFrame):
    def __init__(self, assistant, settings, data_dir=DATA_DIR) -> None:
        super().__init__(objectName="SettingsPage")
        self.assistant, self.settings, self.data_dir = assistant, settings, data_dir
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.addWidget(QLabel("Diagnostic", objectName="SettingsTitle"))
        layout.addWidget(QLabel(
            "Ce dont Friday dépend. Si Ollama ralentit fortement deux réponses de suite, le "
            "modèle est rechargé tout seul ; data/ est sauvegardé chaque jour.",
            objectName="Hint", wordWrap=True))  # fmt: skip
        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        layout.addLayout(self.grid)
        buttons = QHBoxLayout()
        for text, action in (("Actualiser", self.refresh), ("Sauvegarder maintenant", self._backup),
                             ("Recharger le modèle", self._reload)):  # fmt: skip
            button = QPushButton(text, objectName="SettingsSmall")
            button.clicked.connect(action)
            buttons.addWidget(button)
        buttons.addStretch()
        layout.addLayout(buttons)
        self.message = QLabel(objectName="Hint", wordWrap=True)
        layout.addWidget(self.message)
        layout.addStretch()
        self.refresh()

    def components(self):
        return getattr(self.assistant, "components", None)

    def refresh(self) -> None:
        while self.grid.count():
            self.grid.takeAt(0).widget().deleteLater()
        for row, (topic, state, detail) in enumerate(
                collect(self.components(), self.settings, self.data_dir)):  # fmt: skip
            self.grid.addWidget(QLabel(state), row, 0)
            self.grid.addWidget(QLabel(topic, objectName="SettingsLabel"), row, 1)
            self.grid.addWidget(QLabel(detail, objectName="Hint", wordWrap=True), row, 2)

    def _backup(self) -> None:
        backup = getattr(self.components(), "backup", None)
        if backup is None:
            self.message.setText("Friday démarre encore : réessayez dans un instant.")
            return
        done = backup.run_now()
        self.message.setText(f"Sauvegarde faite : {done.name}." if done
                             else "Sauvegarde impossible (voir logs/friday.log).")  # fmt: skip
        self.refresh()

    def _reload(self) -> None:
        brain = getattr(self.components(), "brain", None)
        if brain is None:
            self.message.setText("Friday démarre encore : réessayez dans un instant.")
            return
        threading.Thread(target=brain.reload_model, daemon=True, name="ollama-reload").start()
        self.message.setText("Rechargement du modèle lancé (quelques secondes).")

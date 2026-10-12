"""Réglages → Diagnostic : l'état d'Ollama, des modèles, de la carte graphique, de la voix et
de la dernière sauvegarde (app/diagnostic.py), avec « Sauvegarder maintenant » et « Recharger
le modèle ». Dans le panneau des réglages, le bilan se fait en arrière-plan, à l'ouverture de
la page (constaté : fait à la construction, il figeait Friday ~1 s à chaque clic sur
l'engrenage : Ollama, nvidia-smi…)."""

import threading

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from friday.app.diagnostic import collect
from friday.core.config import DATA_DIR

POLL_MS = 100  # la page vient chercher le bilan fait dans un autre fil


def _check(box: dict, components, settings, data_dir) -> None:
    """Dans un autre fil : le bilan, déposé dans `box` (rien de Qt ici)."""
    try:
        box["lines"] = collect(components, settings, data_dir)
    except Exception as error:  # le diagnostic ne doit jamais planter Friday
        box["lines"] = [("Diagnostic", "⚠️", f"impossible : {error}")]


class DiagnosticPage(QFrame):
    def __init__(self, assistant, settings, data_dir=DATA_DIR, refresh_now: bool = True) -> None:
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
        for text, action in (("Actualiser", self.refresh_async),
                             ("Sauvegarder maintenant", self._backup),
                             ("Recharger le modèle", self._reload),
                             ("Brancher Claude Code", self._plug)):  # fmt: skip
            button = QPushButton(text, objectName="SettingsSmall")
            button.clicked.connect(action)
            buttons.addWidget(button)
        buttons.addStretch()
        layout.addLayout(buttons)
        self.message = QLabel(objectName="Hint", wordWrap=True)
        layout.addWidget(self.message)
        layout.addStretch()
        # Le bilan fait dans un autre fil est déposé dans une boîte, et la page vient l'y
        # chercher. Le fil ne garde JAMAIS la page : sinon, s'il en tenait la dernière
        # référence, Python la détruisait depuis ce fil (constaté : Qt plantait plus tard)
        self._box: dict = {}
        self._checking = False
        self._poll = QTimer(self, interval=POLL_MS, timeout=self._collect_result)
        if refresh_now:
            self.refresh()

    def components(self):
        return getattr(self.assistant, "components", None)

    def refresh(self) -> None:
        self._fill(collect(self.components(), self.settings, self.data_dir))

    def refresh_async(self) -> None:
        """Le bilan sans figer l'interface : dans un autre fil, puis affiché."""
        if self._checking:
            return
        self._checking = True
        if not self.message.text():  # « Sauvegarde faite… » reste affiché
            self.message.setText("Vérification…")

        box = self._box = {}
        threading.Thread(target=_check, args=(box, self.components(), self.settings, self.data_dir),
                         daemon=True, name="diagnostic").start()  # fmt: skip
        self._poll.start()

    def _collect_result(self) -> None:
        if "lines" in self._box:
            lines = self._box.pop("lines")
            self._poll.stop()
            self._fill(lines)

    def _fill(self, lines: list) -> None:
        self._checking = False
        if self.message.text() == "Vérification…":
            self.message.setText("")
        while self.grid.count():
            self.grid.takeAt(0).widget().deleteLater()
        for row, (topic, state, detail) in enumerate(lines):
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
        self.refresh_async()

    def _plug(self) -> None:
        """Les limites Claude à l'écran : le relais branché sur la ligne d'état de Claude Code
        (copie de sécurité de ses réglages d'abord)."""
        from friday.claude_status import install

        try:
            self.message.setText(install())
        except (OSError, ValueError) as error:
            self.message.setText(f"Branchement impossible : {error}")

    def _reload(self) -> None:
        brain = getattr(self.components(), "brain", None)
        if brain is None:
            self.message.setText("Friday démarre encore : réessayez dans un instant.")
            return
        threading.Thread(target=brain.reload_model, daemon=True, name="ollama-reload").start()
        self.message.setText("Rechargement du modèle lancé (quelques secondes).")

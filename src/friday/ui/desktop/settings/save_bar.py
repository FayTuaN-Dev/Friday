"""La barre « Annuler » · « Enregistrer » des réglages du .env : cachée tant que rien n'a
changé, puis « Redémarrer Friday » une fois enregistré. Servie aux Réglages et à l'onglet
Réglages de la page Trading."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from friday.core.env_file import update_env


class SaveBar(QFrame):
    def __init__(self, forms: list, restart) -> None:
        """`forms` : les pages FormPage suivies ; `restart` : relance Friday."""
        super().__init__(objectName="SaveBar")
        self.forms = forms
        self._saved = False  # enregistré, redémarrage pas encore fait
        row = QHBoxLayout(self)
        row.setContentsMargins(16, 8, 8, 8)
        self.banner = QLabel(objectName="SaveBarText", wordWrap=True)
        self.cancel_button = QPushButton("Annuler", objectName="SettingsSmall")
        self.save_button = QPushButton("Enregistrer", objectName="SettingsPrimary")
        self.restart_button = QPushButton("Redémarrer Friday", objectName="SettingsPrimary")
        self.cancel_button.clicked.connect(self.revert)
        self.save_button.clicked.connect(self.save)
        self.restart_button.clicked.connect(restart)
        row.addWidget(self.banner, 1)
        for button in (self.cancel_button, self.save_button, self.restart_button):
            row.addWidget(button, 0, Qt.AlignRight)
        for form in forms:
            form.edited.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        count = len(self.changes())
        plural = "s" if count > 1 else ""
        if count:
            self.banner.setText(f"{count} réglage{plural} modifié{plural}")
        elif self._saved:
            self.banner.setText("Enregistré : redémarrez Friday pour l'appliquer.")
        self.cancel_button.setVisible(bool(count))
        self.save_button.setVisible(bool(count))
        self.restart_button.setVisible(self._saved and not count)
        self.setVisible(bool(count) or self._saved)

    def changes(self) -> dict[str, str]:
        changed: dict[str, str] = {}
        for form in self.forms:
            changed |= form.changes()
        return changed

    def revert(self) -> None:
        for form in self.forms:
            form.revert()
        self.refresh()

    def save(self) -> bool:
        """Écrit les réglages modifiés dans le .env ; renvoie True s'il y en avait."""
        changed = self.changes()
        if not changed:
            return False
        update_env(changed)
        for form in self.forms:  # les nouvelles valeurs deviennent le point de départ
            form.commit()
        self._saved = True
        self.refresh()
        return True

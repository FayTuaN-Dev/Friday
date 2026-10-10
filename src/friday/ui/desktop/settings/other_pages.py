"""Pages « Apparence » (couleur, appliquée tout de suite) et « Comptes » (Google)."""

from collections.abc import Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from friday.ui.desktop.theme import PRESETS
from friday.ui.desktop.widgets.color_menu import swatch


def title(text: str) -> QLabel:
    return QLabel(text, objectName="SettingsTitle")


class AppearancePage(QWidget):
    def __init__(self, current: QColor, apply_color: Callable[[QColor], None],
                 orb_style: str = "sphere", apply_style: Callable[[str], None] | None = None,
                 ) -> None:  # fmt: skip
        super().__init__(objectName="SettingsPage")
        self.current, self.apply_color = QColor(current), apply_color
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(8)
        layout.addWidget(title("Apparence"))
        layout.addWidget(QLabel("Couleur de Friday (toute l'interface et l'hologramme suivent)",
                                objectName="SettingsLabel"))  # fmt: skip
        grid = QGridLayout()
        grid.setSpacing(8)
        for i, (name, value) in enumerate(PRESETS.items()):
            button = QPushButton(name, objectName="SettingsSwatch")
            button.setIcon(swatch(QColor(value), 16))
            button.setIconSize(QSize(16, 16))
            button.clicked.connect(lambda _=False, v=value: self._choose(QColor(v)))
            grid.addWidget(button, *divmod(i, 3))
        layout.addLayout(grid)
        other = QPushButton("Autre couleur…", objectName="SettingsSmall")
        other.clicked.connect(self._pick)
        layout.addWidget(other, 0, Qt.AlignLeft)
        layout.addWidget(QLabel("Appliquée tout de suite et gardée au prochain lancement.",
                                objectName="Hint"))  # fmt: skip
        if apply_style is not None:
            layout.addSpacing(10)
            layout.addWidget(QLabel("Cœur de Friday", objectName="SettingsLabel"))
            styles = QHBoxLayout()
            for value, name in (("sphere", "Sphère de particules"), ("holo", "Hologramme")):
                button = QPushButton(name, objectName="SettingsSmall", checkable=True)
                button.setChecked(value == orb_style)
                button.clicked.connect(lambda _=False, v=value: self._style(v, apply_style))
                styles.addWidget(button)
                self.__dict__.setdefault("style_buttons", {})[value] = button
            styles.addStretch()
            layout.addLayout(styles)
        layout.addStretch()

    def _pick(self) -> None:
        chosen = QColorDialog.getColor(self.current, self, "Couleur de Friday")
        if chosen.isValid():
            self._choose(chosen)

    def _style(self, value: str, apply_style: Callable[[str], None]) -> None:
        for name, button in self.style_buttons.items():
            button.setChecked(name == value)
        apply_style(value)

    def _choose(self, color: QColor) -> None:
        self.current = color
        self.apply_color(color)


class AccountsPage(QWidget):
    def __init__(self, google) -> None:
        """`google` : GoogleAccount, ou None si non configuré (pas de google_credentials.json)."""
        super().__init__(objectName="SettingsPage")
        self.google = google
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(8)
        layout.addWidget(title("Comptes"))
        row = QFrame(objectName="SettingsRow")
        line = QHBoxLayout(row)
        line.setContentsMargins(14, 10, 14, 10)
        texts = QVBoxLayout()
        texts.addWidget(QLabel("Google (agenda et mails)", objectName="SettingsLabel"))
        self.status = QLabel(objectName="Hint", wordWrap=True)
        texts.addWidget(self.status)
        line.addLayout(texts, 1)
        self.connect_button = QPushButton("Se connecter", objectName="SettingsSmall")
        self.disconnect_button = QPushButton("Se déconnecter", objectName="SettingsSmall")
        self.connect_button.clicked.connect(self._connect)
        self.disconnect_button.clicked.connect(self._disconnect)
        line.addWidget(self.connect_button)
        line.addWidget(self.disconnect_button)
        layout.addWidget(row)
        layout.addStretch()
        self._confirming = False
        self.refresh()

    def refresh(self) -> None:
        if self.google is None:
            self.status.setText(
                "Non configuré : il faut data/google_credentials.json (voir README)."
            )
            self.connect_button.setEnabled(False)
            self.disconnect_button.setEnabled(False)
            return
        connected = self.google.connected
        self.status.setText("Connecté." if connected else "Non connecté.")
        self.connect_button.setText("Se reconnecter" if connected else "Se connecter")
        self.disconnect_button.setEnabled(connected)

    def _connect(self) -> None:
        self.google.connect_in_background()
        self.status.setText("Une page d'autorisation s'ouvre dans le navigateur…")

    def _disconnect(self) -> None:
        if not self._confirming:  # deux clics : on ne se déconnecte pas par mégarde
            self._confirming = True
            self.disconnect_button.setText("Confirmer ?")
            return
        self._confirming = False
        self.disconnect_button.setText("Se déconnecter")
        self.google.disconnect()
        self.refresh()

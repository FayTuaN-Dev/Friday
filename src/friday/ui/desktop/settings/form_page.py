"""Page de réglages construite à partir du schéma (core/settings_schema.py) : une ligne par
réglage, avec le bon contrôle (interrupteur, liste, nombre, texte)."""

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from friday.core.settings_schema import Field, Section
from friday.ui.desktop.widgets.toggle import Toggle

log = logging.getLogger(__name__)
TRUE = {"1", "true", "yes", "oui", "on"}


def make_control(field: Field, value: str) -> QWidget:
    if field.kind == "bool":
        return Toggle(value.strip().lower() in TRUE)
    if field.kind == "int":
        box = QSpinBox(minimum=int(field.minimum), maximum=int(field.maximum),
                       singleStep=int(field.step))  # fmt: skip
        box.setValue(int(float(value or field.default or 0)))
        return box
    if field.kind == "float":
        box = QDoubleSpinBox(minimum=field.minimum, maximum=field.maximum,
                             singleStep=field.step, decimals=2)  # fmt: skip
        box.setValue(float(value or field.default or 0))
        return box
    if field.kind == "choice":
        combo = QComboBox()
        try:
            options = field.options() if field.options else []
        except Exception as error:  # périphériques audio illisibles…
            log.warning("Choix de « %s » indisponibles : %s", field.label, error)
            options = []
        for option_value, label in options:
            combo.addItem(label, option_value)
        index = combo.findData(value)
        if index < 0 and value:  # valeur écrite à la main dans le .env : on la garde
            combo.addItem(value, value)
            index = combo.count() - 1
        combo.setCurrentIndex(max(0, index))
        return combo
    return QLineEdit(value)


def control_value(control: QWidget) -> str:
    if isinstance(control, Toggle):
        return "true" if control.isChecked() else "false"
    if isinstance(control, QSpinBox):
        return str(control.value())
    if isinstance(control, QDoubleSpinBox):
        return f"{control.value():.2f}".rstrip("0").rstrip(".")
    if isinstance(control, QComboBox):
        return str(control.currentData() or "")
    return control.text().strip()


class FormPage(QWidget):
    """Les valeurs de départ viennent du .env ; `changes()` rend ce qui a été modifié."""

    def __init__(self, section: Section, env: dict[str, str]) -> None:
        super().__init__(objectName="SettingsPage")
        self._controls: dict[str, tuple[QWidget, str]] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(8)
        layout.addWidget(QLabel(section.name, objectName="SettingsTitle"))
        for field in section.fields:
            start = env.get(field.key, field.default)
            control = make_control(field, start)
            self._controls[field.key] = (control, control_value(control))
            layout.addWidget(self._row(field, control))
        layout.addStretch()

    def _row(self, field: Field, control: QWidget) -> QFrame:
        row = QFrame(objectName="SettingsRow")
        line = QHBoxLayout(row)
        line.setContentsMargins(14, 10, 14, 10)
        texts = QVBoxLayout()
        texts.setSpacing(1)
        texts.addWidget(QLabel(field.label, objectName="SettingsLabel", wordWrap=True))
        if field.help:
            texts.addWidget(QLabel(field.help, objectName="Hint", wordWrap=True))
        line.addLayout(texts, 1)
        if not isinstance(control, Toggle):
            control.setMinimumWidth(220)
        line.addWidget(control, 0, Qt.AlignVCenter)
        return row

    def commit(self) -> None:
        """Après enregistrement : les valeurs actuelles deviennent la référence."""
        self._controls = {k: (c, control_value(c)) for k, (c, _) in self._controls.items()}

    def changes(self) -> dict[str, str]:
        return {key: control_value(control) for key, (control, start) in self._controls.items()
                if control_value(control) != start}  # fmt: skip

"""Page « Briefing » : activé ou non, heures, rubriques (retirer, ajouter). Appliqué tout de
suite dans data/briefing.json, sans redémarrage."""

from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from friday.briefing.config import KINDS, NEEDS_VALUE, OPTIONAL_VALUE, Section
from friday.ui.desktop.widgets.toggle import Toggle

KIND_LABELS = {
    "meteo": "Météo (ville facultative)", "agenda": "Agenda Google du jour",
    "rappels": "Rappels du jour", "mails": "Mails non lus", "liste": "Une liste (nom)",
    "actualites": "Actualité (sujet)", "libre": "Rubrique libre (consigne)",
}  # fmt: skip


class BriefingPage(QWidget):
    def __init__(self, briefing) -> None:
        super().__init__(objectName="SettingsPage")
        self.briefing = briefing
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(8)
        layout.addWidget(QLabel("Briefing du matin", objectName="SettingsTitle"))
        if briefing is None:
            layout.addWidget(QLabel("Le briefing n'est pas encore chargé.", objectName="Hint"))
            layout.addStretch()
            return
        config = briefing.config
        self.enabled = Toggle(config.enabled)
        self.enabled.toggled.connect(briefing.set_enabled)
        layout.addWidget(self._row("Briefing automatique le matin", self.enabled))
        self.on_greeting = Toggle(config.on_greeting)
        self.on_greeting.toggled.connect(briefing.set_on_greeting)
        layout.addWidget(self._row("Attendre mon premier « bonjour » (sinon : dès le démarrage)",
                                   self.on_greeting))  # fmt: skip
        hours = QWidget()
        between = QHBoxLayout(hours)
        between.setContentsMargins(0, 0, 0, 0)
        self.start = QSpinBox(minimum=0, maximum=23, value=config.start_hour, suffix=" h")
        self.end = QSpinBox(minimum=1, maximum=24, value=config.end_hour, suffix=" h")
        for box in (self.start, self.end):
            box.valueChanged.connect(self._save_hours)
        between.addWidget(QLabel("de"))
        between.addWidget(self.start)
        between.addWidget(QLabel("à"))
        between.addWidget(self.end)
        layout.addWidget(self._row("Plage horaire", hours))
        layout.addWidget(QLabel("Rubriques", objectName="SettingsLabel"))
        self.sections = QVBoxLayout()
        self.sections.setSpacing(6)
        layout.addLayout(self.sections)
        layout.addWidget(self._adder())
        layout.addStretch()
        self.refresh()

    def _row(self, label: str, control: QWidget) -> QFrame:
        row = QFrame(objectName="SettingsRow")
        line = QHBoxLayout(row)
        line.setContentsMargins(14, 10, 14, 10)
        line.addWidget(QLabel(label, objectName="SettingsLabel"), 1)
        line.addWidget(control)
        return row

    def _save_hours(self) -> None:
        self.briefing.set_hours(self.start.value(), self.end.value())

    def refresh(self) -> None:
        while self.sections.count():
            item = self.sections.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        sections = self.briefing.config.sections
        if not sections:
            self.sections.addWidget(
                QLabel("Aucune rubrique : le briefing se taira.", objectName="Hint")
            )
        for section in sections:
            remove = QPushButton("Retirer", objectName="SettingsSmall")
            remove.clicked.connect(lambda _=False, s=section: self._remove(s))
            self.sections.addWidget(self._row(section.label(), remove))

    def _remove(self, section: Section) -> None:
        self.briefing.remove(section.kind, section.value)
        self.refresh()

    def _adder(self) -> QFrame:
        self.kind = QComboBox()
        for kind in KINDS:
            self.kind.addItem(KIND_LABELS.get(kind, kind), kind)
        self.value = QLineEdit(placeholderText="Ville, sujet, liste ou consigne")
        add = QPushButton("Ajouter", objectName="SettingsSmall")
        add.clicked.connect(self._add)
        self.kind.currentIndexChanged.connect(self._update_value_field)
        row = QFrame(objectName="SettingsRow")
        line = QHBoxLayout(row)
        line.setContentsMargins(14, 10, 14, 10)
        line.addWidget(self.kind)
        line.addWidget(self.value, 1)
        line.addWidget(add)
        self._update_value_field()
        return row

    def _update_value_field(self) -> None:
        kind = self.kind.currentData()
        self.value.setEnabled(kind in NEEDS_VALUE | OPTIONAL_VALUE)

    def _add(self) -> None:
        message = self.briefing.add(self.kind.currentData(), self.value.text())
        self.value.clear()
        self.value.setPlaceholderText(message)
        self.refresh()

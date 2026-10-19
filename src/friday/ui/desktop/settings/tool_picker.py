"""Réglages → Connecteurs → « Outils » : cocher les outils d'un serveur que qwen reçoit. La
mémoire de qwen est comptée : une jauge montre le poids des outils cochés, et au-delà de la
limite on ne peut pas enregistrer."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from friday.connectors import tools as mcp_tools


class ToolPicker(QFrame):
    done = Signal()

    def __init__(self, connectors, name: str) -> None:
        super().__init__(objectName="SettingsRow")
        self.connectors, self.name = connectors, name
        self.offers = connectors.offers(name)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.addWidget(
            QLabel(f"Outils de « {name} » donnés à Friday", objectName="SettingsLabel")
        )
        layout.addWidget(QLabel(
            "Coche ceux qui te servent : moins il y en a, mieux qwen s'en sert. « modifie » : "
            "il te demandera « oui » avant.", objectName="Hint", wordWrap=True))  # fmt: skip
        inner = QWidget()
        boxes = QVBoxLayout(inner)
        boxes.setContentsMargins(0, 0, 0, 0)
        self.boxes: list[QCheckBox] = []
        for offer in self.offers:
            kind = "lecture" if offer.read_only else "modifie"
            box = QCheckBox(f"{offer.title} · {kind} · {offer.size:,} car.".replace(",", " "))
            box.setToolTip(offer.name)
            box.setChecked(offer.given)
            box.toggled.connect(self._weigh)
            boxes.addWidget(box)
            self.boxes.append(box)
        boxes.addStretch()
        scroll = QScrollArea(widgetResizable=True)
        scroll.setWidget(inner)
        scroll.setMaximumHeight(260)
        layout.addWidget(scroll)
        line = QHBoxLayout()
        self.weight = QLabel(objectName="Hint")
        line.addWidget(self.weight, 1)
        default = QPushButton("Par défaut", objectName="SettingsSmall")
        default.setToolTip("Les premiers outils assez légers, lecture seule d'abord")
        default.clicked.connect(lambda: self._save([]))
        self.save_button = QPushButton("Enregistrer", objectName="SettingsPrimary")
        self.save_button.clicked.connect(lambda: self._save(self.chosen()))
        line.addWidget(default)
        line.addWidget(self.save_button)
        layout.addLayout(line)
        self._weigh()

    def chosen(self) -> list[str]:
        return [o.name for o, box in zip(self.offers, self.boxes, strict=True) if box.isChecked()]

    def total(self) -> int:
        return sum(o.size for o, box in zip(self.offers, self.boxes, strict=True)
                   if box.isChecked())  # fmt: skip

    def _weigh(self) -> None:
        total, limit = self.total(), mcp_tools.MAX_TOTAL
        over = total > limit
        self.weight.setText(
            f"{len(self.chosen())} outil(s) · {total:,} / {limit:,} caractères".replace(",", " ")
            + (" : trop lourd pour qwen" if over else "")
        )
        self.weight.setStyleSheet("color: #e5675b;" if over else "")
        self.save_button.setEnabled(not over and bool(self.chosen()))

    def _save(self, names: list[str]) -> None:
        self.connectors.set_tools(self.name, names)
        self.done.emit()

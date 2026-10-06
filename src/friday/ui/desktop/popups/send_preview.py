"""Aperçu d'un envoi en ligne (mode trading) : EXACTEMENT ce qui partira à Claude. Chaque
élément peut être décoché ; « Envoyer » ou « Annuler » (ou « oui » / « non » à la voix).
Sans réponse explicite, rien ne part."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
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

from friday.tools.base import Display
from friday.ui.desktop.popups.base import Popup

SNIPPET = 360  # caractères d'un extrait affichés (le texte complet en info-bulle)


class SendPreviewPopup(Popup):
    def __init__(self, display: Display) -> None:
        super().__init__("🔒", display.title, (540, 640))
        data = display.data
        self.packet, self.request, self._answer = data["packet"], data["request"], data["answer"]
        self.body.addWidget(QLabel(
            "Voici exactement ce qui partira à Claude, en ligne. Décochez ce que vous ne voulez "
            "pas envoyer.", objectName="Hint", wordWrap=True))  # fmt: skip
        content = QWidget()
        column = QVBoxLayout(content)
        column.setContentsMargins(0, 0, 4, 0)
        column.setSpacing(8)
        column.addWidget(self._card("Question", self.packet.question))
        for note in self.packet.notes:
            column.addWidget(QLabel(f"ℹ️ {note}", objectName="Hint", wordWrap=True))
        if self.packet.masked:
            kinds = ", ".join(sorted(set(self.packet.masked)))
            column.addWidget(QLabel(f"🛡️ Masqué automatiquement : {kinds}.", objectName="Hint",
                                    wordWrap=True))  # fmt: skip
        self.boxes = []
        for item in self.packet.items:
            column.addWidget(self._item(item))
        column.addStretch()
        scroll = QScrollArea(widgetResizable=True)
        scroll.setWidget(content)
        self.body.addWidget(scroll, 1)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Annuler", objectName="SettingsSmall")
        send = QPushButton("Envoyer", objectName="SettingsPrimary")
        cancel.clicked.connect(lambda: self._decide(False))
        send.clicked.connect(lambda: self._decide(True))
        buttons.addWidget(cancel)
        buttons.addWidget(send)
        self.body.addLayout(buttons)
        # Réponse donnée à la voix (« oui » / « non ») : l'aperçu se ferme de lui-même.
        self._watch = QTimer(self, interval=300)
        self._watch.timeout.connect(self._closed_elsewhere)
        self._watch.start()

    def _card(self, title: str, text: str) -> QFrame:
        card = QFrame(objectName="ResultCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.addWidget(QLabel(title, objectName="Domain"))
        layout.addWidget(QLabel(text, objectName="Snippet", wordWrap=True))
        return card

    def _item(self, item) -> QFrame:
        card = QFrame(objectName="ResultCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 8)
        box = QCheckBox(f"{item.kind.capitalize()} · {item.source}")
        box.setChecked(item.included)
        box.toggled.connect(lambda checked, i=item: setattr(i, "included", checked))
        self.boxes.append(box)
        if item.image is not None:  # la capture : on voit exactement l'image qui part
            layout.addWidget(box)
            layout.addWidget(self._image(item.image))
            return card
        text = item.text if len(item.text) <= SNIPPET else item.text[:SNIPPET] + "…"
        label = QLabel(text, objectName="Snippet", wordWrap=True)
        label.setToolTip(item.text)
        layout.addWidget(box)
        layout.addWidget(label)
        return card

    def _image(self, image: bytes) -> QLabel:
        pixmap = QPixmap()
        pixmap.loadFromData(image)
        label = QLabel(alignment=Qt.AlignCenter)
        label.setPixmap(pixmap.scaledToWidth(480, Qt.SmoothTransformation))
        return label

    def _decide(self, approved: bool) -> None:
        self._watch.stop()
        self._answer(approved)
        self.close()

    def _closed_elsewhere(self) -> None:
        if self.request.answered:
            self._watch.stop()
            self.close()

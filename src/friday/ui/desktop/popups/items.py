"""Pop-up générique : une liste d'éléments (rappels, notes, courses…)."""

from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from friday.tools.base import Display
from friday.ui.desktop.popups.base import Popup


def item_row(item: dict) -> QFrame:
    row = QFrame(objectName="MemoryItem")
    layout = QVBoxLayout(row)
    layout.setContentsMargins(10, 6, 10, 6)
    layout.setSpacing(2)
    layout.addWidget(QLabel(item["text"], wordWrap=True))
    if item.get("meta"):
        layout.addWidget(QLabel(item["meta"], objectName="MemoryMeta"))
    return row


class ItemsPopup(Popup):
    def __init__(self, display: Display) -> None:
        super().__init__(display.data.get("icon", "📋"), display.title, (380, 440))
        content = QWidget()
        column = QVBoxLayout(content)
        column.setContentsMargins(0, 0, 4, 0)
        column.setSpacing(6)
        for item in display.data["items"]:
            column.addWidget(item_row(item))
        column.addStretch()
        scroll = QScrollArea(widgetResizable=True)
        scroll.setWidget(content)
        self.body.addWidget(scroll, 1)

"""Pop-up générique : une liste d'éléments (rappels, notes, courses…)."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from friday.tools.base import Display
from friday.ui.desktop.popups.base import LinkRow, Popup


def item_row(item: dict) -> QFrame:
    """Une ligne ; cliquable (survol, ↗) quand elle mène quelque part (« url »)."""
    row = LinkRow(item.get("url", ""), objectName="MemoryItem")
    outer = QHBoxLayout(row)
    outer.setContentsMargins(10, 6, 10, 6)
    outer.setSpacing(8)
    column = QVBoxLayout()
    column.setSpacing(2)
    column.addWidget(QLabel(item["text"], wordWrap=True))
    if item.get("meta"):
        column.addWidget(QLabel(item["meta"], objectName="MemoryMeta", wordWrap=True))
    outer.addLayout(column, 1)
    if row.url:
        outer.addWidget(QLabel("↗", objectName="OpenMark"), 0, Qt.AlignTop)
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
        self.fit_height(content)

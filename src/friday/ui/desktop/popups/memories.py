"""Pop-up « Ce que je sais sur vous » : la liste des souvenirs de Friday."""

from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from friday.tools.base import Display
from friday.ui.desktop.popups.base import Popup

SOURCES = {"explicit": "demandé", "auto": "déduit"}


def memory_item(memory: dict) -> QFrame:
    item = QFrame(objectName="MemoryItem")
    layout = QVBoxLayout(item)
    layout.setContentsMargins(10, 6, 10, 6)
    layout.setSpacing(2)
    layout.addWidget(QLabel(memory["text"], wordWrap=True))
    source = SOURCES.get(memory["source"], memory["source"])
    meta = f"n°{memory['id']} · {source} · {memory['date']}"
    if memory.get("category"):
        meta += f" · {memory['category']}"
    if memory.get("confirmations", 1) > 1:
        meta += f" · confirmé {memory['confirmations']} fois"
    for old in memory.get("before", [])[:2]:
        layout.addWidget(QLabel(f"avant : {old}", objectName="MemoryMeta", wordWrap=True))
    layout.addWidget(QLabel(meta, objectName="MemoryMeta"))
    return item


class MemoriesPopup(Popup):
    def __init__(self, display: Display) -> None:
        super().__init__("🧠", display.title, (420, 500))
        content = QWidget()
        column = QVBoxLayout(content)
        column.setContentsMargins(0, 0, 4, 0)
        column.setSpacing(6)
        for memory in display.data["memories"]:
            column.addWidget(memory_item(memory))
        column.addStretch()

        scroll = QScrollArea(widgetResizable=True)
        scroll.setWidget(content)
        self.body.addWidget(scroll, 1)
        self.body.addWidget(
            QLabel("Pour effacer : « Friday, oublie que… »", objectName="Hint", wordWrap=True)
        )

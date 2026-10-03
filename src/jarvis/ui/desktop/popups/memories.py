"""Pop-up « Ce que je sais sur vous » : la liste des souvenirs de Jarvis."""

from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from jarvis.tools.base import Display
from jarvis.ui.desktop.popups.base import Popup

SOURCES = {"explicit": "demandé", "auto": "déduit"}


def memory_item(memory: dict) -> QFrame:
    item = QFrame(objectName="MemoryItem")
    layout = QVBoxLayout(item)
    layout.setContentsMargins(10, 6, 10, 6)
    layout.setSpacing(2)
    layout.addWidget(QLabel(memory["text"], wordWrap=True))
    source = SOURCES.get(memory["source"], memory["source"])
    meta = f"n°{memory['id']} · {source} · {memory['date']}"
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
            QLabel("Pour effacer : « Jarvis, oublie que… »", objectName="Hint", wordWrap=True)
        )

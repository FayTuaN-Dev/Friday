"""Pop-up des fichiers trouvés : cliquer sur le nom l'ouvre, « Dossier » le montre."""

import logging
from html import escape
from pathlib import Path

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from friday.files.opener import CannotOpen, open_file, reveal_file
from friday.tools.base import Display
from friday.ui.desktop.popups.base import Popup

log = logging.getLogger(__name__)


def _act(action: str, path: str) -> None:
    try:
        (reveal_file if action == "reveal" else open_file)(Path(path))
    except CannotOpen as error:
        log.warning("%s", error)


def file_card(item: dict) -> QFrame:
    card = QFrame(objectName="ResultCard")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(12, 8, 12, 8)
    layout.setSpacing(2)
    path = item["path"]

    top = QHBoxLayout()
    name = QLabel(f'<a href="open">{escape(item["name"])}</a>', objectName="Link", wordWrap=True)
    name.setToolTip(path)
    folder = QLabel('<a href="reveal">Dossier</a>', objectName="Domain")
    folder.setToolTip("Montrer dans l'explorateur")
    for label in (name, folder):
        label.linkActivated.connect(lambda action, p=path: _act(action, p))
    top.addWidget(name, 1)
    top.addWidget(folder)
    layout.addLayout(top)
    layout.addWidget(QLabel(item["where"], objectName="Snippet", wordWrap=True))
    layout.addWidget(QLabel(item["meta"], objectName="MemoryMeta"))
    return card


class FilesPopup(Popup):
    def __init__(self, display: Display) -> None:
        super().__init__("🗂️", display.title, (440, 520))
        content = QWidget()
        column = QVBoxLayout(content)
        column.setContentsMargins(0, 0, 4, 0)
        column.setSpacing(8)
        for item in display.data["files"]:
            column.addWidget(file_card(item))
        column.addStretch()
        scroll = QScrollArea(widgetResizable=True)
        scroll.setWidget(content)
        self.body.addWidget(scroll)

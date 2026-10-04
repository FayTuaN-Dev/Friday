"""Pop-up des résultats de recherche web (cliquer sur un titre ouvre le navigateur)."""

from html import escape
from urllib.parse import urlparse

from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from friday.tools.base import Display
from friday.ui.desktop.popups.base import Popup


def result_card(title: str, url: str, snippet: str) -> QFrame:
    card = QFrame(objectName="ResultCard")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(10, 8, 10, 8)
    layout.setSpacing(2)

    link = QLabel(f'<a href="{escape(url, quote=True)}">{escape(title)}</a>', objectName="Link")
    link.setOpenExternalLinks(True)
    link.setWordWrap(True)
    domain = QLabel(urlparse(url).netloc.removeprefix("www."), objectName="Domain")
    text = QLabel(snippet, objectName="Snippet", wordWrap=True)

    for widget in (link, domain, text):
        layout.addWidget(widget)
    return card


class ResultsPopup(Popup):
    def __init__(self, display: Display) -> None:
        super().__init__("🔎", display.title, (440, 520))
        content = QWidget()
        column = QVBoxLayout(content)
        column.setContentsMargins(0, 0, 4, 0)
        column.setSpacing(8)
        for r in display.data["results"]:
            column.addWidget(result_card(r["title"], r["url"], r["snippet"]))
        column.addStretch()

        scroll = QScrollArea(widgetResizable=True)
        scroll.setWidget(content)
        self.body.addWidget(scroll)

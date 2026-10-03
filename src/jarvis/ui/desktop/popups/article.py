"""Pop-up d'article : le texte d'une page web lue par Jarvis."""

from html import escape
from urllib.parse import urlparse

from PySide6.QtWidgets import QLabel, QTextBrowser

from jarvis.tools.base import Display
from jarvis.ui.desktop.popups.base import Popup


class ArticlePopup(Popup):
    def __init__(self, display: Display) -> None:
        super().__init__("📄", display.title, (520, 620))
        url = display.data["url"]
        source = QLabel(
            f'Source : <a href="{escape(url, quote=True)}">{escape(urlparse(url).netloc)}</a>',
            objectName="Domain",
        )
        source.setOpenExternalLinks(True)

        text = QTextBrowser(objectName="Article")
        paragraphs = (p.strip() for p in display.data["text"].splitlines())
        text.setHtml("".join(f"<p>{escape(p)}</p>" for p in paragraphs if p))

        self.body.addWidget(source)
        self.body.addWidget(text, 1)

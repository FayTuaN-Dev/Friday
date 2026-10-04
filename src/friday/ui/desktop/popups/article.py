"""Pop-up d'article : le texte d'une page web ou d'un fichier lu par Friday."""

from html import escape
from urllib.parse import urlparse

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QLabel, QTextBrowser

from friday.tools.base import Display
from friday.ui.desktop.popups.base import Popup


class ArticlePopup(Popup):
    def __init__(self, display: Display) -> None:
        super().__init__("📄", display.title, (520, 620))
        if "path" in display.data:  # fichier de l'ordinateur : lien pour l'ouvrir
            url = QUrl.fromLocalFile(display.data["path"]).toString()
            where = f"Fichier : {escape(display.data['path'])}"
        else:
            url = display.data["url"]
            where = f"Source : {escape(urlparse(url).netloc)}"
        source = QLabel(f'<a href="{escape(url, quote=True)}">{where}</a>', objectName="Domain")
        source.setOpenExternalLinks(True)

        text = QTextBrowser(objectName="Article")
        paragraphs = (p.strip() for p in display.data["text"].splitlines())
        text.setHtml("".join(f"<p>{escape(p)}</p>" for p in paragraphs if p))

        self.body.addWidget(source)
        self.body.addWidget(text, 1)

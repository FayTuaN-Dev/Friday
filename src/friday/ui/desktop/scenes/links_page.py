"""Page web des scènes : un lien cliqué (titre d'un article sur le globe) s'ouvre dans le
navigateur de l'utilisateur, la scène reste en place (U5)."""

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWebEngineCore import QWebEnginePage

HOME = "friday.local"  # l'adresse de base de la page des scènes


def is_outside(url: QUrl, main_frame: bool) -> bool:
    return main_frame and url.scheme() in ("http", "https") and url.host() != HOME


class LinksPage(QWebEnginePage):
    def acceptNavigationRequest(self, url: QUrl, kind, main_frame: bool) -> bool:
        if is_outside(url, main_frame):
            QDesktopServices.openUrl(url)
            return False
        return super().acceptNavigationRequest(url, kind, main_frame)

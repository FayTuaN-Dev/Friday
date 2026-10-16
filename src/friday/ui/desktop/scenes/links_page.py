"""Page web des scènes : un lien cliqué (titre d'un article sur le globe) s'ouvre dans le
navigateur de l'utilisateur, la scène reste en place (U5). Et une demande de la page à
Friday (bouton « Avions » de la carte) arrive par la console : « friday:{…} »."""

import json

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWebEngineCore import QWebEnginePage

HOME = "friday.local"  # l'adresse de base de la page des scènes


ASK = "friday:"


def request_of(message: str) -> dict | None:
    """Une demande de la page (« friday:{"ask": …} »), ou None pour un message ordinaire."""
    if not message.startswith(ASK):
        return None
    try:
        request = json.loads(message[len(ASK) :])
    except ValueError:
        return None
    return request if isinstance(request, dict) and "ask" in request else None


def is_outside(url: QUrl, main_frame: bool) -> bool:
    return main_frame and url.scheme() in ("http", "https") and url.host() != HOME


class LinksPage(QWebEnginePage):
    asked = Signal(dict)  # une demande de la page à Friday

    def javaScriptConsoleMessage(self, level, message: str, line: int, source: str) -> None:
        request = request_of(message)
        if request is not None:
            self.asked.emit(request)

    def acceptNavigationRequest(self, url: QUrl, kind, main_frame: bool) -> bool:
        if is_outside(url, main_frame):
            QDesktopServices.openUrl(url)
            return False
        return super().acceptNavigationRequest(url, kind, main_frame)

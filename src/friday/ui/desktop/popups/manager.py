"""Ouvre les pop-ups à côté de la fenêtre principale et limite leur nombre."""

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QWidget

from friday.tools.base import Display
from friday.ui.desktop.popups.article import ArticlePopup
from friday.ui.desktop.popups.base import Popup
from friday.ui.desktop.popups.claude import ClaudePopup
from friday.ui.desktop.popups.files import FilesPopup
from friday.ui.desktop.popups.images import ImagesPopup
from friday.ui.desktop.popups.items import ItemsPopup
from friday.ui.desktop.popups.memories import MemoriesPopup
from friday.ui.desktop.popups.results import ResultsPopup
from friday.ui.desktop.popups.weather import WeatherPopup

POPUPS = {
    "results": ResultsPopup,
    "article": ArticlePopup,
    "images": ImagesPopup,
    "memories": MemoriesPopup,
    "weather": WeatherPopup,
    "claude": ClaudePopup,
    "items": ItemsPopup,
    "files": FilesPopup,
}
MAX_OPEN = 3
GAP = 12  # espace entre la fenêtre et le pop-up
CASCADE = 36  # décalage entre pop-ups successifs


class PopupManager:
    def __init__(self, anchor: QWidget) -> None:
        self.anchor = anchor
        self.popups: list[Popup] = []

    def show(self, display: Display) -> Popup | None:
        popup_class = POPUPS.get(display.kind)
        if popup_class is None:
            return None
        while len(self.popups) >= MAX_OPEN:
            self.popups[0].close()  # le plus ancien laisse sa place

        popup = popup_class(display)
        popup.closed.connect(self._forget)
        popup.move(self._position_for(popup, len(self.popups)))
        self.popups.append(popup)
        popup.show_animated()
        return popup

    def close_all(self) -> None:
        for popup in list(self.popups):
            popup.close()

    def _forget(self, popup: Popup) -> None:
        if popup in self.popups:
            self.popups.remove(popup)

    def _position_for(self, popup: Popup, index: int) -> QPoint:
        frame = self.anchor.frameGeometry()
        offset = index * CASCADE
        x = frame.right() + GAP + offset
        y = frame.top() + offset
        screen = self.anchor.screen().availableGeometry()
        if x + popup.width() > screen.right():  # pas de place à droite : on va à gauche
            x = frame.left() - GAP - popup.width() - offset
        x = max(screen.left(), min(x, screen.right() - popup.width()))
        y = max(screen.top(), min(y, screen.bottom() - popup.height()))
        return QPoint(x, y)

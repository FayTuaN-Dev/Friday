"""Ouvre les pop-ups à côté de la fenêtre principale et limite leur nombre."""

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QWidget

from friday.tools.base import Display
from friday.tools.popups import CLOSE
from friday.ui.desktop.popups.article import ArticlePopup
from friday.ui.desktop.popups.base import Popup
from friday.ui.desktop.popups.claude import ClaudePopup
from friday.ui.desktop.popups.files import FilesPopup
from friday.ui.desktop.popups.images import ImagesPopup
from friday.ui.desktop.popups.items import ItemsPopup
from friday.ui.desktop.popups.memories import MemoriesPopup
from friday.ui.desktop.popups.results import ResultsPopup
from friday.ui.desktop.popups.screen import ScreenPopup
from friday.ui.desktop.popups.send_preview import SendPreviewPopup
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
    "screen": ScreenPopup,
    "send_preview": SendPreviewPopup,
}
MAX_OPEN = 3
GAP = 12  # espace entre la fenêtre et le pop-up
CASCADE = 36  # décalage entre pop-ups successifs


class PopupManager:
    def __init__(self, anchor: QWidget) -> None:
        self.anchor = anchor
        self.popups: list[Popup] = []

    def show(self, display: Display) -> Popup | None:
        if display.kind == CLOSE:  # Friday ferme ses propres fenêtres
            self.close_last() if display.data.get("which") == "last" else self.close_all()
            return None
        popup_class = POPUPS.get(display.kind)
        if popup_class is None:
            return None
        if display.key:  # une liste déjà affichée : mise à jour sur place
            current = next((p for p in self.popups if p.key == display.key), None)
            if current is not None:
                return self._replace(current, popup_class(display), display.key)
        if display.refresh:  # rien d'ouvert à mettre à jour : on n'ouvre rien
            return None
        while len(self.popups) >= MAX_OPEN:
            self.popups[0].close()  # le plus ancien laisse sa place

        popup = popup_class(display)
        popup.key = display.key
        popup.closed.connect(self._forget)
        popup.move(self._position_for(popup, len(self.popups)))
        self.popups.append(popup)
        popup.show_animated()
        return popup

    def _replace(self, current: Popup, popup: Popup, key: str) -> Popup:
        popup.key = key
        popup.closed.connect(self._forget)
        popup.setGeometry(current.geometry())  # même place, même taille : pas de saut
        self.popups[self.popups.index(current)] = popup
        current.close()
        popup.setWindowOpacity(0.97)
        popup.show()
        return popup

    def close_last(self) -> None:
        if self.popups:
            self.popups[-1].close()

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

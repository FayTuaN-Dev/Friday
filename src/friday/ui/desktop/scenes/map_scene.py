"""Scène carte 3D plein écran (J7) : « montre-moi la tour Eiffel » → la carte se place sur le
lieu, inclinée, bâtiments en volume ; une fois que Friday a fini de parler, elle s'envole un
peu et tourne lentement autour. La même scène montre le globe de la veille monde (J9b), qui
tourne dès qu'il s'affiche. La page web : map_page.py (lieux) et globe_js.py (globe).

La page est créée UNE fois, peu après le démarrage, puis réutilisée : créer le moteur web
bloque la fenêtre un instant, ce qui hachait la voix quand c'était fait pendant qu'elle
parlait."""

import json
import logging
import time

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QVBoxLayout, QWidget

from friday.ui.desktop.scenes.map_page import BACKGROUND, page

__all__ = ["MapScene", "go_script", "page", "world_script"]

log = logging.getLogger(__name__)

# La carte est prête à être vue : style chargé, tuiles reçues, caméra immobile (U8)
READY_JS = ("typeof map !== 'undefined' && map.loaded() && map.areTilesLoaded() "
            "&& !map.isMoving()")  # fmt: skip
POLL_MS = 120


def world_script(data: dict) -> str:
    """Le JavaScript qui montre le globe et ses points."""
    return f"window.fridayWorld && window.fridayWorld({json.dumps(data['points'])});"


def go_script(data: dict, accent: str) -> str:
    """Le JavaScript qui place la carte sur un lieu."""
    args = ", ".join(json.dumps(v) for v in (data["lat"], data["lon"], data["zoom"], accent))
    return f"window.fridayGo && window.fridayGo({args});"


def lower_web_priority() -> None:
    """Les processus du moteur web de Friday en priorité « inférieure à la normale ». Constaté :
    la carte qui se charge (ses tuiles, son rendu) et la voix (fabriquée sur le processeur)
    se disputaient la machine : voix hachée. Windows sert maintenant la voix d'abord."""
    try:
        import psutil

        for child in psutil.Process().children(recursive=True):
            if "qtwebengine" in child.name().lower():
                child.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception as error:  # rien de grave : la carte marche quand même
        log.debug("Priorité du moteur web inchangée : %s", error)


class MapScene(QWidget):
    keep = True  # gardée entre deux affichages (le calque la cache au lieu de la détruire)

    def __init__(self, accent: str = "#f0a83c", parent=None) -> None:
        super().__init__(parent)
        from PySide6.QtWebEngineWidgets import QWebEngineView

        self.accent = accent
        self.ready = False
        self._pending: str | None = None  # le dernier script, joué une fois la page prête
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = QWebEngineView(self)
        self.view.page().setBackgroundColor(QColor(BACKGROUND))  # pas de flash blanc
        self.view.loadFinished.connect(self._loaded)
        self.view.setHtml(page(accent), QUrl("https://friday.local/"))
        layout.addWidget(self.view)
        # Le moteur web (processus à part) passe après la voix et Friday (U8)
        QTimer.singleShot(3000, lower_web_priority)

    def _loaded(self, ok: bool) -> None:
        self.ready = ok
        if ok and self._pending is not None:
            self._run(self._pending)

    def _run(self, script: str) -> None:
        self._pending = script
        if self.ready:
            self.view.page().runJavaScript(script)

    def go(self, data: dict) -> None:
        """Se place sur le lieu (sans animation : Friday va en parler)."""
        self._run(go_script(data, self.accent))

    def world(self, data: dict) -> None:
        """Le globe de la veille monde (J9b)."""
        self._run(world_script(data))

    def set_insets(self, top: int, bottom: int) -> None:
        """La conversation couvre le bas : le lieu (ou le globe) se centre au-dessus."""
        if self.ready:
            self.view.page().runJavaScript(
                f"window.fridayPad && window.fridayPad({top}, {bottom});"
            )

    def when_shown(self, callback, timeout: float = 4.0) -> None:
        """Appelle `callback` quand la carte est prête à être vue (page chargée, tuiles
        reçues, caméra immobile), ou au bout de `timeout` secondes."""
        deadline = time.monotonic() + timeout

        def check(done=False) -> None:
            if done or time.monotonic() > deadline:
                callback()
            elif not self.ready:
                QTimer.singleShot(POLL_MS, check)
            else:
                QTimer.singleShot(POLL_MS, lambda: self.view.page().runJavaScript(
                    READY_JS, 0, lambda ok: check(bool(ok))))  # fmt: skip

        check()

    def animate(self) -> None:
        """Friday a fini de parler : vol et rotation."""
        if self.ready:
            self.view.page().runJavaScript("window.fridayMove && window.fridayMove();")

    def still(self) -> None:
        if self.ready:
            self.view.page().runJavaScript("window.fridayStop && window.fridayStop();")

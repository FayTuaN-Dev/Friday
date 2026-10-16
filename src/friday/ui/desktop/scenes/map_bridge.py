"""Ce que la page de la carte demande à Friday (boutons de la carte, layers_js.py) : les
avions de ce qui est à l'écran. La demande part sur un fil à part (OpenSky répond en moins
d'une seconde, mais le réseau peut traîner) ; la réponse revient à la page en script."""

import json
import logging
import threading

import httpx
from PySide6.QtCore import QObject, Signal

from friday.tools.place import HEADERS
from friday.tools.planes import planes_here
from friday.tools.planes_data import Busy

log = logging.getLogger(__name__)

BUSY = "Le service des avions est saturé ou a atteint sa limite du jour : réessayez plus tard."
DOWN = "Avions indisponibles pour le moment."


class MapBridge(QObject):
    reply = Signal(str)  # le script à jouer dans la page (renvoyé sur le fil de la fenêtre)

    def __init__(self, accent: str, client: httpx.Client | None = None, parent=None) -> None:
        super().__init__(parent)
        self.accent = accent
        self.client = client or httpx.Client(timeout=20, headers=HEADERS)

    def ask(self, request: dict) -> None:
        box = request.get("box")
        if request.get("ask") == "planes" and isinstance(box, list) and len(box) == 4:
            threading.Thread(target=self.planes, args=(box, request.get("id")),
                             daemon=True).start()  # fmt: skip

    def planes(self, box: list, ask_id) -> None:
        try:
            data = {"planes": planes_here(self.client, [float(v) for v in box])}
        except Busy:
            data = {"error": BUSY}
        except Exception as error:  # réseau, réponse illisible : la carte le dit, sans planter
            log.warning("Avions de la carte indisponibles : %s", error)
            data = {"error": DOWN}
        data["id"] = ask_id
        args = ", ".join(json.dumps(v) for v in (data, self.accent))
        self.reply.emit(f"window.fridayPlanesHere && window.fridayPlanesHere({args});")

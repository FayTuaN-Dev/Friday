"""Mode globe : « Friday, ouvre l'œil de Dieu » → le globe God's Eye View dans sa fenêtre.
Le globe et qwen3:8b ne tiennent pas ensemble dans 8 Go (mesuré : le globe prend jusqu'à
1,4 Go) : le temps du globe, un petit modèle (4b) remplace le cerveau. Fenêtre fermée (ou
« Friday, ferme l'œil de Dieu ») → le globe s'arrête et le cerveau habituel revient."""

import logging
import os
import re
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

from friday.app.events import AssistantState
from friday.app.game_mode import say_directly
from friday.app.globe_app import GlobeApp
from friday.app.gpu_reload import swap_brain
from friday.brain import gpu_gate
from friday.core.config import ROOT_DIR
from friday.tools.base import Display
from friday.voice.wake import normalize

if TYPE_CHECKING:
    from friday.app.assistant import Assistant

log = logging.getLogger(__name__)

# « œil » devient « l il » une fois normalisé (le « œ » disparaît) ; « oeil » reste « oeil »
NAME = re.compile(r"\b((oe)?il de dieu|gods? ?eyes?|god s eyes?|mode globe)\b")
CLOSE = re.compile(r"\b(ferm\w*|quitt\w*|arret\w*|sor[st]\w*|fin|stop\w*|eteins?)\b")
WATCH_EVERY = 2.0
GRACE = 30.0  # fenêtre jamais vue au bout de ce temps : on considère qu'elle est fermée
# Profil du navigateur du globe : hors de data/ (sauvegardé chaque jour), son cache pèserait
PROFILE = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Friday" / "globe-navigateur"


def asks_globe(text: str) -> bool:
    plain = normalize(text)
    return bool(NAME.search(plain)) and not CLOSE.search(plain)


def asks_globe_closed(text: str) -> bool:
    plain = normalize(text)
    return bool(CLOSE.search(plain)) and bool(NAME.search(plain) or "globe" in plain)


def model_thinks(client, model: str) -> bool | None:
    """True/False : le modèle sait réfléchir ou non ; None : il n'est pas installé."""
    try:
        return "thinking" in (getattr(client.show(model), "capabilities", None) or [])
    except Exception:
        return None


class GlobeMode:
    def __init__(self, assistant: "Assistant", app: GlobeApp | None = None) -> None:
        self.assistant = assistant
        folder = (
            Path(assistant.settings.globe_dir)
            if getattr(assistant.settings, "globe_dir", "")
            else ROOT_DIR.parent / "gods-eye-view"
        )
        self.app = app or GlobeApp(folder, PROFILE)
        self.on = False

    def toggle(self) -> None:
        """Bouton de la barre de titre ou menu de l'icône."""
        self.assistant.post("globe", "leave" if self.on else "enter")

    # --- Dans le fil de l'assistant ---

    def command(self, text: str) -> bool:
        if not self.on and asks_globe(text):
            self.enter()
            return True
        if self.on and asks_globe_closed(text):
            self.leave()
            return True
        return False

    def event(self, what: str) -> None:
        if what == "enter":
            self.enter()
        elif what in ("leave", "closed"):
            self.leave(closed=what == "closed")

    def enter(self) -> None:
        a = self.assistant
        if self.on or a.game.paused:
            return
        small = a.settings.globe_model
        if not self.app.installed:
            say_directly(a, f"L'œil de Dieu n'est pas installé : il faut le dossier "
                            f"gods-eye-view dans {self.app.folder.parent}.")  # fmt: skip
            return
        thinks = model_thinks(a.components.brain.client, small)
        if thinks is None:
            say_directly(a, f"Il me manque le petit modèle {small} : installez-le avec "
                            f"ollama pull {small}.")  # fmt: skip
            return
        say_directly(a, "J'ouvre l'œil de Dieu. Je passe sur mon petit cerveau le temps que "
                        "vous regardiez.", wait=False)  # fmt: skip
        a.set_state(AssistantState.LOADING)
        start = time.monotonic()
        swap_brain(a, small, thinks)
        if not self.app.start() or not self.app.open_window():
            self.app.close()
            swap_brain(a, None)
            say_directly(a, "Le globe ne démarre pas, désolée. Je reprends mon cerveau habituel.")
            return
        self.on = True
        a.listener.on_display(Display("globe_mode", "Œil de Dieu", {"on": True}))
        log.info("Mode globe : %s à la place de %s, globe ouvert en %.1f s", small,
                 a.settings.ollama_model, time.monotonic() - start)  # fmt: skip
        threading.Thread(target=self._watch, daemon=True, name="globe-watch").start()

    def leave(self, closed: bool = False) -> None:
        """`closed` : la fenêtre a été fermée (sinon, Friday la ferme elle-même)."""
        a = self.assistant
        if not self.on:
            return
        self.on = False
        a.listener.on_display(Display("globe_mode", "Œil de Dieu", {"on": False}))
        self.app.close()
        if a.game.paused:  # en pleine partie : le retour du mode jeu rechargera le gros
            gpu_gate.STAND_IN.clear()
            gpu_gate.NO_THINK.clear()
            return
        say_directly(a, "Globe fermé : je reprends mon cerveau habituel.", wait=False)
        a.set_state(AssistantState.LOADING)
        start = time.monotonic()
        swap_brain(a, None)
        log.info("Mode globe terminé : %s rechargé en %.1f s", a.settings.ollama_model,
                 time.monotonic() - start)  # fmt: skip

    def shutdown(self) -> None:
        """Friday s'arrête : le globe aussi (pas besoin de recharger quoi que ce soit)."""
        if self.on:
            self.on = False
            self.app.close()

    # --- Fil de surveillance ---

    def _watch(self) -> None:
        opened, seen = time.monotonic(), False
        while self.on:
            time.sleep(WATCH_EVERY)
            if not self.on:
                return
            if self.app.window_open():
                seen = True
            elif seen or time.monotonic() - opened > GRACE:
                log.info("Mode globe : fenêtre fermée")
                self.assistant.post("globe", "closed")
                return

"""Push-to-talk : une touche globale (fonctionne même si le terminal n'a pas le focus)."""

import logging
from collections.abc import Callable

import keyboard

log = logging.getLogger(__name__)


class PushToTalk:
    def __init__(self, key: str, on_press: Callable[[], None], on_release: Callable[[], None]):
        self.key = key
        self._on_press = on_press
        self._on_release = on_release
        self._down = False
        keyboard.on_press_key(key, self._press)
        keyboard.on_release_key(key, self._release)

    def _press(self, _event) -> None:
        if self._down:  # la touche maintenue envoie des répétitions
            return
        self._down = True
        self._safe(self._on_press)

    def _release(self, _event) -> None:
        if not self._down:
            return
        self._down = False
        self._safe(self._on_release)

    @staticmethod
    def _safe(fn: Callable[[], None]) -> None:
        try:
            fn()
        except Exception:
            log.exception("Erreur dans le push-to-talk")

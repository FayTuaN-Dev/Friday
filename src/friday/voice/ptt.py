"""Push-to-talk : une touche globale (fonctionne même si la fenêtre n'a pas le focus)."""

import logging
from collections.abc import Callable

import keyboard

log = logging.getLogger(__name__)


class PushToTalk:
    def __init__(self, key: str, on_press: Callable[[], None], on_release: Callable[[], None],
                 on_other_key: Callable[[], None] | None = None):  # fmt: skip
        self.key = key
        self._on_press = on_press
        self._on_release = on_release
        self._down = False
        # Un seul crochet pour l'appui et le relâchement : il se retire proprement.
        self._hook = keyboard.hook_key(key, self._on_event)
        # Une autre touche pendant l'appui (Ctrl+C avec Ctrl comme touche) : prévenu
        self._others = None
        if on_other_key is not None:
            codes = set(keyboard.key_to_scan_codes(key))
            self._others = keyboard.on_press(
                lambda event: (
                    self._down and event.scan_code not in codes and self._safe(on_other_key)
                )  # fmt: skip
            )

    def close(self) -> None:
        if self._hook is not None:
            keyboard.unhook(self._hook)
            self._hook = None
        if self._others is not None:
            keyboard.unhook(self._others)
            self._others = None

    def _on_event(self, event) -> None:
        if event.event_type == keyboard.KEY_DOWN:
            if self._down:  # la touche maintenue envoie des répétitions
                return
            self._down = True
            self._safe(self._on_press)
        elif self._down:
            self._down = False
            self._safe(self._on_release)

    @staticmethod
    def _safe(fn: Callable[[], None]) -> None:
        try:
            fn()
        except Exception:
            log.exception("Erreur dans le push-to-talk")

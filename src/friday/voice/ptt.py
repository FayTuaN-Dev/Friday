"""Push-to-talk : une touche globale (fonctionne même si la fenêtre n'a pas le focus).

Les touches « de droite » ou « de gauche » (Ctrl droit, Maj gauche…) ne sont jamais vues par
`keyboard.hook_key` sous Windows : leur code étendu (57373 pour Ctrl droit) n'arrive pas dans
les évènements, qui portent le code de base (29, comme Ctrl gauche). Constaté avec la dictée
sur Ctrl droit. Pour elles, on lit l'état de la touche toutes les 20 ms.
"""

import logging
import threading
from collections.abc import Callable

import keyboard

log = logging.getLogger(__name__)

# Touches latérales : code Windows (virtual key) de chacune
SIDED = {
    "left shift": 0xA0, "right shift": 0xA1, "left ctrl": 0xA2, "right ctrl": 0xA3,
    "left alt": 0xA4, "right alt": 0xA5, "left windows": 0x5B, "right windows": 0x5C,
}  # fmt: skip
POLL_SECONDS = 0.02


def key_is_down(vk: int) -> bool:
    import ctypes

    return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)


class PushToTalk:
    def __init__(self, key: str, on_press: Callable[[], None], on_release: Callable[[], None],
                 on_other_key: Callable[[], None] | None = None,
                 is_down: Callable[[int], bool] = key_is_down):  # fmt: skip
        self.key = key
        self._on_press = on_press
        self._on_release = on_release
        self._down = False
        self._hook = self._others = self._poller = None
        self._stop = threading.Event()
        vk = SIDED.get(key.strip().lower())
        codes = set(keyboard.key_to_scan_codes(key))
        if vk is None:
            # Un seul crochet pour l'appui et le relâchement : il se retire proprement.
            self._hook = keyboard.hook_key(key, self._on_event)
        else:
            codes |= {code & 0xFF for code in codes}  # le code de base, porté par l'évènement
            self._poller = threading.Thread(target=self._poll, args=(vk, is_down), daemon=True,
                                            name=f"touche {key}")  # fmt: skip
            self._poller.start()
        # Une autre touche pendant l'appui (Ctrl+C avec Ctrl comme touche) : prévenu
        if on_other_key is not None:
            self._others = keyboard.on_press(
                lambda event: (
                    self._down and event.scan_code not in codes and self._safe(on_other_key)
                )  # fmt: skip
            )

    def close(self) -> None:
        self._stop.set()
        if self._hook is not None:
            keyboard.unhook(self._hook)
            self._hook = None
        if self._others is not None:
            keyboard.unhook(self._others)
            self._others = None

    def _poll(self, vk: int, is_down: Callable[[int], bool]) -> None:
        while not self._stop.wait(POLL_SECONDS):
            try:
                down = is_down(vk)
            except Exception:
                log.exception("État de la touche « %s » illisible", self.key)
                return
            if down != self._down:
                self._on_event(type("Event", (), {"event_type": keyboard.KEY_DOWN
                                                  if down else keyboard.KEY_UP}))  # fmt: skip

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

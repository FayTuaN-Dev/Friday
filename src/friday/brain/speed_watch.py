"""Surveillance d'Ollama : la vitesse de chaque réponse (jetons par seconde, donnée par Ollama
à la fin du flux) est comparée à la vitesse normale. Si elle s'effondre deux réponses de
suite (constaté une fois : le modèle à moitié sorti de la carte graphique), le modèle est
rechargé tout seul, en arrière-plan."""

import logging
import threading
import time
from collections.abc import Callable

log = logging.getLogger(__name__)

MIN_TOKENS = 20  # une réponse trop courte ne dit rien de la vitesse
SLOW = 0.35  # sous 35 % de la vitesse normale : effondrée
STRIKES = 2  # réponses lentes d'affilée avant de recharger
PAUSE = 600  # secondes minimum entre deux rechargements


class SpeedWatch:
    def __init__(self, reload: Callable[[], None], clock: Callable[[], float] = time.monotonic,
                 background: bool = True) -> None:  # fmt: skip
        """`reload()` : décharge puis recharge le modèle (lent : lancé dans un fil à part)."""
        self.reload, self.clock, self.background = reload, clock, background
        self.normal: float | None = None  # vitesse normale (jetons / s)
        self.last: float | None = None
        self.strikes = 0
        self.reloads: list[float] = []  # instants des rechargements (pour le diagnostic)

    def record(self, chunk) -> None:
        """Le dernier morceau du flux d'Ollama (done=True) : eval_count, eval_duration (ns)."""
        count, duration = getattr(chunk, "eval_count", None), getattr(chunk, "eval_duration", None)
        if not count or not duration or count < MIN_TOKENS:
            return
        speed = count / (duration / 1e9)
        self.last = speed
        if self.normal is None or speed >= self.normal * SLOW:
            # moyenne glissante des réponses normales (la carte se réchauffe, le contexte grandit)
            self.normal = speed if self.normal is None else 0.8 * self.normal + 0.2 * speed
            self.strikes = 0
            return
        self.strikes += 1
        log.warning("Ollama lent : %.1f jetons/s (normal : %.1f), %d/%d", speed, self.normal,
                    self.strikes, STRIKES)  # fmt: skip
        recent = self.reloads and self.clock() - self.reloads[-1] < PAUSE
        if self.strikes >= STRIKES and not recent:
            self.strikes = 0
            self.reloads.append(self.clock())
            log.warning("Vitesse effondrée : rechargement du modèle")
            if self.background:
                threading.Thread(target=self._reload, daemon=True, name="ollama-reload").start()
            else:
                self._reload()

    def _reload(self) -> None:
        try:
            self.reload()
            log.info("Modèle rechargé")
        except Exception:
            log.exception("Rechargement du modèle impossible")

"""Surveillance d'Ollama : la vitesse de chaque réponse (jetons par seconde, donnée par Ollama
à la fin du flux) est comparée à la vitesse normale. Si elle s'effondre deux réponses de
suite (constaté une fois : le modèle à moitié sorti de la carte graphique), le modèle est
rechargé tout seul, en arrière-plan.

La vitesse de LECTURE du contexte est surveillée aussi : constaté après le regard sur l'écran,
elle tombe de 2 400 à 140 jetons/s (40 s d'attente par réponse) alors que l'écriture ne baisse
que d'un tiers. Le cache d'Ollama la rend très variable (une partie déjà lue compte comme
lue en un instant) : on juge donc sur un plancher fixe, une seule fois suffit."""

import logging
import threading
import time
from collections.abc import Callable

log = logging.getLogger(__name__)

MIN_TOKENS = 20  # une réponse trop courte ne dit rien de la vitesse
SLOW = 0.35  # sous 35 % de la vitesse normale : effondrée
STRIKES = 2  # réponses lentes d'affilée avant de recharger
PAUSE = 600  # secondes minimum entre deux rechargements
MIN_READ = 1000  # jetons lus : en dessous, la mesure ne dit rien
READ_FLOOR = 500  # jetons lus par seconde : normal au-dessus de 1 800 sur la RTX 3070


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
        if self._reading_collapsed(chunk):
            self._trigger()
            return
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
        if self.strikes >= STRIKES:
            self._trigger()

    def _reading_collapsed(self, chunk) -> bool:
        count = getattr(chunk, "prompt_eval_count", None)
        duration = getattr(chunk, "prompt_eval_duration", None)
        if not count or not duration or count < MIN_READ:
            return False
        speed = count / (duration / 1e9)
        if speed >= READ_FLOOR:
            return False
        log.warning("Ollama lit lentement : %.0f jetons/s sur %d jetons", speed, count)
        return True

    def _trigger(self) -> None:
        if self.reloads and self.clock() - self.reloads[-1] < PAUSE:
            return
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

"""Données préparées en avance pendant le mode trading : les sources publiques les plus lentes
(données de marché ~0,3 s, marchés liés ~0,6 s, actualités) sont gardées quelques dizaines de
secondes en mémoire, et rafraîchies en arrière-plan pour l'instrument courant et ceux qu'on
surveille. L'aperçu d'une analyse les trouve prêtes au lieu de les attendre.

Seules des données publiques sont concernées ; rien de l'utilisateur n'est préparé ni envoyé.
"""

import logging
import threading
import time
from collections.abc import Callable

log = logging.getLogger(__name__)
FRESH = 90  # secondes : au-delà, la donnée est relue
EVERY = 30  # secondes entre deux rafraîchissements (toujours fraîche à l'aperçu)


class Warm:
    def __init__(self, fresh: float = FRESH, clock: Callable[[], float] = time.monotonic) -> None:
        self.fresh, self.clock = fresh, clock
        self._data: dict[tuple, tuple[float, object]] = {}
        self._lock = threading.Lock()

    def wrap(self, name: str, fn: Callable) -> Callable:
        """`fn` gardée `fresh` secondes par arguments ; une erreur n'est jamais gardée."""

        def cached(*args):
            key = (name, *args)
            with self._lock:
                found = self._data.get(key)
            if found is not None and self.clock() - found[0] < self.fresh:
                return found[1]
            value = fn(*args)
            with self._lock:
                self._data[key] = (self.clock(), value)
            return value

        return cached

    def forget(self) -> None:
        with self._lock:
            self._data.clear()


def start_warming(trading, tasks: Callable[[object], None], interval: float = EVERY):
    """Tant que le mode trading est actif, `tasks(instrument)` pour l'instrument courant et
    ceux qu'on surveille, toutes les `interval` secondes (la première fois aussitôt)."""
    stop = threading.Event()

    def instruments():
        found = [trading.current]
        alerts = getattr(trading, "alerts", None)
        if alerts is not None:
            from friday.trading.instruments import by_symbol

            found += [by_symbol(a.symbol) for a in alerts.store.all() if a.kind == "setup"]
        return [i for n, i in enumerate(found) if i is not None and i not in found[:n]]

    def loop():
        while not stop.is_set():
            if trading.mode.enabled:
                for instrument in instruments():
                    try:
                        tasks(instrument)
                    except Exception as error:  # une source en panne : l'aperçu le dira
                        log.info("Préparation des données de %s : %s", instrument.symbol, error)
            stop.wait(interval)

    threading.Thread(target=loop, daemon=True, name="trading-warm").start()
    return stop

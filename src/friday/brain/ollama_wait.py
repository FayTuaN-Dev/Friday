"""Attendre Ollama au démarrage (S3). Lancée avec Windows, Friday est souvent prête avant
Ollama : sans attendre, le préchargement de qwen échouait et le modèle se chargeait plus
tard, après Whisper, à l'étroit dans la carte graphique (lent). On attend donc qu'Ollama
réponde avant de charger quoi que ce soit, dans l'ordre habituel."""

import logging
import time
from collections.abc import Callable

log = logging.getLogger(__name__)

PATIENCE = 180.0  # secondes : un PC qui démarre peut être long
STEP = 2.0


def wait_for_ollama(
    client,
    patience: float = PATIENCE,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> bool:
    """Renvoie True dès qu'Ollama répond, False si la patience est épuisée."""
    start = clock()
    waited = False
    while True:
        try:
            client.list()
            if waited:
                log.info("Ollama joignable après %.0f s d'attente", clock() - start)
            return True
        except Exception as error:  # pas encore lancé : connexion refusée
            if clock() - start >= patience:
                log.warning("Ollama toujours injoignable après %.0f s (%s)", patience, error)
                return False
            if not waited:
                log.info("Ollama pas encore prêt : Friday l'attend")
                waited = True
            sleep(STEP)

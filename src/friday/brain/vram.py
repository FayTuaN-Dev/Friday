"""Mémoire vidéo partagée entre les modèles d'Ollama (8 Go : un seul gros modèle à la fois).

Constaté : un modèle déchargé avec keep_alive=0 libère la carte APRÈS la réponse d'Ollama.
Si qwen3 se recharge pendant ce temps, Windows en range une partie dans la mémoire du PC et
il lit ensuite son contexte 15 fois plus lentement (140 jetons/s au lieu de 2 400) jusqu'au
prochain rechargement. On attend donc que la place soit vraiment libre.
"""

import logging
import time
from collections.abc import Callable

log = logging.getLogger(__name__)

TIMEOUT = 10.0  # secondes au plus
PAUSE = 0.25


def wait_unloaded(client, model: str, timeout: float = TIMEOUT,
                  sleep: Callable[[float], None] = time.sleep) -> bool:  # fmt: skip
    """Attend que `model` ait quitté la mémoire d'Ollama. False si toujours là au bout du délai
    (ou si Ollama ne répond pas : on n'attend pas pour rien)."""
    waited = 0.0
    while waited < timeout:
        try:
            loaded = [m.model for m in client.ps().models]
        except Exception:  # client de test, Ollama injoignable…
            return False
        if not any(name == model or name.startswith(model + ":") for name in loaded):
            return True
        sleep(PAUSE)
        waited += PAUSE
    log.warning("« %s » toujours en mémoire après %.0f s", model, timeout)
    return False
